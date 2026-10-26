"""Load-time validation for folders and databases."""

from __future__ import annotations

from tests.support.input_fixtures import monthly_csvs, write_text
from trigger_designer.core.node_configuration import (
    IONodes,
    NodeTypes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow


def _content(path, file_type: str = "csv", **extra):
    window = TriggerSubWindow()
    node = get_class_from_opcode(IONodes.FILE_INPUT, NodeTypes.IO)(window.scene)
    content = node.content
    content.filePath = str(path)
    content.file_type = file_type
    for key, value in extra.items():
        setattr(content, key, value)
    return window, content


def test_validate_missing_folder_message(tmp_path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    window, content = _content(empty)
    issues = content.validate_loaded_state()
    assert issues
    assert "No files" in issues[0]
    assert str(empty) in issues[0]
    window.close()


def test_validate_reports_differing_files(tmp_path) -> None:
    monthly = monthly_csvs(tmp_path)
    window, content = _content(monthly)
    issues = content.validate_loaded_state()
    assert any("3 files" in issue for issue in issues)
    assert any("differ" in issue for issue in issues)
    window.close()


def test_validate_schema_drift_same_messages_as_legacy(tmp_path) -> None:
    monthly = monthly_csvs(tmp_path)
    window, content = _content(monthly)
    content.schema_snapshot = [{"name": "old_column", "dtype": "String"}]
    issues = content.validate_loaded_state()
    assert "Missing saved columns: old_column" in issues
    assert any(
        issue.startswith("New columns compared to saved workflow") for issue in issues
    )
    window.close()


def test_validate_legacy_schema_drift_messages(tmp_path) -> None:
    source = write_text(tmp_path / "in.csv", "id\n1\n")
    window, content = _content(source)
    assert content._use_legacy_path()
    content.schema_snapshot = [{"name": "id", "dtype": "Int64"}]
    issues = content.validate_loaded_state()
    assert "Column type changes: id (Int64 -> String)" in issues
    window.close()


def test_validate_never_raises_on_bad_database(tmp_path) -> None:
    broken = write_text(tmp_path / "broken.sqlite", "not a database")
    window, content = _content(broken, "sqlite", db_mode="table", db_table="sales")
    issues = content.validate_loaded_state()
    assert issues
    window.close()
