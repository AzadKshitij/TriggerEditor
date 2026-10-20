"""Frame comparison helpers for workflow goldens.

Frozen expectations live in ``tests/e2e/fixtures/expected`` (see
``tests/support/corpus.py`` for why). Comparison is about values and column
identity: dtypes are ignored because a CSV round-trip re-infers them, and row
order is compared unless a case marks a golden order-insensitive, because
several workflows (sort, running total, split) exist to fix an order.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path

import polars as pl
from polars.testing import assert_frame_equal

#: Frozen E2E expectations, regenerated with ``TRIGGER_UPDATE_E2E_GOLDENS=1``.
GOLDEN_DIR = Path(__file__).resolve().parents[1] / "e2e" / "fixtures" / "expected"
UPDATE_ENV = "TRIGGER_UPDATE_E2E_GOLDENS"


def read_frame(path: Path | str) -> pl.DataFrame:
    """Read a CSV/JSON file the app wrote.

    Old exports from a pandas preview may carry a leading index column the app
    never writes (an empty name or ``Unnamed: 0``); dropping it compares the
    data the workflow produced.
    """
    path = Path(path)
    if not path.exists():
        raise AssertionError(f"expected output file does not exist: {path}")
    if path.suffix.lower() == ".json":
        return pl.read_json(path)
    frame = pl.read_csv(path, infer_schema_length=None)
    if frame.width and _is_index_column(frame.columns[0]):
        frame = frame.drop(frame.columns[0])
    return frame


def _is_index_column(name: str) -> bool:
    return name == "" or name.startswith("Unnamed:")


def assert_frames_match(
    actual: pl.DataFrame,
    expected: pl.DataFrame,
    *,
    check_dtypes: bool = False,
    check_column_order: bool = True,
    check_row_order: bool = True,
) -> None:
    """Assert two frames describe the same table or fail with a useful diff."""
    actual = _materialize(actual)
    expected = _materialize(expected)
    assert_frame_equal(
        actual,
        expected,
        check_dtypes=check_dtypes,
        check_column_order=check_column_order,
        check_row_order=check_row_order,
    )


def assert_frame_golden(
    frame: pl.DataFrame | pl.LazyFrame,
    name: str,
    *,
    sort_by: Sequence[str] | None = None,
) -> None:
    """Compare a produced frame with the frozen expectation ``name``.

    ``sort_by`` names the columns to sort both frames by first, for goldens
    whose order is not part of the contract (a multi-threaded join). Set
    ``TRIGGER_UPDATE_E2E_GOLDENS=1`` to rewrite the expectation from this run
    instead - the only sanctioned way to change an E2E golden, so the diff
    shows up in review.
    """
    golden = GOLDEN_DIR / f"{name}.csv"
    frame = _materialize(frame)
    if sort_by is not None:
        frame = frame.sort(sort_by)
    if os.environ.get(UPDATE_ENV) == "1":
        golden.parent.mkdir(parents=True, exist_ok=True)
        frame.write_csv(golden)
        print(f"[goldens] wrote {golden}")
        return
    if not golden.exists():
        raise AssertionError(f"missing golden {golden}; regenerate with {UPDATE_ENV}=1")
    expected = pl.read_csv(golden, infer_schema_length=None)
    if sort_by is not None:
        expected = expected.sort(sort_by)
    assert_frames_match(frame, expected)


def _materialize(frame: pl.DataFrame | pl.LazyFrame) -> pl.DataFrame:
    if isinstance(frame, pl.LazyFrame):
        return frame.collect()
    return frame
