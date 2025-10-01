import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_1859614659984 = pl.scan_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/src/test_Data.csv', infer_schema=False)

# var_file_input_1859614659984 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
print('''No Incoming Variable''')
var_select_1859614663024 = var_file_input_1859614659984.select(['customer_id', 'first_name', 'last_name', 'email', 'phone', 'age', 'salary', 'department', 'notes', 'join_date', 'empty_column'])
var_select_1859614663024 = var_select_1859614663024.with_columns(pl.col('customer_id').cast(pl.Int64, strict=False).alias('customer_id'))
var_select_1859614663024 = var_select_1859614663024.with_columns(pl.col('first_name').cast(pl.String, strict=False).alias('first_name'))
var_select_1859614663024 = var_select_1859614663024.with_columns(pl.col('last_name').cast(pl.String, strict=False).alias('last_name'))
var_select_1859614663024 = var_select_1859614663024.with_columns(pl.col('email').cast(pl.String, strict=False).alias('email'))
var_select_1859614663024 = var_select_1859614663024.with_columns(pl.col('phone').cast(pl.String, strict=False).alias('phone'))
var_select_1859614663024 = var_select_1859614663024.with_columns(pl.col('age').cast(pl.Int64, strict=False).alias('age'))
var_select_1859614663024 = var_select_1859614663024.with_columns(pl.col('salary').cast(pl.Float64, strict=False).alias('salary'))
var_select_1859614663024 = var_select_1859614663024.with_columns(pl.col('department').cast(pl.String, strict=False).alias('department'))
var_select_1859614663024 = var_select_1859614663024.with_columns(pl.col('notes').cast(pl.String, strict=False).alias('notes'))
var_select_1859614663024 = var_select_1859614663024.with_columns(pl.col('join_date').cast(pl.Date, strict=False).alias('join_date'))
var_select_1859614663024 = var_select_1859614663024.with_columns(pl.col('empty_column').cast(pl.String, strict=False).alias('empty_column'))
import polars as pl
# Sequential split - first 70% for estimation
indexed_df = var_select_1859614663024.with_row_index()
var_estimation_1859614664784 = indexed_df.filter(pl.col('index') < pl.col('index').max() * 0.7).drop('index')
var_validation_1859614664784 = indexed_df.filter(pl.col('index') >= pl.col('index').max() * 0.7).drop('index')
