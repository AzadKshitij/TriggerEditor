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
var_file_input_2905413384816 = pl.scan_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/data/channels.csv', infer_schema=False)

# var_file_input_2905413384816 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_2905413953936 = pl.scan_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/data/orders.csv', infer_schema=False)

# var_file_input_2905413953936 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_2905413955536 = pl.scan_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/data/customers.csv', infer_schema=False)

# var_file_input_2905413955536 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_2905413956976 = pl.scan_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/data/products.csv', infer_schema=False)

# var_file_input_2905413956976 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_2905413958576 = pl.scan_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/data/suppliers.csv', infer_schema=False)

# var_file_input_2905413958576 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_2905414025776 = pl.scan_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/data/fx_rates.csv', infer_schema=False)

# var_file_input_2905414025776 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
var_select_2905414211120 = var_file_input_2905413384816.select(['channel_id', 'channel_name', 'channel_group', 'is_digital'])
var_select_2905414211120 = var_select_2905414211120.with_columns(
    pl.col('channel_id').cast(pl.Int64, strict=False).alias('channel_id')
)
var_select_2905414211120 = var_select_2905414211120.with_columns(
    pl.col('channel_name').cast(pl.String, strict=False).alias('channel_name')
)
var_select_2905414211120 = var_select_2905414211120.with_columns(
    pl.col('channel_group').cast(pl.String, strict=False).alias('channel_group')
)
var_select_2905414211120 = var_select_2905414211120.with_columns(
    pl.col('is_digital').cast(pl.String, strict=False).alias('is_digital')
)
var_select_2905414028656 = var_file_input_2905413953936.select([' Order ID ', 'Customer_Id', 'PRODUCT_ID', 'supplier id', 'Channel ID', 'Currency', 'Order TS', 'Quantity', 'unit_price_local', 'Discount Pct', 'tax_local', 'shipping_local', 'Status', 'Payment Method', 'is_returned'])
var_select_2905414028656 = var_select_2905414028656.with_columns(
    pl.col(' Order ID ').cast(pl.String, strict=False).alias(' Order ID ')
)
var_select_2905414028656 = var_select_2905414028656.with_columns(
    pl.col('Customer_Id').cast(pl.Int64, strict=False).alias('Customer_Id')
)
var_select_2905414028656 = var_select_2905414028656.with_columns(
    pl.col('PRODUCT_ID').cast(pl.Int64, strict=False).alias('PRODUCT_ID')
)
var_select_2905414028656 = var_select_2905414028656.with_columns(
    pl.col('supplier id').cast(pl.Int64, strict=False).alias('supplier id')
)
var_select_2905414028656 = var_select_2905414028656.with_columns(
    pl.col('Channel ID').cast(pl.Int64, strict=False).alias('Channel ID')
)
var_select_2905414028656 = var_select_2905414028656.with_columns(
    pl.col('Currency').cast(pl.String, strict=False).alias('Currency')
)
var_select_2905414028656 = var_select_2905414028656.with_columns(
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
var_select_2905414028656 = var_select_2905414028656.with_columns(
    pl.col('Quantity').cast(pl.Int64, strict=False).alias('Quantity')
)
var_select_2905414028656 = var_select_2905414028656.with_columns(
    pl.col('unit_price_local').cast(pl.Float64, strict=False).alias('unit_price_local')
)
var_select_2905414028656 = var_select_2905414028656.with_columns(
    pl.col('Discount Pct').cast(pl.Float64, strict=False).alias('Discount Pct')
)
var_select_2905414028656 = var_select_2905414028656.with_columns(
    pl.col('tax_local').cast(pl.Float64, strict=False).alias('tax_local')
)
var_select_2905414028656 = var_select_2905414028656.with_columns(
    pl.col('shipping_local').cast(pl.Float64, strict=False).alias('shipping_local')
)
var_select_2905414028656 = var_select_2905414028656.with_columns(
    pl.col('Status').cast(pl.String, strict=False).alias('Status')
)
var_select_2905414028656 = var_select_2905414028656.with_columns(
    pl.col('Payment Method').cast(pl.String, strict=False).alias('Payment Method')
)
var_select_2905414028656 = var_select_2905414028656.with_columns(
    pl.col('is_returned').cast(pl.String, strict=False).alias('is_returned')
)
var_select_2905414213040 = var_file_input_2905413955536.select(['customer_id', 'email', 'full_name', 'signup_date', 'country', 'region', 'currency', 'segment', 'age_band', 'loyalty_tier'])
var_select_2905414213040 = var_select_2905414213040.with_columns(
    pl.col('customer_id').cast(pl.Int64, strict=False).alias('customer_id')
)
var_select_2905414213040 = var_select_2905414213040.with_columns(
    pl.col('email').cast(pl.String, strict=False).alias('email')
)
var_select_2905414213040 = var_select_2905414213040.with_columns(
    pl.col('full_name').cast(pl.String, strict=False).alias('full_name')
)
var_select_2905414213040 = var_select_2905414213040.with_columns(
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
var_select_2905414213040 = var_select_2905414213040.with_columns(
    pl.col('country').cast(pl.String, strict=False).alias('country')
)
var_select_2905414213040 = var_select_2905414213040.with_columns(
    pl.col('region').cast(pl.String, strict=False).alias('region')
)
var_select_2905414213040 = var_select_2905414213040.with_columns(
    pl.col('currency').cast(pl.String, strict=False).alias('currency')
)
var_select_2905414213040 = var_select_2905414213040.with_columns(
    pl.col('segment').cast(pl.String, strict=False).alias('segment')
)
var_select_2905414213040 = var_select_2905414213040.with_columns(
    pl.col('age_band').cast(pl.String, strict=False).alias('age_band')
)
var_select_2905414213040 = var_select_2905414213040.with_columns(
    pl.col('loyalty_tier').cast(pl.String, strict=False).alias('loyalty_tier')
)
var_select_2905414213040 = var_select_2905414213040.rename({'email': 'customer_email', 'full_name': 'customer_name', 'country': 'customer_country', 'currency': 'customer_currency', 'age_band': 'customer_age_band'})
var_select_2905414215600 = var_file_input_2905413956976.select(['product_id', 'sku', 'product_name', 'category', 'subcategory', 'brand', 'unit_price', 'unit_cost', 'launch_date'])
var_select_2905414215600 = var_select_2905414215600.with_columns(
    pl.col('product_id').cast(pl.Int64, strict=False).alias('product_id')
)
var_select_2905414215600 = var_select_2905414215600.with_columns(
    pl.col('sku').cast(pl.String, strict=False).alias('sku')
)
var_select_2905414215600 = var_select_2905414215600.with_columns(
    pl.col('product_name').cast(pl.String, strict=False).alias('product_name')
)
var_select_2905414215600 = var_select_2905414215600.with_columns(
    pl.col('category').cast(pl.String, strict=False).alias('category')
)
var_select_2905414215600 = var_select_2905414215600.with_columns(
    pl.col('subcategory').cast(pl.String, strict=False).alias('subcategory')
)
var_select_2905414215600 = var_select_2905414215600.with_columns(
    pl.col('brand').cast(pl.String, strict=False).alias('brand')
)
var_select_2905414215600 = var_select_2905414215600.with_columns(
    pl.col('unit_price').cast(pl.Float64, strict=False).alias('unit_price')
)
var_select_2905414215600 = var_select_2905414215600.with_columns(
    pl.col('unit_cost').cast(pl.Float64, strict=False).alias('unit_cost')
)
var_select_2905414215600 = var_select_2905414215600.with_columns(
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
var_select_2905414217520 = var_file_input_2905413958576.select(['supplier_id', 'supplier_name', 'country', 'lead_time_days', 'reliability_score'])
var_select_2905414217520 = var_select_2905414217520.with_columns(
    pl.col('supplier_id').cast(pl.Int64, strict=False).alias('supplier_id')
)
var_select_2905414217520 = var_select_2905414217520.with_columns(
    pl.col('supplier_name').cast(pl.String, strict=False).alias('supplier_name')
)
var_select_2905414217520 = var_select_2905414217520.with_columns(
    pl.col('country').cast(pl.String, strict=False).alias('country')
)
var_select_2905414217520 = var_select_2905414217520.with_columns(
    pl.col('lead_time_days').cast(pl.Int64, strict=False).alias('lead_time_days')
)
var_select_2905414217520 = var_select_2905414217520.with_columns(
    pl.col('reliability_score').cast(pl.Float64, strict=False).alias('reliability_score')
)
var_select_2905414219440 = var_file_input_2905414025776.select(['currency', 'currency_name', 'usd_rate'])
var_select_2905414219440 = var_select_2905414219440.with_columns(
    pl.col('currency').cast(pl.String, strict=False).alias('currency')
)
var_select_2905414219440 = var_select_2905414219440.with_columns(
    pl.col('currency_name').cast(pl.String, strict=False).alias('currency_name')
)
var_select_2905414219440 = var_select_2905414219440.with_columns(
    pl.col('usd_rate').cast(pl.Float64, strict=False).alias('usd_rate')
)
import polars as pl
# Normalize column names (11 renamed)
var_normalize_columns_2903920251184 = var_select_2905414028656.rename({' Order ID ': 'order_id', 'Customer_Id': 'customer_id', 'PRODUCT_ID': 'product_id', 'supplier id': 'supplier_id', 'Channel ID': 'channel_id', 'Currency': 'currency', 'Order TS': 'order_ts', 'Quantity': 'quantity', 'Discount Pct': 'discount_pct', 'Status': 'status', 'Payment Method': 'payment_method'})
import duckdb
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_select_2905414219440.collect() if hasattr(var_select_2905414219440, 'collect') else var_select_2905414219440
duck.register('df_step_0', df_for_duck)
df_for_duck = duck.execute('''SELECT * REPLACE (LOWER("currency") AS "currency") FROM df_step_0''').pl()
# Widen DuckDB-native types into Select-supported dtypes
df_for_duck = normalize_to_supported_dtypes(df_for_duck)
# Preserve lazy execution when the incoming value is lazy
var_formula_2903920364112 = df_for_duck.lazy() if hasattr(var_select_2905414219440, 'collect') else df_for_duck
duck.close()
from trigger_designer.core.utils.cleansing_util import DataCleansing, NullStrategy
import polars as pl
# Convert LazyFrame to DataFrame if needed
_cleansing_input = var_normalize_columns_2903920251184.collect() if hasattr(var_normalize_columns_2903920251184, 'collect') else var_normalize_columns_2903920251184
cleaner = DataCleansing(_cleansing_input)
cleaner.strip_whitespace(remove_all=False, normalize_spaces=True, fields=['order_id', 'customer_id', 'product_id', 'supplier_id', 'channel_id', 'currency', 'order_ts', 'quantity', 'unit_price_local', 'discount_pct', 'tax_local', 'shipping_local', 'status', 'payment_method', 'is_returned'])
var_cleansing_2905414221360 = cleaner.get_result()
from trigger_designer.core.utils.cleansing_util import DataCleansing, NullStrategy
import polars as pl
# Convert LazyFrame to DataFrame if needed
_cleansing_input = var_cleansing_2905414221360.collect() if hasattr(var_cleansing_2905414221360, 'collect') else var_cleansing_2905414221360
cleaner = DataCleansing(_cleansing_input)
cleaner.strip_whitespace(remove_all=False, normalize_spaces=True, fields=['currency'])
cleaner.modify_case('lower', fields=['currency'])
var_cleansing_2903924658320 = cleaner.get_result()
from trigger_designer.core.utils.cleansing_util import DataCleansing, NullStrategy
import polars as pl
# Convert LazyFrame to DataFrame if needed
_cleansing_input = var_cleansing_2903924658320.collect() if hasattr(var_cleansing_2903924658320, 'collect') else var_cleansing_2903924658320
cleaner = DataCleansing(_cleansing_input)
cleaner.remove_rows_with_nulls(fields=['order_id', 'customer_id', 'product_id'])
cleaner.strip_whitespace(remove_all=False, normalize_spaces=True, fields=['order_id', 'customer_id', 'product_id'])
cleaner.modify_case('lower', fields=['order_id', 'customer_id', 'product_id'])
var_cleansing_2905414362736 = cleaner.get_result()
import duckdb
import polars as pl
# Filter rows with a SQL WHERE clause (no new columns)
df_for_duck = var_cleansing_2905414362736.collect() if hasattr(var_cleansing_2905414362736, 'collect') else var_cleansing_2905414362736
duck = duckdb.connect(':memory:')
duck.register('df_filter', df_for_duck)
var_t_filter_2905414365136 = duck.execute('SELECT * FROM df_filter WHERE "quantity" >= 1 and "quantity" <= 500').pl()
var_f_filter_2905414365136 = duck.execute('SELECT * FROM df_filter WHERE NOT ("quantity" >= 1 and "quantity" <= 500)').pl()
# Preserve lazy execution when the incoming value is lazy
var_t_filter_2905414365136 = var_t_filter_2905414365136.lazy() if hasattr(var_cleansing_2905414362736, 'collect') else var_t_filter_2905414365136
var_f_filter_2905414365136 = var_f_filter_2905414365136.lazy() if hasattr(var_cleansing_2905414362736, 'collect') else var_f_filter_2905414365136
duck.close()
import duckdb
import polars as pl
# Filter rows with a SQL WHERE clause (no new columns)
df_for_duck = var_t_filter_2905414365136.collect() if hasattr(var_t_filter_2905414365136, 'collect') else var_t_filter_2905414365136
duck = duckdb.connect(':memory:')
duck.register('df_filter', df_for_duck)
var_t_filter_2903920246864 = duck.execute('SELECT * FROM df_filter WHERE "unit_price_local" > 0 and \n"unit_price_local" <= 5000').pl()
var_f_filter_2903920246864 = duck.execute('SELECT * FROM df_filter WHERE NOT ("unit_price_local" > 0 and \n"unit_price_local" <= 5000)').pl()
# Preserve lazy execution when the incoming value is lazy
var_t_filter_2903920246864 = var_t_filter_2903920246864.lazy() if hasattr(var_t_filter_2905414365136, 'collect') else var_t_filter_2903920246864
var_f_filter_2903920246864 = var_f_filter_2903920246864.lazy() if hasattr(var_t_filter_2905414365136, 'collect') else var_f_filter_2903920246864
duck.close()
import duckdb
import polars as pl
# Filter rows with a SQL WHERE clause (no new columns)
df_for_duck = var_t_filter_2903920246864.collect() if hasattr(var_t_filter_2903920246864, 'collect') else var_t_filter_2903920246864
duck = duckdb.connect(':memory:')
duck.register('df_filter', df_for_duck)
var_t_filter_2903920249104 = duck.execute('SELECT * FROM df_filter WHERE YEAR("order_ts") <= 2025').pl()
var_f_filter_2903920249104 = duck.execute('SELECT * FROM df_filter WHERE NOT (YEAR("order_ts") <= 2025)').pl()
# Preserve lazy execution when the incoming value is lazy
var_t_filter_2903920249104 = var_t_filter_2903920249104.lazy() if hasattr(var_t_filter_2903920246864, 'collect') else var_t_filter_2903920249104
var_f_filter_2903920249104 = var_f_filter_2903920249104.lazy() if hasattr(var_t_filter_2903920246864, 'collect') else var_f_filter_2903920249104
duck.close()
import polars as pl
# Split into unique and duplicate records based on: order_id
var_unique_2903920257744 = var_t_filter_2903920249104.unique(subset=["order_id"], maintain_order=True)
var_duplicate_2903920257744 = var_t_filter_2903920249104.filter(pl.struct(["order_id"]).is_duplicated())
var_select_2903924660240 = var_unique_2903920257744.select(['order_id', 'customer_id', 'product_id', 'supplier_id', 'channel_id', 'currency', 'order_ts', 'quantity', 'unit_price_local', 'discount_pct', 'tax_local', 'shipping_local', 'status', 'payment_method', 'is_returned'])
# Polars LazyFrame Join Operation
import polars as pl

def _ensure_lazyframe(data):
    if isinstance(data, pl.DataFrame):
        return data.lazy()
    if isinstance(data, pl.LazyFrame):
        return data
    raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(data)}')

_left_input = _ensure_lazyframe(var_select_2903924660240)
_right_input = _ensure_lazyframe(var_select_2905414213040)

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
var_join_2903920377072 = _join_result.filter(
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
var_l_join_2903920377072 = _join_result.filter(
    pl.col('__right_present').is_null()
).select(_left_cols)

# Extract right-only data efficiently
_right_cols = ['customer_id', 'customer_email', 'customer_name', 'signup_date', 'customer_country', 'region', 'customer_currency', 'segment', 'customer_age_band', 'loyalty_tier']
var_r_join_2903920377072 = _join_result.filter(
    pl.col('__left_present').is_null()
).select(_right_cols)

# Clean up temporary variables
del _left_input, _right_input, _left_tagged, _right_tagged, _join_result, _left_cols, _right_cols
import polars as pl
_union_inputs_2903923634288 = [var_join_2903920377072, var_l_join_2903920377072]
var_union_2903923634288 = pl.concat([(f.lazy() if isinstance(f, pl.DataFrame) else f) for f in _union_inputs_2903923634288], how='diagonal_relaxed')
del _union_inputs_2903923634288
# Polars LazyFrame Join Operation
import polars as pl

def _ensure_lazyframe(data):
    if isinstance(data, pl.DataFrame):
        return data.lazy()
    if isinstance(data, pl.LazyFrame):
        return data
    raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(data)}')

_left_input = _ensure_lazyframe(var_union_2903923634288)
_right_input = _ensure_lazyframe(var_select_2905414215600)

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
var_join_2903923518000 = _join_result.filter(
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
var_l_join_2903923518000 = _join_result.filter(
    pl.col('__right_present').is_null()
).select(_left_cols)

# Extract right-only data efficiently
_right_cols = ['product_id', 'sku', 'product_name', 'category', 'subcategory', 'brand', 'unit_price', 'unit_cost', 'launch_date']
var_r_join_2903923518000 = _join_result.filter(
    pl.col('__left_present').is_null()
).select(_right_cols)

# Clean up temporary variables
del _left_input, _right_input, _left_tagged, _right_tagged, _join_result, _left_cols, _right_cols
# Ensure we're working with a LazyFrame for memory efficiency
if var_union_2903923634288 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_union_2903923634288, pl.DataFrame):
        var_union_2903923634288_lazy = var_union_2903923634288.lazy()
    elif isinstance(var_union_2903923634288, pl.LazyFrame):
        var_union_2903923634288_lazy = var_union_2903923634288
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_union_2903923634288)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_union_2903923634288_lazy.sink_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/01 enriched customer_id.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/01 enriched customer_id.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
import polars as pl
_union_inputs_2903923729712 = [var_join_2903923518000, var_l_join_2903923518000]
var_union_2903923729712 = pl.concat([(f.lazy() if isinstance(f, pl.DataFrame) else f) for f in _union_inputs_2903923729712], how='diagonal_relaxed')
del _union_inputs_2903923729712
# Polars LazyFrame Join Operation
import polars as pl

def _ensure_lazyframe(data):
    if isinstance(data, pl.DataFrame):
        return data.lazy()
    if isinstance(data, pl.LazyFrame):
        return data
    raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(data)}')

