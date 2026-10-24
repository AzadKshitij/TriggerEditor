# Join - modernization plan

Status: not started.
Implementation order: 15 of 18 (Tier 4, two inputs, three outputs).
Read first: `plans/nodes/README.md`.

## 1. Current implementation

- File: `src/trigger_designer/qt/widgets/nodes/Join/join.py` (1,500+ lines).
- Content: `JoinContent` (line 37).
- Node: `TriggerNode_Join` (line 1428).
- Inputs: two. Outputs: three - left-only, joined, right-only
  (`outputs=[3, 3, 3]`).
- Settings today:
  - `join_type` (UI-only; the engine always does a full outer join)
  - `mapping_data`: `[{"left_column", "right_column"}]`
  - `selected_columns`: `[{"name", "source": "L"|"R"}]`
  - `auto_accept_new_columns`
  - `known_columns` (same shape as selected)
- Old execution: `transform_data` performs one full outer join with
  `coalesce=True`, tags rows with `__left_present`/`__right_present`, renames
  conflicting right columns to `<name>_right`, and derives the three outputs
  from one collected result.
- Rename following: `_follow_upstream_renames` remaps mapping/selection;
  the node calls it in `processInputs`.
- Output selection: `_sync_selected_with_schema` prunes stale names, adds new
  arrivals when auto-accept is on, and refreshes `known_columns`.
- Old UI: mapping row editors, output column checklist/search, auto-accept
  menu action.
- Existing tests: `tests/ui/test_join_rename_propagation.py`; saved workflows
  `savedfiles/4. in-join.json`, `4.1. in-join.json`, plus goldens.
- Existing tests assume the full outer join and three outputs.

## 2. Target

- Core: `src/trigger_designer/core/shaping/join.py`.
- Content: `JoinContent(ShapingContent)` with a custom mapping/output layout.
- Node: `TriggerNode_Join(ShapingNode)`.
- Settings: the five keys above except `join_type` remains for compatibility.
- Output kinds: `("left", "join", "right")`.
- `INPUTS = 2`; `HISTORY = "Join"`;
  `SUMMARY = "three-way join"`.

### Settings schema

```python
DEFAULTS = {
    "join_type": "inner",  # UI/legacy only; see behavior contract
    "mapping_data": [],
    "selected_columns": [],
    "auto_accept_new_columns": True,
    "known_columns": [],
}
```

## 3. Behavior contract

- **The engine is a full outer join.** `join_type` is currently a UI setting
  that does not change `transform_data`; do not silently switch the engine to
  inner/left/right in this migration. Keep the setting, document that the
  three-output design requires full outer.
- `mapping_data` empty -> `TD-SHAPE-001` "Add at least one key pair".
- Each mapping pair must reference columns present in the corresponding
  input; invalid pairs are dropped. If no valid pair remains -> the same
  error.
- Conflicting non-key right columns are renamed `<name>_right` before the
  full join; left conflicts get `<name>_left` from Polars. Do not change the
  suffix contract without updating goldens.
- `selected_columns` empty -> all non-internal result columns, in result
  order.
- `selected_columns` preserves its list order; duplicate names are removed.
  A selected right key that was coalesced away is mapped to its left
  counterpart (preserve current behavior).
- Output 0 = rows present only on the left, with left columns.
- Output 1 = matched rows, with the selected output columns.
- Output 2 = rows present only on the right, with right columns plus the
  coalesced key when needed.
- `auto_accept_new_columns` and `known_columns` are UI selection state:
  - new live columns are appended to `selected_columns` only when auto
    accept is on and the column was never seen;
  - explicitly unchecked known columns stay out;
  - `known_columns` is refreshed to the live schema.
- Rename following must work before the join: if the left/right upstream
  reports old->new, update mapping/selected/known for that side.
- Return lazy frames; the old implementation collects inside `transform_data`
  to derive all three outputs. Keep the collect inside the runner and
  `.lazy()` the results.
- Output variables: `var_l_join_<id>`, `var_join_<id>`, `var_r_join_<id>`.
- `join_type` is not used by the runner; keep it settable and serialized.

## 4. Core extraction

Create `core/shaping/join.py` and port `transform_data` with these changes:

- `self.left_data`/`self.right_data` -> `frames[0]`/`frames[1]`;
- `self.mapping_data`/`selected_columns` -> `settings`;
- `frame_schema` from common;
- keep the tag columns, suffixing, selected-column remap and full outer join
  exactly;
- return `[l_data, data, r_data]` as lazy frames.

```python
DEFAULTS = {...}

def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    left = as_lazy(frames[0])
    right = as_lazy(frames[1])
    ...
    return [l_data.lazy(), data.lazy(), r_data.lazy()]
```

- Do not use `join_type` in the runner.
- Do not collect the input before checking schemas.
- `describe` can report mapping/output selection counts; keep it cheap.

## 5. UI

