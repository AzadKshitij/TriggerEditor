import polars as pl
from qtpy.QtWidgets import (
    QWidget,
    QLineEdit,
    QLayout,
    QVBoxLayout,
    QListWidget,
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
from trigger_designer.qt.widgets.common import EmptyStateLabel
from nodeeditor.utils_no_qt import dumpException

from trigger_designer.qt.widgets.select_table_widget import (
    ComboBoxDelegate,
    SelectTableWidget,
    RowData,
)
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
        global_logger.debug("📋 SelectContent: Initializing Select node content widget")

        # local variables
        # self.old_data: dict = []
        self.table_data: list = []
        self.history = self.node.scene.history

        # incoming variables
        self.incoming_variable: str = ""
        self.incom_data: Optional[pl.DataFrame] = None

        global_logger.trace("📋 SelectContent: Initialization completed")

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
            # Initialize table_data if not already present (e.g., from deserialization)
            if not self.table_data:
                self.table_data = [
                    RowData(True, col, str(self.incom_data[col].dtype))
                    for col in self.incom_data.columns
                ]

            # Initialize changes if not already present (e.g., from deserialization)
            if not hasattr(self, "changes") or not self.changes:
                self.changes: dict = {
                    "selected_columns": list(
                        self.incom_data.columns
                    ),  # Select all by default
                    "rename_mapping": {},
                    "dtype_mapping": {},
                }

            # Ensure selected_columns has default values if empty
            if not self.changes.get("selected_columns"):
                self.changes["selected_columns"] = list(self.incom_data.columns)

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
            dock_layout.addWidget(EmptyStateLabel())

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

    def _date_parse_formats(self) -> list[str]:
        return [
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%Y.%m.%d",
            "%d-%m-%Y",
            "%d/%m/%Y",
            "%d.%m.%Y",
            "%m-%d-%Y",
            "%m/%d/%Y",
            "%m.%m.%Y",
            "%d %b %Y",
            "%d %B %Y",
            "%b %d %Y",
            "%B %d %Y",
            "%d-%b-%Y",
            "%d-%B-%Y",
        ]

    def _datetime_parse_formats(self) -> list[str]:
        base_date_formats = self._date_parse_formats()
        time_suffixes = [
            " %H:%M:%S",
            " %H:%M",
            "T%H:%M:%S",
            "T%H:%M",
        ]

        formats: list[str] = []
        for date_format in base_date_formats:
            for suffix in time_suffixes:
                formats.append(f"{date_format}{suffix}")

        formats.extend(
            [
                "%d %b %Y %H:%M:%S",
                "%d %B %Y %H:%M:%S",
                "%b %d %Y %H:%M:%S",
                "%B %d %Y %H:%M:%S",
                "%d %b %Y %H:%M",
                "%d %B %Y %H:%M",
                "%b %d %Y %H:%M",
                "%B %d %Y %H:%M",
            ]
        )
        return formats

    def _build_dtype_conversion_expr(self, col: str, dtype: str) -> Optional[pl.Expr]:
        """Build a Polars expression that converts a column to the requested dtype."""
        polars_dtype = self._map_dtype_to_polars(dtype)
        if polars_dtype is None:
            return None

        if polars_dtype not in (pl.Date, pl.Datetime):
            return pl.col(col).cast(polars_dtype, strict=False).alias(col)

        text_expr = pl.col(col).cast(pl.String, strict=False)

        if polars_dtype == pl.Date:
            parse_exprs: list[pl.Expr] = []
            parse_exprs.extend(
                text_expr.str.strptime(pl.Date, fmt, strict=False, exact=True)
                for fmt in self._date_parse_formats()
            )
            parse_exprs.extend(
                text_expr.str.strptime(pl.Datetime, fmt, strict=False, exact=True).cast(
                    pl.Date, strict=False
                )
                for fmt in self._datetime_parse_formats()
            )
            parse_exprs.append(text_expr.str.to_date(strict=False))
            parse_exprs.append(pl.col(col).cast(pl.Date, strict=False))
            return pl.coalesce(parse_exprs).alias(col)

        parse_exprs = []
        parse_exprs.extend(
            text_expr.str.strptime(pl.Datetime, fmt, strict=False, exact=True)
            for fmt in self._datetime_parse_formats()
        )
        parse_exprs.extend(
            text_expr.str.strptime(pl.Date, fmt, strict=False, exact=True).cast(
                pl.Datetime, strict=False
            )
            for fmt in self._date_parse_formats()
        )
        parse_exprs.append(text_expr.str.to_datetime(strict=False))
        parse_exprs.append(pl.col(col).cast(pl.Datetime, strict=False))
        return pl.coalesce(parse_exprs).alias(col)

    def _build_dtype_conversion_code(self, col: str, dtype: str) -> Optional[str]:
        """Build generated code for converting a column to the requested dtype."""
        polars_dtype = self._map_dtype_to_polars(dtype)
        if polars_dtype is None:
            return None

        if polars_dtype not in (pl.Date, pl.Datetime):
            type_str = self._get_polars_type_string(dtype)
            return f"pl.col('{col}').cast({type_str}, strict=False).alias('{col}')"

        text_expr = f"pl.col('{col}').cast(pl.String, strict=False)"

        if polars_dtype == pl.Date:
            expressions = [
                f"{text_expr}.str.strptime(pl.Date, {fmt!r}, strict=False, exact=True)"
                for fmt in self._date_parse_formats()
            ]
            expressions.extend(
                f"{text_expr}.str.strptime(pl.Datetime, {fmt!r}, strict=False, exact=True).cast(pl.Date, strict=False)"
                for fmt in self._datetime_parse_formats()
            )
            expressions.append(f"{text_expr}.str.to_date(strict=False)")
            expressions.append(f"pl.col('{col}').cast(pl.Date, strict=False)")
        else:
            expressions = [
                f"{text_expr}.str.strptime(pl.Datetime, {fmt!r}, strict=False, exact=True)"
                for fmt in self._datetime_parse_formats()
            ]
            expressions.extend(
                f"{text_expr}.str.strptime(pl.Date, {fmt!r}, strict=False, exact=True).cast(pl.Datetime, strict=False)"
                for fmt in self._date_parse_formats()
            )
            expressions.append(f"{text_expr}.str.to_datetime(strict=False)")
            expressions.append(f"pl.col('{col}').cast(pl.Datetime, strict=False)")

        joined = ",\n        ".join(expressions)
        return f"pl.coalesce([\n        {joined}\n    ]).alias('{col}')"

    def apply_changes(self) -> None:
        """Apply changes from self.changes to self.data"""
        global_logger.debug(
            "📋 SelectContent: Applying column selection and transformation changes"
        )

        # Ensure we have both incoming data and changes to apply
        if (
            getattr(self, "changes", None) is not None
            and getattr(self, "incom_data", None) is not None
        ):
            selected_columns = self.changes["selected_columns"]
            available_columns = list(self.incom_data.columns)

            global_logger.debug(
                f"📊 SelectContent: Available columns: {available_columns}"
            )
            global_logger.debug(
                f"📊 SelectContent: Requested columns: {selected_columns}"
            )

            # Validate that selected columns exist in the incoming data
            valid_columns = []
            invalid_columns = []

            for col in selected_columns:
                if col in available_columns:
                    valid_columns.append(col)
                else:
                    invalid_columns.append(col)

            if invalid_columns:
                global_logger.warning(
                    f"⚠️ SelectContent: Invalid columns found and will be skipped: {invalid_columns}"
                )
                global_logger.info(
                    f"📊 SelectContent: Available columns are: {available_columns}"
                )

            # If no valid columns, use all available columns
            if not valid_columns:
                valid_columns = available_columns
                global_logger.warning(
                    "⚠️ SelectContent: No valid columns selected, using all available columns"
                )
                self.changes["selected_columns"] = valid_columns
            else:
                # Update changes to only include valid columns
                if len(valid_columns) != len(selected_columns):
                    self.changes["selected_columns"] = valid_columns
                    global_logger.info(
                        f"📊 SelectContent: Updated selection to {len(valid_columns)} valid columns"
                    )

            global_logger.info(
                f"📊 SelectContent: Applying changes to {len(valid_columns)} valid columns"
            )

            print(f"🐍 Applying changes: selected_columns={valid_columns}")
            print(f"🐍 dtype_mapping={self.changes.get('dtype_mapping', {})}")
            print(f"🐍 rename_mapping={self.changes.get('rename_mapping', {})}")

            try:
                global_logger.debug(
                    f"📋 SelectContent: Selecting columns: {valid_columns}"
                )
                self.data = self.incom_data.select(valid_columns)
                global_logger.info(
                    f"✅ SelectContent: Successfully selected {len(valid_columns)} columns"
                )
            except Exception as e:
                global_logger.error(
                    f"❌ SelectContent: Failed to select columns: {str(e)}"
                )
                # Fallback: try to select all available columns
                try:
                    global_logger.warning(
                        "🔄 SelectContent: Attempting fallback to all available columns"
                    )
                    self.data = self.incom_data.select(available_columns)
                    self.changes["selected_columns"] = available_columns
                    global_logger.info(
                        f"✅ SelectContent: Fallback successful - selected all {len(available_columns)} columns"
                    )
                except Exception as fallback_error:
                    global_logger.error(
                        f"❌ SelectContent: Fallback also failed: {str(fallback_error)}"
                    )
                    self.data = None
                    return
        else:
            global_logger.warning(
                "⚠️ SelectContent: Cannot apply changes - missing incoming data or changes configuration"
            )

        # Apply data type changes if any (only for columns that exist in the data)
        if self.data is not None:
            current_columns = self.data.columns
            for col, dtype in self.changes["dtype_mapping"].items():
                if col not in current_columns:
                    global_logger.warning(
                        f"⚠️ SelectContent: Skipping type conversion for missing column '{col}'"
                    )
                    continue

                try:
                    global_logger.debug(
                        f"📋 SelectContent: Converting column '{col}' to type '{dtype}'"
                    )
                    expr = self._build_dtype_conversion_expr(col, dtype)
                    if expr is None:
                        global_logger.warning(
                            f"⚠️ SelectContent: Unknown data type '{dtype}' for column '{col}', skipping conversion"
                        )
                        continue

                    self.data = self.data.with_columns(expr)
                    global_logger.info(
                        f"✅ SelectContent: Successfully converted column '{col}' to {dtype}"
                    )
                except Exception as e:
                    global_logger.error(
                        f"❌ SelectContent: Failed to convert column '{col}' to {dtype}: {str(e)}"
                    )
                    print(f"Failed to convert column {col} to {dtype}: {str(e)}")

        # Apply renaming if any
        if self.changes["rename_mapping"]:
            rename_dict = self.changes["rename_mapping"]
            global_logger.debug(f"📋 SelectContent: Renaming columns: {rename_dict}")
            self.data = self.data.rename(rename_dict)
            global_logger.info(
                f"✅ SelectContent: Successfully renamed {len(rename_dict)} columns"
            )

        # Summary log
        if hasattr(self, "data") and self.data is not None:
            final_shape = self.data.shape
            global_logger.info(
                f"🎯 SelectContent: Column selection completed - Final DataFrame shape: {final_shape}"
            )
        else:
            global_logger.warning(
                "⚠️ SelectContent: No output data generated after applying changes"
            )

        print(
            "🐍 File: Preparation/select.py | Line: 279 | processInputs ~ self._is_invalid",
            self.node._is_invalid,
        )

    def process_data_changes(
        self, data_: list[list]
    ) -> tuple[list[str], dict[str, str], dict[str, str]]:
        global_logger.debug(
            f"📋 SelectContent: Processing data changes for {len(data_)} columns"
        )

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
            global_logger.trace(
                f"📋 SelectContent: Processing column '{column_name}' -> type: {data_type}, name: {new_name}"
            )

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
        global_logger.debug(
            f"📋 SelectContent: Updating data types for {len(selected_columns)} columns"
        )

        # Select only the specified columns from incom_data
        self.data = self.incom_data.select(selected_columns)
        global_logger.info(
            f"📊 SelectContent: Selected {len(selected_columns)} columns from input data"
        )

        # Apply data type changes if any
        for col, dtype in dtype_mapping.items():
            try:
                global_logger.debug(
                    f"🔄 SelectContent: Converting column '{col}' to type '{dtype}'"
                )
                expr = self._build_dtype_conversion_expr(col, dtype)
                if expr is None:
                    global_logger.warning(
                        f"⚠️ SelectContent: Unknown data type '{dtype}' for column '{col}'"
                    )
                    continue

                self.data = self.data.with_columns(expr)
                global_logger.trace(
                    f"✅ SelectContent: Column '{col}' converted to {dtype}"
                )
            except Exception as e:
                global_logger.error(
                    f"❌ SelectContent: Failed to convert column '{col}' to {dtype}: {str(e)}"
                )
                print(f"Failed to convert column {col} to {dtype}: {str(e)}")

        # Apply renaming if any (only for columns that exist in the data)
        if rename_mapping and self.data is not None:
            current_columns = self.data.columns
            # Filter rename mapping to only include existing columns
            valid_rename_mapping = {
                old_name: new_name
                for old_name, new_name in rename_mapping.items()
                if old_name in current_columns
            }
            invalid_columns = set(rename_mapping.keys()) - set(current_columns)

            if invalid_columns:
                global_logger.warning(
                    f"⚠️ SelectContent: Skipping rename for missing columns: {invalid_columns}"
                )

            if valid_rename_mapping:
                try:
                    global_logger.debug(
                        f"🏷️ SelectContent: Renaming {len(valid_rename_mapping)} columns"
                    )
                    self.data = self.data.rename(valid_rename_mapping)
                    global_logger.info(
                        "✅ SelectContent: Column renaming completed successfully"
                    )
                except Exception as e:
                    global_logger.error(
                        f"❌ SelectContent: Failed to rename columns: {str(e)}"
                    )
                    print(f"Failed to rename columns: {str(e)}")

    def handleDataChanged(self, data_: list) -> None:
        if self.history.is_restoring_history:
            global_logger.trace(
                "📋 SelectContent: Skipping data change handling - restoring history"
            )
            return

        global_logger.debug(
            f"📋 SelectContent: Handling data changes for {len(data_)} items"
        )
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
            expr_code = self._build_dtype_conversion_code(col, dtype)
            if expr_code:
                code_lines.append(
                    f"{self.variable_name} = {self.variable_name}.with_columns(\n"
                    f"    {expr_code}\n"
                    f")"
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
            # Load the table data and convert dictionaries back to RowData objects
            raw_table_data = data.get("table_data", [])
            self.table_data = []

            for item in raw_table_data:
                if isinstance(item, dict):
                    # Convert dictionary back to RowData object
                    self.table_data.append(
                        RowData(
                            checked=item.get("checked", False),
                            text=item.get("text", ""),
                            dtype=item.get("dtype", "object"),
                            rename=item.get("rename", ""),
                        )
                    )
                else:
                    # Already a RowData object (shouldn't happen but handle it)
                    self.table_data.append(item)

            self.changes = data.get(
                "changes",
                {"selected_columns": [], "rename_mapping": {}, "dtype_mapping": {}},
            )

            # Apply the changes if we have incoming data
            if hasattr(self, "incom_data") and self.incom_data is not None:
                self.apply_changes()

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
        global_logger.info("🔧 SelectNode: Initializing Select node")
        super().__init__(scene, inputs=[1], outputs=[3])
        global_logger.debug("📋 SelectNode: Node created with 1 input and 3 outputs")
        self.eval()
        global_logger.trace("✅ SelectNode: Initialization completed")

    def initInnerClasses(self) -> None:
        global_logger.debug("🔧 SelectNode: Initializing inner classes")
        self.content: SelectContent = SelectContent(self)
        self.grNode: TriggerGraphicsNode = TriggerGraphicsNode(self)
        self.content.evaluate.connect(self.onInputChanged)
        self.param: list = []
        global_logger.trace("✅ SelectNode: Inner classes initialized")

    def processInputs(self, input_values):
        global_logger.info("🔄 SelectNode: Starting input processing")
        print("⚠️⚠️⚠️ Select ⚠️⚠️⚠️")

        try:
            input_node = self.getInput(0)
            socket_index = self.getSocketValue(input_node.outputs, self)
            input_value = input_values[0][socket_index]

            global_logger.debug(
                f"� SelectNode: Retrieved input data, socket index: {socket_index}"
            )

            if input_value:
                global_logger.info("✅ SelectNode: Input data received, processing...")
                print("We have input")

                # Validate input data
                input_data = input_value.get("data")
                variable_name = input_value.get("variable_name", "unknown")

                if input_data is not None:
                    global_logger.info(
                        f"📊 SelectNode: Processing DataFrame with shape {input_data.shape} for variable '{variable_name}'"
                    )

                    self.markDirty(False)
                    self.markInvalid(False)

                    # Custom processing logic for the Select node
                    self.content.incom_data = input_data
                    self.content.incoming_variable = variable_name

                    # Apply column selection and transformations
                    self.content.apply_changes()

                    # Validate output data
                    if hasattr(self.content, "data") and self.content.data is not None:
                        output_shape = self.content.data.shape
                        global_logger.info(
                            f"📊 SelectNode: Output DataFrame shape: {output_shape}"
                        )

                        self.param = [
                            {
                                "data": self.content.data,
                                "variable_name": self.content.variable_name,
                            }
                        ]

                        self.evalChildren()
                        global_logger.info(
                            "✅ SelectNode: Processing completed successfully"
                        )

                        print(
                            "🐍 File: Preparation/select.py | Line: 279 | processInputs ~ self._is_invalid",
                            self._is_invalid,
                        )

                        return self.param
                    else:
                        global_logger.error(
                            "❌ SelectNode: No output data generated after processing"
                        )
                        self.markDirty(True)
                        self.markInvalid(True)
                        return None
                else:
                    global_logger.warning("⚠️ SelectNode: Input value contains no data")
                    self.markDirty(True)
                    self.markInvalid(True)
                    return None

            else:
                global_logger.warning("⚠️ SelectNode: No input data available")
                print("We don't have input")
                self.markDirty(True)
                self.markInvalid(True)
                self.grNode.setToolTip("Input is not connected")
                print(
                    "🐍 File: Preparation/select.py | Line: 292 | processInputs ~ self._is_invalid",
                    self._is_invalid,
                )
                return None

        except Exception as e:
            global_logger.error(
                f"❌ SelectNode: Error during input processing: {str(e)}"
            )
            global_logger.critical(
                f"🚨 SelectNode: Exception details: {type(e).__name__}: {str(e)}"
            )
            self.markDirty(True)
            self.markInvalid(True)
            self.grNode.setToolTip(f"Processing error: {str(e)}")
            return None

    def get_code(self):
        return self.content.get_code()
