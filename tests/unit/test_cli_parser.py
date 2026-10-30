"""Command-line grammar, usage errors and help text (plan 08 3.3, Appendix B)."""

from __future__ import annotations

import pytest

from tests.support.cli import call_main
from trigger_designer.cli.parser import COMMAND_MODULES, build_parser


def test_version_flag():
    result = call_main(["--version"])
    assert result.code == 0
    assert result.stdout.strip() == "trigger-designer-cli 0.1.0 (workflow schema 2)"


def test_usage_error_exits_64():
    result = call_main(["run"])
    assert result.code == 64
    assert "usage" in result.stderr.lower()


def test_unknown_command_and_flag_exit_64():
    assert call_main(["frobnicate"]).code == 64
    assert call_main(["info", "x.tds", "--nope"]).code == 64


def test_abbreviations_rejected():
    assert call_main(["run", "wf.tds", "--dry"]).code == 64


def test_no_command_is_usage_error():
    assert call_main([]).code == 64


def test_defaults():
    args = build_parser().parse_args(["run", "wf.tds"])
    assert args.timeout == 3600
    assert args.cancel_grace == 10
    assert args.min_free_mb == 64
    assert args.log_format == "text"
    assert args.trigger == "manual"
    assert args.param == []
    assert args.allow_unapproved is False


def test_param_is_repeatable():
    args = build_parser().parse_args(
        ["run", "wf.tds", "--param", "a=1", "--param", "b=c=d"]
    )
    assert args.param == ["a=1", "b=c=d"]


@pytest.mark.parametrize("command", sorted(COMMAND_MODULES))
def test_every_command_has_examples(command):
    result = call_main([command, "--help"])
    assert result.code == 0
    assert "Example" in result.stdout


def test_top_help_lists_commands_and_exit_codes():
    result = call_main(["--help"])
    assert result.code == 0
    for command in COMMAND_MODULES:
        assert command in result.stdout
    assert "130 cancelled" in result.stdout


def test_schedule_requires_one_trigger():
    assert call_main(["schedule", "add", "n", "wf.tds"]).code == 64
    assert (
        call_main(
            ["schedule", "add", "n", "wf.tds", "--daily", "01:00", "--hourly", "2"]
        ).code
        == 64
    )
