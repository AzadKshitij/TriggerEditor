"""Run-record dataclasses and validation (docs/plan/02-audit-trail.md 3.3, 3.8).

Qt-free. ``to_dict`` is the on-disk shape; verification always works on the raw
parsed dict, never on a dataclass round trip (unknown keys must stay covered).
"""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass, field
from typing import Any

from trigger_designer.core.audit.canonical import GENESIS_HASH

RUN_RECORD_SCHEMA_VERSION = 1
HASH_ALGO = "sha256-canonical-json-v1"

RUN_STATUSES = ("ok", "failed", "cancelled")
NODE_STATUSES = ("ok", "failed", "skipped")
SHA_STATUSES = (
    "computed",
    "cached",
    "skipped_size_limit",
    "disabled",
    "missing",
    "error",
    "cancelled",
)

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _known(cls, data: dict) -> dict:
    names = {f.name for f in dataclasses.fields(cls)}
    return {k: v for k, v in data.items() if k in names}


@dataclass(frozen=True)
class FileFingerprint:
    role: str  # "input" | "output"
    path: str
    size_bytes: int | None = None
    modified_time: str | None = None
    sha256: str | None = None
    sheet: str | None = None
    node_id: int | None = None
    mtime_ns: int | None = None
    sha256_status: str = "disabled"
    row_count: int | None = None
    row_count_method: str = "none"
    error: str | None = None

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @staticmethod
    def from_dict(d: dict) -> FileFingerprint:
        return FileFingerprint(**_known(FileFingerprint, d))


@dataclass(frozen=True)
class NodeRunRecord:
    node_id: int
    op: str
    title: str
    status: str  # "ok" | "failed" | "skipped"
    seq: int = 0
    label: str | None = None
    started_at: str | None = None
    duration_s: float = 0.0
    count_seconds: float = 0.0
    settings: dict = field(default_factory=dict)
    seed: int | None = None
    code_sha256: str | None = None
    rows_in: list = field(default_factory=list)
    rows_out: dict = field(default_factory=dict)
    columns_out: dict = field(default_factory=dict)
    dtypes_out: dict = field(default_factory=dict)
    count_method: dict = field(default_factory=dict)
    #: ``None`` = not measured (the executor does not measure memory).
    peak_memory_mb: float | None = None
    warnings: list = field(default_factory=list)
    error: dict | None = None
    test_summary: dict | None = None

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @staticmethod
    def from_dict(d: dict) -> NodeRunRecord:
        return NodeRunRecord(**_known(NodeRunRecord, d))


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    started_at: str
    finished_at: str
    status: str  # "running" (in flight only) | "ok" | "failed" | "cancelled"
    app_version: str
    workflow_schema_version: int
    workflow_path: str | None
    workflow_sha256: str | None
    user: str | None
    machine: str | None
    python_version: str
    polars_version: str
    inputs: list = field(default_factory=list)  # [FileFingerprint]
    outputs: list = field(default_factory=list)  # [FileFingerprint]
    nodes: list = field(default_factory=list)  # [NodeRunRecord]
    generated_code: str | None = None
    # extensions (all defaulted)
    schema_version: int = RUN_RECORD_SCHEMA_VERSION
    seq: int = 0
    duration_s: float = 0.0
    app_name: str = "TriggerDesigner"
    duckdb_version: str | None = None
    os_name: str = ""
    workflow_uuid: str | None = None
    graph_sha256: str = ""
    workflow_modified_since_save: bool | None = None
    options: dict = field(default_factory=dict)
    baseline: dict | None = None
    warnings: list = field(default_factory=list)
    generated_code_sha256: str = ""
    hash_algo: str = HASH_ALGO
    prev_record_hash: str = GENESIS_HASH
    record_hash: str = ""

    def to_dict(self) -> dict:
        out: dict[str, Any] = {}
        for f in dataclasses.fields(self):
            value = getattr(self, f.name)
            if f.name in ("inputs", "outputs", "nodes"):
                value = [
                    item.to_dict() if hasattr(item, "to_dict") else dict(item)
                    for item in value
                ]
            elif isinstance(value, dict):
                value = dict(value)
            elif isinstance(value, list):
                value = list(value)
            out[f.name] = value
        return out

    @staticmethod
    def from_dict(d: dict) -> RunRecord:
        data = _known(RunRecord, d)
        data["inputs"] = [FileFingerprint.from_dict(x) for x in d.get("inputs") or []]
        data["outputs"] = [FileFingerprint.from_dict(x) for x in d.get("outputs") or []]
        data["nodes"] = [NodeRunRecord.from_dict(x) for x in d.get("nodes") or []]
        return RunRecord(**data)


#: Run-level keys a record must carry (3.3). Derived from the dataclass so the
#: document and the code cannot drift; a test pins the list. This is the set for
#: the *current* schema version; use :func:`required_run_keys` for a record.
REQUIRED_RUN_KEYS = tuple(f.name for f in dataclasses.fields(RunRecord))

