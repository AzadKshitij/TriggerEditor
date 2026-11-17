"""The ``trigger-designer-cli`` command line (plan 08 3.3, Appendix B).

Stdlib ``argparse`` only: ``--help`` and ``--version`` start in tens of
milliseconds because nothing heavy is imported here.
"""

from __future__ import annotations

import argparse
import sys

from trigger_designer.core.constants import VERSION, WORKFLOW_SCHEMA_VERSION
from trigger_designer.core.headless.exit_codes import ExitCode

PROG = "trigger-designer-cli"

TOP_EPILOG = """\
exit codes: 0 ok, 1 node failed, 2 invalid workflow/input, 3 internal error,
  4 timeout, 5 memory limit, 6 refused by safety policy, 7 already running,
  8 could not write outputs, 9 scheduler error, 10 verification failed,
  64 bad command line, 130 cancelled.

output: tables are plain ASCII when piped; on a terminal they use colour if the
  optional `rich` package is installed. --color never|always|auto decides;
  NO_COLOR (any value) and TRIGGER_DESIGNER_COLOR=never|always are honoured.
  --json output is never styled.

Run `trigger-designer-cli <command> --help` for the options of one command.
Example:
  trigger-designer-cli run sales.tds --param input_file=D:\\in\\today.csv
"""

RUN_DESCRIPTION = """\
Run WORKFLOW (a .tds file). Outputs are written to temporary files and moved
into place only if every node succeeds, so a failed or cancelled run never
leaves a half-written output.

Ctrl+C asks the run to stop after the current node. A node that is already
running cannot be interrupted; after --cancel-grace seconds the process exits
(130). Outputs are not touched in that case.
"""

RUN_EPILOG = """\
Example:
  trigger-designer-cli run sales.tds --param input_file=D:\\in\\today.csv --log-format json
"""

VALIDATE_DESCRIPTION = """\
Check the file without running it. Default (fast, no editor libraries): JSON
structure, schema version, node types, cycles. --deep also loads the workflow
like the editor does, resolves inputs, and checks the code each node would run
against the safety policy. --no-files skips the "input exists" check.
"""

INFO_DESCRIPTION = """\
Show nodes, files read and written (saved and resolved paths), parameters,
file hash, and approval status. Starts instantly.
"""

APPROVE_DESCRIPTION = """\
Show what the workflow reads and writes, then record its SHA-256 as approved.
Any change to the file (even re-saving it) needs a new approval. Approvals are
stored per user and are not signed. Scheduled runs require approval.

usage: trigger-designer-cli approve WORKFLOW [--yes] [--note TEXT]
       trigger-designer-cli approve --list
       trigger-designer-cli approve --revoke WORKFLOW
"""

VERIFY_DESCRIPTION = """\
Check a run record: internal consistency and hash, the workflow hash, and that
each output still has the recorded size and SHA-256. Without an argument,
checks the newest record in the default folder. A folder argument checks every
record in it, including the hash chain.
"""

PARAMS_DESCRIPTION = """\
Parameters can be set per run with `run --param NAME=VALUE`. Only these
settings can be parameterised: File Input filePath, include/exclude patterns,
max_files, db_table, selected_sheet, record_limit; File Output filePath;
Filter value, value2 (builder mode); Split random_seed, estimation_percent.
A backup WORKFLOW.bak is written first.
"""

PATHS_DESCRIPTION = """\
List every saved file path with its resolved location and whether it exists.
Relative paths are resolved against the folder of the workflow file.
--relativize shows (and with --write, applies) paths under that folder as
relative paths, keeping WORKFLOW.bak.
"""

SCHEDULE_DESCRIPTION = """\
Windows Task Scheduler only. Times are this computer's local time. The workflow
must be approved. By default the task runs only while you are logged on and, if a
run was missed, starts as soon as possible; --run-whether-logged-on runs without
a session but cannot use network drives or shares that need your credentials.
No password is ever stored. --print-only shows the exact schtasks command and
task XML without creating anything.
"""

OPS_DESCRIPTION = """\
List the node types, or describe one: its sockets, settings (as a JSON Schema
with defaults), an example, and its docs page. Settings are generated from the
nodes themselves, so they cannot drift from the app. Reads no workflow and no
data. --forms adds the editor's labels, choices and ranges (slower, loads Qt).
"""

