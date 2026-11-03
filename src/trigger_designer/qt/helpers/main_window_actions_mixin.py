from __future__ import annotations

from loguru import logger as glogger
from qtpy.QtGui import QKeySequence
from qtpy.QtWidgets import QAction, QDialog

from trigger_designer.qt.dialogs.preferences_dialog import PreferencesDialog
from trigger_designer.qt.helpers import node_arrange
from trigger_designer.qt.helpers.shortcuts import apply_to_window
from trigger_designer.qt.node_editor_colors import (
    apply_node_editor_colors,
    load_node_editor_colors,
    refresh_open_scenes,
)


class MainWindowActionsMixin:
    """Mixin encapsulating action creation and settings management."""

    def createActions(self) -> None:
        super().createActions()

        self.actSettings = QAction(
            "Settings",
            self,
            statusTip="Open settings dialog",
            triggered=self.showSettings,
        )

        self.actExportWorkpaper = QAction(
            "Export &Workpaper...",
            self,
            statusTip="Write an Excel workpaper of the last recorded run",
            triggered=self.exportWorkpaper,
        )

        self.actSaveLayout = QAction(
            "&Save Current Layout",
            self,
            statusTip="Persist the current window and dock arrangement",
            triggered=self.saveCurrentLayout,
        )

        self.actResetLayout = QAction(
            "&Reset Layout",
            self,
            statusTip="Restore the default window and dock arrangement",
            triggered=self.resetLayout,
        )

        self.actClose = QAction(
            "Cl&ose",
            self,
            statusTip="Close the active window",
            triggered=self.mdiArea.closeActiveSubWindow,
        )
        self.actCloseAll = QAction(
            "Close &All",
            self,
            statusTip="Close all the windows",
            triggered=self.mdiArea.closeAllSubWindows,
        )
        self.actTile = QAction(
            "&Tile",
            self,
            statusTip="Tile the windows",
            triggered=self.mdiArea.tileSubWindows,
        )
        self.actCascade = QAction(
            "&Cascade",
            self,
            statusTip="Cascade the windows",
            triggered=self.mdiArea.cascadeSubWindows,
        )
        self.actNext = QAction(
            "Ne&xt",
            self,
            shortcut=QKeySequence.StandardKey.NextChild,
            statusTip="Move the focus to the next window",
            triggered=self.mdiArea.activateNextSubWindow,
        )
        self.actPrevious = QAction(
            "Pre&vious",
            self,
            shortcut=QKeySequence.StandardKey.PreviousChild,
            statusTip="Move the focus to the previous window",
            triggered=self.mdiArea.activatePreviousSubWindow,
        )

        self.actSeparator = QAction(self)
        self.actSeparator.setSeparator(True)

        self.actAbout = QAction(
            "&About",
            self,
            statusTip="Show the application's About box",
            triggered=self.about,
        )

        self.createArrangeActions()

    def exportWorkpaper(self) -> None:
        """File > Export Workpaper...: summary, run log and workflow of the last run."""
        from trigger_designer.qt.helpers.workpaper_export import export_workpaper

        export_workpaper(self)

    def createArrangeActions(self) -> None:
        """Build the Arrange menu's actions, one per arrangement command.

        They live on the main window so the Edit menu, the shortcuts and the
        node context menu (which runs the same helpers) cannot drift apart.
        """
        for command in node_arrange.COMMANDS:
            action = QAction(
                command.label,
                self,
                statusTip=f"{command.label} the selected nodes",
            )
            action.triggered.connect(
                lambda _checked=False, command_id=command.id: self.arrangeSelection(
                    command_id
                )
            )
            setattr(self, command.action, action)

        self.actToggleSnap = QAction("Snap to Grid", self)
        self.actToggleSnap.setCheckable(True)
        self.actToggleSnap.setStatusTip("Snap nodes to the canvas grid while dragging")
        self.actToggleSnap.triggered.connect(self.onToggleSnap)

        apply_to_window(self)

    def arrangeSelection(self, command_id: str) -> None:
        """Run one Arrange command on the active canvas."""
        active = self.getCurrentNodeEditorWidget()
        scene = getattr(active, "scene", None) if active is not None else None
        if scene is None:
            return
        if not node_arrange.apply_command(scene, command_id):
            return
        command = node_arrange.COMMAND_BY_ID.get(command_id)
        if command is not None and self.statusBar() is not None:
            self.statusBar().showMessage(command.label, 2000)
        self.updateEditMenu()

    def onToggleSnap(self, checked: bool) -> None:
        active = self.getCurrentNodeEditorWidget()
        scene = getattr(active, "scene", None) if active is not None else None
        if scene is None:
            return
        node_arrange.set_snap_enabled(scene, bool(checked))

    def syncSnapAction(self) -> None:
        """Show the preference's real value on the checkable menu item."""
        if getattr(self, "actToggleSnap", None) is None:
            return
        active = self.getCurrentNodeEditorWidget()
        scene = getattr(active, "scene", None) if active is not None else None
        if scene is not None:
            self.actToggleSnap.setChecked(node_arrange.snap_enabled(scene))

    def refreshShortcuts(self) -> None:
        """Re-read the shortcut map after the preferences dialog closes."""
        apply_to_window(self)

    def showSettings(self) -> None:
        dialog = PreferencesDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.loadSettings()

    def loadSettings(self) -> None:
        glogger.debug("Loading settings...")
        apply_node_editor_colors(load_node_editor_colors())
        refresh_open_scenes(self)
        self.refreshShortcuts()
        # One signal covers canvas, node rings, tables, logs and preview.
        apply_appearance = getattr(self, "apply_appearance", None)
        if callable(apply_appearance):
            apply_appearance()
