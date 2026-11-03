"""Everything a run decides before any node executes (plan 08 3.7 steps 3-6).

Pure and Qt-free: unit-testable without a window. ``build_run_plan`` reads the
workflow, applies parameters to a copy, checks inputs and outputs, stages the
outputs and writes the ASCII work copy the editor's loader will read.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from trigger_designer.core.headless.approvals import store_for
from trigger_designer.core.headless.atomic import StagedOutput, plan_staging
from trigger_designer.core.headless.exit_codes import CliError, ExitCode
from trigger_designer.core.headless.op_catalog import known_op, node_op
from trigger_designer.core.headless.params import (
    AppliedParams,
    PathRef,
    apply_params,
    parse_cli_params,
    read_param_defs,
    set_setting,
    write_workflow_ascii,
)
from trigger_designer.core.headless.state import ensure
from trigger_designer.core.headless.workflow_file import (
    Finding,
    WorkflowDoc,
    static_validate,
)

MB = 1024 * 1024


@dataclass
class RunOptions:
    params: dict[str, str] = field(default_factory=dict)
    input_dir: str | None = None
    output_dir: str | None = None
    record_dir: str | None = None
    timeout_s: float | None = 3600.0
    max_memory_mb: float | None = None
    threads: int | None = None
    cancel_grace_s: float = 10.0
    min_free_mb: int = 64
    create_output_dirs: bool = False
    strict: bool = False
    keep_going: bool = False
    allow_unapproved: bool = False
    allow_custom_code: bool = False
    dry_run: bool = False
    no_record: bool = False
    no_hash: bool = False
    emit_script: str | None = None
    log_format: str = "text"
    log_file: str | None = None
    verbosity: int = 0
    quiet: bool = False
    trigger: str = "manual"
    state_dir: str | None = None
    cwd: str | None = None
    capture_logs: bool = False

    @classmethod
    def from_args(cls, args: Any) -> RunOptions:
        return cls(
            params=parse_cli_params(getattr(args, "param", None) or []),
            input_dir=getattr(args, "input_dir", None),
            output_dir=getattr(args, "output_dir", None),
            record_dir=getattr(args, "record_dir", None),
            timeout_s=(getattr(args, "timeout", 3600.0) or None),
            max_memory_mb=getattr(args, "max_memory", None),
            threads=getattr(args, "threads", None),
            cancel_grace_s=getattr(args, "cancel_grace", 10.0),
            min_free_mb=getattr(args, "min_free_mb", 64),
            create_output_dirs=getattr(args, "create_output_dirs", False),
            strict=getattr(args, "strict", False),
            keep_going=getattr(args, "keep_going", False),
            allow_unapproved=getattr(args, "allow_unapproved", False),
            allow_custom_code=getattr(args, "allow_custom_code", False),
            dry_run=getattr(args, "dry_run", False),
            no_record=getattr(args, "no_record", False),
            no_hash=getattr(args, "no_hash", False),
            emit_script=getattr(args, "emit_script", None),
            log_format=getattr(args, "log_format", "text"),
            log_file=getattr(args, "log_file", None),
            verbosity=getattr(args, "verbose", 0),
            quiet=getattr(args, "quiet", False),
            trigger=getattr(args, "trigger", "manual"),
            state_dir=getattr(args, "state_dir", None),
        )


@dataclass
class RunPlan:
    doc: WorkflowDoc
    applied: AppliedParams
    staged: list[StagedOutput]
    io_paths: list[str]
    work_dir: Path
    work_copy: Path
    run_id: str
    params_resolved: dict[str, str]
    warnings: list[Finding]
    inputs: list[dict]
    outputs: list[dict]
    approval_sha256: str | None = None


def _node(data: dict, node_id) -> dict:
    return next(n for n in data["nodes"] if n.get("id") == node_id)


def check_trust(doc: WorkflowDoc, opts: RunOptions, state: Path) -> str | None:
    """Custom-code gate and approval pinning (3.11). Returns the approved sha."""
    store = store_for(state)
    approved = store.is_approved(doc.sha256)
    custom = [
        info
        for node in doc.nodes
        if (info := known_op(node_op(node) or "")) and info.custom_code
    ]
    if custom and not (opts.allow_custom_code and approved):
        raise CliError(
            ExitCode.REFUSED,
            "TD-CLI-011",
            "The workflow contains a node with user-written code.",
            "Run it with --allow-custom-code only if the file is approved and "
            "you trust its author.",
        )
    if approved:
        return doc.sha256
    unattended = opts.trigger == "schedule"
    if opts.allow_unapproved and not unattended:
        return None
    changed = store.changed_since_approval(doc.path, doc.sha256)
    if changed:
        raise CliError(
            ExitCode.REFUSED,
            "TD-CLI-008" if not unattended else "TD-CLI-009",
            "The workflow changed after it was approved"
            f" (approved {changed.get('approved_at')} by {changed.get('approved_by')}).",
            "Check who changed it, then approve it again with `approve`.",
        )
    raise CliError(
        ExitCode.REFUSED,
        "TD-CLI-008",
        "This workflow has not been approved to run.",
        "Review it with `approve <workflow>`; scheduled runs always need approval.",
    )


def _check_inputs(applied: AppliedParams) -> tuple[list[dict], list[str]]:
    from trigger_designer.core.inputs import (
        DEFAULT_EXCLUDE,
        InputReadError,
        detect_file_type,
        list_source_files,
    )

    rows: list[dict] = []
    io_paths: list[str] = []
    problems: list[InputReadError] = []
    for ref in applied.inputs:
        node = _node(applied.data, ref.node_id)
        content = node.get("content") or {}
        file_type = str(content.get("file_type") or detect_file_type(ref.path))
        io_paths.append(ref.path)
        try:
            listing = list_source_files(
                ref.path,
                file_type,
                include=list(content.get("include_patterns") or ()),
                exclude=list(content.get("exclude_patterns") or DEFAULT_EXCLUDE),
                recursive=bool(content.get("recursive", False)),
                order=str(content.get("file_order") or "name"),
                max_files=int(content.get("max_files") or 10000),
            )
        except InputReadError as exc:
            problems.append(exc)
            rows.append(
                {
                    "node_id": ref.node_id,
                    "path": ref.path,
                    "exists": False,
                    "size_bytes": None,
                }
            )
            continue
        io_paths.extend(f.path for f in listing.files)
        rows.append(
            {
                "node_id": ref.node_id,
                "path": ref.path,
                "exists": True,
                "files": len(listing.files),
                "size_bytes": sum(f.size_bytes for f in listing.files),
            }
        )
    if problems:
        first = problems[0]
        detail = "; ".join(p.message for p in problems)
        raise CliError(
            ExitCode.INVALID,
            first.code,
            detail,
            "Use --input-dir to remap saved paths, or fix the path in the editor.",
        )
    return rows, io_paths


def _check_outputs(
    applied: AppliedParams, opts: RunOptions, input_paths: list[str]
) -> list[PathRef]:
    seen: dict[str, PathRef] = {}
    inputs = {os.path.normcase(os.path.normpath(p)) for p in input_paths}
    for ref in applied.outputs:
        key = os.path.normcase(os.path.normpath(ref.path))
        if key in seen:
            raise CliError(
                ExitCode.INVALID,
                "TD-CLI-014",
                f"Two outputs would overwrite each other: {ref.path}",
                "Give each File Output its own file name.",
            )
        if key in inputs:
            raise CliError(
                ExitCode.INVALID,
                "TD-CLI-014",
                f"The output would overwrite an input file: {ref.path}",
                "Choose a different output file or folder.",
            )
        seen[key] = ref
        directory = os.path.dirname(ref.path) or "."
        if not os.path.isdir(directory):
            if not opts.create_output_dirs:
                raise CliError(
                    ExitCode.INVALID,
                    "TD-CLI-014",
                    f"The output folder does not exist: {directory}",
                    "Create it, or pass --create-output-dirs.",
                )
            if not opts.dry_run:
                os.makedirs(directory, exist_ok=True)
        if os.path.isdir(directory):
            _probe_writable(directory)
            free = shutil.disk_usage(directory).free
            if free < opts.min_free_mb * MB:
                raise CliError(
                    ExitCode.INVALID,
                    "TD-CLI-015",
                    f"Only {free // MB} MB free on the drive of {directory} "
                    f"(minimum {opts.min_free_mb} MB).",
                    "Free some space or choose another folder with --output-dir.",
                )
    return list(seen.values())


def _probe_writable(directory: str) -> None:
    probe = os.path.join(directory, f".td-probe-{uuid.uuid4().hex[:8]}")
    try:
        with open(probe, "wb"):
            pass
        os.unlink(probe)
    except OSError as exc:
        with contextlib.suppress(OSError):
            os.unlink(probe)
        raise CliError(
            ExitCode.INVALID,
            "TD-CLI-014",
            f"The output folder cannot be written: {directory} ({exc.strerror or exc})",
            "Check permissions.",
        ) from None


def build_run_plan(
    opts: RunOptions,
    doc: WorkflowDoc,
    state: Path,
    run_id: str | None = None,
    *,
    mode: str = "run",
    check_files: bool = True,
) -> RunPlan:
    """``mode``: ``run`` (everything), ``dry`` (no lock/files) or ``validate``
    (no approval gate; output folders are not required to exist)."""
    run_id = run_id or uuid.uuid4().hex
    run8 = run_id[:8]
    findings = static_validate(doc)
    errors = [f for f in findings if f.level == "error"]
    if errors:
        first = errors[0]
        raise CliError(
            ExitCode.INVALID,
            first.td_code,
            "; ".join(f.message for f in errors),
        )
    warnings = [f for f in findings if f.level == "warning"]
    if opts.strict and warnings:
        raise CliError(
            ExitCode.INVALID,
            warnings[0].td_code,
            "--strict: " + "; ".join(f.message for f in warnings),
        )
    approval = check_trust(doc, opts, state) if mode != "validate" else None
    defs = read_param_defs(doc)
    applied = apply_params(
        doc,
        defs,
        opts.params,
        input_dir=opts.input_dir,
        output_dir=opts.output_dir,
        cwd=opts.cwd or os.getcwd(),
    )
    if check_files:
        input_rows, io_paths = _check_inputs(applied)
    else:
        input_rows = [{"node_id": r.node_id, "path": r.path} for r in applied.inputs]
        io_paths = [r.path for r in applied.inputs]
    if mode == "validate":
        outputs = list(applied.outputs)
    else:
        outputs = _check_outputs(applied, opts, io_paths)
    staging_root = Path(state) / "staging"
    staged = plan_staging([(o.node_id, o.path) for o in outputs], run8, staging_root)
    for item, ref in zip(staged, outputs, strict=True):
        node = _node(applied.data, ref.node_id)
        set_setting(node["content"], ref.key, item.staged)
        io_paths.append(item.staged)
        if item.cross_volume:
            os.makedirs(os.path.dirname(item.staged), exist_ok=True)
    work_dir = ensure(Path(state), "work") / run_id
    work_dir.mkdir(parents=True, exist_ok=True)
    work_copy = work_dir / "workflow.tds"
    write_workflow_ascii(applied.data, work_copy)
    return RunPlan(
        doc=doc,
        applied=applied,
        staged=staged,
        io_paths=io_paths,
        work_dir=work_dir,
        work_copy=work_copy,
        run_id=run_id,
        params_resolved=dict(applied.resolved),
        warnings=warnings,
        inputs=input_rows,
        outputs=[
            {"node_id": item.node_id, "final": item.final, "staged": item.staged}
            for item in staged
        ],
        approval_sha256=approval,
    )


def cleanup_work(plan: RunPlan) -> None:
    shutil.rmtree(plan.work_dir, ignore_errors=True)
