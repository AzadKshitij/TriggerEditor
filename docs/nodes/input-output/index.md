# Input and Output nodes

These nodes connect your workflow to files. **File Input** reads data in. **File Output** writes the result out. **Workpaper Output** writes an audit workpaper (a formatted Excel file with the evidence). Every workflow starts with at least one File Input.

## Nodes in this family

| Icon | Node | What it does |
|---|---|---|
| ![File Input](../../assets/node_icons/Input/File%20Input.svg) | **[File Input](file-input.md)** | Reads a CSV or text file, an Excel workbook, Parquet, JSON, JSON Lines, SQLite or DuckDB (one file, a folder or a pattern; matching files are stacked by column name). CSV columns arrive as text. |
| ![File Output](../../assets/node_icons/Input/File%20Output.svg) | **[File Output](file-output.md)** | Writes the incoming table to a CSV, Parquet or Excel file when you Run. |
| ![Workpaper Output](../../assets/node_icons/Input/Workpaper%20Output.svg) | **[Workpaper Output](workpaper-output.md)** | Writes a formatted Excel workpaper with the test results and the evidence behind them. |

---

## Live preview and Run

This applies to every node in the app, so it is explained once, here.

**While you edit, the app works on a small sample. Run works on everything.**

| | While you edit (live preview) | When you press Run |
|---|---|---|
| Rows each node reads from each input | The first 100 rows | All rows |
| Rows each node shows on each output | At most 100 | All rows are processed; the Data Preview shows up to 1,000 rows (or 2 MB, whichever is smaller) |
| Files are written | Never | Yes (File Output, charts, reports) |

What this means for you:

- **Counts, totals and matches in the live preview describe the sample, not your data.** A Join can show "no matches" in the preview because the matching row is row 101. A Count node shows at most 100. Treat the preview as a way to check that your settings are wired correctly; read the real numbers after a Run.
- **A problem hiding in row 5,000 will not appear until you Run.** An unexpected text value in a number column, a Reconcile that finds too many candidate pairs, or a bad byte deep in a file only show up when the full data is read.
- **Excel, JSON and database inputs are read in full even while editing.** Only what happens downstream of them is limited to 100 rows.
- The Data Preview tells you which one you are looking at. It says "from Run" for the result of the last Run, and "evaluated, not run" for a live preview.
- To Run, press the **Run workflow** button (the play icon at the top-left of the canvas). While a run is in progress the same spot shows a **Cancel run** button; cancelling stops after the current step finishes.

If you need a number you can quote, Run the workflow and read it from the run result, not from the preview.

For how a Run works step by step (and what happens when a step fails), see [Running workflows](../../guide/running-workflows.md#live-evaluation-and-the-100-row-sample).

---

