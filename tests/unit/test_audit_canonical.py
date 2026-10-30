"""Canonical JSON and hashing (docs/plan/02-audit-trail.md 3.4)."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pytest

from trigger_designer.core.audit.canonical import (
    GENESIS_HASH,
    canonical_json,
    compute_record_hash,
    sha256_hex,
    utc_now_iso,
)


def test_known_vector():
    digest = sha256_hex(canonical_json({"b": 2, "a": 1}))
    assert digest == "43258cff783fe7036d8a43033f830adfc60ec037382473548ac742b888292777"


def test_key_order_and_whitespace_irrelevant():
    one = canonical_json({"a": 1, "b": {"y": 1, "x": 2}})
    two = canonical_json({"b": {"x": 2, "y": 1}, "a": 1})
    assert one == two
    assert b" " not in one and b"\n" not in one


def test_canonical_json_non_ascii():
    out = canonical_json({"b": 1, "a": [1.5, None, "é"]})
    assert out == b'{"a":[1.5,null,"\xc3\xa9"],"b":1}'


def test_large_integers_up_to_64_bits_are_accepted():
    # mtime_ns is ~1.7e18, well above 2**53
    assert canonical_json({"n": 1792512131500000000}) == b'{"n":1792512131500000000}'


@pytest.mark.parametrize(
    "value",
    [{1, 2}, Path("x"), datetime(2026, 1, 1), 2**64],
    ids=["set", "path", "datetime", "huge-int"],
)
def test_rejects_non_json_types(value):
    with pytest.raises(TypeError):
        canonical_json({"v": value})


def test_record_hash_excludes_record_hash_field():
    body = {"a": 1, "prev_record_hash": GENESIS_HASH, "record_hash": "x"}
    base = compute_record_hash(body)
    assert compute_record_hash({**body, "record_hash": "something else"}) == base
    assert compute_record_hash({**body, "prev_record_hash": "1" * 64}) != base


def test_utc_now_iso_shape():
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{6}Z", utc_now_iso())


def test_genesis_is_64_zeros():
    assert GENESIS_HASH == "0" * 64
