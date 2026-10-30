"""The only module that imports Qt for the command line (plan 08 3.1, S6).

``trigger-designer-cli run`` loads a workflow through the editor's own
``TriggerSubWindow`` on the offscreen platform, so the code each node runs is
produced by exactly the classes the GUI uses. Nothing here is imported by the
Qt-free commands (``info``, ``approve``, ``verify-log`` ...).
"""

from __future__ import annotations

import contextlib
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

from trigger_designer.core.headless.exit_codes import CliError, ExitCode


def quiet_loguru(level: str = "WARNING") -> None:
    """Node and editor code logs a lot at DEBUG/INFO; a command that prints a
    report on stdout must not be drowned by it."""
    logger.remove()
    logger.add(sys.stderr, level=level)


def ensure_app():
    """The process-wide ``QApplication`` on the offscreen platform."""
    os.environ["QT_QPA_PLATFORM"] = os.environ.get("TRIGGER_CLI_QPA", "offscreen")
    from qtpy.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(["trigger-designer-cli"])
    app.setApplicationName("Trigger Designer")
    return app


class _NullDialog:
    """Stands in for the modal progress dialog (same stub the test-suite uses)."""

    def __getattr__(self, _name):
        return lambda *args, **kwargs: None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@contextlib.contextmanager
def suppress_ui():
    """No dialog may open: a headless process has nobody to click it away."""
    from nodeeditor import node_editor_widget

    from trigger_designer.qt import design_window
    from trigger_designer.qt.helpers import eval_progress

    saved = (
        design_window.make_progress_dialog,
        eval_progress.make_progress_dialog,
        design_window.QMessageBox,
    )
    saved_vendored = node_editor_widget.QMessageBox

    class _Box:
        StandardButton = design_window.QMessageBox.StandardButton
        warning = information = critical = classmethod(lambda cls, *a, **k: None)

    def null(*_args, **_kwargs):
        return _NullDialog()

    design_window.make_progress_dialog = eval_progress.make_progress_dialog = null
    design_window.QMessageBox = _Box
    node_editor_widget.QMessageBox = _Box
    try:
        yield
    finally:
        node_editor_widget.QMessageBox = saved_vendored
        (
            design_window.make_progress_dialog,
            eval_progress.make_progress_dialog,
            design_window.QMessageBox,
        ) = saved


def make_window():
    """A ``TriggerSubWindow`` whose log goes to a list, not to stdout (F11)."""
    from trigger_designer.qt.design_window import TriggerSubWindow

    class HeadlessWindow(TriggerSubWindow):
        messages: list

        def log(self, level: str, message: str) -> None:
            if not hasattr(self, "messages") or self.messages is None:
                self.messages = []
            self.messages.append((level, message))

    window = HeadlessWindow()
    window.messages = []
    return window


@dataclass
class LoadReport:
    ok: bool
    nodes: list = field(default_factory=list)
    unknown: list = field(default_factory=list)
    invalid: list = field(default_factory=list)
    validation: list = field(default_factory=list)
    messages: list = field(default_factory=list)


def op_of(node: Any) -> str:
    try:
        return f"{node.node_type.value}.{node.node_code.name.lower()}"
    except Exception:  # noqa: BLE001
        return "unknown"


class HeadlessSession:
    """One loaded workflow: window, ordered nodes, upstream map."""

    def __init__(self) -> None:
        self.app = ensure_app()
        self.window = make_window()
        self.report: LoadReport | None = None

    # -- loading -----------------------------------------------------------
    def load(
        self,
        tds_path: str,
        *,
        expect_nodes: int | None = None,
        expect_edges: int | None = None,
    ) -> LoadReport:
        from nodeeditor.node_graph import GraphCycleError, topological_order

        from trigger_designer.qt.helpers.edge_validators import cycle_message
        from trigger_designer.qt.widgets.nodes.unknown import TriggerNode_Unknown

        try:
            with suppress_ui():
                ok = bool(self.window.fileLoad(tds_path))
        except CliError:
            raise
        except Exception as exc:
            raise CliError(
                ExitCode.INVALID,
                "TD-CLI-001",
                f"The workflow could not be loaded: {exc}",
            ) from exc
        if not ok:
            raise CliError(
                ExitCode.INVALID,
                "TD-CLI-001",
                "The workflow could not be loaded.",
                "; ".join(m for _lvl, m in self.window.messages[-3:]),
            )
        scene = self.window.scene
        if expect_nodes is not None and len(scene.nodes) != expect_nodes:
            raise CliError(
                ExitCode.INVALID,
                "TD-CLI-001",
                f"Only {len(scene.nodes)} of {expect_nodes} nodes could be loaded.",
            )
        if expect_edges is not None and len(scene.edges) != expect_edges:
            raise CliError(
                ExitCode.INVALID,
                "TD-CLI-001",
                f"Only {len(scene.edges)} of {expect_edges} connections could be loaded.",
            )
        try:
            nodes = list(topological_order(scene))
        except GraphCycleError as exc:
            raise CliError(ExitCode.INVALID, "TD-CLI-004", cycle_message(exc)) from exc
        validation = []
        with contextlib.suppress(Exception):
            validation = list(self.window.validateLoadedWorkflow())
        self.report = LoadReport(
            ok=True,
            nodes=nodes,
            unknown=[n for n in nodes if isinstance(n, TriggerNode_Unknown)],
            invalid=[n for n in nodes if n.isInvalid()],
            validation=validation,
            messages=list(self.window.messages),
        )
        return self.report

    # -- run preparation ---------------------------------------------------
    def reevaluate(self) -> None:
        """Make every node's live state current (what Run does in the editor)."""
        assert self.report is not None
        self.window._reevaluate_for_run(self.report.nodes)

    def upstream(self) -> dict:
        from trigger_designer.qt.helpers.workflow_execution_mixin import (
            _direct_upstream,
        )

        assert self.report is not None
        return _direct_upstream(self.report.nodes)

    def before_run(self, on_warning) -> None:
        """Each content's ``before_run``; a failing hook is a warning."""
        assert self.report is not None
        for node in self.report.nodes:
            hook = getattr(getattr(node, "content", None), "before_run", None)
            if callable(hook):
                try:
                    hook()
                except Exception as exc:  # noqa: BLE001
                    on_warning(
                        f"before_run failed for {getattr(node, 'node_title', node)}: {exc}",
                        getattr(node, "id", None),
                    )

    def specs(self):
        from trigger_designer.qt.helpers.audit_bridge import node_specs_from_window

        assert self.report is not None
        return node_specs_from_window(self.window, self.report.nodes)

    def enricher(self):
        """``(NodeError, node) -> NodeError`` for the recorder (plan 03)."""
        from trigger_designer.core.errors import enrich_error
        from trigger_designer.qt.helpers.error_context import build_enrich_job

        window = self.window

        def enrich(error, node):
            job = build_enrich_job(node, window, error, "run")
            return enrich_error(job).root

        return enrich

    def emit_script(self, path: str) -> str:
        assert self.report is not None
        return self.window.getPyFile(self.report.nodes, path)

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self.window.deleteLater()


