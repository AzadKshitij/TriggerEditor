# 09 - Foundations (must land FIRST; plans 01-08 build on it)

Status: implementation plan. Written 2026-10-21 against `main` @ `71b4041` with a dirty working tree
(`check_output.py`, `pyproject.toml`, `uv.lock`, `main.py`, `file_opener.py`, `model_pandas.py` deleted,
untracked `__main__.py`, `docs/`). Every `file:line` below was opened and checked on that tree; anchor on the quoted
statement, not the line number, if the file moved. Paths are relative to the repo root; `src/trigger_designer/` is
written `td/` in code skeletons and tables only.

Audience: a cheaper model. There are no open questions in this document. Where a decision was needed it is stated with
its reason. If reality differs from a quoted line, stop and report the difference; do not improvise a design.

BUG numbers always mean `docs/bugs.md`. Two numbering confusions in the task text are resolved here:

* "no-sink graphs never collect lazy plans" is **BUG-004**; "cancellation not wired / `request_cancel` unused" is **BUG-011**
  (brief "fact 4"). Run correctness is BUG-004 + BUG-005 + BUG-012.
* "stale live state" is **BUG-005**; the cycle/disabled Run button is **BUG-012**.

---

## 1. Goal, non-goals, dependency table, single source of truth

### 1.1 Goal and non-goals

**Goal.** Plans 02, 03, 06 and 08 all edit the same lines of `executor.py` (~L266, L310, L378-388),
`workflow_worker.py` `run()` (L43-68), `workflow_execution_mixin.py` (`executeWorkflow` L47-89, `_on_node_finished`,
`_on_workflow_finished` L125-141, `_execution_cleanup`), `performance_scene.py` (`serialize`/`saveToFile`), `pyproject.toml`,
`uv.lock` and `trigger.spec`; several bugs (BUG-001, 002, 003, 005, 010, 011, 012) block every plan. This plan extracts that
shared work into **ten small commits (F-A .. F-J, with F-H split into F-H1 and F-H2)** so the feature plans only fill hook
bodies and add their own files.

