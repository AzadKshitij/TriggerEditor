"""Machine-readable node specs: what an agent needs to author a workflow.

Qt-free and import-light. ``list_ops`` reads only the op catalogue; the settings
schema of one op imports that op's ``core`` module on demand (a ``DEFAULTS``
dict, or a ``ParamsBase`` dataclass for the audit tests), never a widget.

Where a value lives in a ``.tds`` node (``content``):

* ``location == "settings"``: ``content["settings"][key]`` (shaping nodes)
* ``location == "content"``: ``content[key]`` (audit tests, File Input, Union)

The JSON Schema is *generated*: types come from the real default values, and
``apply_form`` can enrich them with labels, choices and ranges from a node's
declarative ``FORM`` (``node_spec_forms`` loads those; it needs Qt, so the
default export does not).

``SPEC_VERSION`` is a public contract: bump it when the shape of the exported
spec changes, and keep ``tests/unit/test_node_spec.py`` green.
"""

from __future__ import annotations

import copy
import dataclasses
import difflib
import importlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from trigger_designer.core.headless import node_items
from trigger_designer.core.headless.exit_codes import CliError, ExitCode
from trigger_designer.core.headless.op_catalog import OPS, OpInfo

SPEC_VERSION = 1

#: Where an op keeps its settings inside the node's ``content``.
SETTINGS = "settings"
CONTENT = "content"


@dataclass(frozen=True)
class SettingsSource:
    """Where the defaults of one op come from."""

    location: str  # SETTINGS | CONTENT
    #: ``module:attr``. ``attr`` is a dict of defaults or a ``ParamsBase`` class.
    source: str | None = None
    #: Hand-written defaults for nodes whose defaults live in a widget module
    #: (importing it would need Qt). ``test_node_spec`` pins them to the app.
    #: A callable is read on use, so it can import lazily.
    static: dict | Callable[[], dict] | None = None


_SHAPING = "trigger_designer.core.shaping."
_AUDIT = "trigger_designer.core.audit."


def _s(module: str, attr: str = "DEFAULTS") -> SettingsSource:
    return SettingsSource(SETTINGS, f"{_SHAPING}{module}:{attr}")


def _a(module: str, attr: str) -> SettingsSource:
    return SettingsSource(CONTENT, f"{_AUDIT}{module}:{attr}")


def _file_input_defaults() -> dict[str, Any]:
    from trigger_designer.core.inputs import DEFAULT_EXCLUDE

    return {**_FILE_INPUT_DEFAULTS, "exclude_patterns": list(DEFAULT_EXCLUDE)}


_FILE_INPUT_DEFAULTS: dict[str, Any] = {
    "filePath": "",
    "file_type": "csv",
    "delimiter": ",",
    "first_row_contains_field_names": True,
    "encoding": "utf8",
    "read_as_text": False,
    "start_row": 1,
    "record_limit": 0,
    "selected_sheet": "",
    "sheet_mode": "one",
    "selected_sheets": [],
    "add_sheet_name_column": False,
    "sheet_name_column_name": "SheetName",
    "include_patterns": [],
    "exclude_patterns": [],
    "recursive": False,
    "file_order": "name",
    "max_files": 10000,
    "schema_mismatch": "union",
    "on_file_error": "stop",
    "output_filename_as_field": False,
    "file_name_column_name": "FileName",
    "file_name_value": "name",
    "json_nested": "text",
    "db_mode": "table",
    "db_table": "",
    "db_query": "",
}

_UNION_DEFAULTS: dict[str, Any] = {"mode": "by_name", "column_map": []}

