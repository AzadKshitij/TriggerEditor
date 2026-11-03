# Lazy data processing for every node

_Plan only, 2026-10-26. Nothing in `src/` was changed to write this. Per-node details are in [nodes.md](nodes.md)._

## Goal

Every node keeps its data as a Polars `LazyFrame` plan from File Input to File Output or to a preview. A node collects a table only at a boundary listed below. Run processes the whole input. Live editing keeps the 100-row sample (`LIVE_SAMPLE_ROWS`, `core/shaping/common.py:81`).

## Verified facts this plan rests on

- **Node count.** 26 nodes are registered (`qt/widgets/nodes/__init__.py:16-192`): the 25 in [NODE_REFERENCE.md](../NODE_REFERENCE.md) plus Join/Union, which the reference omits.
- **Polars 2.0.0 (pinned in `uv.lock`), checked locally:**
  - `LazyFrame.pivot` requires `on_columns`, so the distinct values must be known first.
  - `sort`, `group_by`, `unique` and `join` take `maintain_order`.
  - `Expr.over(order_by=...)`, `Expr.shuffle(seed)`, `Expr.hash(seed)`, `LazyFrame.top_k` and `LazyFrame.cache` exist.
  - `join(how="anti")` and `how="semi"` work. Test result: anti-left `[1]`, anti-right `[4]`, semi `[2, 3]`, inner 2 rows, full outer 4 rows.
  - `sink_csv`, `sink_parquet`, `sink_ndjson` and `sink_ipc` stream. `collect_batches` and `sink_batches` exist but are unstable and slower.
  - There is no `LazyFrame.sample` or `shuffle`, and no `melt` (use `unpivot`).
  - Per the 2.0 upgrade notes, the streaming engine does not guarantee row order for `unpivot`, `group_by` or joins unless `maintain_order` is set.
  - `join_where` is experimental and does not preserve row order.
- **DuckDB 2.0.0, checked locally:** `DuckDBPyRelation.pl(lazy=True)` returns a Polars `LazyFrame`. Its plan shows a `PYTHON SCAN` source. The eager `pl()` also exists. Whether DuckDB re-runs on every collect, whether pushdown reaches it, and whether a registered `LazyFrame` is collected first are **not verified**. They are spike S1.
- **Survey.** Two read-only inventories covered the core modules and the Qt layer. The line references below were checked with grep and reads on the worktree, except items marked _(spike)_.

## Where things stand

| Class | Meaning | Nodes |
|---|---|---|
| LAZY | Plans only, no full collect in the runner | GroupBy, Select, Sort, Unique, Split, Normalize, Record ID, Select Records, Find and Replace, Date Helper, Append, Join, Running Total, Transpose, Unpivot, Graph |
| LAZY, custom path | Lazy, but the logic lives in the Qt module | Union |
| MIXED | Part lazy, part eager | File Input, File Output, Filter |
| LAZY-WITH-COLLECT | Lazy plan with a collect on the way | Pivot |
| EAGER | Collects or builds a whole table | Cleansing, Formula, Rows, Reconcile, Count |

Full per-node status is in [nodes.md](nodes.md).

## Rules the rewrite follows

- **R1.** Core runners take and return `LazyFrame`s. A runner never calls `collect()` except at a boundary (B1 to B9 below).
- **R2.** Schema comes from `collect_schema()`. A data-dependent output shape gets a bounded two-pass plan, as Pivot does.
- **R3.** Row order is a contract only where a node declares it. Those nodes use `maintain_order` or an explicit order key such as `over(order_by=...)`, and each has an order test.
- **R4.** Guards that depend on data (pivot columns, candidate pairs) are computed lazily or with bounded collects, and keep their `TD-SHAPE-*` codes.
- **R5.** Expressions come first. UDFs go through `map_batches` and must be pure. No Python row loops over frames.
- **R6.** All DuckDB use goes through one adapter: relation to `pl(lazy=True)`. The node owns the connection's lifetime (spike S1).
- **R7.** Output uses `sink_*` for CSV, Parquet, NDJSON and IPC. Excel and JSON get streaming writers (spikes S2 and S3).
- **R8.** Input uses scans for CSV, TXT, Parquet and NDJSON. Excel, JSON, SQLite and DuckDB keep bounded or eager reads until a spike shows a lazy route.
- **R9.** Chips and `describe()` use bounded lazy aggregates. They must not regenerate lists or collect 10,000 rows on every evaluation.
- **R10.** Tests: a laziness guard (count `LazyFrame.collect` and `DuckDBPyRelation.pl`), schema equality, and equivalence with today's golden outputs.

## Boundaries: where a collect is allowed

