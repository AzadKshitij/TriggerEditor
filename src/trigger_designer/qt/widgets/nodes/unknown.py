from typing import Any, Dict, List, Optional

from qtpy.QtWidgets import QVBoxLayout, QLabel, QWidget
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget

from trigger_designer.qt.node_base import (
    TriggerNode,
    TriggerGraphicsNode,
)

# NOTE: intentionally NOT registered in any opcode registry and NOT in
# _LAZY_NODE_SPECS, so it never appears in the palette. The loader
# instantiates it directly for saved nodes it cannot resolve.


class UnknownContent(QDMNodeIconContentWidget):
    """Keeps the raw saved content of an unresolvable node."""

    def __init__(self, node: "TriggerNode", parent: Optional[QWidget] = None) -> None:
        self.missing_op: str = "unknown.unknown"
        self.raw_content: Dict[str, Any] = {}
        super().__init__(node, parent)

    def create_layout(self, dock_layout: QVBoxLayout) -> QVBoxLayout:
        label = QLabel(
            f"Unknown node type:\n{self.missing_op}\n\n"
            "Its saved settings are kept and will be written back on save. "
            "Install the providing node or replace this node."
        )
        label.setWordWrap(True)
        dock_layout.addWidget(label)
        return dock_layout

    def serialize(self) -> Dict[str, Any]:
        res = super().serialize()
        res.update(self.raw_content)
        return res

    def deserialize(self, data: Dict[str, Any], hashmap: Dict[str, Any] = {}) -> bool:
        res = super().deserialize(data, hashmap)
        self.raw_content = dict(data)
        return res


class TriggerNode_Unknown(TriggerNode):
    """Placeholder for a saved node whose op id cannot be resolved.

    Preserves position, sockets (rebuilt from data by the base deserializer),
    title, and raw content, so the rest of the workflow loads intact.
    """

    icon = "node_unknown"
    node_code = 0
    node_type = "unknown"
    node_title = "Unknown"
    content_label_objname = "trigger_node_unknown"
    style = {}

    def __init__(self, scene) -> None:
        super().__init__(scene, inputs=[], outputs=[])
        self.missing_op: str = "unknown.unknown"
        self.markInvalid(True)

    def initInnerClasses(self) -> None:
        self.content: UnknownContent = UnknownContent(self)
        self.grNode: TriggerGraphicsNode = TriggerGraphicsNode(self)
        self.param: List[Dict[str, Any]] = []

    def evalImplementation(self) -> None:
        self.markInvalid(True)
        self.grNode.setToolTip(
            f"Unknown node type '{self.missing_op}' — cannot evaluate"
        )
        return None

    def get_code(self) -> str:
        return f"# Unknown node '{self.missing_op}' — skipped\n"

    def serialize(self) -> Dict[str, Any]:
        res = super().serialize()
        res["node_code"] = 0
        res["node_type"] = "unknown"
        res["op"] = self.missing_op
        return res

    def deserialize(self, data: dict, hashmap: dict = {}, restore_id: bool = True) -> bool:
        res = super().deserialize(data, hashmap, restore_id)
        op = data.get("op")
        if not op:
            # Deferred import: this module is imported during registry
            # setup, when node_configuration is only partly initialized.
            from trigger_designer.core.node_configuration import migrate_v1_data

            op = migrate_v1_data(data) or "unknown.unknown"
        self.missing_op = op
        self.content.missing_op = op
        self.markInvalid(True)
        self.grNode.setToolTip(f"Unknown node type '{op}' — see config dock")
        return res
