# Cleansing - modernization plan

Status: implemented.
Implementation order: 10 of 18 (Tier 2, value/row/column mutation).
Read first: `plans/nodes/README.md`.

## 1. Current implementation

- File: `src/trigger_designer/qt/widgets/nodes/Preparation/cleansing.py`.
- Content: `CleansingContent` (line 56).
- Node: `TriggerNode_Cleansing` (line 735).
- Inputs: one. Outputs: one.
- Settings today:
  - `remove_null_rows` (False)
  - `remove_null_rows_from_selected_columns` (False)
  - `remove_null_columns` (False)
  - `replace_null_strings` (True)
  - `replace_null_numbers` (True)
  - `strip_whitespace` (True)
  - `normalize_spaces` (True)
  - `remove_all_whitespace` (False)
  - `case_modification` (`none`, `lower`, `upper`, `title`)
  - `remove_letters` (False)
  - `remove_numbers` (False)
  - `remove_punctuation` (False)
  - `selected_fields`
- Old execution: `process_data` collects, builds `DataCleansing`, applies
  null operations, null replacement, then text operations only to
  `selected_fields`.
- Old UI: four sections - fields, nulls, replacement, characters/case.
- Old codegen: `get_code` builds the same `DataCleansing` call chain.
- Core utility already exists: `src/trigger_designer/core/utils/cleansing_util.py`
  (`DataCleansing`, `NullStrategy`).
- Existing tests: none dedicated; all-node e2e only.
- Saved workflow: in the all-node workflow; no dedicated `.tds`.

## 2. Target

- Core: `src/trigger_designer/core/shaping/cleansing.py`.
- Content: `CleansingContent(ShapingContent)`.
- Node: `TriggerNode_Cleansing(ShapingNode)`.
- Settings: the 12 keys above.
- Output kind: `("cleansing",)`.
- `INPUTS = 1`; `HISTORY = "Cleansing"`;
  `SUMMARY = "nulls and text cleanup"`.

### Settings schema

```python
DEFAULTS = {
    "remove_null_rows": False,
    "remove_null_rows_from_selected_columns": False,
    "remove_null_columns": False,
    "replace_null_strings": True,
    "replace_null_numbers": True,
    "strip_whitespace": True,
    "normalize_spaces": True,
    "remove_all_whitespace": False,
    "case_modification": "none",
    "remove_letters": False,
    "remove_numbers": False,
    "remove_punctuation": False,
    "selected_fields": [],
}
```

`null_strategy` from the old class is unused configuration; do not carry it.

## 3. Behavior contract

- Order of operations is part of the contract:
  1. remove all-null rows (if selected);
  2. remove rows with nulls in selected fields (if selected and
     `selected_fields` is non-empty);
  3. remove all-null columns (if selected);
  4. replace null strings/numbers with defaults;
  5. text cleanup on `selected_fields` only:
     trim/normalize whitespace, remove characters, change case.
- If `selected_fields` is empty, text cleanup is a no-op. The old
  `remove_null_rows_from_selected_columns` live path called
  `remove_rows_with_nulls([])` while codegen skipped it; the modern runner
  must skip it when the list is empty so live and Run agree.
- Fields that disappeared upstream are ignored.
- `remove_all_whitespace` wins over `normalize_spaces` (DataCleansing already
  encodes this; do not reimplement).
- The old node collects because `DataCleansing` needs eager stats. Keep the
  collect inside `run_node`; return `.lazy()`.
- Preserve the old handling of null replacement: defaults supplied by
  `DataCleansing`.
- Errors from `DataCleansing` should surface as `ShapingError` with a stable
  code where known; otherwise let the normal translator wrap the exception.
  Do not swallow and return `None`.

## 4. Core extraction

Create `core/shaping/cleansing.py` and port `process_data` verbatim, replacing
`self.incom_data` with `frames[0]`:

```python
DEFAULTS = {...}

def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    frame = as_lazy(frames[0])
    data = frame.collect()
    cleaner = DataCleansing(data)
    s = {**DEFAULTS, **(settings or {})}
    fields = [name for name in s["selected_fields"] if name in data.columns]

    if s["remove_null_rows"]:
        cleaner.handle_nulls(NullStrategy.REMOVE_ALL_NULL_ROWS)
    if s["remove_null_rows_from_selected_columns"] and fields:
        cleaner.remove_rows_with_nulls(fields=fields)
    if s["remove_null_columns"]:
        cleaner.handle_nulls(NullStrategy.REMOVE_ALL_NULL_COLS)
    if s["replace_null_strings"] or s["replace_null_numbers"]:
        cleaner.replace_null_defaults(
            replace_strings=s["replace_null_strings"],
            replace_numbers=s["replace_null_numbers"],
        )
    if fields:
        if s["strip_whitespace"] or s["normalize_spaces"] or s["remove_all_whitespace"]:
            cleaner.strip_whitespace(
                remove_all=s["remove_all_whitespace"],
                normalize_spaces=s["normalize_spaces"],
                fields=fields,
            )
        if s["remove_letters"] or s["remove_numbers"] or s["remove_punctuation"]:
            cleaner.remove_characters(
                remove_letters=s["remove_letters"],
                remove_numbers=s["remove_numbers"],
                remove_punctuation=s["remove_punctuation"],
                fields=fields,
            )
        if s["case_modification"] != "none":
            cleaner.modify_case(s["case_modification"], fields=fields)
    return [cleaner.get_result().lazy()]
```

