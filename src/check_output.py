import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_1828008432240 = pl.scan_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/src/test_Data.csv', infer_schema=False)

# var_file_input_1828008432240 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
var_select_1828008435280 = var_file_input_1828008432240.select(['customer_id', 'first_name', 'last_name', 'email', 'phone', 'age', 'salary', 'department', 'notes', 'join_date', 'empty_column'])
var_select_1828008435280 = var_select_1828008435280.with_columns(pl.col('customer_id').cast(pl.Int64, strict=False).alias('customer_id'))
var_select_1828008435280 = var_select_1828008435280.with_columns(pl.col('first_name').cast(pl.String, strict=False).alias('first_name'))
var_select_1828008435280 = var_select_1828008435280.with_columns(pl.col('last_name').cast(pl.String, strict=False).alias('last_name'))
var_select_1828008435280 = var_select_1828008435280.with_columns(pl.col('email').cast(pl.String, strict=False).alias('email'))
var_select_1828008435280 = var_select_1828008435280.with_columns(pl.col('phone').cast(pl.String, strict=False).alias('phone'))
var_select_1828008435280 = var_select_1828008435280.with_columns(pl.col('age').cast(pl.Int64, strict=False).alias('age'))
var_select_1828008435280 = var_select_1828008435280.with_columns(pl.col('salary').cast(pl.Float64, strict=False).alias('salary'))
var_select_1828008435280 = var_select_1828008435280.with_columns(pl.col('department').cast(pl.String, strict=False).alias('department'))
var_select_1828008435280 = var_select_1828008435280.with_columns(pl.col('notes').cast(pl.String, strict=False).alias('notes'))
var_select_1828008435280 = var_select_1828008435280.with_columns(pl.col('join_date').cast(pl.Date, strict=False).alias('join_date'))
var_select_1828008435280 = var_select_1828008435280.with_columns(pl.col('empty_column').cast(pl.String, strict=False).alias('empty_column'))
var_sort_1828008437040 = var_select_1828008435280.sort(['customer_id', 'first_name'], descending=[True, False])
# Ensure we're working with a LazyFrame for memory efficiency
if var_sort_1828008437040 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_sort_1828008437040, pl.DataFrame):
        var_sort_1828008437040_lazy = var_sort_1828008437040.lazy()
    elif isinstance(var_sort_1828008437040, pl.LazyFrame):
        var_sort_1828008437040_lazy = var_sort_1828008437040
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_sort_1828008437040)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_sort_1828008437040_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/src/test_Data_Sort.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/src/test_Data_Sort.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
