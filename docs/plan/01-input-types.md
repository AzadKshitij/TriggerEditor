# 01 - More input types for File Input

Status: implementation plan. Owner of: `src/trigger_designer/core/inputs.py`, `src/trigger_designer/core/input_source.py`,
and the extension of `src/trigger_designer/qt/widgets/nodes/InOut/file_input.py`.
Read `docs/plan/00-codebase-brief.md` first (called "the brief" below). Section numbers like "brief 3.3" refer to it.
All commands are PowerShell from the repo root. Never run bare `pytest` or `uv sync` (brief 2.2, 2.4).

Decision rule used everywhere in this plan: every choice is made here with a one-line reason. If you hit a
case this plan does not cover, apply the closest rule and add a row to the edge-case table in the PR description.

---

## 1. Goal and non-goals

### 1.1 Goal

File Input (`input.file_input`, brief 7.1) becomes the single node that loads:

| # | Capability | Summary |
|---|---|---|
| a | Folder / glob | One table from every matching file in a folder or glob pattern. Adds a source-file column (name configurable, off switch). Deterministic order. Schema differences are unioned by column name (missing -> null), reported per file in the node UI and as a structured `SourceReport`. Include/exclude patterns, optional recursion. |
| b | Parquet | `.parquet`, lazy via `pl.scan_parquet`. |
| c | JSON / NDJSON | `.json` (array of records, eager) and `.ndjson`/`.jsonl` (lazy `pl.scan_ndjson`). |
| d | SQLite / DuckDB files | Pick a table or write a SELECT. Read-only enforced by the engine, never network. |
| e | Multi-sheet Excel | One sheet (today), all sheets, or chosen sheets, plus an optional sheet-name column. |

Also delivered for other plans: `ResolvedFile` + `resolve_input_files()` (plan 02, 08), structured `InputReadError`
that names file / sheet / column (plan 03), a relative-path storage rule with a minimal helper (plan 08 may replace it).

### 1.2 Non-goals (decided, not open)

* No new node and no new enum member. Reason: the op id `input.file_input` stays stable; legacy `.tds` load untouched.
* No network databases (Postgres, SQL Server, ...), no cloud/URL sources, no S3/HTTP globs. Reason: product owner scoped this phase to files.
* No write access to databases. No `ATTACH`, no extensions, no `COPY`.
* No CSV type inference. CSV stays string-everything. Reason: downstream Select/Formula behaviour must not change (brief 7.1).
* No CSV encodings beyond `utf8` and `utf8-lossy` (Polars supports only these). Latin-1 files: user picks `utf8-lossy` (documented in tooltip).
* No per-file different settings (all files in one node share delimiter/sheet/etc.). Reason: monthly exports are homogeneous; mismatches are reported, not configured.
* No change to File Output, Run orchestration, `NodeExecutor`, or plan 02/03/08 modules.
* No cancellation / progress UI for slow reads (brief 4.2: not wired anywhere).
* No `xlsxwriter` work (that is export, plan 06). Reading uses `fastexcel` 0.21.0 (installed, declared) - nothing new to install. `openpyxl` 3.1.5 is installed but this plan does not use it in `src/` (only tests use it to *create* `.xlsx` fixtures).

---

## 2. Current state (verified 2026-10-21, `file_input.py` is 941 lines)

| Fact | Where |
|---|---|
| Settings schema: `filePath, file_type, record_limit, output_filename_as_field, delimiter, first_row_contains_field_names, selected_sheet, available_sheets, start_row, schema_snapshot, file_metadata` | `file_input.py:46-58` |
| Class attributes duplicated in `__init__`; unit tests build the content with `FileInputContent.__new__` and set only the legacy attributes (so new attributes MUST have class-level defaults) | `file_input.py:60-92`; `tests/unit/test_workflow_serialization.py:88-110` |
| Type detection by extension only: xlsx/xls -> excel, txt -> txt, everything else -> csv | `file_input.py:468-479` |
| Browse dialog: one file, filter csv/txt/xlsx/xls | `file_input.py:429-466` |
| CSV live scan = `pl.scan_csv(path, infer_schema=False[, separator][, has_header=False])`, `.head(record_limit)`, optional `with_columns(pl.lit(basename).alias("FileName"))` | `file_input.py:632-650` |
| Excel live read is eager (`fastexcel.read_excel(...).load_sheet(...).to_polars().lazy()`); dtypes inferred; fallback `pl.read_excel(path, sheet_id=0)`; failure -> empty DataFrame | `file_input.py:567-630` |
| `loadFile` collects `head(10)` just to test emptiness and sets `self.data = pl.DataFrame()` if zero rows (schema lost) | `file_input.py:693-737` |
| `get_code()`: csv/txt scan, excel via fastexcel; `separator='{self.delimiter}'` and `idx_or_name='{self.selected_sheet}'` are unescaped interpolations | `file_input.py:739-841` (esp. `:760`, `:795`) |
| `check_file_path` only does `os.path.exists`; missing file -> tooltip, empty frame | `file_input.py:307-325` |
| `serialize()` re-reads the file (`_refresh_saved_input_metadata`) - I/O at save time | `file_input.py:352-363, 843-845` |
| `validate_loaded_state` re-reads the file and diffs `schema_snapshot`; Excel sheet check via fastexcel | `file_input.py:365-427` |
| Controls use `registerInputWidget` = whole-scene snapshot undo (brief 1.4 SURPRISE); text path emits `evaluate` on every keystroke | `file_input.py:140, 171, 182, 193, 203, 217, 261-267` |
| `processInputs` returns `[{"data": content.data, "variable_name": content.variable_name}]` | `file_input.py:905-928` |
| No relative paths: `filePath` is absolute in `.tds`; `Scene.saveToFile` calls `serialize()` BEFORE it sets `scene.filename` (so on Save-As the scene still holds the OLD or no filename); `loadFromFile` sets `scene.filename` BEFORE `deserialize()` | `.venv\Lib\site-packages\nodeeditor\node_scene.py:621-638, 640-660` |
| `TriggerScene.filename` is the attribute used by load; `TriggerScene` does not override `saveToFile` (plan 09 F-F adds `workflow_dir`, `_save_target` and the override) | `src/trigger_designer/qt/performance_scene.py:166-180` |
| Select shows dtypes from `frame_schema`; "Reset Types" restores the source-schema dtype; "Auto-Detect Types" first casts the column to `String` | `Preparation/select.py:560-573, 616` |
| `fastexcel` 0.21.0, `polars` 1.44.2, `duckdb` 1.5.5, stdlib `sqlite3` (SQLite 3.50.4) installed. `pl.concat(..., how="diagonal_relaxed")`, `scan_parquet`, `scan_ndjson`, `read_database(query, sqlite3_conn)`, `duckdb.connect(path, read_only=True)` all verified to work | probed in this repo's venv |
| Verified Polars behaviour used below: duplicate CSV header `id,id` -> `id`, `id_duplicated_0`; UTF-8 BOM is stripped; 0-byte CSV raises `NoDataError` at `collect_schema()`; header-only CSV -> schema with 0 rows; invalid UTF-8 raises `ComputeError: invalid utf-8 sequence` at collect; `encoding="utf8-lossy"` accepted | probed |
| Verified DB engine behaviour: sqlite `mode=ro` URI + authorizer denies `DROP`; DuckDB `read_only=True` rejects `DROP`; DuckDB `SET enable_external_access=false` rejects `read_csv('a.csv')` and `COPY ... TO` | probed |

---

## 3. Final design

### 3.1 Module layout (Qt-free first, brief 10.1)

```
src/trigger_designer/core/inputs.py         paths, listing, ordering, ResolvedFile, errors, constants   (NO polars read calls)
src/trigger_designer/core/input_source.py   readers, union, report, db access, build_source()           (polars/duckdb/sqlite3/fastexcel; NO Qt)
src/trigger_designer/qt/widgets/nodes/InOut/file_input.py   state, dock UI, live wiring, get_code()
src/trigger_designer/resources/qt/images/node_icons/ui/files.svg   new glyph
src/trigger_designer/qt/resources.json                       +icon_files
tests/support/input_fixtures.py             deterministic fixture generators (section 6.1)
```

Why two core modules: `inputs.py` is imported by plans 02/08 for `ResolvedFile` and must stay light (no heavy readers at import).

### 3.2 Settings model (serialization keys and defaults)

All new keys are added to `FileInputContent.serialized_state_schema`; legacy keys are unchanged. Missing keys take the default
(brief 3.5), so old files load without migration code. Types in a class-level attribute block (section 4 step 6) so `__new__`-built
instances work.

| Key | Default | Meaning / reason |
|---|---|---|
| `filePath` (legacy) | `""` | File, folder or glob pattern, **absolute** when written (old app versions still read it). |
| `filePathRel` | `""` | Same target relative to the `.tds` folder, POSIX separators. `""` when not computable (different drive, unsaved workflow). |
| `input_schema_version` | `1` | Content schema. Legacy files lack it -> 1. `serialize()` writes `2`. Used only for logging/migration hooks (see 3.3). |
| `file_type` (legacy, extended) | `"csv"` | One of `csv, txt, excel, parquet, json, ndjson, sqlite, duckdb`. |
| `record_limit` (legacy) | `0` | `0` = all rows. Applied after the union (so deterministic). Now has a UI spin. |
| `output_filename_as_field` (legacy) | `False` | On/off for the source-file column (kept as the switch; name preserved so old files keep working). |
| `file_name_column_name` | `"FileName"` | Column name. Same as legacy hard-coded name. |
| `file_name_value` | `"name"` | `"name"` (basename), `"path"` (absolute path as read), `"relative"` (path relative to the folder root, POSIX; equals name for single/pattern). `"relative"` exists because recursive folders repeat basenames. |
| `include_patterns` | `[]` | Folder mode only. `[]` = defaults of the chosen `file_type` (table in 3.4). Case-insensitive fnmatch on the file name. |
| `exclude_patterns` | `["~$*", ".*", "Thumbs.db", "desktop.ini"]` | Applied in folder and pattern mode to the file name. Defaults drop Excel lock files (`~$x.xlsx`) and hidden/system files. |
| `recursive` | `False` | Folder mode: walk subfolders (symlinked directories are never followed). |
| `file_order` | `"name"` | `"name"` = natural order of the relative path; `"modified"` = mtime ascending then name. This IS the state rule printed in the UI tooltip. |
| `schema_mismatch` | `"union"` | `"union"` or `"error"` (strict: first difference stops the read with `InputReadError(kind="schema_mismatch")`). Auditors may want strict. |
| `on_file_error` | `"stop"` | `"stop"` = first unreadable file fails the node; `"skip"` = skip it and record it in the report. |
| `max_files` | `10000` | Safety cap; more matches -> `InputReadError(kind="too_many_files")`. |
| `encoding` | `"utf8"` | `"utf8"` or `"utf8-lossy"` (csv/txt only). Default = today's Polars behaviour. |
| `read_as_text` | `False` | Non-CSV sources only: cast every column to `String` (escape hatch to behave like CSV). |
| `json_nested` | `"text"` | `"text"` or `"keep"`. `"text"` turns Struct/List columns into JSON strings so File Output CSV does not fail; `"keep"` leaves Polars nested dtypes. |
| `sheet_mode` | `"one"` | Excel: `"one"` (legacy, uses `selected_sheet`), `"all"`, `"chosen"` (uses `selected_sheets`). |
| `selected_sheets` | `[]` | Excel `chosen` mode. A name missing in some file -> that (file, sheet) is reported as `sheet_missing`; with `on_file_error="stop"` it fails. |
| `add_sheet_name_column` | `False` | Excel: add the sheet name column. The UI turns it on when the mode becomes `all`/`chosen`. |
| `sheet_name_column_name` | `"SheetName"` | Column name. |
| `db_mode` | `"table"` | sqlite/duckdb: `"table"` or `"query"`. |
| `db_table` | `""` | Table name (table mode). |
| `db_query` | `""` | One SELECT statement (query mode). |
| `delimiter`, `first_row_contains_field_names`, `selected_sheet`, `available_sheets`, `start_row`, `schema_snapshot`, `file_metadata` | unchanged | Legacy. `file_metadata` gets extra keys for multi-file (3.8). |

Not persisted (runtime only): `last_report: SourceReport | None`, `last_error: InputReadError | None`.

### 3.3 Migration and compatibility rules

1. No new op id, no new enum member, `WORKFLOW_SCHEMA_VERSION` stays `2` (additive keys; brief 3.5 says no bump). Reason: a bump would require a migration branch nobody needs.
2. Legacy content (no `input_schema_version`) loads as version 1 with all new keys at defaults = exactly the old behaviour.
3. `FileInputContent.deserialize` ends by calling `migrate_file_input_state(self)`; for version 1 it does nothing except set `self.input_schema_version = 1` (hook for future). `serialize()` always writes `2`.
4. v1-format workflow files (no `op`, `node_code` ints; brief 7.3) already map to `input.file_input` via `V1_OPCODE_TO_OP`; nothing changes.
5. **Legacy single-file CSV/TXT/Excel code generation is byte-identical** (section 3.7). A characterization test pinned BEFORE any change enforces it (step 0).
6. New file types in a `.tds` opened by an OLD app version: `file_type="parquet"` falls to the old `else` branch (scan_csv) - degraded but no crash. Acceptable; documented in pitfalls.

### 3.4 File type table

| `file_type` | Extensions (auto-detect) | Default folder include | Reader | Lazy? |
|---|---|---|---|---|
| `csv` | `.csv`, `.tsv`, unknown | `*.csv` | `pl.scan_csv(infer_schema=False, ...)` | yes |
| `txt` | `.txt` | `*.txt` | same, own type kept for legacy | yes |
| `excel` | `.xlsx .xlsm .xls` | `*.xlsx *.xlsm *.xls` | `fastexcel` -> `.lazy()` | no (eager per sheet) |
| `parquet` | `.parquet .pq` | `*.parquet *.pq` | `pl.scan_parquet` | yes |
| `json` | `.json` | `*.json` | `pl.read_json(...)`.lazy() (array of records or object with list values) | no |
| `ndjson` | `.ndjson .jsonl` | `*.ndjson *.jsonl` | `pl.scan_ndjson` | yes |
| `sqlite` | `.db .sqlite .sqlite3` | n/a (single file only) | stdlib `sqlite3` -> `pl.read_database` | no |
| `duckdb` | `.duckdb .ddb` | n/a (single file only) | `duckdb.connect(read_only=True)` -> `.pl()` | no |

