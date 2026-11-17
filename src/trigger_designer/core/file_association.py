"""Open ``.tds`` workflow files with Trigger Designer (Windows, per user, Qt-free).

The installer registers the file type itself. This module does the same for a
portable copy (unzipped, never installed): one call writes the per-user keys
under ``HKEY_CURRENT_USER\\Software\\Classes``, which needs no administrator
rights, and ``unregister`` removes exactly what ``register`` wrote.

What it writes:

* the ProgID ``TriggerDesigner.Workflow`` (display name, icon, the ``open``
  command ``"<exe>" "%1"``);
* ``.tds\\OpenWithProgids`` so Trigger Designer appears in "Open with";
* an ``Applications\\TriggerEditor.exe`` entry so Windows shows the product name;
* the ``.tds`` default, **only when nothing else owns the type** (Tableau also
  uses ``.tds`` for its data sources). Windows protects a user's own choice, so
  when another program is the default the user picks Trigger Designer once in
  Settings > Default apps (``status().owner`` names the other program).

The registry module is injectable so the logic is tested without touching the
real registry.
"""

from __future__ import annotations

import contextlib
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

EXTENSION = ".tds"
PROG_ID = "TriggerDesigner.Workflow"
APP_EXE = "TriggerEditor.exe"
FRIENDLY_NAME = "Trigger Designer workflow"
PRODUCT_NAME = "Trigger Designer"
_CLASSES = "Software\\Classes\\"
_SHCNE_ASSOCCHANGED = 0x08000000


class AssociationUnavailable(RuntimeError):
    """File types can only be registered on Windows."""


@dataclass(frozen=True)
class Association:
    """Where ``.tds`` files stand for the current user."""

    #: Trigger Designer's ProgID and "open" command are present.
    registered: bool
    #: ``.tds`` opens with Trigger Designer by default.
    is_default: bool
    #: The ProgID that currently owns ``.tds`` (``None`` when nothing does).
    owner: str | None
    #: The ``open`` command Trigger Designer registered, if any.
    command: str | None


def is_supported() -> bool:
    return sys.platform == "win32"


def _registry() -> Any:
    if not is_supported():
        raise AssociationUnavailable(
            "Registering file types is only available on Windows."
        )
    import winreg

    return winreg


# --------------------------------------------------------------- what to run
def editor_executable() -> Path | None:
    """The editor exe of a frozen (portable or installed) build, else ``None``.

    ``tds.exe`` sits beside it, so either program finds it.
    """
    if not getattr(sys, "frozen", False):
        return None
    current = Path(sys.executable)
    if current.name.lower() == APP_EXE.lower():
        return current
    sibling = current.with_name(APP_EXE)
    return sibling if sibling.exists() else None


def open_command() -> str:
    """The command Windows runs to open a file: the editor exe, or from source
    ``pythonw -m trigger_designer.main`` (no console window)."""
    exe = editor_executable()
    if exe is not None:
        return f'"{exe}" "%1"'
    python = Path(sys.executable)
    windowed = python.with_name("pythonw.exe")
    interpreter = windowed if windowed.exists() else python
    return f'"{interpreter}" -m trigger_designer.main "%1"'


def icon_value() -> str:
    exe = editor_executable()
    if exe is not None:
        return f'"{exe}",0'
    return str(Path(__file__).resolve().parents[1] / "resources" / "Icon.ico")


# ------------------------------------------------------------ registry helpers
def _set(reg: Any, subkey: str, name: str, value: str) -> None:
    with reg.CreateKeyEx(
        reg.HKEY_CURRENT_USER, _CLASSES + subkey, 0, reg.KEY_WRITE
    ) as key:
        reg.SetValueEx(key, name, 0, reg.REG_SZ, value)


def _get(reg: Any, root: Any, subkey: str, name: str = "") -> str | None:
    try:
        with reg.OpenKey(root, subkey, 0, reg.KEY_READ) as key:
            value, _kind = reg.QueryValueEx(key, name)
    except OSError:
        return None
    return str(value) if value not in (None, "") else None


