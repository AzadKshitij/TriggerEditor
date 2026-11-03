# Date Helper

![Date Helper icon](../../assets/node_icons/Preparation/DateHelper.svg){ .node-icon }

## Purpose

Adds columns derived from dates: weekday, weekend and month-end flags, quarters and fiscal periods, the difference between two dates, adding days or **working** days, using your own working week and holidays.

## When to use it

Cut-off and timing tests: postings on weekends or public holidays, days from invoice to payment, working days to settle, fiscal quarter reporting.

## Inputs and outputs

| Socket | Carries |
|---|---|
| Input | The table (dates may be real dates or text) |
| Out | The input columns plus one new column per calculation |

## Settings

| Section | Control | Default | Effect |
|---|---|---|---|
| Calendar | **Fiscal year starts** | January | The first month of your fiscal year. |
| Calendar | **Working days** (seven buttons M T W T F S S) | Monday to Friday | The days that count as working days. At least one is required. |
| Calculations | **Calculation** list (each entry collapsible) | none | One entry per new column. The collapsed entry shows `Calculation · Date -> Name`. |
| each entry | **Calculation** | Weekday name | What to compute (table below). |
| each entry | **Output name** (placeholder "Auto") | Auto | The new column's name. Auto gives `<date column>_<calculation>`, or `<date1>_to_<date2>_<calculation>` for the two-date calculations. |
| each entry | **Date** | empty | The date column (real date or text). |
| each entry | **Second date** | blank | For the two-date calculations. |
| each entry | **Days** (-100,000 to 100,000) | 0 | For Add days and Add business days. |
| each entry | **Days from column** | blank | A column with the number of days per row; overrides **Days** when set. |
| Advanced date handling (collapsed) | **Text dates** | Auto-detect | How to read text dates: `2024-12-31`, `31/12/2024`, `12/31/2024`, `31-Dec-2024`, `20241231` or `31.12.2024`. |
| Advanced date handling | **Non-working day** | Forward | When an Add business days start date is not a working day, move **Forward** to the next working day or **Backward** to the previous one first. |
| Advanced date handling | **Holidays** (text box, placeholder "2024-12-25 (one per line)") | empty | Holidays as `YYYY-MM-DD`, separated by new lines, spaces, commas or semicolons. They are skipped by the business-day calculations. |

Only the fields a calculation uses are shown.

| Calculation | Result |
|---|---|
| Weekday name | `Monday` to `Sunday` (English) |
| Weekday number | 1 (Monday) to 7 (Sunday) |
| Is weekend | true when the day is **not** one of your Working days |
| Is month end | true on the last day of the month |
| Quarter | calendar quarter 1 to 4 |
| Fiscal year | the year in which the fiscal year **ends**. With an April start, 31 Jan 2024 and 2 Mar 2024 are fiscal year 2024 and 25 Dec 2024 is 2025. With a January start it is the calendar year. |
| Fiscal period | month number within the fiscal year (1 to 12) |
| Fiscal quarter | 1 to 4, counted from the fiscal start |
| Days between | Second date minus Date, in days (negative when the second date is earlier) |
| Add days | Date plus Days |
| Add business days | Date plus working days, respecting Working days and Holidays |
| Is business day | true when the date is a working day and not a holiday |
| Business days between | Working days from Date up to, but not including, Second date |

## Worked example

Input (text dates):

| inv_date | due |
|---|---|
| 2024-01-31 | 2024-02-15 |
| 2024-03-02 | 2024-03-01 |
| 2024-12-25 | 2025-01-10 |

Settings: fiscal year starts April; holiday `2024-12-25`; calculations on `inv_date`: Weekday name, Is month end (named `month_end`), Fiscal year, Fiscal quarter, Fiscal period, Days between (second date `due`), Add business days (Days 3, named `plus3bd`), Is business day, Is weekend.

| inv_date | weekday name | month_end | fiscal year | fiscal quarter | fiscal period | days between | plus3bd | is business day | is weekend |
|---|---|---|---|---|---|---|---|---|---|
| 2024-01-31 | Wednesday | true | 2024 | 4 | 10 | 15 | 2024-02-05 | true | false |
| 2024-03-02 | Saturday | false | 2024 | 4 | 12 | -1 | 2024-03-07 | false | true |
| 2024-12-25 | Wednesday | false | 2025 | 3 | 9 | 16 | 2024-12-31 | false | false |

The real output also contains `inv_date` and `due`, and uses the Auto names such as `inv_date_weekday_name` and `inv_date_to_due_days_between`. Note that 25 December is a Wednesday, so "Is weekend" is false, yet "Is business day" is false because the date is in the Holidays list.

## Edge cases and limits

- [Preview uses 100 rows](index.md#preview-vs-run). A chip "n unreadable dates in column (first 100 rows)" reports text that could not be read as a date in the sample.
- Text that cannot be read as a date gives an **empty** result, not an error.
- Auto-detect cannot know whether `03/04/2024` is 3 April or 4 March. When your text dates contain slashes, choose the exact layout under **Text dates**.
- The date column must be a real date, a date-time or text; a number column gives `TD-SHAPE-050`.
- A time of day on a date-time value is ignored; calculations use the date part.
- New column names must be unique and must not already exist (`TD-SHAPE-002`).
- With no calculations the table passes through unchanged.

## Messages you may see

| Code | When | Fix |
|---|---|---|
| `TD-SHAPE-001` | A calculation has no date column (or no second date for a two-date one) | Pick it |
| `TD-SHAPE-002` | An output name is duplicated or already exists | Give it a unique name |
| `TD-SHAPE-003` | A chosen column is gone | Pick it again |
| `TD-SHAPE-004` | An unknown value (fiscal month, working day, roll direction, calculation) | Pick from the lists |
| `TD-SHAPE-050` | The column is neither a date nor text | Choose a date or text column |
| `TD-SHAPE-052` | A holiday is not `YYYY-MM-DD` (the detail quotes it) | Type holidays as year-month-day |
| `TD-SHAPE-053` | No working day ticked | Tick at least one weekday |

## Tips

- Add "Is weekend" and "Is business day" columns, then use a [Filter](filter.md) to list postings on non-working days.
- Keep the holiday list in the workflow so the test is reproducible.


Back to the [Preparation node index](index.md).
