"""Formula and Filter-expression SQL cannot read or write files (BUG-029/030)."""

from __future__ import annotations

import ast
from pathlib import Path

import polars as pl
import pytest

from trigger_designer.core.shaping import filter as filter_core
from trigger_designer.core.shaping import formula as formula_core
from trigger_designer.core.shaping.common import ShapingError


def _frame() -> pl.LazyFrame:
    return pl.DataFrame({"x": [1, 2, 3], "s": ["a", "b", "c"]}).lazy()


def _filter(expression: str):
    return filter_core.run_node(
        [_frame()], {"mode": "expression", "expression": expression}
    )


def _formula(text: str, target: str = "y"):
    return formula_core.run_node(
        [_frame()],
        {"sections": [{"target_column": target, "formula_text": text}]},
    )


@pytest.fixture
def secret(tmp_path: Path) -> Path:
    path = tmp_path / "secret.csv"
    path.write_text("token\nhunter2\n", encoding="utf-8")
    return path


# --- normal use is unchanged --------------------------------------------------


def test_normal_filter_expressions_still_work() -> None:
    matched, unmatched = _filter("[x] > 1")
    assert matched.collect()["x"].to_list() == [2, 3]
    assert unmatched.collect()["x"].to_list() == [1]
    matched, _ = _filter("[x] IN (1, 2) AND NOT [x] = 3")
    assert matched.collect()["x"].to_list() == [1, 2]
    matched, _ = _filter("[s] = 'a;b' OR [s] LIKE '%read_csv(%'")
    assert matched.collect().height == 0


def test_normal_formulas_still_work() -> None:
    out = _formula("[x] * 2").pop().collect()
    assert out["y"].to_list() == [2, 4, 6]
    out = _formula("'DROP TABLE x -- ' || [s]").pop().collect()
    assert out["y"][0] == "DROP TABLE x -- a"


def test_chained_sections_still_work() -> None:
    out = formula_core.run_node(
        [_frame()],
        {
            "sections": [
                {"target_column": "a", "formula_text": "[x] + 1"},
                {"target_column": "b", "formula_text": "[a] * 2"},
            ]
        },
    )[0].collect()
    assert out["b"].to_list() == [4, 6, 8]


# --- attacks ------------------------------------------------------------------

ATTACKS = [
    "1=1) UNION ALL SELECT 1, 'x' FROM read_csv('{path}') --",
    "[x] IN (SELECT 1 FROM read_csv_auto('{path}'))",
    "[x] > 0; COPY (SELECT 1) TO '{out}'",
    "[x] > 0) ; COPY df_filter TO '{out}' --",
    "EXISTS (SELECT * FROM '{path}')",
    'EXISTS (SELECT * FROM "{path}")',
    "[x] = (SELECT count(*) FROM glob('*'))",
    "[x] = (SELECT 1 FROM duckdb_settings() LIMIT 1)",
    "[x] = random()",
    "1=1; ATTACH '{out}.db'",
    "1=1; INSTALL httpfs",
    "1=1; SET enable_external_access=true",
    "1=1; PRAGMA database_list",
    "$$ ' $$ = $$ ' $$ ; COPY df_filter TO '{out}' -- '",
]


@pytest.mark.parametrize("template", ATTACKS)
def test_filter_expression_attacks_fail_and_write_nothing(
    template: str, secret: Path, tmp_path: Path
) -> None:
    out = tmp_path / "written.csv"
    expression = template.format(path=secret.as_posix(), out=out.as_posix())
    with pytest.raises(ShapingError):
        _filter(expression)
    assert not out.exists()
    assert not Path(out.as_posix() + ".db").exists()


@pytest.mark.parametrize("template", ATTACKS)
def test_formula_attacks_fail_and_write_nothing(
    template: str, secret: Path, tmp_path: Path
) -> None:
    out = tmp_path / "written.csv"
    text = template.format(path=secret.as_posix(), out=out.as_posix())
    with pytest.raises(ShapingError):
        _formula(text)
    assert not out.exists()
    assert not Path(out.as_posix() + ".db").exists()


