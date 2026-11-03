# Preparation nodes

Preparation nodes clean, reshape and enrich a table before you analyse it. They are the first nodes you place after an input node: fix the types, remove the rubbish, add the columns you need, then pass the table on to joins, audit tests or reports.

This page covers all 16 Preparation nodes in the palette.

## Nodes in this family

| Icon | Node | What it does |
|---|---|---|
| ![Cleansing](../../assets/node_icons/Preparation/Cleansing.svg) | **[Cleansing](cleansing.md)** | Per-column clean-up: trim, change case, handle empty values, convert type. |
| ![Filter](../../assets/node_icons/Preparation/Filter.svg) | **[Filter](filter.md)** | Keeps or drops rows that meet conditions you set. |
| ![Formula](../../assets/node_icons/Preparation/Formula.svg) | **[Formula](formula.md)** | Creates or changes columns from SQL-style expressions. |
| ![Aggregate](../../assets/node_icons/Preparation/Groupby.svg) | **[Aggregate](aggregate.md)** | Collapses rows into groups and totals, counts or averages each group. |
| ![Select](../../assets/node_icons/Preparation/Select.svg) | **[Select](select.md)** | Chooses, renames, reorders and changes the type of columns. |
| ![Sort](../../assets/node_icons/Preparation/Sort.svg) | **[Sort](sort.md)** | Orders rows by one or more columns. |
| ![Unique](../../assets/node_icons/Preparation/Unique.svg) | **[Unique](unique.md)** | Keeps the first row for each key and sends the repeats out separately. |
| ![Split](../../assets/node_icons/Preparation/Split.svg) | **[Split](split.md)** | Divides the rows into two sets by percent (an estimation and a validation set). |
| ![Rows](../../assets/node_icons/Preparation/Dynamic%20Row%20Generate.svg) | **[Rows](rows.md)** | Builds a series of rows from ranges, patterns or literal values. |
| ![Normalize](../../assets/node_icons/Preparation/Select.svg) | **[Normalize](normalize.md)** | Tidies column names: trim, collapse spaces, apply one case rule. (Shares the Select icon.) |
| ![Record ID](../../assets/node_icons/Preparation/RecordID.svg) | **[Record ID](record-id.md)** | Adds a numbered column, optionally restarting per group. |
| ![Select Records](../../assets/node_icons/Preparation/SelectRecords.svg) | **[Select Records](select-records.md)** | Keeps the first, last, a range, the largest or smallest rows, and sends the rest out separately. |
| ![Find and Replace](../../assets/node_icons/Preparation/FindReplace.svg) | **[Find and Replace](find-and-replace.md)** | Applies an ordered list of text or pattern replacements to chosen columns. |
| ![Date Helper](../../assets/node_icons/Preparation/DateHelper.svg) | **[Date Helper](date-helper.md)** | Adds date parts, fiscal periods, day differences and business-day figures. |
| ![Text to Columns](../../assets/node_icons/Preparation/TextToColumns.svg) | **[Text to Columns](text-to-columns.md)** | Splits one text column on a delimiter or pattern into columns or rows. |
| ![Multi-Field Formula](../../assets/node_icons/Preparation/MultiFieldFormula.svg) | **[Multi-Field Formula](multi-field-formula.md)** | Applies one expression to many ticked columns at once. |

---

## How Preparation nodes work

<a id="preview-vs-run"></a>

### Preview uses 100 rows, Run uses all rows

While you edit a node, the app shows a **live preview** so you can see the effect of every change straight away. To stay fast on big files, the preview reads only the **first 100 rows** of each input and shows at most 100 rows of each output. When you press **Run**, the workflow processes **every row**.

What this means for you:

- A preview that looks right proves your settings work on the first 100 rows, not on the whole file. A value that only appears on row 40,000 (an unreadable date, a text amount, a duplicate) will not show in the preview.
- Counts shown in the preview (for example "12 cells change (first 100 rows)") are counts for the sample only.
- Settings that depend on row position or on the whole table (Select Records, Record ID, Split, Unique, Aggregate totals) show sample results while you edit, and whole-table results after Run. Rely on the Run result.
- A node can pass the preview and still fail on Run when a bad value sits in the later rows (for example a plain `CAST` meeting a text value). Use the forgiving `TRY_CAST` where data is untidy.

