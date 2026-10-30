# The Run pipeline

What happens between the Run button and a sealed run record. Files:
`qt/design_window.py`, `qt/helpers/workflow_execution_mixin.py`,
`qt/helpers/workflow_worker.py`, `core/ExecutionCheck/run_loop.py`,
`core/ExecutionCheck/executor.py`, `qt/helpers/audit_bridge.py`.

## Sequence

```
Run button -> TriggerSubWindow.run_workflow() -> WorkflowExecutionMixin.executeWorkflow()

 GUI thread
  1. guard: a worker is already running            -> return False
  2. commit_pending_config_edits(evaluate=False); evaluator.flush_now()
  3. topological_order(scene)                       (GraphCycleError -> select the
                                                     loop's edges, log, return False)
  4. disable Run; clear execution_results, _last_run_codes, "run" problems;
     markInvalid(False), clear_error("run"), resetPen on every node
  5. _reevaluate_for_run(sorted_nodes)              every node markDirty + doEvalOutputs
  6. _run_before_run_hooks(sorted_nodes)            content.before_run() then before_run_hooks
  7. _show_run_controls(True)                       Run hidden, Cancel shown
  8. executor = NodeExecutor()                      fresh per Run (fresh worker thread)
  9. _start_run_session(...)                        audit recorder (may be None)
 10. WorkflowWorker(sorted_nodes, executor, continue_on_error, upstream)
     signals -> _on_node_started / _on_node_finished / _on_node_errored /
                _on_node_skipped / _on_workflow_finished
 11. evaluator.suspend(); worker.start()

 Worker thread (QThread)  ->  run_nodes(...)   (core/ExecutionCheck/run_loop.py)
     per node:  executor.execute_node(node)
                  code = node.get_code(); result.code = code
                  code = code_filter(code)                  (optional seam)
                  before_node(node)                          (audit: fingerprint inputs)
                  exec(code, {**execution_context, "__name__": "__main__"}, locals)
                    on the pooled "NodeExecutorWorker" thread, 30 s timeout
                  verify_plans: collect_schema() of every LazyFrame local
                  content.after_execution(variables)         (warnings only on failure)
                  after_node(node, locals, result)           (audit: count rows, hash outputs)
                  execution_context.update(locals)           (shared namespace)

 GUI thread (queued signals)
     _on_node_finished: session.node_finished, keep result.code,
        success -> clear_error("run"), execution_results[node] = pruned vars,
                   setPenExecuted, content.on_run_result(variables)
        failure -> translate_exception(..., phase="run") -> node.set_error(.., "run"),
                   start background enrichment, markInvalid, setPenError
     _on_node_errored: same translation for an exception that escaped execute_node
     _on_workflow_finished(success):
        cancel flag from worker.cancelled, hold the QThread reference until finished,
        evaluator.resume(), getPyFile(sorted_nodes)  (never raises),
        _seal_run_record(success), cleanup + summary in the Logging dock,
        raise the Problems dock when roots_only errors > 0,
        executionResultsChanged.emit()
```

## `run_nodes` semantics (shared by GUI and headless)

`run_nodes(nodes, executor, *, continue_on_error=False, upstream=None,
cancel=None, on_node_started, on_node_finished, on_node_errored,
on_node_skipped) -> LoopOutcome(success, cancelled, executed, failed, skipped)`

* Qt-free (threading, dataclasses, typing). `WorkflowWorker.run()` is only a
  wrapper that turns the callbacks into signals; calling `worker.run()` instead
  of `start()` executes synchronously on the caller's thread (used by tests).
* Stop policy: `continue_on_error=False` stops at the first failed node and
  sends no skip notifications for the rest. `True` carries on; a node whose
  direct upstream failed or was skipped is skipped itself (transitively), with
  `on_node_skipped(node, blocker)`.
* Cancel: `cancel` (a `threading.Event`) is checked **between nodes only**.
  Every remaining node gets `on_node_skipped(node, None)`. A running node is
  never interrupted.
* `on_node_finished(node, result)` fires for success and failure alike
  (read `result.success`); `on_node_errored` only when `execute_node` itself
  raised an `Exception`. Callback exceptions propagate. `KeyboardInterrupt`
  and `SystemExit` are not caught.
* `run_nodes` calls `executor.reset_cancel()` at the start.
* `success` is `not failed and not skipped and not cancelled`.

## Policies