| # | Boundary | Bound | Where |
|---|---|---|---|
| B1 | Scalar aggregate for a guard or summary | one row | Count, Reconcile summary and guards |
| B2 | Pivot distinct header values | at most 501 rows | Pivot pass 1 |
| B3 | One-to-one assignment over candidate pairs | `MAX_CANDIDATE_PAIRS` (5,000,000), key columns only | Reconcile (D5) |
| B4 | Split shuffle, one integer column | one column | Split (D1) |
| B5 | Preview and chart collects | 1,000 rows or 2 MB; 2,001 chart points | Preview dock, Graph |
| B6 | Select bulk auto-detect sample | 1,000 rows, user action | Select dialog |
| B7 | Error locator and attribution collects on failure paths | `row_cap` (5,000,000 rows) | Error enrichment (F4) |
| B8 | Excel, JSON, SQLite and DuckDB reads until a lazy route is proven | whole file | File Input (D4) |
| B9 | Excel and JSON writers until streaming writers exist | whole frame | File Output (D4) |

## Decisions needed

- **D1. Split.** Keep the seeded shuffle, using boundary B4 for the index column, or switch to a hash-based assignment with `Expr.hash(seed)`. The hash version is fully lazy but changes which rows land in which split for existing seeds. _Proposed: keep the shuffle for now._
- **D2. Row-order contract.** Which nodes promise input order? _Proposed:_ Record ID, Running Total, Select Records (first and last), Unique (keep first), Transpose, and the left output of Join. Measure the cost of `maintain_order` first.
- **D3. SQL-backed nodes (Filter expression mode, Formula).** Keep DuckDB behind the adapter, or translate to Polars expressions. _Proposed: adapter first (R6), translation later._
- **D4. Excel, JSON, SQLite and DuckDB sources; Excel and JSON output.** _Proposed:_ streaming writers for output, bounded reads for input until S1 and S4 finish.
- **D5. Reconcile assignment.** Keep the iterative assignment as boundary B3, or redesign it as lazy window logic. _Proposed: keep B3 now._
- **D6. `LIVE_CAP_ROWS`.** Pivot (5,000,000) and Reconcile (200,000) can no longer trigger, because live inputs are capped at 100 rows. _Proposed: remove the path and the cap check._
- **D7. Graph chart source.** Chart the run result when a run has finished, and the live sample only before the first run. _Proposed, together with fix F1._
- **D8. Filter expression NULLs.** A row whose predicate evaluates to NULL is dropped from both outputs today, because `WHERE NOT (NULL)` is not true. The rewrite must either keep that or route those rows to the unmatched output. _Needs a test first, then a decision._
- **D9. Legacy File Input path.** Route it through `build_source`, or keep it with a metadata cache (F2). _Proposed: cache now, retire later._

## Defects found during the survey

- **F1 (high, regression from the live-sample change).** A Graph charts the 100-row live sample after a Run. Cause: `executor.py:399` calls `after_execution(result.variables)` before `result.variables` is set at line 408. The field defaults to `{}` (line 40), so the Graph's hook gets nothing, `_run_frame` stays empty, and `frames[0]` keeps the live `head(100)`. A temporary probe, since deleted, showed the chart at 100 rows against a run of 1,008 rows. Before the live-sample change, `frames[0]` held the full live frame, so the chart showed the full data. The existing tests miss it: `tests/e2e/test_graph_run.py:64` checks only that `frames[0]` is not `None`, and `tests/unit/test_graph_node.py:175` passes the run frame in directly.
- **F2 (medium).** The legacy File Input path re-reads its file on every evaluation. `processInputs` (`file_input.py:1815`) calls `check_file_path` (`:1157`), which calls `loadFile` (`:1171`). For Excel that is a full sheet read each time. For CSV it adds a `head(10).collect()` (`:1597`).
- **F3 (medium).** The Reconcile pair guard collects both inputs before it counts pairs (`reconcile.py:447-448`, and `estimate_pairs` in `common.py:112-130`).
- **F4 (medium).** The error locator and attribution collect up to `row_cap` rows on failure paths (`core/errors/attribution.py:64`, `core/errors/locator.py:137` and `:147`).
- **F5 (low).** Count collects to a scalar and then wraps it (`count.py:21`).
- **F6 (low).** The File Output `use_streaming` setting is stored but never read (`file_output.py:13`, Qt `file_output.py:264`).
- **F7 (low).** The live cap check runs an extra plan for Pivot and Reconcile, although it cannot trigger (`shaping_support.py:302` and `:312-314`).
- **F8 (low).** Cleansing computes `null_count` statistics that nothing reads (`cleansing_util.py:84`, `:130`, `:180`, `:195`).
- **F9 (low).** The Date Helper chip reads `head(10_000)` while its text says "first 100 rows" (`date_helper.py:222`).
- **F10 (low).** Docs drift. `NODE_REFERENCE.md` omits Union, says File Output writes only CSV, Parquet or Excel (the code also writes NDJSON, IPC and JSON), and describes Graph as matplotlib-only.
- **F11 (low).** Enum members with no node: `IONodes.BROWSER`, `IONodes.TEXT_INPUT`, `TransformNodes.ARRANGE`. Also an empty module at `Documentation/comment.py`.
- **F12 (info).** After a Run nothing is collected or cached. A node that feeds several consumers re-runs its upstream plan each time. Measure this and add `cache()` at fan-out points.

