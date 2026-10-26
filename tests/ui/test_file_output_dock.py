"""File Output dock: format dropdown, visibility, undo and no live write."""

from __future__ import annotations

import polars as pl
from nodeeditor.node_edge import Edge

from trigger_designer.core.node_configuration import (
    IONodes,
    NodeTypes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.docks.node_config import ConfigDock
from trigger_designer.qt.node_base import TriggerNode
from trigger_designer.qt.widgets.common import NoWheelComboBox


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


def _node(qtbot):
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    source = Source(window.scene, pl.DataFrame({"a": [1, 2]}).lazy())
    cls = get_class_from_opcode(IONodes.FILE_OUTPUT, NodeTypes.IO)
    node = cls(window.scene)
    Edge(window.scene, source.outputs[0], node.inputs[0])
    node.markDirty(True)
    node.eval()
    dock = ConfigDock()
    qtbot.addWidget(dock)
    dock.updateConfig([node.grNode])
    return window, node, dock


def test_format_dropdown_lists_every_format(qtbot) -> None:
    _window, node, _dock = _node(qtbot)
    content = node.content
    combo = content.formatCombo
    assert isinstance(combo, NoWheelComboBox)
    values = [combo.itemData(index) for index in range(combo.count())]
    assert values == [
        "csv",
        "excel",
        "parquet",
        "json",
        "ndjson",
        "ipc",
        "custom_delimited",
    ]
    assert combo.maxVisibleItems() == combo.count()
    assert combo.currentData() == "csv"


def test_delimiter_and_bom_follow_the_format(qtbot) -> None:
    _window, node, _dock = _node(qtbot)
    content = node.content
    assert content.delimiter_row.isHidden() is False
    assert content.bom_row.isHidden() is False

    combo = content.formatCombo
    combo.setCurrentIndex(combo.findData("parquet"))
    assert content.settings["file_format"] == "parquet"
    assert content.delimiter_row.isHidden() is True
    assert content.bom_row.isHidden() is True

    combo.setCurrentIndex(combo.findData("custom_delimited"))
    assert content.delimiter_row.isHidden() is False


def test_editing_never_writes_a_file(qtbot, tmp_path) -> None:
    _window, node, _dock = _node(qtbot)
    content = node.content
    target = tmp_path / "never.csv"
    content.set_setting("filePath", str(target), "File Output Path Changed")
    content.set_setting("delimiter", ";", "File Output Delimiter Changed")
    content.set_setting("file_format", "parquet", "File Output Format Changed")
    assert not target.exists()


def test_format_change_is_undoable(qtbot) -> None:
    window, node, _dock = _node(qtbot)
    content = node.content
    history = window.scene.history
    history.storeHistory("Baseline")
    combo = content.formatCombo
    combo.setCurrentIndex(combo.findData("json"))
    assert content.settings["file_format"] == "json"
    history.undo()
    assert content.settings["file_format"] == "csv"
    assert content.formatCombo.currentData() == "csv"


def test_generated_code_uses_the_core_writer(qtbot) -> None:
    _window, node, _dock = _node(qtbot)
    code = node.get_code()
    assert "trigger_designer.core.shaping.file_output" in code
    assert "write_node" in code
