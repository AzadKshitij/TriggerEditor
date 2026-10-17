"""Data Preview dock: a live preview of the selected node's output.

The dock follows the active design window. Selecting a node (or editing one in
the Config Dock) points the embedded `DataPreviewPanel` at that node's output
socket; a pin freezes the current node so selection changes stop moving the
preview, and the options menu exports the loaded frame or opens it in a
standalone window.

Per-window state mirrors the LoggingDock: keyed by ``str(id(design_window))``,
dropped by ``remove_design_window`` when the window closes. Each entry holds
``pinned``, ``pin_node``, ``socket_index`` and ``shown_node`` - the last one is
what lets an evaluation refresh the preview only for the node on screen.

Payload resolution, in order: the node's ``value`` (one ``{"data",
"variable_name"}`` entry per output socket), then the run results through
``getSocketData`` (a run writes to ``execution_results``, not ``value``). A
value the preview cannot render counts as "no output", so the panel shows the
empty state instead of a collect failure.
"""

import weakref
from typing import Any

from qtpy.QtCore import QTimer
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import (
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QMenu,
    QVBoxLayout,
    QWidget,
)

from trigger_designer.qt.models.preview_sampling import is_previewable
from trigger_designer.qt.resource_manager import ResourceManager
from trigger_designer.qt.widgets.common import IconButton, NoWheelComboBox
from trigger_designer.qt.widgets.data_preview_panel import DataPreviewPanel
from trigger_designer.qt.widgets.data_preview_window import DataPreviewWindow

_TITLE = "Data Preview"
_COALESCE_MS = 300
_NO_DATA = "No previewable data on this socket"
_PIN_LOST = "Pinned node is no longer in the scene"


