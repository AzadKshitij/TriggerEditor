# Formula Node — Background Validation Worker

*   **Author:** Azad Kshitij
*   **Status:** Draft
*   **Date:** 2026-11-04

--------------------------------------------------------------------------------

## Overview

The formula node's editor becomes unresponsive while the user types a formula.
After every 800 ms pause in typing, the editor calls `validate_section`, which
opens two DuckDB connections, runs a Polars `.collect()` call, and executes a
query against 100 real data rows — all on the Qt main (UI) thread. The event
loop is blocked for the duration of that work, which can range from a few
hundred milliseconds to over a second depending on how complex the upstream
pipeline is. The user sees: type a letter, app hangs, error (or nothing) appears.

This design replaces the synchronous `validate_section` call with a background
worker dispatched from the editor's debounce timer. The worker runs DuckDB and
Polars off the UI thread and delivers results back via a Qt queued signal. The
existing timing (800 ms debounce), two-pass validation logic (EXPLAIN + 100-row
execution), and 100-row sample size all stay exactly as they are.

--------------------------------------------------------------------------------

## The Problem

### Synchronous validation blocks the UI thread

`check_for_errors` in `SQLFormulaEditor` (sql_formula_editor.py:610) calls
`self.external_validator(text)` directly. The validator is wired to
`FormulaContent._validate_section`, which calls `core.validate_section`. That
function does the following work, synchronously, on the UI thread:

1. Builds a zero-row `pl.DataFrame` from the upstream schema.
2. Opens a DuckDB connection; runs `EXPLAIN` on the generated query to check
   syntax and column binding. Even this fast pass has DuckDB connection overhead.
3. If EXPLAIN passes: calls `_sample_rows(frames[0])`, which runs
   `.head(100).collect()` on the full upstream Polars LazyFrame. If the
   upstream pipeline has a join, groupby, or large file scan, this single call
   can take hundreds of milliseconds to over a second.
4. Opens a second DuckDB connection; executes the formula query against those
   100 rows. This is what catches runtime type errors that EXPLAIN misses
   (e.g., `[Price] + ""`).

Each call opens two DuckDB connections and runs one Polars collection. With
five formula sections active, `_first_error` re-runs sections 0 through N-1
before testing section N, so a single validation cycle for section 4 runs up
to eight DuckDB queries.

### A second synchronous path exists

There is a second, independent call to `_validate_section` on the UI thread:
`_commit_editor_text` (formula.py) calls `_refresh_error(index)`, which calls
`_validate_section` directly. This path is triggered by the 300 ms model-commit
debounce — more frequently than the 800 ms error-check debounce, and separately
from it. Fixing only the error-timer path would leave this path still blocking.

### Why two-pass validation is necessary

DuckDB binds `[Price] + ""` without complaint and only fails when it converts
the string for a real row. A syntax-only check (EXPLAIN against a zero-row
copy) would let that formula appear valid until the full workflow runs. The
two-pass design is correct and must be preserved.

--------------------------------------------------------------------------------

## Goals

*   The formula editor never blocks the Qt UI thread during validation. The
    user can type continuously without the editor freezing.
*   Error underlines appear after the user pauses typing, inside the editor,
    without requiring the user to click away.
*   The fix uses existing codebase threading patterns (`AuditTask`,
    `PreviewRequestController`). No new threading primitives are introduced.
*   Validation correctness is unchanged: the two-pass EXPLAIN + 100-row
    execution runs in full, only off the UI thread.
*   Both the error-timer path and the `_refresh_error` commit path stop
    blocking the UI thread.

--------------------------------------------------------------------------------

## Non-Goals

*   Changing the 800 ms debounce interval — the timing is already correct.
*   Changing validation logic, accuracy, or the 100-row sample size.
*   Adding new error-detection capabilities to the formula editor.
*   Improving the performance of upstream Polars pipelines.
*   Introducing a row-sample cache — this is a secondary optimization deferred
    until profiling confirms background validation is still too slow after
    threading is in place.
*   Fixing sluggishness in any node other than the formula node.

--------------------------------------------------------------------------------

## Open Questions

*   **OQ-1 (Polars off-thread safety)**: `sql_guard.py` already carries a
    comment documenting a past crash when Polars `.collect()` ran off the Qt
    main thread inside a DuckDB context. Before shipping, the implementation
    must confirm that `.head(100).collect()` is safe to run from a
    `QThreadPool` worker thread under the existing `DUCKDB_THREADS` constraint.
    If it is not safe, the row sample must be collected on the UI thread before
    dispatch (snapshot the `pl.DataFrame`, pass it into the worker; no live
    Polars computation in the background). The resolution of this question
    determines Step 1 of the implementation.

