"""Text and HTML rendering of a data profile (plan 05). Qt-free.

The dock, the HTML export and the "Full report" button all read a
``DataProfile`` through the helpers here, so the three can never disagree about
how a figure is worded.
"""

from __future__ import annotations

from datetime import datetime
from html import escape

from trigger_designer.core.profile import FLAG_TONE, ColumnProfile, DataProfile

FLAG_LABELS = {
    "all_null": "all null",
    "all_blank": "all blank",
    "constant": "constant",
    "high_cardinality": "almost all unique",
    "mostly_null": "mostly null",
    "mixed_numeric_text": "mixed numbers and text",
    "mixed_date_text": "mixed dates and text",
    "leading_zeros": "leading zeros",
    "trailing_minus": "trailing minus",
    "decimal_comma_suspected": "decimal comma",
    "leading_trailing_whitespace": "stray whitespace",
    "numeric_as_text": "numbers stored as text",
    "date_as_text": "dates stored as text",
    "negative_values": "negative values",
    "outlier_suspected": "possible outlier",
    "nan_values": "NaN values",
    "inf_values": "infinite values",
}


# ---- wording helpers ---------------------------------------------------------
def flag_labels(cp: ColumnProfile) -> list[str]:
    return [FLAG_LABELS.get(flag, flag) for flag in cp.flags]


def flags_text(cp: ColumnProfile) -> str:
    return ", ".join(flag_labels(cp))


def has_warning(cp: ColumnProfile) -> bool:
    return any(FLAG_TONE.get(flag) == "warning" for flag in cp.flags)


def distinct_text(cp: ColumnProfile) -> str:
    if cp.distinct_count is None:
        return ""
    return f"{'~' if cp.distinct_is_approx else ''}{cp.distinct_count:,}"


def suggested_text(cp: ColumnProfile) -> str:
    if not cp.suggested_type or cp.suggested_type == cp.dtype:
        return ""
    if cp.suggested_confidence >= 1.0:
        return cp.suggested_type
    return f"{cp.suggested_type} ({cp.suggested_confidence * 100:.0f}%)"


def _num(value: float | None) -> str:
    if value is None:
        return "-"
    if float(value).is_integer() and abs(value) < 1e15:
        return f"{int(value):,}"
    return f"{value:,.6g}"


def detail_rows(cp: ColumnProfile) -> list[tuple[str, str]]:
    """Ordered ``(label, text)`` pairs describing one column; empty values skipped."""
    rows: list[tuple[str, str]] = [("Type in file", cp.dtype)]
    suggested = suggested_text(cp)
    if suggested:
        rows.append(("Suggested type", suggested))
    rows.append(("Null", f"{cp.null_count:,} ({cp.null_pct:.2f}%)"))
    if cp.blank_count:
        rows.append(("Blank text", f"{cp.blank_count:,}"))
    if cp.whitespace_count:
        rows.append(("Stray whitespace", f"{cp.whitespace_count:,} values"))
    if cp.distinct_count is not None:
        pct = f" ({cp.distinct_pct:.1f}% of non-null)" if cp.distinct_pct else ""
        rows.append(("Distinct", f"{distinct_text(cp)}{pct}"))
    if cp.numeric_basis:
        basis = "parsed from text" if cp.numeric_basis == "parsed_text" else "native"
        rows.append(
            (
                f"Min / max ({basis})",
                f"{_num(cp.min_numeric)} / {_num(cp.max_numeric)}",
            )
        )
        rows.append(
            (
                "Mean / median / std",
                f"{_num(cp.mean)} / {_num(cp.median)} / {_num(cp.std)}",
            )
        )
        if cp.negative_count:
            rows.append(("Negative values", f"{cp.negative_count:,}"))
        if cp.zero_count:
            rows.append(("Zeros", f"{cp.zero_count:,}"))
        if cp.nan_count:
            rows.append(("NaN", f"{cp.nan_count:,}"))
        if cp.inf_count:
            rows.append(("Infinite", f"{cp.inf_count:,}"))
    elif cp.min is not None or cp.max is not None:
        label = (
            "Min / max"
            if cp.suggested_type in ("Date", "Datetime")
            else "Min / max (text order)"
        )
        rows.append((label, f"{cp.min or ''} / {cp.max or ''}"))
    if cp.min_length is not None:
        rows.append(("Length", f"{cp.min_length} to {cp.max_length} characters"))
    if cp.date_like_count:
        rows.append(("Look like dates", f"{cp.date_like_count:,}"))
    return rows


