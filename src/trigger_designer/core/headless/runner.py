"""Run a saved workflow without a window (plan 08 3.7, S7).

``run_workflow_file`` is the library entry point and what ``trigger-designer-cli
run`` calls. Everything before the first Qt import is Qt-free; the nodes are the
editor's own, loaded on the offscreen platform (``qt/headless.py``).
"""

from __future__ import annotations

import contextlib
import os
import shutil
import socket
import sys
import threading
import traceback
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from trigger_designer.core.constants import VERSION
from trigger_designer.core.headless.atomic import (
    StagedOutput,
    commit_all,
    discard_all,
    write_json_atomic,
)
from trigger_designer.core.headless.context import CliContext
from trigger_designer.core.headless.events import (
    Emitter,
    attach_loguru_bridge,
    route_stray_stdout,
)
from trigger_designer.core.headless.exit_codes import CliError, ExitCode, combine
from trigger_designer.core.headless.locks import RunLock, lock_path
from trigger_designer.core.headless.plan import (
    RunOptions,
    RunPlan,
    build_run_plan,
    cleanup_work,
)
from trigger_designer.core.headless.state import data_dir, ensure, state_dir
from trigger_designer.core.headless.supervisor import Supervisor
from trigger_designer.core.headless.workflow_file import (
    Finding,
    WorkflowDoc,
    read_workflow,
)


@dataclass
class RunOutcome:
    exit_code: int
    status: str
    record: Any = None
    record_path: str | None = None
    errors: list = field(default_factory=list)
    run_id: str = ""
    nodes_ok: int = 0
    nodes_failed: int = 0
    events: list = field(default_factory=list)


def _status_for(code: ExitCode) -> str:
    return {
        ExitCode.OK: "ok",
        ExitCode.CANCELLED: "cancelled",
        ExitCode.REFUSED: "refused",
        ExitCode.INVALID: "invalid",
        ExitCode.BUSY: "invalid",
    }.get(code, "failed")


def _options(
    input_overrides, input_dir, output_dir, record_dir, timeout_s, extra
) -> RunOptions:
    opts = RunOptions(
        **{k: v for k, v in extra.items() if k in RunOptions.__dataclass_fields__}
    )
    if input_overrides:
        opts.params = {**opts.params, **dict(input_overrides)}
    if input_dir is not None:
        opts.input_dir = input_dir
    if output_dir is not None:
        opts.output_dir = output_dir
    if record_dir is not None:
        opts.record_dir = record_dir
    opts.timeout_s = timeout_s or None
    return opts


def _error_rows(record: Any) -> list[dict]:
    rows = []
    for node in getattr(record, "nodes", []) or []:
        if getattr(node, "status", "") != "failed":
            continue
        error = node.error or {}
        rows.append(
            {
                "node_id": node.node_id,
                "title": error.get("title") or node.title,
                "code": error.get("code"),
                "message": error.get("detail") or error.get("title"),
                "hint": error.get("hint"),
                "node": node.title,
            }
        )
    return rows


