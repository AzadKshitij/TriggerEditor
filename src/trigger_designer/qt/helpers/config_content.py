"""Shared lightweight base for Config Dock content widgets.

The shaping nodes and the older table-driven nodes had duplicated plumbing:
an ``evaluate`` signal, the node getter/setter, the dock icon setup and the
history reference. This base owns those once. Node-specific data, widgets,
serialization and code generation stay on the subclass.
"""

from __future__ import annotations

from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget
from qtpy.QtCore import Signal
from qtpy.QtGui import QPixmap
from qtpy.QtWidgets import QWidget

from trigger_designer.qt.node_base import TriggerChangeHandler, TriggerNode


class ConfigContent(QDMNodeIconContentWidget, TriggerChangeHandler):
    """Common Config Dock content plumbing for every node family."""

    evaluate = Signal()

    def __init__(self, node: TriggerNode, parent: QWidget | None = None) -> None:
        super().__init__(node, parent)
        TriggerChangeHandler.__init__(self, node.scene, node)
        self.history = node.scene.history

    @property
    def node(self) -> TriggerNode:
        return self._node

    @node.setter
    def node(self, value: TriggerNode) -> None:
        self._node = value

    def initUI(self, _icon: QPixmap | None = None) -> None:
        super().initUI(self.node.rsm.get(f"{self.node.icon}"))
