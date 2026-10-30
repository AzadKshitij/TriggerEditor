"""The synthetic ledger every audit-node test builds on is exact and deterministic."""

from __future__ import annotations

import polars as pl

from tests.support.audit_ledger import GL_ROWS, ROWS, make_ledger


def test_shape_and_planted_counts() -> None:
    ledger = make_ledger()
    assert ledger.frame.shape == (ROWS, 9) and ROWS == 2413
    assert ledger.gl.height == GL_ROWS == 2013 and ledger.ap.height == 400
    assert set(ledger.frame.schema.values()) == {pl.String}
    assert {k: len(v) for k, v in ledger.planted.items()} == {
        "weekend": 15,
        "holiday": 4,
        "round": 20,
        "just_below": 13,
        "keyword": 9,
        "after_period": 7,
        "manual": 25,
        "triple": 1,
        "dup_sources": 22,
    }


def test_deterministic_and_seed_sensitive() -> None:
    assert make_ledger().frame.equals(make_ledger().frame)
    assert not make_ledger(seed=1).frame.equals(make_ledger().frame)


def test_exact_duplicate_reference_numbers() -> None:
    frame = make_ledger().frame
    groups = (
        frame.group_by(["vendor", "invoice_no", "amount"])
        .len()
        .filter(pl.col("len") > 1)
    )
    assert groups.height == 17 and groups["len"].sum() == 36


def test_sequence_gaps_in_the_gl_series() -> None:
    gl = make_ledger().gl
    numbers = set(gl["je_number"].str.slice(3).cast(pl.Int64).to_list())
    missing = set(range(1, max(numbers) + 1)) - numbers
    assert missing == set(range(1000, 1010)) | {1500} | set(range(1800, 1803))


def test_write_csv_writes_all_three_files(tmp_path) -> None:
    paths = make_ledger().write_csv(tmp_path / "out")
    assert set(paths) == {"all", "gl", "ap"}
    heights = {k: pl.read_csv(v, infer_schema=False).height for k, v in paths.items()}
    assert heights == {"all": 2413, "gl": 2013, "ap": 400}
