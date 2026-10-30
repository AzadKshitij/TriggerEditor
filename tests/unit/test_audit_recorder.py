"""The run recorder, driven by hand with fakes (plan 02 sections 3.5, 3.7, 4)."""

from __future__ import annotations

import hashlib
import itertools
import math
from pathlib import Path

import polars as pl
import pytest

from tests.support.audit_helpers import (
    ORDERS_SHA256,
    FakeNode,
    FakeResult,
    drive,
    make_recorder,
)
from trigger_designer.core.audit import counting as counting_mod
from trigger_designer.core.audit.counting import CountError
from trigger_designer.core.audit.recorder import (
    EdgeRef,
    NodeSpec,
    extract_seed,
    sanitize,
)
from trigger_designer.core.audit.store import verify_store

CSV = "id,amount\n1,10\n2,20\n3,30\n"


def _csv(tmp_path: Path, name="in.csv", text=CSV) -> Path:
    path = tmp_path / name
    path.write_bytes(text.encode())
    return path


def _specs(tmp_path, *, out_name="out.csv", settings=None):
    src = _csv(tmp_path)
    out = tmp_path / out_name
    return (
        [
            NodeSpec(
                1,
                "input.file_input",
                "File Input",
                settings={"delimiter": ","},
                n_outputs=1,
                output_variables=("var_in_1",),
                is_source=True,
                input_files=({"path": str(src), "sheet": None, "kind": "csv"},),
            ),
            NodeSpec(
                2,
                "preparation.normalize_columns",
                "Normalize",
                settings=settings or {"case_mode": "keep"},
                n_outputs=1,
                output_variables=("var_norm_2",),
            ),
            NodeSpec(
                3,
                "input.file_output",
                "File Output",
                input_files=(),
                output_files=({"path": str(out), "format": "csv", "delimiter": ","},),
            ),
        ],
        [EdgeRef(1, 0, 2, 0), EdgeRef(2, 0, 3, 0)],
        src,
        out,
    )


def _frames(src_rows=3):
    frame = pl.DataFrame(
        {"id": [str(i) for i in range(1, src_rows + 1)], "amount": ["10"] * src_rows}
    )
    return frame


def _run_pipeline(tmp_path, recorder, *, rows=3, write_rows=None, specs_edges=None):
    specs, edges, _src, out = specs_edges or _specs(tmp_path)
    record = recorder.begin(
        str(tmp_path / "wf.tds") if (tmp_path / "wf.tds").exists() else None,
        specs,
        app_version="0.1.0",
        edges=edges,
    )
    nodes = [FakeNode(s.node_id, s.title) for s in specs]
    frame = _frames(rows)

    def write_output():
        _frames(write_rows if write_rows is not None else rows).write_csv(out)

    variables = {1: {"var_in_1": frame.lazy()}, 2: {"var_norm_2": frame.lazy()}, 3: {}}
    # the output file appears when the sink node runs
    for node in nodes:
        if node.id == 3:
            write_output()
    drive(recorder, record, nodes, variables)
    return record, nodes


def test_begin_computes_hashes_and_mode(tmp_path):
    wf = tmp_path / "wf.tds"
    wf.write_text('{"nodes": []}', encoding="utf-8")
    specs, edges, *_ = _specs(tmp_path)
    recorder = make_recorder(tmp_path)
    record = recorder.begin(
        str(wf), specs, app_version="0.1.0", edges=edges, workflow_uuid="u-1"
    )
    assert record.status == "running"
    assert record.workflow_sha256 == hashlib.sha256(wf.read_bytes()).hexdigest()
    assert record.workflow_path == wf.as_posix()
    assert record.workflow_uuid == "u-1"
    assert record.options["row_count_mode_effective"] == "all"
    assert record.options["total_input_bytes"] == len(CSV)
    assert len(record.run_id) == 32
    assert recorder.mode == "all"


def test_begin_unsaved_workflow_has_graph_hash_only(tmp_path):
    specs, edges, *_ = _specs(tmp_path)
    record = make_recorder(tmp_path).begin(
        None, specs, app_version="0.1.0", edges=edges
    )
    assert record.workflow_path is None and record.workflow_sha256 is None
    assert len(record.graph_sha256) == 64


