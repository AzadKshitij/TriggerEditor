"""Characterization tests for the legacy single-file File Input path.

These freeze the generated code and live frames that existed before input
types were added. The legacy branch runs every existing workflow, so a change
to these strings is a deliberate output change, not a cosmetic edit.
"""

from __future__ import annotations

import polars as pl

from trigger_designer.qt.widgets.nodes.InOut.file_input import FileInputContent


def _legacy(path: str, **overrides) -> FileInputContent:
    content = FileInputContent.__new__(FileInputContent)
    content.filePath = path
    content.id = 7
    content.preview_rows = 10
    content.file_type = "csv"
    content.record_limit = 0
    content.output_filename_as_field = False
    content.delimiter = ","
    content.first_row_contains_field_names = True
    content.selected_sheet = ""
    content.available_sheets = []
    content.start_row = 1
    content.data = None
    content.variable_name = "var_file_input_7"
    content.schema_snapshot = []
    content.file_metadata = {}
    content._missing_file_attempts = {}
    for key, value in overrides.items():
        setattr(content, key, value)
    return content


EXPECTED_CSV_CODE = (
    "import polars as pl\n"
    "import os\n"
    "from trigger_designer.core.input_source import name_blank_columns\n"
    "\n"
    "# Always use LazyFrame for memory efficiency\n"
    "# Using LazyFrame for optimal memory usage\n"
    "var_file_input_7 = name_blank_columns("
    "pl.scan_csv('C:\\\\data\\\\in.csv', infer_schema=False))\n"
    "\n"
    "# var_file_input_7 is now a LazyFrame for memory-efficient processing\n"
    "# Use .collect() only when you need to materialize the data\n"
)

EXPECTED_TXT_CODE = (
    "import polars as pl\n"
    "import os\n"
    "from trigger_designer.core.input_source import name_blank_columns\n"
    "\n"
    "# Always use LazyFrame for memory efficiency\n"
    "# Using LazyFrame for optimal memory usage\n"
    "var_file_input_7 = name_blank_columns("
    "pl.scan_csv('C:\\\\data\\\\in.txt', "
    "infer_schema=False, separator=';'))\n"
    "\n"
    "# var_file_input_7 is now a LazyFrame for memory-efficient processing\n"
    "# Use .collect() only when you need to materialize the data\n"
)

EXPECTED_NO_HEADER_CODE = (
    "import polars as pl\n"
    "import os\n"
    "from trigger_designer.core.input_source import name_blank_columns\n"
    "\n"
    "# Always use LazyFrame for memory efficiency\n"
    "# Using LazyFrame for optimal memory usage\n"
    "var_file_input_7 = name_blank_columns("
    "pl.scan_csv('C:\\\\data\\\\in.csv', "
    "infer_schema=False, has_header=False))\n"
    "\n"
    "# var_file_input_7 is now a LazyFrame for memory-efficient processing\n"
    "# Use .collect() only when you need to materialize the data\n"
)

EXPECTED_EXCEL_CODE = (
    "import polars as pl\n"
    "import os\n"
    "\n"
    "# Always use LazyFrame for memory efficiency\n"
    "import fastexcel\n"
    "reader_7 = fastexcel.read_excel('C:\\\\data\\\\in.xlsx')\n"
    "excel_df_7 = reader_7.load_sheet(idx_or_name='Jan', header_row=1)\n"
    "# Convert to polars LazyFrame for memory efficiency\n"
    "try:\n"
    "    eager_df_7 = excel_df_7.to_polars()\n"
    "except AttributeError:\n"
    "    eager_df_7 = pl.from_arrow(excel_df_7.to_arrow())\n"
    "# Convert to LazyFrame immediately\n"
    "var_file_input_7 = eager_df_7.lazy()\n"
    "\n"
    "# var_file_input_7 is now a LazyFrame for memory-efficient processing\n"
    "# Use .collect() only when you need to materialize the data\n"
)

