# Normalize - modernization plan

Status: not started.
Implementation order: 7 of 18 (Tier 1, rename columns).
Read first: `plans/nodes/README.md`.

## 1. Current implementation

- File: `src/trigger_designer/qt/widgets/nodes/Preparation/normalize_columns.py`.
- Content: `NormalizeColumnsContent` (line 106).
- Node: `TriggerNode_NormalizeColumns` (line 433).
- Inputs: one. Outputs: one.
- Settings today:
  - `trim_whitespace` (default `True`)
  - `spaces_to_underscore` (default `True`)
  - `remove_all_whitespace` (default `False`)
  - `case_modification` (`none`, `lower`, `upper`, `title`)
  - `selected_columns`
- Pure helpers currently live in the node module:
  `normalize_column_name` (line 55) and `build_rename_mapping` (line 79).
- Old execution: `_current_mapping()` builds a rename map from the live schema
  and rules; `update_data()` renames and rejects duplicate output names.
- Old UI: rules section (trim, spaces/underscore, remove all, case) and a
  searchable column checklist with All/None.
- Old codegen: `get_code` emits a rename map and `df.rename(mapping)`.
- Existing test: `tests/unit/test_normalize_columns.py` imports
  `build_rename_mapping` from the node module.
- Saved workflow: none dedicated, but the node is in the all-node workflow.

## 2. Target

- Core: `src/trigger_designer/core/shaping/normalize.py`.
- Content: `NormalizeContent(ShapingContent)`.
- Node: `TriggerNode_Normalize(ShapingNode)` (or keep the old class name for
  the registry; prefer the shorter content name).
- Settings:
  - `trim_whitespace`
  - `spaces_to_underscore`
  - `remove_all_whitespace`
  - `case_modification`
  - `selected_columns`
- Output kind: `("normalize",)`.
- `INPUTS = 1`; `HISTORY = "Normalize"`;
  `SUMMARY = "column name rules"`.

### Settings schema

```python
DEFAULTS = {
    "trim_whitespace": True,
    "spaces_to_underscore": True,
    "remove_all_whitespace": False,
    "case_modification": "none",
    "selected_columns": [],
}
```

## 3. Behavior contract

- Rules apply in this fixed order, exactly as today:
  1. trim leading/trailing whitespace (when enabled),
  2. remove all whitespace (takes precedence over underscore), else replace
     runs of whitespace with `_`,
  3. case conversion (`lower`, `upper`, `title`).
- An empty result keeps the original column name (`return result or name`).
- `selected_columns` limits the scope; empty selection means **all** columns
  (old behavior; the old `_field_selection_initialized` flag is UI state, not
  a saved rule). If an upstream column disappears, it is ignored.
- If two columns normalize to the same final name, raise
  `ShapingError("TD-SHAPE-002", "Rules produce duplicate column name '<name>'")`.
  The old node set `data=None` and an invalid tooltip; the modern error is
  clearer and should be translated by the normal error path.
- Only changed names go into the rename map (`mapping[old] = new`).
- Preserve column order and dtypes; rename only.
- Return a LazyFrame.
- Downstream rename propagation must keep working: `upstream_rename_map`
  looks for `content._current_mapping()`. Provide it as a pure function of
  settings + live schema on the new content.

## 4. Core extraction

Move `normalize_column_name` and `build_rename_mapping` from the node module
into `core/shaping/normalize.py` unchanged. Add:

```python
DEFAULTS = {
    "trim_whitespace": True,
    "spaces_to_underscore": True,
    "remove_all_whitespace": False,
    "case_modification": "none",
    "selected_columns": [],
}


def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    frame = as_lazy(frames[0])
    schema = schema_of(frame)
    columns = list(schema)
    selected = [
        name for name in (settings or {}).get("selected_columns") or []
        if name in schema
    ]
    mapping = build_rename_mapping(
        columns,
        selected,
        trim_whitespace=bool(settings.get("trim_whitespace", True)),
        spaces_to_underscore=bool(settings.get("spaces_to_underscore", True)),
        remove_all_whitespace=bool(settings.get("remove_all_whitespace", False)),
        case_modification=str(settings.get("case_modification", "none")),
    )
    final_names = [mapping.get(name, name) for name in columns]
    duplicates = {name for name in final_names if final_names.count(name) > 1}
    if duplicates:
        raise ShapingError("TD-SHAPE-002", f"Rules produce duplicate column name '{sorted(duplicates)[0]}'")
    return [frame.rename(mapping) if mapping else frame]
```

- Keep `CASE_OPTIONS`/display maps in the Qt module; core stores only the
  model strings.
- Update `tests/unit/test_normalize_columns.py` imports to
  `from trigger_designer.core.shaping.normalize import build_rename_mapping`.
- Do not leave a duplicate `build_rename_mapping` in the node module.

## 5. UI

Use the standard form, not the old custom checklist:

