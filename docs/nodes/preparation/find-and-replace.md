# Find and Replace

![Find and Replace icon](../../assets/node_icons/Preparation/FindReplace.svg){ .node-icon }

## Purpose

Applies an ordered list of find-and-replace rules to the text columns you pick, as plain text or as regular expressions.

## When to use it

Standardise names (`Ltd.` to `Limited`), strip prefixes, blank out placeholders such as `N/A`, fix a recurring typo across a column.

## Inputs and outputs

| Socket | Carries |
|---|---|
| Input | The table |
| Out | The same table with the replaced text (in place, or in new columns) |

## Settings

| Section | Control | Default | Effect |
|---|---|---|---|
| Columns | **Columns** (picker) | none | The **text** columns to change. Hint: "Text columns only. A numeric column is rejected." |
| Rules | **Rule** (list, up to 50, each card collapsible) | none | One card per rule. The collapsed card shows a summary such as `Find... -> Replace · literal`. |
| Rules | **Find** | empty | The text (or pattern) to look for, up to 500 characters. |
| Rules | **Replace** | empty | The replacement. Empty deletes the found text. |
| Rules | **Mode** | Literal | **Literal** matches the text exactly as typed. **Regex** reads Find as a regular expression. |
| Rules | **On** | on | Untick to switch a rule off without deleting it. |
| Rules | **Match case** | off | Off means upper and lower case do not matter. |
| Rules | **Whole cell** | off | Replace only when the whole cell equals the Find text (or the whole cell matches the regular expression). |
| Output | **Keep original** and a suffix box (placeholder `_clean`) | off | Off: the columns are changed in place. On: the original stays and the result goes to a new column named `<column><suffix>`; an empty suffix becomes `_clean`. |

A note says "Rules run top to bottom. Each rule sees the previous result." The node shows a chip such as "12 cells change (first 100 rows)" or "No cells change in the first 100 rows".

In **Regex** mode the replacement can use groups from the pattern as `$1`, `$2`, .... In **Literal** mode a `$` in the replacement is just a dollar sign.

## Worked example

Input:

| memo | amt |
|---|---|
| Paid to ACME Ltd. | 1 |
| paid to acme ltd | 2 |
| N/A | 3 |
| Refund (ACME) | 4 |

Columns = `memo`; Keep original on (suffix `_clean`); rule 1: Find `N/A`, Replace empty, Literal, Whole cell; rule 2: Find `^(?:Paid to|paid to) `, Replace empty, Regex.

| memo | amt | memo_clean |
|---|---|---|
| Paid to ACME Ltd. | 1 | ACME Ltd. |
| paid to acme ltd | 2 | acme ltd |
| N/A | 3 | *(empty text)* |
| Refund (ACME) | 4 | Refund (ACME) |

A single Literal rule with Find `acme`, Replace `Acme Inc`, Match case off, in place, changes every case variant: `Paid to Acme Inc Ltd.`, `paid to Acme Inc ltd`, `Refund (Acme Inc)`.

## Edge cases and limits

- [Preview uses 100 rows](index.md#preview-vs-run); the "cells change" chip counts the sample only.
- Only **text** columns. Pick a number column and the node stops with `TD-SHAPE-044`; convert it with [Select](select.md) first.
- Empty cells stay empty.
- Only switched-on rules are checked. A switched-off rule may have an empty Find or an invalid pattern without stopping the node; the "Rule n" in a message counts all rules, on or off.
- With no rule switched on, the table passes through unchanged (the columns are still checked).
- Rules run in order, so a later rule can change what an earlier one produced.
- A Regex Find that is not valid (for example an unclosed `(`) stops the node with `TD-SHAPE-040`. Escape special characters with a backslash.
- With Keep original on, the new column names must not already exist or repeat (`TD-SHAPE-002`).

## Messages you may see

| Code | When | Fix |
|---|---|---|
| `TD-SHAPE-001` | No column picked | Pick at least one text column |
| `TD-SHAPE-002` | A suffixed name already exists or repeats | Change the suffix |
| `TD-SHAPE-003` | A picked column is gone | Pick it again |
| `TD-SHAPE-040` | Invalid regular expression (the detail names the rule number) | Escape special characters with a backslash |
| `TD-SHAPE-041` | Find longer than 500 characters | Shorten it |
| `TD-SHAPE-042` | A switched-on rule has an empty Find | Type the text, or remove the rule |
| `TD-SHAPE-043` | More than 50 rules | Remove rules or use two nodes |
| `TD-SHAPE-044` | A picked column is not text | Convert it to text with Select |

## Tips

Turn Keep original on while you build the rules, compare the two columns, then switch it off when you are happy.


Back to the [Preparation node index](index.md).
