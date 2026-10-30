# Audit trail internals

The audit trail records every Run as one immutable, hash-chained JSON file
(the **run record**). The five audit *tests* (Duplicates, Gaps, Benford,
Sample, Risk Filters) live in the same package, `core/audit/`, but are a
separate concern (`adding-a-node.md` section B); this page is about the record.

Rule of the package: **Qt-free, and it never changes a Run's outcome.** Every
entry point swallows and logs its own failures (a warning in the record at
worst). A unit test fails if any `core/audit` module imports Qt or the
executor.

## Modules

| Module | Responsibility |
|---|---|
| `__init__.py` | Lazy re-exports through `__getattr__` and `_EXPORTS` (name -> submodule). Importing the package costs nothing and pulls in no polars; generated code may import one submodule alone. Add a new public name to `_EXPORTS`; `test_every_lazy_export_resolves` checks them. |
| `schema.py` | Dataclasses `FileFingerprint`, `NodeRunRecord`, `RunRecord`; `validate_record_dict`; constants. |
| `canonical.py` | `canonical_json`, `sha256_hex`, `compute_record_hash`, `utc_now_iso`, `GENESIS_HASH`. |
| `fingerprint.py` | `fingerprint_file`, `sha256_stream`, `count_rows_in_file`, `FingerprintCache`, `recorded_path`, `normalise_path`. |
| `counting.py` | `decide_row_count_mode`, `count_frame`, `schema_of`, `CountError`. |
| `store.py` | `RunStore`, `verify_store`, `verify_record_file`, `resolve_store_dir`, the lock, the index. |
| `recorder.py` | `RunRecorder`, `AuditOptions`, `NodeSpec`, `EdgeRef`, `sanitize`, `extract_seed`, the run-record provider registry. |
| `errors_adapter.py` | `NodeError` (or an exception) to the stored `error` dict: `node_error_to_dict`, `error_to_dict`, `exception_to_dict`. |
| `compare.py` | `compare_runs`, `check_inputs`, `DiffItem`, `RunDiff`, `InputCheck`. |
| `view.py` | Display rows shared by the dock and the HTML export: `run_summary_rows`, `node_table_rows`, `format_duration`, `format_local_time`. |
| `export.py` | `render_html(record, verify=None)`, `export_json(source, destination)`. |
| `test_summary.py` | `TestSummary` (what an audit test reports; stored in `NodeRunRecord.test_summary`). |
| Qt side | `qt/helpers/audit_bridge.py` (`RunSession`, `options_from_preferences`, `store_from_preferences`, `node_specs_from_window`), `qt/helpers/audit_tasks.py` (`AuditTask`), `qt/docks/run_history_dock.py` (`RunHistoryDock`, `InputCheckDialog`), `qt/models/run_history_models.py`, preferences group "Audit trail". |

## Record schema (`RUN_RECORD_SCHEMA_VERSION = 1`, `HASH_ALGO = "sha256-canonical-json-v1"`)

`RunRecord.to_dict()` is the on-disk shape. `REQUIRED_RUN_KEYS` is **derived
from the dataclass fields** (a test pins the list) and is the key set of the
*current* schema version. `validate_record_dict` checks a record against
`required_run_keys(record["schema_version"])` and reports each missing key as
`schema_invalid`.

**Schema evolution rule.** A sealed record is never rewritten, so a field added
later must not make older records invalid. To add a run-level field: give it a
default in `RunRecord`, raise `RUN_RECORD_SCHEMA_VERSION` to N, and register it
in `FIELD_ADDED_IN` (`{"new_field": N}`). Only records with `schema_version >= N`
must then carry the key; version 1 records, and every field not listed, keep
their original requirements. A test checks that each registered field is not
ahead of the schema version, and another seals records, adds a field and
verifies the old store still passes. Fields:

