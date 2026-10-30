# Join nodes

These nodes combine two or more tables. Pick the one that matches the question you are asking.

| If you want to... | Use |
|---|---|
| Put the rows of one table under the rows of another (two inputs) | [Append](#append) |
| Stack any number of tables, with control over how columns line up | [Union](#union) |
| Look up matching rows by an exact key, and see what matched, what only the left has and what only the right has | [Join](#join) |
| Match two lists on keys plus an amount (with a tolerance) and a date window, and report the differences | [Reconcile](#reconcile) |
| Match names or descriptions that are almost, but not exactly, the same | [Fuzzy Match](#fuzzy-match) |

## Contents

- [Before you start: left, right and the 100-row preview](#before-you-start-left-right-and-the-100-row-preview)
- [Append](#append) | [Union](#union) | [Join](#join) | [Reconcile](#reconcile) | [Fuzzy Match](#fuzzy-match)

## Before you start: left, right and the 100-row preview

- **Left and right.** Append, Join, Reconcile and Fuzzy Match have two input sockets. The first socket (top) is the **left** input and the second socket is the **right** input. "Input 1" in an error message means the left one and "Input 2" the right one. Swapping them changes which side's columns come first and which outputs are "left only" and "right only".
- **Output sockets are lettered.** Join has `L`, `J`, `R`. Reconcile has `M`, `L`, `R`, `S`. Fuzzy Match has `M`, `L`, `R`. Connect each socket to the node you want to receive that output. The summary line at the top of the Config Dock spells out what each letter means.
- **Live preview versus Run.** While you edit, each input is cut to its first 100 rows, so a match that needs row 101 will not appear in the preview. Run uses all rows. See [Live preview and Run](input-output.md#live-preview-and-run).
- **Row order is not guaranteed.** After a join or match, rows may come out in a different order from run to run. If order matters, add a Sort node (see [Preparation nodes](preparation.md)) after it.

---

## Append

<img src="../../../src/trigger_designer/resources/qt/images/node_icons/Join/Append.svg" width="56" alt="Append icon">

### Contents

[Purpose](#purpose) | [When to use it](#when-to-use-it) | [Inputs and outputs](#inputs-and-outputs) | [Settings](#settings) | [Worked example](#worked-example) | [Edge cases and limits](#edge-cases-and-limits) | [Errors you may see](#errors-you-may-see) | [Tips](#tips)

### Purpose

Append puts the rows of the right input underneath the rows of the left input. It always handles exactly two inputs.

### When to use it

- You have two tables with the same layout (this year and last year) and want one table.
- You want to place two tables side by side (Horizontal), row for row.

For more than two inputs, or when you want to line up columns that have different names, use [Union](#union).

### Inputs and outputs

| Socket | Carries |
|---|---|
| Input 1 (left, top) | The first table. Its rows come first. |
| Input 2 (right, bottom) | The second table. |
| Output `Out` | The two tables combined. |

### Settings

One section, **Append**, with the note "Vertical requires identical schemas."

| Control | What it does | Default |
|---|---|---|
| **Method** | **Diagonal (relaxed)**: stack the rows; match columns by name; a column missing on one side is filled with empty values; a column with different types on the two sides is widened to a type that holds both (for example whole numbers and decimals become decimals; numbers and text become text). **Vertical (same columns)**: stack the rows, but only if both tables have exactly the same columns and types; otherwise stop with an error. **Horizontal (side by side)**: put the right table's columns next to the left table's columns, row by row. **Diagonal (strict)**: like Diagonal (relaxed), but columns that appear on both sides must have exactly the same type. | Diagonal (relaxed) |

The chip in the Config Dock shows the method and "rows stacked, left then right".

### Worked example

Left input (open invoices):

| Invoice | Amount |
|---|---|
| A1 | 100.0 |
| A2 | 250.0 |
| A3 | 75.0 |

Right input (payments, with an extra column):

| Invoice | Amount | Paid |
|---|---|---|
| A1 | 100.0 | Y |
| A3 | 80.0 | N |
| A9 | 10.0 | Y |

With **Method** = Diagonal (relaxed), the output `Out` is:

| Invoice | Amount | Paid |
|---|---|---|
| A1 | 100.0 | null |
| A2 | 250.0 | null |
| A3 | 75.0 | null |
| A1 | 100.0 | Y |
| A3 | 80.0 | N |
| A9 | 10.0 | Y |

With **Vertical (same columns)** the same two tables stop with `TD-SHAPE-004`: `schemas differ (right-only: ['Paid']). Try 'diagonal_relaxed'.`

With **Horizontal**, two tables of the same length, `Invoice` (A1, A2) and `Paid` (Y, N), give:

| Invoice | Paid |
|---|---|
| A1 | Y |
| A2 | N |

### Edge cases and limits

- **Row cap:** none. The live preview shows 100 rows; Run appends everything. See [Live preview and Run](input-output.md#live-preview-and-run).
- **Empty input:** an empty table contributes no rows; its columns still count for Diagonal methods.
- **Nulls** stay null.
- **Different types.** Diagonal (relaxed) widens (a column of numbers on one side and text on the other becomes text, so `3` and `"x"` coexist). Vertical and Diagonal (strict) refuse.
- **Horizontal** needs the same number of rows on both sides and different column names on both sides. Otherwise it stops (see errors).
- The Vertical error says what differs: columns only on one side (`left-only: [...]`, `right-only: [...]`), a column with different types (`'Amount' is Int64 on the left but String on the right`), or the same columns in a different order.

### Errors you may see

| Code | What it means | What to do |
|---|---|---|
| `TD-SHAPE-004` | **Vertical** was chosen and the two tables are not identical in columns and types. | Choose **Diagonal (relaxed)**, or make the inputs match with Select nodes. |
| `TD-SCH-004` | **Diagonal (strict)** was chosen and a shared column has different types, or the columns differ. | Make both inputs have the same columns and types, or use Diagonal (relaxed). |
| `TD-SCH-005` | **Horizontal**: the two tables have different numbers of rows. | Make sure both come from the same step, or use Diagonal. |
| `TD-SCH-002` | **Horizontal**: a column name appears on both sides. | Rename one of them with a Select node first. |
| `TD-SHAPE-005` | An input has no data ("Input 1 has no data"). | Connect and fix the upstream node. |

### Tips

- Use Append for "this year plus last year". If the second table has a column the first lacks, keep Diagonal (relaxed) and check the new column for empty cells in the first table's rows.
- To keep track of where each row came from, add a column to each side first (for example a Formula that writes `"2024"` or `"2025"`).

---

## Union

<img src="../../../src/trigger_designer/resources/qt/images/node_icons/Join/Union.svg" width="56" alt="Union icon">

### Contents

[Purpose](#purpose-1) | [When to use it](#when-to-use-it-1) | [Inputs and outputs](#inputs-and-outputs-1) | [Settings](#settings-1) | [Worked example](#worked-example-1) | [Edge cases and limits](#edge-cases-and-limits-1) | [Errors and messages](#errors-and-messages) | [Tips](#tips-1)

### Purpose

Union stacks any number of tables, one under the other (the SQL "UNION ALL": all rows are kept, duplicates are not removed). It has three ways of lining up the columns.

### When to use it

- You have three or more tables with the same layout (twelve monthly extracts, one table per entity).
- The tables are almost the same but a few columns are named differently, and you want to say which column lines up with which.
- You want to stack by column position and ignore headers.

### Inputs and outputs

| Socket | Carries |
|---|---|
| Input (a single socket on the left that accepts **any number of connections**) | Every connected table. Connect as many as you need to this one socket. |
| Output (one, on the right) | The stacked table. |

The inputs are stacked in connection order (`#1` first). The **Input order** section lets you change it.

### Settings

The Config Dock shows "Connect at least one input" until something is connected. After that it has up to three sections.

**Union mode** ("How columns from the inputs are aligned.")

| Control | What it does | Default |
|---|---|---|
| **Mode** | **Auto by Name**: columns with exactly the same name (upper/lower case matter) line up. The output has every name found, in the order first seen; a table without a column gets empty values there. **Auto by Position**: ignore names; the first column of each table lines up, then the second, and so on. The output uses the first table's column names; if another table is wider, the extra columns are named `Extra_4`, `Extra_5`..., and shorter tables are filled with empty values. **Manual**: you build the output columns yourself. | Auto by Name |

**Input order** ("Rows stack #1 first. Reorder with Up/Down or reconnect edges.")

One row per connected input, labelled with its number and where it comes from (for example `#1 File Input [out 0]`), with two icon buttons per row: **Move input N earlier** and **Move input N later**. Each move is an undo step ("Input Order Changed").

**Column Mapping** (only in Manual mode; "Align each input's column to an output. Blank = Null.")

| Control | What it does |
|---|---|
| Header row | `Output`, then one heading per input. |
| **Output column** (text box) | The name of this column in the result. |
| One drop-down per input | Which column of that input goes into this output column. `(none)` leaves it empty (null) for that input. |
| **Add output column** (icon) | Adds a row, named `New_Column`, `New_Column_2`... |
| **Remove output column** (icon, per row) | Removes the row. |

The first time you switch to Manual, the grid is pre-filled with the Auto-by-Name result so you can adjust it. Rows with an empty or repeated output name are ignored. Edits apply about a third of a second after you stop.

### Worked example

Three tables:

`Table 1`

| Invoice | Amount |
|---|---|
| A1 | 10 |
| A2 | 20 |

`Table 2` (the amount is text; has an extra column)

| Invoice | Amount | Note |
|---|---|---|
| B1 | "30" | late |

`Table 3` (reference column has a different name)

| Ref | Amount |
|---|---|
| C1 | 5 |

**Auto by Name** gives:

| Invoice | Amount | Note | Ref |
|---|---|---|---|
| A1 | 10 | null | null |
| A2 | 20 | null | null |
| B1 | 30 | late | null |
| null | 5 | null | C1 |

`Amount` is whole numbers in two tables and text in the other, so the whole column becomes text (shown as numbers here for readability). The node's tooltip says: `Column 'Amount' has conflicting types (Int64, String); coerced to String.` `Ref` is a separate column from `Invoice`; to line them up use Manual.

**Manual** with two tables, `Table 1` = (Invoice, Amount) and `Table 4` = (Ref, Total, Note):

| Output | Table 1 | Table 4 |
|---|---|---|
| Doc | Invoice | Ref |
| Value | Amount | Total |
| Comment | (none) | Note |

gives

| Doc | Value | Comment |
|---|---|---|
| A1 | 10 | null |
| B1 | 20 | x |

(`Table 1` supplies A1/10; `Table 4` supplies B1/20/x.)

**Auto by Position** on the same two tables (`Table 1` has two columns, `Table 4` three) gives column names from `Table 1` plus `Extra_3`:

| Invoice | Amount | Extra_3 |
|---|---|---|
| A1 | 10 | null |
| B1 | 20 | x |

### Edge cases and limits

- **One connected input** passes through unchanged.
- **Row cap:** none. The live preview shows the first 100 rows of the result; Run stacks everything. See [Live preview and Run](input-output.md#live-preview-and-run).
- **Type conflicts.** When the same column (or position, or Manual row) has different types across inputs, it is converted to text for all of them, and a warning appears in the node's tooltip. Text-to-text and number-to-number needs no conversion.
- **Names are case-sensitive** in Auto by Name: `Amount` and `amount` become two columns.
- **Disconnected or empty upstream nodes** are skipped. If none produces data the tooltip says "Upstream nodes produced no output".
- **Manual with no valid rows** falls back to the Auto-by-Name layout.
- If stacking fails for any reason the node is marked invalid with the tooltip "Union failed" (the technical detail is in the log).
- Adding or removing a connection while the Manual grid is open rebuilds the grid so that the new input's columns appear.

### Errors and messages

Union does not raise `TD-` codes. It reports on the node tooltip:

| Message | What it means |
|---|---|
| Connect at least one input | Nothing is connected. |
| Upstream nodes produced no output | The connected nodes have errors or no data; fix them first. |
| Union failed | The tables could not be stacked. Check the column types; look in the log for details. |
| Column 'X' has conflicting types (...); coerced to String. | A warning, not an error. The column was turned into text. |

### Tips

- Prefer Auto by Name when the tables come from the same system. Use Manual when the tables come from different systems and the same field has different names.
- To record which table a row came from, add a source column to each input before the Union (a Formula writing the table name), or have File Input add the filename.
- If you only have two tables, [Append](#append) is simpler.

---

## Join

<img src="../../../src/trigger_designer/resources/qt/images/node_icons/Join/Join.svg" width="56" alt="Join icon">

### Contents

[Purpose](#purpose-2) | [When to use it](#when-to-use-it-2) | [Inputs and outputs](#inputs-and-outputs-2) | [Settings](#settings-2) | [Worked example](#worked-example-2) | [Edge cases and limits](#edge-cases-and-limits-2) | [Errors you may see](#errors-you-may-see-1) | [Tips](#tips-2)

### Purpose

Join matches the rows of two tables on one or more key columns and gives you three results at once: the rows that matched (with columns from both sides), the left rows that have no match, and the right rows that have no match. You never lose a row silently, which is what you want in an audit.

### When to use it

- You want to bring information from one table into another (add the vendor's country to each payment).
- You want to find what is in one list and not in the other (invoices without payment, payments without invoice), when the keys are exactly equal.

If the keys are not exactly equal (small differences in text, amounts that must agree within a tolerance, dates that may be a few days apart), use [Reconcile](#reconcile) or [Fuzzy Match](#fuzzy-match).

### Inputs and outputs

| Socket | Carries |
|---|---|
| Input 1 (left, top) | The left table. |
| Input 2 (right, bottom) | The right table. |
| Output `L` | **Left only.** Left rows with no matching right row. Columns: all of the left table's columns. |
| Output `J` | **Joined.** Rows that matched on the keys, with the columns you chose in Output columns (all by default). |
| Output `R` | **Right only.** Right rows with no matching left row. Columns: all of the right table's columns. |

### Settings

Until both inputs are connected the Config Dock says "Both inputs must be connected". Then:

**Key pairs**

| Control | What it does | Default |
|---|---|---|
| **Add key pair** (icon) | Adds a pair: a column from the left table, an arrow, a column from the right table. Rows match when all pairs are equal. The new pair is pre-filled with the first column combination not already used. | One pair is created for you: the first column of each table |
| Each pair: **Left key column**, **Right key column** | The columns that must be equal. A column that has vanished from the input is shown as `name (missing)`. | |
| **Remove key pair** (icon) | Deletes the pair. | |

**Output columns** ("Unchecked columns stay out of the joined output.")

| Control | What it does | Default |
|---|---|---|
| **Auto-accept new columns** (checkbox) | When on, a column that newly appears upstream is ticked automatically. When off, it stays unticked until you tick it. | On |
| **All** / **None** | Tick or untick every column. | |
| Column checklist, entries shown as `L: name` and `R: name` | Which columns the `J` output contains. `L:` columns come from the left table, `R:` from the right. | Everything ticked |

The output columns control the `J` output only. `L` and `R` always carry every column of their own side.

A summary chip shows the number of keys and the number of columns, with "full outer join".

### Worked example

Left (invoices):

| Invoice | Amount |
|---|---|
| A1 | 100.0 |
| A2 | 250.0 |
| A3 | 75.0 |

Right (payments):

| Invoice | Amount | Paid |
|---|---|---|
| A1 | 100.0 | Y |
| A3 | 80.0 | N |
| A9 | 10.0 | Y |

Key pair: `Invoice` = `Invoice`. Everything ticked.

Output `L` (invoice A2 has no payment):

| Invoice | Amount |
|---|---|
| A2 | 250.0 |

Output `J`:

| Invoice | Amount | Amount_right | Paid |
|---|---|---|---|
| A1 | 100.0 | 100.0 | Y |
| A3 | 75.0 | 80.0 | N |

Output `R` (payment A9 has no invoice):

| Invoice | Amount_right | Paid |
|---|---|---|
| A9 | 10.0 | Y |

When both tables have a column of the same name (`Amount`), the right table's column is renamed `Amount_right` in `J` and `R`. In the Output columns list it still appears as `R: Amount`.

If you tick only `L: Invoice` and `R: Paid` in Output columns, `J` becomes:

| Invoice | Paid |
|---|---|
| A1 | Y |
| A3 | N |

When the key columns have different names (`InvoiceNo` on the left, `Ref` on the right), the key appears once in `J`, under the **left** name, and in `R` the right-only keys also appear under the left name (`InvoiceNo`).

### Edge cases and limits

- **Row cap:** none in the node. The live preview shows 100 rows; Run joins everything. See [Live preview and Run](input-output.md#live-preview-and-run).
- **Exact match only.** Keys are compared as they are: `ABC` and `abc` do not match, and `A1` and ` A1` (with a space) do not match. Clean keys first (see Cleansing in [Preparation nodes](preparation.md)) or use [Reconcile](#reconcile), which trims and ignores case.
- **Null keys never match.** A left row with an empty key goes to `L`; a right row with an empty key goes to `R`.
- **One-to-many.** If one left row matches several right rows, `J` has one row per pair, so the left row appears several times. Row counts in `J` can therefore be higher than either input. Check for duplicate keys with the [Duplicates audit node](audit.md) before you join.
- **Key types must be the same.** A number key against a text key is refused (see errors). Convert one side with a Select node.
- **Columns that disappear upstream** are dropped from the Output columns selection. A key pair whose column no longer exists is dropped too. If you remove every key pair (or the last one disappears), Join puts the default pair back (the first column of each table) the next time it evaluates, so check the key pair after changing the inputs.
- **Renamed columns upstream.** If you rename a column in a Select node placed before Join, the key pairs and selections follow the new name.
- **Row order is not guaranteed** (a 1-to-many join may list the matches in any order). Add a Sort node if order matters.

### Errors you may see

| Code | What it means | What to do |
|---|---|---|
| `TD-SHAPE-001` | "Add at least one key pair". No pair is set (rare: the dock normally re-creates the default pair). | Add a key pair. |
| `TD-TYP-002` | The two key columns have different types, for example whole numbers against text. | Add a Select node on one side and set the key column to the same type (usually Text). |
| `TD-SHAPE-005` | An input has no data. | Connect and fix the upstream node. |

### Tips

- Join the two tables and check three numbers: rows in `L`, rows in `J`, rows in `R`. They should explain your totals: left rows = `L` + the left side of `J`.
- To get a classic "left join", use `J` and `L` together with [Append](#append) (Diagonal), or just use `L` to list the exceptions.
- Join on several columns at once (company and invoice number) with extra key pairs rather than creating a combined key.

---

## Reconcile

<img src="../../../src/trigger_designer/resources/qt/images/node_icons/Join/Reconcile.svg" width="56" alt="Reconcile icon">

### Contents

[Purpose](#purpose-3) | [When to use it](#when-to-use-it-3) | [Inputs and outputs](#inputs-and-outputs-3) | [Settings](#settings-3) | [Worked example](#worked-example-3) | [Edge cases and limits](#edge-cases-and-limits-3) | [Errors you may see](#errors-you-may-see-2) | [Tips](#tips-3)

### Purpose

Reconcile compares two lists (for example the bank statement and the ledger) the way an auditor does: match on reference keys, check that the amounts agree within a tolerance, check that the dates are close enough, and then tell you what matched, what is left over on each side and how much the totals differ. It gives four outputs, including a one-row summary you can quote.

### When to use it

- Bank to ledger, sub-ledger to general ledger, invoices to payments, purchase orders to receipts.
- The two sides do not agree to the cent, or the dates differ by a few days.
- One side may have several lines for one line on the other (one invoice paid in instalments).

### Inputs and outputs

| Socket | Carries |
|---|---|
| Input 1 (left) | The first list (for example the ledger). |
| Input 2 (right) | The second list (for example the bank). |
| Output `M` | **Matched.** One row per matched pair (or per line in a group), with the left columns followed by the right columns, preceded by `Match_ID`, `Match_Status` and the differences. |
| Output `L` | **Left unmatched.** Left rows with no match, plus `Unmatched_Reason`. |
| Output `R` | **Right unmatched.** Right rows with no match, plus `Unmatched_Reason`. |
| Output `S` | **Summary.** One row with counts, totals and the net difference. |

### Settings

Four sections.

**Match**

| Control | What it does | Default |
|---|---|---|
| **Match type** (segmented buttons) | **1 : 1**: each left row is matched with at most one right row. **1 : N**: one left row may be matched with many right rows (for example an invoice paid in several instalments). **N : 1**: many left rows to one right row. **N : N**: lines are grouped by the keys on each side and the groups are compared. Hint: "Match type controls how many times each side may be used." | 1 : 1 |
| **Key pairs** (list, up to 10) | Each pair is a **Left column** and a **Right column** whose values must be equal. Every pair must agree for two rows to be candidates. Add pairs with the **Add** icon. Rows with an empty left or right column are ignored. Hint: "Keys are trimmed and compared as lower-case text. Null keys never match." | Empty |

**Amount**

| Control | What it does | Default |
|---|---|---|
| **Left amount** / **Right amount** | Optional. The numeric (or number-like text) columns to compare. Leave both blank to match without checking amounts. Setting only one side is an error. | Blank |
| **Tolerance** (segmented: **Amount** or **Percent**) and **Value** | How far apart the two amounts may be and still count as agreeing. **Amount**: an absolute difference (for example 0.50). **Percent**: a percentage of the **left** amount (for example 1 means 1%). Hint: "Leave both amounts blank to skip amount matching. Percent is of the left amount." | Amount, 0 |

**Date window** (not shown for N : N)

| Control | What it does | Default |
|---|---|---|
| **Left date** / **Right date** | Optional date columns (real dates, date-times, or text that reads as a date). Leave both blank to skip date matching. Setting only one side is an error. | Blank |
| **Window (days)** | The largest allowed gap, in days, between the two dates (0 to 3,650). Hint: "Leave both dates blank to skip date matching." | 0 |

**Limits & output** (collapsed): "Up to 5,000,000 candidate pairs. The live preview uses the first 100 rows of each input; Run gives the full result."

#### What the outputs contain

`M` (matched). Columns, in order: `Match_ID`, `Match_Status`, `Amount_Diff` (only when amounts are set), `Date_Gap_Days` (only when dates are set), then every column of the left table, then every column of the right table. A right column with the same name as a left column gets `_right` added. Rows are ordered by `Match_ID`.

- `Match_ID` numbers the matches, starting at 1. In 1:N, N:1 and N:N, all rows of one group share an ID.
- `Match_Status` is `Matched` when no amounts are set, `Within tolerance` when the amounts agree, `Outside tolerance` when they do not. For 1:1, rows only become a match when the amounts agree, so you see `Within tolerance`. For 1:N, N:1 and N:N, rows are grouped by the keys and compared in total, so a group whose total is off still appears in `M`, marked `Outside tolerance`.
- `Amount_Diff` is always **right amount minus left amount** (for a group, the group totals).
- `Date_Gap_Days` is right date minus left date, in days.

`L` and `R` (unmatched). The original columns plus `Unmatched_Reason`, one of:

| Reason | Meaning |
|---|---|
| No candidate with the same key | No row on the other side has the same key(s). (With no key pairs, the wording is "No candidate within the date window".) |
| Candidates outside tolerance | Rows with the same key exist on the other side but none agrees within the amount tolerance or date window. |
| Candidates already matched | A better candidate was used by another row (1:1 and similar). |

`S` (summary), one row:

| Column | Meaning |
|---|---|
| `Match_Type` | The match type used (`one_to_one`, `one_to_many`, `many_to_one`, `many_to_many`). |
| `Left_Rows`, `Right_Rows` | Rows in each input. |
| `Matched_Groups` | Number of matches (distinct `Match_ID`). |
| `Left_Matched_Rows`, `Right_Matched_Rows` | Rows matched on each side. |
| `Left_Unmatched_Rows`, `Right_Unmatched_Rows` | Rows left over. |
| `Left_Match_Rate_Pct`, `Right_Match_Rate_Pct` | Matched rows as a percentage of rows. |
| `Left_Total`, `Right_Total` | Sum of the amount column on each side (only with amounts). |
| `Matched_Left_Total`, `Matched_Right_Total` | Sum of the matched rows on each side. |
| `Matched_Net_Difference` | Matched right total minus matched left total. |
| `Matched_Abs_Difference` | Sum of the absolute differences per match. |
| `Left_Unmatched_Total`, `Right_Unmatched_Total` | Amount in the unmatched rows. |
| `Net_Difference_Total` | `Right_Total` minus `Left_Total`. |
| `Within_Tolerance_Groups`, `Outside_Tolerance_Groups` | How many matches are inside / outside the tolerance. |

Without amounts the total and difference columns are empty (null).

### Worked example

Left, the ledger:

| Ref | Amount | Date |
|---|---|---|
| INV-1 | 100.00 | 2025-01-03 |
| INV-2 | 250.00 | 2025-01-04 |
| INV-3 | 75.00 | 2025-01-05 |
| INV-4 | 40.00 | 2025-01-09 |

Right, the bank:

| Ref | Amount | Date |
|---|---|---|
| inv-1 | 100.00 | 2025-01-03 |
| INV-2 (trailing space) | 250.00 | 2025-01-06 |
| INV-3 | 75.40 | 2025-01-05 |
| INV-9 | 10.00 | 2025-01-09 |

Settings: **Match type** 1 : 1; key pair `Ref` = `Ref`; **Left amount** and **Right amount** = `Amount`; **Tolerance** Amount, **Value** 0.50; **Left date** and **Right date** = `Date`; **Window (days)** 3.

Output `M`:

| Match_ID | Match_Status | Amount_Diff | Date_Gap_Days | Ref | Amount | Date | Ref_right | Amount_right | Date_right |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Within tolerance | 0.0 | 0 | INV-1 | 100.0 | 2025-01-03 | inv-1 | 100.0 | 2025-01-03 |
| 2 | Within tolerance | 0.0 | 2 | INV-2 | 250.0 | 2025-01-04 | INV-2 | 250.0 | 2025-01-06 |
| 3 | Within tolerance | 0.4 | 0 | INV-3 | 75.0 | 2025-01-05 | INV-3 | 75.4 | 2025-01-05 |

Case and spaces in the keys were ignored (`inv-1`, `INV-2 `). Output `L`:

| Ref | Amount | Date | Unmatched_Reason |
|---|---|---|---|
| INV-4 | 40.0 | 2025-01-09 | No candidate with the same key |

Output `R`:

| Ref | Amount | Date | Unmatched_Reason |
|---|---|---|---|
| INV-9 | 10.0 | 2025-01-09 | No candidate with the same key |

Output `S` (shown as a list for readability):

| Column | Value |
|---|---|
| Match_Type | one_to_one |
| Left_Rows / Right_Rows | 4 / 4 |
| Matched_Groups | 3 |
| Left_Matched_Rows / Right_Matched_Rows | 3 / 3 |
| Left_Unmatched_Rows / Right_Unmatched_Rows | 1 / 1 |
| Left_Match_Rate_Pct / Right_Match_Rate_Pct | 75.0 / 75.0 |
| Left_Total / Right_Total | 465.0 / 435.4 |
| Matched_Left_Total / Matched_Right_Total | 425.0 / 425.4 |
| Matched_Net_Difference | 0.4 |
| Matched_Abs_Difference | 0.4 |
| Left_Unmatched_Total / Right_Unmatched_Total | 40.0 / 10.0 |
| Net_Difference_Total | -29.6 |
| Within_Tolerance_Groups / Outside_Tolerance_Groups | 3 / 0 |

If you set **Value** to 0 and clear the dates, INV-3 (75.00 against 75.40) is no longer a match. It goes to `L` and `R` with the reason `Candidates outside tolerance`, and INV-4 and INV-9 keep `No candidate with the same key`.

A **1 : N** example. Left orders `O1` (300) and `O2` (50); right payments `O1` 100, `O1` 200, `O2` 45, key `Order`, amounts `Total` and `Paid`, **Tolerance** Percent 5. `M`:

| Match_ID | Match_Status | Amount_Diff | Order | Total | Order_right | Paid |
|---|---|---|---|---|---|---|
| 1 | Within tolerance | 0.0 | O1 | 300.0 | O1 | 100.0 |
| 1 | Within tolerance | 0.0 | O1 | 300.0 | O1 | 200.0 |
| 2 | Outside tolerance | -5.0 | O2 | 50.0 | O2 | 45.0 |

The two O1 payments add up to 300 and are one match with two rows. O2 is 5 short, which is 10% of 50, so it is listed as `Outside tolerance`.

### Edge cases and limits

- **Candidate pairs: up to 5,000,000.** Reconcile counts how many row pairs could possibly match before it starts. More than that stops with `TD-SHAPE-072`. Add key columns or narrow the date window.
- **Live preview:** 100 rows of each input; Run uses all rows and holds both inputs in memory. See [Live preview and Run](input-output.md#live-preview-and-run).
- **Keys** are converted to text, trimmed and lower-cased on both sides before comparing. `007` and `7` are different; `Inv-1 ` and `inv-1` are the same. There is no fuzziness: for that see [Fuzzy Match](#fuzzy-match).
- **Null keys never match.**
- **Amounts** may be number columns or text that holds numbers. Text amounts are read the way the Audit nodes read them: `1,234.50`, `1.234,50` (European) and `1,234` are 1234.5, 1234.5 and 1234; a single comma that is not a thousands group is a decimal comma (`1,50` is 1.5); `(12.00)` is negative; currency signs and spaces are ignored. A mixed or malformed form such as `1,2,3` is read as empty. Text that is not a number is treated as empty and cannot match when amounts are compared. Differences are compared after rounding to six decimals.
- **Date columns** may be dates, date-times or text. Text should be in a standard form such as `2025-01-31`; text that does not read as a date counts as empty. A date-time is reduced to its date.
- **Without key pairs** you can match on dates alone (choose a date pair and a window). Without keys and without dates the node refuses to run (`TD-SHAPE-071`).
- **N : N** ignores the date window (the date boxes are hidden) and compares groups of rows with the same key on each side by their totals.
- **Which pair wins in 1 : 1.** The pairs with the smallest amount difference, then the smallest date gap, are taken first; a row can only be used once. The result is the same each time you run it.
- **Ties** never depend on row order; the same inputs always give the same answer.

### Errors you may see

| Code | What it means | What to do |
|---|---|---|
| `TD-SHAPE-071` | "Add a key column pair or a date window". There is nothing to match on. | Add a key pair, or choose a date pair. |
| `TD-SHAPE-070` | "Pick the amount/date column on both sides". Only one side is set. | Pick it on both sides, or on neither. |
| `TD-SHAPE-072` | More than 5,000,000 possible matches. | Add key columns or narrow the date window. |
| `TD-SHAPE-003` | A chosen column is no longer in the input. | Select the column again. |
| `TD-SHAPE-004` | A setting is unknown or out of range (negative tolerance or window). | Pick a value inside the allowed range. |
| `TD-SHAPE-050` | A date column is neither a date nor text (for example numbers). | Choose a date column, or convert the column first. |
| `TD-SHAPE-005` | An input has no data. | Connect and fix the upstream node. |

### Tips

- Start with a tolerance of 0 and no dates to see what matches exactly; then widen the tolerance a little at a time and watch `Matched_Abs_Difference` and `Outside_Tolerance_Groups` in `S`.
- The summary `S` is the number to put in the working paper: left total, right total, unmatched totals and the net difference all come from one place.
- Check `Unmatched_Reason`. "Candidates outside tolerance" means the reference exists on both sides but the amount or date disagrees, which is usually the finding. "No candidate with the same key" means the item is missing on the other side.
- For many-to-one cases (one bank deposit for several invoices) choose N : 1 and give amounts so that totals are compared.

---

## Fuzzy Match

<img src="../../../src/trigger_designer/resources/qt/images/node_icons/Join/FuzzyMatch.svg" width="56" alt="Fuzzy Match icon">

### Contents

[Purpose](#purpose-4) | [When to use it](#when-to-use-it-4) | [Inputs and outputs](#inputs-and-outputs-4) | [Settings](#settings-4) | [Worked example](#worked-example-4) | [Edge cases and limits](#edge-cases-and-limits-4) | [Errors you may see](#errors-you-may-see-3) | [Tips](#tips-4)

### Purpose

Fuzzy Match pairs rows whose text is similar but not identical: `Acme Inc.` and `ACME, Inc`, `Initech LLC` and `Initec`. Each pair gets a score between 0 and 1 (1 is identical), and only pairs at or above your minimum are kept.

### When to use it

- Vendor names typed differently in two systems (vendor master to payments).
- Employee names, customer names, addresses and descriptions where an exact [Join](#join) misses real matches.

Use [Join](#join) or [Reconcile](#reconcile) when the key is exact. Fuzzy results are suggestions: review them.

### Inputs and outputs

| Socket | Carries |
|---|---|
| Input 1 (left) | The first list. |
| Input 2 (right) | The second list. |
| Output `M` | **Matched.** `Match_ID`, `Match_Score`, then every left column, then every right column (a right column with the same name as a left column gets `_right`). |
| Output `L` | **Left unmatched.** Left rows with no pair at or above the minimum score (and rows with empty text). |
| Output `R` | **Right unmatched.** The same for the right. |

### Settings

**Compare**

| Control | What it does | Default |
|---|---|---|
| **Left text** / **Right text** | The text columns to compare. Only text columns are listed. | Empty |
| **Algorithm** | **Jaro-Winkler**: gives extra credit to names that start the same way; good for names. **Levenshtein ratio**: counts the single-character edits between the texts; good for codes and descriptions. | Jaro-Winkler |
| **Minimum score** | Pairs scoring below this are dropped. 0.01 to 1.0 in steps of 0.01. Hint: "1.0 is identical; pairs scoring below are dropped." | 0.85 |
| **Ignore Inc/Ltd/LLC** (checkbox) | Removes company-form words before comparing: inc, incorporated, ltd, limited, llc, plc, corp, corporation, co, company, gmbh, ag, sa, pty, pvt, bv, nv, lp, llp. | On |
| **Pairs** | **One to one**: each row is used at most once; the best-scoring pairs win. **Best per left row**: each left row gets its best right row (a right row can be used several times). **All pairs**: every pair at or above the minimum. | One to one |

Hint on the form: "Text is lower-cased and punctuation is ignored before comparing. Empty text never matches."

**Speed**

| Control | What it does | Default |
|---|---|---|
| **Block on** | Only rows that share a "block" are compared, which keeps large inputs fast. **First characters**: rows must start with the same first few letters. **First word**: rows must share the first word. **Nothing (small data)**: compare everything with everything. | First characters |
| **Characters** | How many leading characters count for the block (1 to 10). Shown for First characters. | 3 |
| **Must also match** (list, up to 5) | Extra column pairs (a **Left column** and a **Right column**) that must be equal, for example country or city. Trimmed and compared as lower-case text. | Empty |

Hint: "Only rows that share the block are compared, which keeps large inputs fast. Extra columns are trimmed and compared as lower-case text."

**Limits & output** (collapsed): "Up to 5,000,000 candidate pairs (1,000,000 with no blocking). The live preview uses the first 100 rows of each input; Run gives the full result."

How text is prepared before scoring: lower-case; every character that is not a letter or digit becomes a space; the company words above are removed (if the checkbox is on); repeated spaces are collapsed. So `ACME, Inc` and `Acme Inc.` both become `acme`.

### Worked example

Left (vendor master):

| Vendor | Spend |
|---|---|
| Acme Inc. | 100 |
| Globex Corporation | 200 |
| Initech LLC | 300 |
| Umbrella Ltd | 400 |

Right (suppliers):

| Supplier | Country |
|---|---|
| ACME, Inc | US |
| Globex Corp | DE |
| Initec | US |
| Wayne Enterprises | UK |

Settings: **Left text** `Vendor`, **Right text** `Supplier`, defaults otherwise. Output `M`:

| Match_ID | Match_Score | Vendor | Spend | Supplier | Country |
|---|---|---|---|---|---|
| 1 | 1.0 | Acme Inc. | 100 | ACME, Inc | US |
| 2 | 1.0 | Globex Corporation | 200 | Globex Corp | DE |
| 3 | 0.9714 | Initech LLC | 300 | Initec | US |

Output `L`:

| Vendor | Spend |
|---|---|
| Umbrella Ltd | 400 |

Output `R`:

| Supplier | Country |
|---|---|
| Wayne Enterprises | UK |

With **Algorithm** Levenshtein ratio, the third pair scores 0.8571 instead of 0.9714.

### Edge cases and limits

- **Candidate pairs: up to 5,000,000** (1,000,000 with **Block on** = Nothing). More stops the run. The count is made before any scoring, so it fails fast.
- **Live preview:** 100 rows of each input. Run uses all rows and keeps both inputs in memory. See [Live preview and Run](input-output.md#live-preview-and-run).
- **Blocking can hide real matches.** With First characters = 3, `The Acme Trading Co` and `Acme Trading Company` are never compared (they start with `the` and `acm`). Use First word, shorten Characters, remove leading words first, or use Nothing on a small table. With Nothing and a minimum of 0.7, that pair is found, with a score of 0.8333.
- **Must also match** is exact (after trimming and lower-casing). A wrong spelling in the extra column also hides a match.
- **Empty text** (null or only spaces and punctuation) never matches and the row goes to `L` or `R`.
- **Only text columns** can be chosen. Convert numbers to text with a Select node first.
- **Ties** are broken the same way every time (higher score first, then row order), so a re-run gives the same result.
- **Score** is rounded to four decimals.
- **Column names.** `Match_ID` and `Match_Score` are reserved: a left column with one of those names is renamed with a `_2` suffix.

### Errors you may see

| Code | What it means | What to do |
|---|---|---|
| `TD-SHAPE-001` | "Pick the text column on both sides". | Choose **Left text** and **Right text**. |
| `TD-SHAPE-004` | A setting is out of range (Minimum score must be above 0 and at most 1; Characters 1 to 10; at most 5 extra match columns). | Pick a value inside the range. |
| `TD-SHAPE-081` | More than 5,000,000 possible pairs. | Use more Characters, or add a **Must also match** column. |
| `TD-SHAPE-082` | **Block on** is Nothing and the tables have more than 1,000,000 row pairs (for example 1,001 by 1,000). | Turn on prefix or first-word blocking. |
| `TD-SHAPE-003` | A chosen column is no longer in the input. | Select the column again. |
| `TD-SHAPE-005` | An input has no data. | Connect and fix the upstream node. |

### Tips

- Start at the default 0.85 and read `M` sorted by `Match_Score`. Look at the lowest scores: that is where wrong matches live. Raise the minimum until the lowest rows are right, then look at `L` and `R` for real names that were missed.
- Add a **Must also match** column (country, tax number, city) to cut false matches and make large runs faster.
- Names with a leading "The" or a title defeat prefix blocking. Use First word, or strip those words with a Find and Replace node first.
- After matching, use the pairs in `M` as a mapping table and Join on `Match_ID`, or keep the pair list as evidence in your working paper.
