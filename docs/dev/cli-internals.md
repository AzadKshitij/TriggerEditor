# CLI internals

How `trigger-designer-cli` is built, how a `run` flows through it, which tests
hold it in place, and what to touch when you add a command or a node. For the
user's view read `../guide/cli.md`; for the short reference `../CLI.md`. Plan
`../plan/08-cli-and-scheduling.md` is background only; where it differs from the
code, the code wins (the notes below say where).

Read first: `architecture.md` (layers), `run-pipeline.md` (the editor's Run, which
the CLI shares), `audit-trail-internals.md` (the record the CLI also writes) and
`security-model.md` (defence 4 is the code policy described here).

## Contents

1. Layout
2. Layers and import rules
3. Data flow of `run`
4. What is shared with the editor
5. Exit codes and errors
6. Plan, parameters and paths
7. Staging and commit
8. Lock, supervisor and the hard exit
9. Events and the stdout channel
10. Approvals and the code policy
11. verify-log
12. Scheduling
13. How to add a command
14. How to add a node (op catalogue and `GENERATED_IMPORTS`)
15. Test strategy
16. Packaging
17. What is not verified, and known gaps
18. Verified against

## 1. Layout

```
src/trigger_designer/
  cli_entry.py              PyInstaller entry of trigger-designer-cli.exe (calls cli.main)
  cli/
    __init__.py             main(argv) -> int; lazy: importing the package is cheap
    __main__.py             python -m trigger_designer.cli
    app.py                  parse, load_command(name), make_context, error -> exit code
    parser.py               argparse tree, help texts, COMMAND_MODULES, exit 64 on usage errors
    output.py               dumps/print_json/print_error (orjson only)
    commands/               run validate info approve verify_log params paths schedule
                            each: execute(args, ctx) -> int
  core/headless/            Qt-free logic, unit-testable without a window
    exit_codes.py           ExitCode, CliError, CLI_CODES (TD-CLI-001..018), combine()
    state.py                state_dir(), data_dir(), ensure()
    context.py              CliContext(state, emitter, extra)
    op_catalog.py           OPS table, V1_OPCODE_TO_OP, node_op()
    workflow_file.py        read_workflow, WorkflowDoc, static_validate, file_nodes, find_cycle
    paths.py                resolve_workflow_path, remap_into_dir, relativize
    params.py               PARAM_TARGETS rules, read_param_defs, apply_params, rewrite helpers
    approvals.py            ApprovalStore (approvals.json), approval_status
    code_policy.py          GENERATED_IMPORTS, validate_generated_code, sandbox globals
    plan.py                 RunOptions, RunPlan, build_run_plan, check_trust
    atomic.py               write_bytes_atomic, plan_staging, commit_all, discard_all
    locks.py                RunLock (per-workflow lock file, stale recovery)
    events.py               Emitter (JSON lines / text), stdout channel, loguru bridge, rotate
    supervisor.py           cancel flag, signals, watchdog (timeout, memory, grace)
    runner.py               _Run, run_workflow_file, run_with_options, deep_validate
    verify.py               verify_record, verify_folder, require_target
    schedule.py             Task Scheduler XML, schtasks wrapper, stored definitions
  qt/headless.py            the ONLY CLI module that imports Qt
```

`core/headless/params.py`, `plan.py`, `schedule.py` and friends are Qt-free but
`runner.py` reaches Qt (and Polars) only through lazy imports inside functions,
and only `qt/headless.py` imports Qt at module level.

## 2. Layers and import rules

```
cli/parser.py  (stdlib argparse; no project imports except constants + exit_codes)
cli/app.py     -> load_command(name) -> cli/commands/<name>.py
                       |
                       +-- read-only commands -> core/headless/{workflow_file, params, paths,
                       |       approvals, verify, schedule, op_catalog, atomic, state}   (no Qt, no Polars)
                       |
                       +-- run / validate --deep -> core/headless/runner.py
                                   |  (lazy)
                                   +-- qt/headless.py  -> design_window (TriggerSubWindow), offscreen Qt
                                   +-- core/ExecutionCheck/{executor, run_loop}
                                   +-- core/audit/{recorder, store, fingerprint}
```

**Import discipline.** `--help`, `--version` and every command that only reads
files must start in well under a second, so they must not import Qt (`qtpy`,
`PyQt6`), Polars, DuckDB or `trigger_designer.main`. (`main` configures loguru at
import and builds the GUI; the CLI must never import it.) The guard is
`tests/unit/test_cli_import_discipline.py`: it starts a subprocess per command,
runs `main(argv)`, and asserts `sys.modules` holds none of the banned packages
and not `trigger_designer.main`. `verify-log` bans only Qt, because the audit
store it reuses may bring Polars.

Rules that keep it true:

* `cli/__init__.py` defines `main` that imports `cli.app` inside the function.
* `cli/parser.py` imports only `core.constants` and `core.headless.exit_codes`.
* `cli/commands/*.py` import `runner`, `qt.headless`, `polars` etc. only inside
  functions (see `commands/run.py` and `validate.py`).
