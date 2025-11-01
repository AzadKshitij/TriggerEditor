"""Mixin for group-related menu items and actions"""
from typing import Optional, cast, TYPE_CHECKING
from qtpy.QtWidgets import QMenu, QWidget, QAction, QMainWindow, QMenuBar
from qtpy.QtCore import Qt
from qtpy.QtGui import QKeySequence

if TYPE_CHECKING:
    from trigger_designer.qt.widgets.scene import TriggerScene

# Do not import TriggerSubWindow at the top to avoid circular import
from nodeeditor.utils_no_qt import dumpException

class GroupActionsMixin:
    """Mixin providing group-related menu items and actions"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Initialize menu and actions
        self.group_menu = None
        self.create_group_action = None
        self.ungroup_action = None
        self.collapse_group_action = None
        self.expand_group_action = None

    def createGroupActions(self) -> None:
        """Create group-related actions"""
        # Group nodes
        self.create_group_action = QAction('&Group Nodes', self)
        if self.create_group_action:
            self.create_group_action.setShortcut(QKeySequence("Ctrl+G"))
            self.create_group_action.setStatusTip('Group selected nodes')
            self.create_group_action.triggered.connect(self.onGroupNodes)

        # Ungroup nodes
        self.ungroup_action = QAction('&Ungroup Nodes', self)
        if self.ungroup_action:
            self.ungroup_action.setShortcut(QKeySequence("Ctrl+Shift+G"))
            self.ungroup_action.setStatusTip('Ungroup selected group')
            self.ungroup_action.triggered.connect(self.onUngroupNodes)

        # Collapse group
        self.collapse_group_action = QAction('&Collapse Group', self)
        if self.collapse_group_action:
            self.collapse_group_action.setShortcut(QKeySequence("Ctrl+H"))
            self.collapse_group_action.setStatusTip('Collapse selected group')
            self.collapse_group_action.triggered.connect(self.onCollapseGroup)

        # Expand group
        self.expand_group_action = QAction('&Expand Group', self)
        if self.expand_group_action:
            self.expand_group_action.setShortcut(QKeySequence("Ctrl+Shift+H"))
            self.expand_group_action.setStatusTip('Expand selected group')
            self.expand_group_action.triggered.connect(self.onExpandGroup)

        # Update enabled state
        self.updateGroupActions()

    def createGroupMenu(self) -> None:
        """Create the Group menu"""
        if isinstance(self, QMainWindow):
            menubar = cast(QMenuBar, self.menuBar())
            self.group_menu = menubar.addMenu("&Group")
            if self.group_menu:
                self.group_menu.aboutToShow.connect(self.updateGroupActions)
                if self.create_group_action:
                    self.group_menu.addAction(self.create_group_action)
                if self.ungroup_action:
                    self.group_menu.addAction(self.ungroup_action)
                self.group_menu.addSeparator()
                if self.collapse_group_action:
                    self.group_menu.addAction(self.collapse_group_action)
                if self.expand_group_action:
                    self.group_menu.addAction(self.expand_group_action)

    def updateGroupActions(self) -> None:
        """Update enabled state of group actions based on selection"""
        from trigger_designer.qt.main_window import TriggerWindow
        try:
            active = cast(TriggerWindow, self).getCurrentNodeEditorWidget()
            if active is None:
                # Disable all actions if no active window
                for action in [
                    self.create_group_action,
                    self.ungroup_action,
                    self.collapse_group_action,
                    self.expand_group_action
                ]:
                    if action is not None:
                        action.setEnabled(False)
                return

            scene = cast('TriggerScene', active.scene)
            # Get selected items
            selected = scene.getSelectedItems()

            # Enable group action if 2+ nodes selected
            nodes = [item for item in selected if hasattr(item, 'node')]
            if self.create_group_action is not None:
                self.create_group_action.setEnabled(len(nodes) >= 2)

            # Enable group-related actions if a group is selected
            groups = [item for item in selected if hasattr(item, 'nodes')]
            has_group = len(groups) > 0

            # Update group-related actions
            for action in [self.ungroup_action, self.collapse_group_action, self.expand_group_action]:
                if action is not None:
                    action.setEnabled(has_group)

        except Exception as e:
            dumpException(e)

    def onGroupNodes(self) -> None:
        """Handle grouping selected nodes"""
        try:
            from trigger_designer.qt.main_window import TriggerWindow
            active = cast(TriggerWindow, self).getCurrentNodeEditorWidget()
            if active:
                scene = cast('TriggerScene', active.scene)
                scene.create_group()

        except Exception as e:
            dumpException(e)

    def onUngroupNodes(self) -> None:
        """Handle ungrouping selected group"""
        try:
            from trigger_designer.qt.main_window import TriggerWindow
            active = cast(TriggerWindow, self).getCurrentNodeEditorWidget()
            if active:
                scene = cast('TriggerScene', active.scene)
                scene.ungroup_selected()

        except Exception as e:
            dumpException(e)

    def onCollapseGroup(self) -> None:
        """Handle collapsing selected group"""
        try:
            from trigger_designer.qt.main_window import TriggerWindow
            active = cast(TriggerWindow, self).getCurrentNodeEditorWidget()
            if not active:
                return

            scene = cast('TriggerScene', active.scene)
            # Get selected group(s)
            groups = [
                item for item in scene.getSelectedItems()
                if hasattr(item, 'nodes')
            ]
            for group in groups:
                scene.collapse_group(group)

        except Exception as e:
            dumpException(e)

    def onExpandGroup(self) -> None:
        """Handle expanding selected group"""
        try:
            from trigger_designer.qt.main_window import TriggerWindow
            active = cast(TriggerWindow, self).getCurrentNodeEditorWidget()
            if not active:
                return

            scene = cast('TriggerScene', active.scene)
            # Get selected group(s)
            groups = [
                item for item in scene.getSelectedItems()
                if hasattr(item, 'nodes')
            ]
            for group in groups:
                scene.expand_group(group)

        except Exception as e:
            dumpException(e)