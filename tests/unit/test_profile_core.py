"""Data Profile engine (core/profile.py), plan 05 section 6.1. No Qt."""

from __future__ import annotations

import datetime as dt
import decimal
import json
import sys

import polars as pl
import pytest

from tests.support.profile_fixtures import FX
from trigger_designer.core import profile as pf

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def prof() -> pf.DataProfile:
    return pf.profile_frame(FX)


def col(profile: pf.DataProfile, name: str) -> pf.ColumnProfile:
    return next(c for c in profile.columns if c.name == name)


def test_shape_and_schema(prof):
    assert prof.row_count == 10
    assert prof.column_count == len(FX.columns)
    assert prof.passes == 4
    assert prof.sampled is False
    frame = prof.to_frame()
    assert frame.schema == pl.Schema(pf.PROFILE_SCHEMA)
    assert frame.height == len(FX.columns)


def test_leading_zero_ids(prof):
    c = col(prof, "id")
    assert c.distinct_count == 10
    assert c.integer_like_count == 10
    assert c.leading_zero_count == 10
    assert (c.suggested_type, c.suggested_confidence) == ("String", 1.0)
    assert c.flags == ["leading_zeros"]
    assert c.min_length == c.max_length == 3
    assert c.top_values == [(f"{i:03d}", 1) for i in range(1, 6)]
    assert (c.min, c.max) == ("001", "010")


def test_messy_amount_column(prof):
    c = col(prof, "amount")
    assert c.null_count == 1
    assert c.empty_count == 1
    assert c.blank_count == 1
    assert c.whitespace_count == 1
    assert c.distinct_count == 9
    assert c.numeric_like_count == 5
    assert c.integer_like_count == 4
    assert c.trailing_minus_count == 1
    assert c.decimal_comma_count == 1
    assert c.dot_decimal_count == 1
    assert (c.min_length, c.max_length) == (0, 4)
    assert c.numeric_basis == "parsed_text"
    assert (c.min_numeric, c.max_numeric) == (7.0, 40.0)
    assert c.sum == 107.5
    assert c.mean == 21.5
    assert c.median == 20.5
    assert c.std == pytest.approx(13.765899897936205)
    assert (c.negative_count, c.zero_count) == (0, 0)
    assert (c.suggested_type, c.suggested_confidence) == ("String", 1.0)
    assert c.flags == [
        "mixed_numeric_text",
        "trailing_minus",
        "leading_trailing_whitespace",
    ]
    assert c.top_values == [
        ("", 1),
        (" 40 ", 1),
        ("1,5", 1),
        ("10", 1),
        ("123-", 1),
    ]


def test_native_int_column(prof):
    c = col(prof, "qty")
    assert c.null_count == 1
    assert c.null_pct == 10.0
    assert c.distinct_count == 6
    assert (c.min, c.max) == ("-1", "5")
    assert c.sum == 22.0
    assert c.mean == pytest.approx(22 / 9)
    assert c.median == 2.0
    assert c.std == pytest.approx(2.2422706745122847)
    assert (c.negative_count, c.zero_count) == (1, 1)
    assert c.numeric_basis == "native"
    assert (c.suggested_type, c.suggested_confidence) == ("Int64", 1.0)
    assert c.flags == ["negative_values"]
    assert c.top_values == [("5", 3), ("2", 2), ("-1", 1), ("0", 1), ("1", 1)]


def test_nan_and_inf(prof):
    c = col(prof, "price")
    assert (c.nan_count, c.inf_count, c.null_count) == (1, 1, 1)
    assert c.distinct_count == 7
    assert (c.min, c.max) == ("-0.5", "3.0")
    assert c.sum == 9.5
    assert c.mean == pytest.approx(9.5 / 7)
    assert c.median == 1.5
    assert c.std == pytest.approx(1.2488089563755576)
    assert c.flags == ["negative_values", "nan_values", "inf_values"]
    assert c.top_values[0] == ("1.5", 3)


def test_dates_stored_as_text(prof):
    c = col(prof, "when")
    assert c.date_like_count == 10
    assert c.date_format_hint == "%Y-%m-%d"
    assert (c.suggested_type, c.suggested_confidence) == ("Date", 1.0)
    assert c.flags == ["date_as_text"]
    assert c.numeric_basis == ""
    # parsed range, not text order
    assert (c.min, c.max) == ("2023-12-01", "2024-09-09")