SETTINGS_SOURCES: dict[str, SettingsSource] = {
    "input.file_input": SettingsSource(CONTENT, static=_file_input_defaults),
    "input.file_output": _s("file_output"),
    "input.workpaper_output": SettingsSource(
        SETTINGS, "trigger_designer.core.workpaper.node_logic:DEFAULTS"
    ),
    "preparation.cleansing": _s("cleansing"),
    "preparation.filter": _s("filter"),
    "preparation.formula": _s("formula"),
    "preparation.groupby": _s("aggregate"),
    "preparation.select": _s("select"),
    "preparation.sort": _s("sort"),
    "preparation.unique": _s("unique"),
    "preparation.split": _s("split"),
    "preparation.dynamic_row_builder": _s("rows"),
    "preparation.normalize_columns": _s("normalize"),
    "preparation.record_id": _s("record_id"),
    "preparation.select_records": _s("select_records"),
    "preparation.find_replace": _s("find_replace"),
    "preparation.date_helper": _s("date_helper"),
    "preparation.text_to_columns": _s("text_to_columns"),
    "preparation.multi_field_formula": _s("multi_formula"),
    "join.append": _s("append"),
    "join.join": _s("join"),
    "join.union": SettingsSource(CONTENT, static=_UNION_DEFAULTS),
    "join.reconcile": _s("reconcile"),
    "join.fuzzy_match": _s("fuzzy"),
    "transform.count_records": _s("count"),
    "transform.running_total": _s("running_total"),
    "transform.transpose": _s("transpose"),
    "transform.pivot": _s("reshape", "PIVOT_DEFAULTS"),
    "transform.unpivot": _s("reshape", "UNPIVOT_DEFAULTS"),
    "transform.window": _s("window"),
    "transform.sql_query": _s("sql_query"),
    "report.graph": _s("graph"),
    "report.data_profile": _s("data_profile"),
    "report.comment": _s("comments"),
    "audit.duplicates": _a("duplicates", "DuplicatesParams"),
    "audit.gaps": _a("gaps", "GapsParams"),
    "audit.benford": _a("benford", "BenfordParams"),
    "audit.sample": _a("sampling", "SamplingParams"),
    "audit.risk_filters": _a("risk_filters", "RiskParams"),
}


@dataclass(frozen=True)
class Sockets:
    """The connection points of one op. ``test_node_spec`` pins them to the app."""

    inputs: int
    outputs: tuple[str, ...]
    #: Input indexes that may stay unconnected.
    optional: tuple[int, ...] = ()
    #: Union: any number of inputs (``inputs`` is the minimum shown at start).
    variadic: bool = False


SOCKETS: dict[str, Sockets] = {
    "input.file_input": Sockets(0, ("data",)),
    "input.file_output": Sockets(1, ()),
    "input.workpaper_output": Sockets(3, (), optional=(1, 2)),
    "preparation.cleansing": Sockets(1, ("cleansing",)),
    "preparation.dynamic_row_builder": Sockets(1, ("rows",)),
    "preparation.filter": Sockets(1, ("true", "false")),
    "preparation.formula": Sockets(1, ("formula",)),
    "preparation.groupby": Sockets(1, ("aggregate",)),
    "preparation.select": Sockets(1, ("select",)),
    "preparation.sort": Sockets(1, ("sort",)),
    "preparation.split": Sockets(1, ("estimation", "validation")),
    "preparation.unique": Sockets(1, ("unique", "duplicates")),
    "preparation.normalize_columns": Sockets(1, ("normalize",)),
    "preparation.record_id": Sockets(1, ("recordid",)),
    "preparation.select_records": Sockets(1, ("records_sel", "records_rest")),
    "preparation.find_replace": Sockets(1, ("find_replace",)),
    "preparation.date_helper": Sockets(1, ("date_helper",)),
    "preparation.multi_field_formula": Sockets(1, ("multi_field_formula",)),
    "preparation.text_to_columns": Sockets(1, ("text_to_columns",)),
    "join.append": Sockets(2, ("append",)),
    "join.union": Sockets(1, ("union",), variadic=True),
    "join.join": Sockets(2, ("left", "join", "right")),
    "join.reconcile": Sockets(
        2, ("recon_matched", "recon_left", "recon_right", "recon_summary")
    ),
    "join.fuzzy_match": Sockets(2, ("fuzzy_matched", "fuzzy_left", "fuzzy_right")),
    "transform.count_records": Sockets(1, ("count",)),
    "transform.running_total": Sockets(1, ("running_total",)),
    "transform.transpose": Sockets(1, ("transpose",)),
    "transform.pivot": Sockets(1, ("pivot",)),
    "transform.unpivot": Sockets(1, ("unpivot",)),
    "transform.window": Sockets(1, ("window",)),
    "transform.sql_query": Sockets(3, ("sql",), optional=(1, 2)),
    "report.graph": Sockets(1, ("graph",)),
    "report.data_profile": Sockets(1, ("data", "profile")),
    "report.comment": Sockets(0, ()),
    "audit.benford": Sockets(1, ("benford", "benfordsum", "benforddrill")),
    "audit.gaps": Sockets(1, ("gaps", "gapsum")),
    "audit.duplicates": Sockets(1, ("dup", "uniq", "dupsum")),
    "audit.risk_filters": Sockets(1, ("riskflag", "risknone", "risksum")),
    "audit.sample": Sockets(1, ("sample", "notsampled", "samplelog")),
}

