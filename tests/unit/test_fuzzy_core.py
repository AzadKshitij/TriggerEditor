"""Fuzzy Match core: hand-computed expectations (docs/plan/07 section 7.2)."""

from __future__ import annotations

import ast
import random
from pathlib import Path

import polars as pl
import pytest

from trigger_designer.core.errors.catalogue import CATALOGUE
from trigger_designer.core.shaping import fuzzy
from trigger_designer.core.shaping.common import ERROR_CODES, ShapingError

FL = pl.DataFrame(
    {
        "Vendor": [
            "ACME Corp.",
            "Globex, Inc",
            "Initech LLC",
            "Umbrella Ltd",
            "Hooli",
            None,
        ],
        "id": [1, 2, 3, 4, 5, 6],
    }
)
FRR = pl.DataFrame(
    {
        "Supplier": [
            "Acme Corporation",
            "GLOBEX INC.",
            "Initec",
            "Umbrela Limited",
            "Pied Piper",
            "Hooly",
        ],
        "ref": list("abcdef"),
    }
)
BASE = {"left_column": "Vendor", "right_column": "Supplier"}


def _run(left, right, **settings):
    return fuzzy.apply_fuzzy(left, right, {**BASE, **settings})


def _names(values: list) -> pl.DataFrame:
    return pl.DataFrame({"Vendor": values, "id": list(range(1, len(values) + 1))})


def _suppliers(values: list) -> pl.DataFrame:
    return pl.DataFrame(
        {"Supplier": values, "ref": [f"r{i}" for i in range(1, len(values) + 1)]}
    )


def code_of(fn, *args, **kwargs) -> str:
    with pytest.raises(ShapingError) as info:
        fn(*args, **kwargs)
    return info.value.code


def test_reference_example_jaro_winkler() -> None:
    result = _run(FL, FRR)
    assert result.matched.columns == [
        "Match_ID",
        "Match_Score",
        "Vendor",
        "id",
        "Supplier",
        "ref",
    ]
    assert result.matched.select("Match_ID", "Match_Score", "id", "ref").rows() == [
        (1, 1.0, 1, "a"),
        (2, 1.0, 2, "b"),
        (3, 0.9714, 3, "c"),
        (4, 0.975, 4, "d"),
        (5, 0.92, 5, "f"),
    ]
    assert result.left_unmatched.rows() == [(None, 6)]
    assert result.right_unmatched.rows() == [("Pied Piper", "e")]


def test_levenshtein_ratio_without_blocking() -> None:
    result = _run(FL, FRR, blocking="none", threshold=0.8, algorithm="levenshtein")
    assert result.matched["Match_Score"].to_list() == [1.0, 1.0, 0.8571, 0.875, 0.8]


def test_first_token_blocking_needs_a_shared_first_word() -> None:
    # "initech" vs "initec" and "umbrella" vs "umbrela" differ in the first word.
    result = _run(FL, FRR, blocking="first_token")
    assert result.matched["id"].to_list() == [1, 2]


def test_threshold_is_inclusive_and_drops_lower_pairs() -> None:
    # levenshtein("hooli", "hooly") ratio is exactly 0.8
    kept = _run(FL, FRR, blocking="none", algorithm="levenshtein", threshold=0.8)
    assert 5 in kept.matched["id"].to_list()
    dropped = _run(FL, FRR, blocking="none", algorithm="levenshtein", threshold=0.81)
    assert 5 not in dropped.matched["id"].to_list()


def test_normalisation_ignores_case_punctuation_and_suffix_words() -> None:
    left = _names(["The  ACME, Inc.", "Foo-Bar"])
    right = _suppliers(["the acme", "foo bar LLC"])
    result = _run(left, right)
    assert result.matched["Match_Score"].to_list() == [1.0, 1.0]
    # without suffix stripping "foo bar llc" is no longer identical
    plain = _run(left, right, strip_suffixes=False)
    scores = plain.matched["Match_Score"].to_list()
    assert scores[0] < 1.0 and scores[1] < 1.0


def test_unicode_letters_are_kept() -> None:
    result = _run(_names(["Café Zoë"]), _suppliers(["café zoë"]))
    assert result.matched["Match_Score"].to_list() == [1.0]


def test_null_empty_and_punctuation_only_text_never_match() -> None:
    left = _names([None, "", "...", "Co Ltd", "real name"])
    right = _suppliers([None, "", "...", "Inc", "real name"])
    result = _run(left, right, threshold=0.01, blocking="none")
    assert result.matched.select("id", "ref").rows() == [(5, "r5")]
    assert sorted(result.left_unmatched["id"].to_list()) == [1, 2, 3, 4]
    assert sorted(result.right_unmatched["ref"].to_list()) == ["r1", "r2", "r3", "r4"]


