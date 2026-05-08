from typing import Optional, Any, Callable
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
from qtpy.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QGroupBox,
    QLineEdit,
    QComboBox,
    QSpinBox,
    QDateTimeEdit,
    QDoubleSpinBox,
)
from qtpy.QtGui import QPixmap
from qtpy.QtCore import Signal, Qt, QDateTime
from trigger_designer.core.node_configuration import (
    register_node,
    PreparationNodes,
    NodeTypes,
)
from trigger_designer.qt.node_base import (
    TriggerChangeHandler,
    TriggerNode,
    TriggerGraphicsNode,
)
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget
from nodeeditor.utils_no_qt import dumpException


class DynamicRowBuilderContent(QDMNodeIconContentWidget, TriggerChangeHandler):
    """Generate rows dynamically based on configured rules.

    Features:
    - Create new rows from scratch or based on input data
    - Support for numeric, string, and datetime fields
    - Configurable start value and increment
    - Safety limits to prevent infinite loops
    """

    evaluate = Signal()
    MAX_ITERATIONS = 10000  # Safety limit

    def __init__(self, node: "TriggerNode", parent: Optional[QWidget] = None) -> None:
        super().__init__(node, parent)
        self.node = node
        TriggerChangeHandler.__init__(self, self.node.scene, self.node)

        # Data tracking
        self.incoming_variable: str = ""
        self.incom_data: Optional[pd.DataFrame] = None
        self.data: Optional[pd.DataFrame] = None
        self.variable_name = f"var_genrows_{self.id}"

        # Configuration
        self.field_name: str = "counter"
        self.field_type: str = "int"
        self.initial_value: Any = 1
        self.increment_value: Any = 1
        self.max_value: Any = 10

        # Type mapping
        self.type_mapping = {
            "int": int,
            "float": float,
            "string": str,
            "datetime": datetime,
        }

    @property
    def node(self) -> "TriggerNode":
        return self._node

    @node.setter
    def node(self, value: "TriggerNode") -> None:
        self._node = value

    def initUI(self, _icon: Optional[QPixmap] = None) -> None:
        icon: QPixmap = self.node.rsm.get(f"{self.node.icon}")
        super().initUI(icon)

    def create_layout(self, dock_layout: QVBoxLayout) -> None:
        """Create the node's UI layout"""
        main_layout = QVBoxLayout()
        main_layout.setSpacing(2)
        main_layout.setContentsMargins(5, 5, 5, 5)

        # Field Configuration
        field_group = QGroupBox("Field Settings")
        field_layout = QVBoxLayout()

        # Field name
        name_label = QLabel("Field Name:")
        self.name_edit = QLineEdit(self.field_name)
        self.name_edit.textChanged.connect(self.on_field_name_changed)
        field_layout.addWidget(name_label)
        field_layout.addWidget(self.name_edit)

        # Field type
        type_label = QLabel("Field Type:")
        self.type_combo = QComboBox()
        self.type_combo.addItems(["int", "float", "string", "datetime"])
        self.type_combo.setCurrentText(self.field_type)
        self.type_combo.currentTextChanged.connect(self.on_field_type_changed)
        field_layout.addWidget(type_label)
        field_layout.addWidget(self.type_combo)

        field_group.setLayout(field_layout)
        main_layout.addWidget(field_group)

        # Value Configuration
        value_group = QGroupBox("Value Settings")
        value_layout = QVBoxLayout()

        # Initial value
        initial_label = QLabel("Start Value:")
        self.initial_widget = self.create_value_widget(self.field_type)
        value_layout.addWidget(initial_label)
        value_layout.addWidget(self.initial_widget)

        # Increment value
        increment_label = QLabel("Increment By:")
        self.increment_widget = self.create_value_widget(self.field_type)
        value_layout.addWidget(increment_label)
        value_layout.addWidget(self.increment_widget)

        # Max value
        max_label = QLabel("End Value:")
        self.max_widget = self.create_value_widget(self.field_type)
        value_layout.addWidget(max_label)
        value_layout.addWidget(self.max_widget)

        value_group.setLayout(value_layout)
        main_layout.addWidget(value_group)

        # Stats display
        stats_group = QGroupBox("Statistics")
        stats_layout = QVBoxLayout()
        self.stats_label = QLabel()
        self.update_stats()
        stats_layout.addWidget(self.stats_label)
        stats_group.setLayout(stats_layout)
        main_layout.addWidget(stats_group)

        dock_layout.addLayout(main_layout)

    def create_value_widget(self, field_type: str) -> QWidget:
        """Create appropriate widget based on field type"""
        if field_type == "int":
            widget = QSpinBox()
            widget.setRange(-1000000, 1000000)
            widget.valueChanged.connect(self.on_value_changed)
        elif field_type == "float":
            widget = QDoubleSpinBox()
            widget.setRange(-1000000, 1000000)
            widget.setDecimals(4)
            widget.valueChanged.connect(self.on_value_changed)
        elif field_type == "datetime":
            widget = QDateTimeEdit()
            widget.setCalendarPopup(True)
            widget.setDateTime(QDateTime.currentDateTime())
            widget.dateTimeChanged.connect(self.on_value_changed)
        else:  # string
            widget = QLineEdit()
            widget.textChanged.connect(self.on_value_changed)
        return widget

    def process_data(self) -> None:
        """Generate rows based on configuration"""
        try:
            # Initialize values based on field type
            start_val = self.get_typed_value(self.initial_widget)
            increment = self.get_typed_value(self.increment_widget)
            end_val = self.get_typed_value(self.max_widget)

            # Generate rows
            values = []
            current = start_val
            iteration = 0

            while iteration < self.MAX_ITERATIONS:
                if self.should_stop(current, end_val):
                    break

                values.append(current)
                current = self.increment_value(current, increment)
                iteration += 1

                if iteration == self.MAX_ITERATIONS:
                    print(
                        f"Warning: Reached maximum iterations ({self.MAX_ITERATIONS})"
                    )

            # Create DataFrame
            if self.incom_data is not None:
                # Expand existing DataFrame
                repeated_df = pd.DataFrame({self.field_name: values})
                self.data = pd.concat([self.incom_data, repeated_df], axis=1)
            else:
                # Create new DataFrame
                self.data = pd.DataFrame({self.field_name: values})

            self.update_stats()

        except Exception as e:
            print(f"Error generating rows: {str(e)}")
            self.data = None

    def get_typed_value(self, widget: QWidget) -> Any:
        """Get properly typed value from widget"""
        if isinstance(widget, QSpinBox):
            return widget.value()
        elif isinstance(widget, QDoubleSpinBox):
            return float(widget.value())
        elif isinstance(widget, QDateTimeEdit):
            return widget.dateTime().toPython()
        else:  # QLineEdit
            return widget.text()

    def should_stop(self, current: Any, end: Any) -> bool:
        """Determine if row generation should stop"""
        if self.field_type in ["int", "float"]:
            return current > end
        elif self.field_type == "datetime":
            return current > end
        else:  # string
            return False

    def _increment_value(self, current: Any, increment: Any) -> Any:
        """Calculate next value based on field type"""
        if self.field_type in ["int", "float"]:
            return current + increment
        elif self.field_type == "datetime":
            return current + timedelta(seconds=increment)
        else:  # string
            return f"{current}{increment}"

    def update_stats(self) -> None:
        """Update statistics display"""
        if self.data is not None:
            stats = f"Generated Rows: {len(self.data):,}"
            self.stats_label.setText(stats)

    def on_field_name_changed(self, value: str) -> None:
        """Handle field name changes"""
        self.field_name = value
        self.process_data()
        self.evaluate.emit()

    def on_field_type_changed(self, value: str) -> None:
        """Handle field type changes"""
        old_type = self.field_type
        self.field_type = value

        # Create new widgets for the new type
        new_initial = self.create_value_widget(value)
        new_increment = self.create_value_widget(value)
        new_max = self.create_value_widget(value)

        # Replace old widgets with new ones
        old_initial = self.initial_widget
        old_increment = self.increment_widget
        old_max = self.max_widget

        old_initial.parent().layout().replaceWidget(old_initial, new_initial)
        old_increment.parent().layout().replaceWidget(old_increment, new_increment)
        old_max.parent().layout().replaceWidget(old_max, new_max)

        # Clean up old widgets
        old_initial.deleteLater()
        old_increment.deleteLater()
        old_max.deleteLater()

        # Store new widgets
        self.initial_widget = new_initial
        self.increment_widget = new_increment
        self.max_widget = new_max

        # Reset to default values based on type
        if value == "int":
            self.initial_value = 1
            self.increment_value = 1
            self.max_value = 10
        elif value == "float":
            self.initial_value = 1.0
            self.increment_value = 1.0
            self.max_value = 10.0
        elif value == "datetime":
            now = QDateTime.currentDateTime()
            self.initial_value = now
            self.increment_value = 3600  # 1 hour in seconds
            self.max_value = now.addDays(1)
        else:  # string
            self.initial_value = "A"
            self.increment_value = "1"
            self.max_value = "Z"

        self.process_data()
        self.evaluate.emit()

    def on_value_changed(self, value: Any) -> None:
        """Handle changes to any value widget"""
        # Determine which widget triggered the change
        sender = self.sender()

        if sender == self.initial_widget:
            self.initial_value = self.get_typed_value(sender)
        elif sender == self.increment_widget:
            self.increment_value = self.get_typed_value(sender)
        elif sender == self.max_widget:
            self.max_value = self.get_typed_value(sender)

        self.process_data()
        self.evaluate.emit()

    def get_code(self) -> str:
        """Generate code for row generation"""
        if self.incom_data is None:
            return "print('No data generated')\n"

        code_lines = [
            f"# Generate rows",
            f"values = []",
            f"current = {self.initial_value}",
            f"while current <= {self.max_value}:",
            f"    values.append(current)",
            f"    current = {self.get_increment_code()}",
            f"",
            f"{self.variable_name} = pd.DataFrame({{'{self.field_name}': values}})",
        ]

        if self.incom_data is not None:
            code_lines.append(
                f"{self.variable_name} = pd.concat([{self.incoming_variable}, {self.variable_name}], axis=1)"
            )

        return "\n".join(code_lines) + "\n"

    def get_increment_code(self) -> str:
        """Get code for increment operation"""
        if self.field_type in ["int", "float"]:
            return f"current + {self.increment_value}"
        elif self.field_type == "datetime":
            return f"current + timedelta(seconds={self.increment_value})"
        else:
            return 'f"{current}{self.increment_value}"'

    def serialize(self) -> dict:
        """Serialize node content"""
        res = super().serialize()
        res.update(
            {
                "field_name": self.field_name,
                "field_type": self.field_type,
                "initial_value": self.initial_value,
                "increment_value": self.increment_value,
                "max_value": self.max_value,
            }
        )
        return res

    def deserialize(self, data: dict, hashmap={}) -> bool:
        """Deserialize node content"""
        res = super().deserialize(data, hashmap)
        try:
            self.field_name = data.get("field_name", "counter")
            self.field_type = data.get("field_type", "int")
            self.initial_value = data.get("initial_value", 1)
            self.increment_value = data.get("increment_value", 1)
            self.max_value = data.get("max_value", 10)
            return True & res
        except Exception as e:
            dumpException(e)
            return res


