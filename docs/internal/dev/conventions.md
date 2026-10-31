# Conventions

`AGENTS.md` at the repo root is binding; this page distils it with examples
that exist in the tree today, and adds the repo's commit and hygiene rules.
Where `AGENTS.md` has fallen behind the code it is flagged **[STALE]**.

## 1. Python and tooling

* Python `>=3.14,<3.15`. Python 3.14 syntax is in use: `except A, B:` without
  parentheses (PEP 758) appears in several files, so do not "fix" it.
* Line length 88, `target-version = "py314"`. Pinned: `ruff==0.17.2`,
  `ty==0.0.91` (pre-commit also runs `ty check` on `src` and `scripts`).
* Verify a change: `.venv\Scripts\python.exe -m ruff format <files>`, then
  `... -m ruff check <files>`, then the focused `pytest` (README). Run ruff on
  files you touch only; the repo is not lint-clean everywhere.
* Prefer `from __future__ import annotations`, `X | None`, dataclasses,
  `pathlib`. Qt through `qtpy` only (the binding is PySide6; never import
  `PySide6`/`PyQt6` directly).
* `# noqa` comments carry the reason after a dash
  (`# noqa: RUF012 - shared empty node style`).
* Logging: `loguru` (`logger.debug/info/warning`); user-facing messages go to
  the Logging dock via `global_logger` or the window's `logInfo/logWarning`.
  A test (`tests/ui/test_no_console_prints.py`) forbids `print`.

## 2. Layering (see `architecture.md`)

Logic in `core/` (Qt-free, unit-testable); Qt file = thin wrapper. A Qt-free
module must not import `qtpy`, `nodeeditor` or `trigger_designer.qt`.
Generated code calls core functions; it never contains logic of its own.

## 3. Config Dock UI (`docs/DESIGN_SYSTEM.md` §§1-7)

* **Reuse** `qt/widgets/common/config_widgets.py` (`from
  trigger_designer.qt.widgets.common import ...`): `IconButton`, `TextButton`,
  `ConfigSection`, `FormRow`, `FormGrid`, `ColumnChecklist`, `ColumnPicker`,
  `SegmentedControl`, `RuleStack`, `NoWheelComboBox`, `EmptyStateLabel`,
  `CONTROL_H`. No per-node rewrites. Reference implementation:
  `Preparation/select.py` (dock section). For a declarative form, use
  `Field`/`FormSection` (`adding-a-node.md`).
* **Icon-first.** Icon-only buttons by default (`IconButton`); text only in
  dialogs and in the paired `All` / `None` bulk toggles (`TextButton`, object
  name `BulkButton`, see `Audit/duplicates.py::build_dock`).
* **Tooltip and accessible name are mandatory** on every icon button
  (`IconButton(tooltip, icon)` sets both).
* **Icons.** Glyphs are Material Symbols declared in `qt/resources.json` as
  `{"mode": "material", "name": "<symbol>"}` (`icon_add`, `icon_remove`, ...) and
  tinted per theme; build a button with
  `IconButton.themed(tooltip, rsm_icon=ResourceManager().get("icon_add"))`.
  No `QIcon.fromTheme` (blank on Windows). **[STALE]** AGENTS.md still mentions a
  `:/qss_icons` fallback: that machinery was removed (`02f8232`); there is no
  fallback argument any more. Node (canvas) icons are the SVG files described in
  `adding-a-node.md`.
* **No inline `setStyleSheet`.** Give the widget an `objectName` and style it in
  `resources/qt/themes/base.qss` (a `str.format` template; tokens such as
  `{background_hover}`, `{accent_primary}`, `{button_bg}`) and in
  `qss/_style.scss` (keep the two in step).
* **Hover/pressed per `objectName`.** A `#objectName` selector outranks
  `QPushButton:hover`, so restate `:hover`, `:pressed`, `:disabled` for each
  object name (see `QPushButton#BulkButton` and `#IconButton` in `base.qss`).
  Use `{background_hover}` / `{background_pressed}`; `{button_hover}` is nearly
  invisible against `{button_bg}`. Keep a **constant 1 px base border** (same
  colour as the background) so hover does not shift layout.
* **Layout tokens.** Main dock layout spacing 2, margins 5; toolbar height 40,
  margins 0; controls height 30 (`CONTROL_H`); icon buttons 30x30 with a 16 px
  glyph (`ICON_SIZE`; caption buttons stay 12 px).
