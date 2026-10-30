"""Risk Filters core: ``run_risk_filters`` against hand-computed and planted cases."""

from __future__ import annotations

import datetime as dt

import polars as pl
import pytest

from tests.support.audit_ledger import make_ledger
from trigger_designer.core.audit.common import AuditConfigError
from trigger_designer.core.audit.risk_filters import (
    LABELS,
    TEST_IDS,
    RiskParams,
    run_risk_filters,
)

FIXTURE = pl.DataFrame(
    {
        "date": [
            "2024-03-02",
            "2024-03-04",
            "2024-12-25",
            "2024-04-03",
            "2024-03-09",
            None,
            "2024-03-05",
        ],
        "amount": [
            "5,000.00",
            "4,900",
            "1000",
            "9999.99",
            "1,000.50",
            "(2000)",
            "123.45",
        ],
        "desc": [
            "Reversal of accrual",
            "normal",
            "Plug entry",
            "x",
            "MANUAL adj",
            None,
            "lunch",
        ],
        "source": ["Manual", "Auto", "m", "AUTO", "y", None, "Auto"],
    }
)


def _all_on(**over) -> RiskParams:
    base = {
        "date_column": "date",
        "amount_column": "amount",
        "description_column": "desc",
        "manual_column": "source",
        "holidays": ["2024-12-25"],
        "approval_limits": [5000, 10000],
        "keywords": ["reversal", "plug", "manual"],
        "period_end": "2024-03-31",
        **dict.fromkeys(TEST_IDS, True),
    }
    base.update(over)
    return RiskParams(**base)


def _run(frame, params):
    result = run_risk_filters(frame, params)
    flagged, clean, summary = (f.collect() for f in result.frames)
    return flagged, clean, summary.row(0, named=True)


def _only(test: str, frame=FIXTURE, **over):
    base = {t: t == test for t in TEST_IDS}
    # Column roles the frame does not have stay unset, as a user would leave them.
    for role in (
        "date_column",
        "amount_column",
        "description_column",
        "manual_column",
    ):
        if _all_on().__dict__[role] not in frame.columns:
            base[role] = ""
    base.update(over)
    return _run(frame, _all_on(**base))


# ---- the plan's verified reference ------------------------------------------
def test_reference_fixture_scores_and_reasons() -> None:
    flagged, clean, s = _run(FIXTURE, _all_on())
    assert flagged.columns == [*FIXTURE.columns, "risk_tests", "risk_score"]
    assert flagged["risk_score"].to_list() == [4, 1, 5, 2, 3, 1]
    assert flagged["risk_tests"].to_list() == [
        "Weekend posting; Round amount; Keyword in description; Manual journal",
        "Just below approval limit",
        (
            "Public-holiday posting; Round amount; Keyword in description; "
            "Posted after period end; Manual journal"
        ),
        "Just below approval limit; Posted after period end",
        "Weekend posting; Keyword in description; Manual journal",
        "Round amount",
    ]
    assert clean.columns == FIXTURE.columns
    assert clean["date"].to_list() == ["2024-03-05"]
    assert s["population_rows"] == 7 and s["exception_rows"] == 6
    assert s["flagged_two_or_more"] == 4 and s["total_score"] == 16
    assert [s[f"n_{t}"] for t in TEST_IDS] == [2, 1, 3, 2, 3, 2, 3]
    assert s["population_value"] == pytest.approx(24023.94)
    assert s["status"] == "warn" and s["code"] is None
    assert s["message"] == "6 of 7 entries were flagged by at least one risk test."
    assert s["test_name"] == "Risk Filters"
    assert s["exception_rate"] == pytest.approx(6 / 7)


def test_summary_columns_and_dtypes() -> None:
    result = run_risk_filters(FIXTURE, _all_on())
    summary = result.frames[2].collect()
    assert summary.columns[:11] == [
        "test_name",
        "criteria",
        "parameters",
        "status",
        "code",
        "message",
        "population_rows",
        "population_value",
        "exception_rows",
        "exception_value",
        "exception_rate",
    ]
    assert summary.columns[11:] == [
        "flagged_two_or_more",
        "total_score",
        "unparseable_rows",
        *[f"n_{t}" for t in TEST_IDS],
    ]
    for name in summary.columns[11:]:
        assert summary.schema[name] == pl.Int64
    assert result.summary_index == 2 and len(result.frames) == 3


