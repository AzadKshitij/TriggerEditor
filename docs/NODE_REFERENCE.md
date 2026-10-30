# Node Reference

Every node available in the Trigger Designer palette, grouped by family. The
op id is the stable identifier stored in saved workflows
(`src/trigger_designer/core/node_configuration.py`); icons live in
`src/trigger_designer/resources/qt/images/node_icons/` and are mapped in
`src/trigger_designer/qt/resources.json`.

## Input / Output

| Node Name | Node Image | Description |
|---|---|---|
| File Input | ![File Input](assets/node_icons/file_input.png) | Reads CSV/TXT, Excel (one, all, or chosen sheets), Parquet, JSON, JSON Lines, SQLite, and DuckDB sources. A file may be a single path, a folder, or a glob; matching files are unioned by column name with a per-file source report and an optional filename/sheet column. Database reads are read-only (one table or one SELECT). "Read all columns as text" makes typed sources behave like CSV; CSV itself always arrives as strings. |
| File Output | ![File Output](assets/node_icons/file_output.png) | Writes the incoming frame to a CSV, Parquet, or Excel file at the configured path. |

## Join

| Node Name | Node Image | Description |
|---|---|---|
| Join | ![Join](assets/node_icons/join.png) | Joins two inputs on a user-defined column mapping using the selected join type. |
| Append | ![Append](assets/node_icons/append.png) | Stacks the rows of the right input underneath the left input. |
| Union | ![Union](assets/node_icons/union.png) | Stack two or more inputs vertically (columns matched by name or manual mapping). |
| Reconcile | ![Reconcile](assets/node_icons/reconcile.png) | Matches two inputs on key columns plus an amount tolerance and/or date window, emitting matched pairs, both unmatched sides, and a summary. |

## Preparation

| Node Name | Node Image | Description |
|---|---|---|
| Cleansing | ![Cleansing](assets/node_icons/cleansing.png) | Per-column data cleanup: trim, case, empty-value handling, and dtype coercion. |
| Filter | ![Filter](assets/node_icons/filter.png) | Keeps or drops rows using comparison operations evaluated against chosen columns. |
| Formula | ![Formula](assets/node_icons/formula.png) | Creates or edits calculated columns from SQL-like expressions. |
| GroupBy | ![GroupBy](assets/node_icons/groupby.png) | Collapses rows into groups by key columns and applies aggregations over each group. |
| Select | ![Select](assets/node_icons/select.png) | Chooses which columns to keep, drop, rename, and reorder in the output. |
| Sort | ![Sort](assets/node_icons/sort.png) | Orders rows by one or more columns, each ascending or descending. |
| Split | ![Split](assets/node_icons/split.png) | Splits the data into training and validation datasets for modelling workflows. |
| Unique | ![Unique](assets/node_icons/unique.png) | Removes duplicate rows based on the selected columns. |
| Normalize | ![Normalize](assets/node_icons/select.png) | Renames columns deterministically: trim, collapse internal whitespace, then apply a case rule. |
| Rows | ![Rows](assets/node_icons/dynamic_row_generate.png) | Builds a grid or series of rows from configured patterns, ranges, or literals. |
| Record ID | ![Record ID](assets/node_icons/recordid.png) | Adds a dense numbered column in input order, optionally restarting per group and ordered by chosen columns. |
| Select Records | ![Select Records](assets/node_icons/selectrecords.png) | Keeps the first, last, ranged, largest, or smallest rows and sends the remainder out of the second socket. |
| Find and Replace | ![Find and Replace](assets/node_icons/findreplace.png) | Applies ordered literal or regex replacements across selected text columns, in place or into suffixed columns. |
| Date Helper | ![Date Helper](assets/node_icons/datehelper.png) | Adds date parts, fiscal periods, day differences, holidays, and business-day calculations as new columns. |
| Text to Columns | ![Text to Columns](../src/trigger_designer/resources/qt/images/node_icons/Preparation/TextToColumns.svg) | Splits one text column on a literal delimiter or a regex into new columns (the last takes the remainder) or into one row per piece; errors `TD-SHAPE-044` (not text) and `TD-SHAPE-101` (pattern can match nothing). |

> Normalize reuses the Select glyph (`node_select`) until a dedicated
> icon ships; the source file is `node_icons/Preparation/Select.svg`.

## Transform

| Node Name | Node Image | Description |
|---|---|---|
| Count | ![Count](assets/node_icons/count.png) | Counts rows, overall or per group, and emits the total as a new frame. |
| Running Total | ![Running Total](assets/node_icons/running_total.png) | Adds a column with a cumulative sum of a numeric column, optionally per group. |
| Transpose | ![Transpose](assets/node_icons/transpose.png) | Flips the frame so rows become columns and columns become rows. |
| Pivot | ![Pivot](assets/node_icons/pivot.png) | Turns distinct header values into columns, aggregating a value column per index group. |
| Unpivot | ![Unpivot](assets/node_icons/unpivot.png) | Stacks selected value columns into a name/value pair while keeping the chosen ID columns. |
| Window | ![Window](assets/node_icons/window.png) | Adds one column per calculation (previous/next row, row number, rank, running sum/min/max/mean, rolling sum), optionally restarting per group and ordered by chosen columns. Rows keep their input order. |

