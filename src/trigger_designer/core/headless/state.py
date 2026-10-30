"""Where the CLI keeps its own files (plan 08 S1). Qt-free, stdlib only."""

from __future__ import annotations

import os
from pathlib import Path

STATE_SUBDIRS = ("locks", "work", "staging", "schedules", "logs")


def state_dir(override: str | os.PathLike | None = None) -> Path:
    """``override`` > env > ``%LOCALAPPDATA%`` > ``$XDG_STATE_HOME`` > ``~/.local/state``."""
    if override:
        return Path(override)
    env = os.environ.get("TRIGGER_DESIGNER_STATE_DIR")
    if env:
        return Path(env)
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / "Trigger Designer" / "cli"
        return Path.home() / "AppData" / "Local" / "Trigger Designer" / "cli"
    xdg = os.environ.get("XDG_STATE_HOME")
    if xdg:
        return Path(xdg) / "trigger-designer"
    return Path.home() / ".local" / "state" / "trigger-designer"


def data_dir() -> Path:
    """The application data folder, exactly as the editor chooses it."""
    override = os.environ.get("TRIGGER_DESIGNER_DATA_DIR")
    if override:
        return Path(override)
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "Trigger Designer"
    return Path.home() / ".trigger_designer"


def ensure(state: Path, sub: str = "") -> Path:
    """Create (once) and return ``state`` or one of its sub-folders."""
    path = state / sub if sub else state
    path.mkdir(parents=True, exist_ok=True)
    return path
