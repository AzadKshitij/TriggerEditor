# Node index

Every node in the Trigger Designer palette, grouped by the six tabs of the node palette (the same groups
appear in the `Shift+A` menu). Click a family page for every setting, worked examples and error messages.

| Family | Page | Nodes |
|---|---|---|
| Input / Output | [input-output.md](input-output.md) | File Input, File Output |
| Preparation | [preparation.md](preparation.md) | 16 nodes: clean, filter, calculate, sort, select |
| Join | [join.md](join.md) | Join, Append, Union, Reconcile, Fuzzy Match |
| Transform | [transform.md](transform.md) | Count, Running Total, Transpose, Pivot, Unpivot, Window, SQL Query |
| Report | [report.md](report.md) | Graph, Data Profile, Comment |
| Audit | [audit.md](audit.md) | Duplicates, Gaps, Benford, Sample, Risk Filters |

## Input / Output

Page: [input-output.md](input-output.md)

| Icon | Node | What it does |
|---|---|---|
| ![File Input](../../../src/trigger_designer/resources/qt/images/node_icons/Input/File%20Input.svg) | **File Input** | Reads a CSV or text file, an Excel workbook, Parquet, JSON, JSON Lines, SQLite or DuckDB (one file, a folder or a pattern; matching files are stacked by column name). CSV columns arrive as text. |
| ![File Output](../../../src/trigger_designer/resources/qt/images/node_icons/Input/File%20Output.svg) | **File Output** | Writes the incoming table to a CSV, Parquet or Excel file when you Run. |

## Preparation

Page: [preparation.md](preparation.md)

| Icon | Node | What it does |
|---|---|---|
| ![Cleansing](../../../src/trigger_designer/resources/qt/images/node_icons/Preparation/Cleansing.svg) | **Cleansing** | Per-column clean-up: trim, change case, handle empty values, convert type. |
| ![Filter](../../../src/trigger_designer/resources/qt/images/node_icons/Preparation/Filter.svg) | **Filter** | Keeps or drops rows that meet conditions you set. |
| ![Formula](../../../src/trigger_designer/resources/qt/images/node_icons/Preparation/Formula.svg) | **Formula** | Creates or changes columns from SQL-style expressions. |
| ![Aggregate](../../../src/trigger_designer/resources/qt/images/node_icons/Preparation/Groupby.svg) | **Aggregate** | Collapses rows into groups and totals, counts or averages each group. |
| ![Select](../../../src/trigger_designer/resources/qt/images/node_icons/Preparation/Select.svg) | **Select** | Chooses, renames, reorders and changes the type of columns. |
| ![Sort](../../../src/trigger_designer/resources/qt/images/node_icons/Preparation/Sort.svg) | **Sort** | Orders rows by one or more columns. |
| ![Unique](../../../src/trigger_designer/resources/qt/images/node_icons/Preparation/Unique.svg) | **Unique** | Keeps the first row for each key and sends the repeats out separately. |
| ![Split](../../../src/trigger_designer/resources/qt/images/node_icons/Preparation/Split.svg) | **Split** | Divides the rows into two sets by percent (an estimation and a validation set). |
| ![Rows](../../../src/trigger_designer/resources/qt/images/node_icons/Preparation/Dynamic%20Row%20Generate.svg) | **Rows** | Builds a series of rows from ranges, patterns or literal values. |
| ![Normalize](../../../src/trigger_designer/resources/qt/images/node_icons/Preparation/Select.svg) | **Normalize** | Tidies column names: trim, collapse spaces, apply one case rule. (Shares the Select icon.) |
| ![Record ID](../../../src/trigger_designer/resources/qt/images/node_icons/Preparation/RecordID.svg) | **Record ID** | Adds a numbered column, optionally restarting per group. |
| ![Select Records](../../../src/trigger_designer/resources/qt/images/node_icons/Preparation/SelectRecords.svg) | **Select Records** | Keeps the first, last, a range, the largest or smallest rows, and sends the rest out separately. |
| ![Find and Replace](../../../src/trigger_designer/resources/qt/images/node_icons/Preparation/FindReplace.svg) | **Find and Replace** | Applies an ordered list of text or pattern replacements to chosen columns. |
| ![Date Helper](../../../src/trigger_designer/resources/qt/images/node_icons/Preparation/DateHelper.svg) | **Date Helper** | Adds date parts, fiscal periods, day differences and business-day figures. |
| ![Multi-Field Formula](../../../src/trigger_designer/resources/qt/images/node_icons/Preparation/MultiFieldFormula.svg) | **Multi-Field Formula** | Applies one expression to many ticked columns at once. |
| ![Text to Columns](../../../src/trigger_designer/resources/qt/images/node_icons/Preparation/TextToColumns.svg) | **Text to Columns** | Splits one text column on a delimiter or pattern into columns or rows. |

