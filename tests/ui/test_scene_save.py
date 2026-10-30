"""Atomic UTF-8 save, tolerant load, metadata and workflow identity."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import orjson
import pytest
from nodeeditor.node_scene import InvalidFile
from qtpy.QtWidgets import QApplication

from trigger_designer.core.node_configuration import (
    NodeTypes,
    PreparationNodes,
    get_class_from_opcode,
)
from trigger_designer.qt import performance_scene
from trigger_designer.qt.design_window import TriggerSubWindow

_APP = QApplication.instance() or QApplication([])

TITLE = "A → 日"


@pytest.fixture()
def window(qtbot):
    win = TriggerSubWindow()
    qtbot.addWidget(win)
    cls = get_class_from_opcode(PreparationNodes.SELECT, NodeTypes.PREPARATION)
    cls(win.scene)
    # Node titles are rebuilt from the class on load, so non-ASCII text is
    # carried by the workflow metadata (which a save must preserve anyway).
    win.scene.loaded_workflow_metadata["note"] = TITLE
    return win


def _note(win: TriggerSubWindow) -> object:
    return win.scene.loaded_workflow_metadata.get("note")


def test_save_roundtrips_non_cp1252_title(window, tmp_path, qtbot) -> None:
    path = tmp_path / "wf.tds"
    window.scene.saveToFile(str(path))
    assert TITLE in path.read_bytes().decode("utf-8")

    other = TriggerSubWindow()
    qtbot.addWidget(other)
    other.scene.loadFromFile(str(path))
    assert _note(other) == TITLE


def _failing_save_leaves_the_file_alone(window, path, raiser) -> None:
    window.scene.saveToFile(str(path))
    before = path.read_bytes()
    window.scene.has_been_modified = True
    raiser()
    with pytest.raises(Exception):  # noqa: B017
        window.scene.saveToFile(str(path))
    assert path.read_bytes() == before
    assert list(path.parent.glob(".tds-*.tmp")) == []
    assert window.scene.has_been_modified is True


def test_save_never_truncates_when_serialize_raises(
    window, tmp_path, monkeypatch
) -> None:
    def raiser() -> None:
        monkeypatch.setattr(
            window.scene,
            "serialize",
            lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        )

    _failing_save_leaves_the_file_alone(window, tmp_path / "wf.tds", raiser)


def test_save_never_truncates_on_encoding_error(window, tmp_path, monkeypatch) -> None:
    def raiser() -> None:
        def dumps(*_a, **_k):
            raise UnicodeEncodeError("utf-8", "x", 0, 1, "boom")

        monkeypatch.setattr(performance_scene.orjson, "dumps", dumps)

    _failing_save_leaves_the_file_alone(window, tmp_path / "wf.tds", raiser)


def test_save_keeps_old_file_when_replace_fails(window, tmp_path, monkeypatch) -> None:
    def raiser() -> None:
        def replace(*_a, **_k):
            raise OSError("locked")

        monkeypatch.setattr(performance_scene.os, "replace", replace)

    _failing_save_leaves_the_file_alone(window, tmp_path / "wf.tds", raiser)


def test_atomic_save_replaces_content(window, tmp_path) -> None:
    path = tmp_path / "wf.tds"
    window.scene.saveToFile(str(path))
    first = path.read_bytes()
    window.scene.loaded_workflow_metadata["note"] = "Changed"
    window.scene.saveToFile(str(path))
    assert path.read_bytes() != first
    assert orjson.loads(path.read_bytes())["workflow_metadata"]
    assert window.scene.has_been_modified is False
    assert window.scene.filename == str(path)


def test_legacy_cp1252_file_loads(window, tmp_path, qtbot) -> None:
    from loguru import logger

    data = window.scene.serialize()
    data["workflow_metadata"]["note"] = "café"
    path = tmp_path / "legacy.tds"
    path.write_bytes(orjson.dumps(data).decode("utf-8").encode("cp1252"))
    # orjson emits raw UTF-8; re-encoding as cp1252 gives the legacy bytes.
    assert b"caf\xe9" in path.read_bytes()

    warnings: list[str] = []
    handler = logger.add(lambda m: warnings.append(str(m)), level="WARNING")
    try:
        other = TriggerSubWindow()
        qtbot.addWidget(other)
        other.scene.loadFromFile(str(path))
    finally:
        logger.remove(handler)
    assert _note(other) == "café"
    assert any("not UTF-8" in line for line in warnings)


def test_utf8_bom_loads(window, tmp_path, qtbot) -> None:
    path = tmp_path / "bom.tds"
    path.write_bytes(b"\xef\xbb\xbf" + orjson.dumps(window.scene.serialize()))
    other = TriggerSubWindow()
    qtbot.addWidget(other)
    other.scene.loadFromFile(str(path))
    assert _note(other) == TITLE


def test_invalid_json_raises_invalid_file(window, tmp_path) -> None:
    path = tmp_path / "bad.tds"
    path.write_bytes(b"not json at all")
    with pytest.raises(InvalidFile):
        window.scene.loadFromFile(str(path))


def test_workflow_dir_during_save_uses_target(window, tmp_path) -> None:
    window.scene.filename = str(tmp_path / "old" / "x.tds")
    target_dir = tmp_path / "new"
    target_dir.mkdir()
    seen: list[str | None] = []
    real = window.scene.serialize

    def spy():
        seen.append(window.scene.workflow_dir)
        return real()

    window.scene.serialize = spy
    window.scene.saveToFile(str(target_dir / "wf.tds"))
    assert seen == [str(target_dir)]
    assert window.scene._save_target is None
    assert window.scene.workflow_dir == str(target_dir)


def test_extra_metadata_keys_survive_save(window, tmp_path, qtbot) -> None:
    window.scene.loaded_workflow_metadata["parameters"] = {"a": 1}
    path = tmp_path / "wf.tds"
    window.scene.saveToFile(str(path))
    other = TriggerSubWindow()
    qtbot.addWidget(other)
    other.scene.loadFromFile(str(path))
    meta = other.scene.loaded_workflow_metadata
    assert meta["parameters"] == {"a": 1}
    assert meta["schema_version"] == 2
    assert meta["saved_at"].endswith("Z")


def test_workflow_uuid_is_stable_across_saves_and_loads(
    window, tmp_path, qtbot
) -> None:
    path = tmp_path / "wf.tds"
    window.scene.saveToFile(str(path))
    first = window.scene.workflow_uuid
    window.scene.saveToFile(str(path))
    assert window.scene.workflow_uuid == first
    other = TriggerSubWindow()
    qtbot.addWidget(other)
    other.scene.loadFromFile(str(path))
    assert other.scene.workflow_uuid == first


def test_file_new_resets_workflow_identity(window, tmp_path) -> None:
    window.scene.saveToFile(str(tmp_path / "wf.tds"))
    first = window.scene.workflow_uuid
    window.scene.loaded_workflow_metadata["parameters"] = {"a": 1}
    window.fileNew()
    assert window.scene.workflow_uuid != first
    assert window.scene.loaded_workflow_metadata == {}


def test_newer_schema_version_warns(window, tmp_path, qtbot) -> None:
    path = tmp_path / "wf.tds"
    window.scene.saveToFile(str(path))
    data = orjson.loads(path.read_bytes())
    data["workflow_metadata"]["schema_version"] = 99
    path.write_bytes(orjson.dumps(data))
    other = TriggerSubWindow()
    qtbot.addWidget(other)
    other.scene.loadFromFile(str(path))
    messages = other.validateLoadedWorkflow()
    assert any("newer version" in message for message in messages)