Keep the custom Join dock; it is a table-like editor, not a simple form.

### Mapping section

- One row per `settings["mapping_data"]`:
  - left column `NoWheelComboBox` (single-select `ColumnPicker` is fine),
  - right column combo,
  - delete icon button.
- "Add key pair" button adds `{"left_column": "", "right_column": ""}`.
- If both frames are present and mapping is empty, `ensure_default_mapping`
  chooses the first column of each side (old behavior).
- Sanitize/write back the whole mapping list on edits. Add/remove are list
  changes; combo edits are property changes.

### Output columns section

- Searchable `ColumnChecklist` or `ColumnPicker` with source labels
  `L: name` / `R: name`.
- "All"/"None" bulk actions (text allowed for these paired toggles).
- Auto-accept menu action, bound to `auto_accept_new_columns`.
- Preserve the current `known_columns` semantics.

- All edits use `set_setting`; no `self.mapping_data`/`self.selected_columns`
  runtime lists.
- Keep 30 px controls, 40 px toolbar, shared `IconButton`.
- Disable the mapping section when either input is absent; show
  `EmptyStateLabel`.

## 6. Content and node

- `JoinContent`:
  - `SETTINGS`, `MODULE`, `OUTPUT_KINDS=("left","join","right")`,
    `INPUTS=2`.
  - override `compute()`:
    1. `_sanitize_mapping(settings, schemas)`;
    2. `_sync_selected_with_schema()` (auto accept/known columns);
    3. `return super().compute()`.
  - `apply_upstream_renames(left_map, right_map)` updates mapping/selected/
    known by source; returns changed.
  - `ensure_default_mapping()` and `_sync_selected_with_schema()` are model
    methods over settings.
  - keep table/search/auto-accept widget methods as UI projections.
- `TriggerNode_Join(ShapingNode)`:
  - override `processInputs(input_values)` to call
    `content.apply_upstream_renames(upstream_rename_map(getInput(0)),
    upstream_rename_map(getInput(1)))` before `super().processInputs`.
  - preserve output variable names.
- Delete old `transform_data`/custom get_code/serialize/deserialize (keep
  loader), old state fields, old timer (base/live evaluate handles).
- Keep class/title/icon/enum/registry.

## 7. Legacy loader

Old keys are top-level. Map:

```python
def _legacy_settings(self, data):
    return {
        "join_type": str(data.get("join_type") or "inner"),
        "mapping_data": [
            {"left_column": str(row.get("left_column") or ""),
             "right_column": str(row.get("right_column") or "")}
            for row in data.get("mapping_data") or []
        ],
        "selected_columns": [
            {"name": str(row.get("name") or ""),
             "source": "R" if row.get("source") == "R" else "L"}
            for row in data.get("selected_columns") or []
        ],
        "auto_accept_new_columns": bool(data.get("auto_accept_new_columns", True)),
        "known_columns": [
            {"name": str(row.get("name") or ""),
             "source": "R" if row.get("source") == "R" else "L"}
            for row in data.get("known_columns") or []
        ],
    }
```

Test with the three saved Join workflows and their goldens.

## 8. Tests

`tests/unit/test_join_core.py`:

- inner/full matching rows -> joined output;
- left-only and right-only outputs;
- conflicting names get `_right`;
- selected column order/source;
- coalesced right key remap;
- empty mapping -> `TD-SHAPE-001`;
- invalid pairs dropped; all invalid -> error;
- lazy inputs;
- no selected columns -> all non-indicator columns;
- three outputs are independent and lazy.

`tests/ui/test_join_dock.py`:

- mapping add/remove/edit; default mapping;
- output checklist auto-accept and explicit uncheck;
- upstream rename updates mapping and selection;
- undo/redo for mapping and output edits;
- generated code equals live for all three outputs;
- legacy saved Join loads.

Keep `test_join_rename_propagation` and the saved Join goldens green.

## 9. Steps

1. Add core + tests.
2. Rebase content on settings + `ShapingContent`; port sanitize/rename/auto
   accept methods.
3. Rebuild mapping/output sections; keep the existing UX.
4. Replace node with `ShapingNode` and rename-follow override.
5. Remove old state/transform/codegen/timer.
6. Run focused tests + Join rename tests + Join e2e goldens.
7. Commit as `refactor: move Join onto the shaping execution system`.

## 10. Acceptance

- [ ] Three outputs match the old goldens.
- [ ] Full outer join semantics are unchanged.
- [ ] Upstream renames do not break mapping or selection.
- [ ] Auto-accept and explicit uncheck still behave.
- [ ] Old saved Join files load.

## 11. Do not

- Do not turn `join_type` into a real inner/left/right engine in this
  migration; it would change the three-output contract.
- Do not change the `_left`/`_right` suffix rules without goldens.
- Do not use `getSocketValue`; `ShapingNode` resolves input sockets.
