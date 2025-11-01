"""Mixin for group-related menu items and actions"""
from typing import Optional, cast
from qtpy.QtWidgets import QMenu, QWidget, QAction
from qtpy.QtCore import Qt
from qtpy.QtGui import QKeySequence

from trigger_designer.qt.design_window import TriggerSubWindow
from nodeeditor.utils_no_qt import dumpException

class GroupActionsMixin:
    """Mixin providing group-related menu items and actions"""

    def __init__(self) -> None:
        self.group_menu: Optional[QMenu] = None
        self.create_group_action: Optional[QAction] = None
        self.ungroup_action: Optional[QAction] = None
        self.collapse_group_action: Optional[QAction] = None
        self.expand_group_action: Optional[QAction] = None

    def createGroupActions(self) -> None:
        """Create group-related actions"""
        # Group nodes
        self.create_group_action = QAction('&Group Nodes', self)
        self.create_group_action.setShortcut(QKeySequence("Ctrl+G"))
        self.create_group_action.setStatusTip('Group selected nodes')
        self.create_group_action.triggered.connect(self.onGroupNodes)

        # Ungroup nodes
        self.ungroup_action = QAction('&Ungroup Nodes', self)
        self.ungroup_action.setShortcut(QKeySequence("Ctrl+Shift+G"))
        self.ungroup_action.setStatusTip('Ungroup selected group')
        self.ungroup_action.triggered.connect(self.onUngroupNodes)

        # Collapse group
        self.collapse_group_action = QAction('&Collapse Group', self)
        self.collapse_group_action.setShortcut(QKeySequence("Ctrl+H"))
        self.collapse_group_action.setStatusTip('Collapse selected group')
        self.collapse_group_action.triggered.connect(self.onCollapseGroup)

        # Expand group
        self.expand_group_action = QAction('&Expand Group', self)
        self.expand_group_action.setShortcut(QKeySequence("Ctrl+Shift+H"))
        self.expand_group_action.setStatusTip('Expand selected group')
        self.expand_group_action.triggered.connect(self.onExpandGroup)

        # Update enabled state
        self.updateGroupActions()

    def createGroupMenu(self) -> None:
        """Create the Group menu"""
        self.group_menu = cast(QWidget, self).menuBar().addMenu("&Group")
        self.group_menu.aboutToShow.connect(self.updateGroupActions)

        self.group_menu.addAction(self.create_group_action)
        self.group_menu.addAction(self.ungroup_action)
        self.group_menu.addSeparator()
        self.group_menu.addAction(self.collapse_group_action)
        self.group_menu.addAction(self.expand_group_action)

    def updateGroupActions(self) -> None:
        """Update enabled state of group actions based on selection"""
        try:
            active = cast(QWidget, self).getCurrentNodeEditorWidget()
            if active is None:
                self.create_group_action.setEnabled(False)
                self.ungroup_action.setEnabled(False)
                self.collapse_group_action.setEnabled(False)
                self.expand_group_action.setEnabled(False)
                return

            # Get selected items
            selected = active.scene.getSelectedItems()

            # Enable group action if 2+ nodes selected
            nodes = [item for item in selected if hasattr(item, 'node')]
            self.create_group_action.setEnabled(len(nodes) >= 2)

            # Enable group-related actions if a group is selected
            groups = [item for item in selected if hasattr(item, 'nodes')]
            has_group = len(groups) > 0

            self.ungroup_action.setEnabled(has_group)
            self.collapse_group_action.setEnabled(has_group)
            self.expand_group_action.setEnabled(has_group)

        except Exception as e:
            dumpException(e)

    def onGroupNodes(self) -> None:
        """Handle grouping selected nodes"""
        try:
            active = cast(QWidget, self).getCurrentNodeEditorWidget()
            if active:
                active.scene.create_group()

        except Exception as e:
            dumpException(e)

    def onUngroupNodes(self) -> None:
        """Handle ungrouping selected group"""
        try:
            active = cast(QWidget, self).getCurrentNodeEditorWidget()
            if active:
                active.scene.ungroup_selected()

        except Exception as e:
            dumpException(e)

    def onCollapseGroup(self) -> None:
        """Handle collapsing selected group"""
        try:
            active = cast(QWidget, self).getCurrentNodeEditorWidget()
            if not active:
                return

            # Get selected group(s)
            groups = [
                item for item in active.scene.getSelectedItems()
                if hasattr(item, 'nodes')
            ]
            for group in groups:
                active.scene.collapse_group(group)

        except Exception as e:
            dumpException(e)

    def onExpandGroup(self) -> None:
        """Handle expanding selected group"""
        try:
            active = cast(QWidget, self).getCurrentNodeEditorWidget()
            if not active:
                return

            # Get selected group(s)
            groups = [
                item for item in active.scene.getSelectedItems()
                if hasattr(item, 'nodes')
            ]
            for group in groups:
                active.scene.expand_group(group)

        except Exception as e:
            dumpException(e)