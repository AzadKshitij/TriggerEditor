"""SQL Query dock: editor behaviour, undo, save/reload and generated code."""

from __future__ import annotations

import polars as pl
import pytest
from nodeeditor.node_edge import Edge
from qtpy.QtWidgets import QVBoxLayout, QWidget

from trigger_designer.core.node_configuration import (
    NodeTypes,
    TransformNodes,
    get_class_from_opcode,
)
from trigger_designer.core.shaping.common import ShapingError
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.docks.node_config import ConfigDock
from trigger_designer.qt.node_base import TriggerNode
from trigger_designer.qt.widgets.sql_formula_editor import (
    SQLFormulaEditor,
    match_completions,
)

T1 = pl.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
T2 = pl.DataFrame({"a": [2, 3, 4], "c": [20.0, 30.0, 40.0]})
JOIN = "SELECT t1.a, t1.b, t2.c FROM t1 JOIN t2 USING (a) ORDER BY t1.a"


class Source(TriggerNode):
    node_title = "Source"

    def __init__(self, scene, frame, name: str = "var_src") -> None:
        self._frame, self._name = frame, name
        super().__init__(scene, inputs=[], outputs=[3])
        self.value = [{"data": frame, "variable_name": name}]
        self.markDirty(False)
        self.markInvalid(False)

    def evalImplementation(self):
        self.value = [{"data": self._frame, "variable_name": self._name}]
        self.markDirty(False)
        self.markInvalid(False)
        return self.value


def _make(qtbot, frames=(T1,), sql=None):
    window = TriggerSubWindow()
    qtbot.addWidget(window)
    cls = get_class_from_opcode(TransformNodes.SQL_QUERY, NodeTypes.TRANSFORM)
    node = cls(window.scene)
    if sql is not None:
        node.content.settings["sql"] = sql
    for index, frame in enumerate(frames):
        source = Source(window.scene, frame.lazy(), f"var_src{index + 1}")
        Edge(window.scene, source.outputs[0], node.inputs[index])
    node.markDirty(True)
    node.eval()
    return window, node


def _open(qtbot, frames=(T1,), sql=None):
    window, node = _make(qtbot, frames, sql)
    dock = ConfigDock()
    qtbot.addWidget(dock)
    dock.updateConfig([node.grNode])
    window.scene.history.storeHistory("Baseline")  # the first stamp is not a step
    return window, node, dock


def _result(node) -> pl.DataFrame:
    node.markDirty(True)
    out = node.eval()
    assert out is not None and not node.isInvalid(), node.current_error
    return out[0]["data"].collect()


def _run_generated(node, namespace: dict) -> pl.DataFrame:
    exec(node.get_code(), {"__name__": "__main__", "pl": pl}, namespace)  # noqa: S102
    return namespace[node.content.variable_name].collect()


# ---- identity and sockets -----------------------------------------------------


def test_registered_with_three_inputs_one_output_and_an_op_id(qtbot) -> None:
    cls = get_class_from_opcode(TransformNodes.SQL_QUERY, NodeTypes.TRANSFORM)
    assert cls.node_title == "SQL Query" and cls.icon == "node_sql_query"
    _window, node = _make(qtbot)
    assert node.serialize()["op"] == "transform.sql_query"
    assert len(node.inputs) == 3 and len(node.outputs) == 1
    assert node.optional_inputs == frozenset({1, 2})


def test_icon_resolves_to_a_real_file() -> None:
    from trigger_designer.qt.resource_manager import ResourceManager

    ResourceManager()
    path = ResourceManager.get_full_path("node_sql_query")
    assert path is not None and path.is_file()
    assert path.read_text(encoding="utf-8").startswith("<svg")


# ---- optional inputs -----------------------------------------------------------


def test_only_t1_wired_is_valid(qtbot) -> None:
    _window, node = _make(qtbot)
    assert not node.isInvalid()
    assert _result(node).equals(T1)


