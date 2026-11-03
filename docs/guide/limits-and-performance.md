# Limits and performance

How big can your data be, how long can a step take, and what can you do to keep a big workflow quick? This page gives the numbers the app really enforces, explains the difference between nodes that stream data and nodes that hold it in memory, and ends with advice for big files.

[Back to the guide index](README.md)

## On this page

- [The short answer](#the-short-answer)
- [Limits the app enforces](#limits-the-app-enforces)
- [Lazy and eager nodes](#lazy-and-eager-nodes)
- [Live editing versus Run](#live-editing-versus-run)
- [What the run record adds](#what-the-run-record-adds)
- [Advice for big files](#advice-for-big-files)
- [If something goes wrong](#if-something-goes-wrong)

## The short answer

There is **no fixed limit on rows or file size**. The practical limit is your computer's memory (RAM), and it applies at the steps that must hold a whole table at once. A few explicit caps stop a step with a clear message, and every step has a 30-second timer. The preview and the live editing view only ever show a small part of the data, whatever the file size.

## Limits the app enforces

| What | Limit | What happens | Where it is explained |
|---|---|---|---|
| Rows read while you edit (live evaluation) | **100 rows** per input; at most 100 rows shown per output | Only a sample is processed while editing; **Run processes everything**. | [Running workflows](running-workflows.md#live-evaluation-and-the-100-row-sample) |
| Data Preview after a Run | **1,000 rows or 2 MB**, whichever is smaller | A window onto the result. Exports from the preview write only these rows. | [Data Preview](config-dock-and-preview.md#data-preview) |
| Time per step in a Run | **30 seconds** (Workpaper Output: **10 minutes**) | The step stops with `TD-RUN-001`; the Run stops. | [Time and memory limits](running-workflows.md#time-and-memory-limits) |
| SQL Query run time | **25 seconds** | Interrupted with `TD-SHAPE-115`. | [Security and privacy](security-and-privacy.md#sql-is-read-only-and-locked-down) |
| SQL text length | 20,000 characters | `TD-SHAPE-114`. | same |
| SQL Query memory | 2 GB | `TD-SHAPE-113` with the engine's message. | same |
| Memory in general | None enforced | If the computer runs out, the step fails with `TD-RUN-002`. | |
| Files from one folder or pattern | 10,000 by default (setting **Max files** in File Input) | `TD-IN-012` "The folder matches too many files". | [Files and formats](files-and-formats.md#input-file-types) |
| Reconcile | 5,000,000 candidate pairs | `TD-SHAPE-072` (checked at Run). | node page |
| Fuzzy Match | 5,000,000 candidate pairs; and without blocking, 1,000,000 row pairs | `TD-SHAPE-081`, `TD-SHAPE-082`, checked before any scoring. | node page |
| Pivot | 500 distinct header values | `TD-SHAPE-061`. | node page |
| Charts | 2,000 distinct groups or points | The chart says it was truncated. | node page |
| Excel output | 1,048,575 data rows and 16,384 columns per sheet | `TD-OUT-013`, `TD-OUT-011`; use CSV or Parquet for more. | [Files and formats](files-and-formats.md#output-file-types) |
| Logs dock | The latest 1,000 messages per workflow | Older ones scroll off. | |
| Undo history | 200 steps per workflow | The oldest steps are dropped. | [Undo and redo](canvas-and-nodes.md#undo-and-redo) |
| Error row search | 5,000,000 rows (a preference) | The message stays general when the bad row is further down. | [Preferences](preferences.md) |
| Fingerprinting an input or output file | Skipped above 2,048 MB (a preference) | `sha256_status` is `skipped_size_limit`. | [Run history](run-history-and-audit-trail.md) |

Counts you see while editing describe the sample. For example, the Count node says "First 100 rows only: full count at Run".

## Lazy and eager nodes

The app builds most work as a **plan**, not as a calculation. A step on a CSV does not read the file; it adds a line to a plan. Data is only read, in pieces, when something at the end of the plan (such as a File Output) asks for the result. Such nodes are **lazy**, and they can handle files much bigger than your memory.

Some nodes need the whole table in memory to do their job. Those are **eager**. They still work on big data, but their size is bounded by RAM.

| Group | Nodes and inputs | Behaviour |
|---|---|---|
| **Streams** (no memory ceiling for the data itself) | Reading **CSV**, **Parquet** and **JSON Lines**. Writing **CSV**, **Parquet**, **JSON Lines** and **Arrow IPC**. Column-based nodes such as **Select**. | Data flows through in pieces. |
| **Holds the result in memory** | **Filter** and **Formula** (SQL result), **Cleansing**, **Reconcile**, **Fuzzy Match**, **Pivot**, **SQL Query**, **Transpose** (the sort step may need the whole table) | The step's output has to fit in RAM. |
| **Reads the whole file** | **Excel**, **JSON** (an array of records), **SQLite** and **DuckDB** inputs | Read in full, even while editing. |
| **Collects before writing** | **Excel** and **JSON** (array) outputs | The whole table is gathered first. |

Row order: after joins, groups and unpivots the order of rows is not guaranteed unless the node sorts. Add a **Sort** node when the order matters.

## Live editing versus Run

Editing is quick because it works on 100 rows. Run is the real work, on all of them. A workflow that feels instant while you build it may take minutes to Run on millions of rows, and a step that is fine on the sample may hit a limit on the full data. Two rules of thumb:

- After you finish building, Run it once and look at the Logs and the run's duration before you rely on it.
- Open **Problems** after a Run, not only while editing: some errors (a value that cannot be converted, 500+ pivot columns, too many fuzzy pairs) appear only on the full data.

## What the run record adds

The [run record](run-history-and-audit-trail.md) costs a little time:

- **Fingerprinting** reads each input and output file once to compute its SHA-256 (a repeat Run on an unchanged file reuses the earlier hash). Turn it off, or lower the size limit, in the Audit trail preferences if you work with very large files.
- **Row counting in "All nodes" mode** computes each node's result once and **keeps it in memory** so every node can have an exact row count. That is why **Auto** switches to **Sinks only** when the combined input is over 256 MB: there, only the input files and the written output files are counted and nothing is held. If you have a big input and plenty of memory, you may set **All nodes**; if a Run runs out of memory on a big input, set **Sinks only** or **Off**.

## Advice for big files

1. **Prefer Parquet or CSV for large outputs.** They are written as a stream. Excel and JSON arrays are collected first and Excel cannot hold more than about a million rows per sheet.
2. **Convert Excel inputs once.** An Excel file is read in full every time the workflow opens. For a very large workbook, save the sheet as CSV or Parquet and read that.
3. **Filter and select early.** Put a **Select** (drop the columns you do not need) and a **Filter** or **Select Records** as close to the input as you can. Fewer rows and columns make every later step quicker and smaller.
4. **Keep an eye on text columns.** CSV columns are read as text. Converting only the columns you need, once, is cheaper than converting everything.
5. **Split a heavy step.** If one step is near its time limit (30 seconds) on your data, put a **Filter** before it, or split the work in two workflows, writing the first stage to Parquet.
6. **Sample for audit tests.** For a first look, a **Sample** node (with a seed) over the population lets you try tests quickly. Run the tests over the whole population when you are happy.
7. **Close what you do not need.** Each open workflow keeps its own previews and logs. Close finished ones.
8. **Avoid joining on text keys with different cases or spaces.** Clean them first (Cleansing or Normalize), or a join can multiply or lose rows.
9. **Check the Logs for timing.** Every Run logs how long it took and the average of this session.

## If something goes wrong

| Symptom | What to do |
|---|---|
| "This step took longer than 30 seconds and was stopped" | Apply advice 3 and 5. A very large write to CSV may also hit it: write Parquet, or filter first. |
| "This step ran out of memory" | Filter rows and drop columns earlier; use Sinks only or Off for **Row counts**; close other programs; avoid Excel/JSON for the big step. |
| The workflow is slow to open | Excel, JSON and database inputs are read in full on open. Convert them, or reduce **Row limit** in File Input while you build. |
| Counts on screen are small | You are looking at the 100-row sample. Run, then read the counts in the preview or the run record. |
| The app is busy after a stopped step | The step's background work cannot be forcibly ended; it finishes in the background. Wait a moment before the next Run. |
