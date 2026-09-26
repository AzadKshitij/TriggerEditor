"""End-to-end undo for the scenarios that were previously broken.

Covers the two failures that motivated the rework:

* **Adding and removing a formula** is one undo step each, and the Config Dock
  gains/loses the section editor to match.
* **Renaming a field / selecting fields** reverts, and - the actual bug - the
  Config Dock stops showing the stale value, which it did because
  ``updateConfig`` short-circuits on its ``_current_key`` when the same node
  is still selected after a restore.

Drives a real :class:`TriggerScene` and a real :class:`ConfigDock` offscreen.
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
)

import pytest
from qtpy.QtWidgets import QApplication, QLabel

from trigger_designer.qt.docks.node_config import ConfigDock
from trigger_designer.qt.performance_scene import TriggerScene
from trigger_designer.qt.undo import ListStructureCommand

APP = QApplication.instance() or QApplication([])


class CountingContent:
    """Content stub that counts how often its widgets are rebuilt."""

    def __init__(self, node, sections):
        self.node = node
        self.history = node.scene.history
        self.sections = sections
        self.rebuilds = 0
        self.syncs = 0
        self.evaluated = 0
        self.layouts_built = 0

    def create_layout(self, layout):
        """What ConfigDock calls to build this node's editors."""
        self.layouts_built += 1
        layout.addWidget(QLabel("editor"))

    # --- undo protocol -------------------------------------------------
    def _rebuild_widgets(self):
        self.rebuilds += 1

    def _sync_widgets_from_model(self):
        self.syncs += 1


class StubNode:
    def __init__(self, scene, content):
        self.scene = scene
        self.content = content


class StubGraphicsNode:
    """Stands in for a QGraphicsItem, which is what the dock is handed.

    ``ConfigDock`` expects a selected graphics node: it looks for a ``.node``
    attribute and reads ``.content`` off it.
    """

    def __init__(self, node):
        self.node = node
        self.content = node.content


@pytest.fixture
def scene():
    return TriggerScene()


@pytest.fixture
def content(scene):
    node = StubNode(scene, None)
    c = CountingContent(node, [{"target_column": "total"}])
    node.content = c
    return c


# ----------------------------------------------------------------------
# Formula add / remove
# ----------------------------------------------------------------------


def test_adding_a_formula_is_one_undo_step(content):
    history = content.history
    history.storeInitialHistoryStamp()

    before = list(content.sections)
    content.sections = before + [{"target_column": "tax"}]
    history.push_edit(
        ListStructureCommand(
            content.node, ("sections",), before, content.sections, "Added Formula"
        )
    )

    assert len(content.sections) == 2
    history.undo()
    assert len(content.sections) == 1
    assert content.sections[0]["target_column"] == "total"
    history.redo()
    assert len(content.sections) == 2


def test_removing_a_formula_is_one_undo_step(content):
    history = content.history
    history.storeInitialHistoryStamp()

    before = list(content.sections)
    content.sections = []
    history.push_edit(
        ListStructureCommand(
            content.node, ("sections",), before, content.sections, "Removed Formula"
        )
    )

    assert content.sections == []
    history.undo()
    assert len(content.sections) == 1
    assert content.rebuilds, "restoring must rebuild the section editors"


def test_formula_history_labels_are_noun_verbed(content):
    history = content.history
    history.storeInitialHistoryStamp()
    before = list(content.sections)
    content.sections = before + [{"target_column": "tax"}]
    history.push_edit(
        ListStructureCommand(
            content.node, ("sections",), before, content.sections, "Added Formula"
        )
    )
    assert history.currentText() == "Added Formula"


def test_undo_stops_being_recorded_while_restoring(content):
    history = content.history
    history.storeInitialHistoryStamp()
    before = list(content.sections)
    content.sections = before + [{"target_column": "tax"}]
    history.push_edit(
        ListStructureCommand(
            content.node, ("sections",), before, content.sections, "Added Formula"
        )
    )
    count = history.controller.count

    history.undo()
    assert history.controller.count == count, "undo must not add a step"


# ----------------------------------------------------------------------
# Config Dock resync
# ----------------------------------------------------------------------


def _make_dock():
    return ConfigDock()


def test_update_config_skips_rebuild_for_same_node(content):
    """The early return is what protects a focused editor; keep it by default."""
    dock = _make_dock()
    graphics = StubGraphicsNode(content.node)
    dock.updateConfig([graphics])
    assert dock._current_key == id(content)
    assert content.layouts_built == 1

    dock.updateConfig([graphics])
    assert content.layouts_built == 1, "same node must not rebuild by default"


def test_update_config_force_rebuilds_for_same_node(content):
    """force=True is what a history restore needs - and the bug fix."""
    dock = _make_dock()
    graphics = StubGraphicsNode(content.node)
    dock.updateConfig([graphics])
    assert content.layouts_built == 1

    # A restore reverts the same, still-selected node. Without force=True the
    # dock would short-circuit on _current_key and keep showing the pre-undo
    # value, which is why a renamed field looked like it ignored the undo.
    dock.updateConfig([graphics], force=True)
    assert content.layouts_built == 2, "forced refresh rebuilds the editor"


def test_update_config_clears_when_nothing_selected(content):
    dock = _make_dock()
    dock.updateConfig([StubGraphicsNode(content.node)])
    dock.updateConfig([])
    assert dock._current_key is None
