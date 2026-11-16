"""What ``core/authoring`` writes must be what the editor writes (AI plan, phase 2).

``core/authoring/templates.py`` is Qt-free, so its node codes, socket types and
edge fields are copies. Here every node type is built in the real editor and
compared with the authored JSON, and an authored workflow is loaded back into
the editor, so a copy that drifted - or a file the editor cannot read - fails
the build.
"""

from __future__ import annotations

import json

import pytest

from tests.support.workflows import REPO_ROOT
from trigger_designer.core.authoring import Editor, apply_patch
from trigger_designer.core.headless.node_spec_forms import registered_nodes
from trigger_designer.qt.headless import make_window

OPS = dict(registered_nodes())


def _plain(value):
    return json.loads(json.dumps(value, default=str))


def _sockets(node: dict) -> list:
    return [
        [
            (s["index"], s["multi_edges"], s["position"], s["socket_type"])
            for s in node[key]
        ]
        for key in ("inputs", "outputs")
    ]


@pytest.fixture
def window(qapp):
    return make_window()


@pytest.mark.parametrize("op", sorted(OPS))
def test_an_authored_node_is_the_node_the_editor_saves(op, window, tmp_path):
    gui = _plain(OPS[op](window.scene).serialize())
    editor = Editor({"nodes": [], "edges": []}, base_dir=str(tmp_path))
    node = editor.node(editor.add_node(op)["id"])
    assert set(node) == set(gui), op
    for key in ("title", "node_code", "node_type", "op", "label_text"):
        assert node[key] == gui[key], (op, key)
    assert (node["label_visible"], node["label_offset"]) == (
        gui["label_visible"],
        gui["label_offset"],
    )
    assert _sockets(node) == _sockets(gui), op
    for key, value in node["content"].items():
        assert _plain(value) == gui["content"][key], (op, key)
    if set(gui["content"]) == {"settings"}:
        assert node["content"] == gui["content"], op


def _edge(editor: Editor) -> dict:
    return editor.data["edges"][-1]


def test_authored_edges_have_the_fields_and_labels_the_editor_writes(window, tmp_path):
    from nodeeditor.node_edge import EDGE_TYPE_DEFAULT, Edge

    scene = window.scene
    sort, select, union = (
        OPS[op](scene)
        for op in ("preparation.sort", "preparation.select", "join.union")
    )
    Edge(scene, sort.outputs[0], select.inputs[0], EDGE_TYPE_DEFAULT)
    Edge(scene, sort.outputs[0], union.inputs[0], EDGE_TYPE_DEFAULT)
    Edge(scene, select.outputs[0], union.inputs[0], EDGE_TYPE_DEFAULT)
    gui = [_plain(e.serialize()) for e in scene.edges]

    editor = Editor({"nodes": [], "edges": []}, base_dir=str(tmp_path))
    a, b, u = (
        editor.add_node(op)["id"]
        for op in ("preparation.sort", "preparation.select", "join.union")
    )
    editor.connect(a, 0, b)
    plain = _edge(editor)
    editor.connect(a, 0, u)
    first_union = _edge(editor)
    editor.connect(b, 0, u)
    second_union = _edge(editor)

    single = next(e for e in gui if e["end"] == select.inputs[0].id)
    assert set(plain) == set(single)
    assert (plain["edge_type"], plain["label"], plain["input_index"]) == (
        single["edge_type"],
        single["label"],
        max(single["input_index"], 0),
    )
    union_edges = sorted(
        (e for e in gui if e["end"] == union.inputs[0].id),
        key=lambda e: e["input_index"],
    )
    # The order is the editor's too. Its "#n" labels come from the canvas
    # (drag-connect), so they are checked against saved workflows below.
    assert [e["input_index"] for e in union_edges] == [
        first_union["input_index"],
        second_union["input_index"],
    ]
    assert (first_union["label"], second_union["label"]) == ("#1", "#2")