def test_boolean_text(prof):
    c = col(prof, "flag")
    assert c.bool_like_count == 10
    assert c.suggested_type == "Boolean"
    assert c.top_values == [("Y", 6), ("N", 4)]
    assert c.distinct_count == 2
    assert c.flags == []


def test_constant_flag(prof):
    c = col(prof, "const")
    assert c.distinct_count == 1
    assert c.flags == ["constant"]


def test_all_null_flag(prof):
    c = col(prof, "nada")
    assert c.null_count == 10
    assert c.distinct_count == 0
    assert (c.suggested_type, c.suggested_confidence) == ("Unknown", 0.0)
    assert c.flags == ["all_null"]
    assert c.top_values == []
    assert c.mean is None


def test_decimal_comma_flag(prof):
    c = col(prof, "locale")
    assert c.decimal_comma_count == 10
    assert (c.suggested_type, c.suggested_confidence) == ("Float64", 1.0)
    assert c.flags == ["decimal_comma_suspected", "numeric_as_text"]
    assert c.numeric_basis == ""


def test_trailing_minus_flag(prof):
    c = col(prof, "sap")
    assert c.numeric_like_count == 7
    assert c.integer_like_count == 7
    assert c.trailing_minus_count == 3
    assert c.sum == 355.0
    assert (c.min_numeric, c.max_numeric) == (5.0, 200.0)
    assert c.mean == pytest.approx(355 / 7)
    assert c.median == 30.0
    assert (c.suggested_type, c.suggested_confidence) == ("Float64", 1.0)
    assert c.flags == ["trailing_minus", "numeric_as_text"]
    # trailing-minus values are not negatives
    assert c.negative_count == 0


def test_high_cardinality_and_mostly_null():
    frame = pl.DataFrame(
        {"id": [f"k{i}" for i in range(25)], "m": [None] * 13 + ["a"] * 12}
    )
    p = pf.profile_frame(frame)
    assert col(p, "id").flags == ["high_cardinality"]
    assert col(p, "m").flags == ["mostly_null"]


def test_flags_have_no_false_positives(prof):
    assert col(prof, "flag").flags == []
    qty = col(prof, "qty").flags
    assert [f for f in qty if pf.FLAG_TONE[f] == "warning"] == []


def test_mixed_date_text_flag():
    values = ["2024-01-31"] * 7 + ["not a date", "", "2024-02-01"]
    p = pf.profile_frame(pl.DataFrame({"posted": values}))
    c = col(p, "posted")
    assert c.flags == ["mixed_date_text"]
    assert c.suggested_type == "String"


def test_mixed_date_flag_ignores_eight_digit_ids():
    # yyyymmdd-looking numbers are ids here, and most are plain integers
    frame = pl.DataFrame({"id": ["20240131", "20240229", "99999999", "12345678"]})
    assert "mixed_date_text" not in col(pf.profile_frame(frame), "id").flags


def test_negative_values_flag():
    p = pf.profile_frame(pl.DataFrame({"a": ["1", "-2", "3"], "b": ["1", "2", "3-"]}))
    assert "negative_values" in col(p, "a").flags
    assert "negative_values" not in col(p, "b").flags


def test_outlier_flag():
    tame = [10.0 + (i % 5) for i in range(200)]
    with_outlier = [*tame, 1_000_000.0]
    assert (
        "outlier_suspected"
        in col(pf.profile_frame(pl.DataFrame({"amount": with_outlier})), "amount").flags
    )
    assert (
        "outlier_suspected"
        not in col(pf.profile_frame(pl.DataFrame({"amount": tame})), "amount").flags
    )


def test_outlier_flag_needs_enough_rows():
    p = pf.profile_frame(pl.DataFrame({"a": [1.0, 1.0, 1.0, 1000.0]}))
    assert "outlier_suspected" not in col(p, "a").flags


def test_text_min_max_is_parsed():
    # lexicographic order would say min "1002.89", max "999.54"
    p = pf.profile_frame(
        pl.DataFrame(
            {
                "amount": ["999.54", "1002.89", "15", "20"],
                "day": ["31-12-2024", "01-02-2024", "15-06-2024", "10-10-2024"],
                "word": ["b", "a", "c", "a"],
            }
        )
    )
    amount = col(p, "amount")
    assert (amount.suggested_type, amount.min, amount.max) == (
        "Float64",
        "15",
        "1002.89",
    )
    day = col(p, "day")
    assert (day.suggested_type, day.min, day.max) == (
        "Date",
        "2024-02-01",
        "2024-12-31",
    )
    word = col(p, "word")
    assert (word.min, word.max) == ("a", "c")


