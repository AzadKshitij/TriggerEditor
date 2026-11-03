# 05 - Data Profile node (Alteryx Field Summary / Browse equivalent)

Status: implementation plan, no source changed. Read `docs/plan/00-codebase-brief.md` first
(sections 3.7 recipe, 4 evaluation, 5 dock, 6 undo, 9 tests, 10.3 summary outputs, 11.3 `DataProfile`).
Every decision below is final; implement exactly as written, **except where section 11 supersedes it**.
Written against Polars 1.44.2 / Python 3.13.12; revalidated 2026-10-28 on Polars 2.0.0 / Python 3.14.8 (section 11).

> **Revalidated 2026-10-28 (branch `feature` @ `984a1fc`). Read section 11 before coding.**
> * Engine (`core/profile.py`, sections 3.2-3.7, 3.12, commit 1): verified on Polars 2.0.0 / Python 3.14. One fix applied below (`is_in(...implode())`).
> * Node layer (3.8 data flow, 3.9-3.11 dock/undo, commits 2-4): **superseded by 11.3.** The node base was refactored into `ShapingNode`/`ShapingContent` (plan 07) after this plan was written; hand-written `TriggerNode` + content classes are no longer the pattern.
> * Line numbers in section 2 are from `71b4041` and have drifted; 11.2 lists the re-verified anchors.
> * Excel export depends on plan 06, which has not landed (11.4).
> * Three new flags, a flag severity map and a changed `min_value`/`max_value` rule for text columns that look numeric or date-like (11.5) amend 3.3 and 3.7 and the expected values in 6.1 and 6.4.
Commands use `.venv\Scripts\python.exe` (the brief explains why not bare `uv run`).

## 1. Goal and non-goals

Goal: a **Data Profile** node (family Report, op id `report.data_profile`) with one input and two outputs:
socket 0 `D` = the input passed through **unchanged** (same object live, same variable value in Run);
socket 1 `P` = a table, one row per input column, with the metrics in 3.3. A Config Dock shows a sortable
profile table, a per-column detail pane (histogram or top-value bars), copy/CSV/Excel export, and states when
figures come from a sample. Built for CSVs where File Input yields all-String columns (brief fact: CSV is
read with `infer_schema=False`), so "does this text column look like numbers/dates" is first-class.

Non-goals (decided): no column picker (put a Select node upstream; reason: AGENTS forbids per-node
rewrites of Select UI); no correlations/outlier tests (plan 04 owns tests); no writing files from `get_code`
(File Output does that); no Excel formatting beyond a frozen header; no new dependency; no change to
`ExecutionResult`, `WorkflowWorker`, `getSocketValue`, `_prune_node_results`.

## 2. Current state (verified 2026-10-21 on `main` @ `71b4041`)

| Fact | Where |
|---|---|
| `ReportNodes` has one member `GRAPH`; append new members at the end | `core/node_configuration.py:64-65` |
| Lazy node specs; Report spec pattern; helper-module exclusion set | `qt/widgets/nodes/__init__.py:122-128` (Graph), `:156-159` (`_LAZY_HELPER_MODULES`) |
| Shift+A menu and palette read `NODE_REGISTRIES[NodeTypes.REPORT]` automatically | `qt/helpers/context_menu_mixin.py:40-45` |
| Precedent: a node emitting an eager summary frame and collecting inside `get_code()` | `Transform/count_records.py:104-112` (live), `:124-144` (codegen) |
| Declared outputs of a node = `node.param` entries, so both of our variables survive Run pruning | `qt/helpers/workflow_execution_mixin.py:220-232` |
| Run executor has a hard 30 s per-node exec timeout (not configurable from UI) | `core/ExecutionCheck/executor.py:94`, `:325` |
| `frame_schema(frame)` resolves a lazy plan's schema | `qt/node_base.py:59` |
| Dock sweep skips children of a widget with `_undo_composite = True`; scroll-area aware | `qt/node_base.py:518-585` (`iter_dock_widgets`, `registerUnboundDockWidgets`, `_inside_composite`) |
| `ConfigDock.updateConfig` returns early for the same content unless `force=True`; so live widgets must refresh themselves | `qt/docks/node_config.py:118-123` |
| Bounded preview collect, lazy frames accepted (`is_previewable` accepts LazyFrame/DataFrame) | `qt/models/preview_sampling.py:26,103`; Data Preview unwraps `entry["data"]` at `qt/docks/data_preview.py:328-346` |
| Off-thread pattern with keep-alive set and request ids | `qt/models/preview_worker.py:33-41` (`_keep_alive`), `:44` (`PreviewCollectWorker`) |
| Existing exporters write via `DataFrame.write_excel` (needs undeclared xlsxwriter, so broken) | `qt/models/polars_table_viewer.py:1161-1209` |
| Excel writing is centralised by plan 06 in the Qt-free helper `trigger_designer.core.excel.write_frame_xlsx` (the only module importing `xlsxwriter`); plan 06 owns the dependency | coordinator decision |
| Theme colours for painted widgets: `get_theme_manager().color(token)`; tokens `danger warning success accent_primary text_primary text_secondary border_subtle background_hover` exist in every theme | `qt/theme_manager.py:589,773`; `resources/qt/themes/dark.json` |
| `IconButton.themed`, `Chip(text, tone)`, `ConfigSection`, `FormRow`, `NoWheelComboBox`, `EmptyStateLabel` | `qt/widgets/common/config_widgets.py:57,106,176,326,547,157,797` |
| UI icon ids available: `icon_save`, `icon_refresh`, `icon_options`, `icon_search`; **no copy / Excel icon** | `qt/resources.json:115-134` |
| `QTableView#ColumnTable` QSS already exists (reuse, no new QSS) | `resources/qt/themes/base.qss:2178-2184` |
| Node icons are 100x100 rounded squares; Report colour `#1A70B1` | `resources/qt/images/node_icons/Report/Graph.svg` |
| `pl.defer(fn, schema=...)` exists in the installed Polars: lazy, runs `fn` on every collect, no memoisation | verified, 3.12 |
| An unquoted empty CSV field is `null`; a quoted `""` is the empty string `''` | verified, 3.12 |

## 3. Final design

### 3.1 Decision table (one line of reasoning each)

| Decision | Choice | Reason |
|---|---|---|
| Family / enum | `ReportNodes.DATA_PROFILE` (appended after `GRAPH`; the integer value depends on append order across plans, but op ids are stable names so it does not matter) | Browse/Field Summary are reporting tools; Report family is otherwise tiny |
| Title / icon | `"Data Profile"`, `node_data_profile` (new SVG, 3.10) | pinned by `test_node_titles.py` |
| Sockets | `inputs=[1]`, `outputs=[3, 1]`, `output_text=["D", "P"]` | socket 0 data, socket 1 profile |
| Profile socket live value | `pl.defer(...)` LazyFrame with exact `PROFILE_SCHEMA` | lazy by convention, never freezes the GUI in `processInputs`; schema known without computing |
| Profile socket in Run | eager `DataFrame` from `profile_table(...)` inside `get_code` | brief fact 2: only code that collects inside `get_code` does work; Count precedent |
| Cache | content keeps one `(key, DataProfile)`; `key = (epoch, settings.key())`; `epoch` increments only when `processInputs` receives a different frame object | uses the existing dirty/eval cache; settings changes recompute only the profile |
| Compute thread | `ProfileWorker(QThread)` for the dock; polars threads for the deferred frame; a `threading.RLock` serialises both | one in-flight compute per node, second caller reads the cache |
| Auto compute | only when the dock view is visible for this node (or a consumer collects the deferred frame) | unselected nodes never scan data |
| Default sample mode | `full` | audit use: nothing silently sampled; the notice and the `sampled` column cover sampled modes |
| Exact vs approximate distinct | exact `n_unique` when rows profiled <= `approx_distinct_threshold` (default 2,000,000), else `approx_n_unique`; column `distinct_is_approx` says which | hash sets for 1M+ rows of long strings are the memory risk |
| Excel export | call `write_frame_xlsx` from `core/excel` (shape in commit 2); if the import or the call fails, show the message in the chip, never raise | product owner: XlsxWriter, behind plan 06's helper; this plan imports no Excel library |
| Histogram | 20 bins (setting 5..100), equal width over finite min..max | no matplotlib; painted widget |
| Column scope | all columns | see non-goals |

### 3.2 Settings: serialization keys and defaults (`SerializableContentMixin.serialized_state_schema`)

| Key / attribute | Default | Range / values | Meaning |
|---|---|---|---|
| `sample_mode` | `"full"` | `"full"`, `"head"`, `"random"` | which rows are profiled |
| `sample_rows` | `100000` | 1000..100000000 (spin step 10000) | N for head/random |
| `seed` | `42` | 0..2147483647 | random sampling seed |
| `top_n` | `5` | 1..50 | frequent values per column |
| `approx_distinct_threshold` | `2000000` | 10000..2000000000 (step 100000) | rows above which distinct is approximate |
| `histogram_bins` | `20` | 5..100 | histogram bins |

No other state is persisted (sort order, selection, search text are UI state). Old files have no keys, so
defaults apply. `deserialize` clamps out-of-range numbers into range and replaces an unknown `sample_mode`
with `"full"` (implemented in `_normalize_settings`, also called by `validate_loaded_state`, which returns
`[]` after clamping silently - decided: a clamped setting is not worth a warning dialog).

### 3.3 Output schema of the Profile socket (exact; `PROFILE_SCHEMA` in `core/profile.py`)

One row per input column, in input order. Column names and dtypes are a contract (plans 02/06 and golden tests):

| Column | Dtype | Definition |
|---|---|---|
| `column` | String | input column name |
| `position` | Int64 | 1-based position |
| `dtype` | String | `str(polars dtype)`, e.g. `String`, `Int64`, `Decimal(precision=38, scale=2)` |
| `row_count` | Int64 | rows profiled (sample size when sampled) |
| `null_count`, `null_pct` | Int64, Float64 | nulls; `null_count*100/row_count` (0.0 when no rows). NaN is **not** null |
| `empty_count`, `empty_pct` | Int64, Float64 | String only: values `== ""`. Null for other dtypes ("not applicable") |
| `blank_count` | Int64 | String only: stripped value is `""` (includes empty) |
| `whitespace_count` | Int64 | String only: value differs from `strip_chars()` (leading/trailing whitespace; includes whitespace-only) |
| `distinct_count`, `distinct_is_approx`, `distinct_pct` | Int64, Boolean, Float64 | distinct **non-null** values (NaN counts as one value); `% = distinct*100/(row_count-null_count)`; null for List/Array/Struct/Object |
| `min_value`, `max_value` | String | text of min/max: ints/decimals/strings/dates/times/durations/categoricals raw; floats = finite values only; String columns = lexicographic (an empty string is the minimum) |
| `min_length`, `max_length` | Int64 | String only: `str.len_chars()` over non-null values (characters, so `日本語` = 3) |
| `mean_value`, `median_value`, `std_value`, `sum_value` | Float64 | over the **numeric basis** (below), finite values only; `std` is sample std (ddof 1); sum is Float64 (Int64/Decimal are cast; exactness beyond 2^53 is not promised) |
| `min_numeric`, `max_numeric` | Float64 | finite min/max of the numeric basis (feeds the histogram) |
| `numeric_basis` | String | `"native"` (int/float/decimal column), `"parsed_text"` (String column with at least one value matching `NUM_RE`; stats use only those plain-format values), `""` otherwise |
| `negative_count`, `zero_count` | Int64 | over the numeric basis (null when basis is `""`) |
| `nan_count`, `inf_count` | Int64 | native numeric only (floats; 0 for ints) |
| `numeric_like_count` | Int64 | String only: stripped value matches `NUM_RE` (plain `-12.5`, `.5`, `1e5`) |
| `integer_like_count` | Int64 | String only: matches `INT_RE` (max 18 digits) |
| `date_like_count` | Int64 | String only: stripped value parses (`strict=False, exact=True`) under any of the 9 date or 4 datetime formats |
| `bool_like_count` | Int64 | String only: case-insensitive `true false yes no y n` |
| `leading_zero_count` | Int64 | String only: matches `LEAD0_RE` (`007`, not `0.5`, not `0`) |
| `trailing_minus_count` | Int64 | String only: `123-`, `12.5-` (SAP style) |
| `decimal_comma_count` | Int64 | String only: `1,5`, `12,25`, `1.234,56` (1-2 digits after the comma, or dot-grouped thousands) |
| `top_values` | String | JSON text `[["value",count],...]`, at most `top_n` entries, ordered count desc then value text asc; value text truncated to 100 chars with `...` char; `[]` when none |
| `top_value`, `top_count` | String, Int64 | first entry of `top_values` (null when none) |
| `suggested_type`, `suggested_confidence` | String, Float64 | 3.6 |
| `flags` | String | comma-separated flag codes in the fixed order of `FLAG_ORDER`, `""` when none |
| `sampled` | Boolean | profile was computed on a sample |

Null semantics (one rule): every count/percentage excludes nulls from the denominator it names;
"not applicable for this dtype" is `null`, "applicable and zero" is `0`. All-null columns have null
min/max/mean/median/std/sum, `distinct_count = 0`, `top_values = []`.

### 3.4 Dtype classes (`dtype_class`) and what each gets

`numeric` (int/uint/float/decimal): null, nan/inf, finite stats, min/max, distinct, top-N, histogram.
`string` (`pl.String` only): everything in 3.3 including text parsing, suggested type, format flags.
`categorical` (Categorical/Enum): null, min/max (as String), distinct, top-N; suggested type = native dtype.
`boolean`, `temporal` (Date, Datetime, Time): null, min/max, distinct, top-N (Duration: no top-N, `cast(String)` is unsupported).
`duration`, `binary`, `null` (pl.Null): null, distinct (duration/binary), no top-N. `nested` (List/Array/Struct/Object): null count only.
Non-String columns get `suggested_type = str(dtype)`, confidence 1.0.

### 3.5 Query plan (exactly these passes; `DataProfile.passes` counts them)

| Pass | When | Query |
|---|---|---|
| P0 | modes `full` and `random` | `lf.select(pl.len())` (row count; also decides exact vs approximate distinct) |
| PS | modes `head`, `random` (when total > N) | materialise the sample: `lf.head(N).collect()` or the seeded index filter; later passes run on that in-memory frame |
| P1 | always | **one** `select` of every aggregate for every column (`pl.len()` + `_aggregate_exprs`), result is one row |
| P2 | if any column has data | one `pl.collect_all([...])`: per column `group_by(v).agg(len).sort([n, v], [desc, asc]).head(top_n)` plus one frame of per-format date counts for String columns with `date_like_count > 0` |
| P3 | if any column has `min_numeric < max_numeric` | one `pl.collect_all([...])`: per numeric-basis column a bin index `group_by` count |

