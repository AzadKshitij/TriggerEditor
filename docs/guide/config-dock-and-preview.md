# The Config Dock, Data Preview, Logs and Problems

Around the canvas there are four panels. The **Node Configuration** dock (the Config Dock) is where you set up a node. The bottom panels (**Data Preview**, **Logs**, **Problems** and **Run History**) share one tab bar and show what the workflow is doing and what it produced.

[Back to the guide index](README.md)

## On this page

- [Show, hide and arrange the panels](#show-hide-and-arrange-the-panels)
- [Config Dock](#config-dock)
- [Data Preview](#data-preview)
- [Logs (the Logging dock)](#logs-the-logging-dock)
- [Problems](#problems)
- [If something goes wrong](#if-something-goes-wrong)

Run History has its own page: [Run history and audit trail](run-history-and-audit-trail.md).

## Show, hide and arrange the panels

All panels are in the **Window** menu.

| Menu entry | Panel | Where it opens |
|---|---|---|
| Node Configuration | Config Dock | Left of the canvas |
| Show Logger | Logs | Bottom |
| Data Preview (`Ctrl+Shift+D`) | Data Preview | Bottom, in the same tab bar as Logs |
| Problems | Problems | Bottom, in the same tab bar |
| Run History | Run History | Bottom, in the same tab bar |
| Nodes Toolbar | The node palette | Top |

You can drag a panel's tab out of the tab bar to float it, or drag a panel to another edge. The app remembers the layout when you close it (switch this off in **Edit > Settings > Layout**). **Window > Save Current Layout** stores the arrangement now; **Window > Reset Layout** puts everything back where it started.

Every panel follows the workflow window that is in front. If you have two workflows open, switching tabs switches what the panels show. Each workflow has its own logs, problems and preview.

## Config Dock

The Config Dock shows the settings of the **one** selected node. Its title names the node: "Node Configuration (Duplicates)". With nothing selected, or with several nodes selected, it is empty.

From top to bottom:

1. **Label** - an optional note shown above the node on the canvas (see [Labels and groups](canvas-and-nodes.md#labels-and-groups)).
2. The node's own sections, for example **Match on**, **Match type** and **Result** for Duplicates. Each node is described on its page in the [node reference](nodes/README.md).

Hover the title area of the dock for a one-line summary of how the node is set up.

How edits behave:

- **Live.** A change is stored in the workflow immediately. You do not press OK or Apply.
- **Typing is debounced.** Text boxes wait a short moment (about 300 ms) after you stop typing before the edit is recorded.
- **One undo step per change.** The Edit menu says what **Undo** will reverse. See [Undo and redo](canvas-and-nodes.md#undo-and-redo).
- **The node recomputes when you leave it.** Until then the node shows the amber "!" (changes not run yet). Select another node or click the empty canvas to let it recompute on the live sample.
- **Buttons are icons.** Hover one to read its tooltip. Text buttons appear only in dialogs and for the paired **All** / **None** column toggles.
- **Lists of columns** show a check box per column, with **All** and **None** at the top.

The dock does not run the whole workflow. It recomputes the node on the **live sample** (the first 100 rows of each input). See [Running workflows](running-workflows.md#live-evaluation-and-the-100-row-sample).

## Data Preview

Open it with **Window > Data Preview** (`Ctrl+Shift+D`). It shows the output of the node you have selected, in a table.

### The strip at the top

| Control | What it does |
|---|---|
| Node chip | The name of the node on display. |
| Socket chip | Appears only when the node has several outputs (for example Duplicates `D`, `U`, `S`). Choose which output to show. |
| Search box ("Search this preview...") | Filters the rows you can see as you type (`Ctrl+F` jumps to it). The scope list next to it limits the search to one column; the default is all columns. |
| Source badge | **from Run** means the table is the output of the last Run. **evaluated - not run** means it was computed by live evaluation on the first 100 rows of each input. Hover the badge to read this. |
| Counts chip | For example `1,000 / 48,213 rows - 17 cols`: rows shown, rows collected, total rows in the source. "counting..." means the total is still being worked out. A **limited** tag means the preview stopped at its size cap. |
| Pin | Freezes the panel on the current node so that selecting other nodes no longer moves it. Pin a node, then click around while you compare. |
| Refresh (`Ctrl+R`) | Collects the table again. |
| Options (three dots) | **Copy as TSV**, **Export CSV...**, **Export Excel...**, **Open in standalone window**, **Unpin**. |

If the pinned node is deleted, the panel says "Pinned node is no longer in the scene" and unpins itself.

### What you see

| Situation | What the preview shows |
|---|---|
| The workflow has been Run, and you have not edited the node since | The result of the Run (badge: **from Run**). |
| You edited the node, or have not yet Run | The live sample: at most 100 rows per input (badge: **evaluated - not run**). |
| The node has no table output, or has a problem | "No previewable data on this socket", or the table of a different socket. |
| The node has no rows | "No rows". |
| Nothing selected | "Select a node to preview its output". |

An edit after a Run makes the preview go back to the live sample for that node, because the Run's table no longer matches the settings.

### How much is shown

The preview collects at most **1,000 rows** or about **2 MB**, whichever is smaller. That is a window onto the result, not the whole result. The counts chip tells you if more rows exist in the source.

### Exporting from the preview

**Export CSV...** and **Export Excel...** write **the rows currently collected in the preview** (and, if you have typed in the search box, only the rows that match). They do **not** re-run the node or write the complete output. To save a full result, use a **File Output** node and Run.

- **Export CSV...** asks for a file name (default `dataframe_export.csv`).
- **Export Excel...** asks for a file name (default `dataframe_export.xlsx`).
- **Copy as TSV** copies the table to the clipboard so you can paste it into Excel.

If the Excel file cannot be written, a dialog titled **Export failed** appears: "The Excel file could not be written", followed by the reason (for example the file is open in Excel). Close the file and try again. CSV export shows no dialog on failure; the reason is written to the Logs file only.

### Standalone window

Choose **Options > Open in standalone window**, or alt-click an output socket on the canvas (after a Run), to open the table in a separate resizable window. It has the same search and export controls and does not follow your selection.

## Logs (the Logging dock)

The tab named **Logs** is the app's running commentary for the active workflow: loading the file, evaluating, each Run, and any problems.

| Control | Meaning |
|---|---|
| Level | Show messages at this level or above: TRACE, DEBUG, INFO, WARNING, ERROR, CRITICAL. The default shows everything. |
| Filter | Show only messages that contain this text. |
| Auto-scroll | Keep the newest message in view. |
| Clear | Empty the log of the active workflow. |

Messages are colour coded by level. The dock keeps the last 1,000 messages per workflow.

After a Run, the Logs hold a summary: whether it completed, failed or was cancelled, how long it took, and the line "Run log saved: ..." with the path of the run record (see [Run history](run-history-and-audit-trail.md)). If a Run fails you also get "Run finished with N problem(s)." and the Problems tab comes to the front.

A technical log file for the whole session is also written to disk. It is meant for support: when the app is installed from the packaged build it is in `%APPDATA%\Trigger Designer\logs`, otherwise in a `logs` folder next to the source.

## Problems

The **Problems** tab lists every node that currently has an error or warning, one row per node. Its title carries the count: "Problems (2)".

| Column | Meaning |
|---|---|
| Node | The node's title and label. A red name is an error, an amber one a warning. |
| Code | The stable error code, for example `TD-SCH-001`. Look it up in the [error reference](errors-and-problems.md#error-code-reference). |
| Problem | A one-sentence description. Hover for a longer tooltip. |

Expand a row (the arrow on the left) to see the detail, then lines starting **Fix:** and **Other fix:**, and **Caused by:** when the real problem is in an earlier node.

| Tool | What it does |
|---|---|
| Filter problems | Narrow the list by typing part of a node name, a code or a message. |
| Click a row | Selects that node on the canvas and scrolls it into view. |
| Copy details (icon) | Copies the selected problems (or all of them, if none is selected) as text for an email or ticket. |
| Show technical details (icon, toggle) | Adds the raw engine message and stack trace to the rows and to the copied text. Your choice is remembered. |

The list updates as you fix things: a node's entry disappears as soon as it recomputes cleanly. Problems from the last Run are cleared when the next Run starts.

More on reading and fixing errors is in [Errors and problems](errors-and-problems.md).

## If something goes wrong

| Symptom | What to do |
|---|---|
| The Data Preview is empty | Select a node. If it still says "No previewable data", the node has an error (check Problems) or only a summary output; choose another socket in the socket chip. |
| The preview shows 100 rows only | That is the live sample. Run the workflow to see the Run's result (up to 1,000 rows). |
| The preview and my output file differ in row count | The preview is capped at 1,000 rows or 2 MB. Open the output file, or look at the counts chip for the true total. |
| Export Excel fails | Close the target file in Excel, or pick another name. If the message mentions that Excel export is not available, use Export CSV instead and tell your administrator. |
| Logs are too noisy | Raise **Level** to INFO or WARNING. |
| A panel has vanished | **Window > ...** and tick it again, or **Window > Reset Layout**. |
| The Config Dock layout looks stale after loading a very old file | Click another node and then the first one again. |
