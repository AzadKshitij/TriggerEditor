# Plan: Make Trigger Designer AI-first (bring-your-own-harness)

## Context
Trigger Designer is a local-first PySide6 node-graph tool for audit analysts (`.tds` workflows, Polars/DuckDB engine, headless CLI). It has no AI code, and its core promise is **no network requests from the app** unless strictly required.

Decision: the app will **not** ship an in-app assistant, chat dock, or LLM client. An in-house chat is hard to maintain and can't match the UI/functionality analysts use daily. Instead, "AI-first" means **the app is the best possible tool for an external AI harness to drive**: the user picks their own harness (Claude Code, Codex, Cursor, Copilot, a local-model agent, anything MCP-capable or CLI-capable), and that harness builds, edits, validates, runs and explains workflows through a stable local interface. The GUI remains the human's review/edit surface. The app itself stays fully offline.

## Principles
1. **Zero network in the app.** No provider adapters, no API keys, no telemetry. The only permitted network use is an explicit, user-initiated download of an optional module (see Phase 5), isolated in one file.
2. **The harness owns the model and its egress.** The app only controls what *its tools return*. Tools default to **schema and aggregate stats, never row values**; value access is opt-in per workflow/session.
3. **Agent edits are reviewable and undoable.** Anything an agent changes appears in the GUI as a visible diff and a single undo step.
4. **Same safety layer.** Agent-supplied SQL/formulas/settings go through `core/sql_guard.py`, `core/codegen_safe.py` and per-node `DEFAULTS`/`FORM` validation. No custom-code node, no exec of agent text.
5. **Machine-readable everything.** Anything a human can learn from docs, an agent can read as structured data.

## Phased roadmap

