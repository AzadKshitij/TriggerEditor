"""Safe workflow authoring over the plain JSON (AI plan, phase 2).

No editor window: ``core/authoring`` works on the dict of a ``.tds`` file. The
real-editor comparison lives in ``tests/ui/test_authoring_matches_gui.py``.
"""

from __future__ import annotations

import json
import os

import pytest

from trigger_designer.core.authoring import (
    Editor,
    apply_patch,
    diff_workflows,
    render_lines,
)
from trigger_designer.core.authoring.edits import ROW
from trigger_designer.core.authoring.model import iter_ids
from trigger_designer.core.authoring.validate import Raw
from trigger_designer.core.headless import access_policy as ap
from trigger_designer.core.headless.exit_codes import CliError, ExitCode
from trigger_designer.core.headless.node_spec import list_ops, settings_schema
from trigger_designer.core.headless.workflow_file import (
    parse_workflow_bytes,
    static_validate,
)


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


@pytest.fixture
def ed(tmp_path):
    return Editor(empty(), base_dir=str(tmp_path))


def err(code: str, fn, *args, **kwargs) -> CliError:
    with pytest.raises(CliError) as caught:
        fn(*args, **kwargs)
    assert caught.value.td_code == code, caught.value.message
    return caught.value


# ------------------------------------------------------------------ add node
def test_new_node_has_defaults_sockets_and_unique_ids(ed):
    info = ed.add_node("preparation.filter")
    node = next(n for n in ed.data["nodes"] if n["id"] == info["id"])
    assert node["op"] == "preparation.filter" and node["title"] == "Filter"
    assert node["content"] == {"settings": node["content"]["settings"]}
    assert len(node["inputs"]) == 1 and len(node["outputs"]) == 2
    assert [s["index"] for s in node["outputs"]] == [0, 1]
    ids = list(iter_ids(ed.data))
    assert len(ids) == len(set(ids))


def test_new_ids_continue_above_the_highest_existing_id(tmp_path):
    data = empty()
    data["id"] = 7_000_000_000_000
    editor = Editor(data, base_dir=str(tmp_path))
    info = editor.add_node("preparation.sort")
    assert info["id"] > 7_000_000_000_000


def test_audit_node_keeps_its_settings_in_content_not_a_settings_object(ed):
    info = ed.add_node("audit.duplicates")
    node = next(n for n in ed.data["nodes"] if n["id"] == info["id"])
    assert "settings" not in node["content"] and node["content"]
    last = node["outputs"][-1]
    assert last["socket_type"] == 1  # the status output


def test_unknown_node_type_suggests_a_near_one(ed):
    error = err("TD-CLI-003", ed.add_node, "preparation.filtr")
    assert "preparation.filter" in error.hint


def test_original_data_is_never_touched(tmp_path):
    data = empty()
    before = json.dumps(data, sort_keys=True)
    editor = Editor(data, base_dir=str(tmp_path))
    editor.add_node("preparation.sort")
    assert json.dumps(data, sort_keys=True) == before


def test_default_position_goes_below_the_lowest_node_and_never_overlaps(ed):
    a = ed.add_node("preparation.sort", x=0, y=0)
    b = ed.add_node("preparation.sort", after=a["id"])
    c = ed.add_node("preparation.sort", after=a["id"])
    nodes = {n["id"]: n for n in ed.data["nodes"]}
    assert nodes[b["id"]]["pos_y"] == ROW
    assert (nodes[c["id"]]["pos_x"], nodes[c["id"]]["pos_y"]) != (
        nodes[b["id"]]["pos_x"],
        nodes[b["id"]]["pos_y"],
    )


def test_x_without_y_is_refused(ed):
    err("TD-CLI-027", ed.add_node, "preparation.sort", x=1)


# ------------------------------------------------------------------ settings
def test_set_settings_changes_only_what_differs(ed):
    info = ed.add_node("preparation.filter")
    out = ed.set_settings(info["id"], {"column": "Amount", "operation": ">"})
    assert sorted(out["changed"]) == ["column", "operation"]
    assert ed.set_settings(info["id"], {"column": "Amount"})["changed"] == []


