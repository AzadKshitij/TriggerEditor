"""Sample (``core/audit/sampling.py`` and the node): reproducible draws.

Hand-computed values come from docs/plan/04-audit-test-nodes.md section 4.4 and
were re-derived independently of ``run_sample`` where a test says so.
"""

from __future__ import annotations

import json
import math
import random
from collections import Counter

import polars as pl
import pytest

from tests.support.audit_demo import demo_graph
from tests.support.audit_ledger import make_ledger
from trigger_designer.core.audit import sampling
from trigger_designer.core.audit.common import ROW, AuditConfigError
from trigger_designer.core.audit.sampling import (
    ALGORITHM,
    LOG_COLUMNS,
    SamplingParams,
    SplitMix64,
    criteria,
    derive_seed,
    floyd_positions,
    requested_size,
    run_sample,
    sample_test_summary,
    systematic_positions,
)
from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.widgets.nodes.Audit.sample import TriggerNode_Sample

LEDGER = make_ledger().frame
KEY = ["je_number"]
TOY = [5000, 120, 80, 300, 40, 60, 900, 20, 150, 330]  # plan 4.4 MUS toy


def toy_frame() -> pl.DataFrame:
    return pl.DataFrame({"id": [f"r{i}" for i in range(10)], "amount": TOY})


def draw(frame, **settings):
    """``(sample, not_sampled, log)`` as eager frames."""
    result = run_sample(frame, SamplingParams(**settings))
    sample, rest, log = result.frames
    return sample.collect(), rest.collect(), log


def overall(log: pl.DataFrame) -> dict:
    return log.filter(pl.col("scope") == "overall").row(0, named=True)


def ids(frame: pl.DataFrame, column: str = "je_number") -> list[str]:
    return frame[column].to_list()


def shuffled(frame: pl.DataFrame, seed: int) -> pl.DataFrame:
    order = list(range(frame.height))
    random.Random(seed).shuffle(order)
    return frame[order]


# ---- the generator ------------------------------------------------------------
def test_splitmix64_published_vector() -> None:
    rng = SplitMix64(0)
    assert [rng.next_u64() for _ in range(3)] == [
        0xE220A8397B1DCDAF,
        0x6E789E6AA1B965F4,
        0x06C45D188009454F,
    ]


def test_unit_is_in_the_half_open_interval_and_uses_53_bits() -> None:
    rng = SplitMix64(7)
    values = [rng.unit() for _ in range(2000)]
    assert all(0.0 <= v < 1.0 for v in values)
    assert all((v * (1 << 53)).is_integer() for v in values)
    assert SplitMix64(0).unit() == (0xE220A8397B1DCDAF >> 11) / float(1 << 53)


def test_floyd_known_answers_and_shape() -> None:
    assert floyd_positions(SplitMix64(42), 20, 5) == [0, 5, 10, 13, 19]
    assert floyd_positions(SplitMix64(1), 5, 5) == [0, 1, 2, 3, 4]
    assert floyd_positions(SplitMix64(1), 5, 9) == [0, 1, 2, 3, 4]
    assert floyd_positions(SplitMix64(1), 0, 3) == []
    for seed in range(50):
        got = floyd_positions(SplitMix64(seed), 30, 12)
        assert (
            got == sorted(set(got)) and len(got) == 12 and 0 <= got[0] <= got[-1] < 30
        )


def test_systematic_known_answers() -> None:
    assert systematic_positions(SplitMix64(42), 20, 5) == (
        [2, 6, 10, 14, 18],
        4.0,
        2.9662595150872932,
    )
    assert systematic_positions(SplitMix64(42), 10, 3) == (
        [2, 5, 9],
        3.3333333333333335,
        2.471882929239411,
    )
    assert systematic_positions(SplitMix64(42), 4, 9) == ([0, 1, 2, 3], 1.0, 0.0)


def test_systematic_always_returns_n_distinct_positions() -> None:
    rng = random.Random(20260101)
    for _ in range(200):
        population = rng.randint(1, 400)
        size = rng.randint(1, population)
        positions, interval, start = systematic_positions(
            SplitMix64(rng.randint(0, 2**31)), population, size
        )
        assert len(set(positions)) == size and 0 <= start < interval
        assert positions[0] >= 0 and positions[-1] < population


def test_derived_seeds() -> None:
    assert derive_seed(42, 0) == 14026160589095004880
    assert derive_seed(42, 1) == 8933602108916158448
    assert derive_seed(42, 0) != derive_seed(43, 0)


# ---- the four methods on the reference ledger (plan 4.4) -----------------------
def test_random_reference() -> None:
    sample, rest, log = draw(LEDGER, key_columns=KEY, sample_size=100)
    assert (sample.height, rest.height) == (100, 2313)
    assert ids(sample)[:3] == ["GL-000015", "GL-000038", "GL-000049"]
    row = overall(log)
    assert (row["population_rows"], row["sample_size"], row["requested_size"]) == (
        2413,
        100,
        100,
    )
    assert row["interval"] is None and row["note"] == ""


