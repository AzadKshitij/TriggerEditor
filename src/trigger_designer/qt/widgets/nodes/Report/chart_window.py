"""Non-modal window that renders the Graph node's chart.

The window opens from the node's Show graph button, which unlocks only after
a successful workflow run. The window is the only place a file is written,
and only when the user asks; the toolbar belongs to the renderer, so each
renderer module builds its own (matplotlib's navigation toolbar, pyqtgraph's
small reset/save row).

Only the selected renderer is imported: the module name is resolved through
``_RENDERER_MODULES`` at build time, so choosing pyqtgraph never pulls
matplotlib into the process, or the other way around.
"""

from __future__ import annotations

import importlib

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QLabel, QVBoxLayout, QWidget

from trigger_designer.core.charts import ChartSpec, status_text
from trigger_designer.qt.widgets.nodes.Report.chart_renderer import ChartRenderer

#: Renderer key -> module exposing ``create_view`` and ``create_toolbar``.
_RENDERER_MODULES = {
    "matplotlib": "trigger_designer.qt.widgets.nodes.Report.chart_view",
    "pyqtgraph": "trigger_designer.qt.widgets.nodes.Report.pyqtgraph_view",
}

#: The renderer every saved workflow drew with before this setting existed.
DEFAULT_RENDERER = "matplotlib"

#: Window size used when the node opens a chart (pixels).
DEFAULT_WINDOW_SIZE = (900, 620)


class ChartWindow(QWidget):
    """Independent, non-modal chart window."""

    def __init__(
        self,
        parent: QWidget | None = None,
        title: str = "Graph",
        size: tuple[int, int] = DEFAULT_WINDOW_SIZE,
        renderer: str = DEFAULT_RENDERER,
    ) -> None:
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.setWindowTitle(title)
        self.resize(*size)

        #: The live renderer's view and toolbar; swapped by ``set_renderer``.
        self.chart_view: ChartRenderer | None = None
        self.toolbar: QWidget | None = None

        self.status_label = QLabel(self)
        # The shared small-caption style; no per-window QSS.
        self.status_label.setObjectName("PreviewStatusLabel")
        self.status_label.setContentsMargins(8, 2, 8, 6)
        self.status_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.status_label)

        self._renderer = ""
        self._install_renderer(renderer)

    @property
    def renderer(self) -> str:
        """The drawing library the window currently shows."""
        return self._renderer

    def set_renderer(self, renderer: str) -> None:
        """Swap renderers in place; the window redraws its last spec."""
        if renderer not in _RENDERER_MODULES:
            renderer = DEFAULT_RENDERER
        if renderer == self._renderer:
            return
        spec = self.chart_view.spec if self.chart_view is not None else None
        self._remove_renderer()
        self._install_renderer(renderer)
        if spec is not None:
            self.set_spec(spec)

    def set_spec(self, spec: ChartSpec | None) -> None:
        """Draw ``spec`` and describe it under the plot."""
        if self.chart_view is not None:
            self.chart_view.set_spec(spec)
        self.status_label.setText(status_text(spec))

    # -- renderer plumbing --------------------------------------------------
    def _install_renderer(self, renderer: str) -> None:
        """Import one renderer module and mount its view and toolbar."""
        if renderer not in _RENDERER_MODULES:
            renderer = DEFAULT_RENDERER
        module = importlib.import_module(_RENDERER_MODULES[renderer])
        view = module.create_view(self)
        toolbar = module.create_toolbar(view, self)

        self._renderer = renderer
        self.chart_view = view
        self.toolbar = toolbar
        # Built top-down: the plot takes the stretch, its toolbar sits under
        # it, and the status caption stays the window's last row.
        self.layout().insertWidget(0, toolbar)
        self.layout().insertWidget(0, view, 1)

    def _remove_renderer(self) -> None:
        """Unhook and release the current view and toolbar."""
        if self.toolbar is not None:
            self.layout().removeWidget(self.toolbar)
            self.toolbar.hide()
            self.toolbar.deleteLater()
        if self.chart_view is not None:
            self.layout().removeWidget(self.chart_view)
            # The plot releases itself in its own event-loop pass (see the
            # renderers' ``dispose``), before the widget goes.
            self.chart_view.dispose()
            self.chart_view.deleteLater()
        self.chart_view = None
        self.toolbar = None
