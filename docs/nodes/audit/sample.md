# Sample

![Sample](../../assets/node_icons/Audit/Sample.svg){ .node-icon }

## Purpose

Draws a sample that someone else can re-perform and get the same rows.

## Inputs and outputs

One input. Outputs `S` Sample, `N` Not sampled, `L` Selection log.

## Settings

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

## Worked example

Twenty journal lines `JE-001` to `JE-020` with amounts 120, 80, 9500, 45, 300, 15, 60,
22000, 75, 410, 18, 90, 35, 5200, 66, 140, 25, 380, 12, 700; key `je`, seed 7, count 5.

| Method | Rows selected | Notes in `L` |
|---|---|---|
| Random | JE-001, 008, 012, 015, 017 | `sample_size` 5 |
| Systematic | JE-002, 006, 010, 014, 018 | `interval` 4.0, `start` 1.559 |
| Monetary unit (Amount `amount`) | JE-003, 005, 008, 014, 018 | `interval` 1285.5; JE-003, 008 and 014 are `high_value`, the others `interval`; `sample_value` 37380 of 39271 |
| Stratified, edges `100, 1000`, sizes `2, 2, all` | JE-003, 005, 006, 008, 010, 012, 014 | three `stratum` rows (11, 6 and 3 rows in the bands) |
| Random, Percent 10 | JE-005, 006 | 10 % of 20 is 2 rows |


Back to the [Audit node index](index.md).
