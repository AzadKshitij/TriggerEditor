# Workpaper internals

How the Excel workpaper is built: the shared Excel engine in `core/excel`, the Qt-free
writer in `core/workpaper`, the Workpaper Output node, File > Export Workpaper..., the
headless seam, the tests and the benchmarks. For the user's view read
`../guide/workpaper.md`. Plan `../plan/06-workpaper-export.md` is background only; where it
differs from the code, the code wins.

Read first: `architecture.md` (layers, generated-code contract), `audit-trail-internals.md`
(the run record that the Run log reads), and `cli-internals.md` sections 10 and 14 (code
policy, op catalogue).

## Contents

1. Module map
2. Data flow of one Run
3. Streaming and memory
4. The run-record provider
5. The generated-code contract and the code policy
6. The node: snapshots, settings, sockets
7. The sheets and their layout contracts
8. Cell rules (sanitising, types, limits)
9. Paths, versions, publishing
10. File > Export Workpaper... (the run workpaper)
11. Headless use
12. Error handling
13. Tests and benchmarks
14. Extension points
15. Known gaps
16. Verified against

## 1. Module map

```
core/excel/                 Qt-free; the ONLY package that imports xlsxwriter
  engine.py                 lazy import, require_xlsxwriter(), new_workbook() with safe options
  errors.py                 ExcelWriteError(code=TD-OUT-nnn), the code constants
  cells.py                  how a Polars value becomes a cell: write_text/write_value, FormatBook,
                            ColumnPlan/column_plan, needs_quote_prefix, guard_text, safe_sheet_name
  spool.py                  Spooled, spool_parquet(), BATCH_ROWS = 50_000, batches()
  frame_export.py           write_frame_xlsx (one frame -> one sheet), check_target_folder, publish
core/workpaper/             Qt-free
  spec.py                   WorkpaperSpec, SourceFile, TestInfo, WorkpaperResult, WorkpaperError
  writer.py                 write_workpaper (one test), write_run_workpaper (whole run), gather_sources
  stream.py                 compute_stats, population_stats, amount_expr, write_csv_sidecar, sha256_file
  sanitize.py               workpaper-facing names and limits (MAX_LISTED, MAX_DATA_COLUMNS, RESERVED_SHEETS)
  sheets_summary.py         the Summary sheet (both layouts)
  sheets_exceptions.py      the Exceptions sheet
  sheets_runlog.py          the Run log and Workflow sheets
  node_logic.py             DEFAULTS, IF_EXISTS_LABELS, ROLES, effective_spec, build_code, run_node
  node_runner.py            run_workpaper(...): the entry point generated code calls
  context.py                current_run_record(): reads the in-flight run record
  paths.py                  unique_path, predict_output_path
qt/
  widgets/nodes/InOut/workpaper_output.py   WorkpaperOutputContent + TriggerNode_WorkpaperOutput
  helpers/workflow_snapshot.py              scene -> plain dicts (workflow steps, sources)
  helpers/workpaper_export.py               File > Export Workpaper...: dialog + flow
  helpers/main_window_actions_mixin.py      actExportWorkpaper (+ main_window_ui_mixin: File menu)
  dialogs/preferences_dialog.py, preferences.py   Engagement defaults (engagement/*, export/workpaper_dir)
core/headless/code_policy.py   GENERATED_IMPORTS allows run_workpaper (and write_frame_xlsx)
core/headless/op_catalog.py    input.workpaper_output row with output_keys=("output_path",)
core/errors/catalogue.py       passthrough entries for TD-OUT-010 .. 015
```

`core/excel/__init__.py` re-exports only `ExcelWriteError` and `write_frame_xlsx`;
`core/workpaper/__init__.py` re-exports the data classes and wraps `write_workpaper` and
`write_run_workpaper` in lazy functions, so importing the package costs nothing (Polars and
xlsxwriter load on the first call). The importers of `write_frame_xlsx` are File Output
(`core/shaping/file_output.py`), the Data Preview export
(`qt/models/polars_table_viewer.py`) and the Data Profile export (`core/profile.py`).

## 2. Data flow of one Run

