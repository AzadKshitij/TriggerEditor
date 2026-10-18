#!/usr/bin/env python3
"""Data Preview wiring: shared dock creation, Window menu, scene hooks."""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)

from qtpy.QtCore import QSettings
from qtpy.QtWidgets import QApplication, QMainWindow

from trigger_designer.core.node_configuration import (
    NodeTypes,
    PreparationNodes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.helpers.preview_dock_state import (
    VISIBLE_KEY,
    DataPreviewDockState,
)
from trigger_designer.qt.main_window import TriggerWindow

_APP = QApplication.instance() or QApplication([])


def _main_window() -> TriggerWindow:
    window = TriggerWindow()
    # Activation of a design window only happens in a shown mdi area, so the
    # dock-following paths are only reachable once the window is visible.
    window.show()
    _APP.processEvents()
    return window


def _active_design_window(window: TriggerWindow) -> TriggerSubWindow:
    window.onFileNew()
    _APP.processEvents()
    sub = window.mdiArea.subWindowList()[0]
    window.mdiArea.setActiveSubWindow(sub)
    _APP.processEvents()
    return sub.widget()


def test_preview_dock_is_created_and_tabified_with_logs():
    window = _main_window()

    assert window.dataPreviewDock is not None
    assert window.dataPreviewDock in window.tabifiedDockWidgets(window.loggingDock)
    assert window.dataPreviewDock.windowTitle() == "Data Preview"


def test_window_menu_exposes_preview_and_config_toggles():
    window = _main_window()
    window.updateWindowMenu()
    actions = {action.text(): action for action in window.windowMenu.actions()}

    assert "Data Preview" in actions
    assert "Node Configuration" in actions

    preview = actions["Data Preview"]
    assert preview.isCheckable()
    assert preview.shortcut().toString() == "Ctrl+Shift+D"

    checked = preview.isChecked()
    preview.trigger()
    assert preview.isChecked() is not checked
    assert window.dataPreviewDock.isVisibleTo(window) is preview.isChecked()


def test_design_window_close_drops_the_followed_state():
    window = _main_window()
    design = _active_design_window(window)
    design.setWindowTitle("Preview Probe")
    window.switchDataPreviewDock(design)
    assert window.dataPreviewDock.windowTitle() == "Data Preview - Preview Probe"

    window.onDesignWindowClose(design, None)

    assert window.dataPreviewDock.windowTitle() == "Data Preview"


def test_design_window_events_reach_the_dock():
    window = _main_window()
    design = _active_design_window(window)
    dock = window.dataPreviewDock
    assert dock.current_design_window_id == str(id(design))

    calls = []
    originals = (
        dock.note_selection_changed,
        dock.note_node_evaluated,
        dock.note_run_finished,
    )
    dock.note_selection_changed = lambda followed: calls.append(("select", followed))
    dock.note_node_evaluated = lambda followed, node: calls.append(
        ("eval", followed, node)
    )
    dock.note_run_finished = lambda followed: calls.append(("run", followed))
    try:
        design.scene.grScene.itemSelected.emit()
        design.scene.notifyNodeEvaluated("node-a")
        design.executionResultsChanged.emit()
    finally:
        (
            dock.note_selection_changed,
            dock.note_node_evaluated,
            dock.note_run_finished,
        ) = originals

    assert calls == [
        ("select", design),
        ("eval", design, "node-a"),
        ("run", design),
    ]


def test_eval_notifies_scene_listeners_only_on_recompute():
    parent = QMainWindow()
    window = TriggerSubWindow(parent)
    scene = window.scene
    seen = []
    scene.addNodeEvaluatedListener(seen.append)

    cls = get_class_from_opcode(PreparationNodes.SELECT, NodeTypes.PREPARATION)
    node = cls(scene)
    scene.nodes.append(node)
    node.evalImplementation = lambda: "ok"
    seen.clear()  # node construction may already have evaluated once

    node.markDirty(True)
    node.eval()
    assert seen == [node]

    # A cache hit returns before the notification, so the table of a node
    # shown in the dock is not rebuilt for reads that changed nothing.
    seen.clear()
    node.markDirty(False)
    node.markInvalid(False)
    node.eval()
    assert seen == []


def test_visible_flag_round_trips_through_qsettings():
    settings = QSettings("TestDataPreviewOrg", "TestDataPreviewApp")
    settings.clear()
    try:
        state = DataPreviewDockState(settings)

        assert state.read() is False

        state.write(True)
        assert state.read() is True

        settings.setValue(VISIBLE_KEY, "true")  # QSettings may hand back text
        assert state.read() is True

        state.write(False)
        assert state.read() is False
    finally:
        settings.clear()