Budget: `full` <= 4 collect calls, `head` <= 4, `random` <= 5 (`passes` asserted in tests). Measured on this
machine (Python 3.13, Polars 1.44.2): 1M rows x 30 columns (10 digit-strings, 10 floats, 10 ints) in memory 7.8 s;
1500 columns x 3 rows 4.3 s; all-30-String CSV via `scan_csv(infer_schema=False)` 22.3 s full, 2.3 s head 100k,
2.9 s random 100k. In `full` mode on a CSV the source is re-scanned in P0-P3 (4 scans); that is the cost of
keeping memory flat; use `head`/`random` on huge files.

### 3.6 Sampling rules

* `full`: profile everything. `sampled = False`.
* `head`: `lf.head(N)` collected once. `sampled = (rows collected >= N)`: if the source had fewer than N rows nothing was dropped.
* `random`: if `total <= N` behave as `full` (no sample, `sampled=False`); else
  `idx = sorted(random.Random(seed).sample(range(total), N))` and keep rows whose `with_row_index` equals one of `idx`
  (`sampled=True`). Same input order + same seed + same N gives identical rows (tested). It depends on the source row order being
  stable (a CSV/parquet scan is; a hash-join output may not be).
* Sampled figures are sample statistics: counts are not scaled up; `row_count` is the sample size. The dock shows a `Chip`
  with tone `accent`: `"Sample: first 100,000 rows"` / `"Sample: random 100,000 rows (seed 42)"`; full data shows a muted chip
  `"Full data: 1,000,000 rows"`.

### 3.7 Suggested type and quality flags (thresholds are module constants in `core/profile.py`)

Base for String columns: `base = rows - null_count - blank_count`; `fam = numeric_like + trailing_minus + decimal_comma + grouped(comma thousands)`.
First matching rule wins (`_suggest`): `base == 0` -> `Unknown`/0.0; `integer_like/base >= 0.98` and any leading zero -> `String`/1.0
(converting would drop zeros); `integer_like/base >= 0.98` -> `Int64`; `fam/base >= 0.98` -> `Float64`; `bool_like/base >= 0.98` -> `Boolean`;
`date_like/base >= 0.98` -> `Datetime` if datetime-with-time values are at least half of them else `Date`; otherwise `String`/1.0.
Confidence = share of base values that parse as the suggestion (rounded to 4 places); `String` is always 1.0 and a mixed column is
told apart by the `mixed_numeric_text` flag.

| Flag | Exact rule |
|---|---|
| `all_null` | rows > 0 and `null_count == rows` |
| `all_blank` | String, rows > 0, not all null, `base == 0` |
| `constant` | rows >= 2, no nulls, `distinct_count == 1` |
| `high_cardinality` | non-null rows >= 20 and `distinct/non-null >= 0.95` |
| `mostly_null` | `null_pct >= 50.0` and not `all_null` |
| `mixed_numeric_text` | String, `0.02 <= fam/base < 0.98` |
| `leading_zeros` | String, `leading_zero_count >= 1` and `integer_like/base >= 0.5` |
| `trailing_minus` | String, `trailing_minus_count >= 1` and `fam/base >= 0.5` |
| `decimal_comma_suspected` | String, `decimal_comma_count >= 1`, `fam/base >= 0.5`, and `decimal_comma_count > dot_decimal_count` (values like `20.5`) |
| `leading_trailing_whitespace` | `whitespace_count >= 1` |
| `numeric_as_text` / `date_as_text` | String column whose suggestion is `Int64`/`Float64` / `Date`/`Datetime` |
| `nan_values` / `inf_values` | `nan_count > 0` / `inf_count > 0` |

### 3.8 Node data flow

* `processInputs`: take `entry = input_values[0][socket_index]`; `frame_schema(entry["data"])` inside try (a bad plan -> tooltip
  `Data Profile: <error>`, `markInvalid`, return `None`); bump `epoch` only if `entry["data"] is not content.incom_data`; set
  `content.incom_data/incoming_variable`; return `self.param = [{"data": entry["data"], "variable_name": main_var},
  {"data": content.profile_lazy(), "variable_name": profile_var}]`. Variables: `var_dprof_<id>` and `var_dprof_profile_<id>`.
  Finish with `content.on_inputs_processed()` (re-requests the dock profile when the view is alive).
* `get_code`: unwired -> `import polars as pl`, `from trigger_designer.core.profile import empty_profile_frame`, main = `pl.DataFrame()`,
  profile = `empty_profile_frame()`. Wired -> `main = <incoming>` and
  `profile = profile_table(<incoming>, **{settings dict repr})` (kwargs are primitives; repr is safe, no f-string interpolation of user text).
  Idempotent, pure. Run recomputes from the generated plan (not the live cache) because Run does not re-evaluate the graph.

### 3.9 Threading rules

`profile_frame` is pure and thread-safe (no Qt). `DataProfileContent.get_or_compute(key, frame, settings)` holds `self._lock`
(RLock) for the whole compute, stores the result only if `key` still equals the current key, and returns it; the worker thread and
the deferred frame both call it. A superseded compute cannot be cancelled (Polars limitation, same as preview): its result is dropped
by the request-id check. GUI never calls `profile_frame` directly.

### 3.10 Dock UI (all inside one root `ProfileDockView`, `_undo_composite = True`)

```
[ search (H30) ............ ][copy][csv][xlsx][recompute]      toolbar H40, margins 0
[ Chip: Full data: 1,000,000 rows | Sample: ... | Profiling... ]
+---------------------------------------------------------------+
| Column | Type | Null % (bar) | Distinct | Suggested | Flags    |  QTableView#ColumnTable, sortable
+---------------------------------------------------------------+
| detail pane: header (name, dtype, suggested+confidence, flags) |
| MiniBarChart (histogram for numeric basis, else top-N bars)    |
| stats rows (label: value, only non-null)                       |
+---------------------------------------------------------------+
> Options (collapsible ConfigSection, collapsed): Sample, Rows, Seed, Top values, Approx above, Bins
```
* Icons: copy `icon_copy` (new), CSV `icon_save` (existing), Excel `icon_export_excel` (new), recompute `icon_refresh`. Tooltips and
  accessible names: `"Copy profile to clipboard"`, `"Export profile as CSV"`, `"Export profile as Excel"`, `"Recompute profile"`.
  New SVGs (16x16, stroke `#D0D0D0`, copied style of `ui/refresh.svg`): `ui/copy.svg` two overlapping rounded rects;
  `ui/export_excel.svg` a page with an arrow and an `X` stroke.
* Table: model `ProfileTableModel` (6 visible columns above), `QSortFilterProxyModel` (`sortRole=Qt.UserRole`, filter on column name,
  case-insensitive, 300 ms debounce `QTimer`), `NullBarDelegate` paints the null-% bar with `get_theme_manager().color("warning")`
  (`"danger"` at 100 %) on a `border_subtle` track and the `12.3%` text in `text_primary`. Rows 22 px (as `ColumnTable`).
* Detail pane: selection change -> `detail_rows(cp)` (module function, Qt-free; ordered `(label, text)` pairs, thousands separators,
  floats `f"{x:,.6g}"`, pct `f"{p:.2f}%"`, `None` skipped) and `MiniBarChart.set_bars(labels, values, kind)` (numeric basis with a
  histogram -> `"hist"` with bin edge captions `min` and `max`; else top values -> `"freq"`; neither -> empty-state text).
* Copy: tab-separated text of the **full** profile frame (header + rows) via `profile_to_tsv`. Exports write the full frame, not the view.
* States (Chip text, no dialogs): loading, ready, failed (`"Profile failed: <error>"`, tone `accent`), export errors.

### 3.11 Undo

Settings only; every handler follows brief 6.3 (guard `is_syncing/is_restoring_history` -> mutate -> `refresh_dock_context()` ->
`evaluate.emit()` -> `push_property_change`). Texts and merge keys: combo `"Profile Sample Changed"` (none); rows
`"Profile Rows Changed"` `dprof-rows`; seed `"Profile Seed Changed"` `dprof-seed`; top `"Profile Top Values Changed"` `dprof-top`;
threshold `"Profile Distinct Threshold Changed"` `dprof-approx`; bins `"Profile Bins Changed"` `dprof-bins`. `_sync_widgets_from_model`
updates the six widgets with `blockSignals` and re-applies enabled state (`rows` enabled unless `full`; `seed` only for `random`).
The view root is `_undo_composite = True`, so the dock sweep binds nothing (no duplicate snapshot entries, search text is not undoable).
Do **not** add `history_stamp_callback`. Table sort/selection/search are UI state.

### 3.12 Verified Polars snippets (executed on 1.44.2; the commit-1 code was re-run on 2.0.0, see 11.1)

```python
lf.select(pl.len(), c.null_count(), (c == "").sum(), (st == "").sum(), (c != st).sum())     # st = c.str.strip_chars()
st.str.contains(r"^[+-]?\d{1,18}$").sum()                                                   # regex counts; (?i:...) groups work
pl.coalesce([st.str.to_date(f, strict=False, exact=True) for f in FORMATS]).is_not_null().sum()
pl.when(st.str.contains(NUM_RE)).then(st.cast(pl.Float64, strict=False))                    # gate: plain 'nan'/'inf' strings never parse
f.filter(f.is_finite()).median()   /   f.is_nan().sum()   /   f.is_infinite().sum()
c.drop_nulls().n_unique()   # NOTE c.n_unique() counts null as a value (verified: [1,None,1] -> 2)
c.drop_nulls().approx_n_unique()      # unsupported on List/Array/Struct (InvalidOperationError) -> skipped for "nested"
c.cast(pl.String)    # fails for List/Array/Duration (skipped), works for Decimal/Date/Time/Boolean/Categorical/Enum/Struct
work.select(v).group_by("v").agg(pl.len().alias("n")).sort(["n","v"], descending=[True, False]).head(n)   # deterministic top-N
pl.collect_all([lf1, lf2, ...])       # one call; shared scan; 1500 frames fine
b = ((xf - lo) / (hi - lo) * bins).floor().clip(0, bins - 1).cast(pl.Int64)   # xf = x.filter(x.is_finite()); filter BEFORE cast (NaN->Int64 raises)
pl.defer(fn, schema=PROFILE_SCHEMA)   # LazyFrame; collect_schema() does not call fn; each collect calls fn
```

## 4. Implementation steps (small commits; run the "done when" before each commit)

All commits: `ruff format` + `ruff check` on touched files first (AGENTS.md). Do not touch other plans' files.

### Commit 1 - `core/profile.py` (Qt-free) + core unit tests

Create `src/trigger_designer/core/profile.py` with exactly the code below (it was executed against the fixtures in section 6 on this
machine; output matched the hand-computed tables). Never `sys.path`-insert `core/` (the module name shadows the stdlib `profile`).
Then write `tests/unit/test_profile_core.py` (section 6.1).

