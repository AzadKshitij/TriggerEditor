#!/usr/bin/env python3

import os
import subprocess
import sys
from pathlib import Path
from typing import ClassVar

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)
SRC_PATH = sys.path[0]

import polars as pl
from qtpy.QtWidgets import QApplication

from trigger_designer.qt.helpers.state_mixin import SerializableContentMixin
from trigger_designer.qt.widgets.nodes.InOut.file_input import FileInputContent

APP = QApplication.instance() or QApplication([])


def _get_app() -> QApplication:
    return APP


class DummySerializableContent(SerializableContentMixin):
    serialized_state_schema: ClassVar[dict] = {
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


class DummyRsm:
    def get(self, _key):
        return None


class DummyNode:
    def __init__(self) -> None:
        self.grNode = DummyGraphicsNode()
        self.rsm = DummyRsm()
        self.invalid = False

    def markInvalid(self, value: bool = True) -> None:
        self.invalid = value


class DummyHistory:
    def __init__(self) -> None:
        self.is_restoring_history = False
        self.entries = []

    def storeHistory(self, **kwargs) -> None:
        self.entries.append(kwargs)


class DummyCheckbox:
    def __init__(self) -> None:
        self.checked_states = []
        self.blocked_states = []

    def blockSignals(self, value: bool) -> None:
        self.blocked_states.append(value)

    def setChecked(self, value: bool) -> None:
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


def test_cleansing_content_serializes_settings() -> None:
    from trigger_designer.core.node_configuration import (
        NodeTypes,
        PreparationNodes,
        get_class_from_opcode,
    )
    from trigger_designer.qt.design_window import TriggerSubWindow

    window = TriggerSubWindow()
    cls = get_class_from_opcode(PreparationNodes.CLEANSING, NodeTypes.PREPARATION)
    content = cls(window.scene).content
    content.settings.update(
        {
            "replace_null_strings": False,
            "remove_all_whitespace": True,
            "case_modification": "upper",
            "remove_letters": True,
            "selected_fields": ["a"],
            "remove_null_rows": True,
            "remove_null_rows_from_selected_columns": True,
        }
    )

    payload = content.serialize()

    assert payload["settings"]["replace_null_strings"] is False
    assert payload["settings"]["remove_all_whitespace"] is True
    assert payload["settings"]["case_modification"] == "upper"
    assert payload["settings"]["remove_letters"] is True
    assert payload["settings"]["selected_fields"] == ["a"]
    assert payload["settings"]["remove_null_rows"] is True

    restored = cls(window.scene).content
    restored.deserialize(payload)

    assert restored.settings["replace_null_strings"] is False
    assert restored.settings["remove_all_whitespace"] is True
    assert restored.settings["case_modification"] == "upper"
    assert restored.settings["remove_letters"] is True
    assert restored.settings["selected_fields"] == ["a"]
    assert restored.settings["remove_null_rows"] is True
    assert restored.settings["remove_null_rows_from_selected_columns"] is True


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
