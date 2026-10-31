# Running workflows without the editor (`trigger-designer-cli`)

`trigger-designer-cli run workflow.tds` runs a saved workflow with no window and
no person: deterministic exit codes, structured logs, the same run record the
editor writes, outputs that are never half-written, and a safety gate for `.tds`
files written by other people. The same command is what a scheduler, a CI job or
a container runs.

The program starts the editor's own node classes on Qt's offscreen platform, so
a workflow gives the same result headless as it does when you press Run. (The
tests compare the two: output files byte for byte, apart from row order for
hash-join outputs, and the run records field by field.) Commands that only read
files (`info`, `validate` without `--deep`, `approve`, `params`, `paths`,
`schedule`) never load Qt, Polars or DuckDB, `verify-log` never loads Qt, and
they start in about a second or less.

This page is the short reference. Longer pages:

* [User guide](guide/cli.md): installing, quick start with real output, every
  command and option, the approval flow, scheduling step by step, safety,
  troubleshooting.
* [Developer page](dev/cli-internals.md): architecture, data flow of `run`,
  import discipline, adding a command or a node, tests, packaging, what is not
  verified.

```text
trigger-designer-cli [--version] [--state-dir DIR] <command> [options]

run         Run a workflow and write its outputs
validate    Check a workflow file (add --deep to load it like the editor)
info        Show what a workflow reads, writes and needs
approve     Pin a reviewed workflow file so it may run unattended
verify-log  Check a run record against the files it describes
params      List, add or remove run-time parameters stored in a workflow
paths       Show saved file paths; optionally make them relative
schedule    Create, list or remove Windows scheduled runs
```

From a source checkout use `python -m trigger_designer.cli ...` (or `uv run
trigger-designer-cli ...`); the installer also provides `trigger-designer-cli.exe`
beside the editor (optional PATH entry).

## What "server ready" means here

A stateless command: no GUI dependency, no hidden state except three per-user
folders (CLI state, run records, approvals), deterministic exit codes, logs on
stdout or in a file, safe to kill. A scheduler, a CI job or a container supplies
the "server". Out of scope: a web UI, multi-user operation, remote databases,
authentication, queueing.

## Operating procedure

1. Author in the editor. Optionally expose settings as parameters:
   `trigger-designer-cli params add wf.tds --name input_file --node "File Input" --setting filePath --required`
2. Make a deployment copy: `trigger-designer-cli paths wf.tds --relativize --write`
   (keeps `wf.tds.bak`). Relative paths resolve against the folder of the `.tds`.
3. Review and pin: `trigger-designer-cli approve wf.tds` (prints what it reads and
   writes; answer `y`). In CI: `approve wf.tds --yes --note "PR 123"`.
4. Dry run: `trigger-designer-cli run wf.tds --dry-run --param input_file=D:\in\today.csv`.
   Exit 0 means the inputs exist, the outputs are writable and every node's code
   passed the safety policy. Nothing is executed or written.
5. Run: `trigger-designer-cli run wf.tds --param input_file=D:\in\today.csv --log-format json --log-file D:\logs\wf.jsonl`
6. Audit later: `trigger-designer-cli verify-log <record>.json --workflow wf.tds`
7. Schedule (Windows): `trigger-designer-cli schedule add nightly wf.tds --daily 02:30 --param input_file=D:\in\today.csv`

## `run`

```text
run WORKFLOW [--param NAME=VALUE]... [--input-dir DIR] [--output-dir DIR] [--dry-run]
             [--timeout SEC=3600] [--max-memory MB] [--threads N] [--cancel-grace SEC=10]
             [--min-free-mb N=64] [--create-output-dirs] [--strict] [--keep-going]
             [--allow-unapproved] [--allow-custom-code]
             [--record-dir DIR] [--no-record] [--no-hash] [--emit-script FILE]
             [--log-format {text,json}] [--log-file FILE] [-v|-vv] [--quiet]
             [--trigger {manual,schedule}]
```

