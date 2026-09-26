"""Undo/redo timeline tests.

These drive a real :class:`TriggerScene` offscreen. The point is not widget
plumbing but the timeline contract: what gets recorded, what merging does,
what undo restores, and that no recording happens while a restore is running.
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
)

import pytest
from qtpy.QtWidgets import QApplication

from trigger_designer.qt.performance_scene import TriggerScene
from trigger_designer.qt.undo import (
    ListStructureCommand,
    PropertyChangeCommand,
    TriggerSceneHistory,
    keep_old_side,
)
from trigger_designer.qt.undo.binding import bind
from trigger_designer.qt.undo.protocol import sync_from_model, syncing

APP = QApplication.instance() or QApplication([])


class FakeContent:
    """Minimal content widget stand-in with the undo protocol methods."""

    def __init__(self, node, settings=None, rows=None):
        self.node = node
        self.history = node.scene.history
        self.settings = dict(settings or {})
        self.rows = list(rows or [])
        self.sync_calls = []
        self.rebuild_calls = []
        self.evaluated = 0

    def _sync_widgets_from_model(self):
        self.sync_calls.append((dict(self.settings), list(self.rows)))

    def _rebuild_widgets(self):
        self.rebuild_calls.append(list(self.rows))

    # A custom widget style signal source for bind_payload.
    class _Payload:
        pass


class FakeNode:
    def __init__(self, scene, content):
        self.scene = scene
        self.content = content


@pytest.fixture
def scene():
    return TriggerScene()


@pytest.fixture
def node(scene):
    content = FakeContent.__new__(FakeContent)
    node = FakeNode(scene, content)
    content.node = node
    content.history = scene.history
    content.settings = {"dtype": "String"}
    content.rows = []
    content.sync_calls = []
    content.rebuild_calls = []
    content.evaluated = 0
    return node


# ----------------------------------------------------------------------
# Wiring
# ----------------------------------------------------------------------


def test_scene_uses_command_stack():
    assert isinstance(TriggerScene.historyClass, type)
    assert issubclass(TriggerScene.historyClass, TriggerSceneHistory)
    scene = TriggerScene()
    assert scene.history.controller is not None
    assert scene.history.controller.count == 0


def test_initial_stamp_is_first_undo_boundary(scene):
    scene.history.storeInitialHistoryStamp()
    assert scene.history.canUndo() is False
    scene.history.storeHistory("Created node")
    assert scene.history.canUndo() is True


# ----------------------------------------------------------------------
# Property commands
# ----------------------------------------------------------------------


def test_property_change_undo_redo_round_trip(node):
    """Push applies the new value, undo returns the old one, redo re-applies.

    ``QUndoStack.push`` calls ``redo()`` on the command, so the timeline is
    self-consistent whether or not the caller mutated the model first.
    """
    history = node.scene.history
    content = node.content
    content.settings["dtype"] = "String"

    history.push_edit(
        PropertyChangeCommand(
            node, ("settings", "dtype"), "String", "Int64", "Type Changed"
        )
    )
    assert content.settings["dtype"] == "Int64"

    history.undo()
    assert content.settings["dtype"] == "String"
    assert content.sync_calls, "widgets must be resynced on undo"

    history.redo()
    assert content.settings["dtype"] == "Int64"


def test_property_command_reaches_nested_mapping(node):
    """A path crossing a dict must use key semantics, not setattr."""
    history = node.scene.history
    content = node.content
    content.settings = {"nested": {"dtype": "String"}}

    history.push_edit(
        PropertyChangeCommand(
            node, ("settings", "nested", "dtype"), "String", "Int64", "Type Changed"
        )
    )
    assert content.settings["nested"]["dtype"] == "Int64"
    history.undo()
    assert content.settings["nested"]["dtype"] == "String"


def test_property_command_records_pre_change_value(node):
    """The command captures the value to return to, not the live object."""
    content = node.content
    content.settings = {"dtype": "String"}

    cmd = PropertyChangeCommand(
        node, ("settings", "dtype"), content.settings["dtype"], "Int64", "Type Changed"
    )
    # Mutating the live dict afterwards must not corrupt the captured "old".
    content.settings["dtype"] = "Float64"
    assert cmd.old == "String"


def test_undo_text_reflects_pending_step(node):
    history = node.scene.history
    history.storeInitialHistoryStamp()
    history.push_edit(
        PropertyChangeCommand(
            node, ("settings", "dtype"), "String", "Int64", "Type Changed"
        )
    )
    assert history.currentText() == "Type Changed"
    history.undo()
    assert history.nextText() == "Type Changed"


# ----------------------------------------------------------------------
# Merging
# ----------------------------------------------------------------------


def test_burst_of_edits_merges_into_one_step(node):
    history = node.scene.history
    history.storeInitialHistoryStamp()  # baseline, not a stack entry
    for value in ("a", "ab", "abc"):
        history.push_edit(
            PropertyChangeCommand(
                node,
                ("settings", "name"),
                "prev",
                value,
                "Renamed Field",
                merge_key="field.name",
            )
        )
    assert history.controller.count == 1, "burst must collapse to one entry"


def test_merge_preserves_original_old_value(node):
    history = node.scene.history
    content = node.content
    content.settings["name"] = "start"
    history.push_edit(
        PropertyChangeCommand(
            node, ("settings", "name"), "start", "a", "Renamed Field", merge_key="n"
        )
    )
    history.push_edit(
        PropertyChangeCommand(
            node, ("settings", "name"), "a", "abc", "Renamed Field", merge_key="n"
        )
    )
    top = history.controller.top_command()
    assert top.old == "start"
    assert top.new == "abc"


def test_different_merge_keys_do_not_merge(node):
    history = node.scene.history
    history.push_edit(
        PropertyChangeCommand(node, ("settings", "a"), 1, 2, "A", merge_key="a")
    )
    history.push_edit(
        PropertyChangeCommand(node, ("settings", "b"), 1, 2, "B", merge_key="b")
    )
    assert history.controller.count == 2


def test_undo_breaks_a_merge_run(node):
    """Editing again after an undo must not fold into the redo tail."""
    history = node.scene.history
    history.push_edit(
        PropertyChangeCommand(node, ("settings", "n"), 0, 1, "Set", merge_key="n")
    )
    history.undo()
    assert not history.controller.is_at_tip()
    history.push_edit(
        PropertyChangeCommand(node, ("settings", "n"), 0, 9, "Set", merge_key="n")
    )
    assert history.controller.count == 1, "the discarded entry must be replaced"


def test_snapshot_merge_keeps_old_side():
    merged = keep_old_side(
        {"old_state": "first", "new_state": "b"},
        {"old_state": "b", "new_state": "c"},
    )
    assert merged["old_state"] == "first"
    assert merged["new_state"] == "c"


# ----------------------------------------------------------------------
# List structure
# ----------------------------------------------------------------------


def test_list_structure_command_rebuilds_widgets(node):
    history = node.scene.history
    content = node.content

    content.rows = []
    history.push_edit(
        ListStructureCommand(node, ("rows",), [], [{"i": 0}], "Added Formula")
    )
    content.rows = [{"i": 0}]

    history.undo()
    assert content.rows == []
    assert content.rebuild_calls, "structure change must rebuild widgets"

    history.redo()
    assert content.rows == [{"i": 0}]


# ----------------------------------------------------------------------
# Re-entrancy
# ----------------------------------------------------------------------


def test_history_is_not_recorded_during_undo(node):
    history = node.scene.history
    history.storeInitialHistoryStamp()
    history.push_edit(
        PropertyChangeCommand(
            node, ("settings", "dtype"), "String", "Int64", "Type Changed"
        )
    )
    before = history.controller.count

    with history.restoring(is_undo=True):
        assert history.storeHistory("should be ignored") is False
        assert (
            history.push_edit(
                PropertyChangeCommand(node, ("settings", "dtype"), "x", "y", "nope")
            )
            is False
        )
    assert history.controller.count == before


def test_restoring_is_nestable(node):
    history = node.scene.history
    with history.restoring(is_undo=True):
        with history.restoring(is_undo=False):
            assert history.is_restoring_history is True
        # Inner exit must not re-enable recording for the outer restore.
        assert history.is_restoring_history is True
    assert history.is_restoring_history is False


def test_callback_exception_does_not_abort_restore(scene):
    """A broken widget callback must not brick undo for the whole scene."""
    history = scene.history

    class Exploding:
        def history_stamp_callback(self, data, is_undo):
            raise RuntimeError("boom")

    node = FakeNode(scene, Exploding())
    history.storeInitialHistoryStamp()
    history.storeHistory(
        "Renamed Field", data={"node": node, "old_state": 1, "new_state": 2}
    )

    history.undo()  # must not raise
    history.redo()
    assert history.canUndo() is True


def test_stamp_data_for_node_without_callback_is_safe(scene):
    """Stamps pointing at a deleted node are dropped, not fatal."""
    history = scene.history
    history.storeInitialHistoryStamp()
    history.storeHistory("Deleted Node", data={"node": None})
    history.undo()
    assert history.is_restoring_history is False


# ----------------------------------------------------------------------
# Listeners
# ----------------------------------------------------------------------


def test_modified_and_restored_listeners_fire_on_undo(node):
    history = node.scene.history
    seen = {"modified": 0, "restored": 0}
    history.addHistoryModifiedListener(
        lambda: seen.__setitem__("modified", seen["modified"] + 1)
    )
    history.addHistoryRestoredListener(
        lambda: seen.__setitem__("restored", seen["restored"] + 1)
    )

    history.storeInitialHistoryStamp()
    history.push_edit(
        PropertyChangeCommand(
            node, ("settings", "dtype"), "String", "Int64", "Type Changed"
        )
    )
    before = seen["restored"]
    history.undo()
    assert seen["restored"] == before + 1
    assert seen["modified"] > 0


# ----------------------------------------------------------------------
# Bindings
# ----------------------------------------------------------------------


def test_bind_skips_noop_signal(node):
    from qtpy.QtWidgets import QCheckBox

    content = node.content
    box = QCheckBox()
    state = {"value": False}

    assert bind(
        content,
        box,
        read=lambda: state["value"],
        write=lambda v: state.__setitem__("value", v),
        text="Toggled Option",
        immediate=True,
        path=("settings", "flag"),
    )
    box.setChecked(False)  # already False -> no diff
    assert node.scene.history.controller.count == 0

    box.setChecked(True)
    assert node.scene.history.controller.count == 1


def test_bind_records_only_real_diffs(node):
    from qtpy.QtWidgets import QCheckBox

    content = node.content
    box = QCheckBox()
    state = {"value": False}
    bind(
        content,
        box,
        read=lambda: state["value"],
        write=lambda v: state.__setitem__("value", v),
        text="Toggled Option",
        immediate=True,
        path=("settings", "flag"),
    )
    box.setChecked(True)
    box.setChecked(True)
    box.setChecked(True)
    assert node.scene.history.controller.count == 1


def test_bind_is_silent_while_syncing(node):
    from qtpy.QtWidgets import QCheckBox

    content = node.content
    box = QCheckBox()
    state = {"value": False}
    bind(
        content,
        box,
        read=lambda: state["value"],
        write=lambda v: state.__setitem__("value", v),
        text="Toggled Option",
        immediate=True,
        path=("settings", "flag"),
    )
    with syncing(content):
        box.setChecked(True)
    assert node.scene.history.controller.count == 0


def test_bind_is_silent_while_suspended(node):
    from qtpy.QtWidgets import QCheckBox

    content = node.content
    box = QCheckBox()
    state = {"value": False}
    bind(
        content,
        box,
        read=lambda: state["value"],
        write=lambda v: state.__setitem__("value", v),
        text="Toggled Option",
        immediate=True,
        path=("settings", "flag"),
    )
    content._suspend_input_tracking = True
    try:
        box.setChecked(True)
    finally:
        content._suspend_input_tracking = False
    assert node.scene.history.controller.count == 0


def test_bind_does_not_double_connect(node):
    from qtpy.QtWidgets import QCheckBox

    content = node.content
    box = QCheckBox()
    state = {"value": False}
    kwargs = {
        "read": lambda: state["value"],
        "write": lambda v: state.__setitem__("value", v),
        "text": "Toggled Option",
        "immediate": True,
        "path": ("settings", "flag"),
    }
    assert bind(content, box, **kwargs) is True
    assert bind(content, box, **kwargs) is False
    box.setChecked(True)
    assert node.scene.history.controller.count == 1


# ----------------------------------------------------------------------
# Protocol
# ----------------------------------------------------------------------


def test_sync_from_model_rebuilds_and_resyncs(node):
    content = node.content
    assert sync_from_model(content, rebuild=True) is True
    assert content.rebuild_calls == [[]]
    assert len(content.sync_calls) == 1


def test_sync_from_model_tolerates_missing_content():
    assert sync_from_model(None) is False


# ----------------------------------------------------------------------
# TriggerChangeHandler registration
# ----------------------------------------------------------------------


def test_register_input_widget_makes_edits_undoable(node):
    """Exercises the real binding path a node uses from create_layout."""
    from qtpy.QtWidgets import QCheckBox

    from trigger_designer.qt.node_base import TriggerChangeHandler

    node.content._undo_tracked_values = {}
    handler = TriggerChangeHandler(node.scene, node)
    box = QCheckBox()

    # newFile/fileLoad/fileSave all seed this before any user edit, and the
    # seed is the undo floor rather than a step of its own.
    node.scene.history.storeInitialHistoryStamp()

    assert handler.registerInputWidget(box, text="Toggled Option") is True
    assert box in handler._input_widgets

    # The widget is seeded at registration, so the first edit records a real
    # before value rather than an entry with nothing to return to.
    box.setChecked(True)
    assert node.scene.history.controller.count == 1
    assert node.scene.history.currentText() == "Toggled Option"


def test_register_input_widget_ignores_untracked_widgets(node):
    from qtpy.QtWidgets import QWidget

    from trigger_designer.qt.node_base import TriggerChangeHandler

    node.content._undo_tracked_values = {}
    handler = TriggerChangeHandler(node.scene, node)
    assert handler.is_input_widget(QWidget()) is False
    assert handler.registerInputWidget(QWidget()) is False


def test_clear_input_widgets_drops_registrations(node):
    from qtpy.QtWidgets import QCheckBox

    from trigger_designer.qt.node_base import TriggerChangeHandler

    node.content._undo_tracked_values = {}
    handler = TriggerChangeHandler(node.scene, node)
    box = QCheckBox()
    handler.registerInputWidget(box)
    assert handler._input_widgets

    handler.clearInputWidgets()
    assert handler._input_widgets == []
    assert handler._tracked_values() == {}


# ----------------------------------------------------------------------
# Value reading
# ----------------------------------------------------------------------


def test_value_of_list_widget_uses_count_not_rowcount():
    """Regression: QListWidget has count(), not rowCount().

    Getting this wrong raised out of create_layout, which ConfigDock catches
    broadly - so the node's entire config panel silently came up blank.
    """
    from qtpy.QtWidgets import QListWidget

    from trigger_designer.qt.undo.binding import is_missing, safe_value_of, value_of

    widget = QListWidget()
    widget.addItems(["alpha", "beta"])
    assert value_of(widget) == ["alpha", "beta"]
    assert not is_missing(safe_value_of(widget))


def test_value_of_table_widget():
    from qtpy.QtWidgets import QTableWidget, QTableWidgetItem

    from trigger_designer.qt.undo.binding import value_of

    table = QTableWidget(2, 2)
    table.setItem(0, 0, QTableWidgetItem("a"))
    table.setItem(1, 1, QTableWidgetItem("b"))
    assert value_of(table) == [["a", ""], ["", "b"]]


def test_value_of_common_controls():
    from qtpy.QtWidgets import QCheckBox, QComboBox, QDoubleSpinBox, QLineEdit

    from trigger_designer.qt.undo.binding import value_of

    line = QLineEdit()
    line.setText("hello")
    assert value_of(line) == "hello"

    check = QCheckBox()
    assert value_of(check) is False
    check.setChecked(True)
    assert value_of(check) is True

    spin = QDoubleSpinBox()
    spin.setValue(1.5)
    assert value_of(spin) == 1.5

    combo = QComboBox()
    combo.addItems(["x", "y"])
    combo.setCurrentText("y")
    assert value_of(combo) == "y"


def test_safe_value_of_reports_failure_instead_of_raising():
    """safe_value_of must never raise - it runs inside create_layout."""
    from qtpy.QtWidgets import QWidget

    from trigger_designer.qt.undo.binding import is_missing, safe_value_of

    plain = QWidget()
    # A bare QWidget exposes none of the tracked accessors, so the fallback
    # probe finds nothing and returns None rather than raising.
    assert not is_missing(safe_value_of(plain))


def test_register_input_widget_skips_unreadable_widget(node):
    """An unreadable control is skipped, not allowed to break create_layout."""
    from qtpy.QtWidgets import QWidget

    from trigger_designer.qt.node_base import TriggerChangeHandler

    node.content._undo_tracked_values = {}
    handler = TriggerChangeHandler(node.scene, node)

    class Hostile(QWidget):
        """A tracked-typed widget whose accessors blow up."""

        def value(self):
            raise RuntimeError("boom")

    hostile = Hostile()
    # Force it down the trackable branch.
    import trigger_designer.qt.node_base as nb

    original = nb.widget_accepts_tracking
    nb.widget_accepts_tracking = lambda w: isinstance(w, QWidget) and w is hostile
    try:
        assert handler.registerInputWidget(hostile) is False
    finally:
        nb.widget_accepts_tracking = original
    assert hostile not in handler._input_widgets


# ----------------------------------------------------------------------
# Config Dock resilience
# ----------------------------------------------------------------------


def test_input_widgets_is_lazy_for_non_cooperating_init(node):
    """Regression: TransposeContent never runs TriggerChangeHandler.__init__.

    Several content classes are declared
    ``(QDMNodeIconContentWidget, TriggerChangeHandler)`` and override
    ``__init__`` without chaining, so attributes assigned in the handler's
    ``__init__`` never exist. Reading ``_input_widgets`` then raised out of
    ``create_layout``, which ConfigDock catches broadly - leaving that node's
    config panel silently blank.
    """
    from qtpy.QtWidgets import QCheckBox

    from trigger_designer.qt.node_base import TriggerChangeHandler

    class NoSuperInit:
        """Stands in for a content class that skips the cooperative __init__."""

        registerInputWidget = TriggerChangeHandler.registerInputWidget
        recursively_find_widgets = TriggerChangeHandler.recursively_find_widgets
        is_input_widget = TriggerChangeHandler.is_input_widget
        clearInputWidgets = TriggerChangeHandler.clearInputWidgets
        _tracked_values = TriggerChangeHandler._tracked_values
        _input_widgets = TriggerChangeHandler._input_widgets

    bare = NoSuperInit()
    bare.node = node
    assert bare._input_widgets == [], "must materialise on read, not raise"

    box = QCheckBox()
    assert bare.registerInputWidget(box) is True
    assert bare._input_widgets == [box]


def test_config_dock_remembers_the_node_it_shows():
    """A restore can clear the selection; the dock must still know its node."""
    from qtpy.QtWidgets import QLabel, QWidget

    from trigger_designer.qt.docks.node_config import ConfigDock

    class Content:
        def create_layout(self, layout):
            layout.addWidget(QLabel("x"))

    class Node:
        def __init__(self):
            self.content = Content()

    class Graphics:
        def __init__(self, node):
            self.node = node
            self.content = node.content

    dock = ConfigDock()
    assert dock.currentNode() is None

    node = Node()
    dock.updateConfig([Graphics(node)])
    assert dock.currentNode() is not None

    dock.updateConfig([])
    assert dock.currentNode() is None
    del QWidget


# ----------------------------------------------------------------------
# Dock registration sweep
# ----------------------------------------------------------------------


def test_iter_dock_widgets_descends_into_scroll_areas(node):
    """Regression: nodes wrap their panel in a QScrollArea.

    The controls live under ``scrollArea.widget()``, which is not reachable
    from any layout on the dock, so the sweep found nothing and Cleansing had
    no undo path at all.
    """
    from qtpy.QtWidgets import QScrollArea, QVBoxLayout, QWidget

    from trigger_designer.qt.node_base import TriggerChangeHandler

    handler = TriggerChangeHandler(node.scene, node)
    outer = QVBoxLayout()
    scroll = QScrollArea()
    inner_widget = QWidget()
    inner_widget.setLayout(QVBoxLayout())
    scroll.setWidget(inner_widget)
    outer.addWidget(scroll)

    found = list(handler.iter_dock_widgets(outer))
    assert inner_widget in found


def test_iter_dock_widgets_does_not_call_widget_on_text_edits(node):
    """QTextEdit/QTableView are QAbstractScrollArea but have no .widget()."""
    from qtpy.QtWidgets import QTableView, QTextEdit, QVBoxLayout

    from trigger_designer.qt.node_base import TriggerChangeHandler

    handler = TriggerChangeHandler(node.scene, node)
    outer = QVBoxLayout()
    outer.addWidget(QTextEdit())
    outer.addWidget(QTableView())

    # Must not raise AttributeError.
    found = list(handler.iter_dock_widgets(outer))
    assert len(found) == 2


def test_sweep_skips_widgets_inside_a_composite(node):
    """A composite owns its signal; binding its children would double-record."""
    from qtpy.QtWidgets import QCheckBox, QVBoxLayout, QWidget

    from trigger_designer.qt.helpers.content_undo_mixin import _COMPOSITE_ATTR
    from trigger_designer.qt.node_base import TriggerChangeHandler

    node.content._undo_tracked_values = {}
    handler = TriggerChangeHandler(node.scene, node)

    composite = QWidget()
    setattr(composite, _COMPOSITE_ATTR, True)
    inner = QVBoxLayout(composite)
    box = QCheckBox()
    inner.addWidget(box)
    outer = QVBoxLayout()
    outer.addWidget(composite)

    assert handler.registerUnboundDockWidgets(outer) == 0
    assert box not in handler._input_widgets


def test_sweep_registers_unbound_controls(node):
    from qtpy.QtWidgets import QCheckBox, QLineEdit, QVBoxLayout

    from trigger_designer.qt.node_base import TriggerChangeHandler

    node.content._undo_tracked_values = {}
    handler = TriggerChangeHandler(node.scene, node)
    outer = QVBoxLayout()
    box = QCheckBox()
    line = QLineEdit()
    outer.addWidget(box)
    outer.addWidget(line)

    assert handler.registerUnboundDockWidgets(outer) == 2
    assert handler.registerUnboundDockWidgets(outer) == 0, "idempotent"
