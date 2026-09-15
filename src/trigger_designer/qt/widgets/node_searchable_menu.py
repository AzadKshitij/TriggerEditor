# Add these imports at the top of the file
from typing import Optional
from qtpy.QtWidgets import QLineEdit, QWidget, QVBoxLayout, QMenu, QWidgetAction
from qtpy.QtCore import Qt, Signal, QTimer
from qtpy.QtGui import QCursor, QHideEvent, QShowEvent

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
        self.searchBox.returnPressed.connect(self._confirm_first_match)
        self.searchLayout.addWidget(self.searchBox)

        # Add the search widget as a custom widget in the menu
        self.searchAction = QWidgetAction(self)
        self.searchAction.setDefaultWidget(self.searchWidget)
        self.addAction(self.searchAction)

        # Store all menu items for filtering
        self.all_actions: dict = {}
        self.all_submenus: dict = {}
        self.is_flat_view: bool = False

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
            self.showFlatList()
            return
        self._apply_filter(self.searchBox.text())

    def _apply_filter(self, text: str) -> None:
        search_text = text.lower()
        for action in self.actions()[1:]:
            action.setVisible(search_text in action.text().lower())

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self.searchBox.setFocus()

    def _confirm_first_match(self) -> None:
        if not self.is_flat_view:
            self.showFlatList()
            return
        for action in self.actions()[1:]:
            if action.isVisible():
                action.trigger()
                break

    def showFlatList(self) -> None:
        if self.is_flat_view:
            return

        # Preserve typed text (may be called from textChanged)
        search_text = self.searchBox.text()

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
        self._apply_filter(search_text)
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
        self._apply_filter(text)

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
        super().hideEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            active_action = self.activeAction()
            if active_action:
                active_action.trigger()
                self.hide()
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(event)


class ClickableLineEdit(QLineEdit):
    clicked = Signal()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)
