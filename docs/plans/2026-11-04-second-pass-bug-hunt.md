# Second-pass bug hunt and fix plan (2026-11-04)

Companion to `2026-10-31-trigger-designer-bug-hunt.md` (first 20 findings) and
`2026-11-01-node-evaluation-and-laziness.md`. This pass covers areas the first
pass did not: join/append/unique/sort/find-replace/aggregate/window/normalize/
transpose/assign/record-id/split, SQL expression rewriting, input discovery,
the headless CLI (plan, params, paths, locks, schedule, workflow validation),
and layout/arrange persistence.

Method: source review plus focused `uv run python` probes against Polars 2.0
and DuckDB. Each finding below was reproduced unless marked **source-only**.

Severity is about user impact, not fix effort.

---

## High

### H1. A backslash in any column name breaks every Formula and Filter node
- File: `src/trigger_designer/core/shaping/sql_expression.py:44-51`
  (`replace_column_names`), reached from `formula.py:103-105` and
  `filter.py:187`.
- Symptom: `re.sub(pattern, replacement, ...)` treats the quoted column name
  as a replacement template, so `\` starts an escape. The failure happens for
  **every** column in the schema because the loop at `sql_expression.py:83-84`
  calls the rewriter once per available column, even when the formula never
  references it. A CSV/Excel header such as `Net\Gross` therefore disables all
  Formula and Filter nodes in the workflow.
- Reproduced:
  - `prepare_expression_sql("Amount > 0", ["Amount", r"Net\Gross"])`
    -> `re.PatternError: bad escape \G at position 4`.
  - `formula.run_node(...)` with that schema raises the raw `PatternError`
    (the call at `formula.py:184` is outside the `try`, so it is not converted
    to a `ShapingError`).
  - `filter.run_node(...)` converts it to `TD-SHAPE-004 bad escape \G ...`,
    but still fails on an unrelated column.
- Fix: make the replacement literal, e.g.
  `re.sub(pattern, lambda _match: replacement, segment, flags=re.IGNORECASE)`,
  or `replacement.replace("\\", "\\\\")`. Add a regression test with a
  backslash header and a formula that does not use it.

### H2. Transpose fails when a column is called `Name` or `Value`
- File: `src/trigger_designer/core/shaping/transpose.py:49-62`.
- Symptom: `unpivot(..., variable_name="Name", value_name="Value")` collides
  with an existing input column of either name. A key column named `Name` or
  `Value`, or a data column named `Name`, fails with a raw Polars
  `DuplicateError: duplicate column name 'Name'`.
- Reproduced:
  - key `Name` + data `Jan,Feb` -> `DuplicateError: duplicate column name 'Name'`.
  - key `Value` -> `DuplicateError: duplicate column name 'Value'`.
  - data column `Name` (key `k`) -> same error.
- Fix: unpivot with sentinel internal names (`__td_var`, `__td_val`) and rename
  them to `Name`/`Value` afterwards, choosing unique names when the input
  already has them. Add tests for all three cases.

### H3. Join right-only output loses the join key value
- File: `src/trigger_designer/core/shaping/join.py:265-281` (`right_final`).
- Symptom: when the mapping joins differently named keys (`id` -> `customer`)
  and the left frame also has a non-key column with the right key's name,
  `coalesce=True` puts the right key value in the left-named key column, while
  the right key name survives as the left's data column. `right_final` selects
  the latter, so a right-only row shows `customer = null` instead of its key,
  and the actual value appears in a column that is not selected.
- Reproduced: left `{id: [1,2], customer: ["left-a","left-b"]}`, right
  `{customer: [1,3], amount: [10,30]}`, mapping `id`->`customer`:
  `right_only = {'customer': [None], 'amount': [30]}`. The value `3` is lost.
- Fix: build the right-only output from the right frame (with its rename map),
  not by name-testing the join result; or map the coalesced left key back to
  the right key name when `right_key` is a coalesced key. Add a test with
  different key names plus a same-named left column.

### H4. Join suffix collision renames columns silently and adds a null column
- File: `src/trigger_designer/core/shaping/join.py:185-192` (right rename to
  `_right`), `253-259` (`left_final`), `265-272` (`right_final`).
- Symptom: if the left frame already has the column the right conflict is
  renamed to, Polars applies `LEFT_SUFFIX` on top. The joined output then keeps
  the left's value under `x_right` and puts the right's value in `x_right_left`,
  which reads as the wrong side. The left-only output gains a spurious
  all-null `x_right_left` column, so its schema no longer matches the left
  input.
- Reproduced: left `{id, x_right, x}`, right `{id, x}`:
  - joined: `x_right = 'L1'` (left), `x_right_left = 'R1'` (right);
  - left_only: extra `x_right_left = None`.
- Fix: derive left-only/right-only from the original frames, or assign rename
  targets with `unique_name` against both schemas and keep an explicit
  source->output map instead of testing suffixes.

---

## Medium

### M1. A duplicate key pair in a join mapping panics the Polars engine
- File: `src/trigger_designer/core/shaping/join.py:27-39`
  (`sanitize_mapping` dedupes only identical pairs) and `196-203`.
- Symptom: two mappings that target the same right key (or the same left key)
  reach `join(right_on=[..., ...])`. Polars 2.0 panics in Rust with
  `PanicException` (`__POLARS_COALESCE_KEYCOL_1 not found`). `PanicException`
  derives from `BaseException`, so `except Exception` handlers in node
  evaluation and error enrichment do not catch it.
- Reproduced with mapping `[a->x, b->x]`; the process survives but the
  exception bypasses normal error reporting.
- Fix: reject a repeated left or right key in `sanitize_mapping` with
  `TD-SHAPE-004` (or drop the later pair) before calling Polars.

### M2. `--input-dir` destroys a glob-pattern input
- File: `src/trigger_designer/core/headless/paths.py:20-21`
  (`remap_into_dir` keeps only the basename), called from
  `headless/params.py:495`.
- Symptom: a File Input saved as `D:\in\*\data.csv` becomes
  `<input-dir>\data.csv`, switching the node from pattern mode to single-file
  mode. The run silently reads one file instead of the folder tree, and the
  inputs list shows a different file set than the saved workflow.
- Reproduced by inspection of `remap_into_dir`: `basename_any` drops every
  wildcard segment. Docs describe the basename rule for ordinary files but do
  not warn that patterns break.
- Fix: keep the path tail after the first glob segment (rebase the pattern), or
  reject a glob with `--input-dir` and point the user at `--param`.

### M3. Run-lock acquisition has an empty-file race
- File: `src/trigger_designer/core/headless/locks.py:105-130`, with
  `_read` at `70-75` and `_owner_alive` at `33-45`. **Source-only** (timing
  dependent).
- Symptom: `os.open(O_EXCL)` creates the lock and the payload is written
  afterwards through `os.fdopen`. A second process that sees the file in
  between reads `{}` (an empty file is a `ValueError`), `_owner_alive({})`
  returns False because there is no pid, so it sweeps, unlinks the lock and
  starts. Both runs then write the same outputs. Separately, `_owner_alive`
  returns False when `psutil` cannot read the process create time, so a live
  lock from another user can be swept.
- Fix: write the payload with `os.write(fd, payload)` before closing, treat an
  unparseable lock younger than a small grace period as busy, and treat an
  unknown create time as alive.

### M4. Join key dtype mismatch shows a raw Polars schema dump
- File: `src/trigger_designer/core/shaping/join.py` before the join at
  `196-203`.
- Symptom: an `Int64` left key against a `String` right key raises Polars
  `SchemaError` with the resolved plan, not a `ShapingError`. The UI shows a
  multi-line engine dump and no `TD-SHAPE-*` code; `require_columns` checks
  names only.
- Reproduced: `join.run_node` with `id: i64` vs `id: str` ->
  `SchemaError: datatypes of join keys don't match ... Resolved plan until failure`.
