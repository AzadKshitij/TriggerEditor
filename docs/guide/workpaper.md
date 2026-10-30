# Workpapers (Excel)

A **workpaper** is the Excel file you file with your audit working papers: what you tested, on which data, how, what you found, and enough evidence for someone else to repeat it. Trigger Designer writes one for you, formatted, with the numbers tied together by formulas and with the evidence (file fingerprints, the steps that ran) already filled in. You add your conclusion and your tick marks.

## On this page

- [What a workpaper is, and why](#what-a-workpaper-is-and-why)
- [Two ways to produce one](#two-ways-to-produce-one)
- [The Workpaper Output node](#the-workpaper-output-node)
- [The Config Dock, setting by setting](#the-config-dock-setting-by-setting)
- [Engagement defaults in Preferences](#engagement-defaults-in-preferences)
- [File > Export Workpaper...](#file--export-workpaper)
- [What each sheet contains](#what-each-sheet-contains)
- [File names, versions and replacing](#file-names-versions-and-replacing)
- [Safe by construction: formulas in your data](#safe-by-construction-formulas-in-your-data)
- [Excel's limits and what happens at them](#excels-limits-and-what-happens-at-them)
- [How a workpaper ties to the audit trail](#how-a-workpaper-ties-to-the-audit-trail)
- [Worked example](#worked-example)
- [From the command line](#from-the-command-line)
- [Errors you may see](#errors-you-may-see)
- [Tips](#tips)

---

## What a workpaper is, and why

A workpaper is **reperformable evidence**. A reviewer who opens it should be able to answer, without asking you:

| Question | Where the workpaper answers it |
|---|---|
| Who prepared it, for whom, for which period? | **Summary** (Engagement block, logo) |
| What was the test and what rule was applied? | **Summary** (Objective, Procedure, Criteria) |
| How many items were tested and how many failed? | **Summary** (Results, with formulas tied to the Exceptions sheet) |
| Which items failed? | **Exceptions** (one row each, with space for a tick mark and a comment) |
| Which data was used? Is it the same file I have? | **Summary** (Source files with SHA-256 fingerprints) and **Run log** |
| What steps turned the raw file into the exceptions? | **Workflow** (every step and its settings) |
| What was the result of the review? | **Summary** (Conclusion and Auditor notes: yellow cells you fill in) |

The four sheets are **Summary**, **Exceptions**, **Run log** and **Workflow**. The workpaper is a normal `.xlsx` file: you can annotate it, print it (the sheets are set to landscape, one page wide, with a footer) and attach it to your engagement file. It does not need Trigger Designer to be read.

The fingerprints are SHA-256 values: a short code that changes if even one byte of a file changes. If your copy of an input file has the same SHA-256 as the one in the workpaper, it is the same file.

---

## Two ways to produce one

| | Workpaper Output node | **File > Export Workpaper...** |
|---|---|---|
| Covers | **One test**: the exceptions of one audit node | **The whole last run**: every audit test of it |
| When it is written | During **Run**, as the node's step | When you choose the menu entry, from the last recorded run |
| Sheets | Summary, Exceptions, Run log, Workflow | Summary (one row per audit test), Run log, Workflow. **No Exceptions sheet.** |
| The Run log is | A snapshot taken while the run is in flight | The completed run |
| Needs | Nothing special (the Run log needs run recording on) | A recorded run (**Record every run** on in Preferences) |
| Use it for | The workpaper of one test, with the exception list to tick | A one-page overview of everything the run did |

Use the node for each test you will file separately. Use the menu entry for a cover sheet of the whole run.

---

## The Workpaper Output node

<img src="../../src/trigger_designer/resources/qt/images/node_icons/Input/File%20Output.svg" width="56" alt="Workpaper Output icon (shared with File Output)">

Find **Workpaper Output** on the **Input** tab of the node palette, next to File Input and File Output. It is an end point: it has three inputs and no output.

| Socket | Letter | Carries | Required |
|---|---|---|---|
| Input 1 | **E** | **Exceptions**: the rows to list (for example the Duplicates output of a **Duplicates** node) | Yes |
| Input 2 | **P** | **Population**: everything that was tested (for example the File Input), used to count the population and its value | No |
| Input 3 | **S** | **Summary**: the one-row result of an audit node, so the test name, rule and counts are copied and reconciled | No |

With nothing on **E** the node is red, its tooltip says "Connect the Exceptions input" and the Config Dock shows the same words. If **P** or **S** is connected but has failed upstream, the node is red too ("Population input has no data" / "Summary input has no data"): it does not silently ignore a broken input.

**Nothing is written while you edit.** The workbook is written by **Run workflow**, as a step of the run. In the live preview the node produces nothing.

If the **Amount column** you chose is not in the Exceptions input, the node's tooltip says "The amount column 'x' is not in the Exceptions input".

---

## The Config Dock, setting by setting

Select the node to open its Config Dock. The header shows three chips (`xlsx`, the row limit such as `100,000 row limit`, and the "If it exists" choice in lower case) and the file name. The dock has six sections, in this order. Edits take effect on the next Run; every change is one undo step named "Workpaper *Setting* Changed".

### File

| Control | Default | What it does |
|---|---|---|
| **File** (text box, with a **Browse for save location** icon button) | empty (placeholder "Enter file path (.xlsx)") | The workbook to write. Must end in `.xlsx`, and the folder must exist. The browse button opens a Save dialog ("Save workpaper", filter "Excel workbook (*.xlsx)"), adds `.xlsx` if you leave it off, starts in the folder of the last workpaper, and remembers the folder you choose. |
| **If it exists** | **New version** | What to do when the file is already there. **New version** keeps the old file and writes `name (2).xlsx` (then `(3)`...). **Replace** overwrites. **Stop with error** refuses (`TD-OUT-010`). Hover text: "New version keeps a workpaper you already annotated". |

### Engagement (open by default; can be collapsed)

These fill the header of the Summary sheet. **A box you leave empty uses the matching [Preferences](#engagement-defaults-in-preferences) value**, which is shown in grey inside the box as its placeholder.

| Control | Default | What it does |
|---|---|---|
| **Reference** | empty (placeholder "e.g. C.3.1") | Your workpaper reference. Shown as "Workpaper reference". Empty cells stay yellow for you to complete. |
| **Client** | empty, then Preferences > Client | The client. Also stored as the file's *Company* property. |
| **Engagement** | empty, then Preferences > Engagement | The engagement name. |
| **Period** | empty, then Preferences > Period | The period covered, as free text. |
| **Prepared by** | empty, then Preferences > Prepared by, then your Windows user name | The preparer. Also stored as the file's *Author* property. |
| **Prepared on** | empty (placeholder "today (YYYY-MM-DD)") | The preparation date. Empty means the day of the Run. Anything that is not a valid `YYYY-MM-DD` date stops the run with `TD-OUT-012`. |
| **Logo** (with a **Browse for logo image** icon button) | empty (placeholder "PNG or JPG"), then Preferences > Logo | An image shown at the top right of the Summary. PNG or JPG only. It is scaled to at most 200 by 36 pixels. A logo that cannot be read does not stop the workpaper; a line in *Notes and limitations* says "Logo not added: ...". |

### Test

| Control | Default | What it does |
|---|---|---|
| **Test name** | empty | The title of the workpaper (first line of the Summary) and "Test performed". If empty, the name from the **S** input is used for "Test performed", and the title says "Audit workpaper". |
| **Objective** | empty | What the test is meant to show. Several lines allowed. An empty Objective leaves a yellow cell on the Summary for you to type in. |
| **Procedure** | empty | What you did. Same behaviour as Objective. |
| **Criteria** | empty | The rule applied. If empty, the **S** input's rule is used; if there is none, the cell says "Not provided - complete manually". |

### Values

| Control | Default | What it does |
|---|---|---|
| **Amount column** | none (blank allowed) | The column of the **E** input to total. It drives the *Value* column of the Results block and the formatting of that column on the Exceptions sheet. Pick a number column, or a text column that holds amounts (see [Amounts](#amounts)). Hover text: "Column summed for the value statistics". |
| **Decimals** | 2 | Decimal places (0 to 6) used to show values on the Summary and in the amount column. |

### Sheets

| Control | Default | What it does |
|---|---|---|
| **Row limit** | 100,000 | The most exception rows listed in the workbook (1 to 1,048,574). More than that is not cut silently: see [Excel's limits](#excels-limits-and-what-happens-at-them). Hint under the box: "Large workpapers can take minutes; this step may run up to 10 minutes." |
| **Exceptions sheet** | `Exceptions` | The name of the listing sheet. Illegal characters (`[ ] : * ? / \`) become spaces, it is cut to 31 characters, and it cannot be `Summary`, `Run log`, `Workflow` or `Tests` (a number is added, for example `Summary (2)`). |
| **Include run log** | On | Adds the **Run log** sheet. |
| **Include workflow** | On | Adds the **Workflow** sheet. |

### Sources (collapsed by default)

| Control | Default | What it does |
|---|---|---|
| **Extra source files** | empty (placeholder "One path per line") | Files that were read outside the workflow (for example a policy document or a manual extract). Each is listed on the Summary with its size, date and SHA-256, computed when the workpaper is written. Hover text: "Files read outside the workflow; they are hashed when the workpaper is written". |

The files read by the workflow itself (every File Input upstream of the node) are listed automatically.

---

## Engagement defaults in Preferences

Open **Edit > Settings**, page **General**, section **Engagement**. Fill in once, and every Workpaper Output node and the export dialog start from these:

| Field | Placeholder | Stored as |
|---|---|---|
| **Client** | Client name | `engagement/client_name` |
| **Engagement** | Engagement or audit name | `engagement/engagement_name` |
| **Period** | Period covered | `engagement/period` |
| **Prepared by** | Defaults to your Windows user name | `engagement/preparer` |
| **Logo** (with a **Browse** button) | PNG or JPG shown on the Summary | `engagement/logo_path` |

Each box is saved when you leave it. A value typed in the node always wins over the Preferences value. The folder last used for a workpaper is remembered as `export/workpaper_dir`. See [Preferences](preferences.md#engagement).

A node picks up the Preferences values **when you press Run**, so a change in Preferences takes effect for the next Run without touching the node.

---

## File > Export Workpaper...

Choose **File > Export Workpaper...** (available while a workflow window is open). It writes a workpaper of the **most recent recorded run** of the workflow in front.

1. If the workflow has no recorded run, a message says "There is no recorded run for this workflow yet. Run the workflow first (and keep run recording on in Preferences), then export the workpaper." Nothing is written.
2. Otherwise the **Export workpaper** dialog asks for:
   - **File** (with a **Browse for save location** button). The suggestion is `<workflow name> workpaper.xlsx` in the last workpaper folder, or the workflow's own folder.
   - **If it exists**: New version (default), Replace or Stop with error, as above.
   - **Engagement**: **Reference**, **Client**, **Engagement**, **Period**, **Prepared by** (empty boxes use the Preferences values shown in grey).
   - **Test**: **Objective** and **Procedure**.
   - **Export** and **Cancel** buttons.
3. On success a message gives the path. The logo comes from Preferences. The export never touches the run history: the sealed records are only read.

The workbook has **Summary**, **Run log** and **Workflow**. Its Summary has a **Test results** table with one row per audit test of the run:

| Column | Meaning |
|---|---|
| **Test** | The test's name |
| **Status** | `pass`, `warn`, `fail` or `error` (a failing status is shown in red) |
| **Population rows** | Rows tested |
| **Exceptions** | Rows flagged |
| **Exception rate** | Exceptions divided by population |
| **Result** | The rule and the outcome sentence of the test |

If the run had no audit test, the table says "No audit tests were recorded in this run." In this layout the *Test performed* row reads "Whole run: N tests" (counted from the run record; "Whole run: no audit tests recorded" when there are none) unless you typed a test name, and there are no tick marks (there is no exception list to tick).

---

## What each sheet contains

### Summary

The first sheet, protected so the evidence cannot be changed by accident (no password: **Review > Unprotect Sheet** removes it). Only the **yellow cells** can be edited. Top to bottom:

| Block | What is in it |
|---|---|
| **Title and logo** | The test name (or "Audit workpaper"), then "Audit workpaper generated by Trigger Designer *version* on *date time*". The logo sits at the top right. |
| **Engagement** | Workpaper reference, Client, Engagement, Period, Test performed, Prepared by, Prepared on, **Reviewed by** and **Review date** (always yellow, for the reviewer). |
| **Objective and procedure** | Objective, Procedure performed, Criteria applied. |
| **Results** | The table described below. |
| **Conclusion** | A drop-down: *No exceptions*, *Exceptions - explained* or *Exceptions - require follow-up*, and **Auditor notes** (free text). |
| **Tick marks** | The legend with a live count of how many rows you marked with each tick (see below). |
| **Source files** | One row per input file (see below). |
| **Notes and limitations** | Everything the writer changed or could not do, in plain sentences. "None." if nothing. |
| **Workbook contents** | The sheets of the workbook, and why a sheet was left out. |

**Results** columns: **Measure**, **Rows**, **Value**, **% of population rows**, **% of population value**, **Basis**. Its rows:

| Row | Rows / Value | Basis column says |
|---|---|---|
| **Population tested** | Counted from the **P** input; if there is none, taken from the **S** input; if neither, a yellow cell for you ("Not provided - enter manually"). Value is the total of the amount column on **P**, or "n/a" when no Amount column is set. | "Counted from the Population input" / "Reported by the test node" / "Not provided - enter manually" |
| **Exceptions found** | Rows and value of the exceptions, as formulas (`=B24`) so they follow what the sheet lists. If the list is truncated, the true totals are written as numbers. The two percentages are exceptions divided by population (`n/a` when there is no population). | "No exceptions noted" or "Counted from the Exceptions input" |
| **Exceptions listed in this workbook** | `=COUNT(...)` and `=SUM(...)` over the Exceptions sheet. | "All exceptions are listed", or **"TRUNCATED: first N of M listed"** in red |
| **Full exception list (CSV)** | Name, row count and SHA-256 of the CSV file, or "Not needed - all exceptions are listed in this workbook". | |
| **Reconciliation to test result** | Compares the exceptions received with the count the audit node reported on **S**: "Agrees to the test node (6 exceptions)", or in red "DIFFERENCE: the test node reported X exceptions but Y were received". With no **S**: "No test result supplied". | |

Every figure has a **cached value** as well as the formula, so previewers that do not recalculate (a phone, a mail preview) still show numbers.

**Tick marks** are fixed: **✓** Agreed to source document, **X** Exception confirmed, **E** Explained - see comment, **F** Follow-up required, **N/A** Not applicable. You choose them from a drop-down in the Exceptions sheet; the Summary counts them with `COUNTIF`.

**Source files** columns: **File**, **Sheet**, **Rows read**, **Size (bytes)**, **Modified (UTC)**, **SHA-256**. The list is the input files recorded by the run (their fingerprints are taken *before* the file is read), then your *Extra source files*, de-duplicated. A file that has since been moved keeps its row, and the SHA-256 cell says "file not found or not computed". Files larger than 4 GB are not hashed. *Rows read* comes from the run record; while the run is still going (a single-test workpaper) the count is taken from the rows the input step produced, and says "not recorded" only when that is not known either (for example a folder of several files, where one count cannot be split).

### Exceptions

The listing of the **E** input.

| Column | Contents |
|---|---|
| **A: Ref** | 1, 2, 3...: a stable reference to quote in comments. |
| **B: Tick mark** | A drop-down (✓, X, E, F, N/A) for you. |
| **C: Auditor comment** | Free text for you. |
| **D onwards** | Your columns, in their order. |

Row 1 is a banner: "Showing all 6 exception rows." (or "No exceptions noted."), or in red **"TRUNCATED - showing the first N of M exception rows. The complete list is in *file*."** (and the tab turns red). Row 2 holds the headers (a column called `Ref`, `Tick mark` or `Auditor comment` in your data gets " (data)" added; an unnamed column becomes `Column 3`). The headers, and the Ref column, are frozen; there are filter buttons; the sheet repeats its header when printed. **This sheet is not protected**, so you can sort, tick and comment.

How values are shown: numbers as numbers, dates as `yyyy-mm-dd`, times and timestamps as Excel dates (time zones removed; the clock time is kept, and the Summary says which columns), durations as seconds (header ends "(seconds)"), blanks as truly empty cells, true/false as booleans. Whole-number columns whose name looks like an identifier (`id`, `no`, `number`, `ref`, `code`, `account`, `invoice`, `po`...) have no thousands separator. Whole numbers of 15 digits or more are kept as text, because Excel keeps only 15 significant digits.

#### Amounts

The **Amount column** is shown with your **Decimals** and totalled. If the column is text, amounts such as `1,234.50`, `(12.00)` (read as -12) and ` 7 ` are read as numbers. European and Swiss forms are understood too: `12,5` and `1.234,50` are read as 12.5 and 1234.5, `1'234.50` as 1234.5. A single comma followed by exactly three digits (`1,234`) is a thousands separator. Values that cannot be read at all stay as text, are not totalled, and are counted in a line of *Notes and limitations*. The totals are sums of floating point numbers.

### Run log

The evidence of the run: who ran what, with what, and what each step did.

| Block | What it shows |
|---|---|
| **Banner** | "Completed run." or "Snapshot taken while the workflow was running: steps up to and including *X* are listed; this step is listed as in progress at the end; later steps are not." The node's workpaper is written *during* the run, so it is a snapshot (status `running`, no finish time); the last row, **Workpaper Output (this workpaper)**, has the status "in progress" and stands for the workpaper step itself. |
| **Run header** | Run ID, Status, Started and Finished (UTC), Run by (`user@machine`), Application version, Python, Polars, Workflow file, **Workflow SHA-256**. |
| **Files** | One row per file: Role (`input` or `output`), Path, Sheet, Size, Modified (UTC), SHA-256. |
| **Steps** | **Step**, **Node**, **Type**, **Status**, **Started (UTC)**, **Duration (s)**, **Rows out**, **Message** (the warnings, or for a failed step its plain-language error and hint; failed steps are shaded red). *Rows out* is "not counted" when the run did not count rows for that step. |

The sheet is protected like the Summary. When the run was not recorded, the sheet is **left out** and the Summary says why: "no run record is available (run recording is off or not installed)". Switching off **Include run log** leaves it out too ("turned off in the node settings").

### Workflow

"Steps that produced the data in this workpaper, in the order they ran." One row per step upstream of the node: **Step**, **Node**, **Type**, **What it does (settings)** (one `Label: value` line per setting, long values cut at 300 characters; a **File Input** step reads, for example, `Source`, `Source type`, `Delimiter`, `Encoding`, `Sheet` or `Sheets`, `Row limit` and the folder or pattern options, and leaves out internal bookkeeping) and **Takes data from** (the nodes feeding it). Below, under **Notes in the workflow**, every **Comment** node on the canvas is copied word for word, so your explanations travel with the evidence. Protected like the Summary. If no workflow information is supplied the sheet is left out with the reason on the Summary.

---

## File names, versions and replacing

- **New version** (the default) never overwrites. The first Run writes `wp.xlsx`; the next writes `wp (2).xlsx`, then `wp (3).xlsx`. Your annotated copy is safe. The CSV list, when there is one, is versioned the same way.
- **Replace** overwrites the workbook. If the old file is open in Excel (Excel makes a hidden `~$wp.xlsx` lock file next to it) the Run stops with `TD-OUT-002`, "open in Excel".
- **Stop with error** refuses to write when `wp.xlsx` (or its CSV) exists: `TD-OUT-010`.
- The workbook is built in a temporary folder and moved into place **last**, so a failure never leaves a half-written file, and an existing file is never damaged by a failed Run.
- The run record names the workbook that was really written, with the version number (see [below](#how-a-workpaper-ties-to-the-audit-trail)).

---

## Safe by construction: formulas in your data

Data from other people can contain text that Excel would run as a formula, for example `=HYPERLINK(...)`, or `-2+3`. Opening such a cell, or re-entering it, can run the formula, open a link or leak data. The workpaper protects you:

- **Every piece of text from your data is stored as text**, never as a formula, number or link. The workbook is created with those conversions switched off.
- **Text that starts with `=`, `@`, a tab or a carriage return**, or with **`+` or `-` followed by anything other than a plain number**, also gets Excel's *quote prefix* format, so editing the cell and pressing Enter keeps it as text. A plain signed number such as `-12.50` or `+5` is not touched.
- **The CSV list gets the same treatment:** the risky cells begin with an apostrophe (`'=1+1`).
- Control characters in text are replaced by the replacement character (U+FFFD) and a line in the Summary counts them.
- The only formulas in the workbook are the ones the writer itself created (the Summary's `COUNT`, `SUM`, `COUNTIF` and `IFERROR`).

You can see it in the [worked example](#worked-example): a note `=1+1` in the data is still the text `=1+1` in the Exceptions sheet.

---

## Excel's limits and what happens at them

| Limit | What the workpaper does | Code |
|---|---|---|
| **Rows.** A sheet holds 1,048,576 rows; the workpaper uses 2 for the banner and header, so at most **1,048,574** exceptions can be listed. | The **Row limit** (default 100,000) lists the first rows. Above it the sheet lists the **first N rows and says so**: the red banner, the red tab, the red "TRUNCATED" line and the totals on the Summary, and a note. **Every row** is written to `<workbook name>_exceptions_full.csv` next to the workbook (its row count and SHA-256 are on the Summary). Nothing is dropped silently. | none (a warning in the Logs) |
| **Columns.** 16,384 per sheet; the workpaper adds three. | More than **16,381** data columns: the Run stops. Select fewer columns first. | `TD-OUT-011` |
| **Text in a cell.** 32,767 characters. | Longer text is shortened with a marker ("...[shortened from N characters; full text in the CSV file]"), a note is added, and the full list goes to the CSV even if the row limit was not reached. | none |
| **Sheet names.** 31 characters, no `[ ] : * ? / \`. | The name is cleaned and cut, and kept unique. | none |
| **Whole table to one sheet.** (File Output as Excel, and the Data Preview export, not the workpaper.) | Refused rather than cut: more than 1,048,575 data rows. | `TD-OUT-013` |
| **Excel cannot create the file** (unusable cell content or sheet name). | The Run stops; nothing is written. | `TD-OUT-014` |

The workpaper never refuses for rows: it lists what fits and writes the rest to the CSV. `TD-OUT-013` applies to the one-sheet exports only.

Size and time: a 500,000-row exception list (8 columns) took between 34 and 47 seconds and about 205 MB extra memory in the benchmark on the developer's machine (more than the editor's usual 30-second step limit, which is why this step gets 10 minutes); memory stays bounded however long the list is, because rows are written in batches. The editor stops most steps at **30 seconds** but waits up to **10 minutes** for Workpaper Output (`TD-RUN-001` if even that is exceeded); see [Time and memory limits](running-workflows.md#time-and-memory-limits). For a very long list, lower the **Row limit**, which keeps the workbook small and quick to open; the CSV still carries every row.

---

## How a workpaper ties to the audit trail

Every Run is recorded in the [run history](run-history-and-audit-trail.md) (when **Record every run** is on). The Workpaper Output node adds to it:

- The **workbook is an output of the run**. The run record lists it with its **SHA-256**, the same value you get by hashing the file afterwards. Open **Window > Run History**, select the run, and compare. If somebody edits the workbook later, its fingerprint no longer matches the record, so you can show which version came out of the run. (Annotating your own copy, of course, changes it: keep the original, which **New version** does for you.)
- The workpaper's **Run log** sheet carries the matching evidence: the run ID, the **workflow's SHA-256**, and the input files with the fingerprints taken before they were read.
- Because the node's workpaper is written *during* the run, its Run log is a snapshot. The sealed, final record is in Run History; **File > Export Workpaper...** gives a workpaper of that final record.

---

## Worked example

This is a real run, with a small file, to show what comes out. The input `payments.csv` has ten payments, three of them paid twice, and two cells that would be dangerous in Excel:

```text
vendor,invoice_no,amount,paid_on,note
Acme Ltd,INV-1001,"1,250.00",2025-01-05,
Borealis,INV-2001,980.50,2025-01-06,
Acme Ltd,INV-1001,"1,250.00",2025-01-19,paid twice?
Zenith,INV-3003,4200.00,2025-01-20,
Zenith,INV-3003,4200.00,2025-01-27,=1+1
Cobalt,INV-4004,310.25,2025-02-02,
Cobalt,INV-4005,310.25,2025-02-03,
Borealis,INV-2001,980.50,2025-02-10,-2+3
Delta,INV-5005,75.00,2025-02-11,
Acme Ltd,INV-1002,640.00,2025-02-12,
```

The workflow:

```text
File Input --+--> Duplicates (D) --------> Workpaper Output  E
             |                  (S) -----> Workpaper Output  S
             +-------------------------->  Workpaper Output  P
Comment: "Reviewed with the AP manager."
```

**Duplicates** has *Key columns* `vendor`, `invoice_no`, `amount`; **Workpaper Output** has Reference `C.3.1`, Client `Acme Holdings`, Engagement `FY2025 audit`, Period `Year ended 31 December 2025`, Prepared by `A. Auditor`, Prepared on `2026-03-31`, Test name `Duplicate vendor payments`, an Objective and a Procedure, and Amount column `amount`. After **Run workflow** the file `duplicate_payments.xlsx` appears, with the sheets `Summary`, `Exceptions`, `Run log`, `Workflow`.

### Summary (trimmed)

```text
A1  Duplicate vendor payments
A2  Audit workpaper generated by Trigger Designer 0.1.0 on 2026-10-31 00:24

Engagement
  Workpaper reference   C.3.1
  Client                Acme Holdings
  Engagement            FY2025 audit
  Period                Year ended 31 December 2025
  Test performed        Duplicate vendor payments
  Prepared by           A. Auditor
  Prepared on           2026-03-31
  Reviewed by           (yellow)
  Review date           (yellow)

Objective and procedure
  Objective             Show that no invoice was paid twice.
  Procedure performed   Matched vendor, invoice number and amount across the 2025 payments file.
  Criteria applied      Rows with the same vendor, invoice_no and amount are duplicates
                        (spaces around text trimmed, case-sensitive).

Results
  Measure                              Rows     Value       % pop rows  % pop value  Basis
  Population tested                    10       14,196.50                            Counted from the Population input
  Exceptions found                     6        12,861.00   60.00%      90.59%       Counted from the Exceptions input
  Exceptions listed in this workbook   6        12,861.00                            All exceptions are listed
  Full exception list (CSV)            Not needed - all exceptions are listed in this workbook
  Reconciliation to test result        Agrees to the test node (6 exceptions)

Conclusion / Auditor notes             (yellow)

Tick marks   ✓ Agreed to source document 0 | X Exception confirmed 0 | E Explained - see comment 0 |
             F Follow-up required 0 | N/A Not applicable 0

Source files
  File: .../in/payments.csv   Rows read: 10   Size: 425
  Modified: 2026-10-30T18:54:32Z   SHA-256: 80f16f0f4b8c9db80f150b4ecb11a79d26b94eb89c1239162b699789ba1e48a6

Notes and limitations: Values are summed as floating point numbers.
Workbook contents:     Summary, Exceptions, Run log, Workflow
```

Behind the numbers: `B23` is `=B24`, `B24` is `=COUNT('Exceptions'!$A$3:$A$8)`, `C24` is `=SUM('Exceptions'!$F$3:$F$8)` and `D23` is `=IFERROR(B23/B22,"n/a")`. The amounts were read from text (`1,250.00` became 1250), which is why the value of the six exceptions is 12,861.00.

### Exceptions

```text
A1  Showing all 6 exception rows.
Ref  Tick mark  Auditor comment  vendor    invoice_no  amount  paid_on     note          dup_group_id  dup_count
1                                Acme Ltd  INV-1001    1250    2025-01-05                1             2
2                                Acme Ltd  INV-1001    1250    2025-01-19  paid twice?   1             2
3                                Borealis  INV-2001    980.5   2025-01-06                2             2
4                                Borealis  INV-2001    980.5   2025-02-10  -2+3          2             2
5                                Zenith    INV-3003    4200    2025-01-20                3             2
6                                Zenith    INV-3003    4200    2025-01-27  =1+1          3             2
```

`Tick mark` and `Auditor comment` are empty for you to fill in. In `note`, `-2+3` and `=1+1` are **text** with the quote prefix, not formulas (the cells show exactly what the data said).

### Run log (trimmed)

```text
A2  Snapshot taken while the workflow was running: steps up to and including Duplicates are listed;
    this step is listed as in progress at the end; later steps are not.
Run ID 7f65b31a2ec1481c94bbbf2359c6d8df   Status running   Started (UTC) 2026-10-30T18:54:34.890001Z
Run by kashvinchandrasan@USMUMKASHVIM2    Application version 0.1.0   Python 3.14.8   Polars 2.0.0
Workflow SHA-256  552818fbaf33ac0b7a1df9a9fbc5bf74289b7a4711518925cfdbfac934ce1555

Role   Path               Size  Modified (UTC)               SHA-256
input  .../in/payments.csv  425  2026-10-30T18:54:32.205544Z  80f16f0f4b8c9db80f150b4ecb11a79d26b94eb89c1239162b699789ba1e48a6

Step  Node        Type        Status  Started (UTC)                Duration (s)  Rows out
1     File Input  File Input  ok      2026-10-30T18:54:34.941898Z  0.00626       10
2     Duplicates  Duplicates  ok      2026-10-30T18:54:34.948224Z  0.00917       11
3     Workpaper Output (this workpaper)  in progress  (time of writing)  in progress  not counted
```

(*Rows out* of Duplicates is 11: 6 duplicates, 4 unique rows and the one-row summary.)

### Workflow (trimmed)

```text
Step  Node        What it does (settings)                                        Takes data from
1     File Input  Filepath: .../in/payments.csv, File type: csv, Delimiter: ...
2     Duplicates  Key columns: ["vendor", "invoice_no", "amount"]               File Input
                  Mode: exact / Trim text: yes / Ignore case: no / Tolerance: 0.0 ...
Notes in the workflow
  Note  Reviewed with the AP manager.
```

### The audit trail

After the Run, **Window > Run History** lists the run with the workbook as an output. Its SHA-256 (`bce72a5c...8370a` in this run) is the SHA-256 of `duplicate_payments.xlsx`, as you can check with `certutil -hashfile duplicate_payments.xlsx SHA256`.

### The whole run

**File > Export Workpaper...** on the same run gives `Summary`, `Run log` and `Workflow` (no Exceptions). Its **Test results** table:

```text
Test        Status  Population rows  Exceptions  Exception rate  Result
Duplicates  fail    10               6           60.00%          Rows with the same vendor, invoice_no and amount are duplicates (spaces ...
```

and its Run log reads "Completed run.", Status `ok`, with all four steps, the Workpaper Output step among them, and the workbook as an `output` with its fingerprint.

---

## From the command line

A workflow with a Workpaper Output node runs unattended with `trigger-designer-cli` like any other (see [Command line](cli.md)). Approve it once, then run it:

```text
> trigger-designer-cli approve dup_payments.tds --yes
...
operations:
  audit.duplicates: 1
  input.file_input: 1
  input.workpaper_output: 1
  report.comment: 1
writes:
  ...\gui\duplicate_payments.xlsx

> trigger-designer-cli run dup_payments.tds --output-dir D:\audit\out --create-output-dirs
... INFO    node.started node_id=... title=Workpaper Output op=input.workpaper_output index=2 total=4
... INFO    node.finished ... title=Workpaper Output status=ok duration_s=0.266
... INFO    output.committed path=...\duplicate_payments.xlsx size_bytes=11526 sha256=1823177c...
... INFO    run.finished status=ok exit_code=0 ... nodes_ok=4 nodes_failed=0
```

What was checked in a real run:

- **`--output-dir` moves the workbook.** The file was written to `D:\audit\out\duplicate_payments.xlsx` and not to the folder saved in the workflow. The `output.committed` line gives the SHA-256 of the workbook, and it equals the hash of the file.
- **`approve` and `info` list the workbook** under `writes`, so a reviewer approving the workflow sees where it will write.
- **The Exceptions, Summary and Workflow sheets are the same as from the editor.** The workflow still carries the Comment notes. The Engagement defaults come from the Preferences of the Windows user who runs the command, unless the node has its own values.
- **The Run log sheet is there.** The command line gives the workpaper a snapshot of the run in flight, exactly as the editor does: the steps before the workpaper with status, start time and duration. With `--no-record` the sheet is left out and the Summary says "The Run log sheet was omitted: no run record is available (run recording is off or not installed)". The command line also writes its own run record (`record_path` on the `run.finished` line).
- **A truncated list works as in the editor.** When the exceptions exceed the **Row limit**, `duplicate_payments_exceptions_full.csv` is written next to the final workbook (in the `--output-dir` folder) and the Summary names it.
- **Versions work too.** A second run with **If it exists** on **New version** writes `duplicate_payments (2).xlsx` and `duplicate_payments (2)_exceptions_full.csv` beside the first ones. The numbered name is chosen before the write, and **Stop with error** refuses an existing file before anything runs.
- **Extra source files follow `--input-dir`**, like a File Input.

---

## Errors you may see

| Code | What it means | What to do |
|---|---|---|
| `TD-OUT-001` | The output folder does not exist. | Create it, or choose an existing folder. |
| `TD-OUT-002` | The workbook is open in Excel (or read-only). | Close it and run again, or choose another name. |
| `TD-OUT-003` | The Excel writer component (`xlsxwriter`) is missing from this installation. | Export CSV or Parquet instead, or reinstall. |
| `TD-OUT-010` | **A workpaper with this name already exists** and **If it exists** is **Stop with error** (or the CSV list already exists). | Choose another file name, or set **If it exists** to **New version**. |
| `TD-OUT-011` | **Too many columns:** the Exceptions input has more than 16,381 columns (16,384 less the three the workpaper adds). | Select fewer columns before Workpaper Output. |
| `TD-OUT-012` | **The settings are not valid:** no file chosen, the file does not end in `.xlsx`, or **Prepared on** is not a `YYYY-MM-DD` date. | Fix the named setting. |
| `TD-OUT-013` | **A table is too large for an Excel sheet** (more than 1,048,575 data rows). Raised by File Output as Excel and the Data Preview export. The workpaper lists what fits and writes the rest to a CSV instead. | Save as CSV or Parquet. |
| `TD-OUT-014` | **Excel could not create the workbook:** a sheet name or cell content that Excel refuses. | Rename the sheet (**Exceptions sheet**) or shorten the offending text. |
| `TD-OUT-015` | **Excel output must use the .xlsx extension** (File Output with Excel selected and a name ending in `.xls`; not raised by Workpaper Output, which reports `TD-OUT-012`). | Rename the file to end in `.xlsx`. |
| `TD-OUT-005` | The disk is full. | Free space or use another drive. |

Also: *Workpaper Output has no output file; choose one before running.* (a workflow with an empty **File** is flagged when it is opened and before Run). A Workpaper Output step that takes more than 10 minutes in the editor (30 seconds for other steps) stops with `TD-RUN-001` ([Running workflows](running-workflows.md#time-and-memory-limits)); the workpaper step notices that the run has given up on it and does not write the workbook afterwards, so no file appears from a failed run. Lower the **Row limit** and run again.

---

## Tips

- Set your **Preferences > Engagement** once per engagement, and leave the node's Client, Engagement, Period and Prepared by empty.
- Connect all three inputs when you can. **P** gives you the population and its value, **S** gives the rule and proves the exception count agrees.
- Fill **Test name**, **Objective** and **Procedure** in the node, so the workpaper needs only your conclusion.
- Keep **If it exists** on **New version** while you work and Replace only for a scratch file.
- Put a **Comment** node on the canvas near the steps you want to explain. It is copied to the Workflow sheet.
- Hash and keep the original: the version you annotate is a different file from the one in the run record.
- Do the sampling, then the workpaper: connect a **Sample** node's output to **E** to document the items selected for testing.
