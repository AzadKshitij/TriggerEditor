"""The Exceptions sheet: streamed rows, tick marks, comments (Qt-free).

Layout: row 1 banner, row 2 headers (``Ref``, ``Tick mark``, ``Auditor comment``,
then the data columns), data from row 3. Rows are written in ascending order
(``constant_memory`` workbooks drop a write to an earlier row).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from trigger_designer.core.excel import engine
from trigger_designer.core.excel.cells import (
    ColumnPlan,
    FormatBook,
    column_values,
    write_text,
    write_value,
)
from trigger_designer.core.excel.spool import Spooled
from trigger_designer.core.workpaper.spec import WorkpaperSpec
from trigger_designer.core.workpaper.stream import ExceptionStats, amount_expr

DATA_FIRST_COL = 3  # A Ref, B Tick mark, C Auditor comment
TAB_RED = "#C00000"
BANNER_RED = {"bold": True, "font_color": "#C00000", "bg_color": "#F8CBAD"}


@dataclass
class ExceptionsLayout:
    last_row: int  # 1-based Excel row of the last data row (min 3)
    written: int
    amount_col_letter: str | None
    value_listed: float | None
    notes: list[str] = field(default_factory=list)


def amount_format(decimals: int) -> dict[str, Any]:
    digits = max(0, min(6, int(decimals)))
    return {"num_format": "#,##0" + ("." + "0" * digits if digits else "")}


def write_exceptions_sheet(
    wb: Any,
    ws: Any,
    book: FormatBook,
    spec: WorkpaperSpec,
    stats: ExceptionStats,
    spooled: Spooled,
    plans: list[ColumnPlan],
    *,
    limit: int,
    csv_name: str | None,
) -> ExceptionsLayout:
    total = stats.total
    truncated = total > limit
    notes: list[str] = []
    counters: dict[str, int] = {}
    amount_idx = next((i for i, p in enumerate(plans) if p.is_amount), None)
    if amount_idx is not None and not stats.amount_usable:
        amount_idx = None

    # --- banner (row 1) and headers (row 2)
    if truncated:
        banner = (
            f"TRUNCATED - showing the first {limit:,} of {total:,} exception rows. "
            f"The complete list is in {csv_name}."
        )
        fmt = book.custom("banner_bad", BANNER_RED)
        ws.write_string(0, 0, banner, fmt)
        for c in range(1, DATA_FIRST_COL + 1):
            ws.write_blank(0, c, None, fmt)
        ws.set_tab_color(TAB_RED)
    elif total == 0:
        ws.write_string(
            0, 0, "No exceptions noted.", book.custom("banner_ok", {"bold": True})
        )
    else:
        ws.write_string(
            0,
            0,
            f"Showing all {total:,} exception rows.",
            book.custom("banner_ok", {"bold": True}),
        )
    for c, text in enumerate(("Ref", "Tick mark", "Auditor comment")):
        write_text(ws, 1, c, text, book, "hdr")
    for c, plan in enumerate(plans):
        write_text(ws, 1, DATA_FIRST_COL + c, plan.header, book, "hdr")

    # --- data
    widths = [min(60, max(10, len(p.header) + 2)) for p in plans]
    amount_fmt = book.custom("amount", amount_format(spec.value_decimals))
    ref_fmt = book.get("id")
    amount_sum = 0.0
    written = 0
    row = 2
    for index, batch in enumerate(spooled.batches()):
        if written >= limit:
            break
        if written + batch.height > limit:
            batch = batch.head(limit - written)
        values = [column_values(batch[p.name], p) for p in plans]
        parsed: list[float | None] | None = None
        if amount_idx is not None:
            name = plans[amount_idx].name
            expr = amount_expr(name, stats.schema[name])
            parsed = (
                batch.select(expr.alias("__a"))["__a"].to_list()
                if expr is not None
                else None
            )
        for i in range(batch.height):
            ws.write_number(row, 0, written + 1, ref_fmt)
            for c, plan in enumerate(plans):
                col = DATA_FIRST_COL + c
                value = values[c][i]
                if parsed is not None and c == amount_idx:
                    number = parsed[i]
                    if number is not None:
                        amount_sum += number
                        ws.write_number(row, col, number, amount_fmt)
                    elif value is None or (
                        isinstance(value, str) and not value.strip()
                    ):
                        ws.write_blank(row, col, None, book.get("text"))
                    else:
                        write_value(ws, row, col, value, "str", book, "text", counters)
                    continue
                write_value(
                    ws, row, col, value, plan.kind, book, plan.fmt_key, counters
                )
            row += 1
            written += 1
        if index == 0:
            for c, plan in enumerate(plans):
                if plan.kind == "str":
                    longest = max((len(v) for v in values[c] if v), default=0)
                    widths[c] = min(60, max(widths[c], longest + 2))

    if total == 0:
        ws.write_string(
            2, 0, "No exceptions noted", book.custom("italic", {"italic": True})
        )
        row = 3
    last_row = max(3, 2 + written)

    # --- notes about what was changed on the way into Excel
    tz_cols = [p.name for p in plans if p.tz_aware]
    if tz_cols:
        notes.append(
            "Time zones were removed (the local clock time is kept) in: "
            + ", ".join(tz_cols)
            + "."
        )
    if counters.get("control"):
        notes.append(
            f"{counters['control']:,} text cell(s) contained control characters, "
            "replaced by the Unicode replacement character."
        )
    if counters.get("shortened"):
        notes.append(
            f"{counters['shortened']:,} text cell(s) were longer than Excel allows and were "
            f"shortened; the full text is in {csv_name}."
        )
    if amount_idx is None and spec.amount_column:
        notes.append(
            f"The amount column '{spec.amount_column}' is not available or not numeric, "
            "so no value statistics are shown."
        )
    elif amount_idx is not None:
        notes.append("Values are summed as floating point numbers.")
        if stats.unparseable:
            notes.append(
                f"{stats.unparseable:,} value(s) in '{spec.amount_column}' could not be read as "
                "a number; they are listed as text and not summed."
            )

    # --- structure: widths, validation, filter, panes, print
    ws.set_column(0, 0, 8)
    ws.set_column(1, 1, 11)
    ws.set_column(2, 2, 40)
    for c, width in enumerate(widths):
        ws.set_column(DATA_FIRST_COL + c, DATA_FIRST_COL + c, width)
    symbols = [sym for sym, _meaning in spec.tick_marks]
    if symbols:
        ws.data_validation(
            2,
            1,
            last_row - 1,
            1,
            {
                "validate": "list",
                "source": symbols,
                "ignore_blank": True,
                "input_title": "Tick mark",
                "input_message": "Choose a tick mark",
            },
        )
    ws.freeze_panes(2, 1)
    ws.autofilter(1, 0, last_row - 1, DATA_FIRST_COL + len(plans) - 1)
    ws.set_landscape()
    ws.fit_to_pages(1, 0)
    ws.repeat_rows(1)
    ws.set_footer("&L&F - &A&RPage &P of &N")
    letter = (
        engine.col_name(DATA_FIRST_COL + amount_idx) if amount_idx is not None else None
    )
    return ExceptionsLayout(
        last_row=last_row,
        written=written,
        amount_col_letter=letter,
        value_listed=amount_sum if amount_idx is not None else None,
        notes=notes,
    )
