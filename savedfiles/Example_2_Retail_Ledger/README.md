# Example 2 — Retail Ledger Showcase

A deliberately large, deliberately dirty retail dataset, a Pandas reference
pipeline that turns it into a full set of business reports, and a node-by-node
recipe for reproducing that pipeline inside TriggerDesigner so the two can be
compared.

The point of the example is the **comparison**. Every stage of the script has a
node-level equivalent, and where they disagree the reason is written down
rather than smoothed over.

> This replaces nothing in the app. It only adds files under
> `savedfiles/Example_2_Retail_Ledger/`.

---

## Quick start

```bash
cd savedfiles/Example_2_Retail_Ledger

python step1_generate_data.py --scale demo   # ~41k orders, ~4 MB, instant
python step2_reference_pipeline.py           # writes reference_output/
```

Then open the app, build the workflow from
**[NODE_SETUP_GUIDE.md](NODE_SETUP_GUIDE.md)**, point its File Output nodes at
`app_output/`, run it, and:

```bash
python step3_compare.py
```

---

## Files

| File | What it is |
|---|---|
| `config.py` | Paths, scale presets, business thresholds, defect rates. The single source of truth both sides read. |
| `step1_generate_data.py` | Builds the six CSVs, with the data-quality defects injected on purpose. |
| `step2_reference_pipeline.py` | The Pandas "ground truth". Writes 23 reports to `reference_output/`. |
| `NODE_SETUP_GUIDE.md` | How to build the equivalent workflow by hand, node by node, with every gotcha. |
| `step3_compare.py` | Diffs `app_output/` against `reference_output/`. |
| `data/` | Generated input (not checked in). |
| `reference_output/` | Pandas reports. |
| `app_output/` | Your workflow's reports. |

---

## The dataset

Five dimension tables and one fact table, sized by preset:

| Preset | orders | customers | products | suppliers | On-disk (orders) |
|---|---|---|---|---|---|
| `demo` | 40,000 | 4,000 | 400 | 60 | 4 MB |
| `standard` | 500,000 | 50,000 | 1,200 | 300 | ~55 MB |
| `large` | 2,000,000 | 200,000 | 2,000 | 500 | ~220 MB |
| `xlarge` | 10,000,000 | 500,000 | 5,000 | 800 | ~1.1 GB |

`orders.csv` is the interesting one. Every defect below exists to force a
specific node type, and the counts are reproducible from a fixed seed:

| Defect | Rate | Forces |
|---|---|---|
| Messy headers (` Order ID `, `PRODUCT_ID`, `supplier id`) | 15 columns | Select → rename |
| Every value stored as text | 100% | Select → dtype mapping |
| Mixed date renderings (ISO, `/`, `.`, `12 Jan`, `DD-MM`) | ~11% | Select → Datetime parse |
| Padded / case-varied text | 35% / 25% | Cleansing → strip, case |
| Null `customer_id` / `product_id` / `order_ts` | 1.5% / 1.0% / 0.5% | Cleansing → remove null rows |
| Zero or negative quantity / price | 2% | Filter (both sockets used) |
| Absurd prices (50k–900k) | 0.3% | Filter → price cap |
| Timestamps in 2099 | 0.4% | Filter → year gate |
| Exact duplicate orders | 2% | Unique (both sockets used) |
| Foreign keys absent from the dimension | 0.8% / 0.4% | Join → right-only socket |

`products.csv` is priced in **USD**; `orders.csv` transacts in 20 currencies.
Getting `cogs_usd` right is the example's deliberate trap — see the guide.

---

## What the pipeline produces

`step2_reference_pipeline.py` writes 23 files to `reference_output/`:

**Enriched fact** — `orders_enriched.csv` (35 columns), plus `.parquet` from
the workflow.

**Rollups** — `monthly_revenue`, `category_revenue`, `region_channel_revenue`,
`segment_revenue`, `top_customers`, `supplier_performance`, `fx_exposure`.

