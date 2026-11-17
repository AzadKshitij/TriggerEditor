"""Errors of the optional modules: one exception type and stable TD-MOD codes.

The plain-language text shown for each code lives in ``core/errors/catalogue.py``.
The message on an exception says what happened in this particular case.
"""

from __future__ import annotations

#: The catalogue, a manifest or an entry of it is not valid.
BAD_MANIFEST = "TD-MOD-001"
#: The module is not installed, or the name is not a module id at all.
NOT_INSTALLED = "TD-MOD-002"
#: The user has not accepted the consent for exactly this manifest.
NO_CONSENT = "TD-MOD-003"
#: An address is not https, is not on the publisher's host, or a redirect left it.
REFUSED_URL = "TD-MOD-004"
#: The connection failed, timed out, answered with an HTTP error or dropped.
DOWNLOAD_FAILED = "TD-MOD-005"
#: A file arrived with more or fewer bytes than the manifest lists.
SIZE_MISMATCH = "TD-MOD-006"
#: A file's SHA-256 is not the one in the manifest; the file is discarded.
HASH_MISMATCH = "TD-MOD-007"
#: Files could not be written, moved or removed (disk full, permissions).
INSTALL_FAILED = "TD-MOD-008"
#: The user cancelled the download. Nothing was installed.
CANCELLED = "TD-MOD-009"


class ModuleError(Exception):
    """A failure of the optional-module feature, with a stable ``TD-MOD-*`` code.

    ``code`` is one of the constants above, ``message`` is one plain sentence
    about what happened, and ``hint`` is what the user can do next.
    """

    def __init__(self, code: str, message: str, hint: str = "") -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message
        self.hint = hint
