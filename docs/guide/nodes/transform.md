# Transform nodes

The **Transform** tab holds seven nodes that change the *shape* of a table: count it, add running
totals, turn columns into rows (or rows into columns), compare each row with its neighbours, or
rewrite the whole table with SQL. The other families are in the [node index](README.md).

| Icon | Node | Use it to | Page section |
|---|---|---|---|
| ![Count](../../../src/trigger_designer/resources/qt/images/node_icons/Transform/Count.svg) | **Count** | Count the rows of a table | [Count](#count) |
| ![Running Total](../../../src/trigger_designer/resources/qt/images/node_icons/Transform/Running%20Total.svg) | **Running Total** | Add a cumulative sum, optionally per account or branch | [Running Total](#running-total) |
| ![Transpose](../../../src/trigger_designer/resources/qt/images/node_icons/Transform/Transpose.svg) | **Transpose** | Turn month or period columns into rows | [Transpose](#transpose) |
| ![Pivot](../../../src/trigger_designer/resources/qt/images/node_icons/Transform/Pivot.svg) | **Pivot** | Turn the values of one column into columns, with totals | [Pivot](#pivot) |
| ![Unpivot](../../../src/trigger_designer/resources/qt/images/node_icons/Transform/Unpivot.svg) | **Unpivot** | Stack several columns into a name and a value | [Unpivot](#unpivot) |
| ![Window](../../../src/trigger_designer/resources/qt/images/node_icons/Transform/Window.svg) | **Window** | Previous or next row, row number, rank, running or rolling sums | [Window](#window) |
| ![SQL Query](../../../src/trigger_designer/resources/qt/images/node_icons/Transform/SQL%20Query.svg) | **SQL Query** | Write one read-only SELECT over up to three tables | [SQL Query](#sql-query) |

All seven icons are purple, the colour of the Transform family.

> **Arrange is not a node.** You may see "Arrange" mentioned next to the Transform family in older notes. It
> is the canvas *Arrange* menu (align and distribute the nodes you selected), not something you put in a
> workflow.

## How these nodes behave

**A node runs when you leave its settings.** Edits in the Config Dock are saved at once, but the Transform
nodes recalculate only when you click another node, click the canvas, save or run. Until then the node shows
a yellow "!" badge (tooltip "Changes pending - the node runs when you click away"). See
[Live preview versus Run](README.md#live-preview-versus-run).

**The preview uses 100 rows.** While you edit, each Transform node works on the first 100 rows of its input
and shows at most 100 output rows. A **Run** uses every row. So a Count in the preview can only say "100", a
Pivot may be missing a header that appears later in the file, and a running total only covers the sample.
Check the full result after a Run: the Data Preview dock labels a table *evaluated · not run* (preview) or
*from Run*.

**Column types.** A CSV or text file arrives with every column as text. Pivot, Window and SQL Query can read
text that holds numbers; Running Total cannot (see its section). Use a *Select* node to change a column's type.

**Errors.** A mistake in the settings turns the node red. The Problems dock shows a short message, a hint
and a code. The codes you can meet in this family:

| Code | Message | What to do |
|---|---|---|
| `TD-SHAPE-001` | A required setting is missing | Fill it in (for example, the header column of a Pivot) |
| `TD-SHAPE-002` | An output column name is empty, duplicated or already exists | Choose a unique name |
| `TD-SHAPE-003` | A selected column is not in the input any more | Select the column again; it was renamed or removed upstream |
| `TD-SHAPE-004` | A setting value is out of range or unknown | Pick a value inside the range |
| `TD-SHAPE-005` | A required input has no data | Connect the input and fix the upstream node ("Input 1 has no data") |
| `TD-SHAPE-060` | Index, header and value columns must be different | Pick three different columns (Pivot); a column cannot be both kept and unpivoted (Unpivot) |
| `TD-SHAPE-061` | Too many new columns | The Pivot header has more than 500 distinct values; filter first |
| `TD-SHAPE-091` | The column must be a number | Pick a numeric column, or text that holds numbers (Window) |
| `TD-SHAPE-110` to `-115` | SQL guard messages | See [SQL Query](#sql-query) |

---

## Count

![Count](../../../src/trigger_designer/resources/qt/images/node_icons/Transform/Count.svg)

**Purpose.** Counts the rows of a table and returns the number as a one-row table.

**When to use it.** To reconcile record counts: "does the file have the 4,812 rows the system report
says?" Put it after File Input, or after a Filter to count the matches. For a count per group (rows per
vendor), use *Aggregate* in the Preparation family instead; Count has no grouping.

**Inputs and outputs.** One input. One output, labelled `Out`, with a single column `Count` (a whole number).

**Settings.** None. The Config Dock only says "No configuration. The output socket carries the row count."

**Worked example.** Input of 5 rows (Account, Date, Amount):

| Account | Date | Amount |
|---|---|---|
| A | 2025-01-01 | 100.0 |
| A | 2025-01-02 | -30.0 |
| B | 2025-01-01 | 50.0 |
| B | 2025-01-03 | 25.0 |
| B | 2025-01-04 | -75.0 |

Output:

| Count |
|---|
| 5 |

**Edge cases and limits.**

- In the live preview the node counts only the sample and shows a warning chip, "First 100 rows only: full
  count at Run". Never quote the preview number. After a **Run** the count covers all rows.
- An empty input gives `Count` 0, not an error.
- An unconnected input gives `TD-SHAPE-005`.

**Tip.** Connect Count to a *File Output* to keep the figure in your working papers.

---

## Running Total

![Running Total](../../../src/trigger_designer/resources/qt/images/node_icons/Transform/Running%20Total.svg)

**Purpose.** Adds a cumulative sum of one or more number columns, optionally restarting for each group.

**When to use it.** To build a running balance from a transaction list, or to see when a cumulative total
crosses a threshold. For other running figures (minimum, maximum, average, rolling windows) use *Window*.

**Inputs and outputs.** One input. One output, labelled `Out`: every input column in the same order, then one new column
per chosen sum column.

**Settings, in dock order** (section *Running totals*):

| Label | Default | Effect |
|---|---|---|
| **Sum** | none chosen | The number columns to total. Only columns that are already numbers are offered. Each one adds a column named `RunTot_<column>`. |
| **Group by** | none chosen | The columns that define a group (account, branch). The total restarts at each new value. With none chosen, one total runs down the whole table. |

**Worked example.** Sum `Amount`, Group by `Account`, on the table above:

| Account | Date | Amount | RunTot_Amount |
|---|---|---|---|
| A | 2025-01-01 | 100.0 | 100.0 |
| A | 2025-01-02 | -30.0 | 70.0 |
| B | 2025-01-01 | 50.0 | 50.0 |
| B | 2025-01-03 | 25.0 | 75.0 |
| B | 2025-01-04 | -75.0 | 0.0 |

With no Group by, the last column reads 100, 70, 120, 145, 70.

**Edge cases and limits.**

- **Row order matters.** The total accumulates in the order the rows arrive. Sort first (a *Sort* node) if you
  want it in date order. Rows are never reordered.
- **Text columns are not offered.** A CSV has no number columns until you convert them, so the Sum list may
  look empty. Convert the column with a *Select* node, or use Window's *Running sum*, which reads text as numbers.
- With no Sum column chosen, the node passes the table through unchanged (no error).
- An empty cell stays empty in the new column and the total carries on past it (1, empty, 3 gives 1, empty, 4).

**Tip.** The name is fixed (`RunTot_<column>`); rename it afterwards with *Select*.

---

## Transpose

![Transpose](../../../src/trigger_designer/resources/qt/images/node_icons/Transform/Transpose.svg)

**Purpose.** Turns chosen columns into rows: every data column becomes a set of `Name` / `Value` rows, and the
key columns repeat on each. (It does not flip the whole table; if you want one row per key and a column per value,
use Pivot.)

**When to use it.** A trial balance or budget with one column per month (Jan, Feb, Mar) is hard to filter,
chart or join. Transpose it into one row per branch and month.

**Inputs and outputs.** One input. One output, labelled `Out`: the key columns, then `Name` (the old column name) and `Value`.

**Settings, in dock order** (section *Transpose*):

| Label | Default | Effect |
|---|---|---|
| **Key columns** | none | Columns that identify the row (branch, account). They are repeated on every output row. |
| **Data columns** | none | The columns to turn into rows. With none chosen the table passes through unchanged. |
| **If columns are missing** | Warn and skip | What to do when a chosen data column no longer exists. *Warn and skip* and *Ignore* both leave the missing column out of the result; *Warn and skip* also shows a "data column(s) missing" chip (and a "key column(s) missing" chip), *Ignore* shows no chip. *Error* stops the node with `TD-SHAPE-003`. |

**Worked example.** Key `Branch`, data `Jan`, `Feb`, `Mar`:

| Branch | Jan | Feb | Mar |
|---|---|---|---|
| North | 10 | 15 | |
| South | 20 | 25 | 30 |

becomes

| Branch | Name | Value |
|---|---|---|
| North | Jan | 10 |
| South | Jan | 20 |
| North | Feb | 15 |
| South | Feb | 25 |
| North | Mar | (empty) |
| South | Mar | 30 |

**Edge cases and limits.**

- Output is one block per data column, in the order you ticked them, and in input row order inside each block.
- Empty cells are kept as empty `Value` rows. Filter them afterwards if you do not want them.
- If the data columns have different types (numbers and text), `Value` becomes text.
- If every data column is missing, the table passes through unchanged. Missing *key* columns only raise a chip (none under *Ignore*).

**Tip.** Unpivot does the same job with more control (it names the two new columns and can drop empty
values). Use Transpose for a quick reshape, Unpivot when you need the names.

---

## Pivot

![Pivot](../../../src/trigger_designer/resources/qt/images/node_icons/Transform/Pivot.svg)

**Purpose.** Turns the distinct values of one column into new columns, and summarises a value column in each.
This is the Excel PivotTable layout: row labels down the side, headers across the top.

**When to use it.** Amount by vendor and month; count of journals by user and posting period; a quick matrix of
two categories.

**Inputs and outputs.** One input, one output (no letter): the Row labels columns, then one column per distinct header value.

**Settings, in dock order:**

*Layout*

| Label | Default | Effect |
|---|---|---|
| **Row labels** | none | Columns that become the rows (several allowed). With none chosen, the result is a single row. |
| **Headers** | none | The column whose values become the new column names. Required. |
| **Values** | none | The column that is summarised in each cell. Required. |

*Aggregation*

| Label | Default | Effect |
|---|---|---|
| **Function** | Sum | How several rows in one cell are combined: Sum, Mean, Min, Max, Median, First, Last or Count. |
| **Empty cells** | Blank | A cell with no data shows blank (*Blank*) or 0 (*Zero*). |

*Naming & limits* (collapsed; open it to change)

| Label | Default | Effect |
|---|---|---|
| **Blank header** | `(blank)` | The column name used for rows whose header cell is empty. |

**Worked example.** Row labels `Vendor`, Headers `Month`, Values `Amount`, Function Sum. Amount arrives as text, as it does from a CSV:

| Vendor | Month | Amount |
|---|---|---|
| Acme | Jan | 100 |
| Acme | Feb | 200 |
| Acme | Jan | 50 |
| Beta | Jan | 75 |
| Beta | Mar | (empty) |

| Vendor | Feb | Jan | Mar |
|---|---|---|---|
| Acme | 200.0 | 150.0 | |
| Beta | | 75.0 | |

With *Empty cells* = Zero, every blank cell becomes 0.0. With Function = Count, the result is Acme: Feb 1,
Jan 2; Beta: Jan 1, Mar 0.

**Edge cases and limits.**

- **Columns are sorted by name**, not by the order they appear (Feb, Jan, Mar above). Number the headers
  (`01 Jan`, `02 Feb`) if you need calendar order, or reorder with *Select* afterwards.
- Sum, Mean, Min, Max and Median read text as numbers (commas are removed; text that is not a number is
  ignored). First, Last and Count work on any column and Count counts non-empty values.
- A Sum of cells that are all empty is empty, not 0.
- Count shows 0 for a header that exists for that row (a row with only empty values), and blank when no row
  has that combination. Choose *Zero* to show 0 everywhere.
- **Limit: 500 columns.** More than 500 distinct header values stops the node with `TD-SHAPE-061`. Filter or group first.
- Row labels, Headers and Values must be three different columns (`TD-SHAPE-060`). Headers and Values are required (`TD-SHAPE-001`).
- Rows are sorted by the Row labels, empty labels last.
- Pivot must see the data to know the headers. In the preview it sees only 100 rows, so some headers may be missing
  until you Run.

**Tip.** To total by two keys across two headers (vendor by month by entity), add a *Formula* that joins them
into one header column first.

---

## Unpivot

![Unpivot](../../../src/trigger_designer/resources/qt/images/node_icons/Transform/Unpivot.svg)

**Purpose.** Stacks several columns into two: the name of the column and its value. It is the opposite of
Pivot.

**When to use it.** Data laid out as one column per month, per account or per test result, when you need one row
per measurement to filter, aggregate, chart or join.

**Inputs and outputs.** One input, one output (no letter): the kept columns, then the name column, then the value column.

**Settings, in dock order:**

*Shape*

| Label | Default | Effect |
|---|---|---|
| **Keep** | none | Columns that identify the row and are repeated on every output row. |
| **Unpivot** | none | The columns to stack. At least one is required (`TD-SHAPE-001`). A column cannot be in both lists (`TD-SHAPE-060`). |

*Output columns*

| Label | Default | Effect |
|---|---|---|
| **Name column** | `Attribute` | Name of the new column holding the old column names. |
| **Value column** | `Value` | Name of the new column holding the values. |
| **Drop empty values** | off | Off keeps rows whose value is empty; on removes them. |

**Worked example.** Keep `Vendor`, Unpivot `Jan`, `Feb`, `Mar`, Name column `Month`, Value column `Amt`, Drop empty values on:

| Vendor | Jan | Feb | Mar |
|---|---|---|---|
| Acme | 100 | 200 | |
| Beta | 75 | | 30 |

| Vendor | Month | Amt |
|---|---|---|
| Acme | Jan | 100 |
| Acme | Feb | 200 |
| Beta | Jan | 75 |
| Beta | Mar | 30 |

With Drop empty values off, Acme/Mar and Beta/Feb are also there, with an empty `Amt`.

**Edge cases and limits.**

- The two new names must be different, not empty, and not the same as a kept column (`TD-SHAPE-002`).
- Rows stay grouped by input row (all of Acme's months, then Beta's), columns in the order you ticked them.
- If the stacked columns have different types, they are converted to one: all numbers become decimals
  (100 becomes 100.0), anything else becomes text ("Mixed types are cast to text").
- The output has (rows x stacked columns) rows. Stacking 12 columns of a 100,000-row file makes 1.2 million rows.

**Tip.** After an Unpivot, an *Aggregate* by the name column gives you totals per old column.

---

## Window

![Window](../../../src/trigger_designer/resources/qt/images/node_icons/Transform/Window.svg)

**Purpose.** Adds one new column per calculation that compares a row with the rows around it: the previous or
next value, a row number, a rank, a running sum, minimum, maximum or mean, or a rolling sum over the last few rows.
The rows stay in their input order.

**When to use it.** Days between one posting and the previous one (previous value, then the days between with a
*Date Helper*); number the lines in each journal; rank invoices by amount within each vendor; detect a balance that
jumps from the one before.

**Inputs and outputs.** One input, one output (no letter): every input column, then the new columns.

**Settings, in dock order:**

*Window*

| Label | Default | Effect |
|---|---|---|
| **Restart per** | none | Columns that define a group. Every calculation starts again for each group. None means the whole table is one group. |
| **Order by** | none | One or more rows of **Column** and **Descending**. This decides which row is "previous", "next", first or last. It does **not** reorder the output. With none, the input order is used. |

*Calculations* (a list; add as many as you need; each card shows only the fields its calculation uses)

| Label | Default | Effect |
|---|---|---|
| **Calculation** | Previous row (lag) | One of the ten calculations below. |
| **Output name** | Auto | Name of the new column. Leave empty to get the automatic name below. It must be different from every existing column (`TD-SHAPE-002`). |
| **Column** | none | The column to calculate on. Not shown for *Row number*. Required (`TD-SHAPE-001`). |
| **Offset** | 1 | Previous/Next row only: how many rows back or ahead (at least 1). |
| **Window rows** | 3 | Rolling sum only: how many rows are summed (at least 1). |
| **Allow partial window** | off | Rolling sum only: on gives a value for the first rows from the rows available; off leaves them empty until the window is full. |
| **Rank high to low** | off | Rank and Dense rank only: on gives rank 1 to the largest. |
| **Nulls** | Skip | Running sum, min, max, mean and rolling sum: *Skip* leaves an empty cell empty; *Treat as 0* counts it as 0. |

| Calculation | New column | What it holds |
|---|---|---|
| Previous row (lag) | `<column>_lag<offset>` | The value from `offset` rows earlier in the group; empty for the first rows |
| Next row (lead) | `<column>_lead<offset>` | The value from `offset` rows later |
| Row number | `Row_Number` | 1, 2, 3 ... in order within the group |
| Rank | `<column>_rank` | Rank; equal values share a rank and the next rank is skipped (1, 1, 3) |
| Dense rank | `<column>_dense_rank` | As Rank without skipping (1, 1, 2) |
| Running sum / min / max / mean | `<column>_cum_sum`, `_cum_min`, `_cum_max`, `_cum_mean` | The cumulative figure from the first row of the group to this row |
| Rolling sum | `<column>_roll<window>` | The sum of the last `window` rows |

**Worked example.** Restart per `Account`, Order by `Date` (A to Z). Calculations: Row number; Previous row on
`Amount`; Running sum on `Amount`; Rank on `Amount` with *Rank high to low*. Input (Amount arrives as text):

| Account | Date | Amount |
|---|---|---|
| A | 2025-01-03 | 100 |
| A | 2025-01-01 | 40 |
| A | 2025-01-02 | 60 |
| B | 2025-01-01 | 25 |
| B | 2025-01-02 | 10 |

| Account | Date | Amount | Row_Number | Amount_lag1 | Amount_cum_sum | Amount_rank |
|---|---|---|---|---|---|---|
| A | 2025-01-03 | 100 | 3 | 60 | 200.0 | 1 |
| A | 2025-01-01 | 40 | 1 | | 40.0 | 3 |
| A | 2025-01-02 | 60 | 2 | 40 | 100.0 | 2 |
| B | 2025-01-01 | 25 | 1 | | 25.0 | 1 |
| B | 2025-01-02 | 10 | 2 | 25 | 35.0 | 2 |

The rows are still in input order; the Date ordering decided that 2025-01-01 is the first row of account A.
A Rolling sum over 2 rows with *Allow partial window* on adds `Amount_roll2`: 160, 40, 100 for account A and
25, 35 for account B. With it off, the first row of each account in date order is empty (for account A the column reads 160,
empty, 100).

**Edge cases and limits.**

- Rank, Dense rank and the running and rolling calculations read text as numbers (commas removed; other text
  becomes empty). Previous and Next work on any column and keep its type. Choosing a column that is neither text nor a number gives `TD-SHAPE-091`.
- Every Order by row needs a column (`TD-SHAPE-001`); an offset or window below 1 gives `TD-SHAPE-004`.
- Running mean divides by the number of non-empty values so far.
- Text dates sort correctly only when written year-month-day (`2025-01-03`). `03/01/2025` sorts as text.
- With no calculation in the list, the table passes through unchanged.

**Tip.** Equal order keys keep input order, so the result is repeatable.

---

## SQL Query

![SQL Query](../../../src/trigger_designer/resources/qt/images/node_icons/Transform/SQL%20Query.svg)

**Purpose.** Runs one SQL `SELECT` over up to three tables and returns its result. It is the escape hatch for
reshapes that the other nodes do not cover: joins with several conditions, subqueries, window functions,
`CASE` logic, set operations.

**When to use it.** When you already think in SQL, or the same job would take five nodes. Prefer the dedicated
nodes (Filter, Join, Aggregate) for simple steps: they are easier to review.

**Inputs and outputs.** Three inputs, top to bottom: **t1** (required), **t2** and **t3** (optional). One output (no letter).
Inside the query the connected inputs are the tables `t1`, `t2` and `t3`, by position. The summary line in the dock reads "t1 required · t2, t3 optional".

**Settings.** One section, *Query*:

| Label | Default | Effect |
|---|---|---|
| **SQL** | `SELECT *` on the next line `FROM t1` | The query. The editor has syntax colours and completes the table and column names. An error line under the editor shows the first problem, found by checking the query against empty copies of your tables, without reading your data. |

The note under the editor reads: "One read-only SELECT. Connected inputs are the tables t1, t2 and t3 (t2 and t3 are optional). Files and random functions are blocked."

**What you can write.** One statement that is a `SELECT`, `WITH` (common table expressions), `FROM ...`
(DuckDB shorthand), `VALUES` or `TABLE`, or one wrapped in brackets. Inside it, anything DuckDB's SQL offers:
joins, `GROUP BY`, `CASE`, window functions (`OVER`), subqueries, `UNION`, `ORDER BY`, `LIMIT`,
`USING SAMPLE`, string, date and maths functions. A closing `;` is fine and comments (`--`, `/* */`) are allowed.
Names are not case-sensitive; put a column name that contains spaces in double quotes, for example `"Posting Date"`.
Only the SQL is checked, not your result: add `ORDER BY` if row order matters, because SQL does not promise
an order without it.

**What is rejected.** Every query passes a guard before it runs, and again each time it runs. It rejects:

| Code | Message you will see | Cause |
|---|---|---|
| `TD-SHAPE-001` | SQL is empty | Nothing in the editor |
| `TD-SHAPE-110` | Only one statement is allowed | A `;` followed by a second statement |
| `TD-SHAPE-111` | Only SELECT queries are allowed | `INSERT`, `UPDATE`, `DELETE`, `CREATE`, `DROP`, `PRAGMA`, `DESCRIBE`, `EXPLAIN`, `COPY`, `ATTACH`, `SET`, `INSTALL` and the like |
| `TD-SHAPE-112` | This function is not allowed (files, system or random) | File readers (`read_csv`, `read_parquet`, any `read_...`, `glob`, any `..._scan`, `sniff_csv`), system functions (`duckdb_...`, `pragma_...`, `current_setting`, `getenv`, `query`), and random ones (`random`, `uuid`, `gen_random_uuid`, `setseed`) |
| `TD-SHAPE-112` | Reading files is not allowed | `FROM 'data.csv'` or a table name that looks like a path |
| `TD-SHAPE-112` | Dollar-quoted and escape strings are not allowed | `$$text$$` and `E'text'` strings; also control characters |
| `TD-SHAPE-113` | SQL could not be parsed: ... or the engine's own message | A typo, an unknown table or column (for example `Table with name t2 does not exist!` when t2 is not connected), a wrong function argument |
| `TD-SHAPE-114` | SQL is longer than 20,000 characters | Query too long |
| `TD-SHAPE-115` | Query took longer than 25 s | The query ran too long and was stopped; filter the data first or simplify the query |

The query runs in a sealed, in-memory copy of the engine with no access to files or the network, on
single-threaded settings and with a 2 GB memory limit. It can read only `t1`, `t2` and `t3` and cannot change
anything on disk or your original data. An unconnected `t1` gives `TD-SHAPE-005` ("Input 1 has no data").
`now()` and similar clock functions are allowed, so a query that uses them can give different results each run.

**Worked example.** `t1` is a payments list, `t2` is a department list:

| Vendor | Amount | Dept |
|---|---|---|
| Acme | 100 | 1 |
| Acme | 250.5 | 2 |
| Beta | 75 | 1 |

| Dept | DeptName |
|---|---|
| 1 | Sales |
| 2 | Ops |

```sql
SELECT d.DeptName,
       COUNT(*) AS n,
       SUM(TRY_CAST(t1.Amount AS DOUBLE)) AS total
FROM t1
JOIN t2 AS d ON t1.Dept = d.Dept
GROUP BY d.DeptName
ORDER BY d.DeptName
```

| DeptName | n | total |
|---|---|---|
| Ops | 1 | 250.5 |
| Sales | 2 | 175.0 |

**The text-column trap (TRY_CAST).** A CSV arrives with every column as text, so `Amount` above is text.

- `SUM(Amount)` on a text column fails with `TD-SHAPE-113` ("No function matches the given name and argument
  types 'sum(VARCHAR)'. You might need to add explicit type casts"). Cast it first.
- `TRY_CAST(Amount AS DOUBLE)` turns text into a number, and **silently gives empty for anything it cannot read**
  instead of an error. It reads `1250.50` and ` 42 ` but **not** `1,234.50`, `(500)`, `$75`, `abc` or an empty
  cell. In a test column of `1250.50`, `1,234.50`, `(500)`, `$75`, `abc`, an empty cell and ` 42 `,
  `SUM(TRY_CAST(Amount AS DOUBLE))` returns 1292.5, and only 2 of the 7 rows were readable: five were dropped
  without a message. Always compare `COUNT(*)` with `COUNT(TRY_CAST(Amount AS DOUBLE))` to see how many were lost,
  or clean the column first with a *Cleansing* or *Find and Replace* node.
- Cast to `DOUBLE` or `DECIMAL(18,2)`, not `INTEGER`: `TRY_CAST('250.5' AS INTEGER)` is 251, a rounded figure.
- Plain `CAST(x AS DOUBLE)` stops the whole query with `TD-SHAPE-113` on the first unreadable value. Use it when
  you want to be told.

**Edge cases and limits.**

- In the live preview the query sees the first 100 rows of each table, so totals and counts are for the sample.
  Run the workflow for the real result. The sealed engine, the guard and the 25 s time limit apply to both.
- The output column types are chosen by the query; unusual types are converted to the ones the rest of the app
  supports (text, whole numbers, decimals, true/false, dates).
- If a query returns no rows, the node returns an empty table with the right columns.

**Tip.** Start from `SELECT * FROM t1`, run it, then build up. The editor's error line catches typos before you
click away. Keep the query short and put the business rule in a comment (`-- exclude reversals`): it is
saved in the workflow and in the run record.
