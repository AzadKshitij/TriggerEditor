from sys import prefix
from qtpy.QtWidgets import QLineEdit, QPushButton, QFileDialog, QVBoxLayout, QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView, QLayout, QComboBox, QLineEdit, QLabel, QHBoxLayout, QListWidget, QAbstractItemView, QFormLayout, QListWidgetItem, QCheckBox, QWidget
from qtpy.QtGui import QPixmap
from qtpy.QtCore import Qt, Signal
from trigger_conf import OP_NODE_APPEND, OP_NODE_JOIN, register_node
from trigger_node_base import TriggerNode, TriggerGraphicsNode
from nodeeditor.node_content_widget import QDMNodeContentWidget
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget
from nodeeditor.utils import dumpException
import pandas as pd
from themes.theme import Theme

theme = Theme()


class Join1Content(QDMNodeIconContentWidget):

    evaluate = Signal()  # Emit when evaluate button is clicked

    def __init__(self, node, parent=None):
        super().__init__(node, parent)
        # local variables
        self.join_type = "inner"  # Default join type
        self.mapping_data = []  # Store mapping pairs
        self.selected_columns = []
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
        icon = QPixmap("Resource/icons/Join/Append.png")
        super().initUI(icon)

    def create_layout(self, dock_layout: QVBoxLayout) -> QLayout:

        print("🐍 File: Join/join_1.py | Line: 42 | initUI ~ create_layout")
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
        # self.add_mapping_row()

        # Add button for new mapping
        add_mapping_button = QPushButton("+")
        add_mapping_button.setMaximumWidth(30)
        add_mapping_button.clicked.connect(self.add_mapping_row)

        join_mapping_layout.addLayout(self.mapping_container)
        join_mapping_layout.addWidget(add_mapping_button)

        # Output columns group
        output_layout = QVBoxLayout()
        output_label = QLabel("Output Columns:")
        self.output_columns_list = QListWidget()
        self.output_columns_list.setSelectionMode(
            QAbstractItemView.SelectionMode.MultiSelection)
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

        # add a button to transform data
        self.eval_button = QPushButton("Evaluate")
        self.eval_button.clicked.connect(self.transform_data)
        main_layout.addWidget(self.eval_button)

        dock_layout.addLayout(main_layout)
        # Update UI after layout is created
        if self.left_data is not None and self.right_data is not None:
            #     self.update_columns()
            self.load_saved_data()
            self.update_output_columns()

        return dock_layout

    def load_saved_data(self):
        if self.mapping_data:
            for mapping in self.mapping_data:
                self.add_mapping_row(
                    left_col=mapping['left_column'],
                    right_col=mapping['right_column']
                )
        # check if col exist in output_column it it does check the checkbox or uncheck it

    def on_join_type_changed(self, join_type):
        self.join_type = join_type

    # def update_combo_boxes(self):

    def add_mapping_row(self, left_col=None, right_col=None):
        # Create a new row for mapping
        row_layout = QHBoxLayout()
        left_column_combo = QComboBox()
        right_column_combo = QComboBox()

        if hasattr(self, 'left_data') and self.left_data is not None:
            left_column_combo.addItems(self.left_data.columns.tolist())
            if left_col and left_col in self.left_data.columns:
                left_column_combo.setCurrentText(left_col)

        if hasattr(self, 'right_data') and self.right_data is not None:
            right_column_combo.addItems(self.right_data.columns.tolist())
            if right_col and right_col in self.right_data.columns:
                right_column_combo.setCurrentText(right_col)

        row_layout.addWidget(left_column_combo)
        row_layout.addWidget(QLabel("="))
        row_layout.addWidget(right_column_combo)
        remove_button = QPushButton("-")
        remove_button.setMaximumWidth(30)
        row_layout.addWidget(remove_button)

        temp_map = {
            'left_column': left_column_combo.currentText(),
            'right_column': right_column_combo.currentText()
        }
        if temp_map not in self.mapping_data:
            self.mapping_data.append(temp_map)

        mapping_pair = {
            'left_combo': left_column_combo,
            'right_combo': right_column_combo,
            'layout': row_layout,
            'remove_btn': remove_button
        }
        self.mapping_pairs.append(mapping_pair)

        # connect signal
        left_column_combo.currentTextChanged.connect(self.update_mapping_data)
        right_column_combo.currentTextChanged.connect(self.update_mapping_data)
        remove_button.clicked.connect(
            lambda: self.remove_mapping_row(mapping_pair))

        # Add to container
        self.mapping_container.addLayout(row_layout)

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

    def update_output_columns(self):
        self.output_columns_list.clear()
        if self.left_data is not None and self.right_data is not None:
            if not self.selected_columns:
                # Pre-select all columns by default
                for col in sorted(self.left_data.columns):
                    self.selected_columns.append({'name': col, 'source': 'L'})
                for col in sorted(self.right_data.columns):
                    self.selected_columns.append({'name': col, 'source': 'R'})

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
                self._add_output_column_item(
                    col, "L", "#2a5d9c", self.selected_columns)

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
                self._add_output_column_item(
                    col, "R", "#9c2a2a", self.selected_columns)

    def _add_output_column_item(self, col, prefix, color, existing_selections):
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
            lambda: self._on_output_checkbox_changed(checkbox))

        # Add to selected_columns if checked by default
        # if is_checked:
        #     col_data = {'name': col, 'source': prefix}
        #     self.selected_columns.append(col_data)

        layout.addWidget(source_label)
        layout.addWidget(checkbox)
        layout.addStretch()
        widget.setLayout(layout)

        item.setSizeHint(widget.sizeHint())
        self.output_columns_list.addItem(item)
        self.output_columns_list.setItemWidget(item, widget)

    def _on_output_checkbox_changed(self, checkbox):
        """Handle checkbox state changes"""
        col_name = checkbox.text()
        source = checkbox.property('source')
        col_data = {'name': col_name, 'source': source}

        if checkbox.isChecked():
            # Check if column already exists
            exists = False
            for existing in self.selected_columns:
                if existing['name'] == col_name and existing['source'] == source:
                    exists = True
                    break
            if not exists:
                self.selected_columns.append(col_data)
        else:
            # Remove the column if it exists
            self.selected_columns = [col for col in self.selected_columns
                                     if not (col['name'] == col_name and col['source'] == source)]
        print("🐍 File: Join/Append.py | Line: 283 | _on_output_checkbox_changed ~ self.selected_columns",
              self.selected_columns)

    def transform_data(self):
        """Transform input data based on join settings"""
        if self.left_data is None or self.right_data is None:
            return None
        print("🐍 File: Join/Append.py | Line: 309 | transform_data ~ self.mapping_data", self.mapping_data)

        if not self.mapping_data:
            return None

        left_cols = [m['left_column'] for m in self.mapping_data]
        right_cols = [m['right_column'] for m in self.mapping_data]

        try:
            # Perform the merge operation
            result = pd.merge(
                self.left_data,
                self.right_data,
                left_on=left_cols,
                right_on=right_cols,
                how=self.join_type,
                suffixes=('_left', '_right')
            )

            # Filter columns based on selected_columns
            if self.selected_columns:
                selected_cols = []
                for col in self.selected_columns:
                    col_name = col['name']
                    if col['source'] == 'L':
                        # Add suffix if it's not a key column
                        if col_name not in left_cols:
                            col_name = f"{col_name}_left"
                    else:  # 'R'
                        if col_name not in right_cols:
                            col_name = f"{col_name}_right"
                    if col_name in result.columns:
                        selected_cols.append(col_name)

                result = result[selected_cols]

            # self.data = result
            print("🐍 File: Join/Append.py | Line: 318 | transform_data ~ result", result)
            self.data = result
            return result
        except Exception as e:
            print(f"Error during transformation: {str(e)}")
            return None

    def get_code(self):
        if not self.mapping_data:
            return None
        code_lines = []
        left_cols = [m['left_column'] for m in self.mapping_data]
        right_cols = [m['right_column'] for m in self.mapping_data]
        code_lines.append(
            f"{self.variable_name} = pd.merge(\n"
            f"    {self.left_variable},\n"
            f"    {self.right_variable},\n"
            f"    left_on={left_cols},\n"
            f"    right_on={right_cols},\n"
            f"    how='{self.join_type}',\n"
            f"    suffixes=('_left', '_right')\n"
            f")"
        )
        # Filter columns based on selected_columns
        if self.selected_columns:
            selected_cols = []
            for col in self.selected_columns:
                col_name = col['name']
                if col['source'] == 'L':
                    # Add suffix if it's not a key column
                    if col_name not in left_cols:
                        col_name = f"{col_name}_left"
                else:  # 'R'
                    if col_name not in right_cols:
                        col_name = f"{col_name}_right"
                selected_cols.append(f"'{col_name}'")
            # Add column selection code
            cols_str = ",\n    ".join(selected_cols)

            code_lines.append(
                f"\n# Select specific columns\n"
                f"{self.variable_name} = {self.variable_name}[[\n"
                f"    {cols_str}\n"
                f"]]"
            )
        return "\n".join(code_lines)

    def serialize(self):
        res = super().serialize()
        res['join_type'] = self.join_type
        res['mapping_data'] = self.mapping_data
        # Serialize output columns
        res['selected_columns'] = self.selected_columns
        return res

    def deserialize(self, data, hashmap={}):
        res = super().deserialize(data, hashmap)
        try:
            # Store join type
            self.join_type = data['join_type']

            # Store mapping data
            self.mapping_data = data.get('mapping_data', [])

            # Store output columns
            self.selected_columns = data.get('selected_columns', [])

            return True & res
        except Exception as e:
            dumpException(e)
        return res


