import traceback
from typing import Any, List, Optional, TYPE_CHECKING

from loguru import logger
from qtpy.QtWidgets import QDockWidget, QLayout, QLineEdit, QVBoxLayout, QWidget

from trigger_designer.qt.undo.binding import bind
from trigger_designer.qt.widgets.common.config_widgets import ConfigSection

if TYPE_CHECKING:
    from trigger_designer.qt.node_base import TriggerNode


class ConfigDock(QDockWidget):
    BASE_TITLE = "Node Configuration"

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(self.BASE_TITLE, parent)
        self._current_key = None
        #: The node currently on display. Kept alongside ``_current_key`` so a
        #: caller can re-show it when the scene selection is empty - a history
        #: restore replays the selection recorded in the stamp, which for the
        #: pre-edit stamp is whatever was selected when the file was loaded.
        self._current_node = None
        #: (logic node, slot) for the floating-label sync installed by
        #: :meth:`_add_label_section`. The slot is a plain Python closure
        #: owned by the long-lived node, so Qt cannot auto-disconnect it
        #: when the dock widgets die - it must be disconnected explicitly
        #: on every rebuild, or stale closures touch deleted editors.
        self._label_sync = None
        self.initUI()

    def currentNode(self) -> Optional[Any]:
        """The node this dock is currently showing, or ``None``."""
        return self._current_node

    def initUI(self) -> None:
        self.dock_widget = QWidget()
        self.dock_widget.setObjectName("ConfigDockWidget")
        self.dock_widget.setMinimumWidth(300)
        self.dock_layout = QVBoxLayout()
        self.setWidget(self.dock_widget)
        self.setFloating(False)
        self.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )

    def updateConfig(self, nodes: List["TriggerNode"], force: bool = False) -> None:
        """Show ``nodes`` in the dock.

        :param force: rebuild even when the same node is already shown.

            The early return below normally protects a focused editor from
            being torn down mid-typing. Undo/redo must bypass it: a restore
            reverts the *selected* node in place, so ``_current_key`` still
            matches and the widgets keep displaying values the model no
            longer holds - a renamed field or a changed dtype that appears
            to have ignored the undo.
        """
        self._disconnect_label_sync()
        if len(nodes) != 1:
            self._current_key = None
            self._current_node = None
            self.setWindowTitle(self.BASE_TITLE)
            self.clear_dock()
            return
        node: TriggerNode = nodes[0]
        if not (hasattr(node, "node") or hasattr(node, "socket")):
            self._current_key = None
            self._current_node = None
            self.setWindowTitle(self.BASE_TITLE)
            self.clear_dock()
            return
        try:
            content = node.content
        except Exception as e:
            traceback.print_exc()
            logger.trace(e)
            return
        if content is None:
            self._current_key = None
            self._current_node = None
            self.setWindowTitle(self.BASE_TITLE)
            self.clear_dock()
            return
        if id(content) == self._current_key and not force:
            # Already showing this node: skip the wipe so focused editors
            # keep focus and scroll positions survive. Live widgets refresh
            # themselves through their own non-destructive paths.
            return
        self._current_key = id(content)
        self._current_node = node
        try:
            logger.debug(f"Updating config for node type: {type(node)}")
            self.setWindowTitle(f"{self.BASE_TITLE} ({self._node_name(node)})")
            self.clear_dock()
            logger.debug("Cleared the dock!!!")
            previous_input_tracking = getattr(content, "_suspend_input_tracking", False)
            previous_node_evaluation = getattr(
                content, "_suspend_node_evaluation", False
            )
            content._suspend_input_tracking = True
            content._suspend_node_evaluation = True
            try:
                content.create_layout(self.dock_layout)  # type: ignore
            finally:
                # Floating-label row above the node's own controls, bound
                # before the sweep so it is not generically re-bound.
                self._add_label_section(node, content)
                # Sweep for controls the node did not register itself, so every
                # dock control is undoable by default. Done inside the
                # suspension window so building the panel records nothing.
                register_unbound = getattr(content, "registerUnboundDockWidgets", None)
                if callable(register_unbound):
                    register_unbound(self.dock_layout)
                content._suspend_input_tracking = previous_input_tracking
                content._suspend_node_evaluation = previous_node_evaluation

            self.dock_widget.setLayout(self.dock_layout)
        except Exception as e:
            traceback.print_exc()
            logger.trace(e)

    def _disconnect_label_sync(self) -> None:
        """Drop the floating-label sync installed by the previous rebuild."""
        target, slot = self._label_sync or (None, None)
        self._label_sync = None
        if target is None or slot is None:
            return
        try:
            target.labelChanged.disconnect(slot)
        except (RuntimeError, TypeError):
            pass

    def _add_label_section(self, node: Any, content: Any) -> None:
        """Floating-label row pinned above the node's own controls.

        Canvas click-to-edit works with no code (the label is a child of
        the graphics node); this row is the discoverable equivalent. Typing
        commits through the shared :func:`bind` debounce (~300ms) as one
        ``"Node label changed"`` undo step per burst, and canvas edits
        flow back into the row via ``labelChanged``.
        """
        logic = getattr(node, "node", node)
        get_label = getattr(logic, "getNodeLabel", None)
        set_label = getattr(logic, "setNodeLabel", None)
        if not callable(get_label) or not callable(set_label):
            return
        try:
            current = get_label() or ""
        except Exception:
            return

        section = ConfigSection("Label", info="Floating textbox above the node.")
        edit = QLineEdit(section)
        edit.setObjectName("NodeLabelEdit")
        edit.setPlaceholderText("Node label...")
        edit.setMinimumHeight(30)
        edit.setClearButtonEnabled(True)
        edit.setText(current)
        section.addWidget(edit)
        self.dock_layout.insertWidget(0, section)

        bind(
            content,
            edit,
            read=lambda: logic.getNodeLabel() or "",
            write=lambda value: logic.setNodeLabel(value, store_history=False),
            text="Node label changed",
            merge_key=f"node-label-{id(logic)}",
        )

        def _sync_from_canvas(text: str) -> None:
            try:
                if edit.hasFocus() or edit.text() == text:
                    return
                edit.setText(text)
            except RuntimeError:
                # Editor already deleted (rebuild raced a canvas edit).
                pass

        try:
            logic.labelChanged.connect(_sync_from_canvas)
        except (RuntimeError, TypeError):
            pass
        else:
            # updateConfig disconnects the previous rebuild's slot first,
            # so at most one sync closure is ever attached to the node.
            self._label_sync = (logic, _sync_from_canvas)

    @staticmethod
    def _node_name(node: "TriggerNode") -> str:
        """Best-effort display name for a selected (graphics) node."""
        inner = getattr(node, "node", None)
        for obj in (inner, node):
            for attr in ("title", "node_title"):
                name = getattr(obj, attr, None)
                if isinstance(name, str) and name.strip():
                    return name.strip()
        return type(inner if inner is not None else node).__name__

    def clear_dock(self) -> None:
        while self.dock_layout.count():
            item = self.dock_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                # Recursively clear nested layouts
                self.clear_layout(item.layout())
            # Clear spacer items as well
            self.dock_layout.removeItem(item)
            del item

    def clear_layout(self, layout: QLayout) -> None:
        # Helper method to clear nested layouts
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self.clear_layout(item.layout())
            del item
