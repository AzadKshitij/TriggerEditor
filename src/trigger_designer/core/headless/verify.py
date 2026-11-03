"""``verify-log``: does a run record still match the files it describes? (plan 08 6.4)

Qt- and Polars-free. The record's own SHA-256 chain (plan 02) replaces the
``.json.sha256`` sidecar of the original plan: the record hash covers every
field, and a store folder is additionally checked as a chain.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from trigger_designer.core.headless.exit_codes import CliError, ExitCode
from trigger_designer.core.headless.workflow_file import Finding

CODE = "TD-CLI-017"
_SKIP_NAMES = {"hash_cache.json"}


def _err(message: str) -> Finding:
    return Finding("error", CODE, message)


def _warn(message: str) -> Finding:
    return Finding("warning", CODE, message)


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_record(
    path: str | os.PathLike,
    *,
    workflow: str | None = None,
    check_files: bool = True,
) -> list[Finding]:
    from trigger_designer.core.audit.store import RunStore, verify_record_file

    findings: list[Finding] = []
    # V1 (+ V2): loads, schema is valid and the record hash matches its content.
    report = verify_record_file(path)
    for problem in report.problems:
        findings.append(_err(f"{problem.kind}: {problem.message}"))
    try:
        record = RunStore().load_dict(path)
    except Exception as exc:  # noqa: BLE001
        findings.append(_err(f"the record cannot be read ({type(exc).__name__})"))
        return findings

    # V3: status agrees with the node results.
    statuses = [n.get("status") for n in record.get("nodes") or []]
    status = record.get("status")
    if status == "ok" and any(s != "ok" for s in statuses):
        findings.append(_err("status is ok but a node did not succeed"))
    if status == "failed" and all(s == "ok" for s in statuses):
        findings.append(_err("status is failed but every node succeeded"))

    # V4: the workflow file is the one that ran.
    if workflow:
        try:
            current = hashlib.sha256(Path(workflow).read_bytes()).hexdigest()
        except OSError as exc:
            findings.append(_err(f"the workflow cannot be read: {exc.strerror or exc}"))
        else:
            if current != record.get("workflow_sha256"):
                findings.append(
                    _err("the workflow file differs from the one that was run")
                )

    # V5: outputs still match.
    if check_files:
        for item in record.get("outputs") or []:
            recorded = item.get("sha256")
            out_path = item.get("path")
            if not recorded or not out_path:
                continue
            if not os.path.exists(out_path):
                findings.append(_err(f"output missing: {out_path}"))
                continue
            if (
                item.get("size_bytes") is not None
                and os.path.getsize(out_path) != item["size_bytes"]
            ):
                findings.append(_err(f"output size changed: {out_path}"))
                continue
            try:
                if _sha256_file(out_path) != recorded:
                    findings.append(_err(f"output content changed: {out_path}"))
            except OSError as exc:
                findings.append(
                    _err(f"output unreadable: {out_path} ({exc.strerror or exc})")
                )

        # V6: inputs are legitimately refreshed, so changes only warn.
        for item in record.get("inputs") or []:
            recorded = item.get("sha256")
            in_path = item.get("path")
            if not recorded or not in_path:
                continue
            if not os.path.exists(in_path):
                findings.append(_warn(f"input no longer present: {in_path}"))
            else:
                try:
                    if _sha256_file(in_path) != recorded:
                        findings.append(
                            _warn(f"input changed since the run: {in_path}")
                        )
                except OSError:
                    findings.append(_warn(f"input unreadable: {in_path}"))
    return findings


def verify_folder(
    folder: str | os.PathLike, *, check_files: bool = True
) -> list[Finding]:
    """Chain-check a store folder, then every record in it."""
    from trigger_designer.core.audit.store import verify_store

    findings: list[Finding] = []
    report = verify_store(folder)
    for problem in report.problems:
        findings.append(_err(f"{problem.kind}: {problem.message}"))
    for warning in report.warnings:
        findings.append(_warn(warning))
    for record in record_files(folder):
        for finding in verify_record(record, check_files=check_files):
            findings.append(
                Finding(
                    finding.level,
                    finding.td_code,
                    f"{Path(record).name}: {finding.message}",
                )
            )
    return findings


def record_files(folder: str | os.PathLike) -> list[Path]:
    """Sealed record files of a store folder (not the cache or index)."""
    return sorted(
        p
        for p in Path(folder).glob("*.json")
        if p.name not in _SKIP_NAMES and not p.name.startswith(".")
    )


def newest_record(root: str | os.PathLike) -> Path | None:
    best: tuple[float, Path] | None = None
    for p in Path(root).rglob("*.json"):
        if p.name in _SKIP_NAMES or p.name.startswith("."):
            continue
        mtime = p.stat().st_mtime
        if best is None or mtime > best[0]:
            best = (mtime, p)
    return best[1] if best else None


def require_target(path: str | None, default_root: Path, workflow: str | None) -> Path:
    """The record or folder to check (see the command's help)."""
    if path:
        target = Path(path)
        if not target.exists():
            raise CliError(ExitCode.INVALID, "TD-CLI-001", f"{path} does not exist.")
        return target
    if workflow:
        from trigger_designer.core.audit.store import resolve_store_dir

        folder = resolve_store_dir(workflow, "", default_root)
        found = newest_record(folder) if folder.exists() else None
    else:
        found = (
            newest_record(default_root / "runs")
            if (default_root / "runs").exists()
            else None
        )
    if found is None:
        raise CliError(
            ExitCode.INVALID,
            "TD-CLI-001",
            "No run record was found.",
            "Pass a record file or a folder of records.",
        )
    return found
