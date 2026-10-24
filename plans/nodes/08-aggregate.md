# Aggregate (GroupBy) - modernization plan

Status: not started.
Implementation order: 12 of 18 (Tier 3, grouping and schema rewrite).
Read first: `plans/nodes/README.md`.

## 1. Current implementation

- File: `src/trigger_designer/qt/widgets/nodes/Preparation/groupby.py`.
- Content: `GroupByContent` (line 137). Node title is **Aggregate**.
- Node: `TriggerNode_GroupBy` (line 888).
- Inputs: one. Outputs: one.
- Settings today: `changes` with
  `{"group_by_columns": [...], "aggregations": {field: {"function", "alias"}}}`.
- Old UI: a `QTableWidget` action table plus a field picker and Add/Remove
  buttons. Action choices are dtype-dependent; group-by rows use the
  `GroupBy` action.
- Old execution: `apply_groupby` builds a `group_by` and aggregation
  expressions, special-cases `count` as `pl.len()`, and normalizes dtypes
  with `normalize_to_supported_dtypes`.
- Old codegen: `get_code` emits the same grouping expressions.
- Existing tests: no dedicated Aggregate unit test; all-node e2e only.
- Saved workflow: all-node workflow; no dedicated `.tds`.

## 2. Target

- Core: `src/trigger_designer/core/shaping/aggregate.py`.
- Content: `AggregateContent(ShapingContent)` with a custom table layout.
- Node: `TriggerNode_Aggregate(ShapingNode)` (keep the existing class name
  if the registry/tests depend on it; title stays `Aggregate`).
- Settings: one ordered `actions` list.
- Output kind: `("aggregate",)`.
- `INPUTS = 1`; `HISTORY = "Aggregate"`;
  `SUMMARY = "group and aggregate"`.

### Settings schema

```python
DEFAULTS = {
    "actions": [
        # {"field": "Region", "action": "GroupBy", "output_name": "Region"},
        # {"field": "Amount", "action": "Sum", "output_name": "Sum_Amount"},
    ],
}
```

Why a list instead of the old `changes` dict: the table is ordered and the
same field can be present as a group key plus later be aggregated; a list
preserves the visible row order and is naturally undoable. The core derives
the old group-by/aggregation structure from the list.

## 3. Behavior contract

- Action names and functions:

| Action | Function | Default output |
|---|---|---|
| `GroupBy` (legacy `Group By`) | group key | field |
| `Count` | `pl.len()` | `Count_<field>` |
| `Sum` | `sum` | `Sum_<field>` |
| `Mean` | `mean` | `Avg_<field>` |
| `Min` | `min` | `Min_<field>` |
| `Max` | `max` | `Max_<field>` |
| `Std` | `std` | `Std_<field>` |
| `Var` | `var` | `Var_<field>` |
| `Median` | `median` | `Median_<field>` |
| `First` | `first` | `First_<field>` |
| `Last` | `last` | `Last_<field>` |
| `N_Unique` | `n_unique` | `Unique_<field>` |
| `List` | `list` | `List_<field>` |

- No actions -> return the input unchanged (old `processInputs` behavior).
- An unknown action -> `TD-SHAPE-004` (do not silently turn it into Count).
- Group keys are emitted first, in action order; then aggregations, in action
  order. If an action field is missing from the input, skip it and add a
  `describe` warning. If no valid actions remain, pass the input through.
- If there are group keys but no aggregation actions: group and emit a
  `count` column named `count` (old behavior).
- If there are aggregation actions but no group keys: aggregate the whole
  table with `select`.
- `Count` is `pl.len()` regardless of the field; the field only names the
  output.
- A later action for the same field overwrites the earlier aggregation
  (the old dict behavior). `GroupBy` duplicates are ignored.
- Output names must be unique and non-empty; blank -> default. Duplicate
  final names -> `TD-SHAPE-002` (do not silently rename).
- Apply `normalize_to_supported_dtypes` to the result.
- Return a LazyFrame.
- Output variable: `var_groupby_<id>`.

## 4. Core extraction

Create `core/shaping/aggregate.py`:

```python
DEFAULTS = {"actions": []}

ACTION_TO_FUNCTION = {...}   # copy the table above
PREFIX_MAP = {...}           # copy the old prefixes


def normalize(settings: dict) -> dict:
    actions = []
    for item in (settings or {}).get("actions") or []:
        field = str(item.get("field") or "").strip()
        if not field:
            continue
        action = str(item.get("action") or "Count")
        if action == "Group By":
            action = "GroupBy"
        output = str(item.get("output_name") or "").strip()
        if not output:
            output = field if action == "GroupBy" else f"{PREFIX_MAP.get(action, '')}{field}"
        actions.append({"field": field, "action": action, "output_name": output})
    return {"actions": actions}


def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    ...
```

Implementation of `run_node`:

1. `frame = as_lazy(frames[0])`; `schema = schema_of(frame)`.
2. Read normalized actions. If empty -> `[frame]`.
3. Build `group_by` list and `aggregations` dict, skipping unknown/missing
   fields; build the `expressions` exactly as the old `apply_groupby` does.
4. If `group_by`:
   - `grouped = frame.group_by(group_by)`;
   - if no aggregation expressions: `grouped.agg(pl.len().alias("count"))`;
   - else `grouped.agg(expressions)`.
   If no `group_by`: `frame.select(expressions)` (if any).
