# Testing

`tests/README.md` is the short version; this page is the working manual.
Counts below were measured on a clean checkout of commit `e2b610a` (a detached
`git worktree`, so other people's uncommitted edits could not interfere) on
2026-10-30, Windows 11, Python 3.14.8, with other jobs competing for the CPU
(wall times are therefore pessimistic).

## Layers

| Layer | Directory | What it may use | Marker (automatic) |
|---|---|---|---|
| Unit | `tests/unit` | Logic, parsing, schema, model code, a node built in memory with a `TriggerSubWindow` and `Edge` (no layouts, no show). Qt is available but not driven. | `unit` |
| UI | `tests/ui` | Offscreen widgets through `pytest-qt` (`qtbot`): Config Dock layouts, signals, focus, undo/redo through the dock, canvas rendering. | `ui` |
| E2E | `tests/e2e` | Checked-in workflows loaded and run through the real app (`fileLoad`, `executeWorkflow`, a real `WorkflowWorker` thread) and compared with frozen outputs or hand-computed rows. | `e2e` |
| Benchmarks | `tests/benchmarks` | Memory and wall-clock budgets. **Skipped unless `--run-benchmarks`.** | `benchmark` |
| Manual | `tests/manual` | Demo scripts for a human (`*_demo.py` is not collected). | none |
| `tests/integration` | | Empty (only `__pycache__`). `CONTRIBUTING.md` still says it holds tests. | |

Put a test in the **lowest layer that can still fail for the bug**. The layer
marker comes from the folder (`tests/conftest.py::pytest_collection_modifyitems`);
`--strict-markers` makes a typo'd marker an error. `slow` is the only marker you
add by hand.

## Commands

Always name a layer or file. **Never run bare `pytest`** (one run takes many
minutes, and a crash in one layer hides the others). Use the venv interpreter
directly (no `uv` sync side effects):

```powershell
.venv\Scripts\python.exe -m ruff format <files>
.venv\Scripts\python.exe -m ruff check <files>
.venv\Scripts\python.exe -m pytest tests\unit\test_record_id_core.py -q         # one file
.venv\Scripts\python.exe -m pytest tests\unit -q                                # a layer
.venv\Scripts\python.exe -m pytest tests\ui -k "duplicates and undo" -q -s      # -s shows stdout
.venv\Scripts\python.exe -m pytest tests\benchmarks --run-benchmarks -s         # opt in
$env:PYTHONIOENCODING = "utf-8"    # when piping output: the app logs emoji
```

`QT_QPA_PLATFORM=offscreen` and a throwaway `TRIGGER_DESIGNER_DATA_DIR` are set
by `tests/conftest.py` before anything imports Qt, so no display is needed and a
developer's real preferences are never read or written. `timeout = 120`
seconds per test with a thread dump (`timeout_method = "thread"`). `pytest-xdist` is
**not installed or declared** even though `tests/README.md` mentions `-n auto`.

### Baselines (commit `e2b610a`, clean worktree)

| Run | Result | Wall time |
|---|---|---|
| `pytest tests/unit` | **2233 passed, 4 skipped, 1 xpassed** | 6 min 28 s |
| `pytest tests/e2e` | **102 passed, 1 failed** (`test_workflow_goldens.py::test_file_outputs_match_golden[split]`: the output has a new `column_1`; the golden was regenerated afterwards in `c3035e5`) | 42 s |
| `pytest tests/ui` | **974 passed, 5 failed** (all `test_no_console_prints.py::test_no_file_prints_to_the_console[...]` for CLI modules such as `cli/commands/validate.py`; the CLI was in progress, prints on purpose, and the guard has to learn that) | 4 min 24 s |

### Focused sets, as of `511db02` (2026-10-31, working tree with other people's uncommitted edits)

The executor thread-leak fix was in progress, so the full layers were not re-run. These
files were run in two sets with `uv run --project . pytest <files> -q`:

| Files | Result |
|---|---|
| `tests/unit/test_file_output.py`, `tests/ui/test_file_output_dock.py` | 39 passed in 9 s |
| `tests/unit/test_headless_workpaper_paths.py`, `tests/e2e/test_cli_workpaper.py` | 15 passed, 1 failed in 24 s. The failure is `test_cli_workpaper.py::test_workflow_sheet_never_shows_staging_names_and_follows_input_dir` (it compares an `as_posix()` path with the Windows path stored in the sheet). |

What these cover: Parquet compression (`test_file_output.py`: codec written, `None` read as
Snappy, unknown codec an error, old `use_streaming` key tolerated), the `.xls` rule (writer and
CLI run raise `TD-OUT-015`, dock rewrites the name), the CLI's Workpaper Output handling
(`--output-dir`, `--param`, versioning, CSV sidecar, `source_files`, `paths --relativize`).
Re-measure the full layers once the executor change is committed.

Skips: `test_headless_paths.py` (a drive path is native on Windows / POSIX only),
`test_inputs_listing.py` (symlinks need privileges). The `xpass`
(`test_audit_store.py::test_record_file_is_read_only`) is expected for an
elevated user, who can write a read-only file. Re-measure before quoting these;
the unit layer in particular grows with every node.

The brief's old baseline (334 unit, 20 e2e, 404 ui with 27 failures, a process abort
in a `tests/ui` teardown) no longer applies: the installed `nodeeditor-qtpy` is
now the PyPI release the repo expects.

