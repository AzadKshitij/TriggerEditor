"""NodeError is frozen data, JSON-safe and stable across enrichment."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import FrozenInstanceError
from pathlib import Path

import orjson
import pytest

from trigger_designer.core.errors import (
    ErrorContext,
    NodeError,
    SuggestedFix,
    make_error,
    shorten,
)


def test_node_error_is_frozen_and_has_defaults() -> None:
    error = NodeError(code="TD-SYS-999", title="x")
    assert error.severity == "error"
    assert error.columns == ()
    assert error.suggested_fixes == ()
    with pytest.raises(FrozenInstanceError):
        error.title = "changed"  # type: ignore[misc]


def test_to_dict_from_dict_roundtrip() -> None:
    error = NodeError(
        code="TD-TYP-001",
        title="Column 'Amount' has values that cannot be read as whole numbers.",
        detail="reason",
        hint="Fix it.",
        technical="technical",
        exc_type="InvalidOperationError",
        columns=("Amount",),
        row_index=4210,
        sample_values=("1,2O0.50",),
        suggested_fixes=(SuggestedFix("Fix it.", kind="clean_data"),),
        params={"column": "Amount"},
    )
    data = error.to_dict()
    assert orjson.loads(orjson.dumps(data))["row_index"] == 4210
    restored = NodeError.from_dict(data)
    assert restored == error


def test_from_dict_ignores_unknown_keys_and_fills_defaults() -> None:
    error = NodeError.from_dict({"code": "TD-SYS-999", "title": "x", "future": 1})
    assert error.code == "TD-SYS-999"
    assert error.severity == "error"
    assert error.columns == ()


def test_fingerprint_ignores_row_and_values() -> None:
    error = NodeError(code="TD-SYS-999", title="x", node_id=1)
    moved = error.with_updates(row_index=4, sample_values=("x",))
    assert moved.fingerprint == error.fingerprint
    assert moved.with_updates(node_id=2).fingerprint != error.fingerprint


def test_summary_alias_and_knock_on_property() -> None:
    error = make_error("TD-RUN-003", culprit_label="Select 'Prep'")
    assert error.summary == error.title
    assert error.knock_on is True


def test_shorten_collapses_whitespace_and_limits() -> None:
    assert shorten("  a\n\t b  ", 20) == "a b"
    assert len(shorten("x" * 100, 10)) == 10
    assert shorten("x" * 100, 10).endswith("…")


def test_error_context_from_node_is_getattr_only() -> None:
    class Node:
        id = 7
        node_title = "Aggregate"
        label_text = "Totals"

    ctx = ErrorContext.from_node(Node(), "run")
    assert ctx.node_id == 7
    assert ctx.node_title == "Aggregate"
    assert ctx.node_label == "Aggregate 'Totals'"
    assert ctx.phase == "run"


def test_core_errors_is_qt_free() -> None:
    root = Path(__file__).resolve().parents[2]
    code = (
        "import sys;"
        f"sys.path.insert(0, {str(root / 'src')!r});"
        "import trigger_designer.core.errors;"
        "print(any(m.startswith(('qtpy', 'PyQt6')) for m in sys.modules))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "False"
