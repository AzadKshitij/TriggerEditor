from qtpy.QtWidgets import (
    QVBoxLayout,
    QComboBox,
    QLineEdit,
    QLabel,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QCheckBox,
    QMenu,
    QWidget,
)
from qtpy.QtGui import QPixmap
from qtpy.QtCore import Qt, QTimer, Signal
from trigger_designer.core.node_configuration import register_node, JoinNodes, NodeTypes
from trigger_designer.qt.node_base import (
    TriggerChangeHandler,
    TriggerNode,
    TriggerGraphicsNode,
    frame_schema,
    upstream_rename_map,
)
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget
from trigger_designer.qt.widgets.common import (
    EmptyStateLabel,
    IconButton,
    NoWheelComboBox,
)
from nodeeditor.utils_no_qt import dumpException
from nodeeditor.node_scene_history import SceneHistory
import polars as pl
from loguru import logger as global_logger
from typing import Optional


class JoinContent(QDMNodeIconContentWidget, TriggerChangeHandler):
    """
    Join node content for performing Polars LazyFrame join operations.

    This widget provides a high-performance join interface using Polars LazyFrame
    operations for optimal memory usage and performance with large datasets.

    Features:
    - Multiple join types (inner, left, right, full outer)
    - Column mapping between left and right tables
    - Selective column output
    - Anti-join outputs for unmatched records
    - LazyFrame operations for performance

    Outputs:
    - L: Left-only data (anti-join results)
    - J: Joined data (main join results)
    - R: Right-only data (anti-join results)
    """

    evaluate = Signal()  # Emit when evaluate button is clicked

    def __init__(self, node: "TriggerNode", parent: Optional[QWidget] = None) -> None:
        super().__init__(node, parent)
        TriggerChangeHandler.__init__(self, self.node.scene, self.node)
        self.node = node

        global_logger.debug("🔄 Join: Initializing Join node content widget")

        # local variables
        self.join_type = "inner"  # Default join type
        self.mapping_data = []  # Store mapping pairs
        self.selected_columns = []
        self.mapping_pairs = []
        self.output_column_checkboxes = []
        # When True, columns arriving from upstream are included in the
        # output automatically. When False they appear unchecked until the
        # user ticks them. `known_columns` tracks every column seen (same
        # shape as `selected_columns`) so an explicit uncheck is never
        # mistaken for a new arrival.
        self.auto_accept_new_columns = True
        self.known_columns = []
        self._auto_accept_action = None
        self.history: SceneHistory = self.node.scene.history

        # Live-by-default: coalesce rapid edits into a single recompute.
        self._apply_timer = QTimer(self)
        self._apply_timer.setSingleShot(True)
        self._apply_timer.setInterval(300)
        self._apply_timer.timeout.connect(self._apply_debounced)
        self._applying = False

        # incoming variables
        self.left_data: Optional[pl.LazyFrame] = None
        self.right_data: Optional[pl.LazyFrame] = None
        self.left_variable: str = ""
        self.right_variable: str = ""

        # pass on variables
        self.data: Optional[pl.LazyFrame] = None
        self.l_data: Optional[pl.LazyFrame] = None
        self.r_data: Optional[pl.LazyFrame] = None
        self.l_variable_name = f"var_l_join_{self.id}"
        self.variable_name = f"var_join_{self.id}"
        self.r_variable_name = f"var_r_join_{self.id}"

    def initUI(self, parent: Optional[QWidget] = None) -> None:
        icon_: QPixmap = self.node.rsm.get(f"{self.node.icon}")
        super().initUI(icon_)

    def _get_frame_schema(
        self, frame: Optional[pl.DataFrame | pl.LazyFrame]
    ) -> dict[str, pl.DataType]:
        if frame is None:
            return {}

        schema = (
            frame.collect_schema() if isinstance(frame, pl.LazyFrame) else frame.schema
        )
        return {name: dtype for name, dtype in schema.items()}

    def _format_column_label(self, column_name: str, dtype: pl.DataType) -> str:
        return f"{column_name} [{dtype}]"

    def _populate_column_combo(
        self,
        combo: QComboBox,
        frame: Optional[pl.DataFrame | pl.LazyFrame],
        selected_column: Optional[str] = None,
    ) -> None:
        for column_name, dtype in self._get_frame_schema(frame).items():
            combo.addItem(self._format_column_label(column_name, dtype), column_name)

        if selected_column:
            selected_index = combo.findData(selected_column)
            if selected_index >= 0:
                combo.setCurrentIndex(selected_index)

    def _combo_current_column(self, combo: QComboBox) -> str:
        current_data = combo.currentData()
        return current_data if isinstance(current_data, str) else combo.currentText()

    def create_layout(self, dock_layout: QVBoxLayout) -> None:
        if self.left_data is not None and self.right_data is not None:
            global_logger.debug(
                f"🔄 Join: Creating layout for join with {len(self._get_frame_schema(self.left_data))} left columns and {len(self._get_frame_schema(self.right_data))} right columns"
            )
            self._sanitize_mapping_data()
            self._sanitize_selected_columns()
            try:
                self._follow_upstream_renames()
            except (
                AttributeError,
                ValueError,
                RuntimeError,
                IndexError,
            ) as follow_error:
                global_logger.debug(
                    f"🔄 Join: Could not follow upstream renames: {follow_error}"
                )
            self._sync_selected_with_schema()

            # Join columns mapping area
            join_mapping_layout = QVBoxLayout()
            join_mapping_layout.setContentsMargins(0, 0, 0, 0)
            join_mapping_layout.setSpacing(2)
            join_mapping_label = QLabel("Join column mapping")
            join_mapping_label.setObjectName("ConfigSectionInfo")
            join_mapping_layout.addWidget(join_mapping_label)

            # Container for mapping rows
            self.mapping_container = QVBoxLayout()
            self.mapping_container.setContentsMargins(0, 0, 0, 0)
            self.mapping_container.setSpacing(2)
            self.mapping_pairs = []

            # Add button for new mapping (icon-only per design system §4)
            add_mapping_button = IconButton.themed(
                "Add mapping",
                rsm_icon=self.node.rsm.get("icon_add"),
            )
            add_mapping_button.clicked.connect(self.add_mapping_row)

            join_mapping_layout.addLayout(self.mapping_container)
            join_mapping_layout.addWidget(add_mapping_button)

            # Output columns group: toolbar with search + bulk options menu
            output_layout = QVBoxLayout()
            output_layout.setContentsMargins(0, 0, 0, 0)
            output_layout.setSpacing(2)
            output_label = QLabel("Output columns")
            output_label.setObjectName("ConfigSectionInfo")
            output_layout.addWidget(output_label)

            output_toolbar = QWidget()
            output_toolbar.setFixedHeight(40)
            output_controls_layout = QHBoxLayout(output_toolbar)
            output_controls_layout.setContentsMargins(0, 0, 0, 0)

            self.output_search = QLineEdit()
            self.output_search.setPlaceholderText("Search columns...")
            self.output_search.setClearButtonEnabled(True)
            self.output_search.setMinimumHeight(30)
            self.output_search.textChanged.connect(self._filter_output_columns)
            output_controls_layout.addWidget(self.output_search)

            # Bulk select/clear moved into one Options menu (design system §4.4)
            self.output_options_btn = IconButton.themed(
                "Output column options",
                rsm_icon=self.node.rsm.get("icon_options"),
                qss_fallback=":/qss_icons/dark/rc/arrow_down.png",
            )
            self.output_options_btn.setObjectName("OptionsButton")
            self._build_output_options_menu(self.output_options_btn)
            output_controls_layout.addWidget(self.output_options_btn)

            self.output_columns_list = QListWidget()
            self.output_columns_list.setObjectName("JoinOutputList")
            output_layout.addWidget(output_toolbar)
            output_layout.addWidget(self.output_columns_list, 1)

            # Main layout assembly
            main_layout = QVBoxLayout()
            main_layout.setContentsMargins(5, 5, 5, 5)
            main_layout.setSpacing(2)
            main_layout.addLayout(join_mapping_layout)
            main_layout.addLayout(output_layout, 1)

            # Evaluate (icon-only); edits also apply live via the debounced timer
            self.eval_button = IconButton.themed(
                "Evaluate join now",
                rsm_icon=self.node.rsm.get("icon_apply"),
                qss_fallback=":/qss_icons/dark/rc/checkbox_checked.png",
                theme_fallback="emblem-ok",
            )
            self.eval_button.clicked.connect(self.transform_data)
            main_layout.addWidget(self.eval_button)

            dock_layout.addLayout(main_layout)
            # Update UI after layout is created

            self.load_saved_data()
            self.update_output_columns()

            self.recursively_find_widgets(dock_layout)

        else:
            dock_layout.addWidget(EmptyStateLabel("Both inputs must be connected"))

    def _build_output_options_menu(self, button: QWidget) -> None:
        """Bulk left/right selection lives in one menu, not four text buttons."""
        menu = QMenu(button)
        check_left = menu.addAction("Check all left columns")
        check_left.triggered.connect(
            lambda: self._set_output_columns_checked("L", True)
        )
        clear_left = menu.addAction("Uncheck all left columns")
        clear_left.triggered.connect(
            lambda: self._set_output_columns_checked("L", False)
        )
        menu.addSeparator()
        check_right = menu.addAction("Check all right columns")
        check_right.triggered.connect(
            lambda: self._set_output_columns_checked("R", True)
        )
        clear_right = menu.addAction("Uncheck all right columns")
        clear_right.triggered.connect(
            lambda: self._set_output_columns_checked("R", False)
        )
        menu.addSeparator()
        self._auto_accept_action = menu.addAction("Auto-add new columns")
        self._auto_accept_action.setCheckable(True)
        self._auto_accept_action.setToolTip(
            "When checked, columns arriving from upstream are included automatically."
        )
        self._auto_accept_action.setChecked(
            bool(getattr(self, "auto_accept_new_columns", True))
        )
        self._auto_accept_action.toggled.connect(self._on_auto_accept_toggled)
        button.setMenu(menu)

    def _on_auto_accept_toggled(self, checked: bool) -> None:
        """Toggle whether newly arrived upstream columns are auto-included."""
        if self.history.is_restoring_history:
            return
        old = bool(getattr(self, "auto_accept_new_columns", True))
        if old == bool(checked):
            return
        old_mapping = [dict(item) for item in self.mapping_data]
        old_selected = [dict(item) for item in self.selected_columns]
        self.auto_accept_new_columns = bool(checked)
        if checked:
            # Immediately pick up pending arrivals, then recompute.
            self._sync_selected_with_schema()
            self.transform_data()
            self._refresh_open_dock()
        history_data = {
            "node": self.node,
            "old_join_type": self.join_type,
            "new_join_type": self.join_type,
            "old_mapping_data": old_mapping,
            "new_mapping_data": [dict(item) for item in self.mapping_data],
            "old_selected_columns": old_selected,
            "new_selected_columns": [dict(item) for item in self.selected_columns],
            "old_auto_accept": old,
            "new_auto_accept": bool(checked),
        }
        self.history.storeHistory(
            desc="Auto-Add Changed",
            data=history_data,
            setModified=True,
        )

    def _filter_output_columns(self, text: str) -> None:
        """Hide output rows that do not match the search text."""
        needle = text.strip().lower()
        for row in range(self.output_columns_list.count()):
            item = self.output_columns_list.item(row)
            widget = self.output_columns_list.itemWidget(item)
            if widget is None:
                continue
            label = widget.findChild(QCheckBox)
            name = label.text() if label is not None else ""
            item.setHidden(bool(needle) and needle not in name.lower())

    def _sanitize_mapping_data(self) -> None:
        if self.left_data is None or self.right_data is None:
            return

        valid_left = set(self._get_frame_schema(self.left_data))
        valid_right = set(self._get_frame_schema(self.right_data))
        sanitized_mapping = []

        for mapping in self.mapping_data:
            left_column = mapping.get("left_column")
            right_column = mapping.get("right_column")
            candidate = {
                "left_column": left_column,
                "right_column": right_column,
            }
            if (
                left_column in valid_left
                and right_column in valid_right
                and candidate not in sanitized_mapping
            ):
                sanitized_mapping.append(candidate)

        self.mapping_data = sanitized_mapping

    def _sanitize_selected_columns(self) -> None:
        if self.left_data is None or self.right_data is None:
            return

        valid_left = set(self._get_frame_schema(self.left_data))
        valid_right = set(self._get_frame_schema(self.right_data))
        sanitized_columns = []

        for column in self.selected_columns:
            name = column.get("name")
            source = column.get("source")
            candidate = {"name": name, "source": source}

            if (
                source == "L"
                and name in valid_left
                and candidate not in sanitized_columns
            ):
                sanitized_columns.append(candidate)
            elif (
                source == "R"
                and name in valid_right
                and candidate not in sanitized_columns
            ):
                sanitized_columns.append(candidate)

        self.selected_columns = sanitized_columns

    def _follow_upstream_renames(self) -> bool:
        """Remap stored configs that reference pre-rename upstream names.

        A rename otherwise looks like a drop + add: sanitize would delete
        the mapping row (breaking the join) and drop the output selection.
        When a stale name is a key in the upstream node's rename mapping
        and the new name is live, the stored reference is renamed instead.

        :return: True when anything was remapped.
        """
        if self.left_data is None or self.right_data is None:
            return False
        try:
            left_node = self.node.getInput(0)
            right_node = self.node.getInput(1)
        except (AttributeError, ValueError, RuntimeError, IndexError):
            return False
        left_map = upstream_rename_map(left_node)
        right_map = upstream_rename_map(right_node)
        if not left_map and not right_map:
            return False
        live_left = set(self._get_frame_schema(self.left_data))
        live_right = set(self._get_frame_schema(self.right_data))
        changed = False

        def _remap(side_map: dict, live: set, current: str) -> str:
            for old, new in side_map.items():
                if old == current and old not in live and new in live:
                    return new
            return current

        for mapping in self.mapping_data:
            new_left = _remap(left_map, live_left, mapping.get("left_column"))
            if new_left != mapping.get("left_column"):
                mapping["left_column"] = new_left
                changed = True
            new_right = _remap(right_map, live_right, mapping.get("right_column"))
            if new_right != mapping.get("right_column"):
                mapping["right_column"] = new_right
                changed = True
        for column in self.selected_columns:
            name = column.get("name")
            if column.get("source") == "L":
                new_name = _remap(left_map, live_left, name)
            elif column.get("source") == "R":
                new_name = _remap(right_map, live_right, name)
            else:
                continue
            if new_name != name:
                column["name"] = new_name
                changed = True
        return changed

    def _sync_selected_with_schema(self) -> bool:
        """Prune stale selections and auto-add new arrivals.

        Stale names are dropped (existing behaviour). Columns in the live
        schema that were never seen before are appended to
        ``selected_columns`` when auto-accept is on; explicitly unchecked
        columns (seen before, stored in ``known_columns``) stay excluded.
        ``known_columns`` is refreshed to the live schema.

        :return: True when the stored selection changed.
        """
        if self.left_data is None or self.right_data is None:
            return False
        self._sanitize_mapping_data()
        self._sanitize_selected_columns()
        auto_accept = bool(getattr(self, "auto_accept_new_columns", True))
        known = getattr(self, "known_columns", None)
        if not isinstance(known, list):
            known = []
            self.known_columns = known
        known_set = {
            (entry.get("name"), entry.get("source"))
            for entry in known
            if isinstance(entry, dict)
        }
        live = [
            {"name": name, "source": "L"}
            for name in sorted(self._get_frame_schema(self.left_data))
        ] + [
            {"name": name, "source": "R"}
            for name in sorted(self._get_frame_schema(self.right_data))
        ]
        live_set = {(entry["name"], entry["source"]) for entry in live}
        before = list(self.selected_columns)
        if auto_accept and self.selected_columns and known_set:
            # Only arrivals newer than the seen-set are added. When nothing
            # was seen yet (legacy file predating the tracker), the current
            # selection is taken as deliberate and recorded without adding.
            selected_set = {
                (column.get("name"), column.get("source"))
                for column in self.selected_columns
            }
            for entry in live:
                key = (entry["name"], entry["source"])
                if key not in known_set and key not in selected_set:
                    self.selected_columns.append(dict(entry))
                    selected_set.add(key)
        # Refresh the seen-set: prune dropped columns, then record what is
        # currently selected. When auto-accept is on the selection already
        # holds every live column, so this converges to the live schema;
        # when off, arrivals stay unknown (pending) while explicit unchecks
        # stay known (excluded).
        kept_known = [
            dict(entry)
            for entry in known
            if (entry.get("name"), entry.get("source")) in live_set
        ]
        kept_keys = {(entry["name"], entry["source"]) for entry in kept_known}
        for entry in live if auto_accept else self.selected_columns:
            if isinstance(entry, dict):
                key = (entry.get("name"), entry.get("source"))
            else:
                continue
            if key in live_set and key not in kept_keys:
                kept_known.append({"name": key[0], "source": key[1]})
                kept_keys.add(key)
        self.known_columns = kept_known
        return self.selected_columns != before

    def ensure_default_mapping(self) -> None:
        """Guarantee at least one mapping pair once both inputs are present.

        Defaults to the first column of each table. Data-only (no widgets):
        the config dock renders mapping_data rows via load_saved_data().
        """
        if self.mapping_data:
            return
        if self.left_data is None or self.right_data is None:
            return
        left_cols = list(self._get_frame_schema(self.left_data))
        right_cols = list(self._get_frame_schema(self.right_data))
        if not left_cols or not right_cols:
            return
        self.mapping_data.append(
            {"left_column": left_cols[0], "right_column": right_cols[0]}
        )
        global_logger.info(
            f"🔄 Join: Auto-mapped {left_cols[0]!r} to {right_cols[0]!r}"
        )

    def load_saved_data(self) -> None:
        self._sanitize_mapping_data()
        if self.mapping_data:
            for mapping in self.mapping_data:
                self.add_mapping_row(
                    left_col=mapping["left_column"], right_col=mapping["right_column"]
                )
        # check if col exist in output_column it it does check the checkbox or uncheck it

    def on_join_type_changed(self, join_type) -> None:
        if self.history.is_restoring_history:
            return

        old_join_type = self.join_type
        self.join_type = join_type

        history_data = {
            "node": self.node,
            "old_join_type": old_join_type,
            "new_join_type": join_type,
            "old_mapping_data": self.mapping_data.copy(),
            "new_mapping_data": self.mapping_data.copy(),
            "old_selected_columns": self.selected_columns.copy(),
            "new_selected_columns": self.selected_columns.copy(),
            "old_auto_accept": bool(getattr(self, "auto_accept_new_columns", True)),
            "new_auto_accept": bool(getattr(self, "auto_accept_new_columns", True)),
        }

        self.history.storeHistory(
            desc=f"Join type changed to {join_type}",
            data=history_data,
            setModified=True,
        )

    # def update_combo_boxes(self):

    def add_mapping_row(self, left_col=None, right_col=None) -> None:
        # Create a new row for mapping
        row_layout = QHBoxLayout()
        row_layout.setContentsMargins(0, 0, 0, 0)
        left_column_combo = NoWheelComboBox()
        right_column_combo = NoWheelComboBox()

        # Set size policies for mapping combos
        for combo in [left_column_combo, right_column_combo]:
            combo.setSizeAdjustPolicy(NoWheelComboBox.SizeAdjustPolicy.AdjustToContents)
            combo.setMinimumWidth(120)  # Set minimum width
            combo.setMinimumHeight(30)

        if hasattr(self, "left_data") and self.left_data is not None:
            self._populate_column_combo(left_column_combo, self.left_data, left_col)

        global_logger.debug(
            f"� Join: Adding mapping row - Right data available: {self.right_data is not None}"
        )

        if hasattr(self, "right_data") and self.right_data is not None:
            self._populate_column_combo(right_column_combo, self.right_data, right_col)

        row_layout.addWidget(left_column_combo)
        row_layout.addSpacing(10)
        row_layout.addWidget(right_column_combo)
        remove_button = IconButton.themed(
            "Remove mapping",
            rsm_icon=self.node.rsm.get("icon_remove"),
        )
        row_layout.addWidget(remove_button)

        temp_map = {
            "left_column": self._combo_current_column(left_column_combo),
            "right_column": self._combo_current_column(right_column_combo),
        }
        if temp_map not in self.mapping_data:
            self.mapping_data.append(temp_map)

        mapping_pair = {
            "left_combo": left_column_combo,
            "right_combo": right_column_combo,
            "layout": row_layout,
            "remove_btn": remove_button,
        }
        self.mapping_pairs.append(mapping_pair)

        # connect signal
        left_column_combo.currentTextChanged.connect(self.update_mapping_data)
        right_column_combo.currentTextChanged.connect(self.update_mapping_data)
        remove_button.clicked.connect(lambda: self.remove_mapping_row(mapping_pair))

        # Add to container
        self.mapping_container.addLayout(row_layout)

    def delete_layout(self, layout) -> None:
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
                else:
                    self.delete_layout(item.layout())
            layout.deleteLater()

    def remove_mapping_row(self, mapping_pair) -> None:
        if len(self.mapping_pairs) > 1:  # Keep at least one mapping row
            if self.history.is_restoring_history:
                return

            # Store old state before removal
            old_mapping_data = self.mapping_data.copy()

            # Find and remove corresponding mapping data
            idx = self.mapping_pairs.index(mapping_pair)
            if idx < len(self.mapping_data):
                self.mapping_data.pop(idx)

            # Remove from UI storage
            self.mapping_pairs.remove(mapping_pair)
            # Remove from layout
            self.delete_layout(mapping_pair["layout"])

            # Store history
            history_data = {
                "node": self.node,
                "old_join_type": self.join_type,
                "new_join_type": self.join_type,
                "old_mapping_data": old_mapping_data,
                "new_mapping_data": self.mapping_data.copy(),
                "old_selected_columns": self.selected_columns.copy(),
                "new_selected_columns": self.selected_columns.copy(),
                "old_auto_accept": bool(getattr(self, "auto_accept_new_columns", True)),
                "new_auto_accept": bool(getattr(self, "auto_accept_new_columns", True)),
            }

            self.history.storeHistory(
                desc="Removed mapping row", data=history_data, setModified=True
            )

    def update_mapping_data(self) -> None:
        """Update mapping data when UI changes"""

        if self.history.is_restoring_history:
            return

        old_mapping_data = self.mapping_data.copy()

        new_mapping_data = []
        for pair in self.mapping_pairs:
            candidate = {
                "left_column": self._combo_current_column(pair["left_combo"]),
                "right_column": self._combo_current_column(pair["right_combo"]),
            }
            if candidate not in new_mapping_data:
                new_mapping_data.append(candidate)

        self.mapping_data = new_mapping_data
        self._sanitize_mapping_data()

        if old_mapping_data == self.mapping_data:
            return

        history_data = {
            "node": self.node,
            "old_join_type": self.join_type,
            "new_join_type": self.join_type,
            "old_mapping_data": old_mapping_data,
            "new_mapping_data": self.mapping_data.copy(),
            "old_selected_columns": self.selected_columns.copy(),
            "new_selected_columns": self.selected_columns.copy(),
            "old_auto_accept": bool(getattr(self, "auto_accept_new_columns", True)),
            "new_auto_accept": bool(getattr(self, "auto_accept_new_columns", True)),
        }

        self.history.storeHistory(
            desc="Join mapping updated", data=history_data, setModified=True
        )
        # Live-by-default: recompute once edits settle.
        if not self._applying:
            self._apply_timer.start()

    def update_output_columns(self) -> None:
        self.output_columns_list.clear()
        self.output_column_checkboxes = []
        if self.left_data is not None and self.right_data is not None:
            self._sanitize_selected_columns()
            left_schema = self._get_frame_schema(self.left_data)
            right_schema = self._get_frame_schema(self.right_data)
            if not self.selected_columns:
                # Pre-select all columns by default
                for col in sorted(left_schema):
                    self.selected_columns.append({"name": col, "source": "L"})
                for col in sorted(right_schema):
                    self.selected_columns.append({"name": col, "source": "R"})

            # Create widget for left columns
            left_label = QLabel("Left table columns")
            left_label.setObjectName("JoinSourceHeaderLeft")
            left_item = QListWidgetItem()
            # Make header non-selectable
            left_item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.output_columns_list.addItem(left_item)
            self.output_columns_list.setItemWidget(left_item, left_label)

            # Add left columns with L prefix and checkboxes
            for col in sorted(left_schema):
                self._add_output_column_item(
                    col,
                    "L",
                    "JoinSourceLeft",
                    self.selected_columns,
                    str(left_schema[col]),
                )

            # Create widget for right columns
            right_label = QLabel("Right table columns")
            right_label.setObjectName("JoinSourceHeaderRight")
            right_item = QListWidgetItem()
            # Make header non-selectable
            right_item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.output_columns_list.addItem(right_item)
            self.output_columns_list.setItemWidget(right_item, right_label)

            # Add right columns with R prefix and checkboxes
            for col in sorted(right_schema):
                self._add_output_column_item(
                    col,
                    "R",
                    "JoinSourceRight",
                    self.selected_columns,
                    str(right_schema[col]),
                )

    def _add_output_column_item(
        self,
        col,
        prefix: str,
        source_object_name: str,
        existing_selections,
        dtype_label: str,
    ) -> None:
        """Helper method to add a column item to the output columns list"""
        item = QListWidgetItem()
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 2, 5, 2)

        # Source indicator (styled via QSS objectName, no inline QSS)
        source_label = QLabel(prefix)
        source_label.setObjectName(source_object_name)
        source_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        source_label.setFixedWidth(20)

        # Checkbox
        checkbox = QCheckBox(col)
        # Set checked state based on existing selections
        is_checked = (
            any(x["name"] == col and x["source"] == prefix for x in existing_selections)
            if existing_selections
            else True
        )
        checkbox.setChecked(is_checked)

        # Store source information in checkbox property
        checkbox.setProperty("source", prefix)
        checkbox.stateChanged.connect(
            lambda: self._on_output_checkbox_changed(checkbox)
        )
        self.output_column_checkboxes.append(
            {"name": col, "source": prefix, "checkbox": checkbox}
        )

        dtype_value_label = QLabel(f"[{dtype_label}]")
        dtype_value_label.setObjectName("JoinDtypeLabel")

        # Add to selected_columns if checked by default
        # if is_checked:
        #     col_data = {'name': col, 'source': prefix}
        #     self.selected_columns.append(col_data)

        layout.addWidget(source_label)
        layout.addWidget(checkbox)
        layout.addWidget(dtype_value_label)
        layout.addStretch()
        widget.setLayout(layout)

        item.setSizeHint(widget.sizeHint())
        self.output_columns_list.addItem(item)
        self.output_columns_list.setItemWidget(item, widget)

    def _get_available_output_columns(self, source: str) -> list[str]:
        if source == "L" and self.left_data is not None:
            return sorted(self._get_frame_schema(self.left_data))
        if source == "R" and self.right_data is not None:
            return sorted(self._get_frame_schema(self.right_data))
        return []

    def _sync_output_column_checkboxes(self, source: str, checked: bool) -> None:
        for entry in self.output_column_checkboxes:
            if entry["source"] != source:
                continue
            checkbox = entry["checkbox"]
            checkbox.blockSignals(True)
            checkbox.setChecked(checked)
            checkbox.blockSignals(False)

    def _set_output_columns_checked(self, source: str, checked: bool) -> None:
        if self.history.is_restoring_history:
            return

        old_selected_columns = self.selected_columns.copy()

        self.selected_columns = [
            column for column in self.selected_columns if column.get("source") != source
        ]

        if checked:
            for column_name in self._get_available_output_columns(source):
                candidate = {"name": column_name, "source": source}
                if candidate not in self.selected_columns:
                    self.selected_columns.append(candidate)

        self._sync_output_column_checkboxes(source, checked)

        if old_selected_columns == self.selected_columns:
            return

        source_label = "left" if source == "L" else "right"
        history_data = {
            "node": self.node,
            "old_join_type": self.join_type,
            "new_join_type": self.join_type,
            "old_mapping_data": self.mapping_data.copy(),
            "new_mapping_data": self.mapping_data.copy(),
            "old_selected_columns": old_selected_columns,
            "new_selected_columns": self.selected_columns.copy(),
            "old_auto_accept": bool(getattr(self, "auto_accept_new_columns", True)),
            "new_auto_accept": bool(getattr(self, "auto_accept_new_columns", True)),
        }

        self.history.storeHistory(
            desc=(
                f"{'Selected' if checked else 'Deselected'} all {source_label} output columns"
            ),
            data=history_data,
            setModified=True,
        )

    def _on_output_checkbox_changed(self, checkbox) -> None:
        """Handle checkbox state changes"""
        if self.history.is_restoring_history:
            return

        col_name = checkbox.text()
        source = checkbox.property("source")
        col_data = {"name": col_name, "source": source}

        old_selected_columns = self.selected_columns.copy()

        if checkbox.isChecked():
            if col_data not in self.selected_columns:
                self.selected_columns.append(col_data)
        else:
            self.selected_columns = [
                col
                for col in self.selected_columns
                if not (col["name"] == col_name and col["source"] == source)
            ]

        history_data = {
            "node": self.node,
            "old_join_type": self.join_type,
            "new_join_type": self.join_type,
            "old_mapping_data": self.mapping_data.copy(),
            "new_mapping_data": self.mapping_data.copy(),
            "old_selected_columns": old_selected_columns,
            "new_selected_columns": self.selected_columns.copy(),
            "old_auto_accept": bool(getattr(self, "auto_accept_new_columns", True)),
            "new_auto_accept": bool(getattr(self, "auto_accept_new_columns", True)),
        }

        self.history.storeHistory(
            desc=f"Column '{col_name}' selection changed",
            data=history_data,
            setModified=True,
        )
        # Live-by-default: recompute once edits settle.
        if not self._applying:
            self._apply_timer.start()

    def _rebuild_dock_widgets(self) -> None:
        """Rebuild mapping rows + output list from the stored model.

        Signal-safe by construction: combos and checkboxes are set before
        their change signals are connected, so rebuilding never records
        history or schedules an apply by itself.
        """
        for pair in self.mapping_pairs[:]:
            self.delete_layout(pair["layout"])
        self.mapping_pairs.clear()
        for mapping in self.mapping_data:
            self.add_mapping_row(
                left_col=mapping["left_column"], right_col=mapping["right_column"]
            )
        self.update_output_columns()
        action = getattr(self, "_auto_accept_action", None)
        if action is not None:
            try:
                checked = bool(getattr(self, "auto_accept_new_columns", True))
                if action.isChecked() != checked:
                    action.blockSignals(True)
                    action.setChecked(checked)
                    action.blockSignals(False)
            except RuntimeError:
                pass

    def _refresh_open_dock(self) -> None:
        """Repaint an open dock after an upstream-driven config migration."""
        if not hasattr(self, "mapping_container") or not hasattr(
            self, "output_columns_list"
        ):
            return
        try:
            self._rebuild_dock_widgets()
        except RuntimeError:
            pass

    def _apply_debounced(self) -> None:
        """Debounced live apply, skipped while restoring history or mid-apply."""
        if self._applying:
            return
        if self.history.is_restoring_history:
            return
        self._applying = True
        try:
            self.transform_data()
        except Exception as e:
            global_logger.error(f"❌ Join: live apply failed: {e}")
        finally:
            self._applying = False

    def history_stamp_callback(self, history_data, is_undo: bool) -> None:
        """Callback for undo/redo operations.

        The scene snapshot has already restored the model before this
        runs, so the payload's old/new diff must NOT be re-applied here:
        it describes the edit that produced the applied stamp, and picking
        its "old" side would step back twice. The only jobs left are
        re-projecting the widgets and recomputing the outputs from the
        restored model.
        """
        node_data = (
            history_data.get("node", None) if isinstance(history_data, dict) else None
        )
        if node_data is not None and node_data != self.node:
            return

        with self.history.restoring(is_undo=is_undo):
            # Legacy stamps predate the auto-accept toggle.
            if not isinstance(getattr(self, "auto_accept_new_columns", True), bool):
                self.auto_accept_new_columns = True
            if not isinstance(getattr(self, "known_columns", None), list):
                self.known_columns = []

            # Update UI to reflect changes
            try:
                self._rebuild_dock_widgets()
            except RuntimeError:
                pass
            try:
                self.transform_data()
            except (RuntimeError, AttributeError, ValueError) as exc:
                global_logger.error(f"❌ Join: recompute after restore failed: {exc}")

    def transform_data(self):
        """
        Transform input data based on join settings using optimized Polars LazyFrame operations.

        PERFORMANCE OPTIMIZATION: Uses a single full outer join with indicators instead of
        3 separate join operations (1 full + 2 anti-joins), resulting in ~3x better performance
        and significantly reduced memory usage.
        """
        if self.left_data is None or self.right_data is None:
            global_logger.warning("🔄 Join: No input data available for join operation")
            return None

        global_logger.debug(
            f"� Join: Processing join with mapping data: {self.mapping_data}"
        )

        self._sync_selected_with_schema()

        if not self.mapping_data:
            global_logger.warning(
                "🔄 Join: No mapping data provided for join operation"
            )
            return None

        left_cols = [m["left_column"] for m in self.mapping_data]
        right_cols = [m["right_column"] for m in self.mapping_data]

        try:
            global_logger.info(
                f"🔄 Join: Performing join on columns - Left: {left_cols}, Right: {right_cols}"
            )

            left_data = (
                self.left_data.lazy()
                if isinstance(self.left_data, pl.DataFrame)
                else self.left_data
            )
            right_data = (
                self.right_data.lazy()
                if isinstance(self.right_data, pl.DataFrame)
                else self.right_data
            )

            # Prepare column suffixes to handle conflicts
            left_suffix = "_left"
            right_suffix = "_right"

            # Get column names from LazyFrames for conflict detection
            left_columns = list(frame_schema(left_data))
            right_columns = list(frame_schema(right_data))

            # Find conflicting columns (not in join keys)
            conflicting_cols = []
            for col in right_columns:
                if col in left_columns and col not in right_cols:
                    conflicting_cols.append(col)

            # Rename conflicting columns in right dataframe before join
            right_data_renamed = right_data
            if conflicting_cols:
                rename_map = {col: f"{col}{right_suffix}" for col in conflicting_cols}
                right_data_renamed = right_data.rename(rename_map)
                global_logger.debug(
                    f"🔄 Join: Renamed conflicting columns in right data: {rename_map}"
                )

            # Tag rows pre-join: tags ride through under any key names
            # (coalescing can drop a right key column, tags never drop),
            # so splitting into join/left-only/right-only stays correct
            # even when the key columns differ by name.
            left_tag, right_tag = "__left_present", "__right_present"
            left_tagged = left_data.with_columns(pl.lit(1).alias(left_tag))
            right_tagged = right_data_renamed.with_columns(pl.lit(1).alias(right_tag))

            # Perform the join operation using Polars
            # Using outer join to capture all combinations like the original pandas code
            result = left_tagged.join(
                right_tagged,
                left_on=left_cols,
                right_on=right_cols,
                how="full",  # Full outer join equivalent to pandas 'outer'
                suffix=left_suffix,  # Suffix for left columns in conflict
                coalesce=True,  # Coalesce join columns to avoid duplicates
            )

            global_logger.debug(f"🔄 Join: Join operation completed successfully")

            # Filter columns based on selected_columns
            if self.selected_columns:
                selected_cols = []
                for col in self.selected_columns:
                    col_name = col["name"]
                    if col["source"] == "L":
                        # For left columns, use original name if it's a join key or add suffix if renamed
                        if col_name in left_cols:
                            selected_cols.append(col_name)
                        elif f"{col_name}{left_suffix}" in result.columns:
                            selected_cols.append(f"{col_name}{left_suffix}")
                        else:
                            selected_cols.append(col_name)
                    else:  # 'R' - Right source
                        # For right columns, use original name if it's a join key or suffixed name
                        if col_name in right_cols:
                            selected_cols.append(col_name)
                        elif f"{col_name}{right_suffix}" in result.columns:
                            selected_cols.append(f"{col_name}{right_suffix}")
                        else:
                            selected_cols.append(col_name)

                # Coalescing drops a right key column when key names differ;
                # its left counterpart holds the same values for matched rows.
                result_cols = set(result.columns)
                fixed_cols = []
                for column in selected_cols:
                    if column not in result_cols and column in right_cols:
                        counterpart = left_cols[right_cols.index(column)]
                        column = counterpart if counterpart in result_cols else column
                    fixed_cols.append(column)
                selected_cols = fixed_cols

                selected_cols = [
                    column
                    for index, column in enumerate(selected_cols)
                    if column in result.columns and column not in selected_cols[:index]
                ]
            # (self.data is assigned below after the single collect.)

            # OPTIMIZED: Extract all join types from single result (much faster!)
            # Presence tags (never coalesced away, unlike right key columns)
            # identify record sources under any key names.
            collected = result.collect()
            both_condition = (
                pl.col(left_tag).is_not_null() & pl.col(right_tag).is_not_null()
            )
            left_only_condition = pl.col(right_tag).is_null()
            right_only_condition = pl.col(left_tag).is_null()

            # Extract the three outputs efficiently from single result
            # Main join data (both exist)
            if self.selected_columns:
                self.data = collected.filter(both_condition).select(selected_cols)
            else:
                non_indicator_cols = [
                    col for col in result.columns if not col.startswith("__")
                ]
                self.data = collected.filter(both_condition).select(non_indicator_cols)

            # Left-only data
            left_final_cols = [
                col
                for col in result.columns
                if col in left_columns
                or (
                    col.endswith(left_suffix)
                    and col.replace(left_suffix, "") in left_columns
                )
            ]
            left_final_cols = [
                col for col in left_final_cols if not col.startswith("__")
            ]
            self.l_data = collected.filter(left_only_condition).select(left_final_cols)

            # Right-only data
            right_final_cols = [
                col
                for col in result.columns
                if col in right_columns
                or (
                    col.endswith(right_suffix)
                    and col.replace(right_suffix, "") in right_columns
                )
            ]
            right_final_cols = [
                col for col in right_final_cols if not col.startswith("__")
            ]
            # Reattach coalesced-away right keys via their left counterparts
            # (full join fills them with the right key values).
            result_cols = set(result.columns)
            for l_key, r_key in zip(left_cols, right_cols):
                if (
                    r_key not in result_cols
                    and l_key in result_cols
                    and l_key not in right_final_cols
                ):
                    right_final_cols.append(l_key)
            self.r_data = collected.filter(right_only_condition).select(
                right_final_cols
            )

            global_logger.info(
                "� Join: OPTIMIZED join transformation completed - used single join instead of 3 separate operations!"
            )
            global_logger.debug(
                f"🔄 Join: Result statistics - Total records processed: {collected.height}"
            )
            return result

        except Exception as e:
            error_msg = f"Error during join transformation: {str(e)}"
            global_logger.error(f"❌ Join: {error_msg}")
            return None

    def get_code(self):
        """Generate Polars LazyFrame join code"""
        self._sync_selected_with_schema()

        if not self.mapping_data or self.left_data is None or self.right_data is None:
            global_logger.warning(
                "Join Node: No mapping data or input data is missing."
            )
            # Fallback: always define all 3 outputs so downstream code
            # never NameErrors. Prefer passthrough; else empty frames.
            fallback = ["import polars as pl"]
            if self.left_variable:
                fallback.append(f"{self.l_variable_name} = {self.left_variable}")
                fallback.append(f"{self.variable_name} = {self.left_variable}")
            else:
                fallback.append(f"{self.l_variable_name} = pl.DataFrame()")
                fallback.append(f"{self.variable_name} = pl.DataFrame()")
            if self.right_variable:
                fallback.append(f"{self.r_variable_name} = {self.right_variable}")
            else:
                fallback.append(f"{self.r_variable_name} = pl.DataFrame()")
            return "\n".join(fallback) + "\n"

        code_lines = []
        left_cols = [m["left_column"] for m in self.mapping_data]
        right_cols = [m["right_column"] for m in self.mapping_data]

        # Get column names for conflict detection
        left_columns = list(frame_schema(self.left_data))
        right_columns = list(frame_schema(self.right_data))

        # Find conflicting columns (not in join keys)
        conflicting_cols = [
            col
            for col in right_columns
            if col in left_columns and col not in right_cols
        ]

        code_lines.append("# Polars LazyFrame Join Operation\nimport polars as pl\n")
        code_lines.extend(
            [
                "def _ensure_lazyframe(data):",
                "    if isinstance(data, pl.DataFrame):",
                "        return data.lazy()",
                "    if isinstance(data, pl.LazyFrame):",
                "        return data",
                "    raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(data)}')",
                "",
                f"_left_input = _ensure_lazyframe({self.left_variable})",
                f"_right_input = _ensure_lazyframe({self.right_variable})",
            ]
        )

        # Add column renaming if there are conflicts
        if conflicting_cols:
            rename_map = {col: f"{col}_right" for col in conflicting_cols}
            code_lines.append(
                f"# Rename conflicting columns in right dataframe\n"
                f"_right_renamed = _right_input.rename({rename_map})\n"
            )
            right_var = "_right_renamed"
        else:
            right_var = "_right_input"

        # Main join operation (presence tags ride through under any key names)
        code_lines.append(
            f"\n# Perform full outer join with coalesce (automatic conflict resolution)\n"
            f"_left_tagged = _left_input.with_columns(pl.lit(1).alias('__left_present'))\n"
            f"_right_tagged = {right_var}.with_columns(pl.lit(1).alias('__right_present'))\n"
            f"_join_result = _left_tagged.join(\n"
            f"    _right_tagged,\n"
            f"    left_on={left_cols},\n"
            f"    right_on={right_cols},\n"
            f"    how='full',\n"
            f"    coalesce=True\n"
            f")"
        )

        # Generate optimized code for left-only and right-only data extraction
        # (a right key coalesced away is represented by its left counterpart)
        left_cols_for_select = [f"{col}" for col in left_columns]
        right_cols_for_select = []
        for col in right_columns:
            if col in conflicting_cols:
                right_cols_for_select.append(f"{col}_right")
            elif col in right_cols and col not in left_columns:
                right_cols_for_select.append(left_cols[right_cols.index(col)])
            else:
                right_cols_for_select.append(f"{col}")

        # Split via presence tags (coalescing can drop a right key column,
        # tags never drop) — correct even when key names differ.
        both_cond = "(pl.col('__left_present').is_not_null() & pl.col('__right_present').is_not_null())"
        left_only_cond = "pl.col('__right_present').is_null()"
        right_only_cond = "pl.col('__left_present').is_null()"

        # THEN: Filter columns based on selected_columns
        if self.selected_columns:
            selected_cols = []
            for col in self.selected_columns:
                col_name = col["name"]
                source = col["source"]

                if (
                    source == "R"
                    and col_name in right_cols
                    and col_name not in left_columns
                    and col_name not in conflicting_cols
                ):
                    # Coalesced-away right key: left counterpart holds values.
                    resolved_name = left_cols[right_cols.index(col_name)]
                elif (
                    source == "R"
                    and col_name not in right_cols
                    and col_name in conflicting_cols
                ):
                    resolved_name = f"{col_name}_right"
                elif source == "R" and col_name in conflicting_cols:
                    resolved_name = f"{col_name}_right"
                else:
                    resolved_name = col_name

                selected_cols.append(f"'{resolved_name}'")

            # Remove duplicates while preserving order
            selected_cols = list(dict.fromkeys(selected_cols))
            cols_str = ",\n    ".join(selected_cols)

            code_lines.append(
                f"\n# Main join result with selected columns (matched records only)"
                f"\n{self.variable_name} = _join_result.filter("
                f"\n    {both_cond}"
                f"\n).select(["
                f"\n    {cols_str}"
                f"\n])"
            )
        else:
            code_lines.append(
                f"\n# Main join result (all columns, matched records only)"
                f"\n{self.variable_name} = _join_result.filter("
                f"\n    {both_cond}"
                f"\n).select([col for col in _join_result.columns if not col.startswith('__')])"
            )

        # Add left-only and right-only extraction code
        code_lines.extend(
            [
                f"\n# Extract left-only data efficiently",
                f"_left_cols = {left_cols_for_select}",
                f"{self.l_variable_name} = _join_result.filter(",
                f"    {left_only_cond}",
                f").select(_left_cols)",
                f"",
                f"# Extract right-only data efficiently",
                f"_right_cols = {right_cols_for_select}",
                f"{self.r_variable_name} = _join_result.filter(",
                f"    {right_only_cond}",
                f").select(_right_cols)",
            ]
        )

        # Clean up temporary variables
        cleanup_vars = [
            "_left_input",
            "_right_input",
            "_left_tagged",
            "_right_tagged",
            "_join_result",
            "_left_cols",
            "_right_cols",
        ]
        if conflicting_cols:
            cleanup_vars.append("_right_renamed")

        code_lines.append(
            f"\n# Clean up temporary variables\ndel {', '.join(cleanup_vars)}"
        )

        return "\n".join(code_lines) + "\n"

    def serialize(self):
        res = super().serialize()
        res["join_type"] = self.join_type
        res["mapping_data"] = self.mapping_data
        # Serialize output columns
        res["selected_columns"] = self.selected_columns
        res["auto_accept_new_columns"] = bool(
            getattr(self, "auto_accept_new_columns", True)
        )
        res["known_columns"] = getattr(self, "known_columns", [])
        return res

    def deserialize(self, data, hashmap={}):
        res = super().deserialize(data, hashmap)
        try:
            # Store join type
            self.join_type = data.get("join_type", "inner")

            # Store mapping data
            self.mapping_data = data.get("mapping_data", [])

            # Store output columns
            self.selected_columns = data.get("selected_columns", [])

            # Auto-accept toggle + seen-columns cache (legacy files default on).
            self.auto_accept_new_columns = data.get("auto_accept_new_columns", True)
            self.known_columns = data.get("known_columns", [])

            return True and res
        except Exception as e:
            dumpException(e)
        return res


