# Formula Tool Reference

The Formula node does not use a custom formula language.
It evaluates DuckDB SQL expressions inside a `SELECT` statement and writes the result into the chosen target column.

## What A Formula Can Be

Any valid DuckDB scalar expression that fits in a `SELECT` list is a valid formula.
In practice, that means the formula tool supports:

- arithmetic expressions
- boolean expressions
- comparison expressions
- `CASE` expressions
- string functions
- numeric functions
- date and time functions
- null-handling functions
- casts and type conversions
- regular-expression functions
- nested expressions and references to earlier formula sections

The Formula node automatically wraps your expression, so you should enter the expression itself, not a full query.

## Formula Syntax Rules

- Use square brackets for column references, for example `[Age]` or `[Order Date]`.
- Use single quotes for string literals, for example `'Adult'`.
- Use double quotes only when DuckDB syntax requires them for identifiers inside generated SQL.
- A Formula node can contain up to 5 sections.
- Sections run top to bottom.
- Later sections can reference columns created by earlier sections.
- Empty sections are ignored until both a target column and a formula are filled in.

## Supported Formula Families

### 1. Arithmetic

```sql
[amount] + [tax]
```

```sql
[amount] - [discount]
```

```sql
[price] * [quantity]
```

```sql
([price] * [quantity]) - [discount]
```

```sql
[total] / [count]
```

### 2. Comparison And Boolean Logic

```sql
[score] > 90
```

```sql
[score] BETWEEN 80 AND 100
```

```sql
[status] = 'Active'
```

```sql
[name] LIKE '%smith%'
```

```sql
[region] IN ('US', 'CA', 'MX')
```

```sql
[end_date] IS NULL
```

```sql
[end_date] IS NOT NULL
```

```sql
[is_active] = true
```

```sql
[amount] > 100 AND [status] = 'Paid'
```

```sql
NOT [is_deleted]
```

### 3. Conditional Logic

```sql
CASE
    WHEN [age] >= 65 THEN 'Senior'
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

```sql
CASE WHEN [double_amount] >= 40 THEN 'high' ELSE 'low' END
```

### 4. Null Handling

```sql
COALESCE([email], 'missing@example.com')
```

```sql
NULLIF([status], 'unknown')
```

```sql
CASE WHEN [value] IS NULL THEN 0 ELSE [value] END
```

```sql
COALESCE([first_name], '') || ' ' || COALESCE([last_name], '')
```

### 5. Type Conversion

```sql
CAST([amount_text] AS DOUBLE)
```

```sql
TRY_CAST([order_date_text] AS DATE)
```

```sql
CAST([order_timestamp] AS TIMESTAMP)
```

```sql
CAST([active_flag] AS BOOLEAN)
```

### 6. String And Text Functions

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
REPLACE([place_of_publication], '-', ' ')
```

```sql
SUBSTRING([customer_code], 1, 3)
```

```sql
CONCAT('INV-', [order_id])
```

```sql
[first_name] || ' ' || [last_name]
```

```sql
REGEXP_REPLACE([sku], '-', '')
```

```sql
SPLIT_PART([email], '@', 2)
```

```sql
LEFT([phone_number], 3)
```

```sql
RIGHT([reference_code], 4)
```

### 7. Numeric Functions

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

```sql
POWER([base], 2)
```

```sql
SQRT([area])
```

```sql
MOD([order_index], 2)
```

```sql
GREATEST([a], [b], [c])
```

```sql
LEAST([a], [b], [c])
```

### 8. Date And Time Functions

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

```sql
CURRENT_DATE
```

```sql
CURRENT_TIMESTAMP
```

### 9. Regular Expressions And Pattern Matching

```sql
REGEXP_REPLACE([sku], '[^0-9]', '')
```

```sql
REGEXP_MATCHES([email], '^[^@]+@[^@]+\\.[^@]+$')
```

```sql
REGEXP_EXTRACT([path], '([^/]+)$')
```

```sql
[code] LIKE 'A%'
```

```sql
[code] NOT LIKE '%test%'
```

### 10. Multi-Section Formula Patterns

Section order matters. Later sections can use columns created earlier in the same Formula node.

```sql
-- Section 1 target: double_amount
[amount] * 2
```

```sql
-- Section 2 target: amount_band
CASE WHEN [double_amount] >= 40 THEN 'high' ELSE 'low' END
```

```sql
-- Section 1 target: audit_date
TRY_CAST([audit_date_text] AS DATE)
```

```sql
-- Section 2 target: audit_year
YEAR([audit_date])
```

```sql
-- Section 3 target: audit_month
MONTH([audit_date])
```

## Formula Examples Already Used In This Repository

These patterns are already used by the app and its tests:

```sql
[amount] * 2
```

```sql
CASE WHEN [double_amount] >= 40 THEN 'high' ELSE 'low' END
```

```sql
CASE WHEN [Age] > 30 THEN 'Adult' ELSE 'Young' END
```

```sql
COALESCE([email], 'missing@example.com')
```

```sql
TRY_CAST([order_date_text] AS DATE)
```

```sql
YEAR([audit_date])
```

```sql
MONTH([audit_date])
```

```sql
REGEXP_REPLACE([sku], '-', '')
```

```sql
ROUND([score], 2)
```

```sql
DATE_TRUNC('month', CAST([order_timestamp] AS TIMESTAMP))
```

## Editor Validation Rules

The SQL formula editor currently checks for:

- unmatched single quotes
- unmatched parentheses
- incomplete `CASE ... END` blocks
- unknown bracketed column references when a column list is available

The editor highlights these SQL tokens for readability:

`SELECT`, `FROM`, `WHERE`, `AND`, `OR`, `NOT`, `IN`, `LIKE`, `IS`, `NULL`, `CASE`, `WHEN`, `THEN`, `ELSE`, `END`, `AS`, `ASC`, `DESC`, `ORDER`, `BY`, `GROUP`, `HAVING`, `JOIN`, `LEFT`, `RIGHT`, `INNER`, `OUTER`, `ON`, `UNION`, `ALL`, `DISTINCT`, `COUNT`, `SUM`, `AVG`, `MIN`, `MAX`, `CAST`, `CONVERT`, `SUBSTRING`, `UPPER`, `LOWER`, `TRIM`, `LENGTH`, `COALESCE`, `ISNULL`, `NULLIF`, `BETWEEN`, `EXISTS`, `ANY`, `SOME`.

## Practical Notes

- Use `CONCAT(...)` or `||` for string building instead of `+`.
- If a column is stored as text but should behave like a date or number, cast it first.
- If a cast may fail, prefer `TRY_CAST(...)` so bad values become `NULL` instead of throwing an error.
- If you add a new column in one section, you can reference it in later sections.
- The Formula node expects expressions, not a full SQL query.

## Related Files

- [Existing formula reference](SQL_FORMULA_REFERENCE.md)
- [Formula editor README](SQL_FORMULA_EDITOR_README.md)
- [Formula node implementation](../src/trigger_designer/qt/widgets/nodes/Preparation/formula.py)