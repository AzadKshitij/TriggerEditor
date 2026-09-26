from __future__ import annotations

import os

from nodeeditor.utils import dumpException
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QMenu, QMessageBox

from trigger_designer.qt.docks.logging_dock import LoggingDock
from trigger_designer.qt.docks.node_config import ConfigDock
from trigger_designer.qt.docks.nodes_list import NodesDock
from trigger_designer.qt.helpers.recent_files import RecentFilesManager


class MainWindowMenuMixin:
    """Mixin holding menu creation and update logic for the main window."""

    windowMenu = None
    helpMenu = None

    def createMenus(self) -> None:  # noqa: N802 (Qt naming style)
        super().createMenus()

        self.openRecentMenu = QMenu("&Open Recent", self)
        self.fileMenu.insertMenu(self.actSave, self.openRecentMenu)
        self.openRecentMenu.aboutToShow.connect(self._rebuild_recent_menu)
        self._rebuild_recent_menu()

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
            self.actDelete.setEnabled(has_mdi_child and active.hasSelectedItems())

            self.actUndo.setEnabled(has_mdi_child and active.canUndo())
            self.actRedo.setEnabled(has_mdi_child and active.canRedo())
            self._syncUndoRedoText(active)
        except Exception as exc:  # pragma: no cover - defensive logging
            dumpException(exc)

    def _syncUndoRedoText(self, active) -> None:
        """Label the undo/redo actions with the step they will apply.

        Falls back to the plain labels when the active window predates the
        command stack, so the menu is never left showing a stale description.
        """
        history = getattr(getattr(active, "scene", None), "history", None)
        undo_text = getattr(history, "currentText", lambda: "")()
        redo_text = getattr(history, "nextText", lambda: "")()

        if undo_text:
            self.actUndo.setText(f"&Undo {undo_text}")
        else:
            self.actUndo.setText("&Undo")

        if redo_text:
            self.actRedo.setText(f"&Redo {redo_text}")
        else:
            self.actRedo.setText("&Redo")

    def updateWindowMenu(self) -> None:
        if not self.windowMenu:
            return
        self.windowMenu.clear()

        toolbar_nodes = self.windowMenu.addAction("Nodes Toolbar")
        toolbar_nodes.setCheckable(True)
        toolbar_nodes.triggered.connect(self.onWindowNodesToolbar)
        toolbar_nodes.setChecked(self.nodesDock.isVisible())

        if hasattr(self, "loggingDock") and self.loggingDock is not None:
            logger_action = self.loggingDock.toggleViewAction()
            logger_action.setText("Show Logger")
            self.windowMenu.addAction(logger_action)

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

    def _recent_manager(self) -> RecentFilesManager:
        return RecentFilesManager()

    def refresh_recent_menu(self) -> None:
        if hasattr(self, "openRecentMenu"):
            self._rebuild_recent_menu()

    def _record_recent(self, path: str | None) -> None:
        if not path:
            return
        try:
            self._recent_manager().add_recent(path)
        except Exception as exc:  # pragma: no cover - defensive logging
            dumpException(exc)
        self.refresh_recent_menu()

    def _rebuild_recent_menu(self) -> None:
        menu = getattr(self, "openRecentMenu", None)
        if menu is None:
            return
        try:
            recents = self._recent_manager().recents()
        except Exception as exc:  # pragma: no cover - defensive logging
            dumpException(exc)
            recents = []
        menu.clear()
        menu.menuAction().setVisible(bool(recents))
        for index, path in enumerate(recents):
            label = os.path.basename(path) or path
            if index < 9:
                label = f"&{index + 1} {label}"
            action = menu.addAction(label)
            action.setToolTip(path)
            action.setStatusTip(path)
            action.triggered.connect(
                lambda _checked=False, p=path: self.open_recent_file(p)
            )
        if recents:
            menu.addSeparator()
            clear_action = menu.addAction("Clear Recent Files")
            clear_action.triggered.connect(self._clear_recents)

    def _clear_recents(self) -> None:
        try:
            self._recent_manager().clear()
        except Exception as exc:  # pragma: no cover - defensive logging
            dumpException(exc)
        self.refresh_recent_menu()

    def open_recent_file(self, path: str) -> None:
        manager = self._recent_manager()
        if not os.path.isfile(path):
            QMessageBox.warning(
                self,
                "Recent file not found",
                f'"{path}" no longer exists.\nIt was removed from recent files.',
            )
            try:
                manager.remove_recent(path)
            except Exception as exc:  # pragma: no cover - defensive logging
                dumpException(exc)
            self.refresh_recent_menu()
            return
        try:
            if not self.maybeSave():
                return
        except Exception as exc:  # pragma: no cover - defensive logging
            dumpException(exc)
            return
        try:
            self.openFile(path)
        except Exception as exc:  # pragma: no cover - defensive logging
            dumpException(exc)


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
        return getattr(self, "loggingDock", None)

    def switchLoggingDock(self, design_window) -> None:
        """Switch the logging dock to show logs for a specific design window"""
        if hasattr(self, "loggingDock") and self.loggingDock:
            self.loggingDock.switch_to_design_window(design_window)

    def onDesignWindowClose(self, design_window, event) -> None:
        """Handle design window close event to clean up logs"""
        if hasattr(self, "loggingDock") and self.loggingDock:
            design_window_id = str(id(design_window))
            self.loggingDock.remove_design_window(design_window_id)

    def createStatusBar(self) -> None:
        self.statusBar().showMessage("Ready")
