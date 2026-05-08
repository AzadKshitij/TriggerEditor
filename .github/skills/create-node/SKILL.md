---
name: create-node
description: "Create a new node for the TriggerEditor project. Use when: adding a new node type, implementing a new data transformation, or extending the editor with new functionality. Produces a complete node file with Content class, TriggerNode class, registration, and integration steps."
argument-hint: "Describe the new node: name, category (Preparation/Transform/Join/Report), inputs, outputs, and what it does."
---

# Create a New TriggerEditor Node

## When to Use
- User wants to add a new data transformation or operation node
- User wants to extend the editor with new functionality
- User asks to create a node that doesn't exist yet

## Project Context

### Node Categories & Enums
Nodes are grouped by category in `src/trigger_designer/core/node_configuration.py`:
- `PreparationNodes` → `src/trigger_designer/qt/widgets/nodes/Preparation/`
- `TransformNodes` → `src/trigger_designer/qt/widgets/nodes/Transform/`
- `JoinNodes` → `src/trigger_designer/qt/widgets/nodes/Join/`
- `ReportNodes` → `src/trigger_designer/qt/widgets/nodes/Report/`
- `IONodes` → `src/trigger_designer/qt/widgets/nodes/InOut/`

### Key Base Classes (from `src/trigger_designer/qt/node_base.py`)
- `TriggerNode` — base node logic class
- `TriggerGraphicsNode` — visual rendering (120×120 px icon node)
- `TriggerChangeHandler` — undo/redo and input-widget registration mixin
- `QDMNodeIconContentWidget` (from nodeeditor lib) — the content widget base

### Data Flow
Each node receives `input_values` in `processInputs()`. Each input value is a dict:
```python
{"data": pl.DataFrame, "variable_name": "var_<node>_<id>"}
```
Outputs are a list of such dicts (one per output socket).

## Procedure

### Step 1 – Gather Requirements
Ask (or infer from context):
1. Node name (e.g., `Pivot`)
2. Category (Preparation / Transform / Join / Report / IO)
3. Number of inputs and socket types (`1` = data socket, `2` = exec, `3` = any)
4. Number of outputs and labels (e.g., `["True", "False"]`)
5. What operation the node performs on polars DataFrames
6. What UI controls are needed (dropdowns, text inputs, checkboxes)

### Step 2 – Add Enum Entry
Open `src/trigger_designer/core/node_configuration.py` and add the new node to the appropriate `IntEnum`:

```python
class PreparationNodes(IntEnum):
    # ... existing entries ...
    MY_NEW_NODE = auto()  # Add this line
```

### Step 3 – Create the Node File
Create `src/trigger_designer/qt/widgets/nodes/<Category>/<node_name>.py`.

Use the following template:

```python
from typing import Optional
from qtpy.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QLineEdit
)
from qtpy.QtGui import QPixmap
from qtpy.QtCore import Qt, Signal
import polars as pl
from loguru import logger

from trigger_designer.core.node_configuration import (
    register_node,
    PreparationNodes,  # Change to appropriate category
    NodeTypes,
)
from trigger_designer.qt.node_base import (
    TriggerChangeHandler,
    TriggerNode,
    TriggerGraphicsNode,
)
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget
from nodeeditor.utils_no_qt import dumpException


class <Name>Content(QDMNodeIconContentWidget, TriggerChangeHandler):
    evaluate = Signal()

    def __init__(self, node: "TriggerNode", parent: Optional[QWidget] = None) -> None:
        super().__init__(node, parent)
        # --- State variables ---
        self.history = self.node.scene.history
        TriggerChangeHandler.__init__(self, self.node.scene, self.node)

        # Incoming data
        self.incoming_variable: str = ""
        self.incom_data: Optional[pl.DataFrame] = None

        # Output data
        self.data: Optional[pl.DataFrame] = None
        self.variable_name = f"var_<name>_{self.id}"

        # UI widget references (set in create_layout)
        # self.my_widget: Optional[QComboBox] = None

    @property
    def node(self) -> "TriggerNode":
        return self._node

    @node.setter
    def node(self, value: "TriggerNode") -> None:
        self._node = value

    def initUI(self, icon_: Optional[QPixmap] = None) -> None:
        icon: QPixmap = self.node.rsm.get(f"{self.node.icon}")
        super().initUI(icon)

    def create_layout(self, dock_layout: QVBoxLayout) -> None:
        if self.incom_data is None:
            no_data_label = QLabel("No incoming data available")
            no_data_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_data_label.setStyleSheet("color: gray;")
            dock_layout.addWidget(no_data_label)
        else:
            main_layout = QVBoxLayout()
            # --- Build your UI widgets here ---
            # Example: column selector
            # self.column_selector = QComboBox()
            # self.column_selector.addItems(list(self.incom_data.columns))
            # main_layout.addWidget(self.column_selector)
            # self.column_selector.currentTextChanged.connect(self.on_changed)
            dock_layout.addLayout(main_layout)
            self.recursively_find_widgets(dock_layout)

    def update_data(self) -> None:
        """Apply the node's operation to self.incom_data, store result in self.data."""
        if self.incom_data is None:
            self.data = None
            return
        try:
            # --- Implement polars transformation here ---
            self.data = self.incom_data  # Replace with actual logic
        except Exception as e:
            logger.error(f"<Name> node error: {e}")
            self.data = None

    def get_code(self) -> str:
        """Generate polars Python code for this node's operation."""
        if self.incom_data is None:
            return "# No data available\n"
        lines = [
            f"# <Name> operation",
            f"{self.variable_name} = {self.incoming_variable}  # Replace with actual polars code",
        ]
        return "\n".join(lines) + "\n"

    def serialize(self) -> dict:
        res = super().serialize()
        # res["my_setting"] = self.my_setting
        return res

    def deserialize(self, data: dict, hashmap: dict = {}) -> bool:
        res = super().deserialize(data, hashmap)
        try:
            # self.my_setting = data.get("my_setting", "")
            return True & res
        except Exception as e:
            dumpException(e)
        return res


@register_node(PreparationNodes.MY_NEW_NODE, NodeTypes.PREPARATION)
class TriggerNode_<Name>(TriggerNode):
    icon = "node_<icon_key>"       # Icon key in resources.json
    node_code = PreparationNodes.MY_NEW_NODE
    node_type = NodeTypes.PREPARATION
    node_title = "<Node Display Name>"
    content_label_objname = "trigger_node_<name>"
    style = {}

    def __init__(self, scene) -> None:
        super().__init__(scene, inputs=[1], outputs=[1])
        self.markInvalid(True)

    def initInnerClasses(self) -> None:
        self.content: <Name>Content = <Name>Content(self)
        self.grNode: TriggerGraphicsNode = TriggerGraphicsNode(self)
        self.content.evaluate.connect(self.onInputChanged)
        self.param: list = []

    def processInputs(self, input_values: list) -> Optional[list]:
        this_socket_index = 0
        input_node = self.getInput(this_socket_index)
        socket_index = self.getSocketValue(input_node.outputs, self)
        input_value = input_values[this_socket_index][socket_index]

        if input_value:
            self.markDirty(False)
            self.markInvalid(False)
            self.content.incom_data = input_value.get("data")
            self.content.incoming_variable = input_value.get("variable_name")
            self.content.update_data()
            self.param = [
                {"data": self.content.data, "variable_name": self.content.variable_name}
            ]
            return self.param
        return None

    def get_code(self) -> str:
        return self.content.get_code()
```

### Step 4 – Add Icon (if needed)
- Icons are referenced by key in `src/trigger_designer/qt/resources/resources.json`
- SVG/PNG icons live in `src/trigger_designer/qt/resources/`
- If reusing an existing icon, check `resources.json` for available keys (e.g., `"node_filter"`, `"node_formula"`)

### Step 5 – Verify Auto-Registration
The `__init__.py` in `src/trigger_designer/qt/widgets/nodes/` auto-imports all `.py` files via `os.walk`. Your new file will be discovered automatically — no manual import needed.

### Step 6 – Verify in Node List
Run the editor and confirm the new node appears in the node list panel (drag-and-drop sidebar). The `node_title` attribute controls the display name.

## Checklist
- [ ] Enum entry added to `node_configuration.py`
- [ ] File created in the correct category subfolder
- [ ] `Content` class has: `evaluate` signal, `variable_name`, `incom_data`, `data`, `get_code()`, `serialize()`, `deserialize()`
- [ ] `TriggerNode_X` class has: all 4 class attributes, `initInnerClasses()`, `processInputs()`, `get_code()`
- [ ] `@register_node(NodeEnum.VALUE, NodeTypes.TYPE)` decorator present
- [ ] Node appears in editor node list

## Common Mistakes
- Forgetting to call `TriggerChangeHandler.__init__(self, self.node.scene, self.node)` in Content `__init__`
- Not calling `self.recursively_find_widgets(dock_layout)` at the end of `create_layout` (breaks undo/redo tracking)
- Using wrong socket type: `1` = data, `2` = exec, `3` = any
- `output_text` list must match length of `outputs` list when labels are needed
- `self.id` is set by the base class — use it to make `variable_name` unique

## Reference Files
- [node_base.py](../../src/trigger_designer/qt/node_base.py) — base classes
- [node_configuration.py](../../src/trigger_designer/core/node_configuration.py) — enums and registration
- [filter.py](../../src/trigger_designer/qt/widgets/nodes/Preparation/filter.py) — simple 1-in, 2-out example
- [formula.py](../../src/trigger_designer/qt/widgets/nodes/Preparation/formula.py) — complex UI example
- [count_recors.py](../../src/trigger_designer/qt/widgets/nodes/Transform/count_recors.py) — transform example
