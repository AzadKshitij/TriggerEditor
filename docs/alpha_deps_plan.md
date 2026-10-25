# Alpha dependency modernization — progress record

Branch `alpha/deps-modernization`, from `main` @ `8e557fc` (identical to
`origin/main` as of 2026-10-25). Plan: 10 phases (0–9), one commit per phase,
no push. Phases 1–5 (the measured upgrade) execute first; phases 6–9 follow.

## Machine + session state (every comparison must match this)

| | |
|---|---|
| Date | 2026-10-25 (all Phase 0 runs, same session) |
| CPU | AMD Ryzen 5 3500U (4c/8t, 2.1 GHz base) — budget laptop |
| RAM | 9.9 GB |
| OS | Windows 11 x64 |
| Python (pre) | 3.13.12 (uv managed); 3.14.8 installed via uv 0.13.4, ready for Phase 1 |
| uv | 0.13.4 (7456b60bc 2026-10-20) |
| Other load | OpenChamber + this session running; no other heavy process during measurement |

## Noise band (the number that gates every later claim)

`docs/PERFORMANCE_PROFILING_FINDINGS.md` warns ±10–25%. Measured today with a
same-tree, same-session baseline+after pair (5 runs each, fixed path-remap
harness — see below):

| workflow | baseline avg | after avg | same-tree speedup |
|---|---|---|---|
| small_2node | 0.006 s | 0.006 s | 1.00x |
| medium_14node | 0.059 s | 0.056 s | 1.06x |
| large_105node | 5.201 s | 4.868 s | 1.07x |

**Rule adopted:** post-upgrade deltas below ~7% on `large_105node`, ~10% on
`medium_14node`, or any delta on sub-10 ms workloads are reported as
*within noise*, never as wins. Per-run spread on `small_2node` (0.004–0.011 s)
is timer-dominated; only its mean-to-mean is meaningful.

Pre-upgrade artefacts (all committed):
`scripts/benchmark_results/pre_deps_baseline.json`, `pre_deps_after.json`,
`canvas_deps_baseline_20261025_193404.json`.

Canvas key medians (120 nodes, 119 edges, repeats=3, defaults):
zoomed-out pan 35.15 ms/step, viewport repaint 42.18 ms, node drag 14.16 ms/
step; full table in the JSON. Post-upgrade canvas run must use the identical
command and be compared with
`benchmark_canvas_perf.py --compare <pre> <post>`.

## Phase 0 — Baseline — DONE 2026-10-25

1. Tree synced: `alpha/deps-modernization` reset --hard to `origin/main`;
   uncommitted app-resave churn in `savedfiles/*.tds` discarded (approved).
