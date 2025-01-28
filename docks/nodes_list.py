from qtpy.QtWidgets import QDockWidget
from widgets.node_drag_listbox import QTRDragListbox


class NodesDock(QDockWidget):
    def __init__(self, parent=None):
        super().__init__("Nodes", parent)
        self.initUI()

    def initUI(self):
        self.nodesListWidget = QTRDragListbox()
        self.setWidget(self.nodesListWidget)
        self.setFloating(False)
        self.setFeatures(QDockWidget.DockWidgetMovable |
                         QDockWidget.DockWidgetFloatable)
        # self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
