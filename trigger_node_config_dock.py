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
        self.clear_dock()
        print("Updating configuration ...")

        if len(node) == 1:
            node = node[0]
            content = node.content
            new_layout = content.create_layout()
            for i in range(new_layout.count()):
                widget = new_layout.itemAt(i).widget()
                print(f"Removing widget {i}: {widget}")
                self.dock_layout.addWidget(widget)
                self.dock_widget.setLayout(self.dock_layout)
            # for i in reversed(range(self.dock_layout.count())):
            #     widget = self.dock_layout.itemAt(i).widget()
            #     print(f"Removing widget {i}: {widget}")
                # self.dock_layout.addWidget(new_layout)

    def clear_dock(self):
        for i in reversed(range(self.dock_layout.count())):
            widget = self.dock_layout.itemAt(i).widget()
            if widget is not None:
                widget.deleteLater()

    # def clearLayout(self, layout: QLayout):
    #     print("::::::::::::::::::::::::")
    #     print("Clearing layout ...")
    #     """Recursively clear a layout and its children."""
    #     while layout.count():
    #         print("Layout count: ", layout.count())
    #         item = layout.takeAt(0)
    #         widget = item.widget()  # If the item is a widget
    #         child_layout = item.layout()
    #         if widget:
    #             print("Widget found: ", widget)
    #             widget.deleteLater()  # Safely delete the widget
    #         elif child_layout:
    #             child_layout.deleteLater()
    #             # print("Layout found: ", child_layout)
    #             # Recursively clear child layouts
    #             # self.clearLayout(child_layout)
    #         # if item.widget():
    #         #     item.widget().deleteLater()
    #         # elif item.layout():
    #         #     self.clearLayout(item.layout())
