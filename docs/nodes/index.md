# Node reference

Every node in the Trigger Designer palette, grouped by the six tabs you see above the canvas (the same
groups appear in the Shift+A menu). Each node has its own page: what it is for, every setting in the Config
Dock, a worked example, and the messages it can show.

| Family | Page | Nodes |
|---|---|---|
| Input and Output | [Input and Output nodes](input-output/index.md) | File Input, File Output, Workpaper Output |
| Preparation | [Preparation nodes](preparation/index.md) | 16 nodes: clean, filter, calculate, sort, select |
| Join | [Join nodes](join/index.md) | Join, Append, Union, Reconcile, Fuzzy Match |
| Transform | [Transform nodes](transform/index.md) | Count, Running Total, Transpose, Pivot, Unpivot, Window, SQL Query |
| Report | [Report nodes](report/index.md) | Graph, Data Profile, Comment |
| Audit | [Audit nodes](audit/index.md) | Duplicates, Gaps, Benford, Sample, Risk Filters |

## Choosing a node

| I want to... | Use |
|---|---|
| Load a file, or save a result | File Input, File Output |
| Tidy messy text, spaces or types | Cleansing, Find and Replace, Normalize, Select |
| Keep only some rows | Filter, Select Records, Unique |
| Add a calculated column | Formula, Multi-Field Formula, Date Helper |
| Total or count per vendor, account or month | Aggregate (Preparation) |
| Count the rows of a table | Count |
| Add a running balance | Running Total (numbers) or Window (any running figure) |
| Compare each row with the previous one, or rank within a group | Window |
| Rotate month columns into rows | Unpivot (or Transpose) |
| Build a matrix of two categories | Pivot |
| Add records from one file to another | Append, Union |
| Look up values from another table | Join |
| Match payments to invoices with a tolerance | Reconcile |
| Match names that are spelled differently | Fuzzy Match |
| Write a query that no node covers | SQL Query |
| Find repeated invoices | Duplicates |
| Find missing cheque or journal numbers | Gaps |
| Test whether amounts look natural | Benford |
| Select items to test | Sample |
| Spot weekend, round-sum or just-under-limit entries | Risk Filters |
| Understand a new file | Data Profile |
| Show a chart or leave a note | Graph, Comment |

<a id="preview-versus-run"></a>

## Live preview versus Run

You work on the canvas with a **preview**; you get the real answer when you press **Run**.

**The preview is a 100-row sample.** As soon as a file is opened or a setting is changed, each node
calculates its output so you can see the effect. To keep a large workbook responsive, File Input and every
node after it work on the **first 100 rows** of each table in this preview, and show at most 100 rows of each
output. The limit is the same for every node (`LIVE_SAMPLE_ROWS` in the code). In the preview, a Count says
"100", a total is a total of the sample, and a Pivot may be missing a header that first appears on row 5,000.
Some nodes warn you (Count shows "First 100 rows only: full count at Run"; Data Profile, Reconcile, Fuzzy
Match and Date Helper say the same in their own words).

**Run uses every row.** **Run** recalculates every node in order, reading the whole input, writes the File
Outputs and records the run. Trust the Run, not the preview, for counts, totals, audit results and the files
you hand over. After a Run, the Data Preview dock labels each table *from Run*; a preview table is labelled
*evaluated · not run*, and its tooltip repeats the 100-row rule.

**A node runs when you leave its settings.** Changing a setting saves it at once and marks the node with a
yellow "!" (tooltip "Changes pending - the node runs when you click away"). The node recalculates when you
select another node, click the empty canvas, or close the document, and then everything after it updates.
So after typing, click away to see the result. Save and Run keep the pending change in the workflow and
Run recalculates everything anyway.

Exceptions to the "click away" rule: the **Audit** nodes, **Data Profile** and **Comment** update as soon as
you change a setting. A few nodes do not run on 100 rows even in the preview: Benford reads up to a million
rows, and Sample does not draw at all on more than 200,000 rows until you Run.

If a preview result disagrees with the Run, believe the Run.
