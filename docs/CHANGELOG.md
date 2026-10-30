# Changelog

Everything on branch `feature` since it diverged from `main` (merge base
`ee997d9`). Written from `git log main..feature` as of commit `9745a25` (121 commits); the list is refreshed at the end of the work. Regenerate the raw,
grouped commit list with `python scripts/gen_changelog_stub.py` and diff it
against this file.

Each bullet ends with the short hash of the commit(s) that introduced it,
linked to `https://github.com/AzadKshitij/TriggerEditor`.

Not part of this branch: the error translator, the input-type readers, the
shaping framework and the undo stack were merged to `main` earlier (plans 01, 03,
07 first wave); this branch only maintains them (see "Fixes and maintenance").

Sections: [Added](#added) · [Changed](#changed) ·
[Behaviour changes that may affect saved workflows](#behaviour-changes-that-may-affect-saved-workflows) ·
[In progress](#in-progress) · [Fixes and maintenance](#fixes-and-maintenance) ·
[Known issues](#known-issues)

## Added

### Audit nodes (new "Audit" family, Shift+A group)

- A new node family `audit` with a shared base: stable `TD-AUDIT-nnn` errors, a
  one-row Summary, an "exceptions" output, a "Count exceptions now" button and
  a Result section in the dock. [`4dc7fe4`](https://github.com/AzadKshitij/TriggerEditor/commit/4dc7fe4)
- **Duplicates**: exact or near matching (amount tolerance, date window) on any
  key columns; outputs Duplicates, Unique and Summary. [`731aec3`](https://github.com/AzadKshitij/TriggerEditor/commit/731aec3)
- **Gaps**: missing, repeated and out-of-order document numbers, and days with no
  entry (weekends and listed holidays can be skipped). [`af0556f`](https://github.com/AzadKshitij/TriggerEditor/commit/af0556f)
- **Benford**: first or first-two-digit distribution of an amount column with a
  verdict and a chart; reads at most the leading rows live, all rows on Run. [`333e78b`](https://github.com/AzadKshitij/TriggerEditor/commit/333e78b)
- **Sample**: a reproducible draw (same rows, settings and seed give the same
  sample whatever the row order; algorithm id `td-sample-1`) plus a Selection log. [`8d972cb`](https://github.com/AzadKshitij/TriggerEditor/commit/8d972cb)
- **Risk Filters**: seven journal-entry risk indicators in one pass with a
  weighted `risk_score`; reports `warn`, never `fail`. [`ea7205d`](https://github.com/AzadKshitij/TriggerEditor/commit/ea7205d)
- Usage guide and icon preview for the five nodes. [`c2caff7`](https://github.com/AzadKshitij/TriggerEditor/commit/c2caff7)

### Audit trail and Run History

- **Every Run now writes an immutable run record** (JSON, SHA-256 hash chain,
  append-only index) next to the saved workflow in `<workflow>.runs/` (or the
  folder chosen in Preferences). It holds inputs and outputs with SHA-256, row
  counts, schemas, settings, generated code, errors and each audit test's
  Summary. [`eeb5035`](https://github.com/AzadKshitij/TriggerEditor/commit/eeb5035) [`b11059e`](https://github.com/AzadKshitij/TriggerEditor/commit/b11059e) [`215d6b5`](https://github.com/AzadKshitij/TriggerEditor/commit/215d6b5) [`814abd8`](https://github.com/AzadKshitij/TriggerEditor/commit/814abd8) [`ee6cc70`](https://github.com/AzadKshitij/TriggerEditor/commit/ee6cc70)
- Run compare, "check inputs" (re-hash now), display rows and HTML/JSON export. [`e518fd9`](https://github.com/AzadKshitij/TriggerEditor/commit/e518fd9)
- **Run History dock**: list, verify the chain, compare two runs, check inputs,
  export. [`3220cf0`](https://github.com/AzadKshitij/TriggerEditor/commit/3220cf0) Its icons: [`36c8452`](https://github.com/AzadKshitij/TriggerEditor/commit/36c8452)
- "Audit trail" group in the General preferences page (record on/off, folder,
  identity, hashing, row-count mode, embed code, warn on changed input). [`9ca3af4`](https://github.com/AzadKshitij/TriggerEditor/commit/9ca3af4)
- Opt-in overhead benchmark (`--run-benchmarks`) and extra tests. [`ba38ca9`](https://github.com/AzadKshitij/TriggerEditor/commit/ba38ca9) [`35efb45`](https://github.com/AzadKshitij/TriggerEditor/commit/35efb45) [`91ebe32`](https://github.com/AzadKshitij/TriggerEditor/commit/91ebe32)

### Run: cancel and a Qt-free run loop

- **Cancel button** next to Run: cooperative cancel that stops before the next
  node and records the run as `cancelled`. [`5791a4a`](https://github.com/AzadKshitij/TriggerEditor/commit/5791a4a)
- The node loop is now `core/ExecutionCheck/run_loop.py::run_nodes` (stop or
  continue on error, skip the nodes below a failure, cancel between nodes), shared
  by the GUI worker and the command line. [`21dcb3e`](https://github.com/AzadKshitij/TriggerEditor/commit/21dcb3e)
- `ExecutionResult.policy_violation` and variables added by an `after_node` hook
  reach the results and the shared namespace. [`019b16f`](https://github.com/AzadKshitij/TriggerEditor/commit/019b16f)

### Security

- `core/sql_guard.py`: one read-only DuckDB sandbox (text rules plus DuckDB's
  parser, then a locked in-memory connection with external access off). [`92e8332`](https://github.com/AzadKshitij/TriggerEditor/commit/92e8332)
- `core/codegen_safe.py`: user text is quoted or reduced to identifier characters
  before it can reach generated code (a node title, sheet name, delimiter, id). [`f881de6`](https://github.com/AzadKshitij/TriggerEditor/commit/f881de6)
- `trigger-designer-cli` script entry, the Qt-free core packages listed for
  PyInstaller, and a warning dialog when the Data Preview Excel export fails. [`0c89206`](https://github.com/AzadKshitij/TriggerEditor/commit/0c89206)

### Command line (`trigger-designer-cli`)

Runs a saved workflow with no window, for schedulers, scripts and CI. User guide
`docs/guide/cli.md`, reference `docs/CLI.md`, developer page `docs/dev/cli-internals.md`.

- Front end and read-only commands: argparse tree with exit 64 for usage errors, the
  frozen exit-code contract (0 to 10, 64, 130), the Qt-free op catalogue and
  tolerant workflow reader, `info` and `validate`. [`efe94bf`](https://github.com/AzadKshitij/TriggerEditor/commit/efe94bf)
- Run-time parameters (`params list|add|remove`, an allow-list of 12 settings),
  path remapping (`--input-dir`, `--output-dir`, relative paths and `filePathRel`),
  `paths --relativize`, and `approve` (SHA-256 pinning of the exact file). [`27d3c5c`](https://github.com/AzadKshitij/TriggerEditor/commit/27d3c5c)
- Safety and supervision: generated-code policy (allowed syntax and imports, no
  file/OS/network access, only declared paths, SELECT-only SQL), per-workflow run
  lock with stale-run recovery, JSON-lines event stream, timeout, memory limit and
  cancel handling. [`10bb241`](https://github.com/AzadKshitij/TriggerEditor/commit/10bb241)
- `run` and `--dry-run`: the editor's own nodes on Qt's offscreen platform, the
  shared run loop and run recorder, outputs staged and moved into place only when
  every node succeeded, `--keep-going`, run records and `<id>.cli.json` sidecars,
  `verify-log`, Ctrl+C / Ctrl+Break / SIGTERM. [`b74095c`](https://github.com/AzadKshitij/TriggerEditor/commit/b74095c) Tests: editor/CLI parity,
  policy corpus, plan, session and verify. [`2564af4`](https://github.com/AzadKshitij/TriggerEditor/commit/2564af4)
- `schedule add|list|show|remove` for Windows Task Scheduler (task XML, `S4U` option,
  no stored password, `--print-only`). [`306fe79`](https://github.com/AzadKshitij/TriggerEditor/commit/306fe79)
- Frozen-build safe command loading, quiet `validate --deep`, the workpaper output
  seam. [`f6bdef5`](https://github.com/AzadKshitij/TriggerEditor/commit/f6bdef5) `trigger-designer-cli.exe` ships beside the editor (PyInstaller
  `MERGE` build, `build.bat` smoke test, installer `addtopath` task). [`891120a`](https://github.com/AzadKshitij/TriggerEditor/commit/891120a) Runbook
  `docs/CLI.md`. [`75c825b`](https://github.com/AzadKshitij/TriggerEditor/commit/75c825b) Generated-code imports must be covered by `trigger.spec`
  (test). [`774f5f8`](https://github.com/AzadKshitij/TriggerEditor/commit/774f5f8)

### New nodes (shaping and report)

- **Text to Columns** [`f15ef8a`](https://github.com/AzadKshitij/TriggerEditor/commit/f15ef8a), **Window** (look-back/ahead, rank, running and
  rolling) [`b938824`](https://github.com/AzadKshitij/TriggerEditor/commit/b938824), **Fuzzy Match** (Jaro-Winkler/Levenshtein with blocking) [`5ab510f`](https://github.com/AzadKshitij/TriggerEditor/commit/5ab510f),
  **Multi-Field Formula** (one SQL template over many columns) [`ff665fb`](https://github.com/AzadKshitij/TriggerEditor/commit/ff665fb),
  **SQL Query** (one read-only SELECT over the inputs) [`050d952`](https://github.com/AzadKshitij/TriggerEditor/commit/050d952), **Comment**
  (a canvas note that never runs) [`b520882`](https://github.com/AzadKshitij/TriggerEditor/commit/b520882). Their op-code members were reserved
  first. [`5befa54`](https://github.com/AzadKshitij/TriggerEditor/commit/5befa54)
- **Data Profile** (Report): per-column nulls/blanks, distinct counts, min/max,
  numeric statistics with a histogram, top values, suggested type and quality
  flags (numbers or dates stored as text, mixed dates, leading zeros, outliers). [`c006735`](https://github.com/AzadKshitij/TriggerEditor/commit/c006735)
- Float spin boxes in shaping forms take a step and decimals (Reconcile tolerance,
  Fuzzy threshold). [`4ba5249`](https://github.com/AzadKshitij/TriggerEditor/commit/4ba5249)

### Canvas and appearance

- Nodes snap to the grid while dragging (Alt bypasses it) and an **Arrange** menu
  (align, distribute, row/column/grid, snap selection). [`45b1904`](https://github.com/AzadKshitij/TriggerEditor/commit/45b1904)
- Application **font size** setting (8-20 pt) in Preferences > Appearance. [`e6ed0f4`](https://github.com/AzadKshitij/TriggerEditor/commit/e6ed0f4)
- A yellow mark on a node whose changes have not run yet. [`60a7a50`](https://github.com/AzadKshitij/TriggerEditor/commit/60a7a50)
- The Select table editor was rebuilt and its columns can be resized. [`ac6c9e0`](https://github.com/AzadKshitij/TriggerEditor/commit/ac6c9e0) [`6a7deb7`](https://github.com/AzadKshitij/TriggerEditor/commit/6a7deb7)
- 13 node icons redrawn; proposals for all 26 kept under `docs/assets/icon_proposals`. [`d7da8a3`](https://github.com/AzadKshitij/TriggerEditor/commit/d7da8a3)

## Changed

- **A node now runs when you leave it**, not on every edit: Config Dock edits
  reach the model, the undo stack and the checkbox at once; the pipeline runs when
  another node is selected or the canvas is clicked. Applies to all shaping nodes,
  Formula, Filter, Rows, File Input and Union. [`dd576f0`](https://github.com/AzadKshitij/TriggerEditor/commit/dd576f0) [`448e643`](https://github.com/AzadKshitij/TriggerEditor/commit/448e643)
- Buttons and actions use Material Symbols (`qt-material-icons`) tinted per
  theme instead of compiled PNG/SVG sets; node menu icons load from the SVG
  files and `icons_rc` is gone. [`02f8232`](https://github.com/AzadKshitij/TriggerEditor/commit/02f8232) [`b27cfae`](https://github.com/AzadKshitij/TriggerEditor/commit/b27cfae) [`1a39435`](https://github.com/AzadKshitij/TriggerEditor/commit/1a39435)
- Run script location: see the behaviour list below. [`3a7eebb`](https://github.com/AzadKshitij/TriggerEditor/commit/3a7eebb)
- Excel files (File Output, Data Preview export) are now written by the shared
  streaming writer in `core/excel` (constant memory, Excel limits reported as
  `TD-OUT-011`/`TD-OUT-013`, a locked file as `TD-OUT-002`). [`e2b610a`](https://github.com/AzadKshitij/TriggerEditor/commit/e2b610a)

## Behaviour changes that may affect saved workflows

Read these before opening an old `.tds` file or re-running an old workflow.

1. **`random()`, `uuid()`, `gen_random_uuid()` and `setseed()` are rejected in SQL
   expressions** (Formula, Filter expression mode, Multi-Field Formula, SQL Query),
   together with `getenv`, `read_*`, `glob`, `*_scan`, `duckdb_*`, `pragma_*`,
   `current_setting`, `FROM 'file'`, `COPY`, `ATTACH`, `PRAGMA`, dollar-quoted and
   `E''` strings and multiple statements. A node that used one now fails with
   `TD-SHAPE-112` (or `-110`/`-111`) instead of running, so that a re-run reproduces
   the same numbers. Use the Sample node with a seed for randomness. Verified in
   `core/sql_guard.py::_DENIED_CALLS`, `tests/unit/test_sql_guard.py` and
   `tests/unit/test_duckdb_safety.py`. [`92e8332`](https://github.com/AzadKshitij/TriggerEditor/commit/92e8332) [`3580284`](https://github.com/AzadKshitij/TriggerEditor/commit/3580284); quoted column names that
   merely contain a denied word are accepted [`5e5baea`](https://github.com/AzadKshitij/TriggerEditor/commit/5e5baea).
2. **Run re-evaluates every node first.** A node that was never evaluated, or whose
   edit was pending, used to run its empty-frame fallback and silently produce an
   empty result; it now runs for real, and nodes that stay invalid are reported in
   the Logging dock. [`d3d49c6`](https://github.com/AzadKshitij/TriggerEditor/commit/d3d49c6)
3. **A broken lazy plan now fails at the node that built it.** After each node the
   executor resolves the schema of every `LazyFrame` it created, so a missing
   column or bad join key no longer "succeeds" until some later sink. Workflows
   with no sink that used to report success may now report a failure. [`d3d49c6`](https://github.com/AzadKshitij/TriggerEditor/commit/d3d49c6)
4. **The run script moved.** `check_output.py` is no longer written to the working
   directory; it goes to `<app data>/last_run/check_output.py` and contains the code
   that actually ran. [`3a7eebb`](https://github.com/AzadKshitij/TriggerEditor/commit/3a7eebb)
5. **Runs write files next to the workflow.** `<workflow>.runs/` appears beside a
   saved `.tds` (record JSON files, `index.jsonl`, `hash_cache.json`); records are
   made read-only. Turn it off or relocate it in Preferences > General > Audit
   trail. Do not commit these folders. [`ee6cc70`](https://github.com/AzadKshitij/TriggerEditor/commit/ee6cc70)
6. **Filter: rows whose comparison is null go to the unmatched output**, so the
   two outputs cover every input row (builder mode `fill_null(True)`; expression
   mode `IS NOT TRUE`). **Aggregate** keeps first-appearance group order instead of
   arbitrary order. Outputs of saved workflows can differ. [`53cc14b`](https://github.com/AzadKshitij/TriggerEditor/commit/53cc14b)
7. **Blank CSV header cells are named `column_<position>`** (stepping around names
   the file already uses) on every CSV read path, so such a column now appears in
   Select and in the output (the golden for the Split workflow gained a
   `column_1`). [`0123d98`](https://github.com/AzadKshitij/TriggerEditor/commit/0123d98) [`c3035e5`](https://github.com/AzadKshitij/TriggerEditor/commit/c3035e5)
8. **Saved files**: `workflow_metadata` now carries a stable `workflow_uuid`, keeps
   keys this version does not know, and the file is written atomically as UTF-8; a
   file saved by this version is still readable by the previous one (extra keys are
   ignored). [`db8e430`](https://github.com/AzadKshitij/TriggerEditor/commit/db8e430)
9. **Excel output**: text cells starting `=`, `@`, `+x`, `-x` are written as text
   (quote-prefixed), never as formulas; a table with more than 16,384 columns
   (`TD-OUT-011`) or more than 1,048,575 data rows (`TD-OUT-013`) is reported as an
   error instead of failing inside the library; cell text is limited to 32,767
   characters.
   [`e2b610a`](https://github.com/AzadKshitij/TriggerEditor/commit/e2b610a)
10. **Record ID** accepts a negative or very large *Start* (it used to raise). [`a1fbaf6`](https://github.com/AzadKshitij/TriggerEditor/commit/a1fbaf6)
11. A saved multi-sheet Excel File Input no longer stores file metadata as one file
    per sheet (it was three times the real size). [`5ae3826`](https://github.com/AzadKshitij/TriggerEditor/commit/5ae3826)
12. Audit amount parsing: decimal-comma amounts are read correctly and
    mixed forms are treated as unreadable (warning `TD-AUDIT-102`) rather than
    mis-read. [`1c0a7f9`](https://github.com/AzadKshitij/TriggerEditor/commit/1c0a7f9)

## In progress

Not final; internals documented later (`docs/dev/workpaper-internals.md`).

- **Workpaper**: Qt-free writer (Summary, Exceptions, Run log, Workflow, run
  workpaper) [`1604afe`](https://github.com/AzadKshitij/TriggerEditor/commit/1604afe), Engagement defaults in Preferences (client, engagement,
  period, preparer, logo) [`d7fbcde`](https://github.com/AzadKshitij/TriggerEditor/commit/d7fbcde), shared streaming Excel writer [`e2b610a`](https://github.com/AzadKshitij/TriggerEditor/commit/e2b610a).

## Fixes and maintenance

- Error system (maintenance of the version already on `main`): dead API removed and
  translator code shared [`b068287`](https://github.com/AzadKshitij/TriggerEditor/commit/b068287); a late enrichment no longer restores a fixed
  run error [`d13f855`](https://github.com/AzadKshitij/TriggerEditor/commit/d13f855); a translator rule corrected [`53cc14b`](https://github.com/AzadKshitij/TriggerEditor/commit/53cc14b); a guard test that every
  `TD-` literal is in the catalogue (and `TD-SHAPE-*` in `ERROR_CODES`) [`9df89e4`](https://github.com/AzadKshitij/TriggerEditor/commit/9df89e4).
- Input types (maintenance): one error helper, one settings list [`cf5900b`](https://github.com/AzadKshitij/TriggerEditor/commit/cf5900b); dead
  code removed and Excel metadata fixed [`5ae3826`](https://github.com/AzadKshitij/TriggerEditor/commit/5ae3826); File Input defers its run until the
  node is left [`448e643`](https://github.com/AzadKshitij/TriggerEditor/commit/448e643).
- Editing: a red Formula node re-evaluates once its text is valid [`259d378`](https://github.com/AzadKshitij/TriggerEditor/commit/259d378);
  Formula sections are trial-run on the first 100 rows while editing [`d3a4d00`](https://github.com/AzadKshitij/TriggerEditor/commit/d3a4d00);
  Formula type and target changes were dropped on PySide6 [`d55b17b`](https://github.com/AzadKshitij/TriggerEditor/commit/d55b17b); debounce timers
  flushed when the dock is left or rebuilt [`cd3ee9c`](https://github.com/AzadKshitij/TriggerEditor/commit/cd3ee9c); a pending debounced text edit
  survives another control committing [`9890d2f`](https://github.com/AzadKshitij/TriggerEditor/commit/9890d2f); live shaping no longer has a row
  cap that could never trigger [`984a1fc`](https://github.com/AzadKshitij/TriggerEditor/commit/984a1fc).
- Canvas: fit/zoom node visibility [`3b405fc`](https://github.com/AzadKshitij/TriggerEditor/commit/3b405fc); one status glyph per node [`208e7df`](https://github.com/AzadKshitij/TriggerEditor/commit/208e7df);
  node drag and drop on PySide6 [`4ca7fa8`](https://github.com/AzadKshitij/TriggerEditor/commit/4ca7fa8); light-theme checkboxes, selection text,
  tooltips and hover [`8829c4c`](https://github.com/AzadKshitij/TriggerEditor/commit/8829c4c); readable and larger table checkboxes/dropdowns [`362f6a5`](https://github.com/AzadKshitij/TriggerEditor/commit/362f6a5).
- Audit refactor: shared live notice and failure hooks; unreadable-value pluralisation
  and date-format message fixed [`1b34ab9`](https://github.com/AzadKshitij/TriggerEditor/commit/1b34ab9).
- Repository hygiene: 68 MB comparison CSV untracked [`c73417f`](https://github.com/AzadKshitij/TriggerEditor/commit/c73417f) [`97a3cce`](https://github.com/AzadKshitij/TriggerEditor/commit/97a3cce); legacy
  stylesheets and compiled resource modules removed [`d93d3cd`](https://github.com/AzadKshitij/TriggerEditor/commit/d93d3cd); unused imports and an
  empty module removed [`561bfd2`](https://github.com/AzadKshitij/TriggerEditor/commit/561bfd2); `check_output.py` path refactor [`baea998`](https://github.com/AzadKshitij/TriggerEditor/commit/baea998).
- Audit amounts: `amount_expr` is cheaper for amounts without a comma ([`297aacc`](https://github.com/AzadKshitij/TriggerEditor/commit/297aacc)); opt-in Audit performance budgets on one million rows ([`158d5ed`](https://github.com/AzadKshitij/TriggerEditor/commit/158d5ed)).
- Tests: `no_modal_dialogs` applied by default to `tests/e2e` [`2bdefa8`](https://github.com/AzadKshitij/TriggerEditor/commit/2bdefa8); goldens
  for the audit workflows [`2113a6e`](https://github.com/AzadKshitij/TriggerEditor/commit/2113a6e); Split goldens regenerated [`c3035e5`](https://github.com/AzadKshitij/TriggerEditor/commit/c3035e5).

## Known issues

As of the commit above. Details and evidence in `docs/dev/*.md`.

1. **Per-node duration and peak memory in run records are always 0.0.**
   `RunRecorder.node_finished` reads `execution_time`/`peak_memory` that
   `ExecutionResult` no longer has (the post-run memory check was removed in
   [`5ae3826`](https://github.com/AzadKshitij/TriggerEditor/commit/5ae3826)); the Run History dock and HTML export show no per-node timing. The
   unit tests use fakes that carry the fields.
2. **Preferences > Errors > "continue past failure" has no effect**: the Run always
   stops at the first failed node (`WorkflowExecutionMixin._run_policy`).
3. **Adding a field to `RunRecord` makes `verify` report older records as
   `schema_invalid`** (the required-key list is derived from the dataclass).
4. **Cancel is cooperative**: the node that is executing finishes (bounded by its
   30 s timeout); a timed-out node leaks its worker thread.
5. **Run records are not git-ignored** (`*.runs/`), and `check_output.py` /
   `dataframe_export.csv` are tracked although generated. Tracked
   `savedfiles/Example_2_Retail_Ledger/app_workflow/1.tds` is rewritten by saving.
6. **Several documents are stale** against this branch: `CONTRIBUTING.md`
   (Python 3.13.12, `tests/integration`, `uv sync` warning), `AGENTS.md`
   (`:/qss_icons` fallback), `docs/plan/00-codebase-brief.md`,
   `docs/SESSION_HANDOFF.md`, `docs/ENHANCED_EXECUTOR_GUIDE.md`,
   `.github/skills/create-node/SKILL.md` (corrections in `docs/dev/architecture.md`
   and `docs/dev/adding-a-node.md`).
7. Test-suite state and flaky areas: see `docs/dev/testing.md` (unit 2233 passed, e2e 102 passed and 1 stale golden since regenerated, ui 974 passed and 5 failed on the in-progress CLI print guard, all measured on e2b610a).
8. Generated code is not standalone: the exported run script imports
   `trigger_designer.core.*` and needs this source tree on `sys.path`.
9. Truncating the tail of a run-record chain is undetectable by design; note the
   `head_hash` printed by verify.
10. Command line, found while writing its docs (see `docs/dev/cli-internals.md` section 17):
    `approve` without `--yes` and with stdin from `NUL` exits 3 instead of 64; a
    console code page that cannot print a path character (cp1252 pipe) makes a
    command exit 3 unless `PYTHONUTF8=1`; `approve`, `info` and `paths` do not list the
    Workpaper Output path; `paths --relativize` finds nothing on a mapped or `subst`
    drive; the Task Scheduler cycle, the installer's PATH task and the packaged exe on
    a machine without Python have not been run.
