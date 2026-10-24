# Running Total - modernization plan

Status: implemented.
Implementation order: 2 of 18 (Tier 0, additive columns).
Read first: `plans/nodes/README.md`.

## 1. Current implementation

- File: `src/trigger_designer/qt/widgets/nodes/Transform/running_total.py`.
- Content: `RunningTotalContent` (line 35).
- Node: `TriggerNode_RunningTotal` (line 286).
- Inputs: one. Outputs: one.
- Settings today: `sum_columns`, `group_by_columns`, plus derived
  `numeric_columns` (not saved configuration).
- Old execution: `process_data`:
  - filters `sum_columns` to live numeric columns;
  - filters `group_by_columns` to live columns;
  - if no sum columns -> input unchanged;
  - adds `RunTot_<column>` with `pl.col(column).cum_sum().over(group_by_columns)`;
  - applies `normalize_to_supported_dtypes`.
- Old UI: two searchable checklists, "Sum" restricted to numeric columns and
  "Group by" for all columns.
- Old codegen: `get_code` emits the same cumulative expressions.
- Existing tests: `tests/e2e/test_workflow_goldens.py` has a property test
  for `RunTot_RelevancyNum`; no dedicated core test.
- Saved workflow: `savedfiles/9. Running Total.tds`.

## 2. Target

- Core: `src/trigger_designer/core/shaping/running_total.py`.
- Content: `RunningTotalContent(ShapingContent)`.
- Node: `TriggerNode_RunningTotal(ShapingNode)`.
- Settings: `sum_columns`, `group_by_columns`.
- Output kind: `("running_total",)`.
- `INPUTS = 1`; `HISTORY = "Running Total"`;
  `SUMMARY = "cumulative sums"`.

### Settings schema

```python
DEFAULTS = {
    "sum_columns": [],
    "group_by_columns": [],
}
```

## 3. Behavior contract

- Sum only numeric columns; ignore a configured sum column that is no longer
  numeric or no longer present.
- Group columns are filtered to the live schema; a missing group column is
  ignored.
- No valid sum columns -> return the input unchanged (old behavior).
- Each output column is named `RunTot_<source>` exactly.
- If a target name already exists in the input, this is a collision. Preserve
  the old behavior? The old node overwrites via `with_columns`, which replaces
  an existing `RunTot_x` column. Keep that: replacing the same derived name is
  allowed; do not add a new `_2` suffix.
- `cum_sum` runs in input order within each group; do not sort first.
- Apply `normalize_to_supported_dtypes` to the result, as the current node
  does, so narrow integer inputs do not leak unsupported dtypes.
- Return a LazyFrame.
- Downstream e2e expects `RunTot_RelevancyNum` and cumulative sums per
  `Difficulty`; this is the acceptance property.

## 4. Core extraction

Create `core/shaping/running_total.py`:

```python
DEFAULTS = {"sum_columns": [], "group_by_columns": []}


def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    frame = as_lazy(frames[0])
    schema = schema_of(frame)
    numeric = [name for name, dtype in schema.items() if dtype.is_numeric()]
    sums = [name for name in (settings or {}).get("sum_columns") or [] if name in numeric]
    groups = [name for name in (settings or {}).get("group_by_columns") or [] if name in schema]
    if not sums:
        return [frame]
    expressions = []
    for name in sums:
        expression = pl.col(name).cum_sum()
        if groups:
            expression = expression.over(groups)
        expressions.append(expression.alias(f"RunTot_{name}"))
    return [normalize_to_supported_dtypes(frame.with_columns(expressions))]
```

- Import `normalize_to_supported_dtypes` from
  `trigger_designer.core.utils.dtype_utils`.
- Do not mutate `settings` lists.
- Do not compute a running total for string/date columns, even if selected.

## 5. UI

Use two column pickers, not custom checkbox lists:

```python
FORM = (
    FormSection(
        "Running totals",
        (
            Field("sum_columns", "Sum", "columns", filter="numeric"),
            Field("group_by_columns", "Group by", "columns"),
        ),
        info="Each selected sum column becomes RunTot_<column>.",
    ),
)
```

- Add `filter="numeric_only"` to `shaping_support._passes`:
  `if kind == "numeric_only": return dtype.is_numeric()`. Use that here.
  Do not reuse `filter="numeric"` because it also admits String columns for
  potential casting; the old Running Total only offers actual numeric
  columns.
- Empty sum selection is valid and means pass-through.
- Dock summary: `N sums, M groups`.
- Do not add a "reset" control; undo covers it.

## 6. Content and node

- Replace the old content, delete `process_data`, `on_sum_selection_changed`,
  `on_group_selection_changed`, `update_checkboxes`, `clear_data`, old
  `get_code`/`serialize`/`deserialize` (keep loader).
- Set `self.output_variables = [f"var_runtot_{self.id}"]` after `super().__init__`
  to keep generated variable names stable.
- Keep the node class name, enum, icon, title and registry entry.
- No upstream rename following is needed (Running Total adds, does not rename).

## 7. Legacy loader

Old content serialized `sum_columns`/`group_by_columns` at the top level:

```python
def _legacy_settings(self, data):
    return {
        "sum_columns": [str(name) for name in data.get("sum_columns") or []],
        "group_by_columns": [str(name) for name in data.get("group_by_columns") or []],
    }

def deserialize(self, data, hashmap={}):  # noqa: B006
    if "settings" not in data and (
        "sum_columns" in data or "group_by_columns" in data
    ):
        data = dict(data)
        data["settings"] = self._legacy_settings(data)
    return super().deserialize(data, hashmap)
```

## 8. Tests

`tests/unit/test_running_total_core.py`:

- no sums -> same frame;
- one sum -> `RunTot_x` cumulative in input order;
- group by -> cumulative restarts per group;
- multiple sums;
- missing/string sum columns ignored;
- existing `RunTot_x` is replaced, not duplicated;
- supported dtypes after narrow int input;
- lazy frame stays lazy.

`tests/ui/test_running_total_dock.py`:

- dock shows sum/group pickers;
- selecting a sum column changes output and adds `RunTot_...`;
- group selection changes the value sequence;
- undo/redo restores both lists and output;
- generated code equals live;
- serialization round-trip.

Keep the existing e2e property test
`test_running_total_frame_is_cumulative_per_keyword` and the saved golden.

## 9. Steps

1. Add core + tests.
2. Replace content with two pickers + loader.
3. Replace node with `ShapingNode`.
4. Remove old checkbox/widget code and imports.
5. Run focused tests, the Running Total e2e property test, then all e2e.
6. Commit as `refactor: move Running Total onto the shaping execution system`.

## 10. Acceptance

- [x] `RunTot_<column>` naming is unchanged.
- [x] Grouped cumulative sums match the existing property test.
- [x] No sum columns passes through.
- [x] Checked-in sample workflows were migrated to the new `settings` schema;
      no legacy loader is kept (project decision: no backward compatibility).
- [x] Live == generated output.

## 11. Do not

- Do not sort before the cumulative sum.
- Do not add a running total for every numeric column automatically.
- Do not change the `RunTot_` prefix.
