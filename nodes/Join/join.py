from qtpy.QtWidgets import QLineEdit, QPushButton, QFileDialog, QVBoxLayout, QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView, QLayout, QComboBox, QLineEdit, QLabel, QHBoxLayout, QListWidget, QAbstractItemView, QFormLayout, QListWidgetItem, QCheckBox, QWidget
from qtpy.QtGui import QPixmap
from qtpy.QtCore import Qt, Signal
from trigger_conf import OP_NODE_JOIN, register_node
from trigger_node_base import TriggerNode, TriggerGraphicsNode
from nodeeditor.node_content_widget import QDMNodeContentWidget
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget
from nodeeditor.utils import dumpException
import pandas as pd
from themes.theme import Theme

theme = Theme()


class JoinContent(QDMNodeIconContentWidget):

    evaluate = Signal()  # Emit when evaluate button is clicked

    def __init__(self, node, parent=None):
        super().__init__(node, parent)
        # local variables
        self.join_type = "inner"  # Default join type
        self.mapping_data = []  # Store mapping pairs
        self.output_columns = []
        self.mapping_pairs = []

        # incoming variables
        self.left_data: pd.DataFrame = None
        self.right_data: pd.DataFrame = None
        self.left_variable: str = ''
        self.right_variable: str = ''

        # pass on variables
        self.data = []
        self.variable_name = f'var_join_{self.id}'

    def initUI(self, parent=None):
        icon = QPixmap("Resource/icons/Join/Join.png")
        super().initUI(icon)

    def create_layout(self, dock_layout: QVBoxLayout) -> QLayout:
        # Join type selection with label
        join_type_layout = QHBoxLayout()
        join_type_label = QLabel("Join Type:")
        self.join_type_combo = QComboBox()
        self.join_type_combo.addItems(["inner", "left", "right", "outer"])
        self.join_type_combo.currentTextChanged.connect(
            self.on_join_type_changed)
        join_type_layout.addWidget(join_type_label)
        join_type_layout.addWidget(self.join_type_combo)
        self.join_type_combo.setCurrentText(self.join_type)
        join_type_layout.addStretch()

        # Join columns mapping area
        join_mapping_layout = QVBoxLayout()
        join_mapping_label = QLabel("Join Column Mapping:")
        join_mapping_layout.addWidget(join_mapping_label)

        # Container for mapping rows
        self.mapping_container = QVBoxLayout()

        # Add initial mapping row
        self.add_mapping_row()

        # Add button for new mapping
        add_mapping_button = QPushButton("+")
        add_mapping_button.setMaximumWidth(30)
        add_mapping_button.clicked.connect(self.add_mapping_row)

        join_mapping_layout.addLayout(self.mapping_container)
        join_mapping_layout.addWidget(add_mapping_button)

        # Add mapping rows from stored data
        # if self.mapping_data:
        #     for mapping in self.mapping_data:
        #         self.add_mapping_row(
        #             mapping['left_column'],
        #             mapping['right_column'],
        #             create_ui=True
        #         )
        # else:
        #     # Add default mapping row if no data exists
        #     self.add_mapping_row()

        # Output columns group
        output_layout = QVBoxLayout()
        output_label = QLabel("Output Columns:")
        self.output_columns_list = QListWidget()
        self.output_columns_list.setSelectionMode(
            QAbstractItemView.MultiSelection)
        self.output_columns_list.setMaximumHeight(150)
        output_layout.addWidget(output_label)
        output_layout.addWidget(self.output_columns_list)

        # self.update_columns()

        # Main layout assembly
        # Main layout assembly
        main_layout = QVBoxLayout()
        main_layout.addLayout(join_type_layout)
        main_layout.addLayout(join_mapping_layout)
        main_layout.addLayout(output_layout)

        dock_layout.addLayout(main_layout)
        # Update UI after layout is created
        if self.left_data is not None and self.right_data is not None:
            self.update_columns()
            self.init_output_columns()

        return dock_layout

    def on_join_type_changed(self, value):
        self.join_type = value

    def add_mapping_row(self, left_col: str = '', right_col: str = ''):
        """Add a mapping row"""
        # Create a new row for mapping
        row_layout = QHBoxLayout()

        # Left column combo
        left_combo = QComboBox()
        if hasattr(self, 'left_data') and self.left_data is not None:
            left_combo.addItems(self.left_data.columns.tolist())
            if left_col and left_col in self.left_data.columns:
                left_combo.setCurrentText(left_col)

        # Right column combo
        right_combo = QComboBox()
        if hasattr(self, 'right_data') and self.right_data is not None:
            right_combo.addItems(self.right_data.columns.tolist())
            if right_col and right_col in self.right_data.columns:
                right_combo.setCurrentText(right_col)

        # Add widgets to row
        row_layout.addWidget(left_combo)
        row_layout.addWidget(QLabel("="))
        row_layout.addWidget(right_combo)

        # Remove button (only if not the first row)
        remove_btn = QPushButton("-")
        remove_btn.setMaximumWidth(30)
        row_layout.addWidget(remove_btn)

        # Store the mapping components
        mapping_pair = {
            'layout': row_layout,
            'left_combo': left_combo,
            'right_combo': right_combo,
            'remove_btn': remove_btn
        }
        self.mapping_pairs.append(mapping_pair)

        # Store mapping data
        mapping_data = {
            'left_column': left_combo.currentText(),
            'right_column': right_combo.currentText()
        }
        self.mapping_data.append(mapping_data)

        # Connect signals
        left_combo.currentTextChanged.connect(self.update_mapping_data)
        right_combo.currentTextChanged.connect(self.update_mapping_data)
        remove_btn.clicked.connect(
            lambda: self.remove_mapping_row(mapping_pair))

        # Add to container
        self.mapping_container.addLayout(row_layout)

    def init_output_columns(self):
        """Initialize output columns after data is available"""
        if hasattr(self, 'output_columns_list'):
            self.update_output_columns()

    def remove_mapping_row(self, mapping_pair):
        if len(self.mapping_pairs) > 1:  # Keep at least one mapping row
            # Remove from layout
            self.delete_layout(mapping_pair['layout'])

            # Find and remove corresponding mapping data
            idx = self.mapping_pairs.index(mapping_pair)
            if idx < len(self.mapping_data):
                self.mapping_data.pop(idx)

            # Remove from UI storage
            self.mapping_pairs.remove(mapping_pair)

    def update_mapping_data(self):
        """Update mapping data when UI changes"""
        for i, pair in enumerate(self.mapping_pairs):
            if i < len(self.mapping_data):
                self.mapping_data[i] = {
                    'left_column': pair['left_combo'].currentText(),
                    'right_column': pair['right_combo'].currentText()
                }
            else:
                self.mapping_data.append({
                    'left_column': pair['left_combo'].currentText(),
                    'right_column': pair['right_combo'].currentText()
                })
        # Trim extra mapping data if UI has fewer rows
        self.mapping_data = self.mapping_data[:len(self.mapping_pairs)]

    def delete_layout(self, layout):
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
                else:
                    self.delete_layout(item.layout())
            layout.deleteLater()

    def update_columns(self):
        if not hasattr(self, 'mapping_pairs'):
            return

        # Update mapping combos
        for pair in self.mapping_pairs:
            left_combo = pair['left_combo']
            right_combo = pair['right_combo']

            if left_combo and right_combo:  # Check if widgets exist
                # Store current selections
                left_current = left_combo.currentText()
                right_current = right_combo.currentText()

                # Update items
                left_combo.clear()
                right_combo.clear()

                if self.left_data is not None:
                    left_combo.addItems(self.left_data.columns.tolist())
                if self.right_data is not None:
                    right_combo.addItems(self.right_data.columns.tolist())

                # Restore selections if possible
                left_idx = left_combo.findText(left_current)
                right_idx = right_combo.findText(right_current)
                if left_idx >= 0:
                    left_combo.setCurrentIndex(left_idx)
                if right_idx >= 0:
                    right_combo.setCurrentIndex(right_idx)

        # Update output columns
        # Update output columns if UI exists
        if hasattr(self, 'output_columns_list'):
            self.update_output_columns()

    def update_output_columns(self):
        self.output_columns_list.clear()
        if self.left_data is not None and self.right_data is not None:
            # Create widget for left columns
            left_label = QLabel("Left Table Columns:")
            left_label.setStyleSheet("font-weight: bold; color: #4a9eff;")
            left_item = QListWidgetItem()
            # Make header non-selectable
            left_item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.output_columns_list.addItem(left_item)
            self.output_columns_list.setItemWidget(left_item, left_label)

            # Add left columns with L prefix and checkboxes
            for col in sorted(self.left_data.columns):
                self._add_column_item(col, "L", "#2a5d9c", self.output_columns)

            # Create widget for right columns
            right_label = QLabel("Right Table Columns:")
            right_label.setStyleSheet("font-weight: bold; color: #ff4a4a;")
            right_item = QListWidgetItem()
            # Make header non-selectable
            right_item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.output_columns_list.addItem(right_item)
            self.output_columns_list.setItemWidget(right_item, right_label)

            # Add right columns with R prefix and checkboxes
            for col in sorted(self.right_data.columns):
                self._add_column_item(col, "R", "#9c2a2a", self.output_columns)

    def _add_column_item(self, col, prefix, color, existing_selections):
        """Helper method to add a column item to the output columns list"""
        item = QListWidgetItem()
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 2, 5, 2)

        # Source indicator
        source_label = QLabel(prefix)
        source_label.setStyleSheet(f"""
            background-color: {color};
            color: white;
            border-radius: 3px;
            font-weight: bold;
        """)
        source_label.setFixedWidth(20)

        # Checkbox
        checkbox = QCheckBox(col)
        # Set checked state based on existing selections
        is_checked = any(
            x['name'] == col and x['source'] == prefix
            for x in existing_selections
        ) if existing_selections else True
        checkbox.setChecked(is_checked)

        # Store source information in checkbox property
        checkbox.setProperty('source', prefix)
        checkbox.stateChanged.connect(
            lambda: self._on_checkbox_changed(checkbox))

        layout.addWidget(source_label)
        layout.addWidget(checkbox)
        layout.addStretch()
        widget.setLayout(layout)

        item.setSizeHint(widget.sizeHint())
        self.output_columns_list.addItem(item)
        self.output_columns_list.setItemWidget(item, widget)

    def _on_checkbox_changed(self, checkbox):
        """Handle checkbox state changes"""
        col_name = checkbox.text()
        source = checkbox.property('source')
        col_data = {'name': col_name, 'source': source}

        if checkbox.isChecked():
            # Check if column already exists
            exists = False
            for existing in self.output_columns:
                if existing['name'] == col_name and existing['source'] == source:
                    exists = True
                    break
            if not exists:
                self.output_columns.append(col_data)
        else:
            # Remove the column if it exists
            self.output_columns = [col for col in self.output_columns
                                   if not (col['name'] == col_name and col['source'] == source)]

    def get_selected_columns(self):
        """Get list of selected column names with their sources"""
        # If UI isn't ready, return stored output columns
        if not hasattr(self, 'output_columns_list'):
            return self.output_columns

        selected = []
        for i in range(self.output_columns_list.count()):
            item = self.output_columns_list.item(i)
            widget = self.output_columns_list.itemWidget(item)
            if widget:
                layout = widget.layout()
                if layout:
                    checkbox = layout.itemAt(1).widget()
                    if isinstance(checkbox, QCheckBox) and checkbox.isChecked():
                        selected.append({
                            'name': checkbox.text(),
                            'source': checkbox.property('source')
                        })
        return selected

    def get_code(self):
        return f"print('New Node')"

    def serialize(self):
        res = super().serialize()
        res['join_type'] = self.join_type
        # Serialize mapping pairs
        # mapping_data = []
        # for pair in self.mapping_pairs:
        #     mapping_data.append({
        #         'left_column': pair['left_combo'].currentText(),
        #         'right_column': pair['right_combo'].currentText()
        #     })
        res['mapping_data'] = self.mapping_data
        # Serialize output columns
        res['output_columns'] = self.output_columns
        return res

    def deserialize(self, data, hashmap={}):
        res = super().deserialize(data, hashmap)
        try:
            # Store join type
            self.join_type = data['join_type']

            # Store mapping data
            self.mapping_data = data.get('mapping_data', [])

            # Store output columns
            self.output_columns = data.get('output_columns', [])

            return True & res
        except Exception as e:
            dumpException(e)
        return res


