---
icon: lucide/function-square
---

# Formula reference

Every SQL expression family the **Formula**, **Multi-Field Formula** and **Filter** nodes support, with working examples. For how to open the editor and add formula cards, see [Formula](formula.md). For the broader language rules, see [SQL expressions](../../guide/sql-expressions.md).

!!! tip "New to formulas?"
    Start with [Formula](formula.md) for a guided walkthrough, then use this page as a function lookup.

---

## Column references

Put a column name in **square brackets**: `[Invoice Amount]`. Spaces in names are fine. Case is ignored and spaces just inside the brackets are trimmed, so `[invoice amount]` and `[ Invoice Amount ]` both resolve to `Invoice Amount`.

```sql
[Amount] * 1.2
[First Name] || ' ' || [Last Name]
```

Unknown names are not columns: the engine reports `Referenced column "x" not found`.

---

## Expression families

=== "Arithmetic"

    Standard operators. When a column comes from a CSV file it arrives as text; use `TRY_CAST` before doing maths on it.

    | Expression | Result |
    |---|---|
    | `[price] + [tax]` | Sum |
    | `[amount] - [discount]` | Difference |
    | `[price] * [quantity]` | Product |
    | `[total] / [count]` | Quotient |
    | `[total] % [divisor]` | Remainder |
    | `[total] // [divisor]` | Integer (floor) division |

    **Examples:**

    ```sql
    [price] * [quantity]
    ```
    ```sql
    ([price] * [quantity]) - [discount]
    ```
    ```sql
    TRY_CAST([amount_text] AS DOUBLE) * 1.1
    ```

    !!! warning "Text columns"
        `[order_value] + 1` fails when the column is text. Wrap it first: `TRY_CAST([order_value] AS DOUBLE) + 1`.

=== "Conditional (CASE)"

    `CASE WHEN … THEN … ELSE … END` and the shorthand `IF`.

    ```sql
    CASE
        WHEN [age] >= 65 THEN 'Senior'
        WHEN [age] >= 18 THEN 'Adult'
        ELSE 'Minor'
    END
    ```
    ```sql
    CASE
        WHEN [department] = 'Sales' AND [salary] > 75000 THEN 'Senior Sales'
        WHEN [department] = 'Engineering' AND [salary] > 90000 THEN 'Senior Engineer'
        ELSE 'Standard'
    END
    ```
    ```sql
    IF(TRY_CAST([amount] AS DOUBLE) IS NULL, 'check', 'ok')
    ```

    **Multi-section pattern:** use an earlier section's output in a later one.

    ```sql
    -- Section 1: target "amount_num"
    TRY_CAST([amount] AS DOUBLE)

    -- Section 2: target "size_band"  (references amount_num)
    CASE
        WHEN [amount_num] >= 1000 THEN 'Large'
        WHEN [amount_num] IS NULL THEN 'Unreadable'
        ELSE 'Small'
    END
    ```

=== "String & text"

    | Function | What it does | Example |
    |---|---|---|
    | `UPPER(x)` | Upper case | `UPPER([city])` → `LONDON` |
    | `LOWER(x)` | Lower case | `LOWER([name])` → `acme ltd` |
    | `TRIM(x)` | Remove leading/trailing spaces | `TRIM([name])` |
    | `LTRIM(x)` / `RTRIM(x)` | Trim one side only | |
    | `LENGTH(x)` | Character count | `LENGTH([name])` |
    | `LEFT(x, n)` | First *n* characters | `LEFT([code], 3)` |
    | `RIGHT(x, n)` | Last *n* characters | `RIGHT([ref], 4)` |
    | `SUBSTRING(x, start, len)` | Extract a slice | `SUBSTRING([code], 1, 3)` |
    | `LPAD(x, n, pad)` | Pad on the left | `LPAD([id], 6, '0')` → `000042` |
    | `RPAD(x, n, pad)` | Pad on the right | |
    | `REPLACE(x, from, to)` | Replace all occurrences | `REPLACE([name], '-', ' ')` |
    | `SPLIT_PART(x, delim, n)` | n-th token after splitting | `SPLIT_PART([email], '@', 2)` |
    | `CONCAT(a, b, …)` | Join strings | `CONCAT('INV-', [id])` |
    | `a \|\| b` | Join strings (operator form) | `[first] \|\| ' ' \|\| [last]` |
    | `CONTAINS(x, sub)` | true if substring present | `CONTAINS([note], 'urgent')` |
    | `STARTS_WITH(x, prefix)` | true if starts with | `STARTS_WITH([code], 'A')` |

    ```sql
    UPPER(TRIM([name]))
    ```
    ```sql
    [first_name] || ' ' || [last_name]
    ```
    ```sql
    CONCAT('INV-', LPAD(CAST([id] AS VARCHAR), 5, '0'))
    ```

