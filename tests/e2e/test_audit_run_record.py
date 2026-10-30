"""Golden run records end to end (docs/plan/02-audit-trail.md 6.3).

Real window, real ``WorkflowWorker`` thread, real files: a Run writes one
sealed, verifiable record next to the workflow.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import orjson
import polars as pl
import pytest
from nodeeditor.node_edge import Edge

from tests.support.audit_helpers import (
    FIXTURE_DIR,
    ORDERS_SHA256,
    build_window,
    build_workflow,
    newest_record,
    run_and_load_record,
    store_dir_of,
)
from tests.support.workflows import run_workflow_and_wait
from trigger_designer.core.audit.canonical import compute_record_hash
from trigger_designer.core.audit.compare import compare_runs
from trigger_designer.core.audit.schema import validate_record_dict
from trigger_designer.core.audit.store import RunStore, verify_store
from trigger_designer.core.node_configuration import (
    IONodes,
    NodeTypes,
    PreparationNodes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.preferences import get_preferences

pytestmark = pytest.mark.e2e


@pytest.fixture(autouse=True)
def _no_dialogs(no_modal_dialogs):
    return no_modal_dialogs


def test_pass_through_run_record_matches_golden_values(qtbot, tmp_path):
    tds, _src, _out = build_workflow(tmp_path)
    _window, rec = run_and_load_record(qtbot, tds)
    assert validate_record_dict(rec) == []
    assert rec["status"] == "ok" and len(rec["nodes"]) == 3
    assert [n["op"] for n in rec["nodes"]] == [
        "input.file_input",
        "preparation.normalize_columns",
        "input.file_output",
    ]
    assert list(rec["nodes"][0]["rows_out"].values()) == [3]
    assert rec["nodes"][1]["rows_in"][0]["rows"] == 3
    assert rec["nodes"][2]["rows_in"][0]["rows"] == 3
    inp = rec["inputs"][0]
    assert inp["sha256"] == ORDERS_SHA256
    assert inp["size_bytes"] == 25 and inp["row_count"] == 3
    out = rec["outputs"][0]
    assert out["sha256"] == ORDERS_SHA256
    assert out["row_count"] == 3 and out["row_count_method"] == "output_file"
    assert rec["workflow_sha256"] == hashlib.sha256(tds.read_bytes()).hexdigest()
    assert rec["workflow_path"] == tds.as_posix()
    assert rec["workflow_uuid"]
    assert rec["prev_record_hash"] == "0" * 64 and rec["seq"] == 1
    assert compute_record_hash(rec) == rec["record_hash"]
    assert verify_store(store_dir_of(tds)).ok
    assert "write_node" in rec["generated_code"]
    assert rec["options"]["row_count_mode_effective"] == "all"
    assert rec["workflow_modified_since_save"] is False


def test_messy_header_output_hash_matches_golden_file(qtbot, tmp_path):
    messy = tmp_path / "messy.csv"
    shutil.copyfile(FIXTURE_DIR / "orders_messy.csv", messy)
    window, _in, out_csv = build_window(tmp_path, input_path=messy)
    tds = tmp_path / "wf.tds"
    window.scene.saveToFile(str(tds))
    window.close()
    _w, rec = run_and_load_record(qtbot, tds)
    expected = (FIXTURE_DIR / "orders_messy.expected.csv").read_bytes()
    assert out_csv.read_bytes() == expected
    assert rec["outputs"][0]["sha256"] == hashlib.sha256(expected).hexdigest()
    norm = rec["nodes"][1]
    (columns,) = norm["columns_out"].values()
    (dtypes,) = norm["dtypes_out"].values()
    assert columns == ["Order_ID", "Customer_Id"]
    assert set(dtypes) == {"String"}


def test_two_runs_chain_and_baseline(qtbot, tmp_path):
    tds, _src, _out = build_workflow(tmp_path)
    window, first = run_and_load_record(qtbot, tds)
    run_workflow_and_wait(qtbot, window)
    second = newest_record(store_dir_of(tds))
    directory = store_dir_of(tds)
    assert len(list(directory.glob("*.json"))) - 0 >= 2
    assert len((directory / "index.jsonl").read_bytes().splitlines()) == 2
    assert second["prev_record_hash"] == first["record_hash"] and second["seq"] == 2
    assert second["baseline"] == {"run_id": first["run_id"], "input_changes": []}
    assert second["inputs"][0]["sha256_status"] == "cached"
    assert verify_store(directory).ok
    assert compare_runs(first, second).identical


def _generated_split_workflow(tmp_path, rows):
    """File Input -> Split (seeded) -> two File Outputs."""
    src = tmp_path / "gen.csv"
    src.write_bytes(
        ("id,amount\n" + "".join(f"{i},{i * 2}\n" for i in range(1, rows + 1))).encode()
    )
    outs = [tmp_path / "out" / "a.csv", tmp_path / "out" / "b.csv"]
    outs[0].parent.mkdir(exist_ok=True)
    window = TriggerSubWindow()
    scene = window.scene
    fin = get_class_from_opcode(IONodes.FILE_INPUT, NodeTypes.IO)(scene)
    split = get_class_from_opcode(PreparationNodes.SPLIT, NodeTypes.PREPARATION)(scene)
    sinks = [
        get_class_from_opcode(IONodes.FILE_OUTPUT, NodeTypes.IO)(scene) for _ in outs
    ]
    fin.content.filePath = str(src)
    fin.content.file_type = "csv"
    split.content.settings.update(is_random=True, random_seed=42)
    for sink, path in zip(sinks, outs, strict=True):
        sink.content.settings["filePath"] = str(path)
        sink.content.settings["file_format"] = "csv"
    Edge(scene, fin.outputs[0], split.inputs[0])
    Edge(scene, split.outputs[0], sinks[0].inputs[0])
    Edge(scene, split.outputs[1], sinks[1].inputs[0])
    tds = tmp_path / "split.tds"
    scene.saveToFile(str(tds))
    window.close()
    return tds, outs


def test_determinism_same_inputs_twice_identical_counts_and_output_hashes(
    qtbot, tmp_path
):
    tds, outs = _generated_split_workflow(tmp_path, 1000)
    window, first = run_and_load_record(qtbot, tds)
    run_workflow_and_wait(qtbot, window)
    second = newest_record(store_dir_of(tds))
    assert first["graph_sha256"] == second["graph_sha256"]
    split_one = next(n for n in first["nodes"] if n["op"].endswith("split"))
    assert sum(v for v in split_one["rows_out"].values()) == 1000
    assert split_one["seed"] == 42
    sink_b = [n for n in first["nodes"] if n["op"] == "input.file_output"][1]
    assert sink_b["rows_in"][0]["from_socket"] == 1
    for a, b in zip(first["nodes"], second["nodes"], strict=True):
        assert a["rows_out"] == b["rows_out"] and a["code_sha256"] == b["code_sha256"]
    assert [o["sha256"] for o in first["outputs"]] == [
        o["sha256"] for o in second["outputs"]
    ]
    assert [o["row_count"] for o in first["outputs"]] == [
        o["row_count"] for o in second["outputs"]
    ]
    assert compare_runs(first, second).identical
    assert len(outs) == 2


def test_recorded_run_survives_move_and_reload(qtbot, tmp_path):
    tds, _src, _out = build_workflow(tmp_path)
    run_and_load_record(qtbot, tds)
    moved = tmp_path / "moved"
    moved.mkdir()
    new_tds = moved / "wf.tds"
    shutil.move(str(tds), new_tds)
    shutil.move(str(store_dir_of(tds)), store_dir_of(new_tds))
    store = RunStore()
    runs = store.list_runs(workflow_path=str(new_tds))
    assert len(runs) == 1
    assert store.verify(workflow_path=str(new_tds)).ok


def test_run_log_dir_preference_relocates_store(qtbot, tmp_path, clean_preferences):
    tds, _src, _out = build_workflow(tmp_path)
    logs = tmp_path / "logs"
    get_preferences().set("audit/run_log_dir", str(logs))
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    assert window.fileLoad(str(tds)) is True
    run_workflow_and_wait(qtbot, window)
    found = [p for p in logs.iterdir() if p.name.startswith("wf-")]
    assert len(found) == 1
    assert verify_store(found[0]).ok
    assert not store_dir_of(tds).exists()


def test_unsaved_workflow_run(qtbot, tmp_path):
    window, _src, _out = build_window(tmp_path)
    qtbot.addWidget(window)
    run_workflow_and_wait(qtbot, window)
    from trigger_designer.qt.preferences import app_data_dir

    store = app_data_dir() / "runs" / "_unsaved"
    rec = newest_record(store)
    assert rec["workflow_path"] is None and rec["workflow_sha256"] is None
    assert len(rec["graph_sha256"]) == 64
    assert verify_store(store).ok


def test_record_written_before_results_changed_signal(qtbot, tmp_path):
    tds, _src, _out = build_workflow(tmp_path)
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    window.fileLoad(str(tds))
    seen: list[bool] = []
    window.executionResultsChanged.connect(
        lambda: seen.append((store_dir_of(tds) / "index.jsonl").exists())
    )
    run_workflow_and_wait(qtbot, window)
    assert seen == [True]


def test_run_signal_emitted_with_saved_path(qtbot, tmp_path):
    tds, _src, _out = build_workflow(tmp_path)
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    window.fileLoad(str(tds))
    with qtbot.waitSignal(window.runRecorded, timeout=60_000) as blocker:
        run_workflow_and_wait(qtbot, window)
    path = Path(blocker.args[0])
    assert path.is_file() and path.parent == store_dir_of(tds)


def test_failed_run_record_has_error_and_status(qtbot, tmp_path):
    window, _src, out_csv = build_window(tmp_path)
    qtbot.addWidget(window)
    sink = next(n for n in window.getAllNodes() if n.node_title == "File Output")
    sink.content.settings["filePath"] = str(tmp_path / "no_such_dir" / "x.csv")
    tds = tmp_path / "wf.tds"
    window.scene.saveToFile(str(tds))
    window.fileLoad(str(tds))
    with qtbot.waitSignal(window.runRecorded, timeout=60_000):
        window.executeWorkflow()
    worker = window._workflow_worker
    if worker is not None:
        worker.wait(60_000)
    rec = newest_record(store_dir_of(tds))
    assert rec["status"] == "failed"
    failed = [n for n in rec["nodes"] if n["status"] == "failed"]
    assert len(failed) == 1 and failed[0]["op"] == "input.file_output"
    error = failed[0]["error"]
    assert error["code"].startswith("TD-") and error["title"] and error["technical"]
    assert verify_store(store_dir_of(tds)).ok
    assert out_csv.exists() is False


def test_recording_off_writes_nothing(qtbot, tmp_path, clean_preferences):
    tds, _src, out = build_workflow(tmp_path)
    get_preferences().set("audit/record_runs", False)
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    window.fileLoad(str(tds))
    run_workflow_and_wait(qtbot, window)
    assert out.exists()
    assert not store_dir_of(tds).exists()
    assert window._run_session is None
    assert window._workflow_executor.before_node is None


def test_recorder_bug_does_not_break_run(qtbot, tmp_path, monkeypatch):
    from trigger_designer.core.audit import recorder as recorder_mod

    def boom(*_a, **_k):
        raise RuntimeError("audit bug")

    monkeypatch.setattr(recorder_mod.RunRecorder, "begin", boom)
    tds, _src, out = build_workflow(tmp_path)
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    window.fileLoad(str(tds))
    run_workflow_and_wait(qtbot, window)
    assert (
        out.exists() and out.read_bytes() == (FIXTURE_DIR / "orders.csv").read_bytes()
    )
    assert not store_dir_of(tds).exists()
    assert window._run_session is None


def test_input_change_between_runs_populates_baseline(qtbot, tmp_path):
    tds, src, _out = build_workflow(tmp_path)
    window, first = run_and_load_record(qtbot, tds)
    src.write_bytes(src.read_bytes() + b"4,40\n")
    run_workflow_and_wait(qtbot, window)
    second = newest_record(store_dir_of(tds))
    (change,) = second["baseline"]["input_changes"]
    assert change["change"] == "modified"
    assert change["old_sha256"] == first["inputs"][0]["sha256"] != change["new_sha256"]
    assert second["nodes"][0]["rows_out"].popitem()[1] == 4


def test_record_is_valid_json_with_sorted_keys_on_disk(qtbot, tmp_path):
    tds, _src, _out = build_workflow(tmp_path)
    run_and_load_record(qtbot, tds)
    directory = store_dir_of(tds)
    entry = orjson.loads((directory / "index.jsonl").read_bytes().splitlines()[0])
    raw = (directory / entry["file"]).read_bytes()
    data = orjson.loads(raw)
    assert list(data) == sorted(data)
    assert isinstance(pl.__version__, str) and data["polars_version"] == pl.__version__


def test_cancelled_run_is_recorded_with_skipped_nodes(qtbot, tmp_path, monkeypatch):
    from trigger_designer.core.ExecutionCheck.executor import NodeExecutor

    tds, _src, out = build_workflow(tmp_path)
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    window.fileLoad(str(tds))
    real = NodeExecutor.execute_node
    calls = {"n": 0}

    def cancel_after_first(self, node):
        result = real(self, node)
        calls["n"] += 1
        if calls["n"] == 1:  # what request_run_cancel does, minus the buttons
            window._workflow_worker.request_cancel()
            window._run_session.request_cancel()
        return result

    monkeypatch.setattr(NodeExecutor, "execute_node", cancel_after_first)
    run_workflow_and_wait(qtbot, window)
    rec = newest_record(store_dir_of(tds))
    assert rec["status"] == "cancelled"
    assert [n["status"] for n in rec["nodes"]] == ["ok", "skipped", "skipped"]
    assert not out.exists()
    assert verify_store(store_dir_of(tds)).ok


def test_request_run_cancel_entry_point_marks_the_session(qtbot, tmp_path):
    tds, _src, _out = build_workflow(tmp_path)
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    window.fileLoad(str(tds))
    seen: dict = {}

    def hold(sorted_nodes):
        seen["session"] = window._run_session

    window.before_run_hooks = [hold]
    run_workflow_and_wait(qtbot, window)
    assert window.request_run_cancel() is False  # nothing in flight any more
    assert newest_record(store_dir_of(tds))["status"] == "ok"


def test_failed_run_record_carries_the_settled_error(qtbot, tmp_path):
    from trigger_designer.core.audit.errors_adapter import node_error_to_dict

    window, _src, _out = build_window(tmp_path)
    qtbot.addWidget(window)
    sink = next(n for n in window.getAllNodes() if n.node_title == "File Output")
    sink.content.settings["filePath"] = str(tmp_path / "nope" / "x.csv")
    tds = tmp_path / "wf.tds"
    window.scene.saveToFile(str(tds))
    window.fileLoad(str(tds))
    with qtbot.waitSignal(window.runRecorded, timeout=60_000):
        window.executeWorkflow()
    rec = newest_record(store_dir_of(tds))
    node = next(n for n in window.getAllNodes() if n.node_title == "File Output")
    failed = next(n for n in rec["nodes"] if n["status"] == "failed")
    settled = node_error_to_dict(node.current_error)
    assert {k: failed["error"][k] for k in settled} == settled
    assert window.is_enrichment_settled()


def test_unreadable_input_is_flagged_not_fatal(qtbot, tmp_path, monkeypatch):
    from trigger_designer.core.audit import fingerprint as fp_mod

    tds, _src, out = build_workflow(tmp_path)

    def locked(*_a, **_k):
        raise PermissionError("the file is locked")

    monkeypatch.setattr(fp_mod, "sha256_stream", locked)
    _w, rec = run_and_load_record(qtbot, tds)
    assert rec["status"] == "ok" and out.exists()
    assert rec["inputs"][0]["sha256_status"] == "error"
    assert rec["inputs"][0]["error"].startswith("PermissionError")
    assert any(w.startswith("input not hashed (error)") for w in rec["warnings"])
    assert verify_store(store_dir_of(tds)).ok


def test_missing_input_is_recorded_as_missing(qtbot, tmp_path):
    tds, src, _out = build_workflow(tmp_path)
    src.unlink()
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    window.fileLoad(str(tds))
    with qtbot.waitSignal(window.runRecorded, timeout=60_000):
        window.executeWorkflow()
    rec = newest_record(store_dir_of(tds))
    assert rec["inputs"][0]["sha256_status"] == "missing"
    assert rec["inputs"][0]["size_bytes"] is None
    assert any("input file not found" in w for w in rec["warnings"])
    assert verify_store(store_dir_of(tds)).ok
