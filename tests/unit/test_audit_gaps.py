"""Gaps: the pure run function, the planted ledger gaps, and the node's Run code."""

from __future__ import annotations

import datetime as dt
import random

import polars as pl
import pytest

from tests.support.audit_demo import demo_graph
from tests.support.audit_ledger import make_ledger
from trigger_designer.core.audit.common import AuditConfigError
from trigger_designer.core.audit.gaps import GapsParams, run_gaps
from trigger_designer.core.node_configuration import (
    AuditNodes,
    NodeTypes,
    get_class_from_op,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.widgets.nodes.Audit.gaps import GapsContent, TriggerNode_Gaps

JE = [
    "JE-000001",
    "JE-000002",
    "JE-000005",
    "JE-000005",
    "JE-000004",
    "JE-000009",
    "X-0003",
    "X-0001",
    "je-7",
    "JE-000010",
]
COLS = ["prefix", "finding", "from", "to", "count", "source_row"]


def _run(frame, **settings):
    result = run_gaps(frame, GapsParams(**settings))
    gaps, summary = (f.collect() for f in result.frames)
    return gaps, summary.row(0, named=True)


def _rows(gaps: pl.DataFrame, columns=COLS) -> list[tuple]:
    return [tuple(r) for r in gaps.select(columns).iter_rows()]


# ---- plan reference cases -----------------------------------------------------
def test_reference_a_prefixed_series() -> None:
    gaps, summary = _run(pl.DataFrame({"je": JE}), sequence_column="je")
    assert gaps.columns == COLS
    assert gaps.schema["count"] == pl.Int64 and gaps.schema["source_row"] == pl.UInt32
    assert _rows(gaps) == [
        ("JE-", "duplicate", "JE-000005", "JE-000005", 2, 3),
        ("JE-", "gap", "JE-000003", "JE-000003", 1, None),
        ("JE-", "gap", "JE-000006", "JE-000008", 3, None),
        ("JE-", "out_of_order", "JE-000004", "JE-000004", 1, 5),
        ("X-", "gap", "X-0002", "X-0002", 1, None),
        ("X-", "out_of_order", "X-0001", "X-0001", 1, 8),
    ]
    assert (summary["series"], summary["gap_ranges"], summary["missing_items"]) == (
        3,
        3,
        5,
    )
    assert (summary["duplicate_values"], summary["out_of_order_rows"]) == (1, 2)
    assert (summary["exception_rows"], summary["population_rows"]) == (6, 10)
    assert summary["status"] == "fail" and summary["code"] is None
    assert summary["population_value"] is None and summary["exception_value"] is None
    assert summary["exception_rate"] == pytest.approx(0.6)
    assert summary["message"] == (
        "3 gap ranges covering 5 missing numbers; 1 repeated numbers; "
        "2 numbers out of order."
    )


def test_reference_b_number_mode_with_unreadable_values() -> None:
    values = ["1", "2", "3", "7", "8", "12", "12", "11", None, "abc"]
    gaps, summary = _run(
        pl.DataFrame({"n": values}), sequence_column="n", mode="number"
    )
    assert _rows(gaps) == [
        ("", "duplicate", "12", "12", 2, 6),
        ("", "gap", "4", "6", 3, None),
        ("", "gap", "9", "10", 2, None),
        ("", "out_of_order", "11", "11", 1, 8),
    ]
    assert summary["unparseable_rows"] == 1  # the null is not unreadable
    assert summary["status"] == "fail" and summary["code"] == "TD-AUDIT-102"
    assert summary["message"].endswith(
        " 1 value could not be read as numbers and was skipped."
    )


DATES = [
    "2024-03-01",
    "2024-03-04",
    "2024-03-05",
    "2024-03-09",
    "2024-03-15",
    None,
    "x",
]


def test_reference_c_date_mode_calendar_business_and_min_gap() -> None:
    frame = pl.DataFrame({"d": DATES})
    gaps, summary = _run(frame, sequence_column="d", mode="date")
    assert _rows(gaps) == [
        ("", "date_gap", "2024-03-02", "2024-03-03", 2, None),
        ("", "date_gap", "2024-03-06", "2024-03-08", 3, None),
        ("", "date_gap", "2024-03-10", "2024-03-14", 5, None),
    ]
    assert summary["unparseable_rows"] == 1 and summary["series"] == 1
    assert summary["population_rows"] == 7
    assert summary["message"].startswith("3 gap ranges covering 10 days.")
    assert summary["code"] == "TD-AUDIT-102"
    assert summary["message"].endswith(
        " 1 value could not be read as dates and was skipped."
    )

    business, _ = _run(frame, sequence_column="d", mode="date", business_days_only=True)
    assert _rows(business) == [
        ("", "date_gap", "2024-03-06", "2024-03-08", 3, None),
        ("", "date_gap", "2024-03-11", "2024-03-14", 4, None),
    ]
    bigger, _ = _run(frame, sequence_column="d", mode="date", min_gap_days=3)
    assert [r[4] for r in _rows(bigger)] == [3, 5]


def test_reference_d_groups_and_expected_range() -> None:
    frame = pl.DataFrame({"je": JE, "led": list("AAAAAABBBA")})
    gaps, summary = _run(
        frame,
        sequence_column="je",
        group_columns=["led"],
        range_start=1,
        range_end=11,
    )
    assert gaps.columns == ["led", *COLS]
    by_ledger = {
        (r["led"], r["from"], r["to"]): r["count"]
        for r in gaps.filter(pl.col("finding") == "gap").to_dicts()
    }
    assert by_ledger[("A", "JE-000011", "JE-000011")] == 1  # trailing gap
    assert by_ledger[("B", "je-1", "je-6")] == 6
    assert by_ledger[("B", "je-8", "je-11")] == 4
    assert by_ledger[("B", "X-0004", "X-0011")] == 8
    assert summary["series"] == 3
    # Ledger B has no JE- numbers, so no JE- range is invented for it.
    assert not [k for k in by_ledger if k[0] == "B" and k[1].startswith("JE-")]


# ---- the planted ledger gaps ------------------------------------------------------
def test_ledger_gl_and_ap_series_by_ledger() -> None:
    gaps, summary = _run(
        make_ledger().frame, sequence_column="je_number", group_columns=["ledger"]
    )
    assert gaps.height == 13
    got = [(r[0], r[2], r[3], r[4], r[5], r[6]) for r in gaps.iter_rows()]
    assert got == [
        ("GL", "duplicate", "GL-000100", "GL-000100", 2, 100),
        ("GL", "duplicate", "GL-000200", "GL-000200", 2, 200),
        ("GL", "duplicate", "GL-000300", "GL-000300", 2, 300),
        ("GL", "gap", "GL-001000", "GL-001009", 10, None),
        ("GL", "gap", "GL-001500", "GL-001500", 1, None),
        ("GL", "gap", "GL-001800", "GL-001802", 3, None),
        ("GL", "out_of_order", "GL-000100", "GL-000100", 1, 2011),
        ("GL", "out_of_order", "GL-000200", "GL-000200", 1, 2012),
        ("GL", "out_of_order", "GL-000300", "GL-000300", 1, 2013),
        ("GL", "out_of_order", "GL-001100", "GL-001100", 1, 1091),
        ("GL", "out_of_order", "GL-001200", "GL-001200", 1, 1191),
        ("GL", "out_of_order", "GL-001300", "GL-001300", 1, 1291),
        ("GL", "out_of_order", "GL-001400", "GL-001400", 1, 1391),
    ]
    assert (summary["series"], summary["gap_ranges"], summary["missing_items"]) == (
        2,
        3,
        14,
    )
    assert (summary["duplicate_values"], summary["out_of_order_rows"]) == (3, 7)
    assert (summary["exception_rows"], summary["population_rows"]) == (13, 2413)
    assert summary["status"] == "fail"


def test_ledger_series_are_separate_without_a_group_column() -> None:
    # GL- and AP- are different prefixes, so they are separate series anyway.
    gaps, summary = _run(make_ledger().frame, sequence_column="je_number")
    assert gaps.height == 13 and summary["series"] == 2


def test_ledger_date_gaps_calendar_and_business_days() -> None:
    frame = make_ledger().frame
    gaps, _ = _run(frame, sequence_column="posting_date", mode="date")
    assert _rows(gaps, ["from", "to", "count"]) == [
        ("2024-03-24", "2024-03-24", 1),
        ("2024-03-30", "2024-04-01", 3),
    ]
    business, summary = _run(
        frame, sequence_column="posting_date", mode="date", business_days_only=True
    )
    assert _rows(business, ["from", "to", "count"]) == [("2024-04-01", "2024-04-01", 1)]
    assert summary["missing_items"] == 1


# ---- properties and parsing ---------------------------------------------------------
def test_gaps_reconstruct_the_sequence() -> None:
    rng = random.Random(20260101)
    for _ in range(200):
        values = [rng.randint(1, 200) for _ in range(rng.randint(1, 40))]
        gaps, _ = _run(
            pl.DataFrame({"n": [str(v) for v in values]}),
            sequence_column="n",
            mode="number",
            report_duplicates=False,
            report_out_of_order=False,
        )
        covered = set(values)
        total = 0
        for _p, finding, start, end, count, _row in _rows(gaps):
            assert finding == "gap"
            covered |= set(range(int(start), int(end) + 1))
            total += count
        assert covered == set(range(min(values), max(values) + 1))
        assert total == (max(values) - min(values) + 1) - len(set(values))


def test_zero_padding_width_is_restored_only_for_padded_series() -> None:
    padded, _ = _run(
        pl.DataFrame({"je": ["JE-000123", "JE-000125"]}), sequence_column="je"
    )
    assert _rows(padded, ["from", "to"]) == [("JE-000124", "JE-000124")]
    plain, _ = _run(
        pl.DataFrame({"je": ["JE-9", "JE-10", "JE-12"]}), sequence_column="je"
    )
    assert _rows(plain, ["from", "to"]) == [("JE-11", "JE-11")]


def test_a_number_wider_than_the_padding_is_not_truncated() -> None:
    gaps, _ = _run(
        pl.DataFrame({"je": ["A-0098", "A-0099", "A-0101"]}), sequence_column="je"
    )
    assert _rows(gaps, ["from", "to"]) == [("A-0100", "A-0100")]
    gaps, _ = _run(pl.DataFrame({"je": ["A-0009", "A-10000"]}), sequence_column="je")
    assert _rows(gaps, ["from", "to"]) == [("A-0010", "A-9999")]


def test_separate_series_per_prefix_and_case() -> None:
    frame = pl.DataFrame({"je": ["JE-1", "JE-3", "je-1", "je-2", "je-5"]})
    gaps, summary = _run(frame, sequence_column="je")
    assert _rows(gaps, ["prefix", "from", "to"]) == [
        ("JE-", "JE-2", "JE-2"),
        ("je-", "je-3", "je-4"),
    ]
    assert summary["series"] == 2


def test_range_start_end_add_leading_and_trailing_gaps() -> None:
    frame = pl.DataFrame({"n": ["5", "6", "9"]})
    gaps, _ = _run(
        frame, sequence_column="n", mode="number", range_start=1, range_end=12
    )
    assert _rows(gaps, ["from", "to", "count"]) == [
        ("1", "4", 4),
        ("10", "12", 3),
        ("7", "8", 2),
    ]
    only_start, _ = _run(frame, sequence_column="n", mode="number", range_start=0)
    assert [r[2] for r in _rows(only_start)] == ["0", "7"]
    # A range the data already covers (or exceeds) adds nothing.
    inside, _ = _run(
        frame, sequence_column="n", mode="number", range_start=6, range_end=8
    )
    assert _rows(inside, ["from"]) == [("7",)]


def test_huge_jump_is_one_row() -> None:
    gaps, summary = _run(
        pl.DataFrame({"n": ["1", "10000000"]}), sequence_column="n", mode="number"
    )
    assert _rows(gaps, ["from", "to", "count"]) == [("2", "9999999", 9_999_998)]
    assert summary["missing_items"] == 9_999_998


def test_number_mode_reads_whole_numbers_only() -> None:
    frame = pl.DataFrame({"n": ["000123", "+124", "125.0", "126.50", "JE-9", "12e1"]})
    gaps, summary = _run(frame, sequence_column="n", mode="number")
    assert gaps.is_empty() and summary["unparseable_rows"] == 3
    assert summary["status"] == "warn" and summary["code"] == "TD-AUDIT-102"


def test_numeric_dtypes_are_read_as_text() -> None:
    ints, _ = _run(pl.DataFrame({"n": [1, 2, 5]}), sequence_column="n", mode="number")
    floats, _ = _run(
        pl.DataFrame({"n": [1.0, 2.0, 5.0]}), sequence_column="n", mode="number"
    )
    assert _rows(ints, ["from", "to"]) == _rows(floats, ["from", "to"]) == [("3", "4")]


def test_prefixed_values_without_digits_are_unreadable() -> None:
    frame = pl.DataFrame({"je": ["JE-1", "JE-3", "JE-", "INV-12-A", "  ", ""]})
    gaps, summary = _run(frame, sequence_column="je")
    assert _rows(gaps, ["from"]) == [("JE-2",)]
    assert summary["unparseable_rows"] == 2  # blank text counts as empty, not bad


def test_surrounding_spaces_are_ignored() -> None:
    gaps, _ = _run(pl.DataFrame({"je": [" JE-1 ", "JE-3"]}), sequence_column="je")
    assert _rows(gaps, ["from"]) == [("JE-2",)]


def test_an_overflowing_number_is_unreadable_not_a_crash() -> None:
    frame = pl.DataFrame({"n": ["1", "3", "99999999999999999999999"]})
    gaps, summary = _run(frame, sequence_column="n", mode="number")
    assert _rows(gaps, ["from"]) == [("2",)] and summary["unparseable_rows"] == 1


def test_report_flags_switch_findings_off() -> None:
    frame = pl.DataFrame({"je": JE})
    gaps, summary = _run(
        frame, sequence_column="je", report_duplicates=False, report_out_of_order=False
    )
    assert set(gaps["finding"]) == {"gap"} and gaps.height == 3
    assert summary["duplicate_values"] == 0 and summary["out_of_order_rows"] == 0
    assert "Also reported" not in summary["criteria"]


# ---- date mode ---------------------------------------------------------------------
def test_date_mode_groups_and_dtypes() -> None:
    frame = pl.DataFrame(
        {
            "d": [
                dt.date(2024, 1, 1),
                dt.date(2024, 1, 4),
                dt.date(2024, 1, 1),
                dt.date(2024, 1, 2),
            ],
            "g": ["A", "A", "B", "B"],
        }
    )
    gaps, summary = _run(frame, sequence_column="d", mode="date", group_columns=["g"])
    assert _rows(gaps, ["g", "from", "to", "count"]) == [
        ("A", "2024-01-02", "2024-01-03", 2)
    ]
    assert summary["series"] == 2


def test_date_mode_datetime_uses_its_own_calendar_date_and_formats() -> None:
    frame = pl.DataFrame(
        {
            "d": [
                dt.datetime(2024, 1, 1, 23, 30),
                dt.datetime(2024, 1, 1, 1, 0),
                dt.datetime(2024, 1, 3, 9, 0),
            ]
        }
    )
    gaps, _ = _run(frame, sequence_column="d", mode="date")
    assert _rows(gaps, ["from", "to"]) == [("2024-01-02", "2024-01-02")]
    text = pl.DataFrame({"d": ["01/03/2024", "05/03/2024"]})
    gaps, _ = _run(text, sequence_column="d", mode="date", date_format="%d/%m/%Y")
    assert _rows(gaps, ["from", "to", "count"]) == [("2024-03-02", "2024-03-04", 3)]


def test_business_days_holidays_and_weekend_only_gaps() -> None:
    # Fri 1st .. Mon 11th: Sat/Sun 2-3 (weekend only), then Mon 4 .. Fri 8 empty.
    frame = pl.DataFrame({"d": ["2024-03-01", "2024-03-04", "2024-03-11"]})
    plain, _ = _run(frame, sequence_column="d", mode="date", business_days_only=True)
    assert _rows(plain, ["from", "to", "count"]) == [("2024-03-05", "2024-03-08", 4)]
    holiday, summary = _run(
        frame,
        sequence_column="d",
        mode="date",
        business_days_only=True,
        holidays=["2024-03-06"],
    )
    assert _rows(holiday, ["from", "to", "count"]) == [("2024-03-05", "2024-03-08", 3)]
    assert "holidays" in summary["criteria"]
    # A gap that is only holidays and weekend vanishes.
    only, _ = _run(
        pl.DataFrame({"d": ["2024-03-08", "2024-03-12"]}),
        sequence_column="d",
        mode="date",
        business_days_only=True,
        holidays=["2024-03-11"],
    )
    assert only.is_empty()


# ---- edge cases -----------------------------------------------------------------------
def test_population_0_1_and_identical_values() -> None:
    empty = pl.DataFrame({"je": []}, schema={"je": pl.String})
    gaps, summary = _run(empty, sequence_column="je")
    assert gaps.is_empty() and gaps.columns == COLS
    assert summary["population_rows"] == 0 and summary["series"] == 0
    assert summary["exception_rate"] is None and summary["status"] == "pass"
    assert summary["message"].startswith("0 gap ranges covering 0 missing")

    one, summary = _run(pl.DataFrame({"je": ["JE-5"]}), sequence_column="je")
    assert one.is_empty() and summary["status"] == "pass" and summary["series"] == 1

    same, summary = _run(pl.DataFrame({"je": ["JE-5"] * 4}), sequence_column="je")
    assert _rows(same, ["finding", "count", "source_row"]) == [("duplicate", 4, 1)]
    assert summary["gap_ranges"] == 0 and summary["exception_rows"] == 1

    dates, summary = _run(
        pl.DataFrame({"d": [None, None]}, schema={"d": pl.String}),
        sequence_column="d",
        mode="date",
    )
    assert dates.is_empty() and summary["series"] == 0
    assert summary["unparseable_rows"] == 0 and summary["status"] == "pass"


def test_null_group_values_form_their_own_series() -> None:
    frame = pl.DataFrame({"n": ["1", "3", "1", "4"], "g": ["A", "A", None, None]})
    gaps, _ = _run(frame, sequence_column="n", mode="number", group_columns=["g"])
    assert gaps.select("g", "from", "to").rows() == [
        ("A", "2", "2"),
        (None, "2", "3"),
    ]


def test_input_order_decides_out_of_order() -> None:
    ascending, _ = _run(
        pl.DataFrame({"n": ["1", "2", "3"]}), sequence_column="n", mode="number"
    )
    descending, summary = _run(
        pl.DataFrame({"n": ["3", "2", "1"]}), sequence_column="n", mode="number"
    )
    assert ascending.is_empty()
    assert summary["out_of_order_rows"] == 2 and summary["gap_ranges"] == 0
    assert _rows(descending, ["from", "source_row"]) == [("1", 3), ("2", 2)]


def test_the_input_is_not_modified_and_unrelated_columns_are_free() -> None:
    frame = pl.DataFrame({"je": JE, "count": range(10), "from": range(10)})
    before = frame.clone()
    gaps, _ = _run(frame, sequence_column="je")
    assert frame.equals(before) and gaps.height == 6


# ---- validation ----------------------------------------------------------------------
@pytest.mark.parametrize(
    ("settings", "code"),
    [
        ({}, "TD-AUDIT-001"),
        ({"sequence_column": "gone"}, "TD-AUDIT-002"),
        ({"sequence_column": "nested"}, "TD-AUDIT-003"),
        ({"sequence_column": "je", "group_columns": ["gone"]}, "TD-AUDIT-002"),
        ({"sequence_column": "je", "mode": "weird"}, "TD-AUDIT-004"),
        ({"sequence_column": "je", "range_start": -1}, "TD-AUDIT-004"),
        ({"sequence_column": "je", "range_end": -5}, "TD-AUDIT-004"),
        ({"sequence_column": "je", "range_start": 9, "range_end": 3}, "TD-AUDIT-004"),
        (
            {"sequence_column": "je", "mode": "date", "date_format": "%Y/%m"},
            "TD-AUDIT-007",
        ),
        ({"sequence_column": "je", "mode": "date", "min_gap_days": 0}, "TD-AUDIT-004"),
        (
            {"sequence_column": "je", "mode": "date", "holidays": ["tomorrow"]},
            "TD-AUDIT-004",
        ),
        ({"sequence_column": "je", "group_columns": ["count"]}, "TD-AUDIT-005"),
    ],
)
def test_validation_codes(settings, code) -> None:
    frame = pl.DataFrame(
        {"je": ["JE-1"], "count": [1], "nested": [[1]]},
    )
    with pytest.raises(AuditConfigError) as info:
        run_gaps(frame, GapsParams(**settings))
    assert info.value.code == code
    assert str(info.value).startswith(f"{code}: ")


def test_reserved_internal_column_is_refused() -> None:
    with pytest.raises(AuditConfigError) as info:
        run_gaps(
            pl.DataFrame({"je": ["JE-1"], "__td_row": [1]}),
            GapsParams(sequence_column="je"),
        )
    assert info.value.code == "TD-AUDIT-005"


def test_range_checks_do_not_apply_to_date_mode() -> None:
    gaps, _ = _run(
        pl.DataFrame({"d": ["2024-01-01"]}),
        sequence_column="d",
        mode="date",
        range_start=-5,
    )
    assert gaps.is_empty()


def test_params_round_trip_and_defaults() -> None:
    params = GapsParams(
        sequence_column="x", group_columns=["a"], range_start=3, holidays=["2024-01-01"]
    )
    assert GapsParams.from_dict(params.to_dict()) == params
    assert GapsParams.from_dict({"unknown": 1}) == GapsParams()
    assert GapsParams().group_columns is not GapsParams().group_columns


def test_criteria_sentences() -> None:
    def criteria(**settings) -> str:
        return _run(pl.DataFrame({"je": ["JE-1"]}), sequence_column="je", **settings)[
            1
        ]["criteria"]

    base = criteria()
    assert base.startswith("je is read as a prefix followed by digits")
    assert "separately" not in base
    grouped = criteria(group_columns=["je"])  # grouping by the column itself is legal
    assert "reported separately for each je." in grouped
    assert "a whole number" in criteria(mode="number")
    assert "Saturdays and Sundays" in criteria(mode="date", business_days_only=True)


# ---- the node: live frames and generated code agree -----------------------------------
def _graph(frame, **settings):
    window, source, node = demo_graph(frame, TriggerNode_Gaps)
    for name, value in settings.items():
        setattr(node.content, name, value)
    node.markDirty(True)
    node.eval()
    return window, source, node


def test_live_value_and_generated_code_agree() -> None:
    frame = pl.DataFrame({"je": JE, "led": list("AAAAAABBBA")}).lazy()
    _window, source, node = _graph(
        frame, sequence_column="je", group_columns=["led"], range_start=1
    )
    out = node.value
    assert [o["variable_name"] for o in out] == [
        f"var_gaps_{node.content.id}",
        f"var_gapsum_{node.content.id}",
    ]
    live = [o["data"].collect() for o in out]
    namespace = {"var_src": source.frame}
    exec(node.get_code(), {"__name__": "__main__"}, namespace)  # noqa: S102
    for item, expected in zip(out, live):
        got = namespace[item["variable_name"]]
        got = got.collect() if isinstance(got, pl.LazyFrame) else got
        assert got.equals(expected)
    assert isinstance(namespace[out[1]["variable_name"]], pl.DataFrame)
    assert live[1].row(0, named=True)["exception_rows"] == live[0].height
    assert "from trigger_designer.core.audit.gaps import GapsParams, run_gaps" in (
        node.get_code()
    )


def test_unwired_node_defines_both_outputs_and_misconfigured_node_raises() -> None:
    window = TriggerSubWindow()
    node = TriggerNode_Gaps(window.scene)
    namespace: dict = {}
    exec(node.get_code(), {}, namespace)  # noqa: S102
    for name in node.content.output_variable_names():
        assert isinstance(namespace[name], pl.DataFrame)

    _window, source, wired = _graph(pl.DataFrame({"je": JE}).lazy())  # no column
    assert wired.isInvalid() and wired.current_error.code == "TD-AUDIT-001"
    assert "TD-AUDIT-001" in wired._node_tooltip()
    with pytest.raises(AuditConfigError) as info:
        exec(wired.get_code(), {}, {"var_src": source.frame})  # noqa: S102
    assert info.value.code == "TD-AUDIT-001"


def test_op_id_title_and_sockets() -> None:
    _window, _source, node = _graph(
        pl.DataFrame({"je": JE}).lazy(), sequence_column="je"
    )
    assert node.serialize()["op"] == "audit.gaps"
    assert get_class_from_op("audit.gaps") is TriggerNode_Gaps
    assert get_class_from_opcode(AuditNodes.GAPS, NodeTypes.AUDIT) is TriggerNode_Gaps
    assert [s.socket_type for s in node.outputs] == [3, 1]
    assert tuple(node.output_text) == ("G", "S") and node.node_title == "Gaps"
    content = node.content
    assert content.exceptions_var_name() == f"var_gaps_{content.id}"
    assert content.summary_variable_name == f"var_gapsum_{content.id}"
    assert isinstance(content, GapsContent)
    declared = _window._declared_output_variable_names(node)
    assert declared == content.output_variable_names()


def test_after_execution_builds_the_test_summary() -> None:
    _window, _source, node = _graph(
        pl.DataFrame({"je": JE}).lazy(), sequence_column="je"
    )
    content = node.content
    content.after_execution(
        {content.summary_variable_name: node.value[1]["data"].collect()}
    )
    summary = content.test_summary
    assert summary.test_id == f"audit.gaps#{node.id}"
    assert summary.exceptions_var == content.output_variable_names()[0]
    assert summary.exception_rows == 6 and summary.status == "fail"
    assert summary.details["gap_ranges"] == 3
    assert summary.parameters["sequence_column"] == "je"


def test_state_round_trips_through_serialize() -> None:
    _window, _source, node = _graph(pl.DataFrame({"je": JE}).lazy())
    content = node.content
    content.sequence_column = "je"
    content.mode = "date"
    content.group_columns = ["led"]
    content.range_start = 3
    content.min_gap_days = 4
    content.business_days_only = True
    content.holidays = ["2024-03-29"]
    data = content.serialize()
    other = TriggerNode_Gaps(TriggerSubWindow().scene)
    other.content.deserialize(dict(data))
    assert other.content.params() == content.params()
    other.content.deserialize({})
    assert other.content.params() == GapsParams()
