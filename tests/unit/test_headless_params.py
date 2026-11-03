"""Parameters, remapping and the work copy (plan 08 3.5, S2)."""

from __future__ import annotations

import json
import os

import pytest

from tests.support.cli import call_main, synthetic_workflow, write_workflow
from trigger_designer.core.headless.exit_codes import CliError, ExitCode
from trigger_designer.core.headless.params import (
    apply_params,
    parse_cli_params,
    read_param_defs,
    write_workflow_ascii,
)
from trigger_designer.core.headless.workflow_file import (
    parse_workflow_bytes,
    read_workflow,
)

PARAMS = [
    {
        "name": "input_file",
        "type": "path_in",
        "node_id": 101,
        "setting": "filePath",
        "default": "default_in.csv",
        "required": False,
    },
    {
        "name": "output_file",
        "type": "path_out",
        "node_id": 103,
        "setting": "filePath",
        "default": None,
        "required": False,
    },
    {
        "name": "needle",
        "type": "string",
        "node_id": 102,
        "setting": "value",
        "default": "dflt",
        "required": False,
    },
]


def _doc(tmp_path, params=None, **kw):
    data = synthetic_workflow(**kw)
    if params is not None:
        data["workflow_metadata"]["parameters"] = params
    return read_workflow(str(write_workflow(tmp_path / "wf" / "wf.tds", data)))


def _apply(doc, overrides=None, **kw):
    kw.setdefault("cwd", str(doc.base_dir))
    return apply_params(doc, read_param_defs(doc), overrides or {}, **kw)


def _content(applied, node_id):
    return next(n for n in applied.data["nodes"] if n["id"] == node_id)["content"]


def test_parse_cli_params_splits_on_first_equals():
    assert parse_cli_params(["a=b=c", "x="]) == {"a": "b=c", "x": ""}


@pytest.mark.parametrize("item", ["novalue", "=x"])
def test_parse_cli_params_rejects_malformed(item):
    with pytest.raises(CliError) as exc:
        parse_cli_params([item])
    assert exc.value.td_code == "TD-CLI-006"


def test_unknown_param_lists_names(tmp_path):
    doc = _doc(tmp_path, PARAMS)
    with pytest.raises(CliError) as exc:
        _apply(doc, {"nope": "1"})
    assert exc.value.td_code == "TD-CLI-005"
    assert "input_file" in exc.value.message and "needle" in exc.value.message


def test_int_type_error_has_example(tmp_path):
    params = [
        {"name": "seed", "type": "int", "node_id": 102, "setting": "random_seed"},
    ]
    data = synthetic_workflow()
    data["nodes"][1]["op"] = "preparation.split"
    data["workflow_metadata"]["parameters"] = params
    doc = read_workflow(str(write_workflow(tmp_path / "wf.tds", data)))
    with pytest.raises(CliError) as exc:
        _apply(doc, {"seed": "1.5"})
    assert exc.value.td_code == "TD-CLI-006"
    assert "Example" in exc.value.hint
    with pytest.raises(CliError):
        _apply(doc, {"seed": str(2**31)})
    assert _content(_apply(doc, {"seed": "42"}), 102)["settings"]["random_seed"] == 42


def test_target_outside_safe_set_td_cli_007(tmp_path):
    bad = [{"name": "delim", "type": "string", "node_id": 101, "setting": "delimiter"}]
    doc = _doc(tmp_path, bad)
    with pytest.raises(CliError) as exc:
        read_param_defs(doc)
    assert exc.value.td_code == "TD-CLI-007"


def test_db_query_not_bindable(tmp_path):
    bad = [{"name": "q", "type": "string", "node_id": 101, "setting": "db_query"}]
    with pytest.raises(CliError) as exc:
        read_param_defs(_doc(tmp_path, bad))
    assert exc.value.td_code == "TD-CLI-007"


def test_filter_expression_mode_refused(tmp_path):
    doc = _doc(tmp_path, PARAMS, filter_mode="expression")
    with pytest.raises(CliError) as exc:
        _apply(doc, {"needle": "abc"})
    assert exc.value.td_code == "TD-CLI-007"


