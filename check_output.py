import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_2433030920528 = pl.scan_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/data/channels.csv', infer_schema=False)

# var_file_input_2433030920528 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_2433030921168 = pl.scan_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/data/orders.csv', infer_schema=False)

# var_file_input_2433030921168 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_2433030924368 = pl.scan_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/data/customers.csv', infer_schema=False)

# var_file_input_2433030924368 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_2433030914128 = pl.scan_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/data/products.csv', infer_schema=False)

# var_file_input_2433030914128 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_2433030915728 = pl.scan_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/data/suppliers.csv', infer_schema=False)

# var_file_input_2433030915728 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_2433030917328 = pl.scan_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/data/fx_rates.csv', infer_schema=False)

# var_file_input_2433030917328 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
var_select_2433030389616 = var_file_input_2433030920528.select(['channel_id', 'channel_name', 'channel_group', 'is_digital'])
var_select_2433030389616 = var_select_2433030389616.with_columns(
    pl.col('channel_id').cast(pl.Int64, strict=False).alias('channel_id')
)
var_select_2433030389616 = var_select_2433030389616.with_columns(
    pl.col('channel_name').cast(pl.String, strict=False).alias('channel_name')
)
var_select_2433030389616 = var_select_2433030389616.with_columns(
    pl.col('channel_group').cast(pl.String, strict=False).alias('channel_group')
)
var_select_2433030389616 = var_select_2433030389616.with_columns(
    pl.col('is_digital').cast(pl.String, strict=False).alias('is_digital')
)
var_select_2433030918448 = var_file_input_2433030921168.select([' Order ID ', 'Customer_Id', 'PRODUCT_ID', 'supplier id', 'Channel ID', 'Currency', 'Order TS', 'Quantity', 'unit_price_local', 'Discount Pct', 'tax_local', 'shipping_local', 'Status', 'Payment Method', 'is_returned'])
var_select_2433030918448 = var_select_2433030918448.with_columns(
    pl.col(' Order ID ').cast(pl.String, strict=False).alias(' Order ID ')
)
var_select_2433030918448 = var_select_2433030918448.with_columns(
    pl.col('Customer_Id').cast(pl.Int64, strict=False).alias('Customer_Id')
)
var_select_2433030918448 = var_select_2433030918448.with_columns(
    pl.col('PRODUCT_ID').cast(pl.Int64, strict=False).alias('PRODUCT_ID')
)
var_select_2433030918448 = var_select_2433030918448.with_columns(
    pl.col('supplier id').cast(pl.Int64, strict=False).alias('supplier id')
)
var_select_2433030918448 = var_select_2433030918448.with_columns(
    pl.col('Channel ID').cast(pl.Int64, strict=False).alias('Channel ID')
)
var_select_2433030918448 = var_select_2433030918448.with_columns(
    pl.col('Currency').cast(pl.String, strict=False).alias('Currency')
)
var_select_2433030918448 = var_select_2433030918448.with_columns(
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
    ]).alias('Order TS')
)
var_select_2433030918448 = var_select_2433030918448.with_columns(
    pl.col('Quantity').cast(pl.Int64, strict=False).alias('Quantity')
)
var_select_2433030918448 = var_select_2433030918448.with_columns(
    pl.col('unit_price_local').cast(pl.Float64, strict=False).alias('unit_price_local')
)
var_select_2433030918448 = var_select_2433030918448.with_columns(
    pl.col('Discount Pct').cast(pl.Float64, strict=False).alias('Discount Pct')
)
var_select_2433030918448 = var_select_2433030918448.with_columns(
    pl.col('tax_local').cast(pl.Float64, strict=False).alias('tax_local')
)
var_select_2433030918448 = var_select_2433030918448.with_columns(
    pl.col('shipping_local').cast(pl.Float64, strict=False).alias('shipping_local')
)
var_select_2433030918448 = var_select_2433030918448.with_columns(
    pl.col('Status').cast(pl.String, strict=False).alias('Status')
)
var_select_2433030918448 = var_select_2433030918448.with_columns(
    pl.col('Payment Method').cast(pl.String, strict=False).alias('Payment Method')
)
var_select_2433030918448 = var_select_2433030918448.with_columns(
    pl.col('is_returned').cast(pl.String, strict=False).alias('is_returned')
)
var_select_2433030384496 = var_file_input_2433030924368.select(['customer_id', 'email', 'full_name', 'signup_date', 'country', 'region', 'currency', 'segment', 'age_band', 'loyalty_tier'])
var_select_2433030384496 = var_select_2433030384496.with_columns(
    pl.col('customer_id').cast(pl.Int64, strict=False).alias('customer_id')
)
var_select_2433030384496 = var_select_2433030384496.with_columns(
    pl.col('email').cast(pl.String, strict=False).alias('email')
)
var_select_2433030384496 = var_select_2433030384496.with_columns(
    pl.col('full_name').cast(pl.String, strict=False).alias('full_name')
)
var_select_2433030384496 = var_select_2433030384496.with_columns(
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
)
var_select_2433030384496 = var_select_2433030384496.with_columns(
    pl.col('country').cast(pl.String, strict=False).alias('country')
)
var_select_2433030384496 = var_select_2433030384496.with_columns(
    pl.col('region').cast(pl.String, strict=False).alias('region')
)
var_select_2433030384496 = var_select_2433030384496.with_columns(
    pl.col('currency').cast(pl.String, strict=False).alias('currency')
)
var_select_2433030384496 = var_select_2433030384496.with_columns(
    pl.col('segment').cast(pl.String, strict=False).alias('segment')
)
var_select_2433030384496 = var_select_2433030384496.with_columns(
    pl.col('age_band').cast(pl.String, strict=False).alias('age_band')
)
var_select_2433030384496 = var_select_2433030384496.with_columns(
    pl.col('loyalty_tier').cast(pl.String, strict=False).alias('loyalty_tier')
)
var_select_2433030384496 = var_select_2433030384496.rename({'email': 'customer_email', 'full_name': 'customer_full_name', 'country': 'customer_country', 'currency': 'customer_currency', 'age_band': 'customer_age_band'})
var_select_2433030386256 = var_file_input_2433030914128.select(['product_id', 'sku', 'product_name', 'category', 'subcategory', 'brand', 'unit_price', 'unit_cost', 'launch_date'])
var_select_2433030386256 = var_select_2433030386256.with_columns(
    pl.col('product_id').cast(pl.Int64, strict=False).alias('product_id')
)
var_select_2433030386256 = var_select_2433030386256.with_columns(
    pl.col('sku').cast(pl.String, strict=False).alias('sku')
)
var_select_2433030386256 = var_select_2433030386256.with_columns(
    pl.col('product_name').cast(pl.String, strict=False).alias('product_name')
)
var_select_2433030386256 = var_select_2433030386256.with_columns(
    pl.col('category').cast(pl.String, strict=False).alias('category')
)
var_select_2433030386256 = var_select_2433030386256.with_columns(
    pl.col('subcategory').cast(pl.String, strict=False).alias('subcategory')
)
var_select_2433030386256 = var_select_2433030386256.with_columns(
    pl.col('brand').cast(pl.String, strict=False).alias('brand')
)
var_select_2433030386256 = var_select_2433030386256.with_columns(
    pl.col('unit_price').cast(pl.Float64, strict=False).alias('unit_price')
)
var_select_2433030386256 = var_select_2433030386256.with_columns(
    pl.col('unit_cost').cast(pl.Float64, strict=False).alias('unit_cost')
)
var_select_2433030386256 = var_select_2433030386256.with_columns(
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
)
var_select_2433030382736 = var_file_input_2433030915728.select(['supplier_id', 'supplier_name', 'country', 'lead_time_days', 'reliability_score'])
var_select_2433030382736 = var_select_2433030382736.with_columns(
    pl.col('supplier_id').cast(pl.Int64, strict=False).alias('supplier_id')
)
var_select_2433030382736 = var_select_2433030382736.with_columns(
    pl.col('supplier_name').cast(pl.String, strict=False).alias('supplier_name')
)
var_select_2433030382736 = var_select_2433030382736.with_columns(
    pl.col('country').cast(pl.String, strict=False).alias('country')
)
var_select_2433030382736 = var_select_2433030382736.with_columns(
    pl.col('lead_time_days').cast(pl.Int64, strict=False).alias('lead_time_days')
)
var_select_2433030382736 = var_select_2433030382736.with_columns(
    pl.col('reliability_score').cast(pl.Float64, strict=False).alias('reliability_score')
)
var_select_2433030378096 = var_file_input_2433030917328.select(['currency', 'currency_name', 'usd_rate'])
var_select_2433030378096 = var_select_2433030378096.with_columns(
    pl.col('currency').cast(pl.String, strict=False).alias('currency')
)
var_select_2433030378096 = var_select_2433030378096.with_columns(
    pl.col('currency_name').cast(pl.String, strict=False).alias('currency_name')
)
var_select_2433030378096 = var_select_2433030378096.with_columns(
    pl.col('usd_rate').cast(pl.Float64, strict=False).alias('usd_rate')
)
import polars as pl
# Normalize column names (11 renamed)
var_normalize_columns_2433037393328 = var_select_2433030918448.rename({' Order ID ': 'order_id', 'Customer_Id': 'customer_id', 'PRODUCT_ID': 'product_id', 'supplier id': 'supplier_id', 'Channel ID': 'channel_id', 'Currency': 'currency', 'Order TS': 'order_ts', 'Quantity': 'quantity', 'Discount Pct': 'discount_pct', 'Status': 'status', 'Payment Method': 'payment_method'})
import duckdb
import polars as pl
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_select_2433030378096.collect() if hasattr(var_select_2433030378096, 'collect') else var_select_2433030378096
duck.register('df_step_0', df_for_duck)
df_for_duck = duck.execute('''SELECT * REPLACE (LOWER("currency") AS "currency") FROM df_step_0''').pl()
# Preserve lazy execution when the incoming value is lazy
var_formula_2433037391248 = df_for_duck.lazy() if hasattr(var_select_2433030378096, 'collect') else df_for_duck
duck.close()
from trigger_designer.core.utils.cleansing_util import DataCleansing, NullStrategy
import polars as pl
# Convert LazyFrame to DataFrame if needed
_cleansing_input = var_normalize_columns_2433037393328.collect() if hasattr(var_normalize_columns_2433037393328, 'collect') else var_normalize_columns_2433037393328
cleaner = DataCleansing(_cleansing_input)
cleaner.strip_whitespace(remove_all=False, normalize_spaces=True, fields=['is_returned'])
cleaner.modify_case('lower', fields=['is_returned'])
var_cleansing_2433030380176 = cleaner.get_result()
from trigger_designer.core.utils.cleansing_util import DataCleansing, NullStrategy
import polars as pl
# Convert LazyFrame to DataFrame if needed
_cleansing_input = var_cleansing_2433030380176.collect() if hasattr(var_cleansing_2433030380176, 'collect') else var_cleansing_2433030380176
cleaner = DataCleansing(_cleansing_input)
cleaner.remove_rows_with_nulls(fields=['order_id', 'customer_id', 'product_id'])
cleaner.strip_whitespace(remove_all=False, normalize_spaces=True, fields=['order_id', 'customer_id', 'product_id'])
cleaner.modify_case('lower', fields=['order_id', 'customer_id', 'product_id'])
var_cleansing_2433030382576 = cleaner.get_result()
import duckdb
import polars as pl
# Filter rows with a SQL WHERE clause (no new columns)
df_for_duck = var_cleansing_2433030382576.collect() if hasattr(var_cleansing_2433030382576, 'collect') else var_cleansing_2433030382576
duck = duckdb.connect(':memory:')
duck.register('df_filter', df_for_duck)
var_t_filter_2433037388528 = duck.execute('SELECT * FROM df_filter WHERE "quantity" >= 1 and "quantity" <= 500').pl()
var_f_filter_2433037388528 = duck.execute('SELECT * FROM df_filter WHERE NOT ("quantity" >= 1 and "quantity" <= 500)').pl()
# Preserve lazy execution when the incoming value is lazy
var_t_filter_2433037388528 = var_t_filter_2433037388528.lazy() if hasattr(var_cleansing_2433030382576, 'collect') else var_t_filter_2433037388528
var_f_filter_2433037388528 = var_f_filter_2433037388528.lazy() if hasattr(var_cleansing_2433030382576, 'collect') else var_f_filter_2433037388528
duck.close()
import duckdb
import polars as pl
# Filter rows with a SQL WHERE clause (no new columns)
df_for_duck = var_t_filter_2433037388528.collect() if hasattr(var_t_filter_2433037388528, 'collect') else var_t_filter_2433037388528
duck = duckdb.connect(':memory:')
duck.register('df_filter', df_for_duck)
var_t_filter_2433037386608 = duck.execute('SELECT * FROM df_filter WHERE "unit_price_local" > 0 and \n"unit_price_local" <= 5000').pl()
var_f_filter_2433037386608 = duck.execute('SELECT * FROM df_filter WHERE NOT ("unit_price_local" > 0 and \n"unit_price_local" <= 5000)').pl()
# Preserve lazy execution when the incoming value is lazy
var_t_filter_2433037386608 = var_t_filter_2433037386608.lazy() if hasattr(var_t_filter_2433037388528, 'collect') else var_t_filter_2433037386608
var_f_filter_2433037386608 = var_f_filter_2433037386608.lazy() if hasattr(var_t_filter_2433037388528, 'collect') else var_f_filter_2433037386608
duck.close()
import duckdb
import polars as pl
# Filter rows with a SQL WHERE clause (no new columns)
df_for_duck = var_t_filter_2433037386608.collect() if hasattr(var_t_filter_2433037386608, 'collect') else var_t_filter_2433037386608
duck = duckdb.connect(':memory:')
duck.register('df_filter', df_for_duck)
var_t_filter_2433037388848 = duck.execute('SELECT * FROM df_filter WHERE YEAR("order_ts") <= 2025').pl()
var_f_filter_2433037388848 = duck.execute('SELECT * FROM df_filter WHERE NOT (YEAR("order_ts") <= 2025)').pl()
# Preserve lazy execution when the incoming value is lazy
var_t_filter_2433037388848 = var_t_filter_2433037388848.lazy() if hasattr(var_t_filter_2433037386608, 'collect') else var_t_filter_2433037388848
var_f_filter_2433037388848 = var_f_filter_2433037388848.lazy() if hasattr(var_t_filter_2433037386608, 'collect') else var_f_filter_2433037388848
duck.close()
import polars as pl
# Split into unique and duplicate records based on: order_id
var_unique_2433031064304 = var_t_filter_2433037388848.unique(subset=["order_id"], maintain_order=True)
var_duplicate_2433031064304 = var_t_filter_2433037388848.filter(pl.struct(["order_id"]).is_duplicated())
# Polars LazyFrame Join Operation
import polars as pl

