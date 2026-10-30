# Files and formats

This page covers the workflow file (`.tds`), the data files the app can read and write, and how the app remembers recent files and your last session.

[Back to the guide index](README.md)

## On this page

- [The workflow file (.tds)](#the-workflow-file-tds)
- [What is inside a .tds](#what-is-inside-a-tds)
- [How file paths are stored](#how-file-paths-are-stored)
- [Saving](#saving)
- [Opening files from other versions](#opening-files-from-other-versions)
- [Input file types](#input-file-types)
- [Output file types](#output-file-types)
- [Recent files and session restore](#recent-files-and-session-restore)
- [Other files the app creates](#other-files-the-app-creates)
- [If something goes wrong](#if-something-goes-wrong)

## The workflow file (.tds)

A **workflow** is saved as a `.tds` file ("Trigger Designer Scene"). It holds the nodes, their settings, the connections, the labels and groups, and where the nodes sit on the canvas. It does **not** hold your data.

A `.tds` is plain text in the JSON format, written in **UTF-8**. You can open it in any text editor to see what it contains, but you should edit workflows in the app. Because it is text, it works well with version control, and you can send it by email.

To open one: **File > Open** (`Ctrl+O`, the file filter says "Design (*.tds)"; you can select several files), **File > Open Recent**, the welcome dialog, or start the program with the file as its argument (`trigger-designer "C:\Work\Orders\orders_check.tds"`).

Opening a workflow that is already open just brings its tab forward.

## What is inside a .tds

Top level:

| Key | Meaning |
|---|---|
| `id` | An internal number for the canvas. |
| `scene_width`, `scene_height` | Size of the canvas area. |
| `nodes` | A list of nodes (below). |
| `edges` | The connections: `start` and `end` are socket ids, plus the edge style and `input_index`. |
| `groups` | The coloured group boxes: title, position, size, whether collapsed, the ids of the nodes inside, and colours. |
| `comments` | Canvas comments. |
| `workflow_metadata` | Facts about the file itself (below). |

Each node has:

| Key | Meaning |
|---|---|
| `id`, `title` | Its id and displayed title. |
| `op` | The **stable operation name**, such as `input.file_input` or `audit.duplicates`. This is how the app knows which node it is, and it does not change when nodes are added to the app. |
| `node_code`, `node_type` | The older numeric identification, kept for compatibility. `op` wins when both are present. |
| `pos_x`, `pos_y` | Position on the canvas. |
| `inputs`, `outputs` | The sockets (index, whether several edges are allowed, a type). |
| `content` | **The node's settings.** What it contains depends on the node; for File Input it is the file path, type, delimiter and so on. |
| `label_text`, `label_visible`, `label_offset` | The floating label. |

`workflow_metadata`:

| Key | Meaning |
|---|---|
| `schema_version` | The version of the file layout. This guide describes version **2**. |
| `app_version` | The program version that saved the file (currently `0.1.0`). |
| `saved_at` | When it was saved, in UTC. |
| `workflow_uuid` | An identity for this workflow. It is created the first time you save, stays the same across saves and when you rename the file, and changes if you use **File > New**. The run record stores it, so records can be tied back to a workflow even after a rename. |

Keys that a newer version of the app added to `workflow_metadata` are carried through a load and save, not dropped.

## How file paths are stored

File Input stores each source path twice:

| Key | Content |
|---|---|
| `filePath` | The **absolute** path, such as `C:\Work\Orders\data\orders.csv`. |
| `filePathRel` | The path **relative to the workflow file**, using forward slashes, such as `../data/orders.csv`. It is stored only when the data is not more than six folders up from the workflow, and not on a different drive. |

When a workflow opens, the app uses the relative path **first**, if the file exists there, and falls back to the absolute path. So a project folder (workflow plus its data) can be zipped, copied to another drive, or sent to a colleague, and still opens correctly as long as the relative layout is kept. If you move only the `.tds`, the relative path no longer points at the data, and the absolute path is used instead, which is why the original data still loads when you move a workflow on the same computer.

Relative paths are written when you **save**. A workflow that has never been saved has no folder to be relative to.

The File Output node stores a path in its settings as you type it. Use a full path (or a path you checked) to be sure where the file goes.

## Saving

- **File > Save** (`Ctrl+S`) saves to the current file. **File > Save As...** (`Ctrl+Shift+S`) asks for a new name. A new, never-saved workflow asks for a name the first time.
- The title shows an asterisk while the workflow has unsaved changes. Closing it asks whether to **Save**, **Discard** or **Cancel**.
- Saving first picks up any text you were typing and any pending edit.
- **Saves are atomic.** The app writes the new content to a temporary file in the same folder (named like `.tds-xxxx.tmp`), forces it to disk, and only then replaces your file. If something goes wrong halfway (a full disk, a crash, a power cut), your previous workflow is still there untouched. Stray `.tds-*.tmp` files can be deleted.
- Files are written as UTF-8.

Saving a workflow is independent of running it. A Run does not save the workflow; the run record states whether the workflow had unsaved changes (`workflow_modified_since_save`).

## Opening files from other versions

| Situation | What happens |
|---|---|
| **Same version** | Opens normally. A progress dialog ("Please wait") shows "Reading...", "Validating workflow..." and "Evaluating workflow..." for larger files. |
| **Saved by an older version** (file layout version 1, or a file without `workflow_metadata`) | Opens. Old numeric node codes are converted to the stable `op` names, older File Input settings are brought up to date, and edges that point at sockets that no longer exist are removed with a line in the Logs ("Removed invalid edge during workflow load"). The next save writes the current layout. |
| **Saved by a newer version** (`schema_version` higher than this program's) | Opens, and a **Workflow Validation Warnings** dialog says: "This workflow was saved by a newer version of the app (file format N, this app understands 2). Some settings may be ignored; saving will overwrite them." Do not save it from this version unless you accept losing what this version does not understand. Use **Save As** to keep the original. |
| **Contains a node this version does not have** | The node loads as a placeholder titled **Unknown**, its settings are kept in the file, and the dialog lists "Unknown node type 'x' ... Its settings were kept; install the providing node or replace it." The rest of the workflow works. |
| **A node's saved settings look wrong** | Each node can check its own loaded state; problems are listed in the same warnings dialog (and in the Logs), by node. |
| **Contains a loop** | Opens, the loop is reported, and the workflow cannot Run until you break the loop. |
| **Not valid JSON** | A dialog titled "Error loading <file>" says the file is not a valid JSON file. Text in the legacy local code page is also accepted: the app tries UTF-8 first, then your computer's code page, and logs that it did so. |
| **File not found** | A dialog "Error loading <file>". |

If a file is partially damaged, the app loads what it can and logs the problem rather than refusing the whole file. Always glance at the Logs after opening a workflow that came from outside.

To see which version wrote a file, open it in a text editor and look at `workflow_metadata` near the end.

**Opening a workflow you did not write:** see [Security and privacy](security-and-privacy.md#opening-a-workflow-you-did-not-create).

## Input file types

Set the type in the **File Input** node (the **Type** list). The app guesses it from the file's extension when you choose a file.

| Type | Extensions | Notes |
|---|---|---|
| CSV | `.csv`, `.tsv` | Delimiter and header row are settings. Everything is first read as **text**; you set number and date types with a Select node (see [Troubleshooting](troubleshooting-and-faq.md#my-numbers-are-treated-as-text)). |
| Text | `.txt` | Read like CSV with the delimiter you choose. |
| Excel | `.xlsx`, `.xlsm`, `.xls` | One sheet, several sheets or all sheets; start row. Excel files are read in full. |
| Parquet | `.parquet`, `.pq` | Keeps column types. Fast and compact. |
| JSON | `.json` | An array of records. Nested values can be kept as text. |
| JSON Lines | `.ndjson`, `.jsonl` | One record per line. |
| SQLite | `.sqlite`, `.sqlite3`, `.db` | Read-only: a table, or one SELECT query. |
| DuckDB | `.duckdb`, `.ddb`, `.db` | Read-only, same as above. A `.db` file is recognised as SQLite or DuckDB by its first bytes. |

The **Source** can also be a **folder** or a **pattern** such as `D:\data\*.csv`: all matching files are read and combined, with controls for include and exclude patterns, subfolders, order, what to do when files have different columns, and what to do when one file cannot be read. By default at most 10,000 files are read from one source.

Encoding: **UTF-8**, or **UTF-8 (replace bad bytes)** for files that are not valid UTF-8, such as many Latin-1 exports.

Databases are always opened read-only.

Each File Input node has its own page in the [node reference](nodes/README.md).

## Output file types

Set the format in the **File Output** node (the **Format** list). The app suggests the format from the file name's extension.

| Format | Typical extension | Notes |
|---|---|---|
| CSV | `.csv` | Optional byte-order mark for Excel; delimiter. |
| Excel | `.xlsx` | The whole table is written; limits of Excel apply (1,048,575 data rows and 16,384 columns per sheet). |
| Parquet | `.parquet` | Written without loading everything into memory. |
| JSON | `.json` | An array of records; loaded fully before writing. |
| NDJSON | `.ndjson` | One record per line. |
| Arrow IPC | `.ipc`, `.arrow` | A fast binary format for other tools. |
| Custom delimited | any | Your own delimiter. |

Workpaper export (a formatted Excel workpaper with an index and a header block) is described in [workpaper.md](workpaper.md).

An output file is written when you **Run**, never while you edit. Writing replaces an existing file of the same name **without asking**, so give each output its own name. If the file is open in Excel, the write fails with a message that says so ([TD-OUT-002](errors-and-problems.md#error-code-reference)).

## Recent files and session restore

- **File > Open Recent** lists the files you opened or saved most recently, newest first, numbered `&1` to `&9` for keyboard selection. It holds **10** by default (**Edit > Settings > General > Recent files**, from 1 to 50) and ends with **Clear Recent Files**.
- If you pick a file that is gone, a dialog "Recent file not found" says so and removes it from the list.
- The **welcome dialog** at startup lists the recent files with **New Project**, **Browse...** and **Open**. Untick **Show this dialog on startup** to stop it (also in **Edit > Settings > General**).
- **Layout.** The app remembers window size, position and the arrangement of the panels, and restores them at startup (**Edit > Settings > Layout > Restore window and dock layout on startup**, on by default).
- **Session restore.** The list of workflows that were open when you closed the app is always saved, but it is reopened at startup only if you tick **Reopen files from the last session** (**Layout** page, off by default). It does not happen when you start the program with a file name on the command line.

## Other files the app creates

| What | Where |
|---|---|
| Preferences (`preferences.ini`) and your own themes | `%APPDATA%\Trigger Designer\` |
| The run script of the last Run | `%APPDATA%\Trigger Designer\last_run\check_output.py` |
| Run records | `<workflow name>.runs\` next to each workflow (see [Run history](run-history-and-audit-trail.md#where-records-are-stored)) |
| Session log files | `%APPDATA%\Trigger Designer\logs\` for the installed app; a `logs` folder beside the source when run from source |

The environment variable `TRIGGER_DESIGNER_DATA_DIR` moves the `%APPDATA%\Trigger Designer` folder, for portable installations. **Edit > Settings > General > Open Preferences Folder** opens it.

## If something goes wrong

| Symptom | What to do |
|---|---|
| "Error loading ..." dialog | The file is missing or is not a `.tds`. Open it in a text editor: a workflow starts with `{` and contains `"nodes"`. |
| A node says the file was not found after moving a workflow | See [Troubleshooting](troubleshooting-and-faq.md#cannot-find-the-file-after-moving-a-workflow). |
| The Logs say "File ... is not UTF-8; decoded as ..." | The workflow was saved by an old tool in your local code page. Save it again from this version and it becomes UTF-8. |
| "Workflow Validation Warnings" lists unknown node types | Use a program version that has those nodes, or replace the placeholders. |
| Stray `.tds-xxxx.tmp` file next to the workflow | A save was interrupted. Your workflow is intact; delete the temp file. |
| Save appears to do nothing | The title still shows the asterisk. Check that the folder is writable and the disk is not full, then use **Save As** to another location. Details are in the Logs. |
