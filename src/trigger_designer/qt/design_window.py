from loguru import logger
from collections import deque
import time

from qtpy.QtGui import (
    QIcon,
    QPixmap,
    QCursor,
    QDropEvent,
    QContextMenuEvent,
    QCloseEvent,
    QDragEnterEvent,
    QKeyEvent,
)
from qtpy.QtCore import QDataStream, QIODevice, Qt, Signal, QSize
from qtpy.QtWidgets import (
    QAction,
    QGraphicsProxyWidget,
    QMenu,
    QWidget,
    QVBoxLayout,
    QPushButton,
)

from nodeeditor.node_editor_widget import NodeEditorWidget
from nodeeditor.node_edge import EDGE_TYPE_DIRECT, EDGE_TYPE_BEZIER, EDGE_TYPE_SQUARE
from nodeeditor.node_graphics_view import MODE_EDGE_DRAG
from nodeeditor.utils import dumpException

from trigger_designer.core.node_configuration import (
    NODE_REGISTRIES,
    NodeTypes,
    get_class_from_opcode,
    LISTBOX_MIMETYPE,
)
from trigger_designer.core.ExecutionCheck.executor import NodeExecutor
from trigger_designer.qt.docks.result import ResultDock
from trigger_designer.qt.helpers.logger import Logger, LogLevel
from trigger_designer.qt.resource_manager import ResourceManager
from trigger_designer.qt.widgets.data_preview_window import DataPreviewWindow
from trigger_designer.qt.widgets.node_searchable_menu import SearchableMenu
from trigger_designer.qt.widgets.node_group import NodeGroup

from typing import Any, Callable, Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from trigger_designer.qt.main_window import TriggerWindow
    from trigger_designer.qt.node_base import TriggerNode
    from nodeeditor.node_node import Node
    from nodeeditor.node_socket import Socket

DEBUG = False
DEBUG_CONTEXT = False


class TriggerSubWindow(NodeEditorWidget):
    itemSelected = Signal(object)

    def __init__(self, parent: Union[QWidget, "TriggerWindow"] = None) -> None:
        super().__init__(parent)
        print("🐍 File: qt/design_window.py:32 | __init__ ~ parent", parent)
        # self.initUI()
        self.logger: Logger = Logger(self)
        self.rsm: ResourceManager = ResourceManager()


<< << << < HEAD

== == == =
        logger.error(
            "🐍 File: qt/design_window.py:m : ",
            self.rsm.get_full_path("node_file_input"),
            " ********* ",
        )
