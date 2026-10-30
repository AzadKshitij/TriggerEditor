# Trigger Designer user guide

Trigger Designer is a desktop program for building data checks without writing code. You draw a **workflow** on a canvas: read a file, clean it, test it (for duplicates, gaps, Benford's law and similar audit tests), and write the result. Everything runs on your own computer, and every run leaves a verifiable record.

This guide is for auditors and analysts who use the program. It is task-oriented and avoids programming terms.

## On this page

- [Where to find what](#where-to-find-what)
- [Conventions used in this guide](#conventions-used-in-this-guide)
- [Your first workflow in 10 minutes](#your-first-workflow-in-10-minutes)
- [Where to go next](#where-to-go-next)

## Where to find what

| I want to... | Read |
|---|---|
| Learn the screen, add nodes, connect them, undo, arrange | [The canvas and nodes](canvas-and-nodes.md) |
| Change a node's settings, look at data, read the logs and the problem list | [The Config Dock, Data Preview, Logs and Problems](config-dock-and-preview.md) |
| Understand the difference between the quick preview and a real Run | [Running workflows](running-workflows.md) |
| Understand an error message, or look up a `TD-` code | [Errors and problems](errors-and-problems.md) |
| See the evidence of what I ran, verify it, compare two runs | [Run history and the audit trail](run-history-and-audit-trail.md) |
| Know what a `.tds` file is, which files I can read and write, how paths are stored | [Files and formats](files-and-formats.md) |
| Change the theme, shortcuts, error and audit settings | [Preferences](preferences.md) |
| Know what the program does and does not guarantee, and how to open a workflow from someone else | [Security and privacy](security-and-privacy.md) |
| Know how big my data can be and how to keep things fast | [Limits and performance](limits-and-performance.md) |
| Fix a common problem, or look up a word | [Troubleshooting, FAQ and glossary](troubleshooting-and-faq.md) |
| Find out what a particular node does | [Node reference](nodes/README.md) |
| Run a workflow unattended from the command line | [Command line](cli.md) |
| Produce a formatted Excel workpaper | [Workpapers](workpaper.md) |

## Conventions used in this guide

- **Bold** is a name you will see on the screen: a menu entry, a button label, a panel title.
- A path of names joined with `>` is a menu: **File > Open Recent** means open the **File** menu, then **Open Recent**.
- `Code font` is a key, a file name or a code you may see, such as `Ctrl+S` or `TD-SCH-001`.
- Most buttons in the program are **icons only**. Hover over one to read its name.
- "The sample" means the first 100 rows of each input, which the program uses while you edit. "A Run" means processing all the data.

## Your first workflow in 10 minutes

You will find duplicate order numbers in a retail orders file. The workflow is four steps:

```text
File Input  ->  Normalize  ->  Duplicates  ->  File Output (x2)
 read the        tidy the        test for        write the duplicates
 CSV             column names    duplicates      and the summary
```

The sample file is `savedfiles\Example_2_Retail_Ledger\data\orders.csv` in the Trigger Designer folder: 40,800 orders with deliberately messy headers such as ` Order ID ` (with spaces). If you work from an installed copy without that folder, use any CSV of your own that has an order, invoice or document number column and set the column name accordingly.

### 1. Start and make a new workflow

1. Start Trigger Designer. The **Welcome to Trigger Designer** dialog opens.
2. Click **New Project**. (Or close the dialog and choose **File > New**, `Ctrl+N`.)

An empty canvas opens as a tab, with the node palette across the top (tabs **Input**, **Preparation**, **Join**, **Transform**, **Report**, **Audit**), the **Node Configuration** panel on the left, and the **Logs**, **Data Preview**, **Problems** and **Run History** tabs at the bottom.

### 2. Read the file

1. In the palette, click the **Input** tab and drag **File Input** onto the canvas.
2. With the node selected, the Node Configuration panel shows its settings. Click the folder icon next to **Source** (tooltip **Browse for file**) and choose `orders.csv`. You can also paste the path into the box.
3. The node recomputes. Open **Window > Data Preview** (`Ctrl+Shift+D`). You see the first 100 rows. The badge reads **evaluated - not run**: this is the sample, not the whole file.

Look at the column names: the first one is ` Order ID ` with spaces. We will tidy that.

### 3. Clean it

1. Press `Shift+A` over the empty canvas. In the search box that opens, type `Norm` and press `Enter`. A **Normalize** node appears at the pointer. (You could also drag it from the **Preparation** tab.)
2. Drag from the round socket on the right of **File Input** to the socket on the left of **Normalize**.
3. Click **Normalize**. Its default settings (**Trim spaces** and **Spaces to underscores**) are what we want. Click the empty canvas to let it compute, then look at the Data Preview: the first column is now `Order_ID`.

### 4. Test it

1. Add a **Duplicates** node from the **Audit** tab (or `Shift+A` and type `Dup`). Connect **Normalize** to it.
2. The node shows a red "!" and a tooltip "Choose the key column." (`TD-AUDIT-001`). That is the program asking you for the one thing it needs.
3. Select **Duplicates**. In the **Match on** section click **None**, then tick only **Order_ID**. Leave **Match type** on **Exact**.
4. Click the empty canvas. The red mark goes. In the **Result** section, press the refresh icon (**Count exceptions now**): the sample has no duplicates.

That is correct for the sample and misleading for the file. The planted duplicates are further down. Only a Run looks at everything.

### 5. Write the result

**Duplicates** has three outputs, marked `D` (the duplicate rows), `U` (the unique rows) and `S` (a one-row summary of the test).

1. Add a **File Output** node (**Input** tab). Connect the `D` socket of **Duplicates** to it.
2. Select it. In **File** type a full path such as `C:\Work\Orders\duplicates.csv` (or use the icon **Browse for save location**). The **Format** is CSV.
3. Add a second **File Output**, connect the `S` socket to it, and give it the path `C:\Work\Orders\summary.csv`.

Nothing is written yet; File Output only writes when you Run.

### 6. Save

Press `Ctrl+S`, choose a folder and name the workflow `orders_check.tds`. The tab title loses its asterisk.

### 7. Run

1. Click the **play** button at the top-left of the canvas (tooltip **Run workflow**). It turns into a stop button while the Run is in progress.
2. Each node lights up purple, then green, as it finishes. For a file this size it takes a moment.
3. Open the **Logs** tab: it ends with the summary of the Run and a line "Run log saved: ...".

### 8. Look at the result

1. Select **Duplicates** and look at the **Data Preview** (choose the `S` socket in the socket chip at the top). The badge now says **from Run**. The summary says it found duplicates: **1590 of 40800 rows are in 790 duplicate groups.**
2. Choose the `D` socket to see the duplicate rows. They also have two extra columns, `dup_group_id` and `dup_count`.
3. Open `duplicates.csv` and `summary.csv` in the folder you chose. They hold the same rows. (`duplicates.csv` has 1,590 rows, `summary.csv` has 1.)

### 9. Look at the evidence

1. Open **Window > Run History**. Run 1 is listed, status `ok`.
2. Click the **Verify run log** icon. The status line says "chain verified ... head xxxxxxxx".
3. Select the run and read the **Summary** pane: the fingerprint of the input file, the number of nodes, the row-count mode.
4. Click **Export selected run as HTML report** to save a page you can attach to a workpaper.

Run it again later on an unchanged file: run 2 appears, and selecting both runs then pressing **Compare two selected runs** shows no differences. Change the Duplicates key, run again, and the comparison lists the changed setting. See [Run history and the audit trail](run-history-and-audit-trail.md).

### If something goes wrong

| Symptom | What to do |
|---|---|
| The Data Preview says "Select a node to preview its output" | Click a node first. |
| Normalize still shows ` Order ID ` | Click the empty canvas to let the node recompute; check the connection from File Input. |
| The Duplicates node keeps its red mark | Make sure at least one column is ticked under **Match on**. |
| The Run does not start | Look for a loop or for another Run in progress. See [Running workflows](running-workflows.md). |
| An error names a file | The file is probably open in Excel; close it and Run again. See [Troubleshooting](troubleshooting-and-faq.md). |
| You want to start over | **File > New**, or close the tab and discard changes. |

## Where to go next

- Browse the [node reference](nodes/README.md) to see what else the palette offers.
- Open one of the examples in `savedfiles\` (for instance `1. in-select.tds`, with its data in `data\`) to see finished workflows. The folder `savedfiles\Example_2_Retail_Ledger\` holds a larger exercise with a step-by-step setup guide.
- Read [Security and privacy](security-and-privacy.md) before opening workflows that someone else sent you.
