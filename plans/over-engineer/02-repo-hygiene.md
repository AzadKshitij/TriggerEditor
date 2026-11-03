# 02 — Repo hygiene: tracked scratch, one-off scripts, stale docs

All low risk. Before each deletion run `git grep -n <name>` and check `.github/` and `.pre-commit-config.yaml` for CI references (not checked by the audit).

## Batch A — binary/data cruft

1. `delete:` `profiles/load_1_20260930_101449.json` (4 MB profiler output). `git rm`, add `profiles/` to `.gitignore`.
2. `delete:` `scripts/benchmark_results/` (20 JSON, canvas-optimisation history).
3. `delete:` top-level `dataframe_export.csv`.
4. `delete:` `src/opencode.json` (tool config under src/).
5. `delete:` `src/trigger_designer/External Resources/` (Alteryx `.yxmd`, 0 refs) and unreferenced `examples/*.csv` (check `git grep -n BL-Flickr` first).
6. **savedfiles/ - partial only (see index correction).** Do NOT hand-list. Compute the keep set: `git grep -hoE "savedfiles/[^\"')]+" -- tests | sort -u`, plus whatever `tests/support/corpus.py` / `workflows.py` build via `REPO_ROOT / "savedfiles" / basename` (read both, the basenames are computed). Known keepers a hand list missed: `0. All Node- Test.tds`, `9. Running Total.tds`, `10. Transpose.tds`, `11. Split.tds`, `12. generate_rows.tds`, `1. out_check.csv`, `out_check_W_formula.csv`, the numbered `*.json` workflows, `8. In-Graph.tds`; also check the repo-root `data/` folder, which tests reference too. Cut only files absent from the computed set: the `Example_1/` scratch (data_creation*.py, manual_code.py, test.ipynb, test_pd_pl.py, output/*.png), stray `l.png`, `Test Graph Output..svg`, `calculator_check*.json`, `check_input.json`, unreferenced `.txt` checks. Move `TriggerDesigner_Setup.iss` to `scripts/` if the installer is still used.
   **`savedfiles/Example_2_Retail_Ledger/app_workflow/1.tds` has uncommitted edits.** Ask the owner whether that work matters (or commit it) before deleting `Example_2_Retail_Ledger/`.
   Steps: compute the keep set, `git rm` the rest, run `tests/e2e`. Follow-up (separate): move the kept workflows to `tests/e2e/workflows/` so `savedfiles/` stops being a test dependency.
   Est.: recount after the keep set is computed; likely fewer than the original ~60 files.

## Batch B — one-off scripts and duplicates

1. `delete:` `check_output.py` (1768 lines) + `scripts/check_output_pandas.py` (64) + `scripts/check_output_polars.py` (99) + `scripts/Compare.py` (408). Replacement: `tests/e2e/test_workflow_goldens.py`. Fix mentions in `docs/bugs.md`, `docs/plan/00-codebase-brief.md`, and the `scripts/Compare.py` comment at `pyproject.toml:20`. Check that `tests/unit/test_file_output.py:156` (`test_check_output_header_puts_src_on_path`) and `tests/conftest.py:221` do not need the real `check_output.py` (they appear to use a fake path). pandas is already out of the dev group (see the pyproject comment), so there is no dev-dep follow-up.
2. `delete:` one-time profiling/bench scripts: `scripts/profile_app.py`, `profile_loading.py` (also referenced by `warmup` docs and `README.md:175,210`; remove those mentions), `benchmark_workflow_execution.py`, `benchmark_eval_perf.py` (888), `benchmark_canvas_perf.py` (679), `all_icons.py`, `run_pyspy.bat` (`README.md:210` mentions it). Keep one benchmark if perf tracking continues.
3. `delete:` root `run.bat` (identical to `scripts/run.bat`, which `README.md:135` documents; keep the scripts/ one). `uv run trigger-designer` already launches the app.
4. `delete:` `examples/` (3 demo scripts for old features) and `tests/manual/global_logging_demo.py` (duplicate of `examples/global_logging_example.py`).
5. `delete:` `tests/manual/` (8 demos, ~1,250 lines; not collected, not referenced). Optional keep: `style_demo.py`, `sql_editor_demo.py`. Note `integration_example.py:136-137` calls two methods slated for deletion in 03/04, another reason to delete it.
6. Check then delete: `tests/support/win_caption_probe.py` (197; grep for importers first), `tests/benchmarks/` (285; only if no CI job runs it).
7. `delete:` `ToDo.md`, `Todo.todo` after moving real items to `docs/bugs.md`.
8. Editor config: keep one of `.vscode/`, `.zed/`; remove the rest.
9. `trigger.spec`: drop excludes for packages never installed (`pandas`, `numba`, `llvmlite`, `numexpr`, `seaborn`) and simplify the `Path.exists()` fallback chain; rebuild to confirm (~15 lines).

## Batch C — stale docs (~3,600 lines, 17 files; content NOT yet read, spot-check first)

Stubs (1-9 lines): `Nodes.md`, `Features.md`, `FeatureDev.md`, `Notes.txt`, `PROGREE.md`, `prompt_requirements.md`.
One-time reports: `PERFORMANCE_PROFILING_FINDINGS.md` (611), `WORKFLOW_LOAD_PERFORMANCE_REPORT.md`, `POLARS_MIGRATION_SUMMARY.md`, `file_reading_updates_summary.md`, `SESSION_HANDOFF.md`.
Per-feature READMEs: `ENHANCED_EXECUTOR_GUIDE.md` (289), `POLARS_TABLE_VIEWER_README.md` (326), `DATA_PREVIEW_DOCK_README.md`, `LOGGING_DOCK_README.md`, `GLOBAL_LOGGING_README.md`, likely `SQL_FORMULA_EDITOR_README.md`.
Also: `docs/design_system_preview.html` (delete if not linked from `DESIGN_SYSTEM.md`), `plans/nodes/` (20 files, overlaps `docs/plan/`; read `plans/nodes/README.md`, merge live items into `docs/plan/`, delete finished).
Keep: `DESIGN_SYSTEM.md` (AGENTS.md), `NODE_REFERENCE.md`, `docs/plan/`, `docs/bugs.md`.
Steps: read each, fold anything not true elsewhere into `NODE_REFERENCE.md`, `git rm`, grep for dangling links.
