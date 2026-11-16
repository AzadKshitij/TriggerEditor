"""The node spec tables must follow the real nodes (AI plan, phase 1).

``core/headless/node_spec.py`` is Qt-free, so its socket and default tables are
copies. This file is what makes a copy that drifted fail the build.
"""

from __future__ import annotations

import dataclasses

import pytest

from trigger_designer.core.audit.common import params_schema
from trigger_designer.core.headless import node_spec as ns
from trigger_designer.core.headless.node_spec_forms import load_forms, registered_nodes
from trigger_designer.qt.headless import make_window


def _registered() -> list[tuple[str, type]]:
    return registered_nodes()


@pytest.fixture(scope="module")
def window(qapp):
    return make_window()


@pytest.mark.parametrize("op, cls", _registered(), ids=lambda v: str(v))
def test_sockets_match_the_real_node(op, cls, window):
    node = cls(window.scene)
    sockets = ns.SOCKETS[op]
    assert len(node.inputs) == sockets.inputs, op
    assert len(node.outputs) == len(sockets.outputs), op
    content_class = getattr(cls, "content_class", None)
    if hasattr(content_class, "OPTIONAL_INPUTS"):
        assert tuple(sorted(content_class.OPTIONAL_INPUTS)) == sockets.optional, op
    if hasattr(content_class, "OUTPUT_KINDS"):
        assert tuple(content_class.OUTPUT_KINDS) == sockets.outputs, op


def test_every_shaping_node_is_checked():
    """Guards the two tests above against silently skipping every node."""
    with_content = [op for op, cls in _registered() if hasattr(cls, "content_class")]
    assert len(with_content) >= 25, with_content


@pytest.mark.parametrize("op, cls", _registered(), ids=lambda v: str(v))
def test_settings_defaults_match_the_real_node(op, cls):
    content_class = getattr(cls, "content_class", None)
    if content_class is None or not hasattr(content_class, "SETTINGS"):
        pytest.skip("not a shaping node: covered by its own test")
    assert ns.settings_defaults(op) == dict(content_class.SETTINGS), op


def test_audit_defaults_match_the_audit_nodes(window):
    from trigger_designer.qt.widgets.nodes.Audit import _base

    for op, cls in _registered():
        if not op.startswith("audit."):
            continue
        node = cls(window.scene)
        params = type(node.content).PARAMS
        assert issubclass(params, _base.ParamsBase)
        expected = {k: v["default"] for k, v in params_schema(params).items()}
        assert ns.settings_defaults(op) == expected, op


def test_file_input_defaults_match_its_serialised_state():
    from trigger_designer.qt.widgets.nodes.InOut.file_input import FileInputContent

    state = FileInputContent.serialized_state_schema
    mine = ns.settings_defaults("input.file_input")
    assert set(mine) <= set(state), set(mine) - set(state)
    for key, value in mine.items():
        assert state[key]["default"] == value, key


def test_union_defaults_match_its_modes():
    from trigger_designer.qt.widgets.nodes.Join.union import MODES

    assert ns.settings_defaults("join.union")["mode"] in MODES


def test_forms_enrich_real_schemas():
    forms = load_forms()
    assert "transform.window" in forms and "preparation.sort" in forms
    window_schema = ns.settings_schema("transform.window", forms)
    op_card = window_schema["properties"]["ops"]["items"]["properties"]["op"]
    assert "lag" in op_card["enum"] and "rank" in op_card["enum"]
    sort_schema = ns.settings_schema("preparation.sort", forms)
    assert sort_schema["properties"]["keys"]["type"] == "array"


def test_form_only_adds_it_never_changes_a_default_or_type():
    forms = load_forms()
    for op in forms:
        plain = ns.settings_schema(op)
        rich = ns.settings_schema(op, forms)
        assert set(rich["properties"]) == set(plain["properties"]), op
        for key, prop in plain["properties"].items():
            assert rich["properties"][key]["default"] == prop["default"], (op, key)
            if "type" in prop:
                assert rich["properties"][key]["type"] == prop["type"], (op, key)


def test_every_form_field_is_a_stored_setting():
    """A form key with no default would be silently dropped from the schema."""
    unknown = {}
    for op, form in load_forms().items():
        keys = set(ns.settings_defaults(op))
        for section in form:
            for spec in ns._flatten(section.fields):
                stored = spec.kind != "note" and not spec.key.startswith("_")
                if stored and spec.key not in keys:
                    unknown.setdefault(op, []).append(spec.key)
    assert not unknown, unknown


def test_dataclass_params_are_plain_json_defaults():
    from trigger_designer.core.audit.benford import BenfordParams

    assert all(
        f.default is not dataclasses.MISSING
        or f.default_factory is not dataclasses.MISSING
        for f in dataclasses.fields(BenfordParams)
    )
