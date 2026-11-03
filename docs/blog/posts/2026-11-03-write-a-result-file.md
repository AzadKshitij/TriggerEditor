---
date: 2026-11-03
categories:
  - How-to
---

# Write a result to a file

Most workflows end by saving a result. This post shows the File Output node: the
settings, the formats, and the one thing that stops people, which is that nothing is
written until you run the workflow.

You need a workflow with at least one table to save, such as the output of
**Normalize** from the [first workflow post](2026-11-03-first-workflow-duplicates.md).

<!-- more -->

## 1. Add File Output

Open the **Input** tab in the palette and drag **File Output** onto the canvas. Connect
the table you want to save to its input socket.

## 2. Choose a path and format

Select **File Output**. In **File**, type a full path such as
`C:\Work\Orders\clean_orders.csv`, or click **Browse for save location**. Choose the
**Format**: CSV, Parquet, Excel, JSON or NDJSON.

Use a folder you can write to. If the file is open in Excel, the run stops with a
message that names the file. Close it and run again.

## 3. Run it

Click the **play** button (tooltip **Run workflow**). File Output writes when its node
runs, and the Logs tab records the file that was written.

## 4. Check the file

Open the file in the folder you chose. Its row count should match the preview after a
Run, not the 100-row sample.

## Common questions

- **Nothing appeared on disk.** Did you press Run? Editing and previewing never write
  a file.
- **The file is replaced on the next Run.** File Output writes the same path each
  time it runs. Copy the file first if you need the old version. (Workpaper Output has
  its own rule for an existing file, described in the [workpapers guide](../../guide/workpaper.md).)

For the full settings, see the [node reference](../../nodes/input-output/file-output.md).
