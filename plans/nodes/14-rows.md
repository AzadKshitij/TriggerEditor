# Rows - modernization plan

Status: implemented.
Implementation order: 11 of 18 (Tier 2, generates rows).
Read first: `plans/nodes/README.md`.

## 1. Current implementation

- File: `src/trigger_designer/qt/widgets/nodes/Preparation/dynamic_row_builder.py`.
- Content: `DynamicRowBuilderContent` (line 30).
- Node: `TriggerNode_DynamicRowBuilder` (line 484). Title is **Rows**.
- Inputs: one (required in the current node). Outputs: one.
- Settings today:
  - `field_name` (default `counter`)
  - `field_type` (`int`, `float`, `string`, `datetime`)
  - `initial_value`, `increment_value`, `max_value`
- Old execution: generate values until `current > max` for numeric/datetime,
  or until the 10,000 cap for strings; build a one-column frame and
  horizontally concat it with the input.
- String increment is concatenation (`"A"` + `"1"`);
  datetime increment is `timedelta(seconds=increment)`.
- Old UI: field name, type combo, and three type-specific editors
  (`QSpinBox`, `QDoubleSpinBox`, `QLineEdit`, `QDateTimeEdit`).
- Old codegen: emits the same loop with Python literals.
- Existing tests: none dedicated; saved workflow
  `savedfiles/12. generate_rows.tds`.
- Saved workflow: `savedfiles/12. generate_rows.tds`.

## 2. Target

- Core: `src/trigger_designer/core/shaping/rows.py`.
- Content: `RowsContent(ShapingContent)` with a custom `create_layout`.
- Node: `TriggerNode_Rows(ShapingNode)`; keep title `"Rows"`.
- Settings: the five keys above.
- Output kind: `("rows",)`.
- `INPUTS = 1`; `HISTORY = "Rows"`;
  `SUMMARY = "generated rows"`.

### Settings schema

```python
DEFAULTS = {
    "field_name": "counter",
    "field_type": "int",
    "initial_value": 1,
    "increment_value": 1,
    "max_value": 10,
}
```

Datetime values are ISO-8601 strings in settings
(`initial_value="2024-01-01T00:00:00"`), because settings must be JSON-safe.
The content converts to/from `datetime` for the editor.

## 3. Behavior contract

- `field_name` must be non-empty; otherwise `TD-SHAPE-001`.
- `field_type` must be one of `int`, `float`, `string`, `datetime`;
  otherwise `TD-SHAPE-004`.
- Numeric loop: include `initial_value`; stop when `current > max_value`;
  increment by `increment_value`. A zero/negative increment can loop until
  the cap; preserve that and emit a warning when the cap is hit.
- String loop: ignore `max_value`; append `increment_value` each time; stop
  at `MAX_ITERATIONS = 10000`.
- Datetime loop: `max_value` is the inclusive upper bound; `increment_value`
  is **seconds** added with `timedelta(seconds=...)`.
- When the input frame exists, horizontally concatenate the generated column
  to it. Preserve Polars horizontal-concat behavior; do not pad/truncate.
- When the input is empty/None, produce a new one-column frame. Although the
  current node requires one connection, the core must still handle `frames[0]
  is None` for unit tests and future optional-input work.
- Return a LazyFrame. The generated one-column frame can be built eagerly,
  then `.lazy()`.
- Output variable: keep `var_genrows_<id>`.

## 4. Core extraction

Create `core/shaping/rows.py`:

```python
MAX_ITERATIONS = 10000
DEFAULTS = {...}


def _typed(value, field_type):
    if field_type == "int":
        return int(value)
    if field_type == "float":
        return float(value)
    if field_type == "datetime":
        return value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    return str(value)


def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    s = {**DEFAULTS, **(settings or {})}
    field_type = s["field_type"]
    if field_type not in ("int", "float", "string", "datetime"):
        raise ShapingError("TD-SHAPE-004", f"Unknown field type '{field_type}'")
    name = str(s["field_name"]).strip()
    if not name:
        raise ShapingError("TD-SHAPE-001", "Field name is empty")
    current = _typed(s["initial_value"], field_type)
    increment = _typed(s["increment_value"], field_type)
    maximum = _typed(s["max_value"], field_type)
    values = []
    for _ in range(MAX_ITERATIONS):
        if field_type in ("int", "float", "datetime") and current > maximum:
            break
        values.append(current)
        if field_type == "datetime":
            current = current + timedelta(seconds=float(increment))
        elif field_type in ("int", "float"):
            current = current + increment
        else:
            current = f"{current}{increment}"
    generated = pl.DataFrame({name: values}).lazy()
    if frames and frames[0] is not None:
        return [pl.concat([as_lazy(frames[0]), generated], how="horizontal")]
    return [generated]
```

