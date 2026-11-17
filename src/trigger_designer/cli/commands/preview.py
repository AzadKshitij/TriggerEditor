"""``preview``: the first rows at a node. Needs ``rows`` access."""

from __future__ import annotations

from trigger_designer.cli.commands._node_data import DATA_NOTICE, run_data_command
from trigger_designer.cli.render import Out, Table
from trigger_designer.core.headless.exit_codes import CliError, ExitCode
from trigger_designer.core.headless.node_inspect import head_rows, schema_of_frame

DEFAULT_ROWS = 10


def _limit(args, policy) -> int:
    if args.rows < 1:
        raise CliError(ExitCode.INVALID, "TD-CLI-006", "--rows must be 1 or more.")
    return min(args.rows, policy.max_rows)


def _build_for(args):
    def build(policy, view, tables) -> dict:
        limit = _limit(args, policy)
        return {
            "notice": DATA_NOTICE,
            "rows_requested": args.rows,
            "rows_limit": limit,
            "limited_by_policy": limit < args.rows,
            "outputs": [
                {
                    "index": t.index,
                    "name": t.name,
                    "columns": schema_of_frame(t.frame),
                    "rows": head_rows(t.frame, limit),
                }
                for t in tables
            ],
        }

    return build


#: Longest cell shown in text mode; ``--json`` carries every value in full.
MAX_CELL = 40


def render_text(envelope: dict, out: Out) -> None:
    node = envelope["node"]
    out.heading(f"node {node['id']}: {node['title']} ({node['op']})")
    out.note(envelope["notice"])
    if envelope["limited_by_policy"]:
        out.line(f"(limited to {envelope['rows_limit']} rows by the access policy)")
    for table in envelope["outputs"]:
        names = [c["name"] for c in table["columns"]]
        out.table(
            Table(
                names,
                [[row[n] for n in names] for row in table["rows"]],
                title=f"output {table['index']} ({table['name']}): "
                f"{len(table['rows'])} rows",
                max_cell=MAX_CELL,
            )
        )


def execute(args, ctx) -> int:
    return run_data_command(
        args,
        ctx,
        need="rows",
        what="reading rows",
        build=_build_for(args),
        render_text=render_text,
        before=lambda policy: _limit(args, policy),
    )