- Fix: compare `schema_of(left)[key]` with `schema_of(right)[key]` and raise
  `TD-SHAPE-091`-style error naming both columns; optionally allow a safe
  numeric cast.

### M5. `os.stat` failures escape as raw `OSError` during input listing
- File: `src/trigger_designer/core/inputs.py:311` (single), `333` (folder),
  `363` (pattern).
- Symptom: a file deleted or made inaccessible between `scandir`/`exists` and
  `stat` raises `FileNotFoundError`/`PermissionError` instead of
  `InputReadError`. The GUI and CLI then lose the `TD-IN-*` code and the
  message that names the file. Network shares and temp folders hit this.
- Fix: wrap each `os.stat` in `try/except OSError`, and either skip with a
  warning (`inputs.py` already collects warnings) or raise
  `InputReadError("unreadable", ...)` with the path.

### M6. Corrupt `layout/state_version` crashes startup
- File: `src/trigger_designer/qt/layout_state.py:116`.
- Symptom: `int(settings.value(STATE_VERSION_KEY, 0) or 0)` raises
  `ValueError` for a hand-edited or truncated INI value, before the window is
  shown, so the app cannot be opened to fix it.
- Fix: guard with `try/except (TypeError, ValueError)` and fall back to 0, as
  the geometry/size readers already do.

