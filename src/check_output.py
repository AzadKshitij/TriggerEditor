import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_2700637637200 = pl.scan_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/src/test_customers.csv', infer_schema=False)

# var_file_input_2700637637200 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_2700637638960 = pl.scan_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/src/test_orders.csv', infer_schema=False)

# var_file_input_2700637638960 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
# Polars LazyFrame Join Operation
import polars as pl


# Perform full outer join with coalesce (automatic conflict resolution)
_join_result = var_file_input_2700637637200.join(
    var_file_input_2700637638960,
    left_on=['customer_id'],
    right_on=['customer_id'],
    how='full',
    coalesce=True
)

# OPTIMIZED: Extract all join types from single result (much faster!)
# Add join type indicator to identify record sources
_result_with_indicators = _join_result.with_columns([
    pl.when(pl.col('customer_id').is_null() | pl.col('order_id').is_null() | pl.col('order_amount').is_null() | pl.col('order_date').is_null() | pl.col('product_category').is_null())
      .then(pl.lit('left_only'))
      .when(pl.col('customer_id').is_null() | pl.col('customer_name').is_null() | pl.col('city').is_null() | pl.col('signup_date').is_null() | pl.col('customer_status').is_null())
      .then(pl.lit('right_only'))
      .otherwise(pl.lit('both'))
      .alias('__join_type')
])

# Main join result with selected columns (matched records only)
var_join_2700637640400 = _result_with_indicators.filter(
    pl.col('__join_type') == 'both'
).select([
    'city',
    'customer_id',
    'customer_name',
    'customer_status',
    'signup_date',
    'order_amount',
    'order_date',
    'order_id',
    'product_category'
])

# Extract left-only data efficiently
_left_cols = ['customer_id', 'customer_name', 'city', 'signup_date', 'customer_status']
var_l_join_2700637640400 = _result_with_indicators.filter(
    pl.col('__join_type') == 'left_only'
).select(_left_cols)

# Extract right-only data efficiently
_right_cols = ['customer_id', 'order_id', 'order_amount', 'order_date', 'product_category']
var_r_join_2700637640400 = _result_with_indicators.filter(
    pl.col('__join_type') == 'right_only'
).select(_right_cols)

# Clean up temporary variables
del _join_result, _result_with_indicators, _left_cols, _right_cols
