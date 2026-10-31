# Transpose

![Transpose](../../assets/node_icons/Transform/Transpose.svg)

## Purpose

Turns chosen columns into rows: every data column becomes a set of `Name` / `Value` rows, and the
key columns repeat on each. (It does not flip the whole table; if you want one row per key and a column per value,
use Pivot.)

## When to use it

A trial balance or budget with one column per month (Jan, Feb, Mar) is hard to filter,
chart or join. Transpose it into one row per branch and month.

## Inputs and outputs

One input. One output, labelled `Out`: the key columns, then `Name` (the old column name) and `Value`.

## Settings

(section *Transpose*):

| Label | Default | Effect |
|---|---|---|
| **Key columns** | none | Columns that identify the row (branch, account). They are repeated on every output row. |
| **Data columns** | none | The columns to turn into rows. With none chosen the table passes through unchanged. |
| **If columns are missing** | Warn and skip | What to do when a chosen data column no longer exists. *Warn and skip* and *Ignore* both leave the missing column out of the result; *Warn and skip* also shows a "data column(s) missing" chip (and a "key column(s) missing" chip), *Ignore* shows no chip. *Error* stops the node with `TD-SHAPE-003`. |

## Worked example

Key `Branch`, data `Jan`, `Feb`, `Mar`:

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

## Edge cases and limits

- Output is one block per data column, in the order you ticked them, and in input row order inside each block.
- Empty cells are kept as empty `Value` rows. Filter them afterwards if you do not want them.
- If the data columns have different types (numbers and text), `Value` becomes text.
- If every data column is missing, the table passes through unchanged. Missing *key* columns only raise a chip (none under *Ignore*).

## Tip

Unpivot does the same job with more control (it names the two new columns and can drop empty
values). Use Transpose for a quick reshape, Unpivot when you need the names.


Back to the [Transform node index](index.md).
