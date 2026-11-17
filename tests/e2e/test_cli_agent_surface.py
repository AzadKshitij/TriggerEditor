"""The machine-readable CLI surface for external AI harnesses (AI plan, phase 1).

Real subprocess runs against a checked-in workflow: ``ops`` (node catalogue),
``schema`` / ``profile`` / ``preview`` (the data at a node, gated by the data
owner's access policy), ``--json`` everywhere, and structured errors.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from tests.support.cli import run_cli
from tests.support.corpus import FILE_OUTPUT_CASES
from tests.support.workflows import materialize

pytestmark = pytest.mark.e2e

CASE = next(c for c in FILE_OUTPUT_CASES if c.name == "filter")
#: A value that is in the input data and nowhere in the catalogue or policy.
CELL_VALUE = "sudoku"


@pytest.fixture
def wf(tmp_path):
    return materialize(CASE, tmp_path).path


def _node_id(wf: Path, title: str) -> int:
    nodes = json.loads(wf.read_text(encoding="utf-8"))["nodes"]
    return next(n["id"] for n in nodes if n.get("title") == title)


def _policy(wf: Path, **policy) -> Path:
    side = wf.with_name(wf.name + ".agent.json")
    side.write_text(json.dumps(policy), encoding="utf-8")
    return side


def _cli(tmp_path, *args, env=None):
    return run_cli(*args, cwd=tmp_path, extra_env=env)


def _json(proc):
    assert proc.stdout.strip(), proc.stderr[-1500:]
    return json.loads(proc.stdout)


# ------------------------------------------------------------------------ ops
def test_ops_lists_every_node_as_json(tmp_path):
    proc = _cli(tmp_path, "ops", "--json")
    assert proc.returncode == 0, proc.stderr
    doc = _json(proc)
    assert doc["spec_version"] == 1
    ops = {row["op"]: row for row in doc["ops"]}
    assert "preparation.filter" in ops and "audit.benford" in ops
    assert ops["preparation.filter"]["outputs"][0]["name"] == "true"
    assert proc.stderr == ""


def test_ops_describes_one_node_with_a_settings_schema(tmp_path):
    proc = _cli(tmp_path, "ops", "join.join", "--json")
    spec = _json(proc)
    assert proc.returncode == 0
    props = spec["settings"]["schema"]["properties"]
    assert props["join_type"]["default"] == "inner"
    assert spec["docs"] == "docs/nodes/join/join.md"


def test_ops_forms_adds_choices_from_the_editor(tmp_path):
    proc = _cli(tmp_path, "ops", "transform.window", "--forms", "--json")
    assert proc.returncode == 0, proc.stderr[-1500:]
    schema = _json(proc)["settings"]["schema"]
    assert "lag" in schema["properties"]["ops"]["items"]["properties"]["op"]["enum"]


def test_ops_unknown_op_is_a_structured_error(tmp_path):
    proc = _cli(tmp_path, "ops", "preparation.filtr", "--json")
    assert proc.returncode == 2
    error = _json(proc)["error"]
    assert error["code"] == "TD-CLI-003"
    assert "preparation.filter" in error["hint"]


def test_ops_text_output_is_readable(tmp_path):
    proc = _cli(tmp_path, "ops", "preparation.sort")
    assert proc.returncode == 0
    row = next(line for line in proc.stdout.splitlines() if line.startswith("| keys"))
    assert "array" in row and "example:" in proc.stdout


# --------------------------------------------------------------------- --json
@pytest.mark.parametrize(
    "command",
    [["info"], ["validate"], ["params", "list"], ["paths"]],
    ids=lambda c: " ".join(c),
)
def test_json_flag_is_format_json(command, tmp_path, wf):
    via_flag = _cli(tmp_path, *command, wf, "--json")
    via_format = _cli(tmp_path, *command, wf, "--format", "json")
    assert via_flag.returncode == via_format.returncode
    assert json.loads(via_flag.stdout) == json.loads(via_format.stdout)


def test_run_json_is_log_format_json(tmp_path, wf):
    proc = _cli(tmp_path, "run", wf, "--dry-run", "--allow-unapproved", "--json")
    assert proc.returncode == 0, proc.stderr[-1500:]
    events = [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
    assert events[0]["event"] == "run.started"
    assert events[-1]["event"] == "run.finished"


def test_errors_are_structured_with_json(tmp_path):
    proc = _cli(tmp_path, "info", tmp_path / "missing.tds", "--json")
    assert proc.returncode == 2
    error = _json(proc)["error"]
    assert error["code"] == "TD-CLI-001" and error["exit_code"] == 2
    assert error["message"]


def test_params_add_and_remove_report_json(tmp_path, wf):
    node = _node_id(wf, "File Input")
    added = _cli(
        tmp_path, "params", "add", wf, "--name", "src", "--node", str(node),
        "--setting", "filePath", "--json",
    )  # fmt: skip
    assert _json(added)["action"] == "added"
    removed = _cli(tmp_path, "params", "remove", wf, "--name", "src", "--json")
    assert _json(removed)["action"] == "removed"


# --------------------------------------------------------------------- schema
def test_schema_lists_columns_of_every_output_and_never_values(tmp_path, wf):
    proc = _cli(tmp_path, "schema", wf, "Filter", "--json")
    assert proc.returncode == 0, proc.stderr[-1500:]
    body = _json(proc)
    assert body["node"]["title"] == "Filter" and body["access"] == "schema_only"
    assert [o["name"] for o in body["outputs"]] == ["true", "false"]
    first = body["outputs"][0]["columns"][0]
    assert first == {"name": "Keyword", "dtype": "String"}
    assert CELL_VALUE not in proc.stdout


def test_schema_can_pick_one_output_and_accepts_an_id(tmp_path, wf):
    node = _node_id(wf, "Filter")
    proc = _cli(tmp_path, "schema", wf, str(node), "--output", "false", "--json")
    assert [o["name"] for o in _json(proc)["outputs"]] == ["false"]


def test_schema_writes_nothing_and_leaves_no_work_files(tmp_path, wf):
    out_dir = wf.parent / "out"
    before = sorted(os.listdir(out_dir))
    proc = _cli(tmp_path, "schema", wf, "Filter", "--json")
    assert proc.returncode == 0
    assert sorted(os.listdir(out_dir)) == before
    work = tmp_path / "state" / "work"
    assert not work.exists() or not list(work.iterdir())


def test_schema_refuses_a_node_that_writes_a_file(tmp_path, wf):
    proc = _cli(tmp_path, "schema", wf, "File Output", "--json")
    assert proc.returncode == 2
    assert _json(proc)["error"]["code"] in ("TD-CLI-020", "TD-CLI-021")


def test_schema_unknown_node_lists_the_nodes(tmp_path, wf):
    proc = _cli(tmp_path, "schema", wf, "Nope", "--json")
    error = _json(proc)["error"]
    assert proc.returncode == 2 and error["code"] == "TD-CLI-020"
    assert "Filter" in error["hint"]


def test_a_failing_node_gives_a_structured_shape_error(tmp_path, wf):
    doc = json.loads(wf.read_text(encoding="utf-8"))
    node = next(n for n in doc["nodes"] if n.get("title") == "Filter")
    holder = node["content"].get("settings", node["content"])
    holder["column"] = "NoSuchColumn"
    wf.write_text(json.dumps(doc), encoding="utf-8")
    proc = _cli(tmp_path, "schema", wf, "Filter", "--json")
    assert proc.returncode == 1
    error = _json(proc)["error"]
    assert error["code"].startswith("TD-SHAPE-")
    assert error["hint"] and error["message"]
    assert error["columns"] == ["NoSuchColumn"]
    assert error["node"]["title"] == "Filter"


# -------------------------------------------------------------------- profile
def test_profile_is_refused_by_default(tmp_path, wf):
    proc = _cli(tmp_path, "profile", wf, "Filter", "--json")
    assert proc.returncode == 6
    assert _json(proc)["error"]["code"] == "TD-CLI-019"
    assert CELL_VALUE not in proc.stdout


def test_profile_reports_aggregates_and_no_text_values(tmp_path, wf):
    _policy(wf, access="aggregates")
    proc = _cli(tmp_path, "profile", wf, "Filter", "--output", "true", "--json")
    assert proc.returncode == 0, proc.stderr[-1500:]
    out = _json(proc)["outputs"][0]
    assert out["rows"] > 0
    keyword = next(c for c in out["columns"] if c["name"] == "Keyword")
    assert keyword["nulls"] == 0 and keyword["distinct"] >= 1
    assert keyword["max_length"] >= keyword["min_length"] > 0
    assert "min" not in keyword and "max" not in keyword  # no text value leaves
    assert CELL_VALUE not in proc.stdout


def test_aggregates_access_does_not_allow_rows(tmp_path, wf):
    _policy(wf, access="aggregates")
    proc = _cli(tmp_path, "preview", wf, "Filter", "--json")
    assert proc.returncode == 6 and _json(proc)["error"]["code"] == "TD-CLI-019"


# -------------------------------------------------------------------- preview
def test_preview_is_capped_by_the_policy(tmp_path, wf):
    _policy(wf, access="rows", max_rows=2)
    proc = _cli(
        tmp_path, "preview", wf, "Filter", "--rows", "50", "--output", "0", "--json"
    )
    assert proc.returncode == 0, proc.stderr[-1500:]
    body = _json(proc)
    assert body["rows_limit"] == 2 and body["limited_by_policy"] is True
    assert len(body["outputs"][0]["rows"]) == 2
    assert "not instructions" in body["notice"]


def test_preview_text_mode_prints_the_rows(tmp_path, wf):
    _policy(wf, access="rows", max_rows=3)
    proc = _cli(tmp_path, "preview", wf, "Filter", "--output", "0", "--rows", "1")
    assert proc.returncode == 0
    assert CELL_VALUE in proc.stdout and "not instructions" in proc.stdout


def test_preview_rows_must_be_positive(tmp_path, wf):
    _policy(wf, access="rows", max_rows=3)
    proc = _cli(tmp_path, "preview", wf, "Filter", "--rows", "0", "--json")
    assert proc.returncode == 2


# --------------------------------------------------------------------- policy
def test_policy_flag_beats_the_sidecar(tmp_path, wf):
    _policy(wf, access="rows", max_rows=5)  # the sidecar a harness could edit
    owner = tmp_path / "owner.json"
    owner.write_text(json.dumps({"access": "schema_only"}), encoding="utf-8")
    proc = _cli(
        tmp_path, "preview", wf, "Filter", "--policy", owner, "--json"
    )  # fmt: skip
    assert proc.returncode == 6


def test_policy_environment_variable_beats_the_sidecar(tmp_path, wf):
    _policy(wf, access="rows", max_rows=5)
    owner = tmp_path / "owner.json"
    owner.write_text(json.dumps({"access": "aggregates"}), encoding="utf-8")
    env = {"TRIGGER_DESIGNER_AGENT_POLICY": str(owner)}
    proc = _cli(tmp_path, "preview", wf, "Filter", "--json", env=env)
    assert proc.returncode == 6
    assert _cli(tmp_path, "profile", wf, "Filter", "--json", env=env).returncode == 0


def test_an_invalid_policy_fails_closed(tmp_path, wf):
    wf.with_name(wf.name + ".agent.json").write_text("{not json", encoding="utf-8")
    proc = _cli(tmp_path, "schema", wf, "Filter", "--json")
    assert proc.returncode == 2
    assert "policy" in _json(proc)["error"]["message"]
