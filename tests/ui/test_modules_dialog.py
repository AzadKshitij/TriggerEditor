"""The Optional modules dialog, its consent screen, and the Help menu entry.

The dialog reaches the store, the catalogue and the installer only through its
constructor seam, so these tests substitute fakes: a real ``ModuleStore`` rooted
in ``tmp_path`` whose listing and checks are canned, a catalogue loader returning
three manifests, and an installer that records its calls and reports progress
from the worker thread. Nothing here touches the network. The consent screen and
the message boxes are patched so each flow runs without blocking.
"""

from __future__ import annotations

import re
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace

import pytest
from qtpy.QtWidgets import QAction, QApplication, QDialog, QMessageBox

from trigger_designer.core.modules import (
    Catalogue,
    Consent,
    InstalledModule,
    ModuleError,
    ModuleFile,
    ModuleManifest,
    ModuleStore,
    VerifyResult,
)
from trigger_designer.qt.dialogs import modules_dialog
from trigger_designer.qt.dialogs.modules_dialog import (
    ModuleConsentDialog,
    ModulesDialog,
)
from trigger_designer.qt.main_window import TriggerWindow

_APP = QApplication.instance() or QApplication([])

_SHA256 = "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08"
EMPTY_MESSAGE = "No optional modules are available in this version."


def _manifest(module_id: str, name: str, version: str) -> ModuleManifest:
    return ModuleManifest(
        id=module_id,
        name=name,
        version=version,
        description=f"{name} adds an example capability.",
        license="MIT",
        files=(
            ModuleFile(
                name=f"{module_id}.bin",
                url=f"https://downloads.example.org/{module_id}/{module_id}.bin",
                size_bytes=4,
                sha256=_SHA256,
            ),
        ),
        homepage=f"https://example.org/{module_id}",
    )


ALPHA = _manifest("alpha", "Alpha", "1.0.0")
BETA = _manifest("beta", "Beta", "2.0.0")
GAMMA = _manifest("gamma", "Gamma", "3.0.0")
DELTA = _manifest("delta", "Delta", "1.0.0")


# -- fakes --------------------------------------------------------------------


class _FakeStore(ModuleStore):
    """A real ModuleStore rooted in tmp_path, with its listing and checks canned."""

    def __init__(
        self,
        root: Path,
        *,
        installed: tuple = (),
        verify_result: VerifyResult | None = None,
        remove_result: bool = True,
    ) -> None:
        super().__init__(root)
        self._installed = list(installed)
        self._verify_result = verify_result or VerifyResult(ok=True, problems=())
        self._remove_result = remove_result
        self.verified: list[str] = []
        self.removed: list[str] = []

    def installed(self):
        return list(self._installed)

    def verify(self, module_id):
        self.verified.append(module_id)
        return self._verify_result

    def remove(self, module_id):
        self.removed.append(module_id)
        return self._remove_result


class _FakeInstaller:
    """Records each call and reports progress from the worker thread."""

    def __init__(self, *, error: Exception | None = None) -> None:
        self.calls: list[tuple[ModuleManifest, Consent, ModuleStore]] = []
        self.threads: list[threading.Thread] = []
        self._error = error

    def __call__(self, manifest, consent, store=None, *, progress=None, cancel=None):
        self.calls.append((manifest, consent, store))
        self.threads.append(threading.current_thread())
        if progress is not None:
            progress(1, 2)
            progress(2, 2)
        if self._error is not None:
            raise self._error
        return SimpleNamespace(version=manifest.version)


def _installed_module(
    manifest: ModuleManifest, root: Path, *, version: str | None = None
) -> InstalledModule:
    return InstalledModule(
        id=manifest.id,
        version=version or manifest.version,
        path=root / manifest.id,
        size_bytes=2048,
        installed_at="2026-11-01T10:00:00+00:00",
        manifest=manifest,
    )


def _dialog(
    qtbot,
    store: _FakeStore,
    installer,
    *,
    catalogue: tuple = (ALPHA, BETA),
    problems: tuple = (),
) -> ModulesDialog:
    listing = Catalogue(
        modules=tuple(catalogue), problems=tuple(problems), source="test"
    )
    dialog = ModulesDialog(
        store=store, catalogue_loader=lambda: listing, installer=installer
    )
    qtbot.addWidget(dialog)
    return dialog


def _select(dialog: ModulesDialog, module_id: str) -> None:
    index = next(i for i, row in enumerate(dialog._rows) if row.module_id == module_id)
    dialog._table.selectRow(index)


