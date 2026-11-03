# Pivot

![Pivot](../../assets/node_icons/Transform/Pivot.svg)

## Purpose

Turns the distinct values of one column into new columns, and summarises a value column in each.
This is the Excel PivotTable layout: row labels down the side, headers across the top.

## When to use it

Amount by vendor and month; count of journals by user and posting period; a quick matrix of
two categories.

## Inputs and outputs

One input, one output (no letter): the Row labels columns, then one column per distinct header value.

## Settings

*Layout*

| Label | Default | Effect |
|---|---|---|
| **Row labels** | none | Columns that become the rows (several allowed). With none chosen, the result is a single row. |
| **Headers** | none | The column whose values become the new column names. Required. |
| **Values** | none | The column that is summarised in each cell. Required. |

*Aggregation*

| Label | Default | Effect |
|---|---|---|
| **Function** | Sum | How several rows in one cell are combined: Sum, Mean, Min, Max, Median, First, Last or Count. |
| **Empty cells** | Blank | A cell with no data shows blank (*Blank*) or 0 (*Zero*). |

*Naming & limits* (collapsed; open it to change)

| Label | Default | Effect |
|---|---|---|
| **Blank header** | `(blank)` | The column name used for rows whose header cell is empty. |

## Worked example

Row labels `Vendor`, Headers `Month`, Values `Amount`, Function Sum. Amount arrives as text, as it does from a CSV:

| Vendor | Month | Amount |
|---|---|---|
| Acme | Jan | 100 |
| Acme | Feb | 200 |
| Acme | Jan | 50 |
| Beta | Jan | 75 |
| Beta | Mar | (empty) |

| Vendor | Feb | Jan | Mar |
|---|---|---|---|
| Acme | 200.0 | 150.0 | |
| Beta | | 75.0 | |

With *Empty cells* = Zero, every blank cell becomes 0.0. With Function = Count, the result is Acme: Feb 1,
Jan 2; Beta: Jan 1, Mar 0.

## Edge cases and limits

- **Columns are sorted by name**, not by the order they appear (Feb, Jan, Mar above). Number the headers
  (`01 Jan`, `02 Feb`) if you need calendar order, or reorder with *Select* afterwards.
- Sum, Mean, Min, Max and Median read text as numbers (commas are removed; text that is not a number is
  ignored). First, Last and Count work on any column and Count counts non-empty values.
- A Sum of cells that are all empty is empty, not 0.
- Count shows 0 for a header that exists for that row (a row with only empty values), and blank when no row
  has that combination. Choose *Zero* to show 0 everywhere.
- **Limit: 500 columns.** More than 500 distinct header values stops the node with `TD-SHAPE-061`. Filter or group first.
- Row labels, Headers and Values must be three different columns (`TD-SHAPE-060`). Headers and Values are required (`TD-SHAPE-001`).
- Rows are sorted by the Row labels, empty labels last.
- Pivot must see the data to know the headers. In the preview it sees only 100 rows, so some headers may be missing
  until you Run.

## Tip

To total by two keys across two headers (vendor by month by entity), add a *Formula* that joins them
into one header column first.


Back to the [Transform node index](index.md).
