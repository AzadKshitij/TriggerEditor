"""Hostile text from a ``.tds`` must stay data in generated code (BUG-003)."""

from __future__ import annotations

import ast
from pathlib import Path

import polars as pl
import pytest

from trigger_designer.core.node_configuration import (
    IONodes,
    NodeTypes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow

VALUES = [
    "'",
    "\\",
    "');import os #",
    "\n",
    '"',
    "a\x00b",
    "'''",
    "x'\nraise SystemExit('pwned')\n#",
]


@pytest.fixture
def window():
    win = TriggerSubWindow()
    yield win
    win.close()


def _no_extra_statements(code: str, allowed_calls: int | None = None) -> ast.Module:
    """Compile ``code`` and return its tree (a SyntaxError fails the test)."""
    return ast.parse(code)


def _csv(tmp_path: Path) -> Path:
    path = tmp_path / "d.csv"
    path.write_text("a,b\n1,2\n3,4\n", encoding="utf-8")
    return path


def _file_input(window, path, file_type="csv", **attrs):
    node = get_class_from_opcode(IONodes.FILE_INPUT, NodeTypes.IO)(window.scene)
    node.content.filePath = str(path)
    node.content.file_type = file_type
    for key, value in attrs.items():
        setattr(node.content, key, value)
    return node


@pytest.mark.parametrize("value", VALUES)
def test_file_input_delimiter_is_inert(window, tmp_path, value) -> None:
    node = _file_input(window, _csv(tmp_path), delimiter=value)
    code = node.get_code()
    before = ast.parse(_file_input(window, _csv(tmp_path), delimiter=";").get_code())
    tree = _no_extra_statements(code)
    assert len(tree.body) == len(before.body)
    marker = tmp_path / "pwned"
    ns = {"pl": pl, "MARKER": str(marker)}
    try:
        exec(code, ns)  # noqa: S102
    except Exception as exc:  # noqa: BLE001 - polars rejects the odd separator
        assert not isinstance(exc, (SyntaxError, SystemExit))
    assert not marker.exists()


@pytest.mark.parametrize("value", VALUES)
def test_file_input_sheet_is_inert(window, tmp_path, value) -> None:
    node = _file_input(
        window, tmp_path / "x.xlsx", file_type="excel", selected_sheet=value
    )
    code = node.get_code()
    tree = ast.parse(code)
    plain = _file_input(
        window, tmp_path / "x.xlsx", file_type="excel", selected_sheet="Sheet1"
    )
    assert len(tree.body) == len(ast.parse(plain.get_code()).body)
    # the sheet name survives as a single string argument
    calls = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "load_sheet"
    ]
    assert len(calls) == 1
    assert ast.literal_eval(calls[0].keywords[0].value) == value


def test_file_input_delimiter_injection_reproduction(window, tmp_path) -> None:
    """The documented BUG-003 payload must not create the marker file."""
    marker = tmp_path / "marker.txt"
    payload = (
        ",')\nopen(MARKER,'w').write('pwned')\nx = pl.scan_csv('d.csv', separator='"
    )
    node = _file_input(window, _csv(tmp_path), delimiter=payload)
    ns = {"pl": pl, "MARKER": str(marker)}
    try:
        exec(node.get_code(), ns)  # noqa: S102
    except Exception as exc:  # noqa: BLE001
        assert not isinstance(exc, SyntaxError)
    assert not marker.exists()


@pytest.mark.parametrize("value", VALUES)
def test_unknown_node_comment_cannot_break_out(window, value) -> None:
    from trigger_designer.qt.widgets.nodes.unknown import TriggerNode_Unknown

    node = TriggerNode_Unknown(window.scene)
    node.content.missing_op = value
    node.missing_op = value
    code = node.get_code()
    tree = ast.parse(code)
    assert tree.body == []  # a comment, nothing executable
    assert len(code.rstrip("\n").splitlines()) == 1


@pytest.mark.parametrize("value", ["x\nimport os", "a b", "'"])
def test_hostile_node_id_stays_inside_names(window, tmp_path, value) -> None:
    node = _file_input(window, tmp_path / "x.xlsx", file_type="excel")
    node.content.id = value
    tree = ast.parse(node.get_code())
    stmts = [type(n).__name__ for n in tree.body]
    assert "Import" in stmts and stmts.count("Expr") == 0
