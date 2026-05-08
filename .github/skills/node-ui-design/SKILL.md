---
name: node-ui-design
description: "Design or improve the UI for a TriggerEditor node's dock panel. Use when: creating the create_layout() method for a new node, redesigning an existing node's controls, adding new widgets to a node's dock panel, or connecting UI signals correctly. Produces a complete create_layout() implementation using QtPy widgets that integrates with the editor's undo/redo and evaluation systems."
argument-hint: "Describe the node's purpose and what controls it needs (dropdowns, text inputs, checkboxes, tables, etc.)."
---

# Design Node UI (`create_layout`) for TriggerEditor

## When to Use
- Writing `create_layout()` for a new node
- Redesigning a node's dock panel controls
- Adding widgets to an existing node
- Fixing signal connections or undo/redo integration

## Architecture Overview

Each node has two visual areas:
1. **The node icon** (120×120 px canvas in the graph editor) — always a simple icon, no interactivity
2. **The dock panel** (a collapsible panel on the right side) — built by `create_layout(dock_layout)`

The `create_layout(dock_layout: QVBoxLayout)` method receives the dock's root vertical layout and must add widgets to it. It is called by the base class when the panel is opened or data changes.

## UI Patterns

### Pattern 1: No-Data Guard (always required)
Always show a placeholder when no input data is connected:
```python
def create_layout(self, dock_layout: QVBoxLayout) -> None:
    if self.incom_data is None:
        no_data_label = QLabel("No incoming data available")
        no_data_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        no_data_label.setStyleSheet("color: gray;")
        dock_layout.addWidget(no_data_label)
    else:
        self._build_controls(dock_layout)
```

### Pattern 2: Column Selector (most common control)
For selecting a column from incoming data:
```python
self.column_selector = QComboBox()
self.column_selector.setObjectName("columnSelector")
self.column_selector.addItems(list(self.incom_data.columns))

# Restore previously selected value
if self.column:
    idx = self.column_selector.findText(self.column)
    if idx >= 0:
        self.column_selector.setCurrentIndex(idx)

self.column_selector.currentTextChanged.connect(self.on_changed)
```

### Pattern 3: Operation Selector (dynamic based on column type)
For operations that depend on the selected column's dtype:
```python
self.operation_selector = QComboBox()
self.operation_selector.setObjectName("operationSelector")
# Populate dynamically after column is known
self._update_operations_for_column_type(self._get_column_type_category(self.column))
self.operation_selector.currentTextChanged.connect(self.on_changed)
```

### Pattern 4: Value Input
```python
self.value_input = QLineEdit()
self.value_input.setObjectName("valueInput")
self.value_input.setPlaceholderText("Enter value...")
if self.value:
    self.value_input.setText(str(self.value))
self.value_input.textChanged.connect(self.on_changed)
```

### Pattern 5: Checkbox
```python
from qtpy.QtWidgets import QCheckBox
self.my_checkbox = QCheckBox("Enable option")
self.my_checkbox.setChecked(self.my_setting)
self.my_checkbox.stateChanged.connect(self.on_changed)
```

### Pattern 6: Labeled Row (horizontal pair)
```python
row = QHBoxLayout()
row.addWidget(QLabel("Column:"))
row.addWidget(self.column_selector)
dock_layout.addLayout(row)
```

### Pattern 7: Multi-column Table Widget
For complex configuration (e.g., groupby aggregations, sort priorities):
```python
from qtpy.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView
self.config_table = QTableWidget()
self.config_table.setColumnCount(2)
self.config_table.setHorizontalHeaderLabels(["Column", "Aggregation"])
self.config_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
# Populate from self.settings list...
```

### Pattern 8: Add/Remove Buttons Row
```python
from qtpy.QtWidgets import QPushButton
btn_row = QHBoxLayout()
add_btn = QPushButton("+ Add")
remove_btn = QPushButton("- Remove")
add_btn.clicked.connect(self.on_add)
remove_btn.clicked.connect(self.on_remove)
btn_row.addWidget(add_btn)
btn_row.addWidget(remove_btn)
dock_layout.addLayout(btn_row)
```

### Pattern 9: Stretch (push controls to top)
Always add a stretch at the bottom to prevent controls from spreading:
```python
dock_layout.addStretch()
```