def test_levenshtein_of_two_empty_strings_is_excluded() -> None:
    result = _run(
        _names(["", "ab"]),
        _suppliers(["", "ab"]),
        algorithm="levenshtein",
        blocking="none",
        threshold=0.5,
    )
    assert result.matched.select("id", "ref").rows() == [(2, "r2")]


def test_one_to_one_leaves_a_lower_ranked_left_row_unmatched() -> None:
    left = _names(["acme", "acmee"])
    right = _suppliers(["acme"])
    result = _run(left, right, threshold=0.8)
    # the right row goes to the exact match; the near match has nothing left
    assert result.matched.select("id", "ref", "Match_Score").rows() == [(1, "r1", 1.0)]
    assert result.left_unmatched["id"].to_list() == [2]
    assert result.right_unmatched.is_empty()


def test_one_to_one_chooses_the_global_best_pairing() -> None:
    left = _names(["alpha one", "alpha onf"])
    right = _suppliers(["alpha onf"])
    result = _run(left, right, threshold=0.5)
    assert result.matched["id"].to_list() == [2]


def test_all_pairs_vs_best_per_left() -> None:
    left = _names(["acme"])
    right = _suppliers(["acme", "acmee"])
    every = _run(left, right, assignment="all_pairs", threshold=0.8)
    best = _run(left, right, assignment="best_per_left", threshold=0.8)
    assert every.matched.select("Match_ID", "ref").rows() == [(1, "r1"), (2, "r2")]
    assert best.matched.select("Match_ID", "ref").rows() == [(1, "r1")]
    # a right row used by no pair is unmatched; one used is not
    assert best.right_unmatched["ref"].to_list() == ["r2"]
    assert every.right_unmatched.is_empty()


def test_best_per_left_may_reuse_one_right_row() -> None:
    left = _names(["acme", "acmee"])
    right = _suppliers(["acme"])
    result = _run(left, right, assignment="best_per_left", threshold=0.8)
    assert result.matched["id"].to_list() == [1, 2]
    assert result.matched["ref"].to_list() == ["r1", "r1"]


def test_ties_break_by_left_then_right_position() -> None:
    left = _names(["same", "same"])
    right = _suppliers(["same", "same"])
    result = _run(left, right)
    assert result.matched.select("Match_ID", "id", "ref").rows() == [
        (1, 1, "r1"),
        (2, 2, "r2"),
    ]


def test_match_id_is_numbered_in_left_order() -> None:
    left = _names(["zeta co", "alpha co", "mid co"])
    right = _suppliers(["mid co", "zeta co", "alpha co"])
    result = _run(left, right)
    assert result.matched.select("Match_ID", "id", "ref").rows() == [
        (1, 1, "r2"),
        (2, 2, "r3"),
        (3, 3, "r1"),
    ]


def test_block_columns_must_match_exactly_trimmed_and_case_folded() -> None:
    left = pl.DataFrame(
        {
            "Vendor": ["acme", "acme", "acme", "acme"],
            "Region": ["North", " south ", None, ""],
            "id": [1, 2, 3, 4],
        }
    )
    right = pl.DataFrame(
        {
            "Supplier": ["acme", "acme"],
            "Area": ["NORTH", "South"],
            "ref": ["n", "s"],
        }
    )
    result = _run(
        left,
        right,
        block_columns=[{"left": "Region", "right": "Area"}],
        assignment="all_pairs",
    )
    assert result.matched.select("id", "ref").rows() == [(1, "n"), (2, "s")]
    assert result.left_unmatched["id"].to_list() == [3, 4]


def test_half_filled_block_column_is_ignored() -> None:
    left, right = _names(["acme"]), _suppliers(["acme"])
    result = _run(left, right, block_columns=[{"left": "Vendor", "right": ""}])
    assert result.matched.height == 1


def test_block_column_must_exist_on_the_right_side() -> None:
    assert (
        code_of(
            _run,
            _names(["a"]),
            _suppliers(["a"]),
            block_columns=[{"left": "Vendor", "right": "Nope"}],
        )
        == "TD-SHAPE-003"
    )


def test_prefix_length_controls_which_pairs_are_compared() -> None:
    left, right = _names(["abcdef"]), _suppliers(["abxdef"])
    assert _run(left, right, prefix_length=2).matched.height == 1
    assert _run(left, right, prefix_length=3, threshold=0.5).matched.height == 0
    assert (
        _run(
            left, right, blocking="none", prefix_length=3, threshold=0.5
        ).matched.height
        == 1
    )


