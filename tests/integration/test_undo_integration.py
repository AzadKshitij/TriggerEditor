"""Undo/redo integration: real window, real nodes, real Config Dock.

The unit tests stub the scene; this one drives the wiring they cannot reach -
``TriggerSubWindow.onHistoryRestored`` forcing the Config Dock to rebuild, the
Edit-menu label, and the ``scene.history`` -> ``QUndoStack`` path - against a
real design window offscreen.
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
)

import polars as pl
import pytest
from qtpy.QtWidgets import QApplication, QMainWindow

from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.docks.node_config import ConfigDock
from trigger_designer.qt.helpers.main_window_ui_mixin import MainWindowMenuMixin
from trigger_designer.qt.undo import PropertyChangeCommand
from trigger_designer.qt.widgets.nodes.Preparation.formula import (
    TriggerNode_Formula as FormulaNode,
)
from trigger_designer.qt.widgets.nodes.Preparation.select import (
    TriggerNode_Select as SelectNode,
)

APP = QApplication.instance() or QApplication([])


@pytest.fixture
def window():
    # Mirror the real hierarchy: the MDI subwindow's parent is the main
    # window, and refreshConfigDock walks parentWidget() looking for
    # configDock.
    parent = QMainWindow()
    dock = ConfigDock(parent)
    parent.configDock = dock
    win = TriggerSubWindow(parent)
    yield win
    win.close()
    win.deleteLater()


@pytest.fixture
def nodes(window):
    formula = FormulaNode(window.scene)
    select = SelectNode(window.scene)
    window.scene.nodes.append(formula)
    window.scene.nodes.append(select)
    return formula, select


def _reset(history):
    """Clear the timeline so a count delta is unambiguous.

    Editing straight after an undo discards the redo tail, which would
    otherwise skew the arithmetic in these assertions.
    """
    history.clear()
    history.storeInitialHistoryStamp()


# ----------------------------------------------------------------------
# Timeline wiring
# ----------------------------------------------------------------------


def test_scene_history_is_a_command_stack(window):
    assert hasattr(window.scene.history, "controller")
    assert not window.scene.history.canUndo()
    assert window.scene.history.currentText() == ""


def test_baseline_alone_is_not_undoable(window):
    window.scene.history.storeInitialHistoryStamp()
    assert not window.scene.history.canUndo()


# ----------------------------------------------------------------------
# Formula add / remove
# ----------------------------------------------------------------------


def test_formula_change_round_trips(window, nodes):
    formula, _ = nodes
    history = window.scene.history
    _reset(history)

    old_sections = [dict(s) for s in formula.content.formula_sections]
    formula.content.formula_sections = old_sections + [
        {"target_column": "doubled", "formula_text": "[amount] * 2"}
    ]
    formula.content.store_history({"formula_sections": old_sections})

    assert history.canUndo()
    assert history.currentText() == "Formula Changed"
    assert history.controller.count == 1

    history.undo()
    assert len(formula.content.formula_sections) == len(old_sections)
    assert history.canRedo()
    assert history.nextText() == "Formula Changed"

    history.redo()
    assert len(formula.content.formula_sections) == len(old_sections) + 1
    assert not history.canRedo()


def test_each_added_section_is_its_own_step(window, nodes):
    formula, _ = nodes
    history = window.scene.history
    _reset(history)
    before = history.controller.count

    for index in range(5):
        sections = [dict(s) for s in formula.content.formula_sections]
        formula.content.formula_sections = sections + [
            {"target_column": f"c{index}", "formula_text": "1"}
        ]
        formula.content.store_history({"formula_sections": sections})

    # Five separate clicks are five separate undo steps - only a *burst* of
    # typing collapses.
    assert history.controller.count == before + 5


# ----------------------------------------------------------------------
# Merging
# ----------------------------------------------------------------------


def test_rename_keystroke_burst_collapses_to_one_step(window, nodes):
    _, select = nodes
    history = window.scene.history
    _reset(history)

    for text in ("a", "ab", "abc", "abcd"):
        select.content.rename_input_text = text
        history.push_edit(
            PropertyChangeCommand(
                select,
                ("rename_input_text",),
                "start",
                text,
                "Renamed Field",
                merge_key="select.rename",
            )
        )

    assert history.controller.count == 1
    top = history.controller.top_command()
    assert top.old == "start", "a burst must undo to where it began"
    assert top.new == "abcd"

    history.undo()
    assert select.content.rename_input_text == "start"
    history.redo()
    assert select.content.rename_input_text == "abcd"


# ----------------------------------------------------------------------
# Select: rename + column selection
# ----------------------------------------------------------------------


def test_select_rename_and_selection_is_undoable(window, nodes):
    _, select = nodes
    history = window.scene.history
    _reset(history)

    old_changes = {"selected_columns": [], "rename_mapping": {}, "dtype_mapping": {}}
    new_changes = {
        "selected_columns": ["amount"],
        "rename_mapping": {"amount": "total_amount"},
        "dtype_mapping": {},
    }
    select.content.data = pl.DataFrame({"amount": [1, 2]})
    select.content.incoming_variable = "input_df"
    select.content.changes = {
        key: (list(value) if isinstance(value, list) else dict(value))
        for key, value in new_changes.items()
    }
    select.content.apply_changes()

    history.push_edit(
        PropertyChangeCommand(
            select,
            ("changes",),
            old_changes,
            new_changes,
            "Column Selection/Rename/Type Changed",
        )
    )

    assert history.currentText() == "Column Selection/Rename/Type Changed"
    history.undo()
    assert select.content.changes["rename_mapping"] == {}
    assert select.content.changes["selected_columns"] == []
    history.redo()
    assert select.content.changes["rename_mapping"] == {"amount": "total_amount"}


# ----------------------------------------------------------------------
# Config Dock resync
# ----------------------------------------------------------------------


def test_dock_is_rebuilt_after_a_restore(window, nodes):
    """The bug this rework exists to fix.

    A restore reverts the *selected* node in place, so ``ConfigDock``'s
    ``_current_key`` check used to short-circuit and leave the dock showing
    values the model no longer held. The restore has to force a rebuild.
    """
    formula, _ = nodes
    # The dock hangs off the parent, as refreshConfigDock expects.
    dock = window.parent().configDock
    history = window.scene.history
    _reset(history)

    formula.grNode.setSelected(True)
    window.refreshConfigDock(force=True)
    assert dock._current_key == id(formula.content)

    history.push_edit(
        PropertyChangeCommand(
            formula,
            ("formula_sections",),
            formula.content.formula_sections,
            [{"target_column": "x", "formula_text": "1"}],
            "Formula Changed",
        )
    )
    history.undo()

    # onHistoryRestored fires through the controller and must have rebuilt.
    assert dock._current_key == id(formula.content)


# ----------------------------------------------------------------------
# Edit menu
# ----------------------------------------------------------------------


class _Action:
    def __init__(self):
        self.text = None
        self.enabled = None

    def setText(self, value):
        self.text = value

    def setEnabled(self, value):
        self.enabled = value


class _FakeMainWindow(MainWindowMenuMixin):
    def __init__(self, editor):
        self.actUndo = _Action()
        self.actRedo = _Action()
        self.actPaste = self.actCut = self.actCopy = self.actDelete = _Action()
        self._editor = editor

    def getCurrentNodeEditorWidget(self):
        return self._editor


def test_edit_menu_names_the_pending_step(window, nodes):
    _, select = nodes
    history = window.scene.history
    _reset(history)

    history.push_edit(
        PropertyChangeCommand(
            select, ("changes",), {}, {"selected_columns": ["a"]}, "Selected Field"
        )
    )

    main = _FakeMainWindow(window)
    main.updateEditMenu()
    assert main.actUndo.enabled is True
    assert main.actUndo.text == "&Undo Selected Field"

    history.undo()
    main.updateEditMenu()
    assert main.actRedo.enabled is True
    assert main.actRedo.text == "&Redo Selected Field"

    while history.canUndo():
        history.undo()
    main.updateEditMenu()
    assert main.actUndo.enabled is False
    assert main.actUndo.text == "&Undo"
