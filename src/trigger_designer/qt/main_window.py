from nodeeditor.node_editor_widget import NodeEditorWidget
from typing import Callable, Optional, cast
from typing_extensions import override
from qtpy.QtGui import (
    QIcon,
    QKeySequence,
    QCloseEvent,
)
from qtpy.QtWidgets import (
    QMdiArea,
    QWidget,
    QMessageBox,
    QFileDialog,
    QMdiSubWindow,
    QTabWidget,
    QShortcut
)
from qtpy.QtCore import Qt, QSignalMapper

from nodeeditor.node_editor_window import NodeEditorWindow
from nodeeditor.utils import dumpException

from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.helpers.main_window_actions_mixin import MainWindowActionsMixin
from trigger_designer.qt.helpers.main_window_ui_mixin import (
    MainWindowDockMixin,
    MainWindowMenuMixin,
)
from trigger_designer.qt.helpers import global_logger


# Enabling edge validators
from nodeeditor.node_edge import Edge
from nodeeditor.node_edge_validators import (
    edge_validator_debug,
    edge_cannot_connect_two_outputs_or_two_inputs,
    edge_cannot_connect_input_and_output_of_same_node,
)

from trigger_designer.qt.resource_manager import ResourceManager

Edge.registerEdgeValidator(edge_validator_debug)
Edge.registerEdgeValidator(edge_cannot_connect_two_outputs_or_two_inputs)
Edge.registerEdgeValidator(edge_cannot_connect_input_and_output_of_same_node)

# images for the dark skin


DEBUG = False


class TriggerWindow(MainWindowDockMixin, MainWindowMenuMixin, MainWindowActionsMixin, NodeEditorWindow):

    def __init__(
        self,
        file_path: Optional[str] = None,
        name_company: str = "Trigger",
        name_product: str = "Trigger Editor",
    ) -> None:
        super().__init__()
        
        # We'll create a single logging dock in initUI
        
        self.openFile(file_path)
        self.name_company = name_company
        self.name_product = name_product

        self.setObjectName("MainWindow")
        self.readSettings()

        self.shortcut = QShortcut(QKeySequence("F11"), self)
        self.shortcut.activated.connect(self.toggleFullScreen)

        # self.setWindowIcon(QIcon(":/trigger_designer/images/icon.png"))

    def initUI(self, parent: Optional[QWidget] = None) -> None:
        
        # super(CalculatorWindow, self).__init__(parent)
        self.windowMapper = QSignalMapper(self)

        # Create logger
        self.empty_icon = QIcon(".")
        self.rsm = ResourceManager()

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
            Qt.DockWidgetArea.AllDockWidgetAreas, QTabWidget.TabPosition.North
        )
        self.setCentralWidget(self.mdiArea)

        self.mdiArea.subWindowActivated.connect(self.updateMenus)
        self.mdiArea.subWindowActivated.connect(self.onSubWindowActivated)

        self.createActions()

        # Docks
        self.createNodesDock()
        self.createConfigDock()
        self.createLoggingDock()
        # self.createResultDock()

        self.createMenus()
        self.createToolBars()
        self.createStatusBar()
        self.updateMenus()

        self.readSettings()

        self.setWindowTitle("Trigger Designer")
        self.setWindowIcon(QIcon(str(self.rsm.get_full_path("app_icon"))))

        self.setDockNestingEnabled(True)
        
        # Initialize global logger with this main window
        global_logger.set_main_window(self)
        # self.tabifyDockWidget(self.configDock, self.resultDock)

    def toggleFullScreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

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

    @override
    def getCurrentNodeEditorWidget(self) -> "NodeEditorWidget":
        """we're returning NodeEditorWidget here..."""
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
            self,
            "Open design from file",
            self.getFileDialogDirectory(),
            self.getFileDialogFilter(),
        )

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
                                self.statusBar().showMessage(
                                    "File %s loaded" % fname, 5000
                                )
                            nodeeditor.setTitle()
                            subwnd = self.createMdiChild(nodeeditor)
                            subwnd.show()
                        else:
                            nodeeditor.close()
        except Exception as e:
            dumpException(e)

    def about(self) -> None:
        QMessageBox.about(
            self,
            "About Calculator NodeEditor Example",
            "The <b>Calculator NodeEditor</b> example demonstrates how to write multiple "
            "document interface applications using PyQt5 and NodeEditor. For more information visit: "
            "<a href='https://www.blenderfreak.com/'>www.BlenderFreak.com</a>",
        )

    def createToolBars(self) -> None:
        pass

    # Dock Widgets #
    # def createResultDock(self) -> None:
    #     self.resultDock = ResultDock(self)
    #     self.addDockWidget(Qt.BottomDockWidgetArea, self.resultDock)

    def createMdiChild(self, child_widget=None):
        nodeeditor = (
            child_widget if child_widget is not None else TriggerSubWindow(
                self)
        )
        # Add the MDI window (which contains both the node editor and its dock) to the MDI area
        subwnd = self.mdiArea.addSubWindow(nodeeditor)
        subwnd.setWindowIcon(self.empty_icon)
        nodeeditor.scene.addItemSelectedListener(self.updateEditMenu)
        nodeeditor.scene.addItemSelectedListener(
            lambda: self.configDock.updateConfig(nodeeditor.getSelectedItems()))
        nodeeditor.scene.addItemsDeselectedListener(self.updateEditMenu)
        nodeeditor.scene.addItemsDeselectedListener(
            lambda: self.configDock.updateConfig(nodeeditor.getSelectedItems()))
        # Connect signals
        nodeeditor.scene.history.addHistoryModifiedListener(
            self.updateEditMenu)
        nodeeditor.addCloseEventListener(self.onSubWndClose)
        # nodeeditor.itemSelected.connect(self.onNodeSelected)
        
        # Connect the design window to the shared logging dock
        nodeeditor.setLoggingDock(self.getLoggingDock())
        
        # Switch logging dock to this window if it's the active one
        if self.mdiArea.activeSubWindow() == subwnd:
            self.switchLoggingDock(nodeeditor)
            
        # Add a welcome log message for new design window
        nodeeditor.logInfo(f"Design window '{nodeeditor.windowTitle()}' created and ready")

        return subwnd

    def onSubWindowActivated(self, sub_window: QMdiSubWindow) -> None:
        """Handle sub window activation to switch logging dock context"""
        if sub_window:
            widget = sub_window.widget()
            if hasattr(widget, 'setLoggingDock'):  # Check if it's a design window
                # Switch the logging dock to show logs for this window
                self.switchLoggingDock(widget)

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

    def onNodeSelected(self, node, select_state: bool) -> None:
        # self.nodeeditor.getSelectedItems()
        self.configDock.updateConfig(node)
