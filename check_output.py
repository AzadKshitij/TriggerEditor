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
var_file_input_2072267572080 = pl.scan_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/data/channels.csv', infer_schema=False)

# var_file_input_2072267572080 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_2072267573840 = pl.scan_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/data/orders.csv', infer_schema=False)

# var_file_input_2072267573840 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_2072267575440 = pl.scan_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/data/customers.csv', infer_schema=False)

# var_file_input_2072267575440 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_2072267576880 = pl.scan_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/data/products.csv', infer_schema=False)

# var_file_input_2072267576880 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_2072267578480 = pl.scan_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/data/suppliers.csv', infer_schema=False)

# var_file_input_2072267578480 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_2072267580080 = pl.scan_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/data/fx_rates.csv', infer_schema=False)

# var_file_input_2072267580080 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
var_select_2072267583600 = var_file_input_2072267572080.select(['channel_id', 'channel_name', 'channel_group', 'is_digital'])
var_select_2072267583600 = var_select_2072267583600.with_columns([
    pl.col('channel_id').cast(pl.Int64, strict=False).alias('channel_id')
])
var_select_2072267581680 = var_file_input_2072267573840.select([' Order ID ', 'Customer_Id', 'PRODUCT_ID', 'supplier id', 'Channel ID', 'Currency', 'Order TS', 'Quantity', 'unit_price_local', 'Discount Pct', 'tax_local', 'shipping_local', 'Status', 'Payment Method', 'is_returned'])
var_select_2072267581680 = var_select_2072267581680.with_columns([
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
        pl.col('Order TS').cast(pl.String, strict=False).str.to_datetime(strict=False)
    ]).alias('Order TS'),
    pl.col('Quantity').cast(pl.Int64, strict=False).alias('Quantity'),
    pl.col('unit_price_local').cast(pl.Float64, strict=False).alias('unit_price_local'),
    pl.col('Discount Pct').cast(pl.Float64, strict=False).alias('Discount Pct'),
    pl.col('tax_local').cast(pl.Float64, strict=False).alias('tax_local'),
    pl.col('shipping_local').cast(pl.Float64, strict=False).alias('shipping_local')
])
var_select_2072267585520 = var_file_input_2072267575440.select(['customer_id', 'email', 'full_name', 'signup_date', 'country', 'region', 'currency', 'segment', 'age_band', 'loyalty_tier'])
var_select_2072267585520 = var_select_2072267585520.with_columns([
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
        pl.col('signup_date').cast(pl.String, strict=False).str.to_date(strict=False)
    ]).alias('signup_date')
])
var_select_2072267585520 = var_select_2072267585520.rename({'email': 'customer_email', 'full_name': 'customer_name', 'country': 'customer_country', 'currency': 'customer_currency', 'age_band': 'customer_age_band'})
var_select_2072267587440 = var_file_input_2072267576880.select(['product_id', 'sku', 'product_name', 'category', 'subcategory', 'brand', 'unit_price', 'unit_cost', 'launch_date'])
var_select_2072267587440 = var_select_2072267587440.with_columns([
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
        pl.col('launch_date').cast(pl.String, strict=False).str.to_date(strict=False)
    ]).alias('launch_date')
])
var_select_2072267622192 = var_file_input_2072267578480.select(['supplier_id', 'supplier_name', 'country', 'lead_time_days', 'reliability_score'])
var_select_2072267622192 = var_select_2072267622192.with_columns([
    pl.col('supplier_id').cast(pl.Int64, strict=False).alias('supplier_id'),
    pl.col('lead_time_days').cast(pl.Int64, strict=False).alias('lead_time_days'),
    pl.col('reliability_score').cast(pl.Float64, strict=False).alias('reliability_score')
])
var_select_2072267624112 = var_file_input_2072267580080.select(['currency', 'currency_name', 'usd_rate'])
var_select_2072267624112 = var_select_2072267624112.with_columns([
    pl.col('usd_rate').cast(pl.Float64, strict=False).alias('usd_rate')
])
import duckdb
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_select_2072267583600.collect() if hasattr(var_select_2072267583600, 'collect') else var_select_2072267583600
duck.register('df_for_duck', df_for_duck)
df_for_duck = duck.sql('''WITH df_step_0 AS (SELECT *, 'channels' AS "source_table" FROM df_for_duck) SELECT * FROM df_step_0''').pl()
# Widen DuckDB-native types into Select-supported dtypes
df_for_duck = normalize_to_supported_dtypes(df_for_duck)
# Preserve lazy execution when the incoming value is lazy
var_formula_2070956498992 = df_for_duck.lazy() if hasattr(var_select_2072267583600, 'collect') else df_for_duck
duck.close()
import polars as pl
# Normalize column names (11 renamed)
var_normalize_columns_2072267636592 = var_select_2072267581680.rename({' Order ID ': 'order_id', 'Customer_Id': 'customer_id', 'PRODUCT_ID': 'product_id', 'supplier id': 'supplier_id', 'Channel ID': 'channel_id', 'Currency': 'currency', 'Order TS': 'order_ts', 'Quantity': 'quantity', 'Discount Pct': 'discount_pct', 'Status': 'status', 'Payment Method': 'payment_method'})
import duckdb
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_select_2072267585520.collect() if hasattr(var_select_2072267585520, 'collect') else var_select_2072267585520
duck.register('df_for_duck', df_for_duck)
df_for_duck = duck.sql('''WITH df_step_0 AS (SELECT *, 'customers' AS "source_table" FROM df_for_duck) SELECT * FROM df_step_0''').pl()
# Widen DuckDB-native types into Select-supported dtypes
df_for_duck = normalize_to_supported_dtypes(df_for_duck)
# Preserve lazy execution when the incoming value is lazy
var_formula_2070956493232 = df_for_duck.lazy() if hasattr(var_select_2072267585520, 'collect') else df_for_duck
duck.close()
import duckdb
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_select_2072267587440.collect() if hasattr(var_select_2072267587440, 'collect') else var_select_2072267587440
duck.register('df_for_duck', df_for_duck)
df_for_duck = duck.sql('''WITH df_step_0 AS (SELECT *, 'products' AS "source_table" FROM df_for_duck) SELECT * FROM df_step_0''').pl()
# Widen DuckDB-native types into Select-supported dtypes
df_for_duck = normalize_to_supported_dtypes(df_for_duck)
# Preserve lazy execution when the incoming value is lazy
var_formula_2070956495152 = df_for_duck.lazy() if hasattr(var_select_2072267587440, 'collect') else df_for_duck
duck.close()
import duckdb
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_select_2072267622192.collect() if hasattr(var_select_2072267622192, 'collect') else var_select_2072267622192
duck.register('df_for_duck', df_for_duck)
df_for_duck = duck.sql('''WITH df_step_0 AS (SELECT *, 'suppliers' AS "source_table" FROM df_for_duck) SELECT * FROM df_step_0''').pl()
# Widen DuckDB-native types into Select-supported dtypes
df_for_duck = normalize_to_supported_dtypes(df_for_duck)
# Preserve lazy execution when the incoming value is lazy
var_formula_2070956497072 = df_for_duck.lazy() if hasattr(var_select_2072267622192, 'collect') else df_for_duck
duck.close()
import duckdb
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_select_2072267624112.collect() if hasattr(var_select_2072267624112, 'collect') else var_select_2072267624112
duck.register('df_for_duck', df_for_duck)
df_for_duck = duck.sql('''WITH df_step_0 AS (SELECT * REPLACE (LOWER("currency") AS "currency") FROM df_for_duck) SELECT * FROM df_step_0''').pl()
# Widen DuckDB-native types into Select-supported dtypes
df_for_duck = normalize_to_supported_dtypes(df_for_duck)
# Preserve lazy execution when the incoming value is lazy
var_formula_2072268034032 = df_for_duck.lazy() if hasattr(var_select_2072267624112, 'collect') else df_for_duck
duck.close()
from trigger_designer.core.utils.cleansing_util import DataCleansing, NullStrategy
import polars as pl
# Convert LazyFrame to DataFrame if needed
_cleansing_input = var_normalize_columns_2072267636592.collect() if hasattr(var_normalize_columns_2072267636592, 'collect') else var_normalize_columns_2072267636592
cleaner = DataCleansing(_cleansing_input)
cleaner.strip_whitespace(remove_all=False, normalize_spaces=True, fields=['order_id', 'customer_id', 'product_id', 'supplier_id', 'channel_id', 'currency', 'order_ts', 'quantity', 'unit_price_local', 'discount_pct', 'tax_local', 'shipping_local', 'status', 'payment_method', 'is_returned'])
var_cleansing_2072267626032 = cleaner.get_result()
var_cleansing_2072267626032 = var_cleansing_2072267626032.lazy() if hasattr(var_normalize_columns_2072267636592, 'collect') else var_cleansing_2072267626032
import polars as pl
_union_inputs_2070956502832 = [var_formula_2070956495152, var_formula_2070956493232]
var_union_2070956502832 = pl.concat([(f.lazy() if isinstance(f, pl.DataFrame) else f) for f in _union_inputs_2070956502832], how='diagonal_relaxed')
del _union_inputs_2070956502832
import duckdb
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_formula_2072268034032.collect() if hasattr(var_formula_2072268034032, 'collect') else var_formula_2072268034032
duck.register('df_for_duck', df_for_duck)
df_for_duck = duck.sql('''WITH df_step_0 AS (SELECT *, 'fx_rates' AS "source_table" FROM df_for_duck) SELECT * FROM df_step_0''').pl()
# Widen DuckDB-native types into Select-supported dtypes
df_for_duck = normalize_to_supported_dtypes(df_for_duck)
# Preserve lazy execution when the incoming value is lazy
var_formula_2070956500912 = df_for_duck.lazy() if hasattr(var_formula_2072268034032, 'collect') else df_for_duck
duck.close()
from trigger_designer.core.utils.cleansing_util import DataCleansing, NullStrategy
import polars as pl
# Convert LazyFrame to DataFrame if needed
_cleansing_input = var_cleansing_2072267626032.collect() if hasattr(var_cleansing_2072267626032, 'collect') else var_cleansing_2072267626032
cleaner = DataCleansing(_cleansing_input)
cleaner.strip_whitespace(remove_all=False, normalize_spaces=True, fields=['order_id', 'currency', 'status', 'payment_method'])
cleaner.modify_case('lower', fields=['order_id', 'currency', 'status', 'payment_method'])
var_cleansing_2070956720208 = cleaner.get_result()
var_cleansing_2070956720208 = var_cleansing_2070956720208.lazy() if hasattr(var_cleansing_2072267626032, 'collect') else var_cleansing_2070956720208
import polars as pl
_union_inputs_2070956504912 = [var_union_2070956502832, var_formula_2070956497072]
var_union_2070956504912 = pl.concat([(f.lazy() if isinstance(f, pl.DataFrame) else f) for f in _union_inputs_2070956504912], how='diagonal_relaxed')
del _union_inputs_2070956504912
from trigger_designer.core.utils.cleansing_util import DataCleansing, NullStrategy
import polars as pl
# Convert LazyFrame to DataFrame if needed
_cleansing_input = var_cleansing_2070956720208.collect() if hasattr(var_cleansing_2070956720208, 'collect') else var_cleansing_2070956720208
cleaner = DataCleansing(_cleansing_input)
cleaner.remove_rows_with_nulls(fields=['customer_id', 'product_id'])
cleaner.modify_case('lower', fields=['customer_id', 'product_id'])
var_cleansing_2072267627952 = cleaner.get_result()
var_cleansing_2072267627952 = var_cleansing_2072267627952.lazy() if hasattr(var_cleansing_2070956720208, 'collect') else var_cleansing_2072267627952
import polars as pl
_union_inputs_2070956506992 = [var_formula_2070956498992, var_union_2070956504912]
var_union_2070956506992 = pl.concat([(f.lazy() if isinstance(f, pl.DataFrame) else f) for f in _union_inputs_2070956506992], how='diagonal_relaxed')
del _union_inputs_2070956506992
# Filter data into true and false results
var_t_filter_2072267629872 = var_cleansing_2072267627952.filter(pl.col('quantity').is_between(1.0, 500.0, closed='both'))
var_f_filter_2072267629872 = var_cleansing_2072267627952.filter(~(pl.col('quantity').is_between(1.0, 500.0, closed='both')))
import polars as pl
_union_inputs_2070956853200 = [var_union_2070956506992, var_formula_2070956500912]
var_union_2070956853200 = pl.concat([(f.lazy() if isinstance(f, pl.DataFrame) else f) for f in _union_inputs_2070956853200], how='diagonal_relaxed')
del _union_inputs_2070956853200
import duckdb
import polars as pl
# Filter rows with a SQL WHERE clause (no new columns)
df_for_duck = var_t_filter_2072267629872.collect() if hasattr(var_t_filter_2072267629872, 'collect') else var_t_filter_2072267629872
duck = duckdb.connect(':memory:')
duck.register('df_filter', df_for_duck)
var_t_filter_2072267632112 = duck.sql('SELECT * FROM df_filter WHERE "unit_price_local" > 0 and \n"unit_price_local" <= 5000').pl()
var_f_filter_2072267632112 = duck.sql('SELECT * FROM df_filter WHERE NOT ("unit_price_local" > 0 and \n"unit_price_local" <= 5000)').pl()
# Preserve lazy execution when the incoming value is lazy
var_t_filter_2072267632112 = var_t_filter_2072267632112.lazy() if hasattr(var_t_filter_2072267629872, 'collect') else var_t_filter_2072267632112
var_f_filter_2072267632112 = var_f_filter_2072267632112.lazy() if hasattr(var_t_filter_2072267629872, 'collect') else var_f_filter_2072267632112
duck.close()
# Ensure we're working with a LazyFrame for memory efficiency
if var_f_filter_2072267629872 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_f_filter_2072267629872, pl.DataFrame):
        var_f_filter_2072267629872_lazy = var_f_filter_2072267629872.lazy()
    elif isinstance(var_f_filter_2072267629872, pl.LazyFrame):
        var_f_filter_2072267629872_lazy = var_f_filter_2072267629872
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_f_filter_2072267629872)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_f_filter_2072267629872_lazy.sink_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/rejected_quantity.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/rejected_quantity.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
# Ensure we're working with a LazyFrame for memory efficiency
if var_union_2070956853200 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_union_2070956853200, pl.DataFrame):
        var_union_2070956853200_lazy = var_union_2070956853200.lazy()
    elif isinstance(var_union_2070956853200, pl.LazyFrame):
        var_union_2070956853200_lazy = var_union_2070956853200
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_union_2070956853200)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_union_2070956853200_lazy.sink_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/reference_data_union.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/reference_data_union.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
import duckdb
import polars as pl
# Filter rows with a SQL WHERE clause (no new columns)
df_for_duck = var_t_filter_2072267632112.collect() if hasattr(var_t_filter_2072267632112, 'collect') else var_t_filter_2072267632112
duck = duckdb.connect(':memory:')
duck.register('df_filter', df_for_duck)
var_t_filter_2072267634352 = duck.sql('SELECT * FROM df_filter WHERE YEAR("order_ts") <= 2025').pl()
var_f_filter_2072267634352 = duck.sql('SELECT * FROM df_filter WHERE NOT (YEAR("order_ts") <= 2025)').pl()
# Preserve lazy execution when the incoming value is lazy
var_t_filter_2072267634352 = var_t_filter_2072267634352.lazy() if hasattr(var_t_filter_2072267632112, 'collect') else var_t_filter_2072267634352
var_f_filter_2072267634352 = var_f_filter_2072267634352.lazy() if hasattr(var_t_filter_2072267632112, 'collect') else var_f_filter_2072267634352
duck.close()
# Ensure we're working with a LazyFrame for memory efficiency
if var_f_filter_2072267632112 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_f_filter_2072267632112, pl.DataFrame):
        var_f_filter_2072267632112_lazy = var_f_filter_2072267632112.lazy()
    elif isinstance(var_f_filter_2072267632112, pl.LazyFrame):
        var_f_filter_2072267632112_lazy = var_f_filter_2072267632112
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_f_filter_2072267632112)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_f_filter_2072267632112_lazy.sink_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/rejected_price_outliers.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/rejected_price_outliers.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
import polars as pl
# Split into unique and duplicate records based on: order_id
var_unique_2072268031792 = var_t_filter_2072267634352.unique(subset=["order_id"], maintain_order=True)
var_duplicate_2072268031792 = var_t_filter_2072267634352.filter(pl.struct(["order_id"]).is_duplicated())
# Ensure we're working with a LazyFrame for memory efficiency
if var_f_filter_2072267634352 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_f_filter_2072267634352, pl.DataFrame):
        var_f_filter_2072267634352_lazy = var_f_filter_2072267634352.lazy()
    elif isinstance(var_f_filter_2072267634352, pl.LazyFrame):
        var_f_filter_2072267634352_lazy = var_f_filter_2072267634352
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_f_filter_2072267634352)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_f_filter_2072267634352_lazy.sink_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/rejected_future_dates.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/rejected_future_dates.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
var_select_2070957016560 = var_unique_2072268031792.select(['order_id', 'customer_id', 'product_id', 'supplier_id', 'channel_id', 'currency', 'order_ts', 'quantity', 'unit_price_local', 'discount_pct', 'tax_local', 'shipping_local', 'status', 'payment_method', 'is_returned'])
# Ensure we're working with a LazyFrame for memory efficiency
if var_unique_2072268031792 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_unique_2072268031792, pl.DataFrame):
        var_unique_2072268031792_lazy = var_unique_2072268031792.lazy()
    elif isinstance(var_unique_2072268031792, pl.LazyFrame):
        var_unique_2072268031792_lazy = var_unique_2072268031792
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_unique_2072268031792)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_unique_2072268031792_lazy.sink_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/04 dropped null key rows.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/04 dropped null key rows.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
# Ensure we're working with a LazyFrame for memory efficiency
if var_duplicate_2072268031792 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_duplicate_2072268031792, pl.DataFrame):
        var_duplicate_2072268031792_lazy = var_duplicate_2072268031792.lazy()
    elif isinstance(var_duplicate_2072268031792, pl.LazyFrame):
        var_duplicate_2072268031792_lazy = var_duplicate_2072268031792
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_duplicate_2072268031792)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_duplicate_2072268031792_lazy.sink_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/duplicate_orders.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/duplicate_orders.csv using LazyFrame')
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

