# Data Profile

![Data Profile icon](../../assets/node_icons/Report/Data%20Profile.svg){ .node-icon }

## Purpose

Data Profile describes every column of a table: how many values are empty, how many are distinct, the smallest and largest value, the most common values, whether a text column looks like numbers or dates, and a list of warning flags such as "mixed numbers and text" or "leading zeros". It passes the data through unchanged and also gives you the findings as a table.

## When to use it

- Straight after File Input, to learn what you have been given before you rely on it.
- After cleaning, to confirm the cleaning worked.
- To document the state of the data in the working paper (the profile can be exported).

## Inputs and outputs

| Socket | Carries |
|---|---|
| Input (left) | The table to profile. |
| Output `D` | **Data.** The input, unchanged. |
| Output `P` | **Profile.** One row per column of the input, with the figures described below. |

## Settings

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

## Reading the profile

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

## The profile table (output P)

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

## Worked example

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

## Edge cases and limits

- **Live preview vs Run.** While you edit, the profile covers only the rows the canvas holds, **the first 100**, and the status chip says so ("Live preview of the rows the canvas holds (the first 100). Run the workflow to profile all rows."). After you press Run, the dock shows the full-data profile, labelled as the result of the run with its time, until you change a setting or press Recompute. The **Sample** settings only take effect in a Run. See [Live preview and Run](../input-output/index.md#live-preview-and-run).
- **Wide tables.** The live preview is skipped for tables with more than 150 columns (the dock says "N columns: the live preview is skipped so the editor stays responsive. Run the workflow to profile every column."). A Run profiles every column.
- **Large tables.** There is no row limit. Distinct counts are estimated above the **Estimate over** threshold. Use **First N rows** or **Random N rows** to profile a sample of a very large table.
- **Random sample.** The node counts the rows first, then picks N row positions. The same seed on the same data gives the same rows.
- **Long text.** Minimum, maximum and common values longer than 100 characters are cut to 100 (ending with an ellipsis).
- **Nested columns** (lists, records) and binary columns get only the empty count; no distinct count or common values.
- **Zero columns** shows "No columns".
- **Stable numbers.** Mean, median, standard deviation and sum are rounded to 12 significant digits so the same data gives the same profile on every run.
- **Empty versus blank.** For text columns, "empty" means no text at all, "blank" means only spaces, and null means missing. They are counted separately.

## Messages you may see

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

## Tips

- Put a Data Profile right after each File Input and look at **Flags** first. "Mixed numbers and text" and "leading zeros" are the two that most often change an audit result.
- Compare profiles before and after a Cleansing or Select node to show that the cleaning did what you said.
- Export the HTML report for the working paper. It lists every column.
- For a repeatable result, use **All rows**, or **Random N rows** with a fixed seed, and note the seed.


Back to the [Report node index](index.md).
