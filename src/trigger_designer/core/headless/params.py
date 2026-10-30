"""Run-time parameters and path remapping applied to a copy of a workflow.

Plan 08 3.5 / S2. The workflow file on disk is never modified by a run: the
patched JSON is written to a work copy and that copy is what the editor's own
loader reads.
"""

from __future__ import annotations

import copy
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from trigger_designer.core.headless.atomic import write_bytes_atomic
from trigger_designer.core.headless.exit_codes import CliError, ExitCode
from trigger_designer.core.headless.op_catalog import known_op, node_op
from trigger_designer.core.headless.paths import (
    remap_into_dir,
    resolve_workflow_path,
)
from trigger_designer.core.headless.workflow_file import (
    WorkflowDoc,
    settings_holder,
)

NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
PARAM_TYPES = ("path_in", "path_out", "string", "int")
_BAD_TEXT = "'\\\r\n\x00"
_DB_TABLE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]{0,127}$")


@dataclass(frozen=True)
class Rule:
    kind: str  # one of PARAM_TYPES
    lo: int | None = None
    hi: int | None = None
    forbid: str = ""
    pattern: re.Pattern | None = None
    #: Settings of the same node that must hold these values.
    needs: tuple[tuple[str, str], ...] = ()
    #: Stored as a list (comma-separated on the command line).
    as_list: bool = False


PARAM_TARGETS: dict[tuple[str, str], Rule] = {
    ("input.file_input", "filePath"): Rule("path_in"),
    ("input.file_input", "include_patterns"): Rule(
        "string", forbid=_BAD_TEXT, as_list=True
    ),
    ("input.file_input", "exclude_patterns"): Rule(
        "string", forbid=_BAD_TEXT, as_list=True
    ),
    ("input.file_input", "max_files"): Rule("int", 1, 100_000),
    ("input.file_input", "db_table"): Rule("string", pattern=_DB_TABLE_RE),
    ("input.file_input", "selected_sheet"): Rule("string", forbid=_BAD_TEXT),
    ("input.file_input", "record_limit"): Rule("int", 0, 2_000_000_000),
    ("input.file_output", "filePath"): Rule("path_out"),
    ("preparation.filter", "value"): Rule(
        "string", forbid=_BAD_TEXT, needs=(("mode", "builder"),)
    ),
    ("preparation.filter", "value2"): Rule(
        "string", forbid=_BAD_TEXT, needs=(("mode", "builder"),)
    ),
    ("preparation.split", "random_seed"): Rule("int", 0, 2**31 - 1),
    ("preparation.split", "estimation_percent"): Rule("int", 1, 99),
}


@dataclass(frozen=True)
class ParamDef:
    name: str
    type: str
    node_id: int
    setting: str
    default: str | None = None
    required: bool = False
    label: str = ""

    def to_dict(self) -> dict:
        out = {
            "name": self.name,
            "label": self.label or self.name,
            "type": self.type,
            "node_id": self.node_id,
            "setting": self.setting,
            "required": self.required,
        }
        out["default"] = self.default
        return out


@dataclass
class PathRef:
    node_id: int
    title: str
    kind: str  # "input" | "output"
    key: str
    saved: str
    path: str  # resolved absolute path
    bound: str | None = None  # parameter name, if any


@dataclass
class AppliedParams:
    data: dict
    resolved: dict[str, str] = field(default_factory=dict)
    inputs: list[PathRef] = field(default_factory=list)
    outputs: list[PathRef] = field(default_factory=list)


# ----------------------------------------------------------------- parsing
def parse_cli_params(items: list[str]) -> dict[str, str]:
    """``NAME=VALUE`` items; split on the first ``=``; later ones win."""
    out: dict[str, str] = {}
    for item in items or []:
        name, sep, value = item.partition("=")
        if not sep or not name.strip():
            raise CliError(
                ExitCode.INVALID,
                "TD-CLI-006",
                f"--param '{item}' must look like NAME=VALUE.",
                "Example: --param input_file=D:\\in\\today.csv",
            )
        out[name.strip()] = value
    return out


