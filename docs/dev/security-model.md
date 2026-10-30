# Security model

Trigger Designer is a local-first desktop tool for analysts. It is not a
multi-user service, but it **opens workflow files (`.tds`) written by other
people** and, with the CLI, runs them unattended. This page says what that
means for contributors.

## Threat model

| Asset | Threat | Source |
|---|---|---|
| Files on the analyst's machine | A workflow's SQL reads (`read_csv('C:/secrets.csv')`, `FROM 'x'`, `glob`) or writes (`COPY ... TO`, `ATTACH`) files, loads an extension, changes engine settings | SQL text typed or stored in Formula, Filter, Multi-Field Formula, SQL Query, File Input query |
| Process integrity | Settings text becomes Python statements in the generated code that `exec` runs | Any setting (sheet name, delimiter, label, node title, column name) reaching `get_code()` |
| Result integrity | A re-run produces different numbers (`random()`, `uuid()`), or an input changed silently | Non-deterministic SQL; edited inputs |
| Source databases | A "query" in File Input modifies or locks a SQLite/DuckDB file | File Input `sqlite`/`duckdb` source |
| Spreadsheet readers | A cell starting with `=`, `+`, `-`, `@` is executed as a formula when the exported workbook is opened | File Output / Data Preview Excel export (`core/excel/cells.py`, in progress) |
| The audit record | Edited or deleted records | Anyone with file access (detectable, not preventable; see `audit-trail-internals.md`) |

**Out of scope / accepted:** the generated Python is trusted *because it is
produced by the app's own node classes from data*. There is no sandbox around
`exec` of generated code, and a user can always run arbitrary Python outside the
app. The defences below therefore focus on keeping *workflow data* inert: it may
become values, never statements, and its SQL may not leave the in-memory tables
it was given.

## Defence 1: `core/codegen_safe.py` (user text stays a value)

Generated code is built by concatenating strings, so every value that enters it
must be rendered as a literal:

```python
from trigger_designer.core.codegen_safe import lit, lit_dq, lit_list, safe_comment, ident_part
lit("it's")          # "it's" quoted/escaped via repr; containers recurse; nan/inf -> float('nan')
lit_dq(text)         # JSON string syntax, valid Python
safe_comment(text)   # collapses line breaks and NULs so a comment cannot end early
ident_part(node.id)  # [A-Za-z0-9_] only, safe inside a variable name
```

* Shaping nodes put **all** settings into a single JSON payload
  (`json.dumps(settings, sort_keys=True)` embedded with `{payload!r}`) and import
  the core function by a fixed dotted name; no setting text is interpolated.
* Audit nodes embed `params_dict()!r` and `ident_part(self.id)`.
* File Input legacy codegen quotes sheet and delimiter with `repr`.
* **Never** write `f"... '{setting}' ..."` or `"..." + setting + "..."` in a
  code generator. `tests/unit/test_codegen_no_unsafe_quotes.py` parses every
  function named in its `CODEGEN_FUNCTIONS` set (`get_code`, `audit_code`,
  `_builder_code`, `_position_code`, `_manual_code`,
  `_build_dtype_conversion_code`) and fails on a quoted interpolation. **If you
  name your generator something else, add the name to that set.**
  `test_codegen_quoting.py` and `test_codegen_safe.py` test the helpers and
  hostile values (quotes, newlines, `\x00`, unicode).

## Defence 2: `core/sql_guard.py` (SQL stays read-only and in memory)

Statement type alone is not a guard: `PRAGMA`, `DESCRIBE`, `FROM 'x.csv'` and
`read_csv()` are all typed `SELECT`, and in-memory DDL still runs after
`lock_configuration`. So there are two layers, and either alone is bypassable:

**Layer 1, text and parser: `check_select_only(sql, *, allow_unparsable=False)`.**
Order (first failure raises `ShapingError`):

1. empty -> `TD-SHAPE-001`; longer than `MAX_SQL_CHARS = 20_000` -> `TD-SHAPE-114`;
2. control characters -> `TD-SHAPE-112`;
3. NFKC-normalise (full-width letters and ligatures must not dodge the rules),
   then `mask()` blanks comments and string contents (DuckDB nests block
   comments; the mask does not, so it rejects a superset);
4. dollar quoting (`$$ ... $$`) and `E'...'` strings -> `TD-SHAPE-112`;
5. a `;` in the masked text -> `TD-SHAPE-110` (one statement);
6. first word must be one of `select with from values table` or `(` ->
   `TD-SHAPE-111`;
7. denied calls anywhere (identifiers kept visible, so a quoted name is also
   caught): `read_*`, `glob`, `*_scan`, `sniff_csv`, `query`, `query_table`,
   `duckdb_*`, `pragma_*`, `current_setting`, `which_secret`, **`random`,
   `uuid`, `gen_random_uuid`, `setseed`**, `getenv`, followed by `(` ->
   `TD-SHAPE-112`;
8. `FROM 'file'`, `JOIN 'file'`, `FROM "dir/file.csv"` (a quoted path-like
   identifier) -> `TD-SHAPE-112`;
