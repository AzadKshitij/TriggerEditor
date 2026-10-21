# Test suite

The suite is split into layers that differ in *what they can break*. Each layer
is marked automatically from its directory by `tests/conftest.py`, so a test
only has to live in the right folder.

| Layer | Directory | Runs | Marker |
|---|---|---|---|
| Unit | `tests/unit` | Pure logic, parsing, schema and model code. No widget layouts, no real windows. | `unit` |
| UI | `tests/ui` | Offscreen Qt widgets driven through `pytest-qt`: layouts, signals, focus, docks. | `ui` |
| End-to-end | `tests/e2e` | Checked-in workflow files loaded and run through the real app, compared with frozen outputs. | `e2e` |
| Benchmarks | `tests/benchmarks` | Memory/time measurements. Skipped unless `--run-benchmarks`. | `benchmark` |
| Manual | `tests/manual` | Demos for a human to look at. Not collected (`*_demo.py`). | - |

## Commands

```powershell
# Everything CI runs (< 20 s on a laptop, no benchmarks)
uv run --project . pytest

# One layer at a time
uv run --project . pytest tests/unit
uv run --project . pytest tests/ui
uv run --project . pytest tests/e2e

# Parallel (about a third faster at the current size)
uv run --project . pytest -n auto --dist loadscope

# Measurements (slow, not part of the default suite)
uv run --project . pytest tests/benchmarks --run-benchmarks

# One test, with its stdout
uv run --project . pytest tests/e2e -k select -s
```

`QT_QPA_PLATFORM=offscreen` is set by the suite itself; no display is needed.
On Windows, set `PYTHONIOENCODING=utf-8` when piping output through a tool that
does not use UTF-8 (the app prints emoji).

## How the E2E layer works

`tests/support/corpus.py` is the case table: each `WorkflowCase` names a
checked-in workflow, the input files its File Input nodes should read, and the
output files it should write. `tests/support/workflows.py` copies the workflow
into a temp directory and rewrites every absolute path, so a run never touches
the repository or the developer's files.

The test then does what the Run button does - `fileLoad`, then
`executeWorkflow` (a real `WorkflowWorker` thread) - and compares each written
file with a frozen golden under `tests/e2e/fixtures/expected`.

Two cases use a locally owned workflow under `tests/e2e/workflows/`. They were
authored against a build that inferred numeric CSV dtypes; File Input now reads
CSV as strings on purpose, so the local copies add an explicit `TRY_CAST` / a
Formula node. The comment in `corpus.py` records why.

Some goldens are compared order-insensitively because the run does not promise
an order (Polars' hash join); the case marks them in `unordered_goldens`.

### Regenerating goldens

```powershell
$env:TRIGGER_UPDATE_E2E_GOLDENS = "1"
uv run --project . pytest tests/e2e
Remove-Item Env:TRIGGER_UPDATE_E2E_GOLDENS
```

This rewrites every golden from the current behaviour, so **read the diff**:
an update is also how a regression gets frozen in. The running-total test
carries a property assertion (cumulative sum per group) next to the golden for
exactly that reason.

The goldens are frozen from the tracked sample data. The CSVs under
`savedfiles/` were produced from a `check.csv` that was never checked in, so
they are not usable as expectations.

## Rules of thumb

- **Put the test in the lowest layer that can still fail for the bug.** Logic
  in `unit`, widget behaviour in `ui`, whole-workflow wiring in `e2e`.
- **One test, one reason to fail.** A test that asserts five things gives five
  ways to be flaky and one line to read.
- **No sleeping.** `qtbot.waitSignal`/`waitUntil` and the helpers in
  `tests/support` cover all waiting.
- **Never let a parent window be garbage collected while the test runs.**
  `qtbot.addWidget` stores weak references; a parent that goes out of scope
  deletes its children mid-test. Teardown destroys objects with
  `deleteLater()` + `sendPostedEvents(DeferredDelete)` while the wrapper is
  still alive.
- **Hold a running `QThread` until it finishes.** `executeWorkflow` drops its
  own reference in the finished handler; if Python then collects the worker
  before `run()` returns, Qt aborts the process. `run_workflow_and_wait`
  captures the worker and calls `wait()` - keep that.

## Conventions

`tests/conftest.py` provides:

- `qapp` - a single `QApplication` for the whole session.
- `no_modal_dialogs` - stubs the load/run progress dialog and `QMessageBox`,
  and captures the code `getPyFile` would write. Returns
  `{"warnings": [...], "run_code": [...]}`.
- Autouse cleanup that hides and deletes leftover top-level widgets without
  firing `closeEvent` (`TriggerWindow.closeEvent` calls `sys.exit`), then
  clears the log sink's window reference.
- `TRIGGER_DESIGNER_DATA_DIR` pointing at a temp directory per session, so a
  run never reads or writes the developer's real preferences.