def test_t2_and_t3_are_optional_but_t1_is_not(qtbot) -> None:
    _window, node = _make(qtbot, frames=())
    assert node.eval() is None and node.isInvalid()

    window2 = TriggerSubWindow()
    qtbot.addWidget(window2)
    node2 = type(node)(window2.scene)
    source = Source(window2.scene, T2.lazy())
    Edge(window2.scene, source.outputs[0], node2.inputs[1])  # t2 only
    node2.markDirty(True)
    assert node2.eval() is None and node2.isInvalid()


def test_two_wired_inputs_join(qtbot) -> None:
    _window, node = _make(qtbot, frames=(T1, T2), sql=JOIN)
    assert _result(node).rows() == [(2, "y", 20.0), (3, "z", 30.0)]


def test_referencing_unconnected_t2_shows_an_error_not_a_crash(qtbot) -> None:
    _window, node = _make(qtbot, sql="SELECT * FROM t2")
    assert node.isInvalid()
    assert node.current_error.code == "TD-SHAPE-113"


# ---- dock ------------------------------------------------------------------------


def test_dock_holds_one_sql_editor_with_plain_column_completion(qtbot) -> None:
    _window, node, dock = _open(qtbot, frames=(T1, T2))
    content = node.content
    editor = content._sql_widget
    assert editor is not None and editor.get_text() == "SELECT *\nFROM t1"
    assert dock.dock_widget.findChildren(SQLFormulaEditor) == [editor.editor]
    assert editor.editor.bracket_columns is False
    names = editor.editor.column_names
    assert names[:3] == ["t1", "t2", "t3"]
    assert {"a", "b", "c"} <= set(names)
    assert content.sql_editors() == [editor]
    assert content._sql_error.isHidden()
    assert content._sql_error.objectName() == "formulaSectionError"


def test_unwired_dock_shows_the_empty_state(qtbot) -> None:
    _window, node = _make(qtbot, frames=())
    holder = QWidget()
    layout = QVBoxLayout(holder)
    node.content.create_layout(layout)
    assert layout.itemAt(0).widget().objectName() == "EmptyStateLabel"
    assert node.content._sql_widget is None


def test_completion_labels_follow_bracket_mode() -> None:
    assert match_completions("na", False, ["name"], bracket=False) == ["name"]
    assert match_completions("na", False, ["name"]) == ["[name]"]
    assert match_completions("na", False, ["name"], bracket=True) == ["[name]"]
    assert match_completions("my", False, ["my col"], bracket=False) == ['"my col"']
    assert match_completions("ev", False, ['ev"il'], bracket=False) == ['"ev""il"']


def test_editor_with_plain_columns_does_not_flag_list_indexing(qtbot) -> None:
    editor = SQLFormulaEditor()
    qtbot.addWidget(editor)
    editor.bracket_columns = False
    editor.set_column_names(["a"])
    editor.setPlainText("select a[1] from t1")
    editor.check_for_errors()
    assert not any("Unknown column" in e["message"] for e in editor.errors)

    default = SQLFormulaEditor()
    qtbot.addWidget(default)
    default.set_column_names(["a"])
    default.setPlainText("[a] + [zzz]")
    default.check_for_errors()
    assert any("Unknown column" in e["message"] for e in default.errors)


def test_error_label_shows_a_bad_column_and_hides_for_valid_sql(qtbot) -> None:
    _window, node, _dock = _open(qtbot)
    content = node.content
    editor = content._sql_widget
    editor.set_text("select zzz from t1")
    qtbot.waitUntil(lambda: not content._sql_error.isHidden(), timeout=3000)
    assert "zzz" in content._sql_error.text()
    editor.set_text("select a from t1")
    qtbot.waitUntil(lambda: content._sql_error.isHidden(), timeout=3000)


def test_error_label_flags_a_forbidden_function_without_reading_files(
    qtbot, tmp_path
) -> None:
    secret = tmp_path / "secret.csv"
    secret.write_text("password\nhunter2\n")
    _window, node, _dock = _open(qtbot)
    content = node.content
    content._sql_widget.set_text(f"select * from read_csv('{secret.as_posix()}')")
    qtbot.waitUntil(lambda: not content._sql_error.isHidden(), timeout=3000)
    assert "not allowed" in content._sql_error.text()
    assert "hunter2" not in content._sql_error.text()
    assert [p.name for p in tmp_path.iterdir()] == ["secret.csv"]


