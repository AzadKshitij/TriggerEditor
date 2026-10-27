"""Select node: table-driven column selection on the shared shaping system."""

from __future__ import annotations

import polars as pl
from qtpy.QtCore import QSortFilterProxyModel, Qt
from qtpy.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLineEdit,
    QMenu,
    QStyledItemDelegate,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from trigger_designer.core.node_configuration import (
    NodeTypes,
    PreparationNodes,
    register_node,
)
from trigger_designer.core.shaping import select as core
from trigger_designer.qt.helpers.shaping_support import ShapingContent, ShapingNode
from trigger_designer.qt.node_base import upstream_rename_map
from trigger_designer.qt.widgets.common import (
    ConfigSection,
    EmptyStateLabel,
    IconButton,
    TextButton,
)
from trigger_designer.qt.widgets.select_table_widget import (
    ComboBoxDelegate,
    RowData,
    SelectTableWidget,
)


class SelectContent(ShapingContent):
    """Column table projected over ``settings['columns']``.

    The table remains the editor. Every table mutation becomes one ``columns``
    setting, so live evaluation and Run share the same core runner and undo is
    one step per table action.
    """

    SETTINGS = core.DEFAULTS
    MODULE = "trigger_designer.core.shaping.select"
    RUNNER = "run_node"
    OUTPUT_KINDS = ("select",)
    INPUTS = 1
    HISTORY = "Select"
    SUMMARY = "column selection"
    BULK_SAMPLE_ROWS = 1000

    def __init__(self, node, parent=None) -> None:
        super().__init__(node, parent)
        self.table_data: list[RowData] = []
        self.table_widget: SelectTableWidget | None = None
        self.table_view: QTableView | None = None
        self.proxy_model: QSortFilterProxyModel | None = None
        self._auto_accept_action = None
        self._suspend_table = False

    # ---- dock -----------------------------------------------------------
    def create_layout(self, dock_layout: QVBoxLayout) -> None:
        if self.frames[0] is None:
            dock_layout.addWidget(EmptyStateLabel())
            return

        self._reconcile_columns()
        self.table_data = self._rows_from_settings()
        section = ConfigSection("")

        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(4)
        toolbar.setFixedHeight(40)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search columns...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setMinimumHeight(30)
        toolbar_layout.addWidget(self.search_input, 1)

        self.all_btn = TextButton("All", "Select every column", toolbar)
        self.none_btn = TextButton("None", "Deselect every column", toolbar)
        for button in (self.all_btn, self.none_btn):
            button.setObjectName("BulkButton")
            button.setFixedWidth(32)
        self.all_btn.clicked.connect(self.select_all_columns)
        self.none_btn.clicked.connect(self.select_no_columns)
        toolbar_layout.addWidget(self.all_btn)
        toolbar_layout.addWidget(self.none_btn)

        self.up_btn = IconButton.themed(
            "Move column up",
            rsm_icon=self.node.rsm.get("icon_move_up"),
            parent=toolbar,
        )
        self.down_btn = IconButton.themed(
            "Move column down",
            rsm_icon=self.node.rsm.get("icon_move_down"),
            parent=toolbar,
        )
        self.up_btn.clicked.connect(
            lambda: self.table_widget.moveSelectedRow("up", self.table_view)
        )
        self.down_btn.clicked.connect(
            lambda: self.table_widget.moveSelectedRow("down", self.table_view)
        )
        toolbar_layout.addWidget(self.up_btn)
        toolbar_layout.addWidget(self.down_btn)

        self.options_btn = IconButton.themed(
            "Column options",
            rsm_icon=self.node.rsm.get("icon_options"),
            parent=toolbar,
        )
        self.options_btn.setObjectName("OptionsButton")
        toolbar_layout.addWidget(self.options_btn)
        section.addWidget(toolbar)

        self.table_widget = SelectTableWidget(
            self.table_data, self._table_changes(), parent=self
        )
        self.table_widget._undo_composite = True
        self.table_widget.data_processed.connect(self._on_table_data)

        self.proxy_model = QSortFilterProxyModel(self)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.proxy_model.setSourceModel(self.table_widget)
        self.proxy_model.setFilterKeyColumn(-1)

        self.table_view = QTableView()
        self.table_view.setObjectName("ColumnTable")
        self.table_view.setModel(self.proxy_model)
        self.table_view.verticalHeader().setDefaultSectionSize(22)
        self.table_view.horizontalHeader().setFixedHeight(20)
        self.table_view.setItemDelegateForColumn(2, ComboBoxDelegate(self.table_view))
        self.table_view.setItemDelegateForColumn(3, QStyledItemDelegate())
        self.table_view.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        self.table_view.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        header = self.table_view.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(0, 40)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        metrics = self.table_view.fontMetrics()
        dtype_width = max(
            metrics.horizontalAdvance(name) for name in SelectTableWidget.DATA_TYPES
        )
        header.resizeSection(2, dtype_width + 30)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table_view.setMinimumHeight(220)
        self.search_input.textChanged.connect(self.proxy_model.setFilterFixedString)

        section.addWidget(self.table_view, 1)
        dock_layout.addWidget(section, 1)
        self._setup_options_menu()
        self._refresh_select_counts()

    def _setup_options_menu(self) -> None:
        menu = QMenu(self.options_btn)
        menu.addAction("Check Selected").triggered.connect(
            lambda _checked=False: self.table_widget.checkSelected(self.table_view)
        )
        menu.addAction("Uncheck Selected").triggered.connect(
            lambda _checked=False: self.table_widget.uncheckSelected(self.table_view)
        )
        menu.addSeparator()

        sort_menu = menu.addMenu("Sort")
        for label, key in (
            ("Original Order", "original"),
            ("Name (A-Z)", "name_asc"),
            ("Name (Z-A)", "name_desc"),
            ("By Type", "type"),
        ):
            sort_menu.addAction(label).triggered.connect(
                lambda _checked=False, sort_key=key: self._sort_columns(sort_key)
            )

        menu.addSeparator()
        rename_menu = menu.addMenu("Bulk Rename")
        for label, selected_only, prefix in (
            ("Add Prefix to Selected...", True, True),
            ("Add Prefix to All...", False, True),
            ("Add Suffix to Selected...", True, False),
            ("Add Suffix to All...", False, False),
        ):
            rename_menu.addAction(label).triggered.connect(
                lambda _checked=False, s=selected_only, p=prefix: (
                    self.prompt_bulk_affix(selected_only=s, is_prefix=p)
                )
            )
        rename_menu.addSeparator()
        for label, selected_only in (
            ("Clear Renames (Selected)", True),
            ("Clear Renames (All)", False),
        ):
            rename_menu.addAction(label).triggered.connect(
                lambda _checked=False, s=selected_only: self.bulk_clear_renames(s)
            )

        dtype_menu = menu.addMenu("Bulk Data Type")
        for label, selected_only in (
            ("Auto-Detect Types (Selected)", True),
            ("Auto-Detect Types (All)", False),
        ):
            dtype_menu.addAction(label).triggered.connect(
                lambda _checked=False, s=selected_only: self.bulk_auto_detect(s)
            )
        dtype_menu.addSeparator()
        for label, selected_only in (
            ("Reset Types (Selected)", True),
            ("Reset Types (All)", False),
        ):
            dtype_menu.addAction(label).triggered.connect(
                lambda _checked=False, s=selected_only: self.bulk_reset_dtypes(s)
            )

        menu.addSeparator()
        self._auto_accept_action = menu.addAction("Auto-add new columns")
        self._auto_accept_action.setCheckable(True)
        self._auto_accept_action.setToolTip(
            "When checked, columns arriving from upstream are included automatically."
        )
        self._auto_accept_action.setChecked(
            bool(self.settings.get("auto_accept_new_columns", True))
        )
        self._auto_accept_action.toggled.connect(self._on_auto_accept_toggled)
        self.options_btn.setMenu(menu)

    def _sort_columns(self, sort_type: str) -> None:
        schema_order = {name: index for index, name in enumerate(self.schema(0))}
        if sort_type == "original":
            key = lambda row: schema_order.get(row.text, len(schema_order))
        elif sort_type == "name_asc" or sort_type == "name_desc":
            key = lambda row: row.text.casefold()
        elif sort_type == "type":
            key = lambda row: (row.dtype.casefold(), row.text.casefold())
        else:
            return
        rows = sorted(self.table_data, key=key, reverse=sort_type == "name_desc")
        self.table_data = rows
        if self.table_widget is not None:
            self.table_widget.set_rows(rows)
        self._commit_table()

    # ---- settings projection -------------------------------------------
    def _table_changes(self) -> dict:
        columns = list(self.settings.get("columns") or [])
        return {
            "selected_columns": [
                column["name"] for column in columns if column.get("selected")
            ],
            "rename_mapping": {
                column["name"]: column["rename"]
                for column in columns
                if column.get("rename")
            },
            "dtype_mapping": {
                column["name"]: column.get("dtype", "")
                for column in columns
                if column.get("dtype")
            },
            "column_order": [column["name"] for column in columns],
            "auto_accept_new_columns": bool(
                self.settings.get("auto_accept_new_columns", True)
            ),
        }

    def _rows_from_settings(self) -> list[RowData]:
        schema = self.schema(0)
        rows: list[RowData] = []
        for column in self.settings.get("columns") or []:
            name = str(column.get("name") or "")
            if not name:
                continue
            source = schema.get(name)
            dtype = str(column.get("dtype") or "")
            if not dtype:
                dtype = core.display_dtype(source) if source is not None else "String"
            rows.append(
                RowData(
                    checked=bool(column.get("selected")),
                    text=name,
                    dtype=dtype,
                    rename=str(column.get("rename") or ""),
                    is_missing=source is None,
                    date_format=str(column.get("date_format") or ""),
                )
            )
        return rows

    def _columns_from_rows(self, rows: list[RowData]) -> list[dict]:
        schema = self.schema(0)
        previous = {
            column.get("name"): column
            for column in (self.settings.get("columns") or [])
        }
        columns: list[dict] = []
        for row in rows:
            source = schema.get(row.text)
            old = previous.get(row.text, {})
            if source is None:
                custom = bool(old.get("dtype_custom", True))
            else:
                custom = row.dtype != core.display_dtype(source)
            columns.append(
                {
                    "name": row.text,
                    "selected": bool(row.checked),
                    "dtype": row.dtype,
                    "rename": row.rename,
                    "date_format": row.date_format,
                    "dtype_custom": custom,
                }
            )
        return columns

    def _on_table_data(self, _payload=None) -> None:
        if self._suspend_table:
            return
        if self.table_widget is not None:
            self.table_data = self.table_widget.rows()
        self.set_setting(
            "columns",
            self._columns_from_rows(self.table_data),
            "Select Columns Changed",
        )
        if self.table_widget is not None:
            self.table_widget.changes = self._table_changes()
        self.refresh_dock_context()

    def _commit_table(self) -> None:
        if self.table_widget is not None and self.table_data:
            self.table_widget.dataChanged.emit(
                self.table_widget.index(0, 0),
                self.table_widget.index(len(self.table_data) - 1, 3),
                [],
            )
        self._on_table_data()

    def _refresh_table(self) -> None:
        rows = self._rows_from_settings()
        self.table_data = rows
        if self.table_widget is not None:
            self.table_widget.set_rows(rows)
            self.table_widget.changes = self._table_changes()
        self._sync_auto_action()
        self.refresh_dock_context()

    def _sync_auto_action(self) -> None:
        action = self._auto_accept_action
        if action is None:
            return
        try:
            checked = bool(self.settings.get("auto_accept_new_columns", True))
            if action.isChecked() != checked:
                action.blockSignals(True)
                action.setChecked(checked)
                action.blockSignals(False)
        except RuntimeError:
            self._auto_accept_action = None

    def _sync_widgets_from_model(self) -> None:
        rows = self._rows_from_settings()
        if self.table_widget is not None and rows != self.table_widget.rows():
            self.table_data = rows
            self.table_widget.set_rows(rows)
            self.table_widget.changes = self._table_changes()
        elif self.table_widget is not None:
            self.table_data = self.table_widget.rows()
        self._sync_auto_action()
        self.refresh_dock_context()

    # ---- schema reconciliation -----------------------------------------
    def _reconcile_columns(self) -> bool:
        schema = self.schema(0)
        if not schema:
            return False
        columns = [dict(column) for column in (self.settings.get("columns") or [])]
        first_build = not columns
        auto = bool(self.settings.get("auto_accept_new_columns", True))
        existing = {column.get("name") for column in columns}
        changed = False

        for column in columns:
            column.setdefault("selected", False)
            column.setdefault("dtype", "")
            column.setdefault("rename", "")
            column.setdefault("date_format", "")
            column.setdefault("dtype_custom", False)
            name = column.get("name")
            if name in schema:
                source = core.display_dtype(schema[name])
                if not column.get("dtype_custom") and column.get("dtype") != source:
                    column["dtype"] = source
                    column["date_format"] = ""
                    changed = True

        new_names = [name for name in schema if name not in existing]
        for name in new_names:
            columns.append(
                {
                    "name": name,
                    "selected": bool(auto or first_build),
                    "dtype": core.display_dtype(schema[name]),
                    "rename": "",
                    "date_format": "",
                    "dtype_custom": False,
                }
            )
            changed = True

        if first_build:
            for column in columns:
                column["selected"] = True

        missing_changed = any(
            row.is_missing != (row.text not in schema) for row in self.table_data
        )
        if changed or first_build:
            self.settings["columns"] = columns
        if self.table_widget is not None and (
            changed or first_build or missing_changed
        ):
            self._refresh_table()
        return changed or first_build

    def compute(self) -> list:
        if self.frames[0] is not None:
            self._reconcile_columns()
        return super().compute()

    def apply_upstream_renames(self, rename_map: dict) -> bool:
        if not rename_map:
            return False
        columns = [dict(column) for column in (self.settings.get("columns") or [])]
        names = {column.get("name") for column in columns}
        changed = False
        for old, new in rename_map.items():
            if old not in names or new in names:
                continue
            for column in columns:
                if column.get("name") == old:
                    column["name"] = new
                    changed = True
            names.discard(old)
            names.add(new)
        if changed:
            self.settings["columns"] = columns
            if self.table_widget is not None:
                self._refresh_table()
            self.refresh_dock_context()
        return changed

    # ---- summary --------------------------------------------------------
    def dock_summary(self) -> str:
        columns = list(self.settings.get("columns") or [])
        selected = sum(1 for column in columns if column.get("selected"))
        renamed = sum(1 for column in columns if column.get("rename"))
        retyped = sum(1 for column in columns if column.get("dtype_custom"))
        parts = [f"{selected} of {len(columns)} columns selected"]
        if renamed:
            parts.append(f"{renamed} renamed")
        if retyped:
            parts.append(f"{retyped} retyped")
        return " \u00b7 ".join(parts)

    def dock_context(self):
        columns = list(self.settings.get("columns") or [])
        selected = sum(1 for column in columns if column.get("selected"))
        chips = [
            (f"{selected} of {len(columns)} columns", "accent" if selected else "")
        ]
        renamed = sum(1 for column in columns if column.get("rename"))
        retyped = sum(1 for column in columns if column.get("dtype_custom"))
        if renamed:
            chips.append((f"{renamed} renamed", ""))
        if retyped:
            chips.append((f"{retyped} retyped", ""))
        return chips, ""

    def _refresh_select_counts(self) -> None:
        self.refresh_dock_context()

    def select_all_columns(self) -> None:
        if self.table_widget is not None:
            self.table_widget.set_all_checked(True)

    def select_no_columns(self) -> None:
        if self.table_widget is not None:
            self.table_widget.set_all_checked(False)

    # ---- bulk tools -----------------------------------------------------
    def _bulk_target_rows(self, selected_only: bool) -> list[RowData]:
        if not selected_only:
            return list(self.table_data)
        try:
            selection = (
                self.table_view.selectionModel()
                if self.table_view is not None
                else None
            )
            if selection is None:
                return []
            rows: list[RowData] = []
            seen: set[int] = set()
            for index in selection.selectedRows():
                if isinstance(self.table_view.model(), QSortFilterProxyModel):
                    index = self.table_view.model().mapToSource(index)
                row = index.row()
                if 0 <= row < len(self.table_data) and row not in seen:
                    seen.add(row)
                    rows.append(self.table_data[row])
            return rows
        except RuntimeError:
            return []

    def prompt_bulk_affix(self, selected_only: bool, is_prefix: bool) -> None:
        scope = "Selected" if selected_only else "All"
        kind = "Prefix" if is_prefix else "Suffix"
        affix, accepted = QInputDialog.getText(
            None, f"Add {kind} ({scope})", f"{kind} to add:"
        )
        if not accepted or not affix:
            return
        rows = self._bulk_target_rows(selected_only)
        if not rows:
            return
        for row in rows:
            base = row.rename or row.text
            row.rename = f"{affix}{base}" if is_prefix else f"{base}{affix}"
        self._commit_table()

    def bulk_clear_renames(self, selected_only: bool) -> None:
        rows = self._bulk_target_rows(selected_only)
        if not rows:
            return
        for row in rows:
            row.rename = ""
        self._commit_table()

    def bulk_reset_dtypes(self, selected_only: bool) -> None:
        schema = self.schema(0)
        rows = self._bulk_target_rows(selected_only)
        if not rows:
            return
        for row in rows:
            if row.text in schema:
                row.dtype = core.display_dtype(schema[row.text])
                row.date_format = ""
        self._commit_table()

    def bulk_auto_detect(self, selected_only: bool) -> None:
        schema = self.schema(0)
        rows = self._bulk_target_rows(selected_only)
        if not rows:
            return
        columns = [row.text for row in rows if row.text in schema]
        samples = self._sample_columns(columns)
        for row in rows:
            if row.text not in schema:
                continue
            dtype, date_format = core.infer_dtype(samples.get(row.text, []))
            if dtype is not None:
                row.dtype = dtype
                row.date_format = date_format or ""
        self._commit_table()

    def _sample_columns(self, columns: list[str]) -> dict[str, list]:
        if not columns or self.frames[0] is None:
            return {}
        try:
            frame = (
                self.frames[0]
                .select([pl.col(column).cast(pl.String) for column in columns])
                .head(self.BULK_SAMPLE_ROWS)
                .collect()
            )
        except Exception:  # noqa: BLE001 - sampling is advisory
            return {}
        return {column: frame.get_column(column).to_list() for column in columns}

    def _on_auto_accept_toggled(self, checked: bool) -> None:
        self.set_setting(
            "auto_accept_new_columns",
            bool(checked),
            "Select Auto Accept Changed",
        )

    # ---- old saved workflow loader -------------------------------------
    def deserialize(self, data, hashmap={}):  # noqa: B006
        """Load old Select content into the new ordered-columns setting.

        This is a one-way migration for checked-in workflows and existing
        files. The new runtime only ever writes ``settings``.
        """
        if "settings" not in data and ("table_data" in data or "changes" in data):
            data = dict(data)
            data["settings"] = self._legacy_settings(data)
        return super().deserialize(data, hashmap)

    def _legacy_settings(self, data: dict) -> dict:
        changes = data.get("changes") or {}
        dtype_mapping = changes.get("dtype_mapping") or {}
        rename_mapping = changes.get("rename_mapping") or {}
        selected = set(changes.get("selected_columns") or [])
        columns = []
        for row in data.get("table_data") or []:
            name = str(row.get("text") or row.get("column_name") or "")
            if not name:
                continue
            checked = row.get("checked")
            if checked is None:
                checked = name in selected
            dtype = self._legacy_dtype(
                row.get("dtype") or dtype_mapping.get(name, "String")
            )
            columns.append(
                {
                    "name": name,
                    "selected": bool(checked),
                    "dtype": dtype,
                    "rename": str(row.get("rename") or rename_mapping.get(name) or ""),
                    "date_format": str(row.get("date_format") or ""),
                    "dtype_custom": name in dtype_mapping,
                }
            )
        if not columns:
            for name in changes.get("selected_columns") or []:
                columns.append(
                    {
                        "name": str(name),
                        "selected": True,
                        "dtype": self._legacy_dtype(dtype_mapping.get(name, "String")),
                        "rename": str(rename_mapping.get(name) or ""),
                        "date_format": "",
                        "dtype_custom": name in dtype_mapping,
                    }
                )
        return {
            "columns": columns,
            "auto_accept_new_columns": bool(
                changes.get("auto_accept_new_columns", True)
            ),
        }

    @staticmethod
    def _legacy_dtype(dtype) -> str:
        text = str(dtype)
        return {
            "object": "String",
            "int64": "Int64",
            "float64": "Float64",
            "bool": "Boolean",
            "datetime64": "Datetime",
        }.get(text, text)


@register_node(PreparationNodes.SELECT, NodeTypes.PREPARATION)
class TriggerNode_Select(ShapingNode):
    """Select node on the shared shaping execution and Config Dock system."""

    icon = "node_select"
    node_code = PreparationNodes.SELECT
    node_type = NodeTypes.PREPARATION
    node_title = "Select"
    content_class = SelectContent
    output_text = ("Out",)
    content_label_objname = "trigger_node_select"
    style = {}  # noqa: RUF012 - shared empty node style

    def processInputs(self, input_values):
        try:
            input_node = self.getInput(0)
            if input_node is not None:
                self.content.apply_upstream_renames(upstream_rename_map(input_node))
        except AttributeError, ValueError, RuntimeError:
            pass
        return super().processInputs(input_values)
