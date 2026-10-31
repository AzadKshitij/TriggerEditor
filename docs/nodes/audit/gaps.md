# Gaps

![Gaps](../../assets/node_icons/Audit/Gaps.svg){ .node-icon }

## Purpose

Finds what is missing from a sequence, such as cheque or journal numbers, or days without entries.

## Inputs and outputs

One input. Outputs `G` Gaps (the findings) and `S` Summary.

## Settings

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
  `source_row` is blank for gaps. Rows are sorted by group, prefix, finding and then by the numeric value
  of `from`, so `6..7` comes before `11..12` (dates sort chronologically).
- `S` Summary: the eleven standard columns (`population_value` and `exception_value` are blank; an
  "exception" is one finding row) plus `series`, `gap_ranges`, `missing_items`, `duplicate_values`,
  `out_of_order_rows`, `unparseable_rows`. Status is `fail` when there is any finding.

## Worked example

Type Prefixed, column `je`, Group by `ledger`. Input:

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


Back to the [Audit node index](index.md).
