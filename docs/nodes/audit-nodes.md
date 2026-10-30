# Audit nodes: how to use them

The **Audit** tab in the node palette (and the *Audit* group in the `Shift+A` menu) holds five
tests that auditors run on ledgers and transaction lists. Each test splits the incoming rows into
the ones that **tripped the test** and the rest, and produces a one-row **Summary** that says what
was tested, how many rows were in scope, how many were flagged, and whether the test passed.
(Sample is the exception: its third output is a *Selection log*, see below.)

| Icon | Node | Question it answers | Outputs |
|---|---|---|---|
| ![Duplicates](../../src/trigger_designer/resources/qt/images/node_icons/Audit/Duplicates.svg) | **Duplicates** | Which rows repeat, exactly or nearly? | `D` Duplicates, `U` Unique, `S` Summary |
| ![Gaps](../../src/trigger_designer/resources/qt/images/node_icons/Audit/Gaps.svg) | **Gaps** | Which numbers or days are missing from a sequence? | `G` Gaps, `S` Summary |
| ![Benford](../../src/trigger_designer/resources/qt/images/node_icons/Audit/Benford.svg) | **Benford** | Do the leading digits of an amount column look natural? | `T` Table, `S` Summary, `D` Drill-down |
| ![Sample](../../src/trigger_designer/resources/qt/images/node_icons/Audit/Sample.svg) | **Sample** | Draw a reproducible sample. | `S` Sample, `N` Not sampled, `L` Selection log |
| ![Risk Filters](../../src/trigger_designer/resources/qt/images/node_icons/Audit/Risk%20Filters.svg) | **Risk Filters** | Which entries trip classic risk indicators? | `F` Flagged, `N` Not flagged, `S` Summary |

All five icons are amber, the colour of the Audit family. Preview: [audit_icons_preview.png](../assets/audit_icons_preview.png).

<!-- workpaper: see ../workpaper.md -->

## Common to every audit node

**Wiring.** Connect one table into the node's single input. The sockets are labelled with the
letters in the table above. Connect any output to a *File Output*, a *Data Profile*, or another
node. A node whose input is not connected shows "Input has no data" in its tooltip and passes nothing on.

