"""Canonical JSON and hashing for run records (docs/plan/02-audit-trail.md 3.4).

Qt-free and import-light: only the standard library and ``orjson``.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

import orjson

GENESIS_HASH = "0" * 64

# Sorted keys, no whitespace, UTF-8, shortest round-trip floats. Datetimes and
# dataclasses are refused (orjson would otherwise serialise them silently), so a
# value that cannot be reproduced from the on-disk JSON never reaches a hash.
# Integers up to 64 bits are accepted (``mtime_ns`` exceeds 2**53).
_OPTS = (
    orjson.OPT_SORT_KEYS
    | orjson.OPT_PASSTHROUGH_DATETIME
    | orjson.OPT_PASSTHROUGH_DATACLASS
    | orjson.OPT_PASSTHROUGH_SUBCLASS
)


def canonical_json(obj: Any) -> bytes:
    """Serialise ``obj`` to its canonical byte form; ``TypeError`` for non-JSON."""
    return orjson.dumps(obj, option=_OPTS)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compute_record_hash(record_dict: dict) -> str:
    """Hash of a record dict with its own ``record_hash`` field left out."""
    body = {k: v for k, v in record_dict.items() if k != "record_hash"}
    return sha256_hex(canonical_json(body))


def utc_now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