# ---- undo / redo -------------------------------------------------------------------


def test_typing_is_one_undo_step_and_restores_the_editor(qtbot) -> None:
    window, node, _dock = _open(qtbot)
    content = node.content
    history = window.scene.history
    editor = content._sql_widget

    for text in ("SELECT a", "SELECT a FROM", "SELECT a FROM t1"):
        editor.set_text(text)
        qtbot.wait(120)  # inside one 300 ms burst
    qtbot.wait(450)
    assert content.settings["sql"] == "SELECT a FROM t1"
    assert history.canUndo()

    history.undo()
    assert content.settings["sql"] == "SELECT *\nFROM t1"
    assert content._sql_widget is editor  # not rebuilt
    assert editor.get_text() == "SELECT *\nFROM t1"
    assert not history.canUndo()

    history.redo()
    assert content.settings["sql"] == "SELECT a FROM t1"
    assert editor.get_text() == "SELECT a FROM t1"


def test_undo_does_not_record_itself(qtbot) -> None:
    window, node, _dock = _open(qtbot)
    history = window.scene.history
    node.content._sql_widget.set_text("SELECT b FROM t1")
    qtbot.wait(450)
    history.undo()
    qtbot.wait(450)  # a stray debounce must not push a new step
    assert not history.canUndo()
    assert history.canRedo()


def test_edit_applies_when_the_dock_is_left(qtbot) -> None:
    _window, node, _dock = _open(qtbot)
    content = node.content
    content._sql_widget.set_text("SELECT b FROM t1")
    qtbot.wait(450)
    assert content._pending_evaluate  # deferred: runs when the dock is left
    content.commit_pending_dock_edits()
    assert not content._pending_evaluate
    assert node.value[0]["data"].collect().columns == ["b"]


def test_dock_leave_commits_text_typed_inside_the_debounce(qtbot) -> None:
    _window, node, _dock = _open(qtbot)
    content = node.content
    content._sql_widget.set_text("SELECT a FROM t1")
    content.commit_pending_dock_edits()  # before 300 ms elapsed
    assert content.settings["sql"] == "SELECT a FROM t1"
    assert node.value[0]["data"].collect().columns == ["a"]


# ---- save / reload -----------------------------------------------------------------


def test_save_and_reload_round_trip(qtbot, tmp_path, no_modal_dialogs) -> None:
    import orjson

    window, _node = _make(qtbot, frames=(T1, T2), sql=JOIN)
    path = tmp_path / "sql_query.tds"
    window.scene.saveToFile(str(path))

    data = orjson.loads(path.read_bytes())
    saved = [n for n in data["nodes"] if n.get("op") == "transform.sql_query"]
    assert len(saved) == 1
    assert saved[0]["content"]["settings"]["sql"] == JOIN

    reloaded = TriggerSubWindow()
    qtbot.addWidget(reloaded)
    assert reloaded.fileLoad(str(path)) is True
    (loaded,) = [n for n in reloaded.getAllNodes() if n.title == "SQL Query"]
    assert loaded.node_code == TransformNodes.SQL_QUERY
    assert loaded.content.settings["sql"] == JOIN
    assert len(loaded.inputs) == 3


def test_legacy_file_without_settings_gets_the_default_query(qtbot) -> None:
    _window, node = _make(qtbot)
    node.content.settings = {}
    node.content.deserialize({"settings": {}})
    assert node.content.settings["sql"] == "SELECT *\nFROM t1"


# ---- generated code ------------------------------------------------------------------


def test_generated_code_agrees_with_the_live_result(qtbot) -> None:
    _window, node = _make(qtbot, frames=(T1, T2), sql=JOIN)
    live = _result(node)
    generated = _run_generated(node, {"var_src1": T1.lazy(), "var_src2": T2.lazy()})
    assert generated.equals(live)
    code = node.get_code()
    assert "_run_node([var_src1, var_src2, None]" in code
    assert code.count("import") == 3  # json, polars, the one named import


def test_generated_code_with_only_t1(qtbot) -> None:
    _window, node = _make(qtbot)
    code = node.get_code()
    assert "_run_node([var_src1, None, None]" in code
    assert _run_generated(node, {"var_src1": T1.lazy()}).equals(T1)


