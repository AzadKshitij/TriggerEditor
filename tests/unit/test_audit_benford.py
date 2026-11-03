"""Benford core (``core/audit/benford.py``) and the node's generated code.

Reference numbers are the independent pure-Python values of
docs/plan/04-audit-test-nodes.md section 4.3; ``reference`` below recomputes them
with plain ``math`` so the Polars implementation is checked against a second one.
"""

from __future__ import annotations

import itertools
import math
import random
from decimal import Decimal

import polars as pl
import pytest

from tests.support.audit_demo import demo_graph
from tests.support.audit_ledger import make_ledger
from trigger_designer.core.audit.benford import (
    LIVE_ROW_LIMIT,
    MAD_BANDS,
    MIN_TESTED,
    BenfordParams,
    build_table,
    chart_data,
    chi2_sf,
    conformity,
    first_digits_expr,
    run_benford,
)
from trigger_designer.core.audit.common import BASE_SUMMARY, AuditConfigError


def reference(counts: dict[int, int], digits: int) -> dict:
    rng = range(1, 10) if digits == 1 else range(10, 100)
    n = sum(counts.values())
    k = len(rng)
    z, mad, chi = {}, 0.0, 0.0
    for d in rng:
        pe = math.log10(1 + 1 / d)
        diff = abs(counts.get(d, 0) / n - pe)
        cc = 1 / (2 * n) if 1 / (2 * n) < diff else 0.0
        z[d] = (diff - cc) / math.sqrt(pe * (1 - pe) / n)
        mad += diff / k
        chi += (counts.get(d, 0) - pe * n) ** 2 / (pe * n)
    return {"z": z, "mad": mad, "chi": chi, "p": chi2_sf(chi, k - 1)}


def _frame(amounts, dtype=pl.Float64) -> pl.LazyFrame:
    return pl.DataFrame(
        {"amount": amounts, "ref": range(len(amounts))},
        schema_overrides={"amount": dtype},
    ).lazy()


def _params(**kw) -> BenfordParams:
    return BenfordParams(amount_column="amount", **kw)


def _summary(result) -> dict:
    return result.for_run()[1].row(0, named=True)


def _fixture_a() -> pl.LazyFrame:
    counts = [301, 176, 125, 97, 79, 67, 58, 51, 46]
    amounts = [d * 1000 + i for d, c in enumerate(counts, 1) for i in range(c)]
    return _frame(amounts)


# ---- digits --------------------------------------------------------------------
VECTOR = [
    (0.3, 3, 30),
    (0.07, 7, 70),
    (1000.0, 1, 10),
    (999.99, 9, 99),
    (4.35, 4, 43),
    (12345678.9, 1, 12),
    (1e-5, 1, 10),
    (0.29, 2, 29),
    (9.99, 9, 99),
    (-250.0, 2, 25),
]


def test_first_digit_vector() -> None:
    frame = pl.DataFrame({"a": [v for v, _, _ in VECTOR]})
    out = frame.select(
        first_digits_expr(pl.col("a"), 1).alias("d1"),
        first_digits_expr(pl.col("a"), 2).alias("d2"),
    )
    assert out["d1"].to_list() == [d1 for _, d1, _ in VECTOR]
    assert out["d2"].to_list() == [d2 for _, _, d2 in VECTOR]


def test_first_digits_match_decimal_reference_on_random_amounts() -> None:
    rnd = random.Random(20260101)
    values = [round(10 ** rnd.uniform(-2, 8), 2) for _ in range(20_000)]
    values = [v for v in values if v > 0]
    out = pl.DataFrame({"a": values}).select(
        first_digits_expr(pl.col("a"), 1).alias("d1"),
        first_digits_expr(pl.col("a"), 2).alias("d2"),
    )
    wrong = 0
    for v, d1, d2 in zip(values, out["d1"], out["d2"]):
        digits = Decimal(repr(v)).as_tuple().digits
        text = "".join(str(x) for x in digits).lstrip("0").ljust(2, "0")
        if int(text[0]) != d1 or int(text[:2]) != d2:
            wrong += 1
    assert wrong == 0


# ---- statistics ---------------------------------------------------------------
def test_chi2_sf_reference_points() -> None:
    assert chi2_sf(3.841458820694124, 1) == pytest.approx(0.05, abs=1e-9)
    assert chi2_sf(15.50731305586545, 8) == pytest.approx(0.05, abs=1e-9)
    assert chi2_sf(20.090235029663233, 8) == pytest.approx(0.01, abs=1e-9)
    assert chi2_sf(112.02198, 89) == pytest.approx(0.05, abs=1e-7)
    assert chi2_sf(0, 8) == 1.0
    assert chi2_sf(-1, 8) == 1.0
    series = [chi2_sf(x / 2, 8) for x in range(1, 120)]
    assert all(a > b for a, b in itertools.pairwise(series))
    assert all(0.0 <= s <= 1.0 for s in series)


