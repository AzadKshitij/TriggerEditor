import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_3106250034864 = pl.scan_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/src/test_Data.csv', infer_schema=False)

# var_file_input_3106250034864 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
from trigger_designer.core.utils.cleansing_util import DataCleansing, NullStrategy
import polars as pl
# Convert LazyFrame to DataFrame if needed
_cleansing_input = var_file_input_3106250034864.collect() if hasattr(var_file_input_3106250034864, 'collect') else var_file_input_3106250034864
cleaner = DataCleansing(_cleansing_input)
cleaner.handle_nulls(NullStrategy.REMOVE_ALL_NULL_ROWS)
cleaner.handle_nulls(NullStrategy.REMOVE_ALL_NULL_COLS)
cleaner.handle_nulls(NullStrategy.REPLACE_WITH_DEFAULT)
cleaner.strip_whitespace(remove_all=False, normalize_spaces=True, fields=['customer_id', 'first_name', 'last_name', 'email', 'phone', 'age', 'salary', 'department', 'notes', 'join_date', 'empty_column'])
var_cleansing_3106250036464 = cleaner.get_result()
