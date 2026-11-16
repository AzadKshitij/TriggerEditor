"""Item shapes and examples: file input and the first preparation nodes.

Plain literals only (no imports beyond typing), so ``list_ops`` stays instant.
"""

from __future__ import annotations

from typing import Any

PROPS: dict[tuple[str, str], dict[str, Any]] = {
    ("input.file_input", "selected_sheets"): {
        "items": {
            "type": "string",
            "description": "Sheet name to read when sheet_mode is chosen.",
        },
    },
    ("input.file_input", "include_patterns"): {
        "items": {
            "type": "string",
            "description": (
                "Glob a file name in a folder must match, e.g. *.csv. "
                "Empty uses the default for the file type."
            ),
        },
    },
    ("preparation.cleansing", "selected_fields"): {
        "items": {"type": "string"},
    },
    ("preparation.groupby", "actions"): {
        "items": {
            "type": "object",
            "properties": {
                "field": {
                    "type": "string",
                    "description": (
                        "Column to group by or aggregate. One aggregate per "
                        "column: a later one replaces an earlier one."
                    ),
                },
                "action": {
                    "type": "string",
                    "enum": [
                        "GroupBy",
                        "Count",
                        "Sum",
                        "Mean",
                        "Min",
                        "Max",
                        "Std",
                        "Var",
                        "Median",
                        "First",
                        "Last",
                        "N_Unique",
                        "List",
                    ],
                    "description": (
                        "GroupBy groups rows by the field. Any other action "
                        "aggregates it per group; Count counts the rows."
                    ),
                },
                "output_name": {
                    "type": "string",
                    "description": (
                        "Result column name of an aggregate. Empty gives a "
                        "default such as Sum_Amount. GroupBy keeps the field name."
                    ),
                },
            },
        },
    },
    ("preparation.select", "columns"): {
        "items": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Source column name.",
                },
                "selected": {
                    "type": "boolean",
                    "description": "Keep this column. Unselected columns are dropped.",
                },
                "dtype": {
                    "type": "string",
                    "description": (
                        "Type to convert to, e.g. String, Int64, Float64, Boolean, "
                        "Date or Datetime. Empty, or a name the node does not "
                        "convert, leaves the column as it is."
                    ),
                },
                "rename": {
                    "type": "string",
                    "description": "New column name. Empty keeps the source name.",
                },
                "date_format": {
                    "type": "string",
                    "description": (
                        "Format for reading text as Date or Datetime, e.g. "
                        "%d/%m/%Y. Empty tries the common formats."
                    ),
                },
                "dtype_custom": {
                    "type": "boolean",
                    "description": (
                        "True when the type differs from the column's own type. "
                        "When False, the editor follows the column's type."
                    ),
                },
            },
        },
    },
    ("preparation.sort", "keys"): {
        "items": {
            "type": "object",
            "properties": {
                "column": {
                    "type": "string",
                    "description": "Column to sort by. Earlier keys sort first.",
                },
                "order": {
                    "type": "string",
                    "description": "Ascending (the default) or Descending.",
                },
            },
        },
    },
    ("preparation.unique", "selected_columns"): {
        "items": {"type": "string"},
    },
}

EXAMPLES: dict[str, dict[str, Any]] = {
    "preparation.cleansing": {
        "selected_fields": ["Vendor"],
        "case_modification": "upper",
    },
    "preparation.formula": {
        "sections": [
            {"target_column": "Amount_x2", "formula_text": "[Amount] * 2"},
        ],
    },
    "preparation.groupby": {
        "actions": [
            {"field": "Vendor", "action": "GroupBy", "output_name": "Vendor"},
            {"field": "Amount", "action": "Sum", "output_name": "total"},
            {"field": "InvoiceNo", "action": "Count", "output_name": "invoices"},
        ],
    },
}
