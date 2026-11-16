"""``schema``: the column names and types at a node. Never a value."""

from __future__ import annotations

from trigger_designer.cli.commands._node_data import run_data_command
from trigger_designer.cli.render import Out, Table
from trigger_designer.core.headless.node_inspect import schema_of_frame


def _build(policy, view, tables) -> dict:
    return {
        "outputs": [
            {
                "index": t.index,
                "name": t.name,
                "columns": schema_of_frame(t.frame),
            }
            for t in tables
        ]
    }


def render_text(envelope: dict, out: Out) -> None:
    node = envelope["node"]
    out.heading(f"node {node['id']}: {node['title']} ({node['op']})")
    for table in envelope["outputs"]:
        out.table(
            Table(
                ["column", "dtype"],
                [[c["name"], c["dtype"]] for c in table["columns"]],
                title=f"output {table['index']} ({table['name']}): "
                f"{len(table['columns'])} columns",
            )
        )


def execute(args, ctx) -> int:
    return run_data_command(
        args,
        ctx,
        need="schema_only",
        what="reading the schema",
        build=_build,
        render_text=render_text,
    )