def _ensure_lazyframe(data):
    if isinstance(data, pl.DataFrame):
        return data.lazy()
    if isinstance(data, pl.LazyFrame):
        return data
    raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(data)}')

_left_input = _ensure_lazyframe(var_unique_2433031064304)
_right_input = _ensure_lazyframe(var_select_2433030384496)

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
var_join_2433031074704 = _join_result.filter(
    (pl.col('__left_present').is_not_null() & pl.col('__right_present').is_not_null())
).select([
    'channel_id',
    'currency',
    'customer_id',
    'discount_pct',
    'is_returned',
    'order_id',
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
    'customer_full_name',
    'loyalty_tier',
    'region',
    'segment',
    'signup_date'
])

# Extract left-only data efficiently
_left_cols = ['order_id', 'customer_id', 'product_id', 'supplier_id', 'channel_id', 'currency', 'order_ts', 'quantity', 'unit_price_local', 'discount_pct', 'tax_local', 'shipping_local', 'status', 'payment_method', 'is_returned']
var_l_join_2433031074704 = _join_result.filter(
    pl.col('__right_present').is_null()
).select(_left_cols)

# Extract right-only data efficiently
_right_cols = ['customer_id', 'customer_email', 'customer_full_name', 'signup_date', 'customer_country', 'region', 'customer_currency', 'segment', 'customer_age_band', 'loyalty_tier']
var_r_join_2433031074704 = _join_result.filter(
    pl.col('__left_present').is_null()
).select(_right_cols)

