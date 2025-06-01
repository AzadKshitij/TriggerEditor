from typing import Dict, Optional, List
import pandas as pd
from qtpy.QtWidgets import QWidget, QVBoxLayout, QLabel, QListWidget, QGroupBox, QAbstractItemView, QCheckBox, QScrollArea
from qtpy.QtGui import QPixmap
from qtpy.QtCore import Signal, Qt
from trigger_designer.core.node_configuration import register_node, TransformNodes, NodeTypes
from trigger_designer.qt.node_base import TriggerChangeHandler, TriggerNode, TriggerGraphicsNode
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget


class RunningTotalContent(QDMNodeIconContentWidget, TriggerChangeHandler):
    """Calculate running totals for numeric columns with optional grouping.

    Features:
    - Select numeric columns for running totals
    - Optional grouping by categorical columns
    - Maintains original row order
    - Prefixes new columns with "RunTot_"
    """

    evaluate = Signal()

    def __init__(self, node: 'TriggerNode', parent: Optional[QWidget] = None) -> None:
        super().__init__(node, parent)
        self.node = node
        # Data tracking
        self.incoming_variable: str = ''
        self.incom_data: Optional[pd.DataFrame] = None
        self.data: Optional[pd.DataFrame] = None
        self.variable_name = f'var_runtot_{self.id}'

        # Configuration
        self.group_by_columns: List[str] = []
        self.sum_columns: List[str] = []
        self.numeric_columns: List[str] = []

        # Checkbox tracking
        self.sum_checkboxes: Dict[str, QCheckBox] = {}
        self.group_checkboxes: Dict[str, QCheckBox] = {}

    @property
    def node(self) -> 'TriggerNode':
        return self._node

    @node.setter
    def node(self, value: 'TriggerNode') -> None:
        self._node = value

    def initUI(self, icon: Optional[QPixmap] = None) -> None:
        icon_: QPixmap = self.node.rsm.get(f'{self.node.icon}')
        super().initUI(icon_)

    def create_layout(self, dock_layout: QVBoxLayout) -> None:
        if self.incom_data is not None:
            main_layout = QVBoxLayout()
            main_layout.setSpacing(2)
            main_layout.setContentsMargins(5, 5, 5, 5)

            # Get numeric columns
            self.numeric_columns = self.incom_data.select_dtypes(
                include=['int64', 'float64']).columns.tolist()

            # Numeric Columns Selection with Checkboxes
            sum_group = QGroupBox("Select Columns for Running Total")
            sum_layout = QVBoxLayout()

            # Create scrollable area for sum columns
            sum_scroll = QScrollArea()
            sum_scroll.setWidgetResizable(True)
            sum_widget = QWidget()
            sum_checkbox_layout = QVBoxLayout()

            # Add checkboxes for numeric columns
            for col in self.numeric_columns:
                checkbox = QCheckBox(col)
                checkbox.stateChanged.connect(self.on_sum_selection_changed)
                self.sum_checkboxes[col] = checkbox
                sum_checkbox_layout.addWidget(checkbox)

            print("🐍 File: Transform/running_total.py:70 | create_layout ~ self.sum_checkboxes",
                  self.sum_checkboxes)

            sum_widget.setLayout(sum_checkbox_layout)
            sum_scroll.setWidget(sum_widget)
            sum_layout.addWidget(sum_scroll)
            sum_group.setLayout(sum_layout)
            main_layout.addWidget(sum_group)

            # Group By Columns Selection with Checkboxes
            group_box = QGroupBox("Group By (Optional)")
            group_layout = QVBoxLayout()

            # Create scrollable area for group columns
            group_scroll = QScrollArea()
            group_scroll.setWidgetResizable(True)
            group_widget = QWidget()
            group_checkbox_layout = QVBoxLayout()

            # Add checkboxes for all columns
            for column in self.incom_data.columns:
                checkbox = QCheckBox(column)
                checkbox.stateChanged.connect(self.on_group_selection_changed)
                self.group_checkboxes[column] = checkbox
                group_checkbox_layout.addWidget(checkbox)

            group_widget.setLayout(group_checkbox_layout)
            group_scroll.setWidget(group_widget)
            group_layout.addWidget(group_scroll)
            group_box.setLayout(group_layout)
            main_layout.addWidget(group_box)

            self.update_checkboxes()

            dock_layout.addLayout(main_layout)
        else:
            no_data_label = QLabel('No incoming data available')
            no_data_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_data_label.setStyleSheet('color: gray;')
            dock_layout.addWidget(no_data_label)

    def process_data(self) -> None:
        """Calculate running totals for selected columns"""
        if self.incom_data is not None and self.sum_columns:
            # Start with original data
            self.data = self.incom_data.copy()

            # Calculate running totals
            if self.group_by_columns:
                # Group by selected columns
                for col in self.sum_columns:
                    self.data[f'RunTot_{col}'] = self.data.groupby(
                        self.group_by_columns)[col].cumsum()
            else:
                # No grouping - straight cumsum
                for col in self.sum_columns:
                    self.data[f'RunTot_{col}'] = self.data[col].cumsum()

    def on_sum_selection_changed(self, state: bool) -> None:
        print("🐍 File: Transform/running_total.py:128 | process_data ~ state", state)
        """Handle sum columns checkbox changes"""
        self.sum_columns = [
            col for col, checkbox in self.sum_checkboxes.items()
            if checkbox.isChecked()
        ]
        # self.process_data()
        self.evaluate.emit()

    def on_group_selection_changed(self) -> None:
        """Handle group by columns checkbox changes"""
        self.group_by_columns = [
            col for col, checkbox in self.group_checkboxes.items()
            if checkbox.isChecked()
        ]
        # self.process_data()
        self.evaluate.emit()

    def get_code(self) -> str:
        """Generate code for running total calculations"""

        if self.incoming_variable is None:
            return "print('No data available for running total calculation')\n"

        code_lines = [
            f"{self.variable_name} = {self.incoming_variable}.copy()"]

        for col in self.sum_columns:
            if self.group_by_columns:
                group_cols = ", ".join(
                    f"'{col}'" for col in self.group_by_columns)
                code_lines.append(
                    f"{self.variable_name}['RunTot_{col}'] = "
                    f"{self.variable_name}.groupby([{group_cols}])['{col}'].cumsum()"
                )
            else:
                code_lines.append(
                    f"{self.variable_name}['RunTot_{col}'] = "
                    f"{self.variable_name}['{col}'].cumsum()"
                )

        return "\n".join(code_lines) + "\n"

    def serialize(self) -> dict:
        """Serialize node content"""
        res = super().serialize()
        res['sum_columns'] = self.sum_columns
        print("🐍 File: Transform/running_total.py:174 | serialize ~ self.sum_columns", self.sum_columns)
        res['group_by_columns'] = self.group_by_columns
        print("🐍 File: Transform/running_total.py:176 | serialize ~ self.group_by_columns",
              self.group_by_columns)
        res['numeric_columns'] = self.numeric_columns
        print("🐍 File: Transform/running_total.py:178 | serialize ~ self.numeric_columns",
              self.numeric_columns)
        return res

    def deserialize(self, data: dict, hashmap={}) -> bool:
        """Deserialize node content"""
        res = super().deserialize(data, hashmap)
        try:
            # Load saved columns
            self.sum_columns = data.get('sum_columns', [])
            self.group_by_columns = data.get('group_by_columns', [])
            self.numeric_columns = data.get('numeric_columns', [])

            return True & res
        except Exception as e:
            dumpException(e)
            return res

    def update_checkboxes(self) -> None:
        """Update checkbox states when data changes"""
        # Clear existing checkboxes
        # self.sum_checkboxes.clear()
        # self.group_checkboxes.clear()

        if self.incom_data is not None:
            # Update numeric columns
            self.numeric_columns = self.incom_data.select_dtypes(
                include=['int64', 'float64']).columns.tolist()

            # Restore sum column selections
            for col in self.numeric_columns:
                if col in self.sum_checkboxes:
                    self.sum_checkboxes[col].setChecked(
                        col in self.sum_columns)

            # Restore group by selections
            for col in self.incom_data.columns:
                if col in self.group_checkboxes:
                    self.group_checkboxes[col].setChecked(
                        col in self.group_by_columns)

    def clear_data(self) -> None:
        """Clear all data and selections"""
        self.data = None
        self.sum_columns.clear()
        self.group_by_columns.clear()
        self.numeric_columns.clear()
        self.sum_checkboxes.clear()
        self.group_checkboxes.clear()


