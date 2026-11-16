"""AdsDockHost: QtAds placement, visibility, toggle actions and saved state."""

from collections.abc import Iterator
from dataclasses import dataclass

import pytest
from qtpy.QtCore import QPoint
from qtpy.QtWidgets import QApplication, QLabel, QMainWindow, QMdiArea, QTextEdit

from trigger_designer.qt.docking.ads_host import AdsDockHost
from trigger_designer.qt.docking.layouts import Area, LayoutSpec, Placement
from trigger_designer.qt.docking.panel import (
    CENTRAL,
    PANEL_CONFIG,
    PANEL_HISTORY,
    PANEL_LOGS,
    PANEL_PREVIEW,
    Panel,
)

_APP = QApplication.instance() or QApplication([])


def _flush() -> None:
    for _ in range(3):
        _APP.processEvents()


@dataclass
class Harness:
    window: QMainWindow
    host: AdsDockHost
    mdi: QMdiArea


def _panels() -> list[Panel]:
    return [
        Panel(PANEL_CONFIG, "Node Configuration", QLabel("config")),
        Panel(PANEL_LOGS, "Logs", QTextEdit("logs")),
        Panel(PANEL_PREVIEW, "Data Preview", QTextEdit("preview")),
        Panel(PANEL_HISTORY, "Run History", QTextEdit("history")),
    ]


def _full_layout() -> LayoutSpec:
    return LayoutSpec(
        name="test-full",
        placements=(
            Placement(PANEL_CONFIG, Area.LEFT),
            Placement(PANEL_LOGS, Area.BOTTOM, CENTRAL),
            Placement(PANEL_PREVIEW, Area.TAB, PANEL_LOGS),
            Placement(PANEL_HISTORY, Area.TAB, PANEL_LOGS),
        ),
        active=(PANEL_LOGS,),
    )


@pytest.fixture
def harness() -> Iterator[Harness]:
    window = QMainWindow()
    host = AdsDockHost(window)
    mdi = QMdiArea()
    mdi.setViewMode(QMdiArea.ViewMode.TabbedView)
    host.set_central(mdi)
    window.setCentralWidget(host.widget())
    for panel in _panels():
        host.register(panel)
    window.resize(1200, 800)
    window.show()
    _flush()
    yield Harness(window, host, mdi)
    window.hide()
    window.deleteLater()


def _global_top(widget) -> int:
    return widget.mapToGlobal(QPoint(0, 0)).y()


def test_layout_puts_config_full_height_and_logs_under_canvas(
    harness: Harness,
) -> None:
    host = harness.host
    host.apply_layout(_full_layout())
    _flush()

    config_area = host.area_widget(PANEL_CONFIG)
    logs_area = host.area_widget(PANEL_LOGS)
    assert config_area is not None and logs_area is not None
    assert config_area.height() > logs_area.height() * 1.5
    assert _global_top(logs_area) > _global_top(harness.mdi)


def test_tabbed_panels_share_the_logs_area(harness: Harness) -> None:
    host = harness.host
    host.apply_layout(_full_layout())
    _flush()

    logs_area = host.area_widget(PANEL_LOGS)
    assert host.area_widget(PANEL_PREVIEW) is logs_area
    assert host.area_widget(PANEL_HISTORY) is logs_area


def test_hide_and_show_report_visibility_changes(harness: Harness) -> None:
    host = harness.host
    events: list[tuple[str, bool]] = []
    host.visibility_changed.connect(lambda pid, vis: events.append((pid, vis)))
    host.apply_layout(_full_layout())
    _flush()
    assert host.is_visible(PANEL_LOGS)

    host.hide_panel(PANEL_LOGS)
    _flush()
    assert not host.is_visible(PANEL_LOGS)
    assert (PANEL_LOGS, False) in events

    host.show_panel(PANEL_LOGS)
    _flush()
    assert host.is_visible(PANEL_LOGS)
    assert (PANEL_LOGS, True) in events


def test_toggle_action_is_checkable_titled_and_toggles_panel(
    harness: Harness,
) -> None:
    host = harness.host
    host.apply_layout(_full_layout())
    _flush()

    action = host.toggle_action(PANEL_LOGS)
    assert action.isCheckable()
    assert action.text() == "Logs"
    assert action.isChecked()

    action.trigger()
    _flush()
    assert not host.is_visible(PANEL_LOGS)

    action.trigger()
    _flush()
    assert host.is_visible(PANEL_LOGS)


def test_save_and_restore_state_round_trip_keeps_visibility(
    harness: Harness,
) -> None:
    host = harness.host
    host.apply_layout(_full_layout())
    _flush()
    host.hide_panel(PANEL_PREVIEW)
    _flush()
    blob = host.save_state()
    assert isinstance(blob, bytes) and blob

    host.show_panel(PANEL_PREVIEW)
    _flush()
    assert host.is_visible(PANEL_PREVIEW)

    assert host.restore_state(blob) is True
    _flush()
    assert not host.is_visible(PANEL_PREVIEW)
    assert host.is_visible(PANEL_LOGS)


