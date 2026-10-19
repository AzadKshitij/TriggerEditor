from nodeeditor.node_editor_widget import NodeEditorWidget
from typing import Callable, Optional, cast
from typing_extensions import override
from qtpy.QtGui import (
    QBrush,
    QIcon,
    QKeySequence,
    QCloseEvent,
)
from qtpy.QtWidgets import (
    QApplication,
    QMdiArea,
    QMenuBar,
    QTableView,
    QWidget,
    QFileDialog,
    QMdiSubWindow,
    QTabWidget,
    QShortcut,
)
from qtpy.QtCore import Qt, QSignalMapper

import orjson as json
from orjson import JSONDecodeError

from nodeeditor.node_editor_window import NodeEditorWindow
from nodeeditor.utils import dumpException

from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.helpers.main_window_actions_mixin import MainWindowActionsMixin
from trigger_designer.qt.helpers.main_window_ui_mixin import (
    MainWindowDockMixin,
    MainWindowMenuMixin,
)
from trigger_designer.qt.helpers import global_logger
from trigger_designer.qt.layout_state import LayoutState, apply_default_layout
from trigger_designer.qt.render_settings import apply_render_settings_to_scene
from trigger_designer.qt.theme_manager import (
    apply_theme_to_scene,
    get_theme_manager,
)
from trigger_designer.qt.widgets.common.window_chrome import install_window_chrome


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


def parse_node_clipboard_payload(raw_text: str) -> dict | None:
    """Validate clipboard text as a node paste payload.

    ``orjson.loads`` happily parses JSON scalars (``true`` -> ``True``),
    and the base-class paste handler then crashes on ``'nodes' not in
    data``. Reject anything that is not a ``{"nodes": [...]}`` mapping
    before it gets there. Returns the payload dict, or ``None``.
    """
    try:
        data = json.loads(raw_text)
    except JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    if not isinstance(data.get("nodes"), list):
        return None
    return data