```
Run workflow (GUI thread)
  _run_before_run_hooks(sorted_nodes)          each content.before_run()
      WorkpaperOutputContent.before_run:       snapshot ON THE GUI THREAD
          _engagement = engagement_from_preferences()
          _workflow   = collect_workflow(node)     # ancestors, run order, + Comment nodes
          _sources    = collect_sources(node)      # files the ancestors read (no hashing)
  worker thread: for each node, get_code() -> exec
      get_code() -> node_logic.build_code(effective_spec(...), input_vars, workflow, sources)
      generated code calls run_workpaper(spec_json=..., exceptions=<var>, population=<var|None>,
                                         summary=<var|None>, workflow_json=..., sources_json=...)
run_workpaper (node_runner.py)
  WorkpaperSpec.from_json(spec_json); extra sources appended
  TestInfo from the first row of the Summary frame
  run_record = current_run_record() if spec.include_run_record else None
  write_workpaper(spec, exceptions, population, test, run_record, workflow)
write_workpaper (writer.py)
  _validated(spec)                       -> TD-OUT-012 on bad path / date / mode; clamp decimals, row_limit
  engine.require_xlsxwriter()            -> TD-OUT-003
  _choose_path(path, mode)               -> TD-OUT-001 / 010 / 002; versioned name for "version"
  tmp = mkdtemp("td_wp_")
  spooled = spool_parquet(exceptions)    # THE ONE RUN of the upstream plan
  column_plan, compute_stats             # one lazy pass over the spool: count, sum, max text length
  population_stats(population)           # one pass over the population plan
  truncated = total > limit; too_long = any(max_len > 32_767)
  if truncated or too_long: write_csv_sidecar -> tmp/full.csv (+ SHA-256)
  workbook = engine.new_workbook(tmp/workpaper.xlsx)       # constant_memory
  sheets added in order: Summary, Exceptions, Run log?, Workflow?
  write_exceptions_sheet  (rows streamed in 50,000-row batches)  -> ExceptionsLayout
  gather_sources, SummaryInputs, write_summary_sheet, write_runlog_sheet, write_workflow_sheet
  wb.close(); publish(tmp xlsx -> final) with os.replace; sha256 of the final file
  publish the CSV sidecar; return WorkpaperResult;  finally rmtree(tmp)
```

Order matters: with `constant_memory` a row written earlier than the current one is dropped,
so the Exceptions sheet is written first (the Summary needs its `last_row`, `written` and the
amount column letter) but the **Summary sheet is the first worksheet** (worksheets are added in
display order up front, written in dependency order). Each sheet writer writes its rows in
ascending order with a cursor.

## 3. Streaming and memory

- `spool_parquet` runs the upstream frame **exactly once**. A `LazyFrame` goes through
  `sink_parquet` (streaming); if Polars cannot stream the plan (`PolarsError`) it is collected
  once and written with `write_parquet`; if Parquet cannot hold the data (Object columns) the
  eager frame is kept in memory in `Spooled.frame` (the only unbounded case).
- Every later pass reads the spool: `compute_stats` (one `select` of `len`, amount `sum`,
  unparseable count and the maximum text length per string column), `write_csv_sidecar`, and
  the sheet writer.
- `Spooled.batches(size=BATCH_ROWS=50_000)` reads with **Polars only, no pyarrow**: it
  repeatedly collects `scan_parquet(path).slice(offset, size)`. Memory is bounded by one batch
  (plus a Parquet row group).
- The workbook is created with `constant_memory: True` and `tmpdir` set to the working temp
  folder; xlsxwriter streams each sheet to disk as rows are written. Hence "ascending rows
  only", and `merge_range`/`write_*` calls must come in row order on every sheet.
- The population plan is a separate scan (`population_stats`), one pass, never spooled.
- First-batch widths: column widths are set from the first batch only (cap 60 characters).
- Peak memory is a few hundred MB at most for any size (see section 13 for numbers).

## 4. The run-record provider

`core/audit/recorder.py` keeps one registry: `set_run_record_provider(callable | None)` /
`get_run_record_provider()` (a lock-guarded module global). The GUI run
(`qt/helpers/audit_bridge.py`, `RunSession`) installs `session.snapshot_current`, which
returns `recorder.snapshot(final_or_None)` as a plain dict, and
`workflow_execution_mixin` clears it with `set_run_record_provider(None)` at the end of the
Run. `core/workpaper/context.py::current_run_record()` calls the provider and returns a
`Mapping` or `None`; it **never raises** (a recording problem must never break a workpaper) and
converts a dataclass with `dataclasses.asdict`. `core/workpaper/context.set_run_record_provider`
is a thin wrapper for tests and headless callers; there is no second registry.

Consequences:

- The record is a **snapshot of the run in flight**: `status` is `running`, `finished_at` is
  missing, the workpaper node itself is not yet in `nodes`. The Run log sheet detects this
  (`status in (None, "", "running")`), prints the "Snapshot taken while..." banner and, for the
  node (`write_runlog_sheet(..., in_progress_step=True)`), appends a labelled "Workpaper Output
  (this workpaper)" row with status "in progress". The whole-run export never adds it.
  `gather_sources` fills a missing `row_count` of an input from its node's `rows_out`
  (`_rows_from_node`, only when that node read one file).
