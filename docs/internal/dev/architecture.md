# Architecture

Verified against the code on branch `feature` (see the commit in the README
for the exact tree). File references are `path` plus the symbol to search for;
line numbers drift and are avoided.

## 1. The two layers

```
src/trigger_designer/
  core/   Qt-free. Pure logic, generated-code targets, record keeping.
  qt/     Everything that imports qtpy / nodeeditor: canvas, nodes, docks.
```

The rule: **a feature's logic lives in `core/` and the Qt file is a thin
wrapper**. That is what lets unit tests run without a window, lets generated
code import the logic, and lets a command-line runner share it.

| Guard | Where |
|---|---|
| `core/audit` imports no Qt and no executor | `tests/unit/test_audit_lazy_init.py::test_every_core_module_is_qt_free_and_executor_free` |
| `core/shaping/<node>.py` imports no Qt | one `test_core_has_no_qt_import` per node, e.g. `tests/unit/test_text_to_columns_core.py` |
| The read-only CLI commands import no Qt / Polars / DuckDB | `tests/unit/test_cli_import_discipline.py` |
| The frozen build lists every core module | `tests/unit/test_packaging_spec.py` (`trigger.spec`, section `core hidden imports`) |

Known exception: `core/ExecutionCheck/executor.py` imports
`trigger_designer.qt.helpers.global_logger` (it logs missing files and
variables to the Logging dock). `core/ExecutionCheck/run_loop.py` is Qt-free on
purpose and is what a headless runner uses.

`core/` and `qt/widgets/nodes/<Family>/` are PEP 420 namespace packages (no
`__init__.py` in most folders), so a new module is found by path, not by
registering a package.

## 2. Module map

### `core/`

| Module | Role |
|---|---|
| `node_configuration.py` | `NodeTypes`, the six op-code enums, `NODE_REGISTRIES`, `register_node`, lazy references, `get_class_from_op`, frozen `V1_OPCODE_TO_OP`. Its last line imports every node module. |
| `shaping/` | One Qt-free module per shaping node (`apply_*`, `run_node`, `describe`, `DEFAULTS`), plus `common.py` (`ERROR_CODES`, `ShapingError`, `live_sample`, `as_lazy`, `schema_of`, `connect_duckdb`). |
| `sql_guard.py` | Read-only DuckDB sandbox used by Formula, Filter, Multi-Field Formula and SQL Query. See `security-model.md`. |
| `codegen_safe.py` | `lit`, `lit_dq`, `lit_list`, `safe_comment`, `ident_part`: the only way user text enters generated code. |
| `audit/` | Audit tests (`duplicates`, `gaps`, `benford`, `sampling`, `risk_filters`, `common`, `test_summary`) and the run-record machinery (`schema`, `canonical`, `store`, `recorder`, `fingerprint`, `counting`, `compare`, `view`, `export`, `errors_adapter`). See `audit-trail-internals.md`. |
| `errors/` | `NodeError`, catalogue, translator, enrichment. See `error-system.md`. |
| `ExecutionCheck/` | `executor.py` (`NodeExecutor`, `ExecutionResult`) and `run_loop.py` (`run_nodes`). See `run-pipeline.md`. |
| `inputs.py`, `input_source.py` | File Input discovery (`list_source_files`) and readers (`build_source`, `SourceSettings`). Live evaluation and generated code both call `build_source`. |
| `profile.py`, `profile_report.py` | Data Profile engine and its report. |
| `frames.py` | `frame_schema`, `frame_shape` (lazy-safe). |
| `charts.py`, `utils/` | Chart spec; dtype widening and the cleansing engine. |
| `excel/`, `headless/`, `warmup.py` | Streaming Excel writer, CLI foundations (op catalogue, workflow reader, approvals), Arrow warm-up. See `cli-internals.md` and `workpaper-internals.md`. |

### `qt/`

