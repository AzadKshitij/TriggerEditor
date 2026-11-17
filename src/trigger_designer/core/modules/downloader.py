"""The one module that talks to the network (optional modules, AI plan phase 5).

No other module may import ``urllib.request``, ``http.client``, ``ssl`` or
``socket`` for this feature. ``install_module`` runs only with a ``Consent`` the
user granted for exactly this manifest. Each file is one HTTPS GET with a generic
User-Agent, no cookies, no credentials, and nothing about the user, the workflows
or the machine. A redirect is followed only to an https address on the same host.
Files stream into a private folder, are hashed as they arrive, and move into
place only when every file has passed. ``module.json`` is written last. Nothing
is extracted, run or imported.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import shutil
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import BinaryIO
from urllib.parse import urljoin, urlsplit

from trigger_designer.core.headless.atomic import write_json_atomic
from trigger_designer.core.modules.consent import Consent
from trigger_designer.core.modules.errors import (
    CANCELLED,
    DOWNLOAD_FAILED,
    HASH_MISMATCH,
    INSTALL_FAILED,
    NO_CONSENT,
    REFUSED_URL,
    SIZE_MISMATCH,
    ModuleError,
)
from trigger_designer.core.modules.manifest import (
    RECORD_FILE_NAME,
    ModuleFile,
    ModuleManifest,
)
from trigger_designer.core.modules.store import (
    PARTIAL_DIR,
    InstalledModule,
    ModuleStore,
    utc_timestamp,
)

#: Bytes per read, and so per progress report.
CHUNK_BYTES = 64 * 1024
USER_AGENT = "TriggerDesigner-modules/1"

_RETRY_HINT = "Check the internet connection and try again. Nothing was installed."
_WRITE_HINT = (
    "Check that the disk has free space and that the data folder is writable, "
    "then try again. Nothing was installed."
)
_SIZE_HINT = (
    "The download was stopped and discarded. Try again later, or report it to "
    "the publisher."
)
_HASH_HINT = (
    "The file was discarded and nothing was installed. Report it to the publisher."
)


class _SameHostRedirect(urllib.request.HTTPRedirectHandler):
    """Follows a redirect only to an https address on the same host, with no credentials."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        origin = urlsplit(req.full_url)
        target_url = urljoin(req.full_url, newurl)
        target = urlsplit(target_url)
        if (
            target.scheme != "https"
            or target.hostname is None
            or target.hostname != origin.hostname
            or "@" in target.netloc
        ):
            shown = target.hostname or "an unknown host"
            raise ModuleError(
                REFUSED_URL,
                f"The server redirected the download to {shown}, which is not allowed.",
                "Modules are downloaded only from their publisher's own secure "
                "(https) address. Nothing was installed.",
            )
        return super().redirect_request(req, fp, code, msg, headers, target_url)


def _open_url(url: str, timeout: float) -> BinaryIO:
    """The only network call: a plain HTTPS GET, with nothing about the user sent."""
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"},
        method="GET",
    )
    opener = urllib.request.build_opener(_SameHostRedirect())
    return opener.open(request, timeout=timeout)


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
    """Download, check and install ``manifest``.

    ``progress(bytes_done, bytes_total)`` is called after each chunk. ``cancel()``
    is polled between chunks and stops the download with TD-MOD-009. ``opener(url,
    timeout)`` replaces the network (tests inject one). On any failure nothing is
    left behind, and an installed module with the same id is left as it was.
    """
    if (
        not isinstance(consent, Consent)
        or consent.fingerprint != manifest.fingerprint()
    ):
        raise ModuleError(
            NO_CONSENT,
            "The consent does not match this module, so nothing was downloaded.",
            "Show the consent screen again and accept it.",
        )
    hosts = set(manifest.hosts)
    for item in manifest.files:
        _check_url(item, hosts)

    store = store if store is not None else ModuleStore()
    partial = store.root / PARTIAL_DIR
    staging = partial / uuid.uuid4().hex
    fetch = opener if opener is not None else _open_url
    total = manifest.total_size
    done = 0
    try:
        try:
            staging.mkdir(parents=True)
        except OSError as exc:
            raise _write_error(exc) from exc
        for item in manifest.files:
            done = _fetch_file(
                item, staging / item.name, done, total, fetch, timeout, progress, cancel
            )
        _check_cancel(cancel)
        return _commit(manifest, store, staging)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
        _remove_if_empty(partial)


def _check_url(item: ModuleFile, hosts: set[str]) -> None:
    parts = urlsplit(item.url)
    if parts.scheme != "https" or parts.hostname not in hosts or "@" in parts.netloc:
        raise ModuleError(
            REFUSED_URL,
            f"The address of '{item.name}' is not a secure address of the "
            "module's publisher.",
            "Nothing was downloaded.",
        )


