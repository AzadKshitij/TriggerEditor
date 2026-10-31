# Trigger Designer

Trigger Designer is a desktop workbench for building data pipelines as a graph of
nodes. You read a file, clean and shape it, test it, and write the result, all on
a canvas. You configure each step in a panel beside the canvas, and the app shows
you the data as you go.

![The Trigger Designer window: node canvas, palette, Config Dock and logs](assets/screenshot_main.webp){ .screenshot }

You do not write code to use it. You drag nodes, connect their sockets, and fill
in the settings. Workflows are saved as portable `.tds` files you can share with
a colleague or run unattended from the command line.

## Who it is for

- **Auditors and analysts** who need repeatable checks over ledgers, journals and
  transaction lists.
- **Anyone** who receives a messy spreadsheet or export and needs a clean,
  documented result without writing a script.
- **Reviewers** who must show what was run, on which file, with which settings.

Everything runs on your own computer. Every Run leaves a record you can verify.

## The shape of every pipeline

Most workflows follow the same four steps:

```text
Input  ->  Prepare  ->  Test  ->  Output
read       clean,       audit     write the
the file   shape        checks    result
```

1. **Input.** File Input reads CSV, text, Excel, Parquet, JSON, SQLite or DuckDB.
2. **Prepare.** Preparation nodes fix types, trim text, filter rows, calculate
   columns, sort, aggregate and reshape.
3. **Test.** Audit nodes find duplicates, gaps, Benford outliers and risky
   entries, and draw repeatable samples.
4. **Output.** File Output writes CSV, Parquet, Excel, JSON or NDJSON. Workpaper
   Output builds a formatted Excel workpaper.

Join and Transform nodes sit between these steps when you need to combine tables
or change their shape.

## Start here

| I want to... | Read |
|---|---|
| Build my first workflow in ten minutes | [Getting started](guide/README.md) |
| Understand the screen, sockets and undo | [The canvas and nodes](guide/canvas-and-nodes.md) |
| Know what a node does and how to set it up | [Node reference](nodes/index.md) |
| Understand preview versus Run | [Running workflows](guide/running-workflows.md) |
| Read an error code | [Errors and problems](guide/errors-and-problems.md) |
| Show what I ran | [Run history and the audit trail](guide/run-history-and-audit-trail.md) |
| Produce an Excel workpaper | [Workpapers](guide/workpaper.md) |
| Run a workflow unattended | [Command line](guide/cli.md) |

## Two habits that save trouble

**Preview is a sample.** While you edit, every node works on the first 100 rows.
Counts, totals and audit results in the preview describe that sample. Press
**Run** before you quote a number or hand over a file.

**Click away after typing.** A setting is saved as you type, but the node
recalculates when you select another node or click the canvas. The yellow mark on
a node means a change is waiting to run.
