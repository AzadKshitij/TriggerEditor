#!/usr/bin/env python3
"""The canvas rendering settings the preferences drive.

The zoom threshold and the per-element modes are the user's call: which parts
of a node survive the canvas simplifying, and where that happens.
"""

import os
import sys
from collections.abc import Iterator

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)

import pytest
from qtpy.QtWidgets import QApplication

from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.preferences import Preferences
from trigger_designer.qt.render_settings import (
    apply_render_settings_to_scene,
    policy_from_preferences,
    threshold_scale,
)
from trigger_designer.qt.widgets.nodes.Preparation.select import (
    TriggerNode_Select as SelectNode,
)

_APP = QApplication.instance() or QApplication([])


@pytest.fixture
def window() -> Iterator[TriggerSubWindow]:
    win = TriggerSubWindow()
    try:
        yield win
    finally:
        win.deleteLater()


@pytest.fixture
def node(window: TriggerSubWindow) -> SelectNode:
    created = SelectNode(window.scene)
    window.scene.nodes.append(created)
    return created


@pytest.fixture
def prefs(tmp_path) -> Preferences:
    return Preferences(tmp_path / "preferences.ini", migrate=False)


def _socket(node) -> object:
    return (node.inputs or node.outputs)[0].grSocket


# -- the settings themselves ------------------------------------------------


def test_the_threshold_is_a_percentage_of_full_size(prefs) -> None:
    prefs.set("editor/render_detail_threshold", 25)
    assert threshold_scale(prefs) == 0.25


def test_the_threshold_is_clamped_to_something_sane(prefs) -> None:
    prefs.set("editor/render_detail_threshold", 500)
    assert threshold_scale(prefs) == 1.0
    prefs.set("editor/render_detail_threshold", -20)
    assert threshold_scale(prefs) == 0.0


def test_the_preferences_map_onto_the_elements_the_scene_knows(prefs) -> None:
    prefs.set("editor/render_detail_card", "never")
    prefs.set("editor/render_detail_sockets", "always")
    prefs.set("editor/render_detail_label", "auto")
    prefs.set("editor/render_detail_indicator", "always")
    policy = policy_from_preferences(prefs)
    assert policy == {
        "content": "never",
        "sockets": "always",
        "label": "auto",
        "badge": "always",
    }


def test_a_mode_the_file_does_not_know_falls_back_to_auto(prefs) -> None:
    prefs.set("editor/render_detail_sockets", "sometimes")
    assert policy_from_preferences(prefs)["sockets"] == "auto"


def test_the_defaults_come_from_the_preference_store(prefs) -> None:
    """The label defaults to always; the others follow the zoom."""
    policy = policy_from_preferences(prefs)
    assert policy == {
        "content": "auto",
        "sockets": "auto",
        "label": "always",
        "badge": "auto",
    }


# -- what the settings do to a scene ----------------------------------------


def test_the_settings_reach_the_scene(window, prefs) -> None:
    prefs.set("editor/render_detail_threshold", 30)
    apply_render_settings_to_scene(window.scene, prefs)
    gr_scene = window.scene.grScene
    assert gr_scene.detail_lod_threshold == 0.3
    assert gr_scene.detail_policy["sockets"] == "auto"


def test_a_socket_set_to_always_survives_the_zoom_out(window, node, prefs) -> None:
    prefs.set("editor/render_detail_sockets", "always")
    apply_render_settings_to_scene(window.scene, prefs)
    gr_scene = window.scene.grScene
    gr_scene.updateDetailLod(0.1)
    assert _socket(node).isVisible()


def test_a_socket_set_to_never_stays_hidden_at_full_zoom(window, node, prefs) -> None:
    prefs.set("editor/render_detail_sockets", "never")
    apply_render_settings_to_scene(window.scene, prefs)
    assert not _socket(node).isVisible()
    window.scene.grScene.updateDetailLod(1.0)
    assert not _socket(node).isVisible()


def test_a_label_set_to_always_survives_the_zoom_out(window, node, prefs) -> None:
    node.setNodeLabel("kept")
    prefs.set("editor/render_detail_label", "always")
    apply_render_settings_to_scene(window.scene, prefs)
    window.scene.grScene.updateDetailLod(0.1)
    assert node.grNode.label_item.isVisible()


def test_a_label_set_to_auto_follows_the_zoom(window, node, prefs) -> None:
    node.setNodeLabel("dropped")
    prefs.set("editor/render_detail_label", "auto")
    apply_render_settings_to_scene(window.scene, prefs)
    window.scene.grScene.updateDetailLod(0.1)
    assert not node.grNode.label_item.isVisible()


def test_the_card_set_to_never_does_not_draw_the_card(window, node, prefs) -> None:
    prefs.set("editor/render_detail_card", "never")
    apply_render_settings_to_scene(window.scene, prefs)
    assert not node.grNode._content_visible


def test_the_status_indicator_follows_its_own_mode(window, node, prefs) -> None:
    prefs.set("editor/render_detail_indicator", "never")
    apply_render_settings_to_scene(window.scene, prefs)
    assert not node.grNode._badge_visible
    prefs.set("editor/render_detail_indicator", "always")
    apply_render_settings_to_scene(window.scene, prefs)
    assert node.grNode._badge_visible


def test_the_threshold_decides_where_the_canvas_simplifies(window, node, prefs) -> None:
    prefs.set("editor/render_detail_threshold", 20)
    apply_render_settings_to_scene(window.scene, prefs)
    gr_scene = window.scene.grScene
    assert gr_scene.updateDetailLod(0.3) is False
    assert _socket(node).isVisible()
    assert gr_scene.updateDetailLod(0.1) is True
    assert not _socket(node).isVisible()


# -- the dialog --------------------------------------------------------------


def test_the_preferences_dialog_builds_the_rendering_section() -> None:
    from trigger_designer.qt.dialogs.preferences_dialog import PreferencesDialog

    dialog = PreferencesDialog()
    try:
        assert set(dialog.render_detail_combos) == {
            "card",
            "sockets",
            "label",
            "indicator",
        }
        for combo in dialog.render_detail_combos.values():
            modes = [combo.itemData(i) for i in range(combo.count())]
            assert modes == ["always", "auto", "never"]
        assert dialog.render_detail_spin.minimum() == 0
        assert dialog.render_detail_spin.maximum() == 100
    finally:
        dialog.deleteLater()


def test_choosing_a_mode_in_the_dialog_writes_the_preference() -> None:
    from trigger_designer.qt.dialogs.preferences_dialog import PreferencesDialog
    from trigger_designer.qt.preferences import get_preferences

    dialog = PreferencesDialog()
    try:
        combo = dialog.render_detail_combos["sockets"]
        combo.setCurrentIndex(combo.findData("always"))
        assert get_preferences().get("editor/render_detail_sockets") == "always"
    finally:
        dialog.deleteLater()
