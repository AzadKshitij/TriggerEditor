"""Atomic file writes and staged outputs (plan 08 3.8, S5). Qt-free."""

from __future__ import annotations

import contextlib
import os
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from trigger_designer.core.headless.exit_codes import CliError, ExitCode
from trigger_designer.core.headless.paths import is_codegen_safe_dir


def write_bytes_atomic(path: Path, data: bytes) -> None:
    path = Path(path)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_bytes(data)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            tmp.unlink()
        raise


def write_json_atomic(path: Path, obj: Any) -> None:
    import orjson

    write_bytes_atomic(
        Path(path),
        orjson.dumps(obj, option=orjson.OPT_INDENT_2 | orjson.OPT_NON_STR_KEYS),
    )


@dataclass
class StagedOutput:
    node_id: int
    final: str
    staged: str
    backup: str | None = None
    cross_volume: bool = False
    #: Where the previous final is parked during commit (recorded in the lock so
    #: a killed run's leftovers can be restored by the next run).
    backup_path: str = ""


def plan_staging(
    finals: list[tuple[int, str]], run8: str, staging_root: Path
) -> list[StagedOutput]:
    """Where each output is written until every node succeeded (3.8)."""
    out: list[StagedOutput] = []
    for index, (node_id, final) in enumerate(finals):
        directory, name = os.path.split(final)
        stem, ext = os.path.splitext(name)
        backup = os.path.join(directory, f".{stem}.tdbak-{run8}{ext}")
        if is_codegen_safe_dir(directory) and is_codegen_safe_dir(name):
            out.append(
                StagedOutput(
                    node_id,
                    final,
                    os.path.join(directory, f".{stem}.tdtmp-{run8}{ext}"),
                    backup_path=backup,
                )
            )
        else:
            out.append(
                StagedOutput(
                    node_id,
                    final,
                    str(Path(staging_root) / run8 / f"{index}{ext}"),
                    cross_volume=True,
                    backup_path=backup,
                )
            )
    return out


def _unlink(path: str | None) -> None:
    if path:
        with contextlib.suppress(OSError):
            os.unlink(path)


def _rollback(staged: list[StagedOutput]) -> None:
    for item in staged:
        if item.backup and os.path.exists(item.backup):
            with contextlib.suppress(OSError):
                os.replace(item.backup, item.final)
            item.backup = None
        _unlink(item.staged)


def commit_all(staged: list[StagedOutput]) -> None:
    """Promote every staged file, or change nothing (backups are restored)."""
    try:
        for item in staged:  # phase A: move old finals aside (a locked one fails here)
            if os.path.exists(item.final):
                item.backup = (
                    item.backup_path or f"{item.final}.tdbak-{uuid.uuid4().hex[:8]}"
                )
                os.replace(item.final, item.backup)
        for item in staged:  # phase B: promote
            source = item.staged
            if item.cross_volume:
                source = os.path.join(
                    os.path.dirname(item.final),
                    f".{os.path.basename(item.final)}.tdtmp-copy",
                )
                shutil.copyfile(item.staged, source)
            os.replace(source, item.final)
    except OSError as exc:
        _rollback(staged)
        raise CliError(
            ExitCode.COMMIT_FAILED,
            "TD-CLI-013",
            f"could not write {exc.filename or 'an output'}: {exc.strerror or exc}",
            "Close the file in other programs (Excel keeps it locked) and run again. "
            "Previous files are unchanged.",
        ) from exc
    for item in staged:  # phase C: drop backups
        _unlink(item.backup)
        item.backup = None
        if item.cross_volume:
            _unlink(item.staged)


def discard_all(staged: list[StagedOutput]) -> None:
    for item in staged:
        _unlink(item.staged)
        _unlink(item.backup)
        if item.cross_volume:
            with contextlib.suppress(OSError):
                os.rmdir(os.path.dirname(item.staged))
