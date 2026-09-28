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
var_file_input_2675535899984 = pl.scan_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/data/channels.csv', infer_schema=False)

# var_file_input_2675535899984 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_2675535898544 = pl.scan_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/data/orders.csv', infer_schema=False)

# var_file_input_2675535898544 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_2675535897904 = pl.scan_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/data/customers.csv', infer_schema=False)

# var_file_input_2675535897904 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_2675535895024 = pl.scan_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/data/products.csv', infer_schema=False)

# var_file_input_2675535895024 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_2675535893744 = pl.scan_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/data/suppliers.csv', infer_schema=False)

# var_file_input_2675535893744 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_2675535892144 = pl.scan_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/data/fx_rates.csv', infer_schema=False)

# var_file_input_2675535892144 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
var_select_2675535888784 = var_file_input_2675535899984.select(['channel_id', 'channel_name', 'channel_group', 'is_digital'])
var_select_2675535888784 = var_select_2675535888784.with_columns(
    pl.col('channel_id').cast(pl.Int64, strict=False).alias('channel_id')
)
var_select_2675535888784 = var_select_2675535888784.with_columns(
    pl.col('channel_name').cast(pl.String, strict=False).alias('channel_name')
)
var_select_2675535888784 = var_select_2675535888784.with_columns(
    pl.col('channel_group').cast(pl.String, strict=False).alias('channel_group')
)
var_select_2675535888784 = var_select_2675535888784.with_columns(
    pl.col('is_digital').cast(pl.String, strict=False).alias('is_digital')
)
var_select_2675535890544 = var_file_input_2675535898544.select([' Order ID ', 'Customer_Id', 'PRODUCT_ID', 'supplier id', 'Channel ID', 'Currency', 'Order TS', 'Quantity', 'unit_price_local', 'Discount Pct', 'tax_local', 'shipping_local', 'Status', 'Payment Method', 'is_returned'])
var_select_2675535890544 = var_select_2675535890544.with_columns(
    pl.col(' Order ID ').cast(pl.String, strict=False).alias(' Order ID ')
)
var_select_2675535890544 = var_select_2675535890544.with_columns(
    pl.col('Customer_Id').cast(pl.Int64, strict=False).alias('Customer_Id')
)
var_select_2675535890544 = var_select_2675535890544.with_columns(
    pl.col('PRODUCT_ID').cast(pl.Int64, strict=False).alias('PRODUCT_ID')
)
var_select_2675535890544 = var_select_2675535890544.with_columns(
    pl.col('supplier id').cast(pl.Int64, strict=False).alias('supplier id')
)
var_select_2675535890544 = var_select_2675535890544.with_columns(
    pl.col('Channel ID').cast(pl.Int64, strict=False).alias('Channel ID')
)
var_select_2675535890544 = var_select_2675535890544.with_columns(
    pl.col('Currency').cast(pl.String, strict=False).alias('Currency')
)
var_select_2675535890544 = var_select_2675535890544.with_columns(
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
var_select_2675535890544 = var_select_2675535890544.with_columns(
    pl.col('Quantity').cast(pl.Int64, strict=False).alias('Quantity')
)
var_select_2675535890544 = var_select_2675535890544.with_columns(
    pl.col('unit_price_local').cast(pl.Float64, strict=False).alias('unit_price_local')
)
var_select_2675535890544 = var_select_2675535890544.with_columns(
    pl.col('Discount Pct').cast(pl.Float64, strict=False).alias('Discount Pct')
)
var_select_2675535890544 = var_select_2675535890544.with_columns(
    pl.col('tax_local').cast(pl.Float64, strict=False).alias('tax_local')
)
var_select_2675535890544 = var_select_2675535890544.with_columns(
    pl.col('shipping_local').cast(pl.Float64, strict=False).alias('shipping_local')
)
var_select_2675535890544 = var_select_2675535890544.with_columns(
    pl.col('Status').cast(pl.String, strict=False).alias('Status')
)
var_select_2675535890544 = var_select_2675535890544.with_columns(
    pl.col('Payment Method').cast(pl.String, strict=False).alias('Payment Method')
)
var_select_2675535890544 = var_select_2675535890544.with_columns(
    pl.col('is_returned').cast(pl.String, strict=False).alias('is_returned')
)
var_select_2672903719184 = var_file_input_2675535897904.select(['customer_id', 'email', 'full_name', 'signup_date', 'country', 'region', 'currency', 'segment', 'age_band', 'loyalty_tier'])
var_select_2672903719184 = var_select_2672903719184.with_columns(
    pl.col('customer_id').cast(pl.Int64, strict=False).alias('customer_id')
)
var_select_2672903719184 = var_select_2672903719184.with_columns(
    pl.col('email').cast(pl.String, strict=False).alias('email')
)
var_select_2672903719184 = var_select_2672903719184.with_columns(
    pl.col('full_name').cast(pl.String, strict=False).alias('full_name')
)
var_select_2672903719184 = var_select_2672903719184.with_columns(
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
var_select_2672903719184 = var_select_2672903719184.with_columns(
    pl.col('country').cast(pl.String, strict=False).alias('country')
)
var_select_2672903719184 = var_select_2672903719184.with_columns(
    pl.col('region').cast(pl.String, strict=False).alias('region')
)
var_select_2672903719184 = var_select_2672903719184.with_columns(
    pl.col('currency').cast(pl.String, strict=False).alias('currency')
)
var_select_2672903719184 = var_select_2672903719184.with_columns(
    pl.col('segment').cast(pl.String, strict=False).alias('segment')
)
var_select_2672903719184 = var_select_2672903719184.with_columns(
    pl.col('age_band').cast(pl.String, strict=False).alias('age_band')
)
var_select_2672903719184 = var_select_2672903719184.with_columns(
    pl.col('loyalty_tier').cast(pl.String, strict=False).alias('loyalty_tier')
)
var_select_2672903719184 = var_select_2672903719184.rename({'email': 'customer_email', 'full_name': 'customer_name', 'country': 'customer_country', 'currency': 'customer_currency', 'age_band': 'customer_age_band'})
var_select_2675536360976 = var_file_input_2675535895024.select(['product_id', 'sku', 'product_name', 'category', 'subcategory', 'brand', 'unit_price', 'unit_cost', 'launch_date'])
var_select_2675536360976 = var_select_2675536360976.with_columns(
    pl.col('product_id').cast(pl.Int64, strict=False).alias('product_id')
)
var_select_2675536360976 = var_select_2675536360976.with_columns(
    pl.col('sku').cast(pl.String, strict=False).alias('sku')
)
var_select_2675536360976 = var_select_2675536360976.with_columns(
    pl.col('product_name').cast(pl.String, strict=False).alias('product_name')
)
var_select_2675536360976 = var_select_2675536360976.with_columns(
    pl.col('category').cast(pl.String, strict=False).alias('category')
)
var_select_2675536360976 = var_select_2675536360976.with_columns(
    pl.col('subcategory').cast(pl.String, strict=False).alias('subcategory')
)
var_select_2675536360976 = var_select_2675536360976.with_columns(
    pl.col('brand').cast(pl.String, strict=False).alias('brand')
)
var_select_2675536360976 = var_select_2675536360976.with_columns(
    pl.col('unit_price').cast(pl.Float64, strict=False).alias('unit_price')
)
var_select_2675536360976 = var_select_2675536360976.with_columns(
    pl.col('unit_cost').cast(pl.Float64, strict=False).alias('unit_cost')
)
var_select_2675536360976 = var_select_2675536360976.with_columns(
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
var_select_2675536359696 = var_file_input_2675535893744.select(['supplier_id', 'supplier_name', 'country', 'lead_time_days', 'reliability_score'])
var_select_2675536359696 = var_select_2675536359696.with_columns(
    pl.col('supplier_id').cast(pl.Int64, strict=False).alias('supplier_id')
)
var_select_2675536359696 = var_select_2675536359696.with_columns(
    pl.col('supplier_name').cast(pl.String, strict=False).alias('supplier_name')
)
var_select_2675536359696 = var_select_2675536359696.with_columns(
    pl.col('country').cast(pl.String, strict=False).alias('country')
)
var_select_2675536359696 = var_select_2675536359696.with_columns(
    pl.col('lead_time_days').cast(pl.Int64, strict=False).alias('lead_time_days')
)
var_select_2675536359696 = var_select_2675536359696.with_columns(
    pl.col('reliability_score').cast(pl.Float64, strict=False).alias('reliability_score')
)
var_select_2675536357296 = var_file_input_2675535892144.select(['currency', 'currency_name', 'usd_rate'])
var_select_2675536357296 = var_select_2675536357296.with_columns(
    pl.col('currency').cast(pl.String, strict=False).alias('currency')
)
var_select_2675536357296 = var_select_2675536357296.with_columns(
    pl.col('currency_name').cast(pl.String, strict=False).alias('currency_name')
)
var_select_2675536357296 = var_select_2675536357296.with_columns(
    pl.col('usd_rate').cast(pl.Float64, strict=False).alias('usd_rate')
)
import duckdb
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_select_2675535888784.collect() if hasattr(var_select_2675535888784, 'collect') else var_select_2675535888784
duck.register('df_step_0', df_for_duck)
df_for_duck = duck.execute('''SELECT *, 'channels' AS "source_table" FROM df_step_0''').pl()
# Widen DuckDB-native types into Select-supported dtypes
df_for_duck = normalize_to_supported_dtypes(df_for_duck)
# Preserve lazy execution when the incoming value is lazy
var_formula_2675542509200 = df_for_duck.lazy() if hasattr(var_select_2675535888784, 'collect') else df_for_duck
duck.close()
import polars as pl
# Normalize column names (11 renamed)
var_normalize_columns_2675541972048 = var_select_2675535890544.rename({' Order ID ': 'order_id', 'Customer_Id': 'customer_id', 'PRODUCT_ID': 'product_id', 'supplier id': 'supplier_id', 'Channel ID': 'channel_id', 'Currency': 'currency', 'Order TS': 'order_ts', 'Quantity': 'quantity', 'Discount Pct': 'discount_pct', 'Status': 'status', 'Payment Method': 'payment_method'})
import duckdb
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_select_2672903719184.collect() if hasattr(var_select_2672903719184, 'collect') else var_select_2672903719184
duck.register('df_step_0', df_for_duck)
df_for_duck = duck.execute('''SELECT *, 'customers' AS "source_table" FROM df_step_0''').pl()
# Widen DuckDB-native types into Select-supported dtypes
df_for_duck = normalize_to_supported_dtypes(df_for_duck)
# Preserve lazy execution when the incoming value is lazy
var_formula_2675542454224 = df_for_duck.lazy() if hasattr(var_select_2672903719184, 'collect') else df_for_duck
duck.close()
import duckdb
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_select_2675536360976.collect() if hasattr(var_select_2675536360976, 'collect') else var_select_2675536360976
duck.register('df_step_0', df_for_duck)
df_for_duck = duck.execute('''SELECT *, 'products' AS "source_table" FROM df_step_0''').pl()
# Widen DuckDB-native types into Select-supported dtypes
df_for_duck = normalize_to_supported_dtypes(df_for_duck)
# Preserve lazy execution when the incoming value is lazy
var_formula_2675542456144 = df_for_duck.lazy() if hasattr(var_select_2675536360976, 'collect') else df_for_duck
duck.close()
import duckdb
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_select_2675536359696.collect() if hasattr(var_select_2675536359696, 'collect') else var_select_2675536359696
duck.register('df_step_0', df_for_duck)
df_for_duck = duck.execute('''SELECT *, 'suppliers' AS "source_table" FROM df_step_0''').pl()
# Widen DuckDB-native types into Select-supported dtypes
df_for_duck = normalize_to_supported_dtypes(df_for_duck)
# Preserve lazy execution when the incoming value is lazy
var_formula_2675542458064 = df_for_duck.lazy() if hasattr(var_select_2675536359696, 'collect') else df_for_duck
duck.close()
import duckdb
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_select_2675536357296.collect() if hasattr(var_select_2675536357296, 'collect') else var_select_2675536357296
duck.register('df_step_0', df_for_duck)
df_for_duck = duck.execute('''SELECT * REPLACE (LOWER("currency") AS "currency") FROM df_step_0''').pl()
# Widen DuckDB-native types into Select-supported dtypes
df_for_duck = normalize_to_supported_dtypes(df_for_duck)
# Preserve lazy execution when the incoming value is lazy
var_formula_2675541976208 = df_for_duck.lazy() if hasattr(var_select_2675536357296, 'collect') else df_for_duck
duck.close()
from trigger_designer.core.utils.cleansing_util import DataCleansing, NullStrategy
import polars as pl
# Convert LazyFrame to DataFrame if needed
_cleansing_input = var_normalize_columns_2675541972048.collect() if hasattr(var_normalize_columns_2675541972048, 'collect') else var_normalize_columns_2675541972048
cleaner = DataCleansing(_cleansing_input)
cleaner.strip_whitespace(remove_all=False, normalize_spaces=True, fields=['order_id', 'customer_id', 'product_id', 'supplier_id', 'channel_id', 'currency', 'order_ts', 'quantity', 'unit_price_local', 'discount_pct', 'tax_local', 'shipping_local', 'status', 'payment_method', 'is_returned'])
var_cleansing_2675536355376 = cleaner.get_result()
import polars as pl
_union_inputs_2675542513040 = [var_formula_2675542456144, var_formula_2675542454224]
var_union_2675542513040 = pl.concat([(f.lazy() if isinstance(f, pl.DataFrame) else f) for f in _union_inputs_2675542513040], how='diagonal_relaxed')
del _union_inputs_2675542513040
import duckdb
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_formula_2675541976208.collect() if hasattr(var_formula_2675541976208, 'collect') else var_formula_2675541976208
duck.register('df_step_0', df_for_duck)
df_for_duck = duck.execute('''SELECT *, 'fx_rates' AS "source_table" FROM df_step_0''').pl()
# Widen DuckDB-native types into Select-supported dtypes
df_for_duck = normalize_to_supported_dtypes(df_for_duck)
# Preserve lazy execution when the incoming value is lazy
var_formula_2675542511120 = df_for_duck.lazy() if hasattr(var_formula_2675541976208, 'collect') else df_for_duck
duck.close()
from trigger_designer.core.utils.cleansing_util import DataCleansing, NullStrategy
import polars as pl
# Convert LazyFrame to DataFrame if needed
_cleansing_input = var_cleansing_2675536355376.collect() if hasattr(var_cleansing_2675536355376, 'collect') else var_cleansing_2675536355376
cleaner = DataCleansing(_cleansing_input)
cleaner.strip_whitespace(remove_all=False, normalize_spaces=True, fields=['order_id', 'currency', 'status', 'payment_method'])
cleaner.modify_case('lower', fields=['order_id', 'currency', 'status', 'payment_method'])
var_cleansing_2675542266640 = cleaner.get_result()
import polars as pl
_union_inputs_2675542515120 = [var_union_2675542513040, var_formula_2675542458064]
var_union_2675542515120 = pl.concat([(f.lazy() if isinstance(f, pl.DataFrame) else f) for f in _union_inputs_2675542515120], how='diagonal_relaxed')
del _union_inputs_2675542515120
from trigger_designer.core.utils.cleansing_util import DataCleansing, NullStrategy
import polars as pl
# Convert LazyFrame to DataFrame if needed
_cleansing_input = var_cleansing_2675542266640.collect() if hasattr(var_cleansing_2675542266640, 'collect') else var_cleansing_2675542266640
cleaner = DataCleansing(_cleansing_input)
cleaner.remove_rows_with_nulls(fields=['order_id', 'customer_id', 'product_id'])
cleaner.modify_case('lower', fields=['order_id', 'customer_id', 'product_id'])
var_cleansing_2675536354256 = cleaner.get_result()
import polars as pl
_union_inputs_2675542517200 = [var_formula_2675542509200, var_union_2675542515120]
var_union_2675542517200 = pl.concat([(f.lazy() if isinstance(f, pl.DataFrame) else f) for f in _union_inputs_2675542517200], how='diagonal_relaxed')
del _union_inputs_2675542517200
# Filter data into true and false results
var_t_filter_2675536347216 = var_cleansing_2675536354256.filter(pl.col('quantity').is_between(1.0, 500.0, closed='both'))
var_f_filter_2675536347216 = var_cleansing_2675536354256.filter(~(pl.col('quantity').is_between(1.0, 500.0, closed='both')))
import polars as pl
_union_inputs_2675542519280 = [var_union_2675542517200, var_formula_2675542511120]
var_union_2675542519280 = pl.concat([(f.lazy() if isinstance(f, pl.DataFrame) else f) for f in _union_inputs_2675542519280], how='diagonal_relaxed')
del _union_inputs_2675542519280
import duckdb
import polars as pl
# Filter rows with a SQL WHERE clause (no new columns)
df_for_duck = var_t_filter_2675536347216.collect() if hasattr(var_t_filter_2675536347216, 'collect') else var_t_filter_2675536347216
duck = duckdb.connect(':memory:')
duck.register('df_filter', df_for_duck)
var_t_filter_2675541967568 = duck.execute('SELECT * FROM df_filter WHERE "unit_price_local" > 0 and \n"unit_price_local" <= 5000').pl()
var_f_filter_2675541967568 = duck.execute('SELECT * FROM df_filter WHERE NOT ("unit_price_local" > 0 and \n"unit_price_local" <= 5000)').pl()
# Preserve lazy execution when the incoming value is lazy
var_t_filter_2675541967568 = var_t_filter_2675541967568.lazy() if hasattr(var_t_filter_2675536347216, 'collect') else var_t_filter_2675541967568
var_f_filter_2675541967568 = var_f_filter_2675541967568.lazy() if hasattr(var_t_filter_2675536347216, 'collect') else var_f_filter_2675541967568
duck.close()
# Ensure we're working with a LazyFrame for memory efficiency
if var_f_filter_2675536347216 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_f_filter_2675536347216, pl.DataFrame):
        var_f_filter_2675536347216_lazy = var_f_filter_2675536347216.lazy()
    elif isinstance(var_f_filter_2675536347216, pl.LazyFrame):
        var_f_filter_2675536347216_lazy = var_f_filter_2675536347216
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_f_filter_2675536347216)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_f_filter_2675536347216_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/rejected_quantity.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/rejected_quantity.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
# Ensure we're working with a LazyFrame for memory efficiency
if var_union_2675542519280 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_union_2675542519280, pl.DataFrame):
        var_union_2675542519280_lazy = var_union_2675542519280.lazy()
    elif isinstance(var_union_2675542519280, pl.LazyFrame):
        var_union_2675542519280_lazy = var_union_2675542519280
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_union_2675542519280)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_union_2675542519280_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/reference_data_union.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/reference_data_union.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
import duckdb
import polars as pl
# Filter rows with a SQL WHERE clause (no new columns)
df_for_duck = var_t_filter_2675541967568.collect() if hasattr(var_t_filter_2675541967568, 'collect') else var_t_filter_2675541967568
duck = duckdb.connect(':memory:')
duck.register('df_filter', df_for_duck)
var_t_filter_2675541969808 = duck.execute('SELECT * FROM df_filter WHERE YEAR("order_ts") <= 2025').pl()
var_f_filter_2675541969808 = duck.execute('SELECT * FROM df_filter WHERE NOT (YEAR("order_ts") <= 2025)').pl()
# Preserve lazy execution when the incoming value is lazy
var_t_filter_2675541969808 = var_t_filter_2675541969808.lazy() if hasattr(var_t_filter_2675541967568, 'collect') else var_t_filter_2675541969808
var_f_filter_2675541969808 = var_f_filter_2675541969808.lazy() if hasattr(var_t_filter_2675541967568, 'collect') else var_f_filter_2675541969808
duck.close()
# Ensure we're working with a LazyFrame for memory efficiency
if var_f_filter_2675541967568 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_f_filter_2675541967568, pl.DataFrame):
        var_f_filter_2675541967568_lazy = var_f_filter_2675541967568.lazy()
    elif isinstance(var_f_filter_2675541967568, pl.LazyFrame):
        var_f_filter_2675541967568_lazy = var_f_filter_2675541967568
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_f_filter_2675541967568)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_f_filter_2675541967568_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/rejected_price_outliers.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/rejected_price_outliers.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
import polars as pl
# Split into unique and duplicate records based on: order_id
var_unique_2675541973968 = var_t_filter_2675541969808.unique(subset=["order_id"], maintain_order=True)
var_duplicate_2675541973968 = var_t_filter_2675541969808.filter(pl.struct(["order_id"]).is_duplicated())
# Ensure we're working with a LazyFrame for memory efficiency
if var_f_filter_2675541969808 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_f_filter_2675541969808, pl.DataFrame):
        var_f_filter_2675541969808_lazy = var_f_filter_2675541969808.lazy()
    elif isinstance(var_f_filter_2675541969808, pl.LazyFrame):
        var_f_filter_2675541969808_lazy = var_f_filter_2675541969808
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_f_filter_2675541969808)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_f_filter_2675541969808_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/rejected_future_dates.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/rejected_future_dates.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
var_select_2675542268560 = var_unique_2675541973968.select(['order_id', 'customer_id', 'product_id', 'supplier_id', 'channel_id', 'currency', 'order_ts', 'quantity', 'unit_price_local', 'discount_pct', 'tax_local', 'shipping_local', 'status', 'payment_method', 'is_returned'])
# Ensure we're working with a LazyFrame for memory efficiency
if var_unique_2675541973968 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_unique_2675541973968, pl.DataFrame):
        var_unique_2675541973968_lazy = var_unique_2675541973968.lazy()
    elif isinstance(var_unique_2675541973968, pl.LazyFrame):
        var_unique_2675541973968_lazy = var_unique_2675541973968
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_unique_2675541973968)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_unique_2675541973968_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/04 dropped null key rows.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/04 dropped null key rows.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
# Ensure we're working with a LazyFrame for memory efficiency
if var_duplicate_2675541973968 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_duplicate_2675541973968, pl.DataFrame):
        var_duplicate_2675541973968_lazy = var_duplicate_2675541973968.lazy()
    elif isinstance(var_duplicate_2675541973968, pl.LazyFrame):
        var_duplicate_2675541973968_lazy = var_duplicate_2675541973968
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_duplicate_2675541973968)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_duplicate_2675541973968_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/duplicate_orders.csv')
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

