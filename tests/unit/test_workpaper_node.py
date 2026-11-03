"""Workpaper Output node: registration, live evaluation, generated code."""

from __future__ import annotations

import ast
import json

import polars as pl
import pytest
from nodeeditor.node_edge import Edge

from tests.support.workpaper import EXCEPTIONS, POPULATION, load
from trigger_designer.core.headless.code_policy import validate_generated_code
from trigger_designer.core.node_configuration import (
    IONodes,
    NodeTypes,
    ReportNodes,
    get_class_from_opcode,
)
from trigger_designer.core.workpaper import node_logic
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.helpers.workflow_snapshot import (
    collect_sources,
    collect_workflow,
)
from trigger_designer.qt.node_base import TriggerNode


class Source(TriggerNode):
    node_title = "Source"

    def __init__(self, scene, frame, name="var_src", ok=True) -> None:
        self._frame, self._name, self._ok = frame, name, ok
        super().__init__(scene, inputs=[], outputs=[3])
        self.value = [{"data": frame if ok else None, "variable_name": name}]
        self.markDirty(False)
        self.markInvalid(not ok)

    def evalImplementation(self):
        data = self._frame if self._ok else None
        self.value = [{"data": data, "variable_name": self._name}]
        self.markDirty(False)
        self.markInvalid(not self._ok)
        return self.value


def _new(qtbot, *, exceptions=True, population=False, summary=False, failing=None):
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    node = get_class_from_opcode(IONodes.WORKPAPER_OUTPUT, NodeTypes.IO)(window.scene)
    feeds = [
        (0, exceptions, EXCEPTIONS, "var_exc"),
        (1, population, POPULATION, "var_pop"),
        (
            2,
            summary,
            pl.DataFrame({"test_name": ["T"], "exception_rows": [3]}),
            "var_sum",
        ),
    ]
    for index, wanted, frame, name in feeds:
        if wanted:
            src = Source(window.scene, frame.lazy(), name, ok=failing != index)
            Edge(window.scene, src.outputs[0], node.inputs[index])
    node.markDirty(True)
    node.eval()
    return window, node


def test_node_is_registered_with_stable_op_id():
    cls = get_class_from_opcode(IONodes.WORKPAPER_OUTPUT, NodeTypes.IO)
    assert cls.__name__ == "TriggerNode_WorkpaperOutput"
    assert int(IONodes.WORKPAPER_OUTPUT) == 5 and int(IONodes.FILE_OUTPUT) == 4
    assert cls.node_title == "Workpaper Output"


def test_op_id_serialises_as_input_workpaper_output(qtbot):
    window, _node = _new(qtbot)
    data = window.scene.serialize()
    entry = next(n for n in data["nodes"] if n["title"] == "Workpaper Output")
    assert entry.get("op") == "input.workpaper_output"


def test_unwired_exceptions_marks_invalid_with_tooltip(qtbot):
    _window, node = _new(qtbot, exceptions=False)
    assert node.isInvalid()
    assert "not connected" in node.grNode.toolTip()


def test_optional_inputs_do_not_invalidate(qtbot):
    _window, node = _new(qtbot)
    assert not node.isInvalid()
    assert node.content.frames[1] is None and node.content.frames[2] is None
    _window, full = _new(qtbot, population=True, summary=True)
    assert not full.isInvalid() and full.content.input_vars == [
        "var_exc",
        "var_pop",
        "var_sum",
    ]


def test_failed_optional_input_invalidates(qtbot):
    _window, node = _new(qtbot, population=True, failing=1)
    assert node.isInvalid()  # never silently dropped from the workpaper


def test_get_code_unwired_raises_and_wired_calls_runner(qtbot):
    _w, unwired = _new(qtbot, exceptions=False)
    with pytest.raises(ValueError, match="connect the Exceptions input"):
        exec(unwired.get_code(), {})  # noqa: S102
    _w, wired = _new(qtbot, population=True, summary=True)
    code = wired.get_code()
    assert code == wired.get_code()
    assert "run_workpaper(" in code and "exceptions=var_exc" in code
    assert "population=var_pop" in code and "summary=var_sum" in code
    assert f"node_id={wired.id}" in code  # lets the runner notice an abandoned step
    _w, minimal = _new(qtbot)
    assert (
        "population=None" in minimal.get_code() and "summary=None" in minimal.get_code()
    )


def test_generated_code_passes_the_headless_policy_and_allowlist(qtbot):
    _w, node = _new(qtbot, population=True)
    code = node.get_code()
    validate_generated_code(code)
    imported = {
        (n.module, tuple(a.name for a in n.names))
        for n in ast.walk(ast.parse(code))
        if isinstance(n, ast.ImportFrom)
    }
    assert imported == {
        ("trigger_designer.core.workpaper.node_runner", ("run_workpaper",))
    }


