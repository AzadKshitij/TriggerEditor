"""The entry point generated code calls (Run Workflow) and headless callers use.

``run_workpaper`` takes resolved values only (JSON text and frames), never
preferences or Qt objects, so the CLI can call it too.
"""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

import polars as pl
from loguru import logger

from trigger_designer.core.workpaper.context import current_run_record
from trigger_designer.core.workpaper.spec import SourceFile, TestInfo, WorkpaperSpec


def _summary_info(summary: pl.LazyFrame | pl.DataFrame | None) -> TestInfo | None:
    if summary is None:
        return None
    frame = (
        summary.limit(1).collect()
        if isinstance(summary, pl.LazyFrame)
        else summary.head(1)
    )
    return TestInfo.from_frame(frame)


def run_workpaper(
    *,
    spec_json: str,
    exceptions: pl.LazyFrame | pl.DataFrame,
    population: pl.LazyFrame | pl.DataFrame | None = None,
    summary: pl.LazyFrame | pl.DataFrame | None = None,
    workflow_json: str | None = None,
    sources_json: str = "[]",
) -> dict[str, Any]:
    """Write the workpaper; returns ``WorkpaperResult.to_dict()``."""
    from trigger_designer.core.workpaper.writer import write_workpaper

    spec = WorkpaperSpec.from_json(spec_json)
    extra = tuple(
        SourceFile.from_mapping(item)
        if isinstance(item, dict)
        else SourceFile(str(item))
        for item in json.loads(sources_json or "[]")
    )
    if extra:
        spec = replace(spec, source_files=(*spec.source_files, *extra))
    workflow = json.loads(workflow_json) if workflow_json else None
    result = write_workpaper(
        spec,
        exceptions,
        population=population,
        test=_summary_info(summary),
        run_record=current_run_record() if spec.include_run_record else None,
        workflow=workflow,
    )
    print(f"[SUCCESS] Workpaper written to {result.path}")
    for line in result.warnings:
        logger.info("Workpaper: {}", line)
    for sheet, reason in result.omitted.items():
        logger.info("Workpaper: the {} sheet was omitted: {}", sheet, reason)
    if result.truncated:
        logger.warning(
            "Workpaper: only {:,} of {:,} exceptions are listed; the full list is in {}",
            result.exceptions_written,
            result.exceptions_total,
            result.csv_path,
        )
    return result.to_dict()
