from __future__ import annotations

from datetime import datetime

from nodeeditor.node_edge import Edge
from nodeeditor.node_graphics_edge import QDMGraphicsEdge
from nodeeditor.node_scene import Scene

from trigger_designer.core.constants import VERSION, WORKFLOW_SCHEMA_VERSION


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

    def updatePositions(self) -> None:
        source_pos = self.start_socket.getSocketPosition()
        source_pos[0] += self.start_socket.node.grNode.pos().x()
        source_pos[1] += self.start_socket.node.grNode.pos().y()
        self.grEdge.setSource(*source_pos)

        if self.end_socket is not None:
            end_pos = self.end_socket.getSocketPosition()
            end_pos[0] += self.end_socket.node.grNode.pos().x()
            end_pos[1] += self.end_socket.node.grNode.pos().y()
            self.grEdge.setDestination(*end_pos)
        else:
            self.grEdge.setDestination(*source_pos)

        if getattr(self.scene, "_bulk_loading", False):
            self.scene._deferred_edge_updates.add(self)
            return

        self.grEdge.update()


class TriggerScene(Scene):
    def __init__(self) -> None:
        super().__init__()
        self._bulk_loading = False
        self._deferred_edge_updates: set[TriggerEdge] = set()
        self.loaded_workflow_metadata: dict[str, object] = {}

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
