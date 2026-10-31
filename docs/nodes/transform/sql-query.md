# SQL Query

![SQL Query](../../assets/node_icons/Transform/SQL%20Query.svg)

## Purpose

Runs one SQL `SELECT` over up to three tables and returns its result. It is the escape hatch for
reshapes that the other nodes do not cover: joins with several conditions, subqueries, window functions,
`CASE` logic, set operations.

## When to use it

When you already think in SQL, or the same job would take five nodes. Prefer the dedicated
nodes (Filter, Join, Aggregate) for simple steps: they are easier to review.

## Inputs and outputs

Three inputs, top to bottom: **t1** (required), **t2** and **t3** (optional). One output (no letter).
Inside the query the connected inputs are the tables `t1`, `t2` and `t3`, by position. The summary line in the dock reads "t1 required · t2, t3 optional".

## Settings

One section, *Query*:

| Label | Default | Effect |
|---|---|---|
| **SQL** | `SELECT *` on the next line `FROM t1` | The query. The editor has syntax colours and completes the table and column names. An error line under the editor shows the first problem, found by checking the query against empty copies of your tables, without reading your data. |

The note under the editor reads: "One read-only SELECT. Connected inputs are the tables t1, t2 and t3 (t2 and t3 are optional). Files and random functions are blocked."

**What you can write.** One statement that is a `SELECT`, `WITH` (common table expressions), `FROM ...`
(DuckDB shorthand), `VALUES` or `TABLE`, or one wrapped in brackets. Inside it, anything DuckDB's SQL offers:
joins, `GROUP BY`, `CASE`, window functions (`OVER`), subqueries, `UNION`, `ORDER BY`, `LIMIT`,
`USING SAMPLE`, string, date and maths functions. A closing `;` is fine and comments (`--`, `/* */`) are allowed.
Names are not case-sensitive; put a column name that contains spaces in double quotes, for example `"Posting Date"`.
Only the SQL is checked, not your result: add `ORDER BY` if row order matters, because SQL does not promise
an order without it.

**What is rejected.** Every query passes a guard before it runs, and again each time it runs. It rejects:

| Code | Message you will see | Cause |
|---|---|---|
| `TD-SHAPE-001` | SQL is empty | Nothing in the editor |
| `TD-SHAPE-110` | Only one statement is allowed | A `;` followed by a second statement |
| `TD-SHAPE-111` | Only SELECT queries are allowed | `INSERT`, `UPDATE`, `DELETE`, `CREATE`, `DROP`, `PRAGMA`, `DESCRIBE`, `EXPLAIN`, `COPY`, `ATTACH`, `SET`, `INSTALL` and the like |
| `TD-SHAPE-112` | This function is not allowed (files, system or random) | File readers (`read_csv`, `read_parquet`, any `read_...`, `glob`, any `..._scan`, `sniff_csv`), system functions (`duckdb_...`, `pragma_...`, `current_setting`, `getenv`, `query`), and random ones (`random`, `uuid`, `gen_random_uuid`, `setseed`) |
| `TD-SHAPE-112` | Reading files is not allowed | `FROM 'data.csv'` or a table name that looks like a path |
| `TD-SHAPE-112` | Dollar-quoted and escape strings are not allowed | `$$text$$` and `E'text'` strings; also control characters |
| `TD-SHAPE-113` | SQL could not be parsed: ... or the engine's own message | A typo, an unknown table or column (for example `Table with name t2 does not exist!` when t2 is not connected), a wrong function argument |
| `TD-SHAPE-114` | SQL is longer than 20,000 characters | Query too long |
| `TD-SHAPE-115` | Query took longer than 25 s | The query ran too long and was stopped; filter the data first or simplify the query |

The query runs in a sealed, in-memory copy of the engine with no access to files or the network, on
single-threaded settings and with a 2 GB memory limit. It can read only `t1`, `t2` and `t3` and cannot change
anything on disk or your original data. An unconnected `t1` gives `TD-SHAPE-005` ("Input 1 has no data").
`now()` and similar clock functions are allowed, so a query that uses them can give different results each run.

## Worked example

`t1` is a payments list, `t2` is a department list:

| Vendor | Amount | Dept |
|---|---|---|
| Acme | 100 | 1 |
| Acme | 250.5 | 2 |
| Beta | 75 | 1 |

| Dept | DeptName |
|---|---|
| 1 | Sales |
| 2 | Ops |

```sql
SELECT d.DeptName,
       COUNT(*) AS n,
       SUM(TRY_CAST(t1.Amount AS DOUBLE)) AS total
FROM t1
JOIN t2 AS d ON t1.Dept = d.Dept
GROUP BY d.DeptName
ORDER BY d.DeptName
```

| DeptName | n | total |
|---|---|---|
| Ops | 1 | 250.5 |
| Sales | 2 | 175.0 |

**The text-column trap (TRY_CAST).** A CSV arrives with every column as text, so `Amount` above is text.

- `SUM(Amount)` on a text column fails with `TD-SHAPE-113` ("No function matches the given name and argument
  types 'sum(VARCHAR)'. You might need to add explicit type casts"). Cast it first.
- `TRY_CAST(Amount AS DOUBLE)` turns text into a number, and **silently gives empty for anything it cannot read**
  instead of an error. It reads `1250.50` and ` 42 ` but **not** `1,234.50`, `(500)`, `$75`, `abc` or an empty
  cell. In a test column of `1250.50`, `1,234.50`, `(500)`, `$75`, `abc`, an empty cell and ` 42 `,
  `SUM(TRY_CAST(Amount AS DOUBLE))` returns 1292.5, and only 2 of the 7 rows were readable: five were dropped
  without a message. Always compare `COUNT(*)` with `COUNT(TRY_CAST(Amount AS DOUBLE))` to see how many were lost,
  or clean the column first with a *Cleansing* or *Find and Replace* node.
- Cast to `DOUBLE` or `DECIMAL(18,2)`, not `INTEGER`: `TRY_CAST('250.5' AS INTEGER)` is 251, a rounded figure.
- Plain `CAST(x AS DOUBLE)` stops the whole query with `TD-SHAPE-113` on the first unreadable value. Use it when
  you want to be told.

## Edge cases and limits

- In the live preview the query sees the first 100 rows of each table, so totals and counts are for the sample.
  Run the workflow for the real result. The sealed engine, the guard and the 25 s time limit apply to both.
- The output column types are chosen by the query; unusual types are converted to the ones the rest of the app
  supports (text, whole numbers, decimals, true/false, dates).
- If a query returns no rows, the node returns an empty table with the right columns.

## Tip

Start from `SELECT * FROM t1`, run it, then build up. The editor's error line catches typos before you
click away. Keep the query short and put the business rule in a comment (`-- exclude reversals`): it is
saved in the workflow and in the run record.


Back to the [Transform node index](index.md).