class DataPreviewDock(QDockWidget):
    """A persistent Data Preview for the active design window's selection."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(_TITLE, parent)
        self.setObjectName("DataPreviewDock")
        self.rsm = ResourceManager()

        self.current_design_window_id: str | None = None
        self._states: dict[str, dict[str, Any]] = {}
        self._window_ref: weakref.ReferenceType[Any] | None = None
        self._payload: Any = None
        self._pending_eval: tuple[str, Any] | None = None

        self._coalesce = QTimer(self)
        self._coalesce.setSingleShot(True)
        self._coalesce.setInterval(_COALESCE_MS)
        self._coalesce.timeout.connect(self._on_eval_settled)

        self._build_ui()

    def _build_ui(self) -> None:
        """Header (toolbar tokens) over the preview panel."""
        body = QWidget(self)
        layout = QVBoxLayout(body)
        layout.setSpacing(2)
        layout.setContentsMargins(5, 5, 5, 5)

        # The panel comes first: the options menu binds to its viewer.
        self.panel = DataPreviewPanel(body)
        self.panel.titleChanged.connect(self._on_title_changed)
        self.panel.controller.busyChanged.connect(self._on_busy_changed)

        header = QWidget(body)
        header.setFixedHeight(40)
        header_layout = QHBoxLayout(header)
        header_layout.setSpacing(2)
        header_layout.setContentsMargins(0, 0, 0, 0)

        self.title_label = QLabel(_TITLE, header)
        self.title_label.setObjectName("PreviewTitleLabel")
        header_layout.addWidget(self.title_label, 1)

        self.socket_combo = NoWheelComboBox(header)
        self.socket_combo.setObjectName("PreviewSocketCombo")
        self.socket_combo.setMinimumHeight(30)
        self.socket_combo.setToolTip("Output socket")
        self.socket_combo.setAccessibleName("Output socket")
        self.socket_combo.setVisible(False)
        self.socket_combo.currentIndexChanged.connect(self._on_socket_changed)
        header_layout.addWidget(self.socket_combo)

        self.pin_btn = self._header_button("icon_pin", "Pin this node", header)
        self.pin_btn.setObjectName("PreviewPinButton")
        self.pin_btn.setCheckable(True)
        self.pin_btn.setEnabled(False)
        self.pin_btn.toggled.connect(self._on_pin_toggled)
        header_layout.addWidget(self.pin_btn)

        self.refresh_btn = self._header_button(
            "icon_refresh", "Refresh preview", header
        )
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.clicked.connect(self.panel.refresh)
        header_layout.addWidget(self.refresh_btn)

        self.options_btn = self._header_button(
            "icon_options", "Preview options", header
        )
        self.options_btn.setObjectName("OptionsButton")
        self._build_options_menu()
        header_layout.addWidget(self.options_btn)

        layout.addWidget(header)
        layout.addWidget(self.panel, 1)

        self.setWidget(body)

    def _header_button(self, icon_id: str, tooltip: str, parent: QWidget) -> IconButton:
        return IconButton.themed(
            tooltip,
            rsm_icon=self.rsm.get(icon_id),
            parent=parent,
        )

    def _build_options_menu(self) -> None:
        self.options_menu = QMenu(self)
        self.export_csv_action = self.options_menu.addAction("Export CSV...")
        self.export_excel_action = self.options_menu.addAction("Export Excel...")
        self.options_menu.addSeparator()
        self.open_window_action = self.options_menu.addAction(
            "Open in standalone window"
        )
        self.options_menu.addSeparator()
        self.unpin_action = self.options_menu.addAction("Unpin")

        self.export_csv_action.triggered.connect(self.panel.viewer.export_csv)
        self.export_excel_action.triggered.connect(self.panel.viewer.export_excel)
        self.open_window_action.triggered.connect(self._open_standalone_window)
        self.unpin_action.triggered.connect(self._unpin)
        self.options_menu.aboutToShow.connect(self._sync_menu)
        self.options_btn.setMenu(self.options_menu)

    # -- per-window surface -------------------------------------------------

    def switch_to_design_window(self, design_window: Any) -> None:
        """Follow ``design_window``: re-read its pin and re-request its node."""
        window_id = str(id(design_window))
        self.current_design_window_id = window_id
        self._window_ref = self._weak_ref(design_window)
        self._states.setdefault(window_id, self._new_state())
        self._drop_pending_eval()
        self.setWindowTitle(self._banner_title(design_window))

        state = self._states[window_id]
        if state["pinned"]:
            if self._pin_holds(design_window, state):
                self._show_node(design_window, state["pin_node"])
            return
        self._show_node(design_window, self._resolve_node(design_window))

    def remove_design_window(self, design_window_id: str) -> None:
        """Forget a closed window's preview state (mirrors the LoggingDock)."""
        self._states.pop(design_window_id, None)
        if self.current_design_window_id != design_window_id:
            return
        self.current_design_window_id = None
        self._window_ref = None
        self._drop_pending_eval()
        self.setWindowTitle(_TITLE)
        self._payload = None
        self.panel.set_source(None, title="")
        self._sync_header(self._new_state(), None)

    # -- design-window hooks (wired by the main window) ---------------------

    def note_selection_changed(self, design_window: Any) -> None:
        """Follow a selection change in ``design_window``; a pin wins."""
        if not self._is_current(design_window):
            return
        state = self._current_state()
        if state is None:
            return
        if state["pinned"]:
            self._pin_holds(design_window, state)
            return
        self._show_node(design_window, self._resolve_node(design_window))

    def note_node_evaluated(self, design_window: Any, node: Any) -> None:
        """Coalesce a burst of node evaluations into one re-request."""
        if not self._is_current(design_window):
            return
        state = self._current_state()
        if state is None or not self._node_is_shown(design_window, state, node):
            return
        self._pending_eval = (str(id(design_window)), node)
        self._coalesce.start()

    def note_run_finished(self, design_window: Any) -> None:
        """Re-resolve right away: run results live outside ``node.value``."""
        if not self._is_current(design_window):
            return
        state = self._current_state()
        if state is None:
            return
        if state["pinned"]:
            if self._pin_holds(design_window, state):
                self._show_node(design_window, state["pin_node"])
            return
        node = self._resolve_node(design_window)
        if node is None:
            # Keep showing what the run was started for.
            node = state["shown_node"]
        self._show_node(design_window, node)

    def _on_eval_settled(self) -> None:
        pending = self._pending_eval
        self._pending_eval = None
        if pending is None:
            return
        window_id, node = pending
        if window_id != self.current_design_window_id:
            return
        design_window = self._window()
        state = self._current_state()
        if design_window is None or state is None:
            return
        if not self._node_is_shown(design_window, state, node):
            return
        # Re-request what is on screen: an evaluation of the node being edited
        # in the Config Dock must not move the preview off a pinned node.
        shown = state["shown_node"]
        if shown is not None:
            self._show_node(design_window, shown)

    # -- header -------------------------------------------------------------

    def _on_title_changed(self, title: str) -> None:
        self.title_label.setText(f"{_TITLE} - {title}" if title else _TITLE)

    def _on_socket_changed(self, index: int) -> None:
        state = self._current_state()
        node = state["shown_node"] if state is not None else None
        design_window = self._window()
        if index < 0 or state is None or node is None or design_window is None:
            return
        state["socket_index"] = index
        self._show_node(design_window, node)

    def _on_pin_toggled(self, checked: bool) -> None:
        state = self._current_state()
        design_window = self._window()
        if state is None or design_window is None:
            return
        if checked:
            node = state["shown_node"]
            if node is None:
                self._set_pin_checked(False)
                return
            state["pinned"] = True
            state["pin_node"] = node
            self._sync_header(state, node)
            return
        state["pinned"] = False
        state["pin_node"] = None
        self._show_node(design_window, self._resolve_node(design_window))

    def _unpin(self) -> None:
        self.pin_btn.setChecked(False)

    def _sync_menu(self) -> None:
        has_data = self._payload is not None
        self.export_csv_action.setEnabled(has_data)
        self.export_excel_action.setEnabled(has_data)
        self.open_window_action.setEnabled(has_data)
        state = self._current_state()
        self.unpin_action.setEnabled(bool(state is not None and state["pinned"]))

    def _sync_header(self, state: dict[str, Any], node: Any) -> None:
        labels = self._socket_labels(node)
        self.socket_combo.setVisible(len(labels) > 1)
        if labels:
            self.socket_combo.blockSignals(True)
            self.socket_combo.clear()
            self.socket_combo.addItems(labels)
            self.socket_combo.setCurrentIndex(
                min(self._socket_index(state, node), len(labels) - 1)
            )
            self.socket_combo.blockSignals(False)

        pinned = bool(state["pinned"])
        self._set_pin_checked(pinned)
        self.pin_btn.setEnabled(node is not None)
        icon = self.rsm.get("icon_unpin" if pinned else "icon_pin")
        if icon is not None:
            self.pin_btn.setIcon(QIcon(icon))
        tooltip = "Unpin this node" if pinned else "Pin this node"
        self.pin_btn.setToolTip(tooltip)
        self.pin_btn.setAccessibleName(tooltip)
        self._sync_refresh_enabled()

    def _sync_refresh_enabled(self) -> None:
        self._set_refresh_enabled(self.panel.controller.busy)

    def _on_busy_changed(self, busy: bool) -> None:
        self._set_refresh_enabled(busy)

    def _set_refresh_enabled(self, busy: bool) -> None:
        self.refresh_btn.setEnabled(self._payload is not None and not busy)

    def _set_pin_checked(self, checked: bool) -> None:
        self.pin_btn.blockSignals(True)
        self.pin_btn.setChecked(checked)
        self.pin_btn.blockSignals(False)

    def _open_standalone_window(self) -> None:
        if self._payload is None:
            return
        window = DataPreviewWindow(self._payload, self.title_label.text(), self)
        window.show()

    # -- showing a node -----------------------------------------------------

    def _show_node(self, design_window: Any, node: Any) -> None:
        window_id = str(id(design_window))
        state = self._states.setdefault(window_id, self._new_state())
        if node is None:
            state["shown_node"] = None
            self._payload = None
            self.panel.set_source(None, title="")
            self._sync_header(state, None)
            return

        if state["shown_node"] is not node:
            # The socket choice belongs to the node it was made on.
            state["socket_index"] = 0
        state["shown_node"] = node
        index = self._socket_index(state, node)
        payload = self._payload_for(design_window, node, index)
        self._payload = payload
        title = self._node_title(node)
        if payload is None:
            self.panel.set_source(None, title=title, empty_text=_NO_DATA)
        else:
            self.panel.set_source(payload, title=title)
        self._sync_header(state, node)

    def _payload_for(self, design_window: Any, node: Any, index: int) -> Any:
        """The value on ``node``'s output ``index``, when it can be shown."""
        entry: Any = getattr(node, "value", None)
        if isinstance(entry, (list, tuple)):
            entry = entry[index] if 0 <= index < len(entry) else None
        elif index != 0:
            entry = None
        payload = self._unwrap(entry)
        if payload is not None:
            return payload
        return self._run_payload(design_window, node, index)

    @staticmethod
    def _unwrap(entry: Any) -> Any:
        """The previewable value of an output entry, else ``None``."""
        if isinstance(entry, dict):
            entry = entry.get("data")
        return entry if is_previewable(entry) else None

    @classmethod
    def _run_payload(cls, design_window: Any, node: Any, index: int) -> Any:
        """Fall back to the run results, which live outside ``node.value``."""
        results = getattr(design_window, "execution_results", None)
        getter = getattr(design_window, "getSocketData", None)
        if not results or node not in results or not callable(getter):
            return None
        try:
            return cls._unwrap(getter(node, index))
        except Exception:  # noqa: BLE001 - the run store is best effort
            return None

    def _resolve_node(self, design_window: Any) -> Any:
        """The Config Dock's node when set, else the first selected node."""
        config_dock = self._config_dock(design_window)
        if config_dock is not None:
            node = config_dock.currentNode()
            if node is not None:
                return node
        return self._first_selected_node(design_window)

    @staticmethod
    def _config_dock(design_window: Any) -> Any:
        finder = getattr(design_window, "_find_config_dock", None)
        if not callable(finder):
            return None
        try:
            return finder()
        except RuntimeError:
            return None

    @staticmethod
    def _first_selected_node(design_window: Any) -> Any:
        getter = getattr(design_window, "getSelectedItems", None)
        if not callable(getter):
            return None
        try:
            items = getter()
        except RuntimeError:  # the scene is being torn down
            return None
        for item in items or []:
            if hasattr(item, "socket"):
                continue  # a socket graphic, not a node
            node = getattr(item, "node", item)
            if hasattr(node, "outputs"):
                return node
        return None

    # -- pins ---------------------------------------------------------------

    def _pin_holds(self, design_window: Any, state: dict[str, Any]) -> bool:
        """True while the pinned node is still there; else unpin with a note."""
        node = state["pin_node"]
        scene = getattr(design_window, "scene", None)
        nodes = getattr(scene, "nodes", None)
        # Only a node proven gone drops the pin: when the scene cannot be
        # inspected the pin stays rather than vanishing for no visible reason.
        gone = node is None or (isinstance(nodes, list) and node not in nodes)
        if not gone:
            return True
        state["pinned"] = False
        state["pin_node"] = None
        state["shown_node"] = None
        self._payload = None
        self.panel.set_source(None, title="", empty_text=_PIN_LOST)
        self._sync_header(state, None)
        return False

    # -- small helpers ------------------------------------------------------

    def _window(self) -> Any:
        """The design window the dock follows, or ``None`` once it is gone."""
        ref = self._window_ref
        window = ref() if ref is not None else None
        if window is None:
            return None
        try:
            window.windowTitle()
        except RuntimeError:  # the C++ side is gone; the wrapper lingers
            self._window_ref = None
            return None
        return window

    def _current_state(self) -> dict[str, Any] | None:
        if self.current_design_window_id is None:
            return None
        return self._states.get(self.current_design_window_id)

    def _is_current(self, design_window: Any) -> bool:
        return self.current_design_window_id == str(id(design_window))

    def _node_is_shown(
        self, design_window: Any, state: dict[str, Any], node: Any
    ) -> bool:
        if node is None:
            return False
        if node is state["shown_node"]:
            return True
        config_dock = self._config_dock(design_window)
        return config_dock is not None and node is config_dock.currentNode()

    def _drop_pending_eval(self) -> None:
        self._coalesce.stop()
        self._pending_eval = None

    def _banner_title(self, design_window: Any) -> str:
        title = ""
        getter = getattr(design_window, "windowTitle", None)
        if callable(getter):
            try:
                title = getter() or ""
            except RuntimeError:
                title = ""
        return f"{_TITLE} - {title}" if title else _TITLE

    @staticmethod
    def _new_state() -> dict[str, Any]:
        return {
            "pinned": False,
            "pin_node": None,
            "socket_index": 0,
            "shown_node": None,
        }

    @staticmethod
    def _socket_index(state: dict[str, Any], node: Any) -> int:
        outputs = getattr(node, "outputs", None) or []
        index = int(state["socket_index"])
        return index if 0 <= index < len(outputs) else 0

    @staticmethod
    def _socket_labels(node: Any) -> list[str]:
        """One label per output socket, from the node's own socket text."""
        labels = []
        for index, socket in enumerate(getattr(node, "outputs", None) or []):
            graphics = getattr(socket, "grSocket", None)
            # nodeeditor keeps the label the node passed as output_text here.
            text = str(getattr(graphics, "_text", "") or "").strip()
            labels.append(text or f"out {index + 1}")
        return labels

    @staticmethod
    def _node_title(node: Any) -> str:
        return str(getattr(node, "title", "") or node.__class__.__name__)

    @staticmethod
    def _weak_ref(obj: Any) -> weakref.ReferenceType[Any] | None:
        try:
            return weakref.ref(obj)
        except TypeError:
            return None
