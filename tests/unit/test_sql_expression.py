"""Filter/Formula SQL expression rewriting: column references and aliases."""

from __future__ import annotations

from trigger_designer.core.shaping.sql_expression import prepare_expression_sql


def test_case_differing_columns_each_resolve_to_themselves() -> None:
    assert prepare_expression_sql("[A] + [a]", ["A", "a"]) == '"A" + "a"'


def test_single_column_resolves_case_insensitively() -> None:
    assert prepare_expression_sql("[amount]", ["Amount"]) == '"Amount"'


def test_inner_spaces_are_ignored_when_resolving() -> None:
    assert prepare_expression_sql("[ Amount ]", ["Amount"]) == '"Amount"'


def test_backslash_in_column_name_stays_literal() -> None:
    assert prepare_expression_sql(r"[Net\Gross]", [r"Net\Gross"]) == r'"Net\Gross"'


def test_unknown_reference_is_left_unchanged() -> None:
    assert prepare_expression_sql("[nope]", ["A"]) == "[nope]"


def test_bracket_text_inside_string_literal_is_not_rewritten() -> None:
    sql = prepare_expression_sql("'[A]' + [A]", ["A"])
    assert sql == "'[A]' + \"A\""


def test_strip_alias_skips_bracket_names_but_applies_outside() -> None:
    sql = prepare_expression_sql("[strip(code)] + strip(x)", ["strip(code)"])
    assert sql == '"strip(code)" + trim(x)'


def test_in_between_alias_still_applies_outside_brackets() -> None:
    sql = prepare_expression_sql(
        "[n] in_between (1, 5)", ["in_between(1, 2)", "n"], in_between=True
    )
    assert sql == '"n" BETWEEN 1 AND 5'


def test_in_between_with_bracketed_bounds_still_translates() -> None:
    sql = prepare_expression_sql("[s] in_between ([lo], [hi])", ["s", "lo", "hi"])
    assert sql == '"s" BETWEEN "lo" AND "hi"'


def test_column_name_containing_brackets_resolves_in_full() -> None:
    sql = prepare_expression_sql(
        "[Amount [USD]] + [Amount]", ["Amount [USD]", "Amount"]
    )
    assert sql == '"Amount [USD]" + "Amount"'