def _delete_tree(reg: Any, subkey: str) -> None:
    path = _CLASSES + subkey
    try:
        with reg.OpenKey(
            reg.HKEY_CURRENT_USER, path, 0, reg.KEY_READ | reg.KEY_WRITE
        ) as key:
            children = []
            index = 0
            while True:
                try:
                    children.append(reg.EnumKey(key, index))
                except OSError:
                    break
                index += 1
    except OSError:
        return
    for child in children:
        _delete_tree(reg, f"{subkey}\\{child}")
    with contextlib.suppress(OSError):
        reg.DeleteKey(reg.HKEY_CURRENT_USER, path)


def _delete_value(reg: Any, subkey: str, name: str) -> None:
    with contextlib.suppress(OSError), reg.OpenKey(
        reg.HKEY_CURRENT_USER, _CLASSES + subkey, 0, reg.KEY_WRITE
    ) as key:
        reg.DeleteValue(key, name)


def _notify_shell() -> None:
    """Tell Explorer the file types changed so icons and menus refresh."""
    with contextlib.suppress(Exception):
        import ctypes

        ctypes.windll.shell32.SHChangeNotify(  # type: ignore[attr-defined]
            _SHCNE_ASSOCCHANGED, 0, None, None
        )


# ---------------------------------------------------------------------- public
def status(reg: Any = None) -> Association:
    """How ``.tds`` is set up for the current user."""
    reg = reg or _registry()
    owner = _get(reg, reg.HKEY_CLASSES_ROOT, EXTENSION)
    command = _get(
        reg, reg.HKEY_CURRENT_USER, f"{_CLASSES}{PROG_ID}\\shell\\open\\command"
    )
    return Association(
        registered=command is not None,
        is_default=owner == PROG_ID,
        owner=owner,
        command=command,
    )


def register(
    command: str | None = None, icon: str | None = None, *, reg: Any = None
) -> Association:
    """Make Trigger Designer available for ``.tds`` files (per user).

    Safe to run again: it rewrites its own keys, and sets the ``.tds`` default
    only when no other program owns the type.
    """
    reg = reg or _registry()
    command = command or open_command()
    icon = icon or icon_value()
    owner = _get(reg, reg.HKEY_CLASSES_ROOT, EXTENSION)

    _set(reg, PROG_ID, "", FRIENDLY_NAME)
    _set(reg, f"{PROG_ID}\\DefaultIcon", "", icon)
    _set(reg, f"{PROG_ID}\\shell\\open", "", "Open")
    _set(reg, f"{PROG_ID}\\shell\\open\\command", "", command)
    _set(reg, f"{EXTENSION}\\OpenWithProgids", PROG_ID, "")
    _set(reg, f"Applications\\{APP_EXE}", "FriendlyAppName", PRODUCT_NAME)
    _set(reg, f"Applications\\{APP_EXE}\\shell\\open\\command", "", command)
    _set(reg, f"Applications\\{APP_EXE}\\SupportedTypes", EXTENSION, "")
    if owner in (None, PROG_ID):
        _set(reg, EXTENSION, "", PROG_ID)
    _notify_shell()
    return status(reg)


def unregister(*, reg: Any = None) -> Association:
    """Remove exactly what ``register`` wrote, leaving other programs' keys."""
    reg = reg or _registry()
    _delete_tree(reg, PROG_ID)
    _delete_tree(reg, f"Applications\\{APP_EXE}")
    _delete_value(reg, f"{EXTENSION}\\OpenWithProgids", PROG_ID)
    # Our default goes; a default someone else set is theirs to keep.
    if _get(reg, reg.HKEY_CURRENT_USER, f"{_CLASSES}{EXTENSION}") == PROG_ID:
        _delete_value(reg, EXTENSION, "")
    _notify_shell()
    return status(reg)
