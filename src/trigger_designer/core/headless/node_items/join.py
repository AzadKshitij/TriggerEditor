"""Item shapes and examples for the join group.

Plain literals only: ``node_items/__init__.py`` merges these tables into
``node_spec``, and ``list_ops`` must stay instant. Each shape is read from the
code that consumes it: ``core/shaping/join.py``, ``core/shaping/reconcile.py``,
``core/shaping/fuzzy.py``, and ``qt/widgets/nodes/Join/union.py`` (Union has no
core module; its column map is executed by the widget).
"""

from __future__ import annotations

from typing import Any

PROPS: dict[tuple[str, str], dict[str, Any]] = {
    # Only the default in core/shaping/join.py names it; nothing reads it.
    ("join.join", "join_type"): {
        "description": (
            "Not used. The node always returns three outputs: J (matched rows), "
            "L (left rows without a match) and R (right rows without a match)."
        ),
    },
    # core/shaping/join.py sanitize_mapping(): a pair is kept only when both
    # columns exist on their own side and neither column is used twice.
    ("join.join", "mapping_data"): {
        "description": (
            "Key pairs. Rows match when every pair is equal (null keys never "
            "match). Each column may appear in one pair only."
        ),
        "items": {
            "type": "object",
            "properties": {
                "left_column": {
                    "type": "string",
                    "description": "Column of the left input.",
                },
                "right_column": {
                    "type": "string",
                    "description": "Column of the right input.",
                },
            },
        },
    },
    # core/shaping/join.py run_node(): the listed columns are the J output, and
    # an empty list means every column. sync_selected_with_schema() drops names
    # that are no longer upstream.
    ("join.join", "selected_columns"): {
        "description": "Columns of the joined output J. Empty means all columns.",
        "items": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Column name as it appears in its input.",
                },
                "source": {
                    "type": "string",
                    "description": (
                        "'L' for a left-input column, 'R' for a right-input "
                        "column. Any other value is dropped."
                    ),
                },
            },
        },
    },
    # core/shaping/join.py sync_selected_with_schema(): with auto-accept on, only
    # columns missing from this list are added to the selection.
    ("join.join", "known_columns"): {
        "description": (
            "Columns the editor has already seen. Auto-accept adds only columns "
            "missing from this list. The editor maintains it."
        ),
        "items": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Column name as it appears in its input.",
                },
                "source": {
                    "type": "string",
                    "description": "'L' for a left-input column, 'R' for right.",
                },
            },
        },
    },
    # qt/widgets/nodes/Join/union.py _concat_manual(): column_map is read only in
    # Manual mode. An empty map (or one with no named rows) falls back to the
    # Auto by Name layout.
    ("join.union", "column_map"): {
        "description": (
            "Manual mode only: one row per output column. Empty (or no named rows) "
            "falls back to Auto by Name."
        ),
        "items": {
            "type": "object",
            "properties": {
                "output": {
                    "type": "string",
                    "description": (
                        "Name of the output column. Blank names are ignored, and "
                        "only the first of repeated names is kept."
                    ),
                },
                "sources": {
                    "type": "array",
                    "description": "One entry per input, in connection order.",
                    "items": {
                        "type": ["string", "null"],
                        "description": (
                            "Column of that input, or null for an empty value."
                        ),
                    },
                },
            },
        },
    },
    # core/shaping/reconcile.py normalize() ignores a pair with an empty side;
    # _slim() compares keys as trimmed, lower-case text.
    ("join.reconcile", "key_pairs"): {
        "description": (
            "Key pairs. Rows are candidates only when every pair is equal. Keys "
            "are compared as trimmed, lower-case text."
        ),
        "items": {
            "type": "object",
            "properties": {
                "left": {
                    "type": "string",
                    "description": "Column of the left input.",
                },
                "right": {
                    "type": "string",
                    "description": "Column of the right input.",
                },
            },
        },
    },
    # core/shaping/fuzzy.py normalize() ignores a pair with an empty side and
    # raises TD-SHAPE-004 above MAX_BLOCK_COLUMNS (5).
    ("join.fuzzy_match", "block_columns"): {
        "description": (
            "Extra column pairs that must be equal (trimmed, lower-case). At most 5."
        ),
        "items": {
            "type": "object",
            "properties": {
                "left": {
                    "type": "string",
                    "description": "Column of the left input.",
                },
                "right": {
                    "type": "string",
                    "description": "Column of the right input.",
                },
            },
        },
    },
}

EXAMPLES: dict[str, dict[str, Any]] = {
    # Invoices to payments on InvoiceNo: J keeps the matched rows, L and R the rest.
    "join.join": {
        "mapping_data": [{"left_column": "InvoiceNo", "right_column": "InvoiceNo"}],
        "selected_columns": [
            {"name": "InvoiceNo", "source": "L"},
            {"name": "Amount", "source": "L"},
            {"name": "Vendor", "source": "L"},
            {"name": "Paid", "source": "R"},
        ],
        "auto_accept_new_columns": True,
        "known_columns": [],
    },
    # One-to-one on InvoiceNo; amounts and dates are not compared.
    "join.reconcile": {
        "match_type": "one_to_one",
        "key_pairs": [{"left": "InvoiceNo", "right": "InvoiceNo"}],
        "amount_left": "",
        "amount_right": "",
        "tolerance_mode": "absolute",
        "tolerance": 0.0,
        "date_left": "",
        "date_right": "",
        "date_window_days": 0,
    },
    # Vendor (left) against Supplier (right): Jaro-Winkler, prefix blocking.
    "join.fuzzy_match": {
        "left_column": "Vendor",
        "right_column": "Supplier",
        "algorithm": "jaro_winkler",
        "threshold": 0.85,
        "blocking": "prefix",
        "prefix_length": 3,
        "block_columns": [],
        "strip_suffixes": True,
        "assignment": "one_to_one",
    },
}
