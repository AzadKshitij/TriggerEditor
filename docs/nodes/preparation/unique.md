# Unique

![Unique icon](../../assets/node_icons/Preparation/Unique.svg){ .node-icon }

## Purpose

Finds duplicates. One output keeps the first row of each distinct key; the other lists every row that belongs to a duplicated key.

## When to use it

Duplicate invoices, repeated payments, duplicate vendor records. The Duplicates output is your exception list.

## Inputs and outputs

| Socket | Carries |
|---|---|
| Input | The table |
| **Unique** | The first row of each distinct combination of the chosen columns, in input order |
| **Duplicates** | **Every** row (including the first) whose combination appears more than once |

## Settings

| Control | Default | Effect |
|---|---|---|
| **Columns** (checklist, section "Duplicate key") | none ticked | Rows that match on **all** ticked columns are duplicates. |

With no column ticked all rows go to **Unique** and **Duplicates** is empty. The dock summary reads "n columns selected".

## Worked example

Input:

| region | rep | amount |
|---|---|---|
| N | a | 100 |
| S | b | 50 |
| N | a | 25 |
| S | c | 75 |
| N | d | *(empty)* |

Columns = `region` and `rep`.

Unique:

| region | rep | amount |
|---|---|---|
| N | a | 100 |
| S | b | 50 |
| S | c | 75 |
| N | d | *(empty)* |

Duplicates:

| region | rep | amount |
|---|---|---|
| N | a | 100 |
| N | a | 25 |

## Edge cases and limits

- [Preview uses 100 rows](index.md#preview-vs-run): a duplicate whose second copy lies beyond row 100 does not appear in the preview.
- Matching is exact: `Acme`, `acme` and `Acme ` are different. Clean the key columns first ([Cleansing](cleansing.md)).
- Empty cells match each other: two rows with an empty key in the same position are duplicates.
- Unique keeps the **first** occurrence in the input; sort first if you want the latest or largest.
- Chosen columns that are no longer in the input are ignored.

## Messages you may see

`TD-SHAPE-005` only.

## Tips

- To find duplicate invoices tick vendor, invoice number and amount.
- For tolerance-based or near-duplicate tests see the Duplicates test in [Audit nodes](../audit/index.md); use Unique for quick exact checks.


Back to the [Preparation node index](index.md).
