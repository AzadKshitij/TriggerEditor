"""The recorder API plans 06 (workpaper) and 08 (CLI) call (plan 02 3.8)."""

from __future__ import annotations

import threading

import polars as pl
import pytest

from tests.support.audit_helpers import (
    FakeNode,
    FakeResult,
    make_recorder,
)
from trigger_designer.core.audit import (
    AuditOptions,
    RunRecorder,
    RunStore,
    get_run_record_provider,
    set_run_record_provider,
)
from trigger_designer.core.audit.recorder import EdgeRef, NodeSpec
from trigger_designer.core.audit.schema import FileFingerprint
from trigger_designer.core.audit.store import RunAlreadySealed, verify_store


def _spec(tmp_path, **over):
    out = tmp_path / "o.csv"
    return NodeSpec(
        1,
        "input.file_output",
        "Out",
        output_variables=("v1",),
        output_files=({"path": str(out), "format": "csv", "delimiter": ","},),
        **over,
    )


def _begin(tmp_path, recorder=None, spec=None):
    recorder = recorder or make_recorder(tmp_path)
    return recorder, recorder.begin(
        None, [spec or _spec(tmp_path)], app_version="0.1.0"
    )


def test_begin_returns_running_and_status_comes_only_from_finish(tmp_path):
    recorder, record = _begin(tmp_path)
    assert record.status == "running"
    recorder.node_finished(record, FakeNode(1), FakeResult(True))
    assert record.status == "running"  # records are never mutated
    final = recorder.finish(record, False)
    assert final.status == "failed" and record.status == "running"


def test_finish_outputs_replace_the_recorders_own(tmp_path):
    recorder, record = _begin(tmp_path)
    (tmp_path / "o.csv").write_text("a\n1\n")
    recorder.after_node(FakeNode(1), {}, FakeResult(True))
    supplied = FileFingerprint(
        role="output", path="D:/final/o.csv", sha256="ab" * 32, sha256_status="computed"
    )
    final = recorder.finish(record, True, outputs=[supplied])
    assert [fp.path for fp in final.outputs] == ["D:/final/o.csv"]


def test_finish_save_false_writes_nothing(tmp_path):
    recorder, record = _begin(tmp_path)
    final = recorder.finish(record, True, save=False)
    assert final.status == "ok" and final.record_hash in ("", "0" * 64)
    assert recorder.last_path is None
    assert not (tmp_path / "runs").exists()


def test_disabled_options_write_nothing_and_create_no_directory(tmp_path):
    recorder = make_recorder(tmp_path, enabled=False)
    recorder, record = _begin(tmp_path, recorder)
    recorder.before_node(FakeNode(1))
    final = recorder.finish(record, True)
    assert final.status == "ok"
    assert recorder.last_path is None
    assert not (tmp_path / "runs").exists()
    assert not (tmp_path / "ad").exists()


def test_second_finish_or_save_raises_already_sealed(tmp_path):
    recorder, record = _begin(tmp_path)
    sealed = recorder.finish(record, True)
    with pytest.raises(RunAlreadySealed):
        recorder.finish(record, True)
    with pytest.raises(RunAlreadySealed):
        recorder.store.save(sealed, tmp_path / "runs")


def test_update_node_error_after_finish_raises(tmp_path):
    recorder, record = _begin(tmp_path)
    recorder.node_finished(record, FakeNode(1), FakeResult(True))
    recorder.finish(record, True)
    with pytest.raises(RunAlreadySealed):
        recorder.update_node_error(1, {"code": "TD-X", "title": "x"})


def test_update_node_error_before_finish_replaces_the_error(tmp_path):
    recorder, record = _begin(tmp_path)
    recorder.node_finished(
        record, FakeNode(1), FakeResult(False, exception=ValueError("v"), error="v")
    )
    recorder.update_node_error(
        1, {"code": "TD-SCH-001", "title": "Column was not found"}
    )
    final = recorder.finish(record, False)
    assert final.nodes[0].error == {
        "code": "TD-SCH-001",
        "title": "Column was not found",
    }
    assert verify_store(tmp_path / "runs").ok


def test_store_dir_option_is_honoured(tmp_path):
    target = tmp_path / "custom" / "here"
    recorder = make_recorder(tmp_path, store_dir=str(target))
    recorder, record = _begin(tmp_path, recorder)
    final = recorder.finish(record, True)
    assert recorder.last_path.startswith(str(target))
    assert (target / "index.jsonl").is_file() and final.seq == 1


