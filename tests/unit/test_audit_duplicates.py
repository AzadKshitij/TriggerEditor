"""Duplicates audit test: core logic, edge cases, error codes and the node's codegen.

Expected values are the hand-checked references of docs/plan/04-audit-test-nodes.md
section 4.1 and the planted cases of the synthetic ledger.
"""

from __future__ import annotations

import datetime as dt
import random
import subprocess
import sys
from collections import Counter

import polars as pl
import pytest

from tests.support.audit_demo import demo_graph
from tests.support.audit_ledger import make_ledger
from trigger_designer.core.audit.common import BASE_SUMMARY, AuditConfigError
from trigger_designer.core.audit.duplicates import (
    DuplicatesParams,
    criteria_text,
    run_duplicates,
)
from trigger_designer.core.node_configuration import (
    AuditNodes,
    NodeTypes,
    get_class_from_op,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.widgets.nodes.Audit.duplicates import TriggerNode_Duplicates


def _d(month: int, day: int) -> dt.date:
    return dt.date(2024, month, day)


REFERENCE = pl.DataFrame(
    {
        "vendor": ["A", "A", "A", "B", "B", "A", None, None, "a ", "C"],
        "inv": [1, 1, 1, 7, 7, 2, 9, 9, 1, 5],
        "amt": [
            "100.00",
            "100.00",
            "100.40",
            "50",
            "50.00",
            "(25)",
            "5",
            "5",
            "100",
            "oops",
        ],
        "date": [
            _d(1, 1),
            _d(1, 2),
            _d(1, 20),
            _d(2, 1),
            _d(2, 1),
            _d(3, 1),
            _d(3, 1),
            _d(3, 1),
            _d(1, 1),
            _d(1, 1),
        ],
    }
)
KEYS = ["vendor", "inv"]


def _run(frame, **settings):
    """``(duplicates, unique, summary row)`` as eager frames / a dict."""
    settings.setdefault("key_columns", KEYS)
    result = run_duplicates(frame, DuplicatesParams(**settings))
    dups, unique, summary = (f.collect() for f in result.frames)
    return dups, unique, summary.row(0, named=True)


# ---- the 4.1 reference table ------------------------------------------------
def test_exact_reference() -> None:
    dups, unique, s = _run(REFERENCE)
    assert dups["dup_count"].to_list() == [3, 3, 3, 2, 2]
    assert dups["dup_group_id"].to_list() == [1, 1, 1, 2, 2]
    assert dups["amt"].to_list()[:2] == ["100.00", "100.00"]
    assert unique.height == 5 and unique.columns == REFERENCE.columns
    assert unique["inv"].to_list() == [2, 9, 9, 1, 5]  # input order, rows 5-9
    assert (s["population_rows"], s["exception_rows"], s["groups"]) == (10, 5, 2)
    assert (s["skipped_rows"], s["unparseable_rows"]) == (2, 0)
    assert s["status"] == "fail" and s["code"] is None
    assert s["message"] == "5 of 10 rows are in 2 duplicate groups."
    assert s["exception_rate"] == 0.5
    assert s["population_value"] is None and s["exception_value"] is None
    assert s["test_name"] == "Duplicates"


def test_exact_ignore_case_joins_the_trimmed_lowercase_row() -> None:
    dups, unique, s = _run(REFERENCE, ignore_case=True)
    assert dups["dup_count"].to_list() == [4, 4, 4, 4, 2, 2]
    assert dups["dup_group_id"].to_list() == [1, 1, 1, 1, 2, 2]
    assert dups["vendor"].to_list()[3] == "a "  # original text, not the key
    assert unique.height == 4
    assert s["exception_rows"] == 6 and s["groups"] == 2


def test_near_amount_and_window_reference() -> None:
    dups, unique, s = _run(
        REFERENCE,
        mode="near",
        amount_column="amt",
        tolerance=0.5,
        date_column="date",
        window_days=3,
    )
    assert dups["dup_count"].to_list() == [2, 2, 2, 2]
    assert dups["dup_group_id"].to_list() == [1, 1, 2, 2]
    assert unique.height == 6
    assert (s["exception_rows"], s["groups"], s["skipped_rows"]) == (4, 2, 3)
    assert s["unparseable_rows"] == 1
    assert s["status"] == "fail" and s["code"] == "TD-AUDIT-102"
    assert s["message"].endswith(
        " 1 value could not be read as numbers or dates and was skipped."
    )
    assert s["message"].startswith("4 of 10 rows are in 2 duplicate groups.")


def test_near_percent_without_date_reference() -> None:
    dups, unique, s = _run(
        REFERENCE,
        mode="near",
        amount_column="amt",
        tolerance_kind="percent",
        tolerance=1,
    )
    assert dups["dup_count"].to_list() == [3, 3, 3, 2, 2]
    assert dups["dup_group_id"].to_list() == [1, 1, 1, 2, 2]
    assert unique.height == 5
    assert s["population_value"] == pytest.approx(535.4)
    assert s["exception_value"] == pytest.approx(400.4)


def test_near_date_only_groups_by_window() -> None:
    dups, _unique, s = _run(REFERENCE, mode="near", date_column="date", window_days=3)
    # rows 0,1 (A,1) 1 day apart; row 2 is 18 days later; B pair same day.
    assert dups["dup_count"].to_list() == [2, 2, 2, 2]
    assert s["unparseable_rows"] == 0 and s["status"] == "fail" and s["code"] is None


def test_value_column_drives_the_summary_values() -> None:
    frame = pl.DataFrame(
        {"k": ["a", "a", "b"], "v": ["10", "(20)", "5"], "other": [1.0, 2.0, 4.0]}
    )
    _d1, _u, s = _run(frame, key_columns=["k"], value_column="v")
    assert s["population_value"] == 35.0 and s["exception_value"] == 30.0
    _d2, _u, s = _run(frame, key_columns=["k"], value_column="other")
    assert s["population_value"] == 7.0 and s["exception_value"] == 3.0
    # Near mode falls back to the amount column when no value column is set.
    _d3, _u, s = _run(
        frame, key_columns=["k"], mode="near", amount_column="other", tolerance=5
    )
    assert s["population_value"] == 7.0 and s["exception_value"] == 3.0


# ---- the synthetic ledger ---------------------------------------------------
def test_ledger_exact_flags_36_rows_in_17_groups() -> None:
    frame = make_ledger().frame
    dups, unique, s = _run(frame, key_columns=["vendor", "invoice_no", "amount"])
    assert dups.height == 36 and unique.height == 2377
    assert dups["dup_group_id"].n_unique() == 17 and s["groups"] == 17
    assert s["population_rows"] == 2413 and s["status"] == "fail"
    sizes = Counter(dups["dup_group_id"].to_list())
    assert dups["dup_count"].to_list() == [
        sizes[g] for g in dups["dup_group_id"].to_list()
    ]
    assert sorted(Counter(sizes.values()).items()) == [(2, 15), (3, 2)]


def test_ledger_near_flags_46_rows_in_22_groups() -> None:
    frame = make_ledger().frame
    dups, unique, s = _run(
        frame,
        key_columns=["vendor", "invoice_no"],
        mode="near",
        amount_column="amount",
        tolerance=0.5,
        date_column="posting_date",
        window_days=3,
    )
    assert dups.height == 46 and unique.height == 2367
    assert dups["dup_group_id"].n_unique() == 22 and s["groups"] == 22
    assert s["unparseable_rows"] == 0 and s["code"] is None


# ---- group ids, partitions and boundaries -----------------------------------
def test_ids_are_dense_and_ordered_by_first_appearance() -> None:
    frame = pl.DataFrame({"k": ["x", "y", "z", "y", "x", "z", "z", "q"]})
    dups, unique, _s = _run(frame, key_columns=["k"])
    assert dups["k"].to_list() == ["x", "x", "y", "y", "z", "z", "z"]
    assert dups["dup_group_id"].to_list() == [1, 1, 2, 2, 3, 3, 3]
    assert unique["k"].to_list() == ["q"]
    assert (
        dups["dup_group_id"].dtype == pl.Int64 and dups["dup_count"].dtype == pl.Int64
    )


def test_unique_plus_duplicates_partition_the_input() -> None:
    rng = random.Random(20260101)
    for _ in range(200):
        n = rng.randint(1, 30)
        frame = pl.DataFrame(
            {
                "i": list(range(n)),
                "k": [rng.choice(["a", "b", "c", "d", None]) for _ in range(n)],
                "m": [rng.randint(1, 2) for _ in range(n)],
            }
        )
        dups, unique, s = _run(frame, key_columns=["k", "m"])
        assert dups.height + unique.height == n == s["population_rows"]
        assert set(dups["i"]).isdisjoint(unique["i"])
        assert unique["i"].to_list() == sorted(unique["i"].to_list())
        counts = Counter(
            (k, m)
            for k, m in zip(frame["k"], frame["m"])
            if k is not None  # null key part is never evidence
        )
        for row in dups.iter_rows(named=True):
            assert row["dup_count"] == counts[(row["k"], row["m"])] >= 2
        assert dups["dup_group_id"].n_unique() == s["groups"]
        assert sorted(set(dups["dup_group_id"])) == list(range(1, s["groups"] + 1))


def _amounts(values):
    return pl.DataFrame({"k": ["x"] * len(values), "a": values})


def test_near_tolerance_boundary() -> None:
    near = {"key_columns": ["k"], "mode": "near", "amount_column": "a"}
    for values, tol, kind, grouped in (
        (["100.00", "100.50"], 0.5, "absolute", True),
        (["100.00", "100.51"], 0.5, "absolute", False),
        (["100", "101"], 1, "percent", True),
        (["100", "101.1"], 1, "percent", False),
        (["0.1", "0.3"], 0.2, "absolute", True),  # float noise (0.3 - 0.1)
    ):
        _d, _u, s = _run(_amounts(values), tolerance=tol, tolerance_kind=kind, **near)
        assert (s["exception_rows"] == 2) is grouped, (values, tol, kind)


def test_near_zero_tolerance_means_equal_amounts() -> None:
    _d, _u, s = _run(
        _amounts(["5", "5.00", "5.01"]),
        key_columns=["k"],
        mode="near",
        amount_column="a",
    )
    assert s["exception_rows"] == 2 and s["groups"] == 1


def test_near_window_boundary_and_chaining() -> None:
    base = dt.date(2024, 5, 1)

    def frame(*offsets):
        return pl.DataFrame(
            {
                "k": ["x"] * len(offsets),
                "d": [base + dt.timedelta(days=o) for o in offsets],
            }
        )

    near = {"key_columns": ["k"], "mode": "near", "date_column": "d", "window_days": 3}
    assert _run(frame(0, 3), **near)[2]["exception_rows"] == 2
    assert _run(frame(0, 4), **near)[2]["exception_rows"] == 0
    chain, _u, s = _run(frame(0, 3, 6), **near)  # documented chaining
    assert chain["dup_count"].to_list() == [3, 3, 3] and s["groups"] == 1
    # Both thresholds must hold: a close date with a far amount is not a pair.
    both = pl.DataFrame({"k": ["x", "x"], "d": [base, base], "a": ["1", "50"]})
    _d, _u, s = _run(both, **near, amount_column="a", tolerance=1)
    assert s["exception_rows"] == 0


def test_near_groups_do_not_cross_keys() -> None:
    frame = pl.DataFrame(
        {"k": ["x", "y", "x", "y"], "a": ["10", "10", "10", "10"], "i": [0, 1, 2, 3]}
    )
    dups, _u, s = _run(
        frame, key_columns=["k"], mode="near", amount_column="a", tolerance=0.1
    )
    assert s["groups"] == 2
    by_group = dups.group_by("dup_group_id").agg(pl.col("k").n_unique())
    assert by_group["k"].to_list() == [1, 1]


def test_trim_and_ignore_case_flags() -> None:
    frame = pl.DataFrame({"k": ["Ab", "Ab ", " ab", "AB"]})
    assert _run(frame, key_columns=["k"], trim_text=False)[2]["exception_rows"] == 0
    assert _run(frame, key_columns=["k"])[2]["exception_rows"] == 2  # "Ab", "Ab "
    assert _run(frame, key_columns=["k"], ignore_case=True)[2]["exception_rows"] == 4
    assert (
        _run(frame, key_columns=["k"], trim_text=False, ignore_case=True)[2][
            "exception_rows"
        ]
        == 2  # "Ab" and "AB" only: the padded rows differ
    )


def test_unreadable_and_null_keys() -> None:
    frame = pl.DataFrame(
        {
            "k": ["a", "a", None, None, "b", "b"],
            "a": ["1", "1", "1", "1", "x", None],
        }
    )
    _d, _u, s = _run(frame, key_columns=["k"])  # exact: only null keys are skipped
    assert s["exception_rows"] == 4 and s["skipped_rows"] == 2
    assert s["unparseable_rows"] == 0 and s["status"] == "fail"
    dups, _u, s = _run(
        frame, key_columns=["k"], mode="near", amount_column="a", tolerance=0
    )
    assert dups.height == 2  # the a rows; b has "x" (unreadable) and None (null)
    assert s["skipped_rows"] == 4 and s["unparseable_rows"] == 1
    clean = frame.head(2)
    _d, _u, s = _run(clean, key_columns=["k"], mode="near", amount_column="a")
    assert s["status"] == "fail"
    only_bad = pl.DataFrame({"k": ["a", "b"], "a": ["x", "y"]})
    _d, _u, s = _run(only_bad, key_columns=["k"], mode="near", amount_column="a")
    assert s["status"] == "warn" and s["code"] == "TD-AUDIT-102"
    assert s["exception_rows"] == 0 and s["unparseable_rows"] == 2


def test_nan_and_infinite_amounts_are_unreadable() -> None:
    frame = pl.DataFrame({"k": ["a", "a", "a"], "a": [float("nan"), 1.0, float("inf")]})
    _d, _u, s = _run(frame, key_columns=["k"], mode="near", amount_column="a")
    assert s["unparseable_rows"] == 2 and s["exception_rows"] == 0


def test_dates_as_text_datetimes_and_formats() -> None:
    text = pl.DataFrame({"k": ["a", "a"], "d": ["03/04/2024", "04/04/2024 09:00:00"]})
    params = {
        "key_columns": ["k"],
        "mode": "near",
        "date_column": "d",
        "window_days": 1,
    }
    assert _run(text, date_format="%d/%m/%Y", **params)[2]["exception_rows"] == 2
    _d, _u, s = _run(text, **params)  # wrong format: both unreadable
    assert s["unparseable_rows"] == 2 and s["exception_rows"] == 0
    stamps = pl.DataFrame(
        {
            "k": ["a", "a"],
            "d": [
                dt.datetime(2024, 3, 2, 23, 0, tzinfo=dt.UTC),
                dt.datetime(2024, 3, 3, 1, 0, tzinfo=dt.UTC),
            ],
        }
    )
    assert _run(stamps, **params)[2]["exception_rows"] == 2


def test_non_text_keys_are_compared_as_text() -> None:
    frame = pl.DataFrame({"k": [1, 1, 2], "b": [True, True, False]})
    assert _run(frame, key_columns=["k", "b"])[2]["exception_rows"] == 2


def test_identical_rows_make_one_group() -> None:
    frame = pl.DataFrame({"k": ["z"] * 6})
    dups, unique, s = _run(frame, key_columns=["k"])
    assert dups["dup_count"].to_list() == [6] * 6 and unique.height == 0
    assert s["groups"] == 1 and s["message"] == "6 of 6 rows are in 1 duplicate group."


def test_population_0_and_1() -> None:
    empty = pl.DataFrame({"k": pl.Series([], dtype=pl.String)})
    for settings in ({}, {"mode": "near", "amount_column": "k"}):
        dups, unique, s = _run(empty, key_columns=["k"], **settings)
        assert dups.height == 0 and unique.height == 0
        assert s["population_rows"] == 0 and s["exception_rows"] == 0
        assert s["exception_rate"] is None and s["status"] == "pass"
        assert s["groups"] == 0 and s["skipped_rows"] == 0
    one = pl.DataFrame({"k": ["a"]})
    dups, unique, s = _run(one, key_columns=["k"])
    assert dups.height == 0 and unique.height == 1 and s["status"] == "pass"
    assert dups.columns == ["k", "dup_group_id", "dup_count"]


def test_summary_columns_and_dtypes() -> None:
    result = run_duplicates(REFERENCE, DuplicatesParams(key_columns=KEYS))
    assert result.summary_index == 2 and len(result.frames) == 3
    summary = result.frames[2].collect()
    assert summary.columns == [
        *BASE_SUMMARY,
        "groups",
        "skipped_rows",
        "unparseable_rows",
    ]
    for name in ("groups", "skipped_rows", "unparseable_rows", "population_rows"):
        assert summary.schema[name] == pl.Int64
    assert summary.schema["population_value"] == pl.Float64
    assert summary.schema["exception_rate"] == pl.Float64
    assert summary.height == 1
    dups = result.frames[0].collect()
    assert dups.columns == [*REFERENCE.columns, "dup_group_id", "dup_count"]
    assert result.for_run()[2].height == 1  # collected eagerly for Run


def test_lazy_input_gives_the_same_result() -> None:
    eager = _run(REFERENCE)
    lazy = _run(REFERENCE.lazy())
    assert eager[0].equals(lazy[0]) and eager[1].equals(lazy[1])
    assert eager[2] == lazy[2]


def test_criteria_sentences() -> None:
    p = DuplicatesParams(key_columns=["vendor", "invoice_no", "amount"])
    assert criteria_text(p) == (
        "Rows with the same vendor, invoice_no and amount are duplicates "
        "(spaces around text trimmed, case-sensitive)."
    )
    p = DuplicatesParams(key_columns=["a"], trim_text=False, ignore_case=True)
    assert criteria_text(p) == (
        "Rows with the same a are duplicates (upper/lower case ignored)."
    )
    p = DuplicatesParams(
        key_columns=["vendor", "invoice_no"],
        mode="near",
        amount_column="amount",
        tolerance=0.5,
        date_column="posting_date",
        window_days=3,
    )
    assert criteria_text(p) == (
        "Rows with the same vendor and invoice_no whose amount differs by at most "
        "0.50 and whose posting_date differs by at most 3 days are near-duplicates "
        "(spaces around text trimmed, case-sensitive)."
    )
    p = DuplicatesParams(
        key_columns=["k"],
        mode="near",
        amount_column="a",
        tolerance_kind="percent",
        tolerance=1.5,
    )
    assert "differs by at most 1.5%" in criteria_text(p)
    assert "date" not in criteria_text(p)


# ---- validation ---------------------------------------------------------------
def _code(frame, **settings) -> str:
    settings.setdefault("key_columns", KEYS)
    with pytest.raises(AuditConfigError) as info:
        run_duplicates(frame, DuplicatesParams(**settings))
    assert str(info.value).startswith(info.value.code + ": ")
    return info.value.code


def test_validation_codes() -> None:
    assert _code(REFERENCE, key_columns=[]) == "TD-AUDIT-001"
    assert _code(REFERENCE, key_columns=["vendor", "gone"]) == "TD-AUDIT-002"
    nested = pl.DataFrame({"k": [[1], [2]]})
    assert _code(nested, key_columns=["k"]) == "TD-AUDIT-003"
    assert _code(REFERENCE, mode="near") == "TD-AUDIT-001"
    assert _code(REFERENCE, mode="near", amount_column="gone") == "TD-AUDIT-002"
    assert _code(REFERENCE, mode="near", date_column="gone") == "TD-AUDIT-002"
    assert _code(REFERENCE, value_column="gone") == "TD-AUDIT-002"
    near = {"mode": "near", "amount_column": "amt"}
    assert _code(REFERENCE, tolerance=-0.1, **near) == "TD-AUDIT-004"
    assert _code(REFERENCE, tolerance=float("nan"), **near) == "TD-AUDIT-004"
    assert _code(REFERENCE, window_days=-1, **near) == "TD-AUDIT-004"
    assert _code(REFERENCE, tolerance_kind="ratio", **near) == "TD-AUDIT-004"
    assert _code(REFERENCE, mode="fuzzy") == "TD-AUDIT-004"
    assert _code(REFERENCE, date_format="%b %d", mode="near", date_column="date") == (
        "TD-AUDIT-007"
    )


def test_validation_messages_name_the_problem() -> None:
    with pytest.raises(AuditConfigError, match="Choose the key column"):
        run_duplicates(REFERENCE, DuplicatesParams())
    with pytest.raises(AuditConfigError, match="amount column or the date column"):
        run_duplicates(REFERENCE, DuplicatesParams(key_columns=KEYS, mode="near"))
    with pytest.raises(AuditConfigError, match="Tolerance must be 0 or more"):
        run_duplicates(
            REFERENCE,
            DuplicatesParams(
                key_columns=KEYS, mode="near", amount_column="amt", tolerance=-1
            ),
        )
    with pytest.raises(AuditConfigError, match="Window must be 0 days or more"):
        run_duplicates(
            REFERENCE,
            DuplicatesParams(
                key_columns=KEYS, mode="near", date_column="date", window_days=-2
            ),
        )


def test_near_columns_are_ignored_in_exact_mode() -> None:
    # A stale hidden amount column must not break an exact run.
    _d, _u, s = _run(REFERENCE, amount_column="gone", date_column="gone")
    assert s["exception_rows"] == 5


def test_reserved_column_error() -> None:
    for name in ("dup_group_id", "dup_count", "__td_row", "__td_anything"):
        frame = pl.DataFrame({"k": ["a", "a"], name: [1, 2]})
        assert _code(frame, key_columns=["k"]) == "TD-AUDIT-005"
        with pytest.raises(AuditConfigError) as info:
            run_duplicates(frame, DuplicatesParams(key_columns=["k"]))
        assert info.value.columns == (name,)


def test_core_module_imports_no_qt() -> None:
    code = (
        "import sys; import trigger_designer.core.audit.duplicates;"
        "bad = [m for m in sys.modules if m.split('.')[0] in "
        "('qtpy', 'PyQt6', 'PyQt5', 'PySide6')]; sys.exit(1 if bad else 0)"
    )
    done = subprocess.run([sys.executable, "-I", "-c", code], check=False)
    assert done.returncode == 0


# ---- the node: live value, generated code, persistence ------------------------
SOURCE = REFERENCE.lazy()


def _node(**settings):
    window, source, node = demo_graph(SOURCE, TriggerNode_Duplicates)
    for name, value in settings.items():
        setattr(node.content, name, value)
    node.markDirty(True)
    node.eval()
    return window, source, node


def test_registration_op_id_and_sockets() -> None:
    assert get_class_from_opcode(AuditNodes.DUPLICATES, NodeTypes.AUDIT) is (
        TriggerNode_Duplicates
    )
    _window, _source, node = _node(key_columns=KEYS)
    assert node.serialize()["op"] == "audit.duplicates"
    assert get_class_from_op("audit.duplicates") is TriggerNode_Duplicates
    assert [s.socket_type for s in node.outputs] == [3, 3, 1]
    assert [o["variable_name"] for o in node.value] == [
        f"var_dup_{node.content.id}",
        f"var_uniq_{node.content.id}",
        f"var_dupsum_{node.content.id}",
    ]
    content = node.content
    assert content.duplicates_var == node.value[0]["variable_name"]
    assert content.unique_var == node.value[1]["variable_name"]
    assert content.summary_variable_name == node.value[2]["variable_name"]
    assert content.exceptions_var_name() == content.duplicates_var


@pytest.mark.parametrize(
    "settings",
    [
        {"key_columns": KEYS},
        {"key_columns": KEYS, "ignore_case": True},
        {
            "key_columns": KEYS,
            "mode": "near",
            "amount_column": "amt",
            "tolerance": 0.5,
            "date_column": "date",
            "window_days": 3,
            "value_column": "amt",
        },
    ],
)
def test_live_value_and_generated_code_agree(settings) -> None:
    _window, source, node = _node(**settings)
    out = node.value
    live = [o["data"].collect() for o in out]
    namespace = {"var_src": source.frame}
    exec(node.get_code(), {"__name__": "__main__"}, namespace)  # noqa: S102
    for item, expected in zip(out, live):
        got = namespace[item["variable_name"]]
        got = got.collect() if isinstance(got, pl.LazyFrame) else got
        assert got.equals(expected)
    assert isinstance(namespace[out[2]["variable_name"]], pl.DataFrame)
    assert live[0].columns[-2:] == ["dup_group_id", "dup_count"]
    code = node.get_code()
    assert "from trigger_designer.core.audit.duplicates import" in code
    assert node.get_code() == code


def test_unwired_node_defines_every_output_variable() -> None:
    window = TriggerSubWindow()
    node = TriggerNode_Duplicates(window.scene)
    namespace: dict = {}
    exec(node.get_code(), {}, namespace)  # noqa: S102
    names = node.content.output_variable_names()
    assert len(names) == 3
    for name in names:
        assert isinstance(namespace[name], pl.DataFrame)


def test_misconfigured_node_fails_live_and_in_the_run_code() -> None:
    _window, source, node = _node()  # no key columns
    assert node.isInvalid() and node.current_error.code == "TD-AUDIT-001"
    assert "TD-AUDIT-001" in node._node_tooltip()
    assert set(node.content.schema()) == set(REFERENCE.columns)
    with pytest.raises(AuditConfigError) as info:
        exec(node.get_code(), {}, {"var_src": source.frame})  # noqa: S102
    assert info.value.code == "TD-AUDIT-001"


def test_after_execution_sets_the_test_summary() -> None:
    _window, _source, node = _node(key_columns=KEYS)
    content = node.content
    frame = node.value[2]["data"].collect()
    content.after_execution({content.summary_variable_name: frame})
    summary = content.test_summary
    assert summary.test_id == f"audit.duplicates#{node.id}"
    assert summary.exceptions_var == content.duplicates_var
    assert summary.exception_rows == 5 and summary.status == "fail"
    assert summary.details == {"groups": 2, "skipped_rows": 2, "unparseable_rows": 0}
    assert summary.parameters["key_columns"] == KEYS


def test_state_round_trips_through_serialize() -> None:
    _window, _source, node = _node(key_columns=KEYS)
    content = node.content
    content.mode = "near"
    content.amount_column = "amt"
    content.tolerance_kind = "percent"
    content.tolerance = 1.5
    content.date_column = "date"
    content.window_days = 7
    content.date_format = "%d/%m/%Y"
    content.value_column = "amt"
    content.ignore_case = True
    content.trim_text = False
    data = content.serialize()
    assert data["key_columns"] == KEYS and data["tolerance"] == 1.5
    window = TriggerSubWindow()
    other = TriggerNode_Duplicates(window.scene)
    other.content.deserialize(dict(data))
    assert other.content.params() == content.params()
    other.content.deserialize({})
    assert other.content.params() == DuplicatesParams()
    assert other.content.key_columns == []
