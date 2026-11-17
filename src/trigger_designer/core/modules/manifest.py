"""Module manifests: the description of one optional module, checked strictly.

A manifest is a plain dict (one entry of the catalogue). ``parse_manifest`` is
the way in: it returns a ``ModuleManifest`` whose every field is well formed, or
raises ``ModuleError`` (TD-MOD-001) naming the bad field. The fingerprint covers
the whole manifest, so a consent given for one fingerprint cannot be reused for
another. Nothing here touches the network or the disk.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from trigger_designer.core.modules.errors import BAD_MANIFEST, ModuleError

#: The metadata file written last into an installed module's folder. No module
#: file may use this name.
RECORD_FILE_NAME = "module.json"

MAX_FILES = 20
MAX_FILE_NAME = 100
MAX_FILE_BYTES = 2_147_483_648  # 2 GiB
MAX_TOTAL_BYTES = 4_294_967_296  # 4 GiB
MAX_URL = 2_048
MAX_VERSION = 32
MAX_NAME = 80
MAX_DESCRIPTION = 500
MAX_LICENSE = 80

_ID_PATTERN = re.compile(r"[a-z][a-z0-9_-]{2,39}")
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
_WINDOWS_DEVICE_NAMES = frozenset(
    {"con", "prn", "aux", "nul"}
    | {f"com{number}" for number in range(1, 10)}
    | {f"lpt{number}" for number in range(1, 10)}
)
_FORBIDDEN_NAME_CHARACTERS = frozenset('/\\:*?"<>|')
_MODULE_FIELDS = frozenset(
    {"id", "name", "version", "description", "license", "files", "homepage"}
)
_REQUIRED_MODULE_FIELDS = _MODULE_FIELDS - {"homepage"}
_FILE_FIELDS = frozenset({"name", "url", "size_bytes", "sha256"})


def is_valid_module_id(value: object) -> bool:
    """True for a text that may name a module folder (lowercase, no separators)."""
    return (
        isinstance(value, str)
        and _ID_PATTERN.fullmatch(value) is not None
        and value not in _WINDOWS_DEVICE_NAMES
    )


@dataclass(frozen=True)
class ModuleFile:
    """One file of a module: where to get it and the size and hash it must have."""

    name: str
    url: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True)
class ModuleManifest:
    """One optional module, as listed in the catalogue."""

    id: str
    name: str
    version: str
    description: str
    license: str
    files: tuple[ModuleFile, ...]
    homepage: str = ""

    @property
    def total_size(self) -> int:
        return sum(item.size_bytes for item in self.files)

    @property
    def hosts(self) -> tuple[str, ...]:
        """The distinct host names the files come from, sorted."""
        names = {urlsplit(item.url).hostname for item in self.files}
        return tuple(sorted(name for name in names if name))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "license": self.license,
            "homepage": self.homepage,
            "files": [
                {
                    "name": item.name,
                    "url": item.url,
                    "size_bytes": item.size_bytes,
                    "sha256": item.sha256,
                }
                for item in self.files
            ],
        }

    def fingerprint(self) -> str:
        """SHA-256 of the canonical JSON of ``to_dict()``."""
        canonical = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def parse_manifest(data: object) -> ModuleManifest:
    """Validate one manifest dict. Raises ``ModuleError`` (TD-MOD-001) naming the field."""
    body = _object(data, "module", _MODULE_FIELDS, _REQUIRED_MODULE_FIELDS)
    module_id = body["id"]
    if not is_valid_module_id(module_id):
        raise _fail(
            "id",
            "must be 3 to 40 characters: a lowercase letter first, then lowercase "
            "letters, digits, '_' or '-' (and not a reserved Windows name)",
        )
    homepage = (
        _url(body["homepage"], "homepage", optional=True) if "homepage" in body else ""
    )
    return ModuleManifest(
        id=module_id,
        name=_text(body["name"], "name", max_length=MAX_NAME),
        version=_text(body["version"], "version", max_length=MAX_VERSION),
        description=_text(
            body["description"], "description", max_length=MAX_DESCRIPTION
        ),
        license=_text(body["license"], "license", max_length=MAX_LICENSE),
        files=_files(body["files"]),
        homepage=homepage,
    )


# ---------------------------------------------------------------- field checks
def _fail(field: str, problem: str) -> ModuleError:
    return ModuleError(
        BAD_MANIFEST,
        f"'{field}' {problem}.",
        "Update Trigger Designer, or ask the publisher for a corrected module list.",
    )


def _object(
    value: object,
    field: str,
    allowed: frozenset[str],
    required: frozenset[str],
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise _fail(field, "must be an object")
    unknown = sorted(str(key) for key in value if key not in allowed)
    if unknown:
        raise _fail(field, f"has unknown field(s): {', '.join(unknown)}")
    missing = sorted(required.difference(value))
    if missing:
        raise _fail(field, f"is missing: {', '.join(missing)}")
    return value


def _text(value: object, field: str, *, max_length: int, min_length: int = 1) -> str:
    if not isinstance(value, str):
        raise _fail(field, "must be text")
    if not min_length <= len(value) <= max_length:
        raise _fail(field, f"must be {min_length} to {max_length} characters long")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise _fail(field, "must not contain control characters")
    return value


def _url(value: object, field: str, *, optional: bool = False) -> str:
    text = _text(value, field, max_length=MAX_URL, min_length=0 if optional else 1)
    if not text:  # only an optional field may be empty
        return text
    try:
        parts = urlsplit(text)
        _ = parts.port  # raises ValueError for a malformed port
    except ValueError:
        raise _fail(field, "must be a valid https address") from None
    if (
        parts.scheme != "https"
        or not parts.hostname
        or "@" in parts.netloc
        or any(char.isspace() for char in text)
    ):
        raise _fail(
            field,
            "must be an https address with a host name and no user name or password",
        )
    return text


def _size(value: object, field: str, limit: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise _fail(field, "must be a whole number of bytes")
    if not 1 <= value <= limit:
        raise _fail(field, f"must be between 1 and {limit:,} bytes")
    return value


def _sha256(value: object, field: str) -> str:
    if not isinstance(value, str) or _SHA256_PATTERN.fullmatch(value) is None:
        raise _fail(
            field, "must be a SHA-256 hash: 64 lowercase hexadecimal characters"
        )
    return value


def _file_name(value: object, field: str) -> str:
    name = _text(value, field, max_length=MAX_FILE_NAME)
    unsafe = (
        name.startswith(".")
        or ".." in name
        or name[-1] in " ."
        or any(char in _FORBIDDEN_NAME_CHARACTERS for char in name)
        or name.casefold() == RECORD_FILE_NAME
        or name.split(".", 1)[0].casefold() in _WINDOWS_DEVICE_NAMES
    )
    if unsafe:
        raise _fail(
            field,
            "must be a plain file name: no folders, no leading dot, no reserved "
            "characters, not module.json and not a reserved Windows name",
        )
    return name


def _files(value: object) -> tuple[ModuleFile, ...]:
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_FILES:
        raise _fail("files", f"must be a list of 1 to {MAX_FILES} files")
    files: list[ModuleFile] = []
    seen: set[str] = set()
    for index, entry in enumerate(value):
        field = f"files[{index}]"
        item = _object(entry, field, _FILE_FIELDS, _FILE_FIELDS)
        name = _file_name(item["name"], f"{field}.name")
        if name.casefold() in seen:
            raise _fail(
                f"{field}.name",
                f"repeats the file name '{name}' (names must differ, ignoring capitals)",
            )
        seen.add(name.casefold())
        files.append(
            ModuleFile(
                name=name,
                url=_url(item["url"], f"{field}.url"),
                size_bytes=_size(
                    item["size_bytes"], f"{field}.size_bytes", MAX_FILE_BYTES
                ),
                sha256=_sha256(item["sha256"], f"{field}.sha256"),
            )
        )
    total = sum(item.size_bytes for item in files)
    if total > MAX_TOTAL_BYTES:
        raise _fail(
            "files",
            f"add up to {total:,} bytes; the limit is {MAX_TOTAL_BYTES:,} bytes",
        )
    return tuple(files)
