# Data limits: how much the app can process lazily

_As of branch `claude/lazy-first-polars`, 2026-10-26._

## Short answer

There is no fixed row or file-size limit in the code. The real limit is RAM. It applies where the app loads a whole table, and where Polars falls back to the in-memory engine. A few explicit caps stop work with an error, or truncate the output.

Live editing is different. While you edit, the app works on the first 100 rows of each input. Run processes the whole input. See [Live evaluation](#live-evaluation).

## Live evaluation

While you edit, each node reads at most `LIVE_SAMPLE_ROWS` (100) leading rows of each input and publishes at most 100 rows per output. Run does not use this path: it runs the generated code on the whole input.

Where the cap is applied:

- `ShapingNode.processInputs` (`qt/helpers/shaping_support.py`) caps each input and each output of every shaping node.
- File Input (`qt/widgets/nodes/InOut/file_input.py`) caps its live output.
- Union (`qt/widgets/nodes/Join/union.py`) caps its live output.
- The helper is `live_sample` in `core/shaping/common.py`.

What that means in practice:

- Lazy inputs (CSV, Parquet, NDJSON) stay lazy. Opening a workflow reads at most 100 rows per node in live mode, instead of scanning the whole input.
- Live previews show at most 100 rows. The source tooltip says so.
- Counts shown while editing describe the sample. The Count node's chip says "First 100 rows only: full count at Run". The Find & Replace and Date Helper chips name the same scope.
- A Graph window plots the frame its node last received. After a Run that is the full result. After an edit upstream it plots the live sample until the next Run.
- Excel, JSON and database inputs are still read in full when a workflow loads. As far as known, Polars has no lazy scan for these formats. The cap limits what runs downstream of the read, not the read itself.

## What streams (no RAM ceiling for the data itself)

- **Inputs:** CSV, Parquet and NDJSON use `scan_*` (`core/input_source.py`).
- **Outputs:** CSV, Parquet, NDJSON and IPC use `sink_*` (`core/shaping/file_output.py`).
- **Column-expression nodes**, such as Select, stay lazy.

## What loads the whole table into RAM

| Node or path | Why | Where |
|---|---|---|
| Filter, Formula | The SQL result is materialised with `.pl()`. DuckDB spills its own operators, but the output still has to fit in RAM. | `core/shaping/filter.py`, `core/shaping/formula.py` |
| Cleansing | Collects the whole input. `DataCleansing` works on DataFrames. | `core/shaping/cleansing.py` |
| Reconcile | Collects both inputs. Matching needs materialised candidates. | `core/shaping/reconcile.py` |
| Pivot | Collects the grouped result, one row per index and header combination. | `core/shaping/reshape.py` |
| Transpose | The ordering sort may need the whole table. Spilling is not verified. | `core/shaping/transpose.py` |
| Excel, JSON-array and SQLite inputs | Read whole, including while editing. As far as known, Polars has no lazy scan for these formats. | `core/input_source.py` |
| Excel and JSON-array outputs | Collected before writing. No streaming sink is known for either. | `core/shaping/file_output.py` |
| Operations Polars cannot stream | Fall back to the in-memory engine, which needs RAM for its input. | Polars engine |

## Explicit caps

- **Reconcile:** more than 5,000,000 candidate pairs raises `TD-SHAPE-072` (`MAX_CANDIDATE_PAIRS`, `core/shaping/reconcile.py`). This check runs at Run.
- **Pivot:** more than 500 distinct header values raises `TD-SHAPE-061` (`MAX_PIVOT_COLUMNS`, `core/shaping/reshape.py`).
- **Old live caps:** Pivot's 5,000,000-row and Reconcile's 200,000-row live limits can no longer trigger, because live inputs are capped at 100 rows. `LIVE_CAP_ROWS` remains in the code and is unused in practice.
- **Charts:** aggregated charts aggregate the whole frame they receive, then cap the distinct X groups at 2,000. Unaggregated charts show the first 2,000 rows and report the truncation (`MAX_CHART_POINTS`, `core/charts.py`). A chart built from a live frame covers the 100-row sample.
- **Previews:** Run results show 1,000 rows or 2 MB, whichever is smaller (`qt/models/preview_sampling.py`, `qt/models/preview_worker.py`). Live values show the first 100 rows. The File Input table viewer shows 10 rows (`qt/widgets/nodes/InOut/file_input.py`).

## Engine settings

- **DuckDB:** the memory limit defaults to 80% of RAM. DuckDB spills to a temp directory for grouping, joins, sorts and windows. The app runs DuckDB on one thread (`DUCKDB_THREADS` in `core/shaping/common.py`), so large SQL nodes are slow before they run out of memory.
- **Polars 2.0:** lazy queries stream by default. Row order is not guaranteed for joins, group-bys and unpivots unless `maintain_order` is set. Any node that relies on incidental row order needs an explicit sort.

## Not measured

The actual ceiling on this machine is unknown. A suggested test is to generate a 10–50 million row CSV and time a Select → Filter → write workflow. Load time with live sampling is also unmeasured on large files.

## Sources

- Polars docs: the streaming concept page, the 2.0 upgrade guide (streaming default and the row-order warning), and the `sink_*` reference.
- DuckDB docs: larger-than-memory workloads, and the limits table (`memory_limit`, temp directory).
