"""Select uses the shaping execution system and keeps its table editor."""

from __future__ import annotations

import polars as pl
from nodeeditor.node_edge import Edge
from qtpy.QtCore import Qt

from trigger_designer.core.node_configuration import (
    NodeTypes,
    PreparationNodes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.docks.node_config import ConfigDock
from trigger_designer.qt.helpers.shaping_support import ShapingContent, ShapingNode
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


def test_select_uses_shaping_and_table_edits_are_undoable(qtbot) -> None:
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    frame = pl.DataFrame({"a": [1, 2], "b": ["x", "y"]}).lazy()
    source = Source(window.scene, frame)
    cls = get_class_from_opcode(PreparationNodes.SELECT, NodeTypes.PREPARATION)
    node = cls(window.scene)
    Edge(window.scene, source.outputs[0], node.inputs[0])
    node.markDirty(True)
    live = node.eval()
    assert live is not None and not node.isInvalid()

    content = node.content
    assert isinstance(content, ShapingContent)
    assert isinstance(node, ShapingNode)
    assert content.history is window.scene.history
    assert [column["name"] for column in content.settings["columns"]] == ["a", "b"]
    assert all(column["selected"] for column in content.settings["columns"])
    assert "trigger_designer.core.shaping.select" in content.get_code()

    namespace = {"var_src": frame}
    exec(content.get_code(), {"__name__": "__main__"}, namespace)  # noqa: S102
    generated = namespace[content.output_variables[0]].collect()
    assert generated.equals(live[0]["data"].collect())

    dock = ConfigDock()
    qtbot.addWidget(dock)
    dock.updateConfig([node.grNode])
    assert content.table_widget is not None
    assert content.table_widget.rowCount() == 2
    assert content.table_view is not None

    history = window.scene.history
    history.storeHistory("Baseline")
    content.table_widget.setData(
        content.table_widget.index(0, 0),
        Qt.CheckState.Unchecked.value,
        Qt.CheckStateRole,
    )
    assert content.settings["columns"][0]["selected"] is False
    assert history.canUndo()
    history.undo()
    assert content.settings["columns"][0]["selected"] is True
    assert (
        content.table_widget.index(0, 0).data(Qt.CheckStateRole)
        == Qt.CheckState.Checked
    )

    content.table_widget.setData(
        content.table_widget.index(1, 3), "Bee", Qt.ItemDataRole.EditRole
    )
    assert content.settings["columns"][1]["rename"] == "Bee"
    serialized = content.serialize()
    assert "settings" in serialized
    assert serialized["settings"]["columns"][1]["rename"] == "Bee"
    assert "2 of 2 columns selected" in content.dock_summary()


def test_select_reconciles_missing_and_new_columns(qtbot) -> None:
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    frame = pl.DataFrame({"a": [1], "b": ["x"]}).lazy()
    source = Source(window.scene, frame)
    cls = get_class_from_opcode(PreparationNodes.SELECT, NodeTypes.PREPARATION)
    node = cls(window.scene)
    Edge(window.scene, source.outputs[0], node.inputs[0])
    node.markDirty(True)
    node.eval()
    content = node.content
    dock = ConfigDock()
    qtbot.addWidget(dock)
    dock.updateConfig([node.grNode])

    source._frame = pl.DataFrame({"a": [2], "c": ["y"]}).lazy()
    source.markDirty(True)
    node.markDirty(True)
    node.eval()
    names = [column["name"] for column in content.settings["columns"]]
    assert names == ["a", "b", "c"]
    rows = {row.text: row for row in content.table_widget.rows()}
    assert rows["b"].is_missing is True
    assert rows["c"].checked is True

    content.set_setting("auto_accept_new_columns", False, "Select Auto Accept Changed")
    source._frame = pl.DataFrame({"a": [3], "c": ["z"], "d": [9]}).lazy()
    source.markDirty(True)
    node.markDirty(True)
    node.eval()
    rows = {row.text: row for row in content.table_widget.rows()}
    assert rows["d"].checked is False
