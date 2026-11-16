"""What an external harness may see: the data owner's access policy (AI plan)."""

from __future__ import annotations

import json

import pytest

from trigger_designer.core.headless import access_policy as ap
from trigger_designer.core.headless.exit_codes import CliError, ExitCode


def _write(path, **data):
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_no_file_means_schema_only(tmp_path, monkeypatch):
    monkeypatch.delenv(ap.ENV_VAR, raising=False)
    policy = ap.load_policy(str(tmp_path / "wf.tds"))
    assert policy.level == "schema_only" and policy.source == "default"
    assert policy.allows("schema_only")
    assert not policy.allows("aggregates") and not policy.allows("rows")


def test_levels_are_ordered():
    rows = ap.AccessPolicy("rows", 5)
    assert rows.allows("schema_only") and rows.allows("aggregates")
    assert rows.allows("rows")
    assert ap.AccessPolicy("aggregates").allows("aggregates")
    assert not ap.AccessPolicy("aggregates").allows("rows")


def test_sidecar_sits_next_to_the_workflow(tmp_path, monkeypatch):
    monkeypatch.delenv(ap.ENV_VAR, raising=False)
    wf = tmp_path / "sales.tds"
    side = _write(tmp_path / "sales.tds.agent.json", access="aggregates")
    assert ap.sidecar_path(str(wf)) == side
    assert ap.load_policy(str(wf)).level == "aggregates"


def test_explicit_file_beats_environment_beats_sidecar(tmp_path, monkeypatch):
    wf = tmp_path / "sales.tds"
    _write(tmp_path / "sales.tds.agent.json", access="rows", max_rows=9)
    env = _write(tmp_path / "env.json", access="aggregates")
    flag = _write(tmp_path / "flag.json", access="schema_only")
    monkeypatch.setenv(ap.ENV_VAR, str(env))
    assert ap.load_policy(str(wf)).level == "aggregates"
    assert ap.load_policy(str(wf), str(flag)).level == "schema_only"
    monkeypatch.delenv(ap.ENV_VAR)
    assert ap.load_policy(str(wf)).level == "rows"


def test_rows_policy_is_capped(tmp_path):
    policy = ap.parse_policy('{"access": "rows", "max_rows": 999999}', "p.json")
    assert policy.max_rows == ap.HARD_MAX_ROWS
    assert not ap.parse_policy('{"access": "aggregates", "max_rows": 7}', "p").max_rows


@pytest.mark.parametrize(
    "text",
    [
        "{not json",
        "[]",
        '{"access": "everything"}',
        '{"access": "rows"}',  # needs max_rows
        '{"access": "rows", "max_rows": -1}',
        '{"access": "rows", "max_rows": true}',
        '{"access": "schema_only", "edit": "yes"}',
    ],
)
def test_invalid_policies_fail_closed(text):
    with pytest.raises(CliError) as exc:
        ap.parse_policy(text, "p.json")
    assert exc.value.code == ExitCode.INVALID and "policy" in exc.value.message


def test_a_named_policy_file_must_exist(tmp_path, monkeypatch):
    monkeypatch.delenv(ap.ENV_VAR, raising=False)
    with pytest.raises(CliError, match="does not exist"):
        ap.load_policy(str(tmp_path / "wf.tds"), str(tmp_path / "missing.json"))


def test_require_refuses_with_the_policy_code():
    with pytest.raises(CliError) as exc:
        ap.require(ap.AccessPolicy(), "rows", "reading rows")
    assert exc.value.code == ExitCode.REFUSED and exc.value.td_code == "TD-CLI-019"
    assert "rows" in exc.value.hint
    ap.require(ap.AccessPolicy("rows", 3), "rows", "reading rows")  # no raise
