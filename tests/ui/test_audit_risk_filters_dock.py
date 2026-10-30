"""Risk Filters Config Dock: controls, per-test enabling, undo/redo, save and reload."""

from __future__ import annotations

import orjson
import polars as pl
from qtpy.QtWidgets import QPlainTextEdit, QSpinBox

from tests.support.audit_demo import demo_graph
from trigger_designer.core.audit.risk_filters import LABELS, TEST_IDS
from trigger_designer.core.node_configuration import (
    AuditNodes,
    NodeTypes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.docks.node_config import ConfigDock
from trigger_designer.qt.widgets.common import (
    ColumnPicker,
    ConfigSection,
    IconButton,
    TextButton,
)
from trigger_designer.qt.widgets.nodes.Audit._base import COUNT_TOOLTIP

FRAME = pl.DataFrame(
    {
        "date": ["2024-03-02", "2024-03-04", "2024-12-25", "2024-04-03"],
        "eff": ["2024-03-02", "2024-03-04", "2024-12-25", "2024-03-20"],
        "amount": ["5,000.00", "4,900", "1000", "9999.99"],
        "desc": ["Reversal of accrual", "normal", "Plug entry", "x"],
        "source": ["Manual", "Auto", "m", "AUTO"],
    }
).lazy()


def _cls():
    return get_class_from_opcode(AuditNodes.RISK_FILTERS, NodeTypes.AUDIT)


def _dock(qtbot, **settings):
    window, source, node = demo_graph(FRAME, _cls())
    qtbot.addWidget(window)
    for name, value in settings.items():
        setattr(node.content, name, value)
    node.markDirty(True)
    node.eval()
    dock = ConfigDock()
    qtbot.addWidget(dock)
    dock.updateConfig([node.grNode])
    node.scene.history.storeHistory("Baseline")
    return window, source, node, dock


def _flagged(node) -> int:
    return node.value[0]["data"].collect().height


def test_dock_lists_columns_and_one_section_per_test(qtbot) -> None:
    _window, _source, node, dock = _dock(qtbot, weekend=True, date_column="date")
    pickers = dock.dock_widget.findChildren(ColumnPicker)
    assert [p.accessibleName().split(":")[0] for p in pickers] == [
        "Posting date",
        "Effective date",
        "Amount",
        "Description",
        "Manual flag",
    ]
    titles = [
        s._title.text()
        for s in dock.dock_widget.findChildren(ConfigSection)
        if s._title
    ]
    assert titles == [
        "COLUMNS",
        *[LABELS[t].upper() for t in TEST_IDS],
        "RESULT",
    ]
    assert not dock.dock_widget.findChildren(TextButton)
    assert dock.dock_widget.findChildren(IconButton)
    assert set(node.content.switches) == set(TEST_IDS)


def test_a_new_node_starts_with_every_test_off_and_says_so(qtbot) -> None:
    _window, _source, node, _unused = _dock(qtbot)
    assert not any(sw.isChecked() for sw in node.content.switches.values())
    assert node.isInvalid() and node.current_error.code == "TD-AUDIT-008"
    # Options of an off test are shown but disabled.
    for test in TEST_IDS:
        for row in node.content._test_bodies[test]:
            assert not row.isEnabled()


def test_switch_enables_only_its_own_options_and_keeps_values(qtbot) -> None:
    window, _source, node, _unused = _dock(
        qtbot, date_column="date", weekend=True, holidays=["2024-12-25"]
    )
    content = node.content
    assert all(r.isEnabled() for r in content._test_bodies["weekend"])
    assert not any(r.isEnabled() for r in content._test_bodies["holiday"])

    content.switches["holiday"].setChecked(True)
    assert content.holiday is True
    assert all(r.isEnabled() for r in content._test_bodies["holiday"])
    assert _flagged(node) == 2  # Saturday and 25 December
    assert window.scene.history.currentText() == "Risk Public-holiday posting Changed"

    content.switches["holiday"].setChecked(False)
    assert content.holidays == ["2024-12-25"]  # switching off clears nothing
    assert not any(r.isEnabled() for r in content._test_bodies["holiday"])
    assert content.holidays_edit.toPlainText() == "2024-12-25"


def test_switch_undo_redo_projects_back_onto_the_controls(qtbot) -> None:
    window, _source, node, _unused = _dock(qtbot, date_column="date", weekend=True)
    content = node.content
    history = window.scene.history
    content.switches["round_amount"].setChecked(True)
    content.amount_picker._toggle_name("amount")
    assert content.amount_column == "amount" and content.round_amount
    assert _flagged(node) == 2  # the Saturday (5,000) and 1,000

    history.undo()
    assert content.amount_column == "" and content.amount_picker.checked() == []
    history.undo()
    assert content.round_amount is False
    assert not content.switches["round_amount"].isChecked()
    assert not any(r.isEnabled() for r in content._test_bodies["round_amount"])
    history.redo()
    assert content.switches["round_amount"].isChecked()
    assert all(r.isEnabled() for r in content._test_bodies["round_amount"])


def test_column_pickers_and_optional_effective_date(qtbot) -> None:
    window, _source, node, _unused = _dock(
        qtbot, weekend=False, after_period_end=True, period_end="2024-03-31"
    )
    content = node.content
    assert node.current_error.code == "TD-AUDIT-001"
    content.date_picker._toggle_name("date")
    assert not node.isInvalid() and _flagged(node) == 2  # 2024-12-25 and 2024-04-03
    assert window.scene.history.currentText() == "Risk Date Column Changed"
    content.effective_picker._toggle_name("eff")
    assert content.effective_date_column == "eff" and _flagged(node) == 1
    assert window.scene.history.currentText() == "Risk Effective Column Changed"
    window.scene.history.undo()
    assert content.effective_date_column == ""
    assert content.effective_picker.checked() == [] and _flagged(node) == 2


def test_date_format_combo(qtbot) -> None:
    window, _source, node, _unused = _dock(qtbot, date_column="date", weekend=True)
    content = node.content
    assert content.format_combo.currentData() == "%Y-%m-%d"
    content.format_combo.setCurrentIndex(content.format_combo.findData("%d/%m/%Y"))
    assert content.date_format == "%d/%m/%Y"
    assert _flagged(node) == 0  # ISO text does not read as day/month/year
    assert window.scene.history.currentText() == "Risk Date Format Changed"
    window.scene.history.undo()
    assert content.format_combo.currentData() == "%Y-%m-%d" and _flagged(node) == 1


def test_option_controls_commit_after_the_debounce_as_one_step(qtbot) -> None:
    window, _source, node, _unused = _dock(
        qtbot, amount_column="amount", just_below_limit=True
    )
    content = node.content
    history = window.scene.history
    assert node.current_error.code == "TD-AUDIT-004"  # no limits yet
    before = history.controller.count
    content.limits_edit.setText("5000, 10000")
    qtbot.waitUntil(lambda: content.approval_limits == [5000.0, 10000.0], timeout=2000)
    assert not node.isInvalid() and _flagged(node) == 2  # 4,900 and 9,999.99
    assert history.controller.count == before + 1
    assert history.currentText() == "Risk Approval Limits Changed"

    content.below_spin.setValue(50.0)
    assert content.below_pct == 50.0 and content.below_spin.suffix() == " %"
    content.below_spin.setValue(60.0)
    assert history.controller.count == before + 2  # a spin burst is one step
    history.undo()
    assert content.below_pct == 2.0 and content.below_spin.value() == 2.0
    history.undo()
    assert content.approval_limits == [] and content.limits_edit.text() == ""


def test_lines_controls_and_round_multiple(qtbot) -> None:
    window, _source, node, _unused = _dock(
        qtbot,
        description_column="desc",
        manual_column="source",
        amount_column="amount",
        keyword=True,
        manual_journal=True,
        round_amount=True,
        round_multiple=1000,
    )
    content = node.content
    assert node.current_error.code == "TD-AUDIT-004"  # no keywords yet
    assert isinstance(content.keywords_edit, QPlainTextEdit)
    content.keywords_edit.setPlainText("reversal\n\n PLUG \n")
    qtbot.waitUntil(lambda: content.keywords == ["reversal", "PLUG"], timeout=2000)
    assert not node.isInvalid()
    assert _flagged(node) == 2  # rows 0 and 2

    content.round_spin.setValue(5000)
    assert content.round_multiple == 5000
    history = window.scene.history
    assert history.currentText() == "Risk Round Multiple Changed"
    history.undo()
    assert content.round_multiple == 1000 and content.round_spin.value() == 1000

    content.manual_values_edit.setPlainText("auto")
    qtbot.waitUntil(lambda: content.manual_values == ["auto"], timeout=2000)
    history.undo()
    assert content.manual_values_edit.toPlainText().split("\n")[0] == "manual"


def test_period_end_text_and_a_bad_date_error(qtbot) -> None:
    _window, _source, node, dock = _dock(
        qtbot, date_column="date", after_period_end=True
    )
    content = node.content
    assert node.current_error.code == "TD-AUDIT-006"
    content.period_edit.setText("2024-03-31")
    dock.updateConfig([])  # leaving the dock commits a pending edit
    assert content.period_end == "2024-03-31" and not node.isInvalid()
    assert _flagged(node) == 2


def test_weight_spins_write_the_whole_dict_and_undo(qtbot) -> None:
    window, _source, node, _unused = _dock(qtbot, date_column="date", weekend=True)
    content = node.content
    history = window.scene.history
    spin = content._weight_spins["weekend"]
    assert isinstance(spin, QSpinBox) and (spin.minimum(), spin.maximum()) == (1, 10)
    before = history.controller.count
    spin.setValue(3)
    spin.setValue(4)
    assert content.weights["weekend"] == 4 and content.weights["holiday"] == 1
    assert history.controller.count == before + 1  # a spin burst is one step
    assert history.currentText() == "Risk Weight Changed"
    rows = node.value[0]["data"].collect()
    assert rows["risk_score"].to_list() == [4]
    history.undo()
    assert content.weights["weekend"] == 1 and spin.value() == 1
    history.redo()
    assert spin.value() == 4 and content.weights["weekend"] == 4


def test_undo_does_not_record_its_own_write_back(qtbot) -> None:
    window, _source, node, _unused = _dock(qtbot, date_column="date", weekend=True)
    history = window.scene.history
    node.content._weight_spins["weekend"].setValue(7)
    count = history.controller.count
    history.undo()
    history.redo()
    assert history.controller.count == count
    assert node.content.weights["weekend"] == 7


def test_result_section_counts_exceptions(qtbot) -> None:
    window, _source, node, dock = _dock(qtbot, date_column="date", weekend=True)
    content = node.content
    button = next(
        b
        for b in dock.dock_widget.findChildren(IconButton)
        if b.accessibleName() == COUNT_TOOLTIP
    )
    count = window.scene.history.controller.count
    button.click()
    assert content.summary_label.text() == (
        "WARN: 1 of 4 entries were flagged by at least one risk test."
    )
    assert content.test_summary.details["n_weekend"] == 1
    assert content.test_summary.details["total_score"] == 1
    assert content.test_summary.status == "warn"
    assert window.scene.history.controller.count == count


def test_a_vanished_column_stays_visible_in_its_picker(qtbot) -> None:
    _window, _source, node, _unused = _dock(qtbot, date_column="gone", weekend=True)
    assert node.current_error.code == "TD-AUDIT-002"
    assert node.content.date_picker.checked() == ["gone"]
    node.content.date_picker._toggle_name("date")
    assert node.content.date_column == "date" and not node.isInvalid()


def test_save_and_reload_keeps_every_setting_and_the_op_id(
    qtbot, tmp_path, no_modal_dialogs
) -> None:
    window, _source, node, _unused = _dock(
        qtbot,
        date_column="date",
        effective_date_column="eff",
        amount_column="amount",
        description_column="desc",
        manual_column="source",
        date_format="%Y-%m-%d",
        holiday=True,
        holidays=["2024-12-25"],
        round_amount=True,
        round_multiple=500,
        just_below_limit=True,
        approval_limits=[5000.0],
        below_pct=3.5,
        keyword=True,
        keywords=["reversal"],
        after_period_end=True,
        period_end="2024-03-31",
        manual_journal=True,
        manual_values=["manual", "m"],
        weights={**dict.fromkeys(TEST_IDS, 1), "keyword": 5},
    )
    expected = node.content.params()
    path = tmp_path / "risk.tds"
    window.scene.saveToFile(str(path))
    data = orjson.loads(path.read_bytes())
    assert [n["op"] for n in data["nodes"] if "audit" in n["op"]] == [
        "audit.risk_filters"
    ]

    reloaded = TriggerSubWindow()
    qtbot.addWidget(reloaded)
    assert reloaded.fileLoad(str(path)) is True
    nodes = [n for n in reloaded.getAllNodes() if n.title == "Risk Filters"]
    assert len(nodes) == 1
    assert nodes[0].content.params() == expected
    assert nodes[0].serialize()["op"] == "audit.risk_filters"
    assert nodes[0].content.weights["keyword"] == 5

    # The dock of the reloaded node shows the saved values once data arrives.
    dock = ConfigDock()
    qtbot.addWidget(dock)
    nodes[0].content.incom_data = FRAME
    dock.updateConfig([nodes[0].grNode])
    content = nodes[0].content
    assert content.round_spin.value() == 500 and content.below_spin.value() == 3.5
    assert content.limits_edit.text() == "5000"
    assert content.keywords_edit.toPlainText() == "reversal"
    assert content._weight_spins["keyword"].value() == 5
    assert content.switches["holiday"].isChecked()
    assert content.effective_picker.checked() == ["eff"]