Every node below links back to this section.

### Common behaviour

- **One table in, one or two tables out.** Every Preparation node has a single input socket on the left. Filter, Unique, Split and Select Records have two output sockets, labelled on the node (T and F, Unique and Duplicates, E and V, S and R). The others have one output.
- **No input, no settings.** If nothing is connected, or the upstream node has no data yet, the Config Dock shows "No incoming data available" and the node reports `TD-SHAPE-005` ("Input 1 has no data"). Connect and fix the upstream node first.
- **Settings apply as you edit.** Text boxes wait about a third of a second after you stop typing before the node recomputes. Each real change is one step in Undo/Redo.
- **Columns that disappear.** If a column you chose is no longer in the input (for example it was renamed upstream), the node reports `TD-SHAPE-003` or, for some nodes, skips that setting. A chip or the message names the column.
- **CSV and Excel text.** Files read as CSV usually give you **text** columns, even when the values look like numbers or dates. Many nodes offer fewer choices for text columns. Convert the type first with [Select](select.md) (Data Type column) or with `TRY_CAST` in a [Formula](formula.md).
- **Nulls** (empty cells) stay empty unless a node says otherwise.

### Reading the Config Dock

The **Config Dock** is the panel that shows the settings of the selected node. Buttons are icon-only: hover over one to see its name. The paired **All** and **None** buttons in Select are the only text buttons.

---

## Writing SQL expressions

[Filter](filter.md) (Expression mode), [Formula](formula.md) and [Multi-Field Formula](multi-field-formula.md) accept **SQL expressions**. You do not write a whole query, only the expression:

- Formula and Multi-Field Formula take an expression that produces a value, for example `[Amount] * 1.2`.
- Filter takes a condition that is true or false, for example `[Amount] > 100`. Think of it as the text after `WHERE`.

Expressions run on the DuckDB engine, so DuckDB's SQL functions are available.

### Column names: square brackets (Formula and Filter)

Put a column name in square brackets: `[Invoice Amount]`. Spaces in names are fine. Matching ignores upper and lower case, and spaces just inside the brackets are ignored, so `[invoice amount]` and `[ Invoice Amount ]` both find `Invoice Amount`.

- Only names that exist in the input (and, in Formula, columns created by earlier formulas in the same node) are recognised. An unknown name is not a column, and the engine reports an error such as `Referenced column "nope" not found`.
- Brackets inside quoted text are left alone: `'[x]'` is the text `[x]`.
- **Text goes in single quotes**: `'paid'`. Double quotes are accepted for text too (`"paid"` is read as `'paid'`), because only `[...]` means a column.
- Inside text, write a quote as two quotes: `'O''Brien'`.
- Multi-Field Formula does not use brackets. It uses `{col}` and `{name}`; see [Multi-Field Formula](multi-field-formula.md).

### What you can write

Any single SQL expression: arithmetic (`+ - * / %`), comparisons (`= <> < > <= >=`), `AND` / `OR` / `NOT`, `CASE WHEN ... THEN ... ELSE ... END`, `IN (...)`, `BETWEEN a AND b`, `LIKE` / `ILIKE`, `IS NULL`, casts (`CAST(x AS ...)`, `TRY_CAST(x AS ...)`, `x::DATE`), `||` to join text, and DuckDB's functions.

Two spelling conveniences are translated for you:

| You type | Meaning | Works in |
|---|---|---|
| `strip(x)` | the same as `trim(x)` | Filter and Formula |
| `x in_between (a, b)` | the same as `x BETWEEN a AND b` | **Filter only**. In a Formula it is a syntax error; write `BETWEEN a AND b`. |

In the editor, press **Ctrl+Space** to open suggestions for functions, keywords and column names.

### Useful functions

Every expression below was run against a small sample table (a text `amt` column such as `"1,200.50"`, a text `posted` column such as `"2024-01-31"`).

