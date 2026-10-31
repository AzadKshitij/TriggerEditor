# Count

![Count](../../assets/node_icons/Transform/Count.svg)

## Purpose

Counts the rows of a table and returns the number as a one-row table.

## When to use it

To reconcile record counts: "does the file have the 4,812 rows the system report
says?" Put it after File Input, or after a Filter to count the matches. For a count per group (rows per
vendor), use *Aggregate* in the Preparation family instead; Count has no grouping.

## Inputs and outputs

One input. One output, labelled `Out`, with a single column `Count` (a whole number).

## Settings

None. The Config Dock only says "No configuration. The output socket carries the row count."

## Worked example

Input of 5 rows (Account, Date, Amount):

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

## Edge cases and limits

- In the live preview the node counts only the sample and shows a warning chip, "First 100 rows only: full
  count at Run". Never quote the preview number. After a **Run** the count covers all rows.
- An empty input gives `Count` 0, not an error.
- An unconnected input gives `TD-SHAPE-005`.

## Tip

Connect Count to a *File Output* to keep the figure in your working papers.


Back to the [Transform node index](index.md).
