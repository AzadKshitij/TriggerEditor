# Select - completed reference migration

Status: **done** at commit `23eadb8` (plus the node-base helper split in
`1eeb293`). This is not a work item. Read it before implementing any other
brief.

## 1. Files

| Layer | File |
|---|---|
| Core | `src/trigger_designer/core/shaping/select.py` |
| Content/node | `src/trigger_designer/qt/widgets/nodes/Preparation/select.py` |
| Shared content | `src/trigger_designer/qt/helpers/shaping_support.py` |
| Shared config base | `src/trigger_designer/qt/helpers/config_content.py` |
| Core tests | `tests/unit/test_select_core.py` |
| Dock tests | `tests/ui/test_select_dock.py`, `test_select_bulk_ops.py`, `test_select_move_rows.py`, `test_select_rename_propagation.py` |
| E2E | `tests/e2e/test_workflow_goldens.py` (Select saved workflows) |

## 2. Settings schema

```python
DEFAULTS = {
    "columns": [
        # {
        #   "name": "customer_full_name",
        #   "selected": True,
        #   "dtype": "String",
        #   "rename": "",
        #   "date_format": "",
        #   "dtype_custom": False,
        # }
    ],
    "auto_accept_new_columns": True,
}
```

- `columns` is the **only** ordered model. The table is a projection.
- `selected`, `rename`, `dtype` and `dtype_custom` are per-column settings.
- `auto_accept_new_columns` controls arrivals from upstream.
- No `changes` dict is written. `changes` is derived only for the old
  `SelectTableWidget` adapter.

## 3. Core pattern

`core/shaping/select.py`:

- `DEFAULTS`;
- `display_dtype`, `dtype_matches`, `build_dtype_expr`, `infer_dtype`;
- `run_node(frames, settings) -> [LazyFrame]`.

Key behavior:

- empty `columns` -> pass input through;
- no selected usable columns -> pass input through;
- select in table order, cast when `dtype_custom`, rename last;
- missing columns are ignored by the runner; the content retains them in
  settings so the UI can show them as missing;
- date/datetime parsing uses a list of formats and `coalesce`;
- boolean parsing accepts true/false tokens and numeric 0/1.

This is the template for core extraction:

1. move pure logic first;
2. keep the runner independent of widgets;
3. make live and codegen call the same function;
4. put all errors in `ShapingError` with stable codes.

## 4. Content pattern

`SelectContent(ShapingContent)`:

- `SETTINGS`, `MODULE`, `RUNNER`, `OUTPUT_KINDS`, `INPUTS`, `HISTORY`,
  `SUMMARY`.
- `create_layout` keeps the **table** as the editor:
  - toolbar 40 px with search, All/None, up/down, options menu;
  - `SelectTableWidget` with columns Check, Name, Type, Rename;
  - `QSortFilterProxyModel` for search;
  - `_undo_composite = True` on the table;
  - `_on_table_data` converts rows to `columns` and calls `set_setting`;
  - `_sync_widgets_from_model` re-projects settings after undo.
- `_reconcile_columns`:
  - fills defaults;
  - refreshes non-custom dtypes from the live schema;
  - appends new columns (selected when `auto_accept` or first build);
  - retains missing columns.
- `apply_upstream_renames(rename_map)`:
  - renames stored column names only when old exists and new is free;
  - table refresh is a projection.
- `dock_summary`/`dock_context` report selected/renamed/retyped counts.
- Legacy loader at lines 603-669 converts old `table_data`/`changes` to
  `settings["columns"]` one way.

`TriggerNode_Select(ShapingNode)`:

- output text `("Out",)`;
- `processInputs` applies `upstream_rename_map` before `super()`;
- base handles input resolution, live compute and codegen.

## 5. What to copy for other nodes

### Table node

Copy the shape of `SelectContent` when the node's editor is a table:

- keep the table;
- make the table rows a projection of one list setting;
- one table action = one `set_setting`/`push_list_change`;
- `_undo_composite = True`;
- override `_sync_widgets_from_model` to reset rows without recording;
- parse/sanitize in one `_rows_to_setting` function;
- keep a one-way legacy loader.

### Form node

For simple nodes, do **not** copy the table machinery. Use the `FORM` engine
in `ShapingContent` (`Field`, `FormSection`, `RuleStack`, `ColumnPicker`).
The Count/Sort/Unique/Transpose plans show the expected shape.

### Rename propagation

- `upstream_rename_map` lives in `qt/helpers/rename_map.py` and is re-exported
  from `node_base`.
- A node that renames columns implements `apply_upstream_renames` on its
  content and calls it from `processInputs` before `super()`.
- A node that computes a rename map for downstream users implements
  `_current_mapping()` (Normalize) or stores renames in its settings
  (Select).
- Collisions are skipped, not overwritten.

### Legacy loader

- Only write `settings` in the new runtime.
- Detect old shape (`"settings" not in data` plus an old key).
- Build the settings dict in a pure `_legacy_settings(data)`.
- Never add old-attribute properties/setters.
- Test with a checked-in saved workflow where one exists.

## 6. Verification used

- `tests/unit/test_select_core.py`
- `tests/ui/test_select_dock.py`
- `tests/ui/test_select_bulk_ops.py`
- `tests/ui/test_select_move_rows.py`
- `tests/ui/test_select_rename_propagation.py`
- `tests/e2e/test_workflow_goldens.py`
- `tests/unit/test_frames.py` for the shared frame helpers.

The Select migration is the proof that the system works. When a new node
seems to need a different architecture, first check whether Select already
solved the same concern.
