# Audit nodes

The **Audit** tab in the node palette (and the *Audit* group in the `Shift+A` menu) holds five
tests that auditors run on ledgers and transaction lists. Each test splits the incoming rows into
the ones that **tripped the test** and the rest, and produces a one-row **Summary** that says what
was tested, how many rows were in scope, how many were flagged, and whether the test passed.
(Sample is the exception: its third output is a *Selection log*, see below.)

All five icons are amber, the colour of the Audit family.

The Excel workpaper of a test (Summary, Exceptions, Run log, Workflow) is described in the
[Workpapers guide](../../guide/workpaper.md).

## Nodes in this family

| Icon | Node | What it does |
|---|---|---|
| ![Duplicates](../../assets/node_icons/Audit/Duplicates.svg) | **[Duplicates](duplicates.md)** | Finds exact and near-duplicate rows. |
| ![Gaps](../../assets/node_icons/Audit/Gaps.svg) | **[Gaps](gaps.md)** | Finds missing, repeated and out-of-order numbers, and days with no entry. |
| ![Benford](../../assets/node_icons/Audit/Benford.svg) | **[Benford](benford.md)** | Tests the leading digits of an amount column against Benford's law. |
| ![Sample](../../assets/node_icons/Audit/Sample.svg) | **[Sample](sample.md)** | Draws a random, systematic, monetary-unit or stratified sample that can be repeated with its seed. |
| ![Risk Filters](../../assets/node_icons/Audit/Risk%20Filters.svg) | **[Risk Filters](risk-filters.md)** | Flags entries that trip classic journal-entry risk indicators. |

## Common to every audit node

**Wiring.** Connect one table into the node's single input. The sockets are labelled with the
letters in the table above. Connect any output to a *File Output*, a *Data Profile*, or another
node. A node whose input is not connected shows "Input has no data" in its tooltip and passes nothing on.

**Live preview versus Run.** While you edit, upstream nodes (File Input and the Transform and
Preparation nodes) pass only the first 100 rows of each table, so every audit node tests that small
sample and the numbers you see are a preview. Press **Run** and every audit node tests all rows.
Benford and Sample have their own limits, noted in their sections. The Data Preview dock labels a
table *evaluated · not run* (preview) or *from Run*. Details: [Live preview versus Run](../../nodes/index.md#preview-versus-run).

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
and in the Excel workpaper ([guide](../../guide/workpaper.md)). A preview (live) result is never recorded, only a Run.

---

