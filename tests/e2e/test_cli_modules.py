"""``modules``: the optional data packs from the command line, offline (e2e).

Real subprocess runs against a data folder laid out by hand (what a finished,
consented install leaves behind): listed, verified and removed with --yes. Nothing
here downloads, and the catalogue is a file the test writes itself.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests.support.cli import cli_env, run_cli
from trigger_designer.core.modules import parse_manifest

pytestmark = pytest.mark.e2e

FILES = {"model.bin": b"demo model bytes"}


def _manifest(files: dict = FILES) -> dict:
    return {
        "id": "demo-model",
        "name": "Demo model",
        "version": "1.0.0",
        "description": "A small module for the command line tests.",
        "license": "MIT",
        "files": [
            {
                "name": name,
                "url": f"https://files.example.com/demo-model/{name}",
                "size_bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
            for name, data in files.items()
        ],
    }


@pytest.fixture
def catalogue_env(tmp_path) -> dict:
    """An empty catalogue of the test's own, so the shipped list cannot change results."""
    path = tmp_path / "catalogue.json"
    path.write_text(json.dumps({"schema": 1, "modules": []}), encoding="utf-8")
    return {"TRIGGER_DESIGNER_MODULE_CATALOGUE": str(path)}


def _cli(tmp_path: Path, env: dict, *args):
    return run_cli(*args, cwd=tmp_path, extra_env=env)


def _json(proc):
    assert proc.stdout.strip(), proc.stderr[-1500:]
    return json.loads(proc.stdout)


def _install_by_hand(data_dir: Path, files: dict = FILES) -> Path:
    """Lay out a module the way the downloader leaves it: the record is written last."""
    folder = data_dir / "modules" / "demo-model"
    folder.mkdir(parents=True)
    for name, data in files.items():
        (folder / name).write_bytes(data)
    record = {
        "installed_at": "2026-11-17T10:00:00Z",
        "manifest": parse_manifest(_manifest(files)).to_dict(),
    }
    (folder / "module.json").write_text(json.dumps(record), encoding="utf-8")
    return folder


def test_listing_a_fresh_data_folder_shows_nothing_and_creates_nothing(
    tmp_path, catalogue_env
):
    proc = _cli(tmp_path, catalogue_env, "modules", "list", "--json")
    assert proc.returncode == 0, proc.stderr
    out = _json(proc)
    assert out["installed"] == []
    assert out["available"] == []
    assert out["catalogue"]["problems"] == []
    assert not (tmp_path / "data" / "modules").exists()


def test_the_catalogue_offers_modules_without_downloading_them(tmp_path):
    catalogue = tmp_path / "catalogue.json"
    catalogue.write_text(
        json.dumps({"schema": 1, "modules": [_manifest()]}), encoding="utf-8"
    )
    env = {"TRIGGER_DESIGNER_MODULE_CATALOGUE": str(catalogue)}
    out = _json(_cli(tmp_path, env, "modules", "list", "--json"))
    assert [item["id"] for item in out["available"]] == ["demo-model"]
    assert out["available"][0]["size_bytes"] == len(FILES["model.bin"])
    assert out["available"][0]["hosts"] == ["files.example.com"]
    assert out["installed"] == []
    assert not (tmp_path / "data" / "modules").exists()


def test_an_installed_module_is_listed_verified_and_removed(tmp_path, catalogue_env):
    folder = _install_by_hand(tmp_path / "data")

    listed = _json(_cli(tmp_path, catalogue_env, "modules", "list", "--json"))
    assert [item["id"] for item in listed["installed"]] == ["demo-model"]
    assert listed["installed"][0]["version"] == "1.0.0"
    assert listed["installed"][0]["size_bytes"] == len(FILES["model.bin"])

    verified = _cli(
        tmp_path, catalogue_env, "modules", "verify", "demo-model", "--json"
    )
    assert verified.returncode == 0, verified.stderr
    assert _json(verified)["ok"] is True

    refused = _cli(tmp_path, catalogue_env, "modules", "remove", "demo-model", "--json")
    assert refused.returncode == 64
    assert _json(refused)["error"]["code"] == "TD-CLI-006"
    assert folder.exists()

    removed = _cli(
        tmp_path, catalogue_env, "modules", "remove", "demo-model", "--yes", "--json"
    )
    assert removed.returncode == 0, removed.stderr
    assert _json(removed)["removed"] is True
    assert not folder.exists()
    after = _json(_cli(tmp_path, catalogue_env, "modules", "list", "--json"))
    assert after["installed"] == []


def test_verify_exits_10_when_a_file_no_longer_matches(tmp_path, catalogue_env):
    folder = _install_by_hand(tmp_path / "data")
    (folder / "model.bin").write_bytes(b"demo model BYTES")  # same size, other bytes
    proc = _cli(tmp_path, catalogue_env, "modules", "verify", "demo-model", "--json")
    assert proc.returncode == 10
    out = _json(proc)
    assert out["ok"] is False
    assert any(problem.startswith("changed") for problem in out["problems"])


def test_unknown_module_names_are_structured_errors(tmp_path, catalogue_env):
    for args in (
        ("verify", "nope-model"),
        ("remove", "nope-model", "--yes"),
        ("remove", "../x", "--yes"),
    ):
        proc = _cli(tmp_path, catalogue_env, "modules", *args, "--json")
        assert proc.returncode == 2, (args, proc.stdout, proc.stderr)
        assert _json(proc)["error"]["code"] == "TD-MOD-002"


def test_the_text_listing_names_the_installed_module(tmp_path, catalogue_env):
    _install_by_hand(tmp_path / "data")
    proc = _cli(tmp_path, catalogue_env, "modules", "list")
    assert proc.returncode == 0, proc.stderr
    assert "demo-model" in proc.stdout


def test_the_command_line_never_loads_the_downloader(tmp_path, catalogue_env):
    code = (
        "import sys\n"
        "from trigger_designer.cli.app import main\n"
        "main(['modules', 'list', '--json'], hard_exit=False)\n"
        "print('LOADED' if 'trigger_designer.core.modules.downloader' in sys.modules "
        "else 'CLEAN')\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env=cli_env(tmp_path, catalogue_env),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=180,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip().splitlines()[-1] == "CLEAN"
