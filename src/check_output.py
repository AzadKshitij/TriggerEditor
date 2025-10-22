import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_2226824792176 = pl.scan_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/src/check.csv', infer_schema=False)

# var_file_input_2226824792176 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
# Validate data columns
missing = [col for col in ['Difficulty'] if col not in var_file_input_2226824792176.columns]
if missing:
    print(f'Warning: Missing columns will be skipped: {missing}')

# Filter to existing columns
valid_key_cols = [col for col in ['Relevancy Score'] if col in var_file_input_2226824792176.columns]
valid_data_cols = [col for col in ['Difficulty'] if col in var_file_input_2226824792176.columns]

# Transpose operation using Polars melt
var_transpose_2226824793776 = var_file_input_2226824792176.melt(
    id_vars=valid_key_cols,
    value_vars=valid_data_cols,
    variable_name='Name',
    value_name='Value'
)
