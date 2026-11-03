# Select

![Select icon](../../assets/node_icons/Preparation/Select.svg){ .node-icon }

## Purpose

Chooses which columns to keep, in what order, under what name and with what data type. It is the main place to turn text columns into numbers and dates.

## When to use it

Right after reading a file: drop columns you do not need, give columns readable names, and set the type of each column so later nodes can calculate and sort correctly.

## Inputs and outputs

| Socket | Carries |
|---|---|
| Input | The table |
| Out | Only the ticked columns, in the dock's order, renamed and converted |

## Settings

The Config Dock shows a toolbar above a table with one row per input column.

Toolbar, left to right:

| Control | Effect |
|---|---|
| Search box ("Search columns...") | Filters the list by name (after about 300 ms). |
| **All** | Ticks every column. |
| **None** | Unticks every column. |
| **Move column up** / **Move column down** | Moves the highlighted column in the order. |
| **Column options** (menu icon) | Opens the bulk menu (below). |

Table columns:

| Column | Effect |
|---|---|
| (checkbox) | Tick to keep the column in the output. |
| **Column** | The input column name (not editable). |
| **Data Type** | String, Int64, Float64, Boolean, Date, Datetime, List, Struct, Categorical, Binary, Decimal or Duration. Defaults to the column's current type. |
| **Rename** | An optional new name. Leave blank to keep the name. |

Right-clicking a row offers Select / Deselect Column, Rename Column, Move to Top, Move Up, Move Down, Move to Bottom, Clear Renames and Reset Types.

The **Column options** menu has: Check Selected, Uncheck Selected, Move to Top, Move to Bottom, **Sort** (Original Order, Name A-Z, Name Z-A, By Type), **Bulk Rename** (Add Prefix or Suffix to Selected or to All, Clear Renames), **Bulk Data Type** (Auto-Detect Types and Reset Types, each for Selected or All) and a checkbox **Auto-add new columns**. When that box is on (the default), columns that later appear upstream are included automatically.

If no usable column is ticked, the node passes the whole table through instead of returning nothing.

**How types are converted.** When the chosen Data Type differs from the current one, the values are converted and anything that cannot be converted becomes empty, **without an error**:

- Text to Int64, Float64 or Decimal: unreadable text becomes empty.
- Text to Boolean: `true, 1, yes, y, t, on` become true and `false, 0, no, n, f, off` become false (any case); other non-zero numbers are true, zero is false, anything else is empty.
- Text to Date or Datetime: many layouts are understood (`2024-01-31`, `31/01/2024`, `31.01.2024`, `01/31/2024`, `31-Jan-2024`, `31 January 2024`, with or without a time). When a value fits several layouts, the day-before-month layouts are tried first. **Auto-Detect Types** reads up to 1,000 values of each column and remembers the layout it found, so day and month are read consistently.

## Worked example

Input (all text, as from a CSV):

| inv_no | amount | posted | internal |
|---|---|---|---|
| 1001 | 120.50 | 31/01/2024 | a |
| 1002 | 900 | 15/02/2024 | b |
| 1003 | abc | x | c |

Settings: `inv_no` ticked, Int64, renamed `Invoice`; `posted` ticked, Date, renamed `Posted on`, layout day/month/year; `amount` ticked, Float64; `internal` unticked.

| Invoice | Posted on | amount |
|---|---|---|
| 1001 | 2024-01-31 | 120.5 |
| 1002 | 2024-02-15 | 900.0 |
| 1003 | *(empty)* | *(empty)* |

## Edge cases and limits

- [Preview uses 100 rows](index.md#preview-vs-run): conversion problems later in the file show only on Run.
- A failed conversion becomes an empty cell **silently**. After converting, look for new empty cells (for example a [Filter](filter.md) with `[amount] IS NULL`) to find values that did not convert.
- A column that disappeared upstream stays in the list flagged as missing until you remove it; it is skipped in the output.
- Keep new names unique.

## Messages you may see

`TD-SHAPE-005` (no input data). Other problems show the engine's message.

## Tips

- Make Select the first node after an input node and fix the types once; every later node benefits.
- Use **Auto-Detect Types (All)** as a starting point, then check Date columns for day and month order.
- Untick columns that hold personal data you do not need before building reports.


Back to the [Preparation node index](index.md).