def _statuses(dialog: ModulesDialog) -> dict[str, str]:
    table = dialog._table
    return {
        table.item(row, 0).text(): table.item(row, 3).text()
        for row in range(table.rowCount())
    }


def _wait_idle(qtbot, dialog: ModulesDialog) -> None:
    qtbot.waitUntil(lambda: dialog._busy is None, timeout=5000)


def _consent_answers(monkeypatch, answer) -> list[str]:
    """Answer the consent screen without showing it.

    ``answer`` is a button attribute name (``"download_button"`` or
    ``"cancel_button"``), which is pressed the way the user would press it, or a
    ``QDialog.DialogCode`` returned as is. The titles shown are returned so a test
    can check that the screen was actually opened.
    """
    titles: list[str] = []

    def fake_exec(self):
        titles.append(self.windowTitle())
        if isinstance(answer, str):
            getattr(self, answer).click()
            return (
                QDialog.DialogCode.Accepted
                if self.result()
                else QDialog.DialogCode.Rejected
            )
        return answer

    monkeypatch.setattr(ModuleConsentDialog, "exec", fake_exec)
    return titles


def _answer_question(monkeypatch, answer) -> list[str]:
    asked: list[str] = []

    def fake_question(parent, title, text, *args, **kwargs):
        asked.append(title)
        return answer

    monkeypatch.setattr(QMessageBox, "question", staticmethod(fake_question))
    return asked


def _record_warnings(monkeypatch) -> list[tuple[str, str]]:
    shown: list[tuple[str, str]] = []

    def fake_warning(parent, title, text, *args, **kwargs):
        shown.append((title, text))
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, "warning", staticmethod(fake_warning))
    return shown


# -- the table ----------------------------------------------------------------


def test_an_empty_catalogue_shows_the_empty_message(qtbot, tmp_path):
    dialog = _dialog(qtbot, _FakeStore(tmp_path), _FakeInstaller(), catalogue=())

    assert not dialog._empty.isHidden()
    assert dialog._empty.text() == EMPTY_MESSAGE
    assert dialog._table.rowCount() == 0
    assert dialog._table.isHidden()


def test_rows_show_each_module_with_its_status(qtbot, tmp_path):
    store = _FakeStore(
        tmp_path,
        installed=(
            _installed_module(BETA, tmp_path),
            _installed_module(GAMMA, tmp_path, version="2.5.0"),
            _installed_module(DELTA, tmp_path),
        ),
    )
    dialog = _dialog(qtbot, store, _FakeInstaller(), catalogue=(ALPHA, BETA, GAMMA))

    assert dialog._empty.isHidden()
    assert _statuses(dialog) == {
        "Alpha": "Not installed",
        "Beta": "Installed",
        "Gamma": "Update available",
        "Delta": "Installed",
    }


def test_catalogue_problems_are_shown_on_a_muted_line(qtbot, tmp_path):
    dialog = _dialog(
        qtbot,
        _FakeStore(tmp_path),
        _FakeInstaller(),
        catalogue=(ALPHA,),
        problems=("beta.json: unreadable",),
    )

    assert not dialog._problems.isHidden()
    assert "beta.json: unreadable" in dialog._problems.text()


def test_each_selection_offers_only_the_actions_it_can_run(qtbot, tmp_path):
    store = _FakeStore(
        tmp_path,
        installed=(
            _installed_module(BETA, tmp_path),
            _installed_module(DELTA, tmp_path),
        ),
    )
    dialog = _dialog(qtbot, store, _FakeInstaller(), catalogue=(ALPHA, BETA, GAMMA))

    _select(dialog, ALPHA.id)
    assert dialog._install_button.isEnabled()
    assert dialog._install_button.text() == "Install"
    assert not dialog._verify_button.isEnabled()
    assert not dialog._remove_button.isEnabled()

    _select(dialog, BETA.id)
    assert dialog._install_button.text() == "Reinstall"
    assert dialog._verify_button.isEnabled()
    assert dialog._remove_button.isEnabled()

    # Delta is installed but no longer in the catalogue: it can be checked and
    # removed, and it has nothing to download.
    _select(dialog, DELTA.id)
    assert not dialog._install_button.isEnabled()
    assert dialog._verify_button.isEnabled()
    assert dialog._remove_button.isEnabled()


