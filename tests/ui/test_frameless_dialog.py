"""FramelessDialog: the app's own title row on every dialog (GitHub issue #45).

Offscreen, so the Qt path runs (no Win32 caption); the Windows-only geometry is
covered by ``tests/unit/test_win_caption_hit_test.py``.
"""

import pytest
from qtpy.QtCore import QPoint, Qt, QTimer
from qtpy.QtTest import QTest
from qtpy.QtWidgets import QDialog, QLabel, QVBoxLayout

from trigger_designer.qt.widgets.common.frameless_dialog import (
    DialogChrome,
    FramelessDialog,
)
from trigger_designer.qt.widgets.common.window_chrome import CHROME_H


class _Sample(FramelessDialog):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.setWindowTitle("Sample title")
        layout = QVBoxLayout(self)
        self.body = QLabel("body", self)
        layout.addWidget(self.body)


@pytest.fixture
def dialog(qtbot):
    dlg = _Sample()
    qtbot.addWidget(dlg)
    dlg.resize(360, 160)
    dlg.show()
    qtbot.waitExposed(dlg)
    return dlg


def test_dialog_is_frameless_and_flagged_for_qss(dialog) -> None:
    assert dialog.windowFlags() & Qt.WindowType.FramelessWindowHint
    assert dialog.property("frameless") is True
    assert isinstance(dialog.chrome, DialogChrome)
    assert dialog.chrome.objectName() == "DialogChrome"
    assert dialog.chrome.height() == CHROME_H


def test_subclass_layout_starts_below_the_title_row(dialog) -> None:
    top = dialog.body.mapTo(dialog, dialog.body.rect().topLeft()).y()
    assert top >= CHROME_H


def test_chrome_spans_the_dialog_and_sits_on_top(dialog) -> None:
    assert dialog.chrome.geometry().x() == 0
    assert dialog.chrome.geometry().y() == 0
    assert dialog.chrome.width() == dialog.width()
    dialog.resize(dialog.width() + 80, dialog.height())
    assert dialog.chrome.width() == dialog.width()


def test_title_is_shown_at_once_and_follows_changes(dialog) -> None:
    label = dialog.chrome.findChild(QLabel, "DialogChromeTitle")
    assert label.text() == "Sample title"
    dialog.setWindowTitle("Renamed")
    assert label.text() == "Renamed"


def test_close_button_rejects_the_dialog(qtbot) -> None:
    dlg = _Sample()
    qtbot.addWidget(dlg)
    QTimer.singleShot(
        50,
        lambda: QTest.mouseClick(dlg.chrome.close_button(), Qt.MouseButton.LeftButton),
    )
    assert dlg.exec() == QDialog.DialogCode.Rejected


def test_close_button_is_never_the_default_or_focusable(dialog) -> None:
    button = dialog.chrome.close_button()
    assert not button.autoDefault()
    assert not button.isDefault()
    assert button.focusPolicy() == Qt.FocusPolicy.NoFocus


def test_escape_rejects_the_dialog(qtbot) -> None:
    dlg = _Sample()
    qtbot.addWidget(dlg)
    QTimer.singleShot(50, lambda: QTest.keyClick(dlg, Qt.Key.Key_Escape))
    assert dlg.exec() == QDialog.DialogCode.Rejected


def test_only_a_close_button_no_min_or_max(dialog) -> None:
    names = [
        b.toolTip()
        for b in dialog.chrome.findChildren(type(dialog.chrome.close_button()))
    ]
    assert names == ["Close"]


def test_resizable_dialog_gets_the_edge_filter_fixed_one_does_not(qtbot) -> None:
    resizable = _Sample()
    fixed = _Sample(resizable=False)
    qtbot.addWidget(resizable)
    qtbot.addWidget(fixed)
    assert resizable.is_resizable() and resizable.resizer is not None
    assert not fixed.is_resizable() and fixed.resizer is None


def test_caption_regions_leave_the_close_button_as_client_area(dialog) -> None:
    regions = dialog.chrome.caption_regions()
    button = dialog.chrome.close_button().geometry()
    assert regions.buttons == {}
    assert regions.menu.size() == button.size()
    assert regions.menu.topLeft() == button.topLeft()
    assert regions.row.height() == CHROME_H


def test_drag_falls_back_to_a_manual_move_when_the_platform_refuses(dialog) -> None:
    chrome = dialog.chrome
    handle = dialog.windowHandle()
    assert handle is not None
    handle.startSystemMove = lambda: False  # Wayland-style refusal
    start = dialog.pos()
    QTest.mousePress(chrome, Qt.MouseButton.LeftButton, pos=QPoint(40, 10))
    QTest.mouseMove(chrome, QPoint(90, 40))
    QTest.mouseRelease(chrome, Qt.MouseButton.LeftButton, pos=QPoint(90, 40))
    assert chrome._drag_offset is None
    assert dialog.pos() != start


def test_theme_change_repaints_the_close_glyph(isolated_theme, qtbot) -> None:
    isolated_theme.apply("catppuccin-latte", persist=False)
    dlg = _Sample()
    qtbot.addWidget(dlg)
    dlg.resize(360, 160)
    dlg.show()
    qtbot.waitExposed(dlg)
    before = dlg.chrome.close_button().icon().cacheKey()
    isolated_theme.apply("catppuccin-mocha", persist=False)
    assert dlg.chrome.close_button().icon().cacheKey() != before


def test_chrome_paints_through_the_style(dialog, monkeypatch) -> None:
    from qtpy.QtWidgets import QStyle

    seen: list[object] = []
    style = dialog.chrome.style()
    real = style.drawPrimitive

    def spy(element, *args, **kwargs):
        seen.append(element)
        return real(element, *args, **kwargs)

    monkeypatch.setattr(
        type(style),
        "drawPrimitive",
        lambda self, e, *a, **k: spy(e, *a, **k),
        raising=False,
    )
    dialog.chrome.repaint()
    assert QStyle.PrimitiveElement.PE_Widget in seen