def test_restore_state_rejects_garbage_without_raising(harness: Harness) -> None:
    assert harness.host.restore_state(b"garbage") is False


def test_duplicate_register_raises_value_error(harness: Harness) -> None:
    duplicate = Panel(PANEL_CONFIG, "Again", QLabel("again"))
    with pytest.raises(ValueError):
        harness.host.register(duplicate)


def test_unknown_panel_id_raises_key_error(harness: Harness) -> None:
    with pytest.raises(KeyError):
        harness.host.is_visible("no-such-panel")


def test_apply_layout_before_set_central_raises_value_error() -> None:
    window = QMainWindow()
    host = AdsDockHost(window)
    host.register(Panel(PANEL_LOGS, "Logs", QTextEdit("logs")))
    with pytest.raises(ValueError):
        host.apply_layout(_full_layout())


def test_show_panel_on_never_placed_panel_makes_it_visible(
    harness: Harness,
) -> None:
    host = harness.host
    host.apply_layout(
        LayoutSpec(
            name="without-history",
            placements=(
                Placement(PANEL_CONFIG, Area.LEFT),
                Placement(PANEL_LOGS, Area.BOTTOM, CENTRAL),
            ),
        )
    )
    _flush()
    assert not host.is_visible(PANEL_HISTORY)

    host.show_panel(PANEL_HISTORY)
    _flush()
    assert host.is_visible(PANEL_HISTORY)


def test_runtime_title_change_updates_dock_but_not_toggle_action(
    harness: Harness,
) -> None:
    host = harness.host
    host.apply_layout(_full_layout())
    _flush()
    panel_widget = host.dock_widget(PANEL_CONFIG).widget()

    panel_widget.setWindowTitle("Node Configuration (Join)")
    _flush()

    assert host.panel_title(PANEL_CONFIG) == "Node Configuration (Join)"
    assert host.toggle_action(PANEL_CONFIG).text() == "Node Configuration"


def test_empty_runtime_title_keeps_previous_title(harness: Harness) -> None:
    host = harness.host
    host.apply_layout(_full_layout())
    _flush()
    panel_widget = host.dock_widget(PANEL_CONFIG).widget()

    panel_widget.setWindowTitle("Node Configuration (Join)")
    _flush()
    panel_widget.setWindowTitle("")
    _flush()

    assert host.panel_title(PANEL_CONFIG) == "Node Configuration (Join)"


def test_panel_title_unknown_id_raises_key_error(harness: Harness) -> None:
    with pytest.raises(KeyError):
        harness.host.panel_title("no-such-panel")


# -- chrome: close buttons and tab titles ------------------------------------


def _closable(host: AdsDockHost, panel_id: str) -> bool:
    import PySide6QtAds as QtAds

    dock = host.dock_widget(panel_id)
    return bool(
        dock.features() & QtAds.CDockWidget.DockWidgetFeature.DockWidgetClosable
    )


def test_docked_panels_have_no_close_button(harness: Harness) -> None:
    harness.host.apply_layout(_full_layout())
    _flush()
    for panel_id in (PANEL_CONFIG, PANEL_LOGS, PANEL_PREVIEW, PANEL_HISTORY):
        assert not _closable(harness.host, panel_id)


def test_floating_panel_gets_its_close_button_and_loses_it_when_docked(
    harness: Harness,
) -> None:
    harness.host.apply_layout(_full_layout())
    _flush()
    dock = harness.host.dock_widget(PANEL_PREVIEW)
    dock.setFloating()
    _flush()
    assert dock.isFloating()
    assert _closable(harness.host, PANEL_PREVIEW)
    # Docking it back takes the button away again.
    harness.host.apply_layout(_full_layout())
    _flush()
    assert not _closable(harness.host, PANEL_PREVIEW)


def test_non_closable_panel_never_gets_a_close_button(harness: Harness) -> None:
    host = harness.host
    sticky = Panel("sticky", "Sticky", QLabel("s"), closable=False)
    host.register(sticky)
    host.show_panel("sticky")
    host.dock_widget("sticky").setFloating()
    _flush()
    assert not _closable(host, "sticky")


def test_tab_titles_are_never_elided(harness: Harness) -> None:
    harness.host.apply_layout(_full_layout())
    _flush()
    for panel_id in (PANEL_LOGS, PANEL_PREVIEW, PANEL_HISTORY):
        assert not harness.host.dock_widget(panel_id).tabWidget().isTitleElided()