=== "Numeric"

    | Function | What it does |
    |---|---|
    | `ROUND(x, n)` | Round to *n* decimal places |
    | `ABS(x)` | Absolute value |
    | `CEIL(x)` | Round up to next integer |
    | `FLOOR(x)` | Round down to next integer |
    | `POWER(x, n)` | *x* to the power *n* |
    | `SQRT(x)` | Square root |
    | `MOD(x, y)` | Remainder of *x* ÷ *y* |
    | `GREATEST(a, b, …)` | Largest of the values |
    | `LEAST(a, b, …)` | Smallest of the values |
    | `LOG(x)` / `LOG(base, x)` | Natural or base logarithm |
    | `EXP(x)` | e raised to *x* |
    | `SIGN(x)` | −1, 0 or 1 |

    ```sql
    ROUND(TRY_CAST([score] AS DOUBLE), 2)
    ```
    ```sql
    ABS([variance])
    ```
    ```sql
    GREATEST([q1], [q2], [q3], [q4])
    ```

=== "Date & time"

    **Extracting parts:**

    | Expression | Returns |
    |---|---|
    | `YEAR([date_col])` | Year as integer |
    | `MONTH([date_col])` | Month 1–12 |
    | `DAY([date_col])` | Day 1–31 |
    | `HOUR([ts_col])` | Hour 0–23 |
    | `MINUTE([ts_col])` | Minute 0–59 |
    | `DAYOFWEEK([date_col])` | 0 (Sun) – 6 (Sat) |
    | `DAYNAME([date_col])` | `'Monday'` etc. |
    | `QUARTER([date_col])` | Quarter 1–4 |
    | `EXTRACT(YEAR FROM [date_col])` | Year (alternative form) |
    | `DATE_PART('month', [date_col])` | Month (alternative form) |

    **Formatting:**

    ```sql
    STRFTIME([date_col], '%Y-%m')      -- "2024-01"
    STRFTIME([date_col], '%d/%m/%Y')   -- "31/01/2024"
    ```

    **Truncating:**

    ```sql
    DATE_TRUNC('month', [ts_col])      -- first instant of the month
    DATE_TRUNC('year',  [date_col])    -- 1 Jan of the year
    ```

    **Differences:**

    ```sql
    DATEDIFF('day',   [start_date], [end_date])
    DATEDIFF('month', [start_date], [end_date])
    DATEDIFF('year',  [start_date], [end_date])
    ```

    **Current values:**

    ```sql
    CURRENT_DATE          -- today as a date
    CURRENT_TIMESTAMP     -- now as a timestamp
    ```

    **Parsing text into a date** (when the column is text):

    ```sql
    TRY_CAST([date_text] AS DATE)                -- ISO format: 2024-01-31
    STRPTIME([date_text], '%d/%m/%Y')::DATE       -- non-ISO: 31/01/2024
    ```

    !!! tip "Always cast text first"
        A column from a CSV is text even when it looks like `2024-01-31`. Use `TRY_CAST([col] AS DATE)` before calling date functions.

