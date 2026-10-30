"""The Run log and Workflow sheets (Qt-free, read-only evidence).

``run_record`` is the plain dict of plan 02 (read with ``.get`` only, so a
missing key renders ``not recorded``). ``workflow`` is the list of plain dicts
built by ``qt/helpers/workflow_snapshot.py``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from trigger_designer.core.audit.view import total_rows_out
from trigger_designer.core.excel.cells import (
    FormatBook,
    guard_text,
    needs_quote_prefix,
    write_text,
)
from trigger_designer.core.workpaper.sheets_summary import BLUE, LIGHT, RED_FILL

NOT_RECORDED = "not recorded"
MAX_SETTING_CHARS = 300
RUNLOG_WIDTHS = (22, 40, 28, 14, 22, 14, 14, 70)
WORKFLOW_WIDTHS = (8, 28, 22, 80, 30)

_STYLES = {
    "rl_title": {"bold": True, "font_size": 14},
    "rl_sub": {"italic": True, "font_color": "#595959"},
    "rl_label": {"bold": True, "bg_color": LIGHT, "valign": "top"},
    "rl_wrap": {"text_wrap": True, "valign": "top"},
    "rl_num": {"num_format": "#,##0", "valign": "top"},
    "rl_dur": {"num_format": "0.000", "valign": "top"},
    "rl_fail": {"text_wrap": True, "valign": "top", "bg_color": RED_FILL},
    "rl_fail_num": {"num_format": "#,##0", "valign": "top", "bg_color": RED_FILL},
    "rl_fail_dur": {"num_format": "0.000", "valign": "top", "bg_color": RED_FILL},
    "rl_section": {"bold": True, "font_color": "#FFFFFF", "bg_color": BLUE},
}


def friendly_op(op: str) -> str:
    """``preparation.select_records`` -> ``Select Records``."""
    tail = str(op or "").rsplit(".", 1)[-1]
    return tail.replace("_", " ").title() if tail else NOT_RECORDED


def _text(v: Any) -> str:
    return NOT_RECORDED if v is None or v == "" else str(v)


def _setup(ws: Any, book: FormatBook, widths: Sequence[int]) -> None:
    for name, props in _STYLES.items():
        book.define(name, props)
    for col, width in enumerate(widths):
        ws.set_column(col, col, width)
    ws.set_tab_color("#7F7F7F")
    ws.set_landscape()
    ws.fit_to_pages(1, 0)
    ws.set_footer("&L&F - &A&RPage &P of &N")


def _merge(
    ws: Any, book: FormatBook, r: int, c0: int, c1: int, text: str, style: str
) -> None:
    text, _ = guard_text(text)
    fmt = book.get(style, needs_quote_prefix(text))
    if c1 > c0:
        ws.merge_range(r, c0, r, c1, "", fmt)
    ws.write_string(r, c0, text, fmt)


def write_runlog_sheet(ws: Any, book: FormatBook, record: Mapping[str, Any]) -> None:
    """Sheet ``Run log``; rows are written in ascending order."""
    _setup(ws, book, RUNLOG_WIDTHS)
    ws.protect("", {"autofilter": True})
    write_text(ws, 0, 0, "Run log", book, "rl_title")
    nodes = list(record.get("nodes") or [])
    status = record.get("status")
    if status in (None, "", "running"):
        finished = [n for n in nodes if n.get("status") in ("ok", "failed")]
        last = (
            (finished[-1].get("title") or friendly_op(finished[-1].get("op", "")))
            if finished
            else "none"
        )
        banner = (
            "Snapshot taken while the workflow was running: steps up to and including "
            f"{last} are listed; this step and later steps are not."
        )
    else:
        banner = "Completed run."
    write_text(ws, 1, 0, banner, book, "rl_sub")

    user, machine = record.get("user"), record.get("machine")
    run_by = f"{user}@{machine}" if user and machine else (user or machine or None)
    pairs = [
        ("Run ID", record.get("run_id")),
        ("Status", status),
        ("Started (UTC)", record.get("started_at")),
        ("Finished (UTC)", record.get("finished_at")),
        ("Run by", run_by),
        ("Application version", record.get("app_version")),
        ("Python", record.get("python_version")),
        ("Polars", record.get("polars_version")),
        ("Workflow file", record.get("workflow_path")),
        ("Workflow SHA-256", record.get("workflow_sha256")),
    ]
    r = 3
    for label, value in pairs:
        write_text(ws, r, 0, label, book, "rl_label")
        _merge(ws, book, r, 1, 7, _text(value), "rl_wrap")
        r += 1

    files = [
        *(record.get("inputs") or []),
        *(record.get("outputs") or []),
    ]
    r += 1
    for c, head in enumerate(
        ("Role", "Path", "Sheet", "Size (bytes)", "Modified (UTC)", "SHA-256")
    ):
        write_text(ws, r, c, head, book, "hdr")
    ws.merge_range(r, 5, r, 7, "", book.get("hdr"))
    write_text(ws, r, 5, "SHA-256", book, "hdr")
    r += 1
    if not files:
        _merge(ws, book, r, 0, 7, "No files were recorded in this run.", "rl_wrap")
        r += 1
    for f in files:
        write_text(ws, r, 0, _text(f.get("role")), book, "rl_wrap")
        write_text(ws, r, 1, _text(f.get("path")), book, "rl_wrap")
        write_text(ws, r, 2, str(f.get("sheet") or ""), book, "rl_wrap")
        if isinstance(f.get("size_bytes"), int):
            ws.write_number(r, 3, f["size_bytes"], book.get("rl_num"))
        else:
            write_text(ws, r, 3, NOT_RECORDED, book, "rl_wrap")
        write_text(ws, r, 4, _text(f.get("modified_time")), book, "rl_wrap")
        _merge(
            ws,
            book,
            r,
            5,
            7,
            _text(f.get("sha256") or f.get("sha256_status")),
            "rl_wrap",
        )
        r += 1

    r += 1
    heads = (
        "Step",
        "Node",
        "Type",
        "Status",
        "Started (UTC)",
        "Duration (s)",
        "Rows out",
        "Message",
    )
    for c, head in enumerate(heads):
        write_text(ws, r, c, head, book, "hdr")
    r += 1
    for i, node in enumerate(nodes, start=1):
        failed = node.get("status") == "failed"
        wrap, num, dur = (
            ("rl_fail", "rl_fail_num", "rl_fail_dur")
            if failed
            else ("rl_wrap", "rl_num", "rl_dur")
        )
        title = str(node.get("title") or friendly_op(node.get("op", "")))
        if node.get("label"):
            title += f" ({node['label']})"
        error = node.get("error") or {}
        if error:
            message = " - ".join(
                x for x in (error.get("title"), error.get("hint")) if x
            )
        else:
            message = "; ".join(str(w) for w in (node.get("warnings") or []))
        ws.write_number(r, 0, i, book.get(num))
        write_text(ws, r, 1, title, book, wrap)
        write_text(ws, r, 2, friendly_op(node.get("op", "")), book, wrap)
        write_text(ws, r, 3, _text(node.get("status")), book, wrap)
        write_text(ws, r, 4, _text(node.get("started_at")), book, wrap)
        duration = node.get("duration_s")
        if isinstance(duration, (int, float)):
            ws.write_number(r, 5, float(duration), book.get(dur))
        else:
            write_text(ws, r, 5, NOT_RECORDED, book, wrap)
        rows = total_rows_out(node)
        if rows is None:
            write_text(ws, r, 6, "not counted", book, wrap)
        else:
            ws.write_number(r, 6, rows, book.get(num))
        write_text(ws, r, 7, message, book, wrap)
        r += 1


def _short(value: Any) -> str:
    text = "" if value is None else str(value)
    return (
        text
        if len(text) <= MAX_SETTING_CHARS
        else text[: MAX_SETTING_CHARS - 3] + "..."
    )


def write_workflow_sheet(
    ws: Any, book: FormatBook, workflow: Sequence[Mapping[str, Any]]
) -> None:
    """Sheet ``Workflow``: the steps in run order, then the preparer's notes."""
    _setup(ws, book, WORKFLOW_WIDTHS)
    ws.protect("", {"autofilter": True})
    write_text(ws, 0, 0, "Workflow", book, "rl_title")
    write_text(
        ws,
        1,
        0,
        "Steps that produced the data in this workpaper, in the order they ran. "
        "Notes written by the preparer follow.",
        book,
        "rl_sub",
    )
    for c, head in enumerate(
        ("Step", "Node", "Type", "What it does (settings)", "Takes data from")
    ):
        write_text(ws, 3, c, head, book, "hdr")
    r = 4
    nodes = [n for n in workflow if n.get("kind", "node") == "node"]
    comments = [n for n in workflow if n.get("kind") == "comment"]
    for node in nodes:
        lines = [
            f"{label}: {_short(value)}" for label, value in node.get("settings") or []
        ]
        height = min(300, 15 * max(1, len(lines)))
        ws.set_row(r, height)
        step = node.get("step")
        if isinstance(step, int):
            ws.write_number(r, 0, step, book.get("rl_num"))
        else:
            write_text(ws, r, 0, "", book, "rl_wrap")
        title = str(node.get("title") or friendly_op(node.get("op", "")))
        if node.get("label"):
            title += f" ({node['label']})"
        write_text(ws, r, 1, title, book, "rl_wrap")
        write_text(ws, r, 2, friendly_op(node.get("op", "")), book, "rl_wrap")
        write_text(ws, r, 3, "\n".join(lines), book, "rl_wrap")
        write_text(
            ws,
            r,
            4,
            ", ".join(str(x) for x in node.get("inputs") or []),
            book,
            "rl_wrap",
        )
        r += 1
    if comments:
        r += 1
        _merge(ws, book, r, 0, 4, "Notes in the workflow", "rl_section")
        r += 1
        for note in comments:
            text = str(note.get("comment") or "")
            ws.set_row(
                r, min(300, 15 * max(1, text.count("\n") + 1 + len(text) // 110))
            )
            write_text(ws, r, 0, "Note", book, "rl_label")
            _merge(ws, book, r, 1, 4, text, "rl_wrap")
            r += 1
