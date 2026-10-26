# File Input - modernization plan

Status: not started.
Implementation order: 18 of 18 (Tier 5, source + filesystem read).
Read first: `plans/nodes/README.md`.

This is the largest and riskiest node. Do it last. Do not rewrite the file
pickers or the source readers in one pass; the readers are already Qt-free and
tested. Migrate them behind a thin settings/core boundary, then remove the old
runtime fields.

## 1. Current implementation

- File: `src/trigger_designer/qt/widgets/nodes/InOut/file_input.py`
  (1,800+ lines).
- Content: `FileInputContent` (line 87).
- Node: `TriggerNode_FileInput` (line 1786), `inputs=[]`, `outputs=[3]`.
- Settings today (top-level content fields):
  - `filePath`, `filePathRel`, `file_type`
  - `record_limit`, `output_filename_as_field`, `delimiter`,
    `first_row_contains_field_names`, `selected_sheet`,
    `available_sheets`, `start_row`
  - `schema_snapshot`, `file_metadata`, `input_schema_version`
  - `file_name_column_name`, `file_name_value`
  - `include_patterns`, `exclude_patterns`, `recursive`, `file_order`
  - `schema_mismatch`, `on_file_error`, `max_files`
  - `encoding`, `read_as_text`, `json_nested`
  - `sheet_mode`, `selected_sheets`, `add_sheet_name_column`,
    `sheet_name_column_name`
  - `db_mode`, `db_table`, `db_query`
- UI: file/folder picker, file type, record limit, filename column, include/
  exclude patterns, recursion, file order, schema mismatch, error policy,
  encoding, JSON nesting, Excel sheet mode/columns, database mode/table/query,
  schema preview and report metadata.
- Core reader already exists: `src/trigger_designer/core/input_source.py`:
  - `SOURCE_KEYS`, `SOURCE_DEFAULTS`;
  - `SourceSettings.from_state`;
  - `build_source(state) -> SourceResult(frame, report)`;
  - `SourceSettings`, `SourceReport`, `FileReport`.
- Old live path: `_load_via_builder()` calls `build_source` and stores
  `data`, `last_report`, `schema_snapshot`, `file_metadata`.
- Old codegen: `get_code` resolves paths and emits a `build_source` call.
- Tests: `tests/unit/test_file_input_codegen.py`,
  `test_file_input_legacy.py`, `test_file_input_state.py`,
  `test_file_input_validate.py`, `test_input_source_*`,
  `tests/e2e/test_input_types_e2e.py`, all-node e2e.
- Saved workflows: `savedfiles/0.*`, `Input Types Test.tds`, `I_select.tds`,
  and the all-node sample.

## 2. Target

- Core: `src/trigger_designer/core/shaping/file_input.py` (thin wrapper over
  `core/input_source.py`; do not move the readers).
- Content: `FileInputContent(ShapingContent)` with a custom source layout.
- Node: `TriggerNode_FileInput(ShapingNode)` with `INPUTS = 0` and one output.
- Settings: all source keys from `SOURCE_DEFAULTS` plus path/metadata keys
  needed for persistence.
- Output kind: `("file",)`.
- `HISTORY = "File Input"`; `SUMMARY = "source"`.

### Settings schema

```python
from trigger_designer.core.input_source import SOURCE_DEFAULTS

DEFAULTS = {
    **SOURCE_DEFAULTS,
    "filePathRel": "",
    "input_schema_version": 2,
    "schema_snapshot": [],
    "file_metadata": {},
}
```

- `SOURCE_KEYS` remains the execution contract; `filePathRel`,
  `input_schema_version`, `schema_snapshot`, `file_metadata` are persistence/
  UI metadata and are ignored by `SourceSettings.from_state`.
- `DEFAULT_EXCLUDE`/tuples from `SOURCE_DEFAULTS` are JSON-serialized as
  lists by the generic content serializer; `from_state` accepts both.

## 3. Behavior contract

- Execution is exactly `build_source(settings)`. Do not reimplement CSV,
  Excel, Parquet, JSON, NDJSON, SQLite or DuckDB reading.
