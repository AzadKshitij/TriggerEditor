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
    upstream_rename_map,
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
from trigger_designer.qt.undo.protocol import is_syncing
from typing import (
    Optional,
    TYPE_CHECKING,
)

if TYPE_CHECKING:
    import polars as pl


# Tokens recognised when coercing a column to Boolean. Polars cannot cast
# Utf8 -> Boolean at all (it raises InvalidOperationError regardless of
# `strict`), so anything textual needs an explicit token match. Numeric
# sources fall back to a non-zero test, since `cast(Float64)` renders 1.0 as
# "1.0" which is not in either token set. Unrecognised values become null,
# matching the `strict=False` contract the other dtype conversions use.
_BOOLEAN_TRUE_TOKENS = ("true", "1", "yes", "y", "t", "on")
_BOOLEAN_FALSE_TOKENS = ("false", "0", "no", "n", "f", "off")


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
            "auto_accept_new_columns": True,
        }
        self._auto_accept_action = None

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
            # Initialize changes if not already present (e.g., from deserialization)
            if not hasattr(self, "changes") or not self.changes:
                self.changes: dict = {
                    "selected_columns": list(
                        frame_schema(self.incom_data)
                    ),  # Select all by default
                    "rename_mapping": {},
                    "dtype_mapping": {},
                    "auto_accept_new_columns": True,
                }

            # Align rows + mappings with the live upstream schema (e.g. an
            # Aggregate rename). Preserves choices for surviving columns.
            self._reconcile_schema()

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

        menu.addSeparator()
        self._auto_accept_action = menu.addAction("Auto-add new columns")
        self._auto_accept_action.setCheckable(True)
        self._auto_accept_action.setToolTip(
            "When checked, columns arriving from upstream are included automatically."
        )
        self._auto_accept_action.setChecked(
            bool((self.changes or {}).get("auto_accept_new_columns", True))
        )
        self._auto_accept_action.toggled.connect(self._on_auto_accept_toggled)

    def _on_auto_accept_toggled(self, checked: bool) -> None:
        """Toggle whether newly arrived upstream columns are auto-included."""
        if self.history.is_restoring_history or is_syncing(self):
            return
        old = bool((self.changes or {}).get("auto_accept_new_columns", True))
        if old == bool(checked):
            return
        self.changes["auto_accept_new_columns"] = bool(checked)
        self.push_property_change(
            ("changes", "auto_accept_new_columns"),
            old,
            bool(checked),
            "Auto-Accept Changed",
        )

    def _sync_widgets_from_model(self) -> None:
        """Refresh widget values from the model, preserving widget identity."""
        action = getattr(self, "_auto_accept_action", None)
        if action is not None:
            try:
                checked = bool(
                    (self.changes or {}).get("auto_accept_new_columns", True)
                )
                if action.isChecked() != checked:
                    action.setChecked(checked)
            except RuntimeError:
                pass

    def apply_upstream_renames(self, rename_map: dict) -> bool:
        """Follow an upstream rename in place, preserving order and settings.

        A rename otherwise looks like a drop + add to schema diffing: the
        renamed row jumps to the end and per-column rename/dtype choices
        keyed by the old name are pruned. When ``old`` is gone from the
        live schema but ``new`` is present, the row (and its ``changes``
        keys) is renamed instead.

        :return: True when anything was renamed.
        """
        if not rename_map or getattr(self, "incom_data", None) is None:
            return False
        try:
            live = set(frame_schema(self.incom_data))
        except Exception:  # noqa: BLE001 - any frame error means no follow
            return False
        changes = self.changes or {}
        rows = [row for row in self.table_data if hasattr(row, "text")]
        present = {row.text for row in rows}
        renamed_any = False
        for old, new in rename_map.items():
            if old in live or new not in live:
                continue
            if old not in present or new in present:
                continue
            for row in rows:
                if row.text == old:
                    row.text = new
                    renamed_any = True
            for key in ("selected_columns", "column_order"):
                values = changes.get(key)
                if isinstance(values, list):
                    changes[key] = [new if value == old else value for value in values]
            for key in ("rename_mapping", "dtype_mapping"):
                mapping = changes.get(key)
                if isinstance(mapping, dict) and old in mapping:
                    mapping[new] = mapping.pop(old)
        if renamed_any:
            self.changes = changes
        return renamed_any

    def _bulk_target_rows(self, selected_only: bool) -> list:
        """Rows a bulk action applies to.

        "Selected" means highlighted rows in the view - the same vocabulary
        as Check/Uncheck Selected - mapped through the search proxy. "All"
        means every row. An empty highlight is a no-op, never a fallback to
        everything: with everything checked by default, checked-state would
        make "Selected" silently mean "All".
        """
        if not selected_only:
            return list(self.table_data)
        try:
            view = getattr(self, "table_view", None)
            selection = view.selectionModel() if view is not None else None
            if selection is None:
                return []
            rows = []
            seen = set()
            for index in selection.selectedRows():
                model = view.model()
                if isinstance(model, QSortFilterProxyModel):
                    index = model.mapToSource(index)
                row = index.row()
                if 0 <= row < len(self.table_data) and row not in seen:
                    seen.add(row)
                    rows.append(self.table_data[row])
        except RuntimeError:
            # Dock was rebuilt under this menu; nothing valid to target.
            return []
        return rows

    def _bulk_commit(self) -> None:
        """Repaint the table and run one history-tracked pipeline pass.

        Emits a bounded dataChanged (values changed, structure did not). A
        bare layoutChanged here segfaults once a selection exists: the proxy
        and view rebuild selection state around a layout change that never
        happened.
        """
        try:
            if self.table_data:
                top_left = self.table_widget.index(0, 0)
                bottom_right = self.table_widget.index(len(self.table_data) - 1, 3)
                self.table_widget.dataChanged.emit(top_left, bottom_right, [])
            self.handleDataChanged(self.table_widget.getData())
        except Exception as exc:
            global_logger.error(f"Select bulk edit failed: {exc}")
            try:
                self.node.grNode.setToolTip(f"Bulk edit failed: {exc}")
            except RuntimeError:
                pass

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

    def _build_boolean_expr(self, col: str) -> pl.Expr:
        """Coerce ``col`` to Boolean from any source type.

        Polars has no Utf8 -> Boolean cast, so the Boolean dtype is served by
        matching normalised text tokens and falling back to a non-zero numeric
        test. Kept source-agnostic so the live path and the generated code
        cannot drift apart.
        """
        source = pl.col(col)
        token = (
            source.cast(pl.String, strict=False).str.to_lowercase().str.strip_chars()
        )
        number = source.cast(pl.Float64, strict=False)
        return (
            pl.when(token.is_in(_BOOLEAN_TRUE_TOKENS))
            .then(True)
            .when(token.is_in(_BOOLEAN_FALSE_TOKENS))
            .then(False)
            .when(number.is_not_null() & (number != 0.0))
            .then(True)
            .when(number.is_not_null())
            .then(False)
            .otherwise(None)
            .alias(col)
        )

    def _build_dtype_conversion_expr(self, col: str, dtype: str) -> Optional[pl.Expr]:
        """Build a Polars expression that converts a column to the requested dtype."""
        polars_dtype = self._map_dtype_to_polars(dtype)
        if polars_dtype is None:
            return None

        if polars_dtype is pl.Boolean:
            return self._build_boolean_expr(col)

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

        if polars_dtype is pl.Boolean:
            # Mirrors _build_boolean_expr exactly. Keep the two in step.
            source = f"pl.col({col!r})"
            token = f"{source}.cast(pl.String, strict=False).str.to_lowercase().str.strip_chars()"
            number = f"{source}.cast(pl.Float64, strict=False)"
            return (
                f"pl.when({token}.is_in({_BOOLEAN_TRUE_TOKENS!r})).then(True)\n"
                f"    .when({token}.is_in({_BOOLEAN_FALSE_TOKENS!r})).then(False)\n"
                f"    .when({number}.is_not_null() & ({number} != 0.0)).then(True)\n"
                f"    .when({number}.is_not_null()).then(False)\n"
                f"    .otherwise(None)\n"
                f"    .alias({col!r})"
            )

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

    def _reconcile_schema(self) -> bool:
        """Align rows + mappings with the live upstream schema.

        An upstream rename/add/drop (e.g. from Aggregate) otherwise leaves
        this node showing stale columns until its dock is rebuilt from
        scratch. Surviving columns keep their check/rename/dtype choices;
        new columns arrive checked when auto-accept is on (unchecked
        otherwise); stale mappings are dropped.

        The user's display order is preserved: surviving rows stay where
        they are and new columns are appended. In particular a manual
        move-up/move-down must survive the ``apply_changes`` pass that
        follows its ``data_processed`` signal.

        :return: True when the row structure changed.
        """
        if getattr(self, "incom_data", None) is None:
            return False
        try:
            schema = frame_schema(self.incom_data)
        except Exception:
            return False
        columns = list(schema)
        if not isinstance(getattr(self, "table_data", None), list):
            self.table_data = []
        changes = getattr(self, "changes", None) or {}
        changes.setdefault("selected_columns", [])
        changes.setdefault("rename_mapping", {})
        changes.setdefault("dtype_mapping", {})
        changes.setdefault("column_order", [])
        changes.setdefault("auto_accept_new_columns", True)
        auto_accept = bool(changes.get("auto_accept_new_columns", True))
        user_dtypes = set(changes.get("dtype_mapping") or {})
        existing = {row.text: row for row in self.table_data if hasattr(row, "text")}
        old_texts = [row.text for row in self.table_data if hasattr(row, "text")]
        old_set = set(old_texts)
        new_set = set(columns)

        restoring = bool(
            getattr(getattr(self, "history", None), "is_restoring_history", False)
        )
        if restoring:
            # Undo/redo: the stored order wins over the on-screen order.
            stored_order = list(changes.get("column_order") or [])
            if not stored_order:
                # Legacy stamp without full order: checked first, then rest.
                selected_set = set(changes.get("selected_columns", []))
                stored_order = [
                    col for col in changes.get("selected_columns", []) if col in new_set
                ]
                stored_order += [col for col in columns if col not in selected_set]
            ordered = [col for col in stored_order if col in new_set]
            for col in columns:
                if col not in ordered:
                    ordered.append(col)
            selected_set = set(changes.get("selected_columns", []))
            new_rows: list = []
            for col in ordered:
                row = existing.get(col)
                if row is None:
                    row = RowData(col in selected_set, col, str(schema[col]))
                elif col not in user_dtypes and row.dtype != str(schema[col]):
                    row.dtype = str(schema[col])
                new_rows.append(row)
            structural = old_texts != ordered
            # Mutate in place: the live table model holds this same list object.
            self.table_data[:] = new_rows
            changes["selected_columns"] = [
                col for col in changes.get("selected_columns", []) if col in new_set
            ]
            changes["column_order"] = ordered
            changes["rename_mapping"] = {
                key: value
                for key, value in changes.get("rename_mapping", {}).items()
                if key in new_set
            }
            changes["dtype_mapping"] = {
                key: value
                for key, value in changes.get("dtype_mapping", {}).items()
                if key in new_set
            }
            self.changes = changes
            return structural

        # Refresh dtypes for surviving columns unless the user overrode them.
        for row in self.table_data:
            if (
                hasattr(row, "text")
                and row.text in schema
                and row.text not in user_dtypes
                and row.dtype != str(schema[row.text])
            ):
                row.dtype = str(schema[row.text])

        if old_set == new_set and old_texts:
            # No columns added or dropped: keep the display order exactly.
            # Rebuild the checked selection from the rows so an uncheck
            # cannot be re-added by stale state.
            changes["selected_columns"] = [
                row.text for row in self.table_data if getattr(row, "checked", False)
            ]
            changes["column_order"] = list(old_texts)
            changes["rename_mapping"] = {
                key: value
                for key, value in changes.get("rename_mapping", {}).items()
                if key in new_set
            }
            changes["dtype_mapping"] = {
                key: value
                for key, value in changes.get("dtype_mapping", {}).items()
                if key in new_set
            }
            self.changes = changes
            return False

        # Columns were added and/or dropped: keep survivors in place,
        # append genuinely new columns in upstream order. New arrivals are
        # checked only when auto-accept is on (first build checks all).
        new_rows = [row for row in self.table_data if row.text in new_set]
        first_build = not old_texts
        for col in columns:
            if col not in existing:
                new_rows.append(
                    RowData(bool(auto_accept) or first_build, col, str(schema[col]))
                )
        structural = old_texts != [row.text for row in new_rows]
        # Mutate in place: the live table model holds this same list object.
        self.table_data[:] = new_rows
        changes["selected_columns"] = [
            row.text for row in new_rows if getattr(row, "checked", False)
        ]
        changes["column_order"] = [row.text for row in new_rows]
        changes["rename_mapping"] = {
            key: value
            for key, value in changes.get("rename_mapping", {}).items()
            if key in new_set
        }
        changes["dtype_mapping"] = {
            key: value
            for key, value in changes.get("dtype_mapping", {}).items()
            if key in new_set
        }
        self.changes = changes
        return structural

    def _refresh_live_view(self) -> None:
        """Repaint the open table after a structural schema change.

        Uses a model reset (never a bare layoutChanged, which segfaults with
        an active selection) and emits no data_processed, so this cannot
        recurse into handleDataChanged.
        """
        widget = getattr(self, "table_widget", None)
        if widget is None:
            return
        try:
            view = getattr(self, "table_view", None)
            if view is not None:
                try:
                    view.clearSelection()
                except RuntimeError:
                    pass
            widget.beginResetModel()
            widget.endResetModel()
        except RuntimeError:
            pass

    def apply_changes(self) -> None:
        """Apply changes from self.changes to self.data"""
        global_logger.debug(
            "📋 SelectContent: Applying column selection and transformation changes"
        )

        # Reconcile first so a renamed upstream column flows through even
        # while this node's dock is open.
        structural = self._reconcile_schema()
        if structural:
            self._refresh_live_view()

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
        auto_accept = bool((self.changes or {}).get("auto_accept_new_columns", True))
        self.changes = {
            "selected_columns": [],
            "rename_mapping": {},
            "dtype_mapping": {},
            "column_order": [
                row.text
                for row in getattr(self, "table_data", [])
                if hasattr(row, "text")
            ],
            "auto_accept_new_columns": auto_accept,
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

        if not self.changes["column_order"]:
            # No live rows (e.g. headless caller): fall back to checked order.
            self.changes["column_order"] = list(self.changes["selected_columns"])

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
            "auto_accept_new_columns": (
                self.changes.get("auto_accept_new_columns", True)
                if hasattr(self, "changes")
                else True
            ),
            "column_order": (
                self.changes["column_order"].copy()
                if hasattr(self, "changes") and "column_order" in self.changes
                else (
                    [row.text for row in self.table_data if hasattr(row, "text")]
                    if hasattr(self, "table_data")
                    else []
                )
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
                    "auto_accept_new_columns": self.changes.get(
                        "auto_accept_new_columns", True
                    ),
                    "column_order": self.changes["column_order"].copy(),
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
        """Callback for undo/redo operations.

        The scene snapshot has already restored the model (table rows and
        ``changes``) before this runs, so the payload's old/new diff must
        NOT be re-applied here: it describes the edit that produced the
        applied stamp, and picking its "old" side would step back twice.
        The only job left is re-running the pipeline and re-projecting
        the widgets from the restored model.
        """
        del history_data, is_undo
        # Legacy stamps predate the auto-accept toggle.
        if isinstance(self.changes, dict):
            self.changes.setdefault("auto_accept_new_columns", True)

        # Apply the changes and update the table
        self.apply_changes()
        widget = getattr(self, "table_widget", None)
        if widget is not None:
            try:
                # A snapshot restore replaces `table_data` wholesale, which
                # breaks the list identity the live model edits in place.
                # Re-point it so later moves/checks mutate `table_data`.
                if getattr(widget, "_data", None) is not self.table_data:
                    try:
                        widget.beginResetModel()
                        widget._data = self.table_data
                        widget.endResetModel()
                    except RuntimeError:
                        widget._data = self.table_data
                widget.update_from_changes(self.changes)
            except RuntimeError:
                pass
        self._sync_widgets_from_model()

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
            {
                "selected_columns": [],
                "rename_mapping": {},
                "dtype_mapping": {},
                "auto_accept_new_columns": True,
            },
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
                {
                    "selected_columns": [],
                    "rename_mapping": {},
                    "dtype_mapping": {},
                    "auto_accept_new_columns": True,
                },
            )
            if isinstance(self.changes, dict):
                self.changes.setdefault("auto_accept_new_columns", True)

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

                    # Follow an upstream rename so downstream configs keep
                    # working instead of going stale.
                    followed = False
                    try:
                        rename_map = upstream_rename_map(input_node)
                        if rename_map:
                            followed = self.content.apply_upstream_renames(rename_map)
                    except (AttributeError, ValueError, RuntimeError) as follow_error:
                        global_logger.warning(
                            f"⚠️ SelectNode: Could not follow upstream renames: {follow_error}"
                        )

                    # Apply column selection and transformations
                    self.content.apply_changes()
                    if followed:
                        self.content._refresh_live_view()

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

                        # NOTE: no evalChildren() here. The base
                        # evalImplementation evaluates children after this
                        # returns and the new value is committed; evaluating
                        # them here would hand them the previous output.
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
