# Sort - modernization plan

Status: not started.
Implementation order: 3 of 18 (Tier 0, row order only).
Read first: `plans/nodes/README.md`.

## 1. Current implementation

- File: `src/trigger_designer/qt/widgets/nodes/Preparation/sort.py`.
- Content: `SortContent` (line 39).
- Node: `TriggerNode_Sort` (line 503).
- Inputs: one. Outputs: one.
- Settings today: `sort_data: list[dict]`, rows shaped
  `{"column": str, "order": "Ascending" | "Descending"}`.
- Old runtime state: `incom_data`, `incoming_variable`, `data`.
- Old execution: `TriggerNode_Sort.processInputs` applies
  `incom.sort([columns], descending=[...])` and silently falls back to the
  input if Polars raises.
- Old UI: `create_layout` adds a `ConfigSection` with one row per sort key;
  `add_sort_row`, `on_column_changed`, `on_order_changed`, `remove_sort_row`
  maintain `sort_data`. Each row has a column combo and an order combo.
- Old codegen: `get_code` emits a `pl.sort` call.
- Existing tests: no dedicated unit test; indirectly covered by
  `savedfiles/7. in-sort-out.json` through the goldens.
- Saved workflow: `savedfiles/7. in-sort-out.json`.

## 2. Target

- Core: `src/trigger_designer/core/shaping/sort.py`.
- Content: `SortContent(ShapingContent)`.
- Node: `TriggerNode_Sort(ShapingNode)` in the same module.
- Settings key: `keys`.
- Output kind: `("sort",)`; output text `("Out",)`.
- `INPUTS = 1`; `HISTORY = "Sort"`; `SUMMARY = "sort keys"`.

### Settings schema

```python
DEFAULTS = {
    "keys": [],  # [{"column": "Amount", "order": "Ascending"}]
}
```

`order` is exactly `"Ascending"` or `"Descending"`. Do not use booleans in the
saved schema; the UI labels already use these strings.

## 3. Behavior contract

- No keys -> pass the input through unchanged, same lazy/eager kind at the
  boundary (return a LazyFrame).
- Keys are applied in list order; first key is the primary sort.
- Null ordering and stability use Polars defaults, as today.
- A configured key whose column disappeared from the live schema is skipped;
  if no valid keys remain, pass through. Do not raise for this node (the old
  node silently passed through on any sort error). Add a `describe` warning
  chip when columns are skipped.
- Preserve input row order for equal keys (Polars `sort` is stable by default
  in the current implementation; do not add `maintain_order` unless required
  by a test).
- Multiple sort keys and one sort key must both work.
- Sorting a LazyFrame stays lazy; do not collect.

## 4. Core extraction

Create `core/shaping/sort.py`:

```python
"""Sort: ordered multi-column sort (Qt-free)."""

from __future__ import annotations

import polars as pl

from trigger_designer.core.shaping.common import as_lazy, schema_of

DEFAULTS = {"keys": []}


def _keys(settings: dict) -> list[dict]:
    return [
        item
        for item in (settings or {}).get("keys") or []
        if isinstance(item, dict) and str(item.get("column") or "").strip()
    ]


def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    frame = as_lazy(frames[0])
    schema = schema_of(frame)
    keys = [item for item in _keys(settings) if item["column"] in schema]
    if not keys:
        return [frame]
    columns = [item["column"] for item in keys]
    descending = [item.get("order") == "Descending" for item in keys]
    return [frame.sort(columns, descending=descending)]


def describe(frames: list, settings: dict) -> list[tuple[str, str]]:
    schema = schema_of(as_lazy(frames[0]))
    missing = [
        item["column"]
        for item in _keys(settings)
        if item["column"] not in schema
    ]
    return [(f"{len(missing)} sort key(s) missing", "warning")] if missing else []
```

- Do not call `frame.columns`; use `schema_of`.
- Do not catch broad exceptions around `sort`; the only expected fallback is
  missing columns, handled above.
