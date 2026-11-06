"""Shaping nodes stay lazy: ``run_node`` must not run its input until Run collects.

``docs/internal/dev/architecture.md`` ("Run") promises that a shaping node builds a
LazyFrame plan and returns it. Each input is wrapped in a probe that logs every
execution of its plan. The count read right after the runner returns, before any
output is collected, is what the node itself made its input run. Collecting the
outputs afterwards must run the input again, which shows the outputs really are
plans over it, so the zero count cannot pass vacuously.

Only ``EAGER_BY_DESIGN`` and ``BOUNDED_BY_DESIGN`` may run an input early, and each
entry is asserted: an entry whose node has become lazy fails, so the exception has
to be removed. Every module that defines a ``run_*(frames, settings)`` runner needs
cases in ``CASES``, or a one-line reason in ``NOT_COVERED``.
"""

from __future__ import annotations

import ast
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

import polars as pl
import pytest

import trigger_designer.core.shaping as shaping_package
from trigger_designer.core.shaping import (
    aggregate,
    append,
    cleansing,
    count,
    data_profile,
    date_helper,
    file_output,
    find_replace,
    formula,
    fuzzy,
    graph,
    join,
    multi_formula,
    normalize,
    reconcile,
    record_id,
    reshape,
    rows,
    running_total,
    select,
    select_records,
    sort,
    split,
    sql_query,
    text_to_columns,
    transpose,
    unique,
    window,
)
from trigger_designer.core.shaping import filter as filter_node

# ---------------------------------------------------------------------------
# Probe: a LazyFrame that logs each time its plan runs
# ---------------------------------------------------------------------------


def probe(frame: pl.DataFrame) -> tuple[pl.LazyFrame, list[int]]:
    """Return a LazyFrame over ``frame`` and the log of its executions.

    One log entry is one execution of the plan, holding the batch height it saw.
    Polars 2.0 does not push ``head()`` into a ``map_batches`` function, so the
    height is the whole input even for a bounded read. Only the count is asserted.
    """
    log: list[int] = []

    def record(batch: pl.DataFrame) -> pl.DataFrame:
        log.append(batch.height)
        return batch

    return frame.lazy().map_batches(record, schema=frame.schema), log


# ---------------------------------------------------------------------------
# Small hand-written inputs (a fresh frame per call)
# ---------------------------------------------------------------------------


def _orders() -> pl.DataFrame:
    """Numeric id, text with a null and a blank, floats, and ISO dates as text."""
    return pl.DataFrame(
        {
            "id": [1, 2, 3, 4, 5, 6],
            "name": [" Alpha ", "beta", None, "GAMMA", "delta", ""],
            "amount": [10.0, 20.5, None, 40.0, 5.25, 60.0],
            "score": [1.5, 2.5, 3.5, 4.5, 5.5, 6.5],
            "when": [
                "2024-01-05",
                "2024-02-10",
                "2024-03-15",
                "2024-04-01",
                "2024-05-20",
                "2024-06-30",
            ],
        }
    )


def _sales() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "id": [1, 1, 2, 2],
            "attr": ["x", "y", "x", "y"],
            "value": [10.0, 20.0, 30.0, 40.0],
        }
    )


def _codes() -> pl.DataFrame:
    return pl.DataFrame({"id": [1, 2, 3], "acct": ["10-20-30", "40-50", "60"]})


def _text_ranks() -> pl.DataFrame:
    return pl.DataFrame({"t": ["10", "x", "3", None]})


def _headers() -> pl.DataFrame:
    return pl.DataFrame({" Order Id ": [1, 2], "Net Amount": [9.5, 3.25]})


def _join_left() -> pl.DataFrame:
    return pl.DataFrame({"id": [1, 2, 3], "a": ["x", "y", "z"]})


def _join_right() -> pl.DataFrame:
    return pl.DataFrame({"rid": [2, 3, 4], "b": ["p", "q", "r"]})


