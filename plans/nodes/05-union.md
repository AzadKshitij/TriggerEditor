# Union - modernization plan

Status: not started.
Implementation order: 16 of 18 (Tier 4, dynamic inputs).
Read first: `plans/nodes/README.md`.

## 1. Current implementation

- File: `src/trigger_designer/qt/widgets/nodes/Join/union.py`.
- Content: `UnionContent` (line 85).
- Node: `TriggerNode_Union` (line 847), inheritance
  `MultiInputNode, TriggerNode`. It has one reusable input socket and reads
  **ordered edges** to build a variable-length input list.
- Outputs: one.
- Settings today:
  - `mode` (`by_name`, `by_position`, `manual`)
  - `column_map`: `[{"output": str, "sources": [col-or-None per input]}]`
- Old execution: `execute_union` dispatches to `_concat_by_name`,
  `_concat_by_position` or `_concat_manual`; `coercion_warnings` records
  type conflicts; `_cast_conflicts` casts conflicting by-name columns to
  String.
- Old UI: mode section, ordered input list, manual mapping grid.
- Old codegen: `_position_code`/`_manual_code` plus a by-name branch.
- Existing tests: `tests/unit/test_union_node.py`; all-node e2e.
- Saved workflow: all-node workflow.

## 2. Target

- Core: `src/trigger_designer/core/shaping/union.py`.
- Content: `UnionContent(ShapingContent)` with a custom dynamic layout and a
  custom `compute`/`get_code`.
- Node: **keep** `TriggerNode_Union(MultiInputNode, TriggerNode)`; do not
  force `ShapingNode` because the node has a variable number of inputs and
  uses one reusable socket.
- Settings: `mode`, `column_map`.
- Output kind: `("union",)`.
- `INPUTS` is dynamic; set `INPUTS = 1` only to satisfy the base
  initialization, then replace `frames`/`input_vars` from ordered edges.
- `HISTORY = "Union"`; `SUMMARY = "stack inputs"`.

### Settings schema

```python
DEFAULTS = {
    "mode": "by_name",
    "column_map": [],
}
```

## 3. Behavior contract

### by_name

- Union columns in first-seen order across input schemas.
- Cast a column to String when the same name has conflicting dtypes across
  inputs; record a warning.
- `pl.concat(..., how="diagonal_relaxed")` so missing columns become nulls.
- Preserve row order: frames in input order, rows in each frame's order.

### by_position

- Width = max column count across inputs.
- Output headers come from the first frame; extra positions are
  `Extra_1`, `Extra_2`, ...
- If a position has conflicting dtypes, cast that position to String and
  warn.
- Missing columns in narrower frames become nulls.
- Preserve input order.

### manual

- `column_map` rows map each output to one source column per input:
  `{"output": "Name", "sources": ["a", "b", None]}`.
- Empty column_map -> generate the default map (same as by-name first-seen
  columns).
- Sanitize rows: output non-empty, sources length == input count, invalid
  source -> null.
- Conflicting output dtypes -> cast to String and warn.
- Preserve output row order.

### general

- One input -> return that input unchanged (old behavior) even if mapping is
  configured.
- No inputs -> error `TD-SHAPE-005` / node tooltip.
- `mode` must be one of the three; unknown -> `TD-SHAPE-004`.
- Return a LazyFrame.
- `coercion_warnings` are UI state/chips, not settings.
- Output variable: `var_union_<id>`.

## 4. Core extraction

Create `core/shaping/union.py` with a helper that also returns warnings:

```python
DEFAULTS = {"mode": "by_name", "column_map": []}
MODES = ("by_name", "by_position", "manual")


def union_frame(frames: list, settings: dict) -> tuple[pl.LazyFrame, list[str]]:
    ...


def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    frame, _warnings = union_frame(frames, settings)
    return [frame]
```

Port `_schemas`, `_cast_conflicts`, `_default_column_map`,
`_sanitize_column_map`, `_concat_by_name`, `_concat_by_position` and
`_concat_manual` from the content, replacing `self.*` with arguments and
returning `(frame, warnings)`.

- `_cast_conflicts` checks dtype conflicts per shared name and casts to
  String; preserve the warning text exactly.
- Do not collect.
- `run_node` is the codegen entry point; `union_frame` is the live entry
  point that also supplies warning chips.

## 5. UI

Keep the custom Union dock:

1. `ConfigSection("Mode")` with a `NoWheelComboBox`/`SegmentedControl`:
   By name / By position / Manual.
