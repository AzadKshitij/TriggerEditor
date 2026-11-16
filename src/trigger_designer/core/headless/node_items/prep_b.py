"""Item shapes and examples for preparation nodes, group b.

Plain literals only: no data library, Qt or trigger_designer import, so
``list_ops`` stays instant. Each shape is read from the node's core module
(``trigger_designer.core.shaping``); ``tests/unit/test_node_items_prep_b.py``
checks them against the code.
"""

from __future__ import annotations

from typing import Any

PROPS: dict[tuple[str, str], dict[str, Any]] = {
    # normalize.py: run_node keeps each name that is a column of the input.
    ("preparation.normalize_columns", "selected_columns"): {
        "items": {"type": "string"},
    },
    # record_id.py: normalize() and apply_record_id() use each name as a key.
    ("preparation.record_id", "group_by"): {
        "items": {"type": "string"},
    },
    # record_id.py: apply_record_id() reads item["column"] and item.get("descending").
    ("preparation.record_id", "order_by"): {
        "items": {
            "type": "object",
            "properties": {
                "column": {
                    "type": "string",
                    "description": (
                        "Column to order by. The first item is the main sort; "
                        "later items break ties."
                    ),
                },
                "descending": {
                    "type": "boolean",
                    "description": (
                        "True numbers the largest values first. Default false."
                    ),
                },
            },
        },
    },
    # select_records.py: apply_select_records() ranks or counts rows within each group.
    ("preparation.select_records", "group_by"): {
        "items": {"type": "string"},
    },
    # find_replace.py: apply_find_replace() needs each name to be a text column.
    ("preparation.find_replace", "columns"): {
        "items": {"type": "string"},
    },
    # find_replace.py: RULE_DEFAULTS, validate_rules() and _pattern() read these keys.
    ("preparation.find_replace", "rules"): {
        "items": {
            "type": "object",
            "properties": {
                "find": {
                    "type": "string",
                    "description": (
                        "Text to find, or a regular expression in regex mode. "
                        "Empty is refused for an enabled rule."
                    ),
                },
                "replace": {
                    "type": "string",
                    "description": (
                        "Text that replaces each match. In regex mode $1, $2 ... "
                        "are capture groups. Blank removes the matches."
                    ),
                },
                "mode": {
                    "type": "string",
                    "enum": ["literal", "regex"],
                    "description": (
                        "literal: Find is matched as typed. "
                        "regex: Find is a regular expression."
                    ),
                },
                "case_sensitive": {
                    "type": "boolean",
                    "description": (
                        "True matches letter case exactly. "
                        "False (the default) ignores case."
                    ),
                },
                "whole_cell": {
                    "type": "boolean",
                    "description": (
                        "True replaces only when the whole cell equals Find. "
                        "False replaces Find wherever it occurs in the cell."
                    ),
                },
                "enabled": {
                    "type": "boolean",
                    "description": (
                        "False switches the rule off; it is skipped. Rules run "
                        "top to bottom, each on the result of the rules above."
                    ),
                },
            },
        },
    },
    # date_helper.py: normalize() reads each calculation's keys; OPS lists the ops.
    ("preparation.date_helper", "ops"): {
        "items": {
            "type": "object",
            "properties": {
                "op": {
                    "type": "string",
                    "enum": [
                        "weekday_name",
                        "weekday_number",
                        "is_weekend",
                        "is_month_end",
                        "quarter",
                        "fiscal_year",
                        "fiscal_period",
                        "fiscal_quarter",
                        "days_between",
                        "add_days",
                        "add_business_days",
                        "is_business_day",
                        "business_days_between",
                    ],
                    "description": (
                        "The calculation. Each item adds one output column."
                    ),
                },
                "source": {
                    "type": "string",
                    "description": (
                        "Date column to calculate from. Date and datetime columns "
                        "work; text is read with the Text dates setting."
                    ),
                },
                "source2": {
                    "type": "string",
                    "description": (
                        "Second date column, used by days_between and "
                        "business_days_between only."
                    ),
                },
                "n": {
                    "type": "integer",
                    "description": (
                        "Days to add; negative subtracts. Used by add_days and "
                        "add_business_days unless n_column is set."
                    ),
                },
                "n_column": {
                    "type": "string",
                    "description": (
                        "Column of day counts used instead of n, for add_days "
                        "and add_business_days."
                    ),
                },
                "name": {
                    "type": "string",
                    "description": (
                        "Output column name. Blank gives an automatic name such "
                        "as Date_weekday_name."
                    ),
                },
            },
        },
    },
    # multi_formula.py: apply_multi_formula() needs each name to be a column.
    ("preparation.multi_field_formula", "columns"): {
        "items": {"type": "string"},
    },
}

EXAMPLES: dict[str, dict[str, Any]] = {
    # Only the selected column is renamed: Vendor Name becomes Vendor_Name.
    "preparation.normalize_columns": {"selected_columns": ["Vendor Name"]},
    # Rows are numbered within each Vendor, the largest Amount first.
    "preparation.record_id": {
        "group_by": ["Vendor"],
        "order_by": [{"column": "Amount", "descending": True}],
    },
    # The largest Amount per Vendor is kept; the other rows leave by output 2.
    "preparation.select_records": {
        "mode": "largest_n",
        "n": 1,
        "by": "Amount",
        "group_by": ["Vendor"],
    },
    "preparation.find_replace": {
        "columns": ["Vendor"],
        "rules": [{"find": "y", "replace": "Y-Corp", "mode": "literal"}],
    },
    # days_between needs a second date column on the input (PaidDate here).
    "preparation.date_helper": {
        "ops": [
            {"op": "weekday_name", "source": "Date", "name": "Weekday"},
            {
                "op": "days_between",
                "source": "Date",
                "source2": "PaidDate",
                "name": "DaysToPay",
            },
            {"op": "add_days", "source": "Date", "n": 30, "name": "DueDate"},
        ],
    },
    "preparation.multi_field_formula": {
        "columns": ["InvoiceNo", "Vendor"],
        "template": "UPPER({col})",
        "mode": "in_place",
    },
}
