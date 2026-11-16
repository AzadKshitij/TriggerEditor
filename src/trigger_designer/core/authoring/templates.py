"""The JSON a freshly created node has, exactly as the editor would save it.

Qt-free copy of facts the node classes hold. ``tests/ui/test_authoring_matches_gui.py``
builds every node in the real editor and fails when this table drifts.
"""

from __future__ import annotations

from typing import Any

from trigger_designer.core.headless.node_spec import (
    SETTINGS,
    SETTINGS_SOURCES,
    SOCKETS,
    settings_defaults,
)
from trigger_designer.core.headless.op_catalog import OPS

#: The ``node_code`` the editor saves (the enum value of the node class).
NODE_CODES: dict[str, int] = {
    "input.file_input": 3,
    "input.file_output": 4,
    "input.workpaper_output": 5,
    "preparation.cleansing": 1,
    "preparation.dynamic_row_builder": 9,
    "preparation.filter": 2,
    "preparation.formula": 3,
    "preparation.groupby": 4,
    "preparation.select": 5,
    "preparation.sort": 6,
    "preparation.split": 8,
    "preparation.unique": 7,
    "preparation.normalize_columns": 10,
    "preparation.record_id": 11,
    "preparation.select_records": 12,
    "preparation.find_replace": 13,
    "preparation.date_helper": 14,
    "preparation.multi_field_formula": 16,
    "preparation.text_to_columns": 15,
    "join.append": 1,
    "join.union": 3,
    "join.join": 2,
    "join.reconcile": 4,
    "join.fuzzy_match": 5,
    "transform.count_records": 2,
    "transform.running_total": 3,
    "transform.transpose": 4,
    "transform.pivot": 5,
    "transform.unpivot": 6,
    "transform.window": 7,
    "transform.sql_query": 8,
    "report.graph": 1,
    "report.data_profile": 2,
    "report.comment": 3,
    "audit.benford": 3,
    "audit.gaps": 2,
    "audit.duplicates": 1,
    "audit.risk_filters": 5,
    "audit.sample": 4,
}

#: Every output is socket type 3 except an audit node's status output, whose
#: index is listed here.
STATUS_OUTPUT_INDEX: dict[str, int] = {
    "audit.benford": 1,
    "audit.gaps": 1,
    "audit.duplicates": 2,
    "audit.risk_filters": 2,
    "audit.sample": 2,
}
INPUT_SOCKET_TYPE, INPUT_POSITION = 1, 2
OUTPUT_SOCKET_TYPE, STATUS_SOCKET_TYPE, OUTPUT_POSITION = 3, 1, 5
EDGE_TYPE = 5
LABEL_OFFSET = 10.0


def _socket_dict(sid: int, index: int, multi: bool, kind: int, position: int) -> dict:
    return {
        "id": sid,
        "index": index,
        "multi_edges": multi,
        "position": position,
        "socket_type": kind,
    }


def socket_counts(op: str) -> tuple[int, int]:
    sockets = SOCKETS[op]
    return sockets.inputs, len(sockets.outputs)


def initial_content(op: str) -> dict[str, Any]:
    """The ``content`` of a new node: its default settings, placed where the
    editor stores them (``content.settings`` or ``content`` itself)."""
    defaults = settings_defaults(op)
    source = SETTINGS_SOURCES.get(op)
    if source is None or source.location == SETTINGS:
        return {"settings": defaults}
    return defaults


def new_node(op: str, node_id: int, socket_ids: list[int], x: float, y: float) -> dict:
    """A new node dict. ``socket_ids`` has one id per input, then per output."""
    sockets = SOCKETS[op]
    info = OPS[op]
    n_in, n_out = sockets.inputs, len(sockets.outputs)
    inputs = [
        _socket_dict(
            socket_ids[i], i, sockets.variadic, INPUT_SOCKET_TYPE, INPUT_POSITION
        )
        for i in range(n_in)
    ]
    outputs = []
    for i in range(n_out):
        status = STATUS_OUTPUT_INDEX.get(op) == i
        outputs.append(
            _socket_dict(
                socket_ids[n_in + i],
                i,
                True,
                STATUS_SOCKET_TYPE if status else OUTPUT_SOCKET_TYPE,
                OUTPUT_POSITION,
            )
        )
    return {
        "id": node_id,
        "title": info.title,
        "pos_x": x,
        "pos_y": y,
        "inputs": inputs,
        "outputs": outputs,
        "content": initial_content(op),
        "label_text": "",
        "label_visible": False,
        "label_offset": LABEL_OFFSET,
        "node_code": NODE_CODES[op],
        "node_type": info.family,
        "op": op,
    }


def new_edge(
    edge_id: int, start: int, end: int, *, label: str = "", input_index: int = 0
) -> dict:
    return {
        "id": edge_id,
        "edge_type": EDGE_TYPE,
        "start": start,
        "end": end,
        "label": label,
        "input_index": input_index,
    }