* New code under `core/headless/` must not import Qt or Polars at module level.
  `code_policy.sandbox_globals()` imports polars, duckdb and fastexcel inside the
  function for that reason.

`qt/headless.py` also keeps GUI side effects out of a headless process: it sets
`QT_QPA_PLATFORM` to `offscreen` (override with `TRIGGER_CLI_QPA`), replaces the
modal progress dialogs and `QMessageBox` with stubs (`suppress_ui`), subclasses
`TriggerSubWindow` so `log()` appends to a list instead of printing
(`make_window`), and funnels loguru to stderr (`quiet_loguru`).

## 3. Data flow of `run`

`cli.main` -> `app.main` parses (exit 64 on a usage error via `TdArgumentParser`),
loads `commands/run.py`, builds `CliContext(state=state_dir(--state-dir))` and
calls `execute`.

`commands/run.py: execute`

1. `RunOptions.from_args(args)`.
2. `hard = ctx.extra["hard_exit"]` (True in production; tests pass False).
3. If hard: `capture_stdout_channel()` dups fd 1 to a private stream and points fd
   1 at stderr, so anything a node `print`s cannot corrupt the JSON lines (section 9).
4. `Emitter(log_format, log_file, stream=..., quiet=...)`, then
   `run_with_options(...)`.
5. Print the text-mode `FAILED at ...` summary, close the emitter, flush stderr,
   and, if hard, `os._exit(code)`. The hard exit is deliberate: Qt and the data
   engine leave threads that can hang a normal interpreter shutdown, and a
   watchdog-forced exit must look the same.

`runner._Run._execute`

1. `--threads` sets `POLARS_MAX_THREADS`; with `capture_logs` (hard exit) loguru is
   bridged into `log` events (level from `-v`).