def test_unknown_setting_is_refused_with_a_suggestion(ed):
    info = ed.add_node("preparation.filter")
    error = err("TD-CLI-022", ed.set_settings, info["id"], {"colum": "x"})
    assert "column" in error.hint


def test_wrong_type_is_refused(ed):
    info = ed.add_node("preparation.filter")
    err("TD-CLI-022", ed.set_settings, info["id"], {"column": 5})


def test_a_bool_is_not_a_whole_number():
    # bool is an int in Python; a settings file must not accept it as one.
    for row in list_ops():
        props = settings_schema(row["op"])["properties"]
        ints = [k for k, v in props.items() if v.get("type") == "integer"]
        if ints:
            break
    else:  # pragma: no cover - guards the search itself
        pytest.skip("no integer setting exists")
    editor = Editor(empty(), base_dir=".")
    info = editor.add_node(row["op"])
    err("TD-CLI-022", editor.set_settings, info["id"], {ints[0]: True})


def test_raw_command_line_text_takes_the_settings_type(ed):
    info = ed.add_node("preparation.filter")
    ed.set_settings(info["id"], {"value": Raw("10000")})  # a text setting
    node = ed.node(info["id"])
    assert node["content"]["settings"]["value"] == "10000"


def test_settings_and_values_that_are_not_plain_json_are_refused(ed):
    info = ed.add_node("preparation.filter")
    err("TD-CLI-027", ed.set_settings, info["id"], {})
    err("TD-CLI-022", ed.set_settings, info["id"], {"value": float("nan")})


# --------------------------------------------------------------------- paths
def test_file_settings_may_stay_inside_the_workflow_folder(tmp_path):
    editor = Editor(empty(), base_dir=str(tmp_path))
    info = editor.add_node("input.file_output")
    editor.set_settings(info["id"], {"filePath": "out/result.csv"})
    inside = str(tmp_path / "deep" / "x.csv")
    editor.set_settings(info["id"], {"filePath": inside})


@pytest.mark.parametrize("bad", ["..\\..\\x.csv", "../x.csv", "C:\\Windows\\x.csv"])
def test_file_settings_outside_the_folder_are_refused(tmp_path, bad):
    editor = Editor(empty(), base_dir=str(tmp_path / "wf"))
    info = editor.add_node("input.file_output")
    error = err("TD-CLI-024", editor.set_settings, info["id"], {"filePath": bad})
    assert error.code == ExitCode.REFUSED


def test_a_policy_can_list_extra_folders(tmp_path):
    extra = tmp_path / "shared"
    editor = Editor(empty(), base_dir=str(tmp_path / "wf"), extra_paths=(str(extra),))
    info = editor.add_node("input.file_output")
    editor.set_settings(info["id"], {"filePath": str(extra / "out.csv")})


def test_a_folder_that_only_shares_a_name_prefix_is_outside(tmp_path):
    root = tmp_path / "wf"
    editor = Editor(empty(), base_dir=str(root))
    info = editor.add_node("input.file_output")
    sibling = os.path.join(str(tmp_path), "wf-other", "x.csv")
    err("TD-CLI-024", editor.set_settings, info["id"], {"filePath": sibling})


# ----------------------------------------------------------------------- SQL
@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM read_csv('x.csv')",
        "SELECT 1; DROP TABLE t1",
        "COPY t1 TO 'x.csv'",
    ],
)
def test_sql_that_is_not_one_read_only_select_is_refused(ed, sql):
    info = ed.add_node("transform.sql_query")
    err("TD-CLI-025", ed.set_settings, info["id"], {"sql": sql})


def test_a_plain_select_is_accepted(ed):
    info = ed.add_node("transform.sql_query")
    ed.set_settings(info["id"], {"sql": "SELECT a, b FROM t1 WHERE a > 3"})


def test_sql_in_a_filter_expression_goes_through_the_guard(ed):
    info = ed.add_node("preparation.filter")
    err(
        "TD-CLI-025",
        ed.set_settings,
        info["id"],
        {"expression": "1=1 OR (SELECT count(*) FROM read_csv('x')) > 0"},
    )
    ed.set_settings(info["id"], {"expression": '"Amount" > 10 AND "Kind" = \'A\''})


