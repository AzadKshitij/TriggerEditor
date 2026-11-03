"""HTML and JSON export of a run record (plan 02 3.16)."""

from __future__ import annotations

import re
from pathlib import Path

import orjson

from tests.support.audit_helpers import make_node, make_record, make_record_dict
from trigger_designer.core.audit.export import export_json, render_html
from trigger_designer.core.audit.store import (
    RunStore,
    VerifyProblem,
    VerifyReport,
    verify_record_file,
)

XSS = "<script>alert(1)</script>"


def _hostile():
    record = make_record_dict(workflow_path="C:/x/<b>wf</b>.tds")
    record["nodes"][0]["title"] = XSS
    record["nodes"][1] = make_node(
        2,
        status="failed",
        error={
            "code": "TD-SYS-999",
            "title": "bad & <i>worse</i>",
            "detail": "d",
            "hint": "h",
            "technical": "oops </script><script>alert(2)</script>",
        },
        settings={"note": XSS},
    )
    record["generated_code"] = "print('</script>')\n"
    record["warnings"] = [XSS]
    return record


def test_html_escapes_everything():
    page = render_html(_hostile())
    # only the template's own tags exist: the injected script never appears raw
    assert XSS not in page
    assert "alert(2)</script>" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert page.count("<script") == 1  # the embedded json block only
    embedded = re.search(
        r'<script type="application/json" id="run-record">(.*?)</script>',
        page,
        re.DOTALL,
    ).group(1)
    assert "<" not in embedded and "\\u003c" in embedded
    # the embedded copy round-trips to the original record
    assert orjson.loads(embedded) == _hostile()


def test_html_contains_hashes_nodes_and_errors():
    record = _hostile()
    record["record_hash"] = "ab" * 32
    page = render_html(record)
    for expected in (
        "ab" * 32,
        record["inputs"][0]["sha256"],
        "TD-SYS-999",
        "File Input" if False else "Out",
        "preparation.select",
        "failed",
    ):
        assert expected in page
    assert "Generated code" in page


def test_html_is_self_contained():
    page = render_html(make_record_dict())
    assert "http://" not in page and "https://" not in page
    assert not re.search(r"<(link|img|iframe)\b", page)
    assert "src=" not in page


def test_html_integrity_box_reports_verification():
    record = make_record_dict()
    ok = VerifyReport(True, 3, [], [], "cd" * 32)
    bad = VerifyReport(
        False,
        3,
        [VerifyProblem("a" * 32, "record_hash_mismatch", "changed <x>")],
        [],
        None,
    )
    assert "verified" in render_html(record, ok) and "cd" * 32 in render_html(
        record, ok
    )
    page = render_html(record, bad)
    assert "verification failed" in page and "record_hash_mismatch" in page
    assert "changed &lt;x&gt;" in page
    assert "Chain check" not in render_html(record)


def test_html_handles_record_without_code_or_nodes():
    record = make_record_dict(generated_code=None, nodes=[], inputs=[], outputs=[])
    page = render_html(record)
    assert "not embedded" in page and "None." in page


def test_export_json_is_byte_identical_and_verifies(tmp_path):
    store = RunStore(app_data_dir=tmp_path / "ad")
    sealed, path = store.seal_and_save(make_record(), tmp_path / "s")
    target = tmp_path / "exports" / "run.json"
    assert export_json(path, target) == str(target)
    assert target.read_bytes() == Path(path).read_bytes()
    assert verify_record_file(target).ok
    assert sealed.record_hash in target.read_text(encoding="utf-8")


def _benford_summary(**over) -> dict:
    summary = {
        "test_id": "audit.benford#7",
        "test_name": "Benford <first digit>",
        "node_id": 7,
        "status": "fail",
        "population_rows": 1000,
        "exception_rows": 12,
        "exception_rate": 0.012,
        "criteria": "MAD > 0.015",
        "message": "Distribution differs from Benford's law",
        "code": "TD-AUDIT-101",
    }
    summary.update(over)
    return summary


def test_html_has_a_tests_section_with_the_stored_summaries():
    record = make_record_dict()
    record["nodes"][1]["op"] = "audit.benford"
    record["nodes"][1]["test_summary"] = _benford_summary()
    page = render_html(record)
    assert "<h2>Tests</h2>" in page
    tests = page.split("<h2>Tests</h2>", 1)[1].split("<h2>", 1)[0]
    for expected in (
        "Benford &lt;first digit&gt;",  # escaped
        '<span class="failed">fail</span>',
        "1,000",
        "12",
        "1.2%",
        "MAD &gt; 0.015",
        "Distribution differs",
        "TD-AUDIT-101",
    ):
        assert expected in tests, expected
    assert "Benford <first digit></td>" not in page  # never raw


def test_html_tests_section_says_when_the_run_had_no_audit_tests():
    page = render_html(make_record_dict())
    assert "No audit tests in this run." in page