def test_criteria_sentence_lists_only_switched_on_tests_in_table_order() -> None:
    _f, _c, s = _run(
        FIXTURE,
        _all_on(
            round_multiple=1000,
            manual_values=["manual"],
            keywords=["reversal", "plug"],
        ),
    )
    assert s["criteria"] == (
        "Entries are flagged when any of these apply: posted on a Saturday or "
        "Sunday (date); posted on a listed public holiday (date; 1 date); a round "
        "amount: a whole multiple of 1,000 (amount); an amount within 2% below an "
        "approval limit (5,000, 10,000); a description containing 'reversal' and "
        "'plug'; posted after the period end 2024-03-31; a manual journal "
        "(source is one of manual)."
    )
    _f, _c, s = _only("weekend")
    assert s["criteria"].endswith("apply: posted on a Saturday or Sunday (date).")
    _f, _c, s = _only(
        "after_period_end",
        FIXTURE.with_columns(pl.col("date").alias("eff")),
        effective_date_column="eff",
    )
    assert "with an effective date on or before it (eff)" in s["criteria"]


# ---- each test in isolation -------------------------------------------------
@pytest.mark.parametrize(
    ("test", "rows"),
    [
        ("weekend", [0, 4]),
        ("holiday", [2]),
        ("round_amount", [0, 2, 5]),
        ("just_below_limit", [1, 3]),
        ("keyword", [0, 2, 4]),
        ("after_period_end", [2, 3]),
        ("manual_journal", [0, 2, 4]),
    ],
)
def test_each_test_fires_alone_on_its_own_rows(test: str, rows: list[int]) -> None:
    flagged, clean, s = _only(test)
    assert flagged["risk_tests"].unique().to_list() == [LABELS[test]]
    assert set(flagged["date"].to_list()) == {FIXTURE["date"][i] for i in rows}
    assert flagged.height == len(rows) and flagged.height + clean.height == 7
    assert s[f"n_{test}"] == len(rows)
    for other in TEST_IDS:
        if other != test:
            assert s[f"n_{other}"] is None  # a switched-off test has no count


def test_just_below_limit_boundaries() -> None:
    amounts = ["4,900", "4,899.99", "5,000", "4,999.99", "9,800", "9,799.99", "10,000"]
    frame = pl.DataFrame({"a": amounts})
    flagged, _c, _s = _run(
        frame,
        RiskParams(
            amount_column="a", just_below_limit=True, approval_limits=[5000, 10000]
        ),
    )
    assert flagged["a"].to_list() == ["4,900", "4,999.99", "9,800"]


def test_round_amount_ignores_zero_and_uses_absolute_value() -> None:
    frame = pl.DataFrame({"a": ["0", "-3000", "(2,000)", "2000.01", "1000.00", "999"]})
    flagged, _c, _s = _run(frame, RiskParams(amount_column="a", round_amount=True))
    assert flagged["a"].to_list() == ["-3000", "(2,000)", "1000.00"]
    flagged, _c, _s = _run(
        frame, RiskParams(amount_column="a", round_amount=True, round_multiple=500)
    )
    assert flagged["a"].to_list() == ["-3000", "(2,000)", "1000.00"]
    flagged, _c, _s = _run(
        frame, RiskParams(amount_column="a", round_amount=True, round_multiple=3000)
    )
    assert flagged["a"].to_list() == ["-3000"]


def test_round_amount_has_no_float_error() -> None:
    frame = pl.DataFrame({"a": ["1000000000000.00", "19.99", "0.1"]})
    flagged, _c, _s = _run(
        frame, RiskParams(amount_column="a", round_amount=True, round_multiple=1)
    )
    # 19.99 and 0.1 are not whole amounts; the large one is.
    assert flagged["a"].to_list() == ["1000000000000.00"]