* **Live by default** with a ~300 ms debounce on text/search
  (`undo/binding.py::DEFAULT_DEBOUNCE_MS`); there is no Apply button. Note that
  "live" means the *model and undo stack* update immediately and the node itself
  runs when the user leaves it (deferred evaluation, `architecture.md`).
* **Undo text is `"Noun Verbed"`** ("Duplicate Keys Changed", "Head Rows Changed")
  and is recorded only when the value really differs.
* Empty input: show `EmptyStateLabel()` instead of controls.
* Themes are token files in `resources/qt/themes/*.json`; never hard-code a hex
  colour in widget code (the Run History models read tokens from
  `get_theme_manager()`).

## 4. Undo/redo (`qt/undo/`)

The timeline is a `QUndoStack` (`UndoController`), not scene snapshots.

* **The model is the only truth.** A command mutates the model, then calls
  `sync_from_model()`; it never writes widgets.
* **Model -> widget never re-records.** Every write-back runs inside
  `with syncing(content):`; bindings check `is_syncing(content)`. Every setting
  handler starts with
  `if is_syncing(self) or self.history.is_restoring_history: return`.
* **Config Dock is the editor.** Selecting a node builds widgets
  (`create_layout`), deselecting destroys them. After a restore the same node is
  still selected, so `ConfigDock.updateConfig` would short-circuit on
  `_current_key`; `onHistoryRestored` passes `force=True`. Do not remove that.
* **Recording helpers** (on `TriggerContentUndoMixin`, available on every
  content):

  | Helper | Use for |
  |---|---|
  | `push_property_change(path, old, new, text, merge_key=...)` | one setting (`path` is dotted on the content and may cross into dict keys: `("settings", "rows")`, `("changes", "rename_mapping")`) |
  | `push_list_change(path, old, new, text)` | a collection that changes *size* (rows, sections); widgets are rebuilt on restore |
  | `registerInputWidget(w, text=..., merge_key=...)` | a hand-built dock control; debounce, diff and restore guard included. Records a **whole-scene snapshot**, so prefer the two above for node settings |
  | `self.history.storeHistory(...)` | fallback: serializes the whole scene; correct but heavy (used for canvas actions: create node, label, arrange) |

  `merge_key` collapses a *burst* (typing) into one step and keeps the original
  `old`; one key per control; never for discrete clicks. `ShapingContent.set_setting`
  and `AuditContentMixin.set_setting` do all of this for you.
* **Widget resync** hooks (both optional): `_sync_widgets_from_model()` refreshes
  values in place keeping widget identity (so a focused editor survives);
  `_rebuild_widgets()` recreates structure when the widget count depends on the
  model. Do not add a new `history_stamp_callback` (legacy snapshot restores
  only; no node subclass uses it now).
* **Every dock control is tracked by default**: `ConfigDock.updateConfig` calls
  `registerUnboundDockWidgets()` after `create_layout`. Traversal subtleties
  (`TriggerChangeHandler.iter_dock_widgets`): use `QScrollArea`, not
  `QAbstractScrollArea`, to reach `widget()`; mark a widget that emits its own
  change signal `_undo_composite = True` (`ColumnChecklist`,
  `SQLFormulaWidget`, `ConfigSection` in shaping/audit forms) so its children are
  not recorded twice.
* **Selection is UI state**, not document state: after a snapshot restore
  `onHistoryRestored` falls back to `ConfigDock.currentNode()` rather than
  blanking the panel.
* **Guards.** `with self.history.restoring(is_undo=is_undo):` (a depth counter;
  never assign `is_restoring_history` directly). Never let an exception escape
  `undo()`/`redo()` (a raise through the C++ stack aborts the process;
  `UndoableEdit._guard` wraps it). **Do not implement `mergeWith`** (`QUndoStack`
  deletes the merged-away command); `UndoController.push` folds commands through
  `can_merge_with`/`absorb`.
* A suppressed second evaluation: after a `set_setting` the command's redo would
  re-evaluate the node; the helpers set `_suspend_node_evaluation` around the
  push. Do the same if you push by hand after you already evaluated.

## 5. Naming and compatibility