def test_text_min_max_for_integer_text_is_integer_looking():
    p = pf.profile_frame(pl.DataFrame({"n": ["10", "9", "100"]}))
    c = col(p, "n")
    assert (c.suggested_type, c.min, c.max) == ("Int64", "9", "100")


def test_flag_tone_covers_every_flag():
    assert set(pf.FLAG_TONE) == set(pf.FLAG_ORDER)
    assert set(pf.FLAG_TONE.values()) == {"info", "warning"}
    assert pf.FLAG_TONE["numeric_as_text"] == "info"
    assert pf.FLAG_TONE["mixed_date_text"] == "warning"


def test_histogram_counts(prof):
    c = col(prof, "qty")
    assert len(c.histogram) == 20
    assert sum(c.histogram) == 9
    assert c.histogram[0] == 1  # the -1
    assert c.histogram[19] == 3  # the three 5s


def test_collect_pass_budget():
    big = pl.DataFrame({"a": list(range(1000))})
    assert pf.profile_frame(FX).passes == 4
    head = pf.profile_frame(
        big, settings=pf.ProfileSettings(sample_mode="head", sample_rows=100)
    )
    assert head.passes == 4
    rnd = pf.profile_frame(
        big, settings=pf.ProfileSettings(sample_mode="random", sample_rows=100)
    )
    assert rnd.passes == 5
    assert pf.profile_frame(pl.DataFrame({"a": []}, schema={"a": pl.Int64})).passes == 2
    assert pf.profile_frame(pl.DataFrame()).passes == 0


def test_head_sample():
    frame = pl.DataFrame({"n": list(range(1000))})
    p = pf.profile_frame(
        frame, settings=pf.ProfileSettings(sample_mode="head", sample_rows=100)
    )
    assert p.row_count == 100
    assert p.sampled is True
    assert p.columns[0].max == "99"
    assert p.columns[0].sampled is True
    # nothing dropped when the source is smaller than N
    short = pf.profile_frame(
        frame.head(50),
        settings=pf.ProfileSettings(sample_mode="head", sample_rows=100),
    )
    assert short.sampled is False


def test_random_sample_is_reproducible():
    frame = pl.DataFrame({"n": list(range(1000))})

    def run(seed: int, rows: int = 100):
        s = pf.ProfileSettings(sample_mode="random", sample_rows=rows, seed=seed)
        return pf.profile_frame(frame, settings=s)

    a, b, c = run(42), run(42), run(8)
    assert a.sampled is True
    assert a.row_count == 100
    assert a.to_frame().drop("sampled").equals(b.to_frame().drop("sampled"))
    assert not a.to_frame().equals(c.to_frame())
    whole = run(42, rows=5000)
    assert whole.sampled is False
    assert whole.row_count == 1000


def test_profile_is_byte_identical_across_runs():
    # Polars sums floats across threads; without rounding the last bit of
    # mean/std/sum drifts between runs and the same file profiles differently.
    n = 300_000
    frame = pl.DataFrame(
        {
            "x": [((i * 7919) % 100_003) / 7.0 for i in range(n)],
            "t": [f"{((i * 104729) % 99_991) / 3.0:.4f}" for i in range(n)],
        }
    )
    first = pf.profile_table(frame)
    for _ in range(4):
        assert pf.profile_table(frame).equals(first)


def test_random_sample_with_colliding_column_name():
    frame = pl.DataFrame({"__pf_i": list(range(300)), "x": list(range(300))})
    s = pf.ProfileSettings(sample_mode="random", sample_rows=50)
    p = pf.profile_frame(frame, settings=s)
    assert p.row_count == 50
    assert [c.name for c in p.columns] == ["__pf_i", "x"]


def test_random_sample_emits_no_deprecation_warning(recwarn):
    frame = pl.DataFrame({"n": list(range(500))})
    s = pf.ProfileSettings(sample_mode="random", sample_rows=50)
    pf.profile_frame(frame, settings=s)
    assert [str(w.message) for w in recwarn if "implode" in str(w.message)] == []


def test_distinct_exact_vs_approx():
    frame = pl.DataFrame({"n": list(range(1000))})
    exact = pf.profile_frame(frame).columns[0]
    assert exact.distinct_is_approx is False
    assert exact.distinct_count == 1000
    approx = pf.profile_frame(
        frame, settings=pf.ProfileSettings(approx_distinct_threshold=500)
    ).columns[0]
    assert approx.distinct_is_approx is True
    assert abs(approx.distinct_count - 1000) / 1000 <= 0.05


