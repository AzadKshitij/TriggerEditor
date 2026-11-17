"""What the user sees and agrees to before a module is downloaded.

``consent_summary`` is pure data and text for the consent screen. ``Consent``
records that the user pressed the accept button for one exact manifest (by its
fingerprint). ``install_module`` refuses to download without a matching ``Consent``.
"""

from __future__ import annotations

from dataclasses import dataclass

from trigger_designer.core.modules.manifest import ModuleManifest
from trigger_designer.core.modules.store import utc_timestamp


@dataclass(frozen=True)
class ConsentSummary:
    module_id: str
    name: str
    version: str
    hosts: tuple[str, ...]
    #: ``(name, url, size_bytes, sha256)`` for each file, in manifest order.
    files: tuple[tuple[str, str, int, str], ...]
    total_size: int
    total_size_text: str
    license: str
    #: Fixed plain-English statement of what will happen.
    notice: str


@dataclass(frozen=True)
class Consent:
    fingerprint: str
    accepted_at: str

    @classmethod
    def granted(cls, manifest: ModuleManifest) -> Consent:
        """Record that the user accepted ``manifest``. Call only after the accept button."""
        return cls(fingerprint=manifest.fingerprint(), accepted_at=utc_timestamp())


def consent_summary(manifest: ModuleManifest) -> ConsentSummary:
    hosts = manifest.hosts
    count = len(manifest.files)
    size = size_text(manifest.total_size)
    noun = "file" if count == 1 else "files"
    notice = (
        f"Trigger Designer will connect to {', '.join(hosts)} to download "
        f"{count} {noun}, {size}, one connection per file. Nothing else is sent: no workflow, no data, no "
        "account details. The files are checked against the hashes below and then "
        "used offline. You can remove the module at any time."
    )
    return ConsentSummary(
        module_id=manifest.id,
        name=manifest.name,
        version=manifest.version,
        hosts=hosts,
        files=tuple(
            (item.name, item.url, item.size_bytes, item.sha256)
            for item in manifest.files
        ),
        total_size=manifest.total_size,
        total_size_text=size,
        license=manifest.license,
        notice=notice,
    )


def size_text(size: int) -> str:
    """A byte count for people, in decimal units: 1 KB is 1,000 bytes."""
    if size < 1_000:
        return f"{size} B"
    value, unit = size / 1_000, "KB"
    for larger in ("MB", "GB"):
        if round(value, 1) < 1_000:
            break
        value, unit = value / 1_000, larger
    return f"{value:.1f} {unit}"