2. `ConfigSection("Inputs")` showing the ordered input labels with
   up/down `IconButton`s when the base supports reordering. The order is the
   edge order from `getOrderedEdges`; display it read-only if reordering is
   not supported.
3. Manual mapping section (mode == manual):
   - one row per `column_map` row with an output-name `QLineEdit` and one
     source combo per input (blank allowed);
   - Add/remove row icon buttons;
   - rebuild when the input count changes, not on every keystroke.
4. `EmptyStateLabel("Connect at least one input")` when no frames.

- All edits write `settings["column_map"]`/`settings["mode"]` through
  `set_setting`; no `self.column_map` model.
- Table/row widget `_undo_composite = True`; add/remove are list changes;
  output-name typing is a merged property change.
- 30 px controls, 40 px toolbar, shared icon buttons, no inline style.

## 6. Content and node

- `UnionContent(ShapingContent)`:
  - `SETTINGS=core.DEFAULTS`, `MODULE`, `OUTPUT_KINDS=("union",)`,
    `INPUTS=1` (placeholder), `HISTORY`, `SUMMARY`.
  - `__init__`: set `frames=[]`, `input_vars=[]`, `coercion_warnings=[]`,
    `order_description=""`.
  - override `ready()` -> `bool(self.frames)`.
  - override `compute()`:
    ```python
    frame, warnings = core.union_frame(self.frames, self.settings)
    self.coercion_warnings = warnings
    self.outputs = [frame.lazy()]
    return self.outputs
    ```
  - override `get_code()` because input variables are dynamic:
    define the output, serialize settings, and call the core runner with the
    ordered `input_vars`.
  - keep mapping/input-order UI methods as projections over settings.
- `TriggerNode_Union(MultiInputNode, TriggerNode)`:
  - keep `evalImplementation` ordered-edge collection;
  - set `content.frames`/`content.input_vars`/`order_description`, sanitize
    the map when the input count changes, call `content.compute()`, set
    `param`, and set the warning tooltip from `content.coercion_warnings`;
  - `get_code` delegates to content.
- Remove `execute_union`, `_concat_*`, `_position_code`, `_manual_code`,
  `_sanitize_column_map` mutation methods and old serialization (keep
  loader).
- Keep title/icon/enum/registry.

## 7. Legacy loader

Old top-level keys: `mode`, `column_map`.

```python
def _legacy_settings(self, data):
    mode = str(data.get("mode") or "by_name")
    if mode not in core.MODES:
        mode = "by_name"
    rows = []
    for row in data.get("column_map") or []:
        output = str(row.get("output") or "")
        if not output:
            continue
        rows.append({
            "output": output,
            "sources": list(row.get("sources") or []),
        })
    return {"mode": mode, "column_map": rows}
```

## 8. Tests

`tests/unit/test_union_core.py`:

- one input -> identity;
- by-name with disjoint and overlapping columns; first-seen order;
- by-name dtype conflict -> String + warning;
- by-position with different widths; extra headers; position conflict;
- manual default map; explicit map; missing source -> null; output order;
- unknown mode -> `TD-SHAPE-004`;
- no frames -> `TD-SHAPE-005` or documented error;
- lazy inputs -> lazy output.

`tests/ui/test_union_dock.py`:

- mode switch rebuilds sections;
- input count change rebuilds mapping;
- mapping add/remove/edit and undo;
- generated code equals live for all three modes;
- warnings appear in the dock context;
- legacy `mode`/`column_map` loads.

Keep `tests/unit/test_union_node.py` and all-node e2e green.

## 9. Steps

1. Add core + tests.
2. Port mapping helpers; remove from content.
3. Rebase content on `ShapingContent` with dynamic `compute`/`get_code`.
4. Update node `evalImplementation`; keep `MultiInputNode`.
5. Remove old execution/codegen and widget state.
6. Run focused tests + all-node e2e.
7. Commit as `refactor: move Union onto the shaping execution system`.

## 10. Acceptance

- [ ] All three modes produce the old frames.
- [ ] Dynamic input count/order works.
- [ ] Dtype conflicts produce String + warnings.
- [ ] Old saved mapping loads.
- [ ] Live == generated output.

## 11. Do not

- Do not convert Union to a fixed two-input `ShapingNode`.
- Do not use `getSocketValue`; use ordered edges.
- Do not lose the `Extra_n` headers in by-position mode.