def test_graph_hash_is_order_insensitive_and_setting_sensitive(tmp_path):
    specs, edges, *_ = _specs(tmp_path)
    one = make_recorder(tmp_path).begin(None, specs, app_version="x", edges=edges)
    two = make_recorder(tmp_path).begin(
        None, list(reversed(specs)), app_version="x", edges=list(reversed(edges))
    )
    assert one.graph_sha256 == two.graph_sha256
    changed, edges2, *_ = _specs(tmp_path, settings={"case_mode": "upper"})
    three = make_recorder(tmp_path).begin(None, changed, app_version="x", edges=edges2)
    assert three.graph_sha256 != one.graph_sha256


def test_mode_switches_to_sink_over_threshold(tmp_path):
    specs, edges, *_ = _specs(tmp_path)
    recorder = make_recorder(tmp_path, exact_counts_max_mb=0)
    record = recorder.begin(None, specs, app_version="x", edges=edges)
    assert record.options["row_count_mode_effective"] == "sink"


def test_identity_off_nulls_user_and_machine(tmp_path):
    specs, edges, *_ = _specs(tmp_path)
    on = make_recorder(tmp_path).begin(None, specs, app_version="x", edges=edges)
    off = make_recorder(tmp_path, record_identity=False).begin(
        None, specs, app_version="x", edges=edges
    )
    assert on.user and on.machine
    assert off.user is None and off.machine is None


def test_ok_run_counts_hashes_and_verifies(tmp_path):
    recorder = make_recorder(tmp_path)
    record, _nodes = _run_pipeline(tmp_path, recorder)
    final = recorder.finish(record, True)
    assert final.status == "ok" and final.seq == 1
    assert [n.status for n in final.nodes] == ["ok", "ok", "ok"]
    assert final.nodes[0].rows_out == {"var_in_1": 3}
    assert final.nodes[0].count_method == {"var_in_1": "materialized"}
    assert final.nodes[0].columns_out == {"var_in_1": ["id", "amount"]}
    assert final.nodes[0].dtypes_out == {"var_in_1": ["String", "String"]}
    assert final.nodes[1].rows_in == [
        {
            "socket": 0,
            "from_node_id": 1,
            "from_socket": 0,
            "variable": "var_in_1",
            "rows": 3,
        }
    ]
    assert final.nodes[2].rows_in[0]["rows"] == 3 and final.nodes[2].rows_out == {}
    assert final.inputs[0].sha256 == hashlib.sha256(CSV.encode()).hexdigest()
    assert final.inputs[0].row_count == 3
    assert final.outputs[0].row_count == 3
    assert final.outputs[0].row_count_method == "output_file"
    assert final.generated_code == "x = 1\n\nx = 1\n\nx = 1\n"
    assert recorder.last_path and Path(recorder.last_path).is_file()
    assert verify_store(tmp_path / "runs").ok


def test_sink_mode_counts_source_and_output_only(tmp_path):
    recorder = make_recorder(tmp_path, row_counts="sink")
    record, _ = _run_pipeline(tmp_path, recorder)
    final = recorder.finish(record, True)
    assert final.nodes[0].rows_out == {"var_in_1": 3}
    assert final.nodes[0].count_method == {"var_in_1": "scan_plan"}
    assert final.nodes[1].rows_out == {"var_norm_2": None}
    assert final.nodes[1].count_method == {"var_norm_2": "none"}
    assert final.nodes[1].columns_out == {"var_norm_2": ["id", "amount"]}
    assert final.nodes[2].rows_in[0]["rows"] == 3  # filled from the output file
    assert final.outputs[0].row_count == 3


def test_off_mode_has_no_counts_but_has_hashes(tmp_path):
    recorder = make_recorder(tmp_path, row_counts="off")
    record, _ = _run_pipeline(tmp_path, recorder)
    final = recorder.finish(record, True)
    assert all(v is None for n in final.nodes for v in n.rows_out.values())
    assert final.nodes[0].columns_out == {}
    assert final.inputs[0].sha256 and final.inputs[0].row_count is None
    assert final.outputs[0].sha256 and final.outputs[0].row_count is None