_left_input = _ensure_lazyframe(var_union_2903923729712)
_right_input = _ensure_lazyframe(var_select_2905414217520)

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
var_join_2903923521040 = _join_result.filter(
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
var_l_join_2903923521040 = _join_result.filter(
    pl.col('__right_present').is_null()
).select(_left_cols)

# Extract right-only data efficiently
_right_cols = ['supplier_id', 'supplier_name', 'country', 'lead_time_days', 'reliability_score']
var_r_join_2903923521040 = _join_result.filter(
    pl.col('__left_present').is_null()
).select(_right_cols)

# Clean up temporary variables
del _left_input, _right_input, _left_tagged, _right_tagged, _join_result, _left_cols, _right_cols
# Ensure we're working with a LazyFrame for memory efficiency
if var_union_2903923729712 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_union_2903923729712, pl.DataFrame):
        var_union_2903923729712_lazy = var_union_2903923729712.lazy()
    elif isinstance(var_union_2903923729712, pl.LazyFrame):
        var_union_2903923729712_lazy = var_union_2903923729712
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_union_2903923729712)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_union_2903923729712_lazy.sink_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/02 enriched product_id.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/02 enriched product_id.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
import polars as pl
_union_inputs_2903923731792 = [var_join_2903923521040, var_l_join_2903923521040]
var_union_2903923731792 = pl.concat([(f.lazy() if isinstance(f, pl.DataFrame) else f) for f in _union_inputs_2903923731792], how='diagonal_relaxed')
del _union_inputs_2903923731792
# Polars LazyFrame Join Operation
import polars as pl