class _Run:
    def __init__(
        self,
        path: str,
        opts: RunOptions,
        ctx: CliContext | None,
        install_signals: bool,
        exit_fn,
    ):
        self.path = path
        self.opts = opts
        self.state = ctx.state if ctx else state_dir(opts.state_dir)
        self.cli_id = uuid.uuid4().hex
        emitter = ctx.emitter if ctx and ctx.emitter else None
        self.emitter = emitter or Emitter(
            opts.log_format, opts.log_file, run_id=self.cli_id, quiet=opts.quiet
        )
        self.emitter.run_id = self.cli_id
        self.install_signals = install_signals
        self.exit_fn = exit_fn
        self.doc: WorkflowDoc | None = None
        self.plan: RunPlan | None = None
        self.lock: RunLock | None = None
        self.session = None
        self.recorder = None
        self.record = None
        self.sup: Supervisor | None = None
        self.nodes_by_id: dict = {}
        self.current_node_id = None
        self.committed = False
        self._record_done = False
        self._provider_installed = False
        self._guard = threading.RLock()
        self._announced = False
        self.outcome: RunOutcome | None = None

    # ------------------------------------------------------------ events
    def emit(self, event: str, level: str = "INFO", **fields) -> None:
        self.emitter.emit(event, level, **fields)

    def _on_node_event(self, event: str, level: str = "INFO", **fields) -> None:
        if event == "node.started":
            self.current_node_id = fields.get("node_id")
        elif event == "node.finished":
            self.current_node_id = None
        self.emit(event, level, **fields)

    def _warn(self, message: str, node_id=None) -> None:
        self.emit("warning", "WARNING", message=message, node_id=node_id)

    # ------------------------------------------------------------ outcome
    def announce(
        self,
        code: ExitCode,
        *,
        status: str | None = None,
        errors: list | None = None,
        record_path: str | None = None,
        nodes_ok: int = 0,
        nodes_failed: int = 0,
        record: Any = None,
    ) -> RunOutcome:
        """Emit ``run.finished`` exactly once and build the outcome."""
        with self._guard:
            if self._announced and self.outcome is not None:
                return self.outcome
            self._announced = True
            status = status or _status_for(code)
            duration = self.sup.elapsed() if self.sup else 0.0
            self.emit(
                "run.finished",
                "INFO" if code == ExitCode.OK else "ERROR",
                status=status,
                exit_code=int(code),
                duration_s=round(duration, 3),
                nodes_ok=nodes_ok,
                nodes_failed=nodes_failed,
                record_path=record_path,
                record_run_id=getattr(record, "run_id", None),
                errors=errors or [],
            )
            self.outcome = RunOutcome(
                exit_code=int(code),
                status=status,
                record=record,
                record_path=record_path,
                errors=errors or [],
                run_id=self.cli_id,
                nodes_ok=nodes_ok,
                nodes_failed=nodes_failed,
                events=list(self.emitter.events),
            )
            return self.outcome

    def _fail(self, exc: CliError) -> RunOutcome:
        row = {
            "node_id": None,
            "title": exc.message,
            "code": exc.td_code,
            "message": exc.message,
            "hint": exc.hint,
        }
        return self.announce(exc.code, errors=[row])

    # ------------------------------------------------------------ cleanup
    def _install_record_provider(self) -> None:
        """Let the workpaper read the in-flight record (its Run log sheet).

        Mirrors ``RunSession.start`` in the GUI. Not installed with
        ``--no-record``: the recorder keeps nothing then, and the workpaper
        reports that run recording is off.
        """
        if self.opts.no_record or self.recorder is None:
            return
        from trigger_designer.core.audit.recorder import set_run_record_provider

        recorder = self.recorder

        def provider() -> dict | None:
            try:
                return recorder.snapshot()
            except Exception:  # noqa: BLE001 - never fail a node over the Run log
                return None

        set_run_record_provider(provider)
        self._provider_installed = True

    def _clear_record_provider(self) -> None:
        if not self._provider_installed:
            return
        self._provider_installed = False
        with contextlib.suppress(Exception):
            from trigger_designer.core.audit.recorder import set_run_record_provider

            set_run_record_provider(None)

    def cleanup(self) -> None:
        self._clear_record_provider()
        if self.sup:
            self.sup.stop()
        if self.plan and not self.committed:
            discard_all(self.plan.staged)
        if self.lock:
            self.lock.release()
        if self.plan:
            cleanup_work(self.plan)

    # ------------------------------------------------------------ forced exit
    def force_cleanup(self, code: ExitCode, reason: str) -> None:
        """Called by the supervisor right before ``os._exit``."""
        with contextlib.suppress(Exception):
            node = self.nodes_by_id.get(self.current_node_id)
            from trigger_designer.core.ExecutionCheck.executor import (
                ExecutionTimeoutError,
            )

            seconds = f"{self.opts.timeout_s or 0:g}"
            exc: BaseException | None = {
                ExitCode.TIMEOUT: ExecutionTimeoutError(
                    f"Node execution timed out after {seconds} seconds"
                ),
                ExitCode.MEMORY: MemoryError("The run exceeded --max-memory."),
                ExitCode.CANCELLED: KeyboardInterrupt("The run was cancelled."),
            }.get(code)
            if node is not None and exc is not None and self.recorder and self.record:
                self.recorder.node_errored(self.record, node, exc)
        final = self._seal(False, code == ExitCode.CANCELLED, [])
        with contextlib.suppress(Exception):
            self.cleanup()
        self.announce(
            code,
            errors=_error_rows(final),
            record_path=self.recorder.last_path if self.recorder else None,
            nodes_ok=sum(1 for n in getattr(final, "nodes", []) if n.status == "ok"),
            nodes_failed=sum(
                1 for n in getattr(final, "nodes", []) if n.status == "failed"
            ),
            record=final,
        )
        with contextlib.suppress(Exception):
            self.emitter.close()

    def _seal(self, ok: bool, cancelled: bool, outputs: list) -> Any:
        """``recorder.finish`` exactly once (normal path and forced exit share it)."""
        with self._guard:
            if self._record_done or self.recorder is None or self.record is None:
                return getattr(self, "_final", None)
            self._record_done = True
            try:
                self._final = self.recorder.finish(
                    self.record,
                    ok,
                    cancelled=cancelled,
                    outputs=outputs,
                    save=not self.opts.no_record,
                )
            except Exception:  # noqa: BLE001
                traceback.print_exc(file=sys.stderr)
                self._final = None
            return self._final

    # ------------------------------------------------------------ main flow
    def execute(self) -> RunOutcome:
        try:
            with route_stray_stdout():
                return self._execute()
        except CliError as exc:
            return self._fail(exc)
        except KeyboardInterrupt:
            return self.announce(ExitCode.CANCELLED, status="cancelled")
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc(file=sys.stderr)
            self._seal(False, False, [])
            return self._fail(
                CliError(ExitCode.INTERNAL, "TD-SYS-999", f"Internal error: {exc}")
            )
        finally:
            self.cleanup()

    def _execute(self) -> RunOutcome:
        opts = self.opts
        if opts.threads:
            os.environ["POLARS_MAX_THREADS"] = str(opts.threads)
        if opts.capture_logs:
            level = {0: "WARNING", 1: "INFO"}.get(opts.verbosity, "DEBUG")
            attach_loguru_bridge(self.emitter, level)
        self.sup = Supervisor(
            deadline_s=opts.timeout_s,
            max_memory_mb=opts.max_memory_mb,
            cancel_grace_s=opts.cancel_grace_s,
            emit=self.emit,
            on_force=self.force_cleanup,
            exit_fn=self.exit_fn,
        )
        doc = self.doc = read_workflow(self.path)
        self.emit(
            "run.started",
            workflow=os.path.abspath(self.path),
            sha256=doc.sha256,
            trigger=opts.trigger,
            pid=os.getpid(),
            version=VERSION,
            dry_run=opts.dry_run,
            params=dict(opts.params),
        )
        plan = self.plan = build_run_plan(
            opts, doc, self.state, self.cli_id, mode="dry" if opts.dry_run else "run"
        )
        self.emit(
            "plan.resolved",
            approved=plan.approval_sha256 is not None,
            params=plan.params_resolved,
            inputs=plan.inputs,
            outputs=plan.outputs,
            warnings=[w.to_dict() for w in plan.warnings],
        )
        for finding in plan.warnings:
            self._warn(f"{finding.td_code}: {finding.message}", finding.node_id)
        if opts.dry_run:
            return self._dry_run()

        self.lock = RunLock(lock_path(self.state, self.path), self.cli_id)
        self.lock.acquire()
        self.lock.note_staged(
            [
                {
                    "final": s.final,
                    "staged": s.staged,
                    "backup": s.backup_path,
                }
                for s in plan.staged
            ]
        )
        if self.install_signals:
            self.sup.install_signal_handlers()
        self.sup.start_watchdog()

        from trigger_designer.qt.headless import HeadlessSession

        session = self.session = HeadlessSession()
        report = session.load(
            str(plan.work_copy),
            expect_nodes=len(doc.nodes),
            expect_edges=len(doc.data.get("edges", [])),
        )
        self._gate_load_report(report)
        self.nodes_by_id = {n.id: n for n in report.nodes}
        self._run_nodes(session, report)
        assert self.outcome is not None
        return self.outcome

    def _gate_load_report(self, report) -> None:
        if report.unknown:
            names = ", ".join(
                str(getattr(n, "missing_op", "?")) for n in report.unknown
            )
            raise CliError(
                ExitCode.INVALID,
                "TD-CLI-003",
                f"The workflow contains node types this build does not provide: {names}.",
            )
        for message in report.validation:
            self._warn(message)
        for level, message in report.messages:
            if level in ("WARNING", "ERROR", "CRITICAL"):
                self._warn(message)
        if self.opts.strict:
            problems = [getattr(n, "node_title", "?") for n in report.invalid] + list(
                report.validation
            )
            if problems:
                raise CliError(
                    ExitCode.INVALID,
                    "TD-CLI-006",
                    "--strict: " + "; ".join(str(p) for p in problems),
                )

    # ------------------------------------------------------------ dry run
    def _dry_run(self) -> RunOutcome:
        from trigger_designer.core.headless.code_policy import (
            CodePolicyError,
            validate_generated_code,
        )
        from trigger_designer.qt.headless import HeadlessSession

        plan = self.plan
        assert plan is not None
        session = self.session = HeadlessSession()
        report = session.load(
            str(plan.work_copy),
            expect_nodes=len(self.doc.nodes),
            expect_edges=len(self.doc.data.get("edges", [])),
        )
        self._gate_load_report(report)
        session.reevaluate()
        from trigger_designer.qt.headless import apply_test_hooks

        for node in report.nodes:
            try:
                apply_test_hooks(node)
                validate_generated_code(node.get_code(), io_paths=plan.io_paths)
            except CodePolicyError as exc:
                raise CliError(
                    ExitCode.REFUSED,
                    "TD-CLI-010",
                    f"The safety policy refused '{node.node_title}': {exc.reason}",
                    "Open the workflow in the editor and look at that node; do not "
                    "run files you do not trust.",
                ) from None
            except CliError:
                raise
            except Exception as exc:  # noqa: BLE001 - a node that cannot make code
                self._warn(f"{node.node_title}: no code ({exc})", node.id)
        self._emit_script(report, {})
        return self.announce(ExitCode.OK, nodes_ok=0)

    def _emit_script(self, report, codes: dict) -> None:
        target = self.opts.emit_script
        if not target or self.session is None:
            return
        try:
            self.session.window._last_run_codes = codes
            self.session.emit_script(target)
            self.emit("script.written", path=os.path.abspath(target))
        except Exception as exc:  # noqa: BLE001
            self._warn(f"--emit-script failed: {exc}")

    # ------------------------------------------------------------ real run
    def _run_nodes(self, session, report) -> None:
        from dataclasses import replace as dc_replace

        from trigger_designer.core.audit.recorder import AuditOptions, RunRecorder
        from trigger_designer.core.audit.store import RunStore
        from trigger_designer.core.ExecutionCheck.executor import (
            NodeExecutor,
            SecurityConfig,
        )
        from trigger_designer.core.headless.code_policy import (
            sandbox_code_filter,
            sandbox_globals,
        )
        from trigger_designer.qt.headless import execute_nodes

        opts, plan, sup = self.opts, self.plan, self.sup
        assert plan is not None and sup is not None
        session.reevaluate()

        executor = NodeExecutor(
            SecurityConfig(
                max_execution_time=(opts.timeout_s + 5) if opts.timeout_s else 1e9
            )
        )
        executor.execution_context.clear()
        executor.execution_context.update(sandbox_globals())
        executor.code_filter = lambda code: sandbox_code_filter(code, plan.io_paths)

        audit = AuditOptions(
            hash_inputs=not opts.no_hash,
            hash_outputs=not opts.no_hash,
            store_dir=opts.record_dir or "",
            app_data_dir=str(data_dir()),
            enabled=not opts.no_record,
        )
        recorder = self.recorder = RunRecorder(RunStore("", data_dir()), audit)
        recorder.error_enricher = session.enricher()
        specs, edges = session.specs()
        specs = _restore_final_paths(specs, plan.staged, dc_replace)
        scene = session.window.scene
        self.record = recorder.begin(
            self.path,
            specs,
            app_version=VERSION,
            edges=edges,
            workflow_uuid=self.doc.metadata.get("workflow_uuid")
            or getattr(scene, "workflow_uuid", None),
            modified_since_save=False,
        )
        executor.before_node = recorder.before_node
        executor.after_node = recorder.after_node
        self._install_record_provider()
        session.before_run(self._warn)

        codes: dict = {}
        ok_ids: set = set()
        result: dict = {}

        def on_event(event, level="INFO", **fields):
            if event == "node.finished" and fields.get("status") == "ok":
                ok_ids.add(fields.get("node_id"))
            self._on_node_event(event, level, **fields)

        def target() -> None:
            try:
                result["loop"] = execute_nodes(
                    report.nodes,
                    executor,
                    cancel=sup.cancel,
                    on_event=on_event,
                    recorder=recorder,
                    record=self.record,
                    keep_going=opts.keep_going,
                    upstream=session.upstream(),
                    codes=codes,
                )
            except BaseException as exc:  # noqa: BLE001
                result["exc"] = exc

        runner = threading.Thread(target=target, daemon=True, name="td-runner")
        runner.start()
        try:
            sup.poll(runner)
        finally:
            executor.shutdown()
            self._clear_record_provider()
        self._finish_run(report, result, ok_ids, codes)

    def _finish_run(self, report, result: dict, ok_ids: set, codes: dict) -> None:
        from trigger_designer.core.audit.fingerprint import fingerprint_file

        opts, plan = self.opts, self.plan
        assert plan is not None
        loop, exc = result.get("loop"), result.get("exc")
        cancelled = bool(loop and loop.cancelled)
        failed = bool(loop and loop.failed)
        refused = isinstance(exc, CliError) and exc.code == ExitCode.REFUSED
        internal = exc is not None and not isinstance(exc, CliError)
        extra_errors: list[dict] = []
        if isinstance(exc, CliError):
            extra_errors.append(_cli_row(exc))
        if internal:
            traceback.print_exception(exc, file=sys.stderr)
            extra_errors.append(
                _cli_row(
                    CliError(ExitCode.INTERNAL, "TD-SYS-999", f"Internal error: {exc}")
                )
            )

        if cancelled or refused or internal:
            to_commit: list[StagedOutput] = []
        elif not failed:
            to_commit = list(plan.staged)
        elif opts.keep_going:
            to_commit = [s for s in plan.staged if s.node_id in ok_ids]
        else:
            to_commit = []

        commit_failed = False
        fingerprints: list = []
        if to_commit:
            try:
                commit_all(to_commit)
                self.committed = True
            except CliError as cexc:
                commit_failed = True
                extra_errors.append(_cli_row(cexc))
                self.emit(
                    "output.commit_failed", "ERROR", path=cexc.message, error=cexc.hint
                )
            else:
                for staged in to_commit:
                    fp = fingerprint_file(
                        staged.final,
                        "output",
                        staged.node_id,
                        hash_enabled=not opts.no_hash,
                    )
                    fingerprints.append(fp)
                    self.emit(
                        "output.committed",
                        path=staged.final,
                        size_bytes=fp.size_bytes,
                        sha256=fp.sha256,
                    )
        discard_all([s for s in plan.staged if s not in to_commit or commit_failed])

        codes_found = []
        if cancelled:
            codes_found.append(ExitCode.CANCELLED)
        if commit_failed:
            codes_found.append(ExitCode.COMMIT_FAILED)
        if failed:
            codes_found.append(ExitCode.NODE_FAILED)
        code = combine(*codes_found)
        if refused and code in (ExitCode.OK, ExitCode.NODE_FAILED):
            code = ExitCode.REFUSED
        if internal and code in (ExitCode.OK, ExitCode.NODE_FAILED):
            code = ExitCode.INTERNAL
        ok = code == ExitCode.OK

        self._emit_script(report, codes)
        final = self._seal(ok, cancelled, [] if commit_failed else fingerprints)
        node_rows = _error_rows(final)
        known = {row["code"] for row in extra_errors}
        rows = extra_errors + [r for r in node_rows if r["code"] not in known]
        nodes = getattr(final, "nodes", []) or []
        record_path = self.recorder.last_path if self.recorder else None
        self._write_sidecar(final, code, plan)
        self.announce(
            code,
            errors=rows,
            record_path=record_path,
            nodes_ok=sum(1 for n in nodes if n.status == "ok"),
            nodes_failed=sum(1 for n in nodes if n.status == "failed"),
            record=final,
        )

    def _write_sidecar(self, final, code: ExitCode, plan: RunPlan) -> None:
        if final is None or self.opts.no_record:
            return
        try:
            folder = ensure(self.state, "logs")
            write_json_atomic(
                folder / f"{final.run_id}.cli.json",
                {
                    "argv": sys.argv,
                    "params_resolved": plan.params_resolved,
                    "exit_code": int(code),
                    "trigger": self.opts.trigger,
                    "approval_sha256": plan.approval_sha256,
                    "host": socket.gethostname(),
                    "record": self.recorder.last_path if self.recorder else None,
                    "staged": [
                        {"final": s.final, "node_id": s.node_id} for s in plan.staged
                    ],
                },
            )
        except Exception as exc:  # noqa: BLE001
            self._warn(f"could not write the run sidecar: {exc}")


