# Per-node plan

Companion to [README.md](README.md), which defines the rules (R1 to R10), the boundaries (B1 to B9), the decisions (D1 to D9), the defects (F1 to F12) and the phases (P0 to P9). Line references are to the worktree as of 2026-10-26.

Each entry gives: the Qt module and core module, today's classification, the target, the phase, and the effort (XS, S, M, L).

## Input / Output

### File Input
- **Qt:** `qt/widgets/nodes/InOut/file_input.py`. **Core:** `core/input_source.py` (`build_source`, `:787`), `core/inputs.py`.
- **Today:** MIXED. CSV, TXT, Parquet and NDJSON are scans (`input_source.py:546-562`). JSON is `read_json` (`:565-567`). Excel reads the whole sheet (`:578-602`) and passes `n_rows` only when a row limit is set, for one sheet in one file. SQLite uses `read_database` (`:609-611`). DuckDB uses `connection.sql(...).pl()` (`:613-614`). The legacy path (`file_input.py:823`) re-reads on every evaluation (F2).
- **Target:** keep the scans, with `record_limit` as a lazy head. Cache the legacy read by file metadata (path, size, mtime, options) and drop the per-evaluation `head(10).collect()`. Excel gets a bounded `n_rows` read for the live sample (S4) and a cached whole read for Run. JSON, SQLite and DuckDB move to the `pl(lazy=True)` route if S1 passes (D4). Retire the legacy path later (D9).
- **Boundary:** B8 until S1 and S4 finish.
- **Tests:** collect counting per format, a read-once test for the cache, and the existing input-type e2e tests.
- **Phase:** P1 for the cache (F2), P5 for the sources. **Effort:** M.

### File Output
- **Qt:** `qt/widgets/nodes/InOut/file_output.py`. **Core:** `core/shaping/file_output.py`.
- **Today:** MIXED. The sinks for CSV (`:57`, `:62`), Parquet (`:66`), NDJSON (`:70`) and IPC (`:72`) stream. Excel collects first (`:64`), and so does JSON (`:68`). `use_streaming` is dead (`:13`, F6). Live mode passes the upstream entry through without computing it.
- **Target:** keep the sinks. Remove the dead setting. Excel gets a streaming writer (S2), with a lazy row count checked against the 1,048,576-row sheet limit before writing. JSON gets a streaming array writer (S3), checked byte for byte against `write_json`.
- **Boundary:** B9 until S2 and S3 finish.
- **Tests:** output equivalence against the current writers, and the row-limit error.
- **Phase:** P1 (the setting), P6 (writers). **Effort:** M.

## Preparation

### Cleansing
- **Qt:** `qt/widgets/nodes/Preparation/cleansing.py`. **Core:** `core/shaping/cleansing.py`, `core/utils/cleansing_util.py` (`DataCleansing`).
- **Today:** EAGER. `cleansing.py:30` collects the whole input. `DataCleansing` runs per-column loops on a DataFrame (`:96`, `:103`). It computes `null_count` statistics on every call that nothing reads (`:84`, `:130`, `:180`, `:195`, F8).
- **Target:** each option becomes an expression on a `LazyFrame`: trim, case, empty to null, `fill_null`, and `cast(strict=False)`. Removing all-null columns takes one bounded aggregate row (B1), then a lazy select.
- **Tests:** parity with the current output for each option, and schema equality.
- **Phase:** P4. **Effort:** L.

### Filter
- **Qt:** `qt/widgets/nodes/Preparation/filter.py`. **Core:** `core/shaping/filter.py`, `core/shaping/sql_expression.py`.
- **Today:** MIXED. Builder mode is lazy (`filter.py:96-113`). Expression mode registers the frame with DuckDB (`:126`) and runs two eager `pl()` calls (`:129-130`), so DuckDB runs twice. Rows whose predicate is NULL are dropped from both outputs (D8).
- **Target:** one DuckDB relation that adds a keep flag, then `pl(lazy=True)`, then two lazy filters (D3). The node owns the connection's lifetime.
- **Tests:** a NULL-predicate fixture (D8), and equivalence on the expression fixtures.
- **Phase:** P4. **Effort:** M.