=== "Null handling"

    | Expression | What it does |
    |---|---|
    | `COALESCE(a, b, …)` | First non-null value in the list |
    | `NULLIF(x, val)` | Returns null when *x* equals *val*, otherwise *x* |
    | `IFNULL(x, default)` | Returns *default* when *x* is null |
    | `x IS NULL` | True when *x* is null |
    | `x IS NOT NULL` | True when *x* is not null |

    ```sql
    COALESCE([email], 'no-email@example.com')
    ```
    ```sql
    COALESCE(TRY_CAST([amount] AS DOUBLE), 0)
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

=== "Type conversion"

    | Expression | Converts to |
    |---|---|
    | `CAST([col] AS DOUBLE)` | Decimal number; fails on bad values |
    | `TRY_CAST([col] AS DOUBLE)` | Decimal number; returns null on bad values |
    | `CAST([col] AS INTEGER)` | Whole number |
    | `TRY_CAST([col] AS INTEGER)` | Whole number, null on failure |
    | `CAST([col] AS DATE)` | Date |
    | `TRY_CAST([col] AS DATE)` | Date, null on failure |
    | `CAST([col] AS TIMESTAMP)` | Date and time |
    | `CAST([col] AS BOOLEAN)` | True / false |
    | `CAST([col] AS VARCHAR)` | Text |
    | `[col]::DATE` | Shorthand cast (DuckDB) |

    **Common type names:**

    | You mean | Use |
    |---|---|
    | Decimal / float | `DOUBLE` or `FLOAT` |
    | Whole number | `INTEGER` or `BIGINT` |
    | Text / string | `VARCHAR` |
    | Date | `DATE` |
    | Date and time | `TIMESTAMP` |
    | Yes / no | `BOOLEAN` |

    !!! success "Prefer TRY_CAST"
        Use `TRY_CAST` whenever the data might be messy. Plain `CAST` stops the node at the first bad value; `TRY_CAST` returns an empty cell instead, so the run continues.

    ```sql
    TRY_CAST([amount_text] AS DOUBLE)
    TRY_CAST([date_str] AS DATE)
    TRY_CAST(REPLACE([amt_comma], ',', '') AS DOUBLE)   -- "1,200.50" → 1200.5
    ```

=== "Comparison & boolean"

    | Operator | Meaning |
    |---|---|
    | `=` | Equal |
    | `<>` or `!=` | Not equal |
    | `<`, `>`, `<=`, `>=` | Less / greater than |
    | `x BETWEEN a AND b` | Inclusive range |
    | `x IN ('a', 'b', 'c')` | Member of list |
    | `x NOT IN (…)` | Not in list |
    | `x LIKE 'A%'` | Pattern match (case-sensitive) |
    | `x ILIKE '%acme%'` | Pattern match (case-insensitive) |
    | `x NOT LIKE '%test%'` | Inverse pattern |
    | `AND`, `OR`, `NOT` | Logical operators |
    | `x IS NULL` | Null check |

    ```sql
    [amount] > 1000 AND [status] = 'Paid'
    ```
    ```sql
    [region] IN ('US', 'CA', 'MX')
    ```
    ```sql
    [score] BETWEEN 80 AND 100
    ```
    ```sql
    [name] ILIKE '%smith%'
    ```
    ```sql
    NOT [is_deleted]
    ```

    !!! warning "Comparing text with numbers"
        `[order_value] > 200` fails when the column is text. Cast first: `TRY_CAST([order_value] AS DOUBLE) > 200`.

=== "Regular expressions"

    | Function | What it does |
    |---|---|
    | `REGEXP_MATCHES(x, pattern)` | True when the full string matches |
    | `REGEXP_REPLACE(x, pattern, replacement)` | Replace all matches |
    | `REGEXP_REPLACE(x, pattern, repl, 'g')` | Replace globally |
    | `REGEXP_EXTRACT(x, pattern)` | First match of the full pattern |
    | `REGEXP_EXTRACT(x, pattern, group)` | Capture group *n* |
    | `REGEXP_EXTRACT_ALL(x, pattern)` | All matches as a list |

    Patterns use standard regular-expression syntax.

    ```sql
    REGEXP_REPLACE([sku], '[^0-9]', '', 'g')      -- keep digits only
    ```
    ```sql
    REGEXP_EXTRACT([path], '([^/]+)$')             -- last path segment
    ```
    ```sql
    REGEXP_MATCHES([email], '^[^@]+@[^@]+\.[^@]+$')   -- basic email check
    ```
    ```sql
    REGEXP_REPLACE([phone], '[^0-9+]', '')         -- strip non-numeric
    ```

    !!! tip "Backslashes in patterns"
        In a DuckDB expression, write `\\d` to match a digit (the first `\` escapes the second for SQL). Inside the formula editor this looks like `'\\d+'`.

=== "Multi-section patterns"

    A single Formula node can hold up to **5 sections**, running top to bottom. Each section can reference columns created by earlier sections in the same node.

    **Pattern: parse then extract**

    ```sql
    -- Section 1: target "audit_date"
    TRY_CAST([audit_date_text] AS DATE)

    -- Section 2: target "audit_year"  (uses audit_date)
    YEAR([audit_date])

    -- Section 3: target "audit_month"  (uses audit_date)
    MONTH([audit_date])
    ```

    **Pattern: clean then categorise**

    ```sql
    -- Section 1: target "amount_num"
    TRY_CAST(REPLACE([amount], ',', '') AS DOUBLE)

    -- Section 2: target "size_band"  (uses amount_num)
    CASE
        WHEN [amount_num] >= 10000 THEN 'Large'
        WHEN [amount_num] >= 1000  THEN 'Medium'
        WHEN [amount_num] IS NULL  THEN 'Unreadable'
        ELSE 'Small'
    END
    ```

    **Pattern: build an identifier**

    ```sql
    -- Section 1: target "vendor_clean"
    UPPER(TRIM([vendor]))

    -- Section 2: target "ref_code"  (uses vendor_clean)
    [vendor_clean] || '-' || LPAD(CAST([id] AS VARCHAR), 6, '0')
    ```

---

## Common pitfalls

!!! failure "CAST on a bad value stops the whole node"
    ```sql
    CAST([amount] AS DOUBLE)   -- stops with TD-TYP-001 on the first non-numeric row
    ```
    Fix: use `TRY_CAST` so bad values become empty instead:
    ```sql
    TRY_CAST([amount] AS DOUBLE)
    ```

!!! failure "Adding text with +"
    ```sql
    [first_name] + ' ' + [last_name]   -- No function matches '+(VARCHAR, VARCHAR)'
    ```
    Fix: use `||` or `CONCAT`:
    ```sql
    [first_name] || ' ' || [last_name]
    CONCAT([first_name], ' ', [last_name])
    ```

!!! failure "Using = to check for null"
    ```sql
    [status] = NULL   -- always false; = never matches null
    ```
    Fix: use `IS NULL`:
    ```sql
    [status] IS NULL
    ```

!!! warning "Preview uses 100 rows"
    The editor evaluates your formula on the first 100 rows of preview data. A bad value that sits on row 10,000 will not appear until you Run. Use `TRY_CAST` to guard against late surprises.

---

Back to the [Formula node](formula.md) · [Preparation node index](index.md)