| Module | Role |
|---|---|
| `node_base.py` | `TriggerNode`: identity, sockets, persistence, `get_code`. Delegates evaluation to `NodeEvaluator` and errors to `NodeErrorState`. Re-exports every name that moved out, so `from trigger_designer.qt.node_base import ...` keeps working. |
| `node_runtime.py` | `NodeEvaluator` (cache and re-entrancy checks, progress, input collection, the one `fail` transition, the one `invalidate`) and `NodeErrorState` (per-source error map, tooltip and badge, Problems dock bridge, knock-on clear). |
| `node_content.py` | `ConfigContent` (canonical content base), `DockBinding` (Config Dock undo registration), `TriggerChangeHandler` (thin mixin over `DockBinding`), `TriggerContent` (legacy adapter over `ConfigContent`). |
| `node_graphics.py` | `TriggerGraphicsNode`: geometry, painting, state-ring pens, badges, low-detail fallback. |
| `design_window.py` | `TriggerSubWindow`: one per open workflow. Load/save, `doEvalOutputs`, `getPyFile`, node drop, logging helpers. |
| `performance_scene.py` | `TriggerScene`: scene serialize (adds `workflow_metadata`), atomic UTF-8 save, `workflow_uuid`, bulk-load flag. |
| `main_window.py` | `TriggerWindow` (MDI), docks, recents, session restore. |
| `helpers/workflow_execution_mixin.py`, `workflow_worker.py` | The Run button. See `run-pipeline.md`. |
| `helpers/evaluation.py` | `EvaluationCoordinator`: coalesced, topologically ordered live evaluation. |
| `helpers/deferred_evaluation.py` | `DeferredEvaluation`: a Config Dock edit marks the node "pending" and it runs when the user leaves it. |
| `helpers/shaping_support.py` | `ShapingContent`, `ShapingNode`, `Field`, `FormSection`. See `adding-a-node.md`. |
| `helpers/config_content.py` | Alias of `node_content.ConfigContent` (old import path). |
| `helpers/audit_bridge.py`, `audit_tasks.py` | `RunSession` (the recorder as the Run button sees it), background tasks for the Run History dock. |
| `helpers/problems_store.py`, `error_context.py`, `error_enricher.py` | Problems dock state, translator context, background enrichment. |
| `helpers/content_undo_mixin.py`, `undo/` | `QUndoStack`-based undo (AGENTS.md has the rules; see `conventions.md`). |
| `helpers/state_mixin.py` | `SerializableContentMixin`: schema-driven `serialize`/`deserialize`. |
| `docks/` | `node_config.py` (Config Dock), `data_preview.py`, `logging_dock.py`, `problems_dock.py`, `run_history_dock.py`, `nodes_list.py`. |
| `widgets/common/config_widgets.py`, `column_picker.py` | Shared dock widgets. |
| `widgets/nodes/<Family>/` | The nodes. Families: `InOut`, `Preparation`, `Join`, `Transform`, `Report`, `Audit`. `nodes/__init__.py` holds the lazy specs. |
| `resources.json`, `resource_manager.py` | Icon ids to files. |
| `preferences.py`, `theme_manager.py`, `layout_state.py` | INI preferences (`app_data_dir()`), themes, window layout. |

## 3. Nodes at a glance

A node is a pair of classes in one module: a logic node (sockets, eval) and a
content widget (state, Config Dock, `get_code`). Identity is the op id
`"<family>.<ENUM MEMBER NAME lowercased>"` (e.g. `preparation.record_id`),
persisted in `.tds` as `"op"`. **Enum member names are API; never rename or
delete one; append new members at the end.** `V1_OPCODE_TO_OP` is frozen.

Two frameworks sit on top of `TriggerNode`:

* **Shaping nodes** (`ShapingNode`/`ShapingContent`): declarative `FORM`,
  settings dict, generated code is a call into `core/shaping/<x>.run_node`.
  Used by every Preparation, Join, Transform and Report node (Select, Join,
  Formula and Filter included, some with custom docks).
* **Audit nodes** (`AuditNode`/`AuditContent`): a `ParamsBase` dataclass plus a
  pure `run_<test>(frame, params) -> AuditResult`.

