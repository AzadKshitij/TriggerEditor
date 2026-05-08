---
name: node-polars-get-code
description: "Write or fix the get_code() function in a TriggerEditor node's Content class. Use when: implementing code generation for a new node, fixing incorrect polars code output, or improving an existing get_code() to produce correct and idiomatic Polars expressions. Produces a get_code() method that generates runnable Python+Polars code strings."
argument-hint: "Describe the node's operation and inputs/outputs, or paste the existing get_code() to fix."
---

# Write `get_code()` for a TriggerEditor Node

## When to Use
- Implementing `get_code()` for a new node
- Fixing or improving an existing `get_code()`
- Ensuring generated code is idiomatic Polars and runnable as a standalone script

## How `get_code()` Works in This Project

The executor collects `get_code()` output from every node in topological order and concatenates them into a single Python script. The result must be runnable as a standalone `.py` file.

### Variable Naming Convention
Every Content class has these attributes at runtime:
- `self.incoming_variable: str` — the Python variable name holding the **input** `pl.DataFrame`
- `self.variable_name: str` — the Python variable name that **this node** should assign its output to (format: `var_<nodetype>_<id>`)
- For nodes with multiple outputs, additional names like `self.f_variable_name` are defined in `__init__`

### Input/Output Dict Structure
At runtime, data flows as dicts: `{"data": pl.DataFrame, "variable_name": str}`.
In `get_code()`, you only deal with the **string names** — not the actual DataFrames.

### Template
```python
def get_code(self) -> str:
    if self.incom_data is None:
        return "# No data available\n"

    lines = [
        "# <Description of operation>",
        f"{self.variable_name} = {self.incoming_variable}.<polars_expression>",
    ]
    return "\n".join(lines) + "\n"
```

## Polars Code Patterns

Refer to these patterns when writing `get_code()`. Use **lazy API** (`lazy()` / `collect()`) only if the rest of the pipeline uses it; otherwise use eager DataFrames directly.

### Filter (single column, single value)
```python
# True results
f"{self.variable_name} = {self.incoming_variable}.filter(pl.col('{col}') {op} {value})"
# False results  
f"{self.f_variable_name} = {self.incoming_variable}.filter(~(pl.col('{col}') {op} {value}))"
```

### Select / Drop Columns
```python
f"{self.variable_name} = {self.incoming_variable}.select([{col_list}])"
# or to drop:
f"{self.variable_name} = {self.incoming_variable}.drop([{col_list}])"
```

### Add / Replace Column (with_columns)
```python
f"{self.variable_name} = {self.incoming_variable}.with_columns(pl.lit({value}).alias('{new_col}'))"
# Expression-based:
f"{self.variable_name} = {self.incoming_variable}.with_columns((pl.col('{a}') + pl.col('{b}')).alias('{result}'))"
```

### Rename Columns
```python
f"{self.variable_name} = {self.incoming_variable}.rename({{{repr(mapping)}}})"
```

### Sort
```python
# self.columns = list of column names, self.ascending = list of bools
cols = repr(self.columns)
ascending = repr(self.ascending)
f"{self.variable_name} = {self.incoming_variable}.sort({cols}, descending=[not x for x in {ascending}])"
```

### Group By + Aggregation
```python
aggs = ", ".join([f"pl.col('{c}').{agg}().alias('{c}_{agg}')" for c, agg in self.aggregations])
f"{self.variable_name} = {self.incoming_variable}.group_by({repr(self.group_cols)}).agg([{aggs}])"
```

### Unique / Deduplicate
```python
f"{self.variable_name} = {self.incoming_variable}.unique(subset={repr(self.columns) if self.columns else None})"
```

### Transpose
```python
f"{self.variable_name} = {self.incoming_variable}.transpose(include_header=True, header_name='Column')"
```

### Join (merge)
```python
# join_type: "inner", "left", "right", "full", "cross", "semi", "anti"
f"{self.variable_name} = {self.left_variable}.join({self.right_variable}, on={repr(self.join_keys)}, how='{self.join_type}')"
```

### Running Total / Cumulative Sum
```python
f"{self.variable_name} = {self.incoming_variable}.with_columns(pl.col('{col}').cum_sum().alias('{result_col}'))"
```

### Count Rows
```python
f"{self.variable_name} = pl.DataFrame({{'count': [{self.incoming_variable}.height]}})"
# or to add count column:
f"{self.variable_name} = {self.incoming_variable}.with_columns(pl.lit({self.incoming_variable}.height).alias('count'))"
```

### Split Column
```python
f"{self.variable_name} = {self.incoming_variable}.with_columns(pl.col('{col}').str.split('{delimiter}').list.to_struct()).unnest('{col}')"
```

### Cleansing (trim, fill nulls, cast types)
```python
# Trim strings
f"pl.col('{col}').str.strip_chars()"
# Fill nulls
f"pl.col('{col}').fill_null({repr(fill_value)})"
# Cast type
f"pl.col('{col}').cast(pl.{dtype})"
```

### Formula via DuckDB (SQL expressions)
When a SQL-like formula is involved (Formula node pattern):
```python
lines = [
    "import duckdb",
    "import polars as pl",
    "duck = duckdb.connect(':memory:')",
    f"df_for_duck = {self.incoming_variable}.collect() if hasattr({self.incoming_variable}, 'collect') else {self.incoming_variable}",
    "duck.register('df', df_for_duck)",
    f"{self.variable_name}_df = duck.execute('''SELECT *, {sql_formula} as \"{target_col}\" FROM df''').pl()",
    f"{self.variable_name} = {self.variable_name}_df",
    "duck.close()",
]
```

## Writing Rules

1. **String safety**: always `repr()` or quote column names when they may contain spaces or special characters.
2. **Guard clause first**: return early with a comment string if required state is missing.
3. **One assignment per output socket**: each output variable must be assigned exactly once.
4. **No runtime execution**: `get_code()` must only build strings — never call polars or execute anything.
5. **Newline at end**: always end with `"\n"` so concatenated scripts remain readable.
6. **Import-free**: do NOT add `import polars as pl` unless it is truly needed (e.g., DuckDB path). The executor script already imports polars.

## Procedure

1. Read the node's `__init__` to identify all state attributes (`self.column`, `self.operation`, `self.value`, etc.)
2. Read `update_data()` to understand the actual polars operation being performed
3. Mirror that logic as a string in `get_code()` using `self.incoming_variable` and `self.variable_name`
4. Handle the guard clause (missing data / settings)
5. Test mentally: if the generated code were run in a fresh Python session with `import polars as pl` and the input variable defined, would it produce the correct output?

## Reference Files
- [filter.py `get_code()`](../../src/trigger_designer/qt/widgets/nodes/Preparation/filter.py) — simple operation, two outputs
- [formula.py `get_code()`](../../src/trigger_designer/qt/widgets/nodes/Preparation/formula.py) — DuckDB SQL formula pattern
- [count_recors.py `get_code()`](../../src/trigger_designer/qt/widgets/nodes/Transform/count_recors.py) — transform pattern
- [node_base.py](../../src/trigger_designer/qt/node_base.py) — TriggerNode base (shows how get_code is called)
