import os as _td_os
import sys as _td_sys
if _td_os.path.isdir(
    _td_os.path.join(_td_os.path.dirname(_td_os.path.abspath(__file__)), "src")
):
    _td_sys.path.insert(
        0,
        _td_os.path.join(_td_os.path.dirname(_td_os.path.abspath(__file__)), "src"),
    )
import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_2051873347440 = pl.scan_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/data/channels.csv', infer_schema=False)

# var_file_input_2051873347440 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_2051877570992 = pl.scan_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/data/orders.csv', infer_schema=False)

# var_file_input_2051877570992 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_2051877572592 = pl.scan_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/data/customers.csv', infer_schema=False)

# var_file_input_2051877572592 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_2051877574032 = pl.scan_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/data/products.csv', infer_schema=False)

# var_file_input_2051877574032 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_2051877575632 = pl.scan_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/data/suppliers.csv', infer_schema=False)

# var_file_input_2051877575632 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_2051877577232 = pl.scan_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/data/fx_rates.csv', infer_schema=False)

# var_file_input_2051877577232 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
var_select_2051877828112 = var_file_input_2051873347440.select(['channel_id', 'channel_name', 'channel_group', 'is_digital'])
var_select_2051877828112 = var_select_2051877828112.with_columns([
    pl.col('channel_id').cast(pl.Int64, strict=False).alias('channel_id')
])
var_select_2051877579952 = var_file_input_2051877570992.select([' Order ID ', 'Customer_Id', 'PRODUCT_ID', 'supplier id', 'Channel ID', 'Currency', 'Order TS', 'Quantity', 'unit_price_local', 'Discount Pct', 'tax_local', 'shipping_local', 'Status', 'Payment Method', 'is_returned'])
var_select_2051877579952 = var_select_2051877579952.with_columns([
    pl.col('Customer_Id').cast(pl.Int64, strict=False).alias('Customer_Id'),
    pl.col('PRODUCT_ID').cast(pl.Int64, strict=False).alias('PRODUCT_ID'),
    pl.col('supplier id').cast(pl.Int64, strict=False).alias('supplier id'),
    pl.col('Channel ID').cast(pl.Int64, strict=False).alias('Channel ID'),
    pl.coalesce([
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y-%m-%d %H:%M:%S', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y-%m-%d %H:%M', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y-%m-%dT%H:%M:%S', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y-%m-%dT%H:%M', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y/%m/%d %H:%M:%S', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y/%m/%d %H:%M', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y/%m/%dT%H:%M:%S', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y/%m/%dT%H:%M', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y.%m.%d %H:%M:%S', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y.%m.%d %H:%M', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y.%m.%dT%H:%M:%S', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y.%m.%dT%H:%M', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%m-%Y %H:%M:%S', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%m-%Y %H:%M', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%m-%YT%H:%M:%S', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%m-%YT%H:%M', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d/%m/%Y %H:%M:%S', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d/%m/%Y %H:%M', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d/%m/%YT%H:%M:%S', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d/%m/%YT%H:%M', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d.%m.%Y %H:%M:%S', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d.%m.%Y %H:%M', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d.%m.%YT%H:%M:%S', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d.%m.%YT%H:%M', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m-%d-%Y %H:%M:%S', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m-%d-%Y %H:%M', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m-%d-%YT%H:%M:%S', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m-%d-%YT%H:%M', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m/%d/%Y %H:%M:%S', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m/%d/%Y %H:%M', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m/%d/%YT%H:%M:%S', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m/%d/%YT%H:%M', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m.%d.%Y %H:%M:%S', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m.%d.%Y %H:%M', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m.%d.%YT%H:%M:%S', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m.%d.%YT%H:%M', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %b %Y %H:%M:%S', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %b %Y %H:%M', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %b %YT%H:%M:%S', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %b %YT%H:%M', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %B %Y %H:%M:%S', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %B %Y %H:%M', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %B %YT%H:%M:%S', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %B %YT%H:%M', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%b %d %Y %H:%M:%S', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%b %d %Y %H:%M', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%b %d %YT%H:%M:%S', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%b %d %YT%H:%M', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%B %d %Y %H:%M:%S', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%B %d %Y %H:%M', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%B %d %YT%H:%M:%S', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%B %d %YT%H:%M', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%b-%Y %H:%M:%S', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%b-%Y %H:%M', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%b-%YT%H:%M:%S', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%b-%YT%H:%M', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%B-%Y %H:%M:%S', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%B-%Y %H:%M', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%B-%YT%H:%M:%S', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%B-%YT%H:%M', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %b %Y %H:%M:%S', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %B %Y %H:%M:%S', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%b %d %Y %H:%M:%S', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%B %d %Y %H:%M:%S', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %b %Y %H:%M', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %B %Y %H:%M', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%b %d %Y %H:%M', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%B %d %Y %H:%M', strict=False, exact=True),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Date, '%Y-%m-%d', strict=False, exact=True).cast(pl.Datetime, strict=False),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Date, '%Y/%m/%d', strict=False, exact=True).cast(pl.Datetime, strict=False),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Date, '%Y.%m.%d', strict=False, exact=True).cast(pl.Datetime, strict=False),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Date, '%d-%m-%Y', strict=False, exact=True).cast(pl.Datetime, strict=False),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Date, '%d/%m/%Y', strict=False, exact=True).cast(pl.Datetime, strict=False),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Date, '%d.%m.%Y', strict=False, exact=True).cast(pl.Datetime, strict=False),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Date, '%m-%d-%Y', strict=False, exact=True).cast(pl.Datetime, strict=False),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Date, '%m/%d/%Y', strict=False, exact=True).cast(pl.Datetime, strict=False),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Date, '%m.%d.%Y', strict=False, exact=True).cast(pl.Datetime, strict=False),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Date, '%d %b %Y', strict=False, exact=True).cast(pl.Datetime, strict=False),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Date, '%d %B %Y', strict=False, exact=True).cast(pl.Datetime, strict=False),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Date, '%b %d %Y', strict=False, exact=True).cast(pl.Datetime, strict=False),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Date, '%B %d %Y', strict=False, exact=True).cast(pl.Datetime, strict=False),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Date, '%d-%b-%Y', strict=False, exact=True).cast(pl.Datetime, strict=False),
        pl.col('Order TS').cast(pl.String, strict=False).str.strptime(pl.Date, '%d-%B-%Y', strict=False, exact=True).cast(pl.Datetime, strict=False),
        pl.col('Order TS').cast(pl.String, strict=False).str.to_datetime(strict=False),
        pl.col('Order TS').cast(pl.Datetime, strict=False)
    ]).alias('Order TS'),
    pl.col('Quantity').cast(pl.Int64, strict=False).alias('Quantity'),
    pl.col('unit_price_local').cast(pl.Float64, strict=False).alias('unit_price_local'),
    pl.col('Discount Pct').cast(pl.Float64, strict=False).alias('Discount Pct'),
    pl.col('tax_local').cast(pl.Float64, strict=False).alias('tax_local'),
    pl.col('shipping_local').cast(pl.Float64, strict=False).alias('shipping_local')
])
var_select_2051877830032 = var_file_input_2051877572592.select(['customer_id', 'email', 'full_name', 'signup_date', 'country', 'region', 'currency', 'segment', 'age_band', 'loyalty_tier'])
var_select_2051877830032 = var_select_2051877830032.with_columns([
    pl.col('customer_id').cast(pl.Int64, strict=False).alias('customer_id'),
    pl.coalesce([
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Date, '%Y-%m-%d', strict=False, exact=True),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Date, '%Y/%m/%d', strict=False, exact=True),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Date, '%Y.%m.%d', strict=False, exact=True),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Date, '%d-%m-%Y', strict=False, exact=True),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Date, '%d/%m/%Y', strict=False, exact=True),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Date, '%d.%m.%Y', strict=False, exact=True),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Date, '%m-%d-%Y', strict=False, exact=True),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Date, '%m/%d/%Y', strict=False, exact=True),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Date, '%m.%d.%Y', strict=False, exact=True),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Date, '%d %b %Y', strict=False, exact=True),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Date, '%d %B %Y', strict=False, exact=True),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Date, '%b %d %Y', strict=False, exact=True),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Date, '%B %d %Y', strict=False, exact=True),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Date, '%d-%b-%Y', strict=False, exact=True),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Date, '%d-%B-%Y', strict=False, exact=True),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y-%m-%d %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y-%m-%d %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y-%m-%dT%H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y-%m-%dT%H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y/%m/%d %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y/%m/%d %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y/%m/%dT%H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y/%m/%dT%H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y.%m.%d %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y.%m.%d %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y.%m.%dT%H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y.%m.%dT%H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%m-%Y %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%m-%Y %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%m-%YT%H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%m-%YT%H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d/%m/%Y %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d/%m/%Y %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d/%m/%YT%H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d/%m/%YT%H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d.%m.%Y %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d.%m.%Y %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d.%m.%YT%H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d.%m.%YT%H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m-%d-%Y %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m-%d-%Y %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m-%d-%YT%H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m-%d-%YT%H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m/%d/%Y %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m/%d/%Y %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m/%d/%YT%H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m/%d/%YT%H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m.%d.%Y %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m.%d.%Y %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m.%d.%YT%H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m.%d.%YT%H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %b %Y %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %b %Y %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %b %YT%H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %b %YT%H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %B %Y %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %B %Y %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %B %YT%H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %B %YT%H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%b %d %Y %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%b %d %Y %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%b %d %YT%H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%b %d %YT%H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%B %d %Y %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%B %d %Y %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%B %d %YT%H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%B %d %YT%H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%b-%Y %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%b-%Y %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%b-%YT%H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%b-%YT%H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%B-%Y %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%B-%Y %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%B-%YT%H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%B-%YT%H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %b %Y %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %B %Y %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%b %d %Y %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%B %d %Y %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %b %Y %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %B %Y %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%b %d %Y %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%B %d %Y %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('signup_date').cast(pl.String, strict=False).str.to_date(strict=False),
        pl.col('signup_date').cast(pl.Date, strict=False)
    ]).alias('signup_date')
])
var_select_2051877830032 = var_select_2051877830032.rename({'email': 'customer_email', 'full_name': 'customer_name', 'country': 'customer_country', 'currency': 'customer_currency', 'age_band': 'customer_age_band'})
var_select_2051877849040 = var_file_input_2051877574032.select(['product_id', 'sku', 'product_name', 'category', 'subcategory', 'brand', 'unit_price', 'unit_cost', 'launch_date'])
var_select_2051877849040 = var_select_2051877849040.with_columns([
    pl.col('product_id').cast(pl.Int64, strict=False).alias('product_id'),
    pl.col('unit_price').cast(pl.Float64, strict=False).alias('unit_price'),
    pl.col('unit_cost').cast(pl.Float64, strict=False).alias('unit_cost'),
    pl.coalesce([
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Date, '%Y-%m-%d', strict=False, exact=True),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Date, '%Y/%m/%d', strict=False, exact=True),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Date, '%Y.%m.%d', strict=False, exact=True),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Date, '%d-%m-%Y', strict=False, exact=True),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Date, '%d/%m/%Y', strict=False, exact=True),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Date, '%d.%m.%Y', strict=False, exact=True),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Date, '%m-%d-%Y', strict=False, exact=True),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Date, '%m/%d/%Y', strict=False, exact=True),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Date, '%m.%d.%Y', strict=False, exact=True),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Date, '%d %b %Y', strict=False, exact=True),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Date, '%d %B %Y', strict=False, exact=True),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Date, '%b %d %Y', strict=False, exact=True),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Date, '%B %d %Y', strict=False, exact=True),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Date, '%d-%b-%Y', strict=False, exact=True),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Date, '%d-%B-%Y', strict=False, exact=True),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y-%m-%d %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y-%m-%d %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y-%m-%dT%H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y-%m-%dT%H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y/%m/%d %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y/%m/%d %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y/%m/%dT%H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y/%m/%dT%H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y.%m.%d %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y.%m.%d %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y.%m.%dT%H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y.%m.%dT%H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%m-%Y %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%m-%Y %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%m-%YT%H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%m-%YT%H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d/%m/%Y %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d/%m/%Y %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d/%m/%YT%H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d/%m/%YT%H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d.%m.%Y %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d.%m.%Y %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d.%m.%YT%H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d.%m.%YT%H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m-%d-%Y %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m-%d-%Y %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m-%d-%YT%H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m-%d-%YT%H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m/%d/%Y %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m/%d/%Y %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m/%d/%YT%H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m/%d/%YT%H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m.%d.%Y %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m.%d.%Y %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m.%d.%YT%H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m.%d.%YT%H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %b %Y %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %b %Y %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %b %YT%H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %b %YT%H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %B %Y %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %B %Y %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %B %YT%H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %B %YT%H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%b %d %Y %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%b %d %Y %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%b %d %YT%H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%b %d %YT%H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%B %d %Y %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%B %d %Y %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%B %d %YT%H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%B %d %YT%H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%b-%Y %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%b-%Y %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%b-%YT%H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%b-%YT%H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%B-%Y %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%B-%Y %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%B-%YT%H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%B-%YT%H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %b %Y %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %B %Y %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%b %d %Y %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%B %d %Y %H:%M:%S', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %b %Y %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %B %Y %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%b %d %Y %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%B %d %Y %H:%M', strict=False, exact=True).cast(pl.Date, strict=False),
        pl.col('launch_date').cast(pl.String, strict=False).str.to_date(strict=False),
        pl.col('launch_date').cast(pl.Date, strict=False)
    ]).alias('launch_date')
])
var_select_2051877850960 = var_file_input_2051877575632.select(['supplier_id', 'supplier_name', 'country', 'lead_time_days', 'reliability_score'])
var_select_2051877850960 = var_select_2051877850960.with_columns([
    pl.col('supplier_id').cast(pl.Int64, strict=False).alias('supplier_id'),
    pl.col('lead_time_days').cast(pl.Int64, strict=False).alias('lead_time_days'),
    pl.col('reliability_score').cast(pl.Float64, strict=False).alias('reliability_score')
])
var_select_2051877852880 = var_file_input_2051877577232.select(['currency', 'currency_name', 'usd_rate'])
var_select_2051877852880 = var_select_2051877852880.with_columns([
    pl.col('usd_rate').cast(pl.Float64, strict=False).alias('usd_rate')
])
import duckdb
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_select_2051877828112.collect() if hasattr(var_select_2051877828112, 'collect') else var_select_2051877828112
duck.register('df_for_duck', df_for_duck)
df_for_duck = duck.execute('''WITH df_step_0 AS (SELECT *, 'channels' AS "source_table" FROM df_for_duck) SELECT * FROM df_step_0''').pl()
# Widen DuckDB-native types into Select-supported dtypes
df_for_duck = normalize_to_supported_dtypes(df_for_duck)
# Preserve lazy execution when the incoming value is lazy
var_formula_2052317759920 = df_for_duck.lazy() if hasattr(var_select_2051877828112, 'collect') else df_for_duck
duck.close()
import polars as pl
# Normalize column names (11 renamed)
var_normalize_columns_2051878183920 = var_select_2051877579952.rename({' Order ID ': 'order_id', 'Customer_Id': 'customer_id', 'PRODUCT_ID': 'product_id', 'supplier id': 'supplier_id', 'Channel ID': 'channel_id', 'Currency': 'currency', 'Order TS': 'order_ts', 'Quantity': 'quantity', 'Discount Pct': 'discount_pct', 'Status': 'status', 'Payment Method': 'payment_method'})
import duckdb
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_select_2051877830032.collect() if hasattr(var_select_2051877830032, 'collect') else var_select_2051877830032
duck.register('df_for_duck', df_for_duck)
df_for_duck = duck.execute('''WITH df_step_0 AS (SELECT *, 'customers' AS "source_table" FROM df_for_duck) SELECT * FROM df_step_0''').pl()
# Widen DuckDB-native types into Select-supported dtypes
df_for_duck = normalize_to_supported_dtypes(df_for_duck)
# Preserve lazy execution when the incoming value is lazy
var_formula_2052317655792 = df_for_duck.lazy() if hasattr(var_select_2051877830032, 'collect') else df_for_duck
duck.close()
import duckdb
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_select_2051877849040.collect() if hasattr(var_select_2051877849040, 'collect') else var_select_2051877849040
duck.register('df_for_duck', df_for_duck)
df_for_duck = duck.execute('''WITH df_step_0 AS (SELECT *, 'products' AS "source_table" FROM df_for_duck) SELECT * FROM df_step_0''').pl()
# Widen DuckDB-native types into Select-supported dtypes
df_for_duck = normalize_to_supported_dtypes(df_for_duck)
# Preserve lazy execution when the incoming value is lazy
var_formula_2052317657712 = df_for_duck.lazy() if hasattr(var_select_2051877849040, 'collect') else df_for_duck
duck.close()
import duckdb
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_select_2051877850960.collect() if hasattr(var_select_2051877850960, 'collect') else var_select_2051877850960
duck.register('df_for_duck', df_for_duck)
df_for_duck = duck.execute('''WITH df_step_0 AS (SELECT *, 'suppliers' AS "source_table" FROM df_for_duck) SELECT * FROM df_step_0''').pl()
# Widen DuckDB-native types into Select-supported dtypes
df_for_duck = normalize_to_supported_dtypes(df_for_duck)
# Preserve lazy execution when the incoming value is lazy
var_formula_2052317758000 = df_for_duck.lazy() if hasattr(var_select_2051877850960, 'collect') else df_for_duck
duck.close()
import duckdb
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_select_2051877852880.collect() if hasattr(var_select_2051877852880, 'collect') else var_select_2051877852880
duck.register('df_for_duck', df_for_duck)
df_for_duck = duck.execute('''WITH df_step_0 AS (SELECT * REPLACE (LOWER("currency") AS "currency") FROM df_for_duck) SELECT * FROM df_step_0''').pl()
# Widen DuckDB-native types into Select-supported dtypes
df_for_duck = normalize_to_supported_dtypes(df_for_duck)
# Preserve lazy execution when the incoming value is lazy
var_formula_2051878297008 = df_for_duck.lazy() if hasattr(var_select_2051877852880, 'collect') else df_for_duck
duck.close()
from trigger_designer.core.utils.cleansing_util import DataCleansing, NullStrategy
import polars as pl
# Convert LazyFrame to DataFrame if needed
_cleansing_input = var_normalize_columns_2051878183920.collect() if hasattr(var_normalize_columns_2051878183920, 'collect') else var_normalize_columns_2051878183920
cleaner = DataCleansing(_cleansing_input)
cleaner.strip_whitespace(remove_all=False, normalize_spaces=True, fields=['order_id', 'customer_id', 'product_id', 'supplier_id', 'channel_id', 'currency', 'order_ts', 'quantity', 'unit_price_local', 'discount_pct', 'tax_local', 'shipping_local', 'status', 'payment_method', 'is_returned'])
var_cleansing_2051877854960 = cleaner.get_result()
var_cleansing_2051877854960 = var_cleansing_2051877854960.lazy() if hasattr(var_normalize_columns_2051878183920, 'collect') else var_cleansing_2051877854960
import polars as pl
_union_inputs_2052317763760 = [var_formula_2052317657712, var_formula_2052317655792]
var_union_2052317763760 = pl.concat([(f.lazy() if isinstance(f, pl.DataFrame) else f) for f in _union_inputs_2052317763760], how='diagonal_relaxed')
del _union_inputs_2052317763760
import duckdb
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_formula_2051878297008.collect() if hasattr(var_formula_2051878297008, 'collect') else var_formula_2051878297008
duck.register('df_for_duck', df_for_duck)
df_for_duck = duck.execute('''WITH df_step_0 AS (SELECT *, 'fx_rates' AS "source_table" FROM df_for_duck) SELECT * FROM df_step_0''').pl()
# Widen DuckDB-native types into Select-supported dtypes
df_for_duck = normalize_to_supported_dtypes(df_for_duck)
# Preserve lazy execution when the incoming value is lazy
var_formula_2052317761840 = df_for_duck.lazy() if hasattr(var_formula_2051878297008, 'collect') else df_for_duck
duck.close()
from trigger_designer.core.utils.cleansing_util import DataCleansing, NullStrategy
import polars as pl
# Convert LazyFrame to DataFrame if needed
_cleansing_input = var_cleansing_2051877854960.collect() if hasattr(var_cleansing_2051877854960, 'collect') else var_cleansing_2051877854960
cleaner = DataCleansing(_cleansing_input)
cleaner.strip_whitespace(remove_all=False, normalize_spaces=True, fields=['order_id', 'currency', 'status', 'payment_method'])
cleaner.modify_case('lower', fields=['order_id', 'currency', 'status', 'payment_method'])
var_cleansing_2052317468208 = cleaner.get_result()
var_cleansing_2052317468208 = var_cleansing_2052317468208.lazy() if hasattr(var_cleansing_2051877854960, 'collect') else var_cleansing_2052317468208
import polars as pl
_union_inputs_2052317765840 = [var_union_2052317763760, var_formula_2052317758000]
var_union_2052317765840 = pl.concat([(f.lazy() if isinstance(f, pl.DataFrame) else f) for f in _union_inputs_2052317765840], how='diagonal_relaxed')
del _union_inputs_2052317765840
from trigger_designer.core.utils.cleansing_util import DataCleansing, NullStrategy
import polars as pl
# Convert LazyFrame to DataFrame if needed
_cleansing_input = var_cleansing_2052317468208.collect() if hasattr(var_cleansing_2052317468208, 'collect') else var_cleansing_2052317468208
cleaner = DataCleansing(_cleansing_input)
cleaner.remove_rows_with_nulls(fields=['customer_id', 'product_id'])
cleaner.modify_case('lower', fields=['customer_id', 'product_id'])
var_cleansing_2051877963408 = cleaner.get_result()
var_cleansing_2051877963408 = var_cleansing_2051877963408.lazy() if hasattr(var_cleansing_2052317468208, 'collect') else var_cleansing_2051877963408
import polars as pl
_union_inputs_2052317767920 = [var_formula_2052317759920, var_union_2052317765840]
var_union_2052317767920 = pl.concat([(f.lazy() if isinstance(f, pl.DataFrame) else f) for f in _union_inputs_2052317767920], how='diagonal_relaxed')
del _union_inputs_2052317767920
# Filter data into true and false results
var_t_filter_2051877965648 = var_cleansing_2051877963408.filter(pl.col('quantity').is_between(1.0, 500.0, closed='both'))
var_f_filter_2051877965648 = var_cleansing_2051877963408.filter(~(pl.col('quantity').is_between(1.0, 500.0, closed='both')))
import polars as pl
_union_inputs_2052317770000 = [var_union_2052317767920, var_formula_2052317761840]
var_union_2052317770000 = pl.concat([(f.lazy() if isinstance(f, pl.DataFrame) else f) for f in _union_inputs_2052317770000], how='diagonal_relaxed')
del _union_inputs_2052317770000
import duckdb
import polars as pl
# Filter rows with a SQL WHERE clause (no new columns)
df_for_duck = var_t_filter_2051877965648.collect() if hasattr(var_t_filter_2051877965648, 'collect') else var_t_filter_2051877965648
duck = duckdb.connect(':memory:')
duck.register('df_filter', df_for_duck)
var_t_filter_2051878179600 = duck.execute('SELECT * FROM df_filter WHERE "unit_price_local" > 0 and \n"unit_price_local" <= 5000').pl()
var_f_filter_2051878179600 = duck.execute('SELECT * FROM df_filter WHERE NOT ("unit_price_local" > 0 and \n"unit_price_local" <= 5000)').pl()
# Preserve lazy execution when the incoming value is lazy
var_t_filter_2051878179600 = var_t_filter_2051878179600.lazy() if hasattr(var_t_filter_2051877965648, 'collect') else var_t_filter_2051878179600
var_f_filter_2051878179600 = var_f_filter_2051878179600.lazy() if hasattr(var_t_filter_2051877965648, 'collect') else var_f_filter_2051878179600
duck.close()
# Ensure we're working with a LazyFrame for memory efficiency
if var_f_filter_2051877965648 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_f_filter_2051877965648, pl.DataFrame):
        var_f_filter_2051877965648_lazy = var_f_filter_2051877965648.lazy()
    elif isinstance(var_f_filter_2051877965648, pl.LazyFrame):
        var_f_filter_2051877965648_lazy = var_f_filter_2051877965648
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_f_filter_2051877965648)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_f_filter_2051877965648_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/rejected_quantity.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/rejected_quantity.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
# Ensure we're working with a LazyFrame for memory efficiency
if var_union_2052317770000 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_union_2052317770000, pl.DataFrame):
        var_union_2052317770000_lazy = var_union_2052317770000.lazy()
    elif isinstance(var_union_2052317770000, pl.LazyFrame):
        var_union_2052317770000_lazy = var_union_2052317770000
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_union_2052317770000)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_union_2052317770000_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/reference_data_union.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/reference_data_union.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
import duckdb
import polars as pl
# Filter rows with a SQL WHERE clause (no new columns)
df_for_duck = var_t_filter_2051878179600.collect() if hasattr(var_t_filter_2051878179600, 'collect') else var_t_filter_2051878179600
duck = duckdb.connect(':memory:')
duck.register('df_filter', df_for_duck)
var_t_filter_2051878181840 = duck.execute('SELECT * FROM df_filter WHERE YEAR("order_ts") <= 2025').pl()
var_f_filter_2051878181840 = duck.execute('SELECT * FROM df_filter WHERE NOT (YEAR("order_ts") <= 2025)').pl()
# Preserve lazy execution when the incoming value is lazy
var_t_filter_2051878181840 = var_t_filter_2051878181840.lazy() if hasattr(var_t_filter_2051878179600, 'collect') else var_t_filter_2051878181840
var_f_filter_2051878181840 = var_f_filter_2051878181840.lazy() if hasattr(var_t_filter_2051878179600, 'collect') else var_f_filter_2051878181840
duck.close()
# Ensure we're working with a LazyFrame for memory efficiency
if var_f_filter_2051878179600 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_f_filter_2051878179600, pl.DataFrame):
        var_f_filter_2051878179600_lazy = var_f_filter_2051878179600.lazy()
    elif isinstance(var_f_filter_2051878179600, pl.LazyFrame):
        var_f_filter_2051878179600_lazy = var_f_filter_2051878179600
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_f_filter_2051878179600)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_f_filter_2051878179600_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/rejected_price_outliers.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/rejected_price_outliers.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
import polars as pl
# Split into unique and duplicate records based on: order_id
var_unique_2051877469904 = var_t_filter_2051878181840.unique(subset=["order_id"], maintain_order=True)
var_duplicate_2051877469904 = var_t_filter_2051878181840.filter(pl.struct(["order_id"]).is_duplicated())
# Ensure we're working with a LazyFrame for memory efficiency
if var_f_filter_2051878181840 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_f_filter_2051878181840, pl.DataFrame):
        var_f_filter_2051878181840_lazy = var_f_filter_2051878181840.lazy()
    elif isinstance(var_f_filter_2051878181840, pl.LazyFrame):
        var_f_filter_2051878181840_lazy = var_f_filter_2051878181840
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_f_filter_2051878181840)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_f_filter_2051878181840_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/rejected_future_dates.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/rejected_future_dates.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
var_select_2052317470128 = var_unique_2051877469904.select(['order_id', 'customer_id', 'product_id', 'supplier_id', 'channel_id', 'currency', 'order_ts', 'quantity', 'unit_price_local', 'discount_pct', 'tax_local', 'shipping_local', 'status', 'payment_method', 'is_returned'])
# Ensure we're working with a LazyFrame for memory efficiency
if var_unique_2051877469904 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_unique_2051877469904, pl.DataFrame):
        var_unique_2051877469904_lazy = var_unique_2051877469904.lazy()
    elif isinstance(var_unique_2051877469904, pl.LazyFrame):
        var_unique_2051877469904_lazy = var_unique_2051877469904
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_unique_2051877469904)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_unique_2051877469904_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/04 dropped null key rows.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/04 dropped null key rows.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
# Ensure we're working with a LazyFrame for memory efficiency
if var_duplicate_2051877469904 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_duplicate_2051877469904, pl.DataFrame):
        var_duplicate_2051877469904_lazy = var_duplicate_2051877469904.lazy()
    elif isinstance(var_duplicate_2051877469904, pl.LazyFrame):
        var_duplicate_2051877469904_lazy = var_duplicate_2051877469904
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_duplicate_2051877469904)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_duplicate_2051877469904_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/duplicate_orders.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/duplicate_orders.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
# Polars LazyFrame Join Operation
import polars as pl

