# Building the workflow by hand — 1:1 with `step2_reference_pipeline.py`

A node-by-node recipe for reproducing the pandas script inside
TriggerDesigner. Every script stage has a row below saying which node to drop,
what to set in the Config Dock, and which socket to wire where. Build it top
to bottom; stages are ordered the way data flows.

Read [Differences to expect](#differences-to-expect) before you start — a
handful of node behaviours will otherwise surprise you, and two of them are
genuine findings about the app, not about your wiring.

Script-to-node map first, so you always know where you are:

| Script (`step2_reference_pipeline.py`) | Nodes |
|---|---|
| `load_raw` — read 6 CSVs as text | 6 × File Input |
| `normalise_columns` + key/dtype casts | 6 × Select (rename + dtype map) |
| text strip/lower (`ORDER_TEXT_FIELDS`), fx currency lower | 2 × Cleansing |
| drop null `order_id/customer_id/product_id` | 1 × Cleansing (remove null rows, selected fields) |
| quantity gate 1–500, price gate 0–5000, year ≤ 2025 | 5 × Filter + 1 × Formula (`YEAR`) + 2 × Append (reject streams) |
| `drop_duplicates(order_id, keep=first)` | 1 × Unique (`U` forward, `D` to file) |
| 5 × `merge(how=left)` | 5 × Join (take **J**; orphans off **L**) |
| money/margin/date/bulk/band/risk/status columns | 1 × Formula (19 sections) |
| `orders_enriched.csv` column subset | 1 × Select (36 columns) |
| enterprise / high-risk slices, 80/20 split | 2 × Filter, 1 × Split |
| 6 groupbys + sorts, cumsum, melt, threshold top-N | 7 × GroupBy, 7 × Sort, 1 × Running Total, 1 × Transpose, 2 × Select (renames), 1 × Formula (rev/lead-day) |
| `pd.concat` of 5 dimensions | 5 × Formula (`source_table` tag) + 4 × Append |
| `kpi_summary`, `data_quality_report`, `scenario_grid` | script-only — no node equivalent |

---

## Before you start

### Point every File Output at `app_output/`

`step3_compare.py` diffs `app_output/` against `reference_output/`.

> **On Windows, type the path with forward slashes.**
>
> `File Output` builds its success message by interpolating the path into a
> single-quoted f-string without `!r`
> (`src/trigger_designer/qt/widgets/nodes/InOut/file_output.py:339`). A
> backslash path therefore reaches the generated program as literal text, and
> `exec()` then parses `\U`, `\t`, `\n` … as escape sequences:
>
> ```
> print(f'[SUCCESS] Successfully saved data to C:\Users\...\out.csv using LazyFrame')
>                                                        ^^^^ truncated \U escape
> SyntaxError: (unicode error) 'unicodeescape' codec can't decode bytes
> ```
>
> The `sink_csv` call itself is fine — the file gets written. It is the success
> `print` that breaks the generated program, so the whole run aborts at the
> first output node. Forward slashes avoid it entirely, and Polars accepts them
> on Windows. `File Input` is unaffected; it uses `!r`.

### Use the `demo` scale while you are wiring

```bash
python step1_generate_data.py --scale demo   # 40,800 orders, ~4 MB
```

Switch to `standard` / `large` / `xlarge` once the graph runs clean.

---

## Stage 1 — Read the six sources (6 × File Input)

Script: `load_raw` reads every CSV with `dtype=str` — everything arrives as
text. The app's CSV reader does the same (`infer_schema=False`), so the two
start from the identical premise.

| Node | File | Columns |
|---|---|---|
| File Input | `data/orders.csv` | 15, messy headers |
| File Input | `data/customers.csv` | 10, includes `region` |
| File Input | `data/products.csv` | 9 |
| File Input | `data/suppliers.csv` | 5 |
| File Input | `data/channels.csv` | 4 |
| File Input | `data/fx_rates.csv` | 3 |

Leave `Record Limit` at 0. Confirm each preview loads.

---

## Stage 2 — Rename headers and set types (6 × Select)

Script: `normalise_columns` (strip/lower/underscore every header) plus explicit
`pd.to_numeric` casts for keys, money and score columns. In the app this is one
Select node per file: tick every column, type the rename, pick the dtype.

### `Select: orders`

| Original header | Rename to | Type |
|---|---|---|
| ` Order ID ` | `order_id` | String |
| `Customer_Id` | `customer_id` | Int64 |
| `PRODUCT_ID` | `product_id` | Int64 |
| `supplier id` | `supplier_id` | Int64 |
| `Channel ID` | `channel_id` | Int64 |
| `Currency` | `currency` | String |
| `Order TS` | `order_ts` | **Datetime** |
| `Quantity` | `quantity` | Int64 |
| `unit_price_local` | `unit_price_local` | Float64 |
| `Discount Pct` | `discount_pct` | Float64 |
| `tax_local` | `tax_local` | Float64 |
| `shipping_local` | `shipping_local` | Float64 |
| `Status` | `status` | String |
| `Payment Method` | `payment_method` | String |
| `is_returned` | `is_returned` | String (see below — **not** Boolean) |

`order_ts` → Datetime matters: the Select node tries day-first formats
(`%d-%m-%Y …`) before month-first ones, which is exactly where the script and
the workflow diverge on purpose (difference 4).

> **Do not map `is_returned` (or anything) to Boolean.** Polars cannot cast
> `String → Boolean` at all — the cast raises `InvalidOperationError` even
> with `strict=False`, so the node errors. The script's `eq("true")`
> conversion is reproduced in Stage 8 with a `CASE WHEN` instead (section 1).

### `Select: customers`

Rename to match the script's `enrich` preamble exactly — the script renames
these five to dodge `currency_x/currency_y` collisions, so the workflow must
use the same names or the joins produce different schemas:

| Original | Rename to | Type |
|---|---|---|
| `customer_id` | `customer_id` | Int64 |
| `email` | `customer_email` | String |
| `full_name` | `customer_name` | String |
| `signup_date` | `signup_date` | String (script never parses it) |
| `country` | `customer_country` | String |
| `region` | `region` | String |
| `currency` | `customer_currency` | String |
| `segment` | `segment` | String |
| `age_band` | `customer_age_band` | String |
| `loyalty_tier` | `loyalty_tier` | String |

Pre-renaming `currency` → `customer_currency` has a second payoff: it removes
the only column collision in the whole join chain (Stage 7), so the Join node
never needs its `_right` suffixing.

### `Select: products`

`product_id`→Int64, `unit_price`→Float64, `unit_cost`→Float64. Everything else
keeps its name as String — including `launch_date` (the script never parses
it, so neither do you).

### `Select: suppliers`

`supplier_id`→Int64, `lead_time_days`→Int64, `reliability_score`→Float64.
**Keep `country` as `country`** — the script only renames the *customer*
country. The supplier report groups by this exact name.

### `Select: channels`

`channel_id`→Int64. Keep `channel_name`, `channel_group`, `is_digital` as
String (`is_digital` stays the text `"true"`/`"false"`, exactly as in the
script, which never converts it).

### `Select: fx_rates`

`usd_rate`→Float64. Keep `currency`, `currency_name` as String.

---

## Stage 3 — Text hygiene (2 × Cleansing)

Script (`clean_orders` stage 03): strip, lowercase and collapse inner whitespace
on `order_id, currency, status, payment_method`. Script (`main`): strip +
lowercase on `fx.currency`. That is *all* the text cleaning the script does —
dimensions are never touched (the generator writes them clean), so dimension
Cleansing nodes would only *create* mismatches (e.g. lowercasing `segment`
turns `"Enterprise"` into `"enterprise"` and breaks every segment key).

| Node | Fields | Strip | Normalize spaces | Case |
|---|---|---|---|---|
| Cleansing: orders | `order_id`, `currency`, `status`, `payment_method` | on | on | Lower Case |
| Cleansing: fx | `currency` | on | off | Lower Case |

The Cleansing node applies `strip_chars()` + `\s+ → " "` + `to_lowercase()` on
exactly the selected fields — the same three operations as the script's
`str.strip().str.lower()` + `str.replace(r"\s+", " ")`.

> The `fx` node is not optional. `fx_rates.csv` stores codes (`USD`, `EUR`…)
> in upper case while the order side is now lower case. Skip it and **every**
> FX join misses: `usd_rate` is null, `net_revenue_usd` is null, every revenue
> figure is zero.

---

## Stage 4 — Drop unreconcilable rows (1 × Cleansing)

Script: drop rows where `order_id`, `customer_id` or `product_id` is null (stage
04). Wire it **after** `Cleansing: orders`, mirroring the script (text first,
gates after — the Cleansing node also runs null-removal before
whitespace/case internally, but the two stages are separate nodes here so the
order is explicit).

- Fields: `order_id`, `customer_id`, `product_id`
- Tick **Remove Null Rows From Selected Columns**, nothing else.

This is `remove_rows_with_nulls`: drop a row if *any* of the three is null —
the same predicate as the script's `isna() | isna() | isna()`.

---

## Stage 5 — Business gates (5 × Filter + 1 × Formula + 2 × Append)

Script: `quantity.between(1, 500)`, `0 < unit_price_local ≤ 5000`,
`order_ts.year ≤ 2025`. A Filter node holds **one** condition with two sockets
(**T** continues, **F** is the reject stream), so each two-sided rule is two
nodes whose **F** streams are concatenated with an Append — the same shape the
script's `rejected_*` exports have.

| # | Node | Column | Operation | Value | T → | F → |
|---|---|---|---|---|---|---|
| 1 | Filter: qty ≥ 1 | `quantity` | Greater Than or Equal | `1` | node 2 | Append: rejected qty (in 1) |
| 2 | Filter: qty ≤ 500 | `quantity` | Less Than or Equal | `500` | node 3 | Append: rejected qty (in 2) |
| 3 | Filter: price > 0 | `unit_price_local` | Greater Than | `0` | node 4 | Append: rejected price (in 1) |
| 4 | Filter: price ≤ 5000 | `unit_price_local` | Less Than or Equal | `5000` | Formula: year | Append: rejected price (in 2) |
| 5 | Filter: year ≤ 2025 | `order_year` | Less Than or Equal | `2025` | Unique | File Output `rejected_future_dates.csv` |

Append nodes: How = `diagonal_relaxed` (union of columns, gaps nulled — the
equivalent of the script keeping both tails in one frame).

- Append: rejected qty → File Output `rejected_quantity.csv`
- Append: rejected price → File Output `rejected_price_outliers.csv`

(The `qty ≤ 500` gate never fires at demo scale — quantities top out at 11 —
but the contract is `between(1, 500)`, so wire it anyway.)

### `Formula: add order_year` (before gate 5)

One section: target `order_year`, formula `YEAR([order_ts])`, dtype Integer.
Formula rules that apply everywhere in this guide:

- Reference columns in **[square brackets]**: `[net_local]`, not `"net_local"`.
- String literals in **single quotes**.
- Overwriting an existing column is fine — the node emits
  `SELECT * REPLACE (…)` and keeps the column in place.

Null timestamps (`""` → null) produce a null year, and a null comparison keeps
the row out of **both** T and F — the script puts those rows in
`rejected_future_dates.csv` instead. Tiny, documented, unavoidable (difference
7).

---

## Stage 6 — Deduplicate (1 × Unique)

Script: capture `duplicated(order_id, keep=False)`, then
`drop_duplicates(order_id, keep="first")`.

**Unique** — selected columns: `order_id`.

- **U** socket → forward (first occurrence kept, `maintain_order=True` —
  exactly `keep="first"`)
- **D** socket → File Output `duplicate_orders.csv` (all rows of duplicate
  groups via `is_duplicated()` — exactly `keep=False`)

Optionally tee **U** into **Count Records** → File Output
`kpi_fact_rowcount.csv` (single-column `Count` file; the script has no
equivalent — it is listed under workflow-only outputs).

---

## Stage 7 — Enrich (5 × Join)

Script: five `merge(how="left")`. Chain five Join nodes on the Unique **U**
output. Left input takes the running fact, right input the dimension.

| # | Node | Left key → Right key | Right input |
|---|---|---|---|
| 1 | Join: customers | `customer_id` → `customer_id` | Select: customers |
| 2 | Join: products | `product_id` → `product_id` | Select: products |
| 3 | Join: suppliers | `supplier_id` → `supplier_id` | Select: suppliers |
| 4 | Join: channels | `channel_id` → `channel_id` | Select: channels |
| 5 | Join: fx | `currency` → `currency` | Cleansing: fx |

Leave join type and output columns untouched. Take the **J** (middle) socket
forward each time.

- Join 1 **L** socket → File Output `orphan_customers.csv`
- Join 2 **L** socket → File Output `orphan_products.csv`

> **Orphans come off L, not R.** The Join node runs one full outer join and
> splits it into three sockets: **L** = left-only rows, **J** = matched rows,
> **R** = right-only rows (`join.py:899-949`). The script's orphans are *order*
> rows whose foreign key missed — left-only rows — so they are the **L**
> socket. The **R** socket is the opposite population: dimension rows nobody
> ordered (customers who never bought anything). Same file name, opposite
> meaning — wire the wrong socket and the row counts match by coincidence
> while the contents are completely different.
>
> The **L** exports carry only the left-side columns at that point (no
> customer/product fields yet), while the script's orphan files are full
> enriched rows — same population, narrower schema. The comparator reports the
> column gap; that is expected.

> **The Join node always does a full outer join.** `join_type` is not read by
> the code generator (`join.py:838-845`: `how="full"` hardcoded); the
> three-socket split is where the join type effectively lives. A pandas
> `how="left"` is J + L, so taking J alone drops the unmatched order rows the
> script keeps — ~1% of rows at demo scale. That is the single largest
> structural difference between the two versions (difference 1).

Because Stage 2 pre-renamed the customer currency, no column exists on both
sides of any join except the keys — the node's `_right` conflict renaming
never triggers, and J schemas match the script's merged frames column for
column.

---

## Stage 8 — Derived measures (1 × Formula)

Script: `enrich` computes local money → USD money → margin → calendar →
bulk/band → risk → a single rounding pass. Add these sections **in order**;
each may reference columns added above it.

| # | Target column | Formula | Type |
|---|---|---|---|
| 1 | `is_returned` | `CASE WHEN LOWER([is_returned]) = 'true' THEN true ELSE false END` | Boolean |
| 2 | `gross_local` | `ROUND([quantity] * [unit_price_local], 2)` | Float |
| 3 | `discount_local` | `ROUND([gross_local] * [discount_pct], 2)` | Float |
| 4 | `net_local` | `ROUND([gross_local] - [discount_local], 2)` | Float |
| 5 | `total_local` | `ROUND([net_local] + [tax_local] + [shipping_local], 2)` | Float |
| 6 | `unit_price_usd` | `ROUND([unit_price_local] * [usd_rate], 2)` | Float |
| 7 | `net_revenue_usd` | `ROUND([net_local] * [usd_rate], 2)` | Float |
| 8 | `tax_usd` | `ROUND([tax_local] * [usd_rate], 2)` | Float |
| 9 | `shipping_usd` | `ROUND([shipping_local] * [usd_rate], 2)` | Float |
| 10 | `total_usd` | `ROUND([total_local] * [usd_rate], 2)` | Float |
| 11 | `cogs_usd` | `ROUND([quantity] * [unit_cost], 2)` | Float |
| 12 | `gross_margin_usd` | `ROUND([net_revenue_usd] - [cogs_usd], 2)` | Float |
| 13 | `margin_pct` | `ROUND(CASE WHEN [net_revenue_usd] = 0 THEN NULL ELSE [gross_margin_usd] / [net_revenue_usd] END, 4)` | Float |
| 14 | `order_month` | `MONTH([order_ts])` | Integer |
| 15 | `order_year_month` | `STRFTIME([order_ts], '%Y-%m')` | String |
| 16 | `is_bulk` | `CASE WHEN [quantity] >= 6 THEN true ELSE false END` | Boolean |
| 17 | `value_band` | `CASE WHEN [net_revenue_usd] > 1000 THEN 'High' WHEN [net_revenue_usd] > 250 THEN 'Medium' ELSE 'Low' END` | String |
| 18 | `risk_score` | see below | Integer |
| 19 | `risk_band` | `CASE WHEN [risk_score] >= 4 THEN 'High' WHEN [risk_score] >= 2 THEN 'Medium' ELSE 'Low' END` | String |
| 20 | `status_clean` | see below | String |

Section 1 overwrites the String column with real booleans (the `REPLACE`
path) — it must come first because `risk_score` tests it as a boolean.
`order_year` already exists from Stage 5, so it is **not** repeated here.

`risk_score` (nulls score 0 via `ELSE`, matching the script's
`fillna(False)`; missing segment scores 2 via `IS NULL`, matching
`segment.isna()`):

```sql
(CASE WHEN [is_returned] THEN 2 ELSE 0 END)
+ (CASE WHEN [status] IN ('refunded', 'cancelled') THEN 2 ELSE 0 END)
+ (CASE WHEN [net_revenue_usd] > 2000 THEN 1 ELSE 0 END)
+ (CASE WHEN [margin_pct] < 0.10 THEN 1 ELSE 0 END)
+ (CASE WHEN [segment] IS NULL THEN 2 ELSE 0 END)
```

`status_clean` (the script's `status.str.title()` spelled out):

```sql
CASE [status] WHEN 'paid' THEN 'Paid'
  WHEN 'pending' THEN 'Pending'
  WHEN 'refunded' THEN 'Refunded'
  WHEN 'cancelled' THEN 'Cancelled'
  WHEN 'partially refunded' THEN 'Partially Refunded'
  ELSE [status] END
```

Notes:

- `value_band` uses strict `>` because the script's `pd.cut` bins are
  right-closed: 250 → Low, 1000 → Medium. `>=` would promote both boundary
  values one band up.
- `ROUND(…, 2)` on every money column mirrors the script's single rounding
  pass. Both sides round, but at different points (per-section vs once at the
  end), so expect sub-cent drift — see difference 8.
- `cogs_usd` is `quantity × unit_cost` with **no** `usd_rate`: `unit_cost`
  comes from the product catalogue, which is already priced in USD.

> ### Exercise: the double-conversion bug
>
> Change section 11 to `ROUND([quantity] * [unit_cost] * [usd_rate], 2)` and
> re-run. For USD rows (`usd_rate = 1.0`) nothing changes; for every other
> currency `cogs_usd` collapses toward zero and `margin_pct` inflates — median
> 0.33 becomes ~0.84. This exact bug lived in the reference script during
> development (it looked fine on USD rows, which is why nobody noticed), and
> it is the clearest demonstration in this example of a difference that is a
> real bug rather than a node-semantics quirk. Change it back afterwards.

---

## Stage 8b — The enriched export (1 × Select)

Script: `orders_enriched.csv` is a 36-column subset in a fixed order. The
Formula output carries ~60 columns, so trim it with a Select: tick exactly
these (column *order* does not matter for the comparison, only membership):

`order_id`, `order_ts`, `order_year`, `order_month`, `order_year_month`,
`customer_id`, `product_id`, `supplier_id`, `channel_id`, `channel_name`,
`channel_group`, `category`, `subcategory`, `brand`, `customer_country`,
`region`, `segment`, `loyalty_tier`, `currency`, `usd_rate`, `status`,
`status_clean`, `quantity`, `unit_price_local`, `discount_pct`, `net_local`,
`total_local`, `net_revenue_usd`, `cogs_usd`, `gross_margin_usd`,
`margin_pct`, `value_band`, `risk_score`, `risk_band`, `is_returned`,
`is_bulk`

→ File Output `orders_enriched.csv` (+ optional second File Output as Parquet
`orders_enriched.parquet` to show the writer's range).

Everything downstream of this point wires from the **Formula** output (full
width), not from this Select — the script slices and aggregates from the full
enriched frame too.

---

## Stage 9 — Row-level slices (2 × Filter + 1 × Split)

All three wire from the Stage 8 Formula output.

| Node | Config | Output |
|---|---|---|
| Filter: enterprise | `segment` Equals `Enterprise` → **T** | `orders_enterprise.csv` |
| Filter: high risk | `risk_band` Equals `High` → **T** | `orders_high_risk.csv` |
| Split | Estimation 80%, Random Split on, seed 42 | **E** → `fact_estimation.csv`, **V** → `fact_validation.csv` |

Case matters: values were never lowercased on the dimension side, so the
enterprise filter is capital-`Enterprise`, exactly as in the script.

The Split node shuffles with Polars (`seed=42`); the script shuffles with
pandas (`random_state=42`). Different algorithms, so the 80/20 **counts**
agree (27,761 / 6,941 at demo scale) while the **membership** differs. The
comparator reports this honestly as key-set overlap below 100%.

---

## Stage 10 — Reports (7 × GroupBy + 7 × Sort + extras)

Function names are the **lowercase** polars names (`sum`, `n_unique`,
`first`), not the dropdown labels. Every rollup uses:

| Field | Function | Alias |
|---|---|---|
| `net_revenue_usd` | sum | `revenue_usd` |
| `gross_margin_usd` | sum | `margin_usd` |
| `order_id` | n_unique | `orders` |

(`count` in the node means `pl.len()` — rows, not distinct values. The script
counts distinct `order_id`s, so the correct function here is `n_unique`.)

| Report | Group by | Sort | Output |
|---|---|---|---|
| Monthly | `order_year_month` | `order_year_month` Ascending | `monthly_revenue.csv` (via Running Total + rename below) |
| Category | `category` | `revenue_usd` Descending | `category_revenue.csv` |
| Region × channel | `region`, `channel_group` | both Ascending | `region_channel_revenue.csv` |
| Segment × risk | `segment`, `risk_band` | both Ascending | `segment_revenue.csv` |
| Suppliers | `supplier_id` (+ `first`: `supplier_name`, `country`, `lead_time_days`, `reliability_score`) | `revenue_usd` Descending | `supplier_performance.csv` (via rev/lead-day Formula below) |
| Currency | `currency` (+ `first`: `usd_rate`) | `revenue_usd` Descending | `fx_exposure.csv` |
| Top customers | `customer_id` → `sum(net_revenue_usd)` as `revenue_usd`, `n_unique(order_id)` as `orders` | see below | `top_customers.csv` |

Details:

- **Monthly.** Group by `order_year_month` *only* (the script never groups by
  year). Sort ascending, then **Running Total** with sum column `revenue_usd`
  and **no group-by columns** — an empty group list is a plain global
  `cum_sum()`, exactly the script's `cumsum()`. The node names the column
  `RunTot_revenue_usd`, so follow with a **Select** renaming it to
  `cumulative_revenue_usd` → File Output `monthly_revenue.csv`. Column order
  then matches the script exactly.
- **Transpose** the monthly rollup (wire from the renamed Select): key
  `order_year_month`, data `revenue_usd`, `margin_usd`, `orders`, missing
  action warn → the node emits `Name`/`Value` columns, so follow with a
  **Select** renaming `Name`→`metric`, `Value`→`value` → File Output
  `monthly_revenue_long.csv`. (Polars `unpivot` ≡ pandas `melt`.)
- **Suppliers.** After the Sort, add a **Formula** with one section:
  `ROUND([revenue_usd] / [lead_time_days], 4)` as `revenue_per_lead_day`
  (Float) → File Output. Note the group column is `country` — the suppliers
  table was deliberately *not* renamed in Stage 2.
- **Top customers.** There is **no limit / top-N node**, so "top" is a revenue
  threshold — the same contract both sides share
  (`cfg.TOP_CUSTOMER_REVENUE_THRESHOLD`, 4000): GroupBy → Filter
  `revenue_usd` Greater Than `4000` (T) → Sort `revenue_usd` Descending →
  File Output.
- **Graphs (optional).** A Graph node on the monthly/category rollups (`bar`,
  x = `order_year_month`/`category`, y = `revenue_usd`) opens a matplotlib
  window — it does **not** write a file. The script's PNGs have no workflow
  equivalent.

---

## Stage 11 — Dimension union (5 × Formula + 4 × Append)

Script: `pd.concat` of the five normalised dimensions, each tagged with
`source_table`. `pd.concat` outer-aligns the columns and nulls the gaps —
exactly the Append node's `diagonal_relaxed` mode.

1. On each Stage 2 Select output, add a one-section **Formula** tagging the
   source: target `source_table`, formula `'customers'` (resp. `'products'`,
   `'suppliers'`, `'channels'`, `'fx_rates'`), dtype String. (The fx branch
   wires from `Cleansing: fx`, matching the script's lowercased fx frame.)
2. Chain four **Append** nodes (`diagonal_relaxed`) in script concat order —
   customers ┬ products → ┬ suppliers → ┬ channels → ┬ fx — → File Output
   `reference_data_union.csv`.

---

## Stage 12 — Compare

```bash
python step3_compare.py
```

Row counts and deltas per file, key-set overlap on each natural key,
column gaps in either direction, and per-column value drift with the worst
absolute delta (float tolerance default `1e-6`, override with `--tolerance`).
Files only one side produced are listed with the reason. When both sides carry
the same key set, rows are sorted by key before comparison so output *order*
never masquerades as a value difference; when key sets differ it says so
instead of printing false mismatches.

---

## What has no app equivalent (script-only outputs)

| File | Why |
|---|---|
| `kpi_summary.csv` | Assembled cell-by-cell in Python (9 metric/value rows). No metric-table node exists. `Count Records` covers only the row count, as `kpi_fact_rowcount.csv`. |
| `data_quality_report.csv` | The script's own stage log, not a data report. |
| `scenario_grid.csv` | A labelled cross-product (`Base/Upside/Downside × 2024/2025`). Generate Rows emits a bare integer counter — and with an input wired it concatenates horizontally instead — so it cannot build this grid. |

---

## Differences to expect

| # | Difference | Effect |
|---|---|---|
| 1 | **Join is always a full outer join** (`join.py:838-845` hardcodes `how="full"`; `join_type` is never read) and the main path takes **J**; the script uses `how="left"` | Every enriched report is ~1% smaller in the workflow; orphans are exported, not carried forward |
| 2 | **Rounding point.** The script rounds every money column once at the end; the Formula node rounds per section | Sub-cent drift per cell; aggregates can drift by cents-to-dollars at demo scale — use `--tolerance 0.5` on money files if you want the signal without the noise |
| 3 | **Date parsing order.** Select tries `%d-%m-%Y` *before* `%m-%d-%Y`; `pd.to_datetime(format="mixed")` infers month-first | The ~3% of ambiguous `DD-MM-YYYY` rows land in the **correct** month in the workflow and the **wrong** month in the script — the workflow is more correct here, and monthly key sets will differ |
| 4 | **Split shuffle.** Polars `shuffle(seed=42)` vs pandas `sample(random_state=42)` | Same 80/20 counts, different membership |
| 5 | **No top-N node** | "Top customers" is a revenue threshold on both sides |
| 6 | **Graph writes no file** | Script PNGs have no workflow equivalent |
| 7 | **Null timestamps** vanish through the year-gate Filter (null comparisons keep the row out of both T and F); the script files them under `rejected_future_dates.csv` | A handful of rows (<0.5%) present in neither workflow output |
| 8 | **Cleansing runs null-removal before whitespace/case** inside one node | Split across two nodes (Stages 3–4) to match the script's order |

Difference 3 is worth dwelling on: a comparison that only checked "do the
numbers match" would miss that the script is quietly filing ~3% of orders into
the wrong month. That is the point of the exercise — the comparator's key-set
overlap column exists to catch exactly this class of divergence.
