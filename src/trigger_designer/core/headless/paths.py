"""Path rules for workflow files (plan 08 3.6). The single owner of resolution."""

from __future__ import annotations

import os
import re

from trigger_designer.core.headless.exit_codes import CliError, ExitCode

_URL = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]+://")
_WIN_DRIVE = re.compile(r"^[A-Za-z]:[\\/]")
_UNSAFE_CODEGEN = frozenset("'\"{}\r\n\x00")


def basename_any(raw: str) -> str:
    """The last path part, splitting on both ``/`` and ``\\``."""
    return re.split(r"[\\/]", raw.rstrip("\\/"))[-1]


def remap_into_dir(raw: str, directory: str) -> str:
    return os.path.normpath(os.path.join(directory, basename_any(raw)))


def resolve_workflow_path(raw: str, *, base_dir: str) -> str:
    """Resolve a path saved in a workflow against the workflow's folder.

    No ``~`` or environment expansion (determinism). Relative paths join
    ``base_dir`` (never the CWD: a scheduled task starts in System32).
    """
    raw = (raw or "").strip()
    if not raw:
        raise CliError(ExitCode.INVALID, "TD-IN-001", "empty file path")
    if "\x00" in raw or _URL.match(raw):
        raise CliError(
            ExitCode.INVALID,
            "TD-CLI-006",
            f"unsupported path: {raw!r} (remote paths are not supported)",
            "Use a local file or folder path.",
        )
    if os.name != "nt" and not _WIN_DRIVE.match(raw):
        raw = raw.replace("\\", "/")
    rooted = raw.startswith("\\\\") or (os.name == "nt" and raw.startswith(("\\", "/")))
    if os.path.isabs(raw) or _WIN_DRIVE.match(raw) or rooted:
        return os.path.normpath(raw)
    return os.path.normpath(os.path.join(base_dir, raw))


def relativize(path: str, base_dir: str) -> str | None:
    """A forward-slash path relative to ``base_dir``, or ``None`` if outside it."""
    norm_path = os.path.normpath(path)
    norm_base = os.path.normpath(base_dir)
    drive_a = os.path.splitdrive(norm_path)[0]
    drive_b = os.path.splitdrive(norm_base)[0]
    if os.name == "nt":
        drive_a, drive_b = drive_a.lower(), drive_b.lower()
    if drive_a != drive_b:
        return None
    cmp_path, cmp_base = os.path.normcase(norm_path), os.path.normcase(norm_base)
    prefix = cmp_base.rstrip("\\/") + os.sep
    if not cmp_path.startswith(prefix):
        return None
    tail = norm_path[len(prefix) :]
    return tail.replace("\\", "/") if tail else None


def is_codegen_safe_dir(p: str) -> bool:
    """No character that breaks the f-string File Output code embeds a path in."""
    return not any(ch in _UNSAFE_CODEGEN for ch in p)