def _ensure_lazyframe(data):
    if isinstance(data, pl.DataFrame):
        return data.lazy()
    if isinstance(data, pl.LazyFrame):
        return data
    raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(data)}')

_left_input = _ensure_lazyframe(var_select_2052317470128)
_right_input = _ensure_lazyframe(var_select_2051877830032)

# Perform full outer join with coalesce (automatic conflict resolution)
_left_tagged = _left_input.with_columns(pl.lit(1).alias('__left_present'))
_right_tagged = _right_input.with_columns(pl.lit(1).alias('__right_present'))
_join_result = _left_tagged.join(
    _right_tagged,
    left_on=['customer_id'],
    right_on=['customer_id'],
    how='full',
    coalesce=True
)

# Main join result with selected columns (matched records only)
var_join_2052316501072 = _join_result.filter(
    (pl.col('__left_present').is_not_null() & pl.col('__right_present').is_not_null())
).select([
    'channel_id',
    'currency',
    'customer_id',
    'discount_pct',
    'is_returned',
    'order_ts',
    'payment_method',
    'product_id',
    'quantity',
    'shipping_local',
    'status',
    'supplier_id',
    'tax_local',
    'unit_price_local',
    'customer_age_band',
    'customer_country',
    'customer_currency',
    'customer_email',
    'loyalty_tier',
    'region',
    'segment',
    'signup_date',
    'customer_name',
    'order_id'
])

