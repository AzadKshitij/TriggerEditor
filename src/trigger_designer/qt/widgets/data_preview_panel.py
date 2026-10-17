"""The Data Preview surface: one strip over the whole collected frame.

One panel per host (standalone window or dock). It owns a
`PreviewRequestController`, so collecting and counting never run on the GUI
thread; the host calls `set_source()`/`set_node()` and binds the panel's
signals. The table is the embedded `PolarsTableViewer`.

The frame the controller collected is shown whole as a single page, so there
is no paging footer - the strip carries what the footer and the old info line
did. It reads left to right: the node on screen (and whether it is pinned),
the output socket when the node has more than one, a live search with an
all-columns scope, the row/column counts, then pin, refresh and the options
menu. A host that does not track nodes (the standalone window) never fills
the node, socket or pin parts, and they stay hidden.
"""

from typing import Any

from qtpy.QtCore import Qt, QTimer, Signal
from qtpy.QtGui import QIcon, QKeySequence
from qtpy.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QShortcut,
    QVBoxLayout,
    QWidget,
)

from trigger_designer.qt.models.polars_table_viewer import (
    ALL_COLUMNS_LABEL,
    PolarsTableViewer,
)
from trigger_designer.qt.models.preview_sampling import PreviewWindow
from trigger_designer.qt.models.preview_worker import PreviewRequestController
from trigger_designer.qt.resource_manager import ResourceManager
from trigger_designer.qt.widgets.common import (
    EmptyStateLabel,
    IconButton,
    NoWheelComboBox,
)

_BLANK_STATE = "Select a node to preview its output"
_SEARCH_DEBOUNCE_MS = 300
_STRIP_HEIGHT = 36
_CHIP_HEIGHT = 24
_ROW_HEIGHT = 24
_NODE_LABEL_WIDTH = 150