**Live preview versus Run.** While you edit, upstream nodes (File Input and the Transform and
Preparation nodes) pass only the first 100 rows of each table, so every audit node tests that small
sample and the numbers you see are a preview. Press **Run** and every audit node tests all rows.
Benford and Sample have their own limits, noted in their sections. The Data Preview dock labels a
table *evaluated · not run* (preview) or *from Run*. Details: [Live preview versus Run](../guide/nodes/README.md#live-preview-versus-run).

**Settings apply at once.** Unlike the Transform and Preparation nodes, an audit node re-tests as soon
as you change a setting (typing in a text box is applied after about a third of a second). There is no
"click away to apply" step.

**Reading the result.** Click the node, then look at the **Result** section at the bottom of the Config Dock.

- *Duplicates, Gaps and Risk Filters* do not count exceptions while you edit, because counting reads
  every row. The Result line says "Not counted yet. Use the refresh button to count." Press the
  **refresh icon** (tooltip "Count exceptions now") beside the Result line. Any setting change
  clears the count again.
- *Benford and Sample* show their result straight away and have no refresh button. Benford also draws a
  chart.
- Click an output socket's data in the Data Preview dock to see the rows.

A counted Result line reads `STATUS: message`, for example `FAIL: 4 of 6 rows are in 2 duplicate groups.`

**The Summary table.** Every Summary (Duplicates, Gaps, Benford, Risk Filters) has the same first eleven
columns, so you can stack summaries from several tests with *Union*:

| Column | Meaning |
|---|---|
| `test_name`, `criteria` | What ran, and the rule in one sentence of plain language |
| `parameters` | The settings as JSON, so the test can be repeated exactly |
| `status` | `pass`, `warn` or `fail` (see the table below) |
| `code`, `message` | A `TD-AUDIT-1xx` warning code (blank when none) and the outcome in a sentence |
| `population_rows`, `population_value` | Rows in scope, and their gross value (sum of absolute amounts); blank when the test has no amount |
| `exception_rows`, `exception_value`, `exception_rate` | The flagged rows, their gross value and their share of the population |

After these eleven columns each test adds its own facts (listed in its section).

Gross value is used on purpose: debits and credits cancel in a net sum and would hide exposure.

| Status | Used by | Meaning |
|---|---|---|
| `pass` | all | Nothing flagged (and nothing skipped) |
| `warn` | all | Risk Filters: something was flagged (indicators are not misstatements). Others: the result is indicative only, or some values were skipped, or Benford is only marginally acceptable |
| `fail` | Duplicates, Gaps, Benford | Duplicates or gaps were found, or the leading digits are nonconforming |

**Errors versus warnings.** A mistake in the settings stops the node with a plain sentence, for example
*"Choose the amount column."* The node turns red and the message, a hint and its code appear in the
Problems dock. Unreadable amounts or dates do **not** stop a test: those values are skipped, the status
is raised to at least `warn` and the message says how many were skipped.

| Code | Stops the node? | Meaning and fix |
|---|---|---|
| `TD-AUDIT-001` | yes | A required column is not chosen ("Choose the amount column."). Pick it. |
| `TD-AUDIT-002` | yes | The chosen column is no longer in the input (renamed upstream). Pick it again. |
| `TD-AUDIT-003` | yes | The column holds nested values (lists or structs). Choose a plain text, number or date column. |
| `TD-AUDIT-004` | yes | A number or option is outside its range ("Tolerance must be 0 or more."), also a bad holiday date in Gaps and an empty keyword list in Risk Filters. |
| `TD-AUDIT-005` | yes | The input already has a column that the node adds (for example `dup_group_id`, `risk_score`, `sample_seq`). Rename it first. |
| `TD-AUDIT-006` | yes | Risk Filters: a date you typed is not `YYYY-MM-DD`. |
| `TD-AUDIT-007` | yes | The date format is not one of the five offered. |
| `TD-AUDIT-008` | yes | Risk Filters: no test is switched on. |
| `TD-AUDIT-009` | yes | Sample (stratified): the edges or sizes list is wrong (count or order). |
| `TD-AUDIT-010` | yes | Sample (monetary unit or stratified): no row has a readable amount. |
| `TD-AUDIT-101` | no (warning) | Benford: too few rows were tested for a reliable result. |
| `TD-AUDIT-102` | no (warning) | Some amounts or dates could not be read and were skipped. Clean them or convert the column with a Select node. |
| `TD-AUDIT-103` | no (warning) | Sample: more rows were requested than exist; the whole population was selected. |

**Undo.** Every setting change is one undo step, and typing in a text box counts as one step.

**Amounts and dates.** Amounts stored as text are cleaned first, then read as numbers. Whitespace, `$`,
`£`, `€` and the apostrophes used as group separators are removed, and `(x)` means `-x`. Dates may be real dates
or text in one of five formats. Their labels in the dock are the format codes `%Y-%m-%d`, `%d/%m/%Y`,
`%m/%d/%Y`, `%d-%m-%Y` and `%Y%m%d` (Risk Filters shows them as friendly examples such as
`31/03/2024 (day/month/year)`). A time after the date (`2024-03-02 14:05:00`) is ignored.

How a text amount is read (verified against the code; the same reader is used by all five tests):

| Text in the cell | Read as | Rule |
|---|---|---|
| `1,234.50` and `1,234,567.89` | 1234.5 and 1234567.89 | Comma and point both present: the last one is the decimal mark |
| `(1,234.50)` | -1234.5 | Brackets mean negative |
| `$5`, `£1,000.00` | 5 and 1000 | Currency symbols are removed |
| `-1,234` and `1,234` | -1234 and 1234 | A lone comma followed by exactly three digits is a thousands separator |
| `1.234,50`, `1 234,50`, `1'234,50` | 1234.5 | European forms: the comma is the decimal mark |
| `1234,5`, `12,50`, `0,123` | 1234.5, 12.5, 0.123 | Any other single comma is a decimal comma |
| `1.5` and `1.234` | 1.5 and 1.234 | A lone point is always a decimal point, so `1.234` is **not** 1234 |
| `1.234.567`, `1,2,3`, `abc` | unreadable | Mixed or malformed forms are skipped (TD-AUDIT-102 warning) instead of producing wrong digits |

A single comma followed by exactly three digits is always read as a thousands separator, so `1,234` is
one thousand two hundred thirty-four, even in a file that means 1.234. If your file uses decimal commas, check the
Summary's `population_value` against a control total.

**Audit trail.** Each test is also a record for the run history. After a Run, the Summary (for Sample,
the Selection log) is turned into a *test summary*: test id (`audit.duplicates#<node id>`), name,
`status`, `population_rows`, `exception_rows`, `exception_rate`, `population_value`, `exception_value`,
`criteria`, `parameters`, `message`, the warning `code` and the node's extra facts (for example
`groups`, `mad`, `n_weekend`). The Run recorder stores it in that node's entry of the run record
(`test_summary`), next to the node's settings, its input and output row counts and the Sample seed.
A node that failed has no test summary. Recording is on by default (*Preferences > Record every run*) and
the record is saved beside the workflow; the Run History dock lists the runs. Today the dock shows
each node's status, row counts and errors; the test results themselves live in the saved record
and in the Excel workpaper. A preview (live) result is never recorded, only a Run.
<!-- workpaper: see ../workpaper.md -->

