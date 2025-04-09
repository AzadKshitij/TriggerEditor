from qtpy.QtWidgets import QWidget, QLineEdit, QPushButton, QFileDialog, QVBoxLayout, QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView, QLayout, QComboBox, QLineEdit, QLabel, QHBoxLayout
from qtpy.QtGui import QPixmap
from qtpy.QtCore import Qt, Signal
from trigger_designer.core.node_configuration import register_node, PreparationNodes, NodeTypes
from trigger_designer.qt.node_base import TriggerChangeHandler, TriggerNode, TriggerGraphicsNode
from nodeeditor.node_content_widget import QDMNodeContentWidget
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget
from nodeeditor.utils import dumpException
import pandas as pd
from typing import Optional, TYPE_CHECKING, Any, Dict, List, OrderedDict, Type, cast, Union

if TYPE_CHECKING:
    from nodeeditor.node_scene import Scene
    import pandas as pd
    from nodeeditor.node_node import Node


class FormulaContent(QDMNodeIconContentWidget, TriggerChangeHandler):

    evaluate = Signal()  # Emit when evaluate button is clicked

    def __init__(self, node: 'TriggerNode', parent: Optional[QWidget] = None) -> None:
        super().__init__(node, parent)
        # local variables
        self.formula: str = ''
        self.formula_text: Optional[str] = None
        self.target_column: Optional[str] = None
        self.is_new_column: bool = False
        self.history = self.node.scene.history
        TriggerChangeHandler.__init__(self, self.node.scene, self.node)

        # incoming variables
        self.incoming_variable: str = ''
        self.incom_data: Optional[pd.DataFrame] = None

        # pass on variables
        self.data: Optional[pd.DataFrame] = None
        self.variable_name = f'var_formula_{self.id}'

    @property
    def node(self) -> 'TriggerNode':
        return self._node

    @node.setter
    def node(self, value: 'TriggerNode') -> None:
        self._node = value

    def initUI(self, icon: Optional[QPixmap] = None) -> None:
        icon: QPixmap = self.node.rsm.get(f"{self.node.icon}")
        super().initUI(icon)

    def create_layout(self, dock_layout: QVBoxLayout) -> None:
        if self.incom_data is None:
            no_data_label = QLabel("No incoming data available")
            no_data_label.setAlignment(Qt.AlignCenter)
            no_data_label.setStyleSheet("color: gray;")
            dock_layout.addWidget(no_data_label)
        # return layout
        else:
            # Column selection
            column_layout = QHBoxLayout()
            self.column_name = QComboBox()
            self.column_name.setEditable(False)  # Initially not editable

            # Add items to combo box
            items = []
            if self.target_column and self.target_column not in self.incom_data.columns:
                items.append(self.target_column)
            items.append("+ add column")
            items.extend(list(self.incom_data.columns))
            self.column_name.addItems(items)

            if self.target_column:
                index = self.column_name.findText(self.target_column)
                if index >= 0:
                    self.column_name.setCurrentIndex(index)
            else:
                # Select "+ add column" by default
                index = self.column_name.findText("+ add column")
                if index >= 0:
                    self.column_name.setCurrentIndex(index)

            column_layout.addWidget(QLabel("Target:"))
            column_layout.addWidget(self.column_name)

            # Formula input with multiline support
            formula_layout = QVBoxLayout()
            self.formula_input = QTextEdit()
            self.formula_input.setPlaceholderText(
                "Enter formula e.g.:\nCASE WHEN [Age] > 30 then 'Adult' else 'Young'")
            self.formula_input.setMinimumHeight(100)
            if self.formula_text:
                self.formula_input.setPlainText(self.formula_text)

            formula_layout.addWidget(QLabel("Formula:"))
            formula_layout.addWidget(self.formula_input)

            # Connect the activation signal
            self.column_name.activated.connect(self.handle_column_activation)
            self.formula_input.textChanged.connect(self.generate_formula)

            # Add layouts
            dock_layout.addLayout(column_layout)
            dock_layout.addLayout(formula_layout)

            self.recursively_find_widgets(dock_layout)

    def handle_column_activation(self, index: int) -> None:
        print(f"handle_column_activation called with index: {index}")
        if self.history.is_restoring_history:
            return

        old_state = {
            'target_column': self.target_column,
            'formula_text': self.formula_text
        }

        current_text = self.column_name.itemText(index)

        if self.column_name.itemText(index) == "+ add column":
            self.column_name.setEditable(True)
            self.column_name.clearEditText()
            self.column_name.lineEdit().returnPressed.connect(self.handle_new_column)
        else:
            self.target_column = current_text
            self.store_history(old_state)

    def handle_new_column(self) -> None:
        if self.history.is_restoring_history:
            return

        old_state = {
            'target_column': self.target_column,
            'formula_text': self.formula_text
        }

        new_column = self.column_name.currentText().strip()
        if new_column and new_column != "+ add column" and new_column not in self.incom_data.columns:
            # # Clear existing items
            # self.column_name.clear()
            # # Add the new column and the "+" button
            # self.column_name.addItem(new_column)
            # # Add back original columns
            # self.column_name.addItems(self.incom_data.columns)
            # # Add the "+" button
            # self.column_name.addItem("+ add column")

            self.target_column = new_column
            self.store_history(old_state)
            self.update_column_list(new_column)
            self.handle_data_changed()

            # Select the new column
            self.column_name.setCurrentIndex(0)

        # Reset to non-editable state
        self.column_name.setEditable(False)

    def handle_data_changed(self) -> None:
        # add new column in the data
        self.data = self.incom_data.copy()
        self.data[self.target_column] = None

    def generate_formula(self) -> None:
        if self.history.is_restoring_history:
            return

        if hasattr(self, 'formula_input'):
            new_formula = self.formula_input.toPlainText()

            if new_formula != self.formula_text:
                old_state = {
                    'target_column': self.target_column,
                    'formula_text': self.formula_text
                }

                self.formula_text = new_formula
                self.store_history(old_state)

                # Update formula and data
                self.data = self.incom_data.copy()
                self.formula = self.formula_text

                # Replace column names in formula
                for col in self.data.columns:
                    self.formula = self.formula.replace(f'[{col}]', f'"{col}"')

                if self.target_column:
                    self.data[self.target_column] = None

    def store_history(self, old_state: dict) -> None:
        new_state = {
            'target_column': self.target_column,
            'formula_text': self.formula_text
        }

        if old_state != new_state:
            history_data = {
                'node': self.node,
                'old_state': old_state,
                'new_state': new_state
            }

            self.history.storeHistory(
                desc="Formula Changed",
                data=history_data,
                setModified=True
            )
            self.evaluate.emit()

    def update_column_list(self, new_column: str) -> None:
        self.column_name.clear()
        self.column_name.addItem(new_column)
        self.column_name.addItems(self.incom_data.columns)
        self.column_name.addItem("+ add column")
        self.column_name.setCurrentIndex(0)

    def history_stamp_callback(self, history_data: dict, is_undo: bool) -> None:
        """Callback for undo/redo operations"""
        try:
            self.history.is_restoring_history = True

            if is_undo:
                state = history_data['old_state']
            else:
                state = history_data['new_state']

            # Update internal state first
            self.formula_text = state['formula_text']
            self.target_column = state['target_column']

            # Update column selector
            if hasattr(self, 'column_name'):
                try:
                    self.column_name.blockSignals(True)

                    # Rebuild combo box items
                    self.column_name.clear()

                    items = []
                    # Add target column if it exists and is not in data columns
                    if self.target_column and self.target_column not in self.incom_data.columns:
                        items.append(self.target_column)

                    # Add standard items
                    items.append("+ add column")
                    items.extend(list(self.incom_data.columns))
                    self.column_name.addItems(items)

                    # Set the correct selection
                    if self.target_column:
                        index = self.column_name.findText(self.target_column)
                    else:
                        # If no target column, select "+ add column"
                        index = self.column_name.findText("+ add column")
                    if index >= 0:
                        self.column_name.setCurrentIndex(index)

                finally:
                    self.column_name.blockSignals(False)

            # Update formula input
            if hasattr(self, 'formula_input'):
                try:
                    self.formula_input.blockSignals(True)
                    if self.formula_text is not None:
                        self.formula_input.setPlainText(self.formula_text)
                finally:
                    self.formula_input.blockSignals(False)

            # Update data
            self.handle_data_changed()
            # self.generate_formula()

            self.evaluate.emit()

        finally:
            self.history.is_restoring_history = False

    def get_code(self):
        if not self.formula_text or not self.target_column:
            return ""
        print("Formula get_code: 1")
        self.generate_formula()
        print("Formula get_code: 2")

        if self.target_column in self.data.columns:
            self.is_new_column = False
        else:
            self.is_new_column = True

        code_lines = []

        # Add import statement
        code_lines.extend([
            "import duckdb",
            "duck= duckdb.connect(':memory:')",
            f"duck.register('df', {self.incoming_variable})",
            "# save original columns",
            f"original_columns = {self.incoming_variable}.columns",
            "# Apply formula to create/update column",
            f"{self.variable_name} = duck.execute('''SELECT *, {self.formula} as \"{self.target_column}\" FROM df''').fetchdf()",  # noqa
            "",
        ])
        if not self.is_new_column:
            code_lines.extend([
                "# Restore original columns",
                f"new_columns = {self.variable_name}.columns",
                f'new_column_name = list(set(new_columns) - set(original_columns))[0]',
                "# Rename it to the original column name",
                f'''{self.variable_name}['{self.target_column}'] = {self.variable_name}[new_column_name]'''
            ])

        return '\n' + '\n'.join(code_lines) + '\n'

    def serialize(self):
        res = super().serialize()
        res['formula'] = self.formula_text
        res['target_column'] = self.target_column
        return res

    def deserialize(self, data, hashmap={}):
        res = super().deserialize(data, hashmap)

        try:
            self.formula_text = data.get('formula', '')
            self.target_column = data.get('target_column', '')
            return True & res
        except Exception as e:
            dumpException(e)
        return res


