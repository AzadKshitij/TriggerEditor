"""``profile``: aggregate statistics of each column at a node. Never a row."""

from __future__ import annotations

from trigger_designer.cli.commands._node_data import run_data_command
from trigger_designer.cli.render import Out, Table, fmt
from trigger_designer.core.headless.node_inspect import profile_frame


def _build(policy, view, tables) -> dict:
    outputs = []
    for t in tables:
        stats = profile_frame(t.frame)
        outputs.append({"index": t.index, "name": t.name, **stats})
    return {"outputs": outputs}


COLUMNS = [
    "column",
    "dtype",
    "nulls",
    "distinct",
    "min",
    "max",
    "mean",
    "text length",
]
NUMERIC = ("nulls", "distinct", "min", "max", "mean")


def _length(col: dict) -> str:
    low, high = col.get("min_length"), col.get("max_length")
    return "" if low is None or high is None else f"{fmt(low)}-{fmt(high)}"


def _row(col: dict) -> list:
    return [
        col["name"],
        col["dtype"],
        fmt(col["nulls"]),
        fmt(col.get("distinct")),
        fmt(col.get("min")),
        fmt(col.get("max")),
        fmt(col.get("mean")),
        _length(col),
    ]


def render_text(envelope: dict, out: Out) -> None:
    node = envelope["node"]
    out.heading(f"node {node['id']}: {node['title']} ({node['op']})")
    for table in envelope["outputs"]:
        out.table(
            Table(
                COLUMNS,
                [_row(col) for col in table["columns"]],
                right=NUMERIC,
                title=f"output {table['index']} ({table['name']}): "
                f"{table['rows']:,} rows",
            )
        )
    out.note("Text columns show only their length range. More statistics: --json.")


def execute(args, ctx) -> int:
    return run_data_command(
        args,
        ctx,
        need="aggregates",
        what="column statistics",
        build=_build,
        render_text=render_text,
    )
