import time
from unittest import result
from qtpy.QtGui import QIcon, QPixmap
from qtpy.QtCore import QDataStream, QIODevice, Qt, Signal
from qtpy.QtWidgets import QAction, QGraphicsProxyWidget, QMenu, QWidget, QVBoxLayout, QPushButton

from trigger_conf import CALC_NODES, get_class_from_opcode, LISTBOX_MIMETYPE
from nodeeditor.node_editor_widget import NodeEditorWidget
from nodeeditor.node_edge import EDGE_TYPE_DIRECT, EDGE_TYPE_BEZIER, EDGE_TYPE_SQUARE
from nodeeditor.node_graphics_view import MODE_EDGE_DRAG
from nodeeditor.utils import dumpException

from collections import deque

from ExecutionCheck.executor import NodeExecutor
# from ExecutionCheck.exec_node import InputNode, PrintNode
from utils.logger import Logger

DEBUG = True
DEBUG_CONTEXT = True


class TriggerSubWindow(NodeEditorWidget):
    itemSelected = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        # self.initUI()
        self.logger = Logger()
        self.setTitle()
        self.addRunButton()

        self.initNewNodeActions()

        self.scene.addHasBeenModifiedListener(self.setTitle)
        self.scene.history.addHistoryRestoredListener(self.onHistoryRestored)
        self.scene.addDragEnterListener(self.onDragEnter)
        self.scene.addDropListener(self.onDrop)
        self.scene.setNodeClassSelector(self.getNodeClassFromData)
        self.scene.addItemSelectedListener(self.onItemSelected)
        self._close_event_listeners = []
        # self.setAttribute(Qt.WA_DeleteOnClose)

    def addRunButton(self):
        self.fixed_button = QPushButton("Run", self)
        self.fixed_button.setFixedSize(100, 30)  # Set the size of the button
        self.fixed_button.move(10, 10)
        self.fixed_button.clicked.connect(self.run_workflow)

    # def initUI(self):
    #     super().initUI()
    #     # self.central_widget = QWidget(self)
    #     # self.layout = QVBoxLayout(self.central_widget)
    #     # self.layout = QVBoxLayout(self)

    #     self.fixed_button = QPushButton("Run", self)
    #     self.fixed_button.setFixedSize(100, 30)  # Set the size of the button
    #     self.fixed_button.move(10, 10)
    #     self.fixed_button.clicked.connect(self.run_workflow)
    #     # Position the button
    #     # self.fixed_button.move(10, 10)
    #     # self.fixed_button.raise_()

    def onItemSelected(self):
        # print(f'node: {self.scene._last_selected_items}')
        self.itemSelected.emit(self.scene._last_selected_items)

    def getNodeClassFromData(self, data):
        print(f'getNodeClassFromData: {data}')
        if 'op_code' not in data:
            return Node
        return get_class_from_opcode(data['op_code'], data['op_type'])

    def doEvalOutputs(self):
        # eval all output nodes
        for node in self.scene.nodes:
            # if node.__class__.__name__ == "CalcNode_Output":
            node.eval()

    def onHistoryRestored(self):
        self.doEvalOutputs()

    def fileLoad(self, filename):
        if super().fileLoad(filename):
            self.doEvalOutputs()
            return True

        return False

    def initNewNodeActions(self):
        self.node_actions = {}
        keys = list(CALC_NODES.keys())
        keys.sort()
        for key in keys:
            node = CALC_NODES[key]
            self.node_actions[node.op_code] = QAction(
                QIcon(node.icon), node.op_title)
            self.node_actions[node.op_code].setData(node.op_code)

    def initNodesContextMenu(self):
        context_menu = QMenu(self)
        keys = list(CALC_NODES.keys())
        keys.sort()
        for key in keys:
            context_menu.addAction(self.node_actions[key])
        return context_menu

    def setTitle(self):
        self.setWindowTitle(self.getUserFriendlyFilename())

    def addCloseEventListener(self, callback):
        self._close_event_listeners.append(callback)

    def closeEvent(self, event):
        for callback in self._close_event_listeners:
            callback(self, event)

    def onDragEnter(self, event):
        if event.mimeData().hasFormat(LISTBOX_MIMETYPE):
            event.acceptProposedAction()
        else:
            # print(" ... denied drag enter event")
            event.setAccepted(False)

    def onDrop(self, event):
        if event.mimeData().hasFormat(LISTBOX_MIMETYPE):
            eventData = event.mimeData().data(LISTBOX_MIMETYPE)
            dataStream = QDataStream(eventData, QIODevice.ReadOnly)
            pixmap = QPixmap()
            dataStream >> pixmap
            # print("eventData::::::::::", eventData)
            # print("dataStream::::::::: ", dataStream)
            op_code = dataStream.readInt()
            text = dataStream.readQString()

            mouse_position = event.pos()
            scene_position = self.scene.grScene.views()[
                0].mapToScene(mouse_position)

            if DEBUG:
                print("GOT DROP: [%d] '%s'" % (op_code, text),
                      "mouse:", mouse_position, "scene:", scene_position)

            try:
                node = get_class_from_opcode(op_code, text)(self.scene)
                node.setPos(scene_position.x(), scene_position.y())
                self.scene.history.storeHistory(
                    "Created node %s" % node.__class__.__name__)
            except Exception as e:
                dumpException(e)

            event.setDropAction(Qt.MoveAction)
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

            if hasattr(item, 'node') or hasattr(item, 'socket'):
                self.handleNodeContextMenu(event)
            elif hasattr(item, 'edge'):
                self.handleEdgeContextMenu(event)
            # elif item is None:
            else:
                self.handleNewNodeContextMenu(event)

            return super().contextMenuEvent(event)
        except Exception as e:
            dumpException(e)

    def handleNodeContextMenu(self, event):
        if DEBUG_CONTEXT:
            print("CONTEXT: NODE")
        context_menu = QMenu(self)
        markDirtyAct = context_menu.addAction("Mark Dirty")
        markDirtyDescendantsAct = context_menu.addAction(
            "Mark Descendant Dirty")
        markInvalidAct = context_menu.addAction("Mark Invalid")
        unmarkInvalidAct = context_menu.addAction("Unmark Invalid")
        evalAct = context_menu.addAction("Eval")
        action = context_menu.exec_(self.mapToGlobal(event.pos()))

        selected = None
        item = self.scene.getItemAt(event.pos())
        if type(item) == QGraphicsProxyWidget:
            item = item.widget()

        if hasattr(item, 'node'):
            selected = item.node
        if hasattr(item, 'socket'):
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

    def handleEdgeContextMenu(self, event):
        if DEBUG_CONTEXT:
            print("CONTEXT: EDGE")
        context_menu = QMenu(self)
        bezierAct = context_menu.addAction("Bezier Edge")
        directAct = context_menu.addAction("Direct Edge")
        squareAct = context_menu.addAction("Square Edge")
        action = context_menu.exec_(self.mapToGlobal(event.pos()))

        selected = None
        item = self.scene.getItemAt(event.pos())
        if hasattr(item, 'edge'):
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

    def finish_new_node_state(self, new_calc_node):
        self.scene.doDeselectItems()
        new_calc_node.grNode.doSelect(True)
        new_calc_node.grNode.onSelected()

    def handleNewNodeContextMenu(self, event):

        if DEBUG_CONTEXT:
            print("CONTEXT: EMPTY SPACE")
        context_menu = self.initNodesContextMenu()
        action = context_menu.exec_(self.mapToGlobal(event.pos()))

        if action is not None:
            new_calc_node = get_class_from_opcode(action.data())(self.scene)
            scene_pos = self.scene.getView().mapToScene(event.pos())
            new_calc_node.setPos(scene_pos.x(), scene_pos.y())
            if DEBUG_CONTEXT:
                print("Selected node:", new_calc_node)

            if self.scene.getView().mode == MODE_EDGE_DRAG:
                # if we were dragging an edge...
                target_socket = self.determine_target_socket_of_node(
                    self.scene.getView().dragging.drag_start_socket.is_output, new_calc_node)
                if target_socket is not None:
                    self.scene.getView().dragging.edgeDragEnd(target_socket.grSocket)
                    self.finish_new_node_state(new_calc_node)

            else:
                self.scene.history.storeHistory(
                    "Created %s" % new_calc_node.__class__.__name__)

    def run_workflow(self):
        # all_nodes = self.getAllNodes()
        # connections = self.getNodeConnections()
        # sorted_nodes = self.topologicalSort(connections)
        # print('%%%%%%%%%%%%%%%%%%%%%')
        # print(sorted_nodes)
        # print('%%%%%%%%%%%%%%%%%%%%%')

        self.executeWorkflow()

        # for node in all_nodes:
        #     print(node)
        # for k, v in self.getNodeConnections().items():
        #     print(k)
        #     print(v)
        #     print("----------")

        # self.getPyFile()
        # Add some dummy logs for testing
        # print("Adding Logs")
        # self.logger.log("This is an info log.", "info")
        # self.logger.log("This is a warning log.", "warning")
        # self.logger.log("This is an error log.", "error")
        # self.logger.log("This is a debug log.", "debug")

    def getPyFile(self):
        connections = self.getNodeConnections()
        sorted_nodes = self.topologicalSort(connections)
        code = """"""
        for node in sorted_nodes:
            code += node.get_code()

        with open("check_output.py", "w") as file:
            # Write the string to the file
            file.write(code)

    def getAllNodes(self):
        return self.scene.nodes

    def getNodeConnections(self) -> dict:
        connections = {}
        for node in self.getAllNodes():
            connections[node] = {
                'inputs': [edge.start_socket.node for socket in node.inputs for edge in socket.edges] if node.inputs else [],
                'outputs': [edge.end_socket.node for socket in node.outputs for edge in socket.edges] if node.outputs else []
            }
        return connections

    def topologicalSort(self, connections):
        in_degree = {node: 0 for node in connections}
        for node in connections:
            for output_node in connections[node]['outputs']:
                in_degree[output_node] += 1

        queue = deque([node for node in connections if in_degree[node] == 0])
        sorted_nodes = []

        while queue:
            node = queue.popleft()
            sorted_nodes.append(node)
            for output_node in connections[node]['outputs']:
                in_degree[output_node] -= 1
                if in_degree[output_node] == 0:
                    queue.append(output_node)

        if len(sorted_nodes) != len(connections):
            raise Exception("Graph has at least one cycle")

        return sorted_nodes

    def executeWorkflow(self):
        connections = self.getNodeConnections()
        sorted_nodes = self.topologicalSort(connections)
        node_data = {}
        executor = NodeExecutor(self.logger)

        start_time = time.time()

        for node in sorted_nodes:
            # Collect data from all input nodes
            input_data = []
            for input_node in connections[node]['inputs']:
                # print(":::::::::::::::::::::::::::::::::")
                # print(input_node)
                # print(":::::::::::::::::::::::::::::::::")
                if input_node in node_data:
                    input_data.append(node_data[input_node])

            print(":::::::::::::::::::::::::::::::::")
            print(f"Code for {self.__class__.__name__}: ", node.get_code())
            print(":::::::::::::::::::::::::::::::::")
            l = executor.execute_node(node)
            print(":::::::::::::::::::::::::::::::::")
            print("executor: ", l)
            print(":::::::::::::::::::::::::::::::::")

        end_time = time.time()
        print("Execution Time: ", end_time - start_time, " seconds")
        self.getPyFile()
        # result = node.execute(input_data)
        # node_data[node] = result
        # print("Input Data::::", input_data)
        # print(connections[node]['inputs'])
        # print(connections[node]['outputs'])
        # print(":::::::::::::::::::::::::::::::::")

        # Execute the node's code
        # result = node.execute(input_data)
        # node_data[node] = result

    # def executeWorkflow(self):
    #     connections = self.getNodeConnections()
    #     sorted_nodes = self.topologicalSort(connections)
    #     node_data = {}

    #     for node in sorted_nodes:
    #         input_data = [
    #             input_node for input_node in connections[node]['inputs']]
    #         # input_data = [node_data[input_node]
    #         #               for input_node in connections[node]['inputs']]
    #         print(":::::::::::::::::::::::::::::::::")
    #         print("Input Data::::", input_data)
    #         print(":::::::::::::::::::::::::::::::::")
        # result = node.execute(input_data)
        # node_data[node] = result