DESCRIPTIONS: dict[str, str] = {
    "input.file_input": "Reads a CSV, Excel, JSON, Parquet, text or database source (or a folder of files) into a table.",
    "input.file_output": "Writes its input table to a file. Files are written only by a real run, never while editing.",
    "input.workpaper_output": "Writes an audit workpaper (Excel) with the test result, exceptions, the run log and the workflow.",
    "preparation.cleansing": "Cleans text columns: trims spaces, fixes case, removes unwanted characters.",
    "preparation.filter": "Splits a table into rows that meet a condition (true) and rows that do not (false). Comparisons follow the column type: text compares as text, so convert numbers stored as text with Select first.",
    "preparation.formula": "Adds or replaces columns using SQL expressions.",
    "preparation.groupby": "Groups rows and calculates sums, counts, means and other aggregates per group.",
    "preparation.select": "Chooses, renames, reorders and retypes columns.",
    "preparation.sort": "Sorts rows by one or more columns.",
    "preparation.unique": "Splits rows into first occurrences (unique) and every row of a repeated key (duplicates).",
    "preparation.split": "Splits rows randomly into an estimation set and a validation set.",
    "preparation.dynamic_row_builder": "Creates rows from rules, such as number or date sequences.",
    "preparation.normalize_columns": "Normalises column names (case, spaces, symbols) so files line up.",
    "preparation.record_id": "Adds a sequential or unique record identifier column.",
    "preparation.select_records": "Keeps a range or sample of rows and sends the rest to a second output.",
    "preparation.find_replace": "Finds and replaces text in selected columns using rules.",
    "preparation.date_helper": "Parses dates and adds parts or differences (year, month, weekday, days between).",
    "preparation.text_to_columns": "Splits one text column into several columns on a delimiter.",
    "preparation.multi_field_formula": "Applies one expression template to many columns at once.",
    "join.append": "Puts the rows of the second input under the rows of the first.",
    "join.union": "Stacks any number of inputs vertically, with control over how columns line up.",
    "join.join": "Matches rows of two inputs on keys; outputs left-only, matched and right-only rows.",
    "join.reconcile": "Matches two lists on keys, an amount (with tolerance) and a date window, and reports the differences.",
    "join.fuzzy_match": "Matches names or descriptions that are similar but not identical.",
    "transform.count_records": "Counts the rows of the input.",
    "transform.running_total": "Adds a running (cumulative) total of a numeric column.",
    "transform.transpose": "Turns rows into columns and columns into rows.",
    "transform.pivot": "Spreads the values of one column across new columns.",
    "transform.unpivot": "Gathers several columns into name/value rows.",
    "transform.window": "Adds window calculations: lag, lead, rank, running and rolling values.",
    "transform.sql_query": "Runs a read-only SQL SELECT over up to three inputs (t1, t2, t3).",
    "report.graph": "Draws a line, bar or scatter chart of a table.",
    "report.data_profile": "Checks table quality: nulls, distinct values, numbers stored as text, odd values.",
    "report.comment": "A note on the canvas for the author or reviewer. Carries no data.",
    "audit.duplicates": "Audit test: finds duplicate records on chosen key columns.",
    "audit.gaps": "Audit test: finds gaps in a numeric or date sequence.",
    "audit.benford": "Audit test: compares leading digits of an amount column with Benford's law.",
    "audit.sample": "Audit test: draws a monetary-unit, random or stratified sample.",
    "audit.risk_filters": "Audit test: flags records matching risk indicators (round amounts, weekends, and so on).",
}