def _keyed_left() -> pl.DataFrame:
    return pl.DataFrame({"k": ["a", "b", "c"], "amt": [10.0, 20.0, 30.0]})


def _keyed_right() -> pl.DataFrame:
    return pl.DataFrame({"k": ["a", "c", "d"], "amt": [10.5, 30.0, 40.0]})


def _vendors() -> pl.DataFrame:
    return pl.DataFrame(
        {"Vendor": ["ACME Corp.", "Globex, Inc", "Initech LLC"], "id": [1, 2, 3]}
    )


def _suppliers() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "Supplier": ["Acme Corporation", "GLOBEX INC.", "Initec"],
            "ref": ["a", "b", "c"],
        }
    )


def _t1() -> pl.DataFrame:
    return pl.DataFrame({"id": [1, 2, 3], "amount": [10.0, 20.5, 30.0]})


def _t2() -> pl.DataFrame:
    return pl.DataFrame({"id": [2, 3, 4], "score": [2.5, 3.5, 4.5]})


# ---------------------------------------------------------------------------
# Cases: every runner, plus the variants whose code path differs (a filter mode,
# rows with and without an input, a text or numeric rank, a cleansing option)
# ---------------------------------------------------------------------------


class Case(NamedTuple):
    """One runner under test, the settings it gets and the frames it reads."""

    id: str
    run: Callable[[list, dict], list]
    settings: dict
    #: One DataFrame per input, ``None`` for an unconnected optional input.
    frames: Callable[[], list[pl.DataFrame | None]]


ROWS_SETTINGS = {
    "field_name": "counter",
    "field_type": "int",
    "initial_value": 1,
    "increment_value": 1,
    "max_value": 5,
}

