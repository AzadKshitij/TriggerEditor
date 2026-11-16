"""The CLI exit-code contract and its error type (plan 08 3.4, Appendix C).

Qt-free and import-light: every CLI command, including ``--help``, needs this.
"""

from __future__ import annotations

from enum import IntEnum


class ExitCode(IntEnum):
    OK = 0
    NODE_FAILED = 1
    INVALID = 2
    INTERNAL = 3
    TIMEOUT = 4
    MEMORY = 5
    REFUSED = 6
    BUSY = 7
    COMMIT_FAILED = 8
    SCHEDULER = 9
    VERIFY_FAILED = 10
    USAGE = 64
    CANCELLED = 130


#: Several outcomes at once: the first one that applies wins (3.4).
PRECEDENCE = (
    ExitCode.CANCELLED,
    ExitCode.TIMEOUT,
    ExitCode.MEMORY,
    ExitCode.COMMIT_FAILED,
    ExitCode.NODE_FAILED,
    ExitCode.OK,
)

#: ``TD-CLI-*`` code -> (default message, default hint). The catalogue in
#: ``core/errors/catalogue.py`` owns the plain-language text shown in the app;
#: this table is the CLI's own copy so ``--help`` never imports it.
CLI_CODES: dict[str, str] = {
    "TD-CLI-001": "The workflow file could not be read.",
    "TD-CLI-002": "This workflow was saved by a newer version of Trigger Designer.",
    "TD-CLI-003": "The workflow contains a node type this program does not know.",
    "TD-CLI-004": "The workflow has a loop: a node depends on its own output.",
    "TD-CLI-005": "A parameter name was not recognised, or a required parameter is missing.",
    "TD-CLI-006": "A parameter or path value is not valid.",
    "TD-CLI-007": "That setting cannot be changed from the command line.",
    "TD-CLI-008": "This workflow has not been approved to run.",
    "TD-CLI-009": "The workflow changed after it was approved.",
    "TD-CLI-010": "The workflow was refused by the safety check.",
    "TD-CLI-011": "The workflow contains a node with user-written code.",
    "TD-CLI-012": "This workflow is already running.",
    "TD-CLI-013": "The results could not be saved to their final location.",
    "TD-CLI-014": "An output folder is missing or cannot be written, or two outputs would overwrite each other.",
    "TD-CLI-015": "There is not enough free disk space for the outputs.",
    "TD-CLI-016": "The Windows scheduler could not complete the request.",
    "TD-CLI-017": "The run record does not match the files it describes.",
    "TD-CLI-018": "This workflow writes no files, so a run produces nothing.",
    "TD-CLI-019": "The data owner's access policy does not allow this.",
    "TD-CLI-020": "The node named on the command line was not found, or is ambiguous.",
    "TD-CLI-021": "This node has no table to look at.",
    "TD-CLI-022": "A setting name or value is not valid for this node type.",
    "TD-CLI-023": "That connection is not allowed.",
    "TD-CLI-024": "A file setting points outside the folders an edit may use.",
    "TD-CLI-025": "The SQL was refused by the safety check.",
    "TD-CLI-026": "The workflow changed since it was read.",
    "TD-CLI-027": "The edit is malformed or cannot be applied to this workflow.",
    "TD-CLI-028": "That workflow is outside the folders this server may use.",
}


class CliError(Exception):
    """A failure with a stable exit code and ``TD-*`` code."""

    def __init__(
        self,
        code: ExitCode,
        td_code: str,
        message: str = "",
        hint: str = "",
    ) -> None:
        self.code = ExitCode(code)
        self.td_code = td_code
        self.message = message or CLI_CODES.get(td_code, "")
        self.hint = hint
        super().__init__(f"[{td_code}] {self.message}")

    def to_dict(self) -> dict:
        return {
            "code": self.td_code,
            "message": self.message,
            "hint": self.hint,
            "exit_code": int(self.code),
        }


def combine(*codes: ExitCode) -> ExitCode:
    """The winning exit code of several simultaneous outcomes (3.4)."""
    present = set(codes)
    for code in PRECEDENCE:
        if code in present:
            return code
    return ExitCode.OK