**Non-goals** (each is somebody else's job; do not do it here):

* Translating errors, the Problems dock, the run record, the workpaper, the CLI command set, relative-path storage:
  plans 03, 02, 06, 08, 01. This plan creates only the seams they plug into.
* Making fallback `get_code()` raise instead of emitting empty frames (second half of BUG-005 recommendation): not done;
  F-E gives an equivalent guarantee (every node is re-evaluated immediately before Run) and a warning for invalid nodes.
* Stable generated variable names (BUG-013 part 3), `getSocketValue` (BUG-008), serialize purity (BUG-017), DuckDB nodes'
  new behaviour. Not here.
* The SQL guard module itself: **plan 07 creates `core/sql_guard.py` in its foundation step F7** (plan 07 section 3.8);
  F-H2 only *applies* it to the existing Formula and Filter nodes.
* Bumping the `qtpy-nodeeditor` ref (F-J explains why it cannot be done from this repo).

### 1.2 Single source of truth: names that plans 02/03/06/08 must use

Plans 02, 03, 06, 08 must be reconciled to these exact names (section 10 lists what each must delete or rename).

**`ExecutionResult` fields** (`src/trigger_designer/core/ExecutionCheck/executor.py`, all defaulted, appended after `timestamp`, in this order; F-B):

| Field | Type / default | Filled by | Consumers |
|---|---|---|---|
| `exception` | `BaseException \| None = None` | `execute_node` failure path: the *source* exception (`original_exception` unwrapped). Null in `without_frames()` | 03 (translator), 02, 08 |
| `traceback_text` | `str = ""` | `"".join(traceback.format_exception(source))`, computed on the exec side before `__traceback__` is dropped | 03, 02 |
| `exception_type` | `str = ""` | `f"{type(source).__module__}.{type(source).__qualname__}"` (survives `without_frames()`) | 02, 08 |
| `code` | `str = ""` | the raw `node.get_code()` text, **before** `code_filter` | 02 (hash), F-I (`getPyFile`) |
| `started_at` | `str = ""` | UTC ISO `YYYY-MM-DDTHH:MM:SS.ffffffZ`, first statement of `execute_node` | 02 |
| `finished_at` | `str = ""` | same format, in `finally` | 02 |
| `policy_violation` | `bool = False` | `True` when the failing source exception has class attribute `policy_violation = True` (plan 08's `CodePolicyError` sets it) | 08 |

**`NodeExecutor` additions** (F-B, F-D, F-E): attributes `before_node`, `after_node`, `code_filter`, `verify_plans`;
methods `reset_cancel()`, `cancel_execution()` (always sets the event), property `cancel_requested`.

| Name | Exact signature | Called |
|---|---|---|
| `before_node` | `Callable[[Any], None] \| None = None`; `(node)` | exec-side thread, after `get_code()` and `code_filter`, before `exec`. Not called when `get_code()`/filter raised |
| `after_node` | `Callable[[Any, dict, ExecutionResult], None] \| None = None`; `(node, local_variables, result)` | after `exec` **succeeded**, after the content's `after_execution`, before `execution_context.update(...)`. After it returns `result.variables = local_variables.copy()` is re-synced |
| `code_filter` | `Callable[[str], str] \| None = None`; `(code) -> code` | right after `get_code()`; may raise (the raise is a normal node failure) |
| `verify_plans` | `bool = True` | F-E: after `exec`, every `pl.LazyFrame` in the node namespace gets `collect_schema()` |

Hook exceptions (`before_node`, `after_node`) are logged at WARNING and **never** fail a node.

**Run loop** (`src/trigger_designer/core/ExecutionCheck/run_loop.py`, Qt-free; F-C):

```python
def run_nodes(nodes, executor, *, continue_on_error=False, upstream=None, cancel=None,
              on_node_started=None, on_node_finished=None, on_node_errored=None,
              on_node_skipped=None) -> LoopOutcome
```

| Callback | Signature | Meaning |
|---|---|---|
| `on_node_started` | `(node)` | about to call `executor.execute_node(node)` |
| `on_node_finished` | `(node, result)` | `execute_node` returned (success **or** failure; check `result.success`) |
| `on_node_errored` | `(node, exc)` | `execute_node` itself raised an `Exception` (defensive path) |
| `on_node_skipped` | `(node, blocker)` | node not executed; `blocker` = nearest failed/skipped upstream node, or `None` when the run was cancelled |

`LoopOutcome` (frozen dataclass): `success: bool`, `cancelled: bool`, `executed: int`, `failed: tuple`, `skipped: tuple`. It is named `LoopOutcome` (not `RunOutcome`) so it never collides with plan 08's `runner.RunOutcome` (which carries `exit_code`).
`WorkflowWorker(nodes, executor, parent=None, *, continue_on_error=False, upstream=None)`; signals `nodeStarted(object)`,
`nodeFinished(object, object)`, `nodeErrored(object, object)`, **`nodeSkipped(object, object)`** (new), `workflowFinished(bool)`;
attributes `cancelled: bool`, `outcome: LoopOutcome | None`, method `request_cancel()`.
Mixin seams: `_run_policy() -> dict` (default `{"continue_on_error": False}`; plan 03 overrides the body to read its preference),
`_on_node_skipped(node, blocker)` (default no-op; plan 03 fills it), `before_run_hooks: list[Callable[[list], None]]`,
`_run_before_run_hooks(sorted_nodes)`, `request_run_cancel() -> bool`, `add_cancel_listener(cb)`,
`_workflow_executor`, `_run_cancelled: bool`, `_show_run_controls(running: bool)`, `_last_run_codes: dict`.
`GraphCycleError(Exception)` lives in `run_loop.py` and is what `topologicalSort` raises.

**Scene** (`td/qt/performance_scene.py`; F-F): `TriggerScene._save_target`, property `workflow_dir`, property `workflow_uuid`,
`loaded_workflow_metadata` (carried forward on save), `reset_workflow_identity()`, overrides `saveToFile` and `loadFromFile`.

**Code generation** (`src/trigger_designer/core/codegen_safe.py`; F-H1): `lit(value) -> str`, `lit_dq(text) -> str`, `lit_list(values) -> str`,
`safe_comment(text) -> str`.

### 1.3 Dependency table: which later plan consumes which F-step

| F-step | One line | 01 | 02 | 03 | 04 | 05 | 06 | 07 | 08 |
|---|---|---|---|---|---|---|---|---|---|
| F-A executor hardening | BUG-001, BUG-010, timeout re-spawn | - | needs | needs | needs | needs | - | - | needs |
| F-B result fields + hook stubs | 1.2 tables | - | needs | needs | - | - | `before_run` | - | `code_filter`, `policy_violation` |
| F-C shared run loop | `run_nodes`, worker rewrite | - | session events | policy 3.15 | - | - | - | - | CLI `execute_nodes` = thin wrapper |
| F-D cancellation | `request_run_cancel`, Cancel button | - | `RunSession.request_cancel` | skipped(None) | - | - | - | - | button + `worker.cancelled` |
| F-E run correctness | cycle, re-eval, plan verify | - | fresh state | - | surfaces plan errors | same | - | - | cycle = clean error |
| F-F atomic UTF-8 save | `workflow_dir`, metadata, uuid | `workflow_dir` | `workflow_uuid` | - | - | - | - | - | `parameters` carry-forward, UTF-8 |
| F-G deps + packaging | xlsxwriter, spec globs, CLI stub | hidden imports | `core/audit` | `core/errors` | `core/audit` | `core/profile` | xlsxwriter | `core/shaping` | entry point, spec |
| F-H1 codegen safety | `lit()` | uses `lit` | - | - | uses `lit` | - | - | - | policy defence-in-depth |
| F-H2 SQL guard on Formula/Filter | needs plan 07 F7 | - | - | - | - | - | - | provides F7 | - |
| F-I docs + `getPyFile` | no CWD write | - | - | - | - | - | - | - | `--emit-script` path arg |
| F-J UI baseline | green UI layer | all UI plans | | | | | | | |

### 1.4 Ordering

`F-A -> F-B -> F-C -> F-D -> F-E -> F-F -> F-G -> F-H1 -> F-I -> F-J`, then **plan 07 step F7** (creates `core/sql_guard.py`),
then **F-H2**. **F-H2 is the one foundation step that must be scheduled after plan 07 F7**; every other step has no
dependency on any feature plan. Consequence: feature plans 02, 03, 06, 08, 01 may start as soon as F-A..F-G land; plan 07 may
start its F1..F7 foundations in parallel with F-H1/F-I/F-J (it does not edit the same files); plan 07 step 12/13 and F-H2
both come after F7. Cross-plan ordering on `node_base.py`: **plan 07 F2 (BUG-031 `optional_inputs`) lands before plan 03 step 6** because both edit the not-connected
branch of `evalImplementation`; plan 03's `set_error` branch must preserve the `optional_inputs` skip (see plan 03 step 6).
If plan 07 slips, F-H2 slips alone; BUG-029/030 stay open until it lands (record that in `docs/bugs.md`
status; do not weaken the guard).

---

## 2. Current state (verified)

| # | Fact | Evidence |
|---|---|---|
| 2.1 | Exec thread catches only `Exception`; `PanicException` (BaseException) escapes `target()`, `finally: done.set()` makes `_execute_with_timeout` return `(True, None)` => success, and the pooled worker thread dies | `executor.py:259-269`; `_node_worker_loop :167-172` has no try/except around `task()` |
| 2.2 | `node_name` is assigned after `node.get_code()`; `except` at `:378-379` uses it | `executor.py:310-311`, `:379` |
| 2.3 | After a timeout the pooled worker is stuck in `target()`; the next `execute_node` queues a task nobody consumes (each later node waits the full timeout) | `executor.py:274-285` comment; harmless today only because the run stops at the first failure |
| 2.4 | `execute_node` does `self._cancel_event.clear()`; `cancel_execution()` sets the event only if a task is running; no reader of the event | `executor.py:303`, `:457-466` |
| 2.5 | `ExecutionResult` has 10 fields, no exception/code/start/finish | `executor.py:34-47` |
| 2.6 | `WorkflowWorker.run` loop with `_cancel_requested` plain bool; stops at first failure; `request_cancel()` has no caller | `workflow_worker.py:25-68` |
| 2.7 | `executeWorkflow` disables Run **before** `topologicalSort` (raises `Exception("Graph has at least one cycle")`, `design_window.py:~754`), `run_workflow` logs and re-raises into the Qt slot; nothing re-enables Run | `workflow_execution_mixin.py:57-61`, `design_window.py:690-696` |
| 2.8 | `executeWorkflow` never calls `eval()`; `doEvalOutputs()` (`design_window.py:327-356`, topological, `_batch_evaluating`, `settle_multi_input_nodes`) exists and is reusable without a dialog | grep `.eval(` in mixin: none |
| 2.9 | Generated code only builds lazy plans; the executor never collects or verifies them | brief 4.3; BUG-004 |
| 2.10 | `TriggerScene` has no `saveToFile`/`loadFromFile` override; the vendored `Scene.saveToFile` does `open(filename, "w")` (truncates; locale encoding) then `serialize()` then sets `self.filename`; `loadFromFile` does `open(filename, "r")` and swallows non-JSON exceptions via `dumpException` | `.venv/Lib/site-packages/nodeeditor/node_scene.py:621-660` |
| 2.11 | `serialize()` overwrites `workflow_metadata` with 3 keys and uses deprecated `datetime.utcnow()`; `deserialize` stores `loaded_workflow_metadata` | `performance_scene.py:166-180` |
| 2.12 | `fileSave` catches every save exception (`dumpException`) and returns `False`; the title/`has_been_modified` are only reset on success | `node_editor_widget.py:160-181` |
| 2.13 | `validateLoadedWorkflow` logs the schema version and never compares it with `WORKFLOW_SCHEMA_VERSION = 2` | `design_window.py:~461-467`, `core/constants.py:8` |
| 2.14 | `pyproject.toml` has no `xlsxwriter`; `uv.lock` none; `.venv` lacks it. `[project.scripts]` has only `trigger-designer`. Both files are **dirty** in the tree | `git diff --stat`: pyproject +21, uv.lock 762 lines |
| 2.15 | `trigger.spec` lists node sources with a `rglob` loop (`:41-51`), literal `hiddenimports` (`:79-110`); `core/` and its subpackages have **no** `__init__.py` (PEP 420) so `collect_submodules` cannot enumerate them (spec comment `:32-40`) | `trigger.spec` |
| 2.16 | Unescaped interpolation sites in `get_code()` (AST scan, this tree): `file_input.py:760,795`; `file_output.py:266,281,287`; `Append.py:158-162`; `join.py:1335`; `cleansing.py:705`; `dynamic_row_builder.py:408`; `filter.py:950,952,958-995`; `formula.py:1313`; `groupby.py:807-827`; `select.py:939-976` (`_build_dtype_conversion_code`), `:1660`, `:1695`; `sort.py:457`; `split.py:190-204`; `unique.py:444`; `running_total.py:226-231`; `transpose.py:282,299,300`; `unknown.py:86` (a comment: a newline in `missing_op` escapes it) | scan script in section 6.8 |
| 2.17 | Plain `duckdb.connect(":memory:")` with user SQL: `filter.py:819` (live), `:850` (`validate_expression`, EXPLAIN), `:1038` (generated); `formula.py:1047`, `:1074` (live), `:1121` (EXPLAIN validation), `:1302` (generated). `formula.py:1313` uses `'''{combined_query}'''`; `duck.close()` is the last emitted line | grep `duckdb.connect` |
| 2.18 | `getPyFile` writes relative `check_output.py` with default encoding and calls `get_code()` a second time per node; the tracked file is ignored by `.gitignore:295` only after untracking; `CHECK_OUTPUT_HEADER` (`design_window.py:65-75`) puts only `<script dir>/src` on `sys.path`; `tests/conftest.py:205-241` stubs `getPyFile` with `(_self, nodes)` | `design_window.py:698-706`; `tests/unit/test_file_output.py:107-116` pins the header constant |
| 2.19 | Installed `qtpy-nodeeditor` is git `ee5e8fd` of `AzadKshitij/qtpy-nodeeditor`; it lacks `setPositions` and the detail-LOD API; `scripts/build.bat:6-19` says the newer canvas commits live only in an **unpublished local clone** (`C:\Projects\qtpy-nodeeditor`) | `direct_url.json`; `build.bat` comment |
| 2.20 | `update_error_highlights` (`sql_formula_editor.py:852-863`) calls `cursor.mergeCharFormat(clean_format)`; Qt emits `textChanged` synchronously; `on_text_changed` (`:586-594`) clears `errors` and restarts the 800 ms timer | BUG-018 probe |
| 2.21 | Baselines today: unit 334 pass, e2e 20 pass, ui 403 pass / 20 fail / 7 error; bare `pytest` aborts (exit 139) | BUG-020 |

---

## 3. Per-step design

Conventions for every step: re-read each file immediately before editing (others edit concurrently); run
`.venv\Scripts\python.exe -m ruff format <touched files>` then `ruff check <touched files>` (only touched files; the repo
baseline is not clean); one commit per step; stage explicit paths only (never `git add -A`, never `git stash`, never
`git checkout -- <file>`); commit message `Foundations F-X: <summary>` plus the attribution trailer. Commands use
`.venv\Scripts\python.exe` (never bare `uv sync`/`uv run` that syncs).

### F-A - Executor hardening (BUG-001, BUG-010, timeout worker re-spawn)

File: `src/trigger_designer/core/ExecutionCheck/executor.py`. Tests: `tests/unit/test_executor_hardening.py` (new).

1. **`target()` catches `BaseException`.** In `_execute_with_timeout` change `except Exception as e:` (`:266`) to
   `except BaseException as e:`. `finally: done.set()` stays. Annotate `exception_container: list[BaseException | None]` and the
   return type `Tuple[bool, Optional[BaseException]]`; `NodeExecutionError.original_exception: Optional[BaseException]`.
   Reason: `polars.exceptions.PanicException` derives from `BaseException` only; `SystemExit`/`KeyboardInterrupt` raised by
   generated code must also be a node failure and must not kill the pooled thread.
2. **Worker loop survives and is replaceable.** Replace `_node_worker_loop` and its start with:

```python
def _start_worker(self) -> None:
    """Start a fresh pooled worker with its own queue."""
    tasks: "queue.Queue[Optional[Callable[[], None]]]" = queue.Queue()
    self._node_task_queue = tasks
    self._node_worker_thread = threading.Thread(
        target=self._node_worker_loop, args=(tasks,), daemon=True, name="NodeExecutorWorker"
    )
    self._node_worker_thread.start()

def _node_worker_loop(self, tasks: "queue.Queue[Optional[Callable[[], None]]]") -> None:
    while True:
        task = tasks.get()
        if task is None:
            return
        try:
            task()
        except BaseException:  # noqa: BLE001 - the worker must outlive any task
            logger.exception("Node executor task raised unexpectedly")
```

   `__init__` replaces the queue/thread creation block (`:159-165`) with `self._start_worker()`.
3. **Timeout replaces the stuck worker.** In `_execute_with_timeout`, in the `if not done.wait(timeout):` branch, before
   `return False, ExecutionTimeoutError(...)`, add:
   `self._node_task_queue.put(None)` (the stuck thread exits when its task ever returns) and `self._start_worker()`.
   Reason: with plan 03's continue-on-error (F-C) a node after a timed-out node would otherwise wait the full timeout on a
   queue nobody reads (2.3). Update the long comment above it (it says "never pick up another task").
4. **`node_name` first (BUG-010).** In `execute_node`, move `node_name = getattr(node.__class__, "__name__", "Unknown")` to
   the line before `try:` (it cannot raise). `code = node.get_code()` stays inside the `try`, so a raising `get_code()` becomes
   an ordinary failure: `result.success False`, `result.error` == `str(exc)`.

Behaviour rules: `execute_node` outer handler stays `except Exception` (the wrapper `NodeExecutionError` is an
`Exception`). `ExecutionTimeoutError` handling unchanged. No new public names.

Error cases: a `BaseException` whose `str()` raises: `str(exception)` inside `NodeExecutionError(...)` construction is in the
`try`, so it surfaces as `Exception` from `str` -> failure with that message; acceptable (covered by "weird exception" test).

### F-B - Shared `ExecutionResult` fields and hook stubs

File: `executor.py`. Tests: `tests/unit/test_executor_hooks.py` (new); extend nothing in `test_execution_result.py` (do not edit
that file; its two tests must keep passing). Plans 02/03/08 then only **fill** these hooks.

1. **Dataclass.** Append after `timestamp` exactly the seven fields of table 1.2, in that order, all defaulted
   (`exception: Optional[BaseException] = None`, `traceback_text: str = ""`, `exception_type: str = ""`, `code: str = ""`,
   `started_at: str = ""`, `finished_at: str = ""`, `policy_violation: bool = False`). Never reorder existing fields.
2. **`without_frames()`** becomes `replace(self, variables={...}, exception=None)` (exceptions hold tracebacks that hold frames).
   `traceback_text`, `exception_type`, `code` are kept.
3. **Helper** (module level, no import of `core.audit`):

```python
def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
```
   (`from datetime import timezone` added to the existing import line; the file imports `datetime` twice - leave that alone.)
4. **Attributes** in `NodeExecutor.__init__`:

```python
self.before_node: Optional[Callable[[Any], None]] = None
self.after_node: Optional[Callable[[Any, dict, ExecutionResult], None]] = None
self.code_filter: Optional[Callable[[str], str]] = None
```
   and the guard:

```python
def _call_hook(self, hook, *args) -> None:
    if hook is None:
        return
    try:
        hook(*args)
    except Exception as exc:  # noqa: BLE001 - observers must never fail a run
        message = f"{getattr(hook, '__name__', 'hook')} failed: {exc!r}"
        logger.warning(message)
```
5. **Call sites in `execute_node`** (anchor on the quoted statements):
   * first statement after `result = ExecutionResult(success=False)`: `result.started_at = _utc_now_iso()`;
   * right after `code = node.get_code()`: `result.code = code`, then
     `if self.code_filter is not None: code = self.code_filter(code)`, then `self._call_hook(self.before_node, node)`,
     then the existing `result.lines_executed = ...` (computed on the filtered code);
   * after the `after_execution` try/except block and **before** `self.execution_context.update(local_variables)`:
     `self._call_hook(self.after_node, node, local_variables, result)` then `result.variables = local_variables.copy()`;
   * in the `except Exception as e:` block, after `result.error = str(e)` / traceback append (keep `result.error` byte-for-byte
     as today; tests pin it): 

```python
source = getattr(e, "original_exception", None) or e
result.exception = source
result.exception_type = f"{type(source).__module__}.{type(source).__qualname__}"
result.traceback_text = "".join(traceback.format_exception(source))
result.policy_violation = bool(getattr(source, "policy_violation", False))
source.__traceback__ = None   # free the frames; the text above is the record
```
   * in `finally:` add `result.finished_at = _utc_now_iso()` as its first line.
6. **`raise NodeExecutionError(...) from exception`** (`:344`): add `from exception` so the original chain is kept.
   `result.error` text is unchanged because `traceback.format_exc()` of the wrapper is still appended exactly as today.

Behaviour rules: `before_node` is not called when `get_code()` or `code_filter` raised (no code ran); `after_node` only on
success; `result.code` is the **unfiltered** text (what the user's graph generates; the filter is a sandbox detail).
`policy_violation` is a class-attribute convention so the executor imports nothing from plan 08.

Hook contract (`before_run_hooks` / `_run_before_run_hooks`): the GUI's `_run_before_run_hooks` logs hook exceptions to the dock and
never raises; headless runners (plan 08's CLI loop over `content.before_run()`, which turns failures into `warning` events) may
iterate `before_run_hooks` themselves, so **the hook list is the contract**, not the GUI helper.

### F-C - Qt-free run loop extracted from the worker

New file `src/trigger_designer/core/ExecutionCheck/run_loop.py` (imports: `threading`, `dataclasses`, `typing` only; no Qt,
no polars, no loguru). Rewrites `src/trigger_designer/qt/helpers/workflow_worker.py` `run()`. Tests:
`tests/unit/test_run_loop.py` (new, Qt-free), `tests/unit/test_workflow_worker_loop.py` (new), existing
`tests/unit/test_workflow_execution_mixin.py` must pass unchanged. Why a module and not a method: the CLI (plan 08) and the
GUI must execute **the same loop** so skip/continue/cancel semantics cannot diverge.

```python
"""Topological node-run loop shared by the GUI worker and the headless CLI."""
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence


class GraphCycleError(Exception):
    """Raised by topologicalSort when the workflow contains a loop."""


@dataclass(frozen=True)
class LoopOutcome:
    success: bool
    cancelled: bool
    executed: int
    failed: tuple
    skipped: tuple


def run_nodes(
    nodes: Sequence[Any],
    executor: Any,
    *,
    continue_on_error: bool = False,
    upstream: Mapping[Any, Sequence[Any]] | None = None,
    cancel: threading.Event | None = None,
    on_node_started: Callable[[Any], None] | None = None,
    on_node_finished: Callable[[Any, Any], None] | None = None,
    on_node_errored: Callable[[Any, BaseException], None] | None = None,
    on_node_skipped: Callable[[Any, Any | None], None] | None = None,
) -> LoopOutcome:
    upstream = upstream or {}
    reset = getattr(executor, "reset_cancel", None)
    if callable(reset):
        reset()
    bad: set = set()            # failed or skipped nodes (hashable by identity)
    failed: list = []
    skipped: list = []
    executed = 0
    cancelled = False
    ordered = list(nodes)
    for index, node in enumerate(ordered):
        if cancel is not None and cancel.is_set():
            cancelled = True
            for rest in ordered[index:]:
                skipped.append(rest)
                if on_node_skipped:
                    on_node_skipped(rest, None)
            break
        blockers = [u for u in upstream.get(node, ()) if u in bad]
        if blockers:
            bad.add(node)
            skipped.append(node)
            if on_node_skipped:
                on_node_skipped(node, blockers[0])
            continue
        if on_node_started:
            on_node_started(node)
        try:
            result = executor.execute_node(node)
        except Exception as exc:  # noqa: BLE001 - mirrors the old worker
            failed.append(node)
            bad.add(node)
            if on_node_errored:
                on_node_errored(node, exc)
            if not continue_on_error:
                break
            continue
        executed += 1
        if on_node_finished:
            on_node_finished(node, result)
        if not getattr(result, "success", False):
            failed.append(node)
            bad.add(node)
            if not continue_on_error:
                break
    success = not failed and not skipped and not cancelled
    return LoopOutcome(success, cancelled, executed, tuple(failed), tuple(skipped))
```

Behaviour rules (these are plan 03 section 3.15, restated as code; they are the contract):

1. `continue_on_error=False` stops at the first failed node and **sends no skipped notifications** for the remainder (today's
   behaviour: later nodes keep default pens). `True`: continue; a node is skipped when **any** upstream node is in `bad`
   (failed or skipped, transitive because skipped nodes enter `bad`); both outputs of a multi-output node are one node.
2. Cancellation is checked **between nodes only**, before blocker analysis. All remaining nodes get
   `on_node_skipped(node, None)` and `outcome.cancelled = True`, `success = False`. A running node is never interrupted.
3. `success` is `False` if anything failed, was skipped or the run was cancelled.
4. Result objects are read with `getattr(result, "success", False)` (existing tests pass `SimpleNamespace` results).
5. Exceptions raised **by callbacks** propagate out of `run_nodes` (plan 08 raises `CliError` from `on_node_finished` for a
   policy violation and relies on it). The worker's callbacks are Qt `emit` calls, which do not raise.
6. `KeyboardInterrupt`/`SystemExit` are not caught (CLI signal handling).

Worker rewrite (`workflow_worker.py`):

```python
class WorkflowWorker(QThread):
    nodeStarted = Signal(object)
    nodeFinished = Signal(object, object)
    nodeErrored = Signal(object, object)
    nodeSkipped = Signal(object, object)     # node, blocker (None = cancelled)
    workflowFinished = Signal(bool)

    def __init__(self, nodes, executor, parent=None, *, continue_on_error=False, upstream=None):
        super().__init__(parent)
        self._nodes = nodes
        self._executor = executor
        self._continue = continue_on_error
        self._upstream = upstream
        self._cancel = threading.Event()
        self.cancelled = False
        self.outcome = None

    @property
    def _cancel_requested(self) -> bool:      # kept: old name, read-only
        return self._cancel.is_set()

    def request_cancel(self) -> None:
        """Cooperative cancel: takes effect before the next node."""
        self._cancel.set()

    def run(self) -> None:
        outcome = run_nodes(
            self._nodes, self._executor,
            continue_on_error=self._continue, upstream=self._upstream, cancel=self._cancel,
            on_node_started=self.nodeStarted.emit,
            on_node_finished=self.nodeFinished.emit,
            on_node_errored=self.nodeErrored.emit,
            on_node_skipped=self.nodeSkipped.emit,
        )
        self.outcome = outcome
        self.cancelled = outcome.cancelled
        self.workflowFinished.emit(outcome.success)
```

Mixin wiring (this commit): in `executeWorkflow` build `upstream = {n: connections[n]["inputs"] for n in sorted_nodes}`, call
`WorkflowWorker(sorted_nodes, executor, continue_on_error=self._run_policy()["continue_on_error"], upstream=upstream)`, connect
`worker.nodeSkipped.connect(self._on_node_skipped)`. Add to the mixin:

```python
def _run_policy(self) -> dict:
    """Run options. Plan 03 overrides the body to read errors/continue_past_failure."""
    return {"continue_on_error": False}

def _on_node_skipped(self, node: Any, blocker: Any) -> None:
    """Slot: a node was not executed. Default: nothing (plan 03 fills it)."""
```
Plan 08's headless `execute_nodes` becomes a thin wrapper: it calls `run_nodes(nodes, executor, cancel=sup.cancel, ...)`
with `on_node_started` -> `node.started` event, `on_node_finished` -> record + `node.finished` event (+ raise
`CliError` when `result.policy_violation`). It must not contain its own loop.

### F-D - Single cancellation API and Cancel button (BUG-011)

Files: `executor.py`, `workflow_execution_mixin.py`, `design_window.py`, `qt/resources.json`,
`src/trigger_designer/resources/qt/images/node_icons/ui/stop.svg` (new). Tests: `tests/unit/test_workflow_cancel.py`,
`tests/ui/test_cancel_button.py` (new).

1. **Executor** (`executor.py`): delete `self._cancel_event.clear()` in `execute_node` (`:303`); add

```python
def reset_cancel(self) -> None:
    self._cancel_event.clear()

@property
def cancel_requested(self) -> bool:
    return self._cancel_event.is_set()
```
   and change `cancel_execution()` to **always** `self._cancel_event.set()` and return `True` only when a task is currently
   running (`self._current_task_done and not is_set()`). Reason: with the clear gone the flag is a plain latch the loop resets at
   the start of each run (F-C calls `reset_cancel`). `before_node`/`after_node` observers may poll `executor.cancel_requested`.
   Honest limit (state it in the tooltip): a node already inside `exec` cannot be interrupted.
2. **Mixin** (`workflow_execution_mixin.py`): `init_workflow_execution` adds `self._workflow_executor = None`,
   `self._run_cancelled = False`, `self._cancel_listeners: list = []`, `self._last_run_codes: dict = {}`. New methods:

```python
def add_cancel_listener(self, callback) -> None:
    """Register a zero-argument callable invoked by request_run_cancel (plans 02/08)."""
    self._cancel_listeners.append(callback)

def request_run_cancel(self) -> bool:
    """THE cancel entry. Returns True when a run was in flight."""
    worker = getattr(self, "_workflow_worker", None)
    executor = getattr(self, "_workflow_executor", None)
    session = getattr(self, "_run_session", None)          # plan 02 RunSession
    active = worker is not None and worker.isRunning()
    if worker is not None:
        worker.request_cancel()
    if executor is not None:
        executor.cancel_execution()
    if session is not None:
        session.request_cancel()
    for callback in list(getattr(self, "_cancel_listeners", [])):
        try:
            callback()
        except Exception as exc:  # noqa: BLE001
            logger.warning("cancel listener failed: {}", exc)
    if active:
        self._run_cancelled = True
        self._log_to_dock("Cancel requested - stopping after the current step finishes")
        button = getattr(self, "cancel_button", None)
        if button is not None:
            button.setEnabled(False)
            button.setToolTip("Cancelling after the current step finishes")
    return active
```
   The line `session.request_cancel()` is exactly what plan 02 assumes (its `RunSession.request_cancel` sets the recorder cancel
   event and remembers `cancelled=True`); plan 02 must not add its own `request_run_cancel` (section 10).
   `isRunning()` on a worker that Qt already deleted raises `RuntimeError`; `_on_workflow_finished` sets `_workflow_worker = None`
   first (existing behaviour) so the guard is safe; wrap `worker.isRunning()` in `try/except RuntimeError: active = False`.
3. **Run controls.** New mixin method

```python
def _show_run_controls(self, running: bool) -> None:
    run_button = getattr(self, "run_button", None)
    cancel_button = getattr(self, "cancel_button", None)
    if run_button is not None:
        run_button.setEnabled(not running)
        run_button.setVisible(not running)
    if cancel_button is not None:
        cancel_button.setVisible(running)
        cancel_button.setEnabled(running)
        if running:
            cancel_button.setToolTip("Cancel run (stops after the current step)")
```
   `executeWorkflow` calls `self._show_run_controls(True)` where it used to call `run_button.setEnabled(False)` (its new
   position is defined in F-E); `_execution_cleanup` ends with `self._show_run_controls(False)` replacing the
   `if hasattr(self, "run_button"): self.run_button.setEnabled(True)` tail (`:192-193`).
4. **Cancelled-run reporting.** `_on_workflow_finished(success)`: first line reads
   `self._run_cancelled = self._run_cancelled or bool(getattr(self._workflow_worker, "cancelled", False))` **before**
   `self._workflow_worker = None`. When `_run_cancelled`: skip the `QTimer.singleShot(1000, ...)` branch and call
   `self._execution_cleanup(success=False)` immediately (like a failure). `_execution_cleanup(success)` keeps its signature
   (the existing test double overrides it with only `success`); inside it, `cancelled = getattr(self, "_run_cancelled", False)`
   selects the log text: `"Run cancelled"` and `status_text = "CANCELLED"` instead of `"FAILED"`, and it skips the
   "check logs for details" error line. `executeWorkflow` resets `self._run_cancelled = False` when a run starts.
5. **Button.** `design_window.py` `addButtons`, right after `self.run_button.clicked.connect(self.run_workflow)`:

```python
self.cancel_button = IconButton.themed(
    "Cancel run (stops after the current step)",
    rsm_icon=self.rsm.get("icon_stop"),
    parent=self,
)
self.cancel_button.move(10, 10)          # same slot as Run: they are never visible together
self.cancel_button.hide()
self.cancel_button.clicked.connect(self.request_run_cancel)
```
   `clicked` passes a `bool`; `request_run_cancel` takes no arguments, so connect via `lambda _checked=False: self.request_run_cancel()`.
   Icon: create `src/trigger_designer/resources/qt/images/node_icons/ui/stop.svg` with the same 16x16 viewBox/fill as `play.svg`
   (`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><rect x="3.5" y="3.5" width="9" height="9" rx="1.2" fill="#D0D0D0"/></svg>`;
   open `play.svg` first and copy its exact root attributes) and add to `qt/resources.json` after `icon_run_play`:
   `"icon_stop":{"path":"qt/images/node_icons/ui/stop.svg","mode":"rb"},`. `trigger.spec` already ships the whole
   `resources/qt` tree (`datas` entry for `src/trigger_designer/resources/qt`), so no spec edit.
6. **How plans attach.** Plan 02: nothing beyond `RunSession.request_cancel` (called by line above) and
   `cancelled=session._cancelled` in its `finish`. Plan 08: the GUI side (S9) is deleted from plan 08 (it is this step); its CLI
   `Supervisor` owns its own `threading.Event` and passes it as `cancel=` to `run_nodes`; nothing else is shared. Plan 03: receives
   `on_node_skipped(node, None)` for cancellation (TD-RUN-004).

### F-E - Run correctness (BUG-012, BUG-011/005 pre-conditions, BUG-005, BUG-004)

Files: `workflow_execution_mixin.py`, `design_window.py`, `executor.py`, `run_loop.py` (`GraphCycleError` already defined in F-C).
Tests: `tests/unit/test_run_preflight.py`, `tests/ui/test_run_cycle.py`, `tests/e2e/test_run_reevaluates.py`,
`tests/e2e/test_run_without_sink.py` (new).

**New `executeWorkflow` order** (this is the whole design; implement as written):

```python
def executeWorkflow(self) -> bool:
    if self._workflow_worker is not None and self._workflow_worker.isRunning():
        return False
    try:
        connections = self.getNodeConnections()
        sorted_nodes = self.topologicalSort(connections)        # may raise GraphCycleError
    except GraphCycleError as exc:
        self._run_refused = str(exc)
        self._log_to_dock(f"Cannot run: {exc}")
        return False                                            # Run button was never disabled
    self._run_refused = ""
    try:
        self.execution_results.clear()
        for node in self.getAllNodes():                         # existing visual reset
            node.markInvalid(False)
            node.grNode.resetPen()
            node.grNode.update()
            # PLAN-03 SEAM (insertion point, do not fill in foundations): plan 03 adds `node.clear_error("run")` here
        # PLAN-03 SEAM: plan 03 also bumps `self._run_generation += 1` here, once per run, before `_reevaluate_for_run`
        self._reevaluate_for_run(sorted_nodes)                   # BUG-005
        self._run_before_run_hooks(sorted_nodes)                 # F-B seam (plan 06)
        self._show_run_controls(True)                            # BUG-012: only now
        executor = NodeExecutor()
        self._workflow_executor = executor
        self._run_cancelled = False
        ...timing + log lines exactly as today...
        self._workflow_sorted_nodes = sorted_nodes
        self._last_run_codes = {}
        upstream = {n: connections[n]["inputs"] for n in sorted_nodes}
        worker = WorkflowWorker(sorted_nodes, executor,
                                continue_on_error=self._run_policy()["continue_on_error"], upstream=upstream)
        ...connect signals (incl. nodeSkipped), self._workflow_worker = worker, worker.start()
    except Exception as exc:  # noqa: BLE001 - never leave Run disabled
        self._show_run_controls(False)
        self._workflow_worker = None
        self._log_to_dock(f"Cannot start the run: {exc}")
        return False
    return True
```

**Ownership of the two error-state lines.** Plan 03 owns `node.clear_error("run")` (per node, in the visual-reset loop) and the
`self._run_generation` bump in `executeWorkflow`; plan 09 adds neither. F-E leaves the two clearly marked `PLAN-03 SEAM` comments
shown above as the insertion points, and `tests/unit/test_run_preflight.py::test_execute_workflow_seams` asserts the seam exists
(the source of `executeWorkflow` contains both `PLAN-03 SEAM` markers, in order, between the visual reset and
`_reevaluate_for_run`; a stub subclass overriding the seam sees it called before `_reevaluate_for_run`). Plan 03 step 8 fills them.

(Plan 02's `RunSession.start(self, sorted_nodes, executor)` goes between `self._workflow_executor = executor` and
`worker = ...`; plan 02 owns that insertion.)

1. **Cycle (BUG-012).** `design_window.topologicalSort` raises `GraphCycleError("Graph has at least one cycle")` instead of
   `Exception` (import from `core.ExecutionCheck.run_loop`; subclass of `Exception`, same message, so `doEvalOutputs`'s
   `except Exception` fallback still works). `run_workflow` becomes:

```python
def run_workflow(self) -> None:
    self.logInfo("Starting workflow execution...")
    try:
        started = self.executeWorkflow()
    except Exception as e:  # noqa: BLE001 - a Qt slot must not raise
        self.logError(f"Workflow execution failed: {e}")
        return
    if not started and getattr(self, "_run_refused", ""):
        QMessageBox.warning(self, "Cannot run workflow",
            "The workflow contains a loop (a step feeds itself through other steps). "
            "Remove the loop and run again.")
```
   `test_execution_visuals` (`design_window.py:~758`) also disables Run before sorting; reorder it the same way (sort first).
2. **Re-evaluate before Run (BUG-005).** Decision: re-evaluate **every** node, in topological order, on the GUI thread, using the
   existing `doEvalOutputs()`:

```python
def _reevaluate_for_run(self, sorted_nodes) -> None:
    """Make every node's live state (incoming_variable, incom_data, ...) current."""
    reevaluate = getattr(self, "doEvalOutputs", None)
    if not callable(reevaluate):
        return                                    # unit-test doubles
    for node in sorted_nodes:
        mark = getattr(node, "markDirty", None)
        if callable(mark):
            mark(True)
    reevaluate()
    invalid = [n for n in sorted_nodes if getattr(n, "isInvalid", lambda: False)()]
    if invalid:
        titles = ", ".join(str(getattr(n, "node_title", "?")) for n in invalid[:5])
        self._log_to_dock(f"Warning: {len(invalid)} step(s) have problems and may fail or "
                          f"produce empty output: {titles}")
```
   Justification (the equivalent guarantee, documented in the docstring): no node executes with stale live state, because
   every node was recomputed immediately before the worker starts; nodes that remain invalid keep their red state (the visual
   reset happens **before** the re-evaluation) and are reported in the Logging dock. We do not abort on invalid nodes because
   unwired/unfinished nodes legitimately run today (they fail with their own message) and the e2e corpus relies on that.
   Cost: File Input re-reads its file once more on the GUI thread per Run (accepted; Run already re-reads for the exec).
3. **No-sink graphs (BUG-004).** Decision: **schema verification, not implicit collection.** In
   `NodeExecutor._execute_with_timeout.target()` after `exec(...)` and still inside the `try`:

```python
if self.verify_plans:
    for value in local_vars.values():
        if isinstance(value, pl.LazyFrame):
            value.collect_schema()
```
   with `self.verify_plans: bool = True` set in `__init__`. A bad column / join key / duplicate projection (plan 03 observations
   O1, O8, O10: the dominant error class) now fails the culprit node at Run, with the original Polars exception, whether or not a
   sink exists. Data-dependent errors (a cast of one bad value) still surface only where data is read (sinks, preview); we
   deliberately do **not** `collect()` terminal nodes implicitly: that would execute a whole pipeline over multi-million-row
   inputs on every Run for graphs the user only meant to check, double the work for graphs that do have a sink, and change
   File Output timings. `collect_schema()` resolves the plan without reading data (verified in BUG-004 probe:
   `ColumnNotFoundError` raised there). Because it runs inside `target()` it is covered by the timeout and the `BaseException`
   rule. The residual limit is documented in F-I item 6.
4. **Run stays enabled on every early exit** (`try/except` shown above restores controls), and `_execution_cleanup` always
   runs after the worker (the `getPyFile` call is guarded in F-I so a raising `get_code()` can no longer skip cleanup).

### F-F - Atomic UTF-8 workflow save, metadata carry-forward, `workflow_dir`, `workflow_uuid` (BUG-002, BUG-015)

Files: `src/trigger_designer/qt/performance_scene.py`, `design_window.py` (`validateLoadedWorkflow`, `fileNew`).
Tests: `tests/ui/test_scene_save.py`, `tests/unit/test_scene_metadata.py`, `tests/ui/test_workflow_version.py` (new).

Add to `TriggerScene` (imports: `locale`, `os`, `tempfile`, `uuid`, `orjson`, `datetime, timezone`, `from loguru import logger`,
`from nodeeditor.node_scene import InvalidFile`, `from nodeeditor.utils_no_qt import dumpException`):

```python
_save_target: str | None = None          # class default; set only while saveToFile runs
_workflow_uuid: str | None = None

@property
def workflow_dir(self) -> str | None:
    """Folder of the .tds being saved (during a save) or loaded; None when unsaved.
    ``Scene.saveToFile`` serialises BEFORE it sets ``self.filename``; _save_target covers that window."""
    target = self._save_target or self.filename
    return os.path.dirname(os.path.abspath(target)) if target else None

@property
def workflow_uuid(self) -> str:
    if not self._workflow_uuid:
        self._workflow_uuid = str(self.loaded_workflow_metadata.get("workflow_uuid") or uuid.uuid4())
    return self._workflow_uuid

def reset_workflow_identity(self) -> None:
    """File > New on an existing scene: a new document, a new identity."""
    self._workflow_uuid = None
    self.loaded_workflow_metadata = {}
```
`TriggerScene.__init__` sets `self._workflow_uuid = None` (class default also exists).

`serialize()`:

```python
def serialize(self):
    data = super().serialize()
    meta = dict(self.loaded_workflow_metadata)        # unknown keys (parameters, plan 08/02 additions) survive
    meta.update(
        schema_version=WORKFLOW_SCHEMA_VERSION,
        app_version=VERSION,
        saved_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        workflow_uuid=self.workflow_uuid,
    )
    data["workflow_metadata"] = meta
    return data
```
`deserialize` keeps its body and additionally sets `self._workflow_uuid = self.loaded_workflow_metadata.get("workflow_uuid") or None`
(after reading the metadata, before `super().deserialize`). A file without metadata keeps today's default
`{"schema_version": 0, "app_version": None}`; its uuid is minted on first use and persists on the next save.

`saveToFile` override (the **only** save implementation; plans 01 and 08 must not override it):

```python
def saveToFile(self, filename: str) -> None:
    filename = os.fspath(filename)
    self._save_target = filename
    tmp_path = None
    try:
        payload = orjson.dumps(self.serialize(), option=orjson.OPT_INDENT_2)   # UTF-8 bytes; may raise
        directory = os.path.dirname(os.path.abspath(filename))
        fd, tmp_path = tempfile.mkstemp(prefix=".tds-", suffix=".tmp", dir=directory)
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, filename)            # atomic on the same volume (NTFS/POSIX)
        tmp_path = None
        self.has_been_modified = False
        self.filename = filename
    except BaseException as exc:
        logger.error("Saving {} failed: {!r}", filename, exc)
        raise
    finally:
        self._save_target = None
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
```
Rules: the target is only touched by `os.replace`, after the full payload is on disk, so a serialize error, an encoding error,
a full disk, an exception or a process kill at any earlier point leaves the previous file byte-identical (a kill leaves one stray
`.tds-*.tmp`; harmless, and the next save in that folder does not collide because `mkstemp` names are unique). `os.replace` onto a
file another program holds open raises `PermissionError`: the exception propagates (`fileSave` catches it and returns False; the
title stays modified). The directory must exist: `mkstemp` raises `FileNotFoundError` (no partial state). `orjson` always writes
UTF-8, so no locale encoding is involved. Do not edit site-packages.

`loadFromFile` override (UTF-8 first, legacy fallback):

```python
def loadFromFile(self, filename: str) -> None:
    raw = open(filename, "rb").read()                      # FileNotFoundError propagates (fileLoad handles it)
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    try:
        data = orjson.loads(raw)
    except orjson.JSONDecodeError:
        data = None
        for encoding in (locale.getpreferredencoding(False), "cp1252"):
            try:
                data = orjson.loads(raw.decode(encoding))
                logger.warning("{} is not UTF-8; decoded as {}", filename, encoding)
                break
            except (UnicodeDecodeError, LookupError, orjson.JSONDecodeError):
                continue
        if data is None:
            raise InvalidFile("%s is not a valid JSON file" % os.path.basename(filename))
    try:
        self.filename = filename                          # before deserialize: workflow_dir needs it
        self.deserialize(data)
        self.has_been_modified = False
    except Exception as exc:                              # unchanged vendored behaviour (partial loads)
        dumpException(exc)
```
(`open(filename, "rb")` is used with a `with` block in the real code; the one-liner above is shorthand.) Old files written
by the vendored code under cp1252 contain bytes such as `0xE9`, which are invalid UTF-8, so they fall to the second branch.

`design_window.py`:

* `validateLoadedWorkflow` (L~461-467): after reading `schema_version`, `if isinstance(schema_version, int) and schema_version > WORKFLOW_SCHEMA_VERSION:`
  append `f"This workflow was saved by a newer version of the app (file format {schema_version}, this app understands {WORKFLOW_SCHEMA_VERSION}). Some settings may be ignored; saving will overwrite them."` to `validation_messages` (the existing dialog path shows it). Import `WORKFLOW_SCHEMA_VERSION` from `core.constants`.
* `TriggerSubWindow.fileNew(self)`: `super().fileNew(); self.scene.reset_workflow_identity()`.

Plan hand-offs: plan 01 reads `getattr(self.node.scene, "workflow_dir", None)` (property above); plan 08 uses `scene.workflow_dir`
(not a new `workflow_base_dir`) and writes its `parameters` block into `loaded_workflow_metadata`-carried metadata, which this step
preserves; plan 02 reads `scene.workflow_uuid`.

### F-G - Dependencies and packaging in one pass (BUG-006 dependency half)

Files: `pyproject.toml`, `uv.lock`, `trigger.spec`, `src/trigger_designer/cli/__init__.py` (new stub),
`src/trigger_designer/qt/models/polars_table_viewer.py` (user-visible export error). Tests: `tests/unit/test_excel_dependency.py` (new),
`tests/unit/test_packaging_spec.py` (new).

**0. Do not clobber the user's work.** `pyproject.toml` (+21 lines, briefcase) and `uv.lock` (762 lines, CRLF churn) are dirty.
Before touching either run and keep the output in the scratchpad: `git status --short pyproject.toml uv.lock`,
`git diff pyproject.toml > "$SCRATCH/pyproject.user.diff"`, `Copy-Item uv.lock "$SCRATCH/uv.lock.user"`. Edit the **working-tree**
files with small anchored edits only (no rewrite, no `git checkout`). The commit must contain **only this step's hunks**:

```powershell
# stage pyproject.toml = HEAD + only our change (the user's briefcase hunk stays unstaged, still on disk)
git show HEAD:pyproject.toml | Set-Content -NoNewline -Encoding utf8 "$SCRATCH\pyproject.head"
# apply the same two edits (xlsxwriter line, cli script line) to "$SCRATCH\pyproject.head" with the Edit tool
$sha = git hash-object -w "$SCRATCH\pyproject.head"
git update-index --cacheinfo 100644,$sha,pyproject.toml
```
Repeat for `uv.lock`: `git show HEAD:uv.lock` into `$SCRATCH\proj\uv.lock`, copy the staged `pyproject` text to `$SCRATCH\proj\pyproject.toml`
(plus `README.md` and `src` stubs are not needed because `package = true` resolves from static metadata; if `uv lock` complains
about the readme, copy `README.md` too), run `uv lock` **inside `$SCRATCH\proj`** (this resolves only; it installs nothing), verify with
`git diff --no-index --stat` that the result differs from HEAD's lock by exactly one new `[[package]] name = "xlsxwriter"` stanza and one
`requires-dist` line, then `git hash-object -w` + `git update-index --cacheinfo` it. Finally run `uv lock` in the real tree **once** so the
user's dirty lock also gains the stanza, and `git diff "$SCRATCH\uv.lock.user" uv.lock` (use `git diff --no-index`) must show only that
stanza. If the real-tree `uv lock` rewrites more than that (CRLF/other churn beyond what was already there) restore the saved copy
and add the stanza by hand. Never run bare `uv sync` (it prunes the git-installed nodeeditor; see the `pyproject.toml:14-20` note).

**1. `pyproject.toml`** (two edits): in `dependencies`, after `"openpyxl>=3.1.0",` add `"xlsxwriter>=3.2.0,<4",`; in `[project.scripts]`
add under `trigger-designer = ...` the line `trigger-designer-cli = "trigger_designer.cli:main"` (placeholder; plan 08 implements
`main`). Create the stub **`src/trigger_designer/cli/__init__.py`** so the script is importable now:

```python
"""Headless command line. Placeholder: plan 08 (S1) replaces this file."""
import sys


def main(argv: list[str] | None = None) -> int:
    sys.stderr.write("trigger-designer-cli is not implemented yet.\n")
    return 2
```
Install into the venv without syncing: `uv pip install --python .venv\Scripts\python.exe "xlsxwriter>=3.2.0,<4"`, then
`.venv\Scripts\python.exe -c "import xlsxwriter; print(xlsxwriter.__version__)"` must print 3.x. After editing `[project.scripts]` the
console script is created by `uv pip install --python .venv\Scripts\python.exe -e . --no-deps` (same no-sync rule).

**2. `trigger.spec`.** Constraint: `core/` and its subpackages are PEP 420 namespace packages, so enumerate sources by file, like the
node loop. Add `from PyInstaller.utils.hooks import collect_submodules` to the imports, and after the node loop (L~51) add:

```python
# Qt-free core packages imported by string from exec'd generated code, importlib or plan
# modules (invisible to PyInstaller's static analysis). Missing packages (a plan not landed
# yet) simply yield nothing, so this block never needs re-editing.
_core_dir = Path("src/trigger_designer/core")
_CORE_PACKAGES = ("audit", "errors", "excel", "workpaper", "shaping", "headless")
_CORE_MODULES = ("inputs", "input_source", "profile", "sql_guard", "codegen_safe")
core_hiddenimports = []
for _pkg in _CORE_PACKAGES:
    for _path in sorted((_core_dir / _pkg).rglob("*.py")):
        _parts = _path.relative_to("src").with_suffix("").parts
        core_hiddenimports.append(".".join(_parts[:-1] if _parts[-1] == "__init__" else _parts))
for _name in _CORE_MODULES:
    if (_core_dir / f"{_name}.py").exists():
        core_hiddenimports.append(f"trigger_designer.core.{_name}")
core_hiddenimports += ["xlsxwriter", "pyarrow.parquet", "trigger_designer.cli"]
core_hiddenimports += collect_submodules("xlsxwriter")
```
and change `+ node_hiddenimports,` to `+ node_hiddenimports + core_hiddenimports,`. The package list is exactly: **core/audit
(plans 02, 04), core/errors (03), core/excel and core/workpaper (06), core/shaping (07), core/headless (08), core/input_source and
core/inputs (01), core/profile (05), core/sql_guard (07), core/codegen_safe (this plan)**. Plan 07's extra
`core/shaping` glob line and plans 04/05's single-line additions are **withdrawn** (section 10); plan 08's second `Analysis` re-uses
`analysis.hiddenimports`, so it inherits this list and only adds `trigger_designer.qt.headless`. The spec is not importable standalone
(`Analysis`, `COLLECT` need PyInstaller's spec globals): the test parses it (`ast.parse`) and `exec`s only the block between
the markers `# --- core hidden imports begin` / `# --- core hidden imports end` that the edit places around the code above.

**3. Data Preview export: no silent failure.** `polars_table_viewer.py` `export_excel` (`:1195-1208`): in `except Exception as e:`
keep `logger.error(...)` and add `from qtpy.QtWidgets import QMessageBox` + `QMessageBox.warning(self, "Export failed", f"The Excel file could not be written.\n\n{e}")`.
(Plan 06 later swaps the writer; the message stays.)

**4. Regression tests** (`tests/unit/test_excel_dependency.py`, details in 6.7): `xlsxwriter` importable; `pyproject.toml` declares it with
the exact pin; File Output "excel" `get_code()` executed against a small `LazyFrame` writes a workbook readable by `fastexcel`;
`PolarsTableViewer.export_excel` with a monkeypatched `QFileDialog.getSaveFileName` writes a readable workbook, and with a
monkeypatched `write_excel` that raises shows the warning (captured through a monkeypatched `QMessageBox.warning`).

### F-H1 - Code-injection hardening of generated code (BUG-003, BUG-032)

New: `src/trigger_designer/core/codegen_safe.py`. Edits at every site of fact 2.16. Tests: `tests/unit/test_codegen_safe.py`,
`tests/unit/test_codegen_quoting.py`, `tests/unit/test_formula_codegen.py` (new).

```python
"""Literals for generated code. Never interpolate user text into code with '{x}'."""
from __future__ import annotations

import json
import math
from typing import Any

_SCALARS = (str, int, float, bool, type(None))


def lit(value: Any) -> str:
    """Python source for a literal value. repr() quotes/escapes str; containers recurse."""
    if isinstance(value, float) and not math.isfinite(value):
        return f"float({str(value)!r})"          # float('nan'), float('inf')
    if isinstance(value, _SCALARS):
        return repr(value)
    if isinstance(value, (list, tuple)):
        inner = ", ".join(lit(v) for v in value)
        return f"[{inner}]" if isinstance(value, list) else f"({inner}{',' if len(value) == 1 else ''})"
    if isinstance(value, dict):
        return "{" + ", ".join(f"{lit(k)}: {lit(v)}" for k, v in value.items()) + "}"
    raise TypeError(f"cannot render {type(value).__name__} as a code literal")


def lit_dq(text: str) -> str:
    """Double-quoted str literal (keeps existing `separator=";"` output). JSON string syntax is valid Python."""
    if not isinstance(text, str):
        raise TypeError("lit_dq needs a str")
    return json.dumps(text, ensure_ascii=False)


def lit_list(values) -> str:
    return lit(list(values))


def safe_comment(text: Any) -> str:
    """Text safe inside a '# ...' comment: no line breaks (a newline would end the comment)."""
    return " ".join(str(text).replace("\r", " ").replace("\n", " ").replace("\x00", " ").split())
```
Caveat of `lit_dq`: `json.dumps(ensure_ascii=False)` leaves U+2028/U+2029 raw, which are legal inside Python string literals
(only `\n`, `\r` end a logical line), and escapes `"`, `\`, control chars with Python-valid escapes.

**Replacement rule** (mechanical, one site at a time): `'{x}'` / `"{x}"` in generated code becomes `{x!r}` (or `{lit(x)}` when
`x` is a list/dict, or `{lit_dq(x)}` where an existing test pins double quotes). `{lit(...)}` inside f-strings needs
`from trigger_designer.core.codegen_safe import lit, lit_dq, lit_list, safe_comment` at the top of the node module (no cycle; it imports
only stdlib). Sites (file: current text -> new text):

| File:line | Now | New |
|---|---|---|
| `file_input.py:760` | `f"idx_or_name='{self.selected_sheet}'"` | `f"idx_or_name={self.selected_sheet!r}"` |
| `file_input.py:795` | `f"separator='{self.delimiter}'"` | `f"separator={self.delimiter!r}"` |
| `file_output.py:266,281` | `f'separator="{self.delimiter}"'` / `f'separator="{delimiter}"'` | `f"separator={lit_dq(self.delimiter)}"` / `f"separator={lit_dq(delimiter)}"` (pinned test `code.count('separator=";"') == 1` keeps passing) |
| `file_output.py:287` | comment containing `'{delimiter}'` | `f"... # Custom delimiter: {safe_comment(delimiter)}"` |
| `Append.py:158-162` | `f"    how='{self.how}',\n"` | `f"    how={self.how!r},\n"` |
| `join.py:1335` | `selected_cols.append(f"'{resolved_name}'")` | `selected_cols.append(repr(resolved_name))` |
| `cleansing.py:705` | `modify_case('{self.case_modification}', ...)` | `modify_case({self.case_modification!r}, ...)` |
| `dynamic_row_builder.py:408` | `pl.DataFrame({{'{self.field_name}': values}})` | `pl.DataFrame({{{self.field_name!r}: values}})` |
| `filter.py:950,952` | `formatted_value = f"'{self.value}'"` | `formatted_value = repr(str(self.value))` |
| `filter.py:958-995` | `pl.col('{self.column}')` (11 sites), `.str.contains('{self.value}')`, `is_between('{self.value}', '{self.value2}', ...)` | `pl.col({self.column!r})`, `.str.contains({str(self.value)!r})`, `is_between({str(self.value)!r}, {str(self.value2)!r}, ...)` |
| `groupby.py:807-827` | `alias('{alias}')`, `pl.col('{column}')`, `[f"'{col}'" ...]` | `alias({alias!r})`, `pl.col({column!r})`, `lit_list(group_by_columns)` |
| `select.py:939-976` (`_build_dtype_conversion_code`) | `pl.col('{col}')...alias('{col}')` (7 sites) | `pl.col({col!r})...alias({col!r})` |
| `select.py:1660` | `[f"'{col}'" for col in ...]` joined | `lit_list(self.changes["selected_columns"])` (adjust the surrounding `", ".join` to use the returned `[...]` text without extra brackets) |
| `select.py:1695` | `[f"'{old}': '{new}'" ...]` | `[f"{old!r}: {new!r}" for old, new in rename_dict.items()]` |
| `sort.py:457` | `.sort('{column}', ...)` | `.sort({column!r}, ...)` |
| `split.py:190-204` | `with_row_index('{split_col}')`, `pl.col('{split_col}')` | `with_row_index({split_col!r})`, `pl.col({split_col!r})` |
| `unique.py:444` | quoted column interpolation | `{x!r}` / `lit_list` (open the line; same rule) |
| `running_total.py:226-231` | `pl.col("{col}")...alias("RunTot_{col}")` | `pl.col({col!r})...alias({"RunTot_" + col!r})` (compute `alias_name = "RunTot_" + col` first) |
| `transpose.py:282,299,300` | `", ".join(f"'{col}'" ...)` | `", ".join(repr(col) for col in ...)` |
| `unknown.py:86` | `# Unknown node '{self.missing_op}' — skipped` | `f"# Unknown node {safe_comment(self.missing_op)} - skipped\n"` |
| `formula.py:1313` | `duck.execute('''{combined_query}''').pl()` | `f"df_for_duck = duck.execute({combined_query!r}).pl()"` |

Two more rules for the sweep: (a) after the table, run the AST scan of 6.8 until it reports nothing inside `get_code` /
`_build_dtype_conversion_code`; any further hit found by it is fixed with the same rule; (b) helper functions that return code
fragments and are called from `get_code` (look for `def _..code`/`def _build_..` in each file you touch) get the same treatment and
are added to the test's `CODEGEN_FUNCTIONS` set.

**BUG-032 (Formula)**: besides `!r`, the generated code closes the connection on every path. Replace the tail of `code_lines`
(from `"duck = duckdb.connect(':memory:')"`) with the same statements indented under `try:` and a final `finally:` block:

```python
"duck = duckdb.connect(':memory:')",
"try:",
"    df_for_duck = ... (existing line, indented four spaces)",
"    duck.register('df_for_duck', df_for_duck)",
f"    df_for_duck = duck.execute({combined_query!r}).pl()",
"    df_for_duck = normalize_to_supported_dtypes(df_for_duck)",
f"    {self.variable_name} = df_for_duck.lazy() if hasattr({self.incoming_variable}, 'collect') else df_for_duck",
"finally:",
"    duck.close()",
```
(the `LazyFrame` result no longer streams from the closed connection because `.pl()` is eager, as today.) The Filter generated
code (`filter.py:1038`) gets the same `try/finally`. F-H2 later replaces `duckdb.connect` in these lines.

Behaviour rules: output for ordinary values is unchanged text (repr of `'abc'` is `'abc'`), so existing golden/e2e tests keep
passing; only values containing a quote/backslash/newline change (to a correct literal).

### F-H2 - Apply plan 07's SQL guard to the existing Formula and Filter-expression nodes (BUG-029, BUG-030)

**Depends on plan 07 step F7** (`src/trigger_designer/core/sql_guard.py`, plan 07 section 3.8). This is the only foundation step
scheduled after a feature-plan step. **Before writing any code** run
`Grep "def check_select_only|def make_locked_connection|def run_select" src/trigger_designer/core/sql_guard.py`; if the file or
the three names are missing, F7 has not landed: stop. The API this step relies on (plan 07 3.8, verify by reading the file):

| Name | Contract used here |
|---|---|
| `check_select_only(sql: str) -> None` | raises `ShapingError` (a `ValueError`, from `core/shaping/common.py`; message `"[TD-SHAPE-NNN] detail"`) unless exactly one read-only SELECT |
| `make_locked_connection(inputs: dict \| None = None)` | fresh in-memory DuckDB, external access off, config locked, frames registered by name; caller closes |

Files: `Preparation/filter.py`, `Preparation/formula.py`. Tests: `tests/unit/test_duckdb_safety.py` (new, 6.9).

1. Add module-level imports `from trigger_designer.core.sql_guard import check_select_only, make_locked_connection` and
   `from trigger_designer.core.shaping.common import ShapingError`; `from contextlib import closing`.
2. **Filter** (`filter.py`): at each of the three sites replace `duckdb.connect(":memory:")` by the locked connection and check the
   composed query first:
   * `:819` live: `query_t = f"SELECT * FROM df_filter WHERE {prepared}"`, `query_f = f"SELECT * FROM df_filter WHERE NOT ({prepared})"`;
     `check_select_only(query_t); check_select_only(query_f)`; `with closing(make_locked_connection({"df_filter": self.incom_data})) as duck:` then
     the two `duck.execute(...)` calls as today (drop the `duck.register` line; the helper registers; a `LazyFrame` is collected by the
     helper, which equals what `register` did). A `ShapingError` is caught by the existing `except Exception` of `_update_expression_data`
     (data stays `None`, node invalid; plan 03 translates the message).
   * `:850` `validate_expression`: `check_select_only(f"SELECT * FROM df_filter WHERE {prepared}")` first, then the locked connection
     with the zero-row `sample`, `EXPLAIN` as today. The existing `except Exception` returns the diagnostic dict; `ShapingError`'s text
     (e.g. `[TD-SHAPE-112] ... not allowed`) goes through `_shorten_error`, which keeps it.
   * `:1038` generated code: call `check_select_only(query_t)` and `check_select_only(query_f)` inside `get_code()` (a `ShapingError` is a
     normal node failure per F-A item 4) and emit
     `"from trigger_designer.core.sql_guard import make_locked_connection"`, `"duck = make_locked_connection({'df_filter': df_for_duck})"`, wrapped in
     `try/finally: duck.close()`.
3. **Formula** (`formula.py`): same pattern at `:1047` (combined query: `check_select_only(query)` inside the existing `try` so a rejection
   falls back to the sequential path, which reports the failing section), `:1074` (per section: `check_select_only(query)` inside the loop's
   `try`; `except ShapingError as exc: errors[index] = str(exc)` before the generic `except Exception`; `EXPLAIN` mode runs
   `check_select_only(query)` on the inner query and then `EXPLAIN {query}` on the locked connection), `:1121` (validation: inner
   `check_select_only(query)` then `EXPLAIN`), and `:1302` generated code (check in `get_code()`, emit `make_locked_connection({'df_for_duck': df_for_duck})`
   inside the `try/finally` from F-H1). `duck.register(relation_name, current_df)` calls inside the sequential loop stay (registering a new
   relation on a locked connection is a Python-side call, not a `SET`; the attack test asserts it works).
4. **Why both a text check and the locked connection** (BUG-030, put this in the module comment): statement type alone is not a guard
   (`PRAGMA`, `DESCRIBE`, `FROM 'x'`, `read_*()` are typed SELECT) and the config lock does not stop in-memory DDL; the helper combines
   masked-text rules, a statement-type check, a fresh connection per run and the lock.
5. The generated code now imports `trigger_designer.core.sql_guard` at Run time: plan 08's code policy allow-list must contain it
   (plan 07 section 3.9 already lists it) and F-G's spec block already hides it.

### F-I - Documentation truth pass and the `check_output.py` decision (BUG-022, BUG-013 steps 1-2, BUG-019, BUG-017 wording)

Two commits are not needed; one docs-and-hygiene commit with two parts. Tests: `tests/unit/test_getpyfile_location.py` (new).

**Part 1: docs only** (no behaviour):

1. `docs/SESSION_HANDOFF.md`: line 12 replace "**No pytest** installed - tests are throwaway scripts..." with "pytest 9.x + pytest-qt are in the dev group; run layers separately (see CONTRIBUTING.md)"; lines ~61 and ~114 delete the "PENDING - Batch B" section (done: `executor.py` `_seed_base_globals`); lines 165-166 replace the "0-byte stubs ... Union registered in enum but unimplemented" bullet by "`Join/find_replace.py` and `Documentation/comment.py` are 0-byte stubs; `Join/union.py` is implemented (956 lines, `tests/unit/test_union_node.py`)"; line 7 replace `C:\Projects\TriggerEditor` standing instruction by "run from the repo root".
2. `docs/NODE_REFERENCE.md:71-77`: remove Union from the "unused icons" table and the sentence that Union is empty; add a Union row to the node table (copy the neighbouring Join/Append row format; description "Stack two or more inputs vertically (columns matched by name or manual mapping)"); keep the sentence for `find_replace.py`/`comment.py`, `IONodes.BROWSER`, `IONodes.TEXT_INPUT`. `README.md`: add one "Union" mention to the node list (grep `Append` to find it).
3. `docs/ENHANCED_EXECUTOR_GUIDE.md`: delete every claim of `allow_file_access`, `allowed_imports`, `forbidden_functions` and the "presets" sections (lines ~53-57, 109-110, 181-191, 263-266 and their headings); replace with a "Limits that exist" section: `SecurityConfig(max_execution_time=30.0, max_memory_mb=512.0)` only, the memory limit is an after-the-fact RSS delta, a timed-out node cannot be killed (the executor replaces its worker), generated code runs with full builtins and **no sandbox** (the allow-list described in plan 08 exists only in the CLI), plus the hook attributes of 1.2 (`before_node`, `after_node`, `code_filter`, `verify_plans`).
4. `CONTRIBUTING.md:12` replace `uv sync` with the documented recipe (`uv lock --upgrade-package <name>` then `uv pip install --python .venv/Scripts/python.exe <name>==<version>`; state that bare `uv sync` prunes `qtpy-nodeeditor`); `:20` delete the `tests/integration/` line (the directory holds only `__pycache__`) and add `tests/unit`, `tests/e2e`, `tests/ui` run commands (each layer separately; bare `pytest` aborts, BUG-020).
5. `AGENTS.md` (the registerInputWidget row of the helper table and the "Prefer the above" line): reword the row to
   `registerInputWidget(w, text=..., merge_key=...)` | a Config Dock control. Debounces and diffs; **records a whole-scene snapshot (and for File Input re-reads the file) unless the node binds the control with an explicit `path=` through `push_property_change`**; and the fallback row to "serializes the whole scene; correct but heavy". Do not change any other AGENTS.md rule.
6. `docs/NODE_REFERENCE.md` (Run section) or `docs/DESIGN_SYSTEM.md`'s run paragraph: one paragraph "What Run verifies": every node is re-evaluated before Run; every lazy output's plan is schema-checked (column and type errors fail the culprit node); data-dependent errors surface where data is read (File Output, Graph, Count, previews).
7. Delete `docs/POLARS_MIGRATION_SUMMARY.md` (0 bytes) and `docs/Nodes.md` (85 bytes) with `git rm`, after `git grep -n "POLARS_MIGRATION_SUMMARY\|docs/Nodes.md"` shows no live link (fix any link found).
8. `docs/bugs.md`: no edits (it is the register; statuses are updated by the maintainers).

**Part 2: `check_output.py` decision (BUG-013 steps 1-2).** Decision: **stop writing it into the CWD; the file is untracked; it moves
to the app data dir; plan 08 does not redo any of this.**

* `git rm --cached check_output.py` (keeps the user's modified working file on disk; `.gitignore:295` then applies). Do not touch
  `scripts/check_output_polars.py` (different file).
* `design_window.py`: replace `getPyFile` with

```python
def getPyFile(self, sorted_nodes, path: "str | os.PathLike | None" = None) -> str:
    """Write the run's generated script; returns the path. Never writes into the CWD."""
    from trigger_designer.qt.preferences import app_data_dir
    target = Path(path) if path else app_data_dir() / "last_run" / "check_output.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    codes = getattr(self, "_last_run_codes", {})
    parts = [check_output_header(_source_root())]
    for node in sorted_nodes:
        code = codes.get(node)
        if code is None:                       # node did not run: ask it, but never abort the export
            try:
                code = node.get_code()
            except Exception as exc:  # noqa: BLE001
                code = f"# {safe_comment(getattr(node, 'node_title', 'node'))}: no code ({safe_comment(exc)})\n"
        parts.append(code)
    target.write_text("".join(parts), encoding="utf-8", newline="\n")
    return str(target)
```
  `_last_run_codes` is filled in the mixin's `_on_node_finished` (first line: `self._last_run_codes[node] = getattr(result, "code", "") or None`
  guarded so empty means "ask the node"; initialise in `init_workflow_execution`, F-D). Imports `Path`, `safe_comment` added.
* **Header import-path problem.** `CHECK_OUTPUT_HEADER` (`design_window.py:65-75`) only inserts `<script dir>/src`, which no longer
  exists next to the relocated script. Keep the constant **unchanged** (`tests/unit/test_file_output.py:107-116` pins it) and add:

```python
def _source_root() -> "str | None":
    if getattr(sys, "frozen", False):
        return None
    root = Path(__file__).resolve().parents[2]            # .../src
    return str(root) if (root / "trigger_designer").is_dir() else None

def check_output_header(src_root: "str | None") -> str:
    if not src_root:
        return CHECK_OUTPUT_HEADER
    return CHECK_OUTPUT_HEADER + f"_td_sys.path.insert(0, {src_root!r})\n"
```
  (so a script run from the data dir can still `import trigger_designer`).
* `_on_workflow_finished` (mixin): wrap the `getPyFile` call: `try: self.getPyFile(self._workflow_sorted_nodes) except Exception as exc: logger.warning(...)`
  so `_execution_cleanup` always runs (BUG-013 evidence bullet 5).
* `tests/conftest.py` `no_modal_dialogs`: change the stub to `def _capture_code(_self, nodes, path=None): captured["run_code"].append(nodes); return ""`
  (plan 08's earlier instruction to widen it is withdrawn).
* Plan 08 `--emit-script FILE` calls `window.getPyFile(nodes, FILE)` (the `path` parameter above) and does nothing else for this bug.

### F-J - UI test baseline repair (optional, last of the independent steps)

Files: `src/trigger_designer/qt/widgets/sql_formula_editor.py`, `src/trigger_designer/qt/performance_scene.py`, `tests/conftest.py`,
`tests/unit/test_nodeeditor_api.py` (new), `tests/ui/nodeeditor_baseline.py` (new), `docs/` none. Tests named in 6.10.

**Triage with evidence (BUG-020 table):**

| Group | Tests | Cause | Decision |
|---|---|---|---|
| A. SQL editor diagnostics | 5 (`test_formula_focus` 1, `test_formula_node` 4 incl. the aborting one) | BUG-018: `mergeCharFormat` inside `update_error_highlights` emits `textChanged`, `on_text_changed` clears the errors | **Fix the code** (below). |
| B. Installed nodeeditor too old | 22 (`test_canvas_grid_render` 6, `test_edge_geometry` 7 errors, `test_labels_groups` 1, `test_render_settings` 8) | `ee5e8fd` lacks `setPositions` and detail-LOD API (`updateDetailLod`, `detail_lod_threshold`, `MIN_GRID_SPACING_PX`, `_detail_visible`, `_content_visible`) | **Do not bump the requirement** (impossible from this repo, see below); **shim the two production call sites** and **xfail the 22 tests by capability**. |

**Why no bump (decision).** `scripts/build.bat:6-19` states the newer canvas commits "are not published yet" and live in the author's
local clone `C:\Projects\qtpy-nodeeditor`; the only published ref we can name is the installed `ee5e8fd`, which is the *old* one, and the
package is intentionally outside `uv.lock`. There is no verifiable SHA to pin, so a bumped requirement would be fiction. The honest
mechanism is a capability probe: the tests that need the new library are `xfail(strict=False)` while the library lacks the API and
simply pass (XPASS) after the author reinstalls from the clone (`scripts/sync-nodeeditor.ps1`). Production code degrades instead of raising.

1. **BUG-018 fix** (`sql_formula_editor.py`): in `SQLFormulaEditor.__init__` add `self._highlighting = False`. In
   `update_error_highlights` (`:852`) wrap the whole body: `if self._highlighting: return`; `self._highlighting = True`; `try: ...existing body... finally: self._highlighting = False`.
   In `on_text_changed` (`:586`) first statement: `if self._highlighting: return`. (Qt emits `textChanged` synchronously inside
   `mergeCharFormat`, verified; the flag makes the handler ignore the self-inflicted signal. Do not block document signals: it can
   suppress relayout.) Do not edit any assertion.
2. **Edge `setPositions` shim** (`performance_scene.py`): in `CachedGraphicsEdge.setPositions`:

```python
def setPositions(self, source, destination) -> None:
    self._invalidate_cached_path()
    parent_setter = getattr(super(), "setPositions", None)
    if parent_setter is not None:
        parent_setter(source, destination)
    else:                                   # older nodeeditor: set both ends one by one
        self.setSource(source[0], source[1])
        self.setDestination(destination[0], destination[1])
```
   `TriggerEdge.updatePositions` already calls `self.grEdge.setPositions(...)`, which is now always defined. (This removes the
   swallowed `AttributeError` tracebacks printed during every e2e load.)
3. **Capability probe test** `tests/unit/test_nodeeditor_api.py`: `test_minimum_nodeeditor_api_present` (always required: `Scene`, `Edge`,
   `QDMGraphicsEdge.setSource/setDestination`, `MultiInputNode`) and `test_full_canvas_api_present` (`QDMGraphicsEdge.setPositions`,
   `QDMGraphicsScene.updateDetailLod`) marked `xfail(strict=False, reason="installed qtpy-nodeeditor predates the canvas work; reinstall from the clone, see scripts/sync-nodeeditor.ps1")`.
4. **xfail policy** `tests/ui/nodeeditor_baseline.py` holds `NEEDS_NEW_NODEEDITOR: frozenset[str]` of exact test node-name suffixes
   (the 22 names in bugs.md BUG-020 rows B, e.g. `test_canvas_grid_render.py::test_zoomed_out_background_paints_an_empty_minor_batch`,
   all four `test_edge_geometry` parametrised ids by their function names `test_the_declared_rect_covers_the_stroke_each_pen_draws`,
   `test_the_widest_pen_is_the_hovered_one_edge_uses`, `test_a_moved_edge_declares_its_new_geometry_before_it_paints`,
   `test_moving_an_edge_invalidates_the_old_stroke_as_well_as_the_new`, `test_labels_groups.py::test_group_collapse_expand_edges`, the eight
   `test_render_settings.py` names) and `HAS_FULL_API = hasattr(QDMGraphicsScene, "updateDetailLod")`. `tests/conftest.py`
   `pytest_collection_modifyitems` (add to the existing hook, `:85-95`): for items whose `nodeid` ends with (or startswith before `[`)
   a member and `not HAS_FULL_API`, `item.add_marker(pytest.mark.xfail(raises=(AttributeError, AssertionError), strict=False, reason="..."))`.
   Setup errors in fixtures are reported as xfail by pytest when `raises` matches. Nothing else is marked: a new failure still fails.
5. **Teardown abort.** After items 1-4, run `tests\ui\test_formula_node.py` and `tests\ui\test_formula_focus.py` three times each; expected: 0
   aborts. If `test_incomplete_quotes_do_not_crash_editor` still aborts after item 1, add it to a `SKIP_ABORTS` set in the same
   baseline module with `pytest.mark.skip(reason="aborts Qt teardown; BUG-020")` (an abort hides every later test; skipping is the
   explicit policy, not a silent one) and record the reproduction in `docs/bugs.md` comments by the maintainer.
6. **Result gate.** `tests\ui` must report `0 failed, 0 errors` with `xfailed` between 0 and 22; the count of `passed` must be at least 408.

---

## 4. Ordered commit list

One commit per row, in this order. Each "done when" is run from the repo root in PowerShell after `ruff format` + `ruff check` on the
touched files (`$py = ".venv\Scripts\python.exe"`, commands are `& $py -m pytest ...`). "UI baseline" means the pre-F-J set of 20
failures + 7 errors (BUG-020) is unchanged and nothing new fails.

| # | Commit title | Done when |
|---|---|---|
| 1 | `Foundations F-A: executor hardening` | `pytest tests\unit\test_executor_hardening.py tests\unit\test_execution_result.py -q` green; `pytest tests\unit tests\e2e -q` = previous counts + new |
| 2 | `Foundations F-B: result fields and executor hooks` | `pytest tests\unit\test_executor_hooks.py tests\unit\test_executor_hardening.py tests\unit\test_execution_result.py -q` |
| 3 | `Foundations F-C: shared run loop` | `pytest tests\unit\test_run_loop.py tests\unit\test_workflow_worker_loop.py tests\unit\test_workflow_execution_mixin.py -q`; `python -c "import sys, trigger_designer.core.ExecutionCheck.run_loop; assert 'qtpy' not in sys.modules and 'PyQt6' not in sys.modules"` exits 0 |
| 4 | `Foundations F-D: cancellation API and Cancel button` | `pytest tests\unit\test_workflow_cancel.py tests\ui\test_cancel_button.py tests\ui\test_canvas_buttons.py tests\unit\test_workflow_execution_mixin.py -q` |
| 5 | `Foundations F-E: run pre-flight, re-evaluation, plan verification` | `pytest tests\unit\test_run_preflight.py tests\ui\test_run_cycle.py tests\e2e\test_run_reevaluates.py tests\e2e\test_run_without_sink.py -q`; then `pytest tests\e2e -q` (20 + new passed) |
| 6 | `Foundations F-F: atomic UTF-8 save, metadata, workflow_dir` | `pytest tests\ui\test_scene_save.py tests\unit\test_scene_metadata.py tests\ui\test_workflow_version.py tests\unit\test_workflow_serialization.py -q` |
| 7 | `Foundations F-G: xlsxwriter, spec hidden imports, CLI stub` | `pytest tests\unit\test_excel_dependency.py tests\unit\test_packaging_spec.py tests\unit\test_file_output.py -q`; `python -c "import xlsxwriter"`; `git diff --cached --stat` shows only the intended hunks of `pyproject.toml`/`uv.lock` |
| 8 | `Foundations F-H1: codegen literals and quoting` | `pytest tests\unit\test_codegen_safe.py tests\unit\test_codegen_quoting.py tests\unit\test_codegen_no_unsafe_quotes.py tests\unit\test_formula_codegen.py tests\unit\test_file_output.py -q`; `pytest tests\e2e -q` |
| 9 | `Foundations F-I: docs truth pass, getPyFile location` | `pytest tests\unit\test_getpyfile_location.py tests\e2e\test_run_side_effects.py tests\unit\test_workflow_execution_mixin.py tests\unit\test_file_output.py -q`; `git ls-files check_output.py` prints nothing; `docs\Nodes.md` gone |
| 10 | `Foundations F-J: UI baseline repair` | `pytest tests\unit\test_nodeeditor_api.py -q`; `pytest tests\ui -q` -> `0 failed`, `0 errors` |
| - | *(plan 07 step F7 creates `core/sql_guard.py`)* | plan 07's own `tests\unit\test_sql_guard.py` |
| 11 | `Foundations F-H2: SQL guard on Formula and Filter` | `pytest tests\unit\test_duckdb_safety.py tests\unit\test_formula_codegen.py -q`; `pytest tests\ui\test_formula_node.py -q` and the Filter UI test files (`Glob tests\ui\test_filter*.py`) show no new failures; `pytest tests\e2e -q` |

Commits 1-3 are strictly ordered (each edits `executor.py`/the worker). Commits 6 (scene) and 7 (packaging) touch disjoint files and may
swap with each other, never with 1-5. Commit 9 needs 2 (`result.code`) and 4 (`_last_run_codes` initialisation).

---

## 5. Edge cases

| Case | Behaviour | Test |
|---|---|---|
| Node code raises `SystemExit`/`KeyboardInterrupt` (user `sys.exit()`) | node failure, worker survives | `test_base_exception_system_exit_is_a_failure` |
| `get_code()` raises | normal failure, error text = the exception text, `before_node` not called | `test_get_code_raising_is_a_normal_failure`, `test_before_node_not_called_when_get_code_raises` |
| Hook raises | node unaffected; WARNING logged | `test_hook_exception_never_fails_a_node` |
| `code_filter` raises (policy) | failure, `policy_violation` True when the class says so; `result.code` holds the raw text | `test_code_filter_failure_sets_policy_violation` |
| Timeout then another node on the same executor | second node completes quickly (fresh worker) | `test_timeout_replaces_the_worker` |
| `continue_on_error=False`, failure | no skipped callbacks, `skipped == ()` | `test_stop_at_first_failure_has_no_skip_notifications` |
| Diamond A->(B,C)->D, B fails, continue | C runs, D skipped with blocker B | `test_diamond_skips_only_dependents` |
| Multi-output node fails | both downstream branches skipped (blocker = that node) | `test_multi_output_failure_skips_both_branches` |
| Cancel before first node | all nodes skipped with blocker `None`, `cancelled` | `test_cancel_before_start_skips_everything` |
| Cancel mid-run | the running node finishes; rest skipped with `None` | `test_cancel_between_nodes` |
| `request_run_cancel` with no run | returns `False`, no exception, listeners still called | `test_request_run_cancel_idle_is_a_noop` |
| Cyclic graph | no exception, Run still enabled, warning shown, nothing executed | `test_cycle_keeps_run_button_enabled` |
| Re-evaluation raises | controls restored, run not started | `test_preflight_exception_restores_run_button` |
| Node invalid after re-eval | Run proceeds, warning logged, node stays red | `test_invalid_nodes_are_reported_not_hidden` |
| Bad column in a lazy `select`, no sink | node fails with `ColumnNotFoundError` | `test_bad_select_column_fails_run_without_sink` |
| Valid lazy plan | untouched, no data read | `test_verify_plans_does_not_collect_data` |
| Save: serialize raises / encoding error / replace fails / kill mid-write | previous file byte-identical, no `.tds-*.tmp` left (except after a kill) | section 6.6 |
| Save to a locked target | `PermissionError` propagates, `fileSave` returns False, title still modified | `test_locked_target_keeps_modified_flag` (Windows: hold the file open) |
| Old cp1252 `.tds` | loads, WARNING logged | `test_legacy_cp1252_file_loads` |
| `.tds` with UTF-8 BOM | loads | `test_utf8_bom_loads` |
| Newer `schema_version` | validation message shown | `test_newer_schema_version_warns` |
| File > New after a save | `workflow_uuid` differs | `test_file_new_resets_workflow_identity` |
| Delimiter/sheet/column/filter value `'`, `\`, `');import os #`, newline, `"` | code parses and does not run injected text | `test_hostile_values_roundtrip_through_exec` |
| Formula text contains `'''` | generated code compiles; live and Run results equal | `test_formula_with_triple_quotes_compiles` |
| Formula query fails at Run | `duck.close()` still executed | `test_generated_formula_closes_connection_on_error` |
| Filter `x IN (SELECT 1 FROM read_csv('f'))` | rejected before execution (TD-SHAPE-112) | `test_filter_cannot_read_files` |
| Filter `1=1; COPY (SELECT 42) TO 'out.csv'` | rejected (TD-SHAPE-110); `out.csv` absent | `test_filter_cannot_write_files` |
| Formula section `(SELECT k FROM read_csv('f'))` | section error; no data returned | `test_formula_cannot_read_files` |
| `PRAGMA`/`DESCRIBE`/`FROM 'x.csv'` (typed SELECT by DuckDB) | rejected | `test_statement_type_alone_is_not_enough` |
| Plan 07 F7 absent when F-H2 starts | stop; do not write a local copy of the guard | procedure in F-H2 |

---

## 6. Test plan (named tests with assertions; reproduction tests fail on the old code and pass on the new)

Layers follow directories (`tests/unit`, `tests/ui`, `tests/e2e`); markers are automatic. Qt-free tests must not import `qtpy`.
Stub node helper used throughout (new file `tests/support/stub_nodes.py`):

```python
class StubNode:
    content = None
    def __init__(self, code="x = 1", title="stub", raises=None):
        self.node_title, self._code, self._raises = title, code, raises
    def get_code(self):
        if self._raises:
            raise self._raises
        return self._code
```

### 6.1 F-A - `tests/unit/test_executor_hardening.py`

* `test_panic_exception_is_a_failure_not_success`: code `import polars.exceptions as pe\nraise pe.PanicException("boom")`; `result.success is False`; `"boom" in result.error`. **Fails on the old code** (`success True`).
* `test_worker_survives_panic`: afterwards `ex._node_worker_thread.is_alive()` and `execute_node(StubNode("x = 1"))` returns `success is True` in `< 2 s` (`time.perf_counter()`), executor `max_execution_time = 3`.
* `test_base_exception_system_exit_is_a_failure`: code `raise SystemExit(3)` -> `success False`; the next node succeeds.
* `test_get_code_raising_is_a_normal_failure` (BUG-010): `StubNode(raises=ValueError("File Output: no incoming data"))` -> `success False`, `"no incoming data" in result.error`, no `UnboundLocalError`. **Fails on the old code.**
* `test_timeout_replaces_the_worker`: `max_execution_time = 0.5`; node 1 `import time; time.sleep(3)` -> `"timed out" in error`; node 2 `y = 2` on the same executor succeeds in `< 1.5 s`.

### 6.2 F-B - `tests/unit/test_executor_hooks.py`

* `test_result_has_new_fields_with_defaults`: `ExecutionResult(success=True)` has `exception None`, `traceback_text ""`, `exception_type ""`, `code ""`, `started_at ""`, `finished_at ""`, `policy_violation False`; the first ten field names (`dataclasses.fields`) are unchanged and in order.
* `test_without_frames_nulls_exception_keeps_text`: result with `exception=ValueError("e")`, `traceback_text="tb"` -> copy has `exception is None`, `traceback_text == "tb"`; original unchanged.
* `test_success_records_code_and_timestamps`: `result.code == "x = 1"`; `started_at`/`finished_at` match `^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{6}Z$`, `finished_at >= started_at`.
* `test_failure_records_exception_type_and_traceback`: code `x = 1/0` -> `isinstance(result.exception, ZeroDivisionError)`, `result.exception_type == "builtins.ZeroDivisionError"`, `"ZeroDivisionError" in result.traceback_text`, `result.error.startswith("division by zero")` (pins that the string is unchanged).
* `test_hooks_run_in_order_with_arguments`: `code_filter("x = 1")` returns `"x = 2"`; recorded order `["filter","before","after"]`; `after_node` receives `(node, vars, result)` with `vars["x"] == 2`; `result.code == "x = 1"` (raw).
* `test_after_node_only_on_success`, `test_before_node_not_called_when_get_code_raises`, `test_hook_exception_never_fails_a_node` (hook raises -> `success True`).
* `test_code_filter_failure_sets_policy_violation`: filter raises `class P(Exception): policy_violation = True` -> `success False`, `result.policy_violation is True`, `result.code` is the raw text.
* `test_after_node_can_replace_a_variable`: hook sets `local_variables["x"] = 9` -> `result.variables["x"] == 9` and `ex.execution_context["x"] == 9`.

### 6.3 F-C - `tests/unit/test_run_loop.py` (Qt-free) and `tests/unit/test_workflow_worker_loop.py`

Fake executor: `execute_node(node)` returns `SimpleNamespace(success=node.ok)`; record events as tuples `("start"|"finish"|"error"|"skip", node.name, extra)`.

* `test_all_ok`: `LoopOutcome(success=True, cancelled=False, executed=3, failed=(), skipped=())`.
* `test_stop_at_first_failure_has_no_skip_notifications`: a, b (fails), c, `continue_on_error=False` -> events end after `finish b`; `outcome.skipped == ()`, `failed == (b,)`.
* `test_diamond_skips_only_dependents`: a -> b,c -> d with b failing, `continue_on_error=True`, `upstream={b:[a], c:[a], d:[b,c]}` -> c executed, d skipped with blocker `b`; `success False`.
* `test_multi_output_failure_skips_both_branches`, `test_skipped_blocker_is_first_failed_parent_in_input_order`, `test_transitive_skip` (a fails; b depends on a; c on b; both skipped, blocker of c is b).
* `test_cancel_before_start_skips_everything` (event pre-set: every node `skip ... None`, `cancelled True`), `test_cancel_between_nodes` (the finished-callback of node 1 sets the event -> nodes 2,3 skipped with `None`, `executed == 1`).
* `test_errored_callback_when_execute_node_raises`, `test_callback_exception_propagates` (finished-callback raises `RuntimeError` -> `run_nodes` raises it), `test_result_without_success_attribute_counts_as_failure`, `test_executor_reset_cancel_is_called` (fake with a `reset_cancel` counter == 1).
* **Parity (GUI loop vs CLI loop)** in `test_workflow_worker_loop.py`: for the scenarios above build the same fake graph; collect events (a) by calling `run_nodes` directly with recording callbacks (this is what plan 08's `execute_nodes` must do), (b) by connecting a `WorkflowWorker`'s five signals to recorders and calling `worker.run()` synchronously; assert the two event lists are equal, `worker.outcome == outcome`, `worker.cancelled == outcome.cancelled`. Plan 08's own test monkeypatches `run_nodes` and asserts `execute_nodes` calls it once.
* `test_worker_default_arguments_keep_old_behaviour`: `WorkflowWorker(nodes, executor)` stops at the first failure; the existing mixin tests pass unchanged.

### 6.4 F-D - `tests/unit/test_workflow_cancel.py`, `tests/ui/test_cancel_button.py`

* `test_cancel_execution_always_sets_the_event`: idle executor: `cancel_execution() is False` and `cancel_requested is True`; `reset_cancel()` clears it.
* `test_request_run_cancel_sets_worker_executor_and_session`: window double with a fake worker (`isRunning() True`, records `request_cancel`), fake executor (records `cancel_execution`), fake `_run_session` (records `request_cancel`), one listener; one call -> each recorded exactly once, returns `True`, `_run_cancelled is True`.
* `test_request_run_cancel_idle_is_a_noop`: no worker -> returns `False`, no exception.
* `test_cancelled_run_is_reported_as_cancelled`: `_on_workflow_finished(False)` with `_run_cancelled=True` -> `_execution_cleanup` called with `False` immediately (no `QTimer`), the dock log contains `"Run cancelled"`.
* `tests/ui/test_cancel_button.py`: `window.cancel_button` exists and is hidden initially; `objectName() == "IconButton"`; 30x30; non-empty `toolTip()` and `accessibleName()`; icon not null; `_show_run_controls(True)` hides run / shows cancel and back; click with no worker is a no-op; with a fake running worker the click calls `request_cancel` once, disables the button and the tooltip contains "Cancelling".
* Real-thread test (`qtbot`): 3-node graph whose first node's code sleeps 0.3 s; `executeWorkflow()`; `window.request_run_cancel()` immediately; wait for `executionResultsChanged`; node 2's `grNode` never got `setPenExecuting`; `run_button.isEnabled()`.

### 6.5 F-E - run correctness

* `tests/ui/test_run_cycle.py::test_cycle_keeps_run_button_enabled` (BUG-012 probe: two Select nodes wired A->B and B->A, `window.run_workflow()`): no exception, `run_button.isEnabled()`, `_workflow_worker is None`, the stubbed `QMessageBox.warning` text contains "loop". **Fails on the old code.**
* `tests/unit/test_run_preflight.py`: `test_topological_sort_raises_graph_cycle_error`; `test_preflight_exception_restores_run_button` (monkeypatch `_reevaluate_for_run` to raise); `test_invalid_nodes_are_reported_not_hidden` (fake invalid node -> dock log contains "problems"); `test_before_run_hooks_run_after_reevaluation` (order list `["reeval","hooks","worker"]`); `test_hook_exception_does_not_abort_run`; `test_execute_workflow_seams` (the two `PLAN-03 SEAM` insertion points exist in `executeWorkflow` in the order above).
* `tests/e2e/test_run_reevaluates.py::test_run_after_unevaluated_load_uses_real_data` (BUG-005): load `savedfiles/1. in-select.tds` via the e2e materialiser, set `select.content.data = None; select.content.incoming_variable = ""`, `run_workflow_and_wait`; the executed Select output has `> 0` rows (`executed_frame(window, select).collect().height`). **Fails on the old code** (empty frame).
* `tests/e2e/test_run_without_sink.py::test_bad_select_column_fails_run_without_sink` (BUG-004): same file, `select.content.changes["selected_columns"] = ["NoSuchCol"]`, run: the Select node `isInvalid()`, no result stored for it, the Logging dock text contains `"NoSuchCol"`. **Fails on the old code.** Unit: `test_verify_plans_does_not_collect_data` (a LazyFrame whose `map_batches` raises on execution but whose schema is valid executes with `success True`), `test_verify_plans_can_be_disabled` (`ex.verify_plans = False` lets the bad plan "succeed").

### 6.6 F-F - save/load (`tests/ui/test_scene_save.py`, `tests/unit/test_scene_metadata.py`, `tests/ui/test_workflow_version.py`)

Fixture: `w = TriggerSubWindow(); node = SelectNodeClass(w.scene); w.scene.saveToFile(str(p))` as in the BUG-002 probe.

* `test_save_roundtrips_non_cp1252_title`: title `"A \u2192 \u65e5"`; save + load in a new window; title survives; `p.read_bytes().decode("utf-8")` succeeds and contains the arrow. Run **without** `PYTHONUTF8` (fails on the old code with `UnicodeEncodeError`).
* `test_save_never_truncates_when_serialize_raises`: monkeypatch `w.scene.serialize` to raise `RuntimeError`; `before = p.read_bytes()`; `saveToFile` raises; `p.read_bytes() == before`; `list(p.parent.glob(".tds-*.tmp")) == []`; `has_been_modified` unchanged. **Fails on the old code** (size 0).
* `test_save_never_truncates_on_encoding_error` (simulated): monkeypatch `performance_scene.orjson.dumps` to raise `UnicodeEncodeError("utf-8", "x", 0, 1, "boom")`; same assertions.
* `test_save_keeps_old_file_when_replace_fails`: monkeypatch `os.replace` to raise `OSError`; same assertions.
* `test_kill_mid_write_leaves_target_intact` (subprocess): a script written to `tmp_path` builds an offscreen `QApplication` and a `TriggerSubWindow`, saves once to `p`, copies `p` to `p.with_suffix(".before")`, then monkeypatches `os.replace` to `os._exit(9)`, changes the title and calls `saveToFile(p)`. Parent asserts `returncode == 9`, `p.read_bytes() == before bytes`, and that a following in-process `saveToFile(p)` succeeds despite the stray `.tds-*.tmp`.
* `test_atomic_save_replaces_content`: second save with a changed title: file differs, valid JSON, `has_been_modified is False`, `scene.filename == str(p)`.
* `test_legacy_cp1252_file_loads`: a freshly saved workflow dict containing `\u00e9` in a title, re-encoded with `.encode("cp1252")` and written to disk; the load returns the right title and a WARNING was logged. `test_utf8_bom_loads`; `test_invalid_json_raises_invalid_file` (`InvalidFile`).
* `test_workflow_dir_during_save_uses_target`: scene whose `filename` is an old path; `serialize` wrapped to record `scene.workflow_dir`; `saveToFile(tmp/x/wf.tds)` -> recorded dir `== str(tmp/x)`; afterwards `_save_target is None` and `workflow_dir == str(tmp/x)`.
* `test_extra_metadata_keys_survive_save` (BUG-015): `scene.loaded_workflow_metadata["parameters"] = {"a": 1}`; save, reload: `parameters == {"a": 1}`; `schema_version == 2`; `saved_at` ends with `Z` and parses.
* `test_workflow_uuid_is_stable_across_saves` and `test_file_new_resets_workflow_identity`.
* `tests/ui/test_workflow_version.py::test_newer_schema_version_warns`: patch the saved JSON `schema_version` to 99; `validateLoadedWorkflow()` returns a message containing "newer version".

### 6.7 F-G - `tests/unit/test_excel_dependency.py`, `tests/unit/test_packaging_spec.py`

* `test_xlsxwriter_is_installed_and_declared`: `import xlsxwriter`; `tomllib` of `pyproject.toml`: a dependency starting `xlsxwriter>=3.2.0,<4` (whitespace-insensitive) and `trigger-designer-cli` in `[project.scripts]`.
* `test_file_output_excel_writes_a_readable_workbook` (BUG-006): content built like `tests/unit/test_file_output.py::_make_content` (copy the helper) with `file_format="excel"`, `filePath=str(tmp/"o.xlsx")`; exec the generated code with `{"var_in": pl.LazyFrame({"a":[1,2],"b":["x","y"]})}`; read back with `fastexcel.read_excel(path).load_sheet(0)` and convert like the node does; rows equal. **Fails on the old tree** (`ModuleNotFoundError`).
* `test_data_preview_export_writes_workbook`: `PolarsTableViewer(dataframe=df)` (pattern of `tests/ui/test_polars_table_viewer.py`), monkeypatch `QFileDialog.getSaveFileName` to return `(path, "")`, call `export_excel()`, read back.
* `test_data_preview_export_reports_failure`: monkeypatch `pl.DataFrame.write_excel` to raise; monkeypatch `QMessageBox.warning` to capture; `export_excel()` -> one warning whose text contains the exception text.
* `test_trigger_spec_core_hidden_imports_block`: `ast.parse` the whole spec; `exec` only the text between the markers `# --- core hidden imports begin` / `# --- core hidden imports end` in a namespace with `Path` and `collect_submodules = lambda name: []`, cwd = repo root; assert `"xlsxwriter"` and `"pyarrow.parquet"` in `core_hiddenimports`; for every directory among `audit errors excel workpaper shaping headless` that exists under `src/trigger_designer/core`, at least one `trigger_designer.core.<pkg>` entry exists; every existing module of `inputs input_source profile sql_guard codegen_safe` is listed (missing files are skipped, so the test passes before the feature plans land).

### 6.8 F-H1 - injection tests

* `test_codegen_safe.py`: for `"a'b"`, `"\\"`, `"\n"`, `"');import os #"`, `"a\x00b"`, `["a", "b'c"]`, `{"k": ("a",)}`: `ast.literal_eval(lit(x)) == x` and `"\n" not in lit(x)`; `eval(lit(float("nan")))` is nan; `ast.literal_eval(lit_dq('a"b')) == 'a"b'`; `lit(object())` raises `TypeError`; `safe_comment("a\nb")` has no `\n`/`\r`.
* `tests/unit/test_codegen_quoting.py::test_hostile_values_roundtrip_through_exec` (BUG-003): parametrize `VALUE in ["'", "\\", "');import os #", "\n", '"', "a\x00b"]` x settings: File Input `delimiter` and `selected_sheet`, Select selected column and rename, Filter `value`/`column`, Group By alias/column, Sort column, Split column, Dynamic Row Builder `field_name`, `unknown.missing_op`. Contents are built with `__new__` like the unit tests (brief 9.2); `ast.parse(content.get_code())` succeeds; executing the code against a 2-row CSV raises at most Polars/`ValueError`-class errors, never `SyntaxError`. **Reproduction case**: File Input `delimiter = ",')\nopen(MARKER,'w').write('pwned')\nx = pl.scan_csv('d.csv', separator='"` -> `os.path.exists(MARKER)` is False after exec. Fails on the old code (marker created).
* `tests/unit/test_codegen_no_unsafe_quotes.py` (sweep guard; the scan is implemented in the test file):

```python
CODEGEN_FUNCTIONS = {"get_code", "_build_dtype_conversion_code"}   # extended by F-H1 rule (b)

def hits(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for fn in ast.walk(tree):
        if isinstance(fn, ast.FunctionDef) and fn.name in CODEGEN_FUNCTIONS:
            for node in ast.walk(fn):
                if isinstance(node, ast.JoinedStr):
                    v = node.values
                    for i, part in enumerate(v):
                        if (isinstance(part, ast.FormattedValue) and part.conversion != ord("r")
                                and part.format_spec is None and 0 < i < len(v) - 1
                                and isinstance(v[i - 1], ast.Constant) and isinstance(v[i + 1], ast.Constant)
                                and isinstance(v[i - 1].value, str) and v[i - 1].value[-1:] in "'\""
                                and v[i + 1].value[:1] == v[i - 1].value[-1:]):
                            yield (path.name, fn.name, node.lineno)

def test_no_unquoted_interpolation_in_generated_code():
    found = [h for p in NODES_DIR.rglob("*.py") if p.stat().st_size for h in hits(p)]
    assert found == []
```
* `tests/unit/test_formula_codegen.py` (BUG-032): `test_formula_with_triple_quotes_compiles` - a Formula section text `'''x'''`: `compile(get_code(), "<f>", "exec")` succeeds and the executed column equals the live result (`"'x'"`); **fails on the old code** (`SyntaxError`). `test_generated_formula_closes_connection_on_error`: exec the code with a failing query, catch the error, then `duck.execute("select 1")` in the namespace raises `duckdb.Error`. `test_generated_filter_closes_connection_on_error` likewise.

### 6.9 F-H2 - attack tests (`tests/unit/test_duckdb_safety.py`)

Fixture: `evil = tmp_path / "evil.csv"` (`k\ntopsecret\n`), `monkeypatch.chdir(tmp_path)`; contents built as in the Filter/Formula unit tests with `incom_data = pl.DataFrame({"x": [1, 2, 3]})`.

* Filter, parametrized expressions, each must leave `content.data is None` (or `validate_expression` returns one diagnostic) **and** create no file: `x IN (SELECT 1 FROM read_csv('evil.csv'))`, `... READ_CSV_AUTO(...)`, `... read_text(...)`, `... glob('*')`, `x = (select count(*) from 'evil.csv')`, `1=1; COPY (SELECT 42 AS pwn) TO 'leak.csv' (FORMAT CSV)`, `1=1; ATTACH 'x.db'`, `1=1; INSTALL httpfs`, `1=1; CREATE TABLE z(a int)`, `x > 0) UNION SELECT * FROM df_filter --`, `x IN (SELECT 1 FROM duckdb_settings())`, `x IN (SELECT 1 FROM query('select 1'))`, `random() > 0.5`. After each: no `leak.csv`, no `x.db`.
* `test_filter_cannot_read_files` and `test_filter_cannot_write_files` (the two named BUG-029 reproductions; fail on the old code: `data` had a matching row; `leak.csv` existed).
* `test_formula_cannot_read_files`: section text `(SELECT k FROM read_csv('evil.csv') LIMIT 1)` -> `section_errors` has that index and `"topsecret"` is in no result frame; `test_formula_multi_statement_rejected`: `x; COPY (SELECT 1) TO 'leak.csv'`.
* `test_statement_type_alone_is_not_enough` (BUG-030): `check_select_only` raises `ShapingError` for each of `pragma version`, `describe select 1`, `select * from read_csv('evil.csv')`, `from 'evil.csv'` (all four are typed `SELECT` by DuckDB's `extract_statements`).
* Locked-connection facts: on `make_locked_connection({"df": frame})`, `read_csv('evil.csv')`, `copy (select 1) to 'o.csv'`, `attach 'x.db'`, `set enable_external_access=true` each raise `duckdb.Error`; `con.register("df2", frame)` after creation works (the sequential Formula path depends on it).
* `test_normal_expressions_still_work`: Filter `x > 1`, `x IN (1, 2) AND NOT x = 3`; Formula `[x] * 2` give the same frames as before F-H2.
* Generated code: with a hostile expression `get_code()` itself raises `ShapingError` (no code is produced); with a benign one `"make_locked_connection" in code and "duckdb.connect" not in code`.

### 6.10 F-I and F-J tests

* `tests/unit/test_getpyfile_location.py`: `test_getpyfile_does_not_write_into_cwd` (`monkeypatch.chdir(tmp_path)`, `TRIGGER_DESIGNER_DATA_DIR` set to another tmp dir, `getPyFile([node])`: `list(tmp_path.iterdir()) == []`, returned path ends with `last_run/check_output.py`, file exists, decodes as UTF-8, no `\r`); `test_getpyfile_uses_recorded_codes_not_get_code` (`_last_run_codes[node] = "x = 1\n"`, node whose `get_code` raises -> file contains `x = 1`); `test_getpyfile_survives_raising_get_code`; `test_getpyfile_path_argument`; `test_exported_script_can_import_the_package` (append `import trigger_designer` to the written script, run it with `sys.executable` from another cwd: exit 0); the existing `test_check_output_header_puts_src_on_path` keeps passing (constant unchanged).
* `tests/e2e/test_run_side_effects.py::test_run_does_not_write_into_cwd` (BUG-013): chdir to `tmp_path`, `run_workflow_and_wait` on a small workflow with the **real** `getPyFile` (patch only the dialogs, not `getPyFile`), `list(tmp_path.iterdir()) == []`.
* `tests/unit/test_docs_present.py`: every file under `docs/` is non-empty; `ENHANCED_EXECUTOR_GUIDE.md` contains none of `allowed_imports`, `forbidden_functions`, `allow_file_access`.
* F-J: `tests/unit/test_nodeeditor_api.py` as in F-J item 3; `tests/ui/test_formula_editor_loop.py::test_highlighting_does_not_fire_text_changed` (BUG-018): editor text `'" unfinished [a]'`; after `check_for_errors()` and `QApplication.processEvents()` (let the timer fire once) `editor.errors` is still non-empty (the old code erased it); the five existing tests (`test_formula_focus` 1, `test_formula_node` 4) pass; `test_baseline_xfail_list_is_exact` (every name in `NEEDS_NEW_NODEEDITOR` exists as a test function in its file).

---

## 7. Acceptance checklist

- [ ] Eleven commits exist (F-A..F-G, F-H1, F-I, F-J, F-H2) with the titles of section 4; F-H2 only after plan 07 F7.
- [ ] A `PanicException` node is a failure; the worker thread survives; a raising `get_code()` is an ordinary failure; a timed-out node does not stall later nodes.
- [ ] `ExecutionResult` has exactly the seven new fields, `without_frames()` nulls `exception`; `before_node`, `after_node`, `code_filter` exist with the signatures of 1.2 and are no-ops by default.
- [ ] `run_nodes` is Qt-free, the worker uses it (and plan 08's CLI will); parity test green; continue/skip/cancel semantics as plan 03 section 3.15.
- [ ] One `request_run_cancel()`; Cancel button visible only while running; a cancelled run logs "Run cancelled"; Run is always restored.
- [ ] Cyclic graph: no exception, Run enabled; every Run re-evaluates all nodes first; a bad lazy plan fails its node without a sink.
- [ ] `saveToFile` is atomic and UTF-8; old cp1252 files load; metadata extras and `workflow_uuid` survive saves; `workflow_dir` works during a save; a newer schema warns.
- [ ] `xlsxwriter>=3.2.0,<4` declared, locked (one stanza), installed in `.venv`; `trigger.spec` has the core hidden-import block; the user's dirty `pyproject.toml`/`uv.lock` hunks are still in the working tree and not in the commit; `trigger-designer-cli` stub importable.
- [ ] File Output "excel" and Data Preview export are tested; a failed preview export shows a message.
- [ ] No f-string in a `get_code` quotes interpolated text without `!r`/`lit` (AST test); hostile `.tds` values do not execute; Formula with `'''` compiles; connections are closed in `finally`.
- [ ] Filter expression and Formula cannot read or write files; the attack table is green; generated code uses the locked connection.
- [ ] Stale docs corrected, placeholders deleted, `check_output.py` untracked and never written to the CWD, the header can import the package from the data dir.
- [ ] `tests\ui` shows 0 failed / 0 errors (xfail only for the 22 capability tests); section 8 commands green; `ruff` clean on every touched file.

---

## 8. Verification commands

Always layer by layer; bare `pytest` aborts the process (BUG-020) and stays off the gate even after F-J.

```powershell
$py = ".venv\Scripts\python.exe"
& $py -m ruff format <touched files>; & $py -m ruff check <touched files>
& $py -m pytest tests\unit -q          # 334 passed before this plan; + new tests, 0 failed
& $py -m pytest tests\e2e -q           # 20 passed before; + new, 0 failed
& $py -m pytest tests\ui -q            # before F-J: 403 passed / 20 failed / 7 errors (baseline); after F-J: 0 failed, 0 errors
& $py -m pytest tests\ui\test_formula_node.py -q ; & $py -m pytest tests\ui\test_formula_focus.py -q   # 3 times after F-J: no abort
git status --short pyproject.toml uv.lock                    # F-G: still dirty afterwards (user hunks kept)
git diff --cached --stat                                      # F-G: only the intended hunks
git ls-files check_output.py                                  # F-I: empty
```
Baseline comparison before F-J: save the failure ids of `pytest tests\ui -q -rfE` once, before commit 1, in the scratchpad and diff after
each commit; any id outside the BUG-020 list is a regression.

---

## 9. Pitfalls

1. **Dirty tree.** `pyproject.toml`, `uv.lock`, `main.py`, `check_output.py`, `file_opener.py`, `model_pandas.py`, `__main__.py` are the user's. Stage explicit paths; for the two shared files use the `git update-index --cacheinfo` recipe of F-G; never `git add -A`, `git stash`, `git checkout -- file`, `git reset --hard`.
2. **No bare `uv sync` / syncing `uv run`.** It prunes the git-installed `nodeeditor`. Use `.venv\Scripts\python.exe` and `uv pip install --python ...`.
3. **`_execution_cleanup(success)`** is overridden with only `success` by the existing test double: pass extra information through attributes (`_run_cancelled`), never new arguments.
4. **`SimpleNamespace` results** in existing tests have no `exception`/`code`: always `getattr(result, "x", default)` in mixin code.
5. **`DummyWindow` in `test_workflow_execution_mixin.py` is not a `TriggerSubWindow`** (no `run_button`, `doEvalOutputs`, `_workflow_executor`): every new mixin call uses `getattr(self, ..., None)` guards (as in the skeletons).
6. **`Scene.saveToFile` order.** The vendored one serialises before it sets `filename`; hence `_save_target`.
7. **`os.replace` across volumes fails**: the temp file is created in the target's directory on purpose.
8. **Namespace packages.** `core/` has no `__init__.py`; do not add one (it changes import resolution of the tree); that is why the spec globs files.
9. **`lit()` of numpy scalars** raises `TypeError`; convert with `int()`/`float()` at the call site. Never fall back to `str(value)`.
10. **`repr()` keeps single quotes** for plain text, so golden outputs do not change; only pinned double-quote output (`separator=";"`) needs `lit_dq`.
11. **Timeout re-spawn** leaves the stuck thread running and writing; its stats are lost. Real kill is plan 08's process exit.
12. **Cancellation is cooperative**, between nodes: say so in every tooltip/log; never promise an in-node stop.
13. **Re-evaluation runs on the GUI thread**: with huge inputs the UI pauses before the worker starts. Accepted; do not move it to a thread (`eval()` touches widgets).
14. **F-H2 ordering.** Never create `core/sql_guard.py` in this plan; if F7 is missing, wait. Never loosen the guard to make an existing formula pass.
15. **Qt-free modules** (`run_loop.py`, `codegen_safe.py`) must not import `qtpy`; check with the import test.
16. **Console encoding.** Reproduce BUG-002 without `PYTHONUTF8` (cp1252 default); set only `PYTHONIOENCODING=utf-8` to keep log lines printable.
17. **xfail by exact name**: a typo silently un-xfails nothing and the failing test stays visible; `test_baseline_xfail_list_is_exact` catches typos.

---

## 10. What plans 01-08 must delete from their own steps because this plan owns it

| Plan | Step / section | Action |
|---|---|---|
| 01 | 3.9 Scene support (`_save_target`, `workflow_dir`, `saveToFile` override), implementation step 6 item "`performance_scene.py`: add `workflow_dir` + `saveToFile` override", the `performance_scene.py` entry of its file list | **Delete.** Consume `scene.workflow_dir` (F-F). Keep `filePathRel` use and `test_save_as_to_other_folder_uses_target_dir` (now exercises F-F) |
| 01 | quoting of its new user strings (BUG-003 notes) | Use `core/codegen_safe` `!r`/`lit()` (F-H1); no private helper |
| 01 | any `trigger.spec` line for `core/inputs.py`, `core/input_source.py` | **Delete**; F-G's block lists them |
| 02 | 3.7 `ExecutionResult` additions and `NodeExecutor` additions (`before_node`, `after_node`, `_call_hook`, insertion points 1-4), step 5 "Edit `executor.py` exactly as 3.7" | **Delete**; they exist after F-B. Keep only `RunRecorder.before_node/after_node` bodies and `executor.before_node = ...` registration. `started_at`/`finished_at` format is `...%S.%fZ` |
| 02 | Step 6 mixin `request_run_cancel()` body | **Delete the method**; keep `RunSession.request_cancel` (F-D calls it) and `finish(..., cancelled=self._cancelled)` |
| 02 | Step 6 item 4 `workflow_uuid` property + `serialize` key (3.12) | **Delete**; use `scene.workflow_uuid` (F-F) |
| 02 | H1 insertion point | Insert `RunSession.start(...)` between `self._workflow_executor = executor` and the `WorkflowWorker(...)` line of F-E's skeleton |
| 03 | Step 4 (executor preserves exception, `BaseException`) | **Delete**; it is F-A + F-B with identical field names (`exception`, `traceback_text`). Keep the translator consumers |
| 03 | Step 8 worker rewrite (`nodeSkipped`, `continue_on_error`, `upstream`, cancel notifications) | **Delete the worker code**; keep `_run_policy()` body (read `errors/continue_past_failure`), `_on_node_skipped` body, translation in `_on_node_finished`/`_on_node_errored`. Replace every `[RECONCILE WITH 09]` by the names of 1.2: `run_nodes`, callbacks `on_node_finished`/`on_node_skipped`, signal `nodeSkipped`, kwargs `continue_on_error`/`upstream`, fields `exception`/`traceback_text` |
| 03 | 3.15 | Keep as the spec; F-C implements it exactly (F-C rules 1-3) |
| 03 | SQL-guard messages | Catalogue entries `TD-SHAPE-110..115` come from plan 07 (the guard raises them); this plan defines no `TD-SYS-12x` code |
| 04 | Packaging note (add `core/audit` + `collect_submodules` to the spec) | **Delete**; F-G globs `core/audit`; do not edit `trigger.spec` |
| 04 | any BUG-001 / `node_name` / `PanicException` workaround | **Delete**; F-A owns it |
| 05 | Packaging item B (single `trigger_designer.core.profile` line) | **Delete**; F-G lists `profile` |
| 06 | Step 1 "declare `xlsxwriter`, `uv lock`, hidden imports, File Output excel regression test" | **Delete the dependency / spec / regression-test parts** (F-G tests `test_file_output_excel_writes_a_readable_workbook`, `test_data_preview_export_*`). Keep `core/excel/` creation and re-pointing the two call sites |
| 06 | Mixin `before_run` stub ("if F-B has not landed, add exactly this") | **Delete the fallback text**; F-B provides `before_run_hooks` + `_run_before_run_hooks` (calls each content's `before_run()`, then each hook callable; exceptions logged, never raised). Keep `WorkpaperOutputContent.before_run()` |
| 06 | `trigger.spec` hidden imports for `core/workpaper/*`, `core/excel/*` | **Delete**; globbed by F-G |
| 07 | F6 (`trigger.spec` lines for `core/shaping` and `sql_guard`) | **Delete the spec edit**; F-G globs both. Keep the docs row work |
| 07 | F7 | Stays in plan 07 and **must land before F-H2**; keep the API of its 3.8 frozen (`check_select_only`, `make_locked_connection`, `run_select`, `infer_schema`) or tell plan 09 first |
| 08 | S4 executor edits (`code_filter` attribute, `node_name` move, `policy_violation` field, `ExecutionResult` field) | **Delete**; F-A/F-B. Keep `core/headless/code_policy.py` with `class CodePolicyError(Exception): policy_violation = True`; `executor.code_filter = ...` stays in `runner.py` |
| 08 | S6 `getPyFile(nodes, path=None)` change and the conftest stub widening | **Delete**; F-I owns both (same signature). Keep `--emit-script` calling `window.getPyFile(nodes, FILE)` |
| 08 | S2 `TriggerScene.serialize` metadata carry-forward edit and the GUI relative-path load using `scene.workflow_base_dir` | **Delete the serialize edit** (F-F); use `scene.workflow_dir` instead of `workflow_base_dir` |
| 08 | F10 / any `saveToFile` plan | **Delete**; F-F is UTF-8 atomic. `read_workflow` keeps its UTF-8 -> locale -> cp1252 fallback (same order as F-F's loader) |
| 08 | S9 GUI Cancel button (items 1-4: `cancelWorkflow`, `cancel_button`, `icon_stop`, `stop.svg`, `_show_run_controls`, `WorkflowWorker.cancelled`) | **Delete**; F-D owns it (method name `request_run_cancel`, not `cancelWorkflow`). `test_workflow_cancel.py` / `test_cancel_button.py` are created by F-D; plan 08 keeps only its CLI cancel tests |
| 08 | S7 `execute_nodes` loop | Replace the body by a call to `run_nodes(...)` (F-C); no second loop |
| 08 | cycle / Run-stuck-disabled note, `topologicalSort` exception type | **Delete**; F-E; the CLI catches `GraphCycleError` -> exit INVALID |
| 08 | S11 `pyproject.toml` `[project.scripts]` edit and creation of `cli/__init__.py` | **Delete the pyproject edit** (F-G added `trigger-designer-cli`); **overwrite** the stub `cli/__init__.py` with the real `main` |
| 08 | S11 `trigger.spec` second `Analysis` | Keep (plan 08 owns the MERGE restructure) but reuse `analysis.hiddenimports`; add only `trigger_designer.qt.headless`; do not re-list core packages |
| 08 | S12 `ENHANCED_EXECUTOR_GUIDE.md` one-sentence edit | Keep, applied on top of F-I's rewritten guide |
| 08 | BUG-003 defence | Keep the AST policy as defence in depth; F-H1 removes the root cause |
| 08 | "evaluate before running" for the GUI path | Headless keeps `fileLoad` + `doEvalOutputs`; the GUI path is F-E |