| Goal | Expression | Result |
|---|---|---|
| Trim spaces | `TRIM([name])` | `"  Acme Ltd "` becomes `Acme Ltd` |
| Upper case | `UPPER(TRIM([name]))` | `ACME LTD` |
| Join text and a number | `CONCAT(TRIM([name]), ' / ', [code])` | `Acme Ltd / 7` |
| First characters | `LEFT(TRIM([name]), 4)` | `Acme` |
| Pad with zeros | `LPAD([code], 5, '0')` | `7` becomes `00007` |
| Replace text | `REPLACE([vendor], 'Acme', 'ACME Ltd')` | |
| Remove non-letters | `regexp_replace([name], '[^A-Za-z]', '', 'g')` | `Acme Ltd` becomes `AcmeLtd` |
| First non-empty value | `COALESCE([name], 'unknown')` | an empty name becomes `unknown` |
| Text to number, safely | `TRY_CAST([amt] AS DOUBLE)` | `"75"` becomes `75.0`, `"x"` becomes empty |
| Number with thousands comma | `TRY_CAST(REPLACE([amt], ',', '') AS DOUBLE)` | `"1,200.50"` becomes `1200.5` |
| Text to date | `TRY_CAST([posted] AS DATE)` | `"2024-01-31"` becomes a date, `"bad"` becomes empty |
| Date as text | `strftime(TRY_CAST([posted] AS DATE), '%Y-%m')` | `2024-01` |
| Days between dates | `date_diff('day', TRY_CAST([posted] AS DATE), DATE '2024-03-01')` | `30` for 31 Jan |
| Rounding | `ROUND(TRY_CAST([order_value] AS DOUBLE) * 1.1, 1)` | `120.50` becomes `132.6` |
| Parse a non-ISO date | `strptime([date], '%d/%m/%Y')::DATE` | `31/12/2024` becomes a date |
| Category | `CASE WHEN TRY_CAST([v] AS DOUBLE) >= 400 THEN 'Large' WHEN TRY_CAST([v] AS DOUBLE) IS NULL THEN 'Unreadable' ELSE 'Small' END` | |
| Simple if | `IF(TRY_CAST([amt] AS DOUBLE) IS NULL, 'check', 'ok')` | |
| Case-insensitive match | `[name] ILIKE '%acme%'` | true, false or empty |
| Month number | `month([d])` for a date column `d` | |
| Text length | `LENGTH([vendor])` | |

### The type pitfall: CSV columns arrive as text

A column read from CSV is text even when it looks like `120.50`. DuckDB does not guess:

- `[order_value] + 1` fails: `No function matches the given name and argument types '+(VARCHAR, INTEGER_LITERAL)'`.
- `[order_value] > 200` in a Filter fails: `Cannot compare values of type VARCHAR and type INTEGER_LITERAL - an explicit cast is required`.

Use **`TRY_CAST`**:

```sql
TRY_CAST([order_value] AS DOUBLE) > 200
```

