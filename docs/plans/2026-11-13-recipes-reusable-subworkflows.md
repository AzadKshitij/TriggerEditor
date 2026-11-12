# Plan: Recipes — reusable sub-workflows (Alteryx-macro equivalent)

Status: proposed (plan only, nothing implemented) · Branch: `recipe` · Date: 2026-11-13

## 1. What we are building

A **Recipe** is a reusable block of nodes saved in its own file (`.tdr`) that appears in any workflow as **one node** with named input ports, named output ports, and a small set of user-facing **parameters**. It is the equivalent of an Alteryx standard macro.

**Name.** Keep **Recipe** (file extension `.tdr`, "Trigger Designer Recipe"). It is distinctive, doesn't borrow Alteryx vocabulary, and the metaphor maps cleanly: *inputs = ingredients, parameters = quantities, output = the dish*. Alternatives considered: Module (too generic, collides with Python modules and the planned optional "capability modules"), Component (UI jargon), Blueprint (implies a template you copy, not something you call), Routine (programmer-ish). Interface nodes are called **Recipe Input** / **Recipe Output**.

**Alteryx mapping**

| Alteryx | Trigger Designer |
|---|---|
| Standard macro (`.yxmc`) | Recipe (`.tdr`) |
| Macro Input / Macro Output tools | Recipe Input / Recipe Output nodes |
| Control Parameter + Action tools | Declared **Parameters**, bound to node settings |
| Macro search paths | Recipe **library folders** |
| Batch / Iterative macro, Analytic App | **Out of scope** for v1 |

**"Seamless" — the acceptance bar.** All of these must work without the user touching a file path or JSON:
1. Select nodes → *Create Recipe* → dialog → the selection is replaced by one Recipe node, wired exactly as before, in **one undo step**, and the workflow still produces identical output.
2. Drag a recipe from the palette (or Shift+A search) → set parameters in the Config Dock → connect → it evaluates live and runs like any node.
3. Double-click / "Edit recipe" opens the recipe in its own tab; save; every workflow using it shows "update available" and updates in one click with a clear diff.
4. A workflow sent to a colleague (or run by the CLI on a scheduler) works **without** the recipe library being present, and the audit trail shows exactly which recipe logic ran.
5. Existing `.tds` files are untouched; opening a recipe workflow in an older build degrades to the "unknown node" placeholder, not a crash.

## 2. Key design decisions (with rationale)

### D1. Instances embed a snapshot of the recipe, plus a link to its origin
The Recipe node in a `.tds` stores: `recipe_ref` (uuid, name, revision, sha256, origin path) **and the full recipe definition** (deduplicated in `workflow_metadata.recipes` keyed by sha256). The library file is only used to *offer updates*.

Why (each point closes a gap the codebase review found):
- **Approvals.** `approvals.py` pins the sha256 of the parent `.tds` bytes only. With embedding, the recipe logic is inside those bytes, so editing a library file can never silently change an approved workflow.
- **`verify-log` V4 / run records** compare `workflow_sha256`; embedded logic makes a recipe change detectable.
- **Untrusted second file.** No runtime read of a path chosen by file content → no new path-traversal / allow-list surface. `HeadlessSession` loads a relocated work copy under `<state>/work/<run_id>/`, which would break relative recipe paths; embedding sidesteps it.
- **Portability.** Email a `.tds`, it runs. This is the single biggest practical advantage over Alteryx's by-reference macros.
- Cost: bigger `.tds`, and updates are explicit. Mitigation: dedupe by hash, show "Update available (rev 3 → 5)", one-click update, CLI `recipe update`.

### D2. Execution = flatten at the run list (not a sub-executor)
Each recipe instance owns a **private inner scene** (hidden `TriggerScene`, fresh node ids per instance). At run time the parent's topological list is **expanded**: the recipe node is replaced by `[inner nodes in inner topological order…, recipe node]`. Inner Recipe Input nodes alias the parent's upstream variables; the Recipe node's own `get_code()` aliases inner Recipe Output variables to its declared output variable names.

