# Running workflows

While you build, the app shows you quick results on a small sample. When you press **Run**, it processes the whole data and writes your output files. This page explains the difference and what Run does, step by step.

[Back to the guide index](README.md)

## On this page

- [Live evaluation and the 100-row sample](#live-evaluation-and-the-100-row-sample)
- [Run Workflow](#run-workflow)
- [What a Run does, in order](#what-a-run-does-in-order)
- [When a step fails](#when-a-step-fails)
- [Cancel](#cancel)
- [The run script](#the-run-script)
- [Time and memory limits](#time-and-memory-limits)
- [Workflows with no output node](#workflows-with-no-output-node)
- [If something goes wrong](#if-something-goes-wrong)

## Live evaluation and the 100-row sample

**Live evaluation** is what happens while you edit. Whenever you open a workflow, change a setting, or connect or disconnect nodes, the affected nodes recompute so that you can see their results in the [Data Preview](config-dock-and-preview.md#data-preview) and any problems straight away.

Three rules make live evaluation fast and safe:

1. **It reads a sample.** Each node reads at most the first **100 rows** of each input and shows at most 100 rows of each output. A "from Run" or "evaluated - not run" badge on the Data Preview tells you which kind of table you are looking at. Counts you see while editing describe the sample. For example, a Count node says "First 100 rows only: full count at Run".
2. **It never writes files.** File Output nodes only check their settings while you edit. Files are written only when you Run.
3. **It recomputes in order, once.** If you change a node, the nodes after it recompute in dependency order, a single time each, rather than once per click.

Some inputs are read in full even in live mode, because the reading library cannot read part of them: Excel files, JSON arrays and SQLite or DuckDB databases. See [Limits and performance](limits-and-performance.md).

Most nodes also wait until you **leave** the node before they recompute (the amber "!" mark, see [Reading the signs on a node](canvas-and-nodes.md#reading-the-signs-on-a-node)). This is called **deferred evaluation**: your edit is saved and undoable straight away, but the work happens when you select another node or click the empty canvas.

While a Run is in progress, live evaluation is paused. Edits you make during a Run are queued and applied when it ends.

## Run Workflow

The **Run workflow** button is the round play button at the top-left of the workflow window. There is no menu entry or keyboard shortcut for it.

Only one Run per workflow window can be in progress. Pressing the button while one is running does nothing. While a Run is in progress the play button is replaced, in the same place, by the **Cancel run** (stop) button.

## What a Run does, in order

1. **Settle your edits.** Any text you have typed that is still waiting for its short delay is committed, and any queued live evaluation is flushed.
2. **Order the nodes.** The nodes are sorted so every node comes after the nodes that feed it. If the workflow contains a loop, nothing runs: the edges of the loop are selected on the canvas and the Logs say "The workflow has a cycle. Remove the connection that loops back." The play button is restored.
3. **Clear the last Run's marks.** Previous Run problems and red marks are removed.
4. **Recompute every node (live evaluation of everything).** Each node is marked out of date and recomputed in order, so the Run starts from settings that match exactly what is on the screen. A node that is still invalid keeps its red mark; the Logs say "Warning: N step(s) have problems and may fail or produce empty output", naming up to five.
5. **Run any preparation hooks.** An internal step for nodes that need to prepare before running. Most nodes have none, and a failing hook never stops the Run.
6. **Start the run record** (see [Run history](run-history-and-audit-trail.md)). If recording fails for any reason, the Run still goes ahead.
7. **Run the nodes, one at a time, in order, on a background thread.** The window stays responsive. For each node:
   - The node's purple ring shows it is running.
   - The node's generated code is executed against the **whole** input, not the sample. Most nodes build a *lazy plan* (a description of the work); the data is actually read and processed when something at the end of the plan, such as a File Output, writes it.
   - **Plans are verified.** After a node's code runs, every lazy result has its column layout resolved. This catches a bad column name or a join key that does not exist right at the node that caused it, without reading any data, instead of surfacing later at some distant File Output.
   - If the node succeeded, it gets a green ring and its outputs are kept for the Data Preview. If it failed, it gets a red ring and an error (see [Errors and problems](errors-and-problems.md)).
8. **Finish.** Live evaluation resumes, the run script is written, the run record is sealed, and the Logs show a summary:
   - the result (completed, failed or cancelled),
   - how long this Run took, the number of runs in this session and the average time,
   - "Run log saved: <path>".

   If any node failed, the Problems dock comes to the front.

Green rings fade about a second after a successful Run. Red rings stay until the problem is fixed.

## When a step fails

What happens next depends on **Edit > Settings > General > Error messages > "Keep running independent branches after a failure"** (on by default).

- **On (default).** The Run carries on with every node that does not depend on the failed one. A node whose upstream failed, or was itself skipped, is **not executed**: it gets the warning `TD-RUN-008` "Skipped because 'X' failed" (not a red error; the node is not marked invalid) and its status in the run record is `skipped`. The failed node is recorded as `failed`, the independent branches as `ok`, and the Run as a whole is `failed`. Files written by the independent branches stay on disk.
- **Off.** The Run **stops at the first failed node**. Nodes after it do not run and are not marked as skipped (in the run record they are listed as `skipped`). Files written by nodes that finished before the failure stay on disk.

The Problems dock lists the failed node as the problem; the skipped nodes' `TD-RUN-008` warnings are knock-on entries that clear when you fix the first node and Run again. The command-line runner has its own flag for the same behaviour; see [cli.md](cli.md).

After a failed Run:

1. Open **Problems** and click the first row. It selects the failing node.
2. Read the message and fix. See [Errors and problems](errors-and-problems.md).
3. Run again.

A failed Run is recorded too: its status is `failed` and the failing node has the error.

## Cancel

Click the stop button (tooltip **"Cancel run (stops after the current step)"**).

Cancel is **cooperative**:

- The node that is executing right now **finishes**. It is not interrupted.
- Every node after it is **skipped**.
- The button greys out and its tooltip changes to "Cancelling after the current step finishes". The Logs say "Cancel requested - stopping after the current step finishes", then "Run cancelled".
- Files that earlier nodes had already finished writing stay on disk. A node that was in the middle of writing a file when you pressed Cancel completes its write.
- The run record is sealed with status `cancelled`.

If a single step is very long (for example a very large write), Cancel will seem to do nothing until that step ends or hits the 30 second step limit (see below).

Closing the workflow window or the app during a Run cancels it the same way and waits up to five seconds for the current step.

## The run script

Every Run writes a plain Python script containing exactly the code that ran, one block per node, in run order. Use it if you or a colleague want to see what the app did, or to rerun the steps outside the app.

| | |
|---|---|
| Where | `%APPDATA%\Trigger Designer\last_run\check_output.py` (the `last_run` folder inside the app data folder; setting the environment variable `TRIGGER_DESIGNER_DATA_DIR` moves it) |
| When it is written | At the end of every Run, successful or not |
| What it overwrites | The previous script. There is one script per app, not one per workflow, so copy it if you want to keep it. |
| Contents | A header, then each node's code. For a node that did not run (for example after a failure) the code is generated freshly; a node that cannot produce code gets a comment line. |
| Running it | With a Python environment that has `polars` and the `trigger_designer` package. When the app runs from source, the header adds the source folder to the path for you. A packaged installation has no source folder, so the package must be installed in the Python you use. |

The script is also embedded in the run record (unless you turn that off in Preferences), together with a hash of it.

The script reads the same files and writes the same output paths as the workflow. Running it overwrites those outputs.

## Time and memory limits

| Limit | Value | What happens |
|---|---|---|
| Time per node | **30 seconds** | The node is stopped from the app's point of view and reports `TD-RUN-001` "This step took longer than 30 seconds and was stopped". The Run stops with that failure. The work already in progress on the background thread cannot be forcibly ended, so it may keep using the CPU until it finishes; start a new Run only after it has quietened, and consider filtering earlier or writing to Parquet. |
| Time for a SQL Query | 25 seconds | Interrupted cleanly with `TD-SHAPE-115`. |
| SQL Query memory | 2 GB | `TD-SHAPE-113` with the engine's message. |
| Out of memory | No fixed cap | If the computer runs out of memory the step fails with `TD-RUN-002`. |
| Preview | 1,000 rows or 2 MB | Display only; it does not limit processing. |

See [Limits and performance](limits-and-performance.md) for advice on large files.

## Workflows with no output node

A workflow without a File Output (a "sink") can be Run, but there is nothing at the end of the plan to pull the data through. In that case:

- Nodes **are** checked: a plan that refers to a column that does not exist fails at the node that caused it. This is the "plans are verified" step above.
- Audit nodes still compute their summary, and the run record still counts rows according to your **Row counts** preference.
- Nothing is written to disk, and a Run that succeeds does not prove that the data would have written without problems.

When you only want to look at results, select a node and use the [Data Preview](config-dock-and-preview.md#data-preview); you do not need to Run.

## If something goes wrong

| Symptom | What to do |
|---|---|
| Pressing Run does nothing | A Run is already in progress (look for the stop button), or the workflow has a loop (check the Logs and the selected edges). |
| "The workflow has a cycle" | Delete one of the connections in the selected loop. |
| The Run stops at the first red node | The preference "Keep running independent branches after a failure" is off (see [When a step fails](#when-a-step-fails)). Fix that node and Run again, or turn the preference on. |
| "This step took longer than 30 seconds" | Reduce the data earlier in the workflow (a Filter or Select Records near the input), or write to Parquet instead of CSV or Excel. |
| The preview is still showing 100 rows after Run | The node was edited after the Run, so the preview went back to the sample. Run again. |
| The Run finished but the output file is missing | Check that the File Output node has a path and is connected to a node; check the Logs for "Run log saved" and open Problems. |
| A warning about steps with problems appears at the start of a Run | Some nodes were invalid when you pressed Run. They will probably fail; open Problems to see why. |
| Nothing happens when I cancel | The current step is still running; Cancel acts after it. |
