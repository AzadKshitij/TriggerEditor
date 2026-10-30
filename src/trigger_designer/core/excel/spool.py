"""Frame -> one temporary Parquet file -> bounded batches (Qt-free).

An upstream plan must run exactly once. It is sunk to a compact temp file; every
later pass (statistics, CSV sidecar, sheet rows) reads that file, so memory stays
bounded by the batch size and the plan is never collected twice.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import polars as pl

BATCH_ROWS = 50_000


@dataclass
class Spooled:
    """The spooled frame: ``path`` to the Parquet file, or ``frame`` when Parquet
    cannot hold the data (e.g. Object columns)."""

    schema: dict[str, Any]
    path: str | None = None
    frame: pl.DataFrame | None = None

    def lazy(self) -> pl.LazyFrame:
        if self.path is not None:
            return pl.scan_parquet(self.path)
        assert self.frame is not None
        return self.frame.lazy()

    def height(self) -> int:
        if self.frame is not None:
            return self.frame.height
        return int(self.lazy().select(pl.len()).collect().item())

    def batches(self, size: int = BATCH_ROWS) -> Iterator[pl.DataFrame]:
        if self.frame is not None:
            for start in range(0, self.frame.height, size):
                yield self.frame.slice(start, size)
            return
        # Polars only (no pyarrow): each slice reads the row groups it needs, so
        # memory stays bounded by the batch (and one row group) whatever the size.
        lazy = pl.scan_parquet(self.path)
        offset = 0
        while True:
            batch = lazy.slice(offset, size).collect()
            if batch.height == 0:
                return
            yield batch
            if batch.height < size:
                return
            offset += size


def frame_schema(frame: pl.LazyFrame | pl.DataFrame) -> dict[str, Any]:
    """Column names and dtypes without collecting."""
    return dict(frame.collect_schema())


def spool_parquet(
    frame: pl.LazyFrame | pl.DataFrame, tmp_dir: str, name: str = "spool.parquet"
) -> Spooled:
    """Run ``frame`` once into ``tmp_dir``; returns the :class:`Spooled` handle."""
    schema = frame_schema(frame)
    path = os.path.join(tmp_dir, name)
    eager: pl.DataFrame | None = frame if isinstance(frame, pl.DataFrame) else None
    if eager is None:
        try:
            frame.sink_parquet(path)  # streaming; the plan runs here
            return Spooled(schema, path=path)
        except pl.exceptions.PolarsError:
            eager = frame.collect()  # a plan that cannot stream: run it once, in memory
    try:
        eager.write_parquet(path)
    except pl.exceptions.PolarsError, OSError, TypeError, ValueError:
        if os.path.exists(path):
            os.remove(path)
        return Spooled(schema, frame=eager)
    return Spooled(schema, path=path)