Auto-detect only runs on Browse and when the path field changes while `file_type` has never been chosen by the user for this
path; the Type combo always overrides. A `.db` file is ambiguous (SQLite vs DuckDB): detect by the 16-byte SQLite header
`b"SQLite format 3\x00"` -> `sqlite`, otherwise `duckdb`.

### 3.5 Typed formats and Select (the interaction, stated once)

* CSV (and TXT) remain all-`String` (`infer_schema=False`). Unchanged.
* Parquet, JSON, NDJSON, SQLite, DuckDB and Excel (already today) deliver **native dtypes**. `frame_schema()` reports them; Select shows
  them as the column's source dtype; "Reset Types" restores that native dtype; "Auto-Detect Types" casts to `String` first so it works on any source
  (`select.py:560-573, 616`). Formula/Filter run in DuckDB, where `TRY_CAST(typed AS DOUBLE)` is a no-op-compatible cast, so the repo's existing
  `TRY_CAST` workflows keep working on typed data.
* The escape hatch is `read_as_text=True` (casts every column to `String`; nested columns stringified first). Use it when a workflow was authored against a CSV and you swap the source for a parquet of the same data.
* Multi-file union of typed files: per-column dtype conflicts are resolved by rule R-DTYPE (3.6).

### 3.6 Core algorithm: listing, ordering, union, reporting

**Source modes** are derived, never stored (reason: no desync with `filePath`, CLI overrides of `filePath` keep working):

```
effective_mode(path_text, base_exists):
    p = path_text.strip()
    if p is a directory                      -> "folder"
    elif has glob chars (* ? [) and p does not exist literally -> "pattern"
    else                                    -> "single"
```
`sqlite`/`duckdb` + `folder`/`pattern` -> `InputReadError(kind="unsupported_source")` ("Database sources take exactly one file").

**Listing** (`core/inputs.py::list_source_files`) returns `FileListing(files, mode, root, excluded_count, warnings)`:

* `folder`: root = the directory; candidates = files directly inside (or the whole tree if `recursive`); keep when `name` matches any include pattern (defaults from 3.4 when `include_patterns==[]`) and no exclude pattern.
* `pattern`: root = longest leading directory part without glob chars; the remainder is compiled by `glob_to_regex` (`**` = any depth incl. zero dirs, `*` = anything except `/`, `?` = one char except `/`, `[...]` classes) and matched against the POSIX relative path, case-insensitively; exclude patterns then apply to the name. `include_patterns` is ignored in pattern mode (UI hides it).
* `single`: the one path, no filtering (explicit file always honoured, even if it matches an exclude pattern). Missing -> kind `file_not_found`.
* Directories are never returned. Symlinks to files are followed; symlinked directories are not descended (loop safety). Broken symlinks are skipped with a warning string. Name comparison is case-insensitive on every OS (reason: identical results Windows/Linux, "Jan.CSV" works).
* Natural order key: `natural_key(rel_posix)` = tuple of (int part or lower-cased str part) so `part_2` < `part_10`; ties broken by the raw string. `file_order="modified"`: key `(mtime_ns, natural_key)`.
* More than `max_files` -> `too_many_files`. Zero files -> `no_match` (an *error*, not an empty frame: auditors must not silently process nothing).

**Reading** (`core/input_source.py::build_source`):

1. `settings = SourceSettings.from_state(state)`; validate.
2. Listing -> `ListedFile` list. For each file in order, preflight `open(io_path, "rb").close()` -> classify `PermissionError`/winerror 32/5 as `locked`, `FileNotFoundError` as `file_not_found`, other `OSError` as `unreadable`.
3. For each readable (file, sheet): `part = reader(...)` returns a `LazyFrame` (or eager frame `.lazy()`), then `columns = part.collect_schema()` (header only; for CSV this reads the first lines) - an exception here is classified (`empty_file`, `parse`, `encoding`, `sheet_missing`, `unreadable`).
4. Per part failure: `on_file_error="stop"` -> raise `InputReadError` naming `path` (+ `sheet`, `column` when extractable); `"skip"` -> add `FileReport(status="skipped", error=...)`, continue. If every part is skipped -> raise `no_readable_files`.
5. Reference columns = columns of the first OK part. For each part compute `missing_columns` (in union, not in part) and `extra_columns` (in part, not in reference). `differs = bool(missing or extra)`.
6. `schema_mismatch="error"` and any `differs` -> raise `schema_mismatch` naming the first differing file and column.
7. **R-DTYPE** (dtype conflicts, deterministic): for each column name present in >1 part with unequal dtypes: if all dtypes are numeric (ints/floats) leave to Polars supertype; otherwise cast that column to `String` in every part that has it; record the column in each affected `FileReport.dtype_conflicts`. CSV is all-`String`, so this only fires for typed formats and Excel.
8. Add the file-name column (`pl.lit(<value>).alias(name)`) to each part **before** concat (value depends on the part), then the sheet column. If the name already exists in a part -> raise `column_conflict` naming the column (the legacy path overwrote silently; the new path refuses).
9. `frame = pl.concat(parts, how="diagonal_relaxed")` when more than one part, else the single part. Missing columns become null. Column order = first appearance across parts in file order (this is what `diagonal` does) - deterministic.
10. `record_limit > 0` -> `.head(n)`. `read_as_text` -> `pl.all().cast(pl.String)`. `json_nested="text"` -> stringify Struct/List columns (before the text cast).
11. Return `SourceResult(frame=LazyFrame, report=SourceReport)`.