_left_input = _ensure_lazyframe(var_select_2675542268560)
_right_input = _ensure_lazyframe(var_select_2672903719184)

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
var_join_2675541978128 = _join_result.filter(
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
    'loyalty_tier',
    'region',
    'segment',
    'signup_date',
    'customer_name'
])

# Extract left-only data efficiently
_left_cols = ['order_id', 'customer_id', 'product_id', 'supplier_id', 'channel_id', 'currency', 'order_ts', 'quantity', 'unit_price_local', 'discount_pct', 'tax_local', 'shipping_local', 'status', 'payment_method', 'is_returned']
var_l_join_2675541978128 = _join_result.filter(
    pl.col('__right_present').is_null()
).select(_left_cols)

# Extract right-only data efficiently
_right_cols = ['customer_id', 'customer_email', 'customer_name', 'signup_date', 'customer_country', 'region', 'customer_currency', 'segment', 'customer_age_band', 'loyalty_tier']
var_r_join_2675541978128 = _join_result.filter(
    pl.col('__left_present').is_null()
).select(_right_cols)

# Clean up temporary variables
del _left_input, _right_input, _left_tagged, _right_tagged, _join_result, _left_cols, _right_cols
# Ensure we're working with a LazyFrame for memory efficiency
if var_l_join_2675541978128 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_l_join_2675541978128, pl.DataFrame):
        var_l_join_2675541978128_lazy = var_l_join_2675541978128.lazy()
    elif isinstance(var_l_join_2675541978128, pl.LazyFrame):
        var_l_join_2675541978128_lazy = var_l_join_2675541978128
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_l_join_2675541978128)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_l_join_2675541978128_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/orphan_customers.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/orphan_customers.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
import polars as pl
_union_inputs_2675541882544 = [var_join_2675541978128, var_l_join_2675541978128]
var_union_2675541882544 = pl.concat([(f.lazy() if isinstance(f, pl.DataFrame) else f) for f in _union_inputs_2675541882544], how='diagonal_relaxed')
del _union_inputs_2675541882544
# Polars LazyFrame Join Operation
import polars as pl

