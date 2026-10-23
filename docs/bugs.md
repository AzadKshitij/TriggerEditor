# Trigger Designer - Bug and Defect Register

Verified 2026-10-21 against `main` @ `71b4041` (working tree has uncommitted edits, see BUG-027).
Environment: Windows 11, `.venv` Python 3.13, Polars 1.44.2, DuckDB 1.5.5, sqlglot 30.20.0, PyQt6 / Qt 6.8.1,
`nodeeditor-qtpy` 0.8.1 from PyPI (installed by `uv sync`, in `uv.lock`; BUG-007 was fixed on 2026-10-22 —
the measurements below were taken before that, against git `ee5e8fd` kept outside the lock).

**Method.** Every item below was re-checked by opening the file and, where feasible, reproducing it with a script,
a pytest-driven probe, or a test invocation. Nothing in the repo was modified except this file. Probe scripts live
in the session scratchpad (not in the repo); each bug quotes the exact code and the exact output observed, and the
repro snippets are self-contained enough to re-run. Status values:

* **Verified** - reproduced or proven by the exact code shown.
* **Partially verified** - code read and the key operation demonstrated, but not driven through the full GUI path.
* **Unverified** - claim from a document could not be reproduced, or is wrong (listed in "Claims not confirmed").

Severity: **Critical** = silent wrong result or data loss in normal use; **High** = a shipped feature is broken or a
security hole; **Medium** = wrong/misleading behaviour with a workaround, or blocks a roadmap plan; **Low** = cosmetic, docs, hygiene.

Plan numbers: 01 input types, 02 audit trail, 03 plain-language errors, 04 audit test nodes, 05 data profile node,
06 workpaper export, 07 shaping nodes (reviewed in "Additions from plan 07 review"), 08 CLI and scheduling.

How to run probes that need the app (offscreen Qt, repo test fixtures):
`$env:PYTHONPATH="."; $env:QT_QPA_PLATFORM="offscreen"; .venv\Scripts\python -m pytest <probe.py> -p tests.conftest --rootdir=. -s -q`
(the `-p tests.conftest` makes `qtbot`-style fixtures such as `no_modal_dialogs` available to a file outside `tests/`).
Set `PYTHONUTF8=1` for runs whose stdout is piped, otherwise emoji log lines raise `UnicodeEncodeError` on the cp1252 console (BUG-028).

---

## Summary table

| ID | Title | Severity | Area | Status | Affects plans |
|---|---|---|---|---|---|
| BUG-001 | Polars `PanicException` reported as success; executor worker dies; later nodes time out | Critical | Executor | Verified | 02, 03, 04, 05, 08 |
| BUG-002 | Saving a workflow truncates the `.tds` to 0 bytes on any serialize/encoding failure; save uses locale encoding | Critical | Persistence (vendored nodeeditor) | Verified | 01, 02, 08 |
| BUG-003 | Hostile or unusual `.tds` text becomes code in the generated script (code injection into `exec`) | High | Codegen / security | Verified | 01, 04, 08 |
| BUG-004 | Run never collects lazy plans when the graph has no sink; broken plans "succeed" | High | Run | Verified | 02, 03, 04, 05 |
| BUG-005 | Run executes `get_code()` from stale or never-evaluated live state; fallback code emits empty frames silently | High | Run | Verified | 02, 04, 08 |
| BUG-006 | Excel export is broken: `xlsxwriter` not installed or declared (File Output "excel", Data Preview) | High | I/O dependency | Verified | 05, 06 |
| BUG-007 | Installed `qtpy-nodeeditor` lacked APIs the repo calls (`setPositions`, detail-LOD); edge updates raise at runtime | High | Environment / canvas | **Fixed** (2026-10-22) | all UI plans |
| BUG-008 | `getSocketValue` resolves only the first matching output socket (two outputs of one node into one node break) | High | Evaluation | Verified | 04, 05, 06 |
| BUG-009 | Run failures: no node tooltip, exception type lost, "Original traceback" is useless | Medium | Errors | Verified | 03, 02 |
| BUG-010 | `execute_node` raises `UnboundLocalError` when `get_code()` raises | Medium | Executor | Verified (latent) | 03, 08 |
| BUG-011 | Cancellation is not wired anywhere; timeouts abandon threads; load progress dialog has no Cancel | Medium | Run / UX | Verified | 08, 01 |
| BUG-012 | A cyclic graph leaves the Run button disabled for good (and re-raises into the Qt slot) | Medium | Run / UX | Verified | 08 |
| BUG-013 | `getPyFile` writes `check_output.py` into the CWD on every Run; file is git-tracked; contents non-deterministic and contain a personal path | Medium | Run / repo hygiene | Verified | 02, 08 |
| BUG-014 | Absolute file paths stored in `.tds`; tracked workflows embed a developer's home path | Medium | Persistence | Verified | 01, 02, 08 |
| BUG-015 | No workflow version check on open; `workflow_metadata` extras are dropped on save | Medium | Persistence | Verified | 02, 08 |
| BUG-016 | File Output `check_file_path` is never called | Low | I/O node | Verified | 03 |
| BUG-017 | `scene.serialize()` re-reads the input file on every save and every undo snapshot; `registerInputWidget` records whole-scene snapshots | Medium | Performance / undo | Verified | 01, 02 |
| BUG-018 | SQL editor erases its own diagnostics (repaint fires `textChanged`) and revalidates every 800 ms forever | Medium | Formula/Filter editor | **Fixed** (2026-10-22) | 03 |
| BUG-019 | `exec()` of generated code has no sandbox; `ENHANCED_EXECUTOR_GUIDE.md` documents features that do not exist | Medium | Security / docs | Verified | 08 |
| BUG-020 | Test-suite health: 20 failed + 7 errors in `tests/ui`; full `pytest` aborts (exit 139) | Medium | Tests | **Fixed** (2026-10-22) - 793 passed, 0 failed, no abort | all |
| BUG-021 | Error-translation hazards: Windows `OSError` has `errno=None`; Polars "out of N values" is a batch size | Low | Errors | Verified | 03 |
| BUG-022 | Stale or incorrect docs (SESSION_HANDOFF, NODE_REFERENCE, README, CONTRIBUTING, AGENTS, placeholders) | Low | Docs | Verified | all |
| BUG-023 | Empty stub node files and enum members with no node | Low | Registry | Verified | - |
| BUG-024 | README claims Windows/macOS/Linux; build and run tooling is Windows-only with hard-coded paths | Low | Packaging / docs | Verified | 08 |
| BUG-025 | Bundled sample `savedfiles/3. in-formula-out.json` fails on Run | Low | Samples | Verified | - |
| BUG-026 | DynamicRowBuilder datetime increment uses a date-time widget where seconds are required | Low | Node | Partially verified | - |
| BUG-027 | Working-tree state: concurrent edits, dead and non-importable `file_opener.py`, unguarded `__main__.py` | Low | Repo hygiene | Verified (facts) | - |
| BUG-028 | Logging hazards: fallback `print` can raise on non-UTF-8 stdout; logging dock off-thread access | Low | Logging | Partially verified | 02, 08 |
| BUG-029 | Filter expression and Formula run user SQL on an unrestricted DuckDB connection: file reads and multi-statement writes (e.g. `COPY ... TO`) from workflow text, also during live evaluation | High | Security / DuckDB nodes | Verified | 07, 08 |
| BUG-030 | DuckDB `extract_statements` type and `lock_configuration` are not a read-only guard (PRAGMA, DESCRIBE, `FROM 'x'`, `read_*()` are typed `SELECT`; in-memory DDL still runs after the lock) | Medium | DuckDB hazard (blocks plan 07 SQL nodes) | Verified | 07 |
| BUG-031 | `TriggerNode.evalImplementation` requires every input to be connected; optional inputs need an override (only `union.py` has one) | Low | Evaluation | Verified (code) | 07 |
| BUG-032 | Generated Formula code embeds the query in `'''...'''`: a formula containing `'''` is a `SyntaxError` at Run; `duck.close()` is skipped on error | Low | Codegen | Verified | 07 |

Claims from the task brief that could not be confirmed are in the section "Claims not confirmed" at the end
(`isModified()` stub, stale `ToDo.md` File Input entry, Cleansing serialization).

---

# CRITICAL

## BUG-001 - Polars `PanicException` is reported as success, the executor thread dies, later nodes time out

* **Severity:** Critical. A node that panics is marked successful (no error, no red ring) and its output variables are
  simply missing. Every later node then waits the full 30 s timeout. For an audit tool, "step passed" when it did not run is the worst failure class.
* **Status:** Verified (reproduced).
* **Symptoms:** Run shows a green node where the node actually died; the next node fails with
  "Code execution timed out after 30.0 seconds"; the next-next node would too, but the run stops at the first failure.
* **Root cause:** `src/trigger_designer/core/ExecutionCheck/executor.py:262-269`
  ```python
  try:
      execution_globals = {**self.execution_context, "__name__": "__main__"}
      exec(code, execution_globals, local_vars)
  except Exception as e:           # :266  PanicException is a BaseException, not an Exception
      exception_container[0] = e   # :267
  finally:
      done.set()                   # :269  runs for BaseException too -> waiter sees "done, no exception"
  ```
  `_execute_with_timeout` then returns `(True, None)` => `result.success = True`. The `BaseException` continues to
  unwind through `target()` and kills the pooled worker thread started at `:157-159` (`_node_worker_loop`, `:168-172`,
  has no try/except around `task()`). The next `execute_node` queues a task nobody consumes and waits the whole timeout.
* **Reproduce** (no Qt needed; `NodeExecutor` with a stub node):
  ```python
  import sys, time; sys.path.insert(0, "src")
  from trigger_designer.core.ExecutionCheck.executor import NodeExecutor
  class N:
      content = None
      def __init__(s, c): s.c = c
      def get_code(s): return s.c
  ex = NodeExecutor(); ex.security_config.max_execution_time = 3.0
  r = ex.execute_node(N("import polars.exceptions as pe\nraise pe.PanicException('boom')"))
  print(r.success, repr(r.error)); time.sleep(0.3); print(ex._node_worker_thread.is_alive())
  t = time.time(); r2 = ex.execute_node(N("x = 1")); print(r2.success, r2.error, round(time.time() - t, 1))
  ```
* **Verified output:**
  ```
  panic node: success=True error='' t=0.00s
  P1 panic success: True | worker thread alive afterwards: False
  P1 PanicException MRO: ['PanicException', 'BaseException', 'object']
  next node: success=False error='Code execution timed out after 3.0 seconds' t=3.00s
  ```
  (The panic is `simulated` with `raise pe.PanicException('boom')`; a real Rust panic uses the same class.)
* **Impact:** Blocks the trustworthiness of plans 02 (the audit trail would record a passed step), 03 (translation
  catalogue code `TD-SYS-998` needs the exception), 04/05 (audit and profile nodes run heavy Rust code that can panic),
  08 (nightly job exit codes). Fix before any of them.