def _node_by_id(data: dict) -> dict:
    return {n.get("id"): n for n in data.get("nodes", []) if isinstance(n, dict)}


def read_param_defs(doc: WorkflowDoc) -> list[ParamDef]:
    raw = doc.metadata.get("parameters") or []
    if not isinstance(raw, list):
        raise CliError(
            ExitCode.INVALID,
            "TD-CLI-006",
            "workflow_metadata.parameters is not a list.",
        )
    nodes = _node_by_id(doc.data)
    defs: list[ParamDef] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            raise CliError(
                ExitCode.INVALID, "TD-CLI-006", "A parameter entry is not an object."
            )
        name = str(item.get("name") or "")
        if not NAME_RE.match(name):
            raise CliError(
                ExitCode.INVALID,
                "TD-CLI-006",
                f"Parameter name '{name}' is not valid (lower case letters, digits, _; "
                "starts with a letter).",
            )
        if name in seen:
            raise CliError(
                ExitCode.INVALID, "TD-CLI-006", f"Duplicate parameter name '{name}'."
            )
        seen.add(name)
        ptype = str(item.get("type") or "")
        if ptype not in PARAM_TYPES:
            raise CliError(
                ExitCode.INVALID,
                "TD-CLI-006",
                f"Parameter '{name}' has an unknown type '{ptype}'.",
            )
        node_id = item.get("node_id")
        setting = str(item.get("setting") or "")
        node = nodes.get(node_id)
        if node is None:
            raise CliError(
                ExitCode.INVALID,
                "TD-CLI-007",
                f"Parameter '{name}' points at node {node_id}, which does not exist.",
            )
        rule = PARAM_TARGETS.get((node_op(node) or "", setting))
        if rule is None or rule.kind != ptype:
            raise CliError(
                ExitCode.INVALID,
                "TD-CLI-007",
                f"Parameter '{name}': {node_op(node)}.{setting} ({ptype}) cannot be "
                "set from the command line.",
            )
        default = item.get("default")
        defs.append(
            ParamDef(
                name=name,
                type=ptype,
                node_id=node_id,
                setting=setting,
                default=None if default is None else str(default),
                required=bool(item.get("required", False)),
                label=str(item.get("label") or ""),
            )
        )
    return defs


# -------------------------------------------------------------- validation
def _check_value(name: str, rule: Rule, value: str) -> str | int | list[str]:
    if rule.kind == "int":
        if not re.fullmatch(r"-?[0-9]+", value.strip()):
            raise CliError(
                ExitCode.INVALID,
                "TD-CLI-006",
                f"Parameter '{name}' needs a whole number, got '{value}'.",
                f"Example: --param {name}=100",
            )
        number = int(value.strip())
        if (rule.lo is not None and number < rule.lo) or (
            rule.hi is not None and number > rule.hi
        ):
            raise CliError(
                ExitCode.INVALID,
                "TD-CLI-006",
                f"Parameter '{name}' must be between {rule.lo} and {rule.hi}.",
            )
        return number
    if rule.kind == "string":
        if any(ch in value for ch in rule.forbid):
            raise CliError(
                ExitCode.INVALID,
                "TD-CLI-006",
                f"Parameter '{name}' contains a character that is not allowed "
                "(quote, backslash or line break).",
            )
        if rule.pattern is not None and not rule.pattern.match(value):
            raise CliError(
                ExitCode.INVALID,
                "TD-CLI-006",
                f"Parameter '{name}' is not a valid name: '{value}'.",
            )
        if rule.as_list:
            return [part.strip() for part in value.split(",") if part.strip()]
        return value
    return value