def _ensure_lazyframe(data):
    if isinstance(data, pl.DataFrame):
        return data.lazy()
    if isinstance(data, pl.LazyFrame):
        return data
    raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(data)}')

_left_input = _ensure_lazyframe(var_union_2675541882544)
_right_input = _ensure_lazyframe(var_select_2675536360976)

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
var_join_2675541981168 = _join_result.filter(
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
    'unit_price',
    'customer_name'
])

# Extract left-only data efficiently
_left_cols = ['channel_id', 'currency', 'customer_id', 'discount_pct', 'is_returned', 'order_id', 'order_ts', 'payment_method', 'product_id', 'quantity', 'shipping_local', 'status', 'supplier_id', 'tax_local', 'unit_price_local', 'customer_age_band', 'customer_country', 'customer_currency', 'customer_email', 'loyalty_tier', 'region', 'segment', 'signup_date', 'customer_name']
var_l_join_2675541981168 = _join_result.filter(
    pl.col('__right_present').is_null()
).select(_left_cols)

# Extract right-only data efficiently
_right_cols = ['product_id', 'sku', 'product_name', 'category', 'subcategory', 'brand', 'unit_price', 'unit_cost', 'launch_date']
var_r_join_2675541981168 = _join_result.filter(
    pl.col('__left_present').is_null()
).select(_right_cols)

# Clean up temporary variables
del _left_input, _right_input, _left_tagged, _right_tagged, _join_result, _left_cols, _right_cols
# Ensure we're working with a LazyFrame for memory efficiency
if var_union_2675541882544 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_union_2675541882544, pl.DataFrame):
        var_union_2675541882544_lazy = var_union_2675541882544.lazy()
    elif isinstance(var_union_2675541882544, pl.LazyFrame):
        var_union_2675541882544_lazy = var_union_2675541882544
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_union_2675541882544)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_union_2675541882544_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/01 enriched customer_id.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/01 enriched customer_id.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
# Ensure we're working with a LazyFrame for memory efficiency
if var_l_join_2675541981168 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_l_join_2675541981168, pl.DataFrame):
        var_l_join_2675541981168_lazy = var_l_join_2675541981168.lazy()
    elif isinstance(var_l_join_2675541981168, pl.LazyFrame):
        var_l_join_2675541981168_lazy = var_l_join_2675541981168
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_l_join_2675541981168)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_l_join_2675541981168_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/orphan_products.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/orphan_products.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
import polars as pl
_union_inputs_2675541884624 = [var_join_2675541981168, var_l_join_2675541981168]
var_union_2675541884624 = pl.concat([(f.lazy() if isinstance(f, pl.DataFrame) else f) for f in _union_inputs_2675541884624], how='diagonal_relaxed')
del _union_inputs_2675541884624
# Polars LazyFrame Join Operation
import polars as pl

def _ensure_lazyframe(data):
    if isinstance(data, pl.DataFrame):
        return data.lazy()
    if isinstance(data, pl.LazyFrame):
        return data
    raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(data)}')

_left_input = _ensure_lazyframe(var_union_2675541884624)
_right_input = _ensure_lazyframe(var_select_2675536359696)

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
var_join_2675541869584 = _join_result.filter(
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
    'supplier_name',
    'customer_name'
])

# Extract left-only data efficiently
_left_cols = ['channel_id', 'currency', 'customer_age_band', 'customer_country', 'customer_currency', 'customer_email', 'customer_id', 'discount_pct', 'is_returned', 'loyalty_tier', 'order_id', 'order_ts', 'payment_method', 'product_id', 'quantity', 'region', 'segment', 'shipping_local', 'signup_date', 'status', 'supplier_id', 'tax_local', 'unit_price_local', 'brand', 'category', 'launch_date', 'product_name', 'sku', 'subcategory', 'unit_cost', 'unit_price', 'customer_name']
var_l_join_2675541869584 = _join_result.filter(
    pl.col('__right_present').is_null()
).select(_left_cols)

# Extract right-only data efficiently
_right_cols = ['supplier_id', 'supplier_name', 'country', 'lead_time_days', 'reliability_score']
var_r_join_2675541869584 = _join_result.filter(
    pl.col('__left_present').is_null()
).select(_right_cols)

# Clean up temporary variables
del _left_input, _right_input, _left_tagged, _right_tagged, _join_result, _left_cols, _right_cols
# Ensure we're working with a LazyFrame for memory efficiency
if var_union_2675541884624 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_union_2675541884624, pl.DataFrame):
        var_union_2675541884624_lazy = var_union_2675541884624.lazy()
    elif isinstance(var_union_2675541884624, pl.LazyFrame):
        var_union_2675541884624_lazy = var_union_2675541884624
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_union_2675541884624)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_union_2675541884624_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/02 enriched product_id.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/02 enriched product_id.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
import polars as pl
_union_inputs_2675541755696 = [var_join_2675541869584, var_l_join_2675541869584]
var_union_2675541755696 = pl.concat([(f.lazy() if isinstance(f, pl.DataFrame) else f) for f in _union_inputs_2675541755696], how='diagonal_relaxed')
del _union_inputs_2675541755696
# Polars LazyFrame Join Operation
import polars as pl

def _ensure_lazyframe(data):
    if isinstance(data, pl.DataFrame):
        return data.lazy()
    if isinstance(data, pl.LazyFrame):
        return data
    raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(data)}')

_left_input = _ensure_lazyframe(var_union_2675541755696)
_right_input = _ensure_lazyframe(var_select_2675535888784)

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
var_join_2675541872624 = _join_result.filter(
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
_left_cols = ['brand', 'category', 'channel_id', 'currency', 'customer_age_band', 'customer_country', 'customer_currency', 'customer_email', 'customer_id', 'discount_pct', 'is_returned', 'launch_date', 'loyalty_tier', 'order_id', 'order_ts', 'payment_method', 'product_id', 'product_name', 'quantity', 'region', 'segment', 'shipping_local', 'signup_date', 'sku', 'status', 'subcategory', 'supplier_id', 'tax_local', 'unit_cost', 'unit_price', 'unit_price_local', 'country', 'lead_time_days', 'reliability_score', 'supplier_name', 'customer_name']
var_l_join_2675541872624 = _join_result.filter(
    pl.col('__right_present').is_null()
).select(_left_cols)

# Extract right-only data efficiently
_right_cols = ['channel_id', 'channel_name', 'channel_group', 'is_digital']
var_r_join_2675541872624 = _join_result.filter(
    pl.col('__left_present').is_null()
).select(_right_cols)

# Clean up temporary variables
del _left_input, _right_input, _left_tagged, _right_tagged, _join_result, _left_cols, _right_cols
# Ensure we're working with a LazyFrame for memory efficiency
if var_union_2675541755696 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_union_2675541755696, pl.DataFrame):
        var_union_2675541755696_lazy = var_union_2675541755696.lazy()
    elif isinstance(var_union_2675541755696, pl.LazyFrame):
        var_union_2675541755696_lazy = var_union_2675541755696
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_union_2675541755696)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_union_2675541755696_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/03 enriched supplier_id.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/03 enriched supplier_id.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
import polars as pl
_union_inputs_2675541757776 = [var_join_2675541872624, var_l_join_2675541872624]
var_union_2675541757776 = pl.concat([(f.lazy() if isinstance(f, pl.DataFrame) else f) for f in _union_inputs_2675541757776], how='diagonal_relaxed')
del _union_inputs_2675541757776
# Polars LazyFrame Join Operation
import polars as pl

