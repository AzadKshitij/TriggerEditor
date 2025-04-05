from ctypes import cast
from qtpy.QtGui import QImage, QPixmap, QBrush, QColor, QPen, QPainter
from qtpy.QtWidgets import QWidget, QLineEdit, QSpinBox, QComboBox, QCheckBox, QGraphicsItem, QStyleOptionGraphicsItem, QLayout
from qtpy.QtCore import QRectF, Qt, Signal, QTimer
from qtpy.QtWidgets import QLabel, QGraphicsPixmapItem, QGraphicsProxyWidget, QVBoxLayout

from nodeeditor.node_node import Node
from nodeeditor.node_content_widget import QDMNodeContentWidget
from nodeeditor.node_graphics_node import QDMGraphicsNode

from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget
from nodeeditor.node_icon_graphics_node import QDMIconGraphicsNode
from nodeeditor.node_socket import Socket
from nodeeditor.node_edge import Edge

from nodeeditor.node_socket import LEFT_CENTER, RIGHT_CENTER
from nodeeditor.utils import dumpException

from trigger_designer.qt.resource_manager import ResourceManager

from typing import TYPE_CHECKING, Any, List, Optional, OrderedDict, Type, TypeVar

if TYPE_CHECKING:
    from nodeeditor.node_scene import Scene

from loguru import logger


class TriggerGraphicsNode(QDMIconGraphicsNode):
    # Add signal for evaluation requests

    rsm = ResourceManager()

    def __init__(self, node: 'TriggerNode', parent: QGraphicsItem = None) -> None:
        super().__init__(node, parent)

        self._default_pen = QPen(QColor("#7F000000"))
        self._default_pen.setWidth(5)
        self._selected_pen = QPen(QColor("#FFFFA637"))
        self._selected_pen.setWidth(5)
        self._executing_pen = QPen(QColor("#FF800080"))  # Purple color
        self._executing_pen.setWidth(5)
        self._executed_pen = QPen(QColor("#FF008000"))   # Green color
        self._executed_pen.setWidth(5)

        self._pen = self._default_pen  # Current pen
        # self._brush_title = QBrush(QColor(style['brush_color']))

    def initSizes(self) -> None:
        super().initSizes()
        self.width = 120
        self.height = 120
        self.edge_roundness = 6
        self.edge_padding = 0
        self.title_horizontal_padding = 8
        self.title_vertical_padding = 10

    def initAssets(self) -> None:
        super().initAssets()
        self.icons = self.rsm.get('status_icons')

    def paint(self, painter: Optional[QPainter], option: Optional[QStyleOptionGraphicsItem],
              widget: Optional[QWidget] = None) -> None:

        if painter is None:
            return

        # Draw the border first
        path_outline = self.shape()  # Get the shape path
        painter.setPen(self._pen)
        painter.drawPath(path_outline)

        # Draw node content
        super().paint(painter, option, widget)

        offset = 24.0
        if self.node.isDirty():
            offset = 0.0
        if self.node.isInvalid():
            offset = 48.0

        # Calculate the position for bottom center
        icon_width = 24.0
        icon_x = (self.width - icon_width) / 2
        icon_y = self.height - 12  # 5 pixels padding from the bottom

        painter.drawImage(
            QRectF(icon_x, icon_y, 24.0, 24.0),
            self.icons,
            QRectF(offset, 0, 24.0, 24.0)
        )

    def setPenExecuting(self) -> None:
        """Set node border to purple while executing"""
        self._pen = self._executing_pen
        self.update()

    def setPenExecuted(self) -> None:
        """Set node border to green after execution"""
        self._pen = self._executed_pen
        self.update()

    def resetPen(self) -> None:
        """Reset to default border color"""
        self._pen = self._default_pen
        self.update()


class TriggerContent(QDMNodeIconContentWidget):
    # _node: 'TriggerNode'  # Define the actual storage

    def initUI(self, icon: Optional[QPixmap] = None) -> Any:
        lbl = QLabel(self.node.content_label, self)  # type: ignore
        lbl.setObjectName(self.node.content_label_objname)  # type: ignore


class TriggerChangeHandler:
    def __init__(self, scene: 'Scene') -> None:
        self._scene = scene
        self._input_widgets: list = []

    # @property
    # def node(self) -> 'TriggerNode':
    #     return self.node

    def registerInputWidget(self, widget: QWidget) -> None:
        """Register a single input widget for change tracking"""
        if widget in self._input_widgets:
            return

        if hasattr(widget, 'textChanged'):
            widget.textChanged.connect(self.onInputChanged)
        elif hasattr(widget, 'valueChanged'):
            widget.valueChanged.connect(self.onInputChanged)
        elif hasattr(widget, 'currentTextChanged'):
            widget.currentTextChanged.connect(self.onInputChanged)
        elif hasattr(widget, 'stateChanged'):
            widget.stateChanged.connect(self.onInputChanged)
        elif hasattr(widget, 'dataChanged'):
            widget.dataChanged.connect(self.onInputChanged)

        self._input_widgets.append(widget)

    def is_input_widget(self, widget: QWidget) -> bool:
        """Check if a widget is an input widget"""
        input_widget_types = (QLineEdit, QSpinBox, QComboBox, QCheckBox)
        return isinstance(widget, input_widget_types)

    def recursively_find_widgets(self, layout: Optional[QLayout]) -> None:
        """Recursively find all input widgets in a parent widget"""
        # input_widgets = []
        if layout is None:
            return

        for i in range(layout.count()):
            item = layout.itemAt(i)
            if item and item.widget():
                # Found a widget
                widget = item.widget()
                if widget:
                    self.registerInputWidget(widget)
                    # Check if widget has its own layout
                    if widget.layout():
                        self.recursively_find_widgets(widget.layout())
            elif item and item.layout():
                # Found a nested layout
                self.recursively_find_widgets(item.layout())

    def onInputChanged(self, *args: list) -> None:
        """Called when any input widget changes"""
        if hasattr(self.node, 'scene'):
            self.node.scene.has_been_modified = True
            self.node.scene.history.storeHistory("Input Modified")
            # Trigger node evaluation
            # self.node.markDirty()
            # self.node.eval()

    def clearInputWidgets(self) -> None:
        """Clear all input widget connections"""
        for widget in self._input_widgets:
            if hasattr(widget, 'textChanged'):
                try:
                    widget.textChanged.disconnect(self.onInputChanged)
                except:
                    pass
            elif hasattr(widget, 'valueChanged'):
                try:
                    widget.valueChanged.disconnect(self.onInputChanged)
                except:
                    pass
            elif hasattr(widget, 'currentTextChanged'):
                try:
                    widget.currentTextChanged.disconnect(self.onInputChanged)
                except:
                    pass
            elif hasattr(widget, 'stateChanged'):
                try:
                    widget.stateChanged.disconnect(self.onInputChanged)
                except:
                    pass
            elif hasattr(widget, 'dataChanged'):
                try:
                    widget.dataChanged.disconnect(self.onInputChanged)
                except:
                    pass
        self._input_widgets.clear()


