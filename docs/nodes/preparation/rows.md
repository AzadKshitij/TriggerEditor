# Rows

![Rows icon](../../assets/node_icons/Preparation/Dynamic%20Row%20Generate.svg){ .node-icon }

## Purpose

Generates a column of sequence values (numbers, dates or text) and places it next to the input table. In code and some older documents this node is called Dynamic Row Builder.

## When to use it

Add a simple counter, a series of dates, or a test column. To number the rows of a real table, [Record ID](record-id.md) is usually the better choice.

## Inputs and outputs

| Socket | Carries |
|---|---|
| Input | A table (the node needs a connected input) |
| Out | The input columns plus the new column |

## Settings

| Control | Default | Effect |
|---|---|---|
| **Name** | `counter` | Name of the generated column. Must not be empty. |
| **Type** | Int | Int, Float, Text or Date/time. Changing the type converts the values where possible. |
| **Start** | 1 | First value. |
| **Increment** | 1 | The step. For Date/time it is a number of **seconds**. For Text it is the text appended at each step. |
| **End** | 10 | Last value, **included**. Not shown for Text. |

Starting values when you switch type: Int 1 / 1 / 10; Float 1.0 / 1.0 / 10.0; Text A / 1 / Z; Date/time 2024-01-01 00:00, 3600 seconds, 2024-01-02 00:00.

## Worked example

Input of three rows (`a` = x, y, z). Name `n`, Type Int, Start 10, Increment 10, End 30:

| a | n |
|---|---|
| x | 10 |
| y | 20 |
| z | 30 |

With Type Date/time, Start 2024-01-01 00:00, Increment 86400, End 2024-01-03 00:00 the same three rows get `2024-01-01 00:00:00`, `2024-01-02 00:00:00` and `2024-01-03 00:00:00`.

## Edge cases and limits

- **The number of generated values must equal the number of input rows.** The new column is attached side by side with the input. With a different count the node stops with `TD-SHAPE-130` ("The generated rows do not match the input rows"), which states both counts. Set Start, Increment and End so the count matches, and remember the live preview only sees the first 100 input rows.
- At most **10,000 values** are generated; the chip "Reached 10,000 rows" warns when the cap is hit (for example Increment 0).
- **Text** type has no End: it keeps appending the Increment text (`A`, `A1`, `A11`, ...) up to the 10,000 cap, so it only fits an input of exactly 10,000 rows. Use Int, Float or Date/time in practice.
- Int and Float stop when the value goes past End. If Start is already past End no values are produced.
- Date/time values have no time zone.

## Messages you may see

`TD-SHAPE-001` (empty name), `TD-SHAPE-004` (unknown type), `TD-SHAPE-005` (no input data), `TD-SHAPE-130` (generated count differs from the input row count).

## Tips

Count the input rows first (an [Aggregate](aggregate.md) with Count) before you set End.


Back to the [Preparation node index](index.md).