CASES: tuple[Case, ...] = (
    Case(
        "aggregate",
        aggregate.run_node,
        {
            "actions": [
                {"field": "name", "action": "GroupBy"},
                {"field": "amount", "action": "Sum"},
            ]
        },
        lambda: [_orders()],
    ),
    Case(
        "append", append.run_node, {"how": "vertical"}, lambda: [_orders(), _orders()]
    ),
    Case("cleansing", cleansing.run_node, {}, lambda: [_orders()]),
    Case(
        "cleansing_remove_null_rows",
        cleansing.run_node,
        {
            "remove_null_rows": True,
            "remove_null_rows_from_selected_columns": True,
            "selected_fields": ["name"],
        },
        lambda: [_orders()],
    ),
    Case(
        "cleansing_remove_null_columns",
        cleansing.run_node,
        {"remove_null_columns": True},
        lambda: [_orders()],
    ),
    Case("count", count.run_node, {}, lambda: [_orders()]),
    Case("data_profile", data_profile.run_node, {}, lambda: [_orders()]),
    # The head(100) sample is read only by parse_failures (the Dock chip), not here.
    Case(
        "date_helper",
        date_helper.run_node,
        {"ops": [{"op": "weekday_name", "source": "when"}]},
        lambda: [_orders()],
    ),
    Case(
        "file_output",
        file_output.run_node,
        {"filePath": "unused.csv", "file_format": "csv"},
        lambda: [_orders()],
    ),
    Case(
        "filter_builder",
        filter_node.run_node,
        {
            "mode": "builder",
            "column": "amount",
            "operation": "Greater Than",
            "value": "15",
        },
        lambda: [_orders()],
    ),
    Case(
        "filter_expression",
        filter_node.run_node,
        {"mode": "expression", "expression": "[amount] > 15"},
        lambda: [_orders()],
    ),
    Case(
        "find_replace",
        find_replace.run_node,
        {"columns": ["name"], "rules": [{"find": "a", "replace": "X"}]},
        lambda: [_orders()],
    ),
    Case(
        "formula",
        formula.run_node,
        {
            "sections": [
                {"target_column": "double_amount", "formula_text": "[amount] * 2"}
            ]
        },
        lambda: [_orders()],
    ),
    Case(
        "fuzzy",
        fuzzy.run_node,
        {"left_column": "Vendor", "right_column": "Supplier"},
        lambda: [_vendors(), _suppliers()],
    ),
    Case(
        "graph",
        graph.run_node,
        {"graph_type": "line", "x_column": "id", "y_column": "amount"},
        lambda: [_orders()],
    ),
    Case(
        "join",
        join.run_node,
        {
            "mapping_data": [{"left_column": "id", "right_column": "rid"}],
            "selected_columns": [],
            "auto_accept_new_columns": True,
            "known_columns": [],
        },
        lambda: [_join_left(), _join_right()],
    ),
    Case(
        "multi_formula",
        multi_formula.run_node,
        {"columns": ["amount"], "template": "{col} * 2", "mode": "in_place"},
        lambda: [_orders()],
    ),
    Case("normalize", normalize.run_node, {}, lambda: [_headers()]),
    Case(
        "record_id",
        record_id.run_node,
        {"name": "RecordID", "start": 1},
        lambda: [_orders()],
    ),
    Case(
        "pivot",
        reshape.run_pivot,
        {
            "index_columns": ["id"],
            "header_column": "attr",
            "value_column": "value",
            "aggregation": "sum",
        },
        lambda: [_sales()],
    ),
    Case(
        "unpivot",
        reshape.run_unpivot,
        {"id_columns": ["id"], "value_columns": ["amount", "score"]},
        lambda: [_orders()],
    ),
    Case(
        "reconcile",
        reconcile.run_node,
        {
            "key_pairs": [{"left": "k", "right": "k"}],
            "amount_left": "amt",
            "amount_right": "amt",
            "tolerance": 1.0,
        },
        lambda: [_keyed_left(), _keyed_right()],
    ),
    Case("rows", rows.run_node, ROWS_SETTINGS, lambda: [None]),
    Case("rows_with_input", rows.run_node, ROWS_SETTINGS, lambda: [_orders().head(5)]),
    Case(
        "running_total",
        running_total.run_node,
        {"sum_columns": ["amount"], "group_by_columns": ["name"]},
        lambda: [_orders()],
    ),
    Case(
        "select",
        select.run_node,
        {
            "columns": [
                {"name": "name", "selected": True, "dtype": "String", "rename": "Name"},
                {"name": "id", "selected": True, "dtype": "Int64", "rename": ""},
            ]
        },
        lambda: [_orders()],
    ),
    Case(
        "select_records_first_n",
        select_records.run_node,
        {"mode": "first_n", "n": 2},
        lambda: [_orders()],
    ),
    Case(
        "select_records_int_rank",
        select_records.run_node,
        {"mode": "largest_n", "n": 2, "by": "id"},
        lambda: [_orders()],
    ),
    Case(
        "select_records_text_rank",
        select_records.run_node,
        {"mode": "largest_n", "n": 1, "by": "t"},
        lambda: [_text_ranks()],
    ),
    Case(
        "sort",
        sort.run_node,
        {"keys": [{"column": "amount", "order": "Descending"}]},
        lambda: [_orders()],
    ),
    Case(
        "split",
        split.run_node,
        {"estimation_percent": 70, "random_seed": 42, "is_random": True},
        lambda: [_orders()],
    ),
    Case(
        "sql_query",
        sql_query.run_node,
        {
            "sql": (
                "SELECT t1.id, t1.amount, t2.score FROM t1 "
                "JOIN t2 USING (id) ORDER BY t1.id"
            )
        },
        lambda: [_t1(), _t2(), None],
    ),
    Case(
        "text_to_columns",
        text_to_columns.run_node,
        {"column": "acct", "pattern": "-", "max_splits": 2},
        lambda: [_codes()],
    ),
    Case(
        "transpose",
        transpose.run_node,
        {"key_columns": ["id"], "data_columns": ["amount", "score"]},
        lambda: [_orders()],
    ),
    Case(
        "unique", unique.run_node, {"selected_columns": ["name"]}, lambda: [_orders()]
    ),
    Case(
        "window",
        window.run_node,
        {
            "partition_by": ["name"],
            "order_by": [{"column": "id"}],
            "ops": [{"op": "lag", "source": "amount"}],
        },
        lambda: [_orders()],
    ),
)

