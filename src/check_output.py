import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_2829759229264 = pl.scan_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/src/check.csv', infer_schema=False)

# var_file_input_2829759229264 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
# Ensure we're working with a LazyFrame for memory efficiency
if var_file_input_2829759229264 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_file_input_2829759229264, pl.DataFrame):
        var_file_input_2829759229264_lazy = var_file_input_2829759229264.lazy()
    elif isinstance(var_file_input_2829759229264, pl.LazyFrame):
        var_file_input_2829759229264_lazy = var_file_input_2829759229264
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_file_input_2829759229264)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_file_input_2829759229264_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/src/check_Lazy.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/src/check_Lazy.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