```python
"""Qt-free data profiling (plan 05). Imports only stdlib, polars, orjson."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Any

import orjson
import polars as pl

TYPE_SHARE = 0.98  # share of non-blank values that must parse to suggest a type
MIXED_MIN = 0.02  # numeric share at/above which a text column is "mixed"
FAMILY_MIN = 0.5  # numeric-family share needed before a format flag fires
HIGH_CARD_MIN_ROWS = 20
HIGH_CARD_RATIO = 0.95
MOSTLY_NULL_PCT = 50.0
MAX_TEXT = 100  # characters kept of a top value / min / max text

INT_RE = r"^[+-]?\d{1,18}$"
NUM_RE = r"^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$"
DOT_DEC_RE = r"^[+-]?\d*\.\d+$"
TRAIL_RE = r"^\d+([.,]\d+)?-$"
DEC_COMMA_RE = r"^[+-]?(\d+|\d{1,3}(\.\d{3})+),\d{1,2}$|^[+-]?\d{1,3}(\.\d{3})+,\d+$"
GROUPED_RE = r"^[+-]?\d{1,3}(,\d{3})+(\.\d+)?$"
LEAD0_RE = r"^[+-]?0\d+$"
BOOL_RE = r"^(?i:true|false|yes|no|y|n)$"
DATE_FORMATS = (
    "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d", "%d-%m-%Y",
    "%d.%m.%Y", "%Y%m%d", "%d-%b-%Y", "%d %b %Y",
)
DATETIME_FORMATS = (
    "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S",
    "%d/%m/%Y %H:%M:%S", "%m/%d/%Y %H:%M:%S",
)
FLAG_ORDER = (
    "all_null", "all_blank", "constant", "high_cardinality", "mostly_null",
    "mixed_numeric_text", "leading_zeros", "trailing_minus",
    "decimal_comma_suspected", "leading_trailing_whitespace",
    "numeric_as_text", "date_as_text", "nan_values", "inf_values",
)

PROFILE_SCHEMA: dict[str, Any] = {
    "column": pl.String, "position": pl.Int64, "dtype": pl.String,
    "row_count": pl.Int64, "null_count": pl.Int64, "null_pct": pl.Float64,
    "empty_count": pl.Int64, "empty_pct": pl.Float64, "blank_count": pl.Int64,
    "whitespace_count": pl.Int64, "distinct_count": pl.Int64,
    "distinct_is_approx": pl.Boolean, "distinct_pct": pl.Float64,
    "min_value": pl.String, "max_value": pl.String,
    "min_length": pl.Int64, "max_length": pl.Int64,
    "mean_value": pl.Float64, "median_value": pl.Float64, "std_value": pl.Float64,
    "sum_value": pl.Float64, "min_numeric": pl.Float64, "max_numeric": pl.Float64,
    "numeric_basis": pl.String, "negative_count": pl.Int64, "zero_count": pl.Int64,
    "nan_count": pl.Int64, "inf_count": pl.Int64,
    "numeric_like_count": pl.Int64, "integer_like_count": pl.Int64,
    "date_like_count": pl.Int64, "bool_like_count": pl.Int64,
    "leading_zero_count": pl.Int64, "trailing_minus_count": pl.Int64,
    "decimal_comma_count": pl.Int64,
    "top_values": pl.String, "top_value": pl.String, "top_count": pl.Int64,
    "suggested_type": pl.String, "suggested_confidence": pl.Float64,
    "flags": pl.String, "sampled": pl.Boolean,
}

@dataclass(frozen=True)
class ProfileSettings:
    sample_mode: str = "full"  # "full" | "head" | "random"
    sample_rows: int = 100_000
    seed: int = 42
    top_n: int = 5
    approx_distinct_threshold: int = 2_000_000
    histogram_bins: int = 20

    def key(self) -> tuple:
        return (self.sample_mode, self.sample_rows, self.seed, self.top_n,
                self.approx_distinct_threshold, self.histogram_bins)

@dataclass
class ColumnProfile:
    name: str
    dtype: str
    count: int  # rows profiled (nulls included)
    null_count: int
    null_pct: float
    distinct_count: int | None
    min: str | None
    max: str | None
    mean: float | None
    sample_values: list[str]  # top-N value texts, most frequent first
    # --- plan-05 extensions (all defaulted; plan 06 reads only the fields above) ---
    position: int = 0
    empty_count: int | None = None
    empty_pct: float | None = None
    blank_count: int | None = None
    whitespace_count: int | None = None
    distinct_is_approx: bool = False
    distinct_pct: float | None = None
    min_length: int | None = None
    max_length: int | None = None
    median: float | None = None
    std: float | None = None
    sum: float | None = None
    min_numeric: float | None = None
    max_numeric: float | None = None
    numeric_basis: str = ""
    negative_count: int | None = None
    zero_count: int | None = None
    nan_count: int | None = None
    inf_count: int | None = None
    numeric_like_count: int | None = None
    integer_like_count: int | None = None
    date_like_count: int | None = None
    bool_like_count: int | None = None
    leading_zero_count: int | None = None
    trailing_minus_count: int | None = None
    decimal_comma_count: int | None = None
    datetime_like_count: int | None = None
    dot_decimal_count: int | None = None
    top_values: list[tuple[str, int]] = field(default_factory=list)
    date_format_hint: str = ""
    suggested_type: str = ""
    suggested_confidence: float = 0.0
    flags: list[str] = field(default_factory=list)
    histogram: list[int] = field(default_factory=list)
    sampled: bool = False

@dataclass
class DataProfile:
    row_count: int
    column_count: int
    columns: list[ColumnProfile]
    sampled: bool
    settings: ProfileSettings = field(default_factory=ProfileSettings)
    passes: int = 0
    seconds: float = 0.0

    def to_frame(self) -> pl.DataFrame:
        return profile_to_frame(self)

def empty_profile_frame() -> pl.DataFrame:
    return pl.DataFrame(schema=PROFILE_SCHEMA)

def dtype_class(dt: pl.DataType) -> str:
    if dt.is_numeric():
        return "numeric"
    if dt == pl.String:
        return "string"
    if dt == pl.Categorical or isinstance(dt, (pl.Categorical, pl.Enum)):
        return "categorical"
    if dt == pl.Boolean:
        return "boolean"
    if dt in (pl.Date, pl.Time) or isinstance(dt, pl.Datetime):
        return "temporal"
    if isinstance(dt, pl.Duration):
        return "duration"
    if dt == pl.Null:
        return "null"
    if dt == pl.Binary:
        return "binary"
    return "nested"  # List, Array, Struct, Object, Unknown

class _Collector:
    """Counts collect calls so tests can prove the pass budget."""

    def __init__(self) -> None:
        self.passes = 0

    def one(self, lf: pl.LazyFrame) -> pl.DataFrame:
        self.passes += 1
        return lf.collect()

    def many(self, frames: list[pl.LazyFrame]) -> list[pl.DataFrame]:
        self.passes += 1
        return pl.collect_all(frames)

def _aggregate_exprs(i: int, name: str, dt: pl.DataType, approx: bool) -> list[pl.Expr]:
    c = pl.col(name)

    def k(m: str) -> str:
        return f"c{i}__{m}"

    cls = dtype_class(dt)
    out: list[pl.Expr] = [c.null_count().alias(k("nulls"))]
    if cls == "numeric":
        f = c.cast(pl.Float64)
        fin = f.filter(f.is_finite())
        out += [
            f.is_nan().sum().alias(k("nan")), f.is_infinite().sum().alias(k("inf")),
            fin.min().alias(k("nmin")), fin.max().alias(k("nmax")),
            fin.mean().alias(k("mean")), fin.median().alias(k("median")),
            fin.std().alias(k("std")), fin.sum().alias(k("sum")),
            (fin < 0).sum().alias(k("neg")), (fin == 0).sum().alias(k("zero")),
            c.min().alias(k("min")), c.max().alias(k("max")),
        ]
    elif cls == "string":
        s = c.cast(pl.String)
        st = s.str.strip_chars()
        ln = s.str.len_chars()
        parsed = pl.when(st.str.contains(NUM_RE)).then(st.cast(pl.Float64, strict=False))
        pf = parsed.filter(parsed.is_finite())
        date_ok = pl.coalesce(
            [st.str.to_date(f, strict=False, exact=True) for f in DATE_FORMATS]
        ).is_not_null()
        dtm_ok = pl.coalesce(
            [st.str.to_datetime(f, strict=False, exact=True) for f in DATETIME_FORMATS]
        ).is_not_null()

        def cnt(e: pl.Expr, m: str) -> pl.Expr:
            return e.sum().alias(k(m))

        out += [
            cnt(s == "", "empty"), cnt(st == "", "blank"), cnt(s != st, "ws"),
            ln.min().alias(k("minlen")), ln.max().alias(k("maxlen")),
            s.min().alias(k("min")), s.max().alias(k("max")),
            cnt(st.str.contains(INT_RE), "int"), cnt(st.str.contains(NUM_RE), "num"),
            cnt(st.str.contains(DOT_DEC_RE), "dotdec"), cnt(st.str.contains(TRAIL_RE), "trail"),
            cnt(st.str.contains(DEC_COMMA_RE), "deccomma"),
            cnt(st.str.contains(GROUPED_RE), "grouped"),
            cnt(st.str.contains(LEAD0_RE), "lead0"), cnt(st.str.contains(BOOL_RE), "bool"),
            cnt(date_ok | dtm_ok, "date"), cnt(dtm_ok, "dtm"),
            pf.min().alias(k("nmin")), pf.max().alias(k("nmax")),
            pf.mean().alias(k("mean")), pf.median().alias(k("median")),
            pf.std().alias(k("std")), pf.sum().alias(k("sum")),
            cnt(pf < 0, "neg"), cnt(pf == 0, "zero"), pf.len().alias(k("pn")),
        ]
    elif cls in ("boolean", "temporal", "duration"):
        out += [c.min().alias(k("min")), c.max().alias(k("max"))]
    elif cls == "categorical":
        out += [c.cast(pl.String).min().alias(k("min")), c.cast(pl.String).max().alias(k("max"))]
    if cls != "nested":
        nn = c.drop_nulls()
        out.append((nn.approx_n_unique() if approx else nn.n_unique()).alias(k("distinct")))
    return out

def _text(v: Any) -> str | None:
    if v is None:
        return None
    t = v if isinstance(v, str) else str(v)
    return t if len(t) <= MAX_TEXT else t[: MAX_TEXT - 1] + "…"

def _suggest(cp: ColumnProfile, base: int, fam: int) -> tuple[str, float]:
    """Suggested type for a String column; first matching rule wins."""
    if base <= 0:
        return "Unknown", 0.0
    ints = cp.integer_like_count or 0
    if ints / base >= TYPE_SHARE and (cp.leading_zero_count or 0) > 0:
        return "String", 1.0  # keep text: converting would drop the zeros
    if ints / base >= TYPE_SHARE:
        return "Int64", round(ints / base, 4)
    if fam / base >= TYPE_SHARE:
        return "Float64", round(fam / base, 4)
    bools = cp.bool_like_count or 0
    if bools / base >= TYPE_SHARE:
        return "Boolean", round(bools / base, 4)
    dates = cp.date_like_count or 0
    if dates / base >= TYPE_SHARE:
        dtm = cp.datetime_like_count or 0
        return ("Datetime" if dtm * 2 >= dates else "Date"), round(dates / base, 4)
    return "String", 1.0

def _flags(cp: ColumnProfile, base: int, fam: int, native: bool) -> list[str]:
    nn = cp.count - cp.null_count
    hit: set[str] = set()
    if cp.count > 0 and cp.null_count == cp.count:
        hit.add("all_null")
    if cp.count > 0 and cp.null_count < cp.count and base == 0 and not native:
        hit.add("all_blank")
    if cp.count >= 2 and cp.null_count == 0 and cp.distinct_count == 1:
        hit.add("constant")
    if (nn >= HIGH_CARD_MIN_ROWS and cp.distinct_count is not None
            and cp.distinct_count / nn >= HIGH_CARD_RATIO):
        hit.add("high_cardinality")
    if cp.null_pct >= MOSTLY_NULL_PCT and "all_null" not in hit:
        hit.add("mostly_null")
    if (cp.nan_count or 0) > 0:
        hit.add("nan_values")
    if (cp.inf_count or 0) > 0:
        hit.add("inf_values")
    if not native and base > 0:
        share = fam / base
        if MIXED_MIN <= share < TYPE_SHARE:
            hit.add("mixed_numeric_text")
        if (cp.leading_zero_count or 0) > 0 and (cp.integer_like_count or 0) / base >= FAMILY_MIN:
            hit.add("leading_zeros")
        if (cp.trailing_minus_count or 0) > 0 and share >= FAMILY_MIN:
            hit.add("trailing_minus")
        if ((cp.decimal_comma_count or 0) > 0 and share >= FAMILY_MIN
                and (cp.decimal_comma_count or 0) > (cp.dot_decimal_count or 0)):
            hit.add("decimal_comma_suspected")
        if cp.suggested_type in ("Int64", "Float64"):
            hit.add("numeric_as_text")
        if cp.suggested_type in ("Date", "Datetime"):
            hit.add("date_as_text")
    if (cp.whitespace_count or 0) > 0:
        hit.add("leading_trailing_whitespace")
    return [f for f in FLAG_ORDER if f in hit]

def _pct(part: int | None, whole: int) -> float | None:
    if part is None:
        return None
    return 0.0 if whole <= 0 else part * 100.0 / whole

def _prepare(lf: pl.LazyFrame, s: ProfileSettings, coll: _Collector):
    """Return (work frame, rows profiled, sampled)."""
    n = max(1, int(s.sample_rows))
    if s.sample_mode == "head":
        df = coll.one(lf.head(n))
        return df.lazy(), df.height, df.height >= n
    total = int(coll.one(lf.select(pl.len())).item())
    if s.sample_mode == "random" and total > n:
        idx = sorted(random.Random(s.seed).sample(range(total), n))
        keep = pl.Series("i", idx, dtype=pl.Int64)
        tag = "__pf_i"
        while tag in lf.collect_schema().names():
            tag += "_"
        sampled = lf.with_row_index(tag).filter(
            pl.col(tag).cast(pl.Int64).is_in(keep.implode())).drop(tag)
        df = coll.one(sampled)
        return df.lazy(), df.height, True
    return lf, total, False

def profile_frame(frame, *, max_rows: int | None = None,
                  settings: ProfileSettings | None = None) -> DataProfile:
    """Profile ``frame`` (LazyFrame or DataFrame). Never raises for data reasons."""
    t0 = time.perf_counter()
    if settings is None:
        settings = (ProfileSettings(sample_mode="head", sample_rows=max_rows)
                    if max_rows is not None else ProfileSettings())
    lf = frame.lazy() if isinstance(frame, pl.DataFrame) else frame
    schema = lf.collect_schema()
    coll = _Collector()
    names = list(schema.names())
    if not names:
        return DataProfile(0, 0, [], False, settings, 0, time.perf_counter() - t0)
    work, rows, sampled = _prepare(lf, settings, coll)
    approx = rows > settings.approx_distinct_threshold

    exprs: list[pl.Expr] = [pl.len().alias("rows")]
    for i, name in enumerate(names):
        exprs += _aggregate_exprs(i, name, schema[name], approx)
    r = coll.one(work.select(exprs)).row(0, named=True)
    rows = int(r["rows"])

    cols: list[ColumnProfile] = []
    fams: dict[int, int] = {}
    bases: dict[int, int] = {}
    for i, name in enumerate(names):
        dt = schema[name]
        cls = dtype_class(dt)

        def g(m: str, _i: int = i):
            return r.get(f"c{_i}__{m}")

        nulls = int(g("nulls") or 0)
        cp = ColumnProfile(
            name=name, dtype=str(dt), count=rows, null_count=nulls,
            null_pct=_pct(nulls, rows) or 0.0, distinct_count=None, min=None,
            max=None, mean=None, sample_values=[], position=i + 1, sampled=sampled)
        if g("distinct") is not None:
            cp.distinct_count = int(g("distinct"))
            cp.distinct_is_approx = approx
            cp.distinct_pct = _pct(cp.distinct_count, rows - nulls)
        if cls == "numeric":
            cp.numeric_basis = "native"
            is_float = dt.is_float()
            cp.min = _text(g("nmin") if is_float else g("min"))
            cp.max = _text(g("nmax") if is_float else g("max"))
            cp.nan_count, cp.inf_count = int(g("nan") or 0), int(g("inf") or 0)
        elif cls == "string":
            cp.min, cp.max = _text(g("min")), _text(g("max"))
            cp.empty_count, cp.blank_count = int(g("empty") or 0), int(g("blank") or 0)
            cp.whitespace_count = int(g("ws") or 0)
            cp.empty_pct = _pct(cp.empty_count, rows)
            cp.min_length, cp.max_length = g("minlen"), g("maxlen")
            cp.numeric_like_count, cp.integer_like_count = int(g("num") or 0), int(g("int") or 0)
            cp.date_like_count, cp.datetime_like_count = int(g("date") or 0), int(g("dtm") or 0)
            cp.bool_like_count = int(g("bool") or 0)
            cp.leading_zero_count = int(g("lead0") or 0)
            cp.trailing_minus_count = int(g("trail") or 0)
            cp.decimal_comma_count = int(g("deccomma") or 0)
            cp.dot_decimal_count = int(g("dotdec") or 0)
            if (g("pn") or 0) > 0:
                cp.numeric_basis = "parsed_text"
            fams[i] = (cp.numeric_like_count + cp.trailing_minus_count
                       + cp.decimal_comma_count + int(g("grouped") or 0))
            bases[i] = rows - nulls - cp.blank_count
        elif cls in ("boolean", "temporal", "duration", "categorical"):
            cp.min, cp.max = _text(g("min")), _text(g("max"))
        if cp.numeric_basis:
            cp.mean, cp.median, cp.std, cp.sum = g("mean"), g("median"), g("std"), g("sum")
            cp.min_numeric, cp.max_numeric = g("nmin"), g("nmax")
            cp.negative_count, cp.zero_count = int(g("neg") or 0), int(g("zero") or 0)
        if cls == "string":
            cp.suggested_type, cp.suggested_confidence = _suggest(cp, bases[i], fams[i])
        else:
            cp.suggested_type, cp.suggested_confidence = cp.dtype, 1.0
        cp.flags = _flags(cp, bases.get(i, 0), fams.get(i, 0), cls != "string")
        cols.append(cp)

    _detail_pass(work, cols, schema, settings, coll)
    _histogram_pass(work, cols, schema, settings, coll)
    return DataProfile(rows, len(cols), cols, sampled, settings, coll.passes,
                       time.perf_counter() - t0)

def _detail_pass(work, cols, schema, settings, coll) -> None:
    frames, owners = [], []
    n = max(1, int(settings.top_n))
    for i, cp in enumerate(cols):
        cls = dtype_class(schema[cp.name])
        if cls in ("duration", "binary", "null", "nested") or cp.count == cp.null_count:
            continue
        v = pl.col(cp.name).drop_nulls().cast(pl.String).alias("v")
        frames.append(work.select(v).group_by("v").agg(pl.len().alias("n"))
                      .sort(["n", "v"], descending=[True, False]).head(n))
        owners.append(("top", i))
    cand = [i for i, cp in enumerate(cols) if (cp.date_like_count or 0) > 0]
    if cand:
        ex = []
        for i in cand:
            st = pl.col(cols[i].name).cast(pl.String).str.strip_chars()
            for j, f in enumerate(DATE_FORMATS):
                ex.append(st.str.to_date(f, strict=False, exact=True).is_not_null().sum().alias(f"c{i}__f{j}"))
            for j, f in enumerate(DATETIME_FORMATS):
                ex.append(st.str.to_datetime(f, strict=False, exact=True).is_not_null().sum().alias(f"c{i}__t{j}"))
        frames.append(work.select(ex))
        owners.append(("fmt", cand))
    if not frames:
        return
    for (kind, ref), out in zip(owners, coll.many(frames)):
        if kind == "top":
            cp = cols[ref]
            cp.top_values = [(_text(a), int(b)) for a, b in out.iter_rows()]
            cp.sample_values = [a for a, _ in cp.top_values]
        else:
            row = out.row(0, named=True)
            fmts = list(DATE_FORMATS) + list(DATETIME_FORMATS)
            for i in ref:
                counts = [row[f"c{i}__f{j}"] for j in range(len(DATE_FORMATS))] + [
                    row[f"c{i}__t{j}"] for j in range(len(DATETIME_FORMATS))]
                best = max(range(len(counts)), key=lambda j: (counts[j], -j))
                cols[i].date_format_hint = fmts[best] if counts[best] > 0 else ""

def _histogram_pass(work, cols, schema, settings, coll) -> None:
    bins = max(2, int(settings.histogram_bins))
    frames, owners = [], []
    for i, cp in enumerate(cols):
        if cp.numeric_basis == "" or cp.min_numeric is None or cp.max_numeric is None:
            continue
        lo, hi = float(cp.min_numeric), float(cp.max_numeric)
        if not hi > lo:
            continue
        if cp.numeric_basis == "native":
            x = pl.col(cp.name).cast(pl.Float64)
        else:
            st = pl.col(cp.name).cast(pl.String).str.strip_chars()
            x = pl.when(st.str.contains(NUM_RE)).then(st.cast(pl.Float64, strict=False))
        xf = x.filter(x.is_finite())
        b = ((xf - lo) / (hi - lo) * bins).floor().clip(0, bins - 1).cast(pl.Int64)
        frames.append(work.select(b.alias("b"))
                      .group_by("b").agg(pl.len().alias("n")))
        owners.append(i)
    if not frames:
        return
    for i, out in zip(owners, coll.many(frames)):
        counts = [0] * bins
        for b, n in out.iter_rows():
            counts[int(b)] = int(n)
        cols[i].histogram = counts

_ATTR = {"column": "name", "row_count": "count", "min_value": "min",
         "max_value": "max", "mean_value": "mean", "median_value": "median",
         "std_value": "std", "sum_value": "sum", "flags": "flags"}

def profile_to_frame(p: DataProfile) -> pl.DataFrame:
    """One row per column, exactly ``PROFILE_SCHEMA`` (empty profile -> 0 rows)."""
    rows = []
    for c in p.columns:
        row = {n: getattr(c, _ATTR.get(n, n), None) for n in PROFILE_SCHEMA}
        row["flags"] = ",".join(c.flags)
        row["top_values"] = orjson.dumps([[v, n] for v, n in c.top_values]).decode()
        row["top_value"] = c.top_values[0][0] if c.top_values else None
        row["top_count"] = c.top_values[0][1] if c.top_values else None
        rows.append(row)
    return pl.DataFrame(rows, schema=PROFILE_SCHEMA)

def profile_table(frame, **settings) -> pl.DataFrame:
    """Entry point used by generated code: settings keys = ProfileSettings fields."""
    return profile_frame(frame, settings=ProfileSettings(**settings)).to_frame()
```

