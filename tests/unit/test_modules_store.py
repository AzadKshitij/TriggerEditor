"""Optional modules: the installed-module store, verification and removal (unit).

The store is laid out by hand in ``tmp_path`` (what a finished install leaves
behind). Everything here works offline.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from trigger_designer.core.modules import (
    InstalledModule,
    ModuleError,
    ModuleStore,
    VerifyResult,
    modules_dir,
    parse_manifest,
)

pytestmark = pytest.mark.unit

CONTENTS = {"model.bin": b"model bytes " * 10, "vocab.txt": b"alpha\nbeta\n"}


def manifest_for(module_id: str = "demo-model", contents: dict = CONTENTS):
    return parse_manifest(
        {
            "id": module_id,
            "name": f"{module_id} name",
            "version": "1.0.0",
            "description": "A module for the store tests.",
            "license": "MIT",
            "files": [
                {
                    "name": name,
                    "url": f"https://files.example.com/{module_id}/{name}",
                    "size_bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
                for name, data in contents.items()
            ],
        }
    )


def write_installed(
    root: Path,
    module_id: str = "demo-model",
    contents: dict = CONTENTS,
    installed_at: str = "2026-11-17T10:00:00Z",
) -> Path:
    """Lay out one installed module exactly as the downloader leaves it."""
    folder = root / module_id
    folder.mkdir(parents=True, exist_ok=True)
    for name, data in contents.items():
        (folder / name).write_bytes(data)
    record = {
        "installed_at": installed_at,
        "manifest": manifest_for(module_id, contents).to_dict(),
    }
    (folder / "module.json").write_text(json.dumps(record), encoding="utf-8")
    return folder


def test_an_empty_store_lists_nothing_and_creates_no_folder(tmp_path):
    store = ModuleStore(tmp_path / "modules")
    assert store.installed() == []
    assert store.get("demo-model") is None
    assert store.path_of("demo-model") is None
    assert not store.root.exists()


def test_the_default_root_is_the_modules_folder_of_the_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("TRIGGER_DESIGNER_DATA_DIR", str(tmp_path))
    assert modules_dir() == tmp_path / "modules"
    assert ModuleStore().root == tmp_path / "modules"


def test_installed_lists_valid_modules_sorted_by_id(tmp_path):
    root = tmp_path / "modules"
    write_installed(root, "zeta-model")
    write_installed(root, "alpha-model")
    items = ModuleStore(root).installed()
    assert [item.id for item in items] == ["alpha-model", "zeta-model"]
    alpha = items[0]
    assert isinstance(alpha, InstalledModule)
    assert alpha.version == "1.0.0"
    assert alpha.size_bytes == sum(len(data) for data in CONTENTS.values())
    assert alpha.installed_at == "2026-11-17T10:00:00Z"
    assert alpha.path == root / "alpha-model"
    assert ModuleStore(root).get("alpha-model") == alpha


def test_folders_that_are_not_installed_modules_are_ignored(tmp_path):
    root = tmp_path / "modules"
    write_installed(root)
    (root / "no-record").mkdir()
    (root / "bad-json").mkdir()
    (root / "bad-json" / "module.json").write_text("{nope", encoding="utf-8")
    (root / "wrong-folder").mkdir()
    record = {
        "installed_at": "2026-11-17T10:00:00Z",
        "manifest": manifest_for("someone-else").to_dict(),
    }
    (root / "wrong-folder" / "module.json").write_text(
        json.dumps(record), encoding="utf-8"
    )
    (root / ".partial" / "abc").mkdir(parents=True)
    (root / "Not A Module").mkdir()
    (root / "stray.txt").write_text("x", encoding="utf-8")

    store = ModuleStore(root)
    assert [item.id for item in store.installed()] == ["demo-model"]
    assert store.get("no-record") is None
    assert store.get("bad-json") is None
    assert store.get("wrong-folder") is None


def test_verify_passes_for_an_untouched_module(tmp_path):
    root = tmp_path / "modules"
    write_installed(root)
    assert ModuleStore(root).verify("demo-model") == VerifyResult(ok=True, problems=())


def test_verify_reports_a_changed_file(tmp_path):
    root = tmp_path / "modules"
    folder = write_installed(root)
    (folder / "model.bin").write_bytes(b"X" * len(CONTENTS["model.bin"]))
    result = ModuleStore(root).verify("demo-model")
    assert result.ok is False
    assert any(problem.startswith("changed: model.bin") for problem in result.problems)


def test_verify_reports_a_file_of_the_wrong_size(tmp_path):
    root = tmp_path / "modules"
    folder = write_installed(root)
    (folder / "model.bin").write_bytes(b"short")
    result = ModuleStore(root).verify("demo-model")
    assert result.ok is False
    assert any(
        problem.startswith("wrong size: model.bin") for problem in result.problems
    )


def test_verify_reports_a_missing_file(tmp_path):
    root = tmp_path / "modules"
    folder = write_installed(root)
    (folder / "vocab.txt").unlink()
    result = ModuleStore(root).verify("demo-model")
    assert result.ok is False
    assert result.problems == ("missing: vocab.txt",)


def test_verify_reports_unexpected_files_but_not_the_record(tmp_path):
    root = tmp_path / "modules"
    folder = write_installed(root)
    (folder / "extra.bin").write_bytes(b"not in the manifest")
    result = ModuleStore(root).verify("demo-model")
    assert result.ok is False
    assert result.problems == ("unexpected: extra.bin",)


def test_verify_of_an_unknown_module_raises_td_mod_002(tmp_path):
    with pytest.raises(ModuleError) as caught:
        ModuleStore(tmp_path / "modules").verify("nope-model")
    assert caught.value.code == "TD-MOD-002"
    with pytest.raises(ModuleError) as caught:
        ModuleStore(tmp_path / "modules").verify("../x")
    assert caught.value.code == "TD-MOD-002"


def test_path_of_points_at_the_module_folder(tmp_path):
    root = tmp_path / "modules"
    folder = write_installed(root)
    store = ModuleStore(root)
    assert store.path_of("demo-model") == folder
    assert store.path_of("nope-model") is None


def test_remove_deletes_the_whole_folder_and_then_reports_not_installed(tmp_path):
    root = tmp_path / "modules"
    folder = write_installed(root)
    (folder / "extra.bin").write_bytes(b"left behind")
    store = ModuleStore(root)
    assert store.remove("demo-model") is True
    assert not folder.exists()
    assert store.installed() == []
    assert store.remove("demo-model") is False


def test_remove_refuses_ids_that_could_leave_the_root(tmp_path):
    root = tmp_path / "modules"
    root.mkdir()
    sibling = tmp_path / "x"
    sibling.mkdir()
    (sibling / "keep.txt").write_text("keep", encoding="utf-8")
    store = ModuleStore(root)
    for module_id in ["../x", "..", "a/b", "..\\x", "C:x", "", "con", "x" * 41]:
        assert store.remove(module_id) is False, module_id
    assert (sibling / "keep.txt").exists()