Only File Input, File Output and Union are still hand-written `TriggerNode` +
content classes. Step by step recipe: `adding-a-node.md`.

## 4. Data flow: live evaluation versus Run

The same node produces data in two different ways. This is the most important
thing to understand before changing a node.

```
          edit in Config Dock / drop an edge / load a file
                          |
                          v
  LIVE (GUI thread)   TriggerNode.eval -> processInputs -> node.value
                      -> LazyFrame plan, shown in Data Preview
                          |
        click Run         v
  RUN                 re-evaluate every node (doEvalOutputs)
                      -> topological order -> WorkflowWorker thread
                      -> NodeExecutor.execute_node(node):
                           code = node.get_code()
                           exec(code, shared globals, locals)
                           verify lazy plans (collect_schema)
                      -> variables kept per node (execution_results)
```

### Live

* `TriggerNode.eval` returns the cached `self.value` unless the node is dirty
  or invalid (`NodeEvaluator.evaluate`). The base `evalImplementation` evaluates
  the inputs and calls the node's `processInputs(input_values)`; a subclass may
  override `evalImplementation` and still gets the same cache, guard and error
  handling.
* `input_values[i]` is the list of output dicts of the node wired to input `i`
  (`[{"data": frame, "variable_name": "var_..."}, ...]`). Pick your entry with
  `getInputWithSocket(i)` (returns node and socket) and index with
  `socket.index`; the older `getSocketValue` returns the first connected output
  and is wrong when two outputs of one node feed two inputs of another.
* Return one dict per output socket, or `None` after setting an error. The base
  then marks the node invalid and its descendants dirty.
* `EvaluationCoordinator` (`scene.evaluator`) coalesces requests, expands them
  to the affected closure and walks it once in dependency order. It is
  *suspended* while a Run is going (both paths use Polars/DuckDB and must not
  overlap) and flushed afterwards.
* **Deferred evaluation** (`DeferredEvaluation`, used by `ShapingContent`,
  File Input, Union, Formula, Filter and Rows; `AuditContent.set_setting`
  evaluates at once instead): a
  setting change updates the model and undo stack at once, shows the yellow
  "changes pending" mark, and the node runs when the user selects another
  node or clicks the canvas. `Run` and `Save` keep it pending (Run
  re-evaluates anyway). Tests call `tests/support/flush.py::flush(node)` before
  reading a node's output.
* Shaping nodes work on the **first 100 rows** of each input while editing
  (`core/shaping/common.py::LIVE_SAMPLE_ROWS`, `live_sample`). Run reads the
  whole input. Chips such as "First 100 rows only: full count at Run" tell the
  user. Audit nodes compute on the full lazy plan live, except where a node
  sets `extras["live_skipped"]`.
* During file load `_bulk_loading` makes `eval()` a no-op and
  `doEvalOutputs` evaluates once in order.

### Run

See `run-pipeline.md` for the full sequence. Key facts:

* Nothing is collected by the executor. Generated code builds `LazyFrame`
  plans; only sinks (File Output), Graph, Count and the audit one-row summaries
  materialise data. Since the executor *verifies plans*
  (`NodeExecutor.verify_plans`, default `True`), a broken plan (missing column,
  bad join key) fails at the node that built it instead of at some later sink.
* Run executes `get_code()` text with `exec`, on one pooled worker thread, with
  one shared globals dict across nodes, so output variable names must be
  globally unique (`var_<kind>_<node id>`).
* Before the worker starts, the whole graph is recomputed live
  (`_reevaluate_for_run`). A node that was never evaluated no longer runs its
  empty-frame fallback.

## 5. LazyFrame conventions

* Frames flowing between nodes are `pl.LazyFrame`. `ShapingContent.compute`
  converts eager outputs with `.lazy()`; `AuditNode.processInputs` wraps input
  with `as_lazy`. File Input scans CSV lazily and reads **every CSV column as
  String on purpose** (typed formats keep native dtypes). Blank CSV header
  cells are named `column_<position>`.
