import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_2941446179728 = pl.scan_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_1/data/monthly_sales_2023.csv', infer_schema=False)

# var_file_input_2941446179728 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_2941539272496 = pl.scan_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_1/data/customers.csv', infer_schema=False)

# var_file_input_2941539272496 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_2941539273936 = pl.scan_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_1/data/products.csv', infer_schema=False)

# var_file_input_2941539273936 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_2941539275216 = pl.scan_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_1/data/regions.csv', infer_schema=False)

# var_file_input_2941539275216 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
var_select_2941539277456 = var_file_input_2941446179728.select(['order_id', 'customer_id', 'product_id', 'order_date', 'order_value'])
var_select_2941539277456 = var_select_2941539277456.with_columns(
    pl.col('order_id').cast(pl.String, strict=False).alias('order_id')
)
var_select_2941539277456 = var_select_2941539277456.with_columns(
    pl.col('customer_id').cast(pl.String, strict=False).alias('customer_id')
)
var_select_2941539277456 = var_select_2941539277456.with_columns(
    pl.col('product_id').cast(pl.String, strict=False).alias('product_id')
)
var_select_2941539277456 = var_select_2941539277456.with_columns(
    pl.coalesce([
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Date, '%Y-%m-%d', strict=False, exact=True),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Date, '%Y/%m/%d', strict=False, exact=True),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Date, '%Y.%m.%d', strict=False, exact=True),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Date, '%d-%m-%Y', strict=False, exact=True),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Date, '%d/%m/%Y', strict=False, exact=True),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Date, '%d.%m.%Y', strict=False, exact=True),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Date, '%m-%d-%Y', strict=False, exact=True),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Date, '%m/%d/%Y', strict=False, exact=True),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Date, '%m.%m.%Y', strict=False, exact=True),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Date, '%d %b %Y', strict=False, exact=True),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Date, '%d %B %Y', strict=False, exact=True),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Date, '%b %d %Y', strict=False, exact=True),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Date, '%B %d %Y', strict=False, exact=True),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Date, '%d-%b-%Y', strict=False, exact=True),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Date, '%d-%B-%Y', strict=False, exact=True),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y-%m-%d %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y-%m-%d %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y-%m-%dT%H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y-%m-%dT%H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y/%m/%d %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y/%m/%d %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y/%m/%dT%H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y/%m/%dT%H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y.%m.%d %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y.%m.%d %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y.%m.%dT%H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y.%m.%dT%H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%m-%Y %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%m-%Y %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%m-%YT%H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%m-%YT%H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d/%m/%Y %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d/%m/%Y %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d/%m/%YT%H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d/%m/%YT%H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d.%m.%Y %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d.%m.%Y %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d.%m.%YT%H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d.%m.%YT%H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m-%d-%Y %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m-%d-%Y %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m-%d-%YT%H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m-%d-%YT%H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m/%d/%Y %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m/%d/%Y %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m/%d/%YT%H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m/%d/%YT%H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m.%m.%Y %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m.%m.%Y %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m.%m.%YT%H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m.%m.%YT%H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %b %Y %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %b %Y %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %b %YT%H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %b %YT%H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %B %Y %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %B %Y %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %B %YT%H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %B %YT%H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%b %d %Y %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%b %d %Y %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%b %d %YT%H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%b %d %YT%H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%B %d %Y %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%B %d %Y %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%B %d %YT%H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%B %d %YT%H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%b-%Y %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%b-%Y %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%b-%YT%H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%b-%YT%H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%B-%Y %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%B-%Y %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%B-%YT%H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%B-%YT%H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %b %Y %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %B %Y %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%b %d %Y %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%B %d %Y %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %b %Y %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %B %Y %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%b %d %Y %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%B %d %Y %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('order_date').cast(pl.String, strict=False).str.to_date(strict=False),
        pl.col('order_date').cast(pl.Date, strict=False)
    ]).alias('order_date')
)

var_select_2941539277456 = var_select_2941539277456.with_columns(
    pl.col('order_value').cast(pl.Float64, strict=False).alias('order_value')
)

var_select_2941539503952 = var_file_input_2941539272496.select(['customer_id', 'name', 'age', 'email', 'region_id'])

var_select_2941539505712 = var_file_input_2941539273936.select(['product_id', 'name', 'category', 'price'])

var_select_2941539507792 = var_file_input_2941539275216.select(['region_id', 'region_name'])

from trigger_designer.core.utils.cleansing_util import DataCleansing, NullStrategy
import polars as pl
# Convert LazyFrame to DataFrame if needed
_cleansing_input = var_select_2941539277456.collect() if hasattr(var_select_2941539277456, 'collect') else var_select_2941539277456
cleaner = DataCleansing(_cleansing_input)
cleaner.replace_null_defaults(replace_strings=True, replace_numbers=True)
var_cleansing_2941539651568 = cleaner.get_result()
# Filter data into true and false results
var_t_filter_2941539661968 = var_cleansing_2941539651568.filter(pl.col('order_value') > 0)
var_f_filter_2941539661968 = var_cleansing_2941539651568.filter(~(pl.col('order_value') > 0))


# Polars LazyFrame Join Operation
import polars as pl

def _ensure_lazyframe(data):
    if isinstance(data, pl.DataFrame):
        return data.lazy()
    if isinstance(data, pl.LazyFrame):
        return data
    raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(data)}')

_left_input = _ensure_lazyframe(var_t_filter_2941539661968)
_right_input = _ensure_lazyframe(var_select_2941539503952)

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
var_join_2941539474544 = _result_with_indicators.filter(
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
var_l_join_2941539474544 = _result_with_indicators.filter(
    pl.col('__join_type') == 'left_only'
).select(_left_cols)

# Extract right-only data efficiently
_right_cols = ['customer_id', 'name', 'age', 'email', 'region_id']
var_r_join_2941539474544 = _result_with_indicators.filter(
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

_left_input = _ensure_lazyframe(var_join_2941539474544)
_right_input = _ensure_lazyframe(var_select_2941539505712)
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
var_join_2941539482064 = _result_with_indicators.filter(
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
var_l_join_2941539482064 = _result_with_indicators.filter(
    pl.col('__join_type') == 'left_only'
).select(_left_cols)

# Extract right-only data efficiently
_right_cols = ['product_id', 'name_right', 'category', 'price']
var_r_join_2941539482064 = _result_with_indicators.filter(
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

_left_input = _ensure_lazyframe(var_join_2941539482064)
_right_input = _ensure_lazyframe(var_select_2941539507792)

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
var_join_2941539648688 = _result_with_indicators.filter(
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
var_l_join_2941539648688 = _result_with_indicators.filter(
    pl.col('__join_type') == 'left_only'
).select(_left_cols)

# Extract right-only data efficiently
_right_cols = ['region_id', 'region_name']
var_r_join_2941539648688 = _result_with_indicators.filter(
    pl.col('__join_type') == 'right_only'
).select(_right_cols)

# Clean up temporary variables
del _left_input, _right_input, _join_result, _result_with_indicators, _left_cols, _right_cols
import duckdb
import polars as pl
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_join_2941539648688.collect() if hasattr(var_join_2941539648688, 'collect') else var_join_2941539648688
duck.register('df_step_0', df_for_duck)
df_for_duck = duck.execute('''SELECT *, YEAR("order_date") AS "year" FROM df_step_0''').pl()
# Preserve lazy execution when the incoming value is lazy
var_formula_2941539510992 = df_for_duck.lazy() if hasattr(var_join_2941539648688, 'collect') else df_for_duck
duck.close()
