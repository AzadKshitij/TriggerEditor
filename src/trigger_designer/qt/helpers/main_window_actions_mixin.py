from __future__ import annotations

from loguru import logger as glogger
from qtpy.QtGui import QKeySequence
from qtpy.QtWidgets import QAction, QDialog

from trigger_designer.qt.models.settings_panel import SettingsDialog
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

    def showSettings(self) -> None:
        dialog = SettingsDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.loadSettings()

    def loadSettings(self) -> None:
        glogger.debug("Loading settings...")
        apply_node_editor_colors(load_node_editor_colors())
        refresh_open_scenes(self)
