"""Qt-free audit building blocks: errors, params, expressions, summary frame."""

from __future__ import annotations

import datetime as dt
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import polars as pl
import pytest

from trigger_designer.core.audit.common import (
    BASE_SUMMARY,
    AuditConfigError,
    AuditResult,
    ParamsBase,
    amount_expr,
    check_date_format,
    check_range,
    check_reserved,
    date_expr,
    join_and,
    key_expr,
    need,
    need_many,
    params_schema,
    parse_number_list,
    parse_size_list,
    summary_frame,
    unreadable,
    warn_unreadable,
)
from trigger_designer.core.audit.test_summary import TestSummary

SRC = Path(__file__).resolve().parents[2] / "src"
AUDIT_DIR = SRC / "trigger_designer" / "core" / "audit"


def test_core_audit_imports_no_qt() -> None:
    modules = sorted(
        f"trigger_designer.core.audit.{p.stem}"
        for p in AUDIT_DIR.glob("*.py")
        if p.stem != "__init__"
    )
    assert "trigger_designer.core.audit.common" in modules
    code = (
        "import importlib, sys\n"
        f"for name in {modules!r}:\n"
        "    importlib.import_module(name)\n"
        "bad = [m for m in sys.modules\n"
        "       if m.split('.')[0] in ('qtpy', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6')\n"
        "       or m.startswith('trigger_designer.qt')]\n"
        "assert not bad, bad\n"
    )
    done = subprocess.run(
        [sys.executable, "-I", "-c", code],
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(SRC), "SYSTEMROOT": "C:\\Windows"},
        check=False,
    )
    assert done.returncode == 0, done.stderr


def test_audit_package_init_imports_nothing_eagerly() -> None:
    """Plan 02 owns the package init: lazy re-exports only (no eager import).

    Generated code may import one submodule, so the init may only use
    ``importlib`` (inside ``__getattr__``) and ``TYPE_CHECKING``-guarded imports.
    """
    import ast

    tree = ast.parse((AUDIT_DIR / "__init__.py").read_text(encoding="utf-8"))
    allowed = {"__future__", "importlib", "typing"}
    for node in tree.body:
        if isinstance(node, ast.Import):
            assert {a.name for a in node.names} <= allowed
        elif isinstance(node, ast.ImportFrom):
            assert node.module in allowed


def test_amount_expr_reads_accounting_text() -> None:
    frame = pl.DataFrame(
        {"a": ["1,234.50", " (500) ", "$5", "\u20ac7", "abc", None, "-3"]}
    )
    out = frame.select(amount_expr("a", pl.String).alias("v"))["v"].to_list()
    assert out == [1234.5, -500.0, 5.0, 7.0, None, None, -3.0]


def test_amount_expr_reads_decimal_comma_and_keeps_us_forms() -> None:
    cases = {
        "1.234,50": 1234.5,
        "1 234,50": 1234.5,
        "1'234,50": 1234.5,
        "1234,5": 1234.5,
        "€1.234.567,89": 1234567.89,
        "(1.234,50)": -1234.5,
        "-0,5": -0.5,
        "1,234.50": 1234.5,
        "(1,234.50)": -1234.5,
        "$5": 5.0,
        "-1,234": -1234.0,
        "1,234,567": 1234567.0,
        "12.5": 12.5,
        # unreadable rather than silently wrong
        "1.234.567": None,
        "1,2,3": None,
        "1.2,3.4": None,
        "1.23,4,5": None,
    }
    frame = pl.DataFrame({"a": list(cases)})
    out = frame.select(amount_expr("a", pl.String).alias("v"))["v"].to_list()
    assert out == list(cases.values())


def test_amount_expr_passes_numbers_through() -> None:
    frame = pl.DataFrame({"a": [1, 2, None]})
    out = frame.select(amount_expr("a", pl.Int64).alias("v"))
    assert out.schema["v"] == pl.Float64
    assert out["v"].to_list() == [1.0, 2.0, None]


def test_date_expr_text_formats_and_time_suffix() -> None:
    frame = pl.DataFrame(
        {"iso": ["2024-03-02", "2024-03-02 14:05:00", " 2024-03-04 ", "junk", None]}
    )
    out = frame.select(date_expr("iso", pl.String, "%Y-%m-%d").alias("d"))["d"]
    assert out.to_list() == [
        dt.date(2024, 3, 2),
        dt.date(2024, 3, 2),
        dt.date(2024, 3, 4),
        None,
        None,
    ]
    dmy = pl.DataFrame({"d": ["03/04/2024"]})
    got = dmy.select(date_expr("d", pl.String, "%d/%m/%Y").alias("d"))["d"]
    assert got.to_list() == [dt.date(2024, 4, 3)]