## Join

Page: [join.md](join.md)

| Icon | Node | What it does |
|---|---|---|
| ![Join](../../../src/trigger_designer/resources/qt/images/node_icons/Join/Join.svg) | **Join** | Combines two tables on matching key columns and also gives the unmatched rows from each side (outputs `L`, `J`, `R`). |
| ![Append](../../../src/trigger_designer/resources/qt/images/node_icons/Join/Append.svg) | **Append** | Puts the rows of a second table underneath the first. |
| ![Union](../../../src/trigger_designer/resources/qt/images/node_icons/Join/Union.svg) | **Union** | Stacks two or more tables, matching columns by name or by a mapping you set. |
| ![Reconcile](../../../src/trigger_designer/resources/qt/images/node_icons/Join/Reconcile.svg) | **Reconcile** | Matches two tables on keys plus an amount tolerance and/or date window; gives matched pairs, both unmatched sides and a summary. |
| ![Fuzzy Match](../../../src/trigger_designer/resources/qt/images/node_icons/Join/FuzzyMatch.svg) | **Fuzzy Match** | Pairs similar text (such as vendor and supplier names) from two tables by similarity score. |

## Transform

Page: [transform.md](transform.md)

| Icon | Node | What it does |
|---|---|---|
| ![Count](../../../src/trigger_designer/resources/qt/images/node_icons/Transform/Count.svg) | **Count** | Returns the number of rows as a one-row table. |
| ![Running Total](../../../src/trigger_designer/resources/qt/images/node_icons/Transform/Running%20Total.svg) | **Running Total** | Adds a cumulative sum column, optionally per group. |
| ![Transpose](../../../src/trigger_designer/resources/qt/images/node_icons/Transform/Transpose.svg) | **Transpose** | Turns chosen columns into Name and Value rows. |
| ![Pivot](../../../src/trigger_designer/resources/qt/images/node_icons/Transform/Pivot.svg) | **Pivot** | Turns the values of one column into columns and totals a value column in each. |
| ![Unpivot](../../../src/trigger_designer/resources/qt/images/node_icons/Transform/Unpivot.svg) | **Unpivot** | Stacks several columns into a name column and a value column. |
| ![Window](../../../src/trigger_designer/resources/qt/images/node_icons/Transform/Window.svg) | **Window** | Adds previous or next row, row number, rank, running and rolling figures. |
| ![SQL Query](../../../src/trigger_designer/resources/qt/images/node_icons/Transform/SQL%20Query.svg) | **SQL Query** | Runs one read-only SELECT over up to three tables (`t1`, `t2`, `t3`). |

## Report

Page: [report.md](report.md)

| Icon | Node | What it does |
|---|---|---|
| ![Graph](../../../src/trigger_designer/resources/qt/images/node_icons/Report/Graph.svg) | **Graph** | Charts the incoming data in its own window after a successful Run; passes the data through unchanged. |
| ![Data Profile](../../../src/trigger_designer/resources/qt/images/node_icons/Report/Data%20Profile.svg) | **Data Profile** | Profiles every column: empty cells, distinct values, ranges, common values and data-quality flags. |
| ![Comment](../../../src/trigger_designer/resources/qt/images/node_icons/Report/Comment.svg) | **Comment** | A note on the canvas. It has no sockets and never runs. |

## Audit

