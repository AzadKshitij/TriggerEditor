"""Count has no configuration, and its dock still evaluates live."""

from __future__ import annotations

import polars as pl
from nodeeditor.node_edge import Edge

from trigger_designer.core.node_configuration import (
    NodeTypes,
    TransformNodes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.docks.node_config import ConfigDock
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


def _node(qtbot, frame):
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    source = Source(window.scene, frame)
    cls = get_class_from_opcode(TransformNodes.COUNT_RECORDS, NodeTypes.TRANSFORM)
    node = cls(window.scene)
    Edge(window.scene, source.outputs[0], node.inputs[0])
    node.markDirty(True)
    node.eval()
    dock = ConfigDock()
    qtbot.addWidget(dock)
    dock.updateConfig([node.grNode])
    return window, source, node, dock


def test_count_dock_builds_with_a_read_only_note(qtbot) -> None:
    _window, _source, node, _dock = _node(qtbot, pl.DataFrame({"a": [1, 2]}).lazy())
    content = node.content
    assert content._widgets == {}
    assert list(content._rows) == ["_note"]
    assert "row count" in content.dock_summary()


def test_count_recomputes_after_an_upstream_change(qtbot) -> None:
    _window, source, node, _dock = _node(qtbot, pl.DataFrame({"a": [1, 2]}).lazy())
    first = node.value[0]["data"].collect()
    assert first["Count"].to_list() == [2]

    source._frame = pl.DataFrame({"a": [1, 2, 3, 4]}).lazy()
    source.markDirty(True)
    node.markDirty(True)
    node.eval()
    second = node.value[0]["data"].collect()
    assert second["Count"].to_list() == [4]