# Extract left-only data efficiently
_left_cols = ['order_id', 'customer_id', 'product_id', 'supplier_id', 'channel_id', 'currency', 'order_ts', 'quantity', 'unit_price_local', 'discount_pct', 'tax_local', 'shipping_local', 'status', 'payment_method', 'is_returned']
var_l_join_2052316501072 = _join_result.filter(
    pl.col('__right_present').is_null()
).select(_left_cols)

# Extract right-only data efficiently
_right_cols = ['customer_id', 'customer_email', 'customer_name', 'signup_date', 'customer_country', 'region', 'customer_currency', 'segment', 'customer_age_band', 'loyalty_tier']
var_r_join_2052316501072 = _join_result.filter(
    pl.col('__left_present').is_null()
).select(_right_cols)

# Clean up temporary variables
del _left_input, _right_input, _left_tagged, _right_tagged, _join_result, _left_cols, _right_cols
# Ensure we're working with a LazyFrame for memory efficiency
if var_l_join_2052316501072 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_l_join_2052316501072, pl.DataFrame):
        var_l_join_2052316501072_lazy = var_l_join_2052316501072.lazy()
    elif isinstance(var_l_join_2052316501072, pl.LazyFrame):
        var_l_join_2052316501072_lazy = var_l_join_2052316501072
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_l_join_2052316501072)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_l_join_2052316501072_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/orphan_customers.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/orphan_customers.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
import polars as pl
_union_inputs_2052316727408 = [var_join_2052316501072, var_l_join_2052316501072]
var_union_2052316727408 = pl.concat([(f.lazy() if isinstance(f, pl.DataFrame) else f) for f in _union_inputs_2052316727408], how='diagonal_relaxed')
del _union_inputs_2052316727408
# Polars LazyFrame Join Operation
import polars as pl