**Phase 1 — Machine-readable surface (foundation)**
- Extend `core/headless/op_catalog.py` into a full **node spec export**: per op, description, inputs/outputs, settings JSON-Schema (generated from each node's `DEFAULTS` + declarative `FORM` in `qt/helpers/shaping_support.py`; audit nodes from `ParamsBase` in `Audit/_base.py`), example settings, links to `docs/nodes/*`.
- `--json` output on all CLI commands (`run`, `validate --deep`, `info`, `params`, `verify-log`) with stable schemas, structured error objects keyed by `TD-SHAPE-xxx` codes (from `core/errors/`) including the plain-language message and a fix hint.
- New CLI commands: `ops` (catalogue), `schema <file> <node>` (column names/types at a node, no values), `profile <file> <node>` (aggregate stats only), `preview <file> <node> [--rows N]` (values; gated by access policy).
- Fully Qt-free so it works without the GUI: build on `core/headless/workflow_file.py` (`WorkflowDoc`).

**Phase 2 — Safe workflow authoring API (Qt-free)**
- New `core/authoring/`: pure functions over `WorkflowDoc` — `add_node`, `remove_node`, `connect`, `disconnect`, `set_setting`, `set_label`, `auto_layout`, `diff(a, b)`. Settings validated against the Phase-1 schemas and `sql_guard`; unknown ops/keys rejected with structured errors.
- Atomic write (reuse existing atomic save), `--dry-run` returning a diff, never silently overwriting: edits write to the file only with an explicit `--apply`, and keep a `.bak`/patch copy.
- Golden tests: scripted edit sequences produce the same `.tds` as the GUI would (pattern: `tests/e2e/test_workflow_goldens.py`).

**Phase 3 — MCP server (local, stdio only)**
- `trigger-designer-mcp` entry point in `pyproject.toml` (optional extra `agent`, base install unchanged). Speaks MCP over **stdio** (no sockets/ports). Exposes the Phase 1–2 functions as tools: `list_ops`, `describe_op`, `read_workflow`, `get_schema`, `get_profile`, `preview_rows`, `add_node`, `connect`, `set_setting`, `validate`, `run`, `explain_error`, `diff`, `verify_log`; plus resources for node docs, `FORMULA_TOOL_REFERENCE.md`, `SQL_FORMULA_REFERENCE.md`.
- Per-workflow **agent access policy** (`.tds` metadata or sidecar `*.agent.json`): `schema_only` (default) | `aggregates` | `rows(N)`; read-only vs edit; path allow-list (reuse path-remapping from `core/headless/params.py`). Policy enforced in the server, not left to the prompt.
- `run` goes through `NodeExecutor` with the existing `code_filter`/`policy_violation` seam (`core/headless/code_policy.py`) and the approval flow (`approve`) so agent-initiated runs still need human approval where configured.

**Phase 4 — GUI integration (human in the loop)**
- **External-edit awareness:** file watcher on open `.tds` files; when an agent changes one, the app shows a non-modal banner with a node-level diff (added/changed/removed nodes and settings) and Reload/Review. Applying is one undo step named "External Edit" via the existing `UndoController` / `SceneSnapshotCommand` (respect `syncing()` rules and `onHistoryRestored(force=True)` from `AGENTS.md`).
- Visual cue on agent-touched nodes until reviewed (UI per `docs/DESIGN_SYSTEM.md`, `objectName` + `base.qss`, icon-first with tooltips/accessibleName).
- Optional local-only control channel (named pipe / stdio) so a harness can tell the open app to select a node or focus a problem — only if file-watching proves insufficient; **no TCP/loopback listener**.

**Phase 5 — Optional capability modules (the only network path)**
- A user-initiated "Add module" flow for extra ML/AI capabilities (e.g., local embedding model for Fuzzy Match, anomaly scoring): explicit consent dialog naming source, size, and hash; download isolated in one module (`core/modules/downloader.py`); verified signatures/hashes; modules run offline afterward; fully removable.
- Test asserting no other module imports network libraries (`socket`, `urllib`, `http`, `requests`, …) and that the app makes zero requests with no module action.

**Phase 6 — Agent enablement kit (docs, not code)**
- Ship `docs/agents/`: a workflow-authoring guide for agents (node catalogue, idioms, audit-test recipes), ready-made `AGENTS.md`/skill/rules snippets and sample MCP config for Claude Code, Codex, Cursor, and generic CLI-only harnesses; example prompts and verified end-to-end walkthroughs.
- Update `docs/guide/security-and-privacy.md` and `docs/internal/dev/security-model.md`: "the app sends nothing; your harness may — here is what our tools expose and how to restrict it."
- Run records (hash-chained, value-free) record the **source** of each change/run (`gui`, `cli`, `mcp`, agent-supplied label) so auditors can see what was agent-driven.

## Critical files
- Extend: `core/headless/op_catalog.py`, `core/headless/workflow_file.py`, `core/headless/params.py`, `cli/*`, `qt/helpers/shaping_support.py`, `core/errors/*`, `qt/undo/*` (external-edit command), `pyproject.toml` (entry point + `agent` extra), `docs/guide/*`.
- New: `core/authoring/`, `core/mcp/` (stdio server + access policy), `core/modules/` (Phase 5), `docs/agents/`, tests in `tests/unit/authoring/`, `tests/unit/mcp/`, `tests/e2e/test_agent_edit_roundtrip.py`.
- Reuse (don't rewrite): `WorkflowDoc`, `op_catalog`, `set_setting`/`push_property_change`, `NodeExecutor` + `code_policy`, `sql_guard`, `codegen_safe`, hash-chained run log, `IconButton`/`ConfigSection` for any UI.

## Risks / open decisions
- Harness data egress is outside our control → mitigated by schema-only defaults and server-enforced access policy; document clearly.
- Prompt injection through cell values/column names returned by tools → never return values by default; sanitize/label tool output as data; all edits validated + human-reviewable.
- Concurrent human and agent edits to the same `.tds` → file-watcher conflict handling (reload prompt, never auto-overwrite unsaved GUI changes).
- Schema stability: node settings JSON-Schema becomes a public contract → version it (`schema_version`) and add a compatibility test.
- Python 3.14 + MCP SDK compatibility → verify via Context7 docs before Phase 3; keep MCP optional.
- Baseline `ruff check` has 562 errors; keep new code clean and verify only touched files.

## Verification (per phase)
- `uv run --project . ruff format <files>` → `ruff check <files>` → focused `pytest`.
- Phase 1–2: golden tests for op/schema export and edit sequences; malicious inputs (non-SELECT SQL, unknown op/key, path escape) rejected with structured errors.
- Phase 3: MCP tool-call tests via an in-process client; access-policy tests (`schema_only` never returns values); `run` honours approval/policy.
- Phase 4: e2e — external edit to an open workflow produces diff banner, one undo step, and undo restores prior state (extend `test_undo_integration.py`); manual check in the running app.
- Phase 5: network-import guard test; zero requests at idle.
- End-to-end manual: with Claude Code (or another harness) configured with the MCP server, build a "duplicate invoices > 10k" workflow on `savedfiles/` data, review in GUI, run headless, confirm run record tags the source.
