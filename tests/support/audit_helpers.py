"""Shared helpers for the run-record (audit trail) tests.

Qt-free helpers first (record factories), then the workflow builders used by
the integration, e2e and ui layers. Heavy imports stay inside the functions so
the unit tests that only need ``make_record`` do not start Qt.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

ORDERS_SHA256 = "aac441b2f011b33ba88a30f384ec388988fff9d248e7620cc73007e74720d5c9"
FIXTURE_DIR = Path(__file__).resolve().parents[1] / "e2e" / "fixtures" / "audit"


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def make_node(node_id: int = 1, **over: Any) -> dict:
    node = {
        "seq": 0,
        "node_id": node_id,
        "op": "preparation.select",
        "title": "Select",
        "label": None,
        "status": "ok",
        "started_at": "2026-10-21T09:14:03.121000Z",
        "duration_s": 0.012,
        "count_seconds": 0.0,
        "settings": {"delimiter": ","},
        "seed": None,
        "code_sha256": sha("code"),
        "rows_in": [],
        "rows_out": {f"var_{node_id}": 3},
        "columns_out": {f"var_{node_id}": ["id", "amount"]},
        "dtypes_out": {f"var_{node_id}": ["String", "String"]},
        "count_method": {f"var_{node_id}": "materialized"},
        "peak_memory_mb": 0.0,
        "warnings": [],
        "error": None,
        "test_summary": None,
    }
    node.update(over)
    return node


def make_fingerprint(role: str = "input", path: str = "C:/data/in.csv", **over) -> dict:
    fp = {
        "role": role,
        "node_id": 1,
        "path": path,
        "sheet": None,
        "size_bytes": 25,
        "modified_time": "2026-10-20T16:02:11.500000Z",
        "mtime_ns": 1792512131500000000,
        "sha256": ORDERS_SHA256,
        "sha256_status": "computed",
        "row_count": 3,
        "row_count_method": "materialized",
        "error": None,
    }
    fp.update(over)
    return fp


def make_record_dict(run_id: str = "a" * 32, status: str = "ok", **over) -> dict:
    """A complete, schema-valid, *unsealed* record dict (hashes still zero)."""
    record = {
        "schema_version": 1,
        "run_id": run_id,
        "seq": 0,
        "status": status,
        "started_at": "2026-10-21T09:14:03.120456Z",
        "finished_at": "2026-10-21T09:14:04.002118Z",
        "duration_s": 0.881662,
        "app_name": "TriggerDesigner",
        "app_version": "0.1.0",
        "workflow_schema_version": 2,
        "python_version": "3.13.12",
        "polars_version": "1.44.2",
        "duckdb_version": "1.5.5",
        "os_name": "Windows-11",
        "user": "tester",
        "machine": "box",
        "workflow_path": None,
        "workflow_sha256": None,
        "workflow_uuid": None,
        "graph_sha256": sha("graph"),
        "workflow_modified_since_save": False,
        "options": {"row_count_mode_effective": "all"},
        "inputs": [make_fingerprint("input")],
        "outputs": [make_fingerprint("output", "C:/data/out.csv", node_id=3)],
        "nodes": [make_node(1), make_node(2, op="input.file_output", title="Out")],
        "baseline": None,
        "warnings": [],
        "generated_code": "x = 1\n",
        "generated_code_sha256": sha("x = 1\n"),
        "hash_algo": "sha256-canonical-json-v1",
        "prev_record_hash": "0" * 64,
        "record_hash": "0" * 64,
    }
    record.update(over)
    return record


def make_record(run_id: str | None = None, status: str = "ok", **over):
    """A ``RunRecord`` built from :func:`make_record_dict` (unsealed)."""
    import uuid

    from trigger_designer.core.audit.schema import RunRecord

    data = make_record_dict(run_id or uuid.uuid4().hex, status, **over)
    return RunRecord.from_dict(data)


# ---------------------------------------------------------------------------
# Recorder fakes (no Qt): a node with an id and an ExecutionResult look-alike.
# ---------------------------------------------------------------------------
class FakeNode:
    def __init__(self, node_id: int, title: str = "Node", content=None):
        self.id = node_id
        self.node_title = title
        self.content = content


class FakeResult:
    def __init__(self, success: bool = True, **over):
        self.success = success
        self.execution_time = over.pop("execution_time", 0.01)
        self.peak_memory = over.pop("peak_memory", 0.5)
        self.warnings = over.pop("warnings", [])
        self.code = over.pop("code", "x = 1\n")
        self.started_at = over.pop("started_at", "2026-10-21T09:14:03.121000Z")
        self.finished_at = over.pop("finished_at", "2026-10-21T09:14:03.131000Z")
        self.exception = over.pop("exception", None)
        self.error = over.pop("error", "")
        self.traceback_text = over.pop("traceback_text", "")
        self.variables = over.pop("variables", {})
        for key, value in over.items():
            setattr(self, key, value)


def make_recorder(tmp_path, **options):
    """A recorder writing into ``tmp_path/runs`` (fallback root ``tmp_path/ad``)."""
    from trigger_designer.core.audit.recorder import AuditOptions, RunRecorder
    from trigger_designer.core.audit.store import RunStore

    options.setdefault("store_dir", str(tmp_path / "runs"))
    return RunRecorder(RunStore(app_data_dir=tmp_path / "ad"), AuditOptions(**options))


def drive(recorder, record, nodes, variables, results=None):
    """Run the executor-side protocol by hand for ``nodes`` in order.

    ``variables`` maps node id -> {variable: frame}; ``results`` maps node id ->
    ``FakeResult`` (default success). Returns the node records.
    """
    out = []
    for node in nodes:
        result = (results or {}).get(node.id) or FakeResult(True)
        recorder.before_node(node)
        if result.success:
            local = dict(variables.get(node.id, {}))
            recorder.after_node(node, local, result)
        out.append(recorder.node_finished(record, node, result))
    return out
