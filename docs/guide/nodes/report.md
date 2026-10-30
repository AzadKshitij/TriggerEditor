# Report nodes

Report nodes help you look at data and explain your work. They do not change your data: **Graph** and **Data Profile** pass the table through untouched, and **Comment** is a note that is not connected to anything.

| If you want to... | Use |
|---|---|
| Draw a line, bar or scatter chart of a table | [Graph](#graph) |
| Check the quality of a table: nulls, distinct values, text that should be numbers, odd values | [Data Profile](#data-profile) |
| Leave a note for yourself or the reviewer on the canvas | [Comment](#comment) |

## Contents

- [Graph](#graph) | [Data Profile](#data-profile) | [Comment](#comment)
- The live preview uses 100 rows and Run uses all rows: see [Live preview and Run](input-output.md#live-preview-and-run). Graph and Data Profile follow that rule.

---

## Graph

<img src="../../../src/trigger_designer/resources/qt/images/node_icons/Report/Graph.svg" width="56" alt="Graph icon">

### Contents

[Purpose](#purpose) | [When to use it](#when-to-use-it) | [Inputs and outputs](#inputs-and-outputs) | [Settings](#settings) | [Worked example](#worked-example) | [Edge cases and limits](#edge-cases-and-limits) | [Messages you may see](#messages-you-may-see) | [Tips](#tips)

### Purpose

Graph draws a chart of the table it receives, in its own window. It passes the table on unchanged, so you can put it in the middle of a workflow without disturbing anything.

### When to use it

- See how amounts change over time (a line chart of totals by month).
- Compare groups (a bar chart of the amount per vendor).
- Look for outliers and clusters (a scatter chart of amount against quantity).

It is for looking at data, not for producing a report file. The chart window lets you save a picture.

### Inputs and outputs

| Socket | Carries |
|---|---|
| Input (left) | The table to chart. |
| Output `Out` (right) | The same table, unchanged. |

### Settings

The Config Dock has one section. The **Show graph** icon button sits on the top row of the dock.

| Control | What it does | Default |
|---|---|---|
| **Show graph** (icon button) | Opens the chart in its own window. It is switched on only after a **successful Run**, with X and Y chosen. Its tooltip says why it is off: "Show graph (run the workflow first)" or "Show graph (no data to draw)". If the window is already open, it is brought to the front. | Off until a Run |
| **Type** | **Line**, **Bar** or **Scatter**. | Line |
| **Renderer** | The library that draws the chart: **matplotlib** or **pyqtgraph**. matplotlib uses its standard navigation toolbar; pyqtgraph replaces it with **reset view** and **save PNG** buttons. This only changes the look and the toolbar, never the data. | matplotlib |
| **X column** | The column for the horizontal axis. The list shows `(select column)` until you pick one. | Empty |
| **Y column** | The column for the vertical axis (the values). | Empty |
| **Color by** | Splits the data into one coloured series per value of this column (for example one line per region). `(none)` turns it off. | None |
| **Aggregate** | How to combine rows that share the same X (and colour): **None**, **Sum**, **Count**, **Mean**, **Median**, **Min**, **Max**. For a bar chart the default is **Sum**; for line and scatter it is **None** (one point per row). | Depends on Type |
| **Title** | Optional chart title, also shown in the window title. | Empty |

Details:

- A column you chose that later disappears from the input stays selected and is shown as `name (missing)`. The chart then reports the problem instead of drawing.
- The chart window follows your changes: edit a setting while it is open and the chart redraws after a short pause.
- With Type **Bar**, Aggregate shows **Sum**, because that is what a bar chart does unless you say otherwise. Choose **None** to draw one bar per row.
- After you reopen a saved workflow, the **Show graph** button is off again until you Run the workflow.
- The window title reads "Graph", "Graph - your title", and adds the renderer name when it is not matplotlib.
- Under the chart, a status line describes what is drawn, for example `3 points · sum of Sales per Month`, `5 points · colored by Region`, or `2,000 points shown (truncated)`.

### Worked example

A table of sales:

| Month | Region | Sales |
|---|---|---|
| Jan | N | 100 |
| Jan | S | 50 |
| Feb | N | 120 |
| Feb | S | 70 |
| Mar | N | 90 |

**Bar chart, X = Month, Y = Sales, Aggregate = Sum (the default).** The bars drawn are:

| Month | Bar height |
|---|---|
| Feb | 190 |
| Jan | 150 |
| Mar | 90 |

Status line: `3 points · sum of Sales per Month`. Note the order: text X values are sorted alphabetically (Feb, Jan, Mar), not by calendar. Use a real date, or a number such as 202501, to get time order.

**Aggregate = Mean** gives Feb 95, Jan 75, Mar 90.

**Line chart, X = Month, Y = Sales, Color by = Region.** One line per region: `Region: N` with Feb 120, Jan 100, Mar 90, and `Region: S` with Feb 70 and Jan 50. Status line: `5 points · colored by Region`.

**Count.** X = Region, Y = Month, Aggregate = Count draws a bar of 3 for N and 2 for S. Count works with any Y column; the other aggregates need a number.

### Edge cases and limits

- **Live preview vs Run.** The chart is built from the table the node last received. While you edit upstream, that is the first 100 rows; after a Run it is the full result. The **Show graph** button only opens after a Run, so you normally see the full data. See [Live preview and Run](input-output.md#live-preview-and-run).
- **Points are capped at 2,000.** With no aggregation, only 2,000 rows are drawn (for a line chart, the first 2,000 after sorting by X) and the status line says "(truncated)". With aggregation, the whole table is summarised first, and the number of distinct X groups is capped at 2,000. Summarise first (the Aggregate node in [Preparation nodes](preparation.md)) if you have more groups than that.
- **Order.** Line charts sort by X (ties keep the input order). Aggregated charts also sort by X. A scatter or bar chart with Aggregate = None keeps the input order.
- **Nulls.** A null X sorts last.
- **Aggregations need numbers** (except Count). If Y is text you get the message below; convert it with a Select node.
- **Empty table.** You get "No rows to plot."
- Graph itself never writes a file. Only the save button in the chart window does, and only when you press it.

### Messages you may see

Graph does not raise `TD-` codes; the chart window and the status line describe the problem in plain words.

| Message | Meaning and fix |
|---|---|
| No incoming data. | Nothing is connected, or the upstream node has an error. |
| Graph needs a table input. | The input is not a table. |
| Select an X column. / Select a Y column. | Choose the columns in the dock. |
| X column 'name' is not in the incoming data. (same for Y) | The column was renamed or removed upstream. Pick it again. |
| Y column 'name' must be numeric for sum. | The chosen aggregation needs numbers. Convert the column, or choose Count. |
| X and Y must differ to aggregate. | Choose two different columns. |
| Color by must differ from X and Y. | Choose another column for colour. (A colour column that no longer exists is ignored.) |
| No rows to plot. | The table is empty after the settings are applied. |
| No data to plot. | Nothing could be drawn. |
| Could not build the chart: ... | The data could not be read; the message gives the reason. |

### Tips

- Put a Graph after an Aggregate node so that you chart totals, not raw rows.
- To check amounts for outliers, use Scatter with X = a number or date and Y = amount, with Aggregate = None.
- A chart is a working-paper aid. For a number to quote, use a [Data Profile](#data-profile) or a summary table.

---

## Data Profile

<img src="../../../src/trigger_designer/resources/qt/images/node_icons/Report/Data%20Profile.svg" width="56" alt="Data Profile icon">

### Contents

[Purpose](#purpose-1) | [When to use it](#when-to-use-it-1) | [Inputs and outputs](#inputs-and-outputs-1) | [Settings](#settings-1) | [Reading the profile](#reading-the-profile) | [The profile table (output P)](#the-profile-table-output-p) | [Worked example](#worked-example-1) | [Edge cases and limits](#edge-cases-and-limits-1) | [Messages you may see](#messages-you-may-see-1) | [Tips](#tips-1)

### Purpose

Data Profile describes every column of a table: how many values are empty, how many are distinct, the smallest and largest value, the most common values, whether a text column looks like numbers or dates, and a list of warning flags such as "mixed numbers and text" or "leading zeros". It passes the data through unchanged and also gives you the findings as a table.

### When to use it

- Straight after File Input, to learn what you have been given before you rely on it.
- After cleaning, to confirm the cleaning worked.
- To document the state of the data in the working paper (the profile can be exported).

### Inputs and outputs

| Socket | Carries |
|---|---|
| Input (left) | The table to profile. |
| Output `D` | **Data.** The input, unchanged. |
| Output `P` | **Profile.** One row per column of the input, with the figures described below. |

### Settings

The node's Config Dock shows the profile itself (a toolbar, a table of columns, and a detail panel for the selected column) with a collapsed **Options** section underneath.

**Options** (collapsed by default)

| Control | What it does | Default | Allowed values |
|---|---|---|---|
| **Sample** | Which rows a workflow **Run** profiles: **All rows**, **First N rows**, or **Random N rows**. Hint: "Which rows a workflow run profiles". | All rows | |
| **Rows (N)** | How many rows to profile when Sample is not All rows. | 100,000 | 1,000 to 100,000,000 |
| **Seed** | Shown for Random N rows. The same seed picks the same random rows every run, so a reviewer can repeat your result. | 42 | 0 to 2,147,483,647 |
| **Top values** | How many of the most common values to list per column. | 5 | 1 to 50 |
| **Estimate over** | Above this many rows, distinct counts are estimated (within about 5%) to save time. Estimated counts are shown with a `~`. | 2,000,000 | 10,000 to 2,000,000,000 |
| **Chart bars** | Number of bars in the distribution chart of a number column. | 20 | 5 to 100 |

A value outside its range, or an unknown Sample, is quietly brought back into range when the workflow is opened.

**The profile view**

| Control | What it does |
|---|---|
| **Filter columns** (search box) | Shows only the columns whose names contain the text. |
| **Open the full report (every column) in your browser** (icon) | Writes an HTML report of the profile and opens it in your browser. The temporary file is deleted when you close the app. |
| **Export profile** (icon, menu) | **Copy to clipboard** (tab-separated text), **CSV file...**, **HTML report...**, **Excel workbook...**. |
| **Recompute profile** (icon) | Profiles again. It discards the last Run's profile and re-profiles the rows the canvas holds (the first 100). |
| Status chip | Says which rows the figures describe: `Data: 5 rows`, `Sample: first 100,000 rows`, or `Sample: random 100,000 rows (seed 42)`. Hover for whether it is a live preview or the result of a Run. |

### Reading the profile

The table in the dock has six columns. Click a header to sort by it.

| Column | Meaning |
|---|---|
| **Column** | The column name. |
| **Type** | The type the column has now (for example `String`, `Int64`, `Date`). A CSV read by File Input is all `String`. |
| **Null %** | Share of values that are empty (null), with a small bar. |
| **Distinct** | How many different non-empty values (`~` in front when estimated). |
| **Suggested** | The type the values look like, when it differs from the current type: for example `Float64`, or `Date (99%)` when 99% of the values read as dates. |
| **Flags** | Warnings and notes (below). Hover for the full list. |

Select a row to see its detail panel: a bar chart (the distribution of a number column, or the frequency of the most common values), then figures such as **Null**, **Blank text**, **Stray whitespace**, **Distinct**, **Min / max**, **Mean / median / std**, **Negative values**, **Zeros**, **Length**, and **Look like dates**. For a text column that holds numbers, the figures are worked out from the text read as numbers and are labelled "(parsed from text)".

**Suggested type** is only offered when at least 98% of the non-blank values fit. It checks, in order: whole numbers, decimal numbers (amounts with a trailing minus, decimal commas and thousands separators count as number-like), true/false/yes/no/y/n, dates, then text. A column of whole numbers with leading zeros (`007`) is suggested to stay text, so the zeros are not lost. Recognised date forms are `2025-01-31`, `31/01/2025`, `01/31/2025`, `2025/01/31`, `31-01-2025`, `31.01.2025`, `20250131`, `31-Jan-2025` and `31 Jan 2025`, plus date-times such as `2025-01-31 14:30:00`. A value such as `03/04/2025` can be read two ways, so check your dates.

**Flags**

| Flag shown | Meaning | Tone |
|---|---|---|
| all null | Every value is empty. | warning |
| all blank | Every non-empty value is only spaces. | warning |
| constant | At least two rows, none empty, one distinct value. | note |
| almost all unique | At least 20 values and 95% or more are different (typical for IDs). | note |
| mostly null | 50% or more of the values are empty. | warning |
| mixed numbers and text | A text column where between 2% and 98% of the values read as numbers. | warning |
| mixed dates and text | A text column where half or more, but under 98%, read as dates. | warning |
| leading zeros | Values such as `007` in a column that is mostly whole numbers. | warning |
| trailing minus | Values such as `100-` (a negative number written the old way). | warning |
| decimal comma | More values use a decimal comma (`12,50`) than a decimal point. | warning |
| stray whitespace | Values with spaces at the start or end. | warning |
| numbers stored as text | A text column that is really numbers. | note |
| dates stored as text | A text column that is really dates. | note |
| negative values | A number column (or text that holds numbers) with negative values. | note |
| possible outlier | At least 20 values, and the largest or smallest is 10 or more standard deviations from the mean. | warning |
| NaN values / infinite values | Not-a-number or infinite values in a decimal column. | warning |

"Note" flags are normal for many files (every number in a CSV is "numbers stored as text"). "Warning" flags deserve a look and are drawn more strongly.

### The profile table (output P)

Output `P` has one row per input column and these columns, in this order. Empty cells are null.

| Group | Columns |
|---|---|
| Identity | `column`, `position`, `dtype` |
| Emptiness | `row_count`, `null_count`, `null_pct`, `empty_count`, `empty_pct`, `blank_count`, `whitespace_count` |
| Distinct | `distinct_count`, `distinct_is_approx`, `distinct_pct` |
| Range | `min_value`, `max_value`, `min_length`, `max_length` |
| Numbers | `mean_value`, `median_value`, `std_value`, `sum_value`, `min_numeric`, `max_numeric`, `numeric_basis` (`native` for number columns, `parsed_text` for text that holds numbers), `negative_count`, `zero_count`, `nan_count`, `inf_count` |
| What text looks like | `numeric_like_count`, `integer_like_count`, `date_like_count`, `bool_like_count`, `leading_zero_count`, `trailing_minus_count`, `decimal_comma_count` |
| Common values | `top_values` (JSON text of value and count pairs), `top_value`, `top_count`, `histogram` (JSON list of bar heights) |
| Verdict | `suggested_type`, `suggested_confidence`, `flags` (comma-separated internal names such as `numeric_as_text,leading_zeros`), `sampled` (true when only some rows were profiled) |

Pass `P` to File Output, to a Filter (for example, keep rows whose `flags` contain `mixed_numeric_text`) or on to the working paper.

### Worked example

Input (read from a CSV, so every column is text except `Qty`):

| Invoice | Amount | Date | Code | Qty | Status |
|---|---|---|---|---|---|
| INV-001 | 100.50 | 2025-01-03 | 007 | 1 | Open |
| INV-002 | 2000 | 2025-01-04 | 012 | 2 | Open |
| INV-003 | 75.40 | 2025-01-05 | 003 | -1 | Open |
| INV-004 | 310 | 2025-01-06 | 099 | 4 | Open |
| INV-005 | (empty) | 2025-01-07 | 010 | 4 | Open |

Output `D` is this table, unchanged. Output `P` (the main columns):

| column | dtype | null_pct | distinct_count | min_value | max_value | suggested_type | flags | top_value |
|---|---|---|---|---|---|---|---|---|
| Invoice | String | 0.0 | 5 | INV-001 | INV-005 | String | | INV-001 |
| Amount | String | 20.0 | 4 | 75.4 | 2000 | Float64 | numeric_as_text | 100.50 |
| Date | String | 0.0 | 5 | 2025-01-03 | 2025-01-07 | Date | date_as_text | 2025-01-03 |
| Code | String | 0.0 | 5 | 003 | 099 | String | leading_zeros | 003 |
| Qty | Int64 | 0.0 | 4 | -1 | 4 | Int64 | negative_values | 4 |
| Status | String | 0.0 | 1 | Open | Open | String | constant | Open |

How to read it: `Amount` is numbers stored as text, with the range 75.4 to 2000 (worked out from the text) and one empty value (20%); its mean is 621.475. `Date` is dates stored as text. `Code` has leading zeros, so convert it as text, not as a number. `Qty` has a negative value you may want to explain. `Status` is the same in every row.

### Edge cases and limits

- **Live preview vs Run.** While you edit, the profile covers only the rows the canvas holds, **the first 100**, and the status chip says so ("Live preview of the rows the canvas holds (the first 100). Run the workflow to profile all rows."). After you press Run, the dock shows the full-data profile, labelled as the result of the run with its time, until you change a setting or press Recompute. The **Sample** settings only take effect in a Run. See [Live preview and Run](input-output.md#live-preview-and-run).
- **Wide tables.** The live preview is skipped for tables with more than 150 columns (the dock says "N columns: the live preview is skipped so the editor stays responsive. Run the workflow to profile every column."). A Run profiles every column.
- **Large tables.** There is no row limit. Distinct counts are estimated above the **Estimate over** threshold. Use **First N rows** or **Random N rows** to profile a sample of a very large table.
- **Random sample.** The node counts the rows first, then picks N row positions. The same seed on the same data gives the same rows.
- **Long text.** Minimum, maximum and common values longer than 100 characters are cut to 100 (ending with an ellipsis).
- **Nested columns** (lists, records) and binary columns get only the empty count; no distinct count or common values.
- **Zero columns** shows "No columns".
- **Stable numbers.** Mean, median, standard deviation and sum are rounded to 12 significant digits so the same data gives the same profile on every run.
- **Empty versus blank.** For text columns, "empty" means no text at all, "blank" means only spaces, and null means missing. They are counted separately.

### Messages you may see

| Message | Meaning and fix |
|---|---|
| Profiling... | The profile is being calculated. |
| Live preview skipped | The table has more than 150 columns. Run the workflow instead. |
| Profile failed: ... | The profile could not be calculated; the reason follows. Check the upstream node. |
| Nothing to copy yet / Nothing to export yet / Nothing to show yet | There is no profile to copy or export yet. |
| Copied N rows / Exported N rows to CSV / Exported N rows to Excel / Exported HTML report | The action finished. |
| Export failed: ... | The file could not be written (for example, it is open in another program), or, for Excel, the Excel writer is not installed ("Excel export is unavailable"). Close the file, choose another name, or export CSV or HTML. |
| Could not write the report / Could not open the report | The full report could not be created or opened in your browser. |
| `TD-SHAPE-005` | The input has no data. Connect and fix the upstream node. |

### Tips

- Put a Data Profile right after each File Input and look at **Flags** first. "Mixed numbers and text" and "leading zeros" are the two that most often change an audit result.
- Compare profiles before and after a Cleansing or Select node to show that the cleaning did what you said.
- Export the HTML report for the working paper. It lists every column.
- For a repeatable result, use **All rows**, or **Random N rows** with a fixed seed, and note the seed.

---

## Comment

<img src="../../../src/trigger_designer/resources/qt/images/node_icons/Report/Comment.svg" width="56" alt="Comment icon">

### Contents

[Purpose](#purpose-2) | [When to use it](#when-to-use-it-2) | [Inputs and outputs](#inputs-and-outputs-2) | [Settings](#settings-2) | [Worked example](#worked-example-2) | [Edge cases and limits](#edge-cases-and-limits-2) | [Errors you may see](#errors-you-may-see) | [Tips](#tips-2)

### Purpose

A Comment is a note on the canvas. It never runs, has no inputs or outputs, and has no effect on the data. Its text is saved with the workflow.

### When to use it

- Explain why a filter or a tolerance was chosen ("tolerance 0.50 agreed with client, see email of 3 March").
- Mark a step as "to be reviewed", or leave a question for the reviewer.
- Describe a group of nodes.

### Inputs and outputs

None. A Comment has no sockets, so it cannot be connected to other nodes. Its summary in the dock reads "0 inputs · 0 outputs · never runs".

### Settings

| Control | What it does | Default |
|---|---|---|
| **Note** (a large text box, placeholder "Note for the reviewer") | The text of the comment, as many lines as you like. Tooltip: "The first line is shown above the node." | Empty |

The first non-blank line of the note, cut to its first 60 characters, is shown as a label above the node on the canvas, so the canvas stays readable. The rest of the text is only visible when you select the node.

Editing a Comment does not make the workflow re-evaluate and does not mark anything as out of date.

### Worked example

You type:

```
Tolerance of 0.50 agreed with the client
Source: bank rec policy, section 4
```

The node shows `Tolerance of 0.50 agreed with the client` above it. Select the node to read both lines.

### Edge cases and limits

- **Label length.** Only the first 60 characters of the first line are shown on the canvas. The note itself is not limited.
- **Empty note.** No label is shown.
- **Running a workflow** does nothing for a Comment: its generated code is only the line `# Comment (not executed)`.
- **Privacy.** The note is stored in the workflow file as plain text. Do not put confidential details in a workflow you will share outside the team.

### Errors you may see

None. A Comment cannot fail.

### Tips

- Start the note with a short title on the first line; that line is what people see on the canvas.
- Place one Comment above each group of nodes that does one job (for example "Step 2: match bank to ledger").
