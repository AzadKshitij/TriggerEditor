#!/usr/bin/env python3
"""Node labels + upstream visual groups: model behaviour and menu helpers."""

import os
import sys
import types

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)

from qtpy.QtTest import QTest
from qtpy.QtWidgets import QApplication, QWidget

APP = QApplication.instance() or QApplication([])


def _make_scene():
    from trigger_designer.qt.performance_scene import TriggerScene

    return TriggerScene()


def _make_nodes(scene, count=2):
    from nodeeditor.node_node import Node

    nodes = []
    for index in range(count):
        node = Node(scene, f"Node {index}", inputs=[1], outputs=[1])
        node.setPos(index * 250.0, 0.0)
        nodes.append(node)
    return nodes


def _mixin_host(scene):
    from trigger_designer.qt.helpers.context_menu_mixin import ContextMenuMixin

    return types.SimpleNamespace(scene=scene, __mixin__=ContextMenuMixin)


def test_label_single_line_and_accessors() -> None:
    scene = _make_scene()
    (node,) = _make_nodes(scene, 1)
    node.setNodeLabel("intake valve")
    assert node.getNodeLabel() == "intake valve"
    assert node.isNodeLabelVisible() is True
    node.setNodeLabel("line one\nline two\rline three")
    assert node.getNodeLabel() == "line one line two line three"
    node.clearNodeLabel()
    assert node.getNodeLabel() == ""


def test_label_serialize_roundtrip() -> None:
    scene = _make_scene()
    (node,) = _make_nodes(scene, 1)
    node.setNodeLabel("prefilter", store_history=False)
    node.setNodeLabelVisible(True)
    data = node.serialize()
    assert data["label_text"] == "prefilter"
    assert data["label_visible"] is True
    assert "label_offset" in data

    scene2 = _make_scene()
    (restored,) = _make_nodes(scene2, 1)
    restored.deserialize(data, hashmap={})
    assert restored.getNodeLabel() == "prefilter"
    assert restored.isNodeLabelVisible() is True


def test_label_deserialize_old_file_without_keys() -> None:
    scene = _make_scene()
    (node,) = _make_nodes(scene, 1)
    data = node.serialize()
    for key in ("label_text", "label_visible", "label_offset"):
        data.pop(key, None)
    assert node.deserialize(dict(data), hashmap={}) is not False
    assert node.getNodeLabel() == ""


def test_group_collapse_expand_edges() -> None:
    from nodeeditor.node_group import Group
    from trigger_designer.qt.performance_scene import TriggerEdge

    scene = _make_scene()
    a, b, c = _make_nodes(scene, 3)
    internal = TriggerEdge(scene, a.outputs[0], b.inputs[0])
    external = TriggerEdge(scene, b.outputs[0], c.inputs[0])

    group = Group(scene, title="G")
    group.addNode(a)
    group.addNode(b)
    group.updateBounds()
    assert group.contains(a) and group.contains(b)
    assert not group.contains(c)
    assert a.parent_group is group

    group.collapse()
    assert group.isCollapsed() is True
    internal.updatePositions()
    assert internal.grEdge.isVisible() is False
    external.updatePositions()
    assert external.grEdge.isVisible() is True
    stub = group.stubPosFor(external)
    assert stub is not None

    group.expand()
    assert group.isCollapsed() is False
    internal.updatePositions()
    external.updatePositions()
    assert internal.grEdge.isVisible() is True


def test_group_serialize_roundtrip() -> None:
    from nodeeditor.node_group import Group

    scene = _make_scene()
    a, b = _make_nodes(scene, 2)
    group = Group(scene, title="Persisted")
    group.addNode(a)
    group.addNode(b)
    group.updateBounds()

    payload = scene.serialize()
    assert "groups" in payload
    assert any(entry.get("title") == "Persisted" for entry in payload["groups"])

    # Full save/load roundtrip into an empty scene (the real file path).
    scene2 = _make_scene()
    assert scene2.deserialize(payload, hashmap={}) is not False
    assert len(scene2.groups) == 1
    assert scene2.groups[0].title == "Persisted"
    assert len(scene2.groups[0].getChildNodes()) == 2


def test_create_group_helper_and_history() -> None:
    from trigger_designer.qt.helpers.context_menu_mixin import ContextMenuMixin

    scene = _make_scene()
    scene.history.storeHistory("baseline")
    a, b = _make_nodes(scene, 2)
    host = _mixin_host(scene)

    assert ContextMenuMixin.createGroup(host, [a]) is None
    group = ContextMenuMixin.createGroup(host, [a, b])
    assert group is not None
    assert {n.id for n in group.getChildNodes()} == {a.id, b.id}
    assert scene.history.canUndo() is True


