import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_2961257575792 = pl.scan_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/src/test_Data.csv', infer_schema=False)

# var_file_input_2961257575792 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
var_select_2961257677200 = var_file_input_2961257575792.select(['customer_id', 'first_name', 'last_name', 'email', 'phone', 'age', 'salary', 'department', 'notes', 'join_date', 'empty_column'])
var_select_2961257677200 = var_select_2961257677200.with_columns(pl.col('customer_id').cast(pl.Int64, strict=False).alias('customer_id'))
var_select_2961257677200 = var_select_2961257677200.with_columns(pl.col('first_name').cast(pl.String, strict=False).alias('first_name'))
var_select_2961257677200 = var_select_2961257677200.with_columns(pl.col('last_name').cast(pl.String, strict=False).alias('last_name'))
var_select_2961257677200 = var_select_2961257677200.with_columns(pl.col('email').cast(pl.String, strict=False).alias('email'))
var_select_2961257677200 = var_select_2961257677200.with_columns(pl.col('phone').cast(pl.String, strict=False).alias('phone'))
var_select_2961257677200 = var_select_2961257677200.with_columns(pl.col('age').cast(pl.String, strict=False).alias('age'))
var_select_2961257677200 = var_select_2961257677200.with_columns(pl.col('salary').cast(pl.String, strict=False).alias('salary'))
var_select_2961257677200 = var_select_2961257677200.with_columns(pl.col('department').cast(pl.String, strict=False).alias('department'))
var_select_2961257677200 = var_select_2961257677200.with_columns(pl.col('notes').cast(pl.String, strict=False).alias('notes'))
var_select_2961257677200 = var_select_2961257677200.with_columns(pl.col('join_date').cast(pl.String, strict=False).alias('join_date'))
var_select_2961257677200 = var_select_2961257677200.with_columns(pl.col('empty_column').cast(pl.String, strict=False).alias('empty_column'))
import duckdb
import polars as pl
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_select_2961257677200.collect() if hasattr(var_select_2961257677200, 'collect') else var_select_2961257677200
# Register DataFrame with DuckDB
duck.register('df', df_for_duck)
# Apply formula to create new column
var_formula_2961257678960_df = duck.execute('''SELECT *, Case when "customer_id" = 5 then "Yes" else "No" as "Final" FROM df''').pl()
# Create LazyFrame from polars DataFrame
var_formula_2961257678960 = var_formula_2961257678960_df.lazy()
# Close DuckDB connection
duck.close()
# Ensure we're working with a LazyFrame for memory efficiency
if var_formula_2961257678960 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_formula_2961257678960, pl.DataFrame):
        var_formula_2961257678960_lazy = var_formula_2961257678960.lazy()
    elif isinstance(var_formula_2961257678960, pl.LazyFrame):
        var_formula_2961257678960_lazy = var_formula_2961257678960
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_formula_2961257678960)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_formula_2961257678960_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/src/test_Data_Final_.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/src/test_Data_Final_.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
