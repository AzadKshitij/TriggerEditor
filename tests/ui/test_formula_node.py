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


def test_live_formula_runs_sections_in_one_duckdb_query(monkeypatch) -> None:
    import duckdb

    content = _build_formula_content(
        [
            {"target_column": "double_amount", "formula_text": "[amount] * 2"},
            {"target_column": "amount_band", "formula_text": "[double_amount] + 1"},
        ]
    )
    original_connect = duckdb.connect
    statements = []

    class CountingConnection:
        def __init__(self):
            self.connection = original_connect(":memory:")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.connection.close()

        def register(self, *args):
            return self.connection.register(*args)

        def execute(self, sql):
            statements.append(sql)
            return self.connection.execute(sql)

    monkeypatch.setattr(duckdb, "connect", lambda *args: CountingConnection())
    content.update_data()

    assert content.last_error == ""
    assert content.data["amount_band"].to_list() == [21, 51]
    assert len(statements) == 1


def test_live_formula_failure_reports_second_section() -> None:
    content = _build_formula_content(
        [
            {"target_column": "double_amount", "formula_text": "[amount] * 2"},
            {"target_column": "bad", "formula_text": "NOSUCHFUNC([double_amount])"},
        ]
    )
    content.update_data()
    assert content.last_error.startswith("Section 2:")
    assert set(content.section_errors) == {1}


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
    assert errors[0]["line"] == 1
    assert errors[0]["column"] == 0
    assert errors[0]["length"] == 4
    editor.deleteLater()


def test_sqlglot_accepts_multiline_expression_and_formula_quoting() -> None:
    _get_app()
    editor = SQLFormulaEditor()
    for formula in (
        "COALESCE(\n [Amount With Spaces],\n 0)",
        "CASE WHEN [amount] > 1 THEN \"it's [fine]\" ELSE 'low' END",
        "[amount] + (\n 2)",
        "'it''s [literal]'",
    ):
        assert editor.validate_sql_syntax(formula) == [], formula
    editor.deleteLater()


def test_sqlglot_reports_multiline_syntax_position_in_editor() -> None:
    _get_app()
    editor = SQLFormulaEditor()
    errors = editor.validate_sql_syntax("[amount] +\n )")
    assert errors
    assert errors[0]["line"] == 2
    assert errors[0]["column"] == 1
    editor.deleteLater()


def test_incomplete_quotes_do_not_crash_editor() -> None:
    _get_app()
    editor = SQLFormulaEditor()
    for formula, line, column in (
        ('"', 1, 0),
        ("'unfinished", 1, 0),
        ('[amount] +\n "unfinished', 2, 1),
    ):
        editor.setPlainText(formula)
        editor.check_for_errors()
        assert editor.errors
        assert editor.errors[0]["line"] == line
        assert editor.errors[0]["column"] == column
        assert "Unterminated" in editor.errors[0]["message"]
    content = _build_formula_content([{"target_column": "result", "formula_text": '"'}])
    editor.external_validator = lambda text: content.validate_section_text(0, text)
    editor.setPlainText('"')
    editor.check_for_errors()
    assert editor.errors
    editor.deleteLater()


def test_duckdb_success_overrides_sqlglot_diagnostics(monkeypatch) -> None:
    _get_app()
    editor = SQLFormulaEditor()
    editor.external_validator = lambda text: []
    monkeypatch.setattr(
        editor,
        "validate_sql_syntax",
        lambda text: [{"message": "Parser disagrees", "line": 1, "column": 0}],
    )
    editor.setPlainText("[amount] + 1")
    editor.check_for_errors()
    assert editor.errors == []
    editor.deleteLater()


def test_duckdb_parser_failure_uses_sqlglot_error_location() -> None:
    _get_app()
    editor = SQLFormulaEditor()
    content = _build_formula_content(
        [{"target_column": "result", "formula_text": "[amount] +\n )"}]
    )
    editor.external_validator = lambda text: content.validate_section_text(0, text)
    editor.setPlainText("[amount] +\n )")
    editor.check_for_errors()
    assert any(error["line"] == 2 and error["column"] == 1 for error in editor.errors)
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


