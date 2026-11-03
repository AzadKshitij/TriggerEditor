---
date: 2026-11-03
categories:
  - How-to
---

# Your first workflow: find duplicate rows in a CSV

This post builds one small workflow. It reads a CSV of orders, tidies the column
names, and finds duplicate order numbers. It takes about ten minutes.

You need the portable build from the [install page](../../install.md) and any CSV
with an order or invoice number column.

<!-- more -->

## 1. Start a new workflow

Start Trigger Designer and click **New Project**. An empty canvas opens.

## 2. Read the file

Drag **File Input** from the **Input** tab onto the canvas. Select it, click the folder
icon next to **Source** (tooltip **Browse for file**), and choose your CSV.

Open **Window > Data Preview** (`Ctrl+Shift+D`). The badge reads **evaluated - not run**.
That means you are looking at the first 100 rows, which is a sample.

## 3. Tidy the column names

Press `Shift+A` on the empty canvas, type `Norm`, and press `Enter`. A **Normalize**
node appears. Drag from the right socket of **File Input** to the left socket of
**Normalize**. The default settings (trim spaces, spaces to underscores) are fine.

Click the empty canvas, then look at the preview. A column named ` Order ID ` is now
`Order_ID`.

## 4. Find the duplicates

Add a **Duplicates** node from the **Audit** tab and connect **Normalize** to it.
A red **!** appears: the node needs a key column.

Select **Duplicates**. Under **Match on**, click **None**, then tick `Order_ID`. Leave
**Match type** on **Exact**. Click the empty canvas to clear the red mark.

## 5. Write the result

**Duplicates** has three outputs. `D` holds the duplicate rows, `U` the unique rows,
and `S` a one-row summary.

Add a **File Output** node and connect `D` to it. Set **File** to a full path, such as
`C:\Work\Orders\duplicates.csv`. The format is CSV.

Nothing is written yet. File Output writes only when you run the workflow.

## 6. Save and run

Press `Ctrl+S` and save the workflow as `orders_check.tds`. Then click the **play**
button (tooltip **Run workflow**).

Each node turns purple while it runs, then green. Open the **Logs** tab to see the
run summary.

## 7. Read the result

Select **Duplicates**, then choose the `S` socket in the chip at the top of the Data
Preview. The badge now reads **from Run**, and the summary gives the count of
duplicate rows and groups.

Open `duplicates.csv` in the folder you chose. It holds the duplicate rows with two
extra columns, `dup_group_id` and `dup_count`.

## What to remember

The preview is a sample of 100 rows. Press **Run** before you quote a number. The next
post shows how a run leaves a record you can verify.