@pytest.mark.parametrize("value", ["a'b", "a\\b", "a\nb", "a\x00b"])
def test_forbidden_chars_in_sheet_and_value(tmp_path, value):
    doc = _doc(tmp_path, PARAMS)
    with pytest.raises(CliError) as exc:
        _apply(doc, {"needle": value})
    assert exc.value.td_code == "TD-CLI-006"
    sheet = [
        {"name": "sheet", "type": "string", "node_id": 101, "setting": "selected_sheet"}
    ]
    doc = _doc(tmp_path, sheet)
    with pytest.raises(CliError):
        _apply(doc, {"sheet": value})


def test_folder_glob_and_include_patterns_bindable(tmp_path):
    params = [
        {"name": "folder", "type": "path_in", "node_id": 101, "setting": "filePath"},
        {
            "name": "inc",
            "type": "string",
            "node_id": 101,
            "setting": "include_patterns",
        },
        {"name": "cap", "type": "int", "node_id": 101, "setting": "max_files"},
        {"name": "tbl", "type": "string", "node_id": 101, "setting": "db_table"},
    ]
    doc = _doc(tmp_path, params)
    applied = _apply(
        doc,
        {
            "folder": str(tmp_path / "in" / "*.csv"),
            "inc": "*.csv, *.txt",
            "cap": "5",
            "tbl": "t_1",
        },
    )
    content = _content(applied, 101)
    assert content["filePath"].endswith("*.csv")
    assert content["include_patterns"] == ["*.csv", "*.txt"]
    assert content["max_files"] == 5 and content["db_table"] == "t_1"
    with pytest.raises(CliError):
        _apply(doc, {"tbl": "x; drop table"})
    with pytest.raises(CliError):
        _apply(doc, {"cap": "0"})


def test_required_missing(tmp_path):
    params = [dict(PARAMS[0], required=True, default=None)]
    with pytest.raises(CliError) as exc:
        _apply(_doc(tmp_path, params))
    assert exc.value.td_code == "TD-CLI-005"
    assert "input_file" in exc.value.message


def test_duplicate_param_names(tmp_path):
    with pytest.raises(CliError) as exc:
        read_param_defs(_doc(tmp_path, [PARAMS[0], dict(PARAMS[0])]))
    assert "Duplicate" in exc.value.message


def test_precedence_param_over_dir_over_default_over_saved(tmp_path):
    doc = _doc(tmp_path, PARAMS, input_path="saved/in.csv")
    in_dir = tmp_path / "indir"
    base = doc.base_dir
    # (4) saved value, no param default consulted when the default is absent
    no_default = [dict(PARAMS[0], default=None)]
    d2 = _doc(tmp_path, no_default, input_path="saved/in.csv")
    assert _apply(d2).inputs[0].path == os.path.normpath(
        os.path.join(base, "saved", "in.csv")
    )
    # (3) default
    assert _apply(doc).inputs[0].path == os.path.normpath(
        os.path.join(base, "default_in.csv")
    )
    # (2) --input-dir remaps the default's basename
    assert _apply(doc, input_dir=str(in_dir)).inputs[0].path == str(
        in_dir / "default_in.csv"
    )
    # (1) explicit --param wins over the dir
    explicit = str(tmp_path / "x" / "given.csv")
    applied = _apply(doc, {"input_file": explicit}, input_dir=str(in_dir))
    assert applied.inputs[0].path == explicit
    assert applied.resolved["input_file"] == explicit


def test_dir_remap_applies_to_unbound_nodes_only(tmp_path):
    only_output = [PARAMS[1]]
    doc = _doc(
        tmp_path,
        only_output,
        input_path="C:/Projects/data/check.csv",
        output_path="C:/Projects/out/o.csv",
    )
    given = str(tmp_path / "explicit_out.csv")
    applied = _apply(
        doc,
        {"output_file": given},
        input_dir=str(tmp_path / "in"),
        output_dir=str(tmp_path / "out"),
    )
    assert applied.inputs[0].path == str(tmp_path / "in" / "check.csv")
    assert applied.outputs[0].path == given