_left_input = _ensure_lazyframe(var_select_2070957016560)
_right_input = _ensure_lazyframe(var_select_2072267585520)

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
var_join_2072268035952 = _join_result.filter(
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
var_l_join_2072268035952 = _join_result.filter(
    pl.col('__right_present').is_null()
).select(_left_cols)

# Extract right-only data efficiently
_right_cols = ['customer_id', 'customer_email', 'customer_name', 'signup_date', 'customer_country', 'region', 'customer_currency', 'segment', 'customer_age_band', 'loyalty_tier']
var_r_join_2072268035952 = _join_result.filter(
    pl.col('__left_present').is_null()
).select(_right_cols)

# Clean up temporary variables
del _left_input, _right_input, _left_tagged, _right_tagged, _join_result, _left_cols, _right_cols
# Ensure we're working with a LazyFrame for memory efficiency
if var_l_join_2072268035952 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_l_join_2072268035952, pl.DataFrame):
        var_l_join_2072268035952_lazy = var_l_join_2072268035952.lazy()
    elif isinstance(var_l_join_2072268035952, pl.LazyFrame):
        var_l_join_2072268035952_lazy = var_l_join_2072268035952
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_l_join_2072268035952)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_l_join_2072268035952_lazy.sink_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/orphan_customers.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/orphan_customers.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
import polars as pl
_union_inputs_2072268268048 = [var_join_2072268035952, var_l_join_2072268035952]
var_union_2072268268048 = pl.concat([(f.lazy() if isinstance(f, pl.DataFrame) else f) for f in _union_inputs_2072268268048], how='diagonal_relaxed')
del _union_inputs_2072268268048
# Polars LazyFrame Join Operation
import polars as pl

