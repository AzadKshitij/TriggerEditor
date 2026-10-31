# 02 - Audit trail (run log)

Status: implementation plan. Depends on `00-codebase-brief.md` (cited as "brief"), `03-*` (`NodeError`)
and `01-*` (`ResolvedFile`). Written against `main` @ `71b4041`. Every `file:line` below was opened
and checked on 2026-10-21; line numbers drift, so grep the quoted symbol if a line is off by a few.

Every decision is final. Each carries a one-line reason ("Why"). There are no open questions.

Contents: 1 Goal | 2 Current state | 3 Final design | 4 Implementation steps | 5 Edge cases |
6 Test plan | 7 Acceptance checklist | 8 Verification commands | 9 Pitfalls | 10 Interfaces

---

## 1. Goal and non-goals

### 1.1 Goal

Every **Run Workflow** writes one **immutable, tamper-evident run record**: a JSON file that says
who ran what, on which exact inputs, with which settings, how many rows went through every node,
which outputs were written (with SHA-256), how long it took, and why it failed if it failed. The
records of one workflow form a **hash chain**. A user can list runs, verify the chain, export a
run (HTML or JSON), compare two runs, and check that the inputs on disk still match a recorded run.

The recorder is **Qt-free** (`core/audit/`). The GUI and the future CLI (plan 08) both call it.

### 1.2 Non-goals (decided)

| Not doing | Why |
|---|---|
| Cryptographic signatures / external anchoring | Needs key management. The chain makes edits and mid-chain deletions detectable. Tail truncation is not detectable (see 5); the Verify report prints the head hash so a user can note it externally. |
| Storing input or output data, or row samples | Audit logs must not copy client data. Only fingerprints and counts are stored. |
| Deleting or pruning runs | Immutable by design. A user may delete the whole `.runs` folder; that is a user action outside the app. |
| A Cancel button | Cancellation is unwired today (brief fact 4). The single cancellation API `request_run_cancel()` is **provided by plan 09 F-D**; this plan only attaches the recorder to it (3.7). A button is a separate change. |
| Re-running a historic run | "Re-run with same inputs" means a **check** (section 3.9), not replaying code. |
| Recording live (non-Run) evaluation | Live evaluation is not a run (brief H9: AVOID for audit). |
| Per-row lineage | Out of scope; counts only. |
| Touching `getPyFile` / `check_output.py` | Brief fact 6; plan 08 owns making that path an argument. The recorder builds its own script text from node `get_code()` results. |

---

## 2. Current state (verified)

All paths relative to the repo root. Line numbers verified against the working tree.

### 2.1 Run orchestration

| Fact | Where |
|---|---|
| `executeWorkflow` is the single start of a Run: guard, disables button, `getNodeConnections()`, `topologicalSort`, **new** `NodeExecutor()`, clears `execution_results`, builds `WorkflowWorker`, wires 4 signals, `worker.start()` | `src/trigger_designer/qt/helpers/workflow_execution_mixin.py:47-94` |
| `_on_node_finished(node, result)`: success stores pruned results; failure only logs and colours the node | `workflow_execution_mixin.py:96-112` |
| `_on_node_errored(node, exc)`: rare path | `workflow_execution_mixin.py:114-123` |
| `_on_workflow_finished(success)`: drops worker, calls `getPyFile`, schedules cleanup, then emits `executionResultsChanged` | `workflow_execution_mixin.py:125-141` |
| `_declared_output_variable_names(node)`: the ordered output variable names of a node (from `node.param`, `node.value`, content attrs) | `workflow_execution_mixin.py:220-258` |
| `WorkflowWorker.run`: loops nodes, emits `nodeStarted`, calls `executor.execute_node`, emits `nodeFinished`, stops at first failure; `request_cancel()` is never called | `src/trigger_designer/qt/helpers/workflow_worker.py:25-68` |
| `TriggerSubWindow.run_workflow` -> `executeWorkflow`; `getPyFile` writes `check_output.py` into the CWD; `getNodeConnections` returns `{node: {"inputs": [...], "outputs": [...]}}` (node lists only, **no socket indexes**) | `src/trigger_designer/qt/design_window.py:690-735` |
| `executionResultsChanged = Signal()` on the window | `design_window.py:83` |
| The document path is `window.filename` (None when unsaved). `NodeEditorWidget.isModified()` is a stub (`filename is not None`) - do **not** use it. `scene.has_been_modified` exists (set by undo/history) | `main_window.py:575` (`widget().filename`); `qt/node_base.py:623`; `qt/undo/history.py:102` |

### 2.2 Executor

| Fact | Where |
|---|---|
| `ExecutionResult` dataclass: `success, output, error(str), variables, execution_time, memory_used, peak_memory, lines_executed, warnings, timestamp`. No node id, no exception, no code, no start time | `src/trigger_designer/core/ExecutionCheck/executor.py:21-47` |
| `execute_node`: `code = node.get_code()` (line ~310), `_execute_with_timeout`, memory check, then `result.variables = local_variables.copy()`, `after_execution` hook (359-370), **`self.execution_context.update(local_variables)` at line 373**, `except` flattens to `str(e)` (378-388) | `executor.py:289-417` |
| Timeout wraps only `exec` (30 s default); the memory check runs after exec | `executor.py:243-269, 328-338` |
| `cancel_execution()` sets `_cancel_event`; nothing reads it | `executor.py:457-464` |
| Executor imports `trigger_designer.qt.helpers.global_logger` (so it is not Qt-free). The recorder must not import it. | `executor.py:11` |

### 2.3 Nodes (what the recorder reads)

| Fact | Where |
|---|---|
| File Input content state is schema-driven: `serialized_state_schema` keys `filePath, file_type, record_limit, output_filename_as_field, delimiter, first_row_contains_field_names, selected_sheet, available_sheets, start_row, schema_snapshot, file_metadata`. `get_serialized_state()` is pure; `serialize()` **re-reads the file** (brief 7.1) so the recorder must use `get_serialized_state()` when present | `qt/widgets/nodes/InOut/file_input.py:46-58`; `qt/helpers/state_mixin.py:39-46` |
| File Output: attrs `filePath`, `file_format` (`csv, excel, parquet, json, ndjson, ipc, custom_delimited`), `delimiter`; code uses `sink_csv/sink_parquet/sink_ndjson/sink_ipc`, `collect().write_excel/write_json`; unwired -> generated code raises `ValueError` | `qt/widgets/nodes/InOut/file_output.py:36-37, 231-349` |
| Split is the only node with a seed today: attrs `random_seed` (default 42), `is_random`; codegen `shuffle(seed=...)` | `qt/widgets/nodes/Preparation/split.py:75-76, 183-190, 224-225` |
| `TriggerNode.id` comes from the vendored `Node(Serializable)`; it is stable across save/load (`restore_id`) | `nodeeditor/node_node.py` (vendored), brief 3.5 |
| `TriggerScene.serialize` adds `workflow_metadata{schema_version, app_version, saved_at}`; `loaded_workflow_metadata` is set on load | `qt/performance_scene.py:166-180` |
| `core/constants.py`: `VERSION = "0.1.0"`, `WORKFLOW_SCHEMA_VERSION = 2` | `core/constants.py:7-8` |

### 2.4 Preferences, docks, tests

| Fact | Where |
|---|---|
| `DEFAULTS` dict + `get_preferences().get("area/key")`; `_coerce` types by the default (bool/int/list/str passes through); `app_data_dir()` honours `TRIGGER_DESIGNER_DATA_DIR` | `qt/preferences.py:42-56, 94-110, 74-84` |
| Dock pattern: `LoggingDock(QDockWidget)` with `switch_to_design_window`, `remove_design_window`; theme-token colours via `LogLevel.token` and `get_theme_manager()` | `qt/docks/logging_dock.py:19-36` |
| Dock creation/tabify/menu/layout hooks | `qt/helpers/main_window_ui_mixin.py:103-125, 257-293`; `qt/main_window.py:142-148, 487-538`; `qt/layout_state.py:225-250` |
| Existing UI glyph ids: `icon_add, icon_remove, icon_folder_open, icon_save, icon_external, icon_apply, icon_options, icon_refresh, icon_pin, icon_unpin, icon_search, icon_run_play, icon_zoom_*, icon_chevron_*` | `qt/resources.json:102-175` |
| Test harness: `run_workflow_and_wait(qtbot, window)`; `no_modal_dialogs` stubs `getPyFile` (so no `check_output.py` in tests) and returns `{"warnings", "run_code"}` | `tests/support/workflows.py:78-99`; `tests/conftest.py:205-240` |
| `.gitattributes` is `* text=auto`: a CSV fixture whose bytes are hashed must be marked `-text` | `.gitattributes` |

### 2.5 The consequences that shape the design

1. **Lazy plans.** `executeWorkflow` never collects (brief fact 2). A node's "row count" does not exist until someone executes its plan. Section 3.5 decides exactly when.
2. **Run uses live state.** `get_code()` reads state set by the last live eval (brief fact 3). The recorder snapshots node settings at `begin` (GUI thread, right before the run) - the same state the code was generated from.
3. **Failure details are strings** (brief fact 5). Plan 09 F-B adds `exception`, `traceback_text`, `exception_type`, `code`, `started_at`, `finished_at` and `policy_violation` to `ExecutionResult`; this plan only consumes them and translates with `NodeError`.
4. **Cancellation is unwired** (brief fact 4). The recorder owns a `threading.Event`; `request_run_cancel()` (provided by plan 09 F-D) also sets it through `RunSession.request_cancel()`, and the GUI's `cancelled` status comes from the session flag, not from the worker.
5. **`check_output.py` in CWD** (brief fact 6): untouched. In tests it is stubbed, so run-record tests do not depend on it.

---

## 3. Final design

### 3.1 Module layout

New Qt-free package `src/trigger_designer/core/audit/` (imports stdlib, `polars`, `orjson`, `loguru`; never `qtpy`, never `trigger_designer.qt.*`, never `executor`):

