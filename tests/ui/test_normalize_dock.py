"""Normalize uses the shaping form; rules, scope, undo and codegen stay in sync."""

from __future__ import annotations

import polars as pl
from nodeeditor.node_edge import Edge
from qtpy.QtWidgets import QCheckBox

from tests.support.flush import live_value
from trigger_designer.core.node_configuration import (
    NodeTypes,
    PreparationNodes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.docks.node_config import ConfigDock
from trigger_designer.qt.node_base import TriggerNode, upstream_rename_map
from trigger_designer.qt.widgets.common import ColumnPicker, NoWheelComboBox


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
    return pl.DataFrame({" Order ID ": [1, 2], "Customer_Id": [3, 4], "sku": [5, 6]})


def _node(qtbot, frame=None):
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    source = Source(window.scene, (frame or _frame()).lazy())
    cls = get_class_from_opcode(
        PreparationNodes.NORMALIZE_COLUMNS, NodeTypes.PREPARATION
    )
    node = cls(window.scene)
    Edge(window.scene, source.outputs[0], node.inputs[0])
    node.markDirty(True)
    node.eval()
    dock = ConfigDock()
    qtbot.addWidget(dock)
    dock.updateConfig([node.grNode])
    return window, source, node, dock


def _columns(node) -> list[str]:
    return live_value(node)[0]["data"].collect_schema().names()


def test_dock_shows_rule_controls_and_columns(qtbot) -> None:
    _window, _source, node, _dock = _node(qtbot)
    content = node.content
    assert isinstance(content._widgets["trim_whitespace"], QCheckBox)
    assert isinstance(content._widgets["case_modification"], NoWheelComboBox)
    picker = content._widgets["selected_columns"]
    assert isinstance(picker, ColumnPicker)
    assert picker.column_names() == [" Order ID ", "Customer_Id", "sku"]
    assert _columns(node) == ["Order_ID", "Customer_Id", "sku"]


def test_toggling_rules_changes_the_output_schema(qtbot) -> None:
    _window, _source, node, _dock = _node(qtbot)
    content = node.content
    underscore = content._widgets["spaces_to_underscore"]
    underscore.setChecked(False)
    assert content.settings["spaces_to_underscore"] is False
    assert _columns(node) == ["Order ID", "Customer_Id", "sku"]

    case = content._widgets["case_modification"]
    case.setCurrentIndex(case.findData("upper"))
    assert content.settings["case_modification"] == "upper"
    assert _columns(node) == ["ORDER ID", "CUSTOMER_ID", "SKU"]


def test_selection_limits_renames(qtbot) -> None:
    _window, _source, node, _dock = _node(qtbot)
    content = node.content
    case = content._widgets["case_modification"]
    case.setCurrentIndex(case.findData("lower"))
    assert _columns(node) == ["order_id", "customer_id", "sku"]

    picker = content._widgets["selected_columns"]
    picker.set_selected(["Customer_Id"], emit=True)
    assert content.settings["selected_columns"] == ["Customer_Id"]
    assert _columns(node) == [" Order ID ", "customer_id", "sku"]


def test_undo_redoes_rules_and_output(qtbot) -> None:
    window, _source, node, _dock = _node(qtbot)
    content = node.content
    history = window.scene.history
    history.storeHistory("Baseline")
    case = content._widgets["case_modification"]

    case.setCurrentIndex(case.findData("upper"))
    assert _columns(node) == ["ORDER_ID", "CUSTOMER_ID", "SKU"]

    history.undo()
    assert content.settings["case_modification"] == "none"
    assert content._widgets["case_modification"].currentData() == "none"
    assert _columns(node) == ["Order_ID", "Customer_Id", "sku"]

    history.redo()
    assert content.settings["case_modification"] == "upper"
    assert _columns(node) == ["ORDER_ID", "CUSTOMER_ID", "SKU"]


def test_generated_code_matches_live(qtbot) -> None:
    _window, _source, node, _dock = _node(qtbot)
    content = node.content
    content.set_setting("case_modification", "lower", "Normalize Case Changed")
    content.set_setting(
        "selected_columns", ["Customer_Id"], "Normalize Normalize Changed"
    )
    live = live_value(node)[0]["data"].collect()

    namespace = {"var_src": _frame().lazy()}
    exec(content.get_code(), {"__name__": "__main__"}, namespace)  # noqa: S102
    generated = namespace[content.output_variables[0]].collect()
    assert generated.equals(live)


def test_downstream_select_follows_the_rename(qtbot) -> None:
    window, _source, node, _dock = _node(qtbot)
    select_cls = get_class_from_opcode(PreparationNodes.SELECT, NodeTypes.PREPARATION)
    select = select_cls(window.scene)
    Edge(window.scene, node.outputs[0], select.inputs[0])

    mapping = upstream_rename_map(node)
    assert mapping[" Order ID "] == "Order_ID"

    select.content.settings["columns"] = [
        {
            "name": " Order ID ",
            "selected": True,
            "dtype": "String",
            "rename": "",
            "date_format": "",
        }
    ]
    select.content.apply_upstream_renames(mapping)
    assert select.content.settings["columns"][0]["name"] == "Order_ID"


def test_serialize_round_trip(qtbot) -> None:
    window, source, node, _dock = _node(qtbot)
    content = node.content
    content.set_setting("case_modification", "upper", "Normalize Case Changed")
    state = content.serialize()
    assert state["settings"]["case_modification"] == "upper"

    cls = get_class_from_opcode(
        PreparationNodes.NORMALIZE_COLUMNS, NodeTypes.PREPARATION
    )
    fresh = cls(window.scene)
    Edge(window.scene, source.outputs[0], fresh.inputs[0])
    assert fresh.content.deserialize(state) is not False
    fresh.markDirty(True)
    out = fresh.eval()
    assert out is not None and not fresh.isInvalid()
    assert out[0]["data"].collect().equals(live_value(node)[0]["data"].collect())