### Formula
- **Qt:** `qt/widgets/nodes/Preparation/formula.py`. **Core:** `core/shaping/formula.py`, `core/shaping/sql_expression.py`.
- **Today:** EAGER. `duck.sql(query).pl()` materialises the input (`formula.py:185-186`). Sections run one at a time, each collected (`:161-163`, `:214-216`). Validation uses zero-row relations and `EXPLAIN` (`:205`, `:224-226`).
- **Target:** chain each section as a DuckDB relation over the previous one, then `pl(lazy=True)` once (S1). Keep the zero-row validation.
- **Tests:** multi-section equivalence, and the validation error codes.
- **Phase:** P4. **Effort:** M to L.

### GroupBy
- **Qt:** `qt/widgets/nodes/Preparation/groupby.py`. **Core:** `core/shaping/aggregate.py`.
- **Today:** LAZY. `group_by(...).agg(...)` and a lazy normalise. `implode` is lazy.
- **Target:** keep. Decide on `maintain_order` for group order (D2), after measuring its cost.
- **Phase:** P2. **Effort:** S.

### Select
- **Qt:** `qt/widgets/nodes/Preparation/select.py`. **Core:** `core/shaping/select.py`.
- **Today:** LAZY for Run and live. The Qt bulk auto-detect collects `head(1000)` (`select.py:589-590`, B6). `infer_dtype` (`core/shaping/select.py:195`) is a Python helper for the UI.
- **Target:** keep. Feed `infer_dtype` from a lazy head so only the needed values are collected.
- **Phase:** P1. **Effort:** XS.

### Sort
- **Qt:** `qt/widgets/nodes/Preparation/sort.py`. **Core:** `core/shaping/sort.py`.
- **Today:** LAZY, a single `sort`.
- **Target:** keep. Add `maintain_order` only where tie order is part of the contract (D2). Measure the memory of a streaming sort on the benchmark.
- **Phase:** P2. **Effort:** XS.

### Unique
- **Qt:** `qt/widgets/nodes/Preparation/unique.py`. **Core:** `core/shaping/unique.py`.
- **Today:** LAZY. Two outputs, the unique rows and the duplicates via `is_duplicated`.
- **Target:** keep. Keep-first uses `maintain_order=True`. If S6 shows the shared input runs twice, add `cache()`.
- **Phase:** P1. **Effort:** XS.

### Split
- **Qt:** `qt/widgets/nodes/Preparation/split.py`. **Core:** `core/shaping/split.py`.
- **Today:** LAZY, but the shuffle is global (`shuffle(seed=)` at `split.py:40`), and a column-wide `max()` sits inside a filter.
- **Target:** D1. Either keep the seeded shuffle with B4 materialising only the index column, or switch to `Expr.hash(seed)`.
- **Phase:** P3. **Effort:** S to M.

### Rows
- **Qt:** `qt/widgets/nodes/Preparation/dynamic_row_builder.py`. **Core:** `core/shaping/rows.py`.
- **Today:** EAGER. A Python loop builds up to `MAX_ITERATIONS` = 10,000 values (`rows.py:51-61`), then a DataFrame (`:71`). `describe` regenerates the whole list on every evaluation (`:77-83`).
- **Target:** vectorise with `int_range`, `date_range` and a cross join. Compute the cap arithmetically, and use the same arithmetic in `describe`. Keep the "Reached 10,000 rows" chip. Existing tests: `tests/unit/test_rows_core.py`.
- **Phase:** P3. **Effort:** M.

### Normalize
- **Qt:** `qt/widgets/nodes/Preparation/normalize_columns.py`. **Core:** `core/shaping/normalize.py`.
- **Today:** LAZY. Schema-only renames.
- **Target:** keep.
- **Phase:** P1. **Effort:** XS.