def test_area_close_button_flag_is_off() -> None:
    import PySide6QtAds as QtAds

    window = QMainWindow()
    AdsDockHost(window)
    assert not QtAds.CDockManager.testConfigFlag(
        QtAds.CDockManager.DockAreaHasCloseButton
    )
    assert QtAds.CDockManager.testConfigFlag(QtAds.CDockManager.DisableTabTextEliding)


def test_dock_separators_are_thin(harness: Harness) -> None:
    from qtpy.QtCore import Qt
    from qtpy.QtWidgets import QSplitter

    harness.host.apply_layout(_full_layout())
    _flush()
    splitters = harness.host.widget().findChildren(QSplitter)
    assert splitters
    for splitter in splitters:
        for index in range(1, splitter.count()):
            handle = splitter.handle(index)
            thickness = (
                handle.width()
                if splitter.orientation() == Qt.Orientation.Horizontal
                else handle.height()
            )
            assert thickness <= AdsDockHost.HANDLE_THICKNESS


# -- minimum size and remembered sizes ---------------------------------------


def _with_min_width(harness: Harness, panel_id: str, minimum: int) -> AdsDockHost:
    """A fresh host whose ``panel_id`` panel declares ``minimum`` px of width."""
    window = QMainWindow()
    host = AdsDockHost(window)
    host.set_central(QMdiArea())
    window.setCentralWidget(host.widget())
    for panel in _panels():
        if panel.panel_id == panel_id:
            panel.min_width = minimum
        host.register(panel)
    window.resize(1200, 800)
    window.show()
    host.apply_layout(_full_layout())
    _flush()
    harness.window = window  # keep the window alive for the test's duration
    return host


def test_panel_min_width_is_enforced_by_the_splitter(harness: Harness) -> None:
    host = _with_min_width(harness, PANEL_CONFIG, 300)
    area = host.area_widget(PANEL_CONFIG)
    assert area is not None
    assert area.minimumSizeHint().width() >= 300
    splitter = area.parentSplitter()
    splitter.setSizes([40, splitter.width() - 40])
    _flush()
    assert area.width() >= 300


def test_panel_without_a_minimum_can_be_squeezed(harness: Harness) -> None:
    host = _with_min_width(harness, PANEL_CONFIG, 0)
    area = host.area_widget(PANEL_CONFIG)
    assert area is not None
    splitter = area.parentSplitter()
    splitter.setSizes([40, splitter.width() - 40])
    _flush()
    assert area.width() < 300


def test_dragged_panel_sizes_survive_save_and_restore(harness: Harness) -> None:
    host = harness.host
    host.apply_layout(_full_layout())
    _flush()
    config_area = host.area_widget(PANEL_CONFIG)
    logs_area = host.area_widget(PANEL_LOGS)
    assert config_area is not None and logs_area is not None
    column = config_area.parentSplitter()
    column.setSizes([520, column.width() - 520])
    rows = logs_area.parentSplitter()
    rows.setSizes([rows.height() - 300, 300])
    _flush()
    saved_width = config_area.width()
    saved_height = logs_area.height()
    blob = host.save_state()

    window = QMainWindow()
    other = AdsDockHost(window)
    other.set_central(QMdiArea())
    window.setCentralWidget(other.widget())
    for panel in _panels():
        other.register(panel)
    window.resize(1200, 800)
    window.show()
    other.apply_layout(_full_layout())  # the default goes in first, as at startup
    _flush()
    assert other.restore_state(blob)
    _flush()
    restored_config = other.area_widget(PANEL_CONFIG)
    restored_logs = other.area_widget(PANEL_LOGS)
    assert restored_config is not None and restored_logs is not None
    assert abs(restored_config.width() - saved_width) <= 2
    assert abs(restored_logs.height() - saved_height) <= 2
    window.hide()


# -- floating panels that end up off screen ----------------------------------


def test_offscreen_floating_panel_is_pulled_back(harness: Harness) -> None:
    from qtpy.QtGui import QGuiApplication

    from trigger_designer.qt.docking.screen_guard import (
        available_screen_rects,
        is_reachable,
    )

    host = harness.host
    host.apply_layout(_full_layout())
    _flush()
    dock = host.dock_widget(PANEL_PREVIEW)
    dock.setFloating()
    _flush()
    container = dock.floatingDockContainer()
    assert container is not None
    container.move(-5000, -5000)
    _flush()
    screens = available_screen_rects()
    assert QGuiApplication.screens() and screens
    assert not is_reachable(container.frameGeometry(), screens)

    assert host.rescue_floating() >= 1
    _flush()
    assert is_reachable(container.frameGeometry(), screens)


def test_rescue_leaves_docked_and_visible_panels_alone(harness: Harness) -> None:
    host = harness.host
    host.apply_layout(_full_layout())
    _flush()
    assert host.rescue_floating() == 0