@register_node(PreparationNodes.DYNAMIC_ROW_BUILDER, NodeTypes.PREPARATION)
class TriggerNode_DynamicRowBuilder(TriggerNode):
    icon = "node_generate_rows"
    node_code = PreparationNodes.DYNAMIC_ROW_BUILDER
    node_title = "Generate Rows"
    node_type = NodeTypes.PREPARATION
    content_label_objname = "trigger_node_generate_rows"

    def __init__(self, scene) -> None:
        super().__init__(scene, inputs=[1], outputs=[1])
        self.eval()

    def initInnerClasses(self) -> None:
        self.content: DynamicRowBuilderContent = DynamicRowBuilderContent(self)
        self.grNode: TriggerGraphicsNode = TriggerGraphicsNode(self)
        self.content.evaluate.connect(self.onInputChanged)
        self.param: list = []

    def processInputs(self, input_values):
        """Process inputs and generate rows based on configuration"""
        this_socket_index = 0
        input_node = self.getInput(this_socket_index)
        socket_index = self.getSocketValue(input_node.outputs, self)
        input_value = input_values[this_socket_index][socket_index]

        if input_value:
            self.markDirty(False)
            self.markInvalid(False)

            self.content.incom_data = input_value.get("data")
            self.content.incoming_variable = input_value.get("variable_name")

            self.content.process_data()
            self.evalChildren()

            self.param = [
                {"data": self.content.data, "variable_name": self.content.variable_name}
            ]

            return self.param
        else:
            self.markDirty(True)
            self.markInvalid(True)
            self.grNode.setToolTip("Input is not connected")
            return None

    def get_code(self) -> str:
        return self.content.get_code()
