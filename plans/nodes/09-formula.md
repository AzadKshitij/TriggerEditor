# Formula - modernization plan

Status: not started.
Implementation order: 13 of 18 (Tier 3, arbitrary expressions).
Read first: `plans/nodes/README.md`.

## 1. Current implementation

- File: `src/trigger_designer/qt/widgets/nodes/Preparation/formula.py`
  (1,417 lines; the largest single-input node).
- Content: `FormulaContent` (line 190), plus `_FormulaCard` and `_ResizeGrip`.
- Node: `TriggerNode_Formula` (line 1353).
- Inputs: one. Outputs: one.
- Settings today: `formula_sections`, a list of
  `{"target_column", "formula_text", "editor_height", "target_dtype"}`.
- Defaults: one empty section; `editor_height=120`; max sections enforced
  by `MAX_FORMULA_SECTIONS`; `target_dtype` must be in `DTYPE_OPTIONS[1:]`.
- Old execution: `_run_sections` builds one DuckDB query with one CTE per
  configured section; on a combined-query failure it falls back to
  `_run_sections_sequential` for per-section error attribution. Results are
  normalized through `normalize_to_supported_dtypes`.
- Old UI: collapsible formula cards with target column, target dtype, SQL
  editor, resize grip, add/remove; completion/validation from
  `SQLFormulaWidget`.
- Old codegen: registers input and executes the same combined query.
- Existing tests: `tests/ui/test_formula_node.py`,
  `tests/ui/test_formula_focus.py`, `tests/ui/test_formula_editor_loop.py`;
  saved workflow `savedfiles/3. in-formula-out.json`.
- NOTE: the full `tests/ui` suite has a pre-existing Formula-editor teardown
  abort. Run targeted Formula tests only until that is fixed.

## 2. Target

- Core: `src/trigger_designer/core/shaping/formula.py`.
- Reuse `core/shaping/sql_expression.py` (created by Filter) for the pure
  `[column]` / string-literal / alias parsing helpers.
- Content: `FormulaContent(ShapingContent)` with a custom card layout.
- Node: `TriggerNode_Formula(ShapingNode)`.
- Settings: `sections`.
- Output kind: `("formula",)`.
- `INPUTS = 1`; `HISTORY = "Formula"`;
  `SUMMARY = "calculated columns"`.

### Settings schema

```python
DEFAULTS = {
    "sections": [
        {
            "target_column": "",
            "formula_text": "",
            "editor_height": 120,
            "target_dtype": "",
        }
    ],
}
```

`editor_height` is UI state but stays in settings so card sizes survive.
Core ignores it.

## 3. Behavior contract

- A section is configured only when both `target_column` and `formula_text`
  are non-empty after stripping.
- Sections run in list order; each later section can reference columns
  created by earlier sections.
