# 08 - Redesign the BaseNode, not just split it

**Status:** proposal, awaiting approval. No implementation yet.

## Why the current file is hard

`node_base.py` is 1,138 lines and owns four independent concerns:

| Lines | Concern | Current symbols |
|---|---|---|
| 65-132 | Frame and rename helpers | `frame_schema`, `frame_shape`, `upstream_rename_map` |
| 135-411 | Canvas painting and theme state | `TriggerGraphicsNode` |
| 414-695 | Content base and Config Dock undo binding | `TriggerContent`, `TriggerChangeHandler` |
| 698-1138 | Node evaluation, errors, sockets, persistence | `TriggerNode` |

The problem is not only file size. The same patterns are repeated:

- `evalImplementation` has three separate failure branches that all mark
  invalid, dirty descendants, set an error and refresh the dock.
- `onEdgeConnectionChanged` and `onInputChanged` duplicate the same
  invalidate-and-evaluate sequence.
- `TriggerContent` and `ConfigContent` both provide content plumbing.
- `TriggerChangeHandler` is a 260-line mixin that owns registration, layout
  traversal, debouncing, tracked values and history fallback.
- `TriggerNode` owns evaluation, error state, UI refresh, socket traversal and
  persistence.
- The file has two QtWidgets import blocks, a duplicate `QWidget`, unused
  eval-progress imports and a dead `evalOperation`.

A split alone would leave those duplicated patterns intact. This plan changes
the ownership model as well.

## Design principles

1. **`TriggerNode` is identity, sockets and persistence.** It should not own
   the evaluation algorithm, error storage or dock binding.
2. **One failure path.** Missing input, failed upstream, failed `processInputs`
   and exceptions all end in the same state transition.
3. **One invalidation path.** Edge changes and input changes share one method.
4. **Composition for stateful services.** Evaluation, errors and dock binding
   are objects with explicit state, not increasingly large mixins.
5. **One content contract.** New and old content classes share the same signal,
   node accessors, history and binding behavior.
6. **No behavior change.** Evaluation order, error knock-on, undo, painting and
   saved files stay the same.
7. **No type-annotation churn.** Keep the existing `Optional[...]` and
   `List[...]` style. No repo-wide formatter.

## Target architecture

```text
qt/node_base.py
  TriggerNode
    identity / sockets / serialization / get_code
    delegates eval -> NodeEvaluator
    delegates errors -> NodeErrorState
    compatibility re-exports

qt/node_runtime.py
  NodeEvaluator
    cache check
    progress reporting
    evalImplementation wrapper
    collect inputs
    processInputs
    success/failure transition
  NodeErrorState
    per-source error map
    tooltip / badge / Problems dock projection
    knock-on clearing

qt/node_content.py
  ConfigContent
    evaluate signal
    node accessors
    icon setup
    history
    DockBinding
  TriggerChangeHandler
    thin compatibility adapter over DockBinding
  TriggerContent
    legacy adapter over ConfigContent
  DockBinding
    registration
    layout traversal
    debounce / tracked values
    clear

qt/node_graphics.py
  TriggerGraphicsNode
    geometry
    painting
    theme pens
    badges
    low-detail fallback

core/frames.py
  frame_schema
  frame_shape

qt/helpers/rename_map.py
  upstream_rename_map
```

`node_base.py` re-exports every moved public name so existing imports keep
working. This pass does not require a repo-wide import sweep.

## The simplified evaluation pattern

`TriggerNode` becomes a small public surface:

```python
class TriggerNode(Node):
    def __init__(...):
        ...
        self.errors = NodeErrorState(self)
        self.evaluator = NodeEvaluator(self)

    def eval(self, index=None):
        return self.evaluator.evaluate()

    def evalImplementation(self):
        return self.evaluator.run_base_implementation()

    @property
    def current_error(self):
        return self.errors.current

    def set_error(self, error, source="live"):
        self.errors.set(error, source)

    def clear_error(self, source=None, *, _seen=None):
        self.errors.clear(source, _seen=_seen)
```

`NodeEvaluator` owns one pipeline:

```text
evaluate()
  if bulk loading: return cached value
  if clean: return cached value
  report progress start
  try:
      value = node.evalImplementation()
  except ValueError:
      node.fail(translate_exception(...))
  except Exception:
      node.fail(translate_exception(...))
  finally:
      report progress finish
      notify scene

run_base_implementation()
  values = collect_inputs()
  if values is None: return fail()
  result = node.processInputs(values)
  if result is None: return fail()
  return succeed(result)
```

