"""Approvals store and the ``approve``/``info`` commands (plan 08 S3)."""

from __future__ import annotations

import json
import os

import pytest

from tests.support.cli import call_main, synthetic_workflow, write_workflow
from trigger_designer.core.headless.approvals import (
    ApprovalStore,
    approval_status,
    make_entry,
    store_for,
)
from trigger_designer.core.headless.exit_codes import CliError, ExitCode
from trigger_designer.core.headless.workflow_file import read_workflow


@pytest.fixture
def wf(tmp_path):
    return write_workflow(tmp_path / "wf" / "wf.tds", synthetic_workflow())


def _env(tmp_path):
    return {"TRIGGER_DESIGNER_STATE_DIR": str(tmp_path / "state")}


def test_add_lookup_revoke(tmp_path, wf):
    store = ApprovalStore(tmp_path / "approvals.json")
    doc = read_workflow(str(wf))
    assert store.is_approved(doc.sha256) is None
    store.add(make_entry(doc, ["a"], ["b"], "note"))
    entry = store.is_approved(doc.sha256)
    assert (
        entry["reads"] == ["a"] and entry["writes"] == ["b"] and entry["note"] == "note"
    )
    store.add(make_entry(doc, [], []))  # same sha replaces
    assert len(store.list()) == 1
    assert store.revoke(str(wf)) == 1
    assert store.is_approved(doc.sha256) is None


def test_changed_bytes_are_not_approved_and_reported(tmp_path, wf):
    state = tmp_path / "state"
    doc = read_workflow(str(wf))
    store_for(state).add(make_entry(doc, [], []))
    assert approval_status(state, doc)["status"] == "yes"
    wf.write_text(wf.read_text(encoding="utf-8") + " ", encoding="utf-8")
    edited = read_workflow(str(wf))
    status = approval_status(state, edited)
    assert status["status"] == "changed"
    assert "changed since approval" in status["text"]


def test_unknown_store_version_is_invalid(tmp_path):
    path = tmp_path / "approvals.json"
    path.write_text(json.dumps({"version": 99, "approvals": []}), encoding="utf-8")
    with pytest.raises(CliError) as exc:
        ApprovalStore(path).list()
    assert exc.value.code == ExitCode.INVALID


def test_no_temp_file_left_after_write(tmp_path, wf):
    store = ApprovalStore(tmp_path / "state" / "approvals.json")
    store.add(make_entry(read_workflow(str(wf)), [], []))
    assert sorted(os.listdir(tmp_path / "state")) == ["approvals.json"]


def test_approve_non_tty_without_yes_is_usage(tmp_path, wf, monkeypatch):
    monkeypatch.setattr("sys.stdin", type("S", (), {"isatty": lambda self: False})())
    result = call_main(["approve", wf], env=_env(tmp_path))
    assert result.code == int(ExitCode.USAGE)
    assert "--yes" in result.stderr


def test_approve_yes_records_reads_and_writes(tmp_path, wf):
    env = _env(tmp_path)
    result = call_main(["approve", wf, "--yes", "--note", "PR 1"], env=env)
    assert result.code == 0, result.stderr
    assert "sha256" in result.stdout
    store = ApprovalStore(tmp_path / "state" / "approvals.json")
    entry = store.list()[0]
    assert entry["note"] == "PR 1"
    assert entry["reads"][0].endswith("in.csv") and entry["writes"][0].endswith(
        "out.csv"
    )
    listed = call_main(["approve", "--list", "--format", "json"], env=env)
    assert listed.json()[0]["sha256"] == entry["sha256"]
    info = call_main(["info", wf, "--format", "json"], env=env).json()
    assert info["approval"]["status"] == "yes"
    revoked = call_main(["approve", "--revoke", wf], env=env)
    assert revoked.code == 0
    assert (
        call_main(["info", wf, "--format", "json"], env=env).json()["approval"][
            "status"
        ]
        == "no"
    )


def test_approve_requires_workflow_or_flag(tmp_path):
    assert call_main(["approve"], env=_env(tmp_path)).code == int(ExitCode.USAGE)


def test_info_text_shows_reads_writes_and_approval(tmp_path, wf):
    result = call_main(["info", wf], env=_env(tmp_path))
    assert result.code == 0
    for needle in ("approved:   no", "reads:", "writes:", "input.file_input: 1"):
        assert needle in result.stdout
