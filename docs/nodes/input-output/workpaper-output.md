# Workpaper Output

![Workpaper Output icon (shared with File Output)](../../assets/node_icons/Input/File%20Output.svg){ .node-icon }

## Purpose

Workpaper Output writes the exceptions of one audit test as a formatted **Excel workpaper** of four sheets: **Summary** (engagement, objective, results tied to the exception list by formulas, conclusion, source files with SHA-256), **Exceptions** (the rows, with a tick-mark drop-down and a comment column), **Run log** and **Workflow** (what ran, with what, and every step's settings). It is the evidence file you attach to your working papers. It does not change the data and has no output socket.

The full description of the sheets, the rules and the limits is in [Workpapers](../../guide/workpaper.md). This section is the node's reference.

## When to use it

- You ran an [audit node](../audit/index.md) (Duplicates, Gaps, Benford, Sample, Risk Filters) and need a file for the engagement file with space for tick marks and comments.
- You need a reviewer to be able to check which data you used (file fingerprints) and what steps produced the result (the Workflow sheet).
- You want one workpaper per test. For a one-page overview of the whole last run, use **File > Export Workpaper...** instead.

If you only want the rows in a file, use [File Output](file-output.md).

## Inputs and outputs

| Socket | Direction | Carries |
|---|---|---|
| **E** Exceptions (input 1) | Input | The rows to list. **Required.** Typically the Duplicates, Gaps or Flagged output of an audit node. |
| **P** Population (input 2) | Input | Everything that was tested; counted for the population and its value. Optional. |
| **S** Summary (input 3) | Input | The one-row Summary of the audit node: the test name, the rule, the status and the counts. Optional; lets the workpaper reconcile its exception count with the test's. |
| (none) | Output | Workpaper Output has no output socket. It is an end point. |

Without **E** the node is red with the tooltip "Connect the Exceptions input". A connected **P** or **S** that has failed upstream turns the node red as well ("Population input has no data" / "Summary input has no data"); it is never ignored.

## Settings

The Config Dock has six sections. The header shows the chips `xlsx`, the row limit and the "If it exists" choice. Empty Engagement boxes use [Preferences](../../guide/preferences.md#engagement) (**Edit > Settings > General > Engagement**), shown in grey inside the box.

**File**

| Control | What it does | Default |
|---|---|---|
| **File** with a **Browse for save location** icon button | The `.xlsx` workbook to write. The folder must exist. | Empty (placeholder "Enter file path (.xlsx)") |
| **If it exists** | **New version** writes `name (2).xlsx` and keeps the old file; **Replace** overwrites; **Stop with error** refuses (`TD-OUT-010`). | New version |

**Engagement** (can be collapsed)

| Control | What it does | Default |
|---|---|---|
| **Reference** | Your workpaper reference (placeholder "e.g. C.3.1"). | Empty |
| **Client**, **Engagement**, **Period** | Header of the Summary. | Empty, then Preferences |
| **Prepared by** | The preparer. | Empty, then Preferences, then your Windows user name |
| **Prepared on** | `YYYY-MM-DD`; an invalid date stops the Run (`TD-OUT-012`). | Empty = the day of the Run (placeholder "today (YYYY-MM-DD)") |
| **Logo** with a **Browse for logo image** icon button | PNG or JPG for the top right of the Summary. | Empty, then Preferences |

**Test**

| Control | What it does | Default |
|---|---|---|
| **Test name** | Title of the workpaper and "Test performed". | Empty (the **S** input's test name is used) |
| **Objective**, **Procedure** | Several lines each. Empty ones become yellow cells for you to fill in. | Empty |
| **Criteria** | The rule applied. | Empty (the **S** input's rule, or "Not provided - complete manually") |

**Values**

| Control | What it does | Default |
|---|---|---|
| **Amount column** | Column of the Exceptions input to total (number, or text holding amounts such as `1,234.50`). Tooltip: "Column summed for the value statistics". | None |
| **Decimals** | Decimal places (0 to 6) shown for values. | 2 |

**Sheets**

| Control | What it does | Default |
|---|---|---|
| **Row limit** | The most exceptions listed in the workbook, 1 to 1,048,574. More rows go to a CSV file next to the workbook, and the workpaper says so. | 100,000 |
| **Exceptions sheet** | Name of the listing sheet (cleaned to Excel's rules, 31 characters). | `Exceptions` |
| **Include run log** | Adds the Run log sheet. | On |
| **Include workflow** | Adds the Workflow sheet. | On |

**Sources** (collapsed by default)

| Control | What it does | Default |
|---|---|---|
| **Extra source files** | One path per line: files read outside the workflow. They are listed and hashed on the Summary. | Empty |

## Worked example

A File Input reads `payments.csv` (10 payments). **Duplicates** with *Key columns* `vendor`, `invoice_no`, `amount` finds 6 rows in 3 groups. Connect Duplicates' **Duplicates** output to **E**, the File Input to **P** and Duplicates' **Summary** output to **S**. Set **File** to `D:\audit\duplicate_payments.xlsx`, **Test name** to "Duplicate vendor payments" and **Amount column** to `amount`, then press **Run workflow**.

The Summary of the workbook reads, in part:

| Measure | Rows | Value | % of population rows | % of population value | Basis |
|---|---|---|---|---|---|
| Population tested | 10 | 14,196.50 | | | Counted from the Population input |
| Exceptions found | 6 | 12,861.00 | 60.00% | 90.59% | Counted from the Exceptions input |
| Exceptions listed in this workbook | 6 | 12,861.00 | | | All exceptions are listed |
| Reconciliation to test result | Agrees to the test node (6 exceptions) | | | | |

The Exceptions sheet lists the 6 rows with empty **Tick mark** and **Auditor comment** columns for you. Run it a second time and `duplicate_payments (2).xlsx` appears next to the first one. See [the worked example in Workpapers](../../guide/workpaper.md#worked-example) for every sheet.

## Edge cases and limits

- **It only writes on Run.** While you edit, nothing is written and the node produces no output.
- **Never overwrites by accident.** With **New version** a second Run makes a numbered copy. The workbook is built in a temporary folder and moved into place last, so a failed Run leaves no half-written file.
- **A file open in Excel** stops a Replace with `TD-OUT-002`.
- **More exceptions than the Row limit:** the workbook lists the first rows with a red "TRUNCATED" banner and writes every row to `<name>_exceptions_full.csv` next to it. Nothing is dropped silently.
- **Text starting with `=`, `+`, `-` or `@`** is stored as text, never as a formula.
- **No recorded run** (Preferences > Record every run off): the Run log sheet is left out and the Summary says why.
- **Big lists are slow.** About 500,000 rows take 35 to 45 seconds, more than the 30 second limit per step; lower the Row limit (see [Limits and performance](../../guide/limits-and-performance.md)).
- **From the command line** the Run log sheet is left out (the command-line run installs no run-record source). **If the file exists** is obeyed there too, `--output-dir` and `--param` can redirect the workbook, and **Source files** follow `--input-dir`; see [The command line](../../guide/cli.md#workpaper-output-on-the-command-line) and [Workpapers](../../guide/workpaper.md#from-the-command-line).
- The workpaper node is not a way to write the whole table: use File Output for that.

## Errors you may see

| Code | What it means | What to do |
|---|---|---|
| `TD-OUT-001` | The output folder does not exist. | Create it, or choose an existing folder. |
| `TD-OUT-002` | The workbook is open in Excel or read-only. | Close it, or choose another name. |
| `TD-OUT-003` | The Excel writer component is missing from this installation. | Reinstall, or use CSV or Parquet. |
| `TD-OUT-010` | A workpaper with this name already exists and **If it exists** is **Stop with error**. | Choose another name or set **New version**. |
| `TD-OUT-011` | The Exceptions input has more than 16,381 columns (Excel's 16,384 less three). | Select fewer columns first. |
| `TD-OUT-012` | The settings are not valid: no file, a file not ending in `.xlsx`, or **Prepared on** not `YYYY-MM-DD`. | Fix the named setting. |
| `TD-OUT-014` | Excel could not create the workbook (a sheet name or a cell it refuses). | Rename the **Exceptions sheet** or shorten the text. |
| `TD-RUN-001` | The step took more than 30 seconds. | Lower the **Row limit**; check the file before running again. |

The node also shows "Workpaper Output has no output file; choose one before running." when **File** is empty.

## Tips

- Fill in Preferences > Engagement once and leave the node's Engagement section empty.
- Connect **P** and **S** whenever you can: the population, the rule and the reconciliation line then fill themselves in.
- Keep **New version** while you work: your annotated copy is never overwritten.
- Add a [Comment](../report/comment.md) to the canvas to explain a step; it is copied to the Workflow sheet.


Back to the [Input and Output node index](index.md).