The three current failure branches collapse into one `fail()` transition:

```text
markInvalid()
markDescendantsDirty()
set a fallback error only when no specific error exists
refresh the selected dock
```

`onEdgeConnectionChanged` and `onInputChanged` both call:

```text
invalidate_and_evaluate()
  clear run error
  markDirty()
  markDescendantsDirty()
  eval()
```

Subclasses that override `evalImplementation` still work. `evaluate()` calls
the node's override; only the base `evalImplementation` delegates to
`run_base_implementation()`. `unknown` and `union` are the current overrides and
are explicitly covered by tests.

## The simplified error pattern

`NodeErrorState` owns:

- `current`
- `set`
- `clear`
- `apply` (tooltip and badge)
- `problems_store`
- `log_new`

`TriggerNode.current_error`, `set_error` and `clear_error` remain as delegating
properties/methods, so every existing caller keeps working.

This removes the error map, recursive clear, Problems-dock bridge and badge
projection from the node class. Error behavior stays identical.

## The simplified content and undo pattern

`DockBinding` is a normal object, not a mixin:

```python
class DockBinding:
    def __init__(self, content, node): ...
    def register(self, widget, text=None, immediate=None,
                 debounce_ms=None, merge_key=None) -> bool: ...
    def register_all(self, layout) -> int: ...
    def iter_widgets(self, layout): ...
    def clear(self) -> None: ...
    def refresh_context(self) -> None: ...
```

`TriggerChangeHandler` keeps its public methods as thin delegations:

```python
class TriggerChangeHandler:
    @property
    def binding(self):
        return self._binding

    def registerInputWidget(self, widget, **kwargs):
        return self.binding.register(widget, **kwargs)

    def recursively_find_widgets(self, layout):
        return self.binding.register_all(layout)
```

The lazy-initialization regression stays: `binding` is created on first access,
so a content class that skips `super().__init__()` still works.

`ConfigContent` becomes the one canonical content base:

- `evaluate` signal
- node getter/setter
- `initUI`
- `history`
- `DockBinding`
- dock context refresh

`ShapingContent` and `SelectContent` already build on this contract.
`TriggerContent` becomes a thin legacy adapter rather than a second full base.
Old nodes that declare `(QDMNodeIconContentWidget, TriggerChangeHandler)` keep
working through the compatibility methods.

## The simplified graphics pattern

Move `TriggerGraphicsNode` out of `node_base.py` without changing its paint
contract. Optional internal cleanup, only after the main migration:

- extract status badge painting
- extract error badge painting
- extract low-detail blit
- keep geometry caches, `boundingRect` margins and theme tokens unchanged

Painting is the highest visual-regression risk, so this stays behavior-first.

## What actually gets smaller

| Area | Before | After |
|---|---|---|
| `node_base.py` | 1,138 lines | about 250-300 |
| Evaluation | 3 failure branches + duplicate invalidation | 1 evaluator, 1 fail path, 1 invalidate path |
| Errors | ~90 lines inside `TriggerNode` | `NodeErrorState` |
| Content | two overlapping bases | one canonical `ConfigContent` + adapters |
| Undo binding | 260-line mixin | `DockBinding` + thin adapter |
| Helpers | mixed into `node_base` | `core/frames.py`, `rename_map.py` |
| Dead code | `evalOperation`, duplicate imports, unused imports | removed |

Total project lines may stay close to today. The improvement is that
`node_base.py` becomes small and the repeated state transitions become single
methods with one owner.

## Phases

### Phase 0 - Baseline

- Record line counts, import surface and test baseline.
- Confirm a clean working tree.
- Add characterization tests only where the current suite has gaps.

**Gate:** full unit/e2e and targeted UI green.

### Phase 1 - Pure helpers

- Move `frame_schema`/`frame_shape` to `core/frames.py`.
- Move `upstream_rename_map` to `qt/helpers/rename_map.py`.
- Re-export from `node_base.py`.

**Gate:** frame, Select rename and Join/Graph rename tests.

### Phase 2 - DockBinding

- Extract `DockBinding` from `TriggerChangeHandler`.
- Keep `TriggerChangeHandler` public methods as delegations.
- Preserve lazy binding, composites, scroll-area traversal, debounce and
  tracked-value behavior.

**Gate:** `test_node_base`, `test_undo`, dock/undo UI.

### Phase 3 - ConfigContent