def test_systematic_reference() -> None:
    sample, rest, log = draw(
        LEDGER, key_columns=KEY, method="systematic", sample_size=100
    )
    assert (sample.height, rest.height) == (100, 2313)
    assert ids(sample)[:3] == ["GL-000004", "GL-000029", "GL-000053"]
    row = overall(log)
    assert row["interval"] == pytest.approx(24.13)
    assert row["start"] == pytest.approx(17.893960524764097, rel=1e-12)


def test_mus_reference() -> None:
    sample, rest, log = draw(
        LEDGER, key_columns=KEY, method="mus", sample_size=50, amount_column="amount"
    )
    assert (sample.height, rest.height) == (50, 2363)
    assert ids(sample)[:3] == ["GL-000055", "GL-000081", "GL-000140"]
    row = overall(log)
    assert row["interval"] == pytest.approx(3468934.663799994, rel=1e-12)
    assert row["start"] == pytest.approx(2572440.1134282183, rel=1e-12)
    assert row["high_value_items"] == 0
    assert row["population_value"] == pytest.approx(173_446_733.19)
    assert row["sample_value"] == pytest.approx(26_253_624.04)
    assert set(sample["sample_basis"]) == {"interval"}


def test_stratified_reference() -> None:
    sample, rest, log = draw(
        LEDGER,
        key_columns=KEY,
        method="stratified",
        amount_column="amount",
        band_edges=[1000, 10000],
        band_sizes=[20, 20, -1],
    )
    assert (sample.height, rest.height) == (870, 1543)
    strata = log.filter(pl.col("scope") == "stratum")
    assert strata["stratum"].to_list() == [1, 2, 3]
    assert strata["population_rows"].to_list() == [828, 755, 830]
    assert strata["sample_size"].to_list() == [20, 20, 830]
    assert overall(log)["sample_value"] == pytest.approx(169_016_858.98)
    assert Counter(sample["sample_stratum"]) == {1: 20, 2: 20, 3: 830}
    assert strata["lower_bound"].to_list() == [None, 1000.0, 10000.0]
    assert strata["upper_bound"].to_list() == [1000.0, 10000.0, None]


def test_percent_size_rounds_up() -> None:
    sample, _rest, log = draw(
        LEDGER, key_columns=KEY, size_kind="percent", sample_percent=10.0
    )
    assert sample.height == 242  # ceil(241.3)
    assert overall(log)["requested_size"] == 242
    params = SamplingParams(size_kind="percent", sample_percent=10.0)
    assert requested_size(params, 30) == 3  # exact, not 3.0000000000000004 -> 4
    assert (
        requested_size(SamplingParams(size_kind="percent", sample_percent=7), 100) == 7
    )
    assert (
        requested_size(SamplingParams(size_kind="percent", sample_percent=0.07), 100000)
        == 70
    )
    assert (
        requested_size(SamplingParams(size_kind="percent", sample_percent=0.01), 5) == 1
    )
    assert requested_size(SamplingParams(size_kind="percent"), 0) == 0


# ---- determinism ----------------------------------------------------------------
@pytest.mark.parametrize("method", ["random", "systematic", "mus"])
def test_same_settings_same_sample_and_a_new_seed_changes_it(method: str) -> None:
    frame = pl.DataFrame(
        {
            "id": [f"r{i:04d}" for i in range(1000)],
            "amount": [i + 1 for i in range(1000)],
        }
    )
    settings = {"key_columns": ["id"], "method": method, "amount_column": "amount"}
    one = draw(frame, sample_size=50, **settings)
    two = draw(frame, sample_size=50, **settings)
    assert one[0].equals(two[0]) and one[1].equals(two[1]) and one[2].equals(two[2])
    other = draw(frame, sample_size=50, seed=43, **settings)
    assert overall(other[2])["seed"] == 43
    if method == "systematic":  # two starts can floor to the same offset
        assert overall(other[2])["start"] != overall(one[2])["start"]
    else:
        assert set(ids(other[0], "id")) != set(ids(one[0], "id"))


@pytest.mark.parametrize("method", ["random", "systematic", "mus", "stratified"])
def test_the_draw_does_not_depend_on_row_order(method: str) -> None:
    settings = {
        "method": method,
        "sample_size": 120,
        "amount_column": "amount",
        "band_edges": [1000, 10000],
        "band_sizes": [15, 15, 40],
    }
    base = draw(LEDGER, key_columns=KEY, **settings)
    expected = set(ids(base[0]))
    seqs = dict(zip(ids(base[0]), base[0]["sample_seq"]))
    for seed in range(5):
        mixed = draw(shuffled(LEDGER, seed), key_columns=KEY, **settings)
        assert set(ids(mixed[0])) == expected
        # The rank is canonical, so it is the same whatever order the rows came in.
        assert dict(zip(ids(mixed[0]), mixed[0]["sample_seq"])) == seqs
        assert mixed[2].equals(base[2])
        # Output rows keep the order the input had.
        order = {v: i for i, v in enumerate(shuffled(LEDGER, seed)["je_number"])}
        positions = [order[v] for v in ids(mixed[0])]
        assert positions == sorted(positions)


