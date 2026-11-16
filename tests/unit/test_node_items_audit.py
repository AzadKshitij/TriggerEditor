"""The audit schema fragments and examples (``node_items/audit.py``) against the code.

Fragments must reach ``describe_op``. Every list must say what it holds, every
setting must have a type, and every choice list must equal the core constant it
copies. Each example must pass the authoring validator and really run through its
audit function (Qt-free, the way the node's generated code calls it) on a small
frame.
"""

from __future__ import annotations

import datetime as dt

import polars as pl
import pytest

from trigger_designer.core.audit import (
    benford,
    duplicates,
    gaps,
    risk_filters,
    sampling,
)
from trigger_designer.core.audit.common import SUPPORTED_DATE_FORMATS
from trigger_designer.core.authoring.validate import validate_value
from trigger_designer.core.headless import node_spec as ns
from trigger_designer.core.headless.node_items import audit as items

pytestmark = pytest.mark.unit

AUDIT_OPS = sorted(op for op in ns.SETTINGS_SOURCES if op.startswith("audit."))

#: Every choice list in PROPS, with the core constant it copies.
ENUM_SOURCES = {
    ("audit.duplicates", "mode"): duplicates.MODES,
    ("audit.duplicates", "tolerance_kind"): duplicates.TOLERANCE_KINDS,
    ("audit.duplicates", "date_format"): SUPPORTED_DATE_FORMATS,
    ("audit.gaps", "mode"): gaps.MODES,
    ("audit.gaps", "date_format"): SUPPORTED_DATE_FORMATS,
    ("audit.sample", "method"): sampling.METHODS,
    ("audit.sample", "size_kind"): sampling.SIZE_KINDS,
    ("audit.risk_filters", "date_format"): SUPPORTED_DATE_FORMATS,
}

#: Settings that hold a date, written as YYYY-MM-DD (the core's ISO check).
ISO_DATE_SETTINGS = [
    ("audit.gaps", "holidays"),
    ("audit.risk_filters", "holidays"),
    ("audit.risk_filters", "period_end"),
]


def _frame() -> pl.DataFrame:
    """Six journal lines. INV-003 is repeated, 2024-03-04 has no entry, 19999 sits
    just under the 20,000 approval limit, 20000 and 30000 are round, and 2024-03-02
    and 2024-03-03 fall on a weekend."""
    return pl.DataFrame(
        {
            "Amount": [5, 20000, 30000, 12345, 19999, 20000],
            "InvoiceNo": [
                "INV-001",
                "INV-002",
                "INV-003",
                "INV-003",
                "INV-004",
                "INV-005",
            ],
            "Vendor": ["Acme", "Bolt", "Acme", "Crest", "Bolt", "Acme"],
            "Date": [dt.date(2024, 3, day) for day in (1, 2, 3, 5, 6, 7)],
        },
        schema={
            "Amount": pl.Int64,
            "InvoiceNo": pl.String,
            "Vendor": pl.String,
            "Date": pl.Date,
        },
    )


def _collected(frames) -> list[pl.DataFrame]:
    return [f.collect() if isinstance(f, pl.LazyFrame) else f for f in frames]


# ------------------------------------------------------------- schema shape
@pytest.mark.parametrize("op, key", sorted(items.PROPS))
def test_fragment_reaches_the_settings_schema(op, key):
    prop = ns.describe_op(op)["settings"]["schema"]["properties"][key]
    for name, value in items.PROPS[(op, key)].items():
        assert prop[name] == value, (op, key, name)


@pytest.mark.parametrize("op, key", sorted(items.PROPS))
def test_fragment_names_a_real_setting_of_its_op(op, key):
    assert op in AUDIT_OPS
    assert key in ns.settings_defaults(op)


@pytest.mark.parametrize("op", AUDIT_OPS)
def test_every_list_says_what_it_holds_and_every_setting_has_a_type(op):
    props = ns.describe_op(op)["settings"]["schema"]["properties"]
    for key, prop in props.items():
        if prop.get("type") == "array":
            assert prop.get("items"), (op, key)
        assert "type" in prop or "enum" in prop, (op, key)


