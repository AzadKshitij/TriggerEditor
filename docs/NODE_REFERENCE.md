# Node Reference

Every node available in the Trigger Designer palette, grouped by family. The
op id is the stable identifier stored in saved workflows
(`src/trigger_designer/core/node_configuration.py`); icons live in
`src/trigger_designer/resources/qt/images/node_icons/` and are mapped in
`src/trigger_designer/qt/resources.json`.

## Input / Output

| Node Name | Node Image | Description |
|---|---|---|
| File Input | ![File Input](assets/node_icons/file_input.png) | Reads a CSV, text, or Excel file from disk into the flow as a Polars frame. |
| File Output | ![File Output](assets/node_icons/file_output.png) | Writes the incoming frame to a CSV, Parquet, or Excel file at the configured path. |

## Join

| Node Name | Node Image | Description |
|---|---|---|
| Join | ![Join](assets/node_icons/join.png) | Joins two inputs on a user-defined column mapping using the selected join type. |
| Append | ![Append](assets/node_icons/append.png) | Stacks the rows of the right input underneath the left input. |

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
| Normalize Columns | ![Normalize Columns](assets/node_icons/select.png) | Renames columns deterministically: trim, collapse internal whitespace, then apply a case rule. |
| Generate Rows | ![Generate Rows](assets/node_icons/dynamic_row_generate.png) | Builds a grid or series of rows from configured patterns, ranges, or literals. |

> Normalize Columns reuses the Select glyph (`node_select`) until a dedicated
> icon ships; the source file is `node_icons/Preparation/Select.svg`.

## Transform

| Node Name | Node Image | Description |
|---|---|---|
| Count Records | ![Count Records](assets/node_icons/count.png) | Counts rows, overall or per group, and emits the total as a new frame. |
| Running Total | ![Running Total](assets/node_icons/running_total.png) | Adds a column with a cumulative sum of a numeric column, optionally per group. |
| Transpose | ![Transpose](assets/node_icons/transpose.png) | Flips the frame so rows become columns and columns become rows. |

## Report

| Node Name | Node Image | Description |
|---|---|---|
| Graph | ![Graph](assets/node_icons/graph.png) | Renders the incoming data as a chart in its own resizable window. |

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
| ![Union](assets/node_icons/union.png) | `node_icons/Join/Union.svg` |
| ![Image](assets/node_icons/image.png) | `node_icons/Report/Image.svg` |
| ![InOut](assets/node_icons/inout.png) | `node_icons/INOUT.svg` |
| ![Browse](assets/node_icons/browse.png) | `node_icons/Input/Browse.svg` |

`Join/union.py`, `Join/find_replace.py`, and `Documentation/comment.py` are
empty placeholder files, so `JoinNodes.UNION` and `IONodes.BROWSER` /
`IONodes.TEXT_INPUT` are registered enum members with no implementation behind
them.

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