- `DEFAULTS["keys"]` must be a fresh list per content instance (the base class
  deep-copies `SETTINGS`; do not use a mutable class-level list directly).

## 5. UI

Use the normal form engine; keep the existing one-row-per-key design:

```python
FIELD = Field(
    "keys",
    "Sort keys",
    "list",
    max_items=10,
    item_default={"column": "", "order": "Ascending"},
    items=(
        Field("column", "Column", "column"),
        Field(
            "order",
            "Order",
            "combo",
            options=(("Ascending", "Ascending"), ("Descending", "Descending")),
        ),
    ),
)
FORM = (FormSection("Sort", (FIELD,)),)
```

- The list must support add, remove, move, duplicate and per-card collapsed
  state through `RuleStack` (base `_list_change` already does).
- Empty state: the section is visible with an "Add sort key" button; do not
  hide the whole dock.
- No search box is needed for sort keys.
- Use `HISTORY = "Sort"` so history entries read `"Sort Sort keys Added"` etc.

## 6. Content and node

- Replace the custom widget code in `SortContent` with the `ShapingContent`
  form above. Delete `sort_data`, `row_widgets`, `next_row_id`,
  `add_sort_row`, `on_column_changed`, `on_order_changed`,
  `remove_sort_row`, `history_stamp_callback` and custom `get_code`.
- `get_code` is inherited; its output variable is `var_sort_<id>`.
- Keep the node class name `TriggerNode_Sort`, icon, title, code and registry
  entry.
- No upstream rename following is needed: Sort references columns but does
  not rename them.

## 7. Legacy loader

The old saved key is `sort_data`. Add a one-way loader:

```python
def _legacy_settings(self, data):
    keys = []
    for row in data.get("sort_data") or []:
        column = str(row.get("column") or "").strip()
        if not column:
            continue
        order = str(row.get("order") or "Ascending")
        keys.append({
            "column": column,
            "order": "Descending" if order == "Descending" else "Ascending",
        })
    return {"keys": keys}


def deserialize(self, data, hashmap={}):  # noqa: B006
    if "settings" not in data and "sort_data" in data:
        data = dict(data)
        data["settings"] = self._legacy_settings(data)
    return super().deserialize(data, hashmap)
```

Test this with the checked-in `savedfiles/7. in-sort-out.json` workflow.

## 8. Tests

`tests/unit/test_sort_core.py`:

- no keys -> identical frame;
- one ascending key;
- one descending key;
- multiple keys with mixed order;
- missing key -> skipped; all missing -> pass-through; `describe` warning;
- LazyFrame stays lazy.

`tests/ui/test_sort_dock.py`:

- dock builds with columns from a connected frame;
- add a row -> `settings["keys"]` grows and live output sorts;
- edit column/order -> output changes; undo restores both;
- generated code executes to the same frame as live;
- serialize -> new instance deserialize round-trip.

Update any old Sort test that imports `SortContent.sort_data` or
`history_stamp_callback`. The saved golden must pass without regenerating it.

## 9. Steps

1. Add core module + tests.
2. Replace `SortContent` with the form-based content and loader.
3. Replace `TriggerNode_Sort` with `ShapingNode` subclass.
4. Remove the old widget/undo code and imports that are now unused.
5. Run focused tests, then `tests/unit tests/e2e`.
6. Commit as `refactor: move Sort onto the shaping execution system`.

## 10. Acceptance

- [ ] `sort_data` is gone from the new runtime.
- [ ] Old `sort_data` saved state loads through the one-way loader.
- [ ] Live and generated output match for ascending, descending and multi-key.
- [ ] Undo/redo works for add, remove, move and edit.
- [ ] The saved-workflow golden `7. in-sort-out` is unchanged.

## 11. Do not

- Do not change the order labels or the default to descending.
- Do not collect the frame.
- Do not add a "maintain order" or "nulls last" setting without a separate
  product decision; the current node does not expose them.