`TRY_CAST` returns empty for a value it cannot read (such as `abc`) instead of stopping the node. Plain `CAST` stops at the first bad value, which may only happen on Run if the bad value is beyond the 100-row preview (see [Preview uses 100 rows](#preview-vs-run)). In a Filter, an empty result counts as "not true", so unreadable rows land on the F output where you can inspect them.

Or set the real type once with [Select](select.md) and avoid casts afterwards.

### The read-only guard

Expressions can only **read** the table that flows through the node. The text is checked first, then run in a locked engine with file and network access switched off. What is rejected:

| What | Example | Code |
|---|---|---|
| More than one statement (anything after a semicolon) | `[id] = 1; SELECT 2` | `TD-SHAPE-110` Only one statement is allowed |
| A statement that is not a plain query (`COPY`, `ATTACH`, `INSTALL`, `LOAD`, `PRAGMA`, `DESCRIBE`, `SHOW`, `EXPLAIN` ...) | `COPY t TO 'x.csv'` | In an expression box these cannot start a statement, so they fail as a syntax error: `TD-SHAPE-113` in Multi-Field Formula, `TD-SHAPE-004` with the engine's message in Filter and Formula. `TD-SHAPE-111` (Only SELECT queries are allowed) is the code when a whole query box holds such a statement, for example in the SQL Query node. After a semicolon they are `TD-SHAPE-110`. |
| File, system and random functions: `read_csv`, `read_parquet` and every `read_*`, `glob`, `*_scan`, `query`, `duckdb_*`, `pragma_*`, `current_setting`, `getenv`, `random`, `uuid`, `gen_random_uuid`, `setseed` | `read_csv('x.csv')`, `random()`, `uuid()` | `TD-SHAPE-112` This function is not allowed (files, system or random) |
| Reading a file as a table | `... FROM 'a.csv'` | `TD-SHAPE-112` Reading files is not allowed |
| Dollar-quoted text (`$$...$$`), `E'...'` strings, control characters | | `TD-SHAPE-112` |
| Text the engine cannot parse or run | | `TD-SHAPE-113` in Multi-Field Formula; `TD-SHAPE-004` with the engine's message in Filter and Formula |
| Longer than 20,000 characters | | `TD-SHAPE-114` The SQL is too long |
| Running longer than 25 seconds | | `TD-SHAPE-115` The query took too long |
| Multi-Field Formula without `{col}` | | `TD-SHAPE-120` The formula must contain {col} |

Why `random()` and `uuid()` are blocked: a workflow must give the same result every time it runs on the same data, which matters for audit evidence. For a reproducible random split use [Split](split.md) with a fixed seed, or the sampling node in [Audit nodes](../audit/index.md).

A semicolon inside quoted text or a `--` comment is fine: `[note] LIKE '%;%'`.

Typical fixes:

| You see | Do this |
|---|---|
| `explicit cast is required` or `No function matches ... VARCHAR` | Wrap the column in `TRY_CAST(... AS DOUBLE)` (or `DATE`, `INTEGER`). |
| `Referenced column "x" not found` | The name is misspelt, or the column does not exist at this point in the workflow. |
| `syntax error at or near ...` | Check brackets, quotes and commas. |
| `TD-SHAPE-112` | Remove the file, system or random function. |

---

## Error codes at a glance

When a Preparation node cannot finish, its message starts with a code. These are the codes and what to do:

| Code | Meaning | What to do |
|---|---|---|
| `TD-SHAPE-001` | A required setting is missing | Fill in the missing setting |
| `TD-SHAPE-002` | An output column name is empty, duplicated or already exists | Choose a unique name |
| `TD-SHAPE-003` | A selected column is not in the input any more | Select the column again |
| `TD-SHAPE-004` | A setting value is out of range or unknown. Filter and Formula also use it for SQL problems, with the engine's explanation | Pick a value from the list or inside the range; fix the expression |
| `TD-SHAPE-005` | A required input has no data | Connect and fix the upstream node |
| `TD-SHAPE-040` | The pattern is not a valid regular expression | Escape special characters with a backslash |
| `TD-SHAPE-041` | The pattern is too long | Shorten the pattern |
| `TD-SHAPE-042` | Find text is empty | Type the text to find |
| `TD-SHAPE-043` | Too many rules | Remove rules or split them over two nodes |
| `TD-SHAPE-044` | The column must be text | Convert the column to text with a Select node |
| `TD-SHAPE-050` | The column is not a date and not text | Choose a date or text column |
| `TD-SHAPE-052` | A holiday is not a YYYY-MM-DD date | Type holidays as year-month-day |
| `TD-SHAPE-053` | Working days must name at least one weekday | Tick at least one weekday |
| `TD-SHAPE-101` | The split pattern can match nothing | Use `\s+` not `\s*` |
| `TD-SHAPE-110` | Only one statement is allowed | Remove everything after the first statement |
| `TD-SHAPE-111` | Only SELECT queries are allowed | Write a read-only query; changing data or settings is not allowed |
| `TD-SHAPE-112` | The SQL uses a function or file access that is not allowed | Remove file-reading, system or random functions |
| `TD-SHAPE-113` | The SQL could not be parsed or run | Check the SQL syntax |
| `TD-SHAPE-114` | The SQL is too long | Shorten the SQL |
| `TD-SHAPE-115` | The query took too long | Simplify the query or filter the data first |
| `TD-SHAPE-120` | The formula must use the column placeholder | Write `{col}`, for example `UPPER({col})` |

The codes `TD-SHAPE-060` to `-091` belong to the Join, Transform and Audit nodes and are described on their pages.

