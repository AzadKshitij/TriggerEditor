"""Multi-Field Formula core: behaviour, edge cases, error codes, SQL attacks."""

from __future__ import annotations

import os
import subprocess
import sys

import polars as pl
import pytest
from nodeeditor.node_edge import Edge

from trigger_designer.core.errors.catalogue import CATALOGUE
from trigger_designer.core.node_configuration import (
    NodeTypes,
    PreparationNodes,
    get_class_from_opcode,
)
from trigger_designer.core.shaping import multi_formula as mf
from trigger_designer.core.shaping.common import ERROR_CODES, ShapingError
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.node_base import TriggerNode


def make_frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "a": [" x", "y ", None],
            "b": ["1", "2.5", "z"],
            "n": [1, 2, 3],
        }
    )


def run(settings: dict, frame: pl.DataFrame | None = None) -> pl.DataFrame:
    frame = make_frame() if frame is None else frame
    (out,) = mf.run_node([frame.lazy()], settings)
    return out.collect()


def code_of(settings: dict, frame: pl.DataFrame | None = None) -> str:
    with pytest.raises(ShapingError) as info:
        run(settings, frame)
    return info.value.code


# ---- behaviour (hand-computed) ------------------------------------------


def test_in_place_keeps_column_order_and_other_columns() -> None:
    out = run({"columns": ["a"], "template": "UPPER(TRIM({col}))"})
    assert out.columns == ["a", "b", "n"]
    assert out["a"].to_list() == ["X", "Y", None]
    assert out["b"].to_list() == ["1", "2.5", "z"]
    assert out["n"].to_list() == [1, 2, 3]


def test_suffix_mode_appends_new_columns() -> None:
    out = run(
        {
            "columns": ["b", "n"],
            "template": "TRY_CAST({col} AS DOUBLE) * 2",
            "mode": "suffix",
            "suffix": "_x2",
        }
    )
    assert out.columns == ["a", "b", "n", "b_x2", "n_x2"]
    assert out["b_x2"].to_list() == [2.0, 5.0, None]
    assert out["n_x2"].to_list() == [2.0, 4.0, 6.0]
    assert out["b"].to_list() == ["1", "2.5", "z"]


def test_name_placeholder_is_the_column_name_as_text() -> None:
    out = run({"columns": ["b"], "template": "{name} || ':' || {col}"})
    assert out["b"].to_list() == ["b:1", "b:2.5", "b:z"]


def test_each_output_column_keeps_its_own_type() -> None:
    out = run(
        {
            "columns": ["b", "n"],
            "template": "LENGTH(CAST({col} AS VARCHAR))",
            "mode": "suffix",
        }
    )
    assert out["b_new"].to_list() == [1, 3, 1]
    assert out["n_new"].to_list() == [1, 1, 1]
    assert out["b_new"].dtype == out["n_new"].dtype


def test_numeric_template_changes_the_dtype_in_place() -> None:
    out = run({"columns": ["n"], "template": "CAST({col} AS DOUBLE) * 1.5"})
    assert out["n"].to_list() == [1.5, 3.0, 4.5]
    assert out["n"].dtype.is_float()


def test_substitution_is_parenthesised_for_precedence() -> None:
    out = run({"columns": ["n"], "template": "{col} + 1 OR 1 = 0"})
    # (n + 1 OR 1 = 0) is evaluated as one expression, never leaking outside.
    assert out.columns == ["a", "b", "n"]
    assert mf.expression_for("{col} + 1", "n").startswith("(")


def test_null_cells_never_raise() -> None:
    out = run({"columns": ["a"], "template": "LENGTH({col})"})
    assert out["a"].to_list() == [2, 2, None]


def test_duplicate_selected_columns_are_applied_once() -> None:
    out = run({"columns": ["n", "n"], "template": "{col} + 1"})
    assert out["n"].to_list() == [2, 3, 4]


def test_column_name_with_quotes_is_escaped() -> None:
    frame = pl.DataFrame({'we"ird': ["a", "b"], "it's": ["c", "d"]})
    out = run({"columns": ['we"ird', "it's"], "template": "UPPER({col})"}, frame=frame)
    assert out['we"ird'].to_list() == ["A", "B"]
    assert out["it's"].to_list() == ["C", "D"]
    out = run(
        {
            "columns": ["it's"],
            "template": "{name} || SUBSTR({col}, 1, 0)",
            "mode": "suffix",
            "suffix": "_n",
        },
        frame=frame,
    )
    assert out["it's_n"].to_list() == ["it's", "it's"]


def test_placeholder_text_in_a_column_name_is_not_substituted_twice() -> None:
    frame = pl.DataFrame({"{name}": ["a"]})
    out = run({"columns": ["{name}"], "template": "{name} || {col}"}, frame=frame)
    assert out["{name}"].to_list() == ["{name}a"]


