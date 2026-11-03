# Running Total

![Running Total](../../assets/node_icons/Transform/Running%20Total.svg)

## Purpose

Adds a cumulative sum of one or more number columns, optionally restarting for each group.

## When to use it

To build a running balance from a transaction list, or to see when a cumulative total
crosses a threshold. For other running figures (minimum, maximum, average, rolling windows) use *Window*.

## Inputs and outputs

One input. One output, labelled `Out`: every input column in the same order, then one new column
per chosen sum column.

## Settings

(section *Running totals*):

| Label | Default | Effect |
|---|---|---|
| **Sum** | none chosen | The columns to total: number columns and text columns (read as numbers, like Window; a value that is not a number becomes empty). Each one adds a column named `RunTot_<column>`. |
| **Group by** | none chosen | The columns that define a group (account, branch). The total restarts at each new value. With none chosen, one total runs down the whole table. |

## Worked example

Sum `Amount`, Group by `Account`, on the table above:

| Account | Date | Amount | RunTot_Amount |
|---|---|---|---|
| A | 2025-01-01 | 100.0 | 100.0 |
| A | 2025-01-02 | -30.0 | 70.0 |
| B | 2025-01-01 | 50.0 | 50.0 |
| B | 2025-01-03 | 25.0 | 75.0 |
| B | 2025-01-04 | -75.0 | 0.0 |

With no Group by, the last column reads 100, 70, 120, 145, 70.

## Edge cases and limits

- **Row order matters.** The total accumulates in the order the rows arrive. Sort first (a *Sort* node) if you
  want it in date order. Rows are never reordered.
- **Text columns are read as numbers.** A CSV arrives as text, so its columns are offered too. A comma in the
  text is dropped (`1,000` is 1000), spaces are trimmed, and a value that is not a number stays empty in the
  new column (it is not an error). The result column is a decimal number. Columns that are neither numbers nor
  text (dates, yes/no) are not offered.
- With no Sum column chosen, the node passes the table through unchanged (no error).
- An empty cell stays empty in the new column and the total carries on past it (1, empty, 3 gives 1, empty, 4).

## Tip

The name is fixed (`RunTot_<column>`); rename it afterwards with *Select*.


Back to the [Transform node index](index.md).