def _ensure_lazyframe(data):
    if isinstance(data, pl.DataFrame):
        return data.lazy()
    if isinstance(data, pl.LazyFrame):
        return data
    raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(data)}')

_left_input = _ensure_lazyframe(var_union_2052316727408)
_right_input = _ensure_lazyframe(var_select_2051877849040)

# Perform full outer join with coalesce (automatic conflict resolution)
_left_tagged = _left_input.with_columns(pl.lit(1).alias('__left_present'))
_right_tagged = _right_input.with_columns(pl.lit(1).alias('__right_present'))
_join_result = _left_tagged.join(
    _right_tagged,
    left_on=['product_id'],
    right_on=['product_id'],
    how='full',
    coalesce=True
)

# Main join result with selected columns (matched records only)
var_join_2052316643728 = _join_result.filter(
    (pl.col('__left_present').is_not_null() & pl.col('__right_present').is_not_null())
).select([
    'channel_id',
    'currency',
    'customer_age_band',
    'customer_country',
    'customer_currency',
    'customer_email',
    'customer_id',
    'discount_pct',
    'is_returned',
    'loyalty_tier',
    'order_ts',
    'payment_method',
    'product_id',
    'quantity',
    'region',
    'segment',
    'shipping_local',
    'signup_date',
    'status',
    'supplier_id',
    'tax_local',
    'unit_price_local',
    'brand',
    'category',
    'launch_date',
    'product_name',
    'sku',
    'subcategory',
    'unit_cost',
    'unit_price',
    'customer_name',
    'order_id'
])

# Extract left-only data efficiently
_left_cols = ['channel_id', 'currency', 'customer_id', 'discount_pct', 'is_returned', 'order_ts', 'payment_method', 'product_id', 'quantity', 'shipping_local', 'status', 'supplier_id', 'tax_local', 'unit_price_local', 'customer_age_band', 'customer_country', 'customer_currency', 'customer_email', 'loyalty_tier', 'region', 'segment', 'signup_date', 'customer_name', 'order_id']
var_l_join_2052316643728 = _join_result.filter(
    pl.col('__right_present').is_null()
).select(_left_cols)

# Extract right-only data efficiently
_right_cols = ['product_id', 'sku', 'product_name', 'category', 'subcategory', 'brand', 'unit_price', 'unit_cost', 'launch_date']
var_r_join_2052316643728 = _join_result.filter(
    pl.col('__left_present').is_null()
).select(_right_cols)

# Clean up temporary variables
del _left_input, _right_input, _left_tagged, _right_tagged, _join_result, _left_cols, _right_cols
# Ensure we're working with a LazyFrame for memory efficiency
if var_union_2052316727408 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_union_2052316727408, pl.DataFrame):
        var_union_2052316727408_lazy = var_union_2052316727408.lazy()
    elif isinstance(var_union_2052316727408, pl.LazyFrame):
        var_union_2052316727408_lazy = var_union_2052316727408
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_union_2052316727408)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_union_2052316727408_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/01 enriched customer_id.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/01 enriched customer_id.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
# Ensure we're working with a LazyFrame for memory efficiency
if var_l_join_2052316643728 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_l_join_2052316643728, pl.DataFrame):
        var_l_join_2052316643728_lazy = var_l_join_2052316643728.lazy()
    elif isinstance(var_l_join_2052316643728, pl.LazyFrame):
        var_l_join_2052316643728_lazy = var_l_join_2052316643728
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_l_join_2052316643728)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_l_join_2052316643728_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/orphan_products.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/orphan_products.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
import polars as pl
_union_inputs_2052316737168 = [var_join_2052316643728, var_l_join_2052316643728]
var_union_2052316737168 = pl.concat([(f.lazy() if isinstance(f, pl.DataFrame) else f) for f in _union_inputs_2052316737168], how='diagonal_relaxed')
del _union_inputs_2052316737168
# Polars LazyFrame Join Operation
import polars as pl

def _ensure_lazyframe(data):
    if isinstance(data, pl.DataFrame):
        return data.lazy()
    if isinstance(data, pl.LazyFrame):
        return data
    raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(data)}')

_left_input = _ensure_lazyframe(var_union_2052316737168)
_right_input = _ensure_lazyframe(var_select_2051877850960)

# Perform full outer join with coalesce (automatic conflict resolution)
_left_tagged = _left_input.with_columns(pl.lit(1).alias('__left_present'))
_right_tagged = _right_input.with_columns(pl.lit(1).alias('__right_present'))
_join_result = _left_tagged.join(
    _right_tagged,
    left_on=['supplier_id'],
    right_on=['supplier_id'],
    how='full',
    coalesce=True
)

# Main join result with selected columns (matched records only)
var_join_2052316646768 = _join_result.filter(
    (pl.col('__left_present').is_not_null() & pl.col('__right_present').is_not_null())
).select([
    'brand',
    'category',
    'channel_id',
    'currency',
    'customer_age_band',
    'customer_country',
    'customer_currency',
    'customer_email',
    'customer_id',
    'discount_pct',
    'is_returned',
    'launch_date',
    'loyalty_tier',
    'order_ts',
    'payment_method',
    'product_id',
    'product_name',
    'quantity',
    'region',
    'segment',
    'shipping_local',
    'signup_date',
    'sku',
    'status',
    'subcategory',
    'supplier_id',
    'tax_local',
    'unit_cost',
    'unit_price',
    'unit_price_local',
    'country',
    'lead_time_days',
    'reliability_score',
    'supplier_name',
    'customer_name',
    'order_id'
])

# Extract left-only data efficiently
_left_cols = ['channel_id', 'currency', 'customer_age_band', 'customer_country', 'customer_currency', 'customer_email', 'customer_id', 'discount_pct', 'is_returned', 'loyalty_tier', 'order_ts', 'payment_method', 'product_id', 'quantity', 'region', 'segment', 'shipping_local', 'signup_date', 'status', 'supplier_id', 'tax_local', 'unit_price_local', 'brand', 'category', 'launch_date', 'product_name', 'sku', 'subcategory', 'unit_cost', 'unit_price', 'customer_name', 'order_id']
var_l_join_2052316646768 = _join_result.filter(
    pl.col('__right_present').is_null()
).select(_left_cols)

