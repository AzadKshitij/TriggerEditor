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
var_file_input_1906953845184 = pl.scan_csv('C:\\Users\\KASHVINCHANDRASAN\\Desktop\\Personal\\Github\\TriggerEditor\\savedfiles\\Example_2_Retail_Ledger\\data\\channels.csv', infer_schema=False)

# var_file_input_1906953845184 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_1905895507072 = pl.scan_csv('C:\\Users\\KASHVINCHANDRASAN\\Desktop\\Personal\\Github\\TriggerEditor\\savedfiles\\Example_2_Retail_Ledger\\data\\orders.csv', infer_schema=False)

# var_file_input_1905895507072 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_1905895512576 = pl.scan_csv('C:\\Users\\KASHVINCHANDRASAN\\Desktop\\Personal\\Github\\TriggerEditor\\savedfiles\\Example_2_Retail_Ledger\\data\\customers.csv', infer_schema=False)

# var_file_input_1905895512576 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_1905895517888 = pl.scan_csv('C:\\Users\\KASHVINCHANDRASAN\\Desktop\\Personal\\Github\\TriggerEditor\\savedfiles\\Example_2_Retail_Ledger\\data\\products.csv', infer_schema=False)

# var_file_input_1905895517888 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_1905895539648 = pl.scan_csv('C:\\Users\\KASHVINCHANDRASAN\\Desktop\\Personal\\Github\\TriggerEditor\\savedfiles\\Example_2_Retail_Ledger\\data\\suppliers.csv', infer_schema=False)

# var_file_input_1905895539648 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
import polars as pl
import os

# Always use LazyFrame for memory efficiency
# Using LazyFrame for optimal memory usage
var_file_input_1905895544256 = pl.scan_csv('C:\\Users\\KASHVINCHANDRASAN\\Desktop\\Personal\\Github\\TriggerEditor\\savedfiles\\Example_2_Retail_Ledger\\data\\fx_rates.csv', infer_schema=False)

