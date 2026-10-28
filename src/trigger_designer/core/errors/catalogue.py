"""The only place user-facing error sentences live.

Every entry is a template; the translator fills it from engine facts. Entries
marked ``passthrough`` are raised by other feature cores with their own
message and a ``TD-`` code; translation keeps that message and adds the hint.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TypedDict

from trigger_designer.core.errors.model import shorten


class Entry(TypedDict, total=False):
    severity: str
    title: str
    title_located: str
    detail: str
    detail_located: str
    fixes: tuple[tuple[str, str], ...]
    hint: str
    reserved: bool
    passthrough: bool


class _SafeDict(dict):
    def __missing__(self, key: str) -> str:
        return "?"


_OPTIONAL_PARAMS = (
    "node_label",
    "culprit_label",
    "path",
    "path_name",
    "column",
    "columns",
    "value",
    "values",
    "row",
    "row_hint",
    "others_sentence",
    "available",
    "suggestion",
    "suggestion_sentence",
    "target",
    "target_one",
    "target_human",
    "target_sql",
    "op_past",
    "reason",
    "function",
    "sheet",
    "seconds",
    "mb",
    "left_key",
    "left_type",
    "right_key",
    "right_type",
    "differences",
    "message",
    "engine",
    "engine_duckdb",
    "failing_count",
    "expected",
    "got",
    "var",
    "input_number",
    "source",
    "n",
    "m",
    "k",
    "min",
    "kind",
    "col",
    "rule",
    "text",
    "fmt",
    "label",
    "detail",
    "name",
)


CATALOGUE: dict[str, Entry] = {
    "TD-IN-001": {
        "severity": "error",
        "title": "The file '{path_name}' was not found.",
        "detail": "Looked for: {path}",
        "fixes": (
            (
                "Check that the file exists and that the drive or network share is reachable.",
                "",
            ),
            ("Choose the file again with Browse in the File Input node.", ""),
        ),
    },
    "TD-IN-002": {
        "severity": "error",
        "title": "'{path_name}' cannot be read: it is open in another program or access is denied.",
        "detail": "{reason}",
        "fixes": (
            ("Close the file in Excel or any other program, then run again.", ""),
            ("Ask for read permission on the folder.", ""),
        ),
    },
    "TD-IN-003": {
        "severity": "error",
        "title": "Sheet '{sheet}' does not exist in '{path_name}'.",
        "detail": "Available sheets: {available}.{suggestion_sentence}",
        "fixes": (
            ("Pick one of the available sheets in the node settings.", ""),
            ("Use the sheet '{suggestion}' instead.", "suggestion"),
        ),
    },
    "TD-IN-004": {
        "severity": "error",
        "title": "'{path_name}' is not UTF-8 text.",
        "detail": "The file contains bytes that are not valid UTF-8, typical for files saved by older Excel versions.",
        "fixes": (
            ("Open the file in Excel or Notepad and save it again as 'CSV UTF-8'.", ""),
        ),
    },
    "TD-IN-005": {
        "severity": "error",
        "title": "'{path_name}' is empty.",
        "detail": "The file has no header and no rows.",
        "fixes": (
            (
                "Check that the export that produced the file finished, then reload it.",
                "",
            ),
        ),
    },
    "TD-IN-006": {
        "severity": "error",
        "title": "'{path_name}' is not a readable Excel workbook.",
        "detail": "{reason}",
        "fixes": (
            ("Open it in Excel and save it again as .xlsx.", ""),
            (
                "If it is really a text file, rename it to .csv and choose File type CSV.",
                "",
            ),
        ),
    },
    "TD-IN-007": {
        "severity": "error",
        "title": "Some rows have more fields than the header.",
        "detail": "Usually the wrong delimiter or an unquoted delimiter inside a value.",
        "fixes": (
            ("Check the delimiter in the node settings.", ""),
            ("Make sure values containing the delimiter are wrapped in quotes.", ""),
        ),
    },
    "TD-SCH-001": {
        "severity": "error",
        "title": "Column '{column}' was not found.",
        "detail": "Available columns: {available}.{suggestion_sentence}",
        "fixes": (
            ("Use the column '{suggestion}' instead.", "suggestion"),
            (
                "Select the column again in this node; it may have been renamed, dropped or typed differently upstream.",
                "",
            ),
        ),
    },
    "TD-SCH-002": {
        "severity": "error",
        "title": "The column name '{column}' appears more than once.",
        "detail": "Every column needs a unique name.",
        "fixes": (
            ("Rename one of the columns with a Select node before this step.", ""),
        ),
    },
    "TD-SCH-003": {
        "severity": "warning",
        "reserved": True,
        "title": "The columns in '{path_name}' changed since the workflow was saved.",
        "detail": "{differences}",
        "fixes": (("Review the nodes that use the changed columns.", ""),),
    },
    "TD-SCH-004": {
        "severity": "error",
        "title": "The two tables have different columns or types.",
        "detail": "Differences: {differences}",
        "fixes": (
            (
                "Make both inputs have the same columns and types (use Select nodes), or use a mode that fills missing columns.",
                "",
            ),
        ),
    },
    "TD-SCH-005": {
        "severity": "error",
        "title": "Columns have different numbers of rows.",
        "detail": "{reason}",
        "fixes": (
            (
                "Check the upstream step that builds these columns from separate lists.",
                "",
            ),
        ),
    },
    "TD-TYP-001": {
        "severity": "error",
        "title": "Column '{column}' has values that cannot be read as {target_human}.",
        "title_located": "Column '{column}' contains '{value}' in row {row:,}, which cannot be read as {target_human}.",
        "detail": "{reason}",
        "detail_located": "{others_sentence}",
        "fixes": (
            ("Clean or correct the value{row_hint} in the source data.", ""),
            (
                "Add a Select node before this one and set '{column}' to {target_one}; values that cannot be converted become empty instead of stopping the run.",
                "",
            ),
            (
                "In the formula, use TRY_CAST([{column}] AS {target_sql}) so bad values become empty.",
                "engine_duckdb",
            ),
        ),
    },
    "TD-TYP-002": {
        "severity": "error",
        "title": "Join keys have different types: '{left_key}' is {left_type} but '{right_key}' is {right_type}.",
        "detail": "Both key columns must hold the same type of value.",
        "fixes": (
            (
                "Add a Select node on one side and set the key column to the same type (usually Text).",
                "",
            ),
            ("Check that both columns really contain the same kind of value.", ""),
        ),
    },
    "TD-TYP-003": {
        "severity": "error",
        "title": "Column '{column}' is text, so it cannot be {op_past}.",
        "title_located": "Column '{column}' contains text ('{value}') in row {row:,}, so it cannot be {op_past}.",
        "detail": "{reason}",
        "detail_located": "{others_sentence}",
        "fixes": (
            ("Clean or correct the value{row_hint}.", ""),
            (
                "Add a Select node before this one and set '{column}' to Decimal.",
                "",
            ),
        ),
    },
    "TD-TYP-004": {
        "severity": "error",
        "title": "Text and numbers cannot be compared.",
        "detail": "{reason}",
        "fixes": (
            (
                "Set the column to a number type with a Select node, or put the value in quotes if the column is text.",
                "",
            ),
        ),
    },
    "TD-TYP-005": {
        "severity": "error",
        "title": "A value in '{column}' does not fit in the target type ({target}).",
        "title_located": "'{value}' in row {row:,} of '{column}' does not fit in the target type ({target}).",
        "detail": "{reason}",
        "fixes": (
            ("Use a wider type (for example Int64 or Decimal) in a Select node.", ""),
        ),
    },
    "TD-TYP-006": {
        "severity": "error",
        "title": "This step needs a {expected} column but '{column}' is {got}.",
        "fixes": (
            ("Check which column this node uses and its type in the Select node.", ""),
        ),
    },
    "TD-TYP-007": {
        "severity": "error",
        "title": "The filter condition must give true or false, not {got}.",
        "fixes": (("Write a comparison such as [Amount] > 0.", ""),),
    },
    "TD-EXP-001": {
        "severity": "error",
        "title": "The expression has a syntax error.",
        "detail": "{reason}",
        "fixes": (("Check brackets, quotes and operators near the marked spot.", ""),),
    },
    "TD-EXP-002": {
        "severity": "error",
        "title": "Unknown function '{function}'.",
        "detail": "{suggestion_sentence}",
        "fixes": (
            ("Use '{suggestion}' instead.", "suggestion"),
            ("Check the function name in the formula help list.", ""),
        ),
    },
    "TD-EXP-003": {
        "severity": "error",
        "title": "The expression cannot be evaluated.",
        "detail": "{reason}",
        "fixes": (("Check the column names and types used in the expression.", ""),),
    },
    "TD-EXP-004": {
        "severity": "error",
        "title": "The pattern (regular expression) is not valid.",
        "detail": "{reason}",
        "fixes": (("Escape special characters such as ( ) [ ] with a backslash.", ""),),
    },
    "TD-EXP-005": {
        "severity": "error",
        "title": "A function received a value it cannot use.",
        "detail": "{reason}",
        "fixes": (
            (
                "Check the arguments of the function, or use TRY_CAST for conversions.",
                "",
            ),
        ),
    },
    "TD-JOI-001": {
        "severity": "error",
        "reserved": True,
        "title": "No columns are mapped.",
        "fixes": (("Map at least one column in the node settings.", ""),),
    },
    "TD-JOI-002": {
        "severity": "error",
        "reserved": True,
        "title": "Both inputs must be connected.",
        "fixes": (("Connect a node to each input.", ""),),
    },
    "TD-OUT-001": {
        "severity": "error",
        "title": "The output folder does not exist.",
        "detail": "Could not create '{path}' because its folder is missing.",
        "fixes": (
            (
                "Create the folder, or choose an existing one in the File Output node.",
                "",
            ),
        ),
    },
    "TD-OUT-002": {
        "severity": "error",
        "title": "'{path_name}' cannot be written: it is open in another program or read-only.",
        "detail": "{reason}",
        "fixes": (
            ("Close the file in Excel or any other program, then run again.", ""),
            ("Choose a different file name or clear the read-only flag.", ""),
        ),
    },
    "TD-OUT-003": {
        "severity": "error",
        "title": "Excel export is not available in this installation.",
        "detail": "The component that writes .xlsx files (xlsxwriter) is missing.",
        "fixes": (
            ("Export as CSV or Parquet instead.", ""),
            ("Reinstall the application.", ""),
        ),
    },
    "TD-OUT-004": {
        "severity": "error",
        "title": "'{path_name}' is not a valid output file name.",
        "detail": "{reason}",
        "fixes": (
            ('Remove characters such as < > : " | ? * and keep the path short.', ""),
            ("Choose a file, not a folder.", ""),
        ),
    },
    "TD-OUT-005": {
        "severity": "error",
        "title": "The disk is full.",
        "detail": "Could not finish writing '{path_name}'.",
        "fixes": (("Free some space or write to another drive.", ""),),
    },
    "TD-OUT-006": {
        "severity": "error",
        "title": "Nothing is connected to this output.",
        "fixes": (
            (
                "Connect the node whose result you want to save to the File Output node.",
                "",
            ),
        ),
    },
    "TD-RUN-001": {
        "severity": "error",
        "title": "This step took longer than {seconds} seconds and was stopped.",
        "detail": "Large inputs or heavy joins can exceed the limit.",
        "fixes": (
            ("Filter or sample the data earlier in the workflow.", ""),
            ("Write large results to Parquet instead of CSV or Excel.", ""),
        ),
    },
    "TD-RUN-002": {
        "severity": "error",
        "title": "This step ran out of memory.",
        "detail": "{reason}",
        "fixes": (
            ("Filter rows or drop unused columns earlier in the workflow.", ""),
            ("Close other programs and run again.", ""),
        ),
    },
    "TD-RUN-003": {
        "severity": "error",
        "reserved": True,
        "title": "Stopped because '{culprit_label}' has a problem.",
        "detail": "The problem is in the earlier step, not in this one.",
        "fixes": (("Fix '{culprit_label}' first, then run again.", ""),),
    },
    "TD-RUN-004": {
        "severity": "warning",
        "reserved": True,
        "title": "The run was cancelled before this step.",
        "fixes": (("Run the workflow again.", ""),),
    },
    "TD-RUN-005": {
        "severity": "warning",
        "reserved": True,
        "title": "Input {input_number} is not connected.",
        "fixes": (("Connect a node to this input.", ""),),
    },
    "TD-RUN-006": {
        "severity": "error",
        "reserved": True,
        "title": "This step needs the result of an earlier step that is not available.",
        "detail": "{reason}",
        "fixes": (
            (
                "Fix the earlier step ('{culprit_label}') and run again.",
                "culprit_label",
            ),
            ("Open the earlier step so it is calculated, then run again.", ""),
        ),
    },
    "TD-RUN-008": {
        "severity": "warning",
        "reserved": True,
        "title": "Skipped because '{culprit_label}' failed.",
        "detail": "Independent branches of the workflow still ran.",
        "fixes": (("Fix '{culprit_label}' and run again.", ""),),
    },
    "TD-SYS-001": {
        "severity": "error",
        "reserved": True,
        "title": "{message}",
        "fixes": (("Check this node's settings.", ""),),
    },
    "TD-SYS-100": {
        "severity": "error",
        "title": "The data engine could not run this step.",
        "detail": "{reason}",
        "fixes": (
            (
                "Check the node settings and the upstream data; copy the details if you need help.",
                "",
            ),
        ),
    },
    "TD-SYS-998": {
        "severity": "error",
        "title": "The data engine stopped unexpectedly.",
        "detail": "This is an internal engine error, not a problem with your data.",
        "fixes": (("Run again; if it repeats, copy the details and report it.", ""),),
    },
    "TD-SYS-999": {
        "severity": "error",
        "title": "Something unexpected went wrong.",
        "detail": "{reason}",
        "fixes": (("Copy the details and report it if it repeats.", ""),),
    },
}

# Codes owned by other plans: title = the message carried by the exception.
_PASSTHROUGH: dict[str, tuple[str, str, str]] = {
    "TD-AUDIT-001": (
        "Choose the {label} column.",
        "Pick the column in the node settings.",
        "error",
    ),
    "TD-AUDIT-002": (
        "Column '{col}' is not in the input data.",
        "Pick the column again; it may have been renamed upstream.",
        "error",
    ),
    "TD-AUDIT-003": (
        "Column '{col}' holds nested values and cannot be used for this test.",
        "Choose a plain text, number or date column.",
        "error",
    ),
    "TD-AUDIT-004": (
        "{label} must be {rule}.",
        "Enter a value inside the allowed range.",
        "error",
    ),
    "TD-AUDIT-005": (
        "The input already has a column named '{name}', which this node adds.",
        "Rename the existing column first.",
        "error",
    ),
    "TD-AUDIT-006": (
        "'{text}' is not a date. Use YYYY-MM-DD.",
        "Type the date as year-month-day.",
        "error",
    ),
    "TD-AUDIT-007": (
        "Date format '{fmt}' is not supported.",
        "Choose one of the formats in the list.",
        "error",
    ),
    "TD-AUDIT-008": (
        "Switch on at least one risk test.",
        "Tick at least one test in the node settings.",
        "error",
    ),
    "TD-AUDIT-009": (
        "{label}: {detail}.",
        "Fix the list of numbers (count and order).",
        "error",
    ),
    "TD-AUDIT-010": (
        "No row has a readable amount in '{col}', so a value-based sample cannot be drawn.",
        "Choose a numeric amount column or clean the values.",
        "error",
    ),
    "TD-AUDIT-101": (
        "Only {n:,} rows were tested; at least {min:,} are needed for a reliable result.",
        "Treat the result as indicative only.",
        "warning",
    ),
    "TD-AUDIT-102": (
        "{n:,} values could not be read as {kind} and were skipped.",
        "Clean those values or convert the column with a Select node.",
        "warning",
    ),
    "TD-AUDIT-103": (
        "Requested {k:,} but only {n:,} rows exist; the whole population was selected.",
        "Lower the sample size.",
        "warning",
    ),
    "TD-SHAPE-001": (
        "A required setting is missing",
        "Fill in the missing setting.",
        "error",
    ),
    "TD-SHAPE-002": (
        "An output column name is empty, duplicated or already exists",
        "Choose a unique name.",
        "error",
    ),
    "TD-SHAPE-003": (
        "A selected column is not in the input any more",
        "Select the column again.",
        "error",
    ),
    "TD-SHAPE-004": (
        "A setting value is out of range or unknown",
        "Pick a value from the list or inside the range.",
        "error",
    ),
    "TD-SHAPE-005": (
        "A required input has no data",
        "Connect and fix the upstream node.",
        "error",
    ),
    "TD-SHAPE-040": (
        "The pattern is not a valid regular expression",
        "Escape special characters with a backslash.",
        "error",
    ),
    "TD-SHAPE-041": ("The pattern is too long", "Shorten the pattern.", "error"),
    "TD-SHAPE-042": ("Find text is empty", "Type the text to find.", "error"),
    "TD-SHAPE-043": (
        "Too many rules",
        "Remove rules or split them over two nodes.",
        "error",
    ),
    "TD-SHAPE-044": (
        "The column must be text",
        "Convert the column to text with a Select node.",
        "error",
    ),
    "TD-SHAPE-050": (
        "The column is not a date and not text",
        "Choose a date or text column.",
        "error",
    ),
    "TD-SHAPE-052": (
        "A holiday is not a YYYY-MM-DD date",
        "Type holidays as year-month-day.",
        "error",
    ),
    "TD-SHAPE-053": (
        "Working days must name at least one weekday",
        "Tick at least one weekday.",
        "error",
    ),
    "TD-SHAPE-060": (
        "Index, header and value columns must be different",
        "Pick three different columns.",
        "error",
    ),
    "TD-SHAPE-061": (
        "Too many new columns",
        "Filter the header column to fewer distinct values.",
        "error",
    ),
    "TD-SHAPE-070": (
        "Amount or date column is set on one side only",
        "Pick it on both sides, or on neither.",
        "error",
    ),
    "TD-SHAPE-071": (
        "Add a key column pair or a date column",
        "Add a key pair or a date window.",
        "error",
    ),
    "TD-SHAPE-072": (
        "Too many possible matches",
        "Add key columns or narrow the tolerance.",
        "error",
    ),
    "TD-CLI-001": (
        "The workflow file could not be read.",
        "Check the path and that it is a .tds file.",
        "error",
    ),
    "TD-CLI-002": (
        "The workflow was saved by a newer Trigger Designer.",
        "Update this program.",
        "error",
    ),
    "TD-CLI-003": (
        "The workflow uses an unknown node type.",
        "Open and re-save it in a compatible version.",
        "error",
    ),
    "TD-CLI-004": (
        "The workflow has a cycle.",
        "Remove the connection that loops back.",
        "error",
    ),
    "TD-CLI-005": (
        "Unknown or missing parameter.",
        "Use one of the listed parameter names.",
        "error",
    ),
    "TD-CLI-006": (
        "A parameter value is not valid.",
        "Use the example format shown.",
        "error",
    ),
    "TD-CLI-007": (
        "This parameter target is not supported.",
        "Choose a supported setting.",
        "error",
    ),
    "TD-CLI-008": (
        "The workflow has not been approved to run unattended.",
        "Approve it first (`approve`).",
        "error",
    ),
    "TD-CLI-009": (
        "The approved workflow changed since approval.",
        "Approve it again.",
        "error",
    ),
    "TD-CLI-010": (
        "The generated code was refused by the safety policy.",
        "Remove the flagged node or setting.",
        "error",
    ),
    "TD-CLI-011": (
        "A custom-code node was refused.",
        "Remove the custom-code node.",
        "error",
    ),
    "TD-CLI-012": (
        "Another run of this workflow is in progress.",
        "Wait and try again.",
        "error",
    ),
    "TD-CLI-013": (
        "The outputs could not be saved.",
        "Close the output files in other programs and run again.",
        "error",
    ),
    "TD-CLI-014": (
        "The output folder is missing or not writable.",
        "Create it or use `--create-output-dirs`.",
        "error",
    ),
    "TD-CLI-015": (
        "There is not enough free disk space.",
        "Free space or lower `--min-free-mb`.",
        "error",
    ),
    "TD-CLI-016": (
        "The scheduler could not be configured.",
        "Check Windows Task Scheduler permissions.",
        "error",
    ),
    "TD-CLI-017": (
        "The run log failed verification.",
        "Treat the log as modified.",
        "error",
    ),
    "TD-CLI-018": (
        "This workflow writes no files.",
        "Add a File Output node.",
        "warning",
    ),
    "TD-IN-010": (
        "I could not read the data in this file",
        "Check the file type and delimiter; the details name the column.",
        "error",
    ),
    "TD-IN-011": (
        "The input file could not be opened",
        "Check the path and your access rights.",
        "error",
    ),
    "TD-IN-012": (
        "The folder matches too many files",
        'Narrow the include pattern or raise "Max files".',
        "error",
    ),
    "TD-IN-013": (
        "The database could not be read as requested",
        "Check the table name and use a single SELECT statement; databases are read-only.",
        "error",
    ),
    "TD-IN-014": (
        "The File Input settings need attention",
        "Open File Input and fix the highlighted setting.",
        "error",
    ),
    "TD-SCH-010": (
        "An added column name already exists in the data",
        "Rename the filename/sheet column in File Input.",
        "error",
    ),
    "TD-SCH-011": (
        "Files in the folder have different columns",
        'Use "Union by name" or fix the odd file named in the details.',
        "error",
    ),
    "TD-OUT-010": (
        "A workpaper with this name already exists",
        'Choose another file name, or set "If the file exists" to New version.',
        "error",
    ),
    "TD-OUT-011": (
        "The table has too many columns for Excel",
        "Excel allows at most 16,384 columns; select fewer columns before writing.",
        "error",
    ),
    "TD-OUT-012": (
        "The workpaper settings are not valid",
        "Check the output file (it must end in .xlsx) and the Prepared on date (YYYY-MM-DD).",
        "error",
    ),
    "TD-OUT-013": (
        "The table is too large for an Excel sheet",
        "An Excel sheet holds at most 1,048,575 data rows; save it as CSV or Parquet instead.",
        "error",
    ),
    "TD-OUT-014": (
        "Excel could not create the workbook",
        "A sheet name or cell content is not valid for Excel; rename the sheet or shorten the text.",
        "error",
    ),
}

for _code, (_title, _hint, _severity) in _PASSTHROUGH.items():
    CATALOGUE[_code] = {
        "severity": _severity,
        "title": _title,
        "hint": _hint,
        "passthrough": True,
    }


def render_entry(
    code: str,
    params: Mapping[str, str | int],
    *,
    located: bool = False,
) -> tuple[str, str, tuple[str, ...]]:
    """Render one catalogue entry: (title, detail, fixes)."""
    entry = CATALOGUE.get(code)
    if entry is None:
        message = shorten(str(params.get("message", "")), 90)
        return message, "", ()
    values = _SafeDict({key: "" for key in _OPTIONAL_PARAMS})
    values.update({key: value for key, value in params.items()})
    for numeric in ("row", "n", "m", "k", "min", "failing_count", "seconds"):
        if numeric in values and isinstance(values[numeric], str):
            text = values[numeric].replace(",", "")
            if text.isdigit():
                values[numeric] = int(text)
    if isinstance(values.get("row"), int):
        values["row_hint"] = f" (row {values['row']:,})"
    else:
        values["row_hint"] = ""
    title_key = "title_located" if located and entry.get("title_located") else "title"
    title = str(entry.get(title_key, "")).format_map(values)
    detail_key = (
        "detail_located" if located and entry.get("detail_located") else "detail"
    )
    detail = str(entry.get(detail_key, "")).format_map(values)
    fixes: list[str] = []
    for template, condition in entry.get("fixes", ()):
        if condition and not params.get(condition):
            continue
        rendered = str(template).format_map(values).strip()
        if rendered and rendered not in fixes:
            fixes.append(rendered)
    return shorten(title, 90), detail, tuple(fixes)
