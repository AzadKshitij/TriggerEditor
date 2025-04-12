from nodeeditor.node_editor_widget import NodeEditorWidget
from typing import Optional, cast
from typing_extensions import override
import nodeeditor
from trigger_designer.qt.docks.result import ResultDock
import os
from qtpy.QtGui import QIcon, QKeySequence, QCloseEvent, QPalette, QColor, QGuiApplication, QScreen
from qtpy.QtWidgets import QMdiArea, QWidget, QDockWidget, QAction, QMessageBox, QFileDialog, QSizePolicy, QMdiSubWindow, QTabWidget, QDialog
from qtpy.QtCore import Qt, QResource, QUrl, QSignalMapper

from loguru import logger as glogger

from nodeeditor.utils import loadStylesheets
from nodeeditor.node_editor_window import NodeEditorWindow
from nodeeditor.utils import dumpException, pp

from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.docks.nodes_list import NodesDock
from trigger_designer.qt.docks.node_config import ConfigDock
from trigger_designer.qt.models.settings_panel import SettingsDialog
from trigger_designer.qt.helpers.signal_handler import SignalHandler


# Enabling edge validators
from nodeeditor.node_edge import Edge
from nodeeditor.node_edge_validators import (
    edge_validator_debug,
    edge_cannot_connect_two_outputs_or_two_inputs,
    edge_cannot_connect_input_and_output_of_same_node
)
Edge.registerEdgeValidator(edge_validator_debug)
Edge.registerEdgeValidator(edge_cannot_connect_two_outputs_or_two_inputs)
Edge.registerEdgeValidator(edge_cannot_connect_input_and_output_of_same_node)

# images for the dark skin


DEBUG = False


