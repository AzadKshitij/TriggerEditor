# 08 - Headless execution (CLI) and local scheduling

Status: implementation plan. Audience: a cheaper model that executes it without making design
decisions. Everything below was decided; each decision has a one-line reason. Evidence was
produced on 2026-10-21 against `main` @ `71b4041` (dirty tree: `main.py`, `pyproject.toml`,
`uv.lock`, `check_output.py` already modified by others - **re-read a file right before you edit it**).
Read `docs/plan/00-codebase-brief.md` first (called "the brief"; section numbers refer to it).
Experiment scripts used for the evidence are not in the repo; the numbers are quoted in section 2.

Reading order for the implementer: 1 -> 3 (reference) -> 4 (do the steps in order) -> 6, 7, 8.
**Cross-plan ownership (after review):** plan 09 (`docs/plan/09-foundations.md`) owns F-B (shared `ExecutionResult` fields, executor hook stubs incl.
`code_filter`/`policy_violation`, `before_run` hook list), F-C (shared Qt-free run loop with continue-on-error), F-D (`request_run_cancel()`), F-F
(atomic UTF-8 `saveToFile`, `workflow_dir`, metadata carry-forward) and F-G (console-script/`pyproject.toml`/`trigger.spec` base pass). Plan 02 owns the
recorder API (`RunRecorder`, `AuditOptions`, `audit_bridge.node_specs_from_window`, executor `before_node/after_node`). This plan only *uses* those.

## Table of contents

1. Goal and non-goals
2. Current state and evidence (including experiments)
3. Final architecture (decisions, modules, grammar, exit codes, parameters, paths, schedule, trust)
4. Ordered implementation steps (12 commits, S1-S12)
5. Edge cases
6. Test plan
7. Acceptance checklist
8. Verification commands
9. Pitfalls
10. Interfaces (consumed / provided)
Appendix A: runbook and Dockerfile. Appendix B: help-text drafts.

---

## 1. Goal and non-goals

**Goal.** `trigger-designer-cli run workflow.tds` executes a saved workflow with no window, no
human, deterministic exit codes, structured logs, the same run record the GUI writes, outputs that
are never half-written, a safety gate for `.tds` files written by other people, and a Windows
Task Scheduler wrapper (`schedule add`). The same CLI, unchanged, is what a container or a CI job
runs ("server ready"). The GUI **Cancel** button is delivered by plan 09 F-D (not this plan) because cancellation is one mechanism with two front ends; this plan owns only the CLI front end.

**In scope**
1. CLI: `run`, `validate`, `info`, `approve`, `verify-log`, `params`, `paths`, `schedule`.
2. Parameters (`--param`, `workflow_metadata.parameters`), relative-path resolution, `--input-dir/--output-dir`.
3. Exit codes, JSONL logging, `--dry-run`, `--timeout`, `--max-memory`, Ctrl+C (the GUI Cancel button is plan 09 F-D).
4. Run records identical to the GUI's (plan 02) and `NodeError` summaries (plan 03).
5. Local scheduling with `schtasks` (Windows only), overlap lock, missed-run behaviour.
6. Trust model: generated-code AST policy, approvals, custom-code gate.
7. Packaging: `trigger-designer-cli.exe` beside the GUI exe; installer edits.
8. Atomic outputs; no more `check_output.py` in the working directory.

**Non-goals (decided, do not build)**
* No web UI, no HTTP API, no multi-user server, no remote database/object-store connectors, no auth.
* No cron / launchd / systemd generators (documented in Appendix A as "write your own line calling the CLI").
* No Qt-free reimplementation of node code generation (section 3.1 explains why).
* No OS-level sandbox. The code policy is defence in depth against *accidental or casual* abuse;
  the real boundary for hostile files is "do not approve them" plus a low-privilege account/container.
* No GUI "Schedule..." dialog (decided: out of scope - a dialog needs a trigger editor, a task
  status poller and credentials UX; the CLI prints the exact command so a user can paste it. Revisit
  only after the CLI is in real use).
* No signed approvals, no encrypted state, no stored credentials/passwords (section 3.11).
* No change to node semantics, to `exec()` of generated code for the **GUI** Run, or to File Input/Output UI.

---

## 2. Current state and evidence

### 2.1 Verified facts (file:line are in the current tree)

| # | Fact | Evidence |
|---|---|---|
| F1 | `main.py` imports Qt and configures loguru + tees stdout/stderr at import time; only an optional `.tds` path is accepted. `[project.scripts] trigger-designer = "trigger_designer.main:main"` is the GUI. | `src/trigger_designer/main.py:1-30,149`, `pyproject.toml:[project.scripts]` |
| F2 | Importing the **node registry** imports Qt: `node_configuration.py` ends with `from trigger_designer.qt.widgets.nodes import *`. Measured: after `import trigger_designer.core.node_configuration`, `PyQt6` is in `sys.modules`. | `core/node_configuration.py:309-310` |
| F3 | Node "content" classes are `QDMNodeIconContentWidget` (QWidget) subclasses; `get_code()` reads `self.incoming_variable`, `self.incom_data` that only live `processInputs()` sets. 23 `get_code` methods, 1154 lines in total; 9 of them read live schema (`frame_schema`, `incom_data`). | `qt/widgets/nodes/**` (measured with `ast`) |
| F4 | `TriggerSubWindow.fileLoad` -> `_load_with_dialog` runs `doEvalOutputs()` = a full live evaluation, so after load every node has `incoming_variable` etc. **This solves "headless has no live state"**: load the file through the real loader, then `topologicalSort(getNodeConnections())`, then `execute_node` per node. | `qt/design_window.py:419-459,327-356,736-756` |
| F5 | Run (GUI) = `executeWorkflow` -> `WorkflowWorker.run()` loop -> `NodeExecutor.execute_node`; `request_cancel()` and `cancel_execution()` have no callers; `execute_node` even does `_cancel_event.clear()` at its start. | `helpers/workflow_execution_mixin.py:47-89`, `helpers/workflow_worker.py:39-68`, `core/ExecutionCheck/executor.py:303,457` |
| F6 | `exec(code, execution_globals, local_vars)` runs on one pooled daemon thread with the **full builtins**; the timeout abandons the thread; the memory check is a post-hoc RSS delta; `SecurityConfig` has only `max_execution_time=30.0` and `max_memory_mb=512.0`. | `executor.py:91-95,243-286,329-338` |
| F7 | **Executor bug**: `node_name` is assigned *after* `node.get_code()`; if `get_code()` raises, the `except` calls `self._report_missing_dependency(node_name, e)` -> `UnboundLocalError` escapes `execute_node`. Reproduced with a code filter that raised. | `executor.py:310-311,379` |
| F8 | `getPyFile` writes `check_output.py` into the CWD after every Run. | `design_window.py:698-706`, `workflow_execution_mixin.py:133` |
| F9 | `TriggerScene.serialize` writes only `schema_version/app_version/saved_at` into `workflow_metadata`, so any extra key (our `parameters`, plan 02's `workflow_uuid`) is dropped on the next GUI save unless carried forward - **fixed by plan 09 F-F** (this plan only tests that `parameters` survives). | `qt/performance_scene.py:166-173,175-180` |
| F10 | `.tds` is written with `open(filename, "w")` (locale encoding, **not UTF-8**) of orjson's UTF-8 text, and read with `open(filename, "r")`. Non-ASCII content is therefore locale-encoded; a CLI running in another locale/container must not assume UTF-8 (plan 09 F-F makes *new* saves atomic UTF-8; old files stay locale-encoded, so the reader fallback stays). | vendored `nodeeditor/node_scene.py:629-634,649-651` |
| F11 | `TriggerSubWindow.log()` falls back to `print("[LEVEL] msg")` when no Logging dock exists (stdout noise); vendored code also prints (`icon: ...`). | `design_window.py:565-572` |
| F12 | `WORKFLOW_SCHEMA_VERSION = 2`, `VERSION = "0.1.0"` (Qt-free file). Edge dict = `{id, edge_type, start, end, label, input_index}` where `start/end` are **socket** ids; node dict has `inputs[]`/`outputs[]` sockets with `id`. | `core/constants.py:7-8`, a real `.tds` |
| F13 | PyInstaller: one spec builds `TriggerEditor.exe` (`console=False`) into `dist/TriggerEditor` (441 MB; `_polars_runtime_32` 168 MB, `pyarrow` 81 MB, `PyQt6` 60 MB). `qoffscreen.dll` is already in `dist/TriggerEditor/_internal/PyQt6/Qt6/plugins/platforms/`. Inno script copies only `TriggerEditor.exe` + `_internal\*`. | `trigger.spec`, `savedfiles/TriggerDesigner_Setup.iss`, `dist/` listing |
| F14 | `click` is declared but unused. Import cost measured: `click` 337 ms cumulative vs `argparse` 28 ms. | `python -X importtime` |

### 2.2 Experiments run for this plan (results are facts, reuse them in tests)

| Id | Experiment | Result |
|---|---|---|
| X1 | Import timing (cold, this machine): polars 0.50-0.75 s; `PyQt6.QtCore/Gui/Widgets` 0.03-0.15 s; duckdb+pyarrow 0.28-0.40 s; `trigger_designer.qt.design_window` 0.27-0.51 s; psutil 83 ms; stdlib CLI set (argparse, json, hashlib, subprocess, signal, threading) 57 ms. | PyQt6 is **not** the cost; polars and duckdb are. |
| X2 | Offscreen headless run (`QT_QPA_PLATFORM=offscreen`, `QApplication([])`, `TriggerSubWindow()`, stubbed progress dialog/`QMessageBox`, `fileLoad(tds)`, `topologicalSort`, `NodeExecutor().execute_node` per node) on `tests/e2e/workflows/formula-category.tds` with remapped paths: app+imports 0.9 s, load 0.61 s, run 1.25 s (Formula dominates: first DuckDB use), `out.csv` produced, **no `check_output.py` in the CWD** (we never call `getPyFile`), matplotlib not imported. | Option (a) works end to end. |
| X3 | **Injection proof.** Same workflow, File Input `content.delimiter = ';\', schema=(open(r"<tmp>\PWNED.txt","w").write("x"),None)[1], x=\''`. Headless run: `PWNED.txt` was created in `<tmp>` (the node then failed with `scan_csv() got an unexpected keyword argument 'x'`). Cause: `file_input.py:795` interpolates `separator='{self.delimiter}'` unescaped; `file_input.py:760` does the same with `selected_sheet`; `filter.py:950,952` do `f"'{self.value}'"`; `dynamic_row_builder.py:408` interpolates `field_name`. | A hostile `.tds` is arbitrary code execution today. Mitigation is mandatory, not optional. (Plan 01's `source_spec()`+`repr` removes the File Input sites once it lands; the Filter and Rows sites remain, and the policy does not depend on any of them being fixed.) |
| X4 | Draft AST policy (section 3.11) run over **every** workflow in `savedfiles/`, `tests/e2e/workflows/`, `data/`: 33 workflows, **128 generated snippets, 0 refused**. | No false positives on the corpus. |
| X5 | Same policy + restricted builtins + `import` statements stripped + SafeOs, executing the 9 `FILE_OUTPUT_CASES`: outputs **byte-identical** (sha256) to unsandboxed runs for select, formula, unique, filter, sort, transpose, split, running_total; `join` differs only in row order (Polars hash join; the corpus already lists it in `unordered_goldens`). | The sandbox does not change results. |
| X6 | Restricted `__builtins__` **without `__import__`** broke DuckDB (`Formula '__import__'`: DuckDB's C++ `.pl()` imports Polars through the calling frame's builtins). Keeping `__import__` in the builtins dict fixes it. The validator forbids the *name* `__import__` and strips all `import` statements, so generated code cannot reach it. | Keep `__import__` in `SAFE_BUILTINS`. |
| X7 | 32 malicious snippets + 7 benign snippets through the draft validator: **all 32 refused, all 7 pass** (table in section 6.3). | Table is verified, not aspirational. |
| X8 | Cancellation: child process runs `LazyFrame.sort(...).sink_csv()` on a worker thread (Rust, GIL released) while the main thread polls `time.sleep(0.2)` with `signal.signal(SIGINT/SIGBREAK)`. Parent sends `CTRL_BREAK_EVENT` (`CREATE_NEW_PROCESS_GROUP`): handler observed after 0.33 s, `os._exit(130)` ended the process mid-sink, return code 130, no final file. | The poll-loop design works with Polars running; the only real kill is process exit. |
| X9 | stdout hygiene: `out = os.fdopen(os.dup(1), "wb", 0); os.dup2(2, 1); sys.stdout = sys.stderr` - stdout then carries only our JSON lines (UTF-8 intact, `\n` endings) while `print()` and `redirect_stdout` captures go elsewhere. | Use exactly this. |
| X10 | `schtasks /Query /FO CSV /V` on this machine (en-IN): localized **header**, stable column order (0 HostName, 1 TaskName `\name`, 2 Next Run Time, 3 Status, 4 Logon Mode, 5 Last Run Time, 6 Last Result, 8 Task To Run, 14 Run As User), dates as `22-10-2026 13:00:00` (locale-dependent), one row per trigger. `schtasks /Query /TN x /XML` shows the real schema (`Settings/StartWhenAvailable`, `MultipleInstancesPolicy IgnoreNew`, `CalendarTrigger/ScheduleByDay/DaysInterval`, `Actions/Exec/Command`), UTF-16. **No task was created during planning** (that would change system configuration without consent); the create/run/delete path is therefore a manual acceptance check (section 7). | Parse CSV by position, never by header; do not parse dates. |
| X11 | A 3-node workflow cold wall time through the offscreen path is about 3 s (X2 sum plus interpreter start-up). | Acceptable for batch use. |

---

## 3. Final architecture

### 3.1 Decision: (a) Qt-offscreen reuse of the real node classes; Qt-free front end

**Decision: (a).** `run`, `validate --deep` and `--dry-run` create a `QApplication` with
`QT_QPA_PLATFORM=offscreen`, load the workflow through the real `TriggerSubWindow` loader and execute
the real nodes' `get_code()` through the real `NodeExecutor`. Everything else (`info`, static
`validate`, `approve`, `verify-log`, `params`, `paths`, `schedule`, `--version`, `--help`) is
**Qt-free and polars-free** and starts in about 60 ms.

Reasons (evidence):
1. **Parity by construction.** The GUI Run and the CLI run call the same `get_code()` on the same
   live-evaluated nodes (F4, X2, X5). A Qt-free runner needs a second code-generator per node:
   23 methods / 1154 lines (F3), nine of which read live schema, plus the socket-wiring logic that
   produces `incoming_variable`. Every future node (plans 04, 05, 07 add 7+) would need two
   implementations that can silently drift - this is exactly the "GUI says OK, nightly job says
   something else" failure an audit tool cannot have.
2. **Qt is not the cost** (X1): PyQt6 import 0.03-0.15 s versus polars 0.5-0.75 s and duckdb 0.3-0.4 s.
3. **The registry is Qt-coupled anyway** (F2); a Qt-free runner could not even resolve op ids
   without a hand-maintained duplicate of the registry.
4. **Offscreen is already bundled** (F13) and is what the test-suite uses (`tests/conftest.py`).

Costs we accept: ~0.3 s extra start-up; a `QApplication` exists; a few stdout prints from vendored code
(handled by X9). To keep Qt out of the common read-only commands, `core/headless/op_catalog.py` is a
small hand-maintained table of op ids (22 enum members today, plus every node planned by plans 01-07, see S1) with a unit test that fails when it
drifts from the real registry (section 6.1 `test_op_catalog_matches_registry`).

**Fallback (decided in advance).** If a future Qt/nodeeditor upgrade breaks offscreen loading, the fallback is
*not* option (b); it is `QT_QPA_PLATFORM=minimal` (`qminimal.dll`, also shipped) selected by env
`TRIGGER_CLI_QPA=minimal`. Only if both fail do we revisit (b) - and that is a new plan.

### 3.2 Module layout and public signatures

Qt-free means: imports only stdlib, orjson (lazily), sqlglot (not used here), and never `polars`,
`PyQt6`, `qtpy`, `trigger_designer.qt.*`, `trigger_designer.main`. All new files are new; edited files
are listed in section 4.

```text
src/trigger_designer/
  cli/                                   (Qt-free, polars-free at import time)
    __init__.py        def main(argv: list[str] | None = None) -> int      # lazy: imports .app
    __main__.py        sys.exit(main())                                    # python -m trigger_designer.cli
    app.py             def main(argv) -> int          # build parser, dispatch, map exceptions -> ExitCode
    parser.py          def build_parser() -> argparse.ArgumentParser       # all help text (Appendix B)
    commands/{run,validate,info,approve,verify_log,params,paths,schedule}.py
                       each: def add_parser(sub) -> None ; def execute(args, ctx) -> int
  cli_entry.py         PyInstaller entry: sys.exit(main())
  core/headless/                         (Qt-free)
    exit_codes.py      class ExitCode(IntEnum) ; class CliError(Exception){code:ExitCode, td_code:str, message:str, hint:str}
    state.py           def state_dir(override: str | None = None) -> Path ; def data_dir() -> Path ; def ensure(sub: str) -> Path
    op_catalog.py      @dataclass(frozen=True) class OpInfo{op, title, family, custom_code: bool=False, output_keys: tuple[str, ...]=(), planned: bool=False}   # output_keys: content keys holding output paths (staged by 3.8; dotted for nested)
                       OPS: dict[str, OpInfo] ; def known_op(op: str) -> OpInfo | None
    workflow_file.py   @dataclass(frozen=True) class WorkflowDoc{path:str, raw:bytes, data:dict, sha256:str, encoding:str, schema_version:int}
                       def read_workflow(path: str) -> WorkflowDoc                       # raises CliError(INVALID)
                       def static_validate(doc: WorkflowDoc) -> list[Finding]            # graph, ops, schema
                       def file_nodes(doc) -> list[FileNode]                             # File Input/Output nodes (id, kind, raw path)
                       @dataclass(frozen=True) class Finding{level:str, td_code:str, message:str, node_id:int|None}
    paths.py           def resolve_workflow_path(raw: str, *, base_dir: str) -> str
                       def remap_into_dir(raw: str, directory: str) -> str
                       def relativize(path: str, base_dir: str) -> str | None
                       def is_codegen_safe_dir(p: str) -> bool
    params.py          @dataclass(frozen=True) class ParamDef{name,type,node_id,setting,default,required,label}
                       PARAM_TARGETS: dict[tuple[str, str], TargetRule]
                       def read_param_defs(doc) -> list[ParamDef] ; def parse_cli_params(items: list[str]) -> dict[str, str]
                       def apply_params(doc, defs, overrides, *, input_dir, output_dir, cwd) -> AppliedParams
    approvals.py       class ApprovalStore{ def __init__(path) ; is_approved(sha)->Approval|None ; add(...) ; revoke(sha) ; list() }
    code_policy.py     class CodePolicyError(Exception) ; def validate_generated_code(code, *, io_paths) -> None
                       def sandbox_code_filter(code, io_paths) -> str ; def sandbox_globals() -> dict ; SAFE_BUILTIN_NAMES
    atomic.py          def write_json_atomic(path, obj) ; @dataclass class StagedOutput{node_id, final, staged, backup}
                       def plan_staging(finals, run_id, state) -> list[StagedOutput]
                       def commit_all(staged: list[StagedOutput]) -> None ; def discard_all(staged) -> None
    locks.py           class RunLock{ acquire()->None (raises CliError(BUSY)) ; release() ; note_staged(paths) }
    events.py          class Emitter{ __init__(fmt, log_file, level, stream=None) ; emit(event, level="INFO", **fields) ; close() }
                       def capture_stdout_channel() -> IO[bytes]      # X9
    supervisor.py      class Supervisor{ cancel: threading.Event ; run(target) -> int ; force_exit(code, reason) }
    plan.py            @dataclass class RunPlan{...} ; def build_run_plan(args, doc, ctx) -> RunPlan     # all pre-flight, no Qt
    runner.py          @dataclass class RunOutcome{exit_code:int, record: object|None, record_path:str|None, errors:list[dict]}
                       def run_workflow_file(path, *, input_overrides={}, output_dir=None, record_dir=None, timeout_s=None, **opts) -> RunOutcome
    schedule.py        @dataclass class ScheduleSpec{...} ; def build_task_xml(spec)->str ; def build_command(spec)->list[str]
                       def schtasks_create/delete/query(...)    # all subprocess goes through _run_schtasks()
    verify.py          def verify_record(path, *, workflow=None, check_files=True) -> list[Finding]
  qt/headless.py       (imports Qt; only imported by runner/validate --deep)
                       class HeadlessWindow(TriggerSubWindow){messages: list[tuple[str,str]]; log() override}
                       class HeadlessSession{ __init__() ; load(tds_path)->LoadReport ; sorted_nodes() ; close() }
                       def execute_nodes(nodes, executor, *, cancel, on_event, recorder, record, keep_going=False, upstream=None) -> LoopOutcome   # thin wrapper over plan 09 F-C run_nodes; LoopOutcome = run_loop.RunOutcome (distinct from runner.RunOutcome)
```

`ctx` is a small `CliContext{state: Path, emitter: Emitter, now: Callable}` built by `app.main`.

### 3.3 CLI grammar (authoritative; full help text drafts in Appendix B)

Program name `trigger-designer-cli` (console script + `trigger-designer-cli.exe` + `python -m trigger_designer.cli`).
Reason for the name: the brief's contract (11.3) and the GUI exe/script keep `trigger-designer`.

```text
trigger-designer-cli [--version] [--state-dir DIR] <command> [options]

run        WORKFLOW [--param NAME=VALUE]... [--input-dir DIR] [--output-dir DIR] [--dry-run]
                    [--timeout SEC=3600] [--max-memory MB] [--threads N] [--cancel-grace SEC=10]
                    [--min-free-mb N=64] [--create-output-dirs] [--strict] [--keep-going]
                    [--allow-unapproved] [--allow-custom-code]
                    [--record-dir DIR] [--no-record] [--no-hash] [--emit-script FILE]
                    [--log-format {text,json}=text] [--log-file FILE] [-v|-vv] [--quiet]
                    [--trigger {manual,schedule}=manual]
validate   WORKFLOW [--deep] [--no-files] [--strict] [--param ...] [--input-dir DIR] [--output-dir DIR]
                    [--format {text,json}=text]
info       WORKFLOW [--format {text,json}=text]
approve    WORKFLOW [--yes] [--note TEXT]   |   --list   |   --revoke WORKFLOW
verify-log [RECORD_OR_DIR] [--workflow WORKFLOW] [--no-files] [--format {text,json}=text]
params     list WORKFLOW | add WORKFLOW --name N --node ID_OR_TITLE --setting S [--type T] [--default V] [--required] [--label L]
           | remove WORKFLOW --name N
paths      WORKFLOW [--relativize] [--write]
schedule   add NAME WORKFLOW (--daily HH:MM | --weekdays HH:MM | --weekly DAYS@HH:MM | --hourly N | --once YYYY-MM-DDTHH:MM)
                    [--param NAME=VALUE]... [--run-whether-logged-on] [--skip-missed] [--timeout SEC] [--max-memory MB]
                    [--print-only] [--force]
           | list [--format {text,json}] | show NAME | remove NAME
```

Rules: argparse (stdlib; F14). `ArgumentParser.error` is overridden to exit **64** (so argparse's
default `2` cannot collide with "workflow invalid"). Unknown flags are errors (no abbreviations:
`allow_abbrev=False`). `--param` may repeat; `NAME=VALUE` splits on the **first** `=`.
`--version` prints `trigger-designer-cli 0.1.0 (workflow schema 2)` from `core/constants.py`.
`--state-dir` is also settable with env `TRIGGER_DESIGNER_STATE_DIR` (flag wins).
`-v` = INFO, `-vv` = DEBUG for the loguru bridge; default level WARNING (node code logs emoji-rich
INFO chatter that would drown the event stream).

### 3.4 Exit-code table (frozen contract; extends the brief's 0-3)

| Code | Name | Meaning | `td_code` examples |
|---|---|---|---|
| 0 | `OK` | all nodes ran, outputs committed (or dry-run plan OK) | |
| 1 | `NODE_FAILED` | a node raised during execution (with `--keep-going`: at least one node failed; independent branches still ran, outputs of **successful** File Output nodes were committed) | the node's `NodeError.code` (plan 03) |
| 2 | `INVALID` | workflow unreadable/invalid, schema newer than supported, unknown op, cycle, bad/unknown parameter, missing input file, missing output folder, low disk, `--strict` warnings | `TD-CLI-001..007,014,015`, `TD-IN-001` |
| 3 | `INTERNAL` | unexpected exception in the CLI itself | `TD-SYS-999` |
| 4 | `TIMEOUT` | `--timeout` exceeded; process killed | `TD-RUN-001` |
| 5 | `MEMORY` | `--max-memory` exceeded; process killed | `TD-RUN-002` |
| 6 | `REFUSED` | safety policy: not approved, hash changed since approval, custom-code node, generated code rejected by the policy | `TD-CLI-008..011` |
| 7 | `BUSY` | another run holds the lock for this workflow | `TD-CLI-012` |
| 8 | `COMMIT_FAILED` | nodes ran but promoting staged outputs failed (file locked by Excel, disk full); previous outputs restored | `TD-CLI-013` |
| 9 | `SCHEDULER` | `schtasks` failed / unsupported platform | `TD-CLI-016` |
| 10 | `VERIFY_FAILED` | `verify-log` found a mismatch | `TD-CLI-017` |
| 64 | `USAGE` | bad command line (argparse) | |
| 130 | `CANCELLED` | Ctrl+C / Ctrl+Break / SIGTERM (graceful or forced) | `TD-RUN-004` |

Precedence when several apply: `CANCELLED` > `TIMEOUT` > `MEMORY` > `COMMIT_FAILED` > `NODE_FAILED` > `OK`.
Reason: "operator stopped it" is the most informative fact; a retry wrapper can branch on 4/5/7/8 (retry later)
vs 1/2/6 (do not retry) vs 130 (operator action).

`td_code`s starting `TD-CLI-` are defined only in `core/headless/exit_codes.py` (`CLI_CODES: dict[str, str]`
mapping code -> default English message): 001 workflow unreadable/not JSON, 002 schema newer than
supported, 003 unknown node type, 004 graph has a cycle, 005 unknown parameter, 006 parameter value
invalid, 007 parameter target unsupported, 008 not approved, 009 approval hash mismatch (reserved for
`schedule`), 010 generated code refused, 011 custom-code node refused, 012 run locked, 013 output
commit failed, 014 output folder missing/not writable, 015 low disk space, 016 scheduler error,
017 verification failed, 018 workflow writes no files (warning). Plan 03's `TD-RUN-001/002/004` and `TD-IN-001` are reused where they fit.
**Supersedes plan 03's exit-code proposal:** if plan 03 (or any other plan) proposes different process exit codes, this table is the only contract (review decision). The full `TD-CLI-001..018` catalogue text for plan 03 to paste is in Appendix C.

### 3.5 Parameters

**Where they live.** `workflow_metadata.parameters` (brief 3.5: new top-level keys only inside
`workflow_metadata`). A list of:

```json
{"name": "input_file", "label": "Input file", "type": "path_in",
 "node_id": 2176004824160, "setting": "filePath", "default": "data/check.csv", "required": false}
```

* `name`: `^[a-z][a-z0-9_]{0,39}$`, unique in the file.
* `type`: `path_in | path_out | string | int`.
* `required`: if true and no default and no `--param`, exit 2 (`TD-CLI-005`).
* A param binds **one** `(node_id, setting)`. Several params may bind different settings of one node.

**Minimal safe set (the only bindable targets; table `PARAM_TARGETS` in `params.py`).** Reason: these
are the settings an operator legitimately changes per run, and each has a verifiable value shape.

| op | setting | allowed type | value rule |
|---|---|---|---|
| `input.file_input` | `filePath` | `path_in` | a file, **folder or glob pattern** (plan 01) or a database file; resolved by 3.6; existence/match count checked through plan 01's `resolve_input_files` |
| `input.file_input` | `include_patterns`, `exclude_patterns` | `string` (comma-separated, stored as the list plan 01 defines) | no `'`, `\`, CR, LF, NUL |
| `input.file_input` | `max_files` | `int` | `1..100000` |
| `input.file_input` | `db_table` | `string` | `^[A-Za-z_][A-Za-z0-9_.]{0,127}$`; **`db_query` is not bindable** (SQL text) |
| `input.file_input` | `selected_sheet` | `string` | no `'`, `\`, CR, LF, NUL (kept even though plan 01's `source_spec()` uses `repr`; it is a one-line defence)  |
| `input.file_input` | `record_limit` | `int` | `0..2_000_000_000` |
| `input.file_output` | `filePath` | `path_out` | resolved by 3.6; staged by 3.8; folder must exist unless `--create-output-dirs` |
| `preparation.filter` | `value`, `value2` | `string` | same character rule; refused (`TD-CLI-007`) when the node's `mode` is `"expression"` |
| `preparation.split` | `random_seed` | `int` | `0..2**31-1` |
| `preparation.split` | `estimation_percent` | `int` | `1..99` |