def test_the_default_key_is_every_column_and_identical_rows_are_interchangeable() -> (
    None
):
    rows = [("a", 1)] * 6 + [("b", 2)] * 3 + [("c", 3)] * 5 + [("d", None)] * 2
    frame = pl.DataFrame(
        {"x": [r[0] for r in rows], "y": [r[1] for r in rows]},
        schema={"x": pl.String, "y": pl.Int64},
    )
    for method in ("random", "systematic"):
        base = draw(frame, method=method, sample_size=7)
        counts = Counter(zip(base[0]["x"], base[0]["y"]))
        for seed in range(5):
            mixed = draw(shuffled(frame, seed), method=method, sample_size=7)
            assert Counter(zip(mixed[0]["x"], mixed[0]["y"])) == counts
            assert sorted(mixed[0]["sample_seq"]) == sorted(base[0]["sample_seq"])
        assert overall(base[2])["key_columns"] == "(all columns)"


def test_a_tied_key_is_broken_by_the_other_columns() -> None:
    frame = pl.DataFrame({"k": ["a"] * 6 + ["b"] * 6, "v": list(range(12))})
    base = draw(frame, key_columns=["k"], sample_size=5)
    for seed in range(5):
        mixed = draw(shuffled(frame, seed), key_columns=["k"], sample_size=5)
        assert sorted(mixed[0]["v"]) == sorted(base[0]["v"])


def test_null_keys_sort_last() -> None:
    frame = pl.DataFrame({"k": [None, "b", "a", None, "c"], "v": [1, 2, 3, 4, 5]})
    sample, _rest, _log = draw(frame, key_columns=["k"], sample_size=5)
    by_seq = dict(zip(sample["sample_seq"], sample["k"]))
    assert [by_seq[i] for i in (1, 2, 3)] == ["a", "b", "c"]
    assert by_seq[4] is None and by_seq[5] is None


def test_live_and_run_pick_the_same_rows() -> None:
    live = run_sample(LEDGER, SamplingParams(key_columns=KEY), live=True)
    run = run_sample(LEDGER, SamplingParams(key_columns=KEY))
    assert live.frames[0].collect().equals(run.frames[0].collect())
    assert live.extras["live_skipped"] is False


# ---- the log lets a reviewer re-perform the draw -----------------------------------
def test_the_log_is_enough_to_redraw() -> None:
    sample, _rest, log = draw(LEDGER, key_columns=KEY, sample_size=40, seed=7)
    row = overall(log)
    assert (
        json.loads(row["parameters"])
        == SamplingParams(key_columns=KEY, sample_size=40, seed=7).to_dict()
    )
    # Re-perform from the log with plain Python, sharing nothing with run_sample.
    canonical = sorted(LEDGER["je_number"].to_list())
    picks = floyd_positions(
        SplitMix64(row["seed"]), row["population_rows"], row["sample_size"]
    )
    assert sorted(canonical[p] for p in picks) == sorted(ids(sample))
    assert sorted(sample["sample_seq"]) == [p + 1 for p in picks]
    again = SamplingParams.from_dict(json.loads(row["parameters"]))
    assert run_sample(LEDGER, again).frames[0].collect().equals(sample)


def test_systematic_redraw_from_interval_and_start() -> None:
    sample, _rest, log = draw(
        LEDGER, key_columns=KEY, method="systematic", sample_size=60
    )
    row = overall(log)
    expected = [math.floor(row["start"] + i * row["interval"]) + 1 for i in range(60)]
    assert sorted(sample["sample_seq"]) == expected


def test_mus_redraw_from_the_log_interval_and_start() -> None:
    sample, _rest, log = draw(
        toy_frame(),
        key_columns=["id"],
        method="mus",
        sample_size=4,
        amount_column="amount",
    )
    row = overall(log)
    assert ids(sample, "id") == ["r0", "r3", "r6", "r9"]
    assert row["high_value_items"] == 2
    assert row["interval"] == pytest.approx(550.0)
    assert row["start"] == pytest.approx(407.8606833245028, rel=1e-12)
    # Plain-Python re-performance over the items that are not high value.
    high = {
        i
        for i, b in zip(sample["sample_seq"], sample["sample_basis"])
        if b == "high_value"
    }
    assert high == {1, 7}
    remaining = [(i + 1, a) for i, a in enumerate(TOY) if i + 1 not in high]
    cumulative, total, hit = [], 0, []
    for seq, amount in remaining:
        total += amount
        cumulative.append((seq, total))
    for j in range(2):
        point = row["start"] + j * row["interval"]
        hit.append(next(seq for seq, c in cumulative if point < c))
    assert hit == [4, 10]
    basis = dict(zip(sample["sample_seq"], sample["sample_basis"]))
    assert basis == {1: "high_value", 4: "interval", 7: "high_value", 10: "interval"}


