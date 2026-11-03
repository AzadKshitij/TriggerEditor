"""The Qt bridge: preferences -> options, settings snapshots, node specs, session."""

from __future__ import annotations

import polars as pl
import pytest
from nodeeditor.node_edge import Edge

from tests.support.audit_helpers import FakeResult, build_window
from trigger_designer.core.audit.recorder import (
    get_run_record_provider,
    set_run_record_provider,
)
from trigger_designer.core.audit.store import verify_store
from trigger_designer.core.ExecutionCheck.executor import NodeExecutor
from trigger_designer.core.node_configuration import (
    IONodes,
    NodeTypes,
    PreparationNodes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.helpers import audit_bridge
from trigger_designer.qt.helpers.audit_bridge import (
    RunSession,
    node_spec_from_node,
    node_specs_from_window,
    options_from_preferences,
    snapshot_settings,
)
from trigger_designer.qt.preferences import get_preferences


def _node(window, title):
    return next(n for n in window.getAllNodes() if n.node_title == title)


# -- options --------------------------------------------------------------------
def test_options_defaults(clean_preferences):
    options = options_from_preferences()
    assert options.record_identity and options.hash_inputs and options.hash_outputs
    assert options.hash_max_mb == 2048 and options.exact_counts_max_mb == 256
    assert options.row_counts == "auto" and options.embed_code
    assert options.app_data_dir and options.enabled and not options.sync_enrich


def test_unknown_row_counts_value_is_auto(clean_preferences):
    get_preferences().set("audit/row_counts", "nonsense")
    assert options_from_preferences().row_counts == "auto"
    get_preferences().set("audit/row_counts", "sink")
    assert options_from_preferences().row_counts == "sink"


def test_preferences_are_picked_up(clean_preferences):
    prefs = get_preferences()
    prefs.set("audit/record_identity", False)
    prefs.set("audit/hash_max_mb", 7)
    prefs.set("audit/embed_code", False)
    prefs.set("errors/redact_values", True)
    options = options_from_preferences()
    assert not options.record_identity and options.hash_max_mb == 7
    assert not options.embed_code and options.redact_values


# -- settings snapshot ------------------------------------------------------------
def test_file_input_snapshot_does_not_read_the_file(tmp_path, monkeypatch):
    window, src, _out = build_window(tmp_path)
    fin = _node(window, "File Input")

    def boom(*_a, **_k):
        raise AssertionError("the snapshot must not read input files")

    monkeypatch.setattr(pl, "read_csv", boom)
    monkeypatch.setattr(pl, "scan_csv", boom)
    settings = snapshot_settings(fin.content)
    assert settings["filePath"] == str(src).replace("\\", "/")
    assert settings["file_type"] == "csv"
    for dropped in ("schema_snapshot", "available_sheets", "file_metadata"):
        assert dropped not in settings
    window.close()


def test_shaping_settings_are_flattened_and_seed_is_visible(tmp_path):
    window = TriggerSubWindow()
    split = get_class_from_opcode(PreparationNodes.SPLIT, NodeTypes.PREPARATION)(
        window.scene
    )
    split.content.settings.update(is_random=True, random_seed=42)
    settings = snapshot_settings(split.content)
    assert settings["random_seed"] == 42 and "settings" not in settings
    assert node_spec_from_node(split, window).settings["random_seed"] == 42
    window.close()


def test_snapshot_survives_a_broken_content():
    class Broken:
        def get_serialized_state(self):
            raise RuntimeError("nope")

    assert snapshot_settings(Broken()) == {
        "_error": "settings unavailable: RuntimeError"
    }
    assert snapshot_settings(None) == {}


# -- node specs ---------------------------------------------------------------------
def test_node_specs_of_file_input_and_output(tmp_path):
    window, src, out = build_window(tmp_path)
    fin, fout = _node(window, "File Input"), _node(window, "File Output")
    spec_in = node_spec_from_node(fin, window)
    assert spec_in.op == "input.file_input" and spec_in.is_source
    assert [f["path"] for f in spec_in.input_files] == [str(src)]
    assert spec_in.input_files[0]["kind"] == "csv" and spec_in.output_files == ()
    assert spec_in.n_outputs == 1
    spec_out = node_spec_from_node(fout, window)
    assert spec_out.op == "input.file_output" and not spec_out.is_source
    assert spec_out.output_files[0]["path"] == str(out)
    assert spec_out.output_files[0]["format"] == "csv"
    assert spec_out.input_files == ()
    window.close()


def test_file_input_folder_lists_every_file(tmp_path):
    window, _src, _out = build_window(tmp_path)
    folder = tmp_path / "many"
    folder.mkdir()
    for name in ("b.csv", "a.csv"):
        (folder / name).write_text("id\n1\n")
    fin = _node(window, "File Input")
    fin.content.filePath = str(folder)
    spec = node_spec_from_node(fin, window)
    assert [
        f["path"].replace("\\", "/").rsplit("/", 1)[-1] for f in spec.input_files
    ] == [
        "a.csv",
        "b.csv",
    ]
    window.close()


def test_content_hooks_override_the_defaults(tmp_path):
    window, _src, _out = build_window(tmp_path)
    fin = _node(window, "File Input")
    fin.content.audit_input_files = lambda: [
        {"path": str(tmp_path / "x.csv"), "sheet": "S", "kind": "csv"}
    ]
    spec = node_spec_from_node(fin, window)
    assert spec.input_files == (
        {"path": str(tmp_path / "x.csv"), "sheet": "S", "kind": "csv"},
    )
    window.close()


def test_edges_carry_real_socket_indexes_for_a_split(tmp_path):
    window = TriggerSubWindow()
    scene = window.scene
    fin = get_class_from_opcode(IONodes.FILE_INPUT, NodeTypes.IO)(scene)
    split = get_class_from_opcode(PreparationNodes.SPLIT, NodeTypes.PREPARATION)(scene)
    sinks = [
        get_class_from_opcode(IONodes.FILE_OUTPUT, NodeTypes.IO)(scene) for _ in "ab"
    ]
    Edge(scene, fin.outputs[0], split.inputs[0])
    Edge(scene, split.outputs[0], sinks[0].inputs[0])
    Edge(scene, split.outputs[1], sinks[1].inputs[0])
    nodes = [fin, split, *sinks]
    specs, edges = node_specs_from_window(window, nodes)
    assert [s.node_id for s in specs] == [n.id for n in nodes]
    by_dst = {e.dst_node_id: e for e in edges}
    assert by_dst[sinks[0].id].src_socket == 0
    assert by_dst[sinks[1].id].src_socket == 1
    assert by_dst[split.id].src_node_id == fin.id
    split_spec = specs[1]
    assert split_spec.n_outputs == 2 and len(split_spec.output_variables) == 2
    # edges to nodes outside the run are dropped
    _specs, partial = node_specs_from_window(window, [fin, split])
    assert len(partial) == 1
    window.close()


# -- session -------------------------------------------------------------------------
def test_session_start_installs_and_clears_the_provider(tmp_path, clean_preferences):
    window, _src, _out = build_window(tmp_path)
    executor = NodeExecutor()
    nodes = window.getAllNodes()
    session = RunSession.start(window, nodes, executor)
    try:
        assert session is not None
        assert executor.before_node == session.recorder.before_node
        assert executor.after_node == session.recorder.after_node
        snap = get_run_record_provider()()
        assert snap["status"] == "running" and snap["nodes"] == []
    finally:
        session.abort()
        set_run_record_provider(None)
    window.close()


def test_session_is_none_when_recording_is_off(tmp_path, clean_preferences):
    window, _src, _out = build_window(tmp_path)
    get_preferences().set("audit/record_runs", False)
    executor = NodeExecutor()
    assert RunSession.start(window, window.getAllNodes(), executor) is None
    assert executor.before_node is None and executor.after_node is None
    window.close()


def test_abort_discards_marker_and_folder(tmp_path, clean_preferences):
    tds = tmp_path / "wf.tds"
    window, _src, _out = build_window(tmp_path)
    window.scene.saveToFile(str(tds))
    session = RunSession.start(window, window.getAllNodes(), NodeExecutor())
    runs = tds.with_suffix(".runs")
    assert runs.exists() and list(runs.glob("*.started"))
    session.abort()
    assert not runs.exists()
    window.close()


def test_request_cancel_marks_the_record_cancelled(tmp_path, clean_preferences):
    tds = tmp_path / "wf.tds"
    window, _src, _out = build_window(tmp_path)
    window.scene.saveToFile(str(tds))
    session = RunSession.start(window, window.getAllNodes(), NodeExecutor())
    session.request_cancel()
    path = session.finish(False)
    assert path
    from tests.support.audit_helpers import newest_record

    record = newest_record(tds.with_suffix(".runs"))
    assert record["status"] == "cancelled"
    assert {n["status"] for n in record["nodes"]} == {"skipped"}
    assert verify_store(tds.with_suffix(".runs")).ok
    window.close()


def test_a_cancel_that_arrives_after_everything_ran_does_not_cancel(
    tmp_path, clean_preferences
):
    tds = tmp_path / "wf.tds"
    window, _src, _out = build_window(tmp_path)
    window.scene.saveToFile(str(tds))
    session = RunSession.start(window, window.getAllNodes(), NodeExecutor())
    session.request_cancel()
    session.finish(True)
    from tests.support.audit_helpers import newest_record

    assert newest_record(tds.with_suffix(".runs"))["status"] == "ok"
    window.close()


def test_finish_twice_returns_the_same_path(tmp_path, clean_preferences):
    window, _src, _out = build_window(tmp_path)
    session = RunSession.start(window, window.getAllNodes(), NodeExecutor())
    first = session.finish(True)
    assert session.finish(True) == first and session.sealed
    window.close()


def test_node_callbacks_never_raise(tmp_path, clean_preferences):
    window, _src, _out = build_window(tmp_path)
    session = RunSession.start(window, window.getAllNodes(), NodeExecutor())
    node = window.getAllNodes()[0]
    session.node_finished(node, object())  # not an ExecutionResult
    session.node_errored(node, RuntimeError("x"))
    session.node_finished(node, FakeResult(True))
    session.abort()
    window.close()


def test_failed_run_waits_for_enrichment_then_seals(tmp_path, clean_preferences):
    tds = tmp_path / "wf.tds"
    window, _src, _out = build_window(tmp_path)
    window.scene.saveToFile(str(tds))
    window._pending_enrichments = 1  # a failed node's error is still being enriched
    session = RunSession.start(window, window.getAllNodes(), NodeExecutor())
    done: list = []
    session.finish_when_settled(False, done.append)
    assert done == [] and not session.sealed
    window._enrichment_finished()
    assert len(done) == 1 and done[0]
    assert window.is_enrichment_settled()
    window.close()


def test_failed_run_seals_after_the_guard_when_enrichment_never_settles(
    qtbot, tmp_path, clean_preferences, monkeypatch
):
    monkeypatch.setattr(audit_bridge, "SETTLE_GUARD_MS", 30)
    tds = tmp_path / "wf.tds"
    window, _src, _out = build_window(tmp_path)
    window.scene.saveToFile(str(tds))
    window._pending_enrichments = 1
    session = RunSession.start(window, window.getAllNodes(), NodeExecutor())
    done: list = []
    session.finish_when_settled(False, done.append)
    qtbot.waitUntil(lambda: bool(done), timeout=5000)
    assert done[0]
    window._enrichment_finished()  # the late settle must not seal twice
    assert len(done) == 1
    window.close()


def test_successful_run_does_not_wait(tmp_path, clean_preferences):
    window, _src, _out = build_window(tmp_path)
    window._pending_enrichments = 5
    session = RunSession.start(window, window.getAllNodes(), NodeExecutor())
    done: list = []
    session.finish_when_settled(True, done.append)
    assert len(done) == 1
    window.close()


def test_changed_inputs_are_logged_as_warnings(tmp_path, clean_preferences):
    tds = tmp_path / "wf.tds"
    window, src, _out = build_window(tmp_path)
    window.scene.saveToFile(str(tds))
    warnings: list[str] = []
    window.logWarning = warnings.append
    nodes = window.getAllNodes()
    for content in (b"a", b"b"):
        src.write_bytes(b"id,amount\n" + content + b",1\n")
        executor = NodeExecutor()
        session = RunSession.start(window, nodes, executor)
        session.recorder.before_node(_node(window, "File Input"))
        session.finish(True)
    assert any(w.startswith("Input changed since the previous run:") for w in warnings)
    get_preferences().set("audit/warn_on_input_change", False)
    warnings.clear()
    src.write_bytes(b"id,amount\nc,1\n")
    session = RunSession.start(window, nodes, NodeExecutor())
    session.recorder.before_node(_node(window, "File Input"))
    session.finish(True)
    assert warnings == []
    window.close()


def test_snapshot_current_after_seal_returns_the_sealed_record(
    tmp_path, clean_preferences
):
    window, _src, _out = build_window(tmp_path)
    session = RunSession.start(window, window.getAllNodes(), NodeExecutor())
    live = session.snapshot_current()
    assert live["status"] == "running"
    session.finish(True)
    sealed = session.snapshot_current()
    assert sealed["status"] == "ok" and sealed["record_hash"]
    set_run_record_provider(None)
    window.close()


@pytest.mark.parametrize("prefix", ["audit/record_runs"])
def test_preference_defaults_exist(prefix, clean_preferences):
    from trigger_designer.qt.preferences import DEFAULTS

    assert prefix in DEFAULTS
    for key in (
        "audit/run_log_dir",
        "audit/record_identity",
        "audit/hash_inputs",
        "audit/hash_outputs",
        "audit/hash_max_mb",
        "audit/row_counts",
        "audit/exact_counts_max_mb",
        "audit/embed_code",
        "audit/warn_on_input_change",
    ):
        assert key in DEFAULTS
