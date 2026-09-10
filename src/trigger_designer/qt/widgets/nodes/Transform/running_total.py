from typing import Dict, Optional, List, TYPE_CHECKING
import polars as pl
from qtpy.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QCheckBox,
)
from qtpy.QtGui import QPixmap
from qtpy.QtCore import Signal
from trigger_designer.core.node_configuration import (
    register_node,
    TransformNodes,
    NodeTypes,
)
from trigger_designer.qt.node_base import (
    TriggerChangeHandler,
    TriggerNode,
    TriggerGraphicsNode,
)
from trigger_designer.qt.helpers.state_mixin import SerializableContentMixin
from trigger_designer.qt.widgets.common import (
    ColumnChecklist,
    ConfigSection,
    EmptyStateLabel,
)
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget
from nodeeditor.utils_no_qt import dumpException
from trigger_designer.qt.helpers import global_logger

if TYPE_CHECKING:
    import polars as pl


class RunningTotalContent(
    QDMNodeIconContentWidget, TriggerChangeHandler, SerializableContentMixin
):
    """Add cumulative-sum columns in the current row order.

    For every selected numeric column, the node appends a new
    ``RunTot_<column>`` column. If grouping columns are selected, the
    cumulative sum resets within each group; otherwise it runs across the
    entire input in the current row order.
    """

    evaluate = Signal()
    serialized_state_schema = {
        "sum_columns": {"default": []},
        "group_by_columns": {"default": []},
        "numeric_columns": {"default": []},
    }

    def __init__(self, node: "TriggerNode", parent: Optional[QWidget] = None) -> None:
        super().__init__(node, parent)
        TriggerChangeHandler.__init__(self, node.scene, node)
        self.node = node
        # Data tracking
        self.incoming_variable: str = ""
        self.incom_data: Optional[pl.DataFrame] = None
        self.data: Optional[pl.DataFrame] = None
        self.variable_name = f"var_runtot_{self.id}"

        # Configuration
        self.group_by_columns: List[str] = []
        self.sum_columns: List[str] = []
        self.numeric_columns: List[str] = []

        # Checkbox tracking
        self.sum_checkboxes: Dict[str, QCheckBox] = {}
        self.group_checkboxes: Dict[str, QCheckBox] = {}

    def _get_schema(self) -> dict[str, pl.DataType]:
        if self.incom_data is None:
            return {}
        if isinstance(self.incom_data, pl.LazyFrame):
            schema = self.incom_data.collect_schema()
            return {name: dtype for name, dtype in schema.items()}
        return {name: dtype for name, dtype in self.incom_data.schema.items()}

    def _get_columns(self) -> list[str]:
        return list(self._get_schema().keys())

    def _get_numeric_columns(self) -> list[str]:
        return [
            name for name, dtype in self._get_schema().items() if dtype.is_numeric()
        ]

    @property
    def node(self) -> "TriggerNode":
        return self._node

    @node.setter
    def node(self, value: "TriggerNode") -> None:
        self._node = value

    def initUI(self, icon: Optional[QPixmap] = None) -> None:
        icon_: QPixmap = self.node.rsm.get(f"{self.node.icon}")
        super().initUI(icon_)

    def create_layout(self, dock_layout: QVBoxLayout) -> None:
        if self.incom_data is None:
            dock_layout.addWidget(EmptyStateLabel())
            return

        main_layout = QVBoxLayout()
        main_layout.setSpacing(2)
        main_layout.setContentsMargins(5, 5, 5, 5)

        self.numeric_columns = self._get_numeric_columns()

        sum_section = ConfigSection("Select Columns for Running Total")
        self.sum_list = ColumnChecklist(self.numeric_columns, self.sum_columns)
        self.sum_list.changed.connect(self.on_sum_selection_changed)
        self.sum_checkboxes = self.sum_list.checkboxes
        sum_section.addWidget(self.sum_list)
        main_layout.addWidget(sum_section)

        group_section = ConfigSection("Group By (Optional)")
        self.group_list = ColumnChecklist(self._get_columns(), self.group_by_columns)
        self.group_list.changed.connect(self.on_group_selection_changed)
        self.group_checkboxes = self.group_list.checkboxes
        group_section.addWidget(self.group_list)
        main_layout.addWidget(group_section)

        dock_layout.addLayout(main_layout)
        self.recursively_find_widgets(dock_layout)

    def process_data(self) -> None:
        """Calculate running totals for selected columns using Polars."""
        if self.incom_data is None:
            self.data = None
            return

        available_columns = self._get_columns()
        self.sum_columns = [
            column
            for column in self.sum_columns
            if column in self._get_numeric_columns()
        ]
        self.group_by_columns = [
            column for column in self.group_by_columns if column in available_columns
        ]

        if not self.sum_columns:
            self.data = self.incom_data
            return

        try:
            expressions = []
            for column in self.sum_columns:
                expression = pl.col(column).cum_sum()
                if self.group_by_columns:
                    expression = expression.over(self.group_by_columns)
                expressions.append(expression.alias(f"RunTot_{column}"))

            self.data = self.incom_data.with_columns(expressions)
        except Exception as e:
            global_logger.error(
                f"❌ RunningTotalContent: Error computing running total: {e}"
            )
            self.data = None

    def on_sum_selection_changed(self, checked: list) -> None:
        """Handle sum columns checkbox changes"""
        self.sum_columns = list(checked)
        self.evaluate.emit()

    def on_group_selection_changed(self, checked: list) -> None:
        """Handle group by columns checkbox changes"""
        self.group_by_columns = list(checked)
        self.evaluate.emit()

    def get_code(self) -> str:
        """Generate Polars code for running total calculations."""
        if not self.incoming_variable:
            return ""

        if not self.sum_columns:
            return (
                f"# No running-total columns selected\n"
                f"{self.variable_name} = {self.incoming_variable}\n"
            )

        exprs = []
        for col in self.sum_columns:
            if self.group_by_columns:
                group_cols = ", ".join(f'"{c}"' for c in self.group_by_columns)
                exprs.append(
                    f'    pl.col("{col}").cum_sum().over([{group_cols}]).alias("RunTot_{col}")'
                )
            else:
                exprs.append(f'    pl.col("{col}").cum_sum().alias("RunTot_{col}")')

        code_lines = [
            "import polars as pl",
            f"{self.variable_name} = {self.incoming_variable}.with_columns([",
        ]
        code_lines.extend(exprs)
        code_lines.append("])")

        return "\n".join(code_lines) + "\n"

    def serialize(self) -> dict:
        """Serialize node content"""
        return self.serialize_content_state(super().serialize())

    def deserialize(self, data: dict, hashmap={}) -> bool:
        """Deserialize node content"""
        res = super().deserialize(data, hashmap)
        try:
            self.deserialize_content_state(data)

            return True & res
        except Exception as e:
            dumpException(e)
            return res

    def update_checkboxes(self) -> None:
        """Update checkbox states when data changes"""
        if self.incom_data is None:
            return
        self.numeric_columns = self._get_numeric_columns()
        if hasattr(self, "sum_list"):
            self.sum_list.setChecked(self.sum_columns)
        if hasattr(self, "group_list"):
            self.group_list.setChecked(self.group_by_columns)

    def clear_data(self) -> None:
        """Clear all data and selections"""
        self.data = None
        self.sum_columns.clear()
        self.group_by_columns.clear()
        self.numeric_columns.clear()
        for checklist in (
            getattr(self, "sum_list", None),
            getattr(self, "group_list", None),
        ):
            if checklist is not None:
                checklist.setChecked([])


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
        try:
            input_node = self.getInput(0)
            socket_index = self.getSocketValue(input_node.outputs, self)
            input_value = input_values[0][socket_index]

            if input_value:
                self.markDirty(False)
                self.markInvalid(False)

                self.content.incom_data = input_value.get("data")
                self.content.incoming_variable = input_value.get("variable_name")

                self.content.process_data()

                if self.content.data is not None:
                    self.param = [
                        {
                            "data": self.content.data,
                            "variable_name": self.content.variable_name,
                        }
                    ]
                    self.evalChildren()
                    return self.param
                else:
                    self.markDirty(True)
                    self.markInvalid(True)
                    self.grNode.setToolTip("No columns selected for running total")
                    return None
            else:
                self.markDirty(True)
                self.markInvalid(True)
                self.grNode.setToolTip("Input is not connected")
                return None
        except Exception as e:
            global_logger.error(
                f"❌ RunningTotalNode: Error during input processing: {e}"
            )
            self.markDirty(True)
            self.markInvalid(True)
            return None

    def get_code(self) -> str:
        return self.content.get_code()
