# Using Trigger Designer from an AI tool (MCP)

Trigger Designer can be driven by an AI tool such as Claude Code, Codex, Cursor or Claude Desktop. You ask for a workflow in plain language ("find the invoices over 10,000 and total them per vendor"); the AI builds it, checks it against your data, and leaves you a `.tds` file to review and run in Trigger Designer.

It works through a small local program, `trigger-designer-mcp`. It speaks the Model Context Protocol (MCP) over standard input and output, so it opens **no network port** and Trigger Designer itself never connects to the internet for this.

This page is written for someone who has never seen the code. Follow it top to bottom once, and you will have a working setup.

## On this page

- [How it fits together](#how-it-fits-together)
- [What leaves your computer](#what-leaves-your-computer)
- [1. Install](#1-install)
- [2. Prepare a workspace and a policy](#2-prepare-a-workspace-and-a-policy)
- [3. Connect your AI tool](#3-connect-your-ai-tool)
- [4. Try it](#4-try-it)
- [5. Review and run the result](#5-review-and-run-the-result)
- [What the AI can and cannot do](#what-the-ai-can-and-cannot-do)
- [Tool reference](#tool-reference)
- [Troubleshooting](#troubleshooting)
- [Uninstall](#uninstall)

## How it fits together

```text
 you (the data owner)                       the AI tool
 ───────────────────                        ───────────
 choose a workspace folder   ──┐
 write a policy file         ──┼──►  trigger-designer-mcp  ◄──  asks for things
 (how much data it may see,    │     (enforces both,             by calling tools
  whether it may write)        │      on your computer)
                               │              │
                               │              ▼
                               └────►  your .tds files and data
```

Two rules shape everything:

- **You set the limits, not the AI.** The workspace folder and the policy file are given when the server starts. The AI cannot change them, and a refusal is final.
- **A person approves and runs.** The AI can build and check a workflow. It has no tool to approve it or to run it. You open the file in Trigger Designer (or use the command line) and run it yourself.

## What leaves your computer

Trigger Designer sends nothing anywhere. **Your AI tool does.** Everything the AI sees in a tool result (column names, statistics, rows) is sent to the AI provider as part of the conversation. That is why the default is the most careful setting:

| Policy `access` | The AI can see | Typical use |
|---|---|---|
| `schema_only` (default) | Column names and types only. Never a value. | Sensitive data. The AI can still build and validate a workflow. |
| `aggregates` | Also per-column statistics (counts, nulls, minimum, maximum, mean, text lengths). Never a row. | It needs to know the shape of the data to choose sensible settings. |
| `rows` | Also the first `max_rows` rows. | Non-sensitive data, or an AI you trust with it. |

Choose the lowest level that works. With `schema_only` the AI never learns what is in your files; it only learns what the columns are called.

## 1. Install

You need:

- Windows, macOS or Linux, and a terminal.
- [uv](https://docs.astral.sh/uv/) (it installs the right Python for you). Install it once with the command on its website.
- Git.
- An AI tool that supports MCP servers over stdio (Claude Code, Codex CLI, Cursor, Claude Desktop and others).

Get the code and install it with the `agent` extra:

```bash
git clone https://github.com/AzadKshitij/TriggerEditor.git
cd TriggerEditor
git checkout AI
uv sync --extra agent
```

(`git checkout AI` is only needed while the feature lives on the `AI` branch.) The first install downloads Python 3.14 and the libraries; it takes a few minutes.

Check that the server starts:

```bash
uv run trigger-designer-mcp --help
```

You should see the options `--workspace`, `--policy` and `--timeout`. Note the full path of the program; you will need it in step 3:

| System | Program |
|---|---|
| Windows | `<folder>\TriggerEditor\.venv\Scripts\trigger-designer-mcp.exe` |
| macOS, Linux | `<folder>/TriggerEditor/.venv/bin/trigger-designer-mcp` |

!!! tip "Why the full path"
    Pointing your AI tool at that file directly starts the server fast and never re-installs anything. It is also the most reliable setup on Windows.

## 2. Prepare a workspace and a policy

The **workspace** is a folder. The server will only open `.tds` files inside it, and the AI will only create files inside it. Make a new, empty folder for the AI and put the data you want it to work with there. Example, using a made-up `C:\audits\q3`:

```text
C:\audits\q3\
  invoices.csv
```

Here is a small data file to try. Save it as `invoices.csv`:

```csv
invoice_id,vendor,amount,posted
INV-1001,Northwind Supplies,2450.00,2026-01-05
INV-1002,Contoso Ltd,18200.50,2026-01-07
INV-1003,Fabrikam Inc,9999.99,2026-01-09
INV-1004,Contoso Ltd,10000.01,2026-01-12
INV-1005,Adatum Corp,56000.00,2026-01-15
INV-1006,Northwind Supplies,310.75,2026-01-19
INV-1007,Fabrikam Inc,12750.00,2026-01-21
INV-1008,Tailspin Toys,845.20,2026-01-23
INV-1009,Adatum Corp,23100.00,2026-01-27
INV-1010,Contoso Ltd,10000.00,2026-01-30
```

The **policy** is a small JSON file that says how much the AI may see and whether it may write. Put it **outside the workspace**, in a folder the AI cannot write to, for example `C:\audits-policy\policy.json`:

```json
{
  "access": "rows",
  "max_rows": 5,
  "edit": true
}
```

| Key | Values | Meaning |
|---|---|---|
| `access` | `schema_only`, `aggregates`, `rows` | How much data the AI may see (see the table above). Default `schema_only`. |
| `max_rows` | 1 to 1000 | Needed with `rows`: the most rows any tool may return. |
| `edit` | `true`, `false` | `true` lets the AI write workflow files. `false` (default) lets it plan and show changes, but nothing is saved. |
| `paths` | a list of folders | Optional. Extra folders the AI may point a file setting at, besides the workspace. |

For a first try, `rows` with `max_rows` 5 and `edit` true is fine because the sample data is not sensitive. For real data start with `schema_only`.

The policy file is read again on **every tool call**, so you can change `access`, `max_rows` or `edit` while the AI is working and the next call obeys it; no restart is needed. Only the `--workspace` and `--policy` arguments in your AI tool's configuration need a restart.

Instead of `--policy` you can set the environment variable `TRIGGER_DESIGNER_AGENT_POLICY` to the policy file's path (the `--policy` argument wins if both are given). Use `--workspace` more than once to allow several folders:

```text
--workspace "C:\audits\q3" --workspace "C:\audits\shared-data"
```

A relative workflow name such as `big_vendors.tds` is looked for in every workspace. If the same name exists in more than one, the AI is asked to give the full path; a brand-new file goes in the first workspace listed.

!!! warning "Keep the policy file out of the workspace"
    If no policy file is given at start-up, the server looks for a `<workflow>.agent.json` next to each workflow. An AI that can write files could change that. Always pass `--policy` and keep that file somewhere the AI cannot reach.

## 3. Connect your AI tool

You give the tool three things: the program from step 1, `--workspace` and `--policy`. Use **absolute paths** everywhere. The examples use Windows paths; on macOS or Linux use `/home/you/...` and the `.venv/bin/` program.

### Claude Code

One command, from any terminal:

```bash
claude mcp add trigger-designer --scope user -- "C:\tools\TriggerEditor\.venv\Scripts\trigger-designer-mcp.exe" --workspace "C:\audits\q3" --policy "C:\audits-policy\policy.json"
```

Everything after the `--` is the command that starts the server. Then start Claude Code and type `/mcp`: `trigger-designer` should show as **connected** with 14 tools. Remove it later with `claude mcp remove trigger-designer`.

### Cursor, Claude Desktop and other tools that read a JSON file

Add this to the tool's MCP settings file (Cursor: `.cursor/mcp.json` in your project or `~/.cursor/mcp.json`; Claude Desktop: `claude_desktop_config.json`), then restart the tool:

```json
{
  "mcpServers": {
    "trigger-designer": {
      "command": "C:\\tools\\TriggerEditor\\.venv\\Scripts\\trigger-designer-mcp.exe",
      "args": [
        "--workspace", "C:\\audits\\q3",
        "--policy", "C:\\audits-policy\\policy.json"
      ]
    }
  }
}
```

In JSON, write every backslash twice.

### Codex CLI

Add this to `~/.codex/config.toml`:

```toml
[mcp_servers.trigger-designer]
command = "C:\\tools\\TriggerEditor\\.venv\\Scripts\\trigger-designer-mcp.exe"
args = ["--workspace", "C:\\audits\\q3", "--policy", "C:\\audits-policy\\policy.json"]
```

### Any other tool

Configure a **stdio** MCP server with the command and arguments above. There is no HTTP mode, no port and no API key.

### Check the connection yourself

If the tool says the server failed to start, run the same command in a terminal:

```bash
"C:\tools\TriggerEditor\.venv\Scripts\trigger-designer-mcp.exe" --workspace "C:\audits\q3" --policy "C:\audits-policy\policy.json"
```

It should sit there silently, waiting for input (press `Ctrl+C` to stop). An error message means a wrong path or a policy file that is not valid JSON; the message says which.

## 4. Try it

Open your AI tool and ask for what you want in plain words. You do not need to name node types or settings; the AI looks them up. For the sample data, try:

> Create a workflow named `big_vendors.tds` that reads `invoices.csv`, keeps only invoices over 10,000, totals the amount and counts the invoices per vendor, sorts by total with the biggest first, and writes the result to `output/big_vendors.csv`. Check your work and show me the first rows of the result. Do not run the workflow.

What you should see, in order:

1. The AI calls `get_policy` to learn what it may do.
2. It looks up the node types it needs (`list_ops`, `describe_op`).
3. It calls `new_workflow` and `patch_workflow` to build the file.
4. It calls `validate`, then (with `rows` access) `get_preview` to look at the result.
5. It reports the rows. For the sample data they are:

| vendor | total | invoices |
|---|---|---|
| Adatum Corp | 79,100.00 | 2 |
| Contoso Ltd | 28,200.51 | 2 |
| Fabrikam Inc | 12,750.00 | 1 |

(INV-1010 is exactly 10,000 and is correctly left out: "over 10,000" means more than.) With `schema_only` the AI cannot show you rows; it will say so and show the columns instead.

More things to ask:

- "Which invoices were posted on a weekend?" (builds a date calculation)
- "Add a step that flags vendors with more than one invoice." (changes the existing workflow)
- "Explain what `big_vendors.tds` does, node by node." (reads the workflow; nothing is changed)
- "Validate `big_vendors.tds` and fix anything it reports."

!!! note "The first data tool call is slow"
    Looking at data starts a separate process that loads the data engine, so the first `get_schema` or `get_preview` can take 10 to 20 seconds. Later calls are quicker.

## 5. Review and run the result

The AI leaves `big_vendors.tds` in the workspace, plus a `.bak` copy of the file as it was before the first change. The workflow has not been run to produce its output. (`validate` and `check_data` do try out the steps that feed each output on your data to find mistakes early, but they write no file.)

1. **Open it in Trigger Designer** (File > Open, or `trigger-designer "C:\audits\q3\big_vendors.tds"`). The nodes the AI created are named after what they do, shown under each node. Check the settings in the Config Dock as you would for any workflow.
2. **Run it** with the Run button, or from the command line:

```bash
trigger-designer-cli approve "C:\audits\q3\big_vendors.tds"
trigger-designer-cli run "C:\audits\q3\big_vendors.tds"
```

`approve` is the step where you confirm you have looked at the workflow; any later change by the AI (or anyone) cancels that approval and you must approve again. See [the command line guide](cli.md#approve-and-the-approval-flow).

### If the workflow is already open while the AI works

Keep the file open in Trigger Designer and watch it as the AI works. When the AI saves a change, a bar appears above the canvas:

> Changed outside Trigger Designer: 2 nodes added, 1 node changed, 3 connections added

Nothing changes in your window until you decide. The bar has three icon buttons (hover for the tooltip):

| Button | What it does |
|---|---|
| Review changes | Lists exactly what changed, node by node, setting by setting. |
| Reload from disk | Takes the AI's version into the window as **one undo step named "External Edit"**. Press `Ctrl+Z` to go back to what you had, including any edits you had not saved. |
| Keep my version | Ignores this change. If you save later, your version replaces the AI's file. |

After you reload, the nodes the AI added or changed are drawn with a dashed outline and a small marker until you press **Mark all as reviewed** on the bar. Hover a marked node to see why. The markers are only on screen; they are never saved in the file.

If the AI is still writing, or the file cannot be read as a workflow, the bar says so and offers only **Keep my version**; it tries again when the file settles. A reload is held back while a run is in progress.

## What the AI can and cannot do

**It can:**

- list the node types and read how each one is configured;
- find the data: list the workflow and data files in the workspace (names, sizes and dates only) and look at a CSV, TSV, text or Parquet file directly, without building a workflow, as far as your policy allows;
- read a workflow in the workspace: its nodes **with their settings**, connections, input and output files;
- look at the columns, statistics or first rows at any node (as far as your policy allows);
- create a new workflow and change one (add, remove, connect, rename and set up nodes) when `edit` is true;
- validate a workflow, which also runs the nodes that feed each output without writing anything, to find mistakes before you run it, and check an edit the same way **before** it is saved.

**It cannot:**

- open a file outside the workspace, or any file that is not a `.tds` workflow;
- see more data than `access` allows, however it asks;
- save anything unless `edit` is true. Without it, every change is only a preview of the differences;
- overwrite a file by accident. A new workflow never replaces an existing file; a change keeps the first `.bak`, is all-or-nothing, and is refused if the file changed since the AI read it;
- approve or run a workflow.

Every change is a **dry run unless the AI says `apply`**. A good AI shows you the differences and asks before it writes.

A change can only be written to the version of the file the AI has read. To write to an existing workflow the AI must pass that version's `sha256`, so an AI working from an old reading cannot overwrite something you saved in the meantime; it is told to read again. A new workflow can be created complete in a single step, which is all-or-nothing: if any part of it is wrong, no file is left behind.

Every change comes back with a `validation` report: what would stop the workflow from running if it were saved as proposed (a missing input file, a loop, and so on). The AI can also ask for `check_data`, which tries out the steps that feed each output on a temporary copy, and for `require_valid`, which refuses to save while there is an error. By default an unfinished workflow can still be saved, because workflows are often built in stages.

### Two things worth knowing

- **Numbers from a CSV are text.** Every column read from a CSV or text file arrives as text until a Select node converts it. The server tells the AI this; `validate` reports a workflow that sums a text column or compares one with "greater than". If you see an error mentioning `TD-TYP-003` or `TD-TYP-004`, this is why.
- **File paths are stored in full.** The AI may give `output/result.csv`; it is saved as a complete path inside the workspace, so the editor and the command line write to the same place. A missing output folder is created when a change is applied.

## Tool reference

You do not need this to use the server; the AI reads it automatically. It is here so you can see what is possible.

| Tool | What it does | Needs |
|---|---|---|
| `get_policy` | What the policy allows. With no workflow: the policy the server started with, the workspaces and the versions. With a workflow: the policy for it. | nothing |
| `list_ops` | Lists every node type. | nothing |
| `describe_op` | One node type in full: connections, every setting with its type and choices, an example. | nothing |
| `list_files` | The workflow and data files in the workspaces: path, size, modified time. Never contents. | nothing |
| `profile_file` | Describes one CSV, TSV, text or Parquet file without a workflow. `schema_only`: column names and how they load (CSV columns always load as text). `aggregates`: also row count, statistics, the type each column can be converted to, and a ready-made `preparation.select` column list. `rows`: also the first rows. Uses the policy the server started with. | `schema_only` |
| `read_workflow` | A workflow's nodes with their settings, connections, files and approval status. `node` returns just one node; `include_settings` can switch the settings off. | nothing |
| `validate` | Everything that would stop a run: structure, node types, loops, input files, output folders, and (by default) a trial run of the nodes that feed each output. Returns `ok` and a list of findings. | `schema_only` |
| `diff` | Differences between two workflows, node by node. Reads no data. | nothing |
| `get_schema` | Column names and types at a node. | `schema_only` |
| `get_profile` | Statistics per column at a node. | `aggregates` |
| `get_preview` | The first rows at a node. | `rows` |
| `explain_error` | Plain-language meaning and fix for an error code (`TD-...`). | nothing |
| `new_workflow` | Creates a workflow, empty or built by `edits` in the same step. Never replaces a file. A dry run unless `apply` is true. | `edit` to apply |
| `patch_workflow` | Applies a list of changes as one all-or-nothing batch (add node, remove node, connect, disconnect, set settings, name a node, lay out). A dry run unless `apply` is true; applying needs `expect_sha256`. Returns a `validation` report; `check_data` and `require_valid` are optional. | `edit` to apply |

Workflow names are relative to the workspace folder: `big_vendors.tds`, not `workspace/big_vendors.tds`.

## Troubleshooting

| What you see | What it means and what to do |
|---|---|
| The tool says the server failed to start or `/mcp` shows it as failed | Run the server command yourself in a terminal (see [Check the connection yourself](#check-the-connection-yourself)). A path with a typo, a missing `.venv` (run `uv sync --extra agent` again), or an invalid policy file are the usual causes. |
| `trigger-designer: connected` but no tools | Restart the AI tool; some tools read their configuration only at start-up. |
| `TD-CLI-019`: the access policy does not allow this | The AI asked for more than the policy permits (for example rows with `schema_only`, or a save with `edit` false). This is by design. Change the policy file if you want to allow it, then restart the AI tool. |
| `TD-CLI-028`: not a workflow inside the folders this server may use | The AI used a path outside the workspace, or not a `.tds` file. Tell it to use a name like `sales.tds`. |
| `TD-CLI-027` mentioning `expect_sha256` | The AI tried to write without saying which version it had read. It should call `read_workflow` and pass the `sha256`. |
| `TD-CLI-006`: exists in more than one workspace | The same file name is in two of your workspace folders. The AI should use the full path. |
| The server stops at start with "the workspace ... is not a folder" | A `--workspace` path does not exist (a typo, or `~` that your tool did not expand). Use a full path. The message shows what the path resolved to. |
| `TD-CLI-026`: the workflow changed since it was read | Someone changed the file (you in the editor, or another tool) after the AI read it. Ask the AI to read it again and repeat the change. |
| `TD-TYP-003` / `TD-TYP-004` from `validate` | A text column is being summed or compared as a number. The AI should add a Select node that sets the column to a number type; the message names the column. |
| `TD-CLI-014`: the output folder does not exist | Apply a change (the folder is created), or create the folder yourself. |
| The text begins `Error executing tool ...: {"error": ...}` | Normal. That is how a refused or failed call is reported; the JSON part has the code, a message and a hint. The AI reads it and adjusts. |
| A data tool is slow, or times out | The first call loads the data engine. For large files raise the limit with `--timeout 1200` in the server command; some AI tools also have their own tool timeout setting. |
| The AI says it cannot show rows | The policy is `schema_only` or `aggregates`. Intended. |
| The AI wrote a file you did not expect | Look at the workspace: only `.tds` files, their `.bak` copies and the output folders of workflows it built are ever created. Delete anything you do not want; set `"edit": false` to stop all writing. |

If something still looks wrong, ask the AI to call `explain_error` with the code, or look up the code in [Errors and problems](errors-and-problems.md).

## Uninstall

- Remove the server from your AI tool: `claude mcp remove trigger-designer` (Claude Code), or delete the entry from the tool's JSON or TOML file.
- Delete the `TriggerEditor` folder. Nothing else is installed on your computer.
- Your workflows and data are never touched by removing the server.

## See also

- [The command line](cli.md): the same workflows from a terminal, including `edit`, `validate`, `approve` and `run`.
- [Security and privacy](security-and-privacy.md)
- [Errors and problems](errors-and-problems.md)