Everything else (delimiter, sheet *index* semantics, expressions, column names, formulas) is **not
bindable** (exit 2, `TD-CLI-007`). Reason: those are the strings that reach code generation unescaped (X3).

**Semantics.**
1. `--param name=value`: `name` must exist in the block (else exit 2 `TD-CLI-005`, message lists known names).
2. Types: `int` -> `int(value)` (no floats, no `_`), error -> `TD-CLI-006` showing an example.
3. Precedence for a bound **path** setting, highest first: (1) explicit `--param`; (2) `--input-dir`/`--output-dir`
   remap of (param default, else the saved path) for `path_in`/`path_out` respectively; (3) param `default`;
   (4) the node's saved value. For a bound **non-path** setting: `--param`, else `default`, else saved value.
4. `--input-dir DIR` / `--output-dir DIR` also apply to File Input / File Output nodes that have **no** param binding:
   new path = `DIR/<basename of the saved path>` (basename taken with both `/` and `\` as separators, so a
   Windows-authored file works in a Linux container). This is the "migration" tool for saved absolute paths. A relative `DIR` is relative to the invoker's CWD.
5. (patcher rule, plan 01) Whenever a `filePath` of a File Input is overridden or remapped, the patcher **deletes `filePathRel` from that node's content** (plan 01 prefers it over `filePath` on load; `tests/support/workflows.materialize` does the same). Parameters are applied to a **copy** of the workflow JSON (`<state>/work/<run_id>/workflow.tds`, ASCII-only JSON, F10);
   the original is never modified. The copy is what `fileLoad` reads, so the GUI load path is exercised unchanged.
6. The resolved values are echoed in `plan.resolved` and stored in the CLI sidecar (`<run_id>.cli.json`) - never
   in the workflow.
7. `params add` validates `(op, setting)` against `PARAM_TARGETS` and writes the block with an atomic file replace,
   keeping a one-time backup `WORKFLOW.bak` (same directory).
8. **GUI preservation (F9):** carried forward by plan 09 F-F (`loaded_workflow_metadata` keys survive `serialize()`). This plan adds only the test
   `test_scene_metadata_roundtrip.py::test_parameters_block_survives_save` (step S2).

### 3.6 Path-resolution rules (`core/headless/paths.py` is the single owner)

`resolve_workflow_path(raw, *, base_dir)` (replaces plan 01's minimal helper; if plan 01's `core/inputs.py` has one,
its body becomes a call to this function - see S2):

1. `raw = raw.strip()`. Empty -> `CliError(INVALID, "TD-IN-001")`. Contains NUL -> `TD-CLI-006`.
2. URL-looking (`^[A-Za-z][A-Za-z0-9+.-]+://`) -> `CliError(INVALID, "TD-CLI-006", "remote paths are not supported")`.
   (Two or more letters before `://`, so `C:\x` is not a URL.)
3. No `~` and no `%VAR%`/`$VAR` expansion (determinism, and no environment-driven path injection).
4. Relative paths (not `os.path.isabs`, not drive-qualified, not UNC) are joined to `base_dir` = **directory of the `.tds`**
   (never the CWD: a scheduled task's CWD is `C:\Windows\System32`), then `os.path.normpath`. On POSIX, backslashes in a
   relative path become `/`.
5. Absolute paths are returned `normpath`'d. A Windows drive path (`^[A-Za-z]:[\\/]`) on POSIX is returned unchanged and will
   simply fail the existence check with the hint "use --input-dir to remap saved paths".
6. `--param` path values (not workflow values) are resolved against the **CWD of the invoker** (shell convention);
   `schedule add` makes them absolute at definition time.
7. Existence is checked only for `path_in`/File Input; the result is a `ResolvedFile` (plan 01) via `resolve_input_files`.
8. `relativize(path, base_dir)`: returns a forward-slash relative path iff `path` is under `base_dir` on the same drive
   (case-insensitive on Windows), else `None`. `paths --relativize --write` rewrites only those, creating `WORKFLOW.bak`.
9. `is_codegen_safe_dir(p)`: no `'`, `"`, `{`, `}`, CR, LF, NUL. Used by output staging (3.8): generated File Output code embeds
   the path in an f-string (`file_output.py:341`), so such paths are staged elsewhere.

GUI side (done in S2, small): plan 01 (3.9) sets `scene.workflow_dir` and resolves `filePathRel` first; this plan adds only the fallback for a workflow whose
`filePath` is a **relative path with no `filePathRel`** (hand-edited or produced by `paths --relativize --write`): `TriggerScene.deserialize` resolves it through
`resolve_workflow_path(raw, base_dir=self.workflow_dir)` before the nodes are built, so such a workflow also opens in the GUI. The GUI still *saves* absolute
`filePath` (+ `filePathRel`); `paths --relativize` is the explicit step for deployment copies and also clears `filePathRel` it made stale (decided: one
rewrite function, `relativize_workflow(data, base_dir)`, writes both keys consistently).

### 3.7 Run lifecycle, cancellation, timeout, memory

**Threads (decided).** `main` = Qt/GUI thread (QApplication, load, signal handling, poll loop);
`td-runner` = the node loop (like the GUI's `WorkflowWorker`); `td-watchdog` = timeout, memory, cancel-grace.
The executor's own pooled thread still runs `exec()` (unchanged). Reason: widgets must be created on the main
thread; signals are only delivered to the main thread, and it must stay in a `time.sleep` loop to receive
them on Windows (X8).

**Order of operations in `run` (each failure names its exit code):**
1. Parse args -> `Emitter` (X9 fd redirect first, before any import that could print) -> `--threads` sets
   `POLARS_MAX_THREADS` (must precede the first polars import).
2. `read_workflow` (encoding fallback: UTF-8 strict, then locale encoding, then cp1252; F10) -> `INVALID`.
3. `schema_version > 2` -> `INVALID TD-CLI-002`. Missing `workflow_metadata` = legacy v1: allowed with a warning.
4. `static_validate`: ops known (v1 nodes without `op` are skipped with a warning; `--deep` resolves them), edges
   reference existing sockets, no cycle (Kahn on socket->node map) -> `INVALID`.
5. Trust gate (3.11): custom-code op -> `REFUSED`; not approved and no `--allow-unapproved` (or `--trigger schedule`) -> `REFUSED`.
6. `build_run_plan`: params (3.5), paths (3.6), `ResolvedFile` check of every input (missing -> `INVALID TD-IN-001`, all
   missing files listed at once), output folders (missing -> `INVALID TD-CLI-014` unless `--create-output-dirs`;
   probe writability by creating+deleting a temp file), free space on each output volume `< --min-free-mb` ->
   `INVALID TD-CLI-015`, staging plan (3.8). Emit `plan.resolved`.
7. `--dry-run`: additionally do steps 9-10 (load + code generation + policy validation of **every node's
   `get_code()`**, no `exec`), print the plan, exit 0/2/6. No lock, no files written except the work copy (deleted).
8. Acquire `RunLock` (`BUSY` if held by a live pid). Start `td-watchdog`.
9. Main thread: `HeadlessSession.load(work_copy)`; messages from `HeadlessWindow.log` become `warning` events;
   unresolved `TriggerNode_Unknown` -> `INVALID TD-CLI-003`; `--strict` turns any warning (invalid node after load,
   schema drift, validation messages) into `INVALID`. Without `--strict`, nodes that are invalid only because they are
   unwired are **not** errors (the GUI runs them with fallback code too; parity).
10. Build `NodeExecutor(SecurityConfig(max_execution_time=<timeout or 1e9>, max_memory_mb=1e9))`, install the policy
    (`executor.execution_context` replaced by `sandbox_globals()`, `executor.code_filter = ...`, a plan 09 F-B hook). Build the recorder (3.12 below),
    install `executor.before_node/after_node` from it, then call every node's `content.before_run()` (the same per-content contract as plan 09 F-B's `_run_before_run_hooks`; exceptions are logged as
    `warning` events, never fatal; runs on the main thread before the runner starts). Start `td-runner` running `core/ExecutionCheck/run_loop.py::run_nodes` (plan 09 F-C) via `execute_nodes`; `--keep-going` is passed as `continue_on_error=`; main thread polls
    (`time.sleep(0.2)`).
11. Commit staged outputs (3.8) **before** the record is finished (`COMMIT_FAILED` on error); fingerprint the committed finals.
12. `recorder.finish(record, ok, cancelled=..., outputs=<post-commit fingerprints>, save=not no_record)` **once** (3.12); sidecars (`.sha256`, `.cli.json`); emit `run.finished`; release lock;
    **always leave through `os._exit(code)`** after flushing the event stream (reason: `main.py` documents a sip fault at
    interpreter finalization with live widgets; Polars/Rust threads can also delay a normal exit).

**Cancellation semantics (state this wording verbatim in help and docs):**
* A cancel request (first Ctrl+C / Ctrl+Break / SIGTERM; the GUI Cancel button reaches the GUI loop through plan 09 F-D) sets a flag that is checked
  **between nodes** only. The node that is running finishes (or fails) first. In-node cancellation does not exist for
  generated code: Python cannot interrupt `exec()`, and a Polars `collect`/`sink_*` runs in Rust with the GIL released
  (X8) - there is no cancel handle in generated code. The GUI's "abandoned thread" limitation (a timed-out node keeps
  running) is unchanged for the GUI.
* **CLI only**: after the first request the watchdog waits `--cancel-grace` seconds (default 10). If the node has not
  finished it calls `force_exit(130, "cancel_forced")`: emit `run.cancel_forced`, snapshot the record (running node recorded
  `failed` with `TD-RUN-004`), `discard_all(staged)`, release the lock, `os._exit(130)`. A second signal forces immediately.
  Process exit is the only real in-node cancel, and it is safe *because outputs are staged* (3.8): the final files are
  never touched until every node succeeded.
* `--timeout SEC` (default 3600; `0` = none) is a **whole-run wall clock** measured from process start; at expiry the
  watchdog does `force_exit(4, "timeout")`. `--max-memory MB` is an **absolute process RSS ceiling** polled every 0.25 s
  with `psutil`; at expiry `force_exit(5, "memory")`. Both replace the executor's per-node checks, which are set to
  "never" (the executor's RSS-*delta* check is advisory and only runs after the node, F6).
* GUI Cancel is plan 09 F-D (button -> `request_run_cancel()`); the running node finishes; no forced exit. The CLI's own `Supervisor.cancel` event is passed as `cancel=` to `run_nodes`; nothing else is shared with the GUI path.

### 3.8 Atomic outputs (staging)

For each File Output node (after param/remap resolution) with final path `F`:
* staged path `S` = `<dir(F)>/.<name>.tdtmp-<run8>.<ext>` when `is_codegen_safe_dir(dir(F))`, else
  `<state>/staging/<run8>/<index>.<ext>` (copy-then-replace commit). `run8` = first 8 hex of `run_id`. The same extension is
  kept because some Polars writers infer format from it.
* The patched workflow copy points the node at `S`; generated code writes `S`. Nothing is ever written to `F` until commit.
* **Commit** (only after every node succeeded), `commit_all(staged)`: phase A move each existing `F` to
  `<dir>/.<name>.tdbak-<run8>.<ext>` with `os.replace` (a locked file fails here, before anything was replaced);
  phase B `os.replace(S, F)` (or copy to a same-directory temp then replace, for cross-volume staging);
  phase C delete the backups. Any failure in A or B rolls back (restore backups, delete staged) and raises
  `CliError(COMMIT_FAILED)`.
* **Stale temps**: `RunLock` records staged/backup paths in the lock file; the next run that finds a *dead* owner deletes
  them. Nothing else is ever globbed or deleted.
* The recorded output fingerprint path is `F` (never `S`): after commit the CLI replaces `record.outputs` with fresh
  `FileFingerprint(role="output", path=F, ...)` values (hashing unless `--no-hash`).

### 3.9 Logging (JSON Lines)

* `--log-format json`: one JSON object per line on **stdout** (the private fd from X9); stderr stays free for
  tracebacks. `--log-format text` (default): human lines on **stderr**; stdout is empty. `--log-file FILE`: always JSONL,
  appended; rotated when larger than 10 MB (`FILE.1`..`FILE.3`).
* Common keys: `ts` (UTC ISO-8601 ms `Z`), `level`, `event`, `run_id`. UTF-8, `\n`, no pretty-printing, orjson.
* Events (stable names; add keys, never rename):

| event | extra keys |
|---|---|
| `run.started` | `workflow, sha256, approved, trigger, pid, version, params` (values of path params as resolved) |
| `plan.resolved` | `inputs[{node_id,path,exists,size_bytes}], outputs[{node_id,final,staged}], warnings[]` |
| `node.started` | `node_id, title, op, index, total` |
| `node.finished` | `node_id, title, status(ok|failed), duration_s, error{code,title,hint}|null` |
| `run.cancelling`, `run.cancel_forced`, `run.timeout`, `run.memory_exceeded` | `reason, elapsed_s, rss_mb` |
| `output.committed` | `path, size_bytes, sha256|null` |
| `output.commit_failed` | `path, error` |
| `warning` | `message, node_id|null` |
| `log` | `source, message` (loguru bridge) |
| `run.finished` | `status(ok|failed|cancelled|refused|invalid), exit_code, duration_s, nodes_ok, nodes_failed, record_path|null, errors[{node_id,title,code,message,hint}]` |

`errors[]` and `node.finished.error` come from the `NodeRunRecord.error` (a plan-03 `NodeError`); the CLI never
re-translates. Text mode ends with one block: `FAILED at node 'Formula' [TD-SCH-001] <title> - <hint>`.

### 3.10 Scheduling (Windows Task Scheduler, local only)

**Storage** `<state>/schedules/<NAME>.json` (written atomically) plus the generated `<NAME>.xml`:

```json
{"version": 1, "name": "nightly-sales", "task_name": "TriggerDesigner\\nightly-sales",
 "workflow": "C:/data/wf.tds", "workflow_sha256": "<64 hex>",
 "params": {"input_file": "C:/data/in.csv"},
 "trigger": {"kind": "daily", "time": "02:30"},
 "run_whether_logged_on": false, "skip_missed": false, "timeout_s": 3600, "max_memory_mb": null,
 "created_at": "2026-10-21T10:00:00Z",
 "command": ["C:/Program Files/Trigger Designer/trigger-designer-cli.exe", "run", "C:/data/wf.tds", "--param", "input_file=C:/data/in.csv",
             "--trigger", "schedule", "--log-format", "json", "--log-file", "<state>/logs/nightly-sales.jsonl", "--timeout", "3600"],
 "xml_path": "<state>/schedules/nightly-sales.xml"}
```

`NAME`: `^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$`. Executable: frozen -> `sys.executable` (the CLI exe); dev ->
`[sys.executable, "-m", "trigger_designer.cli"]`. Workflow and param paths are made absolute at `add` time.

**Trigger grammar -> XML** (`StartBoundary` is *local* wall-clock time without zone; Task Scheduler runs in local time):
`--daily HH:MM` -> `CalendarTrigger/ScheduleByDay/DaysInterval=1`; `--weekdays HH:MM` -> `ScheduleByWeek` Mon-Fri;
`--weekly MON,THU@HH:MM` -> `ScheduleByWeek/DaysOfWeek`; `--hourly N` -> `TimeTrigger` starting now with
`Repetition/Interval=PT{N}H` (no `Duration` = indefinitely); `--once ISO` -> `TimeTrigger`. `StartBoundary` date for
recurring triggers = today.

**Task XML template** (`build_task_xml`; text is escaped with `xml.sax.saxutils.escape`; file written as UTF-16 with BOM,
the encoding Windows itself exports - X10):

```xml
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo><Description>{description: workflow path + sha256 + created by trigger-designer-cli}</Description>
    <URI>\TriggerDesigner\{name}</URI></RegistrationInfo>
  <Triggers>{trigger_xml}</Triggers>
  <Principals><Principal id="Author"><UserId>{DOMAIN\user}</UserId>
    <LogonType>{InteractiveToken | S4U}</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <StartWhenAvailable>{true | false}</StartWhenAvailable>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT{timeout+300}S</ExecutionTimeLimit>
    <Enabled>true</Enabled>
  </Settings>
  <Actions Context="Author"><Exec>
    <Command>{exe}</Command><Arguments>{subprocess.list2cmdline(args)}</Arguments>
    <WorkingDirectory>{dirname(workflow)}</WorkingDirectory></Exec></Actions>
</Task>
```

(`ExecutionTimeLimit` is written as `PT{n}S` seconds; Task Scheduler normalises.)

**Commands (all through `_run_schtasks(argv) -> CompletedProcess`, the only `subprocess` call, so tests mock one function):**
create `["schtasks", "/Create", "/TN", "TriggerDesigner\\<name>", "/XML", "<xml_path>", "/F"]`;
delete `["schtasks", "/Delete", "/TN", "TriggerDesigner\\<name>", "/F"]`;
status `["schtasks", "/Query", "/FO", "CSV", "/V"]` filtered to rows whose column 1 starts with `\TriggerDesigner\`
(positions 1, 2, 3, 6; dates kept as raw strings, X10). `schedule add --print-only` prints the exact command line and the XML
and creates nothing ("generated, inspectable command"). `schedule add` also prints the command line it ran.

**Decisions.**
* *Missed runs*: `StartWhenAvailable=true` (run as soon as possible after a missed start) by default; `--skip-missed` sets false.
  Reason: a nightly audit job that silently skips because the laptop was asleep is worse than one that runs late.
* *Overlap*: two layers - `MultipleInstancesPolicy=IgnoreNew` in the task and the CLI `RunLock` (a manual run during a
  scheduled one exits 7, not corrupts).
* *Run-as user / no desktop session*: default principal = the creating user, `LogonType=InteractiveToken` ("only when logged
  on"). `--run-whether-logged-on` uses `LogonType=S4U` (no password stored or asked; **no network credentials**: mapped drives and UNC shares
  that need authentication will fail - the runbook says "use local paths or a service account"). We never pass `/RP`, never accept a password.
  If `/Create` fails with access denied for S4U, exit 9 with that hint.
* *Approval*: `schedule add` requires the workflow's current SHA-256 to be approved (exit 6 otherwise). Scheduled runs pass
  `--trigger schedule`, which **ignores** `--allow-unapproved`; if the file changed after scheduling the next run exits 6 and
  logs `TD-CLI-008` (someone edited an approved file).
* *Time*: schedule definitions are local time; records/logs are UTC. A DST gap/overlap is handled by Task Scheduler;
  `StartWhenAvailable` covers a skipped 02:30.
* *Non-Windows*: `schedule` exits 9 with "scheduling is implemented for Windows Task Scheduler only; call the CLI from cron/systemd/launchd (Appendix A)".

### 3.11 Trust model

**Assumptions.** The operator's command line, `--state-dir`, and the approvals file are trusted. The `.tds` is **not**
(it may come from a colleague, e-mail, or a shared drive) and generated code is `exec()`'d (F6, X3).

Layers, all always on in the CLI (there is deliberately **no** `--no-sandbox`; reason: one fewer foot-gun, and X4 shows no false
positives on the corpus; a legitimate rejection is fixed in the allowlist with a test):

1. **Static validation of the JSON** (`validate`/`run`): unknown ops, unresolved nodes, cycles. `TriggerNode_Unknown` -> exit 2.
2. **Approval pinning** (`approve`): SHA-256 of the raw `.tds` bytes. `run` refuses an unapproved file with exit 6 unless
   `--allow-unapproved` (interactive use only; ignored for `--trigger schedule`). `approve` prints what the file **reads**
   (File Input paths after defaults), **writes** (File Output paths), node op counts and parameters, and asks `Approve? [y/N]`
   (`--yes` skips; a non-TTY without `--yes` exits 64). Store: `<state>/approvals.json`
   `{"version":1,"approvals":[{"sha256","name","path","approved_by","approved_at","note","reads":[],"writes":[]}]}`.
   **Unsigned** (decided): the file lives in the same per-user profile an attacker would need to already control; signing needs
   key management for no gain; in CI generate the file in the pipeline and mount it read-only (`--state-dir`).
3. **Custom-code gate**: `OPS[op].custom_code` (false for all 22 ops today; no node embeds user-authored Python). A workflow
   containing a `custom_code=True` op exits 6 unless `--allow-custom-code` **and** approved. The flag exists so plan 07/08+
   authors cannot add a user-Python node that silently runs headless. When allowed, the code is **still** policy-validated.
4. **Generated-code policy** (`code_policy.py`, X4/X5/X7), applied to every node's `get_code()` *before* `exec` and in `--dry-run`:
   * parse; only AST node types in `ALLOWED_NODE_TYPES` (no `ClassDef`, `With`, `Global`, `Nonlocal`, `Async*`, `NamedExpr`, `Yield`, `Await`, `Match`);
   * `import` allowed only for `polars, duckdb, fastexcel, os, datetime` and the two named `trigger_designer.core.utils.*` imports with
     exact names; only `import os` is removed from the tree (`ast.NodeTransformer`); the other allowed imports run as real statements through the builtins `__import__` (X6), and the common names are pre-bound in
     the exec globals (`pl, duckdb, fastexcel, os(SafeOs), datetime, timedelta, normalize_to_supported_dtypes, DataCleansing, NullStrategy`);
   * forbidden names (`__import__ eval exec compile open input breakpoint globals locals vars getattr setattr delattr memoryview exit quit help dir super ... sys subprocess importlib ctypes socket shutil pathlib pickle io tempfile glob requests urllib`), **no dunder names or attributes**,
     forbidden attributes (`system popen environ getenv listdir ... plugins register_plugin_function read_database write_database read_clipboard scan_delta ...`);
   * `os` is a `SimpleNamespace(path=<basename,dirname,join,splitext,exists,isfile,isdir,abspath,normpath>, sep)`; validator allows only `os.path.<those>`;
   * **I/O path rule**: any call whose attribute starts with `scan_`/`read_`/`sink_`/`write_` must have a **string-literal** first argument
     (or `source/file/path/f/workbook` keyword) that is in `io_paths` = {resolved input paths} + {staged output paths}; this is what stops a
     tampered File Output/Input *code path* from touching anything the approved workflow did not declare;
   * **SQL rule**: `.execute/.sql/.query/.executemany` need a literal string that, after blanking quoted literals, is a single `SELECT`/`WITH`
     and contains none of `read_* *_scan glob copy attach detach install load pragma export import call create drop insert update delete alter getenv current_setting http* s3 sniff_csv duckdb_* pg_* write_*`;
     `duckdb.connect` only with `':memory:'`;
   * exec globals use `SAFE_BUILTINS` (about 70 names; includes `__import__`, X6) - no `open`, `eval`, `exec`, `compile`, `getattr`, `globals`, `input`.
   **Allowlist of generated-code imports (verified by reading each plan's `get_code`; `GENERATED_IMPORTS` in `code_policy.py` is the single table):**

   | Source plan | Generated import (module -> allowed names) | Notes |
   |---|---|---|
   | existing nodes | `polars, duckdb, fastexcel, datetime(datetime, timedelta), os` ; `trigger_designer.core.utils.dtype_utils` -> `normalize_to_supported_dtypes`; `...cleansing_util` -> `DataCleansing, NullStrategy` | `import os` is **stripped** and replaced by the SafeOs global; all other allowed imports stay real statements |
   | 01 | `trigger_designer.core.input_source` -> `build_source`, `name_blank_columns` | `build_source` is the builder path; the spec dict literal carries `filePath` (checked by the path-key scan). `name_blank_columns` is emitted by the legacy CSV/TXT path to name blank header cells. |
   | 04 | `trigger_designer.core.audit.{duplicates,gaps,benford,sampling,risk_filters}` -> `DuplicatesParams/run_duplicates`, `GapsParams/run_gaps`, `BenfordParams/run_benford`, `SamplingParams/run_sample`, `RiskParams/run_risk_filters` | calls `.from_dict(...)`, `.for_run()` (plain attributes) |
   | 05 | `trigger_designer.core.profile` -> `profile_table, empty_profile_frame` | |
   | 06 | `trigger_designer.core.excel.frame_export` -> `write_frame_xlsx`; `trigger_designer.core.workpaper.node_runner` -> `run_workpaper` | output path lives in `spec_json` (`output_path`) -> path-key scan; this plan's S1 row `OPS["input.workpaper_output"].output_keys = ("output_path",)` makes the patcher stage it |
   | 07 | `json` -> (module import); `trigger_designer.core.shaping.<module>` -> `run_node` (aliased `as _run_node`) | module part is a **prefix rule**: `trigger_designer.core.shaping.` + `[a-z_]+`; the payload is `json.loads('<literal>')` |

   **Path rules for helpers (replaces "every `write_*` call needs a literal first argument" for helpers):** (a) the literal-path rule applies to *method* calls (`x.scan_csv(...)`, `df.write_csv(...)`) only; (b) calls to allowlisted *named* helpers are not path-checked by name; instead (c) the **path-key scan**: every `dict` literal key and every JSON-looking string constant is inspected recursively and any value under a key in `PATH_KEYS = {"filePath","output_path","db_path"}` must be in `io_paths`; (d) a literal string among the first two positional arguments of a `write_*` named helper must be in `io_paths`. `io_paths` = resolved input paths + staged output paths (3.8).

   **How a future node registers its generated imports:** add one row to `GENERATED_IMPORTS` (module or module-prefix -> allowed names) and, if its content holds an output path, set `OpInfo.output_keys` in `op_catalog.py`; add the node to the corpus test `test_every_registered_node_code_passes_policy` (builds the node, wires a stub source, validates `get_code()`). A node that needs anything outside this table (extra builtin, file API, new SQL token) must be rejected in review or get its own attack-table rows first. Reason: one visible table beats scattered exceptions.

5. **Process hygiene**: runs as the invoking user; no elevation; work copy and staging in the per-user state dir; the patched copy is deleted.

**Known residual risks (documented, accepted).** Approved paths can still be read/overwritten (that is what approval reviews);
DuckDB/Polars internals are trusted; a determined attacker with code-execution in an *allowed* library call is out of scope;
the policy is not a security boundary against a hostile approved file - run unattended jobs under a low-privilege account or in a container
(Appendix A). **No policy relaxation exists for the GUI**: the GUI Run keeps today's behaviour (unchanged, out of scope).

### 3.12 Run-record wiring (plan 02 API; identical to the GUI)

```python
from trigger_designer.core.audit.recorder import RunRecorder, AuditOptions
from trigger_designer.core.audit.store import RunStore
from trigger_designer.qt.helpers.audit_bridge import node_specs_from_window
opts = AuditOptions(store_dir=record_dir or "", enabled=True, hash_inputs=not no_hash, hash_outputs=not no_hash)
recorder = RunRecorder(RunStore(record_dir) if record_dir else None, opts)
specs, edges = node_specs_from_window(window, sorted_nodes)          # same function the GUI uses
record = recorder.begin(original_tds_path, specs, app_version=VERSION, edges=edges)   # ORIGINAL file, not the work copy
executor.before_node, executor.after_node = recorder.before_node, recorder.after_node  # input fingerprints + row counts
# ... run loop (plan 09 F-C) calls recorder.node_finished(record, node, result) per node ...
final = recorder.finish(record, ok, cancelled=cancelled, outputs=post_commit_fingerprints, save=not no_record)   # ONCE
```

Rules: (1) `finish` is called **exactly once**; a `_finish_once` lock-guarded flag lets the normal path and `force_exit` share it (the loser does nothing).
(2) A sealed record is never modified (`dataclasses.replace` is not used; cancellation is `cancelled=True`, committed outputs go in through `outputs=`).
(3) `--no-record` -> `save=False` (the object is still built, so `run.finished` can report counts). (4) The output fingerprints use the **final** paths, hashed after
commit (unless `--no-hash`). (5) Because commit must precede `finish`, a commit failure calls `finish(record, False, outputs=[], ...)` and exits 8.
(6) For a forced exit (timeout/memory/cancel_forced) the running node is passed to `recorder.node_errored(record, node, exc)` with a `TimeoutError`/`MemoryError`/
`KeyboardInterrupt` instance before `finish`. (7) Failed nodes: after the loop call plan 03's `enrich_error(EnrichJob(error=<NodeRunRecord.error>, ancestors=..., inputs_of=..., labels=..., titles=..., ops=...))`
(synchronous, never raises, <= ~15 s) for the **first** failed node only, on the main thread, before `finish`; the enriched `root` replaces the provisional error in events and `errors[]`;
`--timeout` is not extended for it; skipped when the run was cancelled/forced. `--no-enrich` is not offered (decided: the 15 s bound is acceptable).


---

## 4. Ordered implementation steps

One commit per step; each step ends green on its "done when". Always: `ruff format <files>` then `ruff check <files>`
(AGENTS.md; compare `ruff check` before/after - the baseline is not clean) then the named tests. Never `uv sync`;
install with `uv pip install --python .venv/Scripts/python.exe -e . --no-deps` after editing `pyproject.toml`.
Python is 3.13; use `from __future__ import annotations`; no new dependencies (argparse, psutil, orjson, sqlglot are present).
Never run bare `pytest` (brief 2.4): run `tests\unit`, `tests\e2e`, named `tests\ui` files.

**S0 - Preconditions (no commit).** Plans 01, 02, 03 must be merged. Check:
`Test-Path src\trigger_designer\core\inputs.py, src\trigger_designer\core\errors.py, src\trigger_designer\core\audit\run_record.py`
(all True). If any is False, stop and report - do not create provisional copies. Baseline: record the pass counts of
`tests\unit` and `tests\e2e` and the 27 known `tests\ui` failures (brief 2.4).

### S1 - Foundation: exit codes, state, op catalog, workflow reader, `info`, static `validate`, `--version`

Create (all Qt-free; skeletons):

```python
# core/headless/exit_codes.py
from enum import IntEnum
class ExitCode(IntEnum):
    OK = 0; NODE_FAILED = 1; INVALID = 2; INTERNAL = 3; TIMEOUT = 4; MEMORY = 5; REFUSED = 6
    BUSY = 7; COMMIT_FAILED = 8; SCHEDULER = 9; VERIFY_FAILED = 10; USAGE = 64; CANCELLED = 130
CLI_CODES = {"TD-CLI-001": "The workflow file could not be read.", ...}   # all 17 from section 3.4
class CliError(Exception):
    def __init__(self, code: ExitCode, td_code: str, message: str, hint: str = "") -> None: ...
PRECEDENCE = [CANCELLED, TIMEOUT, MEMORY, COMMIT_FAILED, NODE_FAILED, OK]   # section 3.4
```

* `state.py`: `state_dir(override=None)`: `override` > env `TRIGGER_DESIGNER_STATE_DIR` > Windows
  `%LOCALAPPDATA%\Trigger Designer\cli` > `$XDG_STATE_HOME/trigger-designer` > `~/.local/state/trigger-designer`. `data_dir()`
  replicates `qt/preferences.py:57-68` exactly (env `TRIGGER_DESIGNER_DATA_DIR`, else `%APPDATA%\Trigger Designer`, else `~/.trigger_designer`).
  `ensure(sub)` = `mkdir(parents=True, exist_ok=True)`, returns the Path. Subdirs used: `locks work staging schedules logs`.
* `op_catalog.py`: `OPS` literal dict with one `OpInfo` per op. Rows for the **22 implemented ops** - exactly `input.file_input`, `input.file_output`,
  `preparation.{cleansing,filter,formula,groupby,select,sort,unique,split,dynamic_row_builder,normalize_columns}`,
  `join.{append,join,union}`, `transform.{count_records,running_total,transpose}`, `report.graph` (title = the node's `node_title`) - with `planned=False`,
  **plus rows for every node planned by plans 01, 04, 05, 06, 07 with `planned=True`** (table below). This plan adds all of them in this step; plans 04/05/06/07 do not
  need to touch `op_catalog.py` (they are not edited for it). Rule for the future: **any node added after these plans must add its own row** (and `output_keys` if it holds an output path).
  Not listed on purpose: `input.browser`, `input.text_input`, `transform.arrange` (enum members without nodes).

  **Planned-op rows (added by this plan; `family` = the enum family value, `title` = the plan's `node_title`; `custom_code=False` for all - none embeds user-authored Python, SQL Query is limited to a guarded single SELECT by plan 07's `sql_guard`):**

  | Plan | `op` | `title` | `family` | `output_keys` |
  |---|---|---|---|---|
  | 01 | (none: `input.file_input` / `input.file_output` keep their ids; the new File Input types - parquet `.parquet .pq`, json `.json`, ndjson `.ndjson .jsonl`, sqlite/duckdb `.db`, excel, csv/txt - are chosen by `detect_file_type` at run time and are not catalogue data) | - | - | file_input: `()`; file_output: `("filePath",)` |
  | 04 | `audit.duplicates` | Duplicates | audit | `()` |
  | 04 | `audit.gaps` | Gaps | audit | `()` |
  | 04 | `audit.benford` | Benford | audit | `()` |
  | 04 | `audit.sample` | Sample | audit | `()` |
  | 04 | `audit.risk_filters` | Risk Filters | audit | `()` |
  | 05 | `report.data_profile` | Data Profile | report | `()` |
  | 06 | `input.workpaper_output` | Workpaper Output | input | `("output_path",)` (plan 06 persisted key; the patcher stages it) |
  | 07 | `preparation.record_id` | Record ID | preparation | `()` |
  | 07 | `preparation.select_records` | Select Records | preparation | `()` |
  | 07 | `preparation.find_replace` | Find and Replace | preparation | `()` |
  | 07 | `preparation.date_helper` | Date Helper | preparation | `()` |
  | 07 | `preparation.text_to_columns` | Text to Columns | preparation | `()` |
  | 07 | `preparation.multi_field_formula` | Multi-Field Formula | preparation | `()` |
  | 07 | `join.reconcile` | Reconcile | join | `()` |
  | 07 | `join.fuzzy_match` | Fuzzy Match | join | `()` |
  | 07 | `transform.pivot` | Pivot | transform | `()` |
  | 07 | `transform.unpivot` | Unpivot | transform | `()` |
  | 07 | `transform.window` | Window | transform | `()` |
  | 07 | `transform.sql_query` | SQL Query | transform | `()` |
  | 07 | `report.comment` | Comment | report | `()` |

  `known_op(op)` returns planned rows too, so static `validate` accepts a workflow that uses them; `--deep` (real registry) reports `TD-CLI-003` for a planned op whose node is not yet registered in the installed build. Op ids are copied from each plan's op/enum table (op id = `<family>.<member lower case>`); if a plan renames one, the catalogue test below fails.
* `workflow_file.py`: `read_workflow(path)`: `raw = Path(path).read_bytes()`; try `raw.decode("utf-8")`, then
  `locale.getpreferredencoding(False)`, then `cp1252` (record which); `json.loads` (stdlib; **not** orjson, so big ints stay exact);
  must be a dict with `nodes` (list) and `edges` (list) else `CliError(INVALID, "TD-CLI-001", ...)`. `sha256 = hashlib.sha256(raw)`.
  `schema_version = data.get("workflow_metadata", {}).get("schema_version", 0)`.
  `static_validate(doc)` returns `Finding`s: `TD-CLI-002` (schema > 2, level error), `TD-CLI-003` (op not in `OPS`, error; nodes
  without `op` -> warning "legacy v1 node, resolved by --deep"), `TD-CLI-004` (cycle: map every socket id (`nodes[].inputs[].id`, `.outputs[].id`)
  to its node id, build edges `socket(start).node -> socket(end).node`, Kahn; error), dangling edge endpoints (warning).
  `file_nodes(doc)` -> `[FileNode(node_id, kind="input"|"output", raw_path, title)]` (kind from `op` suffix `file_input`/`file_output`, or title for v1 nodes,
  same rule as `tests/support/workflows.py:_node_kind`).
* `cli/parser.py` `build_parser()`: subparsers for **all** commands now (handlers for the not-yet-built ones print
  `not implemented yet` and return 3 - replaced step by step); `ArgumentParser` subclass whose `error()` prints usage + message to
  stderr and `sys.exit(64)`; `allow_abbrev=False`; help texts verbatim from Appendix B.
* `cli/app.py`:

```python
def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)          # SystemExit(64) on usage errors; --version/--help exit 0
    try:
        return int(args.handler(args, make_context(args)))
    except CliError as exc:
        _print_error(args, exc)             # text or json per args.format/log_format
        return int(exc.code)
    except KeyboardInterrupt:
        return int(ExitCode.CANCELLED)
    except Exception:                       # noqa: BLE001 - last line of defence
        traceback.print_exc(file=sys.stderr)
        return int(ExitCode.INTERNAL)
```

* `commands/info.py`: reads, prints (text or json): path, sha256, size, schema/app version, saved_at, encoding, node counts per op,
  File Input rows (raw path, resolved path via 3.6, exists, size), File Output rows, parameter block, approval status
  (`ApprovalStore` is added in S3; until then print `approval: unknown`). **Must not import polars or PyQt6.**
* `commands/validate.py` (static only now): runs `static_validate`, `--strict` promotes warnings, prints findings, exit 0/2.
* `pyproject.toml`: plan 09 F-G does the shared pass; this plan adds only `trigger-designer-cli = "trigger_designer.cli:main"` under `[project.scripts]` (keep `trigger-designer`).
  Reinstall editable (command above). Plan 09 F-G created a stub `cli/__init__.py`; **overwrite** it with `def main(argv=None): from trigger_designer.cli.app import main as _m; return _m(argv)`.

Done when:
```powershell
.venv\Scripts\python.exe -m ruff format src\trigger_designer\cli src\trigger_designer\core\headless tests\unit\test_cli_parser.py
.venv\Scripts\python.exe -m ruff check  src\trigger_designer\cli src\trigger_designer\core\headless
.venv\Scripts\python.exe -m pytest tests\unit\test_cli_parser.py tests\unit\test_headless_workflow_file.py tests\unit\test_op_catalog_matches_registry.py tests\unit\test_cli_import_discipline.py -q
.venv\Scripts\trigger-designer-cli.exe --version        # -> trigger-designer-cli 0.1.0 (workflow schema 2)
.venv\Scripts\trigger-designer-cli.exe info "savedfiles\0. All Node- Test.tds" --format json   # valid JSON, exit 0
```

### S2 - Paths, parameters, `params`/`paths` commands, GUI metadata preservation

* `paths.py` implements 3.6 exactly. Skeleton of the part that is easy to get wrong:

```python
_URL = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]+://")
_WIN_DRIVE = re.compile(r"^[A-Za-z]:[\\/]")
def basename_any(raw: str) -> str:
    return re.split(r"[\\/]", raw.rstrip("\\/"))[-1]
