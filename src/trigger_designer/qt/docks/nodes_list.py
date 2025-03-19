from csv import list_dialects
from qtpy.QtWidgets import QDockWidget, QTabWidget, QWidget, QVBoxLayout, QSizePolicy
from trigger_designer.qt.widgets.node_drag_listbox import QTRDragListbox
from qtpy.QtCore import QSize, Qt


class NodesDock(QDockWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()
        self.setFeatures(QDockWidget.NoDockWidgetFeatures)
        self.setTitleBarWidget(QWidget())
        self.setFloating(False)
        self.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable |
                         QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        # self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

    def initUI(self):
        # Create the tab widget
        tab_widget = QTabWidget()
        tab_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # Create the tabs
        tab_calc = QWidget()
        tab_input = QWidget()
        tab_preparation = QWidget()
        tab_join = QWidget()
        tab_transform = QWidget()

        # Create the drag list boxes
        calcListWidget = QTRDragListbox(node_type="CALC")
        inputListWidget = QTRDragListbox(node_type="INPUT")
        preparationListWidget = QTRDragListbox(node_type="PREPARATION")
        joinListWidget = QTRDragListbox(node_type="JOIN")
        transformListWidget = QTRDragListbox(node_type="TRANSFORM")

        tabs = [tab_calc, tab_input, tab_preparation, tab_join, tab_transform]
        drag_list_boxes = [calcListWidget, inputListWidget,
                           preparationListWidget, joinListWidget, transformListWidget]

        for item in zip(tabs, drag_list_boxes):
            item[-1].setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            tab_layout = QVBoxLayout()
            tab_layout.addWidget(item[-1])
            item[0].setLayout(tab_layout)

        # Add tabs to the tab widget
        tab_widget.addTab(tab_calc, "Calc")
        tab_widget.addTab(tab_input, "Input")
        tab_widget.addTab(tab_preparation, "Preparation")
        tab_widget.addTab(tab_join, "Join")
        tab_widget.addTab(tab_transform, "Transform")

        # nodesListWidget = QTRDragListbox(node_type="lol node tyupe")
        # tab_widget.adjustSize()
        # tab_widget.adjustSize()
        self.setWidget(tab_widget)
        tab_widget.setMaximumHeight(105)
        self.adjustSize()