--------------------------------------------------------------------------------

## Critical User Journeys (CUJs)

### CUJ 1: Typing a formula without freezing

*   **Given**: A formula node is open with one or more formula sections. The
    upstream pipeline has connected data (e.g., a loaded CSV with 10,000 rows
    passing through a filter and a groupby).
*   **When**: The user types a formula character by character. The 800 ms
    debounce fires after each pause.
*   **Then**: The editor remains interactive while the debounce fires and the
    background worker runs. The cursor blinks, text input is accepted without
    delay, and the error underline appears (or clears) when the worker returns
    — without the editor freezing or the UI hanging.

### CUJ 2: Error underline while staying in the editor

*   **Given**: The user has typed a formula with a type mismatch
    (`[Price] + "prefix"`). They pause for one second without clicking away.
*   **When**: The debounce fires and the background worker executes the 100-row
    pass.
*   **Then**: A red underline appears under the offending part of the formula
    while the user is still inside the editor, with no focus-out required. The
    error label beneath the editor shows the DuckDB error message.

### CUJ 3: Rapid editing discards stale results

*   **Given**: The user pauses briefly, the background worker dispatches, then
    the user starts typing again before the worker finishes.
*   **When**: The debounce restarts; a new worker is dispatched. The old
    worker's result signal fires.
*   **Then**: The stale result is discarded (generation counter mismatch). The
    editor shows no underline until the new worker returns.

### CUJ 4: Dock rebuild cancels in-flight workers

*   **Given**: A structural change occurs (the user changes a target column,
    adds a formula section, or removes one), causing `_rebuild_cards` to run.
*   **When**: `_rebuild_cards` calls `clear_layout` to destroy and recreate all
    card widgets.
*   **Then**: All in-flight workers for all sections are cancelled before widget
    destruction. No worker fires its result signal into a deleted widget.

--------------------------------------------------------------------------------

## Technical Plan

### Resolution of OQ-1 (Polars off-thread safety)

`sql_guard.py` documents a past crash from Polars `.collect()` running off the
Qt main thread inside a DuckDB context. Rather than verifying thread safety
and relying on the `DUCKDB_THREADS` constraint holding, this design eliminates
the problem at the source: **the row sample is collected on the UI thread
before the worker is dispatched**, and the resulting `pl.DataFrame` snapshot is
passed into the worker. The worker never calls `.collect()`.

The EXPLAIN pass constructs `pl.DataFrame(schema=schema_of(frames[0]))`, which
reads the LazyFrame's declared schema (pure Python, no Rust computation) and is
safe off-thread. Only `.head(100).collect()` triggers Rust execution; that call
stays on the UI thread in the dispatcher.

This resolves OQ-1 and closes B2 from the Goldfish review.

---

### New components

Three new objects are introduced. All live in
`src/trigger_designer/qt/widgets/nodes/Preparation/formula.py`.

**`_ValidationSignals(QObject)`**

A minimal `QObject` companion whose only purpose is to hold the signals that
`_ValidationRunner` emits. `QRunnable` does not inherit from `QObject` and
cannot emit signals on its own. This companion is created on the UI thread,
passed into the runner, and held alive by the caller until the runner finishes.

```
Signals:
  finished(section_index: int, generation: int, errors: list[dict])
  failed(section_index: int, generation: int, message: str)
```

**`_ValidationRunner(QRunnable)`**

Modeled on `AuditTask` (`qt/helpers/audit_tasks.py`). Owns: a snapshot of the
sections list, a schema-only `pl.DataFrame`, a row-sample `pl.DataFrame`
(already collected), the section index, the formula text override, a
`threading.Event` cancel token, the generation counter value at dispatch time,
and a reference to its `_ValidationSignals`.

Its `run()` method:
1. Calls `core._first_error(sections, section_index, schema_only, explain=True)`
   (EXPLAIN pass — DuckDB only, no Polars).
2. Checks the cancel token. Returns without emitting if set.
3. If the row sample has rows: calls `core._first_error(sections, section_index,
   rows_snap, explain=False)` (100-row execution).