def _ensure_lazyframe(data):
    if isinstance(data, pl.DataFrame):
        return data.lazy()
    if isinstance(data, pl.LazyFrame):
        return data
    raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(data)}')

_left_input = _ensure_lazyframe(var_union_2072268268048)
_right_input = _ensure_lazyframe(var_select_2072267587440)

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
var_join_2072268038992 = _join_result.filter(
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
var_l_join_2072268038992 = _join_result.filter(
    pl.col('__right_present').is_null()
).select(_left_cols)

# Extract right-only data efficiently
_right_cols = ['product_id', 'sku', 'product_name', 'category', 'subcategory', 'brand', 'unit_price', 'unit_cost', 'launch_date']
var_r_join_2072268038992 = _join_result.filter(
    pl.col('__left_present').is_null()
).select(_right_cols)

# Clean up temporary variables
del _left_input, _right_input, _left_tagged, _right_tagged, _join_result, _left_cols, _right_cols
# Ensure we're working with a LazyFrame for memory efficiency
if var_union_2072268268048 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_union_2072268268048, pl.DataFrame):
        var_union_2072268268048_lazy = var_union_2072268268048.lazy()
    elif isinstance(var_union_2072268268048, pl.LazyFrame):
        var_union_2072268268048_lazy = var_union_2072268268048
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_union_2072268268048)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_union_2072268268048_lazy.sink_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/01 enriched customer_id.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/01 enriched customer_id.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
# Ensure we're working with a LazyFrame for memory efficiency
if var_l_join_2072268038992 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_l_join_2072268038992, pl.DataFrame):
        var_l_join_2072268038992_lazy = var_l_join_2072268038992.lazy()
    elif isinstance(var_l_join_2072268038992, pl.LazyFrame):
        var_l_join_2072268038992_lazy = var_l_join_2072268038992
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_l_join_2072268038992)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_l_join_2072268038992_lazy.sink_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/orphan_products.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/orphan_products.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
import polars as pl
_union_inputs_2072268270128 = [var_join_2072268038992, var_l_join_2072268038992]
var_union_2072268270128 = pl.concat([(f.lazy() if isinstance(f, pl.DataFrame) else f) for f in _union_inputs_2072268270128], how='diagonal_relaxed')
del _union_inputs_2072268270128
# Polars LazyFrame Join Operation
import polars as pl