# Clean up temporary variables
del _left_input, _right_input, _left_tagged, _right_tagged, _join_result, _left_cols, _right_cols
import polars as pl
_union_inputs_2433019852944 = [var_join_2433031074704, var_l_join_2433031074704]
var_union_2433019852944 = pl.concat([(f.lazy() if isinstance(f, pl.DataFrame) else f) for f in _union_inputs_2433019852944], how='diagonal_relaxed')
del _union_inputs_2433019852944
# Polars LazyFrame Join Operation
import polars as pl

def _ensure_lazyframe(data):
    if isinstance(data, pl.DataFrame):
        return data.lazy()
    if isinstance(data, pl.LazyFrame):
        return data
    raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(data)}')

_left_input = _ensure_lazyframe(var_union_2433019852944)
_right_input = _ensure_lazyframe(var_select_2433030386256)

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
var_join_2433037671056 = _join_result.filter(
    (pl.col('__left_present').is_not_null() & pl.col('__right_present').is_not_null())
).select([
    'channel_id',
    'currency',
    'customer_age_band',
    'customer_country',
    'customer_currency',
    'customer_email',
    'customer_full_name',
    'customer_id',
    'discount_pct',
    'is_returned',
    'loyalty_tier',
    'order_id',
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
    'unit_price'
])

