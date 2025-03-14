from qtpy.QtWidgets import QApplication, QPushButton, QMainWindow

from qtpy.QtWidgets import (
    QLineEdit, QWidget, QVBoxLayout, QMenu, QWidgetAction,
    QScrollArea, QAction
)
from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QCursor


class SearchableMenu(QMenu):
    def __init__(self, parent=None, max_visible_items: int = 10):
        super().__init__(parent)
        self.max_visible_items = max_visible_items

        # Scrollable Area
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Container for actions
        self.container = QWidget(self)
        self.layout = QVBoxLayout(self.container)
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_area.setWidget(self.container)

        # Search Bar
        self.searchWidget = QWidget(self)
        self.searchLayout = QVBoxLayout(self.searchWidget)
        self.searchLayout.setContentsMargins(5, 5, 5, 5)

        self.searchBox = ClickableLineEdit(self.searchWidget)
        self.searchBox.setPlaceholderText("Search...")
        self.searchBox.textChanged.connect(self.filterNodes)
        self.searchBox.clicked.connect(self.showFlatList)

        self.searchLayout.addWidget(self.searchBox)

        # Add search box and scrollable actions to menu
        self.searchAction = QWidgetAction(self)
        self.searchAction.setDefaultWidget(self.searchWidget)
        self.addAction(self.searchAction)

        self.scrollAction = QWidgetAction(self)
        self.scrollAction.setDefaultWidget(self.scroll_area)
        self.addAction(self.scrollAction)

        # Storage for actions
        self.all_actions = []
        self.is_flat_view = False

        # Set menu appearance
        self.setFixedWidth(300)
        self.setStyleSheet("menu-scrollable: 1;")
        self.setWindowFlags(Qt.Popup)

    def add_searchable_action(self, action: QAction):
        """Add an action to the searchable menu."""
        self.all_actions.append(action)
        self.layout.addWidget(action.parent())  # Ensure action gets displayed

    def showFlatList(self):
        """Display all actions in a flat list inside the scroll area."""
        if self.is_flat_view:
            return

        # Clear layout
        for i in reversed(range(self.layout.count())):
            widget = self.layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        # Add all actions
        for action in sorted(self.all_actions, key=lambda x: x.text()):
            self.layout.addWidget(action.parent())

        self.is_flat_view = True
        self.searchBox.setFocus()
        self.adjust_scroll_height()

    def filterNodes(self, text):
        """Filter visible actions based on search query."""
        search_text = text.lower()
        visible_count = 0

        for action in self.all_actions:
            widget = action.parent()
            if search_text in action.text().lower():
                widget.setVisible(True)
                visible_count += 1
            else:
                widget.setVisible(False)

        self.adjust_scroll_height(visible_count)

    def adjust_scroll_height(self, visible_count=None):
        """Set scroll area height based on visible items."""
        item_height = 30  # Estimated item height
        max_height = self.max_visible_items * item_height
        if visible_count is None:
            visible_count = len(self.all_actions)
        self.scroll_area.setFixedHeight(
            min(max_height, visible_count * item_height))

    def exec_(self, pos):
        """Show the menu at a given position."""
        self.showFlatList()
        super().exec_(pos)

    def hideEvent(self, event):
        """Reset search box and state on close."""
        self.searchBox.clear()
        self.is_flat_view = False
        super().hideEvent(event)


class ClickableLineEdit(QLineEdit):
    """Custom LineEdit that emits a clicked signal when clicked."""
    clicked = Signal()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Scrollable Searchable Context Menu")
        self.setGeometry(100, 100, 400, 300)

        self.button = QPushButton("Right-click me!", self)
        self.button.setGeometry(100, 100, 200, 50)
        self.button.setContextMenuPolicy(Qt.CustomContextMenu)
        self.button.customContextMenuRequested.connect(self.show_context_menu)

    def show_context_menu(self, pos):
        """Show context menu with many actions."""
        menu = SearchableMenu(None)
        menu.setWindowFlags(Qt.Popup)

        # Add 30 actions to test scrolling
        for i in range(30):
            action = QAction(f"Node {i+1}", self)
            action.setData(i)  # Optional: Store node ID
            menu.add_searchable_action(action)

        menu.exec_(self.mapToGlobal(pos))


if __name__ == "__main__":
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec_()
