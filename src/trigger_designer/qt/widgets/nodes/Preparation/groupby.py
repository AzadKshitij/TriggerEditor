import copy

import polars as pl
from qtpy.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QFrame,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QSplitter,
)
from qtpy.QtGui import QPixmap
from qtpy.QtCore import (
    Qt,
    Signal,
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
from trigger_designer.qt.widgets.common import (
    EmptyStateLabel,
    IconButton,
    NoWheelComboBox,
)
from trigger_designer.qt.undo.protocol import is_syncing
from nodeeditor.utils_no_qt import dumpException

from trigger_designer.qt.helpers import global_logger
from typing import (
    Optional,
    TYPE_CHECKING,
)

if TYPE_CHECKING:
    import polars as pl


AGGREGATION_FUNCTIONS = [
    "GroupBy",
    "Count",
    "Sum",
    "Mean",
    "Min",
    "Max",
    "Std",
    "Var",
    "Median",
    "First",
    "Last",
    "N_Unique",
    "List",
]

ACTION_TO_FUNCTION = {
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
    "List": "list",
}

FUNCTION_TO_ACTION = {
    "count": "Count",
    "sum": "Sum",
    "mean": "Mean",
    "min": "Min",
    "max": "Max",
    "std": "Std",
    "var": "Var",
    "median": "Median",
    "first": "First",
    "last": "Last",
    "n_unique": "N_Unique",
    "list": "List",
}

PREFIX_MAP = {
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
    "List": "List_",
}


def _default_output_name(field: str, action: str) -> str:
    if action == "GroupBy":
        return field
    return f"{PREFIX_MAP.get(action, '')}{field}"


class GroupByContent(QDMNodeIconContentWidget, TriggerChangeHandler):
    """DataFrame group-by and aggregation widget (displayed as Aggregate).

    Model (``self.changes``) is the only truth; the tables are a projection.
    Edits update the model with undo support and defer the heavy polars
    recompute until the node is deselected (see ``commit_pending_dock_edits``).
    """

    evaluate = Signal()  # Emit when deselect-commit recomputes

    @staticmethod
    def _normalize_changes(changes: Optional[dict]) -> dict:
        """Ensure serialized Aggregate state always has the expected keys."""
        normalized_changes = changes if isinstance(changes, dict) else {}
        return {
            "group_by_columns": list(normalized_changes.get("group_by_columns", [])),
            "aggregations": dict(normalized_changes.get("aggregations", {})),
        }

    @staticmethod
    def _actions_data_from_changes(changes: Optional[dict]) -> list[dict[str, str]]:
        """Rebuild table rows from serialized Aggregate state."""
        normalized_changes = GroupByContent._normalize_changes(changes)
        actions_data = [
            {"field": column, "action": "GroupBy", "output_name": column}
            for column in normalized_changes["group_by_columns"]
        ]
        for column, config in normalized_changes["aggregations"].items():
            actions_data.append(
                {
                    "field": column,
                    "action": FUNCTION_TO_ACTION.get(
                        config.get("function", "count"), "Count"
                    ),
                    "output_name": config.get("alias", column),
                }
            )
        return actions_data

    @staticmethod
    def _changes_from_actions(actions: list[dict]) -> dict:
        """Pure inverse of ``_actions_data_from_changes`` (old files compat)."""
        group_by_columns: list[str] = []
        aggregations: dict = {}
        for entry in actions:
            field = str(entry.get("field", ""))
            if not field:
                continue
            action = str(entry.get("action", "Count"))
            # Accept legacy "Group By" spelling.
            if action in ("GroupBy", "Group By"):
                if field not in group_by_columns:
                    group_by_columns.append(field)
                continue
            output_name = str(
                entry.get("output_name") or _default_output_name(field, action)
            )
            aggregations[field] = {
                "function": ACTION_TO_FUNCTION.get(action, "count"),
                "alias": output_name,
            }
        return {"group_by_columns": group_by_columns, "aggregations": aggregations}

    def __init__(self, node: "TriggerNode", parent: Optional[QWidget] = None) -> None:
        super().__init__(node, parent)
        global_logger.debug(
            "AggregateContent: Initializing Aggregate node content widget"
        )

        # Local variables
        self.history = self.node.scene.history

        # Incoming variables
        self.incoming_variable: str = ""
        self.incom_data: Optional[pl.DataFrame] = None

        # Pass on variables
        self.data: Optional[pl.DataFrame] = None
        self.variable_name: str = f"var_groupby_{self.id}"

        # Configuration for operations (model truth)
        self.changes: dict = self._normalize_changes(None)

        # Cache for serialization safety
        self.cached_actions_data: list = []

        # Dock widgets (rebuilt on every selection)
        self.fields_table: Optional[QTableWidget] = None
        self.actions_table: Optional[QTableWidget] = None
        self.search_input: Optional[QLineEdit] = None
        self._building_table = False

    @property
    def node(self) -> "TriggerNode":
        return self._node

    @node.setter
    def node(self, value: "TriggerNode") -> None:
        self._node = value

    def initUI(self, icon: Optional[QPixmap] = None) -> None:
        _icon: QPixmap = self.node.rsm.get(f"{self.node.icon}")
        super().initUI(_icon)

    def _guarded(self) -> bool:
        if getattr(self.history, "is_restoring_history", False):
            return True
        if is_syncing(self):
            return True
        return self._building_table

    def create_layout(self, dock_layout: QVBoxLayout) -> None:
        if self.incom_data is not None:
            global_logger.debug(
                f"AggregateContent: Creating layout for {len(frame_schema(self.incom_data))} columns"
            )
            self.changes = self._normalize_changes(getattr(self, "changes", None))

            # Adopt legacy actions_data when changes are empty (old files, or
            # sessions affected by the list-command corruption bug).
            pending = getattr(self, "actions_data", None)
            if not pending:
                pending = getattr(self, "cached_actions_data", None)
            if (
                pending
                and not self.changes["group_by_columns"]
                and not self.changes["aggregations"]
            ):
                try:
                    self.changes = self._normalize_changes(
                        self._changes_from_actions(pending)
                    )
                    self.cached_actions_data = self._actions_data_from_changes(
                        self.changes
                    )
                except Exception:
                    pass

            main_widget = QWidget()
            main_layout = QVBoxLayout(main_widget)
            main_layout.setContentsMargins(5, 5, 5, 5)
            main_layout.setSpacing(2)

            # Fields toolbar: search only (H40, margins 0 per design system)
            toolbar_widget = QWidget()
            toolbar_layout = QHBoxLayout(toolbar_widget)
            toolbar_layout.setContentsMargins(0, 0, 0, 0)
            toolbar_widget.setFixedHeight(40)
            self.search_input = QLineEdit()
            self.search_input.setPlaceholderText("Search fields...")
            self.search_input.setClearButtonEnabled(True)
            self.search_input.setMinimumHeight(30)
            self.search_input.textChanged.connect(self._filter_fields)
            toolbar_layout.addWidget(self.search_input)

            # Fields section
            fields_widget = QWidget()
            fields_layout = QVBoxLayout(fields_widget)
            fields_layout.setContentsMargins(0, 0, 0, 0)
            fields_layout.setSpacing(2)
            fields_label = QLabel("Fields")
            fields_label.setObjectName("ConfigSectionInfo")
            fields_layout.addWidget(fields_label)
            fields_layout.addWidget(toolbar_widget)
            self.create_fields_table()
            fields_layout.addWidget(self.fields_table)
            fields_widget.setMinimumHeight(200)

            # + button between Fields and Actions (centered, icon-only)
            add_button_widget = QWidget()
            add_button_layout = QHBoxLayout(add_button_widget)
            add_button_layout.setContentsMargins(0, 0, 0, 0)
            add_button_layout.addStretch()
            self.add_btn = IconButton.themed(
                "Add selected field as group key",
                rsm_icon=self.node.rsm.get("icon_add"),
            )
            self.add_btn.clicked.connect(self.add_selected_field)
            add_button_layout.addWidget(self.add_btn)
            add_button_layout.addStretch()
            add_button_widget.setFixedHeight(40)

            # Actions section
            actions_widget = QWidget()
            actions_layout = QVBoxLayout(actions_widget)
            actions_layout.setContentsMargins(0, 0, 0, 0)
            actions_layout.setSpacing(2)
            actions_label = QLabel("Actions")
            actions_label.setObjectName("ConfigSectionInfo")
            actions_layout.addWidget(actions_label)
            self.create_actions_table()
            actions_layout.addWidget(self.actions_table)
            actions_widget.setMinimumHeight(200)

            # Splitter: Fields | + | Actions so tables stay resizable
            self.splitter = QSplitter(Qt.Orientation.Vertical)
            self.splitter.setChildrenCollapsible(False)
            self.splitter.addWidget(fields_widget)
            self.splitter.addWidget(add_button_widget)
            self.splitter.addWidget(actions_widget)
            self.splitter.setStretchFactor(0, 1)
            self.splitter.setStretchFactor(1, 0)
            self.splitter.setStretchFactor(2, 1)

            main_layout.addWidget(self.splitter, 1)

            # Remove-row controls (icon-only); no Apply button: commit on deselect.
            actions_button_layout = QHBoxLayout()
            actions_button_layout.setContentsMargins(0, 0, 0, 0)
            self.remove_btn = IconButton.themed(
                "Remove selected action",
                rsm_icon=self.node.rsm.get("icon_remove"),
            )
            self.remove_btn.clicked.connect(self.remove_selected_action)
            actions_button_layout.addWidget(self.remove_btn)
            actions_button_layout.addStretch()
            main_layout.addLayout(actions_button_layout)

            # Scroll container: when the dock is shorter than the sections'
            # minimum heights, the dock itself scrolls instead of pushing
            # content out of bounds. QScrollArea (not QAbstractScrollArea)
            # so the undo sweep in iter_dock_widgets still reaches controls.
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setWidget(main_widget)
            dock_layout.addWidget(scroll, 1)

            # Project model -> widgets (no recompute here; deselect commits).
            self._rebuild_widgets()
            self.cached_actions_data = self._actions_data_from_changes(self.changes)
        else:
            dock_layout.addWidget(EmptyStateLabel())

    def create_fields_table(self) -> None:
        """Create the fields table showing available columns"""
        self.fields_table = QTableWidget()
        self.fields_table.setColumnCount(2)
        self.fields_table.setHorizontalHeaderLabels(["Field", "Type"])
        self.fields_table.setAlternatingRowColors(True)
        self.fields_table.setWordWrap(False)
        self.fields_table.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOn
        )
        self.fields_table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.fields_table.setMinimumHeight(110)
        self.fields_table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.fields_table.verticalHeader().setVisible(False)

        schema = frame_schema(self.incom_data)
        self.fields_table.setRowCount(len(schema))
        for row, column in enumerate(schema):
            field_item = QTableWidgetItem(column)
            field_item.setFlags(field_item.flags() | Qt.ItemFlag.ItemIsSelectable)
            self.fields_table.setItem(row, 0, field_item)
            dtype = str(schema[column])
            type_item = QTableWidgetItem(dtype)
            type_item.setFlags(type_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.fields_table.setItem(row, 1, type_item)

        self.fields_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        header = self.fields_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.fields_table.setColumnWidth(0, 220)
        self.fields_table.setColumnWidth(1, 140)
        if self.search_input is not None and self.search_input.text():
            self._filter_fields(self.search_input.text())

    def create_actions_table(self) -> None:
        """Create the actions table shell; rows come from ``_rebuild_widgets``."""
        self.actions_table = QTableWidget()
        self.actions_table.setColumnCount(3)
        self.actions_table.setHorizontalHeaderLabels(
            ["Field", "Action", "Output Field Name"]
        )
        self.actions_table.setAlternatingRowColors(True)
        self.actions_table.setWordWrap(False)
        self.actions_table.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOn
        )
        self.actions_table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.actions_table.setMinimumHeight(110)
        self.actions_table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.actions_table.verticalHeader().setVisible(False)
        self.actions_table.setRowCount(0)
        self.actions_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.actions_table.setSelectionMode(
            QTableWidget.SelectionMode.ExtendedSelection
        )
        header = self.actions_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.actions_table.setColumnWidth(0, 180)
        self.actions_table.setColumnWidth(1, 120)
        self.actions_table.setColumnWidth(2, 240)
        self.actions_table.itemChanged.connect(self._on_alias_edited)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def _filter_fields(self, text: str) -> None:
        if self.fields_table is None:
            return
        needle = (text or "").strip().lower()
        try:
            for row in range(self.fields_table.rowCount()):
                item = self.fields_table.item(row, 0)
                name = item.text().lower() if item else ""
                self.fields_table.setRowHidden(row, bool(needle and needle not in name))
        except RuntimeError:
            pass

    # ------------------------------------------------------------------
    # Model helpers (model is the only truth)
    # ------------------------------------------------------------------

    def _current_actions(self) -> list[dict[str, str]]:
        return self._actions_data_from_changes(self.changes)

    def _set_model(
        self,
        new_changes: dict,
        text: str,
        structural: bool,
        merge_key: Optional[str] = None,
    ) -> bool:
        old = copy.deepcopy(self.changes)
        new = self._normalize_changes(copy.deepcopy(new_changes))
        if old == new:
            return False
        self.changes = new
        self.cached_actions_data = self._actions_data_from_changes(new)
        # NOTE: the model is a dict, so even structural edits travel as a
        # property change (with rebuild=True). push_list_change assumes a
        # list value and would store list(changes) == its key names,
        # corrupting the model into ["group_by_columns", "aggregations"].
        # Pushing runs the command's redo() synchronously, whose restore
        # emits evaluate -> recompute. Suspend that: the heavy recompute
        # happens only on deselect-commit, not on every click/keystroke.
        self._suspend_node_evaluation = True
        try:
            pushed = self.push_property_change(
                ("changes",),
                old,
                new,
                text,
                rebuild=structural,
                merge_key=merge_key,
            )
        finally:
            self._suspend_node_evaluation = False
        if not pushed:
            self.sync_from_model(rebuild=structural, evaluate=False)
        return True

    def _row_for_sender(self, widget) -> int:
        if self.actions_table is None:
            return -1
        try:
            for row in range(self.actions_table.rowCount()):
                if self.actions_table.cellWidget(row, 1) is widget:
                    return row
        except RuntimeError:
            return -1
        return -1

    # ------------------------------------------------------------------
    # Dock slots (widget -> model; no recompute here)
    # ------------------------------------------------------------------

    def add_selected_field(self) -> None:
        """Add selected fields to the model, then re-project."""
        if self._guarded():
            return
        if self.fields_table is None:
            return
        try:
            selected = self.fields_table.selectionModel().selectedRows()
        except RuntimeError:
            return
        if not selected:
            return
        existing = {a["field"] for a in self._current_actions()}
        actions = self._current_actions()
        added = 0
        for index in selected:
            try:
                row = index.row()
                item = self.fields_table.item(row, 0)
            except RuntimeError:
                continue
            if item is None:
                continue
            field_name = item.text()
            if field_name in existing:
                continue
            actions.append(
                {
                    "field": field_name,
                    "action": "Count",
                    "output_name": _default_output_name(field_name, "Count"),
                }
            )
            existing.add(field_name)
            added += 1
        if added:
            self._set_model(
                self._changes_from_actions(actions),
                "Aggregate Field Added",
                structural=True,
            )

    def remove_selected_action(self) -> None:
        """Remove selected actions from the model, then re-project."""
        if self._guarded() or self.actions_table is None:
            return
        try:
            selected = self.actions_table.selectionModel().selectedRows()
        except RuntimeError:
            return
        if not selected:
            return
        doomed = set()
        for index in selected:
            try:
                item = self.actions_table.item(index.row(), 0)
            except RuntimeError:
                continue
            if item is not None:
                doomed.add(item.text())
        if not doomed:
            return
        actions = [a for a in self._current_actions() if a["field"] not in doomed]
        self._set_model(
            self._changes_from_actions(actions),
            "Aggregate Field Removed",
            structural=True,
        )

    def _on_action_combo_changed(self, _text: str = "") -> None:
        if self._guarded() or self.actions_table is None:
            return
        combo = self.sender()
        if combo is None:
            return
        row = self._row_for_sender(combo)
        if row < 0:
            return
        try:
            field_item = self.actions_table.item(row, 0)
            action = combo.currentText()
        except RuntimeError:
            return
        if field_item is None:
            return
        field_name = field_item.text()
        actions = self._current_actions()
        for entry in actions:
            if entry["field"] == field_name:
                entry["action"] = action
                entry["output_name"] = _default_output_name(field_name, action)
                break
        else:
            return
        self._set_model(
            self._changes_from_actions(actions),
            "Aggregate Action Changed",
            structural=False,
        )

    def _on_alias_edited(self, item: QTableWidgetItem) -> None:
        if self._guarded() or self.actions_table is None or item is None:
            return
        try:
            if item.column() != 2:
                return
            row = item.row()
            field_item = self.actions_table.item(row, 0)
        except RuntimeError:
            return
        if field_item is None:
            return
        field_name = field_item.text()
        alias = item.text()
        actions = self._current_actions()
        for entry in actions:
            if entry["field"] == field_name:
                if entry["output_name"] == alias:
                    return
                entry["output_name"] = alias
                break
        else:
            return
        self._set_model(
            self._changes_from_actions(actions),
            "Aggregate Output Renamed",
            structural=False,
            merge_key="aggregate-alias",
        )

    # ------------------------------------------------------------------
    # Undo projection (model -> widget; never re-records)
    # ------------------------------------------------------------------

    def _rebuild_widgets(self) -> None:
        if self.actions_table is None:
            return
        self._building_table = True
        try:
            try:
                self.actions_table.blockSignals(True)
            except RuntimeError:
                return
            try:
                self.actions_table.setRowCount(0)
            except RuntimeError:
                return
            for entry in self._current_actions():
                self._insert_action_row(
                    entry["field"], entry["action"], entry["output_name"]
                )
        finally:
            try:
                self.actions_table.blockSignals(False)
            except RuntimeError:
                pass
            self._building_table = False

    def _insert_action_row(
        self, field_name: str, action: str, output_name: str
    ) -> None:
        row = self.actions_table.rowCount()
        self.actions_table.insertRow(row)
        field_item = QTableWidgetItem(field_name)
        field_item.setFlags(field_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.actions_table.setItem(row, 0, field_item)
        combo = NoWheelComboBox()
        combo.addItems(AGGREGATION_FUNCTIONS)
        combo.setMinimumHeight(30)
        combo.setCurrentText(action if action in AGGREGATION_FUNCTIONS else "Count")
        combo.currentTextChanged.connect(self._on_action_combo_changed)
        self.actions_table.setCellWidget(row, 1, combo)
        self.actions_table.setItem(row, 2, QTableWidgetItem(output_name))

    def _sync_widgets_from_model(self) -> None:
        if self.actions_table is None:
            return
        actions = self._current_actions()
        try:
            count = self.actions_table.rowCount()
        except RuntimeError:
            return
        if count != len(actions):
            self._rebuild_widgets()
            return
        self._building_table = True
        try:
            try:
                self.actions_table.blockSignals(True)
            except RuntimeError:
                return
            for row, entry in enumerate(actions):
                try:
                    field_item = self.actions_table.item(row, 0)
                    output_item = self.actions_table.item(row, 2)
                    combo = self.actions_table.cellWidget(row, 1)
                except RuntimeError:
                    continue
                if field_item is not None and field_item.text() != entry["field"]:
                    field_item.setText(entry["field"])
                if combo is not None and combo.currentText() != entry["action"]:
                    combo.setCurrentText(entry["action"])
                if (
                    output_item is not None
                    and output_item.text() != entry["output_name"]
                ):
                    output_item.setText(entry["output_name"])
        finally:
            try:
                self.actions_table.blockSignals(False)
            except RuntimeError:
                pass
            self._building_table = False

    # ------------------------------------------------------------------
    # Deselect commit (the only recompute path from the dock)
    # ------------------------------------------------------------------

    def commit_pending_dock_edits(self) -> None:
        """Recompute from the model. Called by the Config Dock on deselect."""
        try:
            self.apply_groupby(emit_evaluate=True)
        except Exception as e:
            global_logger.error(f"Aggregate commit on deselect failed: {e}")

    # ------------------------------------------------------------------
    # Execution (reads the model only; never the widgets)
    # ------------------------------------------------------------------

    def apply_groupby(self, emit_evaluate: bool = False) -> None:
        """Apply the Aggregate operations to the data"""
        global_logger.info("AggregateContent: Applying Aggregate operations")

        if self.incom_data is None:
            global_logger.warning("AggregateContent: No input data available")
            return

        changes = self._normalize_changes(self.changes)
        self.changes = changes
        group_by_columns = changes["group_by_columns"]
        aggregations = changes["aggregations"]

        if not group_by_columns and not aggregations:
            global_logger.warning("AggregateContent: No operations configured")
            return

        try:
            available_columns = list(frame_schema(self.incom_data))

            if group_by_columns:
                valid_group_columns = [
                    col for col in group_by_columns if col in available_columns
                ]
                if not valid_group_columns:
                    global_logger.error(
                        "AggregateContent: No valid group by columns found"
                    )
                    return
                grouped = self.incom_data.group_by(valid_group_columns)
                agg_expressions = []
                for column, config in aggregations.items():
                    if column not in available_columns:
                        continue
                    func_name = config["function"]
                    alias = config["alias"]
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
                        continue
                    agg_expressions.append(expr)
                if agg_expressions:
                    self.data = grouped.agg(agg_expressions)
                else:
                    self.data = grouped.agg(pl.len().alias("count"))
            else:
                agg_expressions = []
                for column, config in aggregations.items():
                    if column not in available_columns:
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

            global_logger.info(
                f"AggregateContent: completed - shape: {frame_shape(self.data)}"
            )
            if emit_evaluate:
                self.evaluate.emit()
        except Exception as e:
            global_logger.error(f"AggregateContent: operation failed: {str(e)}")
            self.data = None

    def reset_configuration(self) -> None:
        """Reset the Aggregate configuration"""
        old = copy.deepcopy(self.changes)
        new = self._normalize_changes(None)
        if old == new:
            return
        self.changes = new
        self.cached_actions_data = []
        self.push_property_change(
            ("changes",), old, new, "Aggregate Reset", rebuild=True
        )

    def get_code(self) -> str:
        """Generate Polars code for the Aggregate operation"""
        if not self.incoming_variable:
            return f"import polars as pl\n{self.variable_name} = pl.DataFrame()\n"

        code_lines = []
        changes = self._normalize_changes(self.changes)
        self.changes = changes
        group_by_columns = changes["group_by_columns"]
        aggregations = changes["aggregations"]

        if not group_by_columns and not aggregations:
            return f"# No Aggregate operation configured\n{self.variable_name} = {self.incoming_variable}\n"

        agg_expressions = []
        for column, config in aggregations.items():
            func_name = config["function"]
            alias = config["alias"]
            if func_name == "count":
                agg_expressions.append(f"pl.len().alias('{alias}')")
            elif func_name in [
                "sum",
                "mean",
                "min",
                "max",
                "std",
                "var",
                "median",
                "first",
                "last",
                "n_unique",
            ]:
                agg_expressions.append(
                    f"pl.col('{column}').{func_name}().alias('{alias}')"
                )
            elif func_name == "list":
                agg_expressions.append(f"pl.col('{column}').list().alias('{alias}')")

        if group_by_columns:
            group_cols_str = ", ".join([f"'{col}'" for col in group_by_columns])
            if not agg_expressions:
                agg_expressions.append("pl.len().alias('count')")
            agg_str = ",\n    ".join(agg_expressions)
            code_lines.append(
                f"{self.variable_name} = {self.incoming_variable}.group_by([{group_cols_str}]).agg(["
            )
            code_lines.append(f"    {agg_str}")
            code_lines.append("])")
        else:
            if agg_expressions:
                agg_str = ",\n    ".join(agg_expressions)
                code_lines.append(
                    f"{self.variable_name} = {self.incoming_variable}.select(["
                )
                code_lines.append(f"    {agg_str}")
                code_lines.append("])")
            else:
                code_lines.append(f"{self.variable_name} = {self.incoming_variable}")

        return "\n".join(code_lines) + "\n"

    def serialize(self):
        """Serialize the Aggregate configuration from the model (never widgets)."""
        res = super().serialize()
        changes = self._normalize_changes(getattr(self, "changes", None))
        actions_data = self._actions_data_from_changes(changes)
        res["actions_data"] = actions_data
        res["changes"] = changes
        self.cached_actions_data = actions_data
        return res

    def deserialize(self, data, hashmap={}):
        """Deserialize the Aggregate configuration"""
        res = super().deserialize(data, hashmap)
        try:
            changes = data.get("changes")
            if not changes and data.get("actions_data"):
                changes = self._changes_from_actions(data.get("actions_data") or [])
            self.changes = self._normalize_changes(changes)
            self.actions_data = data.get(
                "actions_data"
            ) or self._actions_data_from_changes(self.changes)
            self.cached_actions_data = list(self.actions_data)
            return True and res
        except Exception as e:
            global_logger.error(f"AggregateContent: Deserialization failed: {str(e)}")
            dumpException(e)
        return res


@register_node(PreparationNodes.GROUPBY, NodeTypes.PREPARATION)
class TriggerNode_GroupBy(TriggerNode):
    icon = "node_groupby"
    node_code = PreparationNodes.GROUPBY
    node_title = "Aggregate"
    node_type = NodeTypes.PREPARATION
    content_label_objname = "trigger_node_groupby"
    style = {}

    def __init__(self, scene) -> None:
        global_logger.info("AggregateNode: Initializing Aggregate node")
        super().__init__(scene, inputs=[1], outputs=[3])
        self.eval()

    def initInnerClasses(self) -> None:
        self.content: GroupByContent = GroupByContent(self)
        self.grNode: TriggerGraphicsNode = TriggerGraphicsNode(self)
        self.content.evaluate.connect(self.onInputChanged)
        self.param: list = []

    @staticmethod
    def _resolve_input_value(input_values, socket_index):
        """Pick the dict-like payload out of the upstream value.

        Upstream ``param`` lists are usually one dict per output socket, but
        some nodes emit nested/ragged shapes, so unwrap defensively instead
        of assuming ``input_values[0][socket_index]`` is a dict.
        """
        raw = input_values[0] if input_values else None
        if isinstance(raw, (list, tuple)):
            if 0 <= socket_index < len(raw):
                candidate = raw[socket_index]
            elif raw:
                candidate = raw[0]
            else:
                return None
        else:
            candidate = raw
        # Unwrap single-element nesting such as [[{...}]].
        while isinstance(candidate, (list, tuple)) and len(candidate) == 1:
            candidate = candidate[0]
        if isinstance(candidate, (list, tuple)):
            candidate = next((v for v in candidate if isinstance(v, dict)), None)
        return candidate if isinstance(candidate, dict) else None

    def processInputs(self, input_values):
        global_logger.info("AggregateNode: Starting input processing")
        try:
            input_node = self.getInput(0)
            if input_node is None:
                self.markDirty(True)
                self.markInvalid(True)
                self.grNode.setToolTip("Input is not connected")
                return None
            try:
                socket_index = self.getSocketValue(input_node.outputs, self)
            except (ValueError, AttributeError):
                socket_index = 0
            input_value = self._resolve_input_value(input_values, socket_index)
            if input_value:
                input_data = input_value.get("data")
                variable_name = input_value.get("variable_name", "unknown")
                if input_data is not None:
                    self.markDirty(False)
                    self.markInvalid(False)
                    self.content.incom_data = input_data
                    self.content.incoming_variable = variable_name
                    # Heal in-memory state corrupted by the old list-command
                    # bug (changes stored as a key list instead of a dict):
                    # rebuild from the cached actions before falling back
                    # to empty.
                    raw_changes = getattr(self.content, "changes", None)
                    if not isinstance(raw_changes, dict):
                        cached = getattr(self.content, "cached_actions_data", None)
                        if cached:
                            try:
                                raw_changes = GroupByContent._changes_from_actions(
                                    cached
                                )
                            except Exception:
                                raw_changes = None
                    self.content.changes = GroupByContent._normalize_changes(
                        raw_changes
                    )
                    if self.content.changes.get(
                        "group_by_columns"
                    ) or self.content.changes.get("aggregations"):
                        self.content.apply_groupby(emit_evaluate=False)
                    else:
                        self.content.data = input_data
                    if hasattr(self.content, "data") and self.content.data is not None:
                        self.param = [
                            {
                                "data": self.content.data,
                                "variable_name": self.content.variable_name,
                            }
                        ]
                        self.evalChildren()
                        return self.param
                    else:
                        self.markDirty(True)
                        self.markInvalid(True)
                        return None
                else:
                    self.markDirty(True)
                    self.markInvalid(True)
                    return None
            else:
                self.markDirty(True)
                self.markInvalid(True)
                self.grNode.setToolTip("Upstream produced no usable output")
                return None
        except Exception as e:
            global_logger.error(
                f"AggregateNode: Error during input processing: {str(e)}"
            )
            self.markDirty(True)
            self.markInvalid(True)
            self.grNode.setToolTip(f"Processing error: {str(e)}")
            return None

    def get_code(self):
        return self.content.get_code()
