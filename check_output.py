import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_2258982732976 = pl.scan_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/data/channels.csv', infer_schema=False)

# var_file_input_2258982732976 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_2258982734576 = pl.scan_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/data/orders.csv', infer_schema=False)

# var_file_input_2258982734576 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_2258982736016 = pl.scan_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/data/customers.csv', infer_schema=False)

# var_file_input_2258982736016 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_2258982737296 = pl.scan_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/data/products.csv', infer_schema=False)

# var_file_input_2258982737296 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_2258982738736 = pl.scan_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/data/suppliers.csv', infer_schema=False)

# var_file_input_2258982738736 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_2258982740176 = pl.scan_csv('C:/Projects/TriggerEditor/savedfiles/Example_2_Retail_Ledger/data/fx_rates.csv', infer_schema=False)

# var_file_input_2258982740176 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
var_select_2258982743376 = var_file_input_2258982732976.select(['channel_id', 'channel_name', 'channel_group', 'is_digital'])
var_select_2258982743376 = var_select_2258982743376.with_columns(
    pl.col('channel_id').cast(pl.Int64, strict=False).alias('channel_id')
)
var_select_2258982743376 = var_select_2258982743376.with_columns(
    pl.col('channel_name').cast(pl.String, strict=False).alias('channel_name')
)
var_select_2258982743376 = var_select_2258982743376.with_columns(
    pl.col('channel_group').cast(pl.String, strict=False).alias('channel_group')
)
var_select_2258982743376 = var_select_2258982743376.with_columns(
    pl.col('is_digital').cast(pl.String, strict=False).alias('is_digital')
)
var_select_2258982741616 = var_file_input_2258982734576.select([' Order ID ', 'Customer_Id', 'PRODUCT_ID', 'supplier id', 'Channel ID', 'Currency', 'Order TS', 'Quantity', 'unit_price_local', 'Discount Pct', 'tax_local', 'shipping_local', 'Status', 'Payment Method', 'is_returned'])
var_select_2258982741616 = var_select_2258982741616.with_columns(
    pl.col(' Order ID ').cast(pl.Int64, strict=False).alias(' Order ID ')
)
var_select_2258982741616 = var_select_2258982741616.with_columns(
    pl.col('Customer_Id').cast(pl.Int64, strict=False).alias('Customer_Id')
)
var_select_2258982741616 = var_select_2258982741616.with_columns(
    pl.col('PRODUCT_ID').cast(pl.Int64, strict=False).alias('PRODUCT_ID')
)
var_select_2258982741616 = var_select_2258982741616.with_columns(
    pl.col('supplier id').cast(pl.Int64, strict=False).alias('supplier id')
)
var_select_2258982741616 = var_select_2258982741616.with_columns(
    pl.col('Channel ID').cast(pl.Int64, strict=False).alias('Channel ID')
)
var_select_2258982741616 = var_select_2258982741616.with_columns(
    pl.col('Currency').cast(pl.String, strict=False).alias('Currency')
)
var_select_2258982741616 = var_select_2258982741616.with_columns(
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
var_select_2258982741616 = var_select_2258982741616.with_columns(
    pl.col('Quantity').cast(pl.Int64, strict=False).alias('Quantity')
)
var_select_2258982741616 = var_select_2258982741616.with_columns(
    pl.col('unit_price_local').cast(pl.Float64, strict=False).alias('unit_price_local')
)
var_select_2258982741616 = var_select_2258982741616.with_columns(
    pl.col('Discount Pct').cast(pl.Float64, strict=False).alias('Discount Pct')
)
var_select_2258982741616 = var_select_2258982741616.with_columns(
    pl.col('tax_local').cast(pl.Float64, strict=False).alias('tax_local')
)
var_select_2258982741616 = var_select_2258982741616.with_columns(
    pl.col('shipping_local').cast(pl.Float64, strict=False).alias('shipping_local')
)
var_select_2258982741616 = var_select_2258982741616.with_columns(
    pl.col('Status').cast(pl.String, strict=False).alias('Status')
)
var_select_2258982741616 = var_select_2258982741616.with_columns(
    pl.col('Payment Method').cast(pl.String, strict=False).alias('Payment Method')
)
var_select_2258982741616 = var_select_2258982741616.with_columns(
    pl.col('is_returned').cast(pl.String, strict=False).alias('is_returned')
)
var_select_2258982745136 = var_file_input_2258982736016.select(['customer_id', 'email', 'full_name', 'signup_date', 'country', 'region', 'currency', 'segment', 'age_band', 'loyalty_tier'])
var_select_2258982745136 = var_select_2258982745136.with_columns(
    pl.col('customer_id').cast(pl.Int64, strict=False).alias('customer_id')
)
var_select_2258982745136 = var_select_2258982745136.with_columns(
    pl.col('email').cast(pl.String, strict=False).alias('email')
)
var_select_2258982745136 = var_select_2258982745136.with_columns(
    pl.col('full_name').cast(pl.String, strict=False).alias('full_name')
)
var_select_2258982745136 = var_select_2258982745136.with_columns(
    pl.col('signup_date').cast(pl.String, strict=False).alias('signup_date')
)
var_select_2258982745136 = var_select_2258982745136.with_columns(
    pl.col('country').cast(pl.String, strict=False).alias('country')
)
var_select_2258982745136 = var_select_2258982745136.with_columns(
    pl.col('region').cast(pl.String, strict=False).alias('region')
)
var_select_2258982745136 = var_select_2258982745136.with_columns(
    pl.col('currency').cast(pl.String, strict=False).alias('currency')
)
var_select_2258982745136 = var_select_2258982745136.with_columns(
    pl.col('segment').cast(pl.String, strict=False).alias('segment')
)
var_select_2258982745136 = var_select_2258982745136.with_columns(
    pl.col('age_band').cast(pl.String, strict=False).alias('age_band')
)
var_select_2258982745136 = var_select_2258982745136.with_columns(
    pl.col('loyalty_tier').cast(pl.String, strict=False).alias('loyalty_tier')
)
var_select_2258982746896 = var_file_input_2258982737296.select(['product_id', 'sku', 'product_name', 'category', 'subcategory', 'brand', 'unit_price', 'unit_cost', 'launch_date'])
var_select_2258982746896 = var_select_2258982746896.with_columns(
    pl.col('product_id').cast(pl.Int64, strict=False).alias('product_id')
)
var_select_2258982746896 = var_select_2258982746896.with_columns(
    pl.col('sku').cast(pl.String, strict=False).alias('sku')
)
var_select_2258982746896 = var_select_2258982746896.with_columns(
    pl.col('product_name').cast(pl.String, strict=False).alias('product_name')
)
var_select_2258982746896 = var_select_2258982746896.with_columns(
    pl.col('category').cast(pl.String, strict=False).alias('category')
)
var_select_2258982746896 = var_select_2258982746896.with_columns(
    pl.col('subcategory').cast(pl.String, strict=False).alias('subcategory')
)
var_select_2258982746896 = var_select_2258982746896.with_columns(
    pl.col('brand').cast(pl.String, strict=False).alias('brand')
)
var_select_2258982746896 = var_select_2258982746896.with_columns(
    pl.col('unit_price').cast(pl.Float64, strict=False).alias('unit_price')
)
var_select_2258982746896 = var_select_2258982746896.with_columns(
    pl.col('unit_cost').cast(pl.Float64, strict=False).alias('unit_cost')
)
var_select_2258982746896 = var_select_2258982746896.with_columns(
    pl.col('launch_date').cast(pl.String, strict=False).alias('launch_date')
)
var_select_2259231867440 = var_file_input_2258982738736.select(['supplier_id', 'supplier_name', 'country', 'lead_time_days', 'reliability_score'])
var_select_2259231867440 = var_select_2259231867440.with_columns(
    pl.col('supplier_id').cast(pl.Int64, strict=False).alias('supplier_id')
)
var_select_2259231867440 = var_select_2259231867440.with_columns(
    pl.col('supplier_name').cast(pl.String, strict=False).alias('supplier_name')
)
var_select_2259231867440 = var_select_2259231867440.with_columns(
    pl.col('country').cast(pl.String, strict=False).alias('country')
)
var_select_2259231867440 = var_select_2259231867440.with_columns(
    pl.col('lead_time_days').cast(pl.String, strict=False).alias('lead_time_days')
)
var_select_2259231867440 = var_select_2259231867440.with_columns(
    pl.col('reliability_score').cast(pl.String, strict=False).alias('reliability_score')
)
var_select_2259231869200 = var_file_input_2258982740176.select(['currency', 'currency_name', 'usd_rate'])
import polars as pl
# Normalize column names (11 renamed)
var_normalize_columns_2259231882480 = var_select_2258982741616.rename({' Order ID ': 'order_id', 'Customer_Id': 'customer_id', 'PRODUCT_ID': 'product_id', 'supplier id': 'supplier_id', 'Channel ID': 'channel_id', 'Currency': 'currency', 'Order TS': 'order_ts', 'Quantity': 'quantity', 'Discount Pct': 'discount_pct', 'Status': 'status', 'Payment Method': 'payment_method'})
from trigger_designer.core.utils.cleansing_util import DataCleansing, NullStrategy
import polars as pl
# Convert LazyFrame to DataFrame if needed
_cleansing_input = var_normalize_columns_2259231882480.collect() if hasattr(var_normalize_columns_2259231882480, 'collect') else var_normalize_columns_2259231882480
cleaner = DataCleansing(_cleansing_input)
cleaner.replace_null_defaults(replace_strings=True, replace_numbers=True)
cleaner.strip_whitespace(remove_all=False, normalize_spaces=True, fields=['is_returned'])
cleaner.modify_case('lower', fields=['is_returned'])
var_cleansing_2259231870960 = cleaner.get_result()
from trigger_designer.core.utils.cleansing_util import DataCleansing, NullStrategy
import polars as pl
# Convert LazyFrame to DataFrame if needed
_cleansing_input = var_cleansing_2259231870960.collect() if hasattr(var_cleansing_2259231870960, 'collect') else var_cleansing_2259231870960
cleaner = DataCleansing(_cleansing_input)
cleaner.remove_rows_with_nulls(fields=['Customer_Id', 'PRODUCT_ID', 'is_returned'])
cleaner.replace_null_defaults(replace_strings=True, replace_numbers=True)
cleaner.strip_whitespace(remove_all=False, normalize_spaces=True, fields=['Customer_Id', 'PRODUCT_ID', 'is_returned'])
cleaner.modify_case('lower', fields=['Customer_Id', 'PRODUCT_ID', 'is_returned'])
var_cleansing_2259231874480 = cleaner.get_result()
import duckdb
import polars as pl
# Filter rows with a SQL WHERE clause (no new columns)
df_for_duck = var_cleansing_2259231874480.collect() if hasattr(var_cleansing_2259231874480, 'collect') else var_cleansing_2259231874480
duck = duckdb.connect(':memory:')
duck.register('df_filter', df_for_duck)
var_t_filter_2259231876240 = duck.execute('SELECT * FROM df_filter WHERE "quantity" BETWEEN 0 AND 500').pl()
var_f_filter_2259231876240 = duck.execute('SELECT * FROM df_filter WHERE NOT ("quantity" BETWEEN 0 AND 500)').pl()
# Preserve lazy execution when the incoming value is lazy
var_t_filter_2259231876240 = var_t_filter_2259231876240.lazy() if hasattr(var_cleansing_2259231874480, 'collect') else var_t_filter_2259231876240
var_f_filter_2259231876240 = var_f_filter_2259231876240.lazy() if hasattr(var_cleansing_2259231874480, 'collect') else var_f_filter_2259231876240
duck.close()
import duckdb
import polars as pl
# Filter rows with a SQL WHERE clause (no new columns)
df_for_duck = var_t_filter_2259231876240.collect() if hasattr(var_t_filter_2259231876240, 'collect') else var_t_filter_2259231876240
duck = duckdb.connect(':memory:')
duck.register('df_filter', df_for_duck)
var_t_filter_2259231878320 = duck.execute('SELECT * FROM df_filter WHERE "unit_price_local" > 0 and \n"unit_price_local" <= 5000').pl()
var_f_filter_2259231878320 = duck.execute('SELECT * FROM df_filter WHERE NOT ("unit_price_local" > 0 and \n"unit_price_local" <= 5000)').pl()
# Preserve lazy execution when the incoming value is lazy
var_t_filter_2259231878320 = var_t_filter_2259231878320.lazy() if hasattr(var_t_filter_2259231876240, 'collect') else var_t_filter_2259231878320
var_f_filter_2259231878320 = var_f_filter_2259231878320.lazy() if hasattr(var_t_filter_2259231876240, 'collect') else var_f_filter_2259231878320
duck.close()
import duckdb
import polars as pl
# Filter rows with a SQL WHERE clause (no new columns)
df_for_duck = var_t_filter_2259231878320.collect() if hasattr(var_t_filter_2259231878320, 'collect') else var_t_filter_2259231878320
duck = duckdb.connect(':memory:')
duck.register('df_filter', df_for_duck)
var_t_filter_2259231880400 = duck.execute('SELECT * FROM df_filter WHERE YEAR("order_ts") <= 2025 AND\nLOWER("is_returned") = \'true\'').pl()
var_f_filter_2259231880400 = duck.execute('SELECT * FROM df_filter WHERE NOT (YEAR("order_ts") <= 2025 AND\nLOWER("is_returned") = \'true\')').pl()
# Preserve lazy execution when the incoming value is lazy
var_t_filter_2259231880400 = var_t_filter_2259231880400.lazy() if hasattr(var_t_filter_2259231878320, 'collect') else var_t_filter_2259231880400
var_f_filter_2259231880400 = var_f_filter_2259231880400.lazy() if hasattr(var_t_filter_2259231878320, 'collect') else var_f_filter_2259231880400
duck.close()
