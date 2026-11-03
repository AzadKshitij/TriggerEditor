# 05 — core/ (~400 lines)

Paths relative to `src/trigger_designer/core/`. Evidence: whole-word grep across src, tests, scripts. Unaudited: `errors/translator.py`, `input_source.py`, `inputs.py`, `shaping/reconcile.py`, `charts.py`, `node_configuration.py`. No stdlib/native reinventions found in the files read (`errors/suggest.py` already uses difflib; `warmup.py`, `connect_duckdb` are live). Verify: ruff format/check on touched files, then pytest.

## Batch A — zero-risk deletes (~85 lines)

1. `delete:` `singleton.py` (20 lines): only its own def/docstring, no `metaclass=` use.
2. `delete:` `errors/catalogue.py:873-891` `main_markdown()` (1 occurrence). First check no docs script calls it with `python -c`.
3. `delete:` `shaping/assign.py:46-48` `greedy_sequential` (docstring says "used by tests", no test does). Confirm `_sequential` still has a live caller.
4. `delete:` dead constants, each 1 occurrence: `constants.py:11` `APP_TITLE`, `:14` `FOLDER_NAME` (then `VERSION_BRANCH` is dead too; check dynamic `getattr`), `errors/model.py:16` `SEVERITIES`, `errors/translator.py:25` `_ANY`, `:29` `_DUCK_NUMERIC`, `:56-57` `_TextError`, `shaping/aggregate.py:47-49` `FUNCTION_TO_ACTION`.
5. `delete:` `frames.py:22-31` `frame_shape` plus its re-export `qt/node_base.py:33`; remove shape/identity assertions in `tests/unit/test_frames.py:7,9,22-24`. Bonus: point `qt/helpers/error_context.py:110` and `shaping_support.py:37` at `core.frames.frame_schema` and drop the aliased re-export at `node_base.py:32`.
6. `reuse:` `utils/dtype_utils.py:65-71` `_frame_schema` (used once at :83) duplicates `core/frames.py::frame_schema`. Difference: returns `{}` for None vs an empty `pl.Schema` for non-frames, so confirm the call at :83 tolerates it. Optionally inline `normalization_casts` (single use at :107) unless tested (`grep -rn normalize_to_supported tests`).

## Batch B — executor dead API (~150 lines) — risk low-medium

`ExecutionCheck/executor.py`: delete `execute_node_legacy` (467-481), `cancel_execution` (504-513), `clear_context` (515-519), `get_context_info` (521-545), `get_statistics` (547-553), `get_execution_history` (555-568), `set_config` (570-577): each has 1 occurrence (the def). Real external users are only `NodeExecutor()`/`execute_node` from `qt/helpers/workflow_execution_mixin.py:110` and `workflow_worker.py:33`. Then the state that only they read: `_cancel_event` (155, 335, 511; **never `is_set()`**, so cancellation is already a no-op), `self.stats`, `self.execution_history`, `ExecutionStats` (89-99), `_update_stats` (483-502) and its call in `execute_node` (verify), history append/trim (450-452), `ExecutionResult.without_frames` (55-70), `_describe_value` (76-86). Fix unused imports (`sys`, `replace`).
Check `_current_task_done` (304, 455) is not used for worker coordination. **Before deleting `cancel_execution`/`_cancel_event`, add a `docs/bugs.md` entry**: cancellation is already a no-op (`_cancel_event` is set at :511 and cleared at :335 but never checked). That is a bug to fix or consciously drop, not a simplification, and deleting the code silently loses the finding.
Tests: delete `tests/unit/test_execution_result.py` and `test_executor_errors.py:77` (`test_without_frames_drops_exception`); `test_executor_hooks.py` and the rest of `test_executor_errors.py` must still pass.
Also `shrink:` missing-dependency attempt counting (213-255, ~30 lines: `_track/_log/_report_missing_dependency`, called only at :417, plus `max_missing_dependency_attempts`, `_missing_dependency_attempts`) → one `logger.warning` for NameError/FileNotFoundError. No test references it (`grep -rn missing_dependency tests`); only log volume changes.

## Batch C — one caller each (~185 lines) — risk medium

1. `yagni/shrink:` `utils/cleansing_util.py` (323 lines, fluent `DataCleansing`). Sole caller `shaping/cleansing.py:8,31`, which only uses `get_result`. `set_data` (69), `get_stats` (321), `CleansingStats` (20), `_validate_input` (64-67) unused. Replace with a list of `pl.Expr` (`str.strip_chars`, `replace_all`, `to_lowercase`, `fill_null`, `drop_nulls`) in a single `with_columns`. Body of the 7 methods was NOT read by the auditor: read them and keep semantics (null-column removal, field filtering, case modes). Line estimate is rough (-150). Tests: `grep -rln cleansing tests`; none import the util directly. Add a before/after output comparison on one workbook.
2. `delete:` `shaping/common.py:25-57` `ERROR_CODES` (33 lines). Only `tests/unit/test_shaping_common.py:8,18` use it (key-format check); the real registry is `errors/catalogue.py` `CATALOGUE`. First diff the `TD-SHAPE-*` code sets, then delete the dict and retarget or drop the test.
