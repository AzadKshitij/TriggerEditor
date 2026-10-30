# Developer documentation

For contributors, and for cheaper coding agents that must extend Trigger
Designer safely. Everything here was checked against the code on branch
`feature` (see "Verified against" at the end). Where an older document disagrees
with the code, the code wins and the page says so.

Read order for a new contributor: this page, `architecture.md`,
`conventions.md`, then the page for your task.

## Index

| Page | Read it when |
|---|---|
| [architecture.md](architecture.md) | You need the layers, live evaluation versus Run, LazyFrame rules, the generated-code contract, `.tds` persistence, the module map, and the corrections to the old codebase brief. |
| [adding-a-node.md](adding-a-node.md) | You add or change a node (shaping, audit or hand-written). Includes a compiled, tested example. |
| [run-pipeline.md](run-pipeline.md) | You touch Run, cancel, the executor, the run script or anything the audit recorder hooks into. |
| [audit-trail-internals.md](audit-trail-internals.md) | You touch run records: schema, hashing, the store and its lock, the recorder, counting, the Run History dock. |
| [error-system.md](error-system.md) | You add an error code, translator rule or error UI. |
| [security-model.md](security-model.md) | You touch SQL, generated code, file access or exports. |
| [testing.md](testing.md) | You write or fix tests, update a golden, or need the baselines. |
| [conventions.md](conventions.md) | You write UI, undo code, or commit. |
| `cli-internals.md` | *To be added* (command line: parser, exit codes, headless runner, approvals, code policy). |
| `workpaper-internals.md` | *To be added* (workpaper writer and the shared Excel engine in `core/excel`). |

Related, not owned here: `../CHANGELOG.md` (what changed on this branch and what
may break saved workflows), `../NODE_REFERENCE.md`, `../guide/` (user guide),
`../bugs.md` (bug register with `BUG-nnn` ids), `../DESIGN_SYSTEM.md`,
`../plan/` (the feature plans; `00-codebase-brief.md` is partly stale, see
`architecture.md` section 9), and the root `AGENTS.md`.

## Repo map

```
AGENTS.md  CONTRIBUTING.md(stale in places)  README.md  pyproject.toml  uv.lock  trigger.spec
src/trigger_designer/
  main.py                 GUI entry (configures loguru at import: a CLI must not import it)
  cli_entry.py, cli/      command line entry and commands (in progress)
  core/                   Qt-free logic (see architecture.md section 2)
    node_configuration.py   enums, registries, lazy loading, op ids, v1 migration
    shaping/                one Qt-free module per shaping node + common.py
    audit/                  audit tests + run-record machinery
    errors/                 NodeError, catalogue, translator, enrichment
    ExecutionCheck/         executor.py, run_loop.py
    excel/, headless/       Excel engine, CLI foundations (in progress)
    sql_guard.py  codegen_safe.py  inputs.py  input_source.py  profile*.py  frames.py ...
  qt/                     GUI
    node_base.py  design_window.py  main_window.py  performance_scene.py
    helpers/                mixins and support (execution, evaluation, undo, shaping_support, audit_bridge ...)
    docks/                  Config Dock, Data Preview, Logging, Problems, Run History, palette
    widgets/common/         shared Config Dock widgets
    widgets/nodes/<Family>/ the nodes: InOut Preparation Join Transform Report Audit
    undo/                   QUndoStack wrapper, commands, bindings
    resources.json          icon ids -> files
  resources/qt/themes/      theme token JSON + base.qss (format template)
  resources/qt/images/node_icons/<Family>/*.svg
  qss/                    _style.scss (keep in step with base.qss)
tests/                    unit/ ui/ e2e/ benchmarks/ manual/ support/   (integration/ is empty)
docs/                     user guide (guide/), plans (plan/), reference docs, dev/ (this folder)
scripts/                  build/profile/benchmark helpers, gen_changelog_stub.py
savedfiles/  data/        sample workflows and CSVs used by e2e tests (tracked; do not let a run rewrite them)
examples/ plans/ profiles/ output/ build/ dist/ logs/     scratch, artefacts or old material; ignore
```

Node families and counts today: IO 2 registered (File Input, File Output),
Preparation 16, Join 5, Transform 7, Report 3, Audit 5. The authoritative lists
are the enums in `core/node_configuration.py` and `_LAZY_NODE_SPECS` in
`qt/widgets/nodes/__init__.py`.

## Environment

