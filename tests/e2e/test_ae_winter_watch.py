"""End-to-end: the A&E Winter Watch example reproduces NHS England's figures.

The workflow reads twelve published monthly CSV returns and writes three
reports. The assertions below are deliberately external: the March 2026
percentages and the "0 of 121 trusts met 95%" line are the figures NHS England
published in its March 2026 statistical commentary, and the twelve-hour count
is the number printed on the same page.
"""

from __future__ import annotations

import polars as pl
import pytest

from tests.support.workflows import (
    WorkflowCase,
    materialize,
    nodes_titled,
    run_workflow_and_wait,
)

pytestmark = pytest.mark.e2e

CASE = WorkflowCase(
    name="ae_winter_watch",
    source="savedfiles/Example_3_AE_Winter_Watch/ae_winter_watch.tds",
    inputs={"data": "savedfiles/Example_3_AE_Winter_Watch/data"},
)


@pytest.fixture(autouse=True)
def _no_dialogs(no_modal_dialogs):
    return no_modal_dialogs


def _run(qtbot, tmp_path):
    from trigger_designer.qt.design_window import TriggerSubWindow

    materialized = materialize(CASE, tmp_path)
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    assert window.fileLoad(str(materialized.path)) is True
    run_workflow_and_wait(qtbot, window)
    return window, materialized.out_dir


def _read(out_dir, name: str) -> pl.DataFrame:
    return pl.read_csv(out_dir / name)


def test_reports_match_published_figures(qtbot, tmp_path, no_modal_dialogs) -> None:
    window, out_dir = _run(qtbot, tmp_path)

    total = len(window.getAllNodes())
    finished = len(window.execution_results)
    assert finished == total, (
        f"{total - finished} of {total} nodes did not finish; "
        f"invalid: {[node.title for node in window.getAllNodes() if node.isInvalid()]}"
    )
    assert no_modal_dialogs["warnings"] == [], no_modal_dialogs["warnings"]

    national = _read(out_dir, "national_monthly.csv")
    assert national.height == 12
    by_month = {str(row["Month"]): row for row in national.iter_rows(named=True)}

    march = by_month["2026-03-01"]
    assert march["Within4Pct"] == pytest.approx(77.11, abs=0.01)
    assert march["Type1Within4Pct"] == pytest.approx(64.09, abs=0.01)
    assert march["Wait12h"] == 46665

    february = by_month["2026-02-01"]
    assert february["Within4Pct"] == pytest.approx(74.06, abs=0.01)

    january = by_month["2026-01-01"]
    assert january["Within4Pct"] == pytest.approx(72.45, abs=0.01)
    assert january["Type1Within4Pct"] == pytest.approx(57.32, abs=0.01)

    trust = _read(out_dir, "trust_watchlist.csv")
    assert trust.height == 121
    # The watchlist is a full-year view of the 121 major A&E trusts. Every
    # Type 1 attendance and every 12-hour decision-to-admit wait belongs to
    # one of them, so those totals must reconcile to the national table; the
    # all-types total is lower because minor-injury units and UTCs are out.
    assert trust["Type1Att"].sum() == national["Type1Att"].sum() == 17_121_495
    assert trust["Type1Over4"].sum() == national["Type1Over4"].sum() == 6_699_243
    assert trust["Wait12h"].sum() == national["Wait12h"].sum() == 570_957
    assert trust["Attendances"].sum() == 25_288_018
    assert set(trust["MonthsReported"].unique().to_list()) == {12}
    # NHS England reported 0 of 121 trusts meeting 95% in March 2026; no trust
    # met it across the full year either.
    assert trust.filter(pl.col("Within4Pct") >= 95).height == 0

    worst = trust.sort("Type1Within4Pct").row(0, named=True)
    assert worst["Trust"] == "MID CHESHIRE HOSPITALS NHS FOUNDATION TRUST"
    assert worst["Type1Within4Pct"] == pytest.approx(43.64, abs=0.01)
    assert worst["Severity"] == "Critical"

    shrewsbury = trust.filter(pl.col("OrgCode") == "RXW").row(0, named=True)
    assert shrewsbury["Wait12h"] == 16915
    assert shrewsbury["Wait12Per1k"] == pytest.approx(105.47, abs=0.01)

    severity = dict(trust.group_by("Severity").len().iter_rows())
    assert severity == {"Critical": 59, "Watch": 42, "OK": 20}

    region = _read(out_dir, "region_summary.csv")
    assert region.height == 7
    # Regions cover every provider, so they reconcile to the national table.
    assert region["Attendances"].sum() == national["Attendances"].sum()
    assert region["Type1Att"].sum() == national["Type1Att"].sum()
    north_west = region.filter(pl.col("Region") == "NHS ENGLAND NORTH WEST").row(
        0, named=True
    )
    assert north_west["Within4Pct"] == pytest.approx(72.37, abs=0.01)
    assert north_west["Type1Within4Pct"] == pytest.approx(57.71, abs=0.01)


def test_charts_use_the_full_run_not_the_live_sample(
    qtbot, tmp_path, no_modal_dialogs
) -> None:
    """The Graph node must chart the run's frame, not the 100-row live sample.

    A live evaluation samples 100 rows, which for the national branch is a
    single month. The chart spec is therefore a useful end-to-end check that
    run outputs reached the node.
    """
    window, _out = _run(qtbot, tmp_path)

    graphs = nodes_titled(window, "Graph")
    assert len(graphs) == 2
    specs = {graph.getNodeLabel(): graph.content.build_spec() for graph in graphs}

    trend = specs["Trend chart"]
    assert trend.renderable is True
    assert trend.point_count == 24  # 12 months x 2 measures
    assert {series.name for series in trend.series} == {
        "Metric: Within4Pct",
        "Metric: Type1Within4Pct",
    }
    assert all(len(series.x) == 12 for series in trend.series)

    watchlist = specs["Watchlist chart"]
    assert watchlist.renderable is True
    assert watchlist.point_count == 15
    assert watchlist.series[0].x[0] == "RBT"
    assert watchlist.series[0].y[0] == pytest.approx(43.64, abs=0.01)