def test_expected_range_takes_a_whole_number_or_null():
    schema = ns.describe_op("audit.gaps")["settings"]["schema"]["properties"]
    for key in ("range_start", "range_end"):
        assert validate_value(schema[key], None, key) is None  # lowest / highest seen
        assert validate_value(schema[key], 1, key) is None
        assert validate_value(schema[key], -1, key) is not None


@pytest.mark.parametrize("op, key", ISO_DATE_SETTINGS)
def test_date_settings_say_their_format(op, key):
    assert "YYYY-MM-DD" in items.PROPS[(op, key)]["description"]


# -------------------------------------------------------------- enum pins
@pytest.mark.parametrize("op, key", sorted(ENUM_SOURCES))
def test_choice_list_equals_the_core_constant(op, key):
    assert items.PROPS[(op, key)]["enum"] == list(ENUM_SOURCES[(op, key)])


def test_every_choice_list_is_pinned_to_a_constant():
    enums = {key for key, fragment in items.PROPS.items() if "enum" in fragment}
    assert enums == set(ENUM_SOURCES)


# -------------------------------------------------------------- examples
def test_one_example_per_audit_op():
    assert set(items.EXAMPLES) == set(AUDIT_OPS)


@pytest.mark.parametrize("op", sorted(items.EXAMPLES))
def test_example_passes_the_authoring_validator(op):
    schema = ns.settings_schema(op)
    example = items.EXAMPLES[op]
    assert set(example) <= set(schema["properties"])
    assert validate_value(schema, example, "settings") is None


def test_duplicates_example_finds_the_repeated_invoice():
    params = duplicates.DuplicatesParams.from_dict(items.EXAMPLES["audit.duplicates"])
    dups, uniques, summary = _collected(
        duplicates.run_duplicates(_frame(), params).for_run()
    )
    assert dups["InvoiceNo"].to_list() == ["INV-003", "INV-003"]
    assert uniques.height == 4
    row = summary.row(0, named=True)
    assert (row["status"], row["groups"], row["exception_rows"]) == ("fail", 1, 2)


def test_gaps_example_finds_the_missing_day():
    params = gaps.GapsParams.from_dict(items.EXAMPLES["audit.gaps"])
    findings, summary = _collected(gaps.run_gaps(_frame(), params).for_run())
    assert findings.select("finding", "from", "to", "count").rows() == [
        ("date_gap", "2024-03-04", "2024-03-04", 1)
    ]
    assert summary.row(0, named=True)["missing_items"] == 1


def test_benford_example_builds_a_nine_row_table_and_drills_the_listed_digits():
    params = benford.BenfordParams.from_dict(items.EXAMPLES["audit.benford"])
    result = benford.run_benford(_frame(), params)
    assert result.extras["table"].height == 9
    assert result.extras["stats"]["n"] == 5  # the 5 is below the minimum amount
    drill = _collected(result.for_run())[2]
    assert sorted(drill["benford_digits"].to_list()) == [1, 1, 2, 2]


def test_sample_example_draws_from_each_band_as_asked():
    params = sampling.SamplingParams.from_dict(items.EXAMPLES["audit.sample"])
    sample, not_sampled, log = _collected(
        sampling.run_sample(_frame(), params).for_run()
    )
    assert sample.height == 3
    assert not_sampled.height == 3
    strata = log.filter(pl.col("scope") == "stratum")
    assert strata["sample_size"].to_list() == [1, 0, 2]  # band 2 is empty


def test_risk_filters_example_flags_the_entries_it_should():
    params = risk_filters.RiskParams.from_dict(items.EXAMPLES["audit.risk_filters"])
    flagged, not_flagged, summary = _collected(
        risk_filters.run_risk_filters(_frame(), params).for_run()
    )
    assert flagged.height == 5
    assert not_flagged.height == 1
    row = summary.row(0, named=True)
    counts = (
        row["n_weekend"],
        row["n_holiday"],
        row["n_round_amount"],
        row["n_just_below_limit"],
    )
    assert counts == (2, 1, 3, 1)
