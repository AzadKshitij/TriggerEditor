from qtpy.QtWidgets import QDockWidget, QTabWidget, QWidget, QVBoxLayout, QSizePolicy
from widgets.node_drag_listbox import QTRDragListbox
from qtpy.QtCore import QSize, Qt


class NodesDock(QDockWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.initUI()
        self.setFeatures(QDockWidget.NoDockWidgetFeatures)
        self.setTitleBarWidget(QWidget())

    def initUI(self):
        # Create the tab widget
        tab_widget = QTabWidget()
        # tab_widget.setFixedHeight(180)
        # print("tab_widget.childrenRect().size():",
        #       tab_widget.childrenRect().size())
        tab_widget.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Fixed
        )

        # Create the tabs
        tab_input = QWidget()
        tab_preparation = QWidget()
        tab_join = QWidget()

        # Create the drag list boxes
        inputListWidget = QTRDragListbox(node_type="INPUT")
        print("inputListWidget.childrenRect().size():",
              inputListWidget.childrenRect().size())
        preparationListWidget = QTRDragListbox(node_type="PREPARATION")
        joinListWidget = QTRDragListbox(node_type="CALC")

        # set size policies for the tab widgets
        tab_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        tab_preparation.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        tab_join.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # Set size policies for the list widgets
        inputListWidget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        # inputListWidget.setFixedHeight(100)
        preparationListWidget.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Fixed)
        joinListWidget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # Set layouts for each tab
        tab_input_layout = QVBoxLayout()
        tab_input_layout.addWidget(inputListWidget)
        tab_input.setLayout(tab_input_layout)

        tab_preparation_layout = QVBoxLayout()
        tab_preparation_layout.addWidget(preparationListWidget)
        tab_preparation.setLayout(tab_preparation_layout)

        tab_join_layout = QVBoxLayout()
        tab_join_layout.addWidget(joinListWidget)
        tab_join.setLayout(tab_join_layout)

        # Add tabs to the tab widget
        tab_widget.addTab(tab_input, "Input")
        tab_widget.addTab(tab_preparation, "Preparation")
        tab_widget.addTab(tab_join, "Join")

        # nodesListWidget = QTRDragListbox(node_type="lol node tyupe")
        # tab_widget.adjustSize()
        tab_widget.adjustSize()
        self.setWidget(tab_widget)
        self.setFloating(False)
        self.setFeatures(QDockWidget.DockWidgetMovable |
                         QDockWidget.DockWidgetFloatable)
        # self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        current_wid = tab_widget.currentWidget()
        tab_widget.setMaximumHeight(160)
        self.adjustSize()
