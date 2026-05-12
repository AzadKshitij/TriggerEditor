from qtpy.QtWidgets import (
    QWidget,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QVBoxLayout,
    QTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QLayout,
    QComboBox,
    QLineEdit,
    QLabel,
    QHBoxLayout,
)
from qtpy.QtGui import QPixmap
from qtpy.QtCore import Qt, Signal
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
from trigger_designer.qt.helpers.state_mixin import SerializableContentMixin
from trigger_designer.qt.widgets.sql_formula_editor import SQLFormulaWidget
from nodeeditor.node_content_widget import QDMNodeContentWidget
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget
from nodeeditor.utils_no_qt import dumpException
import polars as pl
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


class FormulaContent(
    QDMNodeIconContentWidget, TriggerChangeHandler, SerializableContentMixin
):
    """
    Content widget for formula node that allows users to create calculated columns using SQL-like expressions.

    This class provides a user interface for creating formulas that can add new columns or modify existing ones
    in the incoming DataFrame. Formulas are executed using DuckDB for SQL compatibility and performance.

    Attributes:
        evaluate: Qt signal emitted when formula settings change and evaluation is needed
        formula: The processed formula string for execution
        formula_text: Raw formula text as entered by user
        target_column: Name of the column to create or modify
        is_new_column: Whether the target column is new or existing
        incoming_variable: Name of the incoming data variable
        incom_data: The incoming polars DataFrame
        data: Processed DataFrame with formula applied
        variable_name: Variable name for the output
    """

    evaluate = Signal()  # Emit when evaluate button is clicked
    serialized_state_schema = {
        "formula": {"attr": "formula_text", "default": ""},
        "target_column": {"default": ""},
    }

    def __init__(self, node: "TriggerNode", parent: Optional[QWidget] = None) -> None:
        super().__init__(node, parent)
        # local variables
        self.formula: str = ""
        self.formula_text: Optional[str] = None
        self.target_column: Optional[str] = None
        self.is_new_column: bool = False
        self.history = self.node.scene.history
        TriggerChangeHandler.__init__(self, self.node.scene, self.node)

        # incoming variables
        self.incoming_variable: str = ""
        self.incom_data: Optional[pl.DataFrame] = None

        # pass on variables
        self.data: Optional[pl.DataFrame] = None
        self.variable_name = f"var_formula_{self.id}"

        # Initialize UI widget references
        self.formula_input: Optional[SQLFormulaWidget] = None
        self.column_name: Optional[QComboBox] = None

    @property
    def node(self) -> "TriggerNode":
        return self._node

    @node.setter
    def node(self, value: "TriggerNode") -> None:
        self._node = value

    def initUI(self, icon_: Optional[QPixmap] = None) -> None:
        """Initialize the user interface for the formula content widget."""
        icon: QPixmap = self.node.rsm.get(f"{self.node.icon}")
        super().initUI(icon)

    def create_layout(self, dock_layout: QVBoxLayout) -> None:
        """
        Create the layout for the formula content widget.

        Sets up UI components for formula creation including target column selection
        and formula input area. Shows appropriate message if no data is available.

        Args:
            dock_layout: The layout to add components to
        """
        if self.incom_data is None:
            no_data_label = QLabel("No incoming data available")
            no_data_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_data_label.setStyleSheet("color: gray;")
            dock_layout.addWidget(no_data_label)
        # return layout
        else:
            # Column selection
            column_layout = QHBoxLayout()
            self.column_name = QComboBox()
            self.column_name.setEditable(False)  # Initially not editable

            # Add items to combo box
            items = []
            if self.target_column and self.target_column not in self.incom_data.columns:
                items.append(self.target_column)
            items.append("+ add column")
            items.extend(list(self.incom_data.columns))
            self.column_name.addItems(items)

            if self.target_column:
                index = self.column_name.findText(self.target_column)
                if index >= 0:
                    self.column_name.setCurrentIndex(index)
            else:
                # Select "+ add column" by default
                index = self.column_name.findText("+ add column")
                if index >= 0:
                    self.column_name.setCurrentIndex(index)

            column_layout.addWidget(QLabel("Target:"))
            column_layout.addWidget(self.column_name)

            # Formula input with SQL syntax highlighting and error detection
            formula_layout = QVBoxLayout()
            self.formula_input = SQLFormulaWidget()
            self.formula_input.set_placeholder_text(
                "Enter formula e.g.:\nCASE WHEN [Age] > 30 then 'Adult' else 'Young'"
            )
            self.formula_input.setMinimumHeight(120)
            if self.formula_text:
                self.formula_input.set_text(self.formula_text)

            # Set available columns for syntax highlighting and validation
            if self.incom_data is not None:
                self.formula_input.set_available_columns(list(self.incom_data.columns))

            formula_layout.addWidget(QLabel("Formula:"))
            formula_layout.addWidget(self.formula_input)

            # Connect the activation signal
            self.column_name.activated.connect(self.handle_column_activation)
            self.formula_input.textChanged.connect(self.generate_formula)

            # Add layouts
            dock_layout.addLayout(column_layout)
            dock_layout.addLayout(formula_layout)

            self.recursively_find_widgets(dock_layout)

    def handle_column_activation(self, index: int) -> None:
        """
        Handle column selection activation in the dropdown.

        Args:
            index: Index of the activated item in the combo box
        """
        print(f"handle_column_activation called with index: {index}")
        if self.history.is_restoring_history:
            return

        old_state = {
            "target_column": self.target_column,
            "formula_text": self.formula_text,
        }

        try:
            current_text = self.column_name.itemText(index)

            if self.column_name.itemText(index) == "+ add column":
                self.column_name.setEditable(True)
                self.column_name.clearEditText()
                self.column_name.lineEdit().returnPressed.connect(
                    self.handle_new_column
                )
        except RuntimeError:
            # Widget has been deleted
            return
        else:
            self.target_column = current_text
            self.store_history(old_state)

    def handle_new_column(self) -> None:
        """Handle creation of a new column when user enters a custom column name."""
        if self.history.is_restoring_history:
            return

        old_state = {
            "target_column": self.target_column,
            "formula_text": self.formula_text,
        }

        try:
            new_column = self.column_name.currentText().strip()
        except RuntimeError:
            # Widget has been deleted
            return

        if (
            new_column
            and new_column != "+ add column"
            and new_column not in self.incom_data.columns
        ):
            # # Clear existing items
            # self.column_name.clear()
            # # Add the new column and the "+" button
            # self.column_name.addItem(new_column)
            # # Add back original columns
            # self.column_name.addItems(self.incom_data.columns)
            # # Add the "+" button
            # self.column_name.addItem("+ add column")

            self.target_column = new_column
            self.store_history(old_state)
            self.update_column_list(new_column)
            self.handle_data_changed()

            # Select the new column
            self.column_name.setCurrentIndex(0)

        # Reset to non-editable state
        self.column_name.setEditable(False)

    def handle_data_changed(self) -> None:
        """Add new column to the data when target column changes."""
        # add new column in the data using polars
        self.data = self.incom_data.clone()
        if self.target_column and self.target_column not in self.data.columns:
            self.data = self.data.with_columns(pl.lit(None).alias(self.target_column))

        # Update available columns in SQL editor for syntax highlighting
        if (
            hasattr(self, "formula_input")
            and self.formula_input
            and self.incom_data is not None
        ):
            try:
                self.formula_input.set_available_columns(list(self.incom_data.columns))
            except (RuntimeError, AttributeError):
                # Widget has been deleted or not properly initialized
                pass

    def _get_current_formula_text(self) -> str:
        if hasattr(self, "formula_input") and self.formula_input:
            return self.formula_input.get_text() or ""
        return self.formula_text or ""

    def _sync_formula_text(self) -> str:
        current_formula = self._get_current_formula_text()
        self.formula_text = current_formula
        return current_formula

    def generate_formula(self) -> None:
        """Generate and process the formula when user modifies the formula text."""
        if self.history.is_restoring_history:
            return

        old_state = {
            "target_column": self.target_column,
            "formula_text": self.formula_text,
        }
        current_formula = self._sync_formula_text()

        if not current_formula or self.incom_data is None:
            self.formula = ""
            self.data = self.incom_data.clone() if self.incom_data is not None else None
            self.store_history(old_state)
            return

        self.store_history(old_state)

        # Update formula and data using polars
        self.data = self.incom_data.clone()
        self.formula = current_formula

        # Replace column names in formula while preserving string literals
        if self.data is not None:
            for col in self.data.columns:
                self.formula = self.formula.replace(f"[{col}]", f'"{col}"')

        if self.target_column and self.target_column not in self.data.columns:
            self.data = self.data.with_columns(pl.lit(None).alias(self.target_column))

    def _replace_column_names(self, formula: str, column_name: str) -> str:
        """
        Replace column names in formula while preserving string literals.

        Args:
            formula: The formula string
            column_name: The column name to replace

        Returns:
            Formula with column names properly replaced
        """
        import re

        # Pattern to match column names in square brackets that are NOT inside string literals
        # This regex looks for [column_name] but excludes those inside single or double quotes
        pattern = rf"\[{re.escape(column_name)}\]"

        # Split the formula by string literals to avoid replacing inside them
        parts = []
        current_pos = 0

        # Find all string literals (both single and double quoted)
        string_literals = list(re.finditer(r"'[^']*'|\"[^\"]*\"", formula))

        for match in string_literals:
            # Process the part before the string literal
            before_string = formula[current_pos : match.start()]
            parts.append(re.sub(pattern, f'"{column_name}"', before_string))

            # Add the string literal as-is
            parts.append(match.group())
            current_pos = match.end()

        # Process the remaining part after the last string literal
        remaining = formula[current_pos:]
        parts.append(re.sub(pattern, f'"{column_name}"', remaining))

        return "".join(parts)

    def _prepare_formula_for_sql(self) -> str:
        """
        Prepare the formula for SQL execution by replacing column names while preserving string literals.

        Returns:
            Formula ready for SQL execution
        """
        # Get the current formula text from the editor
        if hasattr(self, "formula_input") and self.formula_input:
            current_formula = self.formula_input.get_text()
        else:
            current_formula = self.formula_text

        if not current_formula or self.data is None:
            return ""

        # Start with the current formula text to preserve quotes
        sql_formula = current_formula

        # Replace column names in square brackets with proper SQL identifiers
        if self.data is not None:
            for col in self.data.columns:
                sql_formula = self._replace_column_names(sql_formula, col)

        return sql_formula

    def store_history(self, old_state: dict) -> None:
        """
        Store history for undo/redo operations.

        Args:
            old_state: Previous state before changes
        """
        new_state = {
            "target_column": self.target_column,
            "formula_text": self.formula_text,
        }

        if old_state != new_state:
            history_data = {
                "node": self.node,
                "old_state": old_state,
                "new_state": new_state,
            }

            self.history.storeHistory(
                desc="Formula Changed", data=history_data, setModified=True
            )
            self.evaluate.emit()

    def update_column_list(self, new_column: str) -> None:
        """
        Update the column dropdown list with a new column.

        Args:
            new_column: Name of the new column to add
        """
        self.column_name.clear()
        self.column_name.addItem(new_column)
        self.column_name.addItems(self.incom_data.columns)
        self.column_name.addItem("+ add column")
        self.column_name.setCurrentIndex(0)

    def history_stamp_callback(self, history_data: dict, is_undo: bool) -> None:
        """Callback for undo/redo operations"""
        try:
            self.history.is_restoring_history = True

            if is_undo:
                state = history_data["old_state"]
            else:
                state = history_data["new_state"]

            # Update internal state first
            self.formula_text = state["formula_text"]
            self.target_column = state["target_column"]

            # Update column selector
            if hasattr(self, "column_name") and self.column_name is not None:
                try:
                    self.column_name.blockSignals(True)

                    # Rebuild combo box items
                    self.column_name.clear()

                    items = []
                    # Add target column if it exists and is not in data columns
                    if (
                        self.target_column
                        and self.target_column not in self.incom_data.columns
                    ):
                        items.append(self.target_column)

                    # Add standard items
                    items.append("+ add column")
                    items.extend(list(self.incom_data.columns))
                    self.column_name.addItems(items)

                    # Set the correct selection
                    if self.target_column:
                        index = self.column_name.findText(self.target_column)
                    else:
                        # If no target column, select "+ add column"
                        index = self.column_name.findText("+ add column")
                    if index >= 0:
                        self.column_name.setCurrentIndex(index)

                except RuntimeError:
                    # Widget has been deleted
                    pass
                finally:
                    try:
                        self.column_name.blockSignals(False)
                    except RuntimeError:
                        # Widget has been deleted
                        pass

            # Update formula input
            if hasattr(self, "formula_input") and self.formula_input is not None:
                try:
                    self.formula_input.blockSignals(True)
                    if self.formula_text is not None:
                        self.formula_input.set_text(self.formula_text)
                except RuntimeError:
                    # Widget has been deleted
                    pass
                finally:
                    try:
                        self.formula_input.blockSignals(False)
                    except RuntimeError:
                        # Widget has been deleted
                        pass

            # Update data
            self.handle_data_changed()
            # self.generate_formula()

            self.evaluate.emit()

        finally:
            self.history.is_restoring_history = False

    def get_code(self) -> str:
        """
        Generate Python code for the formula operation using DuckDB and polars.

        Returns:
            String containing the generated Python code
        """
        # Get current formula text from editor
        # current_formula = ""
        # if hasattr(self, 'formula_input') and self.formula_input:
        #     current_formula = self.formula_input.get_text()
        # elif self.formula_text:
        current_formula = self._sync_formula_text()

        if not current_formula or not self.target_column or self.data is None:
            return ""

        self.generate_formula()

        if self.target_column in self.incom_data.columns:
            self.is_new_column = False
        else:
            self.is_new_column = True

        code_lines = []

        # Add import statements and DuckDB setup
        code_lines.extend(
            [
                "import duckdb",
                "import polars as pl",
                "# Initialize DuckDB connection",
                "duck = duckdb.connect(':memory:')",
                f"# Convert polars LazyFrame to DataFrame if needed for DuckDB",
                f"df_for_duck = {self.incoming_variable}.collect() if hasattr({self.incoming_variable}, 'collect') else {self.incoming_variable}",
                "# Register DataFrame with DuckDB",
                f"duck.register('df', df_for_duck)",
            ]
        )

        # Prepare the formula for SQL execution
        sql_formula = self._prepare_formula_for_sql()

        if self.is_new_column:
            # Creating new column
            code_lines.extend(
                [
                    "# Apply formula to create new column",
                    f"{self.variable_name}_df = duck.execute('''SELECT *, {sql_formula} as \"{self.target_column}\" FROM df''').pl()",
                    f"# Create LazyFrame from polars DataFrame",
                    f"{self.variable_name} = {self.variable_name}_df.lazy()",
                ]
            )
        else:
            # Updating existing column
            code_lines.extend(
                [
                    "# Apply formula to update existing column",
                    f"{self.variable_name}_df = duck.execute('''SELECT * EXCLUDE \"{self.target_column}\", {sql_formula} as \"{self.target_column}\" FROM df''').pl()",
                    f"# Create LazyFrame from polars DataFrame",
                    f"{self.variable_name} = {self.variable_name}_df.lazy()",
                ]
            )

        code_lines.append("# Close DuckDB connection")
        code_lines.append("duck.close()")

        return "\n".join(code_lines) + "\n"

    def serialize(self) -> dict:
        """
        Serialize the formula content to a dictionary.

        Returns:
            Dictionary containing serialized formula settings
        """
        self._sync_formula_text()
        return self.serialize_content_state(super().serialize())

    def deserialize(self, data: dict, hashmap: dict = {}) -> bool:
        """
        Deserialize formula content from a dictionary.

        Args:
            data: Dictionary containing serialized data
            hashmap: Hash map for object references

        Returns:
            True if deserialization was successful
        """
        res = super().deserialize(data, hashmap)

        try:
            self.deserialize_content_state(data)
            return True & res
        except Exception as e:
            dumpException(e)
        return res