* Never call `.columns`, `.dtypes`, `.schema` or `.shape` on a live frame.
  Use `trigger_designer.core.frames.frame_schema(frame)` (or
  `shaping.common.schema_of`) which uses `collect_schema()` for lazy frames,
  and `frame_shape` for log text.
* DuckDB sees Polars frames through Arrow (`pyarrow` is a hard dependency).
  Shaping connections use **one DuckDB thread** (`DUCKDB_THREADS = 1`): DuckDB
  workers entering `LazyFrame.collect` off the Qt thread crashed Formula and
  Filter live evaluation.
* Do not collect in `processInputs` unless the node's contract needs it (the
  audit one-row Summary is collected only inside `AuditResult.for_run()` at
  Run).
* `after_execution(variables)` (executor thread) and `on_run_result(variables)`
  (GUI thread) are optional hooks on a node *content*; only a node that needs
  the run result (Graph, audit Summary) uses them.

## 6. Generated code contract

`node.get_code() -> str` is called **once per Run** by `NodeExecutor`, and its
text is kept (`result.code`) and reused for the exported script; it must be
pure and idempotent. Rules every node follows:

1. **Always define every output variable**, on every path. Unwired or
   unconfigured: `var = pl.DataFrame().lazy()` (shaping) or `pl.DataFrame()`
   (audit). Downstream code must never `NameError`.
2. Variable names are `var_<kind>_<content.id>`. `content.id` is stable across
   save/load (`restore_id`) but changes if the node is recreated. Anything
   derived from an id goes through `ident_part`.
3. Shaping nodes emit a **call into core**, not inline logic:
   ```python
   import json
   import polars as pl
   from trigger_designer.core.shaping.record_id import run_node as _run_node
   var_recordid_12, = _run_node([var_in_3], json.loads('{"name": "RecordID", ...}'))
   ```
   so live evaluation and Run run the same function. Settings are a JSON
   payload (`sort_keys=True`); keys in `PRESENTATION_SETTINGS` are left out.
4. Audit nodes emit
   `from <module> import <Params>, run_<test>` then
   `outs = run_<test>(var_in, Params.from_dict({...})).for_run()`.
   A configured-wrong node *raises* (`AuditConfigError`) rather than emitting
   an empty frame: an audit test that silently produced nothing would read as
   "no exceptions".
5. **User text never enters code by f-string interpolation.** Use
   `codegen_safe.lit`/`lit_dq`/`safe_comment`/`ident_part` or the JSON payload.
   `tests/unit/test_codegen_no_unsafe_quotes.py` AST-scans every function
   named in its `CODEGEN_FUNCTIONS` set (`get_code`, `audit_code`, ...) and
   fails on `'{x}'`/`"{x}"` patterns.
6. Generated code is **not standalone**: it imports `trigger_designer.core.*`.
   The exported script (`getPyFile`) prepends a header that puts this tree's
   `src` on `sys.path` (`check_output_header`).
7. The executor seeds `pl`, `os`, `datetime`, `timedelta` into the shared
   globals; still `import polars as pl` at the top of every snippet so the
   exported script runs.
8. Quirk: because exec uses separate globals and locals, a `lambda` or nested
   `def` in a snippet cannot see names assigned earlier in the same snippet.
   Names from *earlier nodes* (globals) are fine. Comprehensions are fine.

## 7. Persistence (`.tds`)

* One orjson file: `TriggerScene.serialize()` = `id, scene_width, scene_height,
  nodes, edges, groups, workflow_metadata`. Saved atomically as UTF-8
  (`saveToFile` writes a temp file then replaces); loaded tolerant of BOM,
  legacy encodings and unknown keys.
* `workflow_metadata`: `schema_version` (`WORKFLOW_SCHEMA_VERSION = 2`),
  `app_version`, `saved_at`, `workflow_uuid` plus any unknown keys carried over
  from the loaded file (so a future `parameters` block survives a re-save).
  `workflow_uuid` is stable across saves, new for *File > New*. No migration
  code branches on the schema version; compatibility is by tolerant defaults.