#: Nodes that run their input during the call on purpose: the test asserts they do.
EAGER_BY_DESIGN: dict[str, str] = {
    "cleansing_remove_null_columns": (
        "all-null columns need the data: one one-row null summary"
    ),
    "data_profile": "a full statistical profile at call time, so Run errors surface here",
    "filter_expression": "the SQL WHERE runs in DuckDB at call time",
    "formula": "the sections run as one DuckDB query at call time",
    "fuzzy": "both inputs are collected to build and score candidate pairs",
    "multi_formula": (
        "one DuckDB query over a collected input (DuckDB workers must not enter "
        "LazyFrame.collect off the Qt thread)"
    ),
    "reconcile": "both inputs are collected to pair keys and total amounts",
    "rows_with_input": "the input height must equal the generated count (TD-SHAPE-130)",
    "select_records_text_rank": (
        "ranking a TEXT column needs one aggregate to see if it holds numbers "
        "(TD-SHAPE-091)"
    ),
    "sql_query": "the SQL runs in DuckDB at call time; its result is materialised",
}

#: Nodes that run their input exactly this many times during the call, and why.
BOUNDED_BY_DESIGN: dict[str, tuple[int, str]] = {
    "pivot": (1, "the distinct header values are collected once; the pivot stays lazy"),
}

#: Shaping modules without a case, with the reason. Empty: every runner has cases.
NOT_COVERED: dict[str, str] = {}


# ---------------------------------------------------------------------------
# Discovery: which shaping modules define a runner
# ---------------------------------------------------------------------------


def _discover_runners() -> dict[str, set[str]]:
    """Map each shaping module with a ``run_*(frames, settings)`` runner to its names.

    Read with ``ast`` so a module that fails to import still shows up.
    """
    directory = Path(next(iter(shaping_package.__path__)))
    found: dict[str, set[str]] = {}
    for source in sorted(directory.glob("*.py")):
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        runners = {
            node.name
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name.startswith("run_")
            and [arg.arg for arg in node.args.args][:2] == ["frames", "settings"]
        }
        if runners:
            found[source.stem] = runners
    return found


def _module_of(run: Callable) -> str:
    return run.__module__.rsplit(".", 1)[-1]


def _probe_inputs(case: Case) -> tuple[list[pl.LazyFrame | None], list[list[int]]]:
    """Wrap each frame of ``case`` in a probe; return the inputs and their logs."""
    inputs: list[pl.LazyFrame | None] = []
    logs: list[list[int]] = []
    for frame in case.frames():
        if frame is None:
            inputs.append(None)
            continue
        lazy, log = probe(frame)
        inputs.append(lazy)
        logs.append(log)
    return inputs, logs


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_probe_counts_executions_not_references() -> None:
    """The probe is the thing being trusted: prove it counts what it should."""
    lazy, log = probe(pl.DataFrame({"v": [1, 2, 3]}))
    lazy.collect_schema()
    assert log == []
    lazy.select(pl.len()).collect()
    assert len(log) == 1
    lazy.collect()
    assert len(log) == 2


def test_every_runner_module_has_cases_or_an_excuse() -> None:
    discovered = _discover_runners()
    covered = {_module_of(case.run) for case in CASES}
    excused = set(NOT_COVERED)
    assert covered.isdisjoint(excused), "a module is both covered and excused"
    assert set(discovered) == covered | excused, (
        f"unlisted modules: {sorted(set(discovered) - covered - excused)}; "
        f"listed but no runner: {sorted((covered | excused) - set(discovered))}"
    )