# Extract right-only data efficiently
_right_cols = ['supplier_id', 'supplier_name', 'country', 'lead_time_days', 'reliability_score']
var_r_join_2052316646768 = _join_result.filter(
    pl.col('__left_present').is_null()
).select(_right_cols)

# Clean up temporary variables
del _left_input, _right_input, _left_tagged, _right_tagged, _join_result, _left_cols, _right_cols
# Ensure we're working with a LazyFrame for memory efficiency
if var_union_2052316737168 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_union_2052316737168, pl.DataFrame):
        var_union_2052316737168_lazy = var_union_2052316737168.lazy()
    elif isinstance(var_union_2052316737168, pl.LazyFrame):
        var_union_2052316737168_lazy = var_union_2052316737168
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_union_2052316737168)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_union_2052316737168_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/02 enriched product_id.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/02 enriched product_id.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
import polars as pl
_union_inputs_2052316739248 = [var_join_2052316646768, var_l_join_2052316646768]
var_union_2052316739248 = pl.concat([(f.lazy() if isinstance(f, pl.DataFrame) else f) for f in _union_inputs_2052316739248], how='diagonal_relaxed')
del _union_inputs_2052316739248
# Polars LazyFrame Join Operation
import polars as pl

def _ensure_lazyframe(data):
    if isinstance(data, pl.DataFrame):
        return data.lazy()
    if isinstance(data, pl.LazyFrame):
        return data
    raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(data)}')

_left_input = _ensure_lazyframe(var_union_2052316739248)
_right_input = _ensure_lazyframe(var_select_2051877828112)

# Perform full outer join with coalesce (automatic conflict resolution)
_left_tagged = _left_input.with_columns(pl.lit(1).alias('__left_present'))
_right_tagged = _right_input.with_columns(pl.lit(1).alias('__right_present'))
_join_result = _left_tagged.join(
    _right_tagged,
    left_on=['channel_id'],
    right_on=['channel_id'],
    how='full',
    coalesce=True
)

# Main join result with selected columns (matched records only)
var_join_2052316649808 = _join_result.filter(
    (pl.col('__left_present').is_not_null() & pl.col('__right_present').is_not_null())
).select([
    'brand',
    'category',
    'channel_id',
    'country',
    'currency',
    'customer_age_band',
    'customer_country',
    'customer_currency',
    'customer_email',
    'customer_id',
    'discount_pct',
    'is_returned',
    'launch_date',
    'lead_time_days',
    'loyalty_tier',
    'order_ts',
    'payment_method',
    'product_id',
    'product_name',
    'quantity',
    'region',
    'reliability_score',
    'segment',
    'shipping_local',
    'signup_date',
    'sku',
    'status',
    'subcategory',
    'supplier_id',
    'supplier_name',
    'tax_local',
    'unit_cost',
    'unit_price',
    'unit_price_local',
    'channel_group',
    'channel_name',
    'is_digital',
    'order_id'
])

# Extract left-only data efficiently
_left_cols = ['brand', 'category', 'channel_id', 'currency', 'customer_age_band', 'customer_country', 'customer_currency', 'customer_email', 'customer_id', 'discount_pct', 'is_returned', 'launch_date', 'loyalty_tier', 'order_ts', 'payment_method', 'product_id', 'product_name', 'quantity', 'region', 'segment', 'shipping_local', 'signup_date', 'sku', 'status', 'subcategory', 'supplier_id', 'tax_local', 'unit_cost', 'unit_price', 'unit_price_local', 'country', 'lead_time_days', 'reliability_score', 'supplier_name', 'customer_name', 'order_id']
var_l_join_2052316649808 = _join_result.filter(
    pl.col('__right_present').is_null()
).select(_left_cols)

# Extract right-only data efficiently
_right_cols = ['channel_id', 'channel_name', 'channel_group', 'is_digital']
var_r_join_2052316649808 = _join_result.filter(
    pl.col('__left_present').is_null()
).select(_right_cols)

# Clean up temporary variables
del _left_input, _right_input, _left_tagged, _right_tagged, _join_result, _left_cols, _right_cols
# Ensure we're working with a LazyFrame for memory efficiency
if var_union_2052316739248 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_union_2052316739248, pl.DataFrame):
        var_union_2052316739248_lazy = var_union_2052316739248.lazy()
    elif isinstance(var_union_2052316739248, pl.LazyFrame):
        var_union_2052316739248_lazy = var_union_2052316739248
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_union_2052316739248)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_union_2052316739248_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/03 enriched supplier_id.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/03 enriched supplier_id.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
import polars as pl
_union_inputs_2052316741328 = [var_join_2052316649808, var_l_join_2052316649808]
var_union_2052316741328 = pl.concat([(f.lazy() if isinstance(f, pl.DataFrame) else f) for f in _union_inputs_2052316741328], how='diagonal_relaxed')
del _union_inputs_2052316741328
# Polars LazyFrame Join Operation
import polars as pl

def _ensure_lazyframe(data):
    if isinstance(data, pl.DataFrame):
        return data.lazy()
    if isinstance(data, pl.LazyFrame):
        return data
    raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(data)}')

_left_input = _ensure_lazyframe(var_union_2052316741328)
_right_input = _ensure_lazyframe(var_formula_2051878297008)

# Perform full outer join with coalesce (automatic conflict resolution)
_left_tagged = _left_input.with_columns(pl.lit(1).alias('__left_present'))
_right_tagged = _right_input.with_columns(pl.lit(1).alias('__right_present'))
_join_result = _left_tagged.join(
    _right_tagged,
    left_on=['currency'],
    right_on=['currency'],
    how='full',
    coalesce=True
)

# Main join result with selected columns (matched records only)
var_join_2052316652848 = _join_result.filter(
    (pl.col('__left_present').is_not_null() & pl.col('__right_present').is_not_null())
).select([
    'brand',
    'category',
    'channel_group',
    'channel_id',
    'channel_name',
    'country',
    'currency',
    'customer_age_band',
    'customer_country',
    'customer_currency',
    'customer_email',
    'customer_id',
    'discount_pct',
    'is_digital',
    'is_returned',
    'launch_date',
    'lead_time_days',
    'loyalty_tier',
    'order_ts',
    'payment_method',
    'product_id',
    'product_name',
    'quantity',
    'region',
    'reliability_score',
    'segment',
    'shipping_local',
    'signup_date',
    'sku',
    'status',
    'subcategory',
    'supplier_id',
    'supplier_name',
    'tax_local',
    'unit_cost',
    'unit_price',
    'unit_price_local',
    'currency_name',
    'usd_rate',
    'order_id'
])

# Extract left-only data efficiently
_left_cols = ['brand', 'category', 'channel_id', 'country', 'currency', 'customer_age_band', 'customer_country', 'customer_currency', 'customer_email', 'customer_id', 'discount_pct', 'is_returned', 'launch_date', 'lead_time_days', 'loyalty_tier', 'order_ts', 'payment_method', 'product_id', 'product_name', 'quantity', 'region', 'reliability_score', 'segment', 'shipping_local', 'signup_date', 'sku', 'status', 'subcategory', 'supplier_id', 'supplier_name', 'tax_local', 'unit_cost', 'unit_price', 'unit_price_local', 'channel_group', 'channel_name', 'is_digital', 'order_id', 'customer_name']
var_l_join_2052316652848 = _join_result.filter(
    pl.col('__right_present').is_null()
).select(_left_cols)

# Extract right-only data efficiently
_right_cols = ['currency', 'currency_name', 'usd_rate']
var_r_join_2052316652848 = _join_result.filter(
    pl.col('__left_present').is_null()
).select(_right_cols)