Page: [audit.md](audit.md) (full guide: [audit-nodes.md](../../nodes/audit-nodes.md))

| Icon | Node | What it does |
|---|---|---|
| ![Duplicates](../../../src/trigger_designer/resources/qt/images/node_icons/Audit/Duplicates.svg) | **Duplicates** | Finds exact and near-duplicate rows. |
| ![Gaps](../../../src/trigger_designer/resources/qt/images/node_icons/Audit/Gaps.svg) | **Gaps** | Finds missing, repeated and out-of-order numbers, and days with no entry. |
| ![Benford](../../../src/trigger_designer/resources/qt/images/node_icons/Audit/Benford.svg) | **Benford** | Tests the leading digits of an amount column against Benford's law. |
| ![Sample](../../../src/trigger_designer/resources/qt/images/node_icons/Audit/Sample.svg) | **Sample** | Draws a random, systematic, monetary-unit or stratified sample that can be repeated with its seed. |
| ![Risk Filters](../../../src/trigger_designer/resources/qt/images/node_icons/Audit/Risk%20Filters.svg) | **Risk Filters** | Flags entries that trip classic journal-entry risk indicators. |

## Choosing a node

| I want to... | Use |
|---|---|
| Load a file, or save a result | File Input, File Output |
| Tidy messy text, spaces or types | Cleansing, Find and Replace, Normalize, Select |
| Keep only some rows | Filter, Select Records, Unique |
| Add a calculated column | Formula, Multi-Field Formula, Date Helper |
| Total or count per vendor, account or month | Aggregate (Preparation) |
| Count the rows of a table | Count |
| Add a running balance | Running Total (numbers) or Window (any running figure) |
| Compare each row with the previous one, or rank within a group | Window |
| Rotate month columns into rows | Unpivot (or Transpose) |
| Build a matrix of two categories | Pivot |
| Add records from one file to another | Append, Union |
| Look up values from another table | Join |
| Match payments to invoices with a tolerance | Reconcile |
| Match names that are spelled differently | Fuzzy Match |
| Write a query that no node covers | SQL Query |
| Find repeated invoices | Duplicates |
| Find missing cheque or journal numbers | Gaps |
| Test whether amounts look natural | Benford |
| Select items to test | Sample |
| Spot weekend, round-sum or just-under-limit entries | Risk Filters |
| Understand a new file | Data Profile |
| Show a chart or leave a note | Graph, Comment |

## Live preview versus Run

You work on the canvas with a **preview**; you get the real answer when you press **Run**.

**The preview is a 100-row sample.** As soon as a file is opened or a setting is changed, each node
calculates its output so you can see the effect. To keep a large workbook responsive, File Input and every
node after it work on the **first 100 rows** of each table in this preview, and show at most 100 rows of each
output. The limit is the same for every node (`LIVE_SAMPLE_ROWS` in the code). In the preview, a Count says
"100", a total is a total of the sample, and a Pivot may be missing a header that first appears on row 5,000.
Some nodes warn you (Count shows "First 100 rows only: full count at Run"; Data Profile, Reconcile, Fuzzy
Match and Date Helper say the same in their own words).

**Run uses every row.** **Run** recalculates every node in order, reading the whole input, writes the File
Outputs and records the run. Trust the Run, not the preview, for counts, totals, audit results and the files
you hand over. After a Run, the Data Preview dock labels each table *from Run*; a preview table is labelled
*evaluated · not run*, and its tooltip repeats the 100-row rule.

**A node runs when you leave its settings.** Changing a setting saves it at once and marks the node with a
yellow "!" (tooltip "Changes pending - the node runs when you click away"). The node recalculates when you
select another node, click the empty canvas, or close the document, and then everything after it updates.
So after typing, click away to see the result. Save and Run keep the pending change in the workflow and
Run recalculates everything anyway.

Exceptions to the "click away" rule: the **Audit** nodes, **Data Profile** and **Comment** update as soon as
you change a setting. A few nodes do not run on 100 rows even in the preview: Benford reads up to a million
rows, and Sample does not draw at all on more than 200,000 rows until you Run.

If a preview result disagrees with the Run, believe the Run.