@register_node(PreparationNodes.FORMULA, NodeTypes.PREPARATION)
class TriggerNode_Formula(TriggerNode):
    """
    A node for creating calculated columns using SQL-like formula expressions.

    This node allows users to create new columns or modify existing ones using
    SQL expressions executed via DuckDB. Supports complex formulas with CASE statements,
    mathematical operations, and string functions.

    Attributes:
        icon: Icon identifier for the node
        node_code: Unique code identifying this node type
        node_type: Category of the node (PREPARATION)
        node_title: Display title for the node
        content_label_objname: Object name for the content widget
        style: Visual styling options
    """

    icon = "node_formula"
    node_code = PreparationNodes.FORMULA
    node_type = NodeTypes.PREPARATION
    node_title = "Formula"
    content_label_objname = "trigger_node_formula"
    style = {}

    def __init__(self, scene) -> None:
        """
        Initialize the formula node.

        Args:
            scene: The node editor scene containing this node
        """
        super().__init__(scene, inputs=[1], outputs=[3])
        self.markInvalid(True)

    def initInnerClasses(self) -> None:
        """
        Initialize the inner classes for the formula node.

        Sets up the content widget, graphics node, and connects signals.
        """
        self.content: FormulaContent = FormulaContent(self)
        self.grNode: TriggerGraphicsNode = TriggerGraphicsNode(self)
        self.content.evaluate.connect(self.onInputChanged)
        self.param: list = []

    def processInputs(self, input_values: list) -> Optional[list]:
        """
        Process input data and apply formula operations.

        Takes incoming data, applies the configured formula using DuckDB,
        and produces output data with the calculated column.

        Args:
            input_values: List of input values from connected nodes

        Returns:
            List containing dictionary with processed data and variable name,
            or None if no valid input is available
        """
        # Only one input for simplicity
        this_socket_index = 0
        input_node = self.getInput(this_socket_index)
        socket_index = self.getSocketValue(input_node.outputs, self)
        input_value = input_values[this_socket_index][socket_index]

        if input_value:
            self.markDirty(False)
            self.markInvalid(False)
            # Custom processing logic for the Formula node
            self.content.incom_data = input_value.get("data")
            self.content.data = input_value.get("data")
            self.content.incoming_variable = input_value.get("variable_name")
            self.param = [
                {"data": self.content.data, "variable_name": self.content.variable_name}
            ]
            self.evalChildren()

            return self.param
        else:
            print("👉🚫 Input is not connected", self.__class__.__name__)
            self.markDirty(True)
            self.markInvalid(True)
            self.grNode.setToolTip("Input is not connected")
            return None

    def get_code(self) -> str:
        """
        Get the generated code for this formula node.

        Returns:
            String containing the Python code for the formula operation
        """
        return self.content.get_code()