Done when: `.venv\Scripts\python.exe -m pytest tests\unit\test_profile_core.py -q` passes (section 6.1) and `ruff check` is clean on both files.

### Commit 2 - export helpers in `core/profile.py` (append after `profile_table`)

```python
def profile_to_tsv(frame: pl.DataFrame) -> str:
    def cell(v: Any) -> str:
        return "" if v is None else str(v).replace("\t", " ").replace("\r", " ").replace("\n", " ")
    rows = ["\t".join(frame.columns)] + ["\t".join(cell(v) for v in r) for r in frame.iter_rows()]
    return "\n".join(rows) + "\n"


def write_profile_xlsx(frame: pl.DataFrame, path: str) -> None:
    """Thin adapter over plan 06's helper; this module imports no Excel library."""
    try:
        from trigger_designer.core.excel import write_frame_xlsx
    except ImportError as exc:  # plan 06 not merged yet, or xlsxwriter missing
        raise RuntimeError("Excel export is unavailable: the Excel writer (xlsxwriter) is not installed") from exc
    # Expected helper signature (plan 06): write_frame_xlsx(frame: pl.DataFrame, path: str, *, sheet_name: str = "Sheet1") -> None
    write_frame_xlsx(frame, path, sheet_name="Profile")


def profile_summary(p: DataProfile) -> dict[str, Any]:
    """Small JSON-safe digest for plan 02 run records and plan 06 workpapers."""
    return {"rows": p.row_count, "columns": p.column_count, "sampled": p.sampled,
            "sample_mode": p.settings.sample_mode, "passes": p.passes,
            "flagged": {c.name: list(c.flags) for c in p.columns if c.flags}}
```
Add tests `test_tsv_*`, `test_xlsx_roundtrip` (6.1). Done when those pass.

### Commit 3 - node registration, resources and node class (no dock widgets yet)

1. `core/node_configuration.py:64-65`: append `DATA_PROFILE = auto()` after `GRAPH` in `ReportNodes`.
2. `qt/widgets/nodes/__init__.py`: add to `_LAZY_NODE_SPECS` after the Graph entry (`:122-128`):
   `{"module_path": "Report.data_profile", "node_code": ReportNodes.DATA_PROFILE, "node_type": NodeTypes.REPORT, "node_title": "Data Profile", "icon": "node_data_profile"}`.
   Add `"Report.profile_view"` to `_LAZY_HELPER_MODULES` (`:156`) only if the view module lives in `Report/`; decided: the view lives in
   `qt/widgets/profile_view.py` and the worker in `qt/models/profile_worker.py`, so **no** change there.
3. Icons: create `resources/qt/images/node_icons/Report/Data Profile.svg` (100x100, `rx=15`, fill `#1A70B1`, white 4px table frame
   `<rect x="22" y="24" width="56" height="52" rx="4"/>`, row/column lines `M22 40H78M22 56H78M46 24V76`, a white 3px zig-zag `M54 68L60 60L66 64L72 52`);
   `ui/copy.svg` (Feather "copy" paths: `rect x=9 y=9 w=13 h=13 rx=2` + `M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1`, stroke `#D0D0D0` 2, 24 viewBox, 16px);
   `ui/export_excel.svg` (Feather "file-x": `M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z`, `M14 2v6h6`, `M9.5 12.5l5 5M14.5 12.5l-5 5`).
   `qt/resources.json`: add `"node_data_profile": {"path": "qt/images/node_icons/Report/Data Profile.svg", "mode": "rb"}`,
   `"icon_copy": {"path": "qt/images/node_icons/ui/copy.svg", "mode": "rb"}`, `"icon_export_excel": {"path": "qt/images/node_icons/ui/export_excel.svg", "mode": "rb"}`
   (recolouring is automatic by the `ui/` path prefix, `theme_icons.py:41`). Skip `icons.qrc` (menu falls back to `ResourceManager`).
4. Create `qt/widgets/nodes/Report/data_profile.py` (imports: `dataclasses`, `threading`, `polars as pl`, brief-3.8 imports, `frame_schema` from `qt.node_base`, and from `core.profile`: `PROFILE_SCHEMA, DataProfile, ProfileSettings, empty_profile_frame, profile_frame`). Skeleton (fill `...` exactly as the brief's Head skeleton 3.8 does for boilerplate: `node` property pair, `initUI`,
   `serialize`/`deserialize` with `serialize_content_state`/`deserialize_content_state`, `evaluate = Signal()`):

```python
@register_node(ReportNodes.DATA_PROFILE, NodeTypes.REPORT)
class TriggerNode_DataProfile(TriggerNode):
    icon = "node_data_profile"; node_code = ReportNodes.DATA_PROFILE; node_title = "Data Profile"
    node_type = NodeTypes.REPORT; content_label_objname = "trigger_node_data_profile"; style = {}

    def __init__(self, scene) -> None:
        super().__init__(scene, inputs=[1], outputs=[3, 1], output_text=["D", "P"])

    def initInnerClasses(self) -> None:
        self.content = DataProfileContent(self)
        self.grNode = TriggerGraphicsNode(self)
        self.content.evaluate.connect(self.onInputChanged)
        self.param: list = []

    def processInputs(self, input_values):
        input_node = self.getInput(0)
        entry = input_values[0][self.getSocketValue(input_node.outputs, self)]
        if not entry or entry.get("data") is None:
            self.markDirty(True); self.markInvalid(True)
            self._set_node_tooltip("Upstream node produced no data"); return None
        try:
            frame_schema(entry["data"])                       # raises on a broken lazy plan
        except Exception as exc:                              # noqa: BLE001
            self.markDirty(True); self.markInvalid(True)
            self._set_node_tooltip(f"Data Profile: {exc}"); return None
        c = self.content
        if entry["data"] is not c.incom_data:
            c.bump_epoch()
        c.incom_data, c.incoming_variable = entry["data"], entry["variable_name"]
        self.param = [{"data": entry["data"], "variable_name": c.main_variable_name},
                      {"data": c.profile_lazy(), "variable_name": c.profile_variable_name}]
        c.on_inputs_processed()
        return self.param

    def get_code(self) -> str:
        return self.content.get_code()


class DataProfileContent(QDMNodeIconContentWidget, TriggerChangeHandler, SerializableContentMixin):
    evaluate = Signal()
    serialized_state_schema = {"sample_mode": {"default": "full"}, "sample_rows": {"default": 100000},
        "seed": {"default": 42}, "top_n": {"default": 5},
        "approx_distinct_threshold": {"default": 2000000}, "histogram_bins": {"default": 20}}
    _LIMITS = {"sample_rows": (1000, 100_000_000), "seed": (0, 2_147_483_647), "top_n": (1, 50),
               "approx_distinct_threshold": (10_000, 2_000_000_000), "histogram_bins": (5, 100)}

    def __init__(self, node, parent=None):
        super().__init__(node, parent)
        TriggerChangeHandler.__init__(self, self.node.scene, self.node)
        self.history = self.node.scene.history
        self.incom_data = None; self.incoming_variable = ""
        self.main_variable_name = f"var_dprof_{self.id}"
        self.profile_variable_name = f"var_dprof_profile_{self.id}"
        self.variable_name = self.main_variable_name
        self.sample_mode = "full"; self.sample_rows = 100000; self.seed = 42; self.top_n = 5
        self.approx_distinct_threshold = 2000000; self.histogram_bins = 20
        self._epoch = 0; self._lock = threading.RLock()
        self._cache: tuple | None = None          # (key, DataProfile)
        self._view = None; self._request_id = 0   # dock view (3.10) and newest worker id

    def settings(self) -> ProfileSettings: ...    # builds ProfileSettings from the six attributes (after _normalize_settings)
    def _normalize_settings(self) -> None: ...    # clamp via _LIMITS; unknown sample_mode -> "full"; call at end of deserialize
    def bump_epoch(self) -> None:
        self._epoch += 1                          # no lock needed: GUI thread only
    def key(self) -> tuple:
        return (self._epoch, self.settings().key())
    def current_profile(self) -> DataProfile | None:
        c = self._cache; return c[1] if c and c[0] == self.key() else None   # for plans 02/06

    def get_or_compute(self, key, frame, settings) -> DataProfile:
        with self._lock:
            if self._cache and self._cache[0] == key:
                return self._cache[1]
            profile = profile_frame(frame, settings=settings)
            if key == self.key():                 # not superseded meanwhile
                self._cache = (key, profile)
            return profile

    def profile_lazy(self) -> pl.LazyFrame:
        key, frame, settings = self.key(), self.incom_data, self.settings()
        return pl.defer(lambda: self.get_or_compute(key, frame, settings).to_frame(), schema=PROFILE_SCHEMA)

    def get_code(self) -> str:
        m, p = self.main_variable_name, self.profile_variable_name
        if not self.incoming_variable:
            return ("import polars as pl\nfrom trigger_designer.core.profile import empty_profile_frame\n"
                    f"{m} = pl.DataFrame()\n{p} = empty_profile_frame()\n")
        kwargs = dataclasses.asdict(self.settings())
        return ("from trigger_designer.core.profile import profile_table\n"
                f"{m} = {self.incoming_variable}\n"
                f"{p} = profile_table({self.incoming_variable}, **{kwargs!r})\n")
```
   `create_layout`, `on_inputs_processed`, `dock_context` come in commit 4; in this commit `create_layout` adds `EmptyStateLabel("Open the dock in the next commit")`-free stub:
   `dock_layout.addWidget(EmptyStateLabel() if self.incom_data is None else QWidget())` and `on_inputs_processed` is `pass`.
   `dock_context` returns `[(mode_text, "accent" if self.sample_mode != "full" else "")], ""` with `mode_text` = `"full data"`, `"first 100,000 rows"` or `"random 100,000 rows (seed 42)"`.
5. Tests: `tests/unit/test_data_profile_node.py` (6.2). Also extend `tests/unit/test_node_titles.py`-style check is automatic (spec title == class title).

Done when: `.venv\Scripts\python.exe -m pytest tests\unit\test_data_profile_node.py tests\unit\test_node_titles.py -q` passes; the node appears in the palette (Report tab) and Shift+A.

### Commit 4 - worker, dock view, undo wiring

1. `qt/models/profile_worker.py`: `_LIVE: set[QThread]`; `class ProfileWorker(QThread)` with `finished_ok = Signal(int, object)`, `failed = Signal(int, str)`,
   `__init__(self, request_id: int, compute: Callable[[], DataProfile])`; `run()` calls `compute()` in try/except (emit `finished_ok(request_id, profile)` or `failed(request_id, str(exc))`);
   helper `start_profile_worker(worker)` adds to `_LIVE` and removes it on `finished` (copy `preview_worker._keep_alive`, `:33-41`) then `worker.start()`.
