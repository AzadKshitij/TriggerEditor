"""write_workpaper orchestration: paths, versioning, errors, runner (Qt-free)."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

import polars as pl
import pytest

from tests.support.workpaper import EXCEPTIONS, FIXED_NOW, POPULATION, load, make_spec
from trigger_designer.core.excel.errors import ExcelWriteError
from trigger_designer.core.workpaper import (
    WorkpaperError,
    WorkpaperSpec,
    write_workpaper,
)
from trigger_designer.core.workpaper.context import (
    current_run_record,
    set_run_record_provider,
)
from trigger_designer.core.workpaper.node_runner import run_workpaper


def test_end_to_end_writes_sheets_in_order(tmp_path):
    result = write_workpaper(
        make_spec(tmp_path),
        EXCEPTIONS,
        population=POPULATION,
        workflow=[{"step": 1, "title": "T", "op": "a.b", "settings": []}],
        run_record={"run_id": "r", "nodes": []},
        now=FIXED_NOW,
    )
    assert load(result.path).sheetnames == [
        "Summary",
        "Exceptions",
        "Run log",
        "Workflow",
    ]
    assert (
        result.workbook_sha256
        == hashlib.sha256(Path(result.path).read_bytes()).hexdigest()
    )
    assert (result.exceptions_total, result.exceptions_written) == (3, 3)
    assert result.population_rows == 10 and result.exceptions_value == pytest.approx(
        6700.75
    )


def test_if_exists_version_creates_numbered_copy(tmp_path):
    spec = make_spec(tmp_path)
    first = write_workpaper(spec, EXCEPTIONS, now=FIXED_NOW)
    before = Path(first.path).read_bytes()
    second = write_workpaper(spec, EXCEPTIONS, now=FIXED_NOW)
    third = write_workpaper(spec, EXCEPTIONS, now=FIXED_NOW)
    assert (
        Path(second.path).name == "wp (2).xlsx"
        and Path(third.path).name == "wp (3).xlsx"
    )
    assert Path(first.path).read_bytes() == before


def test_if_exists_replace_overwrites(tmp_path):
    spec = make_spec(tmp_path, if_exists="replace")
    write_workpaper(spec, EXCEPTIONS, now=FIXED_NOW)
    again = write_workpaper(spec, EXCEPTIONS.head(1), now=FIXED_NOW)
    assert Path(again.path).name == "wp.xlsx" and again.exceptions_total == 1
    assert [p.name for p in tmp_path.iterdir()] == ["wp.xlsx"]


def test_if_exists_fail_raises_td_out_010(tmp_path):
    spec = make_spec(tmp_path, if_exists="fail")
    write_workpaper(spec, EXCEPTIONS, now=FIXED_NOW)
    with pytest.raises(WorkpaperError) as err:
        write_workpaper(spec, EXCEPTIONS, now=FIXED_NOW)
    assert err.value.code == "TD-OUT-010" and "already exists" in str(err.value)


def test_missing_folder_raises_td_out_001(tmp_path):
    spec = make_spec(tmp_path, output_path=str(tmp_path / "nope" / "wp.xlsx"))
    with pytest.raises(ExcelWriteError) as err:
        write_workpaper(spec, EXCEPTIONS, now=FIXED_NOW)
    assert err.value.code == "TD-OUT-001"


@pytest.mark.parametrize("name", ["", "wp.xls", "wp.csv", "wp"])
def test_wrong_or_empty_output_path_raises_td_out_012(tmp_path, name):
    spec = make_spec(tmp_path, output_path=str(tmp_path / name) if name else "")
    with pytest.raises(WorkpaperError) as err:
        write_workpaper(spec, EXCEPTIONS, now=FIXED_NOW)
    assert err.value.code == "TD-OUT-012"


def test_bad_prepared_date_raises_td_out_012(tmp_path):
    with pytest.raises(WorkpaperError) as err:
        write_workpaper(make_spec(tmp_path, prepared_date="31/03/2026"), EXCEPTIONS)
    assert err.value.code == "TD-OUT-012" and "YYYY-MM-DD" in str(err.value)


def test_blank_prepared_date_uses_now(tmp_path):
    result = write_workpaper(
        make_spec(tmp_path, prepared_date=""), EXCEPTIONS, now=FIXED_NOW
    )
    assert load(result.path)["Summary"]["B11"].value.date().isoformat() == "2026-03-31"


def test_zero_columns_raises(tmp_path):
    with pytest.raises(WorkpaperError):
        write_workpaper(make_spec(tmp_path), pl.DataFrame(), now=FIXED_NOW)


def test_replace_when_excel_lock_file_exists_raises_td_out_002(tmp_path):
    spec = make_spec(tmp_path, if_exists="replace")
    write_workpaper(spec, EXCEPTIONS, now=FIXED_NOW)
    (tmp_path / "~$wp.xlsx").write_bytes(b"lock")
    with pytest.raises(WorkpaperError) as err:
        write_workpaper(spec, EXCEPTIONS, now=FIXED_NOW)
    assert err.value.code == "TD-OUT-002" and "open in Excel" in str(err.value)


def test_replace_when_replace_is_denied_raises_td_out_002(tmp_path, monkeypatch):
    spec = make_spec(tmp_path, if_exists="replace")
    write_workpaper(spec, EXCEPTIONS, now=FIXED_NOW)
    original = Path(spec.output_path).read_bytes()

    def denied(*_a):
        raise PermissionError("locked")

    monkeypatch.setattr(os, "replace", denied)
    with pytest.raises(ExcelWriteError) as err:
        write_workpaper(spec, EXCEPTIONS, now=FIXED_NOW)
    monkeypatch.undo()
    assert err.value.code == "TD-OUT-002"
    assert Path(spec.output_path).read_bytes() == original


@pytest.mark.skipif(
    sys.platform != "win32", reason="exclusive file handles are a Windows thing"
)
def test_replace_when_target_is_really_locked(tmp_path):
    import msvcrt  # noqa: F401 - Windows only

    spec = make_spec(tmp_path, if_exists="replace")
    write_workpaper(spec, EXCEPTIONS, now=FIXED_NOW)
    import ctypes
    from ctypes import wintypes

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateFileW.restype = wintypes.HANDLE
    handle = k32.CreateFileW(
        spec.output_path, 0x80000000, 0, None, 3, 0x80, None
    )  # no sharing
    try:
        with pytest.raises(ExcelWriteError) as err:
            write_workpaper(spec, EXCEPTIONS, now=FIXED_NOW)
        assert err.value.code == "TD-OUT-002"
    finally:
        k32.CloseHandle(handle)


def test_failed_write_leaves_no_partial_target_and_cleans_temp(tmp_path, monkeypatch):
    before = set(Path(tempfile.gettempdir()).glob("td_wp_*"))
    import xlsxwriter

    def boom(self):
        raise xlsxwriter.exceptions.XlsxWriterException("boom")

    monkeypatch.setattr(xlsxwriter.Workbook, "_store_workbook", boom)
    with pytest.raises(ExcelWriteError) as err:
        write_workpaper(make_spec(tmp_path), EXCEPTIONS, now=FIXED_NOW)
    assert err.value.code == "TD-OUT-014"
    assert not (tmp_path / "wp.xlsx").exists()
    assert set(Path(tempfile.gettempdir()).glob("td_wp_*")) == before


def test_eager_dataframe_input_matches_lazy(tmp_path):
    a = write_workpaper(make_spec(tmp_path), EXCEPTIONS, now=FIXED_NOW)
    b = write_workpaper(
        make_spec(tmp_path, output_path=str(tmp_path / "b.xlsx")),
        EXCEPTIONS.lazy(),
        now=FIXED_NOW,
    )
    rows = lambda p: [[c.value for c in r] for r in load(p)["Exceptions"].iter_rows()]
    assert rows(a.path) == rows(b.path)


def test_exceptions_plan_is_executed_once(tmp_path):
    calls = []

    def count(df):
        calls.append(df.height)
        return df

    lazy = EXCEPTIONS.lazy().map_batches(count)
    write_workpaper(make_spec(tmp_path), lazy, now=FIXED_NOW)
    assert len(calls) == 1


def test_xlsxwriter_missing_raises_td_out_003(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "xlsxwriter", None)
    with pytest.raises(ExcelWriteError) as err:
        write_workpaper(make_spec(tmp_path), EXCEPTIONS, now=FIXED_NOW)
    assert err.value.code == "TD-OUT-003"


def test_spec_json_roundtrip_and_unknown_keys_ignored():
    spec = WorkpaperSpec(client="O'Brien", tick_marks=(("a", "b"),))
    again = WorkpaperSpec.from_json(spec.to_json())
    assert again == spec
    data = json.loads(spec.to_json())
    data["future_field"] = 1
    assert WorkpaperSpec.from_json(json.dumps(data)) == spec


def test_run_workpaper_parses_summary_frame(tmp_path):
    summary = pl.DataFrame(
        {
            "test_name": ["From node"],
            "criteria": ["Amount >= 1,500"],
            "status": ["fail"],
            "message": ["m"],
            "population_rows": [10],
            "exception_rows": [3],
            "exception_rate": [0.3],
            "parameters": [json.dumps({"k": 1})],
            "unknown": [1],
        }
    )
    spec = make_spec(tmp_path, test_name="", criteria="")
    out = run_workpaper(
        spec_json=spec.to_json(),
        exceptions=EXCEPTIONS,
        summary=summary.lazy(),
        workflow_json=json.dumps(
            [{"step": 1, "title": "T", "op": "a.b", "settings": []}]
        ),
    )
    ws = load(out["path"])["Summary"]
    assert (
        ws["B9"].value == "From node"
        and ws["B26"].value == "Agrees to the test node (3 exceptions)"
    )
    assert out["exceptions_total"] == 3 and out["sheets"][-1] == "Workflow"


def test_run_workpaper_adds_extra_sources(tmp_path):
    src = tmp_path / "extra.csv"
    src.write_text("a\n1\n")
    out = run_workpaper(
        spec_json=make_spec(tmp_path).to_json(),
        exceptions=EXCEPTIONS,
        sources_json=json.dumps([{"path": str(src)}, str(tmp_path / "other.csv")]),
    )
    values = [
        c.value
        for r in load(out["path"])["Summary"].iter_rows(min_col=1, max_col=1)
        for c in r
    ]
    assert str(src) in values and str(tmp_path / "other.csv") in values


def test_run_workpaper_uses_registered_run_record_provider(tmp_path):
    set_run_record_provider(
        lambda: {"run_id": "provider-run", "status": "running", "nodes": []}
    )
    try:
        assert current_run_record()["run_id"] == "provider-run"
        out = run_workpaper(
            spec_json=make_spec(tmp_path).to_json(), exceptions=EXCEPTIONS
        )
    finally:
        set_run_record_provider(None)
    assert "Run log" in out["sheets"]
    assert current_run_record() is None


def test_provider_failure_never_breaks_the_workpaper(tmp_path):
    def broken():
        raise RuntimeError("no")

    set_run_record_provider(broken)
    try:
        out = run_workpaper(
            spec_json=make_spec(tmp_path).to_json(), exceptions=EXCEPTIONS
        )
    finally:
        set_run_record_provider(None)
    assert "Run log" not in out["sheets"]


# -- publish_path: the CLI writes to a staging name, the file lands elsewhere ----
def _staged_spec(tmp_path, publish: str, **kw):
    staged = tmp_path / ".wp.tdtmp-abc12345.xlsx"
    return make_spec(
        tmp_path, output_path=str(staged), publish_path=publish, row_limit=1, **kw
    )


def test_full_csv_is_named_after_the_publish_path(tmp_path):
    final = tmp_path / "ledger_wp.xlsx"
    result = write_workpaper(
        _staged_spec(tmp_path, str(final)), EXCEPTIONS, now=FIXED_NOW
    )
    assert Path(result.path).name == ".wp.tdtmp-abc12345.xlsx"
    assert result.csv_path == str(tmp_path / "ledger_wp_exceptions_full.csv")
    assert os.path.exists(result.csv_path)
    assert not [p for p in os.listdir(tmp_path) if "tdtmp" in p and p.endswith(".csv")]
    text = " ".join(
        str(c.value) for row in load(result.path)["Summary"].iter_rows() for c in row
    )
    assert "ledger_wp_exceptions_full.csv" in text


def test_publish_path_must_be_xlsx_like_the_output_path(tmp_path):
    with pytest.raises(WorkpaperError, match="xlsx"):
        write_workpaper(
            _staged_spec(tmp_path, str(tmp_path / "x.txt")), EXCEPTIONS, now=FIXED_NOW
        )


# ---------------------------------------------------------------- abandonment
def test_abandoned_write_publishes_nothing(tmp_path):
    from trigger_designer.core.workpaper.spec import WorkpaperAbandoned

    spec = make_spec(tmp_path)
    with pytest.raises(WorkpaperAbandoned):
        write_workpaper(spec, EXCEPTIONS, abandoned=lambda: True)
    assert list(tmp_path.iterdir()) == []


def test_not_abandoned_write_still_publishes(tmp_path):
    result = write_workpaper(make_spec(tmp_path), EXCEPTIONS, abandoned=lambda: False)
    assert result.path and (tmp_path / "wp.xlsx").exists()


def test_abandoned_after_the_workbook_is_built_leaves_no_csv(tmp_path):
    calls = []

    def abandoned():
        calls.append(1)
        return len(calls) >= 2  # fine at the first check, gone at the last one

    from trigger_designer.core.workpaper.spec import WorkpaperAbandoned

    spec = make_spec(tmp_path, row_limit=1)
    with pytest.raises(WorkpaperAbandoned):
        write_workpaper(spec, EXCEPTIONS, abandoned=abandoned)
    assert list(tmp_path.iterdir()) == []


def _provider(record):
    from trigger_designer.core.workpaper.context import set_run_record_provider

    set_run_record_provider(lambda: record)
    return lambda: set_run_record_provider(None)


@pytest.mark.parametrize(
    ("record", "gone"),
    [
        ({"status": "running", "nodes": [{"node_id": 7, "status": "failed"}]}, True),
        ({"status": "running", "nodes": [{"node_id": 3, "status": "failed"}]}, False),
        ({"status": "running", "nodes": []}, False),
        ({"status": "failed", "nodes": []}, True),
        (None, False),
    ],
)
def test_run_workpaper_detects_an_abandoned_step_from_the_run_record(
    tmp_path, record, gone
):
    undo = _provider(record)
    try:
        spec = make_spec(tmp_path)
        if gone:
            from trigger_designer.core.workpaper.spec import WorkpaperAbandoned

            with pytest.raises(WorkpaperAbandoned):
                run_workpaper(
                    spec_json=spec.to_json(), exceptions=EXCEPTIONS, node_id=7
                )
            assert list(tmp_path.iterdir()) == []
        else:
            out = run_workpaper(
                spec_json=spec.to_json(), exceptions=EXCEPTIONS, node_id=7
            )
            assert (tmp_path / "wp.xlsx").exists() and out["path"]
    finally:
        undo()
