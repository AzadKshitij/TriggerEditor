# 00 - Codebase Brief (shared source of truth for plans 01-08)

Audience: authors of the eight feature plans and the (cheaper) models that execute them.
Everything below was verified by opening the file or running the command on
2026-10-21 against `main` @ `71b4041` (working tree had unrelated local edits: `check_output.py`,
`pyproject.toml`, `main.py`, `uv.lock`, untracked `src/trigger_designer/__main__.py`; none were touched).
Paths are relative to the repo root. `file.py:N` = line in the current tree.
Where a doc disagrees with the code, the code is described and the doc is flagged **[STALE DOC]** or **[SURPRISE]**.

## Table of contents

1. [Repo map](#1-repo-map)
2. [Environment and commands](#2-environment-and-commands)
3. [Anatomy of a node, end to end (+ ADD A NEW NODE RECIPE)](#3-anatomy-of-a-node-end-to-end)
4. [Evaluation architecture](#4-evaluation-architecture)
5. [Config Dock and UI conventions](#5-config-dock-and-ui-conventions)
6. [Undo/redo contract](#6-undoredo-contract)
7. [Data I/O](#7-data-io)
8. [Errors today](#8-errors-today)
9. [Testing guide](#9-testing-guide)
10. [Cross-cutting design guidance and technical debt](#10-cross-cutting-design-guidance)
11. [Dependency/ordering map and shared interfaces](#11-dependencyordering-map-between-the-eight-features)
12. [Glossary](#12-glossary)

### Ten facts that change plans (read first)

1. **Excel export is broken in this environment.** `FileOutput` "excel" and the Data Preview export call `DataFrame.write_excel`, which needs `xlsxwriter`. It is **not installed and not declared** in `pyproject.toml`/`uv.lock` (verified: `ModuleNotFoundError: Excel export requires 'xlsxwriter'`). Plan 06 (workpaper) must add it as a declared dependency (or use `openpyxl`, which is installed, 3.1.5) and justify it.
2. **Run Workflow does no data work unless the graph has a sink.** Generated code builds Polars `LazyFrame` plans. Nothing is collected by the executor. Only File Output (`sink_*`/`collect().write_*`), Graph and Count (`collect`) materialise data. A broken lazy plan with no sink "succeeds" in Run. Audit-test nodes (04) and profile nodes (05) that must surface failures during Run must collect/sink inside their own `get_code()`.
3. **Run executes generated code from live state.** `get_code()` reads `content.incoming_variable`, `content.incom_data`, etc., which are set only by the *live* `processInputs()` pass. Run does not re-evaluate the graph first. A node that was never live-evaluated emits its fallback code (empty `pl.DataFrame()`).
4. **Cancellation is not wired.** `WorkflowWorker.request_cancel()` and `NodeExecutor.cancel_execution()` have no callers; `_cancel_event` is set but never read by the exec thread. There is no Cancel button.
5. **Errors are flattened to strings.** `NodeExecutor.execute_node` catches everything and keeps only `str(exception)` (+ traceback text for wrapped errors). The exception object/type is lost before the GUI sees it (`executor.py:378-388`). Live errors become canvas tooltips via `str(e)` (`node_base.py:892-900`).
6. **`getPyFile` writes `check_output.py` into the *current working directory* after every Run** (`design_window.py:698-706`). That file is tracked by git (despite `.gitignore:295`) so every Run dirties the working tree. Tests stub it out (`no_modal_dialogs`).
7. **Full `pytest` run aborts in this environment** (see 2.4): the installed `qtpy-nodeeditor` (git `ee5e8fd`) lacks canvas commits the repo needs. Run the layers separately: unit 334 pass / e2e 20 pass / ui 404 pass + 20 fail + 7 error (all pre-existing).
8. **Docs are partly stale.** `docs/SESSION_HANDOFF.md`, `docs/NODE_REFERENCE.md`, `docs/ENHANCED_EXECUTOR_GUIDE.md`, `CONTRIBUTING.md` contradict the code in places (list in 10.4).
9. **Absolute paths are stored in `.tds`** for File Input/Output (`filePath`), and the File Input also stores `schema_snapshot`/`file_metadata` captured by *re-reading the file at save time*.
10. **`exec()` of generated code has no sandbox** and shares one namespace across nodes (`executor.py:264`). Names must be globally unique (`var_<kind>_<node id>`).

---

## 1. Repo map

### 1.1 Top level

| Path | Role |
|---|---|
| `AGENTS.md` | Binding rules for agents (summarised in 1.4). |
| `pyproject.toml`, `uv.lock` | Deps (Python `>=3.13.12,<3.14`), ruff/pytest/briefcase config. **Do not run bare `uv sync`** (see 2.2). |
| `src/trigger_designer/` | The application package (1.2). |
| `tests/` | `unit/ ui/ e2e/ benchmarks/ manual/ support/`; `integration/` is an empty dir (only `__pycache__`; **[STALE DOC]** `CONTRIBUTING.md` says it holds tests). |
| `docs/` | Design system, node reference, logging/preview READMEs, perf reports. Several stale (10.4). `docs/plan/` = this folder. |
| `savedfiles/` | Sample `.tds`/`.json` workflows + sample CSVs used by e2e tests (`savedfiles/0. All Node- Test.tds`, `1. out_check.csv`, ...). Tracked. |
| `data/` | Sample CSVs (`check.csv`, `check_1.csv`, `test_customers.csv`, ...) used by e2e tests; also `Test_*.tds` workflows. |
| `scripts/` | `build.bat` (PyInstaller + nodeeditor install), `sync-nodeeditor.ps1`, profiling/benchmark scripts, `dev_watch.py`. |
| `run.bat`, `scripts/run.bat` | `uv run --project . src\trigger_designer\main.py [file]`; `self`/`comp` args point at hard-coded machine paths. |
| `check_output.py` | Generated by every Run (CWD); tracked in git by accident. |
| `logs/` | Dev-mode loguru log files, one per launch (`trigger_designer_<timestamp>.log`). Untracked. |
| `build/ dist/ profiles/ output/ examples/` | Build artefacts / profiler dumps / scratch. Ignore. |
| `trigger.spec` | PyInstaller spec. New data files (icons, json) may need adding. |

### 1.2 `src/trigger_designer/`

| Path | Role (one line) |
|---|---|
| `main.py` | App entry. **Importing it configures loguru + tees stdout/stderr at import time** (`main.py:149`). A CLI must not import it. |
| `__main__.py` | `from trigger_designer.main import main; main()` (untracked, new). `python -m trigger_designer` launches the GUI. |
| `core/node_configuration.py` | Node enums, registries, lazy loading, op-id resolution, v1 migration (section 3). |
| `core/ExecutionCheck/executor.py` | `NodeExecutor`, `ExecutionResult`, `SecurityConfig` - exec() of generated code with timeout (section 4). **Not Qt-free**: imports `qt.helpers.global_logger`. |
| `core/constants.py` | `VERSION = "0.1.0"`, `WORKFLOW_SCHEMA_VERSION = 2`, `FOLDER_NAME`. |
| `core/charts.py`, `core/utils/dtype_utils.py`, `core/utils/cleansing_util.py` | Qt-free helpers (chart spec, dtype widening map, cleansing engine). The right home for new Qt-free logic. |
| `core/warmup.py` | DuckDB/Polars Arrow warm-up on a thread at startup. |
| `core/singleton.py` | Thread-safe `Singleton` metaclass (unused by most code). |
| `qt/node_base.py` | **Most important file.** `TriggerNode`, `TriggerContent`, `TriggerChangeHandler`, `TriggerGraphicsNode`, `frame_schema()`, `frame_shape()`, `upstream_rename_map()`. |
| `qt/design_window.py` | `TriggerSubWindow` (one per open workflow): load/save, `doEvalOutputs`, `run_workflow`, `topologicalSort`, `getPyFile`, logging helpers. |
| `qt/main_window.py` | `TriggerWindow` (QMainWindow): MDI area, docks, file open/save, recents, session restore. |
| `qt/performance_scene.py` | `TriggerScene` (adds `workflow_metadata` on save, bulk-load flag, node-evaluated listeners), `TriggerEdge`. |
| `qt/helpers/workflow_execution_mixin.py` | Run Workflow orchestration (`executeWorkflow`, result storage, pens, stats). |
| `qt/helpers/workflow_worker.py` | `WorkflowWorker(QThread)` that loops nodes through the executor. |
| `qt/helpers/eval_progress.py` | Modal progress dialog used during file **load** (not Run). |
| `qt/helpers/content_undo_mixin.py` | `TriggerContentUndoMixin` (`push_property_change`, `push_list_change`, `sync_from_model`). |
| `qt/helpers/state_mixin.py` | `SerializableContentMixin` (schema-driven serialize/deserialize). |
| `qt/helpers/global_logger.py` | `global_logger.info(...)` -> active design window -> Logging dock. |
| `qt/helpers/recent_files.py` | `RecentFilesManager` (list in `preferences.ini`). |
| `qt/helpers/main_window_ui_mixin.py` | Menus (`MainWindowMenuMixin`) and docks (`MainWindowDockMixin`: `createXxxDock`, `switchXxxDock`). |
| `qt/helpers/main_window_actions_mixin.py` | `createActions` (Settings, layout, window actions, About). |
| `qt/helpers/context_menu_mixin.py` | Canvas right-click / Shift+A node menu; reads `NODE_REGISTRIES`. |
| `qt/helpers/dock_chrome.py`, `win_caption.py` | Tab-only dock chrome; frameless window caption. |
| `qt/helpers/file_opener.py` | **Dead code** vendored from TagStudio: imports `structlog` and `tagstudio.*` (not installed); nothing imports it (grep). Do not use. (Someone else was editing it while this brief was written.) |
| `qt/docks/node_config.py` | `ConfigDock` - the node editor panel (section 5). |
| `qt/docks/data_preview.py` | `DataPreviewDock` - shared preview of selected node output (follows scene hooks). |
| `qt/docks/logging_dock.py` | `LoggingDock` - in-memory per-window log view (max 1000 entries/window). |
| `qt/docks/nodes_list.py` | `NodesDock` - palette tabs (one `QTRDragListbox` per `NodeTypes`). |
| `qt/widgets/common/config_widgets.py` | Shared Config Dock widgets (`IconButton`, `TextButton`, `ConfigSection`, `FormRow`, `ColumnChecklist`, ...). |
| `qt/widgets/nodes/__init__.py` | **Node module registry** `_LAZY_NODE_SPECS` + import sweep (section 3). |
| `qt/widgets/nodes/InOut/` | `file_input.py` (941 lines), `file_output.py` (438). |
| `qt/widgets/nodes/Join/` | `join.py` (1551), `Append.py`, `union.py` (956, **implemented**), `find_replace.py` (0 bytes). |
| `qt/widgets/nodes/Preparation/` | `cleansing, dynamic_row_builder ("Rows"), filter, formula, groupby ("Aggregate"), normalize_columns, select, sort, split, unique`. |
| `qt/widgets/nodes/Transform/` | `count_records ("Count"), running_total, transpose`. |
| `qt/widgets/nodes/Report/` | `graph.py` (+ helpers `chart_view.py`, `chart_window.py`, excluded from the sweep). |
| `qt/widgets/nodes/Documentation/comment.py` | 0 bytes. |
| `qt/widgets/nodes/unknown.py` | `TriggerNode_Unknown` placeholder for unresolvable ops (never registered). |
| `qt/widgets/sql_formula_editor.py`, `select_table_widget.py`, `data_preview_panel.py`, `node_drag_listbox.py`, `node_searchable_menu.py` | Big shared widgets (formula editor w/ completer; Select table + `ComboBoxDelegate`; preview strip + table; palette; Shift+A menu). |
| `qt/models/` | `polars_table_viewer.py` (table model/view), `preview_sampling.py` (Qt-free bounded collect), `preview_worker.py`. `settings_panel.py`, `model_file_dialogue.py` (and `model_pandas.py`, which a concurrent edit was deleting) are tiny legacy. |
| `qt/undo/` | `controller.py` (QUndoStack wrapper), `commands.py`, `binding.py`, `protocol.py`, `history.py` (section 6). |
| `qt/preferences.py` | `Preferences` INI store (section 7). `layout_state.py` persists window/dock layout. |
| `qt/theme_manager.py`, `theme_icons.py`, `node_editor_colors.py`, `render_settings.py` | Theming and canvas settings. |
| `qt/resource_manager.py` + `qt/resources.json` | Icon/id lookup (`ResourceManager().get("node_split")` -> `QPixmap`). |
| `qt/dialogs/` | Preferences, About, Welcome, Theme editor. |
| `qt/tr_qt.py`, `qt/translations.py` | 0 bytes. |
| `qt/darkstyle_rc.py` (11k lines) | Compiled Qt resources - never hand-edit. |
| `resources/qt/themes/*.json`, `base.qss` | 12 theme token files + the QSS `str.format` template. |
| `resources/qt/images/node_icons/` | SVG/PNG node + UI icons (`ui/` subfolder = monochrome glyphs re-coloured per theme). |
| `qss/` | Legacy SCSS/QSS sources (`_style.scss` must stay in step with `base.qss`). |

### 1.3 The 20 files a feature author will touch most

| # | File | Why |
|---|---|---|
| 1 | `src/trigger_designer/core/node_configuration.py` | Add enum member (new node) |
| 2 | `src/trigger_designer/qt/widgets/nodes/__init__.py` | Add `_LAZY_NODE_SPECS` entry |
| 3 | `src/trigger_designer/qt/widgets/nodes/<Family>/<new>.py` | The node |
| 4 | `src/trigger_designer/qt/resources.json` (+ SVG in `resources/qt/images/node_icons/`) | Node icon id |
| 5 | `src/trigger_designer/qt/resources.json` (+ the SVG) | Menu icon (resolved by `ResourceManager`; nothing to compile) |
| 6 | `src/trigger_designer/qt/node_base.py` | Base classes, `frame_schema`, eval flow, error tooltips |
| 7 | `src/trigger_designer/core/ExecutionCheck/executor.py` | `ExecutionResult`, exec, error capture |
| 8 | `src/trigger_designer/qt/helpers/workflow_execution_mixin.py` | Run orchestration; hook for run recording |
| 9 | `src/trigger_designer/qt/helpers/workflow_worker.py` | Per-node signals |
| 10 | `src/trigger_designer/qt/design_window.py` | Load/save/run entry points, `getPyFile` |
| 11 | `src/trigger_designer/qt/widgets/nodes/InOut/file_input.py` | Input types (01), resolved files |
| 12 | `src/trigger_designer/qt/widgets/nodes/InOut/file_output.py` | Export formats (06) |
| 13 | `src/trigger_designer/qt/widgets/common/config_widgets.py` | Shared dock widgets |
| 14 | `src/trigger_designer/qt/docks/node_config.py` | Dock lifecycle |
| 15 | `src/trigger_designer/qt/helpers/main_window_ui_mixin.py` | New docks/menu entries |
| 16 | `src/trigger_designer/qt/preferences.py` (+ `dialogs/preferences_dialog.py`) | New preference keys |
| 17 | `src/trigger_designer/qt/main_window.py` | Window wiring (`createMdiChild`) |
| 18 | `tests/conftest.py`, `tests/support/{workflows,corpus,frames}.py` | Test fixtures / e2e corpus |
| 19 | `pyproject.toml` | Dependencies (xlsxwriter!), CLI entry point |
| 20 | `src/trigger_designer/qt/widgets/nodes/Join/union.py` | Best **modern** example: multi-input, undo wired correctly |

### 1.4 AGENTS.md rules (binding; summarised)

* Config Dock UI follows `docs/DESIGN_SYSTEM.md` §§1-7; reference implementation `Preparation/select.py:134-259`.
* Reuse `qt/widgets/common/config_widgets.py`: `IconButton`, `TextButton`, `ConfigSection`, `ColumnChecklist`, `NoWheelComboBox`, `EmptyStateLabel`. **No per-node rewrites.**
* Icon-first: icon-only buttons; text only in dialogs and the paired `All`/`None` `TextButton`s. Mandatory tooltip + accessible name. **No `QIcon.fromTheme`** (blank on Windows) - use `IconButton.themed` with `:/qss_icons` fallback. **No inline `setStyleSheet`** - use `objectName` + `resources/qt/themes/base.qss` / `qss/_style.scss`.
* Hover/pressed must be restated per `objectName` (a `#objectName` selector outranks `QPushButton:hover`); use `{background_hover}`/`{background_pressed}`, never `{button_hover}`; keep a constant 1px base border.
* Layout tokens: main layout `spacing 2, margins 5`; toolbar `H40 margins 0`; controls `H30`; icon buttons `30x30 / 12px`.
* Live-by-default, ~300 ms debounce on text/search; history entries `"Noun Verbed"` and only on a real diff.
* Undo: model is the only truth; model->widget writes run inside `syncing(content)`; bindings check `is_syncing`; `ConfigDock.updateConfig(..., force=True)` after restore (do not remove); prefer `push_property_change` / `push_list_change` / `registerInputWidget`; fallback `history.storeHistory` (heavy); **do not add a new `history_stamp_callback`**; use `with self.history.restoring(is_undo=...)`; never let exceptions escape `undo()/redo()` (use `UndoableEdit._guard`); **do not implement `mergeWith`** (use `can_merge_with`/`absorb`). `_undo_composite = True` on widgets that emit their own change signal. Use `QScrollArea` (not `QAbstractScrollArea`) when traversing.
* Verify with: `ruff format <files>` then `ruff check <files>` then focused `pytest`.

**[SURPRISE]** AGENTS.md claims `registerInputWidget` "handles debounce, diffing and the restore guard". True, but the entry it records is a **whole-scene snapshot** (`bind(... write=None, path=None)` -> `history.storeHistory`, `binding.py:243-251`), not a fine-grained command. Only `push_property_change`/`push_list_change` give cheap commands. Also `split.py:345`, `filter.py` (mode), `unique/sort/...` still use the legacy `history_stamp_callback`/`storeHistory` despite the "do not add new" rule.

---

## 2. Environment and commands

### 2.1 Versions (verified with `.venv\Scripts\python`)

| Package | Version | Notes |
|---|---|---|
| Python | 3.13.12 (MSC v.1944, 64-bit) | venv at `.venv/`, base interpreter from scoop |
| polars | 1.44.2 | pinned |
| duckdb | 1.5.5 | formula/filter SQL engine (needs `pyarrow` to register Polars frames) |
| pyarrow | 25.0.1 | pinned |
| numpy | 2.5.3 | |
| openpyxl | 3.1.5 | installed (declared `>=3.1.0`) |
| fastexcel | 0.21.0 | Excel *reading* (File Input) |
| **xlsxwriter** | **MISSING** | needed by `DataFrame.write_excel`; undeclared |
| PyQt6 / PyQt6-Qt6 / qtpy | 6.8.0 / 6.8.1 / 2.4.2 | pinned |
| qtpy-nodeeditor | 0.7 (git `ee5e8fd`, author's fork) | **older than the repo expects** (2.4) |
| loguru | 0.7.3 | |
| orjson | 3.12.0 | `.tds` read/write |
| sqlglot | 30.20.0 | formula diagnostics |
| matplotlib / pillow / psutil / click | 3.11.2 / 12.3.0 / 7.2.2 / 8.5.0 | `click` is declared but **unused** by the app today (good CLI candidate) |
| pytest / pytest-qt / pytest-timeout / pytest-xdist | 9.1.1 / 4.5.0 / 2.4.0 / 3.8.0 | |
| ruff | 0.16.9 | `line-length = 88`, `target py313` |
| pandas | 2.3.3 | dev-only (preview tests) |
| uv | 0.6.6 | |
| not installed | sqlparse, jinja2, reportlab, fpdf2, python-docx, tabulate, structlog | any plan needing these must add and justify a dependency |

### 2.2 Run the app

```powershell
# from repo root (Windows, PowerShell)
uv run --no-sync --project . python -m trigger_designer            # GUI (via __main__.py)
uv run --no-sync --project . python src\trigger_designer\main.py "savedfiles\0. All Node- Test.tds"   # what run.bat does (without sync)
.\run.bat                                                           # uv run --project . src\trigger_designer\main.py
.venv\Scripts\python.exe -m trigger_designer                        # no uv at all
```

* **Caution (from `pyproject.toml:14-20`, not re-verified by running):** `qtpy-nodeeditor` is installed from git with `--no-deps` and is kept **out of `uv.lock`**; a plain `uv sync` / `uv run --project .` (which syncs) may prune it and break the GUI. `uv run --no-sync` works (verified: `uv run --no-sync --project . python -c "import nodeeditor, polars"` OK). Safest: call `.venv\Scripts\python.exe -m ...` directly. Re-install with `scripts\build.bat` / `scripts\sync-nodeeditor.ps1` (both reference `C:\Projects\qtpy-nodeeditor`, the author's machine).
* `main()` sets `QT_QPA_PLATFORM` nowhere; headless runs need `$env:QT_QPA_PLATFORM="offscreen"`.
* Logging to console prints emoji; when piping on Windows set `$env:PYTHONIOENCODING="utf-8"` (tests/README; `main._configure_logging` also reconfigures streams with `errors="backslashreplace"`).

### 2.3 Format / lint / test commands (all verified to run)

```powershell
.venv\Scripts\python.exe -m ruff format <files>          # AGENTS.md step 1
.venv\Scripts\python.exe -m ruff check <files>           # step 2   (equivalent: uv run --no-sync --project . ruff ...)
.venv\Scripts\python.exe -m pytest tests\unit\test_normalize_columns.py -q          # focused: 6 passed, ~1 s (3 s wall incl. start-up)
.venv\Scripts\python.exe -m pytest tests\unit -q                                    # 334 passed, 10.7 s
.venv\Scripts\python.exe -m pytest tests\e2e -q                                     # 20 passed, 3.9 s
.venv\Scripts\python.exe -m pytest tests\ui -q                                      # 404 passed, 20 failed, 7 errors, 25.8 s (pre-existing)
.venv\Scripts\python.exe -m pytest tests -k select -s                               # -s shows stdout
.venv\Scripts\python.exe -m pytest tests\benchmarks --run-benchmarks                # opt-in benchmarks
.venv\Scripts\python.exe -m pytest -n auto --dist loadscope                         # xdist (README says ~1/3 faster; not tried)
```

* Pytest config (`pyproject.toml:124-141`): `testpaths=["tests"]`, `addopts="-ra --strict-markers"`, `qt_api="pyqt6"`, `timeout=120` (thread dump on expiry), markers `unit ui e2e benchmark slow`. Layer markers are added **automatically from the directory** by `tests/conftest.py:85-95`; a typo'd marker fails (`--strict-markers`).
* The only custom flag: `--run-benchmarks` (`conftest.py:76-82`). The only env switches: `TRIGGER_UPDATE_E2E_GOLDENS=1` (rewrite goldens), `TRIGGER_DESIGNER_DATA_DIR` (set by conftest to a temp dir), `QT_QPA_PLATFORM=offscreen` (set by conftest), `TRIGGER_DISABLE_DATA_WARMUP=1` (skip warm-up thread in `main`).
* `ruff check` baseline is **not clean**: `ruff check src/trigger_designer/core` reports 76 errors (61 auto-fixable) that predate you. Only run ruff on files you touch and compare before/after. `ruff format --check` was clean on the files tried.
* Windows: forward slashes work in Bash; PowerShell `>` writes UTF-16 (breaks JSON reads). Never create two `QApplication`s in one process (fast-fail `0xC0000409`).

### 2.4 Test suite state in this environment

| Run | Result |
|---|---|
| `pytest` (all) | **Process aborts** (`Fatal Python error: Aborted`, exit 139) ~22 s in, in the teardown of `tests/ui/test_formula_focus.py::test_editor_diagnostics_replace_stale_section_error_without_rebuilding` (a failing test). Reproduced 3/3. README's "< 20 s" is therefore unverifiable here. |
| `pytest tests/unit` | 334 passed (10.7 s) |
| `pytest tests/e2e` | 20 passed (3.9 s). Prints `AttributeError: 'super' object has no attribute 'setPositions'` tracebacks while loading edges - swallowed by `dumpException`, harmless to results. |
| `pytest tests/ui` | 404 passed / 20 failed / 7 errors. Failures: `test_canvas_grid_render` (6), `test_render_settings` (8), `test_edge_geometry` (7 errors), `test_labels_groups::test_group_collapse_expand_edges`, `test_formula_node` (4) + `test_formula_focus` (1). Causes: installed nodeeditor lacks `QDMGraphicsEdge.setPositions`, `QDMGraphicsScene.updateDetailLod/detail_lod_threshold/MIN_GRID_SPACING_PX` (warning `The installed nodeeditor has no detail policy`), and the SQL editor reports no diagnostics (`editor.errors == []`). `tests/ui/test_formula_node.py` alone ran to completion with 4 failures on one invocation and aborted at exit on another (intermittent teardown abort). |

**Rule for plans:** a plan's verification commands must name specific test files/layers (`tests\unit\...`, `tests\e2e`), never bare `pytest`, and must treat the 27 pre-existing ui failures/errors as the baseline.


---

## 3. Anatomy of a node, end to end

Worked examples: **Split** (`Preparation/split.py`, multi-output, 1 input), **Normalize** (`Preparation/normalize_columns.py`, simple pass-through, SerializableContentMixin schema) and **Union** (`Join/union.py`, multi-input, *correct* modern undo wiring). Filter (`Preparation/filter.py:1136`) is the other 2-output node (`T`/`F`).

### 3.1 Registration and identity (`core/node_configuration.py`)

| Piece | Where | What |
|---|---|---|
| Families | `NodeTypes(StrEnum)` `:23-28` | `IO="input"`, `PREPARATION="preparation"`, `JOIN="join"`, `TRANSFORM="transform"`, `REPORT="report"`. Adding a family also needs `NODE_REGISTRIES` (`:69`), `_OPCODE_ENUMS` (`:79`), a palette tab (automatic: `nodes_list.py` iterates `NodeTypes`) and a Shift+A category in `context_menu_mixin.py:41-45`. Avoid; reuse a family. |
| Op-code enums | `IONodes, PreparationNodes, JoinNodes, TransformNodes, ReportNodes` `:31-65` (`IntEnum` + `auto()`) | Member **name** = identity. Values are 1-based in declaration order (e.g. `IONodes.FILE_INPUT == 3`, `PreparationNodes.SPLIT == 8`). **Append new members at the END of an enum; never rename or delete one.** |
| Stable op id | `"<family>.<member name lowercased>"` e.g. `preparation.normalize_columns`, `input.file_input` | Produced by `TriggerNode.serialize` (`node_base.py:940-955`: `f"{node_type.value}.{node_code.name.lower()}"`), resolved by `get_class_from_op` (`:267-288`, which `.upper()`s the name). **This string is what `.tds` files persist** (`"op"` key). |
| v1 migration | `V1_OPCODE_TO_OP` `:92-121`, `migrate_v1_data` `:291-306` | Frozen map (family, old int) -> op id for pre-v2 files. **Never edit.** A new node needs no entry. Note the v1 ints differ from today's enum values (v1 file_input=4, today 3) - that is why the table exists. |
| Registry | `NODE_REGISTRIES[NodeTypes][int] -> class or LazyNodeReference` | `register_node(code, family)` decorator (`:226`) replaces a lazy entry with the real class (`register_node_now` `:183-197`); a duplicate raises `InvalidNodeRegistration`. |
| Lazy loading | `register_lazy_node` `:200`; `LazyNodeReference` `:138-169`; **specs in `qt/widgets/nodes/__init__.py:14-149`** | Palette and Shift+A menu read `node_title` and `icon` from the *reference* without importing the module. `get_class_from_opcode` (`:234`) imports on first use. |
| Import sweep | `qt/widgets/nodes/__init__.py:161-186` | Every `.py` under `nodes/` **not** listed in `_LAZY_NODE_SPECS` or `_LAZY_HELPER_MODULES` is imported at startup (so an unlisted node still registers, just eagerly). Helper modules that are not nodes and import heavy deps (matplotlib) must be added to `_LAZY_HELPER_MODULES`. Node subfolders are **namespace packages** (no `__init__.py`). |
| Unknown ops | `TriggerSubWindow.getNodeClassFromData` `design_window.py:306-325` | `"op"` present -> `get_class_from_op`; failure -> `TriggerNode_Unknown` (keeps raw content, shows validation warning). No `"op"` -> `migrate_v1_data` of `node_code`/`op_code`. |
| Palette | `NodesDock` -> `QTRDragListbox.addMyItems` (`node_drag_listbox.py:~80`) | Iterates `NODE_REGISTRIES[family]` sorted by int key; shows `node_title` + icon id. Drag payload = `(pixmap, node_code int, family str)`; `onDrop` (`design_window.py:637-688`) calls `get_class_from_opcode(code, family)(scene)` then `scene.history.storeHistory("Created node ...")`. |
| Shift+A menu | `context_menu_mixin.py:36-100` | Same registries; icons via `_get_action_icon` (`ResourceManager` file path, pixmap fallback). |
| Titles | `node_title` class attr; `TriggerNode.deserialize` (`node_base.py:966`) overwrites the saved title with the class title (except Unknown) | Renaming a node title is safe; `tests/unit/test_node_titles.py` pins the spec title == class title. |

### 3.2 Class structure

Every node = **two classes in one module** + registration.

```
TriggerNode_<X>(TriggerNode)            # logic node; owns sockets, eval hooks, get_code() delegate
    initInnerClasses(): self.content = <X>Content(self); self.grNode = TriggerGraphicsNode(self)
                        self.content.evaluate.connect(self.onInputChanged); self.param = []
<X>Content(QDMNodeIconContentWidget, TriggerChangeHandler[, SerializableContentMixin])
    holds ALL state + dock UI + get_code() + serialize()/deserialize()
```

* Base-class order matters: `TriggerChangeHandler` carries `TriggerContentUndoMixin`; `TriggerContent` (`node_base.py:361`) lists the mixin **before** the Qt base so its `history_stamp_callback` wins the MRO. Most nodes use `(QDMNodeIconContentWidget, TriggerChangeHandler)` and call `TriggerChangeHandler.__init__(self, self.node.scene, self.node)` explicitly (the Qt base does not cooperate with `super().__init__`; that is why `_input_widgets` is a lazy property, `node_base.py:401-417`).
* The `node` property/setter pair on every content class is boilerplate required by `TriggerChangeHandler`.
* Class attributes of the node: `icon` (resources.json id), `node_code` (enum member), `node_title`, `node_type` (`NodeTypes`), `content_label_objname` (cosmetic only; no QSS rule uses it today), `style = {}`.
* **Sockets** are declared by the constructor call `super().__init__(scene, inputs=[1], outputs=[3, 3], output_text=["E", "V"])`: one list entry per socket; the int is a socket *colour type* only (1 vs 3 are mixed freely; no type checking). `output_text` is reduced to the first letter, upper-cased (`_normalize_socket_text`, `node_base.py:661-670`). Inputs have no labels here (the base accepts `input_text`). Multi-edge input socket: inherit `MultiInputNode` first (`union.py:847`, `class TriggerNode_Union(MultiInputNode, TriggerNode)`) and read `getOrderedEdges()`.
* Output socket i <-> element i of the list the node returns from `processInputs` (stored in `self.param`/`self.value`).

### 3.3 Live data contract (`processInputs`)

`TriggerNode.evalImplementation` (`node_base.py:816-852`) calls `input_node.eval()` for each input `i` and hands the node `input_values[i] = <upstream node's self.value>` = the **list of output dicts** of the upstream node. The node picks its entry:

```python
input_node = self.getInput(0)                                        # first node wired to input 0
socket_index = self.getSocketValue(input_node.outputs, self)         # which upstream output socket feeds me
entry = input_values[0][socket_index]                                # {"data": LazyFrame|DataFrame, "variable_name": "var_..."}
```

* Return `[{"data": <frame>, "variable_name": <str>}, ...]` (one dict per output socket) on success; **return `None` on failure** after setting a tooltip - the base then does `markInvalid()`, `markDescendantsDirty()`, keeps your tooltip (or "Invalid operation").
* **[SURPRISE]** `getSocketValue` (`node_base.py:708-723`) returns the *first* upstream output socket that has an edge to this node. If two outputs of the **same** upstream node (e.g. Split `E` and `V`) feed two inputs of one downstream node, both inputs resolve to socket 0 (by code reading; Join at `join.py:1460-1462` and Append `Append.py:214-215` use it that way). Plans that need "both outputs of one node into one node" must use `getInputWithSocket` (vendored `node_node.py:566`) or fix this helper.
* `self.param` is also read by the Run path to know the declared output variable names (`workflow_execution_mixin.py:235-238`).
* Live frames are **LazyFrame by convention** (File Input scans CSV lazily; Excel is read eagerly then `.lazy()`); eager `DataFrame` can appear (Append/Join historically). Never call `.columns`/`.dtypes`/`.shape` on `incom_data`: use `frame_schema(frame)` (`node_base.py:59-72`, returns `{name: dtype}` via `collect_schema()` for lazy) and `frame_shape` (`:75-83`). `upstream_rename_map(node)` (`:86-112`) lets downstream nodes follow renames.
* Dirty/invalid caching: `eval()` returns the cached `self.value` unless the node is dirty or invalid (`node_base.py:885-887`). Config changes must go through `self.evaluate.emit()` -> `TriggerNode.onInputChanged` (`:931-938`: `markDirty(); markDescendantsDirty(); eval()`). During file load `_bulk_loading` makes `eval()` a no-op and `_batch_evaluating` suppresses `evalChildren` (`:807-814, 877-884`).
* `eval()` swallows exceptions: `ValueError` -> invalid + tooltip `str(e)`; any other -> invalid + tooltip + `dumpException(e)` (prints traceback to stderr), returns `None` (`:892-900`).

### 3.4 `get_code()` contract (Run Workflow)

* Signature: `get_code(self) -> str` on the content (node delegates `return self.content.get_code()`). Called by `NodeExecutor.execute_node` (`executor.py:310`) **and again** by `getPyFile` after the run (`design_window.py:698-702`) to build `check_output.py` - so it must be **pure and idempotent** (no side effects, no counters).
* Execution: `exec(code, execution_globals, local_vars)` (`executor.py:262-264`) on the executor's pooled worker thread.
  * `execution_globals = {**executor.execution_context, "__name__": "__main__"}`. The context is seeded with `pl`, `os`, `datetime`, `timedelta` (`_seed_base_globals`, `:174-179`) and accumulates **every variable assigned by every earlier node** (`execution_context.update(local_variables)`, `:373`). So upstream frames are visible by their variable name.
  * `local_vars` starts empty; top-level assignments land there and become `ExecutionResult.variables`.
  * **Verified quirk:** because globals and locals are separate dicts, `lambda`/nested `def` bodies in generated code **cannot see names assigned earlier in the same snippet** (`NameError`); comprehensions can (Python 3.13). Upstream variables (globals) are fine anywhere. Avoid nested functions referencing same-snippet temps.
  * Imports in generated code are allowed (no restriction); add `import polars as pl` at the top of any snippet that uses `pl` (the exported `check_output.py` has no seeded globals).
* Required behaviours (from SESSION_HANDOFF "P0 fallbacks", verified in every node): **always define the output variable(s)**, even when unwired/unconfigured (`pl.DataFrame()` or passthrough), so downstream code never `NameError`s; multi-output nodes define **all** output variables (Split: `estimation_var`, `validation_var`; Filter: `variable_name`, `f_variable_name`).
* Variable naming: `var_<kind>_<self.id>` (Split uses `var_estimation_{id}` / `var_validation_{id}`; Filter `var_t_filter_{id}` / `var_f_filter_{id}`; the skeleton `var_head_{id}`). `id` is the content widget's `Serializable.id` (unique per instance; **changes if the node is re-created, restored from the file keeps ids via `restore_id`**).
* Output type: Polars `LazyFrame` is the norm (`docs/prompt_requirements.md`: "Use Lazyframe always unless not possible"); File Output accepts both. Use `collect_schema()` not `.columns` in generated code too (Transpose does).
* The run keeps only declared outputs per node (`_prune_node_results`, `workflow_execution_mixin.py:260-282`: names from `node.param`, `node.value`, then content attrs named `variable_name`, `*_variable_name`, `*_var`). **A node whose output variable is not exposed through one of those names is invisible to the Data Preview after a run.**
* Optional hook: `content.after_execution(variables: dict)` is called by the executor on the worker thread after a successful exec (`executor.py:359-370`); only Graph uses it (`graph.py:545`). Failures there become warnings, not errors.

### 3.5 Persistence (`.tds`)

* File = orjson (indent 2) of `TriggerScene.serialize()` (`performance_scene.py:166-173`): keys `id, scene_width, scene_height, nodes, edges, groups, workflow_metadata{schema_version:2, app_version:"0.1.0", saved_at:<utcnow ISO>}`. Verified by dumping a real save. Saved with plain `open(filename, "w")` (default encoding, **not** UTF-8-forced) in `Scene.saveToFile` (vendored `node_scene.py:621-636`). `loadFromFile` (`:640-660`) **swallows non-JSON exceptions** (`dumpException`) so a partly failed load still "succeeds".
* Node dict: `id, title, pos_x, pos_y, inputs[], outputs[] (socket ids/index/position/socket_type/multi_edges), content{...}, label_text, label_visible, label_offset, node_code, node_type, op`. Edge dict: `id, edge_type, start, end, label, input_index`.
* `content` = whatever the content class's `serialize()` returns. Two styles:
  1. **Schema style (preferred)**: `SerializableContentMixin.serialized_state_schema = {"key": {"default": ..., "attr": "optional_attribute_name"}}` (`state_mixin.py`); `serialize() -> self.serialize_content_state(super().serialize())`; `deserialize` calls `deserialize_content_state(data)`. Missing keys take the default => **backward compatible by construction**; dict defaults are merged. `validate_loaded_state() -> list[str]` (default `[]`) is called after load; messages go to the Logging dock and one warning dialog (`design_window.py:461-508`).
  2. Hand-written `res = super().serialize(); res[...] = ...` with `data.get(key, default)` in `deserialize` (Split, File Output).
* `WORKFLOW_SCHEMA_VERSION = 2` (`core/constants.py`) is *written* and *logged* on load but **no migration code branches on it**; compatibility is by tolerant `.get` defaults and the `op`/v1 map. A new node or new key needs no version bump. Bump only for a breaking change and add the branch yourself in `TriggerScene.deserialize` or `_load_with_dialog` (`design_window.py:433-459`).
* Content must be JSON-serialisable by orjson (no dataclass instances: `Select` once saved raw `RowData`; datetimes need `.isoformat()`).

### 3.6 Icons, resources, tooltips, titles

| Need | Edit |
|---|---|
| Canvas icon + palette icon | Add SVG under `src/trigger_designer/resources/qt/images/node_icons/<Family>/<Name>.svg`; add `"node_<name>": {"path": "qt/images/node_icons/<Family>/<Name>.svg", "mode": "rb"}` to `qt/resources.json`; set `icon = "node_<name>"` on the node and in the `_LAZY_NODE_SPECS` entry. Until a dedicated icon exists, reuse an existing id (Normalize reuses `node_select`). `ResourceManager().get(id)` renders SVG ("rb") to a `QPixmap`, caches it. A missing id returns `None`. |
| Shift+A menu icon | Add the SVG and a `resources.json` entry; the menu resolves it through `ResourceManager`. No compile step. |
| UI glyphs (buttons) | `resources.json` ids `icon_*` under `qt/images/node_icons/ui/*.svg` are monochrome and re-coloured per theme (`theme_icons.py`). Use `IconButton.themed(tooltip, rsm_icon=rsm.get("icon_x"), qss_fallback=":/qss_icons/dark/rc/<name>.png")`. |
| Node status badge / ring | Automatic: `TriggerGraphicsNode.paint` picks the badge from `status_icons.png` (dirty / ok / invalid) and the ring colour from `setPenExecuting/Executed/Error` (`node_base.py:336-358`) using theme tokens `activity/success/danger`. |
| Tooltip (error/status text on canvas) | `self._set_node_tooltip(text)` (None-safe, `node_base.py:775-789`) or `self.grNode.setToolTip(text)`. Empty string clears. |
| Title | `node_title` class attr + spec; displayed on canvas and palette. |
| Category colour | Theme tokens `node_input/node_prepare/node_join/node_transform/node_report` (`resources/qt/themes/*.json`). |

### 3.7 ADD A NEW NODE RECIPE

Do the steps in order; every step names the exact file. "Family" = one of the five `NodeTypes`.

1. **Enum member.** `src/trigger_designer/core/node_configuration.py`: append `MY_NODE = auto()` at the **end** of the family enum (e.g. `PreparationNodes`, currently ending `NORMALIZE_COLUMNS`). Never reorder/rename. Op id becomes `"<family>.my_node"`.
2. **Node module.** Create `src/trigger_designer/qt/widgets/nodes/<Family folder>/<snake_name>.py` (folders: `InOut`, `Join`, `Preparation`, `Transform`, `Report`; no `__init__.py`). Copy the skeleton in 3.8. Put Qt-free logic (parsing, rules, summary maths) in a **separate** `core/...` module and import it, so unit tests need no widgets (pattern: `normalize_column_name` / `build_rename_mapping` at top of `normalize_columns.py`, ideally moved under `core/`).
3. **Register the class** with `@register_node(<Enum>.MY_NODE, NodeTypes.<FAMILY>)` directly above `class TriggerNode_MyNode(TriggerNode)`; set `node_code = <Enum>.MY_NODE`, `node_type`, `node_title`, `icon`, `content_label_objname`.
4. **Lazy spec.** `src/trigger_designer/qt/widgets/nodes/__init__.py`: add to `_LAZY_NODE_SPECS`:
   `{"module_path": "<FolderName>.<module_stem>", "node_code": <Enum>.MY_NODE, "node_type": NodeTypes.<FAMILY>, "node_title": "<Title>", "icon": "node_<name>"}`. Title and icon **must equal the class attributes** (`tests/unit/test_node_titles.py`). If you skip this step the node still works (eager import) but loads at startup.
5. **Icon.** Add SVG + `resources.json` entry (3.6), or reuse an existing icon id.
6. **Sockets.** Choose `inputs=[...]`, `outputs=[...]` in `__init__`; multi-input => `MultiInputNode`.
7. **State.** Declare `serialized_state_schema` (key + default) and give the content the attributes; implement `serialize/deserialize` exactly as in the skeleton (`validate_loaded_state` if loaded settings can go stale).
8. **Live logic.** Implement `processInputs` (3.3) and the content's `update_data`; return `None` + tooltip on error; use `frame_schema()` for names/dtypes; keep frames lazy.
9. **Codegen.** Implement `get_code` (3.4): defines output var(s) on every path; `import polars as pl` first.
10. **Dock UI.** `create_layout(dock_layout)` per section 5: `EmptyStateLabel` gate, `ConfigSection`/`FormRow`/shared widgets only; optional `dock_context()` for the pane tooltip.
11. **Undo.** Slots follow the 6.3 pattern (guard -> mutate model -> `self.evaluate.emit()` -> `push_property_change(...)`); implement `_sync_widgets_from_model` (and `_rebuild_widgets` if the widget *count* depends on the model).
12. **Tests** (section 9): a unit test for codegen/live agreement, a ui test for the dock + undo, and (if it writes files) a `WorkflowCase` in `tests/support/corpus.py` with a golden. Update `tests/unit/test_node_titles.py` only if you rename an existing node.
13. **Docs.** Add a row to `docs/NODE_REFERENCE.md` (that file is stale; fix the Union gap while you are there) and, if the node adds files, check `trigger.spec` includes them.
14. **Verify:** `ruff format` + `ruff check` on touched files, then the focused tests, then `pytest tests\unit tests\e2e` (expect 334+/20+ passing). Smoke manually: drop the node unwired -> Run completes with no `NameError`; wire File Input through -> Run; save, reload, Run again (SESSION_HANDOFF "Manual smoke").

### 3.8 Verified skeleton (single-input / single-output pass-through "Head")

The three files below were written to a scratch directory and **run against the repo with pytest: 5 passed** (unit 3, ui 1, e2e 1), then deleted. Differences from a real file are marked `REAL:` or `# <- real file` (the verified copy could not call `@register_node` without adding an enum member to the repo, so it reuses `NORMALIZE_COLUMNS`'s code and does not decorate). Copy `head_node.py`; replace those lines (enable the `@register_node` decorator, use your new enum member).

```python
"""Skeleton: single-input / single-output pass-through node ("Head").

Copy to src/trigger_designer/qt/widgets/nodes/<Family>/<module>.py and follow
the ADD A NEW NODE RECIPE in docs/plan/00-codebase-brief.md.
"""

from typing import Any, Optional

from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget
from nodeeditor.utils_no_qt import dumpException
from qtpy.QtCore import Signal
from qtpy.QtGui import QPixmap
from qtpy.QtWidgets import QSpinBox, QVBoxLayout, QWidget

from trigger_designer.core.node_configuration import (
    NodeTypes,
    PreparationNodes,
    register_node,  # noqa: F401  (used as decorator in the real file)
)
from trigger_designer.qt.helpers.state_mixin import SerializableContentMixin
from trigger_designer.qt.node_base import (
    TriggerChangeHandler,
    TriggerGraphicsNode,
    TriggerNode,
)
from trigger_designer.qt.undo.protocol import is_syncing
from trigger_designer.qt.widgets.common import ConfigSection, EmptyStateLabel, FormRow


class HeadContent(
    QDMNodeIconContentWidget, TriggerChangeHandler, SerializableContentMixin
):
    """Keeps the first ``row_limit`` rows."""

    evaluate = Signal()
    #: key -> {"default": ..., "attr": optional attribute name}. Drives
    #: serialize()/deserialize(); a missing key in an old file gets the default.
    serialized_state_schema = {"row_limit": {"default": 100}}

    def __init__(self, node: "TriggerNode", parent: Optional[QWidget] = None) -> None:
        super().__init__(node, parent)
        TriggerChangeHandler.__init__(self, self.node.scene, self.node)
        self.history = self.node.scene.history  # push_* helpers read self.history

        self.incoming_variable: str = ""  # set by the node in processInputs
        self.incom_data: Optional[Any] = None  # LazyFrame (or DataFrame)
        self.data: Optional[Any] = None  # what this node emits
        self.variable_name = f"var_head_{self.id}"  # unique per node instance
        self.row_limit: int = 100
        self.row_spin: Optional[QSpinBox] = None

    # TriggerChangeHandler expects a plain ``node`` attribute; every content
    # class in the repo repeats this property pair.
    @property
    def node(self) -> "TriggerNode":
        return self._node

    @node.setter
    def node(self, value: "TriggerNode") -> None:
        self._node = value

    def initUI(self, icon: Optional[QPixmap] = None) -> None:
        # The canvas icon is a ResourceManager id (resources.json), not a qrc path.
        super().initUI(self.node.rsm.get(f"{self.node.icon}"))

    # ---- model -> data ---------------------------------------------------
    def update_data(self) -> None:
        self.data = (
            None if self.incom_data is None else self.incom_data.head(self.row_limit)
        )

    # ---- Config Dock -----------------------------------------------------
    def create_layout(self, dock_layout: QVBoxLayout) -> None:
        if self.incom_data is None:
            dock_layout.addWidget(EmptyStateLabel())
            return
        section = ConfigSection()
        self.row_spin = QSpinBox()
        self.row_spin.setRange(1, 10_000_000)
        self.row_spin.setMinimumHeight(30)
        self.row_spin.setValue(self.row_limit)
        self.row_spin.valueChanged.connect(self._on_row_limit_changed)
        section.addWidget(FormRow("Rows", self.row_spin, label_width=64))
        dock_layout.addWidget(section)
        dock_layout.addStretch()
        # ConfigDock calls registerUnboundDockWidgets() afterwards, so the spin
        # is tracked even without an explicit registerInputWidget() call.

    def dock_context(self) -> tuple[list[tuple[str, str]], str]:
        return [(f"first {self.row_limit:,} rows", "accent")], ""

    def _on_row_limit_changed(self, value: int) -> None:
        # Guard 1: model->widget write-backs are not user edits.
        if is_syncing(self) or self.history.is_restoring_history:
            return
        old = self.row_limit
        if value == old:
            return
        self.row_limit = value  # mutate the model first
        self.refresh_dock_context()
        self.evaluate.emit()  # re-run the graph (node.onInputChanged)
        self.push_property_change(  # then record one undo step
            ("row_limit",), old, value, "Head Rows Changed", merge_key="head-rows"
        )

    # ---- undo projection ---------------------------------------------------
    def _sync_widgets_from_model(self) -> None:
        spin = self.row_spin
        if spin is None:
            return
        try:
            if spin.value() != self.row_limit:
                spin.blockSignals(True)
                spin.setValue(self.row_limit)
                spin.blockSignals(False)
        except RuntimeError:  # dock rebuilt: widget already deleted
            self.row_spin = None

    # ---- code generation ---------------------------------------------------
    def get_code(self) -> str:
        if not self.incoming_variable:
            # ALWAYS define the output variable so downstream code cannot NameError.
            return f"import polars as pl\n{self.variable_name} = pl.DataFrame()\n"
        return (
            f"{self.variable_name} = {self.incoming_variable}.head({self.row_limit})\n"
        )

    # ---- persistence ---------------------------------------------------------
    def serialize(self):
        return self.serialize_content_state(super().serialize())

    def deserialize(self, data, hashmap={}):
        res = super().deserialize(data, hashmap)
        try:
            self.deserialize_content_state(data)
            return True and res
        except Exception as exc:  # noqa: BLE001
            dumpException(exc)
        return res


# @register_node(PreparationNodes.NORMALIZE_COLUMNS, NodeTypes.PREPARATION)  # <- real file
class TriggerNode_Head(TriggerNode):
    icon = "node_select"  # resources.json id
    node_code = PreparationNodes.NORMALIZE_COLUMNS  # REAL: your new enum member
    node_title = "Head"
    node_type = NodeTypes.PREPARATION
    content_label_objname = "trigger_node_head"
    style = {}

    def __init__(self, scene) -> None:
        # inputs/outputs are lists of socket types (ints); one entry = one socket.
        super().__init__(scene, inputs=[1], outputs=[3])

    def initInnerClasses(self) -> None:
        self.content: HeadContent = HeadContent(self)
        self.grNode: TriggerGraphicsNode = TriggerGraphicsNode(self)
        self.content.evaluate.connect(self.onInputChanged)
        self.param: list = []

    def processInputs(self, input_values) -> Optional[list]:
        # input_values[i] is the *list of output dicts* of the node wired to
        # input i; pick the entry for the socket that feeds us.
        input_node = self.getInput(0)
        socket_index = self.getSocketValue(input_node.outputs, self)
        entry = input_values[0][socket_index]
        if not entry or entry.get("data") is None:
            self.markDirty(True)
            self.markInvalid(True)
            self._set_node_tooltip("Input has no data")
            return None  # None => base class marks invalid + keeps tooltip
        self.content.incom_data = entry["data"]
        self.content.incoming_variable = entry["variable_name"]
        self.content.update_data()
        self.param = [
            {"data": self.content.data, "variable_name": self.content.variable_name}
        ]
        return self.param  # becomes self.value; children read it via eval()

    def get_code(self) -> str:
        return self.content.get_code()
```


---

## 4. Evaluation architecture

Two independent paths exist and **must not be confused**:

| | Live evaluation | Run Workflow |
|---|---|---|
| Trigger | any config change, edge change, file load | Run button (`run_button` -> `TriggerSubWindow.run_workflow`, `design_window.py:690`) |
| Thread | GUI thread (synchronous) | `WorkflowWorker` QThread -> `NodeExecutor` pooled daemon thread; results delivered by signals to the GUI thread |
| Code | `processInputs()` Python calling Polars directly on lazy frames | `get_code()` strings `exec()`'d |
| Data | `node.value` (list of `{"data","variable_name"}`), cached by dirty/invalid flags | `window.execution_results[node] = {var_name: LazyFrame/DataFrame/...}` |
| Errors | tooltip + `markInvalid` | `ExecutionResult.error` string, red ring, Logging dock |
| Side effects | none (no files written) | File Output writes files; `check_output.py` written |

### 4.1 Live path (`qt/node_base.py`)

```
user edits control
  -> content slot mutates model; self.evaluate.emit()                 (Signal on content)
  -> TriggerNode.onInputChanged (node_base.py:931)  [skipped if content._suspend_node_evaluation]
       markDirty(); markDescendantsDirty(); eval()
  -> TriggerNode.eval (877)
       if scene._bulk_loading: return self.value                       # load in progress
       if not dirty and not invalid: return cached self.value          # cache hit (no progress/notify)
       scene._eval_progress_cb(self, False)                            # progress dialog hook (load only)
       try evalImplementation() (816):
            for each input i: getInput(i) is None -> markInvalid, markDescendantsDirty, tooltip "Input i is not connected", return None
                              val = input_node.eval()   # RECURSION upstream (cached if clean)
                              val is None -> markInvalid, tooltip "Input i: upstream node produced no output", return None
            result = processInputs(input_values)        # node-specific; may return None
            result is None -> markInvalid, markDescendantsDirty, default tooltip "Invalid operation" (only if none set), return None
            self.value = result; markInvalid(False); markDirty(False); tooltip ""
            evalChildren()  # push to children; no-op while scene._batch_evaluating
            _refresh_selected_node_config()  # rebuilds dock if this node is selected
       except ValueError -> markInvalid; tooltip str(e); markDescendantsDirty            (returns None)
       except Exception  -> markInvalid; tooltip str(e); dumpException(e); return None
       finally: scene._eval_progress_cb(self, True); scene.notifyNodeEvaluated(self)   # DataPreviewDock listens
```

* **File load**: `TriggerSubWindow.fileLoad` (`design_window.py:419`) -> `_load_with_dialog` (`:433`): `Scene.loadFromFile` inside `_suspend_scene_restore_updates` (bulk-load flags), `validateConnections`, `validateLoadedWorkflow`, then `doEvalOutputs(dialog)` (`:327-356`): topological order, `scene._batch_evaluating=True`, `node.eval()` each, then `settle_multi_input_nodes` (`performance_scene.py:183`). The only progress UI in the app is this load dialog (`eval_progress.py`, shown when a dialog is passed; `PROGRESS_NODE_THRESHOLD = 8`); **Run has no progress dialog**, only per-node ring colours.
* Threading: live eval is GUI-thread only. Heavy live work (e.g. collecting) freezes the UI. Preview collection uses `qt/models/preview_worker.py` (separate worker).
* Caching nuance: `eval()` only recomputes when dirty/invalid; code that changes config must `markDirty(True)` + `markDescendantsDirty()` before `eval()` (what `onInputChanged` does). In tests, `FileInput.eval()` re-reads the file from `filePath`.
* Lazy plans are *planned* here, never collected, except where a node inherently needs data: Count (`len` query), Formula (DuckDB registers an Arrow table - collects, restores lazy), Cleansing stats, Graph (matplotlib), Rows stats fallback. `frame_schema()` calls `collect_schema()` which **does** resolve the plan and raises on bad column references - that is where most live schema errors surface.

### 4.2 Run Workflow path

```
GUI thread                                   WorkflowWorker (QThread)                 NodeExecutor pooled thread
----------                                   ------------------------                 --------------------------
run_workflow() (design_window:690)
 executeWorkflow() (mixin:47)
  guard: worker already running -> return
  run_button.setEnabled(False)               (before the sort: a cycle error leaves it disabled)
  connections = getNodeConnections()         (design_window:711)
  sorted_nodes = topologicalSort()           (:736; Kahn; raises Exception("Graph has at least one cycle"))
  executor = NodeExecutor()                  (NEW per run: fresh context + worker thread)
  execution_results.clear(); every node: markInvalid(False), grNode.resetPen()
  worker = WorkflowWorker(sorted_nodes, executor); connect signals; worker.start()
                                             run() (workflow_worker.py:43)
                                              for node in nodes:
                                               if _cancel_requested: success=False; break   # nobody sets it
                                               nodeStarted.emit(node) -----------> GUI: _on_node_started: setPenExecuting
                                               executor.execute_node(node) (executor.py:289)
                                                 code = node.get_code()
                                                 _execute_with_timeout(code, locals, 30 s) --queue--> exec(code, {**context,"__name__":"__main__"}, locals)
                                                 wait up to max_execution_time; on timeout: ExecutionTimeoutError, thread abandoned
                                                 memory check AFTER exec: RSS delta > 512 MB -> ExecutionMemoryError
                                                 exception -> NodeExecutionError(str(exc), original_exception=exc)
                                                 success: result.variables = locals copy; after_execution hook; context.update(locals)
                                               nodeFinished.emit(node, result) --> GUI: _on_node_finished (mixin:96)
                                               if not result.success: success=False; break   # STOP at first failure
                                              workflowFinished.emit(success) ----> GUI: _on_workflow_finished (mixin:125)
GUI slots:
 _on_node_finished: ok -> execution_results[node] = _prune_node_results(...); setPenExecuted
                    fail -> logger.error + global_logger.error("Node execution failed for '<title>': <error>");
                            node.markInvalid(); setPenError   (NO tooltip is set on the node!)
 _on_workflow_finished: _workflow_worker=None; getPyFile(sorted_nodes) -> writes ./check_output.py;
                        success: QTimer.singleShot(1000, cleanup) else cleanup now; emit executionResultsChanged
 _execution_cleanup (mixin:143): timing stats to Logging dock; reset pens of valid nodes (invalid keep red); run_button enabled
```

Facts verified in code:

* **Order/scope**: all scene nodes run in topological order, including unconnected ones (an unwired node runs its fallback code). Nodes after a failure never run (no result, pen stays default).
* **`ExecutionResult`** (`executor.py:34-47`): `success, output (captured stdout), error (str), variables (dict), execution_time, memory_used, peak_memory (MB deltas of process RSS), lines_executed, warnings (stderr text, hook failures), timestamp`. `.without_frames()` returns a copy with variables described as strings for the 100-item `execution_history`. **No node id, no exception object, no row counts, no code text, no start time other than `timestamp` (creation)**.
* `ExecutionStats` (`:78-87`) aggregates counts/time/max memory; `SecurityConfig` has **only** `max_execution_time=30.0` and `max_memory_mb=512.0` (**[STALE DOC]** `ENHANCED_EXECUTOR_GUIDE.md` documents `allowed_imports`, forbidden functions, restricted builtins - none exist).
* **Timeout** wraps the whole node's exec; sinks (`sink_csv`) on a large file may legitimately exceed 30 s => `ExecutionTimeoutError` while the abandoned thread keeps writing. Not configurable from the UI. A timed-out exec thread is never reused (the run stops).
* **Memory limit** is measured once, after exec returned, as RSS delta (`:329-338`); it is advisory and can be tripped by unrelated allocations.
* `redirect_stdout/redirect_stderr` (`_capture_output`) is process-global while a node executes; generated `print()` goes to `result.output` which nobody displays.
* Result storage: `window.execution_results: Dict[node, Dict[var, value]]` (only declared outputs, `_prune_node_results`). `getSocketData(node, socket_index)` (`mixin:300`) resolves a socket's frame; the Data Preview dock and the socket-click preview read it. `executionResultsChanged` (Qt signal on `TriggerSubWindow`) fires after every run - `DataPreviewDock.note_run_finished` and tests (`run_workflow_and_wait`) listen.
* Pens/status colours: `executing` = theme token `activity` (purple), `executed` = `success` (green), `error` = `danger` (red), default transparent (`node_base.py:187-203`, `336-358`). Cleanup resets valid nodes to default after 1 s; invalid nodes keep the red ring. The bottom-edge **status badge** is from `status_icons.png` by `isDirty()/isInvalid()`.
* Cancellation: `WorkflowWorker.request_cancel()` (`:39`) "takes effect before the next node" but is never called; `NodeExecutor.cancel_execution()` (`:457`) sets `_cancel_event`, which nothing waits on. There is no way to interrupt a running exec thread.
* `getPyFile` (`design_window.py:698`): `CHECK_OUTPUT_HEADER + node.get_code()` for each sorted node, written to relative `check_output.py`. The header injects `src/` into `sys.path` so the script runs from the repo root. It is the closest thing to an "export to Python".
* `NodeExecutor._report_missing_dependency` logs `NameError`/`FileNotFoundError` retries through `global_logger` **from the executor thread** (touches the Logging dock off the GUI thread; `LoggingDock.log` has no lock).

### 4.3 Where lazy plans are sunk/collected in Run

| Node | Run-time materialisation |
|---|---|
| File Output | `sink_csv/sink_parquet/sink_ndjson/sink_ipc` (streaming); `collect().write_excel/write_json` (needs xlsxwriter for excel) - the only normal sinks |
| Graph | `after_execution` hook collects for the chart window |
| Count | generated code runs `select(pl.len()).collect().item()` (`count_records.py:137`) and emits an **eager** 1-row `pl.DataFrame({'Count': [n]})` - the precedent for "summary as a frame" |
| Formula, Filter (expression mode) | generated code collects `df_for_duck` (`formula.py:1305`, `filter.py:1034`), registers it in DuckDB, returns lazy again |
| Cleansing | generated code collects its input (`cleansing.py:651`) |
| Everything else | stays lazy until a sink |

### 4.4 Hook points for cross-cutting features

Recommendation key: **USE** = recommended primary hook; **OK** = acceptable secondary; **AVOID** = reason.

| # | Hook | Location | Thread | Gives you | Cost / risk | Recommendation |
|---|---|---|---|---|---|---|
| H1 | `WorkflowExecutionMixin.executeWorkflow` | `workflow_execution_mixin.py:47-89` | GUI | Run start: node list, order, workflow path (`self.filename`), run counter | Single place to mint a `run_id`; must not break when `filename` is None (unsaved) | **USE** for run begin (`RunRecorder.begin`) |
| H2 | `_on_node_finished(node, result)` | `:96-112` | GUI | Node object (id, op, title, content), `ExecutionResult`, success/error, durations | Frames in `result.variables`; reading them is cheap, *counting* lazy rows is not | **USE** for per-node records and error translation (`translate_exception`) |
| H3 | `_on_node_errored(node, exc)` | `:114-123` | GUI | The raw exception (only for failures *outside* `execute_node`'s own try) | Rare path (`# pragma: no cover`) | **OK** (also translate here) |
| H4 | `_on_workflow_finished(success)` | `:125-141` | GUI | Run end; `execution_results` complete; `executionResultsChanged` emitted right after | `getPyFile` runs just before: generated script available | **USE** for run finish + writing the run record file |
| H5 | `NodeExecutor.execute_node` except/finally | `executor.py:378-417` | worker/exec | Original exception object (`e.original_exception`), traceback, timing, memory | Runs off-GUI; keep it Qt-free. Currently drops exception type | **USE** only to *preserve* the exception on `ExecutionResult` (add fields `exception`, `traceback_text`, `code`, `started_at`); translate on the GUI thread (H2) |
| H6 | `after_execution(variables)` content hook | `executor.py:359-370` | worker | Output variables of that node right after exec, before pruning | Per-content opt-in; failures only warn | **USE** for row counting of *declared outputs* (e.g. `pl.LazyFrame.select(pl.len())` capped/optional) and for audit-test result capture, because it sees frames that may be pruned later |
| H7 | `WorkflowWorker.run` signals | `workflow_worker.py:43-68` | worker | Per-node start/finish ordering | Signals already carry node+result | **OK** (no change needed); add `runStarted` only if H1 is insufficient |
| H8 | `TriggerNode.eval` `except` branches | `node_base.py:892-900` | GUI | Live errors with exception object | The only live choke point (plus the tooltips in `evalImplementation`) | **USE** for plain-language live errors: replace `str(e)` with `translate_exception(e, node=self).title` and keep the technical text in a second tooltip line |
| H9 | `scene.notifyNodeEvaluated(node)` | `performance_scene.py:149`, called from `node_base.py:905-909` | GUI | Every real live recompute | Fires often (every keystroke commit) | **USE** for live "data profile"/row-count refresh; **AVOID** for audit trail (not a run) |
| H10 | `TriggerSubWindow.getPyFile` | `design_window.py:698` | GUI | Full generated script, sorted nodes | Writes into CWD (bad for CLI/service use) | **OK** to capture the script text into the run record; **AVOID** extending the CWD write - make the target path an argument |
| H11 | `fileLoad` / `validateLoadedWorkflow` | `design_window.py:419-508` | GUI | Missing-input detection, schema drift messages (`FileInputContent.validate_loaded_state`) | Dialog + log based | **USE** for "resolved input files" checks (01) and CLI pre-flight (08) |
| H12 | `global_logger` / loguru | `helpers/global_logger.py`, `main.py:97-146` | any | Free-form text only | Not structured; log scraping is fragile | **AVOID** as an audit source; fine for human diagnostics |
| H13 | `TriggerScene.serialize/deserialize` | `performance_scene.py:166-180` | GUI | `workflow_metadata` block | Written on every save; additive keys are safe | **USE** to add run-related metadata (e.g. `workflow_uuid`) |

**Minimal-intrusion recipe for run recording (02):** (a) add optional fields to `ExecutionResult` (H5), (b) create the recorder in `executeWorkflow` (H1), (c) append `NodeRunRecord` in `_on_node_finished` (H2), (d) finalise + persist in `_on_workflow_finished` (H4), (e) get row counts from H6 only for nodes that opt in. Do **not** touch `WorkflowWorker`.

---

## 5. Config Dock and UI conventions

### 5.1 `ConfigDock` lifecycle (`qt/docks/node_config.py`)

1. Selection (canvas) -> `main_window.createMdiChild` listeners call `configDock.updateConfig(nodeeditor.getSelectedItems())` (`main_window.py:495-501`). Items are **graphics nodes** (`grNode`); `updateConfig` accepts anything with `.node` or `.socket` and reads `.content`.
2. `updateConfig(nodes, force=False)` (`:78-166`): disconnect previous label sync; detach context refresh; `_commit_previous_if_leaving` (calls `content.commit_pending_dock_edits()` if present - Aggregate); if not exactly one node -> clear dock; **`if id(content) == self._current_key and not force: return`** (`:118`) - keeps focused editors alive; else `clear_dock()` (deleteLater every widget), set `content._dock_context_refresh`, set `content._suspend_input_tracking = True` and `content._suspend_node_evaluation = True`, call `content.create_layout(self.dock_layout)`, then in `finally`: add the **Label row** (`_add_label_section`), mount `content.dock_actions()` widgets next to it, run **`content.registerUnboundDockWidgets(self.dock_layout)`** (every tracked widget not already bound becomes undoable), restore the two flags.
3. `create_layout` exceptions are caught and `traceback.print_exc()`'d (`:164-166`): a bug there leaves a **silently blank panel** (+ stderr traceback). Tests should call `create_layout` directly to see errors.
4. `force=True` is passed by `TriggerSubWindow.onHistoryRestored` (`design_window.py:358-376`) after undo/redo; **do not remove** (AGENTS.md).
5. The pane tooltip comes from `content.dock_context() -> (list[(text, tone)], label)` (`_context_summary`, `:331-373`). Optional hooks on content: `dock_context()`, `dock_actions() -> list[QWidget]` (parentless widgets), `commit_pending_dock_edits()`, `refresh_dock_context()` (from the mixin).
6. `iter_dock_widgets` / `registerUnboundDockWidgets` (`node_base.py:518-592`): traverse layouts, descending into `QScrollArea.widget()`; skip any widget nested under a parent with `_undo_composite = True` (`SegmentedControl`, `ColumnChecklist`, `SQLFormulaWidget`; `ConfigSection` is **not** a composite - `union.py:349` marks its own sections).

### 5.2 Design-system tokens (`docs/DESIGN_SYSTEM.md` §§0-7; constants in `config_widgets.py:32-40`)

| Token | Value | Constant |
|---|---|---|
| Dock min width | 300 | `ConfigDock.initUI` |
| Main layout | spacing 2, margins 5 | `ConfigDock.dock_layout` already applies this; nodes add sections to it |
| Control height | 30 | `CONTROL_H` (`setMinimumHeight(30)` on `QLineEdit/QSpinBox/QComboBox`) |
| Icon button | 30x30, icon 12x12 | `IconButton` (`ICON_SIZE=12`) |
| Toolbar row | fixed height 40, margins 0 | Select toolbar (`select.py:159-162`) |
| Chrome strip / chip / row | 36 / 24 / 28 (dense 24) | `STRIP_H, CHIP_H, ROW_H, DENSE_ROW_H` |
| Section gap | 4 | `SECTION_GAP` |
| Debounce | 300 ms text/search | `DEFAULT_DEBOUNCE_MS` (`binding.py:54`) |
| Spacing scale | 2/4/6 inside a panel, 8/12 between groups | DESIGN_SYSTEM §0.4 |
| Fonts | Segoe UI Variable Text / Cascadia Mono | theme |
| Colour | **never hex**; theme tokens (`text_primary`, `background_hover`, `danger`, `success`, `warning`, `accent_primary`, `node_*`) from `resources/qt/themes/*.json`; `base.qss` is a `str.format` template - a `{token}` missing from any theme raises at startup (`tests/unit/test_theme_tokens.py` guards) | `theme_manager.py` is the **only** owner of `QApplication.setStyleSheet` |

QSS rules: a new `objectName` needs rules in both `resources/qt/themes/base.qss` and `qss/_style.scss`, with `:hover`, `:pressed`, `:disabled` restated using `{background_hover}`/`{background_pressed}` and a constant 1px border (DESIGN_SYSTEM §4.5). No inline `setStyleSheet`.

### 5.3 Shared widgets (`qt/widgets/common/config_widgets.py`, re-exported by `qt/widgets/common/__init__.py`)

| Widget | Signature | Notes |
|---|---|---|
| `IconButton` | `IconButton(tooltip: str, icon: QIcon\|QPixmap\|str\|None=None, parent=None)`; `IconButton.themed(tooltip, rsm_icon=None, qss_fallback=None, theme_fallback=None, parent=None)` | `objectName="IconButton"`, fixed 30x30, sets tooltip + accessibleName; `apply_theme()` re-resolves glyph on theme change. Always pass `rsm_icon=self.node.rsm.get("icon_x")`. |
| `TextButton` | `TextButton(text, tooltip=None, parent=None)` | Only for paired `All`/`None`. `objectName="TextButton"`. |
| `NoWheelComboBox` | `QComboBox` subclass | Use for **every** combo in the dock (wheel-steal bug). |
| `ConfigSection` | `ConfigSection(title="", info=None, parent=None, *, collapsible=False, collapsed=False, count=None)`; `.addWidget(w, stretch=0)`, `.addLayout(l, stretch=0)`, `.set_count(text)`, `.add_header_action(w)`, `.set_title`, `.set_collapsed` | Flat section: header (title only if needed) + hairline. `objectName="ConfigSection"`; `info` renders `ConfigSectionInfo` label. |
| `FormRow` | `FormRow(label, field, hint=None, parent=None, *, label_width=0, action=None)`; `.field()`, `.replace_field(w)` | One 30px row: label, control, optional trailing action button (browse). |
| `FormGrid` | `FormGrid()`; `.add(...)` | Aligned label/field grid. |
| `SegmentedControl` | `SegmentedControl(options, current=None)`; `.value()`, `.set_value(v)`, signal `changed(str)` | `_undo_composite=True`. |
| `ColumnChecklist` | `ColumnChecklist(columns=(), checked=(), label_fn=None, min_height=0, max_height=320, parent=None)`; `.setColumns(cols, checked)`, `.setChecked(list)`, `.set_all_checked(bool)` (**one** emit), `.checked()`, `.checkboxes: dict[str, QCheckBox]`, signal `changed(list)` | `_undo_composite=True`. Never loop `setChecked` on the boxes (N re-evaluations). |
| `EmptyStateLabel` | `EmptyStateLabel(text="No incoming data available", parent=None)` | The only empty state. Gate `create_layout` on `incom_data is None`. |
| `Chip`, `StatusBadge`, `ContextStrip`, `InspectorHeader` | see file | Chrome pieces; `InspectorHeader`/`ContextStrip` are no longer mounted by the dock. |

### 5.4 How a typical node builds its dock

Reference `select.py:133-269` (Pattern A, toolbar + table): `if incom_data is None: return`; `ConfigSection("")`; toolbar `QWidget` fixed height 40 with `QLineEdit` search (min height 30, clear button), `TextButton("All")`/`TextButton("None")` (objectName `BulkButton`), `IconButton.themed(...)` move up/down, `IconButton.themed(..., rsm_icon=rsm.get("icon_options"))` named `OptionsButton`; `SelectTableWidget` model behind a `QSortFilterProxyModel` (case-insensitive, all columns); `QTableView` objectName `ColumnTable`, 22px rows, `ComboBoxDelegate` for dtype. Pattern B (form stack, e.g. `split.py:95-143`, `normalize_columns.py:206-288`): `EmptyStateLabel` gate; `ConfigSection` -> `FormRow(label, widget, label_width=...)`; `dock_layout.addStretch()` last (never an empty `HBox` after the stretch).

### 5.5 Adding a new dock (Data Preview / Logging are the models)

1. Class `class MyDock(QDockWidget)` in `qt/docks/my_dock.py`; `__init__(parent)`: `super().__init__(_TITLE, parent)`; `self.setObjectName("MyDock")` (**stable object name is mandatory** for `saveState`/`restoreState`, `layout_state.py`); build UI in a child widget; `setFeatures(DockWidgetMovable | DockWidgetFloatable | DockWidgetClosable)`; follow the active design window via `switch_to_design_window(design_window)` and `remove_design_window(window_id)` (copy `DataPreviewDock`/`LoggingDock`), keyed by `str(id(design_window))`.
2. `qt/helpers/main_window_ui_mixin.py` `MainWindowDockMixin`: add `createMyDock()` (`self.myDock = MyDock(self); setObjectName; self.addDockWidget(Qt.BottomDockWidgetArea, self.myDock); self.tabifyDockWidget(self.loggingDock, self.myDock)` + `install_tab_only_chrome(self.myDock)` if it joins the bottom tab group), `switchMyDock`, and extend `onDesignWindowClose` (`:289-295`).
3. `qt/main_window.py` `initUI` (`:142-148`): call `self.createMyDock()` after `createDataPreviewDock()`. `createMdiChild` (`:487-538`) wires per-window scene hooks (`scene.addItemSelectedListener`, `addNodeEvaluatedListener`, `executionResultsChanged`); `onSubWindowActivated` (`:540`) calls `switchXxxDock`.
4. Menu: `MainWindowMenuMixin.updateWindowMenu` (`main_window_ui_mixin.py:103-160`): `action = self.myDock.toggleViewAction(); action.setText("My Dock"); self.windowMenu.addAction(action)` (Data Preview also sets shortcut `Ctrl+Shift+D`).
5. Layout persistence: `layout_state.apply_default_layout` (`layout_state.py:225-250`) lists docks by attribute name; add `("myDock", area)` there.
6. Theming: implement `apply_theme()`; `TriggerWindow.apply_appearance` (`main_window.py:293-330`) calls `apply_theme` on children and explicitly on `loggingDock`/`dataPreviewDock`.
7. Tests: instantiate `TriggerWindow()`; `window.show()`; `window.onFileNew()`; see `tests/ui/test_data_preview_wiring.py`.

There is currently **no menu action for Run** (only the canvas overlay button). A "Run" menu/CLI entry must call `TriggerSubWindow.run_workflow()`.

---

## 6. Undo/redo contract

### 6.1 Moving parts (`qt/undo/`)

* `TriggerSceneHistory` (`history.py`) replaces the library's `SceneHistory`; owns an `UndoController` (`controller.py`, a `QUndoStack`, limit 200 steps, macro support). `scene.history.undo()/redo()/canUndo()/currentText()/push_edit(cmd)/storeHistory(...)/restoring(is_undo=...)`.
* Commands (`commands.py`): `PropertyChangeCommand(node, path, old, new, text, rebuild=False, merge_key=None)`, `ListStructureCommand(...)` (always rebuilds), `SceneSnapshotCommand` (whole-scene stamps; used by `storeHistory`). `path` is a tuple resolved by `set_in` on the **content** widget; segments may cross attribute -> dict keys (`("changes","rename_mapping")`).
* Every command's `undo()/redo()` -> `_guard(...)` -> `_restore(value, rebuild)` -> `_apply` (writes model) then **`sync_from_model(content, rebuild=...)`** (`protocol.py:99-140`): inside `syncing(content)` it calls `_rebuild_widgets()` (if `rebuild`) then `_sync_widgets_from_model()`, then (unless the history is restoring) `content.evaluate.emit()` so the graph re-evaluates.
* `UndoController.push` folds a command into the tip when `tip.can_merge_with(edit)` (same `merge_key`, same path, same node, at the tip) - **no `mergeWith`** (`controller.py:50-79`). A folded push returns `False` and `redo()` is **not** invoked -> you must `evaluate.emit()` yourself on every user edit (see 6.3).
* The first `storeHistory` stamp is a baseline, not an undo step (`history.py:110-118`).

### 6.2 `TriggerContentUndoMixin` (`qt/helpers/content_undo_mixin.py`, inherited via `TriggerChangeHandler`)

| Helper | Signature | Use |
|---|---|---|
| `push_property_change` | `(path, old, new, text, *, rebuild=False, merge_key=None) -> bool` | one setting (dtype, mode, a selected column, a spin value) |
| `push_list_change` | `(path, old, new, text, *, merge_key=None) -> bool` | a collection whose *size* changes (rows/sections); always rebuilds widgets on restore |
| `registerInputWidget` | `(widget, text=None, immediate=None, debounce_ms=None, merge_key=None) -> bool` (`node_base.py:446`) | opt a control into the **snapshot** binding (history label `text` defaults to `"Modified <Title>"`); debounce 300 ms for text, immediate for spin/combo/button |
| `recursively_find_widgets(layout)` | registers every trackable widget (called at the end of many `create_layout`s) | snapshot fallback |
| `sync_from_model` | `(rebuild=False, evaluate=True) -> bool` | call after you mutate the model outside a command |
| `_sync_widgets_from_model()` / `_rebuild_widgets()` | override | refresh values in place / recreate structure; both default to no-ops |
| `history_stamp_callback` | default -> `sync_from_model()` | **do not override in new code** |

Guards: `is_syncing(content)` (`protocol.py:47`), `is_suspended(content)`, `scene.history.is_restoring_history` (depth counter; use `with history.restoring(is_undo=...)` - never assign the flag), `syncing(content)` context manager around any model->widget write (`protocol.py:72`). A widget signal handler must `return` early when `is_syncing(self) or self.history.is_restoring_history`.

### 6.3 Canonical wiring pattern (copy this)

From `Join/union.py:608-624` (mode) and the Head skeleton (`_on_row_limit_changed`):

```python
def _on_x_changed(self, value):
    if is_syncing(self) or self.history.is_restoring_history:   # guard 1
        return
    old = self.x
    if value == old:                                            # real diff only
        return
    self.x = value                                              # 1. mutate the model
    self.refresh_dock_context()
    self.evaluate.emit()                                        # 2. re-evaluate (needed because merged pushes skip redo())
    self.push_property_change(("x",), old, value,               # 3. record ONE step
                              "Noun Verbed", merge_key="node-x")  # merge_key only for bursts (typing/spin)
def _sync_widgets_from_model(self):                             # runs inside syncing(): blockSignals + write if different
    w = self.x_widget
    if w is not None and w.value() != self.x:
        w.blockSignals(True); w.setValue(self.x); w.blockSignals(False)
```

Union adds two more shapes: collections (`push_list_change(("column_map",), old, new, "Union Column Added")` + `_rebuild_widgets`) and debounced grids (`QTimer` 300 ms -> `_commit_mapping`). Mark composite sections `widget._undo_composite = True` so `registerUnboundDockWidgets` does not also bind their children (`union.py:342-349`).

Worked, tested examples: Head skeleton (3.8; test `test_skeleton_b_ui.py` shows edit -> undo -> redo -> force rebuild), `union.py`, `filter.py:889` (`merge_key="filter-expression"`), `select.py:413-424`, `groupby.py:397-410` (`rebuild=True`).

### 6.4 Pitfalls (AGENTS.md + observed)

* Writing widgets from the model **outside** `syncing()` re-records the change; the user then cannot undo past it.
* Do not rebuild the dock manually; undo already calls `onHistoryRestored -> refreshConfigDock(force=True)` for snapshots and `sync_from_model` for commands.
* A node with no explicit registration is still tracked (snapshot) by the dock sweep; if you push commands yourself **and** the sweep also binds the same widget you get two history entries - either mark the widget/section `_undo_composite = True` or call `clearInputWidgets()` (formula does).
* `merge_key` per control; sharing a key across controls merges unrelated edits. Do not pass it for discrete clicks.
* Selection is UI state, not document state: after a snapshot restore `onHistoryRestored` falls back to `ConfigDock.currentNode()` rather than blanking.
* Never raise from `undo/redo` (Qt aborts the process); never implement `mergeWith`; `QScrollArea`, not `QAbstractScrollArea`.
* `evaluate.emit()` inside `sync_from_model` is suppressed while `is_restoring_history`; `onHistoryRestored` itself calls `doEvalOutputs()`.
* New data that lives **outside** `content` (edge order in Union, node label) is not covered by `path` commands; use `history.storeHistory(...)` (snapshot) as `union._move_input` does.


---

## 7. Data I/O

### 7.1 File Input (`qt/widgets/nodes/InOut/file_input.py`)

| Aspect | Behaviour (verified) |
|---|---|
| Node | `TriggerNode_FileInput` `:886`, no inputs, one output `[3]`; `__init__` calls `self.eval()` then `markInvalid(True)` (`:894-897`). |
| Types | Detected from the extension by `_auto_detect_file_type` (`:468`): `.xlsx/.xls` -> `"excel"`, `.txt` -> `"txt"`, everything else -> `"csv"`. Browse filter offers csv/txt/xlsx/xls (`:432-438`). **No** parquet/json/ndjson/ipc input, no folder/glob/multi-file input, no encoding, quote, null-value, skip-footer or date options. |
| Persisted state | `serialized_state_schema` `:46-58`: `filePath, file_type, record_limit (0 = no limit; no UI), output_filename_as_field, delimiter, first_row_contains_field_names, selected_sheet, available_sheets, start_row, schema_snapshot (list of {name,dtype}), file_metadata ({size_bytes, modified_time})`. |
| CSV live | `_scan_csv_full` `:632-650`: `pl.scan_csv(path, infer_schema=False[, separator=...][, has_header=False])` -> **every column is `String` by design** (README/handoff: "File Input now reads CSV as strings on purpose"); `record_limit` -> `.head(n)`; `output_filename_as_field` -> `with_columns(pl.lit(basename).alias("FileName"))`. Numeric work needs `TRY_CAST` in Formula (see `tests/e2e/workflows/*.tds`). |
| CSV codegen | `get_code` `:739-841`: same scan with `{self.filePath!r}` (safe repr) but `separator='{self.delimiter}'` and `idx_or_name='{self.selected_sheet}'` are **unescaped string interpolations** (a `'` or `\` in a delimiter/sheet name breaks the generated code). Delimiter UI accepts `\t`, `\n`, `\r` escapes (`:273-284`). |
| Excel | `fastexcel.read_excel(path).load_sheet(idx_or_name=<sheet>, header_row=<start_row-1 or None>, skip_rows=..., n_rows=<record_limit>)` -> `.to_polars()` (fallback `pl.from_arrow(...)`) -> `.lazy()`; **eager read of the whole sheet** both live (`_read_excel` `:567`, despite "preview" in its name) and in Run; dtypes are *inferred by fastexcel* (unlike CSV). Sheet list via `fastexcel` (`_show_sheet_selection_dialog` `:481`). Fallback `pl.read_excel(path, sheet_id=0)` if fastexcel fails. |
| Missing file | `check_file_path` `:307-325`: tooltip `File '<path>' does not exist`, `markInvalid(True)`, empty frame; logs at most 5 retries per path (`max_missing_file_attempts`). `processInputs` `:905-928` returns `None` -> downstream shows "upstream node produced no output". |
| Load-time drift check | `validate_loaded_state` `:365-427` **re-reads the file** and diffs against `schema_snapshot` (missing/new columns, dtype changes, missing Excel sheet) -> messages -> Logging dock + one `QMessageBox.warning` (`design_window.py:492-508`). `serialize()` also **re-reads the file** (`_refresh_saved_input_metadata`, `:843-845`) so saving is I/O-bound on large inputs. |
| Dock | `create_layout` `:131-241`: path `QLineEdit` + browse `IconButton` (`FormRow(... action=loadButton)`), settings section hidden until a file is set. Controls registered with `registerInputWidget` (snapshot undo). |

**Where absolute paths live (all must be handled by plans 01/02/08):** `.tds` `content.filePath` of every File Input and File Output; `schema_snapshot`/`file_metadata`; generated code (`{path!r}` literals), hence `check_output.py`; recent files list and `layout/session_files` in `preferences.ini`. The e2e harness rewrites `filePath` in a copy of the `.tds` before loading (`tests/support/workflows.py:50-75`) - the same technique a CLI `--input name=path` override needs. There is **no** relative-path resolution, no path variables, no content hash.

### 7.2 File Output (`.../InOut/file_output.py`)

* Node `[1] -> []` (no outputs). Content state: `filePath, file_format, delimiter, use_streaming, include_bom` (`serialize` `:351-358`; `compression` attr exists, unused; `use_streaming` and `include_bom` are stored but there is **no UI for bom/compression** and `use_streaming` does not change the code).
* Formats (`formatCombo` `:94`): `csv, excel, parquet, json, ndjson, ipc, custom_delimited`; auto-selected from the extension in `_on_filePathEdit_textChanged` (`:137-154`).
* `get_code` `:231-349`: raises `ValueError('File Output: no incoming data - connect an input')` when unwired (Run fails loudly); otherwise wraps `{var}_lazy = var.lazy() if DataFrame` and writes inside `try/except Exception: print('[ERROR] ...'); raise`: csv/custom -> `sink_csv(path[, separator=..., include_bom=True])`; parquet -> `sink_parquet(path, compression='snappy')`; ndjson/ipc -> `sink_ndjson/sink_ipc`; **excel/json -> `collect().write_excel/write_json`**. Path is forced to forward slashes (`:242`) because a raw `\U` broke the generated `print`. Prints `[SUCCESS] ...` (stdout is captured into `ExecutionResult.output`, never shown). **No row count, no file hash, no overwrite protection, no parent-directory creation.**
* `check_file_path` (`:181`) validates the parent dir but **is never called** (grep: only the definition). A bad directory is discovered at Run time as a Polars error.
* `processInputs` (`:409-427`) marks valid when an input exists and stores `incoming_variable`; it does not touch the data.

### 7.3 Save / load of `.tds`

* Extension/filter `Design (*.tds);;All Files (*)` (vendored `NodeEditorWindow.getFileDialogFilter`). `onFileSave/onFileSaveAs` -> `NodeEditorWidget.fileSave` -> `scene.saveToFile` (section 3.5). Older samples under `savedfiles/` and `tests/e2e/workflows/` are **v1** (no `op`, no `workflow_metadata`, `node_code` ints) and still load via `migrate_v1_data`; some are named `.json` but are the same format.
* Load: `TriggerWindow.openFile` (`main_window.py:385-405`) -> `TriggerSubWindow().fileLoad(path)`; on success `createMdiChild` + `_record_recent(path)`.
* Recent files: `RecentFilesManager` (`helpers/recent_files.py`): key `recentFiles` in `preferences.ini` (absolute, normalised, newest first, cap `general/recent_limit` default 10, max 50), `show_welcome_dialog` flag.
* Session restore: `layout/session` (default **False**) + `layout/session_files` + `layout/session_active` (`layout_state.py:30-34, 174-215`).

### 7.4 Preferences storage (`qt/preferences.py`)

* One INI via `QSettings(IniFormat)`: `%APPDATA%\Trigger Designer\preferences.ini`; override the directory with env `TRIGGER_DESIGNER_DATA_DIR` (tests do). User themes in `<dir>\themes`. First run migrates three legacy `QSettings` registry scopes (`:36-40`).
* API: `from trigger_designer.qt.preferences import get_preferences`; `prefs = get_preferences()`; `prefs.get("section/key", default)` (typed by the default's type: bool/int/list, `_coerce` `:94-110`), `prefs.set(key, value)` (emits `changed(str, object)`), `prefs.contains/remove/reset(prefix)`. `DEFAULTS` (`:42-56`) documents known keys.
* **Add a key:** (1) add `"area/name": default` to `DEFAULTS` (type of the default drives coercion); (2) read with `get_preferences().get("area/name")`; (3) UI: `dialogs/preferences_dialog.py` pages `_build_appearance_page / _layout / _editor / _node_editor / _general` (`:153, 227, 273, 348, 392`), load in the dialog's init (`:454` shows the pattern: `self.grid_size_spin.setValue(int(self._prefs.get("editor/grid_size", 20) ...))`) and write in a slot (`:638`). Do **not** create other `QSettings` scopes (DESIGN_SYSTEM §7). Qt-free code (core/CLI) should not import `qt.preferences`; pass paths in explicitly, or read `app_data_dir()` (Qt-light function but the module imports `qtpy.QtCore`).
* Suggested new keys (plans): `audit/run_log_dir`, `audit/record_runs` (bool), `audit/hash_inputs` (bool), `export/workpaper_dir`.

### 7.5 Logging

* **loguru** is configured at *import time* of `trigger_designer/main.py` (`_configure_logging` `:97-146`): removes default sink; adds stderr sink and a file sink, both `DEBUG`, format `{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{function}:{line} - {message}`; also tees `sys.stdout/sys.stderr` into the same file (`_TeeStream`, ANSI stripped).
* Log directory (`_log_dir` `:83-94`): dev = `<repo>/logs/`; frozen/briefcase = `%APPDATA%\Trigger Designer\logs` (fallback `~/.trigger_designer/logs`). File name `trigger_designer_<YYYY-MM-DD_HH-MM-SS>.log`, **one per launch, never rotated or pruned** (dozens sit in `logs/`; untracked).
* Because the configuration lives in `main.py`, **tests and any headless entry point get loguru's default stderr DEBUG sink** (that is the noise in pytest output) and no file. A CLI should configure its own sink (`logger.remove(); logger.add(...)`) and must not import `trigger_designer.main`.
* **Logging dock** (`qt/docks/logging_dock.py`): in-memory, per design-window (`logs_per_window[str(id(window))]`, last 1000 entries), level combo, text filter, auto-scroll, clear; refreshed by a 100 ms `QTimer`. Fed by `TriggerSubWindow.log(level, message)` (`design_window.py:565-596`: `logInfo/logWarning/...`) and by `global_logger.info(...)` which routes to the active window. **Not persisted**, not thread-safe (executor logs from its worker thread). `docs/LOGGING_DOCK_README.md` / `GLOBAL_LOGGING_README.md` describe it.
* Many nodes log verbosely with emoji (`count_records.py`, `file_input.py` use `logger.info/global_logger.*` in hot paths); do not copy that style. `tests/ui/test_no_console_prints.py` guards against stray `print`.

---

## 8. Errors today

### 8.1 Where exceptions are caught/surfaced

| # | Site | Line refs | What is caught | Surfaced as |
|---|---|---|---|---|
| E1 | `TriggerNode.eval` | `node_base.py:892-900` | `ValueError`; any `Exception` | `markInvalid()`, canvas tooltip = `str(e)`, `dumpException(e)` (stderr traceback; **not** in the Logging dock). `ValueError` also `markDescendantsDirty()`. Returns `None`. |
| E2 | `TriggerNode.evalImplementation` | `:816-852` | none; handles `None` returns | "Input {i} is not connected" (`:823`) - also shown when the input *exists but is invalid*, e.g. upstream failed (**misleading**); "Input {i}: upstream node produced no output" (`:831`); "Invalid operation" (`:842`) |
| E3 | Per-node `processInputs` | e.g. `select.py:1953-1965`, `groupby.py:994-1002`, `count_records.py:240-267`, `transpose.py:476-503`, `Append.py:248`, `join.py:1516,1547`, `union.py:876-930`, `running_total.py:327-334`, `split.py:517,550`, `file_input.py:908`, `file_output.py:417` | node-specific `try/except Exception as e` (86 `except Exception` in `nodes/`) | tooltips such as `Processing error: {e}`, `Input is not connected` (generic fallback used for **any** falsy input), `Both inputs must be connected`, `Append failed (...). Try 'diagonal_relaxed'.`, `Count failed: no output generated`, `Transpose failed ...`. 68 `setToolTip` sites; wording is inconsistent. |
| E4 | `FileInputContent.check_file_path` / `validate_loaded_state` | `file_input.py:307-325, 365-427` | missing file / schema drift | tooltip + `markInvalid`; load-time warnings dialog |
| E5 | `FileOutputContent` | `file_output.py:181-198` (unused), generated code `:243-347` | write errors inside generated `try` | `print('[ERROR] ...')` then re-raise -> E7 |
| E6 | `NodeExecutor._execute_with_timeout` | `executor.py:259-269` | any `Exception` in `exec` -> `exception_container` | handed to E7; timeout -> `ExecutionTimeoutError` (`:283`) |
| E7 | `NodeExecutor.execute_node` | `:340-348, 378-388` | `ExecutionMemoryError`, `ExecutionTimeoutError`, `NodeExecutionError(str(exc), original_exception=exc)`, generic | `result.success=False`, `result.error = str(e)` (+ `"\n\nOriginal traceback:\n" + traceback.format_exc()` when `original_exception` is set); `logger.error`; `_report_missing_dependency` logs `NameError`/`FileNotFoundError` up to 5x |
| E8 | `WorkflowWorker.run` | `workflow_worker.py:53-60` | `Exception` escaping `execute_node` (`# pragma: no cover`) | `nodeErrored(node, exc)`; run stops |
| E9 | `_on_node_finished` (fail) / `_on_node_errored` | `workflow_execution_mixin.py:106-123` | n/a (slots) | `logger.error` + `global_logger.error(f"Node execution failed for '{title}': {error}")` (Logging dock), `markInvalid()`, red ring. **No canvas tooltip is set**, so the node does not say why it failed. |
| E10 | `run_workflow` | `design_window.py:690-696` | `Exception` from `executeWorkflow` (e.g. cycle) | `logError` then **re-raise** (button already disabled, see 4.2) |
| E11 | Load | `design_window.py:433-459`; vendored `node_scene.py:640-660`, `node_editor_widget.py:133-158`; `validateConnections :510-539` | `FileNotFoundError`, `InvalidFile` -> `QMessageBox.warning`; other exceptions swallowed by `dumpException`; invalid edges removed with `logWarning` | dialog / Logging dock |
| E12 | Validation | `validateLoadedWorkflow :461-490` | `TriggerNode_Unknown`, per-content `validate_loaded_state()` | `logWarning` + one `QMessageBox.warning` (first 8 messages) |
| E13 | Config Dock | `node_config.py:106-110, 164-166` | `create_layout` failure | `traceback.print_exc()` + blank panel (silent to the user) |
| E14 | Preview | `qt/models/preview_worker.py`, `data_preview_panel.py` | collect failures | panel status text; see DESIGN_SYSTEM §5 |
| E15 | Formula/Filter SQL editor | `sql_formula_editor.py` (sqlglot/DuckDB diagnostics), `formula.py:802` `QMessageBox.warning(parent, "Add Column", error)` | parse/bind errors | inline underline + one dialog |
| E16 | Main entry | `main.py:196-197, 216-220, 244-245` | warm-up, theme, welcome failures | `logger.debug/error/warning` only |

### 8.2 How node error state and tooltips are set

* State = `markInvalid(True)` (red status badge from `status_icons.png`) and `markDirty(True)`; message = `grNode.setToolTip(text)` (use `node._set_node_tooltip(text)`: None-safe). `eval()` keeps a node's own tooltip when `processInputs` already set one (`:841-842`). Successful eval clears it (`:849`).
* Run failures colour the ring red (`setPenError`) and keep `isInvalid()` true until the next run clears it (`executeWorkflow` loop `:66-69`), but carry **no text on the node**.
* `ExecutionResult.error` is a single `str`. Typical contents: `NodeExecutionError` text is just `str(original)` such as Polars `ColumnNotFoundError: Column "x" not found`, DuckDB `Binder Error: ...`, `FileNotFoundError: [Errno 2] ...`, `NameError: name 'var_x_123' is not defined`, `Code execution timed out after 30.0 seconds`, `Memory usage exceeded limit: 612.00MB`. Plan 03 should key its translation table on `type(exc).__name__` + message regex over these.
* There is no error code, no severity other than valid/invalid, no link between a failing node and the Logging dock line.

---

## 9. Testing guide

### 9.1 Layout

```
tests/
  conftest.py              session QApplication (autouse), TRIGGER_DESIGNER_DATA_DIR temp dir, QT_QPA_PLATFORM=offscreen,
                           layer markers by directory, --run-benchmarks, fixtures: clean_preferences, theme_manager, no_modal_dialogs,
                           autouse _no_leaked_qt_windows (deleteLater + sendPostedEvents(DeferredDelete); resets GlobalLogger window)
  support/                 corpus.py (WorkflowCase table), workflows.py (materialize, run_workflow_and_wait, executed_frame, nodes_titled),
                           frames.py (read_frame, assert_frames_match, assert_frame_golden), qt_widgets.py (dispose_plot_widget), ...
  unit/                    pure logic + node classes built in a TriggerSubWindow (no real shown windows)   - 334 tests
  ui/                      offscreen widgets via pytest-qt (docks, dialogs, canvas)                       - 431 tests (27 baseline failures)
  e2e/                     test_workflow_goldens.py, test_graph_run.py, test_undo_integration.py;
                           workflows/*.tds (locally owned), fixtures/expected/*.csv (13 goldens)          - 20 tests
  benchmarks/              skipped without --run-benchmarks
  manual/                  *_demo.py scripts (not collected)
```

* Existing files import `sys.path` hacks (`sys.path.insert(0, ".../src")`) and `os.environ.setdefault("QT_QPA_PLATFORM","offscreen")` at the top; `conftest.py` already does both, so new files can skip them. Many create `APP = QApplication.instance() or QApplication([])`; the session `qapp` fixture is autouse, so you rarely need to.
* Qt object lifetime rules (tests/README): `qtbot.addWidget` stores a weakref - keep the parent (`QMainWindow`) in a local variable until the test ends; use `TriggerSubWindow()` without a parent for e2e; hold the `QThread` until `wait()` returns (`run_workflow_and_wait`); no sleeping - use `qtbot.waitSignal/waitUntil`; one `QApplication` per process.
* **Node construction in tests:** `window = TriggerSubWindow(parent_or_None); node = get_class_from_opcode(<Enum>.X, NodeTypes.<F>)(window.scene)`. `Node.__init__` already appends to `scene.nodes`; several older tests `window.scene.nodes.append(node)` again (harmless duplicate; do not copy). Wire with `Edge(window.scene, src.outputs[i], dst.inputs[j])` (`nodeeditor.node_edge.Edge`); `Edge` triggers `onEdgeConnectionChanged` -> eval.
* Fixture data: `data/check.csv`, `data/check_1.csv`, `savedfiles/1. out_check.csv` etc.; `tests/support/frames.py` has no frame factories despite the name (just comparison helpers); build small frames inline with `pl.DataFrame(...).lazy()`.

### 9.2 (a) Unit test for a node's generated code and live/codegen agreement - verified skeleton

Pattern: build the node in a `TriggerSubWindow`, feed it with a stub `Source(TriggerNode)` that returns `[{"data": LazyFrame, "variable_name": "var_src"}]`, `eval()` it, then `exec(node.get_code(), {"pl": pl}, namespace)` with the upstream variable pre-seeded and compare the two frames. Real examples: `tests/unit/test_normalize_columns.py:60-84` (`exec` with `{"__name__": "__main__", "pl": pl}`), `tests/unit/test_batch_evaluation.py:22-40` (`Source`/`Sink` doubles).

```python
"""(a) Unit test for a node's generated code + live/codegen agreement."""

import polars as pl
from nodeeditor.node_edge import Edge
from qtpy.QtWidgets import QMainWindow

from trigger_designer.qt.design_window import TriggerSubWindow
from trigger_designer.qt.node_base import TriggerNode

from head_node import TriggerNode_Head


class Source(TriggerNode):
    """Test double: emits one LazyFrame the way a File Input does."""

    node_title = "Source"

    def __init__(self, scene, frame):
        super().__init__(scene, inputs=[], outputs=[3])
        self._frame = frame

    def evalImplementation(self):
        self.value = [{"data": self._frame, "variable_name": "var_src"}]
        self.markDirty(False)
        self.markInvalid(False)
        return self.value


def _graph(rows=10):
    parent = QMainWindow()  # keep a strong ref: qtbot/GC would delete children
    window = TriggerSubWindow(parent)
    frame = pl.DataFrame({"a": list(range(rows))}).lazy()
    src = Source(window.scene, frame)  # Node.__init__ already adds to scene.nodes
    node = TriggerNode_Head(window.scene)
    Edge(window.scene, src.outputs[0], node.inputs[0])
    return parent, window, src, node


def test_live_value_and_generated_code_agree():
    _parent, _window, src, node = _graph(rows=10)
    node.content.row_limit = 3
    node.markDirty(True)
    out = node.eval()
    assert out is not None and not node.isInvalid()

    live = out[0]["data"].collect()
    assert live.height == 3

    code = node.get_code()  # what Run Workflow exec()s
    namespace = {"var_src": src._frame}
    exec(code, {"__name__": "__main__", "pl": pl}, namespace)  # noqa: S102
    ran = namespace[out[0]["variable_name"]].collect()
    assert ran.equals(live)


def test_unwired_node_still_defines_its_output_variable():
    parent = QMainWindow()
    window = TriggerSubWindow(parent)
    node = TriggerNode_Head(window.scene)
    namespace = {}
    exec(node.get_code(), {"pl": pl}, namespace)  # noqa: S102
    assert node.content.variable_name in namespace


def test_state_round_trips_through_serialize():
    _parent, window, _src, node = _graph()
    node.content.row_limit = 7
    data = node.content.serialize()
    assert data["row_limit"] == 7
    node.content.row_limit = 1
    node.content.deserialize({"row_limit": 7})
    assert node.content.row_limit == 7
    # backward compatibility: a file written before the setting existed
    node.content.deserialize({})
    assert node.content.row_limit == 100
```

### 9.3 (b) UI test: open a node's Config Dock with pytest-qt - verified skeleton

Notes: `QT_QPA_PLATFORM=offscreen` comes from conftest. Instantiate `ConfigDock()` (it is a plain `QDockWidget`; no main window needed), pass **graphics nodes** (`node.grNode`) to `updateConfig`, find widgets via `dock.dock_widget.findChild(...)` (the dock's internal `QWidget`), call `history.storeHistory("Baseline")` once before testing undo (first stamp is the baseline, not a step), and use `force=True` to mimic `onHistoryRestored`. For full-window behaviour use `TriggerWindow()` + `window.show()` + `window.onFileNew()` (`tests/ui/test_data_preview_wiring.py:21-40`). To see `create_layout` exceptions (the dock swallows them) call `node.content.create_layout(QVBoxLayout(QWidget()))` directly (`tests/ui/test_select_bulk_ops.py:34-45`).

```python
"""(b) UI test: open the node's Config Dock, edit a control, undo/redo."""

import polars as pl
from qtpy.QtWidgets import QSpinBox

from trigger_designer.qt.docks.node_config import ConfigDock

from test_skeleton_a_unit import _graph


def test_dock_builds_edits_and_undoes(qtbot):
    parent, window, _src, node = _graph(rows=50)
    qtbot.addWidget(parent)  # weakref only: keep `parent` alive in this scope
    node.markDirty(True)
    node.eval()

    dock = ConfigDock()
    qtbot.addWidget(dock)
    # ConfigDock.updateConfig takes the *selected items*; a content-bearing
    # logic node is accepted too (it checks hasattr(node, "node") or "socket").
    # In the app the items are node.grNode; mirror that:
    dock.updateConfig([node.grNode])
    spin = dock.dock_widget.findChild(QSpinBox)
    assert spin is not None and spin.value() == 100

    history = window.scene.history
    history.storeHistory("Baseline")  # first stamp is the baseline, not a step
    spin.setValue(5)  # user edit
    assert node.content.row_limit == 5
    assert node.value[0]["data"].collect().height == 5  # live re-eval happened
    assert history.canUndo()

    history.undo()
    assert node.content.row_limit == 100
    assert node.value[0]["data"].collect().height == 50
    history.redo()
    assert node.content.row_limit == 5

    # force=True rebuilds the same selected node (what onHistoryRestored does)
    dock.updateConfig([node.grNode], force=True)
    assert dock.dock_widget.findChild(QSpinBox).value() == 5
    assert isinstance(node.value[0]["data"], pl.LazyFrame)
```

### 9.4 (c) Golden-file end-to-end workflow test

**How the corpus works** (`tests/support/corpus.py`, `workflows.py`, `frames.py`, `tests/e2e/test_workflow_goldens.py`):

1. `WorkflowCase(name, source, inputs, goldens, unordered_goldens)` (`workflows.py:22-39`): `source` = repo-relative `.tds/.json`; `inputs` maps the File Input **basename** in the file to a repo-relative sample (`{"check.csv": "data/check.csv"}`); `goldens` maps a **produced file basename** (what File Output wrote) to a golden **name**; `unordered_goldens` lists golden names compared after sorting by every column (hash joins).
2. `materialize(case, tmp_path)` (`workflows.py:50-75`) reads the workflow JSON, and for every node whose `content` has `filePath/file_path/outputPath/output_path` rewrites File Input paths to the checked-in fixtures and File Output paths to `tmp_path/out/<basename>`, writes `tmp_path/<case>.tds`. Node kind is detected by `op` suffix `file_input/file_output` **or** title `"File Input"/"File Output"` (v1 files have no `op`).
3. `_open_case` (`test_workflow_goldens.py:39-54`): `TriggerSubWindow()`, `qtbot.addWidget`, `window.fileLoad(path) is True`, `validateLoadedWorkflow() == []`, no dialog warnings (`no_modal_dialogs["warnings"] == []`).
4. `run_workflow_and_wait(qtbot, window)` (`workflows.py:78-99`): waits on `executionResultsChanged` around `window.executeWorkflow()`, then `worker.wait()` and `sendPostedEvents(DeferredDelete)`.
5. Assertions: `_assert_run_clean` (every node has an `execution_results` entry, none invalid); each produced file read with `read_frame` (**CSV is re-inferred**, pandas index columns dropped) and compared with `assert_frame_golden(frame, golden_name, sort_by=...)` against `tests/e2e/fixtures/expected/<golden>.csv` using `polars.testing.assert_frame_equal(check_dtypes=False, check_column_order=True, check_row_order=True)`. Also assert `no_modal_dialogs["run_code"]` is non-empty (the run reached `getPyFile`).
6. Property checks live next to a golden (`test_running_total_frame_is_cumulative_per_keyword`) using `executed_frame(window, node, index)` which maps `node.value[index]["variable_name"]` to `window.execution_results[node]`.
7. **Regenerate goldens:** PowerShell `$env:TRIGGER_UPDATE_E2E_GOLDENS="1"; .venv\Scripts\python.exe -m pytest tests\e2e; Remove-Item Env:TRIGGER_UPDATE_E2E_GOLDENS` - rewrites **every** golden (`frames.py:84-88`); review `git diff tests/e2e/fixtures/expected`.
8. **Add a corpus case:** save a workflow from the app (or build one programmatically as below) into `tests/e2e/workflows/<name>.tds`; add `WorkflowCase(...)` to `FILE_OUTPUT_CASES` in `corpus.py`; regenerate goldens; read the diff. Because File Input reads CSV as strings, numeric nodes in a workflow need an explicit cast (comment at `corpus.py:1-28`).
9. Checked-in workflows were authored on other machines: absolute paths do not exist here. Always go through `materialize`. A workflow **built inside the test** (below) uses `tmp_path` directly and needs no materialisation.

The skeleton builds File Input -> Normalize -> File Output in code, saves a `.tds` with `scene.saveToFile`, reloads it in a fresh window, runs, and checks the output two ways (inline frame; golden helper pointed at a temp dir).

```python
"""(c) End-to-end: build a workflow, save it as .tds, reload, Run, compare.

For a *checked-in* workflow instead of a programmatic one, add a WorkflowCase
to tests/support/corpus.py (see the brief) and let
tests/e2e/test_workflow_goldens.py parametrize over it.
"""

import polars as pl
import pytest
from nodeeditor.node_edge import Edge

from tests.support import frames
from tests.support.frames import assert_frame_golden, assert_frames_match, read_frame
from tests.support.workflows import run_workflow_and_wait
from trigger_designer.core.node_configuration import (
    IONodes,
    NodeTypes,
    PreparationNodes,
    get_class_from_opcode,
)
from trigger_designer.qt.design_window import TriggerSubWindow

pytestmark = pytest.mark.e2e


def _build_tds(tmp_path):
    src = tmp_path / "in.csv"
    src.write_text(" Order ID ,Customer Id\n1,a\n2,b\n", encoding="utf-8")
    out = tmp_path / "out" / "result.csv"
    out.parent.mkdir()

    window = TriggerSubWindow()
    scene = window.scene
    fin = get_class_from_opcode(IONodes.FILE_INPUT, NodeTypes.IO)(scene)
    norm = get_class_from_opcode(
        PreparationNodes.NORMALIZE_COLUMNS, NodeTypes.PREPARATION
    )(scene)
    fout = get_class_from_opcode(IONodes.FILE_OUTPUT, NodeTypes.IO)(scene)

    # Absolute paths end up in the .tds (see brief, section 7). Tests use tmp.
    fin.content.filePath = str(src)
    fin.content.file_type = "csv"
    fout.content.filePath = str(out)
    fout.content.file_format = "csv"

    Edge(scene, fin.outputs[0], norm.inputs[0])
    Edge(scene, norm.outputs[0], fout.inputs[0])

    tds = tmp_path / "wf.tds"
    scene.saveToFile(str(tds))  # orjson, indent 2; same call the Save action makes
    window.close()
    return tds, out


def test_programmatic_workflow_runs_and_matches_expected(
    qtbot, tmp_path, no_modal_dialogs, monkeypatch
):
    tds, out = _build_tds(tmp_path)

    window = TriggerSubWindow()  # no parent QMainWindow: qtbot keeps a weakref only
    qtbot.addWidget(window)
    assert window.fileLoad(str(tds)) is True  # deserialize + validate + evaluate
    assert window.validateLoadedWorkflow() == []

    run_workflow_and_wait(qtbot, window)  # real WorkflowWorker thread

    assert len(window.execution_results) == len(window.getAllNodes())  # all green
    frame = read_frame(out)  # CSV -> DataFrame (drops pandas index columns)

    # 1) inline expectation
    # read_frame() re-infers CSV dtypes, so numbers come back as ints
    expected = pl.DataFrame({"Order_ID": [1, 2], "Customer_Id": ["a", "b"]})
    assert_frames_match(frame, expected)  # dtypes ignored, row order checked

    # 2) frozen golden. Point GOLDEN_DIR at a temp dir for this demo; in the repo
    #    leave it alone (tests/e2e/fixtures/expected) and regenerate with
    #    TRIGGER_UPDATE_E2E_GOLDENS=1.
    monkeypatch.setattr(frames, "GOLDEN_DIR", tmp_path / "golden")
    monkeypatch.setenv(frames.UPDATE_ENV, "1")
    assert_frame_golden(frame, "demo")  # writes tmp/golden/demo.csv
    monkeypatch.delenv(frames.UPDATE_ENV)
    assert_frame_golden(frame, "demo")  # now compares
```

How the three skeletons were verified (and how to run your own copies from outside `tests/`):

```powershell
$S = "<dir containing head_node.py and test_skeleton_*.py>"
$env:PYTHONIOENCODING = "utf-8"; $env:PYTHONPATH = "$S;$PWD"
.venv\Scripts\python.exe -m pytest -c pyproject.toml --rootdir . -p tests.conftest "$S\test_skeleton_a_unit.py" "$S\test_skeleton_b_ui.py" "$S\test_skeleton_c_e2e.py" -q -p no:cacheprovider
# -> 5 passed
```

Inside the repo just place them under `tests/unit`, `tests/ui`, `tests/e2e`, delete the `-p tests.conftest` and the `from head_node import ...` (import your real node), and they pick up `conftest.py` automatically. Expect harmless noise: loguru DEBUG lines, `datetime.utcnow()` DeprecationWarning (`performance_scene.py:171`), `setPositions` AttributeError tracebacks on edge load, `Cannot open file ':Input/Output/...'` Qt warnings.

### 9.5 Other patterns worth reusing

* Run without a thread: `WorkflowWorker(nodes, NodeExecutor()).run()` executes synchronously (docstring `workflow_worker.py:11-14`); `tests/unit/test_workflow_execution_mixin.py` drives the mixin directly.
* Undo integration: `tests/e2e/test_undo_integration.py`, `tests/unit/test_undo.py` (789 lines), `test_undo_node_scenarios.py`.
* Serialization round-trip incl. subprocess: `tests/unit/test_workflow_serialization.py`.
* Preferences/theme isolation: `clean_preferences`, `theme_manager` fixtures.
* Memory/perf: `tests/benchmarks/` + `--run-benchmarks`.

---

## 10. Cross-cutting design guidance

### 10.1 Conventions every plan must follow

* **Qt-free core first.** Anything computable without widgets (translation tables, run-record dataclasses, profile maths, test-criteria logic, input resolution, workpaper building) goes in `src/trigger_designer/core/<area>/...` and imports only stdlib + polars (+ loguru). Qt widgets, docks and node classes stay in `qt/`. `core/ExecutionCheck/executor.py` already breaks this (imports `qt.helpers.global_logger`); do not add more. Core modules must be importable without `QApplication` (pattern: `core/utils/dtype_utils.py`, `qt/models/preview_sampling.py`).
* **Naming.** Modules `snake_case.py`; node classes `TriggerNode_<Name>` + `<Name>Content`; enum members `UPPER_SNAKE` (the lowercase form becomes the persisted op id); variables in generated code `var_<kind>_<id>` / `_<kind>_tmp_<id>`; objectNames `PascalCase` (`ConfigSection`), node label objectName `trigger_node_<name>`; history text `"Noun Verbed"`; icon ids `node_<name>` / `icon_<verb>`; preference keys `area/snake_case`.
* **Dependencies.** No new heavy dependency without justification in the plan. Already available: polars, duckdb, pyarrow, orjson, fastexcel, openpyxl (declared, currently unused), click (declared, unused), psutil, loguru, matplotlib, pillow. Known gap: **xlsxwriter** (required by `write_excel`) - plan 06 must declare it in `pyproject.toml` (and `trigger.spec` hidden imports if needed). Anything that touches `pyproject.toml`/`uv.lock` must also respect the "do not `uv sync`" note and be installed with `uv pip install --python .venv/Scripts/python.exe <pkg>==<ver>` after `uv lock --upgrade-package`.
* **Lazy first, collect deliberately.** Keep live and generated code on `LazyFrame`; use `frame_schema()` for names/dtypes; a node that must count or test rows collects *inside its own `get_code()`* (as Count does) and says so in its docstring. Never collect in `create_layout` or on selection.
* **Strings in, casts explicit.** CSV columns arrive as `String`; audit tests/profile must cast with `strict=False` (`pl.col(c).cast(pl.Float64, strict=False)`) and report cast failures rather than crash.
* **Idempotent `get_code`**, always defining outputs (3.4). Escape user text embedded in generated code with `!r` (never `'{x}'`).
* **State** via `serialized_state_schema` with defaults (backward compatible); new top-level `.tds` keys only inside `workflow_metadata`.
* **Undo** per section 6; **dock UI** per section 5 and DESIGN_SYSTEM; no inline QSS; no new `QSettings` scopes.
* **Tests**: unit for Qt-free logic, ui for docks, e2e golden for anything that writes a file; verification commands name layers (never bare `pytest`).
* **Run/Run-log invariants**: do not change `getSocketData`, `_prune_node_results`, `execution_results` shapes; extend `ExecutionResult` only by *adding defaulted fields*.

### 10.2 Error-code naming scheme (proposal for plan 03; consumed by 02/04/08)

`TD-<AREA>-<NNN>` (stable, never reused, documented in one table in the package `core/errors/`, `catalogue.py`; plan 03 owns it):

| Area | Meaning | Examples (seed list) |
|---|---|---|
| `IN` | input files / reading | `TD-IN-001` file not found, `TD-IN-002` no permission/locked, `TD-IN-003` sheet missing, `TD-IN-004` encoding/parse failure, `TD-IN-005` empty file |
| `SCH` | schema / columns | `TD-SCH-001` column not found (carry `columns`), `TD-SCH-002` duplicate column names, `TD-SCH-003` schema drift vs saved snapshot |
| `TYP` | types / casts | `TD-TYP-001` cannot convert text to number/date, `TD-TYP-002` incompatible join key types |
| `EXP` | formula/filter expression | `TD-EXP-001` SQL syntax, `TD-EXP-002` unknown function, `TD-EXP-003` binder error |
| `JOI` | join/append/union configuration | `TD-JOI-001` no mapping, `TD-JOI-002` both inputs required |
| `OUT` | output writing | `TD-OUT-001` folder missing, `TD-OUT-002` file open elsewhere, `TD-OUT-003` format not supported/xlsxwriter missing |
| `RUN` | execution environment | `TD-RUN-001` timeout, `TD-RUN-002` memory limit, `TD-RUN-003` upstream failed, `TD-RUN-004` cancelled |
| `TST` | audit test configuration | `TD-TST-001` no column chosen, `TD-TST-002` invalid threshold |
| `SYS` | unexpected/internal | `TD-SYS-999` fallback for anything unmatched (always keep `technical`) |

Severity: `error` (node fails/invalid) or `warning` (node ok, result needs attention). Code is the **stable key** for docs, tests and the audit log; the human sentence may be reworded freely.

### 10.3 How nodes should expose structured summary outputs

Precedent: **Count** returns a one-row frame (`{'Count': [n]}`) as an ordinary output socket - summaries are data, so they flow through the graph, are previewable, writable by File Output and exportable. Convention for new nodes (04, 05, 07):

1. Audit test nodes: output socket 0 = rows that **passed/all rows (passthrough)**, socket 1 = **exceptions** (full rows + a `__reason` column), socket 2 (optional) = a **one-row summary frame** with the `TestSummary` fields as columns. Name the summary variable `summary_variable_name` (content attr ending `_variable_name`, so `_declared_output_variable_names` (`workflow_execution_mixin.py:252-256`) keeps it after pruning; it is appended after `param` names, so socket indexes stay stable).
2. Also keep a Python-side object (`content.test_summary: TestSummary`) updated in live `processInputs` (cheap counts via one `select(pl.len(), ...)`; gate expensive ones behind an explicit button/option) so the dock and the run recorder can read it without re-collecting.
3. Profile node (05): one output = **long-form profile frame** (one row per column); the dock shows it with the existing table viewer.
4. Never mutate `ExecutionResult.output` text to carry results.

### 10.4 Technical debt / pitfalls (verified)

| Area | Finding |
|---|---|
| Security | `exec()` of generated code with full builtins/imports, one shared namespace for the whole run (`executor.py:262-264, 373`); user text is interpolated into code in many nodes (filter/formula expressions, delimiter, sheet name). Not a sandbox; `SecurityConfig` is time + RSS only. |
| Paths | Absolute paths in `.tds` (7.1); `getPyFile` writes `check_output.py` to CWD (`design_window.py:704`), file is git-tracked yet ignored (`.gitignore:295`); `run.bat` hard-codes `C:\Projects\TriggerEditor`; `scripts/build.bat`/`sync-nodeeditor.ps1` hard-code `C:\Projects\qtpy-nodeeditor`. |
| Stale docs **[STALE DOC]** | `SESSION_HANDOFF.md`: says "No pytest installed" (pytest 9.1.1 + pytest-qt are in the dev group and a ~785-test suite exists), lists as pending items already done (Batch B executor seeding is done: `executor.py:174`), says `Join/union.py` is a 0-byte stub (it is 956 lines, tested by `tests/unit/test_union_node.py`; only `find_replace.py` and `comment.py` are empty). `NODE_REFERENCE.md`: omits Union and claims it is unimplemented. `ENHANCED_EXECUTOR_GUIDE.md`: documents `allowed_imports`/forbidden functions that do not exist. `CONTRIBUTING.md`: `uv sync` (conflicts with the nodeeditor note), `tests/integration` is empty, "register the node in node_configuration.py" omits the lazy-spec/icon steps. `tests/README.md`: "< 20 s" full suite does not hold here (crashes). `docs/prompt_requirements.md` is an aspirational prompt, not a rule set. AGENTS.md claim about `registerInputWidget` (1.4). DESIGN_SYSTEM line references (`transpose.py:77` etc.) have drifted. |
| Empty/stub files | `qt/widgets/nodes/Documentation/comment.py`, `Join/find_replace.py`, `qt/tr_qt.py`, `qt/translations.py`, `docs/POLARS_MIGRATION_SUMMARY.md` (0 bytes), `docs/Nodes.md` (1 line). Enum members without a node: `IONodes.BROWSER`, `IONodes.TEXT_INPUT`, `TransformNodes.ARRANGE`. |
| Dead code | `qt/helpers/file_opener.py` (imports `structlog`, `tagstudio.*`; nothing imports it; being edited concurrently), `qt/models/model_pandas.py` (pandas legacy), `TriggerNode.evalOperation`, commented blocks in `node_base.py`, `design_window.test_execution_visuals`. |
| Cancellation | Not wired (4.2). Timed-out exec threads are abandoned, not killed. |
| Run button | Disabled before `topologicalSort`; a cycle exception leaves it disabled (`workflow_execution_mixin.py:57-61`; by reading, not reproduced). |
| `getSocketValue` | First-match semantics (3.3). |
| Live collect on GUI thread | Count/Formula/Cleansing/Select preview collect synchronously; large data freezes the UI. |
| Logging | Not thread-safe dock; log files never pruned; loguru configured only in `main.py`. |
| Excel | `write_excel` needs undeclared `xlsxwriter`; Excel read is eager and dtype-inferring while CSV is all-String. |
| Libraries | `qtpy-nodeeditor` outside the lock; installed commit older than repo needs (ui failures, `setPositions`, detail policy). `matplotlib` pulled at startup unless Graph module is lazy (guarded by `test_startup_import_sweep_keeps_the_chart_backend_out`). |
| Lint | `ruff check` baseline not clean (76 errors in `core/` alone); `ty` configured but unused in CI. |
| Undo | Mixed: modern commands (Union, Filter expression, Select toggles, GroupBy) vs legacy snapshot callbacks (Split, parts of Filter/Sort/Unique/Join); `registerInputWidget` = snapshot. |
| Misc | `datetime.utcnow()` deprecated (`performance_scene.py:171`); vendored `print('icon: ...')`/`print('STYLE loading')`/`print("name:", name)` noise; `loadFromFile` swallows exceptions; generic "Input is not connected" for an upstream failure; `LazyNodeReference` duplicates title/icon from the class (kept in sync by a test). |
| Flaky/known-failing tests | Teardown abort in full run; 27 ui baseline failures (2.4). Treat as environment baseline; do not "fix" by editing assertions. |

---

## 11. Dependency/ordering map between the eight features

### 11.1 Features and what they provide/consume

| # | Feature | Provides (shared interface) | Consumes | New node? | Touches |
|---|---|---|---|---|---|
| 01 | Input types | `ResolvedFile`, `resolve_input_files()`, `FileInputContent.resolved_input_files()`, new `file_type` values; safe path quoting; optional `FileFingerprint` | node recipe (3.7), `file_input.py` | no (extends File Input; maybe new Input-family nodes) | `file_input.py`, `core/inputs.py`, tests/e2e corpus |
| 02 | Audit trail / run log | `RunRecord`, `NodeRunRecord`, `FileFingerprint`, `RunRecorder`, `RunStore` | `NodeError` (03), `ResolvedFile` (01), `TestSummary` (04, optional), hooks H1/H2/H4/H5/H6 | no | `executor.py` (add fields), `workflow_execution_mixin.py`, new `core/audit/`, optional Logging/Run-log dock, preferences |
| 03 | Plain-language errors | `NodeError`, `translate_exception()`, error-code table | hooks H2/H8 | no | package `core/errors/`, `node_base.py`, mixin, `executor.py` (preserve exception) |
| 04 | Audit test nodes | `TestSummary`, node-family `Audit` (new `NodeTypes` member is *not* required: use `TRANSFORM`/`PREPARATION` or add a family per 3.1) | node recipe, summary-output convention (10.3), `NodeError` for config errors | **yes** (several) | `node_configuration.py`, `nodes/__init__.py`, new node modules, icons |
| 05 | Data profile node | `ColumnProfile`, `DataProfile`, `profile_frame()` | node recipe, 10.3 | **yes** | same as 04 |
| 06 | Workpaper export | `WorkpaperSpec`, `build_workpaper()` | `RunRecord` (02), `TestSummary` (04), `DataProfile` (05), xlsxwriter | maybe an Output-family node/menu action | `pyproject.toml`, `core/workpaper/`, File Output or menu |
| 07 | Shaping nodes | none (pure leaf nodes) | node recipe only | **yes** (several) | node modules, icons |
| 08 | CLI / scheduling | `run_workflow_file()` headless runner, `trigger-designer-cli` console script, exit-code contract | `ResolvedFile` (01), `RunRecord` (02), `NodeError` (03) | no | `pyproject.toml` `[project.scripts]`, new `cli.py`, `core/headless.py` |

### 11.2 Recommended implementation order (minimises rework)

0. **Prerequisite (tiny, no plan owns it):** declare `xlsxwriter`; decide Excel strategy. Optionally fix the first-class dev ergonomics (document the per-layer test commands). Owner: plan 06 or a pre-step.
1. **03 core** (package `core/errors/`: `NodeError`, `translate_exception`, seed table) + **01 core** (`core/inputs.py`: `ResolvedFile`, `resolve_input_files`) + **07** shaping nodes - mutually independent; run in parallel. 07 also validates the recipe cheaply.
2. **03 integration** (preserve exception on `ExecutionResult`, translate in H2/H8, tooltips on failed nodes) and **01 integration** (File Input uses resolver; `validate_loaded_state` uses it).
3. **02** audit trail (needs `NodeError` and `ResolvedFile` fields in its records).
4. **04** audit test nodes and **05** profile node (parallel; both need only the recipe; 04 should emit `TestSummary` that 02 can record, so build 04 after 02's `RunRecord` fields are frozen, but code against the dataclass names below).
5. **06** workpaper (needs `RunRecord`, `TestSummary`, `DataProfile`).
6. **08** CLI/scheduling last: it composes 01 (override inputs), 02 (record), 03 (exit codes/messages) and needs the headless runner; build the headless runner skeleton earlier only if 02 wants to test recording without a window.

Why this order: 03 and 01 define the two value types (`NodeError`, `ResolvedFile`) embedded in every `RunRecord`; if 02 went first it would define provisional copies and be reworked. 06 and 08 only compose.

### 11.3 Minimal stable shared interfaces (names and fields only; implement in the module shown, as frozen `@dataclass`es with defaults so adding a field later is non-breaking)

All JSON-serialisable via `dataclasses.asdict` + orjson; timestamps are ISO-8601 UTC strings; paths are `str` (POSIX-style separators not required); no Qt types.

**package `core/errors/` (plan 03; `from trigger_designer.core.errors import ...`)**

```text
NodeError
  code: str                      # "TD-<AREA>-<NNN>", see 10.2
  title: str                     # plain language, one line, <= 90 chars, no jargon
  detail: str                    # what happened, in context (node, column, file)
  hint: str                      # imperative next step
  technical: str                 # original str(exc) (kept for logs/support)
  exc_type: str                  # type(exc).__name__ ("" if none)
  severity: str                  # "error" | "warning"
  node_id: int | None            # TriggerNode.id
  node_title: str | None
  op: str | None                 # "preparation.filter"
  columns: tuple[str, ...]       # columns involved
  path: str | None               # file involved
translate_exception(exc: BaseException | str | None, *, node=None, phase: str = "run") -> NodeError   # never raises
```

**`core/inputs.py` (plan 01)**

```text
ResolvedFile
  path: str                      # absolute, as read
  exists: bool
  kind: str                      # "csv" | "txt" | "excel" | ... (the file_type value)
  sheet: str | None
  size_bytes: int | None
  modified_time: str | None
  sha256: str | None             # None unless requested
resolve_input_files(content_state: dict) -> list[ResolvedFile]       # content_state = FileInputContent.get_serialized_state()
FileInputContent.resolved_input_files(self, *, hash: bool = False) -> list[ResolvedFile]
```

**`core/audit/run_record.py` (plan 02)**

```text
FileFingerprint:  role ("input"|"output"), path, size_bytes, modified_time, sha256 | None, sheet | None, node_id | None
NodeRunRecord:    node_id: int, op: str, title: str, label: str | None,
                  status ("ok"|"failed"|"skipped"), started_at: str, duration_s: float,
                  rows_out: dict[str, int | None]       # output variable -> row count (None = not counted)
                  columns_out: dict[str, list[str]]     # output variable -> column names
                  peak_memory_mb: float, warnings: list[str],
                  error: NodeError | None, test_summary: TestSummary | None
RunRecord:        run_id: str (uuid4 hex), started_at, finished_at, status ("ok"|"failed"|"cancelled"),
                  app_version, workflow_schema_version: int, workflow_path: str | None, workflow_sha256: str | None,
                  user: str, machine: str, python_version: str, polars_version: str,
                  inputs: list[FileFingerprint], outputs: list[FileFingerprint],
                  nodes: list[NodeRunRecord], generated_code: str | None
RunRecorder:      begin(workflow_path, nodes, *, app_version) -> RunRecord
                  node_finished(record, node, execution_result, *, rows_out=None, test_summary=None) -> NodeRunRecord
                  finish(record, success: bool) -> RunRecord
RunStore:         save(record: RunRecord, directory=None) -> str (path)    # default <app_data_dir>/runs/<run_id>.json
                  load(path) -> RunRecord ; list_runs(directory=None, workflow_path=None) -> list[RunRecord header]
```

**`core/audit/test_summary.py` (plan 04)**

```text
TestSummary
  test_id: str                   # "<op>#<node_id>"
  test_name: str                 # human title of the test
  node_id: int | None
  status: str                    # "pass" | "fail" | "warn" | "error"
  population_rows: int | None    # rows tested
  exception_rows: int | None
  exception_rate: float | None
  criteria: str                  # one human sentence of what was tested
  parameters: dict[str, Any]     # the node settings used (JSON-safe)
  message: str                   # plain-language outcome
  exceptions_var: str | None     # generated-code variable holding exception rows
```

**`core/profile.py` (plan 05)**

```text
ColumnProfile: name, dtype, count, null_count, null_pct, distinct_count | None, min, max, mean | None, sample_values: list[str]
DataProfile:   row_count: int, column_count: int, columns: list[ColumnProfile], sampled: bool
profile_frame(frame: pl.LazyFrame | pl.DataFrame, *, max_rows: int | None = None) -> DataProfile
```

**`core/workpaper/spec.py` (plan 06)**

```text
WorkpaperSpec: title, preparer, reviewer, purpose, sections: list[str], include_run_record: bool,
               include_tests: bool, include_profile: bool, output_path: str, format: str  # "xlsx"
build_workpaper(spec: WorkpaperSpec, run: RunRecord | None, profiles: list[DataProfile], out: str) -> str
```

**`core/headless.py` + `cli.py` (plan 08)**

```text
run_workflow_file(path: str, *, input_overrides: dict[str, str] = {}, output_dir: str | None = None,
                  record_dir: str | None = None, timeout_s: float | None = None) -> RunRecord
exit codes: 0 ok | 1 node failed | 2 workflow invalid / input missing | 3 internal error
console script: trigger-designer-cli = "trigger_designer.cli:main"      # click is already a dependency
```

Headless caveats the CLI plan must handle: needs a `QApplication` with `QT_QPA_PLATFORM=offscreen`; build a `TriggerSubWindow()` (no `QMainWindow`), `fileLoad(path)`, apply input overrides to File Input `content.filePath` **before** the first evaluation (or post-load + `markDirty` + `doEvalOutputs()`), run `WorkflowWorker(sorted_nodes, NodeExecutor()).run()` synchronously (or `executeWorkflow` + event loop), never import `trigger_designer.main`, set `check_output.py` target explicitly (4.4 H10), and patch out/avoid `QMessageBox` + `make_progress_dialog` (the `no_modal_dialogs` fixture shows exactly what to stub: `design_window.make_progress_dialog`, `eval_progress.make_progress_dialog`, `design_window.QMessageBox`, `workflow_execution_mixin.QTimer`).

---

## 12. Glossary

| Term | Meaning |
|---|---|
| **Trigger Designer / TriggerEditor** | Product name / repo name. |
| **`.tds`** | Workflow file (JSON via orjson). "Design" in dialogs. Older samples are `.json`. |
| **Node / logic node** | `TriggerNode` subclass: sockets + eval logic. |
| **Content** | The node's `QDMNodeIconContentWidget` subclass: state, dock UI, `get_code`. Not shown on canvas (the canvas shows an icon). |
| **grNode** | `TriggerGraphicsNode`, the canvas item; owns tooltip, ring pen, status badge. |
| **Socket** | Input/output connector; int "type" is colour only. Output i <-> element i of the value list. |
| **Edge** | Connection (`TriggerEdge`); `input_index` orders multi-input edges. |
| **Op id** | `"<family>.<enum member lowercased>"`, the persisted node identity (`input.file_input`). |
| **Family / NodeTypes** | `input, preparation, join, transform, report` (palette tabs). |
| **Lazy spec** | `_LAZY_NODE_SPECS` entry: lets the palette list a node without importing it. |
| **Live evaluation** | GUI-thread `eval()` chain producing `node.value` for previews/config. |
| **Run Workflow / Run** | Background execution of generated code through `NodeExecutor`. |
| **Generated code / `get_code()`** | Python text per node, `exec()`'d at Run and concatenated into `check_output.py`. |
| **Execution context** | The shared globals dict of one run (`NodeExecutor.execution_context`). |
| **Declared outputs** | Variable names a node exposes (`param`, `value`, `*_variable_name`, `*_var`); only these survive `_prune_node_results`. |
| **`incom_data` / `incoming_variable`** | Content attributes: the upstream frame (live) and its variable name (for codegen). |
| **`param` / `value`** | Node attributes: list of `{"data","variable_name"}` per output socket. |
| **Config Dock** | Left dock showing the selected node's `create_layout`. |
| **Data Preview dock** | Bottom dock showing a collected sample of a node's output; follows selection, pin, run results. |
| **Logging dock** | Bottom dock with in-memory per-workflow log. |
| **dock_context** | Optional content hook giving the Config Dock's tooltip summary. |
| **Composite widget** | A widget with `_undo_composite = True` that owns its change signal. |
| **Syncing** | `syncing(content)` guard: model->widget writes that must not be recorded. |
| **Baseline stamp** | First scene snapshot; not an undo step. |
| **Snapshot / stamp** | Whole-scene serialisation used by legacy/`registerInputWidget` undo. |
| **Golden** | Frozen expected CSV under `tests/e2e/fixtures/expected`. |
| **Corpus / WorkflowCase** | The e2e table of checked-in workflows (`tests/support/corpus.py`). |
| **Materialize** | Copy a workflow to tmp and rewrite its file paths. |
| **Batch evaluating / bulk loading** | Scene flags that suppress cascades while loading a file. |
| **Aggregate** | UI title of the GroupBy node (`node_title="Aggregate"`). **Rows** = dynamic row builder; **Count** = count_records; **Normalize** = normalize_columns. |
| **Pen / ring** | Coloured border drawn around a node for executing/executed/error. |
| **Status badge** | Small image at the node's bottom edge (dirty/ok/invalid). |
| **Audit test / exception set** | (planned, 04) a node that tests a population and routes failing rows to a second output. |
| **Workpaper** | (planned, 06) the Excel deliverable summarising a run, tests and profiles. |
| **Run record** | (planned, 02) the JSON log of one Run. |
