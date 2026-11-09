#!/usr/bin/env python3
"""The Config Dock rebuilds when the selected node becomes ready.

Issue #22: a shaping node picked before its inputs compute shows only the
"No incoming data available" empty state. When evaluation later succeeded,
``_refresh_selected_node_config`` reached the dock with the *same* node, so
``updateConfig`` short-circuited on ``_current_key`` and the empty layout
stuck until the user clicked away and back. The dock now remembers the
readiness it displayed and rebuilds when it changes.
"""

from __future__ import annotations

import polars as pl
from nodeeditor.node_edge import Edge
from qtpy.QtWidgets import QWidget

from trigger_designer.core.node_configuration import (
    JoinNodes,
    NodeTypes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.docks.node_config import ConfigDock
from trigger_designer.qt.node_base import TriggerNode
from trigger_designer.qt.widgets.common import ColumnPicker


class Source(TriggerNode):
    node_title = "Source"

    def __init__(self, scene, frame, name: str) -> None:
        self._frame = frame
        self._name = name
        super().__init__(scene, inputs=[], outputs=[3])
        self.value = [{"data": frame, "variable_name": name}]
        self.markDirty(False)
        self.markInvalid(False)

    def evalImplementation(self):
        self.value = [{"data": self._frame, "variable_name": self._name}]
        self.markDirty(False)
        self.markInvalid(False)
        return self.value


def _frame() -> pl.DataFrame:
    return pl.DataFrame({"id": [1, 2]})


def _join_node(window):
    cls = get_class_from_opcode(JoinNodes.JOIN, NodeTypes.JOIN)
    return cls(window.scene)


def _layout_widgets(dock: ConfigDock) -> list[QWidget]:
    """Widgets the dock layout currently holds, in order.

    The layout, not ``findChildren``: a rebuild's ``deleteLater`` widgets
    stay children until the event loop runs, while the layout only ever
    lists the live ones.
    """
    widgets = []
    for index in range(dock.dock_layout.count()):
        widget = dock.dock_layout.itemAt(index).widget()
        if widget is not None:
            widgets.append(widget)
    return widgets


def _layout_names(dock: ConfigDock) -> list[str]:
    return [widget.objectName() for widget in _layout_widgets(dock)]


def test_dock_rebuilds_when_the_node_becomes_ready(qtbot) -> None:
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    dock = ConfigDock()
    qtbot.addWidget(dock)

    node = _join_node(window)
    dock.updateConfig([node.grNode])

    # Not connected yet: the empty state, no controls.
    assert "EmptyStateLabel" in _layout_names(dock)

    left = Source(window.scene, _frame().lazy(), "var_left")
    right = Source(window.scene, _frame().lazy(), "var_right")
    Edge(window.scene, left.outputs[0], node.inputs[0])
    Edge(window.scene, right.outputs[0], node.inputs[1])
    node.markDirty(True)
    node.eval()

    # Same node, same dock call - but the node is ready now, so the refresh
    # that succeed() triggers must replace the empty state with controls.
    dock.updateConfig([node.grNode])
    assert "EmptyStateLabel" not in _layout_names(dock)
    assert node.content.output_picker in dock.dock_widget.findChildren(ColumnPicker)


def test_a_ready_node_keeps_its_widgets_across_refreshes(qtbot) -> None:
    """The early return must survive: no rebuild while nothing changed."""
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    dock = ConfigDock()
    qtbot.addWidget(dock)

    node = _join_node(window)
    left = Source(window.scene, _frame().lazy(), "var_left")
    right = Source(window.scene, _frame().lazy(), "var_right")
    Edge(window.scene, left.outputs[0], node.inputs[0])
    Edge(window.scene, right.outputs[0], node.inputs[1])
    node.markDirty(True)
    node.eval()

    dock.updateConfig([node.grNode])
    before = _layout_widgets(dock)
    assert before, "the dock built nothing"
    dock.updateConfig([node.grNode])
    after = _layout_widgets(dock)
    # The same widgets both times: the second refresh must not rebuild.
    assert [id(widget) for widget in before] == [id(widget) for widget in after]