def test_keywords_are_case_insensitive_literal_substrings() -> None:
    frame = pl.DataFrame({"d": ["REVERSAL of x", "a.b", "axb", "Plúg", "none", None]})
    flagged, _c, _s = _run(
        frame,
        RiskParams(description_column="d", keyword=True, keywords=["Reversal", "a.b"]),
    )
    assert flagged["d"].to_list() == ["REVERSAL of x", "a.b"]  # '.' is not a regex
    flagged, _c, _s = _run(
        frame,
        RiskParams(description_column="d", keyword=True, keywords=["PLÚG"]),
    )
    assert flagged["d"].to_list() == ["Plúg"]


def test_manual_values_are_trimmed_and_case_insensitive() -> None:
    frame = pl.DataFrame({"m": [" Manual ", "MANUAL", "auto", None, "Y"]})
    flagged, _c, _s = _run(
        frame,
        RiskParams(manual_column="m", manual_journal=True, manual_values=["manual"]),
    )
    assert flagged["m"].to_list() == [" Manual ", "MANUAL"]
    flagged, _c, _s = _run(frame, RiskParams(manual_column="m", manual_journal=True))
    assert flagged["m"].to_list() == [" Manual ", "MANUAL", "Y"]


def test_manual_column_may_be_boolean_or_number() -> None:
    frame = pl.DataFrame({"m": [True, False, None], "n": [1, 0, 1]})
    flagged, _c, _s = _run(frame, RiskParams(manual_column="m", manual_journal=True))
    assert flagged.height == 1 and flagged["m"].to_list() == [True]
    flagged, _c, _s = _run(frame, RiskParams(manual_column="n", manual_journal=True))
    assert flagged["n"].to_list() == [1, 1]


# ---- period end and effective date -----------------------------------------
def test_effective_date_refines_after_period_end() -> None:
    frame = pl.DataFrame(
        {
            "post": ["2024-04-02", "2024-04-02", "2024-03-30", "2024-04-05"],
            "eff": ["2024-03-28", "2024-04-01", "2024-03-30", None],
        }
    )
    base = {"date_column": "post", "after_period_end": True, "period_end": "2024-03-31"}
    flagged, _c, _s = _run(frame, RiskParams(**base))
    assert flagged["post"].to_list() == ["2024-04-02", "2024-04-02", "2024-04-05"]
    flagged, _c, _s = _run(frame, RiskParams(**base, effective_date_column="eff"))
    assert flagged.to_dicts() == [
        {
            "post": "2024-04-02",
            "eff": "2024-03-28",
            "risk_tests": "Posted after period end",
            "risk_score": 1,
        }
    ]


def test_posting_on_the_period_end_is_not_after_it() -> None:
    frame = pl.DataFrame({"d": ["2024-03-31", "2024-04-01"]})
    flagged, _c, _s = _only(
        "after_period_end", frame, date_column="d", period_end="2024-03-31"
    )
    assert flagged["d"].to_list() == ["2024-04-01"]


# ---- weights ----------------------------------------------------------------
def test_weights_scale_the_score_and_the_total() -> None:
    flagged, _c, s = _only("weekend", weights={"weekend": 3})
    assert flagged["risk_score"].to_list() == [3, 3]
    assert s["total_score"] == 6
    flagged, _c, _s = _run(FIXTURE, _all_on(weights={"weekend": 3, "round_amount": 10}))
    assert flagged["risk_score"].to_list() == [
        3 + 10 + 1 + 1,
        1,
        10 + 4,
        2,
        3 + 1 + 1,
        10,
    ]


def test_missing_weights_default_to_one() -> None:
    flagged, _c, _s = _only("weekend", weights={})
    assert flagged["risk_score"].to_list() == [1, 1]


# ---- dates ------------------------------------------------------------------
@pytest.mark.parametrize(
    ("fmt", "text"),
    [
        ("%Y-%m-%d", "2024-03-02"),
        ("%d/%m/%Y", "02/03/2024"),
        ("%m/%d/%Y", "03/02/2024"),
        ("%d-%m-%Y", "02-03-2024"),
        ("%Y%m%d", "20240302"),
    ],
)
def test_every_supported_date_format_reads_a_saturday(fmt: str, text: str) -> None:
    frame = pl.DataFrame({"d": [text, "garbage"]})
    flagged, _c, s = _only("weekend", frame, date_column="d", date_format=fmt)
    assert flagged["d"].to_list() == [text]
    assert s["unparseable_rows"] == 1 and s["status"] == "warn"