def _ensure_lazyframe(data):
    if isinstance(data, pl.DataFrame):
        return data.lazy()
    if isinstance(data, pl.LazyFrame):
        return data
    raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(data)}')

_left_input = _ensure_lazyframe(var_union_2903923731792)
_right_input = _ensure_lazyframe(var_select_2905414211120)

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
var_join_2903923622448 = _join_result.filter(
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
var_l_join_2903923622448 = _join_result.filter(
    pl.col('__right_present').is_null()
).select(_left_cols)

# Extract right-only data efficiently
_right_cols = ['channel_id', 'channel_name', 'channel_group', 'is_digital']
var_r_join_2903923622448 = _join_result.filter(
    pl.col('__left_present').is_null()
).select(_right_cols)

# Clean up temporary variables
del _left_input, _right_input, _left_tagged, _right_tagged, _join_result, _left_cols, _right_cols
# Ensure we're working with a LazyFrame for memory efficiency
if var_union_2903923731792 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_union_2903923731792, pl.DataFrame):
        var_union_2903923731792_lazy = var_union_2903923731792.lazy()
    elif isinstance(var_union_2903923731792, pl.LazyFrame):
        var_union_2903923731792_lazy = var_union_2903923731792
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_union_2903923731792)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_union_2903923731792_lazy.sink_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/03 enriched supplier_id.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/03 enriched supplier_id.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
import polars as pl
_union_inputs_2903923733872 = [var_join_2903923622448, var_l_join_2903923622448]
var_union_2903923733872 = pl.concat([(f.lazy() if isinstance(f, pl.DataFrame) else f) for f in _union_inputs_2903923733872], how='diagonal_relaxed')
del _union_inputs_2903923733872
# Polars LazyFrame Join Operation
import polars as pl

