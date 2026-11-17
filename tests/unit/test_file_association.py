"""Registering ``.tds`` for Trigger Designer, per user (no real registry is touched)."""

from __future__ import annotations

import sys

import pytest

from trigger_designer.core import file_association as fa

pytestmark = pytest.mark.unit


class _Handle:
    """What ``winreg.OpenKey`` / ``CreateKeyEx`` return: a context manager."""

    def __init__(self, registry: FakeRegistry, places: list[tuple[dict, str]]):
        self.registry, self.places = registry, places

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


class FakeRegistry:
    """The few ``winreg`` calls the module makes, on two in-memory hives.

    ``user`` is HKEY_CURRENT_USER and ``machine`` the system-wide classes (what a
    program such as Tableau registers for ``.tds``). HKEY_CLASSES_ROOT reads the
    user hive first, then the machine hive, as Windows does.
    """

    HKEY_CURRENT_USER = "HKCU"
    HKEY_CLASSES_ROOT = "HKCR"
    KEY_READ = 1
    KEY_WRITE = 2
    REG_SZ = 1

    def __init__(self, machine: dict[str, dict[str, str]] | None = None) -> None:
        self.user: dict[str, dict[str, str]] = {}
        self.machine = {self._k(p): dict(v) for p, v in (machine or {}).items()}

    @staticmethod
    def _k(path: str) -> str:
        return path.lower().strip("\\")

    def _places(self, root: str, sub: str) -> list[tuple[dict, str]]:
        sub = self._k(sub)
        if root == self.HKEY_CURRENT_USER:
            return [(self.user, sub)]
        return [
            (self.user, "software\\classes\\" + sub),
            (self.machine, sub),
        ]

    def CreateKeyEx(self, root, sub, _reserved, _access):
        assert root == self.HKEY_CURRENT_USER, "only the user hive may be written"
        parts = self._k(sub).split("\\")
        for i in range(1, len(parts) + 1):
            self.user.setdefault("\\".join(parts[:i]), {})
        return _Handle(self, self._places(root, sub))

    def OpenKey(self, root, sub, _reserved, _access):
        places = [(s, p) for s, p in self._places(root, sub) if p in s]
        if not places:
            raise FileNotFoundError(sub)
        return _Handle(self, places)

    def SetValueEx(self, key, name, _reserved, _kind, value):
        store, path = key.places[0]
        store[path][name] = value

    def QueryValueEx(self, key, name):
        for store, path in key.places:
            if path in store and name in store[path]:
                return store[path][name], self.REG_SZ
        raise FileNotFoundError(name)

    def EnumKey(self, key, index):
        store, path = key.places[0]
        prefix = path + "\\"
        children = sorted(
            {k[len(prefix) :].split("\\")[0] for k in store if k.startswith(prefix)}
        )
        if index >= len(children):
            raise OSError("no more keys")
        return children[index]

    def DeleteKey(self, root, sub):
        assert root == self.HKEY_CURRENT_USER
        path = self._k(sub)
        if path not in self.user:
            raise FileNotFoundError(sub)
        if any(k.startswith(path + "\\") for k in self.user):
            raise OSError("the key has subkeys")
        del self.user[path]

    def DeleteValue(self, key, name):
        store, path = key.places[0]
        if name not in store[path]:
            raise FileNotFoundError(name)
        del store[path][name]

    # --- test helpers
    def value(self, sub: str, name: str = ""):
        return self.user.get("software\\classes\\" + self._k(sub), {}).get(name)

    def has_key(self, sub: str) -> bool:
        return "software\\classes\\" + self._k(sub) in self.user


@pytest.fixture(autouse=True)
def _no_shell_notification(monkeypatch):
    calls: list[int] = []
    monkeypatch.setattr(fa, "_notify_shell", lambda: calls.append(1))
    return calls


CMD = '"C:\\Users\\Zoë Ünal\\Trigger Designer\\TriggerEditor.exe" "%1"'
ICON = '"C:\\Users\\Zoë Ünal\\Trigger Designer\\TriggerEditor.exe",0'


def test_nothing_is_registered_to_begin_with():
    status = fa.status(FakeRegistry())
    assert status == fa.Association(
        registered=False, is_default=False, owner=None, command=None
    )


def test_registering_makes_tds_open_in_the_editor():
    reg = FakeRegistry()

    status = fa.register(CMD, ICON, reg=reg)

    assert status.registered and status.is_default
    assert status.owner == fa.PROG_ID and status.command == CMD
    assert reg.value(fa.PROG_ID) == "Trigger Designer workflow"
    assert reg.value(f"{fa.PROG_ID}\\DefaultIcon") == ICON
    assert reg.value(f"{fa.PROG_ID}\\shell\\open\\command") == CMD
    assert reg.value(".tds") == fa.PROG_ID
    assert reg.value(".tds\\OpenWithProgids", fa.PROG_ID) == ""
    assert reg.value("Applications\\TriggerEditor.exe", "FriendlyAppName") == (
        "Trigger Designer"
    )
    assert reg.value("Applications\\TriggerEditor.exe\\shell\\open\\command") == CMD
    assert reg.value("Applications\\TriggerEditor.exe\\SupportedTypes", ".tds") == ""


