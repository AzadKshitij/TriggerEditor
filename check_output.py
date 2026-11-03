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

from trigger_designer.core.input_source import build_source

# File Input (csv, builder path)
_spec_1873945534272 = {
    "filePath": "C:/Users/<you>/TriggerEditor/savedfiles/Example_3_AE_Winter_Watch/data",
    "file_type": "csv",
    "record_limit": 0,
    "output_filename_as_field": True,
    "delimiter": ",",
    "first_row_contains_field_names": True,
    "selected_sheet": "",
    "start_row": 1,
    "include_patterns": [],
    "exclude_patterns": ["~$*", ".*", "Thumbs.db", "desktop.ini"],
    "recursive": False,
    "file_order": "name",
    "file_name_column_name": "FileName",
    "file_name_value": "name",
    "schema_mismatch": "union",
    "on_file_error": "stop",
    "max_files": 10000,
    "encoding": "utf8",
    "read_as_text": False,
    "json_nested": "text",
    "sheet_mode": "one",
    "selected_sheets": [],
    "add_sheet_name_column": False,
    "sheet_name_column_name": "SheetName",
    "db_mode": "table",
    "db_table": "",
    "db_query": "",
}
var_file_input_1873945534272 = pl.DataFrame()
var_file_input_1873945534272 = build_source(_spec_1873945534272).frame
