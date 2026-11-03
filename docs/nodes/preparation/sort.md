# Sort

![Sort icon](../../assets/node_icons/Preparation/Sort.svg){ .node-icon }

## Purpose

Orders the rows by one or more columns.

## When to use it

Put the biggest amounts first, order by date for a review, or sort before [Select Records](select-records.md) or a report.

## Inputs and outputs

| Socket | Carries |
|---|---|
| Input | The table |
| Out | The same rows in the new order |

## Settings

One section, **Sort**, holding a list of sort keys (up to 10). The first key is the main one; later keys break ties.

| Control | Default | Effect |
|---|---|---|
| **Column** (per key) | empty | The column to sort by. |
| **Order** (per key) | Ascending | Ascending or Descending. |

Keys without a column are ignored. With no valid key the table passes through unchanged. A chip "n sort key(s) missing" warns when a chosen column is no longer in the input.

## Worked example

Input:

| region | rep | amount |
|---|---|---|
| N | a | 100 |
| S | b | 50 |
| N | a | 25 |
| S | c | 75 |
| N | d | *(empty)* |

Keys: `region` Ascending, then `amount` Descending.

| region | rep | amount |
|---|---|---|
| N | d | *(empty)* |
| N | a | 100 |
| N | a | 25 |
| S | c | 75 |
| S | b | 50 |

Empty values come first, in both ascending and descending sorts.

## Edge cases and limits

- [Preview uses 100 rows](index.md#preview-vs-run): the preview order is the order of the sample only.
- **Text columns sort as text**: `"100"` comes before `"25"`. Convert amounts with [Select](select.md) first.
- Rows with equal keys may keep any relative order; add another key if the order must be repeatable.
- Maximum 10 keys.

## Messages you may see

`TD-SHAPE-005` only.

## Tips

Sort after an [Aggregate](aggregate.md) so the summary reads largest first.


Back to the [Preparation node index](index.md).
