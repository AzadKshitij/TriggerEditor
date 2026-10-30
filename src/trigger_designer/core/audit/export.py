"""Export a run record as JSON or a self-contained HTML report (plan 02 3.16).

Qt-free. The JSON export is a byte copy, so the record hash still verifies on
the copy. The HTML page needs no JavaScript and no network: every dynamic
string goes through ``html.escape``; the original record is embedded as an
``application/json`` script block (with ``</`` neutralised) so a tool can
re-verify it.
"""

from __future__ import annotations

import html
import os
import shutil
from pathlib import Path
from typing import Any

import orjson

from trigger_designer.core.audit.view import (
    format_duration,
    format_local_time,
    node_table_rows,
    run_summary_rows,
)

_CSS = """
:root{--bg:#ffffff;--fg:#1c2330;--muted:#5b6678;--line:#d6dce6;--panel:#f5f7fa;
--ok:#1b7f3b;--bad:#b3261e;--warn:#9a6700;--code:#eef1f6}
@media (prefers-color-scheme: dark){:root{--bg:#161b24;--fg:#e4e9f2;--muted:#9aa6bb;
--line:#2c3547;--panel:#1d2430;--ok:#5fcf80;--bad:#ff8a80;--warn:#e3b341;--code:#222b3a}}
body{margin:0;padding:24px;background:var(--bg);color:var(--fg);
font:14px/1.45 "Segoe UI Variable Text","Segoe UI",system-ui,sans-serif}
h1{font-size:20px;margin:0 0 4px}h2{font-size:15px;margin:24px 0 8px}
.muted{color:var(--muted)}.box{background:var(--panel);border:1px solid var(--line);
border-radius:6px;padding:12px 14px}
table{border-collapse:collapse;width:100%;margin:4px 0}
th,td{border-bottom:1px solid var(--line);padding:4px 8px;text-align:left;
vertical-align:top;font-size:13px}th{color:var(--muted);font-weight:600}
td.num{text-align:right;font-variant-numeric:tabular-nums}
.ok{color:var(--ok)}.failed,.bad{color:var(--bad)}.skipped,.cancelled,.warn{color:var(--warn)}
code,pre{font-family:"Cascadia Mono",Consolas,monospace;font-size:12px}
pre{background:var(--code);padding:10px;border-radius:6px;overflow:auto;max-height:420px}
details{margin:4px 0}summary{cursor:pointer}
.hash{font-family:"Cascadia Mono",Consolas,monospace;font-size:12px;word-break:break-all}
"""


