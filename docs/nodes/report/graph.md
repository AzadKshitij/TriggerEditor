# Graph

![Graph icon](../../assets/node_icons/Report/Graph.svg){ .node-icon }

## Purpose

Graph draws a chart of the table it receives, in its own window. It passes the table on unchanged, so you can put it in the middle of a workflow without disturbing anything.

## When to use it

- See how amounts change over time (a line chart of totals by month).
- Compare groups (a bar chart of the amount per vendor).
- Look for outliers and clusters (a scatter chart of amount against quantity).

It is for looking at data, not for producing a report file. The chart window lets you save a picture.

## Inputs and outputs

| Socket | Carries |
|---|---|
| Input (left) | The table to chart. |
| Output `Out` (right) | The same table, unchanged. |

## Settings

The Config Dock has one section. The **Show graph** icon button sits on the top row of the dock.

| Control | What it does | Default |
|---|---|---|
| **Show graph** (icon button) | Opens the chart in its own window. It is switched on only after a **successful Run**, with X and Y chosen. Its tooltip says why it is off: "Show graph (run the workflow first)" or "Show graph (no data to draw)". If the window is already open, it is brought to the front. | Off until a Run |
| **Type** | **Line**, **Bar** or **Scatter**. | Line |
| **Renderer** | The library that draws the chart: **matplotlib** or **pyqtgraph**. matplotlib uses its standard navigation toolbar; pyqtgraph replaces it with **reset view** and **save PNG** buttons. This only changes the look and the toolbar, never the data. | matplotlib |
| **X column** | The column for the horizontal axis. The list shows `(select column)` until you pick one. | Empty |
| **Y column** | The column for the vertical axis (the values). | Empty |
| **Color by** | Splits the data into one coloured series per value of this column (for example one line per region). `(none)` turns it off. | None |
| **Aggregate** | How to combine rows that share the same X (and colour): **None**, **Sum**, **Count**, **Mean**, **Median**, **Min**, **Max**. For a bar chart the default is **Sum**; for line and scatter it is **None** (one point per row). | Depends on Type |
| **Title** | Optional chart title, also shown in the window title. | Empty |

Details:

- A column you chose that later disappears from the input stays selected and is shown as `name (missing)`. The chart then reports the problem instead of drawing.
- The chart window follows your changes: edit a setting while it is open and the chart redraws after a short pause.
- With Type **Bar**, Aggregate shows **Sum**, because that is what a bar chart does unless you say otherwise. Choose **None** to draw one bar per row.
- After you reopen a saved workflow, the **Show graph** button is off again until you Run the workflow.
- The window title reads "Graph", "Graph - your title", and adds the renderer name when it is not matplotlib.
- Under the chart, a status line describes what is drawn, for example `3 points · sum of Sales per Month`, `5 points · colored by Region`, or `2,000 points shown (truncated)`.

## Worked example

A table of sales:

| Month | Region | Sales |
|---|---|---|
| Jan | N | 100 |
| Jan | S | 50 |
| Feb | N | 120 |
| Feb | S | 70 |
| Mar | N | 90 |

**Bar chart, X = Month, Y = Sales, Aggregate = Sum (the default).** The bars drawn are:

| Month | Bar height |
|---|---|
| Feb | 190 |
| Jan | 150 |
| Mar | 90 |

Status line: `3 points · sum of Sales per Month`. Note the order: text X values are sorted alphabetically (Feb, Jan, Mar), not by calendar. Use a real date, or a number such as 202501, to get time order.

**Aggregate = Mean** gives Feb 95, Jan 75, Mar 90.

**Line chart, X = Month, Y = Sales, Color by = Region.** One line per region: `Region: N` with Feb 120, Jan 100, Mar 90, and `Region: S` with Feb 70 and Jan 50. Status line: `5 points · colored by Region`.

**Count.** X = Region, Y = Month, Aggregate = Count draws a bar of 3 for N and 2 for S. Count works with any Y column; the other aggregates need a number.

## Edge cases and limits

- **Live preview vs Run.** The chart is built from the table the node last received. While you edit upstream, that is the first 100 rows; after a Run it is the full result. The **Show graph** button only opens after a Run, so you normally see the full data. See [Live preview and Run](../input-output/index.md#live-preview-and-run).
- **Points are capped at 2,000.** With no aggregation, only 2,000 rows are drawn (for a line chart, the first 2,000 after sorting by X) and the status line says "(truncated)". With aggregation, the whole table is summarised first, and the number of distinct X groups is capped at 2,000. Summarise first (the Aggregate node in [Preparation nodes](../preparation/index.md)) if you have more groups than that.
- **Order.** Line charts sort by X (ties keep the input order). Aggregated charts also sort by X. A scatter or bar chart with Aggregate = None keeps the input order.
- **Nulls.** A null X sorts last.
- **Aggregations need numbers** (except Count). If Y is text you get the message below; convert it with a Select node.
- **Empty table.** You get "No rows to plot."
- Graph itself never writes a file. Only the save button in the chart window does, and only when you press it.

## Messages you may see

Graph does not raise `TD-` codes; the chart window and the status line describe the problem in plain words.

| Message | Meaning and fix |
|---|---|
| No incoming data. | Nothing is connected, or the upstream node has an error. |
| Graph needs a table input. | The input is not a table. |
| Select an X column. / Select a Y column. | Choose the columns in the dock. |
| X column 'name' is not in the incoming data. (same for Y) | The column was renamed or removed upstream. Pick it again. |
| Y column 'name' must be numeric for sum. | The chosen aggregation needs numbers. Convert the column, or choose Count. |
| X and Y must differ to aggregate. | Choose two different columns. |
| Color by must differ from X and Y. | Choose another column for colour. (A colour column that no longer exists is ignored.) |
| No rows to plot. | The table is empty after the settings are applied. |
| No data to plot. | Nothing could be drawn. |
| Could not build the chart: ... | The data could not be read; the message gives the reason. |

## Tips

- Put a Graph after an Aggregate node so that you chart totals, not raw rows.
- To check amounts for outliers, use Scatter with X = a number or date and Y = amount, with Aggregate = None.
- A chart is a working-paper aid. For a number to quote, use a [Data Profile](data-profile.md) or a summary table.


Back to the [Report node index](index.md).