2. `qt/widgets/profile_view.py`: `ProfileTableModel`, `NullBarDelegate`, `MiniBarChart`, `detail_rows(cp)`, `status_text(profile)`, and
   `class ProfileDockView(QWidget)` with `_undo_composite = True`, layout per 3.10, public API used by the content:
   `set_loading()`, `set_profile(profile: DataProfile)`, `set_failed(msg: str)`, `set_message(msg: str)`, `apply_settings(d: dict)`, read-only attributes `state` (`"loading"|"ready"|"failed"`), `notice` (the `Chip`), `chart` (`MiniBarChart`, attribute `kind` in `"hist"|"freq"|""`), `table` (`QTableView`), `search` (`QLineEdit`), and signals `copyRequested`, `csvRequested`, `excelRequested`, `recomputeRequested`.
   Module-level `from qtpy.QtWidgets import QFileDialog` (tests monkeypatch `profile_view.QFileDialog.getSaveFileName`). Export slots (in the view):
   `frame = self._profile.to_frame()`; CSV -> `frame.write_csv(path)`; Excel -> `write_profile_xlsx(frame, path)` inside `try/except Exception as exc: self.set_message(f"Export failed: {exc}")`.
   Copy -> `QApplication.clipboard().setText(profile_to_tsv(frame))`. Header name casing: `"Column", "Type", "Null %", "Distinct", "Suggested", "Flags"`;
   distinct text `~1,002` when `distinct_is_approx`; suggested text `Float64 (98%)` when confidence < 1 else the type; sort values: name casefold, dtype text, null_pct, distinct (None -> -1), suggested text, flags count.
   Options section: `ConfigSection("Options", collapsible=True, collapsed=True)` with `FormRow`s: `NoWheelComboBox` Sample (`Full data`/`First N rows`/`Random N rows`), four `QSpinBox` (min height 30,
   ranges/steps from 3.2). The view emits `settingChanged(str, object)` (`key`, `value`); it never mutates the model.
3. In `DataProfileContent`: `create_layout` -> `EmptyStateLabel` when `incom_data is None`, else `self._view = ProfileDockView(self.settings_dict(), self.node.rsm)`; `dock_layout.addWidget(view, 1)`;
   connect `settingChanged -> self._on_setting_changed`, `recomputeRequested -> self._recompute`, `view.destroyed -> lambda: setattr(self, "_view", None)`; then `self.request_profile()`.
   `on_inputs_processed()`: `if self._view is not None: self.request_profile()`.
   `request_profile()`: cached for `self.key()` -> `view.set_profile(cached)`; else `self._request_id += 1`, `view.set_loading()`, start `ProfileWorker(rid, lambda: self.get_or_compute(key, frame, settings))`
   whose signals connect to bound methods `_on_profile_ready(rid, profile)` / `_on_profile_failed(rid, msg)`; both ignore `rid != self._request_id` and a deleted view (`RuntimeError`).
   `_recompute`: `self._cache = None; self.bump_epoch(); self.request_profile()`.
   `_on_setting_changed(key, value)`: the brief-6.3 handler with `path=(key,)`, `old=getattr(self, key)`, the texts/merge keys of 3.11; after `evaluate.emit()` nothing else (eval -> `on_inputs_processed` recomputes).
   `_sync_widgets_from_model()`: `self._view.apply_settings(self.settings_dict())` inside try/except `RuntimeError` (view deleted -> set `self._view = None`).
4. Tests: `tests/ui/test_data_profile_dock.py` (6.3).

Done when: `.venv\Scripts\python.exe -m pytest tests\ui\test_data_profile_dock.py tests\unit\test_data_profile_node.py -q` passes; manual smoke: File Input (`data/check.csv`) -> Data Profile, select node, table fills, click rows, change Sample to `First N rows`, undo/redo restores it, Ctrl+Z does not record search typing.

### Commit 5 - e2e golden, benchmark, docs

`tests/e2e/test_data_profile_golden.py`, `tests/benchmarks/test_data_profile_perf.py` (6.4, 6.5); regenerate the golden once with
`$env:TRIGGER_UPDATE_E2E_GOLDENS="1"; .venv\Scripts\python.exe -m pytest tests\e2e\test_data_profile_golden.py; Remove-Item Env:TRIGGER_UPDATE_E2E_GOLDENS`,
then verify the golden against the hand-computed assertions in the same test and review `git diff tests/e2e/fixtures/expected`. Add a `docs/NODE_REFERENCE.md` row (Data Profile, Report, inputs/outputs, settings).

### Cross-plan integration (plans 01, 02, 03, 06, 08, 09)