4. Emits `signals.finished(section_index, generation, errors)`.
5. The entire `run()` body is wrapped in `try/except Exception`; on any
   exception it emits `signals.failed(section_index, generation, str(exc))` and
   logs via `logger.exception`.

**`_ValidationDispatcher`**

Modeled on `PreviewRequestController` (`qt/models/preview_worker.py`).
Lives as an attribute of `FormulaContent`. Owns:

- `_generation: int` — increments on every dispatch and on dock rebuild.
- `_tokens: list[threading.Event]` — one token per formula section (up to 5).
- `_active: set` — holds strong references to `(runner, signals)` pairs to
  prevent premature garbage collection (pattern from `ErrorEnricher`).

Public interface:
- `dispatch(section_index, sections_snap, schema_only, rows_snap, text)` —
  builds and starts one `_ValidationRunner`. Returns immediately.
- `cancel_from(section_index)` — sets tokens for sections >= section_index.
- `bump_generation()` — increments `_generation`; stale results will not
  match and are discarded.

---

### Changes to existing components

**`FormulaContent` (formula.py — Qt widget)**

New attributes:
- `_dispatcher: _ValidationDispatcher` — created in `__init__`.

New methods:
- `_dispatch_validation(section_index, text)` — called by the editor's
  `schedule_validation` callback. UI thread. Steps:
  1. Build `sections_snap` from `self._section_list()` with `text` inserted at
     `section_index` (this is a plain list; `_section_list` already returns a
     copy from `normalize`).
  2. Build `schema_only = pl.DataFrame(schema=schema_of(self.frames[0]))`.
  3. Build `rows_snap = core._sample_rows(self.frames[0])` — collects 100 rows
     on the UI thread; may be `None` if frames are absent or collection fails.
  4. Call `self._dispatcher.dispatch(section_index, sections_snap, schema_only,
     rows_snap, text)`.
- `_on_validation_result(section_index, generation, errors)` — slot connected
  to `_ValidationSignals.finished` via `Qt.ConnectionType.QueuedConnection`.
  Checks `generation == self._dispatcher._generation`; discards if stale.
  Looks up the editor widget for `section_index`; calls
  `editor.apply_validation_results(errors)` and updates `error_label`.
  Removes the `(runner, signals)` pair from `_dispatcher._active`.
- `_on_validation_failed(section_index, generation, message)` — slot connected
  to `_ValidationSignals.failed`. Logs via `logger.warning`. On a non-stale
  generation, calls `editor.apply_validation_results([{"message": message,
  "line": 1, "column": 0, "length": 1}])`. Removes from `_dispatcher._active`.

Modified methods:
- `_rebuild_cards`: call `self._dispatcher.cancel_from(0)` and
  `self._dispatcher.bump_generation()` before `clear_layout`.
- `_remove_section(index)`: call `self._dispatcher.cancel_from(index)` before
  `self._commit(...)`.
- `_add_section`: call `self._dispatcher.cancel_from(len(sections))` before
  `self._commit(...)`.
- `_commit_editor_text`: **remove** the `self._refresh_error(index)` call loop.
  Error display is handled entirely by the editor's async path.
- `create_layout` / `_rebuild_cards` (card creation): replace
  `formula_input.set_validate_callback(partial(self._validate_section, index))`
  with `formula_input.schedule_validation =
  partial(self._dispatch_validation, index)`. Leave `external_validator` unset
  so the synchronous DuckDB path is not called from `check_for_errors`.

**`SQLFormulaEditor` (sql_formula_editor.py)**

New attribute:
- `schedule_validation: Callable[[str], None] | None = None` — set by
  `FormulaContent` during card construction. Fire-and-forget; no return value.

New method:
- `apply_validation_results(errors: list[dict])` — called by
  `FormulaContent._on_validation_result` on the UI thread. Replaces
  `self.errors` with the incoming list; calls `update_error_highlights()` and
  `allErrorsDetected.emit(formatted_messages)`. Also emits the backward-
  compatible `errorDetected` signal if the first error carries line/column.

Modified method:
- `check_for_errors`: after the SQLGlot and column-reference fast path, check
  `if self.schedule_validation is not None`. If set, call
  `self.schedule_validation(text)` and skip the `external_validator` block.
  `external_validator` continues to work as before for callers that do not use
  the async path (e.g., the SQL Query node).

---

### Data flow

