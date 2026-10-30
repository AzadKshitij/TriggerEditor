"""Sweep guard: no ``'{x}'`` / ``"{x}"`` interpolation inside code generators."""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "trigger_designer"
CODEGEN_FUNCTIONS = {
    "get_code",
    "_builder_code",
    "_position_code",
    "_manual_code",
    "audit_code",
    "_build_dtype_conversion_code",
}


def _hits(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for fn in ast.walk(tree):
        if not (isinstance(fn, ast.FunctionDef) and fn.name in CODEGEN_FUNCTIONS):
            continue
        for node in ast.walk(fn):
            if not isinstance(node, ast.JoinedStr):
                continue
            v = node.values
            for i, part in enumerate(v):
                if (
                    isinstance(part, ast.FormattedValue)
                    and part.conversion != ord("r")
                    and 0 < i < len(v) - 1
                    and isinstance(v[i - 1], ast.Constant)
                    and isinstance(v[i + 1], ast.Constant)
                    and isinstance(v[i - 1].value, str)
                    and isinstance(v[i + 1].value, str)
                    and v[i - 1].value[-1:] in ("'", '"')
                    and v[i + 1].value[:1] == v[i - 1].value[-1:]
                ):
                    yield (path.name, fn.name, node.lineno)


def test_no_unquoted_interpolation_in_generated_code() -> None:
    found = [h for p in SRC.rglob("*.py") for h in _hits(p)]
    assert found == []


def test_scan_detects_the_old_pattern(tmp_path) -> None:
    bad = tmp_path / "bad.py"
    bad.write_text(
        "def get_code(self):\n    return f\"sep='{self.delimiter}'\"\n",
        encoding="utf-8",
    )
    assert list(_hits(bad))