Outputs are written to temporary files next to the final ones
(`.name.tdtmp-<run>.ext`) and moved into place only when every node succeeded.
A failed, cancelled or killed run never changes an existing output. With
`--keep-going`, branches that do not depend on a failed node still run and the
outputs of the File Output nodes that succeeded are committed. Leftovers of a
killed run are swept by the next run of the same workflow.

* `--param NAME=VALUE` overrides a parameter defined in the workflow (splits on the
  first `=`). Only these settings can be parameters: File Input `filePath`,
  `include_patterns`, `exclude_patterns`, `max_files`, `db_table`, `selected_sheet`,
  `record_limit`; File Output `filePath`; Workpaper Output `output_path`; Filter `value`/`value2` (builder mode);
  Split `random_seed`, `estimation_percent`. Anything else is refused
  (`TD-CLI-007`) because those strings reach code generation.
* Precedence for a path setting: `--param`, then `--input-dir`/`--output-dir`
  (same file name as saved, either `/` or `\` accepted), then the parameter's
  default, then the saved value. Overriding a File Input path removes its stale
  `filePathRel`. Relative `--param` paths resolve against the shell's current folder;
  paths saved in the workflow resolve against the folder of the `.tds`.
* `--timeout` is a whole-run wall clock (0 = none); `--max-memory` is an absolute
  process memory ceiling checked every 0.25 s. Both end the process (exit 4 / 5);
  the staged outputs are discarded.
* **Cancellation.** Ctrl+C, Ctrl+Break or SIGTERM ask the run to stop after the
  current node. A node that is already running cannot be interrupted (generated
  code runs inside Polars or DuckDB); after `--cancel-grace` seconds the process
  exits 130 and outputs are not touched. A second signal exits immediately.
* **Workpaper Output** follows `--output-dir` and `--param`, and its `source_files`
  follow `--input-dir`. `If the file exists` is decided before the run starts: `version`
  writes `name (2).xlsx` on a second run, `fail` exits 2 with `TD-OUT-010`, `replace`
  keeps the name. A row-limited workpaper's `<name>_exceptions_full.csv` is written
  beside the final workbook. The CLI run gives the workpaper the in-flight run record, so it has a Run log
  sheet (omitted, with the reason on the Summary, under `--no-record`). See [guide/cli.md](guide/cli.md#workpaper-output-on-the-command-line).
* `--emit-script FILE` also saves the generated Python script.
* The run record is the same sealed, hash-chained record the editor writes
  (`--record-dir` or next to the workflow in `<name>.runs`). One record per run, also
  for cancelled, timed-out and failed runs. A sidecar `<record id>.cli.json`
  (arguments, resolved parameters, approval hash) goes to `<state>/logs`.

## Exit codes (frozen contract)

| Code | Name | Meaning |
|---|---|---|
| 0 | OK | all nodes ran, outputs committed (or the dry run is fine) |
| 1 | NODE_FAILED | a node raised (with `--keep-going`: at least one) |
| 2 | INVALID | unreadable/invalid workflow, newer schema, unknown node, cycle, bad parameter, missing input, missing output folder, low disk, `--strict` warnings |
| 3 | INTERNAL | unexpected error in the CLI |
| 4 | TIMEOUT | `--timeout` exceeded |
| 5 | MEMORY | `--max-memory` exceeded |
| 6 | REFUSED | not approved, edited since approval, custom-code node, generated code rejected by the safety policy |
| 7 | BUSY | another run holds the lock for this workflow |
| 8 | COMMIT_FAILED | nodes ran but the outputs could not be moved into place (locked by Excel, disk full); previous files restored |
| 9 | SCHEDULER | `schtasks` failed, or not Windows |
| 10 | VERIFY_FAILED | `verify-log` found a mismatch |
| 64 | USAGE | bad command line |
| 130 | CANCELLED | Ctrl+C / Ctrl+Break / SIGTERM |

When several apply: cancelled > timeout > memory > commit failed > refused > node failed > ok.

**What a wrapper should do**

| Exit | Action |
|---|---|
| 0 | success |
| 4, 5, 7, 8 | transient or environmental: retry later |
| 1 | data/logic problem: alert; do not blindly retry (read `run.finished.errors[]`) |
| 2 | configuration problem: alert and fix |
| 6 | a human must `approve` (or investigate a changed or hostile file) |
| 130 | operator cancelled |
| 3, 9, 10, 64 | bug / scheduler / verification / usage: alert |

## Log events (`--log-format json`)

One JSON object per line on **stdout** (everything else, including anything nodes
`print`, goes to stderr); `--log-file` always writes the same lines. Common keys:
`ts` (UTC, ms, `Z`), `level`, `event`, `run_id`. Events: `run.started`,
`plan.resolved`, `node.started`, `node.finished`, `node.skipped`, `warning`, `log`,
`output.committed`, `output.commit_failed`, `run.cancelling`, `run.cancel_forced`,
`run.timeout`, `run.memory_exceeded`, `script.written`, `run.finished`. Keys are only
ever added. `run.finished` carries `status` (`ok|failed|cancelled|refused|invalid`),
`exit_code`, `duration_s`, `nodes_ok`, `nodes_failed`, `record_path`,
`record_run_id` and `errors[{node_id,title,code,message,hint}]`, where the codes
and wording come from the plain-language error catalogue (`TD-*`). `--log-file` is
rotated at 10 MB (three backups). Text mode prints human lines on stderr and ends
with one line such as `FAILED at node 'Formula' [TD-SCH-001] ... - hint`.

## Safety model

`.tds` files can come from anyone and their generated code is executed. The CLI
therefore always:

1. validates structure (schema newer than supported, unknown node types, cycles);
2. requires **approval** of the exact file: `approve` pins the SHA-256 of the bytes;
   any edit, even a re-save, needs a new approval. `--allow-unapproved` is for
   interactive use only and is ignored for `--trigger schedule`. The approvals
   file is per user and not signed; in CI generate it in the pipeline and mount it
   read-only (`--state-dir`);
3. refuses nodes with user-written code unless `--allow-custom-code` and approved
   (no current node has any);
4. checks every node's generated code against a policy before it runs: allowed
   syntax and imports only, no dunder access, `open`/`eval`/`exec`/OS APIs,
   non-`SELECT` SQL, or any file path the approved workflow did not declare. The
   exec globals use restricted builtins. A future node that needs another import
   adds one row to `GENERATED_IMPORTS` in `core/headless/code_policy.py` plus an
   attack-table row.

This is defence in depth against accidental and casual abuse, not an OS sandbox:
approved paths can still be read and overwritten (that is what approval reviews).
Run unattended jobs under a low-privilege account or in a container, and do not
approve files you do not trust.

## Windows scheduling

```text
schedule add NAME WORKFLOW (--daily HH:MM | --weekdays HH:MM | --weekly MON,THU@HH:MM
                            | --hourly N | --once YYYY-MM-DDTHH:MM)
             [--param NAME=VALUE]... [--run-whether-logged-on] [--skip-missed]
             [--timeout SEC] [--max-memory MB] [--print-only] [--force]
schedule list [--format json] | show NAME | remove NAME
```

The workflow must be approved. The task runs `trigger-designer-cli run ... --trigger
schedule --log-format json --log-file <state>\logs\NAME.jsonl`, starts in the
workflow's folder, and never overlaps itself (`IgnoreNew`, plus the CLI's own run
lock, exit 7). Times are this computer's local time; records and logs are UTC. A
missed run starts as soon as possible (`--skip-missed` turns that off). By default
the task runs only while you are logged on; `--run-whether-logged-on` uses `S4U`:
no desktop session needed, but no network credentials either (use local paths or a
service account). No password is ever stored or accepted. If the workflow file
changes after scheduling, the next run exits 6 (`TD-CLI-009`). `--print-only` shows
the exact `schtasks` command and task XML and creates nothing. Parameter paths are
made absolute when you add the schedule.

Other schedulers (not generated, one line each):

```text
cron      30 2 * * *  trigger-designer-cli run /srv/wf.tds --trigger schedule --log-format json --log-file /var/log/td/wf.jsonl
```

systemd timers and launchd work the same way; no `flock` is needed, the CLI has its own lock.

## Containers (sketch, not part of the acceptance tests)

Qt needs its offscreen runtime libraries even without a display.

```dockerfile
FROM python:3.14-slim
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libegl1 libxkbcommon0 libfontconfig1 libdbus-1-3 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir uv && uv pip install --system -e .
ENV QT_QPA_PLATFORM=offscreen PYTHONUTF8=1 TRIGGER_DESIGNER_STATE_DIR=/state TRIGGER_DESIGNER_DATA_DIR=/data
VOLUME ["/state", "/data", "/in", "/out"]
ENTRYPOINT ["trigger-designer-cli"]
CMD ["--help"]
```

`docker run --rm -v wf:/wf:ro -v in:/in:ro -v out:/out -v approvals:/state trigger-designer run /wf/wf.tds --input-dir /in --output-dir /out --log-format json`
(`--input-dir`/`--output-dir` remap Windows-authored absolute paths by file name;
mount `/state/approvals.json` read-only). Run as a non-root user with only `/out`
writable.

## Files and folders

| What | Where |
|---|---|
| CLI state (`--state-dir`, env `TRIGGER_DESIGNER_STATE_DIR`) | `%LOCALAPPDATA%\Trigger Designer\cli` (else `$XDG_STATE_HOME/trigger-designer`) |
| Approvals | `<state>/approvals.json` |
| Locks, work copies, staging | `<state>/locks`, `<state>/work/<run>` (deleted after the run), `<state>/staging` (only for output folders whose path contains `' " { }`) |
| Schedules | `<state>/schedules/NAME.{json,xml}` |
| Logs and run sidecars | `<state>/logs` |
| Run records | `--record-dir`, else `<workflow>.runs` next to the workflow (the same folder the editor's Run History dock shows) |
| Generated script | `--emit-script FILE` (the editor writes its own to `<app data>\last_run`) |

## Troubleshooting

* Exit 6: `trigger-designer-cli info wf.tds` shows `approved: no` or `no - changed since approval`.
* Exit 7: another run is active, or a dead run's lock (stale locks clear themselves when the process is gone).
* Exit 8: close the output file in Excel, check free disk space; previous files are unchanged.
* Exit 2 with `TD-IN-001`: `paths wf.tds` shows which saved path is missing; remap with `--input-dir`.
* A scheduled task that does nothing: tasks created without `--run-whether-logged-on` do not run when nobody is logged on.
* Characters the console cannot show (a cp1252 pipe and a Cyrillic path) are printed
  as `?`; piped output is UTF-8 unless you set `PYTHONIOENCODING`. Set `PYTHONUTF8=1`
  to keep them.
* More in [guide/cli.md](guide/cli.md#troubleshooting).

## For developers

* Library entry point: `trigger_designer.core.headless.runner.run_workflow_file(path, ...)`
  returns a `RunOutcome` (exit code, status, record path, errors).
* Qt-free modules live in `core/headless/`; only `qt/headless.py` imports Qt. The
  CLI never imports `trigger_designer.main`. `tests/unit/test_cli_import_discipline.py`
  guards this.
* A new node needs a row in `core/headless/op_catalog.py` (with `output_keys` if it
  holds an output path); `test_op_catalog_matches_registry.py` fails otherwise. If
  its generated code imports a module that is not in `GENERATED_IMPORTS`
  (`core/headless/code_policy.py`) the run exits 6, and the module must also be in
  the `trigger.spec` hidden imports (`test_packaging_spec.py`). See
  [cli-internals.md](dev/cli-internals.md) section 14.
* Failure injection for the end-to-end tests (`TD_TEST_HOOKS=1`, never in a frozen
  build): `TD_TEST_SLEEP_BEFORE_NODE="Title:seconds"`, `TD_TEST_FAIL_NODE=Title`,
  `TD_TEST_INJECT=Title` with `TD_TEST_INJECT_CODE`, `TD_TEST_ALLOC_MB="Title:n"`.
