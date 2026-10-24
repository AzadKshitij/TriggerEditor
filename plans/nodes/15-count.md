# Count - modernization plan

Status: not started.
Implementation order: 1 of 18 (Tier 0, no settings, lowest risk).
Read first: `plans/nodes/README.md`, `docs/plan/07-shaping-nodes.md`.

## 1. Current implementation

- File: `src/trigger_designer/qt/widgets/nodes/Transform/count_records.py`.
- Content: `CountRecordsContent` (line 26).
- Node: `TriggerNode_CountRecords` (line 148).
- Inputs: one (`[1]`). Outputs: one (`[3]`).
- Old runtime state: `incom_data`, `incoming_variable`, `data`,
  `total_records`.
- Old execution: `CountRecordsContent.process_data` collects `pl.len()`,
  stores the count in `total_records`, and builds `pl.DataFrame({"Count": [...]})`.
- Old UI: `create_layout` has no controls. The dock is intentionally empty.
- Old codegen: `get_code` calls `len(df)` / `collect().height` and emits a
  `pl.DataFrame({"Count": [count]})`.
- Existing tests: no dedicated Count test; covered indirectly by
  `tests/e2e/test_workflow_goldens.py` (all-node workflow).

## 2. Target

- Core: `src/trigger_designer/core/shaping/count.py`.
- Content: `CountContent(ShapingContent)`.
- Node: `TriggerNode_Count(ShapingNode)` in the existing module.
- Settings: `{}` (no user settings).
- Output kind: `("count",)`; output text `("Out",)`.
- `INPUTS = 1`; `SUMMARY = "row count"`.

### Settings schema

```python
DEFAULTS = {}
```

`total_records` is **not** a setting. It is a derived display value. Do not
serialize it into the new model.

## 3. Behavior contract

- Return exactly one row: column `Count`, dtype `Int64` (cast the result).
- Count all rows, including rows whose values are null.
- Input may be `DataFrame` or `LazyFrame`.
- Counting a lazy frame may collect it; this node is allowed to collect.
- Unconfigured node with a connected input is valid; no error.
- No upstream columns are required, so an empty schema is still countable.
- Preserve the existing downstream name `var_count_<id>` if practical by
  assigning `self.output_variables = [f"var_count_{self.id}"]` after
  `super().__init__`; otherwise document the name change in the commit.

## 4. Core extraction

Create `core/shaping/count.py`:

```python
"""Count: total rows as a one-row frame (Qt-free)."""

from __future__ import annotations

import polars as pl

from trigger_designer.core.shaping.common import as_lazy

DEFAULTS: dict = {}


def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    frame = as_lazy(frames[0])
    total = frame.select(pl.len()).collect().item()
    return [pl.DataFrame({"Count": [int(total)]}, schema={"Count": pl.Int64}).lazy()]
```

- Do not reuse the old `process_data` method; it is a projection into widgets.
- Do not import `QWidget`, `pl` is enough.
- Keep `settings` accepted even though it is unused, for the shared runner API.

## 5. Content and node

```python
class CountContent(ShapingContent):
    SETTINGS = core.DEFAULTS
    MODULE = "trigger_designer.core.shaping.count"
    OUTPUT_KINDS = ("count",)
    INPUTS = 1
    HISTORY = "Count"
    SUMMARY = "row count"
    FORM = ()
```

- `FORM = ()` means the dock shows no configuration. That is correct.
- Override `create_layout` only if a useful read-only note is wanted. Prefer
  the base empty form; do not add a control that cannot change anything.
- Node class keeps the existing icon/title/enum and uses `ShapingNode`;
  `content_class = CountContent`, `output_text = ("Out",)`.
- Delete `TriggerNode_CountRecords.processInputs` and `get_code`; the base
  handles input, compute and codegen.

## 6. Legacy loader

Not required for Count. The old `total_records` key is derived and must not be
loaded into settings. Existing workflows still load because the node identity
and registry entry are unchanged.

## 7. Tests

Create `tests/unit/test_count_core.py`:

- DataFrame with 3 rows -> one row `Count == 3`.
- LazyFrame with nulls -> counts nulls.
- Empty frame -> `Count == 0`, dtype `Int64`.
- Runner returns one frame and no Qt import.
- Node live output and generated code both produce the same frame (use the
  shared `tests/support/frames.py` helpers where possible).

Add a small UI check to `tests/ui/test_shaping_docks.py` or a new
`tests/ui/test_count_dock.py`:

- `create_layout` builds without error with a connected frame.
- There are no editable controls (or only the intended note).
- `node.eval()` updates the preview after an upstream frame change.

Update the all-node e2e if it asserts the old class name or old
`total_records` attribute.

## 8. Steps

1. Add `core/shaping/count.py`.
2. Add `CountContent` and `TriggerNode_Count`; remove the old content/node
   execution methods from `count_records.py`.
3. Keep the module path, enum, icon, title and registry entry unchanged.
4. Add core/UI tests.
5. Run the focused tests and the e2e all-node workflow.
6. Commit as `refactor: move Count onto the shaping execution system`.

## 9. Acceptance

- [ ] `core/shaping/count.py` is Qt-free and tested.
- [ ] `CountRecordsContent`/`TriggerNode_CountRecords` are replaced by
      `CountContent`/`TriggerNode_Count` (or the old class names are kept only
      as the registered node name; prefer new names).
- [ ] No `incom_data`, `incoming_variable`, `data` or `total_records` in the
      new execution path.
- [ ] Live output == generated-code output.
- [ ] All-node e2e still passes.

## 10. Do not

- Do not add a "Count column" setting. Count is total rows.
- Do not add a second output.
- Do not keep a `total_records` widget attribute as a model.
