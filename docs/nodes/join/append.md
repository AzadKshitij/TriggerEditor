# Append

![Append icon](../../assets/node_icons/Join/Append.svg){ .node-icon }

## Purpose

Append puts the rows of the right input underneath the rows of the left input. It always handles exactly two inputs.

## When to use it

- You have two tables with the same layout (this year and last year) and want one table.
- You want to place two tables side by side (Horizontal), row for row.

For more than two inputs, or when you want to line up columns that have different names, use [Union](union.md).

## Inputs and outputs

| Socket | Carries |
|---|---|
| Input 1 (left, top) | The first table. Its rows come first. |
| Input 2 (right, bottom) | The second table. |
| Output `Out` | The two tables combined. |

## Settings

One section, **Append**, with the note "Vertical requires identical schemas."

| Control | What it does | Default |
|---|---|---|
| **Method** | **Diagonal (relaxed)**: stack the rows; match columns by name; a column missing on one side is filled with empty values; a column with different types on the two sides is widened to a type that holds both (for example whole numbers and decimals become decimals; numbers and text become text). **Vertical (same columns)**: stack the rows, but only if both tables have exactly the same columns and types; otherwise stop with an error. **Horizontal (side by side)**: put the right table's columns next to the left table's columns, row by row. **Diagonal (strict)**: like Diagonal (relaxed), but columns that appear on both sides must have exactly the same type. | Diagonal (relaxed) |

The chip in the Config Dock shows the method and "rows stacked, left then right".

## Worked example

Left input (open invoices):

| Invoice | Amount |
|---|---|
| A1 | 100.0 |
| A2 | 250.0 |
| A3 | 75.0 |

Right input (payments, with an extra column):

| Invoice | Amount | Paid |
|---|---|---|
| A1 | 100.0 | Y |
| A3 | 80.0 | N |
| A9 | 10.0 | Y |

With **Method** = Diagonal (relaxed), the output `Out` is:

| Invoice | Amount | Paid |
|---|---|---|
| A1 | 100.0 | null |
| A2 | 250.0 | null |
| A3 | 75.0 | null |
| A1 | 100.0 | Y |
| A3 | 80.0 | N |
| A9 | 10.0 | Y |

With **Vertical (same columns)** the same two tables stop with `TD-SHAPE-004`: `schemas differ (right-only: ['Paid']). Try 'diagonal_relaxed'.`

With **Horizontal**, two tables of the same length, `Invoice` (A1, A2) and `Paid` (Y, N), give:

| Invoice | Paid |
|---|---|
| A1 | Y |
| A2 | N |

## Edge cases and limits

- **Row cap:** none. The live preview shows 100 rows; Run appends everything. See [Live preview and Run](../input-output/index.md#live-preview-and-run).
- **Empty input:** an empty table contributes no rows; its columns still count for Diagonal methods.
- **Nulls** stay null.
- **Different types.** Diagonal (relaxed) widens (a column of numbers on one side and text on the other becomes text, so `3` and `"x"` coexist). Vertical and Diagonal (strict) refuse.
- **Horizontal** needs the same number of rows on both sides and different column names on both sides. Otherwise it stops (see errors).
- The Vertical error says what differs: columns only on one side (`left-only: [...]`, `right-only: [...]`), a column with different types (`'Amount' is Int64 on the left but String on the right`), or the same columns in a different order.

## Errors you may see

| Code | What it means | What to do |
|---|---|---|
| `TD-SHAPE-004` | **Vertical** was chosen and the two tables are not identical in columns and types. | Choose **Diagonal (relaxed)**, or make the inputs match with Select nodes. |
| `TD-SCH-004` | **Diagonal (strict)** was chosen and a shared column has different types, or the columns differ. | Make both inputs have the same columns and types, or use Diagonal (relaxed). |
| `TD-SCH-005` | **Horizontal**: the two tables have different numbers of rows. | Make sure both come from the same step, or use Diagonal. |
| `TD-SCH-002` | **Horizontal**: a column name appears on both sides. | Rename one of them with a Select node first. |
| `TD-SHAPE-005` | An input has no data ("Input 1 has no data"). | Connect and fix the upstream node. |

## Tips

- Use Append for "this year plus last year". If the second table has a column the first lacks, keep Diagonal (relaxed) and check the new column for empty cells in the first table's rows.
- To keep track of where each row came from, add a column to each side first (for example a Formula that writes `"2024"` or `"2025"`).


Back to the [Join node index](index.md).
