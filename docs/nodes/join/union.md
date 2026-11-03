# Union

![Union icon](../../assets/node_icons/Join/Union.svg){ .node-icon }

## Purpose

Union stacks any number of tables, one under the other (the SQL "UNION ALL": all rows are kept, duplicates are not removed). It has three ways of lining up the columns.

## When to use it

- You have three or more tables with the same layout (twelve monthly extracts, one table per entity).
- The tables are almost the same but a few columns are named differently, and you want to say which column lines up with which.
- You want to stack by column position and ignore headers.

## Inputs and outputs

| Socket | Carries |
|---|---|
| Input (a single socket on the left that accepts **any number of connections**) | Every connected table. Connect as many as you need to this one socket. |
| Output (one, on the right) | The stacked table. |

The inputs are stacked in connection order (`#1` first). The **Input order** section lets you change it.

## Settings

The Config Dock shows "Connect at least one input" until something is connected. After that it has up to three sections.

**Union mode** ("How columns from the inputs are aligned.")

| Control | What it does | Default |
|---|---|---|
| **Mode** | **Auto by Name**: columns with exactly the same name (upper/lower case matter) line up. The output has every name found, in the order first seen; a table without a column gets empty values there. **Auto by Position**: ignore names; the first column of each table lines up, then the second, and so on. The output uses the first table's column names; if another table is wider, the extra columns are named `Extra_4`, `Extra_5`..., and shorter tables are filled with empty values. **Manual**: you build the output columns yourself. | Auto by Name |

**Input order** ("Rows stack #1 first. Reorder with Up/Down or reconnect edges.")

One row per connected input, labelled with its number and where it comes from (for example `#1 File Input [out 0]`), with two icon buttons per row: **Move input N earlier** and **Move input N later**. Each move is an undo step ("Input Order Changed").

**Column Mapping** (only in Manual mode; "Align each input's column to an output. Blank = Null.")

| Control | What it does |
|---|---|
| Header row | `Output`, then one heading per input. |
| **Output column** (text box) | The name of this column in the result. |
| One drop-down per input | Which column of that input goes into this output column. `(none)` leaves it empty (null) for that input. |
| **Add output column** (icon) | Adds a row, named `New_Column`, `New_Column_2`... |
| **Remove output column** (icon, per row) | Removes the row. |

The first time you switch to Manual, the grid is pre-filled with the Auto-by-Name result so you can adjust it. Rows with an empty or repeated output name are ignored. Edits apply about a third of a second after you stop.

## Worked example

Three tables:

`Table 1`

| Invoice | Amount |
|---|---|
| A1 | 10 |
| A2 | 20 |

`Table 2` (the amount is text; has an extra column)

| Invoice | Amount | Note |
|---|---|---|
| B1 | "30" | late |

`Table 3` (reference column has a different name)

| Ref | Amount |
|---|---|
| C1 | 5 |

**Auto by Name** gives:

| Invoice | Amount | Note | Ref |
|---|---|---|---|
| A1 | 10 | null | null |
| A2 | 20 | null | null |
| B1 | 30 | late | null |
| null | 5 | null | C1 |

`Amount` is whole numbers in two tables and text in the other, so the whole column becomes text (shown as numbers here for readability). The node's tooltip says: `Column 'Amount' has conflicting types (Int64, String); coerced to String.` `Ref` is a separate column from `Invoice`; to line them up use Manual.

**Manual** with two tables, `Table 1` = (Invoice, Amount) and `Table 4` = (Ref, Total, Note):

| Output | Table 1 | Table 4 |
|---|---|---|
| Doc | Invoice | Ref |
| Value | Amount | Total |
| Comment | (none) | Note |

gives

| Doc | Value | Comment |
|---|---|---|
| A1 | 10 | null |
| B1 | 20 | x |

(`Table 1` supplies A1/10; `Table 4` supplies B1/20/x.)

**Auto by Position** on the same two tables (`Table 1` has two columns, `Table 4` three) gives column names from `Table 1` plus `Extra_3`:

| Invoice | Amount | Extra_3 |
|---|---|---|
| A1 | 10 | null |
| B1 | 20 | x |

## Edge cases and limits

- **One connected input** passes through unchanged.
- **Row cap:** none. The live preview shows the first 100 rows of the result; Run stacks everything. See [Live preview and Run](../input-output/index.md#live-preview-and-run).
- **Type conflicts.** When the same column (or position, or Manual row) has different types across inputs, it is converted to text for all of them, and a warning appears in the node's tooltip. Text-to-text and number-to-number needs no conversion.
- **Names are case-sensitive** in Auto by Name: `Amount` and `amount` become two columns.
- **Disconnected or empty upstream nodes** are skipped. If none produces data the tooltip says "Upstream nodes produced no output".
- **Manual with no valid rows** falls back to the Auto-by-Name layout.
- If stacking fails for any reason the node is marked invalid with the tooltip "Union failed" (the technical detail is in the log).
- Adding or removing a connection while the Manual grid is open rebuilds the grid so that the new input's columns appear.

## Errors and messages

Union does not raise `TD-` codes. It reports on the node tooltip:

| Message | What it means |
|---|---|
| Connect at least one input | Nothing is connected. |
| Upstream nodes produced no output | The connected nodes have errors or no data; fix them first. |
| Union failed | The tables could not be stacked. Check the column types; look in the log for details. |
| Column 'X' has conflicting types (...); coerced to String. | A warning, not an error. The column was turned into text. |

## Tips

- Prefer Auto by Name when the tables come from the same system. Use Manual when the tables come from different systems and the same field has different names.
- To record which table a row came from, add a source column to each input before the Union (a Formula writing the table name), or have File Input add the filename.
- If you only have two tables, [Append](append.md) is simpler.


Back to the [Join node index](index.md).
