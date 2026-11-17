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

EDIT_TOOLS = {"new_workflow", "patch_workflow"}
TOOLS = EDIT_TOOLS | {
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
        expected_read_only = tool.name not in EDIT_TOOLS
        assert tool.annotations.read_only_hint is expected_read_only, tool.name
        assert tool.annotations.destructive_hint is False, tool.name
    # Nothing can approve or run a workflow: that stays with a person.
    assert not {t.name for t in tools} & {"run", "approve", "run_workflow"}


def test_discovery_tools_return_structured_data(wf, tmp_path):
    tools = _tools(wf, tmp_path)
    ops = call(tools, "list_ops").structured_content
    assert "preparation.filter" in {row["op"] for row in ops["ops"]}
    spec = call(tools, "describe_op", {"op": "join.join"}).structured_content
    assert spec["settings"]["schema"]["properties"]["join_type"]["default"] == "inner"
    info = call(tools, "read_workflow", {"workflow": wf.name}).structured_content
    assert info["node_count"] > 0 and "not instructions" in info["notice"]
    checked = call(
        tools, "validate", {"workflow": wf.name, "check_data": False}
    ).structured_content
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
    assert policy["tools"] == {
        "schema": True,
        "profile": False,
        "preview": False,
        "apply_edits": False,
    }
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


# ---------------------------------------------------------------- edit tools
ADD_SORT = [
    {
        "op": "add_node",
        "type": "preparation.sort",
        "ref": "s",
        "settings": {"keys": [{"column": "amount", "order": "Descending"}]},
    }
]


def _new(tools: AgentTools, name: str, apply: bool):
    return call(tools, "new_workflow", {"workflow": name, "apply": apply})


def test_edits_are_dry_runs_unless_apply_is_set(wf, tmp_path):
    tools = _tools(wf, tmp_path, access="schema_only", edit=True)
    before = wf.read_bytes()
    dry = call(tools, "patch_workflow", {"workflow": wf.name, "edits": ADD_SORT})
    body = dry.structured_content
    assert not dry.is_error, dry.content
    assert body["dry_run"] is True and body["applied"] is False
    assert body["diff"]["summary"]["nodes_added"] == 1
    assert wf.read_bytes() == before
    fresh = _new(tools, "fresh.tds", apply=False)
    assert fresh.structured_content["created"] is False
    assert not (wf.parent / "fresh.tds").exists()


def test_apply_is_refused_without_edit_in_the_policy(wf, tmp_path):
    tools = _tools(wf, tmp_path, access="rows", max_rows=5)  # edit defaults to false
    before = wf.read_bytes()
    refused = call(
        tools,
        "patch_workflow",
        {"workflow": wf.name, "edits": ADD_SORT, "apply": True},
    )
    assert error_of(refused)["code"] == "TD-CLI-019"
    assert wf.read_bytes() == before and not list(wf.parent.glob("*.bak"))
    assert error_of(_new(tools, "fresh.tds", apply=True))["code"] == "TD-CLI-019"
    assert not (wf.parent / "fresh.tds").exists()


def test_apply_writes_keeps_a_backup_and_changes_the_hash(wf, tmp_path):
    tools = _tools(wf, tmp_path, access="schema_only", edit=True)
    old_sha = call(tools, "read_workflow", {"workflow": wf.name}).structured_content[
        "sha256"
    ]
    done = call(
        tools,
        "patch_workflow",
        {
            "workflow": wf.name,
            "edits": ADD_SORT,
            "apply": True,
            "expect_sha256": old_sha,
        },
    )
    body = done.structured_content
    assert not done.is_error, done.content
    assert body["applied"] is True and body["sha256_before"] == old_sha
    assert body["sha256_after"] != old_sha and body["backup"]
    assert Path(body["backup"]).exists()
    again = call(tools, "read_workflow", {"workflow": wf.name}).structured_content
    assert again["sha256"] == body["sha256_after"]
    assert call(
        tools, "validate", {"workflow": wf.name, "check_data": False}
    ).structured_content["ok"]


def test_a_stale_expect_sha256_is_refused_and_nothing_is_written(wf, tmp_path):
    tools = _tools(wf, tmp_path, edit=True)
    before = wf.read_bytes()
    stale = call(
        tools,
        "patch_workflow",
        {
            "workflow": wf.name,
            "edits": ADD_SORT,
            "apply": True,
            "expect_sha256": "0" * 64,
        },
    )
    assert error_of(stale)["code"] == "TD-CLI-026"
    assert wf.read_bytes() == before


def test_a_bad_edit_is_a_structured_error_and_all_or_nothing(wf, tmp_path):
    tools = _tools(wf, tmp_path, edit=True)
    before = wf.read_bytes()
    edits = [*ADD_SORT, {"op": "connect", "from": "s", "to": "no such node"}]
    bad = call(
        tools, "patch_workflow", {"workflow": wf.name, "edits": edits, "apply": True}
    )
    assert error_of(bad)["code"] in {"TD-CLI-020", "TD-CLI-027"}
    assert wf.read_bytes() == before


def test_new_workflow_creates_once_and_never_replaces(wf, tmp_path):
    tools = _tools(wf, tmp_path, edit=True)
    made = _new(tools, "fresh.tds", apply=True)
    assert not made.is_error, made.content
    assert made.structured_content["created"] is True
    assert (wf.parent / "fresh.tds").exists()
    assert error_of(_new(tools, "fresh.tds", apply=True))["code"] == "TD-CLI-027"
    assert error_of(_new(tools, wf.name, apply=True))["code"] == "TD-CLI-027"


def test_edit_tools_obey_the_workspace_guard(wf, tmp_path):
    tools = _tools(wf, tmp_path, edit=True)
    outside = str(tmp_path.parent / "elsewhere.tds")
    assert error_of(_new(tools, outside, apply=True))["code"] == "TD-CLI-028"
    refused = call(
        tools,
        "patch_workflow",
        {"workflow": outside, "edits": ADD_SORT, "apply": True},
    )
    assert error_of(refused)["code"] == "TD-CLI-028"


def test_get_policy_tells_the_harness_whether_it_may_apply(wf, tmp_path):
    tools = _tools(wf, tmp_path, access="schema_only", edit=True)
    policy = call(tools, "get_policy", {"workflow": wf.name}).structured_content
    assert policy["tools"]["apply_edits"] is True


# ------------------------------------- the pitfalls a real harness fell into
def _invoice_workspace(tmp_path):
    ws = tmp_path / "pitfalls"
    ws.mkdir()
    (ws / "invoices.csv").write_text(
        "invoice_id,vendor,amount\nA1,Acme,9999\nA2,Acme,20000\nB1,Birch,30000\n",
        encoding="utf-8",
    )
    return ws


def _agent(ws, tmp_path, **policy):
    policy = {"access": "schema_only", "edit": True, **policy}
    return AgentTools(
        policy_file=_policy_file(tmp_path, **policy), workspaces=[str(ws)]
    )


def _patch(tools, edits, apply=True, name="flow.tds"):
    return call(
        tools,
        "patch_workflow",
        {"workflow": name, "edits": edits, "apply": apply},
    )


READ = {
    "op": "add_node",
    "type": "input.file_input",
    "ref": "src",
    "title": "Invoices",
    "settings": {"filePath": "invoices.csv", "file_type": "csv"},
}
SUM_TEXT = {
    "op": "add_node",
    "type": "preparation.groupby",
    "ref": "totals",
    "after": "src",
    "title": "Total per vendor",
    "settings": {
        "actions": [
            {"field": "vendor", "action": "GroupBy", "output_name": "vendor"},
            {"field": "amount", "action": "Sum", "output_name": "total"},
        ]
    },
}
WRITE = {
    "op": "add_node",
    "type": "input.file_output",
    "ref": "out",
    "after": "totals",
    "title": "Totals file",
    "settings": {"filePath": "output/totals.csv", "file_format": "csv"},
}
LINKS = [
    {"op": "connect", "from": "src", "to": "totals"},
    {"op": "connect", "from": "totals", "to": "out"},
]


def _built(tools):
    assert not call(
        tools, "new_workflow", {"workflow": "flow.tds", "apply": True}
    ).is_error
    done = _patch(tools, [READ, SUM_TEXT, WRITE, *LINKS])
    assert not done.is_error, done.content
    return done.structured_content


def test_a_new_output_folder_is_created_and_files_are_stored_complete(tmp_path):
    ws = _invoice_workspace(tmp_path)
    tools = _agent(ws, tmp_path)
    call(tools, "new_workflow", {"workflow": "flow.tds", "apply": True})
    dry = _patch(tools, [READ, SUM_TEXT, WRITE, *LINKS], apply=False)
    assert not dry.is_error, dry.content
    folders = dry.structured_content["output_folders"]
    assert folders["created"] == [] and len(folders["to_create"]) == 1
    assert not (ws / "output").exists()
    done = _patch(tools, [READ, SUM_TEXT, WRITE, *LINKS])
    assert (ws / "output").is_dir()
    assert done.structured_content["output_folders"]["created"] == [str(ws / "output")]
    saved = json.loads((ws / "flow.tds").read_text(encoding="utf-8"))
    out = next(n for n in saved["nodes"] if n["op"] == "input.file_output")
    assert out["content"]["settings"]["filePath"] == str(ws / "output" / "totals.csv")


def test_a_name_given_to_a_node_is_what_the_editor_and_the_tools_show(tmp_path):
    ws = _invoice_workspace(tmp_path)
    tools = _agent(ws, tmp_path)
    _built(tools)
    info = call(tools, "read_workflow", {"workflow": "flow.tds"}).structured_content
    names = {n["label"]: n for n in info["nodes"] if "label" in n}
    assert set(names) == {"Invoices", "Total per vendor", "Totals file"}
    assert names["Total per vendor"]["title"] == "Aggregate"
    assert len(info["connections"]) == 2
    schema = call(
        tools, "get_schema", {"workflow": "flow.tds", "node": "Invoices"}
    ).structured_content
    assert [c["name"] for c in schema["outputs"][0]["columns"]][:2] == [
        "invoice_id",
        "vendor",
    ]


def test_validate_finds_the_text_column_before_any_run(tmp_path):
    """The mistake a real harness made: summing a CSV column that is text."""
    ws = _invoice_workspace(tmp_path)
    tools = _agent(ws, tmp_path)
    _built(tools)
    result = call(tools, "validate", {"workflow": "flow.tds"}).structured_content
    assert result["ok"] is False
    errors = [f for f in result["findings"] if f["level"] == "error"]
    assert errors and errors[0]["code"] == "TD-TYP-003"
    assert "'amount'" in errors[0]["message"]  # the real column, not ''
    assert "preparation.select" in errors[0]["message"]
    assert "dtype_custom" in errors[0]["message"]
    assert any("data types" in c for c in result["checked"])
    # Without the data check the structure alone looks fine, and says so.
    quick = call(
        tools, "validate", {"workflow": "flow.tds", "check_data": False}
    ).structured_content
    assert quick["ok"] is True and not any("data types" in c for c in quick["checked"])


def test_validate_passes_once_the_column_is_converted(tmp_path):
    ws = _invoice_workspace(tmp_path)
    tools = _agent(ws, tmp_path)
    _built(tools)
    fix = [
        {
            "op": "add_node",
            "type": "preparation.select",
            "ref": "cast",
            "title": "Amount to number",
            "settings": {
                "columns": [
                    {
                        "name": n,
                        "selected": True,
                        "dtype": t,
                        "rename": "",
                        "date_format": "",
                        "dtype_custom": t != "String",
                    }
                    for n, t in (
                        ("invoice_id", "String"),
                        ("vendor", "String"),
                        ("amount", "Float64"),
                    )
                ]
            },
        },
        # In a later batch a node is found by the name it was given.
        {"op": "disconnect", "from": "Invoices", "to": "Total per vendor"},
        {"op": "connect", "from": "Invoices", "to": "cast"},
        {"op": "connect", "from": "cast", "to": "Total per vendor"},
    ]
    assert not _patch(tools, fix).is_error
    result = call(tools, "validate", {"workflow": "flow.tds"}).structured_content
    assert result["ok"] is True, result["findings"]


def test_validate_flags_a_filter_that_compares_text_as_numbers(tmp_path):
    """Greater-than on a text column runs without error and keeps wrong rows."""
    ws = _invoice_workspace(tmp_path)
    tools = _agent(ws, tmp_path)
    call(tools, "new_workflow", {"workflow": "flow.tds", "apply": True})
    edits = [
        READ,
        {
            "op": "add_node",
            "type": "preparation.filter",
            "ref": "big",
            "after": "src",
            "title": "Over 10,000",
            "settings": {
                "column": "amount",
                "operation": "Greater Than",
                "value": "10000",
            },
        },
        {
            "op": "add_node",
            "type": "input.file_output",
            "ref": "out",
            "after": "big",
            "title": "Big invoices",
            "settings": {"filePath": "output/big.csv", "file_format": "csv"},
        },
        {"op": "connect", "from": "src", "to": "big"},
        {"op": "connect", "from": "big", "output": "true", "to": "out"},
    ]
    assert not _patch(tools, edits).is_error
    result = call(tools, "validate", {"workflow": "flow.tds"}).structured_content
    assert result["ok"] is False
    [finding] = [f for f in result["findings"] if f["level"] == "error"]
    assert finding["code"] == "TD-TYP-004"
    assert "'amount'" in finding["message"] and "Greater Than" in finding["message"]
    assert "preparation.select" in finding["message"]


def test_validate_reports_a_missing_output_folder(tmp_path):
    ws = _invoice_workspace(tmp_path)
    tools = _agent(ws, tmp_path)
    _built(tools)
    (ws / "output").rmdir()
    result = call(
        tools, "validate", {"workflow": "flow.tds", "check_data": False}
    ).structured_content
    assert result["ok"] is False
    assert any(f["code"] == "TD-CLI-014" for f in result["findings"])


def test_get_policy_explains_which_key_the_owner_changes(wf, tmp_path):
    policy = call(_tools(wf, tmp_path), "get_policy", {"workflow": wf.name})
    note = policy.structured_content["note"]
    assert '"edit"' in note and '"access"' in note and "data owner" in note


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
