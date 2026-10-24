# File Output - modernization plan

Status: not started.
Implementation order: 17 of 18 (Tier 5, filesystem write).
Read first: `plans/nodes/README.md`.

## 1. Current implementation

- File: `src/trigger_designer/qt/widgets/nodes/InOut/file_output.py`.
- Content: `FileOutputContent` (line 31).
- Node: `TriggerNode_FileOutput` (line 392), `inputs=[1]`, `outputs=[]`.
- Settings today:
  - `filePath`
  - `file_format` (`csv`, `custom_delimited`, `excel`, `parquet`, `json`,
    `ndjson`, `ipc`)
  - `delimiter`
  - `use_streaming` (currently not consulted by the writer; see below)
  - `include_bom`
  - `compression` (currently not consulted by the writer)
- Old execution: `processInputs` stores the input variable and returns the
  input value; it does **not** write during live evaluation.
- Old codegen: `get_code` emits sink calls (`sink_csv`, `sink_parquet`,
  `sink_ndjson`, `sink_ipc`) or collect-then-write (`excel`, `json`), with a
  success print and error re-raise.
- Existing tests: `tests/unit/test_file_output.py`,
  `tests/e2e/test_input_types_e2e.py`, all-node e2e.

## 2. Target

- Core: `src/trigger_designer/core/shaping/file_output.py`.
- Content: `FileOutputContent(ShapingContent)` with a custom path/format
  layout.
- Node: keep `TriggerNode_FileOutput(TriggerNode)` (sink, zero outputs) and
  keep the custom `processInputs`. This is a documented exception to
  `ShapingNode`: the node has no output socket and must not write during
  live evaluation.
- Settings: the six keys above.
- `INPUTS = 1`; `OUTPUT_KINDS = ()`;
- `HISTORY = "File Output"`; `SUMMARY = "write to file"`.

### Settings schema

```python
DEFAULTS = {
    "filePath": "",
    "file_format": "csv",
    "delimiter": ",",
    "use_streaming": True,
    "include_bom": False,
    "compression": None,
}
```

## 3. Behavior contract

- **Live never writes.** Editing the dock or changing upstream data must not
  create/truncate a file. Only generated code (Run) calls the writer.
- `filePath` empty -> generated code raises
  `ValueError("File Output: no incoming data - connect an input")` or a
  dedicated "choose a path" error. Live must not fail just because the path
  is empty until the user Runs.
- Input may be `DataFrame` or `LazyFrame`; writer normalizes to LazyFrame.
- Format behavior must match the old `get_code`:
  - CSV: `sink_csv(path, separator=delimiter if not ",", include_bom)`
  - custom_delimited: `sink_csv` with the configured separator; empty ->
    `","`
  - Excel: `collect().write_excel(path)`
  - Parquet: `sink_parquet(path, compression="snappy")`
  - JSON: `collect().write_json(path)`
  - NDJSON: `sink_ndjson(path)`
  - IPC: `sink_ipc(path)`
- Existing `use_streaming` and `compression` settings are retained for saved
  compatibility, but the current writer ignores them. Do not silently
  implement new behavior in this migration; either keep them as UI-only
  (document it) or implement them in a separate change with tests.
- Errors are raised, not swallowed. The old code re-raises after printing;
  do not print from core. The Run error path will report the exception.
- Paths are used as given, with forward slashes in generated code only when
  needed for safe quoting. Prefer JSON-serialized settings so a Windows path
  cannot become a Python escape.
- No output socket, no output variable.

## 4. Core extraction

Create `core/shaping/file_output.py`:

```python
DEFAULTS = {...}
FORMATS = ("csv", "custom_delimited", "excel", "parquet", "json", "ndjson", "ipc")


def write_node(frames: list, settings: dict) -> None:
    """Write the input; called by generated code only."""
    frame = as_lazy(frames[0])
    s = {**DEFAULTS, **(settings or {})}
    path = str(s["filePath"] or "")
    if not path:
        raise ValueError("File Output: choose an output path")
    ...
```

