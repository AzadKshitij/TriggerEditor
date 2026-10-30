"""Hand-maintained table of node op ids (plan 08 S1).

Qt-free by design: reading the real registry imports Qt (``node_configuration``
ends by importing every node). ``tests/unit/test_op_catalog_matches_registry.py``
fails when this table and the registry drift, so a new node must add its row
here (and ``output_keys``/``input_keys`` when its content holds a file path:
``approve``, ``info`` and ``paths`` list files from these keys).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OpInfo:
    op: str
    title: str
    family: str
    custom_code: bool = False
    #: Content keys that hold an output path; the patcher stages these.
    output_keys: tuple[str, ...] = ()
    #: Content keys that hold an input path (read before the run).
    input_keys: tuple[str, ...] = ()
    #: True while the node is planned but may not be registered in this build.
    planned: bool = False


def _row(op: str, title: str, **kw) -> tuple[str, OpInfo]:
    return op, OpInfo(op, title, op.partition(".")[0], **kw)


OPS: dict[str, OpInfo] = dict(
    [
        _row("input.file_input", "File Input", input_keys=("filePath",)),
        _row("input.file_output", "File Output", output_keys=("filePath",)),
        _row("preparation.cleansing", "Cleansing"),
        _row("preparation.filter", "Filter"),
        _row("preparation.formula", "Formula"),
        _row("preparation.groupby", "Aggregate"),
        _row("preparation.select", "Select"),
        _row("preparation.sort", "Sort"),
        _row("preparation.unique", "Unique"),
        _row("preparation.split", "Split"),
        _row("preparation.dynamic_row_builder", "Rows"),
        _row("preparation.normalize_columns", "Normalize"),
        _row("preparation.record_id", "Record ID"),
        _row("preparation.select_records", "Select Records"),
        _row("preparation.find_replace", "Find and Replace"),
        _row("preparation.date_helper", "Date Helper"),
        _row("preparation.text_to_columns", "Text to Columns"),
        _row("preparation.multi_field_formula", "Multi-Field Formula"),
        _row("join.append", "Append"),
        _row("join.join", "Join"),
        _row("join.union", "Union"),
        _row("join.reconcile", "Reconcile"),
        _row("join.fuzzy_match", "Fuzzy Match"),
        _row("transform.count_records", "Count"),
        _row("transform.running_total", "Running Total"),
        _row("transform.transpose", "Transpose"),
        _row("transform.pivot", "Pivot"),
        _row("transform.unpivot", "Unpivot"),
        _row("transform.window", "Window"),
        _row("transform.sql_query", "SQL Query"),
        _row("report.graph", "Graph"),
        _row("report.data_profile", "Data Profile"),
        _row("report.comment", "Comment"),
        _row("audit.duplicates", "Duplicates"),
        _row("audit.gaps", "Gaps"),
        _row("audit.benford", "Benford"),
        _row("audit.sample", "Sample"),
        _row("audit.risk_filters", "Risk Filters"),
        # The workpaper node holds its output path in ``output_path``; listing
        # it here lets the patcher stage it like a File Output.
        _row(
            "input.workpaper_output",
            "Workpaper Output",
            output_keys=("output_path",),
        ),
    ]
)

#: Frozen v1 numbering (copied from ``node_configuration.V1_OPCODE_TO_OP``,
#: which is marked NEVER edit, so this copy cannot drift). Lets the Qt-free
#: validator resolve files that predate stable op ids.
V1_OPCODE_TO_OP: dict[tuple[str, int], str] = {
    ("input", 1): "input.browser",
    ("input", 2): "input.directory",
    ("input", 3): "input.text_input",
    ("input", 4): "input.file_input",
    ("input", 5): "input.file_output",
    ("input", 6): "input.text_output",
    ("preparation", 1): "preparation.cleansing",
    ("preparation", 2): "preparation.filter",
    ("preparation", 3): "preparation.formula",
    ("preparation", 4): "preparation.select",
    ("preparation", 5): "preparation.sort",
    ("preparation", 6): "preparation.unique",
    ("preparation", 7): "preparation.split",
    ("preparation", 8): "preparation.dynamic_row_builder",
    ("preparation", 9): "preparation.dynamic_row_builder",
    ("join", 1): "join.append",
    ("join", 2): "join.join",
    ("join", 3): "join.union",
    ("transform", 1): "transform.arrange",
    ("transform", 2): "transform.count_records",
    ("transform", 3): "transform.running_total",
    ("transform", 4): "transform.transpose",
    ("report", 1): "report.table",
    ("report", 2): "report.plot",
    ("report", 3): "report.graph",
}


def known_op(op: str) -> OpInfo | None:
    return OPS.get(op)


def migrate_v1_op(node: dict) -> str | None:
    """The stable op id of a v1 node dict (``node_code``/``op_code`` keys)."""
    if "node_code" in node:
        family, code = node.get("node_type"), node.get("node_code")
    elif "op_code" in node:
        family, code = str(node.get("op_type", "")).lower(), node.get("op_code")
    else:
        return None
    try:
        return V1_OPCODE_TO_OP.get((str(family), int(code)))
    except TypeError, ValueError:
        return None


def node_op(node: dict) -> str | None:
    """The op id of a node dict: stored ``op``, else the v1 migration."""
    op = node.get("op")
    if isinstance(op, str) and op:
        return op
    return migrate_v1_op(node)
