"""Glue between the Qt window and the Qt-free run recorder (plan 02 3.7, 3.10).

Everything that knows about ``TriggerNode`` lives here; ``core/audit`` never
imports Qt. ``RunSession`` is GUI only; headless callers build specs with
:func:`node_specs_from_window` and drive ``RunRecorder`` directly.

Nothing in this module may fail or slow a run: callers wrap every entry point
in ``try/except`` and a recording problem is logged, never raised.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from typing import Any

from loguru import logger
from qtpy.QtCore import QTimer

from trigger_designer.core.audit.errors_adapter import node_error_to_dict
from trigger_designer.core.audit.recorder import (
    AuditOptions,
    EdgeRef,
    NodeSpec,
    RunRecorder,
    sanitize,
    set_run_record_provider,
)
from trigger_designer.core.audit.schema import RunRecord
from trigger_designer.core.audit.store import RunStore
from trigger_designer.core.constants import VERSION
from trigger_designer.qt.preferences import app_data_dir, get_preferences

#: Seconds-as-milliseconds a failed run waits for error enrichment (3.7a).
SETTLE_GUARD_MS = 5000

#: Settings keys that are bulky or volatile rather than settings (3.10).
_DROPPED_KEYS = frozenset(
    {"schema_snapshot", "available_sheets", "file_metadata", "id", "pos_x", "pos_y"}
)
_PATH_KEYS = frozenset({"filePath", "file_path", "outputPath", "output_path"})
_ROW_COUNT_CHOICES = ("auto", "all", "sink", "off")


# ------------------------------------------------------------------ options
def options_from_preferences() -> AuditOptions:
    """The effective :class:`AuditOptions` from the ``audit/*`` preferences."""
    prefs = get_preferences()
    row_counts = str(prefs.get("audit/row_counts", "auto") or "auto")
    if row_counts not in _ROW_COUNT_CHOICES:
        row_counts = "auto"
    return AuditOptions(
        record_identity=bool(prefs.get("audit/record_identity", True)),
        hash_inputs=bool(prefs.get("audit/hash_inputs", True)),
        hash_outputs=bool(prefs.get("audit/hash_outputs", True)),
        hash_max_mb=max(0, int(prefs.get("audit/hash_max_mb", 2048))),
        row_counts=row_counts,
        exact_counts_max_mb=max(0, int(prefs.get("audit/exact_counts_max_mb", 256))),
        embed_code=bool(prefs.get("audit/embed_code", True)),
        app_data_dir=str(app_data_dir()),
        redact_values=bool(prefs.get("errors/redact_values", False)),
    )


def store_from_preferences() -> RunStore:
    prefs = get_preferences()
    return RunStore(str(prefs.get("audit/run_log_dir", "") or ""), app_data_dir())


# ------------------------------------------------------------------ settings
def _forward(value: Any) -> Any:
    return value.replace("\\", "/") if isinstance(value, str) else value


def snapshot_settings(content: Any) -> dict:
    """JSON-safe settings of a node's content; never re-reads input files."""
    if content is None:
        return {}
    try:
        getter = getattr(content, "get_serialized_state", None)
        state = getter() if callable(getter) else content.serialize()
    except Exception as exc:  # noqa: BLE001 - a record without settings beats none
        return {"_error": f"settings unavailable: {type(exc).__name__}"}
    if not isinstance(state, dict):
        return {}
    state = dict(state)
    nested = state.get("settings")
    if isinstance(nested, dict):  # shaping nodes keep their settings in one dict
        state.pop("settings")
        state = {**state, **nested}
    cleaned = {
        str(k): v
        for k, v in state.items()
        if str(k) not in _DROPPED_KEYS and not str(k).startswith("_")
    }
    result = sanitize(cleaned)
    for key in _PATH_KEYS & set(result):
        result[key] = _forward(result[key])
    return result


# ---------------------------------------------------------------- node specs
def _op_of(node: Any) -> str:
    try:
        return f"{node.node_type.value}.{node.node_code.name.lower()}"
    except Exception:  # noqa: BLE001
        return "unknown"


def _input_files(node: Any, op: str) -> tuple[dict, ...]:
    content = getattr(node, "content", None)
    if content is None:
        return ()
    for name in ("audit_input_files", "resolved_input_files"):
        getter = getattr(content, name, None)
        if callable(getter):
            try:
                found = []
                for item in getter():
                    if isinstance(item, dict):
                        found.append(
                            {
                                "path": str(item.get("path") or ""),
                                "sheet": item.get("sheet") or None,
                                "kind": item.get("kind"),
                            }
                        )
                    else:
                        found.append(
                            {
                                "path": str(getattr(item, "path", "") or ""),
                                "sheet": getattr(item, "sheet", None) or None,
                                "kind": getattr(item, "kind", None),
                            }
                        )
                return tuple(entry for entry in found if entry["path"])
            except Exception as exc:  # noqa: BLE001
                logger.debug("audit: {} failed: {}", name, exc)
    if op != "input.file_input":
        return ()
    path = str(getattr(content, "filePath", "") or "")
    if not path:
        return ()
    kind = getattr(content, "file_type", None)
    sheet = None
    if kind == "excel" and getattr(content, "sheet_mode", "one") == "one":
        sheet = getattr(content, "selected_sheet", None) or None
    try:
        from trigger_designer.core.inputs import list_source_files

        listing = list_source_files(
            path,
            str(kind or "csv"),
            include=list(getattr(content, "include_patterns", ()) or ()),
            exclude=list(getattr(content, "exclude_patterns", ()) or ()),
            recursive=bool(getattr(content, "recursive", False)),
            order=str(getattr(content, "file_order", "name") or "name"),
            max_files=int(getattr(content, "max_files", 10000) or 10000),
        )
        files = [{"path": f.path, "sheet": sheet, "kind": kind} for f in listing.files]
        if files:
            return tuple(files)
    except Exception as exc:  # noqa: BLE001 - a missing file is recorded as missing
        logger.debug("audit: input listing failed ({}); using the stored path", exc)
    return ({"path": path, "sheet": sheet, "kind": kind},)


def _output_files(node: Any, op: str, settings: dict) -> tuple[dict, ...]:
    content = getattr(node, "content", None)
    if content is None:
        return ()
    getter = getattr(content, "audit_output_files", None)
    if callable(getter):
        try:
            return tuple(
                {
                    "path": str(item.get("path") or ""),
                    "format": item.get("format"),
                    "delimiter": item.get("delimiter"),
                }
                for item in getter()
                if item.get("path")
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("audit: audit_output_files failed: {}", exc)
    if op != "input.file_output":
        return ()
    live = getattr(content, "settings", None)
    live = live if isinstance(live, dict) else {}
    path = str(
        live.get("filePath")
        or settings.get("filePath")
        or getattr(content, "filePath", "")
        or ""
    )
    if not path:
        return ()
    return (
        {
            "path": path,
            "format": live.get("file_format")
            or settings.get("file_format")
            or getattr(content, "file_format", "csv"),
            "delimiter": live.get("delimiter")
            or settings.get("delimiter")
            or getattr(content, "delimiter", ","),
        },
    )


def node_spec_from_node(node: Any, window: Any) -> NodeSpec:
    """Plain-data description of one node, taken on the GUI thread."""
    op = _op_of(node)
    settings = snapshot_settings(getattr(node, "content", None))
    names: tuple[str, ...] = ()
    declared = getattr(window, "_declared_output_variable_names", None)
    if callable(declared):
        try:
            names = tuple(declared(node))
        except Exception:  # noqa: BLE001
            names = ()
    label = str(getattr(node, "label_text", "") or "").strip() or None
    return NodeSpec(
        node_id=int(node.id),
        op=op,
        title=str(getattr(node, "node_title", "") or ""),
        label=label,
        settings=settings,
        n_outputs=len(getattr(node, "outputs", ()) or ()),
        output_variables=names,
        is_source=op == "input.file_input",
        input_files=_input_files(node, op),
        output_files=_output_files(node, op, settings),
    )


def node_specs_from_window(
    window: Any, sorted_nodes: Sequence[Any]
) -> tuple[list[NodeSpec], list[EdgeRef]]:
    """Specs in execution order plus the edges between them (real socket indexes)."""
    specs = [node_spec_from_node(node, window) for node in sorted_nodes]
    ids = {spec.node_id for spec in specs}
    edges: list[EdgeRef] = []
    for edge in getattr(window.scene, "edges", ()) or ():
        try:
            start, end = edge.start_socket, edge.end_socket
            source, target = start.node.id, end.node.id
            if source in ids and target in ids:
                edges.append(EdgeRef(source, int(start.index), target, int(end.index)))
        except AttributeError:
            continue
    return specs, edges


# ------------------------------------------------------------------- session
class RunSession:
    """The recorder of one GUI run, as the execution mixin sees it."""

    def __init__(
        self,
        window: Any,
        recorder: RunRecorder,
        record: RunRecord,
        nodes: Sequence[Any],
    ) -> None:
        self._window = window
        self._recorder = recorder
        self._record = record
        self._nodes = {getattr(node, "id", None): node for node in nodes}
        self._cancelled = False
        self._final: RunRecord | None = None
        self._sealed = False

    # -- creation ----------------------------------------------------------
    @staticmethod
    def start(
        window: Any, sorted_nodes: Sequence[Any], executor: Any
    ) -> RunSession | None:
        """Begin recording and install the executor hooks; ``None`` when off."""
        if not bool(get_preferences().get("audit/record_runs", True)):
            return None
        recorder = RunRecorder(store_from_preferences(), options_from_preferences())
        specs, edges = node_specs_from_window(window, sorted_nodes)
        scene = getattr(window, "scene", None)
        path = (
            getattr(window, "filename", None)
            or getattr(scene, "filename", None)
            or None
        )
        record = recorder.begin(
            os.fspath(path) if path else None,
            specs,
            app_version=VERSION,
            edges=edges,
            workflow_uuid=getattr(scene, "workflow_uuid", None),
            modified_since_save=getattr(scene, "has_been_modified", None),
        )
        session = RunSession(window, recorder, record, sorted_nodes)
        executor.before_node = recorder.before_node
        executor.after_node = recorder.after_node
        set_run_record_provider(session.snapshot_current)
        return session

    # -- properties ---------------------------------------------------------
    @property
    def recorder(self) -> RunRecorder:
        return self._recorder

    @property
    def record(self) -> RunRecord:
        return self._record

    @property
    def sealed(self) -> bool:
        return self._sealed

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    # -- run callbacks (GUI thread) ----------------------------------------
    def node_finished(self, node: Any, result: Any) -> None:
        try:
            self._recorder.node_finished(self._record, node, result)
        except Exception:  # noqa: BLE001 - the run must not notice
            logger.exception("audit: node record failed")

    def node_errored(self, node: Any, exc: BaseException) -> None:
        try:
            self._recorder.node_errored(self._record, node, exc)
        except Exception:  # noqa: BLE001
            logger.exception("audit: node error record failed")

    def request_cancel(self) -> None:
        """Called by ``request_run_cancel``; the GUI's ``cancelled`` status."""
        self._cancelled = True
        self._recorder.request_cancel()

    def snapshot_current(self) -> dict | None:
        try:
            return self._recorder.snapshot(self._final if self._sealed else None)
        except Exception:  # noqa: BLE001
            return None

    # -- sealing ---------------------------------------------------------------
    def _refresh_failed_errors(self) -> None:
        """Replace first-pass errors with what the Problems store settled on."""
        for node_record in self._recorder.snapshot()["nodes"]:
            if node_record.get("status") != "failed":
                continue
            node = self._nodes.get(node_record.get("node_id"))
            error = getattr(node, "current_error", None)
            if error is None:
                continue
            data = node_error_to_dict(error)
            culprit_id = getattr(error, "culprit_node_id", None)
            culprit = self._nodes.get(culprit_id)
            root = getattr(culprit, "current_error", None)
            if culprit is not None and culprit is not node and root is not None:
                data["root_cause"] = node_error_to_dict(root)
            try:
                self._recorder.update_node_error(node_record["node_id"], data)
            except Exception as exc:  # noqa: BLE001
                logger.debug("audit: could not refresh the error: {}", exc)

    def finish(self, success: bool) -> str | None:
        """Seal the record; the saved path, or ``None`` when saving failed."""
        if self._sealed:
            return self._recorder.last_path
        try:
            self._refresh_failed_errors()
        except Exception as exc:  # noqa: BLE001
            logger.debug("audit: error refresh skipped: {}", exc)
        self._final = self._recorder.finish(
            self._record, success, cancelled=self._cancelled and not success
        )
        self._sealed = True
        path = self._recorder.last_path
        self._warn_about_changed_inputs()
        return path

    def abort(self) -> None:
        """The run never started: discard the begun record and its marker."""
        if self._sealed:
            return
        self._sealed = True
        try:
            self._recorder.finish(self._record, False, save=False)
        except Exception:  # noqa: BLE001, S110
            pass

    def _warn_about_changed_inputs(self) -> None:
        if not bool(get_preferences().get("audit/warn_on_input_change", True)):
            return
        baseline = (self._final.baseline if self._final else None) or {}
        warn = getattr(self._window, "logWarning", None)
        for change in baseline.get("input_changes", []):
            message = f"Input changed since the previous run: {change.get('path')}"
            if callable(warn):
                warn(message)
            else:
                logger.warning(message)

    def finish_when_settled(
        self, success: bool, on_done: Callable[[str | None], None]
    ) -> None:
        """Seal now, or after plan 03's enrichment has settled (3.7a)."""
        window = self._window
        settled = getattr(window, "is_enrichment_settled", None)
        if success or not callable(settled) or settled():
            on_done(self.finish(success))
            return
        state = {"done": False}

        def run_once() -> None:
            if state["done"]:
                return
            state["done"] = True
            on_done(self.finish(success))

        add_listener = getattr(window, "add_enrichment_settled_listener", None)
        if callable(add_listener):
            add_listener(run_once)
        QTimer.singleShot(SETTLE_GUARD_MS, run_once)
