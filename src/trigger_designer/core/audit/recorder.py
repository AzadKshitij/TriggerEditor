"""The run recorder: one immutable record per Run (docs/plan/02-audit-trail.md).

Qt-free; never imports the executor or ``trigger_designer.qt``. The GUI bridge
(``qt/helpers/audit_bridge.py``) and the headless runner both drive it:

* ``begin`` (GUI thread) snapshots settings and hashes the workflow file;
* ``before_node`` / ``after_node`` are executor hooks (worker thread): they
  fingerprint inputs and outputs and count rows;
* ``node_finished`` / ``node_errored`` (GUI thread) build the node records;
* ``finish`` seals the record into the :class:`RunStore`.

The audit layer must never change a run's outcome: every failure in here is
logged and turned into a warning, never raised into the run.
"""

from __future__ import annotations

import copy
import dataclasses
import getpass
import math
import os
import platform
import socket
import threading
import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from pathlib import Path
from typing import Any

from loguru import logger

from trigger_designer.core.audit.canonical import (
    canonical_json,
    sha256_hex,
    utc_now_iso,
)
from trigger_designer.core.audit.counting import (
    CountError,
    count_frame,
    decide_row_count_mode,
    is_frame,
    schema_of,
)
from trigger_designer.core.audit.errors_adapter import error_to_dict, exception_to_dict
from trigger_designer.core.audit.fingerprint import (
    CACHE_FILENAME,
    FingerprintCache,
    count_rows_in_file,
    fingerprint_file,
    recorded_path,
)
from trigger_designer.core.audit.schema import (
    HASH_ALGO,
    RUN_RECORD_SCHEMA_VERSION,
    FileFingerprint,
    NodeRunRecord,
    RunRecord,
)
from trigger_designer.core.audit.store import (
    RunAlreadySealed,
    RunStore,
    StoreLockTimeout,
)
from trigger_designer.core.constants import APP_NAME, WORKFLOW_SCHEMA_VERSION

MAX_CODE_BYTES = 1_048_576
MAX_WARNINGS = 20
MAX_WARNING_CHARS = 500
MAX_STRING = 20_000
MAX_DEPTH = 12


# --------------------------------------------------------------- the registry
_provider_lock = threading.Lock()
_run_record_provider: Callable[[], dict | None] | None = None


def set_run_record_provider(provider: Callable[[], dict | None] | None) -> None:
    """Install (or clear, with ``None``) the callable that returns the in-flight
    record as a dict; plan 06 reads it while a run is going."""
    global _run_record_provider
    with _provider_lock:
        _run_record_provider = provider


def get_run_record_provider() -> Callable[[], dict | None] | None:
    with _provider_lock:
        return _run_record_provider


# ------------------------------------------------------------------ settings
def sanitize(value: Any, _depth: int = 0) -> Any:
    """JSON-safe copy of a settings value (3.10)."""
    if _depth > MAX_DEPTH:
        return "..."
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value if -(2**63) <= value < 2**63 else repr(value)
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, str):
        if len(value) > MAX_STRING:
            return value[:MAX_STRING] + "...[truncated]"
        return value
    if isinstance(value, dict):
        return {str(k): sanitize(v, _depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize(v, _depth + 1) for v in value]
    if isinstance(value, (set, frozenset)):
        return [sanitize(v, _depth + 1) for v in sorted(value, key=repr)]
    if isinstance(value, os.PathLike):
        return os.fspath(value).replace("\\", "/")
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return repr(value)[:200]


def extract_seed(settings: dict | None) -> int | None:
    """The random seed a node used, when it has one."""
    if not isinstance(settings, dict):
        return None
    if settings.get("is_random") is False:
        return None
    for key in ("random_seed", "seed"):
        value = settings.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return None


# ------------------------------------------------------------------ the specs
@dataclass(frozen=True)
class EdgeRef:
    src_node_id: int
    src_socket: int
    dst_node_id: int
    dst_socket: int


@dataclass(frozen=True)
class NodeSpec:
    node_id: int
    op: str
    title: str
    label: str | None = None
    settings: dict = field(default_factory=dict)  # already JSON-safe
    n_outputs: int = 0
    output_variables: tuple[str, ...] = ()  # socket order
    is_source: bool = False  # File Input style
    input_files: tuple[dict, ...] = ()  # ({"path", "sheet", "kind"},)
    output_files: tuple[dict, ...] = ()  # ({"path", "format", "delimiter"},)


@dataclass(frozen=True)
class AuditOptions:
    record_identity: bool = True
    hash_inputs: bool = True
    hash_outputs: bool = True
    hash_max_mb: int = 2048
    row_counts: str = "auto"
    exact_counts_max_mb: int = 256
    embed_code: bool = True
    store_dir: str = ""  # explicit store folder ("" = default resolution)
    app_data_dir: str = ""  # fallback root, "" = none
    enabled: bool = True  # False: nothing is written (--no-record)
    sync_enrich: bool = False  # headless: enrich errors synchronously
    redact_values: bool = False  # errors/redact_values: hide sampled values


@dataclass
class _NodeCounts:
    rows_out: dict = field(default_factory=dict)
    columns_out: dict = field(default_factory=dict)
    dtypes_out: dict = field(default_factory=dict)
    count_method: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)
    count_seconds: float = 0.0


