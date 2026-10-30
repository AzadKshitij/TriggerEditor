"""Hash chain, run store, locking and verification (plan 02 3.11, section 5)."""

from __future__ import annotations

import hashlib
import itertools
import os
import stat
import threading
import time
from pathlib import Path

import orjson
import pytest

from tests.support.audit_helpers import make_record
from trigger_designer.core.audit import store as store_mod
from trigger_designer.core.audit.canonical import (
    GENESIS_HASH,
    compute_record_hash,
)
from trigger_designer.core.audit.store import (
    RunAlreadySealed,
    RunStore,
    StoreLockTimeout,
    resolve_store_dir,
    verify_record_file,
    verify_store,
)


def _seed(tmp_path, count=3, **kwargs):
    store = RunStore(app_data_dir=tmp_path / "appdata")
    directory = tmp_path / "wf.runs"
    sealed = []
    for i in range(count):
        record = make_record(
            started_at=f"2026-10-21T09:14:0{i}.000000Z",
            finished_at=f"2026-10-21T09:14:0{i}.500000Z",
            **kwargs,
        )
        sealed.append(store.seal_and_save(record, directory)[0])
    return store, directory, sealed


def _edit(path: Path, mutate) -> None:
    """Rewrite a (read-only) record file the way a tamperer would."""
    os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    data = orjson.loads(path.read_bytes())
    mutate(data)
    path.write_bytes(orjson.dumps(data, option=orjson.OPT_INDENT_2))


def _record_path(directory: Path, sealed) -> Path:
    return directory / f"{sealed.run_id}.json"


def _kinds(report) -> list[str]:
    return [p.kind for p in report.problems]


def test_first_record_links_to_genesis(tmp_path):
    _store, _dir, sealed = _seed(tmp_path, 1)
    assert sealed[0].prev_record_hash == GENESIS_HASH
    assert sealed[0].seq == 1
    assert len(sealed[0].record_hash) == 64


def test_chain_links_and_seq_increment(tmp_path):
    _store, _dir, (r1, r2, r3) = _seed(tmp_path, 3)
    assert [r1.seq, r2.seq, r3.seq] == [1, 2, 3]
    assert r2.prev_record_hash == r1.record_hash
    assert r3.prev_record_hash == r2.record_hash


def test_verify_ok_on_clean_store(tmp_path):
    store, directory, sealed = _seed(tmp_path, 3)
    report = store.verify(directory)
    assert report.ok and report.checked == 3 and not report.problems
    assert report.head_hash == sealed[-1].record_hash
    assert report.warnings == []


def test_verify_empty_or_missing_store_is_ok(tmp_path):
    report = verify_store(tmp_path / "never_created")
    assert report.ok and report.checked == 0 and report.head_hash is None


def test_status_running_cannot_be_sealed(tmp_path):
    store = RunStore(app_data_dir=tmp_path)
    with pytest.raises(ValueError, match="running"):
        store.seal_and_save(make_record(status="running"), tmp_path / "s")


def test_second_seal_raises_already_sealed(tmp_path):
    store, directory, sealed = _seed(tmp_path, 1)
    with pytest.raises(RunAlreadySealed):
        store.seal_and_save(make_record(run_id=sealed[0].run_id), directory)


def test_verify_detects_edited_field(tmp_path):
    store, directory, (_r1, r2, _r3) = _seed(tmp_path, 3)
    _edit(_record_path(directory, r2), lambda d: d.update(status="failed"))
    report = store.verify(directory)
    assert not report.ok
    assert _kinds(report) == ["record_hash_mismatch"]  # one problem, only run 2
    assert report.problems[0].run_id == r2.run_id


def test_verify_detects_deleted_record(tmp_path):
    store, directory, (_r1, r2, _r3) = _seed(tmp_path, 3)
    path = _record_path(directory, r2)
    os.chmod(path, stat.S_IWRITE)
    path.unlink()
    report = store.verify(directory)
    assert _kinds(report) == ["missing_record"]


