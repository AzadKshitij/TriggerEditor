"""The Sample node's Config Dock: controls, undo/redo, save and reload."""

from __future__ import annotations

import orjson
import polars as pl

from tests.support.audit_demo import demo_graph
from tests.support.audit_ledger import make_ledger
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.docks.node_config import ConfigDock
from trigger_designer.qt.widgets.common import ColumnPicker, IconButton, TextButton
from trigger_designer.qt.widgets.nodes.Audit.sample import (
    NEW_SEED_TOOLTIP,
    TriggerNode_Sample,
)

FRAME = make_ledger().frame.lazy()


def _dock(qtbot, **settings):
    window, source, node = demo_graph(FRAME, TriggerNode_Sample)
    qtbot.addWidget(window)
    node.content.key_columns = ["je_number"]
    for name, value in settings.items():
        setattr(node.content, name, value)
    node.markDirty(True)
    node.eval()
    dock = ConfigDock()
    qtbot.addWidget(dock)
    dock.updateConfig([node.grNode])
    node.scene.history.storeHistory("Baseline")
    return window, source, node, dock


def _sample_height(node) -> int:
    data = node.value[0]["data"]
    return (data.collect() if isinstance(data, pl.LazyFrame) else data).height


def test_dock_builds_with_the_documented_controls(qtbot) -> None:
    _window, _source, node, dock = _dock(qtbot)
    content = node.content
    assert [content.method_combo.itemData(i) for i in range(4)] == [
        "random",
        "systematic",
        "mus",
        "stratified",
    ]
    assert [content.method_combo.itemText(i) for i in range(4)] == [
        "Random",
        "Systematic",
        "Monetary unit",
        "Stratified",
    ]
    names = [
        p.accessibleName().split(":")[0]
        for p in dock.dock_widget.findChildren(ColumnPicker)
    ]
    assert names == ["Stable key", "Amount"]
    assert content.key_picker.checked() == ["je_number"]
    assert content.size_spin.value() == 100 and content.seed_spin.value() == 42
    assert (content.seed_spin.minimum(), content.seed_spin.maximum()) == (
        0,
        2_147_483_647,
    )
    assert content.percent_spin.suffix() == " %"
    assert (content.percent_spin.minimum(), content.percent_spin.maximum()) == (
        0.01,
        100.0,
    )
    assert "unique per row" in content.key_picker.toolTip()
    assert not dock.dock_widget.findChildren(TextButton)
    button = content.seed_button
    assert button.toolTip() == button.accessibleName() == NEW_SEED_TOOLTIP
    assert (
        "Selected 100 of 2,413 rows (random, seed 42)." in content.summary_label.text()
    )


def test_rows_show_and_hide_with_the_method_and_size_kind(qtbot) -> None:
    _window, _source, node, _dock_unused = _dock(qtbot)
    content = node.content

    def shown(widget) -> bool:
        return not widget.isHidden()

    assert shown(content._size_section) and not shown(content._strata_section)
    assert shown(content._rows["sample_size"]) and not shown(
        content._rows["sample_percent"]
    )

    content.size_kind_control._buttons["Percent"].click()
    assert content.size_kind == "percent"
    assert shown(content._rows["sample_percent"]) and not shown(
        content._rows["sample_size"]
    )

    content.method_combo.setCurrentIndex(3)
    assert content.method == "stratified"
    assert not shown(content._size_section) and shown(content._strata_section)

    node.scene.history.undo()  # back to mus/random with the size block shown again
    assert content.method == "random"
    assert shown(content._size_section) and not shown(content._strata_section)


def test_method_change_is_one_undo_step_and_redraws(qtbot) -> None:
    window, _source, node, _dock_unused = _dock(qtbot)
    content = node.content
    history = window.scene.history
    before = history.controller.count
    content.method_combo.setCurrentIndex(1)
    assert content.method == "systematic"
    assert history.controller.count == before + 1
    assert history.currentText() == "Sample Method Changed"
    assert "systematic" in content.summary_label.text()
    assert "Interval 24.13" in content.summary_label.text()
    history.undo()
    assert content.method == "random" and content.method_combo.currentData() == "random"
    assert "(random," in content.summary_label.text()
    history.redo()
    assert (
        content.method == "systematic"
        and content.method_combo.currentData() == "systematic"
    )


def test_size_count_and_percent_edits(qtbot) -> None:
    window, _source, node, _dock_unused = _dock(qtbot)
    content = node.content
    history = window.scene.history
    before = history.controller.count
    for value in (10, 20, 30):
        content.size_spin.setValue(value)
    assert content.sample_size == 30 and _sample_height(node) == 30
    assert history.controller.count == before + 1  # one burst, one step
    assert history.currentText() == "Sample Size Changed"

    content.size_kind_control._buttons["Percent"].click()
    assert history.currentText() == "Sample Size Kind Changed"
    content.percent_spin.setValue(12.5)
    assert content.sample_percent == 12.5 and _sample_height(node) == 302
    assert history.currentText() == "Sample Percent Changed"
    history.undo()
    history.undo()
    assert content.size_kind == "count" and content.size_kind_control.value() == "Count"
    history.undo()
    assert content.sample_size == 100 and content.size_spin.value() == 100


