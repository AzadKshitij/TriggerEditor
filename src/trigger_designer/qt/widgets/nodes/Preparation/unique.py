import pprint
from qtpy.QtWidgets import (QWidget, QLineEdit, QPushButton, QFileDialog, QVBoxLayout, QTextEdit, QTableWidget,
                            QTableWidgetItem, QHeaderView, QLayout, QComboBox, QLineEdit, QLabel, QHBoxLayout, QListWidget, QListWidgetItem)
from qtpy.QtGui import QPixmap
from qtpy.QtCore import Qt, Signal
from trigger_designer.core.node_configuration import register_node, PreparationNodes, NodeTypes
from trigger_designer.qt.node_base import TriggerChangeHandler, TriggerNode, TriggerGraphicsNode
from nodeeditor.node_content_widget import QDMNodeContentWidget
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget
from nodeeditor.utils import dumpException
from nodeeditor.node_scene_history import SceneHistory
from nodeeditor.node_scene import Scene
import pandas as pd
from typing import Optional


class UniqueContent(QDMNodeIconContentWidget, TriggerChangeHandler):

    evaluate = Signal()  # Emit when evaluate button is clicked

    def __init__(self, node, parent: Optional[QWidget] = None) -> None:
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

    def initUI(self, parent: Optional[QWidget] = None) -> None:
        icon: QPixmap | None = self.node.rsm.get(f"{self.node.icon}")
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

    def update_column_list(self) -> None:
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

    def on_item_changed(self, item) -> None:
        """Handle checkbox state changes"""
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

            self.history.storeHistory(
                desc=f"Column '{item.text()}' Selection Changed",
                data=history_data,
                setModified=True
            )
        self.handle_data_changed()

    def history_stamp_callback(self, history_data, is_undo: bool) -> None:
        """Callback for undo/redo operations"""
        try:
            self.history.is_restoring_history = True
            if is_undo:
                # Undo operation
                self.selected_columns = history_data['old_selected_columns']
            else:
                # Redo operation
                self.selected_columns = history_data['new_selected_columns']

            # Update UI elements
            if hasattr(self, 'column_list'):
                try:
                    self.column_list.blockSignals(True)
                    self.update_column_list()
                finally:
                    self.column_list.blockSignals(False)
            # Update data
            self.handle_data_changed()

        finally:
            self.history.is_restoring_history = False

    def get_selected_columns(self):
        """Get list of selected column names"""
        selected_columns = []
        for index in range(self.column_list.count()):
            item = self.column_list.item(index)
            if item.checkState() == Qt.Checked:
                selected_columns.append(item.text())
        return selected_columns

    def handle_data_changed(self) -> None:
        self.data = self.incom_data.copy()
        self.data = self.data[self.selected_columns]

    def get_code(self):
        if not self.selected_columns:
            return ""

        selected_columns_str = [f"'{col}'" for col in self.selected_columns]
        selected_columns_str = ", ".join(selected_columns_str)
        code_lines = []

        # Add import statement
        code_lines.append("import pandas as pd")
        code_lines.append(f"df = {self.incoming_variable}")

        # Add code to find unique values
        code_lines.append(
            f"unique_df = df.drop_duplicates(subset=[{selected_columns_str}])")

        # Register the resulting DataFrame
        code_lines.append(f"{self.variable_name} = unique_df")

        return '\n'.join(code_lines) + '\n'

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


@register_node(PreparationNodes.UNIQUE, NodeTypes.PREPARATION)
class TriggerNode_Unique(TriggerNode):
    icon = 'node_unique'
    node_code = PreparationNodes.UNIQUE
    node_type = NodeTypes.PREPARATION
    node_title = "Unique"
    content_label_objname = "trigger_node_unique"
    style = {}

    def __init__(self, scene: 'Scene') -> None:
        super().__init__(scene, inputs=[1], outputs=[3])
        # self.eval()

    def initInnerClasses(self) -> None:
        self.content: UniqueContent = UniqueContent(self)
        self.grNode: TriggerGraphicsNode = TriggerGraphicsNode(self)
        self.content.evaluate.connect(self.onInputChanged)

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
            return [None]

    def get_code(self):
        return self.content.get_code()