Typical lazy plans stay lazy (csv/parquet/ndjson). Excel, JSON (array), sqlite and duckdb are eager per part and wrapped `.lazy()` (same as today's Excel).

**Structured errors** `InputReadError(Exception)` (in `core/inputs.py`):

```python
@dataclass-like fields: kind, message, path, sheet, column, technical, cause_type, code
kinds -> plan-03 code (field `code`; full table with titles/hints below):
  file_not_found -> TD-IN-001   no_match -> TD-IN-001    permission -> TD-IN-002   locked -> TD-IN-002
  sheet_missing -> TD-IN-003    encoding -> TD-IN-004    empty_file -> TD-IN-005
  parse -> TD-IN-010            unreadable -> TD-IN-011  too_many_files -> TD-IN-012  db_error -> TD-IN-013   config -> TD-IN-014
  schema_mismatch -> TD-SCH-011 column_conflict -> TD-SCH-010
  unsupported_source, no_readable_files -> TD-IN-014 (config);  db_forbidden -> TD-IN-013 (db_error)   (`technical` keeps the exact kind)
  corrupt workbook (not a valid .xlsx/.xls) -> TD-IN-006      ragged CSV rows (if ever detected) -> TD-IN-007
str(err) == plain sentence that always contains the file name:  "Cannot read 'D:\\x\\Jan.csv': the file is open in another program."
err.as_dict() -> JSON-safe dict of the fields.
```
**Codes owned by plan 03 (numbers fixed jointly; plan 03 pastes this table into its error table).** `InputReadError.kind` is the key; plan 03's
`translate_exception` returns `NodeError(code=err.code, title, hint, ...)`. Existing plan 03 codes keep their meaning (004 = "not UTF-8 text", 006 = corrupt xlsx,
007 = ragged CSV, SCH-002 = duplicate column name, SCH-003 = reserved drift warning); this plan uses them only where that meaning fits and adds the new numbers.
Duplicate column names inside one file are noted in the report as a warning with note code TD-SCH-002, never as a failure.

| kind | code | title (plain language) | hint |
|---|---|---|---|
| `file_not_found`, `no_match` | TD-IN-001 | I could not find the input file(s) | Check the file, folder or pattern still exists, or pick it again. |
| `permission`, `locked` | TD-IN-002 | The input file is open in another program or not allowed | Close the file (Excel often locks it) and run again. |
| `sheet_missing` | TD-IN-003 | A worksheet I was asked to read is missing | Pick an existing sheet in File Input. |
| `encoding` | TD-IN-004 | The file is not UTF-8 text | Set Encoding to "UTF-8 (replace bad bytes)" in File Input. |
| `empty_file` | TD-IN-005 | The input file is empty | Check the export finished; remove the file or choose "Skip and report". |
| corrupt workbook | TD-IN-006 | The workbook is damaged or not an Excel file | Open and re-save it in Excel, or re-export it. |
| ragged CSV | TD-IN-007 | Some CSV rows have a different number of columns | Check the delimiter and quoting of the export. |
| `parse` | TD-IN-010 | I could not read the data in this file | Check the file type and delimiter; the details name the column. |
| `unreadable` | TD-IN-011 | The input file could not be opened | Check the path and your access rights. |
| `too_many_files` | TD-IN-012 | The folder matches too many files | Narrow the include pattern or raise "Max files". |
| `db_error`, `db_forbidden` | TD-IN-013 | The database could not be read as requested | Check the table name and use a single SELECT statement; databases are read-only. |
| `config`, `unsupported_source`, `no_readable_files` | TD-IN-014 | The File Input settings need attention | Open File Input and fix the highlighted setting. |
| `column_conflict` | TD-SCH-010 | An added column name already exists in the data | Rename the filename/sheet column in File Input. |
| `schema_mismatch` | TD-SCH-011 | Files in the folder have different columns | Use "Union by name" or fix the odd file named in the details. |

The Excel "not a valid workbook" case (`CalamineError ... invalid Zip archive`) is `kind="parse"` whose `code` property returns `TD-IN-006` when `technical`
contains `invalid Zip archive` or `EOCD`; `test_not_a_workbook` asserts `.code == "TD-IN-006"`.
Import rule: `from trigger_designer.core.errors import ...` (the package `core/errors/` from plan 03, not the single `core/errors.py` the brief and older docs mention).
This plan does NOT import `core.errors`: `InputReadError` carries a string `code`, so there is no import cycle and plan 03 may land in either order.
Plan 03 owns the File Input tooltip text (see 3.7); this plan supplies only the structured `InputReadError`/`SourceReport`.

`diagnose_collect_error(exc, report) -> InputReadError` (also in `input_source.py`): for failures that only surface at `collect()` (body parse errors, bad UTF-8 deep in a file) it scans `str(exc)` for any `report` file path/basename and for `column "x"`/`'x'`, and returns an `InputReadError(kind="parse"|"encoding")` naming the file/column when found, else `kind="parse"` with the whole report path list in `technical`. Plan 03 calls it from its translator; this plan only provides and tests it. Limitation (documented): a body-level error is not known until `collect()`; live/Run cannot name the file without it.

**ResolvedFile** (`core/inputs.py`, fields per brief 11.3 plus defaulted extras):

```python
@dataclass(frozen=True)
class ResolvedFile:
    path: str                    # absolute, as read
    exists: bool
    kind: str                    # file_type value
    sheet: str | None = None
    size_bytes: int | None = None
    modified_time: str | None = None     # ISO-8601 UTC "2026-10-21T08:15:00Z"
    sha256: str | None = None            # only when hash=True
    relative_path: str = ""              # to folder root; "" for single files
    detail: str = ""                     # sqlite/duckdb: table name or "query"
resolve_input_files(content_state: dict, *, base_dir: str | None = None, hash: bool = False) -> list[ResolvedFile]
```
Never raises: on listing errors it returns `[ResolvedFile(path=<path text>, exists=False, kind=...)]`. Excel with `sheet_mode != "one"`
returns one entry per (file, sheet) (opening the workbook with `fastexcel`; failure -> one entry, `sheet=None`). `hash=True` streams SHA-256
in 1 MiB chunks, once per file.

### 3.7 Code generation and the two evaluation paths

Principle: **live and Run use the same builder for everything new**, so they cannot disagree.

```
content._use_legacy_path()  ->  True when ALL hold:
    effective_mode == "single" and file_type in {"csv","txt","excel"}
    and encoding == "utf8" and not read_as_text and record fields only legacy ones
    and file_name_column_name == "FileName" and file_name_value == "name"
    and (file_type != "excel" or sheet_mode == "one")
```
* **Legacy path (True):** live uses the existing `_scan_csv_full` / `_read_excel` code, Run uses the existing `get_code()` body, both untouched.
* **Builder path (False):**
  * Live: `check_file_path()` -> `build_source(state)` -> `self.data = result.frame`, `self.last_report = result.report`; `InputReadError` -> tooltip `str(err)`, `markInvalid(True)`, `self.data = pl.DataFrame()`, `self.last_error = err`. No `head(10).collect()` (schema only; zero-row data keeps its columns).
  * **Tooltip ownership:** `_set_input_error_tooltip(err)` (default `grNode.setToolTip(str(err))`) and `_set_input_report_tooltip(report)` (default: `report.summary()` when files were skipped or differ, else clear) are two thin methods. **Plan 03 owns the File Input tooltip builder and replaces these two methods**; this plan supplies only the structured `InputReadError` / `SourceReport` and keeps the defaults so it works standalone.
  * Run: `get_code()` emits (pure, idempotent, always defines the variable):

```python
import polars as pl
from trigger_designer.core.input_source import build_source
# File Input: folder of CSV files (builder path)
_spec_<id> = {<repr of self.source_spec()>}
try:
    var_file_input_<id> = build_source(_spec_<id>).frame
except Exception:
    var_file_input_<id> = pl.DataFrame()
    raise
```
    `source_spec()` returns `{key: value}` for every key in `SOURCE_KEYS` (all schema keys except `schema_snapshot, file_metadata, available_sheets, filePathRel, input_schema_version`) with `filePath` already resolved to an absolute path. `repr()` of a dict of str/int/bool/list is safe (no unescaped interpolation). The helper is importable in `exec()` and in `check_output.py` (its header puts `src/` on `sys.path`, brief 4.2).
  * `InputReadError` raised inside `exec` becomes `NodeExecutionError(str(exc))` -> `ExecutionResult.error` = plain sentence with the file name (plan 03 will preserve the object).
* Both paths: `processInputs` is unchanged except that `check_file_path()` is routed as above; `Run` re-reads from disk (generated code runs `build_source` itself); live `eval` caching rules are unchanged (brief 4.1).

### 3.8 Paths: relative storage with absolute fallback (minimal helper)

`core/inputs.py` (plan 08 owns a general helper later and may replace these three functions; keep the names so a swap is mechanical):

```python
def to_stored_paths(abs_path: str, workflow_dir: str | None) -> tuple[str, str]:
    """(absolute, relative-or-"")  relative uses '/' and only when same drive and workflow_dir known."""
def resolve_stored_path(abs_path: str, rel_path: str, workflow_dir: str | None) -> str:
    """Relative first (if rel_path and workflow_dir and the target exists), else the absolute path."""
def io_path(path: str) -> str:
    """Windows long-path safe form: prefix \\\\?\\ (UNC: \\\\?\\UNC\\) when len(abspath) > 240 on win32; identity elsewhere."""
```
Rules:
* **Write** (`serialize()`): `filePath` stays absolute; `filePathRel` = relative path to `scene.workflow_dir` (provided by plan 09 F-F, 3.9) else `""`. For a glob pattern the relative form is computed on the pattern string (the glob chars survive `os.path.relpath`; computed with the directory part only and the file part re-attached).
* **Read** (`deserialize()`): `filePath = resolve_stored_path(filePath, filePathRel, scene.workflow_dir)`. Relative first because the common failure is a moved project folder; the absolute path is the fallback when the relative target does not exist. The resolved absolute value is what lives in memory and in generated code.
* The e2e `materialize()` rewrites only `filePath`; step 11 also deletes `filePathRel` there (a stale relative path would win over the rewritten absolute one).
* Existing `.tds` without `filePathRel` keep working (absolute only).

### 3.9 Scene support: provided by plan 09 F-F

`TriggerScene.workflow_dir` (property) and the `_save_target` hook, plus the single atomic UTF-8 `saveToFile` override (which also fixes BUG-002),
are **provided by plan 09 F-F**. This plan adds NO `saveToFile` override and does not edit `performance_scene.py`. Contract relied on (the attribute is named `workflow_dir` everywhere):
`scene.workflow_dir` is the folder of the `.tds` being saved (via `_save_target`, set before `serialize()` runs) or loaded (`filename`, set before `deserialize()`), else `None`.
Content reads it as `getattr(self.node.scene, "workflow_dir", None)`. Until plan 09 F-F lands, step 6 uses a temporary fallback in `file_input.py`
(`_workflow_dir(scene)`: `getattr(scene, "workflow_dir", None) or (os.path.dirname(os.path.abspath(scene.filename)) if scene.filename else None)`); the Save-As test
(`test_save_as_to_other_folder_uses_target_dir`) is `xfail(strict=False)` until F-F merges, then must pass. This plan keeps only its own load-order logic (relative first, absolute fallback, 3.8).

### 3.10 `serialize()` does no I/O; metadata

* `serialize()` stops re-reading the file. `schema_snapshot` is refreshed whenever a live load succeeds (new `_record_schema_from(frame)`); `file_metadata` is refreshed from `resolve_input_files()` (stat only, no hashing, no reads). Reason: saving a workflow pointing at 500 files must not read 500 files.
* `file_metadata` keeps legacy `size_bytes`, `modified_time` (int epoch; for single files exactly as before) and adds `file_count`, `total_size_bytes`, `newest_modified_time`.
* `validate_loaded_state()` (called at load, brief 8.1 E12): single legacy source -> unchanged behaviour. Builder path -> `build_source` once; messages: `InputReadError` text; `No files match ...`; report summary `N of M files differ in columns (first: <name>)`; drift vs `schema_snapshot` (same three messages as today, computed from `frame_schema` of the built frame).

### 3.11 Config Dock layout (per `docs/DESIGN_SYSTEM.md` §§1-7, AGENTS.md)

Main layout is the dock's (spacing 2, margins 5). Controls H30. Buttons icon-only 30x30 with tooltip + accessibleName (`IconButton` does both). No inline `setStyleSheet`; **no new objectNames except `FilesTable`'s reuse of the existing `ColumnTable`**, so no QSS edits are needed. All combos are `NoWheelComboBox`.

```
Section A  "source_section"   (ConfigSection, no title)  _undo_composite=True
  FormRow "Source"  [QLineEdit  placeholder "File, folder or pattern (D:\data\*.csv)"  accessibleName "Source path"]
                    action = container(HBox spacing 2, margins 0): [IconButton "Browse for file" (icon_folder_open)]
                                                                   [IconButton "Browse for folder" (icon_files)]
  FormRow "Type"    [NoWheelComboBox  CSV | Text | Excel | Parquet | JSON | JSON Lines | SQLite | DuckDB   accessibleName "File type"]   (visible when path set)

Section B  "files_section"   ConfigSection("Files")   visible only in folder/pattern mode      _undo_composite=True
  header count text (section.set_count): "12 files - 3 differ" (or "No files match")
  FormRow "Include"   [QLineEdit  "*.csv; *.tsv"  tooltip "Semicolon-separated name patterns. Empty = all <type> files"]   folder mode only
  FormRow "Exclude"   [QLineEdit  tooltip "Semicolon-separated name patterns to skip. Default skips Excel lock files (~$*) and hidden files"]
  [QCheckBox "Include subfolders"]                                                              folder mode only
  FormRow "Order"     [combo "Name (natural)" | "Modified date"   tooltip "Files are read in this order; 'part_2' comes before 'part_10'"]
  FormRow "Columns"   [combo "Union by name" | "Must match"       tooltip "Union fills missing columns with empty values"]
  FormRow "Bad file"  [combo "Stop with error" | "Skip and report"]
  QTableView objectName "ColumnTable" (read-only, 3 columns File | Status | Columns, row height 22, min 60 / max 160 px, no edit triggers,
        accessibleName "Files read").  Status text: "OK", "+2 columns", "missing 1", "skipped: locked", "error".
        Row tooltip = full detail (missing/extra column names, dtype conflicts, error sentence).

Section C  "settings_section"  ConfigSection()  (visible when path set)     _undo_composite=True
  [QCheckBox "Output filename as field"]  (legacy label)   tooltip "Add the source file name as a column"
  FormRow "Column name" [QLineEdit "FileName"]      visible when the checkbox is on
  FormRow "Value"       [combo "File name" | "Full path" | "Relative path"]   visible when the checkbox is on
  --- csv/txt ---   FormRow "Delimiter" (legacy), [QCheckBox "First row holds field names"] (legacy),
                    FormRow "Encoding" [combo "UTF-8" | "UTF-8 (replace bad bytes)"]
  --- excel ---     FormRow "Sheets" [combo "One sheet" | "All sheets" | "Chosen sheets"]
                    FormRow "Sheet" [combo]  (sheet_mode == one, legacy)    FormRow "Start row" [QSpinBox] (legacy)
                    ColumnChecklist of sheets (sheet_mode == chosen)   [QCheckBox "Add sheet name column"] + FormRow "Column name" [QLineEdit]
  --- json/ndjson --- FormRow "Nested values" [combo "As text" | "Keep as is"]
  --- all non-csv ---  [QCheckBox "Read all columns as text"]
  FormRow "Row limit" [QSpinBox 0..2_000_000_000 special value text "All" at 0   tooltip "0 = read every row"]

Section D  "db_section"  ConfigSection()   visible only for sqlite / duckdb      _undo_composite=True
  FormRow "Read"   [combo "Table" | "SQL query"]
  FormRow "Table"  [combo of tables] action=[IconButton "Reload table list" (icon_refresh)]     (table mode)
  [QPlainTextEdit  placeholder "SELECT ... (read-only)"  min height 90  accessibleName "SQL query"]  (query mode, debounced 300 ms)
  ConfigSection info text: "Read-only. One SELECT statement. The database is never modified."
```
`dock_layout.addStretch()` is last. `create_layout` keeps the existing guard: widgets are always built; section visibility is driven by `_apply_visibility()`.
`dock_context()` chips: file type, `"<n> files"` when n>1, `"<m> differ"` when m>0, `"all sheets"`, `"table <name>"`; label = basename of the source.

New glyph `files.svg` (16x16, same palette as `folder_open.svg`; exact content in step 9) and `resources.json` entry `"icon_files": {"path": "qt/images/node_icons/ui/files.svg", "mode": "rb"}`.
Pass `qss_fallback=":/qss_icons/dark/rc/up_arrow.png"` as the last-resort for `IconButton.themed` (never `theme_fallback`; AGENTS.md forbids `QIcon.fromTheme` - the legacy `theme_fallback="document-open"` at `file_input.py:145` is removed in this work).

### 3.12 Undo registration

* Every control is bound with `push_property_change` (fine-grained), **not** `registerInputWidget`. Each section is marked `_undo_composite = True` so the dock sweep does not also bind the children (brief 6.4: double entries).
* One generic setter on the content:

```python
def _apply_setting(self, key: str, new, text: str, *, merge_key: str | None = None, rebuild: bool = False) -> None:
    if is_syncing(self) or self.history.is_restoring_history:
        return
    old = getattr(self, key)
    if new == old:
        return
    setattr(self, key, new)
    self._after_setting_changed(key)          # recompute file_type visibility, sheets, reload data
    self.refresh_dock_context()
    self.evaluate.emit()                      # required: merged pushes skip redo() (brief 6.1)
    self.push_property_change((key,), old, new, text, rebuild=rebuild, merge_key=merge_key)
```
  History texts (`"Noun Verbed"`): `Source Path Changed` (merge_key `fi-path`), `File Type Changed`, `Include Patterns Changed` (`fi-include`), `Exclude Patterns Changed` (`fi-exclude`), `Subfolders Toggled`, `File Order Changed`, `Schema Mode Changed`, `Bad File Mode Changed`, `Filename Field Toggled`, `Filename Column Renamed` (`fi-fname`), `Filename Value Changed`, `Delimiter Changed` (`fi-delim`), `Header Row Toggled`, `Encoding Changed`, `Sheet Mode Changed`, `Sheet Changed`, `Sheets Chosen`, `Sheet Column Toggled`, `Sheet Column Renamed` (`fi-sheetcol`), `Start Row Changed` (`fi-start`), `Row Limit Changed` (`fi-limit`), `Read As Text Toggled`, `Nested Values Changed`, `Database Read Mode Changed`, `Database Table Changed`, `SQL Query Changed` (`fi-query`).
  Text controls (path, include, exclude, names, delimiter, query) commit through one shared `QTimer` per control, single-shot 300 ms (AGENTS.md live-by-default debounce); combos/checks/spins commit immediately.
* **Compound change** (Browse picks a folder: path + type + filename-field on): a content property `source_state` (getter returns `{"filePath","file_type","output_filename_as_field","selected_sheet","available_sheets"}`, setter applies the dict) and one `push_property_change(("source_state",), old, new, "Source Chosen")`. Reason: one undo step for one user action.
* `_sync_widgets_from_model()` writes every widget from the model (blockSignals pattern, brief 6.3) and calls `_apply_visibility()`. `_rebuild_widgets()` additionally refills the type/sheet/table combos and the Files table. Pass `rebuild=True` for changes of `file_type`, `sheet_mode`, `source_state`, `db_mode`.
* Because the model is the truth, restoring a path must re-resolve data: `_after_setting_changed` is also called from `_sync_widgets_from_model` through `sync_from_model` -> `evaluate` (brief 6.1), so no extra code.

### 3.13 Performance rules

* Listing is `os.scandir` based; no per-file stat beyond `st_mtime`/`st_size` (one `scandir` entry stat). 10 000 files list in well under 1 s.
* Per-file `collect_schema()` reads only the header (CSV/Parquet/NDJSON). Excel/DB/JSON array are read fully at build time (eager, as Excel is today) - documented, mitigated by `record_limit`.
* Live path never collects data (no `head(10).collect()` on the builder path). Preview collects in `preview_worker` as today.
* Builder is invoked at most once per live evaluation. The Files table reads `content.last_report` (no extra I/O).

### 3.14 Generated-code imports (stable list for plan 08's named-import policy)

The builder path of `get_code()` imports exactly these and nothing else; the list changes only with plan 08 sign-off.

| Module | Name | Used by |
|---|---|---|
| `polars` | `pl` (`import polars as pl`) | fallback `pl.DataFrame()`, all paths |
| `trigger_designer.core.input_source` | `build_source` | builder path (`from trigger_designer.core.input_source import build_source`) |

The legacy path keeps its existing imports (`polars`, `os`, and `fastexcel` for Excel) unchanged. `InputReadError` is raised inside `build_source` and never imported by generated code.

### 3.15 Keys the CLI may override (for plan 08 `PARAM_TARGETS`)

Serialization keys of the File Input `content` dict in the `.tds`. When plan 08's work-copy patcher overrides `filePath` it MUST also delete `filePathRel` (relative wins on load, 3.8).

| Key | Type | Override meaning |
|---|---|---|
| `filePath` | `str` | Single file, **folder** or **glob pattern** (mode derived from the text, 3.6) or the database file. Always paired with deleting `filePathRel`. |
| `file_type` | `str` (`csv txt excel parquet json ndjson sqlite duckdb`) | Only when the new target has a different type. |
| `include_patterns` | `list[str]` | Folder-mode name patterns (`[]` = type default). |
| `exclude_patterns` | `list[str]` | Name patterns to skip. |
| `recursive` | `bool` | Folder-mode subfolders. |
| `file_order` | `str` (`name`, `modified`) | Read order. |
| `max_files` | `int` | Safety cap. |
| `sheet_mode` | `str` (`one`, `all`, `chosen`) | Excel sheet selection mode. |
| `selected_sheet` | `str` | Excel single sheet. |
| `selected_sheets` | `list[str]` | Excel chosen sheets. |
| `db_mode` | `str` (`table`, `query`) | Database read mode. |
| `db_table` | `str` | Table name. |
| `db_query` | `str` | One SELECT statement (read-only enforced). |
| `record_limit` | `int` | Row cap (`0` = all). |
| `on_file_error`, `schema_mismatch` | `str` (`stop`/`skip`; `union`/`error`) | Failure policy. |

Not for override: `schema_snapshot`, `file_metadata`, `available_sheets`, `input_schema_version`.

**`materialize(...)` behaviour plan 08 can reuse** (`tests/support/workflows.py::materialize`, extended in step 10): copy the `.tds` JSON to a temp dir; for every File Input node (op suffix `file_input`, or title `"File Input"` for v1 files) set the given overrides in `content`; whenever `filePath` is overridden, `pop("filePathRel", None)`; touch nothing else (not `schema_snapshot`/`file_metadata`: drift messages are informational); write UTF-8. Plan 08's headless patcher must apply the same `filePathRel` rule.

---

## 4. Ordered implementation steps (small commits)

Verification block that every step ends with (substitute touched files):

```powershell
.venv\Scripts\python.exe -m ruff format <files>
.venv\Scripts\python.exe -m ruff check <files>
.venv\Scripts\python.exe -m pytest <focused tests> -q
```
Commit message form: `input: <what>` and end with the attribution line from the session reminder.

### Step 0 - Characterization tests (BEFORE changing anything)

Files: `tests/unit/test_file_input_legacy.py` (new).
Purpose: freeze today's `get_code()` text and live frames for single CSV, TXT with `;`, header-less CSV, Excel one sheet.

```python
def _legacy(tmp_path, **kw) -> FileInputContent:      # build via FileInputContent.__new__ like test_workflow_serialization._build_file_input_content
    ...
def test_legacy_csv_get_code_is_frozen():
    c = _legacy(tmp_path, filePath=str(csv), file_type="csv")
    c.id = 7                                          # SerializableContentMixin id; set explicitly so the text is stable
    assert c.get_code() == EXPECTED_CSV_CODE         # paste the string produced by the CURRENT code, with path via repr
```
Create `EXPECTED_*` by running the current code once and pasting (the path is `{filePath!r}`; compute the expectation with `repr(str(csv))`).
Also `test_legacy_serialize_keys_unchanged`: `set(content.serialize_content_state({}))` equals the 11 legacy keys exactly (this test is updated in step 6 to "legacy keys are a subset").
Done when: `.venv\Scripts\python.exe -m pytest tests\unit\test_file_input_legacy.py tests\unit\test_workflow_serialization.py -q` -> all pass on the untouched tree. Commit `input: pin legacy File Input behaviour`.

### Step 1 - `core/inputs.py`: constants, errors, natural order, glob, listing, paths, ResolvedFile

Files: `src/trigger_designer/core/inputs.py` (new), `tests/unit/test_inputs_listing.py` (new).
Imports allowed: stdlib only (`os, re, hashlib, fnmatch, dataclasses, datetime, sqlite3`-no). Must import without polars (keeps plan 02/08 light).

Public names and exact signatures:

```python
FILE_TYPES = ("csv","txt","excel","parquet","json","ndjson","sqlite","duckdb")
DEFAULT_INCLUDE: dict[str, tuple[str, ...]] = {
    "csv": ("*.csv",), "txt": ("*.txt",), "excel": ("*.xlsx","*.xlsm","*.xls"),
    "parquet": ("*.parquet","*.pq"), "json": ("*.json",), "ndjson": ("*.ndjson","*.jsonl"),
    "sqlite": (), "duckdb": (),
}
DEFAULT_EXCLUDE = ("~$*", ".*", "Thumbs.db", "desktop.ini")
GLOB_CHARS = "*?["

class InputReadError(Exception):
    def __init__(self, kind: str, message: str, *, path: str | None = None, sheet: str | None = None,
                 column: str | None = None, technical: str = "", cause_type: str = "") -> None: ...
    code: str  # property from _KIND_TO_CODE
    def as_dict(self) -> dict: ...
    # __str__ -> message

@dataclass(frozen=True)
class ListedFile: path: str; relative_path: str; size_bytes: int; mtime_ns: int
@dataclass
class FileListing: files: list[ListedFile]; mode: str; root: str; excluded_count: int; warnings: list[str]

def natural_key(text: str) -> tuple: ...
def glob_to_regex(pattern: str) -> re.Pattern: ...
def has_glob(text: str) -> bool: ...
def effective_mode(path_text: str) -> str: ...          # "single" | "folder" | "pattern" | "empty"
def detect_file_type(path_text: str) -> str: ...        # extension table 3.4; ".db" sniffs the SQLite header
def list_source_files(path_text, file_type, *, include=(), exclude=DEFAULT_EXCLUDE, recursive=False,
                      order="name", max_files=10000) -> FileListing: ...      # raises InputReadError
def to_stored_paths(abs_path, workflow_dir) -> tuple[str, str]: ...
def resolve_stored_path(abs_path, rel_path, workflow_dir) -> str: ...
def io_path(path: str) -> str: ...
@dataclass(frozen=True) class ResolvedFile: ...         # 3.6
def resolve_input_files(content_state: dict, *, base_dir=None, hash=False) -> list[ResolvedFile]: ...
```

Skeletons (copy):

```python
_NUM = re.compile(r"(\d+)")
def natural_key(text: str) -> tuple:
    return tuple((0, int(p)) if p.isdigit() else (1, p.lower()) for p in _NUM.split(text) if p != "") + ((2, text),)
```
(`(2, text)` is the raw-string tiebreak so equal-lowercase names order deterministically.)

```python
def glob_to_regex(pattern: str) -> re.Pattern:
    p = pattern.replace("\\", "/"); out = []; i = 0
    while i < len(p):
        c = p[i]
        if p.startswith("**/", i): out.append("(?:.*/)?"); i += 3; continue
        if p.startswith("**", i):  out.append(".*"); i += 2; continue
        if c == "*": out.append("[^/]*")
        elif c == "?": out.append("[^/]")
        elif c == "[":
            j = p.find("]", i + 1)
            if j == -1: out.append(re.escape(c))
            else: out.append("[" + p[i+1:j].replace("\\", "\\\\") + "]"); i = j
        else: out.append(re.escape(c))
        i += 1
    return re.compile("^" + "".join(out) + "$", re.IGNORECASE)
```

`list_source_files` walk (folder mode): use `os.scandir(io_path(dir))` iteratively; for each entry: `entry.is_dir(follow_symlinks=False)` -> descend only when `recursive`; `entry.is_file()` (follows file symlinks; broken link -> False -> add a warning) -> name tests -> `ListedFile(path=os.path.normpath(abs), relative_path=posix_rel, size_bytes=st.st_size, mtime_ns=st.st_mtime_ns)`. Include match: `any(glob_to_regex(p).match(name) for p in include_or_default)`; exclude likewise. Pattern mode: root = leading directory of the path text up to the first segment containing a glob char; walk recursively only if the pattern contains `**`, otherwise only the directory depth implied by the number of `/` in the remainder (simplest correct implementation: walk the whole tree under root when the remainder has `**`, else just `root` plus one level per remaining separator using `scandir` recursion limited by depth); match `glob_to_regex(remainder)` on the relative POSIX path. Sort per `file_order`. Raise `no_match` / `too_many_files` / `file_not_found`.

`detect_file_type`: lower-cased extension -> table; `.db` -> read 16 bytes, `b"SQLite format 3\x00"` -> `sqlite` else `duckdb`; unknown -> `csv`.

`io_path`: `if os.name == "nt" and len(p) > 240 and not p.startswith("\\\\?\\"): p = "\\\\?\\UNC\\" + p[2:] if p.startswith("\\\\") else "\\\\?\\" + os.path.abspath(p)`.

`to_stored_paths`: `try: rel = os.path.relpath(abs_path, workflow_dir).replace("\\", "/")` and `except ValueError: rel = ""` (different drive); also `rel = ""` when `workflow_dir is None` or the result starts with `..` more than 6 levels (readability; reason: absurd relatives are worse than absolute).

`resolve_stored_path`: `if rel_path and workflow_dir: cand = os.path.normpath(os.path.join(workflow_dir, rel_path)); if has_glob(cand) ? os.path.exists(os.path.dirname(cand_without_glob)) : os.path.exists(cand): return cand`; else return `abs_path`. (For patterns test existence of the non-glob directory prefix.)

`resolve_input_files`: build `state = {**DEFAULTS, **content_state}`, `path = resolve_stored_path(...)`; try `list_source_files`; each listed file -> `ResolvedFile(... modified_time = datetime.fromtimestamp(mtime, UTC).strftime("%Y-%m-%dT%H:%M:%SZ"))`; sqlite/duckdb -> one entry with `detail=` table name or `"query"`; excel with `sheet_mode != "one"` -> one entry per sheet using `fastexcel` imported lazily inside the function (wrapped in try). Hashing helper `_sha256(path)` with a per-call cache dict.

Unit tests (test names in section 6.2). Done when:
`.venv\Scripts\python.exe -m pytest tests\unit\test_inputs_listing.py -q` passes; `.venv\Scripts\python.exe -c "import sys, trigger_designer.core.inputs; print('polars' in sys.modules)"` prints `False`.
Commit `input: file listing, ordering, errors, ResolvedFile`.

### Step 2 - `core/input_source.py`: single-file readers (csv/txt/parquet/json/ndjson) + build_source skeleton

Files: `src/trigger_designer/core/input_source.py` (new), `tests/unit/test_input_source_formats.py` (new).

```python
SOURCE_KEYS = ("filePath","file_type","record_limit","output_filename_as_field","delimiter","first_row_contains_field_names",
               "selected_sheet","start_row","include_patterns","exclude_patterns","recursive","file_order","file_name_column_name",
               "file_name_value","schema_mismatch","on_file_error","max_files","encoding","read_as_text","json_nested","sheet_mode",
               "selected_sheets","add_sheet_name_column","sheet_name_column_name","db_mode","db_table","db_query")
SOURCE_DEFAULTS: dict = {...}          # one default per SOURCE_KEYS entry, values exactly as in 3.2
@dataclass(frozen=True) class SourceSettings: ...      # typed view; from_state(dict) fills defaults, validates enums -> InputReadError("config")
@dataclass class FileReport: path, relative_path, sheet, status, columns, missing_columns, extra_columns, dtype_conflicts, error, size_bytes
@dataclass class SourceReport: mode, root, file_count, ok_count, skipped_count, excluded_count, union_columns, reference_columns, warnings, files; methods as_dict(), differing_files(), summary() -> str
@dataclass class SourceResult: frame: pl.LazyFrame; report: SourceReport
def build_source(state: dict) -> SourceResult: ...
def diagnose_collect_error(exc: BaseException, report: SourceReport | None) -> InputReadError: ...
```
Part reader dispatch (one function per type, each returns a `pl.LazyFrame`):

```python
def _read_csv(path, s):   # csv/txt
    opts = {"infer_schema": False, "encoding": s.encoding}
    if s.delimiter != ",": opts["separator"] = s.delimiter
    if not s.first_row_contains_field_names: opts["has_header"] = False
    return pl.scan_csv(io_path(path), **opts)
def _read_parquet(path, s): return pl.scan_parquet(io_path(path))
def _read_ndjson(path, s):  return pl.scan_ndjson(io_path(path))
def _read_json(path, s):    return pl.read_json(io_path(path)).lazy()
```
Error classification `_classify(exc, path, sheet=None) -> InputReadError` maps: `FileNotFoundError` -> `file_not_found`; `PermissionError` or `OSError` with `winerror in (5, 32)` or message containing "being used by another process" -> `locked` (message "the file is open in another program"); `pl.exceptions.NoDataError` -> `empty_file`; message contains "invalid utf-8" -> `encoding` (hint in message: choose UTF-8 (replace bad bytes)); other `pl.exceptions.PolarsError`/`ValueError`/`OSError` -> `parse`/`unreadable`. Column extraction regex: `column\s+["']([^"']+)["']` on `str(exc)`.

`json_nested="text"` helper:

```python
def _stringify_nested(frame: pl.LazyFrame) -> pl.LazyFrame:
    schema = frame.collect_schema()
    exprs = [
        pl.when(pl.col(c).is_null()).then(None)
          .otherwise(pl.struct(pl.col(c).alias("v")).struct.json_encode().str.json_path_match("$.v")).alias(c)
        for c, dt in schema.items() if isinstance(dt, (pl.Struct, pl.List, pl.Array))
    ]
    return frame.with_columns(exprs) if exprs else frame
```
(verified: Struct `{"a":1}` -> `'{"a":1}'`, List `[1,2]` -> `'[1,2]'`, null stays null).

`build_source` in this step handles `mode == "single"` for csv/txt/parquet/json/ndjson only, plus the final record limit / text cast; other types raise `InputReadError("config", "not implemented")` temporarily (replaced in steps 3-5; delete the stub).
Done when: `.venv\Scripts\python.exe -m pytest tests\unit\test_input_source_formats.py -q` passes. Commit `input: parquet, json, ndjson readers`.

### Step 3 - Folder/pattern union, report, file-name column

Files: `core/input_source.py`, `tests/unit/test_input_source_union.py` (new).
Implement the 11 steps of 3.6 in `build_source` (pseudocode):

```python
def build_source(state):
    s = SourceSettings.from_state(state)
    listing = list_source_files(s.filePath, s.file_type, include=s.include_patterns, exclude=s.exclude_patterns,
                                recursive=s.recursive, order=s.file_order, max_files=s.max_files) if s.mode != "single" else _single_listing(s)
    parts: list[_Part] = []; reports: list[FileReport] = []
    for lf in listing.files:
        for unit in _units_for(lf, s):                 # csv etc: one unit; excel: one per sheet (step 4)
            try:
                _preflight(lf.path)
                frame = READERS[s.file_type](lf.path, unit, s)
                cols = frame.collect_schema()          # header only for lazy formats
            except Exception as exc:
                err = exc if isinstance(exc, InputReadError) else _classify(exc, lf.path, unit.sheet)
                if s.on_file_error == "stop": raise err from None
                reports.append(FileReport(..., status="skipped", error=err.as_dict())); continue
            parts.append(_Part(lf, unit, frame, cols)); reports.append(FileReport(..., status="ok", columns=list(cols)))
    if not parts: raise InputReadError("no_readable_files", "None of the <n> files could be read.", path=s.filePath)
    _compute_differences(parts, reports, s)             # missing/extra; raises schema_mismatch in strict mode
    _resolve_dtype_conflicts(parts, reports)            # R-DTYPE
    frames = [_decorate(p, s) for p in parts]           # file-name column then sheet column; column_conflict check
    frame = frames[0] if len(frames) == 1 else pl.concat(frames, how="diagonal_relaxed")
    if s.file_type == "json" ...: nested handling; read_as_text; record_limit
    return SourceResult(frame, SourceReport(...))
```
`_single_listing(s)` returns a one-file `FileListing(mode="single")` after `os.path.exists` check (`file_not_found` otherwise).
`file_name_value`: `"name"` -> `os.path.basename(path)`, `"path"` -> `path`, `"relative"` -> `lf.relative_path or basename`.
Done when: `.venv\Scripts\python.exe -m pytest tests\unit\test_input_source_union.py tests\unit\test_input_source_formats.py -q` pass. Commit `input: folder and glob union with report`.

### Step 4 - Multi-sheet Excel

Files: `core/input_source.py`, `tests/unit/test_input_source_excel.py` (new; builds `.xlsx` with `openpyxl` from `tests/support/input_fixtures.py`).

```python
def _excel_sheet_names(path) -> list[str]:                     # fastexcel.read_excel(io_path(path)).sheet_names
def _units_for(lf, s):  # excel: sheet_mode one -> [s.selected_sheet or first sheet]; all -> every sheet; chosen -> s.selected_sheets (missing -> sheet_missing error unit)
def _read_excel(path, sheet, s) -> pl.LazyFrame:
    reader = fastexcel.read_excel(io_path(path))
    skip = s.start_row - 1
    kw = {"header_row": skip} if s.first_row_contains_field_names else {"header_row": None, **({"skip_rows": skip} if skip else {})}
    if s.record_limit > 0 and s.sheet_mode == "one" and not multi_file: kw["n_rows"] = s.record_limit
    return reader.load_sheet(sheet, **kw).to_polars().lazy()
```
(For `to_polars` fallback keep `pl.from_arrow(sheet.to_arrow())` like legacy.) Excel parts inside one workbook share one `fastexcel` reader per file (cache by path within `build_source`). A `.xls`/`.xlsx` that is not a workbook (`CalamineError ... invalid Zip archive`) -> `parse` kind, message "is not a valid Excel workbook". Sheet column added by `_decorate` when `s.add_sheet_name_column`.
Done when: `.venv\Scripts\python.exe -m pytest tests\unit\test_input_source_excel.py -q` passes. Commit `input: multi-sheet excel`.

### Step 5 - SQLite and DuckDB, read-only

Files: `core/input_source.py`, `tests/unit/test_input_source_db.py` (new).

```python
def list_db_tables(path: str, kind: str) -> list[str]:
    """sorted table + view names; read-only; raises InputReadError(db_error)."""

@contextmanager
def _open_sqlite_ro(path):
    uri = "file:" + Path(os.path.abspath(path)).as_posix().replace("?", "%3f").replace("#", "%23") + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.execute("PRAGMA query_only=ON")
    ALLOWED = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_RECURSIVE}
    conn.set_authorizer(lambda action, a, b, db, trig: sqlite3.SQLITE_OK if action in ALLOWED else sqlite3.SQLITE_DENY)
    try: yield conn
    finally: conn.close()

@contextmanager
def _open_duckdb_ro(path):
    conn = duckdb.connect(os.path.abspath(path), read_only=True)
    conn.execute("SET enable_external_access=false")
    conn.execute("SET lock_configuration=true")     # the user query cannot flip the setting back
    try: yield conn
    finally: conn.close()

def _quote_ident(name: str) -> str: return '"' + name.replace('"', '""') + '"'

def _sql_for(s) -> str:
    if s.db_mode == "table":
        if not s.db_table: raise InputReadError("config", "Choose a table.", path=s.filePath)
        base = f"SELECT * FROM {_quote_ident(s.db_table)}"
    else:
        q = s.db_query.strip().rstrip(";").strip()
        if not q: raise InputReadError("config", "Write a SELECT query.", path=s.filePath)
        base = q
    if s.record_limit > 0:
        base = f"SELECT * FROM ({base}) AS _q LIMIT {int(s.record_limit)}"
    return base
```
Read: sqlite -> `pl.read_database(sql, conn)`; duckdb -> `conn.execute(sql).pl()`; both `.lazy()`. Multiple statements: sqlite raises `ProgrammingError` ("only one statement"), DuckDB `execute` runs the first or raises; add an explicit guard `_reject_multi_statement(q)`: `sqlparse` is NOT installed, so use `sqlglot` (installed, 30.20.0): `len(sqlglot.parse(q, read="sqlite"|"duckdb")) != 1` -> `db_forbidden` "Only one SELECT statement is allowed." Engine errors (`sqlite3.DatabaseError`, `duckdb.Error`) -> `db_error`; authorizer/read-only denials (message contains "not authorized" / "read-only" / "Cannot execute statement" / "file system operations are disabled") -> `db_forbidden` with message "This query tries to change data or use files, which is not allowed. Only SELECT is read." File locked by another writer (DuckDB `IO Error: Could not set lock`) -> `locked`.
Done when: `.venv\Scripts\python.exe -m pytest tests\unit\test_input_source_db.py -q` passes (includes the negative read-only tests). Commit `input: sqlite and duckdb read-only sources`.

### Step 6 - FileInputContent state, serialization, migration, paths

Files: `src/trigger_designer/qt/widgets/nodes/InOut/file_input.py`, `tests/unit/test_file_input_state.py` (new), update `tests/unit/test_file_input_legacy.py` key test.

1. Extend `serialized_state_schema` with every new key from 3.2 (`{"default": ...}`; list/dict defaults are deep-copied by the mixin).
2. Add class-level defaults for ALL new attributes right under `serialized_state_schema` (reason: `__new__`-built test instances): e.g.
```python
    input_schema_version = 1
    filePathRel = ""
    include_patterns: list = []      # NEVER mutated in place; always reassign (class-level mutable)
    ...
    last_report = None
    last_error = None
```
   The mixin deep-copies on deserialize (`setattr` with a copy) so shared class-level lists are never mutated; keep it that way (assign new lists, never `.append`).
3. `serialize()`:
```python
def serialize(self):
    state = self.serialize_content_state(super().serialize())
    abs_path, rel = to_stored_paths(self.filePath, getattr(self.node.scene, "workflow_dir", None)) if self.filePath else ("", "")
    state["filePath"] = abs_path or self.filePath
    state["filePathRel"] = rel
    state["input_schema_version"] = 2
    state["file_metadata"] = self._build_file_metadata()    # stat only, no I/O reads
    return state
```
   Remove the `_refresh_saved_input_metadata()` call from `serialize()` (3.10). `_refresh_saved_input_metadata` stays for `loadFile`.
4. `deserialize()`: after `deserialize_content_state(data)`: `self.filePath = resolve_stored_path(self.filePath, self.filePathRel, getattr(self.node.scene, "workflow_dir", None))`; `migrate_file_input_state(self)`; then the existing widget refresh code (replaced in step 9 by `_sync_widgets_from_model`).
5. `source_spec()`, `source_state` property, `_use_legacy_path()` (3.7), `resolved_input_files(self, *, hash=False)` (delegates to `resolve_input_files(self.get_serialized_state() | {"filePath": self.filePath}, base_dir=workflow_dir, hash=hash)`).
6. Scene support (`workflow_dir`, `_save_target`, `saveToFile`) is provided by plan 09 F-F (3.9); do not edit `performance_scene.py`. Add the temporary `_workflow_dir(scene)` fallback in `file_input.py` and use it instead of `getattr(self.node.scene, "workflow_dir", None)` in items 3-5.
7. `_build_file_metadata()` rewritten: single legacy -> exactly the old dict; otherwise old keys from the first file plus `file_count`, `total_size_bytes`, `newest_modified_time` (via `resolve_input_files`).

Tests (names in 6.2): round trips, defaults for legacy dict, relative-path rule, Save-As to another folder.
Done when: `.venv\Scripts\python.exe -m pytest tests\unit\test_file_input_legacy.py tests\unit\test_file_input_state.py tests\unit\test_workflow_serialization.py -q` pass. Commit `input: File Input state and relative paths`.

### Step 7 - Live path and code generation

Files: `file_input.py`, `tests/unit/test_file_input_codegen.py` (new).

* `check_file_path()`:
```python
def check_file_path(self) -> bool:
    if not self.filePath: return False
    if self._use_legacy_path():
        ...existing body unchanged...
    return self._load_via_builder()

def _load_via_builder(self) -> bool:
    try:
        result = build_source(self.source_spec())
    except InputReadError as err:
        self.last_error, self.last_report = err, None
        self.data = pl.DataFrame()
        self._set_input_error_tooltip(err); self.node.markInvalid(True)   # plan 03 replaces this builder
        self._log_missing_file(err.path or self.filePath) if err.kind in ("file_not_found", "no_match") else logger.warning(str(err))
        return False
    self.last_error, self.last_report = None, result.report
    self.data = result.frame
    self._record_schema_from(result.frame)
    self._set_input_report_tooltip(result.report)   # plan 03 replaces this builder
    self.node.markInvalid(False)
    return True
```
  (Tooltip on success shows e.g. `"3 files, 1 differs (sales_2024-03.csv: +channel)"`; empty when clean. Do not call `global_logger` per evaluation - brief 10.4 notes emoji/hot-path logging.)
* `loadFile()` builder branch: delegates to `check_file_path`-equivalent (no preview collect). Keep legacy branch intact.
* `get_code()`: at top, `if not self.filePath: <existing fallback>`; `if not self._use_legacy_path(): return self._builder_code()`; else the existing body **verbatim**.
```python
def _builder_code(self) -> str:
    var, spec = self.variable_name, self.source_spec()
    return (
        "import polars as pl\n"
        "from trigger_designer.core.input_source import build_source\n"
        f"# File Input ({spec['file_type']}, builder path)\n"
        f"_spec_{self.id} = {spec!r}\n"
        f"{var} = pl.DataFrame()\n"
        f"{var} = build_source(_spec_{self.id}).frame\n"
    )
```
  (Defining `var = pl.DataFrame()` first guarantees the variable exists even if the call raises, matching the P0-fallback rule in brief 3.4.)
* Excel one-sheet legacy path: nothing changes. Remove the unescaped `separator='{...}'`/`idx_or_name='{...}'` ONLY on the builder path (not on legacy, to keep byte-identical output; the quoting bug stays documented in pitfalls).

Done when: `.venv\Scripts\python.exe -m pytest tests\unit\test_file_input_codegen.py tests\unit\test_file_input_legacy.py -q` pass (legacy text still equal; builder code executes via `exec` and equals live). Commit `input: wire builder into live and Run paths`.

### Step 8 - validate_loaded_state and tooltips

Files: `file_input.py`, `tests/unit/test_file_input_validate.py` (new).
Rewrite `validate_loaded_state()`: if `_use_legacy_path()` -> existing body unchanged; else the builder messages of 3.10. Never raise. Reuse the legacy diff code by extracting `_diff_schema(saved_snapshot, current_dict) -> list[str]` (pure) and call it from both branches (legacy branch result must be identical; test pins it).
Done when: `.venv\Scripts\python.exe -m pytest tests\unit\test_file_input_validate.py tests\unit\test_workflow_serialization.py -q` pass. Commit `input: load-time validation for folders and databases`.

### Step 9 - Config Dock UI + undo

Files: `file_input.py` (rewrite `create_layout`, handlers, `_sync_widgets_from_model`, `_rebuild_widgets`, `dock_context`, `openFileDialog`, new `openFolderDialog`), `resources/qt/images/node_icons/ui/files.svg` (new), `qt/resources.json`, `tests/ui/test_file_input_dock.py` (new).

`files.svg` exact content:
```xml
<svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
<path d="M4 1.5h5l3 3v7.25c0 .41-.34.75-.75.75h-7.5A.75.75 0 0 1 3 11.75v-9.5c0-.41.34-.75.75-.75Z" fill="#D0D0D0"/>
<path d="M9 1.5v3h3" stroke="#14171B" stroke-width="1" stroke-linejoin="round"/>
<path d="M5.5 14.5h7.75c.41 0 .75-.34.75-.75V6.5" stroke="#8C8C8C" stroke-width="1" stroke-linecap="round"/>
</svg>
```
`resources.json`: add after `icon_folder_open`:
```json
    "icon_files":{
        "path":"qt/images/node_icons/ui/files.svg",
        "mode": "rb"
    },
```
Implementation rules:
* Build exactly the widgets in 3.11; keep attribute names the legacy tests/UI may reference: `filePathEdit`, `loadButton`, `outputFilenameCheckBox`, `delimiterEdit`, `firstRowFieldNamesCheckBox`, `selectedSheetCombo`, `startRowSpinBox`, `settings_section`, `source_section`. New: `folderButton`, `typeCombo`, `files_section`, `filesTable`, `includeEdit`, `excludeEdit`, `recursiveCheck`, `orderCombo`, `schemaCombo`, `badFileCombo`, `fileNameColumnEdit`, `fileNameValueCombo`, `encodingCombo`, `sheetModeCombo`, `sheetsChecklist`, `sheetColumnCheck`, `sheetColumnEdit`, `nestedCombo`, `asTextCheck`, `limitSpin`, `db_section`, `dbModeCombo`, `dbTableCombo`, `dbRefreshButton`, `dbQueryEdit`.
* Replace every `registerInputWidget(...)` with the `_apply_setting` pattern (3.12). Mark the four sections `_undo_composite = True`.
* Browse file: `QFileDialog.getOpenFileName` with filter `"All Supported (*.csv *.tsv *.txt *.xlsx *.xlsm *.xls *.parquet *.pq *.json *.ndjson *.jsonl *.db *.sqlite *.sqlite3 *.duckdb *.ddb);;CSV (*.csv *.tsv);;Text (*.txt);;Excel (*.xlsx *.xlsm *.xls);;Parquet (*.parquet *.pq);;JSON (*.json);;JSON Lines (*.ndjson *.jsonl);;Database (*.db *.sqlite *.sqlite3 *.duckdb *.ddb);;All Files (*)"` (the legacy code passes `options=QFileDialog.Options()` - drop it; `QFileDialog.Options` does not exist in PyQt6). Browse folder: `QFileDialog.getExistingDirectory`; on pick -> detect the most common supported extension among files directly inside (`Counter` of `detect_file_type`), set `file_type` to it (default `csv`), set `output_filename_as_field=True`, set `file_name_value="name"`, and push ONE `source_state` command.
* Path text commits after a 300 ms single-shot timer; before committing, if the text is a file and the user never chose a type for this path, call `detect_file_type`.
* When `file_type` is excel and sheets are needed: `_refresh_sheets()` calls `fastexcel.read_excel(io_path(first_file)).sheet_names` (first listed file in folder mode), sets `available_sheets`, defaults `selected_sheet` to the first when empty or no longer present, and fills `sheetsChecklist`. A failure is caught, logged with `logger.warning`, and shown as the node tooltip; it must NOT clear `filePath` (the legacy code did, `file_input.py:505-514`).
* `_refresh_db_tables()` calls `list_db_tables`; failure -> empty combo + tooltip with `str(err)`.
* Files table model: build with `QStandardItemModel` from `content.last_report.files` inside `_refresh_files_table()`; called from `create_layout`, `_rebuild_widgets`, and after every successful/failed build (`_load_via_builder` end). Guard: widget deleted -> `RuntimeError` -> ignore (pattern at brief 3.8 skeleton).
* `_apply_visibility()` owns ALL show/hide decisions as a pure function of (mode, file_type, sheet_mode, db_mode, filename-field flag, has_path); `_hide_all_options`/`_update_ui_visibility` become thin wrappers kept for backward compatibility with `deserialize`.
* Selection of a node with no file: Section A only (sections B-D hidden), as today.

Done when:
`.venv\Scripts\python.exe -m pytest tests\ui\test_file_input_dock.py -q` passes; manual smoke: `.venv\Scripts\python.exe -m trigger_designer`, drop File Input, browse a folder of 3 CSVs, confirm the Files table lists 3 rows, the third shows "+1 column", Ctrl+Z restores the previous source in one step.
Commit `input: Config Dock for folders, sheets, databases`.

### Step 10 - E2E goldens and corpus

Files: `tests/support/input_fixtures.py` (new), `tests/e2e/test_input_types_e2e.py` (new), `tests/e2e/fixtures/expected/input_*.csv` (new goldens, contents in 6.4), `tests/support/workflows.py` (materialize: also remove `filePathRel`).
Done when: `.venv\Scripts\python.exe -m pytest tests\e2e -q` -> all previous 20 + new tests pass. Commit `input: e2e goldens for new input types`.

### Step 11 - Docs

Files: `docs/NODE_REFERENCE.md` (File Input row: types, folder/glob, report, read-only DB; mention `read_as_text`), nothing else.
Done when: `git diff --stat docs/NODE_REFERENCE.md` shows only that file; run the full verification (section 8). Commit `docs: File Input input types`.

---

## 5. Edge cases (decided behaviour)

| Case | Behaviour | Test (6.2/6.3) |
|---|---|---|
| Empty folder | `InputReadError(no_match)`: "No files in 'X' match *.csv." Node invalid, tooltip shows it. Not an empty frame. | `test_empty_folder_raises_no_match` |
| Pattern with zero matches | Same `no_match`, message includes the pattern. | `test_pattern_zero_matches` |
| Path does not exist (single) | `file_not_found`; legacy path keeps its existing tooltip text unchanged (`File '<p>' does not exist`). | legacy tests |
| Unreadable / locked file | Preflight `open(rb)`; `locked`/`permission`. `on_file_error=stop` fails naming the file; `skip` records `status="skipped"` and continues; all skipped -> `no_readable_files`. | `test_locked_file_*` (uses an exclusive handle on win32; skipped on other OS via `pytest.skip`) |
| `~$tmp.xlsx` Excel lock files | Dropped by default exclude `~$*`. Explicit single path to such a file is honoured and fails with `parse` ("not a valid Excel workbook"). | `test_lock_files_excluded_by_default` |
| Mixed delimiters / headers across files | Not detected per file (one setting for the node). Wrong delimiter yields one wide column; the report shows the differing column set vs the first file, so it is visible. | `test_mixed_headers_reported` |
| Mixed encodings | Strict `utf8` fails with `encoding` naming the file at collect (via `diagnose_collect_error`); `utf8-lossy` reads all. BOM stripped. | `test_encoding_error_names_file`, `test_utf8_lossy_reads_latin1` |
| Duplicate column names inside a file | Polars renames the second `id` to `id_duplicated_0`; recorded in `FileReport.warnings`-style note `duplicate_columns` and in the report `warnings`. No failure. | `test_duplicate_column_names_renamed_and_noted` |
| Empty (0-byte) file | `empty_file` kind (`TD-IN-005`), follows `on_file_error`. Header-only file: OK, 0 rows, contributes its columns. | `test_zero_byte_and_header_only` |
| Unicode / emoji / long Windows paths | `io_path()` applies the `\\?\` prefix over 240 chars on Windows; unicode names are preserved verbatim in the file-name column. Generated code uses `repr` of the dict, so backslashes/quotes are safe. | `test_unicode_file_names`, `test_long_path_prefix` |
| Huge folders | `max_files` cap (10 000) -> `too_many_files`; listing is `scandir` only; header-only schema per file; no data collected live. Perf sanity in 6.5. | `test_too_many_files`, `test_perf_*` |
| Symlinks | File symlinks followed; directory symlinks not descended; broken link skipped + warning. Windows symlink creation needs privileges -> tests `pytest.skip` on `OSError`. | `test_symlink_file_followed`, `test_symlink_dir_not_followed` |
| Case sensitivity of globs | Always case-insensitive (our matcher, not `glob.glob`). Order key lower-cased. | `test_glob_case_insensitive` |
| Relative vs absolute `filePath` | A relative `filePath` typed by the user is made absolute against the current working directory ONLY at read time (`os.path.abspath`); stored `filePath` stays what the user typed on the legacy path. Saved files store absolute + `filePathRel`. | `test_relative_text_path_resolves` |
| Two files with identical basename (recursive) | OK; `file_name_value="relative"` disambiguates. Order uses full relative path. | `test_recursive_same_basename` |
| Output column name collides with data | `column_conflict` naming the column (builder path only). | `test_filename_column_conflict` |
| Strict schema mode with a difference | `schema_mismatch` naming first differing file and the first differing column. | `test_strict_schema_mismatch` |
| Typed dtype conflict across files (int vs text) | R-DTYPE: that column becomes `String` in all parts; listed in `dtype_conflicts`. int vs float -> `Float64`. | `test_dtype_conflict_to_string`, `test_numeric_supertype` |
| Excel sheet absent in some files (chosen mode) | `sheet_missing` for that (file, sheet): stop or skip per `on_file_error`. | `test_chosen_sheet_missing` |
| Excel file open in Excel (locked) | `locked` via preflight. | covered by locked test |
| Database file missing table / bad SQL | `db_error` with engine text in `technical`; message names the table/file. | `test_sqlite_missing_table` |
| Write attempts in SQL (`DROP`, `INSERT`, `ATTACH`, `PRAGMA writable_schema`, `COPY`, `read_csv('x')`) | `db_forbidden`; DB bytes unchanged (test hashes the file before/after). | `test_*_rejects_writes`, `test_db_file_unchanged` |
| Legacy workflow whose `file_type` is `csv` but file is `.parquet` | Unchanged (legacy path, CSV parse error). Not our concern. | n/a |
| Opened in old app version | Degrades (3.3 rule 6). | n/a |

---

## 6. Test plan

Layers: unit (`tests\unit`), ui (`tests\ui`), e2e (`tests\e2e`), benchmarks (`tests\benchmarks`, opt-in). Test files import from `tests.support.input_fixtures`
(brief 9.4 uses `from tests.support...`).

### 6.1 Deterministic fixture generator - `tests/support/input_fixtures.py` (exact contents)

```python
"""Deterministic input fixtures. Every function returns Paths and writes byte-identical files on each call."""
from __future__ import annotations
import json, sqlite3
from pathlib import Path
import duckdb, openpyxl, polars as pl

def write_text(path: Path, text: str, encoding: str = "utf-8") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode(encoding))     # bytes: no newline translation on Windows
    return path

