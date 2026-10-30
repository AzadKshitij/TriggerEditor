"""Run-record schema, round trip and validation (docs/plan/02 3.3, 3.8)."""

from __future__ import annotations

import copy
import subprocess
import sys

from tests.support.audit_helpers import make_record_dict, sha
from trigger_designer.core.audit.canonical import compute_record_hash
from trigger_designer.core.audit.schema import (
    RunRecord,
    validate_record_dict,
)

#: The run-level keys of the 3.3 field table. Pinned here on purpose: adding a
#: field to the dataclass must be a conscious change to the format.
RUN_LEVEL_KEYS = {
    "schema_version",
    "run_id",
    "seq",
    "status",
    "started_at",
    "finished_at",
    "duration_s",
    "app_name",
    "app_version",
    "workflow_schema_version",
    "python_version",
    "polars_version",
    "duckdb_version",
    "os_name",
    "user",
    "machine",
    "workflow_path",
    "workflow_sha256",
    "workflow_uuid",
    "graph_sha256",
    "workflow_modified_since_save",
    "options",
    "inputs",
    "outputs",
    "nodes",
    "baseline",
    "warnings",
    "generated_code",
    "generated_code_sha256",
    "hash_algo",
    "prev_record_hash",
    "record_hash",
}


def _valid() -> dict:
    return make_record_dict(
        record_hash=sha("h"), prev_record_hash=sha("p"), graph_sha256=sha("g")
    )


def test_example_record_validates():
    assert validate_record_dict(_valid()) == []


def test_missing_required_key_reported():
    record = _valid()
    del record["nodes"]
    messages = validate_record_dict(record)
    assert any(m.startswith("nodes:") for m in messages)


def test_bad_status_enum():
    record = _valid()
    record["status"] = "weird"
    record["nodes"][0]["status"] = "meh"
    messages = validate_record_dict(record)
    assert any(m.startswith("status:") for m in messages)
    assert any(m.startswith("nodes[0].status:") for m in messages)


def test_bad_hash_length():
    record = _valid()
    record["record_hash"] = "abc"
    assert any(m.startswith("record_hash:") for m in validate_record_dict(record))


def test_future_schema_version_rejected():
    record = _valid()
    record["schema_version"] = 2
    assert any("newer" in m for m in validate_record_dict(record))


def test_error_object_needs_code_and_title():
    record = _valid()
    record["nodes"][1]["error"] = {"code": "TD-X"}
    assert any("error.title" in m for m in validate_record_dict(record))


def test_roundtrip_to_dict_from_dict():
    record = RunRecord.from_dict(_valid())
    assert RunRecord.from_dict(record.to_dict()).to_dict() == record.to_dict()
    assert record.nodes[0].node_id == 1
    assert record.inputs[0].sha256_status == "computed"


def test_from_dict_ignores_unknown_keys_but_raw_hash_still_covers_them():
    raw = _valid()
    raw["x_future"] = 1
    record = RunRecord.from_dict(raw)  # no TypeError
    assert "x_future" not in record.to_dict()
    other = {**raw, "x_future": 2}
    assert compute_record_hash(raw) != compute_record_hash(other)


def test_to_dict_field_set_matches_spec():
    assert set(RunRecord.from_dict(_valid()).to_dict()) == RUN_LEVEL_KEYS


def test_schema_imports_no_qt():
    code = (
        "import sys, trigger_designer.core.audit.schema, "
        "trigger_designer.core.audit.canonical;"
        "bad=[m for m in sys.modules if m.startswith(('qtpy','PyQt','PySide'))];"
        "assert not bad, bad"
    )
    proc = subprocess.run(
        [sys.executable, "-I", "-c", code],
        check=False,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr


def test_deepcopy_of_to_dict_is_independent():
    record = RunRecord.from_dict(_valid())
    one = record.to_dict()
    two = copy.deepcopy(one)
    two["warnings"].append("x")
    assert record.to_dict()["warnings"] == []