def test_name_clashes_are_renamed() -> None:
    left = pl.DataFrame({"name": ["acme"], "Match_Score": ["x"], "k": [1]})
    right = pl.DataFrame({"name": ["acme"], "Match_Score": ["y"], "k": [2]})
    result = fuzzy.apply_fuzzy(
        left, right, {"left_column": "name", "right_column": "name"}
    )
    assert result.matched.columns == [
        "Match_ID",
        "Match_Score",
        "name",
        "Match_Score_2",
        "k",
        "name_right",
        "Match_Score_3",
        "k_right",
    ]
    assert result.matched.row(0) == (1, 1.0, "acme", "x", 1, "acme", "y", 2)


def test_non_text_columns_are_compared_as_text() -> None:
    left = pl.DataFrame({"Vendor": [12345, 678]})
    right = pl.DataFrame({"Supplier": ["12345", "999"]})
    result = _run(left, right)
    assert result.matched.select("Vendor", "Supplier").rows() == [(12345, "12345")]


def test_zero_rows_give_typed_empty_outputs() -> None:
    left = FL.head(0)
    right = FRR.head(0)
    for blocking in ("prefix", "first_token", "none"):
        result = _run(left, right, blocking=blocking)
        assert result.matched.is_empty()
        assert result.matched.schema["Match_ID"] == pl.Int64
        assert result.matched.schema["Match_Score"] == pl.Float64
        assert result.matched.schema["Vendor"] == pl.String
        assert result.matched.schema["ref"] == pl.String
        assert result.left_unmatched.schema == FL.schema
    only_right = _run(FL.head(0), FRR)
    assert only_right.right_unmatched.height == FRR.height
    only_left = _run(FL, FRR.head(0))
    assert only_left.left_unmatched.height == FL.height


def test_no_pair_above_threshold_is_all_unmatched() -> None:
    result = _run(_names(["aaa"]), _suppliers(["aaz"]), threshold=1.0)
    assert result.matched.is_empty()
    assert result.left_unmatched.height == 1 and result.right_unmatched.height == 1


def test_inputs_may_be_lazy_and_the_same_frame() -> None:
    names = pl.DataFrame({"n": ["acme corp", "globex"], "i": [1, 2]})
    result = fuzzy.apply_fuzzy(
        names.lazy(), names.lazy(), {"left_column": "n", "right_column": "n"}
    )
    assert result.matched.select("i", "i_right").rows() == [(1, 1), (2, 2)]


def test_run_node_returns_three_lazy_frames_equal_to_apply() -> None:
    outputs = fuzzy.run_node([FL.lazy(), FRR.lazy()], dict(BASE))
    assert len(outputs) == 3 and all(isinstance(o, pl.LazyFrame) for o in outputs)
    direct = _run(FL, FRR)
    assert outputs[0].collect().equals(direct.matched)
    assert outputs[1].collect().equals(direct.left_unmatched)
    assert outputs[2].collect().equals(direct.right_unmatched)


def test_run_node_validates_like_the_live_path() -> None:
    assert code_of(fuzzy.run_node, [FL, FRR], {}) == "TD-SHAPE-001"
    assert (
        code_of(fuzzy.run_node, [FL, FRR], {**BASE, "threshold": 0}) == "TD-SHAPE-004"
    )


# ---- errors ---------------------------------------------------------------
def test_missing_column_settings_are_001() -> None:
    assert code_of(fuzzy.apply_fuzzy, FL, FRR, {}) == "TD-SHAPE-001"
    assert code_of(fuzzy.apply_fuzzy, FL, FRR, {"left_column": "Vendor"}) == (
        "TD-SHAPE-001"
    )
    assert code_of(fuzzy.apply_fuzzy, FL, FRR, {"right_column": "Supplier"}) == (
        "TD-SHAPE-001"
    )


def test_unknown_column_is_003_on_either_side() -> None:
    assert code_of(_run, FL, FRR, left_column="Nope") == "TD-SHAPE-003"
    assert code_of(_run, FL, FRR, right_column="Nope") == "TD-SHAPE-003"
    # the left name does not exist on the right input and vice versa
    assert code_of(_run, FRR, FL) == "TD-SHAPE-003"


