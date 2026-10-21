# 03 - Plain-language, actionable errors

Status: implementation plan (no source was changed to write it). Read `docs/plan/00-codebase-brief.md`
sections 4, 5, 8, 9 and 11.3 first; this plan does not repeat them. Paths are repo-relative, `file.py:N` is the
line in the tree at `main` @ `71b4041` (+ the uncommitted edits listed in the brief). Every exception type and
message in section 3.4 was **observed** by running Polars 1.44.2 / DuckDB 1.5.5 / fastexcel 0.21.0 snippets
with `.venv\Scripts\python.exe` on 2026-10-21 (Windows 11). Where a message could not be provoked safely
(`MemoryError`, `PanicException`) it is marked **simulated**.

Revision 2 (cross-plan review): code areas aligned with plans 01/04/06/07/08 (3.5b), generic `TD-` pass-through rule 0, run-loop/executor/cancel work moved to plan 09 (F-A..F-D), synchronous `enrich_sync`, exit-code proposal superseded by plan 08.

Contents: 1 Goal/non-goals - 2 Current state - 3 Final design - 4 Implementation steps - 5 Edge cases -
6 Test plan - 7 Acceptance checklist - 8 Verification commands - 9 Pitfalls - 10 Interfaces.

---

## 1. Goal and non-goals

**Goal.** When a node fails, the user sees, on the node and in one list, a sentence that names the node, the
column, the offending row/value and the next action - not `str(exception)`. Example (must be reproducible by a
unit test, section 6):

> Aggregate 'Totals': column 'Amount' contains text ('1,2O0.50') in row 4,210, so it cannot be summed.
> Fix: clean the value, or add a Select node before this one and set Amount to Decimal.

Delivered by:

1. A Qt-free structured `NodeError` + one central `translate_exception()` + one message catalogue file.
2. A bounded, cheap second query that finds the first offending row and up to 5 offending values for cast/parse errors.
3. "Did you mean" suggestions (`difflib`) for misspelt columns, sheets and functions.
4. UI: better node tooltip, persistent error badge on the node, a new **Problems** dock (click selects the node,
   copy details, "technical details" toggle).
5. Continue-past-failed-branch for Run (independent branches still run).
6. Formula/Filter inline diagnostics keep their position logic but use the translator for wording and fix hints.
7. Preferences: `errors/redact_values`, `errors/continue_past_failure`, `errors/locate_rows`, `errors/locate_row_cap`.

**Non-goals (decided, with reason).**

| Not doing | Reason |
|---|---|
| Auto-applying fixes ("click to add a Select node") | Needs graph surgery + undo commands; `SuggestedFix.kind/params` are stored so a later plan can add buttons without changing the schema. |
| Translating the Data Preview panel's collect failures (brief E14) and the SQL editor's syntax squiggles | Different surface and thread; the translator is callable from there later. Only the Formula/Filter *wording* changes (3.10). |
| Localisation to a second language | The catalogue is the single source of strings (3.3) so it is possible later; shipping only `en`. |
| A cancel button / cancellation API | Owned by plan 09 F-D. `TD-RUN-004` is defined and `_on_node_skipped(node, None)` renders it; it only fires once F-D reports skipped-because-cancelled. |
| Making the 30 s timeout / 512 MB memory limit configurable | Out of scope; the messages tell the user what to do instead (filter/sample/Parquet). |
| Fixing the 68 per-node `setToolTip` sites | They are wrapped by `TD-SYS-001` (3.4) so they appear in the dock; node-by-node migration is incremental. Only File Input/Output, Join, Append and the base class move in step 11. |

---

## 2. Current state (verified)

