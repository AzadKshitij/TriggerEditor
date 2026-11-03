"""Enrichment: upstream attribution, row/value location and knock-on errors."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from trigger_designer.core.errors.attribution import Ancestor, attribute_upstream
from trigger_designer.core.errors.builders import make_error
from trigger_designer.core.errors.catalogue import render_entry
from trigger_designer.core.errors.locator import (
    locate_conversion_failures,
    polars_dtype_from_name,
)
from trigger_designer.core.errors.model import ErrorContext, NodeError
from trigger_designer.core.errors.redact import redact_error

_LOCATABLE = {"TD-TYP-001", "TD-TYP-003", "TD-TYP-005"}


@dataclass
class EnrichJob:
    error: NodeError
    ancestors: tuple[Ancestor, ...] = ()
    inputs_of: dict[int, tuple[Any, ...]] = field(default_factory=dict)
    labels: dict[int, str] = field(default_factory=dict)
    attribute: bool = True
    locate: bool = True
    row_cap: int = 5_000_000
    redact: bool = False


@dataclass
class EnrichResult:
    root: NodeError
    knock_on: NodeError | None = None
    culprit_node_id: int | None = None


def _rebuild(
    error: NodeError,
    *,
    row: int | None = None,
    values: tuple[str, ...] = (),
    status: str = "",
    node_id: int | None = None,
) -> NodeError:
    params = dict(error.params)
    if row is not None:
        params["row"] = int(row)
    if values:
        params["value"] = values[0]
        params["values"] = ", ".join(values)
        if len(values) > 1:
            params["others_sentence"] = (
                f"{len(values) - 1} more value(s) are also invalid, "
                f"for example {', '.join(values[1:])}."
            )
        params["row_hint"] = f" (row {row:,})" if row is not None else ""
    title, detail, fixes = render_entry(error.code, params, located=row is not None)
    return error.with_updates(
        title=title or error.title,
        detail=detail or error.detail,
        hint=fixes[0] if fixes else error.hint,
        row_index=row if row is not None else error.row_index,
        sample_values=values or error.sample_values,
        locate_status=status or error.locate_status,
        node_id=node_id if node_id is not None else error.node_id,
        params=params,
    )


def enrich_error(job: EnrichJob) -> EnrichResult:
    """Never raises; returns the original error when anything goes wrong."""
    try:
        error = job.error
        culprit = error.culprit_node_id
        if job.attribute and culprit is None and job.ancestors:
            culprit = attribute_upstream(
                error.code,
                error.exc_type.split(".")[-1],
                job.ancestors,
                row_cap=min(job.row_cap, 100_000),
            )
        if culprit is not None and culprit != error.node_id:
            label = job.labels.get(culprit) or f"node {culprit}"
            error = error.with_updates(
                node_id=culprit,
                node_label=label,
                culprit_node_id=culprit,
                culprit_node_title=label,
            )
            error = _rebuild(error, node_id=culprit)

        target_id = culprit if culprit is not None else error.node_id
        if job.locate and error.code in _LOCATABLE and target_id is not None:
            params = dict(error.params)
            column = str(params.get("column", ""))
            target = polars_dtype_from_name(str(params.get("target", "")))
            known = params.get("value") if params.get("engine_duckdb") else None
            frames = job.inputs_of.get(target_id, ())
            located = locate_conversion_failures(
                frames,
                column,
                target,
                known_value=known,
                sum_mode=error.code == "TD-TYP-003",
                date_format=params.get("date_format"),
                row_cap=job.row_cap,
            )
            if located.status == "found":
                error = _rebuild(
                    error,
                    row=located.row_index,
                    values=located.values,
                    status="found",
                )
            else:
                error = error.with_updates(locate_status=located.status)
        elif not job.locate and error.code in _LOCATABLE:
            error = error.with_updates(locate_status="disabled")

        knock_on = None
        if (
            culprit is not None
            and error.node_id is not None
            and culprit != job.error.node_id
        ):
            origin = job.error
            ctx = ErrorContext(
                node_id=origin.node_id,
                node_title=origin.node_title,
                node_label=origin.node_label,
                op=origin.op,
                phase=origin.phase,
            )
            knock_on = make_error(
                "TD-RUN-003",
                ctx,
                culprit_label=job.labels.get(culprit, f"node {culprit}"),
                culprit_node_id=culprit,
                culprit_node_title=job.labels.get(culprit),
            )
        if job.redact:
            error = redact_error(error)
            if knock_on is not None:
                knock_on = redact_error(knock_on)
        return EnrichResult(root=error, knock_on=knock_on, culprit_node_id=culprit)
    except Exception:  # noqa: BLE001 - enrichment must never fail a run
        return EnrichResult(root=job.error, knock_on=None, culprit_node_id=None)


def enrich_sync(error: NodeError, **kwargs) -> EnrichResult:
    return enrich_error(EnrichJob(error=error, **kwargs))