def _ensure_lazyframe(data):
    if isinstance(data, pl.DataFrame):
        return data.lazy()
    if isinstance(data, pl.LazyFrame):
        return data
    raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(data)}')

_left_input = _ensure_lazyframe(var_union_2675541757776)
_right_input = _ensure_lazyframe(var_formula_2675541976208)

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
var_join_2675541875664 = _join_result.filter(
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
_left_cols = ['brand', 'category', 'channel_id', 'country', 'currency', 'customer_age_band', 'customer_country', 'customer_currency', 'customer_email', 'customer_id', 'discount_pct', 'is_returned', 'launch_date', 'lead_time_days', 'loyalty_tier', 'order_id', 'order_ts', 'payment_method', 'product_id', 'product_name', 'quantity', 'region', 'reliability_score', 'segment', 'shipping_local', 'signup_date', 'sku', 'status', 'subcategory', 'supplier_id', 'supplier_name', 'tax_local', 'unit_cost', 'unit_price', 'unit_price_local', 'channel_group', 'channel_name', 'is_digital', 'customer_name']
var_l_join_2675541875664 = _join_result.filter(
    pl.col('__right_present').is_null()
).select(_left_cols)

# Extract right-only data efficiently
_right_cols = ['currency', 'currency_name', 'usd_rate']
var_r_join_2675541875664 = _join_result.filter(
    pl.col('__left_present').is_null()
).select(_right_cols)

# Clean up temporary variables
del _left_input, _right_input, _left_tagged, _right_tagged, _join_result, _left_cols, _right_cols
# Ensure we're working with a LazyFrame for memory efficiency
if var_union_2675541757776 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_union_2675541757776, pl.DataFrame):
        var_union_2675541757776_lazy = var_union_2675541757776.lazy()
    elif isinstance(var_union_2675541757776, pl.LazyFrame):
        var_union_2675541757776_lazy = var_union_2675541757776
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_union_2675541757776)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_union_2675541757776_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/04 enriched channel_id.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/04 enriched channel_id.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
import polars as pl
_union_inputs_2675541759856 = [var_join_2675541875664, var_l_join_2675541875664]
var_union_2675541759856 = pl.concat([(f.lazy() if isinstance(f, pl.DataFrame) else f) for f in _union_inputs_2675541759856], how='diagonal_relaxed')
del _union_inputs_2675541759856
import duckdb
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_union_2675541759856.collect() if hasattr(var_union_2675541759856, 'collect') else var_union_2675541759856
duck.register('df_step_0', df_for_duck)
df_for_duck = duck.execute('''SELECT *, "quantity" * "unit_price_local" AS "g" FROM df_step_0''').pl()
duck.register('df_step_1', df_for_duck)
df_for_duck = duck.execute('''SELECT *, ROUND("g", 2) AS "gross_local" FROM df_step_1''').pl()
duck.register('df_step_2', df_for_duck)
df_for_duck = duck.execute('''SELECT *, ROUND("gross_local" * "discount_pct", 2) AS "discount_local" FROM df_step_2''').pl()
duck.register('df_step_3', df_for_duck)
df_for_duck = duck.execute('''SELECT *, ROUND("gross_local" - "discount_local", 2) AS "net_local" FROM df_step_3''').pl()
duck.register('df_step_4', df_for_duck)
df_for_duck = duck.execute('''SELECT *, ROUND("net_local" + "tax_local" + "shipping_local", 2) AS "total_local" FROM df_step_4''').pl()
# Widen DuckDB-native types into Select-supported dtypes
df_for_duck = normalize_to_supported_dtypes(df_for_duck)
# Preserve lazy execution when the incoming value is lazy
var_formula_2675541878704 = df_for_duck.lazy() if hasattr(var_union_2675541759856, 'collect') else df_for_duck
duck.close()
# Ensure we're working with a LazyFrame for memory efficiency
if var_union_2675541759856 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_union_2675541759856, pl.DataFrame):
        var_union_2675541759856_lazy = var_union_2675541759856.lazy()
    elif isinstance(var_union_2675541759856, pl.LazyFrame):
        var_union_2675541759856_lazy = var_union_2675541759856
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_union_2675541759856)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_union_2675541759856_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/05 enriched currency.csv')
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
df_for_duck = var_formula_2675541878704.collect() if hasattr(var_formula_2675541878704, 'collect') else var_formula_2675541878704
duck.register('df_step_0', df_for_duck)
df_for_duck = duck.execute('''SELECT *, ROUND("unit_price_local" * "usd_rate", 2) AS "unit_price_usd" FROM df_step_0''').pl()
duck.register('df_step_1', df_for_duck)
df_for_duck = duck.execute('''SELECT *, ROUND("net_local" * "usd_rate", 2) AS "net_revenue_usd" FROM df_step_1''').pl()
duck.register('df_step_2', df_for_duck)
df_for_duck = duck.execute('''SELECT *, ROUND("tax_local" * "usd_rate", 2) AS "tax_usd" FROM df_step_2''').pl()
duck.register('df_step_3', df_for_duck)
df_for_duck = duck.execute('''SELECT *, ROUND("shipping_local" * "usd_rate", 2) AS "shipping_usd" FROM df_step_3''').pl()
duck.register('df_step_4', df_for_duck)
df_for_duck = duck.execute('''SELECT *, ROUND("total_local" * "usd_rate", 2) AS "total_usd" FROM df_step_4''').pl()
# Widen DuckDB-native types into Select-supported dtypes
df_for_duck = normalize_to_supported_dtypes(df_for_duck)
# Preserve lazy execution when the incoming value is lazy
var_formula_2675541880624 = df_for_duck.lazy() if hasattr(var_formula_2675541878704, 'collect') else df_for_duck
duck.close()
import duckdb
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_formula_2675541880624.collect() if hasattr(var_formula_2675541880624, 'collect') else var_formula_2675541880624
duck.register('df_step_0', df_for_duck)
df_for_duck = duck.execute('''SELECT *, ROUND("quantity" * "unit_cost", 2) AS "cogs_usd" FROM df_step_0''').pl()
duck.register('df_step_1', df_for_duck)
df_for_duck = duck.execute('''SELECT *, ROUND("net_revenue_usd" - "cogs_usd", 2) AS "gross_margin_usd" FROM df_step_1''').pl()
duck.register('df_step_2', df_for_duck)
df_for_duck = duck.execute('''SELECT *, ROUND(CASE
    WHEN "net_revenue_usd" IS NULL OR "net_revenue_usd" = 0 THEN NULL
    ELSE "gross_margin_usd" / "net_revenue_usd"
END, 4) AS "margin_pct" FROM df_step_2''').pl()
# Widen DuckDB-native types into Select-supported dtypes
df_for_duck = normalize_to_supported_dtypes(df_for_duck)
# Preserve lazy execution when the incoming value is lazy
var_formula_2675541761936 = df_for_duck.lazy() if hasattr(var_formula_2675541880624, 'collect') else df_for_duck
duck.close()
import duckdb
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_formula_2675541761936.collect() if hasattr(var_formula_2675541761936, 'collect') else var_formula_2675541761936
duck.register('df_step_0', df_for_duck)
df_for_duck = duck.execute('''SELECT *, YEAR("order_ts") AS "order_year" FROM df_step_0''').pl()
duck.register('df_step_1', df_for_duck)
df_for_duck = duck.execute('''SELECT *, MONTH("order_ts") AS "order_month" FROM df_step_1''').pl()
duck.register('df_step_2', df_for_duck)
df_for_duck = duck.execute('''SELECT *, STRFTIME("order_ts", '%Y-%m') AS "order_year_month" FROM df_step_2''').pl()
duck.register('df_step_3', df_for_duck)
df_for_duck = duck.execute('''SELECT *, "quantity" >= 6 AS "is_bulk" FROM df_step_3''').pl()
duck.register('df_step_4', df_for_duck)
df_for_duck = duck.execute('''SELECT *, CASE
    WHEN "net_revenue_usd" IS NULL THEN NULL
    WHEN "net_revenue_usd" <= 250  THEN 'Low'
    WHEN "net_revenue_usd" <= 1000 THEN 'Medium'
    ELSE 'High'
END
 AS "value_band" FROM df_step_4''').pl()
# Widen DuckDB-native types into Select-supported dtypes
df_for_duck = normalize_to_supported_dtypes(df_for_duck)
# Preserve lazy execution when the incoming value is lazy
var_formula_2675541763856 = df_for_duck.lazy() if hasattr(var_formula_2675541761936, 'collect') else df_for_duck
duck.close()
import duckdb
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_formula_2675541763856.collect() if hasattr(var_formula_2675541763856, 'collect') else var_formula_2675541763856
duck.register('df_step_0', df_for_duck)
df_for_duck = duck.execute('''SELECT * REPLACE (CASE WHEN LOWER("is_returned") = 'true' THEN true ELSE false END AS "is_returned") FROM df_step_0''').pl()
duck.register('df_step_1', df_for_duck)
df_for_duck = duck.execute('''SELECT *, (CASE WHEN "is_returned" THEN 2 ELSE 0 END)
+ (CASE WHEN "status" IN ('refunded', 'cancelled') THEN 2 ELSE 0 END)
+ (CASE WHEN "net_revenue_usd" > 2000 THEN 1 ELSE 0 END)
+ (CASE WHEN "margin_pct" < 0.10 THEN 1 ELSE 0 END)
+ (CASE WHEN "segment" IS NULL THEN 2 ELSE 0 END)
 AS "risk_score" FROM df_step_1''').pl()
duck.register('df_step_2', df_for_duck)
df_for_duck = duck.execute('''SELECT *, CASE
    WHEN "risk_score" >= 4 THEN 'High'
    WHEN "risk_score" >= 2 THEN 'Medium'
    ELSE 'Low'
END AS "risk_band" FROM df_step_2''').pl()
duck.register('df_step_3', df_for_duck)
df_for_duck = duck.execute('''SELECT *, CASE "status" WHEN 'paid' THEN 'Paid'
  WHEN 'pending' THEN 'Pending'
  WHEN 'refunded' THEN 'Refunded'
  WHEN 'cancelled' THEN 'Cancelled'
  WHEN 'partially refunded' THEN 'Partially Refunded'
  ELSE "status" END AS "status_clean" FROM df_step_3''').pl()
