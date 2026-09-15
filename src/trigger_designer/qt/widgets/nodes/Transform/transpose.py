from typing import Optional, List, TYPE_CHECKING
import polars as pl
from qtpy.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QComboBox,
)
from qtpy.QtGui import QPixmap
from qtpy.QtCore import Signal  # noqa: F401
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
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget
from nodeeditor.utils_no_qt import dumpException
from trigger_designer.qt.helpers import global_logger
from trigger_designer.qt.widgets.common import (
    ColumnChecklist,
    ConfigSection,
    EmptyStateLabel,
)

if TYPE_CHECKING:
    from nodeeditor.node_scene import Scene
    from nodeeditor.node_node import Node
    import polars as pl


class TransposeContent(QDMNodeIconContentWidget, TriggerChangeHandler):
    """Transpose selected columns into rows while maintaining key columns using Polars.

    Features:
    - Select key columns to maintain
    - Choose columns to transpose
    - Configure missing column handling
    """

    evaluate = Signal()

    def __init__(self, node: "TriggerNode", parent: Optional[QWidget] = None) -> None:
        super().__init__(node, parent)
        global_logger.debug(
            "📊 TransposeContent: Initializing Transpose node content widget"
        )

        self.node = node

        # Data tracking
        self.incoming_variable: str = ""
        self.incom_data: Optional[pl.DataFrame] = None
        self.data: Optional[pl.DataFrame] = None
        self.variable_name = f"var_transpose_{self.id}"

        # Configuration
        self.key_columns: List[str] = []
        self.data_columns: List[str] = []
        self.missing_action = "warn"  # One of: error, warn, ignore

        # Checkbox tracking
        self.key_checkboxes: dict = {}
        self.data_checkboxes: dict = {}

        global_logger.trace("📊 TransposeContent: Initialization completed")

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

        key_section = ConfigSection(
            "Select Key Columns (ID Variables)",
            "These columns will be preserved as identifiers in the transposed result.",
        )
        self.key_list = ColumnChecklist(self.incom_data.columns, self.key_columns)
        self.key_list.changed.connect(self.on_key_selection_changed)
        self.key_checkboxes = self.key_list.checkboxes
        key_section.addWidget(self.key_list)
        main_layout.addWidget(key_section)

        data_section = ConfigSection(
            "Select Columns to Transpose (Value Variables)",
            "These columns will be transposed from columns to rows. Column names become 'Name' values, column data becomes 'Value' values.",
        )
        self.data_list = ColumnChecklist(self.incom_data.columns, self.data_columns)
        self.data_list.changed.connect(self.on_data_selection_changed)
        self.data_checkboxes = self.data_list.checkboxes
        data_section.addWidget(self.data_list)
        main_layout.addWidget(data_section)

        action_section = ConfigSection(
            "Missing Columns Handling",
            "How to handle columns that are selected but don't exist in the input data.",
        )
        self.action_combo = QComboBox()
        self.action_combo.addItems(["error", "warn", "ignore"])
        self.action_combo.setCurrentText(self.missing_action)
        self.action_combo.currentTextChanged.connect(self.on_action_changed)
        action_section.addWidget(self.action_combo)
        main_layout.addWidget(action_section)

        dock_layout.addLayout(main_layout)
        self.recursively_find_widgets(dock_layout)

    def process_data(self) -> None:
        """Transpose selected columns while maintaining key columns using Polars"""
        if self.incom_data is None:
            self.data = None
            return
        if not self.data_columns:
            # Unconfigured: pass input through so downstream nodes keep working.
            global_logger.debug(
                "📊 TransposeContent: No columns selected, passing input through"
            )
            self.data = self.incom_data
            return
        if self.incom_data is not None and self.data_columns:
            global_logger.debug(
                "📊 TransposeContent: Processing data for transpose operation"
            )
            try:
                available_columns = self.incom_data.columns

                # Validate columns exist
                missing = [
                    col for col in self.data_columns if col not in available_columns
                ]
                if missing:
                    if self.missing_action == "error":
                        global_logger.error(
                            f"❌ TransposeContent: Missing columns: {missing}"
                        )
                        raise ValueError(f"Missing columns: {missing}")
                    elif self.missing_action == "warn":
                        global_logger.warning(
                            f"⚠️ TransposeContent: Missing columns will be skipped: {missing}"
                        )
                        print(f"Warning: Missing columns will be skipped: {missing}")

                # Validate key columns exist
                missing_key_cols = [
                    col for col in self.key_columns if col not in available_columns
                ]
                if missing_key_cols:
                    global_logger.warning(
                        f"⚠️ TransposeContent: Missing key columns will be skipped: {missing_key_cols}"
                    )

                # Filter to existing columns only
                valid_key_cols = [
                    col for col in self.key_columns if col in available_columns
                ]
                valid_data_cols = [
                    col for col in self.data_columns if col in available_columns
                ]

                if not valid_data_cols:
                    global_logger.warning(
                        "⚠️ TransposeContent: No valid data columns found for transpose"
                    )
                    self.data = None
                    return

                global_logger.debug(
                    f"📊 TransposeContent: Index columns: {valid_key_cols}"
                )
                global_logger.debug(
                    f"📊 TransposeContent: Value columns: {valid_data_cols}"
                )

                # Perform transpose operation using Polars unpivot (replaces deprecated melt)
                self.data = self.incom_data.unpivot(
                    index=valid_key_cols,
                    on=valid_data_cols,
                    variable_name="Name",
                    value_name="Value",
                )

                global_logger.info(
                    f"✅ TransposeContent: Transpose completed - Result shape: {self.data.shape}"
                )

            except Exception as e:
                global_logger.error(
                    f"❌ TransposeContent: Error in transpose operation: {str(e)}"
                )
                print(f"Error in transpose operation: {str(e)}")
                self.data = None

    def get_code(self) -> str:
        """Generate Polars code for transpose operation"""
        if self.data is None or not self.incoming_variable:
            # Fallback: always define the output so downstream code never
            # NameErrors (or SyntaxErrors on an empty incoming variable).
            code = ["import polars as pl"]
            if self.incoming_variable:
                code.append(f"{self.variable_name} = {self.incoming_variable}")
            else:
                code.append(f"{self.variable_name} = pl.DataFrame()")
            return "\n".join(code) + "\n"

        code_lines = []

        # Add column validation if needed
        if self.missing_action != "ignore":
            data_cols_str = ", ".join(f"'{col}'" for col in self.data_columns)
            code_lines.extend(
                [
                    f"# Validate data columns",
                    f"missing = [col for col in [{data_cols_str}] if col not in {self.incoming_variable}.columns]",
                    f"if missing:",
                ]
            )
            if self.missing_action == "error":
                code_lines.append("    raise ValueError(f'Missing columns: {missing}')")
            else:  # warn
                code_lines.append(
                    "    print(f'Warning: Missing columns will be skipped: {missing}')"
                )
                code_lines.append("")

        # Validate and filter columns
        key_cols_str = ", ".join(f"'{col}'" for col in self.key_columns)
        data_cols_str = ", ".join(f"'{col}'" for col in self.data_columns)

        code_lines.extend(
            [
                f"# Filter to existing columns",
                f"valid_key_cols = [col for col in [{key_cols_str}] if col in {self.incoming_variable}.columns]",
                f"valid_data_cols = [col for col in [{data_cols_str}] if col in {self.incoming_variable}.columns]",
                f"",
                f"# Transpose operation using Polars unpivot",
                f"{self.variable_name} = {self.incoming_variable}.unpivot(",
                f"    index=valid_key_cols,",
                f"    on=valid_data_cols,",
                f"    variable_name='Name',",
                f"    value_name='Value'",
                f")",
            ]
        )

        return "\n".join(code_lines) + "\n"

    def on_key_selection_changed(self, checked: list) -> None:
        """Handle key columns checkbox changes"""
        self.key_columns = list(checked)
        global_logger.debug(
            f"📊 TransposeContent: Key columns updated: {self.key_columns}"
        )
        self.process_data()
        self.evaluate.emit()

    def on_data_selection_changed(self, checked: list) -> None:
        """Handle data columns checkbox changes"""
        self.data_columns = list(checked)
        global_logger.debug(
            f"📊 TransposeContent: Data columns updated: {self.data_columns}"
        )
        self.process_data()
        self.evaluate.emit()

    def on_action_changed(self, value: str) -> None:
        """Handle missing column action changes"""
        self.missing_action = value
        global_logger.debug(
            f"📊 TransposeContent: Missing action changed to: {self.missing_action}"
        )
        self.process_data()
        self.evaluate.emit()

    def serialize(self) -> dict:
        """Serialize node content"""
        res = super().serialize()
        res.update(
            {
                "key_columns": self.key_columns,
                "data_columns": self.data_columns,
                "missing_action": self.missing_action,
            }
        )
        return res

    def deserialize(self, data: dict, hashmap={}) -> bool:
        """Deserialize node content"""
        res = super().deserialize(data, hashmap)
        try:
            global_logger.debug("📊 TransposeContent: Deserializing Transpose node")

            self.key_columns = data.get("key_columns", [])
            self.data_columns = data.get("data_columns", [])
            self.missing_action = data.get("missing_action", "warn")

            global_logger.debug(
                f"📊 TransposeContent: Restored key columns: {self.key_columns}"
            )
            global_logger.debug(
                f"📊 TransposeContent: Restored data columns: {self.data_columns}"
            )
            global_logger.debug(
                f"📊 TransposeContent: Restored missing action: {self.missing_action}"
            )

            return True & res
        except Exception as e:
            global_logger.error(
                f"❌ TransposeContent: Deserialization failed: {str(e)}"
            )
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
        global_logger.info("🔧 TransposeNode: Initializing Transpose node")
        super().__init__(scene, inputs=[1], outputs=[1])
        global_logger.debug("📊 TransposeNode: Node created with 1 input and 1 output")
        self.eval()
        global_logger.trace("✅ TransposeNode: Initialization completed")

    def initInnerClasses(self) -> None:
        global_logger.debug("🔧 TransposeNode: Initializing inner classes")
        self.content: TransposeContent = TransposeContent(self)
        self.grNode: TriggerGraphicsNode = TriggerGraphicsNode(self)
        self.content.evaluate.connect(self.onInputChanged)
        self.param: list = []
        global_logger.trace("✅ TransposeNode: Inner classes initialized")

    def processInputs(self, input_values):
        global_logger.info("🔄 TransposeNode: Starting input processing")
        print("⚠️⚠️⚠️ Transpose ⚠️⚠️⚠️")

        try:
            input_node = self.getInput(0)
            socket_index = self.getSocketValue(input_node.outputs, self)
            input_value = input_values[0][socket_index]

            global_logger.debug(
                f"📊 TransposeNode: Retrieved input data, socket index: {socket_index}"
            )

            if input_value:
                global_logger.info(
                    "✅ TransposeNode: Input data received, processing..."
                )
                print("We have input")

                # Validate input data
                input_data = input_value.get("data")
                variable_name = input_value.get("variable_name", "unknown")

                if input_data is not None:
                    global_logger.info(
                        f"📊 TransposeNode: Processing DataFrame with shape {input_data.shape} for variable '{variable_name}'"
                    )

                    self.markDirty(False)
                    self.markInvalid(False)

                    # Store input data
                    self.content.incom_data = input_data
                    self.content.incoming_variable = variable_name

                    # Process the transpose operation
                    self.content.process_data()

                    # Validate output data
                    if hasattr(self.content, "data") and self.content.data is not None:
                        output_shape = self.content.data.shape
                        global_logger.info(
                            f"📊 TransposeNode: Output DataFrame shape: {output_shape}"
                        )

                        self.param = [
                            {
                                "data": self.content.data,
                                "variable_name": self.content.variable_name,
                            }
                        ]

                        self.evalChildren()
                        global_logger.info(
                            "✅ TransposeNode: Processing completed successfully"
                        )
                        return self.param
                    else:
                        global_logger.error(
                            "❌ TransposeNode: No output data generated after processing"
                        )
                        self.markDirty(True)
                        self.markInvalid(True)
                        return None
                else:
                    global_logger.warning(
                        "⚠️ TransposeNode: Input value contains no data"
                    )
                    self.markDirty(True)
                    self.markInvalid(True)
                    return None

            else:
                global_logger.warning("⚠️ TransposeNode: No input data available")
                print("We don't have input")
                self.markDirty(True)
                self.markInvalid(True)
                self.grNode.setToolTip("Input is not connected")
                return None

        except Exception as e:
            global_logger.error(
                f"❌ TransposeNode: Error during input processing: {str(e)}"
            )
            global_logger.critical(
                f"🚨 TransposeNode: Exception details: {type(e).__name__}: {str(e)}"
            )
            self.markDirty(True)
            self.markInvalid(True)
            self.grNode.setToolTip(f"Processing error: {str(e)}")
            return None

    def get_code(self) -> str:
        return self.content.get_code()
