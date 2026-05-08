from typing import Optional, TYPE_CHECKING
import polars as pl
from qtpy.QtWidgets import QWidget, QVBoxLayout, QLabel
from qtpy.QtGui import QPixmap
from qtpy.QtCore import Signal, Qt
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
from trigger_designer.qt.helpers import global_logger

if TYPE_CHECKING:
    from nodeeditor.node_scene import Scene
    from nodeeditor.node_node import Node
    import polars as pl


class CountRecordsContent(QDMNodeIconContentWidget, TriggerChangeHandler):
    """Simple record counter for DataFrame using Polars.
    Counts total number of rows in the input DataFrame.
    """

    evaluate = Signal()

    def __init__(self, node: "TriggerNode", parent: Optional[QWidget] = None) -> None:
        super().__init__(node, parent)
        global_logger.debug(
            "🔢 CountRecordsContent: Initializing Count Records node content widget"
        )
        self.node = node

        # Data tracking
        self.incoming_variable: str = ""
        self.incom_data: Optional[pl.DataFrame] = None
        self.data: Optional[pl.DataFrame] = None
        self.variable_name = f"var_count_{self.id}"

        # Count result
        self.total_records = 0
        global_logger.trace("🔢 CountRecordsContent: Initialization completed")

    @property
    def node(self) -> "TriggerNode":
        return self._node

    @node.setter
    def node(self, value: "TriggerNode") -> None:
        self._node = value

    def initUI(self, icon_: Optional[QPixmap] = None) -> None:
        icon: QPixmap = self.node.rsm.get(f"{self.node.icon}")
        super().initUI(icon)

    def create_layout(self, dock_layout: QVBoxLayout) -> None:
        global_logger.debug("🔢 CountRecordsContent: Creating layout")
        message_label = QLabel("No configuration needed. The output socket returns the row count.")
        message_label.setWordWrap(True)
        message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message_label.setStyleSheet(
            "color: gray; font-style: italic; padding: 12px;"
        )
        dock_layout.addWidget(message_label)

    def serialize(self):
        """Serialize the Count Records configuration"""
        res = super().serialize()
        res["total_records"] = self.total_records
        res["variable_name"] = self.variable_name
        return res

    def deserialize(self, data, hashmap={}):
        """Deserialize the Count Records configuration"""
        res = super().deserialize(data, hashmap)
        try:
            global_logger.debug(
                "🔢 CountRecordsContent: Deserializing Count Records node"
            )

            self.total_records = data.get("total_records", 0)
            self.variable_name = data.get("variable_name", f"var_count_{self.id}")

            return True & res
        except Exception as e:
            global_logger.error(
                f"❌ CountRecordsContent: Deserialization failed: {str(e)}"
            )
        return res

    def process_data(self) -> None:
        """Count total records in DataFrame using Polars"""
        if self.incom_data is not None:
            global_logger.debug(
                "🔢 CountRecordsContent: Processing data to count records"
            )
            try:
                if isinstance(self.incom_data, pl.LazyFrame):
                    self.total_records = self.incom_data.select(pl.len()).collect().item()
                else:
                    self.total_records = self.incom_data.height

                # Create result DataFrame with Polars
                self.data = pl.DataFrame({"Count": [self.total_records]})

                global_logger.info(
                    f"✅ CountRecordsContent: Successfully counted {self.total_records:,} records"
                )
            except Exception as e:
                global_logger.error(
                    f"❌ CountRecordsContent: Error counting records: {str(e)}"
                )
                self.total_records = 0
                self.data = None

    def get_code(self) -> str:
        """Generate Polars code for counting records"""
        if not self.incoming_variable:
            return ""

        code_lines = ["import polars as pl"]
        code_lines.append("# Count records in DataFrame")
        code_lines.append(
            f"_count_value = {self.incoming_variable}.select(pl.len()).collect().item() if hasattr({self.incoming_variable}, 'collect') else {self.incoming_variable}.height"
        )
        code_lines.append(
            f"{self.variable_name} = pl.DataFrame({{'Count': [_count_value]}})"
        )
        code_lines.append("del _count_value")

        return "\n".join(code_lines) + "\n"