@register_node(TransformNodes.RUNNING_TOTAL, NodeTypes.TRANSFORM)
class TriggerNode_RunningTotal(TriggerNode):
    icon = "node_running_total"
    node_code = TransformNodes.RUNNING_TOTAL
    node_title = "Running Total"
    node_type = NodeTypes.TRANSFORM
    content_label_objname = "trigger_node_running_total"

    def __init__(self, scene) -> None:
        super().__init__(scene, inputs=[1], outputs=[1])
        self.eval()

    def initInnerClasses(self) -> None:
        self.content: RunningTotalContent = RunningTotalContent(self)
        self.grNode: TriggerGraphicsNode = TriggerGraphicsNode(self)
        self.content.evaluate.connect(self.onInputChanged)
        self.param: List = []

    def processInputs(self, input_values):
        this_socket_index = 0
        input_node = self.getInput(this_socket_index)
        socket_index = self.getSocketValue(input_node.outputs, self)
        input_value = input_values[this_socket_index][socket_index]

        if input_value:
            self.markDirty(False)
            self.markInvalid(False)

            self.content.incom_data = input_value.get('data')
            self.content.incoming_variable = input_value.get('variable_name')

            self.content.process_data()

            self.param = [{
                'data': self.content.data,
                'variable_name': self.content.variable_name
            }]
            self.evalChildren()

            return self.param
        else:
            self.markDirty(True)
            self.markInvalid(True)
            self.grNode.setToolTip('Input is not connected')
            return None

    def get_code(self) -> str:
        return self.content.get_code()
