# Session Handoff — Node Audit & P0 Fixes (2026-09-15/16)

## Standing instructions from user
- **After every completed task, launch the app**: `run.bat self` (detached via
  `Start-Process`, working dir `C:\Projects\TriggerEditor`). Do this even for
  verification-only turns.
- **Work one thing at a time**: implement incrementally, each item with an
  **automated offscreen test + manual test card** in the reply.
- Planning/approval mode is over — build mode is active.

## Environment & tooling notes (Windows, PowerShell 5.1)
- venv: `.venv\Scripts\python` (py3.13). **No pytest** installed — tests are
  throwaway scripts in `C:\Users\azadk\AppData\Local\Temp\opencode\`, run them,
  then delete.
- GUI tests: `$env:PYTHONUTF8="1"` (else emoji logs crash on cp1252) and
  `os.environ["QT_QPA_PLATFORM"]="offscreen"` at the top of every script.
- **Never instantiate `QApplication` twice** in one script (second instance =
  instant `0xC0000409` fastfail, no traceback).
- On hard crash, stdout buffer is lost — test scripts must write PASS/FAIL to a
  result **file**, not just print.
- `git show REV:path --output=<file>` writes raw bytes; PowerShell `>` redirect
  writes UTF-16 (breaks JSON reads).
- Test-file pattern that works: build real nodes in `TriggerScene`, wire with
  `nodeeditor.node_edge.Edge`, `app.processEvents()`, explicit `.eval()`.
  `FileInput.eval()` **re-reads the CSV from `filePath`** (overwrites
  directly-assigned `content.data`) — use real temp CSVs. Dirty-flag caching:
  after config changes call `node.markDirty(True)` + `markDescendantsDirty()`
  before re-eval, mirroring the app.

## Architecture facts (verified, don't re-derive)
- **Run model**: `executeWorkflow` topo-sorts, then `NodeExecutor.execute_node`
  runs each `get_code()` via `exec(code, execution_globals, local_vars)`;
  locals merge into the shared context afterwards. **Imports leak**: generated
  code using bare `pl` only works because FileInput's code imports it first.
  Function defs inside generated code resolve globals from the shared dict.
- **Live model**: `TriggerNode.evalImplementation` pulls `input_node.eval()`
  recursively, then `processInputs(input_values)`; downstream contract is
  `self.param = [{"data":..., "variable_name":...}]`, one entry per output
  socket; consumer reads `input_values[i][socket_index]`.
- **Live data is eager** (`pl.DataFrame`) everywhere by convention; codegen is
  lazy. Join was the only lazy-live producer — fixed to collect once.
- **Join semantics (deliberate)**: full-outer + `coalesce=True`, split via
  pre-join presence tags (`__left_present`/`__right_present`, stripped from
  outputs). A right key coalesced away is represented by its left counterpart
  (same values for matched rows; coalesce-fill for right-only rows) — this
  matches native polars coalesce behavior, not a bug.
- `V1_OPCODE_TO_OP` uses **pre-GroupBy numbering** (GroupBy was inserted
  mid-enum at pos. 4; historical: 4=select, 5=sort, 6=unique, 7=split,
  8=dynamic_row_builder; 9 kept for interim-era files). Verified against git
  history + every surviving v1 file.
- `savedfiles/0. All Node- Test.tds` had 5 stale titles from the old buggy
  migration (e.g. "Sort" on a Select). Fixed by **renaming titles to match
  live type/content** (non-destructive; flipping ops would have changed pipeline
  behavior). All 21 titles now match resolved classes.
- Menu icons resolve via compiled Qt resources (`:Category/...` from
  `icons.qrc` → `icons_rc.py`); `Groupby.svg` was missing from the `.qrc`
  (added; `icons_rc.py` still needs a recompile — no rcc toolchain in venv).
  `_get_action_icon` now falls back to `ResourceManager` filesystem pixmaps.

## DONE this session (all verified, committed)
- Batch B: executor import seeding (`pl/os/datetime/timedelta` in
  `NodeExecutor.execution_context`, survives `clear_context`).
- Batch C: Unique returns None (no fake-green); getSocketValue first-match +
  ValueError; base preserves node-specific tooltips + "upstream produced no
  output" wording; RunningTotal/Count/Transpose data-None tooltips.
  getInput-None guards skipped: unreachable (base guarantees non-None
  before processInputs).
- Batch D/P2 (schema approach, NOT collect): shared `frame_schema()` +
  `frame_shape()` in `node_base`; all `.columns`/`[col].dtype`/`.shape`
  sites in select/groupby/transpose/filter/sort/unique/formula/graph/join
  use them; lazy flows end-to-end (Append stays lazy). Local collects only
  where inherent: count (len query), formula (duckdb, restores lazy),
  graph (matplotlib), dynrow stats fallback. Transpose codegen uses
  `collect_schema().names()` + own `import polars as pl`.
- Cleansing: engine (len/.item stats) is inherently eager like duckdb —
  `process_data` collects at the boundary, matching its codegen which
  already did (line 609). All other nodes verified lazy-safe live
  (select/filter/sort/unique/groupby/transpose/split/formula/dynrow/
  append/join/file I/O) + split live check (10 rows, outputs stay lazy).
- Batch D/P3: Select RowData asdict on save; Filter ""→None/"Equals"
  restore; join_type .get default; RowBuilder datetime iso + widget
  seeding. Stale-incoming_variable NOT reproduced (chain + join topologies,
  worst-order eval) — no fix applied.
- Batch E: `True & res`→`and` (16 files); dup imports/init (sort/filter/
  cleansing/join); QFileDialog `;;`; `!r` path codegen; FileOutput
  check_file_path → parent-dir semantics; FileInput live = full lazy scan
  (preview drift fixed, viewer gets head sample); `_read_csv` deleted;
  prints + commented blocks swept; `count_recors.py`→`count_records.py`.
  `incom_data` rename SKIPPED (143 sites, zero behavior gain).
  Manual test cards for each item are in the chat history above.
- Shift+A menu: removed 10-item window (showed 10/17 nodes); search focuses on
  open; typing auto-switches to flat list; first match auto-highlighted, Enter
  creates it. (`node_searchable_menu.py`)
- GroupBy menu icon fallback. (`context_menu_mixin.py`, `icons.qrc`)
- Join: get_code fallback (3 vars), auto-mapping (first-col pair when both
  inputs present), eager single-collect outputs, tag-based splitting,
  differing-key joins fixed live + codegen. (`Join/join.py`)
- P0 fallbacks (output var always defined): Transpose (+live passthrough when
  unconfigured, +`""`-vs-`None` guard fix), Count Records (zero-count),
  Running Total, Append (known-side passthrough), FileInput, Filter (T=all /
  F=empty), Formula, GroupBy, Select (guard fix + empty-selection passthrough),
  Split (both vars), Unique (both vars), Cleansing, Sort (+multi-col quoting
  fix — list repr already quotes, do NOT add quotes), Graph (guard +
  passthrough define), DynamicRowBuilder (shadowed `increment_value` call →
  `_increment_value`; codegen rewritten with literal rendering, imports,
  iteration cap), File Output (unwired raises `ValueError` instead of silent
  green no-save).
- Icons for +/- buttons via in-repo `add.png`/`sub.png` (`resources.json`:
  `icon_add`/`icon_remove`; Join/Sort/Formula/GroupBy).
- Commits (working tree clean): `108ac51` (P0 fallbacks), `0a87181` (join/
  transform rework), `a1e51ed` (icons). Manual test cards for each item are in
  the chat history above.

## PENDING — Batch B: executor import seeding (next recommended)
Seed `polars` (and `os`) into `NodeExecutor.execution_context` globals so
generated code doesn't depend on FileInput-first import leakage. Files:
`core/ExecutionCheck/executor.py` (`execute_node`, `_execute_with_timeout`).
Test: workflow whose first node isn't FileInput + a standalone `check_output.py`
run. (~6 nodes' get_code use bare `pl` today: filter, groupby, select-dtype
branch, genrows, split?, unique.)

## PENDING — P1: contracts + error UX
- `unique.py:570` returns `[None,None]` (fake-green success) — return `None`.
- `getSocketValue` (`node_base.py:312`) silently defaults to socket 0 and
  overwrites per match — return first match; error when unresolvable.
- Missing `getInput() is None` guards: filter:675, sort:534-535, unique:538-539,
  dynrow:392-393, running_total:261-262, transpose:336-337, count:169-170,
  file_output:412-413, join:1220-1223 (template: `Append.py:179-185`).
- Misleading messages: base `"Input {i} is NaN"` (it's upstream-None, not NaN),
  `"Invalid operation"` (no why), `"Input is not connected"` shown when
  upstream *failed*; running_total "No columns selected" on `data is None`;
  missing tooltips on count/transpose invalid paths; graph bare `return None`.
- Graph decision revisited: currently kept socket + passthrough; OK to leave.

## PENDING — P2: lazy hardening (cheap insurance, currently unreachable)
Shared `ensure_eager()` helper + one-liners where `.shape`/`[col].dtype` assume
eager input: select:944/959/595, groupby:996/1032, transpose:356/371,
count:194, filter:176/284/522 (use `collect_schema()` like cleansing:141-143).

## PENDING — P3: save/load round-trips
- Stale `incoming_variable` after load (unordered `doEvalOutputs` + dirty-flag
  cache) — evaluate topologically or seed from edges on load.
- Select saves raw `RowData` dataclasses (not JSON-safe) though deserialize
  expects dicts — `dataclasses.asdict` on save.
- DynamicRowBuilder `create_layout` ignores deserialized initial/increment/max
  (widgets always default); datetime values in serialize may break `json.dump`.
- Filter `""`-vs-`None` restore mismatch (`:601-603` vs `__init__:66`).
- `join_type = data["join_type"]` direct key (KeyError on old files).

## PENDING — P4: hygiene + misc (do last, all independent)
~20 emoji-debug `print`s (join:1214 etc.), commented blocks (join:137-149,
318,468-480,576-578,642-664; file_input:890-896), duplicate imports
(sort:6,16; filter:4,14; cleansing:14,24), double `TriggerChangeHandler.__init__`
(sort:64,73; join:64,77), `return True & res` → `and` (6 files), typos
(`count_recors.py` filename, `incomming`, `incom_data`), QFileDialog `|` → `;;`
(graph:88-90), single-quote path interpolation breaks on Windows paths
(file_input:725, file_output:272+), file_input preview-10-rows vs full-scan
codegen drift, `check_file_path` wrong for outputs (checks file existence,
should check parent dir).

## Known-remaining bugs (filed, not scheduled)
- DynamicRowBuilder **datetime increment widget** is a QDateTimeEdit where a
  seconds-spinner belongs (`timedelta(seconds=<datetime>)` TypeErrors; node
  goes invalid — no regression, was already broken).
- Graph `plt.show()` blocks headless Run (pops window per Run).
- `Join/union.py`, `Join/find_replace.py`, `Documentation/comment.py` are
  0-byte stubs (Union registered in enum but unimplemented).
- `run.bat :COMP` points at a stale absolute path on another machine.

## Manual smoke (after any node change)
New workflow → drop each touched node unwired → Run completes, zero
`NameError`s → wire File Input through → Run gives real results → save, reload,
Run again.
