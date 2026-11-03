# Retail Ledger workflow load: measured optimizations

Measured 2026-09-30 on Windows, Python 3.13, headless Qt, using
`savedfiles/Example_2_Retail_Ledger/app_workflow/1.tds` (105 nodes, 113 edges).
All timings are wall-clock and include synchronous evaluation during file
load, not the separate Run Workflow command. See `scripts/profile_loading.py`
for repeatable phase timing, per-node exclusive costs, and optional output
fingerprints. Measurements fluctuate with cold imports, filesystem caches,
and background system activity; the adjacent stages below used separate
fresh-process runs rather than pretending to be a controlled microbenchmark.

| Stage | Commit | File load | Evaluation | First / re-settle recomputes |
|---|---|---:|---:|---:|
| Original behavior (forced old Union pass) | `e96b024` | 4,489 ms | 4,267 ms | 138 / 72 |
| Only retry incomplete Unions | `7f28adb` | 2,801 ms | 2,522 ms | 138 / 0 |
| Single-query live Formula | `842cfa4` | 2,431 ms | 2,170 ms | 138 / 0 |
| Suppress reentrant child pushes during bulk load | `eea0ed3` | 1,860 ms | 1,595 ms | 105 / 0 |
| Final, cold without background warm-up | `60d51c7` | 1,889 ms | 1,636 ms | 105 / 0 |
| Final, warmed before loading | `60d51c7` | 1,312 ms | 1,132 ms | 105 / 0 |

Cold load is about **58% shorter** than the original 4,489 ms run (2.38x).
With a prewarmed bridge the *load itself* is about **71% shorter** (3.42x),
but warming does not eliminate the roughly 622 ms first-use initialization:
it moves it off the GUI thread while the splash is shown. For an immediate
command-line file open, warm-up and loading may race, so neither the 1,312 ms
nor the implied end-to-end speedup is guaranteed. Three consecutive
prewarmed loads in one process were 1,237, 1,307, and 1,231 ms.

For all six staged runs, every one of the 105 node result fingerprints,
schemas, shapes, and invalid statuses matched the old forced-Union-pass
baseline. GroupBy snapshots are sorted before hashing because GroupBy does
not guarantee output row order. The real application was also launched
offscreen with this saved file with background warming enabled and disabled;
both file opens succeeded. Focused Formula, Union, Filter, batch evaluation,
and warm-up suites: **57 passed**. Full `tests/unit` collection is currently
blocked by an unrelated pre-existing `test_sql_editor.py` import of the
unavailable top-level `sql_formula_editor` module.

The Filter single-query experiment was **rejected and reverted**: cold/warm
runs did not establish a speedup (Filter exclusive time was 761/176/159 ms
before and 831/155/168 ms after), and four IPC fingerprints changed.
No Filter runtime change was committed. `TRIGGER_DISABLE_DATA_WARMUP=1`
disables the startup worker for A/B checks; profiling `--force-settle`
replays the old unconditional Union pass without changing application code.