# Filter - modernization plan

Status: not started.
Implementation order: 9 of 18 (Tier 2, drops rows).
Read first: `plans/nodes/README.md`.

## 1. Current implementation

- File: `src/trigger_designer/qt/widgets/nodes/Preparation/filter.py`.
- Content: `FilterContent` (line 50).
- Node: `TriggerNode_Filter` (line 1105).
- Inputs: one. Outputs: two - true and false
  (`output_text=["T", "F"]`, `outputs=[3, 3]`).
- Settings today:
  - `mode`: `builder` or `expression`
  - `column`, `operation` (default `Equals`), `value`, `value2`
  - `expression`
- Old execution:
  - builder: `update_data` builds a Polars expression and returns
    `input.filter(expr)` / `input.filter(~expr)`;
  - expression: `_update_expression_data` prepares a DuckDB WHERE clause and
    runs two queries, materialising then re-wrapping as lazy if the input was
    lazy.
- Old UI: mode selector, column/operation/value builder, SQL expression
  editor with validation, two output labels.
- Old codegen: builder emits `pl.filter`; expression emits a DuckDB query.
- Existing tests: `tests/ui/test_filter_expression.py`; saved workflow
  `savedfiles/6. in-filter-out.json`.
- Shared pure helpers currently live in
  `qt/widgets/sql_formula_editor.py`: `STRING_LITERAL_RE`,
  `translate_function_aliases`. They cannot be imported by a core module.

## 2. Target

- Core: `src/trigger_designer/core/shaping/filter.py`.
- Shared pure expression helper (create once, also used by Formula):
  `src/trigger_designer/core/shaping/sql_expression.py`.
- Content: `FilterContent(ShapingContent)` with a custom `create_layout`.
- Node: `TriggerNode_Filter(ShapingNode)`.
- Settings: `mode`, `column`, `operation`, `value`, `value2`, `expression`.
- Output kinds: `("true", "false")`.
- `INPUTS = 1`; `HISTORY = "Filter"`;
  `SUMMARY = "row filter"`.

### Settings schema

```python
DEFAULTS = {
    "mode": "builder",  # "builder" | "expression"
    "column": "",
    "operation": "Equals",
    "value": "",
    "value2": "",
    "expression": "",
}
```

## 3. Behavior contract

### Builder mode

- Operations: `Equals`, `Not Equals`, `Contains`, `Less Than`,
  `Greater Than`, `Less Than or Equal`, `Greater Than or Equal`,
  `In Between`.
- `Contains` is only for text columns; the UI hides it for non-text.
- Numeric comparisons convert the configured value to `float`; text/date
  comparisons keep it as a string and let Polars compare.
- `In Between` is inclusive and reorders `value`/`value2` for numeric columns.
- Incomplete configuration (no column, no value, or missing `value2` for
  `In Between`) must pass the input to True and an empty frame to False,
  matching the old codegen fallback. Do not return `None`.
- A configured column that disappeared -> `TD-SHAPE-003`.
- Unsupported operation -> `TD-SHAPE-004`.

### Expression mode

- Empty expression -> True = input, False = `input.head(0)`.
- Use DuckDB:
  - prepare the expression via the shared helper;
  - register the input frame under `df_filter`;
  - run `SELECT * FROM df_filter WHERE <expr>` and
    `SELECT * FROM df_filter WHERE NOT (<expr>)`;
  - materialise both while the connection is open, then `.lazy()` if the
    input was lazy (the old code documents why lazy streaming from a closed
    connection fails).
- A bad expression -> `ShapingError("TD-SHAPE-004", shortened_message)`.
  Keep the first line and strip `Binder Error:` / `Catalog Error:` /
  `Parser Error:` like `_shorten_error`.
- Do not add columns; this is a row filter only.

### Shared expression helper

Move these pure functions out of `qt/widgets/sql_formula_editor.py` into
`core/shaping/sql_expression.py`:

- `STRING_LITERAL_RE`
- `apply_outside_string_literals`
- `normalize_string_literals`
- `quote_identifier`
- `replace_column_names`
- `translate_in_between`
- `translate_function_aliases`
- `prepare_expression_sql`

Then have `sql_formula_editor.py` import/re-export them so existing UI imports
keep working. Do not duplicate regexes in `core/shaping/filter.py`.

## 4. Core extraction

Create `core/shaping/filter.py`:

```python
def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    frame = as_lazy(frames[0])
    s = {**DEFAULTS, **(settings or {})}
    if s["mode"] == "expression":
        return _expression_outputs(frame, str(s["expression"]))
    return _builder_outputs(frame, s)
```

`_builder_outputs`:

- schema = `schema_of(frame)`;
- require `s["column"]` in schema (unless empty -> fallback);
- build `pl.Expr` exactly as `update_data` lines 370-437;
- return `[frame.filter(expr), frame.filter(~expr)]`.

`_expression_outputs`:

- empty -> `[frame, frame.head(0)]`;
- prepare SQL, register, execute, collect; return lazy outputs.

`describe` is optional; return a warning chip for an incomplete builder or
empty expression so the user knows the node is passing rows through.

## 5. UI

The operation list depends on the selected column's dtype, and the expression
editor needs validation, so keep a custom `create_layout`; do not force this
into `FORM`.

Structure:

1. `SegmentedControl` for `Simple` / `Expression`, bound to `settings["mode"]`
   via `set_setting`.
2. Builder section (`ConfigSection("Condition")`), shown when mode is
   builder:
   - single-column `ColumnPicker` bound to `column`;
   - `NoWheelComboBox` for `operation`, repopulated from the live dtype;
   - value editor (`QLineEdit` or typed) bound to `value`;
   - second value editor for `In Between`, bound to `value2`;
   - `update_visibility` hides fields per operation.
3. Expression section (`ConfigSection("Expression")`), shown in expression
   mode:
   - `SQLFormulaWidget`; bind its text to `expression` with the existing
     300 ms debounce and `push_property_change` merge;
   - set available columns from `self.schema(0)`;
   - use `set_validate_callback` to call the core `prepare_expression_sql` +
     DuckDB `EXPLAIN` against a zero-row schema frame (no full collect);
   - keep `[column]` completion syntax.
4. Do not show both sections at once.

- All edits go through `set_setting`; do not mutate `self.column` etc.
- Keep the existing output labels `T`/`F`.
- The old `_apply_mode_visibility` becomes a `show_if`/visibility helper over
  settings.
- Use `NoWheelComboBox`, 30 px controls, no inline styles.

## 6. Content and node

- Replace the old state with settings. Delete `update_data`,
  `update_columns`, `_update_expression_data`, all `on_*_changed` handlers,
  `history_stamp_callback`, old `get_code`/`serialize`/`deserialize`.
- `validate_expression` stays as a thin UI method calling the core helper.
- Set `self.output_variables = [f"var_t_filter_{self.id}",
  f"var_f_filter_{self.id}"]` to keep old generated names.
- Keep the node class name, enum, icon, title and registry entry.
- No upstream rename following is needed (Filter does not rename).

## 7. Legacy loader

Old content serialized the six keys at the top level. Map them with the
defaults above; normalize unknown mode to builder and unknown operation to
`Equals`.

```python
def _legacy_settings(self, data):
    mode = str(data.get("mode") or "builder")
    if mode not in ("builder", "expression"):
        mode = "builder"
    return {
        "mode": mode,
        "column": str(data.get("column") or ""),
        "operation": str(data.get("operation") or "Equals"),
        "value": "" if data.get("value") is None else str(data.get("value")),
        "value2": "" if data.get("value2") is None else str(data.get("value2")),
        "expression": str(data.get("expression") or ""),
    }
```

Test with `savedfiles/6. in-filter-out.json` and its false-output golden.

## 8. Tests

`tests/unit/test_filter_core.py`:

- each builder operation on text/numeric/date-ish data;
- incomplete builder passes through / empty false;
- missing column -> `TD-SHAPE-003`;
- `In Between` inclusive and numeric reorder;
- expression empty -> pass-through / empty;
- expression equals/not equals, `[column]` syntax, `in_between` alias,
  function aliases, quoted identifiers and string literals;
- bad expression -> `TD-SHAPE-004`;
- lazy input stays lazy in both modes;
- both outputs partition the input for a valid expression.

`tests/ui/test_filter_dock.py`:

- builder/expression switch preserves settings and shows the right section;
- operation list changes with column dtype;
- value2 visibility for `In Between`;
- undo/redo for mode, column, operation, value, expression;
- expression validation errors appear in the editor;
- generated code equals live for builder and expression.

Update `tests/ui/test_filter_expression.py` to the new settings path.
Keep the saved Filter goldens unchanged.

## 9. Steps

1. Create `core/shaping/sql_expression.py`; move the pure helpers and update
   the Qt module imports/re-exports.
2. Add `core/shaping/filter.py` + core tests.
3. Rebuild `FilterContent` on `ShapingContent` with a custom layout and
   settings-backed widgets + loader.
4. Replace node with `ShapingNode`; keep output names.
5. Run focused tests, Filter goldens, then all e2e.
6. Commit as `refactor: move Filter onto the shaping execution system`.

## 10. Acceptance

- [ ] Builder and expression modes both use the same core runner from live
      and generated code.
- [ ] Both outputs are correct and lazy when the input is lazy.
- [ ] Incomplete configuration passes rows through instead of invalidating.
- [ ] Old saved state loads.
- [ ] Expression validation still works in the editor.

## 11. Do not

- Do not change the operation names (`Equals`, `In Between`, etc.).
- Do not import Qt from `core/shaping/filter.py`.
- Do not duplicate `STRING_LITERAL_RE` or alias translation.
- Do not use `SELECT * EXCLUDE` or add helper columns.
