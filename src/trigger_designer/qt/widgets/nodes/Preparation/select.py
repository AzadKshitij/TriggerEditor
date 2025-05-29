import pandas as pd
from qtpy.QtWidgets import (QWidget, QLineEdit, QLayout, QVBoxLayout, QListWidget, QLabel, QTableView,
                            QListWidgetItem, QTableWidget, QTableWidgetItem, QCheckBox, QComboBox, QHeaderView, QPushButton)
from qtpy.QtGui import QPixmap
from qtpy.QtCore import Qt, QSaveFile, Signal, QVariant, QModelIndex
from trigger_designer.core.node_configuration import register_node, PreparationNodes, NodeTypes
from trigger_designer.qt.node_base import TriggerChangeHandler, TriggerNode, TriggerGraphicsNode
from nodeeditor.node_content_widget import QDMNodeContentWidget
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget
from nodeeditor.utils import dumpException

from trigger_designer.qt.widgets.select_table_widget import ComboBoxDelegate, SelectTableWidget, RowData
from typing import Optional, TYPE_CHECKING, Any, Dict, List, OrderedDict, Type, cast, Union

if TYPE_CHECKING:
    from nodeeditor.node_scene import Scene
    from nodeeditor.node_node import Node
    import pandas as pd


class SelectContent(QDMNodeIconContentWidget, TriggerChangeHandler):
    """DataFrame column selection and modification widget.

    Provides comprehensive column management including:
    - Selection and filtering
    - Reordering and sorting
    - Type conversion and renaming
    - Metadata management

    Args:
        QDMNodeContentWidget (_type_): _description_

    Variables:
        columns (dict): {column_name: [is_selected, column_type, rename]}
        incoming_columns (list): [column_name]

    Extra: 

    """

    evaluate = Signal()  # Emit when evaluate button is clicked

    def __init__(self, node: 'TriggerNode', parent: Optional[QWidget] = None) -> None:
        super().__init__(node, parent)
        # local variables
        # self.old_data: dict = []
        self.table_data: list = []
        self.history = self.node.scene.history

        # incoming variables
        self.incoming_variable: str = ''
        self.incom_data: Optional[pd.DataFrame] = None

        # pass on variables
        self.data: Optional[pd.DataFrame] = None
        self.variable_name: str = f'var_select_{self.id}'

    @property
    def node(self) -> 'TriggerNode':
        return self._node

    @node.setter
    def node(self, value: 'TriggerNode') -> None:
        self._node = value

    def initUI(self, icon: Optional[QPixmap] = None) -> None:
        _icon: QPixmap = self.node.rsm.get(f"{self.node.icon}")
        super().initUI(_icon)

    def create_layout(self, dock_layout: QVBoxLayout) -> None:
        if self.incom_data is not None:
            if not self.table_data:
                self.table_data = [
                    RowData(True, col, self.incom_data[col].dtype.name)
                    for col in self.incom_data.columns
                ]
            # if self.old_data != {}:
            #     self.old_data = table_data
            # Initialize changes if not already present
            if not hasattr(self, 'changes'):
                self.changes: dict = {
                    'selected_columns': [],
                    'rename_mapping': {},
                    'dtype_mapping': {}
                }
            self.table_view = QTableView()
            # Create some sample data
            self.table_widget = SelectTableWidget(
                data=self.table_data, changes=self.changes, parent=self)
            # Set the custom delegate for the 'Option' column (index 2)
            self.table_view.setItemDelegateForColumn(
                2, ComboBoxDelegate(self.table_view))
            self.table_view.setModel(self.table_widget)
            self.table_widget.dataChanged.connect(self.handleDataChanged)
            dock_layout.addWidget(self.table_view)
        else:
            no_data_label = QLabel("No incoming data available")
            no_data_label.setAlignment(Qt.AlignCenter)
            no_data_label.setStyleSheet("color: gray;")
            dock_layout.addWidget(no_data_label)

        # return layout

    def apply_changes(self) -> None:
        """Apply changes from self.changes to self.data"""
        # Select only the specified columns from incom_data
        if getattr(self, 'changes', None) is not None:
            selected_columns = self.changes['selected_columns']
            self.data = self.incom_data[selected_columns].copy()

            # Apply data type changes if any
            for col, dtype in self.changes['dtype_mapping'].items():
                try:
                    if dtype in ['int64', 'int32', 'float64', 'float32']:
                        self.data[col] = pd.to_numeric(
                            self.data[col], errors='coerce')
                    self.data[col] = self.data[col].astype(
                        dtype, errors='ignore')
                except Exception as e:
                    print(
                        f"Failed to convert column {col} to {dtype}: {str(e)}")

            # Apply renaming if any
            if self.changes['rename_mapping']:
                rename_dict = self.changes['rename_mapping']
                self.data.rename(columns=rename_dict, inplace=True)

            print(
                "🐍 File: Preparation/select.py | Line: 279 | processInputs ~ self._is_invalid", self.node._is_invalid)

    def process_data_changes(self, data_: list[list]) -> Dict[str, Any]:
        # Store the changes in a serializable format
        self.changes = {
            'selected_columns': [],
            'rename_mapping': {},
            'dtype_mapping': {},
            'column_order': []  # Add column order tracking
        }

        # Get column order from table widget
        # if hasattr(self, 'table_widget'):
        #     header = self.table_widget..horizontalHeader()
        #     self.changes['column_order'] = [
        #         header.logicalIndex(i)
        #         for i in range(header.count())
        #     ]

        # Extract selected columns, their new names and data types
        for column_info in data_:
            column_name, data_type, new_name = column_info
            self.changes['selected_columns'].append(column_name)

            if new_name:
                self.changes['rename_mapping'][column_name] = new_name

            if data_type:
                self.changes['dtype_mapping'][column_name] = data_type

        return (self.changes['selected_columns'],
                self.changes['rename_mapping'],
                self.changes['dtype_mapping'])

    def update_data_dtype(self, selected_columns: list[str], rename_mapping: dict, dtype_mapping: dict) -> None:
        """Update self.data based on the processed changes"""
        # Select only the specified columns from incom_data
        self.data = self.incom_data[selected_columns].copy()

        # Apply data type changes if any
        for col, dtype in dtype_mapping.items():
            try:
                if dtype in ['int64', 'int32', 'float64', 'float32']:
                    self.data[col] = pd.to_numeric(
                        self.data[col], errors='coerce')
                self.data[col] = self.data[col].astype(dtype, errors='ignore')
            except Exception as e:
                print(f"Failed to convert column {col} to {dtype}: {str(e)}")

        # Apply renaming if any
        if rename_mapping:
            self.data.rename(columns=rename_mapping, inplace=True)

    def handleDataChanged(self, data_: list[list]) -> None:
        if self.history.is_restoring_history:
            return

        # Store old state before changes
        old_changes = {
            'selected_columns': self.changes['selected_columns'].copy() if hasattr(self, 'changes') else [],
            'rename_mapping': self.changes['rename_mapping'].copy() if hasattr(self, 'changes') else {},
            'dtype_mapping': self.changes['dtype_mapping'].copy() if hasattr(self, 'changes') else {}
        }

        # Process the new changes
        self.process_data_changes(data_)
        self.apply_changes()

        # Store history only if there are actual changes
        if old_changes != self.changes:
            history_data = {
                'node': self.node,
                'old_changes': old_changes,
                'new_changes': {
                    'selected_columns': self.changes['selected_columns'].copy(),
                    'rename_mapping': self.changes['rename_mapping'].copy(),
                    'dtype_mapping': self.changes['dtype_mapping'].copy()
                }
            }

            self.history.storeHistory(
                desc="Column Selection/Rename/Type Changed",
                data=history_data,
                setModified=True
            )

        # self.node.scene.has_been_modified = True
        # self.node.scene.history.storeHistory("Input Modified")

        # self.process_data_changes(
        #     data_)
        # self.apply_changes()

        self.evaluate.emit()

    def history_stamp_callback(self, history_data: dict, is_undo: bool) -> None:
        """Callback for undo/redo operations"""
        if is_undo:
            # Undo operation
            self.changes = history_data['old_changes']
        else:
            # Redo operation
            self.changes = history_data['new_changes']

        # Apply the changes and update the table
        self.apply_changes()
        if hasattr(self, 'table_widget'):
            self.table_widget.update_from_changes(self.changes)

    def get_code(self) -> str:
        if self.data is None or self.incoming_variable is None:
            return ""

        code_lines = []

        # Get selected columns using the stored changes
        selected_columns = [
            f"'{col}'" for col in self.changes['selected_columns']]
        columns_str = ', '.join(selected_columns)
        code_lines.append(
            f"{self.variable_name} = {self.incoming_variable}[[{columns_str}]].copy()")

        # Apply data type changes from stored changes
        for col, dtype in self.changes['dtype_mapping'].items():
            if dtype in ['int64', 'int32', 'float64', 'float32']:
                code_lines.append(
                    f"{self.variable_name}['{col}'] = pd.to_numeric({self.variable_name}['{col}'], errors='coerce')")
            code_lines.append(
                f"{self.variable_name}['{col}'] = {self.variable_name}['{col}'].astype('{dtype}', errors='ignore')")

        # Apply column renaming from stored changes
        if self.changes['rename_mapping']:
            rename_str = ', '.join([f"'{old}': '{new}'"
                                    for old, new in self.changes['rename_mapping'].items()])
            code_lines.append(
                f"{self.variable_name}.rename(columns={{{rename_str}}}, inplace=True)")

        return '\n'.join(code_lines) + '\n'

    def serialize(self):
        res = super().serialize()
        res['table_data'] = self.table_data
        res['changes'] = getattr(self, 'changes', {
            'selected_columns': [],
            'rename_mapping': {},
            'dtype_mapping': {}
        })
        return res

    def deserialize(self, data, hashmap={}):
        res = super().deserialize(data, hashmap)
        try:
            print("deserialize Select node")
            self.old_columns = data['table_data']
            self.changes = data['changes']
            return True & res
        except Exception as e:
            dumpException(e)
        return res