def test_file_path_override_deletes_file_path_rel(tmp_path):
    doc = _doc(tmp_path, [PARAMS[0]], input_path="stale.csv", input_rel="stale.csv")
    assert "filePathRel" not in _content(_apply(doc, {"input_file": "x.csv"}), 101)
    # a remapped, unbound input drops it too
    doc = _doc(tmp_path, None, input_path="stale.csv", input_rel="stale.csv")
    assert "filePathRel" not in _content(_apply(doc, input_dir=str(tmp_path)), 101)


def test_file_path_rel_is_preferred_when_it_exists(tmp_path):
    (tmp_path / "wf").mkdir()
    (tmp_path / "wf" / "near.csv").write_text("a\n1\n")
    doc = _doc(tmp_path, None, input_path="C:/gone/far.csv", input_rel="near.csv")
    assert _apply(doc).inputs[0].path == os.path.normpath(
        str(tmp_path / "wf" / "near.csv")
    )


def test_original_document_not_mutated(tmp_path):
    doc = _doc(tmp_path, PARAMS)
    before = json.dumps(doc.data, sort_keys=True)
    _apply(doc, {"needle": "zzz", "input_file": "a.csv"})
    assert json.dumps(doc.data, sort_keys=True) == before


def test_work_copy_is_ascii_json(tmp_path):
    doc = _doc(tmp_path, PARAMS)
    applied = _apply(
        doc, {"needle": "caf\xe9", "input_file": str(tmp_path / "r\xe9sum\xe9.csv")}
    )
    target = tmp_path / "work.tds"
    write_workflow_ascii(applied.data, target)
    raw = target.read_bytes()
    assert raw.isascii() and b"\\u00e9" in raw
    again = parse_workflow_bytes(raw, str(target))
    assert (
        next(n for n in again.nodes if n["id"] == 102)["content"]["settings"]["value"]
        == "caf\xe9"
    )


def test_params_add_writes_backup_and_block(tmp_path):
    path = write_workflow(tmp_path / "wf.tds", synthetic_workflow())
    result = call_main(
        [
            "params",
            "add",
            path,
            "--name",
            "input_file",
            "--node",
            "File Input",
            "--setting",
            "filePath",
            "--required",
        ]
    )
    assert result.code == 0, result.stderr
    assert os.path.exists(str(path) + ".bak")
    block = json.loads(path.read_text(encoding="utf-8"))["workflow_metadata"][
        "parameters"
    ]
    assert block[0]["name"] == "input_file" and block[0]["required"] is True
    assert block[0]["type"] == "path_in" and block[0]["node_id"] == 101
    listed = call_main(["params", "list", path, "--format", "json"])
    assert listed.json()[0]["name"] == "input_file"
    removed = call_main(["params", "remove", path, "--name", "input_file"])
    assert removed.code == 0
    assert (
        json.loads(path.read_text(encoding="utf-8"))["workflow_metadata"]["parameters"]
        == []
    )


def test_params_add_rejects_unsupported_setting_and_bad_type(tmp_path):
    path = write_workflow(tmp_path / "wf.tds", synthetic_workflow())
    base = ["params", "add", path, "--name", "p", "--node", "101"]
    result = call_main([*base, "--setting", "delimiter"])
    assert result.code == int(ExitCode.INVALID) and "TD-CLI-007" in result.stderr
    result = call_main([*base, "--setting", "filePath", "--type", "string"])
    assert result.code == int(ExitCode.INVALID)
    result = call_main(
        [
            "params",
            "add",
            path,
            "--name",
            "Bad Name",
            "--node",
            "101",
            "--setting",
            "filePath",
        ]
    )
    assert result.code == int(ExitCode.INVALID)


def test_params_add_ambiguous_title_needs_id(tmp_path):
    data = synthetic_workflow()
    dup = dict(data["nodes"][0], id=555, outputs=[{"id": 5551}])
    data["nodes"].append(dup)
    path = write_workflow(tmp_path / "wf.tds", data)
    result = call_main(
        [
            "params",
            "add",
            path,
            "--name",
            "p",
            "--node",
            "File Input",
            "--setting",
            "filePath",
        ]
    )
    assert result.code == int(ExitCode.INVALID) and "ids" in result.stderr
