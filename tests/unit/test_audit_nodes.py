"""The shared Audit base (``Audit/_base.py``) through a tiny demo node.

The five real nodes add their own tests; this file only covers what every audit
node inherits: registration, live/Run agreement, errors, persistence, the undo
write path and the TestSummary hooks.
"""

from __future__ import annotations

import polars as pl
import pytest

from tests.support.audit_demo import (
    DemoContent,
    DemoNode,
    DemoParams,
    demo_graph,
    run_demo,
)
from trigger_designer.core.audit.common import AuditConfigError
from trigger_designer.core.audit.test_summary import TestSummary
from trigger_designer.core.node_configuration import (
    _OPCODE_ENUMS,
    NODE_REGISTRIES,
    AuditNodes,
    NodeTypes,
)
from trigger_designer.qt.design_window import TriggerSubWindow

FRAME = pl.DataFrame(
    {
        "amount": ["10", "(5)", "7,000.50", "abc", None, "9000"],
        "key": ["a", "b", "c", "d", "e", "f"],
    }
).lazy()


def _ready(**settings):
    window, source, node = demo_graph(FRAME)
    for name, value in settings.items():
        setattr(node.content, name, value)
    node.markDirty(True)
    node.eval()
    return window, source, node


def test_family_registration() -> None:
    assert NodeTypes.AUDIT.value == "audit"
    assert [m.name for m in AuditNodes] == [
        "DUPLICATES",
        "GAPS",
        "BENFORD",
        "SAMPLE",
        "RISK_FILTERS",
    ]
    assert [m.value for m in AuditNodes] == [1, 2, 3, 4, 5]
    assert _OPCODE_ENUMS[NodeTypes.AUDIT] is AuditNodes
    assert NodeTypes.AUDIT in NODE_REGISTRIES


def test_helper_modules_stay_out_of_the_startup_sweep() -> None:
    from trigger_designer.qt.widgets.nodes import _LAZY_HELPER_MODULES

    assert {"Audit._base", "Audit.benford_chart"} <= _LAZY_HELPER_MODULES


def test_the_context_menu_has_an_audit_category() -> None:
    from trigger_designer.qt.helpers.context_menu_mixin import ContextMenuMixin

    mixin = ContextMenuMixin()
    mixin.init_context_menu_support()
    assert mixin.nodes_by_type["Audit"] is NODE_REGISTRIES[NodeTypes.AUDIT]


def test_live_value_and_generated_code_agree() -> None:
    _window, source, node = _ready(column="amount", threshold=6.0)
    out = node.value
    assert [o["variable_name"] for o in out] == node.content.output_variable_names()
    live = [o["data"].collect() for o in out]
    assert live[0].height == 3 and live[1].height == 3

    namespace = {"var_src": source.frame}
    exec(node.get_code(), {"__name__": "__main__"}, namespace)  # noqa: S102
    for item, expected in zip(out, live):
        got = namespace[item["variable_name"]]
        got = got.collect() if isinstance(got, pl.LazyFrame) else got
        assert got.equals(expected)
    # The one-row summary is collected eagerly in generated code.
    assert isinstance(namespace[out[2]["variable_name"]], pl.DataFrame)
    summary = live[2].row(0, named=True)
    assert summary["exception_rows"] == 3 and summary["population_rows"] == 6
    assert summary["status"] == "fail" and summary["code"] == "TD-AUDIT-102"


def test_generated_code_uses_a_plain_literal_and_cleans_up() -> None:
    _window, _source, node = _ready(column='it\'s "odd"\\', threshold=1.0)
    code = node.get_code()
    assert "from tests.support.audit_demo import DemoParams, run_demo" in code
    assert f"_ap_{node.content.id} = DemoParams.from_dict(" in code
    assert f"del _ap_{node.content.id}" in code
    namespace = {}
    exec(  # noqa: S102
        code.split("\n", 2)[2].split("\n")[0].replace("_ap_", "ap_", 1),
        {"DemoParams": DemoParams},
        namespace,
    )
    assert namespace[f"ap_{node.content.id}"].column == 'it\'s "odd"\\'
    assert node.get_code() == code  # idempotent


def test_unwired_node_defines_every_output_variable() -> None:
    window = TriggerSubWindow()
    node = DemoNode(window.scene)
    namespace = {}
    exec(node.get_code(), {}, namespace)  # noqa: S102
    for name in node.content.output_variable_names():
        assert isinstance(namespace[name], pl.DataFrame)
    assert len(node.content.output_variable_names()) == 3


def test_misconfigured_node_fails_live_and_in_the_run_code() -> None:
    _window, source, node = _ready()  # no column chosen
    assert node.value is None or node.isInvalid()
    assert node.isInvalid()
    assert node.current_error is not None
    assert node.current_error.code == "TD-AUDIT-001"
    assert "TD-AUDIT-001" in node._node_tooltip()
    # The dock can still list the columns of an input that failed validation.
    assert set(node.content.schema()) == {"amount", "key"}
    with pytest.raises(AuditConfigError) as info:
        exec(node.get_code(), {}, {"var_src": source.frame})  # noqa: S102
    assert info.value.code == "TD-AUDIT-001"

    node.content.column = "amount"
    node.markDirty(True)
    assert node.eval() is not None
    assert not node.isInvalid() and node.current_error is None


def test_a_column_that_vanished_names_itself() -> None:
    _window, _source, node = _ready(column="gone")
    assert node.current_error.code == "TD-AUDIT-002"
    assert "gone" in node.current_error.render_summary()