## Complete `create_layout` Template
```python
def create_layout(self, dock_layout: QVBoxLayout) -> None:
    if self.incom_data is None:
        no_data_label = QLabel("No incoming data available")
        no_data_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        no_data_label.setStyleSheet("color: gray;")
        dock_layout.addWidget(no_data_label)
        return

    main_layout = QVBoxLayout()

    # --- Row 1: Column selector ---
    row1 = QHBoxLayout()
    self.column_selector = QComboBox()
    self.column_selector.setObjectName("columnSelector")
    self.column_selector.addItems(list(self.incom_data.columns))
    if self.column:
        idx = self.column_selector.findText(self.column)
        if idx >= 0:
            self.column_selector.setCurrentIndex(idx)
    self.column_selector.currentTextChanged.connect(self.on_changed)
    row1.addWidget(QLabel("Column:"))
    row1.addWidget(self.column_selector)
    main_layout.addLayout(row1)

    # --- Row 2: Value input ---
    row2 = QHBoxLayout()
    self.value_input = QLineEdit()
    self.value_input.setPlaceholderText("Enter value...")
    if self.value:
        self.value_input.setText(str(self.value))
    self.value_input.textChanged.connect(self.on_changed)
    row2.addWidget(QLabel("Value:"))
    row2.addWidget(self.value_input)
    main_layout.addLayout(row2)

    main_layout.addStretch()
    dock_layout.addLayout(main_layout)

    # REQUIRED: register all input widgets for undo/redo tracking
    self.recursively_find_widgets(dock_layout)
```

## Critical Integration Points

### 1. `recursively_find_widgets` — REQUIRED
Must be called at the end of `create_layout` (after all widgets are added). Walks the layout tree, finds all `QLineEdit`, `QSpinBox`, `QComboBox`, `QCheckBox` widgets, and connects them to `onInputChanged` for undo/redo tracking.

```python
self.recursively_find_widgets(dock_layout)
```

### 2. Signal → evaluate chain
UI changes should trigger node evaluation. Use this pattern in change handlers:
```python
def on_changed(self) -> None:
    if self.history.is_restoring_history:
        return  # Don't store history during undo/redo restoration
    # ... update self.column, self.value etc. ...
    self.evaluate.emit()  # Triggers TriggerNode.onInputChanged → eval()
    self.update_data()    # Recompute polars result immediately for preview
```

### 3. Undo/Redo History
Store history when settings change (not continuously during typing for text):
```python
old_state = {"column": self.column, "value": self.value}
# ... apply change ...
new_state = {"column": self.column, "value": self.value}
if old_state != new_state:
    self.history.storeHistory(
        desc="<Node Name> Changed",
        data={"node": self.node, "old_state": old_state, "new_state": new_state},
        setModified=True
    )
```

Implement `history_stamp_callback(self, history_data, is_undo: bool)` to restore widget state:
```python
def history_stamp_callback(self, history_data, is_undo: bool) -> None:
    try:
        self.history.is_restoring_history = True
        state = history_data["old_state"] if is_undo else history_data["new_state"]

        self.column_selector.blockSignals(True)
        idx = self.column_selector.findText(state["column"])
        if idx >= 0:
            self.column_selector.setCurrentIndex(idx)
            self.column = state["column"]
        self.column_selector.blockSignals(False)

        self.update_data()
    finally:
        self.history.is_restoring_history = False
```

### 4. Restoring State After Reconnect
When `create_layout` is called again (e.g., after data changes), restore widget state from `self` attributes — never rely on widget state as the source of truth.

### 5. Signal Blocking During Restore
When programmatically setting widget values (in `history_stamp_callback` or `update_columns`), block signals to prevent circular updates:
```python
self.my_widget.blockSignals(True)
self.my_widget.setCurrentIndex(idx)
self.my_widget.blockSignals(False)
```

## Widget Quick Reference

| Widget | Import | Common Use |
|---|---|---|
| `QComboBox` | `qtpy.QtWidgets` | Column/option selector |
| `QLineEdit` | `qtpy.QtWidgets` | Text/value input |
| `QCheckBox` | `qtpy.QtWidgets` | Boolean toggle |
| `QSpinBox` | `qtpy.QtWidgets` | Integer input |
| `QDoubleSpinBox` | `qtpy.QtWidgets` | Float input |
| `QPushButton` | `qtpy.QtWidgets` | Trigger action |
| `QLabel` | `qtpy.QtWidgets` | Static text |
| `QTableWidget` | `qtpy.QtWidgets` | Multi-row config |
| `QVBoxLayout` | `qtpy.QtWidgets` | Vertical stack |
| `QHBoxLayout` | `qtpy.QtWidgets` | Horizontal row |

## Style Guidelines
- Use `setObjectName()` on key widgets (for QSS targeting and debugging)
- Don't set fixed sizes unless necessary; prefer `setMinimumWidth()`
- Add `addStretch()` at bottom of main_layout to prevent layout stretching
- Labels should be concise (max 10 chars): `"Column:"`, `"Value:"`, `"Target:"`
- For `QComboBox` with dynamic items, always restore the previously selected value

## Reference Files
- [filter.py](../../src/trigger_designer/qt/widgets/nodes/Preparation/filter.py) — column + operation + value pattern
- [formula.py](../../src/trigger_designer/qt/widgets/nodes/Preparation/formula.py) — column + complex text editor (SQLFormulaWidget)
- [select.py](../../src/trigger_designer/qt/widgets/nodes/Preparation/select.py) — multi-column selection
- [sort.py](../../src/trigger_designer/qt/widgets/nodes/Preparation/sort.py) — sortable list pattern
- [node_base.py TriggerChangeHandler](../../src/trigger_designer/qt/node_base.py) — `recursively_find_widgets`, `registerInputWidget`
