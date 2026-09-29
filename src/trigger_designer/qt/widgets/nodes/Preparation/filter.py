from typing import Optional, Union
import re
import duckdb
from qtpy.QtWidgets import (
    QLineEdit,
    QVBoxLayout,
)
from qtpy.QtGui import QPixmap
from qtpy.QtCore import QTimer, Signal
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
from nodeeditor.node_content_widget import QDMNodeContentWidget
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget
from trigger_designer.qt.undo.protocol import is_syncing
from trigger_designer.qt.widgets.common import EmptyStateLabel, NoWheelComboBox
from trigger_designer.qt.widgets.sql_formula_editor import (
    SQLFormulaWidget,
    STRING_LITERAL_RE,
    translate_function_aliases,
)
from nodeeditor.utils_no_qt import dumpException
from loguru import logger
import polars as pl

FILTER_MODES = ["Simple", "Expression"]
FILTER_MODE_BUILDER = "builder"
FILTER_MODE_EXPRESSION = "expression"
_EXPRESSION_DEBOUNCE_MS = 300
EXPRESSION_PLACEHOLDER = (
    "Filter rows with SQL, e.g.:\n"
    "[order_value] in_between (0, 500) AND [status] = 'paid'"
)


class FilterContent(QDMNodeIconContentWidget, TriggerChangeHandler):
    """
    Content widget for filter node that provides UI for filtering data based on column values.

    Two modes: a Simple builder (one column / operation / value condition,
    including an inclusive In Between with min/max values) and an Expression
    editor that filters rows with a SQL WHERE clause over bracketed column
    references (e.g. ``[order_value] in_between (0, 500)``). The expression
    creates no new columns; it only selects rows.

    This class handles the user interface and logic for filtering incoming data using various
    comparison operations. It supports filtering with different data types and operations
    like equals, contains, greater than, etc.

    Attributes:
        evaluate: Qt signal emitted when filter settings change and evaluation is needed
        column: The column name to filter on
        operation: The filter operation (Equals, Contains, etc.)
        value: The value to filter against
        value2: The second value for two-sided operations (In Between)
        mode: "builder" for the Simple UI, "expression" for the SQL editor
        expression: The SQL WHERE clause used in expression mode
        incoming_variable: Name of the incoming data variable
        incom_data: The incoming polars DataFrame
        data: Filtered data (true results)
        f_data: Filtered data (false results)
        variable_name: Variable name for true filter results
        f_variable_name: Variable name for false filter results
    """

    evaluate = Signal()  # Emit when evaluate button is clicked

    def __init__(
        self, node: "TriggerNode", parent: Optional[QDMNodeIconContentWidget] = None
    ) -> None:
        super().__init__(node, parent)
        # local variables
        # self.column: str = None
        self.column: Optional[str] = None
        # self.column: str = ""
        self.operation: str = "Equals"
        self.value: Union[str, float, int] = ""
        self.value2: Union[str, float, int] = ""
        self.mode: str = FILTER_MODE_BUILDER
        self.expression: str = ""
        self.history = self.node.scene.history

        TriggerChangeHandler.__init__(self, self.node.scene, self.node)

        # incoming variables
        self.incoming_variable: str = ""
        self.incom_data: Optional[pl.DataFrame] = None

        # pass on variables
        self.data: Optional[pl.DataFrame] = None
        self.f_data: Optional[pl.DataFrame] = None
        self.variable_name = f"var_t_filter_{self.id}"
        self.f_variable_name = f"var_f_filter_{self.id}"

    @property
    def node(self) -> "TriggerNode":
        """Get the associated trigger node."""
        return self._node

    @node.setter
    def node(self, value: "TriggerNode") -> None:
        """Set the associated trigger node."""
        self._node = value

    def initUI(self, icon_: Optional[QPixmap] = None) -> None:
        """
        Initialize the user interface for the filter content widget.

        Args:
            icon_: Optional pixmap icon for the node
        """
        icon: QPixmap = self.node.rsm.get(f"{self.node.icon}")
        super().initUI(icon)

    def create_layout(self, dock_layout: QVBoxLayout) -> None:
        """
        Create the layout for the filter content widget.

        Sets up UI components including the mode selector, column selector,
        operation selector, and value input field(s) - or a SQL expression
        editor in expression mode. If no data is available, shows appropriate
        message.

        Args:
            dock_layout: The layout to add components to
        """

        if self.incom_data is None:
            dock_layout.addWidget(EmptyStateLabel())
            return
        else:
            main_layout = QVBoxLayout()
            main_layout.setSpacing(2)
            main_layout.setContentsMargins(5, 5, 5, 5)

            # Filter mode selector (Simple builder vs SQL expression)
            self.mode_selector = NoWheelComboBox()
            self.mode_selector.setObjectName("filterModeSelector")
            self.mode_selector.addItems(FILTER_MODES)
            self.mode_selector.setCurrentText(
                "Expression" if self.mode == FILTER_MODE_EXPRESSION else "Simple"
            )
            self.mode_selector.setToolTip(
                "Simple builds one column condition; Expression filters rows "
                "with a SQL WHERE clause (no new columns)"
            )
            self.mode_selector.setMinimumHeight(30)
            main_layout.addWidget(self.mode_selector)

            # Column selector combobox
            self.column_selector = NoWheelComboBox()
            self.column_selector.setObjectName("columnSelector")
            self.column_selector.setMinimumWidth(100)
            self.column_selector.setMinimumHeight(30)

            # Operation selector combobox
            self.operation_selector = NoWheelComboBox()
            self.operation_selector.setObjectName("operationSelector")
            self.operation_selector.setMinimumHeight(30)
            # Operations will be populated dynamically based on selected column type

            # Value input line edits (value2 is the max bound for In Between)
            self.value_input = QLineEdit()
            self.value_input.setObjectName("valueInput")
            self.value_input.setPlaceholderText("Enter filter value...")
            self.value_input.setMinimumHeight(30)

            self.value2_input = QLineEdit()
            self.value2_input.setObjectName("value2Input")
            self.value2_input.setPlaceholderText("Enter max value...")
            self.value2_input.setMinimumHeight(30)

            # SQL expression editor (expression mode only)
            self.expression_input = SQLFormulaWidget()
            self.expression_input.set_placeholder_text(EXPRESSION_PLACEHOLDER)
            self.expression_input.set_available_columns(
                list(frame_schema(self.incom_data))
            )
            self.expression_input.set_validate_callback(self.validate_expression)
            self.expression_input.setMinimumHeight(120)
            self._expression_debounce = QTimer(self.expression_input)
            self._expression_debounce.setSingleShot(True)
            self._expression_debounce.setInterval(_EXPRESSION_DEBOUNCE_MS)
            self._expression_debounce.timeout.connect(self._debounced_commit_expression)

            # Initialize default values after creating widgets
            # self.column = self.column_selector.currentText()
            # self.operation = self.operation_selector.currentText()
            # self.value = self.value_input.text()

            self.update_columns()

            # Add widgets to filter layout
            main_layout.addWidget(self.column_selector)
            main_layout.addWidget(self.operation_selector)
            main_layout.addWidget(self.value_input)
            main_layout.addWidget(self.value2_input)
            main_layout.addWidget(self.expression_input)

            main_layout.addStretch()

            dock_layout.addLayout(main_layout)

            self.recursively_find_widgets(dock_layout)

            # Connect signals (inside data guard — widgets exist only here)
            self.mode_selector.currentTextChanged.connect(self.on_mode_changed)
            self.column_selector.currentTextChanged.connect(self.on_column_changed)
            self.operation_selector.currentTextChanged.connect(self.on_filter_changed)
            self.value_input.textChanged.connect(self.on_filter_changed)
            self.value2_input.textChanged.connect(self.on_filter_changed)
            self.expression_input.textChanged.connect(self._expression_debounce.start)
            self.expression_input.editingFinished.connect(
                self._expression_debounce.stop
            )
            self.expression_input.editingFinished.connect(self.commit_expression)

            self._apply_mode_visibility()

    def _get_column_type_category(self, column_name: str) -> str:
        """
        Determine the category of a column based on its data type.

        Args:
            column_name: Name of the column to check

        Returns:
            Category string: 'numeric', 'string', 'date', or 'other'
        """
        if self.incom_data is None:
            return "other"
        schema = frame_schema(self.incom_data)
        if column_name not in schema:
            return "other"

        col_dtype = schema[column_name]

        # Numeric types
        if col_dtype in [
            pl.Float32,
            pl.Float64,
            pl.Int8,
            pl.Int16,
            pl.Int32,
            pl.Int64,
            pl.UInt8,
            pl.UInt16,
            pl.UInt32,
            pl.UInt64,
        ]:
            return "numeric"
        # String types
        elif col_dtype in [pl.Utf8, pl.String]:
            return "string"
        # Date/time types
        elif col_dtype in [pl.Date, pl.Datetime, pl.Time, pl.Duration]:
            return "date"
        # Other types (Boolean, List, Struct, etc.)
        else:
            return "other"

    def _update_operations_for_column_type(self, column_type: str) -> None:
        """
        Update the operation selector based on the column data type.

        Args:
            column_type: The category of the column ('numeric', 'string', 'date', 'other')
        """
        # Block signals to prevent triggering changes during update
        self.operation_selector.blockSignals(True)

        # Clear existing operations
        self.operation_selector.clear()

        # Add operations based on column type
        if column_type == "numeric":
            operations = [
                "Equals",
                "Not Equals",
                "Less Than",
                "Greater Than",
                "Less Than or Equal",
                "Greater Than or Equal",
                "In Between",
            ]
        elif column_type == "string":
            operations = ["Equals", "Not Equals", "Contains"]
        elif column_type == "date":
            operations = [
                "Equals",
                "Not Equals",
                "Less Than",
                "Greater Than",
                "Less Than or Equal",
                "Greater Than or Equal",
                "In Between",
            ]
        else:  # other types (Boolean, List, Struct, etc.)
            operations = ["Equals", "Not Equals"]

        # Add the operations to the selector
        self.operation_selector.addItems(operations)

        # Restore the previously selected operation if it's still available
        if hasattr(self, "operation") and self.operation:
            index = self.operation_selector.findText(self.operation)
            if index >= 0:
                self.operation_selector.setCurrentIndex(index)
            else:
                # If previous operation is not available, select the first one
                self.operation_selector.setCurrentIndex(0)
                self.operation = self.operation_selector.currentText()

        # Unblock signals
        self.operation_selector.blockSignals(False)

    def on_column_changed(self) -> None:
        """
        Handle column selection changes.

        Updates available operations based on the selected column's data type,
        then triggers the general filter change handling.
        """
        if hasattr(self, "column_selector") and self.incom_data is not None:
            selected_column = self.column_selector.currentText()
            if selected_column:
                # Get the column type category and update operations
                column_type = self._get_column_type_category(selected_column)
                self._update_operations_for_column_type(column_type)

        # Now handle the filter change as usual
        self.on_filter_changed()

    def update_data(self) -> None:
        """
        Update the filtered data based on current filter settings.

        Applies the selected filter operation to the incoming data and creates
        both true and false result datasets. Uses polars for data processing.
        """
        if self.incom_data is None:
            return
        if self.mode == FILTER_MODE_EXPRESSION:
            self._update_expression_data()
            return
        if self.incom_data is not None:
            needs_value2 = self.operation == "In Between"
            if (
                self.column
                and self.operation
                and self.value
                and (not needs_value2 or self.value2)
            ):
                try:
                    # Get column data type for value conversion
                    col_dtype = frame_schema(self.incom_data)[self.column]

                    # Convert value based on column type
                    if col_dtype in [
                        pl.Float32,
                        pl.Float64,
                        pl.Int8,
                        pl.Int16,
                        pl.Int32,
                        pl.Int64,
                        pl.UInt8,
                        pl.UInt16,
                        pl.UInt32,
                        pl.UInt64,
                    ]:
                        converted_value = float(self.value)
                    else:
                        # For string, date, and other types - let polars handle the conversion
                        converted_value = self.value

                    # Apply filter based on operation using polars expressions
                    # Since operations are now filtered by column type, we don't need type validation
                    if self.operation == "Equals":
                        filter_expr = pl.col(self.column) == converted_value
                    elif self.operation == "Not Equals":
                        filter_expr = pl.col(self.column) != converted_value
                    elif self.operation == "Contains":
                        # Only available for string columns, so no type check needed
                        filter_expr = pl.col(self.column).str.contains(converted_value)
                    elif self.operation == "Less Than":
                        filter_expr = pl.col(self.column) < converted_value
                    elif self.operation == "Greater Than":
                        filter_expr = pl.col(self.column) > converted_value
                    elif self.operation == "Less Than or Equal":
                        filter_expr = pl.col(self.column) <= converted_value
                    elif self.operation == "Greater Than or Equal":
                        filter_expr = pl.col(self.column) >= converted_value
                    elif self.operation == "In Between":
                        # Inclusive on both ends; entry order does not matter.
                        if col_dtype in [
                            pl.Float32,
                            pl.Float64,
                            pl.Int8,
                            pl.Int16,
                            pl.Int32,
                            pl.Int64,
                            pl.UInt8,
                            pl.UInt16,
                            pl.UInt32,
                            pl.UInt64,
                        ]:
                            low, high = float(self.value), float(self.value2)
                            low, high = (low, high) if low <= high else (high, low)
                            filter_expr = pl.col(self.column).is_between(
                                low, high, closed="both"
                            )
                        else:
                            filter_expr = pl.col(self.column).is_between(
                                self.value, self.value2, closed="both"
                            )
                    else:
                        raise ValueError(f"Unsupported operation: {self.operation}")

                    # Apply the filter for true and false results
                    self.data = self.incom_data.filter(filter_expr)
                    self.f_data = self.incom_data.filter(~filter_expr)

                except Exception as e:
                    logger.error(f"Filter error: {str(e)}")
                    self.data = None
                    self.f_data = None
            else:
                self.data = None
                self.f_data = None

    def update_columns(self) -> None:
        """
        Update the column selector with available columns from incoming data.

        Populates the column selector combobox with column names from the
        incoming DataFrame and restores previously selected values if they exist.
        """
        if self.incom_data is not None:
            self.column_selector.clear()
            self.column_selector.addItems(list(frame_schema(self.incom_data)))

            # Block signals during initial setup
            self.column_selector.blockSignals(True)
            self.operation_selector.blockSignals(True)
            self.value_input.blockSignals(True)

            # Apply stored settings if they exist
            if hasattr(self, "column") and self.column:
                index = self.column_selector.findText(self.column)
                if index >= 0:
                    self.column_selector.setCurrentIndex(index)
                else:
                    self.column = self.column_selector.currentText()
            else:
                # Set default column if none selected
                if self.column_selector.count() > 0:
                    self.column = self.column_selector.currentText()

            # Update operations based on selected column type
            if self.column:
                column_type = self._get_column_type_category(self.column)
                self._update_operations_for_column_type(column_type)

            # Apply stored operation if it exists and is available
            if hasattr(self, "operation") and self.operation:
                index = self.operation_selector.findText(self.operation)
                if index >= 0:
                    self.operation_selector.setCurrentIndex(index)
                else:
                    # If stored operation is not available, select the first one
                    if self.operation_selector.count() > 0:
                        self.operation_selector.setCurrentIndex(0)
                        self.operation = self.operation_selector.currentText()

            if hasattr(self, "value"):
                self.value_input.setText(self.value)

            if hasattr(self, "value2"):
                self.value2_input.setText(self.value2)

            if hasattr(self, "mode"):
                self.mode_selector.blockSignals(True)
                self.mode_selector.setCurrentText(
                    "Expression" if self.mode == FILTER_MODE_EXPRESSION else "Simple"
                )
                self.mode_selector.blockSignals(False)

            if hasattr(self, "expression"):
                self.expression_input.set_text(self.expression)

            # Unblock signals
            self.column_selector.blockSignals(False)
            self.operation_selector.blockSignals(False)
            self.value_input.blockSignals(False)
            self.value2_input.blockSignals(False)

            self._apply_mode_visibility()

    def _apply_mode_visibility(self) -> None:
        """Show builder widgets or the expression editor, never both."""
        try:
            is_expression = self.mode == FILTER_MODE_EXPRESSION
            self.column_selector.setVisible(not is_expression)
            self.operation_selector.setVisible(not is_expression)
            self.value_input.setVisible(not is_expression)
            self.value2_input.setVisible(
                not is_expression and self.operation == "In Between"
            )
            self.expression_input.setVisible(is_expression)
        except RuntimeError:
            pass

    def _sync_widgets_from_model(self) -> None:
        """Refresh widget values from the model, preserving widget identity.

        Every text write is guarded by an equality check: an unconditional
        setText/setPlainText resets the caret (line edits jump to the end,
        the SQL editor to position 0), which would steal the cursor on every
        keystroke burst commit.
        """
        try:
            if hasattr(self, "mode_selector"):
                self.mode_selector.setCurrentText(
                    "Expression" if self.mode == FILTER_MODE_EXPRESSION else "Simple"
                )
            if hasattr(self, "column_selector") and self.column:
                index = self.column_selector.findText(self.column)
                if index >= 0:
                    self.column_selector.setCurrentIndex(index)
            if hasattr(self, "operation_selector") and self.operation:
                index = self.operation_selector.findText(self.operation)
                if index >= 0:
                    self.operation_selector.setCurrentIndex(index)
            if hasattr(self, "value_input"):
                if self.value_input.text() != self.value:
                    self.value_input.setText(self.value)
            if hasattr(self, "value2_input"):
                if self.value2_input.text() != self.value2:
                    self.value2_input.setText(self.value2)
            if hasattr(self, "expression_input"):
                if self.expression_input.get_text() != self.expression:
                    self.expression_input.set_text(self.expression)
            self._apply_mode_visibility()
        except RuntimeError:
            pass

    def on_mode_changed(self, text: str) -> None:
        """Handle filter mode changes between Simple and Expression."""
        if is_syncing(self) or self.history.is_restoring_history:
            return
        new_mode = (
            FILTER_MODE_EXPRESSION if text == "Expression" else FILTER_MODE_BUILDER
        )
        if new_mode == self.mode:
            return
        old_state = {"mode": self.mode}
        self.mode = new_mode
        new_state = {"mode": self.mode}
        self.history.storeHistory(
            desc="Filter Mode Changed",
            data={"node": self.node, "old_state": old_state, "new_state": new_state},
            setModified=True,
        )
        self._apply_mode_visibility()
        self.evaluate.emit()
        self.update_data()

    def on_filter_changed(self) -> None:
        """
        Handle changes to filter settings.

        Called when user modifies column selection, operation, or value.
        Updates internal state, stores history for undo/redo, and triggers
        data evaluation.
        """
        # Model-driven write-backs are not user edits (undo protocol).
        if is_syncing(self):
            return
        # Prevent storing history during restoration
        if self.history.is_restoring_history:
            return

        # Get current values before updating
        new_column = self.column_selector.currentText()
        new_operation = self.operation_selector.currentText()
        new_value = self.value_input.text()
        new_value2 = self.value2_input.text()

        # Don't store history if nothing has changed
        if (
            new_column == self.column
            and new_operation == self.operation
            and new_value == self.value
            and new_value2 == self.value2
        ):
            return

        # Store old state before changes
        old_state = {
            "column": self.column,
            "operation": self.operation,
            "value": self.value,
            "value2": self.value2,
        }

        # Update current state
        self.column = new_column
        self.operation = new_operation
        self.value = new_value
        self.value2 = new_value2

        # Store new state
        new_state = {
            "column": self.column,
            "operation": self.operation,
            "value": self.value,
            "value2": self.value2,
        }

        # Only store history if there are actual changes
        if old_state != new_state:
            history_data = {
                "node": self.node,
                "old_state": old_state,
                "new_state": new_state,
            }

            self.history.storeHistory(
                desc="Filter Settings Changed", data=history_data, setModified=True
            )

        self._apply_mode_visibility()
        self.evaluate.emit()
        self.update_data()

    def history_stamp_callback(self, history_data, is_undo: bool) -> None:
        """
        Callback for undo/redo operations.

        Restores filter state from history data when undo or redo operations
        are performed. Updates UI elements and data without triggering
        additional history entries.

        Args:
            history_data: Dictionary containing old and new state information
            is_undo: True for undo operations, False for redo operations
        """
        with self.history.restoring(is_undo=is_undo):
            if is_undo:
                # Undo operation
                state = history_data["old_state"]
            else:
                # Redo operation
                state = history_data["new_state"]

            # Update the UI elements without triggering change events
            self.column_selector.blockSignals(True)
            self.operation_selector.blockSignals(True)
            self.value_input.blockSignals(True)
            self.value2_input.blockSignals(True)

            # Set the values
            if state["column"]:
                index = self.column_selector.findText(state["column"])
                if index >= 0:
                    self.column_selector.setCurrentIndex(index)
                    self.column = state["column"]

            if state["operation"]:
                index = self.operation_selector.findText(state["operation"])
                if index >= 0:
                    self.operation_selector.setCurrentIndex(index)
                    self.operation = state["operation"]

            if state["value"] is not None:
                self.value_input.setText(state["value"])
                self.value = state["value"]

            if state.get("value2") is not None:
                self.value2_input.setText(state["value2"])
                self.value2 = state["value2"]

            if state.get("mode"):
                self.mode = state["mode"]
            if state.get("expression") is not None:
                self.expression = state["expression"]
                try:
                    self.expression_input.set_text(state["expression"])
                except (AttributeError, RuntimeError):
                    pass

            # Unblock signals
            self.column_selector.blockSignals(False)
            self.operation_selector.blockSignals(False)
            self.value_input.blockSignals(False)
            self.value2_input.blockSignals(False)

            self._apply_mode_visibility()

            # Update the data
            self.update_data()

    # ------------------------------------------------------------------
    # Expression mode (SQL WHERE clause, no new columns)
    # ------------------------------------------------------------------

    @staticmethod
    def _quote_identifier(identifier: str) -> str:
        return '"' + identifier.replace('"', '""') + '"'

    def _apply_outside_string_literals(self, formula: str, transform) -> str:
        parts: list[str] = []
        current_pos = 0
        for match in STRING_LITERAL_RE.finditer(formula):
            parts.append(transform(formula[current_pos : match.start()]))
            parts.append(match.group())
            current_pos = match.end()
        parts.append(transform(formula[current_pos:]))
        return "".join(parts)

    def _normalize_string_literals(self, formula: str) -> str:
        """Rewrite "..." as '...' (only [...] are columns)."""
        token_pattern = re.compile(r"'([^']|'')*'|\"([^\"]|\"\")*\"|\[[^\]]*\]")
        parts: list[str] = []
        current_pos = 0
        for match in token_pattern.finditer(formula):
            parts.append(formula[current_pos : match.start()])
            token = match.group()
            if token.startswith('"'):
                inner = token[1:-1].replace('""', '"').replace("'", "''")
                token = f"'{inner}'"
            parts.append(token)
            current_pos = match.end()
        parts.append(formula[current_pos:])
        return "".join(parts)

    def _replace_column_names(self, formula: str, column_name: str) -> str:
        """Rewrite [column] references to quoted identifiers, case-insensitively."""
        pattern = rf"\[\s*{re.escape(column_name)}\s*\]"
        replacement = self._quote_identifier(column_name)
        return self._apply_outside_string_literals(
            formula,
            lambda segment: re.sub(pattern, replacement, segment, flags=re.IGNORECASE),
        )

    @staticmethod
    def _translate_in_between(segment: str) -> str:
        """Alias ``in_between (a, b)`` to SQL ``BETWEEN a AND b``.

        Lets ``[order_value] in_between (0, 500)`` read naturally while the
        engine stays plain DuckDB.
        """
        return re.sub(
            r"(?i)\bin_between\s*\(\s*(.+?)\s*,\s*(.+?)\s*\)",
            r"BETWEEN \1 AND \2",
            segment,
        )

    def _prepare_filter_sql(
        self, expression_text: str, available_columns: list[str]
    ) -> str:
        sql_expression = self._normalize_string_literals(expression_text)
        sql_expression = self._apply_outside_string_literals(
            sql_expression, self._translate_in_between
        )
        sql_expression = self._apply_outside_string_literals(
            sql_expression, translate_function_aliases
        )
        for column_name in available_columns:
            sql_expression = self._replace_column_names(sql_expression, column_name)
        return sql_expression

    @staticmethod
    def _shorten_error(message: str) -> str:
        text = (message or "").strip().replace("\r\n", "\n")
        first_line = text.split("\n", 1)[0].strip()
        for prefix in ("Binder Error:", "Catalog Error:", "Parser Error:"):
            if first_line.startswith(prefix):
                first_line = first_line[len(prefix) :].strip()
        return first_line[:160]

    def _update_expression_data(self) -> None:
        """Filter rows with the SQL expression via DuckDB (no new columns)."""
        text = (self.expression or "").strip()
        if not text:
            self.data = self.incom_data
            try:
                self.f_data = self.incom_data.head(0)
            except Exception:
                self.f_data = None
            return
        try:
            # DuckDB can scan a Polars LazyFrame directly (its replacement
            # scans understand LazyFrame natively) - collecting first would
            # force the whole upstream lazy chain to materialize on every
            # keystroke, even though DuckDB re-materializes it anyway.
            was_lazy = isinstance(self.incom_data, pl.LazyFrame)
            prepared = self._prepare_filter_sql(
                text, list(frame_schema(self.incom_data))
            )
            with duckdb.connect(":memory:") as duck:
                duck.register("df_filter", self.incom_data)
                # Eager .pl() here, not lazy=True: a lazy result streams
                # from this connection on collect(), which fails once the
                # `with` block below has closed it. Materializing now, while
                # the connection is open, then re-wrapping is what the
                # original code did too.
                self.data = duck.execute(
                    f"SELECT * FROM df_filter WHERE {prepared}"
                ).pl()
                self.f_data = duck.execute(
                    f"SELECT * FROM df_filter WHERE NOT ({prepared})"
                ).pl()
            if was_lazy:
                self.data = self.data.lazy()
                self.f_data = self.f_data.lazy()
        except Exception as e:
            logger.error(f"Filter expression error: {str(e)}")
            self.data = None
            self.f_data = None

    def validate_expression(self, text: str) -> list[dict]:
        """EXPLAIN the WHERE clause against the live schema for the editor."""
        if self.incom_data is None or not (text or "").strip():
            return []
        try:
            # EXPLAIN only needs column names/types, never real rows - build
            # a zero-row frame from the lazy-safe schema instead of collecting
            # the whole upstream chain on every keystroke of the editor.
            sample = pl.DataFrame(schema=frame_schema(self.incom_data))
            prepared = self._prepare_filter_sql(text, list(sample.columns))
            with duckdb.connect(":memory:") as duck:
                duck.register("df_filter", sample)
                duck.execute(
                    f"EXPLAIN SELECT * FROM df_filter WHERE {prepared}"
                ).fetchall()
            return []
        except Exception as exc:
            return [
                {
                    "message": self._shorten_error(str(exc)),
                    "line": 1,
                    "column": 0,
                    "length": 1,
                }
            ]

    def _debounced_commit_expression(self) -> None:
        """Apply the expression text after the debounce pause."""
        if self.history.is_restoring_history:
            return
        try:
            self.commit_expression()
        except RuntimeError:
            pass

    def commit_expression(self) -> None:
        """Commit the expression editor text with merged undo history."""
        if is_syncing(self) or self.history.is_restoring_history:
            return
        try:
            current = self.expression_input.get_text() or ""
        except (AttributeError, RuntimeError):
            return
        if self.expression == current:
            return
        old = self.expression
        self.expression = current
        self.update_data()
        self.evaluate.emit()
        self.push_property_change(
            ("expression",),
            old,
            current,
            "Filter Expression Changed",
            merge_key="filter-expression",
        )

    def get_code(self) -> str:
        """
        Generate Python code for the filter operation.

        Creates polars-based filter code that can be executed to reproduce
        the filter operation on the data.

        Returns:
            String containing the generated Python code
        """
        if self.mode == FILTER_MODE_EXPRESSION:
            return self._get_expression_code()

        if (
            self.incom_data is None
            or self.column is None
            or self.operation is None
            or self.value is None
            or (self.operation == "In Between" and not self.value2)
            or not self.incoming_variable
        ):
            # Fallback: always define both outputs so downstream code never
            # NameErrors. Unconfigured-but-wired passes everything to True
            # (nothing filtered out) and an empty frame to False.
            code = ["import polars as pl"]
            if self.incoming_variable:
                code.append(f"{self.variable_name} = {self.incoming_variable}")
                code.append(
                    f"{self.f_variable_name} = {self.incoming_variable}.head(0)"
                )
            else:
                code.append(f"{self.variable_name} = pl.DataFrame()")
                code.append(f"{self.f_variable_name} = pl.DataFrame()")
            return "\n".join(code) + "\n"

        # Get column data type
        col_dtype = frame_schema(self.incom_data)[self.column]

        # Format value based on data type
        if col_dtype in [
            pl.Float32,
            pl.Float64,
            pl.Int8,
            pl.Int16,
            pl.Int32,
            pl.Int64,
            pl.UInt8,
            pl.UInt16,
            pl.UInt32,
            pl.UInt64,
        ]:
            formatted_value = self.value  # Numeric value doesn't need quotes
        elif col_dtype in [pl.Date, pl.Datetime, pl.Time, pl.Duration]:
            formatted_value = f"'{self.value}'"  # Date/time values as strings
        else:
            formatted_value = f"'{self.value}'"  # String value needs quotes

        code_lines = []

        # Generate polars filter expression
        if self.operation == "Equals":
            filter_expr = f"pl.col('{self.column}') == {formatted_value}"
        elif self.operation == "Not Equals":
            filter_expr = f"pl.col('{self.column}') != {formatted_value}"
        elif self.operation == "Contains":
            filter_expr = f"pl.col('{self.column}').str.contains('{self.value}')"
        elif self.operation == "Less Than":
            filter_expr = f"pl.col('{self.column}') < {formatted_value}"
        elif self.operation == "Greater Than":
            filter_expr = f"pl.col('{self.column}') > {formatted_value}"
        elif self.operation == "Less Than or Equal":
            filter_expr = f"pl.col('{self.column}') <= {formatted_value}"
        elif self.operation == "Greater Than or Equal":
            filter_expr = f"pl.col('{self.column}') >= {formatted_value}"
        elif self.operation == "In Between":
            if col_dtype in [
                pl.Float32,
                pl.Float64,
                pl.Int8,
                pl.Int16,
                pl.Int32,
                pl.Int64,
                pl.UInt8,
                pl.UInt16,
                pl.UInt32,
                pl.UInt64,
            ]:
                low, high = float(self.value), float(self.value2)
                low, high = (low, high) if low <= high else (high, low)
                filter_expr = (
                    f"pl.col('{self.column}').is_between({low}, {high}, closed='both')"
                )
            else:
                filter_expr = (
                    f"pl.col('{self.column}').is_between('{self.value}', "
                    f"'{self.value2}', closed='both')"
                )
        else:
            filter_expr = f"pl.col('{self.column}') == {formatted_value}"

        code_lines.append("# Filter data into true and false results")
        code_lines.append(
            f"{self.variable_name} = {self.incoming_variable}.filter({filter_expr})"
        )
        code_lines.append(
            f"{self.f_variable_name} = {self.incoming_variable}.filter(~({filter_expr}))"
        )

        return "\n".join(code_lines) + "\n"

    def _get_expression_code(self) -> str:
        """Generate DuckDB-backed code for expression-mode filtering."""
        if not self.incoming_variable:
            return (
                "import polars as pl\n"
                f"{self.variable_name} = pl.DataFrame()\n"
                f"{self.f_variable_name} = pl.DataFrame()\n"
            )
        if self.incom_data is None or not (self.expression or "").strip():
            return (
                "import polars as pl\n"
                f"{self.variable_name} = {self.incoming_variable}\n"
                f"{self.f_variable_name} = {self.incoming_variable}.head(0)\n"
            )
        available_columns = list(frame_schema(self.incom_data))
        prepared = self._prepare_filter_sql(self.expression, available_columns)
        # repr(), not triple quotes: an expression ending in a string literal
        # (e.g. ``= 'paid'``) would otherwise fuse with a closing '''.
        query_t = f"SELECT * FROM df_filter WHERE {prepared}"
        query_f = f"SELECT * FROM df_filter WHERE NOT ({prepared})"
        return (
            "\n".join(
                [
                    "import duckdb",
                    "import polars as pl",
                    "# Filter rows with a SQL WHERE clause (no new columns)",
                    (
                        f"df_for_duck = {self.incoming_variable}.collect() "
                        f"if hasattr({self.incoming_variable}, 'collect') "
                        f"else {self.incoming_variable}"
                    ),
                    "duck = duckdb.connect(':memory:')",
                    "duck.register('df_filter', df_for_duck)",
                    f"{self.variable_name} = duck.execute({query_t!r}).pl()",
                    f"{self.f_variable_name} = duck.execute({query_f!r}).pl()",
                    "# Preserve lazy execution when the incoming value is lazy",
                    (
                        f"{self.variable_name} = {self.variable_name}.lazy() "
                        f"if hasattr({self.incoming_variable}, 'collect') "
                        f"else {self.variable_name}"
                    ),
                    (
                        f"{self.f_variable_name} = {self.f_variable_name}.lazy() "
                        f"if hasattr({self.incoming_variable}, 'collect') "
                        f"else {self.f_variable_name}"
                    ),
                    "duck.close()",
                ]
            )
            + "\n"
        )

    def serialize(self) -> dict:
        """
        Serialize the filter content to a dictionary.

        Returns:
            Dictionary containing serialized filter settings
        """
        res = super().serialize()
        res["column"] = self.column
        res["operation"] = self.operation
        res["value"] = self.value
        res["value2"] = self.value2
        res["mode"] = self.mode
        res["expression"] = self.expression
        return res

    def deserialize(self, data: dict, hashmap: dict = {}) -> bool:
        """
        Deserialize filter content from a dictionary.

        Args:
            data: Dictionary containing serialized data
            hashmap: Hash map for object references

        Returns:
            True if deserialization was successful
        """
        res = super().deserialize(data, hashmap)

        try:
            # Get stored settings individually (normalize to __init__
            # defaults so a fresh node and a reloaded one behave alike).
            # value2/mode/expression postdate older files and default cleanly.
            self.column = data.get("column", "") or None
            self.operation = data.get("operation", "") or "Equals"
            self.value = data.get("value", "")
            self.value2 = data.get("value2", "")
            self.mode = data.get("mode", FILTER_MODE_BUILDER)
            self.expression = data.get("expression", "")
            return True and res
        except Exception as e:
            dumpException(e)
        return res