def test_node_record_rows_in_derived_from_edges_with_two_outputs(tmp_path):
    a = NodeSpec(
        1, "preparation.split", "Split", n_outputs=2, output_variables=("va", "vb")
    )
    b = NodeSpec(2, "preparation.select", "Select", output_variables=("vc",))
    recorder = make_recorder(tmp_path)
    record = recorder.begin(None, [a, b], app_version="x", edges=[EdgeRef(1, 1, 2, 0)])
    frames = {
        1: {"va": pl.LazyFrame({"x": [1, 2, 3, 4]}), "vb": pl.LazyFrame({"x": [9]})},
        2: {"vc": pl.LazyFrame({"x": [9]})},
    }
    nodes = [FakeNode(1, "Split"), FakeNode(2, "Select")]
    records = drive(recorder, record, nodes, frames)
    assert records[0].rows_out == {"va": 4, "vb": 1}
    assert records[1].rows_in == [
        {"socket": 0, "from_node_id": 1, "from_socket": 1, "variable": "vb", "rows": 1}
    ]


def test_finish_marks_unrun_nodes_skipped_after_failure(tmp_path):
    specs, edges, *_ = _specs(tmp_path)
    recorder = make_recorder(tmp_path)
    record = recorder.begin(None, specs, app_version="x", edges=edges)
    nodes = [FakeNode(s.node_id, s.title) for s in specs]
    failed = FakeResult(False, error="boom", exception=ValueError("boom"))
    drive(
        recorder,
        record,
        nodes[:2],
        {1: {"var_in_1": _frames().lazy()}},
        results={2: failed},
    )
    final = recorder.finish(record, False)
    assert final.status == "failed"
    assert [n.status for n in final.nodes] == ["ok", "failed", "skipped"]
    assert final.nodes[1].error["code"].startswith("TD-")
    assert final.nodes[1].error["technical"]
    assert final.nodes[2].duration_s == 0.0 and final.nodes[2].started_at is None
    assert verify_store(tmp_path / "runs").ok


def test_cancelled_status(tmp_path):
    specs, edges, *_ = _specs(tmp_path)
    recorder = make_recorder(tmp_path)
    record = recorder.begin(None, specs, app_version="x", edges=edges)
    recorder.request_cancel()
    final = recorder.finish(record, False, cancelled=True)
    assert final.status == "cancelled"
    assert {n.status for n in final.nodes} == {"skipped"}


def test_cancel_stops_hashing_in_before_node(tmp_path):
    specs, edges, *_ = _specs(tmp_path)
    recorder = make_recorder(tmp_path)
    record = recorder.begin(None, specs, app_version="x", edges=edges)
    recorder.request_cancel()
    recorder.before_node(FakeNode(1))
    final = recorder.finish(record, False, cancelled=True)
    assert final.inputs[0].sha256_status == "cancelled"
    assert any("input not hashed (cancelled)" in w for w in final.warnings)


def test_row_count_mismatch_warning(tmp_path):
    recorder = make_recorder(tmp_path)
    record, _ = _run_pipeline(tmp_path, recorder, rows=5, write_rows=3)
    final = recorder.finish(record, True)
    assert any(
        w.startswith("row count mismatch: File Output received 5")
        for w in final.warnings
    )


def test_failed_output_node_is_flagged_partial(tmp_path):
    specs, edges, _src, out = _specs(tmp_path)
    out.write_bytes(b"id\n1\n")  # a half-written file
    recorder = make_recorder(tmp_path)
    record = recorder.begin(None, specs, app_version="x", edges=edges)
    node = FakeNode(3, "File Output")
    recorder.node_finished(
        record,
        node,
        FakeResult(False, error="disk full", exception=OSError("disk full")),
    )
    final = recorder.finish(record, False)
    partial = [fp for fp in final.outputs if fp.error]
    assert partial and partial[0].error == "node failed; file may be partial"
    assert partial[0].sha256 is None and partial[0].sha256_status == "disabled"