9. DuckDB's own `extract_statements`: exactly one, and `StatementType.SELECT`,
   else `TD-SHAPE-110/111`. An unparsable text is `TD-SHAPE-113` unless
   `allow_unparsable=True` (Formula, Filter and Multi-Field Formula pass it so the
   *engine's* message reaches the user; nothing that does not parse can run).

A quoted column name that merely contains a denied word (`"read_total"`) is
accepted; a quoted *call* is still rejected (`5e5baea`).

**Layer 2, locked connection: `make_locked_connection(inputs=None, *, threads=1,
memory_limit="2GB")`.** A fresh in-memory connection with
`autoinstall/autoload_known_extensions=false`, `allow_community_extensions=false`,
`allow_unsigned_extensions=false`, `enable_external_access=false`, then
`lock_configuration=true`; frames are registered **by name** (names must match
`[A-Za-z_][A-Za-z0-9_]*`, else `TD-SHAPE-004`). The caller closes it.
`connect_for_shaping()` is the same with no memory cap (a context manager, used by
Formula and Filter which process whole tables).

`run_select(sql, inputs, timeout_s=25.0) -> pl.DataFrame` = check + locked
connection + a `threading.Timer` that `interrupt()`s the connection
(`TD-SHAPE-115`; 25 s is below the executor's 30 s). `infer_schema(sql,
schemas)` runs the query on zero-row inputs wrapped in `LIMIT 0`.

**Who uses it:** Formula, Filter (builder and expression), Multi-Field Formula,
SQL Query. Live evaluation, editor validation and generated code all go through
`core/shaping/<node>.py`, so there is one path. Fuzzy Match uses a plain
in-memory DuckDB connection (`core/shaping/common.py::connect_duckdb`) but never
runs user SQL.

**Determinism.** `random()`, `uuid()`, `gen_random_uuid()` and `setseed()` are
rejected so a re-run reproduces the same numbers (an audit requirement). A
workflow saved with such an expression now fails with `TD-SHAPE-112` (see the
changelog). Use the Sample node with a seed instead.

**If you add a node that runs user SQL:** call `check_select_only` (or
`run_select`) and a locked connection; do not call `duckdb.connect` yourself;
add your node's attacks to `tests/unit/test_duckdb_safety.py`.

## Defence 3: read-only database sources

`core/input_source.py`: SQLite is opened with a `file:...?mode=ro` URI,
`PRAGMA query_only=ON` and an authorizer that allows only `SELECT`, `READ`,
`FUNCTION`, `RECURSIVE`; DuckDB with `read_only=True`, `enable_external_access=
false` and `lock_configuration=true`. A multi-statement query is refused
(`_reject_multi_statement`, `db_forbidden`). The paths themselves are the user's
own choice.

## Defence 4: the executor

`NodeExecutor` runs generated code with a 30 s per-node timeout on a pooled
thread, verifies lazy plans, and has a `code_filter` hook with a
`policy_violation` flag so a runner can refuse code before `exec`. The
command-line runner installs one: `core/headless/code_policy.py` parses the
generated code and allows only known AST shapes and imports
(`GENERATED_IMPORTS`, and the prefix rule `trigger_designer.core.shaping.<x>`
importing only `run_node`/`write_node`), forbids dunders and file/OS APIs, and
requires every path to be one the approved workflow declared. **A new node whose
generated code imports anything outside those tables is refused by
`trigger-designer-cli run`**, so extend `GENERATED_IMPORTS` in the same change
(details in the later `cli-internals.md`). The GUI installs no filter. None of
this is a sandbox; do not add `eval`/`exec`/`compile` of workflow text anywhere
else.

## Defence 5: the record and error text

* `errors/redact_values` removes sample values from error text before it is shown
  or stored; `AuditOptions.redact_values` carries it into the run record.
* `audit/record_identity` omits user and machine names from the record.
* The record stores generated code only if `audit/embed_code` is on and it is
  under 1 MiB; settings go through `sanitize` (bounded depth and string size).
* The run script (`last_run/check_output.py`) lives in the app data folder, not
  next to the user's data.

## Defence 6: Excel output (in progress)

`core/excel/cells.py` (not yet documented here) is where text cells that look
like formulas are neutralised. Whoever owns the workpaper writes
`workpaper-internals.md`; until then treat "a user string must never be written
as an Excel formula" as a rule of any new export code.

## Test strategy

| Attack surface | Tests |
|---|---|
| SQL guard rules, one case per rejection | `tests/unit/test_sql_guard.py` (parametrised code/`TD-SHAPE-nnn` table incl. `random()`, `uuid()`, `gen_random_uuid()`) |
| Whole nodes under attack: every attack must raise `ShapingError` **and write nothing** | `tests/unit/test_duckdb_safety.py` (`ATTACKS` list run against Filter and Formula: UNION with `read_csv`, `COPY`, `ATTACH`, `INSTALL`, `SET enable_external_access`, `PRAGMA`, `glob`, `duckdb_settings`, dollar quoting; asserts the target file/db does not exist) |
| DuckDB threading | `tests/unit/test_shaping_duckdb_threads.py` |
| Codegen quoting | `test_codegen_no_unsafe_quotes.py` (AST sweep), `test_codegen_quoting.py`, `test_codegen_safe.py`, `test_file_input_codegen.py` |
| DB sources | `tests/unit/test_input_source_db.py` |
| Core stays free of unsafe calls | the headless code policy tests (later) |

Strategy for a new security fix: (1) write the failing attack as a parametrised
test that asserts both the error code and that nothing was written; (2) fix in
`sql_guard` or `codegen_safe`, not in the node; (3) check that live evaluation,
editor validation and generated code all see the fix (they share core).

## Rules of thumb

* User text is data. Quote it with `codegen_safe`, bind it as a parameter, or
  register frames by validated name; never concatenate it into code or SQL.
* Reject, do not sanitise: a guard that "cleans" SQL invites a bypass.
* A guard rejection keeps its own code (`TD-SHAPE-110..115`); do not wrap it into
  a generic error.
* Everything that can read or write a file outside the user's chosen input/output
  paths needs an explicit decision and a test.