- Input files are in `record["inputs"]` with the fingerprints taken before they were read, so
  the Summary's source hashes are the run-time ones (`gather_sources` prefers a record entry
  that has a hash over a configured entry without one).
- **The headless runner does not install a provider**, so `current_run_record()` is `None` in a
  CLI run: the Run log is omitted with `NO_RECORD_REASON` (see section 15).
- The sealed record is written after the Run; the node tells it about its output through
  `audit_output_files()` (below).

## 5. The generated-code contract and the code policy

`node_logic.build_code` returns:

```python
import polars as pl
from trigger_designer.core.workpaper.node_runner import run_workpaper
_workpaper_result = run_workpaper(
    spec_json='{"title": ..., ...}',
    exceptions=<input var 0>,
    population=<input var 1 or None>,
    summary=<input var 2 or None>,
    workflow_json='[...]' or None,
    sources_json='[...]',
)
```

- With no Exceptions variable the code is a single `raise ValueError('Workpaper Output: connect
  the Exceptions input')`.
- **User text never enters the code as source.** The spec is serialised with `json.dumps`
  inside `WorkpaperSpec.to_json()`, and the whole JSON string is embedded with `!r`; the
  workflow and sources are `json.dumps(..., ensure_ascii=False)` embedded with `!r`. Free text
  (objective, procedure, criteria, notes) therefore cannot break out of a string literal.
- `core/headless/code_policy.py::GENERATED_IMPORTS` contains
  `"trigger_designer.core.workpaper.node_runner": {"run_workpaper"}` (and
  `"trigger_designer.core.excel.frame_export": {"write_frame_xlsx"}` for File Output as Excel).
  The AST policy allows only these names to be imported from those modules; any other import
  from them, or from a module not listed, is refused by `approve`/`run` in the CLI. Adding a
  new function to a node's generated code means adding it to `GENERATED_IMPORTS` in the same
  change (`tests/unit/test_headless_code_policy.py` guards it).
- `PATH_KEYS` of the policy includes `output_path`, the key of this node, and
  `op_catalog` declares `output_keys=("output_path",)` for `input.workpaper_output`, so the CLI
  lists the workbook under `writes`, stages it and remaps it with `--output-dir` exactly like a
  File Output. `tests/unit/test_op_catalog_matches_registry.py` checks the catalogue row.
- The executor runs the code with the node's input variables in scope (`exec`), on the worker
  thread; the result variable is unused except for debugging.

## 6. The node: snapshots, settings, sockets