```
User types
  │
  ▼
SQLFormulaEditor.on_text_changed()
  │  clears errors; restarts error_timer (800 ms)
  ▼
error_timer.timeout → check_for_errors()   [UI thread]
  ├─► validate_sql_syntax(text)             fast; SQLGlot
  ├─► validate_column_references(text)      fast; regex
  ├─► update_error_highlights()             shows fast-path underlines immediately
  └─► schedule_validation(text)             fire-and-forget; no blocking
        │
        ▼
FormulaContent._dispatch_validation(index, text)   [UI thread]
  ├─ dispatcher.cancel_from(index)
  ├─ build sections_snap, schema_only, rows_snap    [.collect() on UI thread]
  ├─ create _ValidationSignals (QObject, UI thread)
  ├─ create _ValidationRunner (QRunnable)
  ├─ connect signals → _on_validation_result / _on_validation_failed
  └─ QThreadPool.globalInstance().start(runner)
        │
        ▼
_ValidationRunner.run()   [QThreadPool worker thread]
  ├─ EXPLAIN pass on schema_only
  ├─ check cancel token
  ├─ 100-row pass on rows_snap
  └─ emit signals.finished(index, generation, errors)
        │  QueuedConnection → UI thread
        ▼
FormulaContent._on_validation_result()   [UI thread]
  ├─ if generation mismatch → discard; remove from _active
  └─ editor.apply_validation_results(errors)
        │
        ▼
SQLFormulaEditor.apply_validation_results()
  ├─ self.errors = errors
  ├─ update_error_highlights()
  └─ allErrorsDetected.emit(...)
```

---

### Error display: fast path then DuckDB

When the debounce fires, `check_for_errors` immediately shows SQLGlot and
column-reference underlines (fast path). When the DuckDB worker returns,
`apply_validation_results` replaces all underlines with the DuckDB result.
DuckDB is authoritative: if it passes, all underlines clear. If it fails, its
errors show instead. This matches the existing behavior where DuckDB overrides
SQLGlot when `external_validator` is set.

There is no "checking…" indicator. The editor shows fast-path results for a
brief window, then shows DuckDB results.

---

### Cancellation and stale-result discard

Two mechanisms are used together:

1. `threading.Event` — prevents the second `_first_error` call (100-row pass)
   from starting if the token is set before it begins.
2. Generation counter — the generation value is baked into every runner at
   dispatch. `_on_validation_result` discards any result whose generation does
   not match the current `_dispatcher._generation`.

`con.interrupt()` is not used. DuckDB queries on 100 rows finish quickly
(under ~200 ms), and interrupting a connection mid-query requires tracking the
connection object across thread boundaries. The generation counter is sufficient
to discard stale results harmlessly.

---

### Lifetime and GC safety

The `(runner, signals)` pair is kept in `_dispatcher._active` from dispatch
until the result or failure signal is delivered. The slot removes the pair from
`_active` as the last step. This pattern follows `ErrorEnricher` and prevents
the Python garbage collector from freeing the `_ValidationSignals` QObject
before the queued signal is delivered to the UI thread.

--------------------------------------------------------------------------------

## Alternatives Considered

### Alternative A: Split validation by phase (EXPLAIN on debounce, 100-row on focus-out)

Run only the EXPLAIN pass (syntax + column-binding check) on the existing 800 ms
debounce. Defer the 100-row execution pass to `editingFinished` (when the user
clicks away or tabs out of the editor).

*   **Pros**: No threading required. Very simple change — replace the full
    `validate_section` call with an EXPLAIN-only call in `check_for_errors`, and
    add a focus-out trigger for the 100-row pass.
*   **Cons**: The user must leave the editor to see runtime type errors (e.g.,
    `[Price] + ""`). The user explicitly stated they want errors to appear after
    a pause *without* having to click away. This approach violates that
    requirement.
*   **Reason for rejection**: Rejected by author — does not meet the requirement
    that errors appear while the user stays inside the editor.

---

### Alternative B: Row-sample cache as the primary fix

Cache the 100-row `pl.DataFrame` on `FormulaContent` and reuse it across
validation cycles until upstream data changes. This eliminates the
`.head(100).collect()` cost on every debounce cycle.

*   **Pros**: No threading required. Cuts the most expensive single operation.
    Simple to add.
*   **Cons**: Does not eliminate the DuckDB connection overhead or the EXPLAIN
    pass, both of which still run synchronously on the UI thread. Even with the
    cache, the validation cycle opens two DuckDB connections and runs queries
    synchronously. The UI thread still freezes, just for a shorter time.
