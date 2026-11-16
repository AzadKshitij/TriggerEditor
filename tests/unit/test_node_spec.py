"""The node spec export is a public contract for agents (AI plan, phase 1).

Qt-free: the editor-side checks (sockets and defaults against the real nodes,
the ``FORM`` enrichment) live in ``tests/ui/test_node_spec_registry.py``.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import polars as pl
import pytest

from trigger_designer.core.headless import node_spec as ns
from trigger_designer.core.headless.exit_codes import CliError
from trigger_designer.core.headless.op_catalog import OPS

REPO = Path(__file__).resolve().parents[2]
LIVE_OPS = sorted(op for op, info in OPS.items() if not info.planned)


def test_every_live_op_is_fully_described():
    missing = {
        table: sorted(set(LIVE_OPS) - set(rows))
        for table, rows in {
            "SETTINGS_SOURCES": ns.SETTINGS_SOURCES,
            "SOCKETS": ns.SOCKETS,
            "DESCRIPTIONS": ns.DESCRIPTIONS,
            "DOC_PAGES": ns.DOC_PAGES,
        }.items()
    }
    assert not any(missing.values()), (
        f"add rows to core/headless/node_spec.py for: {missing}"
    )


def test_no_row_for_an_op_that_does_not_exist():
    for table in (ns.SETTINGS_SOURCES, ns.SOCKETS, ns.DESCRIPTIONS, ns.DOC_PAGES):
        assert not set(table) - set(OPS)


@pytest.mark.parametrize("op", LIVE_OPS)
def test_docs_page_exists(op):
    assert (REPO / "docs" / ns.DOC_PAGES[op]).is_file()


def test_list_is_exactly_the_live_ops_and_needs_no_data_libraries():
    rows = ns.list_ops()
    assert [r["op"] for r in rows] == [op for op in OPS if op in LIVE_OPS]
    assert {"op", "title", "family", "description", "docs", "inputs", "outputs"} <= set(
        rows[0]
    )


@pytest.mark.parametrize("op", LIVE_OPS)
def test_describe_is_json_and_closed(op):
    spec = ns.describe_op(op)
    json.dumps(spec)  # nothing but plain JSON
    schema = spec["settings"]["schema"]
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    # Every default is a valid instance of its own schema.
    for key, prop in schema["properties"].items():
        assert "default" in prop, key
    assert spec["settings"]["defaults"] == {
        k: p["default"] for k, p in schema["properties"].items()
    }


@pytest.mark.parametrize("op", sorted(ns.EXAMPLES))
def test_example_only_uses_known_keys_and_types(op):
    schema = ns.settings_schema(op)
    assert set(ns.EXAMPLES[op]) <= set(schema["properties"])
    for key, value in ns.EXAMPLES[op].items():
        wanted = schema["properties"][key].get("type")
        python = {
            "string": str,
            "boolean": bool,
            "integer": int,
            "number": (int, float),
            "array": list,
            "object": dict,
        }.get(wanted)
        assert python is None or isinstance(value, python), (op, key)


def test_shaping_examples_really_run():
    frame = pl.DataFrame(
        {
            "Amount": [5, 20000, 30000],
            "InvoiceNo": ["a", "a", "b"],
            "Vendor": ["x", "y", "y"],
        }
    )
    for op in ("preparation.filter", "preparation.sort", "preparation.unique"):
        source = ns.SETTINGS_SOURCES[op].source
        assert source is not None
        core = importlib.import_module(source.partition(":")[0])
        outs = core.run_node([frame.lazy()], ns.EXAMPLES[op])
        assert outs, op
        [out.collect() for out in outs]
    sql = importlib.import_module("trigger_designer.core.shaping.sql_query")
    [out] = sql.run_node([frame.lazy(), None, None], ns.EXAMPLES["transform.sql_query"])
    assert sorted(out.collect().columns) == ["Vendor", "total"]


def test_select_example_converts_text_to_the_type_it_names():
    core = importlib.import_module("trigger_designer.core.shaping.select")
    frame = pl.DataFrame({"Amount": ["2450.00", "18200.5"], "InvoiceNo": ["a", "b"]})
    [out] = core.run_node([frame.lazy()], ns.EXAMPLES["preparation.select"])
    assert out.collect().schema["Amount"] == pl.Float64


def test_filter_example_selects_what_it_says():
    core = importlib.import_module("trigger_designer.core.shaping.filter")
    frame = pl.DataFrame({"Amount": [5, 20000, 30000]}).lazy()
    true_out, false_out = core.run_node([frame], ns.EXAMPLES["preparation.filter"])
    assert true_out.collect()["Amount"].to_list() == [20000, 30000]
    assert false_out.collect()["Amount"].to_list() == [5]


def test_the_filter_description_warns_about_text_columns():
    assert "text" in ns.DESCRIPTIONS["preparation.filter"]


@pytest.mark.parametrize(
    "value, expected",
    [
        (True, {"type": "boolean"}),  # bool is not "integer"
        (3, {"type": "integer"}),
        (1.5, {"type": "number"}),
        ("x", {"type": "string"}),
        ([], {"type": "array"}),
        (["a"], {"type": "array", "items": {"type": "string"}}),
        (None, {}),
    ],
)
def test_infer_schema(value, expected):
    assert ns.infer_schema(value) == expected


def test_infer_schema_nests_objects():
    schema = ns.infer_schema({"a": [{"b": 1}]})
    assert schema["properties"]["a"]["items"]["properties"]["b"] == {"type": "integer"}


def test_audit_settings_come_from_the_params_dataclass():
    defaults = ns.settings_defaults("audit.benford")
    assert defaults["digits"] == 1
    assert defaults["drill_auto"] is True
    assert ns.describe_op("audit.benford")["settings"]["path"] == "content"


def test_shaping_settings_live_under_settings():
    spec = ns.describe_op("preparation.filter")
    assert spec["settings"]["path"] == "content.settings"
    assert spec["settings"]["schema"]["properties"]["mode"]["default"] == "builder"


def test_defaults_are_copies():
    ns.settings_defaults("preparation.sort")["keys"].append("junk")
    assert ns.settings_defaults("preparation.sort")["keys"] == []
    first = ns.describe_op("input.file_input")["settings"]["defaults"]
    first["exclude_patterns"].append("junk")
    assert (
        "junk"
        not in ns.describe_op("input.file_input")["settings"]["defaults"][
            "exclude_patterns"
        ]
    )


def test_sockets_describe_optional_and_variadic_inputs():
    sql = ns.summarize_op("transform.sql_query")
    assert [i["required"] for i in sql["inputs"]] == [True, False, False]
    assert ns.summarize_op("join.union")["inputs_variadic"] is True
    assert ns.summarize_op("input.file_input")["inputs"] == []
    assert [o["name"] for o in ns.summarize_op("preparation.filter")["outputs"]] == [
        "true",
        "false",
    ]


def test_file_keys_follow_the_catalogue():
    files = ns.describe_op("input.file_output")["files"]
    assert files["writes"] == ["filePath"]
    assert ns.describe_op("input.file_input")["files"]["reads"] == ["filePath"]


def test_unknown_op_suggests_the_closest():
    with pytest.raises(CliError) as exc:
        ns.describe_op("preparation.filtr")
    assert exc.value.td_code == "TD-CLI-003"
    assert "preparation.filter" in exc.value.hint


def test_export_all_has_a_version_and_every_op():
    doc = ns.export_all()
    assert doc["spec_version"] == ns.SPEC_VERSION == 1
    assert [o["op"] for o in doc["ops"]] == [r["op"] for r in ns.list_ops()]
    json.dumps(doc)


# ------------------------------------------------------------------- FORM
def _field(key, kind, **kw):
    base = {
        "key": key,
        "label": key.title(),
        "kind": kind,
        "options": (),
        "minimum": 0,
        "maximum": 1_000_000,
        "tip": "",
        "hint": "",
        "items": (),
        "item_default": {},
        "max_items": 50,
        "show_if": None,
    }
    return SimpleNamespace(**{**base, **kw})


def test_apply_form_adds_choices_ranges_and_labels():
    schema = {
        "type": "object",
        "properties": {
            "mode": {"type": "string", "default": "a"},
            "n": {"type": "integer", "default": 1},
            "on": {"type": "boolean", "default": False},
            "cols": {"type": "array", "default": []},
        },
    }
    form = (
        SimpleNamespace(
            fields=(
                _field("mode", "combo", options=(("a", "Alpha"), "b")),
                _field("n", "int", minimum=1, maximum=9, tip="How many"),
                _field("on", "check"),
                _field("cols", "picker"),
                _field("_hint", "note"),
                _field("not_stored", "text"),
            )
        ),
    )
    ns.apply_form(schema, form)
    props = schema["properties"]
    assert props["mode"]["enum"] == ["a", "b"]
    assert props["mode"]["type"] == "string"  # the real default's type wins
    assert (props["n"]["minimum"], props["n"]["maximum"]) == (1, 9)
    assert props["n"]["description"] == "How many"
    assert props["cols"]["x-td-ref"] == "columns"
    assert "not_stored" not in props and "_hint" not in props


def test_apply_form_describes_list_cards_and_flattens_pairs():
    schema = {
        "type": "object",
        "properties": {"keys": {"type": "array", "default": []}},
    }
    card = _field(
        "keys",
        "list",
        item_default={"column": "", "order": "Ascending"},
        items=(
            _field("column", "column"),
            _field(
                "pair",
                "pair",
                items=(_field("order", "combo", options=("Ascending", "Descending")),),
            ),
        ),
    )
    ns.apply_form(schema, (SimpleNamespace(fields=(card,)),))
    items = schema["properties"]["keys"]["items"]["properties"]
    assert items["column"]["x-td-ref"] == "column"
    assert items["order"]["enum"] == ["Ascending", "Descending"]
    assert schema["properties"]["keys"]["x-td-item-default"]["order"] == "Ascending"


def test_form_choices_survive_item_schemas_already_described():
    """``node_items`` describes list items first; the editor form must still add
    its choices and column references to those same item properties."""
    schema = {
        "type": "object",
        "properties": {
            "keys": {
                "type": "array",
                "default": [],
                "items": {
                    "type": "object",
                    "properties": {
                        "column": {"type": "string", "description": "the column"},
                        "order": {"type": "string", "description": "the direction"},
                    },
                },
            }
        },
    }
    card = _field(
        "keys",
        "list",
        items=(
            _field("column", "column"),
            _field("order", "combo", options=("Ascending", "Descending")),
        ),
    )
    ns.apply_form(schema, (SimpleNamespace(fields=(card,)),))
    items = schema["properties"]["keys"]["items"]["properties"]
    assert items["order"]["enum"] == ["Ascending", "Descending"]
    assert items["order"]["description"] == "the direction"
    assert items["column"]["x-td-ref"] == "column"
    assert items["column"]["description"] == "the column"


def test_conditional_fields_are_marked():
    schema = {"type": "object", "properties": {"v": {"type": "string"}}}
    spec = _field("v", "text", show_if=lambda s: True)
    ns.apply_form(schema, (SimpleNamespace(fields=(spec,)),))
    assert schema["properties"]["v"]["x-td-conditional"] is True