---

## Duplicates

Finds rows that repeat.

**Sockets.** One input. Outputs `D` Duplicates, `U` Unique, `S` Summary.

**Settings, in dock order** (defaults in brackets):

| Section | Label | Default | Effect |
|---|---|---|---|
| Match on | column list with `All` / `None` | none ticked | The columns that together identify a duplicate (for example `vendor` and `invoice_no`). At least one is required (TD-AUDIT-001). |
| Match on | **Trim spaces** | on | Ignore spaces before and after text, so `"ACME "` and `"ACME"` match. |
| Match on | **Ignore case** | off | Treat `acme` and `ACME` as equal. |
| Match type | **Exact** / **Near** | Exact | *Exact*: every ticked column equal. *Near*: the ticked columns equal **and** the amount and/or the date are close. |
| Near match (Near only) | **Amount** | blank | Column compared with a tolerance. |
| Near match | **Tolerance** and **Amount** / **Percent** | 0, Amount | How far apart two amounts may be. *Amount*: a fixed difference. *Percent*: a percent of the larger absolute amount. |
| Near match | **Date** | blank | Column compared with a window. |
| Near match | **Window** | 0 days | How many days apart two dates may be (0 to 3660). |
| Near match | **Date format** | `%Y-%m-%d` | How text dates are written. Ignored for real date columns. |
| Value | **Value** | blank | Optional column whose absolute values are totalled in the Summary (`population_value`, `exception_value`). Near mode falls back to the Amount column. With neither, the values stay blank. |

Near needs at least the Amount or the Date column (TD-AUDIT-001 otherwise). If both are set, a row must
satisfy both. Near matching also groups rows linked through a chain of close neighbours (A close to B,
B close to C puts all three in one group), as the tooltip on the Near button says.

**Outputs.**

- `D` Duplicates: every row of every group of two or more, with all the input columns plus
  `dup_group_id` (1, 2, ... in order of first appearance) and `dup_count` (rows in that group).
- `U` Unique: all the other rows, input columns only, in input order. A row with an empty key cell, or
  with an unreadable amount or date in Near mode, can never be a duplicate and lands here.
- `S` Summary: the eleven standard columns plus `groups` (duplicate groups), `skipped_rows` (rows that
  could not be compared) and `unparseable_rows` (unreadable amount or date cells). Status is `fail`
  when any duplicate exists, otherwise `pass` (`warn` if values were skipped).

**Worked example.** Exact match on `vendor` and `invoice_no`, Trim on, Ignore case on. Input (6 rows):