# Widen DuckDB-native types into Select-supported dtypes
df_for_duck = normalize_to_supported_dtypes(df_for_duck)
# Preserve lazy execution when the incoming value is lazy
var_formula_2675541765776 = df_for_duck.lazy() if hasattr(var_formula_2675541763856, 'collect') else df_for_duck
duck.close()
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
var_groupby_2675541769616 = var_formula_2675541765776.group_by(['order_year_month']).agg([
    pl.col('net_revenue_usd').sum().alias('revenue_usd'),
    pl.col('gross_margin_usd').sum().alias('margin_usd'),
    pl.col('order_id').n_unique().alias('orders')
])
var_groupby_2675541769616 = normalize_to_supported_dtypes(var_groupby_2675541769616)
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
var_groupby_2675541684176 = var_formula_2675541765776.group_by(['category']).agg([
    pl.col('net_revenue_usd').sum().alias('revenue_usd'),
    pl.col('gross_margin_usd').sum().alias('margin_usd'),
    pl.col('order_id').n_unique().alias('orders')
])
var_groupby_2675541684176 = normalize_to_supported_dtypes(var_groupby_2675541684176)
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
var_groupby_2675541611280 = var_formula_2675541765776.group_by(['region', 'channel_group']).agg([
    pl.col('net_revenue_usd').sum().alias('revenue_usd'),
    pl.col('gross_margin_usd').sum().alias('margin_usd'),
    pl.col('order_id').n_unique().alias('orders')
])
var_groupby_2675541611280 = normalize_to_supported_dtypes(var_groupby_2675541611280)
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
var_groupby_2675541613200 = var_formula_2675541765776.group_by(['segment', 'risk_band']).agg([
    pl.col('net_revenue_usd').sum().alias('revenue_usd'),
    pl.col('gross_margin_usd').sum().alias('margin_usd'),
    pl.col('order_id').n_unique().alias('orders')
])
var_groupby_2675541613200 = normalize_to_supported_dtypes(var_groupby_2675541613200)
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
var_groupby_2675541615120 = var_formula_2675541765776.group_by(['customer_id']).agg([
    pl.col('net_revenue_usd').sum().alias('revenue_usd'),
    pl.col('order_id').n_unique().alias('orders')
])
var_groupby_2675541615120 = normalize_to_supported_dtypes(var_groupby_2675541615120)
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
var_groupby_2675541509776 = var_formula_2675541765776.group_by(['supplier_id', 'supplier_name', 'country']).agg([
    pl.col('net_revenue_usd').sum().alias('revenue_usd'),
    pl.col('order_id').n_unique().alias('orders'),
    pl.col('lead_time_days').first().alias('lead_time_days'),
    pl.col('reliability_score').first().alias('reliability_score')
])
var_groupby_2675541509776 = normalize_to_supported_dtypes(var_groupby_2675541509776)
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
var_groupby_2675541519056 = var_formula_2675541765776.group_by(['currency']).agg([
    pl.col('net_revenue_usd').sum().alias('revenue_usd'),
    pl.col('order_id').n_unique().alias('orders'),
    pl.col('usd_rate').first().alias('usd_rate')
])
var_groupby_2675541519056 = normalize_to_supported_dtypes(var_groupby_2675541519056)
var_select_2675542103760 = var_formula_2675541765776.select(['brand', 'category', 'channel_group', 'channel_id', 'channel_name', 'country', 'currency', 'customer_age_band', 'customer_country', 'customer_currency', 'customer_email', 'customer_id', 'discount_pct', 'is_digital', 'is_returned', 'launch_date', 'lead_time_days', 'loyalty_tier', 'order_id', 'order_ts', 'payment_method', 'product_id', 'product_name', 'quantity', 'region', 'reliability_score', 'segment', 'shipping_local', 'signup_date', 'sku', 'status', 'subcategory', 'supplier_id', 'supplier_name', 'tax_local', 'unit_cost', 'unit_price', 'unit_price_local', 'currency_name', 'usd_rate', 'g', 'gross_local', 'discount_local', 'net_local', 'total_local', 'unit_price_usd', 'net_revenue_usd', 'tax_usd', 'shipping_usd', 'total_usd', 'cogs_usd', 'gross_margin_usd', 'margin_pct', 'order_year', 'order_month', 'order_year_month', 'is_bulk', 'value_band', 'risk_score', 'risk_band', 'customer_name', 'status_clean'])
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('brand').cast(pl.String, strict=False).alias('brand')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('category').cast(pl.String, strict=False).alias('category')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('channel_group').cast(pl.String, strict=False).alias('channel_group')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('channel_id').cast(pl.Int64, strict=False).alias('channel_id')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('channel_name').cast(pl.String, strict=False).alias('channel_name')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('country').cast(pl.String, strict=False).alias('country')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('currency').cast(pl.String, strict=False).alias('currency')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('customer_age_band').cast(pl.String, strict=False).alias('customer_age_band')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('customer_country').cast(pl.String, strict=False).alias('customer_country')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('customer_currency').cast(pl.String, strict=False).alias('customer_currency')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('customer_email').cast(pl.String, strict=False).alias('customer_email')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('customer_id').cast(pl.Int64, strict=False).alias('customer_id')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('discount_pct').cast(pl.Float64, strict=False).alias('discount_pct')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.when(pl.col('is_digital').cast(pl.String, strict=False).str.to_lowercase().str.strip_chars().is_in(('true', '1', 'yes', 'y', 't', 'on'))).then(True)
    .when(pl.col('is_digital').cast(pl.String, strict=False).str.to_lowercase().str.strip_chars().is_in(('false', '0', 'no', 'n', 'f', 'off'))).then(False)
    .when(pl.col('is_digital').cast(pl.Float64, strict=False).is_not_null() & (pl.col('is_digital').cast(pl.Float64, strict=False) != 0.0)).then(True)
    .when(pl.col('is_digital').cast(pl.Float64, strict=False).is_not_null()).then(False)
    .otherwise(None)
    .alias('is_digital')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.when(pl.col('is_returned').cast(pl.String, strict=False).str.to_lowercase().str.strip_chars().is_in(('true', '1', 'yes', 'y', 't', 'on'))).then(True)
    .when(pl.col('is_returned').cast(pl.String, strict=False).str.to_lowercase().str.strip_chars().is_in(('false', '0', 'no', 'n', 'f', 'off'))).then(False)
    .when(pl.col('is_returned').cast(pl.Float64, strict=False).is_not_null() & (pl.col('is_returned').cast(pl.Float64, strict=False) != 0.0)).then(True)
    .when(pl.col('is_returned').cast(pl.Float64, strict=False).is_not_null()).then(False)
    .otherwise(None)
    .alias('is_returned')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
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
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('lead_time_days').cast(pl.Int64, strict=False).alias('lead_time_days')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('loyalty_tier').cast(pl.String, strict=False).alias('loyalty_tier')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('order_id').cast(pl.String, strict=False).alias('order_id')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('order_ts').cast(pl.String, strict=False).alias('order_ts')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('payment_method').cast(pl.String, strict=False).alias('payment_method')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('product_id').cast(pl.Int64, strict=False).alias('product_id')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('product_name').cast(pl.String, strict=False).alias('product_name')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('quantity').cast(pl.Int64, strict=False).alias('quantity')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('region').cast(pl.String, strict=False).alias('region')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('reliability_score').cast(pl.Float64, strict=False).alias('reliability_score')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('segment').cast(pl.String, strict=False).alias('segment')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('shipping_local').cast(pl.Float64, strict=False).alias('shipping_local')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
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
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('sku').cast(pl.String, strict=False).alias('sku')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('status').cast(pl.String, strict=False).alias('status')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('subcategory').cast(pl.String, strict=False).alias('subcategory')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('supplier_id').cast(pl.Int64, strict=False).alias('supplier_id')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('supplier_name').cast(pl.String, strict=False).alias('supplier_name')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('tax_local').cast(pl.Float64, strict=False).alias('tax_local')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('unit_cost').cast(pl.Float64, strict=False).alias('unit_cost')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('unit_price').cast(pl.Float64, strict=False).alias('unit_price')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('unit_price_local').cast(pl.Float64, strict=False).alias('unit_price_local')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('currency_name').cast(pl.String, strict=False).alias('currency_name')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('usd_rate').cast(pl.Float64, strict=False).alias('usd_rate')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('g').cast(pl.Float64, strict=False).alias('g')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('gross_local').cast(pl.Float64, strict=False).alias('gross_local')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('discount_local').cast(pl.Float64, strict=False).alias('discount_local')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('net_local').cast(pl.Float64, strict=False).alias('net_local')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('total_local').cast(pl.Float64, strict=False).alias('total_local')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('unit_price_usd').cast(pl.Float64, strict=False).alias('unit_price_usd')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('net_revenue_usd').cast(pl.Float64, strict=False).alias('net_revenue_usd')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('tax_usd').cast(pl.Float64, strict=False).alias('tax_usd')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('shipping_usd').cast(pl.Float64, strict=False).alias('shipping_usd')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('total_usd').cast(pl.Float64, strict=False).alias('total_usd')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('cogs_usd').cast(pl.Float64, strict=False).alias('cogs_usd')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('gross_margin_usd').cast(pl.Float64, strict=False).alias('gross_margin_usd')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('margin_pct').cast(pl.Float64, strict=False).alias('margin_pct')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('order_year').cast(pl.Int64, strict=False).alias('order_year')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('order_month').cast(pl.Int64, strict=False).alias('order_month')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('order_year_month').cast(pl.String, strict=False).alias('order_year_month')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.when(pl.col('is_bulk').cast(pl.String, strict=False).str.to_lowercase().str.strip_chars().is_in(('true', '1', 'yes', 'y', 't', 'on'))).then(True)
    .when(pl.col('is_bulk').cast(pl.String, strict=False).str.to_lowercase().str.strip_chars().is_in(('false', '0', 'no', 'n', 'f', 'off'))).then(False)
    .when(pl.col('is_bulk').cast(pl.Float64, strict=False).is_not_null() & (pl.col('is_bulk').cast(pl.Float64, strict=False) != 0.0)).then(True)
    .when(pl.col('is_bulk').cast(pl.Float64, strict=False).is_not_null()).then(False)
    .otherwise(None)
    .alias('is_bulk')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('value_band').cast(pl.String, strict=False).alias('value_band')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('risk_score').cast(pl.Int64, strict=False).alias('risk_score')
)
var_select_2675542103760 = var_select_2675542103760.with_columns(
    pl.col('risk_band').cast(pl.String, strict=False).alias('risk_band')
)
var_select_2675542334736 = var_formula_2675541765776.select(['order_id', 'order_ts', 'order_year', 'order_month', 'order_year_month', 'customer_id', 'product_id', 'supplier_id', 'channel_id', 'channel_name', 'channel_group', 'category', 'subcategory', 'brand', 'customer_country', 'region', 'segment', 'loyalty_tier', 'currency', 'usd_rate', 'status', 'status_clean', 'quantity', 'unit_price_local', 'discount_pct', 'net_local', 'total_local', 'net_revenue_usd', 'cogs_usd', 'gross_margin_usd', 'margin_pct', 'value_band', 'risk_score', 'risk_band', 'is_returned', 'is_bulk', 'country', 'customer_age_band', 'customer_currency', 'customer_email', 'is_digital', 'launch_date', 'lead_time_days', 'payment_method', 'product_name', 'reliability_score', 'shipping_local', 'signup_date', 'sku', 'supplier_name', 'tax_local', 'unit_cost', 'unit_price', 'currency_name', 'customer_name', 'g', 'gross_local', 'discount_local', 'unit_price_usd', 'tax_usd', 'shipping_usd', 'total_usd'])
var_select_2675542334736 = var_select_2675542334736.with_columns(
    pl.col('order_id').cast(pl.String, strict=False).alias('order_id')
)
var_select_2675542334736 = var_select_2675542334736.with_columns(
    pl.coalesce([
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y-%m-%d %H:%M:%S', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y-%m-%d %H:%M', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y-%m-%dT%H:%M:%S', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y-%m-%dT%H:%M', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y/%m/%d %H:%M:%S', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y/%m/%d %H:%M', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y/%m/%dT%H:%M:%S', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y/%m/%dT%H:%M', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y.%m.%d %H:%M:%S', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y.%m.%d %H:%M', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y.%m.%dT%H:%M:%S', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%Y.%m.%dT%H:%M', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%m-%Y %H:%M:%S', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%m-%Y %H:%M', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%m-%YT%H:%M:%S', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%m-%YT%H:%M', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d/%m/%Y %H:%M:%S', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d/%m/%Y %H:%M', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d/%m/%YT%H:%M:%S', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d/%m/%YT%H:%M', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d.%m.%Y %H:%M:%S', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d.%m.%Y %H:%M', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d.%m.%YT%H:%M:%S', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d.%m.%YT%H:%M', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m-%d-%Y %H:%M:%S', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m-%d-%Y %H:%M', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m-%d-%YT%H:%M:%S', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m-%d-%YT%H:%M', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m/%d/%Y %H:%M:%S', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m/%d/%Y %H:%M', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m/%d/%YT%H:%M:%S', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m/%d/%YT%H:%M', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m.%d.%Y %H:%M:%S', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m.%d.%Y %H:%M', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m.%d.%YT%H:%M:%S', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%m.%d.%YT%H:%M', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %b %Y %H:%M:%S', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %b %Y %H:%M', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %b %YT%H:%M:%S', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %b %YT%H:%M', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %B %Y %H:%M:%S', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %B %Y %H:%M', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %B %YT%H:%M:%S', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %B %YT%H:%M', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%b %d %Y %H:%M:%S', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%b %d %Y %H:%M', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%b %d %YT%H:%M:%S', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%b %d %YT%H:%M', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%B %d %Y %H:%M:%S', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%B %d %Y %H:%M', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%B %d %YT%H:%M:%S', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%B %d %YT%H:%M', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%b-%Y %H:%M:%S', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%b-%Y %H:%M', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%b-%YT%H:%M:%S', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%b-%YT%H:%M', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%B-%Y %H:%M:%S', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%B-%Y %H:%M', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%B-%YT%H:%M:%S', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d-%B-%YT%H:%M', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %b %Y %H:%M:%S', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %B %Y %H:%M:%S', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%b %d %Y %H:%M:%S', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%B %d %Y %H:%M:%S', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %b %Y %H:%M', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%d %B %Y %H:%M', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%b %d %Y %H:%M', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Datetime, '%B %d %Y %H:%M', strict=False, exact=True),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Date, '%Y-%m-%d', strict=False, exact=True).cast(pl.Datetime, strict=False),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Date, '%Y/%m/%d', strict=False, exact=True).cast(pl.Datetime, strict=False),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Date, '%Y.%m.%d', strict=False, exact=True).cast(pl.Datetime, strict=False),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Date, '%d-%m-%Y', strict=False, exact=True).cast(pl.Datetime, strict=False),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Date, '%d/%m/%Y', strict=False, exact=True).cast(pl.Datetime, strict=False),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Date, '%d.%m.%Y', strict=False, exact=True).cast(pl.Datetime, strict=False),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Date, '%m-%d-%Y', strict=False, exact=True).cast(pl.Datetime, strict=False),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Date, '%m/%d/%Y', strict=False, exact=True).cast(pl.Datetime, strict=False),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Date, '%m.%d.%Y', strict=False, exact=True).cast(pl.Datetime, strict=False),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Date, '%d %b %Y', strict=False, exact=True).cast(pl.Datetime, strict=False),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Date, '%d %B %Y', strict=False, exact=True).cast(pl.Datetime, strict=False),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Date, '%b %d %Y', strict=False, exact=True).cast(pl.Datetime, strict=False),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Date, '%B %d %Y', strict=False, exact=True).cast(pl.Datetime, strict=False),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Date, '%d-%b-%Y', strict=False, exact=True).cast(pl.Datetime, strict=False),
        pl.col('order_ts').cast(pl.String, strict=False).str.strptime(pl.Date, '%d-%B-%Y', strict=False, exact=True).cast(pl.Datetime, strict=False),
        pl.col('order_ts').cast(pl.String, strict=False).str.to_datetime(strict=False),
        pl.col('order_ts').cast(pl.Datetime, strict=False)
    ]).alias('order_ts')
)
var_select_2675542334736 = var_select_2675542334736.with_columns(
    pl.col('order_year').cast(pl.Int64, strict=False).alias('order_year')
)
var_select_2675542334736 = var_select_2675542334736.with_columns(
    pl.col('order_month').cast(pl.Int64, strict=False).alias('order_month')
)
var_select_2675542334736 = var_select_2675542334736.with_columns(
    pl.col('order_year_month').cast(pl.String, strict=False).alias('order_year_month')
)
var_select_2675542334736 = var_select_2675542334736.with_columns(
    pl.col('customer_id').cast(pl.Int64, strict=False).alias('customer_id')
)
var_select_2675542334736 = var_select_2675542334736.with_columns(
    pl.col('product_id').cast(pl.Int64, strict=False).alias('product_id')
)
var_select_2675542334736 = var_select_2675542334736.with_columns(
    pl.col('supplier_id').cast(pl.Int64, strict=False).alias('supplier_id')
)
var_select_2675542334736 = var_select_2675542334736.with_columns(
    pl.col('channel_id').cast(pl.Int64, strict=False).alias('channel_id')
)
var_select_2675542334736 = var_select_2675542334736.with_columns(
    pl.col('channel_name').cast(pl.String, strict=False).alias('channel_name')
)
var_select_2675542334736 = var_select_2675542334736.with_columns(
    pl.col('channel_group').cast(pl.String, strict=False).alias('channel_group')
)
var_select_2675542334736 = var_select_2675542334736.with_columns(
    pl.col('category').cast(pl.String, strict=False).alias('category')
)
var_select_2675542334736 = var_select_2675542334736.with_columns(
    pl.col('subcategory').cast(pl.String, strict=False).alias('subcategory')
)
var_select_2675542334736 = var_select_2675542334736.with_columns(
    pl.col('brand').cast(pl.String, strict=False).alias('brand')
)
var_select_2675542334736 = var_select_2675542334736.with_columns(
    pl.col('customer_country').cast(pl.String, strict=False).alias('customer_country')
)
var_select_2675542334736 = var_select_2675542334736.with_columns(
    pl.col('region').cast(pl.String, strict=False).alias('region')
)
var_select_2675542334736 = var_select_2675542334736.with_columns(
    pl.col('segment').cast(pl.String, strict=False).alias('segment')
)
var_select_2675542334736 = var_select_2675542334736.with_columns(
    pl.col('loyalty_tier').cast(pl.String, strict=False).alias('loyalty_tier')
)
var_select_2675542334736 = var_select_2675542334736.with_columns(
    pl.col('currency').cast(pl.String, strict=False).alias('currency')
)
var_select_2675542334736 = var_select_2675542334736.with_columns(
    pl.col('usd_rate').cast(pl.Float64, strict=False).alias('usd_rate')
)
var_select_2675542334736 = var_select_2675542334736.with_columns(
    pl.col('status').cast(pl.String, strict=False).alias('status')
)
var_select_2675542334736 = var_select_2675542334736.with_columns(
    pl.col('status_clean').cast(pl.String, strict=False).alias('status_clean')
)
var_select_2675542334736 = var_select_2675542334736.with_columns(
    pl.col('quantity').cast(pl.Int64, strict=False).alias('quantity')
)
var_select_2675542334736 = var_select_2675542334736.with_columns(
    pl.col('unit_price_local').cast(pl.Float64, strict=False).alias('unit_price_local')
)
var_select_2675542334736 = var_select_2675542334736.with_columns(
    pl.col('discount_pct').cast(pl.Float64, strict=False).alias('discount_pct')
)
var_select_2675542334736 = var_select_2675542334736.with_columns(
    pl.col('net_local').cast(pl.Float64, strict=False).alias('net_local')
)
var_select_2675542334736 = var_select_2675542334736.with_columns(
    pl.col('total_local').cast(pl.Float64, strict=False).alias('total_local')
)
var_select_2675542334736 = var_select_2675542334736.with_columns(
    pl.col('net_revenue_usd').cast(pl.Float64, strict=False).alias('net_revenue_usd')
)
var_select_2675542334736 = var_select_2675542334736.with_columns(
    pl.col('cogs_usd').cast(pl.Float64, strict=False).alias('cogs_usd')
)
var_select_2675542334736 = var_select_2675542334736.with_columns(
    pl.col('gross_margin_usd').cast(pl.Float64, strict=False).alias('gross_margin_usd')
)
var_select_2675542334736 = var_select_2675542334736.with_columns(
    pl.col('margin_pct').cast(pl.Float64, strict=False).alias('margin_pct')
)
var_select_2675542334736 = var_select_2675542334736.with_columns(
    pl.col('value_band').cast(pl.String, strict=False).alias('value_band')
)
var_select_2675542334736 = var_select_2675542334736.with_columns(
    pl.col('risk_score').cast(pl.Int64, strict=False).alias('risk_score')
)
var_select_2675542334736 = var_select_2675542334736.with_columns(
    pl.col('risk_band').cast(pl.String, strict=False).alias('risk_band')
)
var_select_2675542334736 = var_select_2675542334736.with_columns(
    pl.when(pl.col('is_returned').cast(pl.String, strict=False).str.to_lowercase().str.strip_chars().is_in(('true', '1', 'yes', 'y', 't', 'on'))).then(True)
    .when(pl.col('is_returned').cast(pl.String, strict=False).str.to_lowercase().str.strip_chars().is_in(('false', '0', 'no', 'n', 'f', 'off'))).then(False)
    .when(pl.col('is_returned').cast(pl.Float64, strict=False).is_not_null() & (pl.col('is_returned').cast(pl.Float64, strict=False) != 0.0)).then(True)
    .when(pl.col('is_returned').cast(pl.Float64, strict=False).is_not_null()).then(False)
    .otherwise(None)
    .alias('is_returned')
)
var_select_2675542334736 = var_select_2675542334736.with_columns(
    pl.when(pl.col('is_bulk').cast(pl.String, strict=False).str.to_lowercase().str.strip_chars().is_in(('true', '1', 'yes', 'y', 't', 'on'))).then(True)
    .when(pl.col('is_bulk').cast(pl.String, strict=False).str.to_lowercase().str.strip_chars().is_in(('false', '0', 'no', 'n', 'f', 'off'))).then(False)
    .when(pl.col('is_bulk').cast(pl.Float64, strict=False).is_not_null() & (pl.col('is_bulk').cast(pl.Float64, strict=False) != 0.0)).then(True)
    .when(pl.col('is_bulk').cast(pl.Float64, strict=False).is_not_null()).then(False)
    .otherwise(None)
    .alias('is_bulk')
)
# Filter data into true and false results
var_t_filter_2675542338256 = var_formula_2675541765776.filter(pl.col('segment') == 'Enterprise')
var_f_filter_2675542338256 = var_formula_2675541765776.filter(~(pl.col('segment') == 'Enterprise'))
# Filter data into true and false results
var_t_filter_2675542342096 = var_formula_2675541765776.filter(pl.col('risk_band') == 'High')
var_f_filter_2675542342096 = var_formula_2675541765776.filter(~(pl.col('risk_band') == 'High'))
import polars as pl
# Random split with seed 42 (row-safe full shuffle)
indexed_df = var_formula_2675541765776.with_row_index('__split_idx').sort(pl.col('__split_idx').shuffle(seed=42))
var_estimation_2675542446064 = indexed_df.filter(pl.col('__split_idx') < pl.col('__split_idx').max() * 0.8).drop('__split_idx')
var_validation_2675542446064 = indexed_df.filter(pl.col('__split_idx') >= pl.col('__split_idx').max() * 0.8).drop('__split_idx')
var_sort_2675541767696 = var_groupby_2675541769616.sort('order_year_month', descending=False)
var_sort_2675541686096 = var_groupby_2675541684176.sort('revenue_usd', descending=True)
var_sort_2675541607760 = var_groupby_2675541611280.sort(['region', 'channel_group'], descending=[False, False])
var_sort_2675542109200 = var_groupby_2675541613200.sort(['segment', 'risk_band'], descending=[False, False])
# Filter data into true and false results
var_t_filter_2675541620560 = var_groupby_2675541615120.filter(pl.col('revenue_usd') > 4000)
var_f_filter_2675541620560 = var_groupby_2675541615120.filter(~(pl.col('revenue_usd') > 4000))
var_sort_2675541511696 = var_groupby_2675541509776.sort('revenue_usd', descending=True)
var_sort_2675541517136 = var_groupby_2675541519056.sort('revenue_usd', descending=True)
import duckdb
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_select_2675542103760.collect() if hasattr(var_select_2675542103760, 'collect') else var_select_2675542103760
duck.register('df_step_0', df_for_duck)
df_for_duck = duck.execute('''SELECT *, "gross_local" * "usd_rate" AS "gross_revenue_usd_raw" FROM df_step_0''').pl()
duck.register('df_step_1', df_for_duck)
df_for_duck = duck.execute('''SELECT *, CASE WHEN "risk_band" = 'High' THEN 1 ELSE 0 END AS "is_high_risk" FROM df_step_1''').pl()
# Widen DuckDB-native types into Select-supported dtypes
df_for_duck = normalize_to_supported_dtypes(df_for_duck)
# Preserve lazy execution when the incoming value is lazy
var_formula_2675542098000 = df_for_duck.lazy() if hasattr(var_select_2675542103760, 'collect') else df_for_duck
duck.close()
# Ensure we're working with a LazyFrame for memory efficiency
if var_select_2675542334736 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_select_2675542334736, pl.DataFrame):
        var_select_2675542334736_lazy = var_select_2675542334736.lazy()
    elif isinstance(var_select_2675542334736, pl.LazyFrame):
        var_select_2675542334736_lazy = var_select_2675542334736
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_select_2675542334736)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_select_2675542334736_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/orders_enriched.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/orders_enriched.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
# Ensure we're working with a LazyFrame for memory efficiency
if var_t_filter_2675542338256 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_t_filter_2675542338256, pl.DataFrame):
        var_t_filter_2675542338256_lazy = var_t_filter_2675542338256.lazy()
    elif isinstance(var_t_filter_2675542338256, pl.LazyFrame):
        var_t_filter_2675542338256_lazy = var_t_filter_2675542338256
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_t_filter_2675542338256)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_t_filter_2675542338256_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/orders_enterprise.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/orders_enterprise.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
# Ensure we're working with a LazyFrame for memory efficiency
if var_t_filter_2675542342096 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_t_filter_2675542342096, pl.DataFrame):
        var_t_filter_2675542342096_lazy = var_t_filter_2675542342096.lazy()
    elif isinstance(var_t_filter_2675542342096, pl.LazyFrame):
        var_t_filter_2675542342096_lazy = var_t_filter_2675542342096
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_t_filter_2675542342096)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_t_filter_2675542342096_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/orders_high_risk.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/orders_high_risk.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
# Ensure we're working with a LazyFrame for memory efficiency
if var_estimation_2675542446064 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_estimation_2675542446064, pl.DataFrame):
        var_estimation_2675542446064_lazy = var_estimation_2675542446064.lazy()
    elif isinstance(var_estimation_2675542446064, pl.LazyFrame):
        var_estimation_2675542446064_lazy = var_estimation_2675542446064
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_estimation_2675542446064)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_estimation_2675542446064_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/fact_estimation.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/fact_estimation.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
# Ensure we're working with a LazyFrame for memory efficiency
if var_validation_2675542446064 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_validation_2675542446064, pl.DataFrame):
        var_validation_2675542446064_lazy = var_validation_2675542446064.lazy()
    elif isinstance(var_validation_2675542446064, pl.LazyFrame):
        var_validation_2675542446064_lazy = var_validation_2675542446064
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_validation_2675542446064)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_validation_2675542446064_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/fact_validation.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/fact_validation.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
var_runtot_2675541673296 = var_sort_2675541767696.with_columns([
    pl.col("revenue_usd").cum_sum().alias("RunTot_revenue_usd")
])
var_runtot_2675541673296 = normalize_to_supported_dtypes(var_runtot_2675541673296)
# Ensure we're working with a LazyFrame for memory efficiency
if var_sort_2675541686096 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_sort_2675541686096, pl.DataFrame):
        var_sort_2675541686096_lazy = var_sort_2675541686096.lazy()
    elif isinstance(var_sort_2675541686096, pl.LazyFrame):
        var_sort_2675541686096_lazy = var_sort_2675541686096
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_sort_2675541686096)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_sort_2675541686096_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/category_revenue.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/category_revenue.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
# Ensure we're working with a LazyFrame for memory efficiency
if var_sort_2675541607760 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_sort_2675541607760, pl.DataFrame):
        var_sort_2675541607760_lazy = var_sort_2675541607760.lazy()
    elif isinstance(var_sort_2675541607760, pl.LazyFrame):
        var_sort_2675541607760_lazy = var_sort_2675541607760
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_sort_2675541607760)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_sort_2675541607760_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/region_channel_revenue.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/region_channel_revenue.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
# Ensure we're working with a LazyFrame for memory efficiency
if var_sort_2675542109200 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_sort_2675542109200, pl.DataFrame):
        var_sort_2675542109200_lazy = var_sort_2675542109200.lazy()
    elif isinstance(var_sort_2675542109200, pl.LazyFrame):
        var_sort_2675542109200_lazy = var_sort_2675542109200
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_sort_2675542109200)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_sort_2675542109200_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/segment_revenue.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/segment_revenue.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
var_sort_2675541618640 = var_t_filter_2675541620560.sort('revenue_usd', descending=True)
import duckdb
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_sort_2675541511696.collect() if hasattr(var_sort_2675541511696, 'collect') else var_sort_2675541511696
duck.register('df_step_0', df_for_duck)
df_for_duck = duck.execute('''SELECT *, "revenue_usd" / "lead_time_days" AS "revenue_per_lead_day" FROM df_step_0''').pl()
# Widen DuckDB-native types into Select-supported dtypes
df_for_duck = normalize_to_supported_dtypes(df_for_duck)
# Preserve lazy execution when the incoming value is lazy
var_formula_2675541513616 = df_for_duck.lazy() if hasattr(var_sort_2675541511696, 'collect') else df_for_duck
duck.close()
# Ensure we're working with a LazyFrame for memory efficiency
if var_sort_2675541517136 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_sort_2675541517136, pl.DataFrame):
        var_sort_2675541517136_lazy = var_sort_2675541517136.lazy()
    elif isinstance(var_sort_2675541517136, pl.LazyFrame):
        var_sort_2675541517136_lazy = var_sort_2675541517136
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_sort_2675541517136)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_sort_2675541517136_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/fx_exposure.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/fx_exposure.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
var_groupby_2675541522576 = var_formula_2675542098000.select([
    pl.col('order_id').n_unique().alias('clean_orders'),
    pl.col('net_revenue_usd').sum().alias('net_revenue_usd'),
    pl.col('gross_margin_usd').sum().alias('gross_margin_usd'),
    pl.col('is_returned').sum().alias('returned_orders'),
    pl.col('customer_id').n_unique().alias('distinct_customers'),
    pl.col('product_id').n_unique().alias('distinct_products'),
    pl.col('gross_revenue_usd_raw').sum().alias('gross_revenue_usd_raw'),
    pl.col('is_high_risk').sum().alias('high_risk_orders')
])
var_groupby_2675541522576 = normalize_to_supported_dtypes(var_groupby_2675541522576)
var_select_2675541675216 = var_runtot_2675541673296.select(['order_year_month', 'revenue_usd', 'margin_usd', 'orders', 'RunTot_revenue_usd'])
var_select_2675541675216 = var_select_2675541675216.with_columns(
    pl.col('order_year_month').cast(pl.String, strict=False).alias('order_year_month')
)
var_select_2675541675216 = var_select_2675541675216.with_columns(
    pl.col('revenue_usd').cast(pl.Float64, strict=False).alias('revenue_usd')
)
var_select_2675541675216 = var_select_2675541675216.with_columns(
    pl.col('margin_usd').cast(pl.Float64, strict=False).alias('margin_usd')
)
var_select_2675541675216 = var_select_2675541675216.with_columns(
    pl.col('RunTot_revenue_usd').cast(pl.Float64, strict=False).alias('RunTot_revenue_usd')
)
var_select_2675541675216 = var_select_2675541675216.rename({'RunTot_revenue_usd': 'cumulative_revenue_usd'})
# Ensure we're working with a LazyFrame for memory efficiency
if var_sort_2675541618640 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_sort_2675541618640, pl.DataFrame):
        var_sort_2675541618640_lazy = var_sort_2675541618640.lazy()
    elif isinstance(var_sort_2675541618640, pl.LazyFrame):
        var_sort_2675541618640_lazy = var_sort_2675541618640
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_sort_2675541618640)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_sort_2675541618640_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/top_customers.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/top_customers.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
# Ensure we're working with a LazyFrame for memory efficiency
if var_formula_2675541513616 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_formula_2675541513616, pl.DataFrame):
        var_formula_2675541513616_lazy = var_formula_2675541513616.lazy()
    elif isinstance(var_formula_2675541513616, pl.LazyFrame):
        var_formula_2675541513616_lazy = var_formula_2675541513616
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_formula_2675541513616)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_formula_2675541513616_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/supplier_performance.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/supplier_performance.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
var_select_2675542101680 = var_groupby_2675541522576.select(['clean_orders', 'gross_revenue_usd_raw', 'net_revenue_usd', 'gross_margin_usd', 'returned_orders', 'distinct_customers', 'distinct_products', 'high_risk_orders'])
var_select_2675542101680 = var_select_2675542101680.with_columns(
    pl.col('clean_orders').cast(pl.Int64, strict=False).alias('clean_orders')
)
var_select_2675542101680 = var_select_2675542101680.with_columns(
    pl.col('gross_revenue_usd_raw').cast(pl.Float64, strict=False).alias('gross_revenue_usd_raw')
)
var_select_2675542101680 = var_select_2675542101680.with_columns(
    pl.col('net_revenue_usd').cast(pl.Float64, strict=False).alias('net_revenue_usd')
)
var_select_2675542101680 = var_select_2675542101680.with_columns(
    pl.col('gross_margin_usd').cast(pl.Float64, strict=False).alias('gross_margin_usd')
)
var_select_2675542101680 = var_select_2675542101680.with_columns(
    pl.col('returned_orders').cast(pl.Int64, strict=False).alias('returned_orders')
)
var_select_2675542101680 = var_select_2675542101680.with_columns(
    pl.col('distinct_customers').cast(pl.Int64, strict=False).alias('distinct_customers')
)
var_select_2675542101680 = var_select_2675542101680.with_columns(
    pl.col('distinct_products').cast(pl.Int64, strict=False).alias('distinct_products')
)
var_select_2675542101680 = var_select_2675542101680.with_columns(
    pl.col('high_risk_orders').cast(pl.Int64, strict=False).alias('high_risk_orders')
)
var_select_2675542101680 = var_select_2675542101680.rename({'gross_revenue_usd_raw': 'gross_revenue_usd'})
# Ensure we're working with a LazyFrame for memory efficiency
if var_select_2675541675216 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_select_2675541675216, pl.DataFrame):
        var_select_2675541675216_lazy = var_select_2675541675216.lazy()
    elif isinstance(var_select_2675541675216, pl.LazyFrame):
        var_select_2675541675216_lazy = var_select_2675541675216
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_select_2675541675216)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_select_2675541675216_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/monthly_revenue.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/monthly_revenue.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
_2675541678736_cols = (var_select_2675541675216.collect_schema().names() if isinstance(var_select_2675541675216, pl.LazyFrame) else var_select_2675541675216.columns)
# Validate data columns
missing = [col for col in ['revenue_usd', 'margin_usd', 'orders'] if col not in _2675541678736_cols]
if missing:
    print(f'Warning: Missing columns will be skipped: {missing}')

