# Node evaluation and LazyFrame plan

Date: 2026-11-01
Status: Proposed. No source code has been changed.
Scope: Config Dock apply timing, audit deferral, SQL focus-out, and lazy-first node execution.

Related plan: `Defer Formula and Filter SQL evaluation to focus-out` (OpenChamber plans).

## Steps

- [ ] Add a Config Dock level focus-out hook that applies pending edits when focus leaves the dock.
- [ ] Make the Audit family use `DeferredEvaluation` and respect `commit_pending_dock_edits(evaluate=False)`.
- [ ] Repair Formula, Filter and SQL Query focus-out evaluation, coalescing all SQL editors in one node.
- [ ] Decide whether Data Profile stays live or follows the new deferred rule.
- [ ] Add a shared lazy-contract test that fails when a node's `run_node` collects its input.
- [ ] Rewrite Cleansing to operate on `LazyFrame` expressions and stop collecting the whole table.
- [ ] Make Pivot use `LazyFrame.pivot`; collect only the bounded distinct header values.
- [ ] Remove the undocumented whole-input collect from Multi-Field Formula, or document it as an exception.
- [ ] Decide the Count and Rows policy: lazy scalar expression or documented eager exception.
- [ ] Document the remaining eager nodes as explicit exceptions and correct the architecture/testing docs.

## 1. Target behaviour

The model stays live, but no pipeline evaluation runs until the node is applied.

Apply points:

- focus leaves the Config Dock for another dock, the canvas, or another window;
- the user selects another node;
- Run;
- Save and Save As;
- undo and redo;
- accepted close, where Save commits and Discard does not.

Do not evaluate while a modal dialog is open. Do not evaluate when focus moves between controls inside the same Config Dock or between Formula sections.

## 2. Current findings

### 2.1 No dock-level focus-out

`ConfigDock` has no `focusOutEvent`, no `focusChanged` connection, and no event filter. `updateConfig` commits only when the selected node changes (`src/trigger_designer/qt/docks/node_config.py:82-96,173-205`). Save and Run call `commit_pending_config_edits` (`src/trigger_designer/qt/main_window.py:504-522`, `src/trigger_designer/qt/helpers/workflow_execution_mixin.py:143-148`). Close cancels pending work (`src/trigger_designer/qt/design_window.py:818-819`).

Result: clicking another dock can leave pending edits unapplied.

### 2.2 Audit nodes evaluate on every change

`AuditContentMixin.set_setting` defaults to `evaluate=True` and emits immediately (`src/trigger_designer/qt/widgets/nodes/Audit/_base.py:246-290`, especially `:254` and `:273-274`). Text controls debounce for 300 ms, then evaluate; combo, check and spin controls evaluate immediately (`:344-370`). `AuditContent` does not inherit `DeferredEvaluation` (`:859`).

Affected nodes: Duplicates, Gaps, Benford, Risk Filters, Sample.

Also, `commit_pending_dock_edits` ignores its `evaluate` argument (`:657-668`). Save and Run pass `evaluate=False`, but each pending field still evaluates.

### 2.3 Formula and Filter focus-out is dead

`FormulaContent._on_editor_finished` and `FilterContent._on_expression_finished` call `_schedule_focus_out_evaluation()` (`Preparation/formula.py:503-506`, `Preparation/filter.py:191-194`). The helper returns immediately when `DEFER_EVALUATION` is true (`qt/helpers/shaping_support.py:452-456`). It is true for both nodes, so evaluation waits for the Config Dock to be left, not for focus to leave the SQL editors. This contradicts the existing focus-out plan.

### 2.4 SQL Query has no focus-out evaluation

`editingFinished` commits the text (`Transform/sql_query.py:109`), but evaluation only happens in `commit_pending_dock_edits` (`:145-157`).

### 2.5 Data Profile is deliberately live

`DataProfileContent.DEFER_EVALUATION = False` (`Report/data_profile.py:61-62`) with the comment that there is no pipeline to batch. Remove this opt-out if the rule applies to every node.

### 2.6 Comment is an opt-out but does no work

`CommentContent.DEFER_EVALUATION = False` (`Report/comment.py:28-29`), but `request_evaluation` is a no-op (`:56-57`). No change required unless the flag itself is being standardised.

## 3. LazyFrame findings

The documented policy is lazy between nodes, with collects only where the algorithm requires them (`plans/nodes/README.md:130-141`). `docs/internal/dev/architecture.md:160-162` claims only sinks, Graph, Count and audit summaries materialise, but the code also materialises in other nodes. A side-effecting `LazyFrame` probe confirmed execution at call time.

### 3.1 Documented eager exceptions

- Cleansing: `core/shaping/cleansing.py:30` collects; the plan explicitly keeps the collect (`plans/nodes/06-cleansing.md:86-87`). `DataCleansing` then clones the frame (`core/utils/cleansing_util.py:60`).
- Count: `core/shaping/count.py:21`; allowed by `plans/nodes/15-count.md:46`.
- Filter expression: `core/shaping/filter.py:197-198`; documented in `plans/nodes/07-filter.md:83`.
- Formula: `core/shaping/formula.py:189`; documented in `plans/nodes/09-formula.md:83`.
- Reconcile and Fuzzy Match: `core/shaping/reconcile.py:447-448`, `core/shaping/fuzzy.py:201-202`; both node docs say Run keeps both inputs in memory.
- File Output JSON: `core/shaping/file_output.py:90`; documented in `docs/guide/files-and-formats.md:143`.
- File Input Excel: `core/input_source.py:501`; documented as read in full.
- File Input JSON: `core/input_source.py:471`; Polars 2.0 has no `scan_json`.
- File Input SQLite/DuckDB: `core/input_source.py:515-518`.
- Audit Sample: `core/audit/sampling.py:287-312`; the deterministic draw needs the canonical population.