| vendor | invoice_no | amount | date |
|---|---|---|---|
| Acme | INV-1 | 1,200.00 | 2025-01-03 |
| ACME␠ | INV-1 | 1,200.00 | 2025-01-03 |
| Beta | INV-2 | 350.00 | 2025-01-04 |
| Acme | INV-3 | 1,200.00 | 2025-01-05 |
| Gamma | INV-4 | 80.00 | 2025-01-05 |
| Beta | INV-2 | 350.00 | 2025-01-04 |

(`␠` marks a trailing space.) `D` holds four rows: both `INV-1` rows with `dup_group_id` 1 and
`dup_count` 2, and both `INV-2` rows with `dup_group_id` 2 and `dup_count` 2. `U` holds `INV-3` and
`INV-4`. `S` says `fail`, "4 of 6 rows are in 2 duplicate groups.", `groups` 2, `exception_rate` 0.667.
Switch **Ignore case** off and **Trim spaces** off and only the `INV-2` pair remains (1 group, 2 rows).

Near example: key `vendor`, Near, Amount `amount` with tolerance 1.00, Date `date` with a window of
3 days. Acme rows at 1000.00 on 2025-01-03 and 1000.50 on 2025-01-05 form one group, while Acme's
1200.00 on 2025-01-04 (200 apart) and Beta's 1000.00 do not. With *Value* left blank the Summary
reports `population_value` 4200.5 and `exception_value` 2000.5 (the amount column is used).

Typical use: pick `vendor`, `invoice_no`, `amount`, exact match, to find invoices paid twice. Then
switch to *Near* with a small tolerance to find the same invoice keyed with a typo.

## Gaps

Finds what is missing from a sequence, such as cheque or journal numbers, or days without entries.

**Sockets.** One input. Outputs `G` Gaps (the findings) and `S` Summary.

**Settings, in dock order:**

| Section | Label | Default | Effect |
|---|---|---|---|
| Sequence | **Column** | none | The column holding the numbers (or, for Date, the dates). Required. |
| Sequence | **Type** | Prefixed | *Number*: whole numbers (`1042`, `1042.0`). *Prefixed*: text then digits, such as `JE-000123`; the series is the prefix. *Date*: calendar days with no entry. |
| Group by | column list with `All` / `None` | none | Check each series separately, for example one per ledger or branch. |
| Also report (not Date) | **Repeated numbers** | on | Report a number that appears more than once. |
| Also report (not Date) | **Numbers out of order** | on | Report a number lower than a higher one seen earlier in the same series. This depends on the order the rows arrive in. |
| Expected range (not Date) | **First** / **Last** | blank ("Lowest seen" / "Highest seen") | The first and last number you expect, so a gap at the very start or end is reported too. Last may not be below First (TD-AUDIT-004). |
| Dates (Date only) | **Format** | `%Y-%m-%d` | How text dates are written. |
| Dates | **Smallest gap** | 1 day | Ignore gaps shorter than this many days (1 to 3660). |
| Dates | **Skip weekends** | off | Saturdays and Sundays are not expected, so they do not count as missing. |
| Dates | **Holidays** | empty | One date per line, `YYYY-MM-DD`; shown only when *Skip weekends* is on. A bad line stops the node (TD-AUDIT-004). |

Prefixed numbers keep their zero padding: `JE-0003` is reported, not `JE-3`, as long as the series has
zero-padded numbers. A series written `1, 2, ... 12` stays unpadded. Cells that are empty are ignored;
text that does not fit the pattern is counted as unreadable (TD-AUDIT-102 warning).

**Outputs.**

- `G` Gaps: one row per finding, never one row per missing number. Columns: the *Group by* columns, then
  `prefix`, `finding`, `from`, `to`, `count`, `source_row`. `finding` is `gap` (a missing range from
  `from` to `to`, `count` numbers), `duplicate` (`count` times; `source_row` is the 1-based input row of the first
  occurrence), `out_of_order` (`source_row` is the offending row) or `date_gap` (days with no entry).
  `source_row` is blank for gaps. Rows are sorted by group, prefix, finding and `from`; unpadded numbers
  sort as text, so `11..12` comes before `6..7`.
