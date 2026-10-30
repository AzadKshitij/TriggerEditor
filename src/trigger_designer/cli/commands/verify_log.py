"""``verify-log``: check a run record against the files it describes."""

from __future__ import annotations

from trigger_designer.cli.output import print_json
from trigger_designer.core.headless.exit_codes import ExitCode
from trigger_designer.core.headless.state import data_dir
from trigger_designer.core.headless.verify import (
    require_target,
    verify_folder,
    verify_record,
)


def execute(args, ctx) -> int:
    target = require_target(args.record, data_dir(), args.workflow)
    check_files = not args.no_files
    if target.is_dir():
        findings = verify_folder(target, check_files=check_files)
    else:
        findings = verify_record(
            target, workflow=args.workflow, check_files=check_files
        )
    errors = [f for f in findings if f.level == "error"]
    if args.format == "json":
        print_json(
            {
                "target": str(target),
                "ok": not errors,
                "findings": [f.to_dict() for f in findings],
            }
        )
    else:
        print(f"checked: {target}")
        for f in findings:
            print(f"{f.level.upper():7} {f.td_code}: {f.message}")
        print("VERIFIED" if not errors else "VERIFICATION FAILED")
    return int(ExitCode.VERIFY_FAILED if errors else ExitCode.OK)