def _table_check(counts: dict[int, int], digits: int) -> None:
    table = build_table(counts, digits)
    ref = reference(counts, digits)
    n = sum(counts.values())
    assert table.height == (9 if digits == 1 else 90)
    assert table["count"].sum() == n
    assert table["proportion"].sum() == pytest.approx(1.0, abs=1e-12)
    assert table["expected_proportion"].sum() == pytest.approx(1.0, abs=1e-12)
    for digit, z in ref["z"].items():
        got = table.filter(pl.col("digit") == digit)["z_statistic"][0]
        assert got == pytest.approx(z, rel=1e-9)
    assert table["chi_square_contribution"].sum() == pytest.approx(ref["chi"], rel=1e-9)
    assert (table["difference"].abs().sum() / table.height) == pytest.approx(
        ref["mad"], rel=1e-9
    )


def test_table_matches_independent_reference() -> None:
    first = dict(zip(range(1, 10), [301, 176, 125, 97, 79, 67, 58, 51, 46]))
    _table_check(first, 1)
    ref = reference(first, 1)
    assert ref["mad"] == pytest.approx(0.0001011163, rel=1e-6)
    assert ref["chi"] == pytest.approx(0.002362, rel=1e-3)
    assert ref["z"][1] == pytest.approx(0.002068, abs=1e-6)
    assert ref["z"][2] == pytest.approx(0.007576, abs=1e-6)
    assert ref["z"][9] == pytest.approx(0.0367, abs=1e-4)

    flat = {d: 100 for d in range(1, 10)}
    _table_check(flat, 1)
    ref = reference(flat, 1)
    assert ref["mad"] == pytest.approx(0.0597170351, rel=1e-8)
    assert ref["chi"] == pytest.approx(361.528464, rel=1e-8)
    assert ref["p"] == pytest.approx(3.1297e-73, rel=1e-3)
    assert ref["z"][1] == pytest.approx(12.384628, rel=1e-6)
    table = build_table(flat, 1)
    assert table.filter(pl.col("significant"))["digit"].to_list() == [
        1,
        2,
        5,
        6,
        7,
        8,
        9,
    ]

    flat2 = {d: 10 for d in range(10, 100)}
    _table_check(flat2, 2)
    ref = reference(flat2, 2)
    assert ref["mad"] == pytest.approx(0.0059742752, rel=1e-8)
    assert ref["chi"] == pytest.approx(366.372711, rel=1e-8)
    assert ref["p"] == pytest.approx(2.4784e-35, rel=1e-3)
    assert ref["z"][10] == pytest.approx(4.476884, rel=1e-6)


def test_table_invariants_hold_for_random_count_vectors() -> None:
    rnd = random.Random(20260101)
    for _ in range(50):
        digits = rnd.choice((1, 2))
        rng = range(1, 10) if digits == 1 else range(10, 100)
        counts = {d: rnd.randint(0, 40) for d in rng}
        if not sum(counts.values()):
            continue
        _table_check(counts, digits)


def test_conformity_bands_are_pinned() -> None:
    assert MAD_BANDS == {1: (0.006, 0.012, 0.015), 2: (0.0012, 0.0018, 0.0022)}
    assert MIN_TESTED == {1: 100, 2: 1000}
    assert conformity(0.006, 1) == "close"
    assert conformity(0.0060001, 1) == "acceptable"
    assert conformity(0.012, 1) == "acceptable"
    assert conformity(0.015, 1) == "marginal"
    assert conformity(0.0151, 1) == "nonconforming"
    assert conformity(0.0012, 2) == "close"
    assert conformity(0.0018, 2) == "acceptable"
    assert conformity(0.0022, 2) == "marginal"
    assert conformity(0.00221, 2) == "nonconforming"


