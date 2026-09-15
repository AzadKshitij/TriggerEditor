import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_2586766917712 = pl.scan_csv('C:/Projects/TriggerEditor/savedfiles/Example_1/data/monthly_sales_2023.csv', infer_schema=False)

# var_file_input_2586766917712 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_2586766932272 = pl.scan_csv('C:/Projects/TriggerEditor/savedfiles/Example_1/data/customers.csv', infer_schema=False)

# var_file_input_2586766932272 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_2586766933712 = pl.scan_csv('C:/Projects/TriggerEditor/savedfiles/Example_1/data/products.csv', infer_schema=False)

# var_file_input_2586766933712 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_2586767098896 = pl.scan_csv('C:/Projects/TriggerEditor/savedfiles/Example_1/data/regions.csv', infer_schema=False)

# var_file_input_2586767098896 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
var_sort_2586767100336 = var_file_input_2586766917712
var_sort_2586767114096 = var_file_input_2586766932272
var_sort_2587822655120 = var_file_input_2586766933712
var_sort_2587822656880 = var_file_input_2586767098896
from trigger_designer.core.utils.cleansing_util import DataCleansing, NullStrategy
import polars as pl
# Convert LazyFrame to DataFrame if needed
_cleansing_input = var_sort_2586767100336.collect() if hasattr(var_sort_2586767100336, 'collect') else var_sort_2586767100336
cleaner = DataCleansing(_cleansing_input)
cleaner.replace_null_defaults(replace_strings=True, replace_numbers=True)
var_cleansing_2586767110256 = cleaner.get_result()
# Filter data into true and false results
var_t_filter_2586767112016 = var_cleansing_2586767110256.filter(pl.col('order_value') > '0')
var_f_filter_2586767112016 = var_cleansing_2586767110256.filter(~(pl.col('order_value') > '0'))
# Polars LazyFrame Join Operation
import polars as pl

def _ensure_lazyframe(data):
    if isinstance(data, pl.DataFrame):
        return data.lazy()
    if isinstance(data, pl.LazyFrame):
        return data
    raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(data)}')

_left_input = _ensure_lazyframe(var_t_filter_2586767112016)
_right_input = _ensure_lazyframe(var_sort_2586767114096)

# Perform full outer join with coalesce (automatic conflict resolution)
_join_result = _left_input.join(
    _right_input,
    left_on=['customer_id'],
    right_on=['customer_id'],
    how='full',
    coalesce=True
)

# OPTIMIZED: Extract all join types from single result (much faster!)
# Add join type indicator to identify record sources
_result_with_indicators = _join_result.with_columns([
    pl.when(pl.col('customer_id').is_null() | pl.col('name').is_null() | pl.col('age').is_null() | pl.col('email').is_null() | pl.col('region_id').is_null())
      .then(pl.lit('left_only'))
      .when(pl.col('order_id').is_null() | pl.col('customer_id').is_null() | pl.col('product_id').is_null() | pl.col('order_date').is_null() | pl.col('order_value').is_null())
      .then(pl.lit('right_only'))
      .otherwise(pl.lit('both'))
      .alias('__join_type')
])

# Main join result with selected columns (matched records only)
var_join_2586767102096 = _result_with_indicators.filter(
    pl.col('__join_type') == 'both'
).select([
    'customer_id',
    'order_date',
    'order_id',
    'order_value',
    'product_id',
    'name',
    'age',
    'email',
    'region_id'
])

# Extract left-only data efficiently
_left_cols = ['order_id', 'customer_id', 'product_id', 'order_date', 'order_value']
var_l_join_2586767102096 = _result_with_indicators.filter(
    pl.col('__join_type') == 'left_only'
).select(_left_cols)

# Extract right-only data efficiently
_right_cols = ['customer_id', 'name', 'age', 'email', 'region_id']
var_r_join_2586767102096 = _result_with_indicators.filter(
    pl.col('__join_type') == 'right_only'
).select(_right_cols)

# Clean up temporary variables
del _left_input, _right_input, _join_result, _result_with_indicators, _left_cols, _right_cols
# Polars LazyFrame Join Operation
import polars as pl

def _ensure_lazyframe(data):
    if isinstance(data, pl.DataFrame):
        return data.lazy()
    if isinstance(data, pl.LazyFrame):
        return data
    raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(data)}')

_left_input = _ensure_lazyframe(var_join_2586767102096)
_right_input = _ensure_lazyframe(var_sort_2587822655120)
# Rename conflicting columns in right dataframe
_right_renamed = _right_input.rename({'name': 'name_right'})


# Perform full outer join with coalesce (automatic conflict resolution)
_join_result = _left_input.join(
    _right_renamed,
    left_on=['product_id'],
    right_on=['product_id'],
    how='full',
    coalesce=True
)