# Extract left-only data efficiently
_left_cols = ['channel_id', 'currency', 'customer_id', 'discount_pct', 'is_returned', 'order_id', 'order_ts', 'payment_method', 'product_id', 'quantity', 'shipping_local', 'status', 'supplier_id', 'tax_local', 'unit_price_local', 'customer_age_band', 'customer_country', 'customer_currency', 'customer_email', 'customer_full_name', 'loyalty_tier', 'region', 'segment', 'signup_date']
var_l_join_2433037671056 = _join_result.filter(
    pl.col('__right_present').is_null()
).select(_left_cols)

# Extract right-only data efficiently
_right_cols = ['product_id', 'sku', 'product_name', 'category', 'subcategory', 'brand', 'unit_price', 'unit_cost', 'launch_date']
var_r_join_2433037671056 = _join_result.filter(
    pl.col('__left_present').is_null()
).select(_right_cols)

# Clean up temporary variables
del _left_input, _right_input, _left_tagged, _right_tagged, _join_result, _left_cols, _right_cols
import polars as pl
_union_inputs_2433020497744 = [var_join_2433037671056, var_l_join_2433037671056]
var_union_2433020497744 = pl.concat([(f.lazy() if isinstance(f, pl.DataFrame) else f) for f in _union_inputs_2433020497744], how='diagonal_relaxed')
del _union_inputs_2433020497744
# Polars LazyFrame Join Operation
import polars as pl