- Add `describe` returning `("Reached 10,000 rows", "warning")` when the loop
  hit the cap.
- Do not use the old widget methods `get_typed_value`/`should_stop`; they read
  widgets. The core version must be pure.

## 5. UI

Keep a custom layout because the three value editors change with
`field_type`. Do not force `QDateTimeEdit` into a generic text field.

Structure:

1. `ConfigSection("Column")`
   - `QLineEdit` for `field_name`, 300 ms debounce, bound via
     `push_property_change` with a merge key.
   - `NoWheelComboBox` for `field_type` with
     `int/float/string/datetime` values and readable labels.
2. `ConfigSection("Values")`
   - Initial, Increment, Maximum editors:
     - int -> `QSpinBox` (wide range, e.g. -1e9..1e9)
     - float -> `QDoubleSpinBox`
     - string -> `QLineEdit`
     - datetime -> `QDateTimeEdit` (calendar popup; ISO string in settings)
   - Rebuild these three widgets when `field_type` changes. Because the
     widgets are structural, call `self._rebuild_widgets()` after the
     `field_type` setting change.
   - Hide `Maximum` for string (it is ignored); show a hint that only the
     10,000 cap applies.
3. A warning label/chip when the cap is reached.

- Every editor writes its typed value into settings; datetime writes
  `.toPython().isoformat()`.
- Do not keep `initial_widget`, `increment_widget`, `max_widget` as model
  state; they are widgets only.
- Use the design-system 30 px control height and no inline styles.

## 6. Content and node

- Delete `process_data`, `create_value_widget`, `_restore_widget_value`,
  `get_typed_value`, `should_stop`, `_increment_value`,
  `_increment_statement`, `_render_literal`, `get_increment_code`,
  `_serialize_value`, old `serialize`/`deserialize`, and custom `get_code`.
- Keep `MAX_ITERATIONS` only in core; the content may import it for the
  warning text.
- Keep the title `Rows` (not `Dynamic Row Builder`); the old class name may be
  renamed to `TriggerNode_Rows` but the registry entry/title must not change.
- No upstream rename following is needed.

## 7. Legacy loader

Old content serialized `field_name`, `field_type`, `initial_value`,
`increment_value`, `max_value` at the top level. Datetimes may already be ISO
strings. Normalize numbers by the declared type:

```python
def _legacy_settings(self, data):
    field_type = str(data.get("field_type") or "int")
    if field_type not in ("int", "float", "string", "datetime"):
        field_type = "int"
    def value(key, default):
        raw = data.get(key, default)
        if field_type == "int":
            return int(raw)
        if field_type == "float":
            return float(raw)
        return "" if raw is None else str(raw)
    return {
        "field_name": str(data.get("field_name") or "counter"),
        "field_type": field_type,
        "initial_value": value("initial_value", 1),
        "increment_value": value("increment_value", 1),
        "max_value": value("max_value", 10),
    }
```

Test with `savedfiles/12. generate_rows.tds`.

## 8. Tests

`tests/unit/test_rows_core.py`:

- int range 1..5 -> 5 rows;
- float range with fractional increment;
- string concatenation and 10,000 cap;
- datetime range using seconds;
- zero/negative increment hits the cap and warns;
- empty field name -> `TD-SHAPE-001`;
- invalid field type -> `TD-SHAPE-004`;
- horizontal concat with an input frame;
- no input -> standalone frame;
- output is lazy;
- generated code == live.

`tests/ui/test_rows_dock.py`:

- dock builds; changing type rebuilds the three value editors;
- changing each value updates output;
- maximum hides for string;
- undo/redo restores values and type;
- serialization round-trip;
- generated code equals live.

Run the saved Rows workflow and the all-node e2e.

## 9. Steps

1. Add core + tests.
2. Rebuild content on `ShapingContent` with custom layout + loader.
3. Replace node with `ShapingNode`; keep title/icon/enum.
4. Remove old widget/loop/codegen code and imports.
5. Run focused tests, Rows saved workflow, all-node e2e.
6. Commit as `refactor: move Rows onto the shaping execution system`.

## 10. Acceptance

- [x] Loop semantics match the old node for all four types.
- [x] Datetime values round-trip as ISO strings.
- [x] The 10,000 cap still protects the UI.
- [x] Checked-in sample workflows were migrated to the new `settings` schema;
      no legacy loader is kept (project decision: no backward compatibility).
- [x] Live == generated output.

## 11. Do not

- Do not make `max_value` stop strings.
- Do not change datetime increment from seconds to days.
- Do not let the generated-code loop use a different cap than live.
