# Troubleshooting and FAQ

The problems people meet most often, with the fix for each, followed by a list of the dialogs you may see and a glossary.

[Back to the guide index](README.md)

## On this page

- [A file is locked or open in Excel](#a-file-is-locked-or-open-in-excel)
- [My numbers are treated as text](#my-numbers-are-treated-as-text)
- [My dates are not recognised](#my-dates-are-not-recognised)
- [The result is empty or has fewer rows than I expect](#the-result-is-empty-or-has-fewer-rows-than-i-expect)
- [A test found nothing in the editor but something after Run](#a-test-found-nothing-in-the-editor-but-something-after-run)
- [A run is slow or stops after 30 seconds](#a-run-is-slow-or-stops-after-30-seconds)
- [Cannot find the file after moving a workflow](#cannot-find-the-file-after-moving-a-workflow)
- [Odd characters, or everything in one column](#odd-characters-or-everything-in-one-column)
- [Excel export is missing or fails](#excel-export-is-missing-or-fails)
- [Run does nothing, or my output file is not there](#run-does-nothing-or-my-output-file-is-not-there)
- [Panels and layout](#panels-and-layout)
- [Dialogs you may see](#dialogs-you-may-see)
- [Quick FAQ](#quick-faq)
- [Glossary](#glossary)

## A file is locked or open in Excel

**What you see:** `TD-IN-002` ("'orders.xlsx' cannot be read: it is open in another program or access is denied") when reading, or `TD-OUT-002` ("cannot be written: it is open in another program or read-only") when writing. A failed **Export Excel...** from the preview shows an **Export failed** dialog.

**Why:** Windows does not let two programs write a file at once, and Excel locks a workbook that it has open. A folder source also sees Excel's temporary `~$name.xlsx` files; those are excluded by default (the default exclude patterns include `~$*`).

**Fix:**

1. Close the file in Excel (or any program that has it open, including a preview pane in File Explorer).
2. Run again. For an output, you can also give the File Output node another file name.
3. If it is read-only, clear the read-only flag or write somewhere else.
4. On a network drive, check that you still have the connection and permission.

## My numbers are treated as text

**What you see:** sums fail with `TD-TYP-003` ("Column 'Amount' is text, so it cannot be ..."), a conversion fails with `TD-TYP-001`, a filter like `[Amount] > 100` gives odd results, or sorting puts "1000" before "200".

**Why:** a CSV has no types. The app reads every CSV column as **text** on purpose, so that nothing is silently changed (a leading zero in an account number such as `00123` stays).

**Fix:**

1. Add a **Select** node after the File Input. In its table, set **Data Type** for the column: `Int64` for whole numbers, `Float64` or `Decimal` for amounts, `Date` or `Datetime` for dates, and keep `String` for identifiers.
2. If some values cannot convert, the error names the first bad row and values (see [Row numbers and values](errors-and-problems.md#row-numbers-values-and-did-you-mean)). Common culprits: a thousands separator or currency sign ("1,250.00", "USD 10"), a comma used as the decimal mark ("12,5"), text such as "n/a", or stray spaces. Clean those first with **Cleansing** or **Find and Replace**.
3. In a **Formula**, `TRY_CAST([col] AS DOUBLE)` turns bad values into empty cells instead of stopping the node.

Parquet, JSON and database inputs keep their own types and do not need this.

## My dates are not recognised

Dates in a CSV arrive as text. In **Select**, change the column to `Date` or `Datetime`, and where the node offers a date format, choose the one that matches the text (for example year-month-day versus day/month/year). Audit nodes that take a date column have their own **Date format** list; the text must match one of the formats. If values do not match, you get `TD-TYP-001` or an audit warning "N values could not be read as dates and were skipped" (`TD-AUDIT-102`).

## The result is empty or has fewer rows than I expect

Work through these in order:

1. **Are you looking at the sample?** While you edit, every node sees only the first **100 rows**. A filter for "Region = West" gives an empty preview if the first 100 rows contain no West. The preview's badge says "evaluated - not run". **Run** the workflow and check again.
2. **Did the preview change after Run?** If the badge says "from Run" and the table is still empty, the result really is empty.
3. **Is it the filter?** Check the case of text, spaces around values, and whether the column is text or a number (a number column does not equal the text "100"). Use **Trim spaces** and **Ignore case** where a node offers them.
4. **Is it a join?** Keys must match exactly. Check the key columns on both sides for type (text versus number), spaces and case. A join on `Customer_Id` (text) and `customer_id` (number) matches nothing. Add a **Select** or **Normalize** on each side so the types agree.
5. **Is a header row being read as data, or the wrong sheet or delimiter?** Check the File Input settings (first row holds field names, delimiter, sheet, start row).
6. **Count at each step.** Select a node and read the counts chip in the Data Preview, then move one node back.
7. **After a Run, open Run History**, select the run, and read the **In** and **Out** columns of the Nodes table: they show rows in and out of every node.

## A test found nothing in the editor but something after Run

This is expected, and it is the most common surprise with Audit nodes. In the editor an Audit node tests only the first 100 rows. Duplicates and gaps are rarely in the first 100 rows. Press **Run**; the test then runs on all rows and the result in the run record and the output tables is the real one. (In the example in the [first-workflow tutorial](README.md#your-first-workflow-in-10-minutes), the editor shows no duplicates and the Run finds 790 groups.)

## A run is slow or stops after 30 seconds

See [Limits and performance](limits-and-performance.md). In short:

- A single step may take at most **30 seconds**. Filter and drop columns early; write big results as Parquet or CSV.
- Excel and JSON inputs are read in full every time a workflow opens: convert them to CSV or Parquet.
- If a Run stops with "ran out of memory", set **Row counts** to **Sinks only** in Preferences, filter earlier, and avoid holding huge intermediate tables.

## Cannot find the file after moving a workflow

**What you see:** `TD-IN-001` ("The file 'orders.csv' was not found"), with a "Looked for:" path, or a File Input with a red mark and "No file selected".

**Why:** a workflow stores each input twice: the full path, and the path relative to the workflow. When it opens, the relative path is tried first, then the full one. If you moved only the `.tds` (not the data), the relative path breaks, and if the data also moved or the drive letter differs, the full path breaks too.

**Fix:**

1. Select the File Input node and click **Browse for file** (the folder icon next to **Source**). Pick the file again. Save the workflow so the new relative path is stored.
2. To move a project, move the workflow **and its data** together, keeping the folder layout.
3. Network drive letters can differ between computers; a UNC path (`\\server\share\...`) is more portable.
4. Do the same for **File Output** nodes: their path is also a full path you may need to update.

Records of earlier runs stay in the old `.runs` folder; move that folder with the workflow if you want the history to follow (see [Run history](run-history-and-audit-trail.md#where-records-are-stored)).

## Odd characters, or everything in one column

| You see | Cause | Fix |
|---|---|---|
| Question marks or strange letters (`CafÃ©`), or `TD-IN-004` "is not UTF-8 text" | The file is in an older encoding (Latin-1 or Windows-1252), typical of old Excel exports. | In File Input set **Encoding** to **UTF-8 (replace bad bytes)**, or re-save the file as "CSV UTF-8" from Excel. |
| One wide column holding everything | Wrong delimiter (for example a semicolon file read as comma). | Set **Delimiter** in File Input (`;`, `\t` for tab, `\|`). |
| `TD-IN-007` "Some rows have more fields than the header" | An unquoted delimiter inside a value, or the wrong delimiter. | Check the delimiter, and that values containing it are wrapped in quotes. |
| Column names have spaces or odd capitals | The source headers. | Add **Normalize** (trim spaces, spaces to underscores, optional case). |
| A leading zero disappeared | It was converted to a number somewhere. | Keep the column as `String` in Select; in Excel, format the column as text before saving. |

## Excel export is missing or fails

- **In the Data Preview**: choose **Options > Export Excel...**. If it fails you get an **Export failed** dialog with the reason. A locked target file is the usual cause (see above).
- **In a File Output node**: choose **Excel** in **Format** and a file name ending in `.xlsx`. If you get `TD-OUT-003` "Excel export is not available in this installation", the Excel writer is missing from the installation: write **CSV** or **Parquet** in the meantime and ask your administrator to reinstall the application.
- **Too big for Excel**: a sheet holds at most **1,048,575** data rows and **16,384** columns (`TD-OUT-013`, `TD-OUT-011`). Write CSV or Parquet, or filter first.
- **Export from the preview writes only what the preview holds** (up to 1,000 rows or 2 MB, and only the rows matching the preview's search box), not the whole result. Use a File Output node and Run to get everything.
- For a formatted workpaper (header block, index sheet), see [workpaper.md](workpaper.md).

## Run does nothing, or my output file is not there

| Check | Fix |
|---|---|
| Is the stop button showing instead of play? | A Run is in progress. Wait, or cancel. |
| Did the Logs say "The workflow has a cycle"? | Remove one connection of the loop (the loop's edges are selected). |
| Is there a **File Output** node, connected, with a path? | Without one, a Run writes nothing. See [Workflows with no output node](running-workflows.md#workflows-with-no-output-node). |
| Did a node fail? | The Problems dock opens by itself after a failed Run; fix the first problem. |
| Is the file where you think? | Open the File Output node and read the path in **File**. Use a full path so there is no doubt where it goes. Check the run record's `outputs`, which lists the exact paths written. |
| Is the run record there? | Run History lists it. "Run log saved: <path>" in the Logs says where it went. |

## Panels and layout

| Problem | Fix |
|---|---|
| The Config Dock, Logs or Preview has disappeared | Open it from the **Window** menu, or **Window > Reset Layout**. |
| The window opens off-screen or too big | **Window > Reset Layout**, or turn off **Restore window and dock layout on startup** in Preferences > Layout. |
| The text is too small | **Edit > Settings > Appearance > Application text**. |
| I want a lighter or darker look | **Edit > Settings > Appearance**, choose a theme. |

## Dialogs you may see

| Title | When | What to do |
|---|---|---|
| **Welcome to Trigger Designer** | At startup (can be switched off) | Open a recent file, **New Project**, or **Browse...**. |
| **Please wait** | While a workflow opens ("Reading...", "Validating workflow...", "Evaluating workflow...") | Wait; large workflows and Excel inputs take longer. |
| **Error loading <file>** | The workflow could not be read | See [Files and formats](files-and-formats.md#opening-files-from-other-versions). |
| **Workflow Validation Warnings** | After opening a file saved by a newer version, or one with unknown nodes, a loop or invalid settings | Read it. Unknown nodes keep their settings; save under another name if unsure. |
| **About to loose your work?** (sic) | Closing a workflow with unsaved changes | **Save**, **Discard** or **Cancel**. |
| **Recent file not found** | A file in **Open Recent** is gone | It is removed from the list. |
| **Set Node Label** | Right-click a node > Set Label... | Type the label; empty removes it. |
| **Export failed** | An Excel export from the preview failed | Close the target file, or choose another name. |
| **Run log verification failed** | After **Verify run log** found a problem | See [the hash chain](run-history-and-audit-trail.md#the-hash-chain-and-tamper-evidence). |
| **Check inputs** | After **Check inputs against selected run** | Read the state of each file. |
| **Export run as JSON / HTML report** | Saving from Run History | Choose a name. |
| **Reset all preferences** | Preferences > General > Reset | Confirm to restore defaults. User themes are kept. |
| **Theme unavailable**, **Import failed**, **Export failed**, **Delete theme**, **Duplicate Theme** | Theme management in Preferences | The message says what to fix. |
| **Preferences** | **Edit > Settings** | See [Preferences](preferences.md). |
| **About** | **Help > About** | Version information. |

## Quick FAQ

**Does Run change my input files?** No. Inputs are only read. Databases are opened read-only.

**Does Run overwrite my outputs?** Yes, a File Output replaces a file of the same name without asking.

**Does editing change my data?** No. The workflow stores settings only. Editing shows you a preview computed from a sample.

**Can I undo a Run?** No: Run writes files and records. Undo covers edits to the workflow. Keep outputs in a folder per version, or use different file names.

**Where is my work saved?** Only when you save (`Ctrl+S`). The title shows an asterisk while there are unsaved changes. The app does not autosave workflows.

**Can I run the same workflow without the window?** Yes, with the command-line runner: see [cli.md](cli.md).

**Is my data sent anywhere?** No. See [Security and privacy](security-and-privacy.md).

**How do I prove what I ran?** Use [Run History](run-history-and-audit-trail.md): verify the chain, export the HTML report, and note the head hash.

**Why did the preview change by itself?** The preview follows your selection and your edits. **Pin** it to freeze it on one node.

**How do I share a result with someone who does not have the app?** Write a CSV, Parquet or Excel file with a File Output node, and send it together with the HTML report of the run.

## Glossary

| Term | Meaning |
|---|---|
| **Audit node** | A node that tests data for something an auditor looks for (duplicates, gaps, Benford conformity, risk filters, samples) and produces a pass/warn/fail summary as well as tables. |
| **Badge** | The small round sign on the bottom edge of a node: normal state, red "!" error, amber "!" warning or changes pending. |
| **Canvas** | The workspace where nodes and connections are drawn. |
| **Chain (hash chain)** | The link from each run record to the one before it, so that edits to the history can be detected. |
| **Config Dock** | The panel (Node Configuration) that shows the settings of the selected node. |
| **Deferred evaluation** | A node's recomputation waits until you leave the node; the amber "!" shows meanwhile. |
| **Edge** | A connection from one node's output to another node's input. |
| **Eager / lazy** | An eager node holds its whole table in memory; a lazy node describes work and lets data stream through. |
| **Fingerprint (hash, SHA-256)** | A code computed from a file's contents. Change one byte and the code changes completely, so it proves a file is the same one. |
| **Group** | A coloured box around nodes that belong together. |
| **Head hash** | The hash of the newest record in the chain; note it elsewhere to detect later removal of the latest records. |
| **Knock-on error** | An error shown on a node only because an earlier node failed. |
| **Label** | A short note floating above a node. |
| **Live evaluation** | The quick recomputation while you edit, on a 100-row sample. |
| **Node** | One step in a workflow. |
| **Output / Input (socket)** | The connection points on the right and left of a node. |
| **Pin** | Freeze the Data Preview on one node. |
| **Plan** | The description of the work a lazy node builds; data is read only when something at the end asks for it. |
| **Problems dock** | The list of nodes that currently have an error or warning. |
| **Record (run record)** | The sealed file that describes one Run. |
| **Run** | Process the whole data with the workflow and write the outputs. |
| **Sample (live sample)** | The first 100 rows used while editing. |
| **Sink** | A node that writes data out (File Output). |
| **Source badge** | The tag on the Data Preview: "from Run" or "evaluated - not run". |
| **Store** | The folder holding one workflow's run records. |
| **Test summary** | The structured result an Audit node adds to the run record. |
| **TD- code** | A stable error code such as `TD-SCH-001`. |
| **`.tds`** | The workflow file. |
| **Workpaper** | A formatted Excel file produced for audit documentation; see [workpaper.md](workpaper.md). |
