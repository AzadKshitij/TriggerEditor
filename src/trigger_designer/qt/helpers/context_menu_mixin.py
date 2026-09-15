from __future__ import annotations

from typing import Any, Dict, Optional

from loguru import logger
from qtpy.QtCore import Qt
from qtpy.QtGui import QContextMenuEvent, QCursor
from qtpy.QtWidgets import QAction, QGraphicsProxyWidget, QMenu

from nodeeditor.utils import dumpException
from nodeeditor.node_edge import (
    EDGE_TYPE_BEZIER,
    EDGE_TYPE_DIRECT,
    EDGE_TYPE_SQUARE,
)

from trigger_designer.core.node_configuration import (
    NODE_REGISTRIES,
    NodeTypes,
    get_class_from_opcode,
)
from trigger_designer.qt.widgets.node_group import NodeGroup
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
                logger.warning(
                    "Missing icon '{}' for category '{}'", icon_id, category
                )
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

            if isinstance(item, NodeGroup):
                self.handleGroupContextMenu(event)
            elif hasattr(item, "node") or hasattr(item, "socket"):
                self.handleNodeContextMenu(event)
            elif hasattr(item, "edge"):
                self.handleEdgeContextMenu(event)
            else:
                self.handleNewNodeContextMenu(event)

            super().contextMenuEvent(event)
        except Exception as exc:
            dumpException(exc)

    def handleGroupContextMenu(self, event: QContextMenuEvent) -> None:
        context_menu = QMenu(self)
        ungroupAct = context_menu.addAction("Ungroup")
        deleteGroupAct = context_menu.addAction("Delete Group")
        context_menu.addSeparator()

        action = context_menu.exec_(self.mapToGlobal(event.pos()))

        item = self.scene.getItemAt(event.pos())
        if isinstance(item, NodeGroup):
            if action == ungroupAct:
                self.ungroupSelected()
            elif action == deleteGroupAct:
                for node in item.nodes:
                    self.scene.removeNode(node)
                self.scene.removeItem(item)
                self.scene.history.storeHistory("Deleted Group and Nodes")

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

        item = self.scene.getItemAt(event.pos())
        if isinstance(item, QGraphicsProxyWidget):
            item = item.widget()

        selected_nodes = [
            graph_item.node
            for graph_item in self.scene.getSelectedItems()
            if hasattr(graph_item, "node")
        ]
        print(
            "🐍 File: qt/design_window.py:375 | handleNodeContextMenu ~ selected_nodes",
            selected_nodes,
        )

        if len(selected_nodes) > 1:
            groupAct = context_menu.addAction("Group Nodes")
            context_menu.addSeparator()
        else:
            groupAct = None

        action = context_menu.exec(self.mapToGlobal(event.pos()))

        selected_node = None
        if hasattr(item, "node"):
            selected_node = item.node
        if hasattr(item, "socket"):
            selected_node = item.socket.node

        if debug_context:
            print("got item:", selected_node)

        if selected_node and action == markDirtyAct:
            selected_node.markDirty()
        if selected_node and action == markDirtyDescendantsAct:
            selected_node.markDescendantsDirty()
        if selected_node and action == markInvalidAct:
            selected_node.markInvalid()
        if selected_node and action == unmarkInvalidAct:
            selected_node.markInvalid(False)
        if selected_node and action == evalAct:
            value = selected_node.eval()
            if debug_context:
                print("EVALUATED:", value)

        if selected_nodes and groupAct and action == groupAct:
            self.createGroup(selected_nodes)

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
        """Create a new node group containing the selected nodes."""
        if nodes is None:
            nodes = [
                item.node
                for item in self.scene.selectedItems()
                if hasattr(item, "node")
            ]

        if len(nodes) < 2:
            return None

        group = NodeGroup(self.scene)
        for node in nodes:
            group.add_node(node)

        self.scene.history.storeHistory("Created Node Group")
        return group

    def ungroupSelected(self):
        """Ungroup the selected group."""
        for item in self.scene.getSelectedItems():
            if isinstance(item, NodeGroup):
                self.scene.grScene.removeItem(item)
                self.scene.history.storeHistory("Ungroup Nodes")