- `S` Summary: the eleven standard columns (`population_value` and `exception_value` are blank; an
  "exception" is one finding row) plus `series`, `gap_ranges`, `missing_items`, `duplicate_values`,
  `out_of_order_rows`, `unparseable_rows`. Status is `fail` when there is any finding.

**Worked example.** Type Prefixed, column `je`, Group by `ledger`. Input:

| ledger | je |
|---|---|
| GL | JE-0001 |
| GL | JE-0002 |
| GL | JE-0005 |
| GL | JE-0006 |
| GL | JE-0006 |
| GL | JE-0004 |
| AP | JE-0100 |
| AP | JE-0102 |

`G` returns:

| ledger | prefix | finding | from | to | count | source_row |
|---|---|---|---|---|---|---|
| AP | JE- | gap | JE-0101 | JE-0101 | 1 | |
| GL | JE- | duplicate | JE-0006 | JE-0006 | 2 | 4 |
| GL | JE- | gap | JE-0003 | JE-0003 | 1 | |
| GL | JE- | out_of_order | JE-0004 | JE-0004 | 1 | 6 |

`S`: `fail`, "2 gap ranges covering 2 missing numbers; 1 repeated numbers; 1 numbers out of order."
(`series` 2, `exception_rows` 4 of 8 rows).

Expected range: for the numbers 3, 4, 5, 8, 9, 10 with type Number, First 1 and Last 12, `G` reports the
gaps `1..2`, `6..7` and `11..12`.

Date example: type Date, column `posting` with 2025-03-03, 03-04, 03-07, 03-12 and 03-12 again:
`G` has two `date_gap` rows, `2025-03-05..2025-03-06` (2 days) and `2025-03-08..2025-03-11` (4 days).
Switching on *Skip weekends* with one holiday, 2025-03-10, leaves `2025-03-05..2025-03-06` (2) and
`2025-03-11..2025-03-11` (1): the weekend and the holiday are not missing days.

## Benford

Tests whether the leading digits of an amount column follow Benford's law. Large departures can point
to invented, rounded or manipulated numbers. It is a prompt for questions, not proof of fraud.

**Sockets.** One input. Outputs `T` Table, `S` Summary, `D` Drill-down.

**Settings, in dock order:**

| Section | Label | Default | Effect |
|---|---|---|---|
| Amount | **Column** | none | The amount column (required). The sign is dropped. Text amounts are read as described above. |
| Test | **Digits** | First digit | *First digit* (1 to 9) or *First two* (10 to 99). |
| Test | **Minimum** | 10.00 | Amounts smaller than this (in either sign) are not tested, because tiny amounts distort the leading digits. Zero is never tested. |
| Result | chart and text | | Bars show the share of rows per digit, the dotted line the share Benford predicts, and digits flagged as out of line are drawn in the danger colour. Below it: the verdict sentence and "Chi-square x (df n), p = ...". |
| Drill-down digits | **Digits that stand out (automatic)** | on | Automatic: the drill-down gets the digits that are over-represented *and* statistically significant. Untick it to tick digits yourself (each row shows the digit, its z-score and its row count). Manual digits outside 1-9 (or 10-99) stop the node (TD-AUDIT-004). |

**Outputs.**

- `T` Table: one row per digit (9 or 90). Columns: `digit`, `count`, `proportion`,
  `expected_proportion`, `expected_count`, `difference`, `z_statistic`, `significant` (z above 1.96, with a
  continuity correction), `chi_square_contribution`.
- `S` Summary: the standard eleven columns (`test_name` is "Benford first digit" or "Benford first two
  digits"; `population_rows` counts every row read, `exception_rows` the rows whose digit stands
  out) plus `digits`, `tested_rows`, `mad`, `conformity`, `chi_square`, `chi_square_df`, `p_value`,
  `flagged_digits` and `unparseable_rows`.
- `D` Drill-down: the input rows whose leading digit is in the drill-down set, with one added column,
  `benford_digits`.