def _check_needs(name: str, rule: Rule, node: dict) -> None:
    content = node.get("content") if isinstance(node.get("content"), dict) else {}
    for key, expected in rule.needs:
        holder = settings_holder(content, key)
        actual = str(holder.get(key) or expected) if holder else expected
        if actual != expected:
            raise CliError(
                ExitCode.INVALID,
                "TD-CLI-007",
                f"Parameter '{name}' cannot be set while the node's {key} is '{actual}'.",
                "Only builder-mode filter values can be parameters.",
            )


def set_setting(content: dict, key: str, value) -> None:
    holder = settings_holder(content, key)
    if holder is None:
        settings = content.get("settings")
        holder = settings if isinstance(settings, dict) else content
    holder[key] = value


def get_setting(content: dict, key: str) -> str:
    holder = settings_holder(content, key)
    return str(holder.get(key) or "") if holder else ""


def _cwd_path(value: str, cwd: str) -> str:
    """A path given on the command line resolves against the invoker's CWD."""
    return resolve_workflow_path(value, base_dir=cwd)


def _saved_input_path(content: dict, base_dir: str) -> str:
    """The path the editor would use: ``filePathRel`` first when it exists."""
    raw = get_setting(content, "filePath")
    rel = get_setting(content, "filePathRel")
    if rel and base_dir:
        candidate = os.path.normpath(os.path.join(base_dir, rel))
        probe = candidate
        if any(ch in candidate for ch in "*?["):
            from trigger_designer.core.inputs import _glob_dir

            probe = _glob_dir(candidate)
        if os.path.exists(probe):
            return candidate
    return raw


def apply_params(
    doc: WorkflowDoc,
    defs: list[ParamDef],
    overrides: dict[str, str],
    *,
    input_dir: str | None = None,
    output_dir: str | None = None,
    cwd: str | None = None,
) -> AppliedParams:
    """Patch a deep copy of the workflow; see plan 3.5 for the precedence."""
    cwd = cwd or os.getcwd()
    by_name = {d.name: d for d in defs}
    unknown = sorted(set(overrides) - set(by_name))
    if unknown:
        raise CliError(
            ExitCode.INVALID,
            "TD-CLI-005",
            f"Unknown parameter {', '.join(repr(n) for n in unknown)}. "
            f"Known parameters: {', '.join(sorted(by_name)) or '(none)'}.",
            "Run `params list <workflow>` to see the available names.",
        )
    in_dir = os.path.abspath(os.path.join(cwd, input_dir)) if input_dir else None
    out_dir = os.path.abspath(os.path.join(cwd, output_dir)) if output_dir else None
    base = doc.base_dir
    data = copy.deepcopy(doc.data)
    nodes = _node_by_id(data)
    applied = AppliedParams(data=data)
    bound_path: dict[tuple[object, str], str] = {}

    for pdef in defs:
        node = nodes[pdef.node_id]
        op = node_op(node) or ""
        rule = PARAM_TARGETS[(op, pdef.setting)]
        content = node.setdefault("content", {})
        explicit = overrides.get(pdef.name)
        if explicit is None and pdef.default is None and pdef.required:
            raise CliError(
                ExitCode.INVALID,
                "TD-CLI-005",
                f"Required parameter '{pdef.name}' was not given.",
                f"Pass --param {pdef.name}=VALUE.",
            )
        if rule.needs and (explicit is not None or pdef.default is not None):
            _check_needs(pdef.name, rule, node)
        if rule.kind in ("path_in", "path_out"):
            directory = in_dir if rule.kind == "path_in" else out_dir
            if explicit is not None:
                path = _cwd_path(explicit, cwd)
            else:
                source = pdef.default or get_setting(content, pdef.setting)
                if directory and source:
                    path = remap_into_dir(source, directory)
                elif pdef.default:
                    path = resolve_workflow_path(pdef.default, base_dir=base)
                else:
                    continue  # nothing bound: the unbound pass below handles it
            set_setting(content, pdef.setting, path)
            if rule.kind == "path_in":
                content.pop("filePathRel", None)
            applied.resolved[pdef.name] = path
            bound_path[(node.get("id"), pdef.setting)] = pdef.name
            continue
        value = explicit if explicit is not None else pdef.default
        if value is None:
            continue
        checked = _check_value(pdef.name, rule, value)
        set_setting(content, pdef.setting, checked)
        applied.resolved[pdef.name] = value

    # Every File Input/Output (and any other node holding an output path).
    for node in data.get("nodes", []):
        if not isinstance(node, dict):
            continue
        op = node_op(node) or ""
        info = known_op(op)
        title = str(node.get("title") or node.get("node_title") or "")
        content = node.get("content")
        if not isinstance(content, dict):
            continue
        if op == "input.file_input" or (not op and title == "File Input"):
            ref = _resolve_node_path(
                node,
                content,
                "filePath",
                "input",
                in_dir,
                base,
                bound_path,
                applied,
                title,
            )
            if ref:
                applied.inputs.append(ref)
        keys = info.output_keys if info else ()
        if not keys and (
            op == "input.file_output" or (not op and title == "File Output")
        ):
            keys = ("filePath",)
        for key in keys:
            ref = _resolve_node_path(
                node, content, key, "output", out_dir, base, bound_path, applied, title
            )
            if ref:
                applied.outputs.append(ref)
    return applied