def _ensure_lazyframe(data):
    if isinstance(data, pl.DataFrame):
        return data.lazy()
    if isinstance(data, pl.LazyFrame):
        return data
    raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(data)}')

_left_input = _ensure_lazyframe(var_union_2903923733872)
_right_input = _ensure_lazyframe(var_formula_2903920364112)

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
var_join_2903923625488 = _join_result.filter(
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
var_l_join_2903923625488 = _join_result.filter(
    pl.col('__right_present').is_null()
).select(_left_cols)

# Extract right-only data efficiently
_right_cols = ['currency', 'currency_name', 'usd_rate']
var_r_join_2903923625488 = _join_result.filter(
    pl.col('__left_present').is_null()
).select(_right_cols)

# Clean up temporary variables
del _left_input, _right_input, _left_tagged, _right_tagged, _join_result, _left_cols, _right_cols
# Ensure we're working with a LazyFrame for memory efficiency
if var_union_2903923733872 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_union_2903923733872, pl.DataFrame):
        var_union_2903923733872_lazy = var_union_2903923733872.lazy()
    elif isinstance(var_union_2903923733872, pl.LazyFrame):
        var_union_2903923733872_lazy = var_union_2903923733872
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_union_2903923733872)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_union_2903923733872_lazy.sink_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/04 enriched channel_id.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/04 enriched channel_id.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
import polars as pl
_union_inputs_2903923735952 = [var_join_2903923625488, var_l_join_2903923625488]
var_union_2903923735952 = pl.concat([(f.lazy() if isinstance(f, pl.DataFrame) else f) for f in _union_inputs_2903923735952], how='diagonal_relaxed')
del _union_inputs_2903923735952
import duckdb
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_union_2903923735952.collect() if hasattr(var_union_2903923735952, 'collect') else var_union_2903923735952
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
# Widen DuckDB-native types into Select-supported dtypes
df_for_duck = normalize_to_supported_dtypes(df_for_duck)
# Preserve lazy execution when the incoming value is lazy
var_formula_2903923628528 = df_for_duck.lazy() if hasattr(var_union_2903923735952, 'collect') else df_for_duck
duck.close()
# Ensure we're working with a LazyFrame for memory efficiency
if var_union_2903923735952 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_union_2903923735952, pl.DataFrame):
        var_union_2903923735952_lazy = var_union_2903923735952.lazy()
    elif isinstance(var_union_2903923735952, pl.LazyFrame):
        var_union_2903923735952_lazy = var_union_2903923735952
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_union_2903923735952)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_union_2903923735952_lazy.sink_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/05 enriched currency.csv')
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
df_for_duck = var_formula_2903923628528.collect() if hasattr(var_formula_2903923628528, 'collect') else var_formula_2903923628528
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
# Widen DuckDB-native types into Select-supported dtypes
df_for_duck = normalize_to_supported_dtypes(df_for_duck)
# Preserve lazy execution when the incoming value is lazy
var_formula_2903923630448 = df_for_duck.lazy() if hasattr(var_formula_2903923628528, 'collect') else df_for_duck
duck.close()
import duckdb
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_formula_2903923630448.collect() if hasattr(var_formula_2903923630448, 'collect') else var_formula_2903923630448
duck.register('df_step_0', df_for_duck)
df_for_duck = duck.execute('''SELECT *, "quantity" * "unit_cost" AS "cogs_usd" FROM df_step_0''').pl()
duck.register('df_step_1', df_for_duck)
df_for_duck = duck.execute('''SELECT *, "net_revenue_usd" * "cogs_usd" AS "gross_margin_usd" FROM df_step_1''').pl()
duck.register('df_step_2', df_for_duck)
df_for_duck = duck.execute('''SELECT *, CASE
    WHEN "net_revenue_usd" IS NULL OR "net_revenue_usd" = 0 THEN NULL
    ELSE "gross_margin_usd" / "net_revenue_usd"
END AS "margin_pct" FROM df_step_2''').pl()
# Widen DuckDB-native types into Select-supported dtypes
df_for_duck = normalize_to_supported_dtypes(df_for_duck)
# Preserve lazy execution when the incoming value is lazy
var_formula_2903923787248 = df_for_duck.lazy() if hasattr(var_formula_2903923630448, 'collect') else df_for_duck
duck.close()
import duckdb
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_formula_2903923787248.collect() if hasattr(var_formula_2903923787248, 'collect') else var_formula_2903923787248
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
var_formula_2903923789168 = df_for_duck.lazy() if hasattr(var_formula_2903923787248, 'collect') else df_for_duck
duck.close()
import duckdb
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_formula_2903923789168.collect() if hasattr(var_formula_2903923789168, 'collect') else var_formula_2903923789168
duck.register('df_step_0', df_for_duck)
df_for_duck = duck.execute('''SELECT *, (CASE WHEN "is_returned" THEN 2 ELSE 0 END)
+ (CASE WHEN "status" IN ('refunded', 'cancelled') THEN 2 ELSE 0 END)
+ (CASE WHEN "net_revenue_usd" > 2000 THEN 1 ELSE 0 END)
+ (CASE WHEN "margin_pct" < 0.10 THEN 1 ELSE 0 END)
+ (CASE WHEN "segment" IS NULL THEN 2 ELSE 0 END)
 AS "risk_score" FROM df_step_0''').pl()