@register_node(PreparationNodes.FILTER, NodeTypes.PREPARATION)
class TriggerNode_Filter(TriggerNode):
    """
    A node for filtering data based on column values and comparison operations.

    This node provides a user interface for applying filters to incoming data.
    It supports various comparison operations (equals, contains, greater than, etc.)
    and produces two outputs: filtered data (true results) and excluded data (false results).

    Attributes:
        icon: Icon identifier for the node
        node_code: Unique code identifying this node type
        node_type: Category of the node (PREPARATION)
        node_title: Display title for the node
        content_label_objname: Object name for the content widget
        style: Visual styling options
    """

    icon = "node_filter"
    node_code = PreparationNodes.FILTER
    node_type = NodeTypes.PREPARATION
    node_title = "Filter"
    content_label_objname = "trigger_node_filter"
    style = {}

    def __init__(self, scene) -> None:
        """
        Initialize the filter node.

        Args:
            scene: The node editor scene containing this node
        """
        super().__init__(scene, inputs=[1], outputs=[3, 3], output_text=["T", "F"])
        # self.eval()
        self.markInvalid(True)

    def initInnerClasses(self) -> None:
        """
        Initialize the inner classes for the filter node.

        Sets up the content widget, graphics node, and connects signals.
        """
        self.content: FilterContent = FilterContent(self)
        self.grNode: TriggerGraphicsNode = TriggerGraphicsNode(self)
        self.content.evaluate.connect(self.onInputChanged)
        self.param: list = []

    def processInputs(self, input_values: list) -> Optional[list]:
        """
        Process input data and apply filter operations.

        Takes incoming data, applies the configured filter, and produces
        two output datasets: one containing filtered results (true) and
        one containing excluded data (false).

        Args:
            input_values: List of input values from connected nodes

        Returns:
            List containing two dictionaries with filtered data and variable names,
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
            # Custom processing logic for the Filter node
            self.content.incom_data = input_value.get("data")
            self.content.incoming_variable = input_value.get("variable_name")
            self.content.update_data()
            self.param = [
                {
                    "data": self.content.data,
                    "variable_name": self.content.variable_name,
                },
                {
                    "data": self.content.f_data,
                    "variable_name": self.content.f_variable_name,
                },
            ]
            self.evalChildren()
            return self.param
        else:
            self.markDirty(True)
            self.markInvalid(True)
            self.grNode.setToolTip("Input is not connected")
            return None

    def get_code(self) -> str:
        """
        Get the generated code for this filter node.

        Returns:
            String containing the Python code for the filter operation
        """
        return self.content.get_code()
