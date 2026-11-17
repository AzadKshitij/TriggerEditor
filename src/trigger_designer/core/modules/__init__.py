"""Optional capability modules: extra data packs the user adds on purpose.

The app is offline by default. A module (for example a local model for Fuzzy
Match) is added only from the app, after a consent screen names its source
host(s), size and hashes. Once installed it is used offline, and it can be
removed at any time.

Importing this package never loads the network code. ``install_module`` below
loads ``downloader`` only when it is called, and the app calls it only with a
``Consent`` the user granted for the same manifest.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import BinaryIO

from trigger_designer.core.modules.catalogue import Catalogue, load_catalogue
from trigger_designer.core.modules.consent import (
    Consent,
    ConsentSummary,
    consent_summary,
)
from trigger_designer.core.modules.errors import ModuleError
from trigger_designer.core.modules.manifest import (
    ModuleFile,
    ModuleManifest,
    parse_manifest,
)
from trigger_designer.core.modules.store import (
    InstalledModule,
    ModuleStore,
    VerifyResult,
    modules_dir,
)

__all__ = [
    "Catalogue",
    "Consent",
    "ConsentSummary",
    "InstalledModule",
    "ModuleError",
    "ModuleFile",
    "ModuleManifest",
    "ModuleStore",
    "VerifyResult",
    "consent_summary",
    "install_module",
    "load_catalogue",
    "modules_dir",
    "parse_manifest",
]


def install_module(
    manifest: ModuleManifest,
    consent: Consent,
    store: ModuleStore | None = None,
    *,
    progress: Callable[[int, int], None] | None = None,
    cancel: Callable[[], bool] | None = None,
    opener: Callable[[str, float], BinaryIO] | None = None,
    timeout: float = 30.0,
) -> InstalledModule:
    """Download, check and install ``manifest`` once the user has consented.

    A thin wrapper: the network code is imported here, on first use only. See
    ``downloader.install_module`` for the rules and the TD-MOD-* errors it raises.
    """
    from trigger_designer.core.modules.downloader import install_module as _impl

    return _impl(
        manifest,
        consent,
        store,
        progress=progress,
        cancel=cancel,
        opener=opener,
        timeout=timeout,
    )
