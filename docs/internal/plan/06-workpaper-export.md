# 06 - Workpaper Output node (audit workpaper .xlsx) and the Excel dependency fix

Audience: the (cheaper) model that implements this. Every decision is made; do not re-decide.
Read first: `docs/plan/00-codebase-brief.md` (sections 3.7 recipe, 3.8 skeleton, 4, 5, 6, 7.2, 9, 11.3) and `AGENTS.md`.
All paths are relative to the repo root `C:\Users\KASHVINCHANDRASAN\Desktop\Personal\Github\TriggerEditor`.
`file.py:N` references were verified on 2026-10-21 against `main` @ `71b4041` (working tree dirty with unrelated edits; do not touch them).

**Product-owner decision (binding): Excel files are WRITTEN with `xlsxwriter`. Application code imports it in exactly one place, `core/excel/engine.py`. Polars `write_excel` is not used. `openpyxl` stays installed/declared and is used ONLY as a test-time reader.**

## Table of contents

1. Goal and non-goals
2. Current state (verified) and the "Why xlsxwriter" note
3. Final design
4. Ordered implementation steps (one commit each)
5. Edge cases and their fixed behaviour
6. Test plan
7. Acceptance checklist
8. Verification commands
9. Pitfalls
10. Interfaces with plans 01-04, 07, 08 and the standalone fallback

---

## 1. Goal and non-goals

**Goal.** An auditor files a workpaper to prove a test was performed; a reviewer must understand months later *what was tested, on which files, with what criteria, and what was found*. Deliver:

1. Step 1: make Excel export work: declare `xlsxwriter`, add the shared Qt-free package `core/excel/` (engine + `write_frame_xlsx`) and re-point the two existing Excel exports (File Output "excel", Data Preview "Export Excel") at it. Both are broken today (`DataFrame.write_excel` needs the undeclared `xlsxwriter`).
2. A new **Workpaper Output** node (IO family) with three inputs - Exceptions (required), Population (optional), Summary (optional, plan 04 one-row summary frame) - that writes ONE formatted `.xlsx`: `Summary`, `Exceptions`, `Run log` (when a run record exists), `Workflow` (optional).
3. A Qt-free writer `core/workpaper/` that streams (`constant_memory`, never holds the exception table twice), is safe against formula injection, never silently truncates, and never overwrites a previously annotated workpaper by default.
4. Engagement defaults (client, engagement, period, preparer, logo) in project-wide Preferences.

**Non-goals (decided, with reasons).**

| Not doing | Reason |
|---|---|
| **PDF export. Out of scope.** | The filed deliverable is editable (ticks, comments, conclusion are typed in Excel). PDF needs a new heavy dependency (`reportlab`/`fpdf2` are not installed, brief 2.1), fonts and pagination. The workbook ships with print setup (landscape, fit to 1 page wide, repeated header row, footer) so Excel "Save as PDF" gives a good PDF. |
| `.xls`, `.xlsb`, `.ods`, CSV-only workpapers | One format keeps the writer testable. A CSV sidecar exists only as the "full list" companion. |
| Charts in the workbook | Plans 05/Graph own charts. |
| Digital signatures / password protection | Sheet protection without password on Summary/Run log/Workflow only (accident prevention, not security). |
| Data profile sheet (plan 05) | `WorkpaperSpec.include_profile` is kept for interface compatibility (brief 11.3) and **ignored**. |
| Cancel/progress UI | Not wired anywhere in the app (brief fact 4). |

---

## 2. Current state (verified) and the "Why xlsxwriter" note