*   **Reason for rejection**: Rejected by author — treats a symptom rather than
    the cause. The root problem is synchronous execution on the UI thread. This
    fix is deferred as a secondary optimization after threading is confirmed
    working.

---

### Alternative C: `SQLFormulaEditor` owns the dispatcher

Place `_ValidationDispatcher` as an attribute of `SQLFormulaEditor` (the editor
widget) rather than `FormulaContent`. The worker would call `external_validator`
synchronously from `run()`, keeping the existing callable interface intact and
requiring no changes to `FormulaContent`.

*   **Pros**: Minimal change to `FormulaContent`. Fixes the threading problem
    generically for any caller that sets `external_validator`, not just the
    formula node.
*   **Cons**: `external_validator` is a closure over `FormulaContent` that
    reads `self.settings` and `self.frames` live. Calling it from a worker
    thread means those live reads happen off the UI thread while the UI thread
    may be mutating them — a data race. The widget is designed to be
    data-agnostic; it cannot take state snapshots because it has no access to
    `frames` or `settings`.
*   **Reason for rejection**: Rejected by author — introduces a data race on
    `self.settings` and `self.frames`. The dispatcher must live where the data
    lives so that snapshots can be taken safely before dispatch.

---

### Alternative D: `QThread` + `moveToThread` instead of `QRunnable`

Use a long-lived `QThread` worker with a persistent event loop, moving a
validator object onto it with `moveToThread`. Requests and results are passed
via signals.

*   **Pros**: Supports multiple sequential validations through a message queue.
    Fine-grained control over the worker's lifecycle.
*   **Cons**: Heavier setup than `QRunnable`. Requires starting, managing, and
    stopping the thread explicitly. The validation task is short-lived and
    fire-and-forget; `QThreadPool` is the idiomatic Qt pattern for that workload.
    The existing codebase uses `QRunnable` + `QThreadPool` for analogous tasks
    (`AuditTask`, `ErrorEnricher`).
*   **Reason for rejection**: Rejected by author — `QRunnable` + `QThreadPool`
    is the correct primitive for this workload and is already established in the
    codebase.

---

### Alternative E: `con.interrupt()` for cancellation

Interrupt the in-flight DuckDB connection when a new validation cycle starts,
stopping the running query immediately.

*   **Pros**: Faster cancellation. Stops a slow DuckDB query mid-execution
    rather than waiting for it to finish.
*   **Cons**: Requires tracking the DuckDB connection object across thread
    boundaries (storing a reference on the runner that the dispatcher can reach
    to call `interrupt()`). Adds cross-thread complexity. DuckDB queries on
    100 rows typically finish in under 200 ms; the generation counter discards
    stale results harmlessly without interruption. The added complexity is not
    warranted.
*   **Reason for rejection**: Rejected by author — generation-counter stale
    discard is sufficient; query duration is short enough that interruption is
    not needed.

--------------------------------------------------------------------------------

## Non-Functional Requirements

**Threading safety**: DuckDB's C++ extension and Polars' Rust extension (via
PyO3) both release the Python GIL during their heavy work. `QRunnable` on
`QThreadPool.globalInstance()` achieves genuine concurrency for this workload.
All result delivery uses `Qt.ConnectionType.QueuedConnection` to guarantee
slot execution on the UI thread.

**Performance**: The `.head(100).collect()` call moves from the worker back to
the UI thread (pre-dispatch). Its cost is unchanged — the user still bears it
at the same moment (after the 800 ms pause). The UI thread is unblocked for
the DuckDB execution portion (the larger share of validation time). If the
pre-dispatch `.collect()` itself proves too slow, the row-sample cache
(Alternative B) can be added in a subsequent change.

**Rollback**: The change is scoped to two files (`formula.py` Qt widget and
`sql_formula_editor.py`). The change to `core/shaping/formula.py` is additive
(new public function; nothing is removed). The original `validate_section` and
`external_validator` paths are preserved and continue to work for other callers.
Rolling back means reverting those two files; no migration or schema change is
required.

--------------------------------------------------------------------------------

## Detailed Implementation Plan

### Target Files to Create/Modify

#### 1. `src/trigger_designer/core/shaping/formula.py` (Modify)

