"""Streamed hashing, the fingerprint cache and output row counting (plan 02 3.5-3.6)."""

from __future__ import annotations

import hashlib
import os
import random
import threading

import polars as pl
import pytest

from trigger_designer.core.audit import fingerprint as fp_mod
from trigger_designer.core.audit.fingerprint import (
    FingerprintCache,
    count_rows_in_file,
    fingerprint_file,
    recorded_path,
    sha256_stream,
)

EMPTY_SHA = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_sha256_matches_hashlib_for_multi_chunk_file(tmp_path):
    data = random.Random(1).randbytes(20 * 1024 * 1024)
    path = tmp_path / "big.bin"
    path.write_bytes(data)
    assert sha256_stream(path, chunk=1024 * 1024) == hashlib.sha256(data).hexdigest()


def test_empty_file_hash(tmp_path):
    path = tmp_path / "empty"
    path.write_bytes(b"")
    assert sha256_stream(path) == EMPTY_SHA


def test_hash_is_cancellable_before_start(tmp_path):
    path = tmp_path / "f"
    path.write_bytes(b"abc")
    event = threading.Event()
    event.set()
    assert sha256_stream(path, cancel=event) is None
    fp = fingerprint_file(path, "input", cancel=event)
    assert fp.sha256 is None and fp.sha256_status == "cancelled"


def test_hash_is_cancellable_midway(tmp_path):
    path = tmp_path / "f"
    path.write_bytes(b"x" * 5_000_000)
    event = threading.Event()
    real_open = open
    reads = {"n": 0}

    class Slow:
        def __init__(self, handle):
            self._h = handle

        def read(self, n):
            reads["n"] += 1
            if reads["n"] == 3:
                event.set()
            return self._h.read(n)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self._h.close()

    import builtins

    original = builtins.open
    builtins.open = lambda *a, **k: Slow(real_open(*a, **k))
    try:
        result = sha256_stream(path, cancel=event, chunk=4096)
    finally:
        builtins.open = original
    assert result is None
    assert reads["n"] <= 4  # stopped within a chunk of the request


def test_cache_hit_avoids_rehash(tmp_path, monkeypatch):
    path = tmp_path / "in.csv"
    path.write_text("a,b\n1,2\n", encoding="utf-8")
    cache = FingerprintCache()
    first = fingerprint_file(path, "input", cache=cache)
    assert first.sha256_status == "computed"
    calls = {"n": 0}
    real = fp_mod.sha256_stream

    def counting(*args, **kwargs):
        calls["n"] += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(fp_mod, "sha256_stream", counting)
    second = fingerprint_file(path, "input", node_id=2, cache=cache)
    assert second.sha256_status == "cached" and second.sha256 == first.sha256
    assert calls["n"] == 0
    # a changed mtime invalidates the entry
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 5_000_000_000))
    third = fingerprint_file(path, "input", cache=cache)
    assert third.sha256_status == "computed" and calls["n"] == 1
    # use_cache=False always recomputes (Check inputs / Verify)
    fourth = fingerprint_file(path, "input", cache=cache, use_cache=False)
    assert fourth.sha256_status == "computed" and calls["n"] == 2


def test_cache_persists_and_corrupt_cache_is_ignored(tmp_path):
    target = tmp_path / "hash_cache.json"
    cache = FingerprintCache(target)
    cache.put("/x/a.csv", 10, 20, "ab" * 32)
    cache.save()
    assert target.is_file()
    again = FingerprintCache(target)
    assert again.get("/x/a.csv", 10, 20) == "ab" * 32
    target.write_text("{not json", encoding="utf-8")
    broken = FingerprintCache(target)
    assert broken.get("/x/a.csv", 10, 20) is None
    assert (tmp_path / "hash_cache.json.bad").exists()


def test_cache_is_capped_oldest_first():
    cache = FingerprintCache(max_entries=3)
    for i in range(5):
        cache.put(f"/f{i}", 1, i, "0" * 64)
    assert len(cache) == 3
    assert cache.get("/f0", 1, 0) is None
    assert cache.get("/f4", 1, 4) is not None


def test_size_limit_skips_hash(tmp_path):
    path = tmp_path / "f"
    path.write_bytes(b"12345")
    fp = fingerprint_file(path, "input", hash_max_bytes=4)
    assert fp.sha256_status == "skipped_size_limit"
    assert fp.sha256 is None and fp.size_bytes == 5


def test_missing_file_status(tmp_path):
    fp = fingerprint_file(tmp_path / "nope.csv", "input", node_id=7)
    assert fp.sha256_status == "missing"
    assert fp.error == "FileNotFoundError"
    assert fp.size_bytes is None and fp.node_id == 7


def test_disabled_status(tmp_path):
    path = tmp_path / "f"
    path.write_bytes(b"x")
    fp = fingerprint_file(path, "output", hash_enabled=False)
    assert fp.sha256_status == "disabled" and fp.sha256 is None
    assert fp.size_bytes == 1 and fp.modified_time.endswith("Z")


def test_permission_error_status(tmp_path, monkeypatch):
    path = tmp_path / "f"
    path.write_bytes(b"x")

    def boom(*_a, **_k):
        raise PermissionError("locked")

    monkeypatch.setattr(fp_mod, "sha256_stream", boom)
    fp = fingerprint_file(path, "input")
    assert fp.sha256_status == "error"
    assert fp.error.startswith("PermissionError")


def test_excel_sheet_is_recorded(tmp_path):
    path = tmp_path / "book.xlsx"
    path.write_bytes(b"not really excel")
    fp = fingerprint_file(path, "input", sheet="Sheet1")
    assert fp.sheet == "Sheet1" and fp.sha256


def test_recorded_path_uses_forward_slashes(tmp_path):
    shown = recorded_path(tmp_path / "a.csv")
    assert "\\" not in shown and shown.endswith("/a.csv")


# -- count_rows_in_file -----------------------------------------------------
def _frame() -> pl.DataFrame:
    return pl.DataFrame({"id": [1, 2, 3], "name": ["a", "b", "c"]})


def test_count_csv_with_embedded_newline(tmp_path):
    path = tmp_path / "q.csv"
    path.write_text('id,note\n1,"line one\nline two"\n2,plain\n', encoding="utf-8")
    assert count_rows_in_file(path, "csv") == 2


def test_count_custom_delimiter(tmp_path):
    path = tmp_path / "d.txt"
    path.write_text("a;b\n1;2\n3;4\n", encoding="utf-8")
    assert count_rows_in_file(path, "custom_delimited", ";") == 2


@pytest.mark.parametrize("fmt", ["parquet", "ipc", "ndjson", "json"])
def test_count_binary_formats(tmp_path, fmt):
    path = tmp_path / f"f.{fmt}"
    frame = _frame()
    {
        "parquet": frame.write_parquet,
        "ipc": frame.write_ipc,
        "ndjson": frame.write_ndjson,
        "json": frame.write_json,
    }[fmt](path)
    assert count_rows_in_file(path, fmt) == 3


def test_count_excel(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    path = tmp_path / "x.xlsx"
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.append(["id", "name"])
    sheet.append([1, "a"])
    sheet.append([2, "b"])
    workbook.save(path)
    assert count_rows_in_file(path, "excel") == 2


def test_count_unreadable_or_unknown_returns_none(tmp_path):
    assert count_rows_in_file(tmp_path / "missing.csv", "csv") is None
    path = tmp_path / "f.bin"
    path.write_bytes(b"\x00\x01")
    assert count_rows_in_file(path, "parquet") is None
    assert count_rows_in_file(path, "mystery") is None