# --------------------------------------------------------------------- test hooks
def _test_hooks_enabled() -> bool:
    return os.environ.get("TD_TEST_HOOKS") == "1" and not getattr(sys, "frozen", False)


_KEEP_ALLOCATED: list = []


def apply_test_hooks(node: Any) -> None:
    """Failure injection for the e2e tests; inert unless ``TD_TEST_HOOKS=1``."""
    if not _test_hooks_enabled():
        return
    title = str(getattr(node, "node_title", ""))
    sleep = os.environ.get("TD_TEST_SLEEP_BEFORE_NODE", "")
    name, _sep, seconds = sleep.rpartition(":")
    if name and name == title:
        time.sleep(float(seconds))
    if os.environ.get("TD_TEST_FAIL_NODE") == title:
        node.get_code = lambda: "raise ValueError('boom')\n"
    if os.environ.get("TD_TEST_INJECT") == title:
        injected = os.environ.get("TD_TEST_INJECT_CODE", "") + "\n"
        node.get_code = lambda: injected
    alloc = os.environ.get("TD_TEST_ALLOC_MB", "")
    name, _sep, megabytes = alloc.rpartition(":")
    if name and name == title:
        _KEEP_ALLOCATED.append(bytearray(int(float(megabytes)) * 1024 * 1024))


def _error_summary(node_record: Any) -> dict | None:
    error = getattr(node_record, "error", None)
    if not error:
        return None
    return {
        "code": error.get("code"),
        "title": error.get("title"),
        "hint": error.get("hint"),
    }


def execute_nodes(
    nodes,
    executor,
    *,
    cancel,
    on_event,
    recorder,
    record,
    keep_going: bool,
    upstream=None,
    codes: dict | None = None,
):
    """A thin adapter over the shared Qt-free run loop (plan 09 F-C)."""
    from trigger_designer.core.ExecutionCheck.run_loop import run_nodes

    index_of = {node: i for i, node in enumerate(nodes)}

    def started(node):
        on_event(
            "node.started",
            node_id=node.id,
            title=node.node_title,
            op=op_of(node),
            index=index_of[node],
            total=len(nodes),
        )
        apply_test_hooks(node)

    def skipped(node, blocker):
        on_event(
            "node.skipped",
            node_id=node.id,
            title=node.node_title,
            blocker=getattr(blocker, "id", None),
        )

    def finished(node, result):
        node_record = None
        try:
            node_record = recorder.node_finished(record, node, result)
        except Exception:  # noqa: BLE001 - a record problem never stops the run
            logger.exception("audit: node record failed")
        if codes is not None and getattr(result, "code", ""):
            codes[node] = result.code
        on_event(
            "node.finished",
            level="INFO" if result.success else "ERROR",
            node_id=node.id,
            title=node.node_title,
            status="ok" if result.success else "failed",
            duration_s=_duration(result),
            error=_error_summary(node_record),
        )
        if getattr(result, "policy_violation", False):
            raise CliError(
                ExitCode.REFUSED,
                "TD-CLI-010",
                f"The safety policy refused the code of '{node.node_title}': {result.error}",
                "Open the workflow in the editor and look at that node; do not run "
                "files you do not trust.",
            )

    def errored(node, exc):
        try:
            recorder.node_errored(record, node, exc)
        except Exception:  # noqa: BLE001
            logger.exception("audit: node error record failed")
        on_event(
            "node.finished",
            level="ERROR",
            node_id=node.id,
            title=node.node_title,
            status="failed",
            duration_s=0.0,
            error={"code": "TD-SYS-999", "title": str(exc), "hint": ""},
        )

    return run_nodes(
        nodes,
        executor,
        continue_on_error=keep_going,
        upstream=upstream,
        cancel=cancel,
        on_node_started=started,
        on_node_finished=finished,
        on_node_errored=errored,
        on_node_skipped=skipped,
    )


def _duration(result: Any) -> float:
    from datetime import datetime

    try:
        start = datetime.fromisoformat(result.started_at)
        end = datetime.fromisoformat(result.finished_at)
        return round((end - start).total_seconds(), 3)
    except Exception:  # noqa: BLE001
        return 0.0
