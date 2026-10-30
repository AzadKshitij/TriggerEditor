"""Workpaper Output node logic without Qt: settings, spec resolution, generated code.

``DEFAULTS`` is the one list of node settings (schema, dock and tests share it).
Empty text settings mean "inherit": ``effective_spec`` fills them from the
Engagement preferences that the Qt side passes in (the core never reads
preferences, so a headless caller can build the same spec).
"""

from __future__ import annotations

import getpass
import json
from collections.abc import Mapping, Sequence
from typing import Any

from trigger_designer.core.workpaper.spec import SourceFile, WorkpaperSpec

DEFAULTS: dict[str, Any] = {
    "output_path": "",
    "if_exists": "version",
    "workpaper_ref": "",
    "client": "",
    "engagement": "",
    "period": "",
    "preparer": "",
    "prepared_date": "",
    "test_name": "",
    "objective": "",
    "procedure": "",
    "criteria": "",
    "amount_column": "",
    "value_decimals": 2,
    "row_limit": 100_000,
    "include_run_log": True,
    "include_workflow": True,
    "exceptions_sheet_name": "Exceptions",
    "logo_path": "",
    "source_files": "",  # one path per line
}

IF_EXISTS_LABELS = (
    ("version", "New version"),
    ("replace", "Replace"),
    ("fail", "Stop with error"),
)

ROLES = ("Exceptions", "Population", "Summary")


def run_node(frames: Sequence[Any], settings: Mapping[str, Any]) -> list:
    """Live evaluation never writes a workpaper; the sink has no output socket."""
    del frames, settings
    return []


def effective_spec(
    settings: Mapping[str, Any],
    engagement: Mapping[str, str] | None = None,
    *,
    app_version: str = "",
    default_user: str | None = None,
) -> WorkpaperSpec:
    """The spec the writer receives: node settings, then Engagement defaults."""
    s = {**DEFAULTS, **dict(settings or {})}
    eng = engagement or {}
    preparer = str(s["preparer"] or eng.get("preparer") or "")
    if not preparer:
        try:
            preparer = default_user if default_user is not None else getpass.getuser()
        except Exception:  # noqa: BLE001 - no user name on this machine
            preparer = ""
    test_name = str(s["test_name"] or "")
    return WorkpaperSpec(
        title=test_name or "Audit workpaper",
        preparer=preparer,
        purpose=str(s["objective"] or ""),
        output_path=str(s["output_path"] or "").replace("\\", "/"),
        workpaper_ref=str(s["workpaper_ref"] or ""),
        client=str(s["client"] or eng.get("client_name") or ""),
        engagement=str(s["engagement"] or eng.get("engagement_name") or ""),
        period=str(s["period"] or eng.get("period") or ""),
        prepared_date=str(s["prepared_date"] or "").strip(),
        test_name=test_name,
        procedure=str(s["procedure"] or ""),
        criteria=str(s["criteria"] or ""),
        amount_column=str(s["amount_column"] or ""),
        value_decimals=_int(s["value_decimals"], 2),
        row_limit=_int(s["row_limit"], 100_000),
        include_run_record=bool(s["include_run_log"]),
        include_workflow=bool(s["include_workflow"]),
        if_exists=str(s["if_exists"] or "version"),
        exceptions_sheet_name=str(s["exceptions_sheet_name"] or "Exceptions"),
        logo_path=str(s["logo_path"] or eng.get("logo_path") or ""),
        source_files=tuple(SourceFile(line) for line in _lines(s["source_files"])),
        app_version=app_version,
    )


def _lines(value: Any) -> list[str]:
    """Paths from a multi-line text (or a list) setting, blanks dropped."""
    items = value.splitlines() if isinstance(value, str) else list(value or [])
    return [str(item).strip() for item in items if str(item).strip()]


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except TypeError, ValueError:
        return default


def build_code(
    spec: WorkpaperSpec,
    input_vars: Sequence[str],
    *,
    workflow: Sequence[Mapping[str, Any]] | None = None,
    sources: Sequence[Mapping[str, Any]] | None = None,
) -> str:
    """Generated code of the node. User text only enters through ``json.dumps`` + ``!r``."""
    if not input_vars or not input_vars[0]:
        return "raise ValueError('Workpaper Output: connect the Exceptions input')\n"
    population = input_vars[1] if len(input_vars) > 1 and input_vars[1] else "None"
    summary = input_vars[2] if len(input_vars) > 2 and input_vars[2] else "None"
    workflow_json = json.dumps(list(workflow), ensure_ascii=False) if workflow else None
    sources_json = json.dumps(list(sources or []), ensure_ascii=False)
    return (
        "import polars as pl\n"
        "from trigger_designer.core.workpaper.node_runner import run_workpaper\n"
        f"_workpaper_result = run_workpaper(\n"
        f"    spec_json={spec.to_json()!r},\n"
        f"    exceptions={input_vars[0]},\n"
        f"    population={population},\n"
        f"    summary={summary},\n"
        f"    workflow_json={workflow_json!r},\n"
        f"    sources_json={sources_json!r},\n"
        ")\n"
    )
