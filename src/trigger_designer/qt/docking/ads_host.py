"""PySide6-QtAds implementation of :class:`DockHost`.

Nothing outside this module imports ``PySide6QtAds``; the app talks to the
``DockHost`` protocol in ``host.py``.
"""

from __future__ import annotations

from functools import partial

import PySide6QtAds as QtAds
from loguru import logger
from qtpy.QtCore import QByteArray, QObject, Qt, QTimer, Signal
from qtpy.QtGui import QAction, QGuiApplication
from qtpy.QtWidgets import QMainWindow, QSplitter, QWidget

from trigger_designer.qt.docking.layouts import Area, LayoutSpec, Placement
from trigger_designer.qt.docking.panel import CENTRAL, Panel
from trigger_designer.qt.docking.screen_guard import rescue_offscreen

_QT_AREAS = {
    Area.LEFT: QtAds.LeftDockWidgetArea,
    Area.RIGHT: QtAds.RightDockWidgetArea,
    Area.TOP: QtAds.TopDockWidgetArea,
    Area.BOTTOM: QtAds.BottomDockWidgetArea,
}


class AdsDockHost(QObject):
    """Owns a ``CDockManager`` over the main window and every panel's dock."""

    visibility_changed = Signal(str, bool)

    def __init__(self, window: QMainWindow) -> None:
        super().__init__(window)
        QtAds.CDockManager.setConfigFlags(QtAds.CDockManager.DefaultOpaqueConfig)
        # Titles are short and fixed; eliding them to "Lo..." only hides the
        # name. Close buttons only appear on floating panels (see
        # ``_sync_closable``); a docked panel is hidden from the Window menu,
        # so the area-wide close button is off everywhere.
        QtAds.CDockManager.setConfigFlag(QtAds.CDockManager.DisableTabTextEliding, True)
        QtAds.CDockManager.setConfigFlag(
            QtAds.CDockManager.DockAreaHasCloseButton, False
        )
        self._manager = QtAds.CDockManager(window)
        # QtAds installs its own widget-level stylesheet on the manager, which
        # outranks the application's QSS. Clear it so the dock chrome follows
        # the theme (the ``ads--*`` rules in resources/qt/themes/base.qss).
        self._manager.setStyleSheet("")
        # New splitters appear whenever a drop splits an area.
        self._manager.dockAreasAdded.connect(self._schedule_tidy_splitters)
        # A floating panel left on a monitor that is unplugged would be
        # unreachable, so pull it back whenever a screen goes away.
        app = QGuiApplication.instance()
        if app is not None:
            app.screenRemoved.connect(self._schedule_rescue_floating)
        self._central_dock: QtAds.CDockWidget | None = None
        self._central_area: QtAds.CDockAreaWidget | None = None
        self._panels: dict[str, Panel] = {}
        self._docks: dict[str, QtAds.CDockWidget] = {}

    # -- DockHost protocol -------------------------------------------------

    def widget(self) -> QWidget:
        return self._manager

    def set_central(self, widget: QWidget) -> None:
        dock = QtAds.CDockWidget(self._manager, "Workflow")
        dock.setFeature(QtAds.CDockWidget.DockWidgetFeature.NoTab, True)
        dock.setWidget(widget)
        self._central_dock = dock
        self._central_area = self._manager.setCentralWidget(dock)

    def register(self, panel: Panel) -> None:
        if panel.panel_id in self._docks:
            raise ValueError(f"Panel {panel.panel_id!r} is already registered")
        dock = QtAds.CDockWidget(self._manager, panel.title)
        dock.setObjectName(panel.panel_id)
        dock.setWidget(panel.widget)
        self._sync_closable(dock, panel)
        dock.topLevelChanged.connect(partial(self._sync_closable, dock, panel))
        if panel.icon is not None:
            dock.setIcon(panel.icon)
        if panel.min_width > 0:
            panel.widget.setMinimumWidth(panel.min_width)
        if panel.min_height > 0:
            panel.widget.setMinimumHeight(panel.min_height)
        if panel.min_width > 0 or panel.min_height > 0:
            # By default QtAds sizes an area from the dock's own hint (a few
            # dozen pixels), so a separator drag or a split could squeeze the
            # panel below its declared minimum. Taking the minimum from the
            # content makes the splitter honour it.
            dock.setMinimumSizeHintMode(
                QtAds.CDockWidget.MinimumSizeHintFromContentMinimumSize
            )
        dock.viewToggled.connect(partial(self._emit_visibility, panel.panel_id))
        panel.widget.windowTitleChanged.connect(
            partial(self._on_panel_title_changed, dock)
        )
        self._panels[panel.panel_id] = panel
        self._docks[panel.panel_id] = dock

    def panel_ids(self) -> list[str]:
        return list(self._docks)

    def show_panel(self, panel_id: str) -> None:
        dock = self._dock(panel_id)
        if not self._is_placed(dock):
            self._manager.addDockWidget(
                QtAds.BottomDockWidgetArea, dock, self._require_central()
            )
        dock.toggleView(True)
        dock.setAsCurrentTab()

    def hide_panel(self, panel_id: str) -> None:
        dock = self._dock(panel_id)
        if self._is_placed(dock):
            dock.toggleView(False)

    def is_visible(self, panel_id: str) -> bool:
        dock = self._dock(panel_id)
        return self._is_placed(dock) and not dock.isClosed()

    def toggle_action(self, panel_id: str) -> QAction:
        """Checkable Window-menu action. Its text is the registration title and
        does not follow runtime title changes (only the dock's title does)."""
        action = self._dock(panel_id).toggleViewAction()
        action.setText(self._panels[panel_id].title)
        return action

    def apply_layout(self, spec: LayoutSpec) -> None:
        self._require_central()
        for dock in self._docks.values():
            if self._is_placed(dock):
                self._manager.removeDockWidget(dock)
        for placement in spec.placements:
            try:
                self._place(placement)
            except Exception:  # noqa: BLE001 - one bad panel must not stop the rest
                logger.exception(
                    "Could not place panel {!r} in layout {!r}",
                    placement.panel_id,
                    spec.name,
                )
        for panel_id in spec.active:
            dock = self._dock(panel_id)
            if self._is_placed(dock):
                dock.setAsCurrentTab()
            else:
                logger.warning("Active panel {!r} is not placed", panel_id)
        for panel_id, size in spec.sizes.items():
            try:
                self._apply_size(panel_id, size)
            except Exception:  # noqa: BLE001 - sizes are best effort
                logger.debug(
                    "Could not apply size {} to panel {!r}",
                    size,
                    panel_id,
                    exc_info=True,
                )
        self._sync_all_closable()
        self._tidy_splitters()

    def save_state(self) -> bytes:
        return bytes(self._manager.saveState())

    def restore_state(self, blob: bytes) -> bool:
        try:
            ok = self._manager.restoreState(QByteArray(blob))
        except Exception:  # noqa: BLE001 - a bad blob must never raise
            logger.warning("Dock layout could not be restored", exc_info=True)
            return False
        self._sync_all_closable()
        self._tidy_splitters()
        # Floating windows are shown after the state is applied; check next turn.
        self._schedule_rescue_floating()
        return bool(ok)

    # -- Test helpers (for tests and the docking package) ------------------

    def dock_widget(self, panel_id: str) -> QtAds.CDockWidget:
        return self._dock(panel_id)

    def area_widget(self, panel_id: str) -> QtAds.CDockAreaWidget | None:
        return self._dock(panel_id).dockAreaWidget()

    def panel_title(self, panel_id: str) -> str:
        return self._dock(panel_id).windowTitle()

    # -- internals ---------------------------------------------------------

    def rescue_floating(self) -> int:
        """Move floating panels that are off every screen back into view.

        Returns how many windows were moved.
        """
        try:
            return rescue_offscreen(self._manager.floatingWidgets())
        except RuntimeError:
            logger.debug("Floating panels are gone before they were rescued")
            return 0

    def _schedule_rescue_floating(self, *_args: object) -> None:
        QTimer.singleShot(0, self.rescue_floating)

    #: Thickness of a dock separator's grab handle, in pixels. Qt's stylesheet
    #: floor for a splitter handle is wider than a separator should look.
    HANDLE_THICKNESS = 3

    def _schedule_tidy_splitters(self) -> None:
        # The splitter is created and filled after the signal; tidy next turn.
        QTimer.singleShot(0, self._tidy_splitters)

    def _tidy_splitters(self) -> None:
        """Clamp every dock separator to :attr:`HANDLE_THICKNESS`.

        The handle's size comes from the global ``QSplitter::handle`` rule, which
        QSS cannot override for dock splitters only, so the widget is clamped.
        """
        try:
            for splitter in self._manager.findChildren(QSplitter):
                horizontal = splitter.orientation() == Qt.Orientation.Horizontal
                for index in range(1, splitter.count()):
                    handle = splitter.handle(index)
                    if horizontal:
                        handle.setMaximumWidth(self.HANDLE_THICKNESS)
                    else:
                        handle.setMaximumHeight(self.HANDLE_THICKNESS)
        except RuntimeError:
            logger.debug("Dock splitters are gone before they were tidied")

    def _sync_all_closable(self) -> None:
        """Re-read every panel's floating state.

        ``topLevelChanged`` does not fire when a layout or a saved state moves
        panels programmatically, so those paths resync explicitly.
        """
        for panel_id, dock in self._docks.items():
            self._sync_closable(dock, self._panels[panel_id])

    @staticmethod
    def _sync_closable(
        dock: QtAds.CDockWidget, panel: Panel, _floating: bool | None = None
    ) -> None:
        """Show the tab's close button only while the panel floats.

        A docked panel is closed from the Window menu (``toggleView`` ignores
        this feature), so the button would only add clutter next to its
        neighbours' tabs.
        """
        try:
            dock.setFeature(
                QtAds.CDockWidget.DockWidgetFeature.DockWidgetClosable,
                panel.closable and dock.isFloating(),
            )
        except RuntimeError:
            logger.debug(
                "Dock {!r} is gone before its close button was set", panel.panel_id
            )

    def _emit_visibility(self, panel_id: str, visible: bool) -> None:
        self.visibility_changed.emit(panel_id, bool(visible))

    def _on_panel_title_changed(self, dock: QtAds.CDockWidget, title: str) -> None:
        if not title:
            return
        try:
            dock.setWindowTitle(title)
        except RuntimeError:
            logger.debug("Dock already deleted; title {!r} not applied", title)

    def _dock(self, panel_id: str) -> QtAds.CDockWidget:
        try:
            return self._docks[panel_id]
        except KeyError:
            raise KeyError(
                f"Unknown dock panel {panel_id!r}; registered: {sorted(self._docks)}"
            ) from None

    @staticmethod
    def _is_placed(dock: QtAds.CDockWidget) -> bool:
        return dock.dockAreaWidget() is not None

    def _require_central(self) -> QtAds.CDockAreaWidget:
        if self._central_area is None:
            raise ValueError("set_central() must be called before docking panels")
        return self._central_area

    def _placed_area(self, panel_id: str | None) -> QtAds.CDockAreaWidget:
        dock = self._docks.get(panel_id) if panel_id is not None else None
        area = dock.dockAreaWidget() if dock is not None else None
        if area is None:
            raise ValueError(f"{panel_id!r} is not a placed panel")
        return area

    def _place(self, placement: Placement) -> None:
        dock = self._dock(placement.panel_id)
        if placement.area is Area.TAB:
            self._manager.addDockWidgetTabToArea(
                dock, self._placed_area(placement.relative_to)
            )
        elif placement.relative_to is None:
            self._manager.addDockWidget(_QT_AREAS[placement.area], dock)
        elif placement.relative_to == CENTRAL:
            self._manager.addDockWidget(
                _QT_AREAS[placement.area], dock, self._require_central()
            )
        else:
            self._manager.addDockWidget(
                _QT_AREAS[placement.area],
                dock,
                self._placed_area(placement.relative_to),
            )

    def _apply_size(self, panel_id: str, size: int) -> None:
        """Best effort: set the panel's area size along its splitter's axis.

        ``setSplitterSizes`` takes one entry per child of the area's splitter,
        so the current sizes are read, the panel's slot is replaced and the
        whole list is handed back.
        """
        area = self._dock(panel_id).dockAreaWidget()
        if area is None:
            return
        splitter = area.parentSplitter()
        index = splitter.indexOf(area)
        if index < 0:
            raise ValueError(f"Area of {panel_id!r} is not inside its splitter")
        sizes = splitter.sizes()
        sizes[index] = size
        self._manager.setSplitterSizes(area, sizes)