# ---- run_benford ---------------------------------------------------------------
def test_run_benford_end_to_end_on_fixture_a() -> None:
    result = run_benford(_fixture_a(), _params())
    table = result.frames[0].collect()
    assert table["count"].to_list() == [301, 176, 125, 97, 79, 67, 58, 51, 46]
    summary = _summary(result)
    assert list(summary)[: len(BASE_SUMMARY)] == list(BASE_SUMMARY)
    assert summary["status"] == "pass" and summary["code"] is None
    assert summary["test_name"] == "Benford first digit"
    assert summary["conformity"] == "close"
    assert summary["tested_rows"] == summary["population_rows"] == 1000
    assert summary["exception_rows"] == 0 and summary["flagged_digits"] == ""
    assert summary["chi_square_df"] == 8
    assert summary["mad"] == pytest.approx(0.0001011163, rel=1e-6)
    assert summary["message"].startswith("Mean absolute deviation 0.0001: close with")
    assert result.frames[2].collect().height == 0
    assert result.frames[2].collect_schema().names()[-1] == "benford_digits"
    assert result.summary_index == 1


def test_minimum_zero_and_unreadable_amounts() -> None:
    base = [
        d * 1000 + i
        for d, c in enumerate([301, 176, 125, 97, 79, 67, 58, 51, 46], 1)
        for i in range(c)
    ]
    amounts = [str(a) for a in base] + ["5", "0", "-0.00", None, "abc", "n/a"]
    result = run_benford(_frame(amounts, pl.String), _params())
    summary = _summary(result)
    assert summary["tested_rows"] == 1000  # 5 is below 10; zeros never tested
    assert summary["population_rows"] == len(amounts)
    assert summary["unparseable_rows"] == 2  # "abc" and "n/a"
    assert summary["status"] == "warn" and summary["code"] == "TD-AUDIT-102"
    assert "2 values could not be read as amounts" in summary["message"]
    # Lowering the minimum brings the 5 in; zero stays out.
    low = _summary(
        run_benford(_frame(amounts, pl.String), _params(min_abs_amount=0.01))
    )
    assert low["tested_rows"] == 1001


def test_negatives_and_accounting_text_use_the_absolute_value() -> None:
    amounts = ["(1,234.50)", "-250", "$5,000", " 7,000.5 ", "€90"]
    result = run_benford(_frame(amounts, pl.String), _params())
    table = result.frames[0].collect()
    assert dict(zip(table["digit"], table["count"])) == {
        1: 1,
        2: 1,
        5: 1,
        7: 1,
        9: 1,
        3: 0,
        4: 0,
        6: 0,
        8: 0,
    }
    assert _summary(result)["unparseable_rows"] == 0


def test_non_finite_amounts_are_unreadable_not_crashes() -> None:
    result = run_benford(_frame([float("nan"), float("inf"), 123.0, None]), _params())
    summary = _summary(result)
    assert summary["tested_rows"] == 1 and summary["unparseable_rows"] == 2


def test_too_few_rows_warns_with_td_audit_101() -> None:
    amounts = [d * 1000 + i for d in range(1, 10) for i in range(10)]  # 90 rows
    summary = _summary(run_benford(_frame(amounts), _params()))
    assert summary["tested_rows"] == 90 and summary["status"] == "fail"
    assert summary["code"] == "TD-AUDIT-101"
    assert "Only 90 rows were tested; at least 100 are needed" in summary["message"]
    # A close fit on 99 rows is downgraded pass -> warn.
    counts = [30, 18, 12, 10, 8, 7, 6, 5, 3]  # 99 rows, close to Benford
    close = [d * 1000 + i for d, c in enumerate(counts, 1) for i in range(c)]
    summary = _summary(run_benford(_frame(close), _params()))
    assert summary["tested_rows"] == 99 and summary["conformity"] in (
        "close",
        "acceptable",
    )
    assert summary["status"] == "warn" and summary["code"] == "TD-AUDIT-101"


def test_nothing_to_test_is_a_warning_with_empty_stats() -> None:
    for amounts in ([0.0, 0.0, 0.0], [1.0, 2.0], [], [None, None]):
        result = run_benford(_frame(amounts), _params())
        summary = _summary(result)
        assert summary["status"] == "warn" and summary["code"] == "TD-AUDIT-101"
        assert (
            summary["message"] == "No row had a usable amount, so nothing was tested."
        )
        assert summary["mad"] is None and summary["p_value"] is None
        assert summary["chi_square"] is None and summary["conformity"] is None
        assert summary["tested_rows"] == 0 and summary["exception_rows"] == 0
        table = result.frames[0].collect()
        assert table.height == 9 and table["count"].sum() == 0
        assert not table["significant"].any()
        assert table["proportion"].null_count() == 9
        assert result.frames[2].collect().height == 0
        assert chart_data(table, []).observed == (0.0,) * 9


def test_one_repeated_digit_is_nonconforming() -> None:
    summary = _summary(run_benford(_frame([555.0] * 500), _params()))
    assert summary["status"] == "fail" and summary["conformity"] == "nonconforming"
    assert summary["flagged_digits"] == "5" and summary["exception_rows"] == 500


