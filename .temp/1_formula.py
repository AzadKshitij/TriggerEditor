from qtpy.QtWidgets import (QVBoxLayout, QComboBox, QLineEdit, QLabel,
                            QHBoxLayout, QPushButton)
from qtpy.QtGui import QPixmap
from qtpy.QtCore import Signal
from trigger_conf import register_node, OP_NODE_FORMULA
from trigger_node_base import TriggerNode, TriggerGraphicsNode
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget
import pandas as pd
import numpy as np


class FormulaContent(QDMNodeIconContentWidget):
    evaluate = Signal()

    def __init__(self, node, parent=None):
        super().__init__(node, parent)
        self.incoming_variable: str = ''
        self.incom_data: pd.DataFrame = None
        self.data: pd.DataFrame = None
        self.variable_name: str = f'var_formula_{self.id}'
        self.formula: str = ''
        self.target_column: str = ''
        self.is_new_column: bool = True

    def initUI(self):
        icon = QPixmap(
            "src/trigger_designer/Resource/icons/Preparation/Formula.png")
        super().initUI(icon)

    def create_layout(self, dock_layout: QVBoxLayout):
        if self.incom_data is not None:
            # Column selection
            column_layout = QHBoxLayout()
            self.column_type = QComboBox()
            self.column_type.addItems(["New Column", "Existing Column"])
            self.column_type.currentTextChanged.connect(
                self.on_column_type_changed)

            self.column_name = QComboBox() if not self.is_new_column else QLineEdit()
            if not self.is_new_column:
                self.column_name.addItems(self.incom_data.columns)

            column_layout.addWidget(QLabel("Target:"))
            column_layout.addWidget(self.column_type)
            column_layout.addWidget(self.column_name)

            # Formula input
            formula_layout = QHBoxLayout()
            self.formula_input = QLineEdit()
            self.formula_input.setPlaceholderText(
                "Enter formula e.g.: if [Age] > 30 then 'Adult' else 'Young'")
            formula_layout.addWidget(QLabel("Formula:"))
            formula_layout.addWidget(self.formula_input)

            # Add layouts
            dock_layout.addLayout(column_layout)
            dock_layout.addLayout(formula_layout)

            # Apply button
            self.apply_btn = QPushButton("Apply Formula")
            self.apply_btn.clicked.connect(self.apply_formula)
            dock_layout.addWidget(self.apply_btn)

    def on_column_type_changed(self, text):
        self.is_new_column = text == "New Column"
        # Remove existing widget
        old_widget = self.column_name
        layout = old_widget.parent()
        layout.removeWidget(old_widget)
        old_widget.deleteLater()

        # Create new widget
        if self.is_new_column:
            self.column_name = QLineEdit()
        else:
            self.column_name = QComboBox()
            self.column_name.addItems(self.incom_data.columns)

        # Add new widget to layout
        layout.addWidget(self.column_name)

    def apply_formula(self):
        if self.incom_data is None:
            return

        # Get target column name
        target_col = (self.column_name.text() if self.is_new_column
                      else self.column_name.currentText())

        # Get formula and parse it
        formula = self.formula_input.text()

        try:
            # Create copy of incoming data
            self.data = self.incom_data.copy()

            # Parse and apply formula
            result = self.evaluate_formula(formula)

            # Assign result to target column
            self.data[target_col] = result

            self.formula = formula
            self.target_column = target_col

            self.evaluate.emit()

        except Exception as e:
            print(f"Error applying formula: {str(e)}")

    def evaluate_formula(self, formula):
        # Replace column references with actual data
        for col in self.incom_data.columns:
            formula = formula.replace(f'[{col}]', f'self.incom_data["{col}"]')

        # Replace keywords
        formula = formula.replace('if ', 'np.where(')
        formula = formula.replace(' then ', ', ')
        formula = formula.replace(' else ', ', ')

        # Evaluate the formula
        return eval(formula + ')')

    def get_code(self):
        if self.data is None or self.incoming_variable is None:
            return ""

        code_lines = [
            f"{self.variable_name} = {self.incoming_variable}.copy()",
            f"# Apply formula: {self.formula}",
        ]

        # Generate formula code
        formula = self.formula
        for col in self.incom_data.columns:
            formula = formula.replace(
                f'[{col}]', f'{self.variable_name}["{col}"]')

        formula = formula.replace('if ', 'np.where(')
        formula = formula.replace(' then ', ', ')
        formula = formula.replace(' else ', ', ')

        code_lines.append(
            f"{self.variable_name}['{self.target_column}'] = {formula})")

        return '\n'.join(code_lines) + '\n'


@register_node(OP_NODE_FORMULA, "PREPARATION")
class TriggerNode_Formula(TriggerNode):
    icon = "node_formula"
    node_code = OP_NODE_FORMULA
    node_title = "Formula"
    content_label_objname = "trigger_node_formula"

    def __init__(self, scene):
        super().__init__(scene, inputs=[1], outputs=[1])
        self.eval()

    def initInnerClasses(self):
        self.content = FormulaContent(self)
        self.grNode = TriggerGraphicsNode(self)

    def processInputs(self, input_values):
        input_value = input_values[0]
        if input_value:
            self.markDirty(False)
            self.markInvalid(False)
            self.content.incom_data = input_value.get('data')
            self.content.incoming_variable = input_value.get('variable_name')

            self.evalChildren()

            return {
                "data": self.content.data,
                "variable_name": self.content.variable_name
            }
        else:
            self.markDirty(True)
            self.markInvalid(True)