## Phases

- **P0. Foundations.** Add the laziness guard helper, a schema-equality test, and an opt-in benchmark on a 10-million-row CSV. Run spikes:
  - **S1.** DuckDB `pl(lazy=True)`: streaming, pushdown, re-execution per collect, and whether `register(LazyFrame)` collects first.
  - **S2.** Incremental Excel output with openpyxl in write-only mode. xlsxwriter is not installed here.
  - **S3.** A streaming JSON-array writer, checked against `write_json` output.
  - **S4.** A bounded fastexcel read (`n_rows`).
  - **S5.** Whether Polars rewrites `sort` plus `head` into a top-k.
  - **S6.** What `cache()` saves at fan-out points.
- **P1. Quick wins.** Count lazy (F5). Normalize, Select, Sort, Unique, Unpivot, Append and GroupBy get guard tests. The Find and Replace and Date Helper chips become lazy aggregates (F9). Remove `use_streaming` (F6). Remove the live cap (D6, F7). Cache the legacy File Input read (F2, D9). Fix the Graph hook order and chart source (F1, D7), which needs your approval first.
- **P2. Order contracts.** Record ID uses `over(order_by=...)`. Running Total uses an explicit order key. Select Records uses `top_k`. Transpose keeps its explicit order keys. Join becomes three plans: inner, plus anti joins for the two unmatched sides.
- **P3. Pivot and Rows.** Pivot becomes two passes: lazy distinct values (B2), then lazy `group_by` plus `pivot(on_columns=...)`. Rows is vectorised with `int_range`, `date_range` and a cross join, and its cap is computed arithmetically. Split follows D1.
- **P4. Cleansing and SQL nodes.** Cleansing becomes expressions, with one bounded pass for all-null columns (B1). Filter expression mode uses the DuckDB adapter (D3, D8). Formula chains DuckDB relations.
- **P5. Sources and Union.** JSON, SQLite, DuckDB and Excel follow S1 and S4 (D4). Move Union into `core/shaping/union.py` with a `run_node`, so the generated code and the live path share it.
- **P6. Sinks.** Excel and JSON get streaming writers (S2, S3). Error-locator caps are reviewed (F4).
- **P7. Reconcile.** Candidates, the pair-count guard (F3), the summary and unmatched rows become lazy. Only the assignment stays as boundary B3 (D5).
- **P8. Charts.** Aggregation and top-k in one lazy plan. Apply the chart source policy (D7). Moving chart builds off the GUI thread is optional.
- **P9. Cleanup.** Remove dead code and update `NODE_REFERENCE.md` and `DATA_LIMITS.md`.

## Acceptance for each node

1. `run_node` returns a `LazyFrame`, or the node's boundary is listed above.
2. `collect_schema()` matches the collected schema on the fixtures.
3. Existing unit, e2e golden and UI tests pass. New order and NULL tests pass.
4. A benchmark result is recorded: time and peak memory, against the baseline from P0.

## Testing approach

- **Laziness guard.** Count `pl.LazyFrame.collect` and `DuckDBPyRelation.pl` calls during `run_node`. Lazy-only nodes must show zero. Boundary nodes must show only the calls listed in the boundary table.
- **Equivalence.** Keep the e2e goldens in `tests/e2e/fixtures/expected`. Add targeted fixtures for NULL predicates (D8), order-sensitive nodes (R3) and Pivot column naming.
- **Benchmarks.** Opt-in, on a 10-million-row CSV. Select, Filter and File Output run end to end. Also GroupBy, Join, Pivot, Reconcile, Excel output and JSON output. Peak memory needs a measurement tool; `psutil` is not confirmed to be installed.

## Known flake, not part of this plan

In the e2e run from earlier in this session, `test_folder_run_failure_names_file` finished with a teardown error. The error was `RuntimeError: Signal source has been deleted`, raised from `error_enricher.py:64` through `problems_store.py:87`. The test passes when run alone, three times in a row. It looks like a race in error-enrichment teardown. It is not yet traced to this change.
