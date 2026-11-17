"""``modules``: list, check and remove the optional data packs, offline.

Adding a module is done in the app only: its consent screen names the source and
the hashes, and nothing is downloaded until the user accepts. This command never
downloads anything and never imports the downloader.
"""

from __future__ import annotations

from trigger_designer.cli.output import print_json
from trigger_designer.cli.render import Out, Table
from trigger_designer.core.headless.exit_codes import CliError, ExitCode
from trigger_designer.core.modules import ModuleError, ModuleStore, load_catalogue
from trigger_designer.core.modules.consent import size_text
from trigger_designer.core.modules.errors import CANCELLED, NOT_INSTALLED

#: The TD-CLI code for a refused command line; `ops` and `schedule` use it too.
USAGE_CODE = "TD-CLI-006"


def _cli_error(exc: ModuleError) -> CliError:
    code = ExitCode.CANCELLED if exc.code == CANCELLED else ExitCode.INVALID
    return CliError(code, exc.code, exc.message, exc.hint)


def _list(args) -> int:
    store = ModuleStore()
    catalogue = load_catalogue()
    installed = store.installed()
    installed_ids = {item.id for item in installed}
    available = [item for item in catalogue.modules if item.id not in installed_ids]
    if args.format == "json":
        print_json(
            {
                "modules_dir": str(store.root),
                "installed": [
                    {
                        "id": item.id,
                        "name": item.manifest.name,
                        "version": item.version,
                        "size_bytes": item.size_bytes,
                        "installed_at": item.installed_at,
                        "path": str(item.path),
                    }
                    for item in installed
                ],
                "available": [
                    {
                        "id": item.id,
                        "name": item.name,
                        "version": item.version,
                        "size_bytes": item.total_size,
                        "license": item.license,
                        "hosts": list(item.hosts),
                        "description": item.description,
                    }
                    for item in available
                ],
                "catalogue": {
                    "source": catalogue.source,
                    "problems": list(catalogue.problems),
                },
            }
        )
        return int(ExitCode.OK)

    out = Out()
    if installed:
        out.table(
            Table(
                ["id", "version", "size", "installed"],
                [
                    [
                        item.id,
                        item.version,
                        size_text(item.size_bytes),
                        item.installed_at,
                    ]
                    for item in installed
                ],
                title="Installed modules",
            )
        )
    else:
        out.line("No modules are installed.")
    if available:
        out.table(
            Table(
                ["id", "version", "size", "license"],
                [
                    [item.id, item.version, size_text(item.total_size), item.license]
                    for item in available
                ],
                title="Available (install them in the app: Help > Optional modules)",
            )
        )
    for problem in catalogue.problems:
        out.note(f"catalogue: {problem}")
    out.note(f"Modules folder: {store.root}")
    return int(ExitCode.OK)


def _verify(args) -> int:
    try:
        result = ModuleStore().verify(args.id)
    except ModuleError as exc:
        raise _cli_error(exc) from exc
    if args.format == "json":
        print_json({"id": args.id, "ok": result.ok, "problems": list(result.problems)})
    else:
        out = Out()
        if result.ok:
            out.line(f"{args.id}: every file matches its size and SHA-256 hash.")
        else:
            out.line(f"{args.id}: {len(result.problems)} problem(s):")
            for problem in result.problems:
                out.line(f"  - {problem}")
    return int(ExitCode.OK if result.ok else ExitCode.VERIFY_FAILED)


def _remove(args) -> int:
    if not args.yes:
        raise CliError(
            ExitCode.USAGE,
            USAGE_CODE,
            "Removing a module needs --yes.",
            "Run the same command again with --yes to delete the module's files.",
        )
    store = ModuleStore()
    try:
        installed = store.get(args.id)
        removed = installed is not None and store.remove(args.id)
    except ModuleError as exc:
        raise _cli_error(exc) from exc
    if not removed:
        raise CliError(
            ExitCode.INVALID,
            NOT_INSTALLED,
            f"The module '{args.id}' is not installed.",
            "Run `modules list` to see the installed modules.",
        )
    if args.format == "json":
        print_json({"id": args.id, "removed": True, "path": str(installed.path)})
    else:
        Out().line(f"Removed {args.id} ({installed.path}).")
    return int(ExitCode.OK)


def execute(args, ctx) -> int:
    if args.modules_cmd == "verify":
        return _verify(args)
    if args.modules_cmd == "remove":
        return _remove(args)
    return _list(args)
