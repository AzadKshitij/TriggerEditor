"""P1 shaping nodes: registry identity and live/codegen agreement."""

from __future__ import annotations

import polars as pl
from nodeeditor.node_edge import Edge

from trigger_designer.core.node_configuration import (
    JoinNodes,
    NodeTypes,
    PreparationNodes,
    TransformNodes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.node_base import TriggerNode


class Source(TriggerNode):
    node_title = "Source"

    def __init__(self, scene, frame) -> None:
        self._frame = frame
        super().__init__(scene, inputs=[], outputs=[3])
        self.value = [{"data": frame, "variable_name": "var_src"}]
        self.markDirty(False)
        self.markInvalid(False)

    def evalImplementation(self):
        self.value = [{"data": self._frame, "variable_name": "var_src"}]
        self.markDirty(False)
        self.markInvalid(False)
        return self.value


CASES = (
    (PreparationNodes.RECORD_ID, NodeTypes.PREPARATION, "Record ID"),
    (PreparationNodes.SELECT_RECORDS, NodeTypes.PREPARATION, "Select Records"),
    (PreparationNodes.FIND_REPLACE, NodeTypes.PREPARATION, "Find and Replace"),
    (PreparationNodes.DATE_HELPER, NodeTypes.PREPARATION, "Date Helper"),
    (TransformNodes.PIVOT, NodeTypes.TRANSFORM, "Pivot"),
    (TransformNodes.UNPIVOT, NodeTypes.TRANSFORM, "Unpivot"),
    (JoinNodes.RECONCILE, NodeTypes.JOIN, "Reconcile"),
)


def test_registry_titles_and_icons() -> None:
    for code, family, title in CASES:
        cls = get_class_from_opcode(code, family)
        assert cls.node_title == title
        assert cls.icon.startswith("node_")
        assert cls.node_code == code


def test_record_id_live_equals_generated_code() -> None:
    window = TriggerSubWindow()
    frame = pl.DataFrame({"v": [1, 2, 3]}).lazy()
    source = Source(window.scene, frame)
    cls = get_class_from_opcode(PreparationNodes.RECORD_ID, NodeTypes.PREPARATION)
    node = cls(window.scene)
    Edge(window.scene, source.outputs[0], node.inputs[0])
    node.content.settings["name"] = "Item"
    node.markDirty(True)
    out = node.eval()
    assert out is not None and not node.isInvalid()
    live = out[0]["data"].collect()
    namespace = {"var_src": frame}
    exec(node.get_code(), {"__name__": "__main__", "pl": pl}, namespace)  # noqa: S102
    generated = namespace[node.content.variable_name].collect()
    assert generated.equals(live)
    assert live["Item"].to_list() == [1, 2, 3]


def test_unwired_shaping_nodes_define_outputs() -> None:
    for code, family, _title in CASES:
        window = TriggerSubWindow()
        node = get_class_from_opcode(code, family)(window.scene)
        namespace: dict = {}
        exec(node.get_code(), {"__name__": "__main__", "pl": pl}, namespace)  # noqa: S102
        for variable in node.content.output_variables:
            assert variable in namespace
