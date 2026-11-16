"""The ``qlementine`` theme engine against the real Qlementine QStyle.

Qlementine cannot run under an application stylesheet (oclero/qlementine#155,
#125) and must not be destroyed while widgets point at it (#133); the tests
pin those rules, then the layout fixes the style needed in this app.
"""

from __future__ import annotations

import pytest
import shiboken6
from qtpy.QtGui import QFont, QPalette
from qtpy.QtWidgets import (
    QApplication,
    QComboBox,
    QListWidget,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

pytest.importorskip("PySide6Qlementine")

from trigger_designer.core.node_configuration import NodeTypes
from trigger_designer.qt import theme_manager as theme_manager_module
from trigger_designer.qt.qlementine_style import TAB_HEIGHT
from trigger_designer.qt.theme_manager import ThemeManager

QLEMENTINE_STYLE = "QlementineStyle"


def _flush(app: QApplication, rounds: int = 20) -> None:
    for _ in range(rounds):
        app.processEvents()


@pytest.fixture()
def live(clean_preferences, tmp_path, qapp, monkeypatch):
    """A ThemeManager bound to the real application, restored afterwards."""
    sheet = qapp.styleSheet()
    palette = QPalette(qapp.palette())
    font = QFont(qapp.font())
    manager = ThemeManager(
        preferences=clean_preferences, themes_dir=tmp_path / "themes", app=qapp
    )
    monkeypatch.setattr(theme_manager_module, "_instance", manager)
    yield manager
    qapp.setStyleSheet("")
    manager._qlementine.uninstall(qapp)
    qapp.setStyleSheet(sheet)
    qapp.setPalette(palette)
    qapp.setFont(font)


def test_applying_the_theme_makes_qlementine_the_style_with_no_stylesheet(
    live: ThemeManager, qapp: QApplication
) -> None:
    live.apply("dark", persist=False)
    assert qapp.styleSheet() != ""

    live.apply("qlementine-dark", persist=False)

    assert qapp.style().objectName() == QLEMENTINE_STYLE
    assert qapp.styleSheet() == ""
    assert live._qlementine.active


def test_switching_back_restores_the_stock_style_and_the_stylesheet(
    live: ThemeManager, qapp: QApplication
) -> None:
    live.apply("qlementine-dark", persist=False)
    live.apply("dark", persist=False)

    assert not live._qlementine.active
    assert qapp.style().objectName() != QLEMENTINE_STYLE
    assert qapp.styleSheet() == live.stylesheet(live.active_theme())


def test_the_style_object_outlives_a_switch_back(
    live: ThemeManager, qapp: QApplication
) -> None:
    """Delegates keep pointers to it; Qt must not delete it (qlementine#133)."""
    live.apply("qlementine-dark", persist=False)
    style = live._qlementine._style

    live.apply("dark", persist=False)
    assert shiboken6.isValid(style)

    live.apply("qlementine-light", persist=False)
    assert live._qlementine._style is style
    assert qapp.style().objectName() == QLEMENTINE_STYLE


def test_the_palette_comes_from_the_theme_tokens(
    live: ThemeManager, qapp: QApplication
) -> None:
    live.apply("qlementine-dark", persist=False)
    dark = qapp.palette().window().color().name()
    live.apply("qlementine-light", persist=False)
    light = qapp.palette().window().color().name()

    assert dark == live.theme("dark").tokens["background_primary"]
    assert light == live.theme("light").tokens["background_primary"]
    assert dark != light


def test_the_accent_preference_reaches_qlementine(
    live: ThemeManager, qapp: QApplication
) -> None:
    live.apply("qlementine-dark", persist=False)
    live.set_accent("#ff8800")
    assert qapp.palette().highlight().color().name() == "#ff8800"


def test_a_combo_box_sizes_itself_under_qlementine(
    live: ThemeManager, qapp: QApplication
) -> None:
    """Any application stylesheet used to overflow the stack in ``sizeHint``."""
    live.apply("qlementine-dark", persist=False)
    combo = QComboBox()
    combo.addItem("column")

    assert combo.sizeHint().width() > 0
    assert combo.minimumSizeHint().width() > 0


def test_live_switching_with_widgets_open_does_not_crash(
    live: ThemeManager, qapp: QApplication
) -> None:
    host = QWidget()
    layout = QVBoxLayout(host)
    combo = QComboBox()
    combo.addItems(["a", "b"])
    listing = QListWidget()
    listing.addItems(["x", "y"])
    layout.addWidget(combo)
    layout.addWidget(listing)
    host.show()

    for theme_id in ("dark", "qlementine-dark", "light", "qlementine-light", "dark"):
        live.apply(theme_id, persist=False)
        _flush(qapp, 5)
        assert combo.sizeHint().width() > 0
        assert listing.sizeHint().width() > 0
    host.close()


def test_the_font_size_preference_wins_over_qlementines_font(
    live: ThemeManager, qapp: QApplication
) -> None:
    live.set_font_size(11)

    live.apply("qlementine-dark", persist=False)
    _flush(qapp, 5)

    assert qapp.font().pointSizeF() == 11.0


def test_the_original_font_comes_back_with_the_classic_theme(
    live: ThemeManager, qapp: QApplication
) -> None:
    live.apply("dark", persist=False)
    family = qapp.font().family()

    live.apply("qlementine-dark", persist=False)
    live.apply("dark", persist=False)
    _flush(qapp, 5)

    assert qapp.font().family() == family


def test_a_missing_library_keeps_the_classic_look(
    live: ThemeManager, qapp: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    from trigger_designer.qt import qlementine_style

    monkeypatch.setattr(qlementine_style, "_q", None)
    live.invalidate()

    live.apply("qlementine-dark", persist=False)

    assert not live._qlementine.active
    assert qapp.style().objectName() != QLEMENTINE_STYLE
    assert qapp.styleSheet() != ""


# -- layout fixes the style needed -------------------------------------------


def test_node_palette_items_fill_their_cells(
    live: ThemeManager, qapp: QApplication
) -> None:
    """The default delegate sized an item widget from an empty text rectangle."""
    from trigger_designer.qt.widgets.node_drag_listbox import QTRDragListbox

    live.apply("qlementine-dark", persist=False)
    listing = QTRDragListbox(node_type=next(iter(NodeTypes)))
    listing.resize(600, 90)
    listing.show()
    _flush(qapp)

    item = listing.item(0)
    widget = listing.itemWidget(item)
    assert widget.geometry() == listing.visualItemRect(item)
    assert widget.width() > 0 and widget.height() > 0


@pytest.mark.parametrize("theme_id", ["dark", "qlementine-dark", "qlementine-light"])
def test_node_palette_dock_always_shows_a_whole_row(
    live: ThemeManager, qapp: QApplication, theme_id: str
) -> None:
    from trigger_designer.qt.docks.nodes_list import BASE_HEIGHT, NodesDock

    live.apply(theme_id, persist=False)
    dock = NodesDock()
    dock.resize(1200, 200)
    dock.show()
    _flush(qapp)

    visible = [lb for lb in dock._lists if lb.isVisible()]
    assert visible
    for listing in visible:
        assert listing.viewport().height() >= listing.item(0).sizeHint().height()
    assert dock._tab_widget.maximumHeight() >= BASE_HEIGHT
    dock.close()


def test_node_palette_dock_keeps_the_compact_height_in_the_classic_theme(
    live: ThemeManager, qapp: QApplication
) -> None:
    from trigger_designer.qt.docks.nodes_list import BASE_HEIGHT, NodesDock

    live.apply("dark", persist=False)
    dock = NodesDock()
    dock.resize(1200, 200)
    dock.show()
    _flush(qapp)

    assert dock._tab_widget.maximumHeight() == BASE_HEIGHT
    dock.close()


def test_node_palette_dock_shrinks_back_after_leaving_qlementine(
    live: ThemeManager, qapp: QApplication
) -> None:
    from trigger_designer.qt.docks.nodes_list import BASE_HEIGHT, NodesDock

    live.apply("qlementine-dark", persist=False)
    dock = NodesDock()
    dock.resize(1200, 200)
    dock.show()
    _flush(qapp)
    assert dock._tab_widget.maximumHeight() > BASE_HEIGHT

    live.apply("dark", persist=False)
    _flush(qapp)

    assert dock._tab_widget.maximumHeight() == BASE_HEIGHT
    dock.close()


@pytest.mark.parametrize("theme_id", ["dark", "qlementine-dark", "qlementine-light"])
def test_every_menu_shares_one_row_in_the_window_chrome(
    live: ThemeManager, qapp: QApplication, theme_id: str
) -> None:
    from trigger_designer.qt.main_window import TriggerWindow

    live.apply(theme_id, persist=False)
    window = TriggerWindow()
    window.resize(1500, 900)
    window.show()
    _flush(qapp, 30)

    bar = window.menuBar()
    rows = {
        bar.actionGeometry(action).y()
        for action in bar.actions()
        if bar.actionGeometry(action).width() > 0
    }
    assert len(rows) == 1
    window.hide()
    window.deleteLater()


def test_the_menu_bar_survives_a_live_switch_to_qlementine(
    live: ThemeManager, qapp: QApplication
) -> None:
    from trigger_designer.qt.main_window import TriggerWindow

    live.apply("dark", persist=False)
    window = TriggerWindow()
    window.resize(1500, 900)
    window.show()
    _flush(qapp, 30)

    live.apply("qlementine-dark", persist=False)
    _flush(qapp, 30)

    bar = window.menuBar()
    rows = {
        bar.actionGeometry(action).y()
        for action in bar.actions()
        if bar.actionGeometry(action).width() > 0
    }
    assert len(rows) == 1
    window.hide()
    window.deleteLater()


# -- item-view cell widgets ---------------------------------------------------


@pytest.mark.parametrize("theme_id", ["dark", "qlementine-dark"])
def test_table_cell_widgets_fill_their_cells(
    live: ThemeManager, qapp: QApplication, theme_id: str
) -> None:
    """Index widgets in a plain table take their whole cell."""
    from trigger_designer.qt.widgets.common.config_widgets import FillCellDelegate

    # Built under the theme under test, as a dock builds its cells.
    live.apply(theme_id, persist=False)
    table = QTableWidget(4, 3)
    table.verticalHeader().setDefaultSectionSize(22)
    for row in range(table.rowCount()):
        # Built the way the Aggregate node builds its Action combos (groupby.py).
        combo = QComboBox()
        combo.setObjectName("CellCombo")
        combo.setMinimumHeight(18)
        combo.addItem("Sum")
        table.setCellWidget(row, 1, combo)
    table.setItemDelegateForColumn(1, FillCellDelegate(table))

    table.resize(600, 200)
    table.show()
    _flush(qapp)

    for row in range(table.rowCount()):
        widget = table.cellWidget(row, 1)
        cell = table.visualRect(table.model().index(row, 1))
        assert widget.width() > 0
        assert cell.contains(widget.geometry())
    table.close()


@pytest.mark.parametrize("theme_id", ["dark", "qlementine-dark"])
def test_a_cell_combo_measures_itself_at_its_real_width(
    live: ThemeManager, qapp: QApplication, theme_id: str
) -> None:
    """A stale 640 px size hint used to stretch the popup over the whole table."""
    from trigger_designer.qt.widgets.common.config_widgets import (
        FillCellDelegate,
        NoWheelComboBox,
    )

    live.apply(theme_id, persist=False)
    table = QTableWidget()
    table.setColumnCount(3)
    table.verticalHeader().setDefaultSectionSize(22)
    table.setColumnWidth(1, 120)
    table.setItemDelegateForColumn(1, FillCellDelegate(table))
    for row in range(3):
        table.insertRow(row)
        # Built the way the Aggregate node builds its Action combos (groupby.py).
        combo = NoWheelComboBox()
        combo.setObjectName("CellCombo")
        combo.setMinimumHeight(18)
        for action in ("GroupBy", "First", "Last", "Sum"):
            combo.addItem(action, action)
        table.setCellWidget(row, 1, combo)
        # Row sizing reads the hint while the combo still has its default size.
        combo.sizeHint()
    table.resize(700, 200)
    table.show()
    _flush(qapp)

    combo = table.cellWidget(1, 1)
    hint, width = combo.sizeHint().width(), combo.width()
    combo.showPopup()
    _flush(qapp, 10)
    popup_width = combo.view().window().width()
    combo.hidePopup()
    table.close()

    assert hint <= width + 8
    assert popup_width < width + 80


def test_aggregate_action_cells_fill_their_cells(
    live: ThemeManager, qapp: QApplication, qtbot
) -> None:
    """The real Aggregate node puts its delegate on the Action column."""
    from tests.ui.test_aggregate_dock import _add_field, _node
    from trigger_designer.qt.widgets.common.config_widgets import FillCellDelegate

    live.apply("qlementine-dark", persist=False)
    _window, _source, node, dock = _node(qtbot)
    content = node.content
    _add_field(content, "g")
    _add_field(content, "x")
    table = content.actions_table
    assert table.rowCount() == 2
    assert isinstance(table.itemDelegateForColumn(1), FillCellDelegate)

    dock.resize(800, 600)
    dock.show()
    _flush(qapp)

    for row in range(table.rowCount()):
        widget = table.cellWidget(row, 1)
        cell = table.visualRect(table.model().index(row, 1))
        assert widget.width() > 0
        assert cell.contains(widget.geometry())


# -- active tab mark ----------------------------------------------------------


def _tab_widget(qapp: QApplication, names=("Input", "Prep", "Join")):
    from qtpy.QtWidgets import QLabel, QTabWidget

    tabs = QTabWidget()
    for name in names:
        tabs.addTab(QLabel(name), name)
    tabs.resize(420, 120)
    tabs.show()
    _flush(qapp)
    return tabs


def _mark_of(bar):
    from trigger_designer.qt.tab_indicator import _ActiveTabMark

    return next((c for c in bar.children() if isinstance(c, _ActiveTabMark)), None)


def _line_colour(bar, index: int) -> str:
    """Colour of the bottom pixel row of tab ``index``, where the accent line is."""
    rect = bar.tabRect(index)
    return bar.grab().toImage().pixelColor(rect.center().x(), rect.bottom()).name()


def test_the_active_tab_carries_an_accent_line_under_qlementine(
    live: ThemeManager, qapp: QApplication
) -> None:
    live.apply("qlementine-dark", persist=False)
    tabs = _tab_widget(qapp)
    bar = tabs.tabBar()
    accent = qapp.palette().highlight().color().name()

    assert _line_colour(bar, 0) == accent
    assert _line_colour(bar, 1) != accent

    tabs.setCurrentIndex(2)
    _flush(qapp)
    assert _line_colour(bar, 2) == accent
    assert _line_colour(bar, 0) != accent
    tabs.close()


def test_a_tab_bar_that_exists_before_the_theme_is_marked_too(
    live: ThemeManager, qapp: QApplication
) -> None:
    live.apply("dark", persist=False)
    tabs = _tab_widget(qapp)
    assert _mark_of(tabs.tabBar()) is None

    live.apply("qlementine-dark", persist=False)
    _flush(qapp)

    assert _mark_of(tabs.tabBar()) is not None
    assert _line_colour(tabs.tabBar(), 0) == qapp.palette().highlight().color().name()
    tabs.close()


def test_the_mark_paints_nothing_under_a_classic_theme(
    live: ThemeManager, qapp: QApplication
) -> None:
    live.apply("qlementine-dark", persist=False)
    tabs = _tab_widget(qapp)
    live.apply("dark", persist=False)
    _flush(qapp)
    bar = tabs.tabBar()
    mark = _mark_of(bar)
    assert mark is not None

    with_mark = bar.grab().toImage()
    mark.hide()
    without_mark = bar.grab().toImage()
    tabs.close()

    assert with_mark == without_mark


def test_the_tab_bar_band_is_the_window_colour(
    live: ThemeManager, qapp: QApplication
) -> None:
    """The workflow tab strip must not get a background of its own."""
    live.apply("qlementine-dark", persist=False)
    tabs = _tab_widget(qapp)
    bar = tabs.tabBar()
    window = qapp.palette().window().color().name()
    # Right of the last tab, still inside the tab widget's header row.
    probe_x = bar.tabRect(bar.count() - 1).right() + 40
    pixel = tabs.grab().toImage().pixelColor(probe_x, 6).name()
    tabs.close()

    assert pixel == window


@pytest.mark.parametrize("theme_id", ["qlementine-dark", "qlementine-light"])
def test_a_qlementine_tab_is_compact_in_both_spacings(
    live: ThemeManager, qapp: QApplication, theme_id: str
) -> None:
    """Dark spaces by 4 px and light by 8; the tab is the same height in both."""
    live.apply(theme_id, persist=False)
    tabs = _tab_widget(qapp)

    assert tabs.tabBar().sizeHint().height() == TAB_HEIGHT
    tabs.close()


def test_menu_bar_items_are_wider_than_qlementines_default(
    live: ThemeManager, qapp: QApplication
) -> None:
    from qtpy.QtWidgets import QMenuBar

    from trigger_designer.qt.qlementine_style import MENU_BAR_ITEM_EXTRA_W

    live.apply("qlementine-dark", persist=False)
    bar = QMenuBar()
    bar.addMenu("File")
    bar.show()
    _flush(qapp)
    wide = bar.actionGeometry(bar.actions()[0]).width()

    style = qapp.style()
    style.menu_item_extra_w = 0
    bar.resize(bar.width() + 1, bar.height())
    bar.updateGeometry()
    _flush(qapp)
    plain = bar.actionGeometry(bar.actions()[0]).width()
    style.menu_item_extra_w = MENU_BAR_ITEM_EXTRA_W
    bar.close()

    assert wide - plain == MENU_BAR_ITEM_EXTRA_W


def _drag_selection(qapp: QApplication, qtbot):
    """A canvas with a drag-selection box held open; returns (view, box rect)."""
    from nodeeditor.node_scene import Scene
    from qtpy.QtCore import QPoint, Qt
    from qtpy.QtTest import QTest

    from trigger_designer.qt.canvas_view import TriggerGraphicsView

    view = TriggerGraphicsView(Scene().grScene)
    qtbot.addWidget(view)
    view.resize(300, 200)
    view.show()
    _flush(qapp)
    viewport = view.viewport()
    QTest.mousePress(
        viewport,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
        QPoint(40, 40),
    )
    QTest.mouseMove(viewport, QPoint(160, 120))
    _flush(qapp)
    return view, QPoint(100, 80)


def test_the_selection_box_is_drawn_under_qlementine(
    live: ThemeManager, qapp: QApplication, qtbot
) -> None:
    live.apply("qlementine-dark", persist=False)
    view, inside = _drag_selection(qapp, qtbot)

    # Inside the box the canvas is tinted with the accent; outside it is not.
    box = view.viewport().grab().toImage().pixelColor(inside)
    outside = view.viewport().grab().toImage().pixelColor(250, 180)
    assert box != outside
    assert box.blue() > outside.blue()


def test_the_selection_box_is_left_to_qt_under_a_classic_theme(
    live: ThemeManager, qapp: QApplication, qtbot
) -> None:
    live.apply("dark", persist=False)
    view, _ = _drag_selection(qapp, qtbot)

    assert view._band.isEmpty() is False  # tracked, but drawForeground skips it