# Filter to existing columns
valid_key_cols = [col for col in ['order_year_month'] if col in _2675541678736_cols]
valid_data_cols = [col for col in ['revenue_usd', 'margin_usd', 'orders'] if col in _2675541678736_cols]

# Transpose operation using Polars unpivot
var_transpose_2675541678736 = var_select_2675541675216.unpivot(
    index=valid_key_cols,
    on=valid_data_cols,
    variable_name='Name',
    value_name='Value'
)
# Widen unpivot supertypes into Select-supported dtypes
var_transpose_2675541678736 = normalize_to_supported_dtypes(var_transpose_2675541678736)
import duckdb
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_select_2675542101680.collect() if hasattr(var_select_2675542101680, 'collect') else var_select_2675542101680
duck.register('df_step_0', df_for_duck)
df_for_duck = duck.execute('''SELECT * REPLACE (ROUND("gross_revenue_usd", 2) AS "gross_revenue_usd") FROM df_step_0''').pl()
duck.register('df_step_1', df_for_duck)
df_for_duck = duck.execute('''SELECT *, CASE WHEN "net_revenue_usd" = 0 
THEN NULL 
ELSE ROUND("gross_margin_usd" / "net_revenue_usd", 4) 
END AS "margin_pct" FROM df_step_1''').pl()
# Widen DuckDB-native types into Select-supported dtypes
df_for_duck = normalize_to_supported_dtypes(df_for_duck)
# Preserve lazy execution when the incoming value is lazy
var_formula_2675542099920 = df_for_duck.lazy() if hasattr(var_select_2675542101680, 'collect') else df_for_duck
duck.close()
var_select_2675541680656 = var_transpose_2675541678736.select(['order_year_month', 'Name', 'Value'])
var_select_2675541680656 = var_select_2675541680656.with_columns(
    pl.col('order_year_month').cast(pl.String, strict=False).alias('order_year_month')
)
var_select_2675541680656 = var_select_2675541680656.with_columns(
    pl.col('Name').cast(pl.String, strict=False).alias('Name')
)
var_select_2675541680656 = var_select_2675541680656.with_columns(
    pl.col('Value').cast(pl.Float64, strict=False).alias('Value')
)
var_select_2675541680656 = var_select_2675541680656.rename({'Name': 'metric', 'Value': 'value'})
var_select_2675542105520 = var_formula_2675542099920.select(['clean_orders', 'gross_revenue_usd', 'net_revenue_usd', 'gross_margin_usd', 'margin_pct', 'returned_orders', 'high_risk_orders', 'distinct_customers', 'distinct_products'])
var_select_2675542105520 = var_select_2675542105520.with_columns(
    pl.col('clean_orders').cast(pl.Int64, strict=False).alias('clean_orders')
)
var_select_2675542105520 = var_select_2675542105520.with_columns(
    pl.col('gross_revenue_usd').cast(pl.Float64, strict=False).alias('gross_revenue_usd')
)
var_select_2675542105520 = var_select_2675542105520.with_columns(
    pl.col('net_revenue_usd').cast(pl.Float64, strict=False).alias('net_revenue_usd')
)
var_select_2675542105520 = var_select_2675542105520.with_columns(
    pl.col('gross_margin_usd').cast(pl.Float64, strict=False).alias('gross_margin_usd')
)
var_select_2675542105520 = var_select_2675542105520.with_columns(
    pl.col('margin_pct').cast(pl.Float64, strict=False).alias('margin_pct')
)
var_select_2675542105520 = var_select_2675542105520.with_columns(
    pl.col('returned_orders').cast(pl.Int64, strict=False).alias('returned_orders')
)
var_select_2675542105520 = var_select_2675542105520.with_columns(
    pl.col('high_risk_orders').cast(pl.Int64, strict=False).alias('high_risk_orders')
)
var_select_2675542105520 = var_select_2675542105520.with_columns(
    pl.col('distinct_customers').cast(pl.Int64, strict=False).alias('distinct_customers')
)
var_select_2675542105520 = var_select_2675542105520.with_columns(
    pl.col('distinct_products').cast(pl.Int64, strict=False).alias('distinct_products')
)
# Ensure we're working with a LazyFrame for memory efficiency
if var_select_2675541680656 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_select_2675541680656, pl.DataFrame):
        var_select_2675541680656_lazy = var_select_2675541680656.lazy()
    elif isinstance(var_select_2675541680656, pl.LazyFrame):
        var_select_2675541680656_lazy = var_select_2675541680656
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_select_2675541680656)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_select_2675541680656_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/monthly_revenue_long.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/monthly_revenue_long.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
_2675542270480_cols = (var_select_2675542105520.collect_schema().names() if isinstance(var_select_2675542105520, pl.LazyFrame) else var_select_2675542105520.columns)
# Validate data columns
missing = [col for col in ['clean_orders', 'gross_revenue_usd', 'net_revenue_usd', 'gross_margin_usd', 'margin_pct', 'returned_orders', 'high_risk_orders', 'distinct_customers', 'distinct_products'] if col not in _2675542270480_cols]
if missing:
    print(f'Warning: Missing columns will be skipped: {missing}')