def _cli_row(exc: CliError) -> dict:
    return {
        "node_id": None,
        "title": exc.message,
        "code": exc.td_code,
        "message": exc.message,
        "hint": exc.hint,
    }


def _restore_final_paths(specs, staged: list[StagedOutput], dc_replace) -> list:
    """The record describes the final paths, never the staged ones."""
    mapping = {os.path.normcase(os.path.normpath(s.staged)): s.final for s in staged}
    if not mapping:
        return specs

    def fix(value):
        if isinstance(value, str):
            return mapping.get(os.path.normcase(os.path.normpath(value)), value)
        if isinstance(value, dict):
            return {k: fix(v) for k, v in value.items()}
        if isinstance(value, list):
            return [fix(v) for v in value]
        if isinstance(value, tuple):
            return tuple(fix(v) for v in value)
        return value

    return [
        dc_replace(
            spec,
            settings=fix(spec.settings),
            output_files=tuple(fix(item) for item in spec.output_files),
        )
        for spec in specs
    ]


def run_workflow_file(
    path: str,
    *,
    input_overrides: dict | None = None,
    input_dir: str | None = None,
    output_dir: str | None = None,
    record_dir: str | None = None,
    timeout_s: float | None = 3600.0,
    ctx: CliContext | None = None,
    install_signals: bool = False,
    exit_fn=os._exit,
    **opts: Any,
) -> RunOutcome:
    """Run ``path`` and return its :class:`RunOutcome` (never raises ``CliError``)."""
    options = _options(
        input_overrides, input_dir, output_dir, record_dir, timeout_s, opts
    )
    return run_with_options(path, options, ctx, install_signals, exit_fn)


