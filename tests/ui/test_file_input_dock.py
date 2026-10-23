"""Config Dock behaviour and undo wiring for File Input."""

from __future__ import annotations

from pathlib import Path

import pytest
from qtpy.QtCore import QPoint
from qtpy.QtWidgets import QWidget

from tests.support.input_fixtures import (
    monthly_csvs,
    multi_sheet_xlsx,
    sqlite_db,
)
from trigger_designer.core.node_configuration import (
    IONodes,
    NodeTypes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.docks.node_config import ConfigDock
from trigger_designer.qt.widgets.common import IconButton


def _graph(qtbot, path: str = "", file_type: str = "csv", **extra):
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    node = get_class_from_opcode(IONodes.FILE_INPUT, NodeTypes.IO)(window.scene)
    content = node.content
    content.filePath = path
    content.file_type = file_type
    for key, value in extra.items():
        setattr(content, key, value)
    dock = ConfigDock()
    qtbot.addWidget(dock)
    dock.updateConfig([node.grNode])
    return window, node, content, dock


def _source_file(tmp_path) -> str:
    source = tmp_path / "in.csv"
    source.write_text("id\n1\n", encoding="utf-8")
    return str(source)


def test_dock_builds_for_empty_node(qtbot) -> None:
    _window, _node, content, _dock = _graph(qtbot)
    assert content.source_section.isHidden() is False
    assert content.files_section.isHidden() is True
    assert content.settings_section.isHidden() is True
    assert content.db_section.isHidden() is True


def test_folder_pick_shows_files_section_and_table(qtbot, tmp_path) -> None:
    monthly = monthly_csvs(tmp_path)
    _window, node, content, _dock = _graph(qtbot)
    content._choose_folder(str(monthly))
    assert content.files_section.isHidden() is False
    assert content.filesTable.model().rowCount() == 3
    statuses = [content.filesTable.model().item(row, 1).text() for row in range(3)]
    assert any("+1 column" in status for status in statuses)
    chips, _label = content.dock_context()
    texts = [text for text, _tone in chips]
    assert "csv" in texts
    assert "3 files" in texts
    assert any("differ" in text for text in texts)
    assert node.isInvalid() is False
    assert content.last_report is not None
    assert content.last_report.differing_files()


def test_visibility_matrix(qtbot, tmp_path) -> None:
    source = _source_file(tmp_path)
    _window, _node, content, _dock = _graph(qtbot, source)
    content._apply_visibility()
    assert content.delimiter_row.isHidden() is False
    assert content.encoding_row.isHidden() is False
    assert content.sheet_mode_row.isHidden() is True
    assert content.nested_row.isHidden() is True
    assert content.db_section.isHidden() is True
    assert content.files_section.isHidden() is True

    content.file_type = "parquet"
    content._apply_visibility()
    assert content.delimiter_row.isHidden() is True
    assert content.as_text_widget.isHidden() is False

    content.file_type = "json"
    content._apply_visibility()
    assert content.nested_row.isHidden() is False

    content.file_type = "excel"
    content._apply_visibility()
    assert content.sheet_mode_row.isHidden() is False
    assert content.selected_sheet_row.isHidden() is False
    assert content.sheets_row.isHidden() is True

    content.sheet_mode = "chosen"
    content._apply_visibility()
    assert content.selected_sheet_row.isHidden() is True
    assert content.sheets_row.isHidden() is False

    content.file_type = "sqlite"
    content._apply_visibility()
    assert content.db_section.isHidden() is False
    assert content.db_table_row.isHidden() is False
    assert content.db_query_row.isHidden() is True


def test_combo_popup_opens_at_the_combo(qtbot, tmp_path) -> None:
    """Dock-owned children: a combo created under the node content opened at
    (1, 1) instead of under the field."""
    _window, _node, content, dock = _graph(qtbot, _source_file(tmp_path))
    dock.resize(320, 600)
    dock.show()
    qtbot.wait(50)
    combo = content.typeCombo
    origin = combo.mapToGlobal(QPoint(0, 0))
    combo.showPopup()
    qtbot.wait(50)
    popup = combo.view().window()
    popup_origin = popup.mapToGlobal(QPoint(0, 0))
    combo.hidePopup()
    assert abs(popup_origin.x() - origin.x()) <= 2
    assert abs(popup_origin.y() - origin.y()) <= 2


def test_buttons_have_tooltip_and_accessible_name(qtbot, tmp_path) -> None:
    _window, _node, _content, dock = _graph(qtbot, _source_file(tmp_path))
    buttons = dock.findChildren(IconButton)
    assert buttons
    for button in buttons:
        assert button.toolTip()
        assert button.accessibleName()
    for widget in dock.findChildren(QWidget):
        assert widget.styleSheet() == ""


def test_no_qicon_fromtheme() -> None:
    source = Path(
        "src/trigger_designer/qt/widgets/nodes/InOut/file_input.py"
    ).read_text(encoding="utf-8")
    assert "fromTheme" not in source


def test_path_edit_debounced(qtbot, tmp_path) -> None:
    source = _source_file(tmp_path)
    window, node, content, _dock = _graph(qtbot)
    history = window.scene.history
    baseline = history.controller.count

    calls: list[int] = []
    original = node.eval

    def counting_eval(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    node.eval = counting_eval
    for _index in range(5):
        content.filePathEdit.setText(source)
    qtbot.wait(420)
    assert len(calls) == 1
    assert history.controller.count == baseline + 1
    assert content.filePath == source


def test_writeback_does_not_rerecord(qtbot, tmp_path) -> None:
    source = _source_file(tmp_path)
    window, _node, content, _dock = _graph(qtbot, source)
    history = window.scene.history
    history.storeHistory("Baseline")
    content.limitSpin.setValue(5)
    count = history.controller.count
    assert count == 1
    history.undo()
    assert content.record_limit == 0
    assert history.controller.count == count
    assert content.limitSpin.value() == 0


@pytest.mark.parametrize(
    ("widget", "new_value", "model", "old_value"),
    [
        ("recursiveCheck", True, "recursive", False),
        ("orderCombo", "modified", "file_order", "name"),
        ("schemaCombo", "error", "schema_mismatch", "union"),
        ("outputFilenameCheckBox", True, "output_filename_as_field", False),
        ("encodingCombo", "utf8-lossy", "encoding", "utf8"),
        ("sheetModeCombo", "all", "sheet_mode", "one"),
        ("limitSpin", 5, "record_limit", 0),
        ("asTextCheck", True, "read_as_text", False),
        ("dbModeCombo", "query", "db_mode", "table"),
        ("fileNameValueCombo", "path", "file_name_value", "name"),
    ],
)
def test_undo_redo_each_setting(
    qtbot, tmp_path, widget, new_value, model, old_value
) -> None:
    source = _source_file(tmp_path)
    window, _node, content, dock = _graph(qtbot, source)
    history = window.scene.history
    history.storeHistory("Baseline")
    control = getattr(content, widget)
    if hasattr(control, "findData") and not hasattr(control, "isChecked"):
        control.setCurrentIndex(control.findData(new_value))
    elif hasattr(control, "isChecked"):
        control.setChecked(new_value)
    else:
        control.setValue(new_value)

    assert getattr(content, model) == new_value
    history.undo()
    assert getattr(content, model) == old_value
    dock.updateConfig([content.node.grNode], force=True)
    history.redo()
    assert getattr(content, model) == new_value


def test_text_setting_debounced_and_undoable(qtbot, tmp_path) -> None:
    source = _source_file(tmp_path)
    window, _node, content, _dock = _graph(qtbot, source)
    history = window.scene.history
    history.storeHistory("Baseline")
    content.fileNameColumnEdit.setText("Src")
    qtbot.wait(420)
    assert content.file_name_column_name == "Src"
    assert history.controller.count == 1
    history.undo()
    assert content.file_name_column_name == "FileName"
    assert content.fileNameColumnEdit.text() == "FileName"


def test_folder_pick_is_one_undo_step(qtbot, tmp_path) -> None:
    monthly = monthly_csvs(tmp_path)
    window, _node, content, _dock = _graph(qtbot)
    history = window.scene.history
    history.storeHistory("Baseline")
    content._choose_folder(str(monthly))
    assert content.filePath == str(monthly)
    assert content.output_filename_as_field is True
    assert history.controller.count == 1
    history.undo()
    assert content.filePath == ""
    assert content.file_type == "csv"
    assert content.output_filename_as_field is False


def test_excel_sheets_checklist_chosen_mode(qtbot, tmp_path) -> None:
    book = multi_sheet_xlsx(tmp_path)
    _window, _node, content, _dock = _graph(
        qtbot, str(book), "excel", sheet_mode="chosen"
    )
    content._refresh_sheets()
    content._sync_widgets_from_model()
    assert set(content.sheetsChecklist.checkboxes) == {"Jan", "Feb"}
    content.sheetsChecklist.set_all_checked(False)
    content.sheetsChecklist.checkboxes["Feb"].setChecked(True)
    assert content.selected_sheets == ["Feb"]


def test_db_table_combo_and_query_edit(qtbot, tmp_path) -> None:
    database = sqlite_db(tmp_path)
    _window, _node, content, _dock = _graph(qtbot, str(database), "sqlite")
    content._refresh_db_tables()
    content._sync_widgets_from_model()
    tables = [
        content.dbTableCombo.itemText(index)
        for index in range(content.dbTableCombo.count())
    ]
    assert tables == ["big", "sales"]

    content.dbModeCombo.setCurrentIndex(content.dbModeCombo.findData("query"))
    assert content.db_mode == "query"
    assert content.db_query_row.isHidden() is False
    content.dbQueryEdit.setPlainText("SELECT * FROM sales")
    qtbot.wait(420)
    assert content.db_query == "SELECT * FROM sales"


def test_db_source_defaults_a_table_for_run(qtbot, tmp_path) -> None:
    database = sqlite_db(tmp_path)
    _window, _node, content, _dock = _graph(qtbot)
    content._choose_file(str(database))
    assert content.file_type == "sqlite"
    assert content.db_mode == "table"
    assert content.db_table in {"big", "sales"}
    spec = content.source_spec()
    assert spec["db_table"] == content.db_table
    assert content._load_via_builder() is True
    assert content.data.collect().height > 0


def test_db_table_defaults_without_the_dock(qtbot, tmp_path) -> None:
    database = sqlite_db(tmp_path)
    _window, _node, content, _dock = _graph(qtbot)
    content.filePath = str(database)
    content.file_type = "sqlite"
    content.db_mode = "table"
    content.db_table = ""
    assert content._load_via_builder() is True
    assert content.db_table in {"big", "sales"}
    assert content.data.collect().height > 0


def test_error_tooltip_for_missing_folder(qtbot, tmp_path) -> None:
    empty = tmp_path / "empty_folder"
    empty.mkdir()
    _window, node, content, _dock = _graph(qtbot)
    content._choose_folder(str(empty))
    assert node.isInvalid() is True
    assert str(empty) in node.grNode.toolTip()