- Use `.sink_*` / `.collect().write_*` exactly as the old code.
- `write_node` returns `None`; it is not a shaping runner.
- Provide `run_node(frames, settings) -> list` that returns `[]` for the
  content base. Never call `write_node` from it.
- Do not import Qt, `print`, or `logger`.
- Keep `compression`/`use_streaming` in `DEFAULTS` only for the settings
  schema; do not pretend they work unless implemented.

## 5. UI

Custom layout because the path needs a browse button:

1. `ConfigSection("Destination")`
   - `QLineEdit` for `filePath` with a browse `IconButton` (folder icon,
     tooltip/accessibility), 300 ms debounce.
   - `NoWheelComboBox` for `file_format` with labels.
   - Delimiter field, visible for csv/custom_delimited.
   - Include BOM checkbox for csv/custom_delimited.
   - Use streaming / compression controls only if they are actually honored;
     otherwise hide or mark read-only so the UI does not lie.
2. A short hint about the target path and format.
3. `dock_context` shows the file name/format, not a data table.

- Do not write on any control change. The only write is generated code.
- Use shared 30 px controls and no inline QSS.
- Keep the path picker behavior and validation messages.

## 6. Content and node

- `FileOutputContent(ShapingContent)`:
  - `SETTINGS`, `MODULE`, `INPUTS=1`, `OUTPUT_KINDS=()`.
  - `compute()` returns `[]` (no output); do not call the writer.
  - override `get_code()`:
    ```python
    import json
    import polars as pl
    from trigger_designer.core.shaping.file_output import write_node as _write_node
    _write_node([<input var>], json.loads('<settings json>'))
    ```
    If the input variable is missing, emit a `raise ValueError("File Output: no incoming data - connect an input")`.
  - no `serialize` override except the legacy loader.
- `TriggerNode_FileOutput(TriggerNode)`:
  - keep `inputs=[1]`, `outputs=[]`;
  - `processInputs` sets `content.frames[0]`, `content.input_vars[0]` and
    returns the input value (old behavior), without writing;
  - `get_code` delegates to content.
- Remove old `data`, `incoming_variable` as model; keep only UI/read-only
  state.
- Keep title/icon/enum/registry.

## 7. Legacy loader

Old content serialized top-level keys. Map each with the defaults above;
`compression` may be `None`.

```python
def _legacy_settings(self, data):
    return {
        "filePath": str(data.get("filePath") or ""),
        "file_format": str(data.get("file_format") or "csv"),
        "delimiter": str(data.get("delimiter") or ","),
        "use_streaming": bool(data.get("use_streaming", True)),
        "include_bom": bool(data.get("include_bom", False)),
        "compression": data.get("compression"),
    }
```

Add the standard `deserialize` guard.

## 8. Tests

`tests/unit/test_file_output.py` (port existing + new):

- each format writes the expected file/bytes (tmp_path);
- CSV delimiter and BOM;
- empty path -> error;
- live content compute does not write (mock `write_node` or check no file);
- generated code writes once;
- Windows path with backslashes compiles/executes;
- input is not modified.

`tests/ui/test_file_output_dock.py`:

- path/format/delimiter visibility;
- setting edits are undoable;
- no file is written on edit;
- generated code equals the expected writer call.

Keep `tests/e2e/test_input_types_e2e.py` and all-node e2e green.

## 9. Steps

1. Add core writer + tests.
2. Rebase content on `ShapingContent` for settings/form/undo; keep custom
   layout and sink node.
3. Add custom `get_code` + loader.
4. Remove old writer/codegen and state.
5. Run focused tests, input-types e2e, all-node e2e.
6. Commit as `refactor: move File Output onto the shaping settings system`.

## 10. Acceptance

- [ ] Editing the dock never writes a file.
- [ ] Run writes exactly once in the configured format.
- [ ] All existing file-output tests pass.
- [ ] Old saved settings load.
- [ ] No output socket is added.

## 11. Do not

- Do not use `ShapingNode` if it adds an output socket.
- Do not write from `run_node`/`compute`.
- Do not implement `use_streaming`/`compression` semantics without tests and
  a separate decision; keep them as saved compatibility settings.
