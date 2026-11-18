"""Canvas comments: the Qt-free reader, the legacy migration and the loaders."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from nodeeditor import node_comment

from trigger_designer.core.authoring.blank import new_workflow
from trigger_designer.core.authoring.model import iter_ids
from trigger_designer.core.headless import node_inspect as ni
from trigger_designer.core.headless.exit_codes import CliError
from trigger_designer.core.headless.op_catalog import OPS, node_op
from trigger_designer.core.headless.workflow_file import read_workflow
from trigger_designer.core.node_configuration import (
    OpCodeNotRegistered,
    ReportNodes,
    get_class_from_op,
)
from trigger_designer.core.shaping.comments import (
    CANVAS_COMMENT_VERSION,
    LEGACY_COMMENT_OP,
    MIGRATED_HEIGHT,
    MIGRATED_WIDTH,
    MIGRATED_Z,
    CommentRecord,
    comments_from_scene,
    comments_from_scene_dict,
    migrate_legacy_comment_nodes,
)
from trigger_designer.qt.performance_scene import TriggerScene

REPO_ROOT = Path(__file__).resolve().parents[2]


def _legacy_node(node_id: int, text: str, x: float = 0.0, y: float = 0.0, **extra):
    """A ``report.comment`` node as the editor saved it before canvas comments."""
    node = {
        "id": node_id,
        "title": "Comment",
        "pos_x": x,
        "pos_y": y,
        "inputs": [],
        "outputs": [],
        "content": {"settings": {"text": text}},
        "label_text": "",
        "label_visible": False,
        "label_offset": 10.0,
        "node_code": 3,
        "node_type": "report",
        "op": LEGACY_COMMENT_OP,
    }
    node.update(extra)
    return node


def _scene(nodes=(), edges=(), **extra):
    data = new_workflow()
    data["nodes"] = list(nodes)
    data["edges"] = list(edges)
    data.update(extra)
    return data


def _note(comment_id: int, text: str, x: float, y: float):
    """A live canvas comment, duck-typed for ``comments_from_scene``."""
    return SimpleNamespace(
        id=comment_id,
        text=lambda: text,
        pos=lambda: SimpleNamespace(x=lambda: x, y=lambda: y),
    )


def test_no_qt_import_in_core() -> None:
    code = (
        "import sys, trigger_designer.core.shaping.comments;"
        "print(any(m.split('.')[0] in ('PySide6','PyQt5','PyQt6','qtpy') for m in sys.modules))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert out.stdout.strip().endswith("False")


def test_the_comment_node_is_gone() -> None:
    assert LEGACY_COMMENT_OP not in OPS
    assert not hasattr(ReportNodes, "COMMENT")
    with pytest.raises(OpCodeNotRegistered):
        get_class_from_op(LEGACY_COMMENT_OP)


def test_constants_match_the_library() -> None:
    assert CANVAS_COMMENT_VERSION == node_comment.COMMENT_SERIALIZATION_VERSION
    assert MIGRATED_WIDTH == node_comment.Comment.DEFAULT_WIDTH
    assert MIGRATED_HEIGHT == node_comment.Comment.DEFAULT_HEIGHT
    assert MIGRATED_Z == node_comment.Comment.DEFAULT_Z_VALUE


# ----------------------------------------------------------------- readers


def test_saved_reader_orders_trims_and_skips_blank_notes() -> None:
    scene = {
        "comments": [
            {"id": 2, "text": "Second", "x": 0, "y": 100},
            {"id": 1, "text": " First ", "x": 0, "y": 10},
            {"id": 3, "text": "   ", "x": 0, "y": 50},
            {"id": 4, "text": None, "x": 0, "y": 60},
            "not a comment",
        ]
    }
    assert comments_from_scene_dict(scene) == [
        CommentRecord(1, "First", 0.0, 10.0),
        CommentRecord(2, "Second", 0.0, 100.0),
    ]


def test_saved_reader_breaks_a_row_by_x_then_id() -> None:
    scene = {
        "comments": [
            {"id": 5, "text": "c", "x": 30, "y": 1},
            {"id": 4, "text": "b", "x": 20, "y": 1},
            {"id": 3, "text": "a", "x": 20, "y": 1},
        ]
    }
    assert [c.comment_id for c in comments_from_scene_dict(scene)] == [3, 4, 5]


def test_saved_reader_tolerates_missing_keys() -> None:
    assert comments_from_scene_dict({}) == []
    assert comments_from_scene_dict({"comments": None}) == []
    assert comments_from_scene_dict({"comments": [{"text": "no id"}]}) == [
        CommentRecord(0, "no id", 0.0, 0.0)
    ]


def test_live_reader_uses_text_pos_and_id_only() -> None:
    scene = SimpleNamespace(
        comments=[
            _note(2, "Later", 0, 200),
            _note(1, "   ", 0, 5),
            _note(3, " Earlier ", 0, 20),
        ]
    )
    assert comments_from_scene(scene) == [
        CommentRecord(3, "Earlier", 0.0, 20.0),
        CommentRecord(2, "Later", 0.0, 200.0),
    ]
    assert comments_from_scene(None) == []


def test_live_reader_agrees_with_the_saved_reader() -> None:
    scene = TriggerScene()
    scene.addComment("First line\nsecond", x=10, y=300)
    scene.addComment("Top", x=50, y=20)
    scene.addComment("   ", x=0, y=0)
    live = comments_from_scene(scene)
    saved = comments_from_scene_dict(scene.serialize())
    assert [c.text for c in live] == ["Top", "First line\nsecond"]
    assert live == saved


# --------------------------------------------------------------- migration


def test_migration_moves_text_and_position_into_a_canvas_comment() -> None:
    original = _scene([_legacy_node(10, "Check cut-off\nsecond", x=40.0, y=25.0)])
    before = copy.deepcopy(original)

    migrated = migrate_legacy_comment_nodes(original)

    assert original == before
    assert migrated["nodes"] == []
    (note,) = migrated["comments"]
    assert note == {
        "id": note["id"],
        "type": "Comment",
        "version": CANVAS_COMMENT_VERSION,
        "text": "Check cut-off\nsecond",
        "x": 40.0,
        "y": 25.0,
        "w": MIGRATED_WIDTH,
        "h": MIGRATED_HEIGHT,
        "z": MIGRATED_Z,
    }
    assert "style" not in note
    assert comments_from_scene_dict(migrated) == [
        CommentRecord(note["id"], "Check cut-off\nsecond", 40.0, 25.0)
    ]


def test_migrated_ids_are_new_and_unique_in_the_file() -> None:
    original = _scene(
        [
            {
                "id": 100,
                "title": "Filter",
                "pos_x": 0.0,
                "pos_y": 0.0,
                "inputs": [{"id": 300, "index": 0}],
                "outputs": [{"id": 999, "index": 0}],
                "content": {},
                "op": "preparation.filter",
            },
            _legacy_node(200, "note"),
        ],
        edges=[{"id": 400, "start": 999, "end": 301}],
        groups=[{"id": 700}],
        comments=[{"id": 800, "text": "old", "x": 0, "y": 0}],
    )
    migrated = migrate_legacy_comment_nodes(original)

    (note,) = [c for c in migrated["comments"] if c["text"] == "note"]
    assert note["id"] == max(iter_ids(original)) + 1 == 1000
    ids = list(iter_ids(migrated))
    assert len(ids) == len(set(ids))
    # The edge from a surviving node's socket is not touched.
    assert migrated["edges"] == original["edges"]


def test_blank_legacy_notes_are_dropped_and_take_no_id() -> None:
    original = _scene(
        [_legacy_node(10, ""), _legacy_node(11, "  \n "), _legacy_node(12, "kept")]
    )
    migrated = migrate_legacy_comment_nodes(original)
    assert migrated["nodes"] == []
    (note,) = migrated["comments"]
    assert note["text"] == "kept"
    assert note["id"] == max(iter_ids(original)) + 1


def test_edges_into_the_removed_sockets_are_dropped_only() -> None:
    legacy = _legacy_node(10, "note")
    legacy["outputs"] = [{"id": 50, "index": 0}]
    other = {
        "id": 20,
        "title": "Filter",
        "pos_x": 0.0,
        "pos_y": 0.0,
        "inputs": [{"id": 60, "index": 0}],
        "outputs": [],
        "content": {},
        "op": "preparation.filter",
    }
    edges = [
        {"id": 70, "start": 50, "end": 60},
        {"id": 71, "start": 61, "end": 60},
        {"id": 72, "start": "odd", "end": None},
    ]
    original = _scene([legacy, other], edges=edges)
    before = copy.deepcopy(original)

    migrated = migrate_legacy_comment_nodes(original)

    assert [e["id"] for e in migrated["edges"]] == [71, 72]
    assert original == before


def test_migration_is_idempotent_and_clean_scenes_come_back_equal() -> None:
    original = _scene([_legacy_node(10, "one", x=1, y=2), _legacy_node(11, "two")])
    once = migrate_legacy_comment_nodes(original)
    assert migrate_legacy_comment_nodes(once) == once
    clean = _scene([{"id": 5, "op": "preparation.filter", "content": {}}])
    result = migrate_legacy_comment_nodes(clean)
    assert result == clean and result is not clean


def test_existing_canvas_comments_are_kept_and_new_ones_follow() -> None:
    existing = {
        "id": 500,
        "type": "Comment",
        "version": CANVAS_COMMENT_VERSION,
        "text": "already here",
        "x": 0.0,
        "y": 0.0,
        "w": MIGRATED_WIDTH,
        "h": MIGRATED_HEIGHT,
        "z": MIGRATED_Z,
    }
    original = _scene([_legacy_node(10, "moved")], comments=[existing])

    migrated = migrate_legacy_comment_nodes(original)

    assert migrated["comments"][0] == existing
    assert migrated["comments"][1]["text"] == "moved"
    assert original["comments"] == [existing]


def test_only_the_stored_op_marks_a_legacy_note() -> None:
    """Without a stored op the loader resolves the v1 table, where
    ("report", 3) is report.graph. The migration must agree with it."""
    graph_like = {
        "id": 10,
        "title": "Graph",
        "pos_x": 0.0,
        "pos_y": 0.0,
        "inputs": [],
        "outputs": [],
        "content": {"settings": {"text": "x"}},
        "node_type": "report",
        "node_code": 3,
    }
    assert node_op(graph_like) == "report.graph"
    migrated = migrate_legacy_comment_nodes(_scene([graph_like]))
    assert migrated["nodes"] == [graph_like]
    assert migrated["comments"] == []


def test_scene_loader_builds_no_note_node() -> None:
    scene = TriggerScene()
    assert scene.deserialize(_scene([_legacy_node(10, "moved", x=40, y=25)])) is True
    assert scene.nodes == []
    (note,) = scene.comments
    assert note.text() == "moved"
    assert (note.pos().x(), note.pos().y()) == (40.0, 25.0)


# ------------------------------------------------------- headless reading


def test_headless_reader_migrates_and_keeps_the_file_hash(tmp_path) -> None:
    path = tmp_path / "legacy.tds"
    path.write_text(
        json.dumps(_scene([_legacy_node(10, "Check cut-off", x=40, y=25)])),
        encoding="utf-8",
    )
    doc = read_workflow(str(path))
    assert doc.nodes == []
    assert [c.text for c in comments_from_scene_dict(doc.data)] == ["Check cut-off"]
    assert doc.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()


def test_a_chart_has_no_table_and_the_removed_note_is_unknown() -> None:
    with pytest.raises(CliError):
        ni.check_inspectable({"id": 1, "op": "report.graph", "title": "x"})
    with pytest.raises(CliError) as exc:
        ni.check_inspectable({"id": 1, "op": LEGACY_COMMENT_OP, "title": "x"})
    assert exc.value.td_code == "TD-CLI-003"


def test_no_shipped_workflow_still_carries_the_removed_node() -> None:
    shipped: list[Path] = []
    for pattern in ("src/**/*.tds", "savedfiles/**/*.tds", "tests/**/*.tds"):
        shipped.extend(REPO_ROOT.glob(pattern))
    assert shipped
    offenders = []
    for path in shipped:
        try:
            data = json.loads(path.read_bytes().decode("utf-8-sig"))
        except ValueError:
            continue  # not a workflow (an invalid-file fixture)
        nodes = data.get("nodes") if isinstance(data, dict) else None
        nodes = nodes or []
        if any(node_op(n) == LEGACY_COMMENT_OP for n in nodes if isinstance(n, dict)):
            offenders.append(path.relative_to(REPO_ROOT).as_posix())
    assert offenders == []
