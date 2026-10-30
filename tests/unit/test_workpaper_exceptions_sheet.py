"""The Exceptions sheet: layout, formats, injection, truncation (Qt-free)."""

from __future__ import annotations

import csv
import datetime as dt

import polars as pl
import pytest

from tests.support.workpaper import EXCEPTIONS, FIXED_NOW, load, make_spec
from trigger_designer.core.workpaper import write_workpaper


def _write(tmp_path, frame, **kw):
    spec = make_spec(tmp_path, **kw)
    result = write_workpaper(spec, frame, now=FIXED_NOW)
    return result, load(result.path)


def test_layout_headers_freeze_filter(tmp_path):
    result, wb = _write(tmp_path, EXCEPTIONS)
    ws = wb["Exceptions"]
    assert ws["A1"].value == "Showing all 3 exception rows."
    assert [ws.cell(2, c).value for c in (1, 2, 3)] == [
        "Ref",
        "Tick mark",
        "Auditor comment",
    ]
    assert [ws.cell(2, c).value for c in range(4, 8)] == [
        "Invoice",
        "Vendor",
        "Amount",
        "Note",
    ]
    assert ws.freeze_panes == "B3" and ws.auto_filter.ref == "A2:G5"
    assert [ws.cell(r, 1).value for r in (3, 4, 5)] == [1, 2, 3]
    assert ws["B3"].value is None and ws["C3"].value is None
    assert result.sheets == ["Summary", "Exceptions"] or "Exceptions" in result.sheets


def test_number_and_date_formats(tmp_path):
    frame = pl.DataFrame(
        {
            "invoice_no": [1234567, None],
            "qty": [1234567, 5],
            "price": [1.5, None],
            "d": [dt.date(2026, 1, 2), None],
            "ts": [dt.datetime(2026, 1, 2, 3, 4, 5), None],
            "ok": [True, None],
        }
    )
    _, wb = _write(tmp_path, frame, amount_column="")
    ws = wb["Exceptions"]
    assert ws["D3"].number_format == "0" and ws["E3"].number_format == "#,##0"
    assert ws["F3"].number_format == "#,##0.00"
    assert ws["G3"].number_format == "yyyy-mm-dd" and ws["G3"].value == dt.datetime(
        2026, 1, 2
    )
    assert ws["H3"].number_format == "yyyy-mm-dd hh:mm:ss"
    assert ws["I3"].value is True
    assert ws["D4"].value is None and ws["F4"].value is None and ws["I4"].value is None


def test_amount_column_numbers_from_strings_and_note(tmp_path):
    frame = pl.DataFrame({"Amount": ["1,234.50", "(12.00)", "oops", ""]})
    result, wb = _write(tmp_path, frame)
    ws = wb["Exceptions"]
    assert [ws.cell(r, 4).value for r in (3, 4, 5)] == [1234.5, -12.0, "oops"]
    assert ws["D6"].value is None
    assert any("1 value(s)" in w and "could not be read" in w for w in result.warnings)
    assert wb["Summary"]["C24"].value.startswith("=SUM('Exceptions'!$D$3:$D$6")
    assert load(result.path, data_only=True)["Summary"]["C24"].value == pytest.approx(
        1222.5
    )


def test_tick_validation_covers_every_data_row(tmp_path):
    _, wb = _write(tmp_path, EXCEPTIONS)
    validations = wb["Exceptions"].data_validations.dataValidation
    assert len(validations) == 1
    assert str(validations[0].sqref) == "B3:B5"
    assert validations[0].formula1 == '"✓,X,E,F,N/A"'


def test_zero_exceptions_sheet(tmp_path):
    result, wb = _write(tmp_path, EXCEPTIONS.clear())
    ws = wb["Exceptions"]
    assert (
        ws["A1"].value == "No exceptions noted."
        and ws["A3"].value == "No exceptions noted"
    )
    assert result.exceptions_total == 0 and not result.truncated
    summary = load(result.path, data_only=True)["Summary"]
    assert summary["B23"].value == 0 and summary["F23"].value == "No exceptions noted"


def test_formula_injection_cells_are_text_with_quote_prefix(tmp_path):
    frame = pl.DataFrame(
        {"=evil": ['=HYPERLINK("http://x","y")', "+1+1", "@x", "-5.5", "ok"]},
    )
    _, wb = _write(tmp_path, frame, amount_column="")
    ws = wb["Exceptions"]
    cells = [ws.cell(r, 4) for r in range(3, 8)]
    assert all(c.data_type == "s" for c in cells)
    assert [c.quotePrefix for c in cells] == [True, True, True, False, False]
    assert ws["D2"].data_type == "s" and ws["D2"].quotePrefix is True


