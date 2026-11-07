# Trigger Designer bug hunt - prioritized fix plan

Date: 2026-10-31
Repository: `TriggerEditor` / `trigger_designer`
Branch: `feature`
Scope: core shaping, audit, workpaper, input/output, Qt models, undo, CLI
Method: source review, ruff correctness pass, focused runtime probes, full unit suite

Baseline at time of writing:

```
2 failed, 2675 passed, 2 skipped, 1 xpassed in 1284.04s (21:24)
```

The two failures are documentation paths, not test flakiness (finding H4).

This plan is ordered by user impact, not by file order. Each finding has a
reproduction, a suggested fix, and the tests that should pin it.

---

## Priority summary

| ID | Severity | Area | One line |
|---|---|---|---|
| H1 | High | Shaping | Text amounts are parsed by removing every comma, so `1.234,50` becomes `1.2345` and `12,5` becomes `125` |
| H2 | High | Select | Auto-Detect Types turns leading-zero IDs such as `0001` into Int64, dropping the zeros |
| H3 | Medium-high | Cleansing | "Remove all-null columns" can return a 0-column frame and reports removed rows |
| H4 | Medium | Tests / docs | Two unit tests still read docs files that moved to `docs/internal/` |
| M1 | Medium | Table viewer | A 0-row frame with columns shows no columns or headers |
| M2 | Medium | Table viewer | "All Columns" search ignores numeric and date columns |
| M3 | Medium | Formula | Choosing target type Time or Categorical silently produces String |
| M4 | Medium | Text to Columns | Rows mode with Skip empty still emits a null row for a null source cell |
| M5 | Medium | Profile | `sampled` is true when the frame has exactly `sample_rows` rows |
| M6 | Medium | File Input UI | Excel preview fallback ignores sheet, start row, header and row limit |
| M7 | Medium | Audit store | Sealing appends after a corrupt middle index line; verify ignores those records |
| M8 | Medium | Select Records | Ranking a non-numeric text column silently selects nothing |
| M9 | Low-medium | Pivot | Numeric aggregation over non-numeric text silently yields null pivot cells |
| M10 | Low | Cleansing | Change statistics count whole columns/rows even when nothing changed |
| L1 | Low | Qt nodes | Mutable default arguments (`inputs`, `outputs`, `hashmap`) |
| L2 | Low | Executor | Uncommitted `after_node` try/except is dead code and would fail a run |
| L3 | Low | Table viewer | Theme refresh emits `dataChanged` for an index beyond the current page |
| L4 | Low | Table viewer | Chunk cache never evicts when `cache_size < chunk_size` |
| L5 | Low | Table viewer | CSV/Excel export ignores the current model sort order |
| L6 | Low | Excel | Empty strings are exported as blank cells, not empty strings |

---

## P0 - High

### H1. Shaping money parsing silently misreads decimal-comma values

**Where**

- `src/trigger_designer/core/shaping/common.py:111-121` (`numeric_expr`)
- `src/trigger_designer/core/shaping/reshape.py:72-74` (Pivot numeric functions)
- `src/trigger_designer/core/shaping/window.py:133-135` (rank, cum_*, rolling_sum)
- `src/trigger_designer/core/shaping/running_total.py:35-37`
- `src/trigger_designer/core/shaping/select_records.py:66` (largest/smallest ranking)
- Reference implementation: `src/trigger_designer/core/utils/amounts.py:18-74`
  (`amount_expr`) already handles decimal commas for Audit, Reconcile and Workpaper.

**Symptom**

`numeric_expr` strips every comma before casting:

```python
column.cast(pl.String)
      .str.replace_all(",", "")
      .str.strip_chars()
      .cast(pl.Float64, strict=False)
```

Therefore:

| Input text | Expected | Actual |
|---|---|---|
| `12,5` | 12.5 | 125.0 |
| `1.234,50` | 1234.5 | 1.2345 |
| `1 234,50` | 1234.5 | null (space remains) |
| `1,234.50` | 1234.5 | 1234.5 (correct) |