def _ensure_lazyframe(data):
    if isinstance(data, pl.DataFrame):
        return data.lazy()
    if isinstance(data, pl.LazyFrame):
        return data
    raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(data)}')

_left_input = _ensure_lazyframe(var_union_2072268270128)
_right_input = _ensure_lazyframe(var_select_2072267622192)

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
var_join_2072268042032 = _join_result.filter(
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
var_l_join_2072268042032 = _join_result.filter(
    pl.col('__right_present').is_null()
).select(_left_cols)

# Extract right-only data efficiently
_right_cols = ['supplier_id', 'supplier_name', 'country', 'lead_time_days', 'reliability_score']
var_r_join_2072268042032 = _join_result.filter(
    pl.col('__left_present').is_null()
).select(_right_cols)

# Clean up temporary variables
del _left_input, _right_input, _left_tagged, _right_tagged, _join_result, _left_cols, _right_cols
# Ensure we're working with a LazyFrame for memory efficiency
if var_union_2072268270128 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_union_2072268270128, pl.DataFrame):
        var_union_2072268270128_lazy = var_union_2072268270128.lazy()
    elif isinstance(var_union_2072268270128, pl.LazyFrame):
        var_union_2072268270128_lazy = var_union_2072268270128
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_union_2072268270128)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_union_2072268270128_lazy.sink_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/02 enriched product_id.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/02 enriched product_id.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
import polars as pl
_union_inputs_2072268272208 = [var_join_2072268042032, var_l_join_2072268042032]
var_union_2072268272208 = pl.concat([(f.lazy() if isinstance(f, pl.DataFrame) else f) for f in _union_inputs_2072268272208], how='diagonal_relaxed')
del _union_inputs_2072268272208
# Polars LazyFrame Join Operation
import polars as pl

def _ensure_lazyframe(data):
    if isinstance(data, pl.DataFrame):
        return data.lazy()
    if isinstance(data, pl.LazyFrame):
        return data
    raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(data)}')

_left_input = _ensure_lazyframe(var_union_2072268272208)
_right_input = _ensure_lazyframe(var_select_2072267583600)

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
var_join_2072268045072 = _join_result.filter(
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
var_l_join_2072268045072 = _join_result.filter(
    pl.col('__right_present').is_null()
).select(_left_cols)

# Extract right-only data efficiently
_right_cols = ['channel_id', 'channel_name', 'channel_group', 'is_digital']
var_r_join_2072268045072 = _join_result.filter(
    pl.col('__left_present').is_null()
).select(_right_cols)

# Clean up temporary variables
del _left_input, _right_input, _left_tagged, _right_tagged, _join_result, _left_cols, _right_cols
# Ensure we're working with a LazyFrame for memory efficiency
if var_union_2072268272208 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_union_2072268272208, pl.DataFrame):
        var_union_2072268272208_lazy = var_union_2072268272208.lazy()
    elif isinstance(var_union_2072268272208, pl.LazyFrame):
        var_union_2072268272208_lazy = var_union_2072268272208
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_union_2072268272208)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_union_2072268272208_lazy.sink_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/03 enriched supplier_id.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/03 enriched supplier_id.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
import polars as pl
_union_inputs_2072268274288 = [var_join_2072268045072, var_l_join_2072268045072]
var_union_2072268274288 = pl.concat([(f.lazy() if isinstance(f, pl.DataFrame) else f) for f in _union_inputs_2072268274288], how='diagonal_relaxed')
del _union_inputs_2072268274288
# Polars LazyFrame Join Operation
import polars as pl

def _ensure_lazyframe(data):
    if isinstance(data, pl.DataFrame):
        return data.lazy()
    if isinstance(data, pl.LazyFrame):
        return data
    raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(data)}')

