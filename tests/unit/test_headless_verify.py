"""``verify-log``: record checks V1-V6 (plan 08 6.4)."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path

import pytest

from tests.support.audit_helpers import make_fingerprint, make_node, make_record
from tests.support.cli import call_main
from trigger_designer.core.audit.store import RunStore
from trigger_designer.core.headless.verify import verify_folder, verify_record


@pytest.fixture
def world(tmp_path):
    """An input, an output, a workflow and a sealed record describing them."""
    src = tmp_path / "in.csv"
    out = tmp_path / "out.csv"
    wf = tmp_path / "wf.tds"
    src.write_bytes(b"a,b\n1,2\n")
    out.write_bytes(b"a,b\n1,2\n3,4\n")
    wf.write_bytes(b'{"nodes": [], "edges": []}')

    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    record = make_record(
        workflow_path=str(wf),
        workflow_sha256=sha(wf),
        inputs=[
            make_fingerprint(
                "input", str(src), sha256=sha(src), size_bytes=src.stat().st_size
            )
        ],
        outputs=[
            make_fingerprint(
                "output",
                str(out),
                sha256=sha(out),
                size_bytes=out.stat().st_size,
                node_id=3,
            )
        ],
    )
    store = RunStore("", tmp_path / "data")
    _sealed, path = store.seal_and_save(record, tmp_path / "rec")
    return {"src": src, "out": out, "wf": wf, "path": path, "dir": tmp_path / "rec"}


def _errors(findings):
    return [f for f in findings if f.level == "error"]


def test_pristine_record_verifies(world):
    assert verify_record(world["path"], workflow=str(world["wf"])) == []
    assert call_main(["verify-log", world["path"], "--workflow", world["wf"]]).code == 0


def test_flipped_record_byte_is_an_error(world):
    path = world["path"]
    os.chmod(path, stat.S_IWRITE | stat.S_IREAD)  # sealed records are read-only
    text = Path(path).read_text(encoding="utf-8")
    assert '"status": "ok"' in text or '"status":"ok"' in text
    Path(path).write_text(text.replace('"ok"', '"failed"', 1), encoding="utf-8")
    findings = verify_record(path)
    assert _errors(findings)
    result = call_main(["verify-log", path])
    assert result.code == 10 and "VERIFICATION FAILED" in result.stdout


def test_deleted_or_extended_output_is_an_error(world):
    world["out"].write_bytes(b"a,b\n1,2\n3,4\n5,6\n")
    messages = [f.message for f in _errors(verify_record(world["path"]))]
    assert any("size changed" in m or "content changed" in m for m in messages)
    world["out"].unlink()
    assert any("missing" in f.message for f in _errors(verify_record(world["path"])))


def test_same_size_content_change_is_an_error(world):
    world["out"].write_bytes(b"a,b\n1,2\n3,5\n")
    assert any(
        "content changed" in f.message for f in _errors(verify_record(world["path"]))
    )


def test_edited_workflow_is_an_error_only_when_given(world):
    world["wf"].write_bytes(b'{"nodes": [], "edges": [], "x": 1}')
    assert verify_record(world["path"]) == []
    assert any(
        "differs" in f.message
        for f in _errors(verify_record(world["path"], workflow=str(world["wf"])))
    )


def test_changed_or_missing_input_only_warns(world):
    world["src"].write_bytes(b"different\n")
    findings = verify_record(world["path"])
    assert not _errors(findings) and findings[0].level == "warning"
    world["src"].unlink()
    findings = verify_record(world["path"])
    assert not _errors(findings) and "no longer present" in findings[0].message
    assert call_main(["verify-log", world["path"]]).code == 0


def test_no_files_skips_output_checks(world):
    world["out"].unlink()
    assert verify_record(world["path"], check_files=False) == []
    assert call_main(["verify-log", world["path"], "--no-files"]).code == 0


def test_status_consistency(world):
    sealed = make_record(
        status="ok",
        nodes=[
            make_node(1, status="ok"),
            make_node(2, status="failed", error={"code": "X"}),
        ],
    )
    _s, path = RunStore("", world["dir"].parent / "d2").seal_and_save(
        sealed, world["dir"].parent / "d2"
    )
    assert any("did not succeed" in f.message for f in _errors(verify_record(path)))


def test_unreadable_record(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("nope")
    assert _errors(verify_record(bad))
    assert call_main(["verify-log", bad]).code == 10


def test_folder_verifies_the_chain(world):
    assert verify_folder(world["dir"]) == []
    result = call_main(["verify-log", world["dir"], "--format", "json"])
    assert result.code == 0 and json.loads(result.stdout)["ok"] is True
    world["out"].unlink()
    assert call_main(["verify-log", world["dir"]]).code == 10


def test_no_argument_checks_the_newest_record(world, tmp_path):
    env = {"TRIGGER_DESIGNER_DATA_DIR": str(tmp_path / "appdata")}
    missing = call_main(["verify-log"], env=env)
    assert missing.code == 2
    store = RunStore("", tmp_path / "appdata")
    store.seal_and_save(
        make_record(inputs=[], outputs=[]), tmp_path / "appdata" / "runs" / "x"
    )
    assert call_main(["verify-log"], env=env).code == 0


def test_missing_target_is_invalid(tmp_path):
    result = call_main(["verify-log", tmp_path / "nope.json"])
    assert result.code == 2