`WorkpaperOutputContent` is a `ShapingContent` (the shaping framework's form builder) with
`SETTINGS = node_logic.DEFAULTS`, `MODULE = "trigger_designer.core.workpaper.node_logic"`,
`OUTPUT_KINDS = ()`, `INPUTS = 3`, `OPTIONAL_INPUTS = {1, 2}`, `HISTORY = "Workpaper"`.
`node_logic.run_node` returns `[]`: **live evaluation never writes a workpaper**, and the node
has no output socket. `TriggerNode_WorkpaperOutput` registers as `IONodes.WORKPAPER_OUTPUT`
(`input.workpaper_output`), reuses the `node_file_output` icon, and has sockets
`inputs=[1, 1, 1]`, `input_text=["E", "P", "S"]`, `outputs=[]`.

- **`FORM`** declares the dock: sections File, Engagement (collapsible), Test, Values, Sheets,
  Sources (collapsible, collapsed). The labels and defaults are in `FORM` and `DEFAULTS`;
  do not duplicate them elsewhere (the user guide quotes them).
- **`before_run()`** is the reason `get_code()` is safe on a worker thread: preferences
  (QSettings), the scene and the file system listing are read **only on the GUI thread**,
  once per Run, into `_engagement`, `_workflow` and `_sources`. `get_code()` on the main
  thread with no snapshot calls `before_run()` itself (live evaluation, tests). The CLI's
  `qt/headless.py::before_run` iterates the nodes and calls the same hook.
- **`effective_spec`** merges the settings with the engagement dict: node text wins, then
  `engagement/*` preferences, then for the preparer `getpass.getuser()`. The core never reads
  preferences, so a headless caller builds the same spec from a plain dict.
- **`audit_output_files()`** returns the workbook path the Run will write, as
  `predict_output_path(path, if_exists)`: for **New version** the *versioned* name (`wp (2).xlsx`),
  so the sealed run record fingerprints the file that really exists. It is read by
  `audit_bridge._output_files` through the content's `audit_output_files` hook.
- **`processInputs`** maps input index to role (`node_logic.ROLES = ("Exceptions", "Population",
  "Summary")`) and never ignores a connected input that failed (red node, tooltip
  "<role> input has no data"). An unconnected optional input is simply absent. It also sets the
  amount-column warning tooltip.
- **`validate_loaded_state`** returns "Workpaper Output has no output file; choose one before
  running." for an empty `output_path`.
- **`dock_context`** returns the header chips (`xlsx`, `N row limit`, the If-exists label in
  lower case) and the file name.
- File and Logo rows get a browse `IconButton` (`IconButton.themed`), through the overridden
  `_build_row`; `browse()` remembers the folder in `export/workpaper_dir`.

## 7. The sheets and their layout contracts

Cell addresses are part of the contract: the Summary's formulas point at the Exceptions sheet
and the tests and users read them. **Change a layout only together with its tests.**

**Summary** (`sheets_summary.write_summary_sheet`). Columns A..F (widths 30, 16, 22, 22, 22,
64). Fixed rows (1-based): 1 title (+ logo at F1), 2 subtitle, 4 Engagement section, 5
reference, 6 client, 7 engagement, 8 period, 9 test performed, 10 prepared by, 11 prepared on,
12 reviewed by, 13 review date, 15 Objective section, 16 objective, 17 procedure, 18 criteria,
20 Results section, 21 headers, 22 population, 23 exceptions found, 24 exceptions listed, 25 CSV,
26 reconciliation. Below row 26 a cursor writes Conclusion, Auditor notes, Tick marks, Source
files, Notes and limitations, Workbook contents. Formulas (each carries a cached value so
non-recalculating viewers show numbers): `B23 =B24`, `C23 =C24`, `D23
=IFERROR(B23/B22,"n/a")`, `E23 =IFERROR(C23/C22,"n/a")`, `B24 =COUNT('Exceptions'!$A$3:$A$n)`,
`C24 =SUM('Exceptions'!$X$3:$X$n)` and a `COUNTIF` per tick mark. When truncated,
B23/C23 are numbers (the true totals) instead of `=B24`. The `run` layout (`mode="run"`) replaces
the Results block by the **Test results** table from row 21 and has no tick marks. The sheet is
protected with an empty password and `autofilter` allowed; yellow cells (`locked: False`) are the
inputs. The empty-text fields are written with the yellow `input` style (`field()` decides).

**Exceptions** (`sheets_exceptions.write_exceptions_sheet`). Row 1 banner (ok / none /
red TRUNCATED + red tab), row 2 headers (`Ref`, `Tick mark`, `Auditor comment`, data columns from
D), data from row 3. `ref` is `written + 1`; the amount column is written from the parsed value
(`amount_expr`), falling back to the original text for unparseable values; `last_row =
max(3, 2 + written)`; the tick-mark list validation covers B3..B(last_row); freeze panes at
(2, 1); autofilter over the header row; landscape, one page wide, header row repeated. The
sheet is **not** protected.

**Run log / Workflow** (`sheets_runlog`). Written read-only from plain dicts
(`record.get`, so a missing key prints `not recorded`). `friendly_op("preparation.select_records")`
= `Select Records`. A failed step uses the `rl_fail*` formats. `total_rows_out(node)` from
`core/audit/view` gives *Rows out* (`None` prints "not counted"). Workflow settings come from
`workflow_snapshot.describe_settings(node)`: the content's `describe_settings()` hook if it has
one, else `snapshot_settings(content)` with labels derived from the keys; values are cut at 600
characters in the snapshot and 300 on the sheet. File Input has the hook
(`FileInputContent.describe_settings`): Source, Source type, folder/pattern options, then the
options of the type (CSV delimiter/header/encoding, Excel sheet(s)/start row, JSON nested values,
database table/query), Row limit and the file name column; bookkeeping keys (`Filepathrel`,
`Input schema version`, `schema_snapshot`, `file_metadata`) are omitted.

Sheet names: `Summary`, the (sanitised) Exceptions name, `Run log`, `Workflow`.
`RESERVED_SHEETS = ("summary", "run log", "workflow", "tests")` keeps a user's name from colliding
(`safe_sheet_name(..., used=RESERVED_SHEETS)`: illegal characters to spaces, 31 characters,
case-insensitive uniqueness by appending ` (n)`).

## 8. Cell rules (sanitising, types, limits)

All in `core/excel/cells.py`, one place:

- **Never `ws.write()`.** It guesses a type and turns `=...` into a formula. Every cell goes
  through `write_text` (strings) or `write_value` (explicit `write_number`, `write_boolean`,
  `write_datetime`, `write_blank`). The workbook options in `engine.new_workbook` also set
  `strings_to_numbers/formulas/urls: False`, `nan_inf_to_errors: False`, `remove_timezone: True`.
- **Danger text** (`needs_quote_prefix`, regex `^(?:[=@\t\r]|[+-](?!\s*[\d.,]+\s*$))`): written
  with a format that has `quote_prefix: True`. A plain signed number (`-12.50`) is not danger.
  `danger_expr` is the Polars twin (Polars' regex has no look-around) for lazy use.
- `guard_text`: control characters (`[\x00-\x08\x0b\x0c\x0e-\x1f]`) to U+FFFD, and text over
  `MAX_CELL_CHARS = 32_767` shortened with a marker. Both counted into the `stats` dict, which
  becomes the Summary's notes.
- `write_value`: `NaN`/`Infinity` as text; integers `>= 10**15` as text; `Decimal` to float;
  dates before 1900 as ISO text; durations are converted to seconds by `column_values`;
  tz-aware datetimes have the zone replaced by `None` (clock time kept).
- `column_plan` picks per-column `kind` and number format; an integer column whose name
  matches `ID_NAME` gets the `0` format (no thousands separator); duration headers get
  ` (seconds)`; headers that collide with `RESERVED_HEADERS` get ` (data)`; empty headers become
  `Column n`.
- `stream.amount_expr(name, dtype)`: for `String` delegates to `core/utils/amounts.py`, the
  shared decimal-comma aware parser that the audit nodes and Reconcile use (`12,5` is 12.5,
  `1.234,50` and `1'234,50` are 1234.5, `(x)` is `-x`; unreadable forms such as `1,2,3` are null
  and counted in `ExceptionStats.unparseable`); numeric dtypes cast to Float64; anything else `None`.
- CSV sidecar (`stream.write_csv_sidecar`): UTF-8 with BOM, a `Ref` column, cells with
  `needs_quote_prefix` text prefixed by `'`, booleans as `true`/`false`, datetimes ISO with a space.

Limits: `EXCEL_MAX_ROWS = 1_048_576`; `HEADER_ROWS = 2`; `MAX_LISTED = 1_048_574`;
`MAX_DATA_COLUMNS = 16_384 - 3`. `write_frame_xlsx` has its own: `engine.MAX_ROWS` and `MAX_COLS`,
refusing (`TD-OUT-013`, `TD-OUT-011`) instead of truncating, because a one-sheet export has no
CSV sidecar to carry the rest.

## 9. Paths, versions, publishing

- `_validated` normalises `output_path` (strip), requires `.xlsx`, and checks `if_exists in
  ("version", "replace", "fail")`, `prepared_date` (ISO), clamps `value_decimals` to 0..6 and
  `row_limit` to 1..`MAX_LISTED` (a note says so when lowered).
- `_choose_path(path, mode)`: `check_target_folder` (TD-OUT-001, no silent mkdir); `version` ->
  `unique_path` (`name (2).xlsx` ...); `fail` + exists -> TD-OUT-010; `replace` + `~$name` lock
  file present -> TD-OUT-002.
- `_sidecar_target(final, mode)`: `<final stem>_exceptions_full.csv`; exists + `fail` -> TD-OUT-010;
  exists + `version` -> `unique_path`.
- The workbook and CSV are built in `tmp` and moved with `frame_export.publish` (`os.replace`).
  `PermissionError` -> TD-OUT-002; `ENOSPC` -> TD-OUT-005; other `OSError` -> TD-OUT-014.
  The workbook is published first; the CSV after. A failure while building calls `_abort(wb)` to
  close the streaming temp handles (Windows cannot delete open files) and re-raises.
- `paths.predict_output_path` is used by the node **before** the Run, so it must stay in step
  with `_choose_path` (same `unique_path`).

## 10. File > Export Workpaper... (the run workpaper)

`qt/helpers/workpaper_export.py::export_workpaper(main_window)`:

1. active window -> `store_from_preferences().latest_record_dict(workflow_path=...)` (the sealed
   history, not the in-flight record); no record -> an information box (`NO_RECORD`), return.
2. `WorkpaperExportDialog` (File, If it exists, Engagement fields, Test text) -> `settings()`.
3. `collect_scene_workflow(scene, order_ids)`: every executable node of the scene in the order
   of the record's `nodes[*].node_id`, then the Comment nodes.
4. `build_spec` -> `node_logic.effective_spec({**DEFAULTS, **settings}, engagement_defaults(),
   app_version=VERSION)`; `write_run_workpaper(spec, run_record=record, workflow=workflow)`.
5. On success the folder is stored in `export/workpaper_dir` and a message box shows the path;
   on failure `QMessageBox.warning("Workpaper not written", str(exc))`.

`write_run_workpaper` shares everything with `write_workpaper` except: no Exceptions sheet
(`with_exceptions=False`), `SummaryInputs(mode="run", tests=tests_from_record(record))` where the
tests are the `test_summary` of the record's nodes, and `WorkpaperResult.exceptions_total` is
the sum of the tests' exception rows. Its "Test performed" row is `spec.test_name`, else
`sheets_summary._whole_run_label(len(tests))` ("Whole run: 2 tests"). `dialog_class` is injectable so tests drive the flow
without a modal dialog.

## 11. Headless use

`run_workpaper` takes resolved values only (JSON text, frames), never preferences or Qt objects:

```python
from trigger_designer.core.workpaper.node_runner import run_workpaper
from trigger_designer.core.workpaper.node_logic import effective_spec
spec = effective_spec({"output_path": "out/wp.xlsx", "client": "Acme"}, {"preparer": "A. Auditor"})
result = run_workpaper(spec_json=spec.to_json(), exceptions=lazy_frame, population=None,
                       summary=None, workflow_json=None, sources_json="[]")
# result is WorkpaperResult.to_dict(): path, csv_path, exceptions_total, exceptions_written,
# truncated, workbook_sha256, sheets, omitted, warnings, duration_s ...
```

Or call `write_workpaper(spec, frame, population=..., test=TestInfo(...), run_record=dict,
workflow=[...])` / `write_run_workpaper(spec, run_record=dict, workflow=[...])` directly. For
a Run log, pass a record dict (or install a provider with
`core.workpaper.context.set_run_record_provider`). `now=` fixes the clock for tests.
`tests/support/workpaper.py` has `FIXED_NOW`, `EXCEPTIONS`, `POPULATION`, `make_spec`, `load`
(openpyxl), `find_label`, `value_right_of`.

The CLI (`trigger-designer-cli run wf.tds --output-dir D`) runs the node like any other: the op
catalogue stages `output_path`, `qt/headless.py` calls `before_run`, the AST policy admits the
generated code. See section 15 for what differs from the editor.

## 12. Error handling

- Writer errors derive from `ExcelWriteError` (`code`, `path`, readable `str`).
  `WorkpaperError` defaults to `TD-OUT-012` and is raised for settings and for an empty column
  list.
- Codes: `TD-OUT-001` folder missing, `002` file open/locked, `003` xlsxwriter missing, `005`
  disk full, `010` exists, `011` too many columns, `012` invalid settings, `013` too many rows
  (one-sheet export only), `014` Excel could not create the workbook. 001..006 have catalogue
  entries with fixes; **010..015 are passthrough** entries in `core/errors/catalogue.py` (`_PASSTHROUGH`:
  title, hint, severity) that keep the writer's own message as the detail. A new code needs a
  catalogue entry and a row in `docs/guide/errors-and-problems.md`; the guard test that every
  `TD-` literal is in the catalogue will fail otherwise.
- Library errors (`xlsxwriter.exceptions.XlsxWriterException`) raised on `close()` become
  `TD-OUT-014`. `write_frame_xlsx` also catches them around its sheet writer.
- Soft problems never raise: a bad logo, an unreadable amount, a missing source file, an
  absent run record each become a line in **Notes and limitations** (or an omitted sheet with a
  reason) and in `WorkpaperResult.warnings`, which `run_workpaper` sends to the log.
- `current_run_record()` and `workflow_snapshot` swallow their own failures (logged at debug /
  warning) so a snapshot problem cannot fail a Run.

## 13. Tests and benchmarks

| File | What it holds |
|---|---|
| `tests/unit/test_excel_frame_export.py` (20) | `write_frame_xlsx`: round trip, header/filter/freeze, formulas never written, sheet names, row and column limits (TD-OUT-013/011), TD-OUT-001/002/003, failed publish keeps the old file, batches keep order, only `engine` imports xlsxwriter, no `ws.write` guessing |
| `tests/unit/test_workpaper_sanitize.py` (24) | quote-prefix rules, `guard_text`, sheet names, headers, column plan |
| `tests/unit/test_workpaper_writer.py` (24) | `write_workpaper` and `write_run_workpaper`: modes, truncation and CSV, versions, errors, hashes |
| `tests/unit/test_workpaper_summary_sheet.py` (15) | the fixed Summary cells, formulas and cached values, protection |
| `tests/unit/test_workpaper_exceptions_sheet.py` (14) | banner, headers, amount handling, validation, freeze, notes |
| `tests/unit/test_workpaper_runlog_sheet.py` (11) | Run log and Workflow sheets, snapshot banner, failed steps |
| `tests/unit/test_workpaper_node.py` (17) | the node: registration and op id, invalid states, `get_code` (policy check, execution, safe embedding of user text), spec defaults and clamps, `before_run` snapshot, predicted versioned name |
| `tests/ui/test_workpaper_dock.py` (12) | the Config Dock: empty state, sections and controls, debounced edits, If-exists labels, amount picker, row-limit spin, undo without re-recording, browse, inherited placeholders, no file written while editing |
| `tests/ui/test_workpaper_export.py` (9) | the export flow: no record, cancel, success, numbered copy, plain-language failure, default path, menu action |
| `tests/ui/test_workpaper_preferences.py` (5) | the Engagement section of Preferences |
| `tests/e2e/test_workpaper_e2e.py` (4) | a real window runs ledger -> Duplicates -> Workpaper Output + File Output (Excel) on a worker thread; the record fingerprints the workbook; Export Workpaper; second run -> `wp (2).xlsx`; Replace; row limit and CSV |
| `tests/unit/test_headless_code_policy.py`, `test_op_catalog_matches_registry.py` | the policy allows `run_workpaper`; the op row exists |
| `tests/benchmarks/test_workpaper_perf.py` | memory/time budgets (opt in) |

Run the focused set (about 45 seconds):

```text
uv run --project . pytest tests/unit/test_workpaper_*.py tests/unit/test_excel_frame_export.py ^
    tests/ui/test_workpaper_*.py tests/e2e/test_workpaper_e2e.py -q
```

The e2e builds a `.tds` with real nodes and `Edge`s, reopens it with `fileLoad`, runs with
`run_workflow_and_wait` and reads the workbook back with `openpyxl` (`tests/support/workpaper.py`
`load(path, data_only=True)` gives the cached values).

**Benchmarks** are skipped unless you pass `--run-benchmarks`:

```text
uv run --project . pytest tests/benchmarks/test_workpaper_perf.py --run-benchmarks -s
```

`WORKPAPER_BENCH_ROWS` (default 500000) changes the size. Rows are generated lazily; peak RSS is
sampled by a thread every 50 ms. Reported numbers:

| Case | Reported by the plan 06 implementer | Re-run for this page (machine busy with other agents) |
|---|---|---|
| `write_workpaper`, 500,000 rows x 8 columns, row limit 1,048,574 | 34 s, +208 MB | 46.6 s, +205 MB |
| `write_frame_xlsx`, 500,000 x 6 | 24 s, +42 MB | 30.9 s, +48 MB |
| over limit (100,000 listed, CSV of 500,000) | passes (CSV has 500,001 lines) | passes |

The asserted budgets are +400 MB and 120 s. Memory is the stable figure; wall time varies with
the machine. **Mind the editor's per-step limit of 30 seconds** (`SecurityConfig.max_execution_time` in `core/ExecutionCheck/executor.py`):
a 500k-row workpaper takes longer than that, so the node's dock carries the hint "Large workpapers
may exceed the 30 second per-node limit; lower the row limit". The timed-out step is abandoned,
not stopped (the executor has no way to interrupt a thread inside `exec`). The workpaper no
longer publishes after that: the generated code passes `node_id=` to `run_workpaper`, which
builds an `abandoned()` poll from the run record (`node_runner._abandon_check`: this node is
`failed` in the in-flight record, or the run is no longer `running`). `write_workpaper` polls it
after the Exceptions sheet, before closing the workbook and again before publishing, and then
drops the staged files and raises `WorkpaperAbandoned` (`spec.py`; nothing is written, the CSV is
not published either). It cannot detect abandonment when no run record exists (CLI, which has no
time limit anyway). The remaining gap is the limit itself, which only the executor can change:
see the options in section 15, item 7.

## 14. Extension points

**Add a sheet** (for example a Profile sheet):

1. Write `core/workpaper/sheets_<name>.py` with `write_<name>_sheet(ws, book, data)`; use only
   `core/excel/cells.py` for cells (`write_text`, `write_value`, `FormatBook`), never `ws.write`
   and never import `xlsxwriter`. Write rows in ascending order.
2. In `writer._sheet_names` add the name (and the reason when omitted), and add it to
   `RESERVED_SHEETS` (`sanitize.py`) so a user's Exceptions name cannot collide.
3. In `write_workpaper` add the worksheet to the ordered list (display order is creation order),
   call the writer inside the `try` that owns `wb`, and add it to `_Names.contents()` so the
   Summary lists it.
4. Take the data through `write_workpaper` arguments (then through `run_workpaper` and the
   generated code in `build_code`, which also needs a spec field in `WorkpaperSpec` and a
   `node_logic.DEFAULTS` key) or from the run record.
5. Tests: a unit test reading the sheet with `openpyxl`; update `test_workpaper_writer` sheet
   lists; `docs/guide/workpaper.md` ("What each sheet contains").

**Add a node setting:** `node_logic.DEFAULTS` (one list for schema, dock and tests), a `Field`
in `FORM`, the `WorkpaperSpec` field and `effective_spec` mapping, the writer behaviour, the dock
test, and the guide's Config Dock table. Mind `from_json`: unknown keys are dropped, so an old
`.tds` with fewer keys keeps working (defaults fill in).

**Add a source of exceptions** (a new node feeding the workpaper): nothing to change in the
writer; connect it to **E**. For a node that reports a test result, make its Summary frame carry
the `TestInfo` columns (`test_name`, `criteria`, `status`, `message`, `population_rows`,
`exception_rows`, `exception_rate`, `population_value`, `exception_value`, `parameters`) so **S**
can reconcile it. Run workpapers read `node["test_summary"]` of the record.

**Add a node whose file should be fingerprinted:** give its content `audit_output_files()`.

**Change the tick marks:** `spec.DEFAULT_TICKS`; the spec already carries `tick_marks`, but the
node has no setting for it yet.

## 15. Known gaps

These were found while writing the guide, by running the code. They are not fixed here.

1. ~~Decimal-comma amounts are misread~~ (fixed: `stream.amount_expr` uses the shared parser).
2. **CLI run, truncated list (fixed in the working tree, not yet committed when this page was
   written).** The CLI stages every output under a temporary name, and the sidecar used to be named
   after it (`.<name>.tdtmp-<id>_exceptions_full.csv`, left hidden in the output folder, and quoted
   on the Summary). The fix adds `WorkpaperSpec.publish_path` (the final path; used only to name
   the CSV, `writer._sidecar_target(spec.publish_path or final, ...)`), set by
   `core/headless/params.py::_finish_workpapers`, which also decides `if_exists` before the write
   (the staged name is always fresh, so the writer cannot see the final one) and remaps
   `source_files` with `--input-dir` (`OpInfo.list_keys`). Verified by hand: `--output-dir` gives
   `x.xlsx` + `x_exceptions_full.csv`, a second run gives `x (2).xlsx` + `x (2)_exceptions_full.csv`.
   Check `git log` for the commit and its tests (`tests/e2e/test_cli_workpaper.py`,
   `tests/unit/test_headless_workpaper_paths.py`).
3. **CLI run, no Run log.** `core/headless` installs no run-record provider, so the Run log
   sheet is omitted ("no run record is available"). (The CLI writes its own record.)
4. ~~Run workpaper "Test performed" always read "Exceptions workpaper"~~ (fixed: "Whole run: N tests").
5. ~~The Workflow sheet's File Input row listed internal keys~~ (fixed: `describe_settings()` hook).
6. ~~In-flight Run log gaps~~ (fixed: labelled in-progress row; `Rows read` from `rows_out`).
   Still "not recorded" for a folder/pattern input of several files.
7. **Time limit (partly mitigated):** the 30 second per-step limit still makes lists of about
   400,000 rows and more fail in the editor (see section 13); an abandoned step no longer
   publishes the workbook. Fixing the limit needs `core/ExecutionCheck/executor.py`. Options:
   (a) a per-node timeout declaration the executor reads (for example a `max_execution_time`
   attribute on the node content, 120 s for Workpaper Output); (b) a progress heartbeat the node
   calls so the executor treats it as alive; (c) lower the work per step (the node's row limit
   default, or write the exceptions sheet from a separate worker and wait on it).

## 16. Verified against

Written on 2026-10-31 against branch `feature` at `eda6906` (workpaper commits `e2b610a`,
`1604afe`, `d7fbcde`, `87eeb4c`, `b4c333f`, `eda6906`). The 135 focused tests above passed, the
three benchmarks passed (`--run-benchmarks`), and a real workflow (File Input -> Duplicates ->
Workpaper Output, with a Comment) was run from the editor harness and through
`trigger-designer-cli run --output-dir`; the resulting workbooks were read back with `openpyxl`
and are the ones quoted in the user guide. Pages name modules and functions rather than line
numbers; if a page and the code disagree, fix the page in the same change that fixed the code.
