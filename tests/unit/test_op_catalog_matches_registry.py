"""The Qt-free op catalogue must follow the real node registry (plan 08 S1)."""

from __future__ import annotations

from trigger_designer.core import node_configuration as nc
from trigger_designer.core.headless.op_catalog import OPS, V1_OPCODE_TO_OP


def _registered() -> set[str]:
    ops = set()
    for family, registry in nc.NODE_REGISTRIES.items():
        for code in registry:
            ops.add(f"{family.value}.{nc._OPCODE_ENUMS[family](code).name.lower()}")
    return ops


def test_every_registered_node_has_a_catalogue_row():
    missing = _registered() - set(OPS)
    assert not missing, (
        f"add rows for {sorted(missing)} to core/headless/op_catalog.py "
        "(and output_keys if the node holds an output path)"
    )


def test_rows_without_a_node_are_marked_planned():
    stale = {op for op in set(OPS) - _registered() if not OPS[op].planned}
    assert not stale, f"rows with no registered node must be planned=True: {stale}"


def test_titles_match_the_registered_nodes():
    for family, registry in nc.NODE_REGISTRIES.items():
        for code, cls in registry.items():
            op = f"{family.value}.{nc._OPCODE_ENUMS[family](code).name.lower()}"
            title = getattr(cls, "node_title", None)
            if op in OPS and title:
                assert OPS[op].title == title, op


def test_v1_table_equals_the_frozen_original():
    assert V1_OPCODE_TO_OP == nc.V1_OPCODE_TO_OP


def test_no_registered_node_embeds_user_python():
    assert not any(info.custom_code for info in OPS.values())


def test_file_output_declares_its_path_key():
    assert OPS["input.file_output"].output_keys == ("filePath",)
    assert OPS["input.workpaper_output"].output_keys == ("output_path",)