def status_text(profile: DataProfile) -> str:
    """The chip above the table: which rows these figures describe."""
    s = profile.settings
    if not profile.sampled:
        return f"Data: {profile.row_count:,} rows"
    if s.sample_mode == "random":
        return f"Sample: random {profile.row_count:,} rows (seed {s.seed})"
    return f"Sample: first {profile.row_count:,} rows"


def chart_for(cp: ColumnProfile) -> tuple[list[str], list[int], str, tuple[str, str]]:
    """``(labels, values, kind, captions)``; kind is ``hist``, ``freq`` or ``""``."""
    if (
        cp.histogram
        and cp.min_numeric is not None
        and cp.max_numeric is not None
        and cp.min_numeric < cp.max_numeric
    ):
        return (
            [""] * len(cp.histogram),
            list(cp.histogram),
            "hist",
            (_num(cp.min_numeric), _num(cp.max_numeric)),
        )
    if cp.top_values:
        return (
            [text for text, _count in cp.top_values],
            [count for _text, count in cp.top_values],
            "freq",
            ("", ""),
        )
    return [], [], "", ("", "")


# ---- HTML ---------------------------------------------------------------------
_CSS = """
:root{--bg:#1e1f22;--panel:#26282c;--line:#3a3d42;--tx:#e3e5e8;--dim:#9aa0a8;--acc:#4a8fe0;--warn:#e0a030;--chip:#32353b}
@media (prefers-color-scheme:light){:root{--bg:#f4f5f7;--panel:#fff;--line:#d5d8dd;--tx:#1d2025;--dim:#656c76;--acc:#1a70b1;--warn:#b26a00;--chip:#eceef1}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--tx);font:13px/1.45 "Segoe UI",system-ui,sans-serif;padding:16px;max-width:1100px;margin-inline:auto}
h1{font-size:20px;margin:4px 0}h2{font-size:15px;margin:28px 0 8px}
.sub{color:var(--dim);margin:0 0 8px}
table{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line)}
th{text-align:left;font-weight:600;color:var(--dim);padding:6px 8px;border-bottom:1px solid var(--line);font-size:12px}
td{padding:4px 8px;border-bottom:1px solid var(--line);vertical-align:middle}
tr:last-child td{border-bottom:0}
td.n a{color:var(--tx);font-weight:600;text-decoration:none}td.n a:hover{text-decoration:underline}
.r{text-align:right;font-variant-numeric:tabular-nums}
.nb{display:inline-block;width:60px;height:8px;background:var(--line);border-radius:2px;vertical-align:middle;overflow:hidden}
.nbf{display:block;height:100%;background:var(--warn)}
.chip{display:inline-block;background:var(--chip);border:1px solid var(--line);border-radius:10px;padding:0 8px;margin:1px 4px 1px 0;font-size:11px;color:var(--dim)}
.chip.warn{color:var(--warn);border-color:var(--warn)}
em{color:var(--dim);font-style:normal}.dim{color:var(--dim)}.ws{color:var(--warn)}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:10px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:4px;padding:10px 12px}
.card h3{margin:0 0 4px;font-size:14px}.card h3 small{color:var(--dim);font-weight:400;margin-left:6px}
dl{display:grid;grid-template-columns:auto 1fr;gap:2px 12px;margin:8px 0}dt{color:var(--dim)}dd{margin:0}
.ctitle{color:var(--dim);font-size:11px;margin-top:8px}
.chart{display:flex;align-items:flex-end;gap:2px;height:70px;margin-top:4px}
.bar{flex:1;background:var(--acc);min-height:2px;border-radius:1px 1px 0 0}
.cap{display:flex;justify-content:space-between;color:var(--dim);font-size:11px}
.frow{display:grid;grid-template-columns:minmax(80px,1fr) 1.2fr auto;gap:8px;align-items:center;margin-top:3px}
.fv{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ftrack{height:8px;background:var(--line);border-radius:2px;overflow:hidden}.fbar{display:block;height:100%;background:var(--acc)}
.fn{font-variant-numeric:tabular-nums;text-align:right}
@media(max-width:640px){.frow{grid-template-columns:1fr}table{display:block;overflow-x:auto}}
"""