* **Policy** is one knob: `_run_policy()` returns `{"continue_on_error": bool}`
  from the preference `errors/continue_past_failure` (default `True`). With it
  on the GUI skips only the dependents of a failed node; the worker re-emits
  `on_node_skipped` as `nodeSkipped`, and `_on_node_skipped(node, blocker)`
  queues the node. Once the run has finished and error enrichment has settled
  (`_mark_skipped_nodes`) each queued node gets a `TD-RUN-008` warning in the
  "run" slot. It is deferred because applying an enriched error calls
  `clear_error("run")` on the failed node, which cascades to the knock-on
  errors of its children. A cancelled run (`blocker is None`) marks nothing.
  The headless runner passes its own flag.
* **Timeout**: `SecurityConfig.max_execution_time = 30.0` seconds per node. On
  timeout the stuck worker thread cannot be killed; a sentinel is queued for it
  and a **fresh worker is started**, so later nodes (continue-on-error) do not
  wait on a queue nobody reads. A run can therefore leak at most one thread per
  timed-out node.
* **Code policy seam**: `NodeExecutor.code_filter(code) -> code`. A filter that
  refuses code raises an exception whose *class attribute*
  `policy_violation = True` is copied to `ExecutionResult.policy_violation`
  (the executor imports no policy module). The raw code is kept on the result
  even when the filter fails. Nothing in the GUI installs a filter.
* **Plan verification**: `NodeExecutor.verify_plans` (default `True`). After
  `exec`, `collect_schema()` is called on every `LazyFrame` local. This checks
  the plan (missing column, bad join key) without reading data and makes the
  *building* node fail. Set `False` only to reproduce the old "fails at the
  sink" behaviour in a test.
* **GC**: a full `gc.collect()` runs every `gc_collect_interval = 20` nodes.

## Cancellation

One entry point: `WorkflowExecutionMixin.request_run_cancel() -> bool` (True
when a run was in flight). It:

1. `worker.request_cancel()` (sets the worker's event; `run_nodes` sees it
   before the next node);
2. `executor.cancel_execution()` (latch; returns whether a node is running);
3. `session.request_cancel()` (stops file hashing at the next chunk and marks the
   run `cancelled`);
4. calls every callback added with `add_cancel_listener`;
5. disables the Cancel button and logs
   "Cancel requested - stopping after the current step finishes".

Cancellation is **cooperative**: the node being executed finishes (bounded by
its 30 s timeout). The worker is authoritative afterwards:
`_on_workflow_finished` reads `worker.cancelled`, so a cancel that arrives
after the last node finished is not reported as a cancelled run.

Limits, pinned by `tests/unit/test_cancel_and_timeout_behaviour.py`:

* The cancel flag is read only between nodes (`run_nodes`). Nothing inside a
  node's `exec` polls it, so a long collect or write runs to completion (or to
  the 30 s limit) after Cancel. Cooperative cancellation inside a collect is not
  feasible with Polars/DuckDB; it is deliberately not attempted.
* A node that hits `max_execution_time` is *abandoned*, not stopped. Its worker
  thread keeps executing the code until the code returns by itself; the
  executor queues a sentinel for it (it exits afterwards) and starts a fresh
  worker so later nodes can run. The stuck code keeps using CPU and memory, and
  may still write files, until it ends. At most one thread leaks per timed-out
  node, and a fresh `NodeExecutor` is made for every Run.

Closing a window with a run in flight calls `shutdown_workflow_worker`, which
cancels, detaches the UI signals and waits; a thread that will not stop is
parked in `_ORPHANED_WORKERS` (Qt aborts the process if a running `QThread` is
destroyed) and `wait_for_orphaned_workflow_workers()` waits again at exit.

## Re-evaluation before Run

Generated code reads state that only a live pass sets
(`content.incoming_variable`, `incom_data`, `data`). `_reevaluate_for_run`
marks every node dirty, calls `doEvalOutputs()` (the coordinator walks the graph
once in dependency order), cancels any deferred "run when the dock is left"
request, and logs `Warning: N step(s) have problems and may fail or produce
empty output: ...` for nodes that stay invalid. Those nodes are not removed from
the run; an unfinished node fails with its own message.

## Results kept per node

`_prune_node_results` keeps only a node's *declared outputs* from the executed
namespace: names from `node.param`, `node.value`, then content attributes named
`variable_name`, `*_variable_name`, `*_var` (`_declared_output_variable_names`).
**A node whose output variable is not exposed through one of those names is
invisible to the Data Preview after Run.** If nothing is declared it falls back
to previewable frames, then to the whole namespace. `getSocketData(node,
socket_index)` serves the preview.

## Run script (`getPyFile`)

