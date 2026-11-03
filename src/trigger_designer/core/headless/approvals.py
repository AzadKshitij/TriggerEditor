"""Approval pinning of reviewed workflow files (plan 08 3.11, S3).

An approval is the SHA-256 of the raw ``.tds`` bytes. The store is per user and
not signed; in CI generate it in the pipeline and mount it read-only
(``--state-dir``).
"""

from __future__ import annotations

import getpass
import os
from datetime import UTC, datetime
from pathlib import Path

from trigger_designer.core.headless.atomic import write_json_atomic
from trigger_designer.core.headless.exit_codes import CliError, ExitCode

STORE_VERSION = 1


def _norm(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


class ApprovalStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def _read(self) -> list[dict]:
        if not self.path.exists():
            return []
        import json

        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise CliError(
                ExitCode.INVALID,
                "TD-CLI-001",
                f"The approvals file {self.path} cannot be read: {exc}",
            ) from None
        if not isinstance(data, dict) or data.get("version") != STORE_VERSION:
            raise CliError(
                ExitCode.INVALID,
                "TD-CLI-001",
                f"The approvals file {self.path} has an unknown version.",
                "Move it aside and approve the workflows again.",
            )
        items = data.get("approvals")
        return (
            [i for i in items if isinstance(i, dict)] if isinstance(items, list) else []
        )

    def _write(self, items: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(self.path, {"version": STORE_VERSION, "approvals": items})

    def list(self) -> list[dict]:
        return self._read()

    def is_approved(self, sha256: str) -> dict | None:
        for item in self._read():
            if item.get("sha256") == sha256:
                return item
        return None

    def changed_since_approval(self, path: str, sha256: str) -> dict | None:
        """An entry for the same path with a different hash (the file was edited)."""
        target = _norm(path)
        for item in self._read():
            if (
                _norm(str(item.get("path") or "")) == target
                and item.get("sha256") != sha256
            ):
                return item
        return None

    def add(self, entry: dict) -> None:
        items = [i for i in self._read() if i.get("sha256") != entry["sha256"]]
        items.append(entry)
        self._write(items)

    def revoke(self, sha_or_path: str) -> int:
        """Remove by hash or path; the number of entries removed."""
        target = _norm(sha_or_path)
        items = self._read()
        keep = [
            i
            for i in items
            if i.get("sha256") != sha_or_path
            and _norm(str(i.get("path") or "")) != target
        ]
        if len(keep) != len(items):
            self._write(keep)
        return len(items) - len(keep)


def store_for(state: Path) -> ApprovalStore:
    return ApprovalStore(Path(state) / "approvals.json")


def make_entry(doc, reads: list[str], writes: list[str], note: str = "") -> dict:
    try:
        user = getpass.getuser()
    except Exception:  # noqa: BLE001
        user = ""
    return {
        "sha256": doc.sha256,
        "name": Path(doc.path).name,
        "path": os.path.abspath(doc.path),
        "approved_by": user,
        "approved_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "note": note,
        "reads": reads,
        "writes": writes,
    }


def approval_status(state: Path, doc) -> dict:
    """``{"status": "yes"|"no"|"changed", "text": str, "entry": dict|None}``."""
    try:
        store = store_for(state)
        entry = store.is_approved(doc.sha256)
        if entry:
            return {
                "status": "yes",
                "entry": entry,
                "text": f"yes (by {entry.get('approved_by')} at {entry.get('approved_at')})",
            }
        changed = store.changed_since_approval(doc.path, doc.sha256)
        if changed:
            return {
                "status": "changed",
                "entry": changed,
                "text": f"no - changed since approval of {changed.get('path')}",
            }
    except CliError as exc:
        return {"status": "unknown", "entry": None, "text": f"unknown ({exc.message})"}
    return {"status": "no", "entry": None, "text": "no"}