def _ensure_lazyframe(data):
    if isinstance(data, pl.DataFrame):
        return data.lazy()
    if isinstance(data, pl.LazyFrame):
        return data
    raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(data)}')

_left_input = _ensure_lazyframe(var_union_2433020497744)
_right_input = _ensure_lazyframe(var_select_2433030382736)

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
var_join_2433037674576 = _join_result.filter(
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
    'customer_full_name',
    'customer_id',
    'discount_pct',
    'is_returned',
    'launch_date',
    'loyalty_tier',
    'order_id',
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
    'supplier_name'
])

# Extract left-only data efficiently
_left_cols = ['channel_id', 'currency', 'customer_age_band', 'customer_country', 'customer_currency', 'customer_email', 'customer_full_name', 'customer_id', 'discount_pct', 'is_returned', 'loyalty_tier', 'order_id', 'order_ts', 'payment_method', 'product_id', 'quantity', 'region', 'segment', 'shipping_local', 'signup_date', 'status', 'supplier_id', 'tax_local', 'unit_price_local', 'brand', 'category', 'launch_date', 'product_name', 'sku', 'subcategory', 'unit_cost', 'unit_price']
var_l_join_2433037674576 = _join_result.filter(
    pl.col('__right_present').is_null()
).select(_left_cols)

