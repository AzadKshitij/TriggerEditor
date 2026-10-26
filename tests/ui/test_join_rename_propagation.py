"""Join keeps mapping and output selection through upstream renames."""

from __future__ import annotations

import polars as pl
from nodeeditor.node_edge import Edge

from trigger_designer.core.node_configuration import (
    JoinNodes,
    NodeTypes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.node_base import TriggerNode


class Source(TriggerNode):
    node_title = "Source"

    def __init__(self, scene, frame, name: str) -> None:
        self._frame = frame
        self._name = name
        super().__init__(scene, inputs=[], outputs=[3])
        self.value = [{"data": frame, "variable_name": name}]
        self.markDirty(False)
        self.markInvalid(False)

    def evalImplementation(self):
        self.value = [{"data": self._frame, "variable_name": self._name}]
        self.markDirty(False)
        self.markInvalid(False)
        return self.value


def _node():
    window = TriggerSubWindow()
    left = Source(window.scene, pl.DataFrame({"id": [1], "a": [2]}).lazy(), "var_left")
    right = Source(
        window.scene, pl.DataFrame({"rid": [1], "b": [3]}).lazy(), "var_right"
    )
    cls = get_class_from_opcode(JoinNodes.JOIN, NodeTypes.JOIN)
    node = cls(window.scene)
    Edge(window.scene, left.outputs[0], node.inputs[0])
    Edge(window.scene, right.outputs[0], node.inputs[1])
    node.content.settings.update(
        {
            "mapping_data": [{"left_column": "id", "right_column": "rid"}],
            "selected_columns": [{"name": "id", "source": "L"}],
        }
    )
    node.markDirty(True)
    node.eval()
    return window, node


def test_upstream_rename_updates_mapping_and_selection() -> None:
    _window, node = _node()
    content = node.content
    # The upstream now publishes the renamed column; the stored config still
    # references the old name.
    content.frames[0] = pl.DataFrame({"new_id": [1], "a": [2]}).lazy()
    changed = content.apply_upstream_renames({"id": "new_id"}, {})
    assert changed is True
    assert content.settings["mapping_data"] == [
        {"left_column": "new_id", "right_column": "rid"}
    ]
    assert content.settings["selected_columns"][0]["name"] == "new_id"


def test_auto_accept_adds_arrivals_and_keeps_unchecked_out() -> None:
    _window, node = _node()
    content = node.content
    content.settings.update(
        {
            "selected_columns": [{"name": "id", "source": "L"}],
            "known_columns": [
                {"name": "id", "source": "L"},
                {"name": "a", "source": "L"},
            ],
        }
    )
    content.compute()
    selected = {
        (entry["name"], entry["source"])
        for entry in content.settings["selected_columns"]
    }
    assert ("b", "R") in selected
    assert ("a", "L") not in selected


def test_serialize_keeps_settings() -> None:
    window, node = _node()
    content = node.content
    content.set_setting("auto_accept_new_columns", False, "Join Auto Accept Changed")
    state = content.serialize()
    assert state["settings"]["auto_accept_new_columns"] is False

    cls = get_class_from_opcode(JoinNodes.JOIN, NodeTypes.JOIN)
    fresh = cls(window.scene)
    assert fresh.content.deserialize(state) is not False
    assert fresh.content.settings["auto_accept_new_columns"] is False
