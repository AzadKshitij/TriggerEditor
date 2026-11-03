"""State behind the Problems dock: one row per node and source."""

from __future__ import annotations

from qtpy.QtCore import QObject, Signal

from trigger_designer.core.errors import NodeError


class ProblemsStore(QObject):
    changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._entries: dict[tuple[int | None, str], NodeError] = {}

    def upsert(self, error: NodeError, source: str) -> bool:
        key = (error.node_id, source)
        old = self._entries.get(key)
        if old is not None and old == error:
            return False
        self._entries[key] = error
        self.changed.emit()
        return True

    def remove(self, node_id: int, source: str | None = None) -> None:
        keys = [
            key
            for key in self._entries
            if key[0] == node_id and (source is None or key[1] == source)
        ]
        if not keys:
            return
        for key in keys:
            del self._entries[key]
        self.changed.emit()

    def clear_source(self, source: str) -> None:
        keys = [key for key in self._entries if key[1] == source]
        if not keys:
            return
        for key in keys:
            del self._entries[key]
        self.changed.emit()

    def clear(self) -> None:
        if not self._entries:
            return
        self._entries.clear()
        self.changed.emit()

    def entries(self) -> list[tuple[str, NodeError]]:
        run = [
            ("run", error)
            for (node_id, source), error in self._entries.items()
            if source == "run"
        ]
        run_ids = {
            node_id
            for (node_id, source) in self._entries
            if source == "run" and node_id is not None
        }
        live = [
            ("live", error)
            for (node_id, source), error in self._entries.items()
            if source != "run" and node_id not in run_ids
        ]
        return run + live

    def count(self, severity: str | None = None, *, roots_only: bool = False) -> int:
        return sum(
            1
            for _source, error in self.entries()
            if (severity is None or error.severity == severity)
            and (not roots_only or not error.knock_on)
        )