def test_invalid_formula_error_does_not_name_generated_alias() -> None:
    for text in ('" sadda [category]', '"" sadda [category]', '" sadda " [category]'):
        content = _build_formula_content(
            [{"target_column": "Lol", "formula_text": text}]
        )
        content.update_data()
        assert content.section_errors[0]
        assert "AS" not in content.section_errors[0]
        assert '"Lol"' not in content.section_errors[0]
        assert "syntax error at or near" not in content.section_errors[0]


def test_closed_string_followed_by_column_requires_operator() -> None:
    _get_app()
    editor = SQLFormulaEditor()
    text = '" sadda " [category]'
    errors = editor.validate_sql_syntax(text)
    assert errors
    assert errors[0]["message"] == "Missing operator before column reference"
    assert errors[0]["column"] == text.index("[category]")
    assert errors[0]["length"] == len("[category]")
    content = _build_formula_content([{"target_column": "Lol", "formula_text": text}])
    editor.set_column_names(["category"])
    editor.external_validator = lambda formula: content.validate_section_text(
        0, formula
    )
    editor.setPlainText(text)
    editor.check_for_errors()
    assert editor.errors[0]["message"] == errors[0]["message"]
    assert "AS" not in editor.errors[0]["message"]
    assert editor.validate_sql_syntax('" sadda " || [category]') == []
    editor.deleteLater()


def test_formula_rejects_top_level_sql_aliases() -> None:
    for text in ("'text' result", "'text' AS result"):
        content = _build_formula_content(
            [{"target_column": "label", "formula_text": text}]
        )
        errors = SQLFormulaEditor.validate_sql_syntax(text)
        assert errors
        assert errors[0]["column"] == text.index("result")
        content.update_data()
        assert content.section_errors[0] == errors[0]["message"]


def test_screenshot_error_points_to_unterminated_quote_not_generated_sql() -> None:
    content = _build_formula_content(
        [{"target_column": "Lol", "formula_text": '" sadda [brand]'}]
    )
    result = content.validate_section_text(0, '" sadda [brand]')
    assert result[0]["category"] == "syntax"
    assert result[0]["line"] == 1
    assert result[0]["column"] == 0
    assert result[0]["message"] == "Unterminated string literal"
    content.update_data()
    assert content.last_error == "Section 1: Unterminated string literal"
    assert 'AS "Lol"' not in content.last_error


def test_schema_only_validation_does_not_collect_lazy_input(monkeypatch) -> None:
    content = _build_formula_content(
        [{"target_column": "x", "formula_text": "[amount] * 2"}]
    )
    content.incom_data = content.incom_data.lazy()

    def no_collect(*args, **kwargs):
        raise AssertionError("Editor validation must not collect input rows")

    monkeypatch.setattr(pl.LazyFrame, "collect", no_collect)
    assert content.validate_section_text(0, "[amount] * 2") == []
    error = content.validate_section_text(0, "NOSUCHFUNC([amount])")[0]
    assert error["category"] == "execution"
    assert "line" not in error
    assert "NOSUCHFUNC" in error["message"].upper()


def test_schema_validation_includes_previous_sections_and_cast() -> None:
    content = _build_formula_content(
        [
            {"target_column": "derived", "formula_text": "[amount] * 2"},
            {
                "target_column": "typed",
                "formula_text": "[derived] + 1",
                "target_dtype": "Integer",
            },
        ]
    )
    assert content.validate_section_text(1, "[derived] + 1") == []
    content.formula_sections[0]["formula_text"] = "NOSUCHFUNC([amount])"
    errors = content.validate_section_text(1, "[derived] + 1")
    assert errors == [
        {
            "message": "Fix section 1 before validating this section",
            "category": "dependency",
        }
    ]