def test_get_code_executes_and_writes_workbook(qtbot, tmp_path):
    _w, node = _new(qtbot, population=True)
    node.content.settings.update(
        output_path=str(tmp_path / "out.xlsx"),
        amount_column="Amount",
        client="Acme",
        prepared_date="2026-03-31",
    )
    scope = {"var_exc": EXCEPTIONS.lazy(), "var_pop": POPULATION.lazy()}
    exec(node.get_code(), scope)  # noqa: S102
    result = scope["_workpaper_result"]
    wb = load(result["path"], data_only=True)
    assert wb.sheetnames[:2] == ["Summary", "Exceptions"]
    assert wb["Summary"]["B6"].value == "Acme" and wb["Summary"]["B22"].value == 10
    assert wb["Summary"]["B24"].value == 3


def test_user_text_is_embedded_safely(qtbot, tmp_path):
    nasty = 'O\'Brien"; import os; os.system("x") #'
    _w, node = _new(qtbot)
    node.content.settings.update(output_path=str(tmp_path / "o.xlsx"), client=nasty)
    code = node.get_code()
    validate_generated_code(code)
    scope = {"var_exc": EXCEPTIONS.lazy()}
    exec(code, scope)  # noqa: S102
    assert load(scope["_workpaper_result"]["path"])["Summary"]["B6"].value == nasty


def test_serialize_roundtrip_and_old_file_defaults(qtbot):
    _w, node = _new(qtbot)
    node.content.settings.update(
        client="Acme", row_limit=50, source_files="a.csv\nb.csv"
    )
    state = node.content.serialize()
    _w2, other = _new(qtbot)
    other.content.deserialize(json.loads(json.dumps(state, default=str)))
    assert (
        other.content.settings["client"] == "Acme"
        and other.content.settings["row_limit"] == 50
    )
    # a file saved before a setting existed loads with the default
    old = json.loads(json.dumps(state, default=str))
    old["settings"].pop("row_limit")
    _w3, third = _new(qtbot)
    third.content.deserialize(old)
    assert third.content.settings["row_limit"] == node_logic.DEFAULTS["row_limit"]


def test_inherits_engagement_preferences(qtbot, clean_preferences):
    for key, value in {
        "engagement/client_name": "Pref Client",
        "engagement/engagement_name": "Pref Engagement",
        "engagement/period": "FY25",
        "engagement/preparer": "Pref Person",
        "engagement/logo_path": "C:/logo.png",
    }.items():
        clean_preferences.set(key, value)
    _w, node = _new(qtbot)
    spec = node.content.effective_spec()
    assert (spec.client, spec.engagement, spec.period, spec.preparer) == (
        "Pref Client",
        "Pref Engagement",
        "FY25",
        "Pref Person",
    )
    assert spec.logo_path == "C:/logo.png"
    node.content.settings["client"] = "Override"
    assert node.content.effective_spec().client == "Override"


def test_preparer_falls_back_to_the_os_user(qtbot, clean_preferences):
    _w, node = _new(qtbot)
    assert node.content.effective_spec().preparer  # getpass.getuser()


def test_node_logic_spec_defaults_and_clamps():
    spec = node_logic.effective_spec(
        {"value_decimals": "x", "row_limit": "7", "source_files": "a\n\n b "},
        default_user="u",
    )
    assert spec.value_decimals == 2 and spec.row_limit == 7 and spec.preparer == "u"
    assert [s.path for s in spec.source_files] == ["a", "b"]
    assert spec.output_path == "" and spec.if_exists == "version"


def test_workflow_snapshot_lists_ancestors_and_comments(qtbot, tmp_path):
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    scene = window.scene
    csv = tmp_path / "in.csv"
    csv.write_text("a,b\n1,2\n")
    fin = get_class_from_opcode(IONodes.FILE_INPUT, NodeTypes.IO)(scene)
    fin.content.filePath = str(csv)
    fin.content.file_type = "csv"
    wp = get_class_from_opcode(IONodes.WORKPAPER_OUTPUT, NodeTypes.IO)(scene)
    Edge(scene, fin.outputs[0], wp.inputs[0])
    note = get_class_from_opcode(ReportNodes.COMMENT, NodeTypes.REPORT)(scene)
    note.content.settings["text"] = "Reviewed with the client"
    steps = collect_workflow(wp)
    assert [s["title"] for s in steps] == ["File Input", "Comment"]
    assert steps[0]["step"] == 1 and steps[0]["op"] == "input.file_input"
    assert any("in.csv" in value for _label, value in steps[0]["settings"])
    assert (
        steps[1]["kind"] == "comment"
        and steps[1]["comment"] == "Reviewed with the client"
    )
    assert [s["path"] for s in collect_sources(wp)] == [str(csv)]