def test_name_placeholder_inside_a_string_literal_is_plain_text_replacement() -> None:
    # {name} already expands to a quoted literal, so inside quotes it breaks them:
    # the plan documents plain text replacement, and the engine reports it (113).
    assert (
        code_of({"columns": ["n"], "template": "'{name}=' || {col}"}) == "TD-SHAPE-113"
    )


def test_semicolon_inside_a_string_literal_is_allowed() -> None:
    out = run({"columns": ["n"], "template": "{col} || ';'"})
    assert out["n"].to_list() == ["1;", "2;", "3;"]


def test_trailing_line_comment_cannot_swallow_the_wrapper() -> None:
    out = run({"columns": ["n"], "template": "{col} + 1 -- note"})
    assert out["n"].to_list() == [2, 3, 4]


def test_multiline_template_works() -> None:
    out = run(
        {"columns": ["n"], "template": "CASE\n WHEN {col} > 1 THEN 1\n ELSE 0 END"}
    )
    assert out["n"].to_list() == [0, 1, 1]


def test_zero_rows_keeps_typed_empty_output() -> None:
    frame = make_frame().clear()
    out = run({"columns": ["n"], "template": "CAST({col} AS DOUBLE)"}, frame=frame)
    assert out.height == 0
    assert out.columns == ["a", "b", "n"]
    assert out.schema["n"].is_float()


def test_unicode_column_and_values() -> None:
    frame = pl.DataFrame({"naïve ñ": ["é", "ñ"]})
    out = run({"columns": ["naïve ñ"], "template": "UPPER({col})"}, frame=frame)
    assert out["naïve ñ"].to_list() == ["É", "Ñ"]


def test_row_order_is_kept() -> None:
    frame = pl.DataFrame({"v": list(range(500, 0, -1))})
    out = run({"columns": ["v"], "template": "{col} * 2"}, frame=frame)
    assert out["v"].to_list() == [v * 2 for v in range(500, 0, -1)]


def test_exactly_200_columns_is_accepted() -> None:
    names = [f"c{i}" for i in range(200)]
    frame = pl.DataFrame({name: [1] for name in names})
    out = run({"columns": names, "template": "{col} + 1"}, frame=frame)
    assert out.row(0) == (2,) * 200


# ---- error codes ----------------------------------------------------------


def test_no_columns_is_001() -> None:
    assert code_of({"columns": [], "template": "{col}"}) == "TD-SHAPE-001"
    assert code_of({"template": "{col}"}) == "TD-SHAPE-001"


def test_more_than_200_columns_is_004() -> None:
    names = [f"c{i}" for i in range(201)]
    frame = pl.DataFrame({name: [1] for name in names})
    assert code_of({"columns": names, "template": "{col}"}, frame) == "TD-SHAPE-004"


def test_unknown_mode_is_004() -> None:
    assert (
        code_of({"columns": ["a"], "template": "{col}", "mode": "sideways"})
        == "TD-SHAPE-004"
    )


@pytest.mark.parametrize("template", ["", "UPPER(x)", "{name}", "{COL}", "{ col }"])
def test_template_without_col_is_120(template: str) -> None:
    assert code_of({"columns": ["a"], "template": template}) == "TD-SHAPE-120"


def test_semicolon_is_110() -> None:
    assert (
        code_of({"columns": ["a"], "template": "{col}); drop table t1; --"})
        == "TD-SHAPE-110"
    )
    assert code_of({"columns": ["a"], "template": "{col}; SELECT 1"}) == "TD-SHAPE-110"


def test_breaking_out_of_the_wrapper_is_110() -> None:
    for template in ("{col}), 5 AS z, (1", "{col}) + (2", ") + {col}"):
        assert code_of({"columns": ["a"], "template": template}) == "TD-SHAPE-110"


def test_blank_suffix_in_suffix_mode_is_001() -> None:
    settings = {"columns": ["a"], "template": "{col}", "mode": "suffix"}
    assert code_of({**settings, "suffix": ""}) == "TD-SHAPE-001"
    assert code_of({**settings, "suffix": "   "}) == "TD-SHAPE-001"
    # in-place mode ignores the suffix entirely
    assert run({"columns": ["a"], "template": "{col}", "suffix": ""}).width == 3


def test_existing_target_name_is_002() -> None:
    frame = pl.DataFrame({"a": [1], "a_new": [2]})
    settings = {"columns": ["a"], "template": "{col}", "mode": "suffix"}
    assert code_of(settings, frame) == "TD-SHAPE-002"