Why not a sub-executor: it would hide inner nodes from the run recorder (keyed by `int node_id`, one flat list), from `code_filter`/`code_policy` (CLI validates only the outer snippet), from per-step errors/timings/cancel, and a nested `execute_node` on the single pooled worker thread would deadlock. Flattening reuses `run_nodes` (skip / continue-on-error / cancel), `verify_plans`, `code_policy` and the recorder unchanged apart from the id bookkeeping below. Spike S2 validates this before we commit.

### D3. Interface via nodes (ports) and a panel (parameters)
- **Ports:** `Recipe Input` / `Recipe Output` nodes inside the recipe, each with a unique **name**, label, description; Input also has `required` and an optional **expected-schema template** (columns + dtypes).
- **Parameters:** declared in an Interface panel in the recipe editor: `name, label, type, default, description, options, bind:{node_id, setting}`. Types v1: `string, int, float, bool, choice, column` (column picker fed from a chosen input port). Bindings target only **scalar settings declared in a node's `FORM`** (text/int/float/check/combo/column). List-valued settings (rule lists, mapping tables) are not bindable in v1. Reuses the shape of the existing `workflow_metadata.parameters` entries.
- Parameter values flow through the same `set_setting` path as hand edits, so SQL still hits `sql_guard` and codegen still uses `codegen_safe` JSON payloads — no new injection surface.

### D4. v1 scope limits (deliberate)
- **No File Output / Workpaper Output / File Input inside recipes in v1.** Data enters through Recipe Input ports; side effects (files, workpapers) stay in the parent. This keeps `file_nodes`, `io_paths`, output staging, `approve` review and Workpaper "workflow steps" correct with no new work. *v1.1:* File Input inside recipes via `path_in` parameters.
- **Nesting allowed**, depth cap 8, cycle detection by recipe uuid chain, total-node cap (e.g. 500 inner nodes per instance tree).
- **No custom code** (already no custom-code node); recursive `custom_code` gate anyway.
- **Test runs in the recipe editor are not written to the run log** (avoids `foo.tds`/`foo.tdr` → shared `foo.runs` folder collision in `core/audit/store.py:86`; also fix that stem logic defensively).
- Sample data is **never embedded** in a recipe by default (audit data is sensitive and recipes get shared): schema-only templates; optional editor-only "test data file" path that is not saved into the instance.

### D5. Identity & versioning
`recipe_uuid` (stable across saves, new on Save As / fork — mirrors `reset_workflow_identity`), `revision` (int, auto-incremented on every save), optional human `version` label, `sha256` of the canonical definition. Update detection = library sha ≠ embedded sha. Compatibility diff is by **port name** and **parameter name**.

## 3. File formats

### `.tdr` (JSON via orjson, atomic save like `.tds`)
```
{
  "kind": "recipe",
  "recipe_metadata": { "schema_version": 1, "recipe_uuid", "name", "description", "category",
                       "revision", "version", "author", "icon", "saved_at", "app_version", "min_app_version" },
  "interface": {
    "inputs":  [ {"name","label","description","required","template":[{"name","dtype"}]} ],
    "outputs": [ {"name","label","description"} ],
    "parameters": [ {"name","label","type","default","description","options","bind":{"node_id","setting"}} ]
  },
  "nodes": [...], "edges": [...], "groups": [...], "comments": [...]   // same dict shapes as .tds
}
```
Inner graph uses the existing node/edge/group serialization, so existing node `deserialize` code and tolerant-default behaviour apply. Unknown keys preserved on round-trip (same policy as `loaded_workflow_metadata`).

