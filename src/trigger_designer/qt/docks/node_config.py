import traceback
from typing import Any, List, Optional, TYPE_CHECKING

from loguru import logger
from qtpy.QtWidgets import (
    QDockWidget,
    QFrame,
    QHBoxLayout,
    QLayout,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from trigger_designer.qt.undo.binding import bind
from trigger_designer.qt.widgets.common.config_widgets import FormRow

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
        #: Content whose ``dock_context()`` fills the current context strip.
        #: Used to detach the live-refresh callback when the dock moves on.
        self._context_owner = None
        self.initUI()

    def currentNode(self) -> Optional[Any]:
        """The node this dock is currently showing, or ``None``."""
        return self._current_node

    def initUI(self) -> None:
        self.dock_widget = QWidget()
        self.dock_widget.setObjectName("ConfigDockWidget")
        self.dock_widget.setMinimumWidth(300)

        outer = QVBoxLayout(self.dock_widget)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # One scrollbar for the whole pane. A node with more sections than
        # the pane is tall scrolls here instead of squeezing its column
        # lists to a few rows (or nesting a second scroll area of its own).
        self.scroll_area = QScrollArea(self.dock_widget)
        self.scroll_area.setObjectName("ConfigDockScroll")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        self.content_widget = QWidget()
        self.content_widget.setObjectName("ConfigDockContent")
        self.dock_layout = QVBoxLayout(self.content_widget)
        self.dock_layout.setContentsMargins(5, 5, 5, 5)
        self.dock_layout.setSpacing(2)
        self.scroll_area.setWidget(self.content_widget)
        outer.addWidget(self.scroll_area)

        self.setWidget(self.dock_widget)
        self.setFloating(False)
        self.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable)

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
        self._detach_context_refresh()
        self._commit_previous_if_leaving(nodes)
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
            # No identity header and no chips row: the pane title names the
            # node, the canvas shows what it is, and the configuration
            # summary is one hover away in the tooltip. Both rows cost 66px
            # above the first table, which is the space this dock needs most.
            self._context_owner = content
            content._dock_context_refresh = lambda: self._set_context_tooltip(
                node, content
            )
            self._set_context_tooltip(node, content)
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
                # Node actions (add formula, open graph window, transpose
                # policy) share the label row instead of each owning a 30px
                # command row of its own.
                self._mount_dock_actions(content)
                # Sweep for controls the node did not register itself, so every
                # dock control is undoable by default. Done inside the
                # suspension window so building the panel records nothing.
                register_unbound = getattr(content, "registerUnboundDockWidgets", None)
                if callable(register_unbound):
                    register_unbound(self.dock_layout)
                content._suspend_input_tracking = previous_input_tracking
                content._suspend_node_evaluation = previous_node_evaluation

        except Exception as e:
            traceback.print_exc()
            logger.trace(e)

    def _commit_previous_if_leaving(self, nodes: List["TriggerNode"]) -> None:
        """Commit deferred dock edits when leaving the current node.

        Nodes with staged (non-live) edits expose
        ``commit_pending_dock_edits`` (Aggregate). It runs before the dock
        widgets are destroyed so the model is already current and only the
        heavy recompute + evaluate happens here.
        """
        current = self._current_node
        if current is None:
            return
        try:
            leaving = len(nodes) != 1 or nodes[0] is not current
        except Exception:
            leaving = True
        if not leaving:
            return
        try:
            content = getattr(current, "content", None)
        except Exception:
            return
        commit = getattr(content, "commit_pending_dock_edits", None)
        if callable(commit):
            try:
                commit()
            except Exception as e:
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

    def _detach_context_refresh(self) -> None:
        """Stop the previous node refreshing a strip that no longer exists."""
        owner = self._context_owner
        self._context_owner = None
        if owner is None:
            return
        try:
            owner.__dict__.pop("_dock_context_refresh", None)
        except AttributeError:
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

        edit = QLineEdit()
        edit.setObjectName("NodeLabelEdit")
        edit.setPlaceholderText("Node label...")
        edit.setMinimumHeight(30)
        edit.setClearButtonEnabled(True)
        edit.setText(current)
        # One 30px row ("Label: ____ [actions]"), not a captioned section:
        # the caption and the field on separate lines cost 42px for a rarely
        # used input, and the trailing slot lets a node put its one obvious
        # action there instead of spending another 30px row on it.
        self._label_actions_layout = QHBoxLayout()
        self._label_actions_layout.setContentsMargins(0, 0, 0, 0)
        self._label_actions_layout.setSpacing(0)
        self._label_actions_layout.addStretch(0)
        actions_widget = QWidget()
        actions_widget.setLayout(self._label_actions_layout)
        row = FormRow("Label", edit, label_width=40, action=actions_widget)
        self.dock_layout.insertWidget(0, row)

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

    def _mount_dock_actions(self, content: Any) -> None:
        """Move a node's own trailing action into the label row.

        A node that has exactly one obvious action (add a formula section,
        open the graph in a window, pick the transpose missing-column policy)
        exposes it through ``dock_actions()``. It then rides on the label row
        instead of claiming a 30px row of its own, which on a short pane is
        the row the first table needed.
        """
        provider = getattr(content, "dock_actions", None)
        slot = getattr(self, "_label_actions_layout", None)
        if not callable(provider) or slot is None:
            return
        try:
            actions = list(provider() or [])
        except Exception as e:
            logger.trace(e)
            return
        for widget in actions:
            if widget is None:
                continue
            try:
                # A live action is created parentless for this rebuild; one
                # that still has a parent belongs to the dock generation that
                # was just cleared and would be deleted under us.
                if widget.parent() is not None:
                    continue
            except RuntimeError:
                # Already deleted by the previous rebuild.
                continue
            # Drop the stretch the slot starts with: the actions sit right
            # after the label field, not pinned to the far edge.
            try:
                slot.insertWidget(slot.count() - 1, widget)
            except RuntimeError:
                continue

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

    @staticmethod
    def _context_summary(content: Any) -> str:
        """One-line configuration summary from the node's ``dock_context()``.

        The hook returns ``(chips, label)`` - chips are ``(text, tone)``
        pairs - or a dict with the same keys. Configuration and schema only:
        no evaluated results. This used to be a 26px chip strip above every
        table; it now reads in the pane's tooltip, where it costs nothing.
        """
        provider = getattr(content, "dock_context", None)
        if not callable(provider):
            return ""
        try:
            data = provider()
        except Exception as e:
            logger.trace(e)
            return ""
        chips: Any = ()
        label = ""
        if isinstance(data, dict):
            chips = data.get("chips", ())
            label = data.get("label", "")
        elif isinstance(data, (tuple, list)) and len(data) == 2:
            chips, label = data
        elif data:
            chips = data
        parts: list[str] = []
        try:
            for chip in chips or ():
                text = chip[0] if isinstance(chip, (tuple, list)) else chip
                if text:
                    parts.append(str(text))
        except (TypeError, ValueError) as e:
            logger.trace(e)
        if label:
            parts.append(str(label))
        return " · ".join(parts)

    def _set_context_tooltip(self, node: Any, content: Any) -> None:
        """Put the node's configuration summary on the pane's tooltip."""
        name = self._node_name(node)
        summary = self._context_summary(content)
        self.setToolTip(f"{name} — {summary}" if summary else name)

    def clear_dock(self) -> None:
        # The label row (and the layout that holds its trailing actions) dies
        # with the rest; drop the stale reference so a rebuild cannot mount a
        # node action on a deleted widget.
        self._label_actions_layout = None
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