The wrong value is not flagged as unreadable, so Pivot, Window, Running Total
and Select Records silently compute and display wrong totals.

Reproduced with:

```python
from trigger_designer.core.shaping import reshape, window, running_total
vals = ["1.234,50", "12,5", "1,234.50"]
# numeric_expr -> [1.2345, 125.0, 1234.5]
# Pivot sum of x = 1.2345 + 125 = 126.2345
# Window cum_sum -> [1.2345, 126.2345, 1360.7345]
```

**Important context**

`docs/nodes/transform/pivot.md:66` currently says "commas are removed; text
that is not a number is ignored". That documents the US-only rule, so this is
partly intentional. It is still a product bug because:

- the app's own amount parser treats decimal commas as valid numbers;
- the four nodes give no warning that `12,5` was read as 125;
- the result is a silent financial misstatement.

**Suggested fix**

1. Preferred: change `numeric_expr` for `pl.String` columns to the shared
   `core.utils.amounts.amount_expr`, so `1.234,50`, `12,5`, `1'234,50` and
   `(12.00)` are handled the same way Audit and Reconcile handle them.
2. If US-only input is an intentional product rule, add validation: detect
   values that look decimal-comma formatted and raise `TD-SHAPE-004` (or show a
   warning chip) instead of silently accepting a wrong number.
3. Update `docs/nodes/transform/pivot.md`, `docs/nodes/transform/window.md`,
   `docs/nodes/transform/running-total.md` and the Select Records doc with the
   chosen rule.

**Tests**

- Unit table for `numeric_expr`: `12,5` -> 12.5, `1.234,50` -> 1234.5,
  `1,234.50` -> 1234.5, `1 234,50` -> 1234.5, `abc` -> null.
- Pivot Sum, Window cum_sum and Running Total over the same table must agree.
- A regression test that US-format input still works.

---

### H2. Auto-Detect Types destroys leading zeros

**Where**

- `src/trigger_designer/core/shaping/select.py:203-206` (integer parse in
  `infer_dtype`)
- `src/trigger_designer/qt/widgets/nodes/Preparation/select.py:699-713`
  (`bulk_auto_detect`)
- Conversion later in `select.py:240-255` (`run_node` casts to the chosen dtype)

**Symptom**

`infer_dtype(["0001", "0002", "0003"])` returns `("Int64", None)`. Auto-Detect
then sets the column dtype to Int64, and the Select node casts the values to
`1, 2, 3`, losing the accounting identifiers' leading zeros.

A user doing the documented workflow "Auto-Detect Types (All) as a starting
point" corrupts identifier columns without any warning.

**Suggested fix**

Before returning `Int64`, reject values that look like zero-padded identifiers:

- any non-empty value matching `^[+-]?0\d+$`, or
- a value whose stripped text has more than 1 character and starts with `0`
  (and is not a decimal such as `0.5`).

Return `("String", None)` for those, matching the existing leading-zero logic
in `core/profile.py` (`LEAD0_RE`, `_suggest` and the `leading_zeros` flag), or
warn in the dock.

**Tests**

- `infer_dtype(["0001", "0002"])` -> String.
- `infer_dtype(["0", "1", "2"])` -> Int64 (single zero is fine).
- `infer_dtype(["0.5", "1.5"])` -> Float64.
- Select round trip keeps `"0001"` when auto-detected and run.

---

## P1 - Medium

### H3. "Remove all-null columns" can return a 0-column frame

**Where**

- `src/trigger_designer/core/utils/cleansing_util.py:92-98`
  (`REMOVE_ALL_NULL_COLS`), `:100-105` (`REMOVE_ANY_NULL_COLS`)
- `src/trigger_designer/core/shaping/cleansing.py:40-41`
- Stats at `cleansing_util.py:133-134`

**Symptom**

When every column is all null, `cols_to_keep` is empty and
`self.df.select([])` returns shape `(0, 0)`. The row count is lost, so downstream
nodes see a schema-less frame, and `CleansingStats.rows_removed` reports the
original row count even though the operation only removed columns.

Reproduced:

```python
d = pl.DataFrame({"a": [None, None], "b": [None, None]})
c = DataCleansing(d)
c.handle_nulls(NullStrategy.REMOVE_ALL_NULL_COLS)
# result shape (0, 0); stats rows_removed=2, columns_removed=2
cleansing.run_node([d.lazy()], {"remove_null_columns": True})[0].collect().shape
# (0, 0)
```

**Suggested fix**

- If `cols_to_keep` is empty, raise a clear `ShapingError` (for example
  `TD-SHAPE-005`, "Every column is empty; keep at least one column or turn off
  Remove all-null columns") instead of returning a 0-column frame.
- Do not add to `rows_removed` for column-only strategies; only
  `columns_removed` should change.
- Apply the same rule to `REMOVE_ANY_NULL_COLS`.

**Tests**

- All-null single-column and multi-column inputs raise the documented error.
- Mixed all-null and non-null columns keep the non-null column and all rows.
- Stats for column-only operations report `rows_removed == 0`.

---

### H4. Two unit tests point at docs that moved to `docs/internal/`

**Where**

- `tests/unit/test_docs_present.py:22` reads
  `docs/ENHANCED_EXECUTOR_GUIDE.md`
- `tests/unit/test_workpaper_output_icon.py:46` reads
  `docs/NODE_REFERENCE.md`
- Current files:
  - `docs/internal/ENHANCED_EXECUTOR_GUIDE.md`
  - `docs/internal/NODE_REFERENCE.md`

**Symptom**

The full unit suite ends with 2 failures:

```
FAILED tests/unit/test_docs_present.py::test_executor_guide_documents_no_missing_features
FAILED tests/unit/test_workpaper_output_icon.py::test_node_reference_has_a_workpaper_output_row_with_the_real_icon
FileNotFoundError
```

The docs move happened in commit `ab9decb6`; the tests were not updated.

**Suggested fix**

Update the two test paths to `docs/internal/...`, or restore the files at the
root if external links still require those paths. Check `docs/index.md` and the
MkDocs navigation for links that still point at the old locations. The
`test_every_doc_file_is_non_empty` test already recurses, so no other path
change is needed there.

**Tests**

- `uv run --project . pytest tests/unit/test_docs_present.py tests/unit/test_workpaper_output_icon.py -q`
- Full unit suite should end with 0 failures.

---

### M1. A 0-row frame with columns loses its columns in the table viewer

**Where**

- `src/trigger_designer/qt/models/polars_table_viewer.py:114-116`
- `:123-137` (`_update_column_info`)
- `:1049-1055` (`search_columns` early return)

**Symptom**

Polars reports any 0-height DataFrame as `is_empty() == True`, even when it has
a schema. `_update_column_info` therefore sets `_column_names = []`,
`columnCount() == 0`, and `headerData(0, Horizontal)` falls back to
`"Column 0"`.

Reproduced:

```python
m = PolarsTableModel(pl.DataFrame({"a": [], "b": []}))
m.columnCount()            # 0
m.headerData(0, 1, 0)      # "Column 0"
```

An empty filter, join or Select result therefore shows a blank table with no
headers, instead of the columns the user asked for.

**Suggested fix**

Use `width > 0` / `height` rather than `is_empty()`:

```python
if self._dataframe.width > 0:
    self._column_names = self._dataframe.columns
    self._column_types = dict(zip(...))
    self._total_rows = self._dataframe.height
    self._total_columns = self._dataframe.width
else:
    ...empty...
```

Also initialize the same way in `__init__` and let `search_columns` return the
frame columns even when it has no rows.

**Tests**

- `pl.DataFrame(schema={"a": pl.Int64, "b": pl.String})` has `columnCount()==2`.
- `pl.DataFrame({"a": [], "b": []})` has 2 column headers and `rowCount()==0`.
- An empty search result still shows headers.

---

### M2. "All Columns" search ignores non-text columns

**Where**

- `src/trigger_designer/qt/models/polars_table_viewer.py:1057-1100`
- Filter at `:1094`: `if self.dataframe[col].dtype in [pl.Utf8, pl.String]`

**Symptom**

With the "All Columns" scope selected, only String columns are searched. IDs,
amounts and dates are invisible to the search box.

Reproduced with a table `{id: [1001, 1002], d: [2024-01-05, 2024-01-06]}`:

```python
viewer.apply_search("1001")  # 0 rows
viewer.apply_search("2024")  # 0 rows
```

**Suggested fix**

Cast every column to text for the search predicate, as the single-column path
already does:

```python
pl.col(col).cast(pl.Utf8, strict=False)
```

Guard nested/binary columns (skip them or catch the cast error) and keep
`fill_null(False)`. The same is needed for Categorical.

**Tests**

- Numeric, Date and Categorical columns are found by the All Columns search.
- The single-column selector still restricts to that column.
- An empty search clears the filter.

---

### M3. Formula target type Time or Categorical silently produces String

**Where**

- `src/trigger_designer/core/shaping/formula.py:34-53` (`DTYPE_OPTIONS`,
  `DTYPE_TO_DUCKDB`)
- `:199` (`normalize_to_supported_dtypes(result)`)
- `src/trigger_designer/core/utils/dtype_utils.py:43-58`
  (`pl.Time -> pl.String`, `pl.Enum -> pl.Categorical`)

**Symptom**

The dock offers Time and Categorical target types, but:

- Time is mapped to DuckDB `TIME`, then `normalize_to_supported_dtypes` maps
  `pl.Time` to `pl.String`;
- Categorical is mapped to DuckDB `VARCHAR` and stays `pl.String`.

Reproduced:

```python
formula.run_node([df], {"sections": [
    {"target_column": "c", "formula_text": "1", "target_dtype": "Categorical"}
]})[0].collect().dtypes
# String, not Categorical
```

The user selects a type the output does not have.

**Suggested fix**

Pick one policy:

- Remove Time and Categorical from `DTYPE_OPTIONS`/`DTYPE_TO_DUCKDB` if they
  cannot be produced, and update the node docs; or
- For Categorical, cast the result `String -> Categorical` after the query; for
  Time, either keep String with a clear note or add Time to supported dtypes.

**Tests**

- Every option in `DTYPE_OPTIONS` produces that dtype or is not offered.
- A Categorical target round-trips as Categorical if kept.

---

### M4. Text to Columns Rows + Skip empty keeps a null source row

**Where**

- `src/trigger_designer/core/shaping/text_to_columns.py:136-157`
- `:138` (`list.drop_nulls()` for `max_splits`)
- `:149-150` (`skip_empty` filters `!= ""` but not null)
- `:155-156` (`explode(..., empty_as_null=True, keep_nulls=True)`)

**Symptom**

A null source cell produces an empty list after splitting, then `explode` with
`empty_as_null=True` emits one null row. `skip_empty=True` does not remove it
because the filter only removes `""`, not null.

Reproduced:

```python
s = ["a,b", None, "", "c,"]
# output=rows, max_splits=1, skip_empty=True
# -> ['a', 'b', None, None, 'c']   # the null source row survives
```

**Suggested fix**

Decide the contract:

- If Skip empty means "drop empty pieces", filter nulls after the explode when
  `skip_empty` is on (`pieces` itself or the exploded column), so a null source
  cell contributes no rows; or
- Document that a null source cell always contributes one null row, even with
  Skip empty, and add a test pinning that.

The first is more consistent with the UI wording "Drops pieces that are empty".

**Tests**

- Null source, `""` source and `"c,"` source under both `skip_empty` values.
- Ensure the original row count is preserved when `skip_empty=False`.

---

### M5. Profile marks a full read as "sampled" when it has exactly N rows

**Where**

- `src/trigger_designer/core/profile.py:465-470`

**Symptom**

`_prepare` in `head` mode does `df = lf.head(n)` and returns
`sampled = df.height >= n`. When the input has exactly `sample_rows` rows, no
sampling happened, but the profile and the run record report `sampled=True`.

Reproduced:

```python
profile_frame(pl.DataFrame({"a": [1, 2, 3]}),
              settings=ProfileSettings(sample_mode="head", sample_rows=3)).sampled
# True, but all 3 rows were read
```

**Suggested fix**

Read `n + 1` rows, keep only `n`, and set `sampled = df.height > n`; or compare
the total row count when it is already known. Do not add an extra collect in
the common case if it can be avoided.

**Tests**

- Exactly N rows -> sampled False.
- N+1 rows -> sampled True, profiled row count N.
- Random mode keeps its current behaviour.

---

### M6. Excel preview fallback ignores the chosen sheet and row settings

**Where**

- `src/trigger_designer/qt/widgets/nodes/InOut/file_input.py:1591-1604`

**Symptom**

When fastexcel fails to load the preview, the fallback is:

```python
df = pl.read_excel(fileName, sheet_id=0)
```

This ignores:

- `self.selected_sheet` (always uses the first sheet);
- `self.start_row`;
- `self.first_row_contains_field_names`;
- the configured row limit is only applied after reading.

The preview can therefore show a completely different sheet and header than
Run will use.

**Suggested fix**

Pass the selected sheet and header/skip options to `pl.read_excel` (for
example `sheet_name=self.selected_sheet`,
`read_options={"has_header": ..., "skip_rows": ...}` where supported), or on
fallback return an empty frame plus an explicit "preview unavailable, Run still
uses the configured settings" message rather than a misleading preview.

**Tests**

- Monkeypatch `fastexcel.read_excel` to raise; assert the fallback uses the
  selected sheet and start row.
- Assert Run and preview agree on the header.

---

### M7. Sealing after a corrupt middle index line creates unverifiable records

**Where**

- `src/trigger_designer/core/audit/store.py:154-191` (`_read_index`)
- `:529-545` (`_seal`)
- `:623` (`list_runs` uses `_read_index(...).entries`)
- `:264-276` (`verify_store` stops at the corrupt line)

**Symptom**

`_read_index` keeps parsing after an unparsable middle line and appends later
entries to `entries`. `_seal` then chains a new record from
`index.entries[-1]`, which may be after the corrupt line. `verify_store` ignores
everything after the corrupt line, so the new records are never verified, and
`list_runs` shows them as if the store were healthy.

Reproduced conceptually with a store whose `index.jsonl` line 2 is corrupt:

1. Seal run 3.
2. `verify_store` reports `index_corrupt` and checks only run 1.
3. `list_runs` returns runs 1 and 3 (run 2 is missing) as if valid.

**Suggested fix**

- Refuse to seal when `index.corrupt_line is not None`; raise a store error
  telling the user to run verification/repair. Do not append past corruption.
- Make `list_runs` stop at the corrupt line (or mark the returned headers as
  unverified) so the UI and verify agree.
- Keep the existing truncated-tail repair, which is safe.

**Tests**

- A corrupt middle line prevents a new seal.
- `list_runs` does not return records after the corrupt line.
- Truncated last line still repairs and seals as today.

---

### M8. Ranking by a non-numeric text column silently selects nothing

**Where**

- `src/trigger_designer/core/shaping/select_records.py:62-70`
- Uses `numeric_expr`, whose `strict=False` turns unreadable text into null

**Symptom**

`largest_n` / `smallest_n` on a String column that contains no numbers produces
an all-null `__key`; `rank(...)` is null; `fill_null(False)` drops every row.
The selected output is empty and the rest output contains everything, with no
error or warning.

**Suggested fix**

Validate before ranking:

- count non-null parsed values in a cheap pass (or check the column dtype);
- if zero, raise `TD-SHAPE-091` ("The column must be a number") or fall back to
  lexical ranking deliberately;
- the dock should say which mode it uses.

**Tests**

- `largest_n` on `["a","b"]` raises or ranks lexically, never silently empty.
- Mixed numeric text and identifiers follows H1's parser policy.
- A normal numeric column is unchanged.

---

### M9. Pivot numeric aggregation over non-numeric text yields silent nulls

**Where**

- `src/trigger_designer/core/shaping/reshape.py:72-82`
- `_agg_expr` at `:39-50`

**Symptom**

For a text value column containing `["abc", "def"]`, choosing Sum produces
pivot columns of all nulls (`{'x': [None], 'y': [None]}`), because
`numeric_expr` makes every value null and `sum` of all-null is null.

This is close to the documented behaviour ("text that is not a number is
ignored", "a Sum of cells that are all empty is empty"), so treat it as a
warning/UX issue rather than a correctness bug: the user gets no signal that
nothing was aggregated.

**Suggested fix**

Add a dock warning when the selected value column has no readable numeric
values (or when the result is all null), and mention the parser policy in the
node docs. If H1 changes `numeric_expr`, this resolves for decimal-comma input.

**Tests**

- All-text value column shows a warning chip or raises a clear config error.
- Mixed numeric/text still sums the numeric values.

---

### M10. Cleansing change statistics overstate changes

**Where**

- `src/trigger_designer/core/utils/cleansing_util.py:241`
  (`whitespace_changes += len(self.df)`)
- `:284` (`character_removals += len(self.df)`)
- `:319` (`case_changes += len(self.df)`)

**Symptom**

The counters increment by the whole frame length for every string column,
whether or not a value changed. For example, `strip_whitespace()` on
`["abc", "def"]` reports `whitespace_changes=2`.

`get_stats()` is not currently used by the UI (only the module and tests), so
this does not corrupt a displayed number today, but the values are wrong for
tests, logs or future reporting.

**Suggested fix**

Count actual differences (compare original and transformed columns) or remove
the unused statistics. If kept, do it with one vectorized comparison per
column, not a Python loop.

**Tests**

- No-change input reports 0.
- One changed cell reports 1.
- Multiple columns sum correctly.

---

## P2 - Low

### L1. Mutable default arguments in Qt node APIs

**Where**

- `src/trigger_designer/qt/node_base.py:79-82` (`inputs=[2,2]`,
  `outputs=[1]`, `input_text=[]`, `output_text=[]`)
- `src/trigger_designer/qt/node_base.py:270-271` (`hashmap: dict = {}`)
- Also: `qt/widgets/nodes/unknown.py:49,96`,
  `qt/widgets/nodes/Preparation/select.py:737`,
  `qt/helpers/shaping_support.py:1090`,
  `qt/widgets/nodes/InOut/file_output.py:313`,
  `qt/widgets/nodes/Report/graph.py:506`,
  `qt/widgets/nodes/Report/data_profile.py:310`,
  `qt/widgets/nodes/Audit/_base.py:848`,
  `qt/widgets/nodes/Join/union.py:817`,
  `qt/widgets/nodes/InOut/file_input.py:1854-1857`

**Symptom**

`Node.deserialize` writes socket ids into the supplied `hashmap`. A caller that
omits it writes into the shared default dict, so ids from one document can leak
into the next. The default socket lists are overwritten by the base
`Node.__init__`, so they are mostly a style/latent issue.

**Suggested fix**

Use `None` defaults and create the list/dict inside the function:

```python
def __init__(self, ..., inputs=None, outputs=None, input_text=None, output_text=None):
    inputs = [2, 2] if inputs is None else inputs
    ...
def deserialize(self, data, hashmap=None, ...):
    hashmap = {} if hashmap is None else hashmap
```

**Tests**

- Two independent `deserialize` calls with no hashmap do not share ids.
- Default socket counts are unchanged.

---

### L2. Uncommitted executor `after_node` try/except is dead code

**Where**

- `src/trigger_designer/core/ExecutionCheck/executor.py:366-377`
- `_call_hook` swallows every `Exception` at `:200-207`

**Symptom**

The working tree wraps `self._call_hook(...)` plus the variable merge in
`try/except`, logs "after_node hook failed", and then `raise`s. Since
`_call_hook` already catches all exceptions, the `except` never runs. If
`_call_hook` is ever changed to propagate, this code would fail a run from an
observer, contradicting the documented contract ("observers must never fail a
run"). The log also mislabels a failure in the merge/update as a hook failure.

**Suggested fix**

Revert the wrapper, or keep only the merge/update in a guarded block and do not
`raise` from an observer failure. Keep the existing
`test_recorder_bug_in_hook_does_not_change_the_run` test as the contract.

**Tests**

- Existing hook tests pass.
- Add one test that a broken `after_node` still leaves the run successful and
  the original variables intact.

---

### L3. Theme refresh emits an index beyond the current page

**Where**

- `src/trigger_designer/qt/models/polars_table_viewer.py:262-270`

**Symptom**

`refresh_theme` emits `top = index(0,0)` to
`bottom = index(self._total_rows - 1, columnCount - 1)`, but `rowCount()` is
only the current page. `bottom` is therefore outside the model rows when the
frame has more than one page.

**Suggested fix**

Use `bottom = self.index(self.rowCount() - 1, self.columnCount() - 1)` and
return early when `rowCount() == 0`.

**Tests**

- Theme change on a multi-page frame does not emit out-of-range indexes.
- Empty frame does not emit.

---

### L4. Chunk cache never evicts when `cache_size < chunk_size`

**Where**

- `src/trigger_designer/qt/models/polars_table_viewer.py:316-334`

**Symptom**

`max_entries = self.cache_size // self.chunk_size` is 0 when the cache is
smaller than one chunk. Then `sorted_entries[:-entries_to_keep]` becomes
`sorted_entries[:0]`, so nothing is removed and the cache grows without bound.

The default viewer uses `chunk_size=1000, cache_size=10000`, so this needs a
non-default host or configuration.

**Suggested fix**

Use `max(1, self.cache_size // self.chunk_size)` and ensure at least one entry
is kept/evicted deterministically.

**Tests**

- Construct a model with `chunk_size=1000, cache_size=500`, load several
  chunks, assert the cache stays at its bound.

---

### L5. Export ignores the current sort order

**Where**

- `src/trigger_designer/qt/models/polars_table_viewer.py:1174-1215`

**Symptom**

`export_csv` / `export_excel` use `self.filtered_dataframe` (the unsorted
source of the filter) instead of the model's current frame. After the user
clicks a header to sort, the view is sorted but the exported file is not.

**Suggested fix**

Export `self.model._dataframe` when it is the authoritative current view, or
document that export is always in source order. Prefer a small public accessor
(`model.current_frame()`) rather than reaching into the private field.

**Tests**

- Sort, export, read back, assert row order matches the view.
- Filter + sort export still contains only filtered rows.

---

### L6. Empty strings become blank cells in Excel exports

**Where**

- `src/trigger_designer/core/excel/cells.py:226-243` (`write_text`)
- `:246-283` (`write_value`)

**Symptom**

`write_text` turns `""` into `ws.write_blank(...)`, so a CSV value that was an
empty string comes back as null/blank from Excel. This is usually harmless, but
it is a fidelity change for a column an auditor may use to distinguish
"empty" from "not provided".

**Suggested fix**

Decide and document the contract. If empty must survive, write it with
`write_string(row, col, "", format)`; if blank is intentional, add a test and a
doc note.

**Tests**

- Empty string round trip through `write_frame_xlsx` if the contract is
  "preserve empty".
- Null remains blank.

---

## Confirmed intentional behaviour (do not "fix")

These were checked and are documented or deliberate. Leave them alone unless
the product decision changes:

1. **Aggregate duplicate fields.** A later action for the same field overwrites
   the earlier one while keeping the first position. Documented in
   `plans/nodes/08-aggregate.md`.
2. **Rows string mode.** String generation stops at 10,000 and ignores
   `max_value`; documented in `plans/nodes/14-rows.md`.
3. **Pivot text-as-numbers.** Commas are removed and non-numeric text is
   ignored; documented in `docs/nodes/transform/pivot.md:66-68`. See H1/M9 for
   the safety concern, but the current rule is explicit.
4. **Split percentages.** The cut is `row_index < max(row_index) * percent`, a
   formula the saved golden pins; small frames are intentionally approximate.
5. **Reconcile near matching.** Tolerant groups may chain through neighbours;
   documented in the Duplicates module docstring.
6. **Start row.** Excel-only and hidden for other file types.
7. **Record limit.** Applied after the union (`input_source.py:835-836`), not
   per file.
8. **PEP 758 `except A, B:`.** Valid Python 3.14 syntax used throughout; not a
   bug.
9. **Nested JSON stringification.** `_stringify_nested` correctly handles
   quotes, backslashes, newlines and lists; verified by probe.
10. **Undo index semantics.** `QUndoStack.index()` is a count of applied
    commands; `UndoController`'s accessors are correct.
11. **Reconcile null keys.** Polars does not match null join keys, so null keys
    stay unmatched, which is the desired accounting behaviour.

## Verified safe in focused probes

- Risk Filters holiday and weekend detection.
- Benford empty drill set and digit extraction.
- Gaps out-of-order, range and zero-padded prefixes.
- Table paging boundaries and absolute row headers.
- `Window` partition `row_number` and `Select` `dtype_matches` for Datetime,
  Date and Categorical.
- The shared `amounts.amount_expr` parser on US, European, currency, negative
  and parenthesised amounts.
- Excel `start_row` + header combinations through `build_source`.
- Undo controller traversal at the bottom, tip and redo tail.

## Areas reviewed with no confirmed defect

Core profile engine, audit recorder lifecycle and row counting, audit store
verification (apart from M7), Excel cell writing and workpaper top-level writer,
input file listing and schema reconciliation, CLI schedule path handling,
headless runner/plan basics, and the Config Dock undo bindings.

These still deserve a second pass if time allows:

- Workpaper Summary/Exceptions sheet layout against real workbooks.
- CLI `schedule add` XML and Windows Task Scheduler round trip.
- Headless cancellation and timeout paths under a real long-running node.
- Large-file streaming in Pivot, Reconcile and Fuzzy Match.

## Suggested order

1. **H4** first: make the suite green, so later changes have a clean baseline.
2. **H1** and **H2**: data-correctness fixes, with table-driven tests.
3. **H3**, **M1**, **M2**: user-visible output and preview correctness.
4. **M3-M8**: smaller correctness and UX fixes.
5. **M9-M10**, **L1-L6**: cleanup and hardening.

Do not batch all of these into one commit. Keep the data-parsing changes
(H1, H2, M8) separate from the Qt model/UI changes (M1, M2, L3-L5) and from
the audit-store change (M7), so each can be reviewed and reverted alone.

## Verification

Focused during development:

```powershell
uv run --project . pytest tests/unit/test_cleansing_core.py -q
uv run --project . pytest tests/unit/test_profile_core.py -q
uv run --project . pytest tests/unit/test_shaping_core.py -q
uv run --project . pytest tests/unit/test_audit_store.py -q
uv run --project . pytest tests/unit/test_docs_present.py tests/unit/test_workpaper_output_icon.py -q
```

Before finishing a change:

```powershell
uv run --project . ruff format <changed files>
uv run --project . ruff check <changed files>
uv run --project . pytest tests/unit -q
```

The full unit suite takes about 21 minutes on this machine, so use the focused
sets while iterating and run the full suite once before declaring the work
done.

For the Qt model fixes, an offscreen smoke test is enough for CI:

```powershell
$env:QT_QPA_PLATFORM="offscreen"
uv run --project . python -c "from qtpy.QtWidgets import QApplication; app=QApplication([]); ..."
```

## Notes for the implementer

- This plan lives in `docs/plans/` in the repository; source files were not
  modified during the hunt.
- The working tree already has uncommitted changes in `executor.py`,
  `tests/unit/test_executor_hooks.py`, `ToDo.md`, `check_output.py`, and the
  untracked `savedfiles/Example_3_AE_Winter_Watch/` and
  `tests/e2e/test_ae_winter_watch.py`. Do not revert them blindly; review L2
  against that diff first.
- When a behaviour is documented (for example pivot comma removal), change the
  document and the code together, and add a test that names the rule.