class TriggerNode(Node):
    icon: str = ""
    node_code: int = 0
    node_title: str = "Undefined"
    node_type: str = ""
    content_label: str = ""
    content_label_objname: str = "calc_node_bg"
    style: dict[str, str] = {
        'brush_color': "#000000"
    }

    # Explicitly define types for Node classes
    GraphicsNode_class: TriggerGraphicsNode = TriggerGraphicsNode  # type: ignore
    NodeContent_class: TriggerContent = TriggerContent  # type: ignore
    rsm: ResourceManager = ResourceManager()

    # evaluationRequested = Signal()

    def __init__(self, scene: 'Scene', inputs: List[int] = [2, 2], outputs: List[int] = [1]) -> None:
        super().__init__(scene, self.__class__.node_title, inputs, outputs)

        self.value: Optional[Any] = None

        # it's really important to mark all nodes Dirty by default
        self.markDirty()

    def initSettings(self) -> None:
        super().initSettings()
        self.input_socket_position = LEFT_CENTER
        self.output_socket_position = RIGHT_CENTER
        # self.evaluationRequested.connect(self.onInputChanged)

    def getSocketValue(self, socket_list: list['Socket'], target_node: 'TriggerNode') -> int:
        """Get value based on socket connection"""
        socket_index = 0
        for i, socket in enumerate(socket_list):
            if socket.edges:
                for edge in socket.edges:
                    if edge.getOtherSocket(socket).node == target_node:
                        socket_index = i
                        break
        return socket_index

    def evalOperation(self, input1: Any, input2: Any) -> int:
        return 123

    def processInputs(self, input_values: list[Any]) -> Optional[Any]:
        # Override this method in subclasses to process the input values
        return input_values

    def evalImplementation(self) -> Any:
        input_values = []
        for i in range(len(self.inputs)):
            input_node = self.getInput(i)
            if not input_node:
                self.markInvalid()
                self.markDescendantsDirty()
                self.grNode.setToolTip(f"Input {i} is not connected")
                return None

            val = input_node.eval()
            if val is None:
                self.markInvalid()
                self.markDescendantsDirty()
                self.grNode.setToolTip(f"Input {i} is NaN")
                return None

            input_values.append(val)

        result = self.processInputs(input_values)
        if result is None:
            self.markInvalid()
            self.markDescendantsDirty()
            self.grNode.setToolTip("Invalid operation")
            return None

        self.value = result
        self.markInvalid(False)
        self.markDirty(False)
        self.grNode.setToolTip("")
        self.evalChildren()
        return self.value

    # Uncomment if you want to use the default evalImplementation for calculator application
    # def evalImplementation(self):
    #     i1 = self.getInput(0)
    #     i2 = self.getInput(1)

    #     if i1 is None or i2 is None:
    #         self.markInvalid()
    #         self.markDescendantsDirty()
    #         self.grNode.setToolTip("Connect all inputs")
    #         return None

    #     else:
    #         val = self.evalOperation(i1.eval(), i2.eval())
    #         self.value = val
    #         self.markDirty(False)
    #         self.markInvalid(False)
    #         self.grNode.setToolTip("")

    #         self.markDescendantsDirty()
    #         self.evalChildren()

    #         return val

    def eval(self, index: Any = None) -> Any:
        if not self.isDirty() and not self.isInvalid():
            print(" _> returning cached %s value:" %
                  self.__class__.__name__)
            return self.value
        try:
            val = self.evalImplementation()
            return val
        except ValueError as e:
            self.markInvalid()
            self.grNode.setToolTip(str(e))
            self.markDescendantsDirty()
        except Exception as e:
            self.markInvalid()
            self.grNode.setToolTip(str(e))
            dumpException(e)
            return None  # Add explicit return for exception case

    def onEdgeConnectionChanged(self, new_edge: 'Edge') -> None:
        # print("%s::__onEdgeConnectionChanged" % self.__class__.__name__)
        self.markDirty()
        self.eval()

    def onInputChanged(self, socket: Optional['Socket'] = None) -> None:
        print("🟡%s::__onInputChanged" % self.__class__.__name__)
        self.markDirty()
        self.markChildrenDirty()
        self.eval()

    def serialize(self) -> OrderedDict:
        res = super().serialize()
        res['node_code'] = self.__class__.node_code
        res['node_type'] = self.__class__.node_type
        return res

    def deserialize(self, data: dict, hashmap: dict = {}, restore_id: bool = True) -> bool:
        res = super().deserialize(data, hashmap, restore_id)
        # print("Deserialized CalcNode '%s'" %
        #       self.__class__.__name__, "res:", res)
        return res