* **Recommended fix (S):** in `executor.py` change `except Exception as e:` (`:266`) to `except BaseException as e:`
  (still let `done.set()` run in `finally`); in `_node_worker_loop` (`:168`) wrap `task()` in
  `try/except BaseException: logger.exception(...)` so the worker survives; leave `KeyboardInterrupt`/`SystemExit`
  handling to the caller. Change the annotations (`Tuple[bool, Optional[BaseException]]`). `execute_node`'s outer
  handler (`:378`) stays `except Exception` because the wrapper `NodeExecutionError` is an `Exception`.
* **Regression test:** `tests/unit/test_executor_panic.py::test_panic_exception_is_a_failure_not_success` - run
  `raise pe.PanicException("boom")`; assert `result.success is False`, then `execute_node` of `x = 1` on the **same**
  executor returns `success is True` in under 2 s (`time.perf_counter()` delta) - proves the worker survived.
* **Effort:** S (30 minutes).

---

## BUG-002 - Saving truncates the `.tds` file to 0 bytes on any failure; save uses the locale encoding

* **Severity:** Critical (data loss). The target file is opened for writing **before** the scene is serialized, so any
  exception while serializing or encoding destroys the user's previous save. On Windows the default text encoding is
  cp1252, so a workflow containing any character outside cp1252 (for example `→`, CJK, emoji in a node title, label,
  formula text or path) cannot be saved at all and wipes the existing file.
* **Status:** Verified (reproduced). The faulty code is in the *installed* `nodeeditor`
  (`.venv/Lib/site-packages/nodeeditor/node_scene.py:621-636`), not in the repo; the repo has no override of `saveToFile`.
  Plan 08 (F10) independently notes the locale-encoding half.
* **Symptoms:** "Save" appears to fail (or silently does something odd); reopening the file reports an invalid file
  or an empty workflow. Previous work is gone.
* **Root cause:** `node_scene.py:621-636`
  ```python
  with open(filename, "w") as file:              # truncates immediately; default (locale) encoding
      json_str = json.dumps(self.serialize(), option=OPT_INDENT_2).decode("utf-8")
      file.write(json_str)                       # UnicodeEncodeError on '\u2192' under cp1252
  ```
  `loadFromFile` (`:640-660`) reads with `open(filename, "r")` too and **swallows non-JSON exceptions**
  (`except Exception as e: dumpException(e)`), so a partly failed load still "succeeds".
* **Reproduce** (pytest probe with a `TriggerSubWindow`; run with the console **not** in UTF-8 mode, i.e. without `PYTHONUTF8=1`, and `PYTHONIOENCODING=utf-8` to keep the log lines printable):
  ```python
  w = TriggerSubWindow(); node = SelectNodeClass(w.scene)
  w.scene.saveToFile(str(p))                       # baseline
  node.title = "Revenue \u2192 \u65e5\u672c\u8a9e"   # any non-cp1252 text
  w.scene.saveToFile(str(p))                       # raises UnicodeEncodeError
  print(p.stat().st_size)                          # 0
  ```
* **Verified output:**
  ```
  SV locale encoding: cp1252
  SV baseline save bytes: 1164
  SV non-cp1252 title -> UnicodeEncodeError ; file size after failed save: 0
  SV serialize raises -> RuntimeError ; file size afterwards: 0 (was 1164)
  ```
* **Impact:** Any plan that adds non-ASCII text to saved state (01 file names and sheet names, 02 audit fields, 06 workpaper
  labels, 08 job names) raises the probability of hitting this. Also affects every user whose data or paths contain non-Latin-1 characters today.