def test_an_update_is_offered_as_update(qtbot, tmp_path):
    store = _FakeStore(
        tmp_path, installed=(_installed_module(GAMMA, tmp_path, version="2.5.0"),)
    )
    dialog = _dialog(qtbot, store, _FakeInstaller(), catalogue=(GAMMA,))

    _select(dialog, GAMMA.id)
    assert dialog._install_button.text() == "Update"
    assert dialog._install_button.isEnabled()


# -- install and consent ------------------------------------------------------


def test_install_opens_consent_and_downloads_nothing_before_it_is_accepted(
    qtbot, monkeypatch, tmp_path
):
    titles = _consent_answers(monkeypatch, QDialog.DialogCode.Rejected)
    installer = _FakeInstaller()
    dialog = _dialog(qtbot, _FakeStore(tmp_path), installer)

    _select(dialog, ALPHA.id)
    dialog._install_button.click()

    assert titles == ["Download Alpha 1.0.0?"]
    assert installer.calls == []
    assert dialog._busy is None


def test_cancelling_the_consent_screen_never_calls_the_installer(
    qtbot, monkeypatch, tmp_path
):
    _consent_answers(monkeypatch, "cancel_button")
    installer = _FakeInstaller()
    dialog = _dialog(qtbot, _FakeStore(tmp_path), installer)

    _select(dialog, ALPHA.id)
    dialog._install_button.click()

    assert installer.calls == []
    assert dialog._busy is None


def test_accepting_the_consent_screen_installs_once_in_the_background(
    qtbot, monkeypatch, tmp_path
):
    _consent_answers(monkeypatch, "download_button")
    installer = _FakeInstaller()
    store = _FakeStore(tmp_path)
    dialog = _dialog(qtbot, store, installer)

    _select(dialog, ALPHA.id)
    dialog._install_button.click()
    _wait_idle(qtbot, dialog)

    assert len(installer.calls) == 1
    manifest, consent, used_store = installer.calls[0]
    assert manifest is ALPHA
    assert used_store is store
    assert isinstance(consent, Consent)
    assert consent.fingerprint == ALPHA.fingerprint()
    assert installer.threads[0] is not threading.main_thread()
    assert dialog._status.text() == "Installed Alpha 1.0.0."


def test_progress_reports_reach_the_progress_bar(qtbot, monkeypatch, tmp_path):
    _consent_answers(monkeypatch, "download_button")
    gate = threading.Event()

    gib = 1 << 30

    def installer(manifest, consent, store=None, *, progress=None, cancel=None):
        # Bytes of a 3 GiB module: the total is past a C int, so the bar must scale.
        progress(gib, 3 * gib)
        gate.wait(5)
        progress(3 * gib, 3 * gib)
        return SimpleNamespace(version=manifest.version)

    dialog = _dialog(qtbot, _FakeStore(tmp_path), installer)
    _select(dialog, ALPHA.id)
    dialog._install_button.click()

    bar = dialog._busy.progress.bar
    # One third of the way through, on the bar's fixed 1000-step scale.
    qtbot.waitUntil(lambda: bar.value() == 333, timeout=5000)
    assert bar.maximum() == 1000

    gate.set()
    _wait_idle(qtbot, dialog)


def test_cancel_on_the_progress_dialog_asks_the_installer_to_stop(
    qtbot, monkeypatch, tmp_path
):
    _consent_answers(monkeypatch, "download_button")
    shown = _record_warnings(monkeypatch)
    started = threading.Event()

    def installer(manifest, consent, store=None, *, progress=None, cancel=None):
        started.set()
        for _ in range(500):
            if cancel():
                raise ModuleError("TD-MOD-009", "The installation was cancelled.", "")
            time.sleep(0.01)
        raise AssertionError("cancel was never requested")

    dialog = _dialog(qtbot, _FakeStore(tmp_path), installer)
    _select(dialog, ALPHA.id)
    dialog._install_button.click()
    qtbot.waitUntil(started.is_set, timeout=5000)

    dialog._busy.progress.cancel_button.click()
    _wait_idle(qtbot, dialog)

    assert shown == []
    assert dialog._status.text() == "Installation cancelled."


def test_an_installer_error_is_shown_and_the_dialog_keeps_working(
    qtbot, monkeypatch, tmp_path
):
    _consent_answers(monkeypatch, "download_button")
    shown = _record_warnings(monkeypatch)
    error = ModuleError(
        "TD-MOD-004",
        "The download failed.",
        "Check your connection and try again.",
    )
    dialog = _dialog(qtbot, _FakeStore(tmp_path), _FakeInstaller(error=error))

    _select(dialog, ALPHA.id)
    dialog._install_button.click()
    _wait_idle(qtbot, dialog)

    assert len(shown) == 1
    title, text = shown[0]
    assert "Alpha" in title
    assert "The download failed." in text
    assert "Check your connection and try again." in text
    assert "TD-MOD-004" in text
    assert dialog._table.rowCount() == 2