def test_a_bad_query_added_with_the_node_never_creates_it(ed):
    err(
        "TD-CLI-025",
        ed.add_node,
        "transform.sql_query",
        settings={"sql": "SELECT * FROM read_csv('x')"},
    )
    assert ed.data["nodes"] == []


# ---------------------------------------------------------------- connecting
def chain(ed, n=2, op="preparation.sort"):
    return [ed.add_node(op, ref=f"n{i}")["id"] for i in range(n)]


def test_connect_by_output_name_and_number(ed):
    f = ed.add_node("preparation.filter")["id"]
    a, b = chain(ed)
    ed.connect(f, "true", a)
    ed.connect(f, 1, b)
    starts = {e["start"] for e in ed.data["edges"]}
    assert len(starts) == 2


def test_a_bad_output_name_lists_the_real_ones(ed):
    f = ed.add_node("preparation.filter")["id"]
    (a,) = chain(ed, 1)
    error = err("TD-CLI-023", ed.connect, f, "maybe", a)
    assert "true" in error.hint and "false" in error.hint


def test_an_occupied_single_input_is_refused(ed):
    a, b, c = chain(ed, 3)
    ed.connect(a, 0, c)
    err("TD-CLI-023", ed.connect, b, 0, c)


def test_connecting_twice_and_to_itself_are_refused(ed):
    a, b = chain(ed)
    ed.connect(a, 0, b)
    err("TD-CLI-023", ed.connect, a, 0, b)
    err("TD-CLI-023", ed.connect, a, 0, a)


def test_a_loop_is_refused_and_leaves_no_edge_behind(ed):
    a, b = chain(ed)
    ed.connect(a, 0, b)
    before = len(ed.data["edges"])
    err("TD-CLI-023", ed.connect, b, 0, a)
    assert len(ed.data["edges"]) == before


def test_an_input_that_does_not_exist_is_refused(ed):
    a, b = chain(ed)
    err("TD-CLI-023", ed.connect, a, 0, b, 3)


def test_union_takes_many_inputs_numbered_in_order_and_renumbers_on_removal(ed):
    a, b, c = chain(ed, 3)
    u = ed.add_node("join.union")["id"]
    for src in (a, b, c):
        ed.connect(src, 0, u)
    into = [e for e in ed.data["edges"] if e["label"]]
    assert [(e["input_index"], e["label"]) for e in into] == [
        (0, "#1"),
        (1, "#2"),
        (2, "#3"),
    ]
    ed.disconnect(a, 0, u)
    into = sorted(
        (e for e in ed.data["edges"] if e["label"]), key=lambda e: e["input_index"]
    )
    assert [(e["input_index"], e["label"]) for e in into] == [(0, "#1"), (1, "#2")]


def test_disconnect_an_edge_that_is_not_there_is_refused(ed):
    a, b = chain(ed)
    err("TD-CLI-023", ed.disconnect, a, 0, b)


# ------------------------------------------------------------- remove / label
def test_removing_a_node_removes_its_edges_and_group_membership(ed):
    a, b = chain(ed)
    ed.connect(a, 0, b)
    ed.data["groups"].append({"id": 1, "children": [a, b]})
    out = ed.remove_node(a)
    assert out["removed_edges"] == 1
    assert ed.data["edges"] == [] and ed.data["groups"][0]["children"] == [b]
    assert [n["id"] for n in ed.data["nodes"]] == [b]


def test_a_node_a_parameter_points_at_cannot_be_removed(ed):
    info = ed.add_node("input.file_output")
    ed.data["workflow_metadata"]["parameters"] = [
        {"name": "out", "node_id": info["id"], "setting": "filePath"}
    ]
    err("TD-CLI-027", ed.remove_node, info["id"])


