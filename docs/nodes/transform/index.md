# Transform nodes

The **Transform** tab holds seven nodes that change the *shape* of a table: count it, add running
totals, turn columns into rows (or rows into columns), compare each row with its neighbours, or
rewrite the whole table with SQL. The other families are in the [node index](../index.md).

All seven icons are purple, the colour of the Transform family.

> **Arrange is not a node.** You may see "Arrange" mentioned next to the Transform family in older notes. It
> is the canvas *Arrange* menu (align and distribute the nodes you selected), not something you put in a
> workflow.

## Nodes in this family

| Icon | Node | What it does |
|---|---|---|
| ![Count](../../assets/node_icons/Transform/Count.svg) | **[Count](count.md)** | Returns the number of rows as a one-row table. |
| ![Running Total](../../assets/node_icons/Transform/Running%20Total.svg) | **[Running Total](running-total.md)** | Adds a cumulative sum column, optionally per group. |
| ![Transpose](../../assets/node_icons/Transform/Transpose.svg) | **[Transpose](transpose.md)** | Turns chosen columns into Name and Value rows. |
| ![Pivot](../../assets/node_icons/Transform/Pivot.svg) | **[Pivot](pivot.md)** | Turns the values of one column into columns and totals a value column in each. |
| ![Unpivot](../../assets/node_icons/Transform/Unpivot.svg) | **[Unpivot](unpivot.md)** | Stacks several columns into a name column and a value column. |
| ![Window](../../assets/node_icons/Transform/Window.svg) | **[Window](window.md)** | Adds previous or next row, row number, rank, running and rolling figures. |
| ![SQL Query](../../assets/node_icons/Transform/SQL%20Query.svg) | **[SQL Query](sql-query.md)** | Runs one read-only SELECT over up to three tables (`t1`, `t2`, `t3`). |

## How these nodes behave

**A node runs when you leave its settings.** Edits in the Config Dock are saved at once, but the Transform
nodes recalculate only when you click another node, click the canvas, save or run. Until then the node shows
a yellow "!" badge (tooltip "Changes pending - the node runs when you click away"). See
[Live preview versus Run](../index.md#preview-versus-run).

**The preview uses 100 rows.** While you edit, each Transform node works on the first 100 rows of its input
and shows at most 100 output rows. A **Run** uses every row. So a Count in the preview can only say "100", a
Pivot may be missing a header that appears later in the file, and a running total only covers the sample.
Check the full result after a Run: the Data Preview dock labels a table *evaluated · not run* (preview) or
*from Run*.

**Column types.** A CSV or text file arrives with every column as text. Pivot, Window, Running Total and SQL Query can read
text that holds numbers. Use a *Select* node to change a column's type.

**Errors.** A mistake in the settings turns the node red. The Problems dock shows a short message, a hint
and a code. The codes you can meet in this family:

| Code | Message | What to do |
|---|---|---|
| `TD-SHAPE-001` | A required setting is missing | Fill it in (for example, the header column of a Pivot) |
| `TD-SHAPE-002` | An output column name is empty, duplicated or already exists | Choose a unique name |
| `TD-SHAPE-003` | A selected column is not in the input any more | Select the column again; it was renamed or removed upstream |
| `TD-SHAPE-004` | A setting value is out of range or unknown | Pick a value inside the range |
| `TD-SHAPE-005` | A required input has no data | Connect the input and fix the upstream node ("Input 1 has no data") |
| `TD-SHAPE-060` | Index, header and value columns must be different | Pick three different columns (Pivot); a column cannot be both kept and unpivoted (Unpivot) |
| `TD-SHAPE-061` | Too many new columns | The Pivot header has more than 500 distinct values; filter first |
| `TD-SHAPE-091` | The column must be a number | Pick a numeric column, or text that holds numbers (Window) |
| `TD-SHAPE-110` to `-115` | SQL guard messages | See [SQL Query](sql-query.md) |

---