@register_node(OP_NODE_APPEND, 'JOIN')
class TriggerNode_Join_1(TriggerNode):
    icon = "Resource/icons/Join/Append.png"
    op_code = OP_NODE_APPEND
    op_type = 'JOIN'
    op_title = "Join_1"
    content_label_objname = "trigger_node_join"
    style = {
        'brush_color': theme.brush_color('INPUT')
    }

    def __init__(self, scene):
        super().__init__(scene, inputs=[1, 1], outputs=[2, 2, 2])
        # self.eval()

    def initInnerClasses(self):
        self.content = Join1Content(self)
        self.grNode = TriggerGraphicsNode(self)

    def processInputs(self, input_values):
        # Only one input for simplicity
        this_left_skt = 0
        this_right_skt = 1

        # Get socket index of incoming data
        input_node = self.getInput(this_left_skt)
        left_skt = self.getSocketValue(input_node.outputs, self)
        input_node = self.getInput(this_right_skt)
        right_skt = self.getSocketValue(input_node.outputs, self)

        left_input = input_values[this_left_skt][left_skt]
        right_input = input_values[this_right_skt][right_skt]

        if left_input and right_input:
            self.markDirty(False)
            self.markInvalid(False)

            # Process left input
            self.content.left_data = left_input.get('data')
            self.content.left_variable = left_input.get('variable_name')

            # Process right input
            self.content.right_data = right_input.get('data')
            self.content.right_variable = right_input.get('variable_name')

            self.evalChildren()
            # Return three outputs in a list
            return [
                # Output 0 - Left data pass-through
                {
                    'data': self.content.left_data,
                    'variable_name': self.content.left_variable
                },
                # Output 1 - Joined data
                {
                    'data': self.content.data,
                    'variable_name': self.content.variable_name
                },
                # Output 2 - Right data pass-through
                {
                    'data': self.content.right_data,
                    'variable_name': self.content.right_variable
                }
            ]

        # variable = self.content.variable_name
        else:
            self.markDirty(True)
            self.markInvalid(True)
            self.grNode.setToolTip('Both inputs must be connected')

    def get_code(self):
        return self.content.get_code()
