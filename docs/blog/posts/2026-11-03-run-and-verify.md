---
date: 2026-11-03
categories:
  - How-to
---

# Run a workflow and check its audit trail

A **Run** processes all the data, not the sample. Each Run also leaves a record that
you can check later. This post follows the record from the first Run to a
comparison of two Runs.

You need a saved workflow that has finished one Run, such as the one from the
[first workflow post](2026-11-03-first-workflow-duplicates.md).

<!-- more -->

## 1. Open Run History

Open **Window > Run History**. Run 1 is listed with the status `ok`.

## 2. Verify the record

Click the **Verify run log** icon. The status line reports that the chain is verified,
with a short code shown as the head of the chain. A verified chain means the record
has not been changed since it was written.

## 3. Read the summary

Select the run and read the **Summary** pane. It shows:

- a fingerprint of each input file, so you can tell whether the file changed;
- the number of nodes that ran;
- how row counts were taken.

## 4. Export a report

Click **Export selected run as HTML report** and save the page. You can attach it to a
workpaper or send it to a reviewer.

## 5. Compare two runs

Run the workflow again on the same, unchanged file. Run 2 appears in the list.
Select both runs and press **Compare two selected runs**. With no changes, the
comparison shows no differences.

Now change the duplicate key, run again, and compare. The comparison lists the setting
that changed. That is the point of the record: you can show exactly what differs
between two runs.

## Where the record lives

Run records are saved in a `<workflow name>.runs` folder next to the workflow file.
Keep that folder with the workflow if you share it. The record can be read, but
changing it breaks the verification.