_left_input = _ensure_lazyframe(var_union_2072268274288)
_right_input = _ensure_lazyframe(var_formula_2072268034032)

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
var_join_2072268261168 = _join_result.filter(
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
var_l_join_2072268261168 = _join_result.filter(
    pl.col('__right_present').is_null()
).select(_left_cols)

# Extract right-only data efficiently
_right_cols = ['currency', 'currency_name', 'usd_rate']
var_r_join_2072268261168 = _join_result.filter(
    pl.col('__left_present').is_null()
).select(_right_cols)

# Clean up temporary variables
del _left_input, _right_input, _left_tagged, _right_tagged, _join_result, _left_cols, _right_cols
# Ensure we're working with a LazyFrame for memory efficiency
if var_union_2072268274288 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_union_2072268274288, pl.DataFrame):
        var_union_2072268274288_lazy = var_union_2072268274288.lazy()
    elif isinstance(var_union_2072268274288, pl.LazyFrame):
        var_union_2072268274288_lazy = var_union_2072268274288
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_union_2072268274288)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_union_2072268274288_lazy.sink_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/04 enriched channel_id.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/04 enriched channel_id.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
import polars as pl
_union_inputs_2072268128976 = [var_join_2072268261168, var_l_join_2072268261168]
var_union_2072268128976 = pl.concat([(f.lazy() if isinstance(f, pl.DataFrame) else f) for f in _union_inputs_2072268128976], how='diagonal_relaxed')
del _union_inputs_2072268128976
import duckdb
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_union_2072268128976.collect() if hasattr(var_union_2072268128976, 'collect') else var_union_2072268128976
duck.register('df_for_duck', df_for_duck)
df_for_duck = duck.sql('''WITH df_step_0 AS (SELECT *, "quantity" * "unit_price_local" AS "g" FROM df_for_duck), df_step_1 AS (SELECT *, ROUND("g", 2) AS "gross_local" FROM df_step_0), df_step_2 AS (SELECT *, ROUND("gross_local" * "discount_pct", 2) AS "discount_local" FROM df_step_1), df_step_3 AS (SELECT *, ROUND("gross_local" - "discount_local", 2) AS "net_local" FROM df_step_2), df_step_4 AS (SELECT *, ROUND("net_local" + "tax_local" + "shipping_local", 2) AS "total_local" FROM df_step_3) SELECT * FROM df_step_4''').pl()
# Widen DuckDB-native types into Select-supported dtypes
df_for_duck = normalize_to_supported_dtypes(df_for_duck)
# Preserve lazy execution when the incoming value is lazy
var_formula_2072268264208 = df_for_duck.lazy() if hasattr(var_union_2072268128976, 'collect') else df_for_duck
duck.close()
# Ensure we're working with a LazyFrame for memory efficiency
if var_union_2072268128976 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_union_2072268128976, pl.DataFrame):
        var_union_2072268128976_lazy = var_union_2072268128976.lazy()
    elif isinstance(var_union_2072268128976, pl.LazyFrame):
        var_union_2072268128976_lazy = var_union_2072268128976
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_union_2072268128976)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_union_2072268128976_lazy.sink_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/05 enriched currency.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/05 enriched currency.csv using LazyFrame')
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
df_for_duck = var_formula_2072268264208.collect() if hasattr(var_formula_2072268264208, 'collect') else var_formula_2072268264208
duck.register('df_for_duck', df_for_duck)
df_for_duck = duck.sql('''WITH df_step_0 AS (SELECT *, ROUND("unit_price_local" * "usd_rate", 2) AS "unit_price_usd" FROM df_for_duck), df_step_1 AS (SELECT *, ROUND("net_local" * "usd_rate", 2) AS "net_revenue_usd" FROM df_step_0), df_step_2 AS (SELECT *, ROUND("tax_local" * "usd_rate", 2) AS "tax_usd" FROM df_step_1), df_step_3 AS (SELECT *, ROUND("shipping_local" * "usd_rate", 2) AS "shipping_usd" FROM df_step_2), df_step_4 AS (SELECT *, ROUND("total_local" * "usd_rate", 2) AS "total_usd" FROM df_step_3) SELECT * FROM df_step_4''').pl()
# Widen DuckDB-native types into Select-supported dtypes
df_for_duck = normalize_to_supported_dtypes(df_for_duck)
# Preserve lazy execution when the incoming value is lazy
var_formula_2072268266128 = df_for_duck.lazy() if hasattr(var_formula_2072268264208, 'collect') else df_for_duck
duck.close()
import duckdb
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_formula_2072268266128.collect() if hasattr(var_formula_2072268266128, 'collect') else var_formula_2072268266128
duck.register('df_for_duck', df_for_duck)
df_for_duck = duck.sql('''WITH df_step_0 AS (SELECT *, ROUND("quantity" * "unit_cost", 2) AS "cogs_usd" FROM df_for_duck), df_step_1 AS (SELECT *, ROUND("net_revenue_usd" - "cogs_usd", 2) AS "gross_margin_usd" FROM df_step_0), df_step_2 AS (SELECT *, ROUND(CASE
    WHEN "net_revenue_usd" IS NULL OR "net_revenue_usd" = 0 THEN NULL
    ELSE "gross_margin_usd" / "net_revenue_usd"
END, 4) AS "margin_pct" FROM df_step_1) SELECT * FROM df_step_2''').pl()
# Widen DuckDB-native types into Select-supported dtypes
df_for_duck = normalize_to_supported_dtypes(df_for_duck)
# Preserve lazy execution when the incoming value is lazy
var_formula_2072268131056 = df_for_duck.lazy() if hasattr(var_formula_2072268266128, 'collect') else df_for_duck
duck.close()
import duckdb
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_formula_2072268131056.collect() if hasattr(var_formula_2072268131056, 'collect') else var_formula_2072268131056
duck.register('df_for_duck', df_for_duck)
df_for_duck = duck.sql('''WITH df_step_0 AS (SELECT *, YEAR("order_ts") AS "order_year" FROM df_for_duck), df_step_1 AS (SELECT *, MONTH("order_ts") AS "order_month" FROM df_step_0), df_step_2 AS (SELECT *, STRFTIME("order_ts", '%Y-%m') AS "order_year_month" FROM df_step_1), df_step_3 AS (SELECT *, "quantity" >= 6 AS "is_bulk" FROM df_step_2), df_step_4 AS (SELECT *, CASE
    WHEN "net_revenue_usd" IS NULL THEN NULL
    WHEN "net_revenue_usd" <= 250  THEN 'Low'
    WHEN "net_revenue_usd" <= 1000 THEN 'Medium'
    ELSE 'High'
END
 AS "value_band" FROM df_step_3) SELECT * FROM df_step_4''').pl()
