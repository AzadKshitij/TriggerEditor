from qtpy.QtWidgets import (QWidget, QLineEdit, QPushButton, QFileDialog, QVBoxLayout, QTextEdit,       QTableWidget,
                            QCheckBox, QGroupBox, QTableWidgetItem, QHeaderView, QLayout, QComboBox, QLineEdit, QLabel, QHBoxLayout)
from qtpy.QtGui import QPixmap
from qtpy.QtCore import Qt, Signal
from trigger_designer.core.node_configuration import NodeTypes, register_node, PreparationNodes
from trigger_designer.qt.node_base import TriggerChangeHandler, TriggerNode, TriggerGraphicsNode
from nodeeditor.node_content_widget import QDMNodeContentWidget
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget
from nodeeditor.utils import dumpException
import pandas as pd
import numpy as np
from typing import Optional, TYPE_CHECKING, Any, Dict, List, OrderedDict, Type, cast, Union
if TYPE_CHECKING:
    from nodeeditor.node_scene import Scene
    from nodeeditor.node_node import Node
from trigger_designer.core.utils.cleansing_util import DataCleansing, CleansingStats, NullStrategy


class CleansingContent(QDMNodeIconContentWidget, TriggerChangeHandler):

    evaluate = Signal()  # Emit when evaluate button is clicked

    def __init__(self, node: 'TriggerNode', parent: Optional[QWidget] = None) -> None:
        super().__init__(node, parent)
        # local variables
        self.history = self.node.scene.history

        # incoming variables
        self.incoming_variable: str = ''
        self.incom_data: Optional[pd.DataFrame] = None

        # pass on variables
        self.data: Optional[pd.DataFrame] = None
        self.variable_name = f'var_cleansing_{self.id}'

        # Cleansing configuration
        self.null_strategy = NullStrategy.REPLACE_WITH_DEFAULT
        self.strip_whitespace = True
        self.normalize_spaces = True
        self.remove_all_whitespace = False
        self.case_modification = 'none'

        # Character removal options
        self.remove_letters = False
        self.remove_numbers = False
        self.remove_punctuation = False

        # Field selection
        self.selected_fields = []

        self.cleansing_stats = None

    @property
    def node(self) -> 'TriggerNode':
        return self._node

    @node.setter
    def node(self, value: 'TriggerNode') -> None:
        self._node = value

    def initUI(self, icon: Optional[QPixmap] = None) -> None:
        icon: QPixmap = self.node.rsm.get(f'{self.node.icon}')
        super().initUI(icon)

    def create_layout(self, dock_layout: QVBoxLayout) -> None:
        if self.incom_data is not None:
            main_layout = QVBoxLayout()
            main_layout.setSpacing(2)  # Minimal spacing between widgets
            main_layout.setContentsMargins(5, 5, 5, 5)

            # Field Selection Group
            fields_group = QGroupBox("Select Fields to Cleanse")
            fields_layout = QVBoxLayout()
            fields_layout.setSpacing(1)

            if self.incom_data is not None:
                for column in self.incom_data.columns:
                    field_check = QCheckBox(str(column))
                    field_check.setChecked(True)  # Default all selected
                    fields_layout.addWidget(field_check)

            fields_group.setLayout(fields_layout)

            # Null Handling Group
            null_group = QGroupBox("Replace Nulls")
            null_layout = QVBoxLayout()
            null_layout.setSpacing(1)

            null_strategy_combo = QComboBox()
            null_strategy_combo.addItems([s.value for s in NullStrategy])
            null_strategy_combo.setCurrentText(self.null_strategy.value)
            null_strategy_combo.currentTextChanged.connect(
                self.on_strategy_changed)

            null_layout.addWidget(null_strategy_combo)
            null_group.setLayout(null_layout)

            # Character Removal Group
            char_group = QGroupBox("Remove Unwanted Characters")
            char_layout = QVBoxLayout()
            char_layout.setSpacing(1)

            # Whitespace options
            whitespace_check = QCheckBox("Leading and Trailing Whitespace")
            whitespace_check.setChecked(self.strip_whitespace)
            whitespace_check.stateChanged.connect(
                lambda state: self.on_whitespace_changed(bool(state)))

            normalize_spaces_check = QCheckBox(
                "Tabs, Line Breaks, and Duplicate Whitespace")
            normalize_spaces_check.setChecked(self.normalize_spaces)
            normalize_spaces_check.stateChanged.connect(
                lambda state: self.on_normalize_spaces_changed(bool(state)))

            remove_all_whitespace_check = QCheckBox("All Whitespace")
            remove_all_whitespace_check.setChecked(self.remove_all_whitespace)
            remove_all_whitespace_check.stateChanged.connect(
                lambda state: self.on_remove_all_whitespace_changed(bool(state)))

            # Character type options
            remove_letters_check = QCheckBox("Letters")
            remove_letters_check.setChecked(False)
            remove_letters_check.stateChanged.connect(
                lambda state: self.on_remove_letters_changed(bool(state)))

            remove_numbers_check = QCheckBox("Numbers")
            remove_numbers_check.setChecked(False)
            remove_numbers_check.stateChanged.connect(
                lambda state: self.on_remove_numbers_changed(bool(state)))

            remove_punctuation_check = QCheckBox("Punctuation")
            remove_punctuation_check.setChecked(False)
            remove_punctuation_check.stateChanged.connect(
                lambda state: self.on_remove_punctuation_changed(bool(state)))

            char_layout.addWidget(whitespace_check)
            char_layout.addWidget(normalize_spaces_check)
            char_layout.addWidget(remove_all_whitespace_check)
            char_layout.addWidget(remove_letters_check)
            char_layout.addWidget(remove_numbers_check)
            char_layout.addWidget(remove_punctuation_check)
            char_group.setLayout(char_layout)

            # Stats Group
            stats_group = QGroupBox("Statistics")
            stats_layout = QVBoxLayout()
            stats_layout.setSpacing(1)
            self.stats_label = QLabel()
            stats_layout.addWidget(self.stats_label)
            stats_group.setLayout(stats_layout)

            # Add all groups to main layout
            main_layout.addWidget(fields_group)
            main_layout.addSpacing(5)  # Small space between sections
            main_layout.addWidget(null_group)
            main_layout.addSpacing(5)
            main_layout.addWidget(char_group)
            main_layout.addSpacing(5)
            main_layout.addWidget(stats_group)
            main_layout.addStretch()  # Push everything to the top

            self.process_data()
            dock_layout.addLayout(main_layout)
        else:
            no_data_label = QLabel('No incoming data available')
            no_data_label.setAlignment(Qt.AlignCenter)
            no_data_label.setStyleSheet('color: gray;')
            dock_layout.addWidget(no_data_label)

        # return layout

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

    def on_strategy_changed(self, value: str) -> None:
        """Handle null strategy combo box changes"""
        try:
            self.null_strategy = NullStrategy(value)
            self.process_data()
            self.evaluate.emit()
        except ValueError as e:
            print(f"Invalid null strategy value: {value}")

    def on_case_changed(self, value: str) -> None:
        """Handle case modification combo box changes"""
        valid_cases = ['none', 'UPPER', 'lower', 'Title']
        if value.lower() in [case.lower() for case in valid_cases]:
            self.case_modification = value.lower()
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

    # def process_data(self) -> None:
    #     if self.incom_data is not None:
    #         cleaner = DataCleansing(self.incom_data)

    #         # Apply configured transformations
    #         cleaner.handle_nulls(self.null_strategy)

    #         if self.strip_whitespace:
    #             cleaner.strip_whitespace(
    #                 remove_all=self.remove_all_whitespace,
    #                 normalize_spaces=self.normalize_spaces
    #             )

    #         if self.case_modification != 'none':
    #             cleaner.modify_case(self.case_modification)

    #         self.data = cleaner.get_result()
    #         self.cleansing_stats = cleaner.get_stats()
    #         self.update_stats_display()

    def process_data(self) -> None:
        if self.incom_data is not None:
            cleaner = DataCleansing(self.incom_data)

            # Apply configured transformations
            cleaner.handle_nulls(self.null_strategy)

            if self.strip_whitespace:
                cleaner.strip_whitespace(
                    remove_all=self.remove_all_whitespace,
                    normalize_spaces=self.normalize_spaces
                )

            # Apply character removal options
            if any([self.remove_letters, self.remove_numbers, self.remove_punctuation]):
                cleaner.remove_characters(
                    remove_letters=self.remove_letters,
                    remove_numbers=self.remove_numbers,
                    remove_punctuation=self.remove_punctuation
                )

            if self.case_modification != 'none':
                cleaner.modify_case(self.case_modification)

            self.data = cleaner.get_result()
            self.cleansing_stats: CleansingStats = cleaner.get_stats()
            self.update_stats_display()

    def update_stats_display(self) -> None:
        if self.cleansing_stats:
            stats = self.cleansing_stats
            stats_text = f"""
            Rows removed: {stats.rows_removed}
            Columns removed: {stats.columns_removed}
            Nulls replaced: {stats.nulls_replaced}
            Whitespace changes: {stats.whitespace_changes}
            Case changes: {stats.case_changes}
            """
            self.stats_label.setText(stats_text)

    def get_code(self) -> str:
        if self.data is None or self.incoming_variable is None:
            return "print('No data to process on Data Cleansing node')\n"

        code_lines = [
            f"cleaner = DataCleansing({self.incoming_variable})",
            f"cleaner.handle_nulls(NullStrategy.{self.null_strategy.name})"
        ]

        if self.strip_whitespace:
            code_lines.append(
                f"cleaner.strip_whitespace(remove_all={self.remove_all_whitespace}, "
                f"normalize_spaces={self.normalize_spaces})"
            )

        if self.case_modification != 'none':
            code_lines.append(
                f"cleaner.modify_case('{self.case_modification}')")

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
        self.content = CleansingContent(self)
        self.grNode = TriggerGraphicsNode(self)
        self.content.evaluate.connect(self.onInputChanged)

    def processInputs(self, input_values):
        # Only one input for simplicity
        this_socket_index = 0
        input_node = self.getInput(this_socket_index)
        socket_index = self.getSocketValue(input_node.outputs, self)
        input_value = input_values[this_socket_index][socket_index]

        if input_value:
            self.markDirty(False)
            self.markInvalid(False)
            # Custom processing logic for the Select node
            self.content.incom_data = input_value.get('data')
            self.content.incoming_variable = input_value.get('variable_name')
            self.evalChildren()
            return [{
                'data': self.content.data,
                'variable_name': self.content.variable_name
            }]
        # variable = self.content.variable_name
        else:
            self.markDirty(True)
            self.markInvalid(True)
            self.grNode.setToolTip('Input is not connected')
            return None

    def get_code(self):
        return self.content.get_code()
