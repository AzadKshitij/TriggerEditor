"""Undo/redo for Trigger Designer.

The timeline is a Qt :class:`~qtpy.QtGui.QUndoStack` owned by a
:class:`UndoController`. Every entry is a :class:`UndoableEdit`:

* :class:`PropertyChangeCommand` / :class:`ListStructureCommand` - fine grained
  inverses for a single node's settings. Cheap, and they know how to refresh
  the Config Dock without a full scene rebuild.
* :class:`SceneSnapshotCommand` - the escape hatch for anything without a
  fine grained inverse (node creation, wiring, grouping, paste). It captures
  the whole scene, so it stays correct even if we have not modelled the
  operation yet.

Two invariants keep the layer coherent:

1. **The model is the only truth.** Widgets are a projection of it, rebuilt by
   :func:`sync_from_model`. Commands mutate the model and then ask the widgets
   to catch up; they never write to widgets directly.
2. **Model -> widget never re-records.** Every write-back happens under
   :func:`syncing`, which the bindings check, so a restore can never push the
   change it is restoring.
"""

from trigger_designer.qt.undo.commands import (
    ListStructureCommand,
    PropertyChangeCommand,
    SceneSnapshotCommand,
    UndoableEdit,
    keep_old_side,
)
from trigger_designer.qt.undo.controller import (
    DEFAULT_UNDO_LIMIT,
    UndoController,
)
from trigger_designer.qt.undo.history import TriggerSceneHistory
from trigger_designer.qt.undo.protocol import (
    is_syncing,
    sync_from_model,
    syncing,
)

__all__ = [
    "DEFAULT_UNDO_LIMIT",
    "ListStructureCommand",
    "PropertyChangeCommand",
    "SceneSnapshotCommand",
    "TriggerSceneHistory",
    "UndoController",
    "UndoableEdit",
    "is_syncing",
    "keep_old_side",
    "sync_from_model",
    "syncing",
]