def test_data_dependent_cast_failure_is_reported_on_execution() -> None:
    content = _build_formula_content(
        [
            {
                "target_column": "typed",
                "formula_text": "[category]",
                "target_dtype": "Integer",
            }
        ]
    )
    # Binding only checks the query's shape; conversion of actual values
    # remains the responsibility of the preview/runtime execution path.
    assert content.validate_section_text(0, "[category]") == []
    content.update_data()
    assert content.last_error.startswith("Section 1:")
    assert content.section_errors[0]
    assert "df_step_" not in content.section_errors[0]
    assert "SELECT " not in content.section_errors[0]
    assert content.data is None


def test_locationless_errors_do_not_underline_or_modify_editor_text() -> None:
    _get_app()
    editor = SQLFormulaEditor()
    editor.setPlainText("NOSUCHFUNC([amount])")
    editor.set_column_names(["amount"])
    editor.external_validator = lambda _: [
        {"message": "Unknown function NOSUCHFUNC", "category": "execution"}
    ]
    messages = []
    changes = []
    editor.allErrorsDetected.connect(messages.append)
    editor.textChanged.connect(lambda: changes.append(True))
    editor.check_for_errors()
    assert messages[-1] == ["Unknown function NOSUCHFUNC"]
    assert editor.extraSelections() == []
    assert not changes
    editor.setPlainText("[amount] + 1")
    assert editor.errors == []
    assert messages[-1] == []
    editor.external_validator = lambda _: []
    editor.check_for_errors()
    assert editor.toPlainText() == "[amount] + 1"
    editor.deleteLater()


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


def test_dtype_dropdown_row_and_pane_owns_scroll_area() -> None:
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
    # The Config Dock pane owns the single scrollbar; a node-level scroll area
    # nested inside it would trap the pointer and stop the pane scrolling.
    assert host.findChild(QScrollArea) is None

    from trigger_designer.qt.widgets.common import NoWheelComboBox

    assert isinstance(widgets["target_selector"], NoWheelComboBox)
    assert isinstance(widgets["dtype_selector"], NoWheelComboBox)

    content._set_section_target(0, "fresh")
    widgets = content.section_widgets[0]
    assert widgets["dtype_selector"].isEnabled()
    integer_index = widgets["dtype_selector"].findText("Integer")
    content.handle_dtype_activation(0, integer_index)
    assert content.formula_sections[0]["target_dtype"] == "Integer"


def test_existing_column_keeps_position_new_appends_last() -> None:
    content = _build_formula_content(
        [
            {"target_column": "amount", "formula_text": "[amount] * 2"},
            {"target_column": "brand_new", "formula_text": "[amount] + 1"},
        ]
    )
    content.update_data()
    assert content.last_error == ""
    assert content.data.columns == ["amount", "category", "order_date", "brand_new"]
    assert content.data["amount"].to_list() == [20, 50]


def test_formula_cards_borderless_themed_untitled() -> None:
    _get_app()
    from nodeeditor.node_scene import Scene
    from qtpy.QtWidgets import QVBoxLayout, QWidget

    from trigger_designer.qt.widgets.nodes.Preparation.formula import (
        TriggerNode_Formula,
    )

    node = TriggerNode_Formula(Scene())
    content = node.content
    content.incom_data = pl.DataFrame({"amount": [10, 25]})
    content.formula_sections.append(content._default_section())
    host = QWidget()
    content.create_layout(QVBoxLayout(host))
    assert len(content.section_widgets) == 2
    for widgets in content.section_widgets:
        assert "title_label" not in widgets
        assert widgets["card"].styleSheet() == ""
        assert widgets["error_label"].styleSheet() == ""
        assert widgets["remove_button"].toolTip() == "Remove formula"
    assert content.section_widgets[0]["remove_button"].isEnabled()

    from qtpy.QtWidgets import QFrame

    separators = [
        frame
        for frame in host.findChildren(QFrame)
        if frame.objectName() == "formulaSeparator"
    ]
    assert len(separators) == 1

    card = content.section_widgets[0]["card"]
    header_layout = card.header_layout
    assert header_layout.indexOf(content.section_widgets[0]["target_selector"]) >= 0
    assert header_layout.indexOf(content.section_widgets[0]["remove_button"]) >= 0
    host.deleteLater()


