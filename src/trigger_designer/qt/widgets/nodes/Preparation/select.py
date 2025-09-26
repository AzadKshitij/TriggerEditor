import polars as pl
from qtpy.QtWidgets import (
    QWidget,
    QLineEdit,
    QLayout,
    QVBoxLayout,
    QListWidget,
    QLabel,
    QTableView,
    QHBoxLayout,
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

from trigger_designer.qt.widgets.select_table_widget import (
    ComboBoxDelegate,
    SelectTableWidget,
    RowData,
)
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


class SelectContent(QDMNodeIconContentWidget, TriggerChangeHandler):
    """DataFrame column selection and modification widget.

    Provides comprehensive column management including:
    - Selection and filtering
    - Reordering and sorting
    - Type conversion and renaming
    - Metadata management

    Args:
        QDMNodeContentWidget (_type_): _description_

    Variables:
        columns (dict): {column_name: [is_selected, column_type, rename]}
        incoming_columns (list): [column_name]

    Extra:

    """

    evaluate = Signal()  # Emit when evaluate button is clicked

    def __init__(self, node: "TriggerNode", parent: Optional[QWidget] = None) -> None:
        super().__init__(node, parent)
        # local variables
        # self.old_data: dict = []
        self.table_data: list = []
        self.history = self.node.scene.history

        # incoming variables
        self.incoming_variable: str = ""
        self.incom_data: Optional[pl.DataFrame] = None

        # pass on variables
        self.data: Optional[pl.DataFrame] = None
        self.variable_name: str = f"var_select_{self.id}"

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
            if not self.table_data:
                self.table_data = [
                    RowData(True, col, str(self.incom_data[col].dtype))
                    for col in self.incom_data.columns
                ]

            # Initialize changes if not already present
            if not hasattr(self, "changes"):
                self.changes: dict = {
                    "selected_columns": [],
                    "rename_mapping": {},
                    "dtype_mapping": {},
                }

            # Create toolbar layout with fixed height
            toolbar_widget = QWidget()
            toolbar_layout = QHBoxLayout(toolbar_widget)
            toolbar_layout.setContentsMargins(0, 0, 0, 0)  # Remove margins
            toolbar_widget.setFixedHeight(40)  # Set fixed height for toolbar

            # Search box
            self.search_input = QLineEdit()
            self.search_input.setPlaceholderText("Search columns...")
            self.search_input.setClearButtonEnabled(True)
            # Set minimum height for search input
            self.search_input.setMinimumHeight(30)
            toolbar_layout.addWidget(self.search_input)

            # Move buttons
            self.up_btn = QPushButton()
            self.up_btn.setIcon(QIcon.fromTheme("go-up"))
            self.up_btn.setIconSize(QSize(12, 12))
            self.up_btn.setMinimumSize(QSize(30, 30))

            self.down_btn = QPushButton()
            self.down_btn.setIcon(QIcon.fromTheme("go-down"))
            self.down_btn.setIconSize(QSize(12, 12))
            self.down_btn.setMinimumSize(QSize(30, 30))

            toolbar_layout.addWidget(self.up_btn)
            toolbar_layout.addWidget(self.down_btn)

            # Options menu button
            self.options_btn = QPushButton()
            self.options_btn.setText("Options")  # Set text separately
            self.options_btn.setIcon(
                QIcon(":/qss_icons/dark/rc/arrow_down.png")
            )  # Set custom icon
            self.options_btn.setStyleSheet(
                """
                QPushButton {
                    text-align: center;
                    padding: 0px 0px 0px 10px;
                    margin: 0;
                }
                QPushButton::menu-indicator {
                    width: 0;
                    image: none;
                }
            """
            )
            # Configure button properties
            self.options_btn.setMinimumHeight(30)
            self.options_btn.setMinimumWidth(60)
            self.options_btn.setIconSize(QSize(12, 12))
            self.options_btn.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

            toolbar_layout.addWidget(self.options_btn)

            # Add toolbar to main layout
            dock_layout.addWidget(toolbar_widget)

            self.table_widget = SelectTableWidget(
                data=self.table_data, changes=self.changes, parent=self
            )

            # Create proxy model for filtering
            self.proxy_model = QSortFilterProxyModel(self)
            self.proxy_model.setFilterCaseSensitivity(
                Qt.CaseSensitivity.CaseInsensitive
            )  # Make search case-insensitive
            self.proxy_model.setSourceModel(self.table_widget)
            self.proxy_model.setFilterKeyColumn(-1)  # Filter on all columns

            self.table_view = QTableView()
            self.table_view.setModel(self.proxy_model)
            # self.table_view.setModel(self.table_widget)

            # Set the custom delegate for the 'Option' column (index 2)
            self.table_view.setItemDelegateForColumn(
                2, ComboBoxDelegate(self.table_view)
            )
            self.table_view.setItemDelegateForColumn(
                3, QStyledItemDelegate()
            )  # For rename column

            # self.table_view.setModel(self.table_widget)

            # Configure view properties
            self.table_view.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
            self.table_view.setSelectionBehavior(
                QTableView.SelectionBehavior.SelectRows
            )

            # Set stretch factors for columns
            header = self.table_view.horizontalHeader()
            header.resizeSection(0, 50)  # Checkbox column

            # Connect signals
            self.setup_connections()

            # Connect to the new data_processed signal instead
            self.table_widget.data_processed.connect(self.handleDataChanged)

            dock_layout.addWidget(self.table_view, 1)
        else:
            no_data_label = QLabel("No incoming data available")
            no_data_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_data_label.setStyleSheet("color: gray;")
            dock_layout.addWidget(no_data_label)

        # return layout

    def setup_connections(self) -> None:
        # Search functionality
        self.search_input.textChanged.connect(
            self.proxy_model.setFilterRegularExpression
        )
        # self.search_input.textChanged.connect(self.table_widget.filterRows)

        # Move row buttons
        self.up_btn.clicked.connect(
            lambda: self.table_widget.moveSelectedRow("up", self.table_view)
        )
        self.down_btn.clicked.connect(
            lambda: self.table_widget.moveSelectedRow("down", self.table_view)
        )

        # Options menu
        self.table_widget.setupOptionsMenu(self.options_btn, self.table_view)

    def _map_dtype_to_polars(self, dtype_str: str) -> Optional[pl.DataType]:
        """Map string data type to Polars data type"""
        dtype_mapping = {
            "String": pl.String,
            "Int64": pl.Int64,
            "Float64": pl.Float64,
            "Boolean": pl.Boolean,
            "Date": pl.Date,
            "Datetime": pl.Datetime,
            "List": pl.List,
            "Struct": pl.Struct,
            "Categorical": pl.Categorical,
            "Binary": pl.Binary,
            "Decimal": pl.Decimal,
            "Duration": pl.Duration,
            # Legacy pandas compatibility
            "object": pl.String,
            "int64": pl.Int64,
            "float64": pl.Float64,
            "bool": pl.Boolean,
            "datetime64": pl.Datetime,
        }
        return dtype_mapping.get(dtype_str)

    def _get_polars_type_string(self, dtype_str: str) -> str:
        """Get Polars type string for code generation"""
        type_string_mapping = {
            "String": "pl.String",
            "Int64": "pl.Int64",
            "Float64": "pl.Float64",
            "Boolean": "pl.Boolean",
            "Date": "pl.Date",
            "Datetime": "pl.Datetime",
            "List": "pl.List",
            "Struct": "pl.Struct",
            "Categorical": "pl.Categorical",
            "Binary": "pl.Binary",
            "Decimal": "pl.Decimal",
            "Duration": "pl.Duration",
            # Legacy pandas compatibility
            "object": "pl.String",
            "int64": "pl.Int64",
            "float64": "pl.Float64",
            "bool": "pl.Boolean",
            "datetime64": "pl.Datetime",
        }
        return type_string_mapping.get(dtype_str, "pl.String")

    def apply_changes(self) -> None:
        """Apply changes from self.changes to self.data"""
        # Select only the specified columns from incom_data
        if getattr(self, "changes", None) is not None:
            selected_columns = self.changes["selected_columns"]
            self.data = self.incom_data.select(selected_columns)

            # Apply data type changes if any
            for col, dtype in self.changes["dtype_mapping"].items():
                try:
                    # Map common data type names to Polars types
                    polars_dtype = self._map_dtype_to_polars(dtype)
                    if polars_dtype:
                        self.data = self.data.with_columns(
                            pl.col(col).cast(polars_dtype, strict=False).alias(col)
                        )
                except Exception as e:
                    print(f"Failed to convert column {col} to {dtype}: {str(e)}")

            # Apply renaming if any
            if self.changes["rename_mapping"]:
                rename_dict = self.changes["rename_mapping"]
                self.data = self.data.rename(rename_dict)

            print(
                "🐍 File: Preparation/select.py | Line: 279 | processInputs ~ self._is_invalid",
                self.node._is_invalid,
            )

    def process_data_changes(
        self, data_: list[list]
    ) -> tuple[list[str], dict[str, str], dict[str, str]]:
        # Store the changes in a serializable format
        self.changes = {
            "selected_columns": [],
            "rename_mapping": {},
            "dtype_mapping": {},
            "column_order": [],  # Add column order tracking
        }

        # Extract selected columns, their new names and data types
        for column_info in data_:
            column_name, data_type, new_name = column_info
            self.changes["selected_columns"].append(column_name)

            if new_name:
                self.changes["rename_mapping"][column_name] = new_name

            if data_type:
                self.changes["dtype_mapping"][column_name] = data_type

        return (
            self.changes["selected_columns"],
            self.changes["rename_mapping"],
            self.changes["dtype_mapping"],
        )

    def update_data_dtype(
        self, selected_columns: list[str], rename_mapping: dict, dtype_mapping: dict
    ) -> None:
        """Update self.data based on the processed changes"""
        # Select only the specified columns from incom_data
        self.data = self.incom_data.select(selected_columns)

        # Apply data type changes if any
        for col, dtype in dtype_mapping.items():
            try:
                polars_dtype = self._map_dtype_to_polars(dtype)
                if polars_dtype:
                    self.data = self.data.with_columns(
                        pl.col(col).cast(polars_dtype, strict=False).alias(col)
                    )
            except Exception as e:
                print(f"Failed to convert column {col} to {dtype}: {str(e)}")

        # Apply renaming if any
        if rename_mapping:
            self.data = self.data.rename(rename_mapping)

    def handleDataChanged(self, data_: list) -> None:
        if self.history.is_restoring_history:
            return

        print(
            "🐍 File: Preparation/select.py | Line: 322 | handleDataChanged ~ data_",
            data_,
            type(data_),
        )

        # Store old state before changes
        old_changes = {
            "selected_columns": (
                self.changes["selected_columns"].copy()
                if hasattr(self, "changes")
                else []
            ),
            "rename_mapping": (
                self.changes["rename_mapping"].copy()
                if hasattr(self, "changes")
                else {}
            ),
            "dtype_mapping": (
                self.changes["dtype_mapping"].copy() if hasattr(self, "changes") else {}
            ),
        }

        # Process the new changes
        self.process_data_changes(data_)
        self.apply_changes()

        # Store history only if there are actual changes
        if old_changes != self.changes:
            history_data = {
                "node": self.node,
                "old_changes": old_changes,
                "new_changes": {
                    "selected_columns": self.changes["selected_columns"].copy(),
                    "rename_mapping": self.changes["rename_mapping"].copy(),
                    "dtype_mapping": self.changes["dtype_mapping"].copy(),
                },
            }

            self.history.storeHistory(
                desc="Column Selection/Rename/Type Changed",
                data=history_data,
                setModified=True,
            )

        # self.node.scene.has_been_modified = True
        # self.node.scene.history.storeHistory("Input Modified")

        # self.process_data_changes(
        #     data_)
        # self.apply_changes()

        self.evaluate.emit()

    def history_stamp_callback(self, history_data: dict, is_undo: bool) -> None:
        """Callback for undo/redo operations"""
        if is_undo:
            # Undo operation
            self.changes = history_data["old_changes"]
        else:
            # Redo operation
            self.changes = history_data["new_changes"]

        # Apply the changes and update the table
        self.apply_changes()
        if hasattr(self, "table_widget"):
            self.table_widget.update_from_changes(self.changes)

    def _get_polars_type_string(self, dtype_str: str) -> str:
        """Get the string representation for Polars types in code generation"""
        type_string_mapping = {
            "String": "pl.String",
            "Int64": "pl.Int64",
            "Float64": "pl.Float64",
            "Boolean": "pl.Boolean",
            "Date": "pl.Date",
            "Datetime": "pl.Datetime",
            "List": "pl.List",
            "Struct": "pl.Struct",
            "Categorical": "pl.Categorical",
            "Binary": "pl.Binary",
            "Decimal": "pl.Decimal",
            "Duration": "pl.Duration",
            # Legacy pandas compatibility
            "object": "pl.String",
            "int64": "pl.Int64",
            "float64": "pl.Float64",
            "bool": "pl.Boolean",
            "datetime64": "pl.Datetime",
        }
        return type_string_mapping.get(dtype_str, "pl.String")

    def get_code(self) -> str:
        if self.data is None or self.incoming_variable is None:
            return ""

        code_lines = []

        # Get selected columns using the stored changes
        selected_columns = [f"'{col}'" for col in self.changes["selected_columns"]]
        columns_str = ", ".join(selected_columns)
        code_lines.append(
            f"{self.variable_name} = {self.incoming_variable}.select([{columns_str}])"
        )

        # Apply data type changes from stored changes
        for col, dtype in self.changes["dtype_mapping"].items():
            polars_dtype = self._map_dtype_to_polars(dtype)
            if polars_dtype:
                # Get the string representation for the type
                type_str = self._get_polars_type_string(dtype)
                code_lines.append(
                    f"{self.variable_name} = {self.variable_name}.with_columns("
                    f"pl.col('{col}').cast({type_str}, strict=False).alias('{col}'))"
                )

        # Apply column renaming from stored changes
        if self.changes["rename_mapping"]:
            rename_dict = self.changes["rename_mapping"]
            rename_str = ", ".join(
                [f"'{old}': '{new}'" for old, new in rename_dict.items()]
            )
            code_lines.append(
                f"{self.variable_name} = {self.variable_name}.rename({{{rename_str}}})"
            )

        return "\n".join(code_lines) + "\n"

    def serialize(self):
        res = super().serialize()
        res["table_data"] = self.table_data
        res["changes"] = getattr(
            self,
            "changes",
            {"selected_columns": [], "rename_mapping": {}, "dtype_mapping": {}},
        )
        return res

    def deserialize(self, data, hashmap={}):
        res = super().deserialize(data, hashmap)
        try:
            print("deserialize Select node")
            self.old_columns = data["table_data"]
            self.changes = data["changes"]
            return True & res
        except Exception as e:
            dumpException(e)
        return res


@register_node(PreparationNodes.SELECT, NodeTypes.PREPARATION)
class TriggerNode_Select(TriggerNode):
    icon = "node_select"
    node_code = PreparationNodes.SELECT
    node_title = "Select"
    node_type = NodeTypes.PREPARATION
    content_label_objname = "trigger_node_select"
    style = {}

    def __init__(self, scene) -> None:
        super().__init__(scene, inputs=[1], outputs=[3])
        self.eval()

    def initInnerClasses(self) -> None:
        self.content: SelectContent = SelectContent(self)
        self.grNode: TriggerGraphicsNode = TriggerGraphicsNode(self)
        self.content.evaluate.connect(self.onInputChanged)
        self.param: list = []

    def processInputs(self, input_values):
        print("⚠️⚠️⚠️ Select ⚠️⚠️⚠️")
        input_node = self.getInput(0)
        socket_index = self.getSocketValue(input_node.outputs, self)
        input_value = input_values[0][socket_index]
        # print("🐍 File: Preparation/select.py | Line: 322 | processInputs ~ input_value.get('data')",
        #       input_value.get('data'))

        if input_value:
            print("We have input")
            self.markDirty(False)
            self.markInvalid(False)
            # Custom processing logic for the Select node
            self.content.incom_data = input_value.get("data")
            self.content.incoming_variable = input_value.get("variable_name")
            # self.content.set_table_data()
            self.content.apply_changes()
            # self.content.set_table_widget()

            self.param = [
                {"data": self.content.data, "variable_name": self.content.variable_name}
            ]
            self.evalChildren()
            print(
                "🐍 File: Preparation/select.py | Line: 279 | processInputs ~ self._is_invalid",
                self._is_invalid,
            )

            return self.param
        else:
            print("We don't have input")
            self.markDirty(True)
            self.markInvalid(True)
            self.grNode.setToolTip("Input is not connected")
            print(
                "🐍 File: Preparation/select.py | Line: 292 | processInputs ~ self._is_invalid",
                self._is_invalid,
            )

            return None

    def get_code(self):
        return self.content.get_code()
