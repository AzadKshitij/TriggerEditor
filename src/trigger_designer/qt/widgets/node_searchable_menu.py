# Add these imports at the top of the file
from typing import Optional
from qtpy.QtWidgets import QLineEdit, QWidget, QVBoxLayout, QMenu, QWidgetAction
from qtpy.QtCore import Qt, Signal, QTimer
from qtpy.QtGui import QCursor, QHideEvent

from trigger_designer.core.node_configuration import get_class_from_opcode


class SearchableMenu(QMenu):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        # Create main container
        self.searchWidget = QWidget(self)
        self.searchLayout = QVBoxLayout(self.searchWidget)
        self.searchLayout.setContentsMargins(1, 1, 1, 1)

        # Create the search box
        self.searchBox = ClickableLineEdit(self.searchWidget)
        self.searchBox.setPlaceholderText("Search nodes...")
        self.searchBox.setEnabled(True)  # Ensure search box is enabled
        self.searchBox.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Add debouncing for search
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self._filter_nodes)
        self.searchBox.textChanged.connect(self._on_text_changed)
        self.searchBox.clicked.connect(self.showFlatList)
        self.searchLayout.addWidget(self.searchBox)

        # Add the search widget as a custom widget in the menu
        self.searchAction = QWidgetAction(self)
        self.searchAction.setDefaultWidget(self.searchWidget)
        self.addAction(self.searchAction)

        # Store all menu items for filtering
        self.all_actions: dict = {}
        self.all_submenus: dict = {}
        self.is_flat_view: bool = False
        self.visible_range = (0, 10)  # Show 10 items at a time
        self.filtered_actions: list = []  # Cache for filtered actions

        self.setFixedWidth(300)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground)

        # Ensure the widget and its children can receive focus and mouse events
        self.searchWidget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocusProxy(self.searchBox)

        self._connected_actions = set()

    def _on_text_changed(self, text: str) -> None:
        # Debounce search to avoid frequent updates
        self.search_timer.start(150)

    def _filter_nodes(self) -> None:
        if not self.is_flat_view:
            return

        search_text = self.searchBox.text().lower()
        self.filtered_actions = [
            a for a in self.actions()[1:] if search_text in a.text().lower()
        ]
        self.visible_range = (0, 10)
        self.updateVisibleActions()

    def scrollUp(self) -> None:
        print("Scroll up")
        if not self.is_flat_view:
            return
        start, end = self.visible_range
        if start > 0:
            self.visible_range = (start - 1, end - 1)
            self.updateVisibleActions()

    def scrollDown(self) -> None:
        print("Scroll down")
        print(
            "🐍 File: widgets/node_searchable_menu.py | Line: 70 | scrollDown ~ self.is_flat_view",
            self.is_flat_view,
        )
        if not self.is_flat_view:
            return

        filtered_actions = [
            a
            for a in self.actions()[1:]
            if self.searchBox.text().lower() in a.text().lower()
        ]
        start, end = self.visible_range
        print(
            "🐍 File: widgets/node_searchable_menu.py | Line: 74 | scrollDown ~ start, end",
            start,
            end,
        )
        if end < len(filtered_actions):
            self.visible_range = (start + 1, end + 1)
            self.updateVisibleActions()

    def updateVisibleActions(self) -> None:
        start, end = self.visible_range
        visible_range = self.filtered_actions[start:end]
        visible_set = set(visible_range)

        # Batch visibility updates
        updates = [(action, action in visible_set) for action in self.actions()[1:]]

        # Apply updates only where needed
        for action, should_be_visible in updates:
            if action.isVisible() != should_be_visible:
                action.setVisible(should_be_visible)

        # Update focus if needed
        if visible_range and (
            not self.activeAction() or self.activeAction() not in visible_set
        ):
            self.setActiveAction(visible_range[0])

    def showFlatList(self) -> None:
        if self.is_flat_view:
            return

        # Clear search and reset state
        self.searchBox.clear()
        self.visible_range = (0, 10)
        self.filtered_actions = []

        # Disconnect and clear all existing actions
        for action in self.actions()[1:]:
            if action in self._connected_actions:
                try:
                    action.triggered.disconnect(self.on_action_triggered)
                except TypeError:
                    pass
            self.removeAction(action)
        self._connected_actions.clear()

        # Add all actions at once
        all_actions = []
        for category_actions in self.all_actions.values():
            all_actions.extend(category_actions)

        all_actions.sort(key=lambda x: x.text())
        for action in all_actions:
            if action not in self._connected_actions:
                action.triggered.connect(self.on_action_triggered)
                self._connected_actions.add(action)
            self.addAction(action)

        self.is_flat_view = True
        self.filtered_actions = all_actions
        self.updateVisibleActions()
        self.searchBox.setFocus()

    def on_action_triggered(self) -> None:
        parent = self.parent()
        action = self.sender()
        if action and action in self._connected_actions:
            parent.set_selected_action_data(action.data())
            parent.add_node_to_scene()
            self.hide()

    def filterNodes(self, text: str) -> None:
        if not self.is_flat_view:
            return

        search_text = text.lower()

        # Show/hide actions based on search
        for action in self.actions()[1:]:
            action.setVisible(search_text in action.text().lower())

        # Reset visible range and update visibility
        self.visible_range = (0, 10)
        self.updateVisibleActions()

    def hideEvent(self, event: QHideEvent) -> None:
        # Disconnect all actions when hiding
        for action in self._connected_actions:
            try:
                action.triggered.disconnect(self.on_action_triggered)
            except TypeError:
                pass
        self._connected_actions.clear()

        self.searchBox.clear()  # Clear search text
        self.is_flat_view = False
        self.visible_range = (0, 10)  # Reset visible range
        self.filtered_actions = []  # Clear filtered actions cache
        super().hideEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            print("Enter key pressed")
            active_action = self.activeAction()
            if active_action:
                print("Active action:", active_action.text())
                active_action.trigger()
                # self.close()
                self.hide()
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(event)

    def wheelEvent(self, event) -> None:
        if not self.is_flat_view:
            return

        delta = event.angleDelta().y()
        start, end = self.visible_range

        if delta < 0 and end < len(self.filtered_actions):  # Scroll down
            self.visible_range = (start + 1, end + 1)
            self.updateVisibleActions()
        elif delta > 0 and start > 0:  # Scroll up
            self.visible_range = (start - 1, end - 1)
            self.updateVisibleActions()

        event.accept()


class ClickableLineEdit(QLineEdit):
    clicked = Signal()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)