EXPECTED_FILENAME_CODE = (
    "import polars as pl\n"
    "import os\n"
    "from trigger_designer.core.input_source import name_blank_columns\n"
    "\n"
    "# Always use LazyFrame for memory efficiency\n"
    "# Using LazyFrame for optimal memory usage\n"
    "var_file_input_7 = name_blank_columns("
    "pl.scan_csv('C:\\\\data\\\\in.csv', infer_schema=False))\n"
    "# Add filename field using lazy operations\n"
    "filename_7 = os.path.basename('C:\\\\data\\\\in.csv')\n"
    "var_file_input_7 = var_file_input_7.with_columns("
    "pl.lit(filename_7).alias('FileName'))\n"
    "\n"
    "# var_file_input_7 is now a LazyFrame for memory-efficient processing\n"
    "# Use .collect() only when you need to materialize the data\n"
)


def test_legacy_csv_get_code_is_frozen() -> None:
    assert _legacy(r"C:\data\in.csv").get_code() == EXPECTED_CSV_CODE


def test_legacy_txt_semicolon_code_frozen() -> None:
    content = _legacy(r"C:\data\in.txt", file_type="txt", delimiter=";")
    assert content.get_code() == EXPECTED_TXT_CODE


def test_legacy_no_header_code_frozen() -> None:
    content = _legacy(r"C:\data\in.csv", first_row_contains_field_names=False)
    assert content.get_code() == EXPECTED_NO_HEADER_CODE


def test_legacy_excel_code_frozen() -> None:
    content = _legacy(
        r"C:\data\in.xlsx", file_type="excel", selected_sheet="Jan", start_row=2
    )
    assert content.get_code() == EXPECTED_EXCEL_CODE


def test_legacy_filename_field_code_frozen() -> None:
    content = _legacy(r"C:\data\in.csv", output_filename_as_field=True)
    assert content.get_code() == EXPECTED_FILENAME_CODE


def test_legacy_serialize_keys_are_still_present() -> None:
    content = _legacy(r"C:\data\in.csv")
    keys = set(content.serialize_content_state({}))
    assert {
        "filePath",
        "file_type",
        "record_limit",
        "output_filename_as_field",
        "delimiter",
        "first_row_contains_field_names",
        "selected_sheet",
        "available_sheets",
        "start_row",
        "schema_snapshot",
        "file_metadata",
    } <= keys


def test_legacy_live_csv_frame_all_strings(tmp_path) -> None:
    source = tmp_path / "in.csv"
    source.write_text("id,name\n1,Ann\n2,Bob\n", encoding="utf-8")
    content = _legacy(str(source))
    frame = content._read_file_based_on_type(str(source))
    assert isinstance(frame, pl.LazyFrame)
    assert all(dtype == pl.String for dtype in frame.collect_schema().values())
    assert frame.collect().rows() == [("1", "Ann"), ("2", "Bob")]


def test_legacy_live_csv_blank_header_gets_a_name(tmp_path) -> None:
    source = tmp_path / "in.csv"
    source.write_text(",name\n1,Ann\n", encoding="utf-8")
    content = _legacy(str(source))
    frame = content._read_file_based_on_type(str(source))
    assert frame.collect_schema().names() == ["column_1", "name"]
    assert frame.collect().rows() == [("1", "Ann")]


def test_legacy_generated_code_names_a_blank_header(tmp_path) -> None:
    source = tmp_path / "in.csv"
    source.write_text(",name\n1,Ann\n", encoding="utf-8")
    content = _legacy(str(source))
    namespace: dict = {}
    exec(content.get_code(), {"__name__": "__main__"}, namespace)  # noqa: S102
    frame = namespace[content.variable_name].collect()
    assert frame.columns == ["column_1", "name"]
    assert frame.rows() == [("1", "Ann")]


def test_legacy_live_csv_delimiter_and_filename_field(tmp_path) -> None:
    source = tmp_path / "in.csv"
    source.write_text("id;name\n1;Ann\n", encoding="utf-8")
    content = _legacy(str(source), delimiter=";", output_filename_as_field=True)
    frame = content._read_file_based_on_type(str(source)).collect()
    assert frame.columns == ["id", "name", "FileName"]
    assert frame["FileName"].to_list() == ["in.csv"]
