# File Output

![File Output icon](../../assets/node_icons/Input/File%20Output.svg){ .node-icon }

## Purpose

File Output writes the table it receives to a file on disk. It writes CSV, a custom-delimited text file, Excel, Parquet, JSON, JSON Lines (NDJSON) or Arrow IPC. It does not change the data.

## When to use it

- You want the result of the workflow as a file you can open in Excel or hand to someone.
- You want to save an intermediate result in a fast format (Parquet) to read back with File Input.
- You want to export an exception list from an [audit node](../audit/index.md).

For an audit **workpaper** (Summary, exception list with tick marks, run log, workflow and file fingerprints in one Excel file), use [Workpaper Output](workpaper-output.md) instead; see [Workpapers](../../guide/workpaper.md).

## Inputs and outputs

| Socket | Direction | Carries |
|---|---|---|
| Input (one socket on the left) | Input | The table to write. |
| (none) | Output | File Output has no output socket. It is an end point. |

## Settings

The Config Dock has two sections.

**Destination**

| Control | What it does | Default |
|---|---|---|
| **File** (text box) with a **Browse for save location** icon button | The full path of the file to create, for example `D:\out\exceptions.csv`. The folder must already exist. The browse button opens a Save dialog filtered to the current format (for Excel the filter is `*.xlsx` only). | Empty (placeholder "Enter file path") |

Typing a path changes the **Format** for you when the extension is recognised:

| Extension | Format picked |
|---|---|
| `.csv`, `.txt` | CSV |
| `.xlsx`, `.xls` | Excel (a typed `.xls` is changed to `.xlsx`, see below) |
| `.parquet` | Parquet |
| `.json` | JSON |
| `.ndjson` | NDJSON |
| `.ipc`, `.arrow` | Arrow IPC |

Other extensions (for example `.jsonl` or `.tsv`) leave the format unchanged. The write is always based on the **Format** setting, not on the extension, so a file called `report.xlsx` with Format CSV would contain CSV text.

**Format**

| Control | Shown for | What it does | Default |
|---|---|---|---|
| **Format** | Always | One of CSV, Excel, Parquet, JSON, NDJSON, Arrow IPC, Custom delimited. | CSV |
| **Delimiter** | CSV and Custom delimited | The separator between values; a single character. A blank box means a comma. | `,` |
| **Encoding: Include BOM** | CSV and Custom delimited | Writes a byte-order mark at the start of the file so that Excel recognises UTF-8 text. | Off |
| **Compression** | Parquet only | The Parquet compression: Snappy, Zstandard, Gzip, LZ4 or None. The control is hidden for every other format. | Snappy |

What each format writes:

| Format | What you get |
|---|---|
| **CSV** | A text file with a header row and one line per row. UTF-8. Empty (null) values are written as nothing between the separators. The Delimiter and BOM settings apply. |
| **Custom delimited** | The same as CSV, for any separator (for example `\|` or `;`). Pick the extension yourself (for example `.txt`); typing `.txt` switches the Format to CSV, which writes the same bytes. |
| **Excel** | A new `.xlsx` workbook with one sheet named `Sheet1`. The header row is bold with a light fill, frozen, and has filter buttons. Numbers, dates and times are real Excel numbers and dates, empty values are blank cells, and text is never treated as a formula (a value starting with `=` stays text). Column widths are set from the data. |
| **Parquet** | A compressed, typed binary file. Fast and compact; keeps column types. Compressed with Snappy unless you pick another **Compression** (Zstandard, Gzip, LZ4, or None for no compression). Snappy is the default; choose another only if the program that reads the file asks for it. |
| **JSON** | One JSON document: a list of records, `[{"Invoice":"A1","Amount":10.5}, ...]`. The whole table is built in memory first. |
| **NDJSON** | JSON Lines: one record per line. |
| **Arrow IPC** | An Arrow file that other data tools read quickly; keeps column types. |

**Excel is `.xlsx` only.** The writer cannot produce the old `.xls` format. When you type a path that ends in `.xls` and leave the field, the dock changes it to `.xlsx` and shows the new name; the Save dialog only offers `*.xlsx`. An old workflow file that still holds an `.xls` name for Excel output does not write a wrong file: the Run stops before anything is written, asking for a name that ends in `.xlsx` (see `TD-OUT-015` below).