def _resolve_node_path(
    node, content, key, kind, directory, base, bound_path, applied, title
) -> PathRef | None:
    node_id = node.get("id")
    saved = get_setting(content, key)
    if kind == "input":
        saved = _saved_input_path(content, base) if key == "filePath" else saved
    name = bound_path.get((node_id, key))
    if name is not None:
        return PathRef(
            node_id, title, kind, key, saved, get_setting(content, key), name
        )
    if not saved:
        return None
    if directory:
        path = remap_into_dir(saved, directory)
    else:
        path = resolve_workflow_path(saved, base_dir=base)
    set_setting(content, key, path)
    if kind == "input":
        content.pop("filePathRel", None)
    return PathRef(node_id, title, kind, key, saved, path)


# ---------------------------------------------------------- file rewriting
def dump_workflow(data: dict) -> bytes:
    """UTF-8 JSON for files we rewrite for the user (``params``, ``paths``)."""
    return (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def write_workflow_ascii(data: dict, path: Path) -> None:
    """The work copy: ASCII-only JSON survives any locale decode (plan 3.5)."""
    write_bytes_atomic(Path(path), json.dumps(data, ensure_ascii=True).encode("ascii"))


def backup_once(path: str) -> str | None:
    """Copy ``path`` to ``path.bak`` unless a backup already exists."""
    bak = path + ".bak"
    if os.path.exists(bak):
        return None
    Path(bak).write_bytes(Path(path).read_bytes())
    return bak


def write_workflow_with_backup(path: str, data: dict) -> str | None:
    bak = backup_once(path)
    write_bytes_atomic(Path(path), dump_workflow(data))
    return bak


def find_node(doc: WorkflowDoc, id_or_title: str) -> dict:
    """A node by numeric id or by (unique) title."""
    nodes = doc.nodes
    try:
        wanted = int(id_or_title)
    except ValueError:
        wanted = None
    if wanted is not None:
        for node in nodes:
            if node.get("id") == wanted:
                return node
    matches = [n for n in nodes if str(n.get("title") or "") == id_or_title]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise CliError(
            ExitCode.INVALID, "TD-CLI-007", f"No node with id or title '{id_or_title}'."
        )
    ids = ", ".join(str(n.get("id")) for n in matches)
    raise CliError(
        ExitCode.INVALID,
        "TD-CLI-007",
        f"{len(matches)} nodes are titled '{id_or_title}' (ids {ids}).",
        "Pass the node id instead.",
    )
