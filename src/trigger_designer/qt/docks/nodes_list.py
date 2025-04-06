from csv import list_dialects
from qtpy.QtWidgets import QDockWidget, QTabWidget, QWidget, QVBoxLayout, QSizePolicy
from trigger_designer.core.node_configuration import NodeTypes
from trigger_designer.qt.widgets.node_drag_listbox import QTRDragListbox
from qtpy.QtCore import QSize, Qt
from typing import Optional


class NodesDock(QDockWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.initUI()
        self.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        self.setTitleBarWidget(QWidget())
        self.setFloating(False)
        self.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable |
                         QDockWidget.DockWidgetFeature.DockWidgetFloatable)
        # self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.setSizePolicy(QSizePolicy.Policy.Preferred,
                           QSizePolicy.Policy.Fixed)

    def initUI(self) -> None:
        # Create the tab widget
        tab_widget = QTabWidget()
        tab_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        # Create the tabs and drag list boxes dynamically
        tabs = {}
        drag_list_boxes = {}

        # Iterate through the NodeTypes enum
        for node_type in NodeTypes:
            tab = QWidget()
            list_widget = QTRDragListbox(node_type=node_type)
            list_widget.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            tab_layout = QVBoxLayout()
            tab_layout.addWidget(list_widget)
            tab.setLayout(tab_layout)

            tabs[node_type] = tab
            drag_list_boxes[node_type] = list_widget

            # Use the enum member name as the tab name (you might want to customize this)
            tab_widget.addTab(tab, node_type.value.title())

        self.setWidget(tab_widget)
        tab_widget.setMaximumHeight(105)
        self.adjustSize()
