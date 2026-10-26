"""File Input state, defaults and relative-path tests."""

from __future__ import annotations

import os
import shutil

import orjson

from trigger_designer.core.input_source import SOURCE_KEYS
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.widgets.nodes.InOut.file_input import FileInputContent

LEGACY_STATE = {
    "filePath": "",
    "file_type": "csv",
    "record_limit": 0,
    "output_filename_as_field": False,
    "delimiter": ",",
    "first_row_contains_field_names": True,
    "selected_sheet": "",
    "available_sheets": [],
    "start_row": 1,
    "schema_snapshot": [],
    "file_metadata": {},
}


def _content(path: str = "") -> tuple[TriggerSubWindow, FileInputContent]:
    window = TriggerSubWindow()
    # Build the node through the registered class so the content has a scene.
    from trigger_designer.core.node_configuration import (
        IONodes,
        NodeTypes,
        get_class_from_opcode,
    )

    node = get_class_from_opcode(IONodes.FILE_INPUT, NodeTypes.IO)(window.scene)
    content = node.content
    content.filePath = path
    return window, content


def _legacy_content(path: str) -> FileInputContent:
    content = FileInputContent.__new__(FileInputContent)
    content.filePath = path
    content.id = 7
    content.preview_rows = 10
    content.data = None
    content.variable_name = "var_file_input_7"
    content._missing_file_attempts = {}
    content.file_type = "csv"
    content.record_limit = 0
    content.output_filename_as_field = False
    content.delimiter = ","
    content.first_row_contains_field_names = True
    content.selected_sheet = ""
    content.available_sheets = []
    content.start_row = 1
    content.schema_snapshot = []
    content.file_metadata = {}
    return content


def test_new_keys_have_defaults_for_legacy_dict() -> None:
    content = _legacy_content("")
    content.deserialize_content_state(dict(LEGACY_STATE))
    assert content.input_schema_version == 1
    assert content.filePathRel == ""
    assert content.file_name_column_name == "FileName"
    assert content.file_name_value == "name"
    assert content.include_patterns == []
    assert content.exclude_patterns == ["~$*", ".*", "Thumbs.db", "desktop.ini"]
    assert content.recursive is False
    assert content.file_order == "name"
    assert content.schema_mismatch == "union"
    assert content.on_file_error == "stop"
    assert content.max_files == 10000
    assert content.encoding == "utf8"
    assert content.read_as_text is False
    assert content.json_nested == "text"
    assert content.sheet_mode == "one"
    assert content.selected_sheets == []
    assert content.add_sheet_name_column is False
    assert content.sheet_name_column_name == "SheetName"
    assert content.db_mode == "table"
    assert content.db_table == ""
    assert content.db_query == ""


def test_serialize_writes_schema_version_2_and_all_keys(tmp_path) -> None:
    source = tmp_path / "in.csv"
    source.write_text("id\n1\n", encoding="utf-8")
    window, content = _content(str(source))
    state = content.serialize()
    assert state["input_schema_version"] == 2
    assert state["filePath"] == str(source)
    assert {
        "filePath",
        "filePathRel",
        "input_schema_version",
        "file_type",
        "record_limit",
        "output_filename_as_field",
        "delimiter",
        "first_row_contains_field_names",
        "selected_sheet",
        "available_sheets",
        "start_row",
        "schema_snapshot",
        "file_metadata",
    } <= set(state)
    window.close()


def test_file_metadata_single_file_legacy_shape(tmp_path) -> None:
    source = tmp_path / "in.csv"
    source.write_text("id\n1\n", encoding="utf-8")
    window, content = _content(str(source))
    metadata = content.serialize()["file_metadata"]
    assert metadata == {
        "size_bytes": source.stat().st_size,
        "modified_time": int(source.stat().st_mtime),
    }
    window.close()


def test_serialize_does_no_file_reads(tmp_path, monkeypatch) -> None:
    source = tmp_path / "in.csv"
    source.write_text("id\n1\n", encoding="utf-8")
    window, content = _content(str(source))

    def fail(*_args, **_kwargs):
        raise AssertionError("serialize must not read the file")

    monkeypatch.setattr("polars.scan_csv", fail)
    monkeypatch.setattr("polars.read_excel", fail)
    monkeypatch.setattr("fastexcel.read_excel", fail)
    state = content.serialize()
    assert state["filePath"] == str(source)
    window.close()