* Node dict: `id, title, pos_x, pos_y, inputs, outputs, content{...},
  label_*, node_code, node_type, op`. Loading resolves `op` with
  `get_class_from_op`; failure gives `TriggerNode_Unknown` (keeps the raw
  content, shows a warning). A file with no `op` goes through
  `migrate_v1_data`.
* Content state, two styles: `SerializableContentMixin.serialized_state_schema`
  (`{key: {"default": ...}}`; missing keys take the default; the preferred
  style, used by shaping and audit nodes through `get_serialized_state_schema`),
  or hand-written `serialize`/`deserialize` with `data.get(key, default)`.
  `validate_loaded_state() -> list[str]` can report stale settings after load.
* **Never rename a persisted key; only add keys with defaults.** Audit
  parameter dataclass field names are persisted keys.
* Paths: File Input/Output store absolute `filePath`; the run record
  normalises to forward slashes.

## 8. Error surface (summary)

Exceptions are translated to `NodeError` (`core/errors`) and stored on the node
per source (`"live"` / `"run"`), then shown as a canvas badge/tooltip, a row in
the Problems dock and a line in the Logging dock. Details:
`error-system.md`.

## 9. Corrections to `docs/plan/00-codebase-brief.md` (dated 2026-10-21)

The brief described `main` at `71b4041`. These statements no longer hold on
`feature`:

| Brief | Now |
|---|---|
| Binding is PyQt6, `qtpy-nodeeditor` from a git fork outside the lock; "do not run bare `uv sync`" | PySide6-Essentials 6.12.0 via `qtpy`, `nodeeditor-qtpy==0.8.2` from PyPI and in `uv.lock`. `qt_api = "pyside6"` in pytest config. |
| Python 3.13.12, Polars 1.44.2, DuckDB 1.5.5 | Python `>=3.14,<3.15` (venv 3.14.8), Polars 2.0.0, DuckDB 2.0.0, pyarrow 26.0.0. Python 3.14 syntax appears: `except A, B:` without parentheses (PEP 758). |
| `xlsxwriter` missing | Declared (`xlsxwriter==3.3.0`) and installed; wrapped by `core/excel`. |
| Fact 3: Run does not re-evaluate; unevaluated nodes emit fallback code | `executeWorkflow` calls `_reevaluate_for_run` first. |
| Fact 4: cancellation not wired | `request_run_cancel`, Cancel button, `run_loop` cancel between nodes (cooperative; the running node finishes). |
| Fact 6: `getPyFile` writes `check_output.py` into the CWD | Writes `<app data>/last_run/check_output.py` using the code that actually ran. The tracked `check_output.py` at the repo root is a stale artefact (see `conventions.md`). |
| Fact 10: exec has no sandbox | Still no sandbox for generated code, but all SQL is guarded (`sql_guard`), user text is quoted (`codegen_safe`), and `NodeExecutor.code_filter` / `policy_violation` exist as a refusal seam used by the headless runner. |
| `__main__.py`: `python -m trigger_designer` | No `__main__.py` in `trigger_designer`. GUI: `trigger-designer` console script or `python src\trigger_designer\main.py`. CLI: `trigger-designer-cli` (`cli/__main__.py`; see `cli-internals.md`). |
| Five families | Six: `NodeTypes.AUDIT` / `AuditNodes` added. |
| "registerInputWidget records a whole-scene snapshot" | Still true for `registerInputWidget`; but shaping/audit nodes use `set_setting` -> `push_property_change`/`push_list_change`. No node subclass now relies on `history_stamp_callback`. |
| `tests/integration` holds tests (CONTRIBUTING) | Empty directory (only `__pycache__`). |
| Dock icon buttons `30x30 / 12px` | `IconButton` default glyph is 16 px (caption buttons 12 px); AGENTS.md says 16 px. Icons are Material Symbols (`qt-material-icons`), not the old `ui/` SVGs. |
| `ruff check` baseline not clean (76 errors in `core`) | At `e2b610a`, `ruff check src tests scripts` reports 562 errors (436 auto-fixable) and `ruff format --check` would reformat 20 files. Run ruff only on the files you touch and compare before/after. |