def test_set_nodes_label_visible_single_undo_step() -> None:
    from trigger_designer.qt.helpers.context_menu_mixin import ContextMenuMixin

    scene = _make_scene()
    scene.history.storeHistory("baseline")
    a, b = _make_nodes(scene, 2)
    host = _mixin_host(scene)
    for node in (a, b):
        node.setNodeLabel("tag")

    changed = ContextMenuMixin.set_nodes_label_visible(host, [a, b], False)
    assert changed == 2
    assert a.isNodeLabelVisible() is False
    assert b.isNodeLabelVisible() is False

    # One history entry covers both nodes.
    scene.history.undo()
    assert a.isNodeLabelVisible() is True
    assert b.isNodeLabelVisible() is True
    scene.history.redo()
    assert a.isNodeLabelVisible() is False

    # Showing skips nodes with no label text.
    c = _make_nodes(scene, 1)[0]
    changed = ContextMenuMixin.set_nodes_label_visible(host, [a, c], True)
    assert changed == 1
    assert a.isNodeLabelVisible() is True
    assert c.isNodeLabelVisible() is False


def test_set_nodes_label_helper() -> None:
    from trigger_designer.qt.helpers.context_menu_mixin import ContextMenuMixin

    scene = _make_scene()
    scene.history.storeHistory("baseline")
    a, b = _make_nodes(scene, 2)
    host = _mixin_host(scene)

    assert ContextMenuMixin.set_nodes_label(host, [a, b], "shared") is True
    assert a.getNodeLabel() == "shared"
    assert b.getNodeLabel() == "shared"
    # No-op text records nothing.
    assert ContextMenuMixin.set_nodes_label(host, [a], "shared") is False


def test_resolve_node_candidates_merges_clicked() -> None:
    from trigger_designer.qt.helpers.context_menu_mixin import ContextMenuMixin

    scene = _make_scene()
    a, b = _make_nodes(scene, 2)
    host = _mixin_host(scene)
    a.grNode.setSelected(True)

    clicked, candidates = ContextMenuMixin.resolve_node_candidates(host, b.grNode)
    assert clicked is b
    assert {n.id for n in candidates} == {a.id, b.id}


def test_config_dock_label_sync_survives_rebuild() -> None:
    """Stale canvas->dock closures must not touch deleted editors.

    Regression: switching selection rebuilt the dock while the previous
    node's ``labelChanged`` stayed connected to a dead ``QLineEdit``.
    """
    from trigger_designer.qt.docks.node_config import ConfigDock
    from trigger_designer.qt.widgets.nodes.Transform.count_records import (
        TriggerNode_CountRecords,
    )

    scene = _make_scene()
    scene.history.storeHistory("baseline")
    first = TriggerNode_CountRecords(scene)
    second = TriggerNode_CountRecords(scene)

    dock = ConfigDock()
    dock.updateConfig([first.grNode])
    dock.updateConfig([second.grNode])
    QTest.qWait(100)  # spin the loop so deleteLater() from the rebuild lands

    # Previously raised: RuntimeError: wrapped C/C++ object ... deleted.
    first.setNodeLabel("edited after rebuild")

    edits = [
        child
        for child in dock.findChildren(QWidget)
        if child.objectName() == "NodeLabelEdit"
    ]
    assert len(edits) == 1
    assert edits[0].text() == second.getNodeLabel()


def test_config_dock_label_edit_follows_canvas() -> None:
    from trigger_designer.qt.docks.node_config import ConfigDock
    from trigger_designer.qt.widgets.nodes.Transform.count_records import (
        TriggerNode_CountRecords,
    )

    scene = _make_scene()
    scene.history.storeHistory("baseline")
    node = TriggerNode_CountRecords(scene)

    dock = ConfigDock()
    dock.updateConfig([node.grNode])
    node.setNodeLabel("from canvas")

    edits = [
        child
        for child in dock.findChildren(QWidget)
        if child.objectName() == "NodeLabelEdit"
    ]
    assert len(edits) == 1
    assert edits[0].text() == "from canvas"


def test_config_dock_label_section_and_debounced_commit() -> None:
    from trigger_designer.qt.docks.node_config import ConfigDock
    from trigger_designer.qt.widgets.nodes.Transform.count_records import (
        TriggerNode_CountRecords,
    )

    scene = _make_scene()
    scene.history.storeHistory("baseline")
    node = TriggerNode_CountRecords(scene)
    node.setNodeLabel("dock seed", store_history=False)

    dock = ConfigDock()
    dock.updateConfig([node.grNode])
    label_edits = [
        child
        for child in dock.findChildren(QWidget)
        if child.objectName() == "NodeLabelEdit"
    ]
    assert len(label_edits) == 1
    assert label_edits[0].text() == "dock seed"

    label_edits[0].setText("dock edited")
    QTest.qWait(500)
    assert node.getNodeLabel() == "dock edited"
    assert scene.history.canUndo() is True
