# Node executor guide

`NodeExecutor` (`src/trigger_designer/core/ExecutionCheck/executor.py`) runs the
Python that each node generates. The GUI's Run button and any future headless
runner drive it through the same loop (`core/ExecutionCheck/run_loop.py`).

## Basic use

```python
from trigger_designer.core.ExecutionCheck.executor import NodeExecutor

executor = NodeExecutor()
result = executor.execute_node(node)      # anything with get_code() -> str

if result.success:
    print(result.variables)               # names the node's code defined
else:
    print(result.error)                   # message (+ original traceback text)
```

`execute_node` never raises for a failing node: the failure comes back in the
result. Variables a node defines are added to a shared `execution_context`, so
later nodes see earlier results. `pl`, `os`, `datetime` and `timedelta` are
pre-seeded in that context.

## Limits that exist

| What | How it works |
|---|---|
| Time | `SecurityConfig(max_execution_time=30.0)`, seconds. This is the **only** setting in `SecurityConfig`. |
| Timeout | A node that exceeds it is reported as failed, but its thread cannot be killed. The executor abandons that worker thread and starts a fresh one, so the next node does not wait behind it. The abandoned code may still be running and writing. |
| Failures | `except BaseException`: `SystemExit`, `KeyboardInterrupt` and Polars `PanicException` raised by generated code are node failures, not crashes, and the worker survives. |
| Cancellation | Cooperative and between nodes only: `cancel_execution()` sets a latch (`cancel_requested`); the run loop stops before the next node. A node already inside `exec` is not interrupted. |

There is no memory limit, no import allow-list, no function deny-list and no file
access policy. Generated code runs with **full builtins and no sandbox**: whatever
a node's `get_code()` emits is executed with the user's rights. Treat a workflow
file like a script. (A restricted-code policy is planned for the command-line
runner only; it does not exist in the GUI executor.)

## Result object

`ExecutionResult` (all fields after `error` and `variables` are filled by
`execute_node`):

| Field | Meaning |
|---|---|
| `success`, `error`, `variables` | outcome, message, the node's local variables |
| `exception` | the source exception (unwrapped), or `None` |
| `exception_type` | `"module.QualName"` of the source exception |
| `traceback_text` | formatted traceback of the source exception |
| `code` | the node's code as generated, **before** `code_filter` |
| `started_at`, `finished_at` | UTC ISO-8601 timestamps |
| `policy_violation` | `True` when the failing exception has the class attribute `policy_violation = True` (a `code_filter` refusing code) |

## Hooks

All are plain attributes, `None` by default. A hook that raises is logged and
never fails a node.

| Attribute | Signature | When |
|---|---|---|
| `code_filter` | `(code) -> code` | right after `get_code()`; may raise to refuse the code (a normal node failure) |
| `before_node` | `(node)` | after the filter, before `exec`; not called when `get_code()` or the filter raised |
| `after_node` | `(node, local_variables, result)` | after a **successful** `exec`; variables it adds or replaces reach `result.variables` and the shared context |
| `verify_plans` | `bool`, default `True` | after `exec`, every `pl.LazyFrame` the node defined has its schema resolved (`collect_schema()`), so a bad column or join key fails the node that caused it, without reading data |

## The run loop

```python
from trigger_designer.core.ExecutionCheck.run_loop import run_nodes

outcome = run_nodes(
    nodes, executor,
    continue_on_error=False,       # True: keep going, skip the nodes below a failure
    upstream={node: [parents]},    # needed for skipping
    cancel=threading.Event(),      # checked between nodes
    on_node_started=..., on_node_finished=..., on_node_errored=..., on_node_skipped=...,
)
```

`outcome` is a `LoopOutcome(success, cancelled, executed, failed, skipped)`. The
loop imports no Qt.
