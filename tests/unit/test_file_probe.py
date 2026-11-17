"""Type judgement and listing for ``profile_file`` / ``list_files`` (AI plan)."""

from __future__ import annotations

import polars as pl
import pytest

from trigger_designer.core.headless.access_policy import AccessPolicy
from trigger_designer.core.headless.file_probe import (
    MAX_LISTED,
    _infer,
    list_workspace_files,
    probe_file,
)

pytestmark = pytest.mark.unit


def _kinds(**columns: list) -> dict[str, str]:
    return _infer(
        pl.DataFrame({k: pl.Series(v, dtype=pl.String) for k, v in columns.items()})
    )


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        (["1", "20", "-3", "+4"], "Int64"),
        (["1.5", "20", ".5", "1e3"], "Float64"),
        (["2026-01-05", "2026-12-31"], "Date"),
        (["2026-01-05 10:30", "2026-01-05T10:30:15"], "Datetime"),
        (["true", "False", "TRUE"], "Boolean"),
        (["007", "008"], "String"),  # leading zeros: an identifier
        (["1,234.50", "2,000"], "String"),  # a thousands separator is not a number
        (["$10", "$20"], "String"),
        (["1", "two"], "String"),
        (["2026-13-45"], "String"),  # looks like a date but is not one
        (["12", None, "  ", "7"], "Int64"),  # blanks and nulls are ignored
        ([None, None], "String"),
        (["99999999999999999999"], "Float64"),  # too big for Int64
    ],
)
def test_a_text_column_is_judged_by_every_value_in_the_sample(values, expected):
    assert _kinds(c=values) == {"c": expected}


def test_a_negative_zero_prefix_number_is_still_a_number():
    assert _kinds(c=["0", "0.5", "10"]) == {"c": "Float64"}
    assert _kinds(c=["0", "10"]) == {"c": "Int64"}


def test_a_csv_is_described_level_by_level(tmp_path):
    path = tmp_path / "t.csv"
    path.write_text("id,amount\n001,10.5\n002,20\n", encoding="utf-8")

    low = probe_file(path, AccessPolicy())
    assert [c["dtype"] for c in low["columns"]] == ["String", "String"]
    assert "row_count" not in low and "suggested_select" not in low

    mid = probe_file(path, AccessPolicy(level="aggregates"))
    assert mid["row_count"] == 2 and "rows" not in mid
    assert {c["name"]: c["can_convert_to"] for c in mid["columns"]} == {
        "id": "String",
        "amount": "Float64",
    }

    high = probe_file(path, AccessPolicy(level="rows", max_rows=1))
    assert high["rows"] == [{"id": "001", "amount": "10.5"}]


@pytest.mark.parametrize(
    ("name", "text", "columns"),
    [
        ("semi.csv", "a;b\n1;2\n", ["a", "b"]),
        ("tabs.tsv", "a\tb\n1\t2\n", ["a", "b"]),
        ("pipes.txt", "a|b\n1|2\n", ["a", "b"]),
    ],
)
def test_the_separator_is_found(tmp_path, name, text, columns):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    assert [c["name"] for c in probe_file(path, AccessPolicy())["columns"]] == columns


def test_a_parquet_file_keeps_its_real_types(tmp_path):
    path = tmp_path / "t.parquet"
    pl.DataFrame({"n": [1, 2], "s": ["a", "b"]}).write_parquet(path)

    body = probe_file(path, AccessPolicy(level="aggregates"))

    assert {c["name"]: c["dtype"] for c in body["columns"]} == {
        "n": "Int64",
        "s": "String",
    }
    assert "suggested_select" not in body and "note" not in body
    assert body["row_count"] == 2


def test_a_ragged_or_badly_encoded_file_still_profiles(tmp_path):
    path = tmp_path / "t.csv"
    path.write_bytes(b"a,b\n1,2\n3\n4,5,6\ncaf\xe9,x\n")
    body = probe_file(path, AccessPolicy(level="rows", max_rows=10))
    assert [c["name"] for c in body["columns"]] == ["a", "b"] and body["rows"]


def test_listing_skips_hidden_run_history_and_other_files(tmp_path):
    (tmp_path / "a.csv").write_text("x\n1\n", encoding="utf-8")
    (tmp_path / "w.tds").write_text("{}", encoding="utf-8")
    (tmp_path / "notes.docx").write_bytes(b"x")
    (tmp_path / ".secret.csv").write_text("x\n", encoding="utf-8")
    (tmp_path / "w.runs").mkdir()
    (tmp_path / "w.runs" / "r.json").write_text("{}", encoding="utf-8")
    body = list_workspace_files([tmp_path])
    assert [f["path"] for f in body["files"]] == ["a.csv", "w.tds"]


def test_listing_cannot_leave_the_workspace_and_is_capped(tmp_path):
    (tmp_path / "in").mkdir()
    (tmp_path.parent / "outside_listing.csv").write_text("x\n", encoding="utf-8")
    assert list_workspace_files([tmp_path], "..")["files"] == []
    for i in range(MAX_LISTED + 5):
        (tmp_path / "in" / f"f{i:04}.csv").write_text("x\n", encoding="utf-8")
    body = list_workspace_files([tmp_path])
    assert len(body["files"]) == MAX_LISTED and body["truncated"] is True
