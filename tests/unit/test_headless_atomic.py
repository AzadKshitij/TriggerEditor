"""Staged outputs and atomic writes (plan 08 3.8, S5)."""

from __future__ import annotations

import os

import pytest

from trigger_designer.core.headless import atomic
from trigger_designer.core.headless.atomic import (
    commit_all,
    discard_all,
    plan_staging,
    write_json_atomic,
)
from trigger_designer.core.headless.exit_codes import CliError, ExitCode


def _staged(tmp_path, names=("a.csv", "b.csv"), content=b"old"):
    finals = []
    for index, name in enumerate(names):
        final = tmp_path / name
        final.write_bytes(content + name.encode())
        finals.append((index, str(final)))
    staged = plan_staging(finals, "ab12cd34", tmp_path / "state" / "staging")
    for item in staged:
        with open(item.staged, "wb") as handle:
            handle.write(b"new" + os.path.basename(item.final).encode())
    return staged


def test_plan_staging_safe_dir_same_dir_same_ext(tmp_path):
    (item,) = plan_staging([(1, str(tmp_path / "out.xlsx"))], "ab12cd34", tmp_path)
    assert os.path.dirname(item.staged) == str(tmp_path)
    assert item.staged.endswith(".tdtmp-ab12cd34.xlsx")
    assert not item.cross_volume


@pytest.mark.parametrize("bad", ["'", '"', "{", "}"])
def test_plan_staging_unsafe_dir_uses_state_staging(tmp_path, bad):
    final = str(tmp_path / f"O{bad}Brien" / "x.csv")
    (item,) = plan_staging([(1, final)], "ab12cd34", tmp_path / "staging")
    assert item.cross_volume
    assert item.staged.startswith(str(tmp_path / "staging"))
    assert item.staged.endswith(".csv")


def test_commit_replaces_and_drops_backups(tmp_path):
    staged = _staged(tmp_path)
    commit_all(staged)
    assert (tmp_path / "a.csv").read_bytes() == b"newa.csv"
    assert sorted(os.listdir(tmp_path)) == ["a.csv", "b.csv"]


def test_commit_creates_new_finals(tmp_path):
    (item,) = plan_staging([(1, str(tmp_path / "n.csv"))], "ab12cd34", tmp_path)
    with open(item.staged, "wb") as handle:
        handle.write(b"x")
    commit_all([item])
    assert (tmp_path / "n.csv").read_bytes() == b"x"


def test_commit_cross_volume_copies(tmp_path):
    out = tmp_path / "O'Brien"
    out.mkdir()
    final = out / "x.csv"
    final.write_bytes(b"old")
    (item,) = plan_staging([(1, str(final))], "ab12cd34", tmp_path / "staging")
    os.makedirs(os.path.dirname(item.staged))
    with open(item.staged, "wb") as handle:
        handle.write(b"new")
    commit_all([item])
    assert final.read_bytes() == b"new"
    assert not os.path.exists(item.staged)
    assert sorted(os.listdir(out)) == ["x.csv"]


def test_commit_rolls_back_when_second_replace_fails(tmp_path, monkeypatch):
    staged = _staged(tmp_path)
    real, calls = os.replace, {"n": 0}

    def flaky(src, dst):
        calls["n"] += 1
        if calls["n"] == 4:  # phase B, second file
            raise PermissionError(13, "locked", dst)
        return real(src, dst)

    monkeypatch.setattr(atomic.os, "replace", flaky)
    with pytest.raises(CliError) as exc:
        commit_all(staged)
    assert exc.value.code == ExitCode.COMMIT_FAILED
    assert exc.value.td_code == "TD-CLI-013"
    monkeypatch.setattr(atomic.os, "replace", real)
    assert (tmp_path / "a.csv").read_bytes() == b"olda.csv"
    assert (tmp_path / "b.csv").read_bytes() == b"oldb.csv"
    assert sorted(os.listdir(tmp_path)) == ["a.csv", "b.csv"]


def test_commit_locked_first_file_changes_nothing(tmp_path, monkeypatch):
    staged = _staged(tmp_path)
    real = os.replace

    def locked(src, dst):
        if str(src).endswith("a.csv"):
            raise PermissionError(13, "in use", src)
        return real(src, dst)

    monkeypatch.setattr(atomic.os, "replace", locked)
    with pytest.raises(CliError) as exc:
        commit_all(staged)
    assert "Excel" in exc.value.hint
    monkeypatch.setattr(atomic.os, "replace", real)
    assert (tmp_path / "a.csv").read_bytes() == b"olda.csv"
    assert (tmp_path / "b.csv").read_bytes() == b"oldb.csv"
    assert not [n for n in os.listdir(tmp_path) if "tdtmp" in n or "tdbak" in n]


def test_discard_all_removes_staged(tmp_path):
    staged = _staged(tmp_path)
    discard_all(staged)
    assert sorted(os.listdir(tmp_path)) == ["a.csv", "b.csv"] + (
        ["state"] if (tmp_path / "state").exists() else []
    )


def test_write_json_atomic_leaves_no_tmp_on_error(tmp_path):
    target = tmp_path / "x.json"
    with pytest.raises(TypeError):
        write_json_atomic(target, {"bad": object()})
    assert os.listdir(tmp_path) == []
    write_json_atomic(target, {"a": 1})
    assert os.listdir(tmp_path) == ["x.json"]
