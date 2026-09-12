import traceback
from loguru import logger
from qtpy.QtWidgets import QDockWidget, QVBoxLayout, QLabel, QWidget, QLayout
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from trigger_designer.qt.node_base import TriggerNode


class ConfigDock(QDockWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("Node Configuration", parent)
        self._current_key = None
        self.initUI()

    def initUI(self) -> None:
        self.dock_widget = QWidget()
        self.dock_widget.setObjectName("ConfigDockWidget")
        self.dock_widget.setMinimumWidth(300)
        self.dock_layout = QVBoxLayout()
        self.setWidget(self.dock_widget)
        self.setFloating(False)
        self.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )

    def updateConfig(self, nodes: List["TriggerNode"]) -> None:
        if len(nodes) != 1:
            self._current_key = None
            self.clear_dock()
            return
        node: TriggerNode = nodes[0]
        if not (hasattr(node, "node") or hasattr(node, "socket")):
            self._current_key = None
            self.clear_dock()
            return
        try:
            content = node.content
        except Exception as e:
            traceback.print_exc()
            logger.trace(e)
            return
        if content is None:
            self._current_key = None
            self.clear_dock()
            return
        if id(content) == self._current_key:
            # Already showing this node: skip the wipe so focused editors
            # keep focus and scroll positions survive. Live widgets refresh
            # themselves through their own non-destructive paths.
            return
        self._current_key = id(content)
        try:
            logger.debug(f"Updating config for node type: {type(node)}")
            self.clear_dock()
            logger.debug("Cleared the dock!!!")
            previous_input_tracking = getattr(content, "_suspend_input_tracking", False)
            previous_node_evaluation = getattr(
                content, "_suspend_node_evaluation", False
            )
            content._suspend_input_tracking = True
            content._suspend_node_evaluation = True
            try:
                content.create_layout(self.dock_layout)  # type: ignore
            finally:
                content._suspend_input_tracking = previous_input_tracking
                content._suspend_node_evaluation = previous_node_evaluation

            self.dock_widget.setLayout(self.dock_layout)
        except Exception as e:
            traceback.print_exc()
            logger.trace(e)

    def clear_dock(self) -> None:
        # for i in reversed(range(self.dock_layout.count())):
        #     widget = self.dock_layout.itemAt(i).widget()
        #     if widget is not None:
        #         widget.deleteLater()
        while self.dock_layout.count():
            item = self.dock_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                # Recursively clear nested layouts
                self.clear_layout(item.layout())
            # Clear spacer items as well
            self.dock_layout.removeItem(item)
            del item

        # # Reset the dock widget's layout to ensure it's clean
        # print("Clearing layout")
        # old_layout = self.dock_widget.layout()
        # if old_layout is not None:
        #     # self.dock_widget.setLayout(None)  # Detach the layout
        #     del old_layout

        # # self.dock_layout = QVBoxLayout()
        # self.dock_layout = QVBoxLayout()
        # self.dock_widget.setLayout(self.dock_layout)  # Detach the layout

        print("Layout cleared")

    def clear_layout(self, layout: QLayout) -> None:
        # Helper method to clear nested layouts
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self.clear_layout(item.layout())
            del item
