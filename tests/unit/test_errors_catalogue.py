"""Catalogue completeness, placeholder safety and rendering."""

from __future__ import annotations

import re
from string import Formatter

from trigger_designer.core.errors.catalogue import (
    _OPTIONAL_PARAMS,
    CATALOGUE,
    render_entry,
)
from trigger_designer.core.errors.model import shorten
from trigger_designer.core.errors.translator import RULES

EMOJI = re.compile(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]")


def _templates() -> list[str]:
    templates: list[str] = []
    for entry in CATALOGUE.values():
        for key in ("title", "title_located", "detail", "detail_located", "hint"):
            value = entry.get(key)
            if value:
                templates.append(str(value))
        for fix, _condition in entry.get("fixes", ()):
            templates.append(str(fix))
    return templates


def _sample_params() -> dict:
    params = {key: "X" for key in _OPTIONAL_PARAMS}
    for key in ("row", "n", "m", "k", "min", "seconds", "failing_count"):
        params[key] = 1
    params["row"] = 4210
    params["engine_duckdb"] = "1"
    return params


def test_every_rule_code_exists_in_catalogue() -> None:
    for rule in RULES:
        for code in rule.codes:
            assert code in CATALOGUE, (rule.id, code)


def test_every_non_reserved_code_has_a_rule() -> None:
    reserved = {code for code, entry in CATALOGUE.items() if entry.get("reserved")}
    rule_codes = {code for rule in RULES for code in rule.codes}
    missing = {
        code
        for code, entry in CATALOGUE.items()
        if code not in reserved and not entry.get("passthrough")
    } - rule_codes
    assert not missing, sorted(missing)


def test_placeholders_are_allowed() -> None:
    allowed = set(_OPTIONAL_PARAMS)
    for template in _templates():
        for _literal, field, _spec, _conversion in Formatter().parse(template):
            if field is None:
                continue
            name = field.split(".")[0].split("[")[0]
            assert name in allowed, (name, template)


def test_rendered_titles_fit_and_have_no_leftovers() -> None:
    params = _sample_params()
    for code in CATALOGUE:
        title, detail, fixes = render_entry(code, params, located=True)
        assert title, code
        assert len(title) <= 90, (code, title)
        for text in (title, detail, *fixes):
            assert "{" not in text and "}" not in text, (code, text)
            assert not EMOJI.search(text), (code, text)


def test_row_formatting_uses_thousands_separator() -> None:
    params = _sample_params()
    params["column"] = "Amount"
    params["target_human"] = "whole numbers"
    params["value"] = "x"
    title, _detail, fixes = render_entry("TD-TYP-003", params, located=True)
    assert "row 4,210" in title
    assert "row 4,210" in fixes[0]


def test_all_plan_codes_are_present() -> None:
    for code in (
        "TD-IN-001",
        "TD-IN-010",
        "TD-SCH-001",
        "TD-SCH-011",
        "TD-AUDIT-001",
        "TD-SHAPE-003",
        "TD-OUT-010",
        "TD-CLI-018",
        "TD-RUN-008",
        "TD-SYS-999",
        "TD-SYS-998",
    ):
        assert code in CATALOGUE


def test_rendered_title_limit_uses_shorten() -> None:
    params = _sample_params()
    params["message"] = "word " * 100
    title, _detail, _fixes = render_entry("TD-SYS-001", params)
    assert len(title) <= 90
    assert title == shorten(params["message"], 90)
