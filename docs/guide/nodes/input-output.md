# Input and Output nodes

These two nodes connect your workflow to files. **File Input** reads data in. **File Output** writes the result out. Every workflow starts with at least one File Input.

## Contents

- [Live preview and Run](#live-preview-and-run) (read this first; the other node pages link here)
- [File Input](#file-input)
- [File Output](#file-output)

> Browse and Text-input style nodes: the node list in the code also names a `BROWSER` and a `TEXT_INPUT` entry, but neither has a node behind it. You cannot add them to a workflow, so they are not documented here. Only File Input and File Output exist in this family.

---

## Live preview and Run

This applies to every node in the app, so it is explained once, here.

**While you edit, the app works on a small sample. Run works on everything.**

| | While you edit (live preview) | When you press Run |
|---|---|---|
| Rows each node reads from each input | The first 100 rows | All rows |
| Rows each node shows on each output | At most 100 | All rows are processed; the Data Preview shows up to 1,000 rows (or 2 MB, whichever is smaller) |
| Files are written | Never | Yes (File Output, charts, reports) |

What this means for you:

- **Counts, totals and matches in the live preview describe the sample, not your data.** A Join can show "no matches" in the preview because the matching row is row 101. A Count node shows at most 100. Treat the preview as a way to check that your settings are wired correctly; read the real numbers after a Run.
- **A problem hiding in row 5,000 will not appear until you Run.** An unexpected text value in a number column, a Reconcile that finds too many candidate pairs, or a bad byte deep in a file only show up when the full data is read.
- **Excel, JSON and database inputs are read in full even while editing.** Only what happens downstream of them is limited to 100 rows.
- The Data Preview tells you which one you are looking at. It says "from Run" for the result of the last Run, and "evaluated, not run" for a live preview.
- To Run, press the **Run workflow** button (the play icon at the top-left of the canvas). While a run is in progress the same spot shows a **Cancel run** button; cancelling stops after the current step finishes.

If you need a number you can quote, Run the workflow and read it from the run result, not from the preview.

For how a Run works step by step (and what happens when a step fails), see [Running workflows](../running-workflows.md#live-evaluation-and-the-100-row-sample).

---

## File Input

<img src="../../../src/trigger_designer/resources/qt/images/node_icons/Input/File%20Input.svg" width="56" alt="File Input icon">

### Contents of this section

- [Purpose](#purpose) | [When to use it](#when-to-use-it) | [Inputs and outputs](#inputs-and-outputs)
- [Settings](#settings): [Source](#source) | [Files](#files-folder-and-pattern-sources) | [Columns and rows](#columns-and-rows) | [CSV and text](#csv-and-text-files) | [Excel](#excel-files) | [Parquet](#parquet-files) | [JSON and JSON Lines](#json-and-json-lines-files) | [SQLite and DuckDB](#sqlite-and-duckdb-databases)
- [Worked examples](#worked-examples) | [Edge cases and limits](#edge-cases-and-limits) | [Errors you may see](#errors-you-may-see) | [Tips](#tips)

### Purpose

File Input reads one file, every matching file in a folder, or every file that matches a pattern such as `D:\data\2025-*.csv`, and hands the rows to the next node. It reads CSV, text, Excel, Parquet, JSON, JSON Lines, SQLite and DuckDB files. When it reads several files it stacks them into one table and tells you which files had different columns.

### When to use it

- You start a workflow from a file, a folder of monthly exports, or a database.
- You need to stack many files that share a layout (twelve monthly ledgers, one file per entity) into one table, with a column telling you which file each row came from.
- You need only part of a database: write a read-only `SELECT`.

If you already have a table inside the workflow and want to put two tables together, use [Append, Union or Join](join.md) instead.

### Inputs and outputs

| Socket | Direction | Carries |
|---|---|---|
| (none) | Input | File Input has no input socket. It is a starting point. |
| Output (one socket on the right) | Output | The table read from the source. |

### Settings

The Config Dock shows only the controls that matter for the source you chose. Until there is a path, only the **Source** box is shown.

All edits apply on their own, about a third of a second after you stop typing. There is no Apply button. Each change is one entry in the undo history (for example "Source Path Changed", "Delimiter Changed", "Bad File Mode Changed").

#### Source

| Control | What it does | Default |
|---|---|---|
| **Source** (text box, with two icon buttons) | The file, folder or pattern to read. Type or paste a path, or use the buttons. A path that is a folder reads the folder; a path containing `*`, `?` or `[` reads every match; anything else is a single file. Icon buttons: **Browse for file** and **Browse for folder**. | Empty |
| **Type** | How to read the source: CSV, Text, Excel, Parquet, JSON, JSON Lines, SQLite or DuckDB. Appears once there is a path. | CSV |

Details:

- **The type is detected for you** from the file extension, as long as you have not picked a type yourself: `.csv` and `.tsv` become CSV; `.txt` Text; `.xlsx`, `.xlsm`, `.xls` Excel; `.parquet`, `.pq` Parquet; `.json` JSON; `.ndjson`, `.jsonl` JSON Lines; `.sqlite`, `.sqlite3` SQLite; `.duckdb`, `.ddb` DuckDB. A `.db` file is opened and its first bytes are checked, so it becomes SQLite or DuckDB correctly. Anything else is treated as CSV. Once you choose a type yourself, typing another path no longer changes it; picking a file with the browse button detects the type again.
- **Browse for folder** picks the folder, sets the type to the most common file type found directly in it, and turns on **Output filename as field** (see below).
- **A file that exists wins over pattern characters.** If your real file name contains `[` or `]`, it is read as a file, not as a pattern.
- Very long Windows paths (over about 240 characters) are handled.

##### How the path is saved in the workflow

When you save a workflow, File Input stores the full path and also the path relative to the workflow file's folder. When you open the workflow, the relative path is used if the file is found there; otherwise the full path is used. So a workflow and its data folder can be copied together to another PC or share and still open. The relative form is not stored when the workflow has never been saved, when the data is on a different drive, or when it sits more than six folder levels above the workflow.

#### Files (folder and pattern sources)

The **Files** section only appears when the Source is a folder or a pattern. It is how you control which files are read and how a mismatch is handled.

| Control | Shown for | What it does | Default |
|---|---|---|---|
| **Include** | Folder | Name patterns (separated by `;`) that a file name must match, for example `part_*.csv; sales*.csv`. Empty means "every file of this Type" (see the table below). Case does not matter. | Empty |
| **Exclude** | Folder and pattern | Name patterns to skip, separated by `;`. | `~$*; .*; Thumbs.db; desktop.ini` (Excel lock files, hidden files, Windows clutter) |
| **Include subfolders** | Folder | Also read files in folders below the Source. Shortcuts (symbolic links) to folders are not followed. | Off |
| **Order** | Folder and pattern | The order in which files are stacked: **Name (natural)** or **Modified date**. | Name (natural) |
| **Columns** | Folder and pattern | What to do when files do not have the same columns: **Union by name** or **Must match**. | Union by name |
| **Bad file** | Folder and pattern | What to do with a file that cannot be read: **Stop with error** or **Skip and report**. | Stop with error |
| **Max files** | Folder and pattern | The most files the source may match, 1 to 100,000. A source that matches more stops with `TD-IN-012`; raise the number to read it. | 10,000 |
| **Files read** (table) | Folder and pattern | One row per file (and per sheet): **File**, **Status**, **Columns**. Hover a row for the details. | |

What "Include" means when empty: the files of the chosen type.

| Type | Files read when Include is empty |
|---|---|
| CSV | `*.csv` |
| Text | `*.txt` |
| Excel | `*.xlsx`, `*.xlsm`, `*.xls` |
| Parquet | `*.parquet`, `*.pq` |
| JSON | `*.json` |
| JSON Lines | `*.ndjson`, `*.jsonl` |

`.tsv` files are not in the CSV list. To read a folder of `.tsv` files, set **Include** to `*.tsv` and **Delimiter** to `\t`.

**Patterns.** In a pattern source, `*` matches any characters within one folder level, `?` one character, `[abc]` one of those characters, and `**` crosses folder levels (so `D:\data\**\*.csv` reads all subfolders). Without `**` a pattern only looks as deep as it is written. Matching ignores upper and lower case. Because a pattern already says which files to read, the **Include** box and **Include subfolders** are hidden for pattern sources.

**Natural name order.** Numbers inside names sort as numbers and case is ignored, so `part_2.csv` comes before `part_10.csv` (a plain alphabetical sort would put `part_10` first). Files in subfolders are ordered by their relative path. **Modified date** reads the oldest file first, with ties broken by name. The order matters: with **Union by name**, columns appear in the order they are first seen, and with stacked rows the first file's rows come first.

**Columns: Union by name.** All files are stacked. Where a file lacks a column, the cells are empty (null). A column that only some files have is added after the columns of the first file. When the same column has different types in different files (for example whole numbers in one Parquet file and text in another), numbers with numbers combine to a common number type, and anything else becomes text. The **Files read** table shows "missing N", "+N column(s)" or "types differ" next to files that differ, and the node's tooltip gives a summary such as `3 files, 3 differ (first: part_1.csv: missing Region)`.

**Columns: Must match.** The Run stops with `TD-SCH-011` as soon as any file has a column the others lack or lacks one the others have. The message names the file that introduces the difference and the column. Use this when a different layout means something is wrong and you want to be told.

**Bad file: Skip and report.** A file that cannot be opened or recognised is left out, the **Files read** table shows "skipped: " and the reason, and the node chip shows "N skipped". If every file is skipped you get an error (`TD-IN-014`, "None of the N files ... could be read"). Skipping covers problems found when a file is opened and its header read, and, for CSV, text and JSON Lines files, problems in the **first 2,000 rows** of the body (an invalid byte, a row with too many fields): such a file is skipped and named. A problem deeper in a file is found later, when the rows are actually read, and then still stops the run even with Skip selected. See [Edge cases](#edge-cases-and-limits).

The node holds at most **Max files** files (default 10,000). A source that matches more stops with `TD-IN-012`; raise **Max files** in the Files section.

#### Columns and rows

These controls apply to all file types.

| Control | Shown for | What it does | Default |
|---|---|---|---|
| **Output filename as field** (checkbox) | All | Adds a column that says which file each row came from. | Off for a single file; on automatically when you pick a folder with the folder button |
| **Column name** | When the box above is checked | Name of the added column. | `FileName` |
| **Value** | When the box above is checked | What goes in it: **File name** (`part_1.csv`), **Full path** (`D:\data\jan\part_1.csv`) or **Relative path** (the path from the Source folder, for example `sub/part_5.csv`; for a single file it is the file name). | File name |
| **Read all columns as text** | Every type except CSV and Text | Turns every column into text, including nested values. Useful when you want to keep leading zeros, or compare values exactly as stored. | Off |
| **Row limit** | All | Read only the first N rows. `All` (0) reads everything. For several files or sheets, the limit applies to the combined table, not to each file. | All |

If the file already has a column with the added name, the run stops with `TD-SCH-010` ("already has a column named 'FileName'. Rename the filename column in File Input."). Change **Column name** to something else.

The added columns (filename and sheet name) are placed **after** the data's own columns.

#### CSV and text files

Types **CSV** and **Text** read the same way. These controls appear:

| Control | What it does | Default |
|---|---|---|
| **Delimiter** | The character that separates fields. Type `\t` for a tab. One character only; a longer entry makes the read fail. | `,` |
| **First row holds field names** | On: the first row is the header. Off: there is no header and the columns are named `column_0`, `column_1`, and so on (counted from 0). | On |
| **Encoding** | **UTF-8**, or **UTF-8 (replace bad bytes)**. | UTF-8 |

Important behaviours:

- **Every CSV column arrives as text.** Numbers, dates and amounts are not converted. This is deliberate: it keeps leading zeros (`007`), long account numbers and odd values exactly as they are in the file. Convert columns with a [Select node](preparation.md) when you need numbers or dates.
- **Empty cells become null.** A cell with nothing between the delimiters is an empty (null) value.
- **Blank header cells get a name.** A header cell that is empty is named `column_N`, where N is its position counted from 1 (`column_2` for the second column), so the column is not lost. This differs on purpose from a file with no header row at all, whose columns count from 0 (`column_0` is the first). If that name is taken, a suffix is added.
- **Duplicate header names** are renamed by the reader (for example `Amount_duplicated_0`) and the node reports a note that mentions `TD-SCH-002`. Fix the source file or rename the columns with a Select node.
- **Encoding.** The app reads UTF-8. A file saved as Windows-1252 or Latin-1 (accented letters such as `é` stored as one byte) is not valid UTF-8 and stops with `TD-IN-004`. Choose **UTF-8 (replace bad bytes)** to read it anyway: the unreadable characters are replaced by a placeholder character (`�`), nothing is dropped. Re-saving the file as "CSV UTF-8" in Excel is the clean fix.

#### Excel files

| Control | Shown when | What it does | Default |
|---|---|---|---|
| **Sheets** | Always for Excel | **One sheet**, **All sheets**, or **Chosen sheets**. | One sheet |
| **Sheet** | One sheet | Which sheet. The list comes from the workbook; the first sheet is picked when you choose the file. | First sheet |
| **Chosen** | Chosen sheets | A checklist of the workbook's sheets. At least one must be ticked. | None ticked |
| **Start row** | Always for Excel | The row in the sheet where the table starts (the header row). Use it to skip title lines above the table. | 1 |
| **Add sheet name column** | Always for Excel | Adds a column holding the name of the sheet each row came from. | Off |
| **Column name** | Add sheet name column is on | Name of that column. | `SheetName` |

- Excel columns **keep their types** (numbers are numbers, dates are dates), unlike CSV. Whole-number cells come in as decimal numbers (`10.0`).
- The header is the row at **Start row**; rows above it are skipped. There is no control for reading Excel without a header: the **First row holds field names** box is only shown for CSV and Text.
- With **All sheets** or **Chosen sheets**, every sheet is read with the same Start row and stacked following the **Columns** rule. Sheets with different layouts produce mostly-empty columns, as in the example below. Use **Must match** to be told, or read the odd sheet on its own.
- A folder or pattern of workbooks reads the chosen sheet (or all sheets) of each workbook. The sheet list shown in the dock comes from the first workbook.
- Excel files are read completely, even while you edit. A very large workbook is slow to open for this reason; Parquet or CSV is much faster.
- A workbook that is locked by another program stops with `TD-IN-002`.

#### Parquet files

No type-specific controls. Parquet files carry their own column types, which are kept. Folder and pattern settings, **Output filename as field**, **Read all columns as text** and **Row limit** all work. Parquet is the fastest format to read and the one to prefer for large intermediate files.

#### JSON and JSON Lines files

| Control | What it does | Default |
|---|---|---|
| **Nested values** | How to treat a column that holds a list or a record (for example `"tags": ["x","y"]` or `"addr": {"city": "Oslo"}`). **As text** turns it into a JSON text value. **Keep as is** leaves it as a nested value. | As text |

- **JSON** must be a file containing a list of records (`[{"id": 1, ...}, {...}]`). The whole file is read at once.
- **JSON Lines** (`.ndjson`, `.jsonl`) has one record per line and is read without loading the whole file first.
- Column types come from the data (`1` is a whole number, `10.5` a decimal).

#### SQLite and DuckDB databases

A **database section** appears with the note "Read-only. One SELECT statement. The database is never modified."

| Control | What it does | Default |
|---|---|---|
| **Read** | **Table** or **SQL query**. | Table |
| **Table** (with a **Reload table list** icon button) | The table or view to read. The list is filled from the database and the first one is chosen for you. Click the reload button after the database changes. | First table |
| **Query** | A single `SELECT` statement, for example `SELECT vendor, SUM(amt) AS total FROM payments GROUP BY vendor`. | Empty |

- The database is opened **read-only**. A statement that tries to change data, or use files, is refused. Only one statement is allowed (a second one after a `;` is refused).
- **Row limit** is applied inside the query (as a `LIMIT`).
- A database source takes exactly one file. Giving it a folder or pattern is an error.
- A database that is open for writing in another program cannot be read: you get `TD-IN-002` with the message "the database is open for writing in another program".
- SQLite and DuckDB files are read whole, even while editing.

### Worked examples

**1. One CSV file.** Source `inv.csv`:

```
Invoice,Amount,Date
INV-001,100.50,2025-01-03
INV-002,2000,2025-01-04
INV-003,,2025-01-05
```

Output (note that everything is text, and the empty amount is null):

| Invoice | Amount | Date |
|---|---|---|
| INV-001 | 100.50 | 2025-01-03 |
| INV-002 | 2000 | 2025-01-04 |
| INV-003 | null | 2025-01-05 |

With **Row limit** set to 2 and **Output filename as field** on, you would get only the first two rows plus a `FileName` column holding `inv.csv`.

**2. A folder of monthly files with a changed layout.** Source is a folder containing `part_1.csv`, `part_2.csv`, `part_10.csv`, a leftover `~$part_3.csv` (Excel lock file) and `notes.txt`. `part_10.csv` has an extra `Region` column.

`part_1.csv`: `Invoice,Amount` / `A1,10` / `A2,20`
`part_2.csv`: `Invoice,Amount` / `A3,30`
`part_10.csv`: `Invoice,Amount,Region` / `A4,40,North`

Settings: Type CSV, **Columns** = Union by name, **Output filename as field** on. The lock file and `notes.txt` are ignored. Files are stacked in natural order (1, 2, 10). Output:

| Invoice | Amount | Region | FileName |
|---|---|---|---|
| A1 | 10 | null | part_1.csv |
| A2 | 20 | null | part_1.csv |
| A3 | 30 | null | part_2.csv |
| A4 | 40 | North | part_10.csv |

The **Files read** table shows `part_1.csv` "missing 1", `part_2.csv` "missing 1", `part_10.csv` "+1 column", and the node tooltip reads `3 files, 3 differ (first: part_1.csv: missing Region)`. With **Columns** = Must match, the same folder stops with: `The files have different columns: 'part_10.csv' differs at 'Region'.` (`TD-SCH-011`).

**3. One workbook, two chosen sheets.** `book.xlsx` has sheets `Jan` (Invoice, Amount), `Feb` (Invoice, Amount, Note) and `Notes`. Settings: Type Excel, **Sheets** = Chosen sheets with `Jan` and `Feb` ticked, **Add sheet name column** on. Output:

| Invoice | Amount | Note | SheetName |
|---|---|---|---|
| A1 | 10.0 | null | Jan |
| A2 | 20.0 | null | Jan |
| B1 | 30.0 | late | Feb |

If the real table on a sheet starts below a title (say the headers are in row 3), set **Start row** to 3.

**4. A database query.** Type SQLite, **Read** = SQL query, with `payments` holding (1, Acme, 10.5), (2, Beta, 20.0), (3, Acme, 5.0) and the query `SELECT vendor, SUM(amt) AS total FROM payments GROUP BY vendor ORDER BY vendor`:

| vendor | total |
|---|---|
| Acme | 15.5 |
| Beta | 20.0 |

**5. A JSON file with nested values.** `[{"id":1,"name":"A","tags":["x","y"],"addr":{"city":"Oslo"}}, {"id":2,"name":"B","tags":[],"addr":{"city":"Rome"}}]`, with **Nested values** = As text:

| id | name | tags | addr |
|---|---|---|---|
| 1 | A | ["x","y"] | {"city":"Oslo"} |
| 2 | B | [] | {"city":"Rome"} |

### Edge cases and limits

- **Live preview shows 100 rows; Run reads all rows.** See [Live preview and Run](#live-preview-and-run). CSV, Parquet and JSON Lines are read lazily while you edit, so opening a workflow with big files stays quick.
- **No row cap.** There is no fixed limit on rows or file size. The practical limit is memory: Excel, JSON and database sources are loaded whole. The folder limit is **Max files** (10,000 by default).
- **Empty file.** An empty file (no header and no rows) stops with `TD-IN-005`, or is skipped when **Bad file** is **Skip and report**. A file with a header and no rows is read as a table with no rows.
- **Nulls.** Empty CSV cells and missing columns are null. They are not zeros or empty strings.
- **Types differ across files.** With Union by name: numbers combine, everything else becomes text for that column, and the Files read table marks the files "types differ".
- **Errors deep inside a file body are found late.** With **Skip and report**, the first 2,000 rows of each CSV, text or JSON Lines file are test-read, so a bad byte or an over-long row there skips (and names) that file. An invalid byte or a row with too many fields further down is found only when all rows are read, and it still stops the run. Reading every row of every file just to check them would cost a full extra pass. When it happens with several files, the error names the file when it can find it, otherwise it says "one of the N input files".
- **Files that disappear.** If the source path is missing the node is marked invalid and its tooltip says so ("File '...' does not exist" or the `TD-IN-001` message). The app logs this a few times, then stops repeating itself.
- **Workflow opened later.** When a saved workflow is opened, File Input checks that the file, sheet and columns still match what was saved and warns you about missing or new columns and changed types.
- **Column order.** Columns follow the first file's order; columns found only in later files follow, in the order first seen; Filename and Sheet name columns come last.

### Errors you may see

The node tooltip shows the plain message. When you Run, the error list shows the code, a plain-language explanation and the fix.

| Code | What it means | What to do |
|---|---|---|
| `TD-IN-001` | The file was not found, or the folder/pattern matched no files (`No files in '...' match ...`). | Check the path; check that the drive or network share is reachable; check **Include** and **Exclude**. |
| `TD-IN-002` | The file is open in another program, or access is denied. | Close the file in Excel (or whichever program), or ask for permission to the folder. |
| `TD-IN-003` | The chosen sheet does not exist in the workbook. | Pick one of the available sheets in the node settings. |
| `TD-IN-004` | The file is not UTF-8 text. | Set **Encoding** to **UTF-8 (replace bad bytes)**, or save the file again as "CSV UTF-8". |
| `TD-IN-005` | The file is empty. | Check the export that made it finished, then reload. |
| `TD-IN-006` | The file is not a readable Excel workbook (damaged or not really Excel). | Open it in Excel and save it again as `.xlsx`. If it is really text, rename it `.csv` and set Type to CSV. |
| `TD-IN-007` | Some rows have more fields than the header. | Check the **Delimiter**; make sure values that contain the delimiter are quoted. |
| `TD-IN-010` | The data in a file could not be read; the details name the column when known. | Check the file Type and Delimiter. |
| `TD-IN-011` | The input file could not be opened. | Check the path and your access rights. |
| `TD-IN-012` | The source matches more files than **Max files** (10,000 by default). | Narrow the **Include** pattern or the folder, or raise **Max files**. |
| `TD-IN-013` | The database could not be read as asked (unknown table, not a single `SELECT`, a statement that tries to change data). | Check the table name; use one `SELECT`. |
| `TD-IN-014` | The File Input settings need attention. Examples: `Choose a file, folder or pattern.`, `Choose a table.`, `Write a SELECT query.`, `Choose at least one sheet.`, `Database sources take exactly one file, not a folder or pattern`, or every file was skipped. | Open File Input and fix the named setting. |
| `TD-SCH-010` | The added filename or sheet-name column has the same name as a column already in the data. | Change **Column name**. |
| `TD-SCH-011` | **Columns** is **Must match** and files have different columns. | Use **Union by name**, or fix the odd file the message names. |

### Tips

- Put one File Input per source and give the real work to other nodes. A File Input followed by a [Select node](preparation.md) that sets the types is the standard start.
- For a folder of exports, turn on **Output filename as field**. Later you can see which file a suspicious row came from.
- Keep **Columns** on **Union by name** while you explore, and switch to **Must match** once the process is stable so a changed layout stops the run instead of quietly adding empty columns.
- Check the **Files read** table after pointing at a folder. Make sure the file count is what you expect, and that no file says "skipped".
- Prefer `D:\data\2025-*.csv` over a folder if the folder also holds files you do not want.
- Convert large CSV inputs to Parquet once (File Output, Parquet) and read the Parquet afterwards.

---

## File Output

<img src="../../../src/trigger_designer/resources/qt/images/node_icons/Input/File%20Output.svg" width="56" alt="File Output icon">

### Contents of this section

- [Purpose](#purpose-1) | [When to use it](#when-to-use-it-1) | [Inputs and outputs](#inputs-and-outputs-1) | [Settings](#settings-1)
- [Worked example](#worked-example) | [Edge cases and limits](#edge-cases-and-limits-1) | [Errors you may see](#errors-you-may-see-1) | [Tips](#tips-1)

### Purpose

File Output writes the table it receives to a file on disk. It writes CSV, a custom-delimited text file, Excel, Parquet, JSON, JSON Lines (NDJSON) or Arrow IPC. It does not change the data.

### When to use it

- You want the result of the workflow as a file you can open in Excel or hand to someone.
- You want to save an intermediate result in a fast format (Parquet) to read back with File Input.
- You want to export an exception list from an [audit node](audit.md).

<!-- workpaper: see ../workpaper.md -->

### Inputs and outputs

| Socket | Direction | Carries |
|---|---|---|
| Input (one socket on the left) | Input | The table to write. |
| (none) | Output | File Output has no output socket. It is an end point. |

### Settings

The Config Dock has two sections.

**Destination**

| Control | What it does | Default |
|---|---|---|
| **File** (text box) with a **Browse for save location** icon button | The full path of the file to create, for example `D:\out\exceptions.csv`. The folder must already exist. The browse button opens a Save dialog filtered to the current format. | Empty (placeholder "Enter file path") |

Typing a path changes the **Format** for you when the extension is recognised:

| Extension | Format picked |
|---|---|
| `.csv`, `.txt` | CSV |
| `.xlsx`, `.xls` | Excel |
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

What each format writes:

| Format | What you get |
|---|---|
| **CSV** | A text file with a header row and one line per row. UTF-8. Empty (null) values are written as nothing between the separators. The Delimiter and BOM settings apply. |
| **Custom delimited** | The same as CSV, for any separator (for example `\|` or `;`). Pick the extension yourself (for example `.txt`); typing `.txt` switches the Format to CSV, which writes the same bytes. |
| **Excel** | A new `.xlsx` workbook with one sheet named `Sheet1`. The header row is bold with a light fill, frozen, and has filter buttons. Numbers, dates and times are real Excel numbers and dates, empty values are blank cells, and text is never treated as a formula (a value starting with `=` stays text). Column widths are set from the data. |
| **Parquet** | A compressed, typed binary file (Snappy compression). Fast and compact; keeps column types. |
| **JSON** | One JSON document: a list of records, `[{"Invoice":"A1","Amount":10.5}, ...]`. The whole table is built in memory first. |
| **NDJSON** | JSON Lines: one record per line. |
| **Arrow IPC** | An Arrow file that other data tools read quickly; keeps column types. |

Compression and streaming are not options in the dock: Parquet always uses Snappy, and CSV, Parquet, NDJSON and Arrow IPC are always written in a streaming way (a table bigger than memory can still be written).

### Worked example

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

### Edge cases and limits

- **It only writes on Run.** While you edit, nothing is written and the node produces no output. After you press **Run workflow** the file appears. See [Live preview and Run](#live-preview-and-run).
- **The whole table is written, not the 100-row preview.**
- **An existing file is overwritten without asking** for CSV, Custom delimited, Parquet, JSON, NDJSON and Arrow IPC. Excel is written to a temporary file and then moved into place, so a failed Excel write does not damage an existing workbook.
- **The folder is not created.** If the folder does not exist, the Run stops with `TD-OUT-001`. Create it first.
- **Nothing connected.** With no input the node shows the tooltip "Input is not connected" and the Run stops with `TD-OUT-006`.
- **No path.** The Run stops with the message `File Output: choose an output path`.
- **Excel limits.** An Excel sheet holds at most 1,048,575 data rows and 16,384 columns. A larger table is refused, never cut short (`TD-OUT-013` for rows, `TD-OUT-011` for columns). Write it as CSV or Parquet instead, or select fewer columns first.
- **Table with no columns** cannot be written as Excel.
- **JSON** loads the entire table into memory before writing.
- **Nested values** (lists, records) are not suitable for CSV. Convert them to text first.
- **Dates in Excel** are real Excel dates formatted `yyyy-mm-dd`; whole numbers use `#,##0` and decimals `#,##0.00`. A text cell longer than Excel's 32,767-character limit is shortened.
- **Leading zeros** survive CSV (they are text in the file) but Excel will drop them when *you* open the CSV and Excel guesses it is a number. Write the file as Excel or open the CSV with column type Text.

### Errors you may see

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

### Tips

- Write exception lists as **Excel** for reviewers and as **Parquet** for anything another workflow will read back.
- Give each output a dated name by hand; File Output never adds a date or version to the name.
- If Excel shows strange characters when you open a CSV, switch on **Include BOM**.
- If you open the CSV in Excel and amounts look wrong, check the regional list separator: many European setups expect `;` as the delimiter.
