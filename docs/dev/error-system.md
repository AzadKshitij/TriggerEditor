# Error system

Goal: a failure reaches the user as a stable code, one plain sentence and a
fix, tied to the node that caused it, instead of a Polars/DuckDB traceback.
Code: `core/errors/` (Qt-free) plus the Qt glue in `qt/node_base.py`,
`qt/helpers/problems_store.py`, `error_context.py`, `error_enricher.py` and
`qt/docks/problems_dock.py`.

## `NodeError` (`core/errors/model.py`)

A frozen dataclass; plain data so it can be stored in a run record, rendered
and tested without a GUI.

| Field | Meaning |
|---|---|
| `code`, `title`, `detail`, `hint` | Stable code; one sentence; the long explanation; the first suggested fix. |
| `technical`, `exc_type`, `exc_module`, `traceback` | Raw material, hidden by default (preference `errors/show_technical`). `traceback` is excluded from equality. |
| `severity` | `error` or `warning`. |
| `node_id`, `node_title`, `node_label`, `op`, `phase` | Who and when (`phase` is `"live"` or `"run"`). |
| `columns`, `path` | Facts the UI can highlight. |
| `suggested_fixes: tuple[SuggestedFix]` | `SuggestedFix(text, kind="manual", params)`; `kind="rename_column"` carries `from`/`to`. |
| `row_index`, `sample_values`, `failing_count`, `locate_status` | Filled by enrichment (the first row that fails a conversion). |
| `did_you_mean` | Close column or sheet names. |
| `culprit_node_id`, `culprit_node_title` | The upstream node that really caused it. |
| `redacted`, `params`, `fingerprint`, `created_at` | `fingerprint` = SHA-1[:12] of `code|node_id|culprit|columns|exc_type`; `with_updates(**changes)` recomputes it. |

`knock_on` is true for `KNOCK_ON_CODES = {TD-RUN-003, TD-RUN-005, TD-RUN-008}`:
"this node did not run because an upstream node failed". Renderers:
`render_summary()` (`"<node label>: <title>"`), `render_tooltip()` (first
sentence of detail, `Fix:`, code, at most 600 chars), `render_text()` (the
copyable block).

`ErrorContext` (what the translator may know): node identity,
`input_columns`, `input_dtypes`, `referenced_columns`, `input_paths` and
`output_paths` (path -> node id), `node_labels`, `variable_owners`,
`date_format`. `ErrorContext.from_node(node, phase)` is duck-typed and never
raises. The GUI builds the full one with `qt/helpers/error_context.build_context`.

## Translation (`core/errors/translator.py`)

`translate_exception(exc, *, node=None, phase="run", ctx=None, redact=False,
traceback_text="") -> NodeError` is **total**: it never raises; on its own
failure it returns `TD-SYS-999`.

Order of attempts:

1. **Passthrough.** Walk `original_exception` up to 5 levels; if any exception has
   a `code` attribute starting `TD-`, or the message matches
   `(?:^|\[)(?P<code>TD-[A-Z]+-\d{3})(?:\]|:)`, use that code. A code absent from
   the catalogue still produces an error (title = the message). A catalogue entry
   marked `passthrough` keeps the exception's own message as the title and adds
   the catalogue hint and the owning node of `exc.path`. This is how
   `ShapingError`, `AuditConfigError`, `InputReadError` and the CLI errors reach
   the user.
2. **Rules.** `RULES` is a tuple of 34 `Rule(id, codes, names, pattern, build)`.
   A rule applies when the exception class-name set intersects `names` (or
   `names is None`) and the regex `pattern` (if any) matches the message text;
   `build(facts, ctx, match)` returns `(code, params)` or `None` to fall through.
   Rules are ordered; the first hit wins. They parse Polars, DuckDB, sqlglot,
   OS and Python messages (column not found, string to number, date format,
   join key types, schema mismatch, timeout, memory, xlsxwriter missing, ...).
