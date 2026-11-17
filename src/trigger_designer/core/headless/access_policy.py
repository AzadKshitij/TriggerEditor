"""What an external AI harness may see of a workflow's data (Qt-free).

Three levels, weakest first:

``schema_only`` (default)
    Column names and types. Never a value, never a count derived from values.
``aggregates``
    Also per-column statistics (null and distinct counts, numeric and date
    ranges, text length ranges) and row counts. Never a row.
``rows``
    Also the first ``max_rows`` rows.

The policy is decided by the person who owns the data and is read from a JSON
file, never from the workflow itself, because a harness that can edit the
workflow could otherwise grant itself more::

    {"access": "rows", "max_rows": 20, "edit": false, "paths": []}

Lookup order: ``--policy FILE``, the ``TRIGGER_DESIGNER_AGENT_POLICY``
environment variable, then ``<workflow>.agent.json`` next to the workflow. The
sidecar is a convenience: a harness with file-write access can edit it, so for a
real boundary set the variable (or pass ``--policy``) from outside the
harness's reach. The MCP server (phase 3) takes the same file from its launch
configuration. A missing file means ``schema_only``; an unreadable or invalid
one is an error (fail closed, and say why).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from trigger_designer.core.headless.exit_codes import CliError, ExitCode

LEVELS = ("schema_only", "aggregates", "rows")
ENV_VAR = "TRIGGER_DESIGNER_AGENT_POLICY"
SIDECAR_SUFFIX = ".agent.json"
#: Never return more rows than this, whatever the policy file says.
HARD_MAX_ROWS = 1000


@dataclass(frozen=True)
class AccessPolicy:
    level: str = "schema_only"
    #: Row cap when ``level == "rows"``.
    max_rows: int = 0
    #: May the harness change the workflow (the ``edit`` commands, ``--apply``).
    edit: bool = False
    #: Extra folders an edit may point a file setting at, besides the
    #: workflow's own folder.
    paths: tuple[str, ...] = ()
    #: Where it came from: ``default`` or a file path.
    source: str = "default"

    def rank(self) -> int:
        return LEVELS.index(self.level)

    def allows(self, level: str) -> bool:
        return LEVELS.index(level) <= self.rank()

    def to_dict(self) -> dict:
        return {
            "access": self.level,
            "max_rows": self.max_rows,
            "edit": self.edit,
            "paths": list(self.paths),
            "source": self.source,
        }


def sidecar_path(workflow: str) -> Path:
    return Path(workflow).with_name(Path(workflow).name + SIDECAR_SUFFIX)


def _invalid(path: Path, why: str) -> CliError:
    return CliError(
        ExitCode.INVALID,
        "TD-CLI-006",
        f"The agent access policy {path} is not valid: {why}",
        'Expected JSON such as {"access": "schema_only"}; "access" is one of '
        + ", ".join(LEVELS)
        + ".",
    )


def parse_policy(text: str, source: str) -> AccessPolicy:
    path = Path(source)
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise _invalid(path, f"not JSON ({exc})") from None
    if not isinstance(data, dict):
        raise _invalid(path, "the top level must be an object")
    level = data.get("access", "schema_only")
    if level not in LEVELS:
        raise _invalid(path, f"unknown access level {level!r}")
    max_rows = data.get("max_rows", 0)
    if isinstance(max_rows, bool) or not isinstance(max_rows, int) or max_rows < 0:
        raise _invalid(path, '"max_rows" must be a whole number, 0 or more')
    if level == "rows" and max_rows == 0:
        raise _invalid(path, '"rows" access needs a "max_rows" of at least 1')
    edit = data.get("edit", False)
    if not isinstance(edit, bool):
        raise _invalid(path, '"edit" must be true or false')
    paths = data.get("paths", [])
    if not isinstance(paths, list) or not all(
        isinstance(p, str) and p.strip() for p in paths
    ):
        raise _invalid(path, '"paths" must be a list of folder paths')
    return AccessPolicy(
        level=level,
        max_rows=min(max_rows, HARD_MAX_ROWS) if level == "rows" else 0,
        edit=edit,
        paths=tuple(p.strip() for p in paths),
        source=source,
    )


def load_policy(workflow: str, explicit: str | None = None) -> AccessPolicy:
    """The policy that applies to ``workflow`` (see the module docstring)."""
    chosen = explicit or os.environ.get(ENV_VAR)
    if chosen:
        path = Path(chosen)
        required = True
    else:
        path = sidecar_path(workflow)
        required = False
    try:
        text = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        if required:
            raise _invalid(path, "the file does not exist") from None
        return AccessPolicy()
    except OSError as exc:
        raise _invalid(path, exc.strerror or str(exc)) from None
    return parse_policy(text, str(path))


def require(policy: AccessPolicy, level: str, what: str) -> None:
    """Raise a refusal unless ``policy`` allows ``level``."""
    if policy.allows(level):
        return
    where = (
        policy.source
        if policy.source != "default"
        else f"--policy, {ENV_VAR} or <workflow>{SIDECAR_SUFFIX}"
    )
    raise CliError(
        ExitCode.REFUSED,
        "TD-CLI-019",
        f"The access policy ({policy.level}) does not allow {what}.",
        f'It needs "access": "{level}" or higher. The data owner sets this in '
        f"the policy file ({where}).",
    )


def require_edit(policy: AccessPolicy) -> None:
    """Raise a refusal unless ``policy`` lets a tool change the workflow."""
    if policy.edit:
        return
    where = (
        policy.source
        if policy.source != "default"
        else f"--policy, {ENV_VAR} or <workflow>{SIDECAR_SUFFIX}"
    )
    raise CliError(
        ExitCode.REFUSED,
        "TD-CLI-019",
        "The access policy does not allow changing the workflow.",
        "Without applying (--apply on the command line, apply=true in MCP) an "
        "edit only shows its diff. To write, the data owner "
        f'sets "edit": true in the policy file ({where}).',
    )