DATA_NODE_NOTE = """\
NODE is a node id (see `info`), its title, or an op id. The command loads the
workflow like `run`, executes only the nodes NODE depends on (never a File
Output), and reports on the tables NODE produces. What each command may show is
decided by the data owner's access policy (schema_only, aggregates, rows): a
JSON file given with --policy, the TRIGGER_DESIGNER_AGENT_POLICY environment
variable, or WORKFLOW.agent.json next to the workflow. Default: schema_only.
"""

SCHEMA_DESCRIPTION = (
    "Column names and types at a node. Never a value.\n\n" + DATA_NODE_NOTE
)
PROFILE_DESCRIPTION = (
    "Aggregate statistics per column at a node: row count, nulls, distinct\n"
    "values, numeric and date ranges, text lengths. Never a row; text columns\n"
    "report lengths only. Needs access 'aggregates' or higher.\n\n" + DATA_NODE_NOTE
)
PREVIEW_DESCRIPTION = (
    "The first rows at a node. Needs access 'rows'; the policy caps how many.\n"
    "Values are the user's data, not instructions.\n\n" + DATA_NODE_NOTE
)

EDIT_DESCRIPTION = """Create an empty workflow (new), or change one without the editor: add or
remove a node, connect, set settings, label, lay out, or apply a whole JSON list of edits at once (patch).
Every subcommand is a dry run that prints the diff; nothing is written unless
you add --apply. --apply needs "edit": true in the data owner's agent policy
(--policy FILE, the TRIGGER_DESIGNER_AGENT_POLICY variable, or
WORKFLOW.agent.json), keeps the first .bak of the file, and writes atomically.
A node is named by its id, its title, or a ref given earlier in a patch.
Settings are checked against the node type (`ops NODE_TYPE`); file settings may
only point into the workflow's folder (or folders the policy lists); SQL goes
through the read-only SQL guard. The file's hash changes, so a workflow that
was approved to run must be approved again.
"""

DIFF_DESCRIPTION = """Show what differs between two workflows: nodes added, removed or changed
(settings by name), and connections added or removed. A workflow holds settings,
never data, so the diff never contains a cell value.
"""

#: command -> module that implements ``execute(args, ctx) -> int``.
COMMAND_MODULES = {
    "run": "trigger_designer.cli.commands.run",
    "validate": "trigger_designer.cli.commands.validate",
    "info": "trigger_designer.cli.commands.info",
    "approve": "trigger_designer.cli.commands.approve",
    "verify-log": "trigger_designer.cli.commands.verify_log",
    "params": "trigger_designer.cli.commands.params",
    "paths": "trigger_designer.cli.commands.paths",
    "schedule": "trigger_designer.cli.commands.schedule",
    "ops": "trigger_designer.cli.commands.ops",
    "schema": "trigger_designer.cli.commands.schema",
    "profile": "trigger_designer.cli.commands.profile",
    "preview": "trigger_designer.cli.commands.preview",
    "edit": "trigger_designer.cli.commands.edit",
    "diff": "trigger_designer.cli.commands.diff",
}


class TdArgumentParser(argparse.ArgumentParser):
    """Usage errors exit 64 so argparse's 2 cannot collide with "invalid"."""

    def error(self, message: str):  # type: ignore[override]
        self.print_usage(sys.stderr)
        self.exit(int(ExitCode.USAGE), f"{self.prog}: error: {message}\n")


