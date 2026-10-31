# Risk Filters

![Risk Filters](../../assets/node_icons/Audit/Risk%20Filters.svg){ .node-icon }

## Purpose

Runs several classic journal-entry red flags at once and tells you which rows tripped which test.

## Inputs and outputs

One input. Outputs `F` Flagged, `N` Not flagged, `S` Summary.

## Settings

First the **Columns** section:

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
  chosen) plus `flagged_two_or_more`, `total_score`, `unparseable_rows` (rows with at least one unreadable amount or date; a row with two bad cells counts once) and one count per test:
  `n_weekend`, `n_holiday`, `n_round_amount`, `n_just_below_limit`, `n_keyword`, `n_after_period_end`,
  `n_manual_journal` (blank for a test that is switched off). Status is `warn` when anything is flagged and never
  `fail`; unreadable dates or amounts add the TD-AUDIT-102 note.

A row tripping several tests is usually worth more attention than one tripping a single test.

## Worked example

Tests on: weekend (weight 1), round amount (multiple of 1000, weight 1), just below
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


Back to the [Audit node index](index.md).
