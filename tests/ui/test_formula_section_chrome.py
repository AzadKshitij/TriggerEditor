"""Formula section chrome: the resize grip and the divider under both engines.

The classic themes paint these through the application stylesheet. The
Qlementine themes apply no stylesheet, so the widgets paint themselves.
"""

from __future__ import annotations

import pytest
from qtpy.QtCore import QEvent, QPoint, QPointF
from qtpy.QtGui import QColor, QCursor, QEnterEvent, QFont, QPalette
from qtpy.QtWidgets import QApplication, QWidget

pytest.importorskip("PySide6Qlementine")

from trigger_designer.qt import theme_manager as theme_manager_module
from trigger_designer.qt.theme_manager import ThemeManager
from trigger_designer.qt.widgets.nodes.Preparation.formula import (
    _ResizeGrip,
    _Separator,
)


class _Content:
    """Stands in for the formula content; the grip only commits heights to it."""

    def _commit_height(self, _index: int, _height: int) -> None:
        pass


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


def _shown(qapp: QApplication, qtbot, widget: QWidget) -> QWidget:
    qtbot.addWidget(widget)
    widget.setFixedWidth(200)
    # Offscreen, a window shown under the pointer starts out hovered.
    widget.move(QCursor.pos() + QPoint(100, 100))
    widget.show()
    _flush(qapp)
    return widget


def _pixel(widget: QWidget, x: int, y: int) -> str:
    return widget.grab().toImage().pixelColor(x, y).name()


def _centre(widget: QWidget) -> str:
    return _pixel(widget, widget.width() // 2, widget.height() // 2)


def _token(live: ThemeManager, theme_id: str, token: str) -> str:
    return QColor(live.theme(theme_id).tokens[token]).name()


def test_the_classic_grip_is_a_four_pixel_bar_painted_by_the_stylesheet(
    live: ThemeManager, qapp: QApplication, qtbot
) -> None:
    live.apply("dark", persist=False)
    grip = _shown(qapp, qtbot, _ResizeGrip(_Content(), 0, QWidget()))

    assert grip.height() == 4
    assert _centre(grip) == _token(live, "dark", "card_border")


def test_the_qlementine_grip_is_a_ten_pixel_hit_area_with_a_pill(
    live: ThemeManager, qapp: QApplication, qtbot
) -> None:
    live.apply("qlementine-dark", persist=False)
    grip = _shown(qapp, qtbot, _ResizeGrip(_Content(), 0, QWidget()))
    inactive = _token(live, "qlementine-dark", "text_inactive")

    assert grip.height() == 10
    assert _centre(grip) == inactive
    assert _pixel(grip, 2, grip.height() // 2) != inactive


def test_the_qlementine_pill_takes_the_secondary_colour_while_hovered(
    live: ThemeManager, qapp: QApplication, qtbot
) -> None:
    live.apply("qlementine-dark", persist=False)
    grip = _shown(qapp, qtbot, _ResizeGrip(_Content(), 0, QWidget()))
    centre = QPointF(grip.width() / 2, grip.height() / 2)

    grip.enterEvent(QEnterEvent(centre, centre, centre))
    assert _centre(grip) == _token(live, "qlementine-dark", "text_secondary")

    grip.leaveEvent(QEvent(QEvent.Type.Leave))
    assert _centre(grip) == _token(live, "qlementine-dark", "text_inactive")


def test_the_grip_height_follows_a_live_switch_between_engines(
    live: ThemeManager, qapp: QApplication, qtbot
) -> None:
    live.apply("dark", persist=False)
    grip = _shown(qapp, qtbot, _ResizeGrip(_Content(), 0, QWidget()))
    assert grip.height() == 4

    live.apply("qlementine-dark", persist=False)
    _flush(qapp)
    assert grip.height() == 10

    live.apply("dark", persist=False)
    _flush(qapp)
    assert grip.height() == 4


def test_the_classic_divider_is_painted_by_the_stylesheet(
    live: ThemeManager, qapp: QApplication, qtbot
) -> None:
    live.apply("dark", persist=False)
    divider = _shown(qapp, qtbot, _Separator())

    assert divider.height() == 1
    assert _centre(divider) == _token(live, "dark", "card_border")


def test_the_qlementine_divider_is_a_one_pixel_card_border_line(
    live: ThemeManager, qapp: QApplication, qtbot
) -> None:
    live.apply("qlementine-dark", persist=False)
    divider = _shown(qapp, qtbot, _Separator())

    assert divider.height() == 1
    assert _centre(divider) == _token(live, "qlementine-dark", "card_border")