def test_verify_detects_swapped_records(tmp_path):
    store, directory, (_r1, r2, r3) = _seed(tmp_path, 3)
    p2, p3 = _record_path(directory, r2), _record_path(directory, r3)
    b2, b3 = p2.read_bytes(), p3.read_bytes()
    os.chmod(p2, stat.S_IWRITE)
    os.chmod(p3, stat.S_IWRITE)
    p2.write_bytes(b3)
    p3.write_bytes(b2)
    report = store.verify(directory)
    assert not report.ok
    assert {"index_mismatch", "prev_hash_mismatch"} <= set(_kinds(report))


def test_verify_detects_removed_index_line(tmp_path):
    store, directory, (_r1, r2, _r3) = _seed(tmp_path, 3)
    index = directory / "index.jsonl"
    lines = index.read_bytes().splitlines(keepends=True)
    index.write_bytes(lines[0] + lines[2])
    report = store.verify(directory)
    assert "seq_gap" in _kinds(report)
    assert any(
        w.startswith("orphan_record") and r2.run_id in w for w in report.warnings
    )


def test_verify_reports_unreadable_record(tmp_path):
    store, directory, (_r1, r2, _r3) = _seed(tmp_path, 3)
    path = _record_path(directory, r2)
    os.chmod(path, stat.S_IWRITE)
    path.write_bytes(b"{ this is not json")
    report = store.verify(directory)
    assert "unreadable" in _kinds(report)
    # the run is still listed from the index
    assert len(store.list_runs(directory)) == 3


def test_partial_last_index_line_is_tolerated(tmp_path):
    store, directory, _sealed = _seed(tmp_path, 2)
    with open(directory / "index.jsonl", "ab") as handle:
        handle.write(b'{"file": "abc.json", "ru')  # crash mid-append
    report = store.verify(directory)
    assert report.ok and report.checked == 2
    assert any(w.startswith("index_truncated_line") for w in report.warnings)
    # the next commit continues from the last complete line and repairs the tail
    nxt, _path = store.seal_and_save(make_record(), directory)
    assert nxt.seq == 3
    after = store.verify(directory)
    assert after.ok and after.checked == 3


def test_corrupt_middle_index_line_stops_the_walk(tmp_path):
    store, directory, _sealed = _seed(tmp_path, 3)
    index = directory / "index.jsonl"
    lines = index.read_bytes().splitlines(keepends=True)
    index.write_bytes(lines[0] + b"garbage\n" + lines[2])
    report = store.verify(directory)
    assert "index_corrupt" in _kinds(report)
    assert report.checked == 1


def test_missing_index_with_records_is_corrupt(tmp_path):
    store, directory, _sealed = _seed(tmp_path, 2)
    (directory / "index.jsonl").unlink()
    report = store.verify(directory)
    assert _kinds(report) == ["index_corrupt"]


def test_orphan_record_is_warned_not_fatal(tmp_path):
    store, directory, sealed = _seed(tmp_path, 2)
    # crash between record write and index append: a valid record, no index line
    orphan = make_record().to_dict()
    orphan.update(seq=3, prev_record_hash=sealed[-1].record_hash)
    orphan["record_hash"] = compute_record_hash(orphan)
    (directory / f"{orphan['run_id']}.json").write_bytes(orjson.dumps(orphan))
    report = store.verify(directory)
    assert report.ok
    assert any(w.startswith("orphan_record") for w in report.warnings)
    # the next sealed run links to the index head, not to the orphan
    nxt, _ = store.seal_and_save(make_record(), directory)
    assert nxt.prev_record_hash == sealed[-1].record_hash and nxt.seq == 3


def test_incomplete_run_marker_is_reported(tmp_path):
    store, directory, _sealed = _seed(tmp_path, 1)
    marker = store.mark_started("f" * 32, None, directory)
    assert marker is not None and marker.exists()
    report = store.verify(directory)
    assert report.ok
    assert any(w.startswith("incomplete_run") for w in report.warnings)