def remap_into_dir(raw: str, directory: str) -> str:
    return os.path.normpath(os.path.join(directory, basename_any(raw)))
def resolve_workflow_path(raw: str, *, base_dir: str) -> str:
    raw = raw.strip()
    if not raw: raise CliError(ExitCode.INVALID, "TD-IN-001", "empty file path")
    if "\x00" in raw or _URL.match(raw): raise CliError(ExitCode.INVALID, "TD-CLI-006", f"unsupported path: {raw!r}")
    if os.name != "nt" and not _WIN_DRIVE.match(raw):
        raw = raw.replace("\\", "/")
    if os.path.isabs(raw) or _WIN_DRIVE.match(raw) or raw.startswith("\\\\"):
        return os.path.normpath(raw)
    return os.path.normpath(os.path.join(base_dir, raw))
```

* `params.py`: `PARAM_TARGETS = {("input.file_input","filePath"): Rule("path_in"), ("input.file_input","selected_sheet"): Rule("string", forbid="'\\\r\n\0"), ("input.file_input","record_limit"): Rule("int",0,2_000_000_000), ("input.file_output","filePath"): Rule("path_out"), ("preparation.filter","value"): Rule("string", forbid=..., needs={"mode":"builder"}), ("preparation.filter","value2"): same, ("preparation.split","random_seed"): Rule("int",0,2**31-1), ("preparation.split","estimation_percent"): Rule("int",1,99)}`.
  `apply_params(...)` works on `copy.deepcopy(doc.data)`: for each bound param compute the value by the 3.5 precedence, validate by `Rule`, set `node["content"][setting]` (for File Input `filePath` also `content.pop("filePathRel", None)`, plan 01); then for every File Input/Output node **without** a binding apply
  `--input-dir/--output-dir` remap, then `resolve_workflow_path(..., base_dir=dirname(doc.path))` for all path values. Returns
  `AppliedParams(data, resolved: dict[name, str], inputs: list[FileNode+resolved], outputs: list[...])`. It does **not** stage (S5).
  A node bound to a `(op, setting)` missing from `PARAM_TARGETS`, or a filter in `expression` mode -> `CliError(INVALID, "TD-CLI-007")`.
* `commands/params.py` (`list/add/remove`) and `commands/paths.py` (`paths WORKFLOW` prints raw/resolved/exists per File node;
  `--relativize` shows the rewrite; `--write` applies with atomic replace + `.bak`).
* Metadata carry-forward, atomic UTF-8 `saveToFile` and `workflow_dir` are **plan 09 F-F**; do not edit `performance_scene.py:166-173` or `saveToFile` here.
* If plan 01's `core/inputs.py` contains a private path helper, change its body to `return resolve_workflow_path(raw, base_dir=base_dir)`
  and keep its signature; do not touch anything else in 01.
* GUI relative-path fallback (3.6): in `TriggerScene.deserialize` (after plan 01's `filePathRel` resolution), for nodes whose `op` ends with `file_input`/`file_output`, whose
  `content["filePathRel"]` is empty and whose `content["filePath"]` is relative, replace it with `resolve_workflow_path(raw, base_dir=self.workflow_dir)` (attribute set by plan 09 F-F;
  `workflow_dir`, not `workflow_base_dir`). Guard with try/except `CliError` -> leave unchanged.

Done when: `pytest tests\unit\test_headless_paths.py tests\unit\test_headless_params.py tests\unit\test_workflow_serialization.py -q` and
`tests\unit\test_scene_metadata_roundtrip.py` (new: assert `parameters` survives a save through plan 09 F-F's carry-forward).

### S3 - Approvals and `approve`

`approvals.py`: `ApprovalStore(path)` reads/writes `{"version":1,"approvals":[...]}` through `write_json_atomic`; `is_approved(sha) -> dict | None`;
`add(entry)` replaces an entry with the same sha; `revoke(sha_or_path)`; unknown JSON version -> `CliError(INVALID)`.
`commands/approve.py`: `approve WORKFLOW` prints the review block (reads, writes, op counts, parameters, sha256), asks `Approve? [y/N]` using
`input()` only when `sys.stdin.isatty()`; `--yes` skips; non-TTY without `--yes` -> exit 64. `--list`, `--revoke WORKFLOW`.
`approved_by = getpass.getuser()`. Update `info` to show `approved: yes (by X at T) | no | changed since approval of <path>` (same path,
different sha -> "changed").
Done when: `pytest tests\unit\test_headless_approvals.py -q`.

### S4 - Code policy and executor hooks

Create `core/headless/code_policy.py` with **this verified code** (it passed X4/X5/X7; copy, then format):

```python
from __future__ import annotations
import ast, builtins as _b, json, os, re, types
from collections.abc import Collection

