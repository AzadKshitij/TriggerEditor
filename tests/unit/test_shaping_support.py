"""Optional inputs and the shaping scaffold contract."""

from __future__ import annotations

import polars as pl
from nodeeditor.node_edge import Edge

from trigger_designer.core.node_configuration import (
    NodeTypes,
    PreparationNodes,
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


class OptionalProbe(TriggerNode):
    node_title = "Optional probe"
    optional_inputs = frozenset({1})

    def __init__(self, scene) -> None:
        self.received = None
        super().__init__(scene, inputs=[1, 1], outputs=[3])

    def processInputs(self, input_values):
        self.received = input_values
        first = input_values[0][0]
        return [{"data": first["data"], "variable_name": "out"}]


class RequiredProbe(OptionalProbe):
    optional_inputs = frozenset()


def test_optional_input_appends_none_and_stays_valid() -> None:
    window = TriggerSubWindow()
    source = Source(window.scene, pl.DataFrame({"a": [1]}).lazy())
    node = OptionalProbe(window.scene)
    Edge(window.scene, source.outputs[0], node.inputs[0])
    node.markDirty(True)
    out = node.eval()
    assert out is not None
    assert not node.isInvalid()
    assert node.received[1] is None


def test_required_input_still_fails() -> None:
    window = TriggerSubWindow()
    source = Source(window.scene, pl.DataFrame({"a": [1]}).lazy())
    node = RequiredProbe(window.scene)
    Edge(window.scene, source.outputs[0], node.inputs[0])
    node.markDirty(True)
    assert node.eval() is None
    assert node.isInvalid()


def test_settings_roundtrip_and_defaults() -> None:
    window = TriggerSubWindow()
    cls = get_class_from_opcode(PreparationNodes.RECORD_ID, NodeTypes.PREPARATION)
    node = cls(window.scene)
    content = node.content
    content.settings["name"] = "Item"
    state = content.serialize()
    assert state["settings"]["name"] == "Item"
    content.settings = {}
    content.deserialize({"settings": {"name": "Other"}})
    assert content.settings["name"] == "Other"
    assert content.settings["start"] == 1