def _fetch_file(
    item: ModuleFile,
    dest: Path,
    done: int,
    total: int,
    fetch: Callable[[str, float], BinaryIO],
    timeout: float,
    progress: Callable[[int, int], None] | None,
    cancel: Callable[[], bool] | None,
) -> int:
    """Stream one file into ``dest``; check its size and hash. Returns bytes done."""
    try:
        stream = fetch(item.url, timeout)
    except ModuleError:
        raise
    except Exception as exc:  # any failure to connect is a download failure
        raise ModuleError(
            DOWNLOAD_FAILED,
            f"'{item.name}' could not be downloaded: {_why(exc)}.",
            _RETRY_HINT,
        ) from exc
    received = 0
    digest = hashlib.sha256()
    try:
        with open(dest, "wb") as out:
            while True:
                _check_cancel(cancel)
                try:
                    chunk = stream.read(CHUNK_BYTES)
                except Exception as exc:  # a stalled or dropped connection
                    raise ModuleError(
                        DOWNLOAD_FAILED,
                        f"'{item.name}' stopped downloading: {_why(exc)}.",
                        _RETRY_HINT,
                    ) from exc
                if not chunk:
                    break
                received += len(chunk)
                if received > item.size_bytes:  # never trust Content-Length alone
                    raise ModuleError(
                        SIZE_MISMATCH,
                        f"'{item.name}' is bigger than the {item.size_bytes:,} bytes "
                        "listed in the consent.",
                        _SIZE_HINT,
                    )
                digest.update(chunk)
                out.write(chunk)
                done += len(chunk)
                if progress is not None:
                    progress(done, total)
    except OSError as exc:  # the file could not be opened or written: a disk problem
        raise _write_error(exc) from exc
    finally:
        _close_quietly(stream)
    if received != item.size_bytes:
        raise ModuleError(
            SIZE_MISMATCH,
            f"'{item.name}' arrived as {received:,} bytes, but the consent lists "
            f"{item.size_bytes:,}.",
            _SIZE_HINT,
        )
    if digest.hexdigest() != item.sha256:
        raise ModuleError(
            HASH_MISMATCH, f"'{item.name}' does not match its SHA-256 hash.", _HASH_HINT
        )
    return done


def _check_cancel(cancel: Callable[[], bool] | None) -> None:
    if cancel is not None and cancel():
        raise ModuleError(
            CANCELLED,
            "The download was cancelled. Nothing was installed.",
            "Start the download again when you are ready.",
        )


def _commit(
    manifest: ModuleManifest, store: ModuleStore, staging: Path
) -> InstalledModule:
    """Move the verified folder into place. ``module.json`` is written last."""
    root = store.root
    target = root / manifest.id
    installed_at = utc_timestamp()
    record = {"installed_at": installed_at, "manifest": manifest.to_dict()}
    previous: Path | None = None
    moved_in = False
    try:
        if os.path.lexists(target):  # an older version (or junk): set it aside
            previous = root / PARTIAL_DIR / f"{uuid.uuid4().hex}.old"
            os.replace(target, previous)
        os.replace(staging, target)
        moved_in = True
        write_json_atomic(target / RECORD_FILE_NAME, record)
    except OSError as exc:
        _restore(target, previous, moved_in)
        raise _write_error(exc) from exc
    except BaseException:
        _restore(target, previous, moved_in)
        raise
    if previous is not None:
        shutil.rmtree(previous, ignore_errors=True)
    return InstalledModule(
        id=manifest.id,
        version=manifest.version,
        path=target,
        size_bytes=manifest.total_size,
        installed_at=installed_at,
        manifest=manifest,
    )


def _restore(target: Path, previous: Path | None, moved_in: bool) -> None:
    """Undo a commit that failed part-way: drop the new folder, put the old one back."""
    if moved_in:
        shutil.rmtree(target, ignore_errors=True)
    if previous is not None:
        with contextlib.suppress(OSError):
            os.replace(previous, target)


def _write_error(exc: OSError) -> ModuleError:
    detail = exc.strerror or type(exc).__name__
    return ModuleError(
        INSTALL_FAILED,
        f"The module could not be written to the data folder ({detail}).",
        _WRITE_HINT,
    )


def _why(exc: BaseException) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        return f"the server answered with HTTP {exc.code}"
    if isinstance(exc, urllib.error.URLError):
        return f"the network said: {exc.reason}"
    if isinstance(exc, TimeoutError):
        return "the connection timed out"
    return "the connection failed"


def _close_quietly(stream: object) -> None:
    close = getattr(stream, "close", None)
    if callable(close):
        with contextlib.suppress(Exception):
            close()


def _remove_if_empty(path: Path) -> None:
    with contextlib.suppress(OSError):
        path.rmdir()
