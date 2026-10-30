"""``codegen_safe`` literals round-trip and never break out of their context."""

from __future__ import annotations

import ast
import math

import pytest

from trigger_designer.core.codegen_safe import (
    ident_part,
    lit,
    lit_dq,
    lit_list,
    safe_comment,
)

HOSTILE = [
    "a'b",
    "\\",
    "\n",
    "');import os #",
    "a\x00b",
    '"',
    "'''x'''",
    " x",
    "\r\n",
]


@pytest.mark.parametrize("value", HOSTILE)
def test_lit_round_trips_and_is_one_line(value: str) -> None:
    assert ast.literal_eval(lit(value)) == value
    assert "\n" not in lit(value)
    assert "\r" not in lit(value)


@pytest.mark.parametrize("value", HOSTILE)
def test_lit_dq_round_trips(value: str) -> None:
    code = lit_dq(value)
    assert ast.literal_eval(code) == value
    assert "\n" not in code


def test_containers_and_scalars() -> None:
    value = {"k": ("a",), "l": ["a", "b'c", 1, 2.5, None, True]}
    assert ast.literal_eval(lit(value)) == value
    assert ast.literal_eval(lit_list(("a", "b'c"))) == ["a", "b'c"]


def test_non_finite_floats() -> None:
    assert math.isnan(eval(lit(float("nan"))))
    assert eval(lit(float("inf"))) == math.inf


def test_unrenderable_types_raise() -> None:
    with pytest.raises(TypeError):
        lit(object())
    with pytest.raises(TypeError):
        lit_dq(1)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", HOSTILE)
def test_safe_comment_has_no_line_break(value: str) -> None:
    out = safe_comment(value)
    assert "\n" not in out and "\r" not in out and "\x00" not in out
    # still a single comment line: compiles as nothing
    assert compile("# " + out, "<c>", "exec")


@pytest.mark.parametrize("value", ["1", 12345, "x\nimport os", "a-b c", "é"])
def test_ident_part_is_an_identifier_suffix(value) -> None:
    assert ("v_" + ident_part(value)).isidentifier()
