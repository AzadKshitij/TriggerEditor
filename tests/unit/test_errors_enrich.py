"""Enrichment moves the root to the culprit and locates the bad row."""

from __future__ import annotations

import polars as pl

from trigger_designer.core.errors import (
    Ancestor,
    EnrichJob,
    ErrorContext,
    enrich_sync,
    translate_exception,
)


def _cast_error():
    raw = pl.LazyFrame({"Amount": ["10", "1,2O0.50"], "k": [1, 2]})
    try:
        raw.select(pl.col("Amount").cast(pl.Int64)).collect()
    except BaseException as exc:  # noqa: BLE001
        ctx = ErrorContext(
            node_id=2,
            node_label="Output 'x'",
            input_columns=("Amount", "k"),
            input_dtypes={"Amount": "String"},
            referenced_columns=("Amount",),
        )
        return translate_exception(exc, ctx=ctx), raw


def test_enrich_moves_root_to_culprit_and_adds_knock_on() -> None:
    error, raw = _cast_error()
    broken = raw.select(pl.col("Amount").cast(pl.Int64))
    result = enrich_sync(
        error,
        ancestors=(Ancestor(1, broken), Ancestor(2, raw)),
        labels={1: "Select 'Prep'", 2: "Output 'x'"},
        attribute=True,
        locate=False,
    )
    assert result.culprit_node_id == 1
    assert result.root.node_id == 1
    assert result.root.culprit_node_id == 1
    assert result.knock_on is not None
    assert result.knock_on.code == "TD-RUN-003"
    assert result.knock_on.node_id == 2


def test_enrich_adds_row_and_rebuilds_text() -> None:
    error, raw = _cast_error()
    result = enrich_sync(
        error,
        inputs_of={2: (raw,)},
        attribute=False,
        locate=True,
    )
    assert result.root.row_index == 2
    assert "row 2" in result.root.title
    assert result.root.locate_status == "found"


def test_enrich_with_locate_disabled_keeps_status_disabled() -> None:
    error, raw = _cast_error()
    result = enrich_sync(error, inputs_of={2: (raw,)}, attribute=False, locate=False)
    assert result.root.locate_status == "disabled"


def test_enrich_redact_hides_values_keeps_row() -> None:
    error, raw = _cast_error()
    result = enrich_sync(
        error,
        inputs_of={2: (raw,)},
        attribute=False,
        locate=True,
        redact=True,
    )
    assert result.root.row_index == 2
    assert result.root.sample_values == ()
    assert result.root.redacted is True


def test_enrich_never_raises_returns_original() -> None:
    error, _raw = _cast_error()
    result = enrich_sync(error, inputs_of={2: (object(),)}, attribute=False)
    assert result.root.code == "TD-TYP-001"


def test_enrich_job_dataclass_can_run_without_qt() -> None:
    error, raw = _cast_error()
    job = EnrichJob(error=error, inputs_of={2: (raw,)}, attribute=False)
    assert job.locate is True