@register_node(PreparationNodes.FORMULA, NodeTypes.PREPARATION)
class TriggerNode_Formula(TriggerNode):
    icon = "node_formula"
    node_code = PreparationNodes.FORMULA
    node_type = NodeTypes.PREPARATION
    node_title = "Formula"
    content_label_objname = "trigger_node_formula"
    style = {}

    def __init__(self, scene) -> None:
        super().__init__(scene, inputs=[1], outputs=[3])
        self.markInvalid(True)

    def initInnerClasses(self) -> None:
        self.content = FormulaContent(self)
        self.grNode = TriggerGraphicsNode(self)
        self.content.evaluate.connect(self.onInputChanged)

    def processInputs(self, input_values):
        # Only one input for simplicity
        this_socket_index = 0
        input_node = self.getInput(this_socket_index)
        socket_index = self.getSocketValue(input_node.outputs, self)
        input_value = input_values[this_socket_index][socket_index]

        if input_value:
            self.markDirty(False)
            self.markInvalid(False)
            # Custom processing logic for the Select node
            self.content.incom_data = input_value.get('data')
            self.content.data = input_value.get('data')
            self.content.incoming_variable = input_value.get('variable_name')
            param = [{
                'data': self.content.data,
                'variable_name': self.content.variable_name
            }]
            self.evalChildren()

            return param
        # variable = self.content.variable_name
        else:
            print("👉🚫 Input is not connected", self.__class__.__name__)
            self.markDirty(True)
            self.markInvalid(True)
            self.grNode.setToolTip('Input is not connected')
            print("🐍 File: Preparation/formula.py | Line: 333 | processInputs ~ self._is_invalid", self._is_invalid)
            return None

    def get_code(self):
        return self.content.get_code()