def test_date_and_datetime_columns_and_time_zones() -> None:
    saturday = dt.date(2024, 3, 2)
    frame = pl.DataFrame(
        {
            "date": [saturday, dt.date(2024, 3, 4)],
            "stamp": [
                dt.datetime(2024, 3, 2, 10, 0),
                dt.datetime(2024, 3, 4, 10, 0),
            ],
            "text": ["2024-03-02 14:05:00", "2024-03-04 09:00:00"],
        }
    )
    for column in ("date", "stamp", "text"):
        flagged, _c, _s = _only("weekend", frame, date_column=column)
        assert flagged.height == 1, column
    # 23:30 UTC on Friday 1 March is already Saturday 2 March in Asia/Kolkata.
    zoned = pl.DataFrame(
        {"z": [dt.datetime(2024, 3, 1, 23, 30)]},
    ).with_columns(
        pl.col("z").dt.replace_time_zone("UTC").dt.convert_time_zone("Asia/Kolkata")
    )
    flagged, _c, _s = _only("weekend", zoned, date_column="z")
    assert flagged.height == 1


def test_holiday_matches_the_calendar_date() -> None:
    frame = pl.DataFrame({"d": ["2024-12-25", "2024-12-26", "2024-12-24"]})
    flagged, _c, s = _only(
        "holiday", frame, date_column="d", holidays=["2024-12-26", "2024-12-25"]
    )
    assert flagged["d"].to_list() == ["2024-12-25", "2024-12-26"]
    assert "(d; 2 dates)" in s["criteria"]


# ---- nulls, unreadable values, edge populations -------------------------------
def test_null_cells_fire_nothing_and_are_not_unreadable() -> None:
    frame = pl.DataFrame(
        {"d": [None, None], "a": [None, None], "t": [None, None], "m": [None, None]}
    )
    flagged, clean, s = _run(
        frame,
        RiskParams(
            date_column="d",
            amount_column="a",
            description_column="t",
            manual_column="m",
            **dict.fromkeys(TEST_IDS, True),
            holidays=["2024-01-01"],
            approval_limits=[100],
            keywords=["x"],
            period_end="2024-01-31",
        ),
    )
    assert flagged.height == 0 and clean.height == 2
    assert s["unparseable_rows"] == 0 and s["status"] == "pass"
    assert s["exception_rows"] == 0 and s["total_score"] == 0


def test_unreadable_amounts_and_dates_are_counted_and_warn() -> None:
    frame = pl.DataFrame(
        {"d": ["2024-03-02", "nope", None], "a": ["abc", "inf", "1,000"]}
    )
    flagged, _c, s = _run(
        frame,
        RiskParams(date_column="d", amount_column="a", weekend=True, round_amount=True),
    )
    assert flagged.height == 2  # Saturday and 1,000; "abc" / "inf" fire nothing
    assert s["unparseable_rows"] == 3  # "nope", "abc", "inf"
    assert s["status"] == "warn" and s["exception_rows"] == 2
    # A clean run with unreadable cells downgrades pass to warn with the note.
    frame = pl.DataFrame({"a": ["abc", "1"]})
    flagged, _c, s = _run(frame, RiskParams(amount_column="a", round_amount=True))
    assert flagged.height == 0
    assert s["status"] == "warn" and s["code"] == "TD-AUDIT-102"
    assert "1 value could not be read as dates or amounts" in s["message"]


def test_empty_input_passes_with_empty_outputs() -> None:
    frame = pl.DataFrame({"d": [], "a": []}, schema={"d": pl.String, "a": pl.String})
    flagged, clean, s = _run(
        frame, RiskParams(date_column="d", amount_column="a", weekend=True)
    )
    assert flagged.height == 0 and clean.height == 0
    assert s["population_rows"] == 0 and s["exception_rows"] == 0
    assert s["exception_rate"] is None and s["status"] == "pass"
    assert s["total_score"] == 0 and s["n_weekend"] == 0


