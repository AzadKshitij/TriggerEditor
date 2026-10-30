# Node Reference

Every node available in the Trigger Designer palette, grouped by family. The
op id is the stable identifier stored in saved workflows
(`src/trigger_designer/core/node_configuration.py`); icons live in
`src/trigger_designer/resources/qt/images/node_icons/` and are mapped in
`src/trigger_designer/qt/resources.json`.

## Input / Output

| Node Name | Node Image | Description |
|---|---|---|
| File Input | ![File Input](../src/trigger_designer/resources/qt/images/node_icons/Input/File%20Input.svg) | Reads CSV/TXT, Excel (one, all, or chosen sheets), Parquet, JSON, JSON Lines, SQLite, and DuckDB sources. A file may be a single path, a folder, or a glob; matching files are unioned by column name with a per-file source report and an optional filename/sheet column. Database reads are read-only (one table or one SELECT). "Read all columns as text" makes typed sources behave like CSV; CSV itself always arrives as strings. |
| File Output | ![File Output](../src/trigger_designer/resources/qt/images/node_icons/Input/File%20Output.svg) | Writes the incoming frame to a CSV, Parquet, or Excel file at the configured path. |
| Workpaper Output | ![Workpaper Output](../src/trigger_designer/resources/qt/images/node_icons/Input/Workpaper%20Output.svg) | Writes an audit workpaper as one Excel workbook: a Summary sheet (engagement details, test, population and exception counts, source files with SHA-256), the Exceptions list with tick marks and comment columns, and optional Run log and Workflow sheets. Inputs are Exceptions (required), Population and Summary (both optional; Summary is the one-row frame an audit node emits). The output must end in `.xlsx`; "If the file exists" is New version, Replace or Stop with error, and an exception list over the row limit is also written in full to `<name>_exceptions_full.csv`. |

## Join

| Node Name | Node Image | Description |
|---|---|---|
| Join | ![Join](../src/trigger_designer/resources/qt/images/node_icons/Join/Join.svg) | Joins two inputs on a user-defined column mapping using the selected join type. |
| Append | ![Append](../src/trigger_designer/resources/qt/images/node_icons/Join/Append.svg) | Stacks the rows of the right input underneath the left input. |
| Union | ![Union](../src/trigger_designer/resources/qt/images/node_icons/Join/Union.svg) | Stack two or more inputs vertically (columns matched by name or manual mapping). |
| Reconcile | ![Reconcile](../src/trigger_designer/resources/qt/images/node_icons/Join/Reconcile.svg) | Matches two inputs on key columns plus an amount tolerance and/or date window, emitting matched pairs, both unmatched sides, and a summary. |
| Fuzzy Match | ![Fuzzy Match](../src/trigger_designer/resources/qt/images/node_icons/Join/FuzzyMatch.svg) | Pairs similar text (for example vendor and supplier names) from two inputs by Jaro-Winkler or Levenshtein score, emitting matched pairs and both unmatched sides. |

## Preparation