def _visible_spaces(text: str | None) -> str:
    """Escape ``text`` and show leading/trailing spaces as amber dots."""
    if text is None:
        return ""
    value = str(text)
    lead = len(value) - len(value.lstrip(" "))
    trail = len(value) - len(value.rstrip(" "))
    core = value.strip(" ")
    return (
        (f'<span class="ws">{"·" * lead}</span>' if lead else "")
        + escape(core)
        + (f'<span class="ws">{"·" * trail}</span>' if trail else "")
    )


def _flag_chips(cp: ColumnProfile) -> str:
    return "".join(
        f'<span class="chip{" warn" if FLAG_TONE.get(flag) == "warning" else ""}">'
        f"{escape(FLAG_LABELS.get(flag, flag))}</span>"
        for flag in cp.flags
    )


def _chart_html(cp: ColumnProfile, total: int) -> str:
    labels, values, kind, captions = chart_for(cp)
    if kind == "hist":
        biggest = max(values) or 1
        bars = "".join(
            f'<div class="bar" style="height:{max(2, round(v / biggest * 100))}%"'
            f' title="{v:,}"></div>'
            for v in values
        )
        return (
            '<div class="ctitle">Distribution</div>'
            f'<div class="chart">{bars}</div>'
            f'<div class="cap"><span>{escape(captions[0])}</span>'
            f"<span>{escape(captions[1])}</span></div>"
        )
    if kind == "freq":
        biggest = max(values) or 1
        rows = "".join(
            f'<div class="frow"><span class="fv">{_visible_spaces(label) or "(empty)"}</span>'
            f'<span class="ftrack"><span class="fbar" style="width:{round(v / biggest * 100)}%">'
            f'</span></span><span class="fn">{v:,} <em>{v * 100 / max(total, 1):.1f}%</em>'
            "</span></div>"
            for label, v in zip(labels, values)
        )
        return f'<div class="ctitle">Most frequent values</div>{rows}'
    return ""


def _card_html(cp: ColumnProfile, total: int) -> str:
    rows = "".join(
        f"<dt>{escape(label)}</dt><dd>{_visible_spaces(text)}</dd>"
        for label, text in detail_rows(cp)
    )
    return (
        f'<div class="card" id="col-{cp.position}">'
        f"<h3>{_visible_spaces(cp.name)} <small>{escape(cp.dtype)}</small></h3>"
        f'<div class="chips">{_flag_chips(cp)}</div>'
        f"<dl>{rows}</dl>{_chart_html(cp, total)}</div>"
    )


def _row_html(cp: ColumnProfile) -> str:
    suggested = suggested_text(cp)
    return (
        f'<tr><td class="n"><a href="#col-{cp.position}">{_visible_spaces(cp.name)}</a></td>'
        f"<td>{escape(cp.dtype)}</td>"
        f'<td><span class="nb"><span class="nbf" style="width:{min(100.0, cp.null_pct):.1f}%">'
        f"</span></span> {cp.null_pct:.1f}%</td>"
        f'<td class="r">{escape(distinct_text(cp))}</td>'
        f"<td>{escape(suggested) if suggested else '<span class=dim>same</span>'}</td>"
        f"<td>{_flag_chips(cp)}</td></tr>"
    )


def profile_to_html(profile: DataProfile, title: str = "Data profile") -> str:
    """A self-contained HTML report: one summary table, then a card per column.

    No scripts, no external files or fonts, so the page opens offline and can be
    attached to a workpaper as it is.
    """
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    chips = (
        f'<span class="chip">{escape(status_text(profile))}</span>'
        f'<span class="chip">{profile.column_count:,} columns</span>'
        f'<span class="chip">Generated {stamp}</span>'
    )
    rows = "".join(_row_html(cp) for cp in profile.columns)
    cards = "".join(_card_html(cp, profile.row_count) for cp in profile.columns)
    body = (
        f"<h1>{escape(title)}</h1>"
        f'<p class="sub">{chips}</p>'
        "<table><thead><tr><th>Column</th><th>Type</th><th>Null %</th>"
        '<th class="r">Distinct</th><th>Suggested</th><th>Flags</th></tr></thead>'
        f"<tbody>{rows}</tbody></table>"
        f'<h2>Column details</h2><div class="cards">{cards}</div>'
        if profile.columns
        else f"<h1>{escape(title)}</h1><p class='sub'>No columns.</p>"
    )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{escape(title)}</title><style>{_CSS}</style></head>"
        f"<body>{body}</body></html>"
    )
