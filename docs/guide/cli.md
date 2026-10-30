# The command line

`trigger-designer-cli` runs a saved workflow with no window and nobody at the keyboard. It is meant for two situations: you want the same check to run every night or every month without opening the program, or IT wants to start a workflow from a script or a job scheduler and read a clear pass/fail answer.

It runs the same nodes as the editor, so a workflow gives the same result headless as it does when you press **Run**. It writes the same [run record](run-history-and-audit-trail.md), and it adds protections that matter when nobody is watching: outputs are never left half-written, a workflow written by someone else will not run until you have approved it, and every outcome is a fixed exit code.

[Back to the guide index](README.md)

This page is the guide. The short command reference for developers and IT is [`docs/CLI.md`](../CLI.md); how it works inside is in [CLI internals](../dev/cli-internals.md).

## On this page

- [What it is for, and what it is not](#what-it-is-for-and-what-it-is-not)
- [Installing and starting it](#installing-and-starting-it)
- [Quick start](#quick-start)
- [Commands at a glance](#commands-at-a-glance)
- [run](#run)
- [validate](#validate)
- [info](#info)
- [approve and the approval flow](#approve-and-the-approval-flow)
- [params](#params)
- [paths](#paths)
- [Parameters and path overrides](#parameters-and-path-overrides)
- [Workpaper Output on the command line](#workpaper-output-on-the-command-line)
- [Run records and verify-log](#run-records-and-verify-log)
- [Exit codes](#exit-codes)
- [Logs and events](#logs-and-events)
- [Timeouts, memory and threads](#timeouts-memory-and-threads)
- [Scheduling on Windows](#scheduling-on-windows)
- [Other schedulers and containers](#other-schedulers-and-containers)
- [Safety](#safety)
- [Where the files go](#where-the-files-go)
- [Troubleshooting](#troubleshooting)

## What it is for, and what it is not

Use it to:

- run a workflow you have already built and saved in the editor, on a schedule or from a script;
- check a workflow without running it (`validate`, `run --dry-run`);
- run the same workflow on a different input file or into a different folder without editing it;
- check later that an output file is still the one a run produced (`verify-log`).

It does not build or edit workflows (use the editor), it has no screen to click, and it never asks questions while running. If something needs a decision, it stops with an exit code and a message.

## Installing and starting it

There are four ways to start the same program. Use whichever your installation provides.

| How | When |
|---|---|
| `trigger-designer-cli` | Installed copy with the folder on `PATH`, or a developer copy with the project's environment active. |
| `trigger-designer-cli.exe` | Next to `TriggerEditor.exe` in the program folder. The Windows installer puts it there. |
| `python -m trigger_designer.cli` | A developer copy. Works from any folder if the package is installed in that Python. |
| `uv run trigger-designer-cli` | A developer copy, started through `uv`. |

**The installed program.** The installer copies `trigger-designer-cli.exe` beside the editor. On the **Select Additional Tasks** page there is an unticked option, **Add trigger-designer-cli to PATH** (the task is called `addtopath` if you install silently with `/TASKS="addtopath"`). Tick it if you want to type `trigger-designer-cli` in any terminal. Open a new terminal window after installing; windows that were already open do not see the change. Without that option, call it by its full path, for example `"C:\Program Files\Trigger Designer\trigger-designer-cli.exe"`.

**A source checkout.** From the project folder:

```text
.venv\Scripts\python.exe -m trigger_designer.cli --version
trigger-designer-cli 0.1.0 (workflow schema 2)
```

**Building the program folder** (for IT). `scripts\build.bat` runs PyInstaller with `trigger.spec`. The spec builds the CLI as a second program that shares every library file with the editor, so it adds only a few megabytes. The build script then starts `trigger-designer-cli.exe --version` and a deep validation of a sample workflow, and fails if either does not work. The single-file "portable" build does not contain the CLI.

The program is a console program. It prints to the terminal and returns an exit code; it never opens a window.

Starting up takes about a second for the commands that only read files (`info`, `validate`, `approve`, `params`, `paths`, `schedule`, `verify-log`), because they do not load the data engine. A `run`, a dry run or a `validate --deep` takes about two seconds in total even for a tiny workflow, because it loads the editor's node classes and the data engine.

## Quick start

You have a workflow `select.tds` that reads `check.csv` and writes a cleaned CSV. This was saved on someone else's computer, so its paths point at `C:\Projects\TriggerEditor\...`, which does not exist here. The examples below use a work folder `Y:\audit` with three sub-folders `wf` (the workflow), `in` (the input) and `out` (the results). Output lines are trimmed with `...`, and the `[exit code N]` lines are not printed by the program: they show the exit code the shell reports.

### 1. Look at the file first

```text
> trigger-designer-cli info select.tds
workflow:   Y:\audit\wf\select.tds
sha256:     21ca314bd088785936bfb4955987066a9b4f07b2252af36bf2f1c957e4eeb445
size:       4326 bytes, encoding utf-8
schema:     0 (saved by app None, None)
approved:   no
nodes:      3
  input.file_input: 1
  input.file_output: 1
  preparation.select: 1
reads:
  [1429604924240] C:/Projects/TriggerEditor/check.csv
       -> C:\Projects\TriggerEditor\check.csv (MISSING)
writes:
  [2441464837840] C:/Projects/TriggerEditor/out_check_W_select.csv
       -> C:\Projects\TriggerEditor\out_check_W_select.csv (new)
parameters:
  (none)
```

`info` tells you what the workflow reads and writes, whether you have approved it, and whether the files exist. Nothing is run.

### 2. Validate

```text
> trigger-designer-cli validate select.tds
WARNING TD-CLI-001: legacy v1 file (no workflow_metadata)
WARNING TD-IN-001: input file not found: C:\Projects\TriggerEditor\check.csv
OK
[exit code 0]
```

Warnings do not fail `validate` unless you add `--strict`. Here the missing input is expected, because we will point at the real file with `--input-dir`. The legacy warning means the file was saved by an older version; open and save it in the editor once to remove it.

### 3. Approve it

A workflow is code that will be run. Before it runs unattended you must say you have looked at it. `approve` prints what the file reads and writes and asks you:

```text
> trigger-designer-cli approve select.tds --note "reviewed demo"
workflow: Y:\audit\wf\select.tds
sha256:   21ca314bd088785936bfb4955987066a9b4f07b2252af36bf2f1c957e4eeb445
operations:
  input.file_input: 1
  input.file_output: 1
  preparation.select: 1
reads:
  C:\Projects\TriggerEditor\check.csv
writes:
  C:\Projects\TriggerEditor\out_check_W_select.csv
parameters:
  (none)
Approve? [y/N] y
Approved.
```

In a script (no one to answer) pass `--yes`. Without a terminal and without `--yes` it stops with exit code 64.

### 4. Dry run

A dry run does everything except run the nodes and write files: it checks the approval, the parameters, that the inputs exist, that the output folders can be written and that every node's code passes the safety check.

```text
> trigger-designer-cli run select.tds --dry-run --input-dir Y:\audit\in --output-dir Y:\audit\out
... INFO    run.started workflow=Y:\audit\wf\select.tds sha256=21ca314b... trigger=manual pid=26108 dry_run=True
... INFO    plan.resolved approved=True inputs=[{'node_id': 1429604924240, 'path': 'Y:\\audit\\in\\check.csv', 'exists': True, 'files': 1, 'size_bytes': 1257}] outputs=[{'node_id': 2441464837840, 'final': 'Y:\\audit\\out\\out_check_W_select.csv', ...}] ...
... WARNING warning message=TD-CLI-001: legacy v1 file (no workflow_metadata)
... INFO    run.finished status=ok exit_code=0 duration_s=1.327 nodes_ok=0 nodes_failed=0
[exit code 0]
```

`--input-dir` says "read every File Input from this folder, using the same file name as saved". `--output-dir` does the same for outputs. This is how a workflow made on another computer runs here.

### 5. Run it

```text
> trigger-designer-cli run select.tds --input-dir Y:\audit\in --output-dir Y:\audit\out
... INFO    run.started ...
... INFO    plan.resolved ...
... INFO    node.started node_id=1429604924240 title=File Input op=input.file_input index=0 total=3
... INFO    node.finished node_id=1429604924240 title=File Input status=ok duration_s=0.01
... INFO    node.started node_id=1429614326224 title=Select op=preparation.select index=1 total=3
... INFO    node.finished node_id=1429614326224 title=Select status=ok duration_s=0.003
... INFO    node.started node_id=2441464837840 title=File Output op=input.file_output index=2 total=3
... INFO    node.finished node_id=2441464837840 title=File Output status=ok duration_s=0.009
... INFO    output.committed path=Y:\audit\out\out_check_W_select.csv size_bytes=840 sha256=dd1e6c4e...
... INFO    run.finished status=ok exit_code=0 duration_s=1.578 nodes_ok=3 nodes_failed=0 record_path=Y:\audit\wf\select.runs\963d5edc374a4fcbbd834457e20e2ae3.json ...
[exit code 0]
```

### 6. Read the exit code

The exit code is the answer. In a script:

- Command Prompt: `echo %ERRORLEVEL%`
- PowerShell: `$LASTEXITCODE`
- Bash: `echo $?`

`0` means every node ran and the outputs are in place. Anything else is a specific problem; see [Exit codes](#exit-codes). When a node fails, the last lines say which one:

```text
... ERROR   node.finished node_id=2676751646608 title=Formula status=failed duration_s=0.097 error={'code': 'TD-SHAPE-004', ...}
... ERROR   run.finished status=failed exit_code=1 duration_s=2.222 nodes_ok=1 nodes_failed=1 record_path=Y:\audit\wf\formula.runs\755fa3af....json ...
FAILED at node 'Formula' [TD-SHAPE-004] Section 1: Cannot compare values of type VARCHAR and type INTEGER_LITERAL - an explicit c... - Pick a value from the list or inside the range.
[exit code 1]
```

The `TD-` code is the same plain-language code the editor shows; look it up in [Errors and problems](errors-and-problems.md). The output files from a failed run are not touched: whatever was there before is still there.

## Commands at a glance

```text
trigger-designer-cli [--version] [--state-dir DIR] <command> [options]
```

| Command | What it does | Loads the data engine? |
|---|---|---|
| `run` | Run a workflow and write its outputs | yes |
| `validate` | Check a workflow file; `--deep` also loads it like the editor | only with `--deep` |
| `info` | Show what a workflow reads, writes and needs | no |
| `approve` | Pin a reviewed workflow file so it may run unattended | no |
| `verify-log` | Check a run record against the files it describes | no |
| `params` | List, add or remove run-time parameters stored in a workflow | no |
| `paths` | Show saved file paths; optionally make them relative | no |
| `schedule` | Create, list, show or remove Windows scheduled runs | no |

Options that belong before the command name:

| Option | Meaning |
|---|---|
| `--version` | Print the program version and the workflow file format it understands, then stop. |
| `--state-dir DIR` | The folder for approvals, locks and schedules. Default: `%LOCALAPPDATA%\Trigger Designer\cli`. The environment variable `TRIGGER_DESIGNER_STATE_DIR` does the same; the option wins. |
| `-h`, `--help` | Help. Also works after a command name: `trigger-designer-cli run --help`. |

Abbreviated option names are not accepted (write `--timeout`, not `--time`), so a script cannot change meaning when a new option is added later.

## run

```text
trigger-designer-cli run WORKFLOW [options]
```

Runs the workflow. All outputs are first written to temporary files next to their final place, named like `.name.tdtmp-<run>.ext`. Only when every node has succeeded are they moved over the final files, in one step. A run that fails, is cancelled, times out or is killed leaves the previous outputs exactly as they were. (The temporary files of a killed run are cleaned up by the next run of the same workflow.)

| Option | Default | Meaning |
|---|---|---|
| `WORKFLOW` | required | The `.tds` file. |
| `--param NAME=VALUE` | none | Set a parameter defined in the workflow. Repeat for more. Split at the first `=`. See [Parameters and path overrides](#parameters-and-path-overrides). |
| `--input-dir DIR` | none | Read every File Input from `DIR`, using the file name saved in the workflow. The Workpaper Output's **Source files** list follows it too. |
| `--output-dir DIR` | none | Write every File Output and every Workpaper Output into `DIR`, using the file name saved in the workflow. |
| `--create-output-dirs` | off | Create output folders that do not exist. Without it a missing folder is an error (exit 2). |
| `--dry-run` | off | Check everything and print the plan. Runs nothing and writes nothing. |
| `--timeout SEC` | `3600` | Stop the whole run after `SEC` seconds. `0` means no limit. Exit 4. |
| `--max-memory MB` | none | Stop if the program uses more than `MB` of memory. Exit 5. |
| `--threads N` | all | Limit the data engine (Polars) to `N` threads. |
| `--cancel-grace SEC` | `10` | After Ctrl+C, how long to wait for the running node before giving up. |
| `--min-free-mb N` | `64` | Refuse to start if an output drive has less than `N` MB free (exit 2). |
| `--strict` | off | Treat warnings as errors (exit 2). A warning is, for example, a file saved by an older version. |
| `--keep-going` | off | After a node fails, still run the branches that do not depend on it, and commit the outputs that did succeed. The exit code is still 1. |
| `--allow-unapproved` | off | Run a file that has not been approved. For interactive use; ignored when `--trigger schedule`. |
| `--allow-custom-code` | off | Allow nodes that contain user-written code. Needs approval too. No current node has user code. |
| `--record-dir DIR` | next to the workflow | Where to write the run record. |
| `--no-record` | off | Write no run record. |
| `--no-hash` | off | Do not compute the SHA-256 fingerprints of inputs and outputs (faster on very large files; `verify-log` then cannot check the files). |
| `--emit-script FILE` | none | Also save the Python script that was run. |
| `--log-format {text,json}` | `text` | `text`: readable lines on stderr. `json`: one JSON object per line on stdout. See [Logs and events](#logs-and-events). |
| `--log-file FILE` | none | Also append the JSON lines to `FILE`, whatever `--log-format` is. |
| `-v`, `-vv` | off | More detail from the program's own log: `-v` adds information messages, `-vv` adds debugging. |
| `--quiet` | off | In text mode print only warnings, errors and the start and end of the run. |
| `--trigger {manual,schedule}` | `manual` | Who started the run. Recorded in the log. A `schedule` run never accepts `--allow-unapproved`. The scheduler sets it for you. |

**Stopping a run.** Ctrl+C, Ctrl+Break or a termination request asks the run to stop after the node that is running. A node that has already started cannot be interrupted in the middle, because it is inside the data engine. If it has not finished after `--cancel-grace` seconds the program ends with exit 130; the outputs are not touched. A second Ctrl+C ends it at once.

**Example with several options:**

```text
trigger-designer-cli run sales.tds --param input_file=D:\in\today.csv --log-format json --log-file D:\logs\sales.jsonl --timeout 1800
```

### What you get when it fails

| Situation | Seen as |
|---|---|
| Not approved | `FAILED at the run [TD-CLI-008] This workflow has not been approved to run. - Review it with approve <workflow>; scheduled runs always need approval.` exit 6 |
| Edited after approval | `... [TD-CLI-008] The workflow changed after it was approved (approved 2026-10-30T17:48:06Z by kashvinchandrasan). - Check who changed it, then approve it again` exit 6 |
| Missing input | `FAILED at the run [TD-IN-001] Cannot find the input file 'Y:\audit\in\nothere.csv'. - Use --input-dir to remap saved paths, or fix the path in the editor.` exit 2 |
| Missing output folder | `FAILED at the run [TD-CLI-014] The output folder does not exist: Y:\audit\out2 - Create it, or pass --create-output-dirs.` exit 2 |
| Unknown or missing parameter | `FAILED at the run [TD-CLI-005] Required parameter 'input_file' was not given. - Pass --param input_file=VALUE.` exit 2 |
| Same workflow already running | `FAILED at the run [TD-CLI-012] This workflow is already running (pid 24656, run 3d4e9781). - Wait for the other run to finish; ...` exit 7 |
| Output locked | `FAILED at the run [TD-CLI-013] could not write Y:\audit\out\select_default.csv: The process cannot access the file because it is being used by another process - Close the file in other programs (Excel keeps it locked) and run again. Previous files are unchanged.` exit 8 |

## validate

```text
trigger-designer-cli validate WORKFLOW [--deep] [--no-files] [--strict] [--param NAME=VALUE] [--input-dir DIR] [--output-dir DIR] [--format {text,json}]
```

Checks a workflow without running it. The default check is instant and does not load the data engine: the file is valid JSON, the version is not newer than this program, every node type is known, there is no loop, and each File Input exists. `--deep` also loads the workflow the way the editor does and checks the code each node would run against the [safety policy](#safety).

| Option | Default | Meaning |
|---|---|---|
| `WORKFLOW` | required | The `.tds` file. |
| `--deep` | off | Load it like the editor; resolve inputs; check each node's generated code. Takes a couple of seconds. |
| `--no-files` | off | Skip the "input file exists" check. Useful on a build server that does not have the data. |
| `--strict` | off | Treat warnings as errors. |
| `--param`, `--input-dir`, `--output-dir` | none | Same meaning as for `run`; used by `--deep`. A required parameter must be given for `--deep` to pass. |
| `-v`, `-vv` | off | With `--deep`: show the editor's own warnings (`-vv`: everything it logs) on stderr. Hidden by default. |
| `--format {text,json}` | `text` | `json` prints `{"ok": ..., "findings": [...]}`. |

Exit `0` means no errors (and, with `--strict`, no warnings). Exit `2` means invalid. Note that in the quick check a missing input file is a warning (exit 0), while with `--deep` it is an error (exit 2), because `--deep` resolves the inputs the way a run would. If a gate must fail on any warning, always pass `--strict`.

```text
> trigger-designer-cli validate wf\select.tds --deep
ERROR   TD-CLI-005: Required parameter 'input_file' was not given.
INVALID
[exit code 2]

> trigger-designer-cli validate wf\select.tds --deep --param input_file=in\check.csv
OK
[exit code 0]
```

A file that cannot be read or is not a workflow gives exit 2 with a one-line message:

```text
error [TD-CLI-001]: bad.tds is not valid JSON (Expecting property name enclosed in double quotes: line 1 column 2 (char 1)).
```

## info

```text
trigger-designer-cli info WORKFLOW [--format {text,json}]
```

Shows the workflow's SHA-256 and size, the version that saved it, the node counts, every file it reads and writes (as saved and as resolved, and whether it exists), its parameters and whether it is approved. It does not need the input files. `--format json` prints the same facts as one JSON object, for scripts. See the example in the [Quick start](#quick-start).

`approved:` shows one of three things: `yes (by <user> at <time>)`, `no`, or `no - changed since approval of <path>` (you approved an earlier version of the same file).

## approve and the approval flow

```text
trigger-designer-cli approve WORKFLOW [--yes] [--note TEXT] [--format {text,json}]
trigger-designer-cli approve --list [--format {text,json}]
trigger-designer-cli approve --revoke WORKFLOW
```

An approval is the SHA-256 fingerprint of the exact bytes of the `.tds` file, together with who approved it and when. It is stored per user in `approvals.json` in the state folder. Changing the file in any way, even saving it again in the editor without changing anything, changes the fingerprint, and the file must be approved again.

| Option | Meaning |
|---|---|
| `WORKFLOW` | The file to review and approve. |
| `--yes` | Do not ask. Required when there is no terminal (a script, CI, a scheduler). |
| `--note TEXT` | A note stored with the approval, such as a ticket number. |
| `--list` | List approvals: first 12 characters of the fingerprint, time (UTC), user and path. |
| `--revoke WORKFLOW` | Remove the approval of a file. Accepts the path or the full fingerprint. Exit 2 if nothing matched. |

```text
> trigger-designer-cli approve --list
21ca314bd088  2026-10-30T17:48:06Z  kashvinchandrasan  Y:\audit\wf\select.tds
d8a13dc49053  2026-10-30T17:48:50Z  kashvinchandrasan  Y:\audit\wf\select.tds
b90b21cab1f9  2026-10-30T17:51:26Z  kashvinchandrasan  Y:\audit\proj\filter.tds
```

(The first two are the same file before and after adding parameters; each version needs its own approval.)

### The flow

1. **A workflow arrives.** You wrote it, or someone sent it, or it was edited.
2. **You review it.** `info` and `approve` print what it reads, writes and the operations it contains. Open it in the editor if you need more. Read [Security and privacy](security-and-privacy.md) first if the file came from someone else.
3. **You approve it.** `approve` pins that exact file.
4. **It runs.** `run` and scheduled runs check the file's fingerprint against the approvals. If it matches, the run proceeds.
5. **It changes.** The next run refuses with exit 6. A scheduled run reports `TD-CLI-009`; a manual run reports `TD-CLI-008` with the message "changed after it was approved" and who approved the earlier version. Review the change and approve again.

Rules to remember:

- `approve` asks `Approve? [y/N]` only on a terminal. With no terminal, or no input (stdin redirected from a file or `NUL`, as in a scheduled task or CI job), it prints the review block, says to pass `--yes` and exits 64 instead of failing.
- An interactive `run` may use `--allow-unapproved` to skip this once. A scheduled run (`--trigger schedule`) ignores that option; it always needs approval.
- The approvals file is not signed. It stops accidents and casual changes, not someone who can edit your files. On a build server, create the approval as part of the pipeline (`approve --yes`) from a reviewed commit, and keep the state folder read-only afterwards.
- The review block, `info` and `paths` list every file a node reads or writes: File Input, File Output and Workpaper Output (its `output_path`). New file-touching nodes appear there once they are in the op catalogue.
- `--input-dir`, `--output-dir` and `--param` are typed by you, so they are trusted. What the file itself says is not. Approving a workflow approves the paths it contains; pointing it at other folders from the command line is your decision.

## params

A **parameter** is a named setting of a node that you can replace on the command line with `--param NAME=VALUE`, so the workflow does not have to be edited for each month's file.

```text
trigger-designer-cli params list WORKFLOW [--format {text,json}]
trigger-designer-cli params add WORKFLOW --name NAME --node ID_OR_TITLE --setting SETTING
                                [--type {path_in,path_out,string,int}] [--default VALUE]
                                [--required] [--label TEXT]
trigger-designer-cli params remove WORKFLOW --name NAME
```

| Option (`add`) | Default | Meaning |
|---|---|---|
| `--name` | required | Lower-case letters, digits and `_`, starting with a letter, up to 40 characters. |
| `--node` | required | The node's id (a number, see `info`) or its title if the title is unique, such as `"File Input"`. |
| `--setting` | required | Which setting. Only the ones listed in the table below. |
| `--type` | from the setting | Only a check: it must match the setting's kind. |
| `--default` | none | Used when no `--param` is given. |
| `--required` | off | `run` fails with exit 2 if there is no value and no default. |
| `--label` | the name, prettified | A friendlier name for tools. |

`add` and `remove` change the file. The first time, they copy it to `WORKFLOW.bak` (an existing `.bak` is never overwritten). **The file's fingerprint changes, so it needs to be approved again.**

```text
> trigger-designer-cli params add select.tds --name input_file --node "File Input" --setting filePath --required
Added parameter 'input_file' -> node 1429604924240.filePath (backup: select.tds.bak)

> trigger-designer-cli params add select.tds --name output_file --node "File Output" --setting filePath --default Y:/audit/out/select_default.csv
Added parameter 'output_file' -> node 2441464837840.filePath

> trigger-designer-cli params list select.tds
input_file           path_in   node 1429604924240.filePath [required]
output_file          path_out  node 2441464837840.filePath default='Y:/audit/out/select_default.csv'
```

### Which settings can be parameters

Only a short list of safe settings can be changed from the command line, because these values end up inside generated code. Anything else is refused with `TD-CLI-007`.

| Node | Setting | Kind | Allowed values |
|---|---|---|---|
| File Input | `filePath` | `path_in` | a local path or folder or pattern |
| File Input | `include_patterns`, `exclude_patterns` | `string` | comma-separated list; no quotes, backslash or line breaks |
| File Input | `max_files` | `int` | 1 to 100000 |
| File Input | `selected_sheet` | `string` | no quotes, backslash or line breaks |
| File Input | `db_table` | `string` | a plain table name (`orders`, `main.orders`) |
| File Input | `record_limit` | `int` | 0 to 2000000000 |
| File Output | `filePath` | `path_out` | a local path |
| Workpaper Output | `output_path` | `path_out` | a local path ending in `.xlsx` |
| Filter | `value`, `value2` | `string` | only when the Filter is in builder mode; no quotes, backslash or line breaks |
| Split | `random_seed` | `int` | 0 to 2147483647 |
| Split | `estimation_percent` | `int` | 1 to 99 |

```text
> trigger-designer-cli params add select.tds --name bad --node "Select" --setting x
error [TD-CLI-007]: preparation.select.x cannot be a parameter.
  hint: Supported settings: input.file_input.db_table, input.file_input.exclude_patterns, ...
```

The editor keeps the parameters when you save the workflow again.

## paths

```text
trigger-designer-cli paths WORKFLOW [--relativize] [--write] [--format {text,json}]
```

Lists every file path saved in the workflow, where it resolves to, and whether it exists. With `--relativize` it shows (and with `--write` it applies) a rewrite of every path that is inside the workflow's folder into a relative path. `--write` first makes `WORKFLOW.bak`. The file changes, so approve it again.

```text
> trigger-designer-cli paths filter.tds --relativize
[1728622098256] input  D:/Audit/proj/data/check.csv
        -> D:\Audit\proj\data\check.csv (exists)
[1728622028944] output D:/Audit/proj/out/6. out_check_W_filter.csv
        -> D:\Audit\proj\out\6. out_check_W_filter.csv (MISSING)
relative paths (preview):
  [1728622098256] D:/Audit/proj/data/check.csv -> data/check.csv
  [1728622028944] D:/Audit/proj/out/6. out_check_W_filter.csv -> out/6. out_check_W_filter.csv

> trigger-designer-cli paths filter.tds --relativize --write
...
backup: filter.tds.bak
```

(The path prefix in this example was shortened to `D:\Audit` for the page.)

This is the way to make a **deployment copy** that works from wherever the folder is copied or mounted. For a File Input the relative path is stored in both `filePath` and `filePathRel`, the way the editor does it. Paths outside the workflow's folder are left alone; use `--input-dir`, `--output-dir` or parameters for those. "MISSING" for an output is normal before the first run.

## Parameters and path overrides

How a run decides which file to use for a File Input or File Output:

| Order | Source | Notes |
|---|---|---|
| 1 | `--param NAME=VALUE` for a path parameter | Wins over everything. A relative value is relative to the folder you are in when you type the command (the "current folder"). |
| 2 | `--input-dir` / `--output-dir` | Takes the file name from the saved path or the parameter's default (`/` and `\` both accepted) and puts it in `DIR`. |
| 3 | The parameter's default (`--default`) | Relative defaults are relative to the workflow's folder. |
| 4 | The path saved in the workflow | Relative paths are relative to the workflow's folder, never to the current folder. |

Two things follow:

- **Paths saved in the workflow are relative to the workflow file's folder**, not to wherever you or the scheduler happened to start the program. A scheduled task starts in the Windows system folder; this rule is what makes relative paths work there.
- **Command-line paths are relative to your current folder**, as every other command is.

**`filePathRel`.** When the editor saves a File Input it stores the absolute path in `filePath` and, if possible, a path relative to the workflow in `filePathRel`. When the relative path leads to an existing file, the editor (and the CLI) uses it; this is why a project folder that was copied to another drive still finds its data. When you override the input with `--param` or `--input-dir`, the stale `filePathRel` is dropped for that run.

```text
> trigger-designer-cli run wf\select.tds --param input_file=in\check.csv --output-dir Y:\audit\out2
... [TD-CLI-014] The output folder does not exist: Y:\audit\out2 - Create it, or pass --create-output-dirs.
[exit code 2]

> trigger-designer-cli run wf\select.tds --param input_file=in\check.csv --output-dir Y:\audit\out2 --create-output-dirs
... INFO    run.finished status=ok exit_code=0 ...
```

(Here `in\check.csv` was resolved from the current folder `Y:\audit`; `output_file` has a default, so `--output-dir` put `select_default.csv` into `out2`.)

The program also refuses these before any node runs (exit 2, `TD-CLI-014`): two File Outputs with the same file, a File Output that would overwrite one of the inputs, and an output folder that cannot be written. Remote paths such as `http://...` or `s3://...` are not supported (`TD-CLI-006`); the program never touches the network.

## Workpaper Output on the command line

A [Workpaper Output](nodes/input-output.md#workpaper-output) node runs the same way as in the editor, with these points:

- **Where it is written.** `--output-dir DIR` puts the workbook into `DIR` under the file name saved in the node, and `--param NAME=PATH` can set its `output_path` (add the parameter with `params add ... --setting output_path`). Both go through the same precedence as for a File Output; see [Parameters and path overrides](#parameters-and-path-overrides).
- **If the file exists** is honoured. With **New version** (the default) the CLI picks the first free name before it starts, so a second run writes `name (2).xlsx` and keeps `name.xlsx`. **Replace** keeps the name. **Stop with error** refuses an existing file before any node runs: exit 2, `TD-OUT-010`.
- **The full exceptions list.** When the Row limit cuts the listing, the file `<name>_exceptions_full.csv` is written next to the final workbook (with the final name, not the temporary one). Unlike the workbook it is written straight to its place, not as part of the all-or-nothing move at the end of the run.
- **Source files.** The node's **Source files** (one path per line) follow `--input-dir` like a File Input, and relative lines are relative to the workflow's folder. They are listed by `info`, `approve`, `validate` and `paths`, and `paths --relativize --write` rewrites them like any other path.
- **No Run log sheet.** The command-line run does not give the workpaper the run's record, so the workbook has no **Run log** sheet and the Summary says that no run record is available. The run record is still written next to the workflow (or in `--record-dir`), and it lists the workpaper with its SHA-256.
- **Workflow sheet.** It shows the nodes that feed the workpaper. A File Input moved with `--input-dir` appears with the path that was actually read.

## Run records and verify-log

Every real run writes a **run record**, the same sealed, hash-chained record the editor writes when you press Run. It lists the nodes, their results and row counts, the fingerprint of every input and output, and the code that ran. It goes to a folder named `<workflow name>.runs` next to the workflow (the folder the editor's Run History tab shows), or to `--record-dir`. A record is written for every outcome, including failed, cancelled and timed-out runs; `--no-record` turns it off (a dry run never writes one).

Alongside it, the CLI writes a small file `<record id>.cli.json` into `logs` in the [state folder](#where-the-files-go): the command line, the resolved parameters, the host name, the exit code and the fingerprint of the approval that allowed it.

`verify-log` asks: is this record still intact, and do the files on disk still match it?

```text
trigger-designer-cli verify-log [RECORD_OR_FOLDER] [--workflow WORKFLOW] [--no-files] [--format {text,json}]
```

| Argument | Meaning |
|---|---|
| `RECORD_OR_FOLDER` | A record file, or a folder of records (all of them are checked, plus the chain between them). Left out: the newest record in the folder of `--workflow`, or, without `--workflow`, in the program's own run folder. |
| `--workflow WORKFLOW` | Also check that this is the workflow file that was run. |
| `--no-files` | Skip the file checks (outputs and inputs); check only the record. |
| `--format {text,json}` | `json` prints `{"target": ..., "ok": ..., "findings": [...]}`. |

What it checks:

| Check | Result if it fails |
|---|---|
| The record is readable, follows the schema and its own hash matches its content | error |
| The overall status agrees with the node results | error |
| The workflow file's fingerprint equals the one recorded (needs `--workflow`) | error |
| Each output file exists and still has the recorded size and SHA-256 | error |
| Each input file still exists and has the recorded SHA-256 | warning only (inputs are legitimately refreshed) |
| For a folder: the chain of records is unbroken | error |

Exit `0` means no errors. Exit `10` means a mismatch.

```text
> trigger-designer-cli verify-log select.runs\a9153285a43e41248c0ad03b9129da2d.json --workflow select.tds
checked: select.runs\a9153285a43e41248c0ad03b9129da2d.json
VERIFIED
[exit code 0]

> trigger-designer-cli verify-log select.runs
checked: select.runs
VERIFIED
[exit code 0]
```

After an output file was edited:

```text
> trigger-designer-cli verify-log select.runs\a9153285a43e41248c0ad03b9129da2d.json --workflow select.tds
checked: select.runs\a9153285a43e41248c0ad03b9129da2d.json
ERROR   TD-CLI-017: output size changed: Y:/audit/out/out_check_W_select.csv
VERIFICATION FAILED
[exit code 10]
```

Two limits to know. A run with `--no-hash` has no fingerprints, so the file checks have nothing to compare. And, as in the editor, removing the newest records from the end of a folder cannot be detected by the chain; note the head hash from a run when you need to prove completeness (see [Run history and the audit trail](run-history-and-audit-trail.md)). When a record cannot be found at all, `verify-log` says so (`TD-CLI-001`, exit 2).

## Exit codes

The exit code is part of the program's contract and does not change between versions. When more than one thing applies, the first row of this order wins: cancelled, timed out, memory, output not written, refused, node failed, ok.

| Code | Name | Meaning | What to do |
|---|---|---|---|
| 0 | OK | Every node ran and the outputs are in place (or a dry run or validation passed). | Nothing. |
| 1 | NODE_FAILED | A node failed (with `--keep-going`, at least one). Old outputs are untouched. | A data or logic problem. Read the failing node and its `TD-` code in the message or in `run.finished`. Fix the data or the workflow. Do not just retry. |
| 2 | INVALID | The workflow or the request is wrong: unreadable file, newer file format, unknown node, loop, bad or missing parameter, missing input, missing output folder, low disk space, or a warning under `--strict`. | A set-up problem. Fix it (`validate`, `paths`, `--input-dir`), then run again. |
| 3 | INTERNAL | An unexpected error in the program. A traceback is on stderr. | Report it with the traceback. Retrying will not help. |
| 4 | TIMEOUT | `--timeout` was exceeded. Staged outputs were discarded. | Raise `--timeout`, or investigate why it is slow. May be retried. |
| 5 | MEMORY | `--max-memory` was exceeded. Staged outputs were discarded. | Raise `--max-memory`, use a smaller input, or free memory. May be retried. |
| 6 | REFUSED | Not approved, edited since approval, contains a user-code node without the permission, or the generated code was rejected by the safety policy. | A person must look. Check who changed the file, then `approve` it again. If the policy rejected it, do not run the file. |
| 7 | BUSY | Another run of the same workflow holds the lock. | Retry later. If no run is active, run again: a dead run's lock clears itself. |
| 8 | COMMIT_FAILED | The nodes ran but the outputs could not be moved into place (a file is open in Excel, the disk is full). Previous files were restored. | Close the file or free the disk, then retry. |
| 9 | SCHEDULER | `schtasks` failed, or the `schedule` command was used on a system that is not Windows. | Read the message from Windows. Run from an account allowed to create tasks. |
| 10 | VERIFY_FAILED | `verify-log` found a mismatch. | Treat the output as changed since the run; investigate. |
| 64 | USAGE | The command line is wrong (an unknown option, a missing argument). Nothing ran. | Fix the command; see `--help`. |
| 130 | CANCELLED | Ctrl+C, Ctrl+Break or a termination request. Outputs untouched. | Run again if it was not intended. |

For a wrapper script: treat `0` as success; retry later on `4`, `5`, `7` and `8`; alert a person on `1`, `2`, `6`, `3`, `9`, `10` and `64`; do not retry `1`, `2`, `3` and `6` blindly.

## Logs and events

**Text mode (the default).** Human-readable lines on **stderr**, one per event, with a time, a level and the event name. A failure ends with one summary line, `FAILED at node '...' [TD-...] ... - hint`. `stdout` stays empty. Use `--quiet` for only warnings, errors and the start and end.

**JSON mode (`--log-format json`).** One JSON object per line on **stdout**. Everything else, including anything a node prints, goes to stderr, so a script can read stdout as clean JSON lines. `--log-file FILE` writes the same lines to a file in either mode (UTF-8, appended). The file is rotated at 10 MB and three older copies are kept. In PowerShell, do not redirect with `>` to capture the JSON (that writes UTF-16); use `--log-file`.

```text
{"ts":"2026-10-30T17:48:18.111Z","level":"INFO","event":"run.started","run_id":"cd53d445...","workflow":"Y:\\audit\\wf\\select.tds","sha256":"21ca314b...","trigger":"manual","pid":21980,"version":"0.1.0","dry_run":false,"params":{}}
{"ts":"2026-10-30T17:48:19.590Z","level":"INFO","event":"node.started","run_id":"cd53d445...","node_id":1429604924240,"title":"File Input","op":"input.file_input","index":0,"total":3}
{"ts":"2026-10-30T17:48:19.615Z","level":"INFO","event":"node.finished","run_id":"cd53d445...","node_id":1429604924240,"title":"File Input","status":"ok","duration_s":0.025,"error":null}
{"ts":"2026-10-30T17:48:19.798Z","level":"INFO","event":"output.committed","run_id":"cd53d445...","path":"Y:\\audit\\out\\out_check_W_select.csv","size_bytes":840,"sha256":"dd1e6c4e..."}
{"ts":"2026-10-30T17:48:19.849Z","level":"INFO","event":"run.finished","run_id":"cd53d445...","status":"ok","exit_code":0,"duration_s":1.741,"nodes_ok":3,"nodes_failed":0,"record_path":"Y:\\audit\\wf\\select.runs\\a9153285....json","record_run_id":"a9153285...","errors":[]}
```

Every line has `ts` (UTC, to the millisecond, ending `Z`), `level`, `event` and `run_id`. Fields are only ever added in later versions, never renamed or removed, so a script that reads the fields it knows keeps working.

Note that `run_id` in the log is the id of this command-line run. The run record has its own id, given as `record_run_id` in `run.finished`.

| Event | When |
|---|---|
| `run.started` | At the start. Workflow, fingerprint, who started it (`trigger`), process id, version, parameters. |
| `plan.resolved` | After parameters and paths were resolved: approval, inputs (exists, size), outputs (final and temporary path), warnings. |
| `warning` | Something to read but not fatal. |
| `node.started`, `node.finished`, `node.skipped` | Each node. `node.finished` has `status` (`ok`, `failed`), `duration_s` and, on failure, `error` with `code`, `title` and `hint`. `node.skipped` names the node whose failure blocked it (`--keep-going`). |
| `log` | A message from the program's own log (see `-v`). |
| `output.committed`, `output.commit_failed` | An output was moved into place (size and SHA-256), or could not be. |
| `run.cancelling`, `run.cancel_forced` | Ctrl+C was received; the grace period ran out. |
| `run.timeout`, `run.memory_exceeded` | A limit was hit. |
| `script.written` | `--emit-script` saved the script. |
| `run.finished` | Always the last event. `status` (`ok`, `failed`, `cancelled`, `refused`, `invalid`), `exit_code`, `duration_s`, `nodes_ok`, `nodes_failed`, `record_path`, `record_run_id` and `errors`: a list of `{node_id, title, code, message, hint, node}` using the same plain-language wording as the editor. |

A busy workflow (exit 7) reports `status` `invalid`; use `exit_code`, not `status`, in scripts.

Reading the result in PowerShell:

```text
$last = Get-Content D:\logs\sales.jsonl | Select-Object -Last 1 | ConvertFrom-Json
if ($last.exit_code -ne 0) { $last.errors | Format-Table node, code, message }
```

## Timeouts, memory and threads

- `--timeout SEC` is a limit for the whole run, from the moment the run starts, including loading. It defaults to 3600 (one hour); `0` removes it. When it fires the program stops, the temporary outputs are removed, a record is written and the exit code is 4.
- `--max-memory MB` is a ceiling for the whole program, checked four times a second. The program needs roughly 70 MB before it has read any data (in a test, a 17-row workflow with a limit of 50 MB was stopped at about 72 MB), so set the limit generously. When it fires the exit code is 5.
- `--threads N` limits the data engine to `N` threads, so a scheduled run does not use every core while people work. It does not change the result.
- A node that is already running cannot be stopped in the middle; the limits act when the watchdog sees them and then end the process. The previous outputs are never changed by such a stop.
- Before it starts, the program checks that each output drive has at least `--min-free-mb` (64) free. Large outputs need more room than that: the temporary file and the old file exist side by side until the move.

See also [Limits and performance](limits-and-performance.md).

## Scheduling on Windows

`schedule` creates a task in Windows Task Scheduler for you, so you do not have to build one by hand. It is Windows only; on other systems it exits with 9.

```text
trigger-designer-cli schedule add NAME WORKFLOW (--daily HH:MM | --weekdays HH:MM | --weekly DAYS@HH:MM | --hourly N | --once YYYY-MM-DDTHH:MM)
                                  [--param NAME=VALUE]... [--run-whether-logged-on] [--skip-missed]
                                  [--timeout SEC] [--max-memory MB] [--print-only] [--force]
trigger-designer-cli schedule list [--format {text,json}]
trigger-designer-cli schedule show NAME
trigger-designer-cli schedule remove NAME
```

| Option (`add`) | Default | Meaning |
|---|---|---|
| `NAME` | required | Letters, digits, `-` and `_`, up to 64 characters. The task appears as `TriggerDesigner\NAME` in Task Scheduler. |
| `WORKFLOW` | required | The workflow. It must already be approved. |
| `--daily HH:MM` | one trigger is required | Every day at that time (24 hours). |
| `--weekdays HH:MM` | | Monday to Friday. |
| `--weekly DAYS@HH:MM` | | For example `MON,THU@06:30`. Days: `MON TUE WED THU FRI SAT SUN`. |
| `--hourly N` | | Every `N` hours, 1 to 720, starting now. |
| `--once YYYY-MM-DDTHH:MM` | | One time, for example `2026-11-02T06:30`. |
| `--param NAME=VALUE` | none | Parameters for each scheduled run. Checked when you add. Path values are made absolute at that moment. |
| `--run-whether-logged-on` | off | Run even when you are not logged on (see below). |
| `--skip-missed` | off | If the computer was off at the scheduled time, do not run later. Default: run as soon as possible. |
| `--timeout SEC` | `3600` | Passed to `run`. The task's own limit is this plus 5 minutes. |
| `--max-memory MB` | none | Passed to `run`. |
| `--print-only` | off | Show the exact commands and the task definition; create nothing. |
| `--force` | off | Replace an existing task of the same name. |

Times are your computer's local time. Records and log timestamps are UTC.

### Step by step: a nightly run

1. **Prepare a deployment copy.** Make paths relative or use parameters, so the task does not depend on your current folder:
   `trigger-designer-cli paths wf\select.tds --relativize --write`
2. **Make sure it runs by hand.** `trigger-designer-cli run wf\select.tds --dry-run ...`, then a real run, and check the output.
3. **Approve it.** Scheduling refuses a file that is not approved:
   ```text
   > trigger-designer-cli schedule add bad wf\filter.tds --daily 02:00
   error [TD-CLI-008]: This workflow has not been approved, and scheduled runs always need approval.
     hint: Review it with `approve wf/filter.tds` first.
   [exit code 6]
   ```
   Run `trigger-designer-cli approve wf\select.tds`.
4. **Look before you create.** `--print-only` shows what would be created and creates nothing:
   ```text
   > trigger-designer-cli schedule add nightly wf\select.tds --daily 02:30 --param input_file=Y:\audit\in\check.csv --print-only
   command: C:\...\python.exe -m trigger_designer.cli --state-dir Y:\state run Y:\audit\wf\select.tds --param input_file=Y:\audit\in\check.csv --trigger schedule --log-format json --log-file Y:\state\logs\nightly.jsonl --timeout 3600
   schtasks: schtasks /Create /TN TriggerDesigner\nightly /XML Y:\state\schedules\nightly.xml /F
   <?xml version="1.0" encoding="UTF-16"?>
   <Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
     ...
     <Triggers><CalendarTrigger><StartBoundary>2026-10-30T02:30:00</StartBoundary>...<ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay></CalendarTrigger></Triggers>
     <Principals><Principal id="Author"><UserId>US\kashvinchandrasan</UserId><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>
     <Settings>
       <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
       <StartWhenAvailable>true</StartWhenAvailable>
       ...
       <ExecutionTimeLimit>PT3900S</ExecutionTimeLimit>
     </Settings>
     <Actions Context="Author"><Exec><Command>C:\...\python.exe</Command><Arguments>-m trigger_designer.cli ... </Arguments><WorkingDirectory>Y:\audit\wf</WorkingDirectory></Exec></Actions>
   </Task>
   ```
   With the installed program the command is `trigger-designer-cli.exe` (the program that is running when you add it); in a source checkout it is `python -m trigger_designer.cli`. The state folder is written into the command, so the task finds your approvals whichever way it is started.
5. **Create it.** The same command without `--print-only`. It prints `Scheduled 'nightly' (TriggerDesigner\nightly).` If a task of that name exists it refuses; add `--force` to replace.
6. **Try it once from Task Scheduler.** Open Task Scheduler, find `TriggerDesigner` in the Task Scheduler Library, right-click the task and choose **Run**. Then read the log `logs\nightly.jsonl` in the state folder. Do this before you rely on the schedule.
7. **Look after it.**
   - `trigger-designer-cli schedule list` shows each task with when it runs (for example `daily at 02:30`), its next run time, status and the exit code of the last run (the `last result`; `0` is success, other numbers are the [exit codes](#exit-codes)).
   - `trigger-designer-cli schedule show nightly` prints one task as JSON (its definition and the live state).
   - `trigger-designer-cli schedule remove nightly` deletes the task and its stored files. Removing a task that Windows no longer has only warns.

What the task is set up to do:

- Starts in the **workflow's folder**, so relative paths work.
- Never overlaps itself: Windows ignores a new start while the previous one still runs, and the CLI's own lock (exit 7) is a second guard.
- A missed run starts as soon as possible (turn off with `--skip-missed`).
- Runs at the lowest privilege level, as you.
- The run is marked `--trigger schedule`: it needs approval and cannot use `--allow-unapproved`. If the workflow file changes after scheduling, the next run exits with 6 (`TD-CLI-009`) until you approve it again. Update the approval, and the task keeps working: it is the file's fingerprint that matters, not the task.
- Logs JSON lines to `<state folder>\logs\NAME.jsonl`.

### Logged on or not

By default the task runs **only while you are logged on**. That is the most reliable setting for mapped network drives and anything that needs your sign-in. A task that is set up this way does nothing when nobody is logged on; that is the first thing to check for "my task did not run".

`--run-whether-logged-on` runs the task with no one logged on (the Windows setting S4U). It has no password, because **the program never asks for or stores a password**. The price is that the task has no network credentials: it can read local drives, but not network shares or mapped drives that need your sign-in. Use local paths, or a service account set up by IT in Task Scheduler directly.

### Before you rely on it

The XML, the command line, the argument handling and the way `list` reads Windows's answer are tested against a stand-in for `schtasks`, and `--print-only` is checked by eye. A real create, run, list and remove cycle on a Windows machine has not yet been recorded. On your first task, do steps 4 to 6 and check that the task starts and that the log appears.

## Other schedulers and containers

The CLI only generates Windows Task Scheduler tasks. Anything else just runs the command:

```text
30 2 * * *  trigger-designer-cli run /srv/wf.tds --trigger schedule --log-format json --log-file /var/log/td/wf.jsonl
```

A cron line, a systemd timer, launchd, a CI job or a container entry point all work the same: run the command, read the exit code. You do not need `flock` or similar, because the program has its own run lock. The container recipe in [CLI.md](../CLI.md) is a sketch that has not been built or run yet; treat it as a starting point for IT, not a tested image. The scheduling commands (`schedule ...`) exit with 9 on systems other than Windows.

## Safety

A `.tds` file can come from anyone, and the program runs code that the file's nodes generate. The editor takes care that a workflow's text becomes values and never programs; the command line, which runs unattended, adds four more layers.

1. **The file is checked.** The format must be readable and not newer than this program, node types must be known, and there must be no loop.
2. **The exact file must be approved.** See [the approval flow](#approve-and-the-approval-flow).
3. **Nodes with user-written code are refused** unless you pass `--allow-custom-code` and the file is approved. No node in the current version contains user-written code, so today this protects only future versions.
4. **The code of every node is checked before it runs.** The check allows only the program shapes and imports that the program's own nodes produce, and it blocks:
   - opening files with Python's `open`, `eval`, `exec`, `compile`, `getattr`, `__import__` and any name that starts with two underscores;
   - system and process access: `os.system`, `subprocess`, `sys`, `socket`, `shutil`, `pathlib`, `ctypes`, environment variables, deleting or creating folders;
   - network and database access from the data engine: `read_database`, extensions, `http`, `s3`, `ATTACH`, `COPY`, `read_csv('...')` inside SQL, and anything other than a single `SELECT` or `WITH` query;
   - any file path that is not one the approved workflow declared. A tampered path in a setting stops the run with exit 6;
   - imports other than a fixed list.

   While it runs the code also gets a reduced set of built-in functions.

A refusal looks like this (a deliberately tampered node, exit 6):

```text
FAILED at the run [TD-CLI-010] The safety policy refused the code of 'Select': line 1: import of 'subprocess' is not allowed - Open the workflow in the editor and look at that node; do not run files you do not trust.
[exit code 6]
```

The program never needs and never uses the network.

**What this is not.** It is a strong safety net against mistakes and against the kind of tampering that edits a setting in a file. It is not an operating-system sandbox. A file you approve may read and overwrite the paths it declares. That is what the approval is for. For unattended jobs:

- Do not approve files you do not trust. Open them in the editor first.
- Run scheduled jobs under an ordinary account with access to only the folders they need; if you can, give it write access only to the output folder.
- Keep the approvals file and the workflows in places others cannot write to.
- For an audit trail, keep the run records and use `verify-log`.

## Where the files go

| What | Where |
|---|---|
| The program's own state (`--state-dir`, `TRIGGER_DESIGNER_STATE_DIR`) | `%LOCALAPPDATA%\Trigger Designer\cli` |
| Approvals | `<state>\approvals.json` |
| Run locks and temporary work copies | `<state>\locks`, `<state>\work` (deleted after the run) |
| Temporary outputs | Next to each final file as `.name.tdtmp-<run>.ext`; for an output folder with a quote or brace in its name, under `<state>\staging` |
| Schedules | `<state>\schedules\NAME.json` and `NAME.xml` |
| Logs and run sidecars | `<state>\logs` (`NAME.jsonl` for scheduled runs, `<record id>.cli.json` for each run) |
| Run records | `--record-dir`, otherwise `<workflow name>.runs` next to the workflow |
| The script of a run | `--emit-script FILE` only; the editor's own is in its application data folder |

A run never modifies the workflow file. It works on a private copy in the `work` folder.

## Troubleshooting

| Symptom | What it means and what to do |
|---|---|
| Exit 6, `This workflow has not been approved` | Run `trigger-designer-cli info wf.tds`; the `approved:` line says `no` or `no - changed since approval`. Review and `approve`. |
| Exit 6 after a save in the editor | Saving changes the fingerprint even when nothing changed. Approve again. After `params add` or `paths --write` too. |
| Exit 7 `This workflow is already running` | Another run holds the lock (the message names its process id). If that run is gone, run again; locks of dead runs clear themselves. A lock is per workflow file, so two different files can run together. |
| Exit 8 `could not write ...` | The output is open in Excel or another program, or the disk is full. Close the file, then run again. Nothing was changed; the previous files are still there. |
| Exit 2 `Cannot find the input file` (`TD-IN-001`) | `trigger-designer-cli paths wf.tds` shows which saved path is missing. Map it with `--input-dir`, or a parameter. |
| Exit 2 `TD-CLI-014` | The output folder is missing or not writable, or two outputs have the same file, or an output would overwrite an input. Use `--create-output-dirs`, or fix the names. |
| Exit 2 on a file that works in the editor, with `--strict` | A warning such as "legacy v1 file" counts as an error under `--strict`. Open the file in the editor, save it, approve it again, or drop `--strict`. |
| Exit 3, a Python traceback | Report it with the traceback. A frequent cause is an unreadable console encoding, below. |
| A scheduled task that never ran | Without `--run-whether-logged-on` the task only runs while you are logged on. Open Task Scheduler and check its History, and `schedule list` for the last result. Also check `logs\NAME.jsonl`. |
| A scheduled task ends with exit 6 (`TD-CLI-009`) | The workflow was edited after it was scheduled. Approve it again; no need to recreate the task. |
| `could not query Windows` in `schedule list` | `schtasks` was not available or was refused. Your own task definitions are still shown. |
| You want to see what the editor's node code prints or logs while loading | Run with `-vv` (`run` and `validate --deep`): its `print` output and log lines are shown as debug lines. By default they are hidden, and `stdout` is never touched, so `--log-format json` stays clean. |
| Nothing at all appears and the exit code is 64 | The command line was wrong. The usage and the reason are on stderr. |

### Headless Qt and "no display"

The nodes are the editor's own, and they need Qt even though nothing is drawn. The CLI starts Qt itself on its "offscreen" platform (no window, no screen, no graphics card) and ignores the `QT_QPA_PLATFORM` of the environment, so it works on a server with no desktop. (`TRIGGER_CLI_QPA` can name another platform for diagnosis.) No window is ever created. If it will not start on a Linux container, the offscreen platform needs a few system libraries; see the container sketch in [CLI.md](../CLI.md).

### Locked files

Windows does not let a program replace a file that another program has open. Excel is the usual one. The CLI checks that the folder can be written before it starts, but it cannot know in advance that you will open the file during the run. That case ends with exit 8 after the nodes have run, and your earlier output is intact. For a scheduled job that writes into a folder that people open in Excel, write to a folder they do not use and copy from there.

### A stale lock

If the computer lost power during a run, the next run of the same workflow removes the dead run's temporary files and, if an output was parked during the move, puts it back. It does not need any action from you.

### cp1252 and other console encodings

Older Windows consoles, redirected output and scheduled tasks use a "code page" such as cp1252 that cannot show every character. The program now prints UTF-8 when its output is piped or redirected, and replaces (with `?`) a character the console cannot show, so a Cyrillic or Chinese file name no longer stops a command. If you choose the encoding yourself with `PYTHONIOENCODING` (for example `cp1252`) the program honours it and replaces what does not fit. To keep every character on a console or in a pipe that reads a code page, tell Python to use UTF-8 before you start the program:

```text
set PYTHONUTF8=1
```

(or `$env:PYTHONUTF8 = "1"` in PowerShell, or `set PYTHONIOENCODING=utf-8`), and for the console itself `chcp 65001`. Put the variable into the scheduled task's environment or into a small `.bat` that sets it and calls the program. Workflow files themselves can be UTF-8 or the machine's code page; both are read. The JSON log lines and `--log-file` are always UTF-8.

### Paths, quotes and drives

- Put paths with spaces in double quotes. In Command Prompt and PowerShell a backslash before the closing quote swallows the quote: write `--input-dir "D:\in"` or `--input-dir D:/in`, not `--input-dir "D:\in\"`.
- Both `/` and `\` work in paths given to the program.
- A workflow on a mapped network drive or a `subst` drive works: `paths --relativize` compares the paths as saved first and, if that finds them apart, their real locations, so both spellings of the folder are recognised.

### Something is slow

A single run has a fixed cost of about two seconds for loading Qt and the data engine, plus the time the nodes need. A virus scanner can add to that. If many small workflows must run, call the program as a library or batch them into one workflow; ask a developer. For big files see [Limits and performance](limits-and-performance.md).

## See also

- [Running workflows](running-workflows.md): the same run, from the editor.
- [Run history and the audit trail](run-history-and-audit-trail.md): what is in a record, and how to verify and compare in the editor.
- [Errors and problems](errors-and-problems.md): the `TD-` codes.
- [Security and privacy](security-and-privacy.md): before you open a file from someone else.
- [CLI.md](../CLI.md): the short command reference. [CLI internals](../dev/cli-internals.md): the developer's view.