def test_marker_is_removed_on_seal(tmp_path):
    store = RunStore(app_data_dir=tmp_path)
    directory = tmp_path / "s"
    record = make_record()
    store.mark_started(record.run_id, None, directory)
    assert (directory / f"{record.run_id}.started").exists()
    store.seal_and_save(record, directory)
    assert not (directory / f"{record.run_id}.started").exists()


def test_verify_warns_on_clock_skew(tmp_path):
    store = RunStore(app_data_dir=tmp_path)
    directory = tmp_path / "s"
    store.seal_and_save(
        make_record(
            started_at="2026-10-21T10:00:00.000000Z",
            finished_at="2026-10-21T10:00:05.000000Z",
        ),
        directory,
    )
    store.seal_and_save(
        make_record(
            started_at="2026-10-21T09:00:00.000000Z",
            finished_at="2026-10-21T09:00:05.000000Z",
        ),
        directory,
    )
    report = store.verify(directory)
    assert report.ok
    assert any(w.startswith("clock_skew") for w in report.warnings)


def test_verify_ignores_formatting_changes(tmp_path):
    store, directory, (r1, *_rest) = _seed(tmp_path, 2)
    path = _record_path(directory, r1)
    os.chmod(path, stat.S_IWRITE)
    data = orjson.loads(path.read_bytes())
    path.write_bytes(
        orjson.dumps(dict(reversed(list(data.items()))))
    )  # compact, reordered
    assert store.verify(directory).ok


def test_unknown_key_with_recomputed_hash_verifies_but_stale_hash_fails(tmp_path):
    store, directory, (r1, *_rest) = _seed(tmp_path, 1)
    path = _record_path(directory, r1)
    _edit(path, lambda d: d.update(x_future=1))
    assert _kinds(store.verify(directory)) == ["record_hash_mismatch"]


def test_verify_record_file_standalone(tmp_path):
    _store, directory, (r1, *_rest) = _seed(tmp_path, 2)
    path = _record_path(directory, r1)
    copy = tmp_path / "exported.json"
    copy.write_bytes(path.read_bytes())
    assert verify_record_file(copy).ok
    _edit(copy, lambda d: d.update(status="failed"))
    report = verify_record_file(copy)
    assert not report.ok and _kinds(report) == ["record_hash_mismatch"]
    assert verify_record_file(tmp_path / "nope.json").problems[0].kind == "unreadable"


def test_record_file_is_pretty_and_hash_matches_canonical(tmp_path):
    _store, directory, (r1, *_rest) = _seed(tmp_path, 1)
    path = _record_path(directory, r1)
    raw = path.read_bytes()
    assert raw.count(b"\n") > 20
    data = orjson.loads(raw)
    assert compute_record_hash(data) == data["record_hash"] == r1.record_hash


@pytest.mark.xfail(strict=False, reason="elevated users can write read-only files")
def test_record_file_is_read_only(tmp_path):
    _store, directory, (r1, *_rest) = _seed(tmp_path, 1)
    assert not os.access(_record_path(directory, r1), os.W_OK)


def test_two_threads_seal_without_forking_the_chain(tmp_path):
    store = RunStore(app_data_dir=tmp_path / "ad")
    directory = tmp_path / "shared"
    results: list = []
    errors: list = []

    def worker():
        try:
            for _ in range(5):
                results.append(store.seal_and_save(make_record(), directory)[0])
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert not errors, errors
    assert sorted(r.seq for r in results) == list(range(1, 41))
    ordered = sorted(results, key=lambda r: r.seq)
    for before, after in itertools.pairwise(ordered):
        assert after.prev_record_hash == before.record_hash
    report = store.verify(directory)
    assert report.ok and report.checked == 40