def test_single_row_and_all_flagged() -> None:
    frame = pl.DataFrame({"a": ["1000"]})
    flagged, clean, s = _run(frame, RiskParams(amount_column="a", round_amount=True))
    assert flagged.height == 1 and clean.height == 0
    assert s["exception_rate"] == 1.0 and s["population_value"] == 1000.0


def test_no_amount_column_leaves_the_values_null() -> None:
    flagged, _c, s = _only("weekend", amount_column="")
    assert flagged.height == 2
    assert s["population_value"] is None and s["exception_value"] is None


def test_flagged_and_not_flagged_partition_the_input_in_order() -> None:
    ledger = make_ledger().frame.with_row_index("pos")  # je_number repeats in places
    flagged, clean, _s = _run(ledger, _ledger_params())
    assert flagged.height + clean.height == ledger.height
    base = flagged.drop("risk_tests", "risk_score")
    assert pl.concat([base, clean]).sort("pos").equals(ledger)
    # Input order is kept within each output.
    for frame in (flagged, clean):
        assert frame["pos"].to_list() == sorted(frame["pos"].to_list())
    assert "" not in flagged["risk_tests"].to_list()
    assert flagged["risk_score"].min() >= 1


def test_a_dataframe_and_a_lazyframe_agree() -> None:
    eager = _run(FIXTURE, _all_on())
    lazy = _run(FIXTURE.lazy(), _all_on())
    assert eager[0].equals(lazy[0]) and eager[1].equals(lazy[1])
    assert eager[2] == lazy[2]


# ---- the planted ledger (plan 7.5) -------------------------------------------
def _ledger_params() -> RiskParams:
    return RiskParams(
        date_column="posting_date",
        effective_date_column="effective_date",
        amount_column="amount",
        description_column="description",
        manual_column="source",
        holidays=["2024-03-29"],
        approval_limits=[5000, 10000],
        keywords=["reversal", "plug"],
        period_end="2024-03-31",
        manual_values=["manual"],
        **dict.fromkeys(TEST_IDS, True),
    )


def test_planted_ledger_counts() -> None:
    ledger = make_ledger().frame
    flagged, clean, s = _run(ledger, _ledger_params())
    assert flagged.height == 94 and clean.height == 2319
    assert (s["population_rows"], s["exception_rows"]) == (2413, 94)
    counts = {t: s[f"n_{t}"] for t in TEST_IDS}
    assert counts == {
        "weekend": 16,
        "holiday": 4,
        "round_amount": 21,
        "just_below_limit": 13,
        "keyword": 9,
        "after_period_end": 7,
        "manual_journal": 26,
    }
    assert s["flagged_two_or_more"] == 1 and s["total_score"] == 96
    assert flagged["risk_score"].max() == 3
    top = flagged.filter(pl.col("risk_score") == 3)
    assert top["je_number"].to_list() == ["GL-000801"]
    assert top["risk_tests"].to_list() == [
        "Weekend posting; Round amount; Manual journal"
    ]
    assert s["exception_value"] == pytest.approx(7_455_480.46)
    assert s["population_value"] == pytest.approx(173_446_733.19)
    assert s["unparseable_rows"] == 0


def test_planted_rows_are_the_flagged_rows() -> None:
    ledger = make_ledger()
    flagged, _c, _s = _only(
        "after_period_end",
        ledger.frame,
        date_column="posting_date",
        effective_date_column="effective_date",
        period_end="2024-03-31",
    )
    assert flagged.height == len(ledger.planted["after_period"])
    # Without the effective date nothing in the ledger changes: all 7 post in April.
    flagged, _c, _s = _only(
        "after_period_end",
        ledger.frame,
        date_column="posting_date",
        period_end="2024-03-31",
    )
    assert flagged.height == 7


# ---- validation ----------------------------------------------------------------
def _code(frame, params) -> str:
    with pytest.raises(AuditConfigError) as info:
        run_risk_filters(frame, params)
    assert str(info.value).startswith(f"{info.value.code}: ")
    return info.value.code