| Node Name | Node Image | Description |
|---|---|---|
| Cleansing | ![Cleansing](../src/trigger_designer/resources/qt/images/node_icons/Preparation/Cleansing.svg) | Per-column data cleanup: trim, case, empty-value handling, and dtype coercion. |
| Filter | ![Filter](../src/trigger_designer/resources/qt/images/node_icons/Preparation/Filter.svg) | Keeps or drops rows using comparison operations evaluated against chosen columns. |
| Formula | ![Formula](../src/trigger_designer/resources/qt/images/node_icons/Preparation/Formula.svg) | Creates or edits calculated columns from SQL-like expressions. |
| GroupBy | ![GroupBy](../src/trigger_designer/resources/qt/images/node_icons/Preparation/Groupby.svg) | Collapses rows into groups by key columns and applies aggregations over each group. |
| Select | ![Select](../src/trigger_designer/resources/qt/images/node_icons/Preparation/Select.svg) | Chooses which columns to keep, drop, rename, and reorder in the output. |
| Sort | ![Sort](../src/trigger_designer/resources/qt/images/node_icons/Preparation/Sort.svg) | Orders rows by one or more columns, each ascending or descending. |
| Split | ![Split](../src/trigger_designer/resources/qt/images/node_icons/Preparation/Split.svg) | Splits the data into training and validation datasets for modelling workflows. |
| Unique | ![Unique](../src/trigger_designer/resources/qt/images/node_icons/Preparation/Unique.svg) | Removes duplicate rows based on the selected columns. |
| Normalize | ![Normalize](../src/trigger_designer/resources/qt/images/node_icons/Preparation/Select.svg) | Renames columns deterministically: trim, collapse internal whitespace, then apply a case rule. |
| Rows | ![Rows](../src/trigger_designer/resources/qt/images/node_icons/Preparation/Dynamic%20Row%20Generate.svg) | Builds a grid or series of rows from configured patterns, ranges, or literals. |
| Record ID | ![Record ID](../src/trigger_designer/resources/qt/images/node_icons/Preparation/RecordID.svg) | Adds a dense numbered column in input order, optionally restarting per group and ordered by chosen columns. |
| Select Records | ![Select Records](../src/trigger_designer/resources/qt/images/node_icons/Preparation/SelectRecords.svg) | Keeps the first, last, ranged, largest, or smallest rows and sends the remainder out of the second socket. |
| Find and Replace | ![Find and Replace](../src/trigger_designer/resources/qt/images/node_icons/Preparation/FindReplace.svg) | Applies ordered literal or regex replacements across selected text columns, in place or into suffixed columns. |
| Date Helper | ![Date Helper](../src/trigger_designer/resources/qt/images/node_icons/Preparation/DateHelper.svg) | Adds date parts, fiscal periods, day differences, holidays, and business-day calculations as new columns. |
| Multi-Field Formula | ![Multi-Field Formula](../src/trigger_designer/resources/qt/images/node_icons/Preparation/MultiFieldFormula.svg) | Applies one SQL expression to every ticked column, replacing the columns or adding `<column><suffix>` copies. `{col}` is the column and `{name}` its name as text; the query runs through the read-only SQL guard (`TD-SHAPE-110`/`112`/`113`), and a formula without `{col}` is `TD-SHAPE-120`. At most 200 columns. |
| Text to Columns | ![Text to Columns](../src/trigger_designer/resources/qt/images/node_icons/Preparation/TextToColumns.svg) | Splits one text column on a literal delimiter or a regex into new columns (the last takes the remainder) or into one row per piece; errors `TD-SHAPE-044` (not text) and `TD-SHAPE-101` (pattern can match nothing). |

> Normalize reuses the Select glyph (`node_select`) until a dedicated
> icon ships; the source file is `node_icons/Preparation/Select.svg`.

## Transform

| Node Name | Node Image | Description |
|---|---|---|
| Count | ![Count](../src/trigger_designer/resources/qt/images/node_icons/Transform/Count.svg) | Counts the rows of the input and returns a one-row table with a single `Count` column. There is no grouping and no settings; for a count per group use GroupBy (Aggregate). The live preview counts only the first 100 rows; Run counts all of them. |
| Running Total | ![Running Total](../src/trigger_designer/resources/qt/images/node_icons/Transform/Running%20Total.svg) | Adds a column with a cumulative sum of a numeric column, optionally per group. |
| Transpose | ![Transpose](../src/trigger_designer/resources/qt/images/node_icons/Transform/Transpose.svg) | Goes from wide to long: the chosen data columns become rows. The output keeps the chosen key columns and adds `Name` (the old column name) and `Value` (the cell), one block of rows per data column. It does not swap rows and columns. |
| Pivot | ![Pivot](../src/trigger_designer/resources/qt/images/node_icons/Transform/Pivot.svg) | Turns distinct header values into columns, aggregating a value column per index group. |
| Unpivot | ![Unpivot](../src/trigger_designer/resources/qt/images/node_icons/Transform/Unpivot.svg) | Stacks selected value columns into a name/value pair while keeping the chosen ID columns. |
| SQL Query | ![SQL Query](../src/trigger_designer/resources/qt/images/node_icons/Transform/SQL%20Query.svg) | Runs one read-only `SELECT` over up to three inputs, which appear as the tables `t1` (required), `t2` and `t3` (optional). The query goes through the SQL guard (`TD-SHAPE-110` to `-115`): one statement, no files, extensions, `PRAGMA`/`COPY`/`ATTACH`, no random functions, 20,000 characters, 25 s. Table names are fixed, so a referenced input that is not connected is `TD-SHAPE-113`. File Input columns are text, so cast numbers with `try_cast`. |
| Window | ![Window](../src/trigger_designer/resources/qt/images/node_icons/Transform/Window.svg) | Adds one column per calculation (previous/next row, row number, rank, running sum/min/max/mean, rolling sum), optionally restarting per group and ordered by chosen columns. Rows keep their input order. |

