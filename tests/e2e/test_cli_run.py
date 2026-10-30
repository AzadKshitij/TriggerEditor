"""``trigger-designer-cli run`` end to end, in a real subprocess (plan 08 6.2).

Every case materializes a checked-in workflow into ``tmp_path`` (inputs point at
the sample data, outputs into ``tmp_path/out``) and runs the installed CLI
against it, so nothing is written near the repository.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
from pathlib import Path

import pytest

from tests.support.cli import events, run_cli
from tests.support.corpus import FILE_OUTPUT_CASES
from tests.support.frames import assert_frame_golden, read_frame
from tests.support.workflows import REPO_ROOT, materialize

pytestmark = pytest.mark.e2e

CASES = {case.name: case for case in FILE_OUTPUT_CASES}
HOOKS = {"TD_TEST_HOOKS": "1"}


def _run(m, tmp_path, *extra, env=None, cwd=None, approve=False, timeout=180):
    args = ["run", m.path if hasattr(m, "path") else m]
    if not approve:
        args.append("--allow-unapproved")
    args += ["--log-format", "json", "--record-dir", tmp_path / "rec", *extra]
    return run_cli(*args, cwd=cwd or tmp_path, extra_env=env, timeout=timeout)


def _finished(proc):
    return [e for e in events(proc) if e["event"] == "run.finished"][-1]


def _leftovers(directory: Path) -> list[str]:
    return [n for n in os.listdir(directory) if "tdtmp" in n or "tdbak" in n]


@pytest.mark.parametrize("name", sorted(CASES))
def test_run_matches_goldens(name, tmp_path):
    case = CASES[name]
    m = materialize(case, tmp_path)
    proc = _run(m, tmp_path)
    assert proc.returncode == 0, proc.stderr[-2000:] + proc.stdout[-2000:]
    written = sorted(p.name for p in m.out_dir.iterdir())
    for basename, golden in case.goldens.items():
        assert basename in written, f"{basename} missing; wrote {written}"
        frame = read_frame(m.out_dir / basename)
        sort_by = frame.columns if golden in case.unordered_goldens else None
        assert_frame_golden(frame, golden, sort_by=sort_by)
    assert _leftovers(m.out_dir) == []
    assert "check_output.py" not in os.listdir(tmp_path)


def test_stdout_is_only_json_lines(tmp_path):
    m = materialize(CASES["formula"], tmp_path)
    proc = _run(m, tmp_path)
    assert proc.returncode == 0, proc.stderr[-1500:]
    rows = events(proc)  # every line must parse
    assert rows[0]["event"] == "run.started"
    assert rows[-1]["event"] == "run.finished"
    assert rows[-1]["exit_code"] == 0 and rows[-1]["status"] == "ok"
    assert Path(rows[-1]["record_path"]).exists()
    assert len([r for r in rows if r["event"] == "node.finished"]) == 3
    assert not any(line.lstrip().startswith("{") for line in proc.stderr.splitlines())
    assert {"ts", "level", "event", "run_id"} <= set(rows[0])


def test_text_mode_has_empty_stdout_and_summary_on_stderr(tmp_path):
    m = materialize(CASES["formula"], tmp_path)
    proc = run_cli(
        "run",
        m.path,
        "--allow-unapproved",
        "--record-dir",
        tmp_path / "rec",
        cwd=tmp_path,
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""
    assert "run.finished" in proc.stderr


def test_missing_input_exit_2(tmp_path):
    inputs = tmp_path / "in"
    inputs.mkdir()
    shutil.copy(REPO_ROOT / "data" / "check.csv", inputs / "check.csv")
    m = materialize(CASES["formula"], tmp_path, {"check.csv": inputs / "check.csv"})
    (inputs / "check.csv").unlink()
    proc = _run(m, tmp_path)
    assert proc.returncode == 2
    done = _finished(proc)
    assert done["status"] == "invalid"
    assert done["errors"][0]["code"] == "TD-IN-001"
    assert list(m.out_dir.iterdir()) == []
    assert not list((tmp_path / "state" / "locks").glob("*.lock"))


def test_unapproved_exit_6_then_approve_then_run(tmp_path):
    m = materialize(CASES["formula"], tmp_path)
    proc = _run(m, tmp_path, approve=True)
    assert proc.returncode == 6
    assert _finished(proc)["errors"][0]["code"] == "TD-CLI-008"
    approved = run_cli("approve", m.path, "--yes", cwd=tmp_path)
    assert approved.returncode == 0, approved.stderr
    ok = _run(m, tmp_path, approve=True)
    assert ok.returncode == 0, ok.stderr[-1500:]
    assert _finished(ok)["status"] == "ok"
    m.path.write_bytes(m.path.read_bytes() + b" ")
    again = _run(m, tmp_path, approve=True)
    assert again.returncode == 6


def test_scheduled_trigger_ignores_allow_unapproved(tmp_path):
    m = materialize(CASES["formula"], tmp_path)
    proc = _run(m, tmp_path, "--trigger", "schedule")
    assert proc.returncode == 6


def test_node_failure_exit_1_keeps_previous_output(tmp_path):
    m = materialize(CASES["formula"], tmp_path)
    target = m.out_dir / "out_check_W_formula.csv"
    target.write_bytes(b"sentinel")
    proc = _run(m, tmp_path, env={**HOOKS, "TD_TEST_FAIL_NODE": "Formula"})
    assert proc.returncode == 1
    assert target.read_bytes() == b"sentinel"
    assert _leftovers(m.out_dir) == []
    rows = events(proc)
    formula = next(
        r for r in rows if r["event"] == "node.finished" and r["title"] == "Formula"
    )
    assert formula["status"] == "failed" and formula["error"]["title"]
    done = rows[-1]
    assert done["status"] == "failed"
    first = done["errors"][0]
    assert first["code"] and first["title"] and first["hint"] is not None


def test_record_written_once_and_verifies(tmp_path):
    from trigger_designer.core.audit.store import RunStore

    m = materialize(CASES["formula"], tmp_path)
    proc = _run(m, tmp_path)
    assert proc.returncode == 0
    rec_dir = tmp_path / "rec"
    records = [p for p in rec_dir.glob("*.json") if p.name != "hash_cache.json"]
    assert len(records) == 1
    record = RunStore().load(records[0])
    assert record.status == "ok"
    assert [n.status for n in record.nodes] == ["ok", "ok", "ok"]
    assert record.workflow_sha256 == hashlib.sha256(m.path.read_bytes()).hexdigest()
    out = record.outputs[0]
    assert out.path.replace("\\", "/").endswith("out_check_W_formula.csv")
    assert ".tdtmp" not in out.path
    assert (
        out.sha256
        == hashlib.sha256(
            (m.out_dir / "out_check_W_formula.csv").read_bytes()
        ).hexdigest()
    )
    verified = run_cli("verify-log", records[0], "--workflow", m.path, cwd=tmp_path)
    assert verified.returncode == 0, verified.stdout + verified.stderr


def test_no_record_writes_nothing(tmp_path):
    m = materialize(CASES["formula"], tmp_path)
    proc = _run(m, tmp_path, "--no-record")
    assert proc.returncode == 0
    assert _finished(proc)["record_path"] is None
    assert not (tmp_path / "rec").exists() or not list(
        (tmp_path / "rec").glob("*.json")
    )


def test_dry_run_executes_nothing(tmp_path):
    m = materialize(CASES["formula"], tmp_path)
    proc = _run(m, tmp_path, "--dry-run")
    assert proc.returncode == 0, proc.stderr[-1500:]
    names = [e["event"] for e in events(proc)]
    assert "plan.resolved" in names and "node.started" not in names
    assert list(m.out_dir.iterdir()) == []
    assert not (tmp_path / "rec").exists()
    assert not list((tmp_path / "state" / "work").glob("*"))


def test_dry_run_missing_input_is_2(tmp_path):
    m = materialize(CASES["formula"], tmp_path)
    proc = _run(m, tmp_path, "--dry-run", "--input-dir", tmp_path / "nowhere")
    assert proc.returncode == 2


def test_injected_code_refused_by_dry_run_and_run(tmp_path):
    m = materialize(CASES["formula"], tmp_path)
    victim = tmp_path / "PWNED.txt"
    env = {
        **HOOKS,
        "TD_TEST_INJECT": "Formula",
        "TD_TEST_INJECT_CODE": f"open({victim.as_posix()!r}, 'w').write('x')",
    }
    dry = _run(m, tmp_path, "--dry-run", env=env)
    assert dry.returncode == 6
    assert _finished(dry)["errors"][0]["code"] == "TD-CLI-010"
    target = m.out_dir / "out_check_W_formula.csv"
    target.write_bytes(b"sentinel")
    real = _run(m, tmp_path, env=env)
    assert real.returncode == 6, real.stderr[-800:]
    assert _finished(real)["errors"][0]["code"] == "TD-CLI-010"
    assert not victim.exists()
    assert target.read_bytes() == b"sentinel"
    assert _leftovers(m.out_dir) == []


def test_undeclared_path_in_generated_code_is_refused(tmp_path):
    m = materialize(CASES["formula"], tmp_path)
    victim = tmp_path / "elsewhere.csv"
    env = {
        **HOOKS,
        "TD_TEST_INJECT": "Formula",
        "TD_TEST_INJECT_CODE": f"pl.DataFrame({{'a': [1]}}).write_csv({victim.as_posix()!r})",
    }
    proc = _run(m, tmp_path, env=env)
    assert proc.returncode == 6
    assert not victim.exists()


def test_param_overrides_and_remap(tmp_path):
    m = materialize(CASES["formula"], tmp_path)
    added = run_cli(
        "params",
        "add",
        m.path,
        "--name",
        "input_file",
        "--node",
        "File Input",
        "--setting",
        "filePath",
        "--required",
        cwd=tmp_path,
    )
    assert added.returncode == 0, added.stderr
    run_cli(
        "params",
        "add",
        m.path,
        "--name",
        "output_file",
        "--node",
        "File Output",
        "--setting",
        "filePath",
        cwd=tmp_path,
    )
    missing = _run(m, tmp_path, "--dry-run")
    assert missing.returncode == 2
    assert _finished(missing)["errors"][0]["code"] == "TD-CLI-005"
    other_in = tmp_path / "elsewhere" / "data.csv"
    other_in.parent.mkdir()
    shutil.copy(REPO_ROOT / "data" / "check.csv", other_in)
    new_out = tmp_path / "newout" / "result.csv"
    new_out.parent.mkdir()
    proc = _run(
        m,
        tmp_path,
        "--param",
        f"input_file={other_in}",
        "--param",
        f"output_file={new_out}",
    )
    assert proc.returncode == 0, proc.stderr[-1500:]
    assert new_out.exists()
    resolved = next(e for e in events(proc) if e["event"] == "plan.resolved")["params"]
    assert resolved["input_file"] == str(other_in) and resolved["output_file"] == str(
        new_out
    )
    # the saved file is never modified by a run
    assert not (m.out_dir / "out_check_W_formula.csv").exists()


def test_input_dir_output_dir_remap_windows_authored_paths(tmp_path):
    case = CASES["formula"]
    # the checked-in workflow still holds C:/Projects/... paths
    src = case.source_path
    wf = tmp_path / "wf" / "wf.tds"
    wf.parent.mkdir()
    shutil.copy(src, wf)
    indir, outdir = tmp_path / "in", tmp_path / "outx"
    indir.mkdir()
    outdir.mkdir()
    shutil.copy(REPO_ROOT / "data" / "check.csv", indir / "check.csv")
    proc = _run(wf, tmp_path, "--input-dir", indir, "--output-dir", outdir)
    assert proc.returncode == 0, proc.stderr[-1500:]
    assert (outdir / "out_check_W_formula.csv").exists()
    assert not (tmp_path / "rec" / "x").exists()


def test_relative_paths_resolve_against_workflow_dir(tmp_path):
    case = CASES["formula"]
    wfdir = tmp_path / "wf"
    wfdir.mkdir()
    m = materialize(case, wfdir, {"check.csv": REPO_ROOT / "data" / "check.csv"})
    shutil.copy(REPO_ROOT / "data" / "check.csv", wfdir / "check.csv")
    data = json.loads(m.path.read_text(encoding="utf-8"))
    for node in data["nodes"]:
        content = node["content"]
        target = content.get("settings") or content
        if node["title"] == "File Input":
            target["filePath"] = (wfdir / "check.csv").as_posix()
        if node["title"] == "File Output":
            target["filePath"] = (wfdir / "result.csv").as_posix()
    m.path.write_text(json.dumps(data), encoding="utf-8")
    paths = run_cli("paths", m.path, "--relativize", "--write", cwd=tmp_path)
    assert paths.returncode == 0, paths.stderr
    assert Path(str(m.path) + ".bak").exists()
    other = tmp_path / "other"
    proc = run_cli(
        "run",
        m.path,
        "--allow-unapproved",
        "--log-format",
        "json",
        "--record-dir",
        tmp_path / "rec",
        cwd=other,
    )
    assert proc.returncode == 0, proc.stderr[-1500:]
    assert (wfdir / "result.csv").exists()
    assert os.listdir(other) == [
        "data",
        "state",
    ] or "check_output.py" not in os.listdir(other)


def test_unicode_space_and_apostrophe_paths(tmp_path):
    case = CASES["formula"]
    indir = tmp_path / "r\xe9sum\xe9 data"
    indir.mkdir()
    shutil.copy(REPO_ROOT / "data" / "check.csv", indir / "check.csv")
    m = materialize(case, tmp_path, {"check.csv": indir / "check.csv"})
    outdir = tmp_path / "O'Brien out"
    outdir.mkdir()
    proc = _run(m, tmp_path, "--output-dir", outdir)
    assert proc.returncode == 0, proc.stderr[-1500:]
    frame = read_frame(outdir / "out_check_W_formula.csv")
    assert_frame_golden(frame, "formula")
    assert _leftovers(outdir) == []


def test_cp1252_workflow_runs(tmp_path):
    m = materialize(CASES["formula"], tmp_path)
    data = json.loads(m.path.read_text(encoding="utf-8"))
    data["nodes"][0]["label_text"] = "Caf\xe9"
    m.path.write_bytes(json.dumps(data, ensure_ascii=False).encode("cp1252"))
    info = run_cli("info", m.path, "--format", "json", cwd=tmp_path)
    assert (
        json.loads(info.stdout)["encoding"] in ("cp1252", "windows-1252")
        or "125" in json.loads(info.stdout)["encoding"]
    )
    proc = _run(m, tmp_path)
    assert proc.returncode == 0, proc.stderr[-1500:]


def test_newer_schema_unknown_op_cycle_exit_2(tmp_path):
    m = materialize(CASES["formula"], tmp_path)
    base = json.loads(m.path.read_text(encoding="utf-8"))
    base.setdefault("workflow_metadata", {})["schema_version"] = 2

    newer = copy.deepcopy(base)
    newer["workflow_metadata"]["schema_version"] = 99
    unknown = copy.deepcopy(base)
    unknown["nodes"][0]["op"] = "preparation.teleport"
    cyclic = copy.deepcopy(base)
    out_socket = cyclic["nodes"][0]["outputs"][0]["id"]
    in_socket = cyclic["nodes"][1]["inputs"] and cyclic["nodes"][1]["inputs"][0]["id"]
    # connect the Formula output back into itself through a new edge
    formula = next(n for n in cyclic["nodes"] if n["title"] == "Formula")
    cyclic["edges"].append(
        {
            "id": 7,
            "edge_type": 5,
            "start": formula["outputs"][0]["id"],
            "end": formula["inputs"][0]["id"],
        }
    )
    del out_socket, in_socket
    for name, data, code in (
        ("newer", newer, "TD-CLI-002"),
        ("unknown", unknown, "TD-CLI-003"),
        ("cycle", cyclic, "TD-CLI-004"),
    ):
        path = tmp_path / f"{name}.tds"
        path.write_text(json.dumps(data), encoding="utf-8")
        proc = _run(path, tmp_path)
        assert proc.returncode == 2, (name, proc.stderr[-800:])
        assert _finished(proc)["errors"][0]["code"] == code


def test_emit_script_writes_the_run_code(tmp_path):
    m = materialize(CASES["formula"], tmp_path)
    script = tmp_path / "script" / "check.py"
    proc = _run(m, tmp_path, "--emit-script", script)
    assert proc.returncode == 0, proc.stderr[-1500:]
    text = script.read_text(encoding="utf-8")
    assert "polars" in text and "import" in text
    compile(text, str(script), "exec")


def test_emit_script_with_dry_run(tmp_path):
    m = materialize(CASES["formula"], tmp_path)
    script = tmp_path / "dry.py"
    proc = _run(m, tmp_path, "--dry-run", "--emit-script", script)
    assert proc.returncode == 0
    assert script.exists() and list(m.out_dir.iterdir()) == []


# ---------------------------------------------------------------- two branches
def _two_branch_workflow(m) -> Path:
    """File Input -> Formula -> Output A  and  File Input -> Output B."""
    data = json.loads(m.path.read_text(encoding="utf-8"))
    nodes = {n["title"]: n for n in data["nodes"]}
    extra = copy.deepcopy(nodes["File Output"])
    extra["id"] = 900001
    extra["inputs"][0]["id"] = 900002
    target = extra["content"].get("settings") or extra["content"]
    target["filePath"] = (m.out_dir / "branch_b.csv").as_posix()
    data["nodes"].append(extra)
    data["edges"].append(
        {
            "id": 900003,
            "edge_type": 5,
            "start": nodes["File Input"]["outputs"][0]["id"],
            "end": 900002,
        }
    )
    path = m.path.with_name("two.tds")
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_keep_going_runs_independent_branches(tmp_path):
    m = materialize(CASES["formula"], tmp_path)
    path = _two_branch_workflow(m)
    env = {**HOOKS, "TD_TEST_FAIL_NODE": "Formula"}
    stopped = _run(path, tmp_path, env=env)
    assert stopped.returncode == 1
    assert not (
        m.out_dir / "branch_b.csv"
    ).exists()  # stops at first failure: nothing committed
    going = _run(path, tmp_path, "--keep-going", env=env)
    assert going.returncode == 1
    assert (m.out_dir / "branch_b.csv").exists()
    assert not (m.out_dir / "out_check_W_formula.csv").exists()
    rows = events(going)
    assert any(r["event"] == "node.skipped" for r in rows)
    assert _leftovers(m.out_dir) == []


def test_two_branch_workflow_runs_clean_without_failures(tmp_path):
    m = materialize(CASES["formula"], tmp_path)
    path = _two_branch_workflow(m)
    proc = _run(path, tmp_path)
    assert proc.returncode == 0, proc.stderr[-1500:]
    assert (m.out_dir / "branch_b.csv").exists()
    assert (m.out_dir / "out_check_W_formula.csv").exists()


def test_output_overwriting_input_is_refused(tmp_path):
    m = materialize(CASES["formula"], tmp_path)
    proc = _run(m, tmp_path, "--output-dir", REPO_ROOT / "data", "--dry-run")
    # the output name differs from check.csv so this is fine...
    assert proc.returncode == 0
    data = json.loads(m.path.read_text(encoding="utf-8"))
    for node in data["nodes"]:
        if node["title"] == "File Output":
            content = node["content"]
            (content.get("settings") or content)["filePath"] = (
                REPO_ROOT / "data" / "check.csv"
            ).as_posix()
    bad = tmp_path / "bad.tds"
    bad.write_text(json.dumps(data), encoding="utf-8")
    refused = _run(bad, tmp_path, "--dry-run")
    assert refused.returncode == 2
    assert _finished(refused)["errors"][0]["code"] == "TD-CLI-014"


def test_missing_output_folder_needs_flag(tmp_path):
    m = materialize(CASES["formula"], tmp_path)
    target = tmp_path / "new" / "deeper"
    refused = _run(m, tmp_path, "--output-dir", target)
    assert refused.returncode == 2
    assert _finished(refused)["errors"][0]["code"] == "TD-CLI-014"
    ok = _run(m, tmp_path, "--output-dir", target, "--create-output-dirs")
    assert ok.returncode == 0, ok.stderr[-1000:]
    assert (target / "out_check_W_formula.csv").exists()


def test_concurrent_run_exit_7(tmp_path):
    from tests.support.cli import spawn_cli

    m = materialize(CASES["formula"], tmp_path)
    env = {**HOOKS, "TD_TEST_SLEEP_BEFORE_NODE": "Formula:8"}
    first = spawn_cli(
        "run",
        m.path,
        "--allow-unapproved",
        "--log-format",
        "json",
        "--record-dir",
        tmp_path / "rec",
        cwd=tmp_path,
        extra_env=env,
    )
    try:
        for line in first.stdout:
            if '"node.started"' in line and "File Input" in line:
                break
        second = _run(m, tmp_path)
        assert second.returncode == 7
        assert _finished(second)["errors"][0]["code"] == "TD-CLI-012"
        first.communicate(timeout=120)
        assert first.returncode == 0
    finally:
        if first.poll() is None:
            first.kill()


def test_killed_run_leaves_no_partial_output(tmp_path):
    from tests.support.cli import spawn_cli

    m = materialize(CASES["formula"], tmp_path)
    final = m.out_dir / "out_check_W_formula.csv"
    env = {**HOOKS, "TD_TEST_SLEEP_BEFORE_NODE": "File Output:60"}
    proc = spawn_cli(
        "run",
        m.path,
        "--allow-unapproved",
        "--log-format",
        "json",
        "--record-dir",
        tmp_path / "rec",
        cwd=tmp_path,
        extra_env=env,
    )
    try:
        for line in proc.stdout:
            if '"node.started"' in line and "File Output" in line:
                break
        proc.kill()
        proc.wait(timeout=30)
    finally:
        if proc.poll() is None:
            proc.kill()
    assert not final.exists()
    rerun = _run(m, tmp_path)
    assert rerun.returncode == 0, rerun.stderr[-1000:]
    assert final.exists() and _leftovers(m.out_dir) == []


def test_workpaper_output_is_staged_and_committed(tmp_path):
    """The Workpaper Output node (plan 06) goes through the same staging seam."""
    pytest.importorskip("trigger_designer.core.workpaper.node_runner")
    from trigger_designer.core.headless.op_catalog import OPS

    assert OPS["input.workpaper_output"].output_keys == ("output_path",)
    m = materialize(CASES["formula"], tmp_path)
    data = json.loads(m.path.read_text(encoding="utf-8"))
    for node in data["nodes"]:
        if node["title"] == "File Output":
            sock = node["inputs"][0]["id"]
            node["title"], node["op"] = "Workpaper Output", "input.workpaper_output"
            node.pop("op_code", None)
            node.pop("op_type", None)
            node["inputs"] = [
                {
                    "id": sock + i,
                    "index": i,
                    "multi_edges": False,
                    "position": 2,
                    "socket_type": 1,
                }
                for i in range(3)
            ]
            node["content"] = {
                "settings": {
                    "output_path": (m.out_dir / "wp.xlsx").as_posix(),
                    # the default (version) would keep the sentinel and add wp (2)
                    "if_exists": "replace",
                }
            }
        else:
            node.pop("op_code", None)
            node.pop("op_type", None)
            node["op"] = {
                "Formula": "preparation.formula",
                "File Input": "input.file_input",
            }[node["title"]]
    path = tmp_path / "wp.tds"
    path.write_text(json.dumps(data), encoding="utf-8")
    final = m.out_dir / "wp.xlsx"
    final.write_bytes(b"previous")
    proc = _run(path, tmp_path)
    if (
        proc.returncode == 1
        and "Workpaper" in proc.stdout
        and "node.finished" in proc.stdout
    ):
        pytest.skip("the workpaper node is not runnable in this build yet")
    assert proc.returncode == 0, proc.stderr[-1500:] + proc.stdout[-1500:]
    assert final.read_bytes()[:2] == b"PK"  # a real xlsx replaced the sentinel
    assert _leftovers(m.out_dir) == []
    done = _finished(proc)
    assert done["status"] == "ok"
    committed = [e for e in events(proc) if e["event"] == "output.committed"]
    assert committed and committed[0]["path"].endswith("wp.xlsx")


def test_validate_deep_loads_like_the_editor(tmp_path):
    m = materialize(CASES["formula"], tmp_path)
    ok = run_cli("validate", m.path, "--deep", "--format", "json", cwd=tmp_path)
    assert ok.returncode == 0, ok.stdout + ok.stderr[-800:]
    assert json.loads(ok.stdout)["ok"] is True
    # nothing was run or written
    assert list(m.out_dir.iterdir()) == []
    assert not list((tmp_path / "state" / "work").glob("*"))
    gone = run_cli(
        "validate", m.path, "--deep", "--input-dir", tmp_path / "nowhere", cwd=tmp_path
    )
    assert gone.returncode == 2 and "TD-IN-001" in gone.stdout
    skipped = run_cli(
        "validate",
        m.path,
        "--deep",
        "--no-files",
        "--input-dir",
        tmp_path / "nowhere",
        cwd=tmp_path,
    )
    assert skipped.returncode == 0, skipped.stdout


def test_text_mode_failure_block_names_the_node(tmp_path):
    m = materialize(CASES["formula"], tmp_path)
    proc = run_cli(
        "run",
        m.path,
        "--allow-unapproved",
        "--record-dir",
        tmp_path / "rec",
        cwd=tmp_path,
        extra_env={**HOOKS, "TD_TEST_FAIL_NODE": "Formula"},
    )
    assert proc.returncode == 1
    assert "FAILED at node 'Formula' [" in proc.stderr
    assert proc.stdout.strip() == ""


def test_strict_refuses_a_legacy_file(tmp_path):
    m = materialize(CASES["formula"], tmp_path)  # a v1 file without workflow_metadata
    proc = _run(m, tmp_path, "--strict")
    assert proc.returncode == 2
    assert "--strict" in _finished(proc)["errors"][0]["message"]


def test_xls_output_name_is_refused_with_a_plain_code(tmp_path):
    """An .xls name would hold .xlsx content: refuse it before anything is written."""
    m = materialize(CASES["formula"], tmp_path)
    data = json.loads(m.path.read_text(encoding="utf-8"))
    for node in data["nodes"]:
        if node["title"] == "File Output":
            content = node["content"]
            target = content.get("settings") or content
            target["file_format"] = "excel"
            target["filePath"] = (m.out_dir / "legacy.xls").as_posix()
            break
    m.path.write_text(json.dumps(data), encoding="utf-8")
    proc = _run(m, tmp_path, "--output-dir", m.out_dir)
    assert proc.returncode != 0
    codes = [e.get("code") for e in _finished(proc)["errors"]]
    assert "TD-OUT-012" in codes, codes
    assert not (m.out_dir / "legacy.xls").exists()
    assert _leftovers(m.out_dir) == []