def monthly_csvs(root: Path) -> Path:
    """Folder 'monthly' with 3 CSVs (+ noise files that must be excluded). Returns the folder."""
    d = root / "monthly"
    write_text(d / "sales_2024-01.csv", "id,region,amount\n1,N,10.50\n2,S,20.00\n")
    write_text(d / "sales_2024-02.csv", "id,region,amount\n3,N,30.25\n")
    write_text(d / "sales_2024-03.csv", "id,region,amount,channel\n4,E,40.00,web\n5,W,5.75,store\n")
    write_text(d / "~$sales_2024-04.csv", "garbage-lock-file")      # Excel-style lock file
    write_text(d / "notes.txt", "not data\n")                       # other extension
    write_text(d / ".hidden.csv", "id\n999\n")                      # hidden file
    return d

def natural_order_csvs(root: Path) -> Path:
    d = root / "natural"
    for n in (10, 2, 1):
        write_text(d / f"part_{n}.csv", f"v\n{n}\n")
    return d

def nested_csvs(root: Path) -> Path:
    d = root / "nested"
    write_text(d / "a" / "data.csv", "k\nA\n")
    write_text(d / "b" / "data.csv", "k\nB\n")
    write_text(d / "top.csv", "k\nT\n")
    return d

def parquet_files(root: Path) -> Path:
    d = root / "pq"; d.mkdir(parents=True, exist_ok=True)
    pl.DataFrame({"id": [1, 2], "amount": [10, 20]}).write_parquet(d / "p1.parquet")
    pl.DataFrame({"id": [3], "amount": [30.5], "tag": ["x"]}).write_parquet(d / "p2.parquet")
    return d