def test_output_variables_are_declared_for_run_pruning() -> None:
    window, _source, node = _ready(column="amount")
    declared = window._declared_output_variable_names(node)
    assert declared == node.content.output_variable_names()
    unwired = DemoNode(window.scene)
    assert (
        window._declared_output_variable_names(unwired)
        == unwired.content.output_variable_names()
    )


def test_op_id_and_sockets() -> None:
    _window, _source, node = _ready(column="amount")
    assert node.serialize()["op"] == "audit.duplicates"
    assert len(node.outputs) == 3
    assert [s.socket_type for s in node.outputs] == [3, 3, 1]


def test_state_round_trips_through_serialize() -> None:
    _window, _source, node = _ready(column="amount")
    content = node.content
    content.keys = ["key"]
    content.mode = "below"
    content.threshold = 12.5
    content.top = 4
    content.levels = [1000.0, 10000.0]
    content.sizes = [20, -1]
    content.lines = ["a", "b"]
    data = content.serialize()
    assert data["threshold"] == 12.5 and data["levels"] == [1000.0, 10000.0]

    window = TriggerSubWindow()
    other = DemoNode(window.scene)
    other.content.deserialize(dict(data))
    assert other.content.params() == content.params()
    other.content.deserialize({})  # a file saved before any setting existed
    assert other.content.params() == DemoParams()
    assert other.content.keys == [] and other.content.keys is not DemoParams().keys


def test_serialized_lists_are_independent_of_the_defaults() -> None:
    _window, _source, node = _ready()
    node.content.keys.append("x")
    assert DemoContent.PARAMS().keys == []
    assert DemoNode(node.scene).content.keys == []


def test_a_setting_that_shadows_a_widget_attribute_is_refused() -> None:
    from dataclasses import dataclass

    from tests.support.audit_demo import DemoContent as Base

    @dataclass
    class Bad(DemoParams):
        size: int = 0  # QWidget.size() would be clobbered

    class BadContent(Base):
        PARAMS = Bad

    class BadNode(DemoNode):
        content_class = BadContent

    window = TriggerSubWindow()
    with pytest.raises(TypeError, match="size"):
        BadNode(window.scene)


def test_after_execution_sets_the_test_summary() -> None:
    _window, _source, node = _ready(column="amount", threshold=6.0)
    content = node.content
    assert content.test_summary is None
    summary_var = content.summary_variable_name
    assert summary_var == content.output_variable_names()[2]
    frame = node.value[2]["data"].collect()
    content.after_execution({summary_var: frame})
    summary = content.test_summary
    assert isinstance(summary, TestSummary)
    assert summary.test_id == f"audit.demo#{node.id}"
    assert summary.exceptions_var == content.output_variable_names()[0]
    assert summary.exception_rows == 3 and summary.status == "fail"
    assert summary.details == {"unreadable_rows": 1}
    assert summary.parameters["threshold"] == 6.0
    # Not a one-row frame, or no summary variable: nothing changes, nothing raises.
    content.test_summary = None
    content.after_execution({})
    content.after_execution({summary_var: pl.DataFrame({"a": [1, 2]})})
    assert content.test_summary is None


def test_count_collects_the_live_summary_without_touching_undo() -> None:
    _window, _source, node = _ready(column="amount", threshold=6.0)
    content = node.content
    history = node.scene.history
    steps = history.controller.count
    content.count_exceptions()
    assert content.test_summary.exception_rows == 3
    assert history.controller.count == steps


def test_set_setting_records_one_undo_step_and_evaluates_once() -> None:
    window, _source, node = _ready(column="amount", threshold=6.0)
    content = node.content
    history = window.scene.history
    history.storeHistory("Baseline")
    evaluations = []
    node.scene.addNodeEvaluatedListener(lambda n: evaluations.append(n))

    assert content.set_setting("threshold", 100.0, "Demo Threshold Changed") is True
    assert content.threshold == 100.0
    assert evaluations.count(node) == 1  # not once for the edit and once for redo
    assert node.value[0]["data"].collect().height == 2
    assert history.canUndo() and history.currentText() == "Demo Threshold Changed"

    assert content.set_setting("threshold", 100.0, "again") is False  # no real diff
    history.undo()
    assert content.threshold == 6.0
    history.redo()
    assert content.threshold == 100.0


def test_set_setting_is_inert_while_the_model_drives_the_widgets() -> None:
    from trigger_designer.qt.undo.protocol import syncing

    window, _source, node = _ready(column="amount")
    content = node.content
    with syncing(content):
        assert content.set_setting("threshold", 5.0, "x") is False
    with window.scene.history.restoring(is_undo=True):
        assert content.set_setting("threshold", 5.0, "x") is False
    assert content.threshold == 0.0


def test_a_new_setting_makes_the_old_summary_stale() -> None:
    _window, _source, node = _ready(column="amount", threshold=6.0)
    node.content.count_exceptions()
    assert node.content.test_summary is not None
    node.content.set_setting("threshold", 1.0, "Demo Threshold Changed")
    assert node.content.test_summary is None


def test_run_function_is_pure_and_matches_the_node() -> None:
    result = run_demo(FRAME, DemoParams(column="amount", threshold=6.0))
    assert [f.collect().height for f in result.frames[:2]] == [3, 3]
    assert result.summary_index == 2 and len(result.for_run()) == 3
