"""The recorder installed on a real ``NodeExecutor`` (plan 02 Step 5, 6.2).

Stub nodes with real generated code; the loop is the shared ``run_nodes`` so
the hook order, ``after_node`` mutation and failure paths are the production
ones. No window is needed.
"""

from __future__ import annotations

import hashlib
from types import SimpleNamespace

import polars as pl
import pytest

from tests.support.audit_helpers import make_recorder
from trigger_designer.core.audit.recorder import EdgeRef, NodeSpec
from trigger_designer.core.audit.store import verify_store
from trigger_designer.core.ExecutionCheck.executor import NodeExecutor
from trigger_designer.core.ExecutionCheck.run_loop import run_nodes

CSV = "id,amount\n1,10\n2,20\n3,30\n"
CSV_SHA = hashlib.sha256(CSV.encode()).hexdigest()


class StubNode:
    def __init__(self, node_id, title, code):
        self.id = node_id
        self.node_title = title
        self._code = code
        self.content = SimpleNamespace()

    def get_code(self):
        return self._code


def _pipeline(tmp_path, *, fail_sink=False, extra_sink=False):
    src = tmp_path / "orders.csv"
    src.write_bytes(CSV.encode())
    out = tmp_path / "out.csv"
    sink_path = tmp_path / "missing_dir" / "out.csv" if fail_sink else out
    nodes = [
        StubNode(
            1,
            "File Input",
            f"import polars as pl\nvar_in_1 = pl.scan_csv({str(src)!r}, infer_schema=False)\n",
        ),
        StubNode(
            2,
            "Head",
            "var_head_2 = var_in_1.head(2)\nvar_all_2 = var_in_1\n",
        ),
        StubNode(3, "File Output", f"var_head_2.sink_csv({str(sink_path)!r})\n"),
    ]
    specs = [
        NodeSpec(
            1,
            "input.file_input",
            "File Input",
            n_outputs=1,
            output_variables=("var_in_1",),
            is_source=True,
            input_files=({"path": str(src), "sheet": None, "kind": "csv"},),
        ),
        NodeSpec(
            2,
            "preparation.head",
            "Head",
            n_outputs=2,
            output_variables=("var_head_2", "var_all_2"),
        ),
        NodeSpec(
            3,
            "input.file_output",
            "File Output",
            output_files=({"path": str(sink_path), "format": "csv", "delimiter": ","},),
        ),
    ]
    edges = [EdgeRef(1, 0, 2, 0), EdgeRef(2, 0, 3, 0)]
    return nodes, specs, edges, src, sink_path


def _run(tmp_path, recorder, nodes, specs, edges, *, continue_on_error=False):
    executor = NodeExecutor()
    record = recorder.begin(None, specs, app_version="0.1.0", edges=edges)
    executor.before_node = recorder.before_node
    executor.after_node = recorder.after_node
    results = {}

    def finished(node, result):
        results[node.id] = result
        recorder.node_finished(record, node, result)

    def errored(node, exc):
        recorder.node_errored(record, node, exc)

    upstream = {nodes[1]: [nodes[0]], nodes[2]: [nodes[1]]}
    outcome = run_nodes(
        nodes,
        executor,
        continue_on_error=continue_on_error,
        upstream=upstream,
        on_node_finished=finished,
        on_node_errored=errored,
    )
    final = recorder.finish(record, outcome.success, cancelled=outcome.cancelled)
    return executor, final, results