class TriggerWindow(
    MainWindowDockMixin, MainWindowMenuMixin, MainWindowActionsMixin, NodeEditorWindow
):
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

        if not file_path:
            self._restore_last_session()

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
        self.mdiArea.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.mdiArea.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
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
        self.createDataPreviewDock()

        self.createMenus()

        # VSCode-style chrome: the menu bar moves into a frameless 32px
        # window row beside the caption buttons. Installed before
        # readSettings() so restored geometry already has no native frame.
        self.window_chrome = install_window_chrome(self)

        self.createToolBars()
        self.createStatusBar()
        self.updateMenus()

        self.readSettings()
        self._theme_mdi_background()

        try:
            get_theme_manager().themeChanged.connect(self.apply_appearance)
        except TypeError:  # pragma: no cover - duplicate connection guard
            pass

        self.setWindowTitle("Trigger Designer")
        self.setWindowIcon(QIcon(str(self.rsm.get_full_path("app_icon"))))

        self.setDockNestingEnabled(True)

        # Initialize global logger with this main window
        global_logger.set_main_window(self)

    def toggleFullScreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    @override
    def menuBar(self) -> QMenuBar:
        """The real menu bar, which lives inside the window chrome now.

        Once ``install_window_chrome()`` gives the menu slot to the chrome,
        the base implementation would auto-create a *new* empty QMenuBar and
        swap the chrome out of the window. Every caller (including the
        qtpy-nodeeditor menu builders) keeps getting the embedded bar.
        """
        chrome = getattr(self, "window_chrome", None)
        if chrome is not None:
            return chrome.menu_bar()
        return super().menuBar()

    @override
    def nativeEvent(self, eventType, message):
        """Hand the Win32 non-client messages to the chrome.

        The chrome answers ``WM_NCCALCSIZE`` / ``WM_NCHITTEST`` so Windows
        treats the custom row as a real caption: snap, the Snap Layouts
        flyout, the native edge cursors and the DWM shadow all come from
        there. Any platform without that layer (and the offscreen plugin the
        tests use) gets ``(False, 0)``, which is what the base class returns.

        ``super().nativeEvent(...)`` is deliberately not called: on PyQt6 6.8
        it re-enters the message it was handed and aborts the process
        (0xC000041D).
        """
        chrome = getattr(self, "window_chrome", None)
        if chrome is None:
            return False, 0
        return chrome.native_event(eventType, message)

    # -- layout / session -------------------------------------------------
    @override
    def readSettings(self) -> None:
        """Restore window geometry and dock state (LayoutState owns policy)."""
        LayoutState().restore(self)

    @override
    def writeSettings(self) -> None:
        """Persist the single auto-saved layout."""
        LayoutState().save(self)

    def saveCurrentLayout(self) -> None:
        """Window menu action: write the current geometry + dock state now."""
        LayoutState().save(self)
        if self.statusBar() is not None:
            self.statusBar().showMessage("Layout saved", 3000)

    def resetLayout(self) -> None:
        """Window menu action: forget the saved layout and restore defaults."""
        LayoutState().clear()
        apply_default_layout(self)
        self.apply_appearance()
        if self.statusBar() is not None:
            self.statusBar().showMessage("Layout reset", 3000)

    def _restore_last_session(self) -> None:
        """Reopen last-session files only when the preference is on."""
        files, active = LayoutState().session_to_restore()
        if not files:
            return
        for path in files:
            self.openFile(path)
        if active:
            sub = self.findMdiChild(active)
            if sub is not None:
                self.mdiArea.setActiveSubWindow(sub)

    def _apply_editor_preferences(self, design_window: TriggerSubWindow) -> None:
        scene = getattr(design_window, "scene", None)
        if scene is None:
            return
        apply_theme_to_scene(scene)
        apply_render_settings_to_scene(scene)
        self._theme_node_rings(scene)

    def apply_render_settings(self) -> None:
        """Push the user's canvas rendering choices into every open scene.

        Each sub-window owns its own graphics scene, so the settings have to
        be handed to all of them.
        """
        for sub in self.mdiArea.subWindowList():
            widget = sub.widget()
            scene = getattr(widget, "scene", None)
            if scene is not None:
                apply_render_settings_to_scene(scene)

    @staticmethod
    def _theme_node_rings(scene) -> None:
        for node in getattr(scene, "nodes", []):
            gr_node = getattr(node, "grNode", None)
            refresh = getattr(gr_node, "apply_theme", None)
            if callable(refresh):
                refresh()

    def _theme_mdi_background(self, manager=None) -> None:
        """Colour the workspace frame.

        ``QMdiArea`` paints its own ``background`` brush, so a stylesheet rule
        never reaches it - it has to be set here.
        """
        mdi = getattr(self, "mdiArea", None)
        if mdi is None:
            return
        manager = manager or get_theme_manager()
        mdi.setBackground(QBrush(manager.color("canvas_background", "#0E1115")))

    def apply_appearance(self, _theme: object = None) -> None:
        """Re-theme every open surface after a theme/accent change."""
        manager = get_theme_manager()
        self._theme_mdi_background(manager)
        for sub in self.mdiArea.subWindowList():
            widget = sub.widget()
            scene = getattr(widget, "scene", None)
            if scene is not None:
                apply_theme_to_scene(scene, manager)
                self._theme_node_rings(scene)
            for view in widget.findChildren(QTableView):
                model = view.model()
                refresh = getattr(model, "refresh_theme", None)
                if callable(refresh):
                    refresh()
            # Python-painted children (SQL formula editors) expose apply_theme.
            for child in widget.findChildren(QWidget):
                refresh = getattr(child, "apply_theme", None)
                if callable(refresh):
                    refresh()
        # Icon buttons hold a rendered pixmap; the monochrome ui/ glyphs are
        # re-rendered per theme, so they have to be re-resolved too.
        for child in self.findChildren(QWidget):
            refresh = getattr(child, "apply_theme", None)
            if callable(refresh):
                refresh()
        logging_dock = getattr(self, "loggingDock", None)
        if logging_dock is not None and hasattr(logging_dock, "apply_theme"):
            logging_dock.apply_theme()
        preview_dock = getattr(self, "dataPreviewDock", None)
        if preview_dock is not None:
            refresh = getattr(preview_dock, "refresh_theme", None)
            if callable(refresh):
                refresh()
        # Caption glyphs are painted in Python, so they re-read the tokens.
        chrome = getattr(self, "window_chrome", None)
        if chrome is not None:
            chrome.apply_theme()

    @override
    def onEditPaste(self) -> None:
        """Paste nodes, ignoring clipboard text that is not node data.

        Overrides the base implementation, which raises ``TypeError`` on
        valid JSON scalars (``true``, ``123``) instead of ignoring them.
        """
        if self.getCurrentNodeEditorWidget() is None:
            return
        clipboard = QApplication.instance().clipboard()
        raw_text = clipboard.text() if clipboard is not None else ""
        if parse_node_clipboard_payload(raw_text) is None:
            message = "Paste ignored: clipboard does not contain node data"
            if self.statusBar() is not None:
                self.statusBar().showMessage(message, 5000)
            global_logger.warning(message)
            return
        super().onEditPaste()

    def closeEvent(self, event: Optional[QCloseEvent]) -> None:
        # Capture the session before children close: the window list is the
        # source of truth for "what was open", and closing clears it.
        LayoutState().save_session(self)
        self.mdiArea.closeAllSubWindows()
        if self.mdiArea.currentSubWindow() and event is not None:
            event.ignore()
        else:
            self.writeSettings()
            if event is not None:
                event.accept()
            # Quit through the event loop instead of raising SystemExit from
            # inside a native close callback: that unwinds through Qt's C++
            # frames and faults (0xC0000005 in sip) on shutdown.
            app = QApplication.instance()
            if app is not None:
                app.quit()

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
                    self._record_recent(fname)
                else:
                    # we need to create new subWindow and open the file
                    nodeeditor = TriggerSubWindow()
                    if nodeeditor.fileLoad(fname):
                        if self.statusBar() is not None:
                            self.statusBar().showMessage("File %s loaded" % fname, 5000)
                        nodeeditor.setTitle()
                        subwnd = self.createMdiChild(nodeeditor)
                        subwnd.show()
                        self._record_recent(fname)
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
                        self._record_recent(fname)
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
                            self._record_recent(fname)
                        else:
                            nodeeditor.close()
        except Exception as e:
            dumpException(e)

    def onFileSave(self):
        result = super().onFileSave()
        if result:
            current = self.getCurrentNodeEditorWidget()
            filename = getattr(current, "filename", None)
            self._record_recent(filename)
        return result

    def onFileSaveAs(self):
        result = super().onFileSaveAs()
        if result:
            current = self.getCurrentNodeEditorWidget()
            filename = getattr(current, "filename", None)
            self._record_recent(filename)
        return result

    def showWelcomeDialogIfNeeded(self) -> None:
        """Show the startup welcome dialog unless opted out."""
        from trigger_designer.qt.dialogs.welcome_dialog import WelcomeDialog
        from trigger_designer.qt.helpers.recent_files import RecentFilesManager

        manager = RecentFilesManager()
        if not manager.is_welcome_enabled():
            return
        dialog = WelcomeDialog(
            manager.recents(),
            show_on_startup=manager.is_welcome_enabled(),
            parent=self,
        )
        if dialog.exec() != dialog.DialogCode.Accepted:
            manager.set_welcome_enabled(dialog.show_on_startup)
            return
        manager.set_welcome_enabled(dialog.show_on_startup)
        if dialog.action == "open" and dialog.selected_path:
            self.open_recent_file(dialog.selected_path)
        elif dialog.action == "new":
            self.onFileNew()
        elif dialog.action == "browse":
            self.onFileOpen()

    def about(self) -> None:
        from trigger_designer.qt.dialogs.about_dialog import AboutDialog

        AboutDialog(self).exec()

    def createToolBars(self) -> None:
        pass

    def createMdiChild(self, child_widget=None):
        nodeeditor = (
            child_widget if child_widget is not None else TriggerSubWindow(self)
        )
        # Add the MDI window (which contains both the node editor and its dock) to the MDI area
        subwnd = self.mdiArea.addSubWindow(nodeeditor)
        subwnd.setWindowIcon(self.empty_icon)
        nodeeditor.scene.addItemSelectedListener(self.updateEditMenu)
        nodeeditor.scene.addItemSelectedListener(
            lambda: self.configDock.updateConfig(nodeeditor.getSelectedItems())
        )
        nodeeditor.scene.addItemsDeselectedListener(self.updateEditMenu)
        nodeeditor.scene.addItemsDeselectedListener(
            lambda: self.configDock.updateConfig(nodeeditor.getSelectedItems())
        )
        # Connect signals
        nodeeditor.scene.history.addHistoryModifiedListener(self.updateEditMenu)
        nodeeditor.addCloseEventListener(self.onSubWndClose)
        # nodeeditor.itemSelected.connect(self.onNodeSelected)

        # Connect the design window to the shared logging dock
        nodeeditor.setLoggingDock(self.getLoggingDock())

        # Wire the preview dock: the hooks are installed once per window and
        # the dock ignores events from windows it does not follow.
        nodeeditor.scene.addItemSelectedListener(
            lambda: self.dataPreviewDock.note_selection_changed(nodeeditor)
        )
        nodeeditor.scene.addItemsDeselectedListener(
            lambda: self.dataPreviewDock.note_selection_changed(nodeeditor)
        )
        nodeeditor.scene.addNodeEvaluatedListener(
            lambda node: self.dataPreviewDock.note_node_evaluated(nodeeditor, node)
        )
        nodeeditor.executionResultsChanged.connect(
            lambda: self.dataPreviewDock.note_run_finished(nodeeditor)
        )

        # Switch the docks to this window if it's the active one
        if self.mdiArea.activeSubWindow() == subwnd:
            self.switchLoggingDock(nodeeditor)
            self.switchDataPreviewDock(nodeeditor)

        # Theme the new scene (canvas grid + node state rings) before it paints.
        self._apply_editor_preferences(nodeeditor)

        # Add a welcome log message for new design window
        nodeeditor.logInfo(
            f"Design window '{nodeeditor.windowTitle()}' created and ready"
        )

        return subwnd

    def onSubWindowActivated(self, sub_window: QMdiSubWindow) -> None:
        """Handle sub window activation to switch the dock contexts"""
        chrome = getattr(self, "window_chrome", None)
        if sub_window:
            widget = sub_window.widget()
            if hasattr(widget, "setLoggingDock"):  # Check if it's a design window
                # Switch both docks to show content for this window
                self.switchLoggingDock(widget)
                self.switchDataPreviewDock(widget)
            if chrome is not None:
                chrome.set_context_title(sub_window.windowTitle())
        elif chrome is not None:
            chrome.set_context_title(None)

    def onSubWndClose(self, widget: QWidget, event: Optional[QCloseEvent]) -> None:
        # Activate the window being closed first so ``maybeSave`` targets the
        # right document (``findMdiChild`` matches by filename, as upstream).
        existing = self.findMdiChild(widget.filename)
        self.mdiArea.setActiveSubWindow(existing)

        if self.maybeSave():
            # The close is really happening: drop per-window dock state.
            self.onDesignWindowClose(widget, event)
            if event is not None:
                event.accept()
        elif event is not None:
            event.ignore()

    def findMdiChild(self, filename):
        for window in self.mdiArea.subWindowList():
            if window.widget().filename == filename:
                return window
        return None

    def onNodeSelected(self, node, select_state: bool) -> None:
        # self.nodeeditor.getSelectedItems()
        self.configDock.updateConfig(node)
