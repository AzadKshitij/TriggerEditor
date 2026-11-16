"""Native captions follow the theme (GitHub issue #45).

``DwmSetWindowAttribute`` is not available offscreen, so the Win32 call is
replaced by a recorder and the test checks *which* windows get themed, with
what colours, and when.
"""

import pytest
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QApplication, QDialog, QWidget

from trigger_designer.qt.helpers import native_title_theme as module
from trigger_designer.qt.theme_manager import get_theme_manager


@pytest.fixture
def calls(monkeypatch):
    recorded: list[dict] = []
    monkeypatch.setattr(module, "native_caption_supported", lambda: True)
    monkeypatch.setattr(
        module,
        "apply_native_title_colors",
        lambda hwnd, **kwargs: recorded.append({"hwnd": hwnd, **kwargs}),
    )
    return recorded


@pytest.fixture
def filter_(calls, qapp):
    instance = module.NativeTitleTheme(QApplication.instance())
    yield instance
    QApplication.instance().removeEventFilter(instance)
    instance.deleteLater()


def test_framed_window_is_themed_on_show(filter_, calls, qtbot) -> None:
    window = QWidget()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    assert calls, "a framed top-level window must be themed when shown"
    manager = get_theme_manager()
    assert calls[-1]["dark"] == manager.is_dark()
    assert calls[-1]["caption"] is not None
    assert calls[-1]["text"] is not None


def test_a_dialog_is_themed_too(filter_, calls, qtbot) -> None:
    dialog = QDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)
    assert calls


def test_frameless_windows_are_skipped(filter_, calls, qtbot) -> None:
    window = QWidget()
    window.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    assert calls == []


def test_a_theme_change_rethemes_open_windows(filter_, calls, qtbot) -> None:
    window = QWidget()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)
    manager = get_theme_manager()
    original = manager.active_theme().id
    other = "catppuccin-mocha" if original != "catppuccin-mocha" else "catppuccin-latte"
    calls.clear()
    try:
        manager.apply(other)
        assert calls
        assert calls[-1]["dark"] == manager.is_dark()
    finally:
        manager.apply(original)


def test_nothing_is_installed_where_the_caption_is_not_native(
    monkeypatch, qapp
) -> None:
    monkeypatch.setattr(module, "native_caption_supported", lambda: False)
    recorded: list[object] = []
    monkeypatch.setattr(
        module, "apply_native_title_colors", lambda *a, **k: recorded.append(a)
    )
    instance = module.NativeTitleTheme(QApplication.instance())
    instance.apply(QWidget())
    assert recorded == []