- Keep `DataCleansing` unchanged; do not duplicate its implementation in
  `core/shaping/cleansing.py`.
- The old `cleansing_stats` is UI-only. Do not put it in settings. If you keep
  a dock chip, compute it from the output or drop it; do not add a second
  execution path.

## 5. UI

Use standard sections and checkboxes:

1. **Fields** - `Field("selected_fields", "Clean", "columns")` with hint
   "Text rules apply only to these columns."
2. **Nulls** - `remove_null_rows`, `remove_null_rows_from_selected_columns`,
   `remove_null_columns`, `replace_null_strings`, `replace_null_numbers`.
3. **Whitespace and characters** - `strip_whitespace`, `normalize_spaces`,
   `remove_all_whitespace`, `remove_letters`, `remove_numbers`,
   `remove_punctuation`.
4. **Case** - combo `none/lower/upper/title` with display labels.

- Use `FormSection(..., info=...)` for the order explanation.
- `remove_null_rows_from_selected_columns` should be disabled/visually
  secondary when no fields are selected; do not change the saved value.
- Keep 30 px controls and the standard main spacing.
- Do not recreate the old per-field checkbox grid; `ColumnPicker` is the
  shared control.

## 6. Content and node

- Delete `process_data`, `_get_schema` (use `self.schema(0)`),
  `_normalize_selected_fields`, `_get_case_display_value`,
  `_refresh_cleansing_counts`, all `on_*_changed` handlers, the field
  checkbox methods, old `get_code`/`serialize`/`deserialize`.
- Set `self.output_variables = [f"var_cleansing_{self.id}"]`.
- Keep the node class name, enum, icon, title and registry entry.
- No upstream rename following is needed.

## 7. Legacy loader

Old content serialized the settings at the top level. Map every key with
the defaults above; normalize `selected_fields` to strings and drop unknown
case values to `"none"`.

```python
def _legacy_settings(self, data):
    settings = {"selected_fields": [str(n) for n in data.get("selected_fields") or []]}
    for key, default in core.DEFAULTS.items():
        if key == "selected_fields":
            continue
        value = data.get(key, default)
        settings[key] = bool(value) if isinstance(default, bool) else str(value)
    if settings["case_modification"] not in ("none", "lower", "upper", "title"):
        settings["case_modification"] = "none"
    return settings
```

Add the standard `deserialize` guard using `"case_modification" in data` or
`"selected_fields" in data`.

## 8. Tests

`tests/unit/test_cleansing_core.py`:

- remove all-null rows, null columns;
- remove rows null in selected fields (and no-op when the list is empty);
- replace null strings/numbers;
- trim/normalize/remove-all whitespace;
- remove letters/numbers/punctuation;
- lower/upper/title;
- selected fields limit text cleanup;
- missing selected field ignored;
- empty input;
- lazy input -> lazy output;
- live codegen and core produce the same frame.

`tests/ui/test_cleansing_dock.py`:

- all four sections build;
- toggling each option changes output;
- field selection limits text cleanup;
- undo/redo restores options and fields;
- generated code equals live;
- serialization round-trip.

Update the all-node e2e if it checks Old `cleansing_stats`/field checkboxes.

## 9. Steps

1. Add core + tests.
2. Replace content with form + loader.
3. Replace node with `ShapingNode`.
4. Remove old widget/stat code and imports.
5. Run focused tests and all-node e2e.
6. Commit as `refactor: move Cleansing onto the shaping execution system`.

## 10. Acceptance

- [x] The operation order matches the old `process_data`.
- [x] Text cleanup only touches selected fields.
- [x] Empty field selection does not make the node invalid.
- [x] Live == generated output.
- [x] Checked-in sample workflows were migrated to the new `settings` schema;
      no legacy loader is kept (project decision: no backward compatibility).

## 11. Do not

- Do not move cleansing logic into Polars expressions; `DataCleansing` is the
  oracle.
- Do not drop the eager collect; `DataCleansing` needs it.
- Do not add `null_strategy` to settings.
