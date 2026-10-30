# Audit nodes: how to use them

The **Audit** tab in the node palette (and the *Audit* group in the `Shift+A` menu) holds five
tests that auditors run on ledgers and transaction lists. Each test splits the incoming rows into
the ones that **tripped the test** and the rest, and produces a one-row **Summary** that says what
was tested, how many rows were in scope, how many were flagged, and whether the test passed.

| Icon | Node | Question it answers | Outputs |
|---|---|---|---|
| ![Duplicates](../../src/trigger_designer/resources/qt/images/node_icons/Audit/Duplicates.svg) | **Duplicates** | Which rows repeat, exactly or nearly? | `D` Duplicates, `U` Unique, `S` Summary |
| ![Gaps](../../src/trigger_designer/resources/qt/images/node_icons/Audit/Gaps.svg) | **Gaps** | Which numbers or days are missing from a sequence? | `G` Gaps, `S` Summary |
| ![Benford](../../src/trigger_designer/resources/qt/images/node_icons/Audit/Benford.svg) | **Benford** | Do the leading digits of an amount column look natural? | `T` Table, `S` Summary, `D` Drill-down |
| ![Sample](../../src/trigger_designer/resources/qt/images/node_icons/Audit/Sample.svg) | **Sample** | Draw a reproducible sample. | `S` Sample, `N` Not sampled, `L` Selection log |
| ![Risk Filters](../../src/trigger_designer/resources/qt/images/node_icons/Audit/Risk%20Filters.svg) | **Risk Filters** | Which entries trip classic risk indicators? | `F` Flagged, `N` Not flagged, `S` Summary |

All five icons are amber, the colour of the Audit family. Preview: [audit_icons_preview.png](../assets/audit_icons_preview.png).

## Common to every audit node

**Wiring.** Connect one table into the node's input. Connect any output to a *File Output*, a
*Data Profile*, or another node. Unwired audit nodes do nothing and never fail a Run.

**Reading the result.** Click the node, then look at the **Result** line at the bottom of the Config
Dock. The node does not count exceptions while you edit, because that would slow big files down. Press the
**Count** (refresh) button beside the Result line to count them. Click an output socket's data in the
Data Preview dock to see the rows.

**The Summary table.** Every Summary has the same first columns, so you can stack summaries from
several tests with *Union*:

| Column | Meaning |
|---|---|
| `test_name`, `criteria` | What ran, in one sentence of plain language |
| `parameters` | The settings as JSON, so the test can be repeated exactly |
| `status` | `pass`, `warn` or `fail` |
| `code`, `message` | A `TD-AUDIT-1xx` warning code and the outcome in a sentence |
| `population_rows`, `population_value` | Rows in scope, and their gross value (sum of absolute amounts) |
| `exception_rows`, `exception_value`, `exception_rate` | The flagged rows, their gross value and share |

Gross value is used on purpose: debits and credits cancel in a net sum and would hide exposure.

**Errors.** A mistake in the settings stops the node with a plain sentence, for example *"Choose the
amount column."* The code in brackets (`TD-AUDIT-001` to `010`) is also listed in the Problems dock. An
unreadable amount or date does not stop the test: those values are skipped, the status becomes
`warn`, and the message says how many were skipped.

**Undo.** Every setting change is one undo step, and typing in a text box counts as one step.

**Amounts and dates.** Amounts stored as text are cleaned first: `(1,234.50)` is read as -1234.5, and `$`,
`£`, `€` and thousands commas are removed. Dates may be real dates or text in one of the five formats the
node offers (`YYYY-MM-DD`, `DD/MM/YYYY`, `MM/DD/YYYY`, `DD-MM-YYYY`, `YYYYMMDD`).

> Decimal commas: `1.234,50`, `1 234,50`, `1'234,50` and `1234,5` are read as European amounts, and
> `1,234.50`, `(1,234.50)`, `$5` and `-1,234` keep their US/UK meaning. A lone comma followed by exactly
> three digits (`1,234`) is read as a thousands separator. Mixed or malformed forms (`1.234.567`,
> `1,2,3`) are treated as unreadable, so the "could not be read" warning (TD-AUDIT-102) appears
> instead of silently wrong numbers.

---

## Duplicates

Finds rows that repeat.

1. **Match on**: tick the columns that together identify a duplicate (for example `vendor` and
   `invoice_no`). `All` / `None` tick or clear every column.
2. Optional: **Trim spaces** and **Ignore case**, so `"ACME "` and `"acme"` match.
3. **Match type**
   - *Exact*: every ticked column equal.
   - *Near*: the ticked columns match exactly, and in addition the **amount** differs by no more than
     a tolerance (a fixed amount or a percent), and optionally the **date** is within N days.
4. Read the result: `D` has every row that belongs to a duplicate group, with a group id and the size
   of the group. `U` has the rows that are unique. `S` is the Summary.

Typical use: pick `vendor`, `invoice_no`, `amount`, exact match, to find invoices paid twice. Then switch
to *Near* with a small tolerance to find the same invoice keyed with a typo.

