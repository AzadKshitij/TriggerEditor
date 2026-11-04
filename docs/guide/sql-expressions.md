---
icon: lucide/database
---

# SQL expressions

Three nodes accept SQL expressions: **Formula**, **Filter** (expression mode) and **Multi-Field Formula**. This page explains the shared rules: how to reference columns, what you can write, and the most common traps.

For a full function lookup, see the [Formula reference](../nodes/preparation/formula-reference.md).

---

## Where expressions appear

| Node | What you write | What it produces |
|---|---|---|
| [Formula](../nodes/preparation/formula.md) | A value expression, one per card | A new column value or a replacement for an existing column |
| [Filter](../nodes/preparation/filter.md) (expression mode) | A condition expression | `true` or `false` per row; true rows go to the T output |
| [Multi-Field Formula](../nodes/preparation/multi-field-formula.md) | A value expression using `{col}` | The same formula applied to every ticked column |

You write the **expression only**, not a full query. The app wraps it into a SQL statement and runs it on the [DuckDB](https://duckdb.org/) engine.

---

## Column references

Put a column name in **square brackets**:

```sql
[Invoice Amount]
[Order Date]
[first_name]
```

- Spaces in names are fine.
- Case is ignored: `[AMOUNT]` finds `Amount`.
- Spaces just inside the brackets are trimmed: `[ Amount ]` finds `Amount`.
- An unknown name is **not** treated as a column: the engine reports `Referenced column "x" not found`.

**Text goes in single quotes**, not brackets:

```sql
[status] = 'Paid'          -- correct: 'Paid' is a text value
[status] = [Paid]          -- wrong: [Paid] would look for a column named Paid
```

---

## What you can write

Any single SQL expression that returns a value (for Formula and Multi-Field Formula) or a boolean (for Filter):

| Category | Examples |
|---|---|
| Arithmetic | `[price] * [qty]`, `([total] - [discount]) / [qty]` |
| Comparisons | `[amount] > 1000`, `[status] <> 'void'` |
| Boolean logic | `[amount] > 100 AND [status] = 'Paid'` |
| Ranges | `[score] BETWEEN 80 AND 100` |
| Lists | `[region] IN ('US', 'CA', 'MX')` |
| Patterns | `[name] ILIKE '%smith%'`, `[code] LIKE 'A%'` |
| Null checks | `[email] IS NULL`, `[amount] IS NOT NULL` |
| Conditional | `CASE WHEN [age] >= 18 THEN 'Adult' ELSE 'Minor' END` |
| Type conversion | `TRY_CAST([amount_text] AS DOUBLE)` |
| String functions | `UPPER([city])`, `TRIM([name])`, `LEFT([code], 3)` |
| Date functions | `YEAR([date_col])`, `DATEDIFF('day', [start], [end])` |
| Null handling | `COALESCE([email], 'none')` |
| Regular expressions | `REGEXP_REPLACE([sku], '[^0-9]', '', 'g')` |

Two shorthand spellings the app translates for you:

| You type | Meaning | Works in |
|---|---|---|
| `strip(x)` | `TRIM(x)` | Filter and Formula |
| `x in_between (a, b)` | `x BETWEEN a AND b` | Filter only |

---

## The critical pitfall: CSV text columns

!!! failure "CSV columns arrive as text"
    Every column in a CSV file is **text**, even when the values look like numbers or dates. DuckDB does not guess.

    These fail on a text column:
    ```sql
    [order_value] + 1               -- No function matches '+(VARCHAR, INTEGER)'
    [order_value] > 200             -- Cannot compare VARCHAR and INTEGER
    YEAR([date_text])               -- expects a DATE, got VARCHAR
    ```

    Fix: cast the column before using it.

!!! success "Use TRY_CAST to handle messy data safely"
    ```sql
    TRY_CAST([order_value] AS DOUBLE) + 1
    TRY_CAST([order_value] AS DOUBLE) > 200
    YEAR(TRY_CAST([date_text] AS DATE))
    ```

    `TRY_CAST` returns **empty** (null) when a value cannot be converted, instead of stopping the node. Plain `CAST` stops at the first bad value.

    Or set the column type once in [Select](../nodes/preparation/select.md) and avoid casts everywhere else.

---

## Useful patterns

### Parse an amount that has commas

```sql
TRY_CAST(REPLACE([amount], ',', '') AS DOUBLE)
```

`"1,200.50"` becomes `1200.5`. An unreadable value becomes empty.

### Parse a non-ISO date

```sql
STRPTIME([date_col], '%d/%m/%Y')::DATE   -- e.g. "31/01/2024"
```

### Categorise with CASE

```sql
CASE
    WHEN TRY_CAST([amount] AS DOUBLE) >= 10000 THEN 'Large'
    WHEN TRY_CAST([amount] AS DOUBLE) >= 1000  THEN 'Medium'
    WHEN TRY_CAST([amount] AS DOUBLE) IS NULL  THEN 'Unreadable'
    ELSE 'Small'
END
```

### Flag nulls with a fallback

```sql
COALESCE([email], 'no-email@example.com')
```

### Build an identifier

```sql
[vendor_prefix] || '-' || LPAD(CAST([id] AS VARCHAR), 6, '0')
```

### Days between two dates

```sql
DATEDIFF('day', TRY_CAST([start_date] AS DATE), TRY_CAST([end_date] AS DATE))
```

---

## The read-only guard

Expressions can only **read** the table that flows into the node. The engine rejects anything that writes data, reads files or calls system functions:

| What is blocked | Code |
|---|---|
| More than one SQL statement (anything after `;`) | `TD-SHAPE-110` |
| File or database reads (`read_csv`, `read_parquet`, `ATTACH`, …) | `TD-SHAPE-112` |
| System and random functions (`random()`, `uuid()`, `getenv()`, …) | `TD-SHAPE-112` |
| A query over 20,000 characters | `TD-SHAPE-114` |
| A query that runs longer than 25 seconds | `TD-SHAPE-115` |

`random()` and `uuid()` are blocked because a workflow must give the same result every time it runs on the same data, which is a requirement for audit evidence. For reproducible random splits, use the [Split](../nodes/preparation/split.md) node with a fixed seed.

A semicolon **inside** a quoted string or a `--` comment is fine: `[note] LIKE '%;%'`.

---

## Keyboard shortcuts in the editor

| Key | Action |
|---|---|
| `Ctrl+Space` | Open suggestions for functions, keywords and column names |
| `Ctrl+Enter` | Re-evaluate the formula |

---

## Where to go next

- **[Formula reference](../nodes/preparation/formula-reference.md)**: every function family with examples, side by side.
- **[Formula node](../nodes/preparation/formula.md)**: how to add cards, set targets and chain sections.
- **[Filter node](../nodes/preparation/filter.md)**: writing conditions that split rows.
- **[Multi-Field Formula](../nodes/preparation/multi-field-formula.md)**: applying one formula to many columns at once.
