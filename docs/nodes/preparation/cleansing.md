# Cleansing

![Cleansing icon](../../assets/node_icons/Preparation/Cleansing.svg){ .node-icon }

## Purpose

Removes empty rows and columns, fills empty cells with neutral defaults, and tidies text (spaces, letters, digits, punctuation, upper or lower case) in the columns you choose.

## When to use it

Right after reading a file with untidy text: stray spaces that stop two vendor names matching, empty cells that break arithmetic, mixed case.

## Inputs and outputs

| Socket | Carries |
|---|---|
| Input | The table to clean |
| Out | The cleaned table (same columns, unless "Remove all-null columns" removes some) |

## Settings

The node applies them in this order: remove nulls, replace nulls, whitespace, characters, case.

| Section | Control | Default | Effect |
|---|---|---|---|
| Fields | **Clean** (column checklist) | none ticked | The columns the **text rules** apply to (whitespace, characters, case) and "Remove rows null in selected". With nothing ticked the text rules do nothing, and a warning chip says so. The null replacement rules are **not** limited to these columns. |
| Nulls | Remove all-null rows | off | Deletes rows where every cell is empty. |
| Nulls | Remove rows null in selected | off | Deletes rows where any ticked **Clean** column is empty. Greyed out until you tick a column. |
| Nulls | Remove all-null columns | off | Deletes columns where every cell is empty. |
| Nulls | Replace null text with '' | **on** | Every empty cell in a **text** column becomes an empty text. |
| Nulls | Replace null numbers with 0 | **on** | Every empty cell in a number column becomes 0. |
| Whitespace and characters | Trim whitespace | **on** | Removes spaces at the start and end of the text in the ticked columns. |
| Whitespace and characters | Collapse inner spaces | **on** | Turns runs of spaces inside the text into one space. It does not trim the ends; that is Trim's job. |
| Whitespace and characters | Remove all whitespace | off | Deletes every space, tab and line break. Wins over collapsing. |
| Whitespace and characters | Remove letters | off | Deletes letters (Latin including accented letters, and basic Cyrillic). |
| Whitespace and characters | Remove numbers | off | Deletes digits. |
| Whitespace and characters | Remove punctuation | off | Deletes punctuation such as `. , ; : ! ? - ( )`. |
| Case | **Case** | None | None, Lower Case, Upper Case, or Title Case (first letter of each word upper, the rest lower). |

With no column ticked under **Clean**, only the null rules run. Because the two null replacements are on by default, all empty text cells become blank text and all empty numbers become 0. Untick them if empty cells must stay empty.

## Worked example

Input:

| Name | Amount | Note |
|---|---|---|
| `  alice   smith ` | 10 | a1! |
| BOB  jones | *(empty)* | b2? |
| *(empty)* | 5 | *(empty)* |
| carol-ann | 7 | c3. |

Settings: Clean = Name and Note; Remove punctuation on; Case = Title Case; everything else at its default.

| Name | Amount | Note |
|---|---|---|
| Alice Smith | 10 | A1 |
| Bob Jones | 0 | B2 |
| *(empty text)* | 5 | *(empty text)* |
| Carolann | 7 | C3 |

A second run on the same input: Clean = Name, "Remove rows null in selected" on, both "Replace null ..." options off, other text rules at their defaults. The row where Name is empty is removed and the empty Amount stays empty:

| Name | Amount | Note |
|---|---|---|
| alice smith | 10 | a1! |
| BOB jones | *(empty)* | b2? |
| carol-ann | 7 | c3. |

## Edge cases and limits

- [Preview uses 100 rows](index.md#preview-vs-run).
- Text rules only touch **text** columns. Ticking a number column under **Clean** does nothing for it.
- "Replace null text" and "Replace null numbers" leave dates, yes/no columns and other types empty.
- Removing punctuation also removes hyphens and apostrophes (`carol-ann` becomes `carolann`).
- Title Case lowercases the rest of each word (`BOB jones` becomes `Bob Jones`).
- An empty input returns an empty table.

## Messages you may see

`TD-SHAPE-005` (no input data). Cleansing has no setting that can be invalid.

## Tips

- Put Cleansing before a [Join](../join/index.md) or [Unique](unique.md): trimming and case-folding key columns prevents "Acme " and "ACME" counting as different.
- Use [Find and Replace](find-and-replace.md) for specific substitutions and Cleansing for general tidying.
- To keep the original next to the cleaned text, use Find and Replace with "Keep original".


Back to the [Preparation node index](index.md).
