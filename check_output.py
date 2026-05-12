import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_2910487201904 = pl.scan_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_1/data/monthly_sales_2023.csv', infer_schema=False)

# var_file_input_2910487201904 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
var_select_2910487203504 = var_file_input_2910487201904.select(['order_id', 'customer_id', 'product_id', 'order_date', 'order_value'])
var_select_2910487203504 = var_select_2910487203504.with_columns(pl.col('order_id').cast(pl.String, strict=False).alias('order_id'))
var_select_2910487203504 = var_select_2910487203504.with_columns(pl.col('customer_id').cast(pl.String, strict=False).alias('customer_id'))
var_select_2910487203504 = var_select_2910487203504.with_columns(pl.col('product_id').cast(pl.String, strict=False).alias('product_id'))
var_select_2910487203504 = var_select_2910487203504.with_columns(pl.col('order_date').cast(pl.Date, strict=False).alias('order_date'))
var_select_2910487203504 = var_select_2910487203504.with_columns(pl.col('order_value').cast(pl.Float64, strict=False).alias('order_value'))
import duckdb
import polars as pl
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_select_2910487203504.collect() if hasattr(var_select_2910487203504, 'collect') else var_select_2910487203504
duck.register('df_step_0', df_for_duck)
df_for_duck = duck.execute('''SELECT *, YEAR("order_date") AS "year" FROM df_step_0''').pl()
# Preserve lazy execution when the incoming value is lazy
var_formula_2910487215824 = df_for_duck.lazy() if hasattr(var_select_2910487203504, 'collect') else df_for_duck
duck.close()
