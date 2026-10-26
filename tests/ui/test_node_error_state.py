"""Live error state, tooltip and badge on a real node."""

from __future__ import annotations

import polars as pl

from trigger_designer.core.errors import ErrorContext, make_error
from trigger_designer.core.node_configuration import (
    IONodes,
    NodeTypes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow


def _node(qtbot):
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    node = get_class_from_opcode(IONodes.FILE_INPUT, NodeTypes.IO)(window.scene)
    return window, node


def test_set_error_sets_tooltip_badge_and_problems(qtbot) -> None:
    window, node = _node(qtbot)
    error = make_error(
        "TD-SYS-001",
        ErrorContext.from_node(node, "live"),
        message="Both inputs must be connected",
    )
    node.set_error(error, "live")
    assert "Both inputs must be connected" in node.grNode.toolTip()
    assert node.grNode._error_badge == "error"
    assert node.current_error is error
    assert window.problems.count() == 1


def test_run_error_wins_then_live_reappears(qtbot) -> None:
    _window, node = _node(qtbot)
    live = make_error("TD-SYS-001", message="live problem")
    run = make_error("TD-RUN-001", seconds="30")
    node.set_error(live, "live")
    node.set_error(run, "run")
    assert node.current_error is run
    assert "30" in node.grNode.toolTip()
    node.clear_error("run")
    assert node.current_error is live


def test_clear_error_clears_tooltip_and_badge(qtbot) -> None:
    _window, node = _node(qtbot)
    node.set_error(make_error("TD-SYS-001", message="bad"), "live")
    node.clear_error()
    assert node.grNode.toolTip() == ""
    assert node.grNode._error_badge == ""


def test_live_eval_translates_an_exception(qtbot) -> None:
    _window, node = _node(qtbot)

    def broken(_inputs):
        raise ValueError("Both inputs must be connected")

    node.processInputs = broken
    node.markDirty(True)
    node.eval()
    assert node.current_error is not None
    assert node.current_error.code == "TD-SYS-001"
    assert "Both inputs must be connected" in node.grNode.toolTip()
    assert node.grNode._error_badge == "error"


def test_successful_eval_clears_the_live_error(qtbot) -> None:
    _window, node = _node(qtbot)
    node.set_error(make_error("TD-SYS-001", message="old"), "live")

    def ok(_inputs):
        return [{"data": pl.DataFrame({"a": [1]}), "variable_name": "x"}]

    node.processInputs = ok
    node.markDirty(True)
    node.eval()
    assert node.current_error is None
    assert node.grNode.toolTip() == ""
    assert node.grNode._error_badge == ""


def test_warning_severity_uses_warning_badge(qtbot) -> None:
    _window, node = _node(qtbot)
    node.set_error(make_error("TD-RUN-004"), "live")
    assert node.grNode._error_badge == "warning"