# OPTIMIZED: Extract all join types from single result (much faster!)
# Add join type indicator to identify record sources
_result_with_indicators = _join_result.with_columns([
    pl.when(pl.col('product_id').is_null() | pl.col('name_right').is_null() | pl.col('category').is_null() | pl.col('price').is_null())
      .then(pl.lit('left_only'))
      .when(pl.col('customer_id').is_null() | pl.col('order_date').is_null() | pl.col('order_id').is_null() | pl.col('order_value').is_null() | pl.col('product_id').is_null() | pl.col('name').is_null() | pl.col('age').is_null() | pl.col('email').is_null() | pl.col('region_id').is_null())
      .then(pl.lit('right_only'))
      .otherwise(pl.lit('both'))
      .alias('__join_type')
])

# Main join result with selected columns (matched records only)
var_join_2586767104816 = _result_with_indicators.filter(
    pl.col('__join_type') == 'both'
).select([
    'age',
    'customer_id',
    'email',
    'name',
    'order_date',
    'order_id',
    'order_value',
    'product_id',
    'region_id',
    'category',
    'name_right',
    'price'
])

# Extract left-only data efficiently
_left_cols = ['customer_id', 'order_date', 'order_id', 'order_value', 'product_id', 'name', 'age', 'email', 'region_id']
var_l_join_2586767104816 = _result_with_indicators.filter(
    pl.col('__join_type') == 'left_only'
).select(_left_cols)

# Extract right-only data efficiently
_right_cols = ['product_id', 'name_right', 'category', 'price']
var_r_join_2586767104816 = _result_with_indicators.filter(
    pl.col('__join_type') == 'right_only'
).select(_right_cols)

# Clean up temporary variables
del _left_input, _right_input, _join_result, _result_with_indicators, _left_cols, _right_cols, _right_renamed
# Polars LazyFrame Join Operation
import polars as pl

def _ensure_lazyframe(data):
    if isinstance(data, pl.DataFrame):
        return data.lazy()
    if isinstance(data, pl.LazyFrame):
        return data
    raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(data)}')

_left_input = _ensure_lazyframe(var_join_2586767104816)
_right_input = _ensure_lazyframe(var_sort_2587822656880)

# Perform full outer join with coalesce (automatic conflict resolution)
_join_result = _left_input.join(
    _right_input,
    left_on=['region_id'],
    right_on=['region_id'],
    how='full',
    coalesce=True
)

# OPTIMIZED: Extract all join types from single result (much faster!)
# Add join type indicator to identify record sources
_result_with_indicators = _join_result.with_columns([
    pl.when(pl.col('region_id').is_null() | pl.col('region_name').is_null())
      .then(pl.lit('left_only'))
      .when(pl.col('age').is_null() | pl.col('customer_id').is_null() | pl.col('email').is_null() | pl.col('name').is_null() | pl.col('order_date').is_null() | pl.col('order_id').is_null() | pl.col('order_value').is_null() | pl.col('product_id').is_null() | pl.col('region_id').is_null() | pl.col('category').is_null() | pl.col('name_right').is_null() | pl.col('price').is_null())
      .then(pl.lit('right_only'))
      .otherwise(pl.lit('both'))
      .alias('__join_type')
])

# Main join result with selected columns (matched records only)
var_join_2586767107536 = _result_with_indicators.filter(
    pl.col('__join_type') == 'both'
).select([
    'age',
    'category',
    'customer_id',
    'email',
    'name',
    'name_right',
    'order_date',
    'order_id',
    'order_value',
    'price',
    'product_id',
    'region_id',
    'region_name'
])

# Extract left-only data efficiently
_left_cols = ['age', 'customer_id', 'email', 'name', 'order_date', 'order_id', 'order_value', 'product_id', 'region_id', 'category', 'name_right', 'price']
var_l_join_2586767107536 = _result_with_indicators.filter(
    pl.col('__join_type') == 'left_only'
).select(_left_cols)

# Extract right-only data efficiently
_right_cols = ['region_id', 'region_name']
var_r_join_2586767107536 = _result_with_indicators.filter(
    pl.col('__join_type') == 'right_only'
).select(_right_cols)

# Clean up temporary variables
del _left_input, _right_input, _join_result, _result_with_indicators, _left_cols, _right_cols
import duckdb
import polars as pl
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_join_2586767107536.collect() if hasattr(var_join_2586767107536, 'collect') else var_join_2586767107536
duck.register('df_step_0', df_for_duck)
df_for_duck = duck.execute('''SELECT *, YEAR("order_date") AS "year" FROM df_step_0''').pl()
# Preserve lazy execution when the incoming value is lazy
var_formula_2587822658640 = df_for_duck.lazy() if hasattr(var_join_2586767107536, 'collect') else df_for_duck
duck.close()