def json_files(root: Path) -> tuple[Path, Path]:
    d = root / "json"
    arr = write_text(d / "records.json", json.dumps([{"a": 1, "b": {"c": 2}, "t": [1, 2]}, {"a": 3, "b": None, "t": None}]))
    nd = write_text(d / "lines.ndjson", '{"a":1,"s":"x"}\n{"a":2,"s":"y","extra":true}\n')
    return arr, nd

def sqlite_db(root: Path) -> Path:
    p = root / "db" / "t.sqlite"; p.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(p)
    c.execute("create table sales(id integer, region text, amount real)")
    c.executemany("insert into sales values(?,?,?)", [(1, "N", 10.5), (2, "S", 20.0), (3, "N", 30.25)])
    c.execute("create view big as select * from sales where amount > 15")
    c.commit(); c.close()
    return p

def duckdb_db(root: Path) -> Path:
    p = root / "db" / "t.duckdb"; p.parent.mkdir(parents=True, exist_ok=True)
    c = duckdb.connect(str(p))
    c.execute("create table sales(id integer, region varchar, amount double)")
    c.execute("insert into sales values (1,'N',10.5),(2,'S',20.0),(3,'N',30.25)")
    c.close()
    return p

def multi_sheet_xlsx(root: Path, name: str = "book.xlsx") -> Path:
    p = root / "xl" / name; p.parent.mkdir(parents=True, exist_ok=True)
    wb = openpyxl.Workbook()
    jan = wb.active; jan.title = "Jan"; jan.append(["id", "amt"]); jan.append([1, 2.5])
    feb = wb.create_sheet("Feb"); feb.append(["id", "amt", "note"]); feb.append([2, "n/a", "x"])
    wb.save(p)
    return p

