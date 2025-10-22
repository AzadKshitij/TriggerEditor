import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_1483097620560 = pl.scan_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/src/check.csv', infer_schema=False)

# var_file_input_1483097620560 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
var_groupby_1483097622160 = var_file_input_1483097620560.group_by(['Difficulty']).agg([
    pl.col('Keyword').n_unique().alias('Unique_Keyword')
])