@pytest.mark.parametrize(
    ("over", "code"),
    [
        (
            {
                "weekend": False,
                "holiday": False,
                "round_amount": False,
                "just_below_limit": False,
                "keyword": False,
                "after_period_end": False,
                "manual_journal": False,
            },
            "TD-AUDIT-008",
        ),
        ({"date_column": ""}, "TD-AUDIT-001"),
        ({"date_column": "gone"}, "TD-AUDIT-002"),
        ({"date_format": "%y"}, "TD-AUDIT-007"),
        ({"amount_column": ""}, "TD-AUDIT-001"),
        ({"amount_column": "gone"}, "TD-AUDIT-002"),
        ({"description_column": ""}, "TD-AUDIT-001"),
        ({"keywords": []}, "TD-AUDIT-004"),
        ({"keywords": ["  "]}, "TD-AUDIT-004"),
        ({"manual_column": ""}, "TD-AUDIT-001"),
        ({"manual_values": []}, "TD-AUDIT-004"),
        ({"holidays": []}, "TD-AUDIT-004"),
        ({"holidays": ["2024-13-01"]}, "TD-AUDIT-006"),
        ({"holidays": ["25/12/2024"]}, "TD-AUDIT-006"),
        ({"period_end": ""}, "TD-AUDIT-006"),
        ({"period_end": "2024-3-1"}, "TD-AUDIT-006"),
        ({"effective_date_column": "gone"}, "TD-AUDIT-002"),
        ({"round_multiple": 0}, "TD-AUDIT-004"),
        ({"approval_limits": []}, "TD-AUDIT-004"),
        ({"approval_limits": [5000, 0]}, "TD-AUDIT-004"),
        ({"approval_limits": [-1]}, "TD-AUDIT-004"),
        ({"below_pct": 0}, "TD-AUDIT-004"),
        ({"below_pct": 100}, "TD-AUDIT-004"),
        ({"weights": {"weekend": 0}}, "TD-AUDIT-004"),
        ({"weights": {"weekend": 11}}, "TD-AUDIT-004"),
    ],
)
def test_validation_codes(over: dict, code: str) -> None:
    assert _code(FIXTURE, _all_on(**over)) == code


def test_validation_only_checks_what_a_switched_on_test_needs() -> None:
    # Nothing about holidays, keywords or period end matters when they are off.
    p = RiskParams(date_column="date", weekend=True, holidays=["bad"], period_end="x")
    flagged, _c, _s = _run(FIXTURE, p)
    assert flagged.height == 2
    # A chosen but vanished amount column is reported even for a date-only test.
    assert (
        _code(
            FIXTURE, RiskParams(date_column="date", amount_column="gone", weekend=True)
        )
        == "TD-AUDIT-002"
    )


def test_reserved_and_nested_columns() -> None:
    for name in ("risk_tests", "risk_score"):
        assert (
            _code(FIXTURE.with_columns(pl.lit(1).alias(name)), _all_on())
            == "TD-AUDIT-005"
        )
    nested = FIXTURE.with_columns(pl.concat_list(pl.col("date")).alias("lst"))
    assert _code(nested, _all_on(date_column="lst")) == "TD-AUDIT-003"
    # A nested column nobody picked is simply carried through.
    flagged, _c, _s = _only("weekend", nested)
    assert "lst" in flagged.columns


def test_the_run_function_does_not_mutate_its_params() -> None:
    p = _all_on()
    before = p.to_dict()
    run_risk_filters(FIXTURE, p).for_run()
    assert p.to_dict() == before


def test_params_round_trip_and_unshared_defaults() -> None:
    p = _all_on(weights={"weekend": 4})
    assert RiskParams.from_dict(p.to_dict()) == p
    assert RiskParams.from_dict({"bogus": 1}) == RiskParams()
    a, b = RiskParams(), RiskParams()
    a.weights["weekend"] = 9
    a.manual_values.append("z")
    assert b.weights["weekend"] == 1 and "z" not in b.manual_values
    assert RiskParams().manual_values == ["manual", "m", "y", "yes", "true", "1"]


