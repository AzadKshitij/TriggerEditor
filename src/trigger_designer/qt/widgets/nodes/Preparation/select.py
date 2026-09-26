import polars as pl
import dataclasses
import re
from datetime import datetime
from qtpy.QtWidgets import (
    QWidget,
    QLineEdit,
    QVBoxLayout,
    QTableView,
    QHBoxLayout,
    QStyledItemDelegate,
    QMenu,
    QInputDialog,
)
from qtpy.QtGui import QPixmap
from qtpy.QtCore import (
    Qt,
    Signal,
    QSortFilterProxyModel,
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
    frame_schema,
    frame_shape,
)
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget
from trigger_designer.qt.widgets.common import EmptyStateLabel, IconButton
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
)

if TYPE_CHECKING:
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

        # Must exist before create_layout runs so processInputs can call
        # apply_changes() on first connection.
        self.changes: dict = {
            "selected_columns": [],
            "rename_mapping": {},
            "dtype_mapping": {},
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
            # Initialize table_data if not already present (e.g., from deserialization)
            if not self.table_data:
                schema = frame_schema(self.incom_data)
                self.table_data = [
                    RowData(True, col, str(schema[col])) for col in schema
                ]

            # Initialize changes if not already present (e.g., from deserialization)
            if not hasattr(self, "changes") or not self.changes:
                self.changes: dict = {
                    "selected_columns": list(
                        frame_schema(self.incom_data)
                    ),  # Select all by default
                    "rename_mapping": {},
                    "dtype_mapping": {},
                }

            # Ensure selected_columns has default values if empty
            if not self.changes.get("selected_columns"):
                self.changes["selected_columns"] = list(frame_schema(self.incom_data))

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

            # Move buttons (icon-only, 30x30/12px per design system §4)
            self.up_btn = IconButton.themed(
                "Move column up",
                rsm_icon=None,
                qss_fallback=":/qss_icons/dark/rc/arrow_up.png",
                theme_fallback="go-up",
                parent=toolbar_widget,
            )

            self.down_btn = IconButton.themed(
                "Move column down",
                rsm_icon=None,
                qss_fallback=":/qss_icons/dark/rc/arrow_down.png",
                theme_fallback="go-down",
                parent=toolbar_widget,
            )

            toolbar_layout.addWidget(self.up_btn)
            toolbar_layout.addWidget(self.down_btn)

            # Options menu button (icon-only; QSS hides menu indicator)
            self.options_btn = IconButton.themed(
                "Column options",
                rsm_icon=self.node.rsm.get("icon_options"),
                qss_fallback=":/qss_icons/dark/rc/arrow_down.png",
                theme_fallback=None,
                parent=toolbar_widget,
            )
            self.options_btn.setObjectName("OptionsButton")

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

        # Bulk rename / retype actions (appended to the same Options menu)
        self.setup_bulk_menus()

    BULK_SAMPLE_ROWS = 1000

    def setup_bulk_menus(self) -> None:
        """Append Bulk Rename / Bulk Data Type submenus to the Options menu."""
        menu = self.options_btn.menu()
        if menu is None:
            return
        menu.addSeparator()

        rename_menu = QMenu("Bulk Rename", menu)
        rename_menu.addAction("Add Prefix to Selected...").triggered.connect(
            lambda _checked=False: self.prompt_bulk_affix(
                selected_only=True, is_prefix=True
            )
        )
        rename_menu.addAction("Add Prefix to All...").triggered.connect(
            lambda _checked=False: self.prompt_bulk_affix(
                selected_only=False, is_prefix=True
            )
        )
        rename_menu.addAction("Add Suffix to Selected...").triggered.connect(
            lambda _checked=False: self.prompt_bulk_affix(
                selected_only=True, is_prefix=False
            )
        )
        rename_menu.addAction("Add Suffix to All...").triggered.connect(
            lambda _checked=False: self.prompt_bulk_affix(
                selected_only=False, is_prefix=False
            )
        )
        rename_menu.addSeparator()
        rename_menu.addAction("Clear Renames (Selected)").triggered.connect(
            lambda _checked=False: self.bulk_clear_renames(selected_only=True)
        )
        rename_menu.addAction("Clear Renames (All)").triggered.connect(
            lambda _checked=False: self.bulk_clear_renames(selected_only=False)
        )
        menu.addMenu(rename_menu)

        dtype_menu = QMenu("Bulk Data Type", menu)
        dtype_menu.addAction("Auto-Detect Types (Selected)").triggered.connect(
            lambda _checked=False: self.bulk_auto_detect(selected_only=True)
        )
        dtype_menu.addAction("Auto-Detect Types (All)").triggered.connect(
            lambda _checked=False: self.bulk_auto_detect(selected_only=False)
        )
        dtype_menu.addSeparator()
        dtype_menu.addAction("Reset Types (Selected)").triggered.connect(
            lambda _checked=False: self.bulk_reset_dtypes(selected_only=True)
        )
        dtype_menu.addAction("Reset Types (All)").triggered.connect(
            lambda _checked=False: self.bulk_reset_dtypes(selected_only=False)
        )
        menu.addMenu(dtype_menu)

    def _bulk_target_rows(self, selected_only: bool) -> list:
        """Rows a bulk action applies to. Empty scope is a no-op, never a fallback."""
        if selected_only:
            return [row for row in self.table_data if row.checked]
        return list(self.table_data)

    def _bulk_commit(self) -> None:
        """Repaint the table and run one history-tracked pipeline pass."""
        self.table_widget.layoutChanged.emit()
        self.handleDataChanged(self.table_widget.getData())

    def prompt_bulk_affix(self, selected_only: bool, is_prefix: bool) -> None:
        """Ask for an affix, then compose it onto the effective names."""
        scope = "Selected" if selected_only else "All"
        kind = "Prefix" if is_prefix else "Suffix"
        affix, accepted = QInputDialog.getText(
            None,
            f"Add {kind} ({scope})",
            f"{kind} to add:",
        )
        if not accepted or not affix:
            return
        rows = self._bulk_target_rows(selected_only)
        if not rows:
            return
        for row in rows:
            base = row.rename or row.text
            row.rename = f"{affix}{base}" if is_prefix else f"{base}{affix}"
        self._bulk_commit()

    def bulk_clear_renames(self, selected_only: bool) -> None:
        rows = self._bulk_target_rows(selected_only)
        if not rows:
            return
        for row in rows:
            row.rename = ""
        self._bulk_commit()

    def bulk_reset_dtypes(self, selected_only: bool) -> None:
        """Restore source-schema dtypes for the scoped rows."""
        if self.incom_data is None:
            return
        rows = self._bulk_target_rows(selected_only)
        if not rows:
            return
        try:
            schema = frame_schema(self.incom_data)
        except Exception:
            return
        for row in rows:
            if row.text in schema:
                row.dtype = str(schema[row.text])
        self._bulk_commit()

    def bulk_auto_detect(self, selected_only: bool) -> None:
        """Infer dtypes from a capped sample of each scoped column."""
        if self.incom_data is None:
            return
        rows = self._bulk_target_rows(selected_only)
        if not rows:
            return
        for row in rows:
            inferred = self._infer_column_dtype(row.text)
            if inferred is not None:
                row.dtype = inferred
        self._bulk_commit()

    def _infer_column_dtype(self, column: str) -> Optional[str]:
        """Infer a display dtype from up to BULK_SAMPLE_ROWS values.

        Precedence: Boolean -> Int64 -> Float64 -> Date -> String. Anything
        unparseable (or all-null) stays String.
        """
        try:
            series = (
                self.incom_data.select(pl.col(column).cast(pl.String))
                .head(self.BULK_SAMPLE_ROWS)
                .collect()
                .get_column(column)
            )
        except Exception:
            return None
        values = [
            value
            for value in series.to_list()
            if value is not None and str(value).strip() != ""
        ]
        if not values:
            return "String"
        lowered = [str(value).strip().lower() for value in values]
        if all(value in ("true", "false") for value in lowered):
            return "Boolean"
        try:
            for value in values:
                int(str(value).strip())
            return "Int64"
        except (TypeError, ValueError):
            pass
        try:
            for value in values:
                float(str(value).strip())
            return "Float64"
        except (TypeError, ValueError):
            pass
        for fmt in self._date_parse_formats():
            try:
                for value in values:
                    datetime.strptime(str(value).strip(), fmt)
                return "Date"
            except (TypeError, ValueError, re.error):
                continue
        return "String"

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
            "%m.%d.%Y",
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
            available_columns = list(frame_schema(self.incom_data))

            # First time with data: select all columns by default
            if not selected_columns:
                selected_columns = available_columns
                self.changes["selected_columns"] = selected_columns

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
            current_columns = list(frame_schema(self.data))
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
            final_shape = frame_shape(self.data)
            global_logger.info(
                f"🎯 SelectContent: Column selection completed - Final DataFrame shape: {final_shape}"
            )
        else:
            global_logger.warning(
                "⚠️ SelectContent: No output data generated after applying changes"
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

        # Apply renaming if any (only for columns that exist in the data)
        if rename_mapping and self.data is not None:
            current_columns = list(frame_schema(self.data))
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

    def handleDataChanged(self, data_: list) -> None:
        if self.history.is_restoring_history:
            global_logger.trace(
                "📋 SelectContent: Skipping data change handling - restoring history"
            )
            return

        global_logger.debug(
            f"📋 SelectContent: Handling data changes for {len(data_)} items"
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
        if self.data is None or not self.incoming_variable:
            # Fallback: always define the output so downstream code never
            # NameErrors (or SyntaxErrors on an empty incoming variable).
            code = ["import polars as pl"]
            if self.incoming_variable:
                code.append(f"{self.variable_name} = {self.incoming_variable}")
            else:
                code.append(f"{self.variable_name} = pl.DataFrame()")
            return "\n".join(code) + "\n"

        if not self.changes["selected_columns"]:
            # No selection: keep everything (matches live apply_changes).
            return f"{self.variable_name} = {self.incoming_variable}\n"

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
        res["table_data"] = [
            dataclasses.asdict(item) if dataclasses.is_dataclass(item) else item
            for item in self.table_data
        ]
        res["changes"] = getattr(
            self,
            "changes",
            {"selected_columns": [], "rename_mapping": {}, "dtype_mapping": {}},
        )
        return res

    def deserialize(self, data, hashmap={}):
        res = super().deserialize(data, hashmap)
        try:
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

            return True and res
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

        try:
            input_node = self.getInput(0)
            socket_index = self.getSocketValue(input_node.outputs, self)
            input_value = input_values[0][socket_index]

            global_logger.debug(
                f"� SelectNode: Retrieved input data, socket index: {socket_index}"
            )

            if input_value:
                global_logger.info("✅ SelectNode: Input data received, processing...")

                # Validate input data
                input_data = input_value.get("data")
                variable_name = input_value.get("variable_name", "unknown")

                if input_data is not None:
                    global_logger.info(
                        f"📊 SelectNode: Processing DataFrame with shape {frame_shape(input_data)} for variable '{variable_name}'"
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
                        output_shape = frame_shape(self.content.data)
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
                self.markDirty(True)
                self.markInvalid(True)
                self.grNode.setToolTip("Input is not connected")
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
