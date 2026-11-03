# Unpivot

![Unpivot](../../assets/node_icons/Transform/Unpivot.svg)

## Purpose

Stacks several columns into two: the name of the column and its value. It is the opposite of
Pivot.

## When to use it

Data laid out as one column per month, per account or per test result, when you need one row
per measurement to filter, aggregate, chart or join.

## Inputs and outputs

One input, one output (no letter): the kept columns, then the name column, then the value column.

## Settings

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

## Worked example

Keep `Vendor`, Unpivot `Jan`, `Feb`, `Mar`, Name column `Month`, Value column `Amt`, Drop empty values on:

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

## Edge cases and limits

- The two new names must be different, not empty, and not the same as a kept column (`TD-SHAPE-002`).
- Rows stay grouped by input row (all of Acme's months, then Beta's), columns in the order you ticked them.
- If the stacked columns have different types, they are converted to one: all numbers become decimals
  (100 becomes 100.0), anything else becomes text ("Mixed types are cast to text").
- The output has (rows x stacked columns) rows. Stacking 12 columns of a 100,000-row file makes 1.2 million rows.

## Tip

After an Unpivot, an *Aggregate* by the name column gives you totals per old column.


Back to the [Transform node index](index.md).