def test_the_ledger_matches_the_plan_numbers() -> None:
    ledger = make_ledger()
    gl, ap = ledger.gl.lazy(), ledger.ap.lazy()
    result = run_benford(gl, _params())
    s = _summary(result)
    assert (s["tested_rows"], s["conformity"], s["status"]) == (2013, "close", "pass")
    assert s["mad"] == pytest.approx(0.003594, abs=1e-6)
    assert s["chi_square"] == pytest.approx(2.8592, abs=1e-4)
    assert s["p_value"] == pytest.approx(0.9429, abs=1e-4)
    assert s["flagged_digits"] == "" and result.frames[2].collect().height == 0
    counts = result.frames[0].collect()["count"].to_list()
    assert counts == [590, 361, 243, 187, 170, 138, 119, 104, 101]

    two = run_benford(gl, _params(digits=2))
    s = _summary(two)
    assert s["conformity"] == "acceptable" and s["flagged_digits"] == "49, 94"
    assert s["chi_square_df"] == 89 and s["status"] == "pass"
    assert s["p_value"] == pytest.approx(0.5628, abs=1e-4)
    assert two.frames[2].collect().height == 48
    assert s["test_name"] == "Benford first two digits"

    bad = run_benford(ap, _params())
    s = _summary(bad)
    assert s["conformity"] == "nonconforming" and s["status"] == "fail"
    assert s["flagged_digits"] == "5, 6, 7, 8, 9" and s["exception_rows"] == 400
    assert s["exception_value"] == pytest.approx(2951968.09, abs=0.01)
    assert s["mad"] == pytest.approx(0.155327, abs=1e-6)

    everything = run_benford(ledger.frame.lazy(), _params())
    s = _summary(everything)
    assert s["tested_rows"] == 2413 and s["mad"] == pytest.approx(0.028145, abs=1e-6)
    assert everything.frames[2].collect().height == 1032


# ---- drill-down ------------------------------------------------------------------
def test_drill_down_returns_source_rows_in_input_order() -> None:
    ap = make_ledger().ap
    result = run_benford(ap.lazy(), _params())
    drill = result.frames[2].collect()
    assert drill.columns == [*ap.columns, "benford_digits"]
    assert drill.drop("benford_digits").equals(ap)
    assert set(drill["benford_digits"]) <= {5, 6, 7, 8, 9}

    manual = (
        run_benford(ap.lazy(), _params(drill_auto=False, drill_digits=[5, 5, 7]))
        .frames[2]
        .collect()
    )
    expected = ap.filter(
        pl.col("amount")
        .cast(pl.Float64)
        .cast(pl.String)
        .str.slice(0, 1)
        .is_in(["5", "7"])
    )
    assert manual["benford_digits"].unique().sort().to_list() == [5, 7]
    assert (
        manual.drop("benford_digits")["je_number"].to_list()
        == expected["je_number"].to_list()
    )

    none = run_benford(ap.lazy(), _params(drill_auto=False, drill_digits=[])).frames[2]
    assert none.collect().height == 0
    assert none.collect_schema().names()[-1] == "benford_digits"


def test_manual_drill_down_is_independent_of_the_flagged_set() -> None:
    result = run_benford(_fixture_a(), _params(drill_auto=False, drill_digits=[9]))
    assert result.frames[2].collect().height == 46
    assert _summary(result)["exception_rows"] == 0


# ---- validation ----------------------------------------------------------------
def _code(frame, **kw) -> str:
    with pytest.raises(AuditConfigError) as info:
        run_benford(frame, BenfordParams(**kw))
    return info.value.code


def test_validation_codes() -> None:
    frame = pl.DataFrame(
        {"amount": [1.0], "nested": [[1]], "benford_digits": [1]}
    ).lazy()
    assert _code(frame) == "TD-AUDIT-001"
    assert _code(frame, amount_column="gone") == "TD-AUDIT-002"
    assert _code(frame, amount_column="nested") == "TD-AUDIT-003"
    ok = pl.DataFrame({"amount": [1.0]}).lazy()
    assert _code(ok, amount_column="amount", digits=3) == "TD-AUDIT-004"
    assert _code(ok, amount_column="amount", min_abs_amount=-1) == "TD-AUDIT-004"
    assert (
        _code(ok, amount_column="amount", drill_auto=False, drill_digits=[10])
        == "TD-AUDIT-004"
    )
    assert (
        _code(ok, amount_column="amount", digits=2, drill_auto=False, drill_digits=[9])
        == "TD-AUDIT-004"
    )
    assert _code(frame, amount_column="amount") == "TD-AUDIT-005"
    # A stale manual list is ignored while the automatic drill-down is on.
    run_benford(ok, BenfordParams(amount_column="amount", drill_digits=[49]))