def test_date_expr_date_and_datetime_inputs() -> None:
    dates = pl.DataFrame({"d": [dt.date(2024, 1, 5)]})
    assert dates.select(date_expr("d", pl.Date, "%Y-%m-%d"))["d"].to_list() == [
        dt.date(2024, 1, 5)
    ]
    utc = pl.DataFrame(
        {"t": [dt.datetime(2024, 3, 2, 23, 30)]},
        schema={"t": pl.Datetime("us", "UTC")},
    ).with_columns(pl.col("t").dt.convert_time_zone("Asia/Kolkata"))
    dtype = utc.schema["t"]
    # 23:30 UTC is 05:00 the next day in India: the calendar date is local.
    assert utc.select(date_expr("t", dtype, "%Y-%m-%d"))["t"].to_list() == [
        dt.date(2024, 3, 3)
    ]


def test_key_expr_flags() -> None:
    frame = pl.DataFrame({"k": [" Ab ", "ab", None], "n": [1, 2, 3]})
    both = frame.select(key_expr("k", pl.String, True, True).alias("k"))["k"]
    assert both.to_list() == ["ab", "ab", None]
    raw = frame.select(key_expr("k", pl.String, False, False).alias("k"))["k"]
    assert raw.to_list() == [" Ab ", "ab", None]
    assert frame.select(key_expr("n", pl.Int64, False, False))["n"].to_list() == [
        "1",
        "2",
        "3",
    ]


def test_unreadable_marks_present_but_unparsed_cells() -> None:
    frame = pl.DataFrame({"a": ["1", "x", None]})
    parsed = amount_expr("a", pl.String)
    assert frame.select(unreadable("a", parsed).alias("u"))["u"].to_list() == [
        False,
        True,
        False,
    ]


def test_parse_lists() -> None:
    assert parse_number_list("1000, 10000") == [1000.0, 10000.0]
    assert parse_number_list("") == []
    assert parse_size_list("20, 20, all") == [20, 20, -1]
    assert parse_size_list("ALL") == [-1]
    assert parse_size_list("") == []
    for bad in ("20, x", "20,", "-5", "1.5"):
        with pytest.raises(ValueError):
            parse_size_list(bad)
    for bad in ("1000,", "x", "nan", "inf"):
        with pytest.raises(ValueError):
            parse_number_list(bad)


def test_audit_config_error_message_starts_with_code() -> None:
    exc = AuditConfigError(
        "TD-AUDIT-001", "Choose the key column.", field="key", columns=("k",)
    )
    assert str(exc).startswith("TD-AUDIT-001: ")
    assert (exc.code, exc.message, exc.field, exc.columns) == (
        "TD-AUDIT-001",
        "Choose the key column.",
        "key",
        ("k",),
    )
    assert isinstance(exc, ValueError)


def test_validators_raise_the_documented_codes() -> None:
    schema = {"a": pl.String, "n": pl.List(pl.Int64), "x": pl.Object}

    def code(fn, *args, **kwargs) -> str:
        with pytest.raises(AuditConfigError) as info:
            fn(*args, **kwargs)
        return info.value.code

    assert code(need, schema, "col", "", "key") == "TD-AUDIT-001"
    assert code(need, schema, "col", "zz", "key") == "TD-AUDIT-002"
    assert code(need, schema, "col", "n", "key") == "TD-AUDIT-003"
    assert code(need, schema, "col", "x", "key") == "TD-AUDIT-003"
    need(schema, "col", "n", "key", nested_ok=True)
    need(schema, "col", "a", "key")
    assert code(need_many, schema, "cols", [], "key") == "TD-AUDIT-001"
    assert code(need_many, schema, "cols", ["a", "zz"], "key") == "TD-AUDIT-002"
    assert code(check_range, False, "tol", "Tolerance", "0 or more") == "TD-AUDIT-004"
    check_range(True, "tol", "Tolerance", "0 or more")
    assert code(check_reserved, schema, ["a"]) == "TD-AUDIT-005"
    check_reserved(schema, ["new"])
    assert code(check_date_format, "%y") == "TD-AUDIT-007"
    check_date_format("%Y-%m-%d")


def test_join_and() -> None:
    assert join_and(["a"]) == "a"
    assert join_and(["a", "b", "c"]) == "a, b and c"


@dataclass
class _P(ParamsBase):
    column: str = ""
    keys: list = field(default_factory=list)
    top: int | None = None


def test_params_round_trip_and_unknown_keys() -> None:
    p = _P(column="amount", keys=["a", "b"], top=3)
    assert _P.from_dict(p.to_dict()) == p
    loaded = _P.from_dict({"column": "x", "obsolete": 1})
    assert loaded == _P(column="x")
    assert _P.from_dict(None) == _P()
    a, b = _P(), _P()
    a.keys.append("k")
    assert b.keys == []  # list defaults are not shared
    src = {"keys": ["q"]}
    got = _P.from_dict(src)
    got.keys.append("z")
    assert src["keys"] == ["q"]  # input is deep-copied


def test_params_schema_lists_every_field_with_its_default() -> None:
    schema = params_schema(_P)
    assert schema == {
        "column": {"default": ""},
        "keys": {"default": []},
        "top": {"default": None},
    }
    schema["keys"]["default"].append("x")
    assert params_schema(_P)["keys"]["default"] == []


