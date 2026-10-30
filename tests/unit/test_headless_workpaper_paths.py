"""Workpaper Output paths under the CLI: remap, --param, relativize, versioning."""

from __future__ import annotations

import json
import os

import pytest

from tests.support.cli import call_main, synthetic_workflow, write_workflow
from trigger_designer.core.headless.exit_codes import CliError
from trigger_designer.core.headless.params import apply_params, read_param_defs
from trigger_designer.core.headless.workflow_file import file_nodes, read_workflow

WP_ID = 104


def _wp_node(**settings):
    return {
        "id": WP_ID,
        "op": "input.workpaper_output",
        "title": "Workpaper Output",
        "inputs": [{"id": 1041}, {"id": 1042}, {"id": 1043}],
        "outputs": [],
        "content": {"settings": {"if_exists": "version", **settings}},
    }


def _doc(tmp_path, *, params=None, **settings):
    data = synthetic_workflow(extra_nodes=[_wp_node(**settings)])
    if params is not None:
        data["workflow_metadata"]["parameters"] = params
    return read_workflow(str(write_workflow(tmp_path / "wf" / "wf.tds", data)))


def _apply(doc, overrides=None, **kw):
    kw.setdefault("cwd", str(doc.base_dir))
    return apply_params(doc, read_param_defs(doc), overrides or {}, **kw)


def _settings(applied):
    node = next(n for n in applied.data["nodes"] if n["id"] == WP_ID)
    return node["content"]["settings"]


PARAM = {
    "name": "workpaper_file",
    "type": "path_out",
    "node_id": WP_ID,
    "setting": "output_path",
    "default": None,
    "required": False,
}


def test_output_dir_remaps_the_workpaper_path(tmp_path):
    doc = _doc(tmp_path, output_path="C:/Reports/wp.xlsx")
    target = tmp_path / "elsewhere"
    target.mkdir()
    applied = _apply(doc, output_dir=str(target))
    refs = {r.key: r for r in applied.outputs if r.node_id == WP_ID}
    assert refs["output_path"].path == str(target / "wp.xlsx")
    assert _settings(applied)["output_path"] == str(target / "wp.xlsx")


def test_param_binds_the_workpaper_output_path(tmp_path):
    doc = _doc(tmp_path, params=[PARAM], output_path="C:/Reports/wp.xlsx")
    given = str(tmp_path / "chosen" / "ledger_wp.xlsx")
    applied = _apply(doc, {"workpaper_file": given})
    assert applied.resolved["workpaper_file"] == given
    assert _settings(applied)["output_path"] == given
    assert any(r.path == given and r.bound == "workpaper_file" for r in applied.outputs)


def test_params_add_accepts_workpaper_output_path(tmp_path):
    path = write_workflow(
        tmp_path / "wf.tds", synthetic_workflow(extra_nodes=[_wp_node(output_path="a")])
    )
    result = call_main(
        [
            "params",
            "add",
            path,
            "--name",
            "wp",
            "--node",
            "Workpaper Output",
            "--setting",
            "output_path",
        ]
    )
    assert result.code == 0, result.stderr
    block = json.loads(path.read_text(encoding="utf-8"))["workflow_metadata"]
    assert block["parameters"][0]["type"] == "path_out"


def test_version_mode_picks_the_free_name_before_staging(tmp_path):
    """The staged write is always a fresh name, so the CLI must version up front."""
    target = tmp_path / "out"
    target.mkdir()
    (target / "wp.xlsx").write_bytes(b"old")
    doc = _doc(tmp_path, output_path="C:/Reports/wp.xlsx", if_exists="version")
    applied = _apply(doc, output_dir=str(target))
    settings = _settings(applied)
    assert settings["output_path"] == str(target / "wp (2).xlsx")
    assert settings["publish_path"] == str(target / "wp (2).xlsx")
    ref = next(r for r in applied.outputs if r.node_id == WP_ID)
    assert ref.path == str(target / "wp (2).xlsx")


