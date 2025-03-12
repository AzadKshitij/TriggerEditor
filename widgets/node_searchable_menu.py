# Add these imports at the top of the file
from qtpy.QtWidgets import QLineEdit, QWidget, QVBoxLayout, QMenu, QWidgetAction
from qtpy.QtCore import Qt, Signal
from qtpy.QtGui import QCursor


class SearchableMenu(QMenu):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Create a widget to hold the search box
        self.searchWidget = QWidget(self)
        self.searchLayout = QVBoxLayout(self.searchWidget)
        self.searchLayout.setContentsMargins(5, 5, 5, 5)

        # Create the search box
        self.searchBox = ClickableLineEdit(self.searchWidget)
        self.searchBox.setPlaceholderText("Search nodes...")
        self.searchBox.textChanged.connect(self.filterNodes)
        self.searchBox.clicked.connect(self.showFlatList)

        self.searchLayout.addWidget(self.searchBox)

        # Add the search widget as a custom widget in the menu
        self.searchAction = QWidgetAction(self)
        self.searchAction.setDefaultWidget(self.searchWidget)
        self.addAction(self.searchAction)

        # Store all menu items for filtering
        self.all_actions = {}
        self.all_submenus = {}  # Add this line
        self.is_flat_view = False

    def showFlatList(self):
        if self.is_flat_view:
            return

        # Clear all existing actions except search box
        for action in self.actions()[1:]:
            self.removeAction(action)

        # Add all actions in a flat list
        all_actions = []
        for category_actions in self.all_actions.values():
            all_actions.extend(category_actions)

        # Sort actions by their text and add to menu
        all_actions.sort(key=lambda x: x.text())
        for action in all_actions:
            self.addAction(action)

        self.is_flat_view = True
        self.searchBox.setFocus()

    def filterNodes(self, text):
        if not self.is_flat_view:
            return

        # Convert search text to lowercase for case-insensitive search
        search_text = text.lower()

        # Skip first action (search box) when filtering
        for action in self.actions()[1:]:
            action.setVisible(search_text in action.text().lower())

    def hideEvent(self, event):
        self.searchBox.clear()
        self.is_flat_view = False
        super().hideEvent(event)


class ClickableLineEdit(QLineEdit):
    clicked = Signal()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)
