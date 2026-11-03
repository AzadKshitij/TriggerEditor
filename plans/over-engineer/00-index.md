# Over-engineering cut plan — index

Audit date 2026-10-27, whole repo. Four read-only audits (core, qt infra, node widgets, deps/scripts/repo). Spot checks done by the lead: zero importers confirmed for `file_opener`, `rc_icon`, `rc_uicon`, `nodeeditor_dark_resources`, `settings_panel`, `model_file_dialogue`, `clickable_label`, `core.singleton`, all `qss/*` legacy files; `flowlayout` only self-references; `click/colorama/packaging/dateutil/tzdata/openpyxl` have no import in `src/`.

**Status (reviewed against the tree, 2026-10-27):** already staged on `feature`: 01 Batch A (legacy qss, `*_dark_resources.py`, `rc_icon.py`, `rc_uicon.py`, `examples/example_test/`), 04 item 4 (`comment.py`), several 03 Batch A/C deletions, and most 06 Batch A dep removals (06 lists what remains). Do not redo those; run `git status` and re-grep before each batch. The plans were written assuming PyQt6/Python 3.13; the repo is now PySide6 on Python 3.14, so treat PyQt6 wording as historical.

Goal: same behaviour, fewer lines. Nothing here touches validation at trust boundaries, security, data-loss handling, or accessibility.

## Ranked plan files (biggest cut first)

| # | File | Est. lines out | Risk | Notes |
|---|------|----------------|------|-------|
| 1 | [01-generated-and-dead-resources.md](01-generated-and-dead-resources.md) | ~14,500 (batch A) + ~2,500 + up to ~11,000 (batch B/C) | low → medium | dead qss, rc modules, icons_rc, darkstyle_rc |
| 2 | [02-repo-hygiene.md](02-repo-hygiene.md) | ~9,000 lines + ~69 MB tracked | low | savedfiles, scripts, docs, examples, manual demos |
| 3 | [03-dead-python-qt.md](03-dead-python-qt.md) | ~1,100 | low–medium | qt infra dead code, select_table_widget, undo surface |
| 4 | [04-nodes.md](04-nodes.md) | ~600 | low–medium | file_input, lazy spec table, boilerplate |
| 5 | [05-core.md](05-core.md) | ~400 | low–medium | executor dead API, DataCleansing, ERROR_CODES |
| 6 | [06-dependencies.md](06-dependencies.md) | ~3-4 pins left (most already applied) | low–medium | openpyxl→dev, shiboken6, pillow, numpy; keep tzdata |

Total (approximate, before the already-staged work): roughly **-28,000 lines (-17,000 excluding 01 batch B/C)**. Dependency cuts are mostly applied already; 06 lists the 3-4 pins left.

## Execution order / rules

1. One PR (or commit) per numbered file, batch by batch inside each file. Each batch ends green.
2. After each batch: `uv run --project . ruff format <files>`, `uv run --project . ruff check <files>`, then the focused pytest list named in that batch. Run the full `pytest` once before merging each file.
3. Smoke launch the app (`uv run trigger-designer`) after files 1, 3, 4 (resources, startup, node palette).
4. Do batch A of every file first (zero-caller, pure deletes), then later batches.
5. Order dependency in 04 Batch C: do item 7 (`ConfigContent` subclassing) and item 11 (lift `_debounced`) before item 12 (quiet-set helper).
6. Commits in this repo omit the Claude co-author trailer (project memory).

## Findings corrected or rejected during review

- `git rm -r savedfiles` was proposed. **Rejected as stated**: `tests/e2e/test_workflow_goldens.py`, `test_graph_run.py` and `tests/support/corpus.py` load workflows from `savedfiles/` (`2. in-select-out.json`, `4.1. in-join-out.json`, `5..7.`, `8. In-Graph.tds`, `tests/e2e/workflows/formula-category.tds`). Only the unreferenced remainder is cut (see 02; the keep-list there is computed by grep, not hand-listed).
- Migrating off `qtpy`: **not a cut**. `nodeeditor-qtpy` requires it; zero lines saved.
- Hand-rolled window chrome (`win_caption.py`, `window_chrome.py`) vs Qt native move/resize: **excluded**, high regression risk (Aero Snap, DPI) and needs manual Windows testing. Revisit separately.
- `psutil`, `pillow` (needed by matplotlib anyway), `orjson`, `loguru` logging: kept or deferred, see 06.
- `TriggerSceneHistory` passthroughs and `history_stamp_callback`: required by nodeeditor, not cuts.
- Legacy QSettings geometry migration in `layout_state.py`: treated as user-data migration, kept.

## Still unaudited (no verdict either way)

`errors/translator.py` (1312 lines), `input_source.py`, `inputs.py`, `shaping/reconcile.py`, `charts.py`, `node_configuration.py`, `shaping_support.py` internals (1128 lines, flagged only as a split candidate, no savings).
