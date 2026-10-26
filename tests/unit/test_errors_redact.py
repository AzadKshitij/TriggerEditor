"""Redaction removes values but keeps the row number."""

from __future__ import annotations

from trigger_designer.core.errors import NodeError
from trigger_designer.core.errors.redact import redact_error, redact_text


def test_redact_text_removes_polars_values() -> None:
    message = (
        "conversion from `str` to `i64` failed in column 'Amount' for 1 out "
        'of 4 values: ["1,2O0.50"]'
    )
    out = redact_text(message, ("1,2O0.50",))
    assert "1,2O0.50" not in out
    assert "values: [<redacted>]" in out


def test_redact_text_scrubs_duckdb_forms() -> None:
    for message, value in (
        ("Could not convert string '1,2O0.50' to INT32", "1,2O0.50"),
        ('invalid date field format: "31/12/2024", expected', "31/12/2024"),
        (
            'Could not parse string "31/12/2024" according to format',
            "31/12/2024",
        ),
        ("error message for the first shown value: 'x'", "x"),
    ):
        out = redact_text(message, (value,))
        assert value not in out


def test_redact_error_keeps_row_and_flags() -> None:
    error = NodeError(
        code="TD-TYP-001",
        title="Column 'Amount' contains 'x' in row 4,210.",
        detail="reason",
        row_index=4210,
        sample_values=("x",),
        technical='values: ["x"]',
        params={"column": "Amount", "row": "4210", "value": "x"},
    )
    redacted = redact_error(error)
    assert redacted.redacted is True
    assert redacted.row_index == 4210
    assert redacted.sample_values == ()
    assert "x" not in redacted.technical


def test_redact_is_idempotent_and_handles_empty_values() -> None:
    error = NodeError(code="TD-SYS-999", title="x", technical="a")
    once = redact_error(error)
    twice = redact_error(once)
    assert twice.redacted is True
    assert twice.technical == once.technical
