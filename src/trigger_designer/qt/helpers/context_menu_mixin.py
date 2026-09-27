from __future__ import annotations

import time
from typing import Any, Dict, Optional

from loguru import logger
from qtpy.QtCore import Qt
from qtpy.QtGui import QContextMenuEvent, QCursor
from qtpy.QtWidgets import QAction, QGraphicsProxyWidget, QInputDialog, QMenu

from nodeeditor.node_edge import (
    EDGE_TYPE_BEZIER,
    EDGE_TYPE_DIRECT,
    EDGE_TYPE_SQUARE,
)
from nodeeditor.node_group import Group
from nodeeditor.utils import dumpException

from trigger_designer.core.node_configuration import (
    NODE_REGISTRIES,
    NodeTypes,
    get_class_from_opcode,
)
from trigger_designer.qt.widgets.node_searchable_menu import SearchableMenu


class ContextMenuMixin:
    """Mixin encapsulating node context menu creation and handling."""

    def init_context_menu_support(self) -> None:
        """Initialise context menu bookkeeping structures."""
        self.selected_action_data: Optional[list] = None
        self.node_actions: Dict[str, Any] = {}
        self.nodes_by_type = {
            "Input/Output": NODE_REGISTRIES[NodeTypes.IO],
            "Preparation": NODE_REGISTRIES[NodeTypes.PREPARATION],
            "Join": NODE_REGISTRIES[NodeTypes.JOIN],
            "Transform": NODE_REGISTRIES[NodeTypes.TRANSFORM],
            "Report": NODE_REGISTRIES[NodeTypes.REPORT],
        }

    # --- Node actions --------------------------------------------------------------
    def initNewNodeActions(self) -> None:  # noqa: N802 (Qt naming style)
        for category, nodes in self.nodes_by_type.items():
            for node_code, node_class in nodes.items():
                action_key = f"{category}_{node_code}"
                action = QAction(
                    self._get_action_icon(category, node_class.icon),
                    node_class.node_title,
                )
                node_type = next(
                    type_name
                    for type_name, registry in NODE_REGISTRIES.items()
                    if node_class in registry.values()
                )
                action.setData([node_code, node_type])
                self.node_actions[action_key] = action

    def _get_action_icon(self, category: str, icon_id: str):
        from qtpy.QtGui import QIcon, QPixmap  # Local import to avoid circular deps

        icon = QIcon(f":{category}/{self.rsm.get_icon_path(icon_id)}")
        if icon.isNull():
            # ponytail: filesystem fallback — icons.qrc may miss an entry
            # (recompile icons_rc.py when adding icons permanently)
            pixmap = self.rsm.get(icon_id)
            if isinstance(pixmap, QPixmap) and not pixmap.isNull():
                icon = QIcon(pixmap)
            else:
                logger.warning("Missing icon '{}' for category '{}'", icon_id, category)
        return icon

    # --- Context menu factories ----------------------------------------------------
    def initNodesContextMenu(self):
        context_menu = SearchableMenu(self)

        for category, nodes in self.nodes_by_type.items():
            if not nodes:
                continue

            submenu = QMenu(category, context_menu)
            context_menu.addMenu(submenu)
            context_menu.all_submenus[category] = submenu
            context_menu.all_actions[category] = []

            node_list = sorted(nodes.values(), key=lambda node: node.node_title)
            for node in node_list:
                action = self.node_actions[f"{category}_{node.node_code}"]
                submenu.addAction(action)
                context_menu.all_actions[category].append(action)

        return context_menu

    # --- Node creation helpers -----------------------------------------------------
    def set_selected_action_data(self, data) -> None:
        self.selected_action_data = data

    def add_node_to_scene(self) -> None:
        if not self.selected_action_data:
            return

        # Belt-and-braces against double Enter handling: an identical request
        # within half a second of the previous one is the same keypress.
        now = time.monotonic()
        last_ts = getattr(self, "_last_add_node_ts", 0.0)
        if (
            list(self.selected_action_data)
            == getattr(self, "_last_add_node_data", None)
            and now - last_ts < 0.5
        ):
            return
        self._last_add_node_ts = now
        self._last_add_node_data = list(self.selected_action_data)

        node_code, node_type = self.selected_action_data
        new_calc_node = get_class_from_opcode(node_code, node_type)(self.scene)
        cursor_pos = self.mapFromGlobal(QCursor.pos())
        scene_pos = self.scene.getView().mapToScene(cursor_pos)
        new_calc_node.setPos(scene_pos.x(), scene_pos.y())
        self.scene.history.storeHistory("Created %s" % new_calc_node.__class__.__name__)

    # --- Context menu handlers -----------------------------------------------------
    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        try:
            item = self.scene.getItemAt(event.pos())
            debug_context = getattr(self, "DEBUG_CONTEXT", False)

            if debug_context:
                print(item)

            if isinstance(item, QGraphicsProxyWidget):
                item = item.widget()

            if isinstance(item, Group):
                # Upstream Group paints its own header menu
                # (collapse/rename/recolor/ungroup/delete) - let it through.
                super().contextMenuEvent(event)
                return
            elif hasattr(item, "node") or hasattr(item, "socket"):
                self.handleNodeContextMenu(event)
            elif hasattr(item, "edge"):
                self.handleEdgeContextMenu(event)
            else:
                self.handleNewNodeContextMenu(event)

            super().contextMenuEvent(event)
        except Exception as exc:
            dumpException(exc)

    # --- Node candidates ---------------------------------------------------------
    def resolve_node_candidates(self, item) -> tuple:
        """Right-clicked node merged into the current selection, deduped.

        Returns ``(clicked, candidates)`` where ``clicked`` is the node under
        the cursor (or ``None``) and ``candidates`` is the selection plus the
        clicked node. Factored out so grouping/label logic is testable
        without opening a menu.
        """
        selected = [
            graph_item.node
            for graph_item in self.scene.getSelectedItems()
            if hasattr(graph_item, "node")
        ]
        clicked = None
        if hasattr(item, "node"):
            clicked = item.node
        elif hasattr(item, "socket"):
            clicked = item.socket.node
        candidates = list(selected)
        if clicked is not None and clicked not in candidates:
            candidates.append(clicked)
        return clicked, candidates

    # --- Node labels -------------------------------------------------------------
    def set_nodes_label(self, nodes, text: str) -> bool:
        """Set the floating label on ``nodes`` as a single undo step."""
        nodes = [node for node in dict.fromkeys(nodes) if node is not None]
        if not nodes:
            return False
        changed = False
        for node in nodes:
            if node.getNodeLabel() != text:
                node.setNodeLabel(text, store_history=False)
                changed = True
        if changed:
            self.scene.history.storeHistory("Node label changed", setModified=True)
        return changed

    def set_nodes_label_visible(self, nodes, visible: bool) -> int:
        """Show/hide floating labels on ``nodes`` as a single undo step.

        Showing is a no-op for nodes with no label text (upstream hides
        empty labels unconditionally). Returns the number of nodes changed.
        """
        nodes = [node for node in dict.fromkeys(nodes) if node is not None]
        changed = 0
        for node in nodes:
            if visible and not node.getNodeLabel():
                continue
            if node.isNodeLabelVisible() != visible:
                node.setNodeLabelVisible(visible)
                changed += 1
        if changed:
            count = "Node" if len(nodes) == 1 else "Nodes"
            shown = "shown" if visible else "hidden"
            self.scene.history.storeHistory(f"{count} label {shown}", setModified=True)
        return changed

    def prompt_node_label(self, nodes) -> bool:
        """Ask for label text once, apply to ``nodes``. ``False`` = cancelled."""
        nodes = [node for node in dict.fromkeys(nodes) if node is not None]
        if not nodes:
            return False
        initial = nodes[0].getNodeLabel() if len(nodes) == 1 else ""
        text, accepted = QInputDialog.getText(
            self,
            "Set Node Label",
            "Label text (empty removes it):",
            text=initial,
        )
        if not accepted:
            return False
        return self.set_nodes_label(nodes, text)

    def handleNodeContextMenu(self, event: QContextMenuEvent) -> None:
        debug_context = getattr(self, "DEBUG_CONTEXT", False)
        if debug_context:
            print("CONTEXT: NODE")
        context_menu = QMenu(self)
        markDirtyAct = context_menu.addAction("Mark Dirty")
        markDirtyDescendantsAct = context_menu.addAction("Mark Descendant Dirty")
        markInvalidAct = context_menu.addAction("Mark Invalid")
        unmarkInvalidAct = context_menu.addAction("Unmark Invalid")
        evalAct = context_menu.addAction("Eval")
        context_menu.addSeparator()

        item = self.scene.getItemAt(event.pos())
        if isinstance(item, QGraphicsProxyWidget):
            item = item.widget()

        clicked_node, candidates = self.resolve_node_candidates(item)

        setLabelAct = context_menu.addAction("Set Label...")
        if len(candidates) > 1:
            showLabelsAct = context_menu.addAction("Show Labels")
            hideLabelsAct = context_menu.addAction("Hide Labels")
            showLabelAct = None
        else:
            showLabelAct = context_menu.addAction("Show Label")
            showLabelAct.setCheckable(True)
            if candidates:
                showLabelAct.setChecked(
                    bool(candidates[0].getNodeLabel())
                    and candidates[0].isNodeLabelVisible()
                )
            showLabelsAct = hideLabelsAct = None

        detachAct = None
        if clicked_node is not None and clicked_node.parent_group is not None:
            detachAct = context_menu.addAction("Detach from Group")

        groupAct = None
        if len(candidates) > 1:
            groupAct = context_menu.addAction("Group Selected Nodes")

        action = context_menu.exec(self.mapToGlobal(event.pos()))

        if debug_context:
            print("got item:", clicked_node)

        if clicked_node and action == markDirtyAct:
            clicked_node.markDirty()
        if clicked_node and action == markDirtyDescendantsAct:
            clicked_node.markDescendantsDirty()
        if clicked_node and action == markInvalidAct:
            clicked_node.markInvalid()
        if clicked_node and action == unmarkInvalidAct:
            clicked_node.markInvalid(False)
        if clicked_node and action == evalAct:
            value = clicked_node.eval()
            if debug_context:
                print("EVALUATED:", value)

        if candidates and action == setLabelAct:
            self.prompt_node_label(candidates)
        if showLabelAct is not None and action == showLabelAct:
            self.set_nodes_label_visible(candidates, showLabelAct.isChecked())
        if showLabelsAct is not None and action == showLabelsAct:
            self.set_nodes_label_visible(candidates, True)
        if hideLabelsAct is not None and action == hideLabelsAct:
            self.set_nodes_label_visible(candidates, False)
        if detachAct is not None and action == detachAct:
            clicked_node.parent_group.removeNode(clicked_node)
            self.scene.history.storeHistory(
                "Detached node from group", setModified=True
            )
        if candidates and groupAct and action == groupAct:
            self.createGroup(candidates)

    def handleEdgeContextMenu(self, event: QContextMenuEvent) -> None:
        debug_context = getattr(self, "DEBUG_CONTEXT", False)
        if debug_context:
            print("CONTEXT: EDGE")
        context_menu = QMenu(self)
        bezierAct = context_menu.addAction("Bezier Edge")
        directAct = context_menu.addAction("Direct Edge")
        squareAct = context_menu.addAction("Square Edge")
        action = context_menu.exec_(self.mapToGlobal(event.pos()))

        item = self.scene.getItemAt(event.pos())
        selected_edge = getattr(item, "edge", None)

        if selected_edge and action == bezierAct:
            selected_edge.edge_type = EDGE_TYPE_BEZIER
        if selected_edge and action == directAct:
            selected_edge.edge_type = EDGE_TYPE_DIRECT
        if selected_edge and action == squareAct:
            selected_edge.edge_type = EDGE_TYPE_SQUARE

    def handleNewNodeContextMenu(self, event: QContextMenuEvent) -> None:
        debug_context = getattr(self, "DEBUG_CONTEXT", False)
        if debug_context:
            print("CONTEXT: EMPTY SPACE")
        self.showNodeContextMenu(event.pos())

    def showNodeContextMenu(self, position) -> None:  # noqa: N802
        debug_context = getattr(self, "DEBUG_CONTEXT", False)
        if debug_context:
            print("CONTEXT: EMPTY SPACE")
        context_menu = self.initNodesContextMenu()
        action = context_menu.exec_(self.mapToGlobal(position))

        if action is not None and action.data():
            try:
                print("Action was triggered!")
                self.selected_action_data = action.data()
                self.add_node_to_scene()
            except Exception as exc:
                dumpException(exc)

    # --- Helpers -------------------------------------------------------------------
    def determine_target_socket_of_node(self, was_dragged_flag, new_calc_node):
        target_socket = None
        if was_dragged_flag:
            if len(new_calc_node.inputs) > 0:
                target_socket = new_calc_node.inputs[0]
        else:
            if len(new_calc_node.outputs) > 0:
                target_socket = new_calc_node.outputs[0]
        return target_socket

    def finish_new_node_state(self, new_calc_node: Any) -> None:
        self.scene.doDeselectItems()
        new_calc_node.grNode.doSelect(True)
        new_calc_node.grNode.onSelected()

    def createGroup(self, nodes=None):
        """Group ``nodes`` in an upstream visual ``Group``.

        Needs 2+ nodes; returns the ``Group`` or ``None``. Drag-and-drop
        into groups, collapse/expand, serialization and history are handled
        by the ``nodeeditor`` package itself.
        """
        if nodes is None:
            nodes = [
                item.node
                for item in self.scene.selectedItems()
                if hasattr(item, "node")
            ]
        nodes = [node for node in dict.fromkeys(nodes) if node is not None]

        if len(nodes) < 2:
            return None

        group = Group(self.scene, title=f"Group ({len(nodes)} nodes)")
        for node in nodes:
            group.addNode(node)
        group.updateBounds()

        self.scene.history.storeHistory(
            f"Created group with {len(nodes)} nodes", setModified=True
        )
        return group
