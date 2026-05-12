#!/usr/bin/env python3

import os
import sys
from datetime import date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)

import polars as pl
from qtpy.QtCore import QEvent, Qt
from qtpy.QtGui import QFocusEvent
from qtpy.QtWidgets import QApplication

from trigger_designer.qt.widgets.nodes.Preparation.formula import (
    MAX_FORMULA_SECTIONS,
    FormulaContent,
)
from trigger_designer.qt.widgets.sql_formula_editor import SQLFormulaWidget


APP = QApplication.instance() or QApplication([])


def _get_app() -> QApplication:
    return APP


def _build_formula_content(formula_sections):
    content = FormulaContent.__new__(FormulaContent)
    content.formula = ""
    content.formula_text = None
    content.target_column = None
    content.is_new_column = False
    content.formula_sections = formula_sections
    content.section_widgets = []
    content.sections_layout = None
    content.add_section_button = None
    content.section_count_label = None
    content._dock_layout = None
    content.incoming_variable = "input_df"
    content.incom_data = pl.DataFrame(
        {
            "amount": [10, 25],
            "category": ["A", "B"],
            "order_date": [date(2024, 1, 15), date(2025, 6, 1)],
        }
    )
    content.data = None
    content.variable_name = "var_formula_test"
    content.last_error = ""
    content._sync_legacy_fields()
    return content


def test_formula_content_applies_multiple_sections_in_order() -> None:
    content = _build_formula_content(
        [
            {"target_column": "double_amount", "formula_text": "[amount] * 2"},
            {
                "target_column": "amount_band",
                "formula_text": (
                    "CASE WHEN [double_amount] >= 40 THEN 'high' ELSE 'low' END"
                ),
            },
        ]
    )

    content.update_data()

    assert content.last_error == ""
    assert isinstance(content.data, pl.DataFrame)
    assert content.data["double_amount"].to_list() == [20, 50]
    assert content.data["amount_band"].to_list() == ["low", "high"]

    generated_code = content.get_code()
    assert "df_step_0" in generated_code
    assert "df_step_1" in generated_code
    assert '"double_amount"' in generated_code
    assert '"amount_band"' in generated_code


def test_formula_content_normalizes_sections() -> None:
    content = _build_formula_content([])

    empty_sections = content._normalize_sections([])
    oversized_sections = content._normalize_sections(
        [
            {"target_column": f"col_{index}", "formula_text": "1"}
            for index in range(MAX_FORMULA_SECTIONS + 2)
        ]
    )

    assert empty_sections == [{"target_column": "", "formula_text": ""}]
    assert len(oversized_sections) == MAX_FORMULA_SECTIONS


def test_formula_content_supports_bracket_function_shorthand() -> None:
    content = _build_formula_content(
        [
            {"target_column": "order_year", "formula_text": "YEAR[order_date]"},
        ]
    )

    content.update_data()

    assert content.last_error == ""
    assert isinstance(content.data, pl.DataFrame)
    assert content.data["order_year"].to_list() == [2024, 2025]

    generated_code = content.get_code()
    assert 'YEAR("order_date")' in generated_code


def test_sql_formula_widget_emits_editing_finished() -> None:
    _get_app()
    widget = SQLFormulaWidget()
    events = []
    widget.editingFinished.connect(lambda: events.append("finished"))

    widget.editor.focusOutEvent(
        QFocusEvent(QEvent.Type.FocusOut, Qt.FocusReason.OtherFocusReason)
    )

    assert events == ["finished"]
    widget.deleteLater()


def main() -> None:
    _get_app()
    test_formula_content_applies_multiple_sections_in_order()
    test_formula_content_normalizes_sections()
    test_sql_formula_widget_emits_editing_finished()
    print("ok")


if __name__ == "__main__":
    main()