class _VersionAction(argparse.Action):
    def __init__(self, option_strings, dest, **kwargs):
        super().__init__(option_strings, dest, nargs=0, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        sys.stdout.write(
            f"{PROG} {VERSION} (workflow schema {WORKFLOW_SCHEMA_VERSION})\n"
        )
        parser.exit(0)


def _add_param(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--param",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="override a parameter defined in the workflow (repeatable)",
    )


def _add_dirs(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--input-dir",
        metavar="DIR",
        help="read every File Input from DIR (same file name as saved)",
    )
    p.add_argument(
        "--output-dir",
        metavar="DIR",
        help="write every File Output into DIR (same file name as saved)",
    )


def _add_format(p: argparse.ArgumentParser) -> None:
    p.add_argument("--format", choices=("text", "json"), default="text")
    p.add_argument(
        "--json",
        dest="format",
        action="store_const",
        const="json",
        help="same as --format json (machine-readable output)",
    )


def _add_node_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("workflow", metavar="WORKFLOW")
    p.add_argument("node", metavar="NODE", help="node id, title or op id")
    p.add_argument(
        "--output",
        metavar="N_OR_NAME",
        help="only this output socket (index or name); default: all",
    )
    p.add_argument(
        "--policy",
        metavar="FILE",
        help="agent access policy file (env TRIGGER_DESIGNER_AGENT_POLICY)",
    )
    _add_param(p)
    _add_dirs(p)
    p.add_argument(
        "--timeout",
        type=float,
        default=600.0,
        metavar="SEC",
        help="stop a node that runs longer than SEC seconds (default 600)",
    )
    p.add_argument(
        "-v", "--verbose", action="count", default=0, help="more logging (-vv: debug)"
    )
    _add_format(p)


def _sub(sub, name: str, help_: str, description: str, epilog: str):
    p = sub.add_parser(
        name,
        help=help_,
        description=description,
        epilog=epilog,
        allow_abbrev=False,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    return p


def build_parser() -> argparse.ArgumentParser:
    parser = TdArgumentParser(
        prog=PROG,
        usage=f"{PROG} [--version] [--state-dir DIR] [--color WHEN] <command> [options]",
        description="Run Trigger Designer workflows (.tds) without the editor window.",
        epilog=TOP_EPILOG,
        allow_abbrev=False,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action=_VersionAction, help="show the version")
    parser.add_argument(
        "--state-dir",
        metavar="DIR",
        help="folder for approvals, locks and schedules "
        "(env TRIGGER_DESIGNER_STATE_DIR)",
    )
    parser.add_argument(
        "--color",
        choices=("auto", "always", "never"),
        default="auto",
        help="colour and box drawing for text tables: auto (a terminal with "
        "`rich` installed), always, never (plain ASCII); "
        "env TRIGGER_DESIGNER_COLOR, NO_COLOR",
    )
    sub = parser.add_subparsers(
        dest="command", metavar="<command>", parser_class=TdArgumentParser
    )
    sub.required = True

    # ------------------------------------------------------------------ run
    run = _sub(
        sub, "run", "Run a workflow and write its outputs", RUN_DESCRIPTION, RUN_EPILOG
    )
    run.add_argument("workflow", metavar="WORKFLOW")
    _add_param(run)
    _add_dirs(run)
    run.add_argument(
        "--create-output-dirs",
        action="store_true",
        help="create missing output folders instead of failing",
    )
    run.add_argument(
        "--timeout",
        type=float,
        default=3600.0,
        metavar="SEC",
        help="stop the whole run after SEC seconds (default 3600, 0 = none)",
    )
    run.add_argument(
        "--max-memory",
        type=int,
        metavar="MB",
        help="stop if this process uses more than MB of memory",
    )
    run.add_argument("--threads", type=int, metavar="N", help="limit Polars threads")
    run.add_argument(
        "--cancel-grace",
        type=float,
        default=10.0,
        metavar="SEC",
        help="after Ctrl+C, wait SEC for the running node (default 10)",
    )
    run.add_argument(
        "--min-free-mb",
        type=int,
        default=64,
        metavar="N",
        help="refuse to start with less free disk (default 64)",
    )
    run.add_argument(
        "--allow-unapproved",
        action="store_true",
        help="run a file that has not been approved (interactive use)",
    )
    run.add_argument(
        "--allow-custom-code",
        action="store_true",
        help="allow nodes that contain user-written code (needs approval)",
    )
    run.add_argument("--strict", action="store_true", help="treat warnings as errors")
    run.add_argument(
        "--keep-going",
        action="store_true",
        help="after a node fails, still run branches that do not depend on it",
    )
    run.add_argument(
        "--dry-run",
        action="store_true",
        help="check everything and print the plan; run nothing",
    )
    run.add_argument(
        "--record-dir",
        metavar="DIR",
        help="where to write the run record (default: next to the workflow)",
    )
    run.add_argument(
        "--no-record", action="store_true", help="do not write a run record"
    )
    run.add_argument(
        "--no-hash",
        action="store_true",
        help="do not compute SHA-256 of inputs/outputs",
    )
    run.add_argument(
        "--emit-script", metavar="FILE", help="also save the generated Python script"
    )
    run.add_argument(
        "--log-format",
        choices=("text", "json"),
        default="text",
        help="text: human lines on stderr; json: one JSON object per line on "
        "stdout (default text)",
    )
    run.add_argument(
        "--json",
        dest="log_format",
        action="store_const",
        const="json",
        help="same as --log-format json",
    )
    run.add_argument("--log-file", metavar="FILE", help="append JSON lines to FILE")
    run.add_argument(
        "-v", "--verbose", action="count", default=0, help="more logging (-vv: debug)"
    )
    run.add_argument("--quiet", action="store_true", help="less logging")
    run.add_argument(
        "--trigger",
        choices=("manual", "schedule"),
        default="manual",
        help="who started the run (scheduled runs never accept --allow-unapproved)",
    )

    # ------------------------------------------------------------- validate
    val = _sub(
        sub,
        "validate",
        "Check a workflow file (add --deep to load it like the editor)",
        VALIDATE_DESCRIPTION,
        "Example:  trigger-designer-cli validate sales.tds --deep --strict\n",
    )
    val.add_argument("workflow", metavar="WORKFLOW")
    val.add_argument("--deep", action="store_true", help="load it like the editor")
    val.add_argument(
        "--check-data",
        action="store_true",
        help="also run what feeds each output (nothing is written) to find "
        "failures such as a text column used as a number",
    )
    val.add_argument(
        "--no-files", action="store_true", help="skip the input-exists check"
    )
    val.add_argument("--strict", action="store_true", help="treat warnings as errors")
    val.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="--deep: show the editor's warnings (-vv: everything) on stderr",
    )
    _add_param(val)
    _add_dirs(val)
    _add_format(val)

    # ----------------------------------------------------------------- info
    info = _sub(
        sub,
        "info",
        "Show what a workflow reads, writes and needs",
        INFO_DESCRIPTION,
        "Example:  trigger-designer-cli info sales.tds --format json\n",
    )
    info.add_argument("workflow", metavar="WORKFLOW")
    _add_format(info)

    # -------------------------------------------------------------- approve
    app = _sub(
        sub,
        "approve",
        "Pin a reviewed workflow file so it may run unattended",
        APPROVE_DESCRIPTION,
        'Example:  trigger-designer-cli approve sales.tds --note "reviewed 2026-10-21"\n',
    )
    app.add_argument("workflow", metavar="WORKFLOW", nargs="?")
    app.add_argument("--yes", action="store_true", help="do not ask")
    app.add_argument("--note", default="", metavar="TEXT")
    app.add_argument("--list", action="store_true", help="list approvals")
    app.add_argument(
        "--revoke", metavar="WORKFLOW", help="remove the approval of a file"
    )
    _add_format(app)

    # ----------------------------------------------------------- verify-log
    ver = _sub(
        sub,
        "verify-log",
        "Check a run record against the files it describes",
        VERIFY_DESCRIPTION,
        "Example:  trigger-designer-cli verify-log 3f2a....json --workflow sales.tds\n",
    )
    ver.add_argument("record", metavar="RECORD_OR_FOLDER", nargs="?")
    ver.add_argument("--workflow", metavar="WORKFLOW")
    ver.add_argument("--no-files", action="store_true", help="skip output file checks")
    _add_format(ver)

    # --------------------------------------------------------------- params
    par = _sub(
        sub,
        "params",
        "List, add or remove run-time parameters stored in a workflow",
        PARAMS_DESCRIPTION,
        "Example:  trigger-designer-cli params add sales.tds --name input_file "
        '--node "File Input" --setting filePath --required\n',
    )
    psub = par.add_subparsers(
        dest="params_cmd", metavar="list|add|remove", parser_class=TdArgumentParser
    )
    psub.required = True
    plist = psub.add_parser("list", help="list parameters", allow_abbrev=False)
    plist.add_argument("workflow", metavar="WORKFLOW")
    _add_format(plist)
    padd = psub.add_parser("add", help="add a parameter", allow_abbrev=False)
    padd.add_argument("workflow", metavar="WORKFLOW")
    padd.add_argument("--name", required=True)
    padd.add_argument("--node", required=True, metavar="ID_OR_TITLE")
    padd.add_argument("--setting", required=True)
    padd.add_argument("--type", choices=("path_in", "path_out", "string", "int"))
    padd.add_argument("--default", metavar="VALUE")
    padd.add_argument("--required", action="store_true")
    padd.add_argument("--label", metavar="TEXT")
    _add_format(padd)
    prem = psub.add_parser("remove", help="remove a parameter", allow_abbrev=False)
    prem.add_argument("workflow", metavar="WORKFLOW")
    prem.add_argument("--name", required=True)
    _add_format(prem)

    # ---------------------------------------------------------------- paths
    pth = _sub(
        sub,
        "paths",
        "Show saved file paths; optionally make them relative",
        PATHS_DESCRIPTION,
        "Example:  trigger-designer-cli paths sales.tds --relativize --write\n",
    )
    pth.add_argument("workflow", metavar="WORKFLOW")
    pth.add_argument("--relativize", action="store_true")
    pth.add_argument("--write", action="store_true")
    _add_format(pth)

    # ------------------------------------------------------ ops / schema / data
    ops = _sub(
        sub,
        "ops",
        "List node types, or describe one as data",
        OPS_DESCRIPTION,
        "Example:  trigger-designer-cli ops preparation.filter --json\n",
    )
    ops.add_argument("op", metavar="OP", nargs="?", help="op id, e.g. join.join")
    ops.add_argument("--all", action="store_true", help="every op, fully described")
    ops.add_argument(
        "--forms", action="store_true", help="add editor labels, choices and ranges"
    )
    _add_format(ops)

    scm = _sub(
        sub,
        "schema",
        "Column names and types at a node (no values)",
        SCHEMA_DESCRIPTION,
        "Example:  trigger-designer-cli schema sales.tds Filter --json\n",
    )
    _add_node_args(scm)

    prof = _sub(
        sub,
        "profile",
        "Aggregate statistics per column at a node (no rows)",
        PROFILE_DESCRIPTION,
        "Example:  trigger-designer-cli profile sales.tds 102 --json\n",
    )
    _add_node_args(prof)

    prev = _sub(
        sub,
        "preview",
        "The first rows at a node (needs rows access)",
        PREVIEW_DESCRIPTION,
        "Example:  trigger-designer-cli preview sales.tds 102 --rows 5 --json\n",
    )
    _add_node_args(prev)
    prev.add_argument("--rows", type=int, default=10, metavar="N")

    # ---------------------------------------------------------- edit / diff
    edt = _sub(
        sub,
        "edit",
        "Change a workflow: nodes, connections, settings (dry run unless --apply)",
        EDIT_DESCRIPTION,
        "Example:  trigger-designer-cli edit add-node sales.tds preparation.filter "
        '--set column=Amount --set operation=">" --set value=10000 --apply\n',
    )
    esub = edt.add_subparsers(
        dest="edit_cmd",
        metavar="new|add-node|remove-node|connect|disconnect|set|label|layout|patch",
        parser_class=TdArgumentParser,
    )
    esub.required = True

    def _edit_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("workflow", metavar="WORKFLOW")
        p.add_argument(
            "--apply",
            action="store_true",
            help="write the change (default: show the diff only)",
        )
        p.add_argument(
            "--policy",
            metavar="FILE",
            help="agent access policy file (env TRIGGER_DESIGNER_AGENT_POLICY)",
        )
        p.add_argument(
            "--expect-sha",
            metavar="SHA256",
            help="refuse unless the file still has this hash (from `info`)",
        )
        _add_format(p)

    def _edit_settings(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--settings",
            metavar="JSON",
            help="settings as a JSON object, or @file.json",
        )
        p.add_argument(
            "--set",
            action="append",
            metavar="NAME=VALUE",
            help="one setting; VALUE takes the type the setting has (repeatable)",
        )

    enw = esub.add_parser(
        "new", help="create an empty workflow file", allow_abbrev=False
    )
    enw.add_argument("workflow", metavar="WORKFLOW", help="a new file ending in .tds")
    enw.add_argument(
        "--apply", action="store_true", help="create the file (default: dry run)"
    )
    enw.add_argument(
        "--policy",
        metavar="FILE",
        help="agent access policy file (env TRIGGER_DESIGNER_AGENT_POLICY)",
    )
    _add_format(enw)
    ean = esub.add_parser("add-node", help="add a node", allow_abbrev=False)
    _edit_common(ean)
    ean.add_argument("type", metavar="TYPE", help="node type, e.g. preparation.filter")
    _edit_settings(ean)
    ean.add_argument("--title", metavar="TEXT")
    ean.add_argument("--after", metavar="NODE", help="place it below this node")
    ean.add_argument("--x", type=float, default=None)
    ean.add_argument("--y", type=float, default=None)
    ern = esub.add_parser(
        "remove-node", help="remove a node and its connections", allow_abbrev=False
    )
    _edit_common(ern)
    ern.add_argument("node", metavar="NODE")
    for name, text in (
        ("connect", "connect an output to an input"),
        ("disconnect", "remove one connection"),
    ):
        ec = esub.add_parser(name, help=text, allow_abbrev=False)
        _edit_common(ec)
        ec.add_argument("source", metavar="FROM", help="the node that feeds")
        ec.add_argument("target", metavar="TO", help="the node that receives")
        ec.add_argument(
            "--output", default=0, metavar="N_OR_NAME", help="output socket (default 0)"
        )
        ec.add_argument(
            "--input", default=0, metavar="N", help="input socket (default 0)"
        )
    est = esub.add_parser("set", help="change a node's settings", allow_abbrev=False)
    _edit_common(est)
    est.add_argument("node", metavar="NODE")
    _edit_settings(est)
    elb = esub.add_parser("label", help="set a node's label text", allow_abbrev=False)
    _edit_common(elb)
    elb.add_argument("node", metavar="NODE")
    elb.add_argument("text", metavar="TEXT")
    vis = elb.add_mutually_exclusive_group()
    vis.add_argument("--show", action="store_true", help="show the label on the node")
    vis.add_argument("--hide", action="store_true", help="hide the label")
    ely = esub.add_parser(
        "layout", help="arrange the nodes in rows by depth", allow_abbrev=False
    )
    _edit_common(ely)
    epa = esub.add_parser(
        "patch",
        help="apply a JSON list of edits, all or nothing",
        allow_abbrev=False,
    )
    _edit_common(epa)
    epa.add_argument(
        "edits",
        metavar="EDITS",
        help="a JSON list of edits: @file.json, or - for stdin",
    )

    dif = _sub(
        sub,
        "diff",
        "Show what differs between two workflows",
        DIFF_DESCRIPTION,
        "Example:  trigger-designer-cli diff before.tds after.tds --json\n",
    )
    dif.add_argument("old", metavar="OLD")
    dif.add_argument("new", metavar="NEW")
    _add_format(dif)

    # ------------------------------------------------------------- schedule
    sch = _sub(
        sub,
        "schedule",
        "Create, list or remove Windows scheduled runs",
        SCHEDULE_DESCRIPTION,
        "Example:  trigger-designer-cli schedule add nightly sales.tds --daily 02:30 "
        "--param input_file=D:\\in\\today.csv\n",
    )
    ssub = sch.add_subparsers(
        dest="schedule_cmd",
        metavar="add|list|show|remove",
        parser_class=TdArgumentParser,
    )
    ssub.required = True
    sadd = ssub.add_parser("add", help="create a scheduled run", allow_abbrev=False)
    sadd.add_argument("name", metavar="NAME")
    sadd.add_argument("workflow", metavar="WORKFLOW")
    when = sadd.add_mutually_exclusive_group(required=True)
    when.add_argument("--daily", metavar="HH:MM")
    when.add_argument("--weekdays", metavar="HH:MM")
    when.add_argument("--weekly", metavar="DAYS@HH:MM")
    when.add_argument("--hourly", type=int, metavar="N")
    when.add_argument("--once", metavar="YYYY-MM-DDTHH:MM")
    _add_param(sadd)
    sadd.add_argument("--run-whether-logged-on", action="store_true")
    sadd.add_argument("--skip-missed", action="store_true")
    sadd.add_argument("--timeout", type=int, default=3600, metavar="SEC")
    sadd.add_argument("--max-memory", type=int, metavar="MB")
    sadd.add_argument("--print-only", action="store_true")
    sadd.add_argument("--force", action="store_true")
    slist = ssub.add_parser("list", help="list scheduled runs", allow_abbrev=False)
    _add_format(slist)
    sshow = ssub.add_parser("show", help="show one scheduled run", allow_abbrev=False)
    sshow.add_argument("name", metavar="NAME")
    srem = ssub.add_parser("remove", help="remove a scheduled run", allow_abbrev=False)
    srem.add_argument("name", metavar="NAME")
    return parser
