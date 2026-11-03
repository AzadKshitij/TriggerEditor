"""Sheet names, headers, injection predicates, amount parsing (Qt-free)."""

from __future__ import annotations

import polars as pl
import pytest

from trigger_designer.core.workpaper.sanitize import (
    MAX_LISTED,
    column_plan,
    danger_expr,
    guard_text,
    needs_quote_prefix,
    quote_sheet,
    safe_sheet_name,
    unique_headers,
)
from trigger_designer.core.workpaper.stream import amount_expr


def test_safe_sheet_name_truncates_and_strips_illegal_chars():
    name = safe_sheet_name(
        "[Bad]: name/with*many?illegal\\chars and then some more text"
    )
    assert len(name) <= 31 and not any(c in name for c in "[]:*?/\\")
    assert safe_sheet_name("'quoted'") == "quoted"
    assert safe_sheet_name("   ") == "Sheet"
    assert safe_sheet_name("", default="Exceptions") == "Exceptions"


def test_safe_sheet_name_is_unique_case_insensitive():
    used = ["exceptions"]
    first = safe_sheet_name("Exceptions", used)
    assert first == "Exceptions (2)"
    assert safe_sheet_name("x" * 40, ["x" * 31]).endswith(" (2)")
    assert len(safe_sheet_name("x" * 40, ["x" * 31])) <= 31


def test_safe_sheet_name_avoids_reserved_names():
    assert (
        safe_sheet_name("summary", ["summary", "run log", "workflow"]) == "summary (2)"
    )


def test_quote_sheet_doubles_apostrophes():
    assert quote_sheet("It's") == "'It''s'"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("=1+1", True),
        ("@SUM(A1)", True),
        ("+cmd|x", True),
        ("-cmd", True),
        ("\tx", True),
        ("\rx", True),
        ("-5.2", False),
        ("+1,000", False),
        ("- 3", False),
        ("ok", False),
        ("", False),
        ("a=b", False),
    ],
)
def test_needs_quote_prefix_table(text, expected):
    assert needs_quote_prefix(text) is expected


def test_polars_and_python_danger_predicates_agree():
    values = [
        "=1+1",
        "@SUM(A1)",
        "+cmd|x",
        "-cmd",
        "\tx",
        "\rx",
        "-5.2",
        "+1,000",
        "- 3",
        "ok",
        "",
        "a=b",
    ]
    got = pl.DataFrame({"v": values}).select(danger_expr(pl.col("v")))["v"].to_list()
    assert got == [needs_quote_prefix(v) for v in values]
    assert pl.DataFrame({"v": [None]}, schema={"v": pl.String}).select(
        danger_expr(pl.col("v"))
    )["v"].to_list() == [False]


def test_guard_text_replaces_control_chars_and_shortens():
    text, flags = guard_text("a\x01b")
    assert text == "a�b" and flags == 1
    long_text, flags = guard_text("x" * 40_000)
    assert (
        len(long_text) <= 32_767 and "shortened from 40,000" in long_text and flags == 2
    )
    assert guard_text("plain\tline\n")[1] == 0


def test_unique_headers_rules():
    assert unique_headers(["", "Ref", "ref", "A"]) == [
        "Column 1",
        "Ref (data)",
        "ref (data)",
        "A",
    ]


def test_integer_identifier_columns_use_plain_format():
    plans = column_plan({"invoice_no": pl.Int64, "qty": pl.Int64, "price": pl.Float64})
    assert [p.fmt_key for p in plans] == ["id", "int", "float"]


def test_duration_header_and_tz_flag():
    plans = column_plan(
        {"d": pl.Duration("us"), "t": pl.Datetime("us", "UTC"), "n": pl.Datetime("us")}
    )
    assert plans[0].header == "d (seconds)" and plans[0].fmt_key == "duration"
    assert [p.tz_aware for p in plans] == [False, True, False]


def test_amount_expr_parses_accounting_strings():
    frame = pl.DataFrame({"a": ["1,234.50", "(12.00)", " 7 ", "x", ""]})
    got = frame.select(amount_expr("a", pl.String).alias("v"))["v"].to_list()
    assert got == [1234.5, -12.0, 7.0, None, None]


def test_amount_expr_numeric_and_unusable():
    assert pl.DataFrame({"a": [1, 2]}).select(amount_expr("a", pl.Int64))[
        "a"
    ].to_list() == [1.0, 2.0]
    assert amount_expr("a", pl.Date) is None


def test_row_limit_constant():
    assert MAX_LISTED == 1_048_574