#: Page of the node's documentation, relative to the repository's ``docs/``.
DOC_PAGES: dict[str, str] = {
    "input.file_input": "nodes/input-output/file-input.md",
    "input.file_output": "nodes/input-output/file-output.md",
    "input.workpaper_output": "nodes/input-output/workpaper-output.md",
    "preparation.cleansing": "nodes/preparation/cleansing.md",
    "preparation.filter": "nodes/preparation/filter.md",
    "preparation.formula": "nodes/preparation/formula.md",
    "preparation.groupby": "nodes/preparation/aggregate.md",
    "preparation.select": "nodes/preparation/select.md",
    "preparation.sort": "nodes/preparation/sort.md",
    "preparation.unique": "nodes/preparation/unique.md",
    "preparation.split": "nodes/preparation/split.md",
    "preparation.dynamic_row_builder": "nodes/preparation/rows.md",
    "preparation.normalize_columns": "nodes/preparation/normalize.md",
    "preparation.record_id": "nodes/preparation/record-id.md",
    "preparation.select_records": "nodes/preparation/select-records.md",
    "preparation.find_replace": "nodes/preparation/find-and-replace.md",
    "preparation.date_helper": "nodes/preparation/date-helper.md",
    "preparation.text_to_columns": "nodes/preparation/text-to-columns.md",
    "preparation.multi_field_formula": "nodes/preparation/multi-field-formula.md",
    "join.append": "nodes/join/append.md",
    "join.union": "nodes/join/union.md",
    "join.join": "nodes/join/join.md",
    "join.reconcile": "nodes/join/reconcile.md",
    "join.fuzzy_match": "nodes/join/fuzzy-match.md",
    "transform.count_records": "nodes/transform/count.md",
    "transform.running_total": "nodes/transform/running-total.md",
    "transform.transpose": "nodes/transform/transpose.md",
    "transform.pivot": "nodes/transform/pivot.md",
    "transform.unpivot": "nodes/transform/unpivot.md",
    "transform.window": "nodes/transform/window.md",
    "transform.sql_query": "nodes/transform/sql-query.md",
    "report.graph": "nodes/report/graph.md",
    "report.data_profile": "nodes/report/data-profile.md",
    "report.comment": "nodes/report/comment.md",
    "audit.duplicates": "nodes/audit/duplicates.md",
    "audit.gaps": "nodes/audit/gaps.md",
    "audit.benford": "nodes/audit/benford.md",
    "audit.sample": "nodes/audit/sample.md",
    "audit.risk_filters": "nodes/audit/risk-filters.md",
}

#: Settings that work when the node is wired up. Each is checked by running the
#: node's own ``run_node`` in ``tests/unit/test_node_spec.py``.
EXAMPLES: dict[str, dict[str, Any]] = {
    "preparation.filter": {
        "mode": "builder",
        "column": "Amount",
        "operation": "Greater Than",
        "value": "10000",
        "value2": "",
        "expression": "",
    },
    "preparation.sort": {"keys": [{"column": "Amount", "order": "Descending"}]},
    # ``dtype_custom: true`` is what makes the editor keep a chosen type; without
    # it the editor resets the column to the type it arrives with.
    "preparation.select": {
        "columns": [
            {
                "name": "Amount",
                "selected": True,
                "dtype": "Float64",
                "rename": "",
                "date_format": "",
                "dtype_custom": True,
            },
            {
                "name": "InvoiceNo",
                "selected": True,
                "dtype": "String",
                "rename": "",
                "date_format": "",
                "dtype_custom": False,
            },
        ],
        "auto_accept_new_columns": True,
    },
    "preparation.unique": {"selected_columns": ["InvoiceNo"]},
    "transform.sql_query": {
        "sql": 'SELECT "Vendor", SUM(TRY_CAST("Amount" AS DOUBLE)) AS total\n'
        'FROM t1\nGROUP BY "Vendor"'
    },
    "input.file_output": {
        "filePath": "output/result.csv",
        "file_format": "csv",
        "delimiter": ",",
        "include_bom": False,
        "compression": "snappy",
    },
    "input.file_input": {"filePath": "data/invoices.csv", "file_type": "csv"},
    "join.union": {"mode": "by_name", "column_map": []},
}


# The list-valued ops' examples live next to their item schemas.
for _op, _example in node_items.EXAMPLES.items():
    EXAMPLES.setdefault(_op, _example)


