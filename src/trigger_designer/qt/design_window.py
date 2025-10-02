from loguru import logger
from collections import deque
import time

from qtpy.QtGui import (
    QIcon,
    QPixmap,
    QDropEvent,
    QCloseEvent,
    QDragEnterEvent,
    QKeyEvent,
)
from qtpy.QtCore import QDataStream, QIODevice, Qt, Signal, QSize, QTimer
from qtpy.QtWidgets import (
    QWidget,
    QPushButton,
)

from nodeeditor.node_editor_widget import NodeEditorWidget
from nodeeditor.utils import dumpException

from trigger_designer.core.node_configuration import (
    NODE_REGISTRIES,
    NodeTypes,
    get_class_from_opcode,
    LISTBOX_MIMETYPE,
)
from trigger_designer.qt.helpers.context_menu_mixin import ContextMenuMixin
from trigger_designer.qt.helpers.logger import Logger
from trigger_designer.qt.resource_manager import ResourceManager
from trigger_designer.qt.widgets.data_preview_window import DataPreviewWindow
from trigger_designer.qt.helpers.workflow_execution_mixin import WorkflowExecutionMixin

from typing import Any, Callable, Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from trigger_designer.qt.main_window import TriggerWindow
    from trigger_designer.qt.node_base import TriggerNode
    from nodeeditor.node_node import Node
    from nodeeditor.node_socket import Socket

DEBUG = False
DEBUG_CONTEXT = False


class TriggerSubWindow(WorkflowExecutionMixin, ContextMenuMixin, NodeEditorWidget):
    itemSelected = Signal(object)

    def __init__(self, parent: Union[QWidget, "TriggerWindow"] = None) -> None:
        super().__init__(parent)
        print("🐍 File: qt/design_window.py:32 | __init__ ~ parent", parent)
        # self.initUI()
        self.logger: Logger = Logger(self)
        self.rsm: ResourceManager = ResourceManager()

        # self.design_window_id = str(id(self))
        # self.logger.set_context(self.design_window_id)

        self._last_scale: float = 1.0

        self.init_workflow_execution()
        self.init_context_menu_support()

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
        """Handle keyboard events.
        
        Shortcuts:
        - Shift+A: Show node context menu
        - Shift+P: Print separator
        - Ctrl+Shift+R: Reset workflow statistics
        - Ctrl+Shift+S: Show workflow statistics
        """
        # Check for Shift+A
        if (
            event.key() == Qt.Key.Key_A
            and event.modifiers() == Qt.KeyboardModifier.ShiftModifier
        ):
            # Get the cursor position and map it to scene coordinates
            cursor_pos = self.mapFromGlobal(self.cursor().pos())
            self.showNodeContextMenu(cursor_pos)
        elif (
            event.key() == Qt.Key.Key_P
            and event.modifiers() == Qt.KeyboardModifier.ShiftModifier
        ):
            print()
            print(
                "------------------------------------------------------------------------------"
            )
            print()
        elif (
            event.key() == Qt.Key.Key_R
            and event.modifiers() == Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
        ):
            # Ctrl+Shift+R to reset workflow statistics
            self.reset_workflow_statistics()
        elif (
            event.key() == Qt.Key.Key_S
            and event.modifiers() == Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
        ):
            # Ctrl+Shift+S to show workflow statistics
            stats = self.get_workflow_statistics()
            print(f"\n{'='*50}")
            print(f"📊 WORKFLOW STATISTICS")
            print(f"{'='*50}")
            print(f"Total executions: {stats['total_executions']}")
            print(f"Total time: {stats['total_time']:.3f} seconds")
            print(f"Average time: {stats['average_execution_time']:.3f} seconds")
            print(f"{'='*50}\n")
            logger.info(f"📊 Workflow statistics - Executions: {stats['total_executions']}, "
                       f"Total time: {stats['total_time']:.3f}s, "
                       f"Average: {stats['average_execution_time']:.3f}s")
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

    def run_workflow(self) -> None:
        self.executeWorkflow()

    def getPyFile(self, sorted_nodes) -> None:
        code = """"""
        for node in sorted_nodes:
            code += node.get_code()
            # print(code)

        with open("check_output.py", "w") as file:
            # Write the string to the file
            file.write(code)

    def getAllNodes(self) -> list["TriggerNode"]:
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
        QTimer.singleShot(
            1500, lambda: self._process_next_node(nodes, current_index + 1)
        )

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


