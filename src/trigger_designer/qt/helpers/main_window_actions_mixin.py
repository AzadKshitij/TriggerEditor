from __future__ import annotations

import sys

from loguru import logger as glogger
from qtpy.QtCore import QProcess, QUrl
from qtpy.QtGui import QDesktopServices, QKeySequence
from qtpy.QtWidgets import QAction, QDialog, QMessageBox

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

        self.actOptionalModules = QAction(
            "Optional modules…",
            self,
            statusTip=(
                "Add or remove optional capability modules (the only feature that "
                "connects to the internet, and only when you choose Install)"
            ),
            triggered=self.showOptionalModules,
        )
        self.actOptionalModules.setObjectName("actionOptionalModules")

        from trigger_designer.core import file_association

        self.actNewWindow = QAction(
            "New &Window",
            self,
            shortcut="Ctrl+Shift+N",
            statusTip="Open a second, separate Trigger Designer window",
            triggered=self.showNewWindow,
        )
        self.actNewWindow.setObjectName("actionNewWindow")

        self.actAssociateFiles = QAction(
            "Open .tds files with Trigger Designer…",
            self,
            statusTip=(
                "Make double-clicking a .tds workflow file open it here "
                "(Windows, for your user only; no administrator rights needed)"
            ),
            triggered=self.associateTdsFiles,
        )
        self.actAssociateFiles.setObjectName("actionAssociateTdsFiles")
        self.actAssociateFiles.setEnabled(file_association.is_supported())

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

    def showNewWindow(self) -> None:
        """File > New Window: start a second, separate copy of the editor."""
        program, args = sys.executable, []
        if not getattr(sys, "frozen", False):
            args = ["-m", "trigger_designer.main"]
        if not QProcess.startDetached(program, args):
            self.statusBar().showMessage("A new window could not be started.", 8000)

    def associateTdsFiles(self) -> None:
        """Help > Open .tds files with Trigger Designer: register the file type."""
        from trigger_designer.core import file_association

        try:
            result = file_association.register()
        except Exception as exc:  # noqa: BLE001 - tell the user, never crash a slot
            glogger.exception("Could not register .tds files")
            QMessageBox.warning(
                self,
                "Open .tds files",
                f"Trigger Designer could not register .tds files:\n\n{exc}",
            )
            return
        if result.is_default:
            QMessageBox.information(
                self,
                "Open .tds files",
                "Done. Double-clicking a .tds file now opens it in Trigger Designer.",
            )
            return
        other = result.owner or "another program"
        QMessageBox.information(
            self,
            "Open .tds files",
            "Trigger Designer is now offered for .tds files, but Windows is set to "
            f"open them with {other}.\n\nChoose Trigger Designer once, in Windows "
            "Settings > Default apps (it opens next), or right-click a .tds file > "
            "Open with > Choose another app > Always.",
        )
        QDesktopServices.openUrl(QUrl("ms-settings:defaultapps"))

    def showOptionalModules(self) -> None:
        """Help > Optional modules: install, verify or remove optional modules."""
        from trigger_designer.qt.dialogs.modules_dialog import ModulesDialog

        dialog = ModulesDialog(self)
        try:
            dialog.exec()
        finally:
            dialog.deleteLater()

    def loadSettings(self) -> None:
        glogger.debug("Loading settings...")
        apply_node_editor_colors(load_node_editor_colors())
        refresh_open_scenes(self)
        self.refreshShortcuts()
        # One signal covers canvas, node rings, tables, logs and preview.
        apply_appearance = getattr(self, "apply_appearance", None)
        if callable(apply_appearance):
            apply_appearance()