- Existing target column -> `SELECT * REPLACE (<expr> AS "target") FROM ...`
  (keeps the column's original ordinal position).
- New target column -> `SELECT *, <expr> AS "target" FROM ...`; if
  `target_dtype` is set, wrap the expression in
  `CAST(<expr> AS <duckdb type>)`.
- `formula_text` uses `[column]` syntax, converted to a quoted SQL identifier;
  string literals and function aliases use the same normalizer as Filter.
- Empty target/formula sections are ignored, not errors.
- A section SQL error:
  - live: expose the first failing section index and a shortened message;
  - core: raise `ShapingError("TD-SHAPE-004", "Section N: <message>")`.
- On a combined-query failure, fall back to the sequential path so the
  failing section is identified (preserve current behavior).
- Normalize the final frame with `normalize_to_supported_dtypes`.
- Keep all configured sections' output columns in order.
- Return a LazyFrame; collect/materialize inside the runner because DuckDB
  returns a DataFrame, then `.lazy()`.
- Output variable: `var_formula_<id>`.

## 4. Core extraction

Create `core/shaping/formula.py` and move these pure pieces:

- `DEFAULT_SECTION`, `MAX_FORMULA_SECTIONS`, `DTYPE_OPTIONS`,
  `DTYPE_TO_DUCKDB`;
- `_normalize_sections` logic (as `normalize(settings)`);
- `_quote_identifier`, `_prepare_formula_for_sql` (using the shared
  `sql_expression` helpers);
- `_section_query`, `_build_combined_query`;
- `_run_sections` and `_run_sections_sequential` without Qt/logger widgets.

Exact signatures:

```python
DEFAULTS = {"sections": [DEFAULT_SECTION]}

def normalize(settings: dict) -> dict: ...
def section_query(section, available_columns, relation_name) -> tuple[str, list[str]]: ...
def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]: ...
```

`run_node`:

1. `frame = as_lazy(frames[0])`; `available = list(schema_of(frame))`.
2. `configured = [(i, s) for i, s in enumerate(normalize(settings)["sections"])
   if s["target_column"].strip() and s["formula_text"].strip()]`.
3. If none -> `[frame]`.
4. Build the combined query; register `df_for_duck`; execute; on failure use
   the sequential path and raise `TD-SHAPE-004` with the section index.
5. `normalize_to_supported_dtypes(result).lazy()`.

Do not import `QWidget`, `SQLFormulaWidget` or `logger` into core.
The `SQLFormulaWidget` validation callback can call a core `validate_section`
helper that runs `EXPLAIN` on a zero-row schema frame.

## 5. UI

Keep the existing card editor; do not replace it with a plain textarea.

- `_FormulaCard` / `_ResizeGrip` stay in the node module.
- `create_layout`:
  - toolbar: add-section `IconButton` with tooltip/accessibility, section
    count;
  - one card per `settings["sections"]`;
  - each card: target column combo (existing columns + "new column"
    prompt), target dtype combo, `SQLFormulaWidget`, remove button, resize
    grip;
  - `SQLFormulaWidget._undo_composite = True`;
  - set available columns and validation callback from the live schema;
  - `editor_height` persists on resize (debounced).
- All control writes go through `set_setting("sections", new_sections, ...)`:
  - add/remove = `push_list_change` (size change, card rebuild);
  - text/height edits = `push_property_change` with a per-section merge key;
  - target/dtype changes = property change, no merge.
- Do not use the old `_sync_sections_from_widgets` to mutate model on every
  format call; build a `_sections_from_widgets()` snapshot only at commit
  points.
- The `FormulaContent` still needs `last_error`/`section_errors` as UI state,
  not settings.
- Follow the design system for card headers, 30 px controls, icon buttons and
  hover states; reuse `FormulaCard*` QSS object names.

## 6. Content and node

- Keep the card/widget code and completion/validation methods; rebase the
  model on settings.
- Delete `formula_sections`, old `_sync_sections_from_widgets` mutation of
  state, `store_history`, `history_stamp_callback`, custom `get_code`,
  `serialize`/`deserialize` (loader replaces).
- Set `self.output_variables = [f"var_formula_{self.id}"]`.
- `TriggerNode_Formula(ShapingNode)`; keep class/title/icon/enum/registry.
- No upstream rename following is needed.

## 7. Legacy loader

Old saved key: `formula_sections` (and possibly `sections`). Map to
`settings["sections"]` via `core.normalize`:

```python
def _legacy_settings(self, data):
    sections = data.get("formula_sections", data.get("sections", []))
    return core.normalize({"sections": sections})

def deserialize(self, data, hashmap={}):  # noqa: B006
    if "settings" not in data and (
        "formula_sections" in data or "sections" in data
    ):
        data = dict(data)
        data["settings"] = self._legacy_settings(data)
    return super().deserialize(data, hashmap)
```

Test with `savedfiles/3. in-formula-out.json` and its golden.

## 8. Tests

`tests/unit/test_formula_core.py`:

- one section creates a column; one overwrites in place;
- multiple sections chain, later references earlier target;
- target dtype CAST;
- empty sections ignored;
- `[column]` quoting, string literals, aliases;
- invalid SQL -> `TD-SHAPE-004` with `Section N`;
- combined-query fallback identifies the failing section;
- dtype normalization;
- lazy input -> lazy output;
- live == generated code.

`tests/ui/test_formula_dock.py` (new, targeted):

- cards build from settings; add/remove/resize;
- target/dtype/text edits update output;
- undo/redo for add/remove and text burst;
- completion/validation still uses the live schema;
- serialization round-trip;
- generated code equals live.

Keep `test_formula_node`, `test_formula_focus`, `test_formula_editor_loop`
green. Do not run the whole `tests/ui` directory until the teardown bug is
fixed.

## 9. Steps

1. Add `core/shaping/formula.py` by moving `_section_query`,
   `_build_combined_query`, `_run_sections*` and pure helpers; add tests.
2. Rebase `FormulaContent` on `ShapingContent`; settings-backed cards; loader.
3. Replace node with `ShapingNode`.
4. Remove old model fields/undo/codegen.
5. Run focused Formula tests + formula golden.
6. Commit as `refactor: move Formula onto the shaping execution system`.

## 10. Acceptance

- [ ] All formula behavior is in core; the UI only edits settings.
- [ ] Existing target columns are replaced in place; new columns append.
- [ ] Section errors name the right section.
- [ ] Live == generated output.
- [ ] Old saved formulas load.

## 11. Do not

- Do not rewrite the SQL editor or completion in this migration.
- Do not move DuckDB types into Qt code.
- Do not execute one query per section on the normal path; preserve the CTE
  chain and the sequential fallback.
