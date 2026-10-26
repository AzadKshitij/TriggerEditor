"""Unit tests for file discovery, ordering, errors and ResolvedFile."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

import orjson
import pytest

from tests.support.input_fixtures import (
    monthly_csvs,
    natural_order_csvs,
    nested_csvs,
    write_text,
)
from trigger_designer.core.inputs import (
    DEFAULT_EXCLUDE,
    InputReadError,
    detect_file_type,
    effective_mode,
    glob_to_regex,
    io_path,
    list_source_files,
    natural_key,
    resolve_input_files,
    resolve_stored_path,
    to_stored_paths,
)


def _names(listing) -> list[str]:
    return [Path(item.path).name for item in listing.files]


def test_natural_key_orders_numbers() -> None:
    assert sorted(["part_10", "part_2", "part_1"], key=natural_key) == [
        "part_1",
        "part_2",
        "part_10",
    ]
    assert sorted(["B", "a"], key=natural_key) == ["a", "B"]
    first = sorted(["a", "A"], key=natural_key)
    assert first == sorted(["A", "a"], key=natural_key)


def test_glob_to_regex_cases() -> None:
    assert glob_to_regex("*.csv").match("Jan.CSV")
    assert not glob_to_regex("*.csv").match("a/b.csv")
    assert glob_to_regex("**/*.csv").match("a/b/c.csv")
    assert glob_to_regex("**/*.csv").match("c.csv")
    assert glob_to_regex("?.csv").match("a.csv")
    assert glob_to_regex("[ab]x.csv").match("Ax.csv")
    assert not glob_to_regex("[ab]x.csv").match("cx.csv")


def test_glob_case_insensitive(tmp_path) -> None:
    monthly = monthly_csvs(tmp_path)
    listing = list_source_files(str(monthly / "SALES_*.CSV"), "csv")
    assert _names(listing) == [
        "sales_2024-01.csv",
        "sales_2024-02.csv",
        "sales_2024-03.csv",
    ]


def test_effective_mode(tmp_path) -> None:
    monthly = monthly_csvs(tmp_path)
    assert effective_mode("") == "empty"
    assert effective_mode(str(monthly)) == "folder"
    assert effective_mode(str(monthly / "*.csv")) == "pattern"
    assert effective_mode(str(monthly / "sales_2024-01.csv")) == "single"


def test_folder_listing_default_include_and_exclude(tmp_path) -> None:
    monthly = monthly_csvs(tmp_path)
    listing = list_source_files(str(monthly), "csv")
    assert _names(listing) == [
        "sales_2024-01.csv",
        "sales_2024-02.csv",
        "sales_2024-03.csv",
    ]
    assert listing.mode == "folder"
    assert listing.excluded_count >= 3


def test_lock_files_excluded_by_default(tmp_path) -> None:
    monthly = monthly_csvs(tmp_path)
    names = _names(list_source_files(str(monthly), "csv"))
    assert "~$sales_2024-04.csv" not in names
    assert ".hidden.csv" not in names
    assert "~$*" in DEFAULT_EXCLUDE


def test_exclude_override(tmp_path) -> None:
    monthly = monthly_csvs(tmp_path)
    names = _names(list_source_files(str(monthly), "csv", exclude=()))
    assert "~$sales_2024-04.csv" in names
    assert ".hidden.csv" in names


def test_include_override(tmp_path) -> None:
    monthly = monthly_csvs(tmp_path)
    listing = list_source_files(str(monthly), "csv", include=("sales_2024-0[12].csv",))
    assert _names(listing) == ["sales_2024-01.csv", "sales_2024-02.csv"]


def test_natural_order_folder(tmp_path) -> None:
    natural = natural_order_csvs(tmp_path)
    assert _names(list_source_files(str(natural), "csv")) == [
        "part_1.csv",
        "part_2.csv",
        "part_10.csv",
    ]


def test_modified_order(tmp_path) -> None:
    natural = natural_order_csvs(tmp_path)
    os.utime(natural / "part_10.csv", (1_000_000, 1_000_000))
    os.utime(natural / "part_2.csv", (2_000_000, 2_000_000))
    os.utime(natural / "part_1.csv", (3_000_000, 3_000_000))
    listing = list_source_files(str(natural), "csv", order="modified")
    assert _names(listing) == ["part_10.csv", "part_2.csv", "part_1.csv"]


def test_recursive_toggle(tmp_path) -> None:
    nested = nested_csvs(tmp_path)
    assert _names(list_source_files(str(nested), "csv")) == ["top.csv"]
    listing = list_source_files(str(nested), "csv", recursive=True)
    assert _names(listing) == ["data.csv", "data.csv", "top.csv"]
    assert sorted(item.relative_path for item in listing.files) == [
        "a/data.csv",
        "b/data.csv",
        "top.csv",
    ]


def test_recursive_same_basename(tmp_path) -> None:
    nested = nested_csvs(tmp_path)
    listing = list_source_files(str(nested), "csv", recursive=True)
    assert sum(Path(item.path).name == "data.csv" for item in listing.files) == 2


def test_pattern_zero_matches(tmp_path) -> None:
    monthly = monthly_csvs(tmp_path)
    with pytest.raises(InputReadError) as error:
        list_source_files(str(monthly / "nope_*.csv"), "csv")
    assert error.value.kind == "no_match"
    assert error.value.code == "TD-IN-001"
    assert "nope_*.csv" in str(error.value)


def test_empty_folder_raises_no_match(tmp_path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(InputReadError) as error:
        list_source_files(str(empty), "csv")
    assert error.value.kind == "no_match"
    assert str(empty) in str(error.value)


@pytest.mark.parametrize(
    ("kind", "code"),
    [
        ("empty_file", "TD-IN-005"),
        ("parse", "TD-IN-010"),
        ("unreadable", "TD-IN-011"),
        ("too_many_files", "TD-IN-012"),
        ("db_error", "TD-IN-013"),
        ("config", "TD-IN-014"),
        ("column_conflict", "TD-SCH-010"),
        ("schema_mismatch", "TD-SCH-011"),
    ],
)
def test_error_codes(kind: str, code: str) -> None:
    error = InputReadError(kind, "message")
    assert error.code == code


def test_too_many_files(tmp_path) -> None:
    monthly = monthly_csvs(tmp_path)
    with pytest.raises(InputReadError) as error:
        list_source_files(str(monthly), "csv", max_files=2)
    assert error.value.kind == "too_many_files"


def test_single_file_ignores_exclude(tmp_path) -> None:
    lock = write_text(tmp_path / "~$x.csv", "id\n1\n")
    listing = list_source_files(str(lock), "csv")
    assert _names(listing) == ["~$x.csv"]


def test_symlink_file_followed(tmp_path) -> None:
    target = write_text(tmp_path / "real.csv", "id\n1\n")
    link = tmp_path / "link.csv"
    try:
        os.symlink(target, link)
    except OSError:
        pytest.skip("symlinks need privileges on this Windows setup")
    listing = list_source_files(str(tmp_path), "csv")
    assert "link.csv" in _names(listing)


def test_symlink_dir_not_followed(tmp_path) -> None:
    real = tmp_path / "real"
    write_text(real / "inner.csv", "id\n1\n")
    root = tmp_path / "root"
    write_text(root / "top.csv", "id\n2\n")
    try:
        os.symlink(real, root / "linked")
    except OSError:
        pytest.skip("symlinks need privileges on this Windows setup")
    listing = list_source_files(str(root), "csv", recursive=True)
    assert _names(listing) == ["top.csv"]


def test_unicode_file_names(tmp_path) -> None:
    directory = tmp_path / "unicode"
    write_text(directory / "données_é_日本.csv", "id\n1\n")
    listing = list_source_files(str(directory), "csv")
    assert Path(listing.files[0].path).name == "données_é_日本.csv"
    resolved = resolve_input_files({"filePath": str(directory), "file_type": "csv"})
    assert resolved[0].exists
    assert Path(resolved[0].path).name == "données_é_日本.csv"


@pytest.mark.skipif(os.name != "nt", reason="Windows long-path prefix")
def test_long_path_prefix() -> None:
    prefixed = io_path("C:\\" + "a" * 250)
    assert prefixed.startswith("\\\\?\\")


def test_io_path_identity_elsewhere(tmp_path) -> None:
    assert io_path(str(tmp_path)) == str(tmp_path.resolve())


def test_stored_paths_roundtrip(tmp_path) -> None:
    target = write_text(tmp_path / "a" / "b.csv", "id\n1\n")
    workflow = tmp_path / "w"
    workflow.mkdir()
    absolute, relative = to_stored_paths(str(target), str(workflow))
    assert absolute == str(target)
    assert relative == "../a/b.csv"
    assert resolve_stored_path(absolute, relative, str(workflow)) == str(
        target.resolve()
    )
    target.unlink()
    assert resolve_stored_path(absolute, relative, str(workflow)) == absolute


def test_stored_paths_no_workflow_dir(tmp_path) -> None:
    target = write_text(tmp_path / "a.csv", "id\n1\n")
    absolute, relative = to_stored_paths(str(target), None)
    assert absolute == str(target)
    assert relative == ""
    assert resolve_stored_path(absolute, relative, None) == absolute


def test_to_stored_paths_other_drive(tmp_path, monkeypatch) -> None:
    def raise_value(*_args, **_kwargs):
        raise ValueError("different drive")

    monkeypatch.setattr(os.path, "relpath", raise_value)
    _absolute, relative = to_stored_paths(str(tmp_path / "a.csv"), str(tmp_path))
    assert relative == ""


def test_detect_file_type(tmp_path) -> None:
    sqlite = tmp_path / "real.db"
    sqlite.write_bytes(b"SQLite format 3\x00" + b"\x00" * 16)
    other = tmp_path / "other.db"
    other.write_bytes(b"not a sqlite file")
    assert detect_file_type(str(sqlite)) == "sqlite"
    assert detect_file_type(str(other)) == "duckdb"
    assert detect_file_type("x.parquet") == "parquet"
    assert detect_file_type("x.jsonl") == "ndjson"
    assert detect_file_type("x.xlsm") == "excel"
    assert detect_file_type("x.unknown") == "csv"


def test_resolved_files_fields_and_hash(tmp_path) -> None:
    monthly = monthly_csvs(tmp_path)
    state = {"filePath": str(monthly), "file_type": "csv"}
    resolved = resolve_input_files(state)
    assert len(resolved) == 3
    first = resolved[0]
    assert first.exists and first.kind == "csv"
    assert first.size_bytes == (monthly / "sales_2024-01.csv").stat().st_size
    assert first.modified_time.endswith("Z")
    assert first.sha256 is None
    assert first.relative_path == "sales_2024-01.csv"

    hashed = resolve_input_files(state, hash=True)
    expected = hashlib.sha256((monthly / "sales_2024-01.csv").read_bytes()).hexdigest()
    assert hashed[0].sha256 == expected


def test_resolve_input_files_never_raises(tmp_path) -> None:
    missing = tmp_path / "missing.csv"
    resolved = resolve_input_files({"filePath": str(missing), "file_type": "csv"})
    assert len(resolved) == 1
    assert not resolved[0].exists
    assert resolved[0].path == str(missing)


def test_input_read_error_as_dict_and_str() -> None:
    error = InputReadError(
        "locked",
        "Cannot read 'C:\\x\\Jan.csv': the file is open in another program.",
        path="C:\\x\\Jan.csv",
        column="amount",
        technical="PermissionError",
        cause_type="PermissionError",
    )
    assert "Jan.csv" in str(error)
    assert error.code == "TD-IN-002"
    assert orjson.loads(orjson.dumps(error.as_dict()))["column"] == "amount"


def test_corrupt_workbook_code() -> None:
    error = InputReadError(
        "parse",
        "The workbook is damaged.",
        technical="CalamineError: invalid Zip archive",
    )
    assert error.code == "TD-IN-006"


def test_inputs_module_is_polars_free() -> None:
    root = Path(__file__).resolve().parents[2]
    code = (
        "import sys;"
        f"sys.path.insert(0, {str(root / 'src')!r});"
        "import trigger_designer.core.inputs;"
        "print('polars' in sys.modules)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == "False"