@register_node(TransformNodes.COUNT_RECORDS, NodeTypes.TRANSFORM)
class TriggerNode_CountRecords(TriggerNode):
    icon = "node_count"
    node_code = TransformNodes.COUNT_RECORDS
    node_title = "Count Records"
    node_type = NodeTypes.TRANSFORM
    content_label_objname = "trigger_node_count_records"

    def __init__(self, scene) -> None:
        global_logger.info("🔧 CountRecordsNode: Initializing Count Records node")
        super().__init__(scene, inputs=[1], outputs=[1])
        global_logger.debug(
            "🔢 CountRecordsNode: Node created with 1 input and 1 output"
        )
        self.eval()
        global_logger.trace("✅ CountRecordsNode: Initialization completed")

    def initInnerClasses(self) -> None:
        global_logger.debug("🔧 CountRecordsNode: Initializing inner classes")
        self.content: CountRecordsContent = CountRecordsContent(self)
        self.grNode: TriggerGraphicsNode = TriggerGraphicsNode(self)
        self.content.evaluate.connect(self.onInputChanged)
        self.param: list = []
        global_logger.trace("✅ CountRecordsNode: Inner classes initialized")

    def processInputs(self, input_values):
        global_logger.info("🔄 CountRecordsNode: Starting input processing")
        print("⚠️⚠️⚠️ Count Records ⚠️⚠️⚠️")

        try:
            input_node = self.getInput(0)
            socket_index = self.getSocketValue(input_node.outputs, self)
            input_value = input_values[0][socket_index]

            global_logger.debug(
                f"🔢 CountRecordsNode: Retrieved input data, socket index: {socket_index}"
            )

            if input_value:
                global_logger.info(
                    "✅ CountRecordsNode: Input data received, processing..."
                )
                print("We have input")

                # Validate input data
                input_data = input_value.get("data")
                variable_name = input_value.get("variable_name", "unknown")

                if input_data is not None:
                    if isinstance(input_data, pl.LazyFrame):
                        input_shape = (
                            "lazy",
                            len(input_data.collect_schema().names()),
                        )
                    else:
                        input_shape = input_data.shape

                    global_logger.info(
                        f"🔢 CountRecordsNode: Processing DataFrame with shape {input_shape} for variable '{variable_name}'"
                    )

                    self.markDirty(False)
                    self.markInvalid(False)

                    # Store input data
                    self.content.incom_data = input_data
                    self.content.incoming_variable = variable_name

                    # Process the data to count records
                    self.content.process_data()

                    # Validate output data
                    if hasattr(self.content, "data") and self.content.data is not None:
                        output_shape = self.content.data.shape
                        global_logger.info(
                            f"🔢 CountRecordsNode: Output DataFrame shape: {output_shape}"
                        )
                        global_logger.info(
                            f"🔢 CountRecordsNode: Total records counted: {self.content.total_records:,}"
                        )

                        self.param = [
                            {
                                "data": self.content.data,
                                "variable_name": self.content.variable_name,
                            }
                        ]

                        self.evalChildren()
                        global_logger.info(
                            "✅ CountRecordsNode: Processing completed successfully"
                        )
                        return self.param
                    else:
                        global_logger.error(
                            "❌ CountRecordsNode: No output data generated after processing"
                        )
                        self.markDirty(True)
                        self.markInvalid(True)
                        return None
                else:
                    global_logger.warning(
                        "⚠️ CountRecordsNode: Input value contains no data"
                    )
                    self.markDirty(True)
                    self.markInvalid(True)
                    return None

            else:
                global_logger.warning("⚠️ CountRecordsNode: No input data available")
                print("We don't have input")
                self.markDirty(True)
                self.markInvalid(True)
                self.grNode.setToolTip("Input is not connected")
                return None

        except Exception as e:
            global_logger.error(
                f"❌ CountRecordsNode: Error during input processing: {str(e)}"
            )
            global_logger.critical(
                f"🚨 CountRecordsNode: Exception details: {type(e).__name__}: {str(e)}"
            )
            self.markDirty(True)
            self.markInvalid(True)
            self.grNode.setToolTip(f"Processing error: {str(e)}")
            return None

    def get_code(self):
        return self.content.get_code()