def test_formula_sidebar_uses_compact_spacing() -> None:
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
    assert content.sections_layout.spacing() == 2
    card = content.section_widgets[0]["card"]
    # The card itself is flush; the body carries the 4px inset so the header
    # row and the folding body line up on the same edge.
    outer = card.layout().contentsMargins()
    assert (outer.left(), outer.top()) == (0, 0)
    body = card.body_layout.contentsMargins()
    assert (body.left(), body.top()) == (4, 2)
    assert card.body_layout.spacing() == 2
    host.deleteLater()


def test_dropdowns_ignore_wheel_without_focus() -> None:
    _get_app()
    from qtpy.QtCore import QPoint, QPointF, Qt
    from qtpy.QtGui import QWheelEvent
    from qtpy.QtWidgets import QApplication

    from trigger_designer.qt.widgets.common import NoWheelComboBox

    combo = NoWheelComboBox()
    combo.addItems(["a", "b", "c"])
    combo.setCurrentIndex(0)

    event = QWheelEvent(
        QPointF(5, 5),
        QPointF(5, 5),
        QPoint(0, 0),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    QApplication.sendEvent(combo, event)
    assert not event.isAccepted()
    assert combo.currentIndex() == 0
    combo.deleteLater()


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


def test_autocomplete_prefix_and_matches() -> None:
    from trigger_designer.qt.widgets.sql_formula_editor import (
        extract_completion_prefix,
        match_completions,
    )

    assert extract_completion_prefix("COA", 3) == ("COA", False)
    assert extract_completion_prefix("[cus", 4) == ("cus", True)
    assert "COALESCE()" in match_completions("COA", False, ["amount"])
    assert match_completions("cus", True, ["customer_id", "city"]) == ["customer_id"]
    assert "[customer_id]" in match_completions("cus", False, ["customer_id"])


def test_autocomplete_insert_replaces_prefix() -> None:
    _get_app()
    editor = SQLFormulaEditor()
    editor.set_column_names(["amount", "customer_id"])

    editor.setPlainText("COA")
    cursor = editor.textCursor()
    cursor.movePosition(cursor.MoveOperation.End)
    editor.setTextCursor(cursor)
    editor._insert_completion("COALESCE()")
    assert editor.toPlainText() == "COALESCE()"

    editor.setPlainText("[cus")
    cursor = editor.textCursor()
    cursor.movePosition(cursor.MoveOperation.End)
    editor.setTextCursor(cursor)
    editor._insert_completion("customer_id")
    assert editor.toPlainText() == "[customer_id]"
    editor.deleteLater()


def test_strip_alias_runs_as_trim() -> None:
    content = _build_formula_content(
        [{"target_column": "clean_category", "formula_text": "strip([category])"}]
    )
    prepared = content._prepare_formula_for_sql(
        "strip([category])", ["amount", "category", "order_date"]
    )
    assert prepared == 'trim("category")', prepared
    content.update_data()
    assert content.last_error == ""
    assert content.data["clean_category"].to_list() == ["A", "B"]


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
    test_autocomplete_prefix_and_matches()
    test_autocomplete_insert_replaces_prefix()
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
    test_existing_column_keeps_position_new_appends_last()
    test_config_dock_skips_rebuild_for_same_node()
    test_dropdowns_ignore_wheel_without_focus()
    test_formula_sidebar_uses_compact_spacing()
    test_formula_cards_borderless_themed_untitled()
    test_formula_refreshes_selectors_on_schema_change()
    test_strip_alias_runs_as_trim()
    print("ok")


if __name__ == "__main__":
    main()