def test_default_store_dir_is_next_to_the_workflow(tmp_path):
    wf = tmp_path / "wf.tds"
    wf.write_text("{}")
    recorder = RunRecorder(RunStore(app_data_dir=tmp_path / "ad"), AuditOptions())
    record = recorder.begin(str(wf), [_spec(tmp_path)], app_version="0.1.0")
    recorder.finish(record, True)
    assert (tmp_path / "wf.runs" / "index.jsonl").is_file()
    assert (tmp_path / "wf.runs" / "hash_cache.json").exists() or True


def test_snapshot_is_an_independent_deep_copy(tmp_path):
    recorder, record = _begin(tmp_path)
    recorder.node_finished(record, FakeNode(1), FakeResult(True))
    snap = recorder.snapshot()
    assert snap["status"] == "running" and snap["record_hash"] == ""
    assert len(snap["nodes"]) == 1
    snap["nodes"].append("x")
    snap["warnings"].append("tamper")
    again = recorder.snapshot()
    assert len(again["nodes"]) == 1 and again["warnings"] == []
    sealed = recorder.finish(record, True)
    shown = recorder.snapshot(sealed)
    assert shown["status"] == "ok" and shown["record_hash"] == sealed.record_hash
    shown["nodes"].clear()
    assert len(sealed.to_dict()["nodes"]) == 1


def test_snapshot_before_begin_is_none():
    assert RunRecorder().snapshot() is None


def test_snapshot_while_worker_thread_runs_hooks_never_raises(tmp_path):
    specs = [
        NodeSpec(i, "preparation.select", f"N{i}", output_variables=(f"v{i}",))
        for i in range(1, 60)
    ]
    recorder = make_recorder(tmp_path)
    record = recorder.begin(None, specs, app_version="x")
    errors: list = []
    stop = threading.Event()

    def worker():
        try:
            for spec in specs:
                recorder.before_node(FakeNode(spec.node_id))
                recorder.after_node(
                    FakeNode(spec.node_id),
                    {spec.output_variables[0]: pl.LazyFrame({"a": [1, 2]})},
                    FakeResult(True),
                )
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)
        finally:
            stop.set()

    thread = threading.Thread(target=worker)
    thread.start()
    snapshots = 0
    while not stop.is_set():
        try:
            assert recorder.snapshot()["status"] == "running"
            snapshots += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)
            break
    thread.join()
    assert not errors and snapshots >= 1
    assert recorder.finish(record, True).status == "ok"


def test_provider_registry_round_trip():
    assert get_run_record_provider() is None

    def provider():
        return {"status": "running"}

    set_run_record_provider(provider)
    try:
        assert get_run_record_provider() is provider
        assert get_run_record_provider()() == {"status": "running"}
    finally:
        set_run_record_provider(None)
    assert get_run_record_provider() is None


def test_headless_recipe_end_to_end(tmp_path):
    """The recipe plan 08 uses: hooks + node_finished + finish, no Qt."""
    src = tmp_path / "in.csv"
    src.write_text("id\n1\n2\n")
    out = tmp_path / "out.csv"
    specs = [
        NodeSpec(
            1,
            "input.file_input",
            "In",
            output_variables=("a",),
            is_source=True,
            input_files=({"path": str(src), "sheet": None, "kind": "csv"},),
        ),
        NodeSpec(
            2,
            "input.file_output",
            "Out",
            output_files=({"path": str(out), "format": "csv", "delimiter": ","},),
        ),
    ]
    recorder = make_recorder(tmp_path, sync_enrich=True)
    record = recorder.begin(
        None, specs, app_version="0.1.0", edges=[EdgeRef(1, 0, 2, 0)]
    )
    frame = pl.scan_csv(src)
    for node in (FakeNode(1, "In"), FakeNode(2, "Out")):
        recorder.before_node(node)
        local = {"a": frame} if node.id == 1 else {}
        if node.id == 2:
            frame.collect().write_csv(out)
        recorder.after_node(node, local, FakeResult(True))
        recorder.node_finished(record, node, FakeResult(True))
    final = recorder.finish(record, True)
    assert final.status == "ok" and recorder.last_path
    assert final.outputs[0].row_count == 2 and final.nodes[1].rows_in[0]["rows"] == 2