def test_every_discovered_runner_has_a_case() -> None:
    discovered = _discover_runners()
    expected = {
        (module, runner)
        for module, runners in discovered.items()
        if module not in NOT_COVERED
        for runner in runners
    }
    covered = {(_module_of(case.run), case.run.__name__) for case in CASES}
    assert covered == expected, (
        f"runners without a case: {sorted(expected - covered)}; "
        f"cases for unknown runners: {sorted(covered - expected)}"
    )


def test_exception_tables_name_real_cases_and_explain_them() -> None:
    ids = [case.id for case in CASES]
    assert len(ids) == len(set(ids)), "case ids must be unique"
    known = set(ids)
    assert set(EAGER_BY_DESIGN) <= known, "EAGER_BY_DESIGN names an unknown case"
    assert set(BOUNDED_BY_DESIGN) <= known, "BOUNDED_BY_DESIGN names an unknown case"
    assert set(EAGER_BY_DESIGN).isdisjoint(BOUNDED_BY_DESIGN)
    reasons = [
        *EAGER_BY_DESIGN.values(),
        *(reason for _, reason in BOUNDED_BY_DESIGN.values()),
        *NOT_COVERED.values(),
    ]
    assert all(reason.strip() and "\n" not in reason for reason in reasons)


def _check_contract(case: Case) -> None:
    """Run ``case`` through probes and assert the lazy contract (AssertionError)."""
    inputs, logs = _probe_inputs(case)
    outputs = case.run(inputs, dict(case.settings))
    executions = [len(log) for log in logs]

    if case.id in EAGER_BY_DESIGN:
        assert all(count >= 1 for count in executions), (
            f"{case.id} is in EAGER_BY_DESIGN ({EAGER_BY_DESIGN[case.id]}) but its "
            f"input did not run during the call (executions {executions}); "
            "the exception is stale, remove the entry"
        )
    elif case.id in BOUNDED_BY_DESIGN:
        expected, reason = BOUNDED_BY_DESIGN[case.id]
        assert executions == [expected] * len(executions), (
            f"{case.id} must run its input exactly {expected} time(s) during the call "
            f"({reason}); got {executions}"
        )
    else:
        assert executions == [0] * len(executions), (
            f"{case.id} ran its input during run_node (executions {executions}); "
            "a shaping node must return a plan and leave the work to Run"
        )

    assert all(isinstance(out, pl.LazyFrame) for out in outputs)
    for out in outputs:
        out.collect()
    if outputs and case.id not in EAGER_BY_DESIGN:
        # Collecting the outputs must run the input again. Otherwise the outputs
        # are not plans over it, and the zero count above would prove nothing.
        reruns = [len(log) - seen for log, seen in zip(logs, executions)]
        assert all(rerun >= 1 for rerun in reruns), (
            f"{case.id}: collecting the outputs did not run the input (reruns "
            f"{reruns}); the outputs are not plans built on it"
        )


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.id)
def test_run_node_leaves_its_input_unexecuted(case: Case) -> None:
    _check_contract(case)


def test_contract_rejects_an_eager_runner_and_a_vacuous_one() -> None:
    """The checks above must be able to fail, or a green run proves nothing."""

    def eager(frames: list, settings: dict) -> list:
        frames[0].collect()
        return [frames[0]]

    def vacuous(frames: list, settings: dict) -> list:
        return [pl.DataFrame({"v": [1]}).lazy()]

    for runner in (eager, vacuous):
        case = Case(runner.__name__, runner, {}, lambda: [pl.DataFrame({"v": [1, 2]})])
        with pytest.raises(AssertionError):
            _check_contract(case)


def test_stale_exception_entry_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    sort_case = next(case for case in CASES if case.id == "sort")
    monkeypatch.setitem(EAGER_BY_DESIGN, "sort", "pretend sort runs its input")
    with pytest.raises(AssertionError, match="stale"):
        _check_contract(sort_case)
