"""Shared test bootstrap.

Every test runs against a throwaway preference store: the app reads and
writes one INI under ``%APPDATA%/Trigger Designer`` unless
``TRIGGER_DESIGNER_DATA_DIR`` points elsewhere, and a developer's real
preferences must never leak into assertions (or be overwritten by a test
run).

A single ``QApplication`` is created on demand for the tests that build
windows; existing modules that create their own use
``QApplication.instance() or QApplication([])`` and therefore share it.

Legacy ``QSettings`` scopes are stubbed out: the first-run migration would
otherwise read the developer's real registry, which makes both the assertions
and the migrated theme machine-dependent. The migration itself is covered by
``test_preferences.py`` with injected sources.

The suite is split into layers by directory, and each layer is marked
automatically: ``tests/unit`` (logic), ``tests/ui`` (offscreen widgets),
``tests/e2e`` (workflow files through the real app) and ``tests/benchmarks``
(memory/timing, only with ``--run-benchmarks``). A test runs in exactly one
layer; ``pytest -m unit`` must not need a window.
"""

from __future__ import annotations

import gc
import os
import sys
import tempfile
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

#: Kept alive for the whole session so the directory is not garbage-collected.
_DATA_DIR = tempfile.TemporaryDirectory(prefix="trigger-designer-tests-")
os.environ.setdefault("TRIGGER_DESIGNER_DATA_DIR", _DATA_DIR.name)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from trigger_designer.qt import preferences as _preferences

# A legacy scope is a QSettings; an empty list keeps tests hermetic.
_preferences._legacy_scopes = list

_APP = None


def ensure_qapp():
    """Create (or return) the process-wide QApplication."""
    global _APP
    from qtpy.QtWidgets import QApplication

    _APP = QApplication.instance() or QApplication([])
    return _APP


@pytest.fixture(scope="session", autouse=True)
def qapp():
    return ensure_qapp()


# -- layers ------------------------------------------------------------------

_LAYERS = {
    "unit": "unit",
    "ui": "ui",
    "e2e": "e2e",
    "benchmarks": "benchmark",
}


def pytest_addoption(parser) -> None:
    parser.addoption(
        "--run-benchmarks",
        action="store_true",
        default=False,
        help="also run tests marked benchmark (skipped by default)",
    )


def pytest_collection_modifyitems(config, items) -> None:
    """Mark each test by the layer directory it lives in."""
    run_benchmarks = config.getoption("--run-benchmarks")
    for item in items:
        layer = _layer_for(item.path)
        if layer is None:
            continue
        item.add_marker(getattr(pytest.mark, layer))
        if layer == "benchmark" and not run_benchmarks:
            item.add_marker(pytest.mark.skip(reason="benchmarks need --run-benchmarks"))


def _layer_for(path: Path) -> str | None:
    try:
        relative = Path(path).resolve().relative_to(_ROOT / "tests")
    except ValueError:
        return None
    if not relative.parts:
        return None
    return _LAYERS.get(relative.parts[0])


# -- preferences -------------------------------------------------------------


@pytest.fixture()
def clean_preferences(tmp_path, monkeypatch):
    """A fresh, empty preference store rooted in the test's tmp dir."""
    from trigger_designer.qt import preferences

    monkeypatch.setenv(preferences.ENV_DATA_DIR, str(tmp_path / "appdata"))
    monkeypatch.setattr(preferences, "_instance", None)
    yield preferences.get_preferences()
    monkeypatch.setattr(preferences, "_instance", None)


@pytest.fixture()
def theme_manager(clean_preferences, tmp_path, monkeypatch):
    """A ThemeManager with built-ins from the repo and user themes in tmp."""
    from trigger_designer.qt import theme_manager

    manager = theme_manager.ThemeManager(
        preferences=clean_preferences,
        themes_dir=tmp_path / "themes",
        app=None,
    )
    # Widgets resolve the manager through the module-level singleton.
    monkeypatch.setattr(theme_manager, "_instance", manager)
    return manager


# -- Qt hygiene --------------------------------------------------------------