def many_csvs(root: Path, files: int, rows: int) -> Path:
    d = root / f"many_{files}x{rows}"
    for i in range(files):
        body = "id,grp,val\n" + "".join(f"{i * rows + r},{r % 7},{(r * 13) % 101}\n" for r in range(rows))
        write_text(d / f"f_{i:04d}.csv", body)
    return d
```

### 6.2 Unit tests (per function; names and key assertions)

`tests/unit/test_inputs_listing.py`
* `test_natural_key_orders_numbers` - `sorted(["part_10","part_2","part_1"], key=natural_key) == ["part_1","part_2","part_10"]`; case-insensitive: `["B","a"]` -> `["a","B"]`; equal-lowercase tiebreak deterministic (`["a","A"]` sorts the same in two shuffles).
* `test_glob_to_regex_cases` - `*.csv` matches `Jan.CSV`, not `a/b.csv`; `**/*.csv` matches `a/b/c.csv` and `c.csv`; `?` single char; `[ab]x.csv`.
* `test_glob_case_insensitive` - listing `monthly\SALES_*.CSV` returns the 3 sales files.
* `test_folder_listing_default_include_and_exclude` - `list_source_files(monthly, "csv")` -> basenames exactly `["sales_2024-01.csv","sales_2024-02.csv","sales_2024-03.csv"]`; `excluded_count >= 3`.
* `test_lock_files_excluded_by_default` / `test_exclude_override` - `exclude=()` also returns `~$sales_2024-04.csv` and `.hidden.csv`.
* `test_include_override` - `include=("sales_2024-0[12].csv",)` -> 2 files.
* `test_natural_order_folder` - natural folder -> `part_1, part_2, part_10`.
* `test_modified_order` - set `os.utime` to make `part_10` oldest -> order `part_10, part_2, part_1` with `order="modified"`.
* `test_recursive_toggle` - nested folder: `recursive=False` -> `["top.csv"]`; `True` -> 3 files, `relative_path` values `["a/data.csv","b/data.csv","top.csv"]`.
* `test_recursive_same_basename` - the two `data.csv` entries both present.
* `test_pattern_zero_matches` / `test_empty_folder_raises_no_match` - `pytest.raises(InputReadError)` with `.kind == "no_match"`, `.code == "TD-IN-001"`, path in message; plus parametrized `.code` checks: `empty_file` TD-IN-005, `parse` TD-IN-010, `unreadable` TD-IN-011, `too_many_files` TD-IN-012, `db_error` TD-IN-013, `config` TD-IN-014, `column_conflict` TD-SCH-010, `schema_mismatch` TD-SCH-011.
* `test_too_many_files` - `max_files=2` on monthly -> `too_many_files`.
* `test_single_file_ignores_exclude` - explicit `~$x.csv` path returned.
* `test_symlink_file_followed` / `test_symlink_dir_not_followed` - skip on `OSError`.
* `test_unicode_file_names` - file `données_é_日本.csv` listed and `ResolvedFile.path` round-trips.
* `test_long_path_prefix` - `io_path("C:\\" + "a"*250)` starts with `\\?\` on win32 (`pytest.mark.skipif(os.name != "nt")`), identity otherwise.
* `test_stored_paths_roundtrip` - `to_stored_paths(str(tmp/a/b.csv), str(tmp/w))` -> rel `"../a/b.csv"`; `resolve_stored_path` returns rel-target when exists; falls back to the absolute when the relative target is gone; returns absolute when `workflow_dir is None`.
* `test_to_stored_paths_other_drive` - monkeypatch `os.path.relpath` to raise `ValueError` -> rel `""`.
* `test_detect_file_type` - table incl. `.db` SQLite header -> `sqlite`, other bytes -> `duckdb`.
* `test_resolved_files_fields_and_hash` - 3 monthly files; `size_bytes` match `stat`, `modified_time` ISO ending `Z`, `sha256 is None` default and equals `hashlib.sha256(bytes).hexdigest()` with `hash=True`.
* `test_resolve_input_files_never_raises` - missing path -> one entry `exists=False`.
* `test_inputs_module_is_polars_free` - subprocess `python -I -c` import check from step 1 (`sys.modules` lacks `polars`).
* `test_input_read_error_as_dict_and_str` - str contains the file name; `as_dict()` JSON-serialisable via `orjson.dumps`; each kind maps to the expected code in 3.6.

`tests/unit/test_input_source_formats.py`
* `test_csv_single_all_strings` - `build_source` of `sales_2024-01.csv` -> all dtypes `String`; rows `[("1","N","10.50"),("2","S","20.00")]`.
* `test_csv_delimiter_and_no_header`, `test_csv_encoding_default_strict_vs_lossy` (latin-1 bytes `b"id,n\n1,caf\xe9\n"`: strict -> `.collect()` raises, `diagnose_collect_error` returns kind `encoding` with `path` of the file; lossy -> `"caf\ufffd"`).
* `test_bom_stripped`, `test_zero_byte_and_header_only` (0-byte -> `empty_file`, header-only -> 0 rows with columns).
* `test_parquet_single_typed_and_lazy` - dtype `Int64`, `isinstance(frame, pl.LazyFrame)`.
* `test_ndjson_lazy`, `test_json_array_records`, `test_json_nested_text_vs_keep` - `json_nested="text"`: `b` becomes String `'{"c":2}'`, `t` becomes `'[1,2]'`, nulls stay null; `"keep"` leaves `Struct`/`List`.
* `test_read_as_text_casts_all` - parquet `amount` becomes `String`.
* `test_record_limit_applies_after_union` (also in union file).
* `test_diagnose_collect_error_names_column` - synthetic `pl.exceptions.ComputeError('could not parse "x" in column "amount"')` -> `column == "amount"`.

`tests/unit/test_input_source_union.py` (uses `monthly_csvs`)
* `test_union_by_name_fills_missing_with_null` - columns `["id","region","amount","channel"]`, 5 rows, `channel` null for ids 1-3.
* `test_filename_column_values_name_path_relative` - `FileName` equals `sales_2024-01.csv` for ids 1,2; `"path"` value equals the absolute path; `"relative"` equals name in folder root.
* `test_filename_column_custom_name_and_off` - custom `Source` present, off -> absent.
* `test_filename_column_conflict` - a CSV already containing `FileName` -> `column_conflict` with `column == "FileName"`.
* `test_order_is_deterministic` - build twice; rows equal; shuffle mtime order has no effect under `file_order="name"`.
* `test_report_marks_differing_files` - report: 3 files, `differing_files()` names `sales_2024-03.csv` (extra `channel`) and the 2 earlier files have `missing_columns == ["channel"]`; `summary()` mentions "3 files"; `as_dict()` orjson-serialisable.
* `test_strict_schema_mismatch` - `schema_mismatch="error"` -> `kind == "schema_mismatch"`, `path` ends with `sales_2024-03.csv`, `column == "channel"`.
* `test_skip_vs_stop_on_bad_file` - add a 0-byte `sales_2024-05.csv`: `stop` -> `empty_file` naming it; `skip` -> 5 rows, report `skipped_count == 1`, status `skipped`.
* `test_dtype_conflict_to_string` / `test_numeric_supertype` - parquet folder `pq`: `amount` Int64 vs Float64 -> `Float64`, ids 1,2,3 -> amounts `[10.0,20.0,30.5]`; make a second parquet with `amount` String -> column `String`, listed in `dtype_conflicts`.
* `test_parquet_folder_missing_column_null` - `tag` null for p1 rows.
* `test_duplicate_column_names_renamed_and_noted`.
* `test_record_limit_applies_after_union` - `record_limit=4` -> 4 rows, the first four in file order.
* `test_build_is_lazy` - `isinstance(result.frame, pl.LazyFrame)`; monkeypatch `pl.LazyFrame.collect` to raise and confirm `build_source` for csv/parquet/ndjson still succeeds (only `collect_schema`).
* `test_unicode_file_name_in_column`.

`tests/unit/test_input_source_excel.py` (uses `multi_sheet_xlsx`)
* `test_one_sheet_legacy_equivalence` - `sheet_mode="one"`, `selected_sheet="Jan"` equals the legacy `_read_excel` frame for the same file.
* `test_all_sheets_union_with_sheet_column` - columns `id, amt, note, SheetName`, 2 rows; R-DTYPE: `amt` conflicts Float64 vs String -> `String` (`"2.5"`, `"n/a"`); report lists both (file, sheet) units.
* `test_chosen_sheets` - only `Feb`; `test_chosen_sheet_missing` - `["Jan","Nope"]` -> stop raises `sheet_missing` with `sheet == "Nope"`; skip -> 1 unit skipped.
* `test_excel_lock_file_default_excluded_in_folder`; `test_not_a_workbook` -> `parse` ("not a valid Excel workbook").
* `test_excel_folder_two_workbooks` - two copies named `a.xlsx`, `b.xlsx`, `file_name_value="name"`: rows from both, `FileName` set per file.

`tests/unit/test_input_source_db.py`
* `test_list_tables_sqlite_and_duckdb` - sqlite -> `["big","sales"]`; duckdb -> `["sales"]`.
* `test_sqlite_table_read_types` - `id` Int64, `amount` Float64, 3 rows; `test_duckdb_table_read_types`.
* `test_sql_query_mode_both_engines` - `SELECT region, SUM(amount) AS total FROM sales GROUP BY region ORDER BY region` -> `[("N",40.75),("S",20.0)]`; trailing `;` tolerated; `record_limit=1` wraps and returns 1 row.
* `test_sqlite_rejects_writes` / `test_duckdb_rejects_writes` - parametrized over `DROP TABLE sales`, `DELETE FROM sales`, `INSERT INTO sales VALUES (9,'x',1)`, `ATTACH 'other.db' AS o`, `PRAGMA writable_schema=1` (sqlite), `COPY sales TO 'x.csv'` (duckdb), `SELECT * FROM read_csv('a.csv')` (duckdb), `INSTALL httpfs` (duckdb): each raises `InputReadError` with `kind in {"db_forbidden","db_error"}` and never succeeds.
* `test_multiple_statements_rejected` - `SELECT 1; DROP TABLE sales` -> `db_forbidden`.
* `test_db_file_unchanged` - sha256 of the DB file before and after all the write attempts is identical.
* `test_sqlite_missing_table` -> `db_error` message names the table; `test_empty_table_name_config_error`.
* `test_db_folder_mode_unsupported` -> `unsupported_source`.
* `test_sqlite_path_with_special_chars` - a path containing `#`, space and unicode opens (URI escaping).
* `test_duckdb_locked_by_writer` - open a read-write DuckDB connection to the file, call the builder -> `kind == "locked"` (skip if the engine allows concurrent read-only reads; assert either success or `locked`, never another kind).

`tests/unit/test_file_input_legacy.py` (step 0, kept forever)
* `test_legacy_csv_get_code_is_frozen`, `test_legacy_txt_semicolon_code_frozen`, `test_legacy_no_header_code_frozen`, `test_legacy_excel_code_frozen`, `test_legacy_filename_field_code_frozen`.
* `test_legacy_live_frame_all_strings` - `_read_file_based_on_type` unchanged: dtypes `String`.
* `test_legacy_path_selection` - `_use_legacy_path()` is True for each of the above and False the moment any new option departs from its default (parametrized over `encoding="utf8-lossy"`, `read_as_text=True`, `file_name_column_name="Src"`, `file_name_value="path"`, `sheet_mode="all"`, a folder path).

`tests/unit/test_file_input_state.py`
* `test_new_keys_have_defaults_for_legacy_dict` - `deserialize_content_state(<the 11 legacy keys only>)` -> every new attribute equals the 3.2 default; `input_schema_version == 1`.
* `test_serialize_writes_schema_version_2_and_all_keys`.
* `test_file_metadata_single_file_legacy_shape` - exactly `{"size_bytes","modified_time"}` plus the new multi keys, with the legacy two equal to the old computation.
* `test_serialize_does_no_file_reads` - monkeypatch `pl.scan_csv`/`pl.read_excel`/`fastexcel.read_excel` to raise; `serialize()` succeeds.
* `test_relative_path_written_and_preferred_on_load` - content with `scene.workflow_dir = tmp/w`; serialize -> `filePathRel == "../data/a.csv"`; move the whole tree, deserialize with the new `workflow_dir` -> `filePath` points into the moved tree.
* `test_absolute_fallback_when_relative_missing`; `test_unsaved_workflow_has_empty_rel`.
* `test_save_as_to_other_folder_uses_target_dir` - real `TriggerSubWindow().scene.saveToFile(tmp/x/wf.tds)` on a scene whose `filename` is an older path -> `.tds` JSON contains `filePathRel` relative to `tmp/x` (pins plan 09 F-F's `_save_target`; xfail until F-F merges).
* `test_old_tds_without_new_keys_loads` - load `savedfiles\0. All Node- Test.tds`-style v1 content through `TriggerSubWindow.fileLoad` (uses `no_modal_dialogs`): File Input has `file_type` `csv` and default new keys.
* `test_source_spec_is_json_safe_and_complete` - `orjson.dumps(spec)` works; keys == `SOURCE_KEYS`.

`tests/unit/test_file_input_codegen.py`
* `test_builder_code_executes_and_matches_live` - folder source; `exec(get_code(), {"pl": pl}, ns)`; `ns[var].collect()` equals `content.data.collect()` (`DataFrame.equals`), incl. column order and nulls (the main live-vs-Run agreement test). Repeat for parquet, ndjson, json, excel-all, sqlite table, duckdb query.
* `test_builder_code_defines_variable_on_failure` - missing folder: `exec` raises `InputReadError`, yet `var` exists in namespace (`pl.DataFrame()`).
* `test_builder_code_is_idempotent_and_pure` - `get_code()` twice equal; no file touched.
* `test_builder_code_quotes_hostile_values` - delimiter `'`, sheet name `a'b\c`, path with `'` and `\` all round-trip through `exec` (builder path), proving no interpolation bug there.
* `test_unconfigured_node_defines_empty_frame` - unchanged fallback.

`tests/unit/test_file_input_validate.py`
* `test_validate_missing_folder_message`, `test_validate_reports_differing_files`, `test_validate_schema_drift_same_messages_as_legacy`, `test_validate_never_raises_on_bad_database`.

### 6.3 UI tests - `tests/ui/test_file_input_dock.py`

Pattern from brief 9.3 (`ConfigDock().updateConfig([node.grNode])`; for `create_layout` exceptions call it directly).
* `test_dock_builds_for_empty_node` - only Section A visible; `files_section`/`db_section`/`settings_section` hidden (`isHidden()`).
* `test_folder_pick_shows_files_section_and_table` - set `content` source to the monthly folder via `_apply_setting` helpers; `filesTable.model().rowCount() == 3`; third row status text contains `"+1 column"`; section count text `"3 files"` and `"differ"`.
* `test_visibility_matrix` - parametrized over `file_type` x mode: csv shows delimiter/encoding; excel shows sheet mode; json shows nested combo; parquet shows only as-text; sqlite shows db_section.
* `test_buttons_have_tooltip_and_accessible_name` - every `IconButton` in the dock: `toolTip()` and `accessibleName()` non-empty; no inline stylesheet: `widget.styleSheet() == ""` for every child.
* `test_no_qicon_fromtheme` - source grep: `"fromTheme" not in Path(file_input.py).read_text()`.
* `test_path_edit_debounced` - set text 5 times quickly; `qtbot.wait(400)`; exactly one evaluation (count `node.eval` calls via monkeypatch) and exactly one history entry (`history` stack count increases by 1).
* `test_undo_redo_each_setting` - for each setting in {recursive, order, schema mode, filename on, filename name, encoding, sheet mode, limit, as-text, db mode}: change via widget, `history.undo()` restores model AND widget, `history.redo()` reapplies (uses `dock.updateConfig(..., force=True)` like brief 9.3). Baseline `history.storeHistory("Baseline")` first.
* `test_folder_pick_is_one_undo_step` - simulate `_choose_folder(path)`; one `undo()` returns to the empty source (path, type, filename-field all restored).
* `test_sync_does_not_rerecord` - `with syncing(content)` style: after `undo()`, `history.canUndo()` count unchanged by the restore.
* `test_excel_sheets_checklist_chosen_mode` - `sheetsChecklist.checked()` mirrors `selected_sheets`; "All"/"None" bulk emits once.
* `test_db_table_combo_and_query_edit` - sqlite fixture: combo lists `big, sales`; switching to query mode shows the editor; typing then `qtbot.wait(400)` commits once.
* `test_error_tooltip_for_missing_folder` - node invalid, tooltip equals `str(err)` mentioning the folder.
* `test_dock_context_chips` - chips contain `"csv"`, `"3 files"`, `"1 differ"`... (wording as implemented: assert substrings `"3 files"` and `"differ"`).
* Baseline note: 20 pre-existing failures live in other ui files; run only this file plus `tests\ui\test_select_*`-free subset (section 8).

### 6.4 Golden-file E2E - `tests/e2e/test_input_types_e2e.py`

Helper builds a workflow in code (brief 9.4 skeleton: `TriggerSubWindow()`, File Input -> File Output csv, set attributes, `scene.saveToFile`, reopen via `window.fileLoad`, `run_workflow_and_wait`, `assert _run_clean`). Fixtures from `input_fixtures`. All programmatic, no checked-in `.tds`.
Because a File Input with a `filePath` set programmatically has no `last_report` before first evaluation, the helper calls `fin.content.filePath = ...`, other settings, then saves; the reload evaluates.

Golden files (`tests/e2e/fixtures/expected/<name>.csv`; exact text; compare uses `assert_frame_golden(frame, name)`, dtypes ignored, order checked):

`input_folder_union.csv` (monthly folder, csv, `output_filename_as_field=True`, defaults):
```
id,region,amount,channel,FileName
1,N,10.50,,sales_2024-01.csv
2,S,20.00,,sales_2024-01.csv
3,N,30.25,,sales_2024-02.csv
4,E,40.00,web,sales_2024-03.csv
5,W,5.75,store,sales_2024-03.csv
```
`input_glob_union.csv`: same workflow but `filePath = <monthly>\sales_2024-0[12].csv`, filename column renamed `Source` -> 
```
id,region,amount,Source
1,N,10.50,sales_2024-01.csv
2,S,20.00,sales_2024-01.csv
3,N,30.25,sales_2024-02.csv
```
`input_parquet_folder.csv` (`pq` folder, parquet, filename field on, default name):
```
id,amount,tag,FileName
1,10.0,,p1.parquet
2,20.0,,p1.parquet
3,30.5,x,p2.parquet
```
`input_json_ndjson.csv` (ndjson file `lines.ndjson`, no filename field):
```
a,s,extra
1,x,
2,y,true
```
`input_json_array_text.csv` (`records.json`, `json_nested="text"`; File Output csv quoting is produced by Polars: embedded quotes doubled):
```
a,b,t
1,"{""c"":2}","[1,2]"
3,,
```
`input_sqlite_query.csv` (sqlite, `db_mode="query"`, `SELECT region, SUM(amount) AS total FROM sales GROUP BY region ORDER BY region`):
```
region,total
N,40.75
S,20.0
```
`input_duckdb_table.csv` (duckdb table `sales`):
```
id,region,amount
1,N,10.5
2,S,20.0
3,N,30.25
```
`input_excel_all_sheets.csv` (`book.xlsx`, `sheet_mode="all"`, `add_sheet_name_column=True`):
```
id,amt,note,SheetName
1.0,2.5,,Jan
2.0,n/a,x,Feb
```
Tests:
* `test_folder_union_matches_golden` (+ asserts `execution_results` has all nodes; `no_modal_dialogs["warnings"] == []`; File Input `last_report.differing_files()` names `sales_2024-03.csv` after the load).
* `test_glob_union_matches_golden`, `test_parquet_folder_matches_golden`, `test_ndjson_matches_golden`, `test_json_array_nested_text_matches_golden`, `test_sqlite_query_matches_golden`, `test_duckdb_table_matches_golden`, `test_excel_all_sheets_matches_golden`.
* `test_workflow_moved_with_data_still_runs` - build the workflow in `tmp/proj/` (data in `tmp/proj/data`), then `shutil.copytree` to `tmp/moved/`, delete the original, open the copy: the File Input resolves via `filePathRel`, run succeeds and equals the golden (proves relative storage + absolute fallback ordering).
* `test_absolute_fallback_when_relative_missing` - corrupt `filePathRel` in the JSON; absolute still exists -> runs.
* `test_folder_run_failure_names_file` (negative) - add a locked-or-0-byte member (`sales_2024-05.csv` empty), `on_file_error="stop"`: the run fails; `window.execution_results` lacks the File Input; the node's `ExecutionResult.error` (read from the worker/`execution_history[-1]`; if not reachable, assert via `run_workflow_and_wait` returning plus `node.isInvalid()`) contains `sales_2024-05.csv`. The same workflow with `on_file_error="skip"` matches `input_folder_union.csv`.
* `test_missing_folder_negative` - folder deleted before load: `validateLoadedWorkflow()` returns a message containing the folder; node invalid; Run fails without a `NameError` (variable defined by generated fallback: assert the run's error text does not contain `NameError`).
* `test_strict_mode_run_fails_with_column` - `schema_mismatch="error"`: error text contains `channel`.
* Existing e2e (`tests\e2e\test_workflow_goldens.py`, 13 goldens) must pass unchanged = regression proof for legacy CSV workflows (and legacy `.tds` with absolute paths).

### 6.5 Performance sanity

* `tests/unit/test_input_perf_sanity.py` marked `@pytest.mark.slow`: generate `many_csvs(tmp, files=120, rows=2000)` (240 000 rows). Assertions (generous, CI-safe): listing + `build_source` (no collect) completes in < 5 s; `result.frame.select(pl.len()).collect().item() == 240000`; whole collect < 20 s; peak extra RSS delta (psutil) after collect-count < 300 MB. Also `test_listing_10000_names` - create 10 000 empty `.csv` names, `list_source_files` < 3 s.
* `tests/benchmarks/test_input_scale_benchmark.py` (opt-in `--run-benchmarks`): 1000 files x 5000 rows build+count; prints timings, asserts count only.
* Evidence that the builder is not collecting data live: `test_build_is_lazy` (6.2).

### 6.6 Regression tests proving nothing changed for legacy

* `test_file_input_legacy.py` (step 0) - generated code text and live frames frozen.
* Unchanged `tests\unit\test_workflow_serialization.py` (its `__new__`-built content proves class-level defaults).
* `tests\e2e` corpus (13 goldens, all single-file CSV) unchanged and green.
* `test_old_tds_without_new_keys_loads` (6.2).

---

## 7. Acceptance checklist

- [ ] Folder of CSVs loads into one table with `FileName` column; order is natural-by-name; `part_2` before `part_10`.
- [ ] Glob (`D:\x\sales_*.csv`) works, case-insensitively, and `**` recursion works.
- [ ] Differing columns are unioned by name with nulls; the Files table lists each file and its differences; `SourceReport` exposes the same facts (`as_dict()` JSON-safe).
- [ ] Include/exclude patterns, recursive toggle, order, strict mode, skip-bad-file all work and are undoable.
- [ ] Excel lock files (`~$*`) and hidden files never read by default.
- [ ] Parquet (lazy), NDJSON (lazy), JSON array (eager), SQLite and DuckDB (table or SELECT, read-only) load; typed dtypes show in Select; `read_as_text` casts to strings.
- [ ] Multi-sheet Excel (one / all / chosen) with sheet-name column.
- [ ] No write is possible to a database (negative tests + file hash unchanged).
- [ ] Live and Run produce equal frames (agreement tests) for every new type; generated code never raises `NameError` downstream.
- [ ] Legacy single-file CSV/TXT/Excel: `get_code()` text byte-identical (step 0 tests), e2e goldens unchanged, legacy `.tds` load.
- [ ] `.tds` stores `filePath` (absolute) + `filePathRel`; moved project folder loads; Save-As to another folder writes the right relative path.
- [ ] `serialize()` does no file reads.
- [ ] `ResolvedFile`, `resolve_input_files`, `FileInputContent.resolved_input_files(hash=...)`, `InputReadError`, `SourceReport`, `diagnose_collect_error` exist and are tested.
- [ ] Dock follows the design system: icon-only buttons with tooltip + accessibleName, no inline QSS, no `QIcon.fromTheme`, `NoWheelComboBox` for all combos, 300 ms debounce on text, history texts `"Noun Verbed"` and only on real diffs.
- [ ] `ruff format` + `ruff check` clean on every touched file (compared to the baseline: only files you touched).
- [ ] Verification commands in section 8 pass; ui baseline (20 failed / 7 errors in OTHER files) unchanged.

---

## 8. Verification commands

```powershell
$env:PYTHONIOENCODING = "utf-8"
# format + lint touched files
.venv\Scripts\python.exe -m ruff format src\trigger_designer\core\inputs.py src\trigger_designer\core\input_source.py src\trigger_designer\qt\widgets\nodes\InOut\file_input.py tests\support\input_fixtures.py tests\unit\test_inputs_listing.py tests\unit\test_input_source_formats.py tests\unit\test_input_source_union.py tests\unit\test_input_source_excel.py tests\unit\test_input_source_db.py tests\unit\test_file_input_legacy.py tests\unit\test_file_input_state.py tests\unit\test_file_input_codegen.py tests\unit\test_file_input_validate.py tests\unit\test_input_perf_sanity.py tests\ui\test_file_input_dock.py tests\e2e\test_input_types_e2e.py
.venv\Scripts\python.exe -m ruff check <the same list>

# focused
.venv\Scripts\python.exe -m pytest tests\unit\test_inputs_listing.py tests\unit\test_input_source_formats.py tests\unit\test_input_source_union.py tests\unit\test_input_source_excel.py tests\unit\test_input_source_db.py -q
.venv\Scripts\python.exe -m pytest tests\unit\test_file_input_legacy.py tests\unit\test_file_input_state.py tests\unit\test_file_input_codegen.py tests\unit\test_file_input_validate.py tests\unit\test_workflow_serialization.py -q
.venv\Scripts\python.exe -m pytest tests\ui\test_file_input_dock.py -q

# layers (never bare pytest; brief 2.4)
.venv\Scripts\python.exe -m pytest tests\unit -q          # baseline 334 passed + new tests, 0 failed
.venv\Scripts\python.exe -m pytest tests\e2e -q           # baseline 20 passed + new tests, 0 failed
.venv\Scripts\python.exe -m pytest tests\ui -q            # baseline 404 passed / 20 failed / 7 errors (pre-existing); new file adds only passes
.venv\Scripts\python.exe -m pytest tests\benchmarks --run-benchmarks -k input_scale   # optional timing

# core stays light
.venv\Scripts\python.exe -I -c "import sys, trigger_designer.core.inputs; print('polars' in sys.modules)"   # must print False
# manual smoke
.venv\Scripts\python.exe -m trigger_designer
```
Manual smoke script: new workflow -> File Input -> browse folder (`monthly`, generated by `python -c "from tests.support.input_fixtures import monthly_csvs; import pathlib; print(monthly_csvs(pathlib.Path('C:/Temp/fi')))"` run from the repo root with `$env:PYTHONPATH="."`) -> connect Select -> File Output csv -> Run -> save -> move the folder pair -> reopen -> Run again.

---

## 9. Pitfalls

1. **`__new__`-built content in tests** (`test_workflow_serialization.py:88`): every new attribute needs a class-level default; list defaults must never be mutated in place.
2. **`Scene.saveToFile` serialises before it sets `scene.filename`.** Without plan 09 F-F's `_save_target` hook, Save-As writes a relative path computed against the wrong folder (test pins it).
3. **Materialize in e2e rewrites only `filePath`.** A stale `filePathRel` wins on load (relative first) - strip it in `materialize`.
4. **Do not collect on the builder path.** The legacy `loadFile` collects `head(10)`; zero rows replaced the frame with `pl.DataFrame()` and lost the schema. The builder path must keep the schema of zero-row sources.
5. **Lazy errors surface at `collect()`.** Header-level problems are caught at build; body-level parse/encoding errors appear later with Polars' text. `diagnose_collect_error` exists for plan 03; do not promise file names for those in the UI.
6. **`pl.concat(how="diagonal_relaxed")` raises on incompatible dtypes at collect**, so R-DTYPE must run first (casts to String) - never skip it for typed formats.
7. **Excel via fastexcel infers float for integer-looking cells** (`1.0`); this is legacy behaviour and is reflected in the golden (`1.0`). Do not "fix" it.
8. **Excel/JSON-array/DB are eager.** A million-row table freezes the GUI thread during live evaluation (brief 10.4 "Live collect on GUI thread"). Mitigation shipped: Row limit spin; documented in the tooltip of the Type combo. Chunked loading is out of scope.
9. **SQLite URI paths**: `#`, `?`, `%`, spaces must be URL-escaped; always build the URI via `Path.as_posix()` plus escaping (test with special characters).
10. **DuckDB read-only needs no writer**: another process holding the file for writing makes `connect(read_only=True)` fail with a lock error -> classified `locked`.
11. **Never `os.path.exists(pattern)` for a glob.** `effective_mode` must test directory-ness first, then glob chars.
12. **Windows**: `os.scandir` yields case-preserving names; compare with lower-cased regex only. Long paths: use `io_path()` on every `open`/`scandir`/`scan_*` call inside the core modules; do not store the prefixed form anywhere.
13. **Generated code**: `repr()` of the spec dict is the only embedding mechanism on the builder path. The legacy path still has the unescaped delimiter/sheet interpolation (`file_input.py:760, 795`) - it stays because byte-identical legacy output is the regression guarantee; a `'` in a delimiter is an existing, documented bug.
14. **`QFileDialog.Options()`** does not exist in PyQt6 (legacy `openFileDialog` calls it); remove it when rewriting the dialog or the browse button raises.
15. **Dock sweep double-binding**: omitting `_undo_composite = True` on a section yields two history entries per edit (brief 6.4).
16. **`evaluate.emit()` after `_apply_setting` is mandatory**: merged pushes skip `redo()`, so without it typing in merged controls would not re-evaluate.
17. **Emoji/hot-path logging**: do not add `global_logger.info` per evaluation (brief 10.4). Use `logger.debug` sparingly.
18. **Pre-existing UI baseline**: 20 failures/7 errors elsewhere; do not touch those assertions; run only the named ui file.
19. **Old app opening new files** degrades to CSV parsing of the path (3.3 rule 6) - acceptable, not guarded.
20. **`sqlglot.parse` for statement counting** may reject valid dialect-specific SQL; on `ParseError` fall back to letting the engine decide (engine read-only enforcement is the real guard).

---

## 10. Interfaces consumed and provided (brief 11.3)

### Provided

| Name | Module | Consumer |
|---|---|---|
| `ResolvedFile` (fields per 3.6; extras `relative_path`, `detail` defaulted) | `core/inputs.py` | plan 02 (FileFingerprint source), plan 08 (pre-flight, `--input` overrides) |
| `resolve_input_files(content_state, *, base_dir=None, hash=False) -> list[ResolvedFile]` | `core/inputs.py` | 02, 08 (brief 11.3 signature, extended with keyword-only args) |
| `FileInputContent.resolved_input_files(self, *, hash: bool = False) -> list[ResolvedFile]` | `file_input.py` | 02 (`after_execution`/finish), 08 |
| `InputReadError` (`kind, message, path, sheet, column, technical, cause_type, code, as_dict()`) with kind->`TD-IN-*`/`TD-SCH-*` codes | `core/inputs.py` | plan 03 (`translate_exception` checks `isinstance(exc, InputReadError)`; no regex needed) |
| `diagnose_collect_error(exc, report) -> InputReadError` | `core/input_source.py` | plan 03 (collect-time errors) |
| `SourceReport` / `FileReport` / `SourceResult`, `build_source(state)` | `core/input_source.py` | plan 08 (headless runner may call `build_source` directly), plan 02 (store `report.as_dict()` in `NodeRunRecord.warnings`) |
| `FileInputContent.last_report`, `.last_error` | `file_input.py` | UI, plan 02 |
| `to_stored_paths`, `resolve_stored_path`, `io_path` | `core/inputs.py` | plan 08 may replace; names kept stable |
| (consumed, not provided) `TriggerScene.workflow_dir`, `_save_target`, atomic `saveToFile` | plan 09 F-F | this plan; File Output may reuse the same rule |
| `core/inputs.py` is polars-free at import | - | keep it so for fast CLI start-up |

Hash policy for plan 02: `FileFingerprint.sha256` is filled by calling `content.resolved_input_files(hash=True)` only when the audit preference says so (this plan never hashes by default).

### Consumed

| Name | From | Use |
|---|---|---|
| `NodeError` / `translate_exception` | plan 03 | Not required to ship this plan. Our `InputReadError.code` already carries the `TD-IN-*` code; plan 03 maps it. If plan 03 lands first, no code change here is needed. |
| `FileFingerprint`, `RunRecorder` | plan 02 | Not consumed (02 consumes us). |
| General path helper | plan 08 | Optional replacement for the three functions in 3.8. |
| Shared node recipe, `frame_schema`, undo helpers, `ConfigSection`/`FormRow`/`IconButton`/`ColumnChecklist`/`NoWheelComboBox`/`EmptyStateLabel` | brief 3, 5, 6 | As used in 3.11/3.12. |

Ordering note (brief 11.2): this plan is parallel with 03/07 in step 1; the core steps (1-5) have no dependency on the node and can merge first, then steps 6-9 integrate. Plan 02 must wait for step 1 (types) and step 6 (`resolved_input_files`).
