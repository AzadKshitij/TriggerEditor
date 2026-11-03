# Record ID

![Record ID icon](../../assets/node_icons/Preparation/RecordID.svg){ .node-icon }

## Purpose

Adds a column of whole numbers that numbers the rows (1, 2, 3, ...), optionally restarting for each group and ordered by other columns.

## When to use it

Give each row a stable reference for workpapers, number the lines within each invoice or journal, or rank rows inside a group.

## Inputs and outputs

| Socket | Carries |
|---|---|
| Input | The table |
| Out | The same rows, in the same order, plus the ID column |

## Settings

| Section | Control | Default | Effect |
|---|---|---|---|
| (top) | **Name** (placeholder `RecordID`) | `RecordID` | Name of the new column; it must be new. Hint: "Dense Int64 numbers. The column name must be new." |
| (top) | **Start at** | 1 | First number (-1,000,000,000 to 1,000,000,000). |
| (top) | **Position** | First | First puts the column on the left, Last on the right. |
| Grouping & order (collapsible) | **Groups** | none | Numbering restarts at the start value for each combination of these columns. |
| Grouping & order | **Order by** (list) | none | Decides which rows get the smaller numbers; each entry has a **Column** and a **Descending** tick. |

A note in the dock reads: "Rows keep input order. This only changes the numbers." Order by never reorders the table.

## Worked example

Input:

| inv | dept | amt |
|---|---|---|
| A | x | 5 |
| B | y | 9 |
| C | x | 7 |
| D | x | 1 |

Defaults add `RecordID` = 1, 2, 3, 4 on the left.

Name `Seq`, Start at 100, Position Last, Groups = `dept`, Order by `amt` Descending:

| inv | dept | amt | Seq |
|---|---|---|---|
| A | x | 5 | 101 |
| B | y | 9 | 100 |
| C | x | 7 | 100 |
| D | x | 1 | 102 |

In dept x the largest amount (C, 7) gets 100, then A (5) gets 101, then D (1) gets 102.

## Edge cases and limits

- [Preview uses 100 rows](index.md#preview-vs-run): preview numbers cover the sample only. Without Groups and Order by, the number is simply the row position.
- Rows tied on the Order by columns keep their input order. Empty values in an Order by column are numbered last.
- Name must not be empty (`TD-SHAPE-001`) and must not already exist (`TD-SHAPE-002`).
- Group and order columns must exist (`TD-SHAPE-003`).

## Messages you may see

`TD-SHAPE-001`, `TD-SHAPE-002`, `TD-SHAPE-003`, `TD-SHAPE-005`.

## Tips

Record ID after a [Sort](sort.md) gives a ranking; with Groups it gives a "line number within invoice".


Back to the [Preparation node index](index.md).
