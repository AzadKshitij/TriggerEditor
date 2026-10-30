"""Read and statically validate a ``.tds`` file without Qt or Polars (plan 08 S1)."""

from __future__ import annotations

import hashlib
import json
import locale
import os
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from trigger_designer.core.constants import WORKFLOW_SCHEMA_VERSION
from trigger_designer.core.headless.exit_codes import CliError, ExitCode
from trigger_designer.core.headless.op_catalog import OPS, known_op, node_op


@dataclass(frozen=True)
class Finding:
    level: str  # "error" | "warning"
    td_code: str
    message: str
    node_id: int | None = None

    def to_dict(self) -> dict:
        return {
            "level": self.level,
            "code": self.td_code,
            "message": self.message,
            "node_id": self.node_id,
        }


@dataclass(frozen=True)
class WorkflowDoc:
    path: str
    raw: bytes
    data: dict
    sha256: str
    encoding: str
    schema_version: int

    @property
    def metadata(self) -> dict:
        meta = self.data.get("workflow_metadata")
        return meta if isinstance(meta, dict) else {}

    @property
    def nodes(self) -> list[dict]:
        return [n for n in self.data.get("nodes", []) if isinstance(n, dict)]

    @property
    def base_dir(self) -> str:
        # abspath, not resolve(): resolve() turns a subst or mapped drive into
        # its target, so paths saved with the drive letter would no longer
        # compare as being inside the folder.
        return os.path.dirname(os.path.abspath(self.path))


@dataclass(frozen=True)
class FileNode:
    node_id: int
    kind: str  # "input" | "output"
    raw_path: str
    title: str
    op: str | None = None
    key: str = "filePath"


def _decode(raw: bytes) -> tuple[str, str]:
    """UTF-8 (BOM tolerated), then the locale encoding, then cp1252."""
    try:
        return raw.decode("utf-8-sig"), "utf-8"
    except UnicodeDecodeError:
        pass
    for name in (locale.getpreferredencoding(False), "cp1252"):
        try:
            return raw.decode(name), name.lower().replace("_", "-")
        except UnicodeDecodeError, LookupError:
            continue
    raise CliError(
        ExitCode.INVALID, "TD-CLI-001", "The file is not text in a known encoding."
    )


def parse_workflow_bytes(raw: bytes, path: str = "") -> WorkflowDoc:
    text, encoding = _decode(raw)
    shown = path or "the file"
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise CliError(
            ExitCode.INVALID, "TD-CLI-001", f"{shown} is not valid JSON ({exc})."
        ) from None
    if (
        not isinstance(data, dict)
        or not isinstance(data.get("nodes"), list)
        or not isinstance(data.get("edges"), list)
    ):
        raise CliError(
            ExitCode.INVALID,
            "TD-CLI-001",
            f"{shown} has no 'nodes' and 'edges' lists.",
        )
    meta = data.get("workflow_metadata")
    version = meta.get("schema_version", 0) if isinstance(meta, dict) else 0
    return WorkflowDoc(
        path=path,
        raw=raw,
        data=data,
        sha256=hashlib.sha256(raw).hexdigest(),
        encoding=encoding,
        schema_version=version if isinstance(version, int) else 0,
    )


def read_workflow(path: str) -> WorkflowDoc:
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        raise CliError(
            ExitCode.INVALID,
            "TD-CLI-001",
            f"Cannot read {path}: {exc.strerror or exc}.",
            "Check the path and that no other program has the file locked.",
        ) from None
    return parse_workflow_bytes(raw, path)


def _title(node: dict) -> str:
    return str(node.get("title") or node.get("node_title") or node.get("id") or "?")


def _socket_owner(nodes: list[dict]) -> dict[Any, Any]:
    owner: dict[Any, Any] = {}
    for node in nodes:
        for key in ("inputs", "outputs"):
            for sock in node.get(key) or []:
                if isinstance(sock, dict) and "id" in sock:
                    owner[sock["id"]] = node.get("id")
    return owner


def find_cycle(data: dict) -> bool:
    """Kahn's algorithm over node ids; True when the graph has a loop."""
    nodes = [n for n in data.get("nodes", []) if isinstance(n, dict)]
    owner = _socket_owner(nodes)
    ids = [n.get("id") for n in nodes]
    indeg = dict.fromkeys(ids, 0)
    out: dict[Any, list] = {i: [] for i in ids}
    for edge in data.get("edges", []):
        if not isinstance(edge, dict):
            continue
        src, dst = owner.get(edge.get("start")), owner.get(edge.get("end"))
        if src is None or dst is None or src not in indeg or dst not in indeg:
            continue
        out[src].append(dst)
        indeg[dst] += 1
    queue = deque(i for i, d in indeg.items() if d == 0)
    seen = 0
    while queue:
        cur = queue.popleft()
        seen += 1
        for nxt in out[cur]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                queue.append(nxt)
    return seen != len(ids)