- Make `ConfigContent` the canonical content base.
- Move it into `qt/node_content.py`.
- Make `TriggerContent` a compatibility adapter.
- Update `ShapingContent` and `SelectContent` imports.

**Gate:** shaping dock tests, Select dock test, old-node smoke tests.

### Phase 4 - NodeErrorState

- Extract error map, tooltip, badge, Problems dock and recursive clear.
- Keep `TriggerNode.current_error`, `set_error`, `clear_error` delegating.
- No change to error fingerprints, knock-on behavior or logging.

**Gate:** error tests, workflow undo, all-node workflow.

### Phase 5 - NodeEvaluator

- Extract cache, progress, exception translation, input collection and
  success/failure transitions.
- Keep `evalImplementation` overrides working.
- Collapse the three failure branches and duplicate invalidation methods.
- Remove `evalOperation` and the commented-out calculator block.

**Gate:** batch evaluation, graph, node titles, execution and all workflow
tests.

### Phase 6 - Graphics and facade cleanup

- Move `TriggerGraphicsNode` to `qt/node_graphics.py`.
- Collapse duplicate imports and remove unused eval-progress imports.
- Slim `TriggerNode` to identity, sockets, persistence and codegen.
- Keep compatibility re-exports in `node_base.py`.
- Optional paint-helper extraction only after tests are green.

**Gate:** geometry, render settings, canvas grid, context menu, full suite.

### Phase 7 - Optional import migration

- Move internal imports to the focused modules.
- Decide whether compatibility re-exports stay for one release or are removed.
- Audit `is_input_widget` before removing it.

This phase is separate. The first pass keeps old imports working.

## Test gates

Targeted:

- `tests/unit/test_node_base.py`
- `tests/unit/test_undo.py`
- `tests/unit/test_batch_evaluation.py`
- `tests/unit/test_graph_node.py`
- `tests/unit/test_node_titles.py`
- `tests/unit/test_nodeeditor_api.py`
- `tests/unit/test_shaping_support.py`
- `tests/unit/test_shaping_nodes.py`
- `tests/ui/test_node_geometry.py`
- `tests/ui/test_render_settings.py`
- `tests/ui/test_canvas_grid_render.py`
- `tests/ui/test_context_menu_dev_actions.py`
- `tests/ui/test_select_rename_propagation.py`
- `tests/ui/test_join_rename_propagation.py`
- `tests/e2e/test_undo_integration.py`
- `tests/e2e/test_workflow_goldens.py`

Full:

- `tests/unit`
- `tests/e2e`
- targeted UI files, because the full UI suite has a pre-existing Formula
  editor teardown abort.

Import smoke:

```python
from trigger_designer.qt.node_base import (
    TriggerNode, TriggerGraphicsNode, TriggerContent, TriggerChangeHandler,
    frame_schema, frame_shape, upstream_rename_map,
)
```

## Risks

| Risk | Mitigation |
|---|---|
| Evaluation semantics change | Keep `evalImplementation` override contract; test unknown/union and all workflows |
| Error knock-on changes | Move `NodeErrorState` as a block; preserve fingerprints and tests |
| Undo registration changes | `DockBinding` is a mechanical extraction; keep lazy init and composite rules |
| Content MRO breaks | Keep undo mixin before Qt base; test old content classes and ConfigContent |
| Painting regressions | Move graphics class without changing paint geometry; run render tests |
| Public imports break | Re-export every moved name from `node_base.py` |
| Circular imports | New modules use `TYPE_CHECKING` for TriggerNode; `node_base` is the only assembler |

## Acceptance criteria

- `node_base.py` is at most about 300 lines.
- One evaluation pipeline and one failure transition.
- One invalidation method for edge and input changes.
- One error state object.
- One canonical content base plus compatibility adapters.
- One dock binding object.
- No duplicate imports, dead `evalOperation`, or commented-out eval block.
- Every old `node_base` import still works.
- No saved-file format change.
- All targeted and full tests pass.
- No mass type-annotation or formatting changes.

## Decisions needed

1. Approve the composition-based redesign (`NodeEvaluator`, `NodeErrorState`,
   `DockBinding`, one `ConfigContent`) rather than file splitting only?
2. Keep the `node_base` compatibility re-exports for the first pass? Recommended.
3. Make `TriggerContent` a thin legacy adapter over `ConfigContent`? Recommended.
4. Remove `evalOperation` and the commented-out eval block? Recommended.
5. Commit per phase, or one final commit after all gates?