def test_relative_path_written_and_preferred_on_load(tmp_path) -> None:
    source = tmp_path / "data" / "a.csv"
    source.parent.mkdir()
    source.write_text("id\n1\n", encoding="utf-8")
    workflow_dir = tmp_path / "proj"
    workflow_dir.mkdir()
    window, content = _content(str(source))
    window.scene.filename = str(workflow_dir / "wf.tds")
    state = content.serialize()
    assert state["filePathRel"] == "../data/a.csv"

    moved = tmp_path.parent / f"{tmp_path.name}_moved"
    shutil.copytree(tmp_path, moved)
    try:
        moved_source = moved / "data" / "a.csv"
        window2, content2 = _content(str(source))
        window2.scene.filename = str(moved / "proj" / "wf.tds")
        content2.deserialize(
            {"filePath": str(source), "filePathRel": "../data/a.csv"}, {}
        )
        assert content2.filePath == str(moved_source.resolve())
    finally:
        shutil.rmtree(moved, ignore_errors=True)
    window.close()
    window2.close()


def test_absolute_fallback_when_relative_missing(tmp_path) -> None:
    source = tmp_path / "a.csv"
    source.write_text("id\n1\n", encoding="utf-8")
    window, content = _content(str(source))
    window.scene.filename = str(tmp_path / "wf.tds")
    content.deserialize({"filePath": str(source), "filePathRel": "gone/a.csv"}, {})
    assert content.filePath == str(source)
    window.close()


def test_unsaved_workflow_has_empty_rel(tmp_path) -> None:
    source = tmp_path / "a.csv"
    source.write_text("id\n1\n", encoding="utf-8")
    window, content = _content(str(source))
    state = content.serialize()
    assert state["filePathRel"] == ""
    window.close()


def test_save_as_to_other_folder_uses_target_dir(tmp_path) -> None:
    source = tmp_path / "data" / "a.csv"
    source.parent.mkdir()
    source.write_text("id\n1\n", encoding="utf-8")
    window, _content_obj = _content(str(source))
    old = tmp_path / "old"
    old.mkdir()
    window.scene.filename = str(old / "wf.tds")
    target = tmp_path / "new"
    target.mkdir()
    window.scene.saveToFile(str(target / "wf.tds"))
    raw = orjson.loads((target / "wf.tds").read_bytes())
    file_input_content = next(
        node["content"] for node in raw["nodes"] if node.get("op") == "input.file_input"
    )
    assert file_input_content["filePathRel"] == "../data/a.csv"
    window.close()


def test_old_tds_without_new_keys_loads(tmp_path) -> None:
    window, content = _content("")
    content.deserialize(dict(LEGACY_STATE), {})
    assert content.file_type == "csv"
    assert content.input_schema_version == 1
    assert content.sheet_mode == "one"
    window.close()


def test_source_spec_is_json_safe_and_complete(tmp_path) -> None:
    source = tmp_path / "a.csv"
    source.write_text("id\n1\n", encoding="utf-8")
    window, content = _content(str(source))
    spec = content.source_spec()
    assert set(spec) == set(SOURCE_KEYS)
    assert orjson.loads(orjson.dumps(spec))["filePath"] == str(source)
    window.close()


def test_legacy_path_selection_matrix(tmp_path) -> None:
    source = tmp_path / "a.csv"
    source.write_text("id\n1\n", encoding="utf-8")
    window, content = _content(str(source))
    assert content._use_legacy_path() is True
    for key, value in (
        ("encoding", "utf8-lossy"),
        ("read_as_text", True),
        ("file_name_column_name", "Src"),
        ("file_name_value", "path"),
        ("sheet_mode", "all"),
        ("exclude_patterns", []),
        ("recursive", True),
    ):
        original = getattr(content, key)
        setattr(content, key, value)
        assert content._use_legacy_path() is False, key
        setattr(content, key, original)

    content.filePath = str(tmp_path)
    assert content._use_legacy_path() is False
    window.close()


def test_class_defaults_support_new_instances() -> None:
    content = _legacy_content("")
    assert content.exclude_patterns == ["~$*", ".*", "Thumbs.db", "desktop.ini"]
    assert content.include_patterns == []
    assert content.db_mode == "table"


def test_workflow_dir_helper_uses_scene_filename(tmp_path) -> None:
    from trigger_designer.qt.widgets.nodes.InOut.file_input import _workflow_dir

    class Scene:
        filename = str(tmp_path / "wf.tds")

    assert _workflow_dir(Scene()) == str(tmp_path)
    assert os.path.isdir(_workflow_dir(Scene()))