def _cap_warning(text: str) -> str:
    return (
        text
        if len(text) <= MAX_WARNING_CHARS
        else text[: MAX_WARNING_CHARS - 3] + "..."
    )


def _file_state(path: str) -> tuple[int | None, int | None]:
    try:
        info = os.stat(path)
    except OSError:
        return None, None
    return info.st_size, info.st_mtime_ns


class RunRecorder:
    """Builds one run record. A recorder instance serves one run at a time."""

    def __init__(
        self,
        store: RunStore | None = None,
        options: AuditOptions | None = None,
        *,
        cache: FingerprintCache | None = None,
    ) -> None:
        self._options = options or AuditOptions()
        self._store = store or RunStore("", self._options.app_data_dir or None)
        self._cache = cache if cache is not None else FingerprintCache()
        self._lock = threading.RLock()
        self._cancel = threading.Event()
        self._sealed_ids: set[str] = set()
        self._last_path: str | None = None
        #: Optional ``(NodeError, node) -> NodeError`` used for headless
        #: enrichment (plan 08 builds a full job from its loaded graph).
        self.error_enricher: Callable[[Any, Any], Any] | None = None
        self._reset()

    # -- state ----------------------------------------------------------
    def _reset(self) -> None:
        self._record: RunRecord | None = None
        self._spec_by_id: dict[int, NodeSpec] = {}
        self._edges: list[EdgeRef] = []
        self._order: list[int] = []
        self._mode = "off"
        self._fingerprints_in: list[FileFingerprint] = []
        self._fingerprints_out: list[FileFingerprint] = []
        self._counts: dict[int, _NodeCounts] = {}
        self._node_records: dict[int, NodeRunRecord] = {}
        self._warnings: list[str] = []
        self._code_parts: list[str] = []
        self._perf_start = 0.0
        self._start_ns = 0
        self._directory: Path | None = None
        self._marker_dir: Path | None = None
        self._dir_preexisted = True

    @property
    def options(self) -> AuditOptions:
        return self._options

    @property
    def last_path(self) -> str | None:
        return self._last_path

    @property
    def mode(self) -> str:
        """Effective row-count mode of the current run."""
        return self._mode

    @property
    def store(self) -> RunStore:
        return self._store

    def request_cancel(self) -> None:
        """Stop hashing at the next chunk (the node being executed finishes)."""
        self._cancel.set()

    # -- begin ----------------------------------------------------------
    def begin(
        self,
        workflow_path: str | None,
        nodes: Sequence[NodeSpec],
        *,
        app_version: str,
        edges: Sequence[EdgeRef] = (),
        workflow_uuid: str | None = None,
        modified_since_save: bool | None = None,
    ) -> RunRecord:
        opts = self._options
        with self._lock:
            self._reset()
            self._cancel.clear()
            self._perf_start = time.perf_counter()
            self._start_ns = time.time_ns()
            started_at = utc_now_iso()
            run_id = uuid.uuid4().hex
            self._spec_by_id = {spec.node_id: spec for spec in nodes}
            self._order = [spec.node_id for spec in nodes]
            self._edges = list(edges)

            total_bytes = 0
            for spec in nodes:
                for item in spec.input_files:
                    size, _mtime = _file_state(str(item.get("path") or ""))
                    total_bytes += size or 0
            self._mode = decide_row_count_mode(
                opts.row_counts, total_bytes, opts.exact_counts_max_mb
            )

            norm_path = recorded_path(workflow_path) if workflow_path else None
            workflow_sha = None
            if norm_path:
                try:
                    workflow_sha = sha256_hex(Path(workflow_path).read_bytes())
                except OSError as exc:
                    self._warnings.append(
                        f"workflow file not hashed: {type(exc).__name__}"
                    )

            graph = {
                "nodes": [
                    {
                        "id": spec.node_id,
                        "op": spec.op,
                        "settings": sanitize(spec.settings),
                    }
                    for spec in sorted(nodes, key=lambda s: s.node_id)
                ],
                "edges": sorted(
                    [e.src_node_id, e.src_socket, e.dst_node_id, e.dst_socket]
                    for e in self._edges
                ),
            }
            graph_sha = sha256_hex(canonical_json(graph))

            user = machine = None
            if opts.record_identity:
                try:
                    user = getpass.getuser()
                except Exception:  # noqa: BLE001
                    user = None
                try:
                    machine = socket.gethostname()
                except Exception:  # noqa: BLE001
                    machine = None

            try:
                import polars as pl

                polars_version = pl.__version__
            except Exception:  # noqa: BLE001
                polars_version = ""
            duckdb_version = None
            try:
                import duckdb

                duckdb_version = duckdb.__version__
            except Exception:  # noqa: BLE001, S110
                pass

            self._record = RunRecord(
                run_id=run_id,
                started_at=started_at,
                finished_at="",
                status="running",
                app_version=app_version,
                workflow_schema_version=WORKFLOW_SCHEMA_VERSION,
                workflow_path=norm_path,
                workflow_sha256=workflow_sha,
                user=user,
                machine=machine,
                python_version=platform.python_version(),
                polars_version=polars_version,
                schema_version=RUN_RECORD_SCHEMA_VERSION,
                app_name=APP_NAME,
                duckdb_version=duckdb_version,
                os_name=platform.platform(),
                workflow_uuid=workflow_uuid,
                graph_sha256=graph_sha,
                workflow_modified_since_save=modified_since_save,
                options={
                    "row_count_mode_requested": opts.row_counts,
                    "row_count_mode_effective": self._mode,
                    "exact_counts_max_mb": opts.exact_counts_max_mb,
                    "total_input_bytes": total_bytes,
                    "hash_inputs": opts.hash_inputs,
                    "hash_outputs": opts.hash_outputs,
                    "hash_max_mb": opts.hash_max_mb,
                    "record_identity": opts.record_identity,
                    "embed_code": opts.embed_code,
                },
                hash_algo=HASH_ALGO,
            )
            if opts.enabled:
                self._prepare_store(norm_path, run_id)
            return self._record

    def _prepare_store(self, workflow_path: str | None, run_id: str) -> None:
        directory = self._options.store_dir or None
        primary = (
            Path(directory) if directory else self._store.store_dir_for(workflow_path)
        )
        self._dir_preexisted = primary.exists()
        try:
            folder, _warning = self._store.resolve_writable(workflow_path, directory)
        except OSError as exc:
            logger.warning("run log folder is not writable: {}", exc)
            return
        self._directory = folder
        self._cache.bind(folder / CACHE_FILENAME)
        marker = self._store.mark_started(run_id, workflow_path, directory)
        self._marker_dir = marker.parent if marker else None

    # -- executor hooks (worker thread) ---------------------------------
    def _hash_max_bytes(self) -> int:
        return int(self._options.hash_max_mb) * 1024 * 1024

    def before_node(self, node: Any) -> None:
        try:
            spec = self._spec_by_id.get(getattr(node, "id", None))
            if spec is None or not spec.input_files:
                return
            for item in spec.input_files:
                path = str(item.get("path") or "")
                if not path:
                    continue
                fp = fingerprint_file(
                    path,
                    "input",
                    spec.node_id,
                    item.get("sheet") or None,
                    cache=self._cache,
                    cancel=self._cancel,
                    hash_enabled=self._options.hash_inputs,
                    hash_max_bytes=self._hash_max_bytes(),
                )
                with self._lock:
                    self._fingerprints_in.append(fp)
        except Exception as exc:  # noqa: BLE001 - never fail a run
            logger.warning("audit: input fingerprint failed: {}", exc)

    def after_node(self, node: Any, local_variables: dict, result: Any) -> None:
        try:
            self._after_node(node, local_variables)
        except Exception as exc:  # noqa: BLE001 - never fail a run
            logger.warning("audit: counting failed: {}", exc)

    def _after_node(self, node: Any, local_variables: dict) -> None:
        spec = self._spec_by_id.get(getattr(node, "id", None))
        if spec is None:
            return
        started = time.perf_counter()
        counts = _NodeCounts()
        mode = self._mode
        for name in spec.output_variables:
            value = local_variables.get(name)
            counts.rows_out[name] = None
            counts.count_method[name] = "none"
            if value is None or mode == "off" or not is_frame(value):
                continue
            try:
                rows, method, stored = count_frame(
                    value, mode, is_source=spec.is_source
                )
                if stored is not value:
                    local_variables[name] = stored
                counts.rows_out[name] = rows
                counts.count_method[name] = method
            except CountError as exc:
                counts.warnings.append(f"row count skipped for {name}: {exc}")
            try:
                names, dtypes = schema_of(local_variables.get(name, value))
                counts.columns_out[name] = names
                counts.dtypes_out[name] = dtypes
            except Exception as exc:  # noqa: BLE001
                counts.warnings.append(
                    f"schema skipped for {name}: {type(exc).__name__}: {exc}"
                )
        outputs: list[FileFingerprint] = []
        for item in spec.output_files:
            path = str(item.get("path") or "")
            if not path:
                continue
            fp = fingerprint_file(
                path,
                "output",
                spec.node_id,
                None,
                cache=self._cache,
                cancel=self._cancel,
                hash_enabled=self._options.hash_outputs,
                hash_max_bytes=self._hash_max_bytes(),
                use_cache=False,  # an output was just written: never trust a cache
            )
            if mode != "off" and fp.size_bytes is not None:
                rows = count_rows_in_file(
                    path,
                    str(item.get("format") or "csv"),
                    str(item.get("delimiter") or ","),
                )
                fp = replace(
                    fp,
                    row_count=rows,
                    row_count_method="output_file" if rows is not None else "none",
                )
            outputs.append(fp)
        counts.count_seconds = time.perf_counter() - started
        with self._lock:
            self._counts[spec.node_id] = counts
            self._fingerprints_out.extend(outputs)

    # -- node results (GUI thread) --------------------------------------
    def _rows_in(self, node_id: int) -> list[dict]:
        entries = []
        for edge in sorted(
            (e for e in self._edges if e.dst_node_id == node_id),
            key=lambda e: e.dst_socket,
        ):
            source = self._spec_by_id.get(edge.src_node_id)
            variable = None
            rows = None
            if source is not None and 0 <= edge.src_socket < len(
                source.output_variables
            ):
                variable = source.output_variables[edge.src_socket]
                counts = self._counts.get(edge.src_node_id)
                if counts is not None:
                    rows = counts.rows_out.get(variable)
            entries.append(
                {
                    "socket": edge.dst_socket,
                    "from_node_id": edge.src_node_id,
                    "from_socket": edge.src_socket,
                    "variable": variable,
                    "rows": rows,
                }
            )
        return entries

    def _spec_for(self, node: Any) -> NodeSpec:
        node_id = getattr(node, "id", None)
        spec = self._spec_by_id.get(node_id)
        if spec is not None:
            return spec
        return NodeSpec(
            node_id=node_id if isinstance(node_id, int) else -1,
            op="unknown",
            title=str(getattr(node, "node_title", "") or ""),
        )

    def _seq_of(self, node_id: int) -> int:
        try:
            return self._order.index(node_id)
        except ValueError:
            return len(self._order)

    def _partial_output_fingerprints(self, spec: NodeSpec) -> list[FileFingerprint]:
        found = []
        for item in spec.output_files:
            path = str(item.get("path") or "")
            size, mtime_ns = _file_state(path) if path else (None, None)
            if (
                size is None
                or mtime_ns is None
                or mtime_ns < self._start_ns - 2_000_000_000
            ):
                continue
            shown = fingerprint_file(path, "output", spec.node_id, hash_enabled=False)
            found.append(replace(shown, error="node failed; file may be partial"))
        return found

    def _test_summary_of(self, node: Any, explicit: dict | None) -> dict | None:
        if explicit is not None:
            return sanitize(explicit)
        summary = getattr(getattr(node, "content", None), "test_summary", None)
        if summary is None:
            return None
        try:
            if dataclasses.is_dataclass(summary) and not isinstance(summary, type):
                return sanitize(dataclasses.asdict(summary))
            if hasattr(summary, "to_dict"):
                return sanitize(summary.to_dict())
            if isinstance(summary, dict):
                return sanitize(summary)
        except Exception as exc:  # noqa: BLE001
            logger.debug("audit: test summary not stored: {}", exc)
        return None

    def node_finished(
        self,
        record: RunRecord,
        node: Any,
        execution_result: Any,
        *,
        rows_out: dict | None = None,
        test_summary: dict | None = None,
    ) -> NodeRunRecord:
        result = execution_result
        with self._lock:
            spec = self._spec_for(node)
            counts = self._counts.get(spec.node_id) or _NodeCounts()
            ok = bool(getattr(result, "success", False))
            code = str(getattr(result, "code", "") or "")
            if code:
                self._code_parts.append(code)
            rows_in = self._rows_in(spec.node_id)
            out_rows = dict(counts.rows_out)
            if rows_out is not None:
                out_rows.update(rows_out)
            if self._mode == "sink" and spec.output_files and rows_in:
                mine = [
                    fp
                    for fp in self._fingerprints_out
                    if fp.node_id == spec.node_id and fp.row_count is not None
                ]
                if mine and rows_in[0]["rows"] is None:
                    rows_in[0]["rows"] = mine[0].row_count
            warnings = [
                _cap_warning(str(w))
                for w in [*(getattr(result, "warnings", None) or []), *counts.warnings]
            ][:MAX_WARNINGS]
            error = None
            if not ok:
                error = error_to_dict(
                    result,
                    node,
                    enrich=self._options.sync_enrich,
                    redact=self._options.redact_values,
                    enricher=self.error_enricher,
                )
                self._fingerprints_out.extend(self._partial_output_fingerprints(spec))
            node_record = NodeRunRecord(
                node_id=spec.node_id,
                op=spec.op,
                title=spec.title,
                status="ok" if ok else "failed",
                seq=self._seq_of(spec.node_id),
                label=spec.label,
                started_at=getattr(result, "started_at", None) or None,
                duration_s=round(
                    float(getattr(result, "execution_time", 0.0) or 0.0), 6
                ),
                count_seconds=round(counts.count_seconds, 6),
                settings=sanitize(spec.settings),
                seed=extract_seed(spec.settings),
                code_sha256=sha256_hex(code.encode("utf-8")) if code else None,
                rows_in=rows_in,
                rows_out=out_rows,
                columns_out=dict(counts.columns_out),
                dtypes_out=dict(counts.dtypes_out),
                count_method=dict(counts.count_method),
                peak_memory_mb=round(
                    float(getattr(result, "peak_memory", 0.0) or 0.0), 3
                ),
                warnings=warnings,
                error=error,
                test_summary=self._test_summary_of(node, test_summary) if ok else None,
            )
            self._node_records[spec.node_id] = node_record
            return node_record

    def node_errored(
        self, record: RunRecord, node: Any, exc: BaseException
    ) -> NodeRunRecord:
        with self._lock:
            spec = self._spec_for(node)
            error = exception_to_dict(
                exc,
                node,
                enrich=self._options.sync_enrich,
                redact=self._options.redact_values,
                enricher=self.error_enricher,
            )
            self._fingerprints_out.extend(self._partial_output_fingerprints(spec))
            node_record = NodeRunRecord(
                node_id=spec.node_id,
                op=spec.op,
                title=spec.title,
                status="failed",
                seq=self._seq_of(spec.node_id),
                label=spec.label,
                settings=sanitize(spec.settings),
                seed=extract_seed(spec.settings),
                rows_in=self._rows_in(spec.node_id),
                error=error,
            )
            self._node_records[spec.node_id] = node_record
            return node_record

    def update_node_error(self, node_id: int, error: dict) -> None:
        """Replace a failed node's error before the record is sealed."""
        with self._lock:
            if self._record is not None and self._record.run_id in self._sealed_ids:
                raise RunAlreadySealed(self._record.run_id)
            existing = self._node_records.get(node_id)
            if existing is not None:
                self._node_records[node_id] = replace(existing, error=sanitize(error))

    # -- snapshots ------------------------------------------------------
    def _in_flight_dict(self) -> dict | None:
        record = self._record
        if record is None:
            return None
        nodes = [
            self._node_records[node_id]
            for node_id in self._order
            if node_id in self._node_records
        ]
        data = replace(
            record,
            nodes=nodes,
            inputs=list(self._fingerprints_in),
            outputs=list(self._fingerprints_out),
            warnings=list(self._warnings),
        ).to_dict()
        data["status"] = "running"
        data["record_hash"] = ""
        return data

    def snapshot(self, record: RunRecord | None = None) -> dict | None:
        """A deep copy of the in-flight (or a sealed) record as a plain dict."""
        with self._lock:
            if record is not None and record.status != "running":
                return copy.deepcopy(record.to_dict())
            data = self._in_flight_dict()
            return copy.deepcopy(data) if data is not None else None

    # -- finish ---------------------------------------------------------
    def _baseline(self, inputs: list[FileFingerprint], workflow_path: str | None):
        if not self._options.enabled:
            return None
        try:
            if self._directory is not None:
                previous = self._store.latest_record_dict(self._directory)
            else:
                previous = self._store.latest_record_dict(
                    self._options.store_dir or None, workflow_path
                )
        except Exception:  # noqa: BLE001
            previous = None
        if not previous:
            return None
        old = {
            (item.get("path"), item.get("sheet")): item
            for item in previous.get("inputs") or []
            if isinstance(item, dict)
        }
        new = {(fp.path, fp.sheet): fp for fp in inputs}
        changes = []
        for key, fp in new.items():
            before = old.get(key)
            if before is None:
                changes.append(
                    {
                        "path": fp.path,
                        "change": "added",
                        "old_sha256": None,
                        "new_sha256": fp.sha256,
                    }
                )
                continue
            old_sha, new_sha = before.get("sha256"), fp.sha256
            if old_sha and new_sha:
                differs = old_sha != new_sha
            else:
                differs = before.get("size_bytes") != fp.size_bytes
            if differs:
                changes.append(
                    {
                        "path": fp.path,
                        "change": "modified",
                        "old_sha256": old_sha,
                        "new_sha256": new_sha,
                    }
                )
        for key, before in old.items():
            if key not in new:
                changes.append(
                    {
                        "path": before.get("path"),
                        "change": "removed",
                        "old_sha256": before.get("sha256"),
                        "new_sha256": None,
                    }
                )
        return {"run_id": previous.get("run_id"), "input_changes": changes}

    def _skipped_record(self, spec: NodeSpec) -> NodeRunRecord:
        return NodeRunRecord(
            node_id=spec.node_id,
            op=spec.op,
            title=spec.title,
            status="skipped",
            seq=self._seq_of(spec.node_id),
            label=spec.label,
            settings=sanitize(spec.settings),
            seed=extract_seed(spec.settings),
            rows_in=self._rows_in(spec.node_id),
        )

    def _finalise_inputs(self) -> list[FileFingerprint]:
        inputs = []
        for fp in self._fingerprints_in:
            spec = self._spec_by_id.get(fp.node_id)
            counts = self._counts.get(fp.node_id)
            if (
                spec is not None
                and counts is not None
                and len(spec.input_files) == 1
                and fp.row_count is None
            ):
                variable = spec.output_variables[0] if spec.output_variables else None
                rows = counts.rows_out.get(variable) if variable else None
                if rows is not None:
                    fp = replace(
                        fp,
                        row_count=rows,
                        row_count_method=counts.count_method.get(variable, "none"),
                    )
            inputs.append(fp)
        return inputs

    def _reconcile(self, nodes: list[NodeRunRecord], outputs: list[FileFingerprint]):
        warnings = []
        for node in nodes:
            spec = self._spec_by_id.get(node.node_id)
            if spec is None or len(spec.output_files) != 1 or not node.rows_in:
                continue
            received = node.rows_in[0].get("rows")
            written = [
                fp.row_count
                for fp in outputs
                if fp.node_id == node.node_id and fp.row_count is not None
            ]
            if received is not None and written and received != written[0]:
                path = spec.output_files[0].get("path")
                warnings.append(
                    f"row count mismatch: {node.title} received {received} rows "
                    f"but {recorded_path(path) if path else '?'} contains {written[0]}"
                )
        return warnings

    def finish(
        self,
        record: RunRecord,
        success: bool,
        *,
        cancelled: bool = False,
        outputs: Sequence[FileFingerprint] | None = None,
        save: bool = True,
    ) -> RunRecord:
        with self._lock:
            if record.run_id in self._sealed_ids:
                raise RunAlreadySealed(record.run_id)
            warnings = list(self._warnings)
            nodes = []
            for node_id in self._order:
                existing = self._node_records.get(node_id)
                if existing is None:
                    spec = self._spec_by_id[node_id]
                    existing = self._skipped_record(spec)
                nodes.append(existing)
            inputs = self._finalise_inputs()
            out_list = (
                list(outputs) if outputs is not None else list(self._fingerprints_out)
            )
            for fp in inputs:
                if fp.sha256_status in ("skipped_size_limit", "error", "cancelled"):
                    warnings.append(f"input not hashed ({fp.sha256_status}): {fp.path}")
                elif fp.sha256_status == "missing":
                    warnings.append(f"input file not found: {fp.path}")
            warnings.extend(self._reconcile(nodes, out_list))

            code = "\n".join(self._code_parts)
            code_sha = sha256_hex(code.encode("utf-8"))
            embed = (
                self._options.embed_code and len(code.encode("utf-8")) <= MAX_CODE_BYTES
            )
            status = "cancelled" if cancelled else ("ok" if success else "failed")
            final = replace(
                record,
                status=status,
                finished_at=utc_now_iso(),
                duration_s=round(time.perf_counter() - self._perf_start, 6),
                inputs=inputs,
                outputs=out_list,
                nodes=nodes,
                baseline=self._baseline(inputs, record.workflow_path),
                warnings=warnings,
                generated_code=code if embed else None,
                generated_code_sha256=code_sha,
            )
            if not save or not self._options.enabled:
                self._discard_marker()
                self._cache_save()
                return final
            try:
                sealed, path = self._store.seal_and_save(
                    final, self._options.store_dir or None
                )
            except RunAlreadySealed:
                raise
            except (OSError, StoreLockTimeout, TypeError, ValueError) as exc:
                logger.error("audit: the run record could not be saved: {}", exc)
                self._last_path = None
                self._cache_save()
                return final
            self._sealed_ids.add(record.run_id)
            self._last_path = path
            self._cache_save()
            return sealed

    def _discard_marker(self) -> None:
        """A run that is not recorded leaves no marker and no new folder."""
        folder = self._marker_dir
        if folder is None or self._record is None:
            return
        try:
            os.unlink(folder / f"{self._record.run_id}.started")
        except OSError:
            pass
        if not self._dir_preexisted:
            for name in (CACHE_FILENAME,):
                try:
                    (folder / name).unlink()
                except OSError:
                    pass
            try:
                folder.rmdir()
            except OSError:
                pass

    def _cache_save(self) -> None:
        try:
            self._cache.save()
        except Exception as exc:  # noqa: BLE001
            logger.debug("audit: hash cache not saved: {}", exc)