class DataPreviewPanel(QWidget):
    """A 36px strip over a table that shows the whole collected frame."""

    pinned = Signal(bool)
    socketChanged = Signal(int)

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
        self.controller.busyChanged.connect(self._on_busy_changed)

        self._payload: Any = None
        self._window: PreviewWindow | None = None
        self._count_pending = False

        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # The table first: the strip's options menu binds to the viewer.
        self._content = QWidget(self)
        content_layout = QVBoxLayout(self._content)
        content_layout.setSpacing(0)
        content_layout.setContentsMargins(0, 0, 0, 0)
        self.viewer = PolarsTableViewer(
            parent=self._content,
            show_controls=False,
            show_info=False,
            show_search=False,
            show_export=False,
            row_height=_ROW_HEIGHT,
        )
        # Whole-frame view: the collected frame is one page, so the model's
        # paging never engages and the table scrolls on its own.
        self.viewer.model.set_page_size(max(1, int(max_rows)))
        content_layout.addWidget(self.viewer, 1)
        self._content.setVisible(False)

        self._state_label = EmptyStateLabel(_BLANK_STATE, self)

        layout.addWidget(self._build_strip())
        layout.addWidget(self._state_label, 1)
        layout.addWidget(self._content, 1)

        self._refresh_shortcut = QShortcut(QKeySequence("Ctrl+R"), self)
        self._refresh_shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
        self._refresh_shortcut.activated.connect(self.refresh)
        self._find_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        self._find_shortcut.setContext(Qt.ShortcutContext.WidgetShortcut)
        self._find_shortcut.activated.connect(self._focus_search)

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(_SEARCH_DEBOUNCE_MS)
        self._search_timer.timeout.connect(self._apply_search)

        self.viewer.model.modelReset.connect(self._update_status)
        self._update_status()

    # -- public API ---------------------------------------------------------

    def set_source(self, payload: Any, empty_text: str | None = None) -> None:
        """Point the panel at ``payload`` (DataFrame/LazyFrame or None).

        ``empty_text`` overrides the placeholder shown for ``payload=None``,
        so a host can distinguish "nothing selected" from "not tabular".
        """
        self._payload = payload
        if payload is None:
            self._forget_data()
            self._show_state(empty_text or _BLANK_STATE)
            return
        if self._window is None:
            self._show_state("Loading...")
        self._sync_refresh_enabled()
        self.controller.request(payload)

    def refresh(self) -> None:
        """Re-request the current payload (no-op when none is set)."""
        if self._payload is None:
            return
        self.controller.request(self._payload)

    def set_node(
        self,
        title: str | None,
        pinned: bool = False,
        enabled: bool = False,
    ) -> None:
        """Show which node is on screen; ``enabled`` allows pinning it.

        ``title=None`` hides the chip and turns the pin off, so the strip
        never claims a node it is not showing.
        """
        self.node_chip.setVisible(bool(title))
        if title:
            elided = self.node_label.fontMetrics().elidedText(
                title, Qt.TextElideMode.ElideMiddle, _NODE_LABEL_WIDTH
            )
            self.node_label.setText(elided)
            self.node_label.setToolTip(title)
        else:
            self.node_label.setText("")
        self.pin_btn.setEnabled(enabled)
        self.pin_btn.blockSignals(True)
        self.pin_btn.setChecked(bool(pinned) and enabled)
        self.pin_btn.blockSignals(False)
        self._apply_pin_visuals(bool(pinned) and enabled)

    def set_sockets(self, labels: list[str], index: int = 0) -> None:
        """Fill the socket chip; it shows only for a node with several outputs."""
        self.socket_combo.blockSignals(True)
        self.socket_combo.clear()
        if labels:
            self.socket_combo.addItems(labels)
            self.socket_combo.setCurrentIndex(index if 0 <= index < len(labels) else 0)
        self.socket_combo.blockSignals(False)
        self.socket_chip.setVisible(len(labels) > 1)

    # -- controller results -------------------------------------------------

    def _on_preview_ready(self, window: PreviewWindow) -> None:
        self._window = window
        self._count_pending = bool(window.limited and window.is_lazy)
        if window.frame.height == 0:
            self._show_state("No rows")
            self._update_status()
            return
        self.viewer.set_dataframe(window.frame)
        self._refresh_scope_items()
        self._set_search_enabled(True)
        self._apply_search()
        self._show_content()
        self._update_status()

    def _on_count_ready(self, count: int) -> None:
        self._count_pending = False
        if self._window is None:
            return
        if count >= 0:
            self._window.total_rows = count
        self._update_status()

    def _on_failed(self, message: str) -> None:
        self._forget_data()
        self._show_state(f"Preview failed: {message}")

    def _on_busy_changed(self, _busy: bool) -> None:
        self._sync_refresh_enabled()

    def _sync_refresh_enabled(self) -> None:
        self.refresh_btn.setEnabled(
            self._payload is not None and not self.controller.busy
        )

    # -- strip: node, socket, normally host-driven --------------------------

    def _build_strip(self) -> QWidget:
        strip = QFrame(self)
        strip.setObjectName("PreviewStrip")
        strip.setFixedHeight(_STRIP_HEIGHT)
        strip.setAttribute(Qt.WA_StyledBackground, True)
        layout = QHBoxLayout(strip)
        layout.setSpacing(4)
        layout.setContentsMargins(6, 3, 6, 3)

        layout.addWidget(self._build_node_chip(strip))
        layout.addWidget(self._build_socket_chip(strip))

        self.search_edit = QLineEdit(strip)
        self.search_edit.setObjectName("PreviewSearchEdit")
        self.search_edit.setPlaceholderText("Search this preview...")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.setMinimumHeight(26)
        self.search_edit.setMinimumWidth(110)
        self.search_edit.setMaximumWidth(200)
        self.search_edit.setToolTip("Filter rows as you type (Ctrl+F)")
        self.search_edit.setAccessibleName("Search preview")
        search_icon = self.rsm.get("icon_search")
        if search_icon is not None:
            self.search_edit.addAction(
                QIcon(search_icon),
                QLineEdit.ActionPosition.LeadingPosition,
            )
        self.search_edit.textChanged.connect(self._on_search_text_changed)
        layout.addWidget(self.search_edit, 1)

        self.scope_combo = NoWheelComboBox(strip)
        self.scope_combo.setObjectName("PreviewScopeCombo")
        self.scope_combo.setFixedHeight(_CHIP_HEIGHT)
        self.scope_combo.setToolTip("Search scope")
        self.scope_combo.setAccessibleName("Search scope")
        self.scope_combo.addItem(ALL_COLUMNS_LABEL)
        self.scope_combo.currentIndexChanged.connect(self._on_scope_changed)
        layout.addWidget(self.scope_combo)

        layout.addStretch(1)
        layout.addWidget(self._build_counts_chip(strip))

        self.pin_btn = IconButton.themed(
            "Pin this node",
            rsm_icon=self.rsm.get("icon_pin"),
            parent=strip,
        )
        self.pin_btn.setObjectName("PreviewPinButton")
        self.pin_btn.setCheckable(True)
        self.pin_btn.setEnabled(False)
        self.pin_btn.toggled.connect(self._on_pin_toggled)
        layout.addWidget(self.pin_btn)

        self.refresh_btn = IconButton.themed(
            "Refresh preview",
            rsm_icon=self.rsm.get("icon_refresh"),
            parent=strip,
        )
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.clicked.connect(self.refresh)
        layout.addWidget(self.refresh_btn)

        self.options_btn = IconButton.themed(
            "Preview options",
            rsm_icon=self.rsm.get("icon_options"),
            parent=strip,
        )
        self.options_btn.setObjectName("OptionsButton")
        self._build_options_menu()
        layout.addWidget(self.options_btn)

        self._set_search_enabled(False)
        return strip

    def _build_node_chip(self, parent: QWidget) -> QFrame:
        self.node_chip = QFrame(parent)
        self.node_chip.setObjectName("PreviewNodeChip")
        self.node_chip.setFixedHeight(_CHIP_HEIGHT)
        self.node_chip.setAttribute(Qt.WA_StyledBackground, True)
        layout = QHBoxLayout(self.node_chip)
        layout.setSpacing(5)
        layout.setContentsMargins(7, 0, 7, 0)

        self._pin_dot = QLabel(self.node_chip)
        self._pin_dot.setObjectName("PreviewPinDot")
        self._pin_dot.setFixedSize(6, 6)
        self._pin_dot.setVisible(False)
        layout.addWidget(self._pin_dot)

        self.node_label = QLabel("", self.node_chip)
        self.node_label.setObjectName("PreviewNodeLabel")
        layout.addWidget(self.node_label)

        self.node_chip.setVisible(False)
        return self.node_chip

    def _build_socket_chip(self, parent: QWidget) -> QFrame:
        self.socket_chip = QFrame(parent)
        self.socket_chip.setObjectName("PreviewSocketChip")
        self.socket_chip.setFixedHeight(_CHIP_HEIGHT)
        self.socket_chip.setAttribute(Qt.WA_StyledBackground, True)
        layout = QHBoxLayout(self.socket_chip)
        layout.setSpacing(0)
        layout.setContentsMargins(2, 0, 2, 0)

        self.socket_combo = NoWheelComboBox(self.socket_chip)
        self.socket_combo.setObjectName("PreviewSocketCombo")
        self.socket_combo.setMinimumHeight(22)
        self.socket_combo.setToolTip("Output socket")
        self.socket_combo.setAccessibleName("Output socket")
        self.socket_combo.currentIndexChanged.connect(self.socketChanged.emit)
        layout.addWidget(self.socket_combo)

        self.socket_chip.setVisible(False)
        return self.socket_chip

    def _build_counts_chip(self, parent: QWidget) -> QFrame:
        self.counts_chip = QFrame(parent)
        self.counts_chip.setObjectName("PreviewCountsChip")
        self.counts_chip.setFixedHeight(_CHIP_HEIGHT)
        self.counts_chip.setAttribute(Qt.WA_StyledBackground, True)
        layout = QHBoxLayout(self.counts_chip)
        layout.setSpacing(5)
        layout.setContentsMargins(7, 0, 7, 0)

        self.status_label = QLabel("", self.counts_chip)
        self.status_label.setObjectName("PreviewStatusLabel")
        layout.addWidget(self.status_label)

        self.limited_badge = QLabel("limited", self.counts_chip)
        self.limited_badge.setObjectName("PreviewLimitedBadge")
        self.limited_badge.setToolTip(
            "Collection stopped at the preview size limit; export still "
            "writes the collected rows."
        )
        self.limited_badge.setVisible(False)
        layout.addWidget(self.limited_badge)

        self.counts_chip.setVisible(False)
        return self.counts_chip

    def _build_options_menu(self) -> None:
        """Panel-owned menu; a dock host appends its own window actions."""
        menu = QMenu(self)
        self.copy_action = menu.addAction("Copy as TSV")
        self.export_csv_action = menu.addAction("Export CSV...")
        self.export_excel_action = menu.addAction("Export Excel...")
        self.copy_action.triggered.connect(self.viewer.copy_all_visible_to_clipboard)
        self.export_csv_action.triggered.connect(self.viewer.export_csv)
        self.export_excel_action.triggered.connect(self.viewer.export_excel)
        menu.aboutToShow.connect(self._sync_options_menu)
        self.options_btn.setMenu(menu)
        self.options_menu = menu

    def _sync_options_menu(self) -> None:
        has_data = self._window is not None
        for action in (
            self.copy_action,
            self.export_csv_action,
            self.export_excel_action,
        ):
            action.setEnabled(has_data)

    def _apply_pin_visuals(self, pinned: bool) -> None:
        icon = self.rsm.get("icon_unpin" if pinned else "icon_pin")
        if icon is not None:
            self.pin_btn.setIcon(QIcon(icon))
        tooltip = "Unpin this node" if pinned else "Pin this node"
        self.pin_btn.setToolTip(tooltip)
        self.pin_btn.setAccessibleName(tooltip)
        self._pin_dot.setVisible(pinned)

    def _on_pin_toggled(self, checked: bool) -> None:
        self._apply_pin_visuals(checked)
        self.pinned.emit(checked)

    # -- strip: live search -------------------------------------------------

    def _on_search_text_changed(self, _text: str) -> None:
        self._search_timer.start()

    def _on_scope_changed(self, _index: int) -> None:
        self._apply_search()

    def _focus_search(self) -> None:
        self.search_edit.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.search_edit.selectAll()

    def _apply_search(self) -> None:
        """Apply the field's text to the loaded frame (the field is the truth)."""
        if self._window is None:
            return
        text = self.search_edit.text().strip()
        if text:
            scope = self.scope_combo.currentText()
            self.viewer.apply_search(
                text, None if scope == ALL_COLUMNS_LABEL else scope
            )
        elif self.viewer.filtered_dataframe is not None:
            self.viewer.clear_search()
        self._update_status()

    def _refresh_scope_items(self) -> None:
        """One scope entry per column, keeping the choice when it survives."""
        current = self.scope_combo.currentText()
        columns = self.viewer.search_columns()
        self.scope_combo.blockSignals(True)
        self.scope_combo.clear()
        self.scope_combo.addItem(ALL_COLUMNS_LABEL)
        self.scope_combo.addItems(columns)
        if current in columns:
            self.scope_combo.setCurrentText(current)
        else:
            self.scope_combo.setCurrentIndex(0)
        self.scope_combo.blockSignals(False)

    def _set_search_enabled(self, enabled: bool) -> None:
        self.search_edit.setEnabled(enabled)
        self.scope_combo.setEnabled(enabled)

    # -- counts / states ----------------------------------------------------

    def _update_status(self) -> None:
        """Row/column counts for the chip: shown of collected, of total."""
        window = self._window
        if window is None:
            self.status_label.setText("")
            self.counts_chip.setVisible(False)
            return

        collected = window.frame.height
        columns = len(window.frame.columns)
        shown = self.viewer.model.total_rows
        total = window.total_rows

        if self._count_pending and total is None:
            text = f"{collected:,} rows · counting..."
        elif shown != collected:
            text = f"{shown:,} / {collected:,} rows · {columns} cols"
        elif total is not None and total > collected:
            text = f"{collected:,} / {total:,} rows · {columns} cols"
        else:
            text = f"{collected:,} rows · {columns} cols"

        tooltip = f"{collected:,} rows collected"
        if total is not None and total > collected:
            tooltip += f" of {total:,} in the source"
        if window.limited:
            tooltip += " (stopped at the size limit)"
        if shown != collected:
            tooltip += f"; {shown:,} match the search"

        self.status_label.setText(text)
        self.status_label.setToolTip(tooltip)
        self.counts_chip.setToolTip(tooltip)
        self.counts_chip.setVisible(True)
        self.limited_badge.setVisible(bool(window.limited))

    def _forget_data(self) -> None:
        """Back to "no preview": drop the filter, the scope and the counts."""
        self._window = None
        self._count_pending = False
        self._search_timer.stop()
        self.search_edit.blockSignals(True)
        self.search_edit.clear()
        self.search_edit.blockSignals(False)
        self.scope_combo.blockSignals(True)
        self.scope_combo.clear()
        self.scope_combo.addItem(ALL_COLUMNS_LABEL)
        self.scope_combo.blockSignals(False)
        self._set_search_enabled(False)
        self._sync_refresh_enabled()
        self._update_status()

    def _show_state(self, text: str) -> None:
        self._state_label.setText(text)
        self._state_label.setVisible(True)
        self._content.setVisible(False)

    def _show_content(self) -> None:
        self._state_label.setVisible(False)
        self._content.setVisible(True)