### Known flaky or slow spots

* The unit layer is slow mostly because of Qt node construction and per-test
  DuckDB/Polars start-up; expect minutes, not seconds.
* Old teardown aborts (`Fatal Python error: Aborted`) came from PySide6 destroying
  a top-level widget whose C++ side was already gone. `_no_leaked_qt_windows`
  (autouse) deletes leftovers in a defined order; if you see an abort, look for a
  test that creates a window outside `qtbot.addWidget` or keeps a QThread alive.
* **Never create a second `QApplication`** (fast fail `0xC0000409`). Use the
  `qapp` fixture, or `QApplication.instance() or QApplication([])` in a module
  that must run alone.
* Hash-join and group-by output order is not guaranteed; goldens for those are
  compared order-insensitively (`WorkflowCase.unordered_goldens`, or
  `assert_frame_golden(..., sort_by=[...])`).
* Anything touching real time (the lock timeout `LOCK_TIMEOUT_S`, the 5 s error
  enrichment settle guard, debounce timers) is shrunk by monkeypatching module
  constants; do not add real sleeps.

## Fixtures and helpers

`tests/conftest.py`

| Fixture | Purpose |
|---|---|
| `qapp` (session, autouse) | The one `QApplication`. |
| `_no_leaked_qt_windows` (autouse) | Deletes top-level widgets a test left, clears the global logger window. |
| `clean_preferences` | A fresh preference store under `tmp_path`; resets the singleton. |
| `theme_manager` | A `ThemeManager` with built-in themes and user themes in tmp. |
| `no_modal_dialogs` | Replaces the modal progress dialog and `QMessageBox`, makes `QTimer.singleShot` immediate, stubs `getPyFile`; returns captured warnings. Applied by default to `tests/e2e` (`2bdefa8`). Use it for any test that loads or runs a workflow. |

`tests/support/` (import from the specific module):

| Module | Provides |
|---|---|
| `workflows.py` | `WorkflowCase` (a checked-in workflow and its expectations), `materialize(case, tmp_path, ...)` (copies the workflow to tmp and rewrites every File Input/Output path so a run never touches the repo), `run_workflow_and_wait(qtbot, window, timeout_ms=90_000)`, `nodes_titled`, `executed_frame(window, node, index=0)`. |
| `corpus.py` | The e2e case table (`ALL_NODES_CASE`, `FILE_OUTPUT_CASES`) and why two cases use locally owned copies under `tests/e2e/workflows/` (CSV columns are read as strings). |
| `frames.py` | `read_frame`, `assert_frames_match` (values and column identity; dtypes ignored), `assert_frame_golden(frame, name, *, sort_by=None)`, `GOLDEN_DIR`, `UPDATE_ENV`. |
| `flush.py` | `flush(node)` / `live_value(node)`: run the evaluation a Config Dock edit left pending (a node runs when it is left). **Call it before reading a node's output after changing a setting.** |
| `qt_widgets.py` | `dispose_plot_widget` for tests that draw charts. |
| `audit_ledger.py` | `make_ledger()` -> `Ledger(frame, planted)`: a deterministic synthetic general ledger (2,413 rows; 2,013 `GL-` and 400 `AP-` rows, all text columns) with anomalies planted on disjoint ranges so every expected count is exact; its own SplitMix64 generator (no library randomness). `Ledger.write_csv(dir)`, `ledger_lazy()`. |
| `audit_demo.py` | `DemoNode`/`DemoContent`: a tiny unregistered audit node built from the shared base, and `demo_graph(frame, node_cls=DemoNode)` -> `(window, source, node)`. Template for audit node tests. |
| `audit_helpers.py` | Run-record tests: `make_record`, `make_record_dict`, `make_node`, `make_fingerprint`, `FakeNode`, `FakeResult` (carries the fields the real `ExecutionResult` lacks; see the audit known gap), `make_recorder`, `drive`, and workflow builders `build_workflow`, `build_window`, `run_and_load_record`, `newest_record`, `write_orders`; the fixed `ORDERS_SHA256`. |
| `input_fixtures.py` | Byte-identical input files: monthly/nested/natural-order CSV folders, Parquet, JSON, SQLite, DuckDB, multi-sheet xlsx, many CSVs. |
| `profile_fixtures.py` | The 10-row `FX` frame that exercises each Data Profile rule with hand-computed expectations. |
| `cli.py` | CLI tests (in progress): `run_cli`, `spawn_cli`, `call_main`, `synthetic_workflow`, `write_workflow`; sets `TRIGGER_DESIGNER_DATA_DIR` and `TRIGGER_DESIGNER_STATE_DIR`. |