@pytest.mark.parametrize("mode", ["all", "sink", "off"])
def test_ok_run_in_every_mode_records_and_verifies(tmp_path, mode):
    nodes, specs, edges, _src, out = _pipeline(tmp_path)
    recorder = make_recorder(tmp_path, row_counts=mode)
    executor, final, results = _run(tmp_path, recorder, nodes, specs, edges)
    assert final.status == "ok" and all(r.success for r in results.values())
    assert final.inputs[0].sha256 == CSV_SHA
    assert final.outputs[0].path == out.as_posix()
    assert verify_store(tmp_path / "runs").ok
    head, everything = (
        final.nodes[1].rows_out["var_head_2"],
        final.nodes[1].rows_out["var_all_2"],
    )
    if mode == "all":
        assert (head, everything) == (2, 3)
        assert final.nodes[2].rows_in[0]["rows"] == 2
        assert final.outputs[0].row_count == 2
        # downstream nodes read the materialised frame from the shared context
        assert isinstance(executor.execution_context["var_in_1"], pl.LazyFrame)
    elif mode == "sink":
        assert (head, everything) == (None, None)
        assert final.nodes[0].rows_out == {"var_in_1": 3}
        assert final.nodes[2].rows_in[0]["rows"] == 2
    else:
        assert head is None and final.outputs[0].row_count is None


def test_after_node_replacement_reaches_context_and_result(tmp_path):
    nodes, specs, edges, *_ = _pipeline(tmp_path)
    recorder = make_recorder(tmp_path, row_counts="all")
    executor, _final, results = _run(tmp_path, recorder, nodes, specs, edges)
    stored = executor.execution_context["var_in_1"]
    assert results[1].variables["var_in_1"] is stored
    # a materialised frame: its plan is an in-memory scan, not a csv scan
    assert "CSV SCAN" not in stored.explain().upper()


def test_failed_node_record_has_error_and_skipped_followers(tmp_path):
    nodes, specs, edges, *_ = _pipeline(tmp_path, fail_sink=True)
    recorder = make_recorder(tmp_path)
    _executor, final, _results = _run(tmp_path, recorder, nodes, specs, edges)
    assert final.status == "failed"
    assert [n.status for n in final.nodes] == ["ok", "ok", "failed"]
    error = final.nodes[2].error
    assert error["code"].startswith("TD-") and error["technical"]
    assert verify_store(tmp_path / "runs").ok


def test_failed_middle_node_skips_the_sink(tmp_path):
    nodes, specs, edges, *_ = _pipeline(tmp_path)
    nodes[1]._code = "var_head_2 = var_in_1.select(pl.col('amnt'))\n"
    recorder = make_recorder(tmp_path)
    _executor, final, _ = _run(tmp_path, recorder, nodes, specs, edges)
    assert [n.status for n in final.nodes] == ["ok", "failed", "skipped"]
    assert final.nodes[1].error["code"].startswith("TD-")
    assert final.outputs == []


def test_continue_on_error_records_every_branch(tmp_path):
    nodes, specs, edges, *_ = _pipeline(tmp_path)
    nodes[1]._code = "raise ValueError('step failed')\n"
    recorder = make_recorder(tmp_path)
    _e, final, _ = _run(tmp_path, recorder, nodes, specs, edges, continue_on_error=True)
    assert [n.status for n in final.nodes] == ["ok", "failed", "skipped"]


def test_recorder_bug_in_hook_does_not_change_the_run(tmp_path, monkeypatch):
    from trigger_designer.core.audit import recorder as recorder_mod

    def boom(*_a, **_k):
        raise RuntimeError("audit bug")

    monkeypatch.setattr(recorder_mod, "fingerprint_file", boom)
    nodes, specs, edges, *_ = _pipeline(tmp_path)
    recorder = make_recorder(tmp_path)
    _e, final, results = _run(tmp_path, recorder, nodes, specs, edges)
    assert all(r.success for r in results.values())
    assert final.status == "ok"


def test_code_is_the_raw_generated_code_and_hashes_match(tmp_path):
    nodes, specs, edges, *_ = _pipeline(tmp_path)
    recorder = make_recorder(tmp_path)
    _e, final, results = _run(tmp_path, recorder, nodes, specs, edges)
    assert results[1].code == nodes[0].get_code()
    assert (
        final.nodes[0].code_sha256
        == hashlib.sha256(nodes[0].get_code().encode()).hexdigest()
    )
    assert nodes[0].get_code() in final.generated_code
    assert final.nodes[0].started_at == results[1].started_at
