from typing import Optional, List, Dict, Any, TYPE_CHECKING
import polars as pl
from qtpy.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
)
from qtpy.QtGui import QPixmap
from qtpy.QtCore import Signal, Slot
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
)
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget
from trigger_designer.qt.widgets.common import (
    ColumnChecklist,
    ConfigSection,
    EmptyStateLabel,
    TextButton,
)
from nodeeditor.utils_no_qt import dumpException
from nodeeditor.node_scene_history import SceneHistory
from nodeeditor.node_scene import Scene


class UniqueContent(QDMNodeIconContentWidget, TriggerChangeHandler):
    """
    Content widget for unique node that removes duplicate rows based on selected columns.

    This class provides a user interface for selecting columns to use for uniqueness
    determination and removes duplicate rows while preserving the first occurrence.
    Uses Polars for efficient data processing with LazyFrame operations.

    Attributes:
        evaluate: Qt signal emitted when unique configuration changes
        selected_columns: List of column names selected for uniqueness check
        incoming_variable: Name of the incoming data variable
        incom_data: The incoming polars LazyFrame
        variable_name: Variable name for the output
    """

    evaluate = Signal()  # Emit when evaluate button is clicked

    def __init__(self, node: "TriggerNode", parent: Optional[QWidget] = None) -> None:
        super().__init__(node, parent)
        TriggerChangeHandler.__init__(self, self.node.scene, self.node)

        # Configuration variables
        self.selected_columns: list[str] = []
        self.history: SceneHistory = self.node.scene.history

        # Incoming data variables
        self.incoming_variable: str = ""
        self.incom_data: pl.DataFrame | pl.LazyFrame | None = None

        # Output variables
        self.data: pl.DataFrame | pl.LazyFrame | None = None
        self.duplicate_data: pl.DataFrame | pl.LazyFrame | None = None
        self.variable_name: str = f"var_unique_{self.id}"
        self.duplicate_variable_name: str = f"var_duplicate_{self.id}"

        # UI components
        self.search_bar: QLineEdit | None = None
        self.column_list: ColumnChecklist | None = None
        self.all_columns: list[str] = []  # Store all available columns for filtering
        self._visible_columns: list[str] = []  # Columns currently shown (post-filter)

    @property
    def node(self) -> "TriggerNode":
        return self._node

    @node.setter
    def node(self, value: "TriggerNode") -> None:
        self._node = value

    def initUI(self, icon_: Optional[QPixmap] = None) -> None:
        """Initialize the user interface for the unique content widget."""
        icon: QPixmap = self.node.rsm.get(f"{self.node.icon}")
        super().initUI(icon)

    def create_layout(self, dock_layout: QVBoxLayout) -> None:
        """
        Create the layout for the unique content widget.

        Sets up UI components for selecting columns to use for uniqueness determination.
        Shows appropriate message if no data is available.

        Args:
            dock_layout: The layout to add components to
        """
        if self.incom_data is not None:
            # Main configuration group (design system defaults: spacing 2)
            config_group = ConfigSection(
                "Unique Configuration",
                "Select columns to determine uniqueness:",
            )

            # Toolbar: search + icon-only select/deselect (design system §4)
            toolbar_layout = QHBoxLayout()
            toolbar_layout.setContentsMargins(0, 0, 0, 0)
            self.search_bar = QLineEdit()
            self.search_bar.setPlaceholderText("Type to filter columns...")
            self.search_bar.setClearButtonEnabled(True)
            self.search_bar.setMinimumHeight(30)
            self.search_bar.textChanged.connect(self._filter_columns)
            toolbar_layout.addWidget(self.search_bar)

            select_all_btn = TextButton("All", "Select all visible columns")
            deselect_all_btn = TextButton("None", "Deselect all visible columns")
            select_all_btn.clicked.connect(self._select_all_columns)
            deselect_all_btn.clicked.connect(self._deselect_all_columns)
            toolbar_layout.addWidget(select_all_btn)
            toolbar_layout.addWidget(deselect_all_btn)
            config_group.addLayout(toolbar_layout)

            # Column selection list - takes all remaining vertical space
            self.column_list = ColumnChecklist(max_height=220)
            self.column_list.changed.connect(self._on_checklist_changed)

            self._update_column_list()
            config_group.layout().addWidget(
                self.column_list, 1
            )  # Give it stretch factor 1 to take available space

            dock_layout.addWidget(config_group, 1)  # Take all available vertical space

            self.recursively_find_widgets(dock_layout)
        else:
            dock_layout.addWidget(EmptyStateLabel())

    def _live_selected_columns(self) -> List[str]:
        """selected_columns filtered to columns present in the current schema.

        A configured column can disappear upstream (e.g. deselected in an
        earlier Select) while staying in selected_columns, so dedup resumes
        on it automatically if it reappears -- mirrors Select's missing-
        column retention instead of crashing on a stale subset.
        """
        schema = frame_schema(self.incom_data)
        if not schema:
            return self.selected_columns
        return [col for col in self.selected_columns if col in schema]

    def process_data(self) -> None:
        """Build unique and duplicate outputs for the current selection."""
        if self.incom_data is None:
            self.data = None
            self.duplicate_data = None
            return

        live_columns = self._live_selected_columns()
        if not live_columns:
            self.data = self.incom_data
            self.duplicate_data = self.incom_data.head(0)
            return

        duplicate_expr = pl.struct(live_columns).is_duplicated()
        self.data = self.incom_data.unique(
            subset=live_columns,
            maintain_order=True,
        )
        self.duplicate_data = self.incom_data.filter(duplicate_expr)

    def _update_column_list(self) -> None:
        """
        Update the column list when input data changes.

        Populates the checklist with one checkbox per available column.
        Preserves previously selected columns when data is refreshed.
        """
        if not hasattr(self, "column_list") or self.column_list is None:
            return

        if self.incom_data is not None:
            try:
                # Get column names and store them
                self.all_columns = list(frame_schema(self.incom_data))
                self._populate_column_list(self.all_columns)
            except Exception:
                # Handle case where column names can't be accessed
                self.all_columns = []

    def _populate_column_list(self, columns: List[str]) -> None:
        """
        Populate the checklist with the given columns.

        Args:
            columns: List of column names to display
        """
        if not hasattr(self, "column_list") or self.column_list is None:
            return

        # Remember what is on screen: filtering hides columns, and hidden
        # selections must survive a checkbox toggle on the visible subset.
        self._visible_columns = list(columns)
        checked = [col for col in columns if col in self.selected_columns]
        self.column_list.setColumns(columns, checked)

    @Slot(str)
    def _filter_columns(self, search_text: str) -> None:
        """
        Filter the column list based on search text.

        Args:
            search_text: Text to filter columns by
        """
        if not hasattr(self, "column_list") or self.column_list is None:
            return

        search_text = search_text.lower()
        if search_text:
            filtered_columns = [
                col for col in self.all_columns if search_text in col.lower()
            ]
        else:
            filtered_columns = self.all_columns.copy()

        self._populate_column_list(filtered_columns)

    def _select_all_columns(self) -> None:
        """Select all currently visible columns."""
        if not hasattr(self, "column_list") or self.column_list is None:
            return

        # Get currently visible columns
        visible_columns = list(getattr(self, "_visible_columns", [])) or list(
            self.column_list.checkboxes.keys()
        )

        if visible_columns:
            old_selected = self.selected_columns.copy()

            # Add all visible columns to selection
            for column in visible_columns:
                if column not in self.selected_columns:
                    self.selected_columns.append(column)

            # Update UI
            self.column_list.setChecked(self.selected_columns)

            # Store history if there was a change
            if old_selected != self.selected_columns:
                self._store_selection_history(old_selected, "Select All Visible")
                self.process_data()
                self.evaluate.emit()

    def _deselect_all_columns(self) -> None:
        """Deselect all currently visible columns."""
        if not hasattr(self, "column_list") or self.column_list is None:
            return

        # Get currently visible columns
        visible_columns = list(getattr(self, "_visible_columns", [])) or list(
            self.column_list.checkboxes.keys()
        )

        if visible_columns:
            old_selected = self.selected_columns.copy()

            # Remove all visible columns from selection
            for column in visible_columns:
                if column in self.selected_columns:
                    self.selected_columns.remove(column)

            # Update UI
            self.column_list.setChecked(self.selected_columns)

            # Store history if there was a change
            if old_selected != self.selected_columns:
                self._store_selection_history(old_selected, "Deselect All Visible")
                self.process_data()
                self.evaluate.emit()

    def _on_checklist_changed(self, checked: List[str]) -> None:
        """Handle checkbox changes with history tracking."""
        # Prevent storing history during restoration
        if self.history.is_restoring_history:
            return

        old_selected_columns = self.selected_columns.copy()
        visible = list(getattr(self, "_visible_columns", checked))
        checked_set = set(checked)
        # Keep hidden selections: only reconcile the columns currently on screen.
        new_selected = [col for col in self.selected_columns if col not in visible]
        # Preserve prior order for still-checked visible columns, then append
        # newly checked ones in checklist order.
        new_selected += [
            col for col in visible if col in checked_set and col in old_selected_columns
        ]
        new_selected += [
            col
            for col in visible
            if col in checked_set and col not in old_selected_columns
        ]
        self.selected_columns = new_selected

        # Only store history if there was an actual change
        if old_selected_columns != self.selected_columns:
            self._store_selection_history(
                old_selected_columns, "Column Selection Changed"
            )
            self.process_data()
            self.evaluate.emit()

    def _store_selection_history(
        self, old_selected: List[str], description: str
    ) -> None:
        """
        Store selection change in history.

        Args:
            old_selected: Previous selection state
            description: Description of the change
        """
        history_data = {
            "node": self.node,
            "old_selected_columns": old_selected,
            "new_selected_columns": self.selected_columns.copy(),
        }

        self.history.storeHistory(
            desc=description,
            data=history_data,
            setModified=True,
        )

    def history_stamp_callback(
        self, history_data: Dict[str, Any], is_undo: bool
    ) -> None:
        """
        Callback for undo/redo operations to restore column selection.

        Args:
            history_data: Dictionary containing old and new states
            is_undo: True if this is an undo operation, False for redo
        """
        with self.history.restoring(is_undo=is_undo):
            if is_undo:
                self.selected_columns = history_data["old_selected_columns"]
            else:
                self.selected_columns = history_data["new_selected_columns"]

            # Update UI elements if they exist
            if hasattr(self, "column_list") and self.column_list is not None:
                try:
                    self.column_list.blockSignals(True)
                    self._update_column_list()
                except RuntimeError:
                    # Widget has been deleted
                    pass
                finally:
                    try:
                        self.column_list.blockSignals(False)
                    except RuntimeError:
                        pass

            self.process_data()
            self.evaluate.emit()

    def _get_selected_columns(self) -> List[str]:
        """
        Get list of currently selected column names from the UI.

        Returns:
            List of column names that are checked in the column list
        """
        if hasattr(self, "column_list") and self.column_list is not None:
            try:
                return self.column_list.checked()
            except RuntimeError:
                # Widget has been deleted, return stored selection
                return self.selected_columns.copy()
        return []

    def get_code(self) -> str:
        """
        Generate Python code for the unique operation using Polars.

        Returns:
            String containing the generated Python code for removing duplicates
        """
        if not self.incoming_variable:
            # Fallback: always define both outputs so downstream code never
            # NameErrors.
            return (
                "import polars as pl\n"
                f"{self.variable_name} = pl.DataFrame()\n"
                f"{self.duplicate_variable_name} = pl.DataFrame()\n"
            )

        live_columns = self._live_selected_columns()
        if not live_columns:
            return (
                "import polars as pl\n"
                f"{self.variable_name} = {self.incoming_variable}\n"
                f"{self.duplicate_variable_name} = {self.incoming_variable}.head(0)\n"
            )

        columns_list = [f'"{col}"' for col in live_columns]
        columns_str = "[" + ", ".join(columns_list) + "]"
        duplicate_expr = f"pl.struct({columns_str}).is_duplicated()"
        code_lines = [
            "import polars as pl",
            f"# Split into unique and duplicate records based on: {', '.join(live_columns)}",
            f"{self.variable_name} = {self.incoming_variable}.unique(subset={columns_str}, maintain_order=True)",
            f"{self.duplicate_variable_name} = {self.incoming_variable}.filter({duplicate_expr})",
        ]

        return "\n".join(code_lines) + "\n"

    def serialize(self):
        res = super().serialize()
        res["selected_columns"] = self.selected_columns
        return res

    def deserialize(self, data, hashmap={}):
        res = super().deserialize(data, hashmap)

        try:
            self.selected_columns = data.get("selected_columns", [])
            return True and res
        except Exception as e:
            dumpException(e)
        return res