# ---- sample sizes (property) ---------------------------------------------------------
def test_sample_size_equals_requested() -> None:
    rng = random.Random(20260101)
    for case in range(100):
        population = rng.randint(1, 300)
        n = rng.randint(1, 400)
        amounts = [round(rng.random() * 1000 + 1, 2) for _ in range(population)]
        if case % 3 == 0:
            amounts[rng.randrange(population)] = 10_000_000.0  # one huge item
        frame = pl.DataFrame(
            {"id": [f"i{k:04d}" for k in range(population)], "amount": amounts}
        )
        base = {
            "key_columns": ["id"],
            "sample_size": n,
            "amount_column": "amount",
            "seed": case,
        }
        for method in ("random", "systematic", "mus"):
            sample, rest, _log = draw(frame, method=method, **base)
            assert sample.height == min(n, population), (case, method)
            assert sample["sample_seq"].n_unique() == sample.height
            assert sample.height + rest.height == population
        edges = [100.0, 500.0]
        sizes = [rng.randint(1, 60), rng.randint(1, 60), rng.choice([-1, 5])]
        sample, _rest, _log = draw(
            frame,
            method="stratified",
            key_columns=["id"],
            amount_column="amount",
            band_edges=edges,
            band_sizes=sizes,
            seed=case,
        )
        members = Counter(1 + sum(a >= e for e in edges) for a in amounts)
        expected = sum(
            members[s] if size == -1 else min(size, members[s])
            for s, size in zip((1, 2, 3), sizes)
        )
        assert sample.height == expected, case


# ---- MUS ---------------------------------------------------------------------------------
def test_mus_toy_certainty_items() -> None:
    sample, rest, log = draw(
        toy_frame(),
        key_columns=["id"],
        method="mus",
        sample_size=4,
        amount_column="amount",
    )
    assert ids(sample, "id") == ["r0", "r3", "r6", "r9"]
    basis = dict(zip(sample["id"], sample["sample_basis"]))
    assert basis == {
        "r0": "high_value",
        "r6": "high_value",
        "r3": "interval",
        "r9": "interval",
    }
    assert rest.height == 6 and "sample_basis" not in rest.columns
    assert overall(log)["sample_value"] == pytest.approx(5000 + 300 + 900 + 330)


def test_mus_item_larger_than_the_rest_still_gives_n_distinct_items() -> None:
    frame = pl.DataFrame(
        {"id": [f"r{i}" for i in range(6)], "amount": [1_000_000, 1, 2, 3, 4, 5]}
    )
    for n in range(1, 7):
        sample, _rest, _log = draw(
            frame,
            key_columns=["id"],
            method="mus",
            sample_size=n,
            amount_column="amount",
        )
        assert sample.height == n
        assert sample.filter(pl.col("id") == "r0").height == 1  # always audited


def test_mus_everything_certain_has_no_interval() -> None:
    sample, _rest, log = draw(
        pl.DataFrame({"id": ["a", "b"], "amount": [10, 10]}),
        key_columns=["id"],
        method="mus",
        sample_size=2,
        amount_column="amount",
    )
    assert sample.height == 2
    row = overall(log)
    assert (
        row["high_value_items"] == 2
        and row["interval"] is None
        and row["start"] is None
    )


def test_mus_zero_negative_and_unreadable_amounts() -> None:
    frame = pl.DataFrame(
        {"id": list("abcdef"), "amount": ["-100", "0", "50", "x", None, "(25)"]}
    )
    sample, rest, log = draw(
        frame, key_columns=["id"], method="mus", sample_size=10, amount_column="amount"
    )
    assert sorted(ids(sample, "id")) == [
        "a",
        "c",
        "f",
    ]  # |-100|, 50, |-25| are eligible
    assert sorted(ids(rest, "id")) == ["b", "d", "e"]
    note = overall(log)["note"]
    assert note.startswith("TD-AUDIT-103: Requested 10 but only 3 rows exist")
    assert "3 rows have a zero or unreadable amount and cannot be selected." in note
    assert overall(log)["population_value"] == pytest.approx(175.0)


def test_mus_with_no_eligible_row_is_an_error() -> None:
    frame = pl.DataFrame({"id": ["a", "b"], "amount": ["0", "n/a"]})
    with pytest.raises(AuditConfigError) as info:
        draw(frame, key_columns=["id"], method="mus", amount_column="amount")
    assert info.value.code == "TD-AUDIT-010"
    assert "'amount'" in str(info.value)
    frame = pl.DataFrame({"id": ["a", "b"], "amount": ["x", None]})
    with pytest.raises(AuditConfigError) as info:
        draw(
            frame,
            key_columns=["id"],
            method="stratified",
            amount_column="amount",
            band_edges=[],
            band_sizes=[1],
        )
    assert info.value.code == "TD-AUDIT-010"