## Gaps

Finds what is missing from a sequence, such as cheque or journal numbers, or days without entries.

1. **Sequence**: choose the column holding the number (`JE-000123` works: the text prefix and the
   zero padding are kept).
2. **Group by**: optional. Check each series separately, for example one per ledger or branch.
3. **Also report**: tick *repeated* numbers and numbers *out of order* as well as missing ones.
4. **Expected range**: optionally say the series should start and end at given numbers, so a gap at
   the very start or end is reported too.
5. **Dates**: optionally pick a date column to find calendar days with no entries. *Skip weekends*
   removes Saturdays and Sundays, and a **Holidays** list (one `YYYY-MM-DD` per line) removes those days.
6. Read the result: `G` has one row per finding (a missing range such as `1000..1009`, a repeated
   number, or an out-of-order row) with its size. `S` counts them.

## Benford

Tests whether the leading digits of an amount column follow Benford's law. Large departures can point
to invented, rounded or manipulated numbers. It is a prompt for questions, not proof of fraud.

1. **Amount**: choose the column. The sign is dropped, and amounts smaller than the minimum (default 10, a
   setting in the dock) are not tested, because tiny amounts distort the leading digits.
2. **Digits**: *first digit* (1 to 9) or *first two digits* (10 to 99).
3. Read the **chart** in the Config Dock: bars show the share of rows per digit and the line shows the
   share Benford predicts. Digits flagged as out of line are drawn in the danger colour.
4. **Drill-down**: leave it on *auto* to get the rows behind the flagged digits, or list digits yourself.
5. Outputs: `T` is the observed-against-expected table, `S` the verdict (`pass` / `warn` / `fail`) with the
   average deviation (MAD) and a chi-square p-value, and `D` the rows for the drill-down digits.

At least 100 tested rows are needed for *first digit* and 1,000 for *first two digits*; with fewer, the node
warns (`TD-AUDIT-101`) that the result is indicative only. While you edit, File Input passes only 100 rows to the editor, so that warning often shows.
Run on the full file for the real result.

## Sample

Draws a sample that someone else can re-perform and get the same rows.

1. **Method**
   - *Random*: every row has an equal chance.
   - *Systematic*: every n-th row from a random start.
   - *Monetary unit (MUS)*: larger amounts are more likely to be picked. Needs an **Amount** column.
   - *Stratified*: split by amount bands and draw a set number from each band.
2. **Size**: a count or a percent. If you ask for more rows than exist, the whole population is
   selected and the log says so (`TD-AUDIT-103`).
3. **Seed**: a number. The same seed and the same data always give the same sample, on any
   machine and any version of the app. Change the seed to draw a different sample.
4. **Stable key** (optional): the columns that identify a row. The draw is based on these, so a re-sorted
   file still gives the same sample.
5. Outputs: `S` the sample, `N` everything not sampled, `L` the **selection log**: method, seed, size,
   and for each selected row why it was picked. Keep `L` in the workpaper so a reviewer can redo the draw.

While you edit, a population over 200,000 rows is not sampled on the canvas. The Result line says the
sample is drawn when you Run. Run always draws.

## Risk Filters

Runs several classic journal-entry red flags at once and tells you which rows tripped which test.

There are seven tests. Each has an **Enabled** switch, its own settings and a **weight**. Switch on at
least one.

| Test | Flags an entry that was... |
|---|---|
| Weekend posting | posted on a Saturday or Sunday |
| Public-holiday posting | posted on a date in your Holidays list |
| Round amount | a multiple of a round number you set |
| Just below approval limit | within a margin under a limit you set |
| Keyword in description | described with one of your keywords |
| Posted after period end | dated after the **Period end** you type (or effective-dated after it) |
| Manual journal | marked manual in a column you choose |

1. Switch on the tests you need and fill in their settings.
2. Read the result: `F` has the flagged rows with a `risk_score` (sum of the weights of the tests tripped)
   and a `risk_tests` column naming them. `N` has the rest. `S` counts rows per test, and how many rows
   tripped two or more.

A row tripping several tests is usually worth more attention than one tripping a single test.

---

## A worked example

1. Add a **File Input** and pick your ledger CSV.
2. Add **Duplicates**, **Gaps** and **Risk Filters** and connect the File Input to each.
3. Set each node's columns and press its **Count** button to see how many rows it flags.
4. Add a **Union** node and connect the three `S` Summary outputs into it: you get one table with a row
   per test.
5. Connect the Union and the flagged outputs you want to keep to **File Output** nodes and Run.

## Where these live in the code

Calculation (no UI) in `src/trigger_designer/core/audit/`; node and dock in
`src/trigger_designer/qt/widgets/nodes/Audit/`; icons in
`src/trigger_designer/resources/qt/images/node_icons/Audit/`, registered in
`src/trigger_designer/qt/resources.json` as `node_duplicates`, `node_gaps`, `node_benford`,
`node_sample` and `node_risk_filters`.