2. **Measurement fix (committed `c09c635`):** the committed sample workflows
   bake the authoring machine's absolute paths
   (`C:/Users/KASHVINCHANDRASAN/...`, `docs/bugs.md` documents 16 files).
   Before this fix the benchmark measured **failures**: `large_105node` ran
   29 nodes in 0.08 s (File Inputs gave up after 5 retries → "no incoming
   data"), and `small_2node`'s 1.01 s `last_execution_time` was the retry
   sleep against a missing `check.csv`. Harness now localizes paths in a
   scratch copy (foreign repo-root rewrite + repo-root basename→`data/`
   fallback, same idea as `tests/support/corpus.py`); saved workflows are
   never touched. Verified: 105/105 nodes, 4.9–5.5 s, +667 MB first-run RSS.
3. Workflow pair + `--compare` captured (numbers above).
4. Canvas `--label deps_baseline` captured (defaults; JSON committed).
5. This doc committed.

Session profile (`profile_app.py`, plan Phase 0 step 3) is **deferred**: it
needs an interactive app close (or the Phase 8 `--profile-seconds` flag that
does not exist yet); cProfile data across the upgrade without an automated
diff is noise we do not need twice. Phase 8 captures profile evidence
properly, before and after, with the self-exit flag.

## Phase 1 — Python 3.14 — DONE 2026-10-25

- Interpreter: 3.14.8 (uv-managed); `.python-version` pinned locally
  (gitignored by design). `requires-python >=3.14,<3.15`, ruff
  `target-version = "py314"`, ty `python-version = "3.14"`; README badge +
  Requirements line updated.
- **Qt trio pulled forward from Phase 5** (sanctioned exception): `pyqt6-sip`
  13.9.1 has no cp314 wheel and its source build needs MSVC (absent), so
  3.14 forces pyqt6 6.11.0 / pyqt6-qt6 6.11.2 / pyqt6-sip 13.13.0
  (cp314/abi3 wheels).
- `datetime.utcnow()` → `datetime.now(UTC)` in `performance_scene.py`.
  PEP 758: `ruff format` under `py314` drops parens on multi-exception
  `except` — valid 3.14 syntax, accepted deliberately.
- Gate discovery: the `ui` layer crashed (0xC0000409) + 3 hard failures in
  `test_formula_editor_loop.py`. Isolated by per-layer bisect, reproduced
  standalone, and attributed with version probes: `mergeCharFormat` and
  `QSyntaxHighlighter.setFormat` fire `textChanged` **identically on Qt
  6.8.1 and 6.11.0** — a pre-existing repo bug (`78d438d` moved error
  painting to `setExtraSelections` but left the old whole-document format
  write in place; the write fired `textChanged`, the handler wiped
  `self.errors` mid-paint, highlights never appeared). Fixed in its own
  commit `8b3c40a`, not counted against the bump.
- Gates: `uv sync` clean; all core imports OK; offscreen `TriggerSubWindow`
  constructs; full pytest **803 passed / 6 skipped** (benchmarks skip as
  designed); `scripts\build.bat` OK (`TriggerEditor.exe`, 13.3 MB); dist exe
  launched — window "Trigger Designer" alive at 15 s (WS 172 MB), stopped
  after smoke.
- Commits: `8b3c40a` (bugfix), `2738e97` (Phase 1 deps).

## Phase 2 — Unused runtime deps — DONE 2026-10-25

- Dropped from `[project].dependencies`: `click`, `colorama`, `packaging`,
  `python-dateutil`, `typing-extensions`, `tzdata` — zero imports repo-wide
  (recursive ripgrep; an earlier non-recursive `Select-String -Path src\*`
  check was meaningless, re-verified). They stay in the lock as transitive
  deps of dev tooling (typer→click, pandas→dateutil/tzdata, pytest→
  packaging); nothing in `src/` can reach those paths.
- `typing-extensions` removal: `main_window.py` now takes `override` from
  stdlib `typing` (3.12+).
- `tzdata` pre-check: duckdb `TIMESTAMPTZ` round-trip runs on the **bundled
  ICU extension** (`duckdb_extensions() → icu loaded=True`); the tzinfo it
  returns (`DstTzInfo`) is duckdb-native, not Python `zoneinfo`; repo has
  zero `zoneinfo` imports. Safe to drop on Windows.
- Gate: full pytest 803 passed / 6 skipped.
  Gotcha recorded for later phases: **bare `uv sync` prunes the `profiling`
  group** — the project convention is `uv sync --all-groups`.

## Phase 3 — Dev deps cleanup (pandas→polars etc.) — DONE 2026-10-25

- dev group: dropped `pandas`, `pandas-stubs`, `autotyping`, `faker`,
  `pkgsizer`, `pytest-xdist`. `uv sync` cascaded out `typer`/`rich`/`pytz`/
  `tzdata`/`mdurl`/`shellingham` with them (they were all reached only via
  `pkgsizer→typer` and `pandas→pytz/tzdata`) — the venv shrank accordingly.
- `tests/unit/test_preview_sampling.py`: the pandas-branch test now builds a
  stub class named `DataFrame` with `__module__ = "pandas.core.frame"` (what
  `_is_pandas_dataframe` actually inspects — no pandas import involved) and
  monkeypatches `pl.from_pandas`, so the conversion branch and the row cap
  stay pinned without pandas installed.
- `scripts/Compare.py`: dropped `import pandas`/`numpy`/`pathlib`, the
  `test_pandas_read()` block (incl. its commented-out chunked/dtype variants)
  and its call in `main()`. It still measures polars vs the stdlib `csv`
  module. Ruff findings went 18 → 14 (the four in the deleted pandas block
  left with it); the remaining ones (F541/BLE001/E722/S110) and ty's
  `dask.dataframe` unresolved-import are pre-existing patterns in the
  untouched helpers, verified by re-running both tools on `git show HEAD`
  of the same path.
- Deleted `scripts/check_output_pandas.py` (generated scratch: one workflow's
  pandas code export) and `scripts/autotype.bat` (wrapper around the removed
  `autotyping`). The polars equivalent, `scripts/check_output_polars.py`,
  stays.
- The app's *defensive* pandas duck-typing (`core/charts.py`,
  `qt/models/preview_sampling.py`) is untouched by design: a user's custom
  node may hand the preview a pandas frame from their own environment. The
  pyproject comment block records this and the `uv add --dev pandas` escape
  hatch for the `savedfiles/` reference pipelines.
