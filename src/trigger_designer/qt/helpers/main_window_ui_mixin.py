from __future__ import annotations

from qtpy.QtCore import Qt

from nodeeditor.utils import dumpException

from trigger_designer.qt.docks.node_config import ConfigDock
from trigger_designer.qt.docks.nodes_list import NodesDock
from trigger_designer.qt.docks.logging_dock import LoggingDock


class MainWindowMenuMixin:
    """Mixin holding menu creation and update logic for the main window."""

    windowMenu = None
    helpMenu = None

    def createMenus(self) -> None:  # noqa: N802 (Qt naming style)
        super().createMenus()

        self.editMenu.addSeparator()
        self.editMenu.addAction(self.actSettings)

        self.windowMenu = self.menuBar().addMenu("&Window")
        self.updateWindowMenu()
        self.windowMenu.aboutToShow.connect(self.updateWindowMenu)

        self.menuBar().addSeparator()

        self.helpMenu = self.menuBar().addMenu("&Help")
        self.helpMenu.addAction(self.actAbout)

        self.editMenu.aboutToShow.connect(self.updateEditMenu)

    def updateMenus(self) -> None:
        active = self.getCurrentNodeEditorWidget()
        has_mdi_child = active is not None

        self.actSave.setEnabled(has_mdi_child)
        self.actSaveAs.setEnabled(has_mdi_child)
        self.actClose.setEnabled(has_mdi_child)
        self.actCloseAll.setEnabled(has_mdi_child)
        self.actTile.setEnabled(has_mdi_child)
        self.actCascade.setEnabled(has_mdi_child)
        self.actNext.setEnabled(has_mdi_child)
        self.actPrevious.setEnabled(has_mdi_child)
        self.actSeparator.setVisible(has_mdi_child)

        self.updateEditMenu()
        self.onSubWindowActivated(self.mdiArea.activeSubWindow())

    def updateEditMenu(self) -> None:
        try:
            active = self.getCurrentNodeEditorWidget()
            has_mdi_child = active is not None

            self.actPaste.setEnabled(has_mdi_child)

            self.actCut.setEnabled(has_mdi_child and active.hasSelectedItems())
            self.actCopy.setEnabled(has_mdi_child and active.hasSelectedItems())
            self.actDelete.setEnabled(
                has_mdi_child and active.hasSelectedItems()
            )

            self.actUndo.setEnabled(has_mdi_child and active.canUndo())
            self.actRedo.setEnabled(has_mdi_child and active.canRedo())
        except Exception as exc:  # pragma: no cover - defensive logging
            dumpException(exc)

    def updateWindowMenu(self) -> None:
        if not self.windowMenu:
            return
        self.windowMenu.clear()

        toolbar_nodes = self.windowMenu.addAction("Nodes Toolbar")
        toolbar_nodes.setCheckable(True)
        toolbar_nodes.triggered.connect(self.onWindowNodesToolbar)
        toolbar_nodes.setChecked(self.nodesDock.isVisible())

        self.windowMenu.addSeparator()

        self.windowMenu.addAction(self.actClose)
        self.windowMenu.addAction(self.actCloseAll)
        self.windowMenu.addSeparator()
        self.windowMenu.addAction(self.actTile)
        self.windowMenu.addAction(self.actCascade)
        self.windowMenu.addSeparator()
        self.windowMenu.addAction(self.actNext)
        self.windowMenu.addAction(self.actPrevious)
        self.windowMenu.addAction(self.actSeparator)

        windows = self.mdiArea.subWindowList()
        self.actSeparator.setVisible(len(windows) != 0)

        for index, window in enumerate(windows):
            child = window.widget()
            if not hasattr(child, "getUserFriendlyFilename"):
                continue
            text = f"{index + 1} {child.getUserFriendlyFilename()}"
            if index < 9:
                text = "&" + text

            action = self.windowMenu.addAction(text)
            action.setCheckable(True)
            action.setChecked(child is self.getCurrentNodeEditorWidget())
            action.triggered.connect(self.windowMapper.map)
            self.windowMapper.setMapping(action, window)

    def onWindowNodesToolbar(self) -> None:
        if self.nodesDock.isVisible():
            self.nodesDock.hide()
        else:
            self.nodesDock.show()


class MainWindowDockMixin:
    """Mixin for dock creation helpers used by the main window."""

    def createNodesDock(self) -> None:
        self.nodesDock = NodesDock(self)
        self.addDockWidget(Qt.TopDockWidgetArea, self.nodesDock)

    def createConfigDock(self) -> None:
        self.configDock = ConfigDock(self)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.configDock)

    def createLoggingDock(self) -> None:
        """Create a single logging dock that shows logs for the active design window"""
        self.loggingDock = LoggingDock(self)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.loggingDock)

    def getLoggingDock(self) -> LoggingDock:
        """Get the shared logging dock"""
        return getattr(self, 'loggingDock', None)

    def switchLoggingDock(self, design_window) -> None:
        """Switch the logging dock to show logs for a specific design window"""
        if hasattr(self, 'loggingDock') and self.loggingDock:
            self.loggingDock.switch_to_design_window(design_window)

    def onDesignWindowClose(self, design_window, event) -> None:
        """Handle design window close event to clean up logs"""
        if hasattr(self, 'loggingDock') and self.loggingDock:
            design_window_id = str(id(design_window))
            self.loggingDock.remove_design_window(design_window_id)

    def createStatusBar(self) -> None:
        self.statusBar().showMessage("Ready")