**Slices** — `orders_enterprise`, `orders_high_risk`, `fact_estimation` /
`fact_validation` (80/20 split), `monthly_revenue_long` (tidy form).

**Audit trails** — `rejected_quantity`, `rejected_price_outliers`,
`rejected_future_dates`, `duplicate_orders`, `orphan_customers`,
`orphan_products`, `data_quality_report` (row count at every cleaning stage).

**Reference data** — `reference_data_union` (all five dimensions stacked),
`scenario_grid`, `kpi_summary`.

---

## Comparing the two versions

`step3_compare.py` reports four things per file:

1. **Row counts** on each side and the delta.
2. **Row-set overlap** on the natural key (`order_year_month`, `category`,
   `currency`, …), so "same rows, different numbers" is distinguishable from
   "different rows entirely".
3. **Column differences** in either direction.
4. **Per-column value drift**, with the count of mismatching cells and the
   largest absolute delta, honouring a float tolerance.

It then lists files only one side produced, annotated with the expected reason.

### Differences you should expect

These are documented in full in
[NODE_SETUP_GUIDE.md](NODE_SETUP_GUIDE.md#differences-to-expect). In short:

| # | Difference | Effect |
|---|---|---|
| 1 | **The Join node always does a full outer join** and splits it into L/J/R sockets. `join_type` is not read by the code generator. The script uses a left join. | Every enriched report is ~1% smaller in the workflow |
| 2 | **`cogs_usd` currency double-conversion** — reproduced on purpose in the guide's formula, fixed in the script | `margin_pct` and `margin_usd` diverge until you fix it |
| 3 | **Running Total is a per-group `cum_sum`**, the script uses an unconditional `cumsum()` | `cumulative_revenue_usd` differs from 2025-01 |
| 4 | **Date parsing order.** Select tries `%d-%m-%Y` before `%m-%d-%Y`; `pd.to_datetime(format="mixed")` infers month-first | The workflow gets the ambiguous `DD-MM-YYYY` rows **right** and the script gets them **wrong** |
| 5 | **No top-N node** | "Top customers" is a revenue threshold on both sides |
| 6 | **Graph opens a window, writes no file** | The script's PNGs have no workflow equivalent |
| 7 | **Cleansing emits operations in a fixed order** (nulls → whitespace → case) | Split across two nodes to match the script |
| 8 | **Rounding happens per section in DuckDB**, once at the end in Pandas | Sub-cent drift in aggregates |

Difference 4 is worth dwelling on: the workflow is *more* correct than the
script here, and a comparison that only checked "do the numbers match" would
miss that the script is quietly filing ~3% of orders into the wrong month.

---

## Scaling up

```bash
python step1_generate_data.py --scale large
python step2_reference_pipeline.py
```

The generator is fully vectorised (no per-row Python loops), so `large` takes
seconds and `xlarge` takes a couple of minutes. The Pandas script is the
memory ceiling — it holds the whole enriched fact in memory, so `xlarge` will
want a machine rather than a laptop.

Things to watch as the row count climbs, all of them visible in the timings:

- The **Formula node defeats lazy evaluation**. It collects the incoming
  LazyFrame to a DataFrame, round-trips it through DuckDB **once per section**,
  then re-lazies the result. Nineteen sections is nineteen full passes over
  the fact table and a peak memory spike at the widest one. If a large run
  struggles, split the derived measures across several Formula nodes so no
  single node holds the whole table, or move the arithmetic into fewer, wider
  SQL statements.
- **Cleansing also collects to a DataFrame** before it can work row-wise.
- Everything else stays lazy end to end, and `File Output` streams via
  `sink_csv`.

---

## Notes

- `config.py` holds every threshold both sides share. If you change
  `TOP_CUSTOMER_REVENUE_THRESHOLD` or `SPLIT_ESTIMATION_PERCENT`, change it
  once and re-run both — otherwise the comparison is measuring two different
  problems.
- The generator uses fixed seeds, so the same `--scale` always produces the
  same bytes.
- `Faker` is deliberately not used: it is slow at millions of rows and not
  reproducible across versions.