duck.register('df_step_1', df_for_duck)
df_for_duck = duck.execute('''SELECT *, CASE
    WHEN "risk_score" >= 4 THEN 'High'
    WHEN "risk_score" >= 2 THEN 'Medium'
    ELSE 'Low'
END AS "risk_band" FROM df_step_1''').pl()
# Widen DuckDB-native types into Select-supported dtypes
df_for_duck = normalize_to_supported_dtypes(df_for_duck)
# Preserve lazy execution when the incoming value is lazy
var_formula_2903923791088 = df_for_duck.lazy() if hasattr(var_formula_2903923789168, 'collect') else df_for_duck
duck.close()
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
var_groupby_2903923800528 = var_formula_2903923791088.group_by(['order_year_month']).agg([
    pl.col('net_revenue_usd').sum().alias('revenue_usd'),
    pl.col('gross_margin_usd').sum().alias('margin_usd'),
    pl.col('order_id').n_unique().alias('orders')
])
var_groupby_2903923800528 = normalize_to_supported_dtypes(var_groupby_2903923800528)
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
var_groupby_2903924354384 = var_formula_2903923791088.group_by(['category']).agg([
    pl.col('net_revenue_usd').sum().alias('revenue_usd'),
    pl.col('gross_margin_usd').sum().alias('margin_usd'),
    pl.col('order_id').n_unique().alias('orders')
])
var_groupby_2903924354384 = normalize_to_supported_dtypes(var_groupby_2903924354384)
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
var_groupby_2903924199568 = var_formula_2903923791088.group_by(['region', 'channel_group']).agg([
    pl.col('net_revenue_usd').sum().alias('revenue_usd'),
    pl.col('gross_margin_usd').sum().alias('margin_usd'),
    pl.col('order_id').n_unique().alias('orders')
])
var_groupby_2903924199568 = normalize_to_supported_dtypes(var_groupby_2903924199568)
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
var_groupby_2903924201488 = var_formula_2903923791088.group_by(['segment', 'risk_band']).agg([
    pl.col('net_revenue_usd').sum().alias('revenue_usd'),
    pl.col('gross_margin_usd').sum().alias('margin_usd'),
    pl.col('order_id').n_unique().alias('orders')
])
var_groupby_2903924201488 = normalize_to_supported_dtypes(var_groupby_2903924201488)
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
var_groupby_2903924203408 = var_formula_2903923791088.group_by(['customer_id']).agg([
    pl.col('net_revenue_usd').sum().alias('revenue_usd'),
    pl.col('order_id').n_unique().alias('orders')
])
var_groupby_2903924203408 = normalize_to_supported_dtypes(var_groupby_2903924203408)
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
var_groupby_2903924098064 = var_formula_2903923791088.group_by(['supplier_id', 'supplier_name', 'country']).agg([
    pl.col('net_revenue_usd').sum().alias('revenue_usd'),
    pl.col('order_id').n_unique().alias('orders'),
    pl.col('lead_time_days').first().alias('lead_time_days'),
    pl.col('reliability_score').first().alias('reliability_score')
])
var_groupby_2903924098064 = normalize_to_supported_dtypes(var_groupby_2903924098064)
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
var_groupby_2903924107344 = var_formula_2903923791088.group_by(['currency']).agg([
    pl.col('net_revenue_usd').sum().alias('revenue_usd'),
    pl.col('order_id').n_unique().alias('orders'),
    pl.col('usd_rate').first().alias('usd_rate')
])
var_groupby_2903924107344 = normalize_to_supported_dtypes(var_groupby_2903924107344)
var_select_2903923971152 = var_formula_2903923791088.select(['brand', 'category', 'channel_group', 'channel_id', 'channel_name', 'country', 'currency', 'customer_age_band', 'customer_country', 'customer_currency', 'customer_email', 'customer_id', 'discount_pct', 'is_digital', 'is_returned', 'launch_date', 'lead_time_days', 'loyalty_tier', 'order_id', 'order_ts', 'payment_method', 'product_id', 'product_name', 'quantity', 'region', 'reliability_score', 'segment', 'shipping_local', 'signup_date', 'sku', 'status', 'subcategory', 'supplier_id', 'supplier_name', 'tax_local', 'unit_cost', 'unit_price', 'unit_price_local', 'currency_name', 'usd_rate', 'g', 'gross_local', 'discount_local', 'net_local', 'total_local', 'unit_price_usd', 'net_revenue_usd', 'tax_usd', 'shipping_usd', 'total_usd', 'cogs_usd', 'gross_margin_usd', 'margin_pct', 'order_year', 'order_month', 'order_year_month', 'is_bulk', 'value_band', 'risk_score', 'risk_band', 'customer_name'])
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('brand').cast(pl.String, strict=False).alias('brand')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('category').cast(pl.String, strict=False).alias('category')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('channel_group').cast(pl.String, strict=False).alias('channel_group')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('channel_id').cast(pl.Int64, strict=False).alias('channel_id')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('channel_name').cast(pl.String, strict=False).alias('channel_name')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('country').cast(pl.String, strict=False).alias('country')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('currency').cast(pl.String, strict=False).alias('currency')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('customer_age_band').cast(pl.String, strict=False).alias('customer_age_band')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('customer_country').cast(pl.String, strict=False).alias('customer_country')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('customer_currency').cast(pl.String, strict=False).alias('customer_currency')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('customer_email').cast(pl.String, strict=False).alias('customer_email')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('customer_id').cast(pl.Int64, strict=False).alias('customer_id')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('discount_pct').cast(pl.Float64, strict=False).alias('discount_pct')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.when(pl.col('is_digital').cast(pl.String, strict=False).str.to_lowercase().str.strip_chars().is_in(('true', '1', 'yes', 'y', 't', 'on'))).then(True)
    .when(pl.col('is_digital').cast(pl.String, strict=False).str.to_lowercase().str.strip_chars().is_in(('false', '0', 'no', 'n', 'f', 'off'))).then(False)
    .when(pl.col('is_digital').cast(pl.Float64, strict=False).is_not_null() & (pl.col('is_digital').cast(pl.Float64, strict=False) != 0.0)).then(True)
    .when(pl.col('is_digital').cast(pl.Float64, strict=False).is_not_null()).then(False)
    .otherwise(None)
    .alias('is_digital')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.when(pl.col('is_returned').cast(pl.String, strict=False).str.to_lowercase().str.strip_chars().is_in(('true', '1', 'yes', 'y', 't', 'on'))).then(True)
    .when(pl.col('is_returned').cast(pl.String, strict=False).str.to_lowercase().str.strip_chars().is_in(('false', '0', 'no', 'n', 'f', 'off'))).then(False)
    .when(pl.col('is_returned').cast(pl.Float64, strict=False).is_not_null() & (pl.col('is_returned').cast(pl.Float64, strict=False) != 0.0)).then(True)
    .when(pl.col('is_returned').cast(pl.Float64, strict=False).is_not_null()).then(False)
    .otherwise(None)
    .alias('is_returned')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
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
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('lead_time_days').cast(pl.Int64, strict=False).alias('lead_time_days')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('loyalty_tier').cast(pl.String, strict=False).alias('loyalty_tier')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('order_id').cast(pl.String, strict=False).alias('order_id')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('order_ts').cast(pl.String, strict=False).alias('order_ts')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('payment_method').cast(pl.String, strict=False).alias('payment_method')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('product_id').cast(pl.Int64, strict=False).alias('product_id')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('product_name').cast(pl.String, strict=False).alias('product_name')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('quantity').cast(pl.Int64, strict=False).alias('quantity')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('region').cast(pl.String, strict=False).alias('region')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('reliability_score').cast(pl.Float64, strict=False).alias('reliability_score')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('segment').cast(pl.String, strict=False).alias('segment')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('shipping_local').cast(pl.Float64, strict=False).alias('shipping_local')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
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
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('sku').cast(pl.String, strict=False).alias('sku')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('status').cast(pl.String, strict=False).alias('status')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('subcategory').cast(pl.String, strict=False).alias('subcategory')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('supplier_id').cast(pl.Int64, strict=False).alias('supplier_id')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('supplier_name').cast(pl.String, strict=False).alias('supplier_name')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('tax_local').cast(pl.Float64, strict=False).alias('tax_local')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('unit_cost').cast(pl.Float64, strict=False).alias('unit_cost')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('unit_price').cast(pl.Float64, strict=False).alias('unit_price')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('unit_price_local').cast(pl.Float64, strict=False).alias('unit_price_local')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('currency_name').cast(pl.String, strict=False).alias('currency_name')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('usd_rate').cast(pl.Float64, strict=False).alias('usd_rate')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('g').cast(pl.Float64, strict=False).alias('g')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('gross_local').cast(pl.Float64, strict=False).alias('gross_local')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('discount_local').cast(pl.Float64, strict=False).alias('discount_local')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('net_local').cast(pl.Float64, strict=False).alias('net_local')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('total_local').cast(pl.Float64, strict=False).alias('total_local')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('unit_price_usd').cast(pl.Float64, strict=False).alias('unit_price_usd')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('net_revenue_usd').cast(pl.Float64, strict=False).alias('net_revenue_usd')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('tax_usd').cast(pl.Float64, strict=False).alias('tax_usd')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('shipping_usd').cast(pl.Float64, strict=False).alias('shipping_usd')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('total_usd').cast(pl.Float64, strict=False).alias('total_usd')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('cogs_usd').cast(pl.Float64, strict=False).alias('cogs_usd')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('gross_margin_usd').cast(pl.Float64, strict=False).alias('gross_margin_usd')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('margin_pct').cast(pl.Float64, strict=False).alias('margin_pct')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('order_year').cast(pl.Int64, strict=False).alias('order_year')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('order_month').cast(pl.Int64, strict=False).alias('order_month')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('order_year_month').cast(pl.String, strict=False).alias('order_year_month')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.when(pl.col('is_bulk').cast(pl.String, strict=False).str.to_lowercase().str.strip_chars().is_in(('true', '1', 'yes', 'y', 't', 'on'))).then(True)
    .when(pl.col('is_bulk').cast(pl.String, strict=False).str.to_lowercase().str.strip_chars().is_in(('false', '0', 'no', 'n', 'f', 'off'))).then(False)
    .when(pl.col('is_bulk').cast(pl.Float64, strict=False).is_not_null() & (pl.col('is_bulk').cast(pl.Float64, strict=False) != 0.0)).then(True)
    .when(pl.col('is_bulk').cast(pl.Float64, strict=False).is_not_null()).then(False)
    .otherwise(None)
    .alias('is_bulk')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('value_band').cast(pl.String, strict=False).alias('value_band')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('risk_score').cast(pl.Int64, strict=False).alias('risk_score')
)
var_select_2903923971152 = var_select_2903923971152.with_columns(
    pl.col('risk_band').cast(pl.String, strict=False).alias('risk_band')
)
var_sort_2903923794288 = var_groupby_2903923800528.sort('order_year_month', descending=False)
var_sort_2903924356304 = var_groupby_2903924354384.sort('revenue_usd', descending=True)
var_sort_2903924196048 = var_groupby_2903924199568.sort(['region', 'channel_group'], descending=[False, False])
var_sort_2903923976592 = var_groupby_2903924201488.sort(['segment', 'risk_band'], descending=[False, False])
# Filter data into true and false results
var_t_filter_2903924208848 = var_groupby_2903924203408.filter(pl.col('revenue_usd') > 4000)
var_f_filter_2903924208848 = var_groupby_2903924203408.filter(~(pl.col('revenue_usd') > 4000))
var_sort_2903924099984 = var_groupby_2903924098064.sort('revenue_usd', descending=True)
var_sort_2903924105424 = var_groupby_2903924107344.sort('revenue_usd', descending=True)
import duckdb
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_select_2903923971152.collect() if hasattr(var_select_2903923971152, 'collect') else var_select_2903923971152
duck.register('df_step_0', df_for_duck)
df_for_duck = duck.execute('''SELECT *, "gross_local" * "usd_rate" AS "gross_revenue_usd_raw" FROM df_step_0''').pl()
duck.register('df_step_1', df_for_duck)
df_for_duck = duck.execute('''SELECT *, CASE WHEN "risk_band" = 'High' THEN 1 ELSE 0 END AS "is_high_risk" FROM df_step_1''').pl()
# Widen DuckDB-native types into Select-supported dtypes
df_for_duck = normalize_to_supported_dtypes(df_for_duck)
# Preserve lazy execution when the incoming value is lazy
var_formula_2903924112784 = df_for_duck.lazy() if hasattr(var_select_2903923971152, 'collect') else df_for_duck
duck.close()
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
var_runtot_2903924251120 = var_sort_2903923794288.with_columns([
    pl.col("revenue_usd").cum_sum().alias("RunTot_revenue_usd")
])
var_runtot_2903924251120 = normalize_to_supported_dtypes(var_runtot_2903924251120)
# Ensure we're working with a LazyFrame for memory efficiency
if var_sort_2903924356304 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_sort_2903924356304, pl.DataFrame):
        var_sort_2903924356304_lazy = var_sort_2903924356304.lazy()
    elif isinstance(var_sort_2903924356304, pl.LazyFrame):
        var_sort_2903924356304_lazy = var_sort_2903924356304
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_sort_2903924356304)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_sort_2903924356304_lazy.sink_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/category_revenue.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/category_revenue.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
# Ensure we're working with a LazyFrame for memory efficiency
if var_sort_2903924196048 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_sort_2903924196048, pl.DataFrame):
        var_sort_2903924196048_lazy = var_sort_2903924196048.lazy()
    elif isinstance(var_sort_2903924196048, pl.LazyFrame):
        var_sort_2903924196048_lazy = var_sort_2903924196048
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_sort_2903924196048)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_sort_2903924196048_lazy.sink_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/region_channel_revenue.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/region_channel_revenue.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
# Ensure we're working with a LazyFrame for memory efficiency
if var_sort_2903923976592 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_sort_2903923976592, pl.DataFrame):
        var_sort_2903923976592_lazy = var_sort_2903923976592.lazy()
    elif isinstance(var_sort_2903923976592, pl.LazyFrame):
        var_sort_2903923976592_lazy = var_sort_2903923976592
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_sort_2903923976592)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_sort_2903923976592_lazy.sink_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/segment_revenue.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/segment_revenue.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
var_sort_2903924206928 = var_t_filter_2903924208848.sort('revenue_usd', descending=True)
import duckdb
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_sort_2903924099984.collect() if hasattr(var_sort_2903924099984, 'collect') else var_sort_2903924099984
duck.register('df_step_0', df_for_duck)
df_for_duck = duck.execute('''SELECT *, "revenue_usd" / "lead_time_days" AS "revenue_per_lead_day" FROM df_step_0''').pl()
# Widen DuckDB-native types into Select-supported dtypes
df_for_duck = normalize_to_supported_dtypes(df_for_duck)
# Preserve lazy execution when the incoming value is lazy
var_formula_2903924101904 = df_for_duck.lazy() if hasattr(var_sort_2903924099984, 'collect') else df_for_duck
duck.close()
# Ensure we're working with a LazyFrame for memory efficiency
if var_sort_2903924105424 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_sort_2903924105424, pl.DataFrame):
        var_sort_2903924105424_lazy = var_sort_2903924105424.lazy()
    elif isinstance(var_sort_2903924105424, pl.LazyFrame):
        var_sort_2903924105424_lazy = var_sort_2903924105424
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_sort_2903924105424)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_sort_2903924105424_lazy.sink_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/fx_exposure.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/fx_exposure.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
var_groupby_2903924110864 = var_formula_2903924112784.select([
    pl.col('order_id').n_unique().alias('clean_orders'),
    pl.col('net_revenue_usd').sum().alias('net_revenue_usd'),
    pl.col('gross_margin_usd').sum().alias('gross_margin_usd'),
    pl.col('is_returned').sum().alias('returned_orders'),
    pl.col('customer_id').n_unique().alias('distinct_customers'),
    pl.col('product_id').n_unique().alias('distinct_products'),
    pl.col('gross_revenue_usd_raw').sum().alias('gross_revenue_usd_raw'),
    pl.col('is_high_risk').sum().alias('high_risk_orders')
])
var_groupby_2903924110864 = normalize_to_supported_dtypes(var_groupby_2903924110864)
var_select_2903924256400 = var_runtot_2903924251120.select(['order_year_month', 'revenue_usd', 'margin_usd', 'orders', 'RunTot_revenue_usd'])
var_select_2903924256400 = var_select_2903924256400.with_columns(
    pl.col('order_year_month').cast(pl.String, strict=False).alias('order_year_month')
)
var_select_2903924256400 = var_select_2903924256400.with_columns(
    pl.col('revenue_usd').cast(pl.Float64, strict=False).alias('revenue_usd')
)
var_select_2903924256400 = var_select_2903924256400.with_columns(
    pl.col('margin_usd').cast(pl.Float64, strict=False).alias('margin_usd')
)
var_select_2903924256400 = var_select_2903924256400.with_columns(
    pl.col('RunTot_revenue_usd').cast(pl.Float64, strict=False).alias('RunTot_revenue_usd')
)
var_select_2903924256400 = var_select_2903924256400.rename({'RunTot_revenue_usd': 'cumulative_revenue_usd'})
# Ensure we're working with a LazyFrame for memory efficiency
if var_sort_2903924206928 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_sort_2903924206928, pl.DataFrame):
        var_sort_2903924206928_lazy = var_sort_2903924206928.lazy()
    elif isinstance(var_sort_2903924206928, pl.LazyFrame):
        var_sort_2903924206928_lazy = var_sort_2903924206928
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_sort_2903924206928)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_sort_2903924206928_lazy.sink_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/top_customers.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/top_customers.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
# Ensure we're working with a LazyFrame for memory efficiency
if var_formula_2903924101904 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_formula_2903924101904, pl.DataFrame):
        var_formula_2903924101904_lazy = var_formula_2903924101904.lazy()
    elif isinstance(var_formula_2903924101904, pl.LazyFrame):
        var_formula_2903924101904_lazy = var_formula_2903924101904
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_formula_2903924101904)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_formula_2903924101904_lazy.sink_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/supplier_performance.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/supplier_performance.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
var_select_2903923969072 = var_groupby_2903924110864.select(['clean_orders', 'gross_revenue_usd_raw', 'net_revenue_usd', 'gross_margin_usd', 'returned_orders', 'distinct_customers', 'distinct_products', 'high_risk_orders'])
var_select_2903923969072 = var_select_2903923969072.with_columns(
    pl.col('clean_orders').cast(pl.Int64, strict=False).alias('clean_orders')
)
var_select_2903923969072 = var_select_2903923969072.with_columns(
    pl.col('gross_revenue_usd_raw').cast(pl.Float64, strict=False).alias('gross_revenue_usd_raw')
)
var_select_2903923969072 = var_select_2903923969072.with_columns(
    pl.col('net_revenue_usd').cast(pl.Float64, strict=False).alias('net_revenue_usd')
)
var_select_2903923969072 = var_select_2903923969072.with_columns(
    pl.col('gross_margin_usd').cast(pl.Float64, strict=False).alias('gross_margin_usd')
)
var_select_2903923969072 = var_select_2903923969072.with_columns(
    pl.col('returned_orders').cast(pl.Int64, strict=False).alias('returned_orders')
)
var_select_2903923969072 = var_select_2903923969072.with_columns(
    pl.col('distinct_customers').cast(pl.Int64, strict=False).alias('distinct_customers')
)
var_select_2903923969072 = var_select_2903923969072.with_columns(
    pl.col('distinct_products').cast(pl.Int64, strict=False).alias('distinct_products')
)
var_select_2903923969072 = var_select_2903923969072.with_columns(
    pl.col('high_risk_orders').cast(pl.Int64, strict=False).alias('high_risk_orders')
)
var_select_2903923969072 = var_select_2903923969072.rename({'gross_revenue_usd_raw': 'gross_revenue_usd'})
# Ensure we're working with a LazyFrame for memory efficiency
if var_select_2903924256400 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_select_2903924256400, pl.DataFrame):
        var_select_2903924256400_lazy = var_select_2903924256400.lazy()
    elif isinstance(var_select_2903924256400, pl.LazyFrame):
        var_select_2903924256400_lazy = var_select_2903924256400
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_select_2903924256400)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_select_2903924256400_lazy.sink_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/monthly_revenue.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/monthly_revenue.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
_2903924346224_cols = (var_select_2903924256400.collect_schema().names() if isinstance(var_select_2903924256400, pl.LazyFrame) else var_select_2903924256400.columns)
# Validate data columns
missing = [col for col in ['revenue_usd', 'margin_usd', 'orders'] if col not in _2903924346224_cols]
if missing:
    print(f'Warning: Missing columns will be skipped: {missing}')

