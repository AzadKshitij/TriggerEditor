#!/usr/bin/env python3

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)
SRC_PATH = sys.path[0]

import polars as pl
from qtpy.QtWidgets import QApplication
from qtpy.QtWidgets import QVBoxLayout

from trigger_designer.core.constants import VERSION, WORKFLOW_SCHEMA_VERSION
from trigger_designer.qt.helpers.state_mixin import SerializableContentMixin
from trigger_designer.qt.widgets.nodes.InOut.file_input import FileInputContent
from trigger_designer.qt.widgets.nodes.Join.join import JoinContent
from trigger_designer.qt.widgets.nodes.Preparation.cleansing import CleansingContent


APP = QApplication.instance() or QApplication([])


def _get_app() -> QApplication:
    return APP


class DummySerializableContent(SerializableContentMixin):
    serialized_state_schema = {
        "formula": {"attr": "formula_text", "default": ""},
        "config": {"default": {"enabled": False, "mode": "safe"}},
    }

    def __init__(self) -> None:
        self.formula_text = None
        self.config = {"enabled": True}


class DummyGraphicsNode:
    def __init__(self) -> None:
        self.tooltip = ""

    def setToolTip(self, tooltip: str) -> None:
        self.tooltip = tooltip


class DummyNode:
    def __init__(self) -> None:
        self.grNode = DummyGraphicsNode()
        self.invalid = False

    def markInvalid(self, value: bool = True) -> None:
        self.invalid = value


class DummyHistory:
    def __init__(self) -> None:
        self.is_restoring_history = False
        self.entries = []

    def storeHistory(self, **kwargs) -> None:  # noqa: N802 (Qt naming style)
        self.entries.append(kwargs)


class DummyCheckbox:
    def __init__(self) -> None:
        self.checked_states = []
        self.blocked_states = []

    def blockSignals(self, value: bool) -> None:  # noqa: N802 (Qt naming style)
        self.blocked_states.append(value)

    def setChecked(self, value: bool) -> None:  # noqa: N802 (Qt naming style)
        self.checked_states.append(value)


def _build_file_input_content(file_path: str) -> FileInputContent:
    content = FileInputContent.__new__(FileInputContent)
    content._node = DummyNode()
    content.history = None
    content.filePath = file_path
    content.preview_rows = 10
    content.file_type = "csv"
    content.record_limit = 0
    content.output_filename_as_field = False
    content.delimiter = ","
    content.first_row_contains_field_names = True
    content.selected_sheet = ""
    content.available_sheets = []
    content.start_row = 1
    content.data = pl.DataFrame()
    content.variable_name = "var_file_input_test"
    content.schema_snapshot = []
    content.file_metadata = {}
    content._missing_file_attempts = {}
    return content


def test_serializable_content_mixin_maps_and_normalizes_state() -> None:
    content = DummySerializableContent()

    payload = content.serialize_content_state({})

    assert payload["formula"] == ""
    assert payload["config"] == {"enabled": True, "mode": "safe"}

    content.deserialize_content_state(
        {"formula": "[amount] * 2", "config": {"enabled": False}}
    )

    assert content.formula_text == "[amount] * 2"
    assert content.config == {"enabled": False, "mode": "safe"}


def test_cleansing_content_serializes_full_state() -> None:
    content = CleansingContent.__new__(CleansingContent)
    content.replace_null_strings = False
    content.replace_null_numbers = True
    content.strip_whitespace = False
    content.normalize_spaces = True
    content.remove_all_whitespace = True
    content.case_modification = "upper"
    content.remove_letters = True
    content.remove_numbers = False
    content.remove_punctuation = True
    content.selected_fields = []
    content._field_selection_initialized = True
    content.remove_null_rows = True
    content.remove_null_rows_from_selected_columns = True
    content.remove_null_columns = False

    payload = content.serialize_content_state({})

    assert payload["replace_null_strings"] is False
    assert payload["remove_all_whitespace"] is True
    assert payload["case_modification"] == "upper"
    assert payload["remove_letters"] is True
    assert payload["selected_fields"] == []
    assert payload["field_selection_initialized"] is True
    assert payload["remove_null_rows_from_selected_columns"] is True

    restored = CleansingContent.__new__(CleansingContent)
    restored.deserialize_content_state(payload)

    assert restored.replace_null_strings is False
    assert restored.remove_all_whitespace is True
    assert restored.case_modification == "upper"
    assert restored.remove_letters is True
    assert restored.selected_fields == []
    assert restored._field_selection_initialized is True
    assert restored.remove_null_rows is True
    assert restored.remove_null_rows_from_selected_columns is True