### Record ID
- **Qt:** `qt/widgets/nodes/Preparation/record_id.py`. **Core:** `core/shaping/record_id.py`.
- **Today:** LAZY, but it uses global sorts (`record_id.py:60-62`), and the row index depends on input order.
- **Target:** use `Expr.over(group, order_by=...)` instead of global sorts (verified in 2.0.0). Put `with_row_index` before any reordering. Add order tests (D2).
- **Phase:** P2. **Effort:** S.

### Select Records
- **Qt:** `qt/widgets/nodes/Preparation/select_records.py`. **Core:** `core/shaping/select_records.py`.
- **Today:** LAZY, with a row index, `rank().over`, filter and sort (`:89-90`). Two outputs: the selected rows and the remainder.
- **Target:** first and last via `head` and `tail`. Largest and smallest via `top_k` or a per-group rank. The remainder as an anti join of the selected rows. Add `cache()` if S6 shows double execution. Add order tests.
- **Phase:** P2. **Effort:** S to M.

### Find and Replace
- **Qt:** `qt/widgets/nodes/Preparation/find_replace.py`. **Core:** `core/shaping/find_replace.py`.
- **Today:** LAZY expressions (`:98-128`). The change-count chip runs `pl.collect_all` over `head(10_000)` (`:142`, F9).
- **Target:** compute the counts as one lazy aggregate over the sample. The chip text already says "first 100 rows".
- **Phase:** P1. **Effort:** S.

### Date Helper
- **Qt:** `qt/widgets/nodes/Preparation/date_helper.py`. **Core:** `core/shaping/date_helper.py`.
- **Today:** LAZY expressions (`:178-202`). The unreadable-dates chip collects `head(10_000)` (`:222`).
- **Target:** count the failures as one lazy aggregate, with the same text.
- **Phase:** P1. **Effort:** S.

## Join

### Append
- **Qt:** `qt/widgets/nodes/Join/Append.py`. **Core:** `core/shaping/append.py`.
- **Today:** LAZY. `pl.concat` (`:32`).
- **Target:** keep.
- **Phase:** P1. **Effort:** XS.

### Union
- **Qt:** `qt/widgets/nodes/Join/union.py` only. There is no core runner.
- **Today:** LAZY, but the concat logic is in Qt: `execute_union` (`:201-232`), with `diagonal_relaxed` concats at `:232`, `:269` and `:310`. The generated code repeats the concat inline (`:785-814`). Output goes through `live_sample`.
- **Target:** move the logic to `core/shaping/union.py` with a `run_node`, and have the generated code call it. Keep `diagonal_relaxed`, the rename mapping and the coercion warnings. Add Union to the palette docs (F10).
- **Phase:** P5. **Effort:** M.

### Join
- **Qt:** `qt/widgets/nodes/Join/join.py`. **Core:** `core/shaping/join.py`.
- **Today:** LAZY. One full outer join (`join.py:196-200`), and three outputs that filter that one result (`:247-281`). Each consumer that collects may run the join again.
- **Target:** three plans. The inner join for the matched output, and anti joins for the left and right unmatched outputs (both verified in 2.0.0). Do not rely on a shared subplan. Use `maintain_order="left"` where the left order is expected (D2).
- **Phase:** P2. **Effort:** M.

### Reconcile
- **Qt:** `qt/widgets/nodes/Join/reconcile.py`. **Core:** `core/shaping/reconcile.py`, `core/shaping/assign.py`, `core/shaping/common.py` (`estimate_pairs`).
- **Today:** EAGER. Both inputs are collected (`reconcile.py:447-448`). Sorts, uniques, group-bys and ranks run on DataFrames (`:221-310`). The pair guard runs on collected frames (`:151-165`, F3). The summary is eager (`:357-417`). Unmatched rows use `is_in(implode())` (`:332-340`). The one-to-one assignment is a Python loop of up to `MAX_ROUNDS` = 200 (`assign.py:7-29`), plus a row-by-row fallback (`:32-43`). `LIVE_CAP_ROWS` = 200,000 (`reconcile.py:26`) is inert (D6).
- **Target:** the candidate plan lazy, with row indexes. The pair-count guard as a lazy aggregate of key-group products, giving one scalar (B1). The summary as lazy aggregates. Unmatched rows as anti joins. The assignment stays as boundary B3, over candidate key columns only (D5).
- **Phase:** P7. **Effort:** L.

