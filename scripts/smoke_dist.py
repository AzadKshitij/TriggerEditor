"""Smoke-test a built ``dist\\TriggerEditor`` folder. Never touches the source tree.

    python scripts\\smoke_dist.py [dist\\TriggerEditor]

Checks ``tds --version``, ``tds validate``, the editor exe starting, and
``tds mcp`` driven over stdio (list tools, ``get_policy``, ``list_files``,
``read_workflow``, ``get_schema`` from a folder with a space and a non-ASCII
letter, and one refused call). Exits non-zero on the first failure.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "savedfiles" / "AI_Demo"


def step(text: str) -> None:
    print(f"- {text}", flush=True)


def fail(text: str) -> None:
    print(f"FAILED: {text}", flush=True)
    raise SystemExit(1)


def run(args: list[str], timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        stdin=subprocess.DEVNULL,
        check=False,
    )


def check_cli(folder: Path, work: Path) -> None:
    tds = folder / "tds.exe"
    out = run([str(tds), "--version"])
    if out.returncode != 0 or "0." not in out.stdout:
        fail(f"tds --version: {out.stdout} {out.stderr}")
    step(f"tds --version -> {out.stdout.strip()}")
    flow = work / "vendor_totals.tds"
    out = run([str(tds), "validate", str(flow), "--deep", "--json"])
    if out.returncode != 0:
        fail(f"tds validate: {out.stdout[-400:]} {out.stderr[-400:]}")
    step("tds validate --deep ok")
    out = run([str(tds), "mcp", "--help"])
    if out.returncode != 0 or "--workspace" not in out.stdout:
        fail(f"tds mcp --help: {out.stdout[-300:]} {out.stderr[-300:]}")
    step("tds mcp --help ok")


def check_editor(folder: Path) -> None:
    editor = folder / "TriggerEditor.exe"
    proc = subprocess.Popen(
        [str(editor)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        time.sleep(8)
        if proc.poll() is not None:
            fail(f"the editor exited early with code {proc.returncode}")
        step("editor stayed running for 8 seconds")
    finally:
        proc.kill()


async def check_mcp(folder: Path, work: Path) -> None:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    policy = work / "policy" / "policy.json"
    policy.parent.mkdir()
    policy.write_text('{"access": "schema_only", "edit": false}', encoding="utf-8")
    params = StdioServerParameters(
        command=str(folder / "tds.exe"),
        args=["mcp", "--workspace", str(work), "--policy", str(policy)],
    )

    async def call(session, name: str, **arguments) -> dict:
        result = await session.call_tool(name, arguments)
        text = "".join(getattr(part, "text", "") for part in result.content)
        if result.is_error:
            return {"_error": text}
        return json.loads(text) if text.startswith("{") else {"_text": text}

    async with (
        stdio_client(params) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        tools = {tool.name for tool in (await session.list_tools()).tools}
        for needed in ("get_policy", "list_ops", "get_schema", "patch_workflow"):
            if needed not in tools:
                fail(f"MCP tool missing: {needed} (have {sorted(tools)})")
        step(f"mcp: {len(tools)} tools")
        policy_info = await call(session, "get_policy")
        if "_error" in policy_info or "schema_only" not in json.dumps(policy_info):
            fail(f"get_policy: {policy_info}")
        step("mcp: get_policy ok")
        files = await call(session, "list_files")
        if "vendor_totals.tds" not in json.dumps(files):
            fail(f"list_files: {files}")
        step("mcp: list_files ok")
        flow = str(work / "vendor_totals.tds")
        workflow = await call(session, "read_workflow", workflow=flow)
        nodes = workflow.get("nodes") or []
        if not nodes:
            fail(f"read_workflow: {str(workflow)[:300]}")
        node = nodes[0].get("id") or nodes[0].get("title")
        schema = await call(session, "get_schema", workflow=flow, node=str(node))
        if "_error" in schema or "column" not in json.dumps(schema).lower():
            fail(f"get_schema (runs a child tds.exe): {str(schema)[:400]}")
        step("mcp: get_schema ok (child process works from the packaged exe)")
        refused = await call(
            session, "read_workflow", workflow=str(Path(work.anchor) / "nope.tds")
        )
        if "_error" not in refused and "error" not in json.dumps(refused).lower():
            fail(f"a path outside the workspace was not refused: {refused}")
        step("mcp: outside path refused")


def main() -> int:
    folder = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "dist" / "TriggerEditor")
    folder = folder.resolve()
    for exe in ("TriggerEditor.exe", "tds.exe"):
        if not (folder / exe).is_file():
            fail(f"missing {folder / exe}")
    with tempfile.TemporaryDirectory(prefix="tds smoke é ") as tmp:
        work = Path(tmp)
        for item in SAMPLE.iterdir():
            if item.suffix in (".csv", ".tds"):
                shutil.copy2(item, work / item.name)
        check_cli(folder, work)
        asyncio.run(check_mcp(folder, work))
    check_editor(folder)
    print("smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