def test_params_round_trip() -> None:
    p = BenfordParams(amount_column="a", digits=2, drill_auto=False, drill_digits=[10])
    assert BenfordParams.from_dict(p.to_dict()) == p
    assert BenfordParams.from_dict({}) == BenfordParams()
    assert BenfordParams().drill_digits is not BenfordParams().drill_digits


# ---- determinism, laziness, live limit ---------------------------------------------
def test_results_are_deterministic() -> None:
    frame = make_ledger().frame.lazy()
    a, b = run_benford(frame, _params()), run_benford(frame, _params())
    for x, y in zip(a.for_run(), b.for_run()):
        x = x.collect() if isinstance(x, pl.LazyFrame) else x
        y = y.collect() if isinstance(y, pl.LazyFrame) else y
        assert x.equals(y)


def test_outputs_stay_lazy_and_the_summary_is_collected_for_run() -> None:
    result = run_benford(_fixture_a(), _params())
    assert all(isinstance(f, pl.LazyFrame) for f in result.frames)
    run = result.for_run()
    assert isinstance(run[1], pl.DataFrame) and isinstance(run[2], pl.LazyFrame)
    assert result.extras["table"].height == 9


def test_live_row_limit_reads_only_the_leading_rows() -> None:
    frame = pl.select(pl.int_range(10, 2_000_010).alias("amount")).lazy()
    limited = run_benford(frame, _params(), row_limit=1000)
    s = _summary(limited)
    assert s["population_rows"] == 1000 and s["tested_rows"] == 1000
    assert "Live preview reads the first 1,000 rows." in s["message"]
    assert limited.extras["limited"] is True
    assert limited.frames[2].collect().height <= 1000
    # A frame smaller than the limit is complete: no note.
    small = run_benford(_fixture_a(), _params(), row_limit=5000)
    assert "Live preview" not in _summary(small)["message"]
    assert small.extras["limited"] is False
    # Run (no limit) sees all of it.
    full = _summary(run_benford(frame, _params()))
    assert full["population_rows"] == 2_000_000
    assert LIVE_ROW_LIMIT == 1_000_000


def test_only_the_digit_table_is_collected() -> None:
    """The one collect is a group-by of <= 91 groups, never the population."""
    frame = pl.select(pl.int_range(10, 600_010).alias("amount")).lazy()
    seen: list[tuple[int, int]] = []
    original = pl.LazyFrame.collect

    def spy(self, *args, **kwargs):
        out = original(self, *args, **kwargs)
        if isinstance(out, pl.DataFrame):
            seen.append(out.shape)
        return out

    pl.LazyFrame.collect = spy
    try:
        run_benford(frame, _params(digits=2))
    finally:
        pl.LazyFrame.collect = original
    assert seen and all(rows <= 91 for rows, _ in seen)


# ---- generated code ------------------------------------------------------------------
def test_generated_code_agrees_with_the_live_result() -> None:
    from trigger_designer.qt.widgets.nodes.Audit.benford import TriggerNode_Benford

    frame = make_ledger().frame.lazy()
    _window, source, node = demo_graph(frame, TriggerNode_Benford)
    content = node.content
    content.amount_column = "amount"
    content.digits = 2
    content.drill_auto = False
    content.drill_digits = [49, 94]
    node.markDirty(True)
    node.eval()
    assert not node.isInvalid()

    names = content.output_variable_names()
    assert [n.rsplit("_", 1)[0] for n in names] == [
        "var_benford",
        "var_benfordsum",
        "var_benforddrill",
    ]
    assert content.table_var == names[0] and content.drill_var == names[2]
    assert content.exceptions_var_name() == names[2]
    live = [o["data"].collect() for o in node.value]

    namespace = {"var_src": source.frame}
    exec(node.get_code(), {"__name__": "__main__"}, namespace)  # noqa: S102
    for name, expected in zip(names, live):
        got = namespace[name]
        got = got.collect() if isinstance(got, pl.LazyFrame) else got
        assert got.equals(expected)
    assert isinstance(namespace[names[1]], pl.DataFrame)
    table = live[0].filter(pl.col("digit").is_in([49, 94]))
    assert live[2].height == table["count"].sum()
    assert set(live[2]["benford_digits"]) == {49, 94}
    assert content.test_summary is not None  # LIVE_SUMMARY: eager
    assert content.test_summary.details["digits"] == 2