## Transform

### Count
- **Qt:** `qt/widgets/nodes/Transform/count_records.py`. **Core:** `core/shaping/count.py`.
- **Today:** EAGER. `frame.select(pl.len()).collect().item()` (`count.py:21`), then wrapped as a one-row frame.
- **Target:** return `frame.select(pl.len().alias("Count"))`, which stays lazy. The live chip stays as it is.
- **Phase:** P1. **Effort:** XS.

### Running Total
- **Qt:** `qt/widgets/nodes/Transform/running_total.py`. **Core:** `core/shaping/running_total.py`.
- **Today:** LAZY. `cum_sum` over the partition (`:36`). The result depends on row order within each group.
- **Target:** make the order explicit: `over(group, order_by=row_index)`. Add order tests (D2).
- **Phase:** P2. **Effort:** S.

### Transpose
- **Qt:** `qt/widgets/nodes/Transform/transpose.py`. **Core:** `core/shaping/transpose.py`.
- **Today:** LAZY. An unpivot, `replace_strict`, then a global sort on `(__block, __row)`.
- **Target:** keep the explicit order keys. Measure the global sort (S1, S5) before changing it.
- **Phase:** P2. **Effort:** S.

### Pivot
- **Qt:** `qt/widgets/nodes/Transform/pivot.py`. **Core:** `core/shaping/reshape.py` (`run_pivot`, `apply_pivot` at `:53`).
- **Today:** LAZY-WITH-COLLECT. The aggregated frame is collected (`reshape.py:83`). Distinct header values are collected to enforce `MAX_PIVOT_COLUMNS` = 500 (`:88-95`, TD-SHAPE-061). The pivot itself is eager (`:117`, `:127`), followed by a sort (`:125`). `LIVE_CAP_ROWS` = 5,000,000 is inert (D6).
- **Target:** pass 1 collects the distinct values lazily, bounded to 501 rows (B2). Pass 2 is a lazy `group_by`, then `LazyFrame.pivot(on_columns=...)`. Keep the column naming (`separator`, `column_naming`) and the column order (`sort_columns`, `maintain_order`). Cache the input if the two passes cost too much (S6).
- **Phase:** P3. **Effort:** M.

### Unpivot
- **Qt:** `qt/widgets/nodes/Transform/unpivot.py`. **Core:** `core/shaping/reshape.py` (`run_unpivot`, `:191`).
- **Today:** LAZY. Sorts on `__pos` with `maintain_order` (`:183`).
- **Target:** keep.
- **Phase:** P1. **Effort:** XS.

## Report

### Graph
- **Qt:** `qt/widgets/nodes/Report/graph.py`. **Core:** `core/shaping/graph.py` (pass-through), `core/charts.py`.
- **Today:** the pass-through is LAZY. The chart is built on the GUI thread (`graph.py`, `build_spec`). `_collect_points` sorts a line chart with `maintain_order` (`charts.py:286`), then collects `head(limit + 1)` (`:299-301`). Partitioning runs on the bounded result (`:322`). The chart reads `frames[0]`, which after a Run is the 100-row live sample (F1, probe: 100 rows against 1,008).
- **Target:** fix the hook order in `executor.py`, so `after_execution` runs after `result.variables` is set (F1). Apply the chart source policy (D7). Keep the chart pipeline lazy and bounded, using top-k for line charts if S5 confirms it. Moving the build off the GUI thread is optional.
- **Phase:** P1 for the fix, which needs your approval first, and P8 for the pipeline. **Effort:** S for the fix, M for the pipeline.