def _agg(pop: int, exc: int, unread: int = 0) -> pl.LazyFrame:
    return pl.LazyFrame(
        {
            "population_rows": [pop],
            "population_value": [100.0],
            "exception_rows": [exc],
            "exception_value": [25.0],
            "unread": [unread],
            "groups": [3],
        }
    )


def _summary(pop: int, exc: int, unread: int = 0) -> pl.DataFrame:
    status = (
        pl.when(pl.col("exception_rows") > 0)
        .then(pl.lit("fail"))
        .otherwise(pl.lit("pass"))
    )
    message = pl.format(
        "{} of {} rows", pl.col("exception_rows"), pl.col("population_rows")
    )
    code = pl.lit(None, dtype=pl.String)
    status, message, code = warn_unreadable(status, message, code, "unread", "numbers")
    return summary_frame(
        _agg(pop, exc, unread),
        test_name="Demo",
        criteria="Rows over the limit.",
        parameters={"b": 2, "a": "\u00e9"},
        status=status,
        message=message,
        code=code,
        extras=("groups",),
    ).collect()


def test_summary_frame_columns_and_order() -> None:
    frame = _summary(10, 2)
    assert tuple(frame.columns) == (*BASE_SUMMARY, "groups")
    assert frame.schema["test_name"] == pl.String
    assert frame.schema["parameters"] == pl.String
    assert frame.schema["code"] == pl.String
    assert frame.schema["population_rows"] == pl.Int64
    assert frame.schema["population_value"] == pl.Float64
    assert frame.schema["exception_rate"] == pl.Float64
    row = frame.row(0, named=True)
    assert row["parameters"] == '{"a": "\u00e9", "b": 2}'  # sorted, not ASCII-escaped
    assert row["exception_rate"] == pytest.approx(0.2)
    assert row["status"] == "fail" and row["code"] is None
    assert row["message"] == "2 of 10 rows"


def test_summary_rate_is_null_for_an_empty_population() -> None:
    row = _summary(0, 0).row(0, named=True)
    assert row["exception_rate"] is None


def test_warn_unreadable_downgrades_pass_and_keeps_fail() -> None:
    passed = _summary(10, 0, unread=4).row(0, named=True)
    assert passed["status"] == "warn"
    assert passed["code"] == "TD-AUDIT-102"
    assert passed["message"].endswith(
        " 4 values could not be read as numbers and were skipped."
    )
    failed = _summary(10, 3, unread=4).row(0, named=True)
    assert failed["status"] == "fail"
    assert failed["code"] == "TD-AUDIT-102"
    clean = _summary(10, 0, unread=0).row(0, named=True)
    assert (clean["status"], clean["code"]) == ("pass", None)
    assert clean["message"] == "0 of 10 rows"


def test_warn_unreadable_keeps_an_existing_code() -> None:
    status, message, code = warn_unreadable(
        pl.lit("pass"),
        pl.lit("m"),
        pl.lit("TD-AUDIT-101"),
        "unread",
        "dates",
    )
    out = (
        _agg(5, 0, unread=2)
        .select(status.alias("s"), message.alias("m"), code.alias("c"))
        .collect()
    )
    assert out.row(0) == (
        "warn",
        "m 2 values could not be read as dates and were skipped.",
        "TD-AUDIT-101",
    )


def test_test_summary_round_trip() -> None:
    summary = TestSummary.from_summary_frame(
        _summary(10, 2), op="audit.demo", node_id=7, exceptions_var="var_x_1"
    )
    assert summary.test_id == "audit.demo#7"
    assert summary.exceptions_var == "var_x_1"
    assert summary.parameters == {"a": "\u00e9", "b": 2}
    assert summary.details == {"groups": 3}  # extras only, never the base columns
    assert summary.exception_rate == pytest.approx(0.2)
    assert TestSummary.from_dict(summary.to_dict()) == summary
    assert TestSummary.from_dict({**summary.to_dict(), "future": 1}) == summary
    assert TestSummary.__test__ is False


def test_test_summary_defaults_match_the_brief_contract() -> None:
    blank = TestSummary()
    assert blank.status == "pass" and blank.parameters == {} and blank.details == {}
    with pytest.raises(AttributeError):
        blank.status = "fail"  # frozen


def test_audit_result_for_run_collects_only_the_one_row_frames() -> None:
    big = pl.LazyFrame({"a": [1, 2, 3]})
    summary = pl.LazyFrame({"x": [1]})
    log = pl.LazyFrame({"y": [2]})
    result = AuditResult(frames=(big, summary, log), summary_index=1, log_index=2)
    out = result.for_run()
    assert isinstance(out[0], pl.LazyFrame)
    assert isinstance(out[1], pl.DataFrame) and isinstance(out[2], pl.DataFrame)
    assert isinstance(result.frames[1], pl.LazyFrame)  # the result itself is unchanged
    plain = AuditResult(frames=(big,)).for_run()
    assert isinstance(plain[0], pl.LazyFrame)
