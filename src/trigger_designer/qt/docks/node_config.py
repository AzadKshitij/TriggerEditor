import traceback
from loguru import logger
from qtpy.QtWidgets import QDockWidget, QVBoxLayout, QLabel, QWidget, QLayout
from typing import Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    from trigger_designer.qt.node_base import TriggerNode


class ConfigDock(QDockWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("Node Configuration", parent)
        self.initUI()

    def initUI(self) -> None:
        self.dock_widget = QWidget()
        self.dock_widget.setObjectName("ConfigDockWidget")
        self.dock_widget.setMinimumWidth(300)
        self.dock_layout = QVBoxLayout()
        self.setWidget(self.dock_widget)
        self.setFloating(False)
        self.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable |
                         QDockWidget.DockWidgetFeature.DockWidgetFloatable)

    def updateConfig(self, nodes: List['TriggerNode']) -> None:
        if len(nodes) == 1:
            node: TriggerNode = nodes[0]
            if hasattr(node, 'node') or hasattr(node, 'socket'):
                try:
                    logger.debug(
                        f"Updating config for node type: {type(node)}")
                    self.clear_dock()
                    logger.debug("Cleared the dock!!!")
                    content = node.content
                    content.create_layout(self.dock_layout)  # type: ignore
                    self.dock_widget.setLayout(self.dock_layout)
                except Exception as e:
                    traceback.print_exc()
                    logger.trace(e)
        else:
            self.clear_dock()

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