@pytest.mark.parametrize(
    "settings",
    [
        {"threshold": 0},
        {"threshold": -0.1},
        {"threshold": 1.01},
        {"threshold": "high"},
        {"prefix_length": 0},
        {"prefix_length": 11},
        {"algorithm": "soundex"},
        {"blocking": "magic"},
        {"assignment": "many"},
        {"block_columns": [{"left": "Vendor", "right": "Supplier"}] * 6},
    ],
)
def test_out_of_range_settings_are_004(settings: dict) -> None:
    assert code_of(_run, FL, FRR, **settings) == "TD-SHAPE-004"


def test_threshold_of_exactly_one_is_allowed() -> None:
    assert _run(FL, FRR, threshold=1.0).matched.height == 2


def test_too_many_candidate_pairs_is_081_before_scoring(monkeypatch) -> None:
    def boom(*_args, **_kwargs):
        raise AssertionError("scored")

    monkeypatch.setattr(fuzzy, "score_pairs", boom)
    monkeypatch.setattr(fuzzy, "MAX_CANDIDATE_PAIRS", 3)
    left, right = _names(["acme"] * 2), _suppliers(["acme"] * 2)
    assert code_of(_run, left, right) == "TD-SHAPE-081"


def test_hundred_thousand_by_hundred_thousand_is_081() -> None:
    left = pl.DataFrame({"Vendor": ["a" + str(i) for i in range(100_000)]})
    right = pl.DataFrame({"Supplier": ["a" + str(i) for i in range(100_000)]})
    assert code_of(_run, left, right, prefix_length=1) == "TD-SHAPE-081"


def test_081_message_names_the_count_and_limit() -> None:
    left, right = _names(["acme"] * 3), _suppliers(["acme"] * 3)
    original = fuzzy.MAX_CANDIDATE_PAIRS
    fuzzy.MAX_CANDIDATE_PAIRS = 5
    try:
        with pytest.raises(ShapingError) as info:
            _run(left, right)
    finally:
        fuzzy.MAX_CANDIDATE_PAIRS = original
    assert "9 possible pairs (limit 5)" in info.value.detail


def test_unblocked_comparison_of_large_inputs_is_082() -> None:
    left = pl.DataFrame({"Vendor": [f"n{i}" for i in range(1001)]})
    right = pl.DataFrame({"Supplier": [f"n{i}" for i in range(1001)]})
    assert code_of(_run, left, right, blocking="none") == "TD-SHAPE-082"
    # 1000 x 1000 is exactly the limit and is allowed
    left, right = left.head(1000), right.head(1000)
    assert _run(left, right, blocking="none", threshold=1.0).matched.height == 1000


def test_new_codes_are_registered_in_both_places() -> None:
    for code in ("TD-SHAPE-081", "TD-SHAPE-082"):
        assert code in ERROR_CODES
        assert code in CATALOGUE


# ---- properties -----------------------------------------------------------
def test_one_to_one_never_reuses_a_row_and_is_deterministic() -> None:
    rng = random.Random(7)
    pool = ["acme", "acne", "acre", "ache", "acmee", "acm", "beta", "betta", "bet"]
    for _ in range(25):
        left = _names([rng.choice(pool) for _ in range(rng.randint(1, 12))])
        right = _suppliers([rng.choice(pool) for _ in range(rng.randint(1, 12))])
        first = _run(left, right, threshold=0.6)
        again = _run(left, right, threshold=0.6)
        assert first.matched.equals(again.matched)
        assert first.matched["id"].is_unique().all()
        assert first.matched["ref"].is_unique().all()
        assert first.matched["Match_Score"].min() is None or (
            first.matched["Match_Score"].min() >= 0.6
        )
        used_left = set(first.matched["id"].to_list())
        assert used_left.isdisjoint(first.left_unmatched["id"].to_list())
        assert len(used_left) + first.left_unmatched.height == left.height
        assert first.matched.height + first.right_unmatched.height == right.height


def test_unmatched_outputs_keep_input_columns_and_order() -> None:
    left = pl.DataFrame({"Vendor": ["zzz", "yyy", "acme"], "extra": [1.5, 2.5, 3.5]})
    right = pl.DataFrame({"Supplier": ["acme", "qqq", "ppp"], "n": [1, 2, 3]})
    result = _run(left, right)
    assert result.left_unmatched.columns == ["Vendor", "extra"]
    assert result.left_unmatched["Vendor"].to_list() == ["zzz", "yyy"]
    assert result.right_unmatched["Supplier"].to_list() == ["qqq", "ppp"]


def test_core_has_no_qt_import() -> None:
    source = Path(fuzzy.__file__).read_text(encoding="utf-8")
    imported: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert not imported & {"qtpy", "PyQt5", "PyQt6", "PySide2", "PySide6"}
    assert "trigger_designer.qt" not in source