def test_control_chars_and_long_strings_are_handled(tmp_path):
    frame = pl.DataFrame({"t": ["a\x01b", "y" * 40_000]})
    result, wb = _write(tmp_path, frame, amount_column="")
    ws = wb["Exceptions"]
    assert ws["D3"].value == "a�b"
    assert len(ws["D4"].value) <= 32_767 and "shortened from 40,000" in ws["D4"].value
    assert result.csv_path is not None
    with open(result.csv_path, encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    assert len(rows[2][1]) == 40_000
    assert any("control characters" in w for w in result.warnings)


def test_timezone_is_stripped_and_noted(tmp_path):
    frame = pl.DataFrame({"ts": [dt.datetime(2026, 1, 1, 12, tzinfo=dt.UTC)]})
    result, wb = _write(tmp_path, frame, amount_column="")
    assert wb["Exceptions"]["D3"].value == dt.datetime(2026, 1, 1, 12)
    assert any("Time zones were removed" in w for w in result.warnings)


def test_unicode_nan_and_large_int(tmp_path):
    frame = pl.DataFrame({"u": ["ünï ✓ 日本"], "f": [float("nan")], "big": [10**16]})
    _, wb = _write(tmp_path, frame, amount_column="")
    ws = wb["Exceptions"]
    assert ws["D3"].value == "ünï ✓ 日本"
    assert ws["E3"].value == "NaN" and ws["F3"].value == str(10**16)


def test_truncation_with_lowered_limit(tmp_path):
    frame = pl.DataFrame(
        {"Amount": [float(i) for i in range(1, 13)], "n": list("abcdefghijkl")}
    )
    result, wb = _write(tmp_path, frame, row_limit=5)
    ws = wb["Exceptions"]
    assert ws["A1"].value.startswith("TRUNCATED - showing the first 5 of 12")
    assert [ws.cell(r, 1).value for r in range(3, 8)] == [1, 2, 3, 4, 5]
    assert ws["A8"].value is None
    assert result.truncated and (
        result.exceptions_total,
        result.exceptions_written,
    ) == (12, 5)
    with open(result.csv_path, encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    assert rows[0][:2] == ["Ref", "Amount"] and [r[0] for r in rows[1:]] == [
        str(i) for i in range(1, 13)
    ]
    summary = wb["Summary"]
    assert "SHA-256" in summary["B25"].value and result.csv_path.endswith(
        "_exceptions_full.csv"
    )
    assert summary["F24"].value == "TRUNCATED: first 5 of 12 listed"
    assert summary["B23"].value == 12 and summary["C23"].value == 78  # static totals
    assert ws.sheet_properties.tabColor.rgb.endswith("C00000")


def test_row_limit_is_clamped_to_excel_maximum(tmp_path):
    result, _ = _write(tmp_path, EXCEPTIONS, row_limit=5_000_000)
    assert any("1,048,574" in w for w in result.warnings)


def test_csv_sidecar_guards_formulas(tmp_path):
    frame = pl.DataFrame({"t": ["=1+1", "-5", "fine"]})
    result, _ = _write(tmp_path, frame, amount_column="", row_limit=1)
    with open(result.csv_path, encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    assert [r[1] for r in rows[1:]] == ["'=1+1", "-5", "fine"]


def test_header_collision_with_fixed_columns(tmp_path):
    frame = pl.DataFrame({"Ref": [1], "Tick mark": [2], "": [3]})
    _, wb = _write(tmp_path, frame, amount_column="")
    assert [wb["Exceptions"].cell(2, c).value for c in (4, 5, 6)] == [
        "Ref (data)",
        "Tick mark (data)",
        "Column 3",
    ]


@pytest.mark.slow
def test_streaming_memory_for_50k_rows(tmp_path):
    import threading
    import time

    import psutil

    proc, peak, stop = psutil.Process(), [0], threading.Event()
    base = proc.memory_info().rss

    def sample():
        while not stop.is_set():
            peak[0] = max(peak[0], proc.memory_info().rss)
            time.sleep(0.02)

    thread = threading.Thread(target=sample)
    thread.start()
    try:
        n = 50_000
        frame = pl.LazyFrame(
            {"Amount": pl.int_range(0, n, eager=True).cast(pl.Float64)}
        ).with_columns(
            *(pl.col("Amount").cast(pl.String).alias(f"s{i}") for i in range(7))
        )
        result = write_workpaper(make_spec(tmp_path, row_limit=n), frame, now=FIXED_NOW)
        assert result.exceptions_written == n
    finally:
        stop.set()
        thread.join()
    assert peak[0] - base < 150 * 1024 * 1024
