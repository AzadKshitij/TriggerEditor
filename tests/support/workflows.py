"""Workflow-file helpers for the E2E layer.

The checked-in workflows under ``savedfiles/`` and ``data/`` were written on
different machines over time, so their ``filePath`` values are absolute and
point at inputs and outputs that do not exist here. :func:`materialize` copies
one into a test's tmp directory and rewrites every File Input to a checked-in
fixture (or an existing sample under ``data/``) and every File Output into
``tmp_path/out`` - so a run writes nowhere near the repository or the
developer's files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import orjson

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class WorkflowCase:
    """A checked-in workflow and what it is checked against."""

    name: str
    source: str  # repo-relative, e.g. "savedfiles/1. in-select.tds"
    #: File Input basename -> repo-relative input file.
    inputs: dict[str, str] = field(default_factory=dict)
    #: Produced-file basename -> frozen golden name under
    #: ``tests/e2e/fixtures/expected`` (see ``support.frames.assert_frame_golden``).
    goldens: dict[str, str] = field(default_factory=dict)
    #: Golden names whose row order the run does not promise, so the harness
    #: sorts both frames by every column before comparing (a hash join).
    unordered_goldens: frozenset[str] = frozenset()

    @property
    def source_path(self) -> Path:
        return REPO_ROOT / self.source


@dataclass(frozen=True)
class MaterializedWorkflow:
    """A workflow copy safe to open: inputs and outputs point into the test."""

    path: Path
    out_dir: Path


def materialize(case: WorkflowCase, tmp_path: Path) -> MaterializedWorkflow:
    data = orjson.loads(case.source_path.read_bytes())
    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True, exist_ok=True)

    for node in data.get("nodes", []):
        content = node.get("content")
        if not isinstance(content, dict):
            continue
        key = _file_path_key(content)
        if key is None:
            continue
        settings = content.get("settings")
        target = settings if isinstance(settings, dict) and key in settings else content
        raw = str(target.get(key) or "")
        if not raw:
            continue
        basename = _basename(raw)

        kind = _node_kind(node)
        if kind == "input":
            target[key] = _input_path(case, basename).as_posix()
            # Relative wins on load; a stale one would override the rewrite.
            target.pop("filePathRel", None)
        elif kind == "output":
            target[key] = (out_dir / basename).as_posix()

    workflow_path = tmp_path / f"{case.name}.tds"
    workflow_path.write_bytes(orjson.dumps(data, option=orjson.OPT_INDENT_2))
    return MaterializedWorkflow(path=workflow_path, out_dir=out_dir)


def run_workflow_and_wait(qtbot, window, timeout_ms: int = 90_000) -> None:
    """Click Run's code path and block until the worker has finished.

    The signal arrives from the worker thread's last instruction, so the
    ``QThread`` is still running when it is delivered; the mixin drops its own
    reference in that slot, and if Python then collects the worker before the
    thread returns, Qt aborts the process ("QThread: Destroyed while thread is
    still running"). Holding the reference and waiting for the thread to finish
    keeps the harness off that path; the posted ``deleteLater`` runs right
    after, with the wrapper still alive.
    """
    from qtpy.QtCore import QCoreApplication, QEvent

    assert window._workflow_worker is None, "a run is already in flight"
    with qtbot.waitSignal(window.executionResultsChanged, timeout=timeout_ms):
        window.executeWorkflow()
        worker = window._workflow_worker
    assert worker is not None, "executeWorkflow never started a worker"
    assert worker.wait(timeout_ms), "workflow worker did not finish"
    QCoreApplication.sendPostedEvents(worker, QEvent.Type.DeferredDelete)
    assert window._workflow_worker is None, "worker was not released"
    assert window.run_button.isEnabled(), "run cleanup did not run"


def nodes_titled(window, title: str) -> list:
    """All nodes whose visible title matches exactly."""
    return [node for node in window.getAllNodes() if node.title == title]


def executed_frame(window, node, index: int = 0):
    """The frame a finished node's output ``index`` produced in the last run.

    Loading evaluated the node's ``processInputs`` into ``node.value``: a list
    of ``{"data", "variable_name"}``, one per output socket. The run defines
    the same variable names in its execution context, so the name links the
    output the test wants to the frame the generated code computed.
    """
    import polars as pl

    outputs = node.value
    if not isinstance(outputs, list):
        raise TypeError(f"{node.title!r}: no evaluated outputs to map")
    entries = [
        entry
        for entry in outputs
        if isinstance(entry, dict) and entry.get("variable_name")
    ]
    if index >= len(entries):
        raise AssertionError(
            f"{node.title!r}: no output #{index} (found {len(entries)})"
        )
    name = entries[index]["variable_name"]
    variables = window.execution_results.get(node) or {}
    if name not in variables:
        raise AssertionError(
            f"{node.title!r}: the run produced no variable {name!r}; "
            f"got {sorted(variables)}"
        )
    value = variables[name]
    return value.collect() if isinstance(value, pl.LazyFrame) else value


def _basename(raw: str) -> str:
    return Path(raw.replace("\\", "/")).name


def _file_path_key(content: dict) -> str | None:
    keys = ("filePath", "file_path", "outputPath", "output_path")
    for key in keys:
        if key in content:
            return key
    settings = content.get("settings")
    if isinstance(settings, dict):
        for key in keys:
            if key in settings:
                return key
    return None


def _node_kind(node: dict) -> str | None:
    """Classify a node as a file reader/writer across v1 and v2 schemas."""
    op = str(node.get("op") or "")
    title = str(node.get("title") or "")
    if op.endswith("file_input") or title == "File Input":
        return "input"
    if op.endswith("file_output") or title == "File Output":
        return "output"
    return None


def _input_path(case: WorkflowCase, basename: str) -> Path:
    candidates = []
    if basename in case.inputs:
        candidates.append(REPO_ROOT / case.inputs[basename])
    candidates.extend(
        [
            REPO_ROOT / "data" / basename,
            REPO_ROOT / "savedfiles" / basename,
            REPO_ROOT / basename,
        ]
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"{case.name}: no input fixture for {basename!r}; "
        f"tried: {', '.join(str(path) for path in candidates)}"
    )
