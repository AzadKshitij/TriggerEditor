# Multi-Field Formula

![Multi-Field Formula icon](../../assets/node_icons/Preparation/MultiFieldFormula.svg){ .node-icon }

## Purpose

Applies **one** SQL expression to many columns at once. You write the expression once, with `{col}` standing for "the current column", and the node repeats it for every column you tick.

## When to use it

Clean or convert a block of similar columns in one step: trim all text columns, convert twelve monthly amounts from text to numbers, upper-case several code columns.

## Inputs and outputs

| Socket | Carries |
|---|---|
| Input | The table |
| Out | The same rows, with the ticked columns replaced or new columns added |

## Settings

| Section | Control | Default | Effect |
|---|---|---|---|
| Columns | **Columns** (checklist) | none | The columns the formula runs on, up to 200. Hint: "The formula runs once for each ticked column (up to 200)." |
| Formula | **Formula** (text box; placeholder `UPPER(TRIM({col}))   or   TRY_CAST({col} AS DOUBLE)`) | empty | One SQL expression. `{col}` is replaced by each column. `{name}` is replaced by that column's name as text. No semicolons. |
| Output | **Result** | Replace the columns | **Replace the columns** overwrites each ticked column. **Add new columns** keeps the originals and adds one result column per ticked column. |
| Output | **New column suffix** (only for Add new columns) | `_new` | Added to each name: `net` with `_num` gives `net_num`. Must not be empty. |

The syntax is the same as in [Writing SQL expressions](index.md#writing-sql-expressions), except that you write `{col}` rather than `[column]`. Each `{col}` is inserted safely quoted, so column names with spaces or quotes work.

The dock note reads: "Use {col} for the column and {name} for its name. One expression only: no semicolons." After editing, a chip reads "2 columns replaced" or "2 columns added".

## Worked example

Input (all text):

| id | net | tax | vendor |
|---|---|---|---|
| 1 | ` 100.5` | 10 | Acme |
| 2 | `200 ` | x | Beta |
| 3 | abc | 30 | Acme |

Columns `net` and `tax`; Formula `TRY_CAST(TRIM({col}) AS DOUBLE)`; Result Add new columns; suffix `_num`:

| id | net | tax | vendor | net_num | tax_num |
|---|---|---|---|---|---|
| 1 | ` 100.5` | 10 | Acme | 100.5 | 10.0 |
| 2 | `200 ` | x | Beta | 200.0 | *(empty)* |
| 3 | abc | 30 | Acme | *(empty)* | 30.0 |

With Result = Replace the columns, `net` and `tax` themselves become decimal numbers: `net` = 100.5, 200.0, empty and `tax` = 10.0, empty, 30.0.

Using `{name}`: Columns `net` and `vendor`; Formula `{name} || ': ' || UPPER({col})`; Add new columns with suffix `_lbl`. The new `net_lbl` column holds `net:  100.5`, `net: 200`, `net: ABC` and `vendor_lbl` holds `vendor: ACME`, `vendor: BETA`, `vendor: ACME`.

## Edge cases and limits

- [Preview uses 100 rows](index.md#preview-vs-run).
- Up to 200 columns per node. In Add new columns mode the new names (`<column><suffix>`) must not already exist (`TD-SHAPE-002`).
- The formula is one expression. A semicolon, or brackets that do not balance, is rejected with `TD-SHAPE-110`. A trailing `--` comment is safe.
- Because the columns are usually text, put `TRIM(...)` and `TRY_CAST(...)` inside the formula.
- The [read-only guard](index.md#the-read-only-guard) checks the whole composed query: `read_csv(...)`, `random()`, `uuid()` and similar give `TD-SHAPE-112`.
- The result type follows the expression.

## Messages you may see

| Code | When | Fix |
|---|---|---|
| `TD-SHAPE-001` | No column ticked, or Add new columns with an empty suffix | Fill it in |
| `TD-SHAPE-002` | A new column name already exists | Change the suffix |
| `TD-SHAPE-003` | A ticked column is gone | Tick it again |
| `TD-SHAPE-004` | More than 200 columns, or an unknown result mode | Tick fewer columns |
| `TD-SHAPE-110` | More than one expression, or a semicolon | Write one expression |
| `TD-SHAPE-112` | A function or file access the guard blocks | Remove it |
| `TD-SHAPE-113` | The SQL could not be parsed or run (the message gives the engine's reason) | Check syntax and types |
| `TD-SHAPE-114`, `-115` | Too long (over 20,000 characters) or too slow (over 25 seconds) | Simplify |
| `TD-SHAPE-120` | The formula has no `{col}` | Write `{col}` where the column goes, for example `UPPER({col})` |

## Tips

Test the formula on one column first, then tick the rest.


Back to the [Preparation node index](index.md).