def test_unknown_column_is_003() -> None:
    assert code_of({"columns": ["zzz"], "template": "{col}"}) == "TD-SHAPE-003"


def test_unknown_function_is_113_with_first_engine_line() -> None:
    with pytest.raises(ShapingError) as info:
        run({"columns": ["a"], "template": "nofunc({col})"})
    assert info.value.code == "TD-SHAPE-113"
    assert "\n" not in info.value.detail


def test_syntax_error_is_113() -> None:
    assert code_of({"columns": ["a"], "template": "{col} +* 2"}) == "TD-SHAPE-113"


def test_query_longer_than_the_guard_limit_is_114() -> None:
    template = "{col}" + " + 0" * 6000
    assert code_of({"columns": ["n"], "template": template}) == "TD-SHAPE-114"


def test_new_code_is_registered_in_both_catalogues() -> None:
    assert "TD-SHAPE-120" in ERROR_CODES
    assert "TD-SHAPE-120" in CATALOGUE
    for code in ("TD-SHAPE-110", "TD-SHAPE-112", "TD-SHAPE-113"):
        assert code in ERROR_CODES and code in CATALOGUE


# ---- read-only guard: attack payloads --------------------------------------

ATTACKS_112 = [
    "{col}) FROM read_csv('x.csv') --",
    "(SELECT count(*) FROM read_csv('secret.csv')) + {col}",
    "(SELECT string_agg(content, '') FROM read_text('secret.txt')) || {col}",
    "(SELECT 1 FROM read_parquet('x.parquet')) + {col}",
    "(SELECT 1 FROM glob('*')) + {col}",
    "(SELECT 1 FROM 'secret.csv') + {col}",
    '(SELECT 1 FROM "dir/secret.csv") + {col}',
    "(SELECT 1 FROM duckdb_settings()) + {col}",
    "(SELECT 1 FROM pragma_database_list()) + {col}",
    "current_setting('threads') || {col}",
    "getenv('PATH') || {col}",
    "{col} + random()",
    "{col} || CAST(uuid() AS VARCHAR)",
    "{col} || gen_random_uuid()::VARCHAR",
    "{col} + setseed(0.5)",
    "(SELECT 1 FROM query_table('t1')) + {col}",
    "query('SELECT 1') || {col}",
    "READ_CSV('x') || {col}",
    "\"read_csv\"('x') || {col}",
    "{col} || $$x$$",
    "{col} || $tag$x$tag$",
    "{col} || E'\\x41'",
    "ｒｅａｄ_csv('x') || {col}",  # fullwidth "read_csv"
    "{col} \x00",
]