class _NullProgressDialog:
    """Stand-in for the modal QProgressDialog shown during a file load."""

    def setLabelText(self, _text: str) -> None:
        pass

    def setMaximum(self, _value: int) -> None:
        pass

    def setValue(self, _value: int) -> None:
        pass

    def repaint(self) -> None:
        pass

    def close(self) -> None:
        pass

    def deleteLater(self) -> None:
        pass


class _ImmediateQTimer:
    """QTimer.singleShot that runs the callback at once.

    The workflow mixin schedules run-button cleanup one second after a run
    so the user sees the "executed" pen colours; a test wants the window
    settled before it ends, and a pending timer would otherwise fire against
    a deleted window.
    """

    @staticmethod
    def singleShot(_delay_ms: int, callback) -> None:
        callback()


@pytest.fixture(autouse=True)
def _no_leaked_qt_windows(qapp):
    """Delete top-level widgets a test left behind, without close events.

    ``TriggerWindow.closeEvent`` saves the session and quits the shared
    ``QApplication``; sending a real close event to a leaked main window in
    cleanup would end the loop every other test relies on. ``deleteLater``
    skips the close path and destroys children with the parent.
    """
    yield
    from qtpy.QtCore import QCoreApplication, QEvent
    from qtpy.QtWidgets import QApplication

    widgets = []
    for widget in list(QApplication.topLevelWidgets()):
        if widget is qapp:
            continue
        try:
            widget.hide()
            widget.deleteLater()
            widgets.append(widget)
        except RuntimeError:
            continue
    # Drop Python's own references first, then run the queued deletions.
    # Under PySide6 a top-level widget's C++ side is owned by Python, so the
    # destruction order matters: collecting before the deferred pass lets the
    # wrapper and the C++ object go down in one defined step instead of
    # leaving a half-dead item for the next test to paint into (access
    # violation, position varies with GC timing).
    del widgets
    gc.collect()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QApplication.processEvents()

    from trigger_designer.qt.helpers.global_logger import GlobalLogger

    GlobalLogger.get_instance().set_main_window(None)


@pytest.fixture()
def no_modal_dialogs(monkeypatch):
    """Keep file-load and run UI out of tests, and capture what it would show.

    Returns a dict with ``warnings`` (validation messages that would have
    opened a QMessageBox) and ``run_code`` (the node lists ``getPyFile``
    would have written to the last-run script).
    """
    from trigger_designer.qt import design_window
    from trigger_designer.qt.helpers import eval_progress, workflow_execution_mixin

    captured: dict[str, list] = {"warnings": [], "run_code": []}

    # Both call sites create the load/evaluation progress dialog through their
    # own module-level name, so patch both.
    _null_dialog = lambda *_args, **_kwargs: _NullProgressDialog()
    monkeypatch.setattr(design_window, "make_progress_dialog", _null_dialog)
    monkeypatch.setattr(eval_progress, "make_progress_dialog", _null_dialog)

    class _RecordingMessageBox:
        StandardButton = design_window.QMessageBox.StandardButton

        @classmethod
        def warning(cls, _parent, _title, text, *_args, **_kwargs):
            captured["warnings"].append(text)

        information = warning
        critical = warning

    monkeypatch.setattr(design_window, "QMessageBox", _RecordingMessageBox)

    def _capture_code(_self, nodes, path=None):
        captured["run_code"].append(nodes)
        return ""

    monkeypatch.setattr(design_window.TriggerSubWindow, "getPyFile", _capture_code)
    monkeypatch.setattr(workflow_execution_mixin, "QTimer", _ImmediateQTimer)

    return captured


@pytest.fixture(autouse=True)
def _e2e_default_no_modal_dialogs(request):
    """Every ``tests/e2e`` test runs with the modal-dialog stub applied.

    A progress dialog or warning box opened by an end-to-end run would block the
    offscreen test forever. A test that also asks for ``no_modal_dialogs`` gets
    the same (cached) fixture value, so it is applied once.
    """
    if "e2e" in Path(str(request.node.fspath)).parts:
        yield request.getfixturevalue("no_modal_dialogs")
    else:
        yield None