## Report

| Node Name | Node Image | Description |
|---|---|---|
| Graph | ![Graph](assets/node_icons/graph.png) | Charts the incoming data in a matplotlib window that unlocks after a successful run; passes its input through unchanged. |
| Data Profile | ![Data Profile](../src/trigger_designer/resources/qt/images/node_icons/Report/Data%20Profile.svg) | Profiles every column of the whole input: nulls, blanks, distinct counts, min/max, numeric statistics and a histogram, the most frequent values, and a suggested type with quality flags (numbers or dates stored as text, mixed dates, leading zeros, stray whitespace, negatives, outliers). Socket `D` passes the input through; socket `P` is a one-row-per-column table (`PROFILE_SCHEMA`, see `docs/plan/05-data-profile-node.md`). The dock shows a sortable table and a per-column detail pane, a **Full report** button (opens an HTML report with a card for every column in the browser) and one **Export** menu (copy, CSV, HTML report, Excel). While you edit, the dock profiles only the first 100 rows the canvas holds (like every node); **run the workflow** and it switches to the profile of all rows, until a setting changes or the next run. Inputs over 150 columns skip the live preview (run the workflow to profile them). Options: sample (all rows, first N, random N with seed), top values, estimate-over threshold for distinct counts, chart bars. |
| Comment | ![Comment](../src/trigger_designer/resources/qt/images/node_icons/Report/Comment.svg) | A note on the canvas with no inputs or outputs; it never executes (the run records it as a no-op and its generated code is `# Comment (not executed)`). The text is saved in the `.tds`; its first line (60 characters at most) is the label shown above the node and is rewritten on every text change. Read comments for the workpaper or run log with `comments_from_scene_dict` / `comments_from_nodes` in `core/shaping/comments.py` (reading order: top to bottom, then left to right; blank notes skipped). |

## What Run verifies

Run recomputes every node first, in graph order, so no step executes with stale
or never-evaluated settings; a step that is still invalid keeps its red state and
is listed in the Logging dock. After each step runs, the plan of every lazy output
is schema-checked: an unknown column, a bad join key or a duplicate output name
fails the step that caused it, with or without a File Output downstream. Errors
that depend on the data itself (for example one value that cannot be cast)
surface only where data is read: File Output, Graph, Count and the Data Preview.

The **Cancel** button replaces Run while a run is in flight. Cancelling is
cooperative: the step that is executing finishes, and the remaining steps are not
started. A loop in the graph refuses to run and leaves Run available.

## Internal (not in the palette)

| Node Name | Node Image | Description |
|---|---|---|
| Unknown | _(none)_ | Placeholder shown when a saved node's op id cannot be resolved; preserves its content so nothing is lost. |

`TriggerNode_Unknown` (`src/trigger_designer/qt/widgets/nodes/unknown.py`) is
deliberately unregistered and never appears in the palette. It also has no
entry in `resources.json`, so `node_unknown` renders blank.

## Icons not yet wired to a node

These SVGs ship in the icon folder but no registered node references them.

| Icon | Source file |
|---|---|
| ![Image](assets/node_icons/image.png) | `node_icons/Report/Image.svg` |
| ![InOut](assets/node_icons/inout.png) | `node_icons/INOUT.svg` |
| ![Browse](assets/node_icons/browse.png) | `node_icons/Input/Browse.svg` |

`Join/find_replace.py` and `Documentation/comment.py` are empty placeholder
files, and `IONodes.BROWSER` / `IONodes.TEXT_INPUT` are registered enum members
with no implementation behind them. The reusable canvas note lives
in the `qtpy-nodeeditor` library instead of an app-specific Report node.

## Regenerating the icons

`docs/assets/node_icons/*.png` are rasterised from the source SVGs at 48x48 so
they sit correctly in a table without an explicit width. Re-render them with:

```python
from pathlib import Path

from qtpy.QtCore import QSize, Qt
from qtpy.QtGui import QImage, QPainter
from qtpy.QtSvg import QSvgRenderer
from qtpy.QtWidgets import QApplication

SRC = Path("src/trigger_designer/resources/qt/images/node_icons")
DST = Path("docs/assets/node_icons")
app = QApplication([])  # noqa: F841

DST.mkdir(parents=True, exist_ok=True)
for svg in sorted(SRC.rglob("*.svg")):
    if "ui" in svg.relative_to(SRC).parts:
        continue  # dock toolbar buttons, not node icons
    out = DST / f"{svg.stem.lower().replace(' ', '_').replace('-', '_')}.png"
    image = QImage(QSize(48, 48), QImage.Format_ARGB32)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing, True)
    QSvgRenderer(str(svg)).render(painter)
    painter.end()
    image.save(str(out), "PNG")
```