| # | Fact | Where |
|---|---|---|
| C1 | Run failure: `NodeExecutor.execute_node` keeps `result.error = str(e)` and, for wrapped errors, appends `"\n\nOriginal traceback:\n" + traceback.format_exc()` (a `MemoryError()` therefore yields an error string that is *only* the traceback). The exception object/type is dropped. | `core/ExecutionCheck/executor.py:378-388` |
| C2 | `ExecutionResult` has no exception, node id or traceback field. `without_frames()` is used for the history. | `executor.py:35-47`, `:49` |
| C3 | The exec thread catches only `Exception`: `except Exception as e: exception_container[0] = e`. `polars.exceptions.PanicException` derives from `BaseException`. **Observed bug (script `obs5`)**: a node whose code raises `PanicException` returns `success=True, error=''`, the pooled worker thread dies, and every later node on that executor times out after 30 s each. | `executor.py:266-267`, `_node_worker_loop :171-176` |
| C4 | `_on_node_finished` failure branch only logs (`logger.error` + `global_logger.error`), `node.markInvalid()`, `setPenError()`. **No tooltip is set**; no structured error is kept. | `qt/helpers/workflow_execution_mixin.py:96-112` (`:106-112` failure) |
| C5 | Run stops at the first failure: `if not result.success: success = False; break`. Nodes after it never run. | `qt/helpers/workflow_worker.py:62-67` |
| C6 | `executeWorkflow` clears `markInvalid(False)` and pens for every node at start. | `workflow_execution_mixin.py:63-69` |
| C7 | Live errors: `eval()` catches `ValueError`/`Exception`, tooltip = `str(e)`; `evalImplementation` writes the three generic tooltips ("Input i is not connected", "Input i: upstream node produced no output", "Invalid operation") and clears the tooltip on success. | `qt/node_base.py:877-900`, `:816-852` (clear at `:849`) |
| C8 | Tooltip helpers `_set_node_tooltip` / `_node_tooltip`; owner-window lookup idiom (walk `view.parentWidget()` until the attribute exists). | `node_base.py:775-799`, `:763-770` |
| C9 | Node badge = bottom-edge `status_icons.png` chosen by `isDirty()/isInvalid()` (`offset 24/0/48`), painted in `TriggerGraphicsNode.paint`; rings from `setPenError/Executed/Executing/resetPen`. `boundingRect` is cached and must contain everything painted. | `node_base.py:115-360`, paint `:231-272`, pens `:336-358` |
| C10 | Lazy plans: only sinks/collects fail at Run, so an upstream bad cast surfaces at File Output/Graph/Count. After plan 09 F-E a graph with no sink fails at Run only for plan-level errors (`collect_schema()` on every lazy output, no implicit collect); data errors still need a sink. | brief 4.3; plan 09 F-E |
| C11 | Formula: `_diagnose_section_error` returns `{"message","category"[,line,column,length]}`; `ParserException` -> sqlglot positions; everything else -> `_shorten_error` text. `_run_sections_sequential` stores only the *message* per section; `update_data` re-raises `ValueError("Section n: msg")` and keeps `last_error=str(exc)`; the node sets `grNode.setToolTip(last_error)` and `global_logger.error` once. Tests pin: `last_error.startswith("Section 1:")`, `section_errors == {0: last_error.removeprefix("Section 1: ")}`, `_shorten_error` output, no "LINE"/"Candidate bindings"/generated alias in messages. | `qt/widgets/nodes/Preparation/formula.py:929-964` (`_shorten_error`, `_diagnose_section_error`), `:1057-1090` (`_run_sections_sequential`), `:1165-1197` (`update_data`), `:1391-1397` (node tooltip); `tests/ui/test_formula_node.py:305-318, 388-455` |
| C12 | Filter: `_update_expression_data` swallows the exception (`logger.error`, `data=None`) - no tooltip, node still returns `param` with `None` data; `validate_expression` returns `{"message": _shorten_error(...), line 1, column 0}`. | `Preparation/filter.py:798-838` (`_update_expression_data`), `:840-865` |
| C13 | File Input missing file: tooltip `File {path!r} does not exist`, `markInvalid`. File Output with no input raises `ValueError('File Output: no incoming data - connect an input')` from `get_code()` (inside `execute_node`'s `try`, `executor.py:307-310`). | `InOut/file_input.py:307-318`; brief 7.2 |
| C14 | Dock plumbing: `createLoggingDock/createDataPreviewDock/switchXxxDock/onDesignWindowClose`; default layout list; per-window wiring in `createMdiChild`; `executionResultsChanged` signal. | `qt/helpers/main_window_ui_mixin.py:257-295`; `qt/main_window.py:142-148, 505-552`; `qt/layout_state.py:225-250`; `design_window.py:83` |
| C15 | `node.id` is `id(self)` (an int, restored from file by `restore_id`); `TriggerNode.getChildrenNodes()` exists (`node_base.py:748`); topological sort and `getNodeConnections()` give per-node `"inputs"`/`"outputs"` lists. | `nodeeditor/node_serializable.py:14`; `design_window.py:711-757` |
| C16 | Baseline: `tests/unit` 334 pass, `tests/e2e` 20 pass, `tests/ui` 404 pass / 20 fail / 7 error (pre-existing; `test_formula_node.py` has 4 of them). | brief 2.4 |

---

## 3. Final design

### 3.1 Decisions (each with its one-line reason)

| # | Decision | Reason |
|---|---|---|
| D1 | Package `src/trigger_designer/core/errors/` (not a single module); `from trigger_designer.core.errors import NodeError, translate_exception` stays valid. | Brief 11.3 names `core/errors.py`. **It is the package `core/errors/` (with `__init__.py`), not a file `core/errors.py`; do not create both.** `from trigger_designer.core.errors import NodeError, translate_exception` works because `__init__.py` re-exports them. |
| D2 | Errors are *data*: a `NodeError` is built from `(code, params)` through the catalogue; enrichment changes `params` and **rebuilds** the text. | Lets the locator add "row 4,210" later without string surgery, and lets tests assert on params. |
| D3 | Translation runs on the GUI thread (regex only, microseconds). The row locator and upstream attribution run on a worker thread (`QThreadPool`) from a **snapshot** (`EnrichJob`) and post back. | Brief 4.2: GUI must not freeze; LazyFrames are immutable plans so they are safe to hand over. |
| D4 | New **Problems** dock, tabified with Logging and Data Preview (not a section in Logging). | Logging is a free-text, append-only, 1000-line HTML pane with no selection model (`logging_dock.py:73-150`); the Problems list is *state* (one row per failing node, replaced/cleared as nodes are fixed), needs click-to-select, copy and a details toggle. The Logging dock still receives one summary line per new error. |
| D5 | Root cause is stored on the **culprit** node; the node that merely surfaced it (usually a sink) gets knock-on `TD-RUN-003`. | A lazy plan fails at File Output but the broken step is upstream (C10); the badge must sit on the broken step. |
| D6 | `continue_past_failure` default **True**; preference reverts to stop-at-first. | Fixing all errors in one cycle beats discovering them one Run at a time; independent branches are by definition unaffected. |
| D7 | `locate_rows` default True, row cap 5,000,000 rows, 2 queries max, 10 s wall-clock abandon, 5 values, each <= 80 chars. | Measured (3.6): 5 M-row CSV scan = 0.15 s, 2 M rows in memory = 0.08 s. |
| D8 | `redact_values` default **False**; when True, sample values are removed from `title/detail/hint/technical/traceback` and from the log line; only the in-memory exception object keeps them. | Values are the point of the feature; users with confidential data flip one switch. |
| D9 | Row numbers are **1-based positions in the failing node's input table, header not counted** (row 1 = first data row). | Exactly what the locator can compute and what the example ("row 4,210") needs; no guessing of file line numbers. |
| D10 | Badge = filled circle with "!" painted inside the node's top-right corner using theme tokens `danger` (error) / `warning` (warning). It does not replace the bottom status badge. | Keeps `boundingRect` unchanged (C9) and satisfies DESIGN_SYSTEM §13 "state is never colour alone". |
| D11 | Tooltip carries title + detail first sentence + `Fix:` + code; **not** the raw exception. | DESIGN_SYSTEM §16: "Keep the raw exception out of the badge"; raw text lives in the dock and the log. |
| D12 | Catching `BaseException` in the exec thread is **provided by plan 09 F-A** (this plan only depends on it and tests it). | Fixes C3; without it a Polars panic is reported as success. |
| D13 | Plans 01/04/06/07/08 raise exceptions that already carry a `TD-` code; the translator has a generic pass-through rule 0 and the catalogue lists their codes (3.5b). | One code space, one place for hints, no per-plan translation rules. |

### 3.2 Module layout and signatures

Qt-free (`core/errors/`, imports stdlib + polars + loguru only; no `qtpy`, no `trigger_designer.qt`):

```
core/errors/__init__.py     re-exports NodeError, SuggestedFix, ErrorContext, translate_exception, make_error
core/errors/model.py        SuggestedFix, NodeError, ErrorContext, KNOCK_ON_CODES, shorten()
core/errors/catalogue.py    CATALOGUE: dict[str, Entry]  (ONLY file with user-facing sentences), render_entry()
core/errors/suggest.py      normalise_name(), suggest_names()
core/errors/redact.py       redact_text(), redact_error()
core/errors/translator.py   translate_exception(), RULES (ordered), translate_sql_diagnostic()
core/errors/builders.py     make_error(code, ctx, **params)  (errors that are not exceptions)
core/errors/locator.py      LocateResult, locate_conversion_failures(), polars_dtype_from_name(), probe_expr()
core/errors/attribution.py  Ancestor, attribute_upstream()
core/errors/enrich.py       EnrichJob, EnrichResult, enrich_error(), enrich_sync()   (sync, Qt-free entry for plans 02/08; signature in section 10)
```

Qt side:

```
qt/helpers/error_context.py   build_context(node, window=None, phase="run") -> ErrorContext ; build_enrich_job(...)
qt/helpers/error_enricher.py  ErrorEnricher(QRunnable) + signal holder; start_enrichment(job, on_done)
qt/helpers/problems_store.py  ProblemsStore(QObject)
qt/docks/problems_dock.py     ProblemsDock(QDockWidget)
qt/node_base.py               TriggerNode.set_error / clear_error / current_error ; TriggerGraphicsNode badge
```

#### `model.py` (full contract)

```python
SEVERITIES = ("error", "warning")
KNOCK_ON_CODES = frozenset({"TD-RUN-003", "TD-RUN-005", "TD-RUN-008"})

@dataclass(frozen=True)
class SuggestedFix:
    text: str                                  # one imperative sentence, final wording
    kind: str = "manual"                       # manual|rename_column|add_node|change_setting|clean_data
    params: dict[str, str] = field(default_factory=dict, compare=False)

@dataclass(frozen=True)
class NodeError:
    # --- frozen by brief 11.3 (names/semantics unchanged) ---
    code: str                                  # "TD-<AREA>-<NNN>"
    title: str                                 # plain language, one line, <= 90 chars (shorten()), NO node prefix
    detail: str = ""
    hint: str = ""                             # == suggested_fixes[0].text or ""
    technical: str = ""                        # original str(exc); scrubbed when redacted
    exc_type: str = ""                         # type(exc).__name__ ("" if none)
    severity: str = "error"                    # "error" | "warning"
    node_id: int | None = None
    node_title: str | None = None
    op: str | None = None                      # "preparation.formula"
    columns: tuple[str, ...] = ()
    path: str | None = None
    # --- added by plan 03 (all defaulted; plan 02 persists via dataclasses.asdict) ---
    phase: str = "run"                         # "live" | "run" | "load"
    node_label: str = ""                       # "Aggregate 'Totals'" (type + user label), used as prefix when rendering
    exc_module: str = ""                       # "polars.exceptions"
    traceback: str = field(default="", compare=False)
    suggested_fixes: tuple[SuggestedFix, ...] = ()
    row_index: int | None = None               # 1-based row in the failing node's input table
    sample_values: tuple[str, ...] = ()        # <= 5, each <= 80 chars + "…"
    failing_count: int | None = None           # when the engine reported it (NOT reliable under streaming, see 3.4 O5)
    did_you_mean: tuple[str, ...] = ()
    culprit_node_id: int | None = None         # upstream node responsible (None = this node)
    culprit_node_title: str | None = None
    locate_status: str = ""                    # ""|found|not_found|skipped|disabled|timeout|error
    redacted: bool = False
    params: dict[str, str] = field(default_factory=dict, compare=False)   # catalogue template params (strings only)
    fingerprint: str = ""                      # sha1[:12] of code|node_id|culprit|columns|exc_type (NOT row/values)
    created_at: str = field(default="", compare=False)   # ISO-8601 UTC

    @property
    def summary(self) -> str: ...              # alias of title (user wording "summary")
    @property
    def knock_on(self) -> bool: ...            # code in KNOCK_ON_CODES
    def render_summary(self) -> str: ...       # f"{node_label}: {title}" (no prefix when node_label == "")
    def render_tooltip(self) -> str: ...       # 3.9; <= 600 chars
    def render_text(self, *, include_technical: bool) -> str: ...   # copy-details format, 3.9
    def with_updates(self, **changes) -> "NodeError": ...           # dataclasses.replace + recompute fingerprint
    def to_dict(self) -> dict: ...             # JSON-safe (tuples -> lists, SuggestedFix -> dict)
    @classmethod
    def from_dict(cls, data: dict) -> "NodeError": ...              # tolerant: unknown keys ignored, missing -> defaults

@dataclass
class ErrorContext:                            # what the translator may know about the failing node; ALL fields optional
    node_id: int | None = None
    node_title: str | None = None              # class title, e.g. "Aggregate"
    node_label: str = ""                       # "Aggregate 'Totals'" or "Aggregate"
    op: str | None = None
    phase: str = "run"
    input_columns: tuple[str, ...] = ()        # columns of the first input that has any
    input_dtypes: dict[str, str] = field(default_factory=dict)      # column -> Polars dtype name ("String", "Int64"...)
    referenced_columns: tuple[str, ...] = ()   # columns the node is configured to use (best effort)
    input_paths: dict[str, int] = field(default_factory=dict)       # normalised path -> File Input node id
    output_paths: dict[str, int] = field(default_factory=dict)      # normalised path -> File Output node id
    node_labels: dict[int, str] = field(default_factory=dict)       # node id -> node_label (for culprit naming)
    variable_owners: dict[str, int] = field(default_factory=dict)   # "var_formula_123" -> node id
    date_format: str | None = None
    @classmethod
    def from_node(cls, node, phase="run") -> "ErrorContext": ...   # getattr-only, never raises, no Qt import
```

`shorten(text, limit)` collapses whitespace, truncates to `limit` with `…`. `normalise_path(p)` = `os.path.normcase(os.path.normpath(str(p).replace("/", os.sep)))`.

#### `translator.py`

```python
def translate_exception(
    exc: BaseException | str | None,
    *,
    node: object | None = None,        # duck-typed TriggerNode; used only through ErrorContext.from_node
    phase: str = "run",
    ctx: ErrorContext | None = None,
    redact: bool = False,
    traceback_text: str = "",
) -> NodeError:                        # NEVER raises; worst case TD-SYS-999 carrying the raw text

def translate_sql_diagnostic(exc: BaseException, formula_text: str, ctx: ErrorContext | None = None) -> dict:
    """Formula/Filter inline diagnostic: {"message", "category", "code", "hint"} (3.10)."""
```

Algorithm: (1) `ctx = ctx or ErrorContext.from_node(node, phase)`; (2) **unwrap**: `NodeExecutionError` with `original_exception` -> that exception (keep the wrapper only for timeout/memory by class name); `str`/`None` input becomes a synthetic `_TextError(text)` whose `type(e).__name__ == ""`; (3) `facts = Facts(names=[c.__name__ for c in type(e).__mro__], text=str(e) or repr(e), first_line=..., e=e)` (`str(e)` wrapped in try/except -> `repr(type(e))`); (4) walk `RULES` in order; the first rule whose `match(facts, ctx)` returns a `dict[str,str]` of params wins; (5) `build(code, params, ctx)` -> `NodeError` via `render_entry`; (6) post: did-you-mean (SCH-001/IN-003/EXP-002), redaction if `redact`, fingerprint, `created_at`, `traceback`. Any exception inside (1)-(6) is caught -> `_fallback(exc_text)` = `TD-SYS-999`.

#### `enrich.py`

```python
@dataclass
class EnrichJob:
    error: NodeError
    ancestors: tuple[Ancestor, ...] = ()           # sources -> nearest ancestor of the failing node; frame may be None
    inputs_of: dict[int, tuple[Any, ...]] = field(default_factory=dict)   # node id -> LazyFrames entering it (failing node AND ancestors)
    labels: dict[int, str] = field(default_factory=dict)                  # node id -> node_label
    titles: dict[int, str] = field(default_factory=dict)                  # node id -> class title
    ops: dict[int, str] = field(default_factory=dict)
    attribute: bool = True
    locate: bool = True
    row_cap: int = 5_000_000
    redact: bool = False

@dataclass
class EnrichResult:
    root: NodeError                 # replaces the provisional error (stored on culprit_node_id or the failing node)
    knock_on: NodeError | None      # TD-RUN-003 for the failing node when root sits on another node
    culprit_node_id: int | None

def enrich_error(job: EnrichJob) -> EnrichResult:    # never raises; <= ~15 s worst case (3.6)
```

### 3.3 The catalogue file (`core/errors/catalogue.py`)

```python
class Entry(TypedDict, total=False):
    severity: str                 # default "error"
    title: str                    # str.format template, NO node prefix
    title_located: str            # used when row_index is known (optional)
    detail: str
    detail_located: str           # used when row_index is known (optional)
    fixes: tuple[tuple[str, str], ...]   # (template, condition_param) ; condition "" = always; used when params[cond] truthy
    reserved: bool                # True = emitted by other plans/nodes, translator has no rule of its own (reached via rule 0 or make_error)
    passthrough: bool             # True = title is the exception's own message (3.5b)

CATALOGUE: dict[str, Entry] = {...}   # the table in 3.5, verbatim
def render_entry(code: str, params: Mapping[str, str | int], *, located: bool) -> tuple[str, str, tuple[str, ...]]
```

Rules for `render_entry`: unknown placeholders render as `?` (a `SafeDict` with `__missing__`); integers use `{row:,}`; `fixes` whose condition param is falsy are dropped; result `title` is `shorten(..., 90)`; `hint = fixes[0]`. `"{...}"` placeholders available everywhere: `{node_label}`, `{path}`, `{path_name}` (basename), `{column}`, `{columns}`, `{value}`, `{values}` (comma list), `{row}`, `{available}`, `{suggestion}`, `{suggestion_sentence}`, `{target}` (raw engine type), `{target_one}`, `{target_human}`, `{target_sql}`, `{op_past}`, `{reason}`, `{function}`, `{sheet}`, `{seconds}`, `{mb}`, `{left_key} {left_type} {right_key} {right_type}`, `{differences}`, `{culprit_label}`, `{message}`, `{engine}`.

A unit test (6) enforces: every key used by a rule exists in `CATALOGUE`; every non-reserved catalogue key has a rule; every placeholder is in the allowed list; every rendered title <= 90 chars; no `{`/`}` left after rendering; no emoji.

### 3.4 Observed exceptions (real outputs; the input to the catalogue)

Test frame: `Amount=["10","20","1,2O0.50","30"]`, `k=[1,2,3,4]`, `s=["a","b","c","d"]` (all `scan`/lazy). Messages trimmed to what matters.

| ID | Trigger (engine) | `module.Class` | Message (observed) |
|---|---|---|---|
| O1 | `select("Amnt")` / `filter(col("Amnt")>1)` / `sort("zz")` / `group_by("zz")` / `unique(subset=["zz"])` / `with_columns(col("zz")+1)` / `join(on="zz")` (Polars) | `polars.exceptions.ColumnNotFoundError` | `unable to find column "Amnt"; valid columns: ["Amount", "k", "s"]` + `Resolved plan until failure:` block |
| O2 | `drop("zz")`, `rename({"zz":"y"})` (Polars) | `polars.exceptions.ColumnNotFoundError` | `"zz" not found` (**no valid-columns list**; needs `ctx.input_columns` for suggestions) |
| O3 | `col("s").struct.field("q")` | `polars.exceptions.StructFieldNotFoundError` | `q` + plan block |
| O4 | `col("Amount").cast(pl.Int64)` / `Float64` / `Decimal(18,2)` / `cast(Int8)` on `300` / `str.strptime(pl.Date,...)` / `str.to_date()` / `cast(Date)` (Polars) | `polars.exceptions.InvalidOperationError` | ``conversion from `str` to `i64` failed in column 'Amount' for 1 out of 4 values: ["1,2O0.50"]`` ; date adds `You might want to try:` lines; `i64`->`i8`: ``conversion from `i64` to `i8` failed in column 'a' for 1 out of 1 values: [300]`` ; ``decimal[18,2]`` / ``decimal[5,2]`` spelled that way |
| O5 | same cast through `sink_csv` / `collect(engine="streaming")` on a 5 M-row CSV | `InvalidOperationError` | ``... for 1 out of 6158 values: ["1,2O0.50"]`` - **the "out of N" is the batch size under streaming, not the table size; never show it as a total** |
| O6 | `col("s").str.to_integer()` | `polars.exceptions.ComputeError` | ``strict integer parsing failed for 4 value(s): ["a", "b", … "d"]; error message for the first shown value: 'invalid digit found in string' (consider non-strict parsing)`` |
| O7 | `group_by("k").agg(col("Amount").sum())`, `select(col("Amount").mean())`, `cum_sum()` | `InvalidOperationError` | ``` `sum` operation not supported for dtype `str` ``` (also `mean`, `cum_sum`); **column name is not in the message** |
| O8 | `a.join(b, on="k")` (`k` i64 vs str), also `how="full"` and via `collect_schema()` | `polars.exceptions.SchemaError` | ``datatypes of join keys don't match - `k`: i64 on left does not match `k`: str on right (and no other type was available to cast to)`` |
| O9 | `pl.concat([a,b])` (vertical and diagonal with differing dtype) | `InvalidOperationError` | `'union'/'concat' inputs should all have the same schema,got` + `Schema { fields: {"k": Int64, "x": Int64}, metadata: () } and` + `Schema { fields: {"k": String, "y": Int64}, metadata: () }` |
| O10 | `select(col("k").alias("z"), col("s").alias("z"))` | `polars.exceptions.DuplicateError` | `projections contained duplicate output name 'z'. ...` |
| O11 | `rename({"k":"s"})` | `DuplicateError` | `column 's' is duplicate` |
| O12 | `join(df, on="a", suffix="")` | `DuplicateError` | `column with name 's' already exists` + `You may want to try:` |
| O13 | `pl.DataFrame([Series("a"), Series("a")])`, `hstack` | `DuplicateError` | `could not create a new DataFrame: column with name 'a' has more than one occurrence` |
| O14 | `scan_csv(missing).collect()` / `.collect_schema()` / `.head(10).collect()` ; `read_csv(missing)` | `builtins.FileNotFoundError` | `The system cannot find the file specified. (os error 2): C:/.../nope.csv` (`scan_csv(missing)` alone does **not** raise) |
| O15 | `sink_csv("<tmp>/nodir/x.csv")`, `sink_parquet(...)` | `FileNotFoundError` | `The system cannot find the path specified. (os error 3): C:/.../nodir/x.csv` |
| O16 | `sink_csv(<a directory>)` | `builtins.IsADirectoryError` | `expected a file path; 'C:\\...\\tmp' is a directory` |
| O17 | `sink_csv` / `write_csv` to a file another process holds open without sharing; `scan_csv` of it | `builtins.OSError` (**not** PermissionError; `errno` is `None`) | `The process cannot access the file because it is being used by another process. (os error 32): C:/.../locked.csv` |
| O18 | `sink_csv` to a read-only file | `builtins.PermissionError` (`errno None`) | `Access is denied. (os error 5): C:/.../ro.csv` |
| O19 | `sink_parquet("a<b.parquet")`, 400-char name | `builtins.OSError` | `The filename, directory name, or volume label syntax is incorrect. (os error 123): ...` (long path: message path is truncated with `...`) |
| O20 | `DataFrame.write_excel` without xlsxwriter | `builtins.ModuleNotFoundError` | `Excel export requires 'xlsxwriter' not found.` + `Please install using the command \`pip install xlsxwriter\`.` |
| O21 | `fastexcel.read_excel(missing.xlsx)` | `_fastexcel.CalamineError` | `calamine error: Xlsx error: I/O error: The system cannot find the file specified. (os error 2)` + `Context:` lines |
| O22 | `fastexcel.read_excel(<text file named .xlsx>)` / `pl.read_excel` | `_fastexcel.CalamineError` | `calamine error: Xlsx error: Zip error: invalid Zip archive: Could not find EOCD` |
| O23 | `load_sheet("Nope")` / `load_sheet(5)` | `_fastexcel.SheetNotFoundError` | `sheet with name "Nope" not found` + `Sheet "Nope" not found in file. Available sheets: "Data".` ; index: `sheet at index 5 not found` + `Sheet index 5 is out of range. File has 1 sheets.` |
| O24 | `scan_csv(<0-byte file>, infer_schema=False).collect()` | `polars.exceptions.NoDataError` | `empty CSV` |
| O25 | `scan_csv(<file with \xff\xfe>)` | `polars.exceptions.ComputeError` | `invalid utf-8 sequence` ; `encoding="utf8-lossy"` reads it (U+FFFD). Python-level `bytes.decode` raises `UnicodeDecodeError`: `'utf-8' codec can't decode byte 0xff in position 2: invalid start byte` (`.start`, `.reason` available) |
| O26 | `scan_csv` ragged file | `ComputeError` | `found more fields than defined in 'Schema'` + `Consider setting 'truncate_ragged_lines=True'.` (a duplicate header does **not** fail: Polars renames to `a_duplicated_0`) |
| O27 | `col("Amount") > 5` / `== 5` (string vs int) | `ComputeError` | `cannot compare string with numeric type (i32)` |
| O28 | `filter(col("a"))` (non-boolean) | `InvalidOperationError` | ``filter predicate must be of type `Boolean`, got `Int64` `` |
| O29 | `unnest("a")` on Int64 | `InvalidOperationError` | `invalid dtype: expected 'Struct', got 'Int64' for 'a'` |
| O30 | `str.replace("(", "x")` | `ComputeError` | `regex error: regex parse error:` / `(` / `^` / `error: unclosed group` |
| O31 | `pl.DataFrame({"a":[1,2],"b":[1]})`, `with_columns(Series len 2)` | `polars.exceptions.ShapeError` | `could not create a new DataFrame: height of column 'b' (1) does not match height of column 'a' (2)` ; `can't broadcast Series 'q' of length 2 to length 3` |
| O32 | `get(10)` / `gather([10])` | `polars.exceptions.OutOfBoundsError` | `gather indices are out of bounds` |
| O33 | DuckDB `SELECT *, Amnt+1 AS z FROM t` (also quoted, in `EXPLAIN`) | `_duckdb.BinderException` | `Binder Error: Referenced column "Amnt" not found in FROM clause!` / `Candidate bindings: "Amount"` (multiple: `"Amt2", "Amount"`) / `LINE 1: ...` ; `t.Amnt`: `Binder Error: Values list "t" does not have a column named "Amnt"` |
| O34 | DuckDB `CAST(Amount AS INTEGER/DOUBLE)` | `_duckdb.ConversionException` | `Conversion Error: Could not convert string '1,2O0.50' to INT32 when casting from source column Amount` (`DOUBLE`; `DECIMAL(18,2)` uses **double quotes**: `string "1,2O0.50" to DECIMAL(18,2)`) |
| O35 | DuckDB `CAST(d AS DATE)` | `ConversionException` | `Conversion Error: invalid date field format: "31/12/2024", expected format is (YYYY-MM-DD) when casting from source column d` |
| O36 | DuckDB `strptime(d,'%Y-%m-%d')` | `_duckdb.InvalidInputException` | `Invalid Input Error: Could not parse string "31/12/2024" according to format specifier "%Y-%m-%d"` + `Error: Literal does not match, expected -` |
| O37 | DuckDB `substr(s,'x')` | `ConversionException` | `Conversion Error: Could not convert string 'x' to INT64` (no source column) |
| O38 | DuckDB syntax | `_duckdb.ParserException` | `Parser Error: syntax error at or near "AS"` ; `unterminated quoted string at or near "'abc FROM t"` ; `syntax error at end of input` |
| O39 | DuckDB unknown function | `_duckdb.CatalogException` | `Catalog Error: Scalar Function with name lenght does not exist!` / `Did you mean "length"?` |
| O40 | DuckDB `upper(k,k)`, `Amount + 1`, `sum(s)` | `BinderException` | `Binder Error: No function matches the given name and argument types '+(VARCHAR, INTEGER_LITERAL)'. You might need to add explicit type casts.` (+ candidate list); `sum(VARCHAR)` likewise |
| O41 | DuckDB `Amount > 5` | `BinderException` | `Binder Error: Cannot compare values of type VARCHAR and type INTEGER_LITERAL - an explicit cast is required` |
| O42 | DuckDB ambiguous / scalar subquery | `BinderException` / `InvalidInputException` | `Ambiguous reference to column name "k" (use: "a.k" or "b.k")` / `More than one row returned by a subquery ...` |
| O43 | DuckDB memory limit | `_duckdb.OutOfMemoryException` | `Out of Memory Error: could not allocate block of size 256.0 KiB ...` |
| O44 | `NameError` from generated code | `builtins.NameError` | `name 'var_up_1' is not defined` |
| O45 | Executor timeout (`max_execution_time` 2 s in the probe) | `ExecutionTimeoutError` (our class) | `Code execution timed out after 2 seconds` (message is `...30.0 seconds` by default) |
| O46 | Executor memory check | `ExecutionMemoryError` | `Memory usage exceeded limit: 612.00MB` (**format only**: raised after exec by RSS delta; not provoked) |
| O47 | `MemoryError()` raised in node code (**simulated**) | `builtins.MemoryError` | `''` (empty `str`!) - executor then reports a traceback-only `result.error` (C1) |
| O48 | `PanicException` (**simulated**: `raise pe.PanicException('boom')`) | `polars.exceptions.PanicException`, MRO `BaseException` only | reported by executor as **success** (C3) |
| O49 | `File Output` unwired | `builtins.ValueError` (our code) | `File Output: no incoming data - connect an input` |
| O50 | SQLContext syntax | `polars.exceptions.SQLInterfaceError` | `sql parser error: Expected: an SQL statement, found: SELEC at Line: 1, Column: 1` |
| O51 | `pl.concat([])`, bad separator, `str.to_decimal()` w/o scale | `ValueError` / `TypeError` | `cannot concat empty list`; `separator="ab" should be a single byte character...`; `...missing 1 required keyword-only argument: 'scale'` (programming errors -> `TD-SYS-100`) |

Other observed facts used below: `difflib.get_close_matches("Amnt", [...], n=3, cutoff=0.6)` -> `['Amount']`; `"custmer id"` -> `['Customer Id']`; `"Totl"` -> `['Total']`; `"zz"` -> `[]`. Regexes below were tested against O4 and O34 text (`groupdict()` returned `{'src': 'str', 'dst': 'i64', 'col': 'Amount', 'n': '1', 'm': '4', 'vals': '"1,2O0.50", ...'}` and `{'val': '1,2O0.50', 'dst': 'INT32', 'col': 'Amount'}`).

### 3.5 Catalogue table (final strings; `CATALOGUE` = this table)

Prefix every rendered summary with `{node_label}: ` (rendering, not template). `[c]` = fix shown only when param `c` is truthy. `S` = severity (E error, W warning). **Rule#** is the row in 3.7. Reserved = emitted by other plans or by node code via `make_error`, no translator rule.

| Code | S | Rule# | Title (`title_located`) / detail / fixes |
|---|---|---|---|
| TD-IN-001 | E | 8 | T: `The file '{path_name}' was not found.` D: `Looked for: {path}` F: `Check that the file exists and that the drive or network share is reachable.` / `Choose the file again with Browse in the File Input node.` |
| TD-IN-002 | E | 8 | T: `'{path_name}' cannot be read: it is open in another program or access is denied.` D: `{reason}` F: `Close the file in Excel or any other program, then run again.` / `Ask for read permission on the folder.` |
| TD-IN-003 | E | 6 | T: `Sheet '{sheet}' does not exist in '{path_name}'.` D: `Available sheets: {available}.{suggestion_sentence}` F: `Pick one of the available sheets in the node settings.` / `Use the sheet '{suggestion}' instead.` [suggestion] |
| TD-IN-004 | E | 9 | T: `'{path_name}' is not UTF-8 text.` D: `The file contains bytes that are not valid UTF-8, typical for files saved by older Excel versions.` F: `Open the file in Excel or Notepad and save it again as 'CSV UTF-8'.` |
| TD-IN-005 | E | 10 | T: `'{path_name}' is empty.` D: `The file has no header and no rows.` F: `Check that the export that produced the file finished, then reload it.` |
| TD-IN-006 | E | 12 | T: `'{path_name}' is not a readable Excel workbook.` D: `{reason}` F: `Open it in Excel and save it again as .xlsx.` / `If it is really a text file, rename it to .csv and choose File type CSV.` |
| TD-IN-007 | E | 11 | T: `Some rows have more fields than the header.` D: `Usually the wrong delimiter or an unquoted delimiter inside a value.` F: `Check the delimiter in the node settings.` / `Make sure values containing the delimiter are wrapped in quotes.` |
| TD-SCH-001 | E | 20,21 | T: `Column '{column}' was not found.` D: `Available columns: {available}.{suggestion_sentence}` F: `Use the column '{suggestion}' instead.` [suggestion] / `Select the column again in this node; it may have been renamed, dropped or typed differently upstream.` |
| TD-SCH-002 | E | 19 | T: `The column name '{column}' appears more than once.` D: `Every column needs a unique name.` F: `Rename one of the columns with a Select node before this step.` |
| TD-SCH-003 | W | - | reserved (plan 01: schema drift). T: `The columns in '{path_name}' changed since the workflow was saved.` D: `{differences}` F: `Review the nodes that use the changed columns.` |
| TD-SCH-004 | E | 18 | T: `The two tables have different columns or types.` D: `Differences: {differences}` F: `Make both inputs have the same columns and types (use Select nodes), or use a mode that fills missing columns.` |
| TD-SCH-005 | E | 26 | T: `Columns have different numbers of rows.` D: `{reason}` F: `Check the upstream step that builds these columns from separate lists.` |
| TD-TYP-001 | E | 13,14,15 | T: `Column '{column}' has values that cannot be read as {target_human}.` TL: `Column '{column}' contains '{value}' in row {row:,}, which cannot be read as {target_human}.` D: `{reason}` DL: `{others_sentence}` F: `Clean or correct the value{row_hint} in the source data.` / `Add a Select node before this one and set '{column}' to {target_one}; values that cannot be converted become empty instead of stopping the run.` / `In the formula, use TRY_CAST([{column}] AS {target_sql}) so bad values become empty.` [engine_duckdb] |
| TD-TYP-002 | E | 17 | T: `Join keys have different types: '{left_key}' is {left_type} but '{right_key}' is {right_type}.` D: `Both key columns must hold the same type of value.` F: `Add a Select node on one side and set the key column to the same type (usually Text).` / `Check that both columns really contain the same kind of value.` |
| TD-TYP-003 | E | 22 | T: `Column '{column}' is text, so it cannot be {op_past}.` TL: `Column '{column}' contains text ('{value}') in row {row:,}, so it cannot be {op_past}.` D: `{reason}` DL: `{others_sentence}` F: `Clean or correct the value{row_hint}.` / `Add a Select node before this one and set '{column}' to Decimal.` |
| TD-TYP-004 | E | 23 | T: `Text and numbers cannot be compared.` D: `{reason}` F: `Set the column to a number type with a Select node, or put the value in quotes if the column is text.` |
| TD-TYP-005 | E | 13 | T: `A value in '{column}' does not fit in the target type ({target}).` TL: `'{value}' in row {row:,} of '{column}' does not fit in the target type ({target}).` D: `{reason}` F: `Use a wider type (for example Int64 or Decimal) in a Select node.` |
| TD-TYP-006 | E | 25 | T: `This step needs a {expected} column but '{column}' is {got}.` F: `Check which column this node uses and its type in the Select node.` |
| TD-TYP-007 | E | 24 | T: `The filter condition must give true or false, not {got}.` F: `Write a comparison such as [Amount] > 0.` |
| TD-EXP-001 | E | 27 | T: `The expression has a syntax error.` D: `{reason}` F: `Check brackets, quotes and operators near the marked spot.` |
| TD-EXP-002 | E | 28 | T: `Unknown function '{function}'.` D: `{suggestion_sentence}` F: `Use '{suggestion}' instead.` [suggestion] / `Check the function name in the formula help list.` |
| TD-EXP-003 | E | 30 | T: `The expression cannot be evaluated.` D: `{reason}` F: `Check the column names and types used in the expression.` |
| TD-EXP-004 | E | 29 | T: `The pattern (regular expression) is not valid.` D: `{reason}` F: `Escape special characters such as ( ) [ ] with a backslash.` |
| TD-EXP-005 | E | 31 | T: `A function received a value it cannot use.` D: `{reason}` F: `Check the arguments of the function, or use TRY_CAST for conversions.` |
| TD-JOI-001 | E | - | reserved (nodes via `make_error`). T: `No columns are mapped.` F: `Map at least one column in the node settings.` |
| TD-JOI-002 | E | - | reserved. T: `Both inputs must be connected.` F: `Connect a node to each input.` |
| TD-OUT-001 | E | 8 | T: `The output folder does not exist.` D: `Could not create '{path}' because its folder is missing.` F: `Create the folder, or choose an existing one in the File Output node.` |
| TD-OUT-002 | E | 8 | T: `'{path_name}' cannot be written: it is open in another program or read-only.` D: `{reason}` F: `Close the file in Excel or any other program, then run again.` / `Choose a different file name or clear the read-only flag.` |
| TD-OUT-003 | E | 4 | T: `Excel export is not available in this installation.` D: `The component that writes .xlsx files (xlsxwriter) is missing.` F: `Export as CSV or Parquet instead.` / `Reinstall the application.` |
| TD-OUT-004 | E | 8 | T: `'{path_name}' is not a valid output file name.` D: `{reason}` F: `Remove characters such as < > : " | ? * and keep the path short.` / `Choose a file, not a folder.` |
| TD-OUT-005 | E | 8 | T: `The disk is full.` D: `Could not finish writing '{path_name}'.` F: `Free some space or write to another drive.` |
| TD-OUT-006 | E | 5 | T: `Nothing is connected to this output.` F: `Connect the node whose result you want to save to the File Output node.` |
| TD-RUN-001 | E | 1 | T: `This step took longer than {seconds} seconds and was stopped.` D: `Large inputs or heavy joins can exceed the limit.` F: `Filter or sample the data earlier in the workflow.` / `Write large results to Parquet instead of CSV or Excel.` |
| TD-RUN-002 | E | 2 | T: `This step ran out of memory.` D: `{reason}` F: `Filter rows or drop unused columns earlier in the workflow.` / `Close other programs and run again.` |
| TD-RUN-003 | E | - | knock-on. T: `Stopped because '{culprit_label}' has a problem.` D: `The problem is in the earlier step, not in this one.` F: `Fix '{culprit_label}' first, then run again.` |
| TD-RUN-004 | W | - | T: `The run was cancelled before this step.` F: `Run the workflow again.` |
| TD-RUN-005 | W | - | knock-on. T: `Input {input_number} is not connected.` F: `Connect a node to this input.` |
| TD-RUN-006 | E | 33 | T: `This step needs the result of an earlier step that is not available.` D: `{reason}` F: `Fix the earlier step ('{culprit_label}') and run again.` [culprit_label] / `Open the earlier step so it is calculated, then run again.` |
| TD-RUN-008 | W | - | knock-on. T: `Skipped because '{culprit_label}' failed.` D: `Independent branches of the workflow still ran.` F: `Fix '{culprit_label}' and run again.` |
| TD-SYS-001 | E | - | legacy wrapper for per-node tooltips/`ValueError` text. T: `{message}` F: `Check this node's settings.` |
| TD-SYS-100 | E | 34,35 | T: `The data engine could not run this step.` D: `{reason}` F: `Check the node settings and the upstream data; copy the details if you need help.` |
| TD-SYS-998 | E | 3 | T: `The data engine stopped unexpectedly.` D: `This is an internal engine error, not a problem with your data.` F: `Run again; if it repeats, copy the details and report it.` |
| TD-SYS-999 | E | 36 | T: `Something unexpected went wrong.` D: `{reason}` F: `Copy the details and report it if it repeats.` |

#### 3.5b Codes owned by other plans (pass-through catalogue entries)

These codes are raised by other plans' Qt-free cores as exceptions that already carry the code and a plain sentence. Catalogue flag `passthrough: True` means: **title = the exception's own message (code prefix stripped), `hint` = the hint below**; severity as listed. They are pasted from the owning plans' tables (plan 04 validation table, plan 07 `ERROR_CODES`, plan 08 section 3.4, plan 01 `InputReadError` kinds); the owners keep the wording authoritative, this table only adds hints. Add a code here **before** raising it elsewhere (`test_every_plan_code_is_in_catalogue`).

| Code | S | Title (generic wording; the exception message is used when present) | Hint |
|---|---|---|---|
| TD-AUDIT-001 | E | `Choose the {label} column.` | Pick the column in the node settings. |
| TD-AUDIT-002 | E | `Column '{col}' is not in the input data.` | Pick the column again; it may have been renamed upstream. |
| TD-AUDIT-003 | E | `Column '{col}' holds nested values and cannot be used for this test.` | Choose a plain text, number or date column. |
| TD-AUDIT-004 | E | `{label} must be {rule}.` | Enter a value inside the allowed range. |
| TD-AUDIT-005 | E | `The input already has a column named '{name}', which this node adds.` | Rename the existing column first. |
| TD-AUDIT-006 | E | `'{text}' is not a date. Use YYYY-MM-DD.` | Type the date as year-month-day. |
| TD-AUDIT-007 | E | `Date format '{fmt}' is not supported.` | Choose one of the formats in the list. |
| TD-AUDIT-008 | E | `Switch on at least one risk test.` | Tick at least one test in the node settings. |
| TD-AUDIT-009 | E | `{label}: {detail}.` | Fix the list of numbers (count and order). |
| TD-AUDIT-010 | E | `No row has a readable amount in '{col}', so a value-based sample cannot be drawn.` | Choose a numeric amount column or clean the values. |
| TD-AUDIT-101 | W | `Only {n:,} rows were tested; at least {min:,} are needed for a reliable result.` | Treat the result as indicative only. |
| TD-AUDIT-102 | W | `{n:,} values could not be read as {kind} and were skipped.` | Clean those values or convert the column with a Select node. |
| TD-AUDIT-103 | W | `Requested {k:,} but only {n:,} rows exist; the whole population was selected.` | Lower the sample size. |
| TD-SHAPE-001 | E | `A required setting is missing` | Fill in the missing setting. |
| TD-SHAPE-002 | E | `An output column name is empty, duplicated or already exists` | Choose a unique name. |
| TD-SHAPE-003 | E | `A selected column is not in the input any more` | Select the column again. |
| TD-SHAPE-004 | E | `A setting value is out of range or unknown` | Pick a value from the list or inside the range. |
| TD-SHAPE-005 | E | `A required input has no data` | Connect and fix the upstream node. |
| TD-SHAPE-040 | E | `The pattern is not a valid regular expression` | Escape special characters with a backslash. |
| TD-SHAPE-041 | E | `The pattern is too long` | Shorten the pattern. |
| TD-SHAPE-042 | E | `Find text is empty` | Type the text to find. |
| TD-SHAPE-043 | E | `Too many rules` | Remove rules or split them over two nodes. |
| TD-SHAPE-044 | E | `The column must be text` | Convert the column to text with a Select node. |
| TD-SHAPE-050 | E | `The column is not a date and not text` | Choose a date or text column. |
| TD-SHAPE-052 | E | `A holiday is not a YYYY-MM-DD date` | Type holidays as year-month-day. |
| TD-SHAPE-053 | E | `Working days must name at least one weekday` | Tick at least one weekday. |
| TD-SHAPE-060 | E | `Index, header and value columns must be different` | Pick three different columns. |
| TD-SHAPE-061 | E | `Too many new columns` | Filter the header column to fewer distinct values. |
| TD-SHAPE-070 | E | `Amount or date column is set on one side only` | Pick it on both sides, or on neither. |
| TD-SHAPE-071 | E | `Add a key column pair or a date column` | Add a key pair or a date window. |
| TD-SHAPE-072 | E | `Too many possible matches` | Add key columns or narrow the tolerance. |
| TD-SHAPE-081 | E | `Too many possible fuzzy pairs` | Add a blocking key or filter earlier. |
| TD-SHAPE-082 | E | `Too many rows to compare without blocking` | Add a blocking column. |
| TD-SHAPE-091 | E | `The column must be a number` | Convert the column with a Select node. |
| TD-SHAPE-101 | E | `The split pattern can match nothing` | Change the split pattern. |
| TD-SHAPE-110 | E | `Only one SQL statement is allowed` | Remove the extra statements. |
| TD-SHAPE-111 | E | `Only SELECT queries are allowed` | Rewrite it as a SELECT. |
| TD-SHAPE-112 | E | `A file, system or random function is not allowed` | Remove that function. |
| TD-SHAPE-113 | E | `The SQL could not be parsed or run` | Check the SQL near the reported text. |
| TD-SHAPE-114 | E | `The SQL is too long` | Shorten the statement. |
| TD-SHAPE-115 | E | `The query took too long` | Filter the data before the query. |
| TD-SHAPE-120 | E | `The formula must contain {col}` | Add {col} to the formula. |
| TD-CLI-001 | E | `The workflow file could not be read.` | Check the path and that it is a .tds file. |
| TD-CLI-002 | E | `The workflow was saved by a newer Trigger Designer.` | Update this program. |
| TD-CLI-003 | E | `The workflow uses an unknown node type.` | Open and re-save it in a compatible version. |
| TD-CLI-004 | E | `The workflow has a cycle.` | Remove the connection that loops back. |
| TD-CLI-005 | E | `Unknown or missing parameter.` | Use one of the listed parameter names. |
| TD-CLI-006 | E | `A parameter value is not valid.` | Use the example format shown. |
| TD-CLI-007 | E | `This parameter target is not supported.` | Choose a supported setting. |
| TD-CLI-008 | E | `The workflow has not been approved to run unattended.` | Approve it first (`approve`). |
| TD-CLI-009 | E | `The approved workflow changed since approval.` | Approve it again. |
| TD-CLI-010 | E | `The generated code was refused by the safety policy.` | Remove the flagged node or setting. |
| TD-CLI-011 | E | `A custom-code node was refused.` | Remove the custom-code node. |
| TD-CLI-012 | E | `Another run of this workflow is in progress.` | Wait and try again. |
| TD-CLI-013 | E | `The outputs could not be saved.` | Close the output files in other programs and run again. |
| TD-CLI-014 | E | `The output folder is missing or not writable.` | Create it or use `--create-output-dirs`. |
| TD-CLI-015 | E | `There is not enough free disk space.` | Free space or lower `--min-free-mb`. |
| TD-CLI-016 | E | `The scheduler could not be configured.` | Check Windows Task Scheduler permissions. |
| TD-CLI-017 | E | `The run log failed verification.` | Treat the log as modified. |
| TD-CLI-018 | W | `This workflow writes no files.` | Add a File Output node. |

**Plan 01 input errors** (plan 01 section 3 is the source of truth; titles/hints copied from its code table; pass-through, severity E). TD-IN-004, TD-IN-006, TD-IN-007, TD-SCH-002, TD-SCH-003 keep this plan's meanings; none of this plan's own codes uses TD-IN-010..014 or TD-SCH-010/011.

| Code | Title | Hint |
|---|---|---|
| TD-IN-010 | I could not read the data in this file | Check the file type and delimiter; the details name the column. |
| TD-IN-011 | The input file could not be opened | Check the path and your access rights. |
| TD-IN-012 | The folder matches too many files | Narrow the include pattern or raise "Max files". |
| TD-IN-013 | The database could not be read as requested | Check the table name and use a single SELECT statement; databases are read-only. |
| TD-IN-014 | The File Input settings need attention | Open File Input and fix the highlighted setting. |
| TD-SCH-010 | An added column name already exists in the data | Rename the filename/sheet column in File Input. |
| TD-SCH-011 | Files in the folder have different columns | Use "Union by name" or fix the odd file named in the details. |

**Plan 06 workpaper errors** (plan 06 section 10.3 is the source of truth; pass-through, severity E). Single definition each; this plan defines no other `TD-OUT-007`/`TD-OUT-010..014`:

| Code | Title | Hint |
|---|---|---|
| TD-OUT-010 | A workpaper with this name already exists | Choose another file name, or set "If the file exists" to New version. |
| TD-OUT-011 | The table has too many columns for Excel | Excel allows at most 16,384 columns; select fewer columns before writing. |
| TD-OUT-012 | The workpaper settings are not valid | Check the output file (it must end in .xlsx) and the Prepared on date (YYYY-MM-DD). |
| TD-OUT-013 | The table is too large for an Excel sheet | An Excel sheet holds at most 1,048,575 data rows; save it as CSV or Parquet instead. |
| TD-OUT-014 | Excel could not create the workbook | A sheet name or cell content is not valid for Excel; rename the sheet or shorten the text. |

**Mapping table plan 01 uses** (`InputReadError.kind` -> `.code`, as in plan 01; this plan only adopts it):

```
file_not_found -> TD-IN-001   no_match -> TD-IN-001    permission -> TD-IN-002   locked -> TD-IN-002
sheet_missing  -> TD-IN-003   encoding -> TD-IN-004    empty_file -> TD-IN-005
parse -> TD-IN-010   unreadable -> TD-IN-011   too_many_files -> TD-IN-012   db_error -> TD-IN-013   config -> TD-IN-014
schema_mismatch -> TD-SCH-011   column_conflict -> TD-SCH-010
unsupported_source, no_readable_files -> TD-IN-014 ;  db_forbidden -> TD-IN-013
corrupt workbook (parse + "invalid Zip archive"/"EOCD") -> TD-IN-006 ; ragged CSV rows -> TD-IN-007
```

Param derivations used by templates: `target` = the raw engine type as reported (`i64`, `INT32`, `decimal[18,2]`); `target_one` / `target_human` (singular / plural noun phrase) from it: `i8..i64/u8..u64/TINYINT..BIGINT/INT32`->`a whole number` / `whole numbers`, `f32/f64/DOUBLE/FLOAT`->`a number` / `numbers`, `decimal[..]/DECIMAL(..)`->`a decimal number` / `decimal numbers`, `date/DATE`->`a date` / `dates`, `datetime/TIMESTAMP`->`a date and time` / `dates and times`, `time`->`a time` / `times`, `bool/BOOLEAN`->`a true/false value` / `true/false values`, anything else -> the raw type name for both; `target_sql` = DuckDB type name (`INTEGER`, `DOUBLE`, `DECIMAL(18,2)`, `DATE`, `TIMESTAMP`, default `DOUBLE`); `op_past` from `{sum:"summed", mean:"averaged", cum_sum:"added up", min:"compared", max:"compared", median:"averaged", std:"averaged", var:"averaged"}` default `"used in this calculation"`; `row_hint` = `f" (row {row:,})"` when located else `""`; `others_sentence` = `f"{n} more value(s) are also invalid, for example {values}."` when `len(sample_values)>1`; `suggestion_sentence` = `f" Did you mean '{s}'?"` when a suggestion exists; `engine_duckdb` = `"1"` for DuckDB-sourced errors; `reason` = `shorten(first useful line of the engine message with plan/`LINE`/`Candidate` blocks removed, 160)`.

### 3.6 Cast-failure locator (exact algorithm and cost cap)

`core/errors/locator.py`:

```python
@dataclass(frozen=True)
class LocateResult:
    status: str                    # found | not_found | skipped | timeout | error
    row_index: int | None = None   # 1-based, first offending row
    values: tuple[str, ...] = ()   # <= max_values, de-duplicated, display-safe
    scanned_rows: int = 0
    elapsed_s: float = 0.0
    cap_hit: bool = False

def polars_dtype_from_name(name: str) -> pl.DataType | None
    # "i8".."i64","u8".."u64","f32","f64","bool","date","time","str"/"String",
    # "decimal[18,2]" -> pl.Decimal(18,2); "datetime[us]"/"datetime[ms]" -> pl.Datetime(..);
    # DuckDB: TINYINT/INT1->Int8, SMALLINT->Int16, INT32/INTEGER->Int32, INT64/BIGINT->Int64, FLOAT->Float32,
    # DOUBLE->Float64, DECIMAL(p,s)->Decimal, DATE->Date, TIMESTAMP->Datetime("us"), BOOLEAN->Boolean; else None.

def probe_expr(column: str, target: pl.DataType, *, date_format: str | None = None) -> pl.Expr:
    src = pl.col(column)
    if target == pl.Date:      return src.str.to_date(format=date_format, strict=False)
    if isinstance(target, pl.Datetime): return src.str.to_datetime(format=date_format, strict=False)
    return src.str.strip_chars().cast(target, strict=False)      # strip: DuckDB trims, Polars does not; avoids false hits

def locate_conversion_failures(
    frames: Sequence[pl.LazyFrame | pl.DataFrame],   # frames entering the failing/culprit node
    column: str, target: pl.DataType | None, *,
    known_value: str | None = None,                  # DuckDB reports exactly one value: used to find its row
    sum_mode: bool = False,                          # TYP-003: target = Float64, source must be String
    date_format: str | None = None,
    row_cap: int = 5_000_000, max_values: int = 5, max_chars: int = 80,
) -> LocateResult
```

Steps (the code must follow these literally):

1. Pick the first frame whose `collect_schema()` contains `column` (wrap in try/except -> `skipped`). If none, `skipped`.
2. `lf = frame.lazy().head(row_cap).with_row_index("__r", offset=1)` (row index **before** any filter so it is the position in the input).
3. Query A (offenders; the only query for Polars-origin errors):
   `bad = pl.col(column).is_not_null() & probe_expr(column, target).is_null()` when the source dtype is `String`; for non-String sources (e.g. `i64`->`i8` overflow) use `pl.col(column).cast(target, strict=False).is_null() & pl.col(column).is_not_null()`.
   `lf.filter(bad).select("__r", pl.col(column).cast(pl.String).alias("__v")).head(max_values).collect(engine="streaming")`.
4. Query B (only when `known_value` is given and not among query A's values): `lf.filter(pl.col(column).cast(pl.String) == known_value).select("__r", "__v").head(1).collect(engine="streaming")`; prepend its row/value (DuckDB reports the exact first bad value, so its row is exact even if Polars' probe disagrees on whitespace semantics).
5. `row_index` = first row's `__r` (min of A/B `__r` if both). `values` = distinct `__v` in row order, each passed through `_display(v, max_chars)`: escape control chars (`\n`->`\\n`), replace `U+FFFD`/lone surrogates via `errors="replace"`, truncate to `max_chars` + `…`.
6. Status: rows found -> `found`; none -> `not_found` and `cap_hit = (scanned_rows >= row_cap)` (scanned_rows = `row_cap` if `frame.height >= cap` is unknown for lazy: set `cap_hit=True` whenever not found, then the message says "not found in the first {row_cap:,} rows"). Any exception -> `error` (never raised to the caller; logged at DEBUG).

**Cost cap (all enforced; numbers measured with `obs3.py` on this machine):**

| Case | Measured |
|---|---|
| 5,000,000-row CSV (`scan_csv`, `infer_schema=False`), bad row 4,210, `head(2_000_000)` + streaming | **0.041 s** |
| same file, bad value at the very end, full 5 M rows | **0.151 s** |
| same file, no hit inside `head(2_000_000)` | 0.081 s |
| 5 M-row in-memory String column, clean, `head(2_000_000)` | 0.006 s |

Caps: `row_cap` 5,000,000 rows (pref `errors/locate_row_cap`), **at most 2 queries**, `max_values` 5, `max_chars` 80, and a **10 s wall-clock abandon** in `ErrorEnricher` (the runnable's result is ignored if it arrives later; `locate_status="timeout"`). Pipeline-breaking upstream plans (sort/group/join before the node) can be slower than the table above - that is what the 10 s abandon is for; the abandoned query keeps running on a daemon pool thread but never blocks the UI or the next Run.

### 3.7 Ordered translator rules

`RULES: list[Rule]`; `Rule = (id, codes, names, pattern, build)`. Matching = (class name in `names` **or** `names == ANY`) **and** `pattern.search(facts.text)` when a pattern is given; first match wins. Class names are compared as strings (`"PanicException"`) so optional libraries (`_fastexcel`, `_duckdb`) need no import. Regexes are compiled once with `re.DOTALL`.

| # | Code | Class names (any of) | Pattern (key groups) | Params produced |
|---|---|---|---|---|
| 0 | (code carried by the exception) | any class | exception has attribute `code` (str) starting `TD-`, **or** `str(e)` matches `(?:^|\[)(?P<code>TD-[A-Z]+-\d{3})(?:\]|:)` (covers `[TD-SHAPE-003] ...` and `TD-AUDIT-001: ...`) | looked up in `CATALOGUE`; params from `e.params` (dict) / `e.columns` / `e.path` / `e.sheet` / `e.kind` when present; `message` = text after the code prefix. Known code: `passthrough` entries use the message as `title` (catalogue title when the message is empty), others render their template. **Unknown `TD-` code: build `NodeError(code=<code>, title=shorten(message,90), severity="error", technical=str(e))` with no hint (never an error, never falls to SYS-999).** Plan 06's `ExcelWriteError.code` and plan 01's `InputReadError.code` use this rule. Skipped when `code` is not a string starting `TD-`. |
| 1 | RUN-001 | `ExecutionTimeoutError` | `timed out after (?P<seconds>[\d.]+) seconds` (also matches without class) | seconds (strip trailing `.0`) |
| 2 | RUN-002 | `ExecutionMemoryError`, `MemoryError`, `OutOfMemoryException` | none / `Memory usage exceeded limit: (?P<mb>[\d.]+)MB` / `Out of Memory Error` | reason (`"Limit exceeded by {mb} MB."` or `"No more memory could be allocated."`) |
| 3 | SYS-998 | `PanicException` | - | reason=text |
| 4 | OUT-003 | `ModuleNotFoundError`, `ImportError` | `xlsxwriter` | - |
| 5 | OUT-006 | `ValueError` | `no incoming data - connect an input` | - |
| 6 | IN-003 | `SheetNotFoundError` | ``sheet with name "(?P<sheet>.*?)" not found`` or `Sheet index (?P<sheet>\d+) is out of range`; `Available sheets: (?P<avail>.*?)\.?\s*$` -> quoted names | sheet, available, suggestion (3.8) |
| 7 | IN-006 (OS-coded) | `CalamineError`, `FastExcelError` | `\(os error (?P<n>\d+)\)` -> **delegate to rule 8 with the number** | - |
| 8 | IN-001/002, OUT-001/002/004/005 | `FileNotFoundError`, `PermissionError`, `IsADirectoryError`, `NotADirectoryError`, `OSError`, `CalamineError` | `\(os error (?P<n>\d+)\)(?::\s*(?P<path>.+?))?\s*$` or class-only | decision below |
| 9 | IN-004 | `UnicodeDecodeError`, `ComputeError` | `invalid utf-8 sequence` (or class `UnicodeDecodeError`) | reason from `e.reason/e.start` when available |
| 10 | IN-005 | `NoDataError` | `empty CSV` | path from ctx if single input |
| 11 | IN-007 | `ComputeError` | `found more fields than defined in 'Schema'` | - |
| 12 | IN-006 | `CalamineError`, `FastExcelError` | `Zip error\|invalid Zip archive\|calamine error` | reason (first line) |
| 13 | TYP-001 / TYP-005 | `InvalidOperationError`, `ComputeError` | ``conversion from `(?P<src>[^`]+)` to `(?P<dst>[^`]+)` failed in column '(?P<col>.+?)' for (?P<n>\d+) out of (?P<m>\d+) values: \[(?P<vals>.*?)\]\s*$`` (MULTILINE) | column, target, source, `value` = first parsed element of `vals`, `failing_count=n` **only if phase=="live"** (O5); code = TYP-005 when `src` and `dst` both match `^(i\|u)\d+$\|^f\d+$`, else TYP-001; `engine_polars` |
| 14 | TYP-001 | `ComputeError` | ``strict integer parsing failed for (?P<n>\d+) value\(s\): \[(?P<vals>.*?)\]`` | target=`i64`, column=first of ctx.referenced_columns that is String (else ""), value |
| 15 | TYP-001 | `ConversionException`, `InvalidInputException` | `Could not convert string (?P<q>['"])(?P<val>.*?)(?P=q) to (?P<dst>[A-Z0-9_(),\s]+?)(?: when casting from source column (?P<col>.+?))?\s*(?:\n\|$)` ; or `invalid date field format: "(?P<val>.*?)", expected format is .*?(?: when casting from source column (?P<col>.+?))?\s*(?:\n\|$)` (dst=`DATE`) ; or `Could not parse string "(?P<val>.*?)" according to format specifier "(?P<fmt>.*?)"` (dst=`DATE`, date_format=fmt, column from ctx); or `^Conversion Error: (?P<reason>.*)` | column (may be ""), target, value (= `known_value`), `engine_duckdb=1` |
| 17 | TYP-002 | `SchemaError` | ``datatypes of join keys don't match - `(?P<left_key>[^`]+)`: (?P<left_type>\S+) on left does not match `(?P<right_key>[^`]+)`: (?P<right_type>\S+) on right`` | all four; columns=(left_key,right_key) |
| 18 | SCH-004 | `InvalidOperationError`, `SchemaError` | `'union'/'concat' inputs should all have the same schema,got\s+Schema \{ fields: \{(?P<a>.*?)\}, metadata.*?\} and\s+Schema \{ fields: \{(?P<b>.*?)\}, metadata` | `differences` built by parsing `"name": Type` pairs: `missing in right: ...; only in right: ...; type differs: k (Int64 vs String)` |
| 19 | SCH-002 | `DuplicateError` | any (also text `has more than one occurrence\|already exists\|is duplicate\|duplicate output name`) | column = first `'(?P<c>[^']+)'` in text |
| 20 | SCH-001 | `ColumnNotFoundError`, `StructFieldNotFoundError`, `SchemaFieldNotFoundError` | ``unable to find column "(?P<col>.*?)"; valid columns: \[(?P<valid>.*?)\]`` or `^"(?P<col>.*?)" not found` or (struct) first line | column, available (from message else `ctx.input_columns`) |
| 21 | SCH-001 | `BinderException` | `Referenced column "(?P<col>.*?)" not found in FROM clause!(?:\s*Candidate bindings: (?P<cands>.*?)\n)?` or `does not have a column named "(?P<col>.*?)"` | column, available = cands unquoted else ctx.input_columns, `engine_duckdb=1` |
| 22 | TYP-003 | `InvalidOperationError`, `BinderException` | ``` `(?P<op>\w+)` operation not supported for dtype `(?P<dtype>[^`]+)` ``` or `No function matches the given name and argument types '(?P<fn>[^(']+)\((?P<args>[^)]*)\)'` | op (`fn` for DuckDB), `dtype`; **column inference**: candidates = `[c for c in ctx.referenced_columns if ctx.input_dtypes.get(c)=="String"]`, else all String columns in `ctx.input_columns` (max 5); `column`=candidates[0], `columns`=tuple(candidates); `sum_mode=1`; when the dtype/args are not text (`dtype != str` and `VARCHAR not in args`) -> falls to rule 30 |
| 23 | TYP-004 | `ComputeError`, `BinderException` | `cannot compare string with numeric type` / `Cannot compare values of type (?P<a>\w+) and type (?P<b>\w+)` | reason |
| 24 | TYP-007 | `InvalidOperationError` | ``filter predicate must be of type `Boolean`, got `(?P<got>[^`]+)` `` | got |
| 25 | TYP-006 | `InvalidOperationError` | `invalid dtype: expected '(?P<expected>[^']+)', got '(?P<got>[^']+)' for '(?P<column>[^']+)'` | all |
| 26 | SCH-005 | `ShapeError` | any | reason |
| 27 | EXP-001 | `ParserException`, `SQLSyntaxError`, `SQLInterfaceError` | `(?:Parser Error: )?(?P<reason>.*)` | reason (first line; `unterminated quoted string` -> `A text value is missing its closing quote.`; `syntax error at end of input` -> `The expression ends too early.`; `syntax error at or near "X"` -> `Unexpected 'X'.`) |
| 28 | EXP-002 | `CatalogException` | `(?:Scalar\|Aggregate\|Table) Function with name (?P<function>\S+) does not exist!(?:\s*Did you mean "(?P<sug>[^"]+)"\?)?` | function, suggestion (DuckDB's own, else difflib over `["length","lower","upper","trim","coalesce","round","substr","replace","concat","strptime","strftime","try_cast"]`) |
| 29 | EXP-004 | `ComputeError` | `regex error: regex parse error:.*?error: (?P<reason>[^\n]+)` | reason |
| 30 | EXP-003 | `BinderException`, `CatalogException` | any (leftovers: ambiguous column, wrong argument count, unknown table) | reason |
| 31 | EXP-005 | `InvalidInputException`, `ConversionException` | any (leftovers) | reason |
| 33 | RUN-006 | `NameError`, `UnboundLocalError` | `name '(?P<var>[^']+)' is not defined` | var -> `ctx.variable_owners[var]` => culprit id/label |
| 34 | SYS-100 | `InvalidOperationError`, `ComputeError`, `OutOfBoundsError`, `PolarsError` subclasses, `ValueError`, `TypeError` | any | reason (first line) |
| 35 | SYS-100 | `PolarsError`-like by module name `polars` | any | reason |
| 36 | SYS-999 | everything else | - | reason = `shorten(text or repr, 160)` |

Rule 0 (pass-through) runs before everything else, including the unwrap of `NodeExecutionError.original_exception`. Rule numbers 16 and 32 are intentionally unused (the numbers are referenced from the catalogue table 3.5 and from tests; do not renumber).

**Rule 8 decision (I/O errors).** Parse `n` (OS error number; if absent derive from class: `FileNotFoundError`->2, `PermissionError`->5, `IsADirectoryError`->21). Extract `path` from the message (`(os error N): <path>`; `...` truncation allowed) else `e.filename`. `p = normalise_path(path)`. `role = "out"` if `p in ctx.output_paths` or `dirname(p) in {dirname(q) for q in ctx.output_paths}`; `role = "in"` if `p in ctx.input_paths`; if both/neither: `role = "out"` when `type(e)` came from a node whose `ctx.op` ends with `file_output`, else `"in"`. Then:

| `n` | role in | role out |
|---|---|---|
| 2, 3, 21 (FileNotFound, IsADirectory) | IN-001 | OUT-001 for 2/3; OUT-004 for 21 |
| 5, 13 | IN-002 | OUT-002 |
| 32 | IN-002 | OUT-002 |
| 123, 206 | IN-001 | OUT-004 |
| 112, 28 | IN-002 | OUT-005 |
| anything else | not matched here -> continue to later rules (ends in SYS-999) |

When `role == "in"` and `p in ctx.input_paths`, set `culprit_node_id = ctx.input_paths[p]`; when `role == "out"` set `culprit_node_id = ctx.output_paths[p]` if known. This is the **path-based attribution** that fixes the lazy-plan case for missing input files (the sink raises but the File Input is named).

### 3.8 Suggestions (`suggest.py`)

```python
def normalise_name(s: str) -> str:  return re.sub(r"[\s_\-]+", "", s).casefold()
def suggest_names(name: str, candidates: Iterable[str], *, limit: int = 3, cutoff: float = 0.6) -> tuple[str, ...]:
    # 1. exact normalised match first (case/space/underscore-only difference), 2. difflib.get_close_matches on
    #    normalised strings mapped back to the original candidates, 3. at most `limit`, no duplicates
```
Verified: `Amnt`->`Amount`; `custmer id`->`Customer Id`; `Totl`->`Total`; `zz`->none. SCH-001 sets `did_you_mean`, `params["suggestion"]`, a `SuggestedFix(kind="rename_column", params={"from": col, "to": s})`. The same helper is used for sheets (IN-003) and functions (EXP-002).

### 3.9 Rendering formats

* **Tooltip** (`render_tooltip`, <= 600 chars, plain text; replaces the node tooltip):
  `"{node_label}: {title}\n{first sentence of detail}\nFix: {hint}\n{code}{ · row N}"` (parts omitted when empty).
* **Copy details** (`render_text(include_technical)`), one block, also what is written to the Logging dock (first line only) and `loguru` (whole block at ERROR):
  ```
  [TD-TYP-003] Aggregate 'Totals': Column 'Amount' contains text ('1,2O0.50') in row 4,210, so it cannot be summed.
  Fix: Clean or correct the value (row 4,210).
  Other fixes: Add a Select node before this one and set 'Amount' to Decimal.
  Columns: Amount
  Rows/values: row 4,210 ('1,2O0.50'); 2 more: 'x', 'y'
  Caused by: Select 'Prep' (node 1402)          # only when culprit differs
  Phase: run   Severity: error   Time: 2026-10-21T14:03:11Z
  --- technical ---
  polars.exceptions.InvalidOperationError: conversion from `str` to `f64` failed ...
  <traceback text>
  ```
  `include_technical=False` stops before `--- technical ---`.
* With `redact=True` the `Rows/values` line becomes `values hidden by privacy setting` and the technical block is scrubbed (3.11).

### 3.10 Formula/Filter inline diagnostics (requirement f)

`translate_sql_diagnostic(exc, formula_text, ctx)` returns `{"message": str, "category": str, "code": str, "hint": str}`:

* `ParserException` (EXP-001): **keep the existing path** (`FormulaContent._diagnose_section_error` calls `SQLFormulaEditor.validate_sql_syntax`, positions untouched); add `"code": "TD-EXP-001"` and `"hint"` only; message unchanged (tests at `test_formula_node.py:204,430` pin them).
* All other exceptions: `err = translate_exception(exc, ctx=ctx)`; `message = shorten(err.title + (" " + err.hint if err.hint else ""), 160)`; `category = "execution"`; plus `code`/`hint`. This replaces `_shorten_error(str(exc))` for the non-parser branch **only** (the function `_shorten_error` stays, its test pins it). The message must not contain `LINE`, `Candidate bindings`, the target alias or `df_step_` (the catalogue guarantees it; a test asserts it).
* Formula `_run_sections_sequential` additionally stores `self._section_exceptions[index] = exc` (cleared with `section_errors`); `update_data` then builds `self.last_node_error = translate_exception(self._section_exceptions[failed], node=self.node, phase="live")` and keeps `last_error`/`section_errors` strings exactly as today. `TriggerNode_Formula.processInputs` (`formula.py:1391-1397`) keeps its `markInvalid` + return `None` but calls `self.set_error(self.content.last_node_error, "live")` instead of `grNode.setToolTip(last_error)` (the tooltip is then produced by `render_tooltip`, which starts with `Section 1: ` stripped - the dock shows the section number in `detail`). The `global_logger.error(f"Formula node failed: ...")` call is replaced by the generic one-line log done in `set_error`.
* Filter: `_update_expression_data` sets `self.last_exception = e` (reset to `None` at its start); `TriggerNode_Filter.processInputs` after `update_data()` does `if self.content.last_exception is not None: self.markInvalid(); self.set_error(translate_exception(self.content.last_exception, node=self, phase="live"), "live"); return None`. `validate_expression` message = same helper as Formula (`translate_sql_diagnostic`, non-parser branch) while keeping `line 1, column 0, length 1`.

### 3.11 Redaction (`redact.py`)

`redact_text(text, values)` replaces every occurrence of each non-empty `values` item with `<redacted>` and applies these regex scrubs (each tested against the O-rows): Polars `values: \[.*\]` -> `values: [<redacted>]`; DuckDB `string (['"]).*?\1 to` -> `string <redacted> to`; `invalid date field format: ".*?"` -> `invalid date field format: <redacted>`; `Could not parse string ".*?" according` -> `Could not parse string <redacted> according`; `first shown value: '.*?'` -> `...: <redacted>`. `redact_error(err)` -> `err.with_updates(sample_values=(), title=<rendered with located=False>, detail=..., technical=redact_text(...), traceback=redact_text(...), redacted=True, row_index=err.row_index)` (the **row number is kept**: it is not a value). `translate_exception(..., redact=True)` and `enrich_error` (job.redact) both end with `redact_error`. The locator is still run (it needs the value only in memory) but `sample_values` is dropped before storage/logging.

### 3.12 Brief hook points used

| Hook | Use |
|---|---|
| H2 `_on_node_finished` (`workflow_execution_mixin.py:96-112`) | translate Run failures, `set_error(..., "run")`, start enrichment |
| H3 `_on_node_errored` (`:114-123`) | same translation with the raw exception |
| H5 `execute_node` except/finally (`executor.py:378-417`) | **none here**: `exception` / `traceback_text` are filled by plan 09 F-B; this plan only reads them |
| H1 `executeWorkflow` (`:47-89`) | clear previous run errors, pass `continue_on_error` + upstream map to the worker |
| H8 `TriggerNode.eval` except branches (`node_base.py:892-900`) | translate live errors |
| H4 `_on_workflow_finished` (`:125-141`) | auto-raise Problems dock once; log "N problems" line |
| H7 worker signals | one new signal `nodeSkipped(node, blocker)` (additive) |
| H12 `global_logger`/loguru | one summary line per new error + full block at ERROR |

### 3.13 UI layout (DESIGN_SYSTEM §§1-7, 9, 11, 13, 14, 16)

**Node tooltip + badge.** See D10/D11. Badge geometry in `TriggerGraphicsNode`: diameter 14 scene units, centre at `bodyRect().topRight() + (-12, +12)`, fill = theme `danger` (error) or `warning` (warning), glyph "!" in `text_on_accent` falling back to white from the theme manager (`get_theme_manager().color(token, fallback)` like `_pen_from_token`, `node_base.py:~190`). New attributes: `_error_badge: str = ""` ("error"/"warning"/""), method `set_error_badge(severity: str)` which calls `update()`. Drawn at the end of `paint` (after the status badge, and also when `_badge_visible` is False so a hidden status badge cannot hide an error; the early `return` at `node_base.py:261-262` is restructured). No change to `boundingRect` (inside the body). Ring: `setPenError()` stays for run failures; for live errors only the badge + the existing red status badge (unchanged behaviour).

**Problems dock** (`qt/docks/problems_dock.py`, `objectName "ProblemsDock"`, title `Problems`, tabified with Logging/Data Preview, tab-only chrome, `Qt.BottomDockWidgetArea`; the tab text becomes `Problems (3)` via `setWindowTitle` when count > 0). Content widget `ProblemsPanel` (`objectName "ProblemsPanel"`):

```
+-- toolbar (fixed H40, margins 0, spacing 2) ----------------------------------------+
| [search QLineEdit H30, placeholder "Filter problems", 300 ms debounce, clear button] |
|                                              [Copy details] [Technical details (chk)] |
+---------------------------------------------------------------------------------------+
| QTreeWidget objectName "ProblemsTree": columns  Node | Code | Problem   (rows 24 dense) |
|   > Aggregate 'Totals'  TD-TYP-003  Column 'Amount' contains text ('1,2O0.50') ...      |
|       child rows (when expanded/selected): detail / "Fix: ..." / other fixes /           |
|       "Caused by: ..." / [technical block, only when the toggle is checked, mono 11px]  |
| EmptyStateLabel("No problems") when empty                                                |
+---------------------------------------------------------------------------------------+
```

* Buttons are `IconButton.themed(...)` (30x30, 12px glyph): copy = new glyph id `icon_copy` (`qt/images/node_icons/ui/copy.svg`), technical toggle = `icon_details` (`ui/details.svg`, `setCheckable(True)`, `setAccessibleName("Technical details")`, tooltip `Show technical details`). Both ids and the two SVG files are added in step 9 (monochrome 16x16 viewBox, `fill="currentColor"` like the existing `ui/*.svg`; copy = two overlapping rounded rects, details = three horizontal lines with a chevron). Mandatory tooltip + accessible name; no inline `setStyleSheet`; `objectName`s `ProblemsTree`, `ProblemsPanel`, `ProblemsDetails` get QSS in `resources/qt/themes/base.qss` **and** `qss/_style.scss` with `:hover`/`:selected`/`:disabled` restated with `{background_hover}`/`{accent_primary}` per DESIGN_SYSTEM §4.5/§11 (no vertical grid lines; selection = accent 18%).
* Row colour: severity text from tokens `danger`/`warning` through `apply_theme()` (never hex); knock-on rows (`TD-RUN-003/005/008`) use `text_secondary`.
* **Click** (single) on a row: `scene.doDeselectItems()`, `node.grNode.setSelected(True)`, `view.centerOn(node.grNode)` (the existing selection listener opens the Config Dock). Row -> node lookup by `error.node_id` over `scene.nodes` (`node.id`). Double click does the same and expands the row.
* **Copy details** copies `render_text(include_technical=<toggle>)` of the selected row (all rows when none selected, separated by a blank line) via `QGuiApplication.clipboard()`.
* **Technical details toggle** persists as preference `errors/show_technical` (default False).
* Follows the active design window exactly like `LoggingDock` (`switch_to_design_window(window)`, `remove_design_window(window_id)`; the store is `window.problems`), refreshes on `ProblemsStore.changed` (coalesced with `QTimer.singleShot(0, ...)`).
* The dock raises itself once per Run when the Run produced at least one root error (`_on_workflow_finished`), never for live errors.

### 3.14 Preference keys (`qt/preferences.py` `DEFAULTS`, `:42-56`)

| Key | Default | Meaning | UI (General page, `preferences_dialog.py:392-`) |
|---|---|---|---|
| `errors/continue_past_failure` | `True` | Run keeps executing branches that do not depend on a failed node | checkbox "Keep running independent branches after a failure" |
| `errors/redact_values` | `False` | scrub sample values from messages, details and the log | checkbox "Hide data values in error messages" |
| `errors/locate_rows` | `True` | run the bounded second query to find the offending row/values | checkbox "Find the offending row for conversion errors" |
| `errors/locate_row_cap` | `5000000` | max input rows scanned by the locator | spin 100,000-100,000,000 step 100,000 |
| `errors/show_technical` | `False` | Problems dock "technical details" toggle | none (dock state) |

Qt-free code never imports preferences: values are passed as arguments (`redact`, `row_cap`, `locate`, `continue_on_error`).

### 3.15 Run policy semantics (spec owned here; implemented by plan 09 F-C)

1. `continue_on_error=False`: stop at the first failure (today's behaviour). `True`: after a failure keep running every node that has **no failed or skipped node among its upstream nodes** (transitive; a multi-input node is skipped when **any** parent failed or was skipped; both outputs of a multi-output node count as the same node).
2. A skipped node is never executed and never `markInvalid`; it gets `TD-RUN-008` (blocker = the nearest failed/skipped parent, first in input order); cancellation uses the same notification with blocker `None` -> `TD-RUN-004`.
3. Overall success is `False` if any node failed, was skipped or the run was cancelled (`LoopOutcome.success`, plan 09 F-C rule 3). With `continue_on_error=False` the loop stops at the first failure and sends **no** skipped notifications for the remainder (those nodes keep their default pens).
4. Wiring (names from plan 09 section 1.2, not re-specified here): the mixin's `_run_policy()` returns `{"continue_on_error": bool}` and is the only policy field the run loop reads; `run_nodes(..., continue_on_error=, upstream=)` calls `on_node_finished(node, result)` / `on_node_errored(node, exc)` / `on_node_skipped(node, blocker)`; `WorkflowWorker` re-emits them as `nodeFinished` / `nodeErrored` / `nodeSkipped`, and the mixin connects `nodeSkipped` to `_on_node_skipped`.
5. Preference `errors/continue_past_failure` (default True) feeds the GUI; headless callers pass the flag explicitly (plan 08 default False, `--keep-going` sets True).

---

## 4. Ordered implementation steps (small commits)

Run `ruff format` + `ruff check` on **only the files you touched** after each step (brief 2.3). Use `.venv\Scripts\python.exe -m ...`. Commit message style: imperative, one line; trailer per the session's attribution rule.

### Step 1 - model, catalogue, suggestions, redaction (no behaviour change)
Files (new): `core/errors/__init__.py`, `model.py`, `catalogue.py`, `suggest.py`, `redact.py`, `builders.py`; tests `tests/unit/test_errors_model.py`, `test_errors_catalogue.py`, `test_errors_suggest.py`, `test_errors_redact.py`.
* `model.py`: implement 3.2 exactly. `fingerprint` = `hashlib.sha1("|".join([code, str(node_id), str(culprit_node_id), ",".join(columns), exc_type]).encode()).hexdigest()[:12]`, set in `with_updates` and in `make_error`. `created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")`.
* `catalogue.py`: paste the table of 3.5 as a dict literal (strings exactly as in the table; `{op_past}` etc. placeholders). Implement `render_entry`, `SafeDict`, and `if __name__ == "__main__": print markdown table` (used in step 13).
* `builders.py`: `make_error(code, ctx=None, *, severity=None, **params) -> NodeError` builds from the catalogue with no exception (used for RUN-003/005/008, JOI-*, SYS-001).
* Done when: `.venv\Scripts\python.exe -m pytest tests\unit\test_errors_model.py tests\unit\test_errors_catalogue.py tests\unit\test_errors_suggest.py tests\unit\test_errors_redact.py -q` passes and `python -c "import trigger_designer.core.errors, sys; assert 'qtpy' not in sys.modules and 'PyQt6' not in sys.modules"` exits 0.

### Step 2 - translator (all rules)
File: `core/errors/translator.py`; test `tests/unit/test_errors_translator.py`.
Skeleton:
```python
@dataclass(frozen=True)
class Facts:
    names: tuple[str, ...]; text: str; first_line: str; exc: BaseException | None

@dataclass(frozen=True)
class Rule:
    id: int
    names: frozenset[str] | None            # None = any class
    pattern: re.Pattern[str] | None
    build: Callable[[Facts, ErrorContext, re.Match[str] | None], tuple[str, dict[str, str]] | None]
        # returns (code, params) or None to decline (rule 8/22 may decline)

RULES: tuple[Rule, ...] = (...)             # exactly the table in 3.7, in that order

def translate_exception(exc, *, node=None, phase="run", ctx=None, redact=False, traceback_text="") -> NodeError:
    try:
        ctx = ctx or ErrorContext.from_node(node, phase)
        facts = _facts(_unwrap(exc))
        for rule in RULES:
            if rule.names is not None and not (set(facts.names) & rule.names): continue
            m = rule.pattern.search(facts.text) if rule.pattern else None
            if rule.pattern and not m: continue
            hit = rule.build(facts, ctx, m)
            if hit: return _finish(hit, facts, ctx, redact, traceback_text)
        return _finish(("TD-SYS-999", {"reason": shorten(facts.text, 160)}), facts, ctx, redact, traceback_text)
    except Exception as boom:                # translator must never raise
        return _fallback(exc, boom)
```
`_unwrap`: if `exc` has attribute `original_exception` that is not None -> that, **except** class names `ExecutionTimeoutError`/`ExecutionMemoryError` (kept); guard against cycles (`seen` set of ids, max depth 5); for `str`/`None` return `_TextError`. `_facts` wraps `str(e)` in try/except and truncates `text` to 20,000 chars for matching only (the full text is kept in `technical`, itself capped at 100,000 chars with a `... [truncated]` suffix). `_finish` builds `NodeError` via `render_entry`, sets `node_id/node_title/op/node_label/phase` from ctx, `columns`, `path`, `exc_type`, `exc_module`, `technical=str(e)` (empty -> `repr`), `traceback`, `params`, did-you-mean, `culprit_*` from params, `severity` from the catalogue, then `redact_error` when asked.
Implement the helper parsers (`_parse_polars_values(vals) -> list[str]` handling `"a"`, `"a\"b"`, `…` separators; `_parse_schema_fields`; `_target_human`, `_target_sql`) as private functions with their own tiny tests.
Done when: `.venv\Scripts\python.exe -m pytest tests\unit\test_errors_translator.py -q` passes (one test per code, fuzz tests).

### Step 3 - locator and attribution
Files (new): `core/errors/locator.py`, `attribution.py`, `enrich.py`; tests `test_errors_locator.py`, `test_errors_attribution.py`, `test_errors_enrich.py`.
* `attribute_upstream(error_code, exc_type, ancestors, *, row_cap=100_000, budget_s=3.0) -> int | None`:
  ```python
  @dataclass(frozen=True)
  class Ancestor: node_id: int; frame: Any | None          # LazyFrame/DataFrame or None
  SCHEMA_CODES = {"TD-SCH-001","TD-SCH-002","TD-SCH-004","TD-SCH-005","TD-TYP-002","TD-TYP-006","TD-IN-001","TD-IN-002","TD-IN-003","TD-IN-005","TD-IN-006","TD-SYS-100"}
  DATA_CODES   = {"TD-TYP-001","TD-TYP-003","TD-TYP-004","TD-TYP-005","TD-IN-004","TD-IN-007","TD-SYS-100"}
  # pass 1 (schema, no data): for a in ancestors (sources -> nearest): frame.lazy().collect_schema(); on Exception -> return a.node_id
  # pass 2 (data): only if code in DATA_CODES; for a in ancestors: frame.lazy().head(row_cap).collect(engine="streaming");
  #   if it raises and type(exc).__name__ == exc_type -> return a.node_id ; stop when time.monotonic()-t0 > budget_s -> None
  ```
  Returns `None` when no ancestor fails (the failing node itself is then responsible).
* `enrich_error(job)` per 3.2: (1) attribution when `job.attribute and error.culprit_node_id is None and ancestors`; (2) rebuild error for the culprit via `render_entry` using its `labels/titles/ops`; (3) locate when `job.locate and code in {TYP-001, TYP-003, TYP-005}` using `job.inputs_of[culprit or failing]`, params `column`, `target`, `known_value`, `sum_mode`, `date_format`; update `params` (`row`, `value`, `values`, `others_sentence`, `row_hint`) and set `row_index/sample_values/locate_status`; (4) `knock_on = make_error("TD-RUN-003", ...)` for the failing node when root moved; (5) `redact_error` if `job.redact`. Wrap everything in try/except returning `EnrichResult(job.error, None, None)`.
* Done when the three test files pass and `locator` test `test_locator_matches_example_row_4210` passes.

### Step 4 - consume `exception` / `traceback_text` (fields supplied by plan 09 F-A/F-B)
Depends on **plan 09 F-A** (executor hardening: `except BaseException` in the exec thread, `node_name`) and **plan 09 F-B** (which fills `ExecutionResult.exception`, `traceback_text`, `exception_type` on the failure path, nulls `exception` in `without_frames()`, and keeps `result.error` unchanged; plan 09 section 1.2). This plan makes **no executor edit**: it only consumes `result.exception` (the source exception, `original_exception` unwrapped) and `result.traceback_text`.
* Done when `.venv\Scripts\python.exe -m pytest tests\unit\test_execution_result.py tests\unit\test_executor_errors.py -q` passes (new files, section 6; they assert the F-B fields reach the translator; the panic test needs F-A).

### Step 5 - preferences
Files: `qt/preferences.py` (`DEFAULTS` add the five keys of 3.14, defaults typed so `_coerce` yields bool/int), `qt/dialogs/preferences_dialog.py` (`_build_general_page` `:392`: three `QCheckBox` + one `QSpinBox`; load in the dialog init next to `:454`; write in slots next to `:638`; follow the existing pattern exactly).
Done when: `.venv\Scripts\python.exe -m pytest tests\unit\test_preferences.py -q` passes and new `tests/ui/test_errors_preferences.py::test_general_page_roundtrips_error_prefs` passes.

### Step 6 - node error state, tooltip, badge, live hook (H8)
Files: `qt/node_base.py`.
* On `TriggerNode` add (lazy store, no `__init__` dependency because `FileInputNode.__init__` calls `eval()` early):
  ```python
  _errors_by_source = None                     # class default; real dict created on first use
  def set_error(self, error, source: str = "live") -> None:
      store = self._errors_dict(); old = store.get(source)
      store[source] = error
      self._apply_error_state()                # tooltip + badge
      if old is None or old.fingerprint != error.fingerprint:
          self._log_new_error(error)           # Logging dock one-liner + loguru ERROR block (skipped when redacted text is empty)
      problems = self._problems_store()
      if problems is not None and not (error.knock_on and source == "live"):
          problems.upsert(error, source)
  def clear_error(self, source: str | None = None) -> None: ...   # None = all; also removes from the store; clears knock-on descendants for source "run"
  @property
  def current_error(self): ...                  # run error wins over live error
  def _apply_error_state(self) -> None:
      err = self.current_error
      self._set_node_tooltip(err.render_tooltip() if err else "")
      gr = getattr(self, "grNode", None)
      if gr is not None: gr.set_error_badge(err.severity if err else "")
  def _problems_store(self):                    # same owner walk as _refresh_selected_node_config (node_base.py:763-770), attribute "problems"
  ```
* `eval()` except branches (`:892-900`): replace `self._set_node_tooltip(str(e))` with `self.set_error(translate_exception(e, node=self, phase="live"), "live")`; keep `markInvalid`, `markDescendantsDirty`, `dumpException(e)` (so tests/stderr behaviour is unchanged). `ValueError` stays on its branch (translated with the same call; legacy messages become `TD-SYS-001` via a rule-5-style fallback: add to `_fallback` -> if `type(e) is ValueError` and no rule matched, use `make_error("TD-SYS-001", message=str(e))`).
* `evalImplementation` (`:816-852`): not-connected branch (**plan 07 F2 / BUG-031 lands first** and has already added the `optional_inputs` class attribute and this guard at the top of `if not input_node:`; this plan must keep it verbatim, ahead of any `set_error`):
  ```python
  if not input_node:
      if i in self.optional_inputs:
          input_values.append(None)
          continue
      self.markInvalid()
      self.markDescendantsDirty()
      self.set_error(make_error("TD-RUN-005", ctx, input_number=i + 1), "live")   # replaces only the old _set_node_tooltip(...) line
  ```
  Test (added to `tests/unit/test_node_errors.py`, or the existing node-base test file): `test_optional_input_unwired_sets_no_error` - a probe node with `optional_inputs = frozenset({1})` and only input 0 wired evaluates valid, `current_error` is `None`, and an unwired required input still gets `TD-RUN-005`; plan 07's `test_optional_inputs_*` must keep passing. Ordering: 07 F2, then this step (also recorded in plan 09 section 1.4); upstream-no-output branch -> `make_error("TD-RUN-003", ctx, culprit_label=<upstream node_label>)` with `culprit_node_id = input_node.id`; `result is None` branch: if the node already has a non-empty tooltip that is not one of ours (legacy) wrap it: `make_error("TD-SYS-001", ctx, message=<tooltip>)`, else `"Invalid operation"` -> `TD-SYS-001`; success branch `:849`: replace `self._set_node_tooltip("")` with `self.clear_error("live")`.
* `onInputChanged` (`:931`) and `onEdgeConnectionChanged` (`:925`): `self.clear_error("run")` first.
* `TriggerGraphicsNode`: add `_error_badge = ""`, `set_error_badge`, painting per 3.13; restructure the `paint` tail (`:261-272`) so the error badge is drawn even when `_badge_visible` is False.
* `qt/helpers/error_context.py`: `build_context(node, window=None, phase="run")` fills `ErrorContext` using only getattr: `node_title=type(node).node_title`, label = `getattr(node, "label_text", "")` (verify the attribute name in `node_base.py`/vendored `node_node.py` before use: `grep -n "label_text"`; if absent use `""`), `op` from `f"{node.node_type.value}.{node.node_code.name.lower()}"`, `input_columns/input_dtypes` from `frame_schema()` of the first upstream value entry (try/except), `referenced_columns` from optional `content.referenced_columns()` (nodes may add it; default `()`), path/owner maps by scanning `node.scene.nodes` for ops ending `file_input`/`file_output` and reading `content.filePath`, `variable_owners` from each node's `param`/`value` entries (`variable_name` -> `node.id`) plus content attrs named `variable_name`, `*_variable_name`.
* Done when: new `tests/ui/test_node_error_state.py` (section 6) and `tests/unit/test_node_base.py` pass; `.venv\Scripts\python.exe -m pytest tests\unit -q` still 334+ pass.

### Step 7 - ProblemsStore and ErrorEnricher
Files (new): `qt/helpers/problems_store.py`, `qt/helpers/error_enricher.py`; `design_window.py`: in `TriggerSubWindow.__init__` (`:85`) add `self.problems = ProblemsStore(self)`.
```python
class ProblemsStore(QObject):
    changed = Signal()
    def upsert(self, error: NodeError, source: str) -> bool:      # key (error.node_id, source); False + no signal when equal
    def remove(self, node_id: int, source: str | None = None) -> None
    def clear_source(self, source: str) -> None
    def entries(self) -> list[tuple[str, NodeError]]              # run errors first (insertion order), then live
    def count(self, severity: str | None = None, *, roots_only: bool = False) -> int   # roots_only excludes knock_on
    pending: int                                                   # enrichment jobs in flight
    settled = Signal()                                             # emitted when pending returns to 0 (plan 02 persists on it)
class ErrorEnricher(QRunnable):                                    # signals on a small QObject holder `.signals.done(object)`
    def __init__(self, job: EnrichJob, timeout_s: float = 10.0): ...
def start_enrichment(job: EnrichJob, on_done: Callable[[EnrichResult], None], *, timeout_s: float = 10.0) -> None
    # QThreadPool.globalInstance().start(...); the timeout is enforced by a QTimer.singleShot(timeout_s*1000) on the GUI side that marks the
    # job abandoned (late result ignored) and applies error.with_updates(locate_status="timeout")
```
`build_enrich_job(node, window, error, phase)` in `error_context.py`: ancestors = BFS upstream via `node.getInputs()` collected, ordered sources -> nearest by topological index (`window._workflow_sorted_nodes` when available, else BFS depth reversed); frame per ancestor = first `value[i]["data"]`; `inputs_of[id]` = for each upstream entry feeding that node (`upstream.value[socket_index]["data"]`); `labels/titles/ops` for all ids involved; flags from preferences.
Done when: `tests/unit/test_problems_store.py` and `tests/ui/test_error_enricher.py` pass.

### Step 8 - Run integration, continue past failure, skipped nodes (H1/H2/H3/H4)
Files: `qt/helpers/workflow_execution_mixin.py` only. The loop itself (continue-on-error, skip propagation, cancellation, skipped notification) is **plan 09 F-C** (shared Qt-free run loop extracted from `WorkflowWorker`) and **F-D** (single cancellation API); this plan owns the **policy spec** in 3.15 and consumes F-C's callbacks (`on_node_finished(node, result)`, `on_node_errored(node, exc)`, `on_node_skipped(node, blocker)` with `blocker=None` meaning cancelled), which `WorkflowWorker` re-emits as the signals `nodeFinished`, `nodeErrored`, `nodeSkipped`. Do not edit `workflow_worker.py`, `run_loop.py` or the `upstream`/`WorkflowWorker(...)` construction in `executeWorkflow` here: F-C/F-E already build `upstream` from `connections`, pass `continue_on_error=self._run_policy()["continue_on_error"]`, and connect `nodeSkipped` to `_on_node_skipped`.
* Mixin seams (plan 09 section 1.2): override the **body** of `_run_policy()` to `return {"continue_on_error": bool(get_preferences().get("errors/continue_past_failure", True))}` (that single key is all `run_nodes` reads); fill the body of `_on_node_skipped(node, blocker)` (below). This plan **owns** these two lines in `executeWorkflow` (plan 09 F-E does not add them; it leaves two marked `# PLAN-03 SEAM` comments and `test_execute_workflow_seams` asserting they exist): at the first marker, inside the existing `markInvalid(False)` visual-reset loop (inside F-E's `try`), add `node.clear_error("run")`; at the second marker, before `_reevaluate_for_run`, add `self._run_generation += 1` (initialise `self._run_generation = 0` in the mixin/window `__init__`). Replace each marker comment with the line.
* `_on_node_finished` failure branch (`:106-112`): keep existing logging and pen/invalid calls, then
  ```python
  err = translate_exception(result.exception or result.error, node=node, phase="run",
                            ctx=build_context(node, self, "run"), redact=prefs.get("errors/redact_values", False),
                            traceback_text=result.traceback_text)
  node.set_error(err, "run")
  if prefs.get("errors/locate_rows", True) or err.code in ATTRIBUTABLE:
      start_enrichment(build_enrich_job(node, self, err, "run"), lambda res, n=node: self._apply_enrichment(n, res))
  ```
  `_apply_enrichment(node, res)`: `node.clear_error("run")`; if `res.culprit_node_id` is not None and differs: `culprit.set_error(res.root, "run")` and `node.set_error(res.knock_on, "run")`; else `node.set_error(res.root, "run")`.
* `_on_node_errored` (`:114-123`): same with `exc`.
* `_on_node_skipped(node, blocker)`: `err = make_error("TD-RUN-004" if blocker is None else "TD-RUN-008", build_context(node, self), culprit_label=blocker's node_label)`; `err = err.with_updates(culprit_node_id=blocker.id if blocker else None)`; `node.set_error(err, "run")`. Skipped nodes are **not** `markInvalid`.
* `_on_workflow_finished` (`:125-141`): after existing code, `if self.problems.count("error", roots_only=True): raise the Problems dock (via an optional callable the main window installs: self.on_run_problems = callable)`; log `"Run finished with N problem(s)"` through `logError`.
* `_execution_cleanup` (`:143`) unchanged except it must not reset the error badges (pens only).
Done when: `tests/unit/test_run_policy_errors.py` (section 6) and `tests/unit/test_workflow_execution_mixin.py` (existing, with a new case) pass.

### Step 9 - Problems dock, icons, QSS, wiring
Files: `qt/docks/problems_dock.py` (new), `qt/helpers/main_window_ui_mixin.py` (add `createProblemsDock`, `switchProblemsDock`, extend `onDesignWindowClose :289-295`, add a menu action in `updateWindowMenu :103-160` with text `Problems`), `qt/main_window.py` (`initUI :142-148` call `createProblemsDock()` after `createDataPreviewDock()`; `createMdiChild :487-538` nothing extra - the dock reads `window.problems`; `onSubWindowActivated :540-552` call `switchProblemsDock`; `apply_appearance :293-330` call `problemsDock.apply_theme()`), `qt/layout_state.py` (`apply_default_layout :225-250`: add `("problemsDock", BottomDockWidgetArea)` and tabify it with logging), `qt/resources.json` (+`icon_copy`, `icon_details`), `resources/qt/images/node_icons/ui/copy.svg` and `details.svg`, `resources/qt/themes/base.qss` and `qss/_style.scss` (new objectNames), `trigger.spec` (the two SVGs are under the already-bundled `resources/` folder - verify with `grep -n node_icons trigger.spec`; add only if missing).
Tab-group order: Logging, Data Preview, Problems. `createProblemsDock` mirrors `createDataPreviewDock` (`:263-273`): `addDockWidget`, `tabifyDockWidget(self.loggingDock, self.problemsDock)`, `install_tab_only_chrome(self.problemsDock)`.
Done when: `tests/ui/test_problems_dock.py` passes and `tests/unit/test_theme_tokens.py` passes (every `{token}` in the new QSS exists).

### Step 10 - Formula/Filter integration (requirement f)
Files: `Preparation/formula.py`, `Preparation/filter.py`, `core/errors/translator.py` (`translate_sql_diagnostic`). Implement exactly 3.10. Keep `_shorten_error` and all existing messages for syntax diagnostics.
Done when: `tests/ui/test_formula_node.py` and `tests/ui/test_filter_expression.py` show **no new failures** versus the baseline (4 known failures in `test_formula_node.py`; compare names) and the new `tests/unit/test_sql_diagnostics.py` passes.

### Step 11 - adopt the catalogue in the nodes that own the commonest tooltips
Files: `InOut/file_input.py:307-318` (`check_file_path`: replace the tooltip with `self.node.set_error(make_error("TD-IN-001", build_context(self.node), path=self.filePath), "live")`; success branch `:319-322` -> `self.node.clear_error("live")`), `InOut/file_output.py` (no change to `get_code`; the translator already maps O49), `Join/join.py:1516,1547` ("Both inputs must be connected" -> `make_error("TD-JOI-002", ...)`), `Join/Append.py:248`. Nothing else is migrated.
Done when: `tests/unit/test_file_output.py`, `tests/unit/test_union_node.py` pass and the new e2e `missing_input` case (step 12) passes.

### Step 12 - e2e golden tests
Files: `tests/support/errors.py` (`assert_error_golden`), `tests/e2e/test_error_workflows.py`, `tests/e2e/fixtures/expected_errors/*.json` (generated by `TRIGGER_UPDATE_E2E_GOLDENS=1`, then reviewed). Exact cases in section 6.4.

### Step 13 - generated reference
File `scripts/dump_error_catalogue.py` calls `catalogue.main_markdown()` -> writes `docs/ERROR_CODES.md` (code, severity, title, fixes). Test `tests/unit/test_errors_catalogue.py::test_error_codes_doc_is_current` compares. This is the support-facing table.
Done when `.venv\Scripts\python.exe scripts\dump_error_catalogue.py` produces no diff on a second run.

---

## 5. Edge cases (each has a decided behaviour and a test in section 6)

| Case | Behaviour |
|---|---|
| **Error surfaces at the sink of a lazy plan** | Path-based attribution (rule 8) names the File Input/Output; otherwise `attribute_upstream` probes ancestors (schema pass then data pass, 100,000 rows, 3 s budget). Root error is stored on the culprit; the sink gets knock-on `TD-RUN-003`. If no ancestor fails the sink keeps the root error. |
| **Graph with no sink** | Plan 09 F-E runs `collect_schema()` on every lazy output (no implicit collect), so a bad column/join key fails the culprit node at Run; data errors (a bad cast value) are still not detected without a sink - documented, not fixed here. |
| **Multi-output nodes (Split, Filter T/F)** | An error belongs to the node, not a socket. Downstream nodes on *either* output are skipped (`TD-RUN-008`) because the worker's `upstream` map is per node. `variable_owners` maps both variable names to the same id. |
| **Disconnected node** | `TD-RUN-005` warning (knock-on, live only, not in the dock). In Run an unwired node runs its fallback code and normally succeeds; File Output unwired -> `TD-OUT-006` error (observed O49). |
| **Very long values** | `_display` truncates to 80 chars + `…`; control chars escaped; the locator selects at most 5 values; `technical` capped at 100,000 chars (`... [truncated]`); tooltip capped at 600 chars; titles `shorten(…, 90)`. |
| **Non-UTF-8 / odd values** | Strings arriving from Polars are valid UTF-8; the locator still casts with `errors="replace"` when formatting and the translator never indexes into `str(e)` unguarded. `UnicodeDecodeError` gets `reason`/`start` from its attributes. A `__str__` that raises -> `repr(type(e))` used. |
| **Confidential values** | `errors/redact_values` (3.11). Row numbers are kept. With redaction ON, `Rows/values` shows "values hidden by privacy setting"; log lines and `technical` are scrubbed; the exception object in `ExecutionResult.exception` is the only raw copy and is dropped by `without_frames()` and by the enrichment hand-off (`result.exception = None` after translation). |
| **Load vs Run errors** | `phase` field: `load` = errors raised during `doEvalOutputs` after `fileLoad` (set by `design_window` via a `scene._loading_phase` flag read in `build_context`: `phase="load" if getattr(scene, "_batch_evaluating", False) else "live"`); they use the "live" source. Run errors use source "run". Run errors override live errors for tooltip/badge; both are visible in the dock (live row is hidden when a run row exists for the same node). |
| **Cancelled runs** | Plan 09 F-D owns cancellation; remaining nodes are reported as skipped with blocker `None` -> `TD-RUN-004` (warning). Tested with a stub run loop. |
| **Repeated identical errors** | `upsert` returns False when `(node_id, source)` already holds an equal error (`fingerprint` + all compare fields); no re-log, no `changed`. Live re-evaluation on every keystroke therefore costs one dict lookup. The locator runs only when the fingerprint changes (`_pending_enrichment: set[str]` per node). |
| **Several sinks fail from the same bad upstream** | Each sink is a separate failure; attribution gives the same culprit; the store holds one root row on the culprit (same fingerprint -> upsert no-op) plus one `TD-RUN-003` row per sink. |
| **Run restarted while enrichment is in flight** | `executeWorkflow` bumps `self._run_generation`; `_apply_enrichment` ignores results whose generation differs. |
| **Window closed with a job in flight** | `ErrorEnricher` signals are parented to the store (`QObject`); `remove_design_window` drops the store reference; late result lands on a dead `QObject` and is ignored (`try/except RuntimeError`). |
| **Node deleted while it has an error** | `TriggerNode.remove()` hook: add `self.clear_error()` in `TriggerNode.onRemoved`-equivalent; the vendored `Node.remove` is overridden in `TriggerNode` only if it does not already exist (`grep -n "def remove" qt/node_base.py`); if absent the store prunes entries whose `node_id` is no longer in `scene.nodes` on every `changed` refresh in the dock. Decision: dock-side pruning (no override). |
| **Exception inside translation** | Impossible to escape (`try/except Exception` around everything); fallback keeps raw text. |
| **Panic in exec thread** | Fixed by plan 09 F-A (D12); reported as `TD-SYS-998`; worker thread survives. |

---

## 6. Test plan

All new tests live in the layer matching their directory (markers are automatic). Qt-free tests must **not** import `qtpy` (guarded by `test_core_errors_is_qt_free`). Fixtures for real triggers are built in `tests/support/error_triggers.py` (one function per catalogue code that *actually raises* the engine exception, so tests break if an engine upgrade changes a message).

### 6.1 Unit tests (`tests/unit/`)

`test_errors_model.py`
* `test_node_error_is_frozen_and_has_defaults`: `NodeError(code="TD-SYS-999", title="x")` -> `severity=="error"`, `columns==()`, assigning raises `FrozenInstanceError`.
* `test_to_dict_from_dict_roundtrip`: all new fields incl. `suggested_fixes`, `params`; `orjson.dumps(err.to_dict())` succeeds (JSON-safe) and `from_dict(...) == err` (compare=False fields ignored).
* `test_from_dict_ignores_unknown_keys_and_fills_defaults`.
* `test_fingerprint_ignores_row_and_values`: two errors differing only in `row_index/sample_values` have equal fingerprints; different `node_id` differ.
* `test_summary_alias_and_knock_on_property`.
* `test_shorten_collapses_whitespace_and_limits`.
* `test_core_errors_is_qt_free`: run `python -I -c "import trigger_designer.core.errors, sys; assert not any(m.startswith(('qtpy','PyQt6')) for m in sys.modules)"` via `subprocess` with `sys.executable`.

`test_errors_catalogue.py`
* `test_every_rule_code_exists_in_catalogue` and `test_every_non_reserved_code_has_a_rule` (walk `RULES`, compare with `CATALOGUE`; reserved set literal in the test must equal entries with `reserved: True`).
* `test_placeholders_are_allowed`: parse each template with `string.Formatter().parse`; names subset of the allowed list in 3.3.
* `test_rendered_titles_fit_and_have_no_leftovers`: render every entry with a full sample param dict; `len(title) <= 90`; no `{`/`}`; `title` has no emoji (regex `[\U0001F300-\U0001FAFF\u2600-\u27BF]`).
* `test_row_formatting_uses_thousands_separator`: `render_entry("TD-TYP-003", {...,"row":4210}, located=True)[0]` contains `row 4,210`.
* `test_error_codes_doc_is_current` (step 13).

`test_errors_suggest.py`: `Amnt`->`("Amount",)`; `custmer id` -> `("Customer Id",)`; `Totl`->`("Total",)`; `zz` -> `()`; `amount ` (case/space difference) -> exact normalised match first; `limit=3`; stable order; candidates may contain duplicates.

`test_errors_redact.py`: for O4, O6, O34, O35, O36 real messages, `redact_text` removes the value (`"1,2O0.50" not in out`) and keeps the structure; `redact_error` keeps `row_index`, sets `redacted=True`, empties `sample_values`; idempotent; handles empty/None values.

`test_errors_translator.py` - **one test per catalogue code with a real triggering input** (`tests/support/error_triggers.py` supplies `trigger(code_id) -> BaseException`; each test does `exc = trigger("...")` then `err = translate_exception(exc, ctx=ctx)`):

| Test name | Real trigger (module `error_triggers`) | Assertions on the NodeError |
|---|---|---|
| `test_td_in_001_polars_missing_input` | `pl.scan_csv(tmp/"nope.csv").collect()` with `ctx.input_paths={norm(path): 7}` | `code=="TD-IN-001"`, `culprit_node_id==7`, `path` endswith `nope.csv`, `exc_type=="FileNotFoundError"`, `'nope.csv' in title` |
| `test_td_in_002_input_locked` (win32 only) | `CreateFileW(..., share=0)` then `pl.scan_csv(p).collect()` | `TD-IN-002`; `technical` contains `os error 32` |
| `test_td_in_003_sheet_missing_with_suggestion` | `fastexcel.read_excel(xlsx).load_sheet("Dat")` (workbook made with openpyxl, sheet `Data`) | `TD-IN-003`, `did_you_mean==("Data",)`, `"Data" in detail` |
| `test_td_in_004_polars_bad_utf8` | scan of bytes `a,b\n1,\xff\xfe\n` | `TD-IN-004`; second case `UnicodeDecodeError` instance -> same code |
| `test_td_in_005_empty_csv` | 0-byte csv | `TD-IN-005` |
| `test_td_in_006_corrupt_xlsx` | text file named `.xlsx` through `fastexcel.read_excel` | `TD-IN-006` |
| `test_td_in_007_ragged_csv` | `3,4,5` row in a 2-col csv | `TD-IN-007` |
| `test_td_sch_001_polars_column_not_found_did_you_mean` | `lf.select("Amnt").collect()` | `TD-SCH-001`, `columns==("Amnt",)`, `did_you_mean==("Amount",)`, `"Amount" in hint` |
| `test_td_sch_001_polars_drop_uses_ctx_columns` | `lf.drop("Amnt").collect()` with `ctx.input_columns=("Amount","k","s")` | `did_you_mean==("Amount",)` (O2 has no list) |
| `test_td_sch_001_duckdb_binder` | `con.execute("SELECT Amnt+1 FROM t")` | `TD-SCH-001`, `columns==("Amnt",)`, `did_you_mean==("Amount",)`, `params["engine_duckdb"]=="1"` |
| `test_td_sch_002_duplicate_projection` / `_rename_collision` / `_join_suffix` | O10, O11, O12 | `TD-SCH-002`, `columns` contains `z` / `s` / `s` |
| `test_td_sch_004_concat_mismatch` | `pl.concat([a,b])` | `TD-SCH-004`; `"k" in detail`; detail lists a type difference |
| `test_td_sch_005_shape_error` | `pl.DataFrame({"a":[1,2],"b":[1]})` | `TD-SCH-005` |
| `test_td_typ_001_polars_cast_columns_and_target` | `lf.select(col("Amount").cast(pl.Int64)).collect()` | `TD-TYP-001`, `columns==("Amount",)`, `params["target"]=="i64"`, `params["value"]=="1,2O0.50"` |
| `test_td_typ_001_date_cast` | `str.to_date()` on `["2024-01-01","31/12/2024","x"]` | `TD-TYP-001`, `params["target_one"]=="a date"` |
| `test_td_typ_001_duckdb_cast_known_value` | `CAST(Amount AS INTEGER)` | `TD-TYP-001`, `params["engine_duckdb"]=="1"`, `params["value"]=="1,2O0.50"`, third fix mentions `TRY_CAST` |
| `test_td_typ_001_duckdb_decimal_double_quotes` | `CAST(Amount AS DECIMAL(18,2))` | value parsed from double quotes |
| `test_td_typ_001_duckdb_strptime_and_date_format` | O35, O36 | `TD-TYP-001`; strptime case `params["date_format"]=="%Y-%m-%d"` |
| `test_td_typ_001_strict_integer_parsing` | `col("s").str.to_integer()` | `TD-TYP-001` (rule 14) |
| `test_td_typ_002_join_key_mismatch` | `a.join(b,on="k")` | `TD-TYP-002`, `columns==("k","k")`, raw engine types `i64` and `str` appear in the title (this entry deliberately prints the raw type names) |
| `test_td_typ_003_polars_sum_on_string_infers_column` | `group_by("k").agg(col("Amount").sum())` with `ctx.referenced_columns=("Amount",)`, `ctx.input_dtypes={"Amount":"String","k":"Int64"}` | `TD-TYP-003`, `columns==("Amount",)`, `"summed"` in title |
| `test_td_typ_003_duckdb_no_function_matches` | `sum(s)` / `Amount + 1` | `TD-TYP-003` |
| `test_td_typ_004_compare_text_number` (Polars and DuckDB) | O27, O41 | `TD-TYP-004` |
| `test_td_typ_005_int_overflow` | `Series([300]).cast(Int8)` | `TD-TYP-005` (src/dst both numeric) |
| `test_td_typ_006_invalid_dtype_expected` | `unnest("a")` | `TD-TYP-006`, `columns==("a",)` |
| `test_td_typ_007_filter_predicate_not_boolean` | `filter(col("a"))` | `TD-TYP-007`, `"Int64" in title` |
| `test_td_exp_001_duckdb_parser` | `SELECT *, k + AS z FROM t` | `TD-EXP-001`; unterminated string case title mentions closing quote |
| `test_td_exp_002_unknown_function_uses_duckdb_suggestion` | `lenght(s)` | `TD-EXP-002`, `params["suggestion"]=="length"` |
| `test_td_exp_003_binder_leftover` | ambiguous `SELECT k FROM t a, t b` | `TD-EXP-003` |
| `test_td_exp_004_bad_regex` | `str.replace("(","x")` | `TD-EXP-004`, `"unclosed group" in detail` |
| `test_td_exp_005_duckdb_invalid_input` | scalar subquery returns many rows | `TD-EXP-005` |
| `test_td_out_001_output_folder_missing` | `lf.sink_csv(tmp/"nodir"/"x.csv")` with `ctx.output_paths` containing that path, node id 9 | `TD-OUT-001`, `culprit_node_id==9` |
| `test_td_out_002_output_locked` (win32) / `_readonly` | handle without sharing; chmod 0o444 | `TD-OUT-002` |
| `test_td_out_003_xlsxwriter_missing` | monkeypatch `sys.modules["xlsxwriter"]=None` then `df.write_excel(...)` (real `ModuleNotFoundError`/`ImportError`) | `TD-OUT-003` |
| `test_td_out_004_invalid_filename_and_directory` | `sink_parquet(tmp/"a<b.parquet")` (win32) ; `sink_csv(tmp)` (any OS) | `TD-OUT-004` |
| `test_td_out_005_disk_full_message` | synthetic `OSError("There is not enough space on the disk. (os error 112): C:/x/out.csv")` (cannot be provoked safely) | `TD-OUT-005` |
| `test_td_out_006_no_incoming_data` | instantiate `FileOutputContent` unwired and call `get_code()` (real `ValueError`) | `TD-OUT-006` |
| `test_td_run_001_timeout` | `NodeExecutor` with `max_execution_time=1` and code `time.sleep(3)`; take `result.exception` | `TD-RUN-001`, `params["seconds"]=="1"` |
| `test_td_run_002_memory` | `ExecutionMemoryError("Memory usage exceeded limit: 612.00MB")` and bare `MemoryError()` | `TD-RUN-002`, `"612" in detail`; empty-message case does not crash |
| `test_td_run_003_004_005_008_built_without_exception` | `make_error(...)` | severities `error/warning/warning/warning`, `knock_on` true, titles contain the culprit label |
| `test_td_run_006_name_error_maps_variable_owner` | `exec("x = var_formula_555")` | `TD-RUN-006`, `ctx.variable_owners={"var_formula_555": 555}` -> `culprit_node_id==555` |
| `test_td_sys_001_legacy_value_error` | `ValueError("Both inputs must be connected")` | `TD-SYS-001`, title equals that text |
| `test_td_sys_100_generic_polars` | `pl.DataFrame({"a":[1]}).select(pl.col("a").get(10))` (OutOfBounds) | `TD-SYS-100` |
| `test_td_sys_998_panic_is_baseexception` | `raise pe.PanicException("boom")` caught as `BaseException` | `TD-SYS-998` |
| `test_td_sys_999_unknown_exception` | `class Weird(Exception)` | `TD-SYS-999`, `technical` has the message |
| `test_reserved_codes_render` | `make_error` for `TD-SCH-003, TD-JOI-001/002, TD-OUT-010..014, TD-IN-010..014, TD-SCH-010/011` | non-empty titles |
| `test_rule0_passthrough_known_codes` | exception with `.code="TD-AUDIT-001"` and message `Choose the key column.`; `ValueError("[TD-SHAPE-003] Column(s) not found: a")`; `ValueError("TD-AUDIT-002: Column 'x' is not in the input data.")` | code kept, `title` = message without prefix, `hint` from 3.5b, severity per table; `columns` from `e.columns` when present |
| `test_rule0_unknown_td_code_falls_back_gracefully` | `Exception("[TD-ZZZ-999] something")` and an exception with `.code="TD-FOO-001"` | `NodeError.code` equals that code, title = message, no exception, `hint==""` |
| `test_rule0_ignores_non_td_codes` | `.code=404`, `.code="E1"`, `.code=None` | falls through to the normal rules |
| `test_plan_one_kind_to_code_mapping` | every kind of the 3.5b mapping built as an exception with `.code` | each renders a non-empty title and the code is in `CATALOGUE` |
| `test_every_plan_code_is_in_catalogue` | grep `src/trigger_designer` (and `docs/plan/0[1-8]*.md` when present) for `TD-(AUDIT\|SHAPE\|CLI\|IN\|SCH\|OUT)-\d{3}` | every match is a `CATALOGUE` key |

`test_errors_translator_fuzz.py` (graceful fallback, never crash):
* `test_translate_never_raises_on_weird_inputs` parametrised over: `None`, `""`, `"plain string"`, `Exception()`, exception whose `__str__` raises, exception with 1 MB message, message containing lone surrogates (`"\ud800"`), NUL bytes, `KeyboardInterrupt()`, `SystemExit(3)`, an exception whose `original_exception` is itself (cycle), a chain A->B->A via `original_exception`, `NodeExecutionError("", original_exception=None)`, an `OSError` with `filename=None` and message `"(os error 5)"`, a regex-catastrophe string `"a"*100000`, an `ExceptionGroup`. Each: result is `NodeError`, `code.startswith("TD-")`, `title` non-empty and `len(title) <= 90`, `len(technical) <= 100_020`.
* `test_translate_mutated_real_messages_never_crash`: `random.Random(1234)`; take the 40 real messages of section 3.4 captured by `error_triggers`, mutate each 25 times (delete a random slice, insert random punctuation, truncate, duplicate a line, swap quotes), wrap in `Exception`/ the original class where constructible; 1,000 translations total; assert no exception and a valid `NodeError`, and that translation of all 1,000 takes < 2 s (regex backtracking guard).
* `test_unknown_class_with_known_text_still_matches_by_text`: `type("X",(Exception,),{})("conversion from `str` to `i64` failed in column 'A' for 1 out of 1 values: [\"x\"]")` -> rule 13 requires class names, so expect `TD-SYS-999`; documents that matching is class-gated (rule 1 and 33 are the only text-only exceptions).

`test_errors_locator.py`
* `test_locator_matches_example_row_4210`: 5,000-row frame `Amount=[str(i)...]` with `"1,2O0.50"` at index 4209 -> `row_index==4210`, `values==("1,2O0.50",)`, `status=="found"`.
* `test_locator_returns_up_to_five_distinct_values_in_row_order`: 20 bad rows, 3 distinct values -> 3 values, first row correct.
* `test_locator_cap_respected_and_reports_not_found`: bad row beyond `row_cap=100` -> `status=="not_found"`, `cap_hit`.
* `test_locator_known_value_exact_row` (DuckDB): value `" 12"`-style whitespace difference -> row found through query B.
* `test_locator_decimal_date_and_overflow_targets`: probe for `Decimal(18,2)`, `Date` (format given), `Int8` from Int64.
* `test_locator_non_string_source_overflow`: `[1,300,2]` -> row 2.
* `test_locator_handles_nulls_and_empty_frame`; `test_locator_skips_when_column_missing`; `test_locator_display_escapes_control_chars_and_truncates` (value `"x"*500+"\n"` -> length <= 81, no raw newline).
* `test_locator_never_raises_on_broken_plan` (frame whose plan raises) -> `status=="error"`.
* `test_locator_on_csv_scan_is_fast` (marks `slow`): 1,000,000-row CSV in `tmp_path`, bad row at end: `elapsed_s < 5`.

`test_errors_attribution.py`: `test_schema_pass_finds_first_failing_ancestor` (frames: ok, `select("zz")` plan, ok -> index 1); `test_data_pass_finds_cast_ancestor` (strict cast plan with bad value in first 100 rows); `test_returns_none_when_all_ancestors_ok`; `test_data_pass_respects_budget` (budget 0 -> `None`); `test_none_frames_are_skipped`; `test_attribution_ignores_ancestors_with_different_exception_type` (data pass only counts the same `exc_type`).

`test_errors_enrich.py`: `test_enrich_moves_root_to_culprit_and_adds_knock_on` (3 ancestors, culprit second; root.node_id == culprit, knock_on.code == "TD-RUN-003", `culprit_node_id` set); `test_enrich_adds_row_and_rebuilds_text` (title contains `row 4,210`); `test_enrich_with_locate_disabled_keeps_status_disabled`; `test_enrich_redact_hides_values_keeps_row`; `test_enrich_never_raises_returns_original`.

`test_executor_errors.py`
* `test_result_keeps_original_exception_and_traceback_text`: node code raising `pl.exceptions.ColumnNotFoundError` -> `isinstance(result.exception, ColumnNotFoundError)`, `"ColumnNotFoundError" in result.traceback_text`, `result.error` unchanged format.
* `test_raw_exception_preserved_in_translation`: `translate_exception(result.exception, traceback_text=result.traceback_text).technical == str(result.exception)` and `.exc_type == "ColumnNotFoundError"` and `"Traceback" in .traceback`.
* `test_panic_exception_is_a_failure_not_success` (`BaseException` subclass raised in code): `result.success is False`, `result.exception` is the panic, **and the next `execute_node` on the same executor succeeds in < 2 s** (worker thread survived).
* `test_empty_memory_error_message_translates` (`raise MemoryError()`).
* `test_without_frames_drops_exception`.
* `test_traceback_is_released_after_formatting` (`result.exception.__traceback__ is None`).

`test_run_policy_errors.py` (semantics of 3.15, exercised through plan 09 F-C's Qt-free run loop with a stub executor and stub nodes; mixin-level assertions follow `tests/unit/test_workflow_execution_mixin.py`):
* `test_stop_on_first_failure_when_continue_off` (A ok, B fails, C independent: C never started).
* `test_continue_runs_independent_branch` (graph: S->B(fail)->D ; S->C; `continue_on_error=True`: order S,B,C; D reported as skipped with blocker B; overall success False).
* `test_skip_propagates_transitively` (B fails, D, E downstream: both skipped, blocker for E is D).
* `test_multi_input_node_is_skipped_when_any_parent_failed`.
* `test_cancel_reports_skipped_with_none_blocker` (mixin renders `TD-RUN-004`).
* `test_node_errored_path_also_continues`.
* `test_skipped_node_gets_td_run_008_and_is_not_invalid` (mixin level).

`test_problems_store.py`: `test_upsert_dedupes_equal_errors` (second equal upsert returns False, `changed` emitted once), `test_upsert_replaces_on_new_fingerprint`, `test_run_entries_listed_before_live`, `test_clear_source_run_leaves_live`, `test_roots_only_count_excludes_knock_on`, `test_remove_by_node`.

`test_sql_diagnostics.py` (Qt-free part of 3.10): `test_formula_binder_message_has_hint_and_no_sql_artifacts` (no `LINE`, `Candidate`, `df_step_`, `"AS"`), `test_formula_unknown_function_message` (`NOSUCHFUNC` -> contains `Unknown function`), `test_parser_exception_keeps_syntax_category`, `test_message_length_le_160`.

### 6.2 UI tests (`tests/ui/`, pytest-qt, offscreen)

`test_node_error_state.py`
* `test_live_cast_error_sets_tooltip_and_badge`: Formula node with `CAST([Amount] AS INTEGER)` fed by the ledger frame; after `eval()`: `node.isInvalid()`, `node.current_error.code == "TD-TYP-001"`, `node.grNode.toolTip()` startswith `Formula` and contains `Fix:` and `TD-TYP-001`, `"Traceback" not in tooltip`, `len(tooltip) <= 600`.
* `test_error_badge_is_painted_in_danger_colour`: render `node.grNode` to a `QImage` via `QGraphicsScene.render` on a 140x140 image; pixel at badge centre equals `get_theme_manager().color("danger")` (tolerance 8); after `clear_error()` the pixel is not that colour.
* `test_badge_visible_even_when_status_badge_hidden`: `grNode.setDetailState({"badge": False})`.
* `test_successful_reeval_clears_live_error_tooltip_and_badge`.
* `test_run_error_wins_over_live_and_survives_live_reeval`: set run error, trigger a successful live `eval()` of the node -> tooltip still run error; then `onInputChanged()` clears the run error.
* `test_knock_on_live_errors_not_in_problems_store`: unconnected input -> `TD-RUN-005` on node, `window.problems.count()==0`.
* `test_upstream_failure_message_names_upstream_node`: B connected to invalid A -> B tooltip contains A's label, code `TD-RUN-003`.
* `test_legacy_tooltip_is_wrapped_as_td_sys_001`.
* `test_identical_error_does_not_relog` (spy `window.logError` call count after two identical evals == 1).
* `test_redaction_pref_hides_values_in_tooltip_and_log`.

`test_problems_dock.py`
* `test_dock_lists_error_with_node_code_and_message` (store upsert -> tree row texts).
* `test_click_row_selects_node_and_updates_config_dock` (`window.scene.getSelectedItems()` is `[node.grNode]`).
* `test_copy_details_puts_text_on_clipboard` (`QGuiApplication.clipboard().text()` contains `[TD-TYP-003]`, no `--- technical ---` when toggle off, contains it when on).
* `test_technical_toggle_shows_raw_exception_and_persists_pref`.
* `test_empty_state_and_tab_title_count` (`Problems (2)`).
* `test_dock_follows_active_window_switch`.
* `test_prunes_rows_of_deleted_nodes`.
* `test_buttons_have_tooltip_and_accessible_name_and_no_inline_style` (`styleSheet()==""`).
* `test_dock_registered_in_default_layout_and_menu` (`TriggerWindow`).

`test_error_enricher.py`: `test_enrichment_posts_row_number_to_store` (`qtbot.waitUntil(lambda: store.entries()[0][1].row_index == 4210)`), `test_stale_generation_result_ignored`, `test_timeout_marks_locate_status_timeout` (monkeypatch the job to sleep 0.3 s with timeout 0.05 s).

`test_errors_preferences.py`: dialog round trip of the four editable keys; defaults (`True, False, True, 5000000`).

`test_formula_node.py` / `test_filter_expression.py` (existing): must not regress (compare to baseline names).

### 6.3 `tests/unit/test_node_base.py` additions
`test_eval_value_error_still_marks_invalid_and_descendants_dirty`; `test_eval_exception_still_calls_dump_exception` (patch `dumpException`).

### 6.4 E2E golden workflows (`tests/e2e/test_error_workflows.py`, `tests/support/errors.py`)

Helper `assert_error_golden(err, name)`: projects `{code, severity, node_title, columns, row_index, sample_values, culprit_node_title, title, hint}` (no ids, times, technical, traceback) to JSON, compares with `tests/e2e/fixtures/expected_errors/<name>.json`; rewritten when `TRIGGER_UPDATE_E2E_GOLDENS=1` (same switch as `frames.py:84-88`). Workflows are **built in the test** (brief 9.4 skeleton: `TriggerSubWindow()`, `get_class_from_opcode`, `Edge`, `scene.saveToFile`, reload, `run_workflow_and_wait`); fixture files are written to `tmp_path`.

`LEDGER` fixture (exact text, UTF-8):
```
Invoice,Amount,Date
INV-1,10.50,2024-01-05
INV-2,20.00,2024-01-06
INV-3,"1,2O0.50",2024-01-07
INV-4,30.25,2024-01-08
```

| Test / golden | Graph | Expected |
|---|---|---|
| `test_missing_input_file` -> `missing_input.json` | File Input(`tmp/gone.csv`, never created) -> File Output(`tmp/out.csv`) | live: File Input has `TD-IN-001` (via `check_file_path`); after Run: root error on **File Input** (`node_title=="File Input"`), `code=="TD-IN-001"`, File Output has `TD-RUN-003` with `culprit_node_title=="File Input"`; `out.csv` not created |
| `test_bad_cast_in_formula` -> `bad_cast_formula.json` | File Input(LEDGER) -> Formula(`target_column="AmountNum"`, `formula_text="CAST([Amount] AS DOUBLE)"`, `target_dtype=""`) -> File Output | Formula root error: `TD-TYP-001`, `columns==["Amount"]`, `row_index==3`, `sample_values==["1,2O0.50"]`, `title=="Column 'Amount' contains '1,2O0.50' in row 3, which cannot be read as numbers."`; File Output has `TD-RUN-008` (skipped); no `out.csv` |
| `test_misspelt_column_in_formula` -> `misspelt_column.json` | File Input(LEDGER) -> Formula(`target_column="Double"`, `formula_text="[Amnt] * 2"`) -> File Output | `TD-SCH-001`, `columns==["Amnt"]`, `did_you_mean` suggestion `Amount` in `hint`; (live diagnostic from `validate_section_text` returns a message containing `Amount`) |
| `test_output_folder_missing` -> `output_folder_missing.json` | File Input(LEDGER) -> File Output(`tmp/no_such_dir/out.csv`) | File Output root error `TD-OUT-001`; File Input has no error and `execution_results` contains the File Input |
| `test_output_file_locked` (win32 only, `skipif`) -> `output_locked.json` | same, `out.csv` pre-created and held with `CreateFileW(share=0)` for the run | `TD-OUT-002` on File Output |
| `test_unwired_output` -> `unwired_output.json` | lone File Output | `TD-OUT-006` |
| `test_independent_branch_continues` (no golden) | `File Input(LEDGER)` -> Formula(bad cast) -> File Output A ; `File Input(LEDGER)` -> Normalize -> File Output B (`tmp/b.csv`) ; prefs `errors/continue_past_failure=True` | `b.csv` exists and equals the Normalize golden semantics (header normalised, 4 rows); A node errors as above; `window.problems.count("error", roots_only=True)==1`; `execution_results` has the Normalize and File Output B nodes |
| `test_independent_branch_stops_when_preference_off` | same with `False` | `b.csv` does **not** exist **if** the Formula branch is ordered first by `topologicalSort`; to make the test deterministic assert `not (b exists and nodes_after_failure_ran)`: assert that **no node after the first failing node in `window._workflow_sorted_nodes` has an `execution_results` entry** |
| `test_raw_exception_preserved_e2e` | the bad-cast workflow | root error `technical` contains `Could not convert string '1,2O0.50'`, `exc_type=="ConversionException"`, `traceback` non-empty, and the Logging dock text (read `window.getLoggingDock().logs_per_window[str(id(window))]`) contains `TD-TYP-001` |
| `test_redaction_e2e` | same with `errors/redact_values=True` | no stored string field (`title/detail/hint/technical/traceback/tooltip`) contains `1,2O0.50`; `row_index==3`; log lines too |
| `test_rerun_after_fix_clears_error_and_badge` | bad cast, then set the formula to `TRY_CAST([Amount] AS DOUBLE)`, rerun | no errors in the store; badge cleared; `out.csv` written |
| `test_repeated_run_does_not_duplicate_rows` | run twice with the same failure | store has the same number of rows after the second run |

Phase 12 acceptance for every golden: run `TRIGGER_UPDATE_E2E_GOLDENS=1` once, **read** the diff of `tests/e2e/fixtures/expected_errors`, confirm each file against the table above, commit.

---

## 7. Acceptance checklist

- [ ] `core/errors` imports without Qt (`test_core_errors_is_qt_free`).
- [ ] `CATALOGUE` is the only place with user-facing error sentences (grep: no sentence from 3.5 appears elsewhere in `src/`).
- [ ] Every catalogue code (non-reserved) has a real-trigger translator test; all 3.4 observations reproduced by the test helpers.
- [ ] The example sentence is produced by a test (`TD-TYP-003` with row 4,210).
- [ ] `ExecutionResult.exception`/`traceback_text` populated with the step-4 semantics (fields supplied by plan 09 F-B); `PanicException` no longer reports success and the worker thread survives (plan 09 F-A; verified by `test_panic_exception_is_a_failure_not_success`).
- [ ] Translator rule 0 passes through any `TD-` coded exception; every code in 3.5b is in `CATALOGUE`; an unknown `TD-` code degrades gracefully (test).
- [ ] `core/errors/` is a package and `from trigger_designer.core.errors import NodeError, translate_exception` works; no `core/errors.py` file exists.
- [ ] `enrich_sync(...)` runs without Qt and returns the culprit/row (test), so plan 02/08 records carry them.
- [ ] Run failure puts a tooltip, badge, Problems row and a Logging line on the right node; root cause sits on the upstream culprit when attribution succeeds.
- [ ] Independent branches continue by default; preference reverts to stop-at-first; skipped nodes show `TD-RUN-008`.
- [ ] Formula/Filter diagnostics keep positions and the four `test_formula_node.py` baselines; non-parser messages are plain language with a fix.
- [ ] `errors/redact_values` removes values from tooltip, dock, log, clipboard text; row numbers kept.
- [ ] Preferences dialog shows the four keys; defaults `True/False/True/5,000,000`.
- [ ] Problems dock: click selects node, copy works, technical toggle works and persists, count in tab title.
- [ ] New QSS objectNames exist in both `base.qss` and `qss/_style.scss`; no inline `setStyleSheet`; `test_theme_tokens.py` passes.
- [ ] `tests\unit` >= 334 + new tests all pass; `tests\e2e` >= 20 + new pass; `tests\ui` shows no new failures versus the 20 failed / 7 error baseline (compare test ids).
- [ ] `ruff format` and `ruff check` clean on every touched file.
- [ ] `docs/ERROR_CODES.md` generated and current.

---

## 8. Verification commands (PowerShell, repo root; never bare `pytest`)

```powershell
# per step (format + lint only touched files, then the step's tests)
.venv\Scripts\python.exe -m ruff format src\trigger_designer\core\errors tests\unit\test_errors_translator.py
.venv\Scripts\python.exe -m ruff check  src\trigger_designer\core\errors tests\unit\test_errors_translator.py

# Qt-free layers
.venv\Scripts\python.exe -m pytest tests\unit\test_errors_model.py tests\unit\test_errors_catalogue.py tests\unit\test_errors_suggest.py tests\unit\test_errors_redact.py -q
.venv\Scripts\python.exe -m pytest tests\unit\test_errors_translator.py tests\unit\test_errors_translator_fuzz.py -q
.venv\Scripts\python.exe -m pytest tests\unit\test_errors_locator.py tests\unit\test_errors_attribution.py tests\unit\test_errors_enrich.py -q
.venv\Scripts\python.exe -m pytest tests\unit\test_executor_errors.py tests\unit\test_execution_result.py tests\unit\test_run_policy_errors.py tests\unit\test_workflow_execution_mixin.py tests\unit\test_problems_store.py tests\unit\test_sql_diagnostics.py -q

# whole unit layer (expect 334 + new, 0 failures)
.venv\Scripts\python.exe -m pytest tests\unit -q

# UI layer: only the new files, then compare the whole layer with the baseline
.venv\Scripts\python.exe -m pytest tests\ui\test_node_error_state.py tests\ui\test_problems_dock.py tests\ui\test_error_enricher.py tests\ui\test_errors_preferences.py -q
.venv\Scripts\python.exe -m pytest tests\ui -q          # expect 20 failed / 7 errors, same ids as baseline (brief 2.4)
.venv\Scripts\python.exe -m pytest tests\ui\test_formula_node.py tests\ui\test_filter_expression.py -q   # no NEW failures

# e2e
.venv\Scripts\python.exe -m pytest tests\e2e -q          # 20 + new
$env:TRIGGER_UPDATE_E2E_GOLDENS="1"; .venv\Scripts\python.exe -m pytest tests\e2e\test_error_workflows.py -q; Remove-Item Env:TRIGGER_UPDATE_E2E_GOLDENS
git diff tests\e2e\fixtures\expected_errors      # review by hand

# slow locator timing (opt-in marker)
.venv\Scripts\python.exe -m pytest tests\unit\test_errors_locator.py -q -m slow
```

Manual smoke (after step 9): `.venv\Scripts\python.exe -m trigger_designer`, open `data\check.csv` as File Input -> Formula `CAST([Relevancy Score] AS INTEGER)` (the sample column contains decimals) -> File Output; Run; confirm tooltip, red "!" badge, Problems tab, click-to-select, copy details, technical toggle; rename the column to `Relevancy Scor` and confirm "Did you mean".

---

## 9. Pitfalls

1. **`result.error` is not the exception text.** It may be only a traceback (empty `MemoryError`) and has `"\n\nOriginal traceback:\n..."` appended (C1). Always translate `result.exception`; use `result.error` only when `exception is None`.
2. **Polars streaming counts are batch counts** (O5). Never display `failing_count` as a table total; it is stored only for live (non-streaming) errors.
3. **Windows `OSError` has `errno=None`** (O17-O19): match on the `(os error N)` text, not on `e.errno` or on `PermissionError`.
4. **`scan_csv(missing)` does not raise** (O14); the error appears at the sink. Path-based attribution (rule 8) is what names the File Input.
5. **Exceptions keep tracebacks -> frames -> frames of data.** `traceback_text` is formatted on the exec thread and `__traceback__` cleared; `without_frames()` drops the exception. A long-lived `ExecutionResult` must never hold the live exception.
6. **`BaseException` is not `Exception`** (`PanicException`, `KeyboardInterrupt`): the translator accepts `BaseException`; the executor thread must catch it (plan 09 F-A, D12); this plan only tests it.
7. **Do not import Qt in `core/errors`.** The translator receives a duck-typed `node` only through `ErrorContext.from_node` (getattr). `build_context` (Qt side) does the real work.
8. **Do not call the locator or attribution on the GUI thread** and do not pass nodes/widgets to them; pass LazyFrames only (D3).
9. **`getSocketValue` first-match semantics** (brief 3.3): when building `inputs_of` use `getInputWithSocket(i)` to find the exact upstream socket, not `getSocketValue`.
10. **Tooltips set directly by legacy code** (68 sites) will overwrite the new tooltip. `set_error` is the only writer for failing nodes; when a legacy site runs after it, `_apply_error_state` is re-invoked from `evalImplementation`'s `result is None` branch. Do not add new direct `setToolTip` error calls.
11. **Formula tests pin message shapes** (C11): `last_error` must start with `Section 1:` and `section_errors[i] == last_error.removeprefix("Section 1: ")`; do not change `_shorten_error`.
12. **`boundingRect` is cached** (C9). The badge lives inside the body rect; if you ever draw outside, invalidate `_bounding_rect`.
13. **Undo/redo is untouched.** Errors are runtime state, not model state: never push history entries or write widgets from the translator/store (AGENTS.md "model is the only truth"). Restores trigger `eval()` which re-sets/clears errors naturally; do not special-case it.
14. **Frozen dataclass + dict fields**: `params`/`SuggestedFix.params` are `compare=False`; never mutate them after construction, use `with_updates`.
15. **Logging dock is not thread-safe** (brief 7.5): `set_error` is only called from the GUI thread (slots); never log from the enrichment thread.
16. **Dock registration needs a stable `objectName`** (`ProblemsDock`) or `restoreState` breaks layouts of existing users; also add it to `apply_default_layout`.
17. **QSS**: a `{token}` missing from any theme aborts startup (`test_theme_tokens.py`); reuse `danger`, `warning`, `accent_primary`, `background_hover`, `background_pressed`, `text_secondary`, `button_bg` only.
18. **`ruff check` baseline is dirty** (brief 2.3): run it on touched files and compare, do not "fix" unrelated findings.
19. **Do not use bare `pytest`** (aborts, brief 2.4); the commands in section 8 name layers.
20. **PowerShell `>` writes UTF-16**: write golden JSON with `json.dumps(..., ensure_ascii=False)` through Python (`Path.write_text(encoding="utf-8")`), as `frames.py` does for CSV.

---

## 10. Interfaces for the other plans

* **Plan 02 (audit trail)** embeds `NodeRunRecord.error: NodeError | None` via `NodeError.to_dict()` / `from_dict()`. A record must carry the **enriched** error (culprit + row). Two entries: (a) GUI: `ProblemsStore.pending: int` and `ProblemsStore.settled = Signal()` (emitted when pending returns to 0); persist failed runs on `settled`, successful ones immediately. (b) No GUI / blocking: the synchronous, Qt-free
  ```python
  def enrich_sync(error: NodeError, *, ancestors: Sequence[Ancestor] = (), inputs_of: Mapping[int, Sequence[Any]] | None = None,
                  labels: Mapping[int, str] | None = None, titles: Mapping[int, str] | None = None,
                  ops: Mapping[int, str] | None = None, attribute: bool = True, locate: bool = True,
                  row_cap: int = 5_000_000, redact: bool = False) -> EnrichResult
  ```
  in `core/errors/enrich.py` (builds an `EnrichJob`, calls `enrich_error`; never raises; typically < 1 s, worst case ~15 s). Plans 02 (finalise paths) and 08 call it directly with LazyFrames from `execution_results` / the executor context (`inputs_of[node_id]` = frames entering that node), so run-log and CLI records carry `culprit_node_id`, `row_index`, `sample_values`. `ExecutionResult.exception/traceback_text` are available for 02's own use. When `redacted` is True store the scrubbed record unchanged.
* **Plan 08 (CLI)**: `translate_exception(result.exception, ctx=ErrorContext(...), redact=flag)` and `enrich_sync(...)` are pure and synchronous. Console line = `err.render_summary()` + `Fix: {err.hint}`; JSON = `err.to_dict()`. **Exit codes: this plan's earlier proposal is superseded by plan 08's table (its section 3.4); plan 03 defines no exit codes.** Plan 08's `TD-CLI-*` codes are in 3.5b and arrive through rule 0. The continue flag maps to the policy in 3.15 (CLI default False, `--keep-going` True).
* **Plan 01**: its kind -> code table (copied in 3.5b) is authoritative; `InputReadError` carries `.code`, `.path`, `.sheet`, `.kind`, so rule 0 needs no `isinstance`. `ErrorContext.input_paths` is built from `FileInputContent.resolved_input_files()` once 01 lands (fallback today: `content.filePath`). `TD-SCH-003` (drift vs snapshot) stays reserved for 01's `validate_loaded_state`.
* **Plan 04**: uses `TD-AUDIT-*` (3.5b); `TD-TST-*` is **not** defined by this plan. `AuditConfigError` messages are `"<code>: <message>"` and also carry `.code`; rule 0 handles both. Test *failures* stay `TestSummary` results, not `NodeError`s.
* **Plan 06**: `ExcelWriteError.code` is passed through rule 0. `TD-OUT-001..003` and `006` keep the meanings in 3.5; plan 06 owns `TD-OUT-010..014` (table in 3.5b copied from its section 10.3). This plan's `TD-OUT-004..006` keep their meanings (invalid output name, disk full, nothing connected); `TD-OUT-007..009` are unused.
* **Plan 07**: `ShapingError` text `"[TD-SHAPE-NNN] detail"` goes through rule 0; the `ERROR_CODES` titles are mirrored in 3.5b.
* **Plan 09**: F-A (executor `BaseException`, `node_name`), F-B (`ExecutionResult` fields, hook stubs), F-C (run loop with the 3.15 semantics), F-D (cancellation). This plan edits none of those lines.
* **All plans**: new error codes are added **only** in `core/errors/catalogue.py`, with a rule or `reserved: True`, a real-trigger test, and a regenerated `docs/ERROR_CODES.md`.
* **Translator contract** (Qt-free, never raises): `translate_exception(exc, *, node=None, phase="run", ctx=None, redact=False, traceback_text="") -> NodeError`; `make_error(code, ctx=None, *, severity=None, **params) -> NodeError`; `enrich_error(EnrichJob) -> EnrichResult`; `enrich_sync(error, **kw) -> EnrichResult`; `ErrorContext` fields as in 3.2 (all optional).