---

## Low

### L1. Reserved internal names collide with real columns
- Files: `core/shaping/window.py:16, 207` (`__pos`),
  `core/shaping/split.py:37` (`__split_idx`).
- Symptom: an input that already contains that header fails with
  `DuplicateError: duplicate column name __pos` instead of working or raising
  a coded error.
- Reproduced for Window. Low because the names start with `__`, but Excel
  exports can carry them.
- Fix: `unique_name(POS, schema)` and use the chosen name in the sort/drop
  steps.

### L2. Case-insensitive column rewriting resolves both names to the first
- File: `core/shaping/sql_expression.py:83-84` with `44-51`.
- Symptom: with columns `A` and `a`, `[A] + [a]` becomes `"A" + "A"`; the
  second column is unreachable, silently producing a wrong number.
- Fix: resolve bracket tokens in one pass against a case-insensitive map, and
  prefer an exact-case match before a case-insensitive one.

### L3. Date Helper's unreadable-date chip mislabels its sample
- File: `core/shaping/date_helper.py:214` (`head(10_000)`) and `233`
  ("first 100 rows").
- Symptom: the chip can say "5,000 unreadable dates ... (first 100 rows)",
  which is internally contradictory and misleads the user about scope.
- Fix: report the actual sample size, or count only `LIVE_SAMPLE_ROWS`.

### L4. Dry run writes to the state directory
- File: `core/headless/plan.py:321-341`; also the writability probe at
  `251-252, 265-279`.
- Symptom: `mode="dry"` still plans staging, creates cross-volume staging
  directories (`336-337`), creates a work directory and writes the ASCII work
  copy (`338-341`), and `_check_outputs` creates/deletes a probe file. The
  docstring says dry means "no lock/files"; `--dry-run` therefore leaves
  artefacts and touches output folders.
- Fix: skip staging/work-copy creation in dry mode, or create them in memory
  and clean up; skip `_probe_writable` when `dry_run` is set (disk-space and
  exists checks can stay).

### L5. Static validation reports a false cycle when ids repeat
- File: `core/headless/workflow_file.py:145-169`.
- Symptom: duplicate node ids collapse in `indeg` but not in `ids`, so
  `seen != len(ids)` reports a cycle for an acyclic file. Reproduced with two
  nodes both `id: 1` and no edges -> `find_cycle` True.