3. **Fallback.** `TD-SYS-999` "Something unexpected went wrong." with the first
   160 characters as `reason`.

Then `_finish` fills computed params (`target_one/_human/_sql`, `path_name`,
`row_hint`, `others_sentence`, `suggestion_sentence`), renders the catalogue
entry, optionally calls `redact_error`, and builds the `NodeError`.

`redact=True` (preference `errors/redact_values`) strips sample values from
titles, details and the technical text (`redact.py`) so an error can be pasted
or stored in a record without leaking data.

## The catalogue (`core/errors/catalogue.py`)

`CATALOGUE: dict[str, Entry]` is "the only place user-facing error sentences
live" (115 codes today). Two sources, merged at import:

* **Full entries** written in `CATALOGUE` (`TD-IN`, `TD-SCH`, `TD-TYP`, `TD-EXP`,
  `TD-JOI`, `TD-OUT`, `TD-RUN`, `TD-SYS`): `severity`, `title` (and
  `title_located` for when a row is known), `detail`, `fixes`
  (`((text, condition_param), ...)`; a fix whose condition param is empty is
  dropped), optional `reserved` (code exists but no rule produces it yet).
* **`_PASSTHROUGH`**: `code -> (title, hint, severity)` for codes raised by other
  feature cores with their own message (`TD-AUDIT-*`, `TD-SHAPE-*`, `TD-CLI-*`,
  and a few `TD-IN/TD-OUT` extensions). Each becomes
  `{"severity", "title", "hint", "passthrough": True}`.

Templates are `str.format_map` strings; every placeholder must be in
`_OPTIONAL_PARAMS` (unknown placeholders render as `?`; the test fails). Titles
are shortened to 90 characters, no emoji (tests). `render_entry(code, params,
*, located=False) -> (title, detail, fixes)`.

Code families: `TD-IN` input, `TD-SCH` schema, `TD-TYP` type conversion,
`TD-EXP` expression, `TD-JOI` join, `TD-OUT` output, `TD-RUN` run (001
timeout, 002 memory, 003/005/008 knock-on), `TD-SYS` internal, `TD-AUDIT` audit
tests, `TD-SHAPE` shaping nodes and SQL guard, `TD-CLI` command line.

## The registry rule

**Every code a node can raise must exist in the catalogue, and a `TD-SHAPE`
code must also be in `core/shaping/common.py::ERROR_CODES`.** Never reuse or
renumber a code (they appear in saved run records and docs). Today the two
`TD-SHAPE` sets are identical (checked while writing this page); nothing fails
globally if they drift, only the per-node tests (`code in ERROR_CODES and code in
CATALOGUE`) do, so add that assertion to the tests of any node that raises a new
code. A code missing from the catalogue still works (title = the message) but has
no hint and no tooltip text.

Also covered by tests (`tests/unit/test_errors_catalogue.py`): every rule's codes
exist in the catalogue; every non-reserved, non-passthrough code has a rule;
placeholders are allowed; no emoji; rendering is safe with sample params.

### How to add a code

1. Pick the next free number in the family (`TD-SHAPE-nnn`); read the existing
   keys first (`TD-SHAPE-006..039` and others are gaps, not reserved).
2. **User mistake raised by your own core code:** raise it
   (`ShapingError("TD-SHAPE-nnn", detail, columns)` /
   `AuditConfigError("TD-AUDIT-nnn", message, field=...)`), then add
   `"TD-SHAPE-nnn": ("Short title", "Fix: sentence.", "error")` to
   `_PASSTHROUGH`, and for shaping add it to `ERROR_CODES` as well.
3. **A raw engine failure you want phrased well:** add a full entry to
   `CATALOGUE` and a `Rule` in `_build_rules()` (next free `id`; put it before
   any broader rule that would match first). Test with the real exception: build
   it by running Polars on a tiny frame (see `tests/unit/test_errors_translator.py`).
