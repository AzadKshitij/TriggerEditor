"""Path resolution rules (plan 08 3.6)."""

from __future__ import annotations

import os

import pytest

from trigger_designer.core.headless.exit_codes import CliError
from trigger_designer.core.headless.paths import (
    basename_any,
    is_codegen_safe_dir,
    relativize,
    remap_into_dir,
    resolve_workflow_path,
)

NT = os.name == "nt"
BASE = "C:\\work\\wf" if NT else "/work/wf"


def _n(*parts: str) -> str:
    return os.path.normpath(os.path.join(*parts))


def test_relative_joins_base_dir_not_cwd():
    assert resolve_workflow_path("data/in.csv", base_dir=BASE) == _n(
        BASE, "data", "in.csv"
    )


def test_dotdot_is_normalised():
    assert resolve_workflow_path("../x.csv", base_dir=BASE) == _n(BASE, "..", "x.csv")


def test_absolute_is_kept():
    absolute = "C:\\data\\in.csv" if NT else "/data/in.csv"
    assert resolve_workflow_path(absolute, base_dir=BASE) == os.path.normpath(absolute)


@pytest.mark.skipif(NT, reason="a drive path is native on Windows")
def test_windows_drive_path_on_posix_is_unchanged():
    assert resolve_workflow_path("C:\\a\\b.csv", base_dir=BASE) == os.path.normpath(
        "C:\\a\\b.csv"
    )


@pytest.mark.skipif(NT, reason="POSIX only")
def test_backslash_relative_on_posix():
    assert resolve_workflow_path("a\\b.csv", base_dir=BASE) == "/work/wf/a/b.csv"


@pytest.mark.parametrize(
    "raw", ["http://x/y.csv", "https://x", "s3://bucket/key", "file://x"]
)
def test_urls_are_refused(raw):
    with pytest.raises(CliError) as exc:
        resolve_workflow_path(raw, base_dir=BASE)
    assert exc.value.td_code == "TD-CLI-006"


def test_drive_letter_is_not_a_url():
    resolve_workflow_path("C:\\x.csv", base_dir=BASE)


def test_empty_is_td_in_001():
    with pytest.raises(CliError) as exc:
        resolve_workflow_path("   ", base_dir=BASE)
    assert exc.value.td_code == "TD-IN-001"


def test_nul_is_refused():
    with pytest.raises(CliError) as exc:
        resolve_workflow_path("a\x00b", base_dir=BASE)
    assert exc.value.td_code == "TD-CLI-006"


def test_unicode_and_space_survive():
    got = resolve_workflow_path("r\xe9sum\xe9 data/a b.csv", base_dir=BASE)
    assert got.endswith(_n("r\xe9sum\xe9 data", "a b.csv"))


@pytest.mark.skipif(not NT, reason="UNC paths are a Windows concept")
def test_unc_is_absolute():
    assert resolve_workflow_path("\\\\server\\share\\a.csv", base_dir=BASE).startswith(
        "\\\\server\\share"
    )


def test_no_home_or_env_expansion():
    assert "~" in resolve_workflow_path("~/x.csv", base_dir=BASE)
    assert "%TEMP%" in resolve_workflow_path("%TEMP%/x.csv", base_dir=BASE)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("C:\\a\\b.csv", "b.csv"),
        ("/a/b.csv", "b.csv"),
        ("a\\b/c.csv", "c.csv"),
        ("x\\", "x"),
    ],
)
def test_basename_any(raw, expected):
    assert basename_any(raw) == expected


def test_remap_into_dir_uses_either_separator(tmp_path):
    for raw in ("C:\\Projects\\data\\check.csv", "/srv/data/check.csv"):
        assert remap_into_dir(raw, str(tmp_path)) == str(tmp_path / "check.csv")


def test_relativize_inside_outside(tmp_path):
    inside = tmp_path / "sub" / "a.csv"
    assert relativize(str(inside), str(tmp_path)) == "sub/a.csv"
    assert relativize(str(tmp_path.parent / "other.csv"), str(tmp_path)) is None
    assert relativize(str(tmp_path), str(tmp_path)) is None


@pytest.mark.skipif(not NT, reason="case-insensitive drives are Windows only")
def test_relativize_ignores_case_and_other_drive():
    assert relativize("C:\\Work\\WF\\a.csv", "c:\\work\\wf") == "a.csv"
    assert relativize("D:\\work\\wf\\a.csv", "C:\\work\\wf") is None


@pytest.mark.parametrize("bad", list("'\"{}") + ["\r", "\n", "\x00"])
def test_codegen_unsafe_chars(bad):
    assert not is_codegen_safe_dir(f"C:/out{bad}dir")


def test_codegen_safe_plain_and_unicode():
    assert is_codegen_safe_dir("C:/out/r\xe9sum\xe9 data")