*   **Type / Scope**: Core logic — Python module, Qt-free
*   **Proposed Changes**:
    - Rename `_sample_rows` to `sample_rows` (remove leading underscore). The
      `_ValidationDispatcher` in the Qt layer needs to call this function from
      the UI thread before dispatch. Making it public avoids accessing a private
      function across module boundaries.
    - Add a new public function `validate_section_presampled`:

      ```
      def validate_section_presampled(
          sections: list[dict],
          section_index: int,
          schema_only: pl.DataFrame,
          rows_snap: pl.DataFrame | None,
      ) -> list[dict]:
      ```

      Behaves identically to `validate_section` but accepts pre-collected
      DataFrames instead of a `frames` list. Skips the `sample_rows()` call
      entirely. Called by `_ValidationRunner.run()` from the worker thread.
      No DuckDB connection is opened for the row collection; the two DuckDB
      passes (`_first_error` × 2) remain unchanged.
    - Update the existing `validate_section` docstring to note that
      `validate_section_presampled` is preferred when calling from a background
      thread.
    - Update the internal call in `validate_section` from `_sample_rows` to
      `sample_rows` to match the rename.

#### 2. `src/trigger_designer/qt/widgets/nodes/Preparation/formula.py` (Modify)

*   **Type / Scope**: Qt widget — `FormulaContent` and its card-building logic
*   **Proposed Changes**:

    **New class `_ValidationSignals(QObject)`** (add at module level, before
    `FormulaContent`):
    - Inherits `QObject`.
    - `finished = Signal(int, int, list)` — `(section_index, generation, errors)`.
    - `failed = Signal(int, int, str)` — `(section_index, generation, message)`.
    - No other attributes or methods.

    **New class `_ValidationRunner(QRunnable)`** (add after `_ValidationSignals`):
    - Constructor accepts: `section_index: int`, `sections_snap: list[dict]`,
      `schema_only: pl.DataFrame`, `rows_snap: pl.DataFrame | None`,
      `cancel_token: threading.Event`, `generation: int`,
      `signals: _ValidationSignals`.
    - Stores all constructor arguments as instance attributes. No other
      initialization.
    - `run()` body (pseudocode):
      ```
      try:
          errors = core.validate_section_presampled(
              sections_snap, section_index, schema_only, rows_snap=None
          )  # EXPLAIN pass: pass rows_snap=None to only run EXPLAIN
          if cancel_token.is_set():
              return
          if rows_snap is not None and rows_snap.height > 0:
              errors = core.validate_section_presampled(
                  sections_snap, section_index, schema_only, rows_snap
              )  # 100-row pass
          signals.finished.emit(section_index, generation, errors)
      except Exception as exc:
          logger.exception("ValidationRunner section %d failed", section_index)
          signals.failed.emit(section_index, generation, str(exc))
      ```

      Note: `validate_section_presampled` needs a `rows_snap` parameter that is
      optional. When `None`, it runs only the EXPLAIN pass (no 100-row check).
      This avoids duplicating the EXPLAIN logic. The function signature in
      `core/shaping/formula.py` must support this.

    **New class `_ValidationDispatcher`** (add after `_ValidationRunner`):
    - Constructor: takes no arguments. Initializes `_generation = 0`,
      `_tokens: list[threading.Event] = []`, `_active: set = set()`.
    - `dispatch(section_index, sections_snap, schema_only, rows_snap, text)`:
      - Replace `sections_snap[section_index]["formula_text"]` with `text` (the
        most recent editor text, which may differ from the model snapshot).
      - Create `cancel_token = threading.Event()`.
      - Extend `self._tokens` to length `section_index + 1` if needed; set
        `self._tokens[section_index] = cancel_token`.
      - Increment `self._generation`.
      - Create `signals = _ValidationSignals()` on the calling thread (UI).
      - Create `runner = _ValidationRunner(section_index, sections_snap,
        schema_only, rows_snap, cancel_token, self._generation, signals)`.
      - Set `runner.setAutoDelete(True)`.
      - Add `(runner, signals)` to `self._active`.
      - `QThreadPool.globalInstance().start(runner)`.
    - `cancel_from(section_index)`:
      - For each `i >= section_index` where `i < len(self._tokens)`: call
        `self._tokens[i].set()`.
    - `bump_generation()`:
      - `self._generation += 1`.

    **Modifications to `FormulaContent`**:

    - `__init__`: add `self._dispatcher = _ValidationDispatcher()`.

    - `_rebuild_cards` (before `clear_layout`): add
      `self._dispatcher.cancel_from(0)` and `self._dispatcher.bump_generation()`.

    - `_remove_section(index)` (before `self._commit`): add
      `self._dispatcher.cancel_from(index)`.

    - `_add_section` (before `self._commit`): add
      `self._dispatcher.cancel_from(len(sections))`.

    - `_commit_editor_text`: remove the `for index in changed: self._refresh_error(index)` loop. Replace with nothing; error display is handled by the async path.

    - Card construction in `_rebuild_cards` (the block that creates each
      `formula_input`): replace:
      ```
      formula_input.set_validate_callback(partial(self._validate_section, index))
      ```
      with:
      ```
      formula_input.schedule_validation = partial(self._dispatch_validation, index)
      ```

    - New method `_dispatch_validation(section_index: int, text: str)`:
      - Guard: if `not self.frames or self.frames[0] is None`, return.
      - `sections_snap = self._section_list()` (returns a normalized copy).
      - `schema_only = pl.DataFrame(schema=schema_of(self.frames[0]))`.
      - `rows_snap = core.sample_rows(self.frames[0])` — may return `None`.
      - `self._dispatcher.dispatch(section_index, sections_snap, schema_only,
        rows_snap, text)`.
      - Connect signals before `dispatch` returns: inside `dispatch`, the
        signals object is connected to `_on_validation_result` and
        `_on_validation_failed` via `Qt.ConnectionType.QueuedConnection`.
        These connections must be made inside `dispatch` after the signals
        object is created and before `start(runner)` is called.

    - New slot `_on_validation_result(section_index: int, generation: int,
      errors: list)`:
      - `self._dispatcher._active.discard(...)` — remove the matching pair.
        (Requires that `_active` holds objects identifiable by `generation`
        and `section_index`, or that `dispatch` returns the pair for later
        removal. Simplest: store a dict keyed by `(section_index, generation)`
        rather than a plain set.)
      - If `generation != self._dispatcher._generation`: return (stale).
      - If `section_index >= len(self.section_widgets)`: return (dock rebuilt).
      - `widget = self.section_widgets[section_index]`.
      - `try: editor = widget["formula_input"].editor` (the inner
        `SQLFormulaEditor`). Call `editor.apply_validation_results(errors)`.
        Update `widget["error_label"]` from `errors`.
      - `except RuntimeError`: widget was deleted; return.

    - New slot `_on_validation_failed(section_index: int, generation: int,
      message: str)`:
      - Remove from `_active`.
      - If stale: return.
      - Log `logger.warning("Formula validation failed section %d: %s",
        section_index, message)`.
      - Deliver a single-item error list via `editor.apply_validation_results`.

