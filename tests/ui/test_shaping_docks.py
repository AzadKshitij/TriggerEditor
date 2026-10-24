"""P1 shaping Config Dock smoke and one undo round trip."""

from __future__ import annotations

import polars as pl
from nodeeditor.node_edge import Edge
from qtpy.QtWidgets import QLabel, QLineEdit

from trigger_designer.core.node_configuration import (
    JoinNodes,
    NodeTypes,
    PreparationNodes,
    TransformNodes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.docks.node_config import ConfigDock
from trigger_designer.qt.node_base import TriggerNode
from trigger_designer.qt.widgets.common import ColumnPicker


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
    (PreparationNodes.RECORD_ID, NodeTypes.PREPARATION),
    (PreparationNodes.SELECT_RECORDS, NodeTypes.PREPARATION),
    (PreparationNodes.FIND_REPLACE, NodeTypes.PREPARATION),
    (PreparationNodes.DATE_HELPER, NodeTypes.PREPARATION),
    (TransformNodes.PIVOT, NodeTypes.TRANSFORM),
    (TransformNodes.UNPIVOT, NodeTypes.TRANSFORM),
    (JoinNodes.RECONCILE, NodeTypes.JOIN),
)


def _node(qtbot, code, family):
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    cls = get_class_from_opcode(code, family)
    node = cls(window.scene)
    frame = pl.DataFrame({"a": [1, 2], "b": ["x", "y"]}).lazy()
    sources = [Source(window.scene, frame) for _ in range(len(node.inputs))]
    for index, source in enumerate(sources):
        Edge(window.scene, source.outputs[0], node.inputs[index])
    node.markDirty(True)
    node.eval()
    dock = ConfigDock()
    qtbot.addWidget(dock)
    dock.updateConfig([node.grNode])
    return window, node, dock


def test_dock_builds_for_every_p1_node(qtbot) -> None:
    for code, family in CASES:
        _window, node, _dock = _node(qtbot, code, family)
        assert node.content._rows, code.name


def test_record_id_dock_edit_and_undo(qtbot) -> None:
    window, node, _dock = _node(
        qtbot, PreparationNodes.RECORD_ID, NodeTypes.PREPARATION
    )
    history = window.scene.history
    history.storeHistory("Baseline")
    field = node.content._widgets["name"]
    assert isinstance(field, QLineEdit)
    field.setText("Item")
    qtbot.wait(350)
    assert node.content.settings["name"] == "Item"
    assert history.canUndo()
    history.undo()
    assert node.content.settings["name"] == "RecordID"
    history.redo()
    assert node.content.settings["name"] == "Item"


def test_record_id_group_picker_updates_without_rebuilding_dock(qtbot) -> None:
    window, node, _dock = _node(
        qtbot, PreparationNodes.RECORD_ID, NodeTypes.PREPARATION
    )
    history = window.scene.history
    history.storeHistory("Baseline")
    picker = node.content._widgets["group_by"]
    assert isinstance(picker, ColumnPicker)

    picker.set_selected(["a"], emit=True)
    assert node.content.settings["group_by"] == ["a"]
    assert node.content._widgets["group_by"] is picker
    assert history.canUndo()

    history.undo()
    assert node.content.settings["group_by"] == []
    assert node.content._widgets["group_by"] is picker
    history.redo()
    assert node.content.settings["group_by"] == ["a"]


def test_select_records_visibility_follows_mode(qtbot) -> None:
    _window, node, dock = _node(
        qtbot, PreparationNodes.SELECT_RECORDS, NodeTypes.PREPARATION
    )
    content = node.content
    assert content._rows["range"].isHidden() is True
    segment = content._widgets["mode"]
    segment._buttons["Range"].click()
    assert content._rows["range"].isHidden() is False
    assert content._rows["n"].isHidden() is True

    summary = [
        label
        for label in dock.findChildren(QLabel)
        if label.objectName() == "ConfigSummary"
    ]
    assert summary
    assert "2 outputs" in summary[0].text()
    assert "S selected" in summary[0].text()


def test_select_records_mode_is_one_step(qtbot) -> None:
    window, node, _dock = _node(
        qtbot, PreparationNodes.SELECT_RECORDS, NodeTypes.PREPARATION
    )
    history = window.scene.history
    history.storeHistory("Baseline")
    segment = node.content._widgets["mode"]
    segment._buttons["Last"].click()
    assert node.content.settings["mode"] == "last_n"
    assert history.canUndo()
    history.undo()
    assert node.content.settings["mode"] == "first_n"