**A. Generated-code imports** (the only imports `DataProfileContent.get_code` ever emits; plan 08's headless allow-list must permit exactly these names; the set is deliberately minimal and stable):

| Emitted by | Import statement | Name used | Stability rule |
|---|---|---|---|
| wired node | `from trigger_designer.core.profile import profile_table` | `profile_table(frame, **settings) -> pl.DataFrame` | signature frozen; new settings are added as defaulted `ProfileSettings` fields, so old generated scripts keep working |
| unwired node | `import polars as pl` | `pl.DataFrame` | - |
| unwired node | `from trigger_designer.core.profile import empty_profile_frame` | `empty_profile_frame() -> pl.DataFrame` | frozen |

Nothing else is imported in generated code (no `profile_frame`, no Qt, no `core.excel`; Excel export happens only in the dock, never in Run). `profile_table` and `empty_profile_frame` are in `core/profile.py`, which imports only stdlib, `polars`, `orjson`.

**B. Packaging.** **Provided by plan 09 F-G (do not redo here):** `core/profile.py` is listed in F-G's `_CORE_MODULES`, so the string import in generated code is covered. This plan makes no `trigger.spec` edit.

**C. Docks / `apply_default_layout`.** This plan adds **no new dock**: the profile lives inside the node's Config Dock panel (3.10) and the Data Preview dock already previews socket `P`. Therefore there is **no** `("dataProfileDock", area)` entry to add to `layout_state.apply_default_layout` (`qt/layout_state.py:225-250`) and no `tabifyDockWidget` call, so there is nothing to collide with plans 02 (Run History) and 03 (Problems) that tabify with Logging/Data Preview. If a reviewer later wants a standalone dock, the fixed rule is: object name `DataProfileDock`, area bottom, tab order `Logging, Data Preview, Data Profile` (appended after Data Preview, after any plan 02/03 tabs already listed), but that is out of scope here.

**D. `qt/resources.json` additions** (exact keys; the only three this plan adds; merge by key, never by line):

| Key | `path` | `mode` |
|---|---|---|
| `node_data_profile` | `qt/images/node_icons/Report/Data Profile.svg` | `rb` |
| `icon_copy` | `qt/images/node_icons/ui/copy.svg` | `rb` |
| `icon_export_excel` | `qt/images/node_icons/ui/export_excel.svg` | `rb` |

Existing keys reused unchanged: `icon_save`, `icon_refresh`, `icon_options`. If plan 01/02/08 also add a `icon_copy`, keep a single entry (same file) and drop the duplicate.

**E. Error codes.** The node raises no `NodeError` itself (it sets tooltips/chip text). Strings below are the ones it produces; plan 03 may paste the table into its catalogue (package `core/errors/`) and translate by exception text. Prefix `TD-PROFILE-NNN`:

| Code | Title (one line) | Hint | Where shown |
|---|---|---|---|
| `TD-PROFILE-001` | The profile could not read the incoming data | Check the node feeding Data Profile for errors, then try again | node tooltip from `processInputs` (`Data Profile: <error>`) |
| `TD-PROFILE-002` | The profile could not be calculated | Use a smaller sample (Options > Sample) or remove very wide text columns upstream | dock chip `Profile failed: <error>` |
| `TD-PROFILE-003` | The Excel file could not be written | Close the file if it is open elsewhere, or choose another folder | dock chip `Export failed: <error>` |
| `TD-PROFILE-004` | Excel export is not available in this installation | Reinstall the application or export as CSV instead | dock chip when `core.excel` / `xlsxwriter` import fails |

**F. Excel helper confirmation.** `write_profile_xlsx` (commit 2) still calls the shared helper with exactly `from trigger_designer.core.excel import write_frame_xlsx` followed by `write_frame_xlsx(frame, path, sheet_name="Profile")` (plan 06 re-exports it from `core/excel/__init__.py`). This plan imports no `xlsxwriter`, `openpyxl` or `pyfastexcel` in application code (openpyxl only reads back in tests).

## 5. Edge cases (behaviour is fixed; each has a test in section 6)

| Case | Behaviour |
|---|---|
| Zero rows | all counts 0, `null_pct`/`distinct_pct` 0.0 or null, `suggested_type` `Unknown` (String) / dtype (others), no flags, `passes == 2` (P0, P1; no P2/P3), empty `top_values` |
| Zero columns | `DataProfile(0, 0, [], ...)`, `passes == 0`, `to_frame()` is the empty `PROFILE_SCHEMA` frame; node output 0 rows; dock shows `EmptyStateLabel("No columns")` |
| Single row | works; `constant` NOT flagged (needs rows >= 2); `std_value` null |
| All null | `all_null`; String suggests `Unknown`/0.0; no top values; `distinct_count == 0` |
| Nested (List/Array/Struct) | null count + `dtype` only; distinct/min/max/top null; no exception |
| Categorical/Enum | counts, min/max as text, distinct, top-N; `suggested_type` = dtype |
| 1000+ columns | one P1 select, one P2/P3 `collect_all`; 1500 cols x 3 rows measured 4.3 s; table filter by name makes it usable |
| Huge strings | min/max/top texts truncated to 100 chars; `max_length` exact (2,000,000-char value tested) |
| NaN vs null | NaN is a value (`nan_count`, counted in distinct, top-N shows `NaN`), excluded from numeric stats; null is null |
| +/-inf | `inf_count`; excluded from min/max/mean/sum/histogram; counted in distinct |
| Decimal | numeric class; stats cast to Float64; min/max raw text keep scale (`-2.25`) |
| Duration / Time / Date | min/max text; Duration has no top-N; no numeric stats |
| Binary | null count + distinct only |
| Non-ASCII | lengths are characters; top values keep the text |
| Names with spaces/dots, or equal to our alias scheme (`c0__nulls`) | safe: expression aliases use positional prefixes `c<i>__metric`, not names |
| Duplicate column names | impossible in Polars; case-variants (`a b`, `A B`) work |
| Unquoted empty CSV field | arrives as null (not empty string); quoted `""` is counted as empty |
| Sampling total <= N | behaves as `full`, `sampled=False` |
| Random column named `__pf_i` | tag name gets `_` appended until unique |
| Bad upstream plan | `processInputs` returns `None` with tooltip; Profile socket not produced |
| Run on unwired node | both variables defined (`pl.DataFrame()` and empty profile frame) |
| Exact vs approximate flip | `distinct_is_approx` true and value within 5 % (1002 vs 1000 observed) |

## 6. Test plan (names and assertions)

Shared helper module `tests/support/profile_fixtures.py` (new) exporting `FX` (the 10-row fixture below), `MESSY_CSV` (e2e text) and
`Source(TriggerNode)` copied from brief 9.2. Hand-computed values below were also reproduced by running the code in commit 1.

Fixture `FX = pl.DataFrame({` `id`: `["001".."010"]` (zero padded); `amount`: `["10","20.5","30"," 40 ","",None,"1,5","abc","123-","7"]`; `qty`: `[1,2,2,3,None,0,-1,5,5,5]`;
`price`: `[1.5,nan,inf,None,2.5,-0.5,0.0,1.5,1.5,3.0]`; `when`: `["2024-01-31","2024-02-29","2023-12-01","2024-03-15","2024-04-01","2024-05-05","2024-06-30","2024-07-04","2024-08-08","2024-09-09"]`;
`flag`: `["Y","N","Y","Y","N","Y","N","Y","Y","N"]`; `const`: `["x"]*10`; `nada`: `[None]*10` (String); `locale`: `["1,5","2,25","3,0","10,75","0,5","100,5","7,1","8,2","9,9","4,4"]`;
`sap`: `["100-","200","300-","50","75-","10","20","30","40","5"]` `})`.

### 6.1 `tests/unit/test_profile_core.py` (no Qt)

Expected (per column; `P = profile_frame(FX)`; `p.row_count == 10`, `p.passes == 4`, `p.sampled is False`, `p.to_frame().schema == pl.Schema(PROFILE_SCHEMA)`, `height == 10`):

| Test | Column | Assertions |
|---|---|---|
| `test_leading_zero_ids` | id | distinct 10, `integer_like_count==10`, `leading_zero_count==10`, suggested `String`/1.0, flags `["leading_zeros"]`, `min_length==max_length==3`, top 5 = `[("001",1)..("005",1)]` |
| `test_messy_amount_column` | amount | `null_count==1, empty_count==1, blank_count==1, whitespace_count==1, distinct_count==9, numeric_like_count==5, integer_like_count==4, trailing_minus_count==1, decimal_comma_count==1, dot_decimal_count==1, min_length==0, max_length==4`; basis `parsed_text`; `min_numeric==7.0, max_numeric==40.0, sum==107.5, mean==21.5, median==20.5, std==approx(13.765899897936205)`, `negative_count==0, zero_count==0`; suggested `String`/1.0; flags `["mixed_numeric_text","trailing_minus","leading_trailing_whitespace"]` (decimal comma NOT flagged: `1 > 1` is false); top5 `[("",1),(" 40 ",1),("1,5",1),("10",1),("123-",1)]` |
| `test_native_int_column` | qty | `null_count==1, null_pct==10.0, distinct_count==6, min=="-1", max=="5", sum==22.0, mean==approx(22/9), median==2.0, std==approx(2.2422706745122847), negative_count==1, zero_count==1`; basis `native`; suggested `Int64`/1.0; flags `[]`; top5 `[("5",3),("2",2),("-1",1),("0",1),("1",1)]` |
| `test_nan_and_inf` | price | `nan_count==1, inf_count==1, null_count==1, distinct_count==7, min=="-0.5", max=="3.0", sum==9.5, mean==approx(9.5/7), median==1.5, std==approx(1.2488089563755576)`; flags `["nan_values","inf_values"]`; top[0]==`("1.5",3)` |
| `test_dates_stored_as_text` | when | `date_like_count==10`, `date_format_hint=="%Y-%m-%d"`, suggested `Date`/1.0, flags `["date_as_text"]`, `numeric_basis==""` |
| `test_boolean_text` | flag | `bool_like_count==10`, suggested `Boolean`, top `[("Y",6),("N",4)]`, `distinct_count==2`, flags `[]` |
| `test_constant_flag` | const | `distinct_count==1`, flags `["constant"]` |
| `test_all_null_flag` | nada | `null_count==10`, `distinct_count==0`, suggested `Unknown`/0.0, flags `["all_null"]`, `top_values==[]`, `mean is None` |
| `test_decimal_comma_flag` | locale | `decimal_comma_count==10`, suggested `Float64`/1.0, flags `["decimal_comma_suspected","numeric_as_text"]`, `numeric_basis==""` |
| `test_trailing_minus_flag` | sap | `numeric_like_count==7, integer_like_count==7, trailing_minus_count==3`, `sum==355.0, min_numeric==5.0, max_numeric==200.0, mean==approx(355/7), median==30.0`, suggested `Float64`/1.0, flags `["trailing_minus","numeric_as_text"]` |
| `test_high_cardinality_and_mostly_null` | 25 rows `id=k0..k24`, `m=[None]*13+["a"]*12` | id flags `["high_cardinality"]`, m flags `["mostly_null"]` |
| `test_flags_have_no_false_positives` | `qty`, `flag` | `flags == []` |
| `test_histogram_counts` | qty (bins 20) | `sum(histogram)==9`, `len==20`, `histogram[0]==1` (value -1), `histogram[19]==3` (value 5) |
| `test_collect_pass_budget` | FX in each mode | full `passes==4`; head `passes==4`; random (N<total) `passes==5`; zero rows `passes==2`; zero columns `passes==0` |
| `test_head_sample` | 1000-row frame, head 100 | `row_count==100`, `sampled`, `columns[0].max=="99"` (int column), `passes==4` |
| `test_random_sample_is_reproducible` | same, random N=100 | same seed twice -> `to_frame().equals`; seed 8 differs; `sampled`; total<=N -> `sampled False`, `row_count==1000` |
| `test_distinct_exact_vs_approx` | 1000-row frame | default settings -> `distinct_is_approx False`, count 1000; `approx_distinct_threshold=500` -> `True`, `abs(count-1000)/1000 <= 0.05` |
| `test_edge_dtypes_do_not_raise` | list, struct, binary, categorical, enum, decimal, duration, time, null, bool, datetime, array, date, uint8 | no exception; `to_frame().schema` valid; decimal `min=="-2.25"`; list `distinct_count is None`; categorical `suggested_type=="Categorical"` |
| `test_huge_and_unicode_strings` | 2,000,000-char value; `["Zoë","日本語","naïve","日本語","😀"]` | `max_length==2_000_000`, `len(min_value) <= 100`; unicode `min_length==1, max_length==5`, top[0]==`("日本語",2)` |
| `test_odd_column_names` | `a b`, `A B`, `x.y`, `c0__nulls` | names preserved, 4 rows |
| `test_zero_rows_and_columns` | empty frames | per 5 |
| `test_deferred_frame_is_lazy_and_cached` | content test in 6.2 | see there |
| `test_tsv_has_header_and_escapes_tabs` | frame with `"a\tb"` | header line equals columns joined by tab; no raw tab inside a cell |
| `test_xlsx_roundtrip` | `write_profile_xlsx(frame, tmp)` | `pytest.importorskip("trigger_designer.core.excel")` (skips until plan 06 lands); read back with `openpyxl.load_workbook` (test-time only): sheet `Profile`, `max_row == frame.height + 1`, header row equals columns; separate test with `monkeypatch.setitem(sys.modules, "trigger_designer.core.excel", None)` -> `RuntimeError` (runs without the helper) |
| `test_profile_summary` | FX | `flagged["nada"]==["all_null"]`, `rows==10` |

### 6.2 `tests/unit/test_data_profile_node.py`

(`Source` double + `TriggerSubWindow` as brief 9.2.) Tests: `test_passthrough_is_unchanged_live` (`out[0]["data"] is src._frame`, `out[0]["variable_name"] == content.main_variable_name`);
`test_profile_socket_is_lazy_with_exact_schema` (`isinstance(out[1]["data"], pl.LazyFrame)`, `collect_schema() == pl.Schema(PROFILE_SCHEMA)`, `content._cache is None` before collect, collecting twice
calls `profile_frame` once - monkeypatch counter on `trigger_designer.qt.widgets.nodes.Report.data_profile.profile_frame`); `test_live_and_run_agree` (exec `node.get_code()` with `{"var_src": frame}`, `ns[profile_var].equals(live collect)`,
`ns[main_var] is frame`); `test_unwired_defines_both_variables`; `test_serialize_roundtrip_and_old_file_defaults` (`deserialize({})` gives the 3.2 defaults; `deserialize({"top_n": 999, "sample_mode": "bogus"})` -> 50, `"full"`);
`test_epoch_only_bumps_on_new_frame` (re-eval with same object keeps `_epoch`; changing `top_n` + `evaluate.emit()` keeps `_epoch`, new key recomputes); `test_bad_plan_sets_tooltip_and_invalid`
(`pl.LazyFrame({"a":[1]}).select(pl.col("zzz"))` upstream -> `node.isInvalid()`); `test_run_pruning_keeps_both_outputs` (`window._declared_output_variable_names(node)` equals the two names, in order).

### 6.3 `tests/ui/test_data_profile_dock.py` (offscreen; `qtbot.waitUntil(lambda: view.state == "ready", timeout=15000)`)

`test_dock_fills_and_sorts` (6 rows model, click `Null %` header, first row is the max-null column); `test_detail_pane_shows_histogram_for_numeric_and_bars_for_text` (`view.chart.kind == "hist"` for `qty`, `"freq"` for `flag`);
`test_sample_notice` (`view.notice.text()` startswith `"Full data"`; after `settingChanged("sample_mode","head")` with 3 rows source and `sample_rows=2` -> startswith `"Sample: first"` and chip `tone == "accent"`);
`test_setting_change_is_one_undo_step_and_restores_widgets` (baseline `history.storeHistory("Baseline")`; change `top_n` spin -> `history.undo()` -> `content.top_n == 5`, widget value 5, `history.redo()` -> new; `updateConfig(..., force=True)` keeps value);
`test_search_typing_is_not_recorded` (type in search, `history.canUndo()` unchanged); `test_copy_puts_tsv_on_clipboard`; `test_export_csv_and_xlsx` (monkeypatch `profile_view.QFileDialog.getSaveFileName` -> `(str(tmp/"p.csv"), "")`;
file exists, `pl.read_csv(...).height == 10`; xlsx loads with openpyxl, skipped if the helper is absent); `test_excel_export_degrades_without_helper` (`sys.modules["trigger_designer.core.excel"] = None` -> chip text startswith `"Export failed"`, no exception);
`test_empty_state_without_input`; `test_stale_result_is_ignored` (call `_on_profile_ready(old_rid, profile)` after a newer request -> view unchanged); `test_create_layout_direct_has_no_exception` (call `content.create_layout(QVBoxLayout(QWidget()))`).

### 6.4 `tests/e2e/test_data_profile_golden.py`

`MESSY_CSV` (exact text, UTF-8, `\n`, trailing newline): header `id,amount,qty,posted,flag,note`; rows
`001,"1,234.50",1,2024-01-31,Y,ok` / `002, 20.5 ,2,2024-02-29,N,""` / `003,30-,2,2024-03-15,Y,ok` / `004,abc,,2024-04-01,Y,ok` / `005,7,0,31/12/2024,N, ok` / `006,,5,not a date,Y,ok`.
Test `test_messy_csv_profile_matches_golden`: build File Input (csv) -> Data Profile; File Output A from socket 0 (`passthrough.csv`), File Output B from socket 1 (`profile.csv`) (build like brief 9.4, save `.tds`, reload in a fresh
`TriggerSubWindow`, `run_workflow_and_wait`); assert (1) `read_frame(passthrough)` equals `pl.read_csv(MESSY, infer_schema=False)` (pass-through unchanged); (2) `assert_frame_golden(read_frame(profile), "data_profile_messy")`;
(3) hand-computed cell checks on the profile frame (`row = lambda c: frame.filter(pl.col("column")==c).row(0, named=True)`): `id` flags `leading_zeros`, suggested `String`; `amount` `null_count 1, whitespace_count 1, numeric_like_count 2, integer_like_count 1,
trailing_minus_count 1, distinct_count 5`, flags `mixed_numeric_text,trailing_minus,leading_trailing_whitespace`; `qty` `null_count 1`, suggested `Int64`, flags `numeric_as_text`; `posted` `date_like_count 5`, suggested `String`, flags `""`;
`flag` suggested `Boolean`, `top_value "Y"`, `top_count 4`; `note` `empty_count 1, blank_count 1, whitespace_count 1, distinct_count 3`, flags `leading_trailing_whitespace`; all rows `row_count == 6` and `sampled == False`. Also assert every node is green
(`len(window.execution_results) == len(window.getAllNodes())`). Golden file: `tests/e2e/fixtures/expected/data_profile_messy.csv`.

### 6.5 `tests/benchmarks/test_data_profile_perf.py` (opt-in `--run-benchmarks`; and a small non-opt-in twin in `tests/unit`)

* `test_profile_1m_by_30_within_budget`: 1M rows, 10 digit-string columns + 10 float + 10 int (numpy seed 1, as measured); `time.perf_counter()` around `profile_frame`; assert `elapsed < 30.0` (measured 7.8 s, budget ~4x for slower CI) and `p.passes <= 4`, `p.column_count == 30`.
* `test_profile_head_sample_is_fast_on_csv`: write the same frame to CSV in `tmp_path`, `pl.scan_csv(path, infer_schema=False)`, `ProfileSettings(sample_mode="head")`, `elapsed < 15.0` (measured 2.3 s).
* Unit twin `test_profile_200k_rows_budget` in `tests/unit/test_profile_core.py`: 200k x 12 mixed columns `< 8.0 s` and `passes <= 4`.

## 7. Acceptance checklist

- [ ] Palette Report tab and Shift+A list "Data Profile"; op id `report.data_profile`; `test_node_titles` green.
- [ ] Wiring File Input -> Data Profile: socket 0 data identical to input (live and Run), socket 1 table matches 3.3 exactly (`PROFILE_SCHEMA`).
- [ ] Selecting the node fills the dock off the GUI thread (UI stays responsive on a 1M-row CSV; chip shows "Profiling...").
- [ ] Sample modes work; chip states Full/Sample; `sampled` column set; random is reproducible by seed.
- [ ] All 14 flags and suggested-type rules behave per 3.7 (tests 6.1).
- [ ] Copy, CSV export, Excel export (via plan 06's `write_frame_xlsx`) work; a missing helper degrades to a message.
- [ ] Settings are undoable one step each; no extra history entries from search/sort/selection.
- [ ] Save/reload keeps six settings; an old `.tds` (no keys) loads with defaults.
- [ ] Profile collect passes <= 4 (5 for random); 1M x 30 within budget.
- [ ] No inline `setStyleSheet`, every icon button has tooltip + accessible name, no `QIcon.fromTheme`.
- [ ] `docs/NODE_REFERENCE.md` row added; ruff format/check clean on touched files; no new ui-test failures versus the 20 failed + 7 errors baseline.

## 8. Verification commands (PowerShell, repo root)

```powershell
.venv\Scripts\python.exe -m ruff format src\trigger_designer\core\profile.py src\trigger_designer\qt\widgets\nodes\Report\data_profile.py src\trigger_designer\qt\widgets\profile_view.py src\trigger_designer\qt\models\profile_worker.py
.venv\Scripts\python.exe -m ruff check  src\trigger_designer\core\profile.py src\trigger_designer\qt\widgets\nodes\Report\data_profile.py src\trigger_designer\qt\widgets\profile_view.py src\trigger_designer\qt\models\profile_worker.py
.venv\Scripts\python.exe -m pytest tests\unit\test_profile_core.py tests\unit\test_data_profile_node.py tests\unit\test_node_titles.py -q   # unit layer
.venv\Scripts\python.exe -m pytest tests\ui\test_data_profile_dock.py -q                                                                   # ui layer (new file only)
.venv\Scripts\python.exe -m pytest tests\e2e\test_data_profile_golden.py -q                                                                # e2e layer
.venv\Scripts\python.exe -m pytest tests\benchmarks\test_data_profile_perf.py --run-benchmarks -q                                          # perf
.venv\Scripts\python.exe -m pytest tests\unit -q ; .venv\Scripts\python.exe -m pytest tests\e2e -q                                         # regression: 334+ / 20+ pass
.venv\Scripts\python.exe -m pytest tests\ui -q                                                                                             # expect only the 20 failed + 7 errors baseline
```
Never run bare `pytest` (brief 2.4: full run aborts). Manual: `.venv\Scripts\python.exe -m trigger_designer`, open `data\check.csv` via File Input, add Data Profile from the Report tab.

## 9. Pitfalls

1. `core/profile.py` shadows the stdlib `profile` only if `core/` itself is on `sys.path`; always import `trigger_designer.core.profile`.
2. `Expr.n_unique()` counts null as a value; always `drop_nulls()` first. `Expr.cast(Int64)` on NaN raises: filter finite **before** the cast (hist bins).
3. `pl.defer` re-runs on **every** collect (Data Preview collects `head(10)` then `head(n)`): all work goes through `get_or_compute`, never call `profile_frame` from the lambda directly.
4. Run recomputes everything inside the executor's 30 s timeout (`executor.py:94`). Full-mode profile of a big all-String CSV (22 s measured for 1M x 30) can time out; users switch the node to `head`/`random`. Raising the timeout belongs to plan 08; do not edit `SecurityConfig` here.
5. `ConfigDock` does not rebuild for the same content (`node_config.py:118`): the content must push new results into the live view (`on_inputs_processed`); do not call `refreshConfigDock(force=True)` from `processInputs`.
6. Worker results arrive after the view may be destroyed: always check `request_id` and catch `RuntimeError` on view access; keep workers in `_LIVE` or Qt aborts the process.
7. `registerUnboundDockWidgets` would snapshot-bind the spin boxes and the search box (double history, undoable typing): the root view must be `_undo_composite = True` and be the Qt parent of everything.
8. Never `QIcon.fromTheme`; new icons live under `ui/` so `theme_icons` recolours them; do not hand-edit `icons_rc.py`.
9. `getSocketValue` returns the first upstream socket wired to a consumer: a node taking **both** `D` and `P` of one Data Profile into two inputs would read socket 0 twice (brief 3.3). Not our bug; document in NODE_REFERENCE.
10. CSV `Y/N` and `001` style values are intentionally text: suggestions never change data; converting is the user's Select/Formula job.
11. Excel writing goes only through `core.excel.write_frame_xlsx` (plan 06); this plan's application code imports no Excel library. Until plan 06 lands the Excel button shows `Export failed: Excel export is unavailable...` and the Excel tests skip. `top_values` stays a JSON string; `None` cells are written blank by the helper.
12. `qt/models/polars_table_viewer.py` export methods call `write_excel` (needs xlsxwriter): do not reuse them; our view has its own export slots.

## 10. Interfaces (shared with plans 02 and 06)

* Brief 11.3 `DataProfile` / `ColumnProfile` / `profile_frame(frame, *, max_rows=None)` are implemented with **exactly** the listed fields
  (`name, dtype, count, null_count, null_pct, distinct_count, min, max, mean, sample_values`; `DataProfile.row_count, column_count, columns, sampled`) plus defaulted extensions
  (`settings`, `passes`, `seconds`, every column in 3.3 as an attribute, `top_values`, `histogram`, `date_format_hint`, `flags`, `suggested_type`). `max_rows=N` means `ProfileSettings(sample_mode="head", sample_rows=N)`.
* `profile_frame(frame, *, settings=ProfileSettings(...))`, `profile_table(frame, **settings) -> pl.DataFrame` (the schema of 3.3), `profile_summary(p) -> dict`, `PROFILE_SCHEMA`, `FLAG_ORDER`.
* Plan 02 (run record): in its `NodeRunRecord`, for `op == "report.data_profile"` store `profile_summary(content.current_profile())` when not `None`, else read the Run frame `execution_results[node][content.profile_variable_name]` (same columns, `flags` column).
  The node declares the profile variable through `node.param[1]`, so it survives pruning.
* Plan 06 (workpaper): `build_workpaper(..., profiles: list[DataProfile])` may call `profile_frame` itself or take the Run frame; the `flags` column is the stable key for a "data quality observations" sheet; `profile_to_tsv` /
  `write_profile_xlsx` is an adapter: plan 06 owns `core/excel/write_frame_xlsx` and the `xlsxwriter` dependency. Expected shape: `from trigger_designer.core.excel import write_frame_xlsx`; `write_frame_xlsx(frame: pl.DataFrame, path: str, *, sheet_name: str = "Sheet1") -> None` (raises on failure; `None` -> blank cell). If plan 06 names it differently only the import line in `write_profile_xlsx` changes. This plan never imports plan 06 code elsewhere.
* Plan 04 (audit tests) may reuse `NUM_RE`, `INT_RE`, `DATE_FORMATS` for text-to-number tests so both agree on what "looks numeric" means.

## 11. Revalidation 2026-10-28 (Polars 2.0.0, Python 3.14.8, branch `feature` @ `984a1fc`)

Supersedes the sections named in the banner. Everything here was checked by reading current code or running it, unless marked **unverified**.

### 11.1 Engine check: what was run and what it showed

The commit-1 code block (`core/profile.py`) was extracted verbatim and run with the project's own `.venv` (`polars 2.0.0`, `python 3.14.8`) on a
50,000-row, 19-column frame (number/zero-padded/decimal-comma/date/mixed/whitespace text; float, int, bool, date, datetime, duration,
categorical, enum, decimal, list, struct, binary, all-null, NaN-containing float), in all three sample modes, plus a `pl.defer` socket and an
all-String `scan_csv(infer_schema=False)` input.

| Check | Result |
|---|---|
| `profile_frame` in `full` / `head` / `random` | runs; `passes` = 4 / 4 / 5 as budgeted in 3.5; output schema equals `PROFILE_SCHEMA` (42 columns) |
| Dtypes incl. Duration, List, Struct, Binary, Null, Decimal, Enum | no exception; nested columns get null count only (3.4) |
| Suggested types / flags on the test frame | digit text -> `Int64` + `numeric_as_text`; zero-padded -> `String` + `leading_zeros`; `1,5` text -> `Float64` + `decimal_comma_suspected`; ISO dates -> `Date` + `date_as_text`; mixed -> `mixed_numeric_text`; padded text -> `leading_trailing_whitespace`; all-null -> `all_null`; NaN float -> `nan_values` |
| `pl.defer(fn, schema=PROFILE_SCHEMA)` | works; `collect_schema()` returns all 42 columns without calling `fn` |
| `scan_csv(infer_schema=False)` all-String | works; same suggestions as the in-memory frame |
| Deprecations | **one**: `is_in` with a same-dtype collection is "ambiguous and deprecated; use `implode`" (the `random` mode index filter). **Fixed in the commit-1 block above** (`is_in(keep.implode())`); after the fix the run emits no warnings |

Timing on this frame was ~0.2 s, but the 1M-row figures in 3.5 and pitfall 4 (7.8 s, 22.3 s, 4.3 s) are **from 1.44.2 / 3.13 and were not re-measured**; re-run `tests/benchmarks/test_data_profile_perf.py` before trusting them.
Not run: the unit tests of section 6.1 (they do not exist yet), and any Qt code.

### 11.2 Anchors re-verified against the current tree (use these, not the section 2 line numbers)

| Fact | Now |
|---|---|
| `ReportNodes` has one member `GRAPH`; append `DATA_PROFILE` after it | `core/node_configuration.py:71-72` |
| Lazy spec for Graph (add ours after it); helper-module exclusion set | `qt/widgets/nodes/__init__.py:122-128`; `_LAZY_HELPER_MODULES` at `:207-211` (now includes `Report.pyqtgraph_view`) |
| Shift+A menu reads `NODE_REGISTRIES` (unchanged mechanism) | `qt/helpers/context_menu_mixin.py:41-45` |
| `frame_schema` lives in `core/frames.py` (re-exported by `node_base`) | `core/frames.py:9` |
| Run executor per-node cap | `SecurityConfig.max_execution_time: float = 30.0` at `core/ExecutionCheck/executor.py:51` (enforced in `_execute_with_timeout`, `:163`) |
| `iter_dock_widgets`, `registerUnboundDockWidgets`, `_inside_composite` | `qt/node_base.py:622`, `:661`, `:689` |
| `ConfigDock.updateConfig(nodes, force=False)`; `_current_key` | `qt/docks/node_config.py:82`, `:29` (short-circuit body not re-read; **unverified**) |
| `is_previewable` accepts LazyFrame/DataFrame | `qt/models/preview_sampling.py:26` |
| Data Preview unwraps `entry["data"]` | `qt/docks/data_preview.py:346` |
| Off-thread pattern | `qt/models/preview_worker.py`: `_keep_alive` `:34`, `PreviewCollectWorker` `:71` |
| Table viewer export methods (still call `write_excel`; still do not reuse) | `qt/models/polars_table_viewer.py:1161` (`export_csv`), `:1186` (`export_excel`, `write_excel` at `:1205`) |
| Theme colour access | `qt/theme_manager.py:604` (`color`), `:836` (`get_theme_manager`) |
| `IconButton`, `TextButton`, `NoWheelComboBox` | `qt/widgets/common/config_widgets.py:56`, `:123`, `:146`; `Chip`, `ConfigSection`, `FormRow`, `EmptyStateLabel` **not re-located** (**unverified**; import them from `qt.widgets.common` as `shaping_support.py` does) |
| UI icon ids | `qt/resources.json`: `icon_copy` `:136`, `icon_save` `:138`, `icon_options` `:140`, `icon_refresh` `:141`, `icon_search` `:144`. These are `"mode": "material"` names, not SVG paths. **`icon_copy` now exists: drop the new `ui/copy.svg` of 3.10.** No Excel/export icon id was found: still new |
| `QTableView#ColumnTable` QSS | `resources/qt/themes/base.qss:2404-2410` (was `:2178`) |
| Report node icons present | `resources/qt/images/node_icons/Report/Graph.svg`, `Image.svg`; a `Profile` icon is still new |
| Count precedent (3.8) | gone: `Transform/count_records.py` is now a 50-line `ShapingNode` and the logic is `core/shaping/count.py` (it collects inside `run_node`, then `.lazy()`, plus a `describe` chip). Same idea, new shape |

### 11.3 Node layer: what replaces 3.8, 3.9 (hand-wiring), 3.11 and commits 2-4

**What changed.** Plan 07 landed. Nodes are now declarative:

* Qt-free logic lives in `core/shaping/<name>.py` with `DEFAULTS: dict`, `run_node(frames, settings) -> list[LazyFrame]` (one per output socket) and optional `describe(frames, settings) -> list[(text, tone)]` (dock chips).
* The Qt side is `class XContent(ShapingContent)` (class attrs `SETTINGS`, `MODULE`, `OUTPUT_KINDS`, `INPUTS`, `HISTORY`, `SUMMARY`, `FORM`, `PRESENTATION_SETTINGS`) and `class TriggerNode_X(ShapingNode)` with `content_class`, `output_text`. Reference implementations: `Transform/count_records.py`, `Report/graph.py` (Graph overrides `create_layout`, `after_execution`, and adds its own signals).
* **Generated code is generic**: `ShapingContent.get_code()` emits `from <MODULE> import run_node as _run_node` plus `json.loads(<settings json>)` and assigns every output variable (`var_<kind>_<id>`; unwired input -> `pl.DataFrame().lazy()` for all outputs). Live evaluation and Run call the same `run_node`.
* **Settings undo** is `ShapingContent.set_setting(key, value, text, merge_key)` (one undo step each); `FORM` builds the dock controls and is swept by the existing undo bindings. Settings persist under one key, `settings`.
* **Errors** are raised as `ShapingError` and shown through `translate_exception` / `node.set_error(...)` (plan 03 package `core/errors/` exists); the old "tooltip string + markInvalid" idiom in 3.8 is obsolete.

**Mapping for Data Profile (decided; replaces the cited sections):**

| Old plan | New |
|---|---|
| `core/profile.py` engine (3.2-3.7, commit 1) | **Unchanged.** Keep it; plans 02/06 depend on its interfaces (section 10). It is not itself a shaping module. |
| Hand-written `TriggerNode_DataProfile` + `DataProfileContent`, `processInputs`, `get_code` (3.8, commits 2-3) | New thin adapter `core/shaping/data_profile.py`: `DEFAULTS = {the six settings of 3.2}`; `run_node(frames, settings)` returns `[as_lazy(frames[0]), profile_table(frames[0], **settings).lazy()]` (collects inside `run_node`, so Run fails loudly, as Count does); `describe` returns the Full/Sample chip text of 3.6. Then `DataProfileContent(ShapingContent)` with `OUTPUT_KINDS = ("data", "profile")`, `INPUTS = 1`, `HISTORY = "Profile"`, `FORM` = one collapsible **Options** `FormSection` (`combo` sample_mode; `int` fields for rows, seed, top N, approx threshold, bins; `show_if` hides rows unless mode != `full` and seed unless `random`), and `TriggerNode_DataProfile(ShapingNode)` with `output_text = ("D", "P")`. Register as `@register_node(ReportNodes.DATA_PROFILE, NodeTypes.REPORT)`; op id `report.data_profile` is unchanged. |
| Settings undo texts / merge keys (3.11) | Replaced by `set_setting` with the same texts (`"Profile Sample Changed"`, `"Profile Rows Changed"` ...) passed as `text`; use `Field` bursts for the spin boxes. No bespoke `_sync_widgets_from_model` for the six settings. |
| `ProfileDockView`, worker, cache, `_undo_composite` (3.9-3.10, commit 4) | **Still needed**, but appended by overriding `create_layout`: call `super().create_layout(dock_layout)` for the Options form, then add the view (root `_undo_composite = True`, as before). `ProfileWorker` and `get_or_compute` are unchanged in design. |

**Decision needed in implementation (not optional): the dock must profile the full input, but the node base samples it.** `ShapingNode.processInputs`
passes `live_sample(entry["data"])` to the content, i.e. `frame.head(LIVE_SAMPLE_ROWS)` with `LIVE_SAMPLE_ROWS = 100` (`core/shaping/common.py:73`),
and it sets `param` to `live_sample` of every output. Consequences, and the resolution chosen here:

1. `TriggerNode_DataProfile` overrides `processInputs`: before delegating to `super().processInputs(...)`, store the **unsampled** upstream frame on the content (`content.full_frame = entry["data"]`, found the same way the base does with `getInputWithSocket(0)`). The dock worker and the `sample_mode` logic of 3.5-3.6 read `full_frame`. The 100-row `frames[0]` is used only for the output sockets and chips.
2. Live socket `D` is therefore the first 100 rows (like every shaping node); Run's `D` is the whole input. The plan's earlier "same object, unchanged, live" (3.8) no longer holds live. Say so in the chip: `describe` returns `("Live output: first 100 rows. Dock and Run profile the whole input.", "warning")`, same idiom as Count.
3. Live socket `P` is `head(100)` of the profile frame, which has one row per input column: **inputs with more than 100 columns show a truncated profile live**; Run is not truncated. Document in `NODE_REFERENCE.md`; do not work around it.
4. `get_code` is the generic one: Run recomputes from `_run_node([var], settings)`, inside the executor's 30 s cap (`executor.py:51`; pitfall 4 still applies, and the 22 s figure is a 1.44.2 measurement).

If implementers would rather keep the node entirely generic (no `full_frame`), the fallback is "dock profiles the 100-row sample and labels it so"; that makes the node much less useful on real files and is **not** the plan.

### 11.4 Other drift to handle

* **Plan 06 has not landed.** `core/excel/` does not exist and `xlsxwriter` is not declared in `pyproject.toml` (the string appears only in `core/errors/catalogue.py:356` and `translator.py:795`, which translate the missing-module error). Pitfall 11 already says what to do: the Excel button must degrade to a chip message and the Excel tests must skip until `core.excel.write_frame_xlsx` exists. Do not add `xlsxwriter` from this plan.
* **Icons.** Use `icon_copy`, `icon_save`, `icon_refresh`, `icon_search` (all exist, material-mode). Add one new id for Excel export and the node icon SVG under `Report/`. Whether a suitable Material name exists in `qt-material-icons` was **not checked**.
* **Charts.** `pyqtgraph` 0.14.0 is a declared dependency and `Report/pyqtgraph_view.py` exists. The decision in 3.1 (painted `MiniBarChart`, no plotting library) is unchanged; a pyqtgraph bar chart is a possible alternative if the owner prefers, but is not adopted here.
* **Environment strings.** `pyproject.toml` now requires `>=3.14.0,<3.15`, pins `polars[pyarrow]==2.0.0`, `numpy==2.5.4`, ruff targets `py314`. Replace "Polars 1.44.2, Python 3.13.12" wherever commands or expectations are stated. The test baselines in section 7/8 ("334+ unit, 20 failed + 7 errors in ui") and the PyQt6 assumptions in the brief predate this and must be re-measured; the app now uses PySide6 through `qtpy` (`pyproject.toml`). `docs/plan/00-codebase-brief.md` has the same stale versions (not edited here).
* **Not re-verified** (still as originally written, so treat with care): sections 5, 6, 9 pitfalls 5-8, and the section 4 steps for commit 5 (e2e golden paths, `TRIGGER_UPDATE_E2E_GOLDENS`). The test files named in section 6 do not exist.

### 11.5 Amendments from the first real-data run (2026-10-28)

Running the engine on `savedfiles/Example_2_Retail_Ledger/data/orders.csv` (40,800 rows, read as all-String) showed four weaknesses. They are fixed as follows; the output
schema (`PROFILE_SCHEMA`, 42 columns) does **not** change.

1. **`mixed_date_text`** (new flag). String column, `base > 0`, `0.5 <= date_like/base < 0.98` (constant `DATE_MIXED_MIN = 0.5`) and `integer_like/base < 0.98`
   (so 8-digit `yyyymmdd`-looking ids never fire it). Meaning: mostly dates, but a real share are not (blank, a second format, a sentinel). The `Order TS` column in `orders.csv` (about 91% date-like) is the motivating case.
2. **`negative_values`** (new flag, info). `numeric_basis != ""` and `negative_count >= 1`. Native and parsed-text columns alike; a trailing-minus value like `123-` is **not** a negative (it is counted by `trailing_minus`).
3. **`outlier_suspected`** (new flag, warning). `numeric_basis != ""`, at least 20 non-null rows, `std > 0`, and `max(max_numeric - mean, mean - min_numeric) / std >= 10.0` (constant `OUTLIER_Z`). It needs no extra pass: it uses figures P1 already has.
   A uniform column peaks near z = 1.7 and a normal one of 40,000 rows near 4, so 10 means "look at this", not "this is wrong".
4. **Flag severity.** New module constant `FLAG_TONE: dict[str, str]` maps every flag to `"info"` or `"warning"`; the dock draws `info` chips muted and `warning` chips in the `warning` theme colour. `info`:
   `numeric_as_text`, `date_as_text`, `high_cardinality`, `constant`, `negative_values`. Everything else is `warning`. The `flags` column keeps the plain comma list (no tones in data). *Reason:* on a CSV every numeric column carries `numeric_as_text`; that is true and useful but must not look like a defect.
5. **`min_value` / `max_value` for text that looks numeric or date-like.** After the suggestion is made, if `suggested_type` is `Int64`/`Float64` the two texts are the **parsed** min and max (`f"{x:.15g}"`, so `884297`, `1002.89`);
   if it is `Date`/`Datetime` they are the parsed min/max as ISO text (`%Y-%m-%d` / `%Y-%m-%d %H:%M:%S`; the first matching format wins per value, so `dd/mm` vs `mm/dd` ambiguity is not resolved). Any other String column keeps the lexicographic min/max of 3.3.
   *Reason:* lexicographic order of `1002.89` / `999.54` / `31-12-2024` is misleading. The numeric range comes from P1 figures that already exist. The date range is computed in the **detail pass (P2)**, only for columns whose suggestion is `Date`/`Datetime`: adding four parse aggregates to P1 for every text column was measured at +54% on that pass (4.3 s to 6.6 s for ten 1M-row text columns), so it was moved. No extra collect.

6. **Stable floats.** `mean_value`, `median_value`, `std_value` and `sum_value` are rounded to 12 significant digits (`_stable`). Found by test: Polars adds floats across threads, so two runs over identical data differed in the last bit of `std_value` (`...37343` vs `...37344`). Min/max are exact and unrounded. *Reason:* the product promise is reperformance; the same file must give a byte-identical profile table.

`FLAG_ORDER` becomes: `all_null, all_blank, constant, high_cardinality, mostly_null, mixed_numeric_text, mixed_date_text, leading_zeros, trailing_minus, decimal_comma_suspected, leading_trailing_whitespace, numeric_as_text, date_as_text, negative_values, outlier_suspected, nan_values, inf_values`.

**Changed expectations in 6.1** (fixture `FX`): `qty` flags `["negative_values"]` (not `[]`); `price` flags `["negative_values","nan_values","inf_values"]`;
`test_flags_have_no_false_positives` asserts `flag == []` and that `qty` has **no warning-tone flag**. `amount`, `sap`, `id`, `when`, `locale` flags are unchanged. New tests: `test_mixed_date_text_flag`, `test_negative_values_flag`, `test_outlier_flag`, `test_text_min_max_is_parsed`, `test_flag_tone_covers_every_flag`.
**Changed expectation in 6.4** (`MESSY_CSV`): `posted` is 5 of 6 date-like (83%), so its flags are `mixed_date_text` (not `""`).

### 11.6 Implementation status (2026-10-28, uncommitted on `feature`)

Built as section 11.3 describes, with these differences from the original text:

| Area | What exists | Deviation from the plan |
|---|---|---|
| Engine | `core/profile.py` (+ `profile_to_tsv`, `write_profile_xlsx`, `profile_summary`, `FLAG_TONE`) | 11.5 amendments; floats rounded to 12 digits; `is_in(...implode())` |
| Runner | `core/shaping/data_profile.py`: `DEFAULTS`, `LIMITS`, `normalize`, `run_node`, `mode_text`, `describe` | new (the shaping contract replaces the hand-written node) |
| Node | `qt/widgets/nodes/Report/data_profile.py`: `DataProfileContent(ShapingContent)`, `TriggerNode_DataProfile(ShapingNode)`; enum `ReportNodes.DATA_PROFILE`, lazy spec, `node_data_profile` icon | `DEFER_EVALUATION = False`; overrides `processInputs` to keep the unsampled frame and to fail on a broken upstream plan |
| Settings | The six settings are a collapsed **Options** `FormSection` built by `ShapingContent`; undo is `set_setting` | No `settingChanged` signal, no per-setting handlers, no `apply_settings` on the view (11.3 table) |
| View | `qt/widgets/profile_view.py`: `ProfileDockView`, `ProfileTableModel`, `NullBarDelegate`, `MiniBarChart` and the pure helpers `detail_rows`, `status_text`, `chart_for`, `suggested_text`, `FLAG_LABELS` | Rows start in **input column order** (header click sorts); fixed starting column widths (`COLUMN_WIDTHS`), found necessary by rendering the real dock; chip tone `warning` added to `base.qss` |
| Worker | **removed** (see 11.8): the live profile is computed on the GUI thread | the plan's `ProfileWorker`, request ids and stale-result handling no longer exist |
| Icons | node SVG `Report/Data Profile.svg`; `icon_export_excel` (Material `table_view`; confirmed to render in the dock, see `docs/plan/examples/data_profile/dock_default.png`) | `icon_copy` already existed; no new `ui/copy.svg` |
| Excel | `write_profile_xlsx` calls `core.excel.write_frame_xlsx`; the button degrades to a chip message | plan 06 has not landed; the workbook tests skip until it does |
| Docs | `docs/NODE_REFERENCE.md` row | - |

**Tests:** `tests/unit/test_profile_core.py` (42, one skipped for the Excel helper), `tests/unit/test_data_profile_node.py` (15), `tests/ui/test_data_profile_dock.py` (18, one skipped), `tests/e2e/test_data_profile_golden.py` (2) with golden `tests/e2e/fixtures/expected/data_profile_messy.csv`, fixtures in `tests/support/profile_fixtures.py`.
Not written: the opt-in benchmark file of 6.5 (figures below were measured with throwaway scripts).

**Measured on Polars 2.0.0 / Python 3.14.8 (replaces the 1.44.2 figures in 3.5 and pitfall 4):**

| Case | Time | Passes |
|---|---|---|
| 1M rows x 30 columns, in memory | 9.5 s | 4 |
| 1M x 30 all-String CSV (344 MB), `full` | 42.9 s (measured before the date range moved to P2; not re-measured) | 4 |
| same CSV, `head` 100k | 2.6 s | 4 |
| same CSV, `random` 100k | 3.7 s | 5 |

**Known limitation, a Polars 2.0 regression, not an engine cost: wide frames.** The same code takes 1.0 s on Polars 1.44.2 and 27 s on 2.0.0 for 1,500 columns; time grows roughly quadratically in the column count on 2.0.0:

| Columns | Polars 2.0.0 (int / text columns) | Polars 1.44.2 |
|---|---|---|
| 30 | 0.15 s / 0.17 s | 0.02 s / 0.09 s |
| 100 | 0.41 s / 0.51 s | 0.04 s / 0.20 s |
| 200 | 0.99 s / 1.29 s | 0.08 s / 0.40 s |
| 400 | 2.8 s / 3.7 s | 0.15 s / 0.88 s |
| 800 | 8.8 s / 10.3 s | 0.38 s / 2.1 s |

Tried and **not** helpful: turning off any single optimizer pass, turning all of them off (16 s), splitting the select into 25 to 250-column chunks run through `collect_all` (about 10 s), projecting each chunk to its own columns first (about 10 s). Up to a few hundred columns this is well under a few seconds and the dock computes off the GUI thread, so nothing is mitigated here. Run has the 30 s per-node cap (`SecurityConfig.max_execution_time`), so an input of about 1,000+ columns can time out in Run in `full` mode.
Worth reporting upstream with the `bench6` pattern (a `select` of ~14 aggregate expressions per column over an N-column frame).

**Other finding:** Polars adds floats across threads, so the last bit of a mean/std/sum varied between identical runs; all float aggregates are rounded to 12 significant digits (`_stable`), pinned by `test_profile_is_byte_identical_across_runs` and `test_two_runs_give_the_same_profile`.

**Pre-existing, unrelated:** `tests/e2e/test_workflow_goldens.py::test_file_outputs_match_golden[split]` fails identically on a clean `HEAD` (checked in a temporary worktree): the sample input has a leading unnamed index column, which Polars 2.0 names `column_1`, while `tests/support/frames.read_frame` only strips `""`/`Unnamed:*`.

### 11.7 Changes after first use (2026-10-28)

First use of the dock showed it profiling 100 rows ("Data: 100 rows") and offering too little. What changed:

**A premise in 11.3 was wrong and is corrected.** 11.3 said the node could keep "the unsampled upstream frame" for the dock. It cannot: File Input and every shaping node already trim their live output (`file_input.py:1804`, `ShapingNode.processInputs`), so the node only ever receives the first 100 rows during live evaluation. The only place the whole input exists is a workflow **Run**. `full_frame` therefore holds whatever the upstream emitted (100 rows in practice) and is kept only so a test source that emits more is profiled in full.

| Request | What was built |
|---|---|
| Show the full report after a Run | The Run executes `run_node` over the whole input and leaves the profile table in `var_profile_<id>`. `DataProfileContent.on_run_result` (called on the GUI thread by `TriggerSubWindow._on_node_finished`, a small additive hook in the shared run code) rebuilds a `DataProfile` with `profile_from_frame` and the dock switches to it (`view.source == "run"`, tooltip "Result of the workflow run at HH:MM:SS"). It stays until a setting changes (the key no longer matches), the Refresh button is pressed, or the next Run replaces it. It is **not** invalidated by upstream edits after the Run; the tooltip's run time is the cue. |
| ... which needs the table to carry the chart data | `PROFILE_SCHEMA` gained `histogram` (JSON list of bin counts, after `top_count`): **43 columns**, additive. The table a user exports is now exactly what the dock and the report render. `profile_from_frame(frame, settings)` is the inverse of `profile_to_frame`; both are round-trip tested. |
| Chip wording | `status_text`: "Data: 40,800 rows" (was "Full data: ..."); samples still read "Sample: first N rows" / "Sample: random N rows (seed S)". The Sample option's first choice is "All rows". |
| Remove the "1 input - 2 outputs - profile table" line | `DataProfileContent.dock_summary()` returns `""`; the dock hides the line for this node only. |
| Are we saving the report as HTML? | Not before; now yes. `core/profile_report.py` (Qt-free) holds the wording helpers and `profile_to_html`: one self-contained page (no scripts, no external files; offline-safe), a summary table that links to a card for **every** column (stats, flags, histogram or top values). Stray leading/trailing spaces are shown as amber dots. |
| A button to see the full report | Toolbar button "Open the full report" writes the HTML to a temp file and opens it in the default browser (`QDesktopServices.openUrl`); temp files are removed at exit. Chosen over an in-app window because the app ships no WebEngine and one renderer then serves both the button and the export. |
| One export button: CSV, HTML, Excel | One Export button with a menu: Copy to clipboard, CSV file..., HTML report..., Excel workbook.... The separate copy/CSV/Excel buttons are gone. Toolbar is now: filter, Full report, Export, Refresh. |
| No Excel write | `xlsxwriter==3.3.0` added to `pyproject.toml` and `uv.lock` (the lock diff is the new package only). New `core/excel/__init__.py: write_frame_xlsx` (Polars `write_excel`: an Excel table with filter buttons, bold frozen header, fitted widths, nulls blank). This also fixes File Output's Excel format, which called the same missing library. Plan 06 still owns any richer workbook. |
| "What is bins?" | Renamed **Chart bars** ("Number of bars in a number column's distribution chart"). Every option now has a hint; "Approx above" became **Estimate over**, "Rows" became **Rows (N)**. |

**Refresh button** now discards the last Run's result and re-profiles the live rows (its job was always "recompute from what the canvas has").

**Intermittent crash found while testing (open, unexplained):** see 11.8.

### 11.8 No background thread; one open crash (2026-10-28)

**Decision (owner): the profile does not run on another thread.** The live profile is computed on the GUI thread (`request_profile` calls `get_or_compute` directly). That is cheap because while you edit the canvas holds at most 100 rows; the profile of all rows is the workflow Run's, delivered by `after_execution` with nothing recomputed. Removed: `qt/models/profile_worker.py`, request ids and stale-result handling, `ProfileDockView.set_loading`, and a garbage-collection pause that had been added for the worker. This supersedes the threading text in 3.9 and pitfalls 3 and 6.
Cost: the Polars 2.0 per-column overhead (11.6) now blocks the GUI instead of a worker: about 0.5 s at 100 columns, 1.3 s at 200, 3.7 s at 400, 10 s at 800 (live rows only; the Run's cost is unchanged).

**Open: intermittent access violation in `tests/e2e/test_data_profile_golden.py`.** Two Run tests back to back (`test_run_gives_the_node_the_whole_input`, then `test_open_dock_switches_to_the_run_result`, which has the dock open) end in `Windows fatal exception: access violation` (exit 139) about 1 run in 15-45. The fault is always in the second test, inside `run_workflow_and_wait`: the main thread is in Qt's event loop, the executor threads are idle, and no Python frame is active at the fault. It still happens with no thread of this node in the process (2 of 45 after removal).
Ruled out by experiment (each followed by a serial loop that still crashed): the profile worker thread; garbage collection during a profile; the `destroyed` handler capturing the view; a DataFrame carried through a queued cross-thread signal (now payload-free); the worker's cleanup running on its own thread; a slow live profile overwriting the Run result (a real race, fixed, but not the crash).
Not reproduced: the second test alone (0/100); a Run with the dock open for Count or Data Profile, with or without File Output sinks (0/100 each); an unrelated Graph run test before my dock test (0/100); the dock view hammered 1,500 times on its own. **Caveat:** those controls ran 2-4 processes in parallel, which can hide a timing race; the fair serial control (the same two-test sequence for the plain Count node) was cancelled. So it is **not known whether the crash is specific to this node or already in the app's Run path.**
If it needs settling: write two back-to-back Run tests for Count, the second with the dock open, and loop them serially (about 100 runs, ~5 minutes). A crash there makes it pre-existing; none makes it this node's.

**Addendum (same day): nothing of this node runs off the GUI thread.** The first Run hand-off used `after_execution` (executor thread) plus a signal. It now uses `on_run_result`, which `TriggerSubWindow._on_node_finished` (`qt/helpers/workflow_execution_mixin.py`, GUI thread) calls with the node's variables after a successful run: an 11-line additive hook in shared code, wrapped so a raising node cannot abort the process. The content has no signal, no queued payload and no thread of its own (`test_the_content_has_no_executor_thread_hook`). The only threads left are the app's own: every node's generated code, including this node's `run_node`, executes on the workflow executor thread, as it does for all nodes.
**The crash is not explained by any of this:** after the change it still happened in 3 of 60 serial runs of the two-test sequence (a batch of 45 before it was clean, which was luck at about a 3-5% rate). Counting every serial loop with a crash-prone configuration: 11 crashes in about 250 runs. Treat `test_open_dock_switches_to_the_run_result` as flaky until the Count-node control in this section has been run.

### 11.9 Follow-ups (2026-10-30)

* **Wide inputs.** Because the live profile runs on the GUI thread and Polars 2.0 plans it in roughly quadratic time in the column count (11.6), the live preview is skipped above `LIVE_MAX_COLUMNS = 150` columns (about 1 s at the limit). The dock shows "Live preview skipped" and a note ("N columns: ... Run the workflow to profile every column."); a Run still profiles every column and the dock then shows it. Inputs of about 1,000+ columns can still hit the Run's 30 s per-node cap.
* **HTML report checked.** Rendered and inspected structurally (no horizontal overflow at 1,100 px or 375 px, every summary row links to its card, every column has a card with its chart). Not judged visually: the review pane was too small to see.
* **File Output's Excel format** (same missing `xlsxwriter`) now has a regression test, as does the declared dependency.
