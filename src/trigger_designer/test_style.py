from qtpy.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                            QTabWidget, QDockWidget, QLabel, QPushButton,
                            QLineEdit, QTextEdit, QComboBox, QSpinBox,
                            QCheckBox, QRadioButton, QProgressBar, QSlider,
                            QScrollBar, QListWidget, QTreeWidget, QTreeWidgetItem,
                            QTableWidget, QTableWidgetItem, QMenuBar, QStatusBar,
                            QToolBar, QGroupBox, QSplitter)
from qtpy.QtCore import Qt


class StyleTestWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Style Test Window")
        self.resize(1200, 800)

        # Create menu bar
        self.create_menu_bar()

        # Create tool bar
        self.create_tool_bar()

        # Create central widget with tabs
        self.create_central_widget()

        # Create dock widgets
        self.create_dock_widgets()

        # Create status bar
        self.statusBar().showMessage("Status Bar Message")

    def create_menu_bar(self) -> None:
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")
        file_menu.addAction("New")
        file_menu.addAction("Open")
        file_menu.addAction("Save")

        edit_menu = menubar.addMenu("Edit")
        edit_menu.addAction("Cut")
        edit_menu.addAction("Copy")
        edit_menu.addAction("Paste")

    def create_tool_bar(self) -> None:
        toolbar = QToolBar()
        self.addToolBar(toolbar)
        toolbar.addAction("Tool 1")
        toolbar.addAction("Tool 2")
        toolbar.addSeparator()
        toolbar.addAction("Tool 3")

    def create_central_widget(self) -> None:
        tab_widget = QTabWidget()

        # Input widgets tab
        input_tab = QWidget()
        input_layout = QVBoxLayout(input_tab)

        input_layout.addWidget(QLabel("Text Input:"))
        input_layout.addWidget(QLineEdit("Line Edit"))
        input_layout.addWidget(QTextEdit("Text Edit"))

        combo = QComboBox()
        combo.addItems(["Item 1", "Item 2", "Item 3"])
        input_layout.addWidget(combo)

        input_layout.addWidget(QSpinBox())
        input_layout.addWidget(QCheckBox("Checkbox"))
        input_layout.addWidget(QRadioButton("Radio Button"))

        tab_widget.addTab(input_tab, "Input Widgets")

        # Progress widgets tab
        progress_tab = QWidget()
        progress_layout = QVBoxLayout(progress_tab)

        progress = QProgressBar()
        progress.setValue(75)
        progress_layout.addWidget(progress)

        slider = QSlider(Qt.Horizontal)
        slider.setValue(50)
        progress_layout.addWidget(slider)

        tab_widget.addTab(progress_tab, "Progress Widgets")

        # List and Tree tab
        list_tab = QWidget()
        list_layout = QVBoxLayout(list_tab)

        list_widget = QListWidget()
        list_widget.addItems(["List Item 1", "List Item 2", "List Item 3"])
        list_layout.addWidget(list_widget)

        tree = QTreeWidget()
        tree.setHeaderLabel("Tree Widget")
        item = QTreeWidgetItem(["Parent"])
        item.addChild(QTreeWidgetItem(["Child 1"]))
        item.addChild(QTreeWidgetItem(["Child 2"]))
        tree.addTopLevelItem(item)
        list_layout.addWidget(tree)

        tab_widget.addTab(list_tab, "List and Tree")

        self.setCentralWidget(tab_widget)

    def create_dock_widgets(self) -> None:
        # Left dock
        left_dock = QDockWidget("Left Dock")
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.addWidget(QPushButton("Dock Button 1"))
        left_layout.addWidget(QPushButton("Dock Button 2"))
        left_dock.setWidget(left_widget)
        self.addDockWidget(Qt.LeftDockWidgetArea, left_dock)

        # Right dock
        right_dock = QDockWidget("Right Dock")
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.addWidget(QLabel("Dock Label"))
        right_layout.addWidget(QLineEdit("Dock Line Edit"))
        right_dock.setWidget(right_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, right_dock)