## Goldens

E2E expectations live in `tests/e2e/fixtures/expected/*.csv` (workflow outputs,
Data Profile, audit tables), `tests/e2e/fixtures/audit/` (inputs and one expected
messy-header output) and are compared with `assert_frame_golden`. The audit run
record e2e tests instead pin hard-coded hashes (`ORDERS_SHA256`,
`orders_messy.expected.csv`), not an updatable CSV.

**Update one golden safely**

```powershell
# 1. be sure the diff you are about to freeze is intended: run the test first and read the failure
.venv\Scripts\python.exe -m pytest tests\e2e\test_workflow_goldens.py -k "split" -q
# 2. rewrite only the selected case
$env:TRIGGER_UPDATE_E2E_GOLDENS = "1"
.venv\Scripts\python.exe -m pytest tests\e2e\test_workflow_goldens.py -k "split" -q
Remove-Item Env:TRIGGER_UPDATE_E2E_GOLDENS
# 3. review exactly what changed, and nothing else
git diff -- tests/e2e/fixtures/expected
```

Rules: select with `-k` (an unfiltered update rewrites every golden in the layer);
update is *the* way a regression gets frozen, so the diff must be explained in the
commit message; keep property assertions next to a golden that could freeze a bug
(the running-total test also asserts a cumulative sum per group); a golden whose
order is not part of the contract needs `sort_by`/`unordered_goldens`; goldens are
frozen from tracked sample data, never from the CSVs under `savedfiles/` (those
came from a file that no longer exists). Do not commit a changed
`savedfiles/**` or `check_output.py` produced by running a workflow.

## Benchmarks

Opt-in with `--run-benchmarks` (otherwise the tests are collected and skipped).

| File | Measures |
|---|---|
| `test_audit_overhead.py` | Run-record overhead on a 1,000,000-row CSV (File Input -> Normalize -> Sort -> Unique -> File Output parquet): recording off versus each row-count mode (median of 3 after a warm-up), plus a hashing throughput floor. Budgets are asserted. |
| `test_audit_perf.py` | The five audit tests on the synthetic ledger. |
| `test_polars_table_viewer_perf.py`, `test_memory_optimization.py` | Preview table model creation; memory-optimised reading. |

Benchmarks assert budgets, so run them on an otherwise idle machine; a failure on
a loaded laptop is not a regression until it repeats.

## Conventions for node tests

(Details and a worked example in `adding-a-node.md`.)

* **Unit (`test_<node>_core.py`)**: test the Qt-free function with frames built in
  the test; expected values written by hand from the input (not copied from output);
  one parametrised case per error code, asserting the *code*; the
  `ERROR_CODES`/catalogue registration check; laziness (`LazyFrame` in, `LazyFrame`
  out, no eager collect of the input); zero-row input keeps its dtypes; **live ==
  generated code** (`node.eval()` then `exec(node.get_code())` and
  `generated.equals(live)`); an unwired node's code still defines every output
  variable; Qt-free (`test_core_has_no_qt_import`).
* **UI (`test_<node>_dock.py`)**: build the node in a `TriggerSubWindow` (or
  `demo_graph` for audit nodes), `ConfigDock().updateConfig([node.grNode])`, call
  `scene.history.storeHistory("Baseline")` first, drive a control, `flush(node)`,
  assert the model and the output, then `history.undo()` / `redo()` and assert the
  control *and* the model; check the empty state and a save/load round trip.
  Always `qtbot.addWidget(window)`.
* **E2E (`test_<node>_workflow.py`)**: File Input -> node -> File Output built
  with `get_class_from_opcode(...)` and `Edge`, `run_workflow_and_wait`, read
  the written file with `read_frame`, compare with rows computed by hand. Use
  `no_modal_dialogs` (autouse in this layer).
* **Security tests** assert the code *and* that nothing was written
  (`security-model.md`).
* **Run-record tests** drive `RunRecorder` with `make_recorder`/`drive` (unit) or a
  real window (`build_workflow`, `run_and_load_record`) and assert hash chain
  properties through `verify_store`.
* Never read the developer's real preferences, app data or `savedfiles/` in place;
  use `tmp_path`, `clean_preferences` and `materialize`.
* Do not weaken an assertion to make a test pass; if a golden is wrong, fix the
  cause and regenerate it deliberately.

## Static checks

`ruff format` / `ruff check` (pinned 0.17.2) and `ty check --no-progress` over
`src` and `scripts` run in pre-commit. Several tests are really lint rules and
will fail your change: `test_codegen_no_unsafe_quotes.py` (AST scan of code
generators), `test_no_console_prints.py` (no `print`), `test_docs_present.py`
(no empty doc files, the executor guide documents only real features),
`test_packaging_spec.py` (`trigger.spec` core hidden imports),
`test_op_catalog_matches_registry.py` (op catalogue vs registry),
`test_error_code_registry.py` (error literals), `test_node_titles.py`.
