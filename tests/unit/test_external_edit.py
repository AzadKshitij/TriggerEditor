"""What changed in a ``.tds`` file an external tool rewrote (AI plan, phase 4).

Each test builds a base and a new file with ``Editor``, ``apply_patch`` or by
editing the dict, then saves both with ``dump_workflow``, so the bytes are the
ones the editor would write. Workflows keep fixed metadata, so rebuilding one
gives the same bytes.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from trigger_designer.core import authoring
from trigger_designer.core.authoring import (
    Editor,
    ExternalChange,
    analyse_external_edit,
    apply_patch,
    new_workflow,
)
from trigger_designer.core.authoring.model import iter_ids
from trigger_designer.core.authoring.templates import new_edge
from trigger_designer.core.constants import WORKFLOW_SCHEMA_VERSION
from trigger_designer.core.headless.params import dump_workflow

pytestmark = pytest.mark.unit

BANNER = "The file was changed outside Trigger Designer"
PATH = "sales.tds"


def empty() -> dict:
    return {
        "id": 1,
        "scene_width": 64000,
        "scene_height": 64000,
        "nodes": [],
        "edges": [],
        "groups": [],
        "workflow_metadata": {"schema_version": 2, "app_version": "0.1.0"},
    }


def editor(tmp_path) -> Editor:
    return Editor(empty(), base_dir=str(tmp_path))


def as_bytes(data: dict) -> bytes:
    return dump_workflow(data)


def analyse(base: bytes, new: bytes) -> ExternalChange:
    return analyse_external_edit(base, new, PATH)


def linked_pair(tmp_path) -> tuple[Editor, int, int]:
    """Two sort nodes, the first feeding the second."""
    ed = editor(tmp_path)
    first = ed.add_node("preparation.sort")["id"]
    second = ed.add_node("preparation.sort")["id"]
    ed.connect(first, 0, second)
    return ed, first, second


def add_loop(data: dict) -> None:
    """Close a loop by hand: ``Editor.connect`` refuses to create one."""
    first, second = data["nodes"][0], data["nodes"][1]
    data["edges"].append(
        new_edge(
            max(iter_ids(data)) + 1,
            second["outputs"][0]["id"],
            first["inputs"][0]["id"],
        )
    )


# ---------------------------------------------------------------- statuses
def test_identical_bytes_are_unchanged(tmp_path):
    ed, _first, _second = linked_pair(tmp_path)
    data = as_bytes(ed.data)
    result = analyse(data, data)
    assert result.status == "unchanged"
    assert result.sha256 == hashlib.sha256(data).hexdigest()
    assert result.summary == ""
    assert result.touched == {} and result.removed == ()
    assert result.lines == () and result.problems == ()
    assert result.data is None and result.diff is None


def test_the_same_workflow_reformatted_is_metadata_only(tmp_path):
    ed, _first, _second = linked_pair(tmp_path)
    base = as_bytes(ed.data)
    new = json.dumps(ed.data, indent=4).encode("utf-8")
    assert new != base
    result = analyse(base, new)
    assert result.status == "metadata_only"
    assert result.summary == f"{BANNER} (no node changes)"
    assert result.touched == {} and result.removed == () and result.lines == ()
    assert result.problems == ()
    assert result.data == ed.data
    assert result.diff["empty"]


def test_a_changed_saved_at_stamp_is_metadata_only(tmp_path):
    ed, _first, _second = linked_pair(tmp_path)
    base = as_bytes(ed.data)
    ed.data["workflow_metadata"]["saved_at"] = "2026-11-17T09:00:00Z"
    result = analyse(base, as_bytes(ed.data))
    assert result.status == "metadata_only"
    assert result.summary == f"{BANNER} (no node changes)"


# ------------------------------------------------------------ changed nodes
def test_an_added_node_and_its_connection_touch_both_ends(tmp_path):
    ed, first, _second = linked_pair(tmp_path)
    base = as_bytes(ed.data)
    results = apply_patch(
        ed,
        [
            {"op": "add_node", "type": "preparation.sort", "ref": "s"},
            {"op": "connect", "from": first, "to": "s"},
        ],
    )
    new_id = results[0]["id"]
    new = as_bytes(ed.data)
    result = analyse(base, new)
    assert isinstance(result, ExternalChange)
    assert result.status == "changed"
    # The new node is "added" even though it is also connected (precedence).
    assert result.touched == {new_id: "added", first: "connected"}
    assert result.summary == (
        "Changed outside Trigger Designer: 1 node added, 1 connection added"
    )
    assert result.lines == (
        f"+ node {new_id} Sort (preparation.sort)",
        f"+ connect {first}.out0 -> {new_id}.in0",
    )
    assert result.removed == () and result.problems == ()
    assert result.sha256 == hashlib.sha256(new).hexdigest()
    assert result.data == json.loads(new)


def test_a_changed_setting_is_touched_and_named_in_the_lines(tmp_path):
    ed = editor(tmp_path)
    node = ed.add_node("preparation.filter")["id"]
    base = as_bytes(ed.data)
    ed.set_settings(node, {"column": "Amount"})
    result = analyse(base, as_bytes(ed.data))
    assert result.status == "changed"
    assert result.touched == {node: "changed"}
    assert result.summary == "Changed outside Trigger Designer: 1 node changed"
    assert any("content.settings.column" in line for line in result.lines)


def test_a_relabelled_node_is_changed(tmp_path):
    ed = editor(tmp_path)
    node = ed.add_node("preparation.sort")["id"]
    base = as_bytes(ed.data)
    ed.set_label(node, "Biggest first")
    result = analyse(base, as_bytes(ed.data))
    assert result.status == "changed"
    assert result.touched == {node: "changed"}
    assert result.summary == "Changed outside Trigger Designer: 1 node changed"
    assert any("label_text" in line for line in result.lines)


def test_a_removed_node_is_listed_and_not_touched(tmp_path):
    ed, first, second = linked_pair(tmp_path)
    base = as_bytes(ed.data)
    ed.remove_node(second)
    result = analyse(base, as_bytes(ed.data))
    assert result.status == "changed"
    assert result.removed == (
        {"id": second, "title": "Sort", "op": "preparation.sort"},
    )
    assert second not in result.touched
    assert result.touched == {first: "connected"}
    assert result.summary == (
        "Changed outside Trigger Designer: 1 node removed, 1 connection removed"
    )


def test_removing_a_union_counts_its_three_connections(tmp_path):
    ed = editor(tmp_path)
    sources = [ed.add_node("preparation.sort")["id"] for _ in range(3)]
    union = ed.add_node("join.union")["id"]
    for source in sources:
        ed.connect(source, 0, union)
    base = as_bytes(ed.data)
    ed.remove_node(union)
    result = analyse(base, as_bytes(ed.data))
    assert result.touched == {source: "connected" for source in sources}
    assert result.summary == (
        "Changed outside Trigger Designer: 1 node removed, 3 connections removed"
    )


def test_a_union_with_three_inputs_reads_as_three_connections(tmp_path):
    ed = editor(tmp_path)
    sources = [ed.add_node("preparation.sort")["id"] for _ in range(3)]
    base = as_bytes(ed.data)
    union = ed.add_node("join.union")["id"]
    for source in sources:
        ed.connect(source, 0, union)
    result = analyse(base, as_bytes(ed.data))
    assert result.touched == {union: "added", **{s: "connected" for s in sources}}
    assert result.summary == (
        "Changed outside Trigger Designer: 1 node added, 3 connections added"
    )


def test_a_changed_node_that_lost_a_connection_is_changed_not_connected(tmp_path):
    ed = editor(tmp_path)
    first, middle, last = (ed.add_node("preparation.sort")["id"] for _ in range(3))
    ed.connect(first, 0, middle)
    ed.connect(middle, 0, last)
    base = as_bytes(ed.data)
    ed.disconnect(first, 0, middle)
    ed.set_label(middle, "Middle")
    result = analyse(base, as_bytes(ed.data))
    # "changed" outranks "connected"; the last node is not touched at all.
    assert result.touched == {first: "connected", middle: "changed"}
    assert result.summary == (
        "Changed outside Trigger Designer: 1 node changed, 1 connection removed"
    )


@pytest.mark.parametrize("count, noun", [(1, "node"), (2, "nodes")])
def test_the_summary_uses_the_singular_only_for_one(tmp_path, count, noun):
    base_data = new_workflow()
    base = as_bytes(base_data)
    ed = Editor(base_data, base_dir=str(tmp_path))
    for _ in range(count):
        ed.add_node("preparation.sort")
    result = analyse(base, as_bytes(ed.data))
    assert result.summary == f"Changed outside Trigger Designer: {count} {noun} added"


def test_a_base_that_cannot_be_read_counts_as_an_empty_workflow(tmp_path):
    ed, first, second = linked_pair(tmp_path)
    result = analyse(b"this was never a workflow", as_bytes(ed.data))
    assert result.status == "changed"
    assert result.touched == {first: "added", second: "added"}
    assert result.summary == (
        "Changed outside Trigger Designer: 2 nodes added, 1 connection added"
    )


def test_an_error_the_base_already_had_is_not_reported_again(tmp_path):
    ed, first, _second = linked_pair(tmp_path)
    add_loop(ed.data)  # the base is already invalid, for its own loop
    base = as_bytes(ed.data)
    ed.set_label(first, "First")
    result = analyse(base, as_bytes(ed.data))
    assert result.status == "changed"
    assert result.touched == {first: "changed"}


# ------------------------------------------------------------------ invalid
def test_a_node_that_changes_its_type_cannot_be_reloaded_in_place(tmp_path):
    ed = editor(tmp_path)
    node = ed.add_node("preparation.sort")["id"]
    base = as_bytes(ed.data)
    retyped = next(n for n in ed.data["nodes"] if n["id"] == node)
    retyped["op"] = "preparation.select"
    result = analyse(base, as_bytes(ed.data))
    problem = (
        "A node changed its type (Sort: preparation.sort -> preparation.select); "
        "close and reopen the file to load it."
    )
    assert result.status == "invalid"
    assert result.problems == (problem,)
    assert result.summary == f"{BANNER} but cannot be reloaded in place: {problem}"
    assert result.data is None and result.diff is None


@pytest.mark.parametrize(
    "new, problem",
    [
        (b"", "sales.tds is empty"),
        (b" \r\n\t", "sales.tds is empty"),
        (b"[]", "sales.tds has no 'nodes' and 'edges' lists"),
        (b"null", "sales.tds has no 'nodes' and 'edges' lists"),
        (b"{}", "sales.tds has no 'nodes' and 'edges' lists"),
    ],
)
def test_a_file_that_is_not_a_workflow_is_unreadable(tmp_path, new, problem):
    base = as_bytes(editor(tmp_path).data)
    result = analyse(base, new)
    assert result.status == "invalid"
    assert result.problems == (problem,)
    assert result.summary == f"{BANNER} but cannot be read yet: {problem}"
    assert result.data is None and result.diff is None
    assert result.sha256 == hashlib.sha256(new).hexdigest()


def test_a_half_written_file_is_unreadable_and_says_why(tmp_path):
    ed, _first, _second = linked_pair(tmp_path)
    base = as_bytes(ed.data)
    result = analyse(base, base[: len(base) // 2])
    assert result.status == "invalid"
    assert len(result.problems) == 1
    assert result.problems[0].startswith("sales.tds is not valid JSON (")
    assert result.summary == f"{BANNER} but cannot be read yet: {result.problems[0]}"


@pytest.mark.parametrize(
    "new",
    [b"\xff\xfe\x00", b"\x00\x01\x02", b"{", b'{"nodes": [', b'"nodes"'],
)
def test_bytes_that_are_not_text_or_json_never_raise(tmp_path, new):
    base = as_bytes(editor(tmp_path).data)
    result = analyse(base, new)
    assert result.status == "invalid"
    assert len(result.problems) == 1
    assert result.summary.startswith(f"{BANNER} but cannot be read yet: ")


def test_a_file_saved_by_a_newer_program_is_unreadable(tmp_path):
    ed, _first, _second = linked_pair(tmp_path)
    base = as_bytes(ed.data)
    ed.data["workflow_metadata"]["schema_version"] = WORKFLOW_SCHEMA_VERSION + 1
    result = analyse(base, as_bytes(ed.data))
    assert result.status == "invalid"
    problem = (
        "sales.tds was saved by a newer Trigger Designer "
        f"(schema {WORKFLOW_SCHEMA_VERSION + 1}); "
        f"this program reads up to schema {WORKFLOW_SCHEMA_VERSION}"
    )
    assert result.problems == (problem,)
    assert result.summary == f"{BANNER} but cannot be read yet: {problem}"


def test_a_loop_added_by_hand_makes_the_file_invalid(tmp_path):
    ed, _first, _second = linked_pair(tmp_path)
    base = as_bytes(ed.data)
    add_loop(ed.data)
    result = analyse(base, as_bytes(ed.data))
    assert result.status == "invalid"
    assert result.problems == ("the graph has a cycle",)
    assert (
        result.summary == f"{BANNER} but is not a valid workflow: the graph has a cycle"
    )


def test_a_node_id_used_twice_makes_the_file_invalid(tmp_path):
    ed, first, _second = linked_pair(tmp_path)
    base = as_bytes(ed.data)
    ed.data["nodes"][1]["id"] = first
    result = analyse(base, as_bytes(ed.data))
    problem = f"node id {first} is used by more than one node"
    assert result.status == "invalid"
    assert result.problems == (problem,)
    assert result.summary == f"{BANNER} but is not a valid workflow: {problem}"


def test_an_unknown_node_type_makes_the_file_invalid(tmp_path):
    ed, _first, _second = linked_pair(tmp_path)
    base = as_bytes(ed.data)
    ed.data["nodes"][0]["op"] = "preparation.nonexistent"
    result = analyse(base, as_bytes(ed.data))
    problem = "unknown node type 'preparation.nonexistent' (node 'Sort')"
    assert result.status == "invalid"
    assert result.problems == (problem,)
    assert result.summary == f"{BANNER} but is not a valid workflow: {problem}"


def test_a_node_with_malformed_sockets_is_invalid_and_does_not_raise(tmp_path):
    ed, _first, _second = linked_pair(tmp_path)
    base = as_bytes(ed.data)
    ed.data["nodes"][0]["inputs"] = 5
    result = analyse(base, as_bytes(ed.data))
    assert result.status == "invalid"
    assert result.problems[0].startswith("sales.tds could not be checked (")


# -------------------------------------------------------------- properties
def test_without_a_path_the_file_is_called_the_file(tmp_path):
    base = as_bytes(editor(tmp_path).data)
    result = analyse_external_edit(base, b"", "")
    assert result.problems == ("the file is empty",)
    assert result.summary == f"{BANNER} but cannot be read yet: the file is empty"


def test_the_same_pair_gives_the_same_result_every_time(tmp_path):
    ed, first, _second = linked_pair(tmp_path)
    base = as_bytes(ed.data)
    ed.set_label(first, "First")
    new = as_bytes(ed.data)
    assert analyse(base, new) == analyse(base, new)
    unreadable_base = b"this was never a workflow"
    assert analyse(unreadable_base, new) == analyse(unreadable_base, new)


def test_the_analysis_is_exported_from_the_authoring_package():
    assert "ExternalChange" in authoring.__all__
    assert "analyse_external_edit" in authoring.__all__
    assert authoring.ExternalChange is ExternalChange
    assert authoring.analyse_external_edit is analyse_external_edit
