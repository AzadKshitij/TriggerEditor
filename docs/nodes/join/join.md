# Join

![Join icon](../../assets/node_icons/Join/Join.svg){ .node-icon }

## Purpose

Join matches the rows of two tables on one or more key columns and gives you three results at once: the rows that matched (with columns from both sides), the left rows that have no match, and the right rows that have no match. You never lose a row silently, which is what you want in an audit.

## When to use it

- You want to bring information from one table into another (add the vendor's country to each payment).
- You want to find what is in one list and not in the other (invoices without payment, payments without invoice), when the keys are exactly equal.

If the keys are not exactly equal (small differences in text, amounts that must agree within a tolerance, dates that may be a few days apart), use [Reconcile](reconcile.md) or [Fuzzy Match](fuzzy-match.md).

## Inputs and outputs

| Socket | Carries |
|---|---|
| Input 1 (left, top) | The left table. |
| Input 2 (right, bottom) | The right table. |
| Output `L` | **Left only.** Left rows with no matching right row. Columns: all of the left table's columns. |
| Output `J` | **Joined.** Rows that matched on the keys, with the columns you chose in Output columns (all by default). |
| Output `R` | **Right only.** Right rows with no matching left row. Columns: all of the right table's columns. |

## Settings

Until both inputs are connected the Config Dock says "Both inputs must be connected". Then:

**Key pairs**

| Control | What it does | Default |
|---|---|---|
| **Add key pair** (icon) | Adds a pair: a column from the left table, an arrow, a column from the right table. Rows match when all pairs are equal. The new pair is pre-filled with the first column combination not already used. | One pair is created for you: the first column of each table |
| Each pair: **Left key column**, **Right key column** | The columns that must be equal. A column that has vanished from the input is shown as `name (missing)`. | |
| **Remove key pair** (icon) | Deletes the pair. | |

**Output columns** ("Unchecked columns stay out of the joined output.")

| Control | What it does | Default |
|---|---|---|
| **Auto-accept new columns** (checkbox) | When on, a column that newly appears upstream is ticked automatically. When off, it stays unticked until you tick it. | On |
| **All** / **None** | Tick or untick every column. | |
| Column checklist, entries shown as `L: name` and `R: name` | Which columns the `J` output contains. `L:` columns come from the left table, `R:` from the right. | Everything ticked |

The output columns control the `J` output only. `L` and `R` always carry every column of their own side.

A summary chip shows the number of keys and the number of columns, with "full outer join".

## Worked example

Left (invoices):

| Invoice | Amount |
|---|---|
| A1 | 100.0 |
| A2 | 250.0 |
| A3 | 75.0 |

Right (payments):

| Invoice | Amount | Paid |
|---|---|---|
| A1 | 100.0 | Y |
| A3 | 80.0 | N |
| A9 | 10.0 | Y |

Key pair: `Invoice` = `Invoice`. Everything ticked.

Output `L` (invoice A2 has no payment):

| Invoice | Amount |
|---|---|
| A2 | 250.0 |

Output `J`:

| Invoice | Amount | Amount_right | Paid |
|---|---|---|---|
| A1 | 100.0 | 100.0 | Y |
| A3 | 75.0 | 80.0 | N |

Output `R` (payment A9 has no invoice):

| Invoice | Amount_right | Paid |
|---|---|---|
| A9 | 10.0 | Y |

When both tables have a column of the same name (`Amount`), the right table's column is renamed `Amount_right` in `J` and `R`. In the Output columns list it still appears as `R: Amount`.

If you tick only `L: Invoice` and `R: Paid` in Output columns, `J` becomes:

| Invoice | Paid |
|---|---|
| A1 | Y |
| A3 | N |

When the key columns have different names (`InvoiceNo` on the left, `Ref` on the right), the key appears once in `J`, under the **left** name, and in `R` the right-only keys also appear under the left name (`InvoiceNo`).

## Edge cases and limits

- **Row cap:** none in the node. The live preview shows 100 rows; Run joins everything. See [Live preview and Run](../input-output/index.md#live-preview-and-run).
- **Exact match only.** Keys are compared as they are: `ABC` and `abc` do not match, and `A1` and ` A1` (with a space) do not match. Clean keys first (see Cleansing in [Preparation nodes](../preparation/index.md)) or use [Reconcile](reconcile.md), which trims and ignores case.
- **Null keys never match.** A left row with an empty key goes to `L`; a right row with an empty key goes to `R`.
- **One-to-many.** If one left row matches several right rows, `J` has one row per pair, so the left row appears several times. Row counts in `J` can therefore be higher than either input. Check for duplicate keys with the [Duplicates audit node](../audit/index.md) before you join.
- **Key types must be the same.** A number key against a text key is refused (see errors). Convert one side with a Select node.
- **Columns that disappear upstream** are dropped from the Output columns selection. A key pair whose column no longer exists is dropped too. If you remove every key pair (or the last one disappears), Join puts the default pair back (the first column of each table) the next time it evaluates, so check the key pair after changing the inputs.
- **Renamed columns upstream.** If you rename a column in a Select node placed before Join, the key pairs and selections follow the new name.
- **Row order is not guaranteed** (a 1-to-many join may list the matches in any order). Add a Sort node if order matters.

## Errors you may see

| Code | What it means | What to do |
|---|---|---|
| `TD-SHAPE-001` | "Add at least one key pair". No pair is set (rare: the dock normally re-creates the default pair). | Add a key pair. |
| `TD-TYP-002` | The two key columns have different types, for example whole numbers against text. | Add a Select node on one side and set the key column to the same type (usually Text). |
| `TD-SHAPE-005` | An input has no data. | Connect and fix the upstream node. |

## Tips

- Join the two tables and check three numbers: rows in `L`, rows in `J`, rows in `R`. They should explain your totals: left rows = `L` + the left side of `J`.
- To get a classic "left join", use `J` and `L` together with [Append](append.md) (Diagonal), or just use `L` to list the exceptions.
- Join on several columns at once (company and invoice number) with extra key pairs rather than creating a combined key.


Back to the [Join node index](index.md).