# Extract right-only data efficiently
_right_cols = ['supplier_id', 'supplier_name', 'country', 'lead_time_days', 'reliability_score']
var_r_join_2433037674576 = _join_result.filter(
    pl.col('__left_present').is_null()
).select(_right_cols)

# Clean up temporary variables
del _left_input, _right_input, _left_tagged, _right_tagged, _join_result, _left_cols, _right_cols
import polars as pl
_union_inputs_2433832559280 = [var_join_2433037674576, var_l_join_2433037674576]
var_union_2433832559280 = pl.concat([(f.lazy() if isinstance(f, pl.DataFrame) else f) for f in _union_inputs_2433832559280], how='diagonal_relaxed')
del _union_inputs_2433832559280
# Polars LazyFrame Join Operation
import polars as pl

def _ensure_lazyframe(data):
    if isinstance(data, pl.DataFrame):
        return data.lazy()
    if isinstance(data, pl.LazyFrame):
        return data
    raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(data)}')

_left_input = _ensure_lazyframe(var_union_2433832559280)
_right_input = _ensure_lazyframe(var_select_2433030389616)

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
var_join_2433037669776 = _join_result.filter(
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
    'customer_full_name',
    'customer_id',
    'discount_pct',
    'is_returned',
    'launch_date',
    'lead_time_days',
    'loyalty_tier',
    'order_id',
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
    'is_digital'
])

# Extract left-only data efficiently
_left_cols = ['brand', 'category', 'channel_id', 'currency', 'customer_age_band', 'customer_country', 'customer_currency', 'customer_email', 'customer_full_name', 'customer_id', 'discount_pct', 'is_returned', 'launch_date', 'loyalty_tier', 'order_id', 'order_ts', 'payment_method', 'product_id', 'product_name', 'quantity', 'region', 'segment', 'shipping_local', 'signup_date', 'sku', 'status', 'subcategory', 'supplier_id', 'tax_local', 'unit_cost', 'unit_price', 'unit_price_local', 'country', 'lead_time_days', 'reliability_score', 'supplier_name']
var_l_join_2433037669776 = _join_result.filter(
    pl.col('__right_present').is_null()
).select(_left_cols)

# Extract right-only data efficiently
_right_cols = ['channel_id', 'channel_name', 'channel_group', 'is_digital']
var_r_join_2433037669776 = _join_result.filter(
    pl.col('__left_present').is_null()
).select(_right_cols)

# Clean up temporary variables
del _left_input, _right_input, _left_tagged, _right_tagged, _join_result, _left_cols, _right_cols
import polars as pl
_union_inputs_2433832558320 = [var_join_2433037669776, var_l_join_2433037669776]
var_union_2433832558320 = pl.concat([(f.lazy() if isinstance(f, pl.DataFrame) else f) for f in _union_inputs_2433832558320], how='diagonal_relaxed')
del _union_inputs_2433832558320
# Polars LazyFrame Join Operation
import polars as pl

def _ensure_lazyframe(data):
    if isinstance(data, pl.DataFrame):
        return data.lazy()
    if isinstance(data, pl.LazyFrame):
        return data
    raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(data)}')

