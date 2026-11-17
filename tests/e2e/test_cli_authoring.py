"""``edit`` and ``diff``: changing a workflow from the command line (AI plan, phase 2).

Real subprocess runs on a copy of a checked-in workflow: every edit is a dry run
unless ``--apply``; ``--apply`` needs the data owner's policy, keeps a backup and
refuses a file that changed; the result still loads and runs.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from tests.support.cli import run_cli
from tests.support.corpus import FILE_OUTPUT_CASES
from tests.support.workflows import materialize
from trigger_designer.core.headless.op_catalog import node_op

pytestmark = pytest.mark.e2e

CASE = next(c for c in FILE_OUTPUT_CASES if c.name == "filter")


@pytest.fixture
def wf(tmp_path):
    return materialize(CASE, tmp_path).path


def _cli(tmp_path, *args):
    return run_cli(*args, cwd=tmp_path)


def _json(proc):
    assert proc.stdout.strip(), proc.stderr[-1500:]
    return json.loads(proc.stdout)


def _node_id(wf: Path, op: str) -> int:
    nodes = json.loads(wf.read_text(encoding="utf-8"))["nodes"]
    return next(n["id"] for n in nodes if node_op(n) == op)


def _allow(wf: Path, **extra) -> Path:
    side = wf.with_name(wf.name + ".agent.json")
    side.write_text(json.dumps({"edit": True, **extra}), encoding="utf-8")
    return side


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ------------------------------------------------------------------ dry run
def test_an_edit_is_a_dry_run_unless_apply_is_given(wf, tmp_path):
    before = wf.read_bytes()
    proc = _cli(tmp_path, "edit", "add-node", str(wf), "preparation.sort", "--json")
    assert proc.returncode == 0, proc.stderr
    out = _json(proc)
    assert out["dry_run"] and not out["applied"] and out["changed"]
    assert out["diff"]["summary"]["nodes_added"] == 1
    assert wf.read_bytes() == before
    assert not wf.with_name(wf.name + ".bak").exists()


def test_apply_needs_the_data_owners_permission(wf, tmp_path):
    before = wf.read_bytes()
    proc = _cli(
        tmp_path, "edit", "add-node", str(wf), "preparation.sort", "--apply", "--json"
    )
    assert proc.returncode == 6
    assert _json(proc)["error"]["code"] == "TD-CLI-019"
    assert wf.read_bytes() == before


def test_a_patch_is_refused_without_permission_too(wf, tmp_path):
    proc = _cli(
        tmp_path,
        "edit",
        "patch",
        str(wf),
        json.dumps([{"op": "layout"}]),
        "--apply",
        "--json",
    )
    assert proc.returncode == 6


# -------------------------------------------------------------------- apply
def test_apply_writes_keeps_one_backup_and_changes_the_hash(wf, tmp_path):
    _allow(wf)
    original = wf.read_bytes()
    proc = _cli(
        tmp_path,
        "edit",
        "add-node",
        str(wf),
        "preparation.sort",
        "--title",
        "Biggest first",
        "--apply",
        "--json",
    )
    out = _json(proc)
    assert proc.returncode == 0, proc.stderr
    assert out["applied"] and out["sha256_after"] == _sha(wf) != out["sha256_before"]
    assert Path(out["backup"]).read_bytes() == original
    # a second edit does not overwrite the first backup
    _cli(tmp_path, "edit", "add-node", str(wf), "preparation.sort", "--apply")
    assert Path(out["backup"]).read_bytes() == original


def test_an_edited_workflow_still_validates_and_lists_the_new_node(wf, tmp_path):
    _allow(wf)
    patch = tmp_path / "patch.json"
    patch.write_text(
        json.dumps(
            [
                {
                    "op": "add_node",
                    "type": "preparation.sort",
                    "ref": "s",
                    "settings": {"keys": [{"column": "Amount", "order": "Descending"}]},
                },
                {
                    "op": "connect",
                    "from": _node_id(wf, "preparation.filter"),
                    "output": "true",
                    "to": "s",
                },
            ]
        ),
        encoding="utf-8",
    )
    proc = _cli(tmp_path, "edit", "patch", str(wf), f"@{patch}", "--apply", "--json")
    assert proc.returncode == 0, proc.stderr
    check = _cli(tmp_path, "validate", str(wf), "--json")
    assert check.returncode == 0, check.stdout + check.stderr
    info = _json(_cli(tmp_path, "info", str(wf), "--json"))
    assert any("preparation.sort" in str(info[k]) for k in info if k.startswith("op"))


def test_an_edited_workflow_needs_approving_again(wf, tmp_path):
    _allow(wf)
    state = ("--state-dir", str(tmp_path / "state"))

    def approval() -> str:
        info = _json(_cli(tmp_path, *state, "info", str(wf), "--json"))
        return info["approval"]["status"]

    assert _cli(tmp_path, *state, "approve", str(wf), "--yes").returncode == 0
    assert approval() == "yes"
    _cli(tmp_path, "edit", "add-node", str(wf), "preparation.sort", "--apply")
    assert approval() == "changed"
    run = _cli(tmp_path, *state, "run", str(wf), "--json")
    assert run.returncode == 6  # not approved: changed since approval


def test_a_changed_file_is_refused_with_expect_sha(wf, tmp_path):
    _allow(wf)
    stale = _sha(wf)
    _cli(tmp_path, "edit", "add-node", str(wf), "preparation.sort", "--apply")
    proc = _cli(
        tmp_path,
        "edit",
        "add-node",
        str(wf),
        "preparation.sort",
        "--expect-sha",
        stale,
        "--apply",
        "--json",
    )
    assert proc.returncode == 2
    assert _json(proc)["error"]["code"] == "TD-CLI-026"


# ------------------------------------------------------------- bad requests
def test_bad_requests_are_structured_errors_and_write_nothing(wf, tmp_path):
    _allow(wf)
    before = wf.read_bytes()
    cases = [
        (["add-node", str(wf), "preparation.filtr"], "TD-CLI-003"),
        (["add-node", str(wf), "preparation.filter", "--set", "colum=x"], "TD-CLI-022"),
        (
            [
                "add-node",
                str(wf),
                "transform.sql_query",
                "--set",
                "sql=SELECT * FROM read_csv('x')",
            ],
            "TD-CLI-025",
        ),
        (["connect", str(wf), "nobody", "alsonobody"], "TD-CLI-020"),
        (
            [
                "add-node",
                str(wf),
                "input.file_output",
                "--set",
                "filePath=..\\..\\x.csv",
            ],
            "TD-CLI-024",
        ),
    ]
    for argv, code in cases:
        proc = _cli(tmp_path, "edit", *argv, "--apply", "--json")
        assert proc.returncode in (2, 6), (argv, proc.stdout, proc.stderr)
        assert _json(proc)["error"]["code"] == code, argv
    assert wf.read_bytes() == before


def test_a_policy_can_allow_another_folder_for_file_settings(wf, tmp_path):
    shared = tmp_path / "shared"
    shared.mkdir()
    _allow(wf, paths=[str(shared)])
    proc = _cli(
        tmp_path,
        "edit",
        "add-node",
        str(wf),
        "input.file_output",
        "--set",
        f"filePath={shared / 'out.csv'}",
        "--json",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_a_patch_that_fails_halfway_writes_nothing(wf, tmp_path):
    _allow(wf)
    before = wf.read_bytes()
    bad = json.dumps(
        [
            {"op": "add_node", "type": "preparation.sort", "ref": "s"},
            {"op": "connect", "from": "s", "to": "s"},
        ]
    )
    proc = _cli(tmp_path, "edit", "patch", str(wf), bad, "--apply", "--json")
    assert proc.returncode == 2
    assert _json(proc)["error"]["message"].startswith("edit 2 (connect):")
    assert wf.read_bytes() == before


def test_a_file_from_a_newer_version_is_refused(tmp_path):
    new = tmp_path / "new.tds"
    new.write_text(
        json.dumps(
            {"nodes": [], "edges": [], "workflow_metadata": {"schema_version": 99}}
        ),
        encoding="utf-8",
    )
    proc = _cli(tmp_path, "edit", "layout", str(new), "--json")
    assert proc.returncode == 2
    assert _json(proc)["error"]["code"] == "TD-CLI-027"


def test_a_node_in_the_old_file_format_cannot_have_its_settings_edited(wf, tmp_path):
    """The checked-in workflow predates stable op ids: its nodes carry numeric
    codes only. They can be connected, not re-configured."""
    data = json.loads(wf.read_text(encoding="utf-8"))
    legacy = next(n for n in data["nodes"] if node_op(n) == "preparation.filter")
    assert "op" not in legacy
    proc = _cli(
        tmp_path,
        "edit",
        "set",
        str(wf),
        str(legacy["id"]),
        "--set",
        "value=1",
        "--json",
    )
    error = _json(proc)["error"]
    assert proc.returncode == 2 and "save it once" in error["hint"]


# --------------------------------------------------------------------- diff
def test_diff_compares_two_files(wf, tmp_path):
    _allow(wf)
    original = tmp_path / "before.tds"
    original.write_bytes(wf.read_bytes())
    _cli(
        tmp_path,
        "edit",
        "add-node",
        str(wf),
        "preparation.sort",
        "--title",
        "Biggest first",
        "--apply",
    )
    out = _json(_cli(tmp_path, "diff", str(original), str(wf), "--json"))
    assert not out["empty"] and out["summary"]["nodes_added"] == 1
    added = out["nodes"]["added"][0]
    assert added["title"] == "Sort" and added["label"] == "Biggest first"
    text = _cli(tmp_path, "diff", str(original), str(wf)).stdout
    assert "+ node" in text and "Biggest first" in text
    same = _json(_cli(tmp_path, "diff", str(original), str(original), "--json"))
    assert same["empty"]


# ---------------------------------------------------------------------- new
def test_new_is_a_dry_run_unless_apply_and_needs_permission(tmp_path):
    target = tmp_path / "fresh.tds"
    dry = _cli(tmp_path, "edit", "new", str(target), "--json")
    assert dry.returncode == 0 and _json(dry)["dry_run"] and not target.exists()
    refused = _cli(tmp_path, "edit", "new", str(target), "--apply", "--json")
    assert refused.returncode == 6 and not target.exists()
    assert _json(refused)["error"]["code"] == "TD-CLI-019"


def test_new_creates_an_empty_workflow_and_never_replaces_a_file(tmp_path):
    target = tmp_path / "fresh.tds"
    _allow(target)
    made = _cli(tmp_path, "edit", "new", str(target), "--apply", "--json")
    out = _json(made)
    assert made.returncode == 0 and out["created"] and target.exists()
    assert out["sha256_after"] == _sha(target)
    assert _cli(tmp_path, "validate", str(target)).returncode == 0
    before = target.read_bytes()
    again = _cli(tmp_path, "edit", "new", str(target), "--apply", "--json")
    assert again.returncode == 2 and target.read_bytes() == before
    assert _json(again)["error"]["code"] == "TD-CLI-027"


@pytest.mark.parametrize("name", ["fresh.txt", "missing_dir/fresh.tds"])
def test_new_refuses_a_bad_name_or_folder(tmp_path, name):
    proc = _cli(tmp_path, "edit", "new", str(tmp_path / name), "--json")
    assert proc.returncode == 2
    assert _json(proc)["error"]["code"] == "TD-CLI-027"


def test_a_workflow_built_only_with_the_cli_runs_and_gives_the_right_rows(tmp_path):
    """new -> patch -> validate -> approve -> run, with no other tool."""
    import csv

    (tmp_path / "invoices.csv").write_text(
        "invoice_id,amount\nA,2450.00\nB,18200.50\nC,10000.00\nD,56000.00\nE,10000.01\n",
        encoding="utf-8",
    )
    wf = tmp_path / "over_10k.tds"
    _allow(wf)
    assert _cli(tmp_path, "edit", "new", str(wf), "--apply").returncode == 0
    column = {"selected": True, "rename": "", "date_format": ""}
    edits = [
        {
            "op": "add_node",
            "type": "input.file_input",
            "ref": "i",
            "settings": {"filePath": "invoices.csv"},
        },
        {
            "op": "add_node",
            "type": "preparation.select",
            "ref": "s",
            "after": "i",
            "settings": {
                "columns": [
                    {
                        **column,
                        "name": "invoice_id",
                        "dtype": "String",
                        "dtype_custom": False,
                    },
                    {
                        **column,
                        "name": "amount",
                        "dtype": "Float64",
                        "dtype_custom": True,
                    },
                ]
            },
        },
        {
            "op": "add_node",
            "type": "preparation.filter",
            "ref": "f",
            "after": "s",
            "settings": {
                "column": "amount",
                "operation": "Greater Than",
                "value": "10000",
            },
        },
        {
            "op": "add_node",
            "type": "preparation.sort",
            "ref": "o",
            "after": "f",
            "settings": {"keys": [{"column": "amount", "order": "Descending"}]},
        },
        {
            "op": "add_node",
            "type": "input.file_output",
            "ref": "w",
            "after": "o",
            "settings": {"filePath": "out/over_10k.csv"},
        },
        {"op": "connect", "from": "i", "to": "s"},
        {"op": "connect", "from": "s", "to": "f"},
        {"op": "connect", "from": "f", "output": "true", "to": "o"},
        {"op": "connect", "from": "o", "to": "w"},
    ]
    patch = tmp_path / "edits.json"
    patch.write_text(json.dumps(edits), encoding="utf-8")
    applied = _cli(tmp_path, "edit", "patch", str(wf), f"@{patch}", "--apply")
    assert applied.returncode == 0, applied.stdout + applied.stderr
    assert _cli(tmp_path, "validate", str(wf)).returncode == 0
    state = ("--state-dir", str(tmp_path / "state"))
    assert _cli(tmp_path, *state, "approve", str(wf), "--yes").returncode == 0
    run = _cli(tmp_path, *state, "run", str(wf), "--create-output-dirs")
    assert run.returncode == 0, run.stderr[-1500:]
    with open(tmp_path / "out" / "over_10k.csv", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert [r["invoice_id"] for r in rows] == ["D", "B", "E"]