# module -> None (bare `import m` allowed) or the set of names `from m import ...` may take.  THE table future nodes extend (3.11).
GENERATED_IMPORTS = {
    "polars": None, "duckdb": None, "fastexcel": None, "os": None, "json": None,
    "datetime": {"datetime", "timedelta"},
    "trigger_designer.core.utils.dtype_utils": {"normalize_to_supported_dtypes"},
    "trigger_designer.core.utils.cleansing_util": {"DataCleansing", "NullStrategy"},
    "trigger_designer.core.input_source": {"build_source"},                                    # plan 01
    "trigger_designer.core.audit.duplicates": {"DuplicatesParams", "run_duplicates"},          # plan 04
    "trigger_designer.core.audit.gaps": {"GapsParams", "run_gaps"},
    "trigger_designer.core.audit.benford": {"BenfordParams", "run_benford"},
    "trigger_designer.core.audit.sampling": {"SamplingParams", "run_sample"},
    "trigger_designer.core.audit.risk_filters": {"RiskParams", "run_risk_filters"},
    "trigger_designer.core.profile": {"profile_table", "empty_profile_frame"},                 # plan 05
    "trigger_designer.core.excel.frame_export": {"write_frame_xlsx"},                          # plan 06
    "trigger_designer.core.workpaper.node_runner": {"run_workpaper"},                          # plan 06
}
GENERATED_IMPORT_PREFIXES = {"trigger_designer.core.shaping.": {"run_node"}}                  # plan 07 (module part: [a-z_]+)
PATH_KEYS = {"filePath", "output_path", "db_path"}
ALLOWED_NODE_TYPES = {ast.Module, ast.alias, ast.Expr, ast.Assign, ast.AugAssign, ast.AnnAssign, ast.Import,
    ast.ImportFrom, ast.FunctionDef, ast.arguments, ast.arg, ast.Return, ast.If, ast.While, ast.For, ast.Try,
    ast.ExceptHandler, ast.Raise, ast.Pass, ast.Break, ast.Continue, ast.Delete, ast.Del, ast.Call, ast.keyword,
    ast.Name, ast.Load, ast.Store, ast.Constant, ast.Attribute, ast.Subscript, ast.Slice, ast.List, ast.Tuple,
    ast.Dict, ast.Set, ast.JoinedStr, ast.FormattedValue, ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare,
    ast.IfExp, ast.Lambda, ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp, ast.comprehension,
    ast.Starred, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow, ast.BitAnd, ast.BitOr,
    ast.BitXor, ast.Invert, ast.Not, ast.USub, ast.UAdd, ast.And, ast.Or, ast.Eq, ast.NotEq, ast.Lt, ast.LtE,
    ast.Gt, ast.GtE, ast.Is, ast.IsNot, ast.In, ast.NotIn}
OS_PATH_OK = {"basename", "dirname", "join", "splitext", "exists", "isfile", "isdir", "abspath", "normpath", "sep"}
FORBIDDEN_NAMES = {"__import__", "eval", "exec", "compile", "open", "input", "breakpoint", "globals", "locals",
    "vars", "getattr", "setattr", "delattr", "memoryview", "exit", "quit", "help", "dir", "super", "classmethod",
    "staticmethod", "property", "__builtins__", "sys", "subprocess", "importlib", "builtins", "ctypes", "socket",
    "shutil", "pathlib", "pickle", "marshal", "io", "tempfile", "glob", "requests", "urllib"}
FORBIDDEN_ATTRS = {"system", "popen", "spawn", "spawnl", "spawnv", "execv", "execl", "startfile", "unlink", "rmdir",
    "removedirs", "makedirs", "mkdir", "chmod", "chown", "environ", "putenv", "getenv", "listdir", "scandir", "walk",
    "kill", "fork", "read_text", "write_text", "read_bytes", "write_bytes", "os", "sys", "subprocess", "importlib",
    "builtins", "modules", "f_globals", "f_locals", "gi_frame", "cr_frame", "tb_frame", "mro", "load_extension",
    "install_extension", "plugins", "register_plugin_function", "read_database", "read_database_uri",
    "write_database", "read_clipboard", "write_clipboard", "from_pandas", "to_pandas", "register_filesystem",
    "scan_pyarrow_dataset", "scan_delta", "scan_iceberg", "read_delta", "write_delta"}
IO_PREFIXES = ("scan_", "read_", "sink_", "write_")
IO_KWARGS = ("source", "file", "path", "f", "workbook")
SQL_CALLS = {"execute", "sql", "query", "executemany"}
SQL_FORBIDDEN_RE = re.compile(r"\b(read_\w+|\w+_scan|glob|copy|attach|detach|install|load|pragma|export|import|"
    r"call|create|drop|insert|update|delete|alter|getenv|current_setting|http\w*|s3|sniff_csv|duckdb_\w+|pg_\w+|"
    r"write_\w+|force|checkpoint|vacuum)\b", re.I)
_SQL_LIT = re.compile(r"'(?:[^']|'')*'|\"(?:[^\"]|\"\")*\"")

class CodePolicyError(Exception):
    def __init__(self, reason: str, lineno: int | None = None) -> None:
        super().__init__(reason if lineno is None else f"line {lineno}: {reason}")
        self.reason, self.lineno = reason, lineno

def norm_path(p: str) -> str:
    return os.path.normcase(os.path.normpath(p))

def validate_generated_code(code: str, *, io_paths: Collection[str] | None = None) -> None:
    allowed = None if io_paths is None else {norm_path(p) for p in io_paths}
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise CodePolicyError(f"syntax error: {exc.msg}", exc.lineno) from None
    _scan_path_keys(tree, allowed)
    for node in ast.walk(tree):
        line = getattr(node, "lineno", None)
        if type(node) not in ALLOWED_NODE_TYPES:
            raise CodePolicyError(f"{type(node).__name__} is not allowed", line)
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name not in GENERATED_IMPORTS or GENERATED_IMPORTS[a.name] is not None:
                    raise CodePolicyError(f"import of '{a.name}' is not allowed", line)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            names = GENERATED_IMPORTS.get(mod)
            if names is None:
                pre = next((v for p, v in GENERATED_IMPORT_PREFIXES.items()
                            if mod.startswith(p) and re.fullmatch(r"[a-z_]+", mod[len(p):])), None)
                names = pre
            if node.level or not names or any(a.name not in names for a in node.names):
                raise CodePolicyError(f"'from {mod} import ...' is not allowed", line)
        elif isinstance(node, ast.Name):
            if node.id in FORBIDDEN_NAMES or (node.id.startswith("__") and node.id != "__name__"):
                raise CodePolicyError(f"name '{node.id}' is not allowed", line)
        elif isinstance(node, ast.Delete):
            if any(not isinstance(t, ast.Name) for t in node.targets):
                raise CodePolicyError("del is only allowed on plain names", line)
        elif isinstance(node, ast.FunctionDef):
            if node.decorator_list:
                raise CodePolicyError("decorators are not allowed", line)
        elif isinstance(node, ast.Attribute):
            _check_attribute(node, line)
        elif isinstance(node, ast.Call):
            _check_call(node, line, allowed)

def _check_attribute(node: ast.Attribute, line) -> None:
    if node.attr.startswith("__") or node.attr in FORBIDDEN_ATTRS:
        raise CodePolicyError(f"attribute '.{node.attr}' is not allowed", line)
    v = node.value
    if isinstance(v, ast.Name) and v.id == "os" and node.attr != "path":
        raise CodePolicyError(f"'os.{node.attr}' is not allowed (only os.path.*)", line)
    if (isinstance(v, ast.Attribute) and isinstance(v.value, ast.Name) and v.value.id == "os"
            and v.attr == "path" and node.attr not in OS_PATH_OK):
        raise CodePolicyError(f"'os.path.{node.attr}' is not allowed", line)

def _literal_str(n) -> str | None:
    return n.value if isinstance(n, ast.Constant) and isinstance(n.value, str) else None

def _check_call(node: ast.Call, line, allowed: set[str] | None) -> None:
    f = node.func
    attr = f.attr if isinstance(f, ast.Attribute) else None
    if attr in SQL_CALLS:
        sql = _literal_str(node.args[0]) if node.args else None
        if sql is None:
            raise CodePolicyError("SQL must be a string literal", line)
        _check_sql(sql, line)
    if attr == "connect" and isinstance(f.value, ast.Name) and f.value.id == "duckdb":
        if not node.args or _literal_str(node.args[0]) != ":memory:" or len(node.args) > 1 or node.keywords:
            raise CodePolicyError("duckdb.connect only accepts ':memory:'", line)
    if attr and attr.startswith(IO_PREFIXES):
        target = node.args[0] if node.args else next((k.value for k in node.keywords if k.arg in IO_KWARGS), None)
        path = _literal_str(target)
        if path is None:
            raise CodePolicyError(f"'{attr}' needs a literal file path", line)
        if allowed is not None and norm_path(path) not in allowed:
            raise CodePolicyError(f"'{attr}' touches an undeclared path", line)
    if isinstance(f, ast.Name) and f.id.startswith("write_"):      # named helper (plan 06): a literal path among the first two args must be declared
        for arg in node.args[:2]:
            lit = _literal_str(arg)
            if lit is not None and allowed is not None and norm_path(lit) not in allowed:
                raise CodePolicyError(f"'{f.id}' touches an undeclared path", line)