def test_edge_dtypes_do_not_raise():
    frame = pl.DataFrame(
        {
            "lst": [[1, 2], [3]],
            "st": [{"a": 1}, {"a": 2}],
            "bin": [b"x", b"y"],
            "cat": pl.Series(["a", "b"], dtype=pl.Categorical),
            "enum": pl.Series(["a", "b"], dtype=pl.Enum(["a", "b"])),
            "dec": pl.Series([decimal.Decimal("-2.25"), decimal.Decimal("1.5")]),
            "dur": [dt.timedelta(seconds=1), dt.timedelta(seconds=2)],
            "tim": [dt.time(1), dt.time(2)],
            "nul": pl.Series([None, None], dtype=pl.Null),
            "boo": [True, False],
            "dtm": [dt.datetime(2024, 1, 1), dt.datetime(2024, 1, 2)],
            "arr": pl.Series([[1, 2], [3, 4]], dtype=pl.Array(pl.Int64, 2)),
            "dat": [dt.date(2024, 1, 1), dt.date(2024, 1, 2)],
            "u8": pl.Series([1, 2], dtype=pl.UInt8),
        }
    )
    p = pf.profile_frame(frame)
    out = p.to_frame()
    assert out.schema == pl.Schema(pf.PROFILE_SCHEMA)
    assert out.height == frame.width
    assert col(p, "dec").min == "-2.25"
    assert col(p, "lst").distinct_count is None
    assert col(p, "cat").suggested_type == "Categorical"
    assert col(p, "dur").top_values == []


def test_huge_and_unicode_strings():
    huge = pf.profile_frame(pl.DataFrame({"s": ["a" * 2_000_000, "b"]})).columns[0]
    assert huge.max_length == 2_000_000
    assert len(huge.min) <= pf.MAX_TEXT
    uni = pf.profile_frame(
        pl.DataFrame({"s": ["Zoë", "日本語", "naïve", "日本語", "😀"]})
    ).columns[0]
    assert (uni.min_length, uni.max_length) == (1, 5)
    assert uni.top_values[0] == ("日本語", 2)


def test_odd_column_names():
    frame = pl.DataFrame({"a b": [1], "A B": [2], "x.y": [3], "c0__nulls": [4]})
    p = pf.profile_frame(frame)
    assert [c.name for c in p.columns] == ["a b", "A B", "x.y", "c0__nulls"]
    assert p.to_frame().height == 4


def test_zero_rows_and_columns():
    empty_rows = pf.profile_frame(
        pl.DataFrame({"a": [], "s": []}, schema={"a": pl.Int64, "s": pl.String})
    )
    assert empty_rows.row_count == 0
    s = col(empty_rows, "s")
    assert (s.suggested_type, s.flags, s.top_values) == ("Unknown", [], [])
    assert col(empty_rows, "a").null_pct == 0.0
    no_cols = pf.profile_frame(pl.DataFrame())
    assert (no_cols.row_count, no_cols.column_count, no_cols.passes) == (0, 0, 0)
    assert no_cols.to_frame().schema == pl.Schema(pf.PROFILE_SCHEMA)
    assert no_cols.to_frame().height == 0


def test_single_row_is_not_constant():
    p = pf.profile_frame(pl.DataFrame({"a": ["x"]}))
    assert col(p, "a").flags == []
    assert col(p, "a").std is None


def test_accepts_lazy_frames_and_csv_strings(tmp_path):
    path = tmp_path / "t.csv"
    path.write_text("n,d\n1,2024-01-01\n2,2024-01-02\n")
    lazy = pl.scan_csv(path, infer_schema=False)
    p = pf.profile_frame(lazy)
    assert (col(p, "n").suggested_type, col(p, "d").suggested_type) == (
        "Int64",
        "Date",
    )


def test_max_rows_is_head_sampling():
    frame = pl.DataFrame({"n": list(range(1000))})
    p = pf.profile_frame(frame, max_rows=10)
    assert (p.row_count, p.sampled, p.settings.sample_mode) == (10, True, "head")


def test_profile_table_matches_to_frame():
    assert pf.profile_table(FX).equals(pf.profile_frame(FX).to_frame())
    assert pf.profile_table(FX, top_n=2).get_column("top_values")[0].count("[") == 3


