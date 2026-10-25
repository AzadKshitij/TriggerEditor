from __future__ import annotations

import os
import tempfile
from collections.abc import Callable
from datetime import datetime

import orjson
from loguru import logger
from nodeeditor.node_edge import Edge
from nodeeditor.node_graphics_edge import QDMGraphicsEdge
from nodeeditor.node_multi_input_node import MultiInputNode
from nodeeditor.node_scene import Scene

from trigger_designer.core.constants import VERSION, WORKFLOW_SCHEMA_VERSION
from trigger_designer.qt.helpers.evaluation import EvaluationCoordinator
from trigger_designer.qt.undo.history import TriggerSceneHistory


class CachedGraphicsEdge(QDMGraphicsEdge):
    def __init__(self, edge: Edge, parent=None) -> None:
        self._cached_path = None
        self._path_dirty = True
        super().__init__(edge, parent)

    def _invalidate_cached_path(self) -> None:
        self._path_dirty = True
        self._cached_path = None

    def createEdgePathCalculator(self):
        calculator = super().createEdgePathCalculator()
        self._invalidate_cached_path()
        return calculator

    def setSource(self, x: float, y: float) -> None:
        # Invalidate first: the base setter adopts the recomputed path, and it
        # must not adopt the cache from the previous position.
        self._invalidate_cached_path()
        super().setSource(x, y)

    def setDestination(self, x: float, y: float) -> None:
        self._invalidate_cached_path()
        super().setDestination(x, y)

    def setPositions(self, source, destination) -> None:
        # A node move sets both ends; invalidate once and let the base setter
        # adopt the recomputed path once.
        self._invalidate_cached_path()
        super().setPositions(source, destination)

    def calcPath(self):
        if self._path_dirty or self._cached_path is None:
            self._cached_path = self.pathCalculator.calcPath()
            self._path_dirty = False
        return self._cached_path


class TriggerEdge(Edge):
    def __init__(
        self,
        scene,
        start_socket=None,
        end_socket=None,
        *args,
        **kwargs,
    ) -> None:
        # A drag may start on an input socket. The package accepts that pair,
        # but every graph algorithm requires an output->input edge, so store
        # the direction data flows, not the direction the user dragged. The
        # temporary drag edge has no end socket and is left untouched.
        if (
            start_socket is not None
            and end_socket is not None
            and getattr(start_socket, "is_input", False)
            and getattr(end_socket, "is_output", False)
        ):
            start_socket, end_socket = end_socket, start_socket
        super().__init__(scene, start_socket, end_socket, *args, **kwargs)

    def getGraphicsEdgeClass(self):
        return CachedGraphicsEdge

    def _collapsed_group(self, node) -> object | None:
        """The collapsed upstream ``Group`` containing ``node``, if any."""
        finder = getattr(self.scene, "findCollapsedGroupForNode", None)
        if finder is None or node is None:
            return None
        try:
            return finder(node)
        except Exception:  # noqa: BLE001
            return None

    def _stub_pos(self, group) -> list | None:
        try:
            point = group.stubPosFor(self)
        except Exception:  # noqa: BLE001
            return None
        if point is None:
            return None
        return [point.x(), point.y()]

    def updatePositions(self) -> None:
        start_node = getattr(self.start_socket, "node", None)
        end_node = (
            getattr(self.end_socket, "node", None)
            if self.end_socket is not None
            else None
        )
        start_group = self._collapsed_group(start_node)
        end_group = self._collapsed_group(end_node)
        if start_group is not None and start_group is end_group:
            # Internal edge of a collapsed group: stay hidden, positions
            # untouched. expand()/restoreExpandedVisuals() reveals it again.
            try:
                self.grEdge.hide()
            except Exception:  # noqa: BLE001, S110
                pass
            return

        source_pos = self.start_socket.getSocketPosition()
        source_pos[0] += self.start_socket.node.grNode.pos().x()
        source_pos[1] += self.start_socket.node.grNode.pos().y()
        if start_group is not None:
            stub = self._stub_pos(start_group)
            if stub is not None:
                source_pos = stub

        if self.end_socket is not None:
            end_pos = self.end_socket.getSocketPosition()
            end_pos[0] += self.end_socket.node.grNode.pos().x()
            end_pos[1] += self.end_socket.node.grNode.pos().y()
            if end_group is not None:
                stub = self._stub_pos(end_group)
                if stub is not None:
                    end_pos = stub
        else:
            end_pos = source_pos

        # Both ends at once: the graphics edge adopts the recomputed path once
        # instead of once per end, which halves the route calculations behind a
        # node move.
        self.grEdge.setPositions(source_pos, end_pos)

        if getattr(self.scene, "_bulk_loading", False):
            self.scene._deferred_edge_updates.add(self)
            return

        self.grEdge.update()