def _scan_path_keys(tree: ast.AST, allowed: set[str] | None, depth: int = 0) -> None:
    """Every value under a PATH_KEYS key - in dict literals and in JSON-looking string constants - must be a declared path."""
    if allowed is None:
        return
    def check(key, value, line):
        if key in PATH_KEYS and isinstance(value, str) and value and norm_path(value) not in allowed:
            raise CodePolicyError(f"'{key}' value is not a declared path", line)
    def walk_json(obj, line):
        if isinstance(obj, dict):
            for k, v in obj.items():
                check(k, v, line); walk_json(v, line)
        elif isinstance(obj, list):
            for v in obj: walk_json(v, line)
    for node in ast.walk(tree):
        line = getattr(node, "lineno", None)
        if isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values):
                if isinstance(k, ast.Constant) and isinstance(v, ast.Constant):
                    check(k.value, v.value, line)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.lstrip()[:1] in "{[":
            try:
                walk_json(json.loads(node.value), line)
            except ValueError:
                pass

def _check_sql(sql: str, line) -> None:
    s = sql.strip().rstrip(";").strip()
    bare = _SQL_LIT.sub("''", s)
    if ";" in bare:
        raise CodePolicyError("multiple SQL statements are not allowed", line)
    if not re.match(r"(?is)^(select|with)\b", s):
        raise CodePolicyError("only SELECT/WITH SQL is allowed", line)
    m = SQL_FORBIDDEN_RE.search(bare)
    if m:
        raise CodePolicyError(f"SQL token '{m.group(0)}' is not allowed", line)

SAFE_BUILTIN_NAMES = ("abs all any bool bytes callable dict divmod enumerate filter float format frozenset hasattr "
    "hash int isinstance issubclass iter len list map max min next print range repr reversed round set slice sorted "
    "str sum tuple type zip None True False Ellipsis NotImplemented Exception BaseException ArithmeticError "
    "AttributeError KeyError IndexError LookupError NameError OSError FileNotFoundError PermissionError "
    "RuntimeError StopIteration TypeError ValueError ZeroDivisionError UnicodeDecodeError UnicodeEncodeError "
    "AssertionError NotImplementedError OverflowError").split()

def make_safe_builtins() -> dict:
    ns = {n: getattr(_b, n) for n in SAFE_BUILTIN_NAMES if hasattr(_b, n)}
    ns["__import__"] = _b.__import__   # X6: DuckDB .pl() imports polars through the frame's builtins
    return ns

def make_safe_os() -> types.SimpleNamespace:
    p = types.SimpleNamespace(**{n: getattr(os.path, n) for n in OS_PATH_OK if n != "sep"}, sep=os.sep)
    return types.SimpleNamespace(path=p, sep=os.sep)

class _StripOsImport(ast.NodeTransformer):
    """`import os` becomes `pass`: the exec globals already hold SafeOs. Every other allowed import stays a real statement."""
    def visit_Import(self, node):
        node.names = [a for a in node.names if a.name != "os"]
        return node if node.names else ast.copy_location(ast.Pass(), node)

def sandbox_code_filter(code: str, io_paths: Collection[str] | None = None) -> str:
    validate_generated_code(code, io_paths=io_paths)
    return ast.unparse(ast.fix_missing_locations(_StripOsImport().visit(ast.parse(code))))

def sandbox_globals() -> dict:
    import datetime as dt
    import duckdb, fastexcel, polars as pl
    from trigger_designer.core.utils.cleansing_util import DataCleansing, NullStrategy
    from trigger_designer.core.utils.dtype_utils import normalize_to_supported_dtypes
    return {"__builtins__": make_safe_builtins(), "pl": pl, "duckdb": duckdb, "fastexcel": fastexcel,
            "os": make_safe_os(), "datetime": dt.datetime, "timedelta": dt.timedelta,
            "normalize_to_supported_dtypes": normalize_to_supported_dtypes,
            "DataCleansing": DataCleansing, "NullStrategy": NullStrategy}
```

(`code_policy.py` imports polars/duckdb only inside `sandbox_globals`, so `validate_generated_code` stays cheap and Qt-free. **Re-verified after the cross-plan review** with exactly the code in S4 (only `import os` stripped, table + path-key scan): corpus 128 snippets / 0 refusals, 8 of 9 e2e cases byte-identical, attack table 32/32 refused, benign 7/7 pass, and 5 helper samples shaped like plans 01/04/06/07 generated code pass while 6 tampered variants (undeclared `filePath`/`output_path`, unknown shaping module, wrong name from an allowed module, `write_frame_xlsx` to an undeclared path, `from json import`) are refused. `test_future_node_imports_pass` keeps one sample per table row.)

**Executor hooks - provided by plan 09 F-B** (do not re-implement): `NodeExecutor.code_filter` (applied right after `get_code()`), `ExecutionResult.policy_violation` (set when the failing source exception has the class attribute `policy_violation = True`, which `CodePolicyError` carries), `before_run` hook list, defaulted `ExecutionResult` fields. Verify with
`Select-String -Path src\trigger_designer\core\ExecutionCheck\executor.py -Pattern "code_filter|policy_violation"`; if F-B has not landed, stop and report (no provisional copy).
The F7 bug (`node_name` assigned after `node.get_code()`) is fixed by plan 09 F-A; this plan edits no executor line. `CodePolicyError` is declared `class CodePolicyError(Exception): policy_violation = True` and exposes `.reason`; `executor.code_filter = ...` is assigned in `runner.py` (3.7 step 10), nothing else.

Done when: `pytest tests\unit\test_headless_code_policy.py tests\unit\test_executor_code_filter.py tests\unit\test_execution_result.py -q`
(the 32-row attack table, the benign table, `test_future_node_imports_pass`, the "every checked-in workflow validates" corpus test, executor F7 regression).

### S5 - Atomic outputs, lock, events, supervisor

```python
# core/headless/atomic.py
def write_json_atomic(path: Path, obj) -> None:
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_bytes(orjson.dumps(obj, option=orjson.OPT_INDENT_2)); os.replace(tmp, path)

@dataclass
class StagedOutput:
    node_id: int; final: str; staged: str; backup: str | None = None; cross_volume: bool = False

def plan_staging(finals: list[tuple[int, str]], run8: str, staging_root: Path) -> list[StagedOutput]:
    out = []
    for i, (nid, final) in enumerate(finals):
        d, name = os.path.split(final); stem, ext = os.path.splitext(name)
        if is_codegen_safe_dir(d):
            out.append(StagedOutput(nid, final, os.path.join(d, f".{stem}.tdtmp-{run8}{ext}")))
        else:
            out.append(StagedOutput(nid, final, str(staging_root / run8 / f"{i}{ext}"), cross_volume=True))
    return out

def commit_all(staged: list[StagedOutput]) -> None:
    done_a: list[StagedOutput] = []
    try:
        for s in staged:                                     # phase A: move old finals aside
            if os.path.exists(s.final):
                s.backup = f"{s.final}.tdbak-{uuid.uuid4().hex[:8]}"
                os.replace(s.final, s.backup)
            done_a.append(s)
        for s in staged:                                     # phase B: promote
            src = s.staged
            if s.cross_volume:
                src = os.path.join(os.path.dirname(s.final), f".{os.path.basename(s.final)}.tdtmp-copy")
                shutil.copyfile(s.staged, src)
            os.replace(src, s.final)
    except OSError as exc:
        _rollback(staged)
        raise CliError(ExitCode.COMMIT_FAILED, "TD-CLI-013", f"could not write {exc.filename or ''}: {exc}",
                       "Close the file in other programs (Excel keeps it locked) and run again.") from exc
    for s in staged:                                         # phase C: drop backups
        if s.backup: _silent_unlink(s.backup)
def discard_all(staged): ...   # unlink staged (+ cross-volume dir), ignore errors
def _rollback(staged): ...     # for s in staged: if s.backup and exists: os.replace(s.backup, s.final); unlink staged
```

* `locks.py` `RunLock(path, run_id)`: `acquire()`: `fd = os.open(path, O_CREAT|O_EXCL|O_WRONLY)`; write
  `{pid, create_time (psutil), run_id, started_at, host, staged: []}`. On `FileExistsError`: read; owner is **live** iff
  `psutil.pid_exists(pid)` and `abs(Process(pid).create_time() - create_time) < 1`; live -> `CliError(BUSY, "TD-CLI-012", ...)`;
  dead -> delete every path in `staged`, unlink the lock, retry once. `note_staged(paths)` rewrites the file (atomic). `release()` unlinks.
  Lock file name: `locks/<sha1(normcase(abspath(workflow)))[:16]>.lock`. (`psutil` imported inside the methods: X1.)
* `events.py`: `capture_stdout_channel()` does X9 and returns the private binary stream; `Emitter.emit` builds the dict
  (`ts` first), `orjson.dumps(..., option=OPT_NON_STR_KEYS)`, writes + flushes under a `threading.Lock`; text mode formats
  `f"{ts[11:19]} {level:<7} {event} " + " ".join(f"{k}={v}")` to stderr; `--log-file` rotates at 10 MB (3 backups) before opening.
  A loguru bridge: `logger.remove(); logger.add(lambda m: emitter.emit("log", level=m.record["level"].name, message=m.record["message"], source=m.record["name"]), level=<-v mapping>)`.
* `supervisor.py`:

```python
class Supervisor:
    def __init__(self, *, deadline_s, max_memory_mb, cancel_grace_s, emit, on_force):
        self.cancel = threading.Event(); self._signals = 0; self._t0 = time.monotonic(); self._cancel_at = None
        ...
    def install_signal_handlers(self) -> None:
        for name in ("SIGINT", "SIGBREAK", "SIGTERM"):
            if hasattr(signal, name): signal.signal(getattr(signal, name), self._on_signal)
    def _on_signal(self, signum, frame) -> None:      # runs on the main thread between bytecodes
        self._signals += 1; self.cancel.set()
        if self._cancel_at is None: self._cancel_at = time.monotonic(); self.emit("run.cancelling", level="WARNING")
        if self._signals >= 2: self.force_exit(ExitCode.CANCELLED, "cancel_forced")
    def start_watchdog(self) -> None:                  # daemon thread "td-watchdog", poll 0.25 s
        # timeout: now - t0 > deadline_s        -> force_exit(TIMEOUT, "timeout")
        # memory : rss_mb > max_memory_mb       -> force_exit(MEMORY, "memory")
        # cancel : now - _cancel_at > grace     -> force_exit(CANCELLED, "cancel_forced")
    def poll(self, runner: threading.Thread) -> None:  # main thread
        while runner.is_alive(): time.sleep(0.2)
    def force_exit(self, code: ExitCode, reason: str) -> None:
        if not self._forcing.acquire(blocking=False): return
        self.emit(f"run.{reason}" if reason != "cancel_forced" else "run.cancel_forced", level="ERROR")
        try: self.on_force(code, reason)               # snapshot record, discard staged, release lock, flush
        finally: os._exit(int(code))
```

Done when: `pytest tests\unit\test_headless_atomic.py tests\unit\test_headless_locks.py tests\unit\test_headless_events.py -q`.

### S6 - Headless Qt session; stop writing `check_output.py` into the CWD

`qt/headless.py` (new; the only module that imports Qt for the CLI):

```python
def ensure_app():
    os.environ["QT_QPA_PLATFORM"] = os.environ.get("TRIGGER_CLI_QPA", "offscreen")   # force, not setdefault
    from qtpy.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(["trigger-designer-cli"])
    app.setApplicationName("Trigger Designer"); return app

class _NullDialog:                                   # same stub tests/conftest.py:205-241 proves
    def __getattr__(self, _n): return lambda *a, **k: None
    def __enter__(self): return self
    def __exit__(self, *a): return False

@contextmanager
def suppress_ui():
    from trigger_designer.qt import design_window
    from trigger_designer.qt.helpers import eval_progress
    saved = (design_window.make_progress_dialog, eval_progress.make_progress_dialog, design_window.QMessageBox)
    class _Box:
        StandardButton = design_window.QMessageBox.StandardButton
        warning = information = critical = classmethod(lambda cls, *a, **k: None)
    design_window.make_progress_dialog = eval_progress.make_progress_dialog = lambda *a, **k: _NullDialog()
    design_window.QMessageBox = _Box
    try: yield
    finally: design_window.make_progress_dialog, eval_progress.make_progress_dialog, design_window.QMessageBox = saved

class HeadlessWindow(TriggerSubWindow):                # defined lazily inside a factory to keep imports local
    def log(self, level, message): self.messages.append((level, message))   # F11: no stdout prints
class HeadlessSession:
    def load(self, tds: str) -> LoadReport:
        with suppress_ui():
            ok = self.window.fileLoad(tds)
        nodes = self.window.topologicalSort(self.window.getNodeConnections()) if ok else []   # raises GraphCycleError (plan 09 F-E); the CLI maps it to TD-CLI-004 / INVALID
        unknown = [n for n in nodes if isinstance(n, TriggerNode_Unknown)]
        invalid = [n for n in nodes if n.isInvalid()]       # reported as warnings (3.7 step 9)
        return LoadReport(ok, nodes, unknown, invalid, self.window.validateLoadedWorkflow(), self.window.messages)
```

`getPyFile(nodes, path=None)`, the app-data `last_run/check_output.py` default, the absolute-`src` header and the `tests/conftest.py` stub widening are **plan 09 F-I** (same signature); this plan edits none of them. `--emit-script FILE` in the CLI calls `window.getPyFile(nodes, FILE)` and does nothing else for this bug.
Done when: `pytest tests\unit\test_getpyfile_location.py tests\unit\test_workflow_execution_mixin.py tests\e2e -q` (F-I's tests; CWD unchanged after a Run; e2e still 20 passed).

### S7 - Plan, runner, `run`, `--dry-run`

`plan.py::build_run_plan(args, doc, ctx) -> RunPlan` performs 3.7 steps 3-6 (pure, Qt-free, unit-testable) and returns
`RunPlan{doc, applied, staged, io_paths, work_copy_path, run_id, params_resolved, warnings}`; the work copy is written with
`json.dumps(applied.data, ensure_ascii=True)` (F10; ASCII survives any locale) to `<state>/work/<run_id>/workflow.tds`.
`runner.py`:

```python
def run_workflow_file(path, *, input_overrides=None, output_dir=None, record_dir=None, timeout_s=None, **opts) -> RunOutcome:
    ctx = opts.get("ctx") or make_default_context(opts)
    doc = read_workflow(path); plan = build_run_plan(Namespace(...), doc, ctx)     # may raise CliError
    if opts.get("dry_run"): return _dry_run(plan, ctx)
    lock = RunLock(...); lock.acquire(); lock.note_staged([s.staged for s in plan.staged])
    sup = Supervisor(deadline_s=timeout_s or None, max_memory_mb=opts.get("max_memory"), cancel_grace_s=opts.get("cancel_grace", 10),
                     emit=ctx.emitter.emit, on_force=lambda code, reason: _force_cleanup(state, code, reason))
    sup.install_signal_handlers(); sup.start_watchdog()
    from trigger_designer.qt.headless import HeadlessSession, ensure_app, execute_nodes     # first Qt import
    ensure_app(); session = HeadlessSession(); report = session.load(plan.work_copy_path)
    _gate_load_report(report, opts)                                                        # TD-CLI-003 / --strict
    executor = NodeExecutor(SecurityConfig(max_execution_time=(timeout_s + 5) if timeout_s else 1e9, max_memory_mb=1e9))
    executor.execution_context.clear(); executor.execution_context.update(sandbox_globals())
    executor.code_filter = lambda code: sandbox_code_filter(code, plan.io_paths)          # hook from plan 09 F-B
    specs, edges = node_specs_from_window(session.window, report.nodes)                    # plan 02 bridge (3.12)
    recorder = RunRecorder(RunStore(record_dir) if record_dir else None, AuditOptions(store_dir=record_dir or "", enabled=True, hash_inputs=not opts.get("no_hash"), hash_outputs=not opts.get("no_hash")))
    record = recorder.begin(path, specs, app_version=VERSION, edges=edges, workflow_uuid=session.window.scene.workflow_uuid)   # ORIGINAL path (sha of original bytes); uuid = plan 09 F-F
    executor.before_node, executor.after_node = recorder.before_node, recorder.after_node
    _run_before_run_hooks(report.nodes, ctx)                                               # content.before_run(), exceptions -> warning events
    connections = session.window.getNodeConnections()
    upstream = {n: connections[n]["inputs"] for n in report.nodes}                         # same map the GUI passes (plan 09 F-C/F-E)
    result: dict = {}
    def target():
        try: result["loop"] = execute_nodes(report.nodes, executor, cancel=sup.cancel, on_event=ctx.emitter.emit, recorder=recorder, record=record, keep_going=opts.get("keep_going", False), upstream=upstream)
        except BaseException as exc: result["exc"] = exc                                  # reported as INTERNAL
    t = threading.Thread(target=target, daemon=True, name="td-runner"); t.start(); sup.poll(t)
    return _finish(plan, ctx, recorder, record, result, lock, session)                  # commit -> enrich -> finish ONCE -> sidecars
```

`execute_nodes` (in `qt/headless.py`) is a thin adapter over **plan 09 F-C's shared Qt-free run loop**, `core/ExecutionCheck/run_loop.py::run_nodes(nodes, executor, *, continue_on_error, upstream, cancel, on_node_started, on_node_finished, on_node_errored, on_node_skipped) -> RunOutcome`.
Semantics come from F-C, not from this plan: cancel event checked between nodes; stop at the first failure unless `continue_on_error` (`--keep-going`); with it a failed node's **descendants are skipped** (via `on_node_skipped`, recorded
`skipped`) while independent branches still run. `upstream` is `{n: connections[n]["inputs"] for n in report.nodes}` from `session.window.getNodeConnections()`. Callback signatures: `on_node_started(node)`, `on_node_finished(node, result)`, `on_node_errored(node, exc)`, `on_node_skipped(node, blocker)`
(`blocker is None` = cancelled). Exceptions raised by callbacks propagate out of `run_nodes` (F-C rule 5), which is how `CliError` for a policy violation leaves the loop. The CLI does not keep its own copy of the loop.

```python
def execute_nodes(nodes, executor, *, cancel, on_event, recorder, record, keep_going, upstream=None):
    index_of = {n: i for i, n in enumerate(nodes)}                 # run_nodes passes only the node
    def started(node):
        on_event("node.started", node_id=node.id, title=node.node_title, op=op_of(node), index=index_of[node], total=len(nodes))
        _test_hooks(node)                                          # TD_TEST_HOOKS only (section 6.2)
    def skipped(node, blocker):
        on_event("node.skipped", node_id=node.id, title=node.node_title, blocker=getattr(blocker, "id", None))                                                                   # recorder.finish marks every unrun node `skipped` (plan 02); no recorder call here
    def finished(node, result):
        if result.policy_violation: raise CliError(ExitCode.REFUSED, "TD-CLI-010", result.error, "The workflow was refused by the safety policy.")
        nr = recorder.node_finished(record, node, result)
        on_event("node.finished", node_id=node.id, title=node.node_title, status="ok" if result.success else "failed",
                 duration_s=round(result.execution_time, 3), error=_err(nr))
    return run_nodes(nodes, executor, continue_on_error=keep_going, upstream=upstream, cancel=cancel,
                     on_node_started=started, on_node_finished=finished, on_node_skipped=skipped)   # -> run_loop.RunOutcome = LoopOutcome (success, cancelled, executed, failed, skipped)
