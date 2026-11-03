# Normalize

![Normalize icon](../../assets/node_icons/Preparation/Select.svg){ .node-icon }

## Purpose

Tidies the **column names**, not the values: trims spaces, turns spaces into underscores or removes them, and changes case. (The palette entry is "Normalize Columns"; the node uses the Select icon.)

## When to use it

Files from different systems name the same column differently (`Net Amount`, `net amount `, `NET_AMOUNT`). Normalize gives them one pattern so formulas and joins do not trip over stray spaces.

## Inputs and outputs

| Socket | Carries |
|---|---|
| Input | The table |
| Out | The same data with new column names |

## Settings

Rules apply in the order trim, whitespace, case.

| Section | Control | Default | Effect |
|---|---|---|---|
| Name rules | **Trim spaces** | on | Removes spaces at the start and end of the name. |
| Name rules | **Spaces to underscores** | on | Each run of spaces inside the name becomes `_`. |
| Name rules | **Remove all whitespace** | off | Deletes spaces entirely. Wins over underscores. |
| Name rules | **Case** | None | None, Lower Case, Upper Case, Title Case (first letter of each word upper, the rest lower). |
| Columns | **Normalize** (checklist) | none ticked | The columns to rename. **Empty means every column.** |

## Worked example

Input columns: `Customer ID`, `  Order Date ` (spaces around it), `Net Amount`. Case = Lower Case.

Output columns: `customer_id`, `order_date`, `net_amount`.

With "Remove all whitespace" on and Title Case, `Customer ID` becomes `Customerid` and `Order  Date` becomes `Orderdate`.

## Edge cases and limits

- If two names end up identical (`Net Amount` and `net amount` with Lower Case), the node stops with `TD-SHAPE-002` and names the duplicate. Untick one of the columns or rename it first.
- A rule never produces an empty name; the original name is kept.
- Only names change; data and types are untouched. Check any [Select](select.md) or [Formula](formula.md) that refers to the old names.
- Normalize reads no row data, so the [100-row preview](index.md#preview-vs-run) makes no difference.

## Messages you may see

`TD-SHAPE-002` (the rules give a duplicate column name: tick fewer columns or change the rules), `TD-SHAPE-005`.

## Tips

Place it directly after the input node, before anything refers to column names.


Back to the [Preparation node index](index.md).