#### 3. `src/trigger_designer/qt/widgets/sql_formula_editor.py` (Modify)

*   **Type / Scope**: Qt widget — `SQLFormulaEditor` and `SQLFormulaWidget`
*   **Proposed Changes**:

    **`SQLFormulaEditor`**:
    - New instance attribute (set in `__init__`):
      `self.schedule_validation: Callable[[str], None] | None = None`.
    - New method `apply_validation_results(errors: list[dict])`:
      - `self.errors = list(errors)` — replace, do not extend.
      - Call `self.update_error_highlights()`.
      - Format and emit `self.allErrorsDetected`.
      - If `errors` and the first entry has `line` and `column`: emit backward-
        compatible `self.errorDetected`.
    - Modify `check_for_errors`:
      - After the SQLGlot and column-reference fast path runs and
        `update_error_highlights()` is called, add:
        ```
        if self.schedule_validation is not None:
            self.schedule_validation(text)
            return   # DuckDB result arrives via apply_validation_results
        ```
      - The `external_validator` block remains in the `else` branch (or the
        code after the early return), so callers that set only
        `external_validator` are unaffected.

    **`SQLFormulaWidget`**: no changes required.

#### 4. `tests/unit/test_formula_core.py` (Modify)

*   **Type / Scope**: Unit tests for `core/shaping/formula.py`
*   **Proposed Changes**:
    - Add tests for `validate_section_presampled`:
      - Passing a correct formula with pre-collected rows returns no errors.
      - Passing a type-mismatch formula (e.g., string column + number literal)
        returns a DuckDB error.
      - Passing `rows_snap=None` performs only the EXPLAIN pass.
      - Passing a schema-only (zero-row) DataFrame with a correct formula
        returns no errors.
    - Add a test confirming `sample_rows` (renamed from `_sample_rows`) is
      importable as a public name.