# --------------------------------------------------------------------- schema
def infer_schema(value: Any) -> dict:
    """A JSON Schema fragment for a default value. ``bool`` is tested before
    ``int`` (it is one); an empty list says nothing about its items."""
    if isinstance(value, bool):
        return {"type": "boolean"}
    if isinstance(value, int):
        return {"type": "integer"}
    if isinstance(value, float):
        return {"type": "number"}
    if isinstance(value, str):
        return {"type": "string"}
    if isinstance(value, (list, tuple)):
        schema: dict = {"type": "array"}
        if value:
            schema["items"] = infer_schema(value[0])
        return schema
    if isinstance(value, dict):
        return {
            "type": "object",
            "properties": {str(k): infer_schema(v) for k, v in value.items()},
        }
    return {}


def _param_defaults(cls: type) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for f in dataclasses.fields(cls):
        if f.default_factory is not dataclasses.MISSING:
            out[f.name] = f.default_factory()
        elif f.default is not dataclasses.MISSING:
            out[f.name] = f.default
    return out


def settings_defaults(op: str) -> dict[str, Any]:
    """A fresh copy of the op's default settings (``{}`` when it has none)."""
    source = SETTINGS_SOURCES.get(op)
    if source is None:
        return {}
    if source.static is not None:
        static = source.static() if callable(source.static) else source.static
        return copy.deepcopy(static)
    assert source.source is not None
    module_name, _, attr = source.source.partition(":")
    target = getattr(importlib.import_module(module_name), attr)
    if isinstance(target, type):
        return _param_defaults(target)
    return copy.deepcopy(dict(target))


def _plain(value: Any) -> Any:
    """JSON-able: tuples become lists, unknown objects become text."""
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_plain(v) for v in value]
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


def settings_schema(op: str, forms: dict[str, tuple] | None = None) -> dict:
    """The JSON Schema of the op's settings object.

    Top level is closed (``additionalProperties: false``): an agent must not
    invent keys. ``forms`` maps op -> ``FORM`` sections to enrich the schema.
    """
    defaults = _plain(settings_defaults(op))
    properties = {}
    for key, value in defaults.items():
        prop = infer_schema(value)
        prop.update(copy.deepcopy(node_items.PROPS.get((op, key), {})))
        prop["default"] = value
        properties[key] = prop
    schema = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    form = (forms or {}).get(op)
    if form:
        apply_form(schema, form)
    return schema


# ------------------------------------------------------------------- FORM
_CHOICE_KINDS = ("combo", "segment")
_COLUMN_KINDS = {"column": "column", "picker": "columns", "columns": "columns"}


def _option_values(options: tuple) -> list:
    values = []
    for option in options or ():
        values.append(option[0] if isinstance(option, (tuple, list)) else option)
    return [_plain(v) for v in values]


def _flatten(fields) -> list:
    """The leaf fields; a ``pair`` is two fields on one row."""
    flat = []
    for spec in fields or ():
        if getattr(spec, "kind", "") == "pair":
            flat.extend(_flatten(spec.items))
        else:
            flat.append(spec)
    return flat


def _field_schema(spec) -> dict:
    kind = spec.kind
    prop: dict = {}
    if kind in _CHOICE_KINDS:
        prop["enum"] = _option_values(spec.options)
    elif kind in ("choices", "weekdays"):
        prop.update(type="array", items={"enum": _option_values(spec.options)})
    elif kind == "check":
        prop["type"] = "boolean"
    elif kind == "int":
        prop.update(type="integer", minimum=spec.minimum, maximum=spec.maximum)
    elif kind == "float":
        prop.update(type="number", minimum=spec.minimum, maximum=spec.maximum)
    elif kind in ("text", "textarea", "suffix"):
        prop["type"] = "string"
    elif kind in _COLUMN_KINDS:
        prop["x-td-ref"] = _COLUMN_KINDS[kind]
    elif kind == "list":
        item_props = {}
        for sub in _flatten(spec.items):
            if sub.kind != "note" and not sub.key.startswith("_"):
                item_props[sub.key] = _field_schema(sub)
        prop.update(
            type="array",
            items={"type": "object", "properties": item_props},
            maxItems=spec.max_items,
        )
        if spec.item_default:
            prop["x-td-item-default"] = _plain(spec.item_default)
    if spec.label:
        prop["title"] = spec.label
    text = spec.tip or spec.hint
    if text:
        prop["description"] = text
    if spec.show_if is not None:
        prop["x-td-conditional"] = True
    return prop