def test_a_path_with_spaces_and_non_ascii_letters_is_kept_exactly():
    reg = FakeRegistry()
    fa.register(CMD, ICON, reg=reg)
    assert "Zoë Ünal" in fa.status(reg).command
    assert fa.status(reg).command.endswith('"%1"')  # the dropped file's path


def test_another_programs_default_is_not_taken_over():
    """Tableau also uses .tds; Windows keeps a user's choice, so we only offer."""
    reg = FakeRegistry(machine={".tds": {"": "Tableau.Datasource"}})

    status = fa.register(CMD, ICON, reg=reg)

    assert status.registered is True
    assert status.is_default is False and status.owner == "Tableau.Datasource"
    assert reg.value(".tds") is None  # the default was left alone
    assert (
        reg.value(".tds\\OpenWithProgids", fa.PROG_ID) == ""
    )  # but offered in Open with


def test_registering_again_changes_nothing_but_the_command():
    reg = FakeRegistry()
    fa.register(CMD, ICON, reg=reg)
    moved = CMD.replace("Trigger Designer", "Moved")

    status = fa.register(moved, ICON, reg=reg)

    assert status.is_default and status.command == moved
    assert reg.value(".tds") == fa.PROG_ID


def test_unregistering_removes_what_was_written_and_nothing_else():
    reg = FakeRegistry()
    reg.user["software\\classes\\.csv"] = {"": "csvfile"}
    reg.user["software\\classes\\.tds\\openwithprogids"] = {"Other.Prog": ""}
    fa.register(CMD, ICON, reg=reg)

    status = fa.unregister(reg=reg)

    assert status.registered is False and status.is_default is False
    assert not reg.has_key(fa.PROG_ID) and not reg.has_key(f"{fa.PROG_ID}\\shell")
    assert not reg.has_key("Applications\\TriggerEditor.exe")
    assert reg.value(".tds\\OpenWithProgids", fa.PROG_ID) is None
    assert reg.value(".tds") is None
    assert reg.value(".csv") == "csvfile"  # untouched
    assert reg.value(".tds\\OpenWithProgids", "Other.Prog") == ""  # untouched


def test_a_default_another_program_set_survives_unregistering():
    reg = FakeRegistry()
    fa.register(CMD, ICON, reg=reg)
    reg.user["software\\classes\\.tds"][""] = "Chosen.ByUser"

    fa.unregister(reg=reg)

    assert reg.value(".tds") == "Chosen.ByUser"


def test_unregistering_when_nothing_was_registered_is_harmless():
    status = fa.unregister(reg=FakeRegistry())
    assert status.registered is False


def test_explorer_is_told_the_file_types_changed(_no_shell_notification):
    reg = FakeRegistry()
    fa.register(CMD, ICON, reg=reg)
    fa.unregister(reg=reg)
    assert len(_no_shell_notification) == 2


# ----------------------------------------------------------- what is launched
def test_a_frozen_editor_registers_itself(monkeypatch, tmp_path):
    exe = tmp_path / "Program Files" / "TriggerEditor.exe"
    exe.parent.mkdir()
    exe.write_bytes(b"")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))

    assert fa.editor_executable() == exe
    assert fa.open_command() == f'"{exe}" "%1"'
    assert fa.icon_value() == f'"{exe}",0'


def test_tds_exe_finds_the_editor_beside_it(monkeypatch, tmp_path):
    (tmp_path / "TriggerEditor.exe").write_bytes(b"")
    cli = tmp_path / "tds.exe"
    cli.write_bytes(b"")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(cli))

    assert fa.editor_executable() == tmp_path / "TriggerEditor.exe"


def test_a_frozen_copy_without_the_editor_has_no_command_to_find(monkeypatch, tmp_path):
    cli = tmp_path / "tds.exe"
    cli.write_bytes(b"")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(cli))

    assert fa.editor_executable() is None


def test_from_source_the_command_runs_the_module_without_a_console(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)

    command = fa.open_command()

    assert command.endswith('-m trigger_designer.main "%1"')
    assert command.startswith('"')
    assert fa.editor_executable() is None


def test_registering_is_only_for_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")

    assert fa.is_supported() is False
    with pytest.raises(fa.AssociationUnavailable):
        fa.register(CMD, ICON)
    with pytest.raises(fa.AssociationUnavailable):
        fa.status()
