# SQL Formula Reference

This file documents what the Formula node and SQL formula editor support today.

## How the Formula Node Works

- Each formula section is a DuckDB SQL expression that runs inside a `SELECT` statement.
- A single Formula node can now contain up to 5 sections.
- Sections run from top to bottom.
- Later sections can reference columns created by earlier sections in the same node.
- Column references should use square brackets, for example `[Order Date]` or `[Customer Name]`.
- String literals should use single quotes, for example `'Active'`.
- The editor does lightweight validation for bracketed column names, quotes, parentheses, and `CASE ... END` balance. It does not do full SQL parsing.

## Syntax Highlighting in the Editor

The editor currently highlights these SQL keywords and functions:

- `SELECT`, `FROM`, `WHERE`, `AND`, `OR`, `NOT`, `IN`, `LIKE`, `IS`, `NULL`
- `CASE`, `WHEN`, `THEN`, `ELSE`, `END`, `AS`
- `ASC`, `DESC`, `ORDER`, `BY`, `GROUP`, `HAVING`
- `JOIN`, `LEFT`, `RIGHT`, `INNER`, `OUTER`, `ON`, `UNION`, `ALL`, `DISTINCT`
- `COUNT`, `SUM`, `AVG`, `MIN`, `MAX`
- `CAST`, `CONVERT`, `SUBSTRING`, `UPPER`, `LOWER`, `TRIM`, `LENGTH`
- `COALESCE`, `ISNULL`, `NULLIF`, `BETWEEN`, `EXISTS`, `ANY`, `SOME`

It also highlights:

- string literals like `'London'`
- numeric literals like `42` or `12.35`
- bracketed column references like `[Amount]`
- function calls like `YEAR(...)` or `REGEXP_REPLACE(...)`
- SQL comments like `-- note`

## Common Formula Patterns

### Conditional logic

```sql
CASE
    WHEN [age] >= 65 THEN 'Senior Citizen'
    WHEN [age] >= 18 THEN 'Adult'
    ELSE 'Minor'
END
```

```sql
CASE
    WHEN [department] = 'Sales' AND [salary] > 75000 THEN 'Senior Sales Rep'
    WHEN [department] = 'Engineering' AND [salary] > 90000 THEN 'Senior Engineer'
    ELSE 'Standard Employee'
END
```

### Text cleanup and text matching

```sql
UPPER([city])
```

```sql
LOWER([customer_name])
```

```sql
TRIM([customer_name])
```

```sql
LENGTH([customer_name])
```

```sql
REPLACE([Place of Publication], '-', ' ')
```

```sql
SUBSTRING([customer_code], 1, 3)
```

```sql
CONCAT('INV-', [order_id])
```

```sql
REGEXP_REPLACE([sku], '-', '')
```

```sql
CASE
    WHEN [Place of Publication] LIKE '%London%' THEN 'London'
    WHEN [Place of Publication] LIKE '%Oxford%' THEN 'Oxford'
    ELSE REPLACE([Place of Publication], '-', ' ')
END
```

### Numeric calculations

```sql
[amount] * 2
```

```sql
([price] * [quantity]) - [discount]
```

```sql
ROUND([score], 2)
```

```sql
ABS([variance])
```

```sql
CEIL([forecast])
```

```sql
FLOOR([forecast])
```

### Null handling and type conversion

```sql
COALESCE([email], 'missing@example.com')
```

```sql
NULLIF([status], 'unknown')
```

```sql
CAST([amount_text] AS DOUBLE)
```

```sql
TRY_CAST([order_date_text] AS DATE)
```

### Date and time formulas

These examples were verified against the DuckDB runtime used by this project.

```sql
YEAR(CAST([order_date] AS DATE))
```

```sql
MONTH(CAST([order_date] AS DATE))
```

```sql
DAY(CAST([order_date] AS DATE))
```

```sql
EXTRACT(YEAR FROM CAST([order_timestamp] AS TIMESTAMP))
```

```sql
DATE_PART('month', CAST([order_date] AS DATE))
```

```sql
STRFTIME(CAST([order_date] AS DATE), '%Y-%m')
```

```sql
DATE_TRUNC('month', CAST([order_timestamp] AS TIMESTAMP))
```

```sql
DATEDIFF('day', CAST([start_date] AS DATE), CAST([end_date] AS DATE))
```

Examples of useful datetime outputs:

```sql
YEAR(CAST([order_date] AS DATE))
```
Creates a numeric year column like `2024`.

```sql
STRFTIME(CAST([order_date] AS DATE), '%Y-%m')
```
Creates a formatted year-month value like `2024-01`.

```sql
DATE_TRUNC('month', CAST([order_timestamp] AS TIMESTAMP))
```
Rounds a timestamp down to the start of the month.

### Boolean and comparison expressions

```sql
[amount] > 100
```

```sql
[status] IS NULL
```

```sql
[score] BETWEEN 80 AND 100
```

```sql
[is_active] = true
```

## Multi-Section Examples

### Example 1: Create two new columns in one node

Section 1 target:

```sql
double_amount
```

Section 1 formula:

```sql
[amount] * 2
```

Section 2 target:

```sql
amount_band
```

Section 2 formula:

```sql
CASE WHEN [double_amount] >= 40 THEN 'high' ELSE 'low' END
```

### Example 2: Parse and extract from a date field

Section 1 target:

```sql
audit_date
```

Section 1 formula:

```sql
TRY_CAST([audit_date_text] AS DATE)
```

Section 2 target:

```sql
audit_year
```

Section 2 formula:

```sql
YEAR([audit_date])
```

Section 3 target:

```sql
audit_month
```

Section 3 formula:

```sql
MONTH([audit_date])
```

## Repo Examples Already Present

These formula styles already appear in this repository:

- `CASE ... WHEN ... THEN ... ELSE ... END`
- `LIKE '%text%'`
- `REPLACE(...)`
- `UPPER(...)`
- boolean expressions such as `[is_active] = true`
- comparisons such as `[salary] > 75000`

Examples can be found in:

- `src/trigger_designer/examples/01. Cleaning _.json`
- `tests/unit/test_sql_editor.py`
- `src/trigger_designer/External Resources/OutputBlob.yxmd`

## Practical Notes

- Use `CONCAT(...)` for string building instead of relying on `+`.
- If a column is text but should behave like a date or number, cast it first.
- If a cast may fail, prefer `TRY_CAST(...)` so bad values become `NULL` instead of throwing an error.
- If you add a new column in section 1, you can reference it in section 2 and later.
- Incomplete sections are ignored until both a target column and a formula are provided.