These are policy conflicts, not code bugs, if strict laziness becomes the rule.

### 3.2 Undocumented eager paths

- Pivot: `core/shaping/reshape.py:83` collects the whole aggregated frame. Polars 2.0 provides `LazyFrame.pivot`, so collect only the distinct header values, bounded by `MAX_PIVOT_COLUMNS`.
- Multi-Field Formula: `core/shaping/multi_formula.py:120` calls `lf.collect()` before `run_select`.
- Rows: `core/shaping/rows.py:74` collects the source height. The reference code in `plans/nodes/14-rows.md:95-120` has no height check; this is an added `TD-SHAPE-130` validation.
- Count could return `frame.select(pl.len().cast(pl.Int64).alias("Count"))` lazily instead of collecting.

### 3.3 Contract drift and test gap

- `docs/internal/dev/architecture.md:160-162` is inaccurate.
- `docs/internal/dev/testing.md:177-178` says nodes are tested for "no eager collect of the input"; no shared test enforces it.
- `ShapingContent.compute` wraps eager outputs with `.lazy()` (`qt/helpers/shaping_support.py:324-326`), hiding internal eagerness.

## 4. Implementation notes

### 4.1 Dock focus-out

Install one focus watcher on `ConfigDock` or connect `QApplication.focusChanged`. On a change:

1. If the old focus is outside the dock, do nothing.
2. If the new focus is still inside the dock, do nothing.
3. If an application modal is active, defer the commit until the modal closes.
4. Otherwise call the current content's `commit_pending_dock_edits(evaluate=True)` once.

Do not add per-editor focus-out handlers for ordinary selectors and checkboxes. The dock is the apply boundary.

### 4.2 Audit deferral

- Make `AuditContent` inherit `DeferredEvaluation`.
- Change `AuditContentMixin.set_setting` to `evaluate=None`, calling `request_evaluation()` like `ShapingContent`.
- `commit_pending_dock_edits(evaluate)`: stop every timer, commit each field with `evaluate=False`, then call `_evaluate_pending()` once when `evaluate` is true.
- Ensure Save and Run with `evaluate=False` leave the pending flag intact and do not emit.
- Keep the input full-plan live behaviour as documented, or add `live_sample` only if that policy changes separately.

### 4.3 SQL focus-out

- Remove the `DEFER_EVALUATION` early return from `_schedule_focus_out_evaluation`; keep the pending check and the modal guard.
- Keep `_sql_editor_has_focus`, so moving between Formula sections is not an apply point.
- Add the same `editingFinished` to `_schedule_focus_out_evaluation` path to SQL Query.
- One evaluation when focus leaves all of that node's SQL editors.

### 4.4 Lazy-first

- Add a test helper that wraps a `LazyFrame` with `map_batches` and records executions. Call each node's `run_node` with a small fixture and assert no execution until the result is collected.
- Rewrite Cleansing with `pl.Expr` operations and return the same `LazyFrame`; collect only a one-row null-count summary when removing columns.
- Use `LazyFrame.pivot` in Pivot and collect only the distinct header list.
- Remove the Multi-Field Formula input collect if DuckDB can take the lazy frame through a managed relation; otherwise document the exception.
- Decide Count and Rows explicitly.

## 5. Tests

1. Focus leaves the dock: one evaluation, and pending edits reach the model.
2. Focus moves between two Formula editors: zero evaluations; leaving both: one.
3. Focus moves to another dock control in the same node: zero evaluations.
4. Audit text edit: no evaluation until apply; one evaluation at apply.
5. Audit `commit_pending_dock_edits(evaluate=False)` emits nothing.
6. Save and Run use the latest model without a live evaluation.
7. Cancel close does not commit; Save on close commits; Discard does not.
8. Lazy contract: Cleansing with all options off does not execute the source.
9. Pivot executes only the distinct-header query at call time; the main pivot stays lazy.
10. Documented exceptions are explicit in the test list.

## 6. Acceptance criteria

- No config edit triggers a pipeline evaluation while the user is still in the node.
- One evaluation occurs when the node is applied by focus loss, selection, Run, Save or undo/redo.
- The model is always current, undo works, and the document is marked modified immediately.
- Nodes do not collect their input unless listed as an explicit, documented exception.
- Architecture and testing docs match the actual eager nodes.
- The full unit suite stays green apart from the known docs-path failures until those are fixed.

## 7. Open decisions

- Does "node loses focus" mean leaving the Config Dock, or only leaving the field being edited?
- Should Data Profile stay live?
- Is strict laziness required for Cleansing, Count, Filter, Formula, Reconcile and Fuzzy, or are those permanent documented exceptions?
- Should the plan live in the repository `plans/bugs/`, the OpenChamber plans panel, or both?
