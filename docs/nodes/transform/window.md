# Window

![Window](../../assets/node_icons/Transform/Window.svg)

## Purpose

Adds one new column per calculation that compares a row with the rows around it: the previous or
next value, a row number, a rank, a running sum, minimum, maximum or mean, or a rolling sum over the last few rows.
The rows stay in their input order.

## When to use it

Days between one posting and the previous one (previous value, then the days between with a
*Date Helper*); number the lines in each journal; rank invoices by amount within each vendor; detect a balance that
jumps from the one before.

## Inputs and outputs

One input, one output (no letter): every input column, then the new columns.

## Settings

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

## Worked example

Restart per `Account`, Order by `Date` (A to Z). Calculations: Row number; Previous row on
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

## Edge cases and limits

- Rank, Dense rank and the running and rolling calculations read text as numbers (commas removed; other text
  becomes empty). Previous and Next work on any column and keep its type. Choosing a column that is neither text nor a number gives `TD-SHAPE-091`.
- Every Order by row needs a column (`TD-SHAPE-001`); an offset or window below 1 gives `TD-SHAPE-004`.
- Running mean divides by the number of non-empty values so far.
- Text dates sort correctly only when written year-month-day (`2025-01-03`). `03/01/2025` sorts as text.
- With no calculation in the list, the table passes through unchanged.

## Tip

Equal order keys keep input order, so the result is repeatable.


Back to the [Transform node index](index.md).