### Parent `.tds` additions
- Node: `op = "recipe.instance"`, `content = { recipe_ref, param_values, ports (names, in order) }`; sockets serialized as for any node.
- `workflow_metadata.recipes = { "<sha256>": <full recipe definition> }`.
- `WORKFLOW_SCHEMA_VERSION` 2 → **3** so older builds warn "saved by a newer version"; unknown `recipe.*` ops load as `TriggerNode_Unknown` with raw content preserved (precedent: `qt/widgets/nodes/unknown.py`). Add to CHANGELOG under "Behaviour changes that may affect saved workflows".

## 4. Architecture

### New packages
- `core/recipes/` (Qt-free; add to `trigger.spec` `_CORE_PACKAGES`, `test_packaging_spec`)
  - `format.py` dataclasses + read/write + schema migration hook; `hashing.py` canonical sha256; `validate.py` (limits, forbidden ops, interface consistency, binding existence, cycle/depth); `library.py` (scan folders, header cache by mtime+size, search); `diff.py` (interface/compatibility diff, update plan).
- `qt/recipes/`
  - `nodes.py` — `TriggerNode_RecipeInstance`, `RecipeInputNode`, `RecipeOutputNode` (+ contents).
  - `inner_scene.py` — build/cache hidden scene per instance, feed inputs, collect outputs, apply parameters, reconcile ports.
  - `expand.py` — `expanded_run_nodes(scene)`, upstream map, alias code generation; single source used by GUI run, headless run, `getPyFile`, `validate --deep`.
  - `editor_window.py` (`RecipeSubWindow(TriggerSubWindow)`), `interface_dock.py`, `create_dialog.py`, `update_dialog.py`, `recipes_list.py` (palette tab), badge painter helpers.

### Registration
- New family `NodeTypes.RECIPE` with `RecipeNodes` IntEnum: `INSTANCE`, `INPUT`, `OUTPUT` (ops `recipe.instance|input|output`; append-only, never rename). Add to `NODE_REGISTRIES`, `_OPCODE_ENUMS`, lazy specs, icons (`resources.json`; Material Symbol via `ResourceManager.register_material` is an option), `op_catalog.OPS` rows, and a Shift+A group. Follow every step of `docs/internal/dev/adding-a-node.md`.
- Because the loader calls `node_class(scene)` with no arguments (`NE/node_scene.py:991`) and sockets come from saved data (`Node.deserialize` creates missing sockets), `TriggerNode_RecipeInstance` is constructed empty and builds its ports from `content`/saved sockets — same pattern as `TriggerNode_Unknown`.
- `Node.deserialize` never *removes* sockets, so the instance implements its own `reconcile_ports(interface)` (match by port name; drop sockets + edges for removed ports and report them) and calls it on load, on undo-restore (`onHistoryRestored`), and on update.

### Inner engine (live evaluation)
`RecipeInstanceNode.processInputs(input_values)`:
1. ensure inner scene (lazy; keyed by instance), apply `param_values` (guarded by `syncing`);
2. set each inner Recipe Input's fed frame (+ upstream `variable_name`); missing optional input → empty frame from template;
3. run the inner scene's own evaluator synchronously (separate `scene.evaluator`; the parent's `_evaluating` guard isn't re-entered);
4. read inner Recipe Output values → return output dicts named with the instance's own output variable names.
Inner failure ⇒ instance fails with `TD-RCP-005` carrying the inner step's translated message and culprit. Parameter edits use `DeferredEvaluation` semantics (pending badge) like other nodes. `live_sample` (100 rows) applies at the instance boundary as for shaping nodes.