# Clean up temporary variables
del _left_input, _right_input, _left_tagged, _right_tagged, _join_result, _left_cols, _right_cols
# Ensure we're working with a LazyFrame for memory efficiency
if var_union_2052316741328 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_union_2052316741328, pl.DataFrame):
        var_union_2052316741328_lazy = var_union_2052316741328.lazy()
    elif isinstance(var_union_2052316741328, pl.LazyFrame):
        var_union_2052316741328_lazy = var_union_2052316741328
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_union_2052316741328)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_union_2052316741328_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/04 enriched channel_id.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/04 enriched channel_id.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
import polars as pl
_union_inputs_2052316809008 = [var_join_2052316652848, var_l_join_2052316652848]
var_union_2052316809008 = pl.concat([(f.lazy() if isinstance(f, pl.DataFrame) else f) for f in _union_inputs_2052316809008], how='diagonal_relaxed')
del _union_inputs_2052316809008
import duckdb
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_union_2052316809008.collect() if hasattr(var_union_2052316809008, 'collect') else var_union_2052316809008
duck.register('df_for_duck', df_for_duck)
df_for_duck = duck.execute('''WITH df_step_0 AS (SELECT *, "quantity" * "unit_price_local" AS "g" FROM df_for_duck), df_step_1 AS (SELECT *, ROUND("g", 2) AS "gross_local" FROM df_step_0), df_step_2 AS (SELECT *, ROUND("gross_local" * "discount_pct", 2) AS "discount_local" FROM df_step_1), df_step_3 AS (SELECT *, ROUND("gross_local" - "discount_local", 2) AS "net_local" FROM df_step_2), df_step_4 AS (SELECT *, ROUND("net_local" + "tax_local" + "shipping_local", 2) AS "total_local" FROM df_step_3) SELECT * FROM df_step_4''').pl()
# Widen DuckDB-native types into Select-supported dtypes
df_for_duck = normalize_to_supported_dtypes(df_for_duck)
# Preserve lazy execution when the incoming value is lazy
var_formula_2052316655888 = df_for_duck.lazy() if hasattr(var_union_2052316809008, 'collect') else df_for_duck
duck.close()
# Ensure we're working with a LazyFrame for memory efficiency
if var_union_2052316809008 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_union_2052316809008, pl.DataFrame):
        var_union_2052316809008_lazy = var_union_2052316809008.lazy()
    elif isinstance(var_union_2052316809008, pl.LazyFrame):
        var_union_2052316809008_lazy = var_union_2052316809008
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_union_2052316809008)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_union_2052316809008_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/05 enriched currency.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/05 enriched currency.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
import duckdb
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_formula_2052316655888.collect() if hasattr(var_formula_2052316655888, 'collect') else var_formula_2052316655888
duck.register('df_for_duck', df_for_duck)
df_for_duck = duck.execute('''WITH df_step_0 AS (SELECT *, ROUND("unit_price_local" * "usd_rate", 2) AS "unit_price_usd" FROM df_for_duck), df_step_1 AS (SELECT *, ROUND("net_local" * "usd_rate", 2) AS "net_revenue_usd" FROM df_step_0), df_step_2 AS (SELECT *, ROUND("tax_local" * "usd_rate", 2) AS "tax_usd" FROM df_step_1), df_step_3 AS (SELECT *, ROUND("shipping_local" * "usd_rate", 2) AS "shipping_usd" FROM df_step_2), df_step_4 AS (SELECT *, ROUND("total_local" * "usd_rate", 2) AS "total_usd" FROM df_step_3) SELECT * FROM df_step_4''').pl()
# Widen DuckDB-native types into Select-supported dtypes
df_for_duck = normalize_to_supported_dtypes(df_for_duck)
# Preserve lazy execution when the incoming value is lazy
var_formula_2052316657808 = df_for_duck.lazy() if hasattr(var_formula_2052316655888, 'collect') else df_for_duck
duck.close()
import duckdb
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_formula_2052316657808.collect() if hasattr(var_formula_2052316657808, 'collect') else var_formula_2052316657808
duck.register('df_for_duck', df_for_duck)
df_for_duck = duck.execute('''WITH df_step_0 AS (SELECT *, ROUND("quantity" * "unit_cost", 2) AS "cogs_usd" FROM df_for_duck), df_step_1 AS (SELECT *, ROUND("net_revenue_usd" - "cogs_usd", 2) AS "gross_margin_usd" FROM df_step_0), df_step_2 AS (SELECT *, ROUND(CASE
    WHEN "net_revenue_usd" IS NULL OR "net_revenue_usd" = 0 THEN NULL
    ELSE "gross_margin_usd" / "net_revenue_usd"
END, 4) AS "margin_pct" FROM df_step_1) SELECT * FROM df_step_2''').pl()
# Widen DuckDB-native types into Select-supported dtypes
df_for_duck = normalize_to_supported_dtypes(df_for_duck)
# Preserve lazy execution when the incoming value is lazy
var_formula_2052316811088 = df_for_duck.lazy() if hasattr(var_formula_2052316657808, 'collect') else df_for_duck
duck.close()
import duckdb
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_formula_2052316811088.collect() if hasattr(var_formula_2052316811088, 'collect') else var_formula_2052316811088
duck.register('df_for_duck', df_for_duck)
df_for_duck = duck.execute('''WITH df_step_0 AS (SELECT *, YEAR("order_ts") AS "order_year" FROM df_for_duck), df_step_1 AS (SELECT *, MONTH("order_ts") AS "order_month" FROM df_step_0), df_step_2 AS (SELECT *, STRFTIME("order_ts", '%Y-%m') AS "order_year_month" FROM df_step_1), df_step_3 AS (SELECT *, "quantity" >= 6 AS "is_bulk" FROM df_step_2), df_step_4 AS (SELECT *, CASE
    WHEN "net_revenue_usd" IS NULL THEN NULL
    WHEN "net_revenue_usd" <= 250  THEN 'Low'
    WHEN "net_revenue_usd" <= 1000 THEN 'Medium'
    ELSE 'High'
END
 AS "value_band" FROM df_step_3) SELECT * FROM df_step_4''').pl()
# Widen DuckDB-native types into Select-supported dtypes
df_for_duck = normalize_to_supported_dtypes(df_for_duck)
# Preserve lazy execution when the incoming value is lazy
var_formula_2052316813008 = df_for_duck.lazy() if hasattr(var_formula_2052316811088, 'collect') else df_for_duck
duck.close()
import duckdb
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_formula_2052316813008.collect() if hasattr(var_formula_2052316813008, 'collect') else var_formula_2052316813008
duck.register('df_for_duck', df_for_duck)
df_for_duck = duck.execute('''WITH df_step_0 AS (SELECT * REPLACE (CASE WHEN LOWER("is_returned") = 'true' THEN true ELSE false END AS "is_returned") FROM df_for_duck), df_step_1 AS (SELECT *, (CASE WHEN "is_returned" THEN 2 ELSE 0 END)
+ (CASE WHEN "status" IN ('refunded', 'cancelled') THEN 2 ELSE 0 END)
+ (CASE WHEN "net_revenue_usd" > 2000 THEN 1 ELSE 0 END)
+ (CASE WHEN "margin_pct" < 0.10 THEN 1 ELSE 0 END)
+ (CASE WHEN "segment" IS NULL THEN 2 ELSE 0 END)
 AS "risk_score" FROM df_step_0), df_step_2 AS (SELECT *, CASE
    WHEN "risk_score" >= 4 THEN 'High'
    WHEN "risk_score" >= 2 THEN 'Medium'
    ELSE 'Low'
END AS "risk_band" FROM df_step_1), df_step_3 AS (SELECT *, CASE "status" WHEN 'paid' THEN 'Paid'
  WHEN 'pending' THEN 'Pending'
  WHEN 'refunded' THEN 'Refunded'
  WHEN 'cancelled' THEN 'Cancelled'
  WHEN 'partially refunded' THEN 'Partially Refunded'
  ELSE "status" END AS "status_clean" FROM df_step_2) SELECT * FROM df_step_3''').pl()
