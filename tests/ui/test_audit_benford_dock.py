"""The Benford node's Config Dock: controls, chart, undo/redo and persistence."""

from __future__ import annotations

import polars as pl
import pytest
from qtpy.QtCore import QPoint
from qtpy.QtGui import QColor
from qtpy.QtTest import QTest

from tests.support.audit_demo import demo_graph
from tests.support.audit_ledger import make_ledger
from trigger_designer.core.audit.benford import BenfordChartData
from trigger_designer.core.node_configuration import (
    AuditNodes,
    NodeTypes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.docks.node_config import ConfigDock
from trigger_designer.qt.theme_manager import get_theme_manager
from trigger_designer.qt.widgets.common import ColumnPicker, IconButton, TextButton
from trigger_designer.qt.widgets.nodes.Audit.benford import (
    TriggerNode_Benford as Benford,
)
from trigger_designer.qt.widgets.nodes.Audit.benford_chart import (
    BenfordChartWidget,
    axis_max,
)

LEDGER = make_ledger().gl.lazy()


def _dock(qtbot, frame=LEDGER, **settings):
    window, source, node = demo_graph(frame, Benford)
    qtbot.addWidget(window)
    for name, value in settings.items():
        setattr(node.content, name, value)
    node.markDirty(True)
    node.eval()
    dock = ConfigDock()
    qtbot.addWidget(dock)
    dock.updateConfig([node.grNode])
    node.scene.history.storeHistory("Baseline")  # the first stamp is not a step
    return window, source, node, dock


def test_node_is_registered_with_three_sockets_and_an_op_id(qtbot) -> None:
    cls = get_class_from_opcode(AuditNodes.BENFORD, NodeTypes.AUDIT)
    assert cls is Benford and cls.node_title == "Benford"
    _window, _source, node, _dock_unused = _dock(qtbot, amount_column="amount")
    assert node.serialize()["op"] == "audit.benford"
    assert [s.socket_type for s in node.outputs] == [3, 1, 3]
    assert len(node.outputs) == 3


def test_dock_sections_and_controls(qtbot) -> None:
    _window, _source, node, dock = _dock(qtbot, amount_column="amount")
    content = node.content
    root = dock.dock_widget
    assert [
        p.accessibleName().split(":")[0] for p in root.findChildren(ColumnPicker)
    ] == ["Column"]
    assert root.findChildren(BenfordChartWidget) == [content.chart]
    assert content.chart.accessibleName() == "Benford chart"
    assert content.digits_control.value() == "First digit"
    assert content.min_spin.value() == 10.0
    assert content.drill_auto_check.isChecked()
    assert not content.drill_list.isEnabled()  # automatic: the list is read-only
    assert not root.findChildren(TextButton)
    assert content.count_button is None  # the summary is live: no Count button
    assert not [b for b in root.findChildren(IconButton) if "Count" in b.toolTip()]


def test_live_summary_chart_and_labels_follow_the_data(qtbot) -> None:
    _window, _source, node, _dock_unused = _dock(qtbot, amount_column="amount")
    content = node.content
    assert content.test_summary is not None  # filled by the live evaluation
    assert content.summary_label.text().startswith(
        "PASS: Mean absolute deviation 0.0036"
    )
    assert content.chi_label.text() == "Chi-square 2.86 (df 8), p = 0.9429"
    data = content.chart.data()
    assert isinstance(data, BenfordChartData) and len(data.digits) == 9
    assert data.flagged == frozenset()
    assert "z" in content.drill_list.checkboxes["1"].text()
    assert "590 rows" in content.drill_list.checkboxes["1"].text()


def test_without_input_the_dock_shows_the_empty_state(qtbot) -> None:
    window, _source, _node, _dock_unused = _dock(qtbot)
    fresh = Benford(window.scene)
    from qtpy.QtWidgets import QVBoxLayout, QWidget

    holder = QWidget()
    layout = QVBoxLayout(holder)
    fresh.content.create_layout(layout)
    assert layout.itemAt(0).widget().objectName() == "EmptyStateLabel"
    assert fresh.content.chart is None


def test_before_a_column_is_chosen_the_chart_is_empty(qtbot) -> None:
    window, _source, node, _dock_unused = _dock(qtbot)
    content = node.content
    assert node.current_error.code == "TD-AUDIT-001"
    assert content.chart.data() is None
    assert content.summary_label.text() == "" and content.chi_label.text() == ""
    history = window.scene.history

    content.column_picker._toggle_name("amount")
    assert content.amount_column == "amount" and not node.isInvalid()
    assert content.chart.data() is not None
    assert history.controller.count == 1
    assert history.currentText() == "Benford Column Changed"
    history.undo()
    assert content.amount_column == "" and content.column_picker.checked() == []
    assert content.chart.data() is None
    history.redo()
    assert content.chart.data() is not None


def test_digit_mode_switches_chart_checklist_and_summary(qtbot) -> None:
    window, _source, node, _dock_unused = _dock(qtbot, amount_column="amount")
    content = node.content
    history = window.scene.history
    content.digits_control._buttons["First two"].click()
    assert content.digits == 2
    assert len(content.chart.data().digits) == 90
    assert len(content.drill_list.checkboxes) == 90
    assert content.summary_label.text().startswith("PASS:")
    assert content.test_summary.test_name == "Benford first two digits"
    assert history.currentText() == "Benford Digits Changed"

    history.undo()
    assert content.digits == 1 and content.digits_control.value() == "First digit"
    assert len(content.chart.data().digits) == 9
    assert len(content.drill_list.checkboxes) == 9
    history.redo()
    assert content.digits == 2 and len(content.drill_list.checkboxes) == 90


def test_minimum_spin_burst_is_one_undo_step(qtbot) -> None:
    window, _source, node, _dock_unused = _dock(qtbot, amount_column="amount")
    content = node.content
    history = window.scene.history
    before = history.controller.count
    for value in (20.0, 50.0, 100.0):
        content.min_spin.setValue(value)
    assert content.min_abs_amount == 100.0
    assert history.controller.count == before + 1
    assert history.currentText() == "Benford Minimum Changed"
    history.undo()
    assert content.min_abs_amount == 10.0 and content.min_spin.value() == 10.0


def test_manual_drill_down_digits_are_sorted_and_undoable(qtbot) -> None:
    window, _source, node, _dock_unused = _dock(qtbot, amount_column="amount")
    content = node.content
    history = window.scene.history

    content.drill_auto_check.setChecked(False)
    assert content.drill_auto is False and content.drill_list.isEnabled()
    assert history.currentText() == "Benford Drill-down Mode Changed"
    assert node.value[2]["data"].collect().height == 0

    boxes = content.drill_list.checkboxes
    boxes["7"].setChecked(True)
    boxes["3"].setChecked(True)
    assert content.drill_digits == [3, 7]
    assert history.currentText() == "Benford Drill-down Digits Changed"
    drill = node.value[2]["data"].collect()
    assert set(drill["benford_digits"]) == {3, 7} and drill.height == 243 + 119

    history.undo()
    assert content.drill_digits == [7] and content.drill_list.checked() == ["7"]
    history.undo()
    assert content.drill_digits == []
    assert not any(b.isChecked() for b in boxes.values())
    history.undo()
    assert content.drill_auto is True and content.drill_auto_check.isChecked()
    assert not content.drill_list.isEnabled()
    history.redo()
    assert content.drill_auto is False and content.drill_list.isEnabled()


def test_undo_does_not_record_its_own_write_back(qtbot) -> None:
    window, _source, node, _dock_unused = _dock(qtbot, amount_column="amount")
    history = window.scene.history
    node.content.min_spin.setValue(25.0)
    count = history.controller.count
    history.undo()
    history.redo()
    assert history.controller.count == count
    assert node.content.min_abs_amount == 25.0


def test_flagged_digits_are_drawn_in_the_danger_colour(qtbot) -> None:
    frame = make_ledger().ap.lazy()
    _window, _source, node, _dock_unused = _dock(qtbot, frame, amount_column="amount")
    chart = node.content.chart
    chart.resize(300, 170)
    data = chart.data()
    assert data.flagged == frozenset({5, 6, 7, 8, 9})
    image = chart.grab().toImage()
    danger = get_theme_manager().color("danger")
    accent = get_theme_manager().color("accent_primary")

    def interior(digit: int) -> QColor:
        rect = chart._bar_rect(data.digits.index(digit))
        return image.pixelColor(int(rect.center().x()), int(rect.bottom()) - 3)

    assert interior(7).name() == danger.name()  # over-represented, flagged
    assert interior(5).name() == danger.name()
    # digit 1 has no AP rows at all: no bar, so the pixel is not either bar colour
    assert interior(1).name() not in (danger.name(), accent.name())


def test_chart_paints_data_empty_state_and_follows_the_theme(qtbot) -> None:
    chart = BenfordChartWidget()
    qtbot.addWidget(chart)
    chart.resize(300, 170)
    assert chart.sizeHint().width() == 300 and chart.sizeHint().height() == 170
    assert chart.minimumHeight() == 170 and chart.hasMouseTracking()

    blank = chart.grab().toImage()
    assert chart.data() is None
    assert (
        len({blank.pixel(x, y) for x in range(0, 300, 7) for y in range(0, 170, 7)})
        <= 3
    )

    digits = tuple(range(1, 10))
    expected = (0.301, 0.176, 0.125, 0.097, 0.079, 0.067, 0.058, 0.051, 0.046)
    chart.set_data(
        BenfordChartData(
            digits, expected, expected, frozenset({2}), (30,) * 9, (1.5,) * 9
        )
    )
    painted = chart.grab().toImage()
    colors = {painted.pixel(x, y) for x in range(0, 300, 3) for y in range(0, 170, 3)}
    assert len(colors) > 6
    assert (
        chart.tooltip_text(0) == "Digit 1: observed 30.1% (30), expected 30.1%, z 1.50"
    )
    assert chart.index_at(chart._bar_rect(4).center().x()) == 4
    assert chart.index_at(1) is None  # inside the axis margin
    QTest.mouseMove(chart, QPoint(120, 60))  # hover must not raise

    # Two-digit mode labels every tenth digit and still paints.
    d2 = tuple(range(10, 100))
    chart.set_data(
        BenfordChartData(
            d2, (0.011,) * 90, (0.011,) * 90, frozenset(), (5,) * 90, (0.0,) * 90
        )
    )
    assert chart.grab().toImage().width() == 300
    assert axis_max(chart.data()) == pytest.approx(0.05)

    # A theme switch repaints through apply_theme (no hard-coded colours).
    chart.apply_theme()
    chart.set_data(None)
    assert chart.data() is None


def test_axis_maximum_is_a_five_percent_step(qtbot) -> None:
    low = BenfordChartData((1,), (0.3,), (0.301,), frozenset(), (1,), (0.0,))
    assert axis_max(low) == pytest.approx(0.35)
    high = BenfordChartData((1,), (0.5,), (0.301,), frozenset(), (1,), (0.0,))
    assert axis_max(high) == pytest.approx(0.55)
    zero = BenfordChartData((1,), (0.0,), (0.0,), frozenset(), (0,), (0.0,))
    assert axis_max(zero) == pytest.approx(0.05)


def test_live_evaluation_is_bounded_by_the_row_limit(qtbot, monkeypatch) -> None:
    import trigger_designer.qt.widgets.nodes.Audit.benford as module

    monkeypatch.setattr(module, "LIVE_ROW_LIMIT", 50)
    _window, _source, node, _dock_unused = _dock(qtbot, amount_column="amount")
    content = node.content
    assert content.last_result.extras["limited"] is True
    assert content.test_summary.population_rows == 50
    assert "Live preview reads the first 50 rows." in content.summary_label.text()
    # The Run code never limits: the generated call has no row_limit.
    assert "row_limit" not in node.get_code()
    namespace = {"var_src": LEDGER}
    exec(node.get_code(), {}, namespace)  # noqa: S102
    assert namespace[content.output_variable_names()[1]]["population_rows"][0] == 2013


def test_save_and_reload_keeps_every_setting(qtbot, tmp_path) -> None:
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    node = Benford(window.scene)
    content = node.content
    content.amount_column = "amount"
    content.digits = 2
    content.min_abs_amount = 0.5
    content.drill_auto = False
    content.drill_digits = [11, 49]
    path = tmp_path / "benford.tds"
    window.scene.saveToFile(str(path))
    saved = next(n for n in window.scene.serialize()["nodes"])
    assert saved["op"] == "audit.benford" and saved["content"]["digits"] == 2

    other = TriggerSubWindow()
    qtbot.addWidget(other)
    assert other.fileLoad(str(path)) is True
    loaded = next(n for n in other.getAllNodes() if n.title == "Benford")
    assert loaded.content.params() == content.params()
    assert loaded.content.params_dict() == {
        "amount_column": "amount",
        "digits": 2,
        "min_abs_amount": 0.5,
        "drill_auto": False,
        "drill_digits": [11, 49],
    }
    # A file saved before any setting existed loads with the defaults.
    loaded.content.deserialize({})
    assert loaded.content.digits == 1 and loaded.content.drill_digits == []


def test_unwired_node_can_be_dropped_and_run(qtbot) -> None:
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    node = Benford(window.scene)
    namespace: dict = {}
    exec(node.get_code(), {}, namespace)  # noqa: S102
    for name in node.content.output_variable_names():
        assert isinstance(namespace[name], pl.DataFrame)