### Run integration (the delicate part)
- `expanded_run_nodes(scene)`: topological parent list → recursive replace. Inner node ids are made **globally unique per instance** (inner scene nodes are re-id'd with fresh `id(obj)`; the original file-side id is kept as `recipe_inner_id`). Variable names are `var_<kind>_<content.id>` and already unique because content ids are ephemeral per live widget.
- Touch points: `workflow_execution_mixin.executeWorkflow` (use expanded list, extend `_direct_upstream` with the synthetic boundary edges so skip/blocked works), `_prune_node_results` / `_declared_output_variable_names` (instance output variables), `_on_node_finished/_on_node_errored/skipped` (mirror an inner failure onto the instance node as `TD-RCP-005` and add the instance to `blocked` so downstream nodes skip as knock-on), `design_window.getPyFile` (emit inner code in order), `qt/headless.py` ordered nodes.
- Per-instance `execution_timeout` = max over inner (each inner node still has its own timeout since each is executed separately).
- Inner Recipe Input `get_code()` (instance mode) = `var_in = <outer var>`; editor mode = template/test-file frame. Output node/instance emit plain name aliases — verify `ast.Assign Name=Name` passes `code_policy.ALLOWED_NODE_TYPES` (Spike S3; add test either way).

### Audit trail
- Inner nodes get their own `NodeSpec`s (`audit_bridge.node_specs_from_window` extended) with synthetic edges through the boundary, so `rows_in/rows_out`, fingerprints, `code_sha256` per inner step are recorded.
- `NodeRunRecord` gains **defaulted** fields: `parent_node_id`, `depth`, `recipe` `{name, uuid, revision, sha256, inner_node_id}`; add to `FIELD_ADDED_IN`, bump `RUN_RECORD_SCHEMA_VERSION`, update `view/export/compare`. `_check_node` still requires int `node_id` (kept).
- Recipe instance `settings` in the record = ref + parameter values + `recipe_sha256` (not the embedded blob; `sanitize` cuts at 20,000 chars).
- Run log sheet (`core/workpaper/sheets_runlog.py`): indent/prefix inner rows by depth. Workpaper "workflow steps" (`workflow_snapshot.collect_workflow` stops at the instance): implement `describe_settings()` on the instance to print recipe name, revision, sha8, parameters and an inner-step summary.

### Errors
New family `TD-RCP-xxx` (catalogue + `_PASSTHROUGH` mirror + `gen_error_reference.py`, per the registry test): 001 recipe file invalid/corrupt, 002 recipe source missing (info: using embedded copy), 003 interface changed (ports removed / params removed or retyped), 004 invalid parameter value, 005 step inside recipe failed (culprit inner step), 006 nesting too deep / cycle, 007 node not allowed in recipes, 008 required recipe input not connected, 009 recipe too large. Plain-language messages per `docs/internal/plan/03`.

### Undo
- Create-from-selection, Explode, Update, Port reconcile each record **one** `storeHistory` snapshot ("Recipe Created", "Recipe Updated"…), performing all mutations first (snapshot approach is the existing norm for structural edits).
- Parameter edits: `push_property_change` via `set_setting` (inherit `ShapingContent`) — merge keys for text.
- Restore re-creates the instance through `scene.deserialize`; inner scene must be rebuilt cheaply → cache keyed by (sha256, param_values) and re-attach.
- The editor tab has its own `UndoController`.

## 4b. Upstream split: `nodeeditor-qtpy` vs this app

`nodeeditor-qtpy` (pinned at `pyproject.toml:60`, currently 0.8.2) is maintained by the same owner, so anything **generic** moves upstream as a backward-compatible minor release; anything that knows what a recipe, a run, or an audit record is stays in the app. Dev loop: `scripts/sync-nodeeditor.ps1` overlay while iterating, then release and bump the pin.

**Moves upstream (generic graph-editor capabilities):**

| # | Upstream change | Replaces this app-side workaround |
|---|---|---|
| U1 | `Node.reconcile_sockets(specs)`: add / remove / reorder sockets by stable key, remove attached edges, report what was dropped; optional `Node.deserialize(..., shrink=True)` | Hand-rolled port reconcile (today `Node.deserialize` never removes sockets) |
| U2 | Serialize socket **name** and **label**; multi-character labels and full-name tooltips on `grSocket` | One-letter labels that aren't saved |
| U3 | `Scene.classify_boundary(nodes)` returning incoming / outgoing / internal edges **with sockets** (generalises `Group._classifyEdges`, which returns edges only) | Re-implementing boundary detection for Create Recipe |
| U4 | View-free subgraph API: `scene.serialize_subgraph(nodes)` and `scene.instantiate_subgraph(data, offset=..., remap_ids=True) -> hashmap`, with no clipboard, mouse position or history side effects unless asked | Copying `SceneClipboard` internals for Create / Explode |
| U5 | Non-destructive load: `Scene.deserialize(data, merge=True)` (today it deletes every node not in the data) | Never being able to merge into a live scene |
| U6 | Collision-free ids: optional uuid ids, or `restore_id=False` that guarantees unique runtime ids with a retained `source_id` | Re-id'ing inner nodes per recipe instance by hand |
| U7 | `with scene.history.batch("Recipe Created"):` collapses several mutations into one stamp / undo step | Careful manual single `storeHistory` calls |
| U8 | **Headless scene mode**: `Scene(headless=True)` using a null graphics-node class (no `QGraphicsItem` / content-widget cost) for hidden inner scenes | Spike S1 risk: heavy hidden scenes; fallback to a Qt-free chain |
| U9 | Per-widget document type: `default_extension` / `getFileDialogFilter` honoured by Open **and** Save As (Save As currently hard-codes the filter at `node_editor_window.py:224`) | Overriding Save As for `.tdr` |
| U10 | Optional `Node.is_container` / badge hook on `GraphicsNode` for a corner glyph painted inside `boundingRect` | Patching `TriggerGraphicsNode.paint` |

**Stays in the app (domain logic):** the `.tdr` format and validation, interface nodes and parameters, embedded store and update flow, run-list expansion and aliasing, audit / recorder / workpaper changes, error codes, library scan, palette and Shift+A, CLI.

**Rules for the upstream work:** every U-item is additive and off by default (existing behaviour and tests unchanged); each ships with upstream unit tests; one release (0.9.0) carries U1 to U10 so the app bumps its pin once; the app keeps working against 0.8.x until the bump lands (feature code behind a capability check during the transition).

## 5. UX specification

**Palette & menus.** `NodesDock` gets a **Recipes** tab (custom widget, not `NodeTypes`-driven): search box, category groups, icon, name, revision, "refresh" `IconButton`. Drag payload uses a **second mime type** (`application/x-trigger-recipe`, carries recipe uuid) handled in `design_window.onDrop`; Shift+A gets a "Recipes" submenu rebuilt on `aboutToShow` (today actions are built once per window — must not be). The static `RECIPE` family tab lists Instance (blank "Choose recipe…"), Input, Output; Input/Output are enabled only in a recipe editor (refresh on window activation).

**Recipe node on canvas.** Same 120×120 card; recipe glyph badge top-right (painted inside `boundingRect` per the docstring at `node_graphics.py:66-81`, opt-in via `node.is_recipe`, also in low-detail path); status chip: *Up to date / Update available / Source missing (embedded copy) / Interface changed*. Ports keep the one-letter label convention; **full port names as tooltips** (spike: hover label). Node title = recipe name; label row works as usual.

**Config Dock.** `RecipeContent(ShapingContent)` overrides `_sections()` to build the form from the recipe's parameters (`Field` kinds already cover text/int/float/check/combo/column), plus sections: *Recipe* (name, description, revision, origin, **Open recipe** / **Update…** / **Detach (explode)** icon buttons) and *Inputs* (status per port). Missing recipe file → `EmptyStateLabel`. Follows `docs/DESIGN_SYSTEM.md` §§1–7, `IconButton`/`ConfigSection`/`EmptyStateLabel`, tooltips + accessibleName, no inline `setStyleSheet`, `objectName` + `base.qss`/`_style.scss`.

**Create Recipe from selection** (context menu next to "Group Selected Nodes", and Ctrl+Shift+R):
- Boundary computed with the logic of `Group._classifyEdges` (`NE/node_group.py:278-343`); internal edges + node dicts via `SceneClipboard.serializeSelected`.
- One **input port per distinct outside source socket** (fan-out into several inner sockets shares one port); one **output port per distinct inner output socket** with outside consumers (if none, terminal outputs offered).
- Dialog: name, description, category, save location (library folder / choose file), port names (prefilled from source/target node titles), optional parameter promotion (checklist of bindable settings of selected nodes). Validation lists disallowed nodes (File Input/Output, Workpaper Output) with reasons.
- Result: `.tdr` written atomically, selection replaced by an instance, edges reconnected, instance selected, one undo step.

**Recipe editor tab.** `.tdr` opens in `RecipeSubWindow` (subclass of `TriggerSubWindow` so docks keep working; satisfies the `hasattr(widget,"diagnostics")` check in `onSubWindowActivated`). Distinct tab prefix/icon (stem collision in tab titles otherwise), top banner "Editing recipe · rev N · used as one node", **Interface dock** (ports, parameters + bindings, metadata, validation status), Run/Preview with template or test data, "Test with parameters" panel. Save validates (forbidden nodes, unnamed/duplicate ports, dangling bindings, unconnected Output) and bumps revision.

**File handling.** Override `getFileDialogFilter` → `Designs (*.tds *.tdr);;Workflows (*.tds);;Recipes (*.tdr)`; `openFile`/`onFileOpen` dispatch by extension (currently hard-coded to `TriggerSubWindow` in four places); File menu gets **New Recipe**; recent files and session restore (`layout_state.py`) work through the same dispatch; welcome dialog lists both; `.iss` installer gets a second association (`.tdr` rows + new `.ico`); `main.py` already takes `argv[1]`.

**Update flow.** Instance badge → *Update…* dialog: revision diff, ports added/removed/renamed, parameters added/removed/retyped, "N edges will be removed" warning; apply = reconcile ports + keep matching parameter values + one undo step. Bulk "Update all recipes in this workflow" in the File menu.

## 6. Headless / CLI

- `op_catalog.OPS`: rows for `recipe.instance|input|output`; `test_op_catalog_matches_registry` stays green. Interface nodes in a *parent* workflow are rejected (`static_validate`).
- `static_validate` (Qt-free, via `core/recipes/validate.py`): recurse into `workflow_metadata.recipes` — known ops only, forbidden-node check, interface consistency, binding existence, nesting depth/cycle, size/node caps, recursive `custom_code` gate (`check_trust`), reference integrity (every instance's sha exists in the table).
- `validate --deep`: build via `HeadlessSession.load`, then run `validate_generated_code` over **expanded** nodes so inner code is never skipped.
- `approve`: review block lists each recipe (name, revision, sha8, parameters, inner op summary) — approval already covers the bytes.
- Parameters from the CLI: allow-list row `PARAM_TARGETS[("recipe.instance","param:<name>")]` for `string/int/bool/choice`, declared in `workflow_metadata.parameters` bound to the instance node id. (Path-typed recipe parameters arrive with v1.1.)
- New subcommands: `recipe info <file.tdr>`, `recipe validate <file.tdr>`, `recipe list [--library DIR]`, `recipe update <workflow.tds> [--library DIR] [--apply]` (never overwrites without `--apply`, writes `.bak`).
- `verify-log`: no change needed (workflow sha now covers recipes); add a test.
- `info`/`paths`: no file nodes are added in v1 (no I/O inside recipes), assert that with a test.

## 7. Phased roadmap

**Phase 0 — De-risking spikes (≈2–3 days, throwaway code, findings written up)**
- S1 hidden `TriggerScene` per instance: instantiate offscreen, with no view; measure memory/time for 30-node recipes × 10 instances; confirm graphics-node/content-widget cost is acceptable. *Fallback:* lazy build + cache, or a Qt-free chain over `core.shaping.run_node` for shaping nodes.
- S2 flatten-at-run-list: hand-build the expanded list and run through `run_nodes` incl. failure/skip propagation and recorder.
- S3 `code_policy` accepts alias assigns; S4 single-undo create-from-selection via one `storeHistory`; S5 id uniqueness (two instances of one recipe in one scene, recorder + `ProblemsStore` + exec namespace); S6 socket reconcile incl. undo.
- Exit: architecture D1–D3 confirmed or amended in this document.

**Phase U — Upstream `nodeeditor-qtpy` 0.9.0 (M, runs in parallel with Phase 1)**
Implement U1–U10 from §4b in the package repo with its own tests; prototype with `sync-nodeeditor.ps1`; release 0.9.0; bump the pin in `pyproject.toml` and `uv.lock`; add a smoke test that the app's existing e2e suite passes on 0.9.0 before any Recipe code depends on it. Phase 2 starts only after the release (or against the overlay on a dev branch). Phase 0 spike S1 and S6 now decide the exact shape of U8 and U1.

**Phase 1 — Format & core library (Qt-free) (M)**
`core/recipes/*`, `.tdr` read/write/hash/validate/library scan/diff, error codes, `trigger.spec`, unit tests (malformed, oversized, cycles, forbidden nodes, hash stability across key order).

**Phase 2 — Nodes & inner engine (L)**
Recipe Input/Output/Instance nodes, registration + `op_catalog`, ports from interface, `reconcile_ports`, inner scene build/feed/collect, parameters apply, embedded store in `workflow_metadata.recipes`, schema v3, Unknown/broken-recipe fallbacks, live evaluation, error mapping, Config Dock form. UI tests for load/save round-trip, undo/redo, port reconcile.

**Phase 3 — Run & audit integration (L)**
`expand.py`, `executeWorkflow`/headless/`getPyFile` integration, upstream map, results pruning, error mirroring + knock-on, recorder specs + schema fields + view/export/compare, Run log/Workpaper rendering. E2E golden: workflow with inline nodes vs. the same via a recipe → identical output frames and equivalent run record.

**Phase 4 — Authoring UX (L)**
`RecipeSubWindow`, Interface dock (ports, parameters, bindings, validation), template/test data, Create-from-selection dialog, save-to-library, Explode (inverse; reuse clipboard deserialize with `restore_id=False` + hashmap remap).

**Phase 5 — Discovery & lifecycle (M)**
Library palette tab + Shift+A rebuild + drag payload, open/new/recent/session-restore dispatch, file filter, installer association, update detection + dialog + bulk update, status chip + badge, "Open recipe", "Detach".

**Phase 6 — Headless/CLI (M)**
`static_validate` recursion, `--deep` via expansion, `approve`, parameters allow-list, `recipe` subcommands, e2e CLI tests against `tests/e2e/workflows` with a recipe workflow.

**Phase 7 — Docs, examples, hardening (M)**
User guide `docs/guide/recipes.md`; node pages `docs/nodes/recipe/{index,recipe,recipe-input,recipe-output}.md` (writing-style template) + `zensical.toml` nav; developer doc `docs/internal/dev/recipes.md` + updates to `architecture.md`, `adding-a-node.md`, `security-model.md`, `cli-internals.md`, `audit-trail-internals.md`, `error-system.md`; CHANGELOG + release notes; 3–4 shipped example recipes (`examples/`, `savedfiles/`) incl. a parameterised cleanse and a reconcile; performance pass; security test pass.

**Post-v1 (not planned in detail):** File Input inside recipes via path parameters; read-only "inspect instance" view with per-step results; list-valued parameters; recipe bundles/signing; batch and iterative recipes.

## 8. Test plan

- **Unit** (`tests/unit/recipes/`): format round-trip + unknown-key preservation; hashing stability; validation (every forbidden/limit case); library scan/cache; diff/compat matrix; error-code registry; `test_op_catalog_matches_registry`; `test_packaging_spec`; `test_codegen_no_unsafe_quotes` (add new generator names); code-policy alias test; audit schema `FIELD_ADDED_IN` test; params allow-list.
- **UI** (`tests/ui/`): instance load with/without source; reconcile on interface change incl. undo; drag-drop payload; Shift+A rebuild; Config Dock form from parameters (+ `ready()` rebuild rule); create-from-selection boundary cases (fan-out, multiple outputs, no outputs, disallowed nodes, groups, comments); explode; tab/title/dispatch for `.tdr`; recents/session restore.
- **E2E** (`tests/e2e/`): golden equivalence inline-vs-recipe (`assert_frame_golden`); two instances of the same recipe with different parameters in one workflow; nested recipe; failure inside recipe → error on instance + downstream skipped; CLI `run`, `validate --deep`, `approve`, `recipe update`, `verify-log`; recipe edit after approval invalidates approval; older-build load (Unknown placeholder) simulated by removing ops from the registry.
- **Security:** hostile `.tdr`/embedded recipe (non-SELECT SQL in an inner node, 10k nodes, cyclic nesting, forbidden nodes, absurd parameter values) → structured refusal; assert no path outside declared I/O is touched; assert no new network imports.
- **Performance:** 20-node recipe × 20 instances load/evaluate time budget; undo snapshot size with embedded definitions (dedup by sha).
- Always: `uv run --project . ruff format <files>`, `ruff check <files>`, focused `pytest` (baseline ruff has 562 pre-existing errors — only touched files must be clean).

## 9. Risks and open decisions

| # | Risk / decision | Position |
|---|---|---|
| 1 | **Embed vs reference.** Embedding is a deliberate departure from Alteryx. | Recommended (D1). Revisit only if file size or update friction proves a problem. |
| 2 | **Hidden scene cost** (Qt graphics per inner node, per instance). | Spike S1; lazy build + cache; fallback to Qt-free chain. |
| 3 | **Node id collisions** (ids are `id()` addresses, restored from file on load; same recipe twice reuses file ids). | Re-id inner nodes per instance; keep original id as `recipe_inner_id`; test S5. |
| 4 | **Canvas library limits** (sockets can't shrink, group API is edges-only, destructive load, heavy scenes). | You own `nodeeditor-qtpy`, so fix upstream (§4b, Phase U, release 0.9.0). Risk becomes lockstep versioning: all changes additive and off by default; app pin bumped once. |
| 5 | **No file watcher exists.** | Scan on focus/menu-open + refresh button; optional watcher later. |
| 6 | **Undo snapshots with embedded recipes** inflate memory (200-step stack). | Dedup by sha in `workflow_metadata.recipes`; share dict references; measure in perf pass. |
| 7 | **Schema bump** to workflow v3. | Older builds warn and show Unknown nodes; documented in CHANGELOG. |
| 8 | **Parameter binding scope** limited to scalar FORM settings. | Covers the common cases; list-valued later. |
| 9 | **Inner failure UX**: errors surface on the instance, not on a visible inner node. | v1: instance error names the inner step + original message; post-v1 inspect view. |
| 10 | **Run records for recipe tests** not recorded. | Decided (D4); revisit if analysts want test runs logged. |
| 11 | Stale/inconsistent repo docs (`adding-a-node.md` names wrong CHANGELOG/NODE_REFERENCE paths). | Fix paths as part of Phase 7. |

## 10. Definition of done (v1)

All phases 0–7 complete; the five "seamless" scenarios in §1 demonstrated end to end in the running app and via the CLI; golden equivalence test green; no new network access; docs and CHANGELOG updated; `ruff` clean on touched files and focused plus full `pytest` green.