#: Evolution rule: a field added after version 1 is listed here with the schema
#: version that introduced it (and ``RUN_RECORD_SCHEMA_VERSION`` is raised to
#: it). Only records of that version or newer must carry the key, so an older
#: sealed record, whose hash covers its original bytes, still validates.
#: Every field not listed here has been required since version 1.
FIELD_ADDED_IN: dict[str, int] = {}


def required_run_keys(schema_version: Any = None) -> tuple[str, ...]:
    """Keys a record of ``schema_version`` must carry (current when unknown)."""
    if not _is_int(schema_version):
        schema_version = RUN_RECORD_SCHEMA_VERSION
    return tuple(
        key for key in REQUIRED_RUN_KEYS if FIELD_ADDED_IN.get(key, 1) <= schema_version
    )


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _check_hash(errors: list[str], where: str, value: Any) -> None:
    if not isinstance(value, str) or not _HEX64.match(value):
        errors.append(f"{where}: expected 64 lowercase hex characters")


def _check_fingerprints(errors: list[str], key: str, items: Any) -> None:
    if not isinstance(items, list):
        errors.append(f"{key}: expected a list")
        return
    for i, item in enumerate(items):
        where = f"{key}[{i}]"
        if not isinstance(item, dict):
            errors.append(f"{where}: expected an object")
            continue
        if not isinstance(item.get("path"), str):
            errors.append(f"{where}.path: expected a string")
        status = item.get("sha256_status")
        if status not in SHA_STATUSES:
            errors.append(
                f"{where}.sha256_status: expected one of {'/'.join(SHA_STATUSES)}"
            )
        sha = item.get("sha256")
        if sha is not None:
            _check_hash(errors, f"{where}.sha256", sha)


def validate_record_dict(d: dict) -> list[str]:
    """Problems found in a raw record dict; ``[]`` when it is valid."""
    errors: list[str] = []
    if not isinstance(d, dict):
        return ["record: expected an object"]
    for key in required_run_keys(d.get("schema_version")):
        if key not in d:
            errors.append(f"{key}: required key is missing")
    version = d.get("schema_version")
    if "schema_version" in d:
        if not _is_int(version):
            errors.append("schema_version: expected an integer")
        elif version > RUN_RECORD_SCHEMA_VERSION:
            errors.append(
                f"schema_version: {version} is newer than this version understands "
                f"({RUN_RECORD_SCHEMA_VERSION})"
            )
    if "run_id" in d and not (isinstance(d["run_id"], str) and d["run_id"]):
        errors.append("run_id: expected a non-empty string")
    if "seq" in d and not _is_int(d["seq"]):
        errors.append("seq: expected an integer")
    if "status" in d and d["status"] not in RUN_STATUSES:
        errors.append(f"status: expected one of {'/'.join(RUN_STATUSES)}")
    for key in ("started_at", "finished_at"):
        if key in d and not isinstance(d[key], str):
            errors.append(f"{key}: expected a string")
    for key in ("record_hash", "prev_record_hash", "graph_sha256"):
        if key in d:
            _check_hash(errors, key, d[key])
    if "generated_code_sha256" in d:
        _check_hash(errors, "generated_code_sha256", d["generated_code_sha256"])
    if d.get("workflow_sha256") is not None:
        _check_hash(errors, "workflow_sha256", d["workflow_sha256"])
    if "inputs" in d:
        _check_fingerprints(errors, "inputs", d["inputs"])
    if "outputs" in d:
        _check_fingerprints(errors, "outputs", d["outputs"])
    if "nodes" in d:
        nodes = d["nodes"]
        if not isinstance(nodes, list):
            errors.append("nodes: expected a list")
        else:
            for i, node in enumerate(nodes):
                _check_node(errors, f"nodes[{i}]", node)
    if "options" in d and not isinstance(d["options"], dict):
        errors.append("options: expected an object")
    if "warnings" in d and not isinstance(d["warnings"], list):
        errors.append("warnings: expected a list")
    return errors


def _check_node(errors: list[str], where: str, node: Any) -> None:
    if not isinstance(node, dict):
        errors.append(f"{where}: expected an object")
        return
    if not _is_int(node.get("node_id")):
        errors.append(f"{where}.node_id: expected an integer")
    if node.get("status") not in NODE_STATUSES:
        errors.append(f"{where}.status: expected one of {'/'.join(NODE_STATUSES)}")
    err = node.get("error")
    if err is not None:
        if not isinstance(err, dict):
            errors.append(f"{where}.error: expected an object or null")
        else:
            for sub in ("code", "title"):
                if not isinstance(err.get(sub), str):
                    errors.append(f"{where}.error.{sub}: expected a string")
    summary = node.get("test_summary")
    if summary is not None and not isinstance(summary, dict):
        errors.append(f"{where}.test_summary: expected an object or null")
