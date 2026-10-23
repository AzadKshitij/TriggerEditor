"""The reported Formula case: a trailing operator is a syntax error."""

from __future__ import annotations

import polars as pl

from trigger_designer.core.errors import translate_exception
from trigger_designer.qt.widgets.nodes.Preparation.formula import FormulaContent


def _content(formula_text: str) -> FormulaContent:
    content = FormulaContent.__new__(FormulaContent)
    content.formula_sections = [
        {"target_column": "result", "formula_text": formula_text}
    ]
    content.section_widgets = []
    content.sections_layout = None
    content.add_section_button = None
    content.section_count_label = None
    content._dock_layout = None
    content.incoming_variable = "input_df"
    content.incom_data = pl.DataFrame({"g": [2], "discount_pct": [0.1]})
    content.data = None
    content.variable_name = "var_formula_test"
    content.last_error = ""
    content.section_errors = {}
    content._live_section_errors = {}
    return content


def test_trailing_operator_is_plain_language() -> None:
    content = _content("[g] * [discount_pct] + ")
    content.update_data()
    assert "Required keyword" in content.last_error

    error = translate_exception(content.last_error)
    assert error.code == "TD-EXP-001"
    assert error.title == "The expression has a syntax error."
    assert "ends too early" in error.detail
    assert "Required keyword" not in error.render_tooltip()
