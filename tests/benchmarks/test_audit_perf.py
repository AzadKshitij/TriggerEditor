"""Audit test performance budgets (docs/plan/04-audit-test-nodes.md section 7.9).

Opt-in: ``pytest tests/benchmarks/test_audit_perf.py --run-benchmarks -s``.
One million synthetic ledger rows are built in memory; each audit test must
finish (every output frame collected) within ``BUDGET_S`` seconds. The
``AUDIT_PERF_ROWS`` environment variable scales the table down for a quick look.
"""

from __future__ import annotations

import os
import time

import numpy as np
import polars as pl
import pytest

from trigger_designer.core.audit.benford import BenfordParams, run_benford
from trigger_designer.core.audit.duplicates import DuplicatesParams, run_duplicates
from trigger_designer.core.audit.gaps import GapsParams, run_gaps
from trigger_designer.core.audit.risk_filters import RiskParams, run_risk_filters
from trigger_designer.core.audit.sampling import SamplingParams, run_sample

ROWS = int(os.environ.get("AUDIT_PERF_ROWS", "1000000"))
BUDGET_S = 10.0
VENDORS = 20_000
INVOICES = 50


@pytest.fixture(scope="module")
def ledger() -> pl.LazyFrame:
    rng = np.random.default_rng(1)
    days = (np.arange(ROWS) % 28).astype("timedelta64[D]")
    dates = (np.datetime64("2026-01-01") + days).astype(str)
    frame = pl.DataFrame(
        {
            "je": pl.Series(np.arange(ROWS)).cast(pl.String).str.zfill(7),
            "vendor": pl.Series(rng.integers(0, VENDORS, ROWS)).cast(pl.String),
            "inv": pl.Series(rng.integers(0, INVOICES, ROWS)).cast(pl.String),
            "amount": pl.Series(rng.lognormal(6.0, 1.5, ROWS)).round(2).cast(pl.String),
            "date": pl.Series(dates),
            "desc": pl.Series(
                rng.choice(["payment", "accrual", "reversal", "adjustment"], ROWS)
            ),
            "src": pl.Series(rng.choice(["manual", "auto", "upload"], ROWS)),
        }
    ).with_columns(("JE-" + pl.col("je")).alias("je"))
    return frame.lazy()


def _run(runner, lf: pl.LazyFrame, params) -> pl.DataFrame:
    """Run one test and collect every output; returns the exceptions-or-first frame."""
    started = time.perf_counter()
    result = runner(lf, params)
    frames = [
        f.collect(engine="streaming") if isinstance(f, pl.LazyFrame) else f
        for f in result.frames
    ]
    elapsed = time.perf_counter() - started
    print(f"\n  {runner.__name__} {type(params).__name__}: {elapsed:.2f} s")
    assert elapsed < BUDGET_S, f"{elapsed:.1f} s is over the {BUDGET_S:.0f} s budget"
    return frames[0]


@pytest.mark.benchmark
def test_duplicates_exact(ledger) -> None:
    params = DuplicatesParams(key_columns=["vendor", "inv", "amount"])
    assert _run(run_duplicates, ledger, params).height >= 0


@pytest.mark.benchmark
def test_duplicates_near_with_tolerance_and_window(ledger) -> None:
    params = DuplicatesParams(
        key_columns=["vendor", "inv"],
        mode="near",
        amount_column="amount",
        tolerance=0.5,
        date_column="date",
        window_days=3,
    )
    assert _run(run_duplicates, ledger, params).height > 0


@pytest.mark.benchmark
def test_gaps_prefixed(ledger) -> None:
    params = GapsParams(sequence_column="je", mode="prefixed")
    assert _run(run_gaps, ledger, params).height >= 0


@pytest.mark.benchmark
def test_benford_first_two_digits(ledger) -> None:
    params = BenfordParams(amount_column="amount", digits=2)
    assert _run(run_benford, ledger, params).height == 90


@pytest.mark.benchmark
@pytest.mark.parametrize(
    ("label", "method", "key_columns"),
    [
        ("random, unique key", "random", ["je"]),
        ("MUS, unique key", "mus", ["je"]),
        ("random, default all-columns key", "random", []),
    ],
)
def test_sample(ledger, label, method, key_columns) -> None:
    params = SamplingParams(
        method=method,
        key_columns=key_columns,
        amount_column="amount" if method == "mus" else "",
        sample_size=1000,
    )
    print(f"\n  sample: {label}")
    assert _run(run_sample, ledger, params).height > 0


@pytest.mark.benchmark
def test_risk_filters_five_tests(ledger) -> None:
    params = RiskParams(
        date_column="date",
        amount_column="amount",
        description_column="desc",
        manual_column="src",
        weekend=True,
        round_amount=True,
        just_below_limit=True,
        approval_limits=[5000],
        keyword=True,
        keywords=["reversal", "adjustment"],
        manual_journal=True,
    )
    assert _run(run_risk_filters, ledger, params).height > 0
