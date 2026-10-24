# Unique - modernization plan

Status: implemented.
Implementation order: 5 of 18 (Tier 0, row removal, two outputs).
Read first: `plans/nodes/README.md`.

## 1. Current implementation

- File: `src/trigger_designer/qt/widgets/nodes/Preparation/unique.py`.
- Content: `UniqueContent` (line 34).
- Node: `TriggerNode_Unique` (line 473).
- Inputs: one. Outputs: two - unique rows and duplicate rows
  (`output_text=["Unique", "Duplicates"]`, `outputs=[3, 3]`).
- Settings today: `selected_columns: list[str]`.
- Old runtime state: `incom_data`, `incoming_variable`, `data`,
  `duplicate_data`.
- Old execution: `UniqueContent.process_data`:
  - if no live selection: `data = input`, `duplicate_data = input.head(0)`;
  - else `data = input.unique(subset=columns, maintain_order=True)`;
  - duplicates = `input.filter(pl.struct(columns).is_duplicated())`.
- Old UI: `create_layout` builds a `ColumnChecklist` with a search bar and
  All/None actions; `_live_selected_columns` filters to the live schema.
- Old codegen: `get_code` emits `unique` plus a duplicate filter.
- Existing tests: no dedicated unit file; covered by
  `savedfiles/5. in-unique.json` goldens.
- Saved workflow: `savedfiles/5. in-unique.json`.

## 2. Target

- Core: `src/trigger_designer/core/shaping/unique.py`.
- Content: `UniqueContent(ShapingContent)`.
- Node: `TriggerNode_Unique(ShapingNode)`.
- Settings key: `selected_columns`.
- Output kinds: `("unique", "duplicates")`.
- `INPUTS = 1`; `HISTORY = "Unique"`;
  `SUMMARY = "duplicate detection"`.

### Settings schema

```python
DEFAULTS = {
    "selected_columns": [],
}
```

## 3. Behavior contract

- Selected columns are compared as a row key; all other columns are carried
  from the first occurrence.
- Preserve the first occurrence and input order in the unique output
  (`maintain_order=True`).
- Duplicate output contains **every** row that belongs to a duplicated key
  group, not only the later copies. This matches the current
  `is_duplicated()` behavior; do not change it.
- Selection may contain columns that disappeared from upstream; keep only
  names present in the live schema.
- If no selected columns survive: unique output is the full input and the
  duplicate output is `input.head(0)`.
- Null values participate in the key; do not drop null rows.
- Return lazy frames; `unique` and `filter` stay lazy.
- Two outputs must be usable independently downstream (ShapingNode handles
  socket order; do not use `getSocketValue`).

## 4. Core extraction

Create `core/shaping/unique.py`:

```python
"""Unique: first occurrence per key plus all duplicate rows (Qt-free)."""

from __future__ import annotations

import polars as pl

from trigger_designer.core.shaping.common import as_lazy, schema_of

DEFAULTS = {"selected_columns": []}


def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    frame = as_lazy(frames[0])
    schema = schema_of(frame)
    columns = [
        str(name)
        for name in (settings or {}).get("selected_columns") or []
        if str(name) in schema
    ]
    if not columns:
        return [frame, frame.head(0)]
    duplicates = frame.filter(pl.struct(columns).is_duplicated())
    unique = frame.unique(subset=columns, maintain_order=True)
    return [unique, duplicates]
```

- If you prefer `pl.col(...).is_duplicated()` over `struct`, verify the
  duplicate semantics on a multi-column key and keep the existing tests.
- Do not call `.collect()`.
- Do not deduplicate the duplicate output: it intentionally contains all
  copies.

## 5. UI

Use the shared column picker, not the old custom search/list:

```python
FORM = (
    FormSection(
        "Duplicate key",
        (
            Field(
                "selected_columns",
                "Columns",
                "columns",
                hint="Rows matching on all selected columns are duplicates.",
            ),
        ),
    ),
)
```

- `ColumnPicker` already provides search, All/None, and 30 px sizing.
- Empty selection is valid and means "no duplicate key configured".
- The dock summary should say `N columns selected`.
- Keep the node's existing output labels `Unique` and `Duplicates`.
- If the old UI's "All/None" wording is important, rely on `ColumnPicker`'s
  built-in controls; do not add a second pair of buttons.

## 6. Content and node

- Replace the old content body; delete `process_data`, `_update_column_list`,
  `_populate_column_list`, `_filter_columns`, `_select_all_columns`,
  `_deselect_all_columns`, `_on_checklist_changed`,
  `_store_selection_history`, `_get_selected_columns`, `history_stamp_callback`
  and custom `get_code`.
- Set `self.output_variables = [f"var_unique_{self.id}",
  f"var_duplicate_{self.id}"]` after `super().__init__` if the old generated
  variable names are asserted anywhere. Otherwise the generic names are fine.
- Keep the node class name, icon, title, enum and registry entry.
- No upstream rename following is needed: Unique does not rename columns.

## 7. Legacy loader

Old saved key: `selected_columns`.

```python
def _legacy_settings(self, data):
    return {"selected_columns": [str(name) for name in data.get("selected_columns") or []]}

def deserialize(self, data, hashmap={}):  # noqa: B006
    if "settings" not in data and "selected_columns" in data:
        data = dict(data)
        data["settings"] = self._legacy_settings(data)
    return super().deserialize(data, hashmap)
```

Test with `savedfiles/5. in-unique.json` and `5. in-unique-out.json`.

## 8. Tests

`tests/unit/test_unique_core.py`:

- no selected columns -> input + empty duplicate frame;
- one key -> first occurrence kept, order preserved;
- multi-column key;
- null keys;
- duplicate output contains all copies;
- missing selected column is ignored;
- all selected columns missing -> pass-through + empty duplicates;
- LazyFrame stays lazy.

`tests/ui/test_unique_dock.py`:

- dock builds and shows the schema columns;
- select a column -> both outputs change;
- All/None works through the picker;
- undo/redo restores the selection and outputs;
- generated code executes to both live frames;
- serialize/deserialize round-trip.

Update any test that reads `UniqueContent.selected_columns` or
`process_data` directly. Keep the saved golden unchanged.

## 9. Steps

1. Add core + core tests.
2. Replace content with the form-based version and loader.
3. Replace node with `ShapingNode`; keep output labels and variable names.
4. Remove old widget/search/checkbox code and unused imports.
5. Run focused tests, saved Uniques goldens, then `tests/unit tests/e2e`.
6. Commit as `refactor: move Unique onto the shaping execution system`.

## 10. Acceptance

- [x] Both output sockets produce the correct frames.
- [x] No selected columns still passes through instead of erroring.
- [x] Duplicate rows are all copies, as before.
- [x] Checked-in sample workflows were migrated to the new `settings` schema;
      no legacy loader is kept (project decision: no backward compatibility).
- [x] Live == generated output for both sockets.

## 11. Do not

- Do not use `pl.DataFrame.unique` defaults that drop order.
- Do not return only the later duplicate rows.
- Do not rename the node title ("Unique" stays).