```python
FORM = (
    FormSection(
        "Name rules",
        (
            Field("trim_whitespace", "Trim spaces", "check"),
            Field("spaces_to_underscore", "Spaces to underscores", "check"),
            Field("remove_all_whitespace", "Remove all whitespace", "check"),
            Field(
                "case_modification",
                "Case",
                "combo",
                options=(
                    ("none", "None"),
                    ("lower", "Lower Case"),
                    ("upper", "Upper Case"),
                    ("title", "Title Case"),
                ),
            ),
        ),
        info="Applied in order: trim, whitespace, case.",
    ),
    FormSection(
        "Columns",
        (
            Field(
                "selected_columns",
                "Normalize",
                "columns",
                hint="Empty means every column.",
            ),
        ),
    ),
)
```

- Use `show_if` so "Remove all whitespace" and "Spaces to underscores" do not
  both look active at once if the design system supports it; if not, leave
  both visible with a hint that remove-all wins.
- ColumnPicker supplies search and All/None.
- The old `field_checkboxes`, `columns_list`, and `_field_selection_initialized`
  are removed. Empty selection means all; do not persist the old
  "initialized" flag.

## 6. Content and node

```python
class NormalizeContent(ShapingContent):
    SETTINGS = core.DEFAULTS
    MODULE = "trigger_designer.core.shaping.normalize"
    OUTPUT_KINDS = ("normalize",)
    INPUTS = 1
    HISTORY = "Normalize"
    SUMMARY = "column name rules"
    FORM = ...

    def _current_mapping(self) -> dict:
        return core.build_rename_mapping(
            list(self.schema(0)),
            list(self.settings.get("selected_columns") or []),
            trim_whitespace=bool(self.settings.get("trim_whitespace", True)),
            spaces_to_underscore=bool(self.settings.get("spaces_to_underscore", True)),
            remove_all_whitespace=bool(self.settings.get("remove_all_whitespace", False)),
            case_modification=str(self.settings.get("case_modification", "none")),
        )
```

- `_current_mapping` is a live projection, not old state; it is the hook
  `upstream_rename_map` already uses.
- Delete `update_data`, `on_trim_changed`, `on_underscore_changed`,
  `on_remove_all_changed`, `on_case_changed`, `on_columns_changed`,
  `update_selected_columns`, `_normalize_selected_columns`, old
  `get_code`/`serialize`/`deserialize` (loader replaces deserialize).
- Keep the node enum, icon, title and registry entry.

## 7. Legacy loader

The old content serialized the settings at the top level (via
`serialize_content_state`). Map only known keys:

```python
def _legacy_settings(self, data):
    return {
        "trim_whitespace": bool(data.get("trim_whitespace", True)),
        "spaces_to_underscore": bool(data.get("spaces_to_underscore", True)),
        "remove_all_whitespace": bool(data.get("remove_all_whitespace", False)),
        "case_modification": str(data.get("case_modification", "none")),
        "selected_columns": [str(name) for name in data.get("selected_columns") or []],
    }

def deserialize(self, data, hashmap={}):  # noqa: B006
    if "settings" not in data and any(
        key in data for key in ("trim_whitespace", "case_modification", "selected_columns")
    ):
        data = dict(data)
        data["settings"] = self._legacy_settings(data)
    return super().deserialize(data, hashmap)
```

## 8. Tests

`tests/unit/test_normalize_core.py`:

- default rules trim and underscore;
- remove-all-whitespace wins over underscores;
- lower/upper/title;
- empty selected columns means all;
- selected subset only;
- unchanged names are absent from the map;
- duplicate final names raise `TD-SHAPE-002`;
- empty normalized name keeps the original;
- lazy frame stays lazy.

Update `tests/unit/test_normalize_columns.py` to import the moved helpers and
keep its existing behavior cases.

`tests/ui/test_normalize_dock.py`:

- dock shows rule controls and columns;
- toggling each rule changes the output schema;
- column selection limits renames;
- undo/redo restores rules and columns;
- generated code equals live;
- downstream Select follows a rename via `upstream_rename_map`.

## 9. Steps

1. Move helpers to core, add runner + tests.
2. Replace content with form + `_current_mapping` + loader.
3. Replace node with `ShapingNode`.
4. Remove old widget code and imports.
5. Run focused tests, all-node e2e, and the Select rename test.
6. Commit as `refactor: move Normalize onto the shaping execution system`.

## 10. Acceptance

- [ ] No duplicate `build_rename_mapping` implementation remains.
- [ ] Empty selection still means all columns.
- [ ] Duplicate names produce a real `TD-SHAPE-002` error.
- [ ] Downstream rename propagation still works.
- [ ] Old saved state loads.

## 11. Do not

- Do not change the rule order.
- Do not treat an empty selection as "no columns".
- Do not add a preview table; renaming is visible in the output/preview.
