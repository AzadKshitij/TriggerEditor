"""ErrorEnricher runs off-thread and posts the result back."""

from __future__ import annotations

import polars as pl

from trigger_designer.core.errors import EnrichJob, ErrorContext, make_error
from trigger_designer.qt.helpers.error_enricher import start_enrichment


def test_enricher_posts_result_without_blocking(qtbot) -> None:
    error = make_error(
        "TD-TYP-001",
        ErrorContext(node_id=1, node_label="Select"),
        column="Amount",
        target="i64",
        target_human="whole numbers",
        value="bad",
        reason="bad value",
    )
    raw = pl.LazyFrame({"Amount": ["1", "bad"]})
    job = EnrichJob(error=error, inputs_of={1: (raw,)}, attribute=False)
    results = []
    start_enrichment(job, results.append, timeout_s=5)
    qtbot.waitUntil(lambda: bool(results), timeout=5000)
    assert results[0].root.row_index == 2
    assert results[0].root.locate_status == "found"