**Streaming is not an option.** CSV, Parquet, NDJSON and Arrow IPC are always written in a streaming way (a table bigger than memory can still be written), so there is no switch for it. Workflow files saved by an earlier version that carry a streaming setting still open; the setting is ignored. A file that stored no compression (or an empty one) is read as Snappy. An unknown compression name in a hand-edited file stops the Run with a message that lists the valid choices.

## Worked example

The table arriving at File Output:

| Invoice | Amount |
|---|---|
| A1 | 10.5 |
| A2 | null |

With **Format** CSV the file contains:

```
Invoice,Amount
A1,10.5
A2,
```

With **Delimiter** `;` and **Include BOM** on, the same data is written as `Invoice;Amount`, `A1;10.5`, `A2;` preceded by the UTF-8 byte-order mark. With **JSON** it is `[{"Invoice":"A1","Amount":10.5},{"Invoice":"A2","Amount":null}]`, and with **NDJSON** it is two lines, one record each.

## Edge cases and limits

- **It only writes on Run.** While you edit, nothing is written and the node produces no output. After you press **Run workflow** the file appears. See [Live preview and Run](index.md#live-preview-and-run).
- **The whole table is written, not the 100-row preview.**
- **An existing file is overwritten without asking** for CSV, Custom delimited, Parquet, JSON, NDJSON and Arrow IPC. Excel is written to a temporary file and then moved into place, so a failed Excel write does not damage an existing workbook.
- **The folder is not created.** If the folder does not exist, the Run stops with `TD-OUT-001`. Create it first.
- **Nothing connected.** With no input the node shows the tooltip "Input is not connected" and the Run stops with `TD-OUT-006`.
- **No path.** The Run stops with the message `File Output: choose an output path`.
- **Excel is `.xlsx` only.** A file name ending in `.xls` is refused (`TD-OUT-015`) with Excel selected; rename it to `.xlsx`.
- **Excel limits.** An Excel sheet holds at most 1,048,575 data rows and 16,384 columns. A larger table is refused, never cut short (`TD-OUT-013` for rows, `TD-OUT-011` for columns). Write it as CSV or Parquet instead, or select fewer columns first.
- **Table with no columns** cannot be written as Excel.
- **JSON** loads the entire table into memory before writing.
- **Nested values** (lists, records) are not suitable for CSV. Convert them to text first.
- **Dates in Excel** are real Excel dates formatted `yyyy-mm-dd`; whole numbers use `#,##0` and decimals `#,##0.00`. A text cell longer than Excel's 32,767-character limit is shortened.
- **Leading zeros** survive CSV (they are text in the file) but Excel will drop them when *you* open the CSV and Excel guesses it is a number. Write the file as Excel or open the CSV with column type Text.

## Errors you may see

| Code | What it means | What to do |
|---|---|---|
| `TD-OUT-001` | The output folder does not exist. | Create the folder, or choose an existing one. |
| `TD-OUT-002` | The file cannot be written: it is open in Excel or another program, or it is read-only. | Close the file, choose a different name, or clear the read-only flag. |
| `TD-OUT-003` | Excel export is not available in this installation (the Excel writer component is missing). | Export as CSV or Parquet instead, or reinstall the application. |
| `TD-OUT-004` | The path is not a valid file name (unsupported characters, or a folder was given). | Remove characters such as `< > : " \| ? *`, keep the path short, and choose a file, not a folder. |
| `TD-OUT-005` | The disk is full. | Free space or write to another drive. |
| `TD-OUT-006` | Nothing is connected to this output. | Connect the node whose result you want to save. |
| `TD-OUT-011` | The table has more than 16,384 columns, the Excel maximum. | Select fewer columns before writing. |
| `TD-OUT-013` | The table has more than 1,048,575 data rows, which an Excel sheet cannot hold. | Save as CSV or Parquet instead. |
| `TD-OUT-014` | Excel could not create the workbook (for example, unusable cell content). | Shorten or fix the offending text and try again. |
| `TD-OUT-015` | Excel output was given a file name ending in `.xls`. The writer only creates `.xlsx` files. | Change the name to end in `.xlsx`. |

## Tips

- Write exception lists as **Excel** for reviewers and as **Parquet** for anything another workflow will read back.
- Give each output a dated name by hand; File Output never adds a date or version to the name.
- If Excel shows strange characters when you open a CSV, switch on **Include BOM**.
- If you open the CSV in Excel and amounts look wrong, check the regional list separator: many European setups expect `;` as the delimiter.


Back to the [Input and Output node index](index.md).