* Op id = `"<family>.<enum member name lowercased>"`; never rename an enum
  member. Persisted keys (content schema keys, audit `Params` field names,
  `workflow_metadata` keys) are API: add with defaults, never rename.
* Node titles are short ("Rows", "Count", "Normalize"); a title change is safe
  (loading overwrites the saved title) but must change the class attribute, the
  lazy spec and the op catalogue together (`test_node_titles.py`,
  `test_op_catalog_matches_registry.py`).
* Variable names in generated code: `var_<kind>_<id>`; core function names
  `apply_<x>`, `run_node`, `describe`, `DEFAULTS`, `normalize`.
* Stable error codes `TD-<FAMILY>-nnn`; never reuse or renumber.
* Python-version-independent behaviour: do not depend on dict-order of
  user-visible output unless sorted; goldens that depend on hash-join order are
  compared order-insensitively (`testing.md`).

## 6. Commits

* Conventional-commit style, matching `git log`: `type(scope): imperative
  summary`, lower case after the colon, no trailing full stop. Types seen:
  `feat`, `fix`, `docs`, `test`, `refactor`, `style`, `perf`. Scopes seen:
  `audit`, `audit-trail`, `nodes`, `run`, `security`, `save`, `cli`, `sql-guard`,
  `workpaper`, `e2e`, `errors`, `graph`, `eval`, `guide` (user docs), `dev`
  (this folder). Older history has plain imperative messages ("Fix filter nulls
  ..."); new work uses the typed form.
  Examples: `fix(security): run Formula and Filter-expression SQL through the
  read-only guard (BUG-029, BUG-030)`, `feat(nodes): add the Window node`,
  `test(audit-trail): opt-in overhead benchmark for the run record`.
* Reference the bug ids from `docs/bugs.md` (`BUG-nnn`) when fixing one.
* The body says *why* and what changed for the user or the contract; list
  behaviour changes explicitly (they feed `docs/CHANGELOG.md`).
* **No `Co-Authored-By` trailer in this repo** (project preference recorded in
  the maintainer's memory; do not add the assistant trailer even if a tool
  suggests it).
* One topic per commit; commit tests with the change. Commit with an explicit
  pathspec (`git commit -m "..." -- <paths>`) when other people or agents are
  committing in the same tree; never `git add -A`, `commit -a`, `stash` or
  `reset` in a shared tree. Do not push unless asked.
* Do not use `--no-verify`; pre-commit runs ruff format, ruff check and `ty`.

## 7. Never commit generated artefacts

* `check_output.py` at the repo root: written by older builds into the working
  directory. It is tracked by accident (although `.gitignore` lists it) and a
  stale copy is in the tree. The current run script goes to
  `<app data>/last_run/check_output.py`. Leave local modifications of it out of
  your commits.
* Run records (`<workflow>.runs/` folders next to a saved workflow: JSON
  records, `index.jsonl`, `hash_cache.json`, `.started` markers). `.gitignore`
  has no pattern for `*.runs/` yet, so check `git status` after running a
  workflow from `savedfiles/` and do not add them. (Suggested fix: add `*.runs/`.)
* `dataframe_export.csv` (tracked, regenerated by Data Preview exports),
  `logs/`, `build/`, `dist/`, `output/`, `profiles/`, `compare_report/`,
  `savedfiles/*/app_output/`, `.pytest_cache/`, `.ruff_cache/`, `__pycache__/`.
* Edited sample workflows under `savedfiles/` that a run or a save touched
  (Save re-writes the file; revert it unless you meant to change the sample).
* Compiled Qt resource modules are not hand-edited; icons are loaded from files.
* Goldens are *not* generated artefacts but are only ever rewritten
  deliberately (`testing.md`).

## 8. Documentation duties

A user-visible change updates, as relevant: `docs/NODE_REFERENCE.md` (node
rows), `docs/guide/**` (user guide), `docs/CHANGELOG.md` (feature, behaviour
change, known issue), and this folder when a contract changes. Do not leave
stale statements behind: when you fix a claim in a doc, fix it everywhere
(`CONTRIBUTING.md` still says Python 3.13.12, lists `tests/integration` and
`uv sync` caveats that no longer apply; `docs/SESSION_HANDOFF.md`,
`docs/ENHANCED_EXECUTOR_GUIDE.md` and `docs/plan/00-codebase-brief.md` predate the
branch).