| Fact | Evidence |
|---|---|
| Excel export is broken here: `xlsxwriter` is neither installed nor declared (Polars' `write_excel` needs it). | `pyproject.toml:33-68` dependency list (`fastexcel>=0.15.1`, `openpyxl>=3.1.0`, no xlsxwriter); `uv.lock` has openpyxl stanzas (`uv.lock:366`, `:979`, `:1027`) and no xlsxwriter; `.venv` lacks it (brief 2.1). |
| File Output "excel" does `var_lazy.collect().write_excel(path)` (whole table in memory). | `src/trigger_designer/qt/widgets/nodes/InOut/file_output.py:293-300`; streaming formats use `sink_*` (`:262-338`). |
| Data Preview "Export Excel" does `current_df.write_excel(filename)` and only logs failures. | `src/trigger_designer/qt/models/polars_table_viewer.py:1195-1210`. |
| No test executes the excel path. | `tests/unit/test_file_output.py:29-41` builds `FileOutputContent.__new__` and asserts code strings only. |
| `openpyxl` is declared but unused in `src`; `fastexcel` is read-only. | brief 2.1, grep. |
| `trigger.spec` hidden imports list `"fastexcel", "openpyxl"`; polars imports xlsxwriter lazily and our new code will import it inside `exec`'d text, invisible to PyInstaller. | `trigger.spec:79-110`; nodes auto-listed at `:42-51`. |
| IO enum ends with `FILE_OUTPUT`; recipe says append at the END. | `src/trigger_designer/core/node_configuration.py:31-35`. |
| Lazy spec list for IO nodes; icon id `node_file_output` exists. | `src/trigger_designer/qt/widgets/nodes/__init__.py:22-28`; `qt/resources.json:24`. |
| Base `evalImplementation` invalidates the node if ANY input is unconnected; optional inputs need an override (Union precedent). | `src/trigger_designer/qt/node_base.py:816-852`; `Join/union.py:~858-950`. |
| `getInputWithSocketIndex(i)` returns `(node, upstream_socket_index)`. | `.venv/Lib/site-packages/nodeeditor/node_node.py:587-606`; brief 3.3 [SURPRISE]. |
| `get_code()` runs on the **worker thread** (and again on the GUI thread via `getPyFile`); read plain attributes only. | `executor.py:310`, brief 3.4/4.2. |
| Run start hook point (GUI thread). | `src/trigger_designer/qt/helpers/workflow_execution_mixin.py:60-62`. |
| Preferences: typed INI, add keys to `DEFAULTS`. | `qt/preferences.py:40-56`; General page `dialogs/preferences_dialog.py:392`, `_load_pages` `:446`. |
| File Input reads CSV with `infer_schema=False`: every column is a String. | brief 7.1. |

### 2.1 Why xlsxwriter (decision record, measured 2026-10-21 in ephemeral envs, repo env untouched)

Command pattern: `uv run --no-project --with xlsxwriter --with openpyxl --with polars==1.44.2 --with pyarrow python probe.py`.

* The product owner first chose `pyfastexcel`, then reversed the decision because it has **no real streaming**: it keeps every cell as a Python tuple, builds one JSON document and one base64 string, and in the same-machine test 500k rows x 6 columns (3M cells) needed **+1.27 GB RSS** (about 570 B per cell; 100k x 6 = +344 MB), which is incompatible with the per-node 512 MB RSS limit (brief 4.2) and with exports of hundreds of thousands of rows. It also lacked cached formula values, sheet protection, images, print setup, and had a broken data-validation implementation.
* xlsxwriter with `constant_memory` writes 500k x 6 cells in **23.3 s with +86 MB RSS** (parquet batches of 50,000), file 18.2 MB, and supports every feature this plan needs natively (3.9). `openpyxl` `write_only` is not an option: 36.3 s for 500k x 5 and **no cached formula values** (writes `<v />`).
* Pin **`xlsxwriter>=3.2.0,<4`**: 3.2.x is the current stable line (3.2.9 verified), supports Python 3.13, provides `constant_memory`, `quote_prefix`, `remove_timezone`, `default_format_properties`; `<4` guards against a major API break. The project pins hard only where an ABI matters (polars, pyarrow, Qt); other libraries use ranges (`openpyxl>=3.1.0`). xlsxwriter is pure Python (BSD-2): no native library, no extra packaging beyond a hidden import.

---

## 3. Final design

### 3.1 New files and edits (map)

```
pyproject.toml / uv.lock / trigger.spec                provided by plan 09 F-G (xlsxwriter dependency, hidden imports); not edited here
src/trigger_designer/core/node_configuration.py        EDIT  IONodes.WORKPAPER_OUTPUT
src/trigger_designer/core/excel/__init__.py            NEW   re-exports write_frame_xlsx, ExcelWriteError
src/trigger_designer/core/excel/errors.py              NEW   ExcelWriteError (.code), TD-OUT codes
src/trigger_designer/core/excel/engine.py              NEW   the ONLY module importing xlsxwriter
src/trigger_designer/core/excel/cells.py               NEW   value -> cell writing rules (types, dates, text guards)
src/trigger_designer/core/excel/spool.py               NEW   frame -> temp Parquet + batches (shared)
src/trigger_designer/core/excel/frame_export.py        NEW   write_frame_xlsx() for File Output + Data Preview
src/trigger_designer/core/workpaper/__init__.py        NEW
src/trigger_designer/core/workpaper/spec.py            NEW   WorkpaperSpec, SourceFile, TestInfo, WorkpaperResult, WorkpaperError
src/trigger_designer/core/workpaper/sanitize.py        NEW   sheet names, headers, column plan, danger predicates
src/trigger_designer/core/workpaper/context.py         NEW   run-record provider registry
src/trigger_designer/core/workpaper/stream.py          NEW   stats, CSV sidecar, sha256
src/trigger_designer/core/workpaper/sheets_exceptions.py NEW
src/trigger_designer/core/workpaper/sheets_summary.py  NEW
src/trigger_designer/core/workpaper/sheets_runlog.py   NEW   Run log + Workflow sheets
src/trigger_designer/core/workpaper/writer.py          NEW   write_workpaper()
src/trigger_designer/core/workpaper/node_runner.py     NEW   run_workpaper() called by generated code
src/trigger_designer/qt/helpers/workflow_snapshot.py   NEW   scene -> plain dicts (GUI thread)
src/trigger_designer/qt/helpers/workflow_execution_mixin.py (stub hook list owned by plan 09 F-B; this plan only fills in the node's before_run body)
src/trigger_designer/qt/widgets/nodes/InOut/file_output.py  EDIT excel branch of get_code (step 1)
src/trigger_designer/qt/models/polars_table_viewer.py  EDIT  Export Excel call (step 1)
src/trigger_designer/qt/preferences.py                 EDIT  DEFAULTS keys
src/trigger_designer/qt/dialogs/preferences_dialog.py  EDIT  "Engagement" section
src/trigger_designer/qt/widgets/nodes/InOut/workpaper_output.py NEW node
src/trigger_designer/qt/widgets/nodes/__init__.py      EDIT  _LAZY_NODE_SPECS entry
tests/unit/test_file_output.py (edit); test_excel_*.py, test_workpaper_*.py (new)
tests/support/workpaper.py                             NEW   readers/helpers shared by tests
tests/ui/test_workpaper_dock.py, test_workpaper_preferences.py        NEW
tests/e2e/test_workpaper_e2e.py + tests/e2e/fixtures/workpaper/*.csv  NEW
tests/benchmarks/test_workpaper_perf.py                NEW
docs/NODE_REFERENCE.md                                 EDIT  one row
```

`core/excel/engine.py` is the **only** file that `import xlsxwriter` (a unit test greps `src/trigger_designer`). Sheet modules receive worksheet/workbook objects from the engine and call their methods; they do not import the package (column-letter helpers come from `engine.col_name`, `engine.cell_ref`). `workflow_snapshot.py` lives in `qt/helpers/` because every `.py` under `qt/widgets/nodes/` is imported at startup (brief 3.1).

### 3.2 Node settings (persisted keys, `serialized_state_schema`)

Missing keys take the default (old files load). `""` means "inherit from Engagement preferences / auto", resolved at `get_code()` time (3.3).

| Key | Type | Default | Meaning / reason |
|---|---|---|---|
| `output_path` | str | `""` | Target `.xlsx`; empty -> TD-OUT-012 at Run. Forward slashes in generated code. |
| `if_exists` | str | `"version"` | `"version"` (`name (2).xlsx`), `"replace"`, `"fail"`. Default protects an auditor's annotated copy from a re-run. |
| `workpaper_ref` | str | `""` | e.g. `C.3.1`; blank renders as an input cell. |
| `client`, `engagement`, `period`, `preparer` | str | `""` | inherit `engagement/client_name`, `engagement/engagement_name`, `engagement/period`, `engagement/preparer` (preparer then `getpass.getuser()`). |
| `prepared_date` | str | `""` | ISO `YYYY-MM-DD`; blank = date of writing (local). |
| `test_name` | str | `""` | blank -> Summary input `test_name` -> `"Exceptions workpaper"`. |
| `objective`, `procedure`, `criteria` | str | `""` | `criteria` blank -> Summary input `criteria` -> placeholder `Not provided - complete manually` (input cell). |
| `amount_column` | str | `""` | Exceptions column used for values. Blank = no value statistics (`n/a`). |
| `value_decimals` | int | `2` | 0-6; number format and rounding of sums. |
| `row_limit` | int | `100000` | Max exception rows listed. Hard max `1048574` (Excel's 1,048,576 minus banner row and header row). Clamped with a Note, never an error. |
| `include_run_log` / `include_workflow` | bool | `True` / `True` | optional sheets. |
| `exceptions_sheet_name` | str | `"Exceptions"` | sanitised by `safe_sheet_name`. |
| `logo_path` | str | `""` | inherit `engagement/logo_path`; PNG/JPG. |
| `source_files` | list[str] | `[]` | Extra source files (standalone fallback, section 10). |

Defaults live in ONE constant `NODE_DEFAULTS` in `workpaper_output.py` used by schema, dock and tests.

### 3.3 Engagement preferences (project-level)

Add to `Preferences.DEFAULTS` (`qt/preferences.py:40-56`): `engagement/client_name`, `engagement/engagement_name`, `engagement/period`, `engagement/preparer`, `engagement/logo_path` (all `""`) and `export/workpaper_dir` (`""`, start folder of the Browse dialog).
Dialog: in `_build_general_page` (`preferences_dialog.py:392`) add `ConfigSection("Engagement")` between `startup` and `danger`: five `QLineEdit` (`FormRow`, H30; the logo row gets a browse `IconButton.themed`), loaded in `_load_pages`, saved in `editingFinished` slots via `self._prefs.set(key, text)`. No new `QSettings` scope, no new objectNames.
Resolution happens in the node (Qt side): `value = node_value or prefs.get(key) or fallback`. The writer never reads preferences.

### 3.4 Data flow

```
 Exceptions (required) --\
 Population (optional) ---+--> Workpaper Output --> (no outputs)  writes .xlsx (+ .csv sidecar)
 Summary    (optional) --/        Run: get_code() -> run_workpaper(spec_json, exceptions, population, summary, workflow_json, sources_json)
```

* Sockets: `inputs=[1, 1, 1]`, `input_text=["E", "P", "S"]` (`node_base.py:677`), `outputs=[]`. Not `MultiInputNode` (one socket, many edges): three named sockets give unambiguous roles.
* Live `evalImplementation` override (Union precedent): input 0 required (invalid + tooltip `Connect the Exceptions input`); inputs 1, 2 optional; a connected-but-failed optional input makes the node invalid (`Population input has no data`) - never silently ignored. Live eval stores plain Python on the content (GUI thread): frames + variable names, `workflow_snapshot`, `source_snapshot`; it never collects data. Returns `[]` as `param`/`value`.
* **`get_code()`** (pure, idempotent, worker-thread-safe; plain attributes only):

```python
import polars as pl
from trigger_designer.core.workpaper.node_runner import run_workpaper
var_workpaper_result_<id> = run_workpaper(
    spec_json=<json literal via !r>, exceptions=<exceptions_variable>,
    population=<population_variable or None>, summary=<summary_variable or None>,
    workflow_json=<json literal or None>, sources_json=<json literal>)
```
  Unwired exceptions: `raise ValueError('Workpaper Output: connect the Exceptions input')` (File Output precedent `file_output.py:232-236`). User strings are embedded only through `json.dumps` + `!r`.
* Hidden imports are required (PyInstaller cannot trace the `exec`'d text): step 1 and step 10.

### 3.5 Public APIs (Qt-free; stdlib + polars + pyarrow + xlsxwriter + loguru)

**`core/excel/engine.py`** (the xlsxwriter façade):

```python
import xlsxwriter
from xlsxwriter.utility import xl_col_to_name, xl_rowcol_to_cell

MAX_ROWS = 1_048_576; MAX_COLS = 16_384
def col_name(idx0: int) -> str: return xl_col_to_name(idx0)
def cell_ref(row0: int, col0: int, abs_: bool = False) -> str: ...
def require_xlsxwriter() -> None: ...          # ImportError -> ExcelWriteError("Excel export needs the 'xlsxwriter' package, which is missing from this installation.", code="TD-OUT-003")
def new_workbook(path: str, tmp_dir: str):
    """xlsxwriter.Workbook(path, {"constant_memory": True, "tmpdir": tmp_dir, "strings_to_numbers": False,
    "strings_to_formulas": False, "strings_to_urls": False, "nan_inf_to_errors": False, "remove_timezone": True,
    "default_format_properties": {"font_name": "Calibri", "font_size": 10}})"""
```

**`core/excel/cells.py`** - the only place that decides how a Python/Polars value is written:

```python
def write_value(ws, row0: int, col0: int, value, kind: str, fmt) -> int: ...   # write_string/write_number/write_datetime/write_boolean/write_blank only; never ws.write()
def needs_quote_prefix(text: str) -> bool: ...                                   # 3.8 danger rule
def guard_text(s: str) -> tuple[str, int]: ...     # (cleaned, flags) control chars -> U+FFFD; > 32,767 chars shortened with marker; flags bit0 control, bit1 shortened
```

**`core/excel/spool.py`**: `spool_parquet(frame, tmp_dir) -> str` (`LazyFrame.sink_parquet`, eager `write_parquet`; the plan runs once) and `iter_batches(path, batch_size=50_000) -> Iterator[pl.DataFrame]` (via `pyarrow.parquet.ParquetFile.iter_batches`).

**`core/excel/frame_export.py`**

```python
def write_frame_xlsx(frame: "pl.LazyFrame | pl.DataFrame", path: str, *, sheet_name: str = "Sheet1") -> int:
    """Spool once, stream batches in constant_memory mode, bold header, frozen header row, autofilter, formats from dtypes
    (same rules as 3.8). Returns data rows written. Real limits: 1,048,575 data rows (Excel's 1,048,576 minus the header)
    and 16,384 columns; beyond either raises ExcelWriteError TD-OUT-013 (plain text, never truncates). Memory is bounded
    (constant_memory + 50,000-row batches), so there is no cell-count cap."""
```

**`core/workpaper/spec.py`**

```python
class WorkpaperError(ExcelWriteError):            # .code, .path; str(e) is plain language
    def __init__(self, message: str, *, code: str = "TD-OUT-012", path: str | None = None): ...

@dataclass(frozen=True)
class SourceFile:
    path: str; sheet: str | None = None; rows: int | None = None; size_bytes: int | None = None
    modified_time: str | None = None; sha256: str | None = None

DEFAULT_TICKS = (("\u2713", "Agreed to source document"), ("X", "Exception confirmed"),
                 ("E", "Explained - see comment"), ("F", "Follow-up required"), ("N/A", "Not applicable"))
CONCLUSIONS = ("No exceptions", "Exceptions - explained", "Exceptions - require follow-up")

@dataclass(frozen=True)
class WorkpaperSpec:
    # names kept from brief 11.3
    title: str = "Audit workpaper"; preparer: str = ""; reviewer: str = ""; purpose: str = ""
    sections: tuple[str, ...] = ()          # reserved, ignored
    include_run_record: bool = True
    include_tests: bool = True              # reserved, ignored
    include_profile: bool = False           # reserved, ignored
    output_path: str = ""; format: str = "xlsx"
    # additions (all defaulted)
    workpaper_ref: str = ""; client: str = ""; engagement: str = ""; period: str = ""
    prepared_date: str = ""; test_name: str = ""; procedure: str = ""; criteria: str = ""
    amount_column: str = ""; value_decimals: int = 2; row_limit: int = 100_000
    include_workflow: bool = True; if_exists: str = "version"
    exceptions_sheet_name: str = "Exceptions"; logo_path: str = ""
    tick_marks: tuple[tuple[str, str], ...] = DEFAULT_TICKS
    source_files: tuple[SourceFile, ...] = (); app_version: str = ""
    def to_json(self) -> str: ...           # json.dumps(asdict(self), ensure_ascii=False)
    @classmethod
    def from_json(cls, text: str) -> "WorkpaperSpec": ...     # ignores unknown keys, rebuilds tuples/SourceFile

@dataclass(frozen=True)
class TestInfo:
    test_name: str = ""; criteria: str = ""; status: str = ""; message: str = ""
    population_rows: int | None = None; exception_rows: int | None = None
    exception_rate: float | None = None; parameters: Mapping[str, Any] = field(default_factory=dict)
    @classmethod
    def from_mapping(cls, d) -> "TestInfo | None": ...        # tolerant
    @classmethod
    def from_frame(cls, df) -> "TestInfo | None": ...         # first row; empty -> None

@dataclass
class WorkpaperResult:
    path: str; csv_path: str | None; exceptions_total: int; exceptions_written: int; truncated: bool
    population_rows: int | None; population_value: float | None; exceptions_value: float | None
    workbook_sha256: str; sheets: list[str]; omitted: dict[str, str]; warnings: list[str]; duration_s: float
    def to_dict(self) -> dict: ...
```

**`core/workpaper/writer.py`**

```python
def write_workpaper(spec: WorkpaperSpec, exceptions: "pl.LazyFrame | pl.DataFrame", *,
                    population=None, test: "TestInfo | Mapping | None" = None,
                    run_record: "Mapping | None" = None, workflow: "Sequence[Mapping] | None" = None,
                    now: "datetime | None" = None) -> WorkpaperResult: ...
```

**`core/workpaper/node_runner.py`**: `run_workpaper(*, spec_json, exceptions, population=None, summary=None, workflow_json=None, sources_json="[]") -> dict` (parse, collect the 1-row summary into `TestInfo`, fetch `context.current_run_record()`, call `write_workpaper`, print one `[SUCCESS] Workpaper written to <path>` line, return `result.to_dict()`).
**`core/workpaper/context.py`**: `set_run_record_provider(fn | None)`, `current_run_record() -> Mapping | None` (never raises; dataclass -> `asdict`).

### 3.6 Streaming algorithm (no double collect) and the `constant_memory` row-order rule

1. **Validate + resolve** spec (3.8): empty path, not `.xlsx`, folder missing (TD-OUT-001), `~$<name>` lock file when `replace` (TD-OUT-002), `engine.require_xlsxwriter()` (TD-OUT-003).
2. **Exceptions -> one temp Parquet** (`tempfile.mkdtemp(prefix="td_wp_")`, `spool_parquet`). Zero columns -> `WorkpaperError`. The upstream plan executes exactly once; every later pass reads the compact file.
3. **Stats from the Parquet** (one `select`): `pl.len()`, optional amount sum (`amount_expr`), unparseable-amount count, per-String-column `max(str.len_chars())`. Population (separate plan): one `select(pl.len(), amount_sum)`; amount column missing there -> value `None` + Note. **All numbers the Summary needs are known before the workbook is opened.**
4. `limit = clamp(row_limit, 1, 1_048_574)`; `truncated = total > limit`; `need_csv = truncated or any cell longer than 32,767`.
5. **CSV sidecar first** (if needed; its row count and SHA-256 are shown on the Summary): `scan_parquet(...).with_row_index("Ref", offset=1)` with tz stripped and the CSV danger prefix -> `sink_csv(include_bom=True)`; polars streams it.
6. **Workbook** from `engine.new_workbook(tmp_xlsx, tmp)` (`constant_memory=True`) with the four worksheets added in tab order (`Summary`, `Exceptions`, `Run log`, `Workflow`). **Row-order rule.** In `constant_memory` mode a row is flushed to disk when a later row is started, so every worksheet must be written in ascending row order, and a write to an earlier row is dropped with return code `-1` (verified). The rule is per worksheet: **each worksheet has its own temp file, so different sheets may be written in any order** (verified 2026-10-21: `Exceptions` written first, then `Summary` row 1 containing `=COUNT('Exceptions'!$A$3:$A$5)` with cached `3`; tab order stayed `['Summary','Exceptions']`, openpyxl `data_only` returned `3`). Decision: **no separate non-constant pass is needed**. Write order: `Exceptions` (streamed), then `Summary`, `Run log`, `Workflow`, each by a monotonically increasing row cursor; Summary figures come from step 3 and the Exceptions layout result, so nothing on the Summary is written "later" than a row below it. Column widths, merged ranges, validations, freeze panes and autofilter may be set at any time (verified for widths).
7. `wb.close()`, then publish (3.8): temp file -> `os.replace`. `finally`: delete the temp dir.

Measured baseline (this machine): 500k x 6 columns -> sink 0.0 s (in-memory source), write 23.3 s, RSS delta 86 MB, 18.2 MB file.

### 3.7 Formulas vs static values (decided)

xlsxwriter `write_formula(cell, formula, fmt, value)` stores a cached value (verified: `openpyxl data_only=True` returned it; the plain load shows the formula string). Excel recalculates on open (full-calc-on-load flag), so the cached values only matter for viewers that do not recalculate.

| Cell (Summary) | Kind | Why |
|---|---|---|
| `B24` exceptions listed | formula `=COUNT('<Exc>'!$A$3:$A$<last>)` + cached | ties to the sheet the auditor edits/filters; `Ref` (col A) holds integers only for real rows (the "No exceptions noted" row is text). |
| `C24` value of listed rows | formula `=SUM('<Exc>'!$<col>$3:$<col>$<last>)` + cached (text `n/a` without amount column) | same; SUM ignores text, so unparseable amounts do not break it. |
| `B23`, `C23` exceptions found / value | formulas `=B24`, `=C24` when not truncated; **static numbers** when truncated | a truncated sheet cannot prove the total. |
| `D23`, `E23` | `=IFERROR(B23/B22,"n/a")`, `=IFERROR(C23/C22,"n/a")` + cached | arithmetic on visible cells; no `#DIV/0!`. |
| `F34:F38` tick counts | `=COUNTIF('<Exc>'!$B$3:$B$<last>,A34)` + cached `0` | live as the auditor ticks. |
| `B22`, `C22` population, all text/metadata/hashes/dates | static | population is not in the workbook; evidence must not change on edit. |

### 3.8 Behaviour rules fixed by this plan

* **Overwrite** (`if_exists`): write to a temp file in the temp dir, then `os.replace(tmp, final)`. `"version"`: first free of `name.xlsx`, `name (2).xlsx`, ...; `"replace"`: overwrite (`PermissionError` -> TD-OUT-002 "The file '<name>' is open in Excel or another program. Close it and run again."); `"fail"`: exists -> TD-OUT-010 "A workpaper named '<name>' already exists. Choose another name or set 'If the file exists' to New version." The sidecar obeys the same mode; its name derives from the **final** workbook path: `<stem>_exceptions_full.csv`.
* **Folder missing** -> TD-OUT-001 (no silent mkdir; matches File Output).
* **Sheet names** (`safe_sheet_name(raw, used, default)`): replace `[]:*?/\` by space, strip leading/trailing `'` and spaces, collapse spaces, cut to 31, empty -> default, unique case-insensitively with ` (2)` (re-cut to 31), avoid reserved `Summary`, `Run log`, `Workflow`. xlsxwriter raises `InvalidWorksheetName` for bad names (verified), so `safe_sheet_name` must run first. Formulas quote names with `quote_sheet` (`'` doubled).
* **Amount column** (`amount_expr`): numeric dtypes `cast(Float64)`; String -> `strip_chars` -> remove `,` -> `^\((.*)\)$` => `-$1` -> `cast(Float64, strict=False)` (CSV text such as `1,234.50`, `(12.00)`). Unparseable non-empty values stay text and are counted in Notes. Sums are Float64, shown rounded to `value_decimals`; Notes state "Values are summed as floating point numbers".
* **Cell types** (`cells.write_value`, explicit calls only - no `ws.write()` anywhere): String -> `write_string`; ints -> `write_number` (ints with `abs >= 10**15` -> `write_string`, Excel keeps 15 digits); floats -> `write_number`, NaN/Inf -> `write_string("NaN"/"Infinity"/"-Infinity")` (verified: `write_number(nan)` raises `TypeError`); Decimal -> number, format by scale (cap 6); `bool` -> `write_boolean`; null -> `write_blank(..., fmt)` (a real blank); Date -> `write_datetime` fmt `yyyy-mm-dd`; Datetime -> `yyyy-mm-dd hh:mm:ss`; Time -> `hh:mm:ss`; tz-aware datetimes: `dt.replace_time_zone(None)` first (wall clock kept; Excel has no time zones) + Note listing the columns; Duration -> total seconds, header suffix ` (seconds)`, format `#,##0.000`; List/Struct/Array/Object/Binary/other -> `str(v)` from `Series.to_list()` (`map_elements(str)` yields the Series repr for lists - verified, do not use).
* **Integer formats**: `#,##0`, except columns whose name matches `(?i)(^|[\W_])(id|no|num|number|ref|code|acct|account|invoice|po)($|[\W_])` -> `0`. Float `#,##0.00`.
* **Text cleaning** (`guard_text`): control characters `[\x00-\x08\x0b\x0c\x0e-\x1f]` -> `U+FFFD` (xlsxwriter would emit `_x0001_` escapes, verified); length > 32,767 -> first `32767 - len(marker)` chars + marker `" ...[shortened from <N> characters; full text in the CSV file]"` (xlsxwriter silently cuts at 32,767 and returns -2, verified). A shortened cell forces the CSV sidecar; counts go to Notes.
* **Formula-injection guard**: every string goes through `write_string` (stored as a string, never a formula; verified `data_type == "s"` for `=cmd|' /C calc'!A0`). A string is *dangerous* if it starts with `=`, `@`, TAB, CR, or starts with `+`/`-` and is not a plain signed number (`^[+-]\s*[\d.,]+\s*$`). Dangerous cells additionally get a `quote_prefix` format (`set_quote_prefix()`; verified `quotePrefix=True` on read-back) so pressing F2+Enter in Excel does not turn them into formulas. Applies to data cells, headers and every metadata string. The format per base format is cached (`fmt_for(base_key, quoted: bool)`). CSV sidecar: dangerous cells get a leading `'`. Polars regex has no look-around (verified error), so the Polars predicate is composed from `starts_with` + `contains` parts (`danger_expr`); the Python regex and the Polars predicate must agree (tested on one shared table). Genuine formulas are written only with `write_formula` from Summary/Exceptions code, never from data.
* **Headers**: empty -> `Column <n>`; collisions (case-insensitive) with `Ref`, `Tick mark`, `Auditor comment` -> suffix ` (data)`; max 16,381 data columns (TD-OUT-011).
* **Never silent truncation**: banner on the Exceptions sheet, Summary `F24`, Notes, `WorkpaperResult.truncated`, Logging-dock line, CSV sidecar with ALL rows.
* **Sheet protection**: `ws.protect("", {"autofilter": True})` on `Summary`, `Run log`, `Workflow` (verified: `protection.sheet` True, formats with `locked: False` stay editable, others locked). `Exceptions` is not protected (auditors filter, sort, tick).
* **Prepared date**: `now or datetime.now()`; spec `prepared_date` overrides; invalid ISO -> TD-OUT-012.

### 3.9 xlsxwriter capabilities verified (ephemeral envs; xlsxwriter 3.2.9, openpyxl 3.1.5, polars 1.44.2)

Each is pinned by `tests/unit/test_excel_capabilities.py` (6.2).

| Capability | Result when re-read with openpyxl |
|---|---|
| `data_validation` list on one cell and a column range | `formula1 == '"No exceptions,Exceptions - explained,Exceptions - require follow-up"'`; range `B2:B6` list `"✓,X"` |
| `freeze_panes`, `autofilter` | `"A2"`, `"A1:C6"` |
| `write_formula` with cached value | formula preserved; `data_only=True` -> cached value |
| `protect("")` + `locked: False` format | `sheet=True`; unlocked cell `locked=False`, other `True` |
| `quote_prefix` format | `quotePrefix=True` |
| `write_string("=cmd|...")` | `data_type 's'` |
| `write_string` > 32,767 chars | returns `-2`, stored truncated at 32,767 |
| Control char `\x01` | stored as `_x0001_` escape |
| `write_number(nan)` | `TypeError` unless `nan_inf_to_errors` |
| Row-order rule (`constant_memory`) | write to an earlier row of the same sheet returns `-1`, ignored |
| Sheets written in any interleaving (`constant_memory`) | verified: Exceptions first, then Summary; tab order and cached formula intact |
| `set_column` after rows (`constant_memory`) | width `44.71` applied |
| Row limit | `write_number(1048575, 0, x)` (0-based, Excel row 1,048,576) returns 0; row index 1,048,576 returns `-1` |
| `insert_image` (PNG) with `constant_memory` | `len(ws._images) == 1` |
| `set_tab_color`, `hide_gridlines(2)`, `repeat_rows`, `set_landscape`, `fit_to_pages`, `set_footer`, `set_properties`, `merge_range` | tab colour `FFC00000`, gridlines off, orientation landscape, footer text, merged `A1:E1`, title property |
| Invalid sheet names | `InvalidWorksheetName` for > 31 chars, `:`, leading `'` |
| Strings in `constant_memory` | written as inline strings (larger file, read fine by openpyxl) |
| Frozen app | pure Python, no native library; needs only a hidden import because it is imported from `exec`'d text (verified by design; confirm in the frozen smoke, section 8) |

### 3.10 Sheet 1 - `Summary` (exact layout)

Columns: `A` width 30, `B` 16, `C` 22, `D` 22, `E` 22, `F` 64. Gridlines hidden (`hide_gridlines(2)`); tab colour `#305496`; print: landscape, `fit_to_pages(1, 0)`, footer `&L&F - &A&RPage &P of &N`. Document properties: title = spec.title, author = preparer, company = client, comments = `Generated by Trigger Designer <app_version>`. Styles: `title` bold 16, bottom border; `sub` italic grey; `section` white bold on `#305496` across A:F; `label` bold on `#D9E1F2`; `hdr` bold on `#D9E1F2` with border; `wrap` text wrap + top. "I" = input style (fill `#FFF2CC`, `locked: False`) used when the value is empty, else a locked plain style. "M" = merged `B:F` (single-row `merge_range`).

| Cell(s) | Content | Style / notes |
|---|---|---|
| `A1:F1` | spec.title (default `Audit workpaper`) | `title`; row height 40; **logo** anchored at `F1`, right aligned (scale so height <= 36 px and width <= 200 px; `x_offset = 453 - scaled_width - 4`; size read with `PIL.Image.open`, pillow is already declared) |
| `A2:F2` | `Audit workpaper generated by Trigger Designer <app_version> on <YYYY-MM-DD HH:MM>` | `sub` |
| `A4:F4` | `Engagement` | `section` |
| `A5` / `B5:F5` | `Workpaper reference` / spec.workpaper_ref | `label` / M, I if empty |
| `A6`, `A7`, `A8` | `Client`, `Engagement`, `Period` / spec values | I if empty |
| `A9` / `B9:F9` | `Test performed` / spec -> test input -> `Exceptions workpaper` | |
| `A10` / `B10:F10` | `Prepared by` / spec.preparer | I if empty |
| `A11` / `B11:F11` | `Prepared on` / date cell, format `yyyy-mm-dd` | locked |
| `A12`, `A13` / `B12`, `B13` | `Reviewed by`, `Review date` / blank | I (`B13` format `yyyy-mm-dd`) |
| `A15:F15` | `Objective and procedure` | `section` |
| `A16`, `A17`, `A18` / `B16:F16`, `B17:F17`, `B18:F18` | `Objective` (spec.purpose, height 48), `Procedure performed` (height 64), `Criteria applied` (spec -> test.criteria -> `Not provided - complete manually`, height 48) | `wrap`; I if empty/placeholder |
| `A20:F20` | `Results` | `section` |
| `A21:F21` | `Measure`, `Rows`, `Value`, `% of population rows`, `% of population value`, `Basis` | `hdr` |
| `A22`, `B22`, `C22`, `F22` | `Population tested` / population rows (Population input count, else `test.population_rows`, else blank input) / population value (amount column on the Population input; blank input; `n/a` if no amount column) / `Counted from the Population input` or `Reported by the test node` or `Not provided - enter manually` | `#,##0`; number fmt |
| `A23`, `B23`, `C23`, `D23`, `E23`, `F23` | `Exceptions found` / formulas or statics per 3.7 / `0.00%` / `No exceptions noted` (0 rows, bold green) else `Counted from the Exceptions input` | |
| `A24`, `B24`, `C24`, `F24` | `Exceptions listed in this workbook` / formulas (3.7) / `All exceptions are listed` or `TRUNCATED: first <limit> of <total> listed` (bold red on `#F8CBAD`) | |
| `A25` / `B25:F25` | `Full exception list (CSV)` / `<file name> - <rows> rows - SHA-256 <hash>` or `Not needed - all exceptions are listed in this workbook` | |
| `A26` / `B26:F26` | `Reconciliation to test result` / `Agrees to the test node (<n> exceptions)` or `DIFFERENCE: the test node reported <n> exceptions but <m> were received` (red) or `No test result supplied` | |
| `A28:F28` | `Conclusion` | `section` |
| `A29` / `B29:F29` | `Conclusion` / blank | I + data validation list = `CONCLUSIONS` (input title `Conclusion`, error alert on) |
| `A30` / `B30:F30` | `Auditor notes` / blank | I, wrap, height 80 |
| `A32:F32` | `Tick marks` | `section` |
| `A33`, `B33:E33`, `F33` | `Tick`, `Meaning`, `Rows marked` | `hdr` |
| `A34:A38`, `B34:E38`, `F34:F38` | one row per `spec.tick_marks` (default 5): symbol / meaning / COUNTIF formula | |
| row 40 | section `Source files` | |
| row 41 | `File`, `Sheet`, `Rows read`, `Size (bytes)`, `Modified (UTC)`, `SHA-256` | `hdr` |
| rows 42.. | one per source; none -> `A42:F42` `No source files recorded` | `Rows read` = `not recorded` when unknown; hash cell `file not found` / `not computed (file larger than 4 GiB)` |
| next | blank, section `Notes and limitations`, one merged `A:F` line per note (`None.` if empty) | |
| next | blank, section `Workbook contents`: `Summary`, `<Exceptions name>`, `Run log` or `Run log - omitted: <reason>`, `Workflow` or `Workflow - omitted: <reason>` | |

(Rows >= 40 assume 5 ticks: `r_sources = 35 + len(ticks) + 1`.) The sheet is protected (3.8).

### 3.11 Sheet 2 - `Exceptions`

| Address | Content |
|---|---|
| `A1` | Banner (overflows right, no merge). Normal: `Showing all <N> exception rows.` Zero: `No exceptions noted.` Truncated: `TRUNCATED - showing the first <limit> of <total> exception rows. The complete list is in <csv name>.` (bold red text on `#F8CBAD` on `A1:D1`) |
| `A2`, `B2`, `C2` | `Ref`, `Tick mark`, `Auditor comment` (`hdr`) |
| `D2..` | data headers (3.8 rules), `hdr` |
| `A3..A<last>` | `Ref` 1..n (integer, format `0`); same numbers as the CSV `Ref` column |
| `B3..B<last>`, `C3..C<last>` | tick mark and comment cells are left unwritten (true blanks); data validation list on `B3:B<last>` = tick symbols (ignore blank, input message `Choose a tick mark`) |
| `D3..` | data per 3.8 formats |
| zero exceptions | `A3` = `No exceptions noted` (italic text), `last = 3` |

`last = 2 + written` (min 3). Freeze panes `(2, 1)`; autofilter `A2:<lastcol><last>`; tab colour `#C00000` when truncated. Print: landscape, fit 1 page wide, `repeat_rows(1)`. Widths set at the end: `A` 8, `B` 11, `C` 40, data `min(60, max(10, len(header)+2, longest first-batch string + 2))` (first-batch sample; documented as an estimate).

### 3.12 Sheet 3 - `Run log` (only when a run record exists)

Source: `run_record` mapping (plan 02 `RunRecord` as dict, brief 11.3), read only with `.get` (missing -> `not recorded`). Because this node runs inside the run the record is an in-progress snapshot (10.2). Columns `A` 22, `B` 40, `C` 28, `D` 14, `E` 22, `F` 14, `G` 14, `H` 70. Rows 1-3 fixed, the rest by cursor (tests find labels with `find_label`).

| Address | Content |
|---|---|
| `A1` | `Run log` (`title`) |
| `A2` | Banner: `Snapshot taken while the workflow was running: steps up to and including <last finished step> are listed; this step and later steps are not.` (status `running`/missing) or `Completed run.` |
| `A4:B13` | `Run ID`, `Status`, `Started (UTC)`, `Finished (UTC)`, `Run by` (`user@machine`), `Application version`, `Python`, `Polars`, `Workflow file`, `Workflow SHA-256` |
| files table | header `Role`, `Path`, `Sheet`, `Size (bytes)`, `Modified (UTC)`, `SHA-256` (`F:H` merged per row); one row per input/output fingerprint |
| steps table | header `Step`, `Node`, `Type`, `Status`, `Started (UTC)`, `Duration (s)`, `Rows out`, `Message`; row per node: 1-based `#`, title (+label), friendly op (after the dot, `_` -> space, title case), status, started, duration 3 dp, `rows_out` summed (`not counted` if None), `error.title - error.hint` else warnings joined; failed steps filled `#F8CBAD` |

Protected, landscape print setup like Summary. Omitted (`omitted["Run log"]`, Summary line, Logging-dock line) when `run_record` is None (`no run record is available (run recording is off or not installed)`) or `include_run_log` is False (`turned off in the node settings`). Never an error.

### 3.13 Sheet 4 - `Workflow` (optional)

Input `workflow`: list of dicts built on the GUI thread by `qt/helpers/workflow_snapshot.py`: `{"step", "node_id", "title", "label", "op", "kind": "node"|"comment", "settings": [[label, value_text], ...], "inputs": [titles], "comment": str|None}` - ancestors of the three inputs in topological order, then every Comment node of the scene.

| Address | Content |
|---|---|
| `A1` | `Workflow` (`title`) |
| `A2` | `Steps that produced the data in this workpaper, in the order they ran. Notes written by the preparer follow.` |
| `A4:E4` | `Step`, `Node`, `Type`, `What it does (settings)`, `Takes data from` |
| `A5..` | rows; settings as `Label: value` lines (wrap; row height `15 * lines`, max 300; values > 300 chars shortened with `...`) |
| after nodes | blank, section `Notes in the workflow`, then per comment node: `A` `Note`, `B:E` merged comment text |

Widths `A` 8, `B` 28, `C` 22, `D` 80, `E` 30; protected. Omitted when `include_workflow` False or the list is empty. Settings text from the optional content hook `describe_settings() -> list[tuple[str, str]]`, else generic `serialize()` keys minus `id, pos_x, pos_y, schema_snapshot, file_metadata, available_sheets` (empty/None skipped). Comment text: `getattr(content, "comment_text", None)` then `serialize().get("text")`.

### 3.14 Branding / logo

`logo_path` (node) or `engagement/logo_path` (pref); PNG/JPG only (extension check, case-insensitive); placed per 3.10. Failure (missing file, unreadable) -> workpaper still written, Note `Logo not added: <reason>`. Colours are fixed neutral blue/grey, defined once in `sheets_summary.STYLES`.

### 3.15 Config Dock layout (follows AGENTS.md and `select.py:134-259`)

`create_layout`: first line `if self.incom_exceptions is None: dock_layout.addWidget(EmptyStateLabel("Connect the Exceptions input")); return`. Sections (each `section._undo_composite = True`, `union.py:349`): fields H30, combos `NoWheelComboBox`, multi-line `QPlainTextEdit` (min height 60), browse `IconButton.themed("Browse for save location", rsm_icon=rsm.get("icon_save"), theme_fallback="document-save")` as `file_output.py:75-81`. No inline QSS, no new objectNames.

| Section | Rows (`FormRow(label, field, label_width=96)`) |
|---|---|
| File | `File` path + browse; `If it exists` combo (`New version`->`version`, `Replace`->`replace`, `Stop with error`->`fail`) |
| `Engagement` (collapsible) | `Reference`, `Client`, `Engagement`, `Period`, `Prepared by`, `Prepared on` (placeholder `today`), `Logo` + browse. Placeholders show the inherited preference value |
| `Test` | `Test name` (placeholder = Summary input's name), `Objective`, `Procedure`, `Criteria` |
| `Values` | `Amount column` combo (`(none)` + Exceptions columns via `frame_schema()`), `Decimals` spin 0-6 |
| `Sheets` | `Row limit` spin 1..1,048,574 (step 10,000), `Exceptions sheet` edit, checkboxes `Include run log`, `Include workflow` |
| `Sources` | `Extra source files` text (one path per line); info line with detected upstream file count |

Debounce 300 ms (one single-shot `QTimer` per text control; combos/spins/checkboxes immediate). History texts `Workpaper <Noun> Changed`, `merge_key="wp-<attr>"` for text/spin only. `dock_context()` chips `[("xlsx","accent"), ("<n> row limit",""), ("new version","")]`, label = file basename. Undo wiring per brief 6.3; `_sync_widgets_from_model` under `blockSignals`. Node tooltip hint: `Large workpapers may exceed the 30 second per-node time limit; lower the row limit.` Nothing is written while editing.

---

## 4. Ordered implementation steps (small commits)

Use `.venv\Scripts\python.exe -m ...`. Never bare `uv sync` (pyproject note: it prunes the git-installed nodeeditor). After each step: `ruff format <files>`, `ruff check <files>`, then the named tests. Commit message `Workpaper: <step>` with the session attribution trailer.

### Step 1 - shared Excel module and existing exports  (commit 1; dependency provided by plan 09 F-G)

**Provided by plan 09 F-G (do not redo here):** declaring `xlsxwriter>=3.2.0,<4` in `pyproject.toml`/`uv.lock` (manual `uv lock --upgrade-package xlsxwriter` + `uv pip install`, never bare `uv sync`), the `trigger.spec` hidden imports (`xlsxwriter`, `pyarrow.parquet`, `trigger_designer.core.excel.frame_export|engine|cells|spool|errors`, later `trigger_designer.core.workpaper.*`) and the File Output "excel" regression test. Precondition for this step: `.venv\Scripts\python.exe -c "import xlsxwriter"` succeeds and `trigger.spec` contains the `xlsxwriter` hidden import; if not, plan 09 F-G has not landed - stop and run it first. The File Output "excel" and Data Preview export regression tests (`test_file_output_excel_writes_a_readable_workbook`, `test_data_preview_export_*`) are owned by plan 09 F-G; this step adds none of them.

Files: `core/excel/{__init__,errors,engine,cells,spool,frame_export}.py`, `file_output.py`, `polars_table_viewer.py`, `tests/unit/test_excel_*.py`, `tests/unit/test_file_output.py`.

1. `core/excel/__init__.py` **explicitly re-exports** `write_frame_xlsx` and `ExcelWriteError` (`from .frame_export import write_frame_xlsx`; `__all__ = ["write_frame_xlsx", "ExcelWriteError"]`) because plan 05 imports `from trigger_designer.core.excel import write_frame_xlsx`. A unit test (`test_core_excel_reexports_write_frame_xlsx`) asserts both import paths give the same object.
2. `core/excel/*` per 3.5/3.8. `write_frame_xlsx` skeleton:
   ```python
   def write_frame_xlsx(frame, path, *, sheet_name="Sheet1"):
       require_xlsxwriter()
       schema = frame_schema(frame)                       # names/dtypes without collecting
       if len(schema) > MAX_COLS: raise ExcelWriteError("Excel allows at most 16,384 columns ...", code="TD-OUT-011")
       tmp = tempfile.mkdtemp(prefix="td_xl_")
       try:
           pq = spool_parquet(frame, tmp)
           total = pl.scan_parquet(pq).select(pl.len()).collect().item()
           if total + 1 > MAX_ROWS:
               raise ExcelWriteError(f"This table has {total:,} rows; an Excel sheet holds at most 1,048,575 data rows. Save it as CSV or Parquet instead.", code="TD-OUT-013")
           wb = new_workbook(tmp_xlsx := os.path.join(tmp, "x.xlsx"), tmp); ws = wb.add_worksheet(safe_sheet_name(sheet_name))
           ... header row (bold fmt), freeze_panes(1, 0), autofilter, rows via iter_batches + cells.write_value, widths ...
           wb.close(); _publish(tmp_xlsx, path)            # os.replace; PermissionError -> TD-OUT-002
           return total
       finally:
           shutil.rmtree(tmp, ignore_errors=True)
   ```
   **Real limit:** 1,048,575 data rows and 16,384 columns (Excel's own); memory is bounded, so there is no other cap and File Output "excel" never refuses a table that Excel can hold; it errors (never truncates) above the Excel limit.
3. `file_output.py:293-300` excel branch becomes:
   ```python
   code_lines.append("        from trigger_designer.core.excel.frame_export import write_frame_xlsx")
   code_lines.append(f"        write_frame_xlsx({var_name}_lazy, {export_path!r})")
   ```
   (no `.collect()` in the generated text). `polars_table_viewer.py:1205`: `write_frame_xlsx(current_df, filename)` (import inside the method; the existing `except` logs `Excel export error`).
4. Tests: 6.1. Done when:
   `.venv\Scripts\python.exe -m pytest tests\unit\test_excel_capabilities.py tests\unit\test_excel_frame_export.py tests\unit\test_file_output.py -q` passes (the regression test failed before: `ModuleNotFoundError`), and `.venv\Scripts\python.exe -m pytest tests\unit -q` still shows 334+ passed.

### Step 2 - Spec, sanitising helpers  (commit 2)

Files: `core/workpaper/__init__.py`, `spec.py`, `sanitize.py`, `tests/unit/test_workpaper_sanitize.py`. `sanitize.py` skeleton:

```python
EXCEL_MAX_ROWS = 1_048_576; HEADER_ROWS = 2; MAX_LISTED = EXCEL_MAX_ROWS - HEADER_ROWS   # 1_048_574
MAX_CELL_CHARS = 32_767
RESERVED_SHEETS = ("summary", "run log", "workflow")
_DANGER = re.compile(r"^(?:[=@\t\r]|[+-](?!\s*[\d.,]+\s*$))")
ID_NAME = re.compile(r"(?i)(^|[\W_])(id|no|num|number|ref|code|acct|account|invoice|po)($|[\W_])")
def safe_sheet_name(raw, used: set[str], default="Sheet") -> str: ...
def needs_quote_prefix(text: str) -> bool: return bool(_DANGER.match(text))
def danger_expr(col: "pl.Expr") -> "pl.Expr": ...      # starts_with/contains composition, no look-around
def unique_headers(names) -> list[str]: ...
def quote_sheet(name: str) -> str: return "'" + name.replace("'", "''") + "'"
def column_plan(schema, amount_column) -> list["ColumnPlan"]: ...   # name, header, kind, fmt_key, is_amount
```
Done when: `pytest tests\unit\test_workpaper_sanitize.py -q` passes.

### Step 3 - Streaming + Exceptions sheet  (commit 3)

Files: `stream.py` (`ExceptionStats`, `compute_stats`, `population_stats`, `amount_expr`, `sanitized_csv_lazy` - the computed literal must end with `.alias(<column name>)` or the CSV header becomes `literal` -, `sha256_file`), `sheets_exceptions.py` (`write_exceptions_sheet(wb, ws, spec, stats, parquet_path, plan, *, limit, csv_name, fmts) -> ExceptionsLayout(last_row, written, amount_col_letter, notes)`), tests `test_workpaper_exceptions_sheet.py`. Per batch: convert each column once to a Python list, then `for i in range(n)` call the per-column writer chosen once per column (`ColumnPlan.kind`), rows strictly ascending; stop at `limit`. Done when `pytest tests\unit\test_workpaper_exceptions_sheet.py -q` passes, including `-k streaming`.

### Step 4 - Summary sheet  (commit 4)

`sheets_summary.py`: `write_summary_sheet(wb, ws, spec, *, test, stats, pop, layout, csv_info, sources, notes, omitted, now, sheet_names) -> None`; row constants:

```python
R = dict(ref=5, client=6, engagement=7, period=8, test=9, prepared_by=10, prepared_on=11, reviewed_by=12, review_date=13,
         objective=16, procedure=17, criteria=18, res_hdr=21, pop=22, exc=23, listed=24, csv=25, recon=26,
         conclusion=29, notes=30, tick_hdr=33, tick_first=34)
```
Rows are written in ascending order with a cursor (spacer rows are simply skipped; `set_row` heights may be set at any time). Done when `pytest tests\unit\test_workpaper_summary_sheet.py -q` passes (asserts every labelled cell, formulas, cached values, validations, protection, image, print setup).

### Step 5 - Run log, Workflow sheets, context  (commit 5)

`context.py`, `sheets_runlog.py`, `tests/unit/test_workpaper_runlog_sheet.py`. Done when that file passes.

### Step 6 - Orchestrator, versioning, sidecar, node_runner  (commit 6)

```python
def write_workpaper(spec, exceptions, *, population=None, test=None, run_record=None, workflow=None, now=None):
    t0 = time.perf_counter(); now = now or datetime.now()
    spec = _validated(spec); require_xlsxwriter()
    tmp = tempfile.mkdtemp(prefix="td_wp_")
    try:
        pq = spool_parquet(exceptions, tmp)
        stats = compute_stats(pq, amount_column=spec.amount_column)
        plan = column_plan(stats.schema, spec.amount_column)
        pop = population_stats(population, amount_column=spec.amount_column) if population is not None else None
        limit = min(max(1, spec.row_limit), MAX_LISTED); final = _choose_path(spec.output_path, spec.if_exists)
        need_csv = stats.total > limit or any(v > MAX_CELL_CHARS for v in stats.max_len_by_column.values())
        csv_info = _write_sidecar(pq, plan, final, spec.if_exists) if need_csv else None
        names = _sheet_names(spec, run_record, workflow)
        wb = new_workbook(tmp_xlsx := os.path.join(tmp, "wp.xlsx"), tmp)
        sheets = {n: wb.add_worksheet(n) for n in names.all}            # tab order: Summary first
        layout = write_exceptions_sheet(wb, sheets[names.exceptions], spec, stats, pq, plan, limit=limit, csv_name=csv_info and csv_info.name)
        write_summary_sheet(wb, sheets["Summary"], ..., layout=layout, ...)   # different sheet => may be written after Exceptions (3.6)
        ... run log / workflow ...
        wb.close(); sha = _publish(tmp_xlsx, final, spec.if_exists)           # os.replace; PermissionError -> TD-OUT-002
        return WorkpaperResult(...)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
```
Done when `pytest tests\unit\test_workpaper_writer.py -q` passes.

### Step 7 - Engagement preferences  (commit 7)
`qt/preferences.py`, `preferences_dialog.py`, `tests/unit/test_preferences.py`, `tests/ui/test_workpaper_preferences.py`. Done when `pytest tests\unit\test_preferences.py tests\ui\test_workpaper_preferences.py -q` passes.

### Step 8 - Node, registration, snapshot helper, before-run hook  (commit 8)

Files: `core/node_configuration.py` (append `WORKPAPER_OUTPUT = auto()` after `FILE_OUTPUT`; value 5), `nodes/__init__.py`, `nodes/InOut/workpaper_output.py`, `qt/helpers/workflow_snapshot.py`, `workflow_execution_mixin.py`, `docs/NODE_REFERENCE.md`.

```python
{"module_path": "InOut.workpaper_output", "node_code": IONodes.WORKPAPER_OUTPUT,
 "node_type": NodeTypes.IO, "node_title": "Workpaper Output", "icon": "node_file_output"},
```
**Hook ownership:** plan 09 F-B adds the shared stubs in `workflow_execution_mixin.py` (a `before_run` hook list called on the GUI thread after `sorted_nodes = self.topologicalSort(connections)`, `:61`, with its own exception guard). This plan only implements `WorkpaperOutputContent.before_run()` and relies on F-B calling it. F-B provides `before_run_hooks` and `_run_before_run_hooks` (it calls each content's `before_run()`, then each hook callable; exceptions are logged and never raised); this plan adds nothing to the mixin.

Node skeleton:

```python
@register_node(IONodes.WORKPAPER_OUTPUT, NodeTypes.IO)
class TriggerNode_WorkpaperOutput(TriggerNode):
    icon = "node_file_output"; node_code = IONodes.WORKPAPER_OUTPUT; node_title = "Workpaper Output"
    node_type = NodeTypes.IO; content_label_objname = "trigger_node_workpaper_output"; style = {}
    def __init__(self, scene) -> None:
        super().__init__(scene, inputs=[1, 1, 1], outputs=[], input_text=["E", "P", "S"])
    def initInnerClasses(self) -> None:
        self.content = WorkpaperOutputContent(self); self.grNode = TriggerGraphicsNode(self)
        self.content.evaluate.connect(self.onInputChanged); self.param = []
    def evalImplementation(self):
        entries = []
        for i, role in enumerate(("Exceptions", "Population", "Summary")):
            node, sock = self.getInputWithSocketIndex(i)
            if node is None:
                if i == 0: return self._fail("Connect the Exceptions input")
                entries.append(None); continue
            val = node.eval()
            entry = val[sock] if isinstance(val, list) and 0 <= sock < len(val) else None
            if not entry or entry.get("data") is None: return self._fail(f"{role} input has no data")
            entries.append(entry)
        self.content.set_inputs(entries)
        self.param = []; self.value = self.param
        self.markInvalid(False); self.markDirty(False); self._set_node_tooltip("")
        self.evalChildren(); self._refresh_selected_node_config()
        return self.value
    def _fail(self, msg): self.markDirty(True); self.markInvalid(True); self._set_node_tooltip(msg); return None
    def get_code(self): return self.content.get_code()
```
Content: `serialized_state_schema` (3.2), `set_inputs`, `before_run()` (refreshes `collect_workflow(node)` and `collect_sources(node)`), `effective_spec()`, `get_code()`, `create_layout`, slots, `serialize/deserialize` (schema style), `validate_loaded_state()` (warning when `output_path == ""` and connected). `workflow_snapshot.py`: `collect_workflow(node) -> list[dict]`, `collect_sources(node) -> list[dict]` (uses `content.resolved_input_files(hash=False)` when present, else `filePath`/`selected_sheet`); ancestor walk via `getInputWithSocketIndex` and `getOrderedEdges()` for multi-input upstream nodes, visited set by `id`.
Done when: `pytest tests\unit\test_workpaper_node.py tests\unit\test_node_titles.py -q` passes.

### Step 9 - Config Dock UI  (commit 9)
Node module (`create_layout` ...), `tests/ui/test_workpaper_dock.py`. Done when it passes and `pytest tests\ui -q` shows exactly the baseline failures (20 failed, 7 errors).

### Step 10 - E2E golden, benchmark, docs  (commit 10)
`tests/e2e/test_workpaper_e2e.py`, fixtures, `tests/benchmarks/test_workpaper_perf.py`, `docs/NODE_REFERENCE.md`; no `trigger.spec` edit: plan 09 F-G globs `core/workpaper/*` and `core/excel/*` into the hidden imports (the modules `writer|node_runner|context|stream|sheets_exceptions|sheets_summary|sheets_runlog|sanitize|spec` are covered by that glob). Done when `pytest tests\e2e\test_workpaper_e2e.py -q`, `pytest tests\e2e -q` (21+ passed) and `pytest tests\benchmarks\test_workpaper_perf.py --run-benchmarks -q` pass.

---

## 5. Edge cases and their fixed behaviour

| Case | Behaviour |
|---|---|
| **Zero exceptions** | Valid workbook; Exceptions sheet header + `A3` `No exceptions noted`; Summary `B23=0` (formula `=B24`, cached 0), `F23` `No exceptions noted`; conclusion left blank. |
| **Over the limit** | `limit = clamp(row_limit, 1, 1_048_574)`; first `limit` rows listed; banner + `F24` + Notes + `truncated=True`; CSV sidecar with ALL rows; Summary `B23`/`C23` static. Excel max 1,048,576 rows includes banner and header, hence 1,048,574. A row limit above it is clamped with a Note. |
| **Sheet names** | `safe_sheet_name`; xlsxwriter raises `InvalidWorksheetName` otherwise (mapped to TD-OUT-014). |
| Duplicate/empty/colliding column names | 3.8 `unique_headers`. |
| **Formula injection** | 3.8: `write_string` + `quote_prefix` for data, headers and metadata; CSV sidecar `'`; numbers (`-5.2`, `+1,000`) untouched. |
| Strings > 32,767 chars | shortened with marker, sidecar forced, Note. |
| Control characters | `U+FFFD`, Note. |
| **Dates/timezones** | `write_datetime` + formats; tz stripped + Note; null -> real blank cell. |
| **Decimals** | amount summed as Float64, rounded for display; Notes state it. |
| Large ints (>= 10**15) | written as text. |
| Unicode | UTF-8 native; CSV sidecar with BOM. Tested with `ünï ✓ 日本`. |
| NaN / Inf | text. |
| **Target open in Excel** | `replace`: `~$` lock-file check + `PermissionError` -> TD-OUT-002; `version`: no collision. Publish via temp file + `os.replace`: failure leaves no partial target. |
| Output path not `.xlsx` | TD-OUT-012 (`.xls` rejected). Folder missing: TD-OUT-001. |
| **Missing optional inputs** | Population absent: Summary `B22/C22` from `test.population_rows` or input cells; Summary absent: settings only; reconciliation `No test result supplied`. A connected but failing optional input invalidates the node. |
| Summary frame with several rows/unknown columns | first row; unknown ignored; `parameters` JSON string tried with `json.loads`. |
| **Missing run record** | `Run log` omitted with reason on Summary, `omitted[...]`, Logging-dock line; never an error. |
| Amount column removed upstream | tooltip warning live; at write time value statistics `n/a` + Note. |
| Source file missing/moved/huge | row kept; `file not found`; > 4 GiB `not computed`. |
| Exceptions is an eager `DataFrame` | `write_parquet` path; same result. |
| > 16,381 data columns | TD-OUT-011. |
| Logo missing/corrupt | Note, workpaper still written. |
| File Output "excel" larger than Excel allows | > 1,048,575 data rows or > 16,384 columns -> TD-OUT-013 (never truncates); everything smaller is streamed. |
| Per-node 30 s limit | stated in the dock tooltip; lowering the row limit is the remedy (500k x 6 takes ~23 s of write time); the publish step is last, so a timeout leaves no half-written target. |

---

## 6. Test plan

`openpyxl` is a **test-time reader only**; application code must not import it (a unit test greps `src/trigger_designer` for `openpyxl` and for `import xlsxwriter` outside `core/excel/engine.py`).

`tests/support/workpaper.py`:

```python
import openpyxl
def load(path, data_only=False): return openpyxl.load_workbook(path, data_only=data_only)
def find_label(ws, label, col=1):
    for r in range(1, ws.max_row + 1):
        if ws.cell(r, col).value == label: return r
    raise AssertionError(f"label {label!r} not found in {ws.title}")
def value_right_of(ws, label): return ws.cell(find_label(ws, label), 2).value
def make_spec(tmp_path, **kw):
    from trigger_designer.core.workpaper.spec import WorkpaperSpec
    base = dict(output_path=str(tmp_path / "wp.xlsx"), title="Invoice approval test", client="Acme Ltd",
                engagement="FY2025 audit", period="Year ended 31 December 2025", preparer="A. Auditor",
                workpaper_ref="C.3.1", prepared_date="2026-03-31", test_name="Invoices above approval limit",
                purpose="Show that invoices above 1,500 were approved.", procedure="Filtered invoices >= 1,500.",
                criteria="Amount is at least 1,500.00", amount_column="Amount", app_version="0.1.0")
    base.update(kw); return WorkpaperSpec(**base)
FIXED_NOW = __import__("datetime").datetime(2026, 3, 31, 9, 30)
```

### 6.1 Step-1 tests (File Output "excel", Data Preview export, shared module)

`tests/unit/test_file_output.py` (add):

```python
def test_excel_format_generates_call_to_shared_exporter_without_collect():
    code = _make_content(file_format="excel", filePath="C:/t/o.xlsx").get_code()
    assert "write_frame_xlsx(var_in_lazy, 'C:/t/o.xlsx')" in code and ".write_excel(" not in code and ".collect()" not in code

def test_excel_format_executes_and_writes_readable_workbook(tmp_path):
    import openpyxl
    out = tmp_path / "out.xlsx"
    code = _make_content(file_format="excel", filePath=str(out)).get_code()
    exec(code, {"__name__": "__main__"}, {"var_in": pl.LazyFrame({"a": [1, 2], "b": ["x", None]})})   # raised ModuleNotFoundError before
    rows = [[c.value for c in r] for r in openpyxl.load_workbook(out).active.iter_rows()]
    assert rows == [["a", "b"], [1, "x"], [2, None]]
```
`tests/unit/test_excel_frame_export.py` (the Data Preview export calls the same function):
* `test_data_preview_export_path_uses_write_frame_xlsx` (source of `polars_table_viewer.py` contains `write_frame_xlsx`, not `write_excel`).
* `test_roundtrip_dates_nulls_floats_bools_nan`: `date`, `datetime`, `None` (blank), `1.5`, `True`, `NaN` -> openpyxl: `datetime` values with `yyyy-mm-dd`, `None`, `"NaN"`, bool.
* `test_header_is_bold_frozen_and_filtered`.
* `test_excel_row_limit_is_enforced_without_writing` (monkeypatch `MAX_ROWS=4`, 4 data rows -> TD-OUT-013, no file) and `test_exactly_at_limit_is_written` (3 data rows with `MAX_ROWS=4`).
* `test_streaming_50k_rows_bounded_memory` (marker `slow`; RSS delta < 150 MB).
* `test_only_engine_imports_xlsxwriter_and_nobody_imports_openpyxl` (grep of `src/trigger_designer`).
* `test_polars_write_excel_is_not_used` (grep `write_excel` in `src`).
* Hidden-import coverage of `core/excel/*` and `core/workpaper/*` is tested by plan 09 F-G's `test_packaging_spec.py`; no spec test here.

### 6.2 Capability pins and writer unit tests (`tests/unit`, no Qt)

`test_excel_capabilities.py` (each builds a workbook through `engine.new_workbook` and reads it back):
`test_formula_cached_value_is_readable_without_recalc` (`=COUNT(A1:A3)` cached 5 -> `data_only` 5; plain load string), `test_data_validation_list_present` (single cell + range), `test_freeze_panes_and_autofilter`, `test_sheet_protection_with_unlocked_cell`, `test_quote_prefix_format_roundtrip`, `test_write_string_formula_text_stays_string`, `test_long_string_returns_minus_two_and_truncates`, `test_control_char_is_escaped_by_library`, `test_constant_memory_rejects_earlier_row_write` (rc == -1), `test_constant_memory_allows_any_sheet_order` (Exceptions first, then Summary with `=COUNT('Exceptions'!$A$3:$A$5)` cached 3), `test_set_column_after_rows_in_constant_memory`, `test_last_excel_row_is_writable_and_next_is_not` (index 1,048,575 -> 0; 1,048,576 -> -1), `test_image_insert_in_constant_memory` (PIL-generated PNG), `test_tab_colour_gridlines_print_setup_properties`, `test_nan_requires_option` (TypeError), `test_invalid_sheet_name_raises`.

`test_workpaper_sanitize.py`: `test_safe_sheet_name_truncates_and_strips_illegal_chars`, `..._is_unique_case_insensitive`, `..._avoids_reserved_names`, `test_quote_sheet_doubles_apostrophes`, `test_needs_quote_prefix_table` (`=1+1` T, `@SUM(A1)` T, `+cmd|x` T, `-cmd` T, `\tx` T, `\rx` T, `-5.2` F, `+1,000` F, `- 3` F, `ok` F, `""` F, `a=b` F), `test_polars_and_python_danger_predicates_agree`, `test_guard_text_replaces_control_chars_and_shortens` (marker, <= 32,767), `test_unique_headers_rules` (`["", "Ref", "ref", "A"]` -> `["Column 1","Ref (data)","ref (data)","A"]`), `test_integer_identifier_columns_use_plain_format`, `test_amount_expr_parses_accounting_strings` (`["1,234.50","(12.00)"," 7 ","x",""]` -> `[1234.5,-12.0,7.0,None,None]`).

`test_workpaper_exceptions_sheet.py` (spec via `make_spec`, frames inline):
* `test_exceptions_sheet_layout_headers_and_freeze`: `A1` `Showing all 3 exception rows.`; `A2:C2 == ["Ref","Tick mark","Auditor comment"]`; data headers from `D2`; `freeze_panes == "B3"`; `auto_filter.ref == "A2:F5"`; `A3:A5 == [1,2,3]`.
* `test_exceptions_number_and_date_formats` (int `#,##0`, id `0`, float `#,##0.00`, date `yyyy-mm-dd`, datetime `yyyy-mm-dd hh:mm:ss`, bool, null -> `None`).
* `test_amount_column_written_as_numbers_even_from_strings` (`["1,234.50","(12.00)","oops"]` -> `1234.5`, `-12.0`, `"oops"`; Note names `1 value`).
* `test_tick_validation_covers_every_data_row` (`"✓,X,E,F,N/A"`, `B3:B<last>`).
* `test_zero_exceptions_sheet`.
* `test_formula_injection_cells_are_text_with_quote_prefix`: `=HYPERLINK("http://x","y")`, `+1+1`, `@x`, `-5.5`, `ok` -> first three `data_type "s"`, `quotePrefix` True; `-5.5` and `ok` False; header named `=evil` also text with prefix.
* `test_control_chars_and_long_strings_are_handled` (`a\ufffdb`; 40,000 chars -> <= 32,767 ending with the marker; `csv_path` not None).
* `test_timezone_is_stripped_and_noted`, `test_unicode_and_headers`, `test_nan_and_inf_become_text`, `test_large_int_becomes_text`.
* `test_truncation_with_lowered_limit`: `row_limit=5` over 12 rows -> `A1` starts `TRUNCATED - showing the first 5 of 12`; `A3:A7 == 1..5`; `A8` empty; `result.truncated`, totals 12/5; sidecar has 12 data rows with `Ref` 1..12; its SHA-256 is on Summary `B25`; tab colour `FFC00000`.
* `test_row_limit_is_clamped_to_excel_maximum` (pure: `min(max(1, 5_000_000), MAX_LISTED) == 1_048_574`; Note emitted).
* `test_streaming_memory_for_50k_rows` (marker `slow`): 50k x 8 columns, psutil sampler: peak RSS delta < 150 MB.

`test_workpaper_summary_sheet.py` (dataset = the E2E dataset, 6.4; amounts as Float):
* `test_summary_fixed_labels_and_values` (labels `A5:A13`, `A16:A18`; `B5 == "C.3.1"`, `B6 == "Acme Ltd"`, `B9`, `B10`, `B11 == datetime(2026,3,31)`, `B12`/`B13` empty, `B18`).
* `test_results_block_values_and_formulas`: `B22 == 10`, `C22 == 9956.6`; plain load `B24 == "=COUNT('Exceptions'!$A$3:$A$5)"`, `C24 == "=SUM('Exceptions'!$F$3:$F$5)"`, `B23 == "=B24"`, `C23 == "=C24"`, `D23 == '=IFERROR(B23/B22,"n/a")'`; `data_only`: `B24 == 3`, `C24 == 6700.75`, `B23 == 3`, `C23 == 6700.75`, `D23 == 0.3`, `E23 == approx(0.6729958)`.
* `test_truncated_summary_uses_static_totals`.
* `test_conclusion_validation_and_unlocked_inputs` (validation on `B29` exactly `"No exceptions,Exceptions - explained,Exceptions - require follow-up"`; `B12`, `B13`, `B29`, `B30` `locked False`; `B5` locked; `ws.protection.sheet is True`).
* `test_tick_legend_counts` (`A34:A38`, `F34 == "=COUNTIF('Exceptions'!$B$3:$B$5,A34)"`, cached 0).
* `test_missing_population_and_summary_make_input_cells`, `test_test_info_reconciliation_difference`, `test_test_info_fills_blank_settings`, `test_sources_table_hashes_and_notes`, `test_workbook_contents_lists_omitted_sheets`.
* `test_logo_added_and_bad_logo_noted` (valid PNG -> `len(ws._images) == 1`; bad path -> none + Note `Logo not added`).
* `test_print_setup_tab_colour_and_properties` (landscape, fit-to-width, footer, gridlines off, tab colour `FF305496`, `wb.properties.title == spec.title`, `creator == "A. Auditor"`).
* `test_summary_written_after_exceptions_has_correct_formulas` (guards the 3.6 decision: Summary cached values equal the Exceptions content although Summary was written second).

`test_workpaper_runlog_sheet.py`: `test_run_log_header_pairs`, `test_run_log_steps_table_rows` (3 nodes; failed row `Column not found - Check the column name`, fill `F8CBAD`), `test_in_progress_banner_when_status_running`, `test_missing_keys_render_not_recorded`, `test_none_record_omits_sheet_with_reason`, `test_workflow_sheet_lists_nodes_settings_and_comments`, `test_sheets_are_protected`.

`test_workpaper_writer.py`: `test_end_to_end_writes_four_sheets_in_order`, `test_custom_exceptions_sheet_name_is_sanitised_and_formulas_follow`, `test_if_exists_version_creates_numbered_copy` (first file bytes unchanged), `test_if_exists_replace_overwrites`, `test_if_exists_fail_raises_td_out_004`, `test_missing_folder_raises_td_out_001`, `test_wrong_extension_raises_td_out_006`, `test_zero_columns_raises`, `test_replace_when_excel_lock_file_exists_raises_td_out_002`, `test_replace_when_target_is_locked_raises_td_out_002` (Windows only: hold the target open with an exclusive handle), `test_failed_write_leaves_no_partial_target_and_cleans_temp` (monkeypatch `Workbook.close` to raise; no `td_wp_*` left), `test_eager_dataframe_input_matches_lazy`, `test_exceptions_plan_is_executed_once` (counter in a `map_batches` plan), `test_xlsxwriter_missing_raises_td_out_003` (`sys.modules["xlsxwriter"] = None`), `test_spec_json_roundtrip_and_unknown_keys_ignored`, `test_run_workpaper_parses_summary_frame`, `test_run_workpaper_uses_registered_run_record_provider`.

`test_workpaper_node.py` (node in a `TriggerSubWindow`, brief 9.2 skeleton; `Source` doubles): `test_node_is_registered_with_stable_op_id` (`input.workpaper_output`, `IONodes.WORKPAPER_OUTPUT == 5`), `test_unwired_exceptions_marks_invalid_with_tooltip`, `test_optional_inputs_do_not_invalidate`, `test_failed_optional_input_invalidates`, `test_get_code_unwired_raises_and_wired_calls_runner` (idempotent: two calls equal), `test_get_code_executes_and_writes_workbook`, `test_user_text_is_embedded_safely` (client `O'Brien"; import os; os.system("x") #`; `B6` equals the raw text; no side effect), `test_serialize_roundtrip_and_old_file_defaults`, `test_inherits_engagement_preferences`, `test_workflow_snapshot_lists_ancestors_and_comments`, `test_before_run_hook_is_called_by_execute_workflow` (hook exceptions do not abort the run).

### 6.3 UI tests (`tests/ui/test_workpaper_dock.py`, brief 9.3)

`test_dock_empty_state_without_exceptions_input`; `test_dock_sections_and_controls_exist` (rows by label text; H30; `NoWheelComboBox`; Logo row present); `test_text_edit_is_debounced_and_recorded_once` (type `Acme`, `qtbot.wait(400)` -> one step `Workpaper Client Changed`; undo -> `""`; redo); `test_amount_column_combo_lists_exceptions_columns_and_undoes`; `test_row_limit_spin_clamps_and_merges_burst`; `test_if_exists_combo_maps_labels_to_values`; `test_undo_does_not_rerecord`; `test_dock_survives_force_rebuild_after_restore`; `test_create_layout_direct_call_has_no_exception`; `tests/ui/test_workpaper_preferences.py::test_preferences_engagement_section_roundtrip` (five fields; Reset All restores defaults). No assertion may depend on the 27 baseline ui failures.

### 6.4 Golden E2E (`tests/e2e/test_workpaper_e2e.py`)

Fixtures (`tests/e2e/fixtures/workpaper/`, UTF-8, LF): `population.csv`

```
Invoice,Vendor,Amount
INV001,Acme,100.00
INV002,Borealis,250.50
INV003,Corvus,1200.00
INV004,Acme,75.25
INV005,Delta,980.00
INV006,Zenith,1500.75
INV007,Corvus,40.00
INV008,Acme,3000.00
INV009,Delta,610.10
INV010,Borealis,2200.00
```
`exceptions.csv`

```
Invoice,Vendor,Amount,Note
INV006,Zenith,"1,500.75",Above limit
INV008,Acme,3000.00,=1+1
INV010,Borealis,2200.00,Above limit
```
(Population value 9,956.60; exceptions value 6,700.75; rows rate 0.3; value rate 0.672995801779724. `"1,500.75"` exercises amount parsing; `=1+1` the injection guard.)

`test_workpaper_end_to_end_from_workflow(qtbot, tmp_path, no_modal_dialogs)` (programmatic graph per brief 9.4; no checked-in `.tds` because paths are absolute): FileInput(exceptions.csv) -> Workpaper input 0; FileInput(population.csv) -> input 1; settings `output_path=tmp/out/wp.xlsx`, client/period/preparer/`prepared_date="2026-03-31"`/test name/objective/procedure/criteria/`amount_column="Amount"`; `saveToFile`; reload in a new window (`fileLoad is True`, `validateLoadedWorkflow() == []`); `run_workflow_and_wait`. Assertions on `wp.xlsx` (openpyxl, plain and `data_only`):
* `wb.sheetnames == ["Summary","Exceptions","Workflow"]` (no run record -> `Run log` omitted).
* Summary: `B5..B13` per settings; `B22 == 10`; `C22 == 9956.6`; `B24 == 3`; `C24 == 6700.75`; `D23 == 0.3`; `E23 == approx(0.6729958)`; `F23 == "Counted from the Exceptions input"`; `B25` starts `Not needed`; `A42` ends `exceptions.csv`, `A43` ends `population.csv`; `F42` equals the real SHA-256 of `exceptions.csv`; `B29` blank with validation; `A34 == "✓"`; `ws.protection.sheet`.
* Exceptions: headers `Ref, Tick mark, Auditor comment, Invoice, Vendor, Amount, Note`; `F3 == 1500.75`, `F4 == 3000.0`, `F5 == 2200.0` (numbers from strings); `G4 == "=1+1"` with `data_type == "s"` and `quotePrefix` True; `freeze_panes == "B3"`; `auto_filter.ref == "A2:G5"`.
* Workflow: a row per File Input and the Workpaper node; File Input settings text contains `exceptions.csv`.
Further tests: `test_second_run_creates_numbered_copy_not_overwrite` (`wp (2).xlsx`; original hash unchanged); `test_summary_input_reconciles` (Summary double `exception_rows=3, population_rows=10, test_name="From node", criteria="Amount >= 1,500"` -> `B9 == "From node"`, `B26 == "Agrees to the test node (3 exceptions)"`); `test_workpaper_with_run_record_provider` (registers `set_run_record_provider(lambda: RECORD)`, clears it in `finally`; `Run log` present); `test_file_output_excel_end_to_end` (File Input -> File Output excel -> Run -> openpyxl equals the input, all text). No CSV golden (`TRIGGER_UPDATE_E2E_GOLDENS` not involved): the explicit cell expectations are the golden.

### 6.5 Memory/performance (`tests/benchmarks/test_workpaper_perf.py`, `--run-benchmarks`)

`test_500k_exceptions_stream_with_bounded_memory`: build 500,000 x 8 lazily (no pandas); `write_workpaper(spec(row_limit=1_048_574), lf)` with an RSS sampler thread (50 ms). Assert: `exceptions_written == 500_000`, no sidecar, peak RSS delta < 400 MB (probe: +86 MB for 6 columns; margin for 8 columns), wall time < 120 s (probe: 23.3 s for 3M cells, ~35 s expected), readable: openpyxl `read_only=True` row count == 500,002, Summary `B24` cached `500000`. `test_over_limit_500k_writes_csv_sidecar`: `row_limit=100_000` -> sheet rows 100,002, sidecar has 500,000 data rows (counted by streaming lines). `test_write_frame_xlsx_500k_x_6_bounded_memory` (File Output path): same bounds.

### 6.6 Coverage map

| Risk | Test |
|---|---|
| Excel dependency missing again | step-1 tests + `test_xlsxwriter_missing_raises_td_out_003` |
| Library behaviour changes on upgrade | `test_excel_capabilities.py` |
| Wrong numbers on Summary | `test_results_block_values_and_formulas`, E2E |
| Silent truncation | `test_truncation_with_lowered_limit`, banner/Summary/Notes asserts |
| Injection | sanitize table, exceptions-sheet test, E2E `=1+1` |
| Memory blow-up (double collect) | `test_exceptions_plan_is_executed_once`, 50k test, 500k benchmark |
| Overwriting an annotated workpaper | `test_if_exists_version_creates_numbered_copy`, E2E second run |
| `constant_memory` row-order bug | `test_constant_memory_*`, `test_summary_written_after_exceptions_has_correct_formulas` |
| Undo double-recording | UI undo tests |

---

## 7. Acceptance checklist

- [ ] (provided by plan 09 F-G; verify only) `xlsxwriter>=3.2.0,<4` declared in `pyproject.toml`; `uv.lock` has exactly one new package stanza; installed in `.venv`; `trigger.spec` hidden imports updated.
- [ ] Only `core/excel/engine.py` imports `xlsxwriter`; no application code imports `openpyxl`; Polars `write_excel` is not used (tests).
- [ ] File Output "excel" and Data Preview "Export Excel" use `write_frame_xlsx`, stream with bounded memory, and fail with TD-OUT-013 only above Excel's real limits.
- [ ] `IONodes.WORKPAPER_OUTPUT` appended at the end; `input.workpaper_output` resolves; `tests/unit/test_node_titles.py` passes; node in palette and Shift+A menu.
- [ ] Sheets `Summary`, `Exceptions`, optional `Run log`, `Workflow`, in order; every Summary address in 3.10 holds the stated content; formulas have cached values; logo, print setup, tab colours present.
- [ ] Zero exceptions, over-limit, long strings, control chars, tz-aware datetimes, NaN/Inf, unicode, injection cells behave per section 5 with tests.
- [ ] Over-limit run writes the full CSV sidecar and records its hash; truncation announced in 5 places.
- [ ] Default `if_exists="version"` never overwrites; locked target -> TD-OUT-002; no partial files.
- [ ] No second collect of the exceptions plan; 500k benchmark within limits.
- [ ] Engagement preferences stored in `preferences.ini`; node inherits and can override.
- [ ] Dock follows AGENTS.md; undo/redo/force rebuild tested.
- [ ] `ruff format` + `ruff check` clean on touched files (do not fix the 76 pre-existing `core/` errors).
- [ ] Baselines: unit >= 334 + new, e2e >= 20 + new, ui failures unchanged (20 failed, 7 errors).

---

## 8. Verification commands

```powershell
.venv\Scripts\python.exe -m ruff format <changed files>
.venv\Scripts\python.exe -m ruff check <changed files>

# step 1
.venv\Scripts\python.exe -m pytest tests\unit\test_excel_capabilities.py tests\unit\test_excel_frame_export.py tests\unit\test_file_output.py -q
# steps 2-6
.venv\Scripts\python.exe -m pytest tests\unit\test_workpaper_sanitize.py tests\unit\test_workpaper_exceptions_sheet.py tests\unit\test_workpaper_summary_sheet.py tests\unit\test_workpaper_runlog_sheet.py tests\unit\test_workpaper_writer.py -q
# steps 7-9
.venv\Scripts\python.exe -m pytest tests\unit\test_preferences.py tests\unit\test_workpaper_node.py tests\unit\test_node_titles.py -q
.venv\Scripts\python.exe -m pytest tests\ui\test_workpaper_dock.py tests\ui\test_workpaper_preferences.py -q
# step 10
.venv\Scripts\python.exe -m pytest tests\e2e\test_workpaper_e2e.py -q
.venv\Scripts\python.exe -m pytest tests\benchmarks\test_workpaper_perf.py --run-benchmarks -q

# layer sweeps at the end (never bare `pytest`, brief 2.4)
.venv\Scripts\python.exe -m pytest tests\unit -q      # 334 + new, 0 failed
.venv\Scripts\python.exe -m pytest tests\e2e -q       # 20 + new, 0 failed
.venv\Scripts\python.exe -m pytest tests\ui -q        # failures == baseline (20 failed, 7 errors)
```

Frozen-build smoke (once, record the result): `scripts\build.bat`, run the exe, File Output -> excel -> Run; then Workpaper Output -> Run (proves the hidden imports cover the `exec`'d imports). Manual smoke: open the workpaper in Excel (no repair prompt; pick a conclusion from the dropdown; tick a row; edit a protected cell is blocked, an unlocked one allowed); Run twice -> `name (2).xlsx`; with `Replace` while the file is open in Excel -> plain "open in Excel" error in the Logging dock.

---

## 9. Pitfalls

1. **`constant_memory` row order.** Never write to a row lower than the last written row *of the same sheet*; the write is dropped with return code `-1` and no exception. Sheets are independent (3.6), so only cursors per sheet matter. The cell helpers assert `rc >= 0` in tests (`-2` only on the long-string path).
2. **Merged cells in `constant_memory`**: only single-row merges (`B16:F16`). A multi-row merge breaks the ordering rule.
3. **`ws.write()` guesses types** (`=...` becomes a formula). Use `write_string`/`write_number`/`write_datetime`/`write_boolean`/`write_blank`/`write_formula` explicitly; a unit test greps `core/` for `".write("` calls.
4. **Polars regex has no look-around** (verified). The Polars predicate is composed from `starts_with`/`contains`; the Python regex keeps its look-ahead. Keep the shared-table test.
5. **`sink_csv` with a computed literal** needs `.alias(<original name>)` or the header becomes `literal`.
6. **`map_elements(str)` on List columns returns the Series repr** - convert via `Series.to_list()`.
7. **CSV-derived frames are all Strings** (brief 7.1). Only `amount_column` is converted; do not guess other numeric columns.
8. **`get_code()` runs on the worker thread**: plain attributes only; all scene walking in `before_run()`/live eval.
9. **`evalImplementation` returns `[]`** (falsy): verify with `test_optional_inputs_do_not_invalidate`; if the base treats it as failure return `[{"data": None, "variable_name": ""}]` as `param` and keep `outputs=[]`.
10. **Every `.py` under `qt/widgets/nodes/` is imported at startup**: keep helpers in `qt/helpers/` and `core/`.
11. **`ConfigSection` is not an undo composite**: set `_undo_composite = True` on each section (brief 6.4), else each edit records twice.
12. **No `uv sync`**; use `uv lock --upgrade-package` + `uv pip install`; check `git diff uv.lock`.
13. **Forward slashes** in the embedded output path (`file_output.py:242`).
14. **Excel recalculates on open** and asks to save on close; expected.
15. **Hash cost**: SHA-256 of multi-GB inputs takes seconds; capped at 4 GiB; runs on the worker thread.
16. **Per-node 30 s timeout** (brief 4.2): large workpapers can exceed it; the publish step is last so no half-written target; the temp dir may remain (OS temp cleanup).
17. **Windows locks**: catch exactly `PermissionError` on `os.replace`.
18. **Inline strings**: in `constant_memory` mode xlsxwriter writes inline strings, so files are larger than with the shared-string table; readers handle both.
19. **Do not read preferences inside `core/`**; pass resolved values (keeps CLI/headless use possible).

---

## 10. Interfaces with other plans and the standalone fallback

### 10.1 From plan 04 (`TestSummary`)

Plan 04's convention (brief 10.3): socket 2 of an audit test node is a **one-row summary frame** whose columns are the `TestSummary` fields; Workpaper Output input 2 consumes it. Columns read (all optional): `test_name`, `criteria`, `status`, `message` (str), `population_rows`, `exception_rows` (int), `exception_rate` (float), `parameters` (JSON string or struct, rendered in Notes as `Test parameters: k=v; ...`). Population/exception *values* are not in `TestSummary`; the writer computes them from `amount_column`. Stub before plan 04: the `Source` double of brief 9.2 emitting `pl.LazyFrame({"test_name": ["T"], "criteria": ["C"], "population_rows": [10], "exception_rows": [3]})`. No import of plan 04 code; `TestInfo` is this plan's tolerant parser.

### 10.2 From plan 02 (run record)

* `core/workpaper/context.py` exposes `set_run_record_provider(fn)`. **Implemented by plan 02** (it adds `RunRecorder.snapshot(record)` and the provider call): plan 02 calls `set_run_record_provider(lambda: recorder.snapshot(record))` in `executeWorkflow` (H1) and `set_run_record_provider(None)` in `_on_workflow_finished` (H4); `snapshot()` returns a **deep-copied plain dict** taken under a lock (the provider is called on the worker thread while the GUI thread appends node records).
* Keys read (`.get` only): `run_id, status, started_at, finished_at, user, machine, app_version, python_version, polars_version, workflow_path, workflow_sha256, inputs[], outputs[], nodes[]`; file entry: `role, path, sheet, size_bytes, modified_time, sha256, node_id`; node: `node_id, op, title, label, status, started_at, duration_s, rows_out{var:int|None}, warnings[], error{title, hint, code}|None` (brief 11.3).
* Inside a run the record is in progress; the banner says so.
* Source files table: `run_record["inputs"]` take precedence (they carry run-time hashes); `collect_sources` and manual `source_files` add missing paths; rows read = sum of `rows_out` of the node with the matching `node_id`.
* **Degrades gracefully when plan 02 is absent** (no provider registered, `current_run_record()` returns None): `Run log` omitted with the stated reason; sources from `collect_sources` (+ manual list) hashed by the writer.

### 10.3 From plan 03 (errors)

`ExcelWriteError`/`WorkpaperError` carry `.code`. Plan 03 owns `TD-OUT-001..009` (001 folder missing, 002 file open elsewhere, 003 Excel writer missing, 004 invalid file name, 005 disk full, 006 nothing connected); this plan reuses 001-003 and 006 with those meanings and owns **`TD-OUT-010..014`**. Plan 03's catalogue already contains the generic pass-through rule "an exception carrying a `.code` that starts with `TD-` is looked up in the catalogue" (title/hint from the table, `technical = str(exc)`); this plan relies on that rule and asks for no special hook. Table to paste into plan 03's catalogue (area `OUT`, severity `error`):

| Code | Title | Hint |
|---|---|---|
| `TD-OUT-010` | A workpaper with this name already exists | Choose another file name, or set "If the file exists" to New version. |
| `TD-OUT-011` | The table has too many columns for Excel | Excel allows at most 16,384 columns; select fewer columns before writing. |
| `TD-OUT-012` | The workpaper settings are not valid | Check the output file (it must end in .xlsx) and the Prepared on date (YYYY-MM-DD). |
| `TD-OUT-013` | The table is too large for an Excel sheet | An Excel sheet holds at most 1,048,575 data rows; save it as CSV or Parquet instead. |
| `TD-OUT-014` | Excel could not create the workbook | A sheet name or cell content is not valid for Excel; rename the sheet or shorten the text. |

Until plan 03 lands, the constants live in `core/excel/errors.py` and the messages are already plain language (the executor's `str(exc)` is readable without the catalogue).

### 10.4 From plan 07 (Comment node)

Expected: op ending `.comment` with `content.comment_text: str` (fallback `serialize()["text"]`). Until it exists no comment is found; tests use a stub with `comment_text`. Optional: any content may implement `describe_settings() -> list[tuple[str, str]]` for the Workflow sheet.

### 10.5 From plan 01 (inputs)

`collect_sources` uses `content.resolved_input_files(hash=False)` when present, else `filePath`/`selected_sheet`. No hard dependency.

### 10.6 From plan 08 (CLI / scheduling)

`write_workpaper` and `run_workpaper` are Qt-free and take resolved values only, so a headless runner can call them; plan 08 may raise the 30 s node time limit for large workpapers. The `before_run` hook is called by `executeWorkflow`; a headless run that bypasses `executeWorkflow` must, for every node in `sorted_nodes` and before `WorkflowWorker(sorted_nodes, executor).run()`, execute exactly this on the thread that owns the scene:

```python
for node in sorted_nodes:
    hook = getattr(getattr(node, "content", None), "before_run", None)
    if callable(hook):
        hook()   # signature: before_run(self) -> None; no arguments; never raises (logs and keeps the previous snapshot)
```

Otherwise the Workflow sheet shows the last live snapshot. `before_run` is idempotent and GUI-thread-only.

**Generated-code import allowlist (for plan 08's code policy / op_catalog).** Besides `import polars as pl`, the generated code of these ops imports exactly:

| Op | Module | Names |
|---|---|---|
| `input.workpaper_output` | `trigger_designer.core.workpaper.node_runner` | `run_workpaper` |
| `input.file_output` (excel branch) | `trigger_designer.core.excel.frame_export` | `write_frame_xlsx` |

Allowed prefixes for the policy: `trigger_designer.core.excel.frame_export` (name `write_frame_xlsx`) and `trigger_designer.core.workpaper.node_runner` (name `run_workpaper`); every other module of `core/workpaper` is imported only by `node_runner`, never by generated text. Test `test_generated_imports_match_allowlist` parses both nodes' `get_code()` with `ast` and asserts the imported `(module, names)` set equals this table.

### 10.7 Standalone fallback with manually entered metadata

With none of plans 01-04 and 07 installed the node works end to end: connect Exceptions only, type client/period/test name/objective/procedure/criteria into the dock (or Preferences -> Engagement), optionally list source files (hashed by the writer), Run writes `Summary` (population cells are yellow input cells), `Exceptions`, `Workflow`; `Run log` is omitted with its reason. The golden E2E tests 1-2 (6.4) exercise exactly this configuration.