def test_formula_guard_rejection_keeps_its_code(secret: Path) -> None:
    with pytest.raises(ShapingError) as info:
        _formula(f"(SELECT count(*) FROM read_csv('{secret.as_posix()}'))")
    assert info.value.code == "TD-SHAPE-112"
    assert info.value.detail.startswith("Section 1:")


def test_file_read_does_not_leak_through_a_later_section(secret: Path) -> None:
    sections = [
        {"target_column": "a", "formula_text": "[x] + 1"},
        {
            "target_column": "b",
            "formula_text": f"(SELECT count(*) FROM read_csv('{secret.as_posix()}'))",
        },
    ]
    with pytest.raises(ShapingError) as info:
        formula_core.run_node([_frame()], {"sections": sections})
    assert info.value.detail.startswith("Section 2:")


# --- editor validation --------------------------------------------------------


def test_formula_validation_reports_the_rejection(secret: Path) -> None:
    text = f"(SELECT count(*) FROM read_csv('{secret.as_posix()}'))"
    settings = {"sections": [{"target_column": "y", "formula_text": text}]}
    errors = formula_core.validate_section([_frame()], settings, 0)
    assert errors and "TD-SHAPE-112" in errors[0]["message"]


def test_engine_lock_is_the_second_layer(secret: Path, tmp_path: Path) -> None:
    """Even if the text check were bypassed the connection cannot read files."""
    import duckdb

    from trigger_designer.core.sql_guard import connect_for_shaping

    out = tmp_path / "w.csv"
    with connect_for_shaping() as duck:
        duck.register("df_filter", _frame())
        with pytest.raises(duckdb.Error):
            duck.sql(f"SELECT * FROM read_csv('{secret.as_posix()}')").pl()
        with pytest.raises(duckdb.Error):
            duck.execute(f"COPY df_filter TO '{out.as_posix()}'")
        with pytest.raises(duckdb.Error):
            duck.execute("SET enable_external_access=true")
        # registering a new relation on a locked connection still works
        duck.register("df_step_1", _frame())
        assert duck.sql("SELECT count(*) AS n FROM df_step_1").pl()["n"][0] == 3
    assert not out.exists()


# --- generated code goes through the same path ---------------------------------


def _filter_node(qtbot):
    from nodeeditor.node_edge import Edge

    from trigger_designer.core.node_configuration import (
        NodeTypes,
        PreparationNodes,
        get_class_from_opcode,
    )
    from trigger_designer.qt.design_window import TriggerSubWindow
    from trigger_designer.qt.node_base import TriggerNode

    window = TriggerSubWindow()
    qtbot.addWidget(window)

    class Source(TriggerNode):
        node_title = "Source"

        def __init__(self, scene) -> None:
            super().__init__(scene, inputs=[], outputs=[3])
            self.value = [{"data": _frame(), "variable_name": "var_src"}]
            self.markDirty(False)
            self.markInvalid(False)

        def evalImplementation(self):
            return self.value

    source = Source(window.scene)
    cls = get_class_from_opcode(PreparationNodes.FILTER, NodeTypes.PREPARATION)
    node = cls(window.scene)
    Edge(window.scene, source.outputs[0], node.inputs[0])
    node.markDirty(True)
    node.eval()
    return node


def test_generated_code_runs_the_guarded_runner(qtbot) -> None:
    node = _filter_node(qtbot)
    content = node.content
    content.set_setting("mode", "expression", "Filter Mode Changed")
    content.set_setting("expression", "[x] > 1; DROP TABLE t", "Filter Expression")
    code = content.get_code()
    ast.parse(code)
    assert "core.shaping.filter" in code
    with pytest.raises(ShapingError):
        exec(code, {"__name__": "__main__"}, {"var_src": _frame()})  # noqa: S102


def test_filter_editor_validation_reports_the_rejection(qtbot, secret) -> None:
    node = _filter_node(qtbot)
    errors = node.content.validate_expression(
        f"[x] IN (SELECT 1 FROM read_csv('{secret.as_posix()}'))"
    )
    assert errors and "TD-SHAPE-112" in errors[0]["message"]
    assert node.content.validate_expression("[x] > 1") == []
