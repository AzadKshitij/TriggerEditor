# Reconcile

![Reconcile icon](../../assets/node_icons/Join/Reconcile.svg){ .node-icon }

## Purpose

Reconcile compares two lists (for example the bank statement and the ledger) the way an auditor does: match on reference keys, check that the amounts agree within a tolerance, check that the dates are close enough, and then tell you what matched, what is left over on each side and how much the totals differ. It gives four outputs, including a one-row summary you can quote.

## When to use it

- Bank to ledger, sub-ledger to general ledger, invoices to payments, purchase orders to receipts.
- The two sides do not agree to the cent, or the dates differ by a few days.
- One side may have several lines for one line on the other (one invoice paid in instalments).

## Inputs and outputs

| Socket | Carries |
|---|---|
| Input 1 (left) | The first list (for example the ledger). |
| Input 2 (right) | The second list (for example the bank). |
| Output `M` | **Matched.** One row per matched pair (or per line in a group), with the left columns followed by the right columns, preceded by `Match_ID`, `Match_Status` and the differences. |
| Output `L` | **Left unmatched.** Left rows with no match, plus `Unmatched_Reason`. |
| Output `R` | **Right unmatched.** Right rows with no match, plus `Unmatched_Reason`. |
| Output `S` | **Summary.** One row with counts, totals and the net difference. |

## Settings

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

### What the outputs contain

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

## Worked example

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

## Edge cases and limits

- **Candidate pairs: up to 5,000,000.** Reconcile counts how many row pairs could possibly match before it starts. More than that stops with `TD-SHAPE-072`. Add key column pairs or narrow the date window.
- **Live preview:** 100 rows of each input; Run uses all rows and holds both inputs in memory. See [Live preview and Run](../input-output/index.md#live-preview-and-run).
- **Keys** are converted to text, trimmed and lower-cased on both sides before comparing. `007` and `7` are different; `Inv-1 ` and `inv-1` are the same. There is no fuzziness: for that see [Fuzzy Match](fuzzy-match.md).
- **Null keys never match.**
- **Amounts** may be number columns or text that holds numbers. Text amounts are read the way the Audit nodes read them: `1,234.50`, `1.234,50` (European) and `1,234` are 1234.5, 1234.5 and 1234; a single comma that is not a thousands group is a decimal comma (`1,50` is 1.5); `(12.00)` is negative; currency signs and spaces are ignored. A mixed or malformed form such as `1,2,3` is read as empty. Text that is not a number is treated as empty and cannot match when amounts are compared. Differences are compared after rounding to six decimals.
- **Date columns** may be dates, date-times or text. Text should be in a standard form such as `2025-01-31`; text that does not read as a date counts as empty. A date-time is reduced to its date.
- **Without key pairs** you can match on dates alone (choose a date pair and a window). Without keys and without dates the node refuses to run (`TD-SHAPE-071`).
- **N : N** ignores the date window (the date boxes are hidden) and compares groups of rows with the same key on each side by their totals.
- **Which pair wins in 1 : 1.** The pairs with the smallest amount difference, then the smallest date gap, are taken first; a row can only be used once. The result is the same each time you run it.
- **Ties** never depend on row order; the same inputs always give the same answer.

## Errors you may see

| Code | What it means | What to do |
|---|---|---|
| `TD-SHAPE-071` | "Add a key column pair or a date window". There is nothing to match on. | Add a key pair, or choose a date pair. |
| `TD-SHAPE-070` | "Pick the amount/date column on both sides". Only one side is set. | Pick it on both sides, or on neither. |
| `TD-SHAPE-072` | More than 5,000,000 possible matches. | Add key column pairs or narrow the date window. |
| `TD-SHAPE-003` | A chosen column is no longer in the input. | Select the column again. |
| `TD-SHAPE-004` | A setting is unknown or out of range (negative tolerance or window). | Pick a value inside the allowed range. |
| `TD-SHAPE-050` | A date column is neither a date nor text (for example numbers). | Choose a date column, or convert the column first. |
| `TD-SHAPE-005` | An input has no data. | Connect and fix the upstream node. |

## Tips

- Start with a tolerance of 0 and no dates to see what matches exactly; then widen the tolerance a little at a time and watch `Matched_Abs_Difference` and `Outside_Tolerance_Groups` in `S`.
- The summary `S` is the number to put in the working paper: left total, right total, unmatched totals and the net difference all come from one place.
- Check `Unmatched_Reason`. "Candidates outside tolerance" means the reference exists on both sides but the amount or date disagrees, which is usually the finding. "No candidate with the same key" means the item is missing on the other side.
- For many-to-one cases (one bank deposit for several invoices) choose N : 1 and give amounts so that totals are compared.


Back to the [Join node index](index.md).