# var_file_input_1905895544256 is now a LazyFrame for memory-efficient processing
# Use .collect() only when you need to materialize the data
import json
import polars as pl
from trigger_designer.core.shaping.select import run_node as _run_node
var_select_1905894923200, = _run_node([var_file_input_1905895507072], json.loads('{"auto_accept_new_columns": true, "columns": [{"date_format": "", "dtype": "String", "dtype_custom": false, "name": " Order ID ", "rename": "", "selected": true}, {"date_format": "", "dtype": "Int64", "dtype_custom": true, "name": "Customer_Id", "rename": "", "selected": true}, {"date_format": "", "dtype": "Int64", "dtype_custom": true, "name": "PRODUCT_ID", "rename": "", "selected": true}, {"date_format": "", "dtype": "Int64", "dtype_custom": true, "name": "supplier id", "rename": "", "selected": true}, {"date_format": "", "dtype": "Int64", "dtype_custom": true, "name": "Channel ID", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "Currency", "rename": "", "selected": true}, {"date_format": "", "dtype": "Datetime", "dtype_custom": true, "name": "Order TS", "rename": "", "selected": true}, {"date_format": "", "dtype": "Int64", "dtype_custom": true, "name": "Quantity", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": true, "name": "unit_price_local", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": true, "name": "Discount Pct", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": true, "name": "tax_local", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": true, "name": "shipping_local", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "Status", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "Payment Method", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "is_returned", "rename": "", "selected": true}]}'))
import json
import polars as pl
from trigger_designer.core.shaping.select import run_node as _run_node
var_select_1905895888640, = _run_node([var_file_input_1906953845184], json.loads('{"auto_accept_new_columns": true, "columns": [{"date_format": "", "dtype": "Int64", "dtype_custom": true, "name": "channel_id", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "channel_name", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "channel_group", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "is_digital", "rename": "", "selected": true}]}'))
import json
import polars as pl
from trigger_designer.core.shaping.select import run_node as _run_node
var_select_1905896210624, = _run_node([var_file_input_1905895512576], json.loads('{"auto_accept_new_columns": true, "columns": [{"date_format": "", "dtype": "Int64", "dtype_custom": true, "name": "customer_id", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "email", "rename": "customer_email", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "full_name", "rename": "customer_name", "selected": true}, {"date_format": "", "dtype": "Date", "dtype_custom": true, "name": "signup_date", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "country", "rename": "customer_country", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "region", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "currency", "rename": "customer_currency", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "segment", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "age_band", "rename": "customer_age_band", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "loyalty_tier", "rename": "", "selected": true}]}'))
import json
import polars as pl
from trigger_designer.core.shaping.select import run_node as _run_node
var_select_1905896215680, = _run_node([var_file_input_1905895517888], json.loads('{"auto_accept_new_columns": true, "columns": [{"date_format": "", "dtype": "Int64", "dtype_custom": true, "name": "product_id", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "sku", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "product_name", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "category", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "subcategory", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "brand", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": true, "name": "unit_price", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": true, "name": "unit_cost", "rename": "", "selected": true}, {"date_format": "", "dtype": "Date", "dtype_custom": true, "name": "launch_date", "rename": "", "selected": true}]}'))
import json
import polars as pl
from trigger_designer.core.shaping.select import run_node as _run_node
var_select_1905896218368, = _run_node([var_file_input_1905895539648], json.loads('{"auto_accept_new_columns": true, "columns": [{"date_format": "", "dtype": "Int64", "dtype_custom": true, "name": "supplier_id", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "supplier_name", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "country", "rename": "", "selected": true}, {"date_format": "", "dtype": "Int64", "dtype_custom": true, "name": "lead_time_days", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": true, "name": "reliability_score", "rename": "", "selected": true}]}'))
import json
import polars as pl
from trigger_designer.core.shaping.select import run_node as _run_node
var_select_1905896244800, = _run_node([var_file_input_1905895544256], json.loads('{"auto_accept_new_columns": true, "columns": [{"date_format": "", "dtype": "String", "dtype_custom": false, "name": "currency", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "currency_name", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": true, "name": "usd_rate", "rename": "", "selected": true}]}'))
import json
import polars as pl
from trigger_designer.core.shaping.normalize import run_node as _run_node
var_normalize_1905896615360, = _run_node([var_select_1905894923200], json.loads('{"case_modification": "lower", "remove_all_whitespace": false, "selected_columns": [" Order ID ", "Customer_Id", "PRODUCT_ID", "supplier id", "Channel ID", "Currency", "Order TS", "Quantity", "unit_price_local", "Discount Pct", "tax_local", "shipping_local", "Status", "Payment Method", "is_returned"], "spaces_to_underscore": true, "trim_whitespace": true}'))
import json
import polars as pl
from trigger_designer.core.shaping.cleansing import run_node as _run_node
var_cleansing_1905896251264, = _run_node([var_normalize_1905896615360], json.loads('{"case_modification": "none", "normalize_spaces": true, "remove_all_whitespace": false, "remove_letters": false, "remove_null_columns": false, "remove_null_rows": false, "remove_null_rows_from_selected_columns": false, "remove_numbers": false, "remove_punctuation": false, "replace_null_numbers": false, "replace_null_strings": false, "selected_fields": ["order_id", "customer_id", "product_id", "supplier_id", "channel_id", "currency", "order_ts", "quantity", "unit_price_local", "discount_pct", "tax_local", "shipping_local", "status", "payment_method", "is_returned"], "strip_whitespace": true}'))
import json
import polars as pl
from trigger_designer.core.shaping.formula import run_node as _run_node
var_formula_1905896734656, = _run_node([var_select_1905896244800], json.loads('{"sections": [{"editor_height": 120, "formula_text": "LOWER([currency])", "target_column": "currency", "target_dtype": ""}]}'))
import json
import polars as pl
from trigger_designer.core.shaping.cleansing import run_node as _run_node
var_cleansing_1905914360704, = _run_node([var_cleansing_1905896251264], json.loads('{"case_modification": "lower", "normalize_spaces": true, "remove_all_whitespace": false, "remove_letters": false, "remove_null_columns": false, "remove_null_rows": false, "remove_null_rows_from_selected_columns": false, "remove_numbers": false, "remove_punctuation": false, "replace_null_numbers": false, "replace_null_strings": false, "selected_fields": ["order_id", "currency", "status", "payment_method"], "strip_whitespace": true}'))
import json
import polars as pl
from trigger_designer.core.shaping.cleansing import run_node as _run_node
var_cleansing_1905896294016, = _run_node([var_cleansing_1905914360704], json.loads('{"case_modification": "lower", "normalize_spaces": false, "remove_all_whitespace": false, "remove_letters": false, "remove_null_columns": false, "remove_null_rows": false, "remove_null_rows_from_selected_columns": false, "remove_numbers": false, "remove_punctuation": false, "replace_null_numbers": false, "replace_null_strings": false, "selected_fields": ["customer_id", "product_id"], "strip_whitespace": false}'))
import json
import polars as pl
from trigger_designer.core.shaping.filter import run_node as _run_node
var_t_filter_1905896514560, var_f_filter_1905896514560 = _run_node([var_cleansing_1905896294016], json.loads('{"column": "quantity", "expression": "[quantity] >= 1 AND [quantity] <= 500", "mode": "builder", "operation": "In Between", "value": "1", "value2": "500"}'))
import json
import polars as pl
from trigger_designer.core.shaping.filter import run_node as _run_node
var_t_filter_1905896520448, var_f_filter_1905896520448 = _run_node([var_t_filter_1905896514560], json.loads('{"column": "order_id", "expression": "[unit_price_local] > 0 and \\n[unit_price_local] <= 5000", "mode": "expression", "operation": "Equals", "value": "", "value2": ""}'))
import json
import polars as pl
from trigger_designer.core.shaping.filter import run_node as _run_node
var_t_filter_1905896608768, var_f_filter_1905896608768 = _run_node([var_t_filter_1905896520448], json.loads('{"column": "customer_id", "expression": "YEAR([order_ts]) <= 2025", "mode": "expression", "operation": "Equals", "value": "", "value2": ""}'))
import json
import polars as pl
from trigger_designer.core.shaping.unique import run_node as _run_node
var_unique_1905896658944, var_duplicate_1905896658944 = _run_node([var_t_filter_1905896608768], json.loads('{"selected_columns": ["order_id"]}'))
import json
import polars as pl
from trigger_designer.core.shaping.select import run_node as _run_node
var_select_1905914382592, = _run_node([var_unique_1905896658944], json.loads('{"auto_accept_new_columns": true, "columns": [{"date_format": "", "dtype": "String", "dtype_custom": false, "name": "order_id", "rename": "", "selected": true}, {"date_format": "", "dtype": "Int64", "dtype_custom": false, "name": "customer_id", "rename": "", "selected": true}, {"date_format": "", "dtype": "Int64", "dtype_custom": false, "name": "product_id", "rename": "", "selected": true}, {"date_format": "", "dtype": "Int64", "dtype_custom": false, "name": "supplier_id", "rename": "", "selected": true}, {"date_format": "", "dtype": "Int64", "dtype_custom": false, "name": "channel_id", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "currency", "rename": "", "selected": true}, {"date_format": "", "dtype": "Datetime(time_unit=\'us\', time_zone=None)", "dtype_custom": true, "name": "order_ts", "rename": "", "selected": true}, {"date_format": "", "dtype": "Int64", "dtype_custom": false, "name": "quantity", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "unit_price_local", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "discount_pct", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "tax_local", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "shipping_local", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "status", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "payment_method", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "is_returned", "rename": "", "selected": true}]}'))
import json
import polars as pl
from trigger_designer.core.shaping.join import run_node as _run_node
var_l_join_1905896949568, var_join_1905896949568, var_r_join_1905896949568 = _run_node([var_select_1905914382592, var_select_1905896210624], json.loads('{"auto_accept_new_columns": true, "join_type": "inner", "known_columns": [{"name": "channel_id", "source": "L"}, {"name": "currency", "source": "L"}, {"name": "customer_id", "source": "L"}, {"name": "discount_pct", "source": "L"}, {"name": "is_returned", "source": "L"}, {"name": "order_id", "source": "L"}, {"name": "order_ts", "source": "L"}, {"name": "payment_method", "source": "L"}, {"name": "product_id", "source": "L"}, {"name": "quantity", "source": "L"}, {"name": "shipping_local", "source": "L"}, {"name": "status", "source": "L"}, {"name": "supplier_id", "source": "L"}, {"name": "tax_local", "source": "L"}, {"name": "unit_price_local", "source": "L"}, {"name": "customer_age_band", "source": "R"}, {"name": "customer_country", "source": "R"}, {"name": "customer_currency", "source": "R"}, {"name": "customer_email", "source": "R"}, {"name": "customer_id", "source": "R"}, {"name": "customer_name", "source": "R"}, {"name": "loyalty_tier", "source": "R"}, {"name": "region", "source": "R"}, {"name": "segment", "source": "R"}, {"name": "signup_date", "source": "R"}], "mapping_data": [{"left_column": "customer_id", "right_column": "customer_id"}], "selected_columns": [{"name": "channel_id", "source": "L"}, {"name": "currency", "source": "L"}, {"name": "customer_id", "source": "L"}, {"name": "discount_pct", "source": "L"}, {"name": "is_returned", "source": "L"}, {"name": "order_ts", "source": "L"}, {"name": "payment_method", "source": "L"}, {"name": "product_id", "source": "L"}, {"name": "quantity", "source": "L"}, {"name": "shipping_local", "source": "L"}, {"name": "status", "source": "L"}, {"name": "supplier_id", "source": "L"}, {"name": "tax_local", "source": "L"}, {"name": "unit_price_local", "source": "L"}, {"name": "customer_age_band", "source": "R"}, {"name": "customer_country", "source": "R"}, {"name": "customer_currency", "source": "R"}, {"name": "customer_email", "source": "R"}, {"name": "customer_id", "source": "R"}, {"name": "loyalty_tier", "source": "R"}, {"name": "region", "source": "R"}, {"name": "segment", "source": "R"}, {"name": "signup_date", "source": "R"}, {"name": "customer_name", "source": "R"}, {"name": "order_id", "source": "L"}]}'))
import polars as pl
_union_inputs_1905913616000 = [var_join_1905896949568, var_l_join_1905896949568]
var_union_1905913616000 = pl.concat([(f.lazy() if isinstance(f, pl.DataFrame) else f) for f in _union_inputs_1905913616000], how='diagonal_relaxed')
del _union_inputs_1905913616000
import json
import polars as pl
from trigger_designer.core.shaping.join import run_node as _run_node
var_l_join_1905896958912, var_join_1905896958912, var_r_join_1905896958912 = _run_node([var_union_1905913616000, var_select_1905896215680], json.loads('{"auto_accept_new_columns": true, "join_type": "inner", "known_columns": [{"name": "channel_id", "source": "L"}, {"name": "currency", "source": "L"}, {"name": "customer_age_band", "source": "L"}, {"name": "customer_country", "source": "L"}, {"name": "customer_currency", "source": "L"}, {"name": "customer_email", "source": "L"}, {"name": "customer_id", "source": "L"}, {"name": "customer_name", "source": "L"}, {"name": "discount_pct", "source": "L"}, {"name": "is_returned", "source": "L"}, {"name": "loyalty_tier", "source": "L"}, {"name": "order_id", "source": "L"}, {"name": "order_ts", "source": "L"}, {"name": "payment_method", "source": "L"}, {"name": "product_id", "source": "L"}, {"name": "quantity", "source": "L"}, {"name": "region", "source": "L"}, {"name": "segment", "source": "L"}, {"name": "shipping_local", "source": "L"}, {"name": "signup_date", "source": "L"}, {"name": "status", "source": "L"}, {"name": "supplier_id", "source": "L"}, {"name": "tax_local", "source": "L"}, {"name": "unit_price_local", "source": "L"}, {"name": "brand", "source": "R"}, {"name": "category", "source": "R"}, {"name": "launch_date", "source": "R"}, {"name": "product_id", "source": "R"}, {"name": "product_name", "source": "R"}, {"name": "sku", "source": "R"}, {"name": "subcategory", "source": "R"}, {"name": "unit_cost", "source": "R"}, {"name": "unit_price", "source": "R"}], "mapping_data": [{"left_column": "product_id", "right_column": "product_id"}], "selected_columns": [{"name": "channel_id", "source": "L"}, {"name": "currency", "source": "L"}, {"name": "customer_age_band", "source": "L"}, {"name": "customer_country", "source": "L"}, {"name": "customer_currency", "source": "L"}, {"name": "customer_email", "source": "L"}, {"name": "customer_id", "source": "L"}, {"name": "discount_pct", "source": "L"}, {"name": "is_returned", "source": "L"}, {"name": "loyalty_tier", "source": "L"}, {"name": "order_ts", "source": "L"}, {"name": "payment_method", "source": "L"}, {"name": "product_id", "source": "L"}, {"name": "quantity", "source": "L"}, {"name": "region", "source": "L"}, {"name": "segment", "source": "L"}, {"name": "shipping_local", "source": "L"}, {"name": "signup_date", "source": "L"}, {"name": "status", "source": "L"}, {"name": "supplier_id", "source": "L"}, {"name": "tax_local", "source": "L"}, {"name": "unit_price_local", "source": "L"}, {"name": "brand", "source": "R"}, {"name": "category", "source": "R"}, {"name": "launch_date", "source": "R"}, {"name": "product_id", "source": "R"}, {"name": "product_name", "source": "R"}, {"name": "sku", "source": "R"}, {"name": "subcategory", "source": "R"}, {"name": "unit_cost", "source": "R"}, {"name": "unit_price", "source": "R"}, {"name": "customer_name", "source": "L"}, {"name": "order_id", "source": "L"}]}'))
import polars as pl
_union_inputs_1905913691968 = [var_join_1905896958912, var_l_join_1905896958912]
var_union_1905913691968 = pl.concat([(f.lazy() if isinstance(f, pl.DataFrame) else f) for f in _union_inputs_1905913691968], how='diagonal_relaxed')
del _union_inputs_1905913691968
import json
import polars as pl
from trigger_designer.core.shaping.join import run_node as _run_node
var_l_join_1905913564416, var_join_1905913564416, var_r_join_1905913564416 = _run_node([var_union_1905913691968, var_select_1905896218368], json.loads('{"auto_accept_new_columns": true, "join_type": "inner", "known_columns": [{"name": "brand", "source": "L"}, {"name": "category", "source": "L"}, {"name": "channel_id", "source": "L"}, {"name": "currency", "source": "L"}, {"name": "customer_age_band", "source": "L"}, {"name": "customer_country", "source": "L"}, {"name": "customer_currency", "source": "L"}, {"name": "customer_email", "source": "L"}, {"name": "customer_id", "source": "L"}, {"name": "customer_name", "source": "L"}, {"name": "discount_pct", "source": "L"}, {"name": "is_returned", "source": "L"}, {"name": "launch_date", "source": "L"}, {"name": "loyalty_tier", "source": "L"}, {"name": "order_id", "source": "L"}, {"name": "order_ts", "source": "L"}, {"name": "payment_method", "source": "L"}, {"name": "product_id", "source": "L"}, {"name": "product_name", "source": "L"}, {"name": "quantity", "source": "L"}, {"name": "region", "source": "L"}, {"name": "segment", "source": "L"}, {"name": "shipping_local", "source": "L"}, {"name": "signup_date", "source": "L"}, {"name": "sku", "source": "L"}, {"name": "status", "source": "L"}, {"name": "subcategory", "source": "L"}, {"name": "supplier_id", "source": "L"}, {"name": "tax_local", "source": "L"}, {"name": "unit_cost", "source": "L"}, {"name": "unit_price", "source": "L"}, {"name": "unit_price_local", "source": "L"}, {"name": "country", "source": "R"}, {"name": "lead_time_days", "source": "R"}, {"name": "reliability_score", "source": "R"}, {"name": "supplier_id", "source": "R"}, {"name": "supplier_name", "source": "R"}], "mapping_data": [{"left_column": "supplier_id", "right_column": "supplier_id"}], "selected_columns": [{"name": "brand", "source": "L"}, {"name": "category", "source": "L"}, {"name": "channel_id", "source": "L"}, {"name": "currency", "source": "L"}, {"name": "customer_age_band", "source": "L"}, {"name": "customer_country", "source": "L"}, {"name": "customer_currency", "source": "L"}, {"name": "customer_email", "source": "L"}, {"name": "customer_id", "source": "L"}, {"name": "discount_pct", "source": "L"}, {"name": "is_returned", "source": "L"}, {"name": "launch_date", "source": "L"}, {"name": "loyalty_tier", "source": "L"}, {"name": "order_ts", "source": "L"}, {"name": "payment_method", "source": "L"}, {"name": "product_id", "source": "L"}, {"name": "product_name", "source": "L"}, {"name": "quantity", "source": "L"}, {"name": "region", "source": "L"}, {"name": "segment", "source": "L"}, {"name": "shipping_local", "source": "L"}, {"name": "signup_date", "source": "L"}, {"name": "sku", "source": "L"}, {"name": "status", "source": "L"}, {"name": "subcategory", "source": "L"}, {"name": "supplier_id", "source": "L"}, {"name": "tax_local", "source": "L"}, {"name": "unit_cost", "source": "L"}, {"name": "unit_price", "source": "L"}, {"name": "unit_price_local", "source": "L"}, {"name": "country", "source": "R"}, {"name": "lead_time_days", "source": "R"}, {"name": "reliability_score", "source": "R"}, {"name": "supplier_id", "source": "R"}, {"name": "supplier_name", "source": "R"}, {"name": "customer_name", "source": "L"}, {"name": "order_id", "source": "L"}]}'))
import polars as pl
_union_inputs_1905913630784 = [var_join_1905913564416, var_l_join_1905913564416]
var_union_1905913630784 = pl.concat([(f.lazy() if isinstance(f, pl.DataFrame) else f) for f in _union_inputs_1905913630784], how='diagonal_relaxed')
del _union_inputs_1905913630784
import json
import polars as pl
from trigger_designer.core.shaping.join import run_node as _run_node
var_l_join_1905913573184, var_join_1905913573184, var_r_join_1905913573184 = _run_node([var_union_1905913630784, var_select_1905895888640], json.loads('{"auto_accept_new_columns": true, "join_type": "inner", "known_columns": [{"name": "brand", "source": "L"}, {"name": "category", "source": "L"}, {"name": "channel_id", "source": "L"}, {"name": "country", "source": "L"}, {"name": "currency", "source": "L"}, {"name": "customer_age_band", "source": "L"}, {"name": "customer_country", "source": "L"}, {"name": "customer_currency", "source": "L"}, {"name": "customer_email", "source": "L"}, {"name": "customer_id", "source": "L"}, {"name": "customer_name", "source": "L"}, {"name": "discount_pct", "source": "L"}, {"name": "is_returned", "source": "L"}, {"name": "launch_date", "source": "L"}, {"name": "lead_time_days", "source": "L"}, {"name": "loyalty_tier", "source": "L"}, {"name": "order_id", "source": "L"}, {"name": "order_ts", "source": "L"}, {"name": "payment_method", "source": "L"}, {"name": "product_id", "source": "L"}, {"name": "product_name", "source": "L"}, {"name": "quantity", "source": "L"}, {"name": "region", "source": "L"}, {"name": "reliability_score", "source": "L"}, {"name": "segment", "source": "L"}, {"name": "shipping_local", "source": "L"}, {"name": "signup_date", "source": "L"}, {"name": "sku", "source": "L"}, {"name": "status", "source": "L"}, {"name": "subcategory", "source": "L"}, {"name": "supplier_id", "source": "L"}, {"name": "supplier_name", "source": "L"}, {"name": "tax_local", "source": "L"}, {"name": "unit_cost", "source": "L"}, {"name": "unit_price", "source": "L"}, {"name": "unit_price_local", "source": "L"}, {"name": "channel_group", "source": "R"}, {"name": "channel_id", "source": "R"}, {"name": "channel_name", "source": "R"}, {"name": "is_digital", "source": "R"}], "mapping_data": [{"left_column": "channel_id", "right_column": "channel_id"}], "selected_columns": [{"name": "brand", "source": "L"}, {"name": "category", "source": "L"}, {"name": "channel_id", "source": "L"}, {"name": "country", "source": "L"}, {"name": "currency", "source": "L"}, {"name": "customer_age_band", "source": "L"}, {"name": "customer_country", "source": "L"}, {"name": "customer_currency", "source": "L"}, {"name": "customer_email", "source": "L"}, {"name": "customer_id", "source": "L"}, {"name": "discount_pct", "source": "L"}, {"name": "is_returned", "source": "L"}, {"name": "launch_date", "source": "L"}, {"name": "lead_time_days", "source": "L"}, {"name": "loyalty_tier", "source": "L"}, {"name": "order_ts", "source": "L"}, {"name": "payment_method", "source": "L"}, {"name": "product_id", "source": "L"}, {"name": "product_name", "source": "L"}, {"name": "quantity", "source": "L"}, {"name": "region", "source": "L"}, {"name": "reliability_score", "source": "L"}, {"name": "segment", "source": "L"}, {"name": "shipping_local", "source": "L"}, {"name": "signup_date", "source": "L"}, {"name": "sku", "source": "L"}, {"name": "status", "source": "L"}, {"name": "subcategory", "source": "L"}, {"name": "supplier_id", "source": "L"}, {"name": "supplier_name", "source": "L"}, {"name": "tax_local", "source": "L"}, {"name": "unit_cost", "source": "L"}, {"name": "unit_price", "source": "L"}, {"name": "unit_price_local", "source": "L"}, {"name": "channel_group", "source": "R"}, {"name": "channel_id", "source": "R"}, {"name": "channel_name", "source": "R"}, {"name": "is_digital", "source": "R"}, {"name": "order_id", "source": "L"}]}'))
import polars as pl
_union_inputs_1905913763328 = [var_join_1905913573184, var_l_join_1905913573184]
var_union_1905913763328 = pl.concat([(f.lazy() if isinstance(f, pl.DataFrame) else f) for f in _union_inputs_1905913763328], how='diagonal_relaxed')
del _union_inputs_1905913763328
import json
import polars as pl
from trigger_designer.core.shaping.join import run_node as _run_node
var_l_join_1905913614464, var_join_1905913614464, var_r_join_1905913614464 = _run_node([var_union_1905913763328, var_formula_1905896734656], json.loads('{"auto_accept_new_columns": true, "join_type": "inner", "known_columns": [{"name": "brand", "source": "L"}, {"name": "category", "source": "L"}, {"name": "channel_group", "source": "L"}, {"name": "channel_id", "source": "L"}, {"name": "channel_name", "source": "L"}, {"name": "country", "source": "L"}, {"name": "currency", "source": "L"}, {"name": "customer_age_band", "source": "L"}, {"name": "customer_country", "source": "L"}, {"name": "customer_currency", "source": "L"}, {"name": "customer_email", "source": "L"}, {"name": "customer_id", "source": "L"}, {"name": "customer_name", "source": "L"}, {"name": "discount_pct", "source": "L"}, {"name": "is_digital", "source": "L"}, {"name": "is_returned", "source": "L"}, {"name": "launch_date", "source": "L"}, {"name": "lead_time_days", "source": "L"}, {"name": "loyalty_tier", "source": "L"}, {"name": "order_id", "source": "L"}, {"name": "order_ts", "source": "L"}, {"name": "payment_method", "source": "L"}, {"name": "product_id", "source": "L"}, {"name": "product_name", "source": "L"}, {"name": "quantity", "source": "L"}, {"name": "region", "source": "L"}, {"name": "reliability_score", "source": "L"}, {"name": "segment", "source": "L"}, {"name": "shipping_local", "source": "L"}, {"name": "signup_date", "source": "L"}, {"name": "sku", "source": "L"}, {"name": "status", "source": "L"}, {"name": "subcategory", "source": "L"}, {"name": "supplier_id", "source": "L"}, {"name": "supplier_name", "source": "L"}, {"name": "tax_local", "source": "L"}, {"name": "unit_cost", "source": "L"}, {"name": "unit_price", "source": "L"}, {"name": "unit_price_local", "source": "L"}, {"name": "currency", "source": "R"}, {"name": "currency_name", "source": "R"}, {"name": "usd_rate", "source": "R"}], "mapping_data": [{"left_column": "currency", "right_column": "currency"}], "selected_columns": [{"name": "brand", "source": "L"}, {"name": "category", "source": "L"}, {"name": "channel_group", "source": "L"}, {"name": "channel_id", "source": "L"}, {"name": "channel_name", "source": "L"}, {"name": "country", "source": "L"}, {"name": "currency", "source": "L"}, {"name": "customer_age_band", "source": "L"}, {"name": "customer_country", "source": "L"}, {"name": "customer_currency", "source": "L"}, {"name": "customer_email", "source": "L"}, {"name": "customer_id", "source": "L"}, {"name": "discount_pct", "source": "L"}, {"name": "is_digital", "source": "L"}, {"name": "is_returned", "source": "L"}, {"name": "launch_date", "source": "L"}, {"name": "lead_time_days", "source": "L"}, {"name": "loyalty_tier", "source": "L"}, {"name": "order_ts", "source": "L"}, {"name": "payment_method", "source": "L"}, {"name": "product_id", "source": "L"}, {"name": "product_name", "source": "L"}, {"name": "quantity", "source": "L"}, {"name": "region", "source": "L"}, {"name": "reliability_score", "source": "L"}, {"name": "segment", "source": "L"}, {"name": "shipping_local", "source": "L"}, {"name": "signup_date", "source": "L"}, {"name": "sku", "source": "L"}, {"name": "status", "source": "L"}, {"name": "subcategory", "source": "L"}, {"name": "supplier_id", "source": "L"}, {"name": "supplier_name", "source": "L"}, {"name": "tax_local", "source": "L"}, {"name": "unit_cost", "source": "L"}, {"name": "unit_price", "source": "L"}, {"name": "unit_price_local", "source": "L"}, {"name": "currency", "source": "R"}, {"name": "currency_name", "source": "R"}, {"name": "usd_rate", "source": "R"}, {"name": "order_id", "source": "L"}]}'))
import polars as pl
_union_inputs_1905913792000 = [var_join_1905913614464, var_l_join_1905913614464]
var_union_1905913792000 = pl.concat([(f.lazy() if isinstance(f, pl.DataFrame) else f) for f in _union_inputs_1905913792000], how='diagonal_relaxed')
del _union_inputs_1905913792000
import json
import polars as pl
from trigger_designer.core.shaping.formula import run_node as _run_node
var_formula_1905913622848, = _run_node([var_union_1905913792000], json.loads('{"sections": [{"editor_height": 60, "formula_text": "[quantity] * [unit_price_local]", "target_column": "g", "target_dtype": ""}, {"editor_height": 60, "formula_text": "ROUND([g], 2)", "target_column": "gross_local", "target_dtype": ""}, {"editor_height": 60, "formula_text": "ROUND([gross_local] * [discount_pct], 2)", "target_column": "discount_local", "target_dtype": ""}, {"editor_height": 60, "formula_text": "ROUND([gross_local] - [discount_local], 2)", "target_column": "net_local", "target_dtype": ""}, {"editor_height": 60, "formula_text": "ROUND([net_local] + [tax_local] + [shipping_local], 2)", "target_column": "total_local", "target_dtype": ""}]}'))
import json
import polars as pl
from trigger_designer.core.shaping.formula import run_node as _run_node
var_formula_1905913627904, = _run_node([var_formula_1905913622848], json.loads('{"sections": [{"editor_height": 60, "formula_text": "ROUND([unit_price_local] * [usd_rate], 2)", "target_column": "unit_price_usd", "target_dtype": ""}, {"editor_height": 60, "formula_text": "ROUND([net_local] * [usd_rate], 2)", "target_column": "net_revenue_usd", "target_dtype": ""}, {"editor_height": 60, "formula_text": "ROUND([tax_local] * [usd_rate], 2)", "target_column": "tax_usd", "target_dtype": ""}, {"editor_height": 60, "formula_text": "ROUND([shipping_local] * [usd_rate], 2)", "target_column": "shipping_usd", "target_dtype": ""}, {"editor_height": 60, "formula_text": "ROUND([total_local] * [usd_rate], 2)", "target_column": "total_usd", "target_dtype": ""}]}'))
import json
import polars as pl
from trigger_designer.core.shaping.formula import run_node as _run_node
var_formula_1905913797760, = _run_node([var_formula_1905913627904], json.loads('{"sections": [{"editor_height": 60, "formula_text": "ROUND([quantity] * [unit_cost], 2)", "target_column": "cogs_usd", "target_dtype": ""}, {"editor_height": 60, "formula_text": "ROUND([net_revenue_usd] - [cogs_usd], 2)", "target_column": "gross_margin_usd", "target_dtype": ""}, {"editor_height": 120, "formula_text": "ROUND(CASE\\n    WHEN [net_revenue_usd] IS NULL OR [net_revenue_usd] = 0 THEN NULL\\n    ELSE [gross_margin_usd] / [net_revenue_usd]\\nEND, 4)", "target_column": "margin_pct", "target_dtype": ""}]}'))
import json
import polars as pl
from trigger_designer.core.shaping.formula import run_node as _run_node
var_formula_1905913803840, = _run_node([var_formula_1905913797760], json.loads('{"sections": [{"editor_height": 60, "formula_text": "YEAR([order_ts])", "target_column": "order_year", "target_dtype": ""}, {"editor_height": 60, "formula_text": "MONTH([order_ts])", "target_column": "order_month", "target_dtype": ""}, {"editor_height": 60, "formula_text": "STRFTIME([order_ts], \'%Y-%m\')", "target_column": "order_year_month", "target_dtype": ""}, {"editor_height": 60, "formula_text": "[quantity] >= 6", "target_column": "is_bulk", "target_dtype": ""}, {"editor_height": 120, "formula_text": "CASE\\n    WHEN [net_revenue_usd] IS NULL THEN NULL\\n    WHEN [net_revenue_usd] <= 250  THEN \'Low\'\\n    WHEN [net_revenue_usd] <= 1000 THEN \'Medium\'\\n    ELSE \'High\'\\nEND\\n", "target_column": "value_band", "target_dtype": ""}]}'))
import json
import polars as pl
from trigger_designer.core.shaping.formula import run_node as _run_node
var_formula_1905913826240, = _run_node([var_formula_1905913803840], json.loads('{"sections": [{"editor_height": 60, "formula_text": "CASE WHEN LOWER([is_returned]) = \'true\' THEN true ELSE false END", "target_column": "is_returned", "target_dtype": ""}, {"editor_height": 160, "formula_text": "(CASE WHEN [is_returned] THEN 2 ELSE 0 END)\\n+ (CASE WHEN [status] IN (\'refunded\', \'cancelled\') THEN 2 ELSE 0 END)\\n+ (CASE WHEN [net_revenue_usd] > 2000 THEN 1 ELSE 0 END)\\n+ (CASE WHEN [margin_pct] < 0.10 THEN 1 ELSE 0 END)\\n+ (CASE WHEN [segment] IS NULL THEN 2 ELSE 0 END)\\n", "target_column": "risk_score", "target_dtype": ""}, {"editor_height": 140, "formula_text": "CASE\\n    WHEN [risk_score] >= 4 THEN \'High\'\\n    WHEN [risk_score] >= 2 THEN \'Medium\'\\n    ELSE \'Low\'\\nEND", "target_column": "risk_band", "target_dtype": ""}, {"editor_height": 160, "formula_text": "CASE [status] WHEN \'paid\' THEN \'Paid\'\\n  WHEN \'pending\' THEN \'Pending\'\\n  WHEN \'refunded\' THEN \'Refunded\'\\n  WHEN \'cancelled\' THEN \'Cancelled\'\\n  WHEN \'partially refunded\' THEN \'Partially Refunded\'\\n  ELSE [status] END", "target_column": "status_clean", "target_dtype": ""}]}'))
import json
import polars as pl
from trigger_designer.core.shaping.aggregate import run_node as _run_node
var_groupby_1905913865024, = _run_node([var_formula_1905913826240], json.loads('{"actions": [{"action": "GroupBy", "field": "order_year_month", "output_name": "order_year_month"}, {"action": "Sum", "field": "net_revenue_usd", "output_name": "revenue_usd"}, {"action": "Sum", "field": "gross_margin_usd", "output_name": "margin_usd"}, {"action": "N_Unique", "field": "order_id", "output_name": "orders"}]}'))
import json
import polars as pl
from trigger_designer.core.shaping.sort import run_node as _run_node
var_sort_1905913826688, = _run_node([var_groupby_1905913865024], json.loads('{"keys": [{"column": "order_year_month", "order": "Ascending"}]}'))
import json
import polars as pl
from trigger_designer.core.shaping.running_total import run_node as _run_node
var_runtot_1905913567232, = _run_node([var_sort_1905913826688], json.loads('{"group_by_columns": [], "sum_columns": ["revenue_usd"]}'))
import json
import polars as pl
from trigger_designer.core.shaping.select import run_node as _run_node
var_select_1905913835840, = _run_node([var_runtot_1905913567232], json.loads('{"auto_accept_new_columns": true, "columns": [{"date_format": "", "dtype": "String", "dtype_custom": false, "name": "order_year_month", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "revenue_usd", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "margin_usd", "rename": "", "selected": true}, {"date_format": "", "dtype": "UInt32", "dtype_custom": true, "name": "orders", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "RunTot_revenue_usd", "rename": "cumulative_revenue_usd", "selected": true}]}'))
import json
from trigger_designer.core.shaping.file_output import write_node as _write_node
_write_node([var_select_1905913835840], json.loads('{"compression": null, "delimiter": ",", "filePath": "C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/monthly_revenue.csv", "file_format": "csv", "include_bom": false, "use_streaming": true}'))
import json
import polars as pl
from trigger_designer.core.shaping.transpose import run_node as _run_node
var_transpose_1905895888960, = _run_node([var_select_1905913835840], json.loads('{"data_columns": ["revenue_usd", "margin_usd", "orders"], "key_columns": ["order_year_month"], "missing_action": "warn"}'))
import json
import polars as pl
from trigger_designer.core.shaping.select import run_node as _run_node
var_select_1905913986752, = _run_node([var_transpose_1905895888960], json.loads('{"auto_accept_new_columns": true, "columns": [{"date_format": "", "dtype": "String", "dtype_custom": false, "name": "order_year_month", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "Name", "rename": "metric", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "Value", "rename": "value", "selected": true}]}'))
import json
from trigger_designer.core.shaping.file_output import write_node as _write_node
_write_node([var_select_1905913986752], json.loads('{"compression": null, "delimiter": ",", "filePath": "C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/monthly_revenue_long.csv", "file_format": "csv", "include_bom": false, "use_streaming": true}'))
import json
import polars as pl
from trigger_designer.core.shaping.aggregate import run_node as _run_node
var_groupby_1905896654272, = _run_node([var_formula_1905913826240], json.loads('{"actions": [{"action": "GroupBy", "field": "category", "output_name": "category"}, {"action": "Sum", "field": "net_revenue_usd", "output_name": "revenue_usd"}, {"action": "Sum", "field": "gross_margin_usd", "output_name": "margin_usd"}, {"action": "N_Unique", "field": "order_id", "output_name": "orders"}]}'))
import json
import polars as pl
from trigger_designer.core.shaping.sort import run_node as _run_node
var_sort_1905914035008, = _run_node([var_groupby_1905896654272], json.loads('{"keys": [{"column": "revenue_usd", "order": "Descending"}]}'))
import json
from trigger_designer.core.shaping.file_output import write_node as _write_node
_write_node([var_sort_1905914035008], json.loads('{"compression": null, "delimiter": ",", "filePath": "C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/category_revenue.csv", "file_format": "csv", "include_bom": false, "use_streaming": true}'))
import json
import polars as pl
from trigger_designer.core.shaping.aggregate import run_node as _run_node
var_groupby_1905914072832, = _run_node([var_formula_1905913826240], json.loads('{"actions": [{"action": "GroupBy", "field": "region", "output_name": "region"}, {"action": "GroupBy", "field": "channel_group", "output_name": "channel_group"}, {"action": "Sum", "field": "net_revenue_usd", "output_name": "revenue_usd"}, {"action": "Sum", "field": "gross_margin_usd", "output_name": "margin_usd"}, {"action": "N_Unique", "field": "order_id", "output_name": "orders"}]}'))
import json
import polars as pl
from trigger_designer.core.shaping.sort import run_node as _run_node
var_sort_1905914045504, = _run_node([var_groupby_1905914072832], json.loads('{"keys": [{"column": "region", "order": "Ascending"}, {"column": "channel_group", "order": "Ascending"}]}'))
import json
from trigger_designer.core.shaping.file_output import write_node as _write_node
_write_node([var_sort_1905914045504], json.loads('{"compression": null, "delimiter": ",", "filePath": "C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/region_channel_revenue.csv", "file_format": "csv", "include_bom": false, "use_streaming": true}'))
import json
import polars as pl
from trigger_designer.core.shaping.aggregate import run_node as _run_node
var_groupby_1905914078336, = _run_node([var_formula_1905913826240], json.loads('{"actions": [{"action": "GroupBy", "field": "segment", "output_name": "segment"}, {"action": "GroupBy", "field": "risk_band", "output_name": "risk_band"}, {"action": "Sum", "field": "net_revenue_usd", "output_name": "revenue_usd"}, {"action": "Sum", "field": "gross_margin_usd", "output_name": "margin_usd"}, {"action": "N_Unique", "field": "order_id", "output_name": "orders"}]}'))
import json
import polars as pl
from trigger_designer.core.shaping.aggregate import run_node as _run_node
var_groupby_1905914083968, = _run_node([var_formula_1905913826240], json.loads('{"actions": [{"action": "GroupBy", "field": "customer_id", "output_name": "customer_id"}, {"action": "Sum", "field": "net_revenue_usd", "output_name": "revenue_usd"}, {"action": "N_Unique", "field": "order_id", "output_name": "orders"}]}'))
import json
import polars as pl
from trigger_designer.core.shaping.filter import run_node as _run_node
var_t_filter_1905914132672, var_f_filter_1905914132672 = _run_node([var_groupby_1905914083968], json.loads('{"column": "revenue_usd", "expression": "", "mode": "builder", "operation": "Greater Than", "value": "4000", "value2": ""}'))
import json
import polars as pl
from trigger_designer.core.shaping.sort import run_node as _run_node
var_sort_1905914126720, = _run_node([var_t_filter_1905914132672], json.loads('{"keys": [{"column": "revenue_usd", "order": "Descending"}]}'))
import json
from trigger_designer.core.shaping.file_output import write_node as _write_node
_write_node([var_sort_1905914126720], json.loads('{"compression": null, "delimiter": ",", "filePath": "C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/top_customers.csv", "file_format": "csv", "include_bom": false, "use_streaming": true}'))
import json
import polars as pl
from trigger_designer.core.shaping.aggregate import run_node as _run_node
var_groupby_1905914159360, = _run_node([var_formula_1905913826240], json.loads('{"actions": [{"action": "GroupBy", "field": "supplier_id", "output_name": "supplier_id"}, {"action": "GroupBy", "field": "supplier_name", "output_name": "supplier_name"}, {"action": "GroupBy", "field": "country", "output_name": "country"}, {"action": "Sum", "field": "net_revenue_usd", "output_name": "revenue_usd"}, {"action": "N_Unique", "field": "order_id", "output_name": "orders"}, {"action": "First", "field": "lead_time_days", "output_name": "lead_time_days"}, {"action": "First", "field": "reliability_score", "output_name": "reliability_score"}]}'))
import json
import polars as pl
from trigger_designer.core.shaping.sort import run_node as _run_node
var_sort_1905914159552, = _run_node([var_groupby_1905914159360], json.loads('{"keys": [{"column": "revenue_usd", "order": "Descending"}]}'))
import json
import polars as pl
from trigger_designer.core.shaping.formula import run_node as _run_node
var_formula_1905914170816, = _run_node([var_sort_1905914159552], json.loads('{"sections": [{"editor_height": 60, "formula_text": "[revenue_usd] / [lead_time_days]", "target_column": "revenue_per_lead_day", "target_dtype": ""}]}'))
import json
from trigger_designer.core.shaping.file_output import write_node as _write_node
_write_node([var_formula_1905914170816], json.loads('{"compression": null, "delimiter": ",", "filePath": "C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/supplier_performance.csv", "file_format": "csv", "include_bom": false, "use_streaming": true}'))
import json
import polars as pl
from trigger_designer.core.shaping.aggregate import run_node as _run_node
var_groupby_1905914203200, = _run_node([var_formula_1905913826240], json.loads('{"actions": [{"action": "GroupBy", "field": "currency", "output_name": "currency"}, {"action": "Sum", "field": "net_revenue_usd", "output_name": "revenue_usd"}, {"action": "N_Unique", "field": "order_id", "output_name": "orders"}, {"action": "First", "field": "usd_rate", "output_name": "usd_rate"}]}'))
import json
import polars as pl
from trigger_designer.core.shaping.sort import run_node as _run_node
var_sort_1905914180352, = _run_node([var_groupby_1905914203200], json.loads('{"keys": [{"column": "revenue_usd", "order": "Descending"}]}'))
import json
from trigger_designer.core.shaping.file_output import write_node as _write_node
_write_node([var_sort_1905914180352], json.loads('{"compression": null, "delimiter": ",", "filePath": "C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/fx_exposure.csv", "file_format": "csv", "include_bom": false, "use_streaming": true}'))
import json
import polars as pl
from trigger_designer.core.shaping.select import run_node as _run_node
var_select_1905914267456, = _run_node([var_formula_1905913826240], json.loads('{"auto_accept_new_columns": true, "columns": [{"date_format": "", "dtype": "String", "dtype_custom": false, "name": "brand", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "category", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "channel_group", "rename": "", "selected": true}, {"date_format": "", "dtype": "Int64", "dtype_custom": false, "name": "channel_id", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "channel_name", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "country", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "currency", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "customer_age_band", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "customer_country", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "customer_currency", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "customer_email", "rename": "", "selected": true}, {"date_format": "", "dtype": "Int64", "dtype_custom": false, "name": "customer_id", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "discount_pct", "rename": "", "selected": true}, {"date_format": "", "dtype": "Boolean", "dtype_custom": true, "name": "is_digital", "rename": "", "selected": true}, {"date_format": "", "dtype": "Boolean", "dtype_custom": false, "name": "is_returned", "rename": "", "selected": true}, {"date_format": "", "dtype": "Date", "dtype_custom": false, "name": "launch_date", "rename": "", "selected": true}, {"date_format": "", "dtype": "Int64", "dtype_custom": false, "name": "lead_time_days", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "loyalty_tier", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "order_id", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": true, "name": "order_ts", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "payment_method", "rename": "", "selected": true}, {"date_format": "", "dtype": "Int64", "dtype_custom": false, "name": "product_id", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "product_name", "rename": "", "selected": true}, {"date_format": "", "dtype": "Int64", "dtype_custom": false, "name": "quantity", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "region", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "reliability_score", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "segment", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "shipping_local", "rename": "", "selected": true}, {"date_format": "", "dtype": "Date", "dtype_custom": false, "name": "signup_date", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "sku", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "status", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "subcategory", "rename": "", "selected": true}, {"date_format": "", "dtype": "Int64", "dtype_custom": false, "name": "supplier_id", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "supplier_name", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "tax_local", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "unit_cost", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "unit_price", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "unit_price_local", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "currency_name", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "usd_rate", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "g", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "gross_local", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "discount_local", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "net_local", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "total_local", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "unit_price_usd", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "net_revenue_usd", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "tax_usd", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "shipping_usd", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "total_usd", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "cogs_usd", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "gross_margin_usd", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "margin_pct", "rename": "", "selected": true}, {"date_format": "", "dtype": "Int64", "dtype_custom": false, "name": "order_year", "rename": "", "selected": true}, {"date_format": "", "dtype": "Int64", "dtype_custom": false, "name": "order_month", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "order_year_month", "rename": "", "selected": true}, {"date_format": "", "dtype": "Boolean", "dtype_custom": false, "name": "is_bulk", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "value_band", "rename": "", "selected": true}, {"date_format": "", "dtype": "Int64", "dtype_custom": false, "name": "risk_score", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "risk_band", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "customer_name", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "status_clean", "rename": "", "selected": true}]}'))
import json
import polars as pl
from trigger_designer.core.shaping.formula import run_node as _run_node
var_formula_1905914234560, = _run_node([var_select_1905914267456], json.loads('{"sections": [{"editor_height": 60, "formula_text": "[gross_local] * [usd_rate]", "target_column": "gross_revenue_usd_raw", "target_dtype": ""}, {"editor_height": 60, "formula_text": "CASE WHEN [risk_band] = \'High\' THEN 1 ELSE 0 END", "target_column": "is_high_risk", "target_dtype": ""}]}'))
import json
import polars as pl
from trigger_designer.core.shaping.aggregate import run_node as _run_node
var_groupby_1905914212992, = _run_node([var_formula_1905914234560], json.loads('{"actions": [{"action": "N_Unique", "field": "order_id", "output_name": "clean_orders"}, {"action": "Sum", "field": "net_revenue_usd", "output_name": "net_revenue_usd"}, {"action": "Sum", "field": "gross_margin_usd", "output_name": "gross_margin_usd"}, {"action": "Sum", "field": "is_returned", "output_name": "returned_orders"}, {"action": "N_Unique", "field": "customer_id", "output_name": "distinct_customers"}, {"action": "N_Unique", "field": "product_id", "output_name": "distinct_products"}, {"action": "Sum", "field": "gross_revenue_usd_raw", "output_name": "gross_revenue_usd_raw"}, {"action": "Sum", "field": "is_high_risk", "output_name": "high_risk_orders"}]}'))
import json
import polars as pl
from trigger_designer.core.shaping.select import run_node as _run_node
var_select_1905914246592, = _run_node([var_groupby_1905914212992], json.loads('{"auto_accept_new_columns": true, "columns": [{"date_format": "", "dtype": "Int64", "dtype_custom": false, "name": "clean_orders", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "gross_revenue_usd_raw", "rename": "gross_revenue_usd", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "net_revenue_usd", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "gross_margin_usd", "rename": "", "selected": true}, {"date_format": "", "dtype": "Int64", "dtype_custom": false, "name": "returned_orders", "rename": "", "selected": true}, {"date_format": "", "dtype": "Int64", "dtype_custom": false, "name": "distinct_customers", "rename": "", "selected": true}, {"date_format": "", "dtype": "Int64", "dtype_custom": false, "name": "distinct_products", "rename": "", "selected": true}, {"date_format": "", "dtype": "Int64", "dtype_custom": false, "name": "high_risk_orders", "rename": "", "selected": true}]}'))
import json
import polars as pl
from trigger_designer.core.shaping.formula import run_node as _run_node
var_formula_1905914240832, = _run_node([var_select_1905914246592], json.loads('{"sections": [{"editor_height": 60, "formula_text": "ROUND([gross_revenue_usd], 2)", "target_column": "gross_revenue_usd", "target_dtype": ""}, {"editor_height": 120, "formula_text": "CASE WHEN [net_revenue_usd] = 0 \\nTHEN NULL \\nELSE ROUND([gross_margin_usd] / [net_revenue_usd], 4) \\nEND", "target_column": "margin_pct", "target_dtype": ""}]}'))
import json
import polars as pl
from trigger_designer.core.shaping.select import run_node as _run_node
var_select_1905914272832, = _run_node([var_formula_1905914240832], json.loads('{"auto_accept_new_columns": true, "columns": [{"date_format": "", "dtype": "Int64", "dtype_custom": false, "name": "clean_orders", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "gross_revenue_usd", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "net_revenue_usd", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "gross_margin_usd", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "margin_pct", "rename": "", "selected": true}, {"date_format": "", "dtype": "Int64", "dtype_custom": false, "name": "returned_orders", "rename": "", "selected": true}, {"date_format": "", "dtype": "Int64", "dtype_custom": false, "name": "high_risk_orders", "rename": "", "selected": true}, {"date_format": "", "dtype": "Int64", "dtype_custom": false, "name": "distinct_customers", "rename": "", "selected": true}, {"date_format": "", "dtype": "Int64", "dtype_custom": false, "name": "distinct_products", "rename": "", "selected": true}]}'))
import json
import polars as pl
from trigger_designer.core.shaping.sort import run_node as _run_node
var_sort_1905914237376, = _run_node([var_groupby_1905914078336], json.loads('{"keys": [{"column": "segment", "order": "Ascending"}, {"column": "risk_band", "order": "Ascending"}]}'))
import json
from trigger_designer.core.shaping.file_output import write_node as _write_node
_write_node([var_sort_1905914237376], json.loads('{"compression": null, "delimiter": ",", "filePath": "C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/segment_revenue.csv", "file_format": "csv", "include_bom": false, "use_streaming": true}'))
import json
from trigger_designer.core.shaping.file_output import write_node as _write_node
_write_node([var_union_1905913616000], json.loads('{"compression": null, "delimiter": ",", "filePath": "C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/01 enriched customer_id.csv", "file_format": "csv", "include_bom": false, "use_streaming": true}'))
import json
from trigger_designer.core.shaping.file_output import write_node as _write_node
_write_node([var_union_1905913691968], json.loads('{"compression": null, "delimiter": ",", "filePath": "C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/02 enriched product_id.csv", "file_format": "csv", "include_bom": false, "use_streaming": true}'))
import json
from trigger_designer.core.shaping.file_output import write_node as _write_node
_write_node([var_union_1905913630784], json.loads('{"compression": null, "delimiter": ",", "filePath": "C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/03 enriched supplier_id.csv", "file_format": "csv", "include_bom": false, "use_streaming": true}'))
import json
from trigger_designer.core.shaping.file_output import write_node as _write_node
_write_node([var_union_1905913763328], json.loads('{"compression": null, "delimiter": ",", "filePath": "C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/04 enriched channel_id.csv", "file_format": "csv", "include_bom": false, "use_streaming": true}'))
import json
from trigger_designer.core.shaping.file_output import write_node as _write_node
_write_node([var_union_1905913792000], json.loads('{"compression": null, "delimiter": ",", "filePath": "C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/05 enriched currency.csv", "file_format": "csv", "include_bom": false, "use_streaming": true}'))
import json
import polars as pl
from trigger_designer.core.shaping.transpose import run_node as _run_node
var_transpose_1905914237312, = _run_node([var_select_1905914272832], json.loads('{"data_columns": ["clean_orders", "gross_revenue_usd", "net_revenue_usd", "gross_margin_usd", "margin_pct", "returned_orders", "high_risk_orders", "distinct_customers", "distinct_products"], "key_columns": [], "missing_action": "warn"}'))
import json
import polars as pl
from trigger_designer.core.shaping.select import run_node as _run_node
var_select_1905914393152, = _run_node([var_transpose_1905914237312], json.loads('{"auto_accept_new_columns": true, "columns": [{"date_format": "", "dtype": "String", "dtype_custom": false, "name": "Name", "rename": "metric", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "Value", "rename": "value", "selected": true}]}'))
import json
from trigger_designer.core.shaping.file_output import write_node as _write_node
_write_node([var_select_1905914393152], json.loads('{"compression": null, "delimiter": ",", "filePath": "C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/kpi_summary.csv", "file_format": "csv", "include_bom": false, "use_streaming": true}'))
import json
from trigger_designer.core.shaping.file_output import write_node as _write_node
_write_node([var_unique_1905896658944], json.loads('{"compression": null, "delimiter": ",", "filePath": "C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/04 dropped null key rows.csv", "file_format": "csv", "include_bom": false, "use_streaming": true}'))
import json
from trigger_designer.core.shaping.file_output import write_node as _write_node
_write_node([var_f_filter_1905896514560], json.loads('{"compression": null, "delimiter": ",", "filePath": "C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/rejected_quantity.csv", "file_format": "csv", "include_bom": false, "use_streaming": true}'))
import json
from trigger_designer.core.shaping.file_output import write_node as _write_node
_write_node([var_f_filter_1905896520448], json.loads('{"compression": null, "delimiter": ",", "filePath": "C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/rejected_price_outliers.csv", "file_format": "csv", "include_bom": false, "use_streaming": true}'))
import json
from trigger_designer.core.shaping.file_output import write_node as _write_node
_write_node([var_f_filter_1905896608768], json.loads('{"compression": null, "delimiter": ",", "filePath": "C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/rejected_future_dates.csv", "file_format": "csv", "include_bom": false, "use_streaming": true}'))
import json
from trigger_designer.core.shaping.file_output import write_node as _write_node
_write_node([var_duplicate_1905896658944], json.loads('{"compression": null, "delimiter": ",", "filePath": "C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/duplicate_orders.csv", "file_format": "csv", "include_bom": false, "use_streaming": true}'))
import json
from trigger_designer.core.shaping.file_output import write_node as _write_node
_write_node([var_l_join_1905896949568], json.loads('{"compression": null, "delimiter": ",", "filePath": "C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/orphan_customers.csv", "file_format": "csv", "include_bom": false, "use_streaming": true}'))
import json
from trigger_designer.core.shaping.file_output import write_node as _write_node
_write_node([var_l_join_1905896958912], json.loads('{"compression": null, "delimiter": ",", "filePath": "C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/orphan_products.csv", "file_format": "csv", "include_bom": false, "use_streaming": true}'))
import json
import polars as pl
from trigger_designer.core.shaping.select import run_node as _run_node
var_select_1905914479616, = _run_node([var_formula_1905913826240], json.loads('{"auto_accept_new_columns": true, "columns": [{"date_format": "", "dtype": "String", "dtype_custom": false, "name": "order_id", "rename": "", "selected": true}, {"date_format": "", "dtype": "Datetime", "dtype_custom": false, "name": "order_ts", "rename": "", "selected": true}, {"date_format": "", "dtype": "Int64", "dtype_custom": false, "name": "order_year", "rename": "", "selected": true}, {"date_format": "", "dtype": "Int64", "dtype_custom": false, "name": "order_month", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "order_year_month", "rename": "", "selected": true}, {"date_format": "", "dtype": "Int64", "dtype_custom": false, "name": "customer_id", "rename": "", "selected": true}, {"date_format": "", "dtype": "Int64", "dtype_custom": false, "name": "product_id", "rename": "", "selected": true}, {"date_format": "", "dtype": "Int64", "dtype_custom": false, "name": "supplier_id", "rename": "", "selected": true}, {"date_format": "", "dtype": "Int64", "dtype_custom": false, "name": "channel_id", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "channel_name", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "channel_group", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "category", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "subcategory", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "brand", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "customer_country", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "region", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "segment", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "loyalty_tier", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "currency", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "usd_rate", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "status", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "status_clean", "rename": "", "selected": true}, {"date_format": "", "dtype": "Int64", "dtype_custom": false, "name": "quantity", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "unit_price_local", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "discount_pct", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "net_local", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "total_local", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "net_revenue_usd", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "cogs_usd", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "gross_margin_usd", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "margin_pct", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "value_band", "rename": "", "selected": true}, {"date_format": "", "dtype": "Int64", "dtype_custom": false, "name": "risk_score", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "risk_band", "rename": "", "selected": true}, {"date_format": "", "dtype": "Boolean", "dtype_custom": false, "name": "is_returned", "rename": "", "selected": true}, {"date_format": "", "dtype": "Boolean", "dtype_custom": false, "name": "is_bulk", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "country", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "customer_age_band", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "customer_currency", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "customer_email", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "is_digital", "rename": "", "selected": true}, {"date_format": "", "dtype": "Date", "dtype_custom": false, "name": "launch_date", "rename": "", "selected": true}, {"date_format": "", "dtype": "Int64", "dtype_custom": false, "name": "lead_time_days", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "payment_method", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "product_name", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "reliability_score", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "shipping_local", "rename": "", "selected": true}, {"date_format": "", "dtype": "Date", "dtype_custom": false, "name": "signup_date", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "sku", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "supplier_name", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "tax_local", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "unit_cost", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "unit_price", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "currency_name", "rename": "", "selected": true}, {"date_format": "", "dtype": "String", "dtype_custom": false, "name": "customer_name", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "g", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "gross_local", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "discount_local", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "unit_price_usd", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "tax_usd", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "shipping_usd", "rename": "", "selected": true}, {"date_format": "", "dtype": "Float64", "dtype_custom": false, "name": "total_usd", "rename": "", "selected": true}]}'))
import json
from trigger_designer.core.shaping.file_output import write_node as _write_node
_write_node([var_select_1905914479616], json.loads('{"compression": null, "delimiter": ",", "filePath": "C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/orders_enriched.csv", "file_format": "csv", "include_bom": false, "use_streaming": true}'))
import json
import polars as pl
from trigger_designer.core.shaping.filter import run_node as _run_node
var_t_filter_1905914489472, var_f_filter_1905914489472 = _run_node([var_formula_1905913826240], json.loads('{"column": "segment", "expression": "", "mode": "builder", "operation": "Equals", "value": "Enterprise", "value2": ""}'))
import json
from trigger_designer.core.shaping.file_output import write_node as _write_node
_write_node([var_t_filter_1905914489472], json.loads('{"compression": null, "delimiter": ",", "filePath": "C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/orders_enterprise.csv", "file_format": "csv", "include_bom": false, "use_streaming": true}'))
import json
import polars as pl
from trigger_designer.core.shaping.filter import run_node as _run_node
var_t_filter_1905914533120, var_f_filter_1905914533120 = _run_node([var_formula_1905913826240], json.loads('{"column": "risk_band", "expression": "", "mode": "builder", "operation": "Equals", "value": "High", "value2": ""}'))
import json
from trigger_designer.core.shaping.file_output import write_node as _write_node
_write_node([var_t_filter_1905914533120], json.loads('{"compression": null, "delimiter": ",", "filePath": "C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/orders_high_risk.csv", "file_format": "csv", "include_bom": false, "use_streaming": true}'))
import json
import polars as pl
from trigger_designer.core.shaping.split import run_node as _run_node
var_estimation_1905914538880, var_validation_1905914538880 = _run_node([var_formula_1905913826240], json.loads('{"estimation_percent": 80, "is_random": true, "random_seed": 42}'))
import json
from trigger_designer.core.shaping.file_output import write_node as _write_node
_write_node([var_estimation_1905914538880], json.loads('{"compression": null, "delimiter": ",", "filePath": "C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/fact_estimation.csv", "file_format": "csv", "include_bom": false, "use_streaming": true}'))
import json
from trigger_designer.core.shaping.file_output import write_node as _write_node
_write_node([var_validation_1905914538880], json.loads('{"compression": null, "delimiter": ",", "filePath": "C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/fact_validation.csv", "file_format": "csv", "include_bom": false, "use_streaming": true}'))
import json
import polars as pl
from trigger_designer.core.shaping.formula import run_node as _run_node
var_formula_1905914593664, = _run_node([var_select_1905896210624], json.loads('{"sections": [{"editor_height": 60, "formula_text": "\'customers\'", "target_column": "source_table", "target_dtype": ""}]}'))
import json
import polars as pl
from trigger_designer.core.shaping.formula import run_node as _run_node
var_formula_1905914599488, = _run_node([var_select_1905896215680], json.loads('{"sections": [{"editor_height": 60, "formula_text": "\'products\'", "target_column": "source_table", "target_dtype": ""}]}'))
import json
import polars as pl
from trigger_designer.core.shaping.formula import run_node as _run_node
var_formula_1905914604928, = _run_node([var_select_1905896218368], json.loads('{"sections": [{"editor_height": 60, "formula_text": "\'suppliers\'", "target_column": "source_table", "target_dtype": ""}]}'))
import json
import polars as pl
from trigger_designer.core.shaping.formula import run_node as _run_node
var_formula_1905914643200, = _run_node([var_select_1905895888640], json.loads('{"sections": [{"editor_height": 60, "formula_text": "\'channels\'", "target_column": "source_table", "target_dtype": ""}]}'))
import json
import polars as pl
from trigger_designer.core.shaping.formula import run_node as _run_node
var_formula_1905914649088, = _run_node([var_formula_1905896734656], json.loads('{"sections": [{"editor_height": 60, "formula_text": "\'fx_rates\'", "target_column": "source_table", "target_dtype": ""}]}'))
import polars as pl
_union_inputs_1905914649344 = [var_formula_1905914599488, var_formula_1905914593664]
var_union_1905914649344 = pl.concat([(f.lazy() if isinstance(f, pl.DataFrame) else f) for f in _union_inputs_1905914649344], how='diagonal_relaxed')
del _union_inputs_1905914649344
import polars as pl
_union_inputs_1905914654144 = [var_union_1905914649344, var_formula_1905914604928]
var_union_1905914654144 = pl.concat([(f.lazy() if isinstance(f, pl.DataFrame) else f) for f in _union_inputs_1905914654144], how='diagonal_relaxed')
del _union_inputs_1905914654144
import polars as pl
_union_inputs_1905914663040 = [var_formula_1905914643200, var_union_1905914654144]
var_union_1905914663040 = pl.concat([(f.lazy() if isinstance(f, pl.DataFrame) else f) for f in _union_inputs_1905914663040], how='diagonal_relaxed')
del _union_inputs_1905914663040
import polars as pl
_union_inputs_1905914668480 = [var_union_1905914663040, var_formula_1905914649088]
var_union_1905914668480 = pl.concat([(f.lazy() if isinstance(f, pl.DataFrame) else f) for f in _union_inputs_1905914668480], how='diagonal_relaxed')
del _union_inputs_1905914668480
import json
from trigger_designer.core.shaping.file_output import write_node as _write_node
_write_node([var_union_1905914668480], json.loads('{"compression": null, "delimiter": ",", "filePath": "C:/Users/KASHVINCHANDRASAN/Desktop/Personal/Github/TriggerEditor/savedfiles/Example_2_Retail_Ledger/app_output/reference_data_union.csv", "file_format": "csv", "include_bom": false, "use_streaming": true}'))
