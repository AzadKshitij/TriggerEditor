import copy
from pprint import pp
from shutil import copy2
from qtpy.QtWidgets import QDockWidget, QVBoxLayout, QLabel, QWidget, QLayout


class ConfigDock(QDockWidget):
    def __init__(self, parent=None):
        super().__init__("Node Configuration", parent)
        self.initUI()

    def initUI(self):
        self.dock_widget = QWidget()
        self.dock_layout = QVBoxLayout()
        self.setWidget(self.dock_widget)
        self.setFloating(False)
        self.setFeatures(QDockWidget.DockWidgetMovable |
                         QDockWidget.DockWidgetFloatable)

    def updateConfig(self, node):
        print("Updating config for node type: ", type(node[0]))
        if len(node) == 1:
            if hasattr(node[0], 'node') or hasattr(node[0], 'socket'):
                self.clear_dock()

                node = node[0]
                content = node.content
                content.create_layout(
                    self.dock_layout)
                self.dock_widget.setLayout(self.dock_layout)
        else:
            self.clear_dock()

    def clear_dock(self):
        # for i in reversed(range(self.dock_layout.count())):
        #     widget = self.dock_layout.itemAt(i).widget()
        #     if widget is not None:
        #         widget.deleteLater()
        while self.dock_layout.count():
            item = self.dock_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            # Clear spacer items as well
            self.dock_layout.removeItem(item)
