import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_1662526196144 = pl.scan_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_1/data/monthly_sales_2023.csv', infer_schema=False)

# var_file_input_1662526196144 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_1662679860560 = pl.scan_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_1/data/customers.csv', infer_schema=False)

# var_file_input_1662679860560 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_1662679862000 = pl.scan_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_1/data/products.csv', infer_schema=False)

# var_file_input_1662679862000 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_1662679863280 = pl.scan_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_1/data/regions.csv', infer_schema=False)

# var_file_input_1662679863280 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
var_select_1662679867120 = var_file_input_1662526196144.select(['order_id', 'customer_id', 'product_id', 'order_date', 'order_value'])
var_select_1662679867120 = var_select_1662679867120.with_columns(pl.col('order_id').cast(pl.String, strict=False).alias('order_id'))
var_select_1662679867120 = var_select_1662679867120.with_columns(pl.col('customer_id').cast(pl.String, strict=False).alias('customer_id'))
var_select_1662679867120 = var_select_1662679867120.with_columns(pl.col('product_id').cast(pl.String, strict=False).alias('product_id'))
var_select_1662679867120 = var_select_1662679867120.with_columns(pl.col('order_date').cast(pl.String, strict=False).alias('order_date'))
var_select_1662679867120 = var_select_1662679867120.with_columns(pl.col('order_value').cast(pl.Float64, strict=False).alias('order_value'))
var_select_1662680252976 = var_file_input_1662679860560.select(['customer_id', 'name', 'age', 'email', 'region_id'])
var_select_1662680254736 = var_file_input_1662679862000.select(['product_id', 'name', 'category', 'price'])
var_select_1662680256816 = var_file_input_1662679863280.select(['region_id', 'region_name'])
from trigger_designer.core.utils.cleansing_util import DataCleansing, NullStrategy
import polars as pl
# Convert LazyFrame to DataFrame if needed
_cleansing_input = var_select_1662679867120.collect() if hasattr(var_select_1662679867120, 'collect') else var_select_1662679867120
cleaner = DataCleansing(_cleansing_input)
cleaner.remove_rows_with_nulls(fields=['order_id', 'customer_id', 'product_id', 'order_date', 'order_value'])
var_cleansing_1662680121904 = cleaner.get_result()
# Filter data into true and false results
var_t_filter_1662680131824 = var_cleansing_1662680121904.filter(pl.col('order_value') > 0)
var_f_filter_1662680131824 = var_cleansing_1662680121904.filter(~(pl.col('order_value') > 0))
# Polars LazyFrame Join Operation
import polars as pl

def _ensure_lazyframe(data):
    if isinstance(data, pl.DataFrame):
        return data.lazy()
    if isinstance(data, pl.LazyFrame):
        return data
    raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(data)}')

_left_input = _ensure_lazyframe(var_t_filter_1662680131824)
_right_input = _ensure_lazyframe(var_select_1662680252976)

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
var_join_1662680044144 = _result_with_indicators.filter(
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
var_l_join_1662680044144 = _result_with_indicators.filter(
    pl.col('__join_type') == 'left_only'
).select(_left_cols)

# Extract right-only data efficiently
_right_cols = ['customer_id', 'name', 'age', 'email', 'region_id']
var_r_join_1662680044144 = _result_with_indicators.filter(
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

_left_input = _ensure_lazyframe(var_join_1662680044144)
_right_input = _ensure_lazyframe(var_select_1662680254736)
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
var_join_1662680050704 = _result_with_indicators.filter(
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
var_l_join_1662680050704 = _result_with_indicators.filter(
    pl.col('__join_type') == 'left_only'
).select(_left_cols)

# Extract right-only data efficiently
_right_cols = ['product_id', 'name_right', 'category', 'price']
var_r_join_1662680050704 = _result_with_indicators.filter(
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

_left_input = _ensure_lazyframe(var_join_1662680050704)
_right_input = _ensure_lazyframe(var_select_1662680256816)

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
var_join_1662680053424 = _result_with_indicators.filter(
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
var_l_join_1662680053424 = _result_with_indicators.filter(
    pl.col('__join_type') == 'left_only'
).select(_left_cols)

# Extract right-only data efficiently
_right_cols = ['region_id', 'region_name']
var_r_join_1662680053424 = _result_with_indicators.filter(
    pl.col('__join_type') == 'right_only'
).select(_right_cols)

# Clean up temporary variables
del _left_input, _right_input, _join_result, _result_with_indicators, _left_cols, _right_cols
# Ensure we're working with a LazyFrame for memory efficiency
if var_join_1662680053424 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_join_1662680053424, pl.DataFrame):
        var_join_1662680053424_lazy = var_join_1662680053424.lazy()
    elif isinstance(var_join_1662680053424, pl.LazyFrame):
        var_join_1662680053424_lazy = var_join_1662680053424
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_join_1662680053424)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_join_1662680053424_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_1/Test1.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_1/Test1.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