# Widen DuckDB-native types into Select-supported dtypes
df_for_duck = normalize_to_supported_dtypes(df_for_duck)
# Preserve lazy execution when the incoming value is lazy
var_formula_2072268132976 = df_for_duck.lazy() if hasattr(var_formula_2072268131056, 'collect') else df_for_duck
duck.close()
import duckdb
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_formula_2072268132976.collect() if hasattr(var_formula_2072268132976, 'collect') else var_formula_2072268132976
duck.register('df_for_duck', df_for_duck)
df_for_duck = duck.sql('''WITH df_step_0 AS (SELECT * REPLACE (CASE WHEN LOWER("is_returned") = 'true' THEN true ELSE false END AS "is_returned") FROM df_for_duck), df_step_1 AS (SELECT *, (CASE WHEN "is_returned" THEN 2 ELSE 0 END)
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
var_formula_2072268134896 = df_for_duck.lazy() if hasattr(var_formula_2072268132976, 'collect') else df_for_duck
duck.close()
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
var_groupby_2072268138736 = var_formula_2072268134896.group_by(['order_year_month']).agg([
    pl.col('net_revenue_usd').sum().alias('revenue_usd'),
    pl.col('gross_margin_usd').sum().alias('margin_usd'),
    pl.col('order_id').n_unique().alias('orders')
])
var_groupby_2072268138736 = normalize_to_supported_dtypes(var_groupby_2072268138736)
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
var_groupby_2072268118832 = var_formula_2072268134896.group_by(['category']).agg([
    pl.col('net_revenue_usd').sum().alias('revenue_usd'),
    pl.col('gross_margin_usd').sum().alias('margin_usd'),
    pl.col('order_id').n_unique().alias('orders')
])
var_groupby_2072268118832 = normalize_to_supported_dtypes(var_groupby_2072268118832)
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
var_groupby_2072268127792 = var_formula_2072268134896.group_by(['region', 'channel_group']).agg([
    pl.col('net_revenue_usd').sum().alias('revenue_usd'),
    pl.col('gross_margin_usd').sum().alias('margin_usd'),
    pl.col('order_id').n_unique().alias('orders')
])
var_groupby_2072268127792 = normalize_to_supported_dtypes(var_groupby_2072268127792)
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
var_groupby_2072268391920 = var_formula_2072268134896.group_by(['segment', 'risk_band']).agg([
    pl.col('net_revenue_usd').sum().alias('revenue_usd'),
    pl.col('gross_margin_usd').sum().alias('margin_usd'),
    pl.col('order_id').n_unique().alias('orders')
])
var_groupby_2072268391920 = normalize_to_supported_dtypes(var_groupby_2072268391920)
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
var_groupby_2072268393840 = var_formula_2072268134896.group_by(['customer_id']).agg([
    pl.col('net_revenue_usd').sum().alias('revenue_usd'),
    pl.col('order_id').n_unique().alias('orders')
])
var_groupby_2072268393840 = normalize_to_supported_dtypes(var_groupby_2072268393840)
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
var_groupby_2072268403120 = var_formula_2072268134896.group_by(['supplier_id', 'supplier_name', 'country']).agg([
    pl.col('net_revenue_usd').sum().alias('revenue_usd'),
    pl.col('order_id').n_unique().alias('orders'),
    pl.col('lead_time_days').first().alias('lead_time_days'),
    pl.col('reliability_score').first().alias('reliability_score')
])
var_groupby_2072268403120 = normalize_to_supported_dtypes(var_groupby_2072268403120)
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
var_groupby_2072268461616 = var_formula_2072268134896.group_by(['currency']).agg([
    pl.col('net_revenue_usd').sum().alias('revenue_usd'),
    pl.col('order_id').n_unique().alias('orders'),
    pl.col('usd_rate').first().alias('usd_rate')
])
var_groupby_2072268461616 = normalize_to_supported_dtypes(var_groupby_2072268461616)
var_select_2070956726128 = var_formula_2072268134896.select(['brand', 'category', 'channel_group', 'channel_id', 'channel_name', 'country', 'currency', 'customer_age_band', 'customer_country', 'customer_currency', 'customer_email', 'customer_id', 'discount_pct', 'is_digital', 'is_returned', 'launch_date', 'lead_time_days', 'loyalty_tier', 'order_id', 'order_ts', 'payment_method', 'product_id', 'product_name', 'quantity', 'region', 'reliability_score', 'segment', 'shipping_local', 'signup_date', 'sku', 'status', 'subcategory', 'supplier_id', 'supplier_name', 'tax_local', 'unit_cost', 'unit_price', 'unit_price_local', 'currency_name', 'usd_rate', 'g', 'gross_local', 'discount_local', 'net_local', 'total_local', 'unit_price_usd', 'net_revenue_usd', 'tax_usd', 'shipping_usd', 'total_usd', 'cogs_usd', 'gross_margin_usd', 'margin_pct', 'order_year', 'order_month', 'order_year_month', 'is_bulk', 'value_band', 'risk_score', 'risk_band', 'customer_name', 'status_clean'])
var_select_2070956726128 = var_select_2070956726128.with_columns([
    pl.when(pl.col('is_digital').cast(pl.String, strict=False).str.to_lowercase().str.strip_chars().is_in(('true', '1', 'yes', 'y', 't', 'on'))).then(True)
    .when(pl.col('is_digital').cast(pl.String, strict=False).str.to_lowercase().str.strip_chars().is_in(('false', '0', 'no', 'n', 'f', 'off'))).then(False)
    .when(pl.col('is_digital').cast(pl.Float64, strict=False).is_not_null() & (pl.col('is_digital').cast(pl.Float64, strict=False) != 0.0)).then(True)
    .when(pl.col('is_digital').cast(pl.Float64, strict=False).is_not_null()).then(False)
    .otherwise(None)
    .alias('is_digital'),
    pl.col('order_ts').cast(pl.String, strict=False).alias('order_ts')
])
var_select_2070956968048 = var_formula_2072268134896.select(['order_id', 'order_ts', 'order_year', 'order_month', 'order_year_month', 'customer_id', 'product_id', 'supplier_id', 'channel_id', 'channel_name', 'channel_group', 'category', 'subcategory', 'brand', 'customer_country', 'region', 'segment', 'loyalty_tier', 'currency', 'usd_rate', 'status', 'status_clean', 'quantity', 'unit_price_local', 'discount_pct', 'net_local', 'total_local', 'net_revenue_usd', 'cogs_usd', 'gross_margin_usd', 'margin_pct', 'value_band', 'risk_score', 'risk_band', 'is_returned', 'is_bulk', 'country', 'customer_age_band', 'customer_currency', 'customer_email', 'is_digital', 'launch_date', 'lead_time_days', 'payment_method', 'product_name', 'reliability_score', 'shipping_local', 'signup_date', 'sku', 'supplier_name', 'tax_local', 'unit_cost', 'unit_price', 'currency_name', 'customer_name', 'g', 'gross_local', 'discount_local', 'unit_price_usd', 'tax_usd', 'shipping_usd', 'total_usd'])
# Filter data into true and false results
var_t_filter_2070956971568 = var_formula_2072268134896.filter(pl.col('segment') == 'Enterprise')
var_f_filter_2070956971568 = var_formula_2072268134896.filter(~(pl.col('segment') == 'Enterprise'))
# Filter data into true and false results
var_t_filter_2070956975408 = var_formula_2072268134896.filter(pl.col('risk_band') == 'High')
var_f_filter_2070956975408 = var_formula_2072268134896.filter(~(pl.col('risk_band') == 'High'))
import polars as pl
# Random split with seed 42 (row-safe full shuffle)
indexed_df = var_formula_2072268134896.with_row_index('__split_idx').sort(pl.col('__split_idx').shuffle(seed=42))
var_estimation_2070956979248 = indexed_df.filter(pl.col('__split_idx') < pl.col('__split_idx').max() * 0.8).drop('__split_idx')
var_validation_2070956979248 = indexed_df.filter(pl.col('__split_idx') >= pl.col('__split_idx').max() * 0.8).drop('__split_idx')
var_sort_2072268136816 = var_groupby_2072268138736.sort('order_year_month', descending=False)
var_sort_2072268120752 = var_groupby_2072268118832.sort('revenue_usd', descending=True)
var_sort_2072268124272 = var_groupby_2072268127792.sort(['region', 'channel_group'], descending=[False, False])
var_sort_2070956733328 = var_groupby_2072268391920.sort(['segment', 'risk_band'], descending=[False, False])
# Filter data into true and false results
var_t_filter_2072268399280 = var_groupby_2072268393840.filter(pl.col('revenue_usd') > 4000)
var_f_filter_2072268399280 = var_groupby_2072268393840.filter(~(pl.col('revenue_usd') > 4000))
var_sort_2072268405040 = var_groupby_2072268403120.sort('revenue_usd', descending=True)
var_sort_2072268459696 = var_groupby_2072268461616.sort('revenue_usd', descending=True)
import duckdb
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_select_2070956726128.collect() if hasattr(var_select_2070956726128, 'collect') else var_select_2070956726128
duck.register('df_for_duck', df_for_duck)
df_for_duck = duck.sql('''WITH df_step_0 AS (SELECT *, "gross_local" * "usd_rate" AS "gross_revenue_usd_raw" FROM df_for_duck), df_step_1 AS (SELECT *, CASE WHEN "risk_band" = 'High' THEN 1 ELSE 0 END AS "is_high_risk" FROM df_step_0) SELECT * FROM df_step_1''').pl()
# Widen DuckDB-native types into Select-supported dtypes
df_for_duck = normalize_to_supported_dtypes(df_for_duck)
# Preserve lazy execution when the incoming value is lazy
var_formula_2072268467056 = df_for_duck.lazy() if hasattr(var_select_2070956726128, 'collect') else df_for_duck
duck.close()
# Ensure we're working with a LazyFrame for memory efficiency
if var_select_2070956968048 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_select_2070956968048, pl.DataFrame):
        var_select_2070956968048_lazy = var_select_2070956968048.lazy()
    elif isinstance(var_select_2070956968048, pl.LazyFrame):
        var_select_2070956968048_lazy = var_select_2070956968048
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_select_2070956968048)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_select_2070956968048_lazy.sink_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/orders_enriched.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/orders_enriched.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
# Ensure we're working with a LazyFrame for memory efficiency
if var_t_filter_2070956971568 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_t_filter_2070956971568, pl.DataFrame):
        var_t_filter_2070956971568_lazy = var_t_filter_2070956971568.lazy()
    elif isinstance(var_t_filter_2070956971568, pl.LazyFrame):
        var_t_filter_2070956971568_lazy = var_t_filter_2070956971568
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_t_filter_2070956971568)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_t_filter_2070956971568_lazy.sink_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/orders_enterprise.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/orders_enterprise.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
# Ensure we're working with a LazyFrame for memory efficiency
if var_t_filter_2070956975408 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_t_filter_2070956975408, pl.DataFrame):
        var_t_filter_2070956975408_lazy = var_t_filter_2070956975408.lazy()
    elif isinstance(var_t_filter_2070956975408, pl.LazyFrame):
        var_t_filter_2070956975408_lazy = var_t_filter_2070956975408
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_t_filter_2070956975408)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_t_filter_2070956975408_lazy.sink_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/orders_high_risk.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/orders_high_risk.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
# Ensure we're working with a LazyFrame for memory efficiency
if var_estimation_2070956979248 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_estimation_2070956979248, pl.DataFrame):
        var_estimation_2070956979248_lazy = var_estimation_2070956979248.lazy()
    elif isinstance(var_estimation_2070956979248, pl.LazyFrame):
        var_estimation_2070956979248_lazy = var_estimation_2070956979248
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_estimation_2070956979248)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_estimation_2070956979248_lazy.sink_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/fact_estimation.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/fact_estimation.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
# Ensure we're working with a LazyFrame for memory efficiency
if var_validation_2070956979248 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_validation_2070956979248, pl.DataFrame):
        var_validation_2070956979248_lazy = var_validation_2070956979248.lazy()
    elif isinstance(var_validation_2070956979248, pl.LazyFrame):
        var_validation_2070956979248_lazy = var_validation_2070956979248
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_validation_2070956979248)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_validation_2070956979248_lazy.sink_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/fact_validation.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/fact_validation.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
var_runtot_2072268140656 = var_sort_2072268136816.with_columns([
    pl.col("revenue_usd").cum_sum().alias("RunTot_revenue_usd")
])
var_runtot_2072268140656 = normalize_to_supported_dtypes(var_runtot_2072268140656)
# Ensure we're working with a LazyFrame for memory efficiency
if var_sort_2072268120752 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_sort_2072268120752, pl.DataFrame):
        var_sort_2072268120752_lazy = var_sort_2072268120752.lazy()
    elif isinstance(var_sort_2072268120752, pl.LazyFrame):
        var_sort_2072268120752_lazy = var_sort_2072268120752
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_sort_2072268120752)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_sort_2072268120752_lazy.sink_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/category_revenue.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/category_revenue.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
# Ensure we're working with a LazyFrame for memory efficiency
if var_sort_2072268124272 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_sort_2072268124272, pl.DataFrame):
        var_sort_2072268124272_lazy = var_sort_2072268124272.lazy()
    elif isinstance(var_sort_2072268124272, pl.LazyFrame):
        var_sort_2072268124272_lazy = var_sort_2072268124272
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_sort_2072268124272)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_sort_2072268124272_lazy.sink_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/region_channel_revenue.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/region_channel_revenue.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
# Ensure we're working with a LazyFrame for memory efficiency
if var_sort_2070956733328 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_sort_2070956733328, pl.DataFrame):
        var_sort_2070956733328_lazy = var_sort_2070956733328.lazy()
    elif isinstance(var_sort_2070956733328, pl.LazyFrame):
        var_sort_2070956733328_lazy = var_sort_2070956733328
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_sort_2070956733328)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_sort_2070956733328_lazy.sink_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/segment_revenue.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/segment_revenue.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
var_sort_2072268397360 = var_t_filter_2072268399280.sort('revenue_usd', descending=True)
import duckdb
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_sort_2072268405040.collect() if hasattr(var_sort_2072268405040, 'collect') else var_sort_2072268405040
duck.register('df_for_duck', df_for_duck)
df_for_duck = duck.sql('''WITH df_step_0 AS (SELECT *, "revenue_usd" / "lead_time_days" AS "revenue_per_lead_day" FROM df_for_duck) SELECT * FROM df_step_0''').pl()
# Widen DuckDB-native types into Select-supported dtypes
df_for_duck = normalize_to_supported_dtypes(df_for_duck)
# Preserve lazy execution when the incoming value is lazy
var_formula_2072268456176 = df_for_duck.lazy() if hasattr(var_sort_2072268405040, 'collect') else df_for_duck
duck.close()
# Ensure we're working with a LazyFrame for memory efficiency
if var_sort_2072268459696 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_sort_2072268459696, pl.DataFrame):
        var_sort_2072268459696_lazy = var_sort_2072268459696.lazy()
    elif isinstance(var_sort_2072268459696, pl.LazyFrame):
        var_sort_2072268459696_lazy = var_sort_2072268459696
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_sort_2072268459696)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_sort_2072268459696_lazy.sink_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/fx_exposure.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/fx_exposure.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
var_groupby_2072268465136 = var_formula_2072268467056.select([
    pl.col('order_id').n_unique().alias('clean_orders'),
    pl.col('net_revenue_usd').sum().alias('net_revenue_usd'),
    pl.col('gross_margin_usd').sum().alias('gross_margin_usd'),
    pl.col('is_returned').sum().alias('returned_orders'),
    pl.col('customer_id').n_unique().alias('distinct_customers'),
    pl.col('product_id').n_unique().alias('distinct_products'),
    pl.col('gross_revenue_usd_raw').sum().alias('gross_revenue_usd_raw'),
    pl.col('is_high_risk').sum().alias('high_risk_orders')
])
var_groupby_2072268465136 = normalize_to_supported_dtypes(var_groupby_2072268465136)
var_select_2072268142576 = var_runtot_2072268140656.select(['order_year_month', 'revenue_usd', 'margin_usd', 'orders', 'RunTot_revenue_usd'])
var_select_2072268142576 = var_select_2072268142576.rename({'RunTot_revenue_usd': 'cumulative_revenue_usd'})
# Ensure we're working with a LazyFrame for memory efficiency
if var_sort_2072268397360 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_sort_2072268397360, pl.DataFrame):
        var_sort_2072268397360_lazy = var_sort_2072268397360.lazy()
    elif isinstance(var_sort_2072268397360, pl.LazyFrame):
        var_sort_2072268397360_lazy = var_sort_2072268397360
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_sort_2072268397360)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_sort_2072268397360_lazy.sink_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/top_customers.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/top_customers.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
# Ensure we're working with a LazyFrame for memory efficiency
if var_formula_2072268456176 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_formula_2072268456176, pl.DataFrame):
        var_formula_2072268456176_lazy = var_formula_2072268456176.lazy()
    elif isinstance(var_formula_2072268456176, pl.LazyFrame):
        var_formula_2072268456176_lazy = var_formula_2072268456176
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_formula_2072268456176)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_formula_2072268456176_lazy.sink_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/supplier_performance.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/supplier_performance.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
var_select_2072268470896 = var_groupby_2072268465136.select(['clean_orders', 'gross_revenue_usd_raw', 'net_revenue_usd', 'gross_margin_usd', 'returned_orders', 'distinct_customers', 'distinct_products', 'high_risk_orders'])
var_select_2072268470896 = var_select_2072268470896.rename({'gross_revenue_usd_raw': 'gross_revenue_usd'})
# Ensure we're working with a LazyFrame for memory efficiency
if var_select_2072268142576 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_select_2072268142576, pl.DataFrame):
        var_select_2072268142576_lazy = var_select_2072268142576.lazy()
    elif isinstance(var_select_2072268142576, pl.LazyFrame):
        var_select_2072268142576_lazy = var_select_2072268142576
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_select_2072268142576)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_select_2072268142576_lazy.sink_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/monthly_revenue.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/monthly_revenue.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
_2072268113392_cols = (var_select_2072268142576.collect_schema().names() if isinstance(var_select_2072268142576, pl.LazyFrame) else var_select_2072268142576.columns)
# Validate data columns
missing = [col for col in ['revenue_usd', 'margin_usd', 'orders'] if col not in _2072268113392_cols]
if missing:
    print(f'Warning: Missing columns will be skipped: {missing}')

# Filter to existing columns
valid_key_cols = [col for col in ['order_year_month'] if col in _2072268113392_cols]
valid_data_cols = [col for col in ['revenue_usd', 'margin_usd', 'orders'] if col in _2072268113392_cols]

# Transpose operation using Polars unpivot
var_transpose_2072268113392 = var_select_2072268142576.unpivot(
    index=valid_key_cols,
    on=valid_data_cols,
    variable_name='Name',
    value_name='Value'
)
# Widen unpivot supertypes into Select-supported dtypes
var_transpose_2072268113392 = normalize_to_supported_dtypes(var_transpose_2072268113392)
import duckdb
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_select_2072268470896.collect() if hasattr(var_select_2072268470896, 'collect') else var_select_2072268470896
duck.register('df_for_duck', df_for_duck)
df_for_duck = duck.sql('''WITH df_step_0 AS (SELECT * REPLACE (ROUND("gross_revenue_usd", 2) AS "gross_revenue_usd") FROM df_for_duck), df_step_1 AS (SELECT *, CASE WHEN "net_revenue_usd" = 0 
THEN NULL 
ELSE ROUND("gross_margin_usd" / "net_revenue_usd", 4) 
END AS "margin_pct" FROM df_step_0) SELECT * FROM df_step_1''').pl()
# Widen DuckDB-native types into Select-supported dtypes
df_for_duck = normalize_to_supported_dtypes(df_for_duck)
# Preserve lazy execution when the incoming value is lazy
var_formula_2072268468976 = df_for_duck.lazy() if hasattr(var_select_2072268470896, 'collect') else df_for_duck
duck.close()
var_select_2072268115312 = var_transpose_2072268113392.select(['order_year_month', 'Name', 'Value'])
var_select_2072268115312 = var_select_2072268115312.rename({'Name': 'metric', 'Value': 'value'})
var_select_2070956725488 = var_formula_2072268468976.select(['clean_orders', 'gross_revenue_usd', 'net_revenue_usd', 'gross_margin_usd', 'margin_pct', 'returned_orders', 'high_risk_orders', 'distinct_customers', 'distinct_products'])
# Ensure we're working with a LazyFrame for memory efficiency
if var_select_2072268115312 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_select_2072268115312, pl.DataFrame):
        var_select_2072268115312_lazy = var_select_2072268115312.lazy()
    elif isinstance(var_select_2072268115312, pl.LazyFrame):
        var_select_2072268115312_lazy = var_select_2072268115312
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_select_2072268115312)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_select_2072268115312_lazy.sink_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/monthly_revenue_long.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/monthly_revenue_long.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
_2070957018480_cols = (var_select_2070956725488.collect_schema().names() if isinstance(var_select_2070956725488, pl.LazyFrame) else var_select_2070956725488.columns)
# Validate data columns
missing = [col for col in ['clean_orders', 'gross_revenue_usd', 'net_revenue_usd', 'gross_margin_usd', 'margin_pct', 'returned_orders', 'high_risk_orders', 'distinct_customers', 'distinct_products'] if col not in _2070957018480_cols]
if missing:
    print(f'Warning: Missing columns will be skipped: {missing}')

# Filter to existing columns
valid_key_cols = [col for col in [] if col in _2070957018480_cols]
valid_data_cols = [col for col in ['clean_orders', 'gross_revenue_usd', 'net_revenue_usd', 'gross_margin_usd', 'margin_pct', 'returned_orders', 'high_risk_orders', 'distinct_customers', 'distinct_products'] if col in _2070957018480_cols]

# Transpose operation using Polars unpivot
var_transpose_2070957018480 = var_select_2070956725488.unpivot(
    index=valid_key_cols,
    on=valid_data_cols,
    variable_name='Name',
    value_name='Value'
)
# Widen unpivot supertypes into Select-supported dtypes
var_transpose_2070957018480 = normalize_to_supported_dtypes(var_transpose_2070957018480)
var_select_2070957020400 = var_transpose_2070957018480.select(['Name', 'Value'])
var_select_2070957020400 = var_select_2070957020400.rename({'Name': 'metric', 'Value': 'value'})
# Ensure we're working with a LazyFrame for memory efficiency
if var_select_2070957020400 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_select_2070957020400, pl.DataFrame):
        var_select_2070957020400_lazy = var_select_2070957020400.lazy()
    elif isinstance(var_select_2070957020400, pl.LazyFrame):
        var_select_2070957020400_lazy = var_select_2070957020400
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_select_2070957020400)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_select_2070957020400_lazy.sink_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/kpi_summary.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/kpi_summary.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
