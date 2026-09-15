from typing import Any, Dict, List, Optional

import polars as pl
from qtpy.QtGui import QPixmap
from qtpy.QtCore import Signal
from qtpy.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLayout,
    QVBoxLayout,
    QWidget,
)

from trigger_designer.core.node_configuration import register_node, JoinNodes, NodeTypes
from trigger_designer.qt.node_base import (
    TriggerChangeHandler,
    TriggerNode,
    TriggerGraphicsNode,
)
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget
from nodeeditor.utils import dumpException
from trigger_designer.qt.widgets.common import ConfigSection, EmptyStateLabel


def _as_lazy(frame: Any) -> Any:
    """Normalize concat inputs to LazyFrame so mixed lazy/eager works."""
    if isinstance(frame, pl.DataFrame):
        return frame.lazy()
    return frame


class AppendContent(QDMNodeIconContentWidget, TriggerChangeHandler):
    """Stack rows from two inputs (vertical concat).

    - diagonal_relaxed: union of columns, missing filled with null,
      mismatched dtypes coerced to their common supertype (default,
      never fails on schema drift).
    - diagonal: union of columns, but overlapping columns must share dtypes.
    - vertical: strict, both sides need the same schema.
    """

    evaluate = Signal()

    def __init__(self, node: "TriggerNode", parent: Optional[QWidget] = None) -> None:
        super().__init__(node, parent)
        TriggerChangeHandler.__init__(self, self.node.scene, self.node)

        self.how: str = "diagonal_relaxed"

        # incoming variables
        self.left_data: Optional[Any] = None
        self.right_data: Optional[Any] = None
        self.left_variable: str = ""
        self.right_variable: str = ""

        # pass on variables
        self.data: Optional[Any] = None
        self.variable_name: str = f"var_append_{self.id}"

    @property
    def node(self) -> "TriggerNode":
        return self._node

    @node.setter
    def node(self, value: "TriggerNode") -> None:
        self._node = value

    def initUI(self, icon_: Optional[QPixmap] = None) -> None:
        icon: QPixmap = self.node.rsm.get(f"{self.node.icon}")
        super().initUI(icon)

    def create_layout(self, dock_layout: QVBoxLayout) -> QLayout:
        if self.left_data is None and self.right_data is None:
            dock_layout.addWidget(EmptyStateLabel())
            return dock_layout

        config_group = ConfigSection("Append Configuration")
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(QLabel("How:"))
        self.how_combo = QComboBox()
        self.how_combo.addItems(["diagonal_relaxed", "diagonal", "vertical"])
        self.how_combo.setToolTip(
            "diagonal_relaxed: union of columns, missing filled with null,\n"
            "mismatched dtypes coerced to supertype.\n"
            "diagonal: union of columns, overlapping dtypes must match.\n"
            "vertical: strict, schemas must match."
        )
        self.how_combo.setCurrentText(self.how)
        self.how_combo.currentTextChanged.connect(self._on_how_changed)
        row.addWidget(self.how_combo)
        row.addStretch()
        config_group.addLayout(row)

        dock_layout.addWidget(config_group)
        dock_layout.addStretch()
        self.recursively_find_widgets(dock_layout)
        return dock_layout

    def _on_how_changed(self, text: str) -> None:
        self.how = text
        self.evaluate.emit()

    def concat(self, left: Any, right: Any) -> Any:
        """Concatenate two frames, staying lazy."""
        return pl.concat([_as_lazy(left), _as_lazy(right)], how=self.how)

    def schema_mismatch(self, left: Any, right: Any) -> Optional[str]:
        """Eager schema check for vertical mode.

        Lazy concat defers schema errors to collect-time, so compare
        (header-only) schemas up front for a clear message. None if OK.
        """
        try:
            l_schema = _as_lazy(left).collect_schema()
            r_schema = _as_lazy(right).collect_schema()
        except Exception as e:
            return str(e)
        if l_schema == r_schema:
            return None
        l_only = [c for c in l_schema.names() if c not in r_schema.names()]
        r_only = [c for c in r_schema.names() if c not in l_schema.names()]
        return f"schemas differ (left-only: {l_only}, right-only: {r_only})."

    def get_code(self) -> Optional[str]:
        if not self.left_variable or not self.right_variable:
            return "# Append: both inputs must be connected\n"
        # Inline _as_lazy equivalent so the snippet runs standalone.
        return (
            "import polars as pl\n"
            f"{self.variable_name} = pl.concat(\n"
            f"    [({self.left_variable}.lazy() if isinstance({self.left_variable}, pl.DataFrame) else {self.left_variable}),\n"
            f"     ({self.right_variable}.lazy() if isinstance({self.right_variable}, pl.DataFrame) else {self.right_variable})],\n"
            f"    how='{self.how}',\n"
            ")\n"
        )

    def serialize(self) -> Dict[str, Any]:
        res = super().serialize()
        res["how"] = self.how
        return res

    def deserialize(self, data: Dict[str, Any], hashmap: Dict[str, Any] = {}) -> bool:
        res = super().deserialize(data, hashmap)
        try:
            # Old join-shaped files stored join_type/mapping_data; those
            # settings have no concat meaning, so only "how" is restored.
            self.how = data.get("how", "diagonal_relaxed")
            if self.how not in ("diagonal_relaxed", "diagonal", "vertical"):
                self.how = "diagonal_relaxed"
            return True & res
        except Exception as e:
            dumpException(e)
        return res