@register_node(PreparationNodes.SELECT, NodeTypes.PREPARATION)
class TriggerNode_Select(TriggerNode):
    icon = "node_select"
    node_code = PreparationNodes.SELECT
    node_title = "Select"
    node_type = NodeTypes.PREPARATION
    content_label_objname = "trigger_node_select"
    style = {}

    def __init__(self, scene) -> None:
        super().__init__(scene, inputs=[1], outputs=[3])
        self.eval()

    def initInnerClasses(self) -> None:
        self.content: SelectContent = SelectContent(self)
        self.grNode = TriggerGraphicsNode(self)
        self.content.evaluate.connect(self.onInputChanged)

    def processInputs(self, input_values):
        print("⚠️⚠️⚠️ Select ⚠️⚠️⚠️")
        input_node = self.getInput(0)
        socket_index = self.getSocketValue(input_node.outputs, self)
        input_value = input_values[0][socket_index]
        # print("🐍 File: Preparation/select.py | Line: 322 | processInputs ~ input_value.get('data')",
        #       input_value.get('data'))

        if input_value:
            print("We have input")
            self.markDirty(False)
            print("1")
            self.markInvalid(False)
            print("2")
            # Custom processing logic for the Select node
            self.content.incom_data = input_value.get('data')
            print("3")
            self.content.incoming_variable = input_value.get('variable_name')
            print("4")
            # self.content.set_table_data()
            print("5")
            self.content.apply_changes()
            print("6")
            # self.content.set_table_widget()

            param = [{
                "data": self.content.data,
                "variable_name": self.content.variable_name
            }]
            self.evalChildren()
            print(
                "🐍 File: Preparation/select.py | Line: 279 | processInputs ~ self._is_invalid", self._is_invalid)

            return param
        else:
            print("We don't have input")
            self.markDirty(True)
            self.markInvalid(True)
            self.grNode.setToolTip("Input is not connected")
            print(
                "🐍 File: Preparation/select.py | Line: 292 | processInputs ~ self._is_invalid", self._is_invalid)

            return None

    def get_code(self):
        return self.content.get_code()
