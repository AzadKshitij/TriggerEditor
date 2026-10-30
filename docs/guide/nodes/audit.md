# Audit nodes

The **Audit** tab holds five tests that auditors run on ledgers and transaction lists. Each splits the
incoming rows into the ones that tripped the test and the rest, and each produces a one-row result (a
**Summary**, or for Sample a **Selection log**) that says what was tested, how many rows were in scope, how many
were flagged and whether the test passed.

| Icon | Node | Question it answers | Outputs | Result `status` |
|---|---|---|---|---|
| ![Duplicates](../../../src/trigger_designer/resources/qt/images/node_icons/Audit/Duplicates.svg) | **Duplicates** | Which rows repeat, exactly or nearly (same key, close amount, close date)? | `D` Duplicates, `U` Unique, `S` Summary | `fail` if any duplicate, else `pass` |
| ![Gaps](../../../src/trigger_designer/resources/qt/images/node_icons/Audit/Gaps.svg) | **Gaps** | Which document numbers, or which days, are missing from a sequence? | `G` Gaps, `S` Summary | `fail` if any finding, else `pass` |
| ![Benford](../../../src/trigger_designer/resources/qt/images/node_icons/Audit/Benford.svg) | **Benford** | Do the leading digits of an amount column look natural? | `T` Table, `S` Summary, `D` Drill-down | `pass`, `warn` (marginal) or `fail` (nonconforming) |
| ![Sample](../../../src/trigger_designer/resources/qt/images/node_icons/Audit/Sample.svg) | **Sample** | Draw a sample that a reviewer can repeat exactly. | `S` Sample, `N` Not sampled, `L` Selection log | `pass` (a warning code if capped) |
| ![Risk Filters](../../../src/trigger_designer/resources/qt/images/node_icons/Audit/Risk%20Filters.svg) | **Risk Filters** | Which entries trip classic risk indicators (weekend, round, just below limit, keyword, late, manual)? | `F` Flagged, `N` Not flagged, `S` Summary | `warn` if any flagged, else `pass` |

All five icons are amber, the colour of the Audit family.

## What they have in common

- **One input table, several outputs.** The letters on the sockets are shown in the table above.
- **Plain-language results.** Every Summary carries the rule in a sentence (`criteria`), the settings as
  JSON (`parameters`), the outcome in a sentence (`message`), the population and the exceptions in rows and
  value.
- **Skipped values are reported, not hidden.** Amounts or dates that cannot be read are skipped and the
  status is raised to `warn` (code `TD-AUDIT-102`). Settings mistakes stop the node with a `TD-AUDIT-0xx`
  message.
- **Preview versus Run.** While you edit, the audit nodes test the 100-row sample that the nodes before them
  pass on; **Run** tests every row. See [Live preview versus Run](README.md#live-preview-versus-run). The
  audit nodes re-test as soon as you change a setting; they do not wait for you to click away.
- **Recorded in the run history.** After a Run, each test's result is stored in the run record (the
  `test_summary` of that node), with its settings and, for Sample, its seed. The Excel workpaper presents
  them. <!-- workpaper: see ../workpaper.md -->

## Full guide

Every setting, output column, code and worked example is in
**[Audit nodes: how to use them](../../nodes/audit-nodes.md)**:

- [Duplicates](../../nodes/audit-nodes.md#duplicates)
- [Gaps](../../nodes/audit-nodes.md#gaps)
- [Benford](../../nodes/audit-nodes.md#benford)
- [Sample](../../nodes/audit-nodes.md#sample)
- [Risk Filters](../../nodes/audit-nodes.md#risk-filters)

The sections of that page on the summary table, amount reading (including decimal commas such as `1.234,50`),
error and warning codes and the audit trail apply to all five nodes.

Back to the [node index](README.md).
