from qtpy.QtWidgets import QLineEdit, QPushButton, QFileDialog, QVBoxLayout, QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView, QLayout, QComboBox, QLineEdit, QLabel, QHBoxLayout
from qtpy.QtGui import QPixmap
from qtpy.QtCore import Qt, Signal
from trigger_conf import OP_NODE_FORMULA, register_node, OP_NODE_FILE_INPUT
from trigger_node_base import TriggerChangeHandler, TriggerNode, TriggerGraphicsNode
from nodeeditor.node_content_widget import QDMNodeContentWidget
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget
from nodeeditor.utils import dumpException
import pandas as pd
from themes.theme import Theme

theme = Theme()


class FormulaContent(QDMNodeIconContentWidget, TriggerChangeHandler):

    evaluate = Signal()  # Emit when evaluate button is clicked

    def __init__(self, node, parent=None):
        super().__init__(node, parent)
        # local variables
        self.formula: str = ''
        self.formula_text: str = ''
        self.target_column: str = ''
        self.is_new_column: bool = True
        TriggerChangeHandler.__init__(self, self.node.scene)

        # incoming variables
        self.incoming_variable: str = ''
        self.incom_data: pd.DataFrame = None

        # pass on variables
        self.data: pd.DataFrame = None
        self.variable_name = f'var_formula_{self.id}'

    def initUI(self, parent=None):
        icon = QPixmap("Resource/icons/Preparation/Formula.png")
        super().initUI(icon)

    def create_layout(self, dock_layout: QVBoxLayout) -> QLayout:
        if self.incom_data is not None:
            # Column selection
            column_layout = QHBoxLayout()
            self.column_name = QComboBox()
            self.column_name.setEditable(False)  # Initially not editable

            # Add existing columns and the "+" button
            self.column_name.addItem("+ add column")
            self.column_name.addItems(self.incom_data.columns)
            # Connect the activation signal
            self.column_name.activated.connect(self.handle_column_activation)

            if self.target_column in self.incom_data.columns:
                self.column_name.setCurrentText(self.target_column)
            else:
                self.column_name.addItem(self.target_column)
                self.column_name.setCurrentText(self.target_column)
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
            self.formula_input.textChanged.connect(self.generate_formula)
            formula_layout.addWidget(QLabel("Formula:"))
            formula_layout.addWidget(self.formula_input)

            # Add layouts
            dock_layout.addLayout(column_layout)
            dock_layout.addLayout(formula_layout)
            self.recursively_find_widgets(dock_layout)
        # return layout
        else:
            no_data_label = QLabel("No incoming data available")
            no_data_label.setAlignment(Qt.AlignCenter)
            no_data_label.setStyleSheet("color: gray;")
            dock_layout.addWidget(no_data_label)

    def handle_column_activation(self, index):
        print("🐍 File: Preparation/formula.py | Line: 78 | handle_column_activation ~ self.column_name.itemText(index)",
              self.column_name.itemText(index))
        if self.column_name.itemText(index) == "+ add column":
            self.column_name.setEditable(True)
            self.column_name.clearEditText()
            self.column_name.lineEdit().returnPressed.connect(self.handle_new_column)
        else:
            self.target_column = self.column_name.itemText(index)

    def handle_new_column(self):
        print("🐍 File: Preparation/formula.py | Line: 80 | handle_new_column ~ self.column_name",
              self.column_name.currentText().strip())

        new_column = self.column_name.currentText().strip()
        if new_column and new_column != "+ add column" and new_column not in self.incom_data.columns:
            # Clear existing items
            self.column_name.clear()

            # Add the new column and the "+" button
            self.column_name.addItem(new_column)

            # Add back original columns
            self.column_name.addItems(self.incom_data.columns)

            # Add the "+" button
            self.column_name.addItem("+ add column")
            self.target_column = new_column
            self.handle_data_changed()

            # Select the new column
            self.column_name.setCurrentIndex(0)

        # Reset to non-editable state
        self.column_name.setEditable(False)

    def handle_data_changed(self):
        # add new column in the data
        self.data = self.incom_data.copy()
        self.data[self.target_column] = None

    def generate_formula(self):
        if not getattr(self, 'formula_input', None) is None:
            self.formula_text = self.formula_input.toPlainText()

        print("🐍 File: Preparation/formula.py | Line: 125 | generate_formula ~ self.formula_text", self.formula_text)

        # If target column changed, remove the old column
        self.data = self.incom_data.copy()
        self.formula = self.formula_text

        # Replace column names in formula
        # self.formula
        # replace column names in formula
        for col in self.data.columns:
            self.formula = self.formula.replace(
                f'[{col}]', f'"{col}"')

        print(
            "🐍 File: Preparation/formula.py | Line: 134 | generate_formula ~ self.formula", self.formula)

        if self.target_column:
            self.data[self.target_column] = None

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


@register_node(OP_NODE_FORMULA, 'PREPARATION')
class TriggerNode_Formula(TriggerNode):
    icon = "Resource/icons/Preparation/Formula.png"
    op_code = OP_NODE_FORMULA
    op_type = 'PREPARATION'
    op_title = "Formula"
    content_label_objname = "trigger_node_formula"
    style = {
        'brush_color': theme.brush_color('PREPARATION')
    }

    def __init__(self, scene):
        super().__init__(scene, inputs=[1], outputs=[3])
        # self.eval()

    def initInnerClasses(self):
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
