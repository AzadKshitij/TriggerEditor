"""Build the A&E Winter Watch workflow (``ae_winter_watch.tds``).

The workflow is constructed from the app's own registered node classes, so the
saved file always matches the current serialization schema. Run this after
moving the repository: the workflow stores File Output paths absolutely, and
this script rebinds them to this checkout.

Usage (from the repository root)::

    uv run --project . python savedfiles/Example_3_AE_Winter_Watch/build_workflow.py
    uv run --project . python savedfiles/Example_3_AE_Winter_Watch/build_workflow.py --run

``--run`` executes the workflow headlessly and prints the three report row
counts. Opening ``ae_winter_watch.tds`` in the app is the normal way to use it.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
DATA_DIR = HERE / "data"
OUTPUT_DIR = HERE / "output"
WORKFLOW = HERE / "ae_winter_watch.tds"

#: Original column -> (short name, dtype). CSV input arrives as text, so every
#: numeric column is cast here. ``dtype_custom`` must be true or the Select
#: dock resets the dtype back to the source dtype on load.
COLUMNS = {
    "Period": ("Period", "String"),
    "Org Code": ("OrgCode", "String"),
    "Parent Org": ("Region", "String"),
    "Org name": ("Trust", "String"),
    "A&E attendances Type 1": ("AttT1", "Int64"),
    "A&E attendances Type 2": ("AttT2", "Int64"),
    "A&E attendances Other A&E Department": ("AttOther", "Int64"),
    "A&E attendances Booked Appointments Type 1": ("BookT1", "Int64"),
    "A&E attendances Booked Appointments Type 2": ("BookT2", "Int64"),
    "A&E attendances Booked Appointments Other Department": ("BookOther", "Int64"),
    "Attendances over 4hrs Type 1": ("OverT1", "Int64"),
    "Attendances over 4hrs Type 2": ("OverT2", "Int64"),
    "Attendances over 4hrs Other Department": ("OverOther", "Int64"),
    "Attendances over 4hrs Booked Appointments Type 1": ("OverBookT1", "Int64"),
    "Attendances over 4hrs Booked Appointments Type 2": ("OverBookT2", "Int64"),
    "Attendances over 4hrs Booked Appointments Other Department": (
        "OverBookOther",
        "Int64",
    ),
    "Patients who have waited 4-12 hs from DTA to admission": ("Wait4to12h", "Int64"),
    "Patients who have waited 12+ hrs from DTA to admission": ("Wait12h", "Int64"),
    "Emergency admissions via A&E - Type 1": ("EmAdmT1", "Int64"),
    "Emergency admissions via A&E - Type 2": ("EmAdmT2", "Int64"),
    "Emergency admissions via A&E - Other A&E department": ("EmAdmOther", "Int64"),
    "Other emergency admissions": ("EmAdmOtherSrc", "Int64"),
}

RATE_SECTIONS = [
    {
        "target_column": "Within4Pct",
        "formula_text": "round(([Attendances] - [Over4]) * 100.0 / [Attendances], 2)",
        "target_dtype": "Float",
        "editor_height": 120,
    },
    {
        "target_column": "Type1Within4Pct",
        "formula_text": (
            "CASE WHEN [Type1Att] > 0 THEN "
            "round(([Type1Att] - [Type1Over4]) * 100.0 / [Type1Att], 2) "
            "ELSE NULL END"
        ),
        "target_dtype": "Float",
        "editor_height": 120,
    },
    {
        "target_column": "Wait12Per1k",
        "formula_text": "round([Wait12h] * 1000.0 / [Attendances], 2)",
        "target_dtype": "Float",
        "editor_height": 120,
    },
    {
        "target_column": "GapTo95",
        "formula_text": "round([Within4Pct] - 95, 2)",
        "target_dtype": "Float",
        "editor_height": 120,
    },
    {
        "target_column": "Severity",
        "formula_text": (
            "CASE WHEN [Type1Within4Pct] < 60 THEN 'Critical' "
            "WHEN [Type1Within4Pct] < 70 THEN 'Watch' ELSE 'OK' END"
        ),
        "target_dtype": "String",
        "editor_height": 120,
    },
]


def _select_columns() -> list[dict]:
    columns = []
    for name, (rename, dtype) in COLUMNS.items():
        columns.append(
            {
                "name": name,
                "selected": True,
                "dtype": dtype,
                "rename": rename,
                "date_format": "",
                "dtype_custom": dtype != "String",
            }
        )
    return columns


def _group_actions(*, keys: list[str], sums: list[str]) -> list[dict]:
    actions = [
        {"field": field, "action": "GroupBy", "output_name": field} for field in keys
    ]
    actions.extend(
        {"field": field, "action": "Sum", "output_name": field} for field in sums
    )
    return actions


def build() -> None:
    from qtpy.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv[:1])

    from nodeeditor.node_edge import Edge

    from trigger_designer.core.node_configuration import (
        IONodes,
        NodeTypes,
        PreparationNodes,
        ReportNodes,
        TransformNodes,
        get_class_from_opcode,
    )
    from trigger_designer.qt.design_window import TriggerSubWindow

    window = TriggerSubWindow()
    scene = window.scene
    nodes: dict[str, object] = {}

    def add(
        name: str,
        op,
        family,
        x: float,
        y: float,
        label: str,
        settings: dict | None = None,
    ):
        cls = get_class_from_opcode(op, family)
        node = cls(scene)
        node.setPos(x, y)
        node.setNodeLabel(label)
        node.setNodeLabelVisible(bool(label))
        if settings is not None:
            node.content.settings = settings
        nodes[name] = node
        return node

    def connect(
        source: str, target: str, out_index: int = 0, in_index: int = 0
    ) -> None:
        Edge(
            scene,
            nodes[source].outputs[out_index],
            nodes[target].inputs[in_index],
        )

    # -- ingest ---------------------------------------------------------
    source = get_class_from_opcode(IONodes.FILE_INPUT, NodeTypes.IO)(scene)
    source.setPos(-640, -60)
    source.setNodeLabel("12 monthly NHS files")
    source.setNodeLabelVisible(True)
    source.content.filePath = str(DATA_DIR)
    source.content.file_type = "csv"
    source.content.first_row_contains_field_names = True
    source.content.file_order = "name"
    source.content.output_filename_as_field = False
    source.content.record_limit = 0
    nodes["source"] = source

    add(
        "cleanse",
        PreparationNodes.CLEANSING,
        NodeTypes.PREPARATION,
        -410,
        -60,
        "Trim names",
        {
            "remove_null_rows": False,
            "remove_null_rows_from_selected_columns": False,
            "remove_null_columns": False,
            "replace_null_strings": True,
            "replace_null_numbers": True,
            "strip_whitespace": True,
            "normalize_spaces": True,
            "remove_all_whitespace": False,
            "case_modification": "none",
            "remove_letters": False,
            "remove_numbers": False,
            "remove_punctuation": False,
            "selected_fields": ["Period", "Org Code", "Parent Org", "Org name"],
        },
    )
    add(
        "drop_total",
        PreparationNodes.FILTER,
        NodeTypes.PREPARATION,
        -180,
        -60,
        "Drop TOTAL row",
        {
            "mode": "builder",
            "column": "Org Code",
            "operation": "Not Equals",
            "value": "TOTAL",
            "value2": "",
            "expression": "",
        },
    )
    add(
        "names",
        PreparationNodes.SELECT,
        NodeTypes.PREPARATION,
        50,
        -60,
        "Rename + cast",
        {"columns": _select_columns(), "auto_accept_new_columns": True},
    )
    add(
        "totals",
        PreparationNodes.FORMULA,
        NodeTypes.PREPARATION,
        280,
        -60,
        "Totals",
        {
            "sections": [
                {
                    "target_column": "Month",
                    "formula_text": (
                        "strptime(regexp_extract([Period], "
                        "'([A-Z]+)-([0-9]{4})$', 0), '%B-%Y')"
                    ),
                    "target_dtype": "Date",
                    "editor_height": 120,
                },
                {
                    "target_column": "Attendances",
                    "formula_text": (
                        "[AttT1] + [AttT2] + [AttOther] + "
                        "[BookT1] + [BookT2] + [BookOther]"
                    ),
                    "target_dtype": "Integer",
                    "editor_height": 120,
                },
                {
                    "target_column": "Over4",
                    "formula_text": (
                        "[OverT1] + [OverT2] + [OverOther] + "
                        "[OverBookT1] + [OverBookT2] + [OverBookOther]"
                    ),
                    "target_dtype": "Integer",
                    "editor_height": 120,
                },
                {
                    "target_column": "Type1Att",
                    "formula_text": "[AttT1] + [BookT1]",
                    "target_dtype": "Integer",
                    "editor_height": 120,
                },
                {
                    "target_column": "Type1Over4",
                    "formula_text": "[OverT1] + [OverBookT1]",
                    "target_dtype": "Integer",
                    "editor_height": 120,
                },
            ]
        },
    )
    add(
        "rates",
        PreparationNodes.FORMULA,
        NodeTypes.PREPARATION,
        510,
        -60,
        "Rates + severity",
        {"sections": RATE_SECTIONS},
    )

    # -- national branch ------------------------------------------------
    add(
        "nat_group",
        PreparationNodes.GROUPBY,
        NodeTypes.PREPARATION,
        740,
        -300,
        "National by month",
        {
            "actions": _group_actions(
                keys=["Month"],
                sums=[
                    "Attendances",
                    "Over4",
                    "Type1Att",
                    "Type1Over4",
                    "Wait12h",
                    "Wait4to12h",
                    "EmAdmT1",
                ],
            )
        },
    )
    add(
        "nat_rates",
        PreparationNodes.FORMULA,
        NodeTypes.PREPARATION,
        970,
        -300,
        "Monthly rates",
        {
            "sections": [
                {
                    "target_column": "Within4Pct",
                    "formula_text": (
                        "round(([Attendances] - [Over4]) * 100.0 / [Attendances], 2)"
                    ),
                    "target_dtype": "Float",
                    "editor_height": 120,
                },
                {
                    "target_column": "Type1Within4Pct",
                    "formula_text": (
                        "round(([Type1Att] - [Type1Over4]) * 100.0 / [Type1Att], 2)"
                    ),
                    "target_dtype": "Float",
                    "editor_height": 120,
                },
                {
                    "target_column": "GapTo95",
                    "formula_text": "round([Within4Pct] - 95, 2)",
                    "target_dtype": "Float",
                    "editor_height": 120,
                },
                {
                    "target_column": "Wait12Per1k",
                    "formula_text": "round([Wait12h] * 1000.0 / [Attendances], 2)",
                    "target_dtype": "Float",
                    "editor_height": 120,
                },
            ]
        },
    )
    add(
        "nat_sort",
        PreparationNodes.SORT,
        NodeTypes.PREPARATION,
        1200,
        -300,
        "Order months",
        {"keys": [{"column": "Month", "order": "Ascending"}]},
    )
    add(
        "nat_long",
        TransformNodes.UNPIVOT,
        NodeTypes.TRANSFORM,
        1430,
        -300,
        "Long for chart",
        {
            "id_columns": ["Month"],
            "value_columns": ["Within4Pct", "Type1Within4Pct"],
            "variable_name": "Metric",
            "value_name": "Percent",
            "drop_nulls": False,
        },
    )
    add(
        "nat_graph",
        ReportNodes.GRAPH,
        NodeTypes.REPORT,
        1660,
        -300,
        "Trend chart",
        {
            "graph_type": "line",
            "x_column": "Month",
            "y_column": "Percent",
            "color_column": "Metric",
            "aggregation": "none",
            "title": "A&E 4-hour performance, Apr 2025 - Mar 2026",
            "renderer": "matplotlib",
        },
    )
    add(
        "nat_out",
        IONodes.FILE_OUTPUT,
        NodeTypes.IO,
        1430,
        -150,
        "national_monthly.csv",
        {
            "filePath": str(OUTPUT_DIR / "national_monthly.csv"),
            "file_format": "csv",
            "delimiter": ",",
            "use_streaming": True,
            "include_bom": False,
            "compression": None,
        },
    )

    # -- trust branch ---------------------------------------------------
    add(
        "trust_group",
        PreparationNodes.GROUPBY,
        NodeTypes.PREPARATION,
        740,
        -60,
        "Annual by trust",
        {
            "actions": [
                {"field": "OrgCode", "action": "GroupBy", "output_name": "OrgCode"},
                {"field": "Trust", "action": "Last", "output_name": "Trust"},
                {"field": "Region", "action": "Last", "output_name": "Region"},
                {"field": "Attendances", "action": "Sum", "output_name": "Attendances"},
                {"field": "Over4", "action": "Sum", "output_name": "Over4"},
                {"field": "Type1Att", "action": "Sum", "output_name": "Type1Att"},
                {"field": "Type1Over4", "action": "Sum", "output_name": "Type1Over4"},
                {"field": "Wait12h", "action": "Sum", "output_name": "Wait12h"},
                {"field": "Month", "action": "Count", "output_name": "MonthsReported"},
            ]
        },
    )
    add(
        "trust_rates",
        PreparationNodes.FORMULA,
        NodeTypes.PREPARATION,
        970,
        -60,
        "Trust rates",
        {
            "sections": [
                {
                    "target_column": "Within4Pct",
                    "formula_text": (
                        "round(([Attendances] - [Over4]) * 100.0 / [Attendances], 2)"
                    ),
                    "target_dtype": "Float",
                    "editor_height": 120,
                },
                {
                    "target_column": "Type1Within4Pct",
                    "formula_text": (
                        "CASE WHEN [Type1Att] > 0 THEN "
                        "round(([Type1Att] - [Type1Over4]) * 100.0 / [Type1Att], 2) "
                        "ELSE NULL END"
                    ),
                    "target_dtype": "Float",
                    "editor_height": 120,
                },
                {
                    "target_column": "Wait12Per1k",
                    "formula_text": "round([Wait12h] * 1000.0 / [Attendances], 2)",
                    "target_dtype": "Float",
                    "editor_height": 120,
                },
                {
                    "target_column": "GapTo95",
                    "formula_text": "round([Within4Pct] - 95, 2)",
                    "target_dtype": "Float",
                    "editor_height": 120,
                },
                {
                    "target_column": "Severity",
                    "formula_text": (
                        "CASE WHEN [Type1Within4Pct] < 60 THEN 'Critical' "
                        "WHEN [Type1Within4Pct] < 70 THEN 'Watch' ELSE 'OK' END"
                    ),
                    "target_dtype": "String",
                    "editor_height": 120,
                },
            ]
        },
    )
    add(
        "trust_filter",
        PreparationNodes.FILTER,
        NodeTypes.PREPARATION,
        1200,
        -60,
        "Major A&E only",
        {
            "mode": "builder",
            "column": "Type1Att",
            "operation": "Greater Than",
            "value": "0",
            "value2": "",
            "expression": "",
        },
    )
    add(
        "trust_sort",
        PreparationNodes.SORT,
        NodeTypes.PREPARATION,
        1430,
        -60,
        "Worst first",
        {"keys": [{"column": "Type1Within4Pct", "order": "Ascending"}]},
    )
    add(
        "trust_top",
        PreparationNodes.SELECT_RECORDS,
        NodeTypes.PREPARATION,
        1660,
        -60,
        "Top 15",
        {
            "mode": "first_n",
            "n": 15,
            "range_start": 1,
            "range_end": 100,
            "by": "",
            "ties": "exact",
            "group_by": [],
        },
    )
    add(
        "trust_graph",
        ReportNodes.GRAPH,
        NodeTypes.REPORT,
        1890,
        -60,
        "Watchlist chart",
        {
            "graph_type": "bar",
            "x_column": "OrgCode",
            "y_column": "Type1Within4Pct",
            "color_column": "",
            "aggregation": "none",
            "title": "Worst 15 trusts, Type 1 seen within 4 hours (2025/26)",
            "renderer": "matplotlib",
        },
    )
    add(
        "trust_out",
        IONodes.FILE_OUTPUT,
        NodeTypes.IO,
        1660,
        90,
        "trust_watchlist.csv",
        {
            "filePath": str(OUTPUT_DIR / "trust_watchlist.csv"),
            "file_format": "csv",
            "delimiter": ",",
            "use_streaming": True,
            "include_bom": False,
            "compression": None,
        },
    )

    # -- region branch --------------------------------------------------
    add(
        "reg_group",
        PreparationNodes.GROUPBY,
        NodeTypes.PREPARATION,
        740,
        180,
        "By region",
        {
            "actions": _group_actions(
                keys=["Region"],
                sums=["Attendances", "Over4", "Type1Att", "Type1Over4", "Wait12h"],
            )
        },
    )
    add(
        "reg_rates",
        PreparationNodes.FORMULA,
        NodeTypes.PREPARATION,
        970,
        180,
        "Region rates",
        {
            "sections": [
                {
                    "target_column": "Within4Pct",
                    "formula_text": (
                        "round(([Attendances] - [Over4]) * 100.0 / [Attendances], 2)"
                    ),
                    "target_dtype": "Float",
                    "editor_height": 120,
                },
                {
                    "target_column": "Type1Within4Pct",
                    "formula_text": (
                        "round(([Type1Att] - [Type1Over4]) * 100.0 / [Type1Att], 2)"
                    ),
                    "target_dtype": "Float",
                    "editor_height": 120,
                },
                {
                    "target_column": "Wait12Per1k",
                    "formula_text": "round([Wait12h] * 1000.0 / [Attendances], 2)",
                    "target_dtype": "Float",
                    "editor_height": 120,
                },
                {
                    "target_column": "GapTo95",
                    "formula_text": "round([Within4Pct] - 95, 2)",
                    "target_dtype": "Float",
                    "editor_height": 120,
                },
            ]
        },
    )
    add(
        "reg_sort",
        PreparationNodes.SORT,
        NodeTypes.PREPARATION,
        1200,
        180,
        "Worst first",
        {"keys": [{"column": "Within4Pct", "order": "Ascending"}]},
    )
    add(
        "reg_out",
        IONodes.FILE_OUTPUT,
        NodeTypes.IO,
        1430,
        180,
        "region_summary.csv",
        {
            "filePath": str(OUTPUT_DIR / "region_summary.csv"),
            "file_format": "csv",
            "delimiter": ",",
            "use_streaming": True,
            "include_bom": False,
            "compression": None,
        },
    )

    # -- edges ----------------------------------------------------------
    connect("source", "cleanse")
    connect("cleanse", "drop_total")
    connect("drop_total", "names")
    connect("names", "totals")
    connect("totals", "rates")

    connect("rates", "nat_group")
    connect("nat_group", "nat_rates")
    connect("nat_rates", "nat_sort")
    connect("nat_sort", "nat_long")
    connect("nat_long", "nat_graph")
    connect("nat_sort", "nat_out")

    connect("rates", "trust_group")
    connect("trust_group", "trust_rates")
    connect("trust_rates", "trust_filter")
    connect("trust_filter", "trust_sort")
    connect("trust_sort", "trust_out")
    connect("trust_sort", "trust_top")
    connect("trust_top", "trust_graph")

    connect("rates", "reg_group")
    connect("reg_group", "reg_rates")
    connect("reg_rates", "reg_sort")
    connect("reg_sort", "reg_out")

    # -- final lane layout ----------------------------------------------
    # Nodes are 262x172 with a label above, so lanes need ~300px of x and
    # ~300px of y. Keeping the coordinates in one table makes the canvas easy
    # to re-arrange without touching the wiring.
    layout = {
        # ingest spine
        "source": (-680, 0),
        "cleanse": (-380, 0),
        "drop_total": (-80, 0),
        "names": (220, 0),
        "totals": (520, 0),
        "rates": (820, 0),
        # national lane
        "nat_group": (1140, -420),
        "nat_rates": (1440, -420),
        "nat_sort": (1740, -420),
        "nat_long": (2040, -420),
        "nat_graph": (2340, -420),
        "nat_out": (1740, -180),
        # trust lane
        "trust_group": (1140, 120),
        "trust_rates": (1440, 120),
        "trust_filter": (1740, 120),
        "trust_sort": (2040, 120),
        "trust_top": (2340, 120),
        "trust_graph": (2640, 120),
        "trust_out": (2040, 380),
        # region lane
        "reg_group": (1140, 640),
        "reg_rates": (1440, 640),
        "reg_sort": (1740, 640),
        "reg_out": (2040, 640),
    }
    for name, (x, y) in layout.items():
        nodes[name].setPos(x, y)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    scene.saveToFile(str(WORKFLOW))
    print(f"wrote {WORKFLOW}")
    print(f"nodes: {len(scene.nodes)}  edges: {len(scene.edges)}")
    window.close()
    app.processEvents()


def run() -> None:
    """Execute the saved workflow headlessly and report what it wrote."""
    from qtpy.QtCore import QEventLoop, QTimer
    from qtpy.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv[:1])

    from trigger_designer.qt.design_window import TriggerSubWindow

    window = TriggerSubWindow()
    if not window.fileLoad(str(WORKFLOW)):
        raise SystemExit("workflow failed to load")

    loop = QEventLoop()
    timed_out = {"value": False}

    def on_done() -> None:
        loop.quit()

    window.executionResultsChanged.connect(on_done)
    QTimer.singleShot(
        180_000, lambda: (timed_out.__setitem__("value", True), loop.quit())
    )
    window.executeWorkflow()
    loop.exec()

    worker = window._workflow_worker
    if timed_out["value"]:
        raise SystemExit("workflow run timed out")
    if worker is not None:
        worker.wait(60_000)

    finished = len(window.execution_results)
    total = len(window.getAllNodes())
    print(f"nodes finished: {finished}/{total}")
    invalid = [node.title for node in window.getAllNodes() if node.isInvalid()]
    if invalid:
        raise SystemExit(f"invalid nodes: {invalid}")
    if finished != total:
        raise SystemExit("not every node produced a result")

    for name in ("national_monthly.csv", "trust_watchlist.csv", "region_summary.csv"):
        path = OUTPUT_DIR / name
        rows = sum(1 for _ in path.open(encoding="utf-8")) - 1
        print(f"{name}: {rows} rows, {path.stat().st_size} bytes")

    window.close()
    app.processEvents()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run", action="store_true", help="run the workflow after building"
    )
    args = parser.parse_args()

    if not DATA_DIR.is_dir():
        raise SystemExit(f"missing data folder: {DATA_DIR}")

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    build()
    if args.run:
        run()


if __name__ == "__main__":
    main()