def test_join_bulk_output_selection_updates_one_side_only() -> None:
    content = SimpleNamespace()
    content._get_frame_schema = JoinContent._get_frame_schema.__get__(content, JoinContent)
    content._get_available_output_columns = JoinContent._get_available_output_columns.__get__(content, JoinContent)
    content._sync_output_column_checkboxes = JoinContent._sync_output_column_checkboxes.__get__(content, JoinContent)
    content._set_output_columns_checked = JoinContent._set_output_columns_checked.__get__(content, JoinContent)
    content.history = DummyHistory()
    content.selected_columns = [{"name": "existing_right", "source": "R"}]
    content.mapping_data = [{"left_column": "id", "right_column": "id"}]
    content.join_type = "inner"
    content.node = DummyNode()
    content.left_data = pl.DataFrame({"id": [1], "name": ["Alice"]})
    content.right_data = pl.DataFrame({"code": [10]})
    left_id_checkbox = DummyCheckbox()
    left_name_checkbox = DummyCheckbox()
    right_code_checkbox = DummyCheckbox()
    content.output_column_checkboxes = [
        {"name": "id", "source": "L", "checkbox": left_id_checkbox},
        {"name": "name", "source": "L", "checkbox": left_name_checkbox},
        {"name": "code", "source": "R", "checkbox": right_code_checkbox},
    ]

    content._set_output_columns_checked("L", True)

    assert {tuple(column.items()) for column in content.selected_columns} == {
        (("name", "existing_right"), ("source", "R")),
        (("name", "id"), ("source", "L")),
        (("name", "name"), ("source", "L")),
    }
    assert left_id_checkbox.checked_states[-1] is True
    assert left_name_checkbox.checked_states[-1] is True
    assert right_code_checkbox.checked_states == []
    assert len(content.history.entries) == 1

    content._set_output_columns_checked("L", False)

    assert content.selected_columns == [{"name": "existing_right", "source": "R"}]
    assert left_id_checkbox.checked_states[-1] is False
    assert left_name_checkbox.checked_states[-1] is False
    assert len(content.history.entries) == 2


def test_join_mapping_rows_show_dtype_labels_but_keep_raw_column_names() -> None:
    _get_app()

    content = SimpleNamespace()
    content._get_frame_schema = JoinContent._get_frame_schema.__get__(content, JoinContent)
    content._format_column_label = JoinContent._format_column_label.__get__(content, JoinContent)
    content._populate_column_combo = JoinContent._populate_column_combo.__get__(content, JoinContent)
    content._combo_current_column = JoinContent._combo_current_column.__get__(content, JoinContent)
    content.update_mapping_data = lambda *args: None
    content.remove_mapping_row = lambda mapping_pair: None
    content.add_mapping_row = JoinContent.add_mapping_row.__get__(content, JoinContent)
    content.history = DummyHistory()
    content.mapping_data = []
    content.mapping_pairs = []
    content.selected_columns = []
    content.node = DummyNode()
    content.left_data = pl.DataFrame({"id": [1], "name": ["Alice"]})
    content.right_data = pl.DataFrame({"code": [10], "label": ["A"]})
    content.mapping_container = QVBoxLayout()

    content.add_mapping_row(left_col="id", right_col="code")

    left_combo = content.mapping_pairs[0]["left_combo"]
    right_combo = content.mapping_pairs[0]["right_combo"]
    left_index = left_combo.findData("id")
    right_index = right_combo.findData("code")

    assert left_combo.itemText(left_index) == "id [Int64]"
    assert right_combo.itemText(right_index) == "code [Int64]"
    assert left_combo.currentData() == "id"
    assert right_combo.currentData() == "code"
    assert content.mapping_data == [{"left_column": "id", "right_column": "code"}]


def test_trigger_scene_workflow_metadata_round_trip_in_subprocess() -> None:
    code = f"""
import os
import sys

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
sys.path.insert(0, r'{SRC_PATH}')

from qtpy.QtWidgets import QApplication

from trigger_designer.core.constants import VERSION, WORKFLOW_SCHEMA_VERSION
from trigger_designer.qt.performance_scene import TriggerScene

app = QApplication.instance() or QApplication([])
scene = TriggerScene()
serialized = scene.serialize()

assert serialized['workflow_metadata']['schema_version'] == WORKFLOW_SCHEMA_VERSION
assert serialized['workflow_metadata']['app_version'] == VERSION
assert 'saved_at' in serialized['workflow_metadata']

scene.deserialize({{
    'id': 1,
    'scene_width': 64000,
    'scene_height': 64000,
    'nodes': [],
    'edges': [],
}})

assert scene.loaded_workflow_metadata['schema_version'] == 0
assert scene.loaded_workflow_metadata['app_version'] is None
print('ok')
"""
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"

    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "ok" in result.stdout


def test_file_input_validation_reports_missing_file() -> None:
    content = _build_file_input_content(str(Path("does_not_exist.csv").resolve()))

    issues = content.validate_loaded_state()

    assert any("Missing input file" in issue for issue in issues)
    assert content.node.invalid is True
    assert "Workflow load validation failed" in content.node.grNode.tooltip


def test_file_input_validation_reports_schema_changes(tmp_path: Path) -> None:
    csv_path = tmp_path / "input.csv"
    csv_path.write_text("name\nAlice\n", encoding="utf-8")

    content = _build_file_input_content(str(csv_path))
    content.schema_snapshot = [
        {"name": "name", "dtype": "String"},
        {"name": "missing_col", "dtype": "String"},
    ]

    issues = content.validate_loaded_state()

    assert any("Missing saved columns" in issue for issue in issues)
    assert content.node.invalid is True
    assert "missing_col" in content.node.grNode.tooltip