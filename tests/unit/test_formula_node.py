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
from trigger_designer.qt.widgets.sql_formula_editor import (
    SQLFormulaEditor,
    SQLFormulaWidget,
)


APP = QApplication.instance() or QApplication([])


def _get_app() -> QApplication:
    return APP


def _build_formula_content(formula_sections):
    content = FormulaContent.__new__(FormulaContent)
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
    content.section_errors = {}
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

    assert empty_sections == [
        {
            "target_column": "",
            "formula_text": "",
            "editor_height": 120,
            "target_dtype": "",
        }
    ]
    assert len(oversized_sections) == MAX_FORMULA_SECTIONS


def test_formula_content_supports_date_functions() -> None:
    content = _build_formula_content(
        [
            {"target_column": "order_year", "formula_text": "YEAR([order_date])"},
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


def test_case_end_balanced_produces_no_error() -> None:
    _get_app()
    editor = SQLFormulaEditor()
    editor.set_column_names(["Age"])
    errors = editor.validate_sql_syntax(
        "CASE WHEN [Age] > 30 THEN 'Adult' ELSE 'Young' END"
    )
    assert errors == []
    editor.deleteLater()


def test_case_missing_end_points_at_case_token() -> None:
    _get_app()
    editor = SQLFormulaEditor()
    errors = editor.validate_sql_syntax("CASE WHEN [Age] > 30 THEN 'Adult'")
    assert len(errors) == 1
    assert errors[0]["message"] == "CASE statement missing END keyword"
    assert errors[0]["length"] == 4
    editor.deleteLater()


def test_column_matching_ignores_case_and_padding() -> None:
    _get_app()
    editor = SQLFormulaEditor()
    editor.set_column_names(["RelevancyScore"])
    assert editor.validate_column_references("[RelevancyScore]") == []
    assert editor.validate_column_references("[relevancyscore]") == []
    assert editor.validate_column_references("[ RelevancyScore ]") == []
    unknown = editor.validate_column_references("[Nope]")
    assert len(unknown) == 1
    editor.deleteLater()


def test_runtime_column_rewrite_matches_validation() -> None:
    content = _build_formula_content(
        [{"target_column": "double_amount", "formula_text": "[AMOUNT] * 2"}]
    )
    content.update_data()
    assert content.last_error == ""
    assert content.data["double_amount"].to_list() == [20, 50]


def test_validate_section_text_catches_bad_function() -> None:
    content = _build_formula_content(
        [{"target_column": "x", "formula_text": "NOSUCHFUNC([amount])"}]
    )
    errors = content.validate_section_text(0, "NOSUCHFUNC([amount])")
    assert len(errors) == 1
    assert "x" not in (content.data.columns if content.data is not None else [])


def test_validate_section_text_passes_good_formula() -> None:
    content = _build_formula_content(
        [{"target_column": "double_amount", "formula_text": "[amount] * 2"}]
    )
    assert content.validate_section_text(0, "[amount] * 2") == []


def test_double_quoted_text_is_a_string() -> None:
    content = _build_formula_content(
        [{"target_column": "label", "formula_text": '"pass"'}]
    )
    content.update_data()
    assert content.last_error == ""
    assert content.data["label"].to_list() == ["pass", "pass"]


def test_bracket_text_inside_strings_is_ignored() -> None:
    _get_app()
    editor = SQLFormulaEditor()
    editor.set_column_names(["amount"])
    assert (
        editor.validate_column_references(
            "CASE WHEN [amount] > 20 THEN '[oops]' ELSE 'low' END"
        )
        == []
    )
    editor.deleteLater()
    content = _build_formula_content(
        [
            {
                "target_column": "band",
                "formula_text": "CASE WHEN [amount] > 20 THEN '[oops]' ELSE 'low' END",
            }
        ]
    )
    content.update_data()
    assert content.last_error == ""
    assert content.data["band"].to_list() == ["low", "[oops]"]


def test_escaped_quotes_do_not_raise() -> None:
    _get_app()
    editor = SQLFormulaEditor()
    assert editor.validate_sql_syntax("'it''s'") == []
    editor.deleteLater()
    content = _build_formula_content(
        [{"target_column": "quote", "formula_text": "'it''s'"}]
    )
    content.update_data()
    assert content.last_error == ""
    assert content.data["quote"].to_list() == ["it's", "it's"]


def test_target_dtype_normalized_and_defaulted() -> None:
    content = _build_formula_content([])
    sections = content._normalize_sections(
        [
            {"target_column": "a", "formula_text": "1", "target_dtype": "Integer"},
            {"target_column": "b", "formula_text": "2", "target_dtype": "Nope"},
            {"target_column": "c", "formula_text": "3"},
        ]
    )
    assert [s["target_dtype"] for s in sections] == ["Integer", "", ""]
    assert all(s["editor_height"] == 120 for s in sections)


def test_debounce_is_fixed_at_800ms() -> None:
    from trigger_designer.qt.widgets.sql_formula_editor import (
        ERROR_CHECK_DEBOUNCE_MS,
    )

    assert ERROR_CHECK_DEBOUNCE_MS == 800


def test_shorten_error_keeps_only_referenced_column() -> None:
    blob = (
        'Binder Error: Referenced column "RelevancyScore" not found in FROM clause!\n'
        'Candidate bindings: "Relevancy Score", "Hot Keyword", "Seed"\n'
        "LINE 1: SELECT t, CASE when [RelevancyScore] > 95 then 'pass' else 'fail' END AS \"Check\""
    )
    assert (
        FormulaContent._shorten_error(blob)
        == 'Referenced column "RelevancyScore" not found'
    )
    assert FormulaContent._shorten_error("Binder Error: boom\nsecond line") == "boom"


def test_update_data_reports_short_section_error() -> None:
    content = _build_formula_content(
        [{"target_column": "x", "formula_text": "NOSUCHFUNC([amount])"}]
    )
    content.update_data()
    assert content.last_error.startswith("Section 1:")
    assert "Candidate bindings" not in content.last_error
    assert "LINE" not in content.last_error
    assert content.section_errors == {0: content.last_error.removeprefix("Section 1: ")}


def test_editor_height_normalized_and_clamped() -> None:
    content = _build_formula_content([])
    sections = content._normalize_sections(
        [
            {"target_column": "a", "formula_text": "1", "editor_height": 300},
            {"target_column": "b", "formula_text": "2", "editor_height": 5},
            {"target_column": "c", "formula_text": "3"},
        ]
    )
    assert [s["editor_height"] for s in sections] == [300, 60, 120]


def test_debounced_commit_applies_without_focus_out() -> None:
    _get_app()
    from nodeeditor.node_scene import Scene
    from qtpy.QtWidgets import QVBoxLayout, QWidget

    from trigger_designer.qt.widgets.nodes.Preparation.formula import (
        TriggerNode_Formula,
    )

    node = TriggerNode_Formula(Scene())
    content = node.content
    content.incom_data = pl.DataFrame({"amount": [10, 25]})
    content._set_section_target(0, "double_amount")
    host = QWidget()
    content.create_layout(QVBoxLayout(host))
    content.section_widgets[0]["formula_input"].set_text("[amount] * 2")
    content._debounced_commit(0)
    assert content.last_error == ""
    assert content.data["double_amount"].to_list() == [20, 50]
    assert content.section_widgets[0]["formula_input"].height() == 120


def test_dtype_cast_applies_to_new_columns_only() -> None:
    content = _build_formula_content(
        [
            {
                "target_column": "half",
                "formula_text": "[amount] / 2",
                "target_dtype": "Integer",
            },
            {
                "target_column": "amount",
                "formula_text": "[amount] + 1",
                "target_dtype": "String",
            },
        ]
    )
    content.update_data()
    assert content.last_error == ""
    assert content.data["half"].dtype == pl.Int64
    assert content.data["amount"].dtype == pl.Int64

    generated_code = content.get_code()
    assert "CAST" in generated_code
    assert generated_code.count("CAST") == 1


def test_dtype_state_existing_locked_new_editable() -> None:
    content = _build_formula_content(
        [
            {"target_column": "amount", "formula_text": "[amount]"},
            {
                "target_column": "fresh",
                "formula_text": "[amount]",
                "target_dtype": "Float",
            },
        ]
    )
    assert content._dtype_state_for_section(0) == ("Integer", False)
    assert content._dtype_state_for_section(1) == ("Float", True)


def test_dtype_dropdown_row_and_scroll_area() -> None:
    _get_app()
    from nodeeditor.node_scene import Scene
    from qtpy.QtWidgets import QScrollArea, QVBoxLayout, QWidget

    from trigger_designer.qt.widgets.nodes.Preparation.formula import (
        DTYPE_OPTIONS,
        TriggerNode_Formula,
    )

    node = TriggerNode_Formula(Scene())
    content = node.content
    content.incom_data = pl.DataFrame({"amount": [10, 25]})
    host = QWidget()
    content.create_layout(QVBoxLayout(host))
    widgets = content.section_widgets[0]
    assert [widgets["dtype_selector"].itemText(i) for i in range(9)] == DTYPE_OPTIONS
    assert host.findChild(QScrollArea) is not None

    content._set_section_target(0, "fresh")
    widgets = content.section_widgets[0]
    assert widgets["dtype_selector"].isEnabled()
    integer_index = widgets["dtype_selector"].findText("Integer")
    content.handle_dtype_activation(0, integer_index)
    assert content.formula_sections[0]["target_dtype"] == "Integer"


def test_config_dock_skips_rebuild_for_same_node() -> None:
    _get_app()
    from nodeeditor.node_scene import Scene
    from qtpy.QtWidgets import QVBoxLayout, QWidget

    from trigger_designer.qt.docks.node_config import ConfigDock
    from trigger_designer.qt.widgets.nodes.Preparation.formula import (
        TriggerNode_Formula,
    )

    scene = Scene()
    node = TriggerNode_Formula(scene)
    node.content.incom_data = pl.DataFrame({"amount": [10, 25]})
    dock = ConfigDock()
    dock.updateConfig([node.grNode])
    assert dock.dock_layout.count() > 0
    first = [
        dock.dock_layout.itemAt(i).widget() for i in range(dock.dock_layout.count())
    ]

    dock.updateConfig([node.grNode])
    second = [
        dock.dock_layout.itemAt(i).widget() for i in range(dock.dock_layout.count())
    ]
    assert first == second

    node2 = TriggerNode_Formula(scene)
    node2.content.incom_data = pl.DataFrame({"amount": [10, 25]})
    dock.updateConfig([node2.grNode])
    third = [
        dock.dock_layout.itemAt(i).widget() for i in range(dock.dock_layout.count())
    ]
    assert third != first

    dock.updateConfig([])
    assert dock.dock_layout.count() == 0
    dock.deleteLater()


def test_formula_refreshes_selectors_on_schema_change() -> None:
    _get_app()
    from nodeeditor.node_scene import Scene
    from qtpy.QtWidgets import QVBoxLayout, QWidget

    from trigger_designer.qt.widgets.nodes.Preparation.formula import (
        TriggerNode_Formula,
    )

    node = TriggerNode_Formula(Scene())
    content = node.content
    content.incom_data = pl.DataFrame({"amount": [10, 25]})
    host = QWidget()
    content.create_layout(QVBoxLayout(host))
    selector = content.section_widgets[0]["target_selector"]
    assert selector.findText("amount") >= 0
    assert selector.findText("total") < 0

    content.incom_data = pl.DataFrame({"amount": [10, 25], "total": [1, 2]})
    content.refresh_dependencies_for_new_data()
    assert selector.findText("total") >= 0
    host.deleteLater()


def test_target_name_survives_serialize_round_trip() -> None:
    _get_app()
    from nodeeditor.node_scene import Scene

    from trigger_designer.qt.widgets.nodes.Preparation.formula import (
        TriggerNode_Formula,
    )

    scene = Scene()
    node = TriggerNode_Formula(scene)
    content = node.content
    content.incom_data = pl.DataFrame({"amount": [10, 25]})
    content._set_section_target(0, "Check")
    assert content.formula_sections[0]["target_column"] == "Check"

    payload = content.serialize()
    assert payload["formula_sections"][0]["target_column"] == "Check"

    scene2 = Scene()
    node2 = TriggerNode_Formula(scene2)
    assert node2.content.deserialize(payload, hashmap={}) is not False
    assert node2.content.formula_sections[0]["target_column"] == "Check"


def test_new_column_error() -> None:
    known = {"amount", "double_amount"}
    assert FormulaContent._new_column_error("", known) is not None
    assert FormulaContent._new_column_error("amount", known) is not None
    assert FormulaContent._new_column_error("AMOUNT", known) is not None
    assert FormulaContent._new_column_error("fresh", known) is None


def main() -> None:
    _get_app()
    test_formula_content_applies_multiple_sections_in_order()
    test_formula_content_normalizes_sections()
    test_sql_formula_widget_emits_editing_finished()
    test_formula_content_supports_date_functions()
    test_case_end_balanced_produces_no_error()
    test_case_missing_end_points_at_case_token()
    test_column_matching_ignores_case_and_padding()
    test_runtime_column_rewrite_matches_validation()
    test_validate_section_text_catches_bad_function()
    test_validate_section_text_passes_good_formula()
    test_new_column_error()
    test_target_name_survives_serialize_round_trip()
    test_double_quoted_text_is_a_string()
    test_bracket_text_inside_strings_is_ignored()
    test_escaped_quotes_do_not_raise()
    test_debounce_is_fixed_at_800ms()
    test_shorten_error_keeps_only_referenced_column()
    test_update_data_reports_short_section_error()
    test_editor_height_normalized_and_clamped()
    test_debounced_commit_applies_without_focus_out()
    test_target_dtype_normalized_and_defaulted()
    test_dtype_cast_applies_to_new_columns_only()
    test_dtype_state_existing_locked_new_editable()
    test_dtype_dropdown_row_and_scroll_area()
    test_config_dock_skips_rebuild_for_same_node()
    test_formula_refreshes_selectors_on_schema_change()
    print("ok")


if __name__ == "__main__":
    main()