class TriggerScene(Scene):
    #: Undo/redo runs on a Qt command stack rather than a list of snapshots.
    historyClass = TriggerSceneHistory

    def __init__(self) -> None:
        super().__init__()
        self._bulk_loading = False
        self._deferred_edge_updates: set[TriggerEdge] = set()
        #: Cycle signatures already reported by the evaluation fallback, so
        #: repeated passes over a legacy cyclic graph do not spam the log.
        self._reported_cycle_signatures: set[tuple[tuple[int, ...], ...]] = set()
        #: Set by the owning sub-window so a cycle found by a deferred pass
        #: reaches the same log/dock as a full pass.
        self.cycle_reporter: Callable[[str], None] | None = None
        self._eval_depth = 0
        self.evaluator = EvaluationCoordinator(self)
        self.loaded_workflow_metadata: dict[str, object] = {}
        #: Set by helpers.eval_progress.eval_progress_dialog while a
        #: progress dialog is driving a load/recompute; None otherwise.
        self._eval_progress_cb = None
        #: Callbacks run, with the node, after a real recompute. ``Scene`` is
        #: not a QObject, so this follows the scene's own listener idiom
        #: (``addItemSelectedListener`` and friends) rather than a signal.
        self._node_evaluated_listeners: list[Callable[[object], None]] = []

    def getEdgeClass(self):
        return TriggerEdge

    def addNodeEvaluatedListener(self, callback: Callable[[object], None]) -> None:
        """Register ``callback(node)`` for every real node recompute."""
        self._node_evaluated_listeners.append(callback)

    def notifyNodeEvaluated(self, node: object) -> None:
        """Run the evaluation listeners for ``node`` (``Node.eval`` calls it)."""
        for callback in list(self._node_evaluated_listeners):
            callback(node)

    def beginBulkLoad(self) -> None:
        self._bulk_loading = True
        self._deferred_edge_updates.clear()
        self.evaluator.begin_bulk_load()

    def endBulkLoad(self) -> None:
        pending_edges = list(self._deferred_edge_updates)
        self._bulk_loading = False
        self._deferred_edge_updates.clear()
        # A load gathers constructor/deserialize notifications but must not
        # flush them; the single doEvalOutputs pass owns evaluation.
        self.evaluator.end_bulk_load()

        for edge in pending_edges:
            edge.updatePositions()

    #: Set only while ``saveToFile`` runs: the vendored implementation
    #: serialises BEFORE it sets ``self.filename``, so content that stores a
    #: path relative to the workflow needs the target during that window.
    _save_target: str | None = None

    @property
    def workflow_dir(self) -> str | None:
        """Folder of the workflow being saved (during a save) or loaded."""
        target = self._save_target or self.filename
        return os.path.dirname(os.path.abspath(target)) if target else None

    def serialize(self):
        data = super().serialize()
        data["workflow_metadata"] = {
            "schema_version": WORKFLOW_SCHEMA_VERSION,
            "app_version": VERSION,
            "saved_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",  # noqa: DTZ003
        }
        return data

    def saveToFile(self, filename: str) -> None:
        """Write UTF-8 JSON atomically, making the target visible to serialize.

        The file is only replaced after the whole payload is on disk, so a
        failure while serialising leaves the previous workflow untouched.
        """
        filename = os.fspath(filename)
        self._save_target = filename
        tmp_path = None
        try:
            # A pending edge edit is newer than the serialization about to
            # run; never let the file capture a stale value. The save target
            # is visible first because evaluation may resolve content paths.
            self.evaluator.flush_now()
            payload = orjson.dumps(self.serialize(), option=orjson.OPT_INDENT_2)
            directory = os.path.dirname(os.path.abspath(filename))
            fd, tmp_path = tempfile.mkstemp(
                prefix=".tds-", suffix=".tmp", dir=directory
            )
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, filename)
            tmp_path = None
            self.filename = filename
            self.has_been_modified = False
        finally:
            self._save_target = None
            if tmp_path is not None:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    def deserialize(self, data, hashmap=None, restore_id: bool = True, *args, **kwargs):
        self.loaded_workflow_metadata = data.get(
            "workflow_metadata",
            {"schema_version": 0, "app_version": None},
        )
        return super().deserialize(data, hashmap, restore_id, *args, **kwargs)


def _incomplete_collectors(scene: Scene) -> list[MultiInputNode]:
    """Collectors whose first pass did not settle every edge.

    A complete collector is a cache hit; retrying it would recompute a whole
    Union branch for no benefit. A collector that is still incomplete after
    the retry is reported once and left alone rather than looped over.
    """
    incomplete: list[MultiInputNode] = []
    for node in scene.nodes:
        if not isinstance(node, MultiInputNode):
            continue
        try:
            expected = len(node.getOrderedEdges())
            actual = len(node.content.input_frames)
        except (AttributeError, RuntimeError, TypeError):
            incomplete.append(node)
            continue
        if node.isDirty() or node.isInvalid() or actual != expected:
            incomplete.append(node)
    return incomplete


def settle_multi_input_nodes(scene: Scene) -> None:
    """Retry only collectors whose first pass did not settle every edge.

    Union commits its value before evaluating children, so a complete
    collector is already settled. Only dirty/invalid/incomplete collectors
    and their descendants need one recovery pass; unrelated branches must
    keep their cached values.
    """
    incomplete = _incomplete_collectors(scene)
    if not incomplete:
        return

    for node in incomplete:
        node.markDirty(True)
        node.markDescendantsDirty(True)

    evaluator = getattr(scene, "evaluator", None)
    if evaluator is not None:
        evaluator.evaluate_nodes(incomplete, mark_dirty=False)
    else:
        # Plain nodeeditor Scene (low-level tests and embedders) has no
        # coordinator; preserve the old recovery path there only.
        for node in scene.nodes:
            node.eval()

    still_incomplete = _incomplete_collectors(scene)
    for node in still_incomplete:
        try:
            edges = len(node.getOrderedEdges())
            frames = len(node.content.input_frames)
            detail = f"{frames} frames for {edges} edges"
        except (AttributeError, RuntimeError, TypeError):
            detail = "unreadable input state"
        logger.warning(
            "Multi-input collector {} did not settle after retry ({})",
            node.__class__.__name__,
            detail,
        )