`TriggerSubWindow.getPyFile(sorted_nodes, path=None) -> str` writes UTF-8 to
`<app data>/last_run/check_output.py` (`app_data_dir()`;
`TRIGGER_DESIGNER_DATA_DIR` overrides it). It never writes to the working
directory. Node code comes from `_last_run_codes` (what actually ran, so the
script matches the run); a node that did not run is asked once; a node that
cannot produce code becomes a `# <title>: no code (...)` comment. A header from
`check_output_header(_source_root())` puts this checkout's `src` on `sys.path`;
frozen builds omit the source path. The script is not standalone (it imports
`trigger_designer.core.*`). The `check_output.py` tracked at the repo root is
an old artefact; do not commit it again.

## Error handling in a Run

`translate_exception(exc, node=, phase="run", ctx=build_context(node, window,
"run"), redact=<errors/redact_values>, traceback_text=...)` gives a `NodeError`
(`error-system.md`). It is stored with `node.set_error(error, "run")`
(canvas badge, tooltip, Problems dock). `_start_error_enrichment` then
translates upstream: a background job (`error_enricher.start_enrichment`) finds
the node whose plan or data really caused the failure and may replace the root
error and give the failing node a knock-on error. `_apply_enrichment` discards a
late result if the node was edited and re-evaluated meanwhile (its run error no
longer has the same `fingerprint`). `_pending_enrichments` counts jobs in flight
so the record can wait for them (below).

## Seams for the audit recorder

The recorder (`core/audit/recorder.py`) never imports the executor or Qt; the
Run pipeline offers these points and nothing else (details in
`audit-trail-internals.md`):

| Seam | Where | Who uses it |
|---|---|---|
| `executor.before_node(node)` / `executor.after_node(node, local_vars, result)` | `NodeExecutor._call_hook` (worker thread; exceptions are logged, never fail the run) | `RunRecorder.before_node/after_node`: fingerprint inputs, count rows, hash outputs. `after_node` may add or replace variables (the `all` row-count mode swaps in a materialised frame); the executor re-syncs `result.variables` and the shared context afterwards. |
| `RunSession.start(window, sorted_nodes, executor)` | `_start_run_session` | Reads the `audit/*` preferences, builds `NodeSpec`s on the GUI thread, calls `recorder.begin`, installs the hooks and `set_run_record_provider(session.snapshot_current)`. Returns `None` when `audit/record_runs` is off. A failure here clears the hooks and the run proceeds unrecorded. |
| `session.node_finished(node, result)` / `node_errored(node, exc)` | `_on_node_finished` / `_on_node_errored` | Builds the per-node record. |
| `session.request_cancel()` | `request_run_cancel` | Cancels hashing. |
| `_seal_run_record(success)` -> `session.finish_when_settled(success and not cancelled, done)` | `_on_workflow_finished`, after `getPyFile` | Seals now on success; for a failed run waits (max `SETTLE_GUARD_MS = 5000`) until `is_enrichment_settled()` so the stored error is the enriched one. `done(path)` logs "Run log saved: <path>" and emits `runRecorded(path)` (the Run History dock listens). |
| `add_enrichment_settled_listener(cb)` | window | One-shot callbacks run when `_pending_enrichments` reaches 0. |
| `_abort_run_session()` | start failures | Discards a begun record and its `.started` marker. |
| `set_run_record_provider` / `get_run_record_provider` | `core/audit/recorder.py` | Lets another feature (the Workpaper Output node, see `workpaper-internals.md`) read the in-flight record as a dict while the run is going. |
| `before_run_hooks`, `content.before_run()` | `_run_before_run_hooks` | Headless runners append to the list; a node content may define `before_run()`. Failures are logged and ignored. |
| `content.after_execution(variables)` | executor thread, pure Python only | Graph, audit nodes' Summary. |
| `content.on_run_result(variables)` | GUI thread | Audit Result text. A raising slot aborts the process under PySide6, so it is wrapped. |

The recording rule: **nothing the recorder does may change a Run's outcome**
(every entry point is `try/except`, failures are warnings).

## Pitfalls

* Do not collect inside `get_code()` text unless the node's contract needs it;
  Run is lazy by design and only sinks materialise data. A workflow with no
  sink "succeeds" if the plans verify.
* `get_code()` must be pure: the same text is executed, hashed into the record
  (`code_sha256`) and exported.
* Never block the GUI thread inside `_on_*` slots; they run between nodes.
* Slots connected to worker signals must not raise (PySide6 aborts).
* Two `QApplication`s in one process abort; tests share the `qapp` fixture.
