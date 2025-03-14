from qtpy.QtWidgets import QApplication, QMainWindow, QMenu, QAction, QScrollArea, QVBoxLayout, QWidget, QPushButton, QWidgetAction
from qtpy.QtCore import Qt


class ScrollableMenu(QMenu):
    def __init__(self, parent=None, max_visible_items=10):
        super().__init__(parent)
        self.max_visible_items = max_visible_items
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.container = QWidget()
        self.layout = QVBoxLayout(self.container)
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area.setWidget(self.container)

    def add_scrollable_action(self, action):
        button = QPushButton(action.text())
        button.clicked.connect(action.trigger)  # Connect action click
        self.layout.addWidget(button)

    def exec_(self, pos):
        # Adjust height based on number of items
        total_items = self.layout.count()
        item_height = 30  # Approximate height per item
        max_height = self.max_visible_items * item_height

        self.scroll_area.setFixedHeight(
            min(max_height, total_items * item_height))
        self.scroll_area.setMinimumWidth(150)

        # Wrap QScrollArea inside the menu
        self.clear()
        action_widget = QWidgetAction(self)
        action_widget.setDefaultWidget(self.scroll_area)
        self.addAction(action_widget)

        super().exec_(pos)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Scrollable Context Menu in QtPy")
        self.setGeometry(100, 100, 400, 300)

        self.button = QPushButton("Right-click me!", self)
        self.button.setGeometry(100, 100, 200, 50)
        self.button.setContextMenuPolicy(Qt.CustomContextMenu)
        self.button.customContextMenuRequested.connect(self.show_context_menu)

    def show_context_menu(self, pos):
        context_menu = ScrollableMenu(self)

        # Add many actions to test scrolling
        for i in range(20):
            action = QAction(f"Option {i+1}", self)
            context_menu.add_scrollable_action(action)

        context_menu.exec_(self.mapToGlobal(pos))


if __name__ == "__main__":
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec_()
