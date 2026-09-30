from __future__ import annotations

from datetime import datetime

from nodeeditor.node_edge import Edge
from nodeeditor.node_graphics_edge import QDMGraphicsEdge
from nodeeditor.node_multi_input_node import MultiInputNode
from nodeeditor.node_scene import Scene

from trigger_designer.core.constants import VERSION, WORKFLOW_SCHEMA_VERSION
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
        super().setSource(x, y)
        self._invalidate_cached_path()

    def setDestination(self, x: float, y: float) -> None:
        super().setDestination(x, y)
        self._invalidate_cached_path()

    def calcPath(self):
        if self._path_dirty or self._cached_path is None:
            self._cached_path = self.pathCalculator.calcPath()
            self._path_dirty = False
        return self._cached_path


class TriggerEdge(Edge):
    def getGraphicsEdgeClass(self):
        return CachedGraphicsEdge

    def _collapsed_group(self, node) -> object | None:
        """The collapsed upstream ``Group`` containing ``node``, if any."""
        finder = getattr(self.scene, "findCollapsedGroupForNode", None)
        if finder is None or node is None:
            return None
        try:
            return finder(node)
        except Exception:
            return None

    def _stub_pos(self, group) -> list | None:
        try:
            point = group.stubPosFor(self)
        except Exception:
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
            except Exception:
                pass
            return

        source_pos = self.start_socket.getSocketPosition()
        source_pos[0] += self.start_socket.node.grNode.pos().x()
        source_pos[1] += self.start_socket.node.grNode.pos().y()
        if start_group is not None:
            stub = self._stub_pos(start_group)
            if stub is not None:
                source_pos = stub
        self.grEdge.setSource(*source_pos)

        if self.end_socket is not None:
            end_pos = self.end_socket.getSocketPosition()
            end_pos[0] += self.end_socket.node.grNode.pos().x()
            end_pos[1] += self.end_socket.node.grNode.pos().y()
            if end_group is not None:
                stub = self._stub_pos(end_group)
                if stub is not None:
                    end_pos = stub
            self.grEdge.setDestination(*end_pos)
        else:
            self.grEdge.setDestination(*source_pos)

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
        self.loaded_workflow_metadata: dict[str, object] = {}
        #: Set by helpers.eval_progress.eval_progress_dialog while a
        #: progress dialog is driving a load/recompute; None otherwise.
        self._eval_progress_cb = None

    def getEdgeClass(self):
        return TriggerEdge

    def beginBulkLoad(self) -> None:
        self._bulk_loading = True
        self._deferred_edge_updates.clear()

    def endBulkLoad(self) -> None:
        pending_edges = list(self._deferred_edge_updates)
        self._bulk_loading = False
        self._deferred_edge_updates.clear()

        for edge in pending_edges:
            edge.updatePositions()

    def serialize(self):
        data = super().serialize()
        data["workflow_metadata"] = {
            "schema_version": WORKFLOW_SCHEMA_VERSION,
            "app_version": VERSION,
            "saved_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        }
        return data

    def deserialize(self, data, hashmap=None, restore_id: bool = True, *args, **kwargs):
        self.loaded_workflow_metadata = data.get(
            "workflow_metadata",
            {"schema_version": 0, "app_version": None},
        )
        return super().deserialize(data, hashmap, restore_id, *args, **kwargs)


def settle_multi_input_nodes(scene: Scene) -> None:
    """Retry only collectors whose first pass did not settle every edge.

    Union now commits its value before evaluating children, so the old
    unconditional second pass recalculated complete Union branches for no
    benefit. Keep a recovery pass for dirty/invalid/incomplete collectors.
    """
    multi_input_nodes = [
        node for node in scene.nodes if isinstance(node, MultiInputNode)
    ]
    incomplete = []
    for node in multi_input_nodes:
        try:
            expected = len(node.getOrderedEdges())
            actual = len(node.content.input_frames)
        except (AttributeError, RuntimeError, TypeError):
            incomplete.append(node)
            continue
        if node.isDirty() or node.isInvalid() or actual != expected:
            incomplete.append(node)

    if not incomplete:
        return

    for node in incomplete:
        node.markDirty(True)
        node.markDescendantsDirty(True)

    for node in scene.nodes:
        node.eval()