def test_before_run_snapshots_on_the_gui_thread(qtbot, clean_preferences):
    _w, node = _new(qtbot)
    clean_preferences.set("engagement/client_name", "Snap")
    assert node.content._workflow is None
    node.content.before_run()
    assert node.content._engagement["client_name"] == "Snap"
    assert [s["title"] for s in node.content._workflow] == ["Source"]
    assert node.content._sources == []
    clean_preferences.set("engagement/client_name", "Later")
    assert node.content.effective_spec().client == "Snap"  # the run uses the snapshot


def test_audit_output_files_predicts_the_versioned_name(qtbot, tmp_path):
    _w, node = _new(qtbot)
    assert node.content.audit_output_files() == []
    target = tmp_path / "wp.xlsx"
    node.content.settings["output_path"] = str(target)
    (only,) = node.content.audit_output_files()
    assert only["path"] == target.as_posix() and only["format"] == "xlsx"
    target.write_bytes(b"x")
    assert node.content.audit_output_files()[0]["path"].endswith("wp (2).xlsx")
    node.content.settings["if_exists"] = "replace"
    assert node.content.audit_output_files()[0]["path"] == target.as_posix()


def test_predict_output_path_has_no_side_effects(tmp_path):
    from trigger_designer.core.workpaper.paths import predict_output_path, unique_path

    target = tmp_path / "a.xlsx"
    assert predict_output_path(str(target), "version") == str(target)
    target.write_bytes(b"x")
    (tmp_path / "a (2).xlsx").write_bytes(b"x")
    assert unique_path(str(target)).endswith("a (3).xlsx")
    assert predict_output_path("", "version") == ""
    assert sorted(p.name for p in tmp_path.iterdir()) == ["a (2).xlsx", "a.xlsx"]


_INTERNAL_LABELS = {
    "Filepathrel",
    "Input schema version",
    "Schema snapshot",
    "File metadata",
}


def _file_input_rows(qtbot, **attrs):
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    fin = get_class_from_opcode(IONodes.FILE_INPUT, NodeTypes.IO)(window.scene)
    for key, value in attrs.items():
        setattr(fin.content, key, value)
    wp = get_class_from_opcode(IONodes.WORKPAPER_OUTPUT, NodeTypes.IO)(window.scene)
    Edge(window.scene, fin.outputs[0], wp.inputs[0])
    rows = dict(collect_workflow(wp)[0]["settings"])
    assert not _INTERNAL_LABELS & set(rows)
    return rows


def test_workflow_file_input_csv_is_curated(qtbot, tmp_path):
    csv = tmp_path / "in.csv"
    csv.write_text("a;b\n1;2\n")
    rows = _file_input_rows(
        qtbot,
        filePath=str(csv),
        file_type="csv",
        delimiter=";",
        record_limit=50,
        encoding="utf8-lossy",
        schema_snapshot=[{"name": "a", "dtype": "Int64"}],
        file_metadata={"size": 9},
    )
    assert rows["Source"] == csv.as_posix() and rows["Source type"] == "csv"
    assert rows["Delimiter"] == ";" and rows["Row limit"] == "50"
    assert rows["Encoding"] == "utf8-lossy"
    assert rows["First row is the header"] == "yes"


def test_workflow_file_input_excel_sheets(qtbot, tmp_path):
    path = tmp_path / "book.xlsx"
    path.write_bytes(b"x")
    rows = _file_input_rows(
        qtbot, filePath=str(path), file_type="excel", selected_sheet="Ledger"
    )
    assert rows["Sheet"] == "Ledger" and rows["Row limit"] == "all rows"
    rows = _file_input_rows(
        qtbot,
        filePath=str(path),
        file_type="excel",
        sheet_mode="chosen",
        selected_sheets=["A", "B"],
        start_row=3,
    )
    assert rows["Sheets"] == "A, B" and rows["Start row"] == "3"


def test_workflow_file_input_folder_options_and_json_db(qtbot, tmp_path):
    rows = _file_input_rows(
        qtbot,
        filePath=str(tmp_path),
        file_type="csv",
        include_patterns=["*.csv"],
        recursive=True,
        on_file_error="skip",
    )
    assert rows["Reads"] == "all files in a folder"
    assert rows["Include"] == "*.csv" and rows["Sub-folders"] == "yes"
    assert rows["Bad file"] == "skip and report"
    js = tmp_path / "d.json"
    js.write_text("[]")
    rows = _file_input_rows(
        qtbot, filePath=str(js), file_type="json", json_nested="keep"
    )
    assert rows["Nested values"] == "kept as is"
    db = tmp_path / "d.sqlite"
    db.write_bytes(b"x")
    rows = _file_input_rows(
        qtbot, filePath=str(db), file_type="sqlite", db_mode="table", db_table="gl"
    )
    assert rows["Table"] == "gl"


def test_workflow_file_input_without_a_path(qtbot):
    assert _file_input_rows(qtbot) == {"Source": "not set"}