def test_node_errored_builds_failed_record(tmp_path):
    specs, edges, *_ = _specs(tmp_path)
    recorder = make_recorder(tmp_path)
    record = recorder.begin(None, specs, app_version="x", edges=edges)
    node_record = recorder.node_errored(record, FakeNode(2), RuntimeError("kaput"))
    assert node_record.status == "failed" and node_record.error["technical"]


def test_missing_input_is_recorded_as_missing(tmp_path):
    specs, edges, src, _out = _specs(tmp_path)
    src.unlink()
    recorder = make_recorder(tmp_path)
    record = recorder.begin(None, specs, app_version="x", edges=edges)
    recorder.before_node(FakeNode(1))
    final = recorder.finish(record, False)
    assert final.inputs[0].sha256_status == "missing"
    assert any("input file not found" in w for w in final.warnings)


def test_embed_code_off_keeps_hash(tmp_path):
    recorder = make_recorder(tmp_path, embed_code=False)
    record, _ = _run_pipeline(tmp_path, recorder)
    final = recorder.finish(record, True)
    assert final.generated_code is None
    joined = b"x = 1\n\nx = 1\n\nx = 1\n"
    assert final.generated_code_sha256 == hashlib.sha256(joined).hexdigest()


def test_generated_code_over_cap_is_dropped_but_hashed(tmp_path):
    specs, edges, *_ = _specs(tmp_path)
    recorder = make_recorder(tmp_path)
    record = recorder.begin(None, specs, app_version="x", edges=edges)
    big = "# " + "x" * 1_100_000 + "\n"
    recorder.node_finished(record, FakeNode(1), FakeResult(True, code=big))
    final = recorder.finish(record, True)
    assert final.generated_code is None
    assert final.generated_code_sha256 == hashlib.sha256(big.encode()).hexdigest()


def test_baseline_input_changes(tmp_path):
    recorder = make_recorder(tmp_path)
    specs_edges = _specs(tmp_path)
    record, _ = _run_pipeline(tmp_path, recorder, specs_edges=specs_edges)
    first = recorder.finish(record, True)
    assert first.baseline is None
    src = specs_edges[2]
    record2, _ = _run_pipeline(tmp_path, recorder, specs_edges=specs_edges)
    second = recorder.finish(record2, True)
    assert second.baseline == {"run_id": first.run_id, "input_changes": []}
    assert second.inputs[0].sha256_status == "cached"
    src.write_bytes((CSV + "4,40\n").encode())
    record3, _ = _run_pipeline(tmp_path, recorder, specs_edges=specs_edges)
    third = recorder.finish(record3, True)
    changes = third.baseline["input_changes"]
    assert len(changes) == 1 and changes[0]["change"] == "modified"
    assert changes[0]["old_sha256"] != changes[0]["new_sha256"]
    assert third.prev_record_hash == second.record_hash and third.seq == 3


def test_count_failure_never_fails_the_run(tmp_path, monkeypatch):
    from trigger_designer.core.audit import recorder as recorder_mod

    def boom(*_a, **_k):
        raise CountError("ComputeError: bad plan")

    monkeypatch.setattr(recorder_mod, "count_frame", boom)
    recorder = make_recorder(tmp_path)
    record, _ = _run_pipeline(tmp_path, recorder)
    final = recorder.finish(record, True)
    assert final.status == "ok"
    assert final.nodes[0].rows_out == {"var_in_1": None}
    assert any("row count skipped for var_in_1" in w for w in final.nodes[0].warnings)
    assert counting_mod.CountError is CountError


def test_after_node_bug_is_swallowed(tmp_path, monkeypatch):
    from trigger_designer.core.audit import recorder as recorder_mod

    def boom(*_a, **_k):
        raise RuntimeError("recorder bug")

    monkeypatch.setattr(recorder_mod, "schema_of", boom)
    recorder = make_recorder(tmp_path)
    record, _ = _run_pipeline(tmp_path, recorder)
    assert recorder.finish(record, True).status == "ok"


