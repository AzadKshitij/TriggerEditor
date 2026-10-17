from typing import Optional, List, TYPE_CHECKING
import polars as pl
from qtpy.QtWidgets import (
    QMenu,
    QVBoxLayout,
    QWidget,
)
from qtpy.QtGui import QActionGroup, QPixmap
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
    frame_schema,
    frame_shape,
)
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget
from nodeeditor.utils_no_qt import dumpException
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
from trigger_designer.qt.helpers import global_logger
from trigger_designer.qt.widgets.common import (
    ColumnChecklist,
    ConfigSection,
    EmptyStateLabel,
    IconButton,
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
        # Stale widget from a previous build: the dock deletes its children on
        # rebuild, so the reference must not survive into ``dock_actions()``.
        self.action_button = None
        if self.incom_data is None:
            dock_layout.addWidget(EmptyStateLabel())
            return

        main_layout = QVBoxLayout()
        main_layout.setSpacing(2)
        main_layout.setContentsMargins(0, 0, 0, 0)

        total_columns = len(frame_schema(self.incom_data))

        key_section = ConfigSection(
            "Key columns",
            "Preserved as identifiers in the transposed result.",
        )
        self.key_section = key_section
        self.key_list = ColumnChecklist(
            list(frame_schema(self.incom_data)), self.key_columns
        )
        self.key_list.changed.connect(self.on_key_selection_changed)
        self.key_checkboxes = self.key_list.checkboxes
        key_section.addWidget(self.key_list)

        data_section = ConfigSection(
            "Columns to transpose",
            "These columns move from columns to rows: names become 'Name', "
            "data becomes 'Value'.",
        )
        self.data_section = data_section
        self.data_list = ColumnChecklist(
            list(frame_schema(self.incom_data)), self.data_columns
        )
        self.data_list.changed.connect(self.on_data_selection_changed)
        self.data_checkboxes = self.data_list.checkboxes
        data_section.addWidget(self.data_list)

        # Missing-column policy: an icon menu mounted on the dock's label row
        # (ConfigDock mounts ``dock_actions()`` there), so it costs no row of
        # its own and never spends a whole section on a set-once control.
        self.action_button = IconButton.themed(
            f"Missing columns: {self.missing_action}",
            rsm_icon=self.node.rsm.get("icon_options"),
            qss_fallback=":/qss_icons/dark/rc/arrow_down.png",
            theme_fallback=None,
        )
        menu = QMenu(self.action_button)
        policy_group = QActionGroup(menu)
        policy_group.setExclusive(True)
        for value in ("error", "warn", "ignore"):
            action = menu.addAction(value.capitalize())
            action.setCheckable(True)
            action.setChecked(value == self.missing_action)
            action.triggered.connect(
                lambda _checked=False, v=value: self.on_action_changed(v)
            )
            policy_group.addAction(action)
        self.action_button.setMenu(menu)

        dock_layout.addWidget(key_section)
        # Each list reports the height its rows need (capped), so the sections
        # hug them; spare pane height stays below instead of stretching a short
        # list into a mostly empty panel.
        dock_layout.addWidget(data_section)
        dock_layout.addStretch(1)
        self._refresh_transpose_counts(total_columns)
        self.recursively_find_widgets(dock_layout)

    def dock_actions(self) -> list:
        """One obvious action, mounted on the dock's label row."""
        button = getattr(self, "action_button", None)
        return [button] if button is not None else []

    def dock_context(self) -> tuple[list[tuple[str, str]], str]:
        """Configuration summary for the dock context strip."""
        chips: list[tuple[str, str]] = []
        values = len(self.data_columns)
        if values:
            chips.append((f"{values} value{'s' if values > 1 else ''}", "accent"))
        keys = len(self.key_columns)
        if keys:
            chips.append((f"{keys} key{'s' if keys > 1 else ''}", ""))
        return chips, f"{self.missing_action} on missing"

    def _refresh_transpose_counts(self, total_columns: Optional[int] = None) -> None:
        """Refresh the pane summary; counts are no longer rendered."""
        self.refresh_dock_context()

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
                available_columns = list(frame_schema(self.incom_data))

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
                # Unpivot widens Value to the common supertype of the value
                # columns, which is often outside the Select dropdown
                # (e.g. all-UInt32 in -> UInt32 out). Normalise the frame.
                self.data = normalize_to_supported_dtypes(self.data)

                global_logger.info(
                    f"✅ TransposeContent: Transpose completed - Result shape: {frame_shape(self.data)}"
                )

            except Exception as e:
                global_logger.error(
                    f"❌ TransposeContent: Error in transpose operation: {str(e)}"
                )
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

        code_lines = [
            "import polars as pl",
            "from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes",
        ]

        # Column names without collecting (incoming may be lazy).
        code_lines.append(
            f"_{self.id}_cols = ({self.incoming_variable}.collect_schema().names()"
            f" if isinstance({self.incoming_variable}, pl.LazyFrame)"
            f" else {self.incoming_variable}.columns)"
        )

        # Add column validation if needed
        if self.missing_action != "ignore":
            data_cols_str = ", ".join(f"'{col}'" for col in self.data_columns)
            code_lines.extend(
                [
                    f"# Validate data columns",
                    f"missing = [col for col in [{data_cols_str}] if col not in _{self.id}_cols]",
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
                f"valid_key_cols = [col for col in [{key_cols_str}] if col in _{self.id}_cols]",
                f"valid_data_cols = [col for col in [{data_cols_str}] if col in _{self.id}_cols]",
                f"",
                f"# Transpose operation using Polars unpivot",
                f"{self.variable_name} = {self.incoming_variable}.unpivot(",
                f"    index=valid_key_cols,",
                f"    on=valid_data_cols,",
                f"    variable_name='Name',",
                f"    value_name='Value'",
                f")",
                "# Widen unpivot supertypes into Select-supported dtypes",
                f"{self.variable_name} = normalize_to_supported_dtypes({self.variable_name})",
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
        self._refresh_transpose_counts()
        self.evaluate.emit()

    def on_data_selection_changed(self, checked: list) -> None:
        """Handle data columns checkbox changes"""
        self.data_columns = list(checked)
        global_logger.debug(
            f"📊 TransposeContent: Data columns updated: {self.data_columns}"
        )
        self.process_data()
        self._refresh_transpose_counts()
        self.evaluate.emit()

    def on_action_changed(self, value: str) -> None:
        """Handle missing column action changes"""
        self.missing_action = value
        button = getattr(self, "action_button", None)
        if button is not None:
            button.setToolTip(f"Missing columns: {value}")
        global_logger.debug(
            f"📊 TransposeContent: Missing action changed to: {self.missing_action}"
        )
        self.process_data()
        self._refresh_transpose_counts()
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

            return True and res
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

                # Validate input data
                input_data = input_value.get("data")
                variable_name = input_value.get("variable_name", "unknown")

                if input_data is not None:
                    global_logger.info(
                        f"📊 TransposeNode: Processing DataFrame with shape {frame_shape(input_data)} for variable '{variable_name}'"
                    )

                    # Store input data
                    self.content.incom_data = input_data
                    self.content.incoming_variable = variable_name

                    # Process the transpose operation
                    self.content.process_data()

                    # Validate output data
                    if hasattr(self.content, "data") and self.content.data is not None:
                        output_shape = frame_shape(self.content.data)
                        global_logger.info(
                            f"📊 TransposeNode: Output DataFrame shape: {output_shape}"
                        )

                        self.param = [
                            {
                                "data": self.content.data,
                                "variable_name": self.content.variable_name,
                            }
                        ]

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
                        self.grNode.setToolTip("Transpose failed: no output generated")
                        return None
                else:
                    global_logger.warning(
                        "⚠️ TransposeNode: Input value contains no data"
                    )
                    self.markDirty(True)
                    self.markInvalid(True)
                    self.grNode.setToolTip("Upstream node produced no data")
                    return None

            else:
                global_logger.warning("⚠️ TransposeNode: No input data available")
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