def test_seed_spin_and_the_new_seed_button(qtbot) -> None:
    window, _source, node, _dock_unused = _dock(qtbot)
    content = node.content
    history = window.scene.history
    first = [o for o in node.value[0]["data"].collect()["je_number"]]

    content.seed_spin.setValue(43)
    assert content.seed == 43 and history.currentText() == "Sample Seed Changed"
    assert [o for o in node.value[0]["data"].collect()["je_number"]] != first
    content.seed_spin.setValue(42)  # the same seed gives the same rows back
    assert [o for o in node.value[0]["data"].collect()["je_number"]] == first

    steps = history.controller.count
    content.seed_button.click()
    assert history.controller.count == steps + 1
    assert history.currentText() == "Sample Seed Changed"
    assert 0 <= content.seed <= 2_147_483_647
    assert content.seed_spin.value() == content.seed
    fresh = content.seed
    history.undo()
    assert content.seed == 42 and content.seed_spin.value() == 42
    history.redo()
    assert content.seed == fresh and content.seed_spin.value() == fresh


def test_key_and_amount_pickers(qtbot) -> None:
    window, _source, node, _dock_unused = _dock(qtbot)
    content = node.content
    history = window.scene.history

    content.amount_picker._toggle_name("amount")
    assert content.amount_column == "amount"
    assert history.currentText() == "Sample Amount Changed"
    assert "Selected 100 of 2,413" in content.summary_label.text()

    content.key_picker._toggle_name("je_number")  # clear: every column is the key
    assert content.key_columns == []
    assert history.currentText() == "Sample Key Changed"
    history.undo()
    assert content.key_columns == ["je_number"]
    assert content.key_picker.checked() == ["je_number"]
    history.undo()
    assert content.amount_column == "" and content.amount_picker.checked() == []


def test_mus_without_an_amount_column_reports_the_error(qtbot) -> None:
    window, _source, node, _dock_unused = _dock(qtbot)
    content = node.content
    content.method_combo.setCurrentIndex(2)
    assert node.isInvalid() and node.current_error.code == "TD-AUDIT-001"
    content.amount_picker._toggle_name("amount")
    assert not node.isInvalid()
    assert _sample_height(node) == 100
    window.scene.history.undo()
    assert node.isInvalid()


def test_strata_lists_commit_after_the_pause_and_undo(qtbot) -> None:
    window, _source, node, _dock_unused = _dock(qtbot, amount_column="amount")
    content = node.content
    history = window.scene.history
    content.method_combo.setCurrentIndex(3)
    assert node.current_error.code == "TD-AUDIT-009"  # one stratum, no sizes yet

    content.sizes_edit.setText("5, 6, all")
    qtbot.waitUntil(lambda: content.band_sizes == [5, 6, -1], timeout=2000)
    content.edges_edit.setText("1000, 10000")
    qtbot.waitUntil(lambda: content.band_edges == [1000.0, 10000.0], timeout=2000)
    assert not node.isInvalid()
    assert _sample_height(node) == 5 + 6 + 830
    assert (
        "Selected 841 of 2,413 rows (stratified, seed 42)."
        in content.summary_label.text()
    )

    content.edges_edit.setText("1000,")  # half typed: the old value stands
    qtbot.wait(450)
    assert content.band_edges == [1000.0, 10000.0]

    history.undo()
    assert content.band_edges == [] and content.edges_edit.text() == ""
    history.undo()
    assert content.band_sizes == [] and content.sizes_edit.text() == ""


def test_undo_does_not_record_its_own_write_back(qtbot) -> None:
    window, _source, node, _dock_unused = _dock(qtbot)
    content = node.content
    history = window.scene.history
    content.seed_spin.setValue(7)
    count = history.controller.count
    history.undo()
    history.redo()
    assert history.controller.count == count and content.seed == 7


def test_dock_rebuild_after_restore_keeps_the_model(qtbot) -> None:
    window, _source, node, dock = _dock(qtbot)
    content = node.content
    content.method_combo.setCurrentIndex(1)
    window.scene.history.undo()
    dock.updateConfig([node.grNode], force=True)
    assert content.method_combo.currentData() == "random"
    assert content.size_spin.value() == 100
    assert dock.dock_widget.findChildren(IconButton)


def test_save_and_reload_keep_every_setting(qtbot, tmp_path) -> None:
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    node = TriggerNode_Sample(window.scene)
    content = node.content
    content.method = "stratified"
    content.seed = 12345
    content.size_kind = "percent"
    content.sample_percent = 12.5
    content.key_columns = ["je_number"]
    content.amount_column = "amount"
    content.band_edges = [1000.0, 10000.0]
    content.band_sizes = [20, 20, -1]
    path = tmp_path / "sample.tds"
    window.scene.saveToFile(str(path))

    saved = orjson.loads(path.read_bytes())
    entry = next(n for n in saved["nodes"] if n["title"] == "Sample")
    assert entry["op"] == "audit.sample"
    assert entry["content"]["seed"] == 12345
    assert entry["content"]["band_sizes"] == [20, 20, -1]

    again = TriggerSubWindow()
    qtbot.addWidget(again)
    assert again.fileLoad(str(path)) is True
    loaded = next(n for n in again.getAllNodes() if n.title == "Sample")
    assert isinstance(loaded, TriggerNode_Sample)
    assert loaded.content.params() == content.params()
    assert (
        loaded.content.output_variable_names()[0] == f"var_sample_{loaded.content.id}"
    )