4. Add tests: translator output for your code; the node test that it is raised
   live and in generated code; `docs/guide` troubleshooting if user visible.
5. Mention it in `docs/CHANGELOG.md`. (`scripts/gen_error_reference.py` is a
   separate in-progress effort to generate an error reference; check whether it
   exists before documenting codes by hand.)

## Where errors live on a node, and how they are shown

* `TriggerNode.set_error(error, source="live"|"run")` stores one error per
  source in `_errors_by_source`. `current_error` is `run` if present, else `live`.
  `clear_error(source=None)` clears one or both; clearing `run` also clears
  the *knock-on* run errors of child nodes (cycle-safe).
* `_apply_error_state`: tooltip = `error.render_tooltip()` (or "Changes pending
  - the node runs when you click away"), and the node badge: `error`, `warning`
  or `pending` (one glyph in the status slot; an error outranks pending).
* A new error (different `fingerprint`) is logged once with the full
  `render_text` to the log file and the one-line summary to the Logging dock.
* `ProblemsStore` (`qt/helpers/problems_store.py`) holds one row per `(node_id,
  source)`; `entries()` lists run errors first, then live errors for nodes
  without a run error. `set_error` skips adding a *live knock-on* row. `count(
  severity, roots_only=True)` excludes knock-ons.
* `ProblemsDock` (`qt/docks/problems_dock.py`): one clickable row per error;
  clicking selects the node; `Run finished with N problem(s)` raises it after a
  failed Run (`on_run_problems`).
* Live errors: nodes call `self.set_error(translate_exception(exc, node=self,
  phase="live"), "live")` then `markInvalid`; `ShapingNode.processInputs` and
  `AuditNode._fail` do it for you. The base `eval()` catches stray exceptions and
  sets a tooltip (plain `ValueError` message).
* Run errors: see `run-pipeline.md` (`_on_node_finished`).

## Enrichment

After a Run failure the first error is only a translation of the exception. Many
failures are *caused upstream* (a bad column in a Formula surfaces in the File
Output). `core/errors/enrich.py`:

* `EnrichJob(error, ancestors, inputs_of, labels, attribute=True, locate=True,
  row_cap=5_000_000, redact=False)` -> `enrich_error(job) -> EnrichResult(root,
  knock_on, culprit_node_id)`; `enrich_sync(error, *, redact=...)` runs without
  ancestors (headless/record).
* `attribute_upstream` (`attribution.py`) walks `ancestors` and finds the node
  whose schema/data produced the failure (`SCHEMA_CODES` / `DATA_CODES` select
  the check; it inspects at most 100,000 rows per ancestor).
* `locate_conversion_failures` (`locator.py`) finds the first failing row and up
  to a few sample values for `TD-TYP-001/003/005` (limited by
  `errors/locate_row_cap`, off with `errors/locate_rows = False`).
* `make_error("TD-RUN-003", ctx, ...)` (`builders.py`) builds the knock-on error
  for the node that merely received the failure.

GUI side: `_start_error_enrichment` builds a job with `build_enrich_job`, runs it
on a `QThreadPool` (`ErrorEnricher`, 10 s default timeout) and
`_apply_enrichment` puts the **root** error on the culprit node and a knock-on on
the failing node. A late result is dropped if the node's run error changed.
The run record waits for enrichment (`finish_when_settled`) so it stores the
settled error.

## Preferences

`errors/continue_past_failure` (default `True`), `errors/redact_values`,
`errors/locate_rows`, `errors/locate_row_cap`, `errors/show_technical`.

## Known gaps

* `errors/continue_past_failure` is stored and shown in Preferences but **not
  read by the Run**: `WorkflowExecutionMixin._run_policy()` returns
  `{"continue_on_error": False}` unconditionally. Only the headless runner
  passes its own policy.
* A `TD-SHAPE` code that is in the catalogue but not in `ERROR_CODES` (or vice
  versa) is not caught by any global test.
