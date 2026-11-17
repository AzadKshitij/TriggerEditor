"""Installed modules: where they live, what is installed, verification and removal.

Layout: ``<root>/<id>/module.json`` plus the module's files, flat, by file name.
The downloader writes ``module.json`` last, so a folder without it is not an
installed module. ``root`` is ``data_dir() / "modules"`` unless a caller passes
another folder. Nothing here touches the network; only the downloader writes here.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from trigger_designer.core.headless.state import data_dir
from trigger_designer.core.modules.errors import (
    INSTALL_FAILED,
    NOT_INSTALLED,
    ModuleError,
)
from trigger_designer.core.modules.manifest import (
    RECORD_FILE_NAME,
    ModuleManifest,
    is_valid_module_id,
    parse_manifest,
)

#: Partial downloads and replaced versions wait here, inside the store root.
PARTIAL_DIR = ".partial"
#: A module record is a few kilobytes; anything bigger is not one.
MAX_RECORD_BYTES = 1 << 20
_HASH_CHUNK = 1 << 20


def modules_dir() -> Path:
    """``data_dir() / "modules"``: the folder every installed module lives in."""
    return data_dir() / "modules"


def utc_timestamp() -> str:
    """ISO-8601 UTC time to the second, for example ``2026-11-17T10:20:30Z``."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class InstalledModule:
    id: str
    version: str
    #: The module's folder (it holds the files and ``module.json``).
    path: Path
    #: The total of the manifest's file sizes.
    size_bytes: int
    installed_at: str
    manifest: ModuleManifest


@dataclass(frozen=True)
class VerifyResult:
    ok: bool
    problems: tuple[str, ...]


class ModuleStore:
    """The modules installed under one folder. Every method here works offline."""

    def __init__(self, root: Path | None = None) -> None:
        # The folder is created by the first install, not here.
        self.root = Path(root) if root is not None else modules_dir()

    def installed(self) -> list[InstalledModule]:
        """Every valid installed module, sorted by id. Junk folders are ignored."""
        try:
            children = list(self.root.iterdir())
        except OSError:
            return []
        found: list[InstalledModule] = []
        for child in children:
            if not is_valid_module_id(child.name) or not child.is_dir():
                continue
            item = self.get(child.name)
            if item is not None:
                found.append(item)
        return sorted(found, key=lambda item: item.id)

    def get(self, module_id: str) -> InstalledModule | None:
        """The installed module with this id, or ``None``.

        A folder whose ``module.json`` is missing, unreadable or invalid, or whose
        manifest names another id, is not an installed module.
        """
        if not is_valid_module_id(module_id):
            return None
        folder = self.root / module_id
        record_path = folder / RECORD_FILE_NAME
        try:
            if record_path.stat().st_size > MAX_RECORD_BYTES:
                return None
            data = json.loads(record_path.read_bytes().decode("utf-8-sig"))
        except OSError, ValueError:
            return None
        if not isinstance(data, dict) or not isinstance(data.get("installed_at"), str):
            return None
        try:
            manifest = parse_manifest(data.get("manifest"))
        except ModuleError:
            return None
        if manifest.id != module_id:
            return None
        return InstalledModule(
            id=manifest.id,
            version=manifest.version,
            path=folder,
            size_bytes=manifest.total_size,
            installed_at=data["installed_at"],
            manifest=manifest,
        )

    def path_of(self, module_id: str) -> Path | None:
        """The folder that holds the module's files, for nodes to read offline."""
        item = self.get(module_id)
        return item.path if item is not None else None

    def verify(self, module_id: str) -> VerifyResult:
        """Re-hash every file against the stored manifest.

        Reports missing files, files of the wrong size, changed files and files the
        manifest does not list. Raises ``ModuleError`` (TD-MOD-002) when the module
        is not installed.
        """
        item = self.get(module_id)
        if item is None:
            raise _not_installed(module_id)
        problems: list[str] = []
        for entry in item.manifest.files:
            problems += _check_file(
                item.path / entry.name, entry.name, entry.size_bytes, entry.sha256
            )
        listed = {entry.name for entry in item.manifest.files}
        try:
            extras = sorted(
                child.name
                for child in item.path.iterdir()
                if child.name != RECORD_FILE_NAME and child.name not in listed
            )
        except OSError as exc:
            problems.append(f"unreadable: the module folder ({exc.strerror or exc})")
            extras = []
        problems += [f"unexpected: {name}" for name in extras]
        return VerifyResult(ok=not problems, problems=tuple(problems))

    def remove(self, module_id: str) -> bool:
        """Delete an installed module's folder. ``False`` if it is not installed.

        An id that is not a valid module id (``../x``, ``con``, ``a/b``) is treated
        as not installed: nothing outside ``root`` is ever touched. The record goes
        first, so a folder that is only half deleted is no longer listed.
        """
        if self.get(module_id) is None:
            return False
        folder = self.root / module_id
        try:
            (folder / RECORD_FILE_NAME).unlink()
            shutil.rmtree(folder)
        except OSError as exc:
            raise ModuleError(
                INSTALL_FAILED,
                f"The module '{module_id}' could not be removed "
                f"({exc.strerror or type(exc).__name__}).",
                "Close any program that is using its files, then try again.",
            ) from exc
        return True


def _not_installed(module_id: str) -> ModuleError:
    return ModuleError(
        NOT_INSTALLED,
        f"The module '{module_id}' is not installed.",
        "Check the name, or list the installed modules.",
    )


def _check_file(path: Path, name: str, size_bytes: int, sha256: str) -> list[str]:
    try:
        if not path.is_file():
            return [f"missing: {name}"]
        actual = path.stat().st_size
        if actual != size_bytes:
            return [f"wrong size: {name} is {actual:,} bytes, expected {size_bytes:,}"]
        if _sha256_file(path) != sha256:
            return [f"changed: {name} no longer matches its SHA-256 hash"]
    except OSError as exc:
        return [f"unreadable: {name} ({exc.strerror or exc})"]
    return []


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(_HASH_CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()
