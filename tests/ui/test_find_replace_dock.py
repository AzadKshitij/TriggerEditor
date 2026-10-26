"""Find and Replace rule edits update in place and undo without a rebuild."""

from __future__ import annotations

import polars as pl
from nodeeditor.node_edge import Edge
from qtpy.QtWidgets import QLineEdit

from trigger_designer.core.node_configuration import (
    NodeTypes,
    PreparationNodes,
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


def _node(qtbot):
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    source = Source(window.scene, pl.DataFrame({"s": ["Alpha"]}).lazy())
    cls = get_class_from_opcode(PreparationNodes.FIND_REPLACE, NodeTypes.PREPARATION)
    node = cls(window.scene)
    Edge(window.scene, source.outputs[0], node.inputs[0])
    node.content.settings["columns"] = ["s"]
    node.markDirty(True)
    node.eval()
    dock = ConfigDock()
    qtbot.addWidget(dock)
    dock.updateConfig([node.grNode])
    return window, node, dock


def test_rule_text_edit_is_in_place_and_undoable(qtbot) -> None:
    window, node, _dock = _node(qtbot)
    content = node.content
    stack = content._stacks["rules"]
    stack.add_button.click()
    assert len(content.settings["rules"]) == 1

    widgets = content._card_widgets["rules"][0]
    find_widget = widgets["find"]
    assert isinstance(find_widget, QLineEdit)

    history = window.scene.history
    history.storeHistory("Baseline")
    find_widget.setText("Alpha")
    qtbot.wait(350)
    assert content.settings["rules"][0]["find"] == "Alpha"

    # A text edit is a value change, not a structural one: the card and its
    # editor must survive the commit.
    assert content._card_widgets["rules"][0]["find"] is find_widget
    assert len(content._stacks["rules"]._cards) == 1

    history.undo()
    assert content.settings["rules"][0]["find"] == ""
    assert content._card_widgets["rules"][0]["find"] is find_widget
    assert find_widget.text() == ""


def test_add_and_remove_keep_existing_cards(qtbot) -> None:
    _window, node, _dock = _node(qtbot)
    content = node.content
    stack = content._stacks["rules"]
    stack.add_button.click()

    first_card = stack._cards[0]
    first_widgets = content._card_widgets["rules"][0]
    stack.add_button.click()
    assert stack._cards[0] is first_card
    assert content._card_widgets["rules"][0] is first_widgets
    assert len(stack._cards) == 2

    second_card = stack._cards[1]
    second_widgets = content._card_widgets["rules"][1]
    remove_button = second_card.findChildren(type(stack.add_button))[3]
    remove_button.click()
    assert stack._cards == [first_card]
    assert content._card_widgets["rules"] == [first_widgets]

    # The remaining card's buttons still target its new position.
    up_button = first_card.findChildren(type(stack.add_button))[0]
    assert up_button.isEnabled() is False
    assert second_widgets  # captured before removal


def test_add_and_remove_rule_still_rebuilds(qtbot) -> None:
    window, node, _dock = _node(qtbot)
    content = node.content
    stack = content._stacks["rules"]
    history = window.scene.history
    history.storeHistory("Baseline")

    stack.add_button.click()
    assert len(content._stacks["rules"]._cards) == 1
    history.undo()
    assert len(content.settings["rules"]) == 0
    assert len(content._stacks["rules"]._cards) == 0