# Filter to existing columns
valid_key_cols = [col for col in ['order_year_month'] if col in _2903924346224_cols]
valid_data_cols = [col for col in ['revenue_usd', 'margin_usd', 'orders'] if col in _2903924346224_cols]

# Transpose operation using Polars unpivot
var_transpose_2903924346224 = var_select_2903924256400.unpivot(
    index=valid_key_cols,
    on=valid_data_cols,
    variable_name='Name',
    value_name='Value'
)
# Widen unpivot supertypes into Select-supported dtypes
var_transpose_2903924346224 = normalize_to_supported_dtypes(var_transpose_2903924346224)
import duckdb
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
# Initialize DuckDB connection
duck = duckdb.connect(':memory:')
# Convert polars LazyFrame to DataFrame if needed for DuckDB
df_for_duck = var_select_2903923969072.collect() if hasattr(var_select_2903923969072, 'collect') else var_select_2903923969072
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
var_formula_2903923967312 = df_for_duck.lazy() if hasattr(var_select_2903923969072, 'collect') else df_for_duck
duck.close()
var_select_2903924350864 = var_transpose_2903924346224.select(['order_year_month', 'Name', 'Value'])
var_select_2903924350864 = var_select_2903924350864.with_columns(
    pl.col('order_year_month').cast(pl.String, strict=False).alias('order_year_month')
)
var_select_2903924350864 = var_select_2903924350864.with_columns(
    pl.col('Name').cast(pl.String, strict=False).alias('Name')
)
var_select_2903924350864 = var_select_2903924350864.with_columns(
    pl.col('Value').cast(pl.Float64, strict=False).alias('Value')
)
var_select_2903924350864 = var_select_2903924350864.rename({'Name': 'metric', 'Value': 'value'})
var_select_2903923972912 = var_formula_2903923967312.select(['clean_orders', 'gross_revenue_usd', 'net_revenue_usd', 'gross_margin_usd', 'margin_pct', 'returned_orders', 'high_risk_orders', 'distinct_customers', 'distinct_products'])
var_select_2903923972912 = var_select_2903923972912.with_columns(
    pl.col('clean_orders').cast(pl.Int64, strict=False).alias('clean_orders')
)
var_select_2903923972912 = var_select_2903923972912.with_columns(
    pl.col('gross_revenue_usd').cast(pl.Float64, strict=False).alias('gross_revenue_usd')
)
var_select_2903923972912 = var_select_2903923972912.with_columns(
    pl.col('net_revenue_usd').cast(pl.Float64, strict=False).alias('net_revenue_usd')
)
var_select_2903923972912 = var_select_2903923972912.with_columns(
    pl.col('gross_margin_usd').cast(pl.Float64, strict=False).alias('gross_margin_usd')
)
var_select_2903923972912 = var_select_2903923972912.with_columns(
    pl.col('margin_pct').cast(pl.Float64, strict=False).alias('margin_pct')
)
var_select_2903923972912 = var_select_2903923972912.with_columns(
    pl.col('returned_orders').cast(pl.Int64, strict=False).alias('returned_orders')
)
var_select_2903923972912 = var_select_2903923972912.with_columns(
    pl.col('high_risk_orders').cast(pl.Int64, strict=False).alias('high_risk_orders')
)
var_select_2903923972912 = var_select_2903923972912.with_columns(
    pl.col('distinct_customers').cast(pl.Int64, strict=False).alias('distinct_customers')
)
var_select_2903923972912 = var_select_2903923972912.with_columns(
    pl.col('distinct_products').cast(pl.Int64, strict=False).alias('distinct_products')
)
# Ensure we're working with a LazyFrame for memory efficiency
if var_select_2903924350864 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_select_2903924350864, pl.DataFrame):
        var_select_2903924350864_lazy = var_select_2903924350864.lazy()
    elif isinstance(var_select_2903924350864, pl.LazyFrame):
        var_select_2903924350864_lazy = var_select_2903924350864
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_select_2903924350864)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_select_2903924350864_lazy.sink_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/monthly_revenue_long.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/monthly_revenue_long.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
import polars as pl
from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
_2907286822480_cols = (var_select_2903923972912.collect_schema().names() if isinstance(var_select_2903923972912, pl.LazyFrame) else var_select_2903923972912.columns)
# Validate data columns
missing = [col for col in ['clean_orders', 'gross_revenue_usd', 'net_revenue_usd', 'gross_margin_usd', 'margin_pct', 'returned_orders', 'high_risk_orders', 'distinct_customers', 'distinct_products'] if col not in _2907286822480_cols]
if missing:
    print(f'Warning: Missing columns will be skipped: {missing}')