| Item | Value (verified) |
|---|---|
| OS | Windows 11 (Git Bash and PowerShell both used; forward slashes work in Bash) |
| Python | `>=3.14.0,<3.15` (`.python-version` 3.14); the venv `.venv` is 3.14.8 |
| GUI | PySide6-Essentials 6.12.0 through `qtpy` 2.4.3 (never import PySide6/PyQt6 directly); canvas `nodeeditor-qtpy` 0.8.2 from PyPI |
| Data | polars 2.0.0 (`[pyarrow]`), pyarrow 26.0.0, duckdb 2.0.0, sqlglot 30.24, fastexcel, openpyxl, xlsxwriter 3.3.0, orjson 3.13.0, numpy 2.5.4 |
| Dev | ruff 0.17.2, ty 0.0.91, pytest 9.1.1, pytest-qt 4.5.0, pytest-timeout 2.4.0, pre-commit, pyinstaller, radon (user's uncommitted `pyproject.toml` edit adds it); no pytest-xdist |
| uv | 0.13.4 (`[tool.uv] package = true`, hatchling build, editable install; scripts `trigger-designer` and `trigger-designer-cli`) |

`pyarrow` is not optional: DuckDB registers Polars frames through Arrow. The old
caution "do not run `uv sync`, it prunes `nodeeditor`" is obsolete (the canvas
is a normal locked dependency now), but the safest habit when several people or
agents share a tree is still to call the venv interpreter directly and not
resync.

### Commands

```powershell
# run the app
.venv\Scripts\python.exe src\trigger_designer\main.py ["path\to\workflow.tds"]
uv run --project . trigger-designer                  # console script
.\run.bat                                            # uv run ... main.py (self/comp args point at one machine's paths)

# format, lint, type-check (only on the files you touched)
.venv\Scripts\python.exe -m ruff format <files>
.venv\Scripts\python.exe -m ruff check <files>
.venv\Scripts\python.exe -m ty check --no-progress src scripts

# tests: name a layer or a file; never bare pytest
.venv\Scripts\python.exe -m pytest tests\unit -q
.venv\Scripts\python.exe -m pytest tests\e2e -q
.venv\Scripts\python.exe -m pytest tests\ui -q
.venv\Scripts\python.exe -m pytest tests\benchmarks --run-benchmarks -s

# regenerate the changelog stub
.venv\Scripts\python.exe scripts\gen_changelog_stub.py
```

Environment variables: `QT_QPA_PLATFORM=offscreen` (headless Qt; the test
suite sets it), `TRIGGER_DESIGNER_DATA_DIR` (preferences, themes, run script,
fallback run store; tests point it at a temp dir), `TRIGGER_DESIGNER_STATE_DIR`
(CLI state), `TRIGGER_UPDATE_E2E_GOLDENS=1` (rewrite goldens, see `testing.md`),
`TRIGGER_DISABLE_DATA_WARMUP=1` (skip the Arrow warm-up thread),
`PYTHONIOENCODING=utf-8` (when piping: the app logs emoji; PowerShell `>` writes
UTF-16 and breaks JSON reads).

Application data (preferences INI, themes, `last_run/check_output.py`, fallback
run records, logs): `%APPDATA%\Trigger Designer` (`app_data_dir()`), or
`TRIGGER_DESIGNER_DATA_DIR`.

### Test baselines

Measured on a clean checkout of `e2b610a` on 2026-10-30 (details, failures and
timings in `testing.md`; other people were committing concurrently, so treat the
numbers as a snapshot and re-measure before quoting):

| Layer | Result |
|---|---|
| `tests/unit` | 2233 passed, 4 skipped, 1 xpassed |
| `tests/e2e` | 102 passed, 1 failed (stale Split golden, regenerated in `c3035e5`) |
| `tests/ui` | 974 passed, 5 failed (the no-`print` guard against the in-progress CLI modules) |

Code-quality baseline at the same commit: `ruff check src tests scripts` reports
562 errors (436 auto-fixable) and `ruff format --check` would reformat 20 files.
The repo is not lint-clean, so run ruff on your files and compare before/after.

## Working rules in a shared tree

Several people and agents commit to this branch concurrently.

* Commit with an explicit pathspec: `git add -- <paths>` then `git commit -m
  "..." -- <paths>`; retry on `index.lock`. No `git add -A`, `commit -a`, `stash`,
  `reset`, no push unless asked, no `Co-Authored-By` trailer in this repo.
* Do not touch files you do not own, and leave the user's uncommitted edits
  alone (at the time of writing: `check_output.py`, `pyproject.toml`, `uv.lock`,
  `savedfiles/Example_2_Retail_Ledger/app_workflow/1.tds`, `docs/assets/icon_proposals/`).
* For a stable test baseline use a detached worktree
  (`git worktree add --detach <dir> HEAD`, run pytest there, remove it) instead of
  racing other people's edits.
* Full rules: `conventions.md`.

## Verified against

Written on 2026-10-30. Code reading and the compiled example were verified at
`e2b610a` plus later commits; each page names the module and symbol rather than a
line number so it stays checkable as the tree moves. If a page and the code
disagree, fix the page in the same change that fixed the code.
