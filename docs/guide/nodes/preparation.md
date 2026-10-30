# Preparation nodes

Preparation nodes clean, reshape and enrich a table before you analyse it. They are the first nodes you place after an input node: fix the types, remove the rubbish, add the columns you need, then pass the table on to joins, audit tests or reports.

This page covers all 16 Preparation nodes in the palette.

## Contents

1. [How Preparation nodes work](#how-preparation-nodes-work) (read this first)
2. [Writing SQL expressions](#writing-sql-expressions) (for Filter, Formula and Multi-Field Formula)
3. [Cleansing](#cleansing)
4. [Filter](#filter)
5. [Formula](#formula)
6. [Aggregate](#aggregate)
7. [Select](#select)
8. [Sort](#sort)
9. [Unique](#unique)
10. [Split](#split)
11. [Rows](#rows)
12. [Normalize](#normalize)
13. [Record ID](#record-id)
14. [Select Records](#select-records)
15. [Find and Replace](#find-and-replace)
16. [Date Helper](#date-helper)
17. [Text to Columns](#text-to-columns)
18. [Multi-Field Formula](#multi-field-formula)
19. [Error codes at a glance](#error-codes-at-a-glance)

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
- **CSV and Excel text.** Files read as CSV usually give you **text** columns, even when the values look like numbers or dates. Many nodes offer fewer choices for text columns. Convert the type first with [Select](#select) (Data Type column) or with `TRY_CAST` in a [Formula](#formula).
- **Nulls** (empty cells) stay empty unless a node says otherwise.

### Reading the Config Dock

The **Config Dock** is the panel that shows the settings of the selected node. Buttons are icon-only: hover over one to see its name. The paired **All** and **None** buttons in Select are the only text buttons.

---

## Writing SQL expressions

[Filter](#filter) (Expression mode), [Formula](#formula) and [Multi-Field Formula](#multi-field-formula) accept **SQL expressions**. You do not write a whole query, only the expression:

- Formula and Multi-Field Formula take an expression that produces a value, for example `[Amount] * 1.2`.
- Filter takes a condition that is true or false, for example `[Amount] > 100`. Think of it as the text after `WHERE`.

Expressions run on the DuckDB engine, so DuckDB's SQL functions are available.

### Column names: square brackets (Formula and Filter)

Put a column name in square brackets: `[Invoice Amount]`. Spaces in names are fine. Matching ignores upper and lower case, and spaces just inside the brackets are ignored, so `[invoice amount]` and `[ Invoice Amount ]` both find `Invoice Amount`.

- Only names that exist in the input (and, in Formula, columns created by earlier formulas in the same node) are recognised. An unknown name is not a column, and the engine reports an error such as `Referenced column "nope" not found`.
- Brackets inside quoted text are left alone: `'[x]'` is the text `[x]`.
- **Text goes in single quotes**: `'paid'`. Double quotes are accepted for text too (`"paid"` is read as `'paid'`), because only `[...]` means a column.
- Inside text, write a quote as two quotes: `'O''Brien'`.
- Multi-Field Formula does not use brackets. It uses `{col}` and `{name}`; see [Multi-Field Formula](#multi-field-formula).

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

Or set the real type once with [Select](#select) and avoid casts afterwards.

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

Why `random()` and `uuid()` are blocked: a workflow must give the same result every time it runs on the same data, which matters for audit evidence. For a reproducible random split use [Split](#split) with a fixed seed, or the sampling node in [Audit nodes](audit.md).

A semicolon inside quoted text or a `--` comment is fine: `[note] LIKE '%;%'`.

Typical fixes:

| You see | Do this |
|---|---|
| `explicit cast is required` or `No function matches ... VARCHAR` | Wrap the column in `TRY_CAST(... AS DOUBLE)` (or `DATE`, `INTEGER`). |
| `Referenced column "x" not found` | The name is misspelt, or the column does not exist at this point in the workflow. |
| `syntax error at or near ...` | Check brackets, quotes and commas. |
| `TD-SHAPE-112` | Remove the file, system or random function. |

---

## Cleansing

<img src="../../../src/trigger_designer/resources/qt/images/node_icons/Preparation/Cleansing.svg" alt="Cleansing icon" width="32" height="32">

**What it does.** Removes empty rows and columns, fills empty cells with neutral defaults, and tidies text (spaces, letters, digits, punctuation, upper or lower case) in the columns you choose.

**When to use it.** Right after reading a file with untidy text: stray spaces that stop two vendor names matching, empty cells that break arithmetic, mixed case.

**Inputs and outputs.**

| Socket | Carries |
|---|---|
| Input | The table to clean |
| Out | The cleaned table (same columns, unless "Remove all-null columns" removes some) |

**Settings.** The node applies them in this order: remove nulls, replace nulls, whitespace, characters, case.

| Section | Control | Default | Effect |
|---|---|---|---|
| Fields | **Clean** (column checklist) | none ticked | The columns the **text rules** apply to (whitespace, characters, case) and "Remove rows null in selected". With nothing ticked the text rules do nothing. The null replacement rules are **not** limited to these columns. |
| Nulls | Remove all-null rows | off | Deletes rows where every cell is empty. |
| Nulls | Remove rows null in selected | off | Deletes rows where any ticked **Clean** column is empty. Greyed out until you tick a column. |
| Nulls | Remove all-null columns | off | Deletes columns where every cell is empty. |
| Nulls | Replace null text with '' | **on** | Every empty cell in a **text** column becomes an empty text. |
| Nulls | Replace null numbers with 0 | **on** | Every empty cell in a number column becomes 0. |
| Whitespace and characters | Trim whitespace | **on** | Removes spaces at the start and end of the text in the ticked columns. |
| Whitespace and characters | Collapse inner spaces | **on** | Turns runs of spaces inside the text into one space (this also trims the ends, even if Trim is off). |
| Whitespace and characters | Remove all whitespace | off | Deletes every space, tab and line break. Wins over collapsing. |
| Whitespace and characters | Remove letters | off | Deletes letters (Latin including accented letters, and basic Cyrillic). |
| Whitespace and characters | Remove numbers | off | Deletes digits. |
| Whitespace and characters | Remove punctuation | off | Deletes punctuation such as `. , ; : ! ? - ( )`. |
| Case | **Case** | None | None, Lower Case, Upper Case, or Title Case (first letter of each word upper, the rest lower). |

With no column ticked under **Clean**, only the null rules run. Because the two null replacements are on by default, all empty text cells become blank text and all empty numbers become 0. Untick them if empty cells must stay empty.

**Worked example.** Input:

| Name | Amount | Note |
|---|---|---|
| `  alice   smith ` | 10 | a1! |
| BOB  jones | *(empty)* | b2? |
| *(empty)* | 5 | *(empty)* |
| carol-ann | 7 | c3. |

Settings: Clean = Name and Note; Remove punctuation on; Case = Title Case; everything else at its default.

| Name | Amount | Note |
|---|---|---|
| Alice Smith | 10 | A1 |
| Bob Jones | 0 | B2 |
| *(empty text)* | 5 | *(empty text)* |
| Carolann | 7 | C3 |

A second run on the same input: Clean = Name, "Remove rows null in selected" on, both "Replace null ..." options off, other text rules at their defaults. The row where Name is empty is removed and the empty Amount stays empty:

| Name | Amount | Note |
|---|---|---|
| alice smith | 10 | a1! |
| BOB jones | *(empty)* | b2? |
| carol-ann | 7 | c3. |

**Edge cases and limits.**

- [Preview uses 100 rows](#preview-vs-run).
- Text rules only touch **text** columns. Ticking a number column under **Clean** does nothing for it.
- "Replace null text" and "Replace null numbers" leave dates, yes/no columns and other types empty.
- Removing punctuation also removes hyphens and apostrophes (`carol-ann` becomes `carolann`).
- Title Case lowercases the rest of each word (`BOB jones` becomes `Bob Jones`).
- An empty input returns an empty table.

**Messages you may see.** `TD-SHAPE-005` (no input data). Cleansing has no setting that can be invalid.

**Tips.**

- Put Cleansing before a [Join](join.md) or [Unique](#unique): trimming and case-folding key columns prevents "Acme " and "ACME" counting as different.
- Use [Find and Replace](#find-and-replace) for specific substitutions and Cleansing for general tidying.
- To keep the original next to the cleaned text, use Find and Replace with "Keep original".

---

## Filter

<img src="../../../src/trigger_designer/resources/qt/images/node_icons/Preparation/Filter.svg" alt="Filter icon" width="32" height="32">

**What it does.** Splits a table into the rows that meet a condition and the rows that do not. Nothing is deleted: both groups come out, on two sockets.

**When to use it.** Isolate high-value transactions, pull out one vendor, separate postings outside a date window, or list the rows that fail a rule.

**Inputs and outputs.**

| Socket | Carries |
|---|---|
| Input | The table to filter |
| **T** (true) | Rows where the condition is true |
| **F** (false) | Every other row, including rows where the condition could not be decided (empty cells) |

T and F together always contain every input row exactly once.

**Settings.** A switch at the top picks the mode.

| Control | Default | Effect |
|---|---|---|
| **Simple / Expression** switch | Simple | Simple builds one condition on one column. Expression takes a SQL condition. |

*Simple mode*

| Control | Default | Effect |
|---|---|---|
| **Column** | "(select column)" | The column to test. A saved column that is no longer in the input is shown as "name (missing)". |
| **Operation** | Equals | The list depends on the column's type (below). |
| **Value** | empty (placeholder "Enter filter value...") | The value to compare with. |
| **Max value** | empty (placeholder "Enter max value...") | Shown only for **In Between**: the upper bound. |

| Column type | Operations offered |
|---|---|
| Text | Equals, Not Equals, Contains |
| Number | Equals, Not Equals, Less Than, Greater Than, Less Than or Equal, Greater Than or Equal, In Between |
| Date or time (real dates, not text) | the same list as numbers (see the edge cases) |
| Other (for example yes/no) | Equals, Not Equals |

*Expression mode*

| Control | Default | Effect |
|---|---|---|
| SQL editor (placeholder: `Filter rows with SQL, e.g.:` / `[order_value] in_between (0, 500) AND [status] = 'paid'`) | empty | A SQL condition; see [Writing SQL expressions](#writing-sql-expressions). Errors show under the editor as you type. |

If the condition is empty (Simple mode: no column or no value; Expression mode: no text), every row goes to **T** and **F** is empty. A chip says "No condition: rows pass through" or "Incomplete condition: rows pass through".

**Worked example (Simple).** Input:

| id | status | order_value | region |
|---|---|---|---|
| 1 | paid | 120 | N |
| 2 | open | 900 | S |
| 3 | paid | abc | N |
| 4 | void | 450 | *(empty)* |

Simple, Column = status, Operation = Equals, Value = paid. T holds rows 1 and 3, F holds rows 2 and 4.

**Worked example (Expression).** Same input:

```sql
TRY_CAST([order_value] AS DOUBLE) in_between (100, 500) AND [status] <> 'void'
```

T:

| id | status | order_value | region |
|---|---|---|---|
| 1 | paid | 120 | N |

F holds rows 2, 3 and 4. Row 3 (`abc`) is on F because `TRY_CAST` made it empty, so the condition could not be true. Row 2 is outside 100 to 500; row 4 is `void`.

Writing `[order_value] > 200` instead fails with `Cannot compare values of type VARCHAR and type INTEGER_LITERAL - an explicit cast is required`, because the column is text. See [the type pitfall](#the-type-pitfall-csv-columns-arrive-as-text).

**Edge cases and limits.**

- [Preview uses 100 rows](#preview-vs-run); Run filters everything.
- Empty cells: a comparison with an empty cell is neither true nor false, so those rows go to **F**. That includes "Not Equals" in Simple mode.
- Simple mode, numbers: the Value must be a number, otherwise `TD-SHAPE-004` ("Filter value must be a number"). **In Between** includes both ends, and if you type the bigger number first the two are swapped.
- Simple mode, **Contains** on text is **case-sensitive** and the value is read as a pattern (a regular expression). Letters and digits behave like plain text, but characters such as `.` or `(` do not (a lone `(` is invalid and stops the node). For a plain, case-insensitive search use Expression mode: `[name] ILIKE '%acme%'`.
- Simple mode on a real date column (not text): the date operations are offered, but a typed date Value is not read as a date and the node fails. Use Expression mode, for example `[posted] >= DATE '2024-01-01'`.
- Simple mode tests one column. For several conditions use Expression with `AND` / `OR`, or chain two Filters.
- Expression mode is protected by the [read-only guard](#the-read-only-guard).

**Messages you may see.**

| Code | When | Fix |
|---|---|---|
| `TD-SHAPE-003` | The Simple column is not in the input | Pick the column again |
| `TD-SHAPE-004` | The Value is not a number; or the SQL engine rejected the condition (the text after the code is the engine's explanation, for example a missing column or "an explicit cast is required") | Correct the value; use `TRY_CAST` |
| `TD-SHAPE-110`, `-112`, `-114`, `-115` | The expression breaks the [read-only guard](#the-read-only-guard) | Remove the offending part |
| `TD-SHAPE-005` | No input data | Fix the upstream node |

**Tips.**

- Use the **F** output as an exception list and connect it to a report.
- `in_between (a, b)` works only in Filter. In a Formula write `BETWEEN a AND b`.
- A Filter followed by [Aggregate](#aggregate) gives totals for just the rows you care about.

---

## Formula

<img src="../../../src/trigger_designer/resources/qt/images/node_icons/Preparation/Formula.svg" alt="Formula icon" width="32" height="32">

**What it does.** Adds calculated columns, or replaces the values of an existing column, using SQL expressions. One node holds up to **five** formulas; each can use the columns created by the ones above it.

**When to use it.** Convert text to numbers or dates, compute a total or variance, build a category, combine columns, flag exceptions.

**Inputs and outputs.**

| Socket | Carries |
|---|---|
| Input | The table to add columns to |
| Out | The same rows with the new or changed columns |

**Settings.** The Config Dock shows one **card** per formula. The dock toolbar has an **Add formula** (plus) icon button and each card has a **Remove formula** icon button. A new node starts with one empty card.

| Control | Default | Effect |
|---|---|---|
| **Target column** (drop-down) | "Select target column" | Where the result goes. Choose an existing column to **replace** it, or **+ add column** to create a new one (an "Add Column" box asks for the name). Columns made by earlier cards are listed too. |
| **Data type** (drop-down) | Auto | Used only for a **new** column. Choices: Auto, String, Integer, Float, Boolean, Date, Datetime, Time, Categorical. Auto keeps whatever the SQL produces. If the target is an existing column the box is greyed and shows that column's type. |
| Formula (SQL editor; placeholder `Enter formula e.g.:` / `CASE WHEN [Age] > 30 THEN 'Adult' ELSE 'Young' END`) | empty | A SQL expression; see [Writing SQL expressions](#writing-sql-expressions). Drag the grip under the editor to make it taller. A message under the editor explains any error. |
| Card header arrow | expanded | Collapse a card. |

A card counts only when it has both a target column and a formula. Cards without both are skipped; if none counts, the table passes through unchanged. Formulas run top to bottom, so a later card may use a column created by an earlier one.

When a formula **replaces** an existing column, the result keeps whatever type the SQL produces; the Data type box is not applied. To force a type, create a new column and choose the Data type, or use `CAST` in the formula.

The dock chips show how many columns the input has and how many formulas are set, for example "2 of 3 formulas".

**Worked example.** Input (all text):

| id | vendor | order_value | date |
|---|---|---|---|
| 1 | Acme | 120.50 | 2024-01-31 |
| 2 | Beta | 900 | 2024-02-15 |
| 3 | Acme | abc | 2024-03-01 |
| 4 | Cole | 450 | 2024-03-31 |

One formula: new column `value_num`, formula `TRY_CAST([order_value] AS DOUBLE)`.

| id | vendor | order_value | date | value_num |
|---|---|---|---|---|
| 1 | Acme | 120.50 | 2024-01-31 | 120.5 |
| 2 | Beta | 900 | 2024-02-15 | 900.0 |
| 3 | Acme | abc | 2024-03-01 | *(empty)* |
| 4 | Cole | 450 | 2024-03-31 | 450.0 |

Two formulas in one node:

```sql
-- formula 1: new column "size"
CASE WHEN TRY_CAST([order_value] AS DOUBLE) >= 400 THEN 'Large'
     WHEN TRY_CAST([order_value] AS DOUBLE) IS NULL THEN 'Unreadable'
     ELSE 'Small' END
-- formula 2: existing column "vendor"
UPPER([vendor]) || '-' || CAST([id] AS VARCHAR)
```

| id | vendor | order_value | date | size |
|---|---|---|---|---|
| 1 | ACME-1 | 120.50 | 2024-01-31 | Small |
| 2 | BETA-2 | 900 | 2024-02-15 | Large |
| 3 | ACME-3 | abc | 2024-03-01 | Unreadable |
| 4 | COLE-4 | 450 | 2024-03-31 | Large |

**Edge cases and limits.**

- [Preview uses 100 rows](#preview-vs-run). The card also trial-runs the formula on the first 100 rows so errors such as "text plus number" show before you Run.
- At most **five** formulas per node; extra ones are dropped. Chain two Formula nodes for more, or use [Multi-Field Formula](#multi-field-formula) to apply one rule to many columns.
- Results are stored as the app's standard types (whole numbers, decimals, text, dates, yes/no); unusual SQL result types are converted.
- Empty cells: most functions return empty when an input is empty. Use `COALESCE([x], 0)` to substitute a value.
- Failed conversions: `TRY_CAST` gives an empty cell; `CAST` stops the node with an error.
- Each formula is one expression and is protected by the [read-only guard](#the-read-only-guard).

**Messages you may see.** The text after the code starts with the formula number, for example `Section 2: ...`.

| Code | When | Fix |
|---|---|---|
| `TD-SHAPE-004` | The SQL engine rejected the formula: a type mismatch (`No function matches ... VARCHAR`), an unknown column (`Referenced column "x" not found`), a syntax error | Use `TRY_CAST`; check column names and brackets |
| `TD-SHAPE-110`, `-112`, `-114`, `-115` | Breaks the [read-only guard](#the-read-only-guard) | Remove the offending part |
| `TD-SHAPE-005` | No input data | Fix the upstream node |

**Tips.**

- Work in steps: one card cleans the text, the next converts it, the next calculates. The preview shows the result of each.
- Name new columns clearly (`amount_num`, `is_late`) so later nodes and reports are readable.
- Yes/no formulas such as `[amount_num] > 1000` make good flag columns for a [Filter](#filter).

---

## Aggregate

<img src="../../../src/trigger_designer/resources/qt/images/node_icons/Preparation/Groupby.svg" alt="Aggregate icon" width="32" height="32">

**What it does.** Summarises the table: one output row for each combination of the group columns, with counts, totals, averages and similar measures. (Saved workflows and older documents call this node GroupBy.)

**When to use it.** Total by vendor or month, transactions per user, the largest posting per account, the number of distinct approvers per supplier.

**Inputs and outputs.**

| Socket | Carries |
|---|---|
| Input | The detailed table |
| Out | The summary: group columns first, then one column per measure |

**Settings.**

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

For a **text** column only GroupBy, Count, Min, Max, First, Last, N_Unique and List are offered. Sum, Mean, Std, Var and Median need a number column, so a CSV amount that arrived as text must be converted first ([Select](#select) or [Formula](#formula)).

The dock chips show the number of keys and measures ("2 keys", "1 measure").

**Worked example.** Input:

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

**Edge cases and limits.**

- [Preview uses 100 rows](#preview-vs-run): totals in the preview are totals of the sample.
- **One action per column.** To get both the sum and the count of `amount`, use two Aggregate nodes, or copy the column with a [Formula](#formula) first.
- Groups come out in order of first appearance, not sorted. Add a [Sort](#sort) after it.
- Empty cells: Sum, Mean, Min and Max ignore them; **Count** counts every row of the group.
- Empty group keys form a group of their own.
- With no actions, or when none of the fields exist, the table passes through unchanged. A chip "n field(s) missing" warns about missing fields.
- Output names must be unique and must not repeat a group column name (`TD-SHAPE-002`).

**Messages you may see.** `TD-SHAPE-002` (duplicate output name: choose a unique name), `TD-SHAPE-004` (unknown action), `TD-SHAPE-005` (no input data).

**Tips.**

- To total only a subset, put a [Filter](#filter) in front.
- Rename output columns to something a reader will understand before they reach a report.
- Use List to see the values behind a total while you investigate, then remove it before exporting.

---

## Select

<img src="../../../src/trigger_designer/resources/qt/images/node_icons/Preparation/Select.svg" alt="Select icon" width="32" height="32">

**What it does.** Chooses which columns to keep, in what order, under what name and with what data type. It is the main place to turn text columns into numbers and dates.

**When to use it.** Right after reading a file: drop columns you do not need, give columns readable names, and set the type of each column so later nodes can calculate and sort correctly.

**Inputs and outputs.**

| Socket | Carries |
|---|---|
| Input | The table |
| Out | Only the ticked columns, in the dock's order, renamed and converted |

**Settings.** The Config Dock shows a toolbar above a table with one row per input column.

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

**Worked example.** Input (all text, as from a CSV):

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

**Edge cases and limits.**

- [Preview uses 100 rows](#preview-vs-run): conversion problems later in the file show only on Run.
- A failed conversion becomes an empty cell **silently**. After converting, look for new empty cells (for example a [Filter](#filter) with `[amount] IS NULL`) to find values that did not convert.
- A column that disappeared upstream stays in the list flagged as missing until you remove it; it is skipped in the output.
- Keep new names unique.

**Messages you may see.** `TD-SHAPE-005` (no input data). Other problems show the engine's message.

**Tips.**

- Make Select the first node after an input node and fix the types once; every later node benefits.
- Use **Auto-Detect Types (All)** as a starting point, then check Date columns for day and month order.
- Untick columns that hold personal data you do not need before building reports.

---

## Sort

<img src="../../../src/trigger_designer/resources/qt/images/node_icons/Preparation/Sort.svg" alt="Sort icon" width="32" height="32">

**What it does.** Orders the rows by one or more columns.

**When to use it.** Put the biggest amounts first, order by date for a review, or sort before [Select Records](#select-records) or a report.

**Inputs and outputs.**

| Socket | Carries |
|---|---|
| Input | The table |
| Out | The same rows in the new order |

**Settings.** One section, **Sort**, holding a list of sort keys (up to 10). The first key is the main one; later keys break ties.

| Control | Default | Effect |
|---|---|---|
| **Column** (per key) | empty | The column to sort by. |
| **Order** (per key) | Ascending | Ascending or Descending. |

Keys without a column are ignored. With no valid key the table passes through unchanged. A chip "n sort key(s) missing" warns when a chosen column is no longer in the input.

**Worked example.** Input:

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

**Edge cases and limits.**

- [Preview uses 100 rows](#preview-vs-run): the preview order is the order of the sample only.
- **Text columns sort as text**: `"100"` comes before `"25"`. Convert amounts with [Select](#select) first.
- Rows with equal keys may keep any relative order; add another key if the order must be repeatable.
- Maximum 10 keys.

**Messages you may see.** `TD-SHAPE-005` only.

**Tips.** Sort after an [Aggregate](#aggregate) so the summary reads largest first.

---

## Unique

<img src="../../../src/trigger_designer/resources/qt/images/node_icons/Preparation/Unique.svg" alt="Unique icon" width="32" height="32">

**What it does.** Finds duplicates. One output keeps the first row of each distinct key; the other lists every row that belongs to a duplicated key.

**When to use it.** Duplicate invoices, repeated payments, duplicate vendor records. The Duplicates output is your exception list.

**Inputs and outputs.**

| Socket | Carries |
|---|---|
| Input | The table |
| **Unique** | The first row of each distinct combination of the chosen columns, in input order |
| **Duplicates** | **Every** row (including the first) whose combination appears more than once |

**Settings.**

| Control | Default | Effect |
|---|---|---|
| **Columns** (checklist, section "Duplicate key") | none ticked | Rows that match on **all** ticked columns are duplicates. |

With no column ticked all rows go to **Unique** and **Duplicates** is empty. The dock summary reads "n columns selected".

**Worked example.** Input:

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

**Edge cases and limits.**

- [Preview uses 100 rows](#preview-vs-run): a duplicate whose second copy lies beyond row 100 does not appear in the preview.
- Matching is exact: `Acme`, `acme` and `Acme ` are different. Clean the key columns first ([Cleansing](#cleansing)).
- Empty cells match each other: two rows with an empty key in the same position are duplicates.
- Unique keeps the **first** occurrence in the input; sort first if you want the latest or largest.
- Chosen columns that are no longer in the input are ignored.

**Messages you may see.** `TD-SHAPE-005` only.

**Tips.**

- To find duplicate invoices tick vendor, invoice number and amount.
- For tolerance-based or near-duplicate tests see the Duplicates test in [Audit nodes](audit.md); use Unique for quick exact checks.

---

## Split

<img src="../../../src/trigger_designer/resources/qt/images/node_icons/Preparation/Split.svg" alt="Split icon" width="32" height="32">

**What it does.** Divides the rows into two groups by percentage: an **Estimation** group and a **Validation** group (the usual build and test split).

**When to use it.** Develop a rule on one part of the data and test it on the rest, or take a reproducible portion of a population.

**Inputs and outputs.**

| Socket | Carries |
|---|---|
| Input | The table |
| **E** (Estimation) | The first part, sized by Estimation % |
| **V** (Validation) | The rest |

**Settings.** One section, **Split**. Its info line reads "Estimation rows first; the rest go to Validation."

| Control | Default | Effect |
|---|---|---|
| **Method** | Random | Random shuffles the rows first. Sequential keeps the input order. |
| **Estimation %** | 70 | 1 to 99: the share that goes to E. |
| **Random seed** | 42 | 0 to 2,147,483,647. Shown only for Random. The same seed on the same data always gives the same split. |

**Worked example.** Ten rows numbered 1 to 10, Estimation % = 70.

- Sequential: E gets rows 1 to 7, V gets rows 8 to 10.
- Random with seed 42: E gets rows 2, 1, 7, 3, 6, 4, 5 (in shuffled order) and V gets 10, 9, 8.

**Edge cases and limits.**

- The split point is "row position below (number of rows minus 1) times the percentage", so sizes are **close to** the percentage, not always exact. With 5 rows and 50 percent, 2 rows go to E and 3 to V. With a single row, E is empty and the row goes to V.
- In Random mode rows come out in shuffled order, not input order.
- [Preview uses 100 rows](#preview-vs-run): the preview splits the sample, Run splits the whole table, so the rows that land in E and V differ.
- This is not a statistical sampler; for audit samples use the Sample test in [Audit nodes](audit.md).

**Messages you may see.** `TD-SHAPE-004` ("Estimation percent must be between 1 and 99"), `TD-SHAPE-005`.

**Tips.** Record the seed with your workpapers so someone else can reproduce the split.

---

## Rows

<img src="../../../src/trigger_designer/resources/qt/images/node_icons/Preparation/Dynamic%20Row%20Generate.svg" alt="Rows icon" width="32" height="32">

**What it does.** Generates a column of sequence values (numbers, dates or text) and places it next to the input table. In code and some older documents this node is called Dynamic Row Builder.

**When to use it.** Add a simple counter, a series of dates, or a test column. To number the rows of a real table, [Record ID](#record-id) is usually the better choice.

**Inputs and outputs.**

| Socket | Carries |
|---|---|
| Input | A table (the node needs a connected input) |
| Out | The input columns plus the new column |

**Settings.**

| Control | Default | Effect |
|---|---|---|
| **Name** | `counter` | Name of the generated column. Must not be empty. |
| **Type** | Int | Int, Float, Text or Date/time. Changing the type converts the values where possible. |
| **Start** | 1 | First value. |
| **Increment** | 1 | The step. For Date/time it is a number of **seconds**. For Text it is the text appended at each step. |
| **End** | 10 | Last value, **included**. Not shown for Text. |

Starting values when you switch type: Int 1 / 1 / 10; Float 1.0 / 1.0 / 10.0; Text A / 1 / Z; Date/time 2024-01-01 00:00, 3600 seconds, 2024-01-02 00:00.

**Worked example.** Input of three rows (`a` = x, y, z). Name `n`, Type Int, Start 10, Increment 10, End 30:

| a | n |
|---|---|
| x | 10 |
| y | 20 |
| z | 30 |

With Type Date/time, Start 2024-01-01 00:00, Increment 86400, End 2024-01-03 00:00 the same three rows get `2024-01-01 00:00:00`, `2024-01-02 00:00:00` and `2024-01-03 00:00:00`.

**Edge cases and limits.**

- **The number of generated values must equal the number of input rows.** The new column is attached side by side with the input. With a different count the node stops with `TD-SHAPE-130` ("The generated rows do not match the input rows"), which states both counts. Set Start, Increment and End so the count matches, and remember the live preview only sees the first 100 input rows.
- At most **10,000 values** are generated; the chip "Reached 10,000 rows" warns when the cap is hit (for example Increment 0).
- **Text** type has no End: it keeps appending the Increment text (`A`, `A1`, `A11`, ...) up to the 10,000 cap, so it only fits an input of exactly 10,000 rows. Use Int, Float or Date/time in practice.
- Int and Float stop when the value goes past End. If Start is already past End no values are produced.
- Date/time values have no time zone.

**Messages you may see.** `TD-SHAPE-001` (empty name), `TD-SHAPE-004` (unknown type), `TD-SHAPE-005` (no input data), `TD-SHAPE-130` (generated count differs from the input row count).

**Tips.** Count the input rows first (an [Aggregate](#aggregate) with Count) before you set End.

---

## Normalize

<img src="../../../src/trigger_designer/resources/qt/images/node_icons/Preparation/Select.svg" alt="Normalize icon" width="32" height="32">

**What it does.** Tidies the **column names**, not the values: trims spaces, turns spaces into underscores or removes them, and changes case. (The palette entry is "Normalize Columns"; the node uses the Select icon.)

**When to use it.** Files from different systems name the same column differently (`Net Amount`, `net amount `, `NET_AMOUNT`). Normalize gives them one pattern so formulas and joins do not trip over stray spaces.

**Inputs and outputs.**

| Socket | Carries |
|---|---|
| Input | The table |
| Out | The same data with new column names |

**Settings.** Rules apply in the order trim, whitespace, case.

| Section | Control | Default | Effect |
|---|---|---|---|
| Name rules | **Trim spaces** | on | Removes spaces at the start and end of the name. |
| Name rules | **Spaces to underscores** | on | Each run of spaces inside the name becomes `_`. |
| Name rules | **Remove all whitespace** | off | Deletes spaces entirely. Wins over underscores. |
| Name rules | **Case** | None | None, Lower Case, Upper Case, Title Case (first letter of each word upper, the rest lower). |
| Columns | **Normalize** (checklist) | none ticked | The columns to rename. **Empty means every column.** |

**Worked example.** Input columns: `Customer ID`, `  Order Date ` (spaces around it), `Net Amount`. Case = Lower Case.

Output columns: `customer_id`, `order_date`, `net_amount`.

With "Remove all whitespace" on and Title Case, `Customer ID` becomes `Customerid` and `Order  Date` becomes `Orderdate`.

**Edge cases and limits.**

- If two names end up identical (`Net Amount` and `net amount` with Lower Case), the node stops with `TD-SHAPE-002` and names the duplicate. Untick one of the columns or rename it first.
- A rule never produces an empty name; the original name is kept.
- Only names change; data and types are untouched. Check any [Select](#select) or [Formula](#formula) that refers to the old names.
- Normalize reads no row data, so the [100-row preview](#preview-vs-run) makes no difference.

**Messages you may see.** `TD-SHAPE-002` (the rules give a duplicate column name: tick fewer columns or change the rules), `TD-SHAPE-005`.

**Tips.** Place it directly after the input node, before anything refers to column names.

---

## Record ID

<img src="../../../src/trigger_designer/resources/qt/images/node_icons/Preparation/RecordID.svg" alt="Record ID icon" width="32" height="32">

**What it does.** Adds a column of whole numbers that numbers the rows (1, 2, 3, ...), optionally restarting for each group and ordered by other columns.

**When to use it.** Give each row a stable reference for workpapers, number the lines within each invoice or journal, or rank rows inside a group.

**Inputs and outputs.**

| Socket | Carries |
|---|---|
| Input | The table |
| Out | The same rows, in the same order, plus the ID column |

**Settings.**

| Section | Control | Default | Effect |
|---|---|---|---|
| (top) | **Name** (placeholder `RecordID`) | `RecordID` | Name of the new column; it must be new. Hint: "Dense Int64 numbers. The column name must be new." |
| (top) | **Start at** | 1 | First number (-1,000,000,000 to 1,000,000,000). |
| (top) | **Position** | First | First puts the column on the left, Last on the right. |
| Grouping & order (collapsible) | **Groups** | none | Numbering restarts at the start value for each combination of these columns. |
| Grouping & order | **Order by** (list) | none | Decides which rows get the smaller numbers; each entry has a **Column** and a **Descending** tick. |

A note in the dock reads: "Rows keep input order. This only changes the numbers." Order by never reorders the table.

**Worked example.** Input:

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

**Edge cases and limits.**

- [Preview uses 100 rows](#preview-vs-run): preview numbers cover the sample only. Without Groups and Order by, the number is simply the row position.
- Rows tied on the Order by columns keep their input order. Empty values in an Order by column are numbered last.
- Name must not be empty (`TD-SHAPE-001`) and must not already exist (`TD-SHAPE-002`).
- Group and order columns must exist (`TD-SHAPE-003`).

**Messages you may see.** `TD-SHAPE-001`, `TD-SHAPE-002`, `TD-SHAPE-003`, `TD-SHAPE-005`.

**Tips.** Record ID after a [Sort](#sort) gives a ranking; with Groups it gives a "line number within invoice".

---

## Select Records

<img src="../../../src/trigger_designer/resources/qt/images/node_icons/Preparation/SelectRecords.svg" alt="Select Records icon" width="32" height="32">

**What it does.** Picks rows by position or rank: the first or last N, a range of row numbers, or the largest or smallest N by a column. What is not picked goes to the second output.

**When to use it.** Top 10 payments, the 5 oldest entries per account, rows 200 to 300 of an extract.

**Inputs and outputs.**

| Socket | Carries |
|---|---|
| Input | The table |
| **S** (Selected) | The chosen rows |
| **R** (Remaining) | Everything else |

**Settings.** One section, **Mode**. A note says "Only the fields used by the chosen mode appear below."

| Control | Default | Shown for | Effect |
|---|---|---|---|
| **Mode** | First | always | First, Last, Range, Large, Small. |
| **N** | 10 | First, Last, Large, Small | How many rows (1 to 100,000,000). |
| **From row** / **To row** | 1 and 100 | Range | 1-based, inclusive, counted across the whole table (From must not exceed To). |
| **Rank by** | blank | Large, Small | The column to rank. Text columns are read as numbers (thousands commas are ignored); unreadable values are never selected. |
| **Ties** | Exact N | Large, Small | **Exact N** returns exactly N rows. **Include ties** also includes rows tied with the Nth. |
| **Per group** | none | all except Range | Selects within each group of the chosen columns. For Range a note says it is global and per-group does not apply. |

**Worked example.** Input:

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

**Edge cases and limits.**

- [Preview uses 100 rows](#preview-vs-run): "First 10" or "row 150" refer to positions in the sample while you edit; Run applies them to the whole table.
- For Large and Small, S is ordered by the ranked value (largest first for Large, smallest first for Small). For First, Last and Range, S keeps input order.
- Empty values in the **Rank by** column are never selected; they go to R.
- Asking for more rows than exist returns all rows in S.

**Messages you may see.**

| Code | When | Fix |
|---|---|---|
| `TD-SHAPE-001` | Large or Small without a Rank by column | Pick the column |
| `TD-SHAPE-003` | The Rank by or group column no longer exists | Pick it again |
| `TD-SHAPE-004` | N below 1, or Range with From above To | Fix the numbers |
| `TD-SHAPE-005` | No input data | Fix the upstream node |

**Tips.** To get "the first 10 by date", [Sort](#sort) first: First and Last follow the current row order.

---

## Find and Replace

<img src="../../../src/trigger_designer/resources/qt/images/node_icons/Preparation/FindReplace.svg" alt="Find and Replace icon" width="32" height="32">

**What it does.** Applies an ordered list of find-and-replace rules to the text columns you pick, as plain text or as regular expressions.

**When to use it.** Standardise names (`Ltd.` to `Limited`), strip prefixes, blank out placeholders such as `N/A`, fix a recurring typo across a column.

**Inputs and outputs.**

| Socket | Carries |
|---|---|
| Input | The table |
| Out | The same table with the replaced text (in place, or in new columns) |

**Settings.**

| Section | Control | Default | Effect |
|---|---|---|---|
| Columns | **Columns** (picker) | none | The **text** columns to change. Hint: "Text columns only. A numeric column is rejected." |
| Rules | **Rule** (list, up to 50, each card collapsible) | none | One card per rule. The collapsed card shows a summary such as `Find... -> Replace · literal`. |
| Rules | **Find** | empty | The text (or pattern) to look for, up to 500 characters. |
| Rules | **Replace** | empty | The replacement. Empty deletes the found text. |
| Rules | **Mode** | Literal | **Literal** matches the text exactly as typed. **Regex** reads Find as a regular expression. |
| Rules | **On** | on | Untick to switch a rule off without deleting it. |
| Rules | **Match case** | off | Off means upper and lower case do not matter. |
| Rules | **Whole cell** | off | Replace only when the whole cell equals the Find text (or the whole cell matches the regular expression). |
| Output | **Keep original** and a suffix box (placeholder `_clean`) | off | Off: the columns are changed in place. On: the original stays and the result goes to a new column named `<column><suffix>`; an empty suffix becomes `_clean`. |

A note says "Rules run top to bottom. Each rule sees the previous result." The node shows a chip such as "12 cells change (first 100 rows)" or "No cells change in the first 100 rows".

In **Regex** mode the replacement can use groups from the pattern as `$1`, `$2`, .... In **Literal** mode a `$` in the replacement is just a dollar sign.

**Worked example.** Input:

| memo | amt |
|---|---|
| Paid to ACME Ltd. | 1 |
| paid to acme ltd | 2 |
| N/A | 3 |
| Refund (ACME) | 4 |

Columns = `memo`; Keep original on (suffix `_clean`); rule 1: Find `N/A`, Replace empty, Literal, Whole cell; rule 2: Find `^(?:Paid to|paid to) `, Replace empty, Regex.

| memo | amt | memo_clean |
|---|---|---|
| Paid to ACME Ltd. | 1 | ACME Ltd. |
| paid to acme ltd | 2 | acme ltd |
| N/A | 3 | *(empty text)* |
| Refund (ACME) | 4 | Refund (ACME) |

A single Literal rule with Find `acme`, Replace `Acme Inc`, Match case off, in place, changes every case variant: `Paid to Acme Inc Ltd.`, `paid to Acme Inc ltd`, `Refund (Acme Inc)`.

**Edge cases and limits.**

- [Preview uses 100 rows](#preview-vs-run); the "cells change" chip counts the sample only.
- Only **text** columns. Pick a number column and the node stops with `TD-SHAPE-044`; convert it with [Select](#select) first.
- Empty cells stay empty.
- Every rule is checked, even a switched-off one: an empty Find in a rule that is off still stops the node. Delete rules you do not need.
- With no rule switched on, the table passes through unchanged (the columns are still checked).
- Rules run in order, so a later rule can change what an earlier one produced.
- A Regex Find that is not valid (for example an unclosed `(`) stops the node with `TD-SHAPE-040`. Escape special characters with a backslash.
- With Keep original on, the new column names must not already exist or repeat (`TD-SHAPE-002`).

**Messages you may see.**

| Code | When | Fix |
|---|---|---|
| `TD-SHAPE-001` | No column picked | Pick at least one text column |
| `TD-SHAPE-002` | A suffixed name already exists or repeats | Change the suffix |
| `TD-SHAPE-003` | A picked column is gone | Pick it again |
| `TD-SHAPE-040` | Invalid regular expression (the detail names the rule number) | Escape special characters with a backslash |
| `TD-SHAPE-041` | Find longer than 500 characters | Shorten it |
| `TD-SHAPE-042` | A rule has an empty Find | Type the text, or remove the rule |
| `TD-SHAPE-043` | More than 50 rules | Remove rules or use two nodes |
| `TD-SHAPE-044` | A picked column is not text | Convert it to text with Select |

**Tips.** Turn Keep original on while you build the rules, compare the two columns, then switch it off when you are happy.

---

## Date Helper

<img src="../../../src/trigger_designer/resources/qt/images/node_icons/Preparation/DateHelper.svg" alt="Date Helper icon" width="32" height="32">

**What it does.** Adds columns derived from dates: weekday, weekend and month-end flags, quarters and fiscal periods, the difference between two dates, adding days or **working** days, using your own working week and holidays.

**When to use it.** Cut-off and timing tests: postings on weekends or public holidays, days from invoice to payment, working days to settle, fiscal quarter reporting.

**Inputs and outputs.**

| Socket | Carries |
|---|---|
| Input | The table (dates may be real dates or text) |
| Out | The input columns plus one new column per calculation |

**Settings.**

| Section | Control | Default | Effect |
|---|---|---|---|
| Calendar | **Fiscal year starts** | January | The first month of your fiscal year. |
| Calendar | **Working days** (seven buttons M T W T F S S) | Monday to Friday | The days that count as working days. At least one is required. |
| Calculations | **Calculation** list (each entry collapsible) | none | One entry per new column. The collapsed entry shows `Calculation · Date -> Name`. |
| each entry | **Calculation** | Weekday name | What to compute (table below). |
| each entry | **Output name** (placeholder "Auto") | Auto | The new column's name. Auto gives `<date column>_<calculation>`, or `<date1>_to_<date2>_<calculation>` for the two-date calculations. |
| each entry | **Date** | empty | The date column (real date or text). |
| each entry | **Second date** | blank | For the two-date calculations. |
| each entry | **Days** (-100,000 to 100,000) | 0 | For Add days and Add business days. |
| each entry | **Days from column** | blank | A column with the number of days per row; overrides **Days** when set. |
| Advanced date handling (collapsed) | **Text dates** | Auto-detect | How to read text dates: `2024-12-31`, `31/12/2024`, `12/31/2024`, `31-Dec-2024`, `20241231` or `31.12.2024`. |
| Advanced date handling | **Non-working day** | Forward | When an Add business days start date is not a working day, move **Forward** to the next working day or **Backward** to the previous one first. |
| Advanced date handling | **Holidays** (text box, placeholder "2024-12-25 (one per line)") | empty | Holidays as `YYYY-MM-DD`, separated by new lines, spaces, commas or semicolons. They are skipped by the business-day calculations. |

Only the fields a calculation uses are shown.

| Calculation | Result |
|---|---|
| Weekday name | `Monday` to `Sunday` (English) |
| Weekday number | 1 (Monday) to 7 (Sunday) |
| Is weekend | true when the day is **not** one of your Working days |
| Is month end | true on the last day of the month |
| Quarter | calendar quarter 1 to 4 |
| Fiscal year | the year in which the fiscal year **ends**. With an April start, 31 Jan 2024 and 2 Mar 2024 are fiscal year 2024 and 25 Dec 2024 is 2025. With a January start it is the calendar year. |
| Fiscal period | month number within the fiscal year (1 to 12) |
| Fiscal quarter | 1 to 4, counted from the fiscal start |
| Days between | Second date minus Date, in days (negative when the second date is earlier) |
| Add days | Date plus Days |
| Add business days | Date plus working days, respecting Working days and Holidays |
| Is business day | true when the date is a working day and not a holiday |
| Business days between | Working days from Date up to, but not including, Second date |

**Worked example.** Input (text dates):

| inv_date | due |
|---|---|
| 2024-01-31 | 2024-02-15 |
| 2024-03-02 | 2024-03-01 |
| 2024-12-25 | 2025-01-10 |

Settings: fiscal year starts April; holiday `2024-12-25`; calculations on `inv_date`: Weekday name, Is month end (named `month_end`), Fiscal year, Fiscal quarter, Fiscal period, Days between (second date `due`), Add business days (Days 3, named `plus3bd`), Is business day, Is weekend.

| inv_date | weekday name | month_end | fiscal year | fiscal quarter | fiscal period | days between | plus3bd | is business day | is weekend |
|---|---|---|---|---|---|---|---|---|---|
| 2024-01-31 | Wednesday | true | 2024 | 4 | 10 | 15 | 2024-02-05 | true | false |
| 2024-03-02 | Saturday | false | 2024 | 4 | 12 | -1 | 2024-03-07 | false | true |
| 2024-12-25 | Wednesday | false | 2025 | 3 | 9 | 16 | 2024-12-31 | false | false |

The real output also contains `inv_date` and `due`, and uses the Auto names such as `inv_date_weekday_name` and `inv_date_to_due_days_between`. Note that 25 December is a Wednesday, so "Is weekend" is false, yet "Is business day" is false because the date is in the Holidays list.

**Edge cases and limits.**

- [Preview uses 100 rows](#preview-vs-run). A chip "n unreadable dates in column (first 100 rows)" reports text that could not be read as a date in the sample.
- Text that cannot be read as a date gives an **empty** result, not an error.
- Auto-detect cannot know whether `03/04/2024` is 3 April or 4 March. When your text dates contain slashes, choose the exact layout under **Text dates**.
- The date column must be a real date, a date-time or text; a number column gives `TD-SHAPE-050`.
- A time of day on a date-time value is ignored; calculations use the date part.
- New column names must be unique and must not already exist (`TD-SHAPE-002`).
- With no calculations the table passes through unchanged.

**Messages you may see.**

| Code | When | Fix |
|---|---|---|
| `TD-SHAPE-001` | A calculation has no date column (or no second date for a two-date one) | Pick it |
| `TD-SHAPE-002` | An output name is duplicated or already exists | Give it a unique name |
| `TD-SHAPE-003` | A chosen column is gone | Pick it again |
| `TD-SHAPE-004` | An unknown value (fiscal month, working day, roll direction, calculation) | Pick from the lists |
| `TD-SHAPE-050` | The column is neither a date nor text | Choose a date or text column |
| `TD-SHAPE-052` | A holiday is not `YYYY-MM-DD` (the detail quotes it) | Type holidays as year-month-day |
| `TD-SHAPE-053` | No working day ticked | Tick at least one weekday |

**Tips.**

- Add "Is weekend" and "Is business day" columns, then use a [Filter](#filter) to list postings on non-working days.
- Keep the holiday list in the workflow so the test is reproducible.

---

## Text to Columns

<img src="../../../src/trigger_designer/resources/qt/images/node_icons/Preparation/TextToColumns.svg" alt="Text to Columns icon" width="32" height="32">

**What it does.** Splits one text column into several columns, or into several rows, at a delimiter or a pattern.

**When to use it.** Split `Surname, First name`, a `code-description` field, account strings such as `100.200.300`, or a cell holding several values separated by semicolons (one value per row).

**Inputs and outputs.**

| Socket | Carries |
|---|---|
| Input | The table |
| Out | The table with the extra columns, or with more rows |

**Settings.**

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

**Worked example.** Input:

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

**Edge cases and limits.**

- [Preview uses 100 rows](#preview-vs-run); in Rows mode the row count after Run is much larger than in the preview.
- Only text columns (`TD-SHAPE-044`). Convert numbers to text first.
- Fewer pieces than columns leaves the extra columns empty; a cell without the delimiter ends up entirely in the first column.
- If a new column name already exists, a number is added (`name_2`).
- A regex that can match nothing, such as `\s*`, is rejected: use `\s+` (`TD-SHAPE-101`).
- A regex separator is replaced by a special marker character (U+241F) internally, so a cell that already contains that character would split there too. This is very rare.
- Maximum 50 columns. An empty Pattern is an error.

**Messages you may see.**

| Code | When | Fix |
|---|---|---|
| `TD-SHAPE-001` | No column picked, or the Pattern is empty | Fill it in |
| `TD-SHAPE-003` | The column is gone | Pick it again |
| `TD-SHAPE-004` | Max splits outside the range | Change the number |
| `TD-SHAPE-040` | Invalid regular expression | Escape special characters |
| `TD-SHAPE-044` | The column is not text | Convert it with Select |
| `TD-SHAPE-101` | The pattern can match nothing | Use `\s+` rather than `\s*` |

**Tips.** To split into rows and then total per piece, follow with an [Aggregate](#aggregate).

---

## Multi-Field Formula

<img src="../../../src/trigger_designer/resources/qt/images/node_icons/Preparation/MultiFieldFormula.svg" alt="Multi-Field Formula icon" width="32" height="32">

**What it does.** Applies **one** SQL expression to many columns at once. You write the expression once, with `{col}` standing for "the current column", and the node repeats it for every column you tick.

**When to use it.** Clean or convert a block of similar columns in one step: trim all text columns, convert twelve monthly amounts from text to numbers, upper-case several code columns.

**Inputs and outputs.**

| Socket | Carries |
|---|---|
| Input | The table |
| Out | The same rows, with the ticked columns replaced or new columns added |

**Settings.**

| Section | Control | Default | Effect |
|---|---|---|---|
| Columns | **Columns** (checklist) | none | The columns the formula runs on, up to 200. Hint: "The formula runs once for each ticked column (up to 200)." |
| Formula | **Formula** (text box; placeholder `UPPER(TRIM({col}))   or   TRY_CAST({col} AS DOUBLE)`) | empty | One SQL expression. `{col}` is replaced by each column. `{name}` is replaced by that column's name as text. No semicolons. |
| Output | **Result** | Replace the columns | **Replace the columns** overwrites each ticked column. **Add new columns** keeps the originals and adds one result column per ticked column. |
| Output | **New column suffix** (only for Add new columns) | `_new` | Added to each name: `net` with `_num` gives `net_num`. Must not be empty. |

The syntax is the same as in [Writing SQL expressions](#writing-sql-expressions), except that you write `{col}` rather than `[column]`. Each `{col}` is inserted safely quoted, so column names with spaces or quotes work.

The dock note reads: "Use {col} for the column and {name} for its name. One expression only: no semicolons." After editing, a chip reads "2 columns replaced" or "2 columns added".

**Worked example.** Input (all text):

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

**Edge cases and limits.**

- [Preview uses 100 rows](#preview-vs-run).
- Up to 200 columns per node. In Add new columns mode the new names (`<column><suffix>`) must not already exist (`TD-SHAPE-002`).
- The formula is one expression. A semicolon, or brackets that do not balance, is rejected with `TD-SHAPE-110`. A trailing `--` comment is safe.
- Because the columns are usually text, put `TRIM(...)` and `TRY_CAST(...)` inside the formula.
- The [read-only guard](#the-read-only-guard) checks the whole composed query: `read_csv(...)`, `random()`, `uuid()` and similar give `TD-SHAPE-112`.
- The result type follows the expression.

**Messages you may see.**

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

**Tips.** Test the formula on one column first, then tick the rest.

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
