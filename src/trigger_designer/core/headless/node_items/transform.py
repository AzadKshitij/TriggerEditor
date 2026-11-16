from __future__ import annotations

from typing import Any

PROPS: dict[tuple[str, str], dict[str, Any]] = {
    ("transform.running_total", "sum_columns"): {
        "items": {"type": "string"},
    },
    ("transform.running_total", "group_by_columns"): {
        "items": {"type": "string"},
    },
    ("transform.transpose", "key_columns"): {
        "items": {"type": "string"},
    },
    ("transform.transpose", "data_columns"): {
        "items": {"type": "string"},
    },
    ("transform.pivot", "index_columns"): {
        "items": {"type": "string"},
    },
    ("transform.unpivot", "id_columns"): {
        "items": {"type": "string"},
    },
    ("transform.unpivot", "value_columns"): {
        "items": {"type": "string"},
    },
    ("transform.window", "partition_by"): {
        "items": {"type": "string"},
    },
    ("transform.window", "order_by"): {
        "items": {
            "type": "object",
            "properties": {
                "column": {
                    "type": "string",
                    "description": "Column to order the rows by. Every row needs one.",
                },
                "descending": {
                    "type": "boolean",
                    "description": (
                        "True orders this column from Z to A, false from A to Z."
                    ),
                },
            },
        },
    },
    ("transform.window", "ops"): {
        "items": {
            "type": "object",
            "properties": {
                "op": {
                    "type": "string",
                    "enum": [
                        "lag",
                        "lead",
                        "row_number",
                        "rank",
                        "dense_rank",
                        "cum_sum",
                        "cum_min",
                        "cum_max",
                        "cum_mean",
                        "rolling_sum",
                    ],
                    "description": (
                        "Calculation for this new column. lag and lead read the "
                        "previous or next row."
                    ),
                },
                "source": {
                    "type": "string",
                    "description": (
                        "Column the calculation reads. Not used by row_number."
                    ),
                },
                "name": {
                    "type": "string",
                    "description": (
                        "Name of the new column. Empty gives a default such as "
                        "Amount_lag1 or Row_Number."
                    ),
                },
                "offset": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100000,
                    "description": (
                        "lag and lead only: how many rows back or ahead. Default 1."
                    ),
                },
                "window": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100000,
                    "description": (
                        "rolling_sum only: how many rows the sum covers. Default 3."
                    ),
                },
                "partial": {
                    "type": "boolean",
                    "description": (
                        "rolling_sum only: true gives a value from the rows "
                        "available at the start; false leaves those rows empty."
                    ),
                },
                "descending": {
                    "type": "boolean",
                    "description": (
                        "rank and dense_rank only: true gives rank 1 to the "
                        "largest value."
                    ),
                },
                "nulls": {
                    "type": "string",
                    "description": (
                        'Running and rolling calculations only. "skip" (default) '
                        'keeps an empty cell empty; "zero" counts it as 0.'
                    ),
                },
            },
        },
    },
}

EXAMPLES: dict[str, dict[str, Any]] = {
    "transform.running_total": {
        "sum_columns": ["Amount"],
        "group_by_columns": ["Vendor"],
    },
    "transform.transpose": {
        "key_columns": ["Vendor", "InvoiceNo"],
        "data_columns": ["Amount"],
    },
    "transform.pivot": {
        "index_columns": ["Vendor"],
        "header_column": "InvoiceNo",
        "value_column": "Amount",
        "aggregation": "sum",
    },
    "transform.unpivot": {
        "id_columns": ["Vendor"],
        "value_columns": ["Amount"],
    },
    "transform.window": {
        "partition_by": ["Vendor"],
        "order_by": [{"column": "Date", "descending": False}],
        "ops": [
            {"op": "cum_sum", "source": "Amount", "name": "RunningAmount"},
            {"op": "lag", "source": "Amount", "offset": 1, "name": "PreviousAmount"},
        ],
    },
}