# ---- stratified ---------------------------------------------------------------------------
def test_stratified_edges_zero_and_unreadable() -> None:
    frame = pl.DataFrame(
        {
            "id": [f"r{i}" for i in range(9)],
            "amount": [
                "0",
                "99",
                "100",
                "999.99",
                "1000",
                "-5000",
                "n/a",
                None,
                "2,000",
            ],
        }
    )
    sample, rest, log = draw(
        frame,
        key_columns=["id"],
        method="stratified",
        amount_column="amount",
        band_edges=[100, 1000],
        band_sizes=[-1, -1, -1],
    )
    stratum = dict(zip(sample["id"], sample["sample_stratum"]))
    assert stratum == {
        "r0": 1,
        "r1": 1,  # 0 and 99 are below the first edge
        "r2": 2,
        "r3": 2,  # a value on an edge belongs to the higher stratum
        "r4": 3,
        "r5": 3,
        "r8": 3,  # |-5000| and 2,000
    }
    assert sorted(ids(rest, "id")) == ["r6", "r7"]  # unreadable: in no stratum
    assert (
        "2 rows have an unreadable amount and are in no stratum."
        in overall(log)["note"]
    )


def test_stratified_short_stratum_takes_all_and_says_so() -> None:
    frame = pl.DataFrame({"id": list("abcde"), "amount": [1, 2, 3, 500, 600]})
    sample, _rest, log = draw(
        frame,
        key_columns=["id"],
        method="stratified",
        amount_column="amount",
        band_edges=[100],
        band_sizes=[10, 1],
    )
    assert sample.height == 4
    strata = log.filter(pl.col("scope") == "stratum")
    assert strata["note"].to_list() == [
        "TD-AUDIT-103: Requested 10 but only 3 rows exist; the whole population was selected.",
        "",
    ]
    assert overall(log)["note"].startswith("TD-AUDIT-103")
    assert (
        sample_test_summary(
            log, SamplingParams(method="stratified"), node_id=1, sample_var="v"
        ).code
        == "TD-AUDIT-103"
    )


def test_stratified_without_edges_is_one_stratum() -> None:
    frame = pl.DataFrame({"id": list("abcdef"), "amount": [1, 2, 3, 4, 5, 6]})
    sample, _rest, log = draw(
        frame,
        key_columns=["id"],
        method="stratified",
        amount_column="amount",
        band_edges=[],
        band_sizes=[2],
    )
    assert sample.height == 2 and set(sample["sample_stratum"]) == {1}
    assert log.height == 2


# ---- the log ---------------------------------------------------------------------------------
def test_selection_log_fields() -> None:
    _s, _r, log = draw(LEDGER, key_columns=KEY, sample_size=10)
    assert tuple(log.columns) == LOG_COLUMNS
    assert log.height == 1 and "timestamp" not in log.columns
    row = overall(log)
    assert row["algorithm"] == ALGORITHM == "td-sample-1"
    assert row["scope"] == "overall" and row["stratum"] is None
    assert row["key_columns"] == "je_number" and row["amount_column"] == ""
    assert (row["method"], row["seed"]) == ("random", 42)
    assert row["population_value"] is None and row["sample_value"] is None
    assert log.schema == pl.Schema(sampling.LOG_SCHEMA)
    _s, _r, strat = draw(
        LEDGER,
        key_columns=KEY,
        method="stratified",
        amount_column="amount",
        band_edges=[1000, 10000],
        band_sizes=[1, 1, 1],
    )
    assert (
        strat.height == 4 and strat["scope"].to_list() == ["overall"] + ["stratum"] * 3
    )


def test_value_columns_fill_when_an_amount_column_is_set_for_random() -> None:
    _s, _r, log = draw(
        toy_frame(), key_columns=["id"], sample_size=3, amount_column="amount"
    )
    row = overall(log)
    assert row["population_value"] == pytest.approx(sum(TOY))
    assert 0 < row["sample_value"] <= sum(TOY)


def test_request_larger_than_the_population_selects_everything() -> None:
    sample, rest, log = draw(toy_frame(), key_columns=["id"], sample_size=50)
    assert sample.height == 10 and rest.height == 0
    row = overall(log)
    assert row["requested_size"] == 50 and row["sample_size"] == 10
    assert row["note"] == (
        "TD-AUDIT-103: Requested 50 but only 10 rows exist; the whole population was selected."
    )


def test_empty_and_single_row_populations() -> None:
    empty = pl.DataFrame(
        {"id": [], "amount": []}, schema={"id": pl.String, "amount": pl.Float64}
    )
    for method in ("random", "systematic", "mus", "stratified"):
        sample, rest, log = draw(
            empty,
            key_columns=["id"],
            method=method,
            amount_column="amount",
            band_edges=[],
            band_sizes=[1],
        )
        assert sample.height == 0 and rest.height == 0
        assert overall(log)["population_rows"] == 0 and overall(log)["sample_size"] == 0
    one = pl.DataFrame({"id": ["a"], "amount": [5.0]})
    sample, _rest, log = draw(one, key_columns=["id"], sample_size=3)
    assert sample.height == 1 and "TD-AUDIT-103" in overall(log)["note"]
    summary = sample_test_summary(log, SamplingParams(), node_id=1, sample_var="v")
    assert summary.exception_rate == 1.0 and summary.code == "TD-AUDIT-103"


