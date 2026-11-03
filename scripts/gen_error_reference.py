"""Regenerate the error-code reference table in the user guide.

The table in ``docs/guide/errors-and-problems.md`` is generated from the two
places that own error codes, so it cannot drift from the code:

* ``trigger_designer.core.errors.catalogue.CATALOGUE`` - every user-facing
  message template (title, detail, fixes, severity);
* ``trigger_designer.core.shaping.common.ERROR_CODES`` - the short description
  the shaping nodes attach to their stable ``TD-SHAPE-*`` codes.

Usage (from the repository root, in the project environment)::

    .venv\\Scripts\\python.exe scripts/gen_error_reference.py            # rewrite the page
    .venv\\Scripts\\python.exe scripts/gen_error_reference.py --check    # exit 1 if stale
    .venv\\Scripts\\python.exe scripts/gen_error_reference.py --stdout   # print, do not write

Only the text between the ``BEGIN``/``END`` markers on the page is replaced.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trigger_designer.core.errors.catalogue import CATALOGUE
from trigger_designer.core.shaping.common import ERROR_CODES

PAGE = ROOT / "docs" / "guide" / "errors-and-problems.md"
BEGIN = "<!-- BEGIN GENERATED ERROR TABLE (scripts/gen_error_reference.py) -->"
END = "<!-- END GENERATED ERROR TABLE -->"

#: Family prefix -> (heading, one-line description). Order is the page order.
FAMILIES: dict[str, tuple[str, str]] = {
    "TD-IN": ("Reading input files (TD-IN)", "File Input, folders, databases."),
    "TD-SCH": (
        "Columns and schemas (TD-SCH)",
        "A column is missing, renamed or differs between files.",
    ),
    "TD-TYP": (
        "Data types and conversion (TD-TYP)",
        "A value could not be read as a number, date or other type.",
    ),
    "TD-JOI": ("Joins (TD-JOI)", "Join and union problems."),
    "TD-SHAPE": (
        "Node settings and data shaping (TD-SHAPE)",
        "Select, Formula, Filter, SQL Query, Pivot, Reconcile, Fuzzy Match and the other shaping nodes.",
    ),
    "TD-OUT": (
        "Writing output files (TD-OUT)",
        "File Output and workpaper export.",
    ),
    "TD-RUN": ("Running a workflow (TD-RUN)", "Problems found while a run executes."),
    "TD-EXP": (
        "Expressions and formulas (TD-EXP)",
        "Problems in formula or expression text.",
    ),
    "TD-SYS": ("System and resources (TD-SYS)", "Memory, time and environment."),
    "TD-AUDIT": (
        "Audit nodes (TD-AUDIT)",
        "Benford, Duplicates, Gaps, Sample and the risk filters.",
    ),
    "TD-CLI": (
        "Command line (TD-CLI)",
        "Raised by the command-line runner; see [cli.md](cli.md).",
    ),
}

# ``{n:,}`` and ``{path_name}`` style fields in the message templates.
_PLACEHOLDER = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)(?::[^}]*)?\}")


def human(text: str) -> str:
    """Make a template readable: ``{path_name}`` stays a visible placeholder.

    Format specs such as ``{n:,}`` are dropped, and ``<`` / ``>`` are escaped
    so literal angle brackets in a message cannot be read as HTML.
    """
    text = _PLACEHOLDER.sub(lambda m: "{" + m.group(1) + "}", str(text))
    text = text.replace("<", "&lt;").replace(">", "&gt;")
    return " ".join(text.split())


def cell(text: str) -> str:
    return human(text).replace("|", "\\|")


def fixes_for(entry: dict) -> str:
    fixes: list[str] = []
    for template, _condition in entry.get("fixes", ()):
        rendered = cell(template)
        if rendered and rendered not in fixes:
            fixes.append(rendered)
    if not fixes and entry.get("hint"):
        fixes.append(cell(entry["hint"]))
    return "<br>".join(
        f"{i}. {f}" if len(fixes) > 1 else f for i, f in enumerate(fixes, 1)
    )


def family_of(code: str) -> str:
    return code.rsplit("-", 1)[0]


def build_table() -> str:
    by_family: dict[str, list[str]] = defaultdict(list)
    for code in sorted(CATALOGUE):
        by_family[family_of(code)].append(code)

    unknown = sorted(set(by_family) - set(FAMILIES))
    if unknown:
        raise SystemExit(
            f"Unknown error families {unknown}: add them to FAMILIES in {Path(__file__).name}"
        )

    lines: list[str] = []
    total = 0
    for prefix, (heading, blurb) in FAMILIES.items():
        codes = by_family.get(prefix)
        if not codes:
            continue
        lines += [f"#### {heading}", "", blurb, ""]
        lines += ["| Code | What it says | How to fix it |", "|---|---|---|"]
        for code in codes:
            entry = CATALOGUE[code]
            title = cell(entry.get("title", ""))
            notes = []
            if entry.get("severity") == "warning":
                notes.append("warning")
            if entry.get("reserved"):
                notes.append("flagged reserved in the catalogue")
            short = ERROR_CODES.get(code)
            if (
                short
                and short.strip().lower() != entry.get("title", "").strip().lower()
            ):
                title += f" _(node note: {cell(short)})_"
            if notes:
                title += f" _({', '.join(notes)})_"
            lines.append(f"| `{code}` | {title} | {fixes_for(entry)} |")
            total += 1
        lines.append("")
    summary = (
        f"_{total} codes. Generated from `core/errors/catalogue.py` and "
        "`core/shaping/common.py`; do not edit by hand._"
    )
    return "\n".join([summary, "", *lines]).rstrip() + "\n"


def splice(page_text: str, table: str) -> str:
    start = page_text.find(BEGIN)
    end = page_text.find(END)
    if start < 0 or end < 0 or end < start:
        raise SystemExit(f"Markers not found in {PAGE}: {BEGIN} ... {END}")
    return page_text[: start + len(BEGIN)] + "\n\n" + table + "\n" + page_text[end:]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check", action="store_true", help="fail if the page is stale"
    )
    parser.add_argument("--stdout", action="store_true", help="print the table only")
    args = parser.parse_args()

    table = build_table()
    if args.stdout:
        sys.stdout.write(table)
        return 0
    current = PAGE.read_text(encoding="utf-8")
    updated = splice(current, table)
    if args.check:
        if updated != current:
            print(f"{PAGE} is out of date: run scripts/gen_error_reference.py")
            return 1
        print("Error reference is up to date.")
        return 0
    if updated != current:
        PAGE.write_text(updated, encoding="utf-8", newline="\n")
        print(f"Updated {PAGE}")
    else:
        print("Error reference already up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