def test_all_mode_replaces_variable_with_materialised_frame(tmp_path):
    specs, edges, *_ = _specs(tmp_path)
    recorder = make_recorder(tmp_path)
    recorder.begin(None, specs, app_version="x", edges=edges)
    calls = itertools.count()

    def spy(series):
        next(calls)
        return series

    lazy = pl.LazyFrame({"a": [1, 2]}).select(
        pl.col("a").map_batches(spy, return_dtype=pl.Int64)
    )
    local = {"var_in_1": lazy}
    recorder.after_node(FakeNode(1), local, FakeResult(True))
    local["var_in_1"].collect()
    local["var_in_1"].collect()
    assert next(calls) == 1


def test_warnings_capped(tmp_path):
    specs, edges, *_ = _specs(tmp_path)
    recorder = make_recorder(tmp_path)
    record = recorder.begin(None, specs, app_version="x", edges=edges)
    many = [f"warn {i} " + "w" * 600 for i in range(40)]
    node_record = recorder.node_finished(
        record, FakeNode(2), FakeResult(True, warnings=many)
    )
    assert len(node_record.warnings) == 20
    assert all(len(w) <= 500 for w in node_record.warnings)


def test_test_summary_is_read_from_content(tmp_path):
    from dataclasses import dataclass

    @dataclass
    class Summary:
        status: str = "warn"
        exception_rows: int = 2

    specs, edges, *_ = _specs(tmp_path)
    recorder = make_recorder(tmp_path)
    record = recorder.begin(None, specs, app_version="x", edges=edges)

    class Content:
        test_summary = Summary()

    node_record = recorder.node_finished(
        record, FakeNode(2, content=Content()), FakeResult(True)
    )
    assert node_record.test_summary == {"status": "warn", "exception_rows": 2}


def test_seed_is_extracted_from_settings(tmp_path):
    spec = NodeSpec(
        1, "preparation.split", "Split", settings={"random_seed": 42, "is_random": True}
    )
    recorder = make_recorder(tmp_path)
    record = recorder.begin(None, [spec], app_version="x")
    node_record = recorder.node_finished(record, FakeNode(1), FakeResult(True))
    assert node_record.seed == 42


@pytest.mark.parametrize(
    ("settings", "expected"),
    [
        ({"random_seed": 42, "is_random": True}, 42),
        ({"random_seed": 42, "is_random": False}, None),
        ({"seed": 7}, 7),
        ({"random_seed": True}, None),
        ({"other": 1}, None),
        (None, None),
    ],
)
def test_seed_extraction(settings, expected):
    assert extract_seed(settings) == expected


def test_sanitize_settings():
    class Weird:
        def __repr__(self):
            return "W" * 500

    out = sanitize(
        {
            1: {"b", "a"},
            "p": Path("C:/x/y"),
            "nan": math.nan,
            "inf": math.inf,
            "t": (1, 2),
            "w": Weird(),
            "long": "z" * 30_000,
            "big": 2**70,
        }
    )
    assert out["1"] == ["a", "b"]
    assert out["p"] == "C:/x/y"
    assert out["nan"] is None and out["inf"] is None
    assert out["t"] == [1, 2]
    assert len(out["w"]) == 200
    assert out["long"].endswith("...[truncated]") and len(out["long"]) < 20_100
    assert out["big"] == repr(2**70)
    deep: dict = {}
    cursor = deep
    for _ in range(20):
        cursor["n"] = {}
        cursor = cursor["n"]
    flat = repr(sanitize(deep))
    assert "'...'" in flat


def test_file_output_row_count_variants(tmp_path):
    """Output files of every non-csv writer are counted the same way."""
    recorder = make_recorder(tmp_path)
    out = tmp_path / "o.parquet"
    spec = NodeSpec(
        1,
        "input.file_output",
        "Out",
        output_files=({"path": str(out), "format": "parquet", "delimiter": ","},),
    )
    record = recorder.begin(None, [spec], app_version="x")
    _frames(4).write_parquet(out)
    drive(recorder, record, [FakeNode(1, "Out")], {1: {}})
    final = recorder.finish(record, True)
    assert final.outputs[0].row_count == 4
    assert final.outputs[0].sha256 and final.outputs[0].sha256 != ORDERS_SHA256