Run level: `run_id` (uuid4 hex), `started_at`, `finished_at` (UTC
`YYYY-MM-DDTHH:MM:SS.ffffffZ`), `status` (`running` in flight only, then
`ok | failed | cancelled`), `app_version`, `workflow_schema_version`,
`workflow_path` (forward slashes), `workflow_sha256`, `user`, `machine`
(`None` when `audit/record_identity` is off), `python_version`,
`polars_version`, `duckdb_version`, `os_name`, `app_name`, `inputs[]`,
`outputs[]` (both `FileFingerprint`), `nodes[]` (`NodeRunRecord`),
`generated_code` (omitted if over 1 MiB or `embed_code` off),
`generated_code_sha256`, `schema_version`, `seq`, `duration_s`,
`workflow_uuid`, `graph_sha256`, `workflow_modified_since_save`, `options`
(requested and effective row-count mode, hash options, input bytes),
`baseline` (`{"run_id", "input_changes": [{path, change: added|modified|removed,
old_sha256, new_sha256}]}` against the previous record), `warnings[]`
(max 20, 500 chars each), `hash_algo`, `prev_record_hash`, `record_hash`.

`FileFingerprint`: `role` (`input|output`), `path`, `size_bytes`,
`modified_time`, `mtime_ns`, `sha256`, `sha256_status`
(`computed | cached | skipped_size_limit | disabled | missing | error |
cancelled`), `sheet`, `node_id`, `row_count`, `row_count_method`, `error`.

`NodeRunRecord`: `node_id`, `op`, `title`, `label`, `status`
(`ok | failed | skipped`), `seq`, `started_at`, `duration_s`, `count_seconds`,
`settings` (sanitised), `seed`, `code_sha256`, `rows_in[]`, `rows_out{var:
n}`, `columns_out`, `dtypes_out`, `count_method`, `peak_memory_mb` (always `null`: not measured),
`warnings`, `error` (stored error dict: `code`, `title` required), `test_summary`.

`graph_sha256` = SHA-256 of the canonical JSON of
`{"nodes": [{id, op, settings}] sorted by id, "edges": sorted [src, src_socket,
dst, dst_socket]}`; it identifies the *graph that ran*, independent of node
positions and of the file bytes.

`validate_record_dict(d) -> list[str]` checks required keys, version (a record
newer than this build is rejected), hex-64 hashes, statuses, fingerprints and
node shape. `from_dict` ignores unknown keys; verification always works on the
raw parsed dict (never a dataclass round trip) so unknown keys stay covered by
the hash.

**Compatibility rules.** Only add fields, always with defaults; never rename
or repurpose one; do not change `canonical_json` options or the hashing
algorithm without a new `HASH_ALGO` and a verifier that still handles the old
one.

## Canonical JSON and hash rules

* `canonical_json(obj) -> bytes`: `orjson.dumps` with `OPT_SORT_KEYS` plus
  `OPT_PASSTHROUGH_DATETIME | PASSTHROUGH_DATACLASS | PASSTHROUGH_SUBCLASS`: sorted
  keys, no whitespace, UTF-8, shortest round-trip floats. Datetimes, dataclasses
  and subclasses **raise `TypeError`** so a value that cannot be reproduced from
  the on-disk JSON never reaches a hash. Integers up to 64 bits are fine
  (`mtime_ns` exceeds 2**53); `sanitize` turns larger ints into `repr`.
* `compute_record_hash(d)` = SHA-256 hex of `canonical_json` of the dict *without*
  its own `record_hash` key.
