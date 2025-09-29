from qtpy.QtWidgets import (
    QWidget,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QVBoxLayout,
    QTableWidget,
    QCheckBox,
    QGroupBox,
    QTableWidgetItem,
    QHeaderView,
    QLayout,
    QComboBox,
    QLineEdit,
    QLabel,
    QHBoxLayout,
    QScrollArea,
    QSizePolicy,
)
from qtpy.QtGui import QPixmap
from qtpy.QtCore import Qt, Signal
from trigger_designer.core.node_configuration import (
    NodeTypes,
    register_node,
    PreparationNodes,
)
from trigger_designer.qt.node_base import (
    TriggerChangeHandler,
    TriggerNode,
    TriggerGraphicsNode,
)
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
from trigger_designer.core.utils.cleansing_util import (
    DataCleansing,
    CleansingStats,
    NullStrategy,
)


class CleansingContent(QDMNodeIconContentWidget, TriggerChangeHandler):

    evaluate = Signal()  # Emit when evaluate button is clicked

    def __init__(self, node: "TriggerNode", parent: Optional[QWidget] = None) -> None:
        super().__init__(node, parent)
        TriggerChangeHandler.__init__(self, self.node.scene, self.node)

        # local variables
        self.history = self.node.scene.history

        # incoming variables
        self.incoming_variable: str = ""
        self.incom_data: Optional[pl.DataFrame] = None

        # pass on variables
        self.data: Optional[pl.DataFrame] = None
        self.variable_name = f"var_cleansing_{self.id}"

        # Cleansing configuration
        self.null_strategy = NullStrategy.REPLACE_WITH_DEFAULT
        self.strip_whitespace = True
        self.normalize_spaces = True
        self.remove_all_whitespace = False
        self.case_modification = "none"

        # Character removal options
        self.remove_letters = False
        self.remove_numbers = False
        self.remove_punctuation = False

        # Field selection
        self.selected_fields = []
        self.field_checkboxes = {}

        # Remove null data options
        self.remove_null_rows = False
        self.remove_null_columns = False

        self.cleansing_stats: Optional[CleansingStats] = None

    @property
    def node(self) -> "TriggerNode":
        return self._node

    @node.setter
    def node(self, value: "TriggerNode") -> None:
        self._node = value

    def initUI(self, icon: Optional[QPixmap] = None) -> None:
        icon_: QPixmap = self.node.rsm.get(f"{self.node.icon}")
        super().initUI(icon_)

    def create_layout(self, dock_layout: QVBoxLayout) -> None:
        if self.incom_data is not None:
            # Create a scroll area for the entire configuration
            scroll_area = QScrollArea()
            scroll_area.setWidgetResizable(True)
            scroll_area.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

            # Create the main widget that will be inside the scroll area
            main_widget = QWidget()
            main_layout = QVBoxLayout(main_widget)
            main_layout.setSpacing(2)
            main_layout.setContentsMargins(5, 5, 5, 5)

            # Field Selection Group - TOP PRIORITY, 50% of space with scrollbar
            fields_group = QGroupBox("Select Fields to Cleanse")
            fields_layout = QVBoxLayout()
            fields_layout.setSpacing(1)

            # All/None buttons
            buttons_layout = QHBoxLayout()
            all_button = QPushButton("All")
            none_button = QPushButton("None")
            all_button.clicked.connect(self.select_all_fields)
            none_button.clicked.connect(self.select_no_fields)
            buttons_layout.addWidget(all_button)
            buttons_layout.addWidget(none_button)
            buttons_layout.addStretch()
            fields_layout.addLayout(buttons_layout)

            # Create scroll area for field checkboxes
            fields_scroll_area = QScrollArea()
            fields_scroll_area.setWidgetResizable(True)
            fields_scroll_area.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            fields_scroll_area.setVerticalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAsNeeded
            )
            # Set fixed height of 500px
            fields_scroll_area.setMinimumHeight(400)
            fields_scroll_area.setMaximumHeight(400)
            fields_scroll_area.setSizePolicy(
                QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
            )

            # Widget to contain the field checkboxes
            fields_widget = QWidget()
            fields_widget_layout = QVBoxLayout(fields_widget)
            fields_widget_layout.setSpacing(3)  # Increased spacing between checkboxes
            fields_widget_layout.setContentsMargins(
                10, 10, 10, 10
            )  # More padding around checkboxes

            # Field checkboxes
            self.field_checkboxes = {}
            if self.incom_data is not None:
                for column in self.incom_data.columns:
                    field_check = QCheckBox(str(column))
                    field_check.setChecked(True)  # Default all selected
                    field_check.stateChanged.connect(self.on_field_selection_changed)
                    self.field_checkboxes[str(column)] = field_check
                    fields_widget_layout.addWidget(field_check)

            fields_widget_layout.addStretch()
            fields_scroll_area.setWidget(fields_widget)
            fields_layout.addWidget(fields_scroll_area)
            fields_group.setLayout(fields_layout)

            # Set size policy for fields group to fixed 500px height
            fields_group.setSizePolicy(
                QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
            )
            fields_group.setMinimumHeight(500)
            fields_group.setMaximumHeight(500)

            # Remove Null Data Group
            null_data_group = QGroupBox("Remove Null Data")
            null_data_layout = QVBoxLayout()
            null_data_layout.setSpacing(1)

            # Remove Null Rows
            remove_null_rows_check = QCheckBox("Remove Null Rows")
            remove_null_rows_check.setChecked(self.remove_null_rows)
            remove_null_rows_check.setToolTip(
                "Remove all rows with a null value in every column"
            )
            remove_null_rows_check.stateChanged.connect(
                lambda state: self.on_remove_null_rows_changed(bool(state))
            )

            # Remove Null Columns
            remove_null_columns_check = QCheckBox("Remove Null Columns")
            remove_null_columns_check.setChecked(self.remove_null_columns)
            remove_null_columns_check.setToolTip(
                "Remove all columns with a null value in every row"
            )
            remove_null_columns_check.stateChanged.connect(
                lambda state: self.on_remove_null_columns_changed(bool(state))
            )

            null_data_layout.addWidget(remove_null_rows_check)
            null_data_layout.addWidget(remove_null_columns_check)
            null_data_group.setLayout(null_data_layout)

            # Set size policy to take minimum space required
            null_data_group.setSizePolicy(
                QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum
            )

            # Replace Nulls Group
            replace_nulls_group = QGroupBox("Replace Nulls")
            replace_nulls_layout = QVBoxLayout()
            replace_nulls_layout.setSpacing(1)

            # Replace with Blanks (String Fields) - default checked
            replace_blanks_check = QCheckBox("Replace with Blanks (String Fields)")
            replace_blanks_check.setChecked(True)
            replace_blanks_check.setToolTip(
                "Replace null values with a blank string value"
            )
            replace_blanks_check.stateChanged.connect(
                lambda state: self.on_replace_blanks_changed(bool(state))
            )

            # Replace with 0 (Numeric Fields) - default checked
            replace_zeros_check = QCheckBox("Replace with 0 (Numeric Fields)")
            replace_zeros_check.setChecked(True)
            replace_zeros_check.setToolTip("Replace null values with a 0 (zero)")
            replace_zeros_check.stateChanged.connect(
                lambda state: self.on_replace_zeros_changed(bool(state))
            )

            replace_nulls_layout.addWidget(replace_blanks_check)
            replace_nulls_layout.addWidget(replace_zeros_check)
            replace_nulls_group.setLayout(replace_nulls_layout)

            # Set size policy to take minimum space required
            replace_nulls_group.setSizePolicy(
                QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum
            )

            # Character Removal Group
            char_group = QGroupBox("Remove Unwanted Characters")
            char_layout = QVBoxLayout()
            char_layout.setSpacing(1)

            # Whitespace options
            whitespace_check = QCheckBox("Leading and Trailing Whitespace")
            whitespace_check.setChecked(True)  # Default checked as per spec
            whitespace_check.stateChanged.connect(
                lambda state: self.on_whitespace_changed(bool(state))
            )

            normalize_spaces_check = QCheckBox(
                "Tabs, Line Breaks, and Duplicate Whitespace"
            )
            normalize_spaces_check.setChecked(self.normalize_spaces)
            normalize_spaces_check.setToolTip(
                "Replace any occurrence of whitespace with a single space"
            )
            normalize_spaces_check.stateChanged.connect(
                lambda state: self.on_normalize_spaces_changed(bool(state))
            )

            remove_all_whitespace_check = QCheckBox("All Whitespace")
            remove_all_whitespace_check.setChecked(self.remove_all_whitespace)
            remove_all_whitespace_check.setToolTip(
                "Remove any occurrence of whitespace"
            )
            remove_all_whitespace_check.stateChanged.connect(
                lambda state: self.on_remove_all_whitespace_changed(bool(state))
            )

            # Character type options
            remove_letters_check = QCheckBox("Letters")
            remove_letters_check.setChecked(False)
            remove_letters_check.setToolTip(
                "Remove all letters, including non-Latin alphabet letters"
            )
            remove_letters_check.stateChanged.connect(
                lambda state: self.on_remove_letters_changed(bool(state))
            )

            remove_numbers_check = QCheckBox("Numbers")
            remove_numbers_check.setChecked(False)
            remove_numbers_check.setToolTip("Remove all numbers")
            remove_numbers_check.stateChanged.connect(
                lambda state: self.on_remove_numbers_changed(bool(state))
            )

            remove_punctuation_check = QCheckBox("Punctuation")
            remove_punctuation_check.setChecked(False)
            remove_punctuation_check.setToolTip("Remove punctuation characters")
            remove_punctuation_check.stateChanged.connect(
                lambda state: self.on_remove_punctuation_changed(bool(state))
            )

            char_layout.addWidget(whitespace_check)
            char_layout.addWidget(normalize_spaces_check)
            char_layout.addWidget(remove_all_whitespace_check)
            char_layout.addWidget(remove_letters_check)
            char_layout.addWidget(remove_numbers_check)
            char_layout.addWidget(remove_punctuation_check)
            char_group.setLayout(char_layout)

            # Set size policy to take minimum space required
            char_group.setSizePolicy(
                QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum
            )

            # Case Modification Group
            case_group = QGroupBox("Modify Case")
            case_layout = QVBoxLayout()
            case_layout.setSpacing(1)

            case_combo = QComboBox()
            case_combo.addItems(["None", "Upper Case", "Lower Case", "Title Case"])
            case_combo.setCurrentText("None")
            case_combo.currentTextChanged.connect(self.on_case_changed)
            case_combo.setToolTip("Change the capitalization of string data types")

            case_layout.addWidget(case_combo)
            case_group.setLayout(case_layout)

            # Set size policy to take minimum space required
            case_group.setSizePolicy(
                QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum
            )

            # Add all groups to main layout in the new order
            # Fields selection takes up to 500px or required space (whichever is smaller)
            # Other groups take only the minimum space they require
            main_layout.addWidget(fields_group)
            main_layout.addSpacing(5)
            main_layout.addWidget(null_data_group)
            main_layout.addSpacing(5)
            main_layout.addWidget(replace_nulls_group)
            main_layout.addSpacing(5)
            main_layout.addWidget(char_group)
            main_layout.addSpacing(5)
            main_layout.addWidget(case_group)
            main_layout.addStretch()  # Push everything to the top

            # Set the main widget to the scroll area
            scroll_area.setWidget(main_widget)

            # Add the scroll area to the dock layout
            dock_layout.addWidget(scroll_area)

            self.update_selected_fields()
            self.process_data()
        else:
            no_data_label = QLabel("No incoming data available")
            no_data_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_data_label.setStyleSheet("color: gray;")
            dock_layout.addWidget(no_data_label)

        # return layout

    def select_all_fields(self) -> None:
        """Select all fields for cleansing"""
        for checkbox in self.field_checkboxes.values():
            checkbox.setChecked(True)
        self.update_selected_fields()
        self.process_data()
        self.evaluate.emit()

    def select_no_fields(self) -> None:
        """Deselect all fields for cleansing"""
        for checkbox in self.field_checkboxes.values():
            checkbox.setChecked(False)
        self.update_selected_fields()
        self.process_data()
        self.evaluate.emit()

    def on_field_selection_changed(self) -> None:
        """Handle field selection changes"""
        self.update_selected_fields()
        self.process_data()
        self.evaluate.emit()

    def update_selected_fields(self) -> None:
        """Update the list of selected fields"""
        self.selected_fields = [
            field
            for field, checkbox in self.field_checkboxes.items()
            if checkbox.isChecked()
        ]

    def on_remove_null_rows_changed(self, state: bool) -> None:
        """Handle remove null rows checkbox changes"""
        self.remove_null_rows = state
        self.process_data()
        self.evaluate.emit()

    def on_remove_null_columns_changed(self, state: bool) -> None:
        """Handle remove null columns checkbox changes"""
        self.remove_null_columns = state
        self.process_data()
        self.evaluate.emit()

    def on_replace_blanks_changed(self, state: bool) -> None:
        """Handle replace with blanks checkbox changes"""
        if state:
            self.null_strategy = NullStrategy.REPLACE_WITH_DEFAULT
        self.process_data()
        self.evaluate.emit()

    def on_replace_zeros_changed(self, state: bool) -> None:
        """Handle replace with zeros checkbox changes"""
        if state:
            self.null_strategy = NullStrategy.REPLACE_WITH_DEFAULT
        self.process_data()
        self.evaluate.emit()

    def on_remove_letters_changed(self, state: bool) -> None:
        """Handle remove letters checkbox changes"""
        self.remove_letters = state
        self.process_data()
        self.evaluate.emit()

    def on_remove_numbers_changed(self, state: bool) -> None:
        """Handle remove numbers checkbox changes"""
        self.remove_numbers = state
        self.process_data()
        self.evaluate.emit()

    def on_remove_punctuation_changed(self, state: bool) -> None:
        """Handle remove punctuation checkbox changes"""
        self.remove_punctuation = state
        self.process_data()
        self.evaluate.emit()

    def on_case_changed(self, value: str) -> None:
        """Handle case modification combo box changes"""
        case_mapping = {
            "None": "none",
            "Upper Case": "upper",
            "Lower Case": "lower",
            "Title Case": "title",
        }

        if value in case_mapping:
            self.case_modification = case_mapping[value]
            self.process_data()
            self.evaluate.emit()
        else:
            print(f"Invalid case modification value: {value}")

    def on_whitespace_changed(self, state: bool) -> None:
        """Handle whitespace checkbox changes"""
        self.strip_whitespace = state
        self.process_data()
        self.evaluate.emit()

    def on_normalize_spaces_changed(self, state: bool) -> None:
        """Handle normalize spaces checkbox changes"""
        self.normalize_spaces = state
        self.process_data()
        self.evaluate.emit()

    def on_remove_all_whitespace_changed(self, state: bool) -> None:
        """Handle remove all whitespace checkbox changes"""
        self.remove_all_whitespace = state
        self.process_data()
        self.evaluate.emit()

    def process_data(self) -> None:
        if self.incom_data is not None:
            cleaner = DataCleansing(self.incom_data)

            # Apply null row/column removal first
            if self.remove_null_rows:
                cleaner.handle_nulls(NullStrategy.REMOVE_ALL_NULL_ROWS)

            if self.remove_null_columns:
                cleaner.handle_nulls(NullStrategy.REMOVE_ALL_NULL_COLS)

            # Apply null replacement strategy
            if self.null_strategy == NullStrategy.REPLACE_WITH_DEFAULT:
                cleaner.handle_nulls(self.null_strategy)

            # Apply transformations only to selected fields
            if self.selected_fields:
                # Apply whitespace cleaning
                if (
                    self.strip_whitespace
                    or self.normalize_spaces
                    or self.remove_all_whitespace
                ):
                    cleaner.strip_whitespace(
                        remove_all=self.remove_all_whitespace,
                        normalize_spaces=self.normalize_spaces,
                        fields=self.selected_fields,
                    )

                # Apply character removal options
                if any(
                    [self.remove_letters, self.remove_numbers, self.remove_punctuation]
                ):
                    cleaner.remove_characters(
                        remove_letters=self.remove_letters,
                        remove_numbers=self.remove_numbers,
                        remove_punctuation=self.remove_punctuation,
                        fields=self.selected_fields,
                    )

                # Apply case modification
                if self.case_modification != "none":
                    cleaner.modify_case(
                        self.case_modification, fields=self.selected_fields
                    )

            self.data = cleaner.get_result()
            self.cleansing_stats = cleaner.get_stats()

    def get_code(self) -> str:
        if self.data is None or self.incoming_variable is None:
            return "print('No data to process on Data Cleansing node')\n"

        code_lines = [
            "from trigger_designer.core.utils.cleansing_util import DataCleansing, NullStrategy",
            "import polars as pl",
            f"# Convert LazyFrame to DataFrame if needed",
            f"_cleansing_input = {self.incoming_variable}.collect() if hasattr({self.incoming_variable}, 'collect') else {self.incoming_variable}",
            f"cleaner = DataCleansing(_cleansing_input)",
        ]

        # Add null row/column removal
        if self.remove_null_rows:
            code_lines.append("cleaner.handle_nulls(NullStrategy.REMOVE_ALL_NULL_ROWS)")

        if self.remove_null_columns:
            code_lines.append("cleaner.handle_nulls(NullStrategy.REMOVE_ALL_NULL_COLS)")

        # Add null replacement
        if self.null_strategy == NullStrategy.REPLACE_WITH_DEFAULT:
            code_lines.append("cleaner.handle_nulls(NullStrategy.REPLACE_WITH_DEFAULT)")

        # Add field selection
        if self.selected_fields:
            fields_str = str(self.selected_fields)

            # Add whitespace cleaning
            if (
                self.strip_whitespace
                or self.normalize_spaces
                or self.remove_all_whitespace
            ):
                code_lines.append(
                    f"cleaner.strip_whitespace("
                    f"remove_all={self.remove_all_whitespace}, "
                    f"normalize_spaces={self.normalize_spaces}, "
                    f"fields={fields_str})"
                )

            # Add character removal
            if any([self.remove_letters, self.remove_numbers, self.remove_punctuation]):
                code_lines.append(
                    f"cleaner.remove_characters("
                    f"remove_letters={self.remove_letters}, "
                    f"remove_numbers={self.remove_numbers}, "
                    f"remove_punctuation={self.remove_punctuation}, "
                    f"fields={fields_str})"
                )

            # Add case modification
            if self.case_modification != "none":
                code_lines.append(
                    f"cleaner.modify_case('{self.case_modification}', fields={fields_str})"
                )

        code_lines.append(f"{self.variable_name} = cleaner.get_result()")

        return "\n".join(code_lines) + "\n"

    def serialize(self):
        res = super().serialize()
        return res

    def deserialize(self, data, hashmap={}):
        res = super().deserialize(data, hashmap)

        try:
            return True & res
        except Exception as e:
            dumpException(e)
        return res