@register_node(OP_NODE_JOIN, 'JOIN')
class TriggerNode_Join(TriggerNode):
    icon = "Resource/icons/Join/Join.png"
    op_code = OP_NODE_JOIN
    op_type = 'JOIN'
    op_title = "Join"
    content_label_objname = "trigger_node_join"
    style = {
        'brush_color': theme.brush_color('INPUT')
    }

    def __init__(self, scene):
        super().__init__(scene, inputs=[1, 1], outputs=[2, 2, 2])
        # self.eval()

    def initInnerClasses(self):
        self.content = JoinContent(self)
        self.grNode = TriggerGraphicsNode(self)

    def processInputs(self, input_values):
        # Only one input for simplicity
        left_input = input_values[0]
        right_input = input_values[1]

        if left_input and right_input:
            self.markDirty(False)
            self.markInvalid(False)

            # Process left input
            self.content.left_data = left_input.get('data')
            self.content.left_variable = left_input.get('variable_name')

            # Process right input
            self.content.right_data = right_input.get('data')
            self.content.right_variable = right_input.get('variable_name')

            # Update UI with available columns
            # self.content.update_columns()
            # self.content.update_columns()
            # self.content.init_output_columns()

            self.evalChildren()
            return [
                {
                    'data': self.content.left_data,
                    'variable_name': self.content.left_variable
                },
                {
                    'data': self.content.data,
                    'variable_name': self.content.variable_name
                },
                {
                    'data': self.content.right_data,
                    'variable_name': self.content.right_variable
                },
            ]

        # variable = self.content.variable_name
        else:
            self.markDirty(True)
            self.markInvalid(True)
            self.grNode.setToolTip('Both inputs must be connected')

    def get_code(self):
        return self.content.get_code()
