import polars as pl
from qtpy.QtWidgets import (
    QWidget,
    QLineEdit,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QLabel,
    QTableView,
    QStyledItemDelegate,
    QSizePolicy,
    QSpacerItem,
    QListWidgetItem,
    QTableWidget,
    QTableWidgetItem,
    QCheckBox,
    QComboBox,
    QHeaderView,
    QPushButton,
)
from qtpy.QtGui import QPixmap, QIcon
from qtpy.QtCore import (
    Qt,
    QSaveFile,
    Signal,
    QVariant,
    QModelIndex,
    QSortFilterProxyModel,
    QSize,
)
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
from nodeeditor.node_content_widget import QDMNodeContentWidget
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget
from nodeeditor.utils_no_qt import dumpException

from trigger_designer.qt.helpers import global_logger
from typing import (
    Optional,
    TYPE_CHECKING,
    Any,
    Dict,
    List,
    OrderedDict,
    Type,
    cast,
    Union,
)

if TYPE_CHECKING:
    from nodeeditor.node_scene import Scene
    from nodeeditor.node_node import Node
    import polars as pl


class GroupByContent(QDMNodeIconContentWidget, TriggerChangeHandler):
    """DataFrame group-by and aggregation widget.

    Provides comprehensive grouping and aggregation functionality including:
    - Column selection for grouping
    - Aggregation function selection (count, sum, mean, min, max, etc.)
    - Column aliasing for results
    - Custom aggregation expressions

    Args:
        QDMNodeContentWidget (_type_): _description_

    Variables:
        incoming_columns (list): [column_name]
        actions_data (list): Configuration for groupby actions

    """

    evaluate = Signal()  # Emit when evaluate button is clicked

    def __init__(self, node: "TriggerNode", parent: Optional[QWidget] = None) -> None:
        super().__init__(node, parent)
        global_logger.debug("📊 GroupByContent: Initializing GroupBy node content widget")

        # Local variables
        self.history = self.node.scene.history

        # Incoming variables
        self.incoming_variable: str = ""
        self.incom_data: Optional[pl.DataFrame] = None

        global_logger.trace("📊 GroupByContent: Initialization completed")

        # Pass on variables
        self.data: Optional[pl.DataFrame] = None
        self.variable_name: str = f"var_groupby_{self.id}"

        # Configuration for operations
        self.changes: dict = {
            "group_by_columns": [],
            "aggregations": {},  # {column: {function: alias}}
        }

    @property
    def node(self) -> "TriggerNode":
        return self._node

    @node.setter
    def node(self, value: "TriggerNode") -> None:
        self._node = value

    def initUI(self, icon: Optional[QPixmap] = None) -> None:
        _icon: QPixmap = self.node.rsm.get(f"{self.node.icon}")
        super().initUI(_icon)

    def create_layout(self, dock_layout: QVBoxLayout) -> None:
        if self.incom_data is not None:
            global_logger.debug(f"📊 GroupByContent: Creating layout for {len(self.incom_data.columns)} columns")

            # Initialize changes if not already present
            if not hasattr(self, "changes") or not self.changes:
                self.changes = {
                    "group_by_columns": [],
                    "aggregations": {},
                }

            # Create main widget for the GroupBy configuration
            main_widget = QWidget()
            main_layout = QVBoxLayout(main_widget)
            main_layout.setContentsMargins(5, 5, 5, 5)

            # Fields Section (Top)
            fields_label = QLabel("Fields:")
            fields_label.setStyleSheet("font-weight: bold; font-size: 12px; padding: 2px;")
            main_layout.addWidget(fields_label)

            # Create fields table (shows available columns)
            self.create_fields_table()
            main_layout.addWidget(self.fields_table)

            # Add button
            add_button_layout = QHBoxLayout()
            self.add_btn = QPushButton("Add")
            self.add_btn.setMinimumHeight(25)
            self.add_btn.setMaximumWidth(80)
            self.add_btn.clicked.connect(self.add_selected_field)
            add_button_layout.addWidget(self.add_btn)
            add_button_layout.addStretch()
            main_layout.addLayout(add_button_layout)

            # Actions Section (Bottom)
            actions_label = QLabel("Actions:")
            actions_label.setStyleSheet("font-weight: bold; font-size: 12px; padding: 2px; margin-top: 10px;")
            main_layout.addWidget(actions_label)

            # Create actions table
            self.create_actions_table()
            main_layout.addWidget(self.actions_table)

            # Restore previously saved actions if any
            if hasattr(self, 'actions_data'):
                self.restore_actions_table()

            # Control buttons for actions table
            actions_button_layout = QHBoxLayout()

            self.remove_btn = QPushButton("Remove")
            self.remove_btn.setMinimumHeight(25)
            self.remove_btn.setMaximumWidth(80)
            self.remove_btn.clicked.connect(self.remove_selected_action)
            actions_button_layout.addWidget(self.remove_btn)

            self.apply_btn = QPushButton("Apply")
            self.apply_btn.setMinimumHeight(25)
            self.apply_btn.setMaximumWidth(80)
            self.apply_btn.clicked.connect(self.apply_groupby)
            actions_button_layout.addWidget(self.apply_btn)

            actions_button_layout.addStretch()
            main_layout.addLayout(actions_button_layout)

            dock_layout.addWidget(main_widget)

        else:
            no_data_label = QLabel("No incoming data available")
            no_data_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_data_label.setStyleSheet("color: gray;")
            dock_layout.addWidget(no_data_label)

    def create_fields_table(self) -> None:
        """Create the fields table showing available columns"""
        global_logger.debug("📊 GroupByContent: Creating fields table")

        self.fields_table = QTableWidget()
        self.fields_table.setColumnCount(2)
        self.fields_table.setHorizontalHeaderLabels(["Field", "Type"])

        # Set row count based on available columns
        self.fields_table.setRowCount(len(self.incom_data.columns))

        # Populate the table with column information
        for row, column in enumerate(self.incom_data.columns):
            # Field name (selectable)
            field_item = QTableWidgetItem(column)
            field_item.setFlags(field_item.flags() | Qt.ItemFlag.ItemIsSelectable)
            self.fields_table.setItem(row, 0, field_item)

            # Data type
            dtype = str(self.incom_data[column].dtype)
            type_item = QTableWidgetItem(dtype)
            type_item.setFlags(type_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.fields_table.setItem(row, 1, type_item)

        # Configure table properties
        self.fields_table.setMaximumHeight(120)
        self.fields_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        header = self.fields_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)

    def create_actions_table(self) -> None:
        """Create the actions table for configuring groupby operations"""
        global_logger.debug("📊 GroupByContent: Creating actions table")

        self.actions_table = QTableWidget()
        self.actions_table.setColumnCount(3)
        self.actions_table.setHorizontalHeaderLabels(["Field", "Action", "Output Field Name"])

        # Available aggregation functions
        self.aggregation_functions = [
            "GroupBy", "Count", "Sum", "Mean", "Min", "Max", 
            "Std", "Var", "Median", "First", "Last",
            "N_Unique", "List"
        ]

        # Initially empty - rows added when user clicks Add
        self.actions_table.setRowCount(0)

        # Configure table properties
        header = self.actions_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        
        # Connect to update changes when table items are changed
        self.actions_table.itemChanged.connect(self.safe_update_groupby_data)

    def add_selected_field(self) -> None:
        """Add selected field from fields table to actions table"""
        if not hasattr(self, 'fields_table') or not hasattr(self, 'actions_table'):
            return

        selected_rows = self.fields_table.selectionModel().selectedRows()
        if not selected_rows:
            global_logger.warning("⚠️ GroupByContent: No field selected to add")
            return

        for index in selected_rows:
            row = index.row()
            field_name = self.fields_table.item(row, 0).text()

            # Check if field already exists in actions table
            if self.field_exists_in_actions(field_name):
                global_logger.warning(f"⚠️ GroupByContent: Field '{field_name}' already added")
                continue

            # Add new row to actions table
            self.add_action_row(field_name)
            global_logger.debug(f"📊 GroupByContent: Added field '{field_name}' to actions")

    def field_exists_in_actions(self, field_name: str) -> bool:
        """Check if field already exists in actions table"""
        for row in range(self.actions_table.rowCount()):
            if self.actions_table.item(row, 0).text() == field_name:
                return True
        return False

    def add_action_row(self, field_name: str) -> None:
        """Add a new row to the actions table"""
        row = self.actions_table.rowCount()
        self.actions_table.insertRow(row)

        # Field name (read-only)
        field_item = QTableWidgetItem(field_name)
        field_item.setFlags(field_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.actions_table.setItem(row, 0, field_item)

        # Action dropdown
        action_combo = QComboBox()
        action_combo.addItems(self.aggregation_functions)
        action_combo.setCurrentText("Count")  # Default to Count
        action_combo.currentTextChanged.connect(lambda: self.on_action_changed(row))
        self.actions_table.setCellWidget(row, 1, action_combo)

        # Output field name (initially based on default action)
        output_name = f"Count_{field_name}"
        output_item = QTableWidgetItem(output_name)
        # Connect to update changes when output name is edited
        output_item.itemChanged = self.update_groupby_data
        self.actions_table.setItem(row, 2, output_item)
        
        # Update changes after adding the row
        try:
            self.update_groupby_data()
        except Exception as e:
            global_logger.error(f"❌ GroupByContent: Error updating data after adding row: {str(e)}")

    def on_action_changed(self, row: int) -> None:
        """Handle action dropdown changes and update output field name accordingly"""
        if row >= self.actions_table.rowCount():
            return

        action_combo = self.actions_table.cellWidget(row, 1)
        field_name = self.actions_table.item(row, 0).text()
        action = action_combo.currentText()

        # Generate appropriate prefix based on action
        prefix_map = {
            "GroupBy": "",
            "Count": "Count_",
            "Sum": "Sum_",
            "Mean": "Avg_",
            "Min": "Min_",
            "Max": "Max_",
            "Std": "Std_",
            "Var": "Var_",
            "Median": "Median_",
            "First": "First_",
            "Last": "Last_",
            "N_Unique": "Unique_",
            "List": "List_"
        }

        prefix = prefix_map.get(action, "")
        if action == "GroupBy":
            output_name = field_name  # No prefix for GroupBy
        else:
            output_name = f"{prefix}{field_name}"

        # Update the output field name
        output_item = self.actions_table.item(row, 2)
        if output_item:
            output_item.setText(output_name)

        global_logger.debug(f"📊 GroupByContent: Updated action for '{field_name}' to '{action}' with output '{output_name}'")
        
        # Update changes when action is changed
        try:
            self.update_groupby_data()
        except Exception as e:
            global_logger.error(f"❌ GroupByContent: Error updating data after action change: {str(e)}")

    def remove_selected_action(self) -> None:
        """Remove selected row from actions table"""
        if not hasattr(self, 'actions_table'):
            return

        selected_rows = self.actions_table.selectionModel().selectedRows()
        if not selected_rows:
            global_logger.warning("⚠️ GroupByContent: No action selected to remove")
            return

        # Remove rows in reverse order to maintain correct indices
        for index in sorted(selected_rows, reverse=True):
            row = index.row()
            field_name = self.actions_table.item(row, 0).text()
            self.actions_table.removeRow(row)
            global_logger.debug(f"📊 GroupByContent: Removed action for field '{field_name}'")
        
        # Update changes after removing rows
        try:
            self.update_groupby_data()
        except Exception as e:
            global_logger.error(f"❌ GroupByContent: Error updating data after removing rows: {str(e)}")

    def safe_update_groupby_data(self, *args) -> None:
        """Safely update groupby data with error handling"""
        try:
            self.update_groupby_data()
        except Exception as e:
            global_logger.error(f"❌ GroupByContent: Safe update error: {str(e)}")
            # Don't re-raise the exception to prevent UI crashes

    def update_groupby_data(self) -> None:
        """Update internal groupby_data from actions table state"""
        if not hasattr(self, 'actions_table') or not self.actions_table:
            return

        # Ensure changes dict exists
        if not hasattr(self, 'changes'):
            self.changes = {"group_by_columns": [], "aggregations": {}}

        self.changes["group_by_columns"] = []
        self.changes["aggregations"] = {}

        for row in range(self.actions_table.rowCount()):
            field_item = self.actions_table.item(row, 0)
            if not field_item:
                continue
            field_name = field_item.text()

            # Get action from dropdown - safely handle None case
            action_combo = self.actions_table.cellWidget(row, 1)
            if not action_combo:
                continue
            action = action_combo.currentText()

            # Get output field name (alias)
            alias_item = self.actions_table.item(row, 2)
            alias = alias_item.text() if alias_item else field_name

            if action == "GroupBy":
                self.changes["group_by_columns"].append(field_name)
            else:
                # Convert action names to lowercase for polars functions
                function_map = {
                    "Count": "count",
                    "Sum": "sum", 
                    "Mean": "mean",
                    "Min": "min",
                    "Max": "max",
                    "Std": "std",
                    "Var": "var", 
                    "Median": "median",
                    "First": "first",
                    "Last": "last",
                    "N_Unique": "n_unique",
                    "List": "list"
                }

                polars_function = function_map.get(action, "count")
                self.changes["aggregations"][field_name] = {
                    "function": polars_function,
                    "alias": alias
                }
        
        # Debug logging to verify changes are being stored
        try:
            global_logger.debug(f"🔧 GroupByContent: Updated changes - GroupBy columns: {self.changes['group_by_columns']}")
            global_logger.debug(f"🔧 GroupByContent: Updated changes - Aggregations: {self.changes['aggregations']}")
        except Exception as e:
            global_logger.error(f"❌ GroupByContent: Error in debug logging: {str(e)}")

    def apply_groupby(self) -> None:
        """Apply the GroupBy operations to the data"""
        global_logger.info("📊 GroupByContent: Applying GroupBy operations")

        if self.incom_data is None:
            global_logger.warning("⚠️ GroupByContent: No input data available for GroupBy")
            return

        self.update_groupby_data()

        group_by_columns = self.changes["group_by_columns"]
        aggregations = self.changes["aggregations"]

        if not group_by_columns and not aggregations:
            global_logger.warning("⚠️ GroupByContent: No operations configured")
            return

        global_logger.debug(f"📊 GroupByContent: Grouping by columns: {group_by_columns}")
        global_logger.debug(f"📊 GroupByContent: Applying aggregations: {list(aggregations.keys())}")

        try:
            available_columns = self.incom_data.columns

            if group_by_columns:
                # Validate that group by columns exist
                valid_group_columns = [col for col in group_by_columns if col in available_columns]

                if not valid_group_columns:
                    global_logger.error("❌ GroupByContent: No valid group by columns found")
                    return

                # Start grouping
                grouped = self.incom_data.group_by(valid_group_columns)

                # Build aggregation expressions
                agg_expressions = []

                for column, config in aggregations.items():
                    if column not in available_columns:
                        global_logger.warning(f"⚠️ GroupByContent: Skipping missing column '{column}'")
                        continue

                    func_name = config["function"]
                    alias = config["alias"]

                    # Create Polars expression based on aggregation function
                    if func_name == "count":
                        expr = pl.len().alias(alias)
                    elif func_name == "sum":
                        expr = pl.col(column).sum().alias(alias)
                    elif func_name == "mean":
                        expr = pl.col(column).mean().alias(alias)
                    elif func_name == "min":
                        expr = pl.col(column).min().alias(alias)
                    elif func_name == "max":
                        expr = pl.col(column).max().alias(alias)
                    elif func_name == "std":
                        expr = pl.col(column).std().alias(alias)
                    elif func_name == "var":
                        expr = pl.col(column).var().alias(alias)
                    elif func_name == "median":
                        expr = pl.col(column).median().alias(alias)
                    elif func_name == "first":
                        expr = pl.col(column).first().alias(alias)
                    elif func_name == "last":
                        expr = pl.col(column).last().alias(alias)
                    elif func_name == "n_unique":
                        expr = pl.col(column).n_unique().alias(alias)
                    elif func_name == "list":
                        expr = pl.col(column).list().alias(alias)
                    else:
                        global_logger.warning(f"⚠️ GroupByContent: Unknown aggregation function '{func_name}'")
                        continue

                    agg_expressions.append(expr)

                # Apply aggregation
                if agg_expressions:
                    self.data = grouped.agg(agg_expressions)
                else:
                    # If no aggregations specified, just do a count
                    self.data = grouped.agg(pl.len().alias("count"))
            else:
                # No grouping, just apply aggregations to entire dataset
                agg_expressions = []
                for column, config in aggregations.items():
                    if column not in available_columns:
                        global_logger.warning(f"⚠️ GroupByContent: Skipping missing column '{column}'")
                        continue

                    func_name = config["function"]
                    alias = config["alias"]

                    if func_name == "count":
                        expr = pl.len().alias(alias)
                    else:
                        expr = getattr(pl.col(column), func_name)().alias(alias)

                    agg_expressions.append(expr)

                if agg_expressions:
                    self.data = self.incom_data.select(agg_expressions)

            global_logger.info(f"✅ GroupByContent: GroupBy completed - Result shape: {self.data.shape}")

            # Emit evaluate signal to update downstream nodes
            self.evaluate.emit()

        except Exception as e:
            global_logger.error(f"❌ GroupByContent: GroupBy operation failed: {str(e)}")
            self.data = None

    def reset_configuration(self) -> None:
        """Reset the GroupBy configuration"""
        global_logger.debug("📊 GroupByContent: Resetting GroupBy configuration")

        if hasattr(self, 'actions_table'):
            # Clear all rows from actions table
            self.actions_table.setRowCount(0)

        # Clear changes
        self.changes = {
            "group_by_columns": [],
            "aggregations": {},
        }

        global_logger.info("✅ GroupByContent: Configuration reset completed")

    def get_code(self) -> str:
        """Generate Polars code for the GroupBy operation"""
        if self.data is None or self.incoming_variable is None:
            return ""

        code_lines = []

        group_by_columns = self.changes["group_by_columns"]
        aggregations = self.changes["aggregations"]

        global_logger.info(f"GroupBy columns: {group_by_columns}")
        global_logger.info(f"Aggregations: {aggregations}")

        # If no operations configured at all, pass through
        if not group_by_columns and not aggregations:
            return f"# No GroupBy operation configured\n{self.variable_name} = {self.incoming_variable}\n"

        # Build aggregation expressions
        agg_expressions = []
        for column, config in aggregations.items():
            func_name = config["function"]
            alias = config["alias"]

            if func_name == "count":
                agg_expressions.append(f"pl.len().alias('{alias}')")
            elif func_name in ["sum", "mean", "min", "max", "std", "var", "median", "first", "last", "n_unique"]:
                agg_expressions.append(f"pl.col('{column}').{func_name}().alias('{alias}')")
            elif func_name == "list":
                agg_expressions.append(f"pl.col('{column}').list().alias('{alias}')")

        if group_by_columns:
            # Group by operation with aggregations
            group_cols_str = ", ".join([f"'{col}'" for col in group_by_columns])
            
            if not agg_expressions:
                agg_expressions.append("pl.len().alias('count')")

            agg_str = ",\n    ".join(agg_expressions)

            code_lines.append(f"{self.variable_name} = {self.incoming_variable}.group_by([{group_cols_str}]).agg([")
            code_lines.append(f"    {agg_str}")
            code_lines.append("])")
        else:
            # Just aggregations without grouping (entire dataset)
            if agg_expressions:
                agg_str = ",\n    ".join(agg_expressions)
                code_lines.append(f"{self.variable_name} = {self.incoming_variable}.select([")
                code_lines.append(f"    {agg_str}")
                code_lines.append("])")
            else:
                code_lines.append(f"{self.variable_name} = {self.incoming_variable}")

        return "\n".join(code_lines) + "\n"

    def serialize(self):
        """Serialize the GroupBy configuration"""
        res = super().serialize()

        # Serialize the actions table configuration
        actions_data = []
        if hasattr(self, 'actions_table'):
            for row in range(self.actions_table.rowCount()):
                field_name = self.actions_table.item(row, 0).text()
                action_combo = self.actions_table.cellWidget(row, 1)
                action = action_combo.currentText()
                output_name = self.actions_table.item(row, 2).text()

                actions_data.append({
                    "field": field_name,
                    "action": action,
                    "output_name": output_name
                })

        res["actions_data"] = actions_data
        res["changes"] = getattr(
            self,
            "changes", 
            {"group_by_columns": [], "aggregations": {}}
        )
        return res

    def deserialize(self, data, hashmap={}):
        """Deserialize the GroupBy configuration"""
        res = super().deserialize(data, hashmap)
        try:
            global_logger.debug("📊 GroupByContent: Deserializing GroupBy node")

            self.changes = data.get("changes", {
                "group_by_columns": [], 
                "aggregations": {}
            })

            # Restore actions table data if available
            self.actions_data = data.get("actions_data", [])

            return True & res
        except Exception as e:
            global_logger.error(f"❌ GroupByContent: Deserialization failed: {str(e)}")
            dumpException(e)
        return res

    def restore_actions_table(self):
        """Restore actions table from deserialized data"""
        if hasattr(self, 'actions_data') and hasattr(self, 'actions_table'):
            for action_config in self.actions_data:
                field_name = action_config["field"]
                action = action_config["action"] 
                output_name = action_config["output_name"]

                # Add the row
                self.add_action_row(field_name)
                row = self.actions_table.rowCount() - 1

                # Set the action
                action_combo = self.actions_table.cellWidget(row, 1)
                action_combo.setCurrentText(action)

                # Set the output name
                output_item = self.actions_table.item(row, 2)
                output_item.setText(output_name)
            
            # Update changes after restoring all actions
            self.update_groupby_data()


@register_node(PreparationNodes.GROUPBY, NodeTypes.PREPARATION) 
class TriggerNode_GroupBy(TriggerNode):
    icon = "node_groupby"
    node_code = PreparationNodes.GROUPBY
    node_title = "GroupBy"
    node_type = NodeTypes.PREPARATION
    content_label_objname = "trigger_node_groupby"
    style = {}

    def __init__(self, scene) -> None:
        global_logger.info("🔧 GroupByNode: Initializing GroupBy node")
        super().__init__(scene, inputs=[1], outputs=[3])
        global_logger.debug("📊 GroupByNode: Node created with 1 input and 3 outputs")
        self.eval()
        global_logger.trace("✅ GroupByNode: Initialization completed")

    def initInnerClasses(self) -> None:
        global_logger.debug("🔧 GroupByNode: Initializing inner classes")
        self.content: GroupByContent = GroupByContent(self)
        self.grNode: TriggerGraphicsNode = TriggerGraphicsNode(self)
        self.content.evaluate.connect(self.onInputChanged)
        self.param: list = []
        global_logger.trace("✅ GroupByNode: Inner classes initialized")

    def processInputs(self, input_values):
        global_logger.info("🔄 GroupByNode: Starting input processing")
        print("⚠️⚠️⚠️ GroupBy ⚠️⚠️⚠️")
        
        try:
            input_node = self.getInput(0)
            socket_index = self.getSocketValue(input_node.outputs, self)
            input_value = input_values[0][socket_index]
            
            global_logger.debug(f"📊 GroupByNode: Retrieved input data, socket index: {socket_index}")

            if input_value:
                global_logger.info("✅ GroupByNode: Input data received, processing...")
                print("We have input")
                
                # Validate input data
                input_data = input_value.get("data")
                variable_name = input_value.get("variable_name", "unknown")
                
                if input_data is not None:
                    global_logger.info(f"📊 GroupByNode: Processing DataFrame with shape {input_data.shape} for variable '{variable_name}'")
                    
                    self.markDirty(False)
                    self.markInvalid(False)
                    
                    # Store input data
                    self.content.incom_data = input_data
                    self.content.incoming_variable = variable_name
                    
                    # Update changes to ensure they're current before applying
                    if hasattr(self.content, 'actions_table') and hasattr(self.content, 'update_groupby_data'):
                        try:
                            self.content.update_groupby_data()
                        except Exception as e:
                            global_logger.error(f"❌ GroupByNode: Error updating groupby data: {str(e)}")
                    
                    # If we have configured groupby operations and data, apply them
                    if (hasattr(self.content, 'changes') and 
                        (self.content.changes.get("group_by_columns") or self.content.changes.get("aggregations"))):
                        self.content.apply_groupby()
                    else:
                        # No groupby configuration yet, pass through original data
                        self.content.data = input_data
                        global_logger.debug("📊 GroupByNode: No GroupBy configuration, passing through data")
                    
                    # Validate output data
                    if hasattr(self.content, 'data') and self.content.data is not None:
                        output_shape = self.content.data.shape
                        global_logger.info(f"📊 GroupByNode: Output DataFrame shape: {output_shape}")
                        
                        self.param = [
                            {"data": self.content.data, "variable_name": self.content.variable_name}
                        ]
                        
                        self.evalChildren()
                        global_logger.info("✅ GroupByNode: Processing completed successfully")
                        
                        return self.param
                    else:
                        global_logger.error("❌ GroupByNode: No output data generated after processing")
                        self.markDirty(True)
                        self.markInvalid(True)
                        return None
                else:
                    global_logger.warning("⚠️ GroupByNode: Input value contains no data")
                    self.markDirty(True)
                    self.markInvalid(True)
                    return None
                    
            else:
                global_logger.warning("⚠️ GroupByNode: No input data available")
                print("We don't have input")
                self.markDirty(True)
                self.markInvalid(True)
                self.grNode.setToolTip("Input is not connected")
                return None
                
        except Exception as e:
            global_logger.error(f"❌ GroupByNode: Error during input processing: {str(e)}")
            global_logger.critical(f"🚨 GroupByNode: Exception details: {type(e).__name__}: {str(e)}")
            self.markDirty(True)
            self.markInvalid(True)
            self.grNode.setToolTip(f"Processing error: {str(e)}")
            return None

    def get_code(self):
        return self.content.get_code()