| File | Contents |
|---|---|
| `__init__.py` | **owned by this plan.** Lazy re-exports via module `__getattr__` (3.8, "Lazy package init"). Plan 04 does not create it. |
| `schema.py` | constants, dataclasses, `to_dict/from_dict`, `validate_record_dict` |
| `canonical.py` | `canonical_json`, `sha256_hex`, `compute_record_hash`, `GENESIS_HASH` |
| `fingerprint.py` | `FingerprintCache`, `fingerprint_file`, `sha256_stream`, `count_rows_in_file` |
| `counting.py` | `decide_row_count_mode`, `count_frame`, `schema_of` |
| `store.py` | `RunStore`, `resolve_store_dir`, file lock, index, `verify_store`, `verify_record_file` |
| `recorder.py` | `AuditOptions`, `NodeSpec`, `EdgeRef`, `RunRecorder` |
| `compare.py` | `compare_runs`, `check_inputs`, dataclasses `RunDiff`, `DiffItem`, `InputCheck` |
| `view.py` | Qt-free view helpers for the dock: `run_summary_rows`, `node_table_rows`, `format_duration` |
| `export.py` | `render_html`, `export_json` |
| `errors_adapter.py` | `error_to_dict(result, node)` (calls plan 03's `translate_exception`) |

Qt side (thin; all logic stays in core):

| File | Contents |
|---|---|
| `qt/helpers/audit_bridge.py` | `RunSession` (glue used by the mixin), `node_spec_from_node`, `options_from_preferences` |
| `qt/helpers/audit_tasks.py` | `AuditTask(QRunnable)` + signals for verify / check-inputs / export in the background |
| `qt/docks/run_history_dock.py` | `RunHistoryDock` |
| `qt/models/run_history_models.py` | `RunListModel`, `NodeTableModel`, `DiffTableModel` (`QAbstractTableModel`s over `view.py` rows) |

Why this split: plan 08 (CLI) must import `core.audit` without Qt; the bridge is the only module that
knows `TriggerNode`.

### 3.2 Example run record (illustrative values; hashes shortened to 8 chars here - real ones are 64 hex)

File on disk: pretty-printed, sorted keys. The hash is computed over the canonical form (3.4), so
pretty-printing is irrelevant to verification.

```json
{
  "schema_version": 1,
  "run_id": "6f1c0a52b3e84f6f9c1d2e7a8b4c5d60",
  "seq": 3,
  "status": "ok",
  "started_at": "2026-10-21T09:14:03.120456Z",
  "finished_at": "2026-10-21T09:14:04.002118Z",
  "duration_s": 0.881662,
  "app_name": "TriggerDesigner",
  "app_version": "0.1.0",
  "workflow_schema_version": 2,
  "python_version": "3.13.12",
  "polars_version": "1.44.2",
  "duckdb_version": "1.5.5",
  "os_name": "Windows-11-10.0.26100-SP0",
  "user": "KASHVIN",
  "machine": "LAPTOP-7F2A",
  "workflow_path": "C:/Work/Q3/orders.tds",
  "workflow_sha256": "9d2b11aa...",
  "workflow_uuid": "0b6c1e0e5b0f4d3a8f8f2a8e6f3d9c11",
  "graph_sha256": "c41e77d0...",
  "workflow_modified_since_save": false,
  "options": {
    "row_count_mode_requested": "auto",
    "row_count_mode_effective": "all",
    "exact_counts_max_mb": 256,
    "total_input_bytes": 25,
    "hash_inputs": true,
    "hash_outputs": true,
    "hash_max_mb": 2048,
    "record_identity": true,
    "embed_code": true
  },
  "inputs": [
    {
      "role": "input",
      "node_id": 11,
      "path": "C:/Work/Q3/orders.csv",
      "sheet": null,
      "size_bytes": 25,
      "modified_time": "2026-10-20T16:02:11.500000Z",
      "mtime_ns": 1792512131500000000,
      "sha256": "aac441b2f011b33ba88a30f384ec388988fff9d248e7620cc73007e74720d5c9",
      "sha256_status": "computed",
      "row_count": 3,
      "row_count_method": "materialized",
      "error": null
    }
  ],
  "outputs": [
    {
      "role": "output",
      "node_id": 13,
      "path": "C:/Work/Q3/out/orders_clean.csv",
      "sheet": null,
      "size_bytes": 25,
      "modified_time": "2026-10-21T09:14:03.900000Z",
      "mtime_ns": 1792573243900000000,
      "sha256": "aac441b2f011b33ba88a30f384ec388988fff9d248e7620cc73007e74720d5c9",
      "sha256_status": "computed",
      "row_count": 3,
      "row_count_method": "output_file",
      "error": null
    }
  ],
  "nodes": [
    {
      "seq": 0,
      "node_id": 11,
      "op": "input.file_input",
      "title": "File Input",
      "label": null,
      "status": "ok",
      "started_at": "2026-10-21T09:14:03.121000Z",
      "duration_s": 0.012,
      "count_seconds": 0.004,
      "settings": {"filePath": "C:/Work/Q3/orders.csv", "file_type": "csv", "delimiter": ","},
      "seed": null,
      "code_sha256": "5be0c1a4...",
      "rows_in": [],
      "rows_out": {"var_file_input_11": 3},
      "columns_out": {"var_file_input_11": ["id", "amount"]},
      "dtypes_out": {"var_file_input_11": ["String", "String"]},
      "count_method": {"var_file_input_11": "materialized"},
      "peak_memory_mb": 0.4,
      "warnings": [],
      "error": null,
      "test_summary": null
    },
    {
      "seq": 1,
      "node_id": 12,
      "op": "preparation.normalize_columns",
      "title": "Normalize",
      "label": null,
      "status": "ok",
      "started_at": "2026-10-21T09:14:03.140000Z",
      "duration_s": 0.003,
      "count_seconds": 0.002,
      "settings": {"case_mode": "keep"},
      "seed": null,
      "code_sha256": "77aa0d9e...",
      "rows_in": [{"socket": 0, "from_node_id": 11, "from_socket": 0, "variable": "var_file_input_11", "rows": 3}],
      "rows_out": {"var_normalize_12": 3},
      "columns_out": {"var_normalize_12": ["id", "amount"]},
      "dtypes_out": {"var_normalize_12": ["String", "String"]},
      "count_method": {"var_normalize_12": "materialized"},
      "peak_memory_mb": 0.1,
      "warnings": [],
      "error": null,
      "test_summary": null
    },
    {
      "seq": 2,
      "node_id": 13,
      "op": "input.file_output",
      "title": "File Output",
      "label": null,
      "status": "ok",
      "started_at": "2026-10-21T09:14:03.160000Z",
      "duration_s": 0.040,
      "count_seconds": 0.001,
      "settings": {"filePath": "C:/Work/Q3/out/orders_clean.csv", "file_format": "csv", "delimiter": ","},
      "seed": null,
      "code_sha256": "e19f4410...",
      "rows_in": [{"socket": 0, "from_node_id": 12, "from_socket": 0, "variable": "var_normalize_12", "rows": 3}],
      "rows_out": {},
      "columns_out": {},
      "dtypes_out": {},
      "count_method": {},
      "peak_memory_mb": 0.0,
      "warnings": [],
      "error": null,
      "test_summary": null
    }
  ],
  "baseline": {
    "run_id": "1a2b3c4d5e6f40718293a4b5c6d7e8f9",
    "input_changes": [
      {"path": "C:/Work/Q3/orders.csv", "change": "modified", "old_sha256": "0f0f0f0f...", "new_sha256": "aac441b2..."}
    ]
  },
  "warnings": [],
  "generated_code": "import polars as pl\nvar_file_input_11 = pl.scan_csv(...)\n...",
  "generated_code_sha256": "3c7d2e90...",
  "hash_algo": "sha256-canonical-json-v1",
  "prev_record_hash": "ab12cd34...",
  "record_hash": "d00dfeed..."
}
```

A failed node looks like this (only the differing fields; `NodeError` from plan 03, all its fields kept):

```json
{
  "status": "failed",
  "rows_out": {"var_filter_14": null},
  "count_method": {"var_filter_14": "none"},
  "error": {
    "code": "TD-SCH-001", "title": "Column 'amnt' was not found",
    "detail": "Filter could not find the column 'amnt'.", "hint": "Pick one of: id, amount.",
    "technical": "ColumnNotFoundError: amnt", "exc_type": "ColumnNotFoundError",
    "severity": "error", "node_id": 14, "node_title": "Filter", "op": "preparation.filter",
    "columns": ["amnt"], "path": null
  }
}
```

### 3.3 Field table (schema_version 1)

Types: `str`, `int`, `float`, `bool`, `null` = JSON null, `[T]` = array. "Required" = key must be
present (value may be null if the type says so). Timestamps are `YYYY-MM-DDTHH:MM:SS.ffffffZ` (UTC,
always 6 fractional digits, produced by `utc_now_iso()`).

**Run level**

| Field | Type | Req | Meaning / rule |
|---|---|---|---|
| `schema_version` | int | yes | `1`. Bumped only for a breaking change; a reader refuses a higher major than it knows. |
| `run_id` | str | yes | `uuid.uuid4().hex` (32 lowercase hex). File name = `<run_id>.json`. |
| `seq` | int | yes | 1-based position in the store's chain. Assigned at commit under the store lock. |
| `status` | str | yes | `ok` / `failed` / `cancelled`. |
| `started_at`, `finished_at` | str | yes | UTC wall clock (informational; see clock skew, 5). |
| `duration_s` | float | yes | `time.perf_counter()` difference, rounded to 6 decimals. Monotonic, immune to clock changes. |
| `app_name`, `app_version` | str | yes | `core.constants.APP_NAME`, `VERSION`. |
| `workflow_schema_version` | int | yes | `core.constants.WORKFLOW_SCHEMA_VERSION`. |
| `python_version`, `polars_version` | str | yes | `platform.python_version()`, `polars.__version__`. |
| `duckdb_version` | str / null | yes | `duckdb.__version__`; null if not importable. Imported lazily inside try. |
| `os_name` | str | yes | `platform.platform()`. |
| `user`, `machine` | str / null | yes | `getpass.getuser()`, `socket.gethostname()`; **null** when `audit/record_identity` is off. Each wrapped in try (null on error). |
| `workflow_path` | str / null | yes | Absolute path, forward slashes; null when unsaved. |
| `workflow_sha256` | str / null | yes | SHA-256 of the **bytes of the saved .tds on disk** at `begin`; null when unsaved or unreadable. |
| `workflow_uuid` | str / null | yes | From `workflow_metadata.workflow_uuid` (3.12); null if the scene has none. |
| `graph_sha256` | str | yes | SHA-256 of canonical JSON of `{"nodes":[{id,op,settings}...sorted by id],"edges":[[src,srcsock,dst,dstsock]...sorted]}`. Always present, also for unsaved workflows; independent of save time and node positions. |
| `workflow_modified_since_save` | bool / null | yes | `scene.has_been_modified` at `begin` (null if the attribute is absent). If true, `workflow_sha256` does **not** describe what ran; `graph_sha256` does. |
| `options` | object | yes | The effective options (see example). Lets a reader interpret null counts. |
| `inputs`, `outputs` | [FileFingerprint] | yes | Order: execution order, then path. Empty arrays allowed. |
| `nodes` | [NodeRunRecord] | yes | One entry per node in the run plan, in execution order; nodes that never ran have `status:"skipped"`. |
| `baseline` | object / null | yes | `{"run_id", "input_changes":[{path, change, old_sha256, new_sha256}]}` vs the previous run in the same store; null for the first run. `change` is `modified` / `added` / `removed`. |
| `warnings` | [str] | yes | Run-level notes (row-count mismatch, hash skipped, store fallback...). |
| `generated_code` | str / null | yes | Concatenated node `get_code()` texts in execution order (no `check_output.py` header). Null when `embed_code` is off or text > 1 MiB. |
| `generated_code_sha256` | str | yes | SHA-256 (UTF-8) of that concatenation, always present. |
| `hash_algo` | str | yes | `"sha256-canonical-json-v1"`. |
| `prev_record_hash` | str | yes | `record_hash` of the previous record in this store, or `GENESIS_HASH` (64 zeros) for seq 1. |
| `record_hash` | str | yes | 64 lowercase hex, see 3.4. |

**FileFingerprint** (`inputs[]`, `outputs[]`)

| Field | Type | Meaning / rule |
|---|---|---|
| `role` | str | `input` / `output`. |
| `node_id` | int / null | Owning node. |
| `path` | str | Absolute, forward slashes. |
| `sheet` | str / null | Excel sheet (input). |
| `size_bytes` | int / null | `os.stat().st_size`; null if missing. |
| `modified_time` | str / null | From `st_mtime_ns`. |
| `mtime_ns` | int / null | Exact `st_mtime_ns` (used as the cache key). |
| `sha256` | str / null | Streamed digest; null unless `sha256_status` is `computed` or `cached`. |
| `sha256_status` | str | `computed`, `cached`, `skipped_size_limit`, `disabled`, `missing`, `error`, `cancelled`. |
| `row_count` | int / null | Input: rows the node produced. Output: rows counted in the written file. |
| `row_count_method` | str | See 3.5 (`materialized`, `scan_plan`, `eager`, `output_file`, `none`). |
| `error` | str / null | Short text (`PermissionError: ...`, or `node failed; file may be partial`). |

**NodeRunRecord** (`nodes[]`)

| Field | Type | Meaning / rule |
|---|---|---|
| `seq` | int | 0-based execution order. |
| `node_id` | int | `TriggerNode.id`. |
| `op` | str | Stable op id (`input.file_input`); for an unresolvable node `"unknown"`. |
| `title` | str | `node.node_title`. |
| `label` | str / null | The user's canvas label (`node.label_text`) if non-empty. |
| `status` | str | `ok` / `failed` / `skipped`. |
| `started_at` | str / null | From `ExecutionResult.started_at`; null for skipped. |
| `duration_s` | float | `ExecutionResult.execution_time` rounded to 6; 0.0 for skipped. Excludes counting time. |
| `count_seconds` | float | Time spent counting/materialising/hashing for this node (3.5); 0.0 if none. |
| `settings` | object | JSON-safe snapshot (3.10). |
| `seed` | int / null | 3.10 rule. |
| `code_sha256` | str / null | SHA-256 of that node's generated code (null for skipped). |
| `rows_in` | [object] | One entry per **connected input socket**: `{socket, from_node_id, from_socket, variable, rows}`; `rows` is the upstream node's `rows_out[variable]` (null if not counted). Unconnected sockets are omitted. |
| `rows_out` | object | `{variable_name: int / null}` per declared output variable, socket order. `{}` for sinks. |
| `columns_out` | object | `{variable_name: [column names]}`; at most 500 names (then the list ends with `"..."`). |
| `dtypes_out` | object | `{variable_name: [dtype strings]}`, parallel to `columns_out` (same truncation). `str(dtype)`. |
| `count_method` | object | `{variable_name: method}`. |
| `peak_memory_mb` | float | `ExecutionResult.peak_memory`, rounded to 3 decimals. |
| `warnings` | [str] | `ExecutionResult.warnings` plus count/materialise errors; each capped at 500 chars, at most 20 entries. |
| `error` | object / null | `NodeError` as dict (plan 03 fields, all of them); `technical` capped at 8000 chars. |
| `test_summary` | object / null | `TestSummary` dict (plan 04); null until plan 04 lands. |

### 3.4 Canonical JSON and hashing rules (final)

`canonical_json(obj) -> bytes`:

1. `orjson.dumps(obj, option=orjson.OPT_SORT_KEYS)`. Result: UTF-8, keys sorted, no whitespace, shortest-round-trip floats, non-ASCII emitted as UTF-8 (not `\u` escapes).
2. Input must contain only `dict` with `str` keys, `list`, `str`, `int` (|n| < 2**63), `float`, `bool`, `None`. `canonical_json` raises `TypeError` otherwise (orjson does, with `OPT_STRICT_INTEGER` set). No tuples, sets, datetimes, Paths: the dataclass `to_dict()` converts them first.
3. No `NaN`/`Infinity`: `sanitize()` (3.10) maps non-finite floats to `null` before hashing.
4. Floats that are stored are pre-rounded by the producer (`duration_s` 6 decimals, `peak_memory_mb` 3), so a record read back and re-dumped is byte-identical.

`compute_record_hash(record_dict) -> str`: `sha256_hex(canonical_json({k: v for k, v in record_dict.items() if k != "record_hash"}))`. It covers `prev_record_hash`, so the chain is bound into each hash.

**Verification always works on the raw parsed dict from disk** (`orjson.loads`), never on a dataclass round trip. Why: unknown future keys must still be covered by the hash.

Test vector (use it in a unit test): `sha256_hex(canonical_json({"b": 2, "a": 1}))` == `43258cff783fe7036d8a43033f830adfc60ec037382473548ac742b888292777`; `canonical_json({"b": 1, "a": [1.5, None, "é"]}) == b'{"a":[1.5,null,"\xc3\xa9"],"b":1}'`.

### 3.5 Row counting: the exact mechanism (decision)

**Problem:** a Run builds lazy plans. Counting a node's output by `lf.select(pl.len()).collect()`
re-executes the whole upstream plan every time (O(k^2) for a chain of k nodes). Counting only at
the sink would miss intermediate counts. Collecting everything destroys streaming for big data.

**Decision: three effective modes, chosen once per run from the preference and the total input size.**

Preference `audit/row_counts` in `{"auto","all","sink","off"}` (default `"auto"`), and
`audit/exact_counts_max_mb` (int, default `256`).

`decide_row_count_mode(requested, total_input_bytes, threshold_mb) -> str`:

| requested | effective |
|---|---|
| `"off"` | `"off"` |
| `"all"` | `"all"` |
| `"sink"` | `"sink"` |
| `"auto"` | `"all"` if `total_input_bytes <= threshold_mb * 1024 * 1024` else `"sink"` |

`total_input_bytes` = sum of `st_size` of every declared input file (cheap `os.stat`, no hashing),
computed in `begin`. A missing file counts 0. Excel files count by file size (they are read eagerly anyway).

**Mode `all` = "collect once and reuse".** In `after_node` (3.7, worker thread, right after the node's
`exec` finished and before `execution_context.update`), for each declared output variable whose value
is a `pl.LazyFrame`:

```python
t0 = time.perf_counter()
df = value.collect()                  # in-memory engine; the plan runs exactly once
local_variables[name] = df.lazy()     # downstream plans now start from the materialised frame
rows = df.height ; schema = df.schema
```

Each plan executes once, and downstream nodes read the cached frame, so total work is about the same
as the lazy run (it loses cross-node predicate/projection pushdown and streaming; memory grows by
the intermediate frames). Eager `pl.DataFrame` outputs: `rows = value.height`, method `eager`, not replaced.

**Mode `sink`:** no materialisation, no extra passes except:
- File Input nodes (spec `is_source`): `value.select(pl.len()).collect(engine="streaming").item()`. For a CSV scan this is a projection-less line count (fast, one sequential read); method `scan_plan`.
- Output nodes: `rows` counted from the **written file** (`count_rows_in_file`, method `output_file`), and the output node's `rows_in` entry gets the same number (`rows_in[0].rows` is set to it if null).
- All other nodes: `rows_out` null, method `none`; `columns_out` from `collect_schema()` (metadata only).

**Mode `off`:** no counting, no schema, only fingerprints.

**Failure handling (hard rule):** the audit layer must never change a run's outcome. Any exception
in counting or materialising is caught, the variable stays lazy and unchanged, `rows` is `null`,
method `none`, and a string `"row count skipped for <variable>: <ExcType>: <msg>"` is appended to the node's warnings.
(Consequence: in mode `all` a broken plan that used to "succeed" silently - brief fact 2 - now shows up as a warning, still not a failure.)

**Cost / trade-off summary (this is the documented budget):**

| Mode | Extra work vs a plain Run | Memory | Budget (perf test, 6.5) |
|---|---|---|---|
| `off` | fingerprints only | none | <= 5% |
| `sink` | 1 file hash per input/output + 1 count pass over each source file + 1 count pass over each output file | none | <= 5% of the run time for the 1M-row workflow |
| `all` | same as `sink`, plus the plans are materialised at every node | all intermediates stay alive until the run ends (the executor context already keeps every variable) | <= 25% of the run time or <= 0.5 s, whichever is larger |

Why default `auto` with 256 MB: typical audit extracts are far below it, so the default gives exact
per-node counts; the big-data case degrades to the cheap mode instead of running out of memory.

**Derived values:** `rows_in` is never counted; it is looked up from the upstream node's `rows_out` through the edge list (`EdgeRef`), so there is no extra pass.

**Reconciliation check (in `finish`):** for every output node with `rows_in[0].rows` and the output file's `row_count` both non-null and different, append a run-level warning
`"row count mismatch: <title> received N rows but <path> contains M"`. (Excel/JSON outputs count after collect, so equality is expected too.)

`count_rows_in_file(path, fmt, delimiter) -> int | None`:

| fmt | method |
|---|---|
| `csv`, `custom_delimited` | `pl.scan_csv(path, separator=sep, infer_schema=False, has_header=True).select(pl.len()).collect(engine="streaming").item()` (`sep` = delimiter or ","). Handles quoted newlines and a UTF-8 BOM. |
| `parquet` | `pl.scan_parquet(path).select(pl.len()).collect().item()` (footer metadata, near free) |
| `ipc` | `pl.scan_ipc(path)...` same pattern |
| `ndjson` | `pl.scan_ndjson(path)...` same pattern |
| `json` | `pl.read_json(path).height` |
| `excel` | `openpyxl.load_workbook(path, read_only=True)` -> first sheet `max_row - 1` (header row), closed in `finally`; **import inside the function** (openpyxl is declared, brief 2.1). `None` if openpyxl or the file fails. |
| other / any exception | `None` |

### 3.6 Fingerprinting (hashing)

`sha256_stream(path, *, cancel: threading.Event | None, chunk: int = 8 * 1024 * 1024) -> str | None`:
opens `rb`, loops `f.read(chunk)`, updates `hashlib.sha256`, checks `cancel.is_set()` before every
chunk and returns `None` (status `cancelled`) when set. 8 MiB: large enough for throughput, small
enough that cancel reacts in well under a second on a local disk.

`FingerprintCache` (in-memory + persisted):
- key `(normalised absolute path, size_bytes, mtime_ns)` -> `sha256`.
- persisted to `<store_dir>/hash_cache.json` (plain JSON, **not** part of the chain, advisory). Loaded lazily, saved at `finish`, capped at 2000 entries (oldest dropped by insertion order). A corrupt cache file is ignored (renamed to `hash_cache.json.bad`).
- A hit sets `sha256_status = "cached"`. Why trust it: `(size, mtime_ns)` is the same test every build tool uses; the status makes it visible, and `audit/hash_cache` is **not** a preference - the cache is always on, but `Check inputs` (3.9) and `Verify` recompute with `use_cache=False`.

`fingerprint_file(path, role, node_id, sheet, *, cache, cancel, hash_enabled, hash_max_bytes) -> FileFingerprint`:

| Condition | Result |
|---|---|
| path empty | not called (caller skips) |
| `os.stat` raises `FileNotFoundError` | `size_bytes=None`, `sha256_status="missing"`, `error="FileNotFoundError"` |
| other `OSError` on stat/open | `sha256_status="error"`, `error="<ExcType>: <msg>"` (e.g. locked file, permission) |
| `hash_enabled` false | stat only, `sha256_status="disabled"` |
| `size > hash_max_bytes` | stat only, `sha256_status="skipped_size_limit"` |
| cache hit | `"cached"` |
| else | stream; `"computed"` or `"cancelled"` or `"error"` |

`hash_max_bytes = audit/hash_max_mb * 1024 * 1024` (default 2048 MB). Why: a 50 GB input would add
minutes to every run; the user can raise the limit, and the record says it was skipped.

When hashed: **inputs in `before_node`** (so the digest describes the file *before* the node reads it;
re-hashing after the read could see a changed file); **outputs in `after_node`** (after the sink
returned). Both run on the worker thread, never on the GUI thread.

### 3.7 Hook points used (brief H1-H13) and executor changes

| Hook | Used? | Exactly how |
|---|---|---|
| H1 `executeWorkflow` (`workflow_execution_mixin.py:47`) | **yes** | In plan 09 F-E's `executeWorkflow` skeleton, between `self._workflow_executor = executor` and the `worker = WorkflowWorker(...)` line (plan 09 F-E names this insertion; this plan adds only the one call): `self._run_session = RunSession.start(self, sorted_nodes, executor)`; the session builds `NodeSpec`s and `EdgeRef`s, calls `RunRecorder.begin`, assigns the **hook bodies** to `executor.before_node/after_node` (the attributes exist, default `None`, via plan 09 F-B) and calls `set_run_record_provider(session.snapshot_current)` (plan 06 reads the in-flight record through it). Wrapped in try/except: a failure logs and sets `_run_session = None`; the Run proceeds. |
| H2 `_on_node_finished` (`:96`) | **yes** | First statement: `self._run_session.node_finished(node, result)` (try/except). Runs on the GUI thread; the executor's `after_node` already ran on the worker thread before `nodeFinished` was emitted, so the counts exist. |
| H3 `_on_node_errored` (`:114`) | **yes** | `self._run_session.node_errored(node, exc)` -> node record `failed`, `error` from `translate_exception(exc)`. |
| H4 `_on_workflow_finished` (`:125`) | **yes** | After `getPyFile(...)` (line 134) and before the cleanup scheduling: `session.finish_when_settled(success, on_done)` (sequence in 3.7a); `on_done(path)` logs `"Run log saved: <path>"` (or the failure) to the Logging dock, calls `set_run_record_provider(None)` and emits `runRecorded(path)`. Then `executionResultsChanged` is emitted as before (so `run_workflow_and_wait` returns **after** the record is on disk). |
| H5 executor | **yes (bodies only)** | The `ExecutionResult` fields, the `NodeExecutor.before_node`/`after_node`/`code_filter` attributes (default `None`) and their call sites are **provided by plan 09 F-B**. This plan supplies only the recorder bodies assigned to them (below). |
| H6 `after_execution` content hook | **no** | Per-node opt-in; the new executor-level `after_node` covers every node uniformly. |
| H7 worker signals | **no** | No change to `WorkflowWorker` (brief recipe). |
| H8, H9, H12 | **no** | Live evaluation is not a run; loguru text is not structured. |
| H10 `getPyFile` | **no** | Left as is. The recorder builds its own script text. |
| H11 load-time validation | **no** | Input checks happen at run time (3.6) and in the dock (3.9). |
| H13 `TriggerScene.serialize` (`performance_scene.py:166`) | **consumed** | `workflow_uuid` in `workflow_metadata` is **provided by plan 09 F-F** (3.12); this plan only reads `scene.workflow_uuid`. |

**Provided by plan 09 F-B (do not edit these in this plan):** the `ExecutionResult` fields
`started_at: str`, `finished_at: str` (UTC ISO `YYYY-MM-DDTHH:MM:SS.ffffffZ`), `code: str` (raw
`get_code()` text, before `code_filter`), `exception`, `traceback_text`, `exception_type`,
`policy_violation` (all defaulted); the `NodeExecutor.before_node`, `after_node` and `code_filter`
attributes (`None` by default; hook exceptions are logged at WARNING and never fail a node); and the
insertion points in `execute_node` (`started_at` first; `result.code` = raw code, then `code_filter`,
then `before_node(node)` before `exec`; `after_node(node, local_variables, result)` after `exec`
succeeded and the `after_execution` block and **before** `execution_context.update(local_variables)`,
followed by `result.variables = local_variables.copy()`; `finished_at` in `finally`). Contract this
plan relies on: `before_node(node)` is called on the worker thread before exec (not when
`get_code()`/`code_filter` raised); `after_node(node, local_variables, result)` only on success, may mutate
`local_variables` in place, and its effect reaches `execution_context` and `result.variables`.
If plan 09 has not landed when you start Step 5, stop: Step 5 only verifies those contracts.

`after_node` is only called on success (failure paths skip it). Failure bookkeeping happens in `RunSession.node_finished` on the GUI thread.

### 3.7a Sealing a failed run: sequence with plan 03's problems (decided)

Goal: the saved record already contains plan 03's enriched error (culprit node, row), never the raw first translation.

Plan 03 contract used here (names are plan 03's; wrap every use in `getattr`/`try` so an absent API degrades to the plain `NodeError`):
`window.problems_store` with Qt signal `settled`, `is_settled() -> bool` and `error_for(node_id) -> NodeError | None`; function `enrich_error(error: NodeError, *, node=None) -> NodeError` (synchronous).

**GUI run (`RunSession.finish_when_settled(success, on_done)`):**
1. `success` true, or no `problems_store`, or `problems_store.is_settled()` already true -> `path = self.finish(success)`; `on_done(path)`; done.
2. Otherwise connect `problems_store.settled` once (single-shot) to a slot that runs step 3, and start a `QTimer.singleShot(5000, step3)` guard (whichever fires first runs step 3; a flag makes it run once).
3. Step 3: for every node record with `status == "failed"`, replace its `error` with `error_for(node_id).to_dict()` when that is not None (via `RunRecorder.update_node_error(node_id, error_dict)`, legal because nothing is sealed yet); then `path = self.finish(success)`; `on_done(path)`.
4. The Run-button re-enable and cleanup are not delayed (they stay in `_execution_cleanup`); only the record write is. `executionResultsChanged` is still emitted at the end of `_on_workflow_finished`; for failed runs the record may therefore appear slightly after it, so tests of failed runs wait on `runRecorded` (6.3 #8).

**Headless / CLI:** `node_finished` calls `errors_adapter.error_to_dict(result, node, enrich=True)`, which calls plan 03's synchronous `enrich_error` itself when `AuditOptions.sync_enrich` is true (default false for the GUI, set true by plan 08). No signals involved; `finish` seals immediately.

### 3.8 Public API (final; other plans rely on exactly this)

`trigger_designer.core.audit` re-exports all of these. The brief 11.3 signatures are kept; additions are keyword-only with defaults.

```python
# schema.py
RUN_RECORD_SCHEMA_VERSION = 1
HASH_ALGO = "sha256-canonical-json-v1"
GENESIS_HASH = "0" * 64

@dataclass(frozen=True)
class FileFingerprint:
    role: str                      # "input" | "output"
    path: str
    size_bytes: int | None = None
    modified_time: str | None = None
    sha256: str | None = None
    sheet: str | None = None
    node_id: int | None = None
    mtime_ns: int | None = None
    sha256_status: str = "disabled"
    row_count: int | None = None
    row_count_method: str = "none"
    error: str | None = None
    def to_dict(self) -> dict: ...
    @staticmethod
    def from_dict(d: dict) -> "FileFingerprint": ...      # ignores unknown keys

@dataclass(frozen=True)
class NodeRunRecord:
    node_id: int
    op: str
    title: str
    status: str                    # "ok" | "failed" | "skipped"
    seq: int = 0
    label: str | None = None
    started_at: str | None = None
    duration_s: float = 0.0
    count_seconds: float = 0.0
    settings: dict = field(default_factory=dict)
    seed: int | None = None
    code_sha256: str | None = None
    rows_in: list = field(default_factory=list)            # [{socket, from_node_id, from_socket, variable, rows}]
    rows_out: dict = field(default_factory=dict)           # variable -> int | None
    columns_out: dict = field(default_factory=dict)        # variable -> [name]
    dtypes_out: dict = field(default_factory=dict)         # variable -> [dtype str]
    count_method: dict = field(default_factory=dict)       # variable -> method
    peak_memory_mb: float = 0.0
    warnings: list = field(default_factory=list)
    error: dict | None = None                              # NodeError as dict (plan 03)
    test_summary: dict | None = None                       # TestSummary as dict (plan 04)
    def to_dict(self) -> dict: ...
    @staticmethod
    def from_dict(d: dict) -> "NodeRunRecord": ...

@dataclass(frozen=True)
class RunRecord:
    run_id: str
    started_at: str
    finished_at: str
    status: str                    # "ok" | "failed" | "cancelled"
    app_version: str
    workflow_schema_version: int
    workflow_path: str | None
    workflow_sha256: str | None
    user: str | None
    machine: str | None
    python_version: str
    polars_version: str
    inputs: list = field(default_factory=list)             # [FileFingerprint]
    outputs: list = field(default_factory=list)           # [FileFingerprint]
    nodes: list = field(default_factory=list)              # [NodeRunRecord]
    generated_code: str | None = None
    # extensions (all defaulted)
    schema_version: int = RUN_RECORD_SCHEMA_VERSION
    seq: int = 0
    duration_s: float = 0.0
    app_name: str = "TriggerDesigner"
    duckdb_version: str | None = None
    os_name: str = ""
    workflow_uuid: str | None = None
    graph_sha256: str = ""
    workflow_modified_since_save: bool | None = None
    options: dict = field(default_factory=dict)
    baseline: dict | None = None
    warnings: list = field(default_factory=list)
    generated_code_sha256: str = ""
    hash_algo: str = HASH_ALGO
    prev_record_hash: str = GENESIS_HASH
    record_hash: str = ""
    def to_dict(self) -> dict: ...                         # nested dataclasses -> dicts; the on-disk shape
    @staticmethod
    def from_dict(d: dict) -> "RunRecord": ...

def validate_record_dict(d: dict) -> list[str]: ...        # [] when valid; messages like "nodes[2].status: expected one of ok/failed/skipped"

# canonical.py
def canonical_json(obj) -> bytes: ...
def sha256_hex(data: bytes) -> str: ...
def compute_record_hash(record_dict: dict) -> str: ...
def utc_now_iso() -> str: ...                              # "2026-10-21T09:14:03.120456Z"

# recorder.py
@dataclass(frozen=True)
class EdgeRef:
    src_node_id: int; src_socket: int; dst_node_id: int; dst_socket: int

@dataclass(frozen=True)
class NodeSpec:
    node_id: int
    op: str
    title: str
    label: str | None = None
    settings: dict = field(default_factory=dict)           # already JSON-safe
    n_outputs: int = 0
    output_variables: tuple[str, ...] = ()                 # socket order
    is_source: bool = False                                # File Input style
    input_files: tuple[dict, ...] = ()                     # ({"path","sheet","kind"},)
    output_files: tuple[dict, ...] = ()                    # ({"path","format","delimiter"},)

@dataclass(frozen=True)
class AuditOptions:
    record_identity: bool = True
    hash_inputs: bool = True
    hash_outputs: bool = True
    hash_max_mb: int = 2048
    row_counts: str = "auto"
    exact_counts_max_mb: int = 256
    embed_code: bool = True
    store_dir: str = ""                                    # explicit override of the store folder ("" = default resolution)
    app_data_dir: str = ""                                 # fallback root, "" = no fallback
    enabled: bool = True                                   # False = --no-record: nothing is written; begin returns a record, finish returns it unsealed
    sync_enrich: bool = False                              # True = call plan 03 enrich_error() synchronously in node_finished (headless)

class RunRecorder:
    def __init__(self, store: "RunStore | None" = None, options: AuditOptions | None = None,
                 *, cache: FingerprintCache | None = None) -> None: ...
    # brief signature, extended with keyword-only args:
    def begin(self, workflow_path: str | None, nodes: Sequence[NodeSpec], *, app_version: str,
              edges: Sequence[EdgeRef] = (), workflow_uuid: str | None = None,
              modified_since_save: bool | None = None) -> RunRecord: ...
    def before_node(self, node) -> None: ...               # executor hook, worker thread; node has .id
    def after_node(self, node, local_variables: dict, result) -> None: ...   # executor hook, worker thread
    def node_finished(self, record: RunRecord, node, execution_result, *,
                      rows_out: dict | None = None, test_summary: dict | None = None) -> NodeRunRecord: ...
    def node_errored(self, record: RunRecord, node, exc: BaseException) -> NodeRunRecord: ...
    def finish(self, record: RunRecord, success: bool, *, cancelled: bool = False,
               outputs: Sequence[FileFingerprint] | None = None, save: bool = True) -> RunRecord: ...
    # outputs: post-commit output fingerprints supplied by a headless caller (plan 08 may move files after the run);
    #          when not None they REPLACE the recorder's own `outputs` (no merging); reconciliation uses the replaced list.
    # save=False: build and return the final (unsealed) record without touching the store (--no-record).
    #          AuditOptions(enabled=False) behaves like save=False for every call.
    def update_node_error(self, node_id: int, error: dict) -> None: ...   # only before finish(); raises RunAlreadySealed after
    def snapshot(self, record: RunRecord | None = None) -> dict: ...      # plan 06: deep copy taken under the recorder lock
    def request_cancel(self) -> None: ...                  # sets the cancel event; hashing stops at the next chunk
    # module-level registry in recorder.py (plan 06):
    #   set_run_record_provider(provider: Callable[[], dict | None] | None) -> None
    #   get_run_record_provider() -> Callable[[], dict | None] | None
    @property
    def last_path(self) -> str | None: ...                 # where finish() saved the record (None if saving failed)

```

**Immutability rules (binding):** a `RunRecord` is never mutated. `status` is set only by `finish` (via `dataclasses.replace`), never by `node_finished`, `begin` or the caller; `begin` returns `status="running"`. Once `seal_and_save` succeeded for a `run_id`, a second `save` / `seal_and_save` / `finish` for it raises `RunAlreadySealed` (the recorder remembers sealed ids; the store also refuses to overwrite an existing `<run_id>.json`). `RunAlreadySealed(Exception)` lives in `store.py`.

`snapshot(record=None)`: acquires the recorder lock and returns a `copy.deepcopy` of the in-flight state as a plain dict with the on-disk shape (`nodes` = records finished so far, `status` = `"running"`, `record_hash` = `""`); if `record` is a sealed record, returns `copy.deepcopy(record.to_dict())`. The result shares no objects with the recorder.

**Lazy package init:** `core/audit/__init__.py` must not import submodules eagerly (plan 04's exec'd generated code may `import trigger_designer.core.audit.<name>`):

```python
_EXPORTS = {"RunRecord": "schema", "NodeRunRecord": "schema", "FileFingerprint": "schema", "canonical_json": "canonical",
            "RunRecorder": "recorder", "AuditOptions": "recorder", "NodeSpec": "recorder", "EdgeRef": "recorder",
            "set_run_record_provider": "recorder", "get_run_record_provider": "recorder", "RunAlreadySealed": "store",
            "RunStore": "store", "verify_store": "store", "compare_runs": "compare", ...}  # every public name of this section

def __getattr__(name):
    mod = _EXPORTS.get(name)
    if mod is None:
        raise AttributeError(name)
    import importlib
    value = getattr(importlib.import_module(f"{__name__}.{mod}"), name)
    globals()[name] = value
    return value
```

API listing continues:

```python
# store.py
class RunStore:
    def __init__(self, run_log_dir: str = "", app_data_dir: str | Path | None = None) -> None: ...
    def store_dir_for(self, workflow_path: str | None) -> Path: ...
    def save(self, record: RunRecord, directory: str | Path | None = None) -> str: ...        # seals + writes; returns the path
    def seal_and_save(self, record: RunRecord, directory=None) -> tuple[RunRecord, str]: ...  # returns the sealed record too
    def load(self, path: str | Path) -> RunRecord: ...
    def load_dict(self, path: str | Path) -> dict: ...                                         # raw, for verify/compare/export
    def list_runs(self, directory: str | Path | None = None, workflow_path: str | None = None) -> list["RunHeader"]: ...
    def verify(self, directory=None, workflow_path=None) -> "VerifyReport": ...

@dataclass(frozen=True)
class RunHeader:
    seq: int; run_id: str; started_at: str; status: str; record_hash: str; prev_record_hash: str; file: str

@dataclass(frozen=True)
class VerifyProblem:
    run_id: str | None
    kind: str      # record_hash_mismatch | prev_hash_mismatch | missing_record | index_mismatch | seq_gap | schema_invalid | unreadable | index_corrupt
    message: str

@dataclass(frozen=True)
class VerifyReport:
    ok: bool                       # True iff problems == []
    checked: int
    problems: list[VerifyProblem]
    warnings: list[str]            # orphan_record, clock_skew, index_truncated_line, incomplete_run
    head_hash: str | None          # record_hash of the last verified record

def verify_store(directory: str | Path) -> VerifyReport: ...
def verify_record_file(path: str | Path) -> VerifyReport: ...   # hash of one file only (no chain)

# compare.py
@dataclass(frozen=True)
class DiffItem:
    kind: str          # "input" | "parameter" | "row_count" | "status" | "output" | "environment" | "node_set"
    node_id: int | None
    node_title: str | None
    field: str         # e.g. "sha256", "settings.delimiter", "rows_out.var_x_5"
    old: object
    new: object

@dataclass(frozen=True)
class RunDiff:
    old_run_id: str; new_run_id: str
    items: list[DiffItem]
    @property
    def identical(self) -> bool: ...

def compare_runs(old: dict, new: dict) -> RunDiff: ...           # raw record dicts

@dataclass(frozen=True)
class InputCheck:
    path: str; sheet: str | None
    state: str         # "unchanged" | "modified" | "missing" | "skipped" | "error"
    recorded_sha256: str | None
    current_sha256: str | None

def check_inputs(record: dict, *, cancel: threading.Event | None = None, use_cache: bool = False) -> list[InputCheck]: ...
```

Final-API promises to other plans:
- **06 (workpaper)** reads `RunRecord.from_dict(RunStore().load_dict(path))` and uses `nodes[].test_summary`, `inputs`, `outputs`, `record_hash`, `generated_code`.
- **08 (CLI)** headless recipe (plan 08 is edited to use exactly this): `recorder = RunRecorder(RunStore(...), AuditOptions(store_dir=<--record-dir>, enabled=not no_record, sync_enrich=True))`; `specs, edges = audit_bridge.node_specs_from_window(window, sorted_nodes)` (the only supported way to build `NodeSpec`/`EdgeRef` headlessly); `record = recorder.begin(path, specs, app_version=VERSION, edges=edges, workflow_uuid=window.scene.workflow_uuid)`; `executor.before_node = recorder.before_node; executor.after_node = recorder.after_node` (this is how fingerprints and row counts are obtained - there is no other API); after each node `recorder.node_finished(record, node, result)`; `final = recorder.finish(record, success, cancelled=..., outputs=<post-commit fingerprints or None>, save=not no_record)`. `recorder.last_path` is the saved file. `AuditOptions.store_dir` chooses the record directory. A second `finish` on the same record raises `RunAlreadySealed`. `RunSession` is GUI-only.
- **06 (workpaper)** live access: `get_run_record_provider()` returns the callable installed at H1 (cleared to None at H4); `recorder.snapshot()` / `session.snapshot_current()` give a locked deep-copied dict.
- **04 (test nodes)** puts a `TestSummary` dict where the recorder can find it: after exec the recorder reads `getattr(node.content, "test_summary", None)` in `node_finished` (GUI thread) and, if it has `to_dict`/is a dataclass, stores `dataclasses.asdict(...)`. No plan-04 import in core. (Only `test_summary` uses `asdict`; **errors use `NodeError.to_dict()`**, 3.8a.)

### 3.8a Error serialisation (decided)

`errors_adapter.error_to_dict` returns `NodeError.to_dict()` (plan 03; tuples such as `columns` become lists, so `canonical_json` accepts it). **Never** `dataclasses.asdict` (tuples survive and `canonical_json` raises). The adapter also runs `_json_safe(d)` (tuple -> list, recursively) as a guard. Stored key set = plan 03's complete `NodeError` field set: `code, title, detail, hint, technical, exc_type, severity, node_id, node_title, op, columns, path` plus any further keys `to_dict()` returns (for example culprit node/row added by enrichment). The schema validator checks only "object or null" and that `code` and `title` are strings.

### 3.9 Compare, "re-run with same inputs" check

`compare_runs(old, new)` (pure, on raw dicts) emits `DiffItem`s in this order, nothing else:

1. `environment`: `app_version`, `polars_version`, `python_version`, `duckdb_version` when different.
2. `input`: match input fingerprints by `(node_id, path, sheet)`; emit `added` / `removed` (`field="presence"`), or `field="sha256"` when both non-null and different, `field="size_bytes"` when sha is unavailable and sizes differ.
3. `node_set`: nodes present in only one run (`field="presence"`).
4. For nodes in both (matched by `node_id`): `parameter` per changed settings leaf (`field="settings.<dotted path>"`, via recursive dict diff; lists compared whole); `seed`; `status`; `row_count` for each `rows_out[variable]` that differs (`field="rows_out.<variable>"`; both None = no item; one None = item).
5. `output`: match output fingerprints by `(node_id, path)`; `sha256` / `row_count` differences.

`check_inputs(record)`: for each recorded input with a path, recompute the SHA-256 now (no cache by default) and return `InputCheck`. State rules: file missing -> `missing`; recorded sha null -> `skipped`; digests equal -> `unchanged`; else `modified`; I/O error -> `error`. Runs in a background task (`AuditTask`); cancellable.

**Re-run warning, automatic:** at `finish`, `baseline.input_changes` is computed against the previous run in the same store (3.3). If non-empty and `audit/warn_on_input_change` is true (default true), `RunSession.finish` logs one Logging-dock warning per changed input: `Input changed since the previous run: <path>`. It never blocks a run. Why: the question an auditor asks is "was the data the same as last time", and the answer must be in the record itself.

### 3.10 Settings snapshot and seed

`snapshot_settings(content) -> dict` (in `audit_bridge.py`, GUI thread):
1. If `content` has `get_serialized_state` (SerializableContentMixin, pure): `state = content.get_serialized_state()`; else `state = content.serialize()` inside try (hand-written nodes: Split, File Output); on exception `{"_error": "settings unavailable: <ExcType>"}`.
2. Drop keys `schema_snapshot`, `available_sheets`, `file_metadata`, `id`, `pos_x`, `pos_y`, and any key whose name starts with `_`. Why: bulky or volatile, not settings.
3. `sanitize(state)`: recursive; dict keys -> `str`; tuple/set -> list (sets sorted by `repr`); `Path` -> `str` with forward slashes; `datetime` -> ISO; non-finite float -> None; any other non-JSON type -> `repr(value)[:200]`; strings longer than 20000 chars truncated with `"...[truncated]"`; recursion depth capped at 12 (deeper -> `"..."`).
4. Path-valued keys (`filePath`) are recorded as stored (absolute) with backslashes replaced by `/`.

`extract_seed(settings) -> int | None`: if `settings.get("is_random") is False` -> None; else first int found in keys `("random_seed", "seed")`; else None. (Split: `random_seed`, `is_random` verified in `split.py:75-76`.)

### 3.11 Storage layout

```
C:/Work/Q3/orders.tds
C:/Work/Q3/orders.runs/              <- store dir (stem of the .tds + ".runs")
    index.jsonl                      append-only, one canonical-JSON line per sealed run
    6f1c0a52b3e84f6f9c1d2e7a8b4c5d60.json   immutable record (chmod read-only, best effort)
    hash_cache.json                  advisory fingerprint cache (not chained)
    .lock                            transient lock file
    <run_id>.started                 transient marker, deleted on seal (crash detection)
```

`index.jsonl` line: `{"file":"<run_id>.json","prev_record_hash":"...","record_hash":"...","run_id":"...","seq":3,"started_at":"...","status":"ok"}`.

`resolve_store_dir(workflow_path, run_log_dir, app_data_dir) -> Path`:

| Case | Directory |
|---|---|
| `run_log_dir` set (preference) and workflow saved | `<run_log_dir>/<stem>-<sha1(abs workflow path lowercase)[:8]>` |
| `run_log_dir` set and unsaved | `<run_log_dir>/_unsaved` |
| default, saved | `<workflow dir>/<stem>.runs` |
| default, unsaved | `<app_data_dir>/runs/_unsaved` |
| default, saved, **not writable** (makedirs / probe raises `OSError`) | `<app_data_dir>/runs/<stem>-<hash8>`; the run's `warnings` gets `"run log stored in fallback folder: <dir> (workflow folder is read-only)"` |

Why next to the .tds by default: the log travels with the workflow (zip a folder, hand it to an
auditor). Why a hash suffix in the relocated case: two workflows named `a.tds` in different folders
must not share a chain.

**Commit procedure** (`RunStore.seal_and_save`), all inside the lock:
1. `acquire_lock(dir)`: `os.open(dir/.lock, O_CREAT | O_EXCL | O_WRONLY)`, write `pid`; retry every 50 ms up to 10 s; a lock file older than 60 s is stale and removed. On timeout raise `StoreLockTimeout`.
2. Read the last **complete** line of `index.jsonl` (tolerate a final line without `\n`: ignore it, add a warning). `prev = its record_hash` or `GENESIS_HASH`; `seq = its seq + 1` or 1.
3. Build the dict: `record.to_dict()` with `seq`, `prev_record_hash`; `record_hash = compute_record_hash(...)`.
4. Write `<run_id>.json.tmp` (pretty: `OPT_INDENT_2 | OPT_SORT_KEYS`), `flush`, `os.fsync`, `os.replace` to `<run_id>.json`; then `os.chmod(path, stat.S_IREAD)` in try.
5. Append the index line (`open("ab")`, write, `flush`, `os.fsync`).
6. Delete `<run_id>.started`; release the lock (delete `.lock`) in `finally`.

`begin` writes the `<run_id>.started` marker (empty file) - best effort - so `list_runs` can report
runs that never sealed (`incomplete_run` warning in verify).

### 3.12 `workflow_uuid` (H13) - provided by plan 09 F-F

The `workflow_uuid` property on `TriggerScene`, its persistence in `workflow_metadata` and the atomic
UTF-8 `saveToFile` (with `workflow_dir` / `_save_target`) are **provided by plan 09 F-F**. This plan only reads
`window.scene.workflow_uuid` in `RunSession.start` and uses `window.workflow_dir` (plan 09) as the folder
for `<stem>.runs` when `window.filename` is set. Why: a moved/renamed `.tds` keeps its identity, so
records can be attributed to the workflow even after the path changes.

### 3.13 Threading rules (binding)

| Operation | Thread | Rule |
|---|---|---|
| `RunSession.start` -> `RunRecorder.begin` (stat of inputs, workflow hash, settings snapshot, `scene.has_been_modified`) | GUI | Reads nodes/contents; must be fast. Workflow-file hashing is bounded: the `.tds` is read whole (small). |
| `before_node`, `after_node` (hashing, counting, materialising) | executor worker thread (the `QThread` that calls `execute_node`) | Never touches Qt objects or node/content attributes. Works only on `NodeSpec` data and the frames passed in. `node.id` is read (an `int` attribute) - allowed. |
| `node_finished`, `node_errored` | GUI | May read `node.content.test_summary`, call `translate_exception(..., node=node)`. |
| `finish` -> `seal_and_save` | GUI | I/O is a few small writes under a lock (<= 10 s worst case, normally < 20 ms). If the lock times out the record goes to the fallback folder. |
| Verify / check inputs / export in the dock | `QThreadPool` (`AuditTask`) | Result via queued signal. The dock never reads big files on the GUI thread. |
| Shared recorder state | | One `threading.RLock` guards `_counts`, `_fingerprints`, `_warnings` between the worker thread (writes) and the GUI thread (reads in `node_finished/finish`). `finish` is only called after `workflowFinished`, so the worker has stopped. |

### 3.14 Preference keys (add to `qt/preferences.py` `DEFAULTS`)

| Key | Default | Meaning |
|---|---|---|
| `audit/record_runs` | `True` | Master switch. Off -> `RunSession.start` returns None; nothing is recorded. |
| `audit/run_log_dir` | `""` | Relocate stores (3.11). |
| `audit/record_identity` | `True` | Off -> `user` and `machine` are null. |
| `audit/hash_inputs` | `True` | |
| `audit/hash_outputs` | `True` | |
| `audit/hash_max_mb` | `2048` | |
| `audit/row_counts` | `"auto"` | `auto` / `all` / `sink` / `off`. Unknown value -> treated as `"auto"` by `options_from_preferences`. |
| `audit/exact_counts_max_mb` | `256` | |
| `audit/embed_code` | `True` | |
| `audit/warn_on_input_change` | `True` | |

UI: a new "Audit trail" group in the **General** page of `qt/dialogs/preferences_dialog.py`
(`_build_general_page`, `:392`), loaded in the dialog init next to the pattern at `:454`, written in
the slot pattern at `:638`. Controls: checkbox record, line edit + browse for folder, checkbox identity,
two checkboxes hashes, spin for max MB, `NoWheelComboBox` for row counts (`Auto / All nodes / Sinks only / Off`), spin for threshold, checkbox embed code, checkbox warn.

### 3.15 Run History dock (UI)

`RunHistoryDock(QDockWidget)`, `objectName "RunHistoryDock"`, title `"Run History"`, bottom area, tabified with Logs and Data Preview. Follows the active window like `LoggingDock`.

```
+------------------------------------------------------------------------------+
| [refresh] [verify] [folder] | [check-inputs] [compare] | [export-json] [export-html]   <- toolbar H40, margins 0
+------------------------------------------------------------------------------+
| #  | Started (local)     | Status | Duration | Nodes | Rows out | Chain      <- runs table (ColumnTable)
| 3  | 2026-10-21 09:14:03 | ok     | 0.9 s    | 3     | 3        | ok
| 2  | ...                                                                       |
+---------------------------------------+--------------------------------------+
| Summary (ConfigSection, read-only)    | Nodes table (ColumnTable)            |
|  Run id        6f1c0a52...            | Node | Op | Status | In | Out | Cols | Time | Error
|  Started/Ended ...                    | File Input | input.file_input | ok | - | 3 | 2 | 12 ms | |
|  Workflow      orders.tds (sha 9d2b..)|                                      |
|  Inputs        1 (all hashed)         |                                      |
|  Outputs       1                      |                                      |
|  Chain         verified / not checked |                                      |
+---------------------------------------+--------------------------------------+
| status strip: "12 runs - chain verified at 09:20 - head ab12cd34"                |
+------------------------------------------------------------------------------+
```

- **Toolbar buttons** (all `IconButton.themed(tooltip, rsm_icon=rsm.get("<id>"), qss_fallback=":/qss_icons/dark/rc/<name>.png")`, fixed 30x30, tooltip + accessibleName mandatory; AGENTS.md rules):

| Button | tooltip | glyph id | Action |
|---|---|---|---|
| Refresh | `Refresh run list` | `icon_refresh` (exists) | reload `index.jsonl` |
| Verify | `Verify run log` | `icon_apply` (exists) | `verify_store` in background; result in the status strip + a dialog listing problems (text allowed in dialogs) |
| Folder | `Open run log folder` | `icon_folder_open` (exists) | `QDesktopServices.openUrl` on the store dir |
| Check inputs | `Check inputs against selected run` | `icon_search` (exists) | `check_inputs` in background; result table in a dialog; a "modified" row is highlighted with the `warning` token |
| Compare | `Compare two selected runs` | new `icon_compare` | checkable; enabled only when exactly 2 runs are selected; switches the lower pane to the diff table (`DiffTableModel`: Kind, Node, Field, Old, New) |
| Export JSON | `Export selected run as JSON` | `icon_save` (exists) | `export_json` (byte copy) via a save dialog |
| Export HTML | `Export selected run as HTML report` | `icon_external` (exists) | `render_html` via a save dialog, then opens it with `QDesktopServices` |

New glyph: add `src/trigger_designer/resources/qt/images/node_icons/ui/compare.svg` (monochrome, `currentColor` as the other `ui/*.svg`: two overlapping rectangles `<rect x="2" y="3" width="8" height="10" rx="1"/><rect x="6" y="3" width="8" height="10" rx="1"/>` with `fill="none" stroke="currentColor"`; copy the root element attributes from `ui/refresh.svg`) and `"icon_compare": {"path": "qt/images/node_icons/ui/compare.svg", "mode": "rb"}` in `qt/resources.json`.
- **Tables**: `QTableView` with `objectName "ColumnTable"` (existing QSS, `select.py:134-259` style), 22 px rows, `QSortFilterProxyModel` not needed. Status cells colour via theme tokens `success` / `danger` / `warning` using the same helper approach as `logging_dock.py:30-36` (token name -> `get_theme_manager()` colour). No hex in code.
- **No new QSS objectNames** -> no `base.qss` / `_style.scss` edit. Why: avoids the template/`str.format` risk (brief 5.2).
- **Empty state**: `EmptyStateLabel("No runs recorded yet")` when the list is empty or the workflow is unsaved and has no runs.
- **Layout tokens**: main layout `spacing 2, margins 5`; toolbar fixed height 40; controls 30.
- **Live refresh**: connects to `window.runRecorded(str)`; selects the new run.
- Multi-select: `ExtendedSelection`; the summary/nodes panes show the *current* row; Compare uses the two selected rows ordered by `seq`.
- Wiring (brief 5.5): `createRunHistoryDock` in `main_window_ui_mixin.py` (tabified with `loggingDock`, `install_tab_only_chrome`), `switchRunHistoryDock` + `onDesignWindowClose` branch, call in `main_window.py:~148`, `createMdiChild` connects `runRecorded`, `onSubWindowActivated` calls the switch, a `toggleViewAction` entry "Run History" in `updateWindowMenu`, `apply_theme()` in `apply_appearance`. **Default tab order** (`layout_state.apply_default_layout`, `default_areas`, all `BottomDockWidgetArea`): `problemsDock` (plan 03, first; skipped by the existing `getattr(..., None)` guard if absent), `runHistoryDock`, `loggingDock`, `dataPreviewDock`. Implement: add `("problemsDock", Bottom), ("runHistoryDock", Bottom)` before the `loggingDock` entry; after the loop tabify in order: `tabifyDockWidget(problems, run_history)` (if problems exists), `tabifyDockWidget(run_history, logging)`, `tabifyDockWidget(logging, preview)`; then `raise_()` the first existing of problems / run_history. Creation order in `main_window.py`: `createProblemsDock` (plan 03), `createRunHistoryDock`, then the existing logging/preview creators, so a fresh install gets the same order. Test: `test_default_layout_tab_order` (6.4 #13).

### 3.16 HTML export (`export.render_html(record, verify=None) -> str`)

Self-contained single file, no external assets, no JavaScript needed to read it. Sections: header (run id, status, start/end, duration, app/Python/Polars versions, user/machine, workflow path and sha), integrity box (record_hash, prev_record_hash, verification result if given), inputs table, outputs table, per-node table (op, status, rows in/out, duration, error code + title), errors detail, settings per node in `<details>`, generated code in `<details><pre>`. Every dynamic string goes through `html.escape(str(v), quote=True)`. The original record is embedded as `<script type="application/json" id="run-record">...</script>` with `</` replaced by `<\/` so the page can be re-verified by a tool. CSS uses custom properties and `@media (prefers-color-scheme: dark)`. JSON export = byte copy of the `.json` file (so the hash verifies after the copy).

---

## 4. Ordered implementation steps

Each step is one commit. After **each** step: `ruff format <touched files>`, `ruff check <touched files>`
(compare against the baseline for pre-existing errors, brief 2.3), then the named tests.
Commands use `.venv\Scripts\python.exe -m` (brief 2.3). Never run bare `pytest`.

### Step 1 - core schema + canonical JSON

Create `core/audit/__init__.py` (the lazy `__getattr__` form of 3.8, `_EXPORTS` filled as modules appear), `schema.py`, `canonical.py`.

`canonical.py` skeleton:

```python
import hashlib, orjson
from datetime import datetime, timezone

GENESIS_HASH = "0" * 64
_OPTS = orjson.OPT_SORT_KEYS | orjson.OPT_STRICT_INTEGER

def canonical_json(obj) -> bytes:
    return orjson.dumps(obj, option=_OPTS)           # TypeError on non-JSON types

def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def compute_record_hash(record_dict: dict) -> str:
    body = {k: v for k, v in record_dict.items() if k != "record_hash"}
    return sha256_hex(canonical_json(body))

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
```

`schema.py`: constants, the five dataclasses exactly as in 3.8, `to_dict` (use a helper that converts nested `FileFingerprint`/`NodeRunRecord` lists and **never emits a dataclass field set different from 3.3**), `from_dict` (`{k: d[k] for k in known fields if k in d}`; nested lists mapped through the nested `from_dict`), and `validate_record_dict(d)` (hand-written; checks: required keys of 3.3 present, types, `status` enums, `schema_version` int <= `RUN_RECORD_SCHEMA_VERSION`, hex length 64 for hashes, node `status` enum, `nodes` is a list of dicts with `node_id:int`).

Done when:
```powershell
.venv\Scripts\python.exe -m pytest tests\unit\test_audit_canonical.py tests\unit\test_audit_schema.py -q
```
(tests from 6.1.1-6.1.2) pass, and `.venv\Scripts\python.exe -c "import trigger_designer.core.audit.schema"` works with `QT_QPA_PLATFORM` unset **and** `python -c "import sys, trigger_designer.core.audit.canonical as m; assert 'qtpy' not in sys.modules"`.

### Step 2 - fingerprints, counting, cache

Create `fingerprint.py` and `counting.py` per 3.5-3.6.

```python
# fingerprint.py (signatures)
class FingerprintCache:
    def __init__(self, path: Path | None = None, max_entries: int = 2000) -> None: ...
    def get(self, path: str, size: int, mtime_ns: int) -> str | None: ...
    def put(self, path: str, size: int, mtime_ns: int, sha256: str) -> None: ...
    def save(self) -> None: ...          # atomic tmp+replace; swallow OSError

def sha256_stream(path, *, cancel=None, chunk=8 * 1024 * 1024) -> str | None: ...
def fingerprint_file(path, role, node_id=None, sheet=None, *, cache=None, cancel=None,
                     hash_enabled=True, hash_max_bytes=2 * 1024**3, use_cache=True) -> FileFingerprint: ...
def count_rows_in_file(path, fmt, delimiter=",") -> int | None: ...
```
Normalise path keys with `os.path.normcase(os.path.abspath(p))`; recorded `path` uses `abspath(p).replace("\\", "/")`.

```python
# counting.py
def decide_row_count_mode(requested, total_input_bytes, threshold_mb) -> str: ...
def schema_of(frame) -> tuple[list[str], list[str]]:
    # LazyFrame -> frame.collect_schema(); DataFrame -> frame.schema. names, [str(dtype)].
    # Caps at 500 names, appending "..." to both lists.
def count_frame(frame, mode, *, is_source) -> tuple[int | None, str, object]:
    # returns (rows, method, frame_to_store). Implements 3.5 exactly; never raises:
    # on Exception returns (None, "none", frame) and the caller appends the warning text (so return the exception text via a 4th tuple element is NOT used - raise CountError(msg) instead and let the caller catch).
```
Implementation note: `count_frame` raises `CountError(str)` on failure; the recorder catches it, adds the warning, keeps the original frame. (Decision, so the warning text lives in one place.)

Done when: `pytest tests\unit\test_audit_fingerprint.py tests\unit\test_audit_counting.py -q`.

### Step 3 - store, chain, verify

Create `store.py`: `RunStore`, `RunHeader`, `VerifyProblem`, `VerifyReport`, `StoreLockTimeout`, `resolve_store_dir`, `verify_store`, `verify_record_file`, lock helper, index read.

`verify_store(directory)` algorithm (exact):
1. If `index.jsonl` missing: `checked=0`; if any `*.json` record files exist -> one problem `index_corrupt` ("index missing but N record files present"); else ok.
2. Read the index lines; a final line without `\n` that does not parse -> warning `index_truncated_line` (not a problem); any other unparsable line -> problem `index_corrupt` and stop the chain walk.
3. `expected_prev = GENESIS_HASH`, `expected_seq = 1`. For each entry: if `entry.seq != expected_seq` -> `seq_gap`. Open `<file>`; missing -> `missing_record`; unparsable -> `unreadable`. `validate_record_dict` errors -> `schema_invalid` (does not stop the walk). `compute_record_hash(raw)` != `raw["record_hash"]` -> `record_hash_mismatch`. `raw["record_hash"] != entry.record_hash` or `raw["run_id"] != entry.run_id` or `raw["seq"] != entry.seq` -> `index_mismatch`. `raw["prev_record_hash"] != expected_prev` -> `prev_hash_mismatch`. Then `expected_prev = entry.record_hash`, `expected_seq += 1` (use the **index** value so one bad record is reported once, not on every later record).
4. Warnings: record files not named in the index (`orphan_record`, includes the run_id); `*.started` markers whose run is not in the index (`incomplete_run`); `raw["started_at"] < previous raw["finished_at"]` (`clock_skew`).
5. `head_hash = expected_prev` if `checked > 0` else None. `ok = not problems`.

`verify_record_file(path)`: parse, `validate_record_dict`, recompute hash; problems only from those checks.

Done when: `pytest tests\unit\test_audit_store.py -q` (6.1.3-6.1.5).

### Step 4 - recorder

Create `recorder.py` (`EdgeRef`, `NodeSpec`, `AuditOptions`, `RunRecorder`) and `errors_adapter.py`.

Internal state of `RunRecorder` (private): `_lock`, `_cancel = threading.Event()`, `_spec_by_id`, `_edges`, `_order` (list of node ids), `_mode`, `_fingerprints_in/out` (list), `_counts: dict[node_id -> NodeCounts]` (`rows_out`, `columns_out`, `dtypes_out`, `count_method`, `warnings`, `count_seconds`), `_node_records: dict[node_id -> NodeRunRecord]`, `_perf_start`, `_options`, `_cache`, `_store`, `_code_parts: list[str]`.

`begin(...)`:
1. `run_id = uuid.uuid4().hex`; `perf_start = time.perf_counter()`; `started_at = utc_now_iso()`.
2. `total_input_bytes` = sum of `os.stat().st_size` over every `NodeSpec.input_files` (OSError -> 0); `_mode = decide_row_count_mode(options.row_counts, total, options.exact_counts_max_mb)`.
3. `workflow_sha256` = `sha256_hex(Path(workflow_path).read_bytes())` when the path exists, else None (OSError -> None + warning).
4. `graph_sha256` = `sha256_hex(canonical_json({"nodes": [{"id", "op", "settings"} sorted by id], "edges": sorted([...])}))`.
5. identity: `user/machine` or None per `record_identity`; versions: `polars.__version__`, lazy `duckdb`.
6. Return a `RunRecord` with `status="running"` (the only place that value exists; it is never written to disk), empty `nodes`.
7. Write the `.started` marker via `store.mark_started(run_id, workflow_path)` (try/except).

`before_node(node)`: `spec = _spec_by_id.get(node.id)`; if none return; if `options.hash_inputs` or not: for each `spec.input_files` -> `fingerprint_file(...)` appended to `_fingerprints_in`. If `_cancel.is_set()` the fingerprint is `cancelled`.

`after_node(node, local_variables, result)`: `spec` lookup; `t0`; for outputs per 3.5 (`for i, name in enumerate(spec.output_variables)`: value = `local_variables.get(name)`; if None -> rows None, method `none`); `count_frame` etc.; for `spec.output_files` + `options.hash_outputs`: `fingerprint_file(role="output")`, then `row_count = count_rows_in_file(...)` when mode != `off`; store everything in `_counts[node.id]`, `count_seconds = perf_counter() - t0 - hash time` (just total of this call is fine: `count_seconds` = whole `after_node` duration; decision, simpler).

`node_finished(record, node, result, *, rows_out=None, test_summary=None)`:
- `status = "ok" if result.success else "failed"`.
- `code_sha256 = sha256_hex(result.code.encode())` if `result.code`, and append `result.code` to `_code_parts`.
- `rows_in` from `_edges`: for each edge with `dst_node_id == node.id`, source rows = `_counts[src].rows_out.get(spec_src.output_variables[src_socket])`.
- Output-node `rows_in` fill-in (sink mode) per 3.5.
- `rows_out` / `columns_out` / `dtypes_out` / `count_method`: from `_counts` (or the explicit `rows_out` argument, which overrides, used by tests and plan 08).
- `error`: failed -> `errors_adapter.error_to_dict(result, node)`; ok -> None.
- failed output node: for each `spec.output_files` whose file exists with `mtime_ns >= start`: append `FileFingerprint(role="output", sha256_status="disabled", error="node failed; file may be partial", ...)`.
- `test_summary`: argument, else `getattr(node.content, "test_summary", None)` converted with `dataclasses.asdict` if a dataclass, else `.to_dict()` if present, else None.
- `warnings` = `result.warnings` + counts warnings, each truncated to 500 chars, max 20.
- `duration_s=round(result.execution_time, 6)`, `peak_memory_mb=round(result.peak_memory, 3)`.
- Stores into `_node_records[node.id]`, returns it.

`node_errored(record, node, exc)`: builds a failed `NodeRunRecord` with `error = errors_adapter.exception_to_dict(exc, node)`.

`finish(record, success, *, cancelled=False)`:
1. For each spec in order without a record -> `NodeRunRecord(status="skipped", settings=spec.settings, ...)`.
2. `inputs` = `_fingerprints_in` + for each spec input file that was never fingerprinted (node skipped) nothing (do not invent).
3. `outputs` = `_fingerprints_out`.
4. Reconciliation warnings (3.5), hashing warnings (`skipped_size_limit`, `error`, `cancelled` inputs: `"input not hashed (<status>): <path>"`).
5. `baseline`: `prev = store.latest_record_dict(dir)`; compare input fingerprints by `(path, sheet)` against `prev["inputs"]` -> `input_changes`.
6. `generated_code = "\n".join(_code_parts)`; `generated_code_sha256`; set `generated_code=None` if `not embed_code` or `len > 1_048_576`.
7. `status = "cancelled" if cancelled else ("ok" if success else "failed")`; `finished_at = utc_now_iso()`; `duration_s = round(perf_counter() - start, 6)`.
8. `final = replace(record, ...)`; `sealed, path = store.seal_and_save(final, directory=...)` inside try: on `StoreLockTimeout`/`OSError` retry **once** into the fallback directory (3.11) adding the warning; if that also fails: log via `loguru`, `last_path=None`, return `final` unsealed (the run itself is unaffected).
9. `cache.save()`.

Done when: `pytest tests\unit\test_audit_recorder.py -q` (6.2.1-6.2.4).

### Step 5 - verify the plan 09 F-B foundations (no production edit)

Plan 09 F-B provides the `ExecutionResult` fields and the `before_node`/`after_node`/`code_filter` attributes. Do not edit `executor.py`. Plan 09 F-B creates `tests/unit/test_executor_hooks.py`; append the recorder-contract cases (6.1 #10: `after_node` mutation of `local_variables` reaches `execution_context` and `result.variables`; hook exceptions do not fail the node) to it against the plan 09 contract (3.7); the recorder bodies are installed in Step 6.

Done when: `pytest tests\unit\test_executor_hooks.py tests\unit\test_execution_result.py tests\unit\test_workflow_execution_mixin.py -q` passes. If the first file fails because fields or hooks are missing, plan 09 F-B is not merged: stop and do plan 09 F-B first.

### Step 6 - Qt bridge + mixin wiring (H1-H4)

1. `qt/helpers/audit_bridge.py`:

```python
def options_from_preferences() -> AuditOptions: ...        # reads the 3.14 keys via get_preferences()
def snapshot_settings(content) -> dict: ...                 # 3.10
def node_spec_from_node(node, window) -> NodeSpec: ...
def node_specs_from_window(window, sorted_nodes) -> tuple[list[NodeSpec], list[EdgeRef]]: ...

class RunSession:
    @staticmethod
    def start(window, sorted_nodes, executor) -> "RunSession | None": ...
    def node_finished(self, node, result) -> None: ...
    def node_errored(self, node, exc) -> None: ...
    def finish(self, success: bool) -> str | None: ...       # returns the saved path; passes cancelled=self._cancelled
    def finish_when_settled(self, success: bool, on_done) -> None: ...   # 3.7a
    def snapshot_current(self) -> dict | None: ...            # RunRecorder.snapshot() of the in-flight run
    def request_cancel(self) -> None: ...                     # attaches to plan 09 F-D (below)
```

`node_spec_from_node`:
- `node_id=node.id`; `op = f"{node.node_type.value}.{node.node_code.name.lower()}"` (same expression as `node_base.py:940-955`); for `TriggerNode_Unknown` -> `"unknown"`; `title=node.node_title`; `label=getattr(node, "label_text", None) or None`.
- `output_variables = tuple(window._declared_output_variable_names(node))`; `n_outputs = len(node.outputs)`.
- `is_source = (op == "input.file_input")`.
- input files: `content.resolved_input_files()` if callable (plan 01; items are `ResolvedFile`: use `.path`, `.sheet`, `.kind`); otherwise, when `op == "input.file_input"` and `content.filePath`: one entry `{"path": content.filePath, "sheet": content.selected_sheet or None, "kind": content.file_type}`. (The fallback is the permanent behaviour for the single-file node; plan 01's multi-file nodes are covered by the first branch.)
- output files: `content.audit_output_files()` if callable (returns a list of `{"path","format","delimiter"}`; plan 06 may add it to its nodes); otherwise, when `op == "input.file_output"` and `content.filePath`: `{"path": content.filePath, "format": content.file_format, "delimiter": content.delimiter}`.

`node_specs_from_window`: edges from `scene.edges` (`edge.start_socket.node.id`, `edge.start_socket.index`, `edge.end_socket.node.id`, `edge.end_socket.index`); only edges whose both ends are in `sorted_nodes`. Socket index attribute: `Socket.index` (vendored `node_socket.py`; verify with grep before use and use the attribute that returns the 0-based position).

2. Mixin edits (`workflow_execution_mixin.py`): add `self._run_session = None` in `init_workflow_execution`; add class attr `runRecorded = None` (same pattern as `executionResultsChanged`, line 19); insert the H1-H4 calls from 3.7 and 3.7a. **Cancellation:** `request_run_cancel()` is **provided by plan 09 F-D** (worker `request_cancel()`, `executor.cancel_execution()`, `session.request_cancel()` on `self._run_session`, then the `add_cancel_listener` callbacks); this plan adds **no** `request_run_cancel` and no edit to it. `RunSession.request_cancel` sets the recorder cancel event and `self._cancelled = True`, and `finish` passes `cancelled=self._cancelled`. The GUI's `cancelled` status therefore comes from the session flag, never inferred from the worker. The attribute name `_run_session` set here is the one F-D reads.
3. `design_window.py`: add `runRecorded = Signal(str)` next to line 83.
4. (`workflow_uuid` and the save changes are plan 09 F-F - no edit here.)
5. `qt/preferences.py`: the 3.14 `DEFAULTS` keys.

Done when:
```powershell
.venv\Scripts\python.exe -m pytest tests\unit\test_audit_bridge.py tests\unit\test_workflow_execution_mixin.py tests\unit\test_workflow_serialization.py tests\unit\test_preferences.py -q
.venv\Scripts\python.exe -m pytest tests\e2e\test_audit_run_record.py -q
```

### Step 7 - export and compare (core)

Create `compare.py`, `view.py`, `export.py` per 3.9, 3.15, 3.16.

`view.py`:
```python
def format_duration(seconds: float) -> str: ...      # "12 ms", "0.9 s", "2 min 05 s"
def run_summary_rows(rec: dict) -> list[tuple[str, str]]: ...   # label, value (the Summary pane)
def node_table_rows(rec: dict) -> list[dict]: ...              # keys: node, op, status, rows_in, rows_out, columns, duration, error
```
`rows_in` display = sum of the sockets' rows (`"3"` or `"3 + 5"` for two sockets, `"-"` when null). Error cell = `error.title` or `""`.

Done when: `pytest tests\unit\test_audit_compare.py tests\unit\test_audit_export.py tests\unit\test_audit_view.py -q`.

### Step 8 - Run History dock

Create `qt/helpers/audit_tasks.py`, `qt/models/run_history_models.py`, `qt/docks/run_history_dock.py`, the SVG + `resources.json` entry (3.15), wiring edits (3.15 last bullet), and the Audit group in the preferences dialog (3.14).

`audit_tasks.py`:
```python
class _Signals(QObject):
    done = Signal(object)        # result
    failed = Signal(str)
class AuditTask(QRunnable):
    def __init__(self, fn, *args): ...      # fn(cancel_event, *args) -> result
    def cancel(self) -> None: ...           # sets the threading.Event
    def run(self) -> None: ...              # try: done.emit(fn(...)) except Exception as e: failed.emit(f"{type(e).__name__}: {e}")
```
Keep a strong reference to each task and its signals object in the dock (`self._tasks`) until `done/failed` (PyQt deletes unreferenced QObjects).

Dock public API (tests use it): `RunHistoryDock.switch_to_design_window(window)`, `.remove_design_window(window_id)`, `.reload()`, `.run_table` (QTableView), `.node_table`, `.diff_table`, `.status_label`, `.btn_verify`, `.btn_compare`, `.btn_export_json`, `.btn_export_html`, `.btn_check_inputs`, `.btn_refresh`, `.btn_folder`, `.verify_finished` (`Signal(object)`, emits the `VerifyReport`; tests wait on it), `.select_run(run_id)`.

Dialogs go through module-level names (`QMessageBox`, `QFileDialog`) so tests can monkeypatch them (the `no_modal_dialogs` fixture does this for `design_window`; the dock tests patch their own module).

Done when: `pytest tests\ui\test_run_history_dock.py -q`; and a manual smoke from 8.5.

### Step 9 - golden fixtures, e2e, perf, docs

Add `tests/e2e/fixtures/audit/orders.csv` (exact bytes below), `.gitattributes` line, `tests/support/audit_helpers.py`, the e2e/perf tests (section 6), and a row in `docs/NODE_REFERENCE.md`? No node is added - skip. Add `docs/AUDIT_TRAIL.md`? Not created by this plan (docs are plan-external); the format is documented by 3.3 of this file.

Done when: all commands in section 8 pass.

---

## 5. Edge cases (decided behaviour)

| Case | Behaviour | Test |
|---|---|---|
| **Cancelled run** | `request_run_cancel()` sets the worker flag, the recorder event and the executor flag. Hashing stops at the next chunk (`sha256_status="cancelled"`). The node being executed finishes (exec cannot be interrupted, brief fact 4). `finish(..., cancelled=True)` -> `status:"cancelled"`, unrun nodes `skipped`. The record is still sealed. | `test_cancelled_run_is_recorded_with_skipped_nodes` |
| **Failed node** | Node `status:"failed"` with `error` dict; later nodes `skipped`; run `status:"failed"`; outputs of earlier nodes are fingerprinted; the failed output node gets a stat-only fingerprint flagged partial. | `test_failed_node_record_has_error_and_skipped_followers` |
| **Timeout** (`ExecutionTimeoutError`) | Failed node, `error` via `translate_exception` (plan 03 maps it to `TD-RUN-001`); the abandoned exec thread may still write; the output file is stat-only (not hashed) with the partial flag. | unit via stubbed result |
| **Memory limit** | Same as failure (`TD-RUN-002`). | unit via stubbed result |
| **Missing input file** | `before_node` fingerprints `sha256_status:"missing"`; the node's own code produces the failure (File Input fallback `pl.DataFrame()` or a scan error). Run record still sealed. | `test_missing_input_is_recorded_as_missing` |
| **Locked / unreadable file** (`PermissionError` while hashing) | `sha256_status:"error"`, `error:"PermissionError: ..."`, run warning `input not hashed (error): <path>`. The run continues. | `test_unreadable_input_is_flagged_not_fatal` (monkeypatch `open`) |
| **Huge file hashing** | Streams 8 MiB chunks; above `audit/hash_max_mb` -> `skipped_size_limit`; cached by `(path,size,mtime_ns)` so the second run is instant (`cached`); cancel works between chunks. | `test_size_limit_skips_hash`, `test_cache_hit_avoids_rehash`, `test_hash_is_cancellable` |
| **Unsaved workflow** | `workflow_path=None`, `workflow_sha256=None`; `graph_sha256` set; store = `<app_data>/runs/_unsaved`. | `test_unsaved_workflow_uses_graph_hash_and_unsaved_store` |
| **Modified-but-saved workflow** | `workflow_modified_since_save=true`; both hashes recorded. A yellow note in the Summary pane: "Workflow had unsaved changes". | summary row unit test |
| **Read-only workflow folder** | Fallback store in app data + run warning (3.11). | `test_readonly_folder_falls_back` (monkeypatch `os.makedirs` to raise) |
| **Clock skew** (system clock moves backwards between runs) | Durations use `perf_counter`; wall timestamps are informational. `verify` adds warning `clock_skew` when a run starts before the previous one finished. Chain order is by `seq`, never by time. | `test_verify_warns_on_clock_skew` |
| **Two app instances** | The `.lock` file serialises sealing; each instance's `prev_record_hash` is read under the lock, so the chain stays linear; `seq` stays gap-free. A lock that is held > 10 s -> fallback folder. A crashed holder -> stale after 60 s. | `test_two_threads_seal_without_forking_the_chain` |
| **Tampered record** (field edited) | `verify` -> `record_hash_mismatch` for that run. | `test_verify_detects_edited_field` |
| **Record deleted** | `missing_record`. | `test_verify_detects_deleted_record` |
| **Record replaced by another valid record** | `index_mismatch` / `prev_hash_mismatch`. | `test_verify_detects_swapped_records` |
| **Index line removed** | `seq_gap` and an `orphan_record` warning. | `test_verify_detects_removed_index_line` |
| **Tail truncation** (last run deleted incl. its index line) | Not detectable by design (documented limitation; Verify shows `head_hash`). | documented in non-goals; no test |
| **Corrupt JSON record** | `unreadable`; the dock still lists the run (from the index) with Chain = "unreadable". | `test_verify_reports_unreadable_record` |
| **Corrupt/partial index last line** (crash during append) | Ignored with warning `index_truncated_line`; next commit continues from the last complete line. | `test_partial_last_index_line_is_tolerated` |
| **Crash between record write and index append** | Orphan record with a valid hash; warning `orphan_record`; next sealed run links to the index head, not to the orphan. | `test_orphan_record_is_warned_not_fatal` |
| **App crash mid-run** | `<run_id>.started` marker remains; Verify warns `incomplete_run`; nothing is chained. | `test_incomplete_run_marker_is_reported` |
| **Node without output** (File Output, sinks) | `rows_out: {}`, `columns_out: {}`; `rows_in` filled. | covered by the golden e2e |
| **Multiple outputs** (Split, Filter) | One entry per variable in `rows_out`; `rows_in` of a downstream node resolves `from_socket` -> variable by index. Brief 3.3 warns that `getSocketValue` is first-match; the recorder uses the **edge's real socket index**, so it is correct even where the live path is not. | `test_split_two_outputs_have_two_counts` |
| **Same node in many runs** | Matched by `node_id` (stable across save/load); `compare_runs` uses it. A re-created node gets a new id -> shows as removed + added (`node_set`). | `test_compare_matches_nodes_by_id` |
| **Graph without sink** | Mode `all`/`sink` still counts (sources; or everything in `all`); outputs empty; no warning. Mode `all` additionally surfaces a broken plan as a node warning (3.5). | `test_graph_without_sink_still_counts_in_all_mode` |
| **Count failure** | Warning on the node, `rows_out` null; run outcome unchanged. | `test_count_failure_never_fails_the_run` |
| **Audit disabled** (`audit/record_runs` false) | No session, no files, no hooks installed, zero overhead. | `test_recording_off_writes_nothing` |
| **Recorder exception** (any bug) | Caught in the bridge/mixin; logged; the Run is unaffected. | `test_recorder_bug_does_not_break_run` |
| **Excel input** | Hashed as a file; `row_count_method` "materialized" for the node variable (frame is eager inside `.lazy()`); sheet recorded. | unit (fingerprint with sheet) |
| **Non-ASCII paths / settings** | Canonical JSON keeps UTF-8; hash stable. | `test_canonical_json_non_ascii` |
| **Very large record** | `generated_code` > 1 MiB is dropped (hash kept); columns capped at 500. | `test_generated_code_over_cap_is_dropped_but_hashed` |
| **Same file used by two input nodes** | Two fingerprints (different `node_id`), the second a cache hit. | in `test_cache_hit_avoids_rehash` |

---

## 6. Test plan

Conventions (brief 9): layer markers come from the directory; no sleeping, use `qtbot.waitSignal`; every test that
builds a workflow uses `tmp_path`; the autouse `TRIGGER_DESIGNER_DATA_DIR` temp dir keeps the fallback store out of the user profile;
`no_modal_dialogs` for anything that runs a window. Shared helper `tests/support/audit_helpers.py` provides:

```python
def build_workflow(tmp_path, rows=3, *, input_name="orders.csv", via_fixture=True) -> tuple[Path, Path, Path]:
    """File Input -> Normalize -> File Output, saved as tmp_path/'wf.tds'. Returns (tds, input_csv, output_csv).
    Follows the programmatic builder in brief 9.4 (_build_tds). If via_fixture, copies
    tests/e2e/fixtures/audit/orders.csv to tmp_path/input_name; else generates `rows` rows."""

def run_and_load_record(qtbot, tds) -> tuple[TriggerSubWindow, dict]:
    """Opens tds in a TriggerSubWindow, run_workflow_and_wait, returns (window, raw record dict
    read from the newest file in <tds>.runs via orjson)."""

def store_dir_of(tds: Path) -> Path:   # tds.with_suffix(".runs")
```

### 6.1 Unit tests (`tests/unit/`, no Qt widgets)

1. `test_audit_canonical.py`
   - `test_known_vector`: `sha256_hex(canonical_json({"b":2,"a":1})) == "43258cff783fe7036d8a43033f830adfc60ec037382473548ac742b888292777"`.
   - `test_key_order_and_whitespace_irrelevant`: two dicts with different insertion order -> equal bytes; no spaces in output.
   - `test_canonical_json_non_ascii`: `canonical_json({"b":1,"a":[1.5,None,"é"]}) == b'{"a":[1.5,null,"\xc3\xa9"],"b":1}'`.
   - `test_rejects_non_json_types`: `pytest.raises(TypeError)` for `set()`, `Path`, `datetime`; int `2**63` raises.
   - `test_record_hash_excludes_record_hash_field`: changing `record_hash` does not change `compute_record_hash`; changing `prev_record_hash` does.
   - `test_utc_now_iso_shape`: regex `^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{6}Z$`.
2. `test_audit_schema.py`
   - `test_example_record_validates`: a fixture dict (the 3.2 example completed with 64-hex hashes) -> `validate_record_dict(d) == []`.
   - `test_missing_required_key_reported`: delete `nodes` -> message names `nodes`.
   - `test_bad_status_enum`, `test_bad_hash_length`, `test_future_schema_version_rejected` (`schema_version=2` -> message).
   - `test_roundtrip_to_dict_from_dict`: `RunRecord.from_dict(r.to_dict()).to_dict() == r.to_dict()`.
   - `test_from_dict_ignores_unknown_keys_but_raw_hash_still_covers_them`: add key `x_future`; `from_dict` ok; `compute_record_hash(raw)` changes when `x_future` changes.
   - `test_to_dict_field_set_matches_spec`: the key set of `RunRecord(...).to_dict()` equals the run-level keys of 3.3 (guards drift between docs and code).
3. `test_audit_store.py` (hash chain)
   - `test_first_record_links_to_genesis`: `prev_record_hash == "0"*64`, `seq == 1`.
   - `test_chain_links_and_seq_increment` (3 saves): `r2.prev_record_hash == r1.record_hash`, seq 1,2,3.
   - `test_verify_ok_on_clean_store`: `report.ok`, `checked == 3`, `head_hash == r3.record_hash`.
   - `test_verify_detects_edited_field`: edit `status` in run 2's file (rewrite JSON) -> problem `record_hash_mismatch` for run 2 only (**one** problem, later records not flagged).
   - `test_verify_detects_deleted_record`, `test_verify_detects_swapped_records`, `test_verify_detects_removed_index_line`, `test_verify_reports_unreadable_record`, `test_partial_last_index_line_is_tolerated`, `test_orphan_record_is_warned_not_fatal`, `test_incomplete_run_marker_is_reported`, `test_verify_warns_on_clock_skew`.
   - `test_verify_record_file_standalone`: exported copy verifies; edited copy fails.
   - `test_record_file_is_pretty_and_hash_matches_canonical`: file text contains newlines; hash recomputed from `orjson.loads` equals stored.
   - `test_record_file_is_read_only`: assert `not os.access(path, os.W_OK)`; decorate `@pytest.mark.xfail(strict=False, reason="elevated users can write read-only files")` so an admin shell does not fail the suite.
   - `test_two_threads_seal_without_forking_the_chain`: 8 threads x 5 saves into one dir -> `verify` ok, `seq` 1..40 unique, each `prev` equals the previous in seq order.
   - `test_stale_lock_is_removed`: pre-create `.lock` with mtime 120 s ago -> save succeeds.
   - `test_lock_timeout_falls_back` (monkeypatch timeout to 0.2 s, hold the lock in the test) -> record in fallback dir + warning.
   - `test_resolve_store_dir_cases`: the five rows of 3.11, with expected paths (compute `sha1` suffix in the test).
   - `test_readonly_folder_falls_back` (monkeypatch `os.makedirs`).
   - `test_list_runs_reads_index_only` (delete a record file; `list_runs` still lists it).
4. `test_audit_fingerprint.py`
   - `test_sha256_matches_hashlib_for_multi_chunk_file`: 20 MiB random bytes (`random.Random(1).randbytes`), chunk 1 MiB -> equals `hashlib.sha256(data)`.
   - `test_empty_file_hash`: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
   - `test_hash_is_cancellable`: set the event before the call -> `None`, status `cancelled`; set it from another thread mid-way (`chunk=4096` on a 5 MB file with a `threading.Timer`) -> `None`.
   - `test_cache_hit_avoids_rehash`: first call `computed`; monkeypatch `sha256_stream` to raise; second call (same size/mtime) -> `cached` and same digest; after `os.utime` change -> recomputed (the monkeypatched raise is expected: assert via a counter instead, using a wrapper).
   - `test_cache_persists_and_corrupt_cache_is_ignored`.
   - `test_size_limit_skips_hash`, `test_missing_file_status`, `test_disabled_status`, `test_permission_error_status`.
   - `test_count_rows_in_file`: parametrized for csv (with a quoted embedded newline -> counts 2 rows, not 3), custom delimiter `;`, parquet, ipc, ndjson, json, excel (only if `openpyxl` imports; the test writes the file with openpyxl); unreadable -> `None`.
5. `test_audit_counting.py`
   - `test_decide_mode_table`: all 4 requested x (below/above threshold) combinations; boundary `==` is "all".
   - `test_count_all_materialises_once`: a LazyFrame with `map_batches` side-effect counter -> after `count_frame(..., "all")` and two further `.collect()` of the returned frame the counter is 1 (proves collect-once-and-reuse).
   - `test_count_sink_mode_only_counts_sources`; `test_count_off_returns_none`; `test_eager_frame_counts_height`; `test_schema_of_caps_columns_at_500`.
   - `test_count_failure_raises_counterror` (plan with a bad column).
6. `test_audit_recorder.py` (recorder with fakes; no Qt)
   - `FakeNode(id)` + `FakeResult(success, execution_time, ...)` dataclasses in the test.
   - `test_begin_computes_hashes_and_mode`: workflow file bytes hash equals `hashlib`; `graph_sha256` identical for two begins with reordered nodes/edges lists (order-insensitive), different when a setting changes.
   - `test_node_record_rows_in_derived_from_edges`: A -> B; after A's `after_node` count 3, `node_finished(B)` has `rows_in[0].rows == 3` and `from_socket` honoured for a 2-output node A (socket 1 -> variable 2).
   - `test_finish_marks_unrun_nodes_skipped`, `test_cancelled_status`, `test_row_count_mismatch_warning`, `test_identity_off_nulls_user_and_machine`, `test_embed_code_off_keeps_hash`, `test_generated_code_over_cap_is_dropped_but_hashed`, `test_baseline_input_changes` (two runs, input file edited between), `test_count_failure_never_fails_the_run`, `test_warnings_capped`.
   - `test_seed_extraction`: `{"random_seed": 42, "is_random": True}` -> 42; `is_random False` -> None; `{"seed": 7}` -> 7; none -> None.
   - `test_sanitize_settings`: sets, Path, datetime, NaN, deep nesting, long strings.
7. `test_audit_compare.py`
   - `test_identical_runs_have_no_items`.
   - `test_input_hash_change`, `test_parameter_change_path` (`settings.delimiter`), `test_row_count_change`, `test_status_change`, `test_node_added_removed`, `test_environment_change`, `test_output_hash_change`, `test_compare_matches_nodes_by_id`.
   - `test_check_inputs_states`: unchanged / modified (edited file) / missing / skipped (recorded sha null).
8. `test_audit_export.py`
   - `test_html_escapes_everything`: a node title `<script>alert(1)</script>` and an error technical text containing `</script>` never appear unescaped in the output; embedded JSON contains `<\/`.
   - `test_html_contains_hashes_and_nodes`; `test_html_is_self_contained` (no `http://`, `https://`, `src=` beyond data URIs).
   - `test_export_json_is_byte_identical` and `verify_record_file` passes on it.
9. `test_audit_view.py`: `format_duration` table; `run_summary_rows` includes the "unsaved changes" row when `workflow_modified_since_save` is true; `node_table_rows` for skipped/failed/ok.
10. `test_executor_hooks.py` (verifies the plan 09 F-B contract with this plan's bodies): `before_node` and `after_node` called in order for a trivial node (use a stub node with `get_code` returning `"x = 1\n"` and `content=None`); `after_node` may replace `local_variables["x"]` and the replacement reaches `execution_context` and `result.variables`; a raising hook does not fail the node; failure path does not call `after_node`; `result.started_at <= result.finished_at` and both match the timestamp regex; `result.code` equals the code; hooks default to None.
11. `test_audit_bridge.py` (needs a `TriggerSubWindow`, pattern brief 9.2): `options_from_preferences` default values and unknown `row_counts` -> `"auto"`; `snapshot_settings` of a File Input uses `get_serialized_state` and **does not re-read the file** (monkeypatch `pl.read_csv`/`pl.scan_csv` to raise; settings still returned); drops `schema_snapshot`; Split settings contain `random_seed`; `node_spec_from_node` of File Input/Output sets `is_source`, `input_files`, `output_files`; `node_specs_from_window` edges carry the correct socket indexes for a Split (`E` and `V` -> two different `from_socket`s).
12. `test_audit_api_contract.py` (new): `finish(..., outputs=[fp])` replaces the recorder's outputs; `finish(..., save=False)` and `AuditOptions(enabled=False)` write no file and do not create the store dir; a second `finish`/`save` for one record raises `RunAlreadySealed`; `begin` returns `status == "running"` and the sealed status comes only from `finish`; `AuditOptions(store_dir=tmp)` is honoured; `snapshot()` is an independent deep copy (mutating it does not change the recorder; taken while a worker thread calls `after_node` it never raises); `set_run_record_provider`/`get_run_record_provider` round trip; `update_node_error` after `finish` raises.
13. `test_audit_errors.py` (new): the stored `error` of a failed node equals `NodeError.to_dict()` with list-typed `columns` and passes `canonical_json`; a tuple input is converted; the fallback dict (plan 03 absent) has the same keys as `NodeError.to_dict()` (compare with `dataclasses.fields(NodeError)` when importable, else skip).
14. `test_audit_lazy_init.py` (new): in a subprocess (`sys.executable -I -c`), `import trigger_designer.core.audit` leaves `trigger_designer.core.audit.recorder`, `polars` and `qtpy` out of `sys.modules`; accessing `trigger_designer.core.audit.RunRecorder` imports only `recorder` and its dependencies; an unknown attribute raises `AttributeError`.

### 6.2 Integration tests (`tests/unit/test_audit_integration.py`: real executor, real nodes, no window event loop)

Pattern: build nodes in a `TriggerSubWindow` as in brief 9.2, wire with `Edge`, create `RunRecorder(RunStore(app_data_dir=tmp_path), AuditOptions(...))`, then drive the loop synchronously exactly like `WorkflowWorker.run` does: for each node in `window.topologicalSort(window.getNodeConnections())`: `executor.execute_node(node)` then `recorder.node_finished(record, node, result)`; finally `recorder.finish(record, success)`. (`WorkflowWorker.run()` can be called directly, brief 9.5, with the mixin signals unconnected - use the explicit loop to keep it readable.)

1. `test_ok_run_has_counts_in_all_mode`: File Input (3-row CSV, `orders.csv` fixture) -> Normalize -> File Output. Assert `rows_out` 3/3, `rows_in` 3, `inputs[0].sha256 == aac441b2...d5c9`, `outputs[0].sha256 == inputs[0].sha256` (byte-identical pass-through), `outputs[0].row_count == 3`, run status ok, `verify_store` ok.
2. `test_sink_mode_counts_source_and_output_only`: same with `row_counts="sink"`: Normalize `rows_out` is `None`, count_method `none`; File Input 3 (`scan_plan`); output file 3; File Output `rows_in[0].rows == 3` (filled from the file).
3. `test_off_mode_has_no_counts_but_has_hashes`.
4. `test_failed_node_record_has_error_and_skipped_followers`: a File Input pointing at a nonexistent path wired to File Output (File Output raises `ValueError` when its input is unwired; here wired, so instead use a Formula/Filter with a bad column). Simplest deterministic failure: `FileOutput` with `filePath` in a directory that does not exist (`tmp_path/"nope"/"x.csv"`) -> sink raises -> node failed, output fingerprint `error` contains "partial" or file missing; a downstream node (second File Output) `skipped`; `error["code"]` startswith `TD-`; `error["technical"]` non-empty.
5. `test_missing_input_is_recorded_as_missing`.
6. `test_split_two_outputs_have_two_counts`: File Input (10 rows generated, `rows=10`) -> Split (75/25, seed 42) -> two File Outputs; assert `rows_out` of Split has two entries summing to 10 and `seed == 42`; the second File Output's `rows_in[0].from_socket == 1`.
7. `test_graph_without_sink_still_counts_in_all_mode`: File Input -> Normalize only; counts present; `outputs == []`.
8. `test_count_failure_never_fails_the_run`: monkeypatch `counting.count_frame` to raise `CountError`; run status stays ok; node warnings contain "row count skipped".
9. `test_second_run_uses_cached_hash_and_chain_links`: run twice; record 2 `inputs[0].sha256_status == "cached"`, `prev_record_hash == record1.record_hash`, `baseline.run_id == record1.run_id`, `baseline.input_changes == []`.
10. `test_input_change_between_runs_populates_baseline`: edit the CSV between runs -> `input_changes[0].change == "modified"`, new and old shas differ.
11. `test_recording_off_writes_nothing` (via `RunSession.start` returning None when the preference is False; asserts `<wf>.runs` does not exist).

### 6.3 E2E golden-file tests (`tests/e2e/test_audit_run_record.py`; real window, real `WorkflowWorker` thread)

Fixtures (exact bytes; commit with `.gitattributes` entry `tests/e2e/fixtures/audit/*.csv -text`):

`tests/e2e/fixtures/audit/orders.csv` - exactly 25 bytes, LF line endings, trailing newline:
```
id,amount
1,10
2,20
3,30
```
SHA-256 of those bytes: `aac441b2f011b33ba88a30f384ec388988fff9d248e7620cc73007e74720d5c9`. (Computed on 2026-10-21; the File Input reads all columns as strings, brief 7.1; polars `sink_csv` writes the same bytes back, so the output hash equals the input hash.)

`tests/e2e/fixtures/audit/orders_messy.csv` (header with spaces, to make Normalize change the output):
```
 Order ID ,Customer Id
1,a
2,b
```
Expected output golden `tests/e2e/fixtures/audit/orders_messy.expected.csv` (generated once by running the test with `TRIGGER_UPDATE_E2E_GOLDENS=1`'s sibling mechanism: the test **computes** the expected hash from this checked-in file, so no literal hash is hard-coded for it):
```
Order_ID,Customer_Id
1,a
2,b
```
(Normalize behaviour verified by the brief's example 9.4: columns `Order_ID`, `Customer_Id`.)

Tests:
1. `test_pass_through_run_record_matches_golden_values` - build workflow via `build_workflow(tmp_path, via_fixture=True)`, `window.fileLoad`, `run_workflow_and_wait`, read the newest record with `orjson`. Assert exactly:
   - `rec["status"] == "ok"`; `len(rec["nodes"]) == 3`; node ops in order `["input.file_input","preparation.normalize_columns","input.file_output"]`;
   - `rec["nodes"][0]["rows_out"]` has one value `3`; `rows_in` of nodes 1 and 2 `rows == 3`;
   - `rec["inputs"][0]["sha256"] == "aac441b2f011b33ba88a30f384ec388988fff9d248e7620cc73007e74720d5c9"`, `size_bytes == 25`, `row_count == 3`;
   - `rec["outputs"][0]["sha256"]` equals the same value, `row_count == 3`, `row_count_method == "output_file"`;
   - `rec["workflow_sha256"] == hashlib.sha256(tds.read_bytes()).hexdigest()`;
   - `rec["prev_record_hash"] == "0"*64`, `rec["seq"] == 1`, `compute_record_hash(rec) == rec["record_hash"]`;
   - `verify_store(store_dir).ok`;
   - `rec["generated_code"]` contains `"sink_csv"`.
2. `test_messy_header_output_hash_matches_golden_file` - uses `orders_messy.csv`; `rec["outputs"][0]["sha256"] == sha256(orders_messy.expected.csv bytes)`; `columns_out` of the Normalize node `== ["Order_ID","Customer_Id"]`; `dtypes_out` all `"String"`.
3. `test_two_runs_chain_and_baseline` - run twice via `run_workflow_and_wait`; two files + two index lines; record 2 links to record 1; `baseline.input_changes == []`; verify ok; `RunDiff` of the two records has **only** timestamp-independent items: `compare_runs(r1, r2).identical` is True (`started_at`, durations, run ids are not compared).
4. `test_determinism_same_inputs_twice_identical_counts_and_output_hashes` - 1,000-row generated CSV (`rows=1000`, values `i,i*2`), seeded Split (seed 42, random mode) -> two outputs; run twice; assert for every node `rows_out` equal, for every output `sha256` equal and `row_count` equal, `graph_sha256` equal, `nodes[*].code_sha256` equal. (Split uses `shuffle(seed=...)` so output is deterministic, `split.py:183-190`.)
5. `test_recorded_run_survives_save_as_and_reload` - move `wf.tds` and `wf.runs` to a new folder; `RunStore().list_runs(workflow_path=new)` returns the runs; `verify` ok (records contain old absolute paths; chain unaffected).
6. `test_run_log_dir_preference_relocates_store` - set `audit/run_log_dir`; the record lands in `<dir>/wf-<hash8>/`.
7. `test_unsaved_workflow_run` - build in memory without saving: record in `<TRIGGER_DESIGNER_DATA_DIR>/runs/_unsaved`, `workflow_path is None`, `graph_sha256` non-empty.
8. `test_failed_run_record_has_error_and_status` - output directory does not exist; wait on `runRecorded`; `rec["status"] == "failed"`; the File Output node `status == "failed"`, `error` dict with non-empty `code`, `title`, `technical`; when plan 03 is merged assert `rec["nodes"][-1]["error"] == window.problems_store.error_for(node_id).to_dict()` (sealed only after `settled`). Variant `test_failed_run_seals_after_settle_timeout`: monkeypatch the guard to 50 ms and a `problems_store` whose `settled` never fires -> the record is still sealed, with the un-enriched error.
9. `test_record_written_before_results_changed_signal` - inside `run_workflow_and_wait` the record file exists on return (guards the H4 ordering).
10. `test_run_signal_emitted`: `window.runRecorded` emits the saved path (`qtbot.waitSignal`).

### 6.4 UI tests (`tests/ui/test_run_history_dock.py`)

Harness: `TriggerWindow()`, `window.show()`, `window.onFileNew()` pattern (`tests/ui/test_data_preview_wiring.py:21-40`); `no_modal_dialogs`; patch `run_history_dock.QMessageBox`, `QFileDialog`, `QDesktopServices` with recorders. Seed a store by calling `RunStore.save` on synthetic records (helper `make_record(run_id, status, ...)` in `tests/support/audit_helpers.py`), then `dock.switch_to_design_window(sub)` where `sub.filename` is a tmp `.tds` path.
1. `test_dock_registered_and_tabified`: `window.runHistoryDock.objectName() == "RunHistoryDock"`, in the bottom area, `toggleViewAction` text `"Run History"`, present in the Window menu.
2. `test_lists_runs_newest_first`: 3 records -> model rows 3, order seq 3,2,1; status column text.
3. `test_empty_state_when_no_runs`: `EmptyStateLabel` visible, tables hidden.
4. `test_selecting_run_fills_summary_and_node_table`: summary rows contain run id, workflow; node table row count equals nodes; failed node row shows `error.title`.
5. `test_every_toolbar_button_has_tooltip_and_accessible_name_and_no_text`: loop `findChildren(IconButton)`: `toolTip()`, `accessibleName()` non-empty, `text() == ""`, size 30x30 (AGENTS.md rules).
6. `test_verify_button_reports_ok_and_tamper`: click verify -> wait `verify_finished` -> status strip contains `"verified"`; edit a record file; click again -> a problem is shown via the patched `QMessageBox` (assert the text contains `record_hash_mismatch` and the run's seq); the run row's Chain cell becomes "failed".
7. `test_compare_enabled_only_for_two_selected`: 1 selected -> disabled; 2 -> enabled; toggling shows `diff_table` with the expected rows (input hash change between two synthetic records).
8. `test_export_json_writes_byte_identical_copy` and `test_export_html_writes_file_and_opens_it` (the patched `QFileDialog.getSaveFileName` returns a tmp path; `QDesktopServices.openUrl` recorded).
9. `test_check_inputs_flags_modified_input`: synthetic record with the sha of a tmp CSV; edit the CSV; click -> dialog text lists the path with `modified`.
10. `test_new_run_signal_refreshes_and_selects`: emit `sub.runRecorded(path)` after saving a record -> list grows, new run selected.
11. `test_theme_change_does_not_raise`: `dock.apply_theme()`.
12. `test_no_inline_stylesheet`: no widget in the dock has a non-empty `styleSheet()` (AGENTS.md rule).
13. `test_default_layout_tab_order`: `apply_default_layout(window)` -> with a stub `problemsDock` attribute present the tab order (by `QTabBar` text) is Problems, Run History, Logs, Data Preview; without it Run History, Logs, Data Preview. Also `test_run_cancel_marks_cancelled_from_session_flag`: call `window.request_run_cancel()` during a run (slow node stub) -> record `status == "cancelled"` even if the worker reports success.
14. `test_preferences_dialog_has_audit_group` (in `tests/ui/test_preferences_audit.py`): changing the row-count combo writes `audit/row_counts`.

Expected baseline: the 27 pre-existing ui failures (brief 2.4) are unchanged; these new tests must all pass.

### 6.5 Performance test (`tests/benchmarks/test_audit_overhead.py`, marked `benchmark`, run with `--run-benchmarks`)

- Generate once per session in `tmp_path_factory`: a 1,000,000-row CSV, 6 columns (`id` int, `amount` float, 3 text columns of 8 chars from a seeded `numpy` RNG, `date` string) - about 70 MB, below the 256 MB threshold so `auto` resolves to `all`.
- Workflow built programmatically: File Input -> Normalize -> Select(all) -> Sort(by id) -> Unique(by id) -> File Output (parquet). (`Sort`/`Unique` force real work.)
- Measure with `time.perf_counter()` around `run_workflow_and_wait`, **median of 3 runs** per configuration after one warm-up run (warm-up primes the OS file cache and imports):
  - baseline: `audit/record_runs=False`;
  - `off`, `sink`, `all`.
- Assertions: `t_off <= 1.05 * t_base + 0.05`; `t_sink <= 1.05 * t_base + 0.10` (the +0.05/0.10 s absorb timer noise on a ~1 s run); `t_all <= 1.25 * t_base + 0.5`. Print the table (`-s`) so a failing budget is diagnosable.
- Also assert `rows_out` of the Unique node equals `1_000_000` (ids are unique) in `all` mode, proving counts were taken in the measured run.
- `test_hashing_throughput_floor`: hashing a 200 MB temp file with the 8 MiB chunk takes < 5 s (a regression guard, not a benchmark claim).

### 6.6 Negative / adversarial tests (collected under 6.1-6.4; listed so none is forgotten)

- Tamper: edit one byte of a record / delete / swap / truncate index mid-file -> verify fails with the specific `kind` (6.1.3).
- A record file whose pretty-printing differs (indentation changed, keys reordered) but whose content is unchanged **still verifies** (`test_verify_ignores_formatting_changes`).
- A record with an unknown extra key and a recomputed `record_hash` verifies; with a stale hash it fails.
- HTML injection (6.1.8).
- Recorder bug isolation: `test_recorder_bug_does_not_break_run` monkeypatches `RunRecorder.begin` to raise; the mixin logs and the run still completes (`executionResultsChanged` emitted, outputs written, no record).
- Hook raising inside `after_node` does not fail the node (6.1.10).
- Locked output file on Windows: open the output path with `open(path, "wb")` held by the test and run -> node fails; the record is sealed; the output fingerprint carries `error`.
- Run with the Run History dock closed/not created (headless `TriggerSubWindow` only, as in e2e): no AttributeError (the mixin never references the dock; the dock listens to the signal).

---

## 7. Acceptance checklist

- [ ] A normal Run writes `<workflow>.runs/<run_id>.json` and one line to `index.jsonl`; the record validates (`validate_record_dict == []`).
- [ ] All fields of 3.3 present; field set of `RunRecord.to_dict()` equals the table (test).
- [ ] Inputs and outputs have size, mtime, SHA-256, row counts; golden hash `aac441b2...d5c9` matches in the e2e test.
- [ ] Per-node `rows_in` per connected socket, `rows_out` per output variable, columns and dtypes, status, duration, `NodeError`.
- [ ] Row-count mechanism implements 3.5 (modes, threshold, failure handling) and the 6.5 budgets hold.
- [ ] Random seed recorded for Split; settings snapshot never re-reads input files.
- [ ] Hash chain: tamper, delete, swap, gap, truncated line, orphan, incomplete, clock skew all handled as in section 5; `verify_store` and the **Verify run log** button agree.
- [ ] Concurrent sealing keeps a linear chain (thread test).
- [ ] Run History dock: list, summary, node table, export HTML/JSON, compare two, check inputs; icon-only toolbar with tooltips and accessible names; no inline QSS; registered in menu/layout/theme.
- [ ] Preferences (3.14) exist, are in `DEFAULTS`, and appear in the dialog.
- [ ] Recording off writes nothing and installs no hooks.
- [ ] The audit layer can never fail or change a run (bug-isolation tests).
- [ ] `core/audit` imports no Qt (`sys.modules` check test) and no `executor`.
- [ ] `ExecutionResult` fields and executor hook stubs come from plan 09 F-B (no edit to `executor.py` here); existing unit tests unchanged and green.
- [ ] API contract for plans 08/06 (6.1 #12): `finish(outputs=, save=)`, `AuditOptions(enabled=, store_dir=, sync_enrich=)`, `RunAlreadySealed`, `snapshot()`, `set_run_record_provider` at H1 and cleared at H4.
- [ ] Failed GUI runs seal only after `problems_store.settled` (or the 5 s guard); headless uses `sync_enrich`; saved errors are `NodeError.to_dict()` (3.7a, 3.8a).
- [ ] `core/audit/__init__.py` is lazy (6.1 #14).
- [ ] Default dock tab order Problems, Run History, Logs, Data Preview (6.4 #13).
- [ ] Cancelled GUI runs get `status:"cancelled"` from the session flag.
- [ ] `getSocketData`, `_prune_node_results`, `execution_results` shapes untouched (brief 10.1 invariant).
- [ ] `ruff format` + `ruff check` clean on every touched/new file (no new errors versus baseline).
- [ ] Baseline test counts: unit >= 334 + new, e2e >= 20 + new, ui failures still exactly the 27 pre-existing.

---

## 8. Verification commands

PowerShell, repo root. Never bare `pytest` (it aborts in this environment, brief 2.4).

```powershell
# 8.1 format + lint, only on files you touched / created
.venv\Scripts\python.exe -m ruff format src\trigger_designer\core\audit tests\unit\test_audit_canonical.py
.venv\Scripts\python.exe -m ruff check  src\trigger_designer\core\audit tests\unit\test_audit_canonical.py

# 8.2 core logic (fast, no Qt widgets)
.venv\Scripts\python.exe -m pytest tests\unit\test_audit_canonical.py tests\unit\test_audit_schema.py tests\unit\test_audit_store.py tests\unit\test_audit_fingerprint.py tests\unit\test_audit_counting.py tests\unit\test_audit_recorder.py tests\unit\test_audit_compare.py tests\unit\test_audit_export.py tests\unit\test_audit_view.py -q

# 8.3 executor / bridge / integration (needs a TriggerSubWindow)
.venv\Scripts\python.exe -m pytest tests\unit\test_executor_hooks.py tests\unit\test_audit_bridge.py tests\unit\test_audit_integration.py tests\unit\test_workflow_uuid.py tests\unit\test_execution_result.py tests\unit\test_workflow_execution_mixin.py tests\unit\test_workflow_serialization.py tests\unit\test_preferences.py -q

# 8.4 whole unit and e2e layers (expect >= 334 + new passed / >= 20 + new passed)
.venv\Scripts\python.exe -m pytest tests\unit -q
.venv\Scripts\python.exe -m pytest tests\e2e -q

# 8.5 ui: the new files only, then compare the layer against the baseline (404 pass / 20 fail / 7 error before this change)
.venv\Scripts\python.exe -m pytest tests\ui\test_run_history_dock.py tests\ui\test_preferences_audit.py -q
.venv\Scripts\python.exe -m pytest tests\ui -q

# 8.6 performance (opt-in)
.venv\Scripts\python.exe -m pytest tests\benchmarks\test_audit_overhead.py --run-benchmarks -s

# 8.7 no-Qt guard
.venv\Scripts\python.exe -c "import sys, trigger_designer.core.audit as a; assert not any(m.startswith('qtpy') or m.startswith('PyQt') for m in sys.modules), 'core.audit imported Qt'; print('ok')"

# 8.8 manual smoke (GUI)
$env:PYTHONIOENCODING="utf-8"
.venv\Scripts\python.exe -m trigger_designer "savedfiles\0. All Node- Test.tds"
#   Run -> Window > Run History -> row appears; Verify (icon) -> "chain verified"; Export HTML -> opens in the browser;
#   edit one byte in the .runs\<id>.json -> Verify reports record_hash_mismatch.
```

---

## 9. Pitfalls

1. **Do not call `node.content.serialize()` for File Input.** It re-reads the file (brief 7.1) and would make `begin` I/O-bound. Use `get_serialized_state()` (3.10).
2. **Never touch Qt objects in `before_node`/`after_node`.** They run on the worker thread. `NodeSpec` carries everything they need; `node.id` is the only attribute read.
3. **Mode `all` replaces variables in `local_variables`.** It must update `local_variables` *before* `execution_context.update(...)` and the executor must re-sync `result.variables` (plan 09 F-B guarantees this after `after_node` returns). Forget either and downstream nodes still read the lazy plan, or the Data Preview shows the stale one.
4. **Do not hash after `canonical_json` of a dataclass round trip.** Hash the raw parsed dict (3.4). A dataclass drops unknown keys and would "fix" a tampered record.
5. **Pre-round floats** before sealing; a re-dump of `0.1 + 0.2` style values must be byte-stable. Only `duration_s` (6 d.p.) and `peak_memory_mb` (3 d.p.) are floats.
6. **Pretty-printing the file is fine; the hash never sees it.** Never "optimise" by hashing the file bytes - editors reformat JSON.
7. **`prev_record_hash` is assigned under the lock at seal time**, not at `begin`. Two instances running at once would otherwise both link to the same predecessor.
8. **`.tds` hash is of the on-disk bytes**; `scene.has_been_modified` tells whether they match what ran. Do not use `isModified()` (stub).
9. **The brief's `getSocketValue` first-match bug does not affect the recorder** only because it uses real edge socket indexes. Do not "simplify" to `getSocketValue`.
10. **Windows read-only attribute:** `os.chmod(path, stat.S_IREAD)` makes later `os.replace` onto the same name fail - records are never rewritten, and the temp file is a different name; never reuse a `run_id`.
11. **`openpyxl` imports are lazy** (slow import, optional). Keep the import inside `count_rows_in_file`.
12. **`pl.scan_csv(...).select(pl.len())` with `infer_schema=False`** is the only safe count for CSV outputs written with quoted newlines; never count `\n`.
13. **`no_modal_dialogs` stubs `getPyFile` only**; it does not stub the recorder, so tests write `<wf>.runs` next to the temp `.tds`. That is intended; the autouse data dir keeps fallback stores out of the profile.
14. **`.gitattributes` `* text=auto`** would rewrite the CSV fixtures' line endings on Windows checkouts and break the golden hash. The `-text` entry is mandatory (step 9).
15. **Qt object lifetime:** keep `AuditTask` and its signals object referenced until completion; hold the `QThread` rule from brief 9.1 in tests.
16. **Do not log the record to Logging dock at INFO per node** (the dock holds 1000 entries). One line at the end only.
17. **Do not import `trigger_designer.main`** anywhere (brief 1.2) - the plan-08 CLI must be able to import `core.audit`.
18. **The executor's own `execution_history`** keeps `without_frames()` copies; the new `code` string is copied into each (up to 100 per run). That is acceptable (strings are shared, not duplicated), but do not add the frames.
19. **Do not mutate or re-seal records.** Status is set only in `finish`; error enrichment goes through `update_node_error` before `finish`; a second seal raises `RunAlreadySealed`.
20. **Dock tests run under the ui layer whose baseline has 27 failures**; compare by test id, not by totals, when judging a regression.

---

## 10. Interfaces consumed and provided

### 10.1 Consumed

| From | What | How used / fallback |
|---|---|---|
| 03 `core/errors.py` | `NodeError`, `translate_exception(exc, *, node=None, phase="run") -> NodeError` (never raises); `ExecutionResult.exception` / `traceback_text` | `errors_adapter.error_to_dict(result, node)`: `exc = getattr(result, "exception", None)`; unwrap `exc = getattr(exc, "original_exception", None) or exc`; `err = translate_exception(exc if exc is not None else result.error, node=node, phase="run")`; return `err.to_dict()` (never `dataclasses.asdict`: tuples) with `technical` truncated to 8000 chars. With `AuditOptions.sync_enrich` call plan 03's `enrich_error(err, node=node)` first. GUI failed runs: see 3.7a. If `import trigger_designer.core.errors` fails (plan 03 not merged), return `{"code":"TD-SYS-999","title":"The step failed","detail":"","hint":"","technical": str(result.error)[:8000], "exc_type": "", "severity":"error","node_id":...,"node_title":...,"op":...,"columns":[],"path":None}` - the same keys as plan 03's `NodeError.to_dict()` (`code, title, detail, hint, technical, exc_type, severity, node_id, node_title, op, columns, path`), so the schema is stable either way. |
| 01 `core/inputs.py` | `ResolvedFile(path, exists, kind, sheet, size_bytes, modified_time, sha256)`, `FileInputContent.resolved_input_files(*, hash=False)` | `node_spec_from_node` calls `resolved_input_files()` (hash false: the recorder does its own streamed, cancellable, cached hashing) and reads `.path`, `.sheet`, `.kind`. Fallback to `filePath` for the existing single-file node (3.8 bridge). |
| 04 `TestSummary` | dataclass in `core/audit/test_summary.py` (plan 04 creates this file) | Not imported by the recorder; read through `content.test_summary` and `dataclasses.asdict` (3.8). Stored under `nodes[].test_summary`. The dict shape is plan 04's; the schema validator only checks "object or null". |

### 10.2 Provided

| To | What |
|---|---|
| 04 | The slot `nodes[].test_summary`; the contract "set `content.test_summary` before `nodeFinished` is delivered (during `processInputs` or `after_execution`)". `after_execution` runs before `nodeFinished`, so a summary computed there is visible to `node_finished`. |
| 06 workpaper | `RunRecord.from_dict(RunStore().load_dict(path))`; stable fields in 3.3; `render_html` is **not** reused (workpaper has its own layout); `compare_runs` and `view.run_summary_rows`/`node_table_rows` are reusable for tables. `RunStore().list_runs(workpaper_dir_of_workflow)` to pick the latest run. |
| 08 CLI/headless | Qt-free `RunRecorder` + `RunStore` + `AuditOptions`; `audit_bridge.node_specs_from_window(window, sorted_nodes)` for the loaded window; the executor hooks (`executor.before_node = recorder.before_node`, `executor.after_node = recorder.after_node`); `recorder.request_cancel()` for `--timeout`; exit-code mapping uses `record.status` (`ok` -> 0, `failed` -> 1) and `record.last_path`/`recorder.last_path` for reporting. A CLI that has no Qt window can build `NodeSpec`/`EdgeRef` itself from the loaded `.tds` JSON (all fields are plain data). Headless runs set `AuditOptions.store_dir` to the CLI's `--record-dir`. |
| 01 | A request: when plan 01 adds multi-file inputs, `resolved_input_files()` must return one `ResolvedFile` per physical file; the recorder fingerprints each. |
| All | `TriggerSubWindow.runRecorded(str)`; lazy `core.audit` exports. (`workflow_uuid`, the `ExecutionResult` fields, `before_node`/`after_node`/`code_filter` and `request_run_cancel()` are plan 09 F-F / F-B / F-D; this plan consumes them.) |

### 10.3 Ordering and conflicts

- Implement after plan 09 (F-B, F-D, F-F), 03 core+integration and 01 core (brief 11.2). Plan 04 can start after Step 4 of this plan (the `test_summary` slot is frozen).
- Files touched that other plans also touch: `executor.py` (not edited here; plan 09 F-B owns it), `workflow_execution_mixin.py` (03: translate in `_on_node_finished`; 08: none), `main_window_ui_mixin.py`/`main_window.py`/`layout_state.py` (any new dock), `qt/preferences.py` `DEFAULTS` and `preferences_dialog.py` (06: `export/workpaper_dir`). Make each edit additive and rebase carefully; no edit in this plan reorders or removes existing lines.
