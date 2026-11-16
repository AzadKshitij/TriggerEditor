"""The read-only MCP server (AI plan, phase 3).

Three layers: the SDK-free tool functions, the registered server driven by the
SDK's in-process client (the same protocol layer a harness uses, without a
subprocess), and a real stdio subprocess (clean standard output, no sockets).
Data tools run the workflow in a CLI child process, so these are e2e tests.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("mcp")

from mcp import Client

from tests.support.cli import SRC
from tests.support.corpus import FILE_OUTPUT_CASES
from tests.support.workflows import materialize
from trigger_designer.agent.server import build_server
from trigger_designer.agent.tools import AgentTools
from trigger_designer.core.headless.exit_codes import CliError

pytestmark = pytest.mark.e2e

CASE = next(c for c in FILE_OUTPUT_CASES if c.name == "filter")
#: A value that is in the input data and nowhere in the catalogue or policy.
CELL_VALUE = "sudoku"

TOOLS = {
    "get_policy",
    "list_ops",
    "describe_op",
    "read_workflow",
    "validate",
    "diff",
    "get_schema",
    "get_profile",
    "get_preview",
    "explain_error",
}


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path, monkeypatch):
    """The in-process tools and their CLI children share one throwaway state."""
    monkeypatch.setenv("TRIGGER_DESIGNER_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("TRIGGER_DESIGNER_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("TRIGGER_DESIGNER_AGENT_POLICY", raising=False)


@pytest.fixture
def wf(tmp_path):
    return materialize(CASE, tmp_path).path


def _policy_file(tmp_path: Path, **policy) -> str:
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(policy), encoding="utf-8")
    return str(path)


def _node_id(wf: Path, title: str) -> int:
    nodes = json.loads(wf.read_text(encoding="utf-8"))["nodes"]
    return next(n["id"] for n in nodes if n.get("title") == title)


def _tools(wf: Path, tmp_path: Path, **policy) -> AgentTools:
    return AgentTools(
        policy_file=_policy_file(tmp_path, **policy) if policy else None,
        workspaces=[str(wf.parent)],
    )


async def _call(tools: AgentTools, name: str, args: dict | None = None):
    async with Client(build_server(tools)) as client:
        return await client.call_tool(name, args or {})


def call(tools: AgentTools, name: str, args: dict | None = None):
    return asyncio.run(_call(tools, name, args))


def error_of(result) -> dict:
    assert result.is_error
    text = result.content[0].text  # "Error executing tool X: {json}"
    return json.loads(text[text.index("{") :])["error"]


# ------------------------------------------------------------ tool functions
def test_workflow_must_be_a_tds_file_inside_a_workspace(wf, tmp_path):
    tools = _tools(wf, tmp_path)
    assert tools.workflow_path(wf.name) == str(wf.resolve())
    outside = tmp_path.parent / "elsewhere.tds"
    for bad in (outside, wf.parent / "notes.txt", wf.parent / ".." / "x.tds"):
        with pytest.raises(CliError) as err:
            tools.workflow_path(str(bad))
        assert err.value.td_code == "TD-CLI-028"


def test_explain_error_knows_catalogue_codes_and_suggests_for_typos(wf, tmp_path):
    tools = _tools(wf, tmp_path)
    known = tools.explain_error("td-cli-019")
    assert known["found"] and known["code"] == "TD-CLI-019"
    assert "access policy" in known["title"]
    unknown = tools.explain_error("TD-CLI-9019")
    assert unknown["found"] is False and "TD-CLI-019" in unknown["similar"]


# -------------------------------------------------- in-process protocol layer
def test_every_tool_is_registered_and_marked_read_only(wf, tmp_path):
    async def go():
        async with Client(build_server(_tools(wf, tmp_path))) as client:
            return (await client.list_tools()).tools

    tools = asyncio.run(go())
    assert {t.name for t in tools} == TOOLS
    for tool in tools:
        assert tool.annotations.read_only_hint is True, tool.name
        assert tool.annotations.destructive_hint is False, tool.name
    assert not {t.name for t in tools} & {"run", "edit", "apply", "approve"}


def test_discovery_tools_return_structured_data(wf, tmp_path):
    tools = _tools(wf, tmp_path)
    ops = call(tools, "list_ops").structured_content
    assert "preparation.filter" in {row["op"] for row in ops["ops"]}
    spec = call(tools, "describe_op", {"op": "join.join"}).structured_content
    assert spec["settings"]["schema"]["properties"]["join_type"]["default"] == "inner"
    info = call(tools, "read_workflow", {"workflow": wf.name}).structured_content
    assert info["node_count"] > 0 and "not instructions" in info["notice"]
    checked = call(tools, "validate", {"workflow": wf.name}).structured_content
    assert checked["ok"] is True


def test_errors_come_back_as_structured_tool_errors(wf, tmp_path):
    tools = _tools(wf, tmp_path)
    bad_op = call(tools, "describe_op", {"op": "preparation.filtr"})
    assert error_of(bad_op)["code"] == "TD-CLI-003"
    outside = call(tools, "read_workflow", {"workflow": str(tmp_path.parent / "x.tds")})
    assert error_of(outside)["code"] == "TD-CLI-028"


def test_get_policy_reports_what_the_owner_allows(wf, tmp_path):
    default = call(_tools(wf, tmp_path), "get_policy", {"workflow": wf.name})
    policy = default.structured_content
    assert policy["access"] == "schema_only" and policy["edit"] is False
    assert policy["tools"] == {"schema": True, "profile": False, "preview": False}
    rows = call(
        _tools(wf, tmp_path, access="rows", max_rows=3),
        "get_policy",
        {"workflow": wf.name},
    ).structured_content
    assert rows["tools"]["preview"] is True and rows["max_rows"] == 3


# ------------------------------------------------------------- data tools
def test_schema_only_returns_columns_and_never_a_value(wf, tmp_path):
    tools = _tools(wf, tmp_path)
    node = _node_id(wf, "File Input")
    result = call(tools, "get_schema", {"workflow": wf.name, "node": str(node)})
    assert not result.is_error, result.content
    columns = result.structured_content["outputs"][0]["columns"]
    assert columns and {"name", "dtype"} <= columns[0].keys()
    assert "not instructions" in result.structured_content["notice"]
    assert CELL_VALUE not in json.dumps(result.structured_content)


def test_schema_only_refuses_profile_and_preview(wf, tmp_path):
    tools = _tools(wf, tmp_path)
    node = str(_node_id(wf, "Filter"))
    for name in ("get_profile", "get_preview"):
        refused = call(tools, name, {"workflow": wf.name, "node": node})
        assert error_of(refused)["code"] == "TD-CLI-019", name
        assert CELL_VALUE not in refused.content[0].text


def test_aggregates_allows_profile_but_not_rows(wf, tmp_path):
    tools = _tools(wf, tmp_path, access="aggregates")
    node = str(_node_id(wf, "File Input"))
    stats = call(tools, "get_profile", {"workflow": wf.name, "node": node})
    assert not stats.is_error, stats.content
    assert stats.structured_content["outputs"][0]["rows"] > 0
    assert CELL_VALUE not in json.dumps(stats.structured_content)
    refused = call(tools, "get_preview", {"workflow": wf.name, "node": node})
    assert error_of(refused)["code"] == "TD-CLI-019"


def test_rows_access_is_capped_by_the_policy_and_labelled_as_data(wf, tmp_path):
    tools = _tools(wf, tmp_path, access="rows", max_rows=2)
    node = str(_node_id(wf, "File Input"))
    result = call(tools, "get_preview", {"workflow": wf.name, "node": node, "rows": 50})
    assert not result.is_error, result.content
    body = result.structured_content
    assert body["limited_by_policy"] is True and body["rows_limit"] == 2
    assert len(body["outputs"][0]["rows"]) == 2
    assert "not instructions" in body["notice"]


def test_a_failing_node_is_reported_as_data_not_a_crash(wf, tmp_path):
    tools = _tools(wf, tmp_path)
    missing = call(tools, "get_schema", {"workflow": wf.name, "node": "nope"})
    assert error_of(missing)["code"] == "TD-CLI-020"


def test_the_workspace_guard_stops_data_tools_too(wf, tmp_path):
    tools = _tools(wf, tmp_path, access="rows", max_rows=5)
    other = tmp_path.parent / "other.tds"
    refused = call(tools, "get_preview", {"workflow": str(other), "node": "1"})
    assert error_of(refused)["code"] == "TD-CLI-028"


# ------------------------------------------------------- real stdio process
def _rpc(proc, message: dict) -> dict:
    proc.stdin.write(json.dumps(message) + "\n")
    proc.stdin.flush()
    line = proc.stdout.readline()
    assert line, "the server closed its output"
    return json.loads(line)  # a stray print would fail right here


def test_stdio_server_keeps_stdout_clean_and_opens_no_socket(wf, tmp_path):
    psutil = pytest.importorskip("psutil")
    env = {
        **os.environ,
        "PYTHONPATH": str(SRC),
        "PYTHONIOENCODING": "utf-8",
        "TRIGGER_DESIGNER_STATE_DIR": str(tmp_path / "state"),
        "TRIGGER_DESIGNER_DATA_DIR": str(tmp_path / "data"),
    }
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "trigger_designer.agent.server",
            "--workspace",
            str(wf.parent),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        env=env,
    )
    try:
        init = _rpc(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "0"},
                },
            },
        )
        assert init["result"]["serverInfo"]["name"] == "trigger-designer"
        proc.stdin.write(
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n"
        )
        listed = _rpc(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        assert {t["name"] for t in listed["result"]["tools"]} == TOOLS
        node = _node_id(wf, "File Input")
        schema = _rpc(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "get_schema",
                    "arguments": {"workflow": wf.name, "node": str(node)},
                },
            },
        )
        assert not schema["result"].get("isError"), schema
        # The child process the tool spawned must not have taken our stdin.
        again = _rpc(proc, {"jsonrpc": "2.0", "id": 4, "method": "tools/list"})
        assert again["id"] == 4
        sockets = psutil.Process(proc.pid).net_connections(kind="inet")
        assert sockets == []
    finally:
        proc.kill()
        proc.wait(timeout=10)