## Report

| Node Name | Node Image | Description |
|---|---|---|
| Graph | ![Graph](../src/trigger_designer/resources/qt/images/node_icons/Report/Graph.svg) | Charts the incoming data in a matplotlib window that unlocks after a successful run; passes its input through unchanged. |
| Data Profile | ![Data Profile](../src/trigger_designer/resources/qt/images/node_icons/Report/Data%20Profile.svg) | Profiles every column of the whole input: nulls, blanks, distinct counts, min/max, numeric statistics and a histogram, the most frequent values, and a suggested type with quality flags (numbers or dates stored as text, mixed dates, leading zeros, stray whitespace, negatives, outliers). Socket `D` passes the input through; socket `P` is a one-row-per-column table (`PROFILE_SCHEMA`, see `docs/plan/05-data-profile-node.md`). The dock shows a sortable table and a per-column detail pane, a **Full report** button (opens an HTML report with a card for every column in the browser) and one **Export** menu (copy, CSV, HTML report, Excel). While you edit, the dock profiles only the first 100 rows the canvas holds (like every node); **run the workflow** and it switches to the profile of all rows, until a setting changes or the next run. Inputs over 150 columns skip the live preview (run the workflow to profile them). Options: sample (all rows, first N, random N with seed), top values, estimate-over threshold for distinct counts, chart bars. |
| Comment | ![Comment](../src/trigger_designer/resources/qt/images/node_icons/Report/Comment.svg) | A note on the canvas with no inputs or outputs; it never executes (the run records it as a no-op and its generated code is `# Comment (not executed)`). The text is saved in the `.tds`; its first line (60 characters at most) is the label shown above the node and is rewritten on every text change. Read comments for the workpaper or run log with `comments_from_scene_dict` / `comments_from_nodes` in `core/shaping/comments.py` (reading order: top to bottom, then left to right; blank notes skipped). |

## What Run verifies

Run recomputes every node first, in graph order, so no step executes with stale
or never-evaluated settings; a step that is still invalid keeps its red state and
is listed in the Logging dock. After each step runs, the plan of every lazy output
is schema-checked: an unknown column, a bad join key or a duplicate output name
fails the step that caused it, with or without a File Output downstream. Errors
that depend on the data itself (for example one value that cannot be cast)
surface only where data is read: File Output, Graph, Count and the Data Preview.

The **Cancel** button replaces Run while a run is in flight. Cancelling is
cooperative: the step that is executing finishes, and the remaining steps are not
started. A loop in the graph refuses to run and leaves Run available.

## Internal (not in the palette)

| Node Name | Node Image | Description |
|---|---|---|
| Unknown | _(none)_ | Placeholder shown when a saved node's op id cannot be resolved; preserves its content so nothing is lost. |

`TriggerNode_Unknown` (`src/trigger_designer/qt/widgets/nodes/unknown.py`) is
deliberately unregistered and never appears in the palette. It also has no
entry in `resources.json`, so `node_unknown` renders blank.

## Icons not yet wired to a node

These SVGs ship in the icon folder but no registered node references them.

| Icon | Source file |
|---|---|
| ![Image](../src/trigger_designer/resources/qt/images/node_icons/Report/Image.svg) | `node_icons/Report/Image.svg` |
| ![InOut](../src/trigger_designer/resources/qt/images/node_icons/INOUT.svg) | `node_icons/INOUT.svg` |
| ![Browse](../src/trigger_designer/resources/qt/images/node_icons/Input/Browse.svg) | `node_icons/Input/Browse.svg` |

`Join/find_replace.py` and `Documentation/comment.py` are empty placeholder
files, and `IONodes.BROWSER` / `IONodes.TEXT_INPUT` are registered enum members
with no implementation behind them. The reusable canvas note lives
in the `qtpy-nodeeditor` library instead of an app-specific Report node.