def test_label(ed):
    info = ed.add_node("preparation.sort")
    ed.set_label(info["id"], " Biggest first ", True)
    node = ed.node(info["id"])
    assert node["label_text"] == "Biggest first" and node["label_visible"] is True
    err("TD-CLI-027", ed.set_label, info["id"], "x", "yes")


def test_a_node_is_found_by_id_unique_title_or_op_and_never_guessed(ed):
    a, _b = chain(ed)
    assert ed.node(a)["id"] == a
    ed.node(str(a))
    err("TD-CLI-020", ed.node, "Sort")  # two nodes are titled Sort
    err("TD-CLI-020", ed.node, "nothing")
    f = ed.add_node("preparation.filter")["id"]
    assert ed.node("Filter")["id"] == f
    assert ed.node("preparation.filter")["id"] == f


# -------------------------------------------------------------------- layout
def test_layout_stacks_a_chain_top_to_bottom(ed):
    a, b, c = chain(ed, 3)
    ed.connect(a, 0, b)
    ed.connect(b, 0, c)
    for n in ed.data["nodes"]:
        n["pos_x"], n["pos_y"] = 500.0, 500.0
    ed.auto_layout()
    pos = {n["id"]: (n["pos_x"], n["pos_y"]) for n in ed.data["nodes"]}
    assert pos[b][1] - pos[a][1] == ROW and pos[c][1] - pos[b][1] == ROW
    assert pos[a][0] == pos[b][0] == pos[c][0]
    assert ed.auto_layout() == {"moved": 0}


def test_layout_refuses_a_workflow_with_groups(ed):
    chain(ed)
    ed.data["groups"].append({"id": 9, "children": []})
    err("TD-CLI-027", ed.auto_layout)


# ----------------------------------------------------------------------- diff
def test_diff_reports_nodes_settings_connections_and_moves(tmp_path):
    base = Editor(empty(), base_dir=str(tmp_path))
    f = base.add_node("preparation.filter")["id"]
    s = base.add_node("preparation.sort")["id"]
    old = base.data
    new = Editor(old, base_dir=str(tmp_path))
    new.set_settings(f, {"column": "Amount"})
    new.connect(f, 0, s)
    new.node(s)["pos_x"] += 50
    added = new.add_node("preparation.select")["id"]
    result = diff_workflows(old, new.data)
    assert not result["empty"]
    assert [n["id"] for n in result["nodes"]["added"]] == [added]
    changed = {
        n["id"]: {c["path"] for c in n["changes"]} for n in result["nodes"]["changed"]
    }
    assert changed[f] == {"content.settings.column"}
    assert changed[s] == {"position"}
    assert len(result["connections"]["added"]) == 1
    assert any("connect" in line for line in render_lines(result))


def test_diff_of_equal_workflows_is_empty(tmp_path):
    editor = Editor(empty(), base_dir=str(tmp_path))
    editor.add_node("preparation.sort")
    result = diff_workflows(editor.data, json.loads(json.dumps(editor.data)))
    assert result["empty"] and render_lines(result) == ["(no differences)"]


# --------------------------------------------------------------------- patch
PATCH = [
    {
        "op": "add_node",
        "type": "preparation.filter",
        "ref": "f",
        "settings": {"column": "Amount", "operation": ">", "value": "10000"},
    },
    {"op": "add_node", "type": "preparation.sort", "ref": "s", "after": "f"},
    {"op": "connect", "from": "f", "output": "true", "to": "s"},
    {"op": "label", "node": "s", "text": "Large first"},
]


def test_a_patch_can_name_the_nodes_it_creates(ed):
    results = apply_patch(ed, PATCH)
    assert [r["action"] for r in results] == [
        "add_node",
        "add_node",
        "connect",
        "label",
    ]
    assert len(ed.data["nodes"]) == 2 and len(ed.data["edges"]) == 1
    raw = json.dumps(ed.data).encode()
    errors = [
        f for f in static_validate(parse_workflow_bytes(raw)) if f.level == "error"
    ]
    assert errors == []