def _e(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _status(value: Any) -> str:
    return f'<span class="{_e(value)}">{_e(value)}</span>'


def _kv_table(rows: list[tuple[str, str]]) -> str:
    body = "".join(f"<tr><th>{_e(k)}</th><td>{_e(v)}</td></tr>" for k, v in rows)
    return f"<table>{body}</table>"


def _files_table(items: list[dict]) -> str:
    if not items:
        return '<p class="muted">None.</p>'
    head = (
        "<tr><th>Path</th><th>Sheet</th><th>Size</th><th>Rows</th>"
        "<th>SHA-256</th><th>Hash status</th><th>Note</th></tr>"
    )
    rows = []
    for fp in items:
        rows.append(
            "<tr>"
            f"<td>{_e(fp.get('path'))}</td><td>{_e(fp.get('sheet') or '')}</td>"
            f'<td class="num">{_e(fp.get("size_bytes") if fp.get("size_bytes") is not None else "-")}</td>'
            f'<td class="num">{_e(fp.get("row_count") if fp.get("row_count") is not None else "-")}</td>'
            f'<td class="hash">{_e(fp.get("sha256") or "-")}</td>'
            f"<td>{_e(fp.get('sha256_status'))}</td><td>{_e(fp.get('error') or '')}</td>"
            "</tr>"
        )
    return f"<table>{head}{''.join(rows)}</table>"


def _nodes_table(record: dict) -> str:
    head = (
        "<tr><th>#</th><th>Node</th><th>Operation</th><th>Status</th>"
        "<th>Rows in</th><th>Rows out</th><th>Time</th><th>Problem</th></tr>"
    )
    rows = []
    for index, row in enumerate(node_table_rows(record), start=1):
        error = row["error"]
        rows.append(
            "<tr>"
            f'<td class="num">{index}</td><td>{_e(row["node"])}</td><td>{_e(row["op"])}</td>'
            f'<td>{_status(row["status"])}</td><td class="num">{_e(row["rows_in"])}</td>'
            f'<td class="num">{_e(row["rows_out"])}</td><td>{_e(row["duration"])}</td>'
            f"<td>{_e(error)}</td></tr>"
        )
    return f"<table>{head}{''.join(rows)}</table>"


def _errors(record: dict) -> str:
    blocks = []
    for node in record.get("nodes") or []:
        error = node.get("error")
        if not isinstance(error, dict):
            continue
        blocks.append(
            f'<div class="box"><strong>{_e(node.get("title"))}</strong> '
            f"<code>{_e(error.get('code'))}</code> - {_e(error.get('title'))}"
            f"<p>{_e(error.get('detail'))}</p>"
            f'<p class="muted">{_e(error.get("hint"))}</p>'
            f"<details><summary>Technical details</summary>"
            f"<pre>{_e(error.get('technical'))}</pre></details></div>"
        )
    return "".join(blocks) or '<p class="muted">No errors.</p>'


def _settings(record: dict) -> str:
    parts = []
    for node in record.get("nodes") or []:
        text = orjson.dumps(
            node.get("settings") or {},
            option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS,
        ).decode()
        seed = node.get("seed")
        extra = f" (seed {_e(seed)})" if seed is not None else ""
        parts.append(
            f"<details><summary>{_e(node.get('title'))}{extra}</summary>"
            f"<pre>{_e(text)}</pre></details>"
        )
    return "".join(parts)


def _integrity(record: dict, verify: Any) -> str:
    lines = [
        f'<div>Record hash: <span class="hash">{_e(record.get("record_hash"))}</span></div>',
        f'<div>Previous record hash: <span class="hash">{_e(record.get("prev_record_hash"))}</span></div>',
        f"<div>Hash algorithm: {_e(record.get('hash_algo'))}</div>",
    ]
    if verify is not None:
        ok = bool(getattr(verify, "ok", False))
        verdict = (
            '<span class="ok">verified</span>'
            if ok
            else '<span class="bad">verification failed</span>'
        )
        lines.append(f"<div>Chain check: {verdict}</div>")
        for problem in getattr(verify, "problems", []) or []:
            lines.append(
                f'<div class="bad">{_e(getattr(problem, "kind", ""))}: '
                f"{_e(getattr(problem, 'message', ''))}</div>"
            )
        head = getattr(verify, "head_hash", None)
        if head:
            lines.append(f'<div>Chain head: <span class="hash">{_e(head)}</span></div>')
    return f'<div class="box">{"".join(lines)}</div>'


def _embedded(record: dict) -> str:
    raw = orjson.dumps(record, option=orjson.OPT_SORT_KEYS).decode()
    # No tag or comment can start inside the block: "<" becomes a JSON escape.
    raw = raw.replace("<", "\\u003c")
    return f'<script type="application/json" id="run-record">{raw}</script>'


def render_html(record: dict, verify: Any = None) -> str:
    """The whole report as one HTML string."""
    title = f"Run {record.get('seq', '')} - {record.get('status', '')}"
    code = record.get("generated_code")
    code_block = (
        f"<details><summary>Generated code</summary><pre>{_e(code)}</pre></details>"
        if code
        else '<p class="muted">Generated code was not embedded in this record.</p>'
    )
    warnings = record.get("warnings") or []
    warning_html = (
        "<ul>" + "".join(f"<li>{_e(w)}</li>" for w in warnings) + "</ul>"
        if warnings
        else '<p class="muted">None.</p>'
    )
    return (
        "<!doctype html>\n"
        '<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{_e(title)}</title><style>{_CSS}</style></head><body>"
        f"<h1>Run record {_e(record.get('seq', ''))}: {_status(record.get('status'))}</h1>"
        f'<div class="muted">{_e(format_local_time(record.get("started_at")))} - '
        f"{_e(format_local_time(record.get('finished_at')))} "
        f"({_e(format_duration(record.get('duration_s')))})</div>"
        "<h2>Summary</h2>"
        f"{_kv_table(run_summary_rows(record))}"
        "<h2>Integrity</h2>"
        f"{_integrity(record, verify)}"
        "<h2>Inputs</h2>"
        f"{_files_table(record.get('inputs') or [])}"
        "<h2>Outputs</h2>"
        f"{_files_table(record.get('outputs') or [])}"
        "<h2>Steps</h2>"
        f"{_nodes_table(record)}"
        "<h2>Errors</h2>"
        f"{_errors(record)}"
        "<h2>Warnings</h2>"
        f"{warning_html}"
        "<h2>Settings</h2>"
        f"{_settings(record)}"
        "<h2>Code</h2>"
        f"{code_block}"
        f"{_embedded(record)}"
        "</body></html>\n"
    )


def export_json(source: str | os.PathLike, destination: str | os.PathLike) -> str:
    """Byte copy of a record file; the copy verifies like the original."""
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    try:
        os.chmod(target, 0o644)  # a copy of a read-only record is the user's file
    except OSError:
        pass
    return str(target)
