"""Schema fragments and examples for the five audit tests.

An audit node keeps its settings on the node content, and its defaults come from
the params dataclasses in ``core/audit``. A default of ``[]`` or ``None`` says
nothing about the items or the type, so the fragments here fill that in. Choice
lists copy the editor's vocabulary; ``tests/unit/test_node_items_audit.py`` pins
them to the core constants.
"""

from __future__ import annotations

from typing import Any

PROPS: dict[tuple[str, str], dict[str, Any]] = {
    ("audit.duplicates", "key_columns"): {
        "description": "Columns that together identify a duplicate, for example the vendor and the invoice number. At least one is required.",
        "items": {"type": "string"},
    },
    ("audit.duplicates", "mode"): {
        "enum": ["exact", "near"],
        "description": "exact: the key columns are equal. near: the key columns are equal and the amount and/or the date are within tolerance and window.",
    },
    ("audit.duplicates", "tolerance_kind"): {
        "enum": ["absolute", "percent"],
        "description": "Used in near mode. absolute: a fixed difference in amount. percent: a percentage of the larger absolute amount.",
    },
    ("audit.duplicates", "date_format"): {
        "enum": ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y%m%d"],
        "description": "How text dates in the near-match date column are read, as a strftime pattern (%Y-%m-%d reads 2024-03-31). Ignored for real Date columns.",
    },
    ("audit.gaps", "group_columns"): {
        "description": "Columns that split the sequence into separate series, for example one per ledger. Empty means one series. Must not be named prefix, finding, from, to, count or source_row.",
        "items": {"type": "string"},
    },
    ("audit.gaps", "mode"): {
        "enum": ["number", "prefixed", "date"],
        "description": "number: whole numbers. prefixed: text then digits, such as JE-000123. date: calendar days with no entry.",
    },
    ("audit.gaps", "range_start"): {
        "type": ["integer", "null"],
        "minimum": 0,
        "description": "First number expected in the series, 0 or more. null means the lowest number seen. Number and prefixed modes only.",
    },
    ("audit.gaps", "range_end"): {
        "type": ["integer", "null"],
        "minimum": 0,
        "description": "Last number expected in the series. null means the highest number seen. Must not be below range_start. Number and prefixed modes only.",
    },
    ("audit.gaps", "date_format"): {
        "enum": ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y%m%d"],
        "description": "How text dates are read in date mode, as a strftime pattern (%Y-%m-%d reads 2024-03-31). Ignored for real Date columns.",
    },
    ("audit.gaps", "holidays"): {
        "description": "Holiday dates, one per entry, written YYYY-MM-DD (for example 2024-03-29). Used in date mode when business_days_only (skip weekends) is on.",
        "items": {"type": "string"},
    },
    ("audit.benford", "drill_digits"): {
        "description": "Digits whose rows go to the drill-down output when drill_auto is false. 1 to 9 when digits is 1 (first digit); 10 to 99 when digits is 2 (first two digits).",
        "items": {"type": "integer", "minimum": 1, "maximum": 99},
    },
    ("audit.sample", "method"): {
        "enum": ["random", "systematic", "mus", "stratified"],
        "description": "random: every row has an equal chance. systematic: every n-th row from a random start. mus: monetary unit, larger amounts are more likely (needs amount_column). stratified: a set number of rows from each amount band (needs amount_column; band_edges and band_sizes define the bands).",
    },
    ("audit.sample", "size_kind"): {
        "enum": ["count", "percent"],
        "description": "count: sample_size rows. percent: sample_percent of the population, rounded up and at least 1. Ignored by stratified.",
    },
    ("audit.sample", "key_columns"): {
        "description": "Columns that identify a row (the stable key). Rows are put in a fixed order by them before the draw, so the same seed gives the same sample. Empty means every column.",
        "items": {"type": "string"},
    },
    ("audit.sample", "band_edges"): {
        "description": "Stratified only. Ascending band edges for the absolute amount, 0 or more, strictly increasing (for example 1000 and 10000). An amount equal to an edge falls in the higher band.",
        "items": {"type": "number", "minimum": 0},
    },
    ("audit.sample", "band_sizes"): {
        "description": "Stratified only. One size per band, so one more than band_edges (for example 1, 1, 2 for two edges). A size is a row count of 1 or more, or -1 for the whole band (shown as all in the editor). 0 is refused.",
        "items": {"type": "integer", "minimum": -1},
    },
    ("audit.risk_filters", "date_format"): {
        "enum": ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y%m%d"],
        "description": "How dates stored as text are read, as a strftime pattern (%Y-%m-%d reads 2024-03-31). Ignored for real Date columns.",
    },
    ("audit.risk_filters", "period_end"): {
        "description": "Period end date, written YYYY-MM-DD (for example 2024-03-31); no other form is accepted. Used by Posted after period end.",
    },
    ("audit.risk_filters", "holidays"): {
        "description": "Public holiday dates, one per entry, written YYYY-MM-DD (for example 2024-12-25). At least one is needed when Public-holiday posting is on.",
        "items": {"type": "string"},
    },
    ("audit.risk_filters", "approval_limits"): {
        "description": "Approval limits as numbers above 0, for example 5000 and 10000. An amount within below_pct under a limit is flagged; the limit itself is not. Needed when Just below approval limit is on.",
        "items": {"type": "number", "minimum": 0},
    },
    ("audit.risk_filters", "keywords"): {
        "description": "Words or phrases, one per entry. A description containing any of them is flagged, ignoring case and matching anywhere in the text. Blank entries are ignored. Needed when Keyword in description is on.",
        "items": {"type": "string"},
    },
}

EXAMPLES: dict[str, dict[str, Any]] = {
    "audit.duplicates": {"key_columns": ["InvoiceNo"], "mode": "exact"},
    "audit.gaps": {"sequence_column": "Date", "mode": "date"},
    "audit.benford": {
        "amount_column": "Amount",
        "drill_auto": False,
        "drill_digits": [1, 2],
    },
    "audit.sample": {
        "method": "stratified",
        "amount_column": "Amount",
        "key_columns": ["InvoiceNo"],
        "band_edges": [1000, 10000],
        "band_sizes": [1, 1, 2],
    },
    "audit.risk_filters": {
        "date_column": "Date",
        "amount_column": "Amount",
        "weekend": True,
        "holiday": True,
        "holidays": ["2024-03-05"],
        "round_amount": True,
        "round_multiple": 1000,
        "just_below_limit": True,
        "approval_limits": [20000],
    },
}