def test_unwired_node_still_defines_its_output(qtbot) -> None:
    _window, node = _make(qtbot, frames=())
    namespace: dict = {}
    exec(node.get_code(), {"__name__": "__main__", "pl": pl}, namespace)  # noqa: S102
    assert node.content.variable_name in namespace
    assert node.get_code().strip().splitlines()[0] == "import polars as pl"


def test_t2_only_wired_defines_its_output_without_running_the_query(qtbot) -> None:
    window, node = _make(qtbot, frames=())
    source = Source(window.scene, T2.lazy(), "var_src2")
    Edge(window.scene, source.outputs[0], node.inputs[1])
    node.markDirty(True)
    node.eval()
    namespace: dict = {}
    exec(node.get_code(), {"__name__": "__main__", "pl": pl}, namespace)  # noqa: S102
    assert node.content.variable_name in namespace


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT '''; import os; os.system(\"x\") #' AS s FROM t1",
        'SELECT """ AS s',
        "SELECT '\\' AS s",
        "SELECT 'café ☃' AS s",
        'SELECT 1 AS "a\'b"',
        "SELECT 'line1\nline2' AS s",
    ],
)
def test_generated_code_never_interpolates_sql_text(qtbot, sql) -> None:
    _window, node = _make(qtbot, sql="SELECT 1")
    node.content.settings["sql"] = sql
    code = node.get_code()
    compile(code, "<generated>", "exec")  # always valid Python
    tree_text = code.splitlines()
    assert len(tree_text) <= 5  # the query never spills into code lines
    import ast

    names = {n.id for n in ast.walk(ast.parse(code)) if isinstance(n, ast.Name)}
    assert "os" not in names and "system" not in names
    # the same text survives the round trip into the engine settings
    call = next(
        n
        for n in ast.walk(ast.parse(code))
        if isinstance(n, ast.Call) and getattr(n.func, "attr", "") == "loads"
    )
    import json

    assert json.loads(ast.literal_eval(call.args[0]))["sql"] == sql


# ---- attacks through generated code and the live path ---------------------------------


ATTACKS = [
    "SELECT * FROM read_csv('{secret}')",
    "SELECT * FROM '{secret}'",
    "SELECT * FROM read_text('{secret}')",
    "SELECT * FROM glob('{dir}/*')",
    "COPY (SELECT * FROM t1) TO '{dir}/out.csv'",
    "COPY t1 TO '{dir}/out.csv'",
    "ATTACH '{dir}/new.db'",
    "INSTALL httpfs",
    "LOAD httpfs",
    "PRAGMA database_list",
    "SET enable_external_access = true",
    "SELECT 1; COPY t1 TO '{dir}/out.csv'",
    "SELECT 1 -- x\n; ATTACH '{dir}/new.db'",
    "SELECT 1 /* ; */ ; ATTACH '{dir}/new.db'",
    "SELECT * FROM ｒｅａｄ_csv('{secret}')",
    "SELECT random()",
]


@pytest.mark.parametrize("sql", ATTACKS)
def test_attack_is_refused_live_and_in_generated_code(qtbot, tmp_path, sql) -> None:
    secret = tmp_path / "secret.csv"
    secret.write_text("password\nhunter2\n")
    sql = sql.format(secret=secret.as_posix(), dir=tmp_path.as_posix())
    _window, node = _make(qtbot, sql="SELECT 1")
    node.content.settings["sql"] = sql

    # live path: the node turns invalid and nothing is produced
    node.markDirty(True)
    assert node.eval() is None
    assert node.isInvalid()
    assert node.current_error.code.startswith("TD-SHAPE-11")

    # Run path: the generated code raises the same coded error
    namespace = {"var_src1": T1.lazy()}
    with pytest.raises(ShapingError) as info:
        exec(node.get_code(), {"__name__": "__main__", "pl": pl}, namespace)  # noqa: S102
    assert info.value.code.startswith("TD-SHAPE-11")
    assert node.content.variable_name not in namespace
    assert "hunter2" not in str(info.value)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["secret.csv"]
