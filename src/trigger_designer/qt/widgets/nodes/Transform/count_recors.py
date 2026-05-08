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

        if self.incom_data is not None:
            # Process data to get current count
            self.process_data()

            main_layout = QVBoxLayout()
            main_layout.setSpacing(5)
            main_layout.setContentsMargins(10, 10, 10, 10)

            # Title
            title_label = QLabel("Record Count")
            title_label.setStyleSheet(
                "font-weight: bold; font-size: 14px; padding: 5px;"
            )
            title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            main_layout.addWidget(title_label)

            # Display count with better formatting
            count_label = QLabel(f"{self.total_records:,}")
            count_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            count_label.setStyleSheet("""
                QLabel {
                    font-size: 20px;
                    font-weight: bold;
                    color: #2196F3;
                    background-color: #f5f5f5;
                    border: 1px solid #ddd;
                    border-radius: 5px;
                    padding: 10px;
                }
            """)
            main_layout.addWidget(count_label)

            # Info label
            info_label = QLabel("Total Records")
            info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            info_label.setStyleSheet("color: #666; font-size: 10px;")
            main_layout.addWidget(info_label)

            dock_layout.addLayout(main_layout)
        else:
            no_data_label = QLabel("No incoming data available")
            no_data_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_data_label.setStyleSheet("color: gray; font-style: italic;")
            dock_layout.addWidget(no_data_label)

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
                # Get the number of rows using Polars shape attribute
                self.total_records = self.incom_data.shape[0]

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
        if self.data is None or self.incoming_variable is None:
            return ""

        code_lines = []
        code_lines.append(f"# Count records in DataFrame")
        code_lines.append(
            f"{self.variable_name} = pl.DataFrame({{'Count': [{self.incoming_variable}.shape[0]]}})"
        )

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
                    global_logger.info(
                        f"🔢 CountRecordsNode: Processing DataFrame with shape {input_data.shape} for variable '{variable_name}'"
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