def test_union_labels_follow_the_convention_of_saved_workflows():
    seen = 0
    for path in sorted((REPO_ROOT / "savedfiles").glob("*.tds")):
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except ValueError:
            continue
        sockets = {
            s["id"]
            for n in data.get("nodes", [])
            if n.get("op") == "join.union"
            for s in n["inputs"]
        }
        for edge in data.get("edges", []):
            if edge.get("end") in sockets:
                seen += 1
                assert edge["label"] == f"#{edge['input_index'] + 1}", path.name
    if not seen:
        pytest.skip("no saved workflow has a Union")


def test_the_editor_loads_an_authored_workflow(window, tmp_path):
    editor = Editor(
        {
            "id": 1,
            "scene_width": 64000,
            "scene_height": 64000,
            "nodes": [],
            "edges": [],
            "groups": [],
            "workflow_metadata": {"schema_version": 2},
        },
        base_dir=str(tmp_path),
    )
    apply_patch(
        editor,
        [
            {"op": "add_node", "type": "input.file_input", "ref": "i"},
            {
                "op": "add_node",
                "type": "preparation.filter",
                "ref": "f",
                "after": "i",
                "settings": {"column": "Amount", "operation": ">", "value": "10"},
            },
            {"op": "add_node", "type": "join.union", "ref": "u", "after": "f"},
            {"op": "add_node", "type": "input.file_output", "ref": "o", "after": "u"},
            {"op": "connect", "from": "i", "to": "f"},
            {"op": "connect", "from": "f", "output": "true", "to": "u"},
            {"op": "connect", "from": "f", "output": "false", "to": "u"},
            {"op": "connect", "from": "u", "to": "o"},
            {"op": "label", "node": "f", "text": "Large amounts", "visible": True},
        ],
    )
    path = tmp_path / "authored.tds"
    path.write_text(json.dumps(editor.data), encoding="utf-8")

    window.scene.loadFromFile(str(path))
    saved = _plain(window.scene.serialize())

    assert sorted(n["op"] for n in saved["nodes"]) == sorted(
        n["op"] for n in editor.data["nodes"]
    )
    assert len(saved["edges"]) == len(editor.data["edges"]) == 4
    by_op = {n["op"]: n for n in saved["nodes"]}
    filt = by_op["preparation.filter"]
    assert filt["content"]["settings"]["column"] == "Amount"
    assert filt["content"]["settings"]["value"] == "10"
    assert filt["label_text"] == "Large amounts" and filt["label_visible"] is True
    authored_ids = {n["id"] for n in editor.data["nodes"]}
    assert {n["id"] for n in saved["nodes"]} == authored_ids


def test_the_editor_opens_a_new_empty_workflow(window, tmp_path):
    from trigger_designer.core.authoring import new_workflow

    path = tmp_path / "blank.tds"
    path.write_text(json.dumps(new_workflow()), encoding="utf-8")
    window.scene.loadFromFile(str(path))
    saved = _plain(window.scene.serialize())
    assert saved["nodes"] == [] and saved["edges"] == []


def test_a_relative_file_input_is_found_by_the_editor(window, tmp_path):
    """The editor reads 'filePathRel' against the workflow's folder; a path set
    without it shows as 'Missing input file'."""
    (tmp_path / "in.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    editor = Editor(
        {
            "id": 1,
            "scene_width": 64000,
            "scene_height": 64000,
            "nodes": [],
            "edges": [],
            "groups": [],
            "workflow_metadata": {"schema_version": 2},
        },
        base_dir=str(tmp_path),
    )
    editor.add_node("input.file_input", settings={"filePath": "in.csv"})
    path = tmp_path / "wf.tds"
    path.write_text(json.dumps(editor.data), encoding="utf-8")
    window.scene.loadFromFile(str(path))
    [node] = [n for n in window.scene.nodes if n.node_title == "File Input"]
    assert node.content.filePath == str(tmp_path / "in.csv")
    assert node.content.validate_loaded_state() == []
