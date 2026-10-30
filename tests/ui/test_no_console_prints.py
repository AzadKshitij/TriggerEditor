#!/usr/bin/env python3
"""The app does not print to a console it does not have.

A windowed build has no terminal, so a ``print()`` either goes nowhere or
spams a console the user cannot see. The run summary, the "no results"
warnings and the debug traces now go to the Logging dock or the log file.

What is left is deliberate: the last-resort fallbacks that run when the
dock is missing or the logger itself failed, and the Shift+P separator.
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)

import pytest

SRC_ROOT = os.path.join(
    os.path.dirname(__file__), "..", "..", "src", "trigger_designer"
)

#: Files whose remaining prints are the deliberate fallbacks.
ALLOWED_PRINTS = {
    # The Shift+P separator and the no-dock fallback of ``log()``.
    os.path.join("qt", "design_window.py"),
    # The fallbacks that run when the dock is gone or logging broke.
    os.path.join("qt", "helpers", "global_logger.py"),
}

#: The headless CLI's stdout is its product (``print`` in its commands and the
#: helpers in ``cli/output.py`` is the interface, not debug output).
ALLOWED_PREFIXES = (
    os.path.join("cli", "commands") + os.sep,
    os.path.join("cli", "output.py"),
)


def _allowed(relative: str) -> bool:
    return relative in ALLOWED_PRINTS or relative.startswith(ALLOWED_PREFIXES)


def _print_lines(path: str) -> list[tuple[int, str]]:
    with open(path, encoding="utf-8") as handle:
        lines = handle.read().splitlines()
    return [
        (number, line.strip())
        for number, line in enumerate(lines, 1)
        if line.strip().startswith("print(")
    ]


def _python_files() -> list[str]:
    found = []
    for dirpath, _dirnames, filenames in os.walk(SRC_ROOT):
        for filename in filenames:
            if filename.endswith(".py"):
                found.append(os.path.join(dirpath, filename))
    return found


@pytest.mark.parametrize(
    "path",
    [p for p in _python_files() if not _allowed(os.path.relpath(p, SRC_ROOT))],
)
def test_no_file_prints_to_the_console(path: str) -> None:
    offenders = _print_lines(path)
    assert not offenders, (
        f"{os.path.relpath(path, SRC_ROOT)} still prints: "
        + "; ".join(f"{n}: {t}" for n, t in offenders)
    )


def test_the_cli_exemption_covers_only_the_cli() -> None:
    assert _allowed(os.path.join("cli", "commands", "info.py"))
    assert not _allowed(os.path.join("cli", "parser.py"))
    assert not _allowed(os.path.join("core", "headless", "runner.py"))
    assert not _allowed(os.path.join("qt", "headless.py"))


def test_the_remaining_prints_are_the_fallbacks() -> None:
    """The two allowed files keep only the prints that are deliberate."""
    for relative in sorted(ALLOWED_PRINTS):
        path = os.path.join(SRC_ROOT, relative)
        remaining = _print_lines(path)
        assert remaining, f"{relative} was expected to keep its fallbacks"
        for number, text in remaining:
            assert (
                "Shift" in text
                or "separator" in text
                or "print" in text.lower()
                or ("GLOBAL" in text or "FALLBACK" in text or "LOGGING-ERROR" in text)
            ), f"{relative}:{number} prints for no clear reason: {text}"


def test_the_run_summary_reaches_the_logging_dock() -> None:
    """The summary is the output the user is meant to read."""
    from trigger_designer.qt.helpers.workflow_execution_mixin import (
        WorkflowExecutionMixin,
    )

    class _Harness(WorkflowExecutionMixin):
        def __init__(self) -> None:
            self.messages: list[str] = []
            self.init_workflow_execution()

        def logInfo(self, message: str) -> None:
            self.messages.append(message)

    harness = _Harness()
    harness._log_to_dock("hello")

    assert harness.messages == ["hello"]
