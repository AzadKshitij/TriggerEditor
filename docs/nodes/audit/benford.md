# Benford

![Benford](../../assets/node_icons/Audit/Benford.svg){ .node-icon }

## Purpose

Tests whether the leading digits of an amount column follow Benford's law. Large departures can point
to invented, rounded or manipulated numbers. It is a prompt for questions, not proof of fraud.

## Inputs and outputs

One input. Outputs `T` Table, `S` Summary, `D` Drill-down.

## Settings

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

## Worked example

300 invoice amounts, first digit, minimum 10. Digit counts: 1: 90, 2: 52, 3: 36, 4: 28,
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


Back to the [Audit node index](index.md).