def _merge(target: dict, extra: dict) -> None:
    """Add ``extra`` to ``target``. The type inferred from the real default wins
    over a weaker form hint; everything else (choices, ranges, text) is added."""
    for key, value in extra.items():
        if key == "properties" and isinstance(value, dict):
            # Each property is itself a schema: merge it, do not let one that
            # ``node_items`` already described hide the form's choices.
            into = target.setdefault("properties", {})
            for name, sub in value.items():
                if isinstance(sub, dict) and isinstance(into.get(name), dict):
                    _merge(into[name], sub)
                else:
                    into.setdefault(name, sub)
            continue
        if (
            key == "items"
            and isinstance(value, dict)
            and isinstance(target.get(key), dict)
        ):
            _merge(target[key], value)
            continue
        if key == "type" and key in target:
            continue
        target.setdefault(key, value)


def apply_form(schema: dict, form: tuple) -> dict:
    """Enrich ``schema`` in place from ``FormSection`` objects (duck-typed)."""
    properties = schema.setdefault("properties", {})
    for section in form:
        for spec in _flatten(getattr(section, "fields", ())):
            if spec.kind == "note" or spec.key.startswith("_"):
                continue
            prop = properties.get(spec.key)
            if prop is None:
                continue  # a form key with no default is not a stored setting
            _merge(prop, _field_schema(spec))
    return schema


# -------------------------------------------------------------------- export
def _sockets(op: str) -> dict:
    sockets = SOCKETS[op]
    inputs = [
        {"index": i, "required": i not in sockets.optional}
        for i in range(sockets.inputs)
    ]
    return {
        "inputs": inputs,
        "inputs_variadic": sockets.variadic,
        "outputs": [{"index": i, "name": n} for i, n in enumerate(sockets.outputs)],
    }


def _info(op: str) -> OpInfo:
    info = OPS.get(op)
    if info is None:
        near = difflib.get_close_matches(op, list(OPS), n=3, cutoff=0.5)
        hint = "Run `ops` to list every op id."
        if near:
            hint = "Did you mean: " + ", ".join(near) + "? " + hint
        raise CliError(
            ExitCode.INVALID, "TD-CLI-003", f"Unknown node type '{op}'.", hint
        )
    return info


def _file_keys(info: OpInfo) -> dict:
    return {
        "reads": list(info.input_keys),
        "writes": list(info.output_keys),
        "reads_many": list(info.list_keys),
    }


def summarize_op(op: str) -> dict:
    """One catalogue row: no settings, so nothing heavy is imported."""
    info = _info(op)
    return {
        "op": op,
        "title": info.title,
        "family": info.family,
        "description": DESCRIPTIONS.get(op, ""),
        "docs": f"docs/{DOC_PAGES[op]}" if op in DOC_PAGES else None,
        "planned": info.planned,
        **_sockets(op),
    }


def list_ops(*, include_planned: bool = False) -> list[dict]:
    return [
        summarize_op(op)
        for op, info in OPS.items()
        if (include_planned or not info.planned) and op in SOCKETS
    ]


def describe_op(op: str, forms: dict[str, tuple] | None = None) -> dict:
    """The full spec of one op: sockets, settings schema, defaults, example."""
    info = _info(op)
    spec = summarize_op(op)
    source = SETTINGS_SOURCES.get(op)
    defaults = _plain(settings_defaults(op))
    spec.update(
        {
            "files": _file_keys(info),
            "custom_code": info.custom_code,
            "settings": {
                "location": source.location if source else SETTINGS,
                "path": (
                    "content.settings"
                    if source and source.location == SETTINGS
                    else "content"
                ),
                "schema": settings_schema(op, forms),
                "defaults": defaults,
                "example": EXAMPLES.get(op, defaults),
                "example_is_default": op not in EXAMPLES,
            },
        }
    )
    return spec


def export_all(forms: dict[str, tuple] | None = None) -> dict:
    """Every op's full spec in one document (``ops --all``)."""
    from trigger_designer.core.constants import VERSION, WORKFLOW_SCHEMA_VERSION

    return {
        "spec_version": SPEC_VERSION,
        "app_version": VERSION,
        "workflow_schema_version": WORKFLOW_SCHEMA_VERSION,
        "ops": [describe_op(row["op"], forms) for row in list_ops()],
    }