- `build_source` already:
  - lists files/folders/patterns in order;
  - applies include/exclude/recursion/max_files;
  - unions schemas with missing columns as nulls and extra columns last;
  - resolves dtype conflicts deterministically;
  - adds filename/sheet columns;
  - applies JSON nesting/text and record limit.
- Preserve all source modes and their defaults. Do not change
  `SOURCE_DEFAULTS` without updating `core/input_source` tests.
- Relative paths: keep the current `filePath` + `filePathRel` behavior. Save
  both; resolve `filePathRel` against the workflow directory on load. Core
  receives the resolved absolute `filePath`.
- `schema_snapshot`/`file_metadata` are advisory UI state. They must not
  affect execution.
- Empty path / unreadable file / bad config: preserve the existing
  `InputReadError` and its `TD-IN-*` codes. Do not collapse every error into
  `TD-SHAPE-004`. If the base `ShapingNode` only catches `ShapingError`, add
  a narrow adapter in `run_node` that re-raises a `ShapingError` carrying the
  original message only as a last resort; first verify `translate_exception`
  handles `InputReadError` via its `.code` (the error catalogue has TD-IN
  rules). Record the chosen behavior in the commit.
- File Input is a source: no input frames. `frames` is an empty list and
  `run_node([], settings)` returns one frame.
- Output variable: `var_file_input_<id>`.

## 4. Core wrapper

Create `core/shaping/file_input.py`:

```python
from trigger_designer.core.input_source import SOURCE_DEFAULTS, build_source

DEFAULTS = {**SOURCE_DEFAULTS, ...}


def read_source(settings: dict):
    return build_source(settings)


def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    result = build_source(settings)
    return [result.frame.lazy() if isinstance(result.frame, pl.DataFrame) else result.frame]
```

- `run_node` ignores `frames` (source node).
- Add `describe` only if it can use an already-produced report; do not read
  the files a second time just for a chip.
- `read_source` is for the live content that needs `result.report` for the
  dock; generated code uses `run_node`.
- Add tests for the wrapper before touching the content.

## 5. UI

Keep the current source UI. Do not rebuild the file pickers or schema
preview in this migration.

Target structure (same sections, settings-backed):

1. **Source** - file/folder picker, `file_type`, path edit, record limit,
   delimiter, header row, start row, encoding, read-as-text, JSON nesting.
2. **Files** - include/exclude patterns, recursive, file order, max files,
   filename column/value, schema mismatch, on-file-error.
3. **Excel** - sheet mode, selected sheets, sheet-name column.
4. **Database** - db mode, table list, query editor, table refresh.
5. **Schema/report** - read-only schema snapshot and report summary.

Implementation rules:

- Keep the existing widget-building methods and file dialogs; replace every
  `self.<setting>` read/write with `self.settings[...]` through
  `set_setting`.
- Timers: path/include/exclude/filename/delimiter/sheet/query debounces stay
  UI timers; their callbacks call `set_setting` with merge keys. Do not
  mutate settings directly.
- A read/reload action calls `content.compute()` (or `read_source`) and
  updates `last_report`, `schema_snapshot`, `file_metadata` as UI state.
- Path changes must not read the file on every keystroke; preserve the
  existing debounce.
- Validate before Run: keep `validate_loaded_state` but read settings.
- `_sync_widgets_from_model` / `_rebuild_widgets` must project settings onto
  widgets; they must not record history.
- Do not add inline styles; use current object names/QSS. Keep 30 px
  controls and the current section layout.
- The output should be displayed as a normal node preview; no table rewrite.

## 6. Content and node

- `FileInputContent(ShapingContent)`:
  - `SETTINGS = core.DEFAULTS`, `MODULE`, `OUTPUT_KINDS=("file",)`,
    `INPUTS=0`, `HISTORY`, `SUMMARY`.
  - custom `create_layout`; no `FORM` needed.
  - `compute()`:
    - call `core.read_source(self.settings)`;
    - set `self.last_report`/`last_error`;
    - set `self.outputs = [result.frame.lazy()]`;
    - return outputs.
  - `get_code` inherited from `ShapingContent` (it emits `run_node([], settings)`).
  - `serialize` override only to convert `filePath` to absolute + relative
    (the generic serializer handles settings otherwise).
  - `deserialize` loader resolves `filePathRel` and maps old top-level keys.