* **Recommended fix (S-M):** in `src/trigger_designer/qt/performance_scene.py` (`TriggerScene`, already the repo's scene subclass) override `saveToFile`:
  serialize first; write bytes (`orjson.dumps(..., option=OPT_INDENT_2)` is already UTF-8) to `filename + ".tmp"`;
  `os.replace` onto the target; then set `has_been_modified = False` and `filename`. Override `loadFromFile` to read bytes
  (`open(filename, "rb")`) and `orjson.loads`. Keep legacy cp1252-written files readable: try UTF-8, fall back to `cp1252` on `UnicodeDecodeError`.
  Do not edit site-packages.
* **Regression test:** `tests/ui/test_scene_save.py::test_save_never_truncates_existing_file` (serialize raising leaves the old bytes intact) and
  `::test_save_roundtrips_non_cp1252_title` (title `"A \u2192 \u65e5"` survives save+load, file is valid UTF-8).
* **Effort:** M (the override is 25 lines; the load fallback and tests are the bulk).

---

# HIGH

## BUG-003 - Text from a `.tds` is interpolated unescaped into generated code (code injection into `exec`)

* **Severity:** High (security). A crafted or merely unusual workflow file runs arbitrary Python when the user clicks Run.
  Plain apostrophes also break nodes by accident (SyntaxError at Run).
* **Status:** Verified (reproduced with a harmless marker file). Plan 08 (experiment X3) reproduced the same hole headless.
* **Symptoms:** Delimiter `'`, a sheet name, a column name or a filter value containing `'` makes the node fail at Run with a `SyntaxError`
  that names generated code the user never wrote. A deliberate payload executes.
* **Root cause (exact sites):**
  * `src/trigger_designer/qt/widgets/nodes/InOut/file_input.py:795` `read_params.append(f"separator='{self.delimiter}'")`
  * `file_input.py:760` `load_params.append(f"idx_or_name='{self.selected_sheet}'")`
  * `qt/widgets/nodes/Preparation/select.py:1660` `selected_columns = [f"'{col}'" ...]` (and `:1695` rename dict)
  * `qt/widgets/nodes/Preparation/filter.py:950-952` ``formatted_value = f"'{self.value}'"`` (by code reading)
  * `qt/widgets/nodes/Preparation/dynamic_row_builder.py:408` ``{{'{self.field_name}': values}}`` (by code reading)
  The `filePath` fields use `{self.filePath!r}` (safe); the above do not. `.tds` content is deserialized straight into these attributes
  (`deserialize_content_state`) with no validation.
* **Reproduce** (offscreen Qt; builds a `FileInputContent` without a scene, like the unit tests do):
  ```python
  c = FileInputContent.__new__(FileInputContent)
  c.filePath = "data/check.csv"; c.file_type = "csv"; c.record_limit = 0
  c.output_filename_as_field = False; c.first_row_contains_field_names = True; c.id = "1"; c.variable_name = "var_fi"
  c.delimiter = ",')\nopen(MARKER,'w').write('pwned')\nx = pl.scan_csv('data/check.csv', separator='"
  try: exec(c.get_code(), {}, {})          # generated code now contains: open(MARKER,'w').write('pwned')
  except Exception as e: print(type(e).__name__)
  print(os.path.exists(MARKER))
  c.delimiter = "'"; exec(c.get_code(), {}, {})   # SyntaxError
  ```
* **Verified output:**
  ```
  open('C:\\Users\\KASHVI~1\\AppData\\Local\\Temp\\td_inject_marker.txt','w').write('pwned')
  exec ended with ValueError            (the original scan_csv call is the 2nd statement; the injected one ran first)
  marker file created by crafted delimiter: True
  plain apostrophe delimiter -> SyntaxError
  ```
  The marker file was removed afterwards.
* **Impact:** Plan 08 makes the generated script headless/scheduled, so a hostile `.tds` becomes unattended code execution; plan 01 adds
  more user-typed values (encoding, null markers, sheet names, glob patterns) that must not repeat this pattern; plan 04 interpolates column names.
* **Recommended fix (M):** one helper `py_literal(value) -> str` (`repr()`) in `qt/helpers/` (or `core/codegen.py`) and replace every
  `'{...}'` site with `{value!r}`; `separator={self.delimiter!r}`. For Select/Filter use `repr` of the column list and rename dict.
  Add the AST policy validator planned in plan 08 section 6 as defence in depth. Do not escape by hand.
* **Regression test:** `tests/unit/test_codegen_quoting.py::test_hostile_values_roundtrip_through_exec` - parametrize delimiter, sheet name, column name,
  filter value over `["'", "\\", "');import os #", "\n"]`; assert `ast.parse(code)` succeeds and that executing the code (against a tiny CSV) does not create a marker file.
* **Effort:** M (about 8 sites + tests).

---

## BUG-004 - Run never collects lazy plans when the graph has no sink

* **Severity:** High. A Run on a graph with no File Output / Graph / Count reports success regardless of whether the Polars plan is valid.
* **Status:** Verified (reproduced).
* **Symptoms:** All nodes turn green; opening the preview later (a `collect()`) then fails. Nothing in Run told the user.
* **Root cause:** Generated code only builds `LazyFrame`s (for example `select.py:1661-1664` emits `var.select([...])`); the executor
  (`executor.py:289-417`) never collects results. Only sink-type nodes materialise data (brief 4.3). A bad column in a lazy `select` raises only at `collect()`.
* **Reproduce** (probe with the shipped `savedfiles/1. in-select.tds`, which has File Input -> Select and no sink):
  set `select.content.changes["selected_columns"] = ["NoSuchCol"]`, call `window.executeWorkflow()`, wait, inspect `window.execution_results`.
* **Verified output:**
  ```
  S1 CODE: var_select_1254127915632 = var_file_input_1254123356016.select(['NoSuchCol'])
  S1 RESULT: executed=2/2 invalid=[]
  S1 type: LazyFrame
  S1 collect raises: ColumnNotFoundError unable to find column "NoSuchCol"; valid columns: ["Keyword", "Seed", ...
  ```
* **Impact:** Plan 03 (errors surface at the sink node, not the culprit; a graph without a sink never errors); plan 04/05 (audit-test and profile
  nodes must collect inside their own `get_code()`, which the plans already require); plan 02 mode `all` plans to surface this as a warning.
* **Recommended fix (M):** two options; do the cheap one first. (a) Per node, after exec, validate the declared output frames with `frame.collect_schema()`
  (cheap, resolves the plan without reading data) in the existing `after_execution`-style hook, and fail the node on `ColumnNotFoundError` / `SchemaError`.
  (b) Optional "Verify plan" Run option that runs `frame.limit(0).collect()` per declared output. Implement (a) in `execute_node` after `result.variables = ...` (`:361`).
* **Regression test:** `tests/e2e/test_run_without_sink.py::test_bad_select_column_fails_run_without_sink` using the probe above; assert the run reports failure and `select` is invalid.
* **Effort:** M.

---

## BUG-005 - Run executes `get_code()` from stale or never-evaluated live state

* **Severity:** High. Generated code depends on attributes that only the live `processInputs()` pass sets (`incoming_variable`, `incom_data`, `data`).
  If a node was never live-evaluated, or its upstream is currently invalid, Run silently executes the fallback code, which defines an **empty** frame.
* **Status:** Verified (reproduced).
* **Symptoms:** Run succeeds and downstream nodes receive `pl.DataFrame()` (0 rows, 0 columns); outputs are empty with no error.
* **Root cause:** `src/trigger_designer/qt/helpers/workflow_execution_mixin.py:47-89` (`executeWorkflow`) never calls `eval()` (grep for `.eval(` in the file: no match).
  Example fallback: `select.py:1643-1651`
  ```python
  if self.data is None or not self.incoming_variable:
      ... code.append(f"{self.variable_name} = pl.DataFrame()")
  ```
* **Reproduce:** load `savedfiles/1. in-select.tds`, set `select.content.data = None; select.content.incoming_variable = ""`, run.
* **Verified output:**
  ```
  S2 CODE: 'import polars as pl\nvar_select_1254128370064 = pl.DataFrame()\n'
  S2 RESULT: success, output = DataFrame (0, 0)
  ```
  Plan 08 (F3, F4) confirms 9 of 23 `get_code` methods read live schema, and that loading through the real loader (`fileLoad` runs `doEvalOutputs`) is the headless workaround.
* **Impact:** Blocks headless use (plan 08 must load via `fileLoad` and evaluate before running); makes the audit trail (02) record a "successful" run over empty data.
* **Recommended fix (M):** at the start of `executeWorkflow` (after the cycle check, see BUG-012) mark every node dirty and call `node.eval()` in topological order
  on the GUI thread (reuse `doEvalOutputs` in `design_window.py`); abort with a message if any node is invalid before the worker starts.
  Independently, make fallback `get_code()` in nodes raise `ValueError("node not evaluated")` instead of emitting empty frames (coordinate with BUG-010).
* **Regression test:** `tests/e2e/test_run_reevaluates.py::test_run_after_unevaluated_load_uses_real_data` - load, null the live state, run, assert the Select output has rows.
* **Effort:** M.

---

## BUG-006 - Excel export is broken because `xlsxwriter` is neither installed nor declared

* **Severity:** High. File Output "excel" fails at Run; Data Preview "Export Excel" silently does nothing.
* **Status:** Verified (reproduced).
* **Product decision (recorded):** Excel *writing* will use `xlsxwriter` (plan 06 step 1). `pyfastexcel` was evaluated and rejected: no real streaming, about 1.27 GB for 500k x 6. The bug stands until that lands: the current code path is broken.
* **Symptoms:** File Output node with `.xlsx` target: Run fails with `Excel export requires 'xlsxwriter' not found.` (shown as a raw string). Data Preview: user picks a filename,
  nothing is written, no message (the exception is only logged).
* **Root cause:**
  * `src/trigger_designer/qt/widgets/nodes/InOut/file_output.py:299` generated `{var}_lazy.collect().write_excel({export_path!r})`
  * `src/trigger_designer/qt/models/polars_table_viewer.py:1205` `current_df.write_excel(filename)` inside `try/except Exception: logger.error(...)` (`:1207-1208`) - the user sees nothing.
  * `pyproject.toml` dependencies list has `fastexcel>=0.15.1` and `openpyxl>=3.1.0` but no `xlsxwriter`; `uv.lock` has none (grep: no match).
* **Reproduce:** `.venv\Scripts\python -c "import polars as pl; pl.DataFrame({'a':[1]}).write_excel('x.xlsx')"`
* **Verified output:**
  ```
  ModuleNotFoundError: Excel export requires 'xlsxwriter' not found.
  Please install using the command `pip install xlsxwriter`.        (and no x.xlsx is created)
  ```
* **Impact:** Plan 06 (workpaper) starts with replacing both call sites; plan 05 (profile export) reuses them.
* **Recommended fix (M):** land plan 06 step 1: add `core/excel/` writer (`write_frame_xlsx`) over `xlsxwriter`, re-point `file_output.py:299` and `polars_table_viewer.py:1205`,
  declare the dependency in `pyproject.toml` and relock. Until then (S): in `polars_table_viewer.py` show a `QMessageBox.warning` (or status text) in the `except` instead of only logging,
  and make `FileOutputContent` mark the node invalid when the format is `excel` and the writer module is missing.
* **Regression test:** `tests/unit/test_excel_export.py::test_file_output_excel_writes_a_readable_workbook` (generated code for format excel, exec it, read it back with `fastexcel`, compare rows)
  and `::test_data_preview_export_reports_failure` (monkeypatch writer to raise; assert the user-visible message).
* **Effort:** M (S for the user-visible error only).

---

## BUG-007 - The installed `qtpy-nodeeditor` is older than the repo expects; edge updates raise at runtime

* **Severity:** High. Not only a test problem: production code calls APIs the installed library does not have, and the error is swallowed.
* **Status:** **Fixed** (2026-10-22). The numbers quoted below were measured before the fix.
* **Symptoms:** Edge geometry not updated on node move or load (silent `AttributeError` tracebacks on stderr: `AttributeError: 'super' object has no attribute 'setPositions'`
  printed while loading every e2e workflow); the app logs `The installed nodeeditor has no detail policy; the canvas keeps its own rules`.
* **Root cause:** installed commit `ee5e8fd1c4dfe0585d6fa2209f02347d4e600c59` of `https://github.com/AzadKshitij/qtpy-nodeeditor.git`
  (`.venv/Lib/site-packages/qtpy_nodeeditor-0.7.dist-info/direct_url.json`); `grep -rn setPositions .venv/Lib/site-packages/nodeeditor` finds nothing, yet:
  `src/trigger_designer/qt/performance_scene.py:44` `super().setPositions(source, destination)` and `:116` `self.grEdge.setPositions(source_pos, end_pos)`;
  `qt/render_settings.py:89-96` uses `detail_lod_threshold`; `qt/node_base.py:254` uses `_content_visible`. The package is intentionally outside `uv.lock`
  (`pyproject.toml:14-20,50-55,101`), so `uv sync` cannot repair it and nothing pins the required ref.
* **Resolution:** the upstream package was published to PyPI as `nodeeditor-qtpy` 0.8.1 (built from the same commit the repo expects).
  It is now a normal, pinned dependency — `nodeeditor-qtpy==0.8.1` in `pyproject.toml`, resolved into `uv.lock` — so `uv sync`
  installs a matching copy and no longer needs the hand-patched git install. `qtpy` was bumped `2.4.2` → `2.4.3` to satisfy
  the package's own floor. `scripts/build.bat` now runs `uv sync --frozen --all-groups` instead of installing from git.
  The `setPositions` / detail-LOD calls in `performance_scene.py` and `render_settings.py` need no guards any more.
* **Reproduce:** `.venv\Scripts\python -m pytest tests/ui/test_edge_geometry.py -q` and `tests/ui/test_labels_groups.py::test_group_collapse_expand_edges`.
* **Verified output (per file, run separately, today):**
  ```
  test_canvas_grid_render.py : 6 failed  (AttributeError: 'QDMGraphicsScene' object has no attribute 'setDetailLod' / 'updateDetailLod' / 'MIN_GRID_SPACING_PX' / 'DETAIL_LOD_THRESHOLD'; 'TriggerGraphicsNode' ... '_detail_visible')
  test_edge_geometry.py      : 7 errors (AttributeError: 'super' object has no attribute 'setPositions')
  test_labels_groups.py      : 1 failed (performance_scene.py:44 setPositions)
  test_render_settings.py    : 8 failed ('updateDetailLod', 'detail_lod_threshold', '_content_visible', two `assert not True`)
  ```
* **Impact:** Every UI plan is developed against a library that does not match what ships; the 27 baseline failures hide new regressions. Plan 08 packaging must pin the right ref.
* **Recommended fix (S-M):** (1) record the required nodeeditor commit in one place (`QTNODEEDITOR_REF` in `scripts/build.bat` and a `docs/` note) and add a startup/self-check test
  `tests/unit/test_nodeeditor_api.py::test_installed_nodeeditor_has_required_api` asserting `hasattr(QDMGraphicsEdge, "setPositions")` etc. so the mismatch is one clear failure, not 27; (2) guard the two
  call sites with `getattr` fallbacks (`setSource` + `setDestination`) so an older lib degrades instead of raising; (3) reinstall the newer ref via `scripts/sync-nodeeditor.ps1`.
* **Regression test:** the API self-check above plus `tests/ui/test_edge_geometry.py` going green.
* **Effort:** S (self-check + guards), M including the environment refresh.

---

## BUG-008 - `getSocketValue` resolves only the first matching output socket

* **Severity:** High for plans that need "both outputs of one node into one downstream node"; Medium today (Split's two outputs rarely feed one node).
* **Status:** Verified (reproduced).
* **Symptoms:** A Join (or Append) fed by two outputs of the same upstream node reads output 0 on both inputs: both sides contain the same data and no error is shown.
* **Root cause:** `src/trigger_designer/qt/node_base.py:708-723`
  ```python
  def getSocketValue(self, socket_list, target_node) -> int:
      for i, socket in enumerate(socket_list):
          if socket.edges:
              for edge in list(socket.edges):
                  other_socket = self._get_connected_socket(socket, edge)
                  ...
                  if other_socket.node == target_node:
                      return i          # first output socket wired to the target node wins
  ```
  Called by 18 sites (for example `join.py:1460-1462`, `Append.py:214-215`). `_get_connected_socket` also has a **side effect**: it removes an inconsistent edge from the socket and logs a warning (`node_base.py:~728-735`), so a getter mutates the graph.
* **Reproduce:** stub node with two outputs (`outputs=[3, 3]`, frames tagged "E" and "V"), wire output 0 to Join input 0 and output 1 to Join input 1, `join.eval()`.
* **Verified output:**
  ```
  S7 left side col: ['E'] right side col: ['E'] left var: var_E right var: var_E
  S7 getSocketValue -> 0 (both inputs resolve to this index)
  ```
* **Impact:** Plan 04 nodes with multiple outputs (Duplicates: Duplicates/Unique/Summary; Sample: S/N/L) feeding one downstream node, plan 05 (D and P outputs), plan 06 (Summary + Exceptions into one Workpaper) hit this. Plan 02 avoids it by using real edge indexes; plan 06 plans to use `getInputWithSocketIndex`.
* **Recommended fix (S):** add `getInputWithSocket(i)` usage (`nodeeditor.Node.getInputWithSocket`, already in the vendored lib) in the helper: new method `TriggerNode.input_socket_index(self, input_index) -> int` that returns the *edge's* start-socket index for input `input_index`; change the 18 call sites mechanically. Keep `getSocketValue` as a deprecated wrapper that delegates when a single edge exists. Remove the edge-removal side effect or move it to load-time validation.
* **Regression test:** `tests/unit/test_socket_resolution.py::test_two_outputs_of_one_node_feed_two_inputs` (the probe above; assert left `side == "E"`, right `side == "V"`).
* **Effort:** M (mechanical, many call sites).

---

# MEDIUM

## BUG-009 - Run failures: no tooltip on the node, exception type lost, "Original traceback" is useless

* **Severity:** Medium. The user sees a red ring with no reason on the node; the Logging dock line has no exception class; the appended "traceback" shows only the executor's own `raise` line.
* **Status:** Verified (reproduced, three parts).
* **Symptoms / observed:**
  1. After a failed Run the failing node's tooltip is empty and `isInvalid()` is true.
  2. `result.error` is `str(exception)` only: `ZeroDivisionError` appears as `division by zero`; `MemoryError()` has an empty message so `error` **starts with** `"\n\nOriginal traceback:"` (it is only a traceback).
  3. The traceback appended for wrapped exceptions is `traceback.format_exc()` of `execute_node`'s `raise NodeExecutionError(...)`, so it never shows the user-code frames or the original class.
  4. Run stops at the first failure, so independent branches after it never run (second File Output in `savedfiles/11. Split.tds` was skipped).
* **Root cause:** `executor.py:344-348` (`raise NodeExecutionError(str(exception), ..., original_exception=exception)` without `from exception`), `:378-388`
  ```python
  except Exception as e:
      self._report_missing_dependency(node_name, e)
      result.error = str(e)
      if hasattr(e, "original_exception") and e.original_exception:
          result.error += f"\n\nOriginal traceback:\n{traceback.format_exc()}"
  ```
  `ExecutionResult` has no `exception` field (`:35-47`); `workflow_execution_mixin.py:106-112` `_on_node_finished` failure branch calls only `logger.error`, `global_logger.error`, `markInvalid()`, `setPenError()` - no `_set_node_tooltip`.
* **Reproduce:** `r = NodeExecutor().execute_node(N("raise MemoryError()"))`, `N("x = 1/0")`; and a probe: load `savedfiles/11. Split.tds`, set a File Output `filePath` to a nonexistent directory, run, read `fo.grNode.toolTip()`.
* **Verified output:**
  ```
  CODE raise MemoryError() -> success False
  ERROR REPR: '\n\nOriginal traceback:\nTraceback (most recent call last):\n  File ".../executor.py", line 344, in execute_node\n    raise NodeExecutionError(...) ...
  CODE x = 1/0 -> success False
  ERROR REPR: 'division by zero\n\nOriginal traceback: ... trigger_designer.core.ExecutionCheck.executor.NodeExecutionError: division by zero\n'
  S6 node: File Output success: False error[:200]: 'The system cannot find the path specified. (os error 3): ...no_such_dir/out.csv (set POLARS_VERBOSE=1 to see full path)\n\nOriginal t'
  S6 tooltip after failed run: '' invalid: True
  has exception attr: False
  ```
* **Impact:** This is plan 03's core problem statement; plan 02 needs the exception/class to record a meaningful failure. Fix is the precondition for both.
* **Recommended fix (S-M):** plan 03 Step 4: add defaulted fields `exception: BaseException | None`, `traceback_text: str` to `ExecutionResult`; `raise NodeExecutionError(...) from exception`; capture `traceback.format_exception(exception)` of the *original*; in `_on_node_finished` set the node tooltip (`node._set_node_tooltip(...)`) from the (translated) message. Do not change `ExecutionResult` positional order.
* **Regression test:** `tests/unit/test_executor_errors.py::test_result_keeps_exception_type_and_original_traceback` (assert `isinstance(result.exception, ZeroDivisionError)` and `"1/0"` or `"ZeroDivisionError"` in `result.traceback_text`) and `tests/e2e/test_run_failure_tooltip.py::test_failed_node_has_tooltip`.
* **Effort:** M.

---

## BUG-010 - `execute_node` raises `UnboundLocalError` when `get_code()` raises

* **Severity:** Medium (latent today: no shipped node's `get_code()` raises at present, File Output now emits `raise ValueError(...)` *inside* the generated code; plan 08 plans a code filter that raises).
* **Status:** Verified (reproduced with a stub node); the plan 08 document (F7) reports the same.
* **Symptoms:** the real error is replaced by `cannot access local variable 'node_name' where it is not associated with a value`; the exception escapes `execute_node` into `WorkflowWorker.run` (`nodeErrored` path, `# pragma: no cover`).
* **Root cause:** `executor.py:310-311`
  ```python
  code = node.get_code()                                   # raises -> node_name never assigned
  node_name = getattr(node.__class__, "__name__", "Unknown")
  ...
  except Exception as e:
      self._report_missing_dependency(node_name, e)        # :379 UnboundLocalError
  ```
* **Reproduce / verified output:**
  ```python
  ex2 = NodeExecutor(); ex2.execute_node(N(ValueError("File Output: no incoming data")))   # N.get_code raises
  ```
  ```
  get_code raise escapes execute_node: UnboundLocalError cannot access local variable 'node_name' where it is not associated with a value
  ```
* **Impact:** plan 08 (code filter), plan 03 (error text), and any future node that validates in `get_code()`.
* **Recommended fix (S):** move `node_name = ...` above `code = node.get_code()` (`:309`). One line.
* **Regression test:** `tests/unit/test_executor_errors.py::test_get_code_raising_is_a_normal_failure` - `result.success is False` and `"no incoming data" in result.error`.
* **Effort:** S (5 minutes).

---

## BUG-011 - Cancellation is not wired; a timed-out node's thread is abandoned; load progress dialog has no Cancel

* **Severity:** Medium. No way to stop a long Run or a long file load.
* **Status:** Verified (grep of callers, code reading).
* **Evidence:**
  * `grep -rn "request_cancel\|cancel_execution\|_cancel_event\|_cancel_requested" src tests` -> only definitions (`workflow_worker.py:37-41`, `executor.py:146,303,457-464`). `execute_node` even does `self._cancel_event.clear()` (`:303`); nothing reads the event in the exec thread.
  * The worker checks `_cancel_requested` only between nodes (`workflow_worker.py:46-49`).
  * Timeout: `executor.py:274-284` returns `ExecutionTimeoutError` while the exec thread keeps running (comment at `:274-281` acknowledges it cannot be killed); the abandoned thread keeps writing (a `sink_csv`) after "failure".
  * `qt/helpers/eval_progress.py:32-46` `make_progress_dialog`: `QProgressDialog(title, None, ...)`, `dialog.setCancelButton(None)`, `ApplicationModal` - no cancel on load/evaluation.
  * There is no Run-time Stop button (`run_button` only; `grep -n "Stop\|stop"` in `design_window.py` finds none for Run).
* **Impact:** plan 08 (cancel/timeout semantics need process-level isolation: a child process can be terminated, a thread cannot); plan 01 (folder inputs make loads longer).
* **Recommended fix (M-L):** GUI: add a Stop `IconButton` that calls `WorkflowWorker.request_cancel()` (between-node cancel is cheap and honest: label it "Stops after the current step"); make the cancel button in `make_progress_dialog` optional for load. For hard cancel use plan 08's subprocess runner; do not try to kill threads.
* **Regression test:** `tests/unit/test_workflow_worker.py::test_cancel_before_next_node_stops_run` (3 stub nodes, cancel after first `nodeFinished`; assert 2nd never `nodeStarted`).
* **Effort:** M (between-node cancel + button), L (hard cancel).

---

## BUG-012 - A cyclic graph leaves the Run button disabled for good

* **Severity:** Medium (UX dead end until the window is reopened).
* **Status:** Verified (reproduced).
* **Root cause:** `workflow_execution_mixin.py:57-61` disables `run_button` *before* `topologicalSort` raises (`design_window.py:754` `raise Exception("Graph has at least one cycle")`); `design_window.py:690-696` `run_workflow` logs and **re-raises** into the Qt slot. Nothing re-enables the button on this path.
* **Reproduce / verified output:** two Select nodes wired A->B and B->A, `window.run_workflow()`:
  ```
  SC edges: 2 run enabled before: True
  [ERROR] Workflow execution failed: Graph has at least one cycle
  SC raised: Exception Graph has at least one cycle
  SC run enabled after cycle error: False
  ```
* **Impact:** plan 08 (a cycle must be a clean error code), plan 03 (a plain-language cycle message).
* **Recommended fix (S):** in `executeWorkflow` compute `sorted_nodes` first and only then disable the button; catch the cycle exception in `run_workflow`, show it via `logError`/dialog and do not re-raise. Better: also prevent the cycle at edge-creation time (separate feature).
* **Regression test:** `tests/ui/test_run_cycle.py::test_cycle_keeps_run_button_enabled` (the probe; assert `run_button.isEnabled()` and no exception).
* **Effort:** S.

---

## BUG-013 - `getPyFile` writes `check_output.py` into the CWD on every Run; the file is git-tracked, non-deterministic, and holds a personal path

* **Severity:** Medium (repo hygiene, privacy, reproducibility; also a problem for headless/service use).
* **Status:** Verified.
* **Evidence:**
  * `src/trigger_designer/qt/design_window.py:698-706`: `with open("check_output.py", "w") as file:` - relative path, default encoding; called from `workflow_execution_mixin.py:133` after every Run (also after failures). Probe in a temp CWD: `S3 files in cwd: ['check_output.py']`.
  * `git ls-files check_output.py` lists it although `.gitignore:295` (`check_output.py`, "Generated by a workflow run") ignores it - it was committed before the ignore. `git status` shows it modified; `git diff --ignore-cr-at-eol --numstat check_output.py` -> `377 377` (only regenerated variable names and CRLF).
  * Non-deterministic: variable names embed `id(self)` (`nodeeditor/node_serializable.py:14` `self.id = id(self)`), e.g. `var_file_input_2051873347440` (committed) vs `var_file_input_1495771067440` (this tree). Two runs of the same workflow never produce the same script, so a script hash is meaningless.
  * Personal path: the tracked file embeds `C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/data/...`.
  * `getPyFile` calls `node.get_code()` a **second** time for every node (the first call is in `execute_node`); a `get_code()` that raises (BUG-010) would abort `_on_workflow_finished` before `_execution_cleanup` and leave the Run button disabled (by code reading: `workflow_execution_mixin.py:125-141`; not reproduced).
* **Impact:** plan 02 (code hash and generated-script capture), plan 08 (CLI must not write into the CWD; plan 08 already avoids `getPyFile`).
* **Recommended fix (S):** (1) `git rm --cached check_output.py` (the `.gitignore` entry then works). (2) Give `getPyFile` a `path` argument defaulting to the app data dir (`TRIGGER_DESIGNER_DATA_DIR`) and write with `encoding="utf-8", newline="\n"`; take node codes from the already-run results instead of calling `get_code()` again. (3) Make generated variable names stable: derive from a counter or a per-workflow stable uuid, not `id()`.
* **Regression test:** `tests/e2e/test_run_side_effects.py::test_run_does_not_write_into_cwd` (chdir to `tmp_path`, run, assert `list(tmp_path.iterdir()) == []`) and `::test_generated_variable_names_are_stable_across_loads` (load twice, compare `get_code()` of every node).
* **Effort:** S for (1)+(2), M for (3).

---

## BUG-014 - Absolute file paths are stored in `.tds`; tracked workflows embed a developer's home path

* **Severity:** Medium (portability; a workflow moved to another machine or user breaks, and the user path leaks).
* **Status:** Verified.
* **Evidence:** `file_input.py:46-58` `serialized_state_schema` stores `filePath` as given; the probe printed `S8 serialized filePath: C:/Users/KASHVINCHANDRASAN/.../data/check.csv absolute: True`. `file_output.py:351-358` stores `filePath` likewise. `git grep -l KASHVINCHANDRASAN` finds 16 tracked files, among them `data/Test_*.tds` (9), `savedfiles/I_select.tds`, `savedfiles/Example_2_Retail_Ledger/app_workflow/1.tds`, `check_output.py`, `run.bat`, `scripts/run.bat`, `scripts/check_output_polars.py`, `tests/manual/polars_viewer_demo.py`.
  The e2e harness works around it by rewriting `filePath` into a temp copy (`tests/support/workflows.py:50-75`). Brief 7.1: `schema_snapshot` and `file_metadata` are also stored.
* **Impact:** plan 01 (relative paths, path variables), plan 02 (input fingerprints record paths), plan 08 (`--input name=path` overrides).
* **Recommended fix (M):** plan 01: store a path relative to the `.tds` folder when the file is below it (keep `filePath` for backward compatibility, new `filePathRel` first on load); scrub personal paths from tracked samples (separate commit).
* **Regression test:** `tests/e2e/test_relative_paths.py::test_workflow_moves_with_its_data_folder` (copy `.tds` + data to another directory, load, run, assert the output).
* **Effort:** M.

---

## BUG-015 - No workflow version check on open; metadata extras are dropped on save

* **Severity:** Medium (ToDo item; becomes important as plans add state).
* **Status:** Verified (code reading).
* **Evidence:** `design_window.py:461-467` `validateLoadedWorkflow` only does `self.logDebug(f"Loaded workflow schema version: {schema_version}")`; no branch compares the version (`WORKFLOW_SCHEMA_VERSION = 2`, `core/constants.py:8`). A file written by a newer app (schema 99) loads silently and unknown keys are ignored. `Todo.todo` line 1 asks for exactly this check.
  `performance_scene.py:166-173` `serialize()` **overwrites** `workflow_metadata` with `{schema_version, app_version, saved_at}`, so any extra key a plan adds (`workflow_uuid`, plan 08 `parameters`) is lost on the next GUI save (plan 08 F9). `performance_scene.py:171` also uses deprecated `datetime.utcnow()`.
* **Recommended fix (S):** in `validateLoadedWorkflow` compare `schema_version` to `WORKFLOW_SCHEMA_VERSION`; newer -> warning dialog "saved by a newer version"; carry unknown `workflow_metadata` keys forward in `serialize()` (`{**self.loaded_workflow_metadata, ...}`); use `datetime.now(timezone.utc)`.
* **Regression test:** `tests/ui/test_workflow_version.py::test_newer_schema_version_warns` and `tests/unit/test_scene_metadata.py::test_extra_metadata_keys_survive_save`.
* **Effort:** S.

---

## BUG-017 - `scene.serialize()` re-reads the input file; `registerInputWidget` records whole-scene snapshots

* **Severity:** Medium (performance and side effects on every save and every dock edit).
* **Status:** Verified (counted).
* **Evidence:**
  * `file_input.py:843-845` `serialize()` calls `self._refresh_saved_input_metadata()` which, when the schema is not passed in, runs `self._read_file_based_on_type(self.filePath)` (`:355-358`): a full file read per serialize. Probe: monkeypatched reader counted `S8 re-reads of source file during 2 scene.serialize() calls: 2`.
  * `node_base.py:446-497` `registerInputWidget` calls `bind(...)` **without** `path=`; `qt/undo/binding.py:194-197` documents that omitting `path` "fall[s] back to a whole-scene snapshot - always correct, but heavier". `AGENTS.md:49` lists `registerInputWidget` as a preferred helper next to the note that `history.storeHistory` "serializes the whole scene ... Prefer the above", which reads as if `registerInputWidget` were fine-grained; it is not. Combined with the first bullet, **every File Input dock edit re-reads the file** (and so does every other snapshot-recorded edit anywhere in the graph).
  * `getSocketValue` (`node_base.py:708`) mutates the scene (BUG-008).
* **Impact:** plan 01 (multi-file/folder inputs make each snapshot read many files), plan 02 (serialize used for hashing).
* **Recommended fix (S-M):** make `serialize()` pure: use the cached `schema_snapshot`/`file_metadata` and refresh them only when the file path/mtime changes or on explicit load; give File Input controls explicit `path=` bindings (`push_property_change`). Fix the AGENTS.md wording.
* **Regression test:** `tests/unit/test_file_input_serialize.py::test_serialize_does_not_read_the_file` (monkeypatch `_read_file_based_on_type` to raise; `serialize()` must pass).
* **Effort:** M.

---

## BUG-018 - SQL editor erases its own diagnostics and revalidates every 800 ms forever

* **Severity:** Medium (the user rarely sees a persistent error; DuckDB `EXPLAIN` runs in a loop while any formula editor holds text).
* **Status:** **Fixed** (2026-10-22). The mechanism below was reproduced first, then the fix was verified: the five failing tests pass and the whole suite runs in one invocation without aborting.
* **Root cause:** `src/trigger_designer/qt/widgets/sql_formula_editor.py`
  * `:863` `cursor.mergeCharFormat(clean_format)` inside `update_error_highlights()` changes the document's formatting, which makes Qt emit `textChanged` (Qt 6.8.1).
  * `:586-594` `on_text_changed()` -> `if self.errors: self.errors.clear(); ...` and restarts `error_timer` (`ERROR_CHECK_DEBOUNCE_MS = 800`).
  * `:597-647` `check_for_errors()` ends with `update_error_highlights()` (`:647`) -> back to `:863` -> loop.
* **Resolution:** `update_error_highlights()` now paints the underline with `setExtraSelections` only and never writes to the document. The `mergeCharFormat` clear block was a leftover: commit `2390857` had already moved the error underline from document character formats to extra selections, but left the old clear in place. It was redundant (extra selections fully control the underline) and harmful (it emitted `textChanged`, wiped the diagnostics, and pushed the document onto the undo stack for a change the user never made). The dead `error_format` variable went with it; the live selection now uses the theme's `danger` colour, which is what `078e714` had intended. The selections are also applied unconditionally, so the underline of a fixed error no longer lingers - which is what the `on_text_changed` comment asked for in the first place.
* **Reproduce** (`tests.ui.test_formula_focus._make_content()` helper, then):
  ```python
  ew.set_text('" unfinished [a]'); ed = ew.editor
  # update_error_highlights called twice per check_for_errors; the 2nd time ed.errors == []
  # let the timer run for 3 s with APP.processEvents(): count check_for_errors calls
  ```
* **Verified output:**
  ```
  B errors at highlight: [[{'message': 'Unterminated string literal', 'line': 1, 'column': 0, 'length': 1, 'category': 'syntax'}], []] final: []
  C on_text_changed fired during check_for_errors: 2     (stack ends at sql_formula_editor.py:863 mergeCharFormat)
  C Qt 6.8.1
  LOOP valid   check_for_errors timer-driven calls in 3 s: 3 errors now: 0
  LOOP invalid check_for_errors timer-driven calls in 3 s: 3 errors now: 0
  ```
  `validate_section_text(0, '" unfinished [a]')` called directly returns the correct `Unterminated string literal` diagnostic, so validation itself is fine.
* **Failing tests explained:** `tests/ui/test_formula_focus.py::test_editor_diagnostics_replace_stale_section_error_without_rebuilding` (`label.text()` empty), `tests/ui/test_formula_node.py::test_duckdb_parser_failure_uses_sqlglot_error_location` (`assert False`), `::test_closed_string_followed_by_column_requires_operator` (`IndexError`, no errors), `::test_locationless_errors_do_not_underline_or_modify_editor_text` (`assert [] == ['Unknown function NOSUCHFUNC']`). `::test_incomplete_quotes_do_not_crash_editor` aborts the process (see BUG-020).
* **Recommended fix (S):** ~~in `update_error_highlights` only clear/merge formats when needed and wrap the formatting block in `blocker = QSignalBlocker(self.document())` ... or use `setExtraSelections` only~~ **done 2026-10-22** - `setExtraSelections` only, see the resolution above.
* **Regression test:** `tests/ui/test_formula_editor_loop.py` (new, 2026-10-22): `test_highlighting_does_not_fire_text_changed`, `test_highlighting_does_not_change_the_document`, `test_highlighting_does_not_touch_the_undo_stack`, `test_the_errors_survive_a_repaint`, `test_a_fixed_error_leaves_no_underline_behind`. On the old code the file aborts the process (exit -1073741819); with the fix all five pass.
* **Effort:** S.

---

## BUG-019 - `exec()` of generated code has no sandbox; `ENHANCED_EXECUTOR_GUIDE.md` documents features that do not exist

* **Severity:** Medium (design gap; the injection route is BUG-003).
* **Status:** Verified.
* **Evidence:** `executor.py:264` `exec(code, execution_globals, local_vars)` with the full builtins; one shared `execution_context` for the whole run (`:262-264`, `:373`). `SecurityConfig` (`executor.py:91-95`) has only `max_execution_time = 30.0` and `max_memory_mb = 512.0`. `docs/ENHANCED_EXECUTOR_GUIDE.md` documents `SecurityConfig(... allowed_imports={...})` (lines 53-57), "`allowed_imports: Set[str]`" / "`forbidden_functions: Set[str]`" (109-110) and presets (181-191, 263-266); `grep -rn "allowed_imports\|forbidden_" src` finds nothing. The memory limit is advisory: RSS delta measured once after exec returns (`:329-338`).
* **Impact:** plan 08 section 6 adds an AST policy + restricted builtins; the guide must not promise the nonexistent API in the meantime.
* **Recommended fix (S docs, L code):** now: rewrite the guide to state the real limits (time, RSS delta) and "no sandbox"; later: plan 08 `core/headless/code_policy.py`.
* **Regression test:** none for the docs fix; for plan 08's policy see its own tests (`all 32 malicious refused, 7 benign accepted`).
* **Effort:** S (docs), L (sandbox).

---

## BUG-020 - Test-suite health: 20 failed + 7 errors in `tests/ui`; full `pytest` aborts

* **Severity:** Medium (the suite cannot gate changes; a crash hides everything after it).
* **Status:** **Fixed** (2026-10-22). BUG-007 (the old nodeeditor) and BUG-018 (the editor wiping its own diagnostics) are both fixed. The suite runs green in one invocation and no longer aborts.
* **Current numbers (`QT_QPA_PLATFORM=offscreen`; re-measured 2026-10-22 after BUG-007 and BUG-018):**

  | Layer | Result | Time |
  |---|---|---|
  | `tests/unit` | **344 passed** (44 warnings) - 334 before, plus 10 new in `tests/unit/test_nodeeditor_api.py` | 10.2 s |
  | `tests/e2e` | **20 passed**, no more swallowed `AttributeError: 'super' object has no attribute 'setPositions'` tracebacks (BUG-007) | 4.1 s |
  | `tests/ui` | **429 passed, 0 failed, 0 errors** - 424 before, plus 5 new in `tests/ui/test_formula_editor_loop.py` | 26-45 s |
  | `pytest tests/` (all) | **793 passed, 6 skipped, 0 failed** - the 6 skips are the benchmarks, which need `--run-benchmarks`. 3 of 3 consecutive runs green, no abort | 28-49 s |

  README's "< 20 s full suite" (`tests/README.md`) still does not hold in this environment (28-49 s), but the suite no longer aborts.
* **What was failing, and why it is gone:**

  | Test id | Error summary | Root cause | Status |
  |---|---|---|---|
  | `test_canvas_grid_render.py` (6), `test_edge_geometry.py` (7 errors), `test_labels_groups.py` (1), `test_render_settings.py` (8) | `no attribute 'setPositions'` / `'MIN_GRID_SPACING_PX'` / `'detail_lod_threshold'` / `'updateDetailLod'` | BUG-007: installed nodeeditor too old | fixed - `nodeeditor-qtpy` 0.8.1 from PyPI |
  | `test_formula_focus.py::test_editor_diagnostics_replace_stale_section_error_without_rebuilding` | `AssertionError: assert 'Unterminated string literal' in ''` (`:82`) | BUG-018 | fixed |
  | `test_formula_node.py::test_duckdb_parser_failure_uses_sqlglot_error_location` | `assert False` (`:280`) | BUG-018 (errors list wiped) | fixed |
  | `test_formula_node.py::test_closed_string_followed_by_column_requires_operator` | `IndexError: list index out of range` (`:440`) | BUG-018 | fixed |
  | `test_formula_node.py::test_locationless_errors_do_not_underline_or_modify_editor_text` | `assert [] == ['Unknown function NOSUCHFUNC']` (`:545`) | BUG-018 | fixed |
  | `test_formula_node.py::test_incomplete_quotes_do_not_crash_editor` | process abort (exit 139) when run alone | BUG-018 | fixed |

* **Abort mechanism (confirmed 2026-10-22):** the abort was a side effect of BUG-018, not a separate Qt problem. `update_error_highlights()` wrote character formats into the document, which made Qt emit `textChanged`; the editor's `textChanged` handler cleared the diagnostics, so the failing tests left half-updated documents behind, and the deferred delete in `tests/conftest.py:196` faulted on them. With the highlight repaint no longer touching the document, the abort is gone - the whole suite now completes.
* **Recommended fix:** done. No `xfail` baseline file is needed; run the suite as one invocation again.
* **Regression test:** `tests/ui/test_formula_editor_loop.py` (new) pins the invariant that painting the diagnostics does not touch the document; on the old code that file aborts the process, with the fix all five pass.
* **Effort:** S (baseline file), M (fixes).

---

# LOW

## BUG-016 - File Output `check_file_path` is never called

* **Severity:** Low. A bad output directory is discovered at Run time as a Polars error instead of on the node.
* **Status:** Verified. `grep -rn check_file_path src`: definition at `file_output.py:181`, only a *different* `check_file_path` is called (`file_input.py:914`). The method validates the parent directory (`:181-198`) and sets `Directory does not exist`.
* **Recommended fix (S):** call it from the path edit handler and `processInputs` (`file_output.py:409-427`); set tooltip via `_set_node_tooltip`.
* **Regression test:** `tests/ui/test_file_output_path.py::test_missing_directory_marks_node_invalid`.
* **Effort:** S. **Affects:** plan 03.

## BUG-021 - Error-translation hazards: Windows `OSError` with `errno=None`; Polars "out of N values" is a batch size

* **Severity:** Low as defects (they are properties of the libraries), High as *traps* for plan 03's translator: a naive rule shows wrong numbers or misses a locked file.
* **Status:** Verified (reproduced).
* **Reproduce / verified output** (`sink_csv` onto a file opened with no sharing via `CreateFileW(... share=0)`, and a cast over a 300 001-row CSV with one bad value):
  ```
  P2 locked file -> OSError errno= None | The process cannot access the file because it is being used by another process. (os error 32): C:/Us...
  P3 sink_csv cast -> InvalidOperationError conversion from `str` to `i64` failed in column 'a' for 1 out of 64929 values: ["x"]
  P3 collect() cast -> InvalidOperationError ... for 1 out of 64929 values: ["x"]       (table size: 300001 rows)
  ```
  Read-only target: `PermissionError` with `errno None` (plan 03 O18). Neither `errno` nor `PermissionError` is reliable on Windows; match on the `(os error N)` text.
* **Recommended handling (S):** classification rules in plan 03: key on `(os error 32)` / `(os error 5)` text; never print `out of {m}` as the table total (print only the offending value and column). No code defect to fix in the repo.
* **Regression test:** plan 03 `test_td_in_*` locked-file and cast tests with real triggers (`tests/support/error_triggers.py`).
* **Effort:** S (part of plan 03). **Affects:** plan 03.

## BUG-022 - Stale or incorrect docs

* **Severity:** Low. Status: Verified (each quoted).
* **Items:**
  * `docs/SESSION_HANDOFF.md:12` says "**No pytest** installed" - pytest 9.1.1 + pytest-qt 4.5.0 are in the dev group (`pyproject.toml:154-155`) and about 785 tests exist. `:165-166` says `Join/union.py` is a 0-byte stub and "Union registered in enum but unimplemented" - it is 956 lines (`wc -l` verified) and tested by `tests/unit/test_union_node.py`. Lines 61 and 114 list Batch B (executor import seeding) as pending although `executor.py:174` `_seed_base_globals` exists. `:7` standing instructions reference `run.bat self` with `C:\Projects\TriggerEditor`.
  * `docs/NODE_REFERENCE.md:76-77` says `Join/union.py` is empty and Union has no implementation; the node table omits Union (only the icon row at `:71`). `README.md` has no mention of Union (grep: no match).
  * `CONTRIBUTING.md:12` tells contributors to run `uv sync`, which `pyproject.toml:14-20` says must not be used (it prunes the git-installed nodeeditor); `:20` lists `tests/integration/` as "Integration tests and demos" but the directory contains only `__pycache__`; "Python 3.13.12+" matches `requires-python`.
  * `AGENTS.md:49` (and the "Prefer the above" line) - see BUG-017: `registerInputWidget` is a whole-scene snapshot unless `path=` is given.
  * `ToDo.md` / `Todo.todo`: see "Claims not confirmed"; both are scratch notes with no dates.
  * `docs/ENHANCED_EXECUTOR_GUIDE.md`: see BUG-019.
  * Empty placeholders: `docs/POLARS_MIGRATION_SUMMARY.md` (0 bytes), `docs/Nodes.md` (85 bytes).
  * `docs/DESIGN_SYSTEM.md` line references (for example `transpose.py:77`) have drifted (brief 10.4).
* **Recommended fix (S):** one docs commit: delete the placeholders, correct the five statements above, add "Union" to `NODE_REFERENCE.md`, replace `uv sync` with the documented sync recipe, state the layer-by-layer test commands.
* **Regression test:** none (docs). Optional: a unit test that every file under `docs/` is non-empty.
* **Effort:** S.

## BUG-023 - Empty stub node files and enum members with no node

* **Severity:** Low. Status: Verified.
* **Evidence:** `wc -l`: `qt/widgets/nodes/Join/find_replace.py` 0, `qt/widgets/nodes/Documentation/comment.py` 0, `qt/tr_qt.py` 0, `qt/translations.py` 0. `core/node_configuration.py:32` `IONodes.BROWSER`, `:33` `IONodes.TEXT_INPUT`, `:58` `TransformNodes.ARRANGE` have no registered node (grep: no other references). (`Join/union.py` is **not** a stub; BUG-022.)
* **Impact:** the palette never shows them; the op-code ints still occupy `auto()` slots, so removing members renumbers every later op-code (`IntEnum` + `auto()`), which affects saved `.tds` files that store ints (brief 3.5).
* **Recommended fix (S):** delete the four empty files; leave the enum members but add a comment "reserved, do not renumber"; or convert to explicit values first.
* **Regression test:** `tests/unit/test_registry.py::test_every_enum_member_has_a_node_or_is_reserved`.
* **Effort:** S.

## BUG-024 - README claims Windows/macOS/Linux; tooling is Windows-only with hard-coded paths

* **Severity:** Low. Status: Verified (code/doc reading).
* **Evidence:** `README.md:19` platform badge "Windows | macOS | Linux", `:95` "The app targets Windows, macOS and Linux". But `scripts/sync-nodeeditor.ps1:22` (`C:\Projects\qtpy-nodeeditor`; `scripts/build.bat` no longer hard-codes it since the 2026-10-22 move to `nodeeditor-qtpy` from PyPI), `scripts/run.bat:17,21` (`C:\Projects\TriggerEditor\...` and a developer's home path), `run.bat` (repo root) the same, `pyproject.toml:94` Windows-only briefcase `sources` (`.venv/Lib/site-packages/nodeeditor`, a Windows venv layout), PyInstaller `trigger.spec`, and an Inno Setup script. There is no shell script, no macOS/Linux packaging, and `.venv/Lib/...` does not exist on POSIX (`lib/python3.13/site-packages`).
* **Recommended fix (S docs, M code):** reword README to "developed and packaged on Windows; macOS/Linux untested", or add a `scripts/run.sh` and a cross-platform nodeeditor install step. Replace hard-coded paths with `%~dp0`.
* **Regression test:** none (docs). **Effort:** S docs. **Affects:** plan 08 (scheduling on Linux hosts).

## BUG-025 - Bundled sample `savedfiles/3. in-formula-out.json` fails on Run

* **Severity:** Low. Status: Verified.
* **Evidence:** loading it and running: `Node execution failed for 'Formula': Binder Error: Cannot compare values of type VARCHAR and type INTEGER_LITERAL - an explicit cast is required (LINE 2: WHEN Difficulty > 7 ...)`. File Input deliberately reads CSV columns as `String` (brief 7.1), so a workflow written before that change compares text to a number. The Formula node also logs `Formula node failed: Section 1: ...` at load.
* **Recommended fix (S):** update the sample to `TRY_CAST(Difficulty AS INTEGER) > 7`, or remove it from the shipped samples; add the sample set to the e2e golden tests so this is caught.
* **Regression test:** extend `tests/e2e/test_workflow_goldens.py` with this file or delete the file. **Effort:** S.

## BUG-026 - DynamicRowBuilder datetime increment widget is a date-time editor where seconds are required

* **Severity:** Low. Status: Partially verified (code reading plus the failing operation; the GUI path was not driven). Listed as known in `docs/SESSION_HANDOFF.md` ("Known-remaining bugs").
* **Evidence:** `dynamic_row_builder.py:110` `self.increment_widget = self.create_value_widget(self.field_type)` creates a `QDateTimeEdit` for the `datetime` type (`:162-165`); `get_typed_value` returns `widget.dateTime().toPython()` (`:267-268`); `_increment_value` does `current + timedelta(seconds=increment)` (`:286`) and the generated code does the same (`:425`).
  ```
  >>> timedelta(seconds=datetime.now())
  TypeError unsupported type for timedelta seconds component: datetime.datetime
  ```
* **Recommended fix (S):** use a `QSpinBox`/`QDoubleSpinBox` (seconds) for the increment when `field_type == "datetime"` (the range fields keep the date-time editors).
* **Regression test:** `tests/unit/test_dynamic_row_builder.py::test_datetime_increment_generates_rows` (start/end datetimes, increment 3600 s -> N rows).
* **Effort:** S.

## BUG-027 - Working-tree state: concurrent edits, dead and non-importable `file_opener.py`, unguarded `__main__.py`

* **Severity:** Low. Status: Verified (facts only; **nothing was reverted or changed**).
* **`git status --short` / `git diff --stat` at the time of review:**
  ```
   M check_output.py                                   (377 lines of regenerated content + CRLF; BUG-013)
   M pyproject.toml                                    (+21: [tool.briefcase] project and Windows app sections)
   M src/trigger_designer/main.py                      (10 lines: _log_dir() treats a Briefcase bundle (python3.dll next to the app) like frozen)
   M src/trigger_designer/qt/helpers/file_opener.py    (4 lines: PySide6 imports -> qtpy)
   D src/trigger_designer/qt/models/model_pandas.py    (27 lines removed; no remaining importers: grep -rn model_pandas finds only docs/plan text)
   M uv.lock                                           (762 lines; CRLF churn plus 382/380 real line changes)
  ?? docs/plan/                                        (other agents' plan files; untouched)
  ?? src/trigger_designer/__main__.py                  (new)
  ```
* **Observations:**
  * `qt/helpers/file_opener.py` still imports `structlog` and `tagstudio.qt.helpers.silent_popen`; neither is installed (`ModuleNotFoundError: No module named 'structlog'`, `... 'tagstudio'`). Nothing imports the module (grep), so the edit (PySide6 -> qtpy) is cosmetic: the module cannot be imported either way. It is dead code copied from another project.
  * New `src/trigger_designer/__main__.py` calls `main()` at import time with no `if __name__ == "__main__":` guard (file content: `from trigger_designer.main import main` / `main()`); importing the module (for example by a tool that imports every module, or `pytest --doctest-modules`) starts the GUI. `python -m trigger_designer` works as intended.
  * `pyproject.toml` has two version numbers: `[project] version = "0.0.1"` (`:7`) and `[tool.briefcase] version = "0.0.1"` (`:78`) versus `core/constants.py:7` `VERSION = "0.1.0"` written into every `.tds` (`app_version`). Three sources of truth.
  * `main.py` `_log_dir()` is the only functional change; it was not exercised here.
* **Recommended fix (S):** after the owner commits the packaging work: delete `file_opener.py`, guard `__main__.py`, single-source the version (`importlib.metadata.version`).
* **Regression test:** `tests/unit/test_entrypoints.py::test_dunder_main_import_has_no_side_effects` (import with `main` patched).
* **Effort:** S.

## BUG-028 - Logging hazards

* **Severity:** Low. Status: Partially verified.
* **Evidence:** (a) `qt/helpers/global_logger.py:99` the fallback `print(f"[LOGGING-ERROR] Failed to log message '{message}': {e}")` itself raised `UnicodeEncodeError: 'charmap' codec can't encode character '\U0001f527'` when stdout was a cp1252 pipe (observed while running the probes without `PYTHONUTF8`); the app tees stdout in `main.py`, so this is mostly a headless/CLI hazard (plan 08 F11 notes the same print fallback). (b) `NodeExecutor._report_missing_dependency` -> `global_logger` is called from the executor's worker thread, but `LoggingDock.log` has no lock (brief 4.2; by code reading, not reproduced). (c) Many nodes log emoji in hot paths; log files are never pruned (brief 7.5).
* **Recommended fix (S):** make the fallback `print` use `errors="replace"` (or `logger.exception`), route executor-thread logging through a queued Qt signal, strip emoji for non-UTF-8 consoles in the CLI.
* **Regression test:** `tests/unit/test_global_logger.py::test_fallback_print_never_raises` (stdout encoded as cp1252, message with an emoji).
* **Effort:** S.

---

# Additions from plan 07 review

Source: `docs/plan/07-shaping-nodes.md`. Already covered (not repeated): `getSocketValue` first-match (BUG-008, plan 07 section 2 and pitfall 1), the `check_output.py`/lazy-run facts (BUG-004, BUG-013). Plan-only hazards with no existing code (Polars `pivot(aggregate_function="sum")` fills missing cells with 0 instead of null, re-verified here: `[{'i':'a','u':1,'v':0},...]` for `sum` vs `None` for `first`; no `.pivot(` exists under `src/`) are not bugs in the app and are left to the plan.

## BUG-029 - Filter expression and Formula run user SQL on an unrestricted DuckDB connection (file read and write from workflow text)

* **Severity:** High (security). Medium if workflows are only ever authored by the user; High because `.tds` files are shared and the Filter runs on open.
* **Status:** Verified (DuckDB behaviour reproduced with the exact query shapes the nodes build; the live-on-open path is by code reading).
* **Symptoms:** A Filter expression or Formula section can read any local file the process can read (`read_csv`, `read_text`, `glob`) and, because the Filter query is pasted after `WHERE` and executed as a string, can append a second statement (`COPY ... TO 'file'`, `ATTACH`, `INSTALL`) that DuckDB also executes.
* **Root cause:** user text goes into a plain `duckdb.connect(":memory:")` with default settings (external access on, no `lock_configuration`) and no statement check:
  * `src/trigger_designer/qt/widgets/nodes/Preparation/filter.py:819-831`
    ```python
    with duckdb.connect(":memory:") as duck:
        duck.register("df_filter", self.incom_data)
        self.data = duck.execute(f"SELECT * FROM df_filter WHERE {prepared}").pl()
    ```
    `_prepare_filter_sql` (`:777-789`) only normalises quotes, aliases and column names. The same text is embedded into generated code at `filter.py:1023-1039`.
  * `qt/widgets/nodes/Preparation/formula.py:1047-1050` and `:1074-1085` (live), `:1302-1313` (generated code): `_section_query` (`:967-998`) wraps `formula_text` in `SELECT *, <text> AS "t"` with no validation, so a scalar sub-select is accepted.
  * The Filter live path `_update_expression_data` runs when the node evaluates, which includes opening a saved workflow, so the statement executes without pressing Run (by code reading; the `COPY` itself was run directly on the same query string).
* **Reproduce** (`uv run --no-sync python`, DuckDB 1.5.5):
  ```python
  df = pl.DataFrame({"x": [1, 2, 3]})
  with duckdb.connect(":memory:") as duck:
      duck.register("df_filter", df)
      p = f"x IN (SELECT 1 FROM read_csv('{secret}') WHERE k='topsecret')"
      duck.execute(f"SELECT * FROM df_filter WHERE {p}").pl()              # Filter read
      duck.execute(f"SELECT * FROM df_filter WHERE 1=1; COPY (SELECT 42 AS pwn) TO '{out}' (FORMAT CSV)")
  duck.execute(f"SELECT *, (SELECT k FROM read_csv('{secret}') LIMIT 1) AS y FROM df_for_duck")  # Formula read
  ```
* **Verified output:** Filter read returned `(1, 1)` (the row matched on file content); after the multi-statement query `leak.csv` existed and contained `pwn` / `42`; Formula returned `{'x': 1, 'y': 'topsecret'}`.
* **Impact:** a shared `.tds` can exfiltrate a file into the table (and from there into an exported workpaper) or write files, with no Run click. BUG-003 and BUG-019 describe the Python-level hole; this one needs no Python injection and survives any `!r` quoting fix. Plan 07's SQL Query and Multi-Field Formula nodes (section 4.13) introduce a sandbox but the two existing nodes keep running outside it.
* **Recommended fix (M):** put one helper (plan 07's `sql_sandbox.py`, or a smaller `core/utils/duck_safe.connect()`) in front of every DuckDB use: `SET enable_external_access=false` then `SET lock_configuration=true` as the last statement on each new connection (verified to block `read_csv`, `COPY`, `ATTACH` and re-enabling access, BUG-030), reject text that is not exactly one statement (for the Filter wrap the expression: `SELECT * FROM df_filter WHERE (<expr>)` and refuse a `;` after masking quotes), and use it in `filter.py`, `formula.py` and the two generated-code templates.
* **Regression test:** `tests/unit/test_duckdb_safety.py::test_filter_and_formula_cannot_read_or_write_files` (expression with `read_csv(...)` raises; expression `1=1; COPY ...` raises and no file appears).
* **Effort:** M.

## BUG-030 - DuckDB statement typing and `lock_configuration` are not a read-only guard

* **Severity:** Medium (hazard; it decides whether the plan 07 SQL nodes are safe and applies to any future DuckDB-executing node).
* **Status:** Verified (DuckDB 1.5.5).
* **Evidence:** `con.extract_statements(q)[0].type` is `StatementType.SELECT` for `pragma version`, `describe select 1`, `from range(3)` and `select * from read_csv('x.csv')`. After `SET enable_external_access=false; SET lock_configuration=true`: `select * from read_csv('x.csv')` raises `PermissionException` and `SET enable_external_access=true` raises `InvalidInputException`, but `create table t as select 1 a` and `pragma database_list` still run.
* **Impact:** a "must be a SELECT statement" check is bypassed by PRAGMA/DESCRIBE/FROM-file forms; the config lock stops file and extension access but not in-memory DDL, so a connection that outlives one query keeps state. Any fix for BUG-029 must combine: lock, one fresh connection per run, single-statement check, and a leading-keyword allow-list.
* **Recommended fix (S):** see BUG-029; document the two facts in the helper's docstring so the allow-list is not "simplified" to a statement-type test.
* **Regression test:** `tests/unit/test_duckdb_safety.py::test_statement_type_alone_is_not_enough` (asserts the four typed-SELECT cases above are rejected by the helper).
* **Effort:** S.

## BUG-031 - `evalImplementation` requires every input; optional inputs need a per-node override

* **Severity:** Low (latent; affects nodes that want optional inputs, plan 07 F2: SQL `t2`/`t3`).
* **Status:** Verified (code reading).
* **Root cause:** `src/trigger_designer/qt/node_base.py:816-834`
  ```python
  for i in range(len(self.inputs)):
      input_node = self.getInput(i)
      if not input_node:
          self.markInvalid(); self.markDescendantsDirty()
          self._set_node_tooltip(f"Input {i} is not connected")
          return None
  ```
  Any unconnected socket makes the node invalid and its tooltip says "not connected", so a node with an optional input cannot evaluate live. The only existing override is `qt/widgets/nodes/Join/union.py:868` (`unknown.py:78` is a stub); a third node copying neither pattern gets the all-required behaviour.
* **Impact:** every new node with optional sockets must reimplement the loop (and the BUG-008 socket resolution with it); an easy place for copy-paste divergence, e.g. forgetting `markDescendantsDirty()`.
* **Recommended fix (S):** add a class attribute `optional_inputs: frozenset[int] = frozenset()` and skip those indexes (pass `None` into `processInputs`) in the base loop; keep Union's override or migrate it.
* **Regression test:** `tests/unit/test_node_base_optional_inputs.py::test_unconnected_optional_input_is_passed_as_none`.
* **Effort:** S.

## BUG-032 - Generated Formula code embeds the query in `'''...'''`; error path leaks the connection

* **Severity:** Low.
* **Status:** Verified (the generated-code shape executed with a harmless formula).
* **Root cause:** `qt/widgets/nodes/Preparation/formula.py:1313`: ``f"df_for_duck = duck.execute('''{combined_query}''').pl()"``. The Filter node already switched to `{query!r}` for this reason (`filter.py:1023-1025` comment); Formula did not. `duck.close()` (`:1321`) is the last emitted line, so a failing query leaves the connection open for the rest of the shared execution context.
* **Reproduce / verified output:** formula text `'''x'''`: the live DuckDB path returns `"'x'"`; the generated line raises `SyntaxError` at Run. (A formula with backslashes was also compared; results matched in the cases tried, but escapes in a non-raw triple-quoted string are interpreted by Python first, so use `!r` rather than reason about each case.)
* **Impact:** Live result and Run result diverge (live works, Run fails); one more route for BUG-003-style injection into `exec`.
* **Recommended fix (S):** `duck.execute({combined_query!r})` and wrap in `try/finally: duck.close()` (or `with duckdb.connect(...) as duck:`).
* **Regression test:** `tests/unit/test_formula_codegen.py::test_formula_with_triple_quotes_compiles` (`compile(get_code(), ...)` and exec yields the same frame as live).
* **Effort:** S.

---

# Claims not confirmed (status Unverified)

| Claim | Finding |
|---|---|
| "`isModified()` is a stub" (plan 02 line 57, 1477) | **Not confirmed.** The installed library delegates: `.venv/Lib/site-packages/nodeeditor/node_editor_widget.py:60-66` `isModified()` returns `self.scene.isModified()` and `node_scene.py:176-182` returns `self.has_been_modified`. The `filename is not None` stub quoted in the plan is `isFilenameSet()` (`node_editor_widget.py:74`). The repo has no override (`grep -rn isModified src`: none; `tests/ui/test_design_window_title.py:46` monkeypatches it). Plan 02 can use either `isModified()` or `scene.has_been_modified`; the caveat that `has_been_modified` is also set by undo/history (`undo/history.py:102`, `controller.py:211`, `node_base.py:623`) stands. |
| `ToDo.md` has a stale "File Input not passing data" entry | **Not found.** `ToDo.md` is 18 lines (Sockets hover, Output Node browse button, Filter suggestions/strip function); `grep -n -i "file input\|passing" ToDo.md` returns nothing. `Todo.todo` has two items (workflow version check, Cleansing serialization). The stale entry may have been removed already. |
| "Cleansing settings do not serialize properly" (`Todo.todo`) | **Not reproduced at the model level.** Round trip of a modified Cleansing node: all 14 schema keys are in `serialize()` output and a fresh node restored them (`replace_null_strings=False`, `case_modification='upper'`, `remove_numbers=True`, `selected_fields=['x','y']`, `remove_null_rows=True`); default list not shared between nodes (`S8b default list shared between nodes: False`). Not tested: widget state after load (checkboxes) and `null_strategy` (an attribute set in `__init__`, not in `serialized_state_schema`). Treat as possibly fixed; re-test through the dock before closing the todo. |
| "`WorkflowWorker`... progress dialog on load has no cancel" | Confirmed (BUG-011). |
| "Unwired File Output: `get_code()` raises `ValueError`" (brief 7.2, plan 03 C13) | **Outdated.** `file_output.py:231-237` now *returns* code `raise ValueError('File Output: no incoming data ...')`, so the error is raised inside `exec` and surfaces as a normal `NodeExecutionError` (verified: `Node execution failed for 'File Output': File Output: no incoming data — connect an input`). The `UnboundLocalError` (BUG-010) is therefore latent, not active for File Output. |

---

# Recommended fix order

Fix before implementing each plan (smallest, riskiest first):

1. **Immediately, before any plan (all S):** BUG-001 (panic as success, 30 min), BUG-010 (one-line `node_name` move), BUG-012 (cycle leaves Run disabled), BUG-013 step 1+2 (`git rm --cached check_output.py`, stop writing into the CWD). Also BUG-002 (save truncation): it is data loss and a 25-line override. **BUG-018 and BUG-007 were fixed on 2026-10-22** and are off this list.
2. **Before plan 03 (plain-language errors):** BUG-001, BUG-009 (exception fields + tooltip), BUG-010, BUG-021 handling rules. These are plan 03's own Step 4 and must land together.
3. **Before plan 02 (audit trail):** BUG-001, BUG-009 (`ExecutionResult.exception`), BUG-005 (re-evaluate on Run), BUG-013 (stable variable names, no CWD write), BUG-015 (carry metadata keys), BUG-017 (pure `serialize()`), BUG-008 only if the recorder uses `getSocketValue` (it must not).
4. **Before plan 01 (input types):** BUG-003 (`!r` quoting everywhere; plan 01 adds many user strings), BUG-014 (relative paths), BUG-017 (serialize re-read), BUG-011 (Cancel on load) and BUG-002 (non-ASCII names).
5. **Before plan 06 (workpaper export):** BUG-006 (Excel writer; plan 06 step 1 is exactly this), BUG-008 (Summary and Exceptions from one node), BUG-002.
6. **Before plans 04 and 05 (audit nodes, data profile):** BUG-001 (heavy Rust code panics), BUG-004 (nodes must collect inside `get_code()`; add the plan-level `collect_schema()` check), BUG-005, BUG-008 (multi-output nodes into one consumer), BUG-006 (profile export).
7. **Before plan 08 (CLI and scheduling):** BUG-001, BUG-003 + BUG-019 (code policy), BUG-005, BUG-010, BUG-011 (hard cancel needs the subprocess runner), BUG-013, BUG-014, BUG-015, BUG-024, BUG-028.
8. **Environment:** resolved on 2026-10-22. BUG-007 (the nodeeditor pin) and BUG-020 (the failing-test baseline and the suite abort) are both fixed, so the UI tests are a usable gate: `pytest tests/` is 793 passed / 6 skipped / 0 failed.
9. **Last / opportunistic:** BUG-016, BUG-022 to BUG-027.

# Quick wins (under one hour each)

| Bug | Change | Where |
|---|---|---|
| BUG-010 | Move `node_name = getattr(...)` above `code = node.get_code()` | `executor.py:310-311` |
| BUG-001 | `except BaseException` in the exec thread; try/except around `task()` in the worker loop | `executor.py:266`, `:172` |
| BUG-012 | Compute `sorted_nodes` before disabling the button; do not re-raise the cycle error | `workflow_execution_mixin.py:57-61`, `design_window.py:690-696` |
| BUG-013 | `git rm --cached check_output.py`; add `encoding="utf-8"` and a path argument to `getPyFile` | `design_window.py:698-706` |
| BUG-018 | ~~Block document signals around `mergeCharFormat` in `update_error_highlights`~~ **done 2026-10-22:** drop the document write, paint with `setExtraSelections` only | `sql_formula_editor.py:852-899` |
| BUG-015 | Warn on newer `schema_version`; carry extra `workflow_metadata` keys; replace `utcnow()` | `design_window.py:461-467`, `performance_scene.py:166-173` |
| BUG-016 | Call `check_file_path()` from the path handler and `processInputs` | `file_output.py:181`, `:409-427` |
| BUG-006 (interim) | Show a message instead of only `logger.error` when the preview Excel export fails | `polars_table_viewer.py:1195-1208` |
| BUG-007 (interim) | Add `test_installed_nodeeditor_has_required_api` so the mismatch is one readable failure | new `tests/unit/test_nodeeditor_api.py` |
| BUG-026 | Spin box for the datetime increment | `dynamic_row_builder.py:110, 162` |
| BUG-025 | `TRY_CAST(Difficulty AS INTEGER)` in the sample, or remove it | `savedfiles/3. in-formula-out.json` |
| BUG-022/023 | Docs corrections, delete empty placeholder files | `docs/`, stub `.py` files |
| BUG-027 | Guard `__main__.py` with `if __name__ == "__main__":` | `src/trigger_designer/__main__.py` |

Larger but high-value (a few hours): BUG-002 (atomic UTF-8 save override), BUG-003 (`!r` literal helper at about 8 sites), BUG-009 (exception preservation + node tooltip), BUG-008 (socket-index helper, 18 call sites).

---

# Pending sources

* Plans read in full or by targeted search: `00-codebase-brief.md`, `01`, `02`, `03`, `04`, `05`, `06`, `08` (04 and 08 appeared during the review; their verified facts F7, F9, F10, X3 are incorporated above and cross-referenced in BUG-003, BUG-010, BUG-013, BUG-015 and BUG-002).
* Plan 07 (`07-shaping-nodes.md`) was reviewed later; its additions are BUG-029 to BUG-032 ("Additions from plan 07 review").
* Plans 01-06 and 08 were still being edited by other agents; findings that originate in them were re-verified against the code, not copied.
* Not covered: GUI-driven reproduction of BUG-026 and BUG-028(b); the packaged (PyInstaller/Briefcase) build; the uncommitted `main.py` `_log_dir()` change; performance regressions (see `docs/PERFORMANCE_PROFILING_FINDINGS.md`).
