from qtpy.QtWidgets import QLineEdit, QLayout, QVBoxLayout, QLabel
from qtpy.QtCore import Qt
from qtpy.QtGui import QPixmap
from trigger_designer.core.node_configuration import register_node, NodeTypes, CalcNodes
from trigger_designer.qt.node_base import TriggerNode, TriggerGraphicsNode
from nodeeditor.node_content_widget import QDMNodeContentWidget
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget
from nodeeditor.utils import dumpException
from trigger_designer.qt.docks.node_config import ConfigDock


class CalcInputContent(QDMNodeIconContentWidget):
    # def __init__(self, node, parent=None):
    #     self.icon = QPixmap("src/trigger_designer/Resource/icons/Input/File Output.png")
    #     print("Input Icon icon: ", self.icon)
    #     super().__init__(node, parent)
    def initUI(self) -> None:
        icon = QPixmap("src/trigger_designer/Resource/icons/Input/File Output.png")
        # icon = QPixmap(
        #     "src/trigger_designer/Resource/icons/Input/File Output.png")
        super().initUI(icon)

    def create_layout(self) -> QLayout:
        layout = QVBoxLayout()
        return layout

    def serialize(self):
        res = super().serialize()
        # res['value'] = self.edit.text()
        return res

    def deserialize(self, data, hashmap={}):
        res = super().deserialize(data, hashmap)
        try:
            value = data["value"]
            # self.edit.setText(value)
            return True & res
        except Exception as e:
            dumpException(e)
        return res


@register_node(CalcNodes.INPUT, NodeTypes.CALC)
class CalcNode_Input(TriggerNode):
    icon = ":/IO/qt/images/node_icons/Input/Browse.svg"
    node_code = CalcNodes.INPUT
    node_title = "Input"
    node_type = NodeTypes.CALC
    content_label_objname = "calc_node_input"

    def __init__(self, scene) -> None:
        super().__init__(scene, inputs=[], outputs=[3])
        self.eval()

    def initInnerClasses(self) -> None:
        self.content = CalcInputContent(self)
        self.grNode = TriggerGraphicsNode(self)
        # self.content.edit.textChanged.connect(self.onInputChanged)

    def evalImplementation(self):
        print("#############")
        print("Input evalImplementation")
        print("#############")
        u_value = 0
        # u_value = self.content.edit.text()
        s_value = int(u_value)
        self.value = s_value
        self.markDirty(False)
        self.markInvalid(False)

        self.markDescendantsInvalid(False)
        self.markDescendantsDirty()

        self.grNode.setToolTip("")

        self.evalChildren()

        return self.value

    def execute(self, node_input) -> None:
        print("Input")
        print(node_input)