# Widen DuckDB-native types into Select-supported dtypes
df_for_duck = normalize_to_supported_dtypes(df_for_duck)
# Preserve lazy execution when the incoming value is lazy
var_formula_2052316814928 = df_for_duck.lazy() if hasattr(var_formula_2052316813008, 'collect') else df_for_duck
duck.close()
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
var_groupby_2052316823088 = var_formula_2052316814928.group_by(['order_year_month']).agg([
    pl.col('net_revenue_usd').sum().alias('revenue_usd'),
    pl.col('gross_margin_usd').sum().alias('margin_usd'),
    pl.col('order_id').n_unique().alias('orders')
])
var_groupby_2052316823088 = normalize_to_supported_dtypes(var_groupby_2052316823088)
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
var_groupby_2052317065968 = var_formula_2052316814928.group_by(['category']).agg([
    pl.col('net_revenue_usd').sum().alias('revenue_usd'),
    pl.col('gross_margin_usd').sum().alias('margin_usd'),
    pl.col('order_id').n_unique().alias('orders')
])
var_groupby_2052317065968 = normalize_to_supported_dtypes(var_groupby_2052317065968)
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
var_groupby_2052317140528 = var_formula_2052316814928.group_by(['region', 'channel_group']).agg([
    pl.col('net_revenue_usd').sum().alias('revenue_usd'),
    pl.col('gross_margin_usd').sum().alias('margin_usd'),
    pl.col('order_id').n_unique().alias('orders')
])
var_groupby_2052317140528 = normalize_to_supported_dtypes(var_groupby_2052317140528)
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
var_groupby_2052317142448 = var_formula_2052316814928.group_by(['segment', 'risk_band']).agg([
    pl.col('net_revenue_usd').sum().alias('revenue_usd'),
    pl.col('gross_margin_usd').sum().alias('margin_usd'),
    pl.col('order_id').n_unique().alias('orders')
])
var_groupby_2052317142448 = normalize_to_supported_dtypes(var_groupby_2052317142448)
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
var_groupby_2052317144368 = var_formula_2052316814928.group_by(['customer_id']).agg([
    pl.col('net_revenue_usd').sum().alias('revenue_usd'),
    pl.col('order_id').n_unique().alias('orders')
])
var_groupby_2052317144368 = normalize_to_supported_dtypes(var_groupby_2052317144368)
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
var_groupby_2052317235632 = var_formula_2052316814928.group_by(['supplier_id', 'supplier_name', 'country']).agg([
    pl.col('net_revenue_usd').sum().alias('revenue_usd'),
    pl.col('order_id').n_unique().alias('orders'),
    pl.col('lead_time_days').first().alias('lead_time_days'),
    pl.col('reliability_score').first().alias('reliability_score')
])
var_groupby_2052317235632 = normalize_to_supported_dtypes(var_groupby_2052317235632)
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
var_groupby_2052317244912 = var_formula_2052316814928.group_by(['currency']).agg([
    pl.col('net_revenue_usd').sum().alias('revenue_usd'),
    pl.col('order_id').n_unique().alias('orders'),
    pl.col('usd_rate').first().alias('usd_rate')
])
var_groupby_2052317244912 = normalize_to_supported_dtypes(var_groupby_2052317244912)
var_select_2052317338096 = var_formula_2052316814928.select(['brand', 'category', 'channel_group', 'channel_id', 'channel_name', 'country', 'currency', 'customer_age_band', 'customer_country', 'customer_currency', 'customer_email', 'customer_id', 'discount_pct', 'is_digital', 'is_returned', 'launch_date', 'lead_time_days', 'loyalty_tier', 'order_id', 'order_ts', 'payment_method', 'product_id', 'product_name', 'quantity', 'region', 'reliability_score', 'segment', 'shipping_local', 'signup_date', 'sku', 'status', 'subcategory', 'supplier_id', 'supplier_name', 'tax_local', 'unit_cost', 'unit_price', 'unit_price_local', 'currency_name', 'usd_rate', 'g', 'gross_local', 'discount_local', 'net_local', 'total_local', 'unit_price_usd', 'net_revenue_usd', 'tax_usd', 'shipping_usd', 'total_usd', 'cogs_usd', 'gross_margin_usd', 'margin_pct', 'order_year', 'order_month', 'order_year_month', 'is_bulk', 'value_band', 'risk_score', 'risk_band', 'customer_name', 'status_clean'])
var_select_2052317338096 = var_select_2052317338096.with_columns([
    pl.when(pl.col('is_digital').cast(pl.String, strict=False).str.to_lowercase().str.strip_chars().is_in(('true', '1', 'yes', 'y', 't', 'on'))).then(True)
    .when(pl.col('is_digital').cast(pl.String, strict=False).str.to_lowercase().str.strip_chars().is_in(('false', '0', 'no', 'n', 'f', 'off'))).then(False)
    .when(pl.col('is_digital').cast(pl.Float64, strict=False).is_not_null() & (pl.col('is_digital').cast(pl.Float64, strict=False) != 0.0)).then(True)
    .when(pl.col('is_digital').cast(pl.Float64, strict=False).is_not_null()).then(False)
    .otherwise(None)
    .alias('is_digital'),
    pl.col('order_ts').cast(pl.String, strict=False).alias('order_ts')
])
var_select_2052317552688 = var_formula_2052316814928.select(['order_id', 'order_ts', 'order_year', 'order_month', 'order_year_month', 'customer_id', 'product_id', 'supplier_id', 'channel_id', 'channel_name', 'channel_group', 'category', 'subcategory', 'brand', 'customer_country', 'region', 'segment', 'loyalty_tier', 'currency', 'usd_rate', 'status', 'status_clean', 'quantity', 'unit_price_local', 'discount_pct', 'net_local', 'total_local', 'net_revenue_usd', 'cogs_usd', 'gross_margin_usd', 'margin_pct', 'value_band', 'risk_score', 'risk_band', 'is_returned', 'is_bulk', 'country', 'customer_age_band', 'customer_currency', 'customer_email', 'is_digital', 'launch_date', 'lead_time_days', 'payment_method', 'product_name', 'reliability_score', 'shipping_local', 'signup_date', 'sku', 'supplier_name', 'tax_local', 'unit_cost', 'unit_price', 'currency_name', 'customer_name', 'g', 'gross_local', 'discount_local', 'unit_price_usd', 'tax_usd', 'shipping_usd', 'total_usd'])
# Filter data into true and false results
var_t_filter_2052317556208 = var_formula_2052316814928.filter(pl.col('segment') == 'Enterprise')
var_f_filter_2052317556208 = var_formula_2052316814928.filter(~(pl.col('segment') == 'Enterprise'))
# Filter data into true and false results
var_t_filter_2052317560048 = var_formula_2052316814928.filter(pl.col('risk_band') == 'High')
var_f_filter_2052317560048 = var_formula_2052316814928.filter(~(pl.col('risk_band') == 'High'))
import polars as pl
# Random split with seed 42 (row-safe full shuffle)
indexed_df = var_formula_2052316814928.with_row_index('__split_idx').sort(pl.col('__split_idx').shuffle(seed=42))
var_estimation_2052317647632 = indexed_df.filter(pl.col('__split_idx') < pl.col('__split_idx').max() * 0.8).drop('__split_idx')
var_validation_2052317647632 = indexed_df.filter(pl.col('__split_idx') >= pl.col('__split_idx').max() * 0.8).drop('__split_idx')
var_sort_2052316818128 = var_groupby_2052316823088.sort('order_year_month', descending=False)
var_sort_2052317067888 = var_groupby_2052317065968.sort('revenue_usd', descending=True)
var_sort_2052317137008 = var_groupby_2052317140528.sort(['region', 'channel_group'], descending=[False, False])
var_sort_2052317343536 = var_groupby_2052317142448.sort(['segment', 'risk_band'], descending=[False, False])
# Filter data into true and false results
var_t_filter_2052317149808 = var_groupby_2052317144368.filter(pl.col('revenue_usd') > 4000)
var_f_filter_2052317149808 = var_groupby_2052317144368.filter(~(pl.col('revenue_usd') > 4000))
var_sort_2052317237552 = var_groupby_2052317235632.sort('revenue_usd', descending=True)
var_sort_2052317242992 = var_groupby_2052317244912.sort('revenue_usd', descending=True)
import duckdb
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_select_2052317338096.collect() if hasattr(var_select_2052317338096, 'collect') else var_select_2052317338096
duck.register('df_for_duck', df_for_duck)
df_for_duck = duck.execute('''WITH df_step_0 AS (SELECT *, "gross_local" * "usd_rate" AS "gross_revenue_usd_raw" FROM df_for_duck), df_step_1 AS (SELECT *, CASE WHEN "risk_band" = 'High' THEN 1 ELSE 0 END AS "is_high_risk" FROM df_step_0) SELECT * FROM df_step_1''').pl()
# Widen DuckDB-native types into Select-supported dtypes
df_for_duck = normalize_to_supported_dtypes(df_for_duck)
# Preserve lazy execution when the incoming value is lazy
var_formula_2052317332336 = df_for_duck.lazy() if hasattr(var_select_2052317338096, 'collect') else df_for_duck
duck.close()
# Ensure we're working with a LazyFrame for memory efficiency
if var_select_2052317552688 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_select_2052317552688, pl.DataFrame):
        var_select_2052317552688_lazy = var_select_2052317552688.lazy()
    elif isinstance(var_select_2052317552688, pl.LazyFrame):
        var_select_2052317552688_lazy = var_select_2052317552688
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_select_2052317552688)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_select_2052317552688_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/orders_enriched.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/orders_enriched.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
# Ensure we're working with a LazyFrame for memory efficiency
if var_t_filter_2052317556208 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_t_filter_2052317556208, pl.DataFrame):
        var_t_filter_2052317556208_lazy = var_t_filter_2052317556208.lazy()
    elif isinstance(var_t_filter_2052317556208, pl.LazyFrame):
        var_t_filter_2052317556208_lazy = var_t_filter_2052317556208
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_t_filter_2052317556208)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_t_filter_2052317556208_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/orders_enterprise.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/orders_enterprise.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
# Ensure we're working with a LazyFrame for memory efficiency
if var_t_filter_2052317560048 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_t_filter_2052317560048, pl.DataFrame):
        var_t_filter_2052317560048_lazy = var_t_filter_2052317560048.lazy()
    elif isinstance(var_t_filter_2052317560048, pl.LazyFrame):
        var_t_filter_2052317560048_lazy = var_t_filter_2052317560048
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_t_filter_2052317560048)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_t_filter_2052317560048_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/orders_high_risk.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/orders_high_risk.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
# Ensure we're working with a LazyFrame for memory efficiency
if var_estimation_2052317647632 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_estimation_2052317647632, pl.DataFrame):
        var_estimation_2052317647632_lazy = var_estimation_2052317647632.lazy()
    elif isinstance(var_estimation_2052317647632, pl.LazyFrame):
        var_estimation_2052317647632_lazy = var_estimation_2052317647632
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_estimation_2052317647632)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_estimation_2052317647632_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/fact_estimation.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/fact_estimation.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
# Ensure we're working with a LazyFrame for memory efficiency
if var_validation_2052317647632 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_validation_2052317647632, pl.DataFrame):
        var_validation_2052317647632_lazy = var_validation_2052317647632.lazy()
    elif isinstance(var_validation_2052317647632, pl.LazyFrame):
        var_validation_2052317647632_lazy = var_validation_2052317647632
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_validation_2052317647632)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_validation_2052317647632_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/fact_validation.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/fact_validation.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
var_runtot_2052316963184 = var_sort_2052316818128.with_columns([
    pl.col("revenue_usd").cum_sum().alias("RunTot_revenue_usd")
])
var_runtot_2052316963184 = normalize_to_supported_dtypes(var_runtot_2052316963184)
# Ensure we're working with a LazyFrame for memory efficiency
if var_sort_2052317067888 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_sort_2052317067888, pl.DataFrame):
        var_sort_2052317067888_lazy = var_sort_2052317067888.lazy()
    elif isinstance(var_sort_2052317067888, pl.LazyFrame):
        var_sort_2052317067888_lazy = var_sort_2052317067888
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_sort_2052317067888)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_sort_2052317067888_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/category_revenue.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/category_revenue.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
# Ensure we're working with a LazyFrame for memory efficiency
if var_sort_2052317137008 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_sort_2052317137008, pl.DataFrame):
        var_sort_2052317137008_lazy = var_sort_2052317137008.lazy()
    elif isinstance(var_sort_2052317137008, pl.LazyFrame):
        var_sort_2052317137008_lazy = var_sort_2052317137008
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_sort_2052317137008)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_sort_2052317137008_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/region_channel_revenue.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/region_channel_revenue.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
# Ensure we're working with a LazyFrame for memory efficiency
if var_sort_2052317343536 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_sort_2052317343536, pl.DataFrame):
        var_sort_2052317343536_lazy = var_sort_2052317343536.lazy()
    elif isinstance(var_sort_2052317343536, pl.LazyFrame):
        var_sort_2052317343536_lazy = var_sort_2052317343536
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_sort_2052317343536)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_sort_2052317343536_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/segment_revenue.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/segment_revenue.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
var_sort_2052317147888 = var_t_filter_2052317149808.sort('revenue_usd', descending=True)
import duckdb
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_sort_2052317237552.collect() if hasattr(var_sort_2052317237552, 'collect') else var_sort_2052317237552
duck.register('df_for_duck', df_for_duck)
df_for_duck = duck.execute('''WITH df_step_0 AS (SELECT *, "revenue_usd" / "lead_time_days" AS "revenue_per_lead_day" FROM df_for_duck) SELECT * FROM df_step_0''').pl()
# Widen DuckDB-native types into Select-supported dtypes
df_for_duck = normalize_to_supported_dtypes(df_for_duck)
# Preserve lazy execution when the incoming value is lazy
var_formula_2052317239472 = df_for_duck.lazy() if hasattr(var_sort_2052317237552, 'collect') else df_for_duck
duck.close()
# Ensure we're working with a LazyFrame for memory efficiency
if var_sort_2052317242992 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_sort_2052317242992, pl.DataFrame):
        var_sort_2052317242992_lazy = var_sort_2052317242992.lazy()
    elif isinstance(var_sort_2052317242992, pl.LazyFrame):
        var_sort_2052317242992_lazy = var_sort_2052317242992
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_sort_2052317242992)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_sort_2052317242992_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/fx_exposure.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/fx_exposure.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
var_groupby_2052317248432 = var_formula_2052317332336.select([
    pl.col('order_id').n_unique().alias('clean_orders'),
    pl.col('net_revenue_usd').sum().alias('net_revenue_usd'),
    pl.col('gross_margin_usd').sum().alias('gross_margin_usd'),
    pl.col('is_returned').sum().alias('returned_orders'),
    pl.col('customer_id').n_unique().alias('distinct_customers'),
    pl.col('product_id').n_unique().alias('distinct_products'),
    pl.col('gross_revenue_usd_raw').sum().alias('gross_revenue_usd_raw'),
    pl.col('is_high_risk').sum().alias('high_risk_orders')
])
var_groupby_2052317248432 = normalize_to_supported_dtypes(var_groupby_2052317248432)
var_select_2052316968304 = var_runtot_2052316963184.select(['order_year_month', 'revenue_usd', 'margin_usd', 'orders', 'RunTot_revenue_usd'])
var_select_2052316968304 = var_select_2052316968304.rename({'RunTot_revenue_usd': 'cumulative_revenue_usd'})
# Ensure we're working with a LazyFrame for memory efficiency
if var_sort_2052317147888 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_sort_2052317147888, pl.DataFrame):
        var_sort_2052317147888_lazy = var_sort_2052317147888.lazy()
    elif isinstance(var_sort_2052317147888, pl.LazyFrame):
        var_sort_2052317147888_lazy = var_sort_2052317147888
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_sort_2052317147888)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_sort_2052317147888_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/top_customers.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/top_customers.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
# Ensure we're working with a LazyFrame for memory efficiency
if var_formula_2052317239472 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_formula_2052317239472, pl.DataFrame):
        var_formula_2052317239472_lazy = var_formula_2052317239472.lazy()
    elif isinstance(var_formula_2052317239472, pl.LazyFrame):
        var_formula_2052317239472_lazy = var_formula_2052317239472
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_formula_2052317239472)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_formula_2052317239472_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/supplier_performance.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/supplier_performance.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
var_select_2052317336176 = var_groupby_2052317248432.select(['clean_orders', 'gross_revenue_usd_raw', 'net_revenue_usd', 'gross_margin_usd', 'returned_orders', 'distinct_customers', 'distinct_products', 'high_risk_orders'])
var_select_2052317336176 = var_select_2052317336176.rename({'gross_revenue_usd_raw': 'gross_revenue_usd'})
# Ensure we're working with a LazyFrame for memory efficiency
if var_select_2052316968304 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_select_2052316968304, pl.DataFrame):
        var_select_2052316968304_lazy = var_select_2052316968304.lazy()
    elif isinstance(var_select_2052316968304, pl.LazyFrame):
        var_select_2052316968304_lazy = var_select_2052316968304
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_select_2052316968304)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_select_2052316968304_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/monthly_revenue.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/monthly_revenue.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
_2052317058288_cols = (var_select_2052316968304.collect_schema().names() if isinstance(var_select_2052316968304, pl.LazyFrame) else var_select_2052316968304.columns)
# Validate data columns
missing = [col for col in ['revenue_usd', 'margin_usd', 'orders'] if col not in _2052317058288_cols]
if missing:
    print(f'Warning: Missing columns will be skipped: {missing}')

