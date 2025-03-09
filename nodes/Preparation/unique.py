import pprint
from qtpy.QtWidgets import (QLineEdit, QPushButton, QFileDialog, QVBoxLayout, QTextEdit, QTableWidget,
                            QTableWidgetItem, QHeaderView, QLayout, QComboBox, QLineEdit, QLabel, QHBoxLayout, QListWidget, QListWidgetItem)
from qtpy.QtGui import QPixmap
from qtpy.QtCore import Qt, Signal
from trigger_conf import OP_NODE_UNIQUE, register_node, OP_NODE_FILE_INPUT
from trigger_node_base import TriggerChangeHandler, TriggerNode, TriggerGraphicsNode
from nodeeditor.node_content_widget import QDMNodeContentWidget
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget
from nodeeditor.utils import dumpException
from nodeeditor.node_scene_history import SceneHistory
import pandas as pd
from themes.theme import Theme

theme = Theme()


class UniqueContent(QDMNodeIconContentWidget, TriggerChangeHandler):

    evaluate = Signal()  # Emit when evaluate button is clicked

    def __init__(self, node, parent=None):
        super().__init__(node, parent)
        # local variables
        self.selected_columns = []
        self.history: SceneHistory = self.node.scene.history

        TriggerChangeHandler.__init__(self, self.node.scene)

        # incoming variables
        self.incoming_variable: str = ''
        self.incom_data: pd.DataFrame = None

        # pass on variables
        self.data = []
        self.variable_name = f'var_union_{self.id}'

    def initUI(self, parent=None):
        icon = QPixmap('Resource/icons/Preparation/Unique.png')
        super().initUI(icon)

    def create_layout(self, dock_layout: QVBoxLayout) -> QLayout:
        header_label = QLabel("Unique")
        header_label.setObjectName("header_label")

        title_label = QLabel("Select columns to find unique values")
        title_label.setObjectName("title_label")

        # Column list box
        self.column_list = QListWidget()
        self.column_list.setObjectName("column_list")
        self.column_list.setSelectionMode(QListWidget.MultiSelection)
        self.column_list.itemChanged.connect(self.on_item_changed)
        # self.column_list.itemSelectionChanged.connect(self.on_item_changed)
        self.update_column_list()
        # self.column_list.itemSelectionChanged.connect(self.on_column_list_changed)

        dock_layout.addWidget(header_label)
        dock_layout.addWidget(title_label)
        dock_layout.addWidget(self.column_list)
        # self.recursively_find_widgets(dock_layout)
        # return layout

    def update_column_list(self):
        """Update the column list when input data changes"""
        self.column_list.clear()
        if self.incom_data is not None:
            for column in self.incom_data.columns:
                item = QListWidgetItem(column)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                # Check if column was previously selected
                if column in self.selected_columns:
                    item.setCheckState(Qt.Checked)
                else:
                    item.setCheckState(Qt.Unchecked)

                self.column_list.addItem(item)

    def on_item_changed(self, item):
        """Handle checkbox state changes"""
        # self.node.scene.has_been_modified = True
        # self.node.scene.history.storeHistory("Input Modified")
        # self.registerInputWidget(item)

        # Prevent storing history during restoration
        if self.history.is_restoring_history:
            return

        old_selected_columns = self.selected_columns.copy()

        if item.checkState() == Qt.Checked:
            if item.text() not in self.selected_columns:
                self.selected_columns.append(item.text())
        else:
            if item.text() in self.selected_columns:
                self.selected_columns.remove(item.text())

        if old_selected_columns != self.selected_columns:
            history_data = {
                'node': self.node,
                'old_selected_columns': old_selected_columns,
                'new_selected_columns': self.selected_columns.copy()
            }
            # print("")
            # print(
            #     "🐍 File: Preparation/unique.py | Line: 98 | on_item_changed ~ history_data")
            # pprint.pp(history_data)
            # print("")

            # Force scene to be active
            # self.node.scene.setFocus()

            self.history.storeHistory(
                desc=f"Column '{item.text()}' Selection Changed",
                data=history_data,
                setModified=True
            )
            # print("🐍 File: Preparation/unique.py | Line: 116 | on_item_changed ~ self.node.scene.history.history_stack",
            #       self.node.scene.history.history_stack[-1])

    def history_stamp_callback(self, history_data, is_undo):
        """Callback for undo/redo operations"""
        # print("🐍 File: Preparation/unique.py | Line: 100 | on_item_changed ~ history_data")
        # pprint.pp(history_data)

        if is_undo:
            # Undo operation
            self.selected_columns = history_data['old_selected_columns']
        else:
            # Redo operation
            self.selected_columns = history_data['new_selected_columns']
        self.update_column_list()

        # get selected node
        # selection = self.node.scene.getSelectedItems()
        # if len(selection) == 1 and self == selection[0].content:
        # Update UI to reflect changes
        # self.update_column_list()

        # Process data with new selection
        # if node.content.incom_data is not None and node.content.selected_columns:
        #     node.content.data = node.content.incom_data[node.content.selected_columns].drop_duplicates(
        #     )
        #     node.content.evaluate.emit()

        # Update UI to reflect changes
        # self.update_column_list()

        # Process data with new selection
        # if node.content.incom_data is not None and node.content.selected_columns:
        #     node.content.data = node.content.incom_data[node.content.selected_columns].drop_duplicates(
        #     )
        #     node.content.evaluate.emit()

    def get_selected_columns(self):
        """Get list of selected column names"""
        selected_columns = []
        for index in range(self.column_list.count()):
            item = self.column_list.item(index)
            if item.checkState() == Qt.Checked:
                selected_columns.append(item.text())
        return selected_columns

    def get_code(self):
        return f"print('New Node')"

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


@register_node(OP_NODE_UNIQUE, 'PREPARATION')
class TriggerNode_Unique(TriggerNode):
    icon = 'Resource/icons/Preparation/Unique.png'
    op_code = OP_NODE_UNIQUE
    op_type = 'PREPARATION'
    op_title = "Unique"
    content_label_objname = "trigger_node_unique"
    style = {
        'brush_color': theme.brush_color('PREPARATION')
    }

    def __init__(self, scene):
        super().__init__(scene, inputs=[1], outputs=[3])
        # self.eval()

    def initInnerClasses(self):
        self.content = UniqueContent(self)
        self.grNode = TriggerGraphicsNode(self)

    def processInputs(self, input_values):
        this_socket_index = 0
        input_node = self.getInput(this_socket_index)
        socket_index = self.getSocketValue(input_node.outputs, self)
        input_value = input_values[this_socket_index][socket_index]

        if input_value:
            self.markDirty(False)
            self.markInvalid(False)
            # Custom processing logic for the Select node
            self.content.incom_data = input_value.get('data')
            self.content.incoming_variable = input_value.get('variable_name')
            self.evalChildren()
            return [{
                'data': self.content.data,
                'variable_name': self.content.variable_name
            }]
        # variable = self.content.variable_name
        else:
            self.markDirty(True)
            self.markInvalid(True)
            self.grNode.setToolTip('Input is not connected')

    def get_code(self):
        return self.content.get_code()
