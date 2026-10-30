"""Display helpers for the Run History dock (docs/plan/02-audit-trail.md 3.15).

Qt-free: plain rows of strings that the Qt models wrap.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def format_duration(seconds: float | None) -> str:
    """``12 ms``, ``0.9 s``, ``2 min 05 s``, ``1 h 02 min``."""
    if seconds is None:
        return "-"
    seconds = max(0.0, float(seconds))
    if seconds < 0.9995:
        return f"{round(seconds * 1000)} ms"
    if seconds < 60:
        return f"{seconds:.1f} s"
    total = round(seconds)
    minutes, secs = divmod(total, 60)
    if minutes < 60:
        return f"{minutes} min {secs:02d} s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h {minutes:02d} min"


def format_local_time(iso: str | None) -> str:
    """UTC ``...Z`` text as local ``YYYY-MM-DD HH:MM:SS``; the input on failure."""
    if not iso:
        return ""
    try:
        parsed = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)
        return parsed.astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except ValueError, OverflowError, OSError:
        return str(iso)


def _short(sha: str | None, n: int = 8) -> str:
    return sha[:n] if sha else "-"


def _file_name(path: str | None) -> str:
    return (path or "").replace("\\", "/").rsplit("/", 1)[-1]


def _count(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def total_rows_out(node: dict) -> int | None:
    """Sum of a node's counted outputs; ``None`` when none was counted."""
    values = [v for v in (node.get("rows_out") or {}).values() if _count(v) is not None]
    return sum(values) if values else None


def run_rows_out(record: dict) -> int | None:
    """Rows written by the run: the sum over output files, else over sinks."""
    outputs = [
        fp.get("row_count")
        for fp in record.get("outputs") or []
        if _count(fp.get("row_count")) is not None
    ]
    return sum(outputs) if outputs else None


def _hash_state(items: list[dict]) -> str:
    if not items:
        return "none"
    states = {i.get("sha256_status") for i in items}
    if states <= {"computed", "cached"}:
        return "all hashed"
    parts = sorted(s for s in states if s not in ("computed", "cached"))
    return "not all hashed (" + ", ".join(parts) + ")"


def run_summary_rows(rec: dict) -> list[tuple[str, str]]:
    """``(label, value)`` rows of the Summary pane."""
    nodes = rec.get("nodes") or []
    inputs = rec.get("inputs") or []
    outputs = rec.get("outputs") or []
    failed = sum(1 for n in nodes if n.get("status") == "failed")
    skipped = sum(1 for n in nodes if n.get("status") == "skipped")
    rows: list[tuple[str, str]] = [
        ("Run id", str(rec.get("run_id", ""))),
        ("Sequence", str(rec.get("seq", ""))),
        ("Status", str(rec.get("status", ""))),
        ("Started", format_local_time(rec.get("started_at"))),
        ("Ended", format_local_time(rec.get("finished_at"))),
        ("Duration", format_duration(rec.get("duration_s"))),
    ]
    path = rec.get("workflow_path")
    if path:
        rows.append(
            (
                "Workflow",
                f"{_file_name(path)} (sha {_short(rec.get('workflow_sha256'))})",
            )
        )
    else:
        rows.append(("Workflow", f"unsaved (graph {_short(rec.get('graph_sha256'))})"))
    if rec.get("workflow_modified_since_save") is True:
        rows.append(("Note", "Workflow had unsaved changes"))
    rows.append(("Inputs", f"{len(inputs)} ({_hash_state(inputs)})"))
    rows.append(("Outputs", f"{len(outputs)} ({_hash_state(outputs)})"))
    detail = f"{len(nodes)}"
    if failed or skipped:
        detail += f" ({failed} failed, {skipped} skipped)"
    rows.append(("Nodes", detail))
    options = rec.get("options") or {}
    rows.append(("Row counts", str(options.get("row_count_mode_effective", "")) or "-"))
    who = " @ ".join(p for p in (rec.get("user"), rec.get("machine")) if p)
    if who:
        rows.append(("Run by", who))
    rows.append(
        (
            "Versions",
            (
                f"app {rec.get('app_version', '')}, polars {rec.get('polars_version', '')}, "
                f"python {rec.get('python_version', '')}"
            ),
        )
    )
    baseline = rec.get("baseline") or {}
    changes = baseline.get("input_changes") or []
    if changes:
        rows.append(("Inputs changed", f"{len(changes)} since the previous run"))
    warnings = rec.get("warnings") or []
    if warnings:
        rows.append(("Warnings", str(len(warnings))))
    rows.append(("Record hash", _short(rec.get("record_hash"), 16)))
    return rows


def node_table_rows(rec: dict) -> list[dict]:
    """One dict per node: node, op, status, rows_in, rows_out, columns, duration, error."""
    out = []
    for node in rec.get("nodes") or []:
        sockets = [_count(entry.get("rows")) for entry in node.get("rows_in") or []]
        if not sockets or all(s is None for s in sockets):
            rows_in = "-"
        else:
            rows_in = " + ".join("-" if s is None else str(s) for s in sockets)
        total = total_rows_out(node)
        columns = next(iter((node.get("columns_out") or {}).values()), None)
        error = node.get("error") or {}
        out.append(
            {
                "node": node.get("label") or node.get("title") or "",
                "op": node.get("op", ""),
                "status": node.get("status", ""),
                "rows_in": rows_in,
                "rows_out": "-" if total is None else str(total),
                "columns": "-" if columns is None else str(len(columns)),
                "duration": (
                    "-"
                    if node.get("status") == "skipped"
                    else format_duration(node.get("duration_s"))
                ),
                "error": str(error.get("title") or "") if error else "",
                "node_id": node.get("node_id"),
            }
        )
    return out