def test_replace_mode_keeps_the_name(tmp_path):
    target = tmp_path / "out"
    target.mkdir()
    (target / "wp.xlsx").write_bytes(b"old")
    doc = _doc(tmp_path, output_path="C:/Reports/wp.xlsx", if_exists="replace")
    applied = _apply(doc, output_dir=str(target))
    assert _settings(applied)["output_path"] == str(target / "wp.xlsx")


def test_fail_mode_refuses_an_existing_workpaper(tmp_path):
    target = tmp_path / "out"
    target.mkdir()
    (target / "wp.xlsx").write_bytes(b"old")
    doc = _doc(tmp_path, output_path="C:/Reports/wp.xlsx", if_exists="fail")
    with pytest.raises(CliError) as caught:
        _apply(doc, output_dir=str(target))
    assert caught.value.td_code == "TD-OUT-010"
    assert "wp.xlsx" in caught.value.message


def test_source_files_follow_input_dir(tmp_path):
    doc = _doc(
        tmp_path,
        output_path="C:/Reports/wp.xlsx",
        source_files="C:/old/ledger.csv\n\nD:/old/other.csv\n",
    )
    in_dir = tmp_path / "in"
    applied = _apply(doc, input_dir=str(in_dir))
    assert _settings(applied)["source_files"].splitlines() == [
        str(in_dir / "ledger.csv"),
        str(in_dir / "other.csv"),
    ]


def test_relative_source_files_resolve_against_the_workflow_folder(tmp_path):
    doc = _doc(tmp_path, output_path="wp.xlsx", source_files="data/ledger.csv")
    applied = _apply(doc)
    assert _settings(applied)["source_files"] == os.path.normpath(
        os.path.join(doc.base_dir, "data", "ledger.csv")
    )
    assert _settings(applied)["output_path"] == os.path.normpath(
        os.path.join(doc.base_dir, "wp.xlsx")
    )


def test_file_listing_names_the_workpaper_output_and_sources(tmp_path):
    doc = _doc(
        tmp_path, output_path="C:/Reports/wp.xlsx", source_files="C:/a.csv\nC:/b.csv"
    )
    rows = [(f.kind, f.key, f.raw_path) for f in file_nodes(doc) if f.node_id == WP_ID]
    assert ("output", "output_path", "C:/Reports/wp.xlsx") in rows
    assert ("input", "source_files", "C:/a.csv") in rows
    assert ("input", "source_files", "C:/b.csv") in rows


def test_paths_relativize_rewrites_output_and_sources(tmp_path):
    base = tmp_path / "wf"
    data = synthetic_workflow(
        extra_nodes=[
            _wp_node(
                output_path=(base / "reports" / "wp.xlsx").as_posix(),
                source_files=(base / "data" / "l.csv").as_posix()
                + "\n"
                + "C:/elsewhere/keep.csv",
            )
        ]
    )
    path = write_workflow(base / "wf.tds", data)
    result = call_main(["paths", path, "--relativize", "--write", "--format", "json"])
    assert result.code == 0, result.stderr
    saved = json.loads(path.read_text(encoding="utf-8"))
    settings = next(n for n in saved["nodes"] if n["id"] == WP_ID)["content"][
        "settings"
    ]
    assert settings["output_path"] == "reports/wp.xlsx"
    assert settings["source_files"].splitlines() == [
        "data/l.csv",
        "C:/elsewhere/keep.csv",
    ]
    assert os.path.exists(str(path) + ".bak")


def test_versioning_rule_matches_the_writer(tmp_path):
    from trigger_designer.core.headless.params import unique_path as cli_rule
    from trigger_designer.core.workpaper.paths import unique_path as writer_rule

    for name in ("a.xlsx", "a (2).xlsx"):
        (tmp_path / name).write_bytes(b"x")
    target = str(tmp_path / "a.xlsx")
    assert cli_rule(target) == writer_rule(target) == str(tmp_path / "a (3).xlsx")