- Fix: validate that ids are unique (a clear `TD-CLI-001` finding) and compare
  `seen` with `len(indeg)`.

### L6. `Distribute` moves an outermost node when the selection is too tight
- File: `qt/helpers/node_arrange.py:210-242`; docstring at `213-216`.
- Symptom: the docstring promises the outermost nodes stay put, but when the
  selection cannot hold its own widths the gap bottoms at 0 and the last node
  is pushed right/下. Reproduced by inspection: nodes at 0/100/150 with widths
  100 -> result 0/100/200.
- Fix: anchor the last node and distribute only the interior nodes, or reword
  the docstring to match the clamping behaviour.

### L7. `schedule` does not catch `subprocess.TimeoutExpired`
- File: `core/headless/schedule.py:277-286`; callers at
  `cli/commands/schedule.py:101, 159`.
- Symptom: if `schtasks` hangs beyond 60 s, the CLI raises an uncaught
  `TimeoutExpired` traceback instead of `TD-CLI-016`. `_live_rows` already
  catches `SubprocessError`; add/remove do not.
- Fix: catch `subprocess.TimeoutExpired` in `_run_schtasks` and raise
  `CliError(ExitCode.SCHEDULER, "TD-CLI-016", ...)`.

### L8. Function aliases are rewritten inside bracket identifiers
- File: `core/shaping/sql_expression.py:63-65, 80-82`.
- Symptom: `[strip(code)]` becomes `[trim(code)]` because the alias rewrite
  runs on code segments that still contain `[...]` references. Likewise
  `in_between` can rewrite a bracket name containing a comma.
- Reproduced for `strip`. Contrived, but the same pass could skip bracket
  tokens the way it skips string literals.
- Fix: add `\[[^\]]*\]` to the token pattern in
  `apply_outside_string_literals` (or mask brackets before applying aliases).

---

## Verified as working / intentional (do not "fix")

- `core/sql_guard.py`: read-only SELECT check, masked text, parser check,
  `enable_external_access=false`, locked config. The probes confirm the
  two-layer defence holds; the DuckDB `FROM 'file'` bypass is blocked.
- `--timeout 0` -> no timeout: documented in `cli/parser.py:205`.
- `--input-dir` dropping `filePathRel` and using the saved basename: documented
  in `docs/guide/cli.md:156, 233` (the glob case in M2 is the undocumented
  exception).
- Split's `row_index < max * percent` cut: documented in `split.py:28-33` and
  pinned by goldens.
- Aggregate `Count` = row count: pinned by
  `tests/unit/test_aggregate_core.py::test_count_uses_len_and_aliases_the_field`.
- Running Total replaces an existing `RunTot_<col>`: pinned by
  `tests/unit/test_running_total_core.py:54-58`.
- Window's duplicate order-by keys: harmless (probe produced the expected lag).
- `cum_mean` with `nulls="zero"`: treating null as zero is the option's
  meaning; results are consistent.
- Pivot `count`: uses `c.count()` (non-null) and matches its dock text.
- Fiscal-year labelling: consistent with "year in which the fiscal year ends".
- `qt/headless.py` `apply_test_hooks`: env-gated by design.
- Scheduled custom-code workflows are impossible today (`build_command` never
  passes `--allow-custom-code`), but no node currently sets
  `custom_code=True` (docs/guide/cli.md:245), so this is a latent gap rather
  than a live bug. Revisit when the first custom-code node ships.

---

## Suggested order

1. H1 (one-line fix, largest blast radius).
2. H2, H3, H4 (silent failures and data loss in report/join nodes).
3. M1 (engine panic), M2 (glob inputs), M6 (startup crash).
4. M3, M4, M5.
5. The Low list as cleanup, with regression tests for each High/Medium.

Every High and Medium finding needs a focused test: malformed headers, key
name collisions, duplicate mappings, null-valued measures, glob inputs, and a
lock acquired concurrently (a two-process test can use a barrier around the
window).