@register_node(PreparationNodes.CLEANSING, NodeTypes.PREPARATION)
class TriggerNode_Cleansing(TriggerNode):
    icon = "node_cleanser"
    node_code = PreparationNodes.CLEANSING
    node_title = "Cleansing"
    node_type = NodeTypes.PREPARATION
    content_label_objname = "trigger_node_node_title"
    style = {}

    def __init__(self, scene):
        super().__init__(scene, inputs=[1], outputs=[3])
        # self.eval()

    def initInnerClasses(self):
        self.content: CleansingContent = CleansingContent(self)
        self.grNode: TriggerGraphicsNode = TriggerGraphicsNode(self)
        self.content.evaluate.connect(self.onInputChanged)
        self.param: list = []

    def processInputs(self, input_values):
        # Only one input for simplicity
        this_socket_index = 0
        input_node = self.getInput(this_socket_index)
        socket_index = self.getSocketValue(input_node.outputs, self)  # type: ignore
        input_value = input_values[this_socket_index][socket_index]

        if input_value:
            self.markDirty(False)
            self.markInvalid(False)
            # Custom processing logic for the Select node
            self.content.incom_data = input_value.get("data")
            self.content.incoming_variable = input_value.get("variable_name")
            self.evalChildren()
            self.param = [
                {"data": self.content.data, "variable_name": self.content.variable_name}
            ]
            return self.param
        # variable = self.content.variable_name
        else:
            self.markDirty(True)
            self.markInvalid(True)
            self.grNode.setToolTip("Input is not connected")
            return None

    def get_code(self):
        return self.content.get_code()
