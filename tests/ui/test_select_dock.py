"""Select keeps its table while using the shared ConfigContent base."""

from __future__ import annotations

import polars as pl
from nodeeditor.node_edge import Edge

from trigger_designer.core.node_configuration import (
    NodeTypes,
    PreparationNodes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.docks.node_config import ConfigDock
from trigger_designer.qt.helpers.config_content import ConfigContent
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


def test_select_uses_shared_base_and_keeps_table(qtbot) -> None:
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    frame = pl.DataFrame({"a": [1, 2], "b": ["x", "y"]}).lazy()
    source = Source(window.scene, frame)
    cls = get_class_from_opcode(PreparationNodes.SELECT, NodeTypes.PREPARATION)
    node = cls(window.scene)
    Edge(window.scene, source.outputs[0], node.inputs[0])
    node.markDirty(True)
    assert node.eval() is not None

    content = node.content
    assert isinstance(content, ConfigContent)
    assert content.node is node
    assert content.history is window.scene.history
    assert hasattr(content, "evaluate")

    dock = ConfigDock()
    qtbot.addWidget(dock)
    dock.updateConfig([node.grNode])
    assert content.table_view is not None
    assert content.changes["selected_columns"] == ["a", "b"]
    serialized = content.serialize()
    assert "changes" in serialized
    assert "table_data" in serialized
