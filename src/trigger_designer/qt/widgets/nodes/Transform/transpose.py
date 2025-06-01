from typing import Optional, List
import pandas as pd
from qtpy.QtWidgets import (QWidget, QVBoxLayout, QLabel, QGroupBox,
                            QCheckBox, QScrollArea, QComboBox)
from qtpy.QtGui import QPixmap
from qtpy.QtCore import Signal, Qt  # noqa: F401
from trigger_designer.core.node_configuration import register_node, TransformNodes, NodeTypes
from trigger_designer.qt.node_base import TriggerChangeHandler, TriggerNode, TriggerGraphicsNode
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget
from nodeeditor.utils_no_qt import dumpException


class TransposeContent(QDMNodeIconContentWidget, TriggerChangeHandler):
    """Transpose selected columns into rows while maintaining key columns.

    Features:
    - Select key columns to maintain
    - Choose columns to transpose
    - Configure missing column handling
    """

    evaluate = Signal()

    def __init__(self, node: 'TriggerNode', parent: Optional[QWidget] = None) -> None:
        super().__init__(node, parent)

        self.node = node

        # Data tracking
        self.incoming_variable: str = ''
        self.incom_data: Optional[pd.DataFrame] = None
        self.data: Optional[pd.DataFrame] = None
        self.variable_name = f'var_transpose_{self.id}'

        # Configuration
        self.key_columns: List[str] = []
        self.data_columns: List[str] = []
        self.missing_action = "warn"  # One of: error, warn, ignore

        # Checkbox tracking
        self.key_checkboxes: dict = {}
        self.data_checkboxes: dict = {}

    def initUI(self, icon: Optional[QPixmap] = None) -> None:
        icon_: QPixmap = self.node.rsm.get(f'{self.node.icon}')
        super().initUI(icon_)

    def create_layout(self, dock_layout: QVBoxLayout) -> None:
        if self.incom_data is not None:
            main_layout = QVBoxLayout()
            main_layout.setSpacing(2)
            main_layout.setContentsMargins(5, 5, 5, 5)

            # Key Columns Selection
            key_group = QGroupBox("Select Key Columns")
            key_layout = QVBoxLayout()
            key_scroll = QScrollArea()
            key_scroll.setWidgetResizable(True)
            key_widget = QWidget()
            key_checkbox_layout = QVBoxLayout()

            for col in self.incom_data.columns:
                checkbox = QCheckBox(col)
                checkbox.stateChanged.connect(self.on_key_selection_changed)
                self.key_checkboxes[col] = checkbox
                key_checkbox_layout.addWidget(checkbox)

            key_widget.setLayout(key_checkbox_layout)
            key_scroll.setWidget(key_widget)
            key_layout.addWidget(key_scroll)
            key_group.setLayout(key_layout)
            main_layout.addWidget(key_group)

            # Data Columns Selection
            data_group = QGroupBox("Select Columns to Transpose")
            data_layout = QVBoxLayout()
            data_scroll = QScrollArea()
            data_scroll.setWidgetResizable(True)
            data_widget = QWidget()
            data_checkbox_layout = QVBoxLayout()

            for col in self.incom_data.columns:
                checkbox = QCheckBox(col)
                checkbox.stateChanged.connect(self.on_data_selection_changed)
                self.data_checkboxes[col] = checkbox
                data_checkbox_layout.addWidget(checkbox)

            data_widget.setLayout(data_checkbox_layout)
            data_scroll.setWidget(data_widget)
            data_layout.addWidget(data_scroll)
            data_group.setLayout(data_layout)
            main_layout.addWidget(data_group)

            # Missing Columns Action
            action_group = QGroupBox("Missing Columns Handling")
            action_layout = QVBoxLayout()
            self.action_combo = QComboBox()
            self.action_combo.addItems(["error", "warn", "ignore"])
            self.action_combo.setCurrentText(self.missing_action)
            self.action_combo.currentTextChanged.connect(
                self.on_action_changed)
            action_layout.addWidget(self.action_combo)
            action_group.setLayout(action_layout)
            main_layout.addWidget(action_group)

            # Update checkbox states based on saved configuration
            for col, checkbox in self.key_checkboxes.items():
                checkbox.setChecked(col in self.key_columns)

            for col, checkbox in self.data_checkboxes.items():
                checkbox.setChecked(col in self.data_columns)

            # Update combo box state
            self.action_combo.setCurrentText(self.missing_action)

            dock_layout.addLayout(main_layout)

        else:
            no_data_label = QLabel('No incoming data available')
            no_data_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_data_label.setStyleSheet('color: gray;')
            dock_layout.addWidget(no_data_label)

    def process_data(self) -> None:
        """Transpose selected columns while maintaining key columns"""
        if self.incom_data is not None and self.data_columns:
            try:
                # Validate columns exist
                missing = [
                    col for col in self.data_columns if col not in self.incom_data.columns]
                if missing:
                    if self.missing_action == "error":
                        raise ValueError(f"Missing columns: {missing}")
                    elif self.missing_action == "warn":
                        print(
                            f"Warning: Missing columns will be skipped: {missing}")

                # Filter to existing columns only
                valid_data_cols = [
                    col for col in self.data_columns if col in self.incom_data.columns]
                if not valid_data_cols:
                    self.data = None
                    return

                # Perform transpose operation
                df = self.incom_data.copy()

                # Melt the DataFrame
                self.data = pd.melt(
                    df,
                    id_vars=self.key_columns,
                    value_vars=valid_data_cols,
                    var_name='Name',
                    value_name='Value'
                )

            except Exception as e:
                print(f"Error in transpose operation: {str(e)}")
                self.data = None

    def get_code(self) -> str:
        """Generate code for transpose operation"""
        if self.data is None or self.incoming_variable is None:
            return "print('No data available for transpose operation')\n"

        code_lines = []

        # Add column validation if needed
        if self.missing_action != "ignore":
            code_lines.extend([
                f"missing = [col for col in {self.data_columns} if col not in {self.incoming_variable}.columns]",
                f"if missing:"
            ])
            if self.missing_action == "error":
                code_lines.append(
                    "    raise ValueError(f'Missing columns: {missing}')"
                )
            else:  # warn
                code_lines.append(
                    "    print(f'Warning: Missing columns will be skipped: {missing}')"
                )

        # Add transpose operation
        key_cols = ", ".join(f"'{col}'" for col in self.key_columns)
        data_cols = ", ".join(f"'{col}'" for col in self.data_columns)

        code_lines.extend([
            f"valid_data_cols = [col for col in [{data_cols}] if col in {self.incoming_variable}.columns]",
            f"{self.variable_name} = pd.melt(",
            f"    {self.incoming_variable},",
            f"    id_vars=[{key_cols}],",
            f"    value_vars=valid_data_cols,",
            f"    var_name='Name',",
            f"    value_name='Value'",
            f")"
        ])

        return "\n".join(code_lines) + "\n"

    def on_key_selection_changed(self) -> None:
        """Handle key columns checkbox changes"""
        self.key_columns = [
            col for col, checkbox in self.key_checkboxes.items()
            if checkbox.isChecked()
        ]
        self.process_data()
        self.evaluate.emit()

    def on_data_selection_changed(self) -> None:
        """Handle data columns checkbox changes"""
        self.data_columns = [
            col for col, checkbox in self.data_checkboxes.items()
            if checkbox.isChecked()
        ]
        self.process_data()
        self.evaluate.emit()

    def on_action_changed(self, value: str) -> None:
        """Handle missing column action changes"""
        self.missing_action = value
        self.process_data()
        self.evaluate.emit()

    def serialize(self) -> dict:
        """Serialize node content"""
        res = super().serialize()
        res.update({
            'key_columns': self.key_columns,
            'data_columns': self.data_columns,
            'missing_action': self.missing_action
        })
        return res

    def deserialize(self, data: dict, hashmap={}) -> bool:
        """Deserialize node content"""
        res = super().deserialize(data, hashmap)
        try:
            self.key_columns = data.get('key_columns', [])
            self.data_columns = data.get('data_columns', [])
            self.missing_action = data.get('missing_action', 'warn')

            return True & res
        except Exception as e:
            dumpException(e)
            return res


@register_node(TransformNodes.TRANSPOSE, NodeTypes.TRANSFORM)
class TriggerNode_Transpose(TriggerNode):
    icon = "node_transpose"
    node_code = TransformNodes.TRANSPOSE
    node_title = "Transpose"
    node_type = NodeTypes.TRANSFORM
    content_label_objname = "trigger_node_transpose"

    def __init__(self, scene) -> None:
        super().__init__(scene, inputs=[1], outputs=[1])
        self.eval()

    def initInnerClasses(self) -> None:
        self.content: TransposeContent = TransposeContent(self)
        self.grNode: TriggerGraphicsNode = TriggerGraphicsNode(self)
        self.content.evaluate.connect(self.onInputChanged)
        self.param: list = []

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
            self.evalChildren()

            self.param = [{
                'data': self.content.data,
                'variable_name': self.content.variable_name
            }]

            return self.param
        else:
            self.markDirty(True)
            self.markInvalid(True)
            self.grNode.setToolTip('Input is not connected')
            return None

    def get_code(self) -> str:
        return self.content.get_code()
