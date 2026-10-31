# Aggregate

![Aggregate icon](../../assets/node_icons/Preparation/Groupby.svg){ .node-icon }

## Purpose

Summarises the table: one output row for each combination of the group columns, with counts, totals, averages and similar measures. (Saved workflows and older documents call this node GroupBy.)

## When to use it

Total by vendor or month, transactions per user, the largest posting per account, the number of distinct approvers per supplier.

## Inputs and outputs

| Socket | Carries |
|---|---|
| Input | The detailed table |
| Out | The summary: group columns first, then one column per measure |

## Settings

| Control | Default | Effect |
|---|---|---|
| Field picker (drop-down of the input columns) | first column | The column to add. |
| **Add field as group key or measure** (plus icon) | | Adds the picked column to the table below as a group key. A column can be added only once; adding it again does nothing. |
| **Remove selected action** (minus icon) | | Removes the selected row(s). |
| Table column **Field** | | The input column (not editable). |
| Table column **Action** | GroupBy | What to do with the column (list below). |
| Table column **Output Field Name** | the column name, or a prefix plus the name | The name in the result. Double-click to rename. Changing the Action resets it to the default name. |

| Action | Meaning | Default output name |
|---|---|---|
| GroupBy | Use as a group key | same as the field |
| Count | Number of rows in the group | `Count_<field>` |
| Sum | Total | `Sum_<field>` |
| Mean | Average | `Avg_<field>` |
| Min / Max | Smallest / largest | `Min_<field>` / `Max_<field>` |
| Std / Var | Standard deviation / variance | `Std_<field>` / `Var_<field>` |
| Median | Middle value | `Median_<field>` |
| First / Last | First / last value in input order | `First_<field>` / `Last_<field>` |
| N_Unique | Number of distinct values | `Unique_<field>` |
| List | The values gathered into a list | `List_<field>` |

For a **text** column only GroupBy, Count, Min, Max, First, Last, N_Unique and List are offered. Sum, Mean, Std, Var and Median need a number column, so a CSV amount that arrived as text must be converted first ([Select](select.md) or [Formula](formula.md)).

The dock chips show the number of keys and measures ("2 keys", "1 measure").

## Worked example

Input:

| region | rep | amount |
|---|---|---|
| N | a | 100 |
| S | b | 50 |
| N | a | 25 |
| S | c | 75 |
| N | d | *(empty)* |

`region` = GroupBy, `amount` = Sum, `rep` = N_Unique:

| region | Sum_amount | Unique_rep |
|---|---|---|
| N | 125 | 2 |
| S | 125 | 2 |

With no group key (only `amount` = Mean and `rep` = Count) the result is one row: `Avg_amount` = 62.5 (the empty value is ignored) and `Count_rep` = 5.

With group keys but no measure, the result has a `count` column holding the number of rows per group.

## Edge cases and limits

- [Preview uses 100 rows](index.md#preview-vs-run): totals in the preview are totals of the sample.
- **One action per column.** To get both the sum and the count of `amount`, use two Aggregate nodes, or copy the column with a [Formula](formula.md) first.
- Groups come out in order of first appearance, not sorted. Add a [Sort](sort.md) after it.
- Empty cells: Sum, Mean, Min and Max ignore them; **Count** counts every row of the group.
- Empty group keys form a group of their own.
- With no actions, or when none of the fields exist, the table passes through unchanged. A chip "n field(s) missing" warns about missing fields.
- Output names must be unique and must not repeat a group column name (`TD-SHAPE-002`).

## Messages you may see

`TD-SHAPE-002` (duplicate output name: choose a unique name), `TD-SHAPE-004` (unknown action), `TD-SHAPE-005` (no input data).

## Tips

- To total only a subset, put a [Filter](filter.md) in front.
- Rename output columns to something a reader will understand before they reach a report.
- Use List to see the values behind a total while you investigate, then remove it before exporting.


Back to the [Preparation node index](index.md).