# ---- the node: live value, generated code, persistence ------------------------
def _node_cls():
    from trigger_designer.core.node_configuration import (
        AuditNodes,
        NodeTypes,
        get_class_from_opcode,
    )

    return get_class_from_opcode(AuditNodes.RISK_FILTERS, NodeTypes.AUDIT)


def _ready_node(frame=FIXTURE, **settings):
    from tests.support.audit_demo import demo_graph

    window, source, node = demo_graph(frame.lazy(), _node_cls())
    for name, value in settings.items():
        setattr(node.content, name, value)
    node.markDirty(True)
    node.eval()
    return window, source, node


def _configured() -> dict:
    p = _all_on()
    return {k: v for k, v in p.to_dict().items()}


def test_the_node_is_registered_with_its_sockets_and_op_id() -> None:
    cls = _node_cls()
    assert (
        cls.node_title == "Risk Filters" and cls.__name__ == "TriggerNode_RiskFilters"
    )
    _window, _source, node = _ready_node(**_configured())
    assert node.serialize()["op"] == "audit.risk_filters"
    assert [s.socket_type for s in node.outputs] == [3, 3, 1]
    assert type(node).output_text == ("F", "N", "S")
    names = node.content.output_variable_names()
    assert [n.rsplit("_", 1)[0] for n in names] == [
        "var_riskflag",
        "var_risknone",
        "var_risksum",
    ]
    assert node.content.summary_variable_name == names[2]
    assert node.content.exceptions_var_name() == names[0] == node.content.flagged_var
    assert node.content.not_flagged_var == names[1]
    assert not node.isInvalid()


def test_live_value_and_generated_code_agree() -> None:
    _window, source, node = _ready_node(**_configured())
    live = [o["data"].collect() for o in node.value]
    assert [f.height for f in live[:2]] == [6, 1]
    namespace = {"var_src": source.frame}
    exec(node.get_code(), {"__name__": "__main__"}, namespace)  # noqa: S102
    for item, expected in zip(node.value, live, strict=True):
        got = namespace[item["variable_name"]]
        got = got.collect() if isinstance(got, pl.LazyFrame) else got
        assert got.equals(expected)
    assert isinstance(namespace[node.value[2]["variable_name"]], pl.DataFrame)


def test_generated_code_imports_the_core_module() -> None:
    _window, _source, node = _ready_node(**_configured())
    assert (
        "from trigger_designer.core.audit.risk_filters import "
        "RiskParams, run_risk_filters" in node.get_code()
    )


def test_unwired_node_runs_without_name_errors() -> None:
    from trigger_designer.qt.design_window import TriggerSubWindow

    window = TriggerSubWindow()
    node = _node_cls()(window.scene)
    namespace: dict = {}
    exec(node.get_code(), {}, namespace)  # noqa: S102
    for name in node.content.output_variable_names():
        assert isinstance(namespace[name], pl.DataFrame)


def test_a_new_node_fails_with_no_test_switched_on() -> None:
    _window, source, node = _ready_node(date_column="date")
    assert node.isInvalid() and node.current_error.code == "TD-AUDIT-008"
    with pytest.raises(AuditConfigError) as info:
        exec(node.get_code(), {}, {"var_src": source.frame})  # noqa: S102
    assert info.value.code == "TD-AUDIT-008"


def test_serialized_state_round_trips_and_old_files_get_defaults() -> None:
    from trigger_designer.qt.design_window import TriggerSubWindow

    _window, _source, node = _ready_node(**_configured())
    node.content.weights = {**node.content.weights, "weekend": 4}
    data = node.content.serialize()
    assert data["weights"]["weekend"] == 4 and data["holidays"] == ["2024-12-25"]
    other = _node_cls()(TriggerSubWindow().scene)
    other.content.deserialize(dict(data))
    assert other.content.params() == node.content.params()
    other.content.deserialize({})
    assert other.content.params() == RiskParams()
    # A file written before a weight existed falls back to 1 for that test.
    other.content.deserialize({"weights": {"weekend": 3}})
    assert other.content.params().weight("holiday") == 1
