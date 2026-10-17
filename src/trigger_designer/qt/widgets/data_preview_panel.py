"""The Data Preview surface: info line, paged table, paging footer.

One panel per host (standalone window or dock). It owns a
`PreviewRequestController`, so collecting and counting never run on the GUI
thread; the host only calls `set_source()`/`refresh()` and binds the panel's
signals. The table itself is the embedded `PolarsTableViewer`.
"""

from typing import Any

from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QKeySequence
from qtpy.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QShortcut,
    QVBoxLayout,
    QWidget,
)

from trigger_designer.qt.models.polars_table_viewer import PolarsTableViewer
from trigger_designer.qt.models.preview_sampling import PreviewWindow
from trigger_designer.qt.models.preview_worker import PreviewRequestController
from trigger_designer.qt.resource_manager import ResourceManager
from trigger_designer.qt.widgets.common import (
    EmptyStateLabel,
    IconButton,
    NoWheelComboBox,
)

_PAGE_SIZES = ("100", "250", "500", "1000")
_BLANK_STATE = "Select a node to preview its output"


class DataPreviewPanel(QWidget):
    """Renders a preview: info line, paged table, paging footer.

    Empty and failure states all render through one `EmptyStateLabel`; the
    table and footer swap in for real data.
    """

    titleChanged = Signal(str)

    def __init__(
        self,
        parent: QWidget | None = None,
        max_rows: int = 1000,
        max_size_mb: float = 2.0,
    ) -> None:
        super().__init__(parent)
        self.rsm = ResourceManager()
        self.controller = PreviewRequestController(
            max_rows=max_rows, max_size_mb=max_size_mb, parent=self
        )
        self.controller.previewReady.connect(self._on_preview_ready)
        self.controller.countReady.connect(self._on_count_ready)
        self.controller.failed.connect(self._on_failed)

        self._payload: Any = None
        self._title = ""
        self._window: PreviewWindow | None = None
        self._count_pending = False

        layout = QVBoxLayout(self)
        layout.setSpacing(2)
        layout.setContentsMargins(5, 5, 5, 5)

        self.info_label = QLabel(self)
        self.info_label.setObjectName("PreviewInfoLabel")
        self.info_label.setVisible(False)
        layout.addWidget(self.info_label)

        self._state_label = EmptyStateLabel(_BLANK_STATE, self)
        layout.addWidget(self._state_label, 1)

        self._content = QWidget(self)
        content_layout = QVBoxLayout(self._content)
        content_layout.setSpacing(2)
        content_layout.setContentsMargins(0, 0, 0, 0)

        self.viewer = PolarsTableViewer(
            parent=self._content,
            show_controls=True,
            show_info=False,
            show_search=True,
            show_export=False,
        )
        content_layout.addWidget(self.viewer, 1)
        content_layout.addWidget(self._create_footer())
        self._content.setVisible(False)
        layout.addWidget(self._content, 1)

        self._refresh_shortcut = QShortcut(QKeySequence("Ctrl+R"), self)
        self._refresh_shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
        self._refresh_shortcut.activated.connect(self.refresh)

        self.viewer.model.modelReset.connect(self._sync_footer)

    # -- public API ---------------------------------------------------------

    def set_source(
        self,
        payload: Any,
        title: str | None = None,
        empty_text: str | None = None,
    ) -> None:
        """Point the panel at ``payload`` (DataFrame/LazyFrame or None).

        ``empty_text`` overrides the placeholder shown for ``payload=None``,
        so a host can distinguish "nothing selected" from "not tabular".
        """
        if title is not None and title != self._title:
            self._title = title
            self.titleChanged.emit(title)
        self._payload = payload
        if payload is None:
            self._window = None
            self._count_pending = False
            self._show_state(empty_text or _BLANK_STATE)
            return
        if self._window is None:
            self._show_state("Loading...")
        self.controller.request(payload)

    def refresh(self) -> None:
        """Re-request the current payload (no-op when none is set)."""
        if self._payload is None:
            return
        self.controller.request(self._payload)

    # -- controller results -------------------------------------------------

    def _on_preview_ready(self, window: PreviewWindow) -> None:
        self._window = window
        self._count_pending = bool(window.limited and window.is_lazy)
        if window.frame.height == 0:
            self._show_state("No rows")
            return
        self.viewer.set_dataframe(window.frame)
        self._show_content()
        self._update_info_line()
        self._sync_footer()

    def _on_count_ready(self, count: int) -> None:
        self._count_pending = False
        if self._window is None:
            return
        if count >= 0:
            self._window.total_rows = count
        self._update_info_line()

    def _on_failed(self, message: str) -> None:
        self._window = None
        self._count_pending = False
        self._show_state(f"Preview failed: {message}")

    # -- info line / states -------------------------------------------------

    def _update_info_line(self) -> None:
        if self._window is None:
            return
        collected = self._window.frame.height
        columns = len(self._window.frame.columns)
        total = self._window.total_rows
        if total is not None and total > collected:
            text = f"{collected:,} rows collected - {total:,} total - {columns} columns"
        elif self._count_pending:
            text = f"{collected:,} rows collected - counting... - {columns} columns"
        elif self._window.limited and total is None:
            # Counting failed; the frame is still known to be truncated.
            text = f"{collected:,} rows collected - {columns} columns"
        else:
            text = f"{collected:,} rows - {columns} columns"
        self.info_label.setText(text)

    def _show_state(self, text: str) -> None:
        self._state_label.setText(text)
        self._state_label.setVisible(True)
        self._content.setVisible(False)
        self.info_label.setVisible(False)

    def _show_content(self) -> None:
        self._state_label.setVisible(False)
        self._content.setVisible(True)
        self.info_label.setVisible(True)

    # -- footer -------------------------------------------------------------

    def _create_footer(self) -> QWidget:
        footer = QWidget(self._content)
        footer.setFixedHeight(30)
        layout = QHBoxLayout(footer)
        layout.setSpacing(2)
        layout.setContentsMargins(0, 0, 0, 0)

        self._first_btn = IconButton.themed(
            "First page",
            rsm_icon=self.rsm.get("icon_chevron_first"),
            qss_fallback=":/qss_icons/dark/rc/arrow_up.png",
            theme_fallback="go-first",
            parent=footer,
        )
        self._prev_btn = IconButton.themed(
            "Previous page",
            rsm_icon=self.rsm.get("icon_chevron_prev"),
            qss_fallback=":/qss_icons/dark/rc/arrow_left.png",
            theme_fallback="go-previous",
            parent=footer,
        )
        self._next_btn = IconButton.themed(
            "Next page",
            rsm_icon=self.rsm.get("icon_chevron_next"),
            qss_fallback=":/qss_icons/dark/rc/arrow_right.png",
            theme_fallback="go-next",
            parent=footer,
        )
        self._last_btn = IconButton.themed(
            "Last page",
            rsm_icon=self.rsm.get("icon_chevron_last"),
            qss_fallback=":/qss_icons/dark/rc/arrow_down.png",
            theme_fallback="go-last",
            parent=footer,
        )

        self._first_btn.clicked.connect(lambda: self._go_to_page(0))
        self._prev_btn.clicked.connect(
            lambda: self._go_to_page(self.viewer.model.page_index - 1)
        )
        self._next_btn.clicked.connect(
            lambda: self._go_to_page(self.viewer.model.page_index + 1)
        )
        self._last_btn.clicked.connect(
            lambda: self._go_to_page(self.viewer.model.page_count - 1)
        )

        for button in (
            self._first_btn,
            self._prev_btn,
            self._next_btn,
            self._last_btn,
        ):
            layout.addWidget(button)

        self.page_size_combo = NoWheelComboBox(footer)
        self.page_size_combo.setMinimumHeight(30)
        self.page_size_combo.setToolTip("Rows per page")
        self.page_size_combo.setAccessibleName("Rows per page")
        self.page_size_combo.addItems(list(_PAGE_SIZES))
        self.page_size_combo.setCurrentText("250")
        self.page_size_combo.currentTextChanged.connect(self._on_page_size_changed)
        layout.addWidget(self.page_size_combo)

        self.range_label = QLabel("", footer)
        self.range_label.setObjectName("PreviewRangeLabel")
        layout.addWidget(self.range_label)

        layout.addStretch()
        return footer

    def _go_to_page(self, index: int) -> None:
        self.viewer.model.set_page(index)

    def _on_page_size_changed(self, text: str) -> None:
        try:
            size = int(text)
        except ValueError:
            return
        if size != self.viewer.model.page_size:
            self.viewer.model.set_page_size(size)

    def _sync_footer(self) -> None:
        model = self.viewer.model
        rows = model.rowCount()
        first = model.page_offset + 1 if rows else 0
        last = model.page_offset + rows if rows else 0
        self.range_label.setText(f"Rows {first:,}-{last:,} of {model.total_rows:,}")
        on_first = model.page_index <= 0
        on_last = model.page_index >= model.page_count - 1
        self._first_btn.setEnabled(not on_first)
        self._prev_btn.setEnabled(not on_first)
        self._next_btn.setEnabled(not on_last)
        self._last_btn.setEnabled(not on_last)
