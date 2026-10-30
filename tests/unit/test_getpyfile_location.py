"""The exported run script goes to the app data folder, never the CWD (BUG-013)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from trigger_designer.qt.design_window import TriggerSubWindow


class Node:
    def __init__(self, code: str = "x = 1\n", raises: Exception | None = None) -> None:
        self.node_title = "stub"
        self._code = code
        self._raises = raises

    def get_code(self) -> str:
        if self._raises is not None:
            raise self._raises
        return self._code


def _export(nodes, codes=None, path=None) -> str:
    fake = SimpleNamespace(_last_run_codes=codes or {})
    return TriggerSubWindow.getPyFile(fake, nodes, path)


@pytest.fixture()
def data_dir(tmp_path, monkeypatch):
    target = tmp_path / "data"
    monkeypatch.setenv("TRIGGER_DESIGNER_DATA_DIR", str(target))
    return target


def test_getpyfile_does_not_write_into_cwd(tmp_path, monkeypatch, data_dir) -> None:
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    written = _export([Node()])
    assert list(cwd.iterdir()) == []
    assert written.endswith(os.path.join("last_run", "check_output.py"))
    assert os.path.dirname(os.path.dirname(written)) == str(data_dir)
    raw = Path(written).read_bytes()
    raw.decode("utf-8")
    assert b"\r" not in raw


def test_getpyfile_uses_recorded_codes_not_get_code(data_dir) -> None:
    node = Node(raises=RuntimeError("must not be asked"))
    text = Path(_export([node], {node: "x = 1\n"})).read_text(encoding="utf-8")
    assert "x = 1" in text


def test_getpyfile_survives_raising_get_code(data_dir) -> None:
    node = Node(raises=ValueError("no incoming\ndata"))
    text = Path(_export([node, Node("y = 2\n")])).read_text(encoding="utf-8")
    assert "y = 2" in text
    assert "no code" in text
    compile(text, "<export>", "exec")  # the message did not break the script


def test_getpyfile_path_argument(tmp_path, data_dir) -> None:
    target = tmp_path / "sub" / "out.py"
    assert _export([Node()], path=target) == str(target)
    assert target.is_file()
    assert not data_dir.exists()


def test_exported_script_can_import_the_package(tmp_path, data_dir) -> None:
    written = _export([Node("import trigger_designer\n")])
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    proc = subprocess.run(
        [sys.executable, written],
        cwd=elsewhere,
        env=env,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr.decode()[-500:]


def test_header_constant_is_unchanged() -> None:
    from trigger_designer.qt.design_window import CHECK_OUTPUT_HEADER

    assert CHECK_OUTPUT_HEADER.startswith("import os as _td_os\n")