def test_empty_profile_frame_has_the_schema():
    f = pf.empty_profile_frame()
    assert f.schema == pl.Schema(pf.PROFILE_SCHEMA)
    assert f.height == 0


def test_tsv_has_header_and_escapes_tabs():
    frame = pl.DataFrame({"a": ["x\ty", None], "b": [1, 2]})
    text = pf.profile_to_tsv(frame)
    lines = text.splitlines()
    assert lines[0] == "a\tb"
    assert lines[1] == "x y\t1"
    assert lines[2] == "\t2"
    assert all(line.count("\t") == 1 for line in lines)


def test_xlsx_without_helper_raises_runtime_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "trigger_designer.core.excel", None)
    with pytest.raises(RuntimeError, match="Excel export is unavailable"):
        pf.write_profile_xlsx(pl.DataFrame({"a": [1]}), "unused.xlsx")


def test_xlsx_roundtrip(tmp_path):
    pytest.importorskip("trigger_designer.core.excel")
    openpyxl = pytest.importorskip("openpyxl")
    frame = pf.profile_frame(FX).to_frame()
    path = tmp_path / "profile.xlsx"
    pf.write_profile_xlsx(frame, str(path))
    sheet = openpyxl.load_workbook(path)["Profile"]
    assert sheet.max_row == frame.height + 1
    assert [c.value for c in sheet[1]] == frame.columns


def test_profile_summary(prof):
    s = pf.profile_summary(prof)
    assert s["rows"] == 10
    assert s["flagged"]["nada"] == ["all_null"]


def test_profile_table_carries_the_chart_data(prof):
    frame = prof.to_frame()
    assert "histogram" in frame.columns
    qty = frame.filter(pl.col("column") == "qty").row(0, named=True)
    assert sum(json.loads(qty["histogram"])) == 9
    text = frame.filter(pl.col("column") == "const").row(0, named=True)
    assert json.loads(text["histogram"]) == []  # no numbers, no histogram


def test_profile_from_frame_round_trips(prof):
    rebuilt = pf.profile_from_frame(prof.to_frame())
    assert rebuilt.row_count == 10
    assert rebuilt.column_count == len(FX.columns)
    assert rebuilt.to_frame().equals(prof.to_frame())


def test_profile_from_frame_restores_what_the_dock_shows(prof):
    rebuilt = pf.profile_from_frame(prof.to_frame())
    amount = col(rebuilt, "amount")
    assert amount.flags == col(prof, "amount").flags
    assert amount.top_values == col(prof, "amount").top_values
    assert amount.numeric_basis == "parsed_text"
    assert amount.mean == col(prof, "amount").mean
    assert col(rebuilt, "qty").histogram == col(prof, "qty").histogram
    assert [c.position for c in rebuilt.columns] == list(range(1, 11))


def test_profile_from_frame_keeps_the_sample_flag_and_settings():
    big = pl.DataFrame({"n": list(range(5000))})
    settings = pf.ProfileSettings(sample_mode="head", sample_rows=1000)
    frame = pf.profile_frame(big, settings=settings).to_frame()
    rebuilt = pf.profile_from_frame(frame, settings)
    assert rebuilt.sampled is True
    assert rebuilt.row_count == 1000
    assert rebuilt.settings.sample_mode == "head"


def test_profile_from_frame_of_an_empty_table():
    rebuilt = pf.profile_from_frame(pf.empty_profile_frame())
    assert (rebuilt.row_count, rebuilt.column_count, rebuilt.sampled) == (0, 0, False)
    assert rebuilt.columns == []


def test_write_frame_xlsx_makes_a_formatted_workbook(tmp_path):
    pytest.importorskip("xlsxwriter")
    openpyxl = pytest.importorskip("openpyxl")
    from trigger_designer.core.excel import write_frame_xlsx

    frame = pl.DataFrame({"a": [1, None, 3], "b": ["x", "y", None]})
    path = tmp_path / "t.xlsx"
    write_frame_xlsx(frame, str(path), sheet_name="Data")
    sheet = openpyxl.load_workbook(path)["Data"]
    assert [c.value for c in sheet[1]] == ["a", "b"]
    assert sheet["A1"].font.bold is True
    assert sheet.freeze_panes == "A2"
    # streamed writer (constant memory): filter buttons via autofilter, no table
    assert sheet.auto_filter.ref == "A1:B4"
    assert [r[0].value for r in sheet.iter_rows(min_row=2)] == [1, None, 3]