# Filter to existing columns
valid_key_cols = [col for col in [] if col in _2675542270480_cols]
valid_data_cols = [col for col in ['clean_orders', 'gross_revenue_usd', 'net_revenue_usd', 'gross_margin_usd', 'margin_pct', 'returned_orders', 'high_risk_orders', 'distinct_customers', 'distinct_products'] if col in _2675542270480_cols]

# Transpose operation using Polars unpivot
var_transpose_2675542270480 = var_select_2675542105520.unpivot(
    index=valid_key_cols,
    on=valid_data_cols,
    variable_name='Name',
    value_name='Value'
)
# Widen unpivot supertypes into Select-supported dtypes
var_transpose_2675542270480 = normalize_to_supported_dtypes(var_transpose_2675542270480)
var_select_2675542272400 = var_transpose_2675542270480.select(['Name', 'Value'])
var_select_2675542272400 = var_select_2675542272400.with_columns(
    pl.col('Name').cast(pl.String, strict=False).alias('Name')
)
var_select_2675542272400 = var_select_2675542272400.with_columns(
    pl.col('Value').cast(pl.Float64, strict=False).alias('Value')
)
var_select_2675542272400 = var_select_2675542272400.rename({'Name': 'metric', 'Value': 'value'})
# Ensure we're working with a LazyFrame for memory efficiency
if var_select_2675542272400 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_select_2675542272400, pl.DataFrame):
        var_select_2675542272400_lazy = var_select_2675542272400.lazy()
    elif isinstance(var_select_2675542272400, pl.LazyFrame):
        var_select_2675542272400_lazy = var_select_2675542272400
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_select_2675542272400)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_select_2675542272400_lazy.sink_csv('C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/kpi_summary.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/kpi_summary.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