@register_node(JoinNodes.JOIN, NodeTypes.JOIN)
class TriggerNode_Join(TriggerNode):
    icon = "node_join"
    node_code = JoinNodes.JOIN
    node_type = NodeTypes.JOIN
    node_title = "Join"
    content_label_objname = "trigger_node_join"
    style = {}

    def __init__(self, scene) -> None:
        super().__init__(
            scene,
            inputs=[1, 1],
            outputs=[3, 3, 3],
            input_text=["L", "R"],
            output_text=["L", "J", "R"],
        )
        # self.eval()

    def initInnerClasses(self) -> None:
        self.content: JoinContent = JoinContent(self)
        self.grNode: TriggerGraphicsNode = TriggerGraphicsNode(self)
        self.content.evaluate.connect(self.onInputChanged)
        self.param: list = []

    def processInputs(self, input_values):

        # Only one input for simplicity
        this_left_skt = 0
        this_right_skt = 1

        # Get socket index of incoming data
        input_node = self.getInput(this_left_skt)
        left_skt = self.getSocketValue(input_node.outputs, self)  # type: ignore
        input_node = self.getInput(this_right_skt)
        right_skt = self.getSocketValue(input_node.outputs, self)  # type: ignore

        left_input = input_values[this_left_skt][left_skt]
        right_input = input_values[this_right_skt][right_skt]

        if left_input and right_input:
            self.markDirty(False)
            self.markInvalid(False)

            # Process left input
            self.content.left_data = left_input.get("data")
            self.content.left_variable = left_input.get("variable_name")

            # Process right input
            self.content.right_data = right_input.get("data")
            self.content.right_variable = right_input.get("variable_name")

            # Both inputs present: follow upstream renames first so stored
            # configs keep working instead of going stale, drop what is
            # truly gone, and ensure at least one mapping pair for fresh
            # nodes (first column of each table) so the node works out of
            # the box.
            followed = False
            try:
                followed = self.content._follow_upstream_renames()
            except (AttributeError, ValueError, RuntimeError) as follow_error:
                global_logger.warning(
                    f"🔄 Join: Could not follow upstream renames: {follow_error}"
                )
            self.content._sanitize_mapping_data()
            if (
                not self.content.mapping_data
                and not getattr(self.content, "known_columns", [])
                and not self.content.selected_columns
            ):
                self.content.ensure_default_mapping()

            global_logger.info(
                f"🔄 Join: Processing inputs - Left: {self.content.left_variable}, Right: {self.content.right_variable}"
            )

            selected_before = list(self.content.selected_columns)
            mapping_before = list(self.content.mapping_data)
            transform_result = self.content.transform_data()
            if (
                followed
                or self.content.selected_columns != selected_before
                or self.content.mapping_data != mapping_before
            ):
                self.content._refresh_open_dock()

            if transform_result is None:
                self.markDirty(True)
                self.markInvalid(True)
                self.grNode.setToolTip("No valid join mapping configured")
                return None

            self.param = [
                # Output 0 - Left data pass-through
                {
                    "data": self.content.l_data,
                    "variable_name": self.content.l_variable_name,
                },
                # Output 1 - Joined data
                {
                    "data": self.content.data,
                    "variable_name": self.content.variable_name,
                },
                # Output 2 - Right data pass-through
                {
                    "data": self.content.r_data,
                    "variable_name": self.content.r_variable_name,
                },
            ]
            # NOTE: no evalChildren() here. The base evalImplementation
            # evaluates children after this returns and the new value is
            # committed; evaluating them here would hand them the previous
            # output.
            # Return three outputs in a list
            return self.param

        # variable = self.content.variable_name
        else:
            self.markDirty(True)
            self.markInvalid(True)
            self.grNode.setToolTip("Both inputs must be connected")
            return None

    def get_code(self):
        return self.content.get_code()