_left_input = _ensure_lazyframe(var_union_2433832558320)
_right_input = _ensure_lazyframe(var_select_2433030378096)

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
var_join_2433037666896 = _join_result.filter(
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
    'customer_full_name',
    'customer_id',
    'discount_pct',
    'is_digital',
    'is_returned',
    'launch_date',
    'lead_time_days',
    'loyalty_tier',
    'order_id',
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
    'usd_rate'
])

# Extract left-only data efficiently
_left_cols = ['brand', 'category', 'channel_id', 'country', 'currency', 'customer_age_band', 'customer_country', 'customer_currency', 'customer_email', 'customer_full_name', 'customer_id', 'discount_pct', 'is_returned', 'launch_date', 'lead_time_days', 'loyalty_tier', 'order_id', 'order_ts', 'payment_method', 'product_id', 'product_name', 'quantity', 'region', 'reliability_score', 'segment', 'shipping_local', 'signup_date', 'sku', 'status', 'subcategory', 'supplier_id', 'supplier_name', 'tax_local', 'unit_cost', 'unit_price', 'unit_price_local', 'channel_group', 'channel_name', 'is_digital']
var_l_join_2433037666896 = _join_result.filter(
    pl.col('__right_present').is_null()
).select(_left_cols)

# Extract right-only data efficiently
_right_cols = ['currency', 'currency_name', 'usd_rate']
var_r_join_2433037666896 = _join_result.filter(
    pl.col('__left_present').is_null()
).select(_right_cols)

# Clean up temporary variables
del _left_input, _right_input, _left_tagged, _right_tagged, _join_result, _left_cols, _right_cols
import duckdb
import polars as pl
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_join_2433037666896.collect() if hasattr(var_join_2433037666896, 'collect') else var_join_2433037666896
duck.register('df_step_0', df_for_duck)
df_for_duck = duck.execute('''SELECT *, "quantity" * "unit_price_local" AS "g" FROM df_step_0''').pl()
duck.register('df_step_1', df_for_duck)
df_for_duck = duck.execute('''SELECT *, "g" AS "gross_local" FROM df_step_1''').pl()
duck.register('df_step_2', df_for_duck)
df_for_duck = duck.execute('''SELECT *, "g" * "discount_pct" AS "discount_local" FROM df_step_2''').pl()
duck.register('df_step_3', df_for_duck)
df_for_duck = duck.execute('''SELECT *, "g" - "discount_local" AS "net_local" FROM df_step_3''').pl()
duck.register('df_step_4', df_for_duck)
df_for_duck = duck.execute('''SELECT *, "net_local" + "tax_local" + "shipping_local" AS "total_local" FROM df_step_4''').pl()
# Preserve lazy execution when the incoming value is lazy
var_formula_2433037677776 = df_for_duck.lazy() if hasattr(var_join_2433037666896, 'collect') else df_for_duck
duck.close()
import duckdb
import polars as pl
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_formula_2433037677776.collect() if hasattr(var_formula_2433037677776, 'collect') else var_formula_2433037677776
duck.register('df_step_0', df_for_duck)
df_for_duck = duck.execute('''SELECT *, "unit_price_local" * "usd_rate" AS "unit_price_usd" FROM df_step_0''').pl()
duck.register('df_step_1', df_for_duck)
df_for_duck = duck.execute('''SELECT *, "net_local" * "usd_rate" AS "net_revenue_usd" FROM df_step_1''').pl()
duck.register('df_step_2', df_for_duck)
df_for_duck = duck.execute('''SELECT *, "tax_local" * "usd_rate" AS "tax_usd" FROM df_step_2''').pl()
duck.register('df_step_3', df_for_duck)
df_for_duck = duck.execute('''SELECT *, "shipping_local" * "usd_rate" AS "shipping_usd" FROM df_step_3''').pl()
duck.register('df_step_4', df_for_duck)
df_for_duck = duck.execute('''SELECT *, "total_local" * "usd_rate" AS "total_usd" FROM df_step_4''').pl()
# Preserve lazy execution when the incoming value is lazy
var_formula_2433037679696 = df_for_duck.lazy() if hasattr(var_formula_2433037677776, 'collect') else df_for_duck
duck.close()
