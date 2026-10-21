"""Non-modal window that renders the Graph node's chart with matplotlib.

The window opens from the node's Show graph button, which unlocks only after
a successful workflow run. The matplotlib navigation toolbar gives zoom, pan
and a save button, so the window is the only place a file is written and only
when the user asks.
"""

from __future__ import annotations

from matplotlib.backends.backend_qtagg import NavigationToolbar2QT
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QLabel, QVBoxLayout, QWidget

from trigger_designer.core.charts import ChartSpec, status_text
from trigger_designer.qt.widgets.nodes.Report.chart_view import ChartView

#: Window size used when the node opens a chart (pixels).
DEFAULT_WINDOW_SIZE = (900, 620)


class _ChartToolbar(NavigationToolbar2QT):
    """Toolbar without the subplot editor.

    ``configure_subplots`` calls ``subplots_adjust`` and switches the figure
    to a tight layout, which conflicts with the constrained layout the chart
    draws with; the rest of the toolbar (home, pan, zoom, save) is fine.
    """

    toolitems = tuple(
        item for item in NavigationToolbar2QT.toolitems if item[0] != "Subplots"
    )


class ChartWindow(QWidget):
    """Independent, non-modal chart window."""

    def __init__(
        self,
        parent: QWidget | None = None,
        title: str = "Graph",
        size: tuple[int, int] = DEFAULT_WINDOW_SIZE,
    ) -> None:
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.setWindowTitle(title)
        self.resize(*size)

        self.chart_view = ChartView(self)
        self.toolbar = _ChartToolbar(self.chart_view.canvas, self)

        self.status_label = QLabel(self)
        # The shared small-caption style; no per-window QSS.
        self.status_label.setObjectName("PreviewStatusLabel")
        self.status_label.setContentsMargins(8, 2, 8, 6)
        self.status_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.chart_view, 1)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.status_label)

    def set_spec(self, spec: ChartSpec | None) -> None:
        """Draw ``spec`` and describe it under the plot."""
        self.chart_view.set_spec(spec)
        self.status_label.setText(status_text(spec))