def test_the_consent_screen_defaults_to_cancel(qtbot):
    consent = ModuleConsentDialog(ALPHA)
    qtbot.addWidget(consent)

    assert consent.windowTitle() == "Download Alpha 1.0.0?"
    assert consent.cancel_button.isDefault()
    assert not consent.download_button.isDefault()


# -- verify and remove --------------------------------------------------------


def test_verify_reports_a_clean_module(qtbot, monkeypatch, tmp_path):
    shown = _record_warnings(monkeypatch)
    store = _FakeStore(tmp_path, installed=(_installed_module(BETA, tmp_path),))
    dialog = _dialog(qtbot, store, _FakeInstaller())

    _select(dialog, BETA.id)
    dialog._verify_button.click()
    _wait_idle(qtbot, dialog)

    assert store.verified == [BETA.id]
    assert shown == []
    assert dialog._status.text() == "Beta 2.0.0 matches what was installed."
    assert _statuses(dialog)["Beta"] == "Installed"


def test_verify_flags_a_module_changed_on_disk(qtbot, monkeypatch, tmp_path):
    shown = _record_warnings(monkeypatch)
    changed = VerifyResult(ok=False, problems=("beta.bin: hash mismatch",))
    store = _FakeStore(
        tmp_path,
        installed=(_installed_module(BETA, tmp_path),),
        verify_result=changed,
    )
    dialog = _dialog(qtbot, store, _FakeInstaller())

    _select(dialog, BETA.id)
    dialog._verify_button.click()
    _wait_idle(qtbot, dialog)

    assert len(shown) == 1
    assert "beta.bin: hash mismatch" in shown[0][1]
    assert _statuses(dialog)["Beta"] == "Installed (changed on disk)"


def test_remove_asks_first_and_removes_nothing_when_refused(
    qtbot, monkeypatch, tmp_path
):
    asked = _answer_question(monkeypatch, QMessageBox.StandardButton.No)
    store = _FakeStore(tmp_path, installed=(_installed_module(BETA, tmp_path),))
    dialog = _dialog(qtbot, store, _FakeInstaller())

    _select(dialog, BETA.id)
    dialog._remove_button.click()

    assert len(asked) == 1
    assert store.removed == []


def test_remove_calls_the_store_only_after_yes(qtbot, monkeypatch, tmp_path):
    asked = _answer_question(monkeypatch, QMessageBox.StandardButton.Yes)
    store = _FakeStore(tmp_path, installed=(_installed_module(BETA, tmp_path),))
    dialog = _dialog(qtbot, store, _FakeInstaller())

    _select(dialog, BETA.id)
    dialog._remove_button.click()

    assert len(asked) == 1
    assert store.removed == [BETA.id]


# -- the Help menu entry ------------------------------------------------------


@pytest.fixture()
def window() -> Iterator[TriggerWindow]:
    win = TriggerWindow()
    win.resize(1200, 800)
    win.show()
    _APP.processEvents()
    yield win
    win.hide()
    win.deleteLater()
    _APP.processEvents()


def test_the_help_menu_opens_the_optional_modules_dialog(window, monkeypatch):
    action = window.findChild(QAction, "actionOptionalModules")
    assert action is not None
    assert action.text() == "Optional modules…"
    assert action in window.helpMenu.actions()

    opened: list[ModulesDialog] = []

    def fake_exec(self):
        opened.append(self)
        return 0

    monkeypatch.setattr(ModulesDialog, "exec", fake_exec)
    action.trigger()

    assert len(opened) == 1
    assert isinstance(opened[0], ModulesDialog)


# -- source guards ------------------------------------------------------------


def test_the_dialog_uses_no_inline_styles_or_theme_icons():
    source = Path(modules_dialog.__file__).read_text(encoding="utf-8")

    assert "setStyleSheet" not in source
    assert "fromTheme" not in source


def test_the_dialog_module_imports_no_network_library():
    source = Path(modules_dialog.__file__).read_text(encoding="utf-8")

    for name in ("urllib", "http", "ssl", "socket", "requests"):
        pattern = rf"^\s*(import|from)\s+{name}\b"
        assert not re.search(pattern, source, re.MULTILINE), name
