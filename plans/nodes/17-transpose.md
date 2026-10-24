# Transpose - modernization plan

Status: not started.
Implementation order: 8 of 18 (Tier 1, reshape columns).
Read first: `plans/nodes/README.md`.

## 1. Current implementation

- File: `src/trigger_designer/qt/widgets/nodes/Transform/transpose.py`.
- Content: `TransposeContent` (line 39).
- Node: `TriggerNode_Transpose` (line 397).
- Inputs: one. Outputs: one.
- Settings today: `key_columns`, `data_columns`, `missing_action`
  (`"warn"`, `"error"`, `"ignore"`).
- Old execution: `process_data` calls Polars `unpivot` with
  `variable_name="Name"`, `value_name="Value"`, then
  `normalize_to_supported_dtypes`.
- Empty `data_columns` -> pass input through.
- Missing data columns: `error` raises, `warn`/`ignore` skip.
- Missing key columns are always skipped with a warning.
- Old UI: two checkbox lists and an action combo; `dock_actions`.
- Old codegen: emits an unpivot call (note: the old `get_code` references
  `self.data`, which is a widget projection; the new core must use the input
  variable instead).
- Existing tests: none dedicated; all-node e2e only.
- Saved workflow: `savedfiles/10. Transpose.tds`.

## 2. Target

- Core: `src/trigger_designer/core/shaping/transpose.py`.
- Content: `TransposeContent(ShapingContent)`.
- Node: `TriggerNode_Transpose(ShapingNode)`.
- Settings: `key_columns`, `data_columns`, `missing_action`.
- Output kind: `("transpose",)`.
- `INPUTS = 1`; `HISTORY = "Transpose"`;
  `SUMMARY = "wide to long"`.

### Settings schema

```python
DEFAULTS = {
    "key_columns": [],
    "data_columns": [],
    "missing_action": "warn",
}
```

## 3. Behavior contract

- No `data_columns` -> return the input unchanged.
- Data columns become rows with `Name` = source column and `Value` =
  the cell value; key columns are repeated.
- Output column order: key columns (in input order), then `Name`, then
  `Value`. Polars `unpivot` currently produces this; pin it in a test.
- `data_columns` may contain key columns? The old node allows it, but that
  duplicates values. Preserve current behavior; do not add validation unless
  a test proves it is needed.
- Missing data columns:
  - `error`: raise `ShapingError("TD-SHAPE-003", "Column(s) not found: ...")`;
  - `warn`: skip them and return a warning chip via `describe`;
  - `ignore`: skip silently.
- Missing key columns: always skip with a warning (current behavior).
- If no valid data columns remain: return `None`/error? The old node sets
  `data = None`, which makes the node invalid. Prefer a `ShapingError` with
  `TD-SHAPE-003` for `error`; for `warn`/`ignore` with zero valid columns,
  pass the input through and warn. Record this explicit choice in the tests.
- Apply `normalize_to_supported_dtypes` after unpivot.
- Return a LazyFrame; `unpivot` stays lazy.

## 4. Core extraction

Create `core/shaping/transpose.py`:

```python
DEFAULTS = {
    "key_columns": [],
    "data_columns": [],
    "missing_action": "warn",
}


def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    frame = as_lazy(frames[0])
    schema = schema_of(frame)
    key_columns = [name for name in settings.get("key_columns") or [] if name in schema]
    data_columns = [name for name in settings.get("data_columns") or [] if name in schema]
    missing = [name for name in settings.get("data_columns") or [] if name not in schema]
    if not settings.get("data_columns"):
        return [frame]
    if missing and settings.get("missing_action") == "error":
        raise ShapingError("TD-SHAPE-003", f"Column(s) not found: {', '.join(missing)}")
    if not data_columns:
        return [frame]
    out = frame.unpivot(
        index=key_columns,
        on=data_columns,
        variable_name="Name",
        value_name="Value",
    )
    return [normalize_to_supported_dtypes(out)]


def describe(frames: list, settings: dict) -> list[tuple[str, str]]:
    schema = schema_of(as_lazy(frames[0]))
    missing = [name for name in settings.get("data_columns") or [] if name not in schema]
    if not missing:
        return []
    return [(f"{len(missing)} data column(s) missing", "warning")]
```

- Do not use `self.data` for the input; the runner only has `frames`.
- Preserve the exact `Name`/`Value` output names.

## 5. UI

```python
FORM = (
    FormSection(
        "Transpose",
        (
            Field("key_columns", "Key columns", "columns"),
            Field("data_columns", "Data columns", "columns"),
            Field(
                "missing_action",
                "If columns are missing",
                "combo",
                options=(
                    ("warn", "Warn and skip"),
                    ("error", "Error"),
                    ("ignore", "Ignore"),
                ),
            ),
        ),
        info="Data columns become Name/Value rows; key columns repeat.",
    ),
)
```

- Keep the old labels ("Key Columns", "Data Columns", "Missing Columns")
  where they fit the design system.
- Use `ColumnPicker` for both lists; it supplies search and All/None.
- Empty data selection means pass-through; show a hint.
- The old `action_button` and `dock_actions` can be removed unless the
  action is needed for a bulk select; prefer the picker's bulk controls.

## 6. Content and node

- Delete `process_data`, `on_key_selection_changed`,
  `on_data_selection_changed`, `on_action_changed`, `dock_actions`, old
  `get_code`/`serialize`/`deserialize` (keep loader).
- Set `self.output_variables = [f"var_transpose_{self.id}"]`.
- Keep the node class name, enum, icon, title and registry entry.
- No upstream rename following is needed.

## 7. Legacy loader

Old content serialized the three keys at the top level:

```python
def _legacy_settings(self, data):
    action = str(data.get("missing_action") or "warn")
    if action not in ("warn", "error", "ignore"):
        action = "warn"
    return {
        "key_columns": [str(name) for name in data.get("key_columns") or []],
        "data_columns": [str(name) for name in data.get("data_columns") or []],
        "missing_action": action,
    }

def deserialize(self, data, hashmap={}):  # noqa: B006
    if "settings" not in data and (
        "key_columns" in data or "data_columns" in data
    ):
        data = dict(data)
        data["settings"] = self._legacy_settings(data)
    return super().deserialize(data, hashmap)
```

Test with `savedfiles/10. Transpose.tds`.

## 8. Tests

`tests/unit/test_transpose_core.py`:

- no data columns -> identical input;
- key + data -> expected long frame, exact `Name`/`Value` columns and order;
- multiple key columns;
- missing key column skipped;
- missing data column with `warn`, `ignore`, `error`;
- no valid data columns fallback;
- dtype normalization (narrow int input);
- lazy frame stays lazy.

`tests/ui/test_transpose_dock.py`:

- dock builds with key/data pickers and missing-action combo;
- editing each setting changes output;
- undo/redo restores settings;
- generated code equals live;
- serialization round-trip.

Run the saved Transpose golden.

## 9. Steps

1. Add core + tests.
2. Replace content with form + loader.
3. Replace node with `ShapingNode`.
4. Remove old widget code and imports.
5. Run focused tests, Transpose golden, all-node e2e.
6. Commit as `refactor: move Transpose onto the shaping execution system`.

## 10. Acceptance

- [ ] Output columns are exactly `key columns..., Name, Value`.
- [ ] Empty data selection passes through.
- [ ] Missing-column actions behave as specified.
- [ ] Old `key_columns`/`data_columns`/`missing_action` load.
- [ ] Live == generated output.

## 11. Do not

- Do not rename `Name`/`Value`.
- Do not collect the frame.
- Do not use the old codegen as the source of truth; it has a widget-state bug.
