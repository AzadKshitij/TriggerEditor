# Text to Columns

![Text to Columns icon](../../assets/node_icons/Preparation/TextToColumns.svg){ .node-icon }

## Purpose

Splits one text column into several columns, or into several rows, at a delimiter or a pattern.

## When to use it

Split `Surname, First name`, a `code-description` field, account strings such as `100.200.300`, or a cell holding several values separated by semicolons (one value per row).

## Inputs and outputs

| Socket | Carries |
|---|---|
| Input | The table |
| Out | The table with the extra columns, or with more rows |

## Settings

| Section | Control | Default | Effect |
|---|---|---|---|
| Split | **Column** | empty | The text column to split. Hint: "Text columns only." |
| Split | **Split by** | Delimiter | **Delimiter** is plain text. **Regex** is a regular expression that must match at least one character. |
| Split | **Pattern** (placeholder `, or \t`) | `,` | The separator. For a delimiter, `\t`, `\n`, `\r` and `\\` are accepted. |
| Output | **Output** | Columns | **Columns** or **Rows**. |
| Output | **Max splits** | 2 | Columns: 1 to 49, and you get that number plus one columns, so 2 gives three columns and the last one receives whatever is left. Rows: 0 to 49, where 0 means no limit. |
| Output | **Column names** (placeholder `a, b, c`; Columns only) | empty | Comma-separated names. Missing names become `<column>_1`, `<column>_2`, .... |
| Output | **Piece number** (placeholder `n`; Rows only) | empty | Optional column holding the 1-based number of the piece within its cell. |
| Options | **Trim spaces** | on | Trims spaces around each piece. |
| Options | **Keep original** | on | Keeps the source column. In Rows mode the original text is kept in `<column>_original`. |
| Options | **Skip empty** (Rows only) | off | Drops pieces that are empty. |

In Rows mode the piece goes into the original column's name and all other columns repeat for each piece. A chip reads "n rows become m (first 100 rows)".

## Worked example

Input:

| id | full |
|---|---|
| 1 | Smith, John, Jr |
| 2 |  Doe,Jane |
| 3 | Solo |

Column `full`, Pattern `,`, Output Columns, Max splits 2, Column names `last, first, suffix`:

| id | full | last | first | suffix |
|---|---|---|---|---|
| 1 | Smith, John, Jr | Smith | John | Jr |
| 2 |  Doe,Jane | Doe | Jane | *(empty)* |
| 3 | Solo | Solo | *(empty)* | *(empty)* |

Same data with Max splits 1, no names and Keep original off: the columns are `full_1` and `full_2`; row 1 gives `Smith` and `John, Jr` (the remainder stays together).

Output Rows, Max splits 0, Piece number `n`, Keep original off:

| id | full | n |
|---|---|---|
| 1 | Smith | 1 |
| 1 | John | 2 |
| 1 | Jr | 3 |
| 2 | Doe | 1 |
| 2 | Jane | 2 |
| 3 | Solo | 1 |

## Edge cases and limits

- [Preview uses 100 rows](index.md#preview-vs-run); in Rows mode the row count after Run is much larger than in the preview.
- Only text columns (`TD-SHAPE-044`). Convert numbers to text first.
- Fewer pieces than columns leaves the extra columns empty; a cell without the delimiter ends up entirely in the first column.
- If a new column name already exists, a number is added (`name_2`).
- A regex that can match nothing, such as `\s*`, is rejected: use `\s+` (`TD-SHAPE-101`).
- A regex separator is replaced by a special marker character (U+241F) internally, so a cell that already contains that character would split there too. This is very rare.
- Maximum 50 columns. An empty Pattern is an error.

## Messages you may see

| Code | When | Fix |
|---|---|---|
| `TD-SHAPE-001` | No column picked, or the Pattern is empty | Fill it in |
| `TD-SHAPE-003` | The column is gone | Pick it again |
| `TD-SHAPE-004` | Max splits outside the range | Change the number |
| `TD-SHAPE-040` | Invalid regular expression | Escape special characters |
| `TD-SHAPE-044` | The column is not text | Convert it with Select |
| `TD-SHAPE-101` | The pattern can match nothing | Use `\s+` rather than `\s*` |

## Tips

To split into rows and then total per piece, follow with an [Aggregate](aggregate.md).


Back to the [Preparation node index](index.md).