def run_with_options(
    path: str,
    options: RunOptions,
    ctx: CliContext | None = None,
    install_signals: bool = False,
    exit_fn=os._exit,
) -> RunOutcome:
    return _Run(path, options, ctx, install_signals, exit_fn).execute()


def deep_validate(doc: WorkflowDoc, args: Any, ctx: CliContext) -> list[Finding]:
    """``validate --deep``: plan, load like the editor, check each node's code."""
    from trigger_designer.core.headless.code_policy import (
        CodePolicyError,
        validate_generated_code,
    )
    from trigger_designer.core.headless.workflow_file import static_validate

    findings = static_validate(doc)
    if any(f.level == "error" for f in findings):
        return findings
    opts = RunOptions.from_args(args)
    plan = None
    try:
        plan = build_run_plan(
            opts,
            doc,
            ctx.state,
            mode="validate",
            check_files=not getattr(args, "no_files", False),
        )
    except CliError as exc:
        findings.append(Finding("error", exc.td_code, exc.message))
        return findings
    try:
        from trigger_designer.qt.headless import HeadlessSession, quiet_loguru

        quiet_loguru(getattr(args, "verbose", 0))
        session = HeadlessSession()
        try:
            report = session.load(
                str(plan.work_copy),
                expect_nodes=len(doc.nodes),
                expect_edges=len(doc.data.get("edges", [])),
            )
        except CliError as exc:
            findings.append(Finding("error", exc.td_code, exc.message))
            return findings
        for node in report.unknown:
            findings.append(
                Finding(
                    "error",
                    "TD-CLI-003",
                    f"unknown node type '{getattr(node, 'missing_op', '?')}'",
                    node.id,
                )
            )
        for message in report.validation:
            findings.append(Finding("warning", "TD-CLI-006", message))
        for node in report.invalid:
            findings.append(
                Finding(
                    "warning",
                    "TD-CLI-006",
                    f"'{node.node_title}' is incomplete",
                    node.id,
                )
            )
        if not report.unknown:
            session.reevaluate()
            for node in report.nodes:
                try:
                    validate_generated_code(node.get_code(), io_paths=plan.io_paths)
                except CodePolicyError as exc:
                    findings.append(
                        Finding(
                            "error",
                            "TD-CLI-010",
                            f"'{node.node_title}': {exc.reason}",
                            node.id,
                        )
                    )
                except Exception:  # noqa: BLE001, S110 - no code is a node problem, not policy
                    pass
        session.close()
    finally:
        if plan is not None:
            shutil.rmtree(plan.work_dir, ignore_errors=True)
        with contextlib.suppress(Exception):
            Path(ctx.state).joinpath("work").rmdir()
    return findings