```

`_finish` (order matters, 3.12): (1) map the `LoopOutcome` (`success`/`cancelled`/`failed`/`skipped`) to `ExitCode` with the 3.4 precedence; (2) if no cancel/failure-without-keep-going, `commit_all(plan.staged)` (-> 8; with `--keep-going`
only the staged outputs of File Output nodes that succeeded are committed); (3) fingerprint the committed **final** files (hash unless `--no-hash`); (4) for the first failed node call plan 03
`enrich_error(...)` (3.12 rule 7); (5) `final = recorder.finish(record, ok, cancelled=cancelled, outputs=fingerprints, save=not no_record)` - once, guarded by `_finish_once`, never
`dataclasses.replace`; (6) write `<run_id>.json.sha256` (`"<hex>  <name>\n"`, over `recorder.last_path`) and `<run_id>.cli.json` (`argv`, `params_resolved`, `exit_code`, `trigger`, `approval_sha256`,
`host`, `staged`) through `write_json_atomic`; (7) emit `run.finished`; `discard_all` leftovers; `lock.release()`; delete the work copy; return `RunOutcome`.
`commands/run.py` wires args -> `run_workflow_file`, then `emitter.close(); os._exit(outcome.exit_code)` (3.7 step 12). `validate --deep` reuses
`build_run_plan` + `HeadlessSession.load` + policy validation of every `get_code()`; `--dry-run` is the same code path with `dry_run=True`.
`--emit-script` and the work-copy cleanup happen in `_finish`/`_dry_run`.

Done when: `pytest tests\e2e\test_cli_run.py tests\unit\test_headless_plan.py -q` (section 6) and manually
`.venv\Scripts\trigger-designer-cli.exe run tests\e2e\workflows\formula-category.tds --input-dir data --output-dir $env:TEMP\td-out --allow-unapproved --log-format json`
prints JSON lines only on stdout and exits 0 (create `$env:TEMP\td-out` first; the input is `data\check.csv`, whose basename matches the workflow's saved `check.csv`).

### S8 - Records (plans 02/03) and `verify-log`

Recorder wiring is exactly 3.12 (plan 02's API: `RunRecorder(RunStore, AuditOptions)`, `audit_bridge.node_specs_from_window`, executor `before_node/after_node`, one `finish(..., cancelled=, outputs=, save=)`);
nothing else from plan 02 is used and no `RunRecord` field is added. Record directory: `--record-dir` (passed as `AuditOptions.store_dir` and to `RunStore`), else plan 02's default
(`<app_data_dir>/runs`, the same folder the GUI uses so the Run-log dock shows CLI runs). `verify.py::verify_record(path, *, workflow, check_files)` returns
`Finding`s for V1..V6 (section 6.4); `commands/verify_log.py` prints and exits 0/10; with no argument
it verifies the newest `*.json` (excluding `*.cli.json`) in the default folder; with a directory it verifies all.
Done when: `pytest tests\unit\test_headless_verify.py tests\e2e\test_cli_parity.py -q`.

### S9 - GUI Cancel button: owned by plan 09 F-D (no work in this plan)

The Cancel button, `icon_stop`/`stop.svg`, `_show_run_controls`, `request_run_cancel()` (the only cancel entry; there is no `cancelWorkflow`), `WorkflowWorker.cancelled`, `tests/unit/test_workflow_cancel.py` and `tests/ui/test_cancel_button.py` are all created by plan 09 F-D. This plan keeps only its CLI cancel behaviour (3.7: `Supervisor.cancel` passed as `cancel=` to `run_nodes`; tests in section 6.5). Verify `request_run_cancel` exists on `TriggerSubWindow`; if not, F-D has not landed: stop and report.
Done when: F-D's `tests\unit\test_workflow_cancel.py tests\ui\test_cancel_button.py` and the existing `tests\ui\test_canvas_buttons.py tests\unit\test_workflow_execution_mixin.py` pass (no new failures beyond the brief's 27 baseline).

### S10 - Scheduling

`schedule.py` implements 3.10: `ScheduleSpec` dataclass, `parse_trigger`, `build_command(spec) -> list[str]`, `build_task_xml(spec) -> str`,
`_run_schtasks(argv)` (the only `subprocess.run([...], capture_output=True, text=True, timeout=60)`), `create/delete/query`, `parse_query_csv(text)` (by position,
`csv.reader`; skips rows whose `TaskName` does not start with `\TriggerDesigner\`; `Last Result` -> `int` when numeric). `commands/schedule.py`:
`add` = validate name -> read workflow -> require approval (exit 6) -> absolute-ize paths -> write JSON + XML (UTF-16) -> print command -> unless `--print-only`
call create (exit 9 on non-zero, including stderr) ; `list`/`show` merge JSON definitions with `parse_query_csv`; `remove` deletes task then files
(missing task is a warning, not an error). On non-Windows return exit 9 with the sentence in 3.10.
Done when: `pytest tests\unit\test_headless_schedule.py -q` (schtasks mocked). Manual (Windows, not automated; documented in section 7): create a task
named `selftest` with `--once <now+2min>`, `schtasks /Run /TN "TriggerDesigner\selftest"`, check the run record appears, `schedule remove selftest`.

### S11 - Packaging

1. `src/trigger_designer/cli_entry.py`: `import sys\nfrom trigger_designer.cli import main\nif __name__ == "__main__":\n    sys.exit(main())`.
2. `trigger.spec` (re-read; plan 09 F-G has done the shared base pass - node hidden imports incl. `core.shaping.*`, `xlsxwriter`, `core.excel`, `core.workpaper`; you add **only** the CLI second `Analysis`/`MERGE` restructure below and the entry point; do not touch hiddenimports). After the existing `analysis = Analysis(...)` add a second analysis that
   reuses the same node hidden imports/datas:

```python
cli_analysis = Analysis(
    ["src/trigger_designer/cli_entry.py"], pathex=[], binaries=[],
    datas=list(analysis.datas), hiddenimports=list(analysis.hiddenimports) + ["trigger_designer.qt.headless"],
    hookspath=[], hooksconfig={}, excludes=list(analysis.excludes), runtime_hooks=[], noarchive=False, optimize=1,
)
MERGE((analysis, "TriggerEditor", "TriggerEditor"), (cli_analysis, "trigger-designer-cli", "trigger-designer-cli"))
cli_pyz = PYZ(cli_analysis.pure)
cli_exe = EXE(cli_pyz, cli_analysis.scripts, [], bootloader_ignore_signals=False, console=True,
              debug=False, strip=False, upx=False, name="trigger-designer-cli", icon=icon_path,
              exclude_binaries=True, argv_emulation=False, target_arch=None)
```

   `MERGE(...)` must come **before** `PYZ(analysis.pure)`/`EXE(...)` of the GUI (move the existing `pyz = PYZ(analysis.pure)` line below it). Then
   change the collection: `COLLECT(executable, cli_exe, analysis.binaries + cli_analysis.binaries, analysis.datas + cli_analysis.datas, name=app_name, ...)`
   (the `--portable` branch keeps the GUI-only behaviour: the CLI is not part of the portable single-file build; print a warning in that branch).
   Size expectation: MERGE shares binaries, so `trigger-designer-cli.exe` adds ~3-6 MB to the 441 MB `dist\TriggerEditor`.
   **Fallback if MERGE misbehaves** (decided): drop `MERGE`, build the CLI as its own `COLLECT(name="trigger-designer-cli")` into
   `dist\trigger-designer-cli\` (+~400 MB) and have the installer copy that folder to `{app}\cli`.
3. `scripts/build.bat`: after the "Verify bundle assets" block add:

```bat
if not exist "dist\TriggerEditor\trigger-designer-cli.exe" (
    echo Build failed: dist\TriggerEditor\trigger-designer-cli.exe missing.
    exit /b 1
)
"dist\TriggerEditor\trigger-designer-cli.exe" --version
if %ERRORLEVEL% NEQ 0 ( echo Build failed: CLI does not start. & exit /b 1 )
"dist\TriggerEditor\trigger-designer-cli.exe" validate "savedfiles\0. All Node- Test.tds" --deep --no-files
if %ERRORLEVEL% NEQ 0 ( echo Build failed: CLI deep validation of the sample workflow failed. & exit /b 1 )
```
4. `savedfiles/TriggerDesigner_Setup.iss`: in `[Files]` add `Source: "..\dist\TriggerEditor\trigger-designer-cli.exe"; DestDir: "{app}"; Flags: ignoreversion`;
   in `[Tasks]` add `Name: "addtopath"; Description: "Add trigger-designer-cli to PATH"; GroupDescription: "Command line:"; Flags: unchecked`;
   in `[Registry]` add `Root: HKA; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}"; Tasks: addtopath; Check: NeedsAddPath('{app}')`;
   append a `[Code]` section with `function NeedsAddPath(Param: string): boolean;` (reads `HKCU\Environment\Path` with `RegQueryStringValue`, returns `Pos(';' + Param + ';', ';' + OrigPath + ';') = 0`).
   `PrivilegesRequiredOverridesAllowed=dialog` already lets per-user installs use `HKA`.
Done when: `scripts\build.bat` completes and prints the CLI version; `dist\TriggerEditor\trigger-designer-cli.exe run <materialized fixture> --allow-unapproved` exits 0 on a clean machine path (no Python installed - verify in a Windows Sandbox/VM if available; otherwise state "not verified" in the PR).

### S12 - Docs

Create `docs/CLI.md` from Appendix A (runbook + exit codes + schedule how-to) and add a three-line "Headless" pointer to `README.md`. Update
`docs/ENHANCED_EXECUTOR_GUIDE.md` with one sentence: "The allowlist described here exists only in the CLI (`core/headless/code_policy.py`)". No other doc edits.

---

## 5. Edge cases (each has a test in section 6; "Decision" is the specified behaviour)

| Case | Decision |
|---|---|
| Input file missing | Exit 2, `TD-IN-001`; **all** missing inputs listed in one event; nothing staged, no lock taken, no outputs touched. `--dry-run` reports the same. |
| Output file locked (Excel has it open) | Nodes run into the staged file; commit phase A fails on `os.replace` of the old file -> rollback -> exit 8 `TD-CLI-013`, hint "close the file in other programs"; previous output unchanged. |
| Output folder missing | Exit 2 `TD-CLI-014` unless `--create-output-dirs`. Two File Output nodes resolving to the same final path, or an output equal to an input path -> exit 2 `TD-CLI-014` ("would overwrite"). |
| Spaces / unicode in paths | Supported everywhere (argv is a list; XML escaped; `list2cmdline` quoting). Work copy is ASCII-escaped JSON so the GUI loader's locale decoding cannot corrupt them (F10). |
| `'`, `"`, `{`, `}` in an **output** directory | Generated File Output code embeds the path in an f-string (`file_output.py:341`) and breaks; the CLI stages such outputs under `<state>/staging/<run8>/` and copies at commit (3.8). Input paths use `repr` and are safe. |
| `.tds` saved in another locale (cp1252 `é`) / UTF-8 | Reader tries UTF-8, locale, cp1252 (F10); `info` shows `encoding`. Undecodable -> exit 2 `TD-CLI-001`. |
| Workflow from a newer schema (`schema_version > 2`) | Exit 2 `TD-CLI-002`, message "saved by a newer Trigger Designer (schema N); update this program". Newer `app_version` with a supported schema -> warning only. |
| Unresolvable / unknown node op | Static: exit 2 `TD-CLI-003` naming the op and node title. `--deep`: `TriggerNode_Unknown` after load -> same. v1 nodes (no `op`) resolve through `migrate_v1_data` at load; a v1 node that cannot -> exit 2. |
| Cycle | Exit 2 `TD-CLI-004` (static, before any Qt). |
| Parameter errors | Unknown name -> `TD-CLI-005` listing known names; bad int/path -> `TD-CLI-006`; target not in the safe set or filter in expression mode -> `TD-CLI-007`; missing required -> `TD-CLI-005`. All exit 2, before any file is touched. |
| Concurrent runs of the same workflow | Second exits 7 `TD-CLI-012` (lock). Different workflows run in parallel (separate locks). Scheduler also has `IgnoreNew`. |
| Killed mid-run (TerminateProcess, power loss) | Final outputs untouched (staged-only writes). Stale `.tdtmp-*` files remain until the next run of that workflow finds the dead lock and deletes **exactly** the paths recorded in it. A killed run writes no record; `verify-log` is unaffected. |
| Low disk | Preflight: free space of each output volume `< --min-free-mb` (default 64) -> exit 2 `TD-CLI-015`. Mid-run `OSError` from a writer is an ordinary node failure (exit 1, plan-03 `TD-OUT-*`), staged files deleted. Commit-time `ENOSPC` -> exit 8, rolled back. |
| Scheduler with no desktop session | `InteractiveToken` tasks do not run when nobody is logged on (documented); `--run-whether-logged-on` uses S4U: runs without a session, no network credentials. `QT_QPA_PLATFORM=offscreen` needs no display either way. |
| UTC vs local time | Records, logs and events are UTC (`...Z`); schedule triggers and `schedule list` "next run" strings are the machine's local time as printed by Windows (not parsed, X10). |
| Graph has no File Output | Run would compute nothing (brief fact 2: lazy plans are never collected). `validate`/`run` emit warning `TD-CLI-018` "this workflow writes no files"; `--strict` -> exit 2. |
| Unwired node left on the canvas | Not an error without `--strict` (the GUI runs it with fallback code; record counts must match). |
| Excel output without `xlsxwriter` | Node failure (plan 06 fixes the dependency); exit 1 with the node's `NodeError`. Not special-cased here. |
| Graph (chart) node headless | `after_execution` emits a Qt signal with no receiver event loop: harmless; no window is created (offscreen). |
| `--timeout` while Polars streams | Process exit (`os._exit(4)`) is the cancel; staged files are orphaned and swept next run; finals untouched. |
| stdout is a closed pipe | `Emitter` swallows `BrokenPipeError`/`OSError` on the stdout channel after the first failure and keeps going (the record and exit code still matter). |
| Run from another working directory | Relative workflow paths resolve against the `.tds` folder; `--param` relative paths against the CWD; nothing is written to the CWD (S6). |

---

## 6. Test plan

Layers: `tests/unit` (no subprocess unless noted), `tests/e2e` (real CLI subprocess against `tests/e2e/workflows` + `savedfiles`, using
`tests/support/workflows.materialize`), `tests/ui` (offscreen widgets). Shared helper to add: `tests/support/cli.py`:

```python
def run_cli(*args, cwd, extra_env=None, timeout=180, input=None):   # python -m trigger_designer.cli ...
    env = {**os.environ, "PYTHONPATH": str(SRC), "PYTHONIOENCODING": "utf-8",
           "TRIGGER_DESIGNER_DATA_DIR": str(cwd / "data"), "TRIGGER_DESIGNER_STATE_DIR": str(cwd / "state"), **(extra_env or {})}
    env.pop("QT_QPA_PLATFORM", None)          # the CLI must set it itself
    return subprocess.run([sys.executable, "-m", "trigger_designer.cli", *map(str, args)], cwd=cwd, env=env,
                          capture_output=True, text=True, encoding="utf-8", timeout=timeout, input=input)
def events(proc) -> list[dict]:               # every non-empty stdout line must be a JSON object
    return [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]
```