>>>>>> > c63aae470736a77aeacf23a62671d42cc2099cf3
        # self.design_window_id = str(id(self))
        # self.logger.set_context(self.design_window_id)

        self._last_scale: float = 1.0
        self.execution_results: dict = {}  # Store execution results for each node
        self.selected_action_data: Optional[list] = None

        self.setTitle()
        self.addButtons()

        self.initNewNodeActions()

        self.scene.addHasBeenModifiedListener(self.setTitle)
        self.scene.history.addHistoryRestoredListener(self.onHistoryRestored)
        self.scene.addDragEnterListener(self.onDragEnter)
        self.scene.addDropListener(self.onDrop)
        self.scene.setNodeClassSelector(self.getNodeClassFromData)
        self.scene.addItemSelectedListener(self.onItemSelected)
        self.scene.grScene.socketClicked.connect(self.onSocketClicked)
        self._close_event_listeners: list[Callable] = []
        # self.setAttribute(Qt.WA_DeleteOnClose)

    # Add this to where you handle socket clicks
    def onSocketClicked(self, socket: "Socket", node: "Node"):
        if socket.is_input:
            return
        socket_index = node.outputs.index(socket)
        data = self.getSocketData(node, socket_index)
        if data is not None:
            # Create and show the data preview window
            title = f"Socket {socket_index} Data - {node.__class__.__name__}"
            preview_window = DataPreviewWindow(data, title, self)
            preview_window.show()

    def addButtons(self) -> None:
        # Run button
        self.run_button = QPushButton("", self)
        self.run_button.setIcon(QIcon.fromTheme("media-playback-start"))
        self.run_button.setToolTip("Run Workflow")
        self.run_button.setFixedSize(100, 30)
        self.run_button.move(10, 10)
        self.run_button.clicked.connect(self.run_workflow)

        # Zoom In button
        self.zoom_in_button = QPushButton("", self)
        self.zoom_in_button.setIcon(QIcon.fromTheme("zoom-in"))
        self.zoom_in_button.setToolTip("Zoom In")
        self.zoom_in_button.setFixedSize(100, 30)
        self.zoom_in_button.move(120, 10)
        self.zoom_in_button.clicked.connect(self.zoomIn)

        # Zoom Out button
        self.zoom_out_button = QPushButton("", self)
        self.zoom_out_button.setIcon(QIcon.fromTheme("zoom-out"))
        self.zoom_out_button.setToolTip("Zoom Out")
        self.zoom_out_button.setFixedSize(100, 30)
        self.zoom_out_button.move(230, 10)
        self.zoom_out_button.clicked.connect(self.zoomOut)

        # Fit View button
        self.fit_button = QPushButton("", self)
        self.fit_button.setIcon(QIcon.fromTheme("zoom-original"))
        self.fit_button.setToolTip("Fit View")
        self.fit_button.setFixedSize(100, 30)
        self.fit_button.move(340, 10)
        self.fit_button.clicked.connect(self.fitView)

    # def activateWindow(self) -> None:
    #     super().activateWindow()
    #     self.logger.set_context(self.design_window_id)

    def zoomIn(self) -> None:
        zoom_factor = self.view.zoomIn()
        self._last_scale *= zoom_factor
        self.view.applyZoom(zoom_factor)

    def zoomOut(self) -> None:
        zoom_factor = self.view.zoomOut()
        print(
            "🐍 File: TriggerEditor/trigger_sub_window.py | Line: 80 | zoomOut ~ zoom_factor",
            zoom_factor,
        )
        self._last_scale *= zoom_factor
        self.view.applyZoom(zoom_factor)

    def fitView(self) -> None:
        nodes = self.scene.nodes
        if not nodes:
            return
        start_time = time.time()

        try:
            # Calculate the bounding rectangle of all nodes
            rect = None
            for node in nodes:
                if rect is None:
                    rect = node.grNode.boundingRect()
                    rect.moveTopLeft(node.pos)
                else:
                    node_rect = node.grNode.boundingRect()
                    node_rect.moveTopLeft(node.pos)
                    rect = rect.united(node_rect)

            if rect is None:
                return

            # Add padding around the nodes
            padding = 50
            rect = rect.adjusted(-padding, -padding, padding, padding)

            # Fit the view while preserving current scale
            self.view.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
            self._last_scale = self.view.transform().m11()  # Store current scale
            self.view.zoom = self._last_scale * 10
            self.view.centerOn(rect.center())

            print(f"⌚ Fit View Time: {time.time() - start_time:.4f}s")
            print(f"Current scale: {self._last_scale}")

        except Exception as e:
            dumpException(e)

    def keyPressEvent(self, event: Optional[QKeyEvent]) -> None:
        # Check for Shift+A
        if (
            event.key() == Qt.Key.Key_A
            and event.modifiers() == Qt.KeyboardModifier.ShiftModifier
        ):
            # Get the cursor position and map it to scene coordinates
            cursor_pos = self.mapFromGlobal(self.cursor().pos())
            self.showNodeContextMenu(cursor_pos)
        if (
            event.key() == Qt.Key.Key_P
            and event.modifiers() == Qt.KeyboardModifier.ShiftModifier
        ):
            print()
            print(
                "------------------------------------------------------------------------------"
            )
            print()
        else:
            super().keyPressEvent(event)

    def onItemSelected(self) -> None:
        # print(f'node: {self.scene._last_selected_items}')
        self.itemSelected.emit(self.scene._last_selected_items)

    def getNodeClassFromData(self, data):
        print(f"getNodeClassFromData: {data}")
        if "node_code" not in data:
            return Node
        return get_class_from_opcode(data["node_code"], data["node_type"])

    def doEvalOutputs(self) -> None:
        # eval all output nodes
        for node in self.scene.nodes:
            # if node.__class__.__name__ == "CalcNode_Output":
            node.eval()

    def onHistoryRestored(self) -> None:
        self.doEvalOutputs()

    def fileLoad(self, filename: str) -> bool:
        if super().fileLoad(filename):
            # self.validateConnections()
            self.doEvalOutputs()
            return True

        return False

    def validateConnections(self) -> None:
        """Validate all edge connections and remove invalid ones"""
        invalid_edges = []

        # Check all edges in the scene
        for edge in self.scene.edges:
            if (
                edge.start_socket is None
                or edge.end_socket is None
                or edge.start_socket.node is None
                or edge.end_socket.node is None
            ):
                invalid_edges.append(edge)
                continue

            # Validate socket indices
            start_node = edge.start_socket.node
            end_node = edge.end_socket.node

            if (
                edge.start_socket not in start_node.outputs
                or edge.end_socket not in end_node.inputs
            ):
                invalid_edges.append(edge)

        # Remove invalid edges
        for edge in invalid_edges:
            if edge in self.scene.edges:
                self.scene.removeEdge(edge)
                print(f"Removed invalid edge: {edge}")

    def initNewNodeActions(self) -> None:
        self.node_actions = {}
        self.nodes_by_type = {
            # 'Calculation': NODE_REGISTRIES[NodeTypes.CALC],
            "Input/Output": NODE_REGISTRIES[NodeTypes.IO],
            "Preparation": NODE_REGISTRIES[NodeTypes.PREPARATION],
            "Join": NODE_REGISTRIES[NodeTypes.JOIN],
            "Transform": NODE_REGISTRIES[NodeTypes.TRANSFORM],
            "Report": NODE_REGISTRIES[NodeTypes.REPORT],
        }

        # Create actions for all nodes across all types
        for category, nodes in self.nodes_by_type.items():
            for node_code, node_class in nodes.items():
                action_key = f"{category}_{node_code}"
                logger.success(
                    f"Registering action: '{action_key}' for node '{node_class.node_title}' and icon path '{self.rsm.get_icon_path(node_class.icon)}'"
                )
                self.node_actions[action_key] = QAction(
                    QIcon(f":{category}/{self.rsm.get_icon_path(node_class.icon)}"),
                    node_class.node_title,
                )
                # Store both node code and type for later use
                node_type = next(
                    type_name
                    for type_name, registry in NODE_REGISTRIES.items()
                    if node_class in registry.values()
                )
                self.node_actions[action_key].setData([node_code, node_type])

    def initNodesContextMenu(self):
        context_menu = SearchableMenu(self)

        # Create submenus for each category
        for category, nodes in self.nodes_by_type.items():
            if not nodes:  # Skip empty categories
                continue

            # Create submenu for category
            submenu = QMenu(category, context_menu)
            context_menu.addMenu(submenu)

            # Store submenu reference
            context_menu.all_submenus[category] = submenu
            context_menu.all_actions[category] = []

            # Add sorted nodes to submenu
            node_list = list(nodes.values())
            node_list.sort(key=lambda x: x.node_title)

            for node in node_list:
                action = self.node_actions[f"{category}_{node.node_code}"]
                submenu.addAction(action)
                context_menu.all_actions[category].append(action)

        return context_menu

    # def initNodesContextMenu(self):
    #     context_menu = QMenu(self)

    #     # Create submenus for each category
    #     for category, nodes in self.nodes_by_type.items():
    #         if not nodes:  # Skip empty categories
    #             continue

    #         # Create submenu for category
    #         submenu = QMenu(category, context_menu)
    #         context_menu.addMenu(submenu)

    #         # Add sorted nodes to submenu
    #         node_list = list(nodes.values())
    #         node_list.sort(key=lambda x: x.node_title)

    #         for node in node_list:
    #             submenu.addAction(
    #                 self.node_actions[f"{category}_{node.node_code}"])

    #     return context_menu

    def setTitle(self) -> None:
        self.setWindowTitle(self.getUserFriendlyFilename())

    def addCloseEventListener(self, callback) -> None:
        self._close_event_listeners.append(callback)

    # def closeEvent(self, event: QCloseEvent) -> None:
    #     for callback in self._close_event_listeners:
    #         callback(self, event)
    #     self.logger.clear_context()

    def onDragEnter(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasFormat(LISTBOX_MIMETYPE):
            event.acceptProposedAction()
        else:
            # print(" ... denied drag enter event")
            event.setAccepted(False)

    def onDrop(self, event: QDropEvent) -> None:
        if event.mimeData().hasFormat(LISTBOX_MIMETYPE):
            eventData = event.mimeData().data(LISTBOX_MIMETYPE)
            dataStream = QDataStream(eventData, QIODevice.OpenModeFlag.ReadOnly)
            pixmap = QPixmap()
            dataStream >> pixmap
            # print("eventData::::::::::", eventData)
            # print("dataStream::::::::: ", dataStream)
            node_code = dataStream.readInt()
            node_type = dataStream.readQString()

            mouse_position = event.pos()
            scene_position = self.scene.grScene.views()[0].mapToScene(mouse_position)

            if DEBUG:
                print(
                    "GOT DROP: [%d] '%s'" % (node_code, node_type),
                    "mouse:",
                    mouse_position,
                    "scene:",
                    scene_position,
                )

            try:
                print("1...")
                node_type_enum = NodeTypes(node_type)
                print("2...")
                node = get_class_from_opcode(node_code, node_type_enum)(
                    self.scene
                )  # type: ignore
                print("3...")
                node.setPos(scene_position.x(), scene_position.y())
                print("4...")
                self.scene.history.storeHistory(
                    "Created node %s" % node.__class__.__name__
                )
                print("5...")
            except Exception as e:
                dumpException(e)

            event.setDropAction(Qt.DropAction.MoveAction)
            event.accept()
        else:
            # print(" ... drop ignored, not requested format '%s'" % LISTBOX_MIMETYPE)
            event.ignore()

    def contextMenuEvent(self, event):
        try:
            item = self.scene.getItemAt(event.pos())
            if DEBUG_CONTEXT:
                print(item)

            if type(item) == QGraphicsProxyWidget:
                item = item.widget()

            # Check for groups first
            if isinstance(item, NodeGroup):
                self.handleGroupContextMenu(event)
            elif hasattr(item, "node") or hasattr(item, "socket"):
                self.handleNodeContextMenu(event)
            elif hasattr(item, "edge"):
                self.handleEdgeContextMenu(event)
            # elif item is None:
            else:
                self.handleNewNodeContextMenu(event)

            return super().contextMenuEvent(event)
        except Exception as e:
            dumpException(e)

    def handleGroupContextMenu(self, event):
        """Handle context menu for node groups"""
        context_menu = QMenu(self)

        # Add group-specific actions
        ungroupAct = context_menu.addAction("Ungroup")
        deleteGroupAct = context_menu.addAction("Delete Group")
        context_menu.addSeparator()

        action = context_menu.exec_(self.mapToGlobal(event.pos()))

        item = self.scene.getItemAt(event.pos())
        if isinstance(item, NodeGroup):
            if action == ungroupAct:
                # Keep nodes but remove group
                self.ungroupSelected()
            elif action == deleteGroupAct:
                # Remove both group and contained nodes
                for node in item.nodes:
                    self.scene.removeNode(node)
                self.scene.removeItem(item)
                self.scene.history.storeHistory("Deleted Group and Nodes")

    def handleNodeContextMenu(self, event: QContextMenuEvent) -> None:
        if DEBUG_CONTEXT:
            print("CONTEXT: NODE")
        context_menu = QMenu(self)
        markDirtyAct = context_menu.addAction("Mark Dirty")
        markDirtyDescendantsAct = context_menu.addAction("Mark Descendant Dirty")
        markInvalidAct = context_menu.addAction("Mark Invalid")
        unmarkInvalidAct = context_menu.addAction("Unmark Invalid")
        evalAct = context_menu.addAction("Eval")

        selected = None
        item = self.scene.getItemAt(event.pos())
        if type(item) == QGraphicsProxyWidget:
            item = item.widget()

        selected_nodes = [
            item.node for item in self.scene.getSelectedItems() if hasattr(item, "node")
        ]
        print(
            "🐍 File: qt/design_window.py:375 | handleNodeContextMenu ~ selected_nodes",
            selected_nodes,
        )

        if len(selected_nodes) > 1:
            groupAct = context_menu.addAction("Group Nodes")
            context_menu.addSeparator()

        action = context_menu.exec(self.mapToGlobal(event.pos()))

        if hasattr(item, "node"):
            selected = item.node
        if hasattr(item, "socket"):
            selected = item.socket.node

        if DEBUG_CONTEXT:
            print("got item:", selected)
        if selected and action == markDirtyAct:
            selected.markDirty()
        if selected and action == markDirtyDescendantsAct:
            selected.markDescendantsDirty()
        if selected and action == markInvalidAct:
            selected.markInvalid()
        if selected and action == unmarkInvalidAct:
            selected.markInvalid(False)
        if selected and action == evalAct:
            val = selected.eval()
            if DEBUG_CONTEXT:
                print("EVALUATED:", val)
        # Handle group action
        if selected_nodes and action == groupAct:
            self.createGroup(selected_nodes)

    def handleEdgeContextMenu(self, event: QContextMenuEvent) -> None:
        if DEBUG_CONTEXT:
            print("CONTEXT: EDGE")
        context_menu = QMenu(self)
        bezierAct = context_menu.addAction("Bezier Edge")
        directAct = context_menu.addAction("Direct Edge")
        squareAct = context_menu.addAction("Square Edge")
        action = context_menu.exec_(self.mapToGlobal(event.pos()))

        selected = None
        item = self.scene.getItemAt(event.pos())
        if hasattr(item, "edge"):
            selected = item.edge

        if selected and action == bezierAct:
            selected.edge_type = EDGE_TYPE_BEZIER
        if selected and action == directAct:
            selected.edge_type = EDGE_TYPE_DIRECT
        if selected and action == squareAct:
            selected.edge_type = EDGE_TYPE_SQUARE

    # helper functions
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

    def set_selected_action_data(self, data) -> None:
        self.selected_action_data = data

    def add_node_to_scene(self) -> None:
        # This method should add the node to the scene
        # You can customize this method based on your requirements
        print("🍒 Adding node to the scene")
        # Example implementation:
        node_code, node_type = self.selected_action_data
        new_calc_node = get_class_from_opcode(node_code, node_type)(self.scene)
        cursor_pos = self.mapFromGlobal(QCursor.pos())
        scene_pos = self.scene.getView().mapToScene(cursor_pos)
        new_calc_node.setPos(scene_pos.x(), scene_pos.y())
        self.scene.history.storeHistory("Created %s" % new_calc_node.__class__.__name__)

    def showNodeContextMenu(self, position) -> None:
        if DEBUG_CONTEXT:
            print("CONTEXT: EMPTY SPACE")
        context_menu = self.initNodesContextMenu()
        action = context_menu.exec_(self.mapToGlobal(position))

        if action is not None and action.data():
            try:
                print("Action was triggered!")
                self.selected_action_data = action.data()
                self.add_node_to_scene()
                # Create node directly without storing action data
                # node_code, node_type = action.data()
                # new_calc_node = get_class_from_opcode(
                #     node_code, node_type)(self.scene)
                # cursor_pos = self.mapFromGlobal(QCursor.pos())
                # scene_pos = self.scene.getView().mapToScene(cursor_pos)
                # new_calc_node.setPos(scene_pos.x(), scene_pos.y())
                # self.scene.history.storeHistory(
                #     "Created %s" % new_calc_node.__class__.__name__)
            except Exception as e:
                dumpException(e)

    def handleNewNodeContextMenu(self, event) -> None:
        if DEBUG_CONTEXT:
            print("CONTEXT: EMPTY SPACE")
        self.showNodeContextMenu(event.pos())

    def run_workflow(self) -> None:
        self.executeWorkflow()

    def getPyFile(self) -> None:
        connections = self.getNodeConnections()
        sorted_nodes = self.topologicalSort(connections)
        code = """"""
        for node in sorted_nodes:
            code += node.get_code()
            print(code)

        with open("check_output.py", "w") as file:
            # Write the string to the file
            file.write(code)

    def getAllNodes(self) -> list['TriggerNode']:
        return self.scene.nodes

    def getNodeConnections(self) -> dict:
        connections = {}
        for node in self.getAllNodes():
            connections[node] = {
                "inputs": (
                    [
                        edge.start_socket.node
                        for socket in node.inputs
                        for edge in socket.edges
                    ]
                    if node.inputs
                    else []
                ),
                "outputs": (
                    [
                        edge.end_socket.node
                        for socket in node.outputs
                        for edge in socket.edges
                    ]
                    if node.outputs
                    else []
                ),
            }
        return connections

    def topologicalSort(self, connections):
        in_degree = {node: 0 for node in connections}
        for node in connections:
            for output_node in connections[node]["outputs"]:
                in_degree[output_node] += 1

        queue = deque([node for node in connections if in_degree[node] == 0])
        sorted_nodes = []

        while queue:
            node = queue.popleft()
            sorted_nodes.append(node)
            for output_node in connections[node]["outputs"]:
                in_degree[output_node] -= 1
                if in_degree[output_node] == 0:
                    queue.append(output_node)

        if len(sorted_nodes) != len(connections):
            raise Exception("Graph has at least one cycle")

        return sorted_nodes

    def test_execution_visuals(self) -> None:
        """Test function to verify execution visual effects"""
        self.run_button.setEnabled(False)
        connections = self.getNodeConnections()
        sorted_nodes = self.topologicalSort(connections)

        # Get all nodes
        nodes = self.getAllNodes()

        # Reset all node borders to default
        for node in sorted_nodes:
            node.grNode.resetPen()
            node.grNode.update()

        # Process nodes one by one with delays
        self._process_next_node(nodes, 0)

    def _process_next_node(self, nodes: list, current_index: int) -> None:
        """Process nodes sequentially with visual transitions"""
        if current_index >= len(nodes):
            # All nodes processed, cleanup
            QTimer.singleShot(1000, self._test_cleanup)
            return

        node = nodes[current_index]

        # Show executing state (purple)
        node.grNode.setPenExecuting()
        node.grNode.update()

        # Schedule transition to executed state (green)
        QTimer.singleShot(1000, lambda: self._transition_to_executed(node))

        # Schedule processing of next node
        QTimer.singleShot(1500, lambda: self._process_next_node(
            nodes, current_index + 1))

    def _test_executed_state(self, node):
        """Helper to show executed state"""
        node.grNode.setPenExecuted()
        node.grNode.update()

    def _transition_to_executed(self, node) -> None:
        """Transition a single node to executed state"""
        node.grNode.setPenExecuted()
        node.grNode.update()

    def _test_cleanup(self) -> None:
        """Reset all nodes and re-enable run button"""
        for node in self.getAllNodes():
            node.grNode.resetPen()
            node.grNode.update()
        self.run_button.setEnabled(True)

    def executeWorkflow(self) -> None:
        # self.test_execution_visuals()
        self.run_button.setEnabled(False)
        connections = self.getNodeConnections()
        import_node = None
        sorted_nodes = self.topologicalSort(connections)
        node_data = {}
        # executor = NodeExecutor()
        executor = NodeExecutor()

        # Reset all node borders
        for node in self.getAllNodes():
            node.grNode.resetPen()
            node.grNode.update()

        start_time = time.time()

        self._execute_next_node(sorted_nodes, 0, executor)

        # for node in sorted_nodes:
        #     node.grNode.setPenExecuting()
        #     node.grNode.update()

        #     stdoutput, local_variables = executor.execute_node(node)
        #     # Store execution results for this node
        #     self.execution_results[node] = local_variables

        #     node.grNode.setPenExecuted()
        #     node.grNode.update()

        # end_time = time.time()
        # print("Execution Time: ", end_time - start_time, " seconds")
        # self.getPyFile()

        # for node in self.getAllNodes():
        #     node.grNode.resetPen()

        # self.run_button.setEnabled(True)

    def _execute_next_node(self, nodes: list, current_index: int, executor: NodeExecutor) -> None:
        """Execute nodes sequentially with visual transitions"""
        if current_index >= len(nodes):
            # All nodes processed, cleanup
            QTimer.singleShot(1000, self._execution_cleanup)
            return

        node = nodes[current_index]

        # Show executing state (purple)
        node.grNode.setPenExecuting()
        node.grNode.update()

        # Execute the node
        try:
            stdoutput, local_variables = executor.execute_node(node)
            self.execution_results[node] = local_variables

            # Show success state (green)
            node.grNode.setPenExecuted()
            node.grNode.update()
        except Exception as e:
            # Could add error state visual here
            logger.error(f"Error executing node {node}: {str(e)}")
            node.grNode.resetPen()
            node.grNode.update()
            self._execution_cleanup()
            return

        # Schedule next node execution
        QTimer.singleShot(500, lambda: self._execute_next_node(
            nodes, current_index + 1, executor))

    def _execution_cleanup(self) -> None:

        for node in self.getAllNodes():
            node.grNode.resetPen()
            node.grNode.update()

        self.run_button.setEnabled(True)

    def getSocketData(self, node, socket_index: int) -> Any:
        """Get the data associated with a specific socket after execution"""
        if self.execution_results is None:
            print("No execution results available. Run the workflow first.")
            return None

        if node not in self.execution_results:
            print(f"No results found for node {node}")
            return None

        # Get the variable name for this socket from the node
        if hasattr(node, 'param'):
            print("node.param: ", node.param)
            socket_data = node.param[socket_index]
            if socket_data:
                var_name = socket_data["variable_name"]
                # Look up the actual data in execution results
                if var_name in self.execution_results[node]:
                    return self.execution_results[node][var_name]

        return None

    def createGroup(self, nodes=None):
        """Create a new node group containing the selected nodes"""
        if nodes is None:
            nodes = [
                item.node
                for item in self.scene.selectedItems()
                if hasattr(item, "node")
            ]

        if len(nodes) < 2:
            return

        group = NodeGroup(self.scene)
        for node in nodes:
            group.add_node(node)

        self.scene.history.storeHistory("Created Node Group")
        return group

    def ungroupSelected(self):
        """Ungroup the selected group"""
        for item in self.scene.getSelectedItems():
            if isinstance(item, NodeGroup):
                self.scene.grScene.removeItem(item)
                self.scene.history.storeHistory("Ungroup Nodes")
