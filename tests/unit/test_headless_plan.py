"""Pre-flight planning of a run, without Qt (plan 08 3.7 steps 3-6)."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from tests.support.cli import synthetic_workflow, write_workflow
from trigger_designer.core.headless import op_catalog
from trigger_designer.core.headless.approvals import make_entry, store_for
from trigger_designer.core.headless.exit_codes import CliError, ExitCode
from trigger_designer.core.headless.plan import RunOptions, build_run_plan
from trigger_designer.core.headless.workflow_file import read_workflow


@pytest.fixture
def env(tmp_path):
    (tmp_path / "in").mkdir()
    (tmp_path / "in" / "a.csv").write_text("x\n1\n")
    (tmp_path / "out").mkdir()
    data = synthetic_workflow(
        input_path=str(tmp_path / "in" / "a.csv"),
        output_path=str(tmp_path / "out" / "o.csv"),
    )
    path = write_workflow(tmp_path / "wf" / "wf.tds", data)
    return {
        "tmp": tmp_path,
        "path": path,
        "doc": read_workflow(str(path)),
        "state": tmp_path / "state",
    }


def _plan(env, **kw):
    kw.setdefault("allow_unapproved", True)
    return build_run_plan(RunOptions(**kw), env["doc"], env["state"], "ab12cd34" * 4)


def _code(exc):
    return exc.value.td_code, exc.value.code


def test_plan_stages_outputs_and_declares_io_paths(env):
    plan = _plan(env)
    (staged,) = plan.staged
    assert staged.final == str(env["tmp"] / "out" / "o.csv")
    assert (
        staged.staged in plan.io_paths
        and str(env["tmp"] / "in" / "a.csv") in plan.io_paths
    )
    assert os.path.basename(staged.staged) == ".o.tdtmp-ab12cd34.csv"
    assert plan.work_copy.parent == env["state"] / "work" / plan.run_id
    assert plan.work_copy.read_bytes().isascii()
    assert plan.inputs[0]["exists"] and plan.outputs[0]["final"] == staged.final


def test_all_missing_inputs_reported_together(env):
    extra = synthetic_workflow(
        input_path=str(env["tmp"] / "in" / "gone1.csv"),
        output_path=str(env["tmp"] / "out" / "o.csv"),
    )
    second = dict(extra["nodes"][0], id=777, outputs=[{"id": 7771}])
    second["content"] = dict(
        second["content"], filePath=str(env["tmp"] / "in" / "gone2.csv")
    )
    extra["nodes"].append(second)
    path = write_workflow(env["tmp"] / "wf" / "two.tds", extra)
    with pytest.raises(CliError) as exc:
        build_run_plan(
            RunOptions(allow_unapproved=True), read_workflow(str(path)), env["state"]
        )
    assert exc.value.td_code == "TD-IN-001" and exc.value.code == ExitCode.INVALID
    assert "gone1.csv" in exc.value.message and "gone2.csv" in exc.value.message
    assert not (env["state"] / "work").exists()


def test_missing_output_dir_and_create_flag(env):
    target = env["tmp"] / "new" / "dir"
    with pytest.raises(CliError) as exc:
        _plan(env, output_dir=str(target))
    assert exc.value.td_code == "TD-CLI-014"
    plan = _plan(env, output_dir=str(target), create_output_dirs=True)
    assert target.is_dir() and plan.staged[0].final == str(target / "o.csv")


def test_dry_run_does_not_create_dirs(env):
    target = env["tmp"] / "new2"
    _plan(env, output_dir=str(target), create_output_dirs=True, dry_run=True)
    assert not target.exists()


def test_output_equal_to_input_path_is_refused(env):
    data = synthetic_workflow(
        input_path=str(env["tmp"] / "in" / "a.csv"),
        output_path=str(env["tmp"] / "in" / "a.csv"),
    )
    path = write_workflow(env["tmp"] / "wf" / "same.tds", data)
    with pytest.raises(CliError) as exc:
        build_run_plan(
            RunOptions(allow_unapproved=True), read_workflow(str(path)), env["state"]
        )
    assert exc.value.td_code == "TD-CLI-014"


def test_duplicate_outputs_are_refused(env):
    data = synthetic_workflow(
        input_path=str(env["tmp"] / "in" / "a.csv"),
        output_path=str(env["tmp"] / "out" / "o.csv"),
    )
    dup = dict(data["nodes"][2], id=888, inputs=[{"id": 8881}])
    data["nodes"].append(dup)
    path = write_workflow(env["tmp"] / "wf" / "dup.tds", data)
    with pytest.raises(CliError) as exc:
        build_run_plan(
            RunOptions(allow_unapproved=True), read_workflow(str(path)), env["state"]
        )
    assert exc.value.td_code == "TD-CLI-014" and "overwrite" in exc.value.message


def test_low_disk_space(env, monkeypatch):
    monkeypatch.setattr(
        shutil, "disk_usage", lambda _p: shutil._ntuple_diskusage(100, 99, 1024)
    )
    with pytest.raises(CliError) as exc:
        _plan(env)
    assert exc.value.td_code == "TD-CLI-015"
    _plan(env, min_free_mb=0)


def test_unapproved_is_refused_and_allowed_with_flag(env):
    with pytest.raises(CliError) as exc:
        _plan(env, allow_unapproved=False)
    assert _code(exc) == ("TD-CLI-008", ExitCode.REFUSED)
    assert _plan(env).approval_sha256 is None


def test_approved_runs_and_changed_file_is_refused(env):
    store_for(env["state"]).add(make_entry(env["doc"], [], []))
    assert _plan(env, allow_unapproved=False).approval_sha256 == env["doc"].sha256
    env["path"].write_text(
        env["path"].read_text(encoding="utf-8") + "\n", encoding="utf-8"
    )
    edited = read_workflow(str(env["path"]))
    with pytest.raises(CliError) as exc:
        build_run_plan(RunOptions(), edited, env["state"])
    assert exc.value.code == ExitCode.REFUSED and "changed after" in exc.value.message


def test_scheduled_trigger_ignores_allow_unapproved(env):
    with pytest.raises(CliError) as exc:
        _plan(env, trigger="schedule", allow_unapproved=True)
    assert exc.value.code == ExitCode.REFUSED


def test_changed_file_on_a_schedule_reports_td_cli_009(env):
    store_for(env["state"]).add(make_entry(env["doc"], [], []))
    env["path"].write_text(
        env["path"].read_text(encoding="utf-8") + "\n", encoding="utf-8"
    )
    edited = read_workflow(str(env["path"]))
    with pytest.raises(CliError) as exc:
        build_run_plan(RunOptions(trigger="schedule"), edited, env["state"])
    assert exc.value.td_code == "TD-CLI-009"


def test_custom_code_op_needs_flag_and_approval(env, monkeypatch):
    patched = dict(op_catalog.OPS)
    patched["preparation.filter"] = op_catalog.OpInfo(
        "preparation.filter", "Filter", "preparation", custom_code=True
    )
    monkeypatch.setattr(op_catalog, "OPS", patched)
    with pytest.raises(CliError) as exc:
        _plan(env)
    assert _code(exc) == ("TD-CLI-011", ExitCode.REFUSED)
    with pytest.raises(CliError):
        _plan(env, allow_custom_code=True)  # not approved
    store_for(env["state"]).add(make_entry(env["doc"], [], []))
    assert _plan(env, allow_custom_code=True, allow_unapproved=False)


def test_strict_turns_warnings_into_errors(env):
    data = synthetic_workflow(
        input_path=str(env["tmp"] / "in" / "a.csv"),
        output_path=str(env["tmp"] / "out" / "o.csv"),
    )
    del data["workflow_metadata"]
    path = write_workflow(env["tmp"] / "wf" / "legacy.tds", data)
    doc = read_workflow(str(path))
    build_run_plan(RunOptions(allow_unapproved=True), doc, env["state"])
    with pytest.raises(CliError) as exc:
        build_run_plan(
            RunOptions(allow_unapproved=True, strict=True), doc, env["state"]
        )
    assert "--strict" in exc.value.message


def test_workflow_that_writes_nothing_warns(env):
    data = synthetic_workflow(input_path=str(env["tmp"] / "in" / "a.csv"))
    data["nodes"].pop(2)
    data["edges"].pop(1)
    path = write_workflow(env["tmp"] / "wf" / "noout.tds", data)
    doc = read_workflow(str(path))
    plan = build_run_plan(RunOptions(allow_unapproved=True), doc, env["state"])
    assert "TD-CLI-018" in [w.td_code for w in plan.warnings]
    with pytest.raises(CliError):
        build_run_plan(
            RunOptions(allow_unapproved=True, strict=True), doc, env["state"]
        )


def test_unwritable_output_folder(env, monkeypatch):
    real_open = open

    def refusing(path, *a, **k):
        if ".td-probe-" in str(path):
            raise PermissionError(13, "denied", str(path))
        return real_open(path, *a, **k)

    monkeypatch.setattr("builtins.open", refusing)
    with pytest.raises(CliError) as exc:
        _plan(env)
    assert exc.value.td_code == "TD-CLI-014"


def test_unsafe_output_dir_stages_under_state(env):
    odd = env["tmp"] / "O'Brien"
    odd.mkdir()
    plan = _plan(env, output_dir=str(odd))
    staged = plan.staged[0]
    assert staged.cross_volume and Path(staged.staged).is_relative_to(
        env["state"] / "staging"
    )
    assert Path(staged.staged).parent.is_dir()


def test_plan_does_not_touch_the_original(env):
    before = env["path"].read_bytes()
    _plan(env, params={}, input_dir=str(env["tmp"] / "in"))
    assert env["path"].read_bytes() == before