5. `normalize_to_supported_dtypes`.
6. Return `[result]`.

- Reuse `ACTION_TO_FUNCTION`, `PREFIX_MAP`, `TEXT_ACTIONS`,
  `ARITHMETIC_ACTIONS` by moving them to core; the UI imports them from
  core. Do not keep a second copy.
- `describe` returns warnings for skipped missing fields.
- Do not collect; grouping on a LazyFrame is supported.

## 5. UI

Keep the table; this is the reference table-heavy dock alongside Select.

Structure:

- `ConfigSection("Group and aggregate")`.
- Toolbar (40 px): searchable field picker (`ColumnPicker` single or a
  `QComboBox` with search), `IconButton.themed` Add, `IconButton.themed`
  Remove.
- `QTableWidget` with columns:
  - Field (read-only text)
  - Action (`NoWheelComboBox`: GroupBy + dtype-appropriate actions)
  - Output name (`QLineEdit`, default from action)
  - Remove (`IconButton.themed`)
- `QTableWidget._undo_composite = True`; table edits call one `set_setting`
  for the whole `actions` list. Add/remove use `push_list_change` (structure);
  alias typing uses `push_property_change` with a per-row merge key.
- Action choices:
  - Text/Categorical: `GroupBy`, `Count`, `Min`, `Max`, `First`, `Last`,
    `N_Unique`, `List`.
  - Numeric/other: all actions.
  - Changing a field rebuilds that row's action list and default output name.
- Do not rebuild the table on alias keystrokes; update the model and let the
  focused editor keep focus.
- Empty table: show `EmptyStateLabel` or a one-line hint plus Add.
- Use design-system sizes: 30 px controls, 30x30 icon buttons, no inline QSS.

## 6. Content and node

- Delete `changes`, `cached_actions_data`, `_normalize_changes`,
  `_actions_data_from_changes`, `_changes_from_actions`, `apply_groupby`,
  table handlers, old `get_code`/`serialize`/`deserialize` (keep loader).
- Add `AggregateContent` methods:
  - `_actions_from_settings()` -> row dicts for the table;
  - `_commit_actions(rows, text, structural=False)`;
  - `_default_output(field, action)`;
  - `_actions_for_dtype(dtype)`.
- Set `self.output_variables = [f"var_groupby_{self.id}"]`.
- Keep title `Aggregate`, enum, icon and registry entry.

## 7. Legacy loader

Old saved state can contain both `changes` and `actions_data`.

```python
def _legacy_settings(self, data):
    actions = []
    for row in data.get("actions_data") or []:
        field = str(row.get("field") or "")
        if not field:
            continue
        action = str(row.get("action") or "Count")
        actions.append({
            "field": field,
            "action": "GroupBy" if action in ("GroupBy", "Group By") else action,
            "output_name": str(row.get("output_name") or ""),
        })
    if not actions:
        changes = data.get("changes") or {}
        for field in changes.get("group_by_columns") or []:
            actions.append({"field": field, "action": "GroupBy", "output_name": field})
        for field, config in (changes.get("aggregations") or {}).items():
            actions.append({
                "field": field,
                "action": core.FUNCTION_TO_ACTION.get(config.get("function", "count"), "Count"),
                "output_name": str(config.get("alias") or ""),
            })
    return core.normalize({"actions": actions})
```

Add the standard `deserialize` guard if `"actions_data"` or `"changes"` is
present and `settings` is not. Preserve the old healing path for corrupt
`changes` (list instead of dict) only inside the loader; delete it from
runtime.

## 8. Tests

`tests/unit/test_aggregate_core.py`:

- no actions -> pass-through;
- GroupBy only -> count column;
- GroupBy + Sum/Count/Mean;
- aggregation without group keys;
- Count uses `pl.len()` and aliases `Count_<field>`;
- all action functions;
- `N_Unique`/`List` output dtypes normalized;
- later action for the same field wins;
- missing field skipped + warning; all missing -> pass-through;
- duplicate output names -> `TD-SHAPE-002`;
- lazy input stays lazy.

`tests/ui/test_aggregate_dock.py`:

- table builds from settings and from a live frame;
- Add/Remove rows; action options by dtype;
- output name default and edit;
- undo/redo for add, remove, action change and alias;
- generated code equals live;
- legacy `changes` and `actions_data` load into `settings["actions"]`.

Run the all-node e2e; add a saved case only if a dedicated fixture is created.

## 9. Steps

1. Move action constants/helpers to core; add `run_node` + tests.
2. Replace content model with `settings["actions"]`; keep the table, rebuild
   it from settings.
3. Add loader for `changes`/`actions_data`.
4. Replace node with `ShapingNode`.
5. Remove old state/undo/codegen.
6. Run focused tests + all-node e2e.
7. Commit as `refactor: move Aggregate onto the shaping execution system`.

## 10. Acceptance

- [ ] `changes` is gone from the runtime; actions are the only model.
- [ ] GroupBy-only, aggregate-only and mixed work as before.
- [ ] Table undo is one step per action.
- [ ] Legacy `changes`/`actions_data` load.
- [ ] Live == generated output.

## 11. Do not

- Do not keep both `actions` and `changes` as truth.
- Do not silently rename duplicate output names.
- Do not change action labels/prefixes without updating the loader and
  goldens.