- `TriggerNode_FileInput(ShapingNode)` with `INPUTS=0`, one output; remove the
  old `processInputs`/`get_code` and `cleanup_memory` unless still needed for
  the reader cache; any retained cleanup must not touch the model.
- Keep title/icon/enum/registry.

## 7. Legacy loader

Old content serialized source keys at the top level (plus path/metadata).

```python
def _legacy_settings(self, data):
    settings = {}
    for key, default in core.SOURCE_DEFAULTS.items():
        value = data.get(key, default)
        if value is None:
            value = default
        settings[key] = value
    settings["filePathRel"] = str(data.get("filePathRel") or "")
    settings["input_schema_version"] = 2
    settings["schema_snapshot"] = list(data.get("schema_snapshot") or [])
    settings["file_metadata"] = dict(data.get("file_metadata") or {})
    return settings

def deserialize(self, data, hashmap={}):  # noqa: B006
    if "settings" not in data and "filePath" in data:
        data = dict(data)
        data["settings"] = self._legacy_settings(data)
    result = super().deserialize(data, hashmap)
    self._resolve_relative_path()
    return result
```

- Keep the current relative-path resolution helper (`to_stored_paths` /
  workflow directory) in the Qt content; core never resolves workflow paths.
- Do not use properties for old fields (`content.filePath`, etc.) in new
  code. Update tests to settings.

## 8. Tests

Core wrapper:

`tests/unit/test_file_input_core.py`:

- `run_node([], settings)` delegates to `build_source`;
- empty path error;
- one CSV/Parquet/JSON/NDJSON/Excel/DB case per `test_input_source_*`;
- record limit, filename column, sheet column, schema mismatch;
- no Qt import.

Content/legacy:

- update `test_file_input_codegen.py` to assert generated code calls
  `core.run_node` with JSON settings and resolves paths.
- update `test_file_input_legacy.py` to assert old state becomes
  `settings`, not old attributes.
- update `test_file_input_state.py` for settings round-trip.
- update `test_file_input_validate.py` for settings-backed validation.
- keep `tests/e2e/test_input_types_e2e.py` and all-node e2e green; do not
  regenerate goldens unless the plan explicitly changes output.

Dock/UI:

- path picker, type switch, debounce;
- Excel/db sections show correct fields;
- schema/report refresh after a successful read;
- undo/redo for path, patterns and mode fields;
- live preview equals generated code.

## 9. Migration stages (do not collapse)

1. **Core wrapper + tests only.** No UI or node change. Commit if useful.
2. **Settings model.** Add `settings` to `FileInputContent` and convert one
   section at a time. Settings is the only truth; do not add parallel
   properties for old fields. Compile after each section.
3. **Content base conversion.** Make `FileInputContent(ShapingContent)`,
   custom layout, `compute` via core. Keep the old source UI code.
4. **Node conversion.** `TriggerNode_FileInput(ShapingNode)` with
   `INPUTS=0`; remove old process/codegen.
5. **Legacy loader + test updates.** Remove old attributes from tests.
6. **Cleanup.** Delete dead source state and timers; run full File Input and
   e2e suites.

Do not combine stage 1 with stage 3; the core wrapper is the safety net.

## 10. Acceptance

- [ ] `build_source` remains the only reader/union implementation.
- [ ] All `test_input_source_*` and `test_file_input_*` tests pass.
- [ ] `test_input_types_e2e` and all-node e2e pass.
- [ ] Old `filePath`, sheet, pattern and DB state loads into settings.
- [ ] Live == generated output.
- [ ] Relative saved paths still resolve.
- [ ] No file is read on every keystroke (debounce preserved).

## 11. Do not

- Do not rewrite CSV/Excel/DB readers in this migration.
- Do not change `SOURCE_DEFAULTS` without updating `core/input_source` tests.
- Do not replace `InputReadError` with a generic shaping error; preserve
  TD-IN codes.
- Do not keep `content.filePath`/`file_type`/`db_table` as parallel model
  fields.
