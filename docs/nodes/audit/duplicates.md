# Duplicates

![Duplicates](../../assets/node_icons/Audit/Duplicates.svg){ .node-icon }

## Purpose

Finds rows that repeat.

## Inputs and outputs

One input. Outputs `D` Duplicates, `U` Unique, `S` Summary.

## Settings

(defaults in brackets):

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

## Worked example

Exact match on `vendor` and `invoice_no`, Trim on, Ignore case on. Input (6 rows):

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


Back to the [Audit node index](index.md).