class TriggerWindow(NodeEditorWindow):

    def __init__(self, file_path: Optional[str] = None, name_company: str = 'Trigger', name_product: str = 'Trigger Editor') -> None:
        super().__init__()
        self.openFile(file_path)
        self.name_company = name_company
        self.name_product = name_product
        self.setObjectName("MainWindow")
        self.readSettings()

        # self.setWindowIcon(QIcon(":/trigger_designer/images/icon.png"))

    def initUI(self, parent: Optional[QWidget] = None) -> None:
        # super(CalculatorWindow, self).__init__(parent)
        self.windowMapper = QSignalMapper(self)
        # Create logger

        # -----------------------------------
        # self.stylesheet_filename = "trigger_designer/qss/darkstyle.qss"
        # self.stylesheet_filename = os.path.join(
        #     os.path.dirname(__file__), "qss/nodeeditor.qss")

        # loadStylesheets(
        #     os.path.join(os.path.dirname(__file__),
        #                  "../qss/nodeeditor.qss"),
        #     self.stylesheet_filename
        # )

        self.empty_icon = QIcon(".")

        if DEBUG:
            print("Registered nodes:")

        self.mdiArea = QMdiArea()
        self.mdiArea.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.mdiArea.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.mdiArea.setViewMode(QMdiArea.ViewMode.TabbedView)
        self.mdiArea.setDocumentMode(True)
        self.mdiArea.setTabsClosable(True)
        self.mdiArea.setTabsMovable(True)

        # Enable window tiling and docking behavior
        self.setDockNestingEnabled(True)
        self.setTabPosition(
            Qt.DockWidgetArea.AllDockWidgetAreas, QTabWidget.TabPosition.North)
        self.setCentralWidget(self.mdiArea)

        self.mdiArea.subWindowActivated.connect(self.updateMenus)

        # Docks
        self.createNodesDock()
        self.createConfigDock()
        # self.createResultDock()

        self.createActions()
        self.createMenus()
        self.createToolBars()
        self.createStatusBar()
        self.updateMenus()

        self.readSettings()

        self.setWindowTitle("Trigger Designer")

        self.setDockNestingEnabled(True)
        # self.tabifyDockWidget(self.configDock, self.resultDock)

    def closeEvent(self, event: Optional[QCloseEvent]) -> None:
        self.mdiArea.closeAllSubWindows()
        if self.mdiArea.currentSubWindow() and event is not None:
            event.ignore()
        else:
            self.writeSettings()
            if event is not None:
                event.accept()
            # hacky fix for PyQt 5.14.x
            import sys
            sys.exit(0)

    def createActions(self) -> None:
        super().createActions()

        self.actSettings = QAction("Settings", self,
                                   statusTip="Open settings dialog",
                                   triggered=self.showSettings)

        self.actClose = QAction("Cl&ose", self, statusTip="Close the active window",
                                triggered=self.mdiArea.closeActiveSubWindow)
        self.actCloseAll = QAction(
            "Close &All", self, statusTip="Close all the windows", triggered=self.mdiArea.closeAllSubWindows)
        self.actTile = QAction(
            "&Tile", self, statusTip="Tile the windows", triggered=self.mdiArea.tileSubWindows)
        self.actCascade = QAction(
            "&Cascade", self, statusTip="Cascade the windows", triggered=self.mdiArea.cascadeSubWindows)
        self.actNext = QAction("Ne&xt", self, shortcut=QKeySequence.StandardKey.NextChild,
                               statusTip="Move the focus to the next window", triggered=self.mdiArea.activateNextSubWindow)
        self.actPrevious = QAction("Pre&vious", self, shortcut=QKeySequence.StandardKey.PreviousChild,
                                   statusTip="Move the focus to the previous window", triggered=self.mdiArea.activatePreviousSubWindow)

        self.actSeparator = QAction(self)
        self.actSeparator.setSeparator(True)

        self.actAbout = QAction(
            "&About", self, statusTip="Show the application's About box", triggered=self.about)

    def showSettings(self) -> None:
        dialog = SettingsDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Reload settings and apply them
            self.loadSettings()

    def loadSettings(self) -> None:
        glogger.debug("Loading settings...")

    @override
    def getCurrentNodeEditorWidget(self) -> 'NodeEditorWidget':
        """ we're returning NodeEditorWidget here... """
        activeSubWindow = self.mdiArea.activeSubWindow()
        if activeSubWindow:
            return cast(NodeEditorWidget, activeSubWindow.widget())
        return cast(NodeEditorWidget, None)

    def onFileNew(self) -> None:
        try:
            subwnd = self.createMdiChild()
            subwnd.widget().fileNew()
            subwnd.show()
        except Exception as e:
            dumpException(e)

    def openFile(self, fname: Optional[str]) -> None:
        try:
            if fname:
                existing = self.findMdiChild(fname)
                if existing:
                    self.mdiArea.setActiveSubWindow(existing)
                else:
                    # we need to create new subWindow and open the file
                    nodeeditor = TriggerSubWindow()
                    if nodeeditor.fileLoad(fname):
                        if self.statusBar() is not None:
                            self.statusBar().showMessage("File %s loaded" % fname, 5000)
                        nodeeditor.setTitle()
                        subwnd = self.createMdiChild(nodeeditor)
                        subwnd.show()
                    else:
                        nodeeditor.close()
        except Exception as e:
            dumpException(e)

    def onFileOpen(self) -> None:
        fnames, filter = QFileDialog.getOpenFileNames(
            self, 'Open design from file', self.getFileDialogDirectory(), self.getFileDialogFilter())

        try:
            for fname in fnames:
                if fname:
                    existing = self.findMdiChild(fname)
                    if existing:
                        self.mdiArea.setActiveSubWindow(existing)
                    else:
                        # we need to create new subWindow and open the file
                        nodeeditor = TriggerSubWindow()
                        if nodeeditor.fileLoad(fname):
                            if self.statusBar() is not None:
                                self.statusBar().showMessage("File %s loaded" % fname, 5000)
                            nodeeditor.setTitle()
                            subwnd = self.createMdiChild(nodeeditor)
                            subwnd.show()
                        else:
                            nodeeditor.close()
        except Exception as e:
            dumpException(e)

    def about(self) -> None:
        QMessageBox.about(self, "About Calculator NodeEditor Example",
                          "The <b>Calculator NodeEditor</b> example demonstrates how to write multiple "
                          "document interface applications using PyQt5 and NodeEditor. For more information visit: "
                          "<a href='https://www.blenderfreak.com/'>www.BlenderFreak.com</a>")

    def createMenus(self) -> None:
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
        # print("update Menus")
        active = self.getCurrentNodeEditorWidget()
        hasMdiChild = (active is not None)

        self.actSave.setEnabled(hasMdiChild)
        self.actSaveAs.setEnabled(hasMdiChild)
        self.actClose.setEnabled(hasMdiChild)
        self.actCloseAll.setEnabled(hasMdiChild)
        self.actTile.setEnabled(hasMdiChild)
        self.actCascade.setEnabled(hasMdiChild)
        self.actNext.setEnabled(hasMdiChild)
        self.actPrevious.setEnabled(hasMdiChild)
        self.actSeparator.setVisible(hasMdiChild)

        self.updateEditMenu()
        self.onSubWindowActivated(self.mdiArea.activeSubWindow())

    def updateEditMenu(self) -> None:
        try:
            # print("update Edit Menu")
            active = self.getCurrentNodeEditorWidget()
            hasMdiChild = (active is not None)

            self.actPaste.setEnabled(hasMdiChild)

            self.actCut.setEnabled(hasMdiChild and active.hasSelectedItems())
            self.actCopy.setEnabled(hasMdiChild and active.hasSelectedItems())
            self.actDelete.setEnabled(
                hasMdiChild and active.hasSelectedItems())

            self.actUndo.setEnabled(hasMdiChild and active.canUndo())
            self.actRedo.setEnabled(hasMdiChild and active.canRedo())
        except Exception as e:
            dumpException(e)

    def updateWindowMenu(self) -> None:
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

        for i, window in enumerate(windows):
            child: QMdiSubWindow = window.widget()

            text = "%d %s" % (i + 1, child.getUserFriendlyFilename())
            if i < 9:
                text = '&' + text

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

    def createToolBars(self) -> None:
        pass

    # Dock Widgets #
    def createNodesDock(self) -> None:
        self.nodesDock = NodesDock(self)
        self.addDockWidget(Qt.TopDockWidgetArea, self.nodesDock)

    def createConfigDock(self) -> None:
        self.configDock = ConfigDock(self)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.configDock)

    # def createResultDock(self) -> None:
    #     self.resultDock = ResultDock(self)
    #     self.addDockWidget(Qt.BottomDockWidgetArea, self.resultDock)

    def createStatusBar(self) -> None:
        self.statusBar().showMessage("Ready")

    def createMdiChild(self, child_widget=None):
        nodeeditor = child_widget if child_widget is not None else TriggerSubWindow(
            self)
        subwnd = self.mdiArea.addSubWindow(nodeeditor)
        subwnd.setWindowIcon(self.empty_icon)
        # nodeeditor.scene.addItemSelectedListener(self.updateEditMenu)
        # nodeeditor.scene.addItemsDeselectedListener(self.updateEditMenu)
        nodeeditor.scene.history.addHistoryModifiedListener(
            self.updateEditMenu)
        nodeeditor.addCloseEventListener(self.onSubWndClose)
        nodeeditor.itemSelected.connect(self.onNodeSelected)
        return subwnd

    def onSubWindowActivated(self, sub_window: QMdiSubWindow) -> None:
        print("Subwindow activated")
        if sub_window:
            widget = sub_window.widget()
            if isinstance(widget, TriggerSubWindow):
                SignalHandler.instance().emit_sub_window_activated(widget.design_window_id)

                # widget.logger.set_result_dock(
                #     self.resultDock, widget.design_window_id)

    def onSubWndClose(self, widget: QWidget, event: Optional[QCloseEvent]) -> None:
        existing = self.findMdiChild(widget.filename)
        self.mdiArea.setActiveSubWindow(existing)

        if self.maybeSave():
            event.accept()
        else:
            event.ignore()

    def findMdiChild(self, filename):
        for window in self.mdiArea.subWindowList():
            if window.widget().filename == filename:
                return window
        return None

    def onNodeSelected(self, node) -> None:
        # self.nodeeditor.getSelectedItems()
        self.configDock.updateConfig(node)
