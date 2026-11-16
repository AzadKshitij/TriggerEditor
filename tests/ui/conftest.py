"""Fixtures shared by the ``tests/ui`` layer."""

import pytest


@pytest.fixture()
def isolated_theme(clean_preferences, tmp_path, qapp, monkeypatch):
    """A ThemeManager of its own, with the application look restored afterwards.

    ``ThemeManager.apply`` swaps the application style, palette, font and
    stylesheet and remembers the choice as a sticky preview, so a test that
    switches themes on the shared singleton leaves the next test a different
    look. This one is bound to the real application but the whole look is put
    back on teardown.
    """
    from qtpy.QtGui import QFont, QPalette

    from trigger_designer.qt import theme_manager as theme_manager_module
    from trigger_designer.qt.theme_manager import ThemeManager

    sheet = qapp.styleSheet()
    palette = QPalette(qapp.palette())
    font = QFont(qapp.font())
    style_name = qapp.style().objectName()
    manager = ThemeManager(
        preferences=clean_preferences, themes_dir=tmp_path / "themes", app=qapp
    )
    monkeypatch.setattr(theme_manager_module, "_instance", manager)
    yield manager
    qapp.setStyleSheet("")
    qlementine = getattr(manager, "_qlementine", None)
    if qlementine is not None:
        qlementine.uninstall(qapp)
    qapp.setStyle(style_name)
    qapp.setStyleSheet(sheet)
    qapp.setPalette(palette)
    qapp.setFont(font)