def test_a_failing_edit_names_its_position_and_the_caller_keeps_the_original(tmp_path):
    original = empty()
    editor = Editor(original, base_dir=str(tmp_path))
    bad = [*PATCH, {"op": "connect", "from": "s", "to": "f"}]
    error = err("TD-CLI-023", apply_patch, editor, bad)
    assert error.message.startswith("edit 5 (connect):")
    assert original["nodes"] == []  # nothing the caller holds was changed


@pytest.mark.parametrize(
    "ops, fragment",
    [
        ([{"op": "explode"}], "unknown operation"),
        ([{"op": "connect", "from": "a"}], "needs: to"),
        ([{"op": "layout", "when": "now"}], "unknown field"),
        ([], "empty"),
        ("not a list", "JSON list"),
        ([5], "must be an object"),
    ],
)
def test_malformed_patches_are_refused(ed, ops, fragment):
    error = err("TD-CLI-027", apply_patch, ed, ops)
    assert fragment in error.message


def test_a_patch_may_be_wrapped_in_an_object(ed):
    assert len(apply_patch(ed, {"operations": PATCH[:1]})) == 1


def test_a_ref_must_be_a_name_and_unique(ed):
    err("TD-CLI-027", ed.add_node, "preparation.sort", ref="1x")
    ed.add_node("preparation.sort", ref="a")
    err("TD-CLI-027", ed.add_node, "preparation.sort", ref="a")


# -------------------------------------------------------------------- policy
def test_policy_reads_edit_and_extra_paths(tmp_path):
    policy = ap.parse_policy(
        json.dumps({"access": "schema_only", "edit": True, "paths": ["D:\\shared"]}),
        str(tmp_path / "p.json"),
    )
    assert policy.edit and policy.paths == ("D:\\shared",)
    ap.require_edit(policy)


def test_editing_is_refused_by_default(tmp_path):
    with pytest.raises(CliError) as caught:
        ap.require_edit(ap.AccessPolicy())
    assert (
        caught.value.code == ExitCode.REFUSED and caught.value.td_code == "TD-CLI-019"
    )


@pytest.mark.parametrize("paths", ["D:\\x", [1], [""], {"a": 1}])
def test_policy_paths_must_be_a_list_of_folders(tmp_path, paths):
    with pytest.raises(CliError) as caught:
        ap.parse_policy(json.dumps({"paths": paths}), str(tmp_path / "p.json"))
    assert caught.value.td_code == "TD-CLI-006"


# ----------------------------------------------------------------------- new
def test_a_new_workflow_is_empty_valid_and_has_its_own_identity(tmp_path):
    from trigger_designer.core.authoring import new_workflow

    a, b = new_workflow(), new_workflow()
    assert a["nodes"] == [] and a["edges"] == []
    meta = a["workflow_metadata"]
    assert meta["schema_version"] == 2 and meta["workflow_uuid"]
    assert meta["workflow_uuid"] != b["workflow_metadata"]["workflow_uuid"]
    doc = parse_workflow_bytes(json.dumps(a).encode())
    assert [f for f in static_validate(doc) if f.level == "error"] == []
    editor = Editor(a, base_dir=str(tmp_path))
    assert editor.add_node("preparation.sort")["id"] > a["id"]


# ------------------------------------------------------- File Input paths
def test_a_file_input_path_also_sets_the_relative_path_the_editor_reads(tmp_path):
    editor = Editor(empty(), base_dir=str(tmp_path))
    info = editor.add_node("input.file_input", settings={"filePath": "data/in.csv"})
    content = editor.node(info["id"])["content"]
    assert content["filePath"] == "data/in.csv"
    assert content["filePathRel"] == "data/in.csv"
    absolute = str(tmp_path / "other" / "x.csv")
    editor.set_settings(info["id"], {"filePath": absolute})
    assert content["filePathRel"] == "other/x.csv"
    editor.set_settings(info["id"], {"filePath": ""})
    assert content["filePathRel"] == ""


def test_filePathRel_cannot_be_set_directly(tmp_path):
    editor = Editor(empty(), base_dir=str(tmp_path))
    info = editor.add_node("input.file_input")
    err("TD-CLI-022", editor.set_settings, info["id"], {"filePathRel": "x.csv"})