**The verdict** uses the mean absolute deviation (MAD) between the observed and expected shares
(Nigrini's bands):

| `conformity` | First digit MAD | First two digits MAD | `status` |
|---|---|---|---|
| close | up to 0.006 | up to 0.0012 | `pass` |
| acceptable | up to 0.012 | up to 0.0018 | `pass` |
| marginal | up to 0.015 | up to 0.0022 | `warn` |
| nonconforming | above | above | `fail` |

At least 100 tested rows are needed for *first digit* and 1,000 for *first two digits*; with fewer, a
`pass` becomes `warn` and the code is `TD-AUDIT-101` ("Only n rows were tested; at least m are needed for
a reliable result."). If no row has a usable amount the status is `warn` with the same code.

**Preview limits.** While you edit, the node reads at most the first 1,000,000 rows of its input (in
practice the upstream node already hands over 100), and says so in the message. Run reads everything,
so run the full file for the real result.

**Worked example.** 300 invoice amounts, first digit, minimum 10. Digit counts: 1: 90, 2: 52, 3: 36, 4: 28,
5: 60, 6: 20, 7: 6, 8: 5, 9: 3. The table `T` (rounded):

| digit | count | proportion | expected_proportion | difference | z_statistic | significant |
|---|---|---|---|---|---|---|
| 1 | 90 | 0.300 | 0.301 | -0.001 | 0.04 | false |
| 2 | 52 | 0.173 | 0.176 | -0.003 | 0.05 | false |
| 3 | 36 | 0.120 | 0.125 | -0.005 | 0.17 | false |
| 4 | 28 | 0.093 | 0.097 | -0.004 | 0.11 | false |
| 5 | 60 | 0.200 | 0.079 | +0.121 | 7.64 | true |
| 6 | 20 | 0.067 | 0.067 | 0.000 | 0.02 | false |
| 7 | 6 | 0.020 | 0.058 | -0.038 | 2.69 | true |
| 8 | 5 | 0.017 | 0.051 | -0.034 | 2.58 | true |
| 9 | 3 | 0.010 | 0.046 | -0.036 | 2.83 | true |

`S` says `fail`, "Mean absolute deviation 0.0268: nonconforming with Benford's Law (300 rows tested,
chi-square p-value 1.103e-13).", `flagged_digits` `5`. Only digit 5 is flagged: 7, 8 and 9 are
significantly *under*-represented, but a deficit is only a symptom, so only over-represented digits
go to the drill-down. `D` holds the 60 rows starting with 5 (`exception_rows` 60, rate 0.2).

## Sample

Draws a sample that someone else can re-perform and get the same rows.

**Sockets.** One input. Outputs `S` Sample, `N` Not sampled, `L` Selection log.

**Settings, in dock order:**

| Section | Label | Default | Effect |
|---|---|---|---|
| Method | **Method** | Random | *Random*: every row has an equal chance. *Systematic*: every n-th row from a random start. *Monetary unit*: larger amounts are more likely to be picked (needs an Amount column). *Stratified*: split by amount bands and draw a set number from each band. |
| Size (not Stratified) | **Kind** | Count | A number of rows, or a percent of the population. |
| Size | **Rows** (Count) | 100 | Rows to draw (1 or more). |
| Size | **Percent** (Percent) | 10 % | 0.01 to 100. The result is rounded up and is at least 1 row. |
| Seed | **Seed** and a refresh button ("New random seed") | 42 | The same seed and the same data always give the same sample, on any machine and any version of the app. Change the seed, or press the button, to draw a different sample. |
| Columns | **Key** | all columns | The stable key: the columns that identify a row. Rows are put in a fixed order by them before the draw, so a re-sorted file gives the same sample. Pick a column that is unique per row (for example the journal number) to keep memory small. |
| Columns | **Amount** | none | Required for Monetary unit and Stratified; optional otherwise (then the log reports population and sample value). |
| Strata (Stratified only) | **Edges** | empty | Ascending band edges for the absolute amount, for example `1000, 10000`. An amount equal to an edge falls in the higher band. |
| Strata | **Sizes** | empty | One size per band, so one more than the edges, for example `20, 20, all`; `all` takes the whole band. |
| Result | text | | One sentence such as "Selected 5 of 20 rows (random, seed 7)." plus the note, if any. |

Stratified sizes ignore Kind and Size. A row with an unreadable amount belongs to no stratum.

**Outputs.**

- `S` Sample: the selected rows in input order, all input columns plus `sample_seq` (the row's
  position in the sorted population the draw was made on; with a unique, already sorted key it equals the row
  number), `sample_basis` (Monetary unit only: `high_value`, a row so large it is audited for certain, or
  `interval`) and `sample_stratum` (Stratified only).
- `N` Not sampled: every other row, input columns only, in input order.
- `L` Selection log: one `overall` row (and, for Stratified, one `stratum` row per band) with `scope`,
  `stratum`, `method`, `seed`, `algorithm` (always `td-sample-1`), `population_rows`, `population_value`,
  `requested_size`, `sample_size`, `sample_value`, `interval`, `start`, `high_value_items`, `lower_bound`,
  `upper_bound`, `key_columns`, `amount_column`, `parameters` and `note`. Keep `L` in the workpaper so a
  reviewer can redo the draw: same data, same key, same settings, same seed, same rows.

**Warnings.** Asking for more rows than exist selects the whole population and writes
`TD-AUDIT-103: Requested 50 but only 20 rows exist; the whole population was selected.` in `note`. Zero
or unreadable amounts cannot be picked by Monetary unit, and the note says how many. Sample's status in
the run record is always `pass`; the 103 code marks the capped draw.

**Preview limit.** While you edit, a population over 200,000 rows is not sampled on the canvas. The Result
line says "Population has more than 200,000 rows: the sample is drawn when you Run." and the outputs are
empty. Run always draws.

**Worked example.** Twenty journal lines `JE-001` to `JE-020` with amounts 120, 80, 9500, 45, 300, 15, 60,
22000, 75, 410, 18, 90, 35, 5200, 66, 140, 25, 380, 12, 700; key `je`, seed 7, count 5.

| Method | Rows selected | Notes in `L` |
|---|---|---|
| Random | JE-001, 008, 012, 015, 017 | `sample_size` 5 |
| Systematic | JE-002, 006, 010, 014, 018 | `interval` 4.0, `start` 1.559 |
| Monetary unit (Amount `amount`) | JE-003, 005, 008, 014, 018 | `interval` 1285.5; JE-003, 008 and 014 are `high_value`, the others `interval`; `sample_value` 37380 of 39271 |
| Stratified, edges `100, 1000`, sizes `2, 2, all` | JE-003, 005, 006, 008, 010, 012, 014 | three `stratum` rows (11, 6 and 3 rows in the bands) |
| Random, Percent 10 | JE-005, 006 | 10 % of 20 is 2 rows |

## Risk Filters

Runs several classic journal-entry red flags at once and tells you which rows tripped which test.

**Sockets.** One input. Outputs `F` Flagged, `N` Not flagged, `S` Summary.

**Settings, in dock order.** First the **Columns** section:

| Label | Default | Used by |
|---|---|---|
| **Posting date** | none | Weekend posting, Public-holiday posting, Posted after period end (required for those) |
| **Effective** (optional) | none | Posted after period end |
| **Amount** | none | Round amount, Just below approval limit (required for those); optional otherwise |
| **Description** | none | Keyword in description |
| **Manual flag** | none | Manual journal |
| **Date format** | 2024-03-31 (year-month-day) | How text dates are written: five choices |

Then seven sections, one per test. Each has an **Enabled** switch (all off by default; switch on at
least one, TD-AUDIT-008), its options and a **Weight** (1 to 10, default 1). The options of a test that
is switched off stay in the node, greyed out, so turning it off and on loses nothing.

| Test | Flags an entry that was... | Options (default) |
|---|---|---|
| Weekend posting | posted on a Saturday or Sunday | none |
| Public-holiday posting | posted on a date in your list | **Dates**, one `YYYY-MM-DD` per line (at least one) |
| Round amount | a non-zero whole multiple of a round number | **Multiple of** (1000) |
| Just below approval limit | within a margin under a limit (the limit itself is not flagged) | **Limits**, comma separated, such as `5000, 10000`; **Within** (2 %) |
| Keyword in description | described with one of your words (any word, ignoring case, anywhere in the text: `adjust` matches "Adjustment") | **Words**, one per line (at least one) |
| Posted after period end | dated after **Period end** (`YYYY-MM-DD`). With an Effective date column chosen, only when the effective date is on or before the period end, that is, back-dated into the closed period | **Period end** |
| Manual journal | marked manual in the Manual flag column (trimmed, ignoring case) | **Values**, one per line (`manual`, `m`, `y`, `yes`, `true`, `1`) |

An empty or unreadable cell never trips a test.

**Outputs.**

- `F` Flagged: the rows that tripped at least one test, all input columns plus `risk_tests` (the names of the
  tests tripped, separated by `; `) and `risk_score` (the sum of the weights of the tests tripped).
- `N` Not flagged: the other rows, input columns only.
- `S` Summary: the eleven standard columns (values are gross absolute amounts when an Amount column is
  chosen) plus `flagged_two_or_more`, `total_score`, `unparseable_rows` and one count per test:
  `n_weekend`, `n_holiday`, `n_round_amount`, `n_just_below_limit`, `n_keyword`, `n_after_period_end`,
  `n_manual_journal` (blank for a test that is switched off). Status is `warn` when anything is flagged and never
  `fail`; unreadable dates or amounts add the TD-AUDIT-102 note.

A row tripping several tests is usually worth more attention than one tripping a single test.

**Worked example.** Tests on: weekend (weight 1), round amount (multiple of 1000, weight 1), just below
limit (limit 10000, within 2 %, weight 3), keyword (`reversal`, `adjust`, weight 2), posted after period end
(2025-03-31, weight 3), manual journal (`m`, weight 1). Input:

| je | posted | amount | memo | source |
|---|---|---|---|---|
| J1 | 2025-03-01 | 5,000.00 | Accrual | M |
| J2 | 2025-03-04 | 9,900.00 | Reversal of prior | S |
| J3 | 2025-04-02 | 1,234.56 | Misc | M |
| J4 | 2025-03-05 | 10,000.00 | Adjustment | S |
| J5 | 2025-03-06 | 250.00 | Office supplies | S |

`F` has four rows: J1 (`Weekend posting; Round amount; Manual journal`, score 3), J2 (`Just below approval
limit; Keyword in description`, score 5), J3 (`Posted after period end; Manual journal`, score 4) and J4
(`Round amount; Keyword in description`, score 3; 10,000 is the limit itself, so it is not "just below").
`N` has J5. `S` is `warn`, "4 of 5 entries were flagged by at least one risk test.", `exception_value` 26134.56
of `population_value` 26384.56, `total_score` 15, `n_round_amount` 2, `n_keyword` 2.

---

## A worked example across the workflow

1. Add a **File Input** and pick your ledger CSV. (A CSV arrives as text columns; the audit nodes read
   text amounts and dates themselves, so no conversion is needed.)
2. Add **Duplicates**, **Gaps** and **Risk Filters** and connect the File Input to each.
3. Set each node's columns and press its refresh button to see how many rows it flags.
4. Add a **Union** node and connect the three `S` Summary outputs into it: you get one table with a row
   per test.
5. Connect the Union and the flagged outputs you want to keep to **File Output** nodes and Run.

Run then writes the files, tests every row, and records each test's result in the run record.

## Where these live in the code

Calculation (no UI) in `src/trigger_designer/core/audit/`; node and dock in
`src/trigger_designer/qt/widgets/nodes/Audit/`; icons in
`src/trigger_designer/resources/qt/images/node_icons/Audit/`, registered in
`src/trigger_designer/qt/resources.json` as `node_duplicates`, `node_gaps`, `node_benford`,
`node_sample` and `node_risk_filters`. The run record is built by
`core/audit/recorder.py` and `qt/helpers/audit_bridge.py`.