Test-only hooks (read **only** when `TD_TEST_HOOKS=1` and `not sys.frozen`; implemented in `qt/headless.py::_test_hooks`):
`TD_TEST_SLEEP_BEFORE_NODE="<title>:<seconds>"` (sleep on the runner thread right before that node executes),
`TD_TEST_FAIL_NODE="<title>"` (replace that node's `get_code` by `raise ValueError('boom')`), `TD_TEST_ALLOC_MB="<title>:<n>"`.

### 6.1 Unit tests (name -> assertions)

| File | Tests (name -> assertion) |
|---|---|
| `test_cli_parser.py` | `test_version_flag` -> stdout `trigger-designer-cli 0.1.0 (workflow schema 2)`, exit 0; `test_usage_error_exits_64` (`run` with no workflow) -> `SystemExit.code == 64`; `test_abbreviations_rejected` (`--dry`) -> 64; `test_param_split_first_equals` -> `{"a": "b=c"}`; `test_every_command_has_examples` -> `--help` of each command exits 0 and contains `Example`; `test_defaults` -> timeout 3600, cancel_grace 10, min_free_mb 64, log_format text. |
| `test_headless_workflow_file.py` | `test_reads_utf8`, `test_reads_cp1252_bytes` (`"Caf\xe9".encode("cp1252")` -> `encoding == "cp1252"`), `test_not_json_is_td_cli_001`, `test_newer_schema_td_cli_002`, `test_unknown_op_td_cli_003`, `test_cycle_td_cli_004` (graph built as JSON with socket ids), `test_v1_node_without_op_is_warning_only`, `test_big_ids_exact` (id `2176004824160` survives), `test_no_file_output_warns_td_cli_018`. |
| `test_op_catalog_matches_registry.py` | `test_catalog_equals_registry`: with `registered` = ops computed from `NODE_REGISTRIES` + `_OPCODE_ENUMS`: (1) `registered <= set(OPS)` (a node without a row fails; message tells the author to edit `core/headless/op_catalog.py`); (2) every `OPS` row not in `registered` has `planned=True` (skip-unregistered flag: rows for nodes of plans 01-07 that have not landed yet are allowed); (3) `test_planned_rows_resolved` is skipped while any planned row is unregistered, and once all plans have landed asserts that no row still has `planned=True` and `set(OPS) == registered` (so the state after all plans land passes with exact equality). |
| `test_cli_import_discipline.py` | subprocess `python -c "import sys; from trigger_designer.cli import main; rc = main([...]); assert not any(m.startswith(('PyQt6','qtpy','polars','duckdb')) for m in sys.modules) and 'trigger_designer.main' not in sys.modules"` for `--version`, `info`, static `validate`, `approve --list`, `params list`, `paths`, `schedule list`; for `verify-log` only PyQt6/qtpy are asserted absent. |
| `test_headless_paths.py` | table over `resolve_workflow_path` (relative, `..`, absolute, drive-on-POSIX [skip nt], URL -> `TD-CLI-006`, empty -> `TD-IN-001`, NUL, backslash-relative on POSIX [skip nt], unicode+space, UNC); `remap_into_dir` with `\` and `/` and trailing slash; `relativize` (inside, outside, other drive, case on nt); `is_codegen_safe_dir` for each forbidden char. |
| `test_headless_params.py` | `test_unknown_param_lists_names`, `test_int_type_error_has_example`, `test_target_outside_safe_set_td_cli_007`, `test_filter_expression_mode_refused`, `test_forbidden_chars_in_sheet_and_value`, `test_precedence_param_over_dir_over_default_over_saved`, `test_dir_remap_applies_to_unbound_nodes_only`, `test_original_document_not_mutated`, `test_work_copy_is_ascii_json` (`"\u00e9"` escaped), `test_required_missing`, `test_duplicate_param_names`, `test_params_add_writes_backup_and_block`, `test_file_path_override_deletes_file_path_rel` (stale `filePathRel` must not win), `test_folder_glob_and_include_patterns_bindable`, `test_db_query_not_bindable`. |
| `test_headless_approvals.py` | add/lookup/revoke; changed bytes -> not approved + `changed since approval` text in `info`; unknown store version -> INVALID; no temp file left after write; `approve` non-TTY without `--yes` -> 64; with `--yes` -> entry has `reads`/`writes`. |
| `test_headless_code_policy.py` | `test_attack_table` (6.3, 32 params -> `CodePolicyError`, `reason` contains the listed substring); `test_benign_table` (7 params pass); `test_future_node_imports_pass` (one generated-code sample per row of `GENERATED_IMPORTS`/prefix table: plans 01, 04, 05, 06, 07 shapes; plus the 6 tampered variants refused); `test_corpus_passes_policy` (every `savedfiles/*.tds` + `tests/e2e/workflows/*.tds` loaded via `TriggerSubWindow`, every node's `get_code()` validated with `io_paths=None`, zero refusals - X4); `test_sandbox_globals_contract` (`"open"/"eval"/"exec"/"getattr"` absent from builtins, `"__import__"` present, `not hasattr(g["os"], "system")`); `test_import_statements_are_stripped` (`"import" not in sandbox_code_filter(code)`); `test_undeclared_path_refused_declared_allowed`; `test_dunder_and_unicode_obfuscation` (e.g. `x = ().__class__`). |
| `test_executor_code_filter.py` (integration with plan 09 F-B's hooks) | `test_get_code_raising_does_not_unbound_error` (fake node, F7) -> `result.success is False`, message contains the exception; `test_code_filter_policy_error_marks_violation`; `test_default_filter_none_unchanged` (an existing simple node still executes). |
| `test_headless_atomic.py` | `test_plan_staging_safe_dir_same_dir_same_ext`; `test_plan_staging_unsafe_dir_uses_state_staging` (parametrize `'`, `"`, `{`, `}`); `test_commit_replaces_and_drops_backups`; `test_commit_rolls_back_when_second_replace_fails` (monkeypatch `os.replace` raising `PermissionError` on call 3) -> first file content restored, staged gone, `CliError.code == COMMIT_FAILED`; `test_commit_locked_first_file_changes_nothing`; `test_write_json_atomic_leaves_no_tmp_on_error`. |
| `test_headless_locks.py` | second `acquire` -> `CliError(BUSY)`; stale lock with dead pid -> acquired and the recorded staged files deleted; lock whose pid is alive but `create_time` differs -> treated as stale; `release` removes the file; lock name stable for the same path with different case on nt. |
| `test_headless_events.py` | JSON mode: each line parses, keys `ts/level/event/run_id` present, `ts` matches `^\d{4}-\d\d-\d\dT[\d:.]+Z$`; text mode writes only to stderr; unicode round-trip; rotation (`max_bytes=1000` param) keeps `.1..3`; `BrokenPipeError` on the channel does not raise. |
| `test_headless_plan.py` | all missing inputs reported together; outputs staged; output dir missing -> `TD-CLI-014`; `--create-output-dirs` creates; duplicate finals / output==input -> `TD-CLI-014`; low disk (monkeypatch `shutil.disk_usage`) -> `TD-CLI-015`; unapproved -> REFUSED; custom-code op (monkeypatch `OPS`) -> REFUSED unless flag **and** approved; `--trigger schedule` ignores `--allow-unapproved`; work copy lives under `<state>/work/<run_id>/`. |
| `test_headless_schedule.py` | see 6.5. |
| `test_headless_verify.py` | see 6.4. |
| `test_scene_metadata_roundtrip.py` | (relies on plan 09 F-F carry-forward) scene deserialised with `workflow_metadata.parameters` -> `serialize()["workflow_metadata"]["parameters"]` equal; `saved_at` refreshed; `schema_version` = constant. |

### 6.2 End-to-end tests (real subprocess; `tests/e2e/test_cli_run.py`, `test_cli_signals.py`, `test_cli_parity.py`)

All use `materialize(case, tmp)`, then `run_cli("run", m.path, "--allow-unapproved", "--log-format", "json", "--record-dir", tmp/"rec", cwd=tmp)` unless stated.

| Test | Assertions |
|---|---|
| `test_run_matches_goldens[case]` (parametrize `FILE_OUTPUT_CASES`) | exit 0; each produced file passes `assert_frame_golden` (same helpers/goldens as the GUI e2e; `unordered_goldens` honoured); `os.listdir(m.out_dir)` has no `.tdtmp`/`.tdbak`; `os.listdir(cwd)` has no `check_output.py`. |
| `test_stdout_is_only_json_lines` | `events(proc)` parses fully; first `run.started`, last `run.finished` with `exit_code == 0` and an existing `record_path`; count of `node.finished` == node count; `proc.stderr` contains no JSON. |
| `test_missing_input_exit_2` | input deleted -> 2; last event `status == "invalid"`; `errors[0].code == "TD-IN-001"`; out dir empty; lock file absent. |
| `test_unapproved_exit_6_then_approve_then_run` | no flag -> 6 (`TD-CLI-008`); `approve --yes` -> 0; run -> 0; edit one byte of the `.tds` -> 6 again. |
| `test_node_failure_exit_1_keeps_previous_output` | pre-create the output with sentinel bytes; `TD_TEST_HOOKS=1 TD_TEST_FAIL_NODE=Formula` -> 1; output bytes unchanged; no temps; `node.finished` for Formula has `status failed` and non-empty `error.title`; record status `failed`. |
| `test_keep_going_runs_independent_branches` | `TD_TEST_FAIL_NODE` on one branch of a two-output workflow, `--keep-going` -> exit 1; the other branch's File Output is committed, the failed branch's output absent/unchanged; failed node's descendants recorded `skipped`; without the flag the run stops at the first failure. |
| `test_before_run_hooks_called_and_failures_are_warnings` | a stub content with `before_run` (via `TD_TEST_HOOKS` marker node title) is called once before the first node; a raising hook yields a `warning` event and the run still exits 0. |
| `test_failed_node_has_enriched_plain_language_error` | failing node -> `run.finished.errors[0]` has `code`, non-empty `title` and `hint` (plan 03 `enrich_error` ran; never raises, bounded). |
| `test_record_written_once_and_loads` | exactly one `<run_id>.json` per run (also after cancel/timeout paths), `RunStore.load` works, `status` is `ok/failed/cancelled`, outputs fingerprints point at the final paths, `--no-record` -> no file but `run.finished.record_path` is null. |
| `test_dry_run_executes_nothing` | exit 0; `plan.resolved` event present; no output files, no record file; with a missing input -> 2; with the X3 delimiter payload -> 6 and no `PWNED.txt`. |
| `test_x3_payload_refused_when_running` | same payload without `--dry-run` -> exit 6 `TD-CLI-010`, no `PWNED.txt`, previous output untouched. |
| `test_param_overrides_and_remap` | `params add` binds File Input path + File Output path; `--param` overrides give output at the new path; `--input-dir`/`--output-dir` alone remap a workflow whose saved paths are `C:/Projects/...` (basename match); precedence per 3.5 asserted through `plan.resolved`. |
| `test_relative_paths_resolve_against_workflow_dir` | copy workflow + input into `tmp/wf`, `paths --relativize --write`, run with `cwd=tmp/other` -> 0 and output beside the workflow; `.bak` exists. |
| `test_unicode_space_and_apostrophe_paths` | input folder `r\xe9sum\xe9 data`, output folder `O'Brien out` (forces cross-volume staging) -> 0; output content equals golden. |
| `test_cp1252_workflow_runs` | rewrite the `.tds` as cp1252 with `é` in `label_text`; run -> 0 (`info` reports `encoding: cp1252`). |
| `test_newer_schema_unknown_op_cycle_exit_2` | three JSON edits -> 2 with `TD-CLI-002/003/004`. |
| `test_concurrent_run_exit_7` | run A with `TD_TEST_SLEEP_BEFORE_NODE=Formula:8` (Popen), wait for its first `node.started`, run B -> 7; A -> 0. |
| `test_killed_run_leaves_no_partial_output` | Popen with `TD_TEST_SLEEP_BEFORE_NODE="File Output:30"`; read stdout until `node.started` of File Output; `proc.kill()`; final output absent; then a normal run -> 0 and no `.tdtmp-*` remains (swept via stale lock). |
| `test_ctrl_break_force_exits_130` (`test_cli_signals.py`) | Popen(`creationflags=CREATE_NEW_PROCESS_GROUP` on nt) with `--cancel-grace 2` and a 30 s hook sleep; send `CTRL_BREAK_EVENT` (POSIX: `SIGINT`) after `run.started`; exit 130 within 8 s; events contain `run.cancelling` then `run.cancel_forced`; record status `cancelled`; out dir empty. |
| `test_ctrl_break_graceful_between_nodes` | hook sleep 1.5 s before the 2nd node, signal at 0.5 s -> exit 130 without `run.cancel_forced`; the first node's `node.finished` present; no commit. |
| `test_second_signal_forces_immediately` | two signals 0.3 s apart with a 30 s hook -> exit 130 in < 5 s. |
| `test_timeout_exit_4` | `--timeout 3`, 30 s hook -> exit 4 in < 10 s; `run.timeout` event; record's failing node error `TD-RUN-001`; no commit. |
| `test_max_memory_exit_5` | `--max-memory 64` -> exit 5, `run.memory_exceeded`; `--max-memory 8192` on the same workflow -> 0. |
| `test_no_window_is_created` | `python -c` using `run_workflow_file` then printing `QGuiApplication.platformName()` -> `offscreen`; `"trigger_designer.main" not in sys.modules`. |
| `test_gui_and_cli_parity[case]` (`test_cli_parity.py`; all cases except hash-join ones) | GUI: `window.fileLoad`, `run_workflow_and_wait` on `materialize(A)`; CLI on `materialize(B)`; per produced file `sha256(A) == sha256(B)` (X5); `RunStore.load` of both records: `len(nodes)`, `[n.op]`, `[n.status]`, `[n.rows_out]` (where not `None`), count of input/output fingerprints and their `sha256` are equal; `run_id`, times, user ignored. Join cases compare frames after sorting every column. |

### 6.3 Malicious generated-code table (`test_attack_table`; run with `io_paths=["C:/data/in.csv", "C:/data/.out.tdtmp-ab12cd34.csv"]`; all verified refused in X7)

| Id | Snippet (abridged) | `reason` contains |
|---|---|---|
| M01 | `x = __import__('os').system('calc')` | `not allowed` |
| M02 | `import subprocess; subprocess.run([...])` | `import of 'subprocess'` |
| M03 | `import os; os.system('calc')` | `.system` |
| M04 | `open('C:/Windows/win.ini').read()` | `name 'open'` |
| M05 | `eval('1+1')` | `name 'eval'` |
| M06 | `exec('import os')` | `name 'exec'` |
| M07 | `getattr(pl, 'os')` | `name 'getattr'` |
| M08 | `().__class__.__bases__[0].__subclasses__()` | `__subclasses__` (BFS may report `__class__`/`__bases__` first: assert `not allowed`) |
| M09 | `(lambda: 0).__globals__` | `__globals__` |
| M10 | `pl.scan_csv('C:/Users/victim/secrets.csv')` | `undeclared path` |
| M11 | `pl.DataFrame({'a':[1]}).write_csv('C:/Users/victim/Startup/x.csv')` | `undeclared path` |
| M12 | `p = 'C:/data/' + 'in.csv'; pl.scan_csv(p)` | `needs a literal file path` |
| M13 | `d.execute("COPY (SELECT 1) TO 'C:/x.csv'")` | `only SELECT/WITH` |
| M14 | `d.execute("SELECT * FROM read_csv('C:/secret.csv')")` | `read_csv` |
| M15 | `d.execute("ATTACH 'x.db'")` | `only SELECT/WITH` |
| M16 | `duckdb.connect('C:/x.db')` | `':memory:'` |
| M17 | `d.execute('SELECT 1; DROP TABLE t')` | `multiple SQL statements` |
| M18 | `q = 'SEL'+'ECT 1'; d.execute(q)` | `string literal` |
| M19 | `class A: pass` | `ClassDef` |
| M20 | `with open('x') as f: pass` | `With is not allowed` |
| M21 | `def f(): global x` | `Global` |
| M22 | `import requests` | `import of 'requests'` |
| M23 | `from os import system` | `from os import` |
| M24 | `pl.plugins.register_plugin_function(...)` | `not allowed` |
| M25 | `pl.col('a').map_elements(lambda v: open('x').read())` | `name 'open'` |
| M26 | `x = (y := breakpoint())` | `NamedExpr` |
| M27 | `@f def g(): pass` | `decorators` |
| M28 | `import os; os.environ['PATH']` | `.environ` |
| M29 | `os.path.unlink('x')` | `.unlink` |
| M30 | `x = (` | `syntax error` |
| M31 | `pl.read_database('select 1', 'sqlite:///x.db')` | `not allowed`/`undeclared` (assert `CodePolicyError` only) |
| M32 | `async def f(): pass` | `AsyncFunctionDef` |

Benign (must pass, `test_benign_table`): `pl.scan_csv('C:\\data\\in.csv', infer_schema=False)`; `LazyFrame().sink_csv('C:/data/.out.tdtmp-ab12cd34.csv')`;
`d.execute('WITH a AS (SELECT 1 AS "set") SELECT * FROM a').pl()`; `x = 1; del x`; the `_ensure_lazyframe` helper from Join (`def`, `isinstance`, `raise TypeError(f'..{type(d)}')`);
`os.path.basename('C:/data/in.csv')`; SQL with `'don''t; copy'` inside a literal.

### 6.4 `verify-log` checks (`test_headless_verify.py`; findings level `error` => exit 10)

V1 record loads through `RunStore.load` (error). V2 `.json.sha256` sidecar: absent -> warning (GUI records have none), mismatch -> error ("record file was modified").
V3 consistency: `status == "ok"` requires every node `ok`; `failed` requires >= 1 non-ok node or a failed node error (error). V4 `--workflow` given: `workflow_sha256`
equals the file's SHA-256 (error). V5 each output fingerprint with a `sha256`: file exists, same size, same sha256 (error; `--no-files` skips). V6 input fingerprints: missing/changed -> warning only (inputs are legitimately refreshed).
Tests: pristine record -> 0; flip one byte in the record -> V2 error; delete an output -> V5; append a row to an output -> V5; edit the workflow -> V4; GUI-style record without sidecar -> warning only, exit 0.

### 6.5 Scheduling tests (all with `_run_schtasks` monkeypatched; no real tasks)

`test_parse_trigger[...]` (daily/weekdays/weekly `MON,THU@06:30`/hourly 6/once; bad `25:00`, `FUNDAY@01:00`, `--hourly 0`);
`test_task_xml_structure` (parse with `ElementTree` using the task namespace: `MultipleInstancesPolicy == IgnoreNew`, `StartWhenAvailable == true`, `Command` equals the exe, `Arguments` equals `subprocess.list2cmdline(args)` for a workflow path with spaces and unicode, `WorkingDirectory` equals the workflow folder, `ExecutionTimeLimit == PT3900S` for timeout 3600, `LogonType == InteractiveToken`);
`test_run_whether_logged_on_uses_s4u_and_never_password` (`LogonType == S4U`; no `/RP`, no `/RU`, no `/P` in any recorded argv);
`test_skip_missed_sets_false`; `test_xml_file_is_utf16_with_bom`; `test_add_calls_create_with_exact_argv`
(`["schtasks","/Create","/TN","TriggerDesigner\\nightly","/XML",<path>,"/F"]`); `test_add_requires_approval_exit_6_no_call`; `test_print_only_no_call_prints_command_and_xml`;
`test_nonzero_schtasks_exit_9_includes_stderr`; `test_list_merges_json_and_csv` (canned CSV from X10 with a **French** header row and `22-10-2026 13:00:00` dates -> `Last Result` parsed as int, dates raw); `test_remove_argv_and_files_deleted`;
`test_non_windows_exit_9` (monkeypatch `sys.platform`); `test_name_validation`. Optional real test `tests/e2e/test_cli_schedule_integration.py`:
`@pytest.mark.skipif(os.name != "nt" or os.environ.get("TD_TEST_SCHTASKS") != "1")` creates `selftest-<pid>` with `--once` in 2030, asserts it is queryable, removes it, asserts it is gone. Skipped by default.

### 6.6 Atomic-write and "partial output" proof

Covered by `test_commit_rolls_back_when_second_replace_fails` (unit) and `test_killed_run_leaves_no_partial_output` (e2e). Additional property test:
`test_final_path_never_opened_before_commit` - monkeypatch `builtins.open`/`pl.LazyFrame.sink_csv` in-process via `run_workflow_file` and assert no call receives the final path before `output.committed`.

---

## 7. Acceptance checklist

- [ ] `trigger-designer-cli --version`, `--help`, and every `<command> --help` work; `info`, static `validate`, `approve`, `params`, `paths`, `schedule list` start without importing PyQt6/polars (`test_cli_import_discipline`).
- [ ] `run` on every `FILE_OUTPUT_CASES` workflow exits 0 and matches the GUI goldens; GUI/CLI byte-identical outputs for the 8 deterministic cases; join compared sorted.
- [ ] Exit codes 0,1,2,4,5,6,7,8,64,130 are each produced by a named e2e test; 3, 9, 10 by unit tests.
- [ ] stdout in `--log-format json` is JSON Lines only (also when nodes `print`); stderr text mode carries no JSON.
- [ ] A killed/cancelled/timed-out/failed run never changes an existing output file and leaves no `.tdtmp`/`.tdbak` after the next run of that workflow.
- [ ] The X3 payload is refused by `--dry-run` and by `run` (exit 6) and creates no file; 32/32 attack rows refused; 7/7 benign pass; corpus 0 refusals.
- [ ] No file is written to the CWD by a CLI run or a GUI Run (`check_output.py` now under `<app_data>/last_run/`).
- [ ] A GUI save of a workflow with a `parameters` block keeps it.
- [ ] Generated code of plans 01/04/05/06/07 passes the policy (`test_future_node_imports_pass`); `filePathRel` never overrides an overridden `filePath`; plan 01 folder/glob/db keys bind per 3.5.
- [ ] Exactly one record write per run; `finish` called once with `cancelled=`/`outputs=`/`save=`; no `dataclasses.replace` on records.
- [ ] `check_output.py` generated under `<app data>/last_run/` still imports `trigger_designer` (header test).
- [ ] GUI Cancel button: plan 09 F-D's acceptance, not repeated here; this plan only confirms `tests/ui/test_canvas_buttons.py` still passes.
- [ ] Run records from the CLI load in `RunStore`/the Run-log dock and match GUI record shape; `verify-log` passes on them and fails on a tampered copy.
- [ ] `schedule add --print-only` prints a runnable `schtasks` command and valid XML; unit tests with mocks pass.
- [ ] Manual (Windows, documented in the PR, **not** automated): `schedule add selftest --once <now+2 min>` -> task appears in `schtasks /Query`; at the time, a run record exists and `Last Result` is 0; `schedule remove selftest`.
- [ ] `scripts\build.bat` produces `dist\TriggerEditor\trigger-designer-cli.exe` (+3-6 MB with MERGE) that passes the two smoke commands; installer script edits compile in Inno Setup.
- [ ] `tests\unit` >= baseline + new tests, all passing; `tests\e2e` all passing; `tests\ui` shows no failures beyond the 27 baseline ones.
- [ ] `ruff format` clean and `ruff check` no worse than before on every touched file.

---

## 8. Verification commands (name layers; never bare `pytest`)

```powershell
# fast loop
.venv\Scripts\python.exe -m pytest tests\unit\test_cli_parser.py tests\unit\test_headless_*.py tests\unit\test_op_catalog_matches_registry.py tests\unit\test_cli_import_discipline.py -q
# touched GUI code
.venv\Scripts\python.exe -m pytest tests\unit\test_workflow_execution_mixin.py tests\unit\test_scene_metadata_roundtrip.py tests\unit\test_executor_code_filter.py tests\unit\test_execution_result.py -q
.venv\Scripts\python.exe -m pytest tests\ui\test_canvas_buttons.py -q
# layers
.venv\Scripts\python.exe -m pytest tests\unit -q                  # baseline 334 passed + new
.venv\Scripts\python.exe -m pytest tests\e2e -q                   # baseline 20 passed + new (CLI tests spawn subprocesses; ~2-4 min)
.venv\Scripts\python.exe -m pytest tests\ui -q                    # 27 pre-existing failures/errors are the baseline
# lint per touched file (compare with the pre-change count)
.venv\Scripts\python.exe -m ruff format <files> ; .venv\Scripts\python.exe -m ruff check <files>
# smoke by hand
.venv\Scripts\trigger-designer-cli.exe info "savedfiles\0. All Node- Test.tds"
.venv\Scripts\trigger-designer-cli.exe validate tests\e2e\workflows\formula-category.tds --deep --no-files
.venv\Scripts\trigger-designer-cli.exe schedule add demo tests\e2e\workflows\formula-category.tds --daily 02:30 --print-only
scripts\build.bat                                                   # packaging step only
```

---

## 9. Pitfalls

1. **Never import `trigger_designer.main`** from the CLI (configures loguru, tees stdout/stderr at import; F1). `cli/` and `core/headless/` must stay free of PyQt6/qtpy/polars at import time; keep heavy imports inside functions. `test_cli_import_discipline` is the guard.
2. `NodeExecutor._capture_output` replaces `sys.stdout` **process-wide** while a node runs; the event stream must use the private fd handle from `capture_stdout_channel()` (X9), never `sys.stdout`.
3. Set `POLARS_MAX_THREADS` (from `--threads`) **before** the first polars import, i.e. before `build_run_plan` imports anything heavy.
4. Do not create the `QApplication` before the Emitter fd redirect and signal handlers; do not create it on a non-main thread; never two `QApplication`s (brief 2.3) - `run_workflow_file` called twice in one process must reuse `QApplication.instance()`.
5. `execute_node` clears the cancel event at its start (`executor.py:303`); the CLI/GUI cancel flag lives on the **worker/supervisor**, not on the executor.
6. `WorkflowWorker` is a `QThread`; the CLI does **not** use it (needs an event loop for queued signals) - it calls plan 09 F-C's shared run loop through `execute_nodes`. Do not hand-copy the loop; `test_gui_and_cli_parity` guards behaviour.
7. Always leave the CLI process with `os._exit(code)` **after** `emitter.close()`, lock release and `discard_all` - and make `force_exit` do the same cleanup first. Do not rely on `atexit`.
8. `TriggerSubWindow.log()` prints to stdout without a dock (F11): `HeadlessWindow.log` must override it. `global_logger` may still print; it goes to stderr after X9.
9. Load happens on the main thread **before** the runner thread starts; node construction on another thread would crash Qt. The wall-clock timeout starts at process start, so a slow load counts.
10. `fileLoad` swallows non-JSON exceptions (`loadFromFile` -> `dumpException`, brief 3.5) and may return True for a half-loaded scene: after load assert node count equals the JSON node count and every edge loaded, else exit 2.
11. The work copy must be **ASCII JSON**; writing it with orjson (UTF-8) and letting Qt's `open(..., "r")` decode it with the locale encoding corrupts non-ASCII paths (F10).
12. `RunRecorder.begin(path, ...)` hashes the file at `path`: pass the **original** `.tds`, not the work copy; commit **then** pass final-path fingerprints in `finish(outputs=...)` (3.8, 3.12). `finish` once, never `replace` a sealed record, never `save` twice (`save=False` for `--no-record`).
13. `psutil` import is 83 ms: import it inside `RunLock`/`Supervisor` methods, not at module top.
14. Windows signal facts (X8): use `CREATE_NEW_PROCESS_GROUP` + `CTRL_BREAK_EVENT` in tests; `CTRL_C_EVENT` is disabled for new process groups; `time.sleep` polling (not `Event.wait()`) is what lets Python run the handler.
15. `schtasks` CSV headers are localized and dates are locale-formatted: parse by column position, never by header text or date.
16. `ArgumentParser` must have `allow_abbrev=False` and the exit-64 override or `--dry` silently selects `--dry-run` and usage errors collide with exit 2.
17. A bound `--param` for a filter value only prevents *accidental* breakage; the code policy is what stops injection. Do not skip either.
18. `schedule add` must absolute-ize `--param` paths against the CWD at definition time; a scheduled task's CWD is `System32`.
19. The e2e tests spawn real Qt processes: give them `timeout=180`, run them serially (no `-n`), and never run them inside the `tests\ui` layer.
20. `pyproject.toml`, `main.py`, `check_output.py` are already modified by others in the working tree: re-read before editing, and never `git add -A`.

---

## 10. Interfaces

**Consumed**
* Plan 01 `core/inputs.py`: `ResolvedFile`, `resolve_input_files(content_state) -> list[ResolvedFile]` - used by `build_run_plan` for the existence/size/sheet check of every File Input after parameters and remaps are applied (the check is done on the patched state, so `exists` reflects the final path). Its minimal path helper (if any) delegates to `resolve_workflow_path`.
* Plan 02: `RunRecorder(RunStore, AuditOptions)`, `begin/node_finished/node_errored/finish(record, ok, *, cancelled=False, outputs=None, save=True)`, `before_node/after_node` hooks, `audit_bridge.node_specs_from_window(window, sorted_nodes)`, `RunStore.load`, `FileFingerprint`. No new `RunRecord` fields are required (CLI-only facts go to `<run_id>.cli.json`).
* Plan 03 `core/errors`: `NodeError` from `NodeRunRecord.error`, `enrich_error(EnrichJob) -> EnrichResult` (synchronous, called once for the first failed node), catalogue entries `TD-CLI-001..018` from Appendix C; codes `TD-IN-001`, `TD-RUN-001/002/004`, `TD-SYS-999` reused. If `ExecutionResult.exception` exists the executor edit uses it (S4).
* Existing: `TriggerSubWindow.fileLoad/validateLoadedWorkflow/topologicalSort/getNodeConnections`, `NodeExecutor.execute_node`, `SecurityConfig`, `core/constants.py`, `tests/support/workflows.materialize`.
* Plan 09: F-B (`ExecutionResult` fields, executor `code_filter`/`policy_violation`, `before_run` hook list), F-C (shared run loop, continue-on-error), F-D (`request_run_cancel()`), F-F (`saveToFile`, `workflow_dir`, metadata carry-forward), F-G (console-script/`pyproject.toml`/`trigger.spec` base pass).
* Plan 06: `content.before_run()` (called once per node before execution); op `input.workpaper_output` is registered in `op_catalog.OPS` by this plan (S1 table, `output_keys=("output_path",)`).
* Plan 01: `filePathRel`, `scene.workflow_dir`, `source_spec()`, folder/glob/db keys in `SOURCE_KEYS`.

**Provided (for plans 04-07 and users)**
* `trigger_designer.core.headless.run_workflow_file(path, *, input_overrides=None, output_dir=None, record_dir=None, timeout_s=None, **opts) -> RunOutcome{exit_code, record, record_path, errors}` - deviation from brief 11.3 (`-> RunRecord`): a refused or invalid run has no record, and callers need the exit code.
* Console script `trigger-designer-cli = "trigger_designer.cli:main"`; exit-code contract of section 3.4 (`ExitCode`); JSONL event contract of 3.9.
* `core/headless/paths.py::resolve_workflow_path / remap_into_dir / relativize` (the path helper for the whole product).
* `core/headless/op_catalog.py::OPS` - this plan adds rows for all planned nodes (plans 01, 04, 05, 06, 07; S1 table); any node added later must add a row (rule), or `test_op_catalog_matches_registry` fails. A node that embeds user-authored Python must set `custom_code=True`.
* `core/headless/code_policy.py` - a node whose generated code needs a new import/helper adds it to the allowlists with an attack-table row; `test_corpus_passes_policy` and a per-node generated-code test are the guard.
* `workflow_metadata.parameters` block schema (3.5) and `PARAM_TARGETS` (extend only with a value rule and a test).
* `GENERATED_IMPORTS` table + registration rule (3.11).

---

## Appendix A - Runbook ("server ready") and container sketch

**What "server ready" means here and no more:** a stateless command; no GUI dependency; no hidden state except three per-user
folders (`state`, run records, approvals); deterministic exit codes; logs on stdout/file; safe to kill. A scheduler, a CI job or a
container supplies the "server". Non-goals: web UI, multi-user, remote DB, authentication, queueing.

**State layout** (`--state-dir` / `TRIGGER_DESIGNER_STATE_DIR`; default `%LOCALAPPDATA%\Trigger Designer\cli`):
`approvals.json`, `locks/`, `work/<run_id>/` (deleted after the run), `staging/` (only for unsafe output paths), `schedules/<name>.{json,xml}`,
`logs/`. Run records: `--record-dir` or `<app data>\runs\<run_id>.json` (+ `.json.sha256`, `.cli.json`) - the same folder the GUI uses.

**Operating procedure**
1. Author in the GUI; (optional) `trigger-designer-cli params add wf.tds --name input_file --node "File Input" --setting filePath --required`.
2. Deployment copy: `trigger-designer-cli paths wf.tds --relativize --write` (keeps `wf.tds.bak`).
3. Review and pin: `trigger-designer-cli approve wf.tds` (prints reads/writes; answer `y`). CI: `approve wf.tds --yes --note "PR 123"`.
4. Dry run: `trigger-designer-cli run wf.tds --dry-run --param input_file=D:\in\today.csv` -> exit 0 means inputs exist, outputs writable, code accepted.
5. Run: `trigger-designer-cli run wf.tds --param input_file=D:\in\today.csv --log-format json --log-file D:\logs\wf.jsonl`.
6. Audit later: `trigger-designer-cli verify-log <run_id>.json --workflow wf.tds`.
7. Schedule (Windows): `trigger-designer-cli schedule add nightly wf.tds --daily 02:30 --param input_file=D:\in\today.csv --timeout 3600`.

**Wrapper policy by exit code** (what a CI/ops script should do):

| Exit | Action |
|---|---|
| 0 | success |
| 4, 5, 7, 8 | transient or environmental: retry later (7 = a run is already active; 8 = output locked/disk full) |
| 1 | data/logic problem: alert; do **not** blindly retry (read `run.finished.errors[]`) |
| 2 | configuration problem (missing input, bad parameter, newer file): alert; fix |
| 6 | policy refusal: a human must `approve` (or investigate a changed/hostile file) |
| 130 | operator cancelled |
| 3, 9, 10, 64 | bug / scheduler / verification / usage: alert |

**Containers.** `Dockerfile` sketch (**not built or run during planning; do not gate acceptance on it**): Linux needs the Qt offscreen runtime libs even with no display.

```dockerfile
FROM python:3.13-slim
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libegl1 libxkbcommon0 libfontconfig1 libdbus-1-3 libglib2.0-0 git \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY . /app
# qtpy-nodeeditor is installed from git with --no-deps on purpose (see scripts/build.bat); pin QTNODEEDITOR_URL to your fork/ref.
RUN pip install --no-cache-dir uv && uv pip install --system -e . && uv pip install --system --no-deps "git+https://github.com/<fork>/qtpy-nodeeditor@<sha>"
ENV QT_QPA_PLATFORM=offscreen PYTHONUTF8=1 TRIGGER_DESIGNER_STATE_DIR=/state TRIGGER_DESIGNER_DATA_DIR=/data
VOLUME ["/state", "/data", "/in", "/out"]
ENTRYPOINT ["trigger-designer-cli"]
CMD ["--help"]
```
Run: `docker run --rm -v wf:/wf:ro -v in:/in:ro -v out:/out -v approvals:/state trigger-designer run /wf/wf.tds --input-dir /in --output-dir /out --log-format json`
(`--input-dir/--output-dir` remap Windows-authored absolute paths by basename; mount `/state/approvals.json` read-only, produced in CI). Run as a non-root user with only `/out` writable.

**Other schedulers (non-goal, how-to only).** cron: `30 2 * * * trigger-designer-cli run /srv/wf.tds --trigger schedule --log-format json --log-file /var/log/td/wf.jsonl`; same idea for systemd timers/launchd. `flock` is unnecessary (the CLI has its own lock).

**Troubleshooting.** exit 6 -> `trigger-designer-cli info wf.tds` shows `approved: no | changed since approval`; exit 7 -> another run, or a dead run's lock (stale locks self-heal when the pid is gone); exit 8 -> close the output file in Excel; exit 2 with `TD-IN-001` -> `paths wf.tds` shows which saved path is missing, remap with `--input-dir`.

---

## Appendix B - Help-text drafts (verbatim starting point; keep line width <= 78; every command has an Example)

```text
usage: trigger-designer-cli [--version] [--state-dir DIR] <command> [options]

Run Trigger Designer workflows (.tds) without the editor window.

commands:
  run         Run a workflow and write its outputs
  validate    Check a workflow file (add --deep to load it like the editor)
  info        Show what a workflow reads, writes and needs
  approve     Pin a reviewed workflow file so it may run unattended
  verify-log  Check a run record against the files it describes
  params      List, add or remove run-time parameters stored in a workflow
  paths       Show saved file paths; optionally make them relative
  schedule    Create, list or remove Windows scheduled runs

exit codes: 0 ok, 1 node failed, 2 invalid workflow/input, 3 internal error,
  4 timeout, 5 memory limit, 6 refused by safety policy, 7 already running,
  8 could not write outputs, 9 scheduler error, 10 verification failed,
  64 bad command line, 130 cancelled.
```

```text
usage: trigger-designer-cli run WORKFLOW [options]

Run WORKFLOW (a .tds file). Outputs are written to temporary files and moved
into place only if every node succeeds, so a failed or cancelled run never
leaves a half-written output.

parameters and paths:
  --param NAME=VALUE    override a parameter defined in the workflow (repeatable)
  --input-dir DIR       read every File Input from DIR (same file name as saved)
  --output-dir DIR      write every File Output into DIR (same file name as saved)
  --create-output-dirs  create missing output folders instead of failing
limits:
  --timeout SEC         stop the whole run after SEC seconds (default 3600, 0 = none)
  --max-memory MB       stop if this process uses more than MB of memory
  --threads N           limit worker threads used by Polars
  --cancel-grace SEC    after Ctrl+C, wait SEC for the running node (default 10)
  --min-free-mb N       refuse to start with less free disk (default 64)
safety:
  --allow-unapproved    run a file that has not been approved (interactive use)
  --allow-custom-code   allow nodes that contain user-written code (needs approval)
  --strict              treat warnings as errors
  --keep-going          after a node fails, still run branches that do not depend on it
output:
  --dry-run             check everything and print the plan; run nothing
  --record-dir DIR      where to write the run record (default: same as the editor)
  --no-record           do not write a run record
  --no-hash             do not compute SHA-256 of inputs/outputs
  --emit-script FILE    also save the generated Python script
  --log-format {text,json}  text: human lines on stderr; json: one JSON object
                        per line on stdout (default text)
  --log-file FILE       append JSON lines to FILE (rotated at 10 MB)
  -v, -vv, --quiet      more / much more / less logging

Ctrl+C asks the run to stop after the current node. A node that is already
running cannot be interrupted; after --cancel-grace seconds the process exits
(130). Outputs are not touched in that case.

Example:
  trigger-designer-cli run sales.tds --param input_file=D:\in\today.csv --log-format json
```

```text
usage: trigger-designer-cli validate WORKFLOW [--deep] [--no-files] [--strict]
                                    [--param NAME=VALUE] [--input-dir DIR] [--output-dir DIR]
                                    [--format {text,json}]
Check the file without running it. Default (fast, no editor libraries): JSON
structure, schema version, node types, cycles. --deep also loads the workflow
like the editor does, resolves inputs, and checks the code each node would run
against the safety policy. --no-files skips the "input exists" check.
Example:  trigger-designer-cli validate sales.tds --deep --strict

usage: trigger-designer-cli info WORKFLOW [--format {text,json}]
Show nodes, files read and written (saved and resolved paths), parameters,
file hash, and approval status. Starts instantly.
Example:  trigger-designer-cli info sales.tds --format json

usage: trigger-designer-cli approve WORKFLOW [--yes] [--note TEXT]
       trigger-designer-cli approve --list
       trigger-designer-cli approve --revoke WORKFLOW
Show what the workflow reads and writes, then record its SHA-256 as approved.
Any change to the file (even re-saving it) needs a new approval. Approvals are
stored per user and are not signed. Scheduled runs require approval.
Example:  trigger-designer-cli approve sales.tds --note "reviewed 2026-10-21"

usage: trigger-designer-cli verify-log [RECORD_OR_FOLDER] [--workflow WORKFLOW]
                                       [--no-files] [--format {text,json}]
Check a run record: file integrity (when a .sha256 file exists), internal
consistency, the workflow hash, and that each output still has the recorded
size and SHA-256. Without an argument, checks the newest record.
Example:  trigger-designer-cli verify-log 3f2a....json --workflow sales.tds

usage: trigger-designer-cli params list WORKFLOW
       trigger-designer-cli params add WORKFLOW --name NAME --node ID_OR_TITLE
              --setting SETTING [--type {path_in,path_out,string,int}]
              [--default VALUE] [--required] [--label TEXT]
       trigger-designer-cli params remove WORKFLOW --name NAME
Parameters can be set per run with `run --param NAME=VALUE`. Only these
settings can be parameterised: File Input filePath, selected_sheet,
record_limit; File Output filePath; Filter value, value2 (builder mode);
Split random_seed, estimation_percent. A backup WORKFLOW.bak is written first.
Example:  trigger-designer-cli params add sales.tds --name input_file --node "File Input" --setting filePath --required

usage: trigger-designer-cli paths WORKFLOW [--relativize] [--write]
List every saved file path with its resolved location and whether it exists.
Relative paths are resolved against the folder of the workflow file.
--relativize shows (and with --write, applies) paths under that folder as
relative paths, keeping WORKFLOW.bak.
Example:  trigger-designer-cli paths sales.tds --relativize --write

usage: trigger-designer-cli schedule add NAME WORKFLOW
              (--daily HH:MM | --weekdays HH:MM | --weekly DAYS@HH:MM | --hourly N | --once YYYY-MM-DDTHH:MM)
              [--param NAME=VALUE] [--run-whether-logged-on] [--skip-missed]
              [--timeout SEC] [--max-memory MB] [--print-only] [--force]
       trigger-designer-cli schedule list [--format {text,json}]
       trigger-designer-cli schedule show NAME
       trigger-designer-cli schedule remove NAME
Windows Task Scheduler only. Times are this computer's local time. The workflow
must be approved. By default the task runs only while you are logged on and, if a
run was missed, starts as soon as possible; --run-whether-logged-on runs without
a session but cannot use network drives or shares that need your credentials.
No password is ever stored. --print-only shows the exact schtasks command and
task XML without creating anything.
Example:  trigger-designer-cli schedule add nightly sales.tds --daily 02:30 --param input_file=D:\in\today.csv
```


---

## Appendix C - `TD-CLI-001..018` catalogue entries (for plan 03 to paste into `core/errors/catalogue.py`)

Plan 03 owns the catalogue file; this plan owns the meaning. `severity` is `error` unless stated. Text is plain language, imperative hints. The exit code in the last column is the
**only** exit-code contract (3.4); any exit-code proposal elsewhere is superseded.

| Code | Title (one line) | Hint | Severity | Exit |
|---|---|---|---|---|
| TD-CLI-001 | The workflow file could not be read. | Check that the file is a Trigger Designer workflow (.tds) and is not damaged or open in another program. | error | 2 |
| TD-CLI-002 | This workflow was saved by a newer version of Trigger Designer. | Update Trigger Designer, or ask the author to save it with your version. | error | 2 |
| TD-CLI-003 | The workflow contains a node type this program does not know. | Install the version that provides it, or replace the node in the editor. | error | 2 |
| TD-CLI-004 | The workflow has a loop: a node depends on its own output. | Open it in the editor and remove the connection that goes backwards. | error | 2 |
| TD-CLI-005 | A parameter name was not recognised, or a required parameter is missing. | Run `params list <workflow>` to see the available names and pass `--param name=value`. | error | 2 |
| TD-CLI-006 | A parameter or path value is not valid. | Use a whole number for number settings and a local file or folder path (no web addresses). | error | 2 |
| TD-CLI-007 | That setting cannot be changed from the command line. | Only file paths, sheet name, row limit, filter values and split seed/percent can be parameters. | error | 2 |
| TD-CLI-008 | This workflow has not been approved to run. | Review it with `approve <workflow>`; scheduled runs always need approval. | error | 6 |
| TD-CLI-009 | The workflow changed after it was approved. | Check who changed it, then approve it again. | error | 6 |
| TD-CLI-010 | The workflow was refused by the safety check. | Open it in the editor and look at the reported node; do not run files you do not trust. | error | 6 |
| TD-CLI-011 | The workflow contains a node with user-written code. | Run it with `--allow-custom-code` only if the file is approved and you trust its author. | error | 6 |
| TD-CLI-012 | This workflow is already running. | Wait for the other run to finish; if none is running, run again (stale locks clear themselves). | error | 7 |
| TD-CLI-013 | The results could not be saved to their final location. | Close the output file in Excel or other programs and check free disk space, then run again. Previous files are unchanged. | error | 8 |
| TD-CLI-014 | An output folder is missing or cannot be written, or two outputs would overwrite each other. | Create the folder (or use `--create-output-dirs`), check permissions, or give each output its own file name. | error | 2 |
| TD-CLI-015 | There is not enough free disk space for the outputs. | Free some space or choose another output folder with `--output-dir`. | error | 2 |
| TD-CLI-016 | The Windows scheduler could not complete the request. | Read the message from Windows below; run from an account allowed to create tasks. | error | 9 |
| TD-CLI-017 | The run record does not match the files it describes. | Treat the outputs as unverified; re-run the workflow and keep the new record. | error | 10 |
| TD-CLI-018 | This workflow writes no files, so a run produces nothing. | Add a File Output node (or use the editor's preview). | warning | 0 (2 with `--strict`) |
