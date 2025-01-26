from qtpy.QtWidgets import QLineEdit, QLayout, QVBoxLayout, QListWidget, QListWidgetItem
from qtpy.QtCore import Qt
from trigger_conf import register_node, OP_NODE_INPUT,  OP_NODE_SELECT
from trigger_node_base import TriggerNode, TriggerGraphicsNode
from nodeeditor.node_content_widget import QDMNodeContentWidget
from nodeeditor.utils import dumpException
from trigger_node_config_dock import ConfigDock


class SelectContent(QDMNodeContentWidget):
    def initUI(self):
        self.selected_columns = ['Seed']
        # self.selected_columns = []
        # self.edit = QLineEdit("1", self)
        # self.edit.setAlignment(Qt.AlignRight)
        # self.edit.setObjectName(self.node.content_label_objname)

    def create_layout(self) -> QLayout:
        self.list_widget = QListWidget(self)

        self.set_list_widget()
        layout = QVBoxLayout()
        layout.addWidget(self.list_widget)
        return layout

    def set_list_widget(self):
        self.list_widget.clear()
        for column in self.selected_columns:
            item = QListWidgetItem(column)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.list_widget.addItem(item)

    def serialize(self):
        res = super().serialize()
        res['selected_columns'] = self.selected_columns
        return res

    def deserialize(self, data, hashmap={}):
        res = super().deserialize(data, hashmap)
        try:
            self.selected_columns = data['selected_columns']
            return True & res
        except Exception as e:
            dumpException(e)
        return res


@register_node(OP_NODE_SELECT)
class TriggerNode_Select(TriggerNode):
    icon = "icons/in.png"
    op_code = OP_NODE_SELECT
    op_title = "Select"
    content_label_objname = "trigger_node_select"

    def __init__(self, scene):
        super().__init__(scene, inputs=[1], outputs=[1])
        # self.eval()

    def initInnerClasses(self):
        self.content = SelectContent(self)
        self.grNode = TriggerGraphicsNode(self)
        # self.content.edit.textChanged.connect(self.onInputChanged)

    # def evalImplementation(self):

    #     u_value = self.content.edit.text()
    #     s_value = int(u_value)
    #     self.value = s_value
    #     self.markDirty(False)
    #     self.markInvalid(False)

    #     self.markDescendantsInvalid(False)
    #     self.markDescendantsDirty()

    #     self.grNode.setToolTip("")

    #     self.evalChildren()

    #     return self.value