def _writes_files(doc: WorkflowDoc) -> bool:
    for node in doc.nodes:
        info = known_op(node_op(node) or "")
        if info is not None and info.output_keys:
            return True
    return any(fn.kind == "output" for fn in file_nodes(doc))


def static_validate(doc: WorkflowDoc) -> list[Finding]:
    findings: list[Finding] = []
    if doc.schema_version > WORKFLOW_SCHEMA_VERSION:
        findings.append(
            Finding(
                "error",
                "TD-CLI-002",
                f"saved by a newer Trigger Designer (schema {doc.schema_version}); "
                "update this program",
            )
        )
    if not doc.metadata:
        findings.append(
            Finding("warning", "TD-CLI-001", "legacy v1 file (no workflow_metadata)")
        )
    for node in doc.nodes:
        nid = node.get("id") if isinstance(node.get("id"), int) else None
        op = node_op(node)
        if op is None:
            findings.append(
                Finding(
                    "warning",
                    "TD-CLI-003",
                    f"legacy node '{_title(node)}' has no op id; --deep resolves it",
                    nid,
                )
            )
        elif known_op(op) is None:
            findings.append(
                Finding(
                    "error",
                    "TD-CLI-003",
                    f"unknown node type '{op}' (node '{_title(node)}')",
                    nid,
                )
            )
    if find_cycle(doc.data):
        findings.append(Finding("error", "TD-CLI-004", "the graph has a cycle"))
    owner = _socket_owner(doc.nodes)
    for edge in doc.data.get("edges", []):
        if isinstance(edge, dict) and (
            edge.get("start") not in owner or edge.get("end") not in owner
        ):
            findings.append(
                Finding("warning", "TD-CLI-001", "an edge points at a missing socket")
            )
            break
    if not _writes_files(doc):
        findings.append(
            Finding("warning", "TD-CLI-018", "this workflow writes no files")
        )
    return findings


def settings_holder(content: dict, key: str) -> dict | None:
    """The dict holding ``key``: the content itself or its ``settings``."""
    if key in content:
        return content
    settings = content.get("settings")
    if isinstance(settings, dict) and key in settings:
        return settings
    return None


def split_path_lines(value) -> list[str]:
    """The non-empty, stripped lines of a multi-line path setting."""
    return [line.strip() for line in str(value or "").splitlines() if line.strip()]


def _file_keys(op: str | None, title: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """(input keys, output keys) of a node, from the op catalogue; a legacy
    node without an op id is recognised by its title."""
    info = known_op(op or "")
    if info is None and op is None:
        info = next((i for i in OPS.values() if i.title == title), None)
    if info is None:
        return (), ()
    return info.input_keys, info.output_keys


def file_nodes(doc: WorkflowDoc) -> list[FileNode]:
    """Every node that reads or writes a file, one row per path key.

    Driven by ``op_catalog`` (``input_keys`` / ``output_keys``), so a new
    file-touching op shows up in ``approve``, ``info`` and ``paths``.
    """
    found: list[FileNode] = []
    for node in doc.nodes:
        op = node_op(node)
        title = _title(node)
        in_keys, out_keys = _file_keys(op, title)
        content = node.get("content")
        content = content if isinstance(content, dict) else {}
        nid = node.get("id")
        for kind, keys in (("input", in_keys), ("output", out_keys)):
            for key in keys:
                holder = settings_holder(content, key)
                raw_path = str(holder.get(key) or "") if holder else ""
                found.append(
                    FileNode(
                        nid if isinstance(nid, int) else -1,
                        kind,
                        raw_path,
                        title,
                        op,
                        key,
                    )
                )
        info = known_op(op or "")
        for key in info.list_keys if info else ():
            holder = settings_holder(content, key)
            for line in split_path_lines(holder.get(key) if holder else ""):
                found.append(
                    FileNode(
                        nid if isinstance(nid, int) else -1,
                        "input",
                        line,
                        title,
                        op,
                        key,
                    )
                )
    return found


def op_counts(doc: WorkflowDoc) -> dict[str, int]:
    counts: dict[str, int] = {}
    for node in doc.nodes:
        key = node_op(node) or f"unknown:{_title(node)}"
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))