# Filter to existing columns
valid_key_cols = [col for col in [] if col in _2907286822480_cols]
valid_data_cols = [col for col in ['clean_orders', 'gross_revenue_usd', 'net_revenue_usd', 'gross_margin_usd', 'margin_pct', 'returned_orders', 'high_risk_orders', 'distinct_customers', 'distinct_products'] if col in _2907286822480_cols]

# Transpose operation using Polars unpivot
var_transpose_2907286822480 = var_select_2903923972912.unpivot(
    index=valid_key_cols,
    on=valid_data_cols,
    variable_name='Name',
    value_name='Value'
)
# Widen unpivot supertypes into Select-supported dtypes
var_transpose_2907286822480 = normalize_to_supported_dtypes(var_transpose_2907286822480)
# Ensure we're working with a LazyFrame for memory efficiency
if var_transpose_2907286822480 is not None:
    # Check if we have a LazyFrame or DataFrame
    import polars as pl
    if isinstance(var_transpose_2907286822480, pl.DataFrame):
        var_transpose_2907286822480_lazy = var_transpose_2907286822480.lazy()
    elif isinstance(var_transpose_2907286822480, pl.LazyFrame):
        var_transpose_2907286822480_lazy = var_transpose_2907286822480
    else:
        raise TypeError(f'Expected pl.DataFrame or pl.LazyFrame, got {type(var_transpose_2907286822480)}')

    try:
        # Using LazyFrame sink for optimal memory usage
        var_transpose_2907286822480_lazy.sink_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/kpi_summary.csv')
        print(f'[SUCCESS] Successfully saved data to C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/kpi_summary.csv using LazyFrame')
    except Exception as e:
        print(f'[ERROR] Failed to save file: {e}')
        raise e
else:
    print('[WARNING] No data to save')
