"""Print the commits of a branch grouped by feature, as a changelog starting point.

    python scripts/gen_changelog_stub.py                 # main..feature, Markdown
    python scripts/gen_changelog_stub.py --base main --head feature --format text
    python scripts/gen_changelog_stub.py --show-other    # only what no group claimed

``docs/CHANGELOG.md`` is written by hand from this list: each bullet there names
the user-visible effect. Regenerate the stub, diff it against the changelog and
add what is new. Groups are matched in order on the commit subject; the first
match wins (edit ``GROUPS`` when a new kind of work appears).
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass

#: (heading, regex on the subject). First match wins.
GROUPS: tuple[tuple[str, str], ...] = (
    ("Documentation", r"^docs"),
    ("Audit trail and Run History", r"\(audit-trail\)"),
    ("Audit nodes", r"^\w+\(audit\)"),
    ("Run: hardening, re-evaluation and cancel", r"^\w+\(run\)"),
    ("Security: SQL guard and code-injection hardening", r"\((security|sql-guard)\)"),
    ("Workpaper and Excel export", r"\((workpaper|excel)\)"),
    ("Command line (CLI)", r"\(cli\)"),
    (
        "Editing and live evaluation",
        (
            r"when it is left|Defer File Input|yellow mark|red Formula|"
            r"Check Formula|late error enrichment|Fix Formula type|\(shaping\)"
        ),
    ),
    ("Saving and loading", r"\(save\)"),
    ("Shaping and report nodes", r"\(nodes\)|^shaping|Record ID|Data Profile"),
    ("Error system", r"^errors|\(errors\)|translator"),
    ("Input types", r"input_source|CSV header|Excel file metadata"),
    (
        "Canvas, docks and appearance",
        (
            r"canvas|Canvas|icon|Icon|theme|Theme|checkbox|font size|Arrange|glyph|"
            r"node visibility|drag and drop|Select table|palette|\(graph\)|\(eval\)"
        ),
    ),
    (
        "Repository hygiene and tests",
        (
            r"Untrack|Stop tracking|^test|Remove unused|Remove dead|"
            r"Refactor check_output|over-engineer"
        ),
    ),
    ("Merges", r"^Merge"),
)
OTHER = "Other"


@dataclass(frozen=True)
class Commit:
    sha: str
    date: str
    subject: str


def read_commits(base: str, head: str, *, no_merges: bool) -> list[Commit]:
    """Commits reachable from ``head`` and not from ``base``, oldest first."""
    command = [
        "git",
        "log",
        "--reverse",
        "--format=%h%x09%ad%x09%s",
        "--date=short",
        f"{base}..{head}",
    ]
    if no_merges:
        command.insert(2, "--no-merges")
    done = subprocess.run(command, capture_output=True, text=True, check=False)
    if done.returncode != 0:
        sys.exit(done.stderr.strip() or "git log failed")
    commits = []
    for line in done.stdout.splitlines():
        parts = line.split("\t", 2)
        if len(parts) == 3:
            commits.append(Commit(*parts))
    return commits


def group_of(subject: str) -> str:
    for heading, pattern in GROUPS:
        if re.search(pattern, subject):
            return heading
    return OTHER


def group_commits(commits: list[Commit]) -> dict[str, list[Commit]]:
    grouped: dict[str, list[Commit]] = {heading: [] for heading, _ in GROUPS}
    grouped[OTHER] = []
    for commit in commits:
        grouped[group_of(commit.subject)].append(commit)
    return {heading: items for heading, items in grouped.items() if items}


def render(grouped: dict[str, list[Commit]], fmt: str) -> str:
    lines: list[str] = []
    for heading, items in grouped.items():
        lines.append(f"## {heading}" if fmt == "md" else heading.upper())
        for commit in items:
            if fmt == "md":
                lines.append(f"- {commit.subject} (`{commit.sha}`, {commit.date})")
            else:
                lines.append(f"  {commit.sha} {commit.date} {commit.subject}")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="main")
    parser.add_argument("--head", default="feature")
    parser.add_argument("--format", choices=("md", "text"), default="md")
    parser.add_argument("--no-merges", action="store_true", help="skip merge commits")
    parser.add_argument(
        "--show-other", action="store_true", help="print only unclaimed commits"
    )
    args = parser.parse_args(argv)
    commits = read_commits(args.base, args.head, no_merges=args.no_merges)
    grouped = group_commits(commits)
    if args.show_other:
        grouped = {OTHER: grouped.get(OTHER, [])}
    # Bytes, so a Windows console code page cannot reject a character.
    text = render(grouped, args.format) + "\n"
    sys.stdout.buffer.write(text.encode("utf-8"))
    print(f"{len(commits)} commit(s) in {args.base}..{args.head}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