2. `Supervisor(...)` is created (its clock is the run's deadline).
3. `read_workflow` -> `run.started`.
4. `build_run_plan(opts, doc, state, cli_id, mode)` (section 6) -> `plan.resolved`
   and one `warning` per finding. Exceptions are `CliError` with their exit code.
5. `--dry-run`: `_dry_run` loads the work copy in a `HeadlessSession`,
   `reevaluate()`s, and for each node runs `apply_test_hooks`, `get_code()` and
   `validate_generated_code`. A rejected node is exit 6 (`TD-CLI-010`); a node that
   cannot make code is only a warning. It emits `--emit-script` if asked and
   announces exit 0. No lock, no record, no files.
6. Real run: `RunLock.acquire()` (exit 7 on a live owner), `note_staged(...)` so a
   crash can be cleaned up, signal handlers (if hard), watchdog thread.
7. `HeadlessSession.load(work_copy, expect_nodes, expect_edges)` loads the patched
   copy through the editor's `fileLoad`. A different node or edge count than the
   file declares is `TD-CLI-001` (nodes silently dropped by the loader must not
   make a "successful" run). Cycles are `TD-CLI-004`.
   `_gate_load_report`: unknown nodes -> exit 2; validation messages and
   WARNING-or-worse log lines -> warnings; under `--strict` an invalid node or
   validation message is exit 2.
8. `_run_nodes`: `session.reevaluate()`; a fresh `NodeExecutor` whose
   `execution_context` is replaced by `sandbox_globals()` and whose `code_filter`
   is `sandbox_code_filter(code, plan.io_paths)`; a `RunRecorder(RunStore("",
   data_dir()), AuditOptions(...))`; `recorder.begin(...)` with the node specs
   rewritten so the record names final paths, not staged ones
   (`_restore_final_paths`); `executor.before_node/after_node` bound to the
   recorder; `session.before_run` hooks.
9. The node loop runs in a daemon thread `td-runner` that calls
   `qt.headless.execute_nodes`, a thin adapter over `core.ExecutionCheck.run_loop.run_nodes`
   (the same loop the GUI's `WorkflowWorker` uses). The main thread only
   `time.sleep`-polls (`Supervisor.poll`) so Python can run signal handlers. The
   adapter converts loop callbacks into `node.started/finished/skipped` events,
   feeds the recorder (`node_finished`, `node_errored`) and turns a
   `policy_violation` result into `CliError(REFUSED, TD-CLI-010)`.
10. `_finish_run` decides what to commit: nothing if cancelled, refused or an
    internal error; all staged outputs if no node failed; with `--keep-going`
    only outputs whose node succeeded. `commit_all` either promotes everything or
    restores the old files (exit 8). Committed files are fingerprinted
    (`fingerprint_file`) and emitted as `output.committed`. The exit code is
    `combine(cancelled, commit_failed, node_failed)`, then raised to 6 or 3 when a
    refusal or internal error occurred. `_seal` calls `recorder.finish(...)` exactly once;
    `_write_sidecar` writes `<state>/logs/<record id>.cli.json`; `announce` emits
    `run.finished` exactly once (guarded by an `RLock` because the supervisor
    thread can announce too).
11. `cleanup` (always): stop the watchdog, discard uncommitted staged files,
    release the lock, delete the work copy.

Forced exits (timeout, memory, second Ctrl+C, grace expiry): `Supervisor.force_exit`
emits the event and calls `_Run.force_cleanup`, which records the running node as
errored (`ExecutionTimeoutError`, `MemoryError` or `KeyboardInterrupt`), seals the
record, cleans up, announces, then `os._exit(code)`.

`run_workflow_file(path, **kw)` is the library entry. It never raises `CliError`;
it returns a `RunOutcome` and by default does not install signal handlers or hard
exit (`install_signals=False`, `exit_fn=os._exit` only used by the supervisor).
`tests/e2e/test_cli_library.py` runs it twice in one process.

## 4. What is shared with the editor

The CLI deliberately contains no run logic of its own beyond supervision.

| Shared piece | Where | Why it matters |
|---|---|---|
| The loader | `TriggerSubWindow.fileLoad` | Same node classes, same migration of old files, same code generation. |
| The run loop | `core/ExecutionCheck/run_loop.run_nodes` | Same stop/continue/skip/cancel semantics as the Run button. |
| The executor | `core/ExecutionCheck/executor.NodeExecutor` | Same exec environment; the CLI swaps `execution_context` for `sandbox_globals()` and sets `code_filter`. The GUI sets no filter. |
| The recorder and store | `core/audit/recorder.RunRecorder`, `store.RunStore`, `fingerprint_file` | The record is byte-compatible; Run History in the editor shows CLI runs. The CLI adds only the `.cli.json` sidecar. |
| Error enrichment | `core.errors.enrich_error` via `HeadlessSession.enricher()` | The same `TD-*` text and hints in `run.finished.errors`. |
| The run script | `window.getPyFile` via `--emit-script` | The same file the editor writes to `last_run`. |

`tests/e2e/test_cli_parity.py::test_gui_and_cli_parity` is the contract for this
table (section 15).

## 5. Exit codes and errors

`core/headless/exit_codes.py` is the frozen contract (`ExitCode` IntEnum: 0 OK, 1
NODE_FAILED, 2 INVALID, 3 INTERNAL, 4 TIMEOUT, 5 MEMORY, 6 REFUSED, 7 BUSY, 8
COMMIT_FAILED, 9 SCHEDULER, 10 VERIFY_FAILED, 64 USAGE, 130 CANCELLED).
`combine()` picks the winner of simultaneous outcomes by `PRECEDENCE` (cancelled,
timeout, memory, commit failed, node failed, ok); REFUSED and INTERNAL are applied
in `_finish_run` and win over node failure. Never renumber a code or reuse one; a
script somewhere depends on it. `status` in `run.finished` is derived by
`_status_for` (BUSY reports `invalid`).

Everything that must stop a command raises `CliError(code, td_code, message,
hint)`. `app.main` catches it, prints through `print_error` (JSON when `--format
json`, else `error [TD-...]: msg` and an indented `hint:` on stderr) and returns
`exc.code`. `KeyboardInterrupt` returns 130; any other exception prints a
traceback and returns 3.

`CLI_CODES` holds the default text of `TD-CLI-001..018` in this module on purpose:
`--help` must not import `core/errors/catalogue.py`. Node-level failures keep their
catalogue codes (`TD-SHAPE-*`, `TD-IN-*` ...). Codes in use: 001 unreadable file or
a legacy-file warning, 002 newer schema, 003 unknown node type, 004 loop, 005
unknown/missing parameter or schedule, 006 invalid value or path, 007 setting not
allowed as a parameter, 008 not approved (also "changed since approval" for manual
runs), 009 changed after approval (scheduled runs), 010 policy refusal, 011 custom
code, 012 busy, 013 commit failed, 014 output folder or collision, 015 low disk,
016 scheduler, 017 verify mismatch, 018 no outputs (warning).

## 6. Plan, parameters and paths

`plan.build_run_plan(opts, doc, state, run_id, mode, check_files)` is pure and
Qt-free. `mode` is `run`, `dry` or `validate` (no approval gate, output folders not
required). Steps: `static_validate` (errors -> `CliError`; warnings under
`--strict` -> exit 2); `check_trust` (custom-code gate, then approval: returns the
approved hash, or None for `--allow-unapproved` on a non-scheduled run; else exit 6
with 008 or 009); `read_param_defs`; `apply_params`; `_check_inputs` (uses
`core.inputs.list_source_files`; collects the files so they become allowed paths);
`_check_outputs` (collision, folder, probe-write, free space; creates folders only
with `--create-output-dirs` and never in a dry run); `plan_staging`; write the
staged paths into the patched data; write the ASCII work copy.

`params.PARAM_TARGETS` maps `(op, setting)` to a `Rule` (kind, numeric range,
forbidden characters, pattern, "needs" conditions such as Filter `mode ==
builder`, list-valued). It is the allow-list of what a command-line value may
change, because these strings reach code generation. A new parameterisable setting
needs a rule here and a test in `test_headless_params.py`. Anything not listed is
`TD-CLI-007`.

`apply_params` works on a deep copy; the workflow on disk is never modified by a
run. Precedence for a path setting is `--param`, then `--input-dir/--output-dir`
(base name remapped with `remap_into_dir`), then the parameter default, then the
saved value. File Input uses `filePathRel` first when the relative file exists
(`_saved_input_path`), and drops `filePathRel` from the copy when the path is
overridden. `_resolve_node_path` also handles every node whose catalogue row lists
`output_keys` (this is how Workpaper Output is staged). The `input.workpaper_output`
`output_path` is itself a `PARAM_TARGETS` entry (`path_out`).

`_finish_workpapers` (end of `apply_params`) handles the settings that only the
Workpaper Output has, on the work copy: (1) every `OpInfo.list_keys` setting
(`source_files`, one path per line, split by `split_path_lines`) is remapped with
`remap_into_dir` under `--input-dir`, else resolved against the workflow folder;
(2) `if_exists` is decided *here*, before staging, because the staged name is always
fresh and the writer could not see the final name: `version` picks the first free
`name (2).xlsx` with `params.unique_path` (a copy of `core.workpaper.paths.unique_path`,
kept apart so `params` does not import Polars; `test_versioning_rule_matches_the_writer`
pins the two together), `fail` raises `CliError(INVALID, TD-OUT-010)` for an existing
file, `replace` keeps the name; (3) `publish_path` is set to the final path, so the
writer names `<name>_exceptions_full.csv` next to the final workbook and not after the
staging name (the CSV is written straight to its place, outside the atomic commit).
`workflow_file.file_nodes` also lists the `list_keys` lines as inputs, and
`paths.relativize_workflow` rewrites them. Tests: `tests/unit/test_headless_workpaper_paths.py`,
`tests/e2e/test_cli_workpaper.py`.

`paths.resolve_workflow_path` is the only resolver: no `~` or environment
expansion, URLs refused, relative against the workflow folder (never the CWD),
`/` and `\` both split on Windows paths. `relativize` returns forward-slash paths
inside the base or None. `WorkflowDoc.base_dir` is `dirname(abspath(path))`
(not `resolve()`, which would turn a `subst` or mapped drive into its target);
`relativize` compares as spelled first, then by `realpath`.

`params add/remove` and `paths --relativize --write` rewrite the user's file with
`write_workflow_with_backup`: `.bak` once (never overwritten), then an atomic
replace with `json.dumps(indent=2, ensure_ascii=False)`. The editor preserves
`workflow_metadata.parameters` on save (test `test_scene_save_keeps_the_parameters_block`).

## 7. Staging and commit

`atomic.plan_staging` assigns each output a temporary sibling
`.<stem>.tdtmp-<run8><ext>` (same directory, so the final move is a same-volume
rename). If the directory or name contains a character that would break the
f-string File Output code embeds a path in (`' " { }` newline NUL; see
`paths.is_codegen_safe_dir`) the output is staged under `<state>/staging/<run8>/`
and copied next to the final file at commit (`cross_volume`).

`commit_all` (phase A: park every existing final as `.<stem>.tdbak-<run8><ext>`;
phase B: promote staged files with `os.replace`; phase C: delete backups). Any
`OSError` rolls everything back and raises `CliError(COMMIT_FAILED, TD-CLI-013)`.
A file locked by Excel fails in phase A, before anything changed. `discard_all`
removes leftovers. `RunLock.note_staged` records `final/staged/backup` so that the
next run's `RunLock.sweep` restores a parked backup when a killed run left no
final file, and deletes leftover temporaries.

`write_bytes_atomic` (`.<name>.<pid>.tmp` then `os.replace`) is used for every file
the CLI writes: approvals, schedules, sidecars, rewritten workflows, the lock.

## 8. Lock, supervisor and the hard exit

`locks.lock_path(state, workflow)` is `<state>/locks/<sha1(normcase(abspath))[:16]>.lock`.
`RunLock.acquire` creates it with `O_CREAT|O_EXCL`; the payload holds the PID, the
process creation time (so a recycled PID is not mistaken for the owner), run id,
host and staged paths. If the file exists and `_owner_alive` (psutil) is true ->
exit 7; otherwise it sweeps the dead run's leftovers, removes the lock and retries.
`psutil` is imported inside functions.

`Supervisor`: a `threading.Event` cancel flag (checked between nodes by the run
loop), `install_signal_handlers` for `SIGINT`, `SIGBREAK` and `SIGTERM`, a daemon
watchdog thread polling every 0.25 s for the deadline, the memory ceiling (RSS via
psutil) and the cancel grace. The first signal sets the flag and emits
`run.cancelling`; a second, or the grace expiring, forces exit 130. The executor's
own default per-node limit is set to `timeout + 5` so it never fires before the
supervisor; a node's own `execution_timeout` (Workpaper Output: 600 s) never lowers it, and the
supervisor's total deadline still wins. A running node cannot be interrupted (it is inside Polars/DuckDB);
that is why the forced exit exists and why outputs are staged.

## 9. Events and the stdout channel

`events.Emitter` builds one record per event with `ts`, `level`, `event`, `run_id`
and the fields, serialises with orjson, appends to the `--log-file` (rotated at 10
MB, three backups, at open), and prints either the JSON line (json mode, on the
private stdout stream) or a text line (stderr, filtered by `--quiet`). It also
keeps every record in `emitter.events` for `RunOutcome.events` (tests read it).
Keys are only ever added. `runner._Run.emit` is the single place events are made,
and `announce` guarantees one `run.finished`.

`capture_stdout_channel` is a file-descriptor trick: `os.dup(1)` for our lines,
`os.dup2(2, 1)` and `sys.stdout = sys.stderr` so a stray `print` from node or
vendored code lands on stderr. That is why stdout in JSON mode is clean (checked by
`test_stdout_is_only_json_lines`) and why in text mode stdout is empty. The
vendored editor prints (for example `icon: <QPixmap ...>`) are routed by
`events.route_stray_stdout` into `logger.debug`, so they show only with `-vv`. `attach_loguru_bridge` replaces loguru's sinks with a `log` event sink.

## 10. Approvals and the code policy

`approvals.ApprovalStore` is `<state>/approvals.json` (`{"version": 1,
"approvals": [{sha256, name, path, approved_by, approved_at, note, reads,
writes}]}`), written atomically, keyed by the SHA-256 of the raw file bytes.
`changed_since_approval(path, sha)` finds an entry for the same path with another
hash, which is what turns exit 6 text into "changed after it was approved". The
store is unsigned by design (documented trade-off). A scheduled run
(`--trigger schedule`) ignores `--allow-unapproved`.

`code_policy.validate_generated_code(code, io_paths=)` is a pure `ast` check:

* only node types in `ALLOWED_NODE_TYPES` (no `class`, `with`, `async`, `global`,
  `import` of anything off the table, no decorators);
* imports only from `GENERATED_IMPORTS` (module -> allowed `from` names, or None
  for a bare `import m`) and `GENERATED_IMPORT_PREFIXES` (`core.shaping.<x>` may
  import `run_node` and `write_node`, `<x>` matching `[a-z_]+`);
* forbidden names and attributes (`FORBIDDEN_NAMES`, `FORBIDDEN_ATTRS`), any
  dunder, `os.*` other than a small `os.path` set;
* SQL passed to `execute/sql/query/executemany` must be a string literal that is a
  single `SELECT`/`WITH` with no forbidden tokens (`read_*`, `copy`, `attach`,
  `pragma`, `http*`, `write_*` ...); `duckdb.connect` only with `':memory:'`;
* every call whose attribute starts with `scan_ read_ sink_ write_` needs a literal
  path that is in `io_paths`; values under the keys in `PATH_KEYS`
  (`filePath`, `output_path`, `db_path`) in dict literals and in JSON-looking
  strings must also be declared paths. Declared paths are the inputs the plan found
  (including each expanded file of a glob) and the staged output paths.

`sandbox_code_filter` runs the validator and then strips `import os` (the exec
globals provide a restricted `os` namespace). `sandbox_globals()` supplies `pl`,
`duckdb`, `fastexcel`, `DataCleansing`, `NullStrategy`,
`normalize_to_supported_dtypes`, `datetime`, `os` (the safe subset) and the
restricted `__builtins__` from `make_safe_builtins()`. Do not widen
`SAFE_BUILTIN_NAMES` casually. The table is exercised by
`tests/unit/test_headless_code_policy.py` (an attack table, a benign table, a
"future node imports" table, a tampered-helper table).

It is defence in depth against accidents and a tampered setting, not an OS
sandbox. See `security-model.md`.

## 11. verify-log

`verify.py` is Qt-free and reuses `core.audit.store` (`verify_record_file`,
`verify_store` for a folder's hash chain, `RunStore.load_dict`). Checks per record:
V1/V2 record parses, schema valid, own hash matches; V3 status agrees with the
node statuses; V4 workflow hash equals `workflow_sha256` (needs `--workflow`); V5
each recorded output exists with the same size and SHA-256 (errors); V6 inputs
changed or missing (warnings). `require_target` picks the record: an explicit
path, else the newest in the store folder of `--workflow`
(`audit.store.resolve_store_dir`), else the newest under `<data>/runs`. The plan
envisaged a `.json.sha256` sidecar; the record's own chain replaced it.

## 12. Scheduling

`schedule.py` keeps every operating-system call behind `_run_schtasks(argv)`, so
tests replace one function (`fake` fixture in `test_headless_schedule.py`).
`build_command(spec)` is the exact command line a task runs: the frozen exe or
`python -m trigger_designer.cli`, then `--state-dir`, `run WORKFLOW`, each
`--param`, `--trigger schedule --log-format json --log-file <state>/logs/NAME.jsonl
--timeout N [--max-memory M]`. `build_task_xml` makes the Task Scheduler 1.2 XML
(UTF-16 with BOM when saved), with `MultipleInstancesPolicy=IgnoreNew`,
`StartWhenAvailable` (off for `--skip-missed`), a start time boundary of today's
date, `ExecutionTimeLimit = timeout + 300 s`, `LeastPrivilege`, and logon type
`InteractiveToken` (default) or `S4U` (`--run-whether-logged-on`). No password is
accepted or stored. The workflow must be approved at `add` time; `--param` values
are validated with `apply_params` and path values made absolute (a task starts in
System32). The task is created with `schtasks /Create /TN TriggerDesigner\NAME /XML
<file> /F`; a failure deletes the stored files and exits 9. `list` joins the stored
definitions with `schtasks /Query /FO CSV /V` parsed by column position (headers
are localized, times are locale-formatted: both kept raw). Names must match
`^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$`. Non-Windows exits 9 with a message pointing at
cron, systemd or launchd. Nothing is generated for cron or containers; those are
text in `../CLI.md`.

## 13. How to add a command

1. **Parser** (`cli/parser.py`): add a sub-parser with `_sub(...)` (description,
   epilog containing the word `Example`; a test requires it), options, and a line in
   `COMMAND_MODULES`. Use `_add_param`, `_add_dirs`, `_add_format` for the shared
   options. `allow_abbrev=False` is set; keep it.
2. **Dispatch** (`cli/app.py: load_command`): add an `elif` branch with a plain
   `from trigger_designer.cli.commands import x as module`. The spelled-out import
   is intentional: PyInstaller finds it statically, so no hidden-import list is
   needed (`test_every_command_module_is_loadable_by_name` checks the mapping).
3. **Module** (`cli/commands/<name>.py`): `def execute(args, ctx) -> int`. Return an
   `ExitCode` value; raise `CliError(code, "TD-CLI-0xx", message, hint)` for
   failures (add a default text to `CLI_CODES` if you add a code). Print results
   with `print`/`print_json`; keep stdout for the result and put diagnostics on
   stderr. Do not import Qt, Polars or `trigger_designer.main` at module level.
4. **Discipline test**: add a row to `CASES` in `test_cli_import_discipline.py`.
5. **Tests**: unit-test the logic in `core/headless/` through `call_main([...])`
   (in-process, no subprocess, `hard_exit=False`); add e2e only if it needs a real
   run (`run_cli`).
6. **Docs**: `../CLI.md` (reference), `../guide/cli.md` (user), this page if the
   architecture changes. Keep the exit-code contract.

## 14. How to add a node

A new node needs three things to run headless. All three are enforced by tests.

1. **Op catalogue row** (`core/headless/op_catalog.py`): `_row("family.name",
   "Title")`. The op id is `<family>.<enum member name lower-cased>`. If the node's
   content holds an output path, give `output_keys=("key",)` so the plan stages it
   and the policy lets it write there. `custom_code=True` marks a node that embeds
   user-written code (none today). Test:
   `tests/unit/test_op_catalog_matches_registry.py` fails when a registered node has
   no row, when a row has no node and is not `planned=True`, when a title differs,
   or when any row is `custom_code`.
2. **`GENERATED_IMPORTS`** (`core/headless/code_policy.py`): whatever the node's
   `get_code()` imports. Modules under `core/shaping/` need nothing (the prefix rule
   admits `run_node`/`write_node`). A new audit, profile or helper module needs one
   row: `"trigger_designer.core.x.y": {"name1", "name2"}`. An import not on the table
   makes `trigger-designer-cli run` exit 6 for that node while the editor works
   fine. Tests: add the new import line to the `FUTURE` (and, if useful, `TAMPERED`)
   list in `test_headless_code_policy.py`; `test_corpus_passes_policy` loads every
   checked-in workflow and validates its code; if the corpus does not contain your
   node, add a small workflow under `tests/e2e/workflows/`.
3. **`trigger.spec`**: `GENERATED_IMPORTS` modules are invisible to PyInstaller
   (generated code is exec'd). `tests/unit/test_packaging_spec.py::
   test_every_module_generated_code_imports_is_in_the_spec` fails when a module in
   the table is not covered by `core_hiddenimports` (the spec lists packages under
   `core/` such as `audit`, `shaping`, `excel`, `workpaper`, `headless`, `utils`, and a
   few single modules). Add the package or file to `_CORE_PACKAGES` /
   `_CORE_MODULES`. A third-party import must be listed by name in the spec.

If the node reads or writes through a new File-Input-like setting that should be a
parameter, add a `PARAM_TARGETS` rule (section 6). If it writes a file, check the
node's output path appears in the approval review: `approve`, `info` and
`paths` list files through `workflow_file.file_nodes`, which reads the op catalogue (`input_keys`, `output_keys`,
and `list_keys` for multi-line path settings) (section 17).

Also add the node to an e2e parity or golden case if it produces a file (add a
`WorkflowCase` to `tests/support/corpus.FILE_OUTPUT_CASES` with a frozen golden).

## 15. Test strategy

| Layer | Files | What it proves |
|---|---|---|
| Unit, pure | `tests/unit/test_headless_{workflow_file,paths,params,approvals,atomic,locks,events,plan,verify,schedule,code_policy}.py`, `test_cli_parser.py` | Every `core/headless` module on its own with `tmp_path`; exit codes; XML; policy attack tables. No Qt. |
| Unit, discipline | `test_cli_import_discipline.py`, `test_op_catalog_matches_registry.py`, `test_packaging_spec.py` | Light commands stay light; catalogue tracks the registry; frozen build covers generated imports. |
| Unit, Qt | `test_headless_session.py` | `HeadlessSession` hooks, test hooks inert without the switch. |
| E2E, workpaper | `tests/e2e/test_cli_workpaper.py` | A Workpaper Output run as a subprocess: `--output-dir`, rerun with New version (`name (2).xlsx`), the full-exceptions CSV beside the final file, `--param` and `paths --relativize` for `output_path`, no staging names on the Workflow sheet, `--input-dir` shown. |
| E2E, process | `tests/e2e/test_cli_run.py` | Real `python -m trigger_designer.cli` subprocess against checked-in workflows: goldens, JSON stdout, text stderr, approval flow, dry run, injected code refused, parameters, remapping, relative paths, unicode paths, cp1252 workflow, strict, keep-going, collisions, concurrent run (exit 7), killed run leaves no partial output, Workpaper Output staging. |
| E2E, parity | `tests/e2e/test_cli_parity.py` | The same workflow through the editor (`TriggerSubWindow` + `WorkflowWorker`) and the CLI: output files byte-identical (frames compared sorted for unordered cases), same node statuses, ops, row counts, input hashes, output hashes. Also `test_corpus_passes_policy`. |
| E2E, signals | `tests/e2e/test_cli_signals.py` | Ctrl+Break graceful and forced (130), second signal, timeout (4), memory (5). Uses `CREATE_NEW_PROCESS_GROUP` on Windows. |
| E2E, library | `tests/e2e/test_cli_library.py` | `run_workflow_file` twice in one process; offscreen platform; `trigger_designer.main` not imported. |

Support code: `tests/support/cli.py` (`cli_env` isolates `TRIGGER_DESIGNER_DATA_DIR` and
`TRIGGER_DESIGNER_STATE_DIR` under `tmp_path` and removes `QT_QPA_PLATFORM` so the CLI must set
it itself; `run_cli`, `spawn_cli`, `events`, `call_main` for in-process calls with
`hard_exit=False`, `synthetic_workflow`, `write_workflow`), `tests/support/corpus.py`
(`FILE_OUTPUT_CASES`) and `tests/support/workflows.py` (`materialize` copies a checked-in
workflow into a temp dir and rewrites its paths so a run never writes near the repo).

**Failure injection (`TD_TEST_HOOKS=1`).** Real failures are hard to produce on cue,
so `qt/headless.apply_test_hooks(node)` is called when a node starts and in a dry
run. It is inert unless `TD_TEST_HOOKS=1` and the process is not frozen
(`sys.frozen`), so a shipped exe cannot be driven by environment variables:

| Variable | Effect |
|---|---|
| `TD_TEST_SLEEP_BEFORE_NODE="Title:seconds"` | Sleep before that node (tests for exit 7, cancel, timeout). |
| `TD_TEST_FAIL_NODE=Title` | The node's code becomes `raise ValueError('boom')` (exit 1, `--keep-going`). |
| `TD_TEST_INJECT=Title` with `TD_TEST_INJECT_CODE` | Replace the node's code, to prove the policy refuses it (exit 6). |
| `TD_TEST_ALLOC_MB="Title:n"` | Allocate and keep `n` MB before the node (exit 5). |

Commands to run the CLI tests:

```powershell
.venv\Scripts\python.exe -m pytest tests\unit -k "headless or cli or op_catalog or packaging" -q
.venv\Scripts\python.exe -m pytest tests\e2e\test_cli_run.py tests\e2e\test_cli_parity.py tests\e2e\test_cli_signals.py tests\e2e\test_cli_library.py -q
```

Regenerating a golden: see `testing.md` (`TRIGGER_UPDATE_E2E_GOLDENS=1`). Do not
loosen the parity test to make a CLI difference pass; the difference is the bug.

## 16. Packaging

* Entry points: `pyproject.toml` `[project.scripts]` defines `trigger-designer`
  (`trigger_designer.main:main`) and `trigger-designer-cli` (`trigger_designer.cli:main`).
  `python -m trigger_designer.cli` uses `cli/__main__.py`.
* `trigger.spec` builds the CLI as a second `Analysis` of `src/trigger_designer/cli_entry.py`
  (console exe `trigger-designer-cli`, hidden import `trigger_designer.qt.headless`),
  merged with the editor via `MERGE(...)` so both share DLLs and data, and `COLLECT`s
  both into `dist\TriggerEditor`. The portable (single-file) build is GUI only.
* `core_hiddenimports` (between the `core hidden imports begin/end` markers) lists the
  Qt-free `core` packages for PyInstaller because they are imported by name from
  exec'd code and from plan modules, and `trigger_designer.cli`.
* `cli/app.py: load_command` imports each command module explicitly for the same reason.
* `scripts\build.bat` ends with a smoke test: the exe must exist, `--version`
  must exit 0 and `validate "savedfiles\0. All Node- Test.tds" --deep --no-files` must exit 0.
* `savedfiles\TriggerDesigner_Setup.iss`: the CLI exe is installed beside the editor;
  the unchecked task `addtopath` appends `{app}` to the user (or machine, depending on the
  install mode) `Path`, guarded by `NeedsAddPath`.
* Frozen detection: `sys.frozen` selects `sys.executable` as the scheduled command
  (`schedule.executable`) and disables the test hooks.

## 17. What is not verified, and known gaps

As the CLI author reported, and as checked while writing the docs:

**Not verified (no test or measurement exists):**

* A real Windows Task Scheduler cycle (`schtasks /Create`, run, `/Query`, `/Delete`)
  has not been recorded. The task XML, argv and CSV parsing are tested against a fake
  `_run_schtasks`; `--print-only` output was read by eye; `schedule list` against the
  live scheduler was run and returned nothing because no task existed.
* The installer was not compiled and the `addtopath` task not exercised.
* The packaged `trigger-designer-cli.exe` was not run on a machine without Python (the
  `dist\TriggerEditor` folder present during the documentation work predates the CLI and has no
  CLI exe). The `build.bat` smoke test covers only `--version` and a deep validate.
* The container recipe in `../CLI.md` was not built; the cron line was not run.
* Exit 9 on a non-Windows system and signal behaviour on Linux are untested.
* Exit 130 and the memory and timeout exits are covered by `test_cli_signals.py` on Windows only.

**Fixed after the docs were written** (tests in `tests/e2e/test_cli_defects.py`,
`tests/unit/test_headless_workflow_file.py`, `tests/unit/test_headless_schedule.py`,
`tests/ui/test_no_console_prints.py`): `approve` with a `NUL` stdin now exits 64;
`cli.app.configure_streams` makes piped output UTF-8 (or `errors="replace"` when
`PYTHONIOENCODING` chose an encoding); `file_nodes` is driven by `OpInfo.input_keys` /
`output_keys` so `approve`, `info` and `paths` list Workpaper Output; `base_dir` uses
`abspath` and `relativize` falls back to real paths (subst and mapped drives); the
vendored editor's `print`s go to the debug log (`events.route_stray_stdout`) and
`quiet_loguru(verbosity)` adds no stderr sink (and no ANSI) unless `-v`/`-vv`;
the console-prints guard exempts `cli/commands` and `cli/output.py`;
`schedule list` shows `daily at 02:30`, not a dict.

**Fixed later** (`0593b8e`, tests above): a Workpaper Output now follows `--output-dir`, `--param`, `--input-dir` (`source_files`) and `paths --relativize`, and obeys `if_exists` and the CSV sidecar rule under the CLI (section 6, `_finish_workpapers`). A Workpaper Output run from the CLI used to have no Run log sheet because the headless runner installed no run-record provider. **Fixed:** `_Run._install_record_provider` (called right after `recorder.begin`) installs `core.audit.recorder.set_run_record_provider` with `recorder.snapshot`, as `qt/helpers/audit_bridge.RunSession.start` does in the editor; `_clear_record_provider` removes it when the node loop ends and again in `cleanup()` (failure, cancel, timeout and forced-exit paths). With `--no-record` it is not installed: the recorder keeps nothing, so the sheet is omitted with `NO_RECORD_REASON`. The imports are inside the methods, so read-only commands still import nothing extra. Tests: `tests/unit/test_headless_record_provider.py`, `tests/e2e/test_cli_workpaper.py`.

**Open:**

1. `validate` without `--deep` reports a missing input as a warning and exits 0, while
   `--deep` (and `run`) report it as an error and exit 2. The plan (`08`) only says a
   run with a missing input exits 2 and that static `validate` prints findings; it does
   not say which level the quick check uses. Options: keep (the quick check is for a
   file that is checked on another machine than the one that runs it), make it an error
   unless `--no-files`, or make it a warning that `--strict` promotes (already true).
   Left as documented.
2. `route_stray_stdout` also captures a deliberate `print` of generated node code; with
   `-vv` it appears as `stdout: ...` debug lines, not on stdout.

## 18. Verified against

Written on 2026-10-30 against branch `feature` at `774f5f8` (CLI commits
`efe94bf`, `27d3c5c`, `10bb241`, `b74095c`, `2564af4`, `306fe79`, `f6bdef5`, `891120a`,
`75c825b`). Commands were run with `.venv\Scripts\python.exe -m trigger_designer.cli`
against copies of `savedfiles/` and `data/` in a scratch folder, and
`tests/unit -k "headless or cli or op_catalog or packaging"` (288 passed, 2 skipped) and
`tests/e2e/test_cli_signals.py` (5 passed) were run. Pages name modules and
functions rather than line numbers; if a page and the code disagree, fix the page in
the same change that fixed the code.

Added 2026-10-31 (as of `511db02`): the Workpaper Output handling in section 6. `tests/unit/test_headless_workpaper_paths.py`, `tests/e2e/test_cli_workpaper.py`, `tests/unit/test_file_output.py` and `tests/ui/test_file_output_dock.py` were run: 54 passed, 1 failed in total (`test_workflow_sheet_never_shows_staging_names_and_follows_input_dir` compares a forward-slash path with the Workflow sheet text, which holds the Windows path with backslashes; see the CHANGELOG known issues).
