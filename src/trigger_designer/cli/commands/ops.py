"""``ops``: the node catalogue, as data an agent (or a person) can read.

``ops`` lists every node type; ``ops OP`` describes one (sockets, settings
schema, defaults, an example, the docs page); ``--all`` exports everything in
one document. ``--forms`` enriches the schemas with the labels, choices and
ranges of each node's editor form; that loads the editor's classes, so it is
slower and the only variant that needs Qt.
"""

from __future__ import annotations

import json

from trigger_designer.cli.output import print_json
from trigger_designer.cli.render import Out, Table
from trigger_designer.core.headless import node_spec
from trigger_designer.core.headless.exit_codes import CliError, ExitCode


def _forms(args) -> dict | None:
    if not args.forms:
        return None
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from trigger_designer.core.headless.node_spec_forms import load_forms

    return load_forms()


def _inputs_text(row: dict) -> str:
    count = len(row["inputs"])
    if row["inputs_variadic"]:
        return f"{count}+"
    optional = sum(1 for i in row["inputs"] if not i["required"])
    return f"{count}" + (f" ({optional} opt)" if optional else "")


def _outputs_text(row: dict) -> str:
    return ", ".join(o["name"] for o in row["outputs"]) or "none"


def render_list(rows: list[dict], out: Out) -> None:
    out.table(
        Table(
            ["op", "title", "in", "out", "description"],
            [
                [
                    r["op"],
                    r["title"],
                    _inputs_text(r),
                    _outputs_text(r),
                    r["description"],
                ]
                for r in rows
            ],
            wrap=("out", "description"),
        )
    )


def _choices(prop: dict) -> str:
    return ", ".join(json.dumps(v, ensure_ascii=False) for v in prop.get("enum", []))


def render_one(spec: dict, out: Out) -> None:
    settings = spec["settings"]
    out.heading(f"{spec['op']}  ({spec['title']})")
    if spec["description"]:
        out.line(spec["description"])
    out.line(f"sockets:   {_inputs_text(spec)} -> {_outputs_text(spec)}")
    out.line(f"settings:  {settings['path']}")
    if spec["docs"]:
        out.line(f"docs:      {spec['docs']}")
    props = settings["schema"]["properties"]
    if props:
        out.table(
            Table(
                ["setting", "type", "default", "choices"],
                [
                    [
                        key,
                        prop.get("type") or ("choice" if "enum" in prop else "any"),
                        json.dumps(prop.get("default"), ensure_ascii=False),
                        _choices(prop),
                    ]
                    for key, prop in props.items()
                ],
                wrap=("choices",),
            )
        )
    else:
        out.line("(no settings)")
    label = "default" if settings["example_is_default"] else "example"
    out.line(f"{label}: {json.dumps(settings['example'], ensure_ascii=False)}")


def execute(args, ctx) -> int:
    forms = _forms(args)
    as_json = args.format == "json"
    if args.all and args.op:
        raise CliError(
            ExitCode.USAGE, "TD-CLI-006", "Give an op id or --all, not both."
        )
    if args.all:
        doc = node_spec.export_all(forms)
        if as_json:
            print_json(doc)
        else:
            print("\n\n".join(render_one(spec) for spec in doc["ops"]))
        return 0
    if args.op:
        spec = node_spec.describe_op(args.op, forms)
        if as_json:
            print_json(spec)
        else:
            render_one(spec, Out())
        return 0
    rows = node_spec.list_ops()
    if as_json:
        print_json({"spec_version": node_spec.SPEC_VERSION, "ops": rows})
    else:
        render_list(rows, Out())
    return 0