@register_node(PreparationNodes.UNIQUE, NodeTypes.PREPARATION)
class TriggerNode_Unique(TriggerNode):
    """
    Node for removing duplicate rows based on selected columns using Polars.

    Provides functionality to remove duplicate rows from a LazyFrame based on
    one or more selected columns. Uses Polars unique() operation for efficient
    deduplication while maintaining lazy evaluation.
    """

    icon = "node_unique"
    node_code = PreparationNodes.UNIQUE
    node_type = NodeTypes.PREPARATION
    node_title = "Unique"
    content_label_objname = "trigger_node_unique"
    style = {}

    def __init__(self, scene: "Scene") -> None:
        """Initialize the Unique node with proper scene integration."""
        super().__init__(
            scene,
            inputs=[1],
            outputs=[3, 3],
            output_text=["Unique", "Duplicates"],
        )
        self.eval()

    def initInnerClasses(self) -> None:
        """Initialize inner classes for content, graphics node and connections."""
        self.content: UniqueContent = UniqueContent(self)
        self.grNode: TriggerGraphicsNode = TriggerGraphicsNode(self)
        self.content.evaluate.connect(self.onInputChanged)
        self.param: List[Dict[str, Any]] = []

    def processInputs(
        self, input_values: List[List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """
        Process incoming data and prepare for unique operation.

        Args:
            input_values: List of input data from connected nodes

        Returns:
            List containing processed data with unique operation applied
        """
        this_socket_index = 0
        input_node = self.getInput(this_socket_index)
        socket_index = self.getSocketValue(input_node.outputs, self)
        input_value = input_values[this_socket_index][socket_index]

        if input_value:
            # Set input data for unique processing
            self.content.incom_data = input_value.get("data")
            self.content.incoming_variable = input_value.get("variable_name")
            self.content.process_data()
            self.param = [
                {
                    "data": self.content.data,
                    "variable_name": self.content.variable_name,
                },
                {
                    "data": self.content.duplicate_data,
                    "variable_name": self.content.duplicate_variable_name,
                },
            ]
            return self.param
        else:
            self.markDirty(True)
            self.markInvalid(True)
            if hasattr(self, "grNode") and self.grNode is not None:
                try:
                    if self.getInput(this_socket_index) is None:
                        self.grNode.setToolTip("Input is not connected")
                    else:
                        self.grNode.setToolTip("Upstream node produced no output")
                except RuntimeError:
                    pass
            return None

    def get_code(self) -> str:
        """
        Get the generated Python code for the unique operation.

        Returns:
            String containing Polars code for removing duplicates
        """
        return self.content.get_code()
