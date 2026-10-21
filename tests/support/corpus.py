"""The workflows the E2E layer loads and runs.

Most sources are the sample files under ``savedfiles/``. Some of those can no
longer run unchanged, because File Input reads CSV columns as strings on
purpose (see ``FileInputContent._scan_csv_full``) while they were authored
against a build that inferred numeric dtypes. Those have a locally owned copy
under ``tests/e2e/workflows/`` with the smallest fix that makes the workflow
mean what it says:

* ``formula-category.tds`` - ``3. in-formula-out.json`` with
  ``TRY_CAST(Difficulty AS INTEGER)`` in its CASE expression, so the numeric
  comparison is explicit.
* ``running-total-grouped.tds`` - a File Input -> Formula -> Running Total ->
  File Output graph. The node arithmetic needs a numeric column, so the
  Formula adds ``RelevancyNum`` with ``TRY_CAST([Relevancy Score] AS DOUBLE)``
  and the Running Total sums it inside each ``Difficulty`` group (the sample
  data has three).

The expected outputs below are *not* the CSVs under ``savedfiles/``: those
were produced from a ``check.csv`` that was never checked in and no longer
exists on the author's machine. Instead, each case's output is frozen under
``tests/e2e/fixtures/expected`` from a run against the tracked sample data.
Regenerate them deliberately with::

    $env:TRIGGER_UPDATE_E2E_GOLDENS = "1"
    uv run --project . pytest tests/e2e -q

and review the resulting diff.
"""

from __future__ import annotations

from tests.support.workflows import WorkflowCase

#: Workflows whose File Output nodes write the files being checked.
FILE_OUTPUT_CASES = (
    WorkflowCase(
        name="select",
        source="savedfiles/2. in-select-out.json",
        inputs={"check.csv": "data/check.csv"},
        goldens={"out_check_W_select.csv": "select"},
    ),
    WorkflowCase(
        name="formula",
        source="tests/e2e/workflows/formula-category.tds",
        inputs={"check.csv": "data/check.csv"},
        goldens={"out_check_W_formula.csv": "formula"},
    ),
    WorkflowCase(
        name="join",
        source="savedfiles/4.1. in-join-out.json",
        inputs={"check.csv": "data/check.csv", "check_1.csv": "data/check_1.csv"},
        goldens={
            "out_check_W_join.csv": "join",
            "out_check_W_left-join.csv": "join-left",
            "out_check_W_right-join.csv": "join-right",
        },
        # Polars' multi-threaded hash join does not promise a row order.
        unordered_goldens=frozenset({"join", "join-left", "join-right"}),
    ),
    WorkflowCase(
        name="unique",
        source="savedfiles/5. in-unique-out.json",
        inputs={"check.csv": "data/check.csv"},
        goldens={"5. out_check_W_uniquecsv.csv": "unique"},
    ),
    WorkflowCase(
        name="filter",
        source="savedfiles/6. in-filter-out.json",
        inputs={"check.csv": "data/check.csv"},
        goldens={
            "6. out_check_W_filter.csv": "filter-true",
            "6.1. out_check_W_false-filter.csv": "filter-false",
        },
    ),
    WorkflowCase(
        name="sort",
        source="savedfiles/7. in-sort-out.json",
        inputs={"check.csv": "data/check.csv"},
        goldens={"7. out_check_W_sort.csv": "sort"},
    ),
    WorkflowCase(
        name="transpose",
        source="savedfiles/10. Transpose.tds",
        inputs={"1. out_check.csv": "savedfiles/1. out_check.csv"},
        goldens={"10. Transposed Out.csv": "transpose"},
    ),
    WorkflowCase(
        name="split",
        source="savedfiles/11. Split.tds",
        inputs={"1. out_check.csv": "savedfiles/1. out_check.csv"},
        goldens={
            "11. Split_E.csv": "split-estimation",
            "11. Split_H.csv": "split-holdout",
        },
    ),
    WorkflowCase(
        name="running_total",
        source="tests/e2e/workflows/running-total-grouped.tds",
        inputs={"check.csv": "data/check.csv"},
        goldens={"running_total.csv": "running-total"},
    ),
)

#: Every node type in one graph: a run-level smoke test.
ALL_NODES_CASE = WorkflowCase(
    name="all_nodes",
    source="savedfiles/0. All Node- Test.tds",
    inputs={"check.csv": "data/check.csv"},
)
