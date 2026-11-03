# Select Records

![Select Records icon](../../assets/node_icons/Preparation/SelectRecords.svg){ .node-icon }

## Purpose

Picks rows by position or rank: the first or last N, a range of row numbers, or the largest or smallest N by a column. What is not picked goes to the second output.

## When to use it

Top 10 payments, the 5 oldest entries per account, rows 200 to 300 of an extract.

## Inputs and outputs

| Socket | Carries |
|---|---|
| Input | The table |
| **S** (Selected) | The chosen rows |
| **R** (Remaining) | Everything else |

## Settings

One section, **Mode**. A note says "Only the fields used by the chosen mode appear below."

| Control | Default | Shown for | Effect |
|---|---|---|---|
| **Mode** | First | always | First, Last, Range, Large, Small. |
| **N** | 10 | First, Last, Large, Small | How many rows (1 to 100,000,000). |
| **From row** / **To row** | 1 and 100 | Range | 1-based, inclusive, counted across the whole table (From must not exceed To). |
| **Rank by** | blank | Large, Small | The column to rank. Text columns are read as numbers (thousands commas are ignored); unreadable values are never selected. |
| **Ties** | Exact N | Large, Small | **Exact N** returns exactly N rows. **Include ties** also includes rows tied with the Nth. |
| **Per group** | none | all except Range | Selects within each group of the chosen columns. For Range a note says it is global and per-group does not apply. |

## Worked example

Input:

| k | v |
|---|---|
| a | 9 |
| b | 5 |
| c | 5 |
| d | 5 |
| e | 1 |

Mode Small, N 2, Rank by `v`, Ties = Exact N: S is `e` (1) and `b` (5); R is `a`, `c`, `d`. (The first of the tied 5s in input order wins.)

Same with Ties = Include ties: S is `e`, `b`, `c`, `d`; R is `a`.

On an invoice table (A/x/5, B/y/9, C/x/7, D/x/1): Mode Large, N 2, Rank by `amt` gives S = B (9) and C (7). Mode Last, N 1, Per group `dept` gives S = B (the last of y) and D (the last of x).

## Edge cases and limits

- [Preview uses 100 rows](index.md#preview-vs-run): "First 10" or "row 150" refer to positions in the sample while you edit; Run applies them to the whole table.
- For Large and Small, S is ordered by the ranked value (largest first for Large, smallest first for Small). For First, Last and Range, S keeps input order.
- Empty values in the **Rank by** column are never selected; they go to R.
- Asking for more rows than exist returns all rows in S.

## Messages you may see

| Code | When | Fix |
|---|---|---|
| `TD-SHAPE-001` | Large or Small without a Rank by column | Pick the column |
| `TD-SHAPE-003` | The Rank by or group column no longer exists | Pick it again |
| `TD-SHAPE-004` | N below 1, or Range with From above To | Fix the numbers |
| `TD-SHAPE-005` | No input data | Fix the upstream node |

## Tips

To get "the first 10 by date", [Sort](sort.md) first: First and Last follow the current row order.


Back to the [Preparation node index](index.md).
