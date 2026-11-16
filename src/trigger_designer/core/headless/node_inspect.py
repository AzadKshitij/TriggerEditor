"""Look at the data at one node: its columns, aggregate statistics, or rows.

The pure helpers (``resolve_node``, ``upstream_ids``, ``column_profile_exprs``,
``jsonable``) need no Qt. ``open_node`` is the one entry point that loads the
workflow through the editor's own classes (like ``run``), executes only the
nodes the target depends on, and hands back the target's output tables as
Polars ``LazyFrame`` objects. It never executes a node that writes a file, and
the work copy it loads redirects every File Output into the staging folder
anyway.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import math
import shutil
from collections.abc import Iterator
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

from trigger_designer.core.headless.exit_codes import CliError, ExitCode
from trigger_designer.core.headless.op_catalog import known_op, node_op
from trigger_designer.core.headless.workflow_file import WorkflowDoc, _socket_owner

#: Nodes whose output is not a table (a chart, a note).
_NO_TABLE_OPS = ("report.comment", "report.graph")


@dataclass
class OutputTable:
    index: int
    name: str
    frame: Any  # polars.LazyFrame


@dataclass
class NodeView:
    node_id: int
    title: str
    op: str
    outputs: list[OutputTable] = field(default_factory=list)

    def header(self) -> dict:
        return {"id": self.node_id, "title": self.title, "op": self.op}


# ---------------------------------------------------------------- pure helpers
def _title(node: dict) -> str:
    return str(node.get("title") or node.get("node_title") or node.get("id") or "?")


def resolve_node(doc: WorkflowDoc, ref: str) -> dict:
    """The node dict named by ``ref``: an id, an exact title (any case), or an
    op id. Several matches, or none, is an error that lists the candidates."""
    nodes = doc.nodes
    text = str(ref).strip()
    matches: list[dict] = []
    if text.lstrip("-").isdigit():
        matches = [n for n in nodes if n.get("id") == int(text)]
    if not matches:
        wanted = text.casefold()
        matches = [n for n in nodes if _title(n).casefold() == wanted]
    if not matches:
        matches = [n for n in nodes if node_op(n) == text]
    if len(matches) == 1:
        return matches[0]
    listing = "; ".join(
        f"{n.get('id')} = {_title(n)} ({node_op(n) or '?'})" for n in nodes[:40]
    )
    if matches:
        raise CliError(
            ExitCode.INVALID,
            "TD-CLI-020",
            f"'{ref}' matches {len(matches)} nodes.",
            "Use the numeric id instead: "
            + "; ".join(f"{n.get('id')} = {_title(n)}" for n in matches),
        )
    raise CliError(
        ExitCode.INVALID,
        "TD-CLI-020",
        f"No node '{ref}' in this workflow.",
        f"Nodes: {listing or '(none)'}.",
    )


def upstream_ids(doc: WorkflowDoc, target_id: int) -> set[int]:
    """``target_id`` and every node it (transitively) reads from."""
    nodes = doc.nodes
    owner = _socket_owner(nodes)
    parents: dict[int, set[int]] = {}
    for edge in doc.data.get("edges", []):
        if not isinstance(edge, dict):
            continue
        src, dst = owner.get(edge.get("start")), owner.get(edge.get("end"))
        if src is None or dst is None:
            continue
        parents.setdefault(dst, set()).add(src)
    position = {n.get("id"): i for i, n in enumerate(nodes)}
    start = position.get(target_id)
    seen: set[int] = set()
    stack = [start] if start is not None else []
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        stack.extend(parents.get(cur, ()))
    return {nodes[i]["id"] for i in seen if isinstance(nodes[i].get("id"), int)}


def check_inspectable(node: dict) -> str:
    """The op id, or an error for a node with no table to look at."""
    op = node_op(node) or ""
    info = known_op(op)
    if info is None:
        raise CliError(
            ExitCode.INVALID,
            "TD-CLI-003",
            f"Node '{_title(node)}' has an unknown type ({op or 'no op id'}).",
        )
    if info.output_keys:
        raise CliError(
            ExitCode.INVALID,
            "TD-CLI-021",
            f"'{info.title}' writes a file and has no table of its own.",
            "Inspect the node that feeds it.",
        )
    if op in _NO_TABLE_OPS:
        raise CliError(
            ExitCode.INVALID,
            "TD-CLI-021",
            f"'{info.title}' produces no table.",
            "Inspect the node that feeds it.",
        )
    return op


def jsonable(value: Any) -> Any:
    """A cell value orjson can write: decimals and durations as text, bytes as
    hex, anything unknown as its ``str``."""
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dt.timedelta):
        return str(value)
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).hex()
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    return str(value)


# ------------------------------------------------------------- column profile
def column_profile_exprs(name: str, dtype: Any, key: str) -> dict[str, Any]:
    """Polars expressions for the aggregate statistics of one column.

    Returns ``{stat: expr}`` (the caller aliases them). Text columns get length
    and blank statistics only: no value, not even a minimum or maximum, ever
    leaves the table.
    """
    import polars as pl

    col = pl.col(name)
    exprs: dict[str, Any] = {"nulls": col.null_count()}
    nested = dtype.is_nested() or dtype == pl.Object or dtype == pl.Binary
    if not nested:
        exprs["distinct"] = col.drop_nulls().n_unique()
    if dtype == pl.Boolean:
        exprs["true_count"] = col.sum()
    elif dtype.is_numeric():
        exprs.update(
            min=col.min(),
            max=col.max(),
            mean=col.mean(),
            std=col.std(),
            sum=col.sum(),
            zeros=(col == 0).sum(),
            negatives=(col < 0).sum(),
        )
    elif dtype in (pl.Date, pl.Time, pl.Duration) or isinstance(dtype, pl.Datetime):
        exprs.update(min=col.min(), max=col.max())
    elif dtype == pl.String:
        exprs.update(
            min_length=col.str.len_chars().min(),
            max_length=col.str.len_chars().max(),
            blanks=(col.str.strip_chars() == "").sum(),
        )
    return {stat: expr.alias(f"{key}__{stat}") for stat, expr in exprs.items()}


def profile_frame(frame: Any) -> dict:
    """Aggregate statistics of a table: row count and one entry per column."""
    import polars as pl

    schema = frame.collect_schema()
    exprs: list[Any] = [pl.len().alias("__rows")]
    plan: list[tuple[int, str, Any, list[str]]] = []
    for i, (name, dtype) in enumerate(schema.items()):
        column = column_profile_exprs(name, dtype, f"c{i}")
        exprs.extend(column.values())
        plan.append((i, name, dtype, list(column)))
    row = frame.select(exprs).collect().row(0, named=True)
    rows = int(row["__rows"])
    columns = []
    for i, name, dtype, stats in plan:
        entry: dict[str, Any] = {"name": name, "dtype": str(dtype)}
        for stat in stats:
            entry[stat] = jsonable(row[f"c{i}__{stat}"])
        columns.append(entry)
    return {"rows": rows, "columns": columns}


def schema_of_frame(frame: Any) -> list[dict]:
    return [
        {"name": name, "dtype": str(dtype)}
        for name, dtype in frame.collect_schema().items()
    ]


def head_rows(frame: Any, n: int) -> list[dict]:
    return [jsonable(r) for r in frame.head(n).collect().to_dicts()]


# ------------------------------------------------------------------ the loader
def node_error(result: Any, node: Any) -> dict:
    """A structured, value-free error object for a node that failed."""
    from trigger_designer.core.audit.errors_adapter import error_to_dict

    err = error_to_dict(result, node, enrich=False, redact=True)
    return {
        "code": err.get("code"),
        "title": err.get("title"),
        "detail": err.get("detail"),
        "hint": err.get("hint"),
        "suggested_fixes": err.get("suggested_fixes", []),
        "columns": err.get("columns", []),
        "node_id": err.get("node_id"),
        "node_title": err.get("node_title"),
        "op": err.get("op"),
    }


class NodeFailed(CliError):
    """A node the target depends on failed; ``error`` is its structured error."""

    def __init__(self, error: dict) -> None:
        super().__init__(
            ExitCode.NODE_FAILED,
            str(error.get("code") or "TD-SYS-999"),
            str(error.get("title") or "A node failed."),
            str(error.get("hint") or ""),
        )
        self.error = error

    def to_dict(self) -> dict:
        base = super().to_dict()
        base.update(
            detail=self.error.get("detail"),
            suggested_fixes=self.error.get("suggested_fixes", []),
            columns=self.error.get("columns", []),
            node={
                "id": self.error.get("node_id"),
                "title": self.error.get("node_title"),
                "op": self.error.get("op"),
            },
        )
        return base


@contextlib.contextmanager
def open_node(args: Any, ctx: Any, doc: WorkflowDoc, node: dict) -> Iterator[NodeView]:
    """Load ``doc`` like the editor, run what ``node`` needs, yield its tables."""
    import polars as pl

    from trigger_designer.core.ExecutionCheck.executor import (
        NodeExecutor,
        SecurityConfig,
    )
    from trigger_designer.core.ExecutionCheck.run_loop import run_nodes
    from trigger_designer.core.headless.code_policy import (
        sandbox_code_filter,
        sandbox_globals,
    )
    from trigger_designer.core.headless.events import route_stray_stdout
    from trigger_designer.core.headless.plan import RunOptions, build_run_plan
    from trigger_designer.qt.headless import HeadlessSession, quiet_loguru

    op = check_inspectable(node)
    target_id = node["id"]
    needed = upstream_ids(doc, target_id)
    opts = RunOptions.from_args(args)
    plan = build_run_plan(opts, doc, ctx.state, mode="validate", check_files=False)
    session = None
    try:
        with route_stray_stdout():
            quiet_loguru(getattr(args, "verbose", 0))
            session = HeadlessSession()
            report = session.load(
                str(plan.work_copy),
                expect_nodes=len(doc.nodes),
                expect_edges=len(doc.data.get("edges", [])),
            )
            if report.unknown:
                raise CliError(
                    ExitCode.INVALID,
                    "TD-CLI-003",
                    "The workflow contains node types this build does not provide.",
                )
            ordered = [n for n in report.nodes if n.id in needed]
            target = next((n for n in ordered if n.id == target_id), None)
            if target is None:
                raise CliError(ExitCode.INVALID, "TD-CLI-020", "Node not loaded.")
            session.reevaluate()
            session.before_run(lambda *_a, **_k: None)
            timeout = float(getattr(args, "timeout", 600.0) or 600.0)
            executor = NodeExecutor(SecurityConfig(max_execution_time=timeout))
            executor.execution_context.clear()
            executor.execution_context.update(sandbox_globals())
            executor.code_filter = lambda code: sandbox_code_filter(code, plan.io_paths)
            failures: list[tuple[Any, Any]] = []
            errors: list[tuple[Any, BaseException]] = []

            def finished(node_, result) -> None:
                if not getattr(result, "success", False):
                    failures.append((node_, result))

            outcome = run_nodes(
                ordered,
                executor,
                upstream=session.upstream(),
                on_node_finished=finished,
                on_node_errored=lambda n, exc: errors.append((n, exc)),
            )
            executor.shutdown()
            if failures:
                node_, result = failures[0]
                raise NodeFailed(node_error(result, node_))
            if errors:
                node_, exc = errors[0]
                from trigger_designer.core.audit.errors_adapter import (
                    exception_to_dict,
                )

                raise NodeFailed(
                    {
                        **exception_to_dict(exc, node_, redact=True),
                        "node_id": node_.id,
                    }
                )
            if not outcome.success:
                raise CliError(
                    ExitCode.NODE_FAILED,
                    "TD-SYS-999",
                    "A node the target depends on did not run.",
                )
            specs, _edges = session.specs()
            names = next(
                (s.output_variables for s in specs if s.node_id == target_id), ()
            )
            outputs: list[OutputTable] = []
            for index, var in enumerate(names):
                value = executor.execution_context.get(var)
                if isinstance(value, pl.DataFrame):
                    value = value.lazy()
                if isinstance(value, pl.LazyFrame):
                    outputs.append(OutputTable(index, _output_name(op, index), value))
            if not outputs:
                raise CliError(
                    ExitCode.INVALID,
                    "TD-CLI-021",
                    f"'{_title(node)}' produced no table.",
                    "Check that the node is connected and complete.",
                )
        view = NodeView(target_id, _title(node), op, outputs)
        with route_stray_stdout():
            yield view
    finally:
        if session is not None:
            with contextlib.suppress(Exception):
                session.close()
        shutil.rmtree(plan.work_dir, ignore_errors=True)
        with contextlib.suppress(Exception):
            Path(ctx.state).joinpath("work").rmdir()


def _output_name(op: str, index: int) -> str:
    from trigger_designer.core.headless.node_spec import SOCKETS

    sockets = SOCKETS.get(op)
    if sockets and index < len(sockets.outputs):
        return sockets.outputs[index]
    return f"output{index}"