- Gate: full pytest 803 passed / 6 skipped; ruff format no-ops on touched
  files.

## Phase 4 — Clean-clone install + nodeeditor 0.8.2 — DONE 2026-10-25

- `nodeeditor-qtpy` 0.8.1 → 0.8.2 (pure-Python patch). The self-tracking
  pin gate (`test_installed_nodeeditor_matches_the_pinned_version`) re-reads
  the pin and passed; all 10 nodeeditor API tests green.
- **Clean-venv proof (the stranger test):** fresh venv under
  `%TEMP%\opencode\clean_alpha_env` built by `uv venv --python 3.14` +
  `UV_PROJECT_ENVIRONMENT=<venv> uv sync --all-groups` against the lockfile
  — no manual installs. Result: python 3.14.8 / Qt 6.11.0 / nodeeditor 0.8.2;
  **full suite 803 passed / 6 skipped on that interpreter**, which includes
  the e2e layer that launches the real app, loads checked-in workflows and
  runs them. (Gotcha: plain `VIRTUAL_ENV` is ignored by `uv sync` — it wants
  `UV_PROJECT_ENVIRONMENT` or `--active`.)
- `scripts/build.bat` header already states the lock-managed truth — no
  change. `scripts/sync-nodeeditor.ps1`: the "uv sync prunes nodeeditor if
  it is missing from the lock" comment was stale pre-pinning language;
  replaced with why the `--no-deps` local-checkout branch exists at all
  (0.8 floors qtpy/orjson are already locked; the branch is a pre-release
  dev convenience only).
- Gates: ps1 parses with 0 errors; full pytest 803 passed.

## Phase 5 — Remaining bumps + duckdb cap + version 0.1.0 — DONE 2026-10-25

- Runtime: `pyarrow` 25.0.1 → **26.0.0** (re-pinned, silent-jump rationale
  kept in the comment), `numpy` → **2.5.4**, `duckdb` `>=1.2.1` →
  **`>=1.5.6,<2`** (floor up, ceiling added — 2.0 gets its own Phase 6),
  `sqlglot` floor → **30.24**, `pillow` → **13.0.0**, `orjson` → **3.13.0**;
  floors aligned to the (already-current) lock: `fastexcel>=0.21.0`,
  `openpyxl>=3.1.5`, `psutil>=7.2.2`. `polars` stays 1.44.2 for Phase 6.
  All 22 installed versions verified via `uv pip list`.
- Tooling: `ruff` → **0.17.2**, `ty` → **0.0.91**, `pre-commit` → **4.7.0**.
- `pyproject version` 0.0.1 → **0.1.0**, now matching `core/constants.py`
  (`VERSION = "0.1.0"`) and the Inno Setup `MyAppVersion` — what a stranger's
  `pip show` reports.
- Gate: `uv lock`/`uv sync --all-groups` clean; full pytest **803 passed /
  6 skipped** on the bumped stack.
- Recorded, deliberately deferred: repo-wide `ruff format --check` under
  0.17 wants 20 files touched and `ruff check` counts 933 fixable findings —
  pre-existing debt the per-file pre-commit flow normalizes lazily; a
  drive-by sweep would pollute every later phase's diff. Batch cleanup is a
  Phase 9 candidate.

## Post-upgrade measurement — pending

(Sections above get their numbers filled in as each phase lands.)
