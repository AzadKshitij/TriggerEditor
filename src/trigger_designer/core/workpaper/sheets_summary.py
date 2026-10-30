"""The Summary sheet (Qt-free): who, what, how, the numbers, the sign-off.

Two layouts share one writer: the *exceptions* layout (one test: results block
with live formulas tied to the Exceptions sheet, tick-mark legend) and the *run*
layout (a table with one row per audit test of a run). Everything below row 19
is written with a row cursor in ascending order (``constant_memory``).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from trigger_designer.core.excel.cells import (
    FormatBook,
    guard_text,
    needs_quote_prefix,
    quote_sheet,
    write_text,
)
from trigger_designer.core.workpaper.spec import (
    CONCLUSIONS,
    NOT_PROVIDED,
    SourceFile,
    TestInfo,
    WorkpaperSpec,
)

BLUE = "#305496"
LIGHT = "#D9E1F2"
INPUT_FILL = "#FFF2CC"
RED_FILL = "#F8CBAD"
LAST_COL = 5  # A..F

STYLES: dict[str, dict[str, Any]] = {
    "title": {"bold": True, "font_size": 16, "bottom": 1, "valign": "vcenter"},
    "sub": {"italic": True, "font_color": "#595959"},
    "section": {"bold": True, "font_color": "#FFFFFF", "bg_color": BLUE},
    "label": {"bold": True, "bg_color": LIGHT, "valign": "top", "text_wrap": True},
    "wrap": {"text_wrap": True, "valign": "top"},
    "input": {
        "bg_color": INPUT_FILL,
        "locked": False,
        "text_wrap": True,
        "valign": "top",
    },
    "input_date": {
        "bg_color": INPUT_FILL,
        "locked": False,
        "valign": "top",
        "num_format": "yyyy-mm-dd",
        "align": "left",
    },
    "date": {"num_format": "yyyy-mm-dd", "align": "left", "valign": "top"},
    "int": {"num_format": "#,##0", "valign": "top"},
    "input_int": {"num_format": "#,##0", "bg_color": INPUT_FILL, "locked": False},
    "input_num": {"num_format": "#,##0.00", "bg_color": INPUT_FILL, "locked": False},
    "pct": {"num_format": "0.00%", "valign": "top"},
    "good": {"bold": True, "font_color": "#375623", "valign": "top"},
    "bad": {
        "bold": True,
        "font_color": "#C00000",
        "bg_color": RED_FILL,
        "valign": "top",
    },
    "bad_text": {"font_color": "#C00000", "text_wrap": True, "valign": "top"},
    "tick": {"bold": True, "align": "center"},
}


@dataclass
class SummaryInputs:
    spec: WorkpaperSpec
    now: datetime
    test: TestInfo | None = None
    mode: str = "exceptions"  # "exceptions" | "run"
    # exceptions layout
    exceptions_sheet: str = "Exceptions"
    exceptions_total: int = 0
    exceptions_value: float | None = None  # all rows (stats)
    listed: int = 0
    listed_value: float | None = None
    last_row: int = 3
    amount_col_letter: str | None = None
    truncated: bool = False
    limit: int = 0
    pop_rows: int | None = None
    pop_value: float | None = None
    csv_text: str = ""
    decimals: int = 2
    # run layout
    tests: list[TestInfo] = field(default_factory=list)
    # common
    sources: list[SourceFile] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    contents: list[str] = field(default_factory=list)
    prepared_on: date | None = None


class _Writer:
    def __init__(self, ws: Any, book: FormatBook) -> None:
        self.ws, self.book = ws, book
        for name, props in STYLES.items():
            book.define(name, props)

    def fmt(self, name: str, quoted: bool = False) -> Any:
        return self.book.get(name, quoted)

    def merged(
        self, r: int, text: str, style: str, c0: int = 1, c1: int = LAST_COL
    ) -> None:
        """Single-row merge ``c0..c1`` on 0-based row ``r`` holding ``text`` as a string."""
        text, _ = guard_text(text)
        fmt = self.fmt(style, needs_quote_prefix(text))
        self.ws.merge_range(r, c0, r, c1, "", fmt)
        if text:
            self.ws.write_string(r, c0, text, fmt)

    def section(self, r: int, text: str) -> None:
        self.merged(r, text, "section", 0, LAST_COL)

    def text(self, r: int, c: int, text: str, style: str = "wrap") -> None:
        write_text(self.ws, r, c, text, self.book, style)

    def field(
        self,
        r: int,
        label: str,
        value: str,
        *,
        height: float | None = None,
        placeholder_is_empty: str | None = None,
    ) -> None:
        if height:
            self.ws.set_row(r, height)
        self.text(r, 0, label, "label")
        empty = not value.strip() or value == placeholder_is_empty
        self.merged(r, value, "input" if empty else "wrap")

    def blank_input(
        self, r: int, label: str, style: str = "input", height: float | None = None
    ) -> None:
        if height:
            self.ws.set_row(r, height)
        self.text(r, 0, label, "label")
        fmt = self.fmt(style)
        self.ws.merge_range(r, 1, r, LAST_COL, "", fmt)


def _logo(ws: Any, path: str) -> str | None:
    """Insert the logo at F1; returns a note when it could not be added."""
    if not path:
        return None
    try:
        if os.path.splitext(path)[1].lower() not in (".png", ".jpg", ".jpeg"):
            return "Logo not added: only PNG and JPG images are supported."
        from PIL import Image

        with Image.open(path) as image:
            width, height = image.size
        scale = min(36 / height, 200 / width, 1.0)
        ws.insert_image(
            0,
            5,
            path,
            {
                "x_scale": scale,
                "y_scale": scale,
                "x_offset": max(0, int(453 - width * scale - 4)),
                "y_offset": 2,
                "object_position": 3,
            },
        )
    except Exception as exc:  # noqa: BLE001 - a bad logo never blocks the workpaper
        return f"Logo not added: {exc}"
    return None


def _pct(num: float | None, den: float | None) -> float | str:
    try:
        if num is None or den in (None, 0) or isinstance(den, str):
            return "n/a"
        return num / den
    except TypeError, ZeroDivisionError:
        return "n/a"


def write_summary_sheet(
    wb: Any, ws: Any, book: FormatBook, s: SummaryInputs
) -> list[str]:
    """Write the sheet; returns extra notes (for example the logo problem)."""
    spec, test = s.spec, s.test
    w = _Writer(ws, book)
    extra_notes: list[str] = []
    for col, width in zip(range(6), (30, 16, 22, 22, 22, 64), strict=True):
        ws.set_column(col, col, width)
    ws.hide_gridlines(2)
    ws.set_tab_color(BLUE)
    ws.set_landscape()
    ws.fit_to_pages(1, 0)
    ws.set_footer("&L&F - &A&RPage &P of &N")

    # --- title block
    ws.set_row(0, 40)
    w.merged(0, spec.title or "Audit workpaper", "title", 0, LAST_COL)
    version = f" {spec.app_version}" if spec.app_version else ""
    w.merged(
        1,
        f"Audit workpaper generated by Trigger Designer{version} on {s.now:%Y-%m-%d %H:%M}",
        "sub",
        0,
        LAST_COL,
    )
    note = _logo(ws, spec.logo_path)
    if note:
        extra_notes.append(note)

    # --- engagement
    w.section(3, "Engagement")
    test_name = (
        spec.test_name or (test.test_name if test else "") or "Exceptions workpaper"
    )
    w.field(4, "Workpaper reference", spec.workpaper_ref)
    w.field(5, "Client", spec.client)
    w.field(6, "Engagement", spec.engagement)
    w.field(7, "Period", spec.period)
    w.field(8, "Test performed", test_name)
    w.field(9, "Prepared by", spec.preparer)
    w.text(10, 0, "Prepared on", "label")
    prepared = s.prepared_on or s.now.date()
    ws.merge_range(10, 1, 10, LAST_COL, "", w.fmt("date"))
    ws.write_datetime(
        10, 1, datetime.combine(prepared, datetime.min.time()), w.fmt("date")
    )
    w.field(11, "Reviewed by", spec.reviewer)
    w.text(12, 0, "Review date", "label")
    ws.merge_range(12, 1, 12, LAST_COL, "", w.fmt("input_date"))

    # --- objective and procedure
    w.section(14, "Objective and procedure")
    criteria = spec.criteria or (test.criteria if test else "") or NOT_PROVIDED
    w.field(15, "Objective", spec.purpose, height=48)
    w.field(16, "Procedure performed", spec.procedure, height=64)
    w.field(
        17, "Criteria applied", criteria, height=48, placeholder_is_empty=NOT_PROVIDED
    )

    # --- results
    if s.mode == "exceptions":
        cursor = _write_results_exceptions(ws, w, s, test)
    else:
        cursor = _write_results_run(ws, w, s)

    # --- conclusion (fixed rows 28-30 in the exceptions layout)
    r = cursor + 1  # blank row between blocks
    w.section(r, "Conclusion")
    w.text(r + 1, 0, "Conclusion", "label")
    ws.merge_range(r + 1, 1, r + 1, LAST_COL, "", w.fmt("input"))
    ws.data_validation(
        r + 1,
        1,
        r + 1,
        1,
        {
            "validate": "list",
            "source": list(CONCLUSIONS),
            "input_title": "Conclusion",
            "input_message": "Choose the conclusion",
            "error_title": "Conclusion",
            "error_message": "Choose one of the listed conclusions.",
            "error_type": "stop",
        },
    )
    w.blank_input(r + 2, "Auditor notes", "input", height=80)
    r += 4

    # --- tick marks
    if s.mode == "exceptions":
        r = _write_ticks(ws, w, s, r)

    # --- sources
    w.section(r, "Source files")
    for c, head in enumerate(
        ("File", "Sheet", "Rows read", "Size (bytes)", "Modified (UTC)", "SHA-256")
    ):
        w.text(r + 1, c, head, "hdr")
    r += 2
    if not s.sources:
        w.merged(r, "No source files recorded", "wrap", 0, LAST_COL)
        r += 1
    for src in s.sources:
        w.text(r, 0, src.path, "wrap")
        w.text(r, 1, src.sheet or "", "wrap")
        if isinstance(src.rows, int):
            ws.write_number(r, 2, src.rows, w.fmt("int"))
        else:
            w.text(r, 2, "not recorded", "wrap")
        if isinstance(src.size_bytes, int):
            ws.write_number(r, 3, src.size_bytes, w.fmt("int"))
        else:
            w.text(r, 3, "", "wrap")
        w.text(r, 4, src.modified_time or "", "wrap")
        w.text(r, 5, src.sha256 or "file not found or not computed", "wrap")
        r += 1

    # --- notes and contents
    notes = [*s.notes, *extra_notes]
    r += 1
    w.section(r, "Notes and limitations")
    r += 1
    for line in notes or ["None."]:
        w.merged(r, line, "wrap", 0, LAST_COL)
        r += 1
    r += 1
    w.section(r, "Workbook contents")
    r += 1
    for line in s.contents:
        w.merged(r, line, "wrap", 0, LAST_COL)
        r += 1
    ws.protect("", {"autofilter": True})
    return extra_notes


def _write_results_exceptions(
    ws: Any, w: _Writer, s: SummaryInputs, test: TestInfo | None
) -> int:
    """Rows 20-26; returns the 0-based row of the last row written."""
    book = w.book
    w.section(19, "Results")
    for c, head in enumerate(
        (
            "Measure",
            "Rows",
            "Value",
            "% of population rows",
            "% of population value",
            "Basis",
        )
    ):
        w.text(20, c, head, "hdr")
    value_fmt = book.custom(
        "value", {"num_format": _num_format(s.decimals), "valign": "top"}
    )
    input_value = book.custom(
        "input_value",
        {
            "num_format": _num_format(s.decimals),
            "bg_color": INPUT_FILL,
            "locked": False,
        },
    )

    # population (row 22)
    w.text(21, 0, "Population tested", "label")
    pop_rows, pop_value = s.pop_rows, s.pop_value
    basis = "Counted from the Population input"
    if pop_rows is None and test is not None and test.population_rows is not None:
        pop_rows, basis = test.population_rows, "Reported by the test node"
        if pop_value is None:
            pop_value = test.population_value
    elif pop_rows is None:
        basis = "Not provided - enter manually"
    if pop_rows is not None:
        ws.write_number(21, 1, pop_rows, w.fmt("int"))
    else:
        ws.write_blank(21, 1, None, w.fmt("input_int"))
    if pop_value is not None:
        ws.write_number(21, 2, pop_value, value_fmt)
    elif not s.spec.amount_column:
        w.text(21, 2, "n/a", "wrap")
    else:
        ws.write_blank(21, 2, None, input_value)
    w.text(21, 5, basis, "wrap")
    exc = f"{quote_sheet(s.exceptions_sheet)}"
    last = s.last_row

    # exceptions found (row 23)
    listed_value = s.listed_value
    w.text(22, 0, "Exceptions found", "label")
    if s.truncated:
        ws.write_number(22, 1, s.exceptions_total, w.fmt("int"))
        if s.exceptions_value is not None:
            ws.write_number(22, 2, s.exceptions_value, value_fmt)
        else:
            w.text(22, 2, "n/a", "wrap")
        found_rows: float | None = s.exceptions_total
        found_value = s.exceptions_value
    else:
        ws.write_formula(22, 1, "=B24", w.fmt("int"), s.listed)
        if listed_value is not None:
            ws.write_formula(22, 2, "=C24", value_fmt, listed_value)
        else:
            ws.write_formula(22, 2, "=C24", w.fmt("wrap"), "n/a")
        found_rows, found_value = s.listed, listed_value
    ws.write_formula(
        22, 3, '=IFERROR(B23/B22,"n/a")', w.fmt("pct"), _pct(found_rows, pop_rows)
    )
    ws.write_formula(
        22, 4, '=IFERROR(C23/C22,"n/a")', w.fmt("pct"), _pct(found_value, pop_value)
    )
    if s.exceptions_total == 0:
        w.text(22, 5, "No exceptions noted", "good")
    else:
        w.text(22, 5, "Counted from the Exceptions input", "wrap")

    # listed (row 24)
    w.text(23, 0, "Exceptions listed in this workbook", "label")
    ws.write_formula(23, 1, f"=COUNT({exc}!$A$3:$A${last})", w.fmt("int"), s.listed)
    if s.amount_col_letter and listed_value is not None:
        col = s.amount_col_letter
        ws.write_formula(
            23, 2, f"=SUM({exc}!${col}$3:${col}${last})", value_fmt, listed_value
        )
    else:
        w.text(23, 2, "n/a", "wrap")
    if s.truncated:
        w.text(
            23,
            5,
            f"TRUNCATED: first {s.limit:,} of {s.exceptions_total:,} listed",
            "bad",
        )
    else:
        w.text(23, 5, "All exceptions are listed", "wrap")

    # csv + reconciliation (rows 25, 26)
    w.text(24, 0, "Full exception list (CSV)", "label")
    w.merged(24, s.csv_text, "wrap")
    w.text(25, 0, "Reconciliation to test result", "label")
    if test is None or test.exception_rows is None:
        w.merged(25, "No test result supplied", "wrap")
    elif test.exception_rows == s.exceptions_total:
        w.merged(
            25, f"Agrees to the test node ({test.exception_rows:,} exceptions)", "wrap"
        )
    else:
        w.merged(
            25,
            f"DIFFERENCE: the test node reported {test.exception_rows:,} exceptions "
            f"but {s.exceptions_total:,} were received",
            "bad_text",
        )
    return 26


def _write_results_run(ws: Any, w: _Writer, s: SummaryInputs) -> int:
    """Test-results table for a whole run; returns the blank row after it (0-based)."""
    w.section(19, "Test results")
    for c, head in enumerate(
        ("Test", "Status", "Population rows", "Exceptions", "Exception rate", "Result")
    ):
        w.text(20, c, head, "hdr")
    r = 21
    if not s.tests:
        w.merged(r, "No audit tests were recorded in this run.", "wrap", 0, LAST_COL)
        return r + 1
    for t in s.tests:
        bad = t.status in ("fail", "error")
        w.text(r, 0, t.test_name or "Test", "wrap")
        w.text(r, 1, t.status or "", "bad_text" if bad else "wrap")
        for c, val in ((2, t.population_rows), (3, t.exception_rows)):
            if val is None:
                w.text(r, c, "n/a", "wrap")
            else:
                ws.write_number(r, c, val, w.fmt("int"))
        if t.exception_rate is None:
            w.text(r, 4, "n/a", "wrap")
        else:
            ws.write_number(r, 4, t.exception_rate, w.fmt("pct"))
        detail = " - ".join(x for x in (t.criteria, t.message) if x)
        w.text(r, 5, detail, "wrap")
        r += 1
    return r


def _write_ticks(ws: Any, w: _Writer, s: SummaryInputs, r: int) -> int:
    exc = quote_sheet(s.exceptions_sheet)
    last = s.last_row
    w.section(r, "Tick marks")
    w.text(r + 1, 0, "Tick", "hdr")
    w.merged(r + 1, "Meaning", "hdr", 1, 4)
    w.text(r + 1, 5, "Rows marked", "hdr")
    r += 2
    for symbol, meaning in s.spec.tick_marks:
        w.text(r, 0, symbol, "tick")
        w.merged(r, meaning, "wrap", 1, 4)
        ws.write_formula(
            r, 5, f"=COUNTIF({exc}!$B$3:$B${last},A{r + 1})", w.fmt("int"), 0
        )
        r += 1
    return r + 1


def _num_format(decimals: int) -> str:
    digits = max(0, min(6, int(decimals)))
    return "#,##0" + ("." + "0" * digits if digits else "")
