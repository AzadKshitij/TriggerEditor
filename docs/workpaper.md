# Audit workpapers (Excel)

Two ways to get a filed, formatted `.xlsx` out of a workflow, plus the shared Excel writer that
File Output and the Data Preview now use.

| Where | What it writes |
|---|---|
| **Workpaper Output** node (IO family) | One test: `Summary`, `Exceptions`, `Run log`, `Workflow` |
| **File > Export Workpaper...** | The last recorded run: `Summary` (one row per audit test), `Run log`, `Workflow` |
| **File Output** with format *Excel*, Data Preview *Export Excel*, Data Profile *Excel workbook* | One sheet, streamed |

## Workpaper Output node

Inputs: **E** Exceptions (required), **P** Population (optional), **S** Summary (optional: the
one-row Summary of an Audit node, so test name, criteria and counts reconcile). No outputs. Nothing is
written while you edit; the workbook is written by **Run**.

Settings (Config Dock): *File* and *If it exists* (**New version** keeps `wp (2).xlsx` instead of
overwriting an annotated copy; *Replace*; *Stop with error*), *Engagement* (reference, client,
engagement, period, prepared by, prepared on, logo; empty fields come from Preferences > Engagement),
*Test* (name, objective, procedure, criteria), *Values* (amount column, decimals), *Sheets* (row limit,
exceptions sheet name, include run log / workflow), *Sources* (extra files, one path per line).

### Sheets

* **Summary** (protected except the yellow input cells): engagement block, objective and procedure,
  results (population, exceptions found, exceptions listed, reconciliation to the test node), conclusion
  (dropdown), auditor notes, tick-mark legend with live counts, source files with SHA-256, notes and
  limitations, workbook contents. The numbers tie to the Exceptions sheet with formulas that also carry
  cached values, so viewers that do not recalculate still show them.
* **Exceptions**: `Ref`, `Tick mark` (dropdown), `Auditor comment`, then your columns. Header frozen,
  filter on, nothing protected. Row 1 says "Showing all N exception rows." or **TRUNCATED**.
* **Run log**: run id, who/where, versions, workflow SHA-256, input/output files with hashes, and one row
  per step. Written while the run is in flight, so it says so and lists the steps finished so far.
  Omitted (with the reason on the Summary) when run recording is off.
* **Workflow**: the steps that produced the data with their settings, then the Comment nodes of the
  canvas.

### Rules that never change

* **No silent truncation.** Above the row limit (default 100,000, at most 1,048,574) the sheet lists the
  first rows, says so in five places, and writes every row to `<name>_exceptions_full.csv` next to the
  workbook (its row count and SHA-256 are on the Summary). Text over Excel's 32,767-character limit
  is shortened with a marker and forces the CSV.
* **No formula injection.** Every string is stored as text; text that starts with `=`, `@`, `+x` or
  `-x` also gets the quote-prefix format so editing the cell cannot turn it into a formula. The CSV
  prefixes such cells with `'`.
* **Never overwrite by accident**: *New version* is the default; a file open in Excel gives a plain
  "open in Excel" error (TD-OUT-002); the workbook is built in a temp folder and moved into place last.
* **Bounded memory.** The Exceptions input is run once into a temp Parquet file and streamed in
  50,000-row batches (`constant_memory`), so 500,000 rows need on the order of 100 MB.
* Amounts stored as text (`1,234.50`, `(12.00)`) are parsed for the value statistics; values that
  cannot be read stay text and are counted in the notes. Time zones are removed (the clock time is kept).

## File > Export Workpaper...

Needs a recorded run (Preferences > Audit trail > *Record every run*). Choose the file, engagement
details, objective and procedure. The Summary lists each audit test of the run (status, population,
exceptions, rate, criteria, outcome). Sheets: `Summary`, `Run log` (completed run), `Workflow`.

## Engagement defaults

Preferences > General > **Engagement**: client, engagement, period, prepared by, logo (PNG/JPG). They
fill every empty field of the node and of the export dialog. The preparer falls back to the OS user name.

## For developers

```python
from trigger_designer.core.workpaper import WorkpaperSpec, write_workpaper, write_run_workpaper
result = write_workpaper(spec, exceptions_frame, population=pop, test=TestInfo(...),
                         run_record=record_dict, workflow=steps)      # one test
result = write_run_workpaper(spec, run_record=record_dict, workflow=steps)   # a whole run
```

* `core/excel/` is the only package that imports `xlsxwriter` (`engine.py`); `write_frame_xlsx` is the
  shared one-sheet export. `core/workpaper/` is Qt-free; the node and dialog live in `qt/`.
* Generated code of the node calls `trigger_designer.core.workpaper.node_runner.run_workpaper(...)`
  with the spec as JSON; headless callers can call it directly (it needs no Qt, and reads the in-flight
  run record through `trigger_designer.core.audit.recorder.get_run_record_provider`).
* `before_run()` of the node (called on the GUI thread by Run Workflow, or by a headless runner for every
  node before the worker starts) snapshots the Engagement preferences, the workflow and the source files,
  because `get_code()` runs on a worker thread.
* Error codes: TD-OUT-001 folder missing, 002 file open elsewhere, 003 `xlsxwriter` missing, 010 workpaper
  exists (*Stop with error*), 011 too many columns, 012 invalid settings (path must end in `.xlsx`,
  Prepared on `YYYY-MM-DD`), 013 too many rows for one sheet, 014 Excel could not create the workbook.
