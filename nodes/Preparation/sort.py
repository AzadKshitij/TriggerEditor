from functools import partial
from qtpy.QtWidgets import (QLineEdit, QPushButton, QFileDialog, QVBoxLayout, QTextEdit, QTableWidget,
                            QTableWidgetItem, QHeaderView, QLayout, QComboBox, QLineEdit, QLabel, QHBoxLayout)
from qtpy.QtGui import QPixmap
from qtpy.QtCore import Qt, Signal
from trigger_conf import OP_NODE_SORT, register_node, OP_NODE_FILE_INPUT
from trigger_node_base import TriggerChangeHandler, TriggerNode, TriggerGraphicsNode
from nodeeditor.node_content_widget import QDMNodeContentWidget
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget
from nodeeditor.utils import dumpException
import pandas as pd
from themes.theme import Theme

theme = Theme()


class SortContent(QDMNodeIconContentWidget, TriggerChangeHandler):

    evaluate = Signal()  # Emit when evaluate button is clicked

    def __init__(self, node, parent=None):
        super().__init__(node, parent)
        # local variables
        self.sort_data: list[dict] = []
        self.sort_rows = []
        self.row_widgets = {}  # Store references to row widgets with their indices
        self.next_row_id = 0   # Unique identifier for each row

        TriggerChangeHandler.__init__(self, self.node.scene)

        # incoming variables
        self.incoming_variable: str = ''
        self.incom_data: pd.DataFrame = None

        # pass on variables
        self.data = []
        self.variable_name = f'var_sort_{self.id}'

    def initUI(self, parent=None):
        icon = QPixmap('Resource/icons/Preparation/sort.png')
        super().initUI(icon)

    def create_layout(self, dock_layout: QVBoxLayout) -> QLayout:
        """Create the basic layout for sort node with a single condition"""
        # TODO: Add default text if no incoming data.
        main_layout = QVBoxLayout()
        self.sort_layout = QVBoxLayout()

        # Create rows based on saved sort_data or add initial row if none exists
        if self.sort_data:
            # Create rows for each saved sort condition
            for sort_item in self.sort_data:
                self.add_sort_row(restore_data=sort_item)
        else:
            # Add default first row if no saved data
            self.add_sort_row()

        # Add row for the add button
        add_btn = QPushButton("+")
        add_btn.setFixedWidth(30)
        add_btn.clicked.connect(self.add_sort_row)

        main_layout.addLayout(self.sort_layout)
        main_layout.addWidget(add_btn)
        main_layout.addStretch()

        dock_layout.addLayout(main_layout)
        self.recursively_find_widgets(dock_layout)
        return dock_layout

    def add_sort_row(self, restore_data=None):
        row_layout = QHBoxLayout()
        column_selector = QComboBox()
        column_selector.addItems(self.incom_data.columns)

        row_id = self.next_row_id
        self.next_row_id += 1

        column_selector.currentTextChanged.connect(
            partial(self.on_column_changed, row_id))
        row_layout.addWidget(column_selector)

        order_selector = QComboBox()
        order_selector.addItems(['Ascending', 'Descending'])
        order_selector.currentTextChanged.connect(
            partial(self.on_order_changed, row_id))
        row_layout.addWidget(order_selector)

        remove_button = QPushButton("-")
        remove_button.setMaximumWidth(30)
        remove_button.clicked.connect(partial(self.remove_sort_row, row_id))
        row_layout.addWidget(remove_button)

        # Store references to widgets and their layout
        self.row_widgets[row_id] = {
            'layout': row_layout,
            'column_selector': column_selector,
            'order_selector': order_selector,
            'remove_button': remove_button,
            'index': self.sort_layout.count()
        }

        if restore_data:
            column_selector.setCurrentText(restore_data['column'])
            order_selector.setCurrentText(restore_data['order'])

        self.sort_layout.addLayout(row_layout)

        if not restore_data:
            self.sort_data.append({
                'column': column_selector.currentText(),
                'order': order_selector.currentText()
            })
            print(
                "🐍 File: Preparation/sort.py | Line: 111 | add_sort_row ~ self.sort_data", self.sort_data)

    def on_column_changed(self, row_id, text):
        row_index = self.row_widgets[row_id]['index']
        self.sort_data[row_index]['column'] = text
        print("🐍 File: Preparation/sort.py | Line: 100 | on_column_changed ~ self.sort_data", self.sort_data)

    def on_order_changed(self, row_id, text):
        row_index = self.row_widgets[row_id]['index']
        self.sort_data[row_index]['order'] = text
        print("🐍 File: Preparation/sort.py | Line: 105 | on_order_changed ~ self.sort_data", self.sort_data)

    def remove_sort_row(self, row_id):
        if row_id not in self.row_widgets:
            return

        # Get the widgets for this row
        row = self.row_widgets[row_id]
        row_layout = row['layout']
        row_index = row['index']

        # Remove the corresponding data
        self.sort_data.pop(row_index)

        # Clean up widgets
        while row_layout.count():
            widget = row_layout.itemAt(0).widget()
            if widget:
                widget.deleteLater()
            row_layout.removeItem(row_layout.itemAt(0))
        self.sort_layout.removeItem(row_layout)

        # Remove from our tracking dict
        del self.row_widgets[row_id]

        # Update indices for remaining rows
        for row in self.row_widgets.values():
            if row['index'] > row_index:
                row['index'] -= 1

    def get_code(self):
        if not self.sort_data:
            return "\n" + f"{self.variable_name} = {self.incoming_variable}.copy()" + "\n"

        sort_conditions = []
        for item in self.sort_data:
            if item['column']:  # Only add if column is selected
                sort_conditions.append(
                    (item['column'], item['order'] == 'Ascending'))

        if not sort_conditions:
            return "\n" + f"{self.variable_name} = {self.incoming_variable}.copy()" + "\n"

        columns, ascending = zip(*sort_conditions)
        return "\n" + f"{self.variable_name} = {self.incoming_variable}.sort_values(by={list(columns)}, ascending={list(ascending)})" + "\n"

    def serialize(self):
        res = super().serialize()
        res['sort_data'] = self.sort_data
        return res

    def deserialize(self, data, hashmap={}):
        res = super().deserialize(data, hashmap)

        self.sort_data = data.get('sort_data', [])

        try:
            # self.filePath = data.get('filePath', "")
            return True & res
        except Exception as e:
            dumpException(e)
        return res


@register_node(OP_NODE_SORT, 'PREPARATION')
class TriggerNode_Sort(TriggerNode):
    icon = 'Resource/icons/Preparation/sort.png'
    op_code = OP_NODE_SORT
    op_type = 'PREPARATION'
    op_title = "Sort"
    content_label_objname = "trigger_node_sort"
    style = {
        'brush_color': theme.brush_color('INPUT')
    }

    def __init__(self, scene):
        super().__init__(scene, inputs=[1], outputs=[3])
        # self.eval()

    def initInnerClasses(self):
        self.content = SortContent(self)
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
            return [None]

    def get_code(self):
        return self.content.get_code()