@register_node(JoinNodes.APPEND, NodeTypes.JOIN)
class TriggerNode_Append(TriggerNode):
    """Append rows from the right input under the left input."""

    icon = "node_append"
    node_code = JoinNodes.APPEND
    node_type = NodeTypes.JOIN
    node_title = "Append"
    content_label_objname = "trigger_node_append"
    style = {}

    def __init__(self, scene) -> None:
        super().__init__(scene, inputs=[1, 1], outputs=[3])

    def initInnerClasses(self) -> None:
        self.content: AppendContent = AppendContent(self)
        self.grNode: TriggerGraphicsNode = TriggerGraphicsNode(self)
        self.content.evaluate.connect(self.onInputChanged)
        self.param: List[Dict[str, Any]] = []

    def processInputs(self, input_values) -> Optional[List[Dict[str, Any]]]:
        left_node = self.getInput(0)
        right_node = self.getInput(1)
        if left_node is None or right_node is None:
            self.markDirty(True)
            self.markInvalid(True)
            self.grNode.setToolTip("Both inputs must be connected")
            return None

        left_input = input_values[0][self.getSocketValue(
            left_node.outputs, self)]
        right_input = input_values[1][self.getSocketValue(
            right_node.outputs, self)]

        if not left_input or not right_input:
            self.markDirty(True)
            self.markInvalid(True)
            self.grNode.setToolTip("Both inputs must be connected")
            return None

        self.markDirty(False)
        self.markInvalid(False)

        self.content.left_data = left_input.get("data")
        self.content.left_variable = left_input.get("variable_name")
        self.content.right_data = right_input.get("data")
        self.content.right_variable = right_input.get("variable_name")

        if self.content.how == "vertical":
            mismatch = self.content.schema_mismatch(
                self.content.left_data, self.content.right_data
            )
            if mismatch is not None:
                self.markDirty(True)
                self.markInvalid(True)
                self.grNode.setToolTip(
                    f"Append failed: {mismatch} Try 'diagonal_relaxed'.")
                return None

        try:
            self.content.data = self.content.concat(
                self.content.left_data, self.content.right_data
            )
        except Exception as e:
            # e.g. vertical/diagonal with incompatible schemas.
            self.markDirty(True)
            self.markInvalid(True)
            self.grNode.setToolTip(
                f"Append failed ({e}). Try 'diagonal_relaxed'.")
            return None

        self.grNode.setToolTip("")
        self.evalChildren()
        self.param = [
            {
                "data": self.content.data,
                "variable_name": self.content.variable_name,
            }
        ]
        return self.param

    def get_code(self):
        return self.content.get_code()