def test_outputs_keep_input_order_and_add_only_the_documented_columns() -> None:
    sample, rest, _log = draw(shuffled(LEDGER, 3), key_columns=KEY, sample_size=30)
    assert sample.columns == [*LEDGER.columns, "sample_seq"]
    assert rest.columns == LEDGER.columns
    assert ROW not in sample.columns and ROW not in rest.columns
    assert sample.height + rest.height == LEDGER.height
    assert set(ids(sample)).isdisjoint(ids(rest))


def test_criteria_and_summary() -> None:
    params = SamplingParams(key_columns=KEY, sample_size=100)
    _s, _r, log = draw(LEDGER, **params.to_dict())
    summary = sample_test_summary(log, params, node_id=9, sample_var="var_sample_9")
    assert summary.test_id == "audit.sample#9" and summary.test_name == "Sample"
    assert summary.status == "pass" and summary.code is None
    assert (summary.population_rows, summary.exception_rows) == (2413, 100)
    assert summary.exception_rate == pytest.approx(100 / 2413)
    assert summary.message == "Selected 100 of 2,413 rows (random, seed 42)."
    assert summary.criteria == "Random sample of 100 rows, seed 42."
    assert summary.exceptions_var == "var_sample_9"
    assert summary.parameters["seed"] == 42
    assert summary.details["selection_log"] == log.to_dicts()
    assert summary.details["seed"] == 42 and summary.details["interval"] is None
    assert criteria(
        SamplingParams(method="mus", amount_column="amount", sample_size=5)
    ).startswith("Monetary unit sample of 5 rows weighted by |amount|")
    assert "10 % of the rows (242 of 2,413)" in criteria(
        SamplingParams(size_kind="percent"), 2413
    )
    assert "by |amount| (edges 1000, 10000)" in criteria(
        SamplingParams(
            method="stratified",
            amount_column="amount",
            band_edges=[1000, 10000],
            band_sizes=[20, 20, -1],
        )
    )


# ---- validation --------------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("settings", "code", "text"),
    [
        ({"method": "bogus"}, "TD-AUDIT-004", "Sample method must be"),
        ({"seed": -1}, "TD-AUDIT-004", "Seed must be"),
        ({"seed": 2**63}, "TD-AUDIT-004", "Seed must be"),
        ({"size_kind": "x"}, "TD-AUDIT-004", "Sample size kind must be"),
        ({"sample_size": 0}, "TD-AUDIT-004", "Sample size must be 1 or more."),
        (
            {"size_kind": "percent", "sample_percent": 0},
            "TD-AUDIT-004",
            "Sample percent must be above 0 and at most 100.",
        ),
        (
            {"size_kind": "percent", "sample_percent": 100.5},
            "TD-AUDIT-004",
            "Sample percent must be above 0 and at most 100.",
        ),
        ({"key_columns": ["nope"]}, "TD-AUDIT-002", "nope"),
        ({"method": "mus"}, "TD-AUDIT-001", "amount"),
        ({"method": "mus", "amount_column": "nope"}, "TD-AUDIT-002", "nope"),
        ({"amount_column": "nope"}, "TD-AUDIT-002", "nope"),
        (
            {
                "method": "stratified",
                "amount_column": "amount",
                "band_edges": [10, 5],
                "band_sizes": [1, 1, 1],
            },
            "TD-AUDIT-009",
            "Strata edges: values must be 0 or more and strictly increasing.",
        ),
        (
            {
                "method": "stratified",
                "amount_column": "amount",
                "band_edges": [-1],
                "band_sizes": [1, 1],
            },
            "TD-AUDIT-009",
            "Strata edges:",
        ),
        (
            {
                "method": "stratified",
                "amount_column": "amount",
                "band_edges": [10, 20],
                "band_sizes": [1, 1],
            },
            "TD-AUDIT-009",
            "Strata sizes: expected 3 values, found 2.",
        ),
        (
            {
                "method": "stratified",
                "amount_column": "amount",
                "band_edges": [],
                "band_sizes": [0],
            },
            "TD-AUDIT-009",
            "Strata sizes: each size must be 1 or more, or all.",
        ),
        (
            {
                "method": "stratified",
                "amount_column": "amount",
                "band_edges": [],
                "band_sizes": [-2],
            },
            "TD-AUDIT-009",
            "Strata sizes:",
        ),
    ],
)
def test_validation_codes(settings: dict, code: str, text: str) -> None:
    frame = pl.DataFrame({"id": ["a", "b"], "amount": [1, 2]})
    with pytest.raises(AuditConfigError) as info:
        run_sample(frame, SamplingParams(**settings))
    assert info.value.code == code and text in str(info.value)
    assert str(info.value).startswith(f"{code}: ")


def test_size_is_ignored_for_stratified_and_percent_only_checked_when_used() -> None:
    frame = pl.DataFrame({"id": ["a", "b"], "amount": [1, 2]})
    run_sample(
        frame,
        SamplingParams(
            method="stratified",
            amount_column="amount",
            sample_size=0,
            band_edges=[],
            band_sizes=[1],
        ),
    )
    run_sample(frame, SamplingParams(sample_percent=500))  # size_kind is count