@pytest.mark.parametrize("template", ATTACKS_112)
def test_guard_rejects_file_and_random_payloads(
    template: str, tmp_path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert code_of({"columns": ["a"], "template": template}) == "TD-SHAPE-112"
    assert list(tmp_path.iterdir()) == []


ATTACKS_NON_SELECT = [
    "{col}); ATTACH 'evil.db' AS evil; --",
    "{col}); COPY t1 TO 'out.csv'; --",
    "{col}); CREATE TABLE x AS SELECT 1; --",
    "{col}); INSTALL httpfs; LOAD httpfs; --",
    "{col}); SET enable_external_access=true; --",
    "{col}); PRAGMA database_list; --",
    "{col}); INSERT INTO t1 VALUES (1); --",
    "{col}); DROP TABLE t1; --",
    "{col}); UPDATE t1 SET a = 1; --",
    "{col}); EXPORT DATABASE 'dump'; --",
    "{col})\n;\nSELECT 1; --",
]


@pytest.mark.parametrize("template", ATTACKS_NON_SELECT)
def test_guard_rejects_extra_statements(template: str, tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert code_of({"columns": ["a"], "template": template}) == "TD-SHAPE-110"
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "template",
    [
        "{col}) FROM t1; ATTACH 'x.db' --",
        "{col}) UNION ALL SELECT 1 --",
    ],
)
def test_breakout_attempts_never_run(template: str, tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert code_of({"columns": ["a"], "template": template}) in {
        "TD-SHAPE-110",
        "TD-SHAPE-113",
    }
    assert list(tmp_path.iterdir()) == []


def test_attack_in_a_comment_or_string_is_harmless_text() -> None:
    out = run(
        {
            "columns": ["n"],
            "template": "{col} /* read_csv('x'); ATTACH 'y' */ + 1",
        }
    )
    assert out["n"].to_list() == [2, 3, 4]
    out = run({"columns": ["n"], "template": "'read_csv(' || {col}"})
    assert out["n"].to_list() == ["read_csv(1", "read_csv(2", "read_csv(3"]


def test_hostile_column_name_cannot_inject_sql() -> None:
    evil = 'a"); DROP TABLE t1; --'
    frame = pl.DataFrame({evil: ["x"], "k": ["y"]})
    out = run({"columns": [evil], "template": "UPPER({col})"}, frame=frame)
    assert out[evil].to_list() == ["X"]
    out = run(
        {
            "columns": [evil],
            "template": "{name} || SUBSTR({col}, 1, 0)",
            "mode": "suffix",
            "suffix": "_n",
        },
        frame=frame,
    )
    assert out[evil + "_n"].to_list() == [evil]


def test_input_frame_is_not_mutated() -> None:
    frame = make_frame()
    before = frame.clone()
    run({"columns": ["a"], "template": "UPPER({col})"}, frame)
    assert frame.equals(before)


# ---- architecture --------------------------------------------------------


def test_core_module_has_no_qt_import() -> None:
    code = (
        "import sys\n"
        "import trigger_designer.core.shaping.multi_formula\n"
        "bad = [m for m in sys.modules "
        "if m.split('.')[0] in ('PySide6','PyQt5','PyQt6','PySide2','qtpy')]\n"
        "assert not bad, bad\n"
    )
    env = {**os.environ, "PYTHONUTF8": "1"}
    result = subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, result.stderr


def test_describe_chip_text() -> None:
    chips = mf.describe([], {"columns": ["a", "b"], "template": "{col}"})
    assert chips == [("2 columns replaced", "accent")]
    chips = mf.describe([], {"columns": ["a"], "template": "{col}", "mode": "suffix"})
    assert chips == [("1 column added", "accent")]
    assert mf.describe([], {"columns": []}) == []


# ---- node: live evaluation equals generated code ---------------------------


class Source(TriggerNode):
    node_title = "Source"

    def __init__(self, scene, frame) -> None:
        self._frame = frame
        super().__init__(scene, inputs=[], outputs=[3])
        self.value = [{"data": frame, "variable_name": "var_src"}]
        self.markDirty(False)
        self.markInvalid(False)

    def evalImplementation(self):
        self.value = [{"data": self._frame, "variable_name": "var_src"}]
        self.markDirty(False)
        self.markInvalid(False)
        return self.value


def _node_class():
    return get_class_from_opcode(
        PreparationNodes.MULTI_FIELD_FORMULA, NodeTypes.PREPARATION
    )


@pytest.mark.parametrize(
    "settings",
    [
        {"columns": ["a"], "template": "UPPER(TRIM({col}))"},
        {
            "columns": ["b", "n"],
            "template": "TRY_CAST({col} AS DOUBLE) * 2",
            "mode": "suffix",
            "suffix": "_x2",
        },
        # text that would break out of a naive code generator
        {"columns": ["b"], "template": "{name} || '\"\n' || {col}"},
        {"columns": ["b"], "template": "{col} || '''''' || '\"\"\"'"},
    ],
)
def test_live_equals_generated_code(settings: dict) -> None:
    window = TriggerSubWindow()
    frame = make_frame().lazy()
    source = Source(window.scene, frame)
    node = _node_class()(window.scene)
    Edge(window.scene, source.outputs[0], node.inputs[0])
    node.content.settings.update(settings)
    node.markDirty(True)
    out = node.eval()
    assert out is not None and not node.isInvalid()
    live = out[0]["data"].collect()
    namespace = {"var_src": frame}
    exec(node.get_code(), {"__name__": "__main__", "pl": pl}, namespace)  # noqa: S102
    generated = namespace[node.content.variable_name].collect()
    assert generated.equals(live)
    assert generated.equals(run(settings))


def test_unwired_node_defines_every_output_variable() -> None:
    window = TriggerSubWindow()
    node = _node_class()(window.scene)
    namespace: dict = {}
    exec(node.get_code(), {"__name__": "__main__", "pl": pl}, namespace)  # noqa: S102
    for variable in node.content.output_variables:
        assert variable in namespace


def test_registry_identity() -> None:
    cls = _node_class()
    assert cls.node_title == "Multi-Field Formula"
    assert cls.node_code == PreparationNodes.MULTI_FIELD_FORMULA
    assert cls.icon == "node_multi_field_formula"


def test_live_error_matches_run_error() -> None:
    window = TriggerSubWindow()
    frame = make_frame().lazy()
    source = Source(window.scene, frame)
    node = _node_class()(window.scene)
    Edge(window.scene, source.outputs[0], node.inputs[0])
    node.content.settings.update(
        {"columns": ["a"], "template": "{col}) FROM read_csv('x') --"}
    )
    node.markDirty(True)
    node.eval()
    assert node.isInvalid()
    with pytest.raises(ShapingError) as info:
        mf.run_node([frame], node.content.settings)
    assert info.value.code == "TD-SHAPE-112"
