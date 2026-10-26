"""Filter uses the shaping runner; mode, builder fields and codegen stay in sync."""

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


def _frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "n": [10, 100, 600, 250],
            "s": ["paid", "pending", "paid", "refunded"],
        }
    )


def _node(qtbot):
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    source = Source(window.scene, _frame().lazy())
    cls = get_class_from_opcode(PreparationNodes.FILTER, NodeTypes.PREPARATION)
    node = cls(window.scene)
    Edge(window.scene, source.outputs[0], node.inputs[0])
    node.markDirty(True)
    node.eval()
    dock = ConfigDock()
    qtbot.addWidget(dock)
    dock.updateConfig([node.grNode])
    return window, source, node, dock


def _outputs(node):
    return node.value[0]["data"].collect(), node.value[1]["data"].collect()


def test_mode_switch_shows_the_right_section(qtbot) -> None:
    _window, _source, node, _dock = _node(qtbot)
    content = node.content
    # Hidden state is what the dock controls; visibility also needs the host.
    assert content.condition_section.isHidden() is False
    assert content.expression_section.isHidden() is True

    content.mode_selector._buttons["Expression"].click()
    assert content.settings["mode"] == "expression"
    assert content.condition_section.isHidden() is True
    assert content.expression_section.isHidden() is False


def test_operation_list_follows_column_dtype(qtbot) -> None:
    _window, _source, node, _dock = _node(qtbot)
    content = node.content
    combo = content.column_selector

    combo.setCurrentIndex(combo.findData("n"))
    operations = (
        content.operation_selector.itemData(i)
        for i in range(content.operation_selector.count())
    )
    assert "In Between" in list(operations)

    combo.setCurrentIndex(combo.findData("s"))
    operations = [
        content.operation_selector.itemData(i)
        for i in range(content.operation_selector.count())
    ]
    assert operations == ["Equals", "Not Equals", "Contains"]


def test_value2_is_visible_only_for_in_between(qtbot) -> None:
    _window, _source, node, _dock = _node(qtbot)
    content = node.content
    content.column_selector.setCurrentIndex(content.column_selector.findData("n"))
    content.operation_selector.setCurrentIndex(
        content.operation_selector.findData("In Between")
    )
    assert content.settings["operation"] == "In Between"
    assert content.value2_row.isHidden() is False

    content.operation_selector.setCurrentIndex(
        content.operation_selector.findData("Equals")
    )
    assert content.value2_row.isHidden() is True


def test_builder_output_and_undo(qtbot) -> None:
    window, _source, node, _dock = _node(qtbot)
    content = node.content
    history = window.scene.history
    content.set_setting("column", "n", "Filter Column Changed")
    content.set_setting("operation", "Greater Than", "Filter Operation Changed")
    content.set_setting("value", "100", "Filter Value Changed")
    history.storeHistory("Baseline")
    content.set_setting("value", "100", "Filter Value Changed")
    assert _outputs(node)[0]["n"].to_list() == [600, 250]

    content.set_setting("value", "600", "Filter Value Changed")
    assert _outputs(node)[0]["n"].to_list() == []
    history.undo()
    assert content.settings["value"] == "100"
    assert content.value_input.text() == "100"
    assert _outputs(node)[0]["n"].to_list() == [600, 250]


def test_expression_validation_reports_an_error(qtbot) -> None:
    _window, _source, node, _dock = _node(qtbot)
    content = node.content
    assert content.validate_expression("[n] > 5") == []
    errors = content.validate_expression("[n] >")
    assert errors and "message" in errors[0]


def test_generated_code_matches_live_builder(qtbot) -> None:
    _window, _source, node, _dock = _node(qtbot)
    content = node.content
    content.set_setting("column", "n", "Filter Column Changed")
    content.set_setting("operation", "In Between", "Filter Operation Changed")
    content.set_setting("value", "0", "Filter Value Changed")
    content.set_setting("value2", "500", "Filter Max value Changed")
    live = _outputs(node)

    namespace = {"var_src": _frame().lazy()}
    exec(content.get_code(), {"__name__": "__main__"}, namespace)  # noqa: S102
    generated = [namespace[name].collect() for name in content.output_variables]
    assert generated[0].equals(live[0])
    assert generated[1].equals(live[1])


def test_generated_code_matches_live_expression(qtbot) -> None:
    _window, _source, node, _dock = _node(qtbot)
    content = node.content
    content.set_setting("mode", "expression", "Filter Mode Changed")
    content.set_setting(
        "expression",
        "[n] in_between (0, 500) AND [s] = 'paid'",
        "Filter Expression Changed",
    )
    live = _outputs(node)

    namespace = {"var_src": _frame().lazy()}
    exec(content.get_code(), {"__name__": "__main__"}, namespace)  # noqa: S102
    generated = [namespace[name].collect() for name in content.output_variables]
    assert generated[0].equals(live[0])
    assert generated[1].equals(live[1])