def test_reserved_and_nested_columns() -> None:
    for name in ("sample_seq", "sample_stratum", "sample_basis", "__td_row"):
        frame = pl.DataFrame({"id": ["a"], name: [1]})
        with pytest.raises(AuditConfigError) as info:
            run_sample(frame, SamplingParams())
        assert info.value.code == "TD-AUDIT-005"
    nested = pl.DataFrame({"id": ["a", "b"], "xs": [[1], [2]]})
    with pytest.raises(
        AuditConfigError
    ) as info:  # no key: every column orders the rows
        run_sample(nested, SamplingParams())
    assert info.value.code == "TD-AUDIT-003"
    with pytest.raises(AuditConfigError) as info:
        run_sample(nested, SamplingParams(key_columns=["xs"]))
    assert info.value.code == "TD-AUDIT-003"
    unique = run_sample(nested, SamplingParams(key_columns=["id"], sample_size=1))
    assert (
        unique.frames[0].collect().height == 1
    )  # a unique key never needs the list column
    tied = pl.DataFrame({"id": ["a", "a"], "xs": [[1], [2]]})
    with pytest.raises(AuditConfigError) as info:
        run_sample(tied, SamplingParams(key_columns=["id"]))
    assert info.value.code == "TD-AUDIT-003"


def test_a_categorical_key_orders_by_its_text() -> None:
    values = ["pear", "apple", "fig", "apple"]
    frame = pl.DataFrame({"k": values, "v": [1, 2, 3, 4]}).with_columns(
        pl.col("k").cast(pl.Categorical)
    )
    flipped = pl.DataFrame({"k": values[::-1], "v": [4, 3, 2, 1]}).with_columns(
        pl.col("k").cast(pl.Categorical)
    )
    a = draw(frame, key_columns=["k"], sample_size=2)[0]
    b = draw(flipped, key_columns=["k"], sample_size=2)[0]
    assert sorted(a["v"]) == sorted(b["v"])


# ---- live evaluation -----------------------------------------------------------------------------
def test_live_limit_returns_empty_frames_with_a_message(monkeypatch) -> None:
    monkeypatch.setattr(sampling, "LIVE_ROW_LIMIT", 10)
    frame = pl.DataFrame({"id": [f"r{i}" for i in range(25)], "amount": range(25)})
    for source in (frame, frame.lazy()):
        result = run_sample(source, SamplingParams(key_columns=["id"]), live=True)
        sample, rest, log = (
            f.collect() if hasattr(f, "collect") else f for f in result.frames
        )
        assert sample.height == 0 and rest.height == 0
        assert sample.columns == ["id", "amount", "sample_seq"]
        assert result.extras["live_skipped"] is True
        assert overall(log)["population_rows"] == 0
    assert run_sample(frame, SamplingParams(), live=True).extras["message"] == (
        "Population has 25 rows: the sample is drawn when you Run."
    )
    assert run_sample(frame.lazy(), SamplingParams(), live=True).extras["message"] == (
        "Population has more than 10 rows: the sample is drawn when you Run."
    )
    # Run never skips, and a config error still shows live.
    assert (
        run_sample(frame, SamplingParams(sample_size=5)).frames[0].collect().height == 5
    )
    with pytest.raises(AuditConfigError):
        run_sample(frame, SamplingParams(method="nope"), live=True)
    exactly = frame.head(10)
    assert (
        run_sample(exactly, SamplingParams(sample_size=3), live=True)
        .frames[0]
        .collect()
        .height
        == 3
    )


def test_live_does_not_read_a_big_scan(tmp_path) -> None:
    path = tmp_path / "big.csv"
    pl.DataFrame({"a": range(sampling.LIVE_ROW_LIMIT + 5000)}).write_csv(path)
    result = run_sample(pl.scan_csv(path), SamplingParams(key_columns=["a"]), live=True)
    assert result.extras["live_skipped"] is True
    assert result.frames[0].collect().height == 0
    run = run_sample(
        pl.scan_csv(path), SamplingParams(key_columns=["a"], sample_size=25)
    )
    assert run.frames[0].collect().height == 25  # Run still draws the whole file


# ---- the node ----------------------------------------------------------------------------------------
def _ready(frame=LEDGER, **settings):
    window, source, node = demo_graph(frame.lazy(), TriggerNode_Sample)
    for name, value in settings.items():
        setattr(node.content, name, value)
    node.markDirty(True)
    node.eval()
    return window, source, node


def test_node_sockets_variables_and_op_id() -> None:
    _w, _s, node = _ready(key_columns=KEY)
    content = node.content
    assert node.serialize()["op"] == "audit.sample"
    assert [s.socket_type for s in node.outputs] == [3, 3, 1]
    names = content.output_variable_names()
    assert [n.rsplit("_", 1)[0] for n in names] == [
        "var_sample",
        "var_notsampled",
        "var_samplelog",
    ]
    assert content.exceptions_var_name() == names[0]
    assert content.summary_variable_name == names[2]
    assert [o["variable_name"] for o in node.value] == names
    assert isinstance(node.value[2]["data"], pl.DataFrame)