* The **chain**: `prev_record_hash` of record *n* is `record_hash` of record
  *n-1* (taken from the index's last entry); the first uses `GENESIS_HASH`
  (64 zeros). `seq` is `previous seq + 1`, assigned **at seal time under the lock**.
* The file on disk is `orjson` with `OPT_INDENT_2 | OPT_SORT_KEYS` (human
  readable); the hash is over the canonical (compact) form, so re-indenting a file
  does not break verification but changing any value does.
* `sanitize(value)` (settings, depth 12, strings cut at 20,000 chars + marker):
  NaN/inf become `None`, sets are sorted lists, paths become forward-slash
  strings, dates ISO strings, anything unknown `repr(...)[:200]`.
* `extract_seed(settings)`: `random_seed` or `seed` int, unless `is_random` is
  explicitly `False`.

## Store layout, locking, verification (`store.py`)

Folder resolution `resolve_store_dir(workflow_path, run_log_dir, app_data_dir)`:

| Condition | Folder |
|---|---|
| `audit/run_log_dir` set, workflow saved | `<run_log_dir>/<stem>-<sha1(abs path lower)[:8]>/` |
| `audit/run_log_dir` set, unsaved | `<run_log_dir>/_unsaved/` |
| default, workflow saved | `<workflow folder>/<stem>.runs/` |
| default, unsaved | `<app data>/runs/_unsaved/` |
| fallback (primary read-only or lock timeout) | `<app data>/runs/<stem>-<hash8>/`, with a warning appended to the record |

Contents: `<run_id>.json` (sealed, `chmod` read-only on a best-effort basis),
`index.jsonl` (append-only; one canonical JSON line per record:
`file, prev_record_hash, record_hash, run_id, seq, started_at, status`),
`<run_id>.started` (marker dropped at `begin`, removed at seal; an unsealed marker
means a crash or kill), `hash_cache.json` (advisory), `.lock`.

* **Lock** `store_lock(folder)`: exclusive `O_CREAT|O_EXCL` file `.lock`; waits up
  to `LOCK_TIMEOUT_S = 10`, treats a lock older than `LOCK_STALE_S = 60` as
  abandoned (deletes it), tolerates Windows `PermissionError` while the owner
  deletes it; raises `StoreLockTimeout`. The lock covers: read index, assign `seq`
  and `prev_record_hash`, write `<run_id>.json.tmp` + `fsync` + `os.replace`,
  append the index line + `fsync`, drop the marker. Constants are module level so
  tests can shrink them.
* `_seal` refuses an existing target (`RunAlreadySealed`); repairs a truncated
  final index line (adds an `index_truncated_line` warning to the new record).
* `seal_and_save(record, directory=None) -> (RunRecord, path)`; `save` returns
  just the path. `list_runs` reads the index only. `latest_record_dict`,
  `load`, `load_dict`, `verify`.
* `verify_store(folder) -> VerifyReport(ok, checked, problems, warnings,
  head_hash)`. Problem kinds: `record_hash_mismatch`, `prev_hash_mismatch`,
  `missing_record`, `index_mismatch`, `seq_gap`, `schema_invalid`, `unreadable`,
  `index_corrupt`. Warnings: `index_truncated_line`, `clock_skew`,
  `orphan_record`, `incomplete_run`. What is **not** detectable: truncating the
  tail of the chain (so the report prints `head_hash`, which a user can note
  elsewhere). `verify_record_file(path)` checks one file in isolation.

## Recorder lifecycle (`RunRecorder`)

One recorder serves one run at a time. `RunRecorder(store=None, options=None,
*, cache=None)`.

1. `begin(workflow_path, nodes: Sequence[NodeSpec], *, app_version, edges=(),
   workflow_uuid=None, modified_since_save=None) -> RunRecord` (GUI thread):
   resets state, new `run_id`, hashes the workflow file, sums input bytes to pick
   the counting mode, builds `graph_sha256`, captures identity/versions, prepares
   the store folder, binds the hash cache and drops the `.started` marker. Returns
   a record with `status="running"`.
2. `before_node(node)` (executor thread): fingerprints (stats + SHA-256, cached by
   `(path, size, mtime_ns)`) the node's declared `input_files`.
3. `after_node(node, local_variables, result)` (executor thread): per declared
   output variable, `count_frame` (rows + schema) and fingerprint the node's
   `output_files` (never from cache; counts rows in the written file). May replace
   a variable with a materialised frame.
4. `node_finished(record, node, execution_result, *, rows_out=None,
   test_summary=None) -> NodeRunRecord` / `node_errored(record, node, exc)`
   (GUI thread). A failed node also fingerprints partial outputs. The stored
   error comes from `errors_adapter` (translated, optionally enriched
   synchronously when `AuditOptions.sync_enrich`, i.e. headless).
5. `update_node_error(node_id, error_dict)`: replaces a failed node's error after
   the Problems store settled (GUI `RunSession._refresh_failed_errors`).
6. `finish(record, success, *, cancelled=False, outputs=None, save=True) ->
   RunRecord`: fills missing nodes as `skipped`, finalises inputs (a single-file
   source gets its row count from its output variable), adds hash/size warnings,
   runs `_reconcile` (a File Output that received N rows but wrote M adds a
   `row count mismatch` warning), computes `baseline`, joins node code
   (`generated_code`, with SHA-256), seals via the store. A save failure returns
   the unsealed record and logs; it never raises into the run. `abort`-style:
   `save=False` discards the marker (and the folder it created).
7. `snapshot(record=None) -> dict | None` and the provider registry
   `set_run_record_provider` / `get_run_record_provider`: the in-flight record
   as a dict (used while a run is going).

`AuditOptions` fields: `record_identity`, `hash_inputs`, `hash_outputs`,
`hash_max_mb` (2048), `row_counts` (`auto|all|sink|off`), `exact_counts_max_mb`
(256), `embed_code`, `store_dir`, `app_data_dir`, `enabled`, `sync_enrich`,
`redact_values`. `NodeSpec(node_id, op, title, label, settings, n_outputs,
output_variables, is_source, input_files, output_files)`;
`EdgeRef(src_node_id, src_socket, dst_node_id, dst_socket)`.

### Counting modes (`counting.py`)

`decide_row_count_mode(requested, total_input_bytes, threshold_mb)`: explicit
`off|all|sink` wins; `auto` picks `all` when the total input size is at most
`exact_counts_max_mb`, otherwise `sink`.

| Mode | What happens | `count_method` |
|---|---|---|
| `all` | Each lazy output is **collected once**, counted, and the materialised frame (`.lazy()`) replaces the variable so downstream nodes reuse it and every plan runs once. | `materialized` (`eager` for an eager frame) |
| `sink` | Nothing is materialised; only *source* nodes are counted with `select(pl.len()).collect(engine="streaming")`; a File Output's `rows_in` is filled from the row count of the file it wrote. | `scan_plan` |
| `off` | No counting. | `none` |

Schema (`columns_out`, `dtypes_out`) is always captured via `collect_schema()` (no
data), capped at 500 columns ending in `"..."`. Counting failures become a
`row count skipped for <var>` warning and leave the frame untouched.

### Fingerprints

`fingerprint_file(path, role, node_id=None, sheet=None, *, cache=None,
cancel=None, hash_enabled=True, hash_max_bytes=2 GiB, use_cache=True,
chunk=8 MiB)` never raises: `missing` for `FileNotFoundError`, `error` for other
`OSError`, `skipped_size_limit` above the limit, `disabled` when hashing is off,
`cached` on a hit, `cancelled` if `cancel` fired. The cache key is
`normcase(abspath)|size|mtime_ns`; max 2000 entries; a corrupt cache file is
renamed `.bad`. `count_rows_in_file(path, fmt, delimiter)` counts by format
(CSV through `scan_csv(infer_schema=False)` because quoted fields can contain
newlines; Excel through `openpyxl` read-only).

## Qt bridge

* `RunSession.start(window, sorted_nodes, executor) -> RunSession | None`
  returns `None` when `audit/record_runs` is false. It builds specs
  (`node_spec_from_node`): settings via `snapshot_settings(content)` (calls
  `get_serialized_state`/`serialize`, flattens a shaping node's nested
  `settings`, drops `schema_snapshot`, `available_sheets`, `file_metadata`, `id`,
  `pos_x`, `pos_y` and `_`-prefixed keys, forward-slashes path keys), input files
  (a content may define `audit_input_files()`; File Input is listed with
  `list_source_files`), output files (`audit_output_files()` or File Output's
  `filePath`/`file_format`/`delimiter`).
* **To make a new file-reading or file-writing node auditable** define
  `audit_input_files() -> [{"path", "sheet", "kind"}]` /
  `audit_output_files() -> [{"path", "format", "delimiter"}]` on its content.
* Preferences: `audit/record_runs`, `audit/run_log_dir`, `audit/record_identity`,
  `audit/hash_inputs`, `audit/hash_outputs`, `audit/hash_max_mb`,
  `audit/row_counts`, `audit/exact_counts_max_mb`, `audit/embed_code`,
  `audit/warn_on_input_change` (log "Input changed since the previous run").
* `RunHistoryDock`: lists runs from the index, shows the node table, verify
  (`verify_store`), compare two runs (`compare_runs`), "check inputs" (`check_inputs`,
  re-hashes now), export JSON/HTML (`export_json`, `render_html`). Long work runs
  in `AuditTask(fn(cancel_event, *args))` on the thread pool; results return
  through queued signals `done`/`failed`; the dock holds a reference until one
  arrives. Colours come from theme tokens.
* Headless: build specs with `node_specs_from_window` and drive `RunRecorder`
  directly with `AuditOptions(sync_enrich=True, store_dir=...)`.

## Public API signatures (as listed in `_EXPORTS`)

```python
# canonical
GENESIS_HASH: str
canonical_json(obj) -> bytes
sha256_hex(data: bytes) -> str
compute_record_hash(record_dict: dict) -> str
utc_now_iso() -> str
# schema
RUN_RECORD_SCHEMA_VERSION = 1; HASH_ALGO = "sha256-canonical-json-v1"
validate_record_dict(d: dict) -> list[str]
FileFingerprint.from_dict(d) / .to_dict();  NodeRunRecord.*;  RunRecord.*
# fingerprint / counting
fingerprint_file(path, role, node_id=None, sheet=None, *, cache=None, cancel=None,
                 hash_enabled=True, hash_max_bytes=..., use_cache=True, chunk=...) -> FileFingerprint
sha256_stream(path, *, cancel=None, chunk=...) -> str | None
count_rows_in_file(path, fmt, delimiter=",") -> int | None
decide_row_count_mode(requested, total_input_bytes, threshold_mb) -> str
count_frame(frame, mode, *, is_source) -> (rows | None, method, frame)
schema_of(frame) -> (names, dtypes)
# store
resolve_store_dir(workflow_path, run_log_dir="", app_data_dir=None) -> Path
RunStore(run_log_dir="", app_data_dir=None)
  .store_dir_for(wp) .fallback_dir_for(wp) .resolve_writable(wp, directory=None)
  .mark_started(run_id, wp, directory=None) .seal_and_save(record, directory=None)
  .save(record, directory=None) .load(path) .load_dict(path)
  .list_runs(directory=None, workflow_path=None) -> list[RunHeader]
  .latest_record_dict(directory=None, workflow_path=None) .verify(directory=None, workflow_path=None)
verify_store(directory) -> VerifyReport;  verify_record_file(path) -> VerifyReport
# recorder
RunRecorder(store=None, options=None, *, cache=None)
  .begin(...) .before_node(node) .after_node(node, locals, result)
  .node_finished(record, node, result, *, rows_out=None, test_summary=None)
  .node_errored(record, node, exc) .update_node_error(node_id, error)
  .finish(record, success, *, cancelled=False, outputs=None, save=True)
  .snapshot(record=None) .request_cancel() ; .options .last_path .mode .store
set_run_record_provider(provider | None); get_run_record_provider()
sanitize(value) -> Any; extract_seed(settings) -> int | None
# compare / view / export / errors
compare_runs(old: dict, new: dict) -> RunDiff            # RunDiff.items: DiffItem(kind, node_id,
                                                        #  node_title, field, old, new); .identical
check_inputs(record: dict, *, cancel=None, use_cache=False) -> list[InputCheck]
run_summary_rows(rec) -> [(label, value)];  node_table_rows(rec) -> [dict];  format_duration(s)
render_html(record: dict, verify=None) -> str;  export_json(source, destination) -> str
error_to_dict(result, node=None, *, enrich=False, redact=False, enricher=None) -> dict
exception_to_dict(exc, node=None, *, ...) -> dict;  node_error_to_dict(error) -> dict
```

`DiffItem.kind` values: `input`, `parameter`, `row_count`, `status`, `output`,
`environment` (`app_version`, `python_version`, `polars_version`,
`duckdb_version` ...), `node_set`.

## Audit tests and the record

`AuditContent` stores a `TestSummary` on the content; the recorder reads
`content.test_summary` in `_test_summary_of` (also accepts an explicit dict) and
stores it as `NodeRunRecord.test_summary`. The Summary is produced two ways: at
Run, `after_execution` reads the one-row Summary variable on the executor thread;
live, Benford and Sample fill it on every evaluation, the others on the "Count
exceptions now" button. `TestSummary` field names up to `exceptions_var` are a
frozen contract (`test_id` is `"<op>#<node_id>"`); later fields are only ever
added with defaults.

## Known gaps (found while writing this page)

* `NodeRunRecord.duration_s` is derived from the `ExecutionResult`'s
  `started_at`/`finished_at` stamps (it covers the whole node: code, hooks and
  row counting). `peak_memory_mb` is `null`: the executor does not measure
  memory (the post-run memory check was removed in `5ae3826`). Earlier builds
  recorded `0.0` for both.
* Truncating the end of the chain is undetectable by design (note `head_hash`).
