# Filter

![Filter icon](../../assets/node_icons/Preparation/Filter.svg){ .node-icon }

## Purpose

Splits a table into the rows that meet a condition and the rows that do not. Nothing is deleted: both groups come out, on two sockets.

## When to use it

Isolate high-value transactions, pull out one vendor, separate postings outside a date window, or list the rows that fail a rule.

## Inputs and outputs

| Socket | Carries |
|---|---|
| Input | The table to filter |
| **T** (true) | Rows where the condition is true |
| **F** (false) | Every other row, including rows where the condition could not be decided (empty cells) |

T and F together always contain every input row exactly once.

## Settings

A switch at the top picks the mode.

| Control | Default | Effect |
|---|---|---|
| **Simple / Expression** switch | Simple | Simple builds one condition on one column. Expression takes a SQL condition. |

*Simple mode*

| Control | Default | Effect |
|---|---|---|
| **Column** | "(select column)" | The column to test. A saved column that is no longer in the input is shown as "name (missing)". |
| **Operation** | Equals | The list depends on the column's type (below). |
| **Value** | empty (placeholder "Enter filter value...") | The value to compare with. |
| **Max value** | empty (placeholder "Enter max value...") | Shown only for **In Between**: the upper bound. |

| Column type | Operations offered |
|---|---|
| Text | Equals, Not Equals, Contains |
| Number | Equals, Not Equals, Less Than, Greater Than, Less Than or Equal, Greater Than or Equal, In Between |
| Date or time (real dates, not text) | the same list as numbers (see the edge cases) |
| Other (for example yes/no) | Equals, Not Equals |

*Expression mode*

| Control | Default | Effect |
|---|---|---|
| SQL editor (placeholder: `Filter rows with SQL, e.g.:` / `[order_value] in_between (0, 500) AND [status] = 'paid'`) | empty | A SQL condition; see [Writing SQL expressions](index.md#writing-sql-expressions). Errors show under the editor as you type. |

If the condition is empty (Simple mode: no column or no value; Expression mode: no text), every row goes to **T** and **F** is empty. A chip says "No condition: rows pass through" or "Incomplete condition: rows pass through".

**Worked example (Simple).** Input:

| id | status | order_value | region |
|---|---|---|---|
| 1 | paid | 120 | N |
| 2 | open | 900 | S |
| 3 | paid | abc | N |
| 4 | void | 450 | *(empty)* |

Simple, Column = status, Operation = Equals, Value = paid. T holds rows 1 and 3, F holds rows 2 and 4.

**Worked example (Expression).** Same input:

```sql
TRY_CAST([order_value] AS DOUBLE) in_between (100, 500) AND [status] <> 'void'
```

T:

| id | status | order_value | region |
|---|---|---|---|
| 1 | paid | 120 | N |

F holds rows 2, 3 and 4. Row 3 (`abc`) is on F because `TRY_CAST` made it empty, so the condition could not be true. Row 2 is outside 100 to 500; row 4 is `void`.

Writing `[order_value] > 200` instead fails with `Cannot compare values of type VARCHAR and type INTEGER_LITERAL - an explicit cast is required`, because the column is text. See [the type pitfall](index.md#the-type-pitfall-csv-columns-arrive-as-text).

## Edge cases and limits

- [Preview uses 100 rows](index.md#preview-vs-run); Run filters everything.
- Empty cells: a comparison with an empty cell is neither true nor false, so those rows go to **F**. That includes "Not Equals" in Simple mode.
- Simple mode, numbers: the Value must be a number, otherwise `TD-SHAPE-004` ("Filter value must be a number"). **In Between** includes both ends, and if you type the bigger number first the two are swapped.
- Simple mode, **Contains** on text is **case-sensitive** and the value is searched as plain text: `.` or `(` mean just those characters. For a case-insensitive search use Expression mode: `[name] ILIKE '%acme%'`.
- Simple mode on a real date, date-time or time column (not text): type the Value as `2024-01-31` (dates and date-times, optionally with a time such as `2024-01-31 13:30:00`) or `13:30:00` (times). A date-only Value on a date-time column means midnight of that day. A Value that cannot be read gives `TD-SHAPE-004` ("Filter value must be a date such as 2024-01-31"). For a date held as text, use Expression mode with `TRY_CAST`.
- Simple mode tests one column. For several conditions use Expression with `AND` / `OR`, or chain two Filters.
- Expression mode is protected by the [read-only guard](index.md#the-read-only-guard).

## Messages you may see

| Code | When | Fix |
|---|---|---|
| `TD-SHAPE-003` | The Simple column is not in the input | Pick the column again |
| `TD-SHAPE-004` | The Value is not a number (or not a date or time on a date column); or the SQL engine rejected the condition (the text after the code is the engine's explanation, for example a missing column or "an explicit cast is required") | Correct the value; use `TRY_CAST` |
| `TD-SHAPE-110`, `-112`, `-114`, `-115` | The expression breaks the [read-only guard](index.md#the-read-only-guard) | Remove the offending part |
| `TD-SHAPE-005` | No input data | Fix the upstream node |

## Tips

- Use the **F** output as an exception list and connect it to a report.
- `in_between (a, b)` works only in Filter. In a Formula write `BETWEEN a AND b`.
- A Filter followed by [Aggregate](aggregate.md) gives totals for just the rows you care about.


Back to the [Preparation node index](index.md).