def test_live_value_and_generated_code_agree() -> None:
    _w, source, node = _ready(
        key_columns=KEY, method="mus", amount_column="amount", sample_size=40
    )
    out = node.value
    live = [
        o["data"].collect() if isinstance(o["data"], pl.LazyFrame) else o["data"]
        for o in out
    ]
    namespace = {"var_src": source.frame}
    exec(node.get_code(), {"__name__": "__main__"}, namespace)  # noqa: S102
    for item, expected in zip(out, live):
        got = namespace[item["variable_name"]]
        got = got.collect() if isinstance(got, pl.LazyFrame) else got
        assert got.equals(expected)
    assert isinstance(namespace[out[2]["variable_name"]], pl.DataFrame)
    assert live[0].height == 40 and live[1].height == LEDGER.height - 40
    assert node.get_code() == node.get_code()  # idempotent: no timestamp, no counter


def test_unwired_node_defines_every_output_variable() -> None:
    window = TriggerSubWindow()
    node = TriggerNode_Sample(window.scene)
    namespace: dict = {}
    exec(node.get_code(), {}, namespace)  # noqa: S102
    for name in node.content.output_variable_names():
        assert isinstance(namespace[name], pl.DataFrame)


def test_misconfiguration_fails_in_the_node_and_in_the_run_code() -> None:
    _w, source, node = _ready(key_columns=KEY, method="mus")  # no amount column
    assert node.isInvalid() and node.current_error.code == "TD-AUDIT-001"
    with pytest.raises(AuditConfigError) as info:
        exec(node.get_code(), {}, {"var_src": source.frame})  # noqa: S102
    assert info.value.code == "TD-AUDIT-001"
    node.content.amount_column = "amount"
    node.markDirty(True)
    assert node.eval() is not None and not node.isInvalid()
    node.content.band_edges = [5.0, 1.0]
    node.content.method = "stratified"
    node.content.band_sizes = [1, 1, 1]
    node.markDirty(True)
    node.eval()
    assert node.current_error.code == "TD-AUDIT-009"


def test_run_summary_comes_from_the_log_variable() -> None:
    _w, _s, node = _ready(key_columns=KEY, sample_size=100)
    content = node.content
    content.after_execution({content.summary_variable_name: node.value[2]["data"]})
    summary = content.test_summary
    assert summary.test_id == f"audit.sample#{node.id}"
    assert summary.exceptions_var == content.output_variable_names()[0]
    assert summary.exception_rows == 100 and summary.details["seed"] == 42
    content.test_summary = None
    content.after_execution({})
    assert content.test_summary is None
    # A stratified log has several rows; the summary still builds.
    content.method, content.amount_column = "stratified", "amount"
    content.band_edges, content.band_sizes = [1000.0], [5, 5]
    node.markDirty(True)
    node.eval()
    assert content.test_summary.details["selection_log"][1]["scope"] == "stratum"
    assert content.test_summary.exception_rows == 10


def test_live_summary_text_and_the_skip_message(monkeypatch) -> None:
    _w, _s, node = _ready(key_columns=KEY, method="systematic", sample_size=100)
    content = node.content
    assert content.test_summary.exception_rows == 100
    assert content.summary_text().startswith(
        "Selected 100 of 2,413 rows (systematic, seed 42). Interval 24.13."
    )
    monkeypatch.setattr(sampling, "LIVE_ROW_LIMIT", 100)
    node.markDirty(True)
    node.eval()
    expected = "Population has more than 100 rows: the sample is drawn when you Run."
    assert content.test_summary is None
    assert content.summary_text() == expected
    assert expected in node._node_tooltip()
    assert node.value[0]["data"].collect().height == 0
    monkeypatch.setattr(sampling, "LIVE_ROW_LIMIT", 200_000)
    node.markDirty(True)
    node.eval()
    assert content.summary_text().startswith("Selected 100")


def test_state_round_trips_and_old_files_take_defaults() -> None:
    _w, _s, node = _ready(key_columns=KEY)
    content = node.content
    content.method = "stratified"
    content.seed = 2**40
    content.band_edges = [1000.0, 10000.0]
    content.band_sizes = [20, 20, -1]
    content.amount_column = "amount"
    data = json.loads(json.dumps(content.serialize()))
    other = TriggerNode_Sample(TriggerSubWindow().scene)
    other.content.deserialize(dict(data))
    assert other.content.params() == content.params()
    other.content.deserialize({})
    assert other.content.params() == SamplingParams()


def test_core_module_is_registered_and_lazy() -> None:
    from trigger_designer.core.node_configuration import (
        NODE_REGISTRIES,
        AuditNodes,
        NodeTypes,
    )
    from trigger_designer.qt.widgets.nodes import _LAZY_NODE_SPECS

    assert NODE_REGISTRIES[NodeTypes.AUDIT][AuditNodes.SAMPLE] is TriggerNode_Sample
    spec = next(s for s in _LAZY_NODE_SPECS if s["module_path"] == "Audit.sample")
    assert spec["node_code"] == AuditNodes.SAMPLE
    assert (spec["node_title"], spec["icon"]) == (
        TriggerNode_Sample.node_title,
        TriggerNode_Sample.icon,
    )