#### 5. `tests/ui/test_formula_dock.py` (Modify)

*   **Type / Scope**: UI tests for `FormulaContent`
*   **Proposed Changes**:
    - Review existing tests that call `_validate_section` or `_refresh_error`
      directly. Update or remove any direct calls to removed methods.
    - Add a test confirming that `_rebuild_cards` calls
      `_dispatcher.cancel_from(0)` (can be verified by checking that the
      generation counter increases).
    - Add a test confirming that `_commit_editor_text` no longer calls any
      synchronous validator.

#### 6. `tests/ui/test_formula_editor_loop.py` (Modify)

*   **Type / Scope**: UI tests for `SQLFormulaEditor`
*   **Proposed Changes**:
    - Add a test for `apply_validation_results`: verify that passing an errors
      list causes `update_error_highlights` to show underlines and
      `allErrorsDetected` to emit.
    - Add a test confirming that when `schedule_validation` is set,
      `check_for_errors` calls it and does not call `external_validator`.

#### 7. `tests/unit/test_errors_formula_live.py` (Review, possibly modify)

*   **Type / Scope**: Live integration tests for formula validation
*   **Proposed Changes**:
    - Review whether any test relies on `validate_section` being called
      synchronously from the UI layer. If so, update to call
      `validate_section_presampled` with pre-collected data or `validate_section`
      directly from the core layer.

#### 8. `tests/e2e/workflows/formula-category.tds` and `tests/e2e/test_multi_field_formula_workflow.py` (Review)

*   **Type / Scope**: End-to-end workflow tests
*   **Proposed Changes**:
    - Review whether any E2E test asserts formula error state immediately after
      programmatic text entry without waiting. Since validation is now async, a
      test that sets formula text and immediately reads the error state may fail
      (the async worker has not returned yet). Add appropriate waits (e.g.,
      `QApplication.processEvents()` and a short sleep, or poll until the error
      label shows content) where needed.

---

### Verification Plan

*   **Unit tests**: `pytest tests/unit/test_formula_core.py
    tests/unit/test_errors_formula_live.py` — all existing tests must pass;
    new `validate_section_presampled` tests must pass.
*   **UI tests**: `pytest tests/ui/test_formula_dock.py
    tests/ui/test_formula_editor_loop.py` — all existing tests must pass; new
    threading-behavior tests must pass.
*   **E2E tests**: `pytest tests/e2e/test_multi_field_formula_workflow.py` —
    formula workflow test must pass end-to-end.
*   **Static analysis**: `ruff check src/trigger_designer/qt/widgets/nodes/
    Preparation/formula.py src/trigger_designer/qt/widgets/sql_formula_editor.py
    src/trigger_designer/core/shaping/formula.py`
*   **Manual smoke test**: Open a formula node connected to a large upstream
    pipeline (join or groupby with 50 k+ rows). Type a formula with a type
    mismatch. Confirm: (a) the editor does not freeze while typing, (b) a red
    underline appears after an 800 ms pause without clicking away, and (c) the
    error label below the editor shows the DuckDB error message.

--------------------------------------------------------------------------------

### Additional Resources

*   `src/trigger_designer/qt/helpers/audit_tasks.py` — `AuditTask` base class
    for `_ValidationRunner`
*   `src/trigger_designer/qt/helpers/error_enricher.py` — `_ACTIVE` set pattern
    for `_ValidationDispatcher`
*   `src/trigger_designer/qt/models/preview_worker.py` —
    `PreviewRequestController` generation-counter pattern for
    `_ValidationDispatcher`
*   `src/trigger_designer/core/sql_guard.py` — `connect_for_shaping` and the
    documented DuckDB-threads constraint
*   `plans/nodes/09-formula.md` — existing node design notes

### Future Improvements

*   **Row-sample cache**: Once background validation is confirmed working, add
    `_row_sample: pl.DataFrame | None` and `_row_sample_frame_id: int | None`
    to `FormulaContent`. The dispatcher collects the sample only when
    `id(self.frames[0])` differs from `_row_sample_frame_id`. Eliminates the
    UI-thread `.collect()` cost for repeated validations when upstream data has
    not changed.
*   **Multi-field formula node**: Apply the same background-worker pattern to
    `multi_field_formula.py` after this change is validated.

--------------------------------------------------------------------------------

<!-- Provenance: Indicates initial structural drafting via EGM. -->

*Drafted with EGM*