# Filter to existing columns
valid_key_cols = [col for col in ['order_year_month'] if col in _2052317058288_cols]
valid_data_cols = [col for col in ['revenue_usd', 'margin_usd', 'orders'] if col in _2052317058288_cols]

# Transpose operation using Polars unpivot
var_transpose_2052317058288 = var_select_2052316968304.unpivot(
    index=valid_key_cols,
    on=valid_data_cols,
    variable_name='Name',
    value_name='Value'
)
# Widen unpivot supertypes into Select-supported dtypes
var_transpose_2052317058288 = normalize_to_supported_dtypes(var_transpose_2052317058288)
import duckdb
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_select_2052317336176.collect() if hasattr(var_select_2052317336176, 'collect') else var_select_2052317336176
duck.register('df_for_duck', df_for_duck)
df_for_duck = duck.execute('''WITH df_step_0 AS (SELECT * REPLACE (ROUND("gross_revenue_usd", 2) AS "gross_revenue_usd") FROM df_for_duck), df_step_1 AS (SELECT *, CASE WHEN "net_revenue_usd" = 0 
THEN NULL 
ELSE ROUND("gross_margin_usd" / "net_revenue_usd", 4) 
END AS "margin_pct" FROM df_step_0) SELECT * FROM df_step_1''').pl()
# Widen DuckDB-native types into Select-supported dtypes
df_for_duck = normalize_to_supported_dtypes(df_for_duck)
# Preserve lazy execution when the incoming value is lazy
var_formula_2052317334256 = df_for_duck.lazy() if hasattr(var_select_2052317336176, 'collect') else df_for_duck
duck.close()
var_select_2052317062448 = var_transpose_2052317058288.select(['order_year_month', 'Name', 'Value'])
var_select_2052317062448 = var_select_2052317062448.rename({'Name': 'metric', 'Value': 'value'})
var_select_2052317340016 = var_formula_2052317334256.select(['clean_orders', 'gross_revenue_usd', 'net_revenue_usd', 'gross_margin_usd', 'margin_pct', 'returned_orders', 'high_risk_orders', 'distinct_customers', 'distinct_products'])
# Ensure we're working with a LazyFrame for memory efficiency
if var_select_2052317062448 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_select_2052317062448, pl.DataFrame):
        var_select_2052317062448_lazy = var_select_2052317062448.lazy()
    elif isinstance(var_select_2052317062448, pl.LazyFrame):
        var_select_2052317062448_lazy = var_select_2052317062448
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_select_2052317062448)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_select_2052317062448_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/monthly_revenue_long.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/monthly_revenue_long.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
_2052317472048_cols = (var_select_2052317340016.collect_schema().names() if isinstance(var_select_2052317340016, pl.LazyFrame) else var_select_2052317340016.columns)
# Validate data columns
missing = [col for col in ['clean_orders', 'gross_revenue_usd', 'net_revenue_usd', 'gross_margin_usd', 'margin_pct', 'returned_orders', 'high_risk_orders', 'distinct_customers', 'distinct_products'] if col not in _2052317472048_cols]
if missing:
    print(f'Warning: Missing columns will be skipped: {missing}')

# Filter to existing columns
valid_key_cols = [col for col in [] if col in _2052317472048_cols]
valid_data_cols = [col for col in ['clean_orders', 'gross_revenue_usd', 'net_revenue_usd', 'gross_margin_usd', 'margin_pct', 'returned_orders', 'high_risk_orders', 'distinct_customers', 'distinct_products'] if col in _2052317472048_cols]

# Transpose operation using Polars unpivot
var_transpose_2052317472048 = var_select_2052317340016.unpivot(
    index=valid_key_cols,
    on=valid_data_cols,
    variable_name='Name',
    value_name='Value'
)
# Widen unpivot supertypes into Select-supported dtypes
var_transpose_2052317472048 = normalize_to_supported_dtypes(var_transpose_2052317472048)
var_select_2052317473968 = var_transpose_2052317472048.select(['Name', 'Value'])
var_select_2052317473968 = var_select_2052317473968.rename({'Name': 'metric', 'Value': 'value'})
# Ensure we're working with a LazyFrame for memory efficiency
if var_select_2052317473968 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_select_2052317473968, pl.DataFrame):
        var_select_2052317473968_lazy = var_select_2052317473968.lazy()
    elif isinstance(var_select_2052317473968, pl.LazyFrame):
        var_select_2052317473968_lazy = var_select_2052317473968
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_select_2052317473968)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_select_2052317473968_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/kpi_summary.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/kpi_summary.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