def test_stale_lock_is_removed(tmp_path):
    store = RunStore(app_data_dir=tmp_path / "ad")
    directory = tmp_path / "s"
    directory.mkdir()
    lock = directory / ".lock"
    lock.write_text("123")
    old = time.time() - 120
    os.utime(lock, (old, old))
    sealed, _ = store.seal_and_save(make_record(), directory)
    assert sealed.seq == 1
    assert not lock.exists()


def test_lock_timeout_falls_back(tmp_path, monkeypatch):
    monkeypatch.setattr(store_mod, "LOCK_TIMEOUT_S", 0.2)
    store = RunStore(app_data_dir=tmp_path / "ad")
    wf = tmp_path / "wf.tds"
    wf.write_text("{}")
    primary = store.store_dir_for(str(wf))
    primary.mkdir(parents=True)
    (primary / ".lock").write_text("held")  # fresh lock: not stale
    record = make_record(workflow_path=str(wf).replace("\\", "/"))
    sealed, path = store.seal_and_save(record)
    fallback = store.fallback_dir_for(record.workflow_path)
    assert Path(path).parent == fallback
    assert any("fallback folder" in w for w in sealed.warnings)
    with pytest.raises(StoreLockTimeout), store_mod.store_lock(primary):
        pass


def test_readonly_folder_falls_back(tmp_path, monkeypatch):
    store = RunStore(app_data_dir=tmp_path / "ad")
    wf = tmp_path / "wf.tds"
    wf.write_text("{}")
    primary = store.store_dir_for(str(wf))
    real = os.makedirs

    def deny(name, *args, **kwargs):
        if Path(name) == primary:
            raise PermissionError("read-only")
        return real(name, *args, **kwargs)

    monkeypatch.setattr(store_mod.os, "makedirs", deny)
    record = make_record(workflow_path=wf.as_posix())
    sealed, path = store.seal_and_save(record)
    assert Path(path).parent == store.fallback_dir_for(record.workflow_path)
    assert any("workflow folder is read-only" in w for w in sealed.warnings)
    assert not primary.exists()


def _h8(path: str) -> str:
    return hashlib.sha1(os.path.abspath(path).lower().encode()).hexdigest()[:8]


def test_resolve_store_dir_cases(tmp_path):
    wf = str(tmp_path / "Q3" / "orders.tds")
    ad = tmp_path / "appdata"
    log = tmp_path / "logs"
    assert resolve_store_dir(wf, str(log), ad) == log / f"orders-{_h8(wf)}"
    assert resolve_store_dir(None, str(log), ad) == log / "_unsaved"
    assert resolve_store_dir(wf, "", ad) == Path(wf).parent / "orders.runs"
    assert resolve_store_dir(None, "", ad) == ad / "runs" / "_unsaved"
    store = RunStore(app_data_dir=ad)
    assert store.fallback_dir_for(wf) == ad / "runs" / f"orders-{_h8(wf)}"
    assert store.fallback_dir_for(None) == ad / "runs" / "_unsaved"


def test_same_stem_in_two_folders_do_not_share_a_chain(tmp_path):
    a = str(tmp_path / "a" / "wf.tds")
    b = str(tmp_path / "b" / "wf.tds")
    assert resolve_store_dir(a, "x", None) != resolve_store_dir(b, "x", None)


def test_list_runs_reads_index_only(tmp_path):
    store, directory, (r1, r2, r3) = _seed(tmp_path, 3)
    path = _record_path(directory, r2)
    os.chmod(path, stat.S_IWRITE)
    path.unlink()
    runs = store.list_runs(directory)
    assert [r.seq for r in runs] == [1, 2, 3]
    assert runs[2].record_hash == r3.record_hash and runs[0].run_id == r1.run_id
    assert runs[0].file == f"{r1.run_id}.json"


def test_latest_record_dict_and_load(tmp_path):
    store, directory, sealed = _seed(tmp_path, 2)
    latest = store.latest_record_dict(directory)
    assert latest["run_id"] == sealed[-1].run_id
    assert store.load(_record_path(directory, sealed[0])).seq == 1
    assert store.latest_record_dict(tmp_path / "empty") is None
