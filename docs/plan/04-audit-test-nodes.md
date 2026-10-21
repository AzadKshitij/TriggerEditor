# 04 - Audit test nodes (family "Audit": Duplicates, Gaps, Benford, Sample, Risk Filters)

Status: implementation plan. Author context: written 2026-10-21 against `main` @ `71b4041`; builds on `docs/plan/00-codebase-brief.md` (the "brief"). Every file:line below was opened or grepped on that date. Every numeric result and Polars call in this plan was executed with `uv run --no-sync --project . python <script>` against the installed `polars 1.44.2` / `numpy 2.5.3`; the numbers quoted as "verified" are the printed output of those runs.

Decisions are final. Where the brief or a sibling plan leaves a choice, this plan picks one and gives a one-line reason. Nothing in here is an open question.

## Table of contents

1. [Goal and non-goals](#1-goal-and-non-goals)
2. [Current state (verified)](#2-current-state-verified)
3. [Shared foundations](#3-shared-foundations)
   3.1 Family and registration - 3.2 File layout - 3.3 Op ids and migration - 3.4 Errors and codes - 3.5 `common.py` - 3.6 Summary frame and `TestSummary` - 3.7 `AuditResult` and generated code - 3.8 Content mixin - 3.9 Node base - 3.10 Shared widget - 3.11 Icons - 3.12 Execution model per node
4. [The five nodes](#4-the-five-nodes)
   4.1 Duplicates - 4.2 Gaps - 4.3 Benford - 4.4 Sample - 4.5 Risk Filters
5. [Ordered implementation steps](#5-ordered-implementation-steps)
6. [Edge cases per node](#6-edge-cases-per-node)
7. [Test plan](#7-test-plan)
8. [Acceptance checklist](#8-acceptance-checklist)
9. [Verification commands](#9-verification-commands)
10. [Pitfalls](#10-pitfalls)
11. [Interfaces to other plans](#11-interfaces-to-other-plans)

---

## 1. Goal and non-goals

**Goal.** Add a new node family **Audit** with five nodes that an auditor can drop on the canvas, point at columns, and run - each producing a *population/exception split*, a one-row *Summary* frame that describes what was tested and what was found, and (for Sample) a *Selection log* that lets a reviewer re-perform the draw.

| Node | What it answers | Outputs (socket order) |
|---|---|---|
| **Duplicates** | Which rows repeat (exactly, or nearly: amount within a tolerance, date within N days)? | `D` Duplicates, `U` Unique, `S` Summary |
| **Gaps** | Which numbers are missing from a sequence (`JE-000123`), repeated, or out of order; which calendar days have no entries? | `G` Gaps, `S` Summary |
| **Benford** | Does the leading-digit distribution of an amount column look natural? | `T` Table (observed vs expected), `S` Summary, `D` Drill-down rows |
| **Sample** | A reproducible sample (random, systematic, monetary-unit, stratified) | `S` Sample, `N` Not sampled, `L` Selection log |
| **Risk Filters** | Which journal entries trip one or more classic risk indicators? | `F` Flagged, `N` Not flagged, `S` Summary |

**Non-goals (decided, with reason).**

* No fiscal calendars. Weekends are Saturday/Sunday; period end is one user-typed date. Reason: calendars differ per client; one date and a holiday list cover the workflow without a calendar engine.
* No statistical sample-size calculators, no evaluation of sample results, no confidence levels. Reason: Sample draws; evaluation belongs to the auditor's methodology.
* No Benford second-digit / last-two-digit tests. Reason: the brief asks for first-digit and first-two-digit; the table machinery generalises later without changing the schema.
* No fuzzy *text* matching (Levenshtein) in Duplicates. Reason: near mode is defined on amount and date only; fuzzy text needs a new dependency.
* No gap `step` other than 1. Reason: document sequences increase by 1; a step setting multiplies edge cases for no audit use.
* No per-node caching of results between live evaluation and Run. Reason: the brief's two evaluation paths are independent (brief section 4); a cache would need invalidation rules this plan does not own.
* No new dependency. `numpy` (pinned `2.5.3`, `pyproject.toml:38`) is already a core dependency; `scipy` is not installed, so the chi-square p-value is implemented in 30 lines (verified, section 4.3).
* No new icons are drawn. The nodes reuse existing icon ids (section 3.11).

---

## 2. Current state (verified)

| Fact | Where |
|---|---|
| Families are `NodeTypes(StrEnum)` with 5 members: `IO, PREPARATION, JOIN, TRANSFORM, REPORT` | `src/trigger_designer/core/node_configuration.py:23-28` |
| Op-code enums are `IntEnum` + `auto()`; last Preparation member is `NORMALIZE_COLUMNS`; `ReportNodes` ends at `GRAPH` | `core/node_configuration.py:31-66` (`PreparationNodes` at `:38`, `ReportNodes` at `:64`) |
| Registry dict and op-enum map are hard-coded per family | `core/node_configuration.py:69-75` (`NODE_REGISTRIES`), `:79-85` (`_OPCODE_ENUMS`) |
| `get_class_from_op("family.name")` does `NodeTypes(family)` then `_OPCODE_ENUMS[family][name.upper()]`, so a new family needs both maps | `core/node_configuration.py:267-288` |
| `register_lazy_node(...)` records title/icon so the palette needs no import | `core/node_configuration.py:200` |
| Lazy specs list and helper-module exclusion set | `qt/widgets/nodes/__init__.py:14` (`_LAZY_NODE_SPECS`), `:156-159` (`_LAZY_HELPER_MODULES`) |
| The palette builds one tab **per `NodeTypes` member** automatically (`for node_type in NodeTypes:`), tab title = `node_type.value.title()` | `qt/docks/nodes_list.py:33-45` |
| The Shift+A menu has a **hard-coded** category dict that must gain `"Audit"` | `qt/helpers/context_menu_mixin.py:40-46` |
| Drop handler does `NodeTypes(node_type)` on the dragged string, so `"audit"` works with no change | `qt/design_window.py:662` |
| Multi-output precedent: `outputs=[3, 3], output_text=["E", "V"]`; `param` holds one dict per socket | `qt/widgets/nodes/Preparation/split.py:468-476, 489-551`; Filter `outputs=[3,3]` at `Preparation/filter.py:1136` |
| Summary-as-frame precedent: Count emits `pl.DataFrame({'Count': [n]})` and always defines its variable | `qt/widgets/nodes/Transform/count_records.py:100-132` |
| `after_execution(variables)` hook is called on the exec worker thread after a successful exec; failures become warnings | `core/ExecutionCheck/executor.py:359-370` (only `Report/graph.py:545` uses it today) |
| `frame_schema(frame)` returns `{name: dtype}` lazily | `qt/node_base.py:59-72` |
| `evalImplementation` / `processInputs` / `getSocketValue` / `_set_node_tooltip` | `qt/node_base.py:816`, `:803`, `:708`, `:775` |
| Undo: flat attribute paths resolve with `set_in` (`("amount_column",)` -> `setattr`); lists are replaced whole | `qt/undo/commands.py:61-91` |
| Config Dock sweep skips children of any widget with `_undo_composite = True`; Union marks its own sections so it can commit explicitly | `qt/node_base.py:557-592`, `Join/union.py:342-349` |
| Shared widgets: `SegmentedControl` (value is the **label text**, `set_value` does not emit), `ColumnChecklist` (`changed(list)`, `setChecked`, `checked()`), `NoWheelComboBox`, `FormRow`, `ConfigSection` | `qt/widgets/common/config_widgets.py:482, 638, 157, 547, 326` |
| Theme colours for painted widgets: `get_theme_manager().color("<token>")`; tokens `accent_primary, danger, text_primary, text_secondary, border_subtle, success, warning` exist in every theme | `qt/theme_manager.py:589, 773`; `resources/qt/themes/dark.json` |
| `core/charts.py` is a Qt-free `ChartSpec` builder for line/bar/scatter; its only renderer is the matplotlib window (`Report/chart_view.py:20-21` imports `matplotlib`), which the startup sweep deliberately avoids | `core/charts.py:66-129`, `nodes/__init__.py:156-159` |
| `scipy` and `hypothesis` are **not installed** | verified: `import hypothesis` -> `ModuleNotFoundError`; scipy absent from the venv |
| `core/audit/` does not exist yet; plan 02 owns its `__init__.py` (lazy re-exports) and expects plan 04 to create `core/audit/test_summary.py` | `src/trigger_designer/core/` listing, `02-audit-trail.md:950, 1500` |
| Plan 06 reads the Summary frame columns `test_name, criteria, status, message, population_rows, exception_rows, exception_rate, parameters` | `06-workpaper-export.md:1041-1043` |

---

## 3. Shared foundations

### 3.1 Family and registration

**Decision: add a real family `NodeTypes.AUDIT = "audit"`** (the brief permitted reusing a family). Reason: an auditor looks for "tests" as a group; the palette tab and Shift+A submenu come almost free (one enum member, one registry entry, one dict entry), and op ids read `audit.duplicates`.

Edits, in this order (all in existing files):

1. `core/node_configuration.py`
   * `NodeTypes`: append `AUDIT = "audit"` after `REPORT`.
   * New enum after `ReportNodes`:
     ```python
     class AuditNodes(IntEnum):
         DUPLICATES = auto()
         GAPS = auto()
         BENFORD = auto()
         SAMPLE = auto()
         RISK_FILTERS = auto()
     ```
   * `NODE_REGISTRIES`: add `NodeTypes.AUDIT: {},`. `_OPCODE_ENUMS`: add `NodeTypes.AUDIT: AuditNodes,`.
   * Add `"AuditNodes"` to `__all__` if the module lists names there (it does: `__all__` at the top of the file; add it next to the other `*Nodes` entries).
2. `qt/helpers/context_menu_mixin.py:40-46`: add `"Audit": NODE_REGISTRIES[NodeTypes.AUDIT],` as the last entry of `self.nodes_by_type`.
3. `qt/widgets/nodes/__init__.py`: import `AuditNodes`; append five dicts to `_LAZY_NODE_SPECS` (exact values in 3.11); add `"Audit._base"` and `"Audit.benford_chart"` to `_LAZY_HELPER_MODULES`.
4. Nothing else. `design_window.py:662` and `nodes_list.py:33` already iterate/convert generically.

Never reorder or rename `AuditNodes` members once released (brief 3.1: the member **name** is the persisted identity).

### 3.2 File layout

```text
src/trigger_designer/core/audit/
    __init__.py              # create EMPTY (docstring only) if plan 02 has not; never add imports to it
    common.py                # AuditConfigError, ParamsBase, AuditResult, expressions, summary builder
    test_summary.py          # TestSummary dataclass (interface for plans 02 and 06)
    duplicates.py            # DuplicatesParams, run_duplicates
    gaps.py                  # GapsParams, run_gaps
    benford.py               # BenfordParams, run_benford, chi2_sf, conformity, chart_data
    sampling.py              # SamplingParams, SplitMix64, run_sample
    risk_filters.py          # RiskParams, run_risk_filters
src/trigger_designer/qt/widgets/common/config_widgets.py   # + ColumnPicker (3.10); re-export in common/__init__.py
src/trigger_designer/qt/widgets/nodes/Audit/                 # namespace package (no __init__.py)
    _base.py                 # AuditContentMixin, AuditNode (3.8, 3.9)   [lazy helper]
    benford_chart.py         # BenfordChartWidget (QPainter)             [lazy helper]
    duplicates.py  gaps.py  benford.py  sample.py  risk_filters.py      # the five nodes
tests/support/audit_ledger.py
tests/unit/test_audit_{common,duplicates,gaps,benford,sampling,risk_filters,nodes}.py
tests/ui/test_audit_docks.py
tests/e2e/test_audit_workflows.py
tests/benchmarks/test_audit_perf.py
```

Rule (brief 10.1): everything under `core/audit/` imports only stdlib + `polars` + `numpy` (+ `orjson` is not needed; use `json`). It never imports `qtpy` or `trigger_designer.qt.*`; a unit test asserts this (7.1).

### 3.3 Op ids and migration notes

| Node | Enum member | Op id (persisted in `.tds` `"op"`) | Class | `node_title` | module stem |
|---|---|---|---|---|---|
| Duplicates | `AuditNodes.DUPLICATES` | `audit.duplicates` | `TriggerNode_Duplicates` | `Duplicates` | `Audit.duplicates` |
| Gaps | `AuditNodes.GAPS` | `audit.gaps` | `TriggerNode_Gaps` | `Gaps` | `Audit.gaps` |
| Benford | `AuditNodes.BENFORD` | `audit.benford` | `TriggerNode_Benford` | `Benford` | `Audit.benford` |
| Sample | `AuditNodes.SAMPLE` | `audit.sample` | `TriggerNode_Sample` | `Sample` | `Audit.sample` |
| Risk Filters | `AuditNodes.RISK_FILTERS` | `audit.risk_filters` | `TriggerNode_RiskFilters` | `Risk Filters` | `Audit.risk_filters` |

* No `V1_OPCODE_TO_OP` entry (brief 3.1: v1 files predate these nodes; the table is frozen).
* `WORKFLOW_SCHEMA_VERSION` stays `2` (brief 3.5: new nodes and new content keys need no bump).
* Content state is schema-driven with defaults, so a file saved by an older build of these nodes loads with defaults for any key added later. Never rename a content key; add keys only.
* An older application opening a file that contains `audit.*` ops shows `TriggerNode_Unknown` (brief 3.1); nothing to do.

### 3.4 Errors and codes

All configuration problems raise one exception type from the Qt-free core; the node turns it into a tooltip (live) or lets it fail the node (Run). Plan 03 translates by regex `^(TD-AUDIT-\d{3}): ` on the message and by `exc_type == "AuditConfigError"`.

```python
class AuditConfigError(ValueError):
    def __init__(self, code: str, message: str, *, field: str = "", columns: tuple[str, ...] = ()):
        super().__init__(f"{code}: {message}")      # str(e) always starts with the code
        self.code, self.message, self.field, self.columns = code, message, field, columns
```

| Code | Severity | Raised / shown when | Message template (plain language) |
|---|---|---|---|
| `TD-AUDIT-001` | error | a required column setting is empty | `Choose the {label} column.` |
| `TD-AUDIT-002` | error | a chosen column is not in the input | `Column '{col}' is not in the input data. Pick it again.` |
| `TD-AUDIT-003` | error | a chosen column holds nested data (List/Struct/Array/Object) | `Column '{col}' holds nested values and cannot be used for this test.` |
| `TD-AUDIT-004` | error | a number is out of range | `{label} must be {rule}.` (e.g. `Tolerance must be 0 or more.`) |
| `TD-AUDIT-005` | error | the input already has a column the node adds | `The input already has a column named '{name}', which this node adds. Rename it first.` |
| `TD-AUDIT-006` | error | a typed date is not `YYYY-MM-DD` | `'{text}' is not a date. Use YYYY-MM-DD.` |
| `TD-AUDIT-007` | error | `date_format` is not in `SUPPORTED_DATE_FORMATS` | `Date format '{fmt}' is not supported.` |
| `TD-AUDIT-008` | error | Risk Filters has no test switched on | `Switch on at least one risk test.` |
| `TD-AUDIT-009` | error | a typed number list is malformed or bands are inconsistent | `{label}: {detail}.` (e.g. `Strata sizes: expected 3 values, found 2.`) |
| `TD-AUDIT-010` | error | MUS / stratified sampling has no row with a readable amount | `No row has a readable amount in '{col}', so a value-based sample cannot be drawn.` |
| `TD-AUDIT-101` | warning (Summary `code`) | Benford tested too few rows | `Only {n:,} rows were tested; at least {min:,} are needed for a reliable result.` |
| `TD-AUDIT-102` | warning (Summary `code`) | values could not be read and were skipped | `{n:,} values could not be read as {kind} and were skipped.` |
| `TD-AUDIT-103` | warning (Selection log `note`) | requested sample size exceeds the population | `Requested {k:,} but only {n:,} rows exist; the whole population was selected.` |

Codes are never reused. Errors are `severity="error"` for plan 03; warnings travel in the Summary/log (`code` column) with status `warn`.

### 3.5 `core/audit/common.py` (create; exact content)

```python
"""Qt-free building blocks shared by the five audit tests."""
from __future__ import annotations

import copy
import dataclasses
import json
from dataclasses import dataclass, field
from typing import Any

import polars as pl

ROW = "__td_row"  # 0-based input position; internal columns all start with "__td_"
SUPPORTED_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%Y%m%d")
_NESTED = (pl.List, pl.Struct, pl.Array, pl.Object)


class AuditConfigError(ValueError):  # see 3.4 for the contract
    ...


@dataclass
class ParamsBase:
    @classmethod
    def from_dict(cls, data: dict | None):
        known = {f.name for f in dataclasses.fields(cls)}
        return cls(**{k: copy.deepcopy(v) for k, v in (data or {}).items() if k in known})

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


def default_of(f: dataclasses.Field) -> Any:
    return f.default_factory() if f.default_factory is not dataclasses.MISSING else f.default


def params_schema(cls) -> dict:
    """serialized_state_schema for SerializableContentMixin."""
    return {f.name: {"default": copy.deepcopy(default_of(f))} for f in dataclasses.fields(cls)}


def as_lazy(frame) -> pl.LazyFrame:
    return frame.lazy() if isinstance(frame, pl.DataFrame) else frame


def json_params(params: dict) -> str:
    return json.dumps(params, sort_keys=True, ensure_ascii=False, default=str)


def join_and(items: list[str]) -> str:
    items = [str(i) for i in items]
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


# ---- validation helpers (each raises AuditConfigError) ---------------------
def need(schema: dict, field_name: str, value: str, label: str, *, nested_ok: bool = False) -> None:
    if not value:
        raise AuditConfigError("TD-AUDIT-001", f"Choose the {label} column.", field=field_name)
    if value not in schema:
        raise AuditConfigError("TD-AUDIT-002", f"Column '{value}' is not in the input data. Pick it again.", field=field_name, columns=(value,))
    if not nested_ok and isinstance(schema[value], _NESTED):
        raise AuditConfigError("TD-AUDIT-003", f"Column '{value}' holds nested values and cannot be used for this test.", field=field_name, columns=(value,))


def need_many(schema: dict, field_name: str, values: list[str], label: str) -> None:
    if not values:
        raise AuditConfigError("TD-AUDIT-001", f"Choose the {label} column.", field=field_name)
    for v in values:
        need(schema, field_name, v, label)


def check_range(ok: bool, field_name: str, label: str, rule: str) -> None:
    if not ok:
        raise AuditConfigError("TD-AUDIT-004", f"{label} must be {rule}.", field=field_name)


def check_date_format(fmt: str) -> None:
    if fmt not in SUPPORTED_DATE_FORMATS:
        raise AuditConfigError("TD-AUDIT-007", f"Date format '{fmt}' is not supported.", field="date_format")


def check_reserved(schema: dict, names: list[str]) -> None:
    for n in names:
        if n in schema:
            raise AuditConfigError("TD-AUDIT-005", f"The input already has a column named '{n}', which this node adds. Rename it first.", field=n, columns=(n,))


# ---- value expressions ------------------------------------------------------
def amount_expr(name: str, dtype: pl.DataType) -> pl.Expr:
    """Float64 or null. Text is cleaned: ' (1,234.50) ' -> -1234.5, '$5' -> 5.0 (verified)."""
    col = pl.col(name)
    if dtype == pl.String:
        col = (col.str.strip_chars().str.replace_all(r"[,\s$£€]", "").str.replace(r"^\((.*)\)$", "-$1"))
    return col.cast(pl.Float64, strict=False)


def date_expr(name: str, dtype: pl.DataType, fmt: str) -> pl.Expr:
    """Date or null. Date as is; Datetime -> calendar date in its own time zone; text parsed
    with `fmt`, ignoring trailing time text ('2024-03-02 14:05:00' -> 2024-03-02, verified)."""
    col = pl.col(name)
    if dtype == pl.Date:
        return col
    if isinstance(dtype, pl.Datetime):
        return col.dt.date()
    txt = col if dtype == pl.String else col.cast(pl.String)
    return txt.str.strip_chars().str.to_date(fmt, strict=False, exact=False)


def key_expr(name: str, dtype: pl.DataType, trim: bool, ignore_case: bool) -> pl.Expr:
    c = pl.col(name) if dtype == pl.String else pl.col(name).cast(pl.String)
    if trim:
        c = c.str.strip_chars()
    if ignore_case:
        c = c.str.to_lowercase()
    return c


def unreadable(name: str, parsed: pl.Expr) -> pl.Expr:
    """True where the cell is present but could not be parsed."""
    return pl.col(name).is_not_null() & parsed.is_null()


@dataclass
class AuditResult:
    frames: tuple  # one entry per output socket, in socket order
    summary_index: int | None = None
    log_index: int | None = None
    extras: dict[str, Any] = field(default_factory=dict)  # eager facts for the dock (table, counts)

    def for_run(self) -> tuple:
        """Frames for generated code: the one-row summary/log is collected NOW, so a broken
        plan fails during Run (brief fact 2); big outputs stay lazy."""
        out = list(self.frames)
        for i in (self.summary_index, self.log_index):
            if i is not None and isinstance(out[i], pl.LazyFrame):
                out[i] = out[i].collect(engine="streaming")
        return tuple(out)
```

`pl.String` is what Polars 1.44.2 calls the text dtype (`pl.Utf8` is an alias); do not use `pl.Utf8`.

### 3.6 Summary frame and `TestSummary`

**Summary frame (every node that has a Summary socket; Sample's equivalent is the Selection log).** One row; columns in this exact order. Base columns (11) are identical for all nodes so plans 02/06 parse any of them the same way; node-specific extras follow.

| # | Column | Dtype | Meaning |
|---|---|---|---|
| 1 | `test_name` | String | `Duplicates`, `Gaps`, `Benford first digit`, `Benford first two digits`, `Risk filters` |
| 2 | `criteria` | String | one plain-language sentence built from the settings (section 4.x.3 gives each template) |
| 3 | `parameters` | String | `json_params(params.to_dict())` (sorted keys, UTF-8) |
| 4 | `status` | String | `pass` / `warn` / `fail` (never `error`; failures raise instead) |
| 5 | `code` | String, nullable | `TD-AUDIT-101/102` when a warning applies, else null |
| 6 | `message` | String | outcome sentence, e.g. `36 of 2,413 rows (1.5%) are in 17 duplicate groups.` |
| 7 | `population_rows` | Int64 | rows tested = all rows that arrived |
| 8 | `population_value` | Float64, nullable | gross value = sum of absolute amounts of the population; null when the node has no amount column |
| 9 | `exception_rows` | Int64 | rows flagged (definition per node) |
| 10 | `exception_value` | Float64, nullable | gross value of the flagged rows |
| 11 | `exception_rate` | Float64, nullable | `exception_rows / population_rows`, null when population is 0 |

**Why gross (absolute) value:** debits and credits cancel in a net sum, hiding exposure; gross is what a reviewer reads as "value at risk".

Builder in `common.py`:

```python
BASE_SUMMARY = ("test_name", "criteria", "parameters", "status", "code", "message",
                "population_rows", "population_value", "exception_rows", "exception_value", "exception_rate")

def summary_frame(agg: pl.LazyFrame, *, test_name: str, criteria: str, parameters: dict,
                  status: pl.Expr, message: pl.Expr, code: pl.Expr | None = None,
                  extras: tuple[str, ...] = ()) -> pl.LazyFrame:
    """`agg` is a one-row frame with population_rows, population_value, exception_rows,
    exception_value and every column named in `extras`. status/message/code are expressions on it."""
    return agg.select(
        pl.lit(test_name).alias("test_name"),
        pl.lit(criteria).alias("criteria"),
        pl.lit(json_params(parameters)).alias("parameters"),
        status.alias("status"),
        (code if code is not None else pl.lit(None, dtype=pl.String)).alias("code"),
        message.alias("message"),
        pl.col("population_rows"), pl.col("population_value"),
        pl.col("exception_rows"), pl.col("exception_value"),
        pl.when(pl.col("population_rows") > 0)
          .then(pl.col("exception_rows") / pl.col("population_rows")).alias("exception_rate"),
        *[pl.col(c) for c in extras],
    )

def warn_unreadable(status: pl.Expr, message: pl.Expr, code: pl.Expr, unreadable_col: str, kind: str):
    """Downgrade pass -> warn and append the TD-AUDIT-102 note when values were skipped.
    Returns (status, message, code) expressions; `code` is never overwritten when already set."""
    bad = pl.col(unreadable_col)
    return (
        pl.when((bad > 0) & (status == "pass")).then(pl.lit("warn")).otherwise(status),
        message + pl.when(bad > 0)
        .then(pl.format(" {} values could not be read as " + kind + " and were skipped.", bad))
        .otherwise(pl.lit("")),
        pl.when(code.is_not_null()).then(code)
        .when(bad > 0).then(pl.lit("TD-AUDIT-102")).otherwise(pl.lit(None, dtype=pl.String)),
    )
```

(`pl.format("{} of {}", ...)` with integer expressions was verified. Number formatting with thousands separators is done in Python where the numbers are known; expression-built messages use plain integers, so the quoted examples in this plan use plain integers in expression-built messages: `36 of 2413 rows ...`. Tests assert the plain-integer form given in each node section.)

**`TestSummary`** - create `core/audit/test_summary.py` (honours brief 11.3 exactly, adds only defaulted fields):

```python
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, ClassVar
import polars as pl


@dataclass(frozen=True)
class TestSummary:
    __test__: ClassVar[bool] = False  # keep pytest from collecting this class
    # --- brief 11.3 fields (names and meaning frozen) ---
    test_id: str = ""                 # "<op>#<node_id>", e.g. "audit.duplicates#139626"
    test_name: str = ""
    node_id: int | None = None
    status: str = "pass"              # "pass" | "warn" | "fail" | "error"
    population_rows: int | None = None
    exception_rows: int | None = None
    exception_rate: float | None = None
    criteria: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)
    message: str = ""
    exceptions_var: str | None = None  # generated-code variable holding exception rows
    # --- additions (defaulted; non-breaking) ---
    population_value: float | None = None
    exception_value: float | None = None
    code: str | None = None            # TD-AUDIT-101/102/103 when a warning applies
    details: dict[str, Any] = field(default_factory=dict)  # node extras (groups, mad, seed, selection_log ...)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TestSummary":
        known = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in data.items() if k in known})

    @classmethod
    def from_summary_frame(cls, frame: pl.DataFrame, *, op: str, node_id: int | None,
                           exceptions_var: str | None = None) -> "TestSummary":
        row = frame.row(0, named=True)
        import json
        base = set(BASE_COLUMNS)
        return cls(
            test_id=f"{op}#{node_id}", test_name=row["test_name"], node_id=node_id, status=row["status"],
            population_rows=row["population_rows"], exception_rows=row["exception_rows"],
            exception_rate=row["exception_rate"], criteria=row["criteria"],
            parameters=json.loads(row["parameters"] or "{}"), message=row["message"],
            exceptions_var=exceptions_var, population_value=row["population_value"],
            exception_value=row["exception_value"], code=row["code"],
            details={k: v for k, v in row.items() if k not in base},
        )

BASE_COLUMNS = ("test_name", "criteria", "parameters", "status", "code", "message", "population_rows",
                "population_value", "exception_rows", "exception_value", "exception_rate")
```

How a node exposes it (decision): `content.test_summary: TestSummary | None`, set (a) in `after_execution(variables)` from the collected Summary variable (runs before `nodeFinished`, so plan 02's recorder sees it), (b) in live evaluation for Benford and Sample (their summary is computed eagerly anyway), (c) when the user presses the **Count** icon button in the dock (Duplicates, Gaps, Risk Filters; collects the one-row summary on the GUI thread with the streaming engine). Reason for (c): live evaluation must not freeze the UI on a 1M-row file just to draw a label.

### 3.7 `AuditResult`, run functions and generated code

Every test has one pure function `run_<name>(frame, params) -> AuditResult` in `core/audit/<name>.py`. It validates (raising `AuditConfigError`), builds lazy frames, and never touches Qt. **Both** paths call it: live `processInputs` uses `result.frames`; `get_code()` emits a call to it. Reason: a single implementation makes "live and Run agree" true by construction, and unit tests need no widgets.

Generated code (exact template; `<id>` = `self.id`):

```python
import polars as pl
from trigger_designer.core.audit.duplicates import DuplicatesParams, run_duplicates
_ap_<id> = DuplicatesParams.from_dict({'key_columns': ['vendor', 'invoice_no'], 'mode': 'exact', ...})
var_dup_<id>, var_uniq_<id>, var_dupsum_<id> = run_duplicates(<incoming_variable>, _ap_<id>).for_run()
del _ap_<id>
```

* The dict literal is `repr(self.params_dict())`: it holds only str/int/float/bool/None/list/dict, so `repr` is a safe Python literal (no quote-injection; brief 10.1 "escape with `!r`").
* The exported `check_output.py` needs the package importable: the exported file is written under the app data dir (`last_run/check_output.py`, plan 09 F-I) and its header (`check_output_header`, F-I) puts the source root on `sys.path`. Document this in the node docstring.
* Unwired (`incoming_variable == ""`): define every output as `pl.DataFrame()` and return (brief 3.4). Wired but misconfigured: the call raises `AuditConfigError` and the node fails loudly. Reason: an audit test that silently produced nothing would read as "no exceptions found" - false assurance.
* `get_code` is pure and idempotent; it only formats strings.

Shared helper (method of `AuditContentMixin`, 3.8): `audit_code(module, run_fn, params_cls, out_vars)`.

### 3.8 Content mixin - `qt/widgets/nodes/Audit/_base.py`

One mixin holds the repeated plumbing so each node file only declares its fields, its dock sections and its `build_outputs`.

```python
class AuditContentMixin(SerializableContentMixin):
    PARAMS: type            # ParamsBase subclass
    OP: str                 # "audit.duplicates"
    TEST_NAME: str
    # serialized_state_schema = params_schema(PARAMS) is assigned in each concrete class body

    # ---- model --------------------------------------------------------
    def init_audit_state(self) -> None:
        for f in dataclasses.fields(self.PARAMS):
            setattr(self, f.name, copy.deepcopy(default_of(f)))
        self.incoming_variable = ""
        self.incom_data = None            # LazyFrame
        self.test_summary = None          # TestSummary | None
        self.last_result = None           # AuditResult of the last live evaluation
        self._bindings: dict[str, tuple] = {}   # field -> (widget, kind, opts)
        self._timers: dict[str, QTimer] = {}

    def params(self):                      # dataclass snapshot of the model
        return self.PARAMS(**{f.name: copy.deepcopy(getattr(self, f.name)) for f in dataclasses.fields(self.PARAMS)})

    def params_dict(self) -> dict:
        return self.params().to_dict()

    def schema(self) -> dict:              # {column: dtype}, lazy-safe
        return frame_schema(self.incom_data)

    # ---- the one place a user edit enters the model (brief 6.3 pattern) ----
    def set_setting(self, name: str, value, text: str, *, merge_key: str | None = None) -> bool:
        if is_syncing(self) or self.history.is_restoring_history:      # guard
            return False
        old, new = copy.deepcopy(getattr(self, name)), copy.deepcopy(value)
        if new == old:                                                  # real diff only
            return False
        setattr(self, name, new)                                        # 1. model first
        self._apply_visibility()
        self.refresh_dock_context()
        self.evaluate.emit()                                            # 2. re-evaluate (merged pushes skip redo)
        self.push_property_change((name,), old, new, text, merge_key=merge_key)   # 3. one undo step
        return True

    # ---- widget binding -------------------------------------------------
    def bind(self, name: str, widget, kind: str, text: str, *, burst: bool = False, **opts) -> None:
        """kind in picker|check|spin|optint|dspin|segment|combo|checklist|digitlist|text|lines|numlist|sizelist.
        burst=True gives the control its own merge_key (spins, text) so typing/spinning is one undo step."""
        self._bindings[name] = (widget, kind, opts)
        merge = f"{self.OP}-{name}" if burst else None
        debounced = kind in ("lines", "numlist", "sizelist", "text")

        def commit() -> None:
            try:
                value = self._read_widget(widget, kind, opts)
            except ValueError:            # half-typed number list: keep the old value
                return
            self.set_setting(name, value, text, merge_key=merge)

        def on_change(*_a) -> None:
            if not debounced:
                commit()
                return
            timer = self._timers.get(name)
            if timer is None:
                timer = QTimer(widget)
                timer.setSingleShot(True)
                timer.setInterval(DEFAULT_DEBOUNCE_MS)         # 300 ms, qt/undo/binding.py:54
                timer.timeout.connect(commit)
                self._timers[name] = timer
            timer.start()

        _signal_of(widget, kind).connect(on_change)

    def _read_widget(self, w, kind, opts):
        return {
            "picker": lambda: w.value(), "check": lambda: w.isChecked(),
            "spin": lambda: w.value(), "dspin": lambda: float(w.value()),
            "optint": lambda: None if w.value() == w.minimum() else int(w.value()),
            "segment": lambda: opts["options"][w.value()],           # label -> stored key
            "combo": lambda: w.currentData(), "checklist": lambda: list(w.checked()), "digitlist": lambda: [int(x) for x in w.checked()],
            "text": lambda: w.text().strip(),
            "lines": lambda: [s.strip() for s in w.toPlainText().splitlines() if s.strip()],
            "numlist": lambda: parse_number_list(w.text()),
            "sizelist": lambda: parse_size_list(w.text()),
        }[kind]()

    def _write_widget(self, w, kind, opts, value) -> None:
        w.blockSignals(True)
        try:
            {"picker": lambda: w.set_value(value or ""), "check": lambda: w.setChecked(bool(value)),
             "spin": lambda: w.setValue(int(value)), "dspin": lambda: w.setValue(float(value)),
             "optint": lambda: w.setValue(w.minimum() if value is None else int(value)),
             "segment": lambda: w.set_value(opts["labels"][value]),
             "combo": lambda: w.setCurrentIndex(max(0, w.findData(value))),
             "checklist": lambda: w.setChecked(list(value)), "digitlist": lambda: w.setChecked([str(v) for v in value]),
             "text": lambda: w.setText(value),
             "lines": lambda: w.setPlainText("\n".join(value)),
             "numlist": lambda: w.setText(", ".join(f"{x:g}" for x in value)),
             "sizelist": lambda: w.setText(", ".join("all" if x < 0 else str(x) for x in value)),
             }[kind]()
        finally:
            w.blockSignals(False)

    # ---- undo projection (runs inside syncing(); brief 6.3) ---------------
    def _sync_widgets_from_model(self) -> None:
        for name, (w, kind, opts) in list(self._bindings.items()):
            try:
                if self._read_widget(w, kind, opts) != getattr(self, name):
                    self._write_widget(w, kind, opts, getattr(self, name))
            except (RuntimeError, ValueError):     # widget deleted by a dock rebuild / unreadable text
                self._bindings.pop(name, None)
        self._apply_visibility()

    def _apply_visibility(self) -> None:           # override: show/hide option rows by mode
        pass

    # ---- run hooks ----------------------------------------------------------
    def after_execution(self, variables: dict) -> None:          # exec worker thread; pure Python only
        frame = variables.get(getattr(self, "summary_variable_name", ""))
        if isinstance(frame, pl.LazyFrame):
            frame = frame.collect()
        if isinstance(frame, pl.DataFrame) and frame.height == 1:
            self.test_summary = TestSummary.from_summary_frame(
                frame, op=self.OP, node_id=self.node.id, exceptions_var=self.exceptions_var_name())

    def exceptions_var_name(self) -> str | None:                # override per node (variable of the exception frame)
        return None

    def audit_code(self, module: str, run_fn: str, params_cls: str, out_vars: list[str]) -> str:
        if not self.incoming_variable:
            return "import polars as pl\n" + "".join(f"{v} = pl.DataFrame()\n" for v in out_vars)
        uid = self.id
        return (
            "import polars as pl\n"
            f"from trigger_designer.core.audit.{module} import {params_cls}, {run_fn}\n"
            f"_ap_{uid} = {params_cls}.from_dict({self.params_dict()!r})\n"
            f"{', '.join(out_vars)} = {run_fn}({self.incoming_variable}, _ap_{uid}).for_run()\n"
            f"del _ap_{uid}\n"
        )

    def serialize(self):
        return self.serialize_content_state(super().serialize())

    def deserialize(self, data, hashmap={}):
        res = super().deserialize(data, hashmap)
        try:
            self.deserialize_content_state(data)
            return True and res
        except Exception as exc:  # noqa: BLE001
            dumpException(exc)
        return res
```

Module-level helpers in the same file: `_signal_of(widget, kind)` (`picker/segment/checklist/digitlist -> widget.changed`, `check -> toggled`, `spin/optint/dspin -> valueChanged`, `combo -> currentIndexChanged`, `lines/text/numlist/sizelist -> textChanged`), `parse_number_list(text) -> list[float]` and `parse_size_list(text) -> list[int]` (empty text -> `[]`; tokens split on `,`; `parse_size_list` maps `all`/`ALL` -> `-1`; any bad token raises `ValueError`; define both in `core/audit/common.py` so they are testable without Qt and import them into `_base.py`).

Every concrete content class is declared exactly like the brief skeleton plus the mixin:

```python
class DuplicatesContent(QDMNodeIconContentWidget, TriggerChangeHandler, AuditContentMixin):
    evaluate = Signal()                       # must be on the concrete QObject class
    PARAMS, OP, TEST_NAME = DuplicatesParams, "audit.duplicates", "Duplicates"
    serialized_state_schema = params_schema(DuplicatesParams)
    def __init__(self, node, parent=None):
        super().__init__(node, parent)
        TriggerChangeHandler.__init__(self, self.node.scene, self.node)
        self.history = self.node.scene.history
        self.init_audit_state()
        self.duplicates_var = f"var_dup_{self.id}"; self.unique_var = f"var_uniq_{self.id}"
        self.summary_variable_name = f"var_dupsum_{self.id}"
    # node property pair, initUI(icon) exactly as in brief 3.8
```

### 3.9 Node base - `Audit/_base.py`

```python
class AuditNode(TriggerNode):
    """Single-input audit test. Subclasses set icon/node_code/node_title/node_type and sockets."""

    def processInputs(self, input_values):
        input_node = self.getInput(0)
        entry = input_values[0][self.getSocketValue(input_node.outputs, self)]
        if not entry or entry.get("data") is None:
            self.markDirty(True); self.markInvalid(True)
            self._set_node_tooltip("Input has no data")
            return None
        c = self.content
        c.incom_data = as_lazy(entry["data"])          # set BEFORE validating so the dock still builds
        c.incoming_variable = entry["variable_name"]
        try:
            result = c.build_result()                  # core run_*(c.incom_data, c.params())
        except AuditConfigError as exc:
            self.markDirty(True); self.markInvalid(True)
            self._set_node_tooltip(str(exc))           # "TD-AUDIT-001: Choose the key column."
            return None
        c.last_result = result
        c.on_result(result)                            # node hook (sets test_summary for Benford/Sample)
        self.param = [{"data": f, "variable_name": v} for f, v in zip(result.frames, c.output_variable_names())]
        return self.param

    def get_code(self) -> str:
        return self.content.get_code()
```

Subclass contract on the content: `build_result()`, `output_variable_names() -> list[str]` (socket order), `get_code()`, `create_layout()`, optional `on_result()`. The three socket types in `__init__`: data outputs `3`, summary/log `1` (colour only).

### 3.10 Shared widget `ColumnPicker` (add to `config_widgets.py`, export in `common/__init__.py`)

AGENTS.md: reuse shared widgets, no per-node rewrites. Seven dock rows need "pick one column of the input"; none of the shared widgets does that, so one shared widget is added (not five private copies):

```python
class ColumnPicker(NoWheelComboBox):
    """Single-column chooser. First entry is '(none)' (value ''). Emits changed(str)."""
    changed = Signal(str)
    NONE_LABEL = "(none)"

    def __init__(self, columns=(), current="", parent=None):
        super().__init__(parent)
        self.setObjectName("ColumnPicker")
        self.setMinimumHeight(CONTROL_H)
        self.set_columns(columns, current)
        self.currentIndexChanged.connect(lambda _i: self.changed.emit(self.value()))

    def set_columns(self, columns, current=""):
        self.blockSignals(True)
        self.clear()
        self.addItem(self.NONE_LABEL, "")
        for c in columns:
            self.addItem(str(c), str(c))
        if current and self.findData(current) < 0:       # stale column: keep it visible so the error says why
            self.addItem(current, current)
        self.setCurrentIndex(max(0, self.findData(current)))
        self.blockSignals(False)

    def value(self) -> str:
        return self.currentData() or ""

    def set_value(self, value: str) -> None:
        self.blockSignals(True)
        if value and self.findData(value) < 0:
            self.addItem(value, value)
        self.setCurrentIndex(max(0, self.findData(value)))
        self.blockSignals(False)
```

`ColumnPicker` is a single control that owns its signal, so it is bound by `bind(..., "picker", ...)`; its parent section is marked `_undo_composite`, so the sweep skips it. Decision: pickers list **all** columns, no dtype filter. Reason: File Input reads CSV as all-`String` (brief 7.1), so a "numeric only" filter would hide every amount column.

QSS: the `ColumnPicker` objectName reuses the combo styling already in `base.qss` (`QComboBox`); add no new rule. Do not call `setStyleSheet`.

### 3.11 Icons

Reuse existing ids (brief 3.6: "Until a dedicated icon exists, reuse"). Title and icon in the spec dict must equal the class attributes (`test_node_titles.py` rule).

| Node | `icon` id | Spec dict (append to `_LAZY_NODE_SPECS`) |
|---|---|---|
| Duplicates | `node_unique` | `{"module_path": "Audit.duplicates", "node_code": AuditNodes.DUPLICATES, "node_type": NodeTypes.AUDIT, "node_title": "Duplicates", "icon": "node_unique"}` |
| Gaps | `node_count` | `{"module_path": "Audit.gaps", "node_code": AuditNodes.GAPS, "node_type": NodeTypes.AUDIT, "node_title": "Gaps", "icon": "node_count"}` |
| Benford | `node_graph` | `{"module_path": "Audit.benford", "node_code": AuditNodes.BENFORD, "node_type": NodeTypes.AUDIT, "node_title": "Benford", "icon": "node_graph"}` |
| Sample | `node_split` | `{"module_path": "Audit.sample", "node_code": AuditNodes.SAMPLE, "node_type": NodeTypes.AUDIT, "node_title": "Sample", "icon": "node_split"}` |
| Risk Filters | `node_filter` | `{"module_path": "Audit.risk_filters", "node_code": AuditNodes.RISK_FILTERS, "node_type": NodeTypes.AUDIT, "node_title": "Risk Filters", "icon": "node_filter"}` |

The dock "Count exceptions" button uses `IconButton.themed("Count exceptions now", rsm_icon=self.node.rsm.get("icon_refresh"), qss_fallback=":/qss_icons/dark/rc/arrow_down.png")` (`icon_refresh` exists in `resources.json:131`; `arrow_down.png` is the fallback glyph the Select/Union docks already use at `select.py:196`).

### 3.12 Execution model per node (streaming vs collect; memory)

| Node | Live `processInputs` | Generated code at Run | Streaming-safe? | Memory while running (N = rows) |
|---|---|---|---|---|
| Duplicates | builds lazy frames only; **no collect** | summary collected with `engine="streaming"` (falls back to in-memory for window/sort ops - verified to run) ; Duplicates/Unique stay lazy | No: `over(keys)` / sort hold the key columns of all N rows | ~ (key bytes + 8) x N; 1M rows x 3 text keys measured 0.27 s exact, 0.37 s near |
| Gaps | lazy frames; **no collect** | summary collected | Partly: distinct-value `group_by` streams; out-of-order needs (series, number, row) of all N rows | ~ 24 bytes x N for out-of-order; ~ 16 bytes x distinct numbers otherwise; 1M rows 0.47 s |
| Benford | **collects** one streaming `group_by` over the amount column only (<= 90 groups) and the totals | same function; table/summary eager, drill-down lazy | Yes (single pass, one projected column) | one column; 1M rows 0.04 s |
| Sample | **collects** the sort key + row index (+ amount for MUS/stratified) when population <= 200,000 rows, otherwise returns empty frames and a tooltip; Run always draws | collects key + row index (+ amount); sample / not-sampled stay lazy joins | No (needs a total order) | unique key: ~ (key bytes + 4) x N; no key or tied key: the **whole frame** is collected for the tie-break sort (documented in the dock tooltip) |
| Risk Filters | lazy frames; **no collect** | summary collected | Yes (row-wise expressions + one aggregate) | constant besides the engine's chunking |

Every output frame that is not a one-row summary stays a `LazyFrame`; each downstream materialisation re-executes the plan (no `cache()`), exactly like every other node in this repo.

---

## 4. The five nodes

Conventions used in every subsection:

* The core module is `core/audit/<name>.py` (Qt-free). The Qt module is `qt/widgets/nodes/Audit/<name>.py` and contains only the two classes of the brief's recipe (`<X>Content`, `TriggerNode_<X>`), registration, the dock builder and `get_code`. Content class declaration, `__init__`, `node` property pair, `initUI`, `serialize/deserialize` are exactly as in 3.8 and brief 3.8; they are not repeated.
* Serialization key = dataclass field name; default = dataclass default (`params_schema`). Dict/list defaults are deep-copied by the state mixin.
* Dock rule for every node (brief 5.4): `if self.incom_data is None: dock_layout.addWidget(EmptyStateLabel()); return`; then `ConfigSection`s; `dock_layout.addStretch()` last; every section is marked `section._undo_composite = True` (Union pattern) because every control commits through `bind()`/`set_setting`; do not call `recursively_find_widgets`. Call `self._bindings.clear()` first, `self._apply_visibility()` last.
* History texts follow `"Noun Verbed"`. `burst=True` controls (spins, text, number lists) pass a per-field `merge_key` (`audit.duplicates-tolerance`); discrete controls (checks, combos, pickers, segmented, checklists) never merge.
* "Count" button (Duplicates, Gaps, Risk Filters): `IconButton.themed("Count exceptions now", ...)` in a section titled "Result" next to a word-wrapped `QLabel` (`self.result_label`). Click -> `summary = self.last_result.for_run()[summary_index]` (GUI thread) -> `self.test_summary = TestSummary.from_summary_frame(summary, op=self.OP, node_id=self.node.id, exceptions_var=self.exceptions_var_name())` -> label text = `test_summary.message`. Before the first count the label reads `Not counted yet. Press the button, or Run the workflow.` The button is not a setting: no undo entry.

---

### 4.1 Duplicates

**Purpose.** Find rows that repeat. *Exact*: the chosen key columns are equal. *Near*: key columns are equal **and** (if an amount column is chosen) amounts differ by at most a tolerance **and** (if a date column is chosen) dates differ by at most N days. Outputs every row that belongs to a group with 2+ rows (with the group id and size), every other row, and a Summary.

**Settings** (`DuplicatesParams`; every field is a serialized key):

```python
@dataclass
class DuplicatesParams(ParamsBase):
    key_columns: list[str] = field(default_factory=list)
    mode: str = "exact"               # "exact" | "near"
    trim_text: bool = True            # reason: trailing spaces are the commonest false negative
    ignore_case: bool = False         # reason: case can be meaningful in IDs
    amount_column: str = ""           # near
    tolerance_kind: str = "absolute"  # "absolute" | "percent" (percent of the larger |amount| of the two)
    tolerance: float = 0.0
    date_column: str = ""             # near
    date_format: str = "%Y-%m-%d"     # one of SUPPORTED_DATE_FORMATS; ignored when the column is Date/Datetime
    window_days: int = 0
    value_column: str = ""            # optional Summary value; near mode falls back to amount_column
```

**Algorithm** (verified; `run_duplicates(frame, p) -> AuditResult(frames=(Duplicates, Unique, Summary), summary_index=2)`):

1. `validate` (table below), `originals = schema.names()`, `lf = lf.with_row_index("__td_row")`.
2. Key columns become `__td_k0..` via `key_expr` (String; trimmed; lower-cased when `ignore_case`). A row is **eligible** only if every key is non-null (a blank invoice number is not evidence of duplication) and, in near mode, the amount (`amount_expr`, not NaN) and/or date (`date_expr`) it needs is readable. `__td_bad` = any needed cell that is present but unreadable (`unreadable()`), counted in `unparseable_rows`.
3. **Exact:** `cnt = when(eligible).then(pl.len().over(keys)).otherwise(1)`, `first = when(eligible).then(row.min().over(keys)).otherwise(row)`.
4. **Near** (decision: hierarchical 1-D clustering, not pairwise graph components; reason: it is O(N log N) and cannot blow up quadratically on a coarse key, and every pair that satisfies *both* thresholds is guaranteed to land in the same group. Consequence, documented in the dock tooltip: a group can also contain rows linked only through a chain of in-tolerance neighbours.) On the eligible rows:

   ```python
   part = lf.filter(pl.col("__td_elig")).sort(kc + (["__td_dt"] if has_d else []) + [ROW])
   part = part.with_columns(pl.struct(kc).rle_id().alias("__td_p"))          # run id of equal key tuples
   cluster = pl.col("__td_p")
   if has_d:   # new date cluster when the key run changes or the day gap to the previous row exceeds window_days
       gap = pl.col("__td_dt").diff().dt.total_days()
       new_d = (pl.col("__td_p") != pl.col("__td_p").shift(1)).fill_null(True) | (gap > p.window_days).fill_null(True)
       part = part.with_columns(new_d.cum_sum().alias("__td_c1")); cluster = pl.col("__td_c1")
   if has_a:   # inside each cluster, sort by amount; new group when the amount gap to the previous row exceeds the tolerance
       part = part.sort(["__td_p"] + (["__td_c1"] if has_d else []) + ["__td_amt", ROW])
       prev = pl.col("__td_amt").shift(1)
       limit = (pl.max_horizontal(pl.col("__td_amt").abs(), prev.abs()) * (p.tolerance / 100.0) + 1e-9
                if p.tolerance_kind == "percent" else pl.lit(p.tolerance + 1e-9))      # 1e-9 absorbs float noise
       new_a = (cluster != cluster.shift(1)).fill_null(True) | ((pl.col("__td_amt") - prev) > limit).fill_null(True)
       part = part.with_columns(new_a.cum_sum().alias("__td_gid"))
   else:
       part = part.with_columns(cluster.alias("__td_gid"))
   lf = lf.join(part.select(ROW, "__td_gid"), on=ROW, how="left")             # ineligible rows get null
   cnt = when(gid.is_not_null()).then(pl.len().over("__td_gid")).otherwise(1); first = ... row.min().over("__td_gid")
   ```
5. `flagged = cnt > 1`. **Duplicates** = flagged rows with `dup_group_id = first.rank("dense")` (1 = group whose first row appears earliest in the input; cast Int64) and `dup_count = cnt` (Int64), sorted by `(dup_group_id, row)`, columns `originals + ["dup_group_id", "dup_count"]`. **Unique** = unflagged rows in input order, `originals` only (decision: "Unique" means "not in any group"; first-of-group retention is the existing Unique node's job).
6. **Summary** aggregate: `population_rows = len`, `population_value = sum(|value|)` (null if no value column), `exception_rows = flagged.sum()`, `exception_value = sum(|value| where flagged)`, `groups = first.filter(flagged).n_unique()`, `skipped_rows = (~eligible).sum()`, `unparseable_rows = __td_bad.sum()`; status `fail` if `exception_rows > 0` else `pass`; message `"{exception_rows} of {population_rows} rows are in {groups} duplicate groups."`; `warn_unreadable(..., "numbers or dates")` appends the TD-AUDIT-102 note.

**Outputs.**

| Socket | Name (`output_text`) | Variable attr | Schema |
|---|---|---|---|
| 0 | Duplicates (`D`) | `duplicates_var = var_dup_<id>` | input columns + `dup_group_id` Int64, `dup_count` Int64 |
| 1 | Unique (`U`) | `unique_var = var_uniq_<id>` | input columns unchanged |
| 2 | Summary (`S`) | `summary_variable_name = var_dupsum_<id>` | base 11 + `groups, skipped_rows, unparseable_rows` (Int64) |

`exceptions_var_name()` returns `self.duplicates_var`. `test_name` = `Duplicates`.

**Criteria sentences.** Exact: `Rows with the same vendor and invoice_no are duplicates (spaces around text trimmed, case-sensitive).` (columns joined `a, b and c`; second clause `upper/lower case ignored` when `ignore_case`; the trim clause is dropped when `trim_text` is off). Near: `Rows with the same vendor and invoice_no whose amount differs by at most 0.50 and whose posting_date differs by at most 3 days are near-duplicates (spaces around text trimmed, case-sensitive).` (absolute tolerance printed `f"{t:,.2f}"`, percent `f"{t:g}%"`; only the clauses whose column is chosen appear).

**Dock (top to bottom).**

| Section | Control (kind) | Field | History text |
|---|---|---|---|
| "Match on" | `TextButton("All")`, `TextButton("None")` (objectName `BulkButton`, call `checklist.set_all_checked(...)`) + `ColumnChecklist` (`checklist`) | `key_columns` | `Duplicate Keys Changed` |
| "Match on" (same section) | `QCheckBox("Trim spaces")` (`check`), `QCheckBox("Ignore case")` (`check`) | `trim_text`, `ignore_case` | `Duplicate Trim Changed`, `Duplicate Case Changed` |
| "Match type" | `SegmentedControl(["Exact", "Near"])` (`segment`, options `{"Exact": "exact", "Near": "near"}`) | `mode` | `Duplicate Match Type Changed` |
| "Near match" (hidden when `mode == "exact"`) | `FormRow("Amount", ColumnPicker)` (`picker`); `FormRow("Tolerance", QDoubleSpinBox 0..1e12, 2 decimals)` (`dspin`, burst) + `SegmentedControl(["Amount", "Percent"])` (`segment`); `FormRow("Date", ColumnPicker)`; `FormRow("Window", QSpinBox 0..3660, suffix " days")` (`spin`, burst); `FormRow("Date format", combo)` (`combo`, items = `SUPPORTED_DATE_FORMATS`) | `amount_column`, `tolerance`, `tolerance_kind`, `date_column`, `window_days`, `date_format` | `Duplicate Amount Changed`, `Duplicate Tolerance Changed`, `Duplicate Tolerance Kind Changed`, `Duplicate Date Column Changed`, `Duplicate Window Changed`, `Duplicate Date Format Changed` |
| "Value" | `FormRow("Value", ColumnPicker)` | `value_column` | `Duplicate Value Column Changed` |
| "Result" | Count button + label (see top of section 4) | - | - |

`_apply_visibility()`: `near_section.setVisible(self.mode == "near")`. Tooltip on the Match type control: `Near matching also groups rows linked through a chain of close neighbours.` `dock_context()` -> `([(f"{len(self.key_columns)} key columns", "accent"), (self.mode, "muted")], "")`.

**Validation (`validate`, in this order; first failure raises).**

| Check | Code | Message field |
|---|---|---|
| `key_columns` empty | 001 | `Choose the key column.` |
| any chosen column missing from input / nested | 002 / 003 | per 3.4 |
| `mode == "near"` and neither amount nor date chosen | 001 | `Choose the amount column or the date column for near matching.` |
| `tolerance < 0` | 004 | `Tolerance must be 0 or more.` |
| `window_days < 0` | 004 | `Window must be 0 days or more.` |
| `date_format` unsupported | 007 | per 3.4 |
| input has `dup_group_id`, `dup_count` or any `__td_*` column | 005 | per 3.4 |

**Undo.** All fields via `set_setting` (no `rebuild`). `key_columns` pushes a **copy** of the list (`list(checked)`), so old/new are distinct objects.

**Verified reference (hand-checkable).** Input (rows 0-9): `vendor = [A,A,A,B,B,A,null,null,"a ",C]`, `inv = [1,1,1,7,7,2,9,9,1,5]`, `amt = ["100.00","100.00","100.40","50","50.00","(25)","5","5","100","oops"]`, `date = [2024-01-01, 01-02, 01-20, 02-01, 02-01, 03-01, 03-01, 03-01, 01-01, 01-01]`; keys `[vendor, inv]`:

| Settings | `dup_count` of Duplicates rows | `dup_group_id` | Unique rows | Summary |
|---|---|---|---|---|
| exact | `[3,3,3,2,2]` (rows 0-4) | `[1,1,1,2,2]` | 5 (rows 5-9) | population 10, exception 5, groups 2, skipped 2 (null vendors), status `fail`, message `5 of 10 rows are in 2 duplicate groups.` |
| exact + `ignore_case` | `[4,4,4,4,2,2]` (rows 0,1,2,8,3,4) | `[1,1,1,1,2,2]` | 4 | exception 6, groups 2 |
| near, amount `absolute 0.5`, date `window 3` | `[2,2,2,2]` (rows 0,1,3,4) | `[1,1,2,2]` | 6 | exception 4, groups 2, skipped 3, unparseable 1 (`oops`), status `fail`, code `TD-AUDIT-102`, message ends ` 1 values could not be read as numbers or dates and were skipped.` |
| near, amount `percent 1`, no date | `[3,3,3,2,2]` | `[1,1,1,2,2]` | 5 | population_value `535.4`, exception_value `400.4` |

---

### 4.2 Gaps

**Purpose.** Find numbers missing from a document sequence, optionally per series (ledger), report repeated and out-of-order numbers, or find calendar days with no entry.

**Settings** (`GapsParams`):

```python
@dataclass
class GapsParams(ParamsBase):
    sequence_column: str = ""
    mode: str = "prefixed"            # "number" | "prefixed" | "date"
    group_columns: list[str] = field(default_factory=list)
    report_duplicates: bool = True    # number/prefixed
    report_out_of_order: bool = True  # number/prefixed
    range_start: int | None = None    # expected first number; None = lowest seen (a missing first document is only visible if set)
    range_end: int | None = None
    date_format: str = "%Y-%m-%d"     # date mode
    min_gap_days: int = 1             # date mode: ignore gaps shorter than this
    business_days_only: bool = False  # date mode: Saturday/Sunday are not expected
```

**Parsing (decisions).** `prefixed`: the number is the **trailing run of digits**, the prefix is everything before it: `JE-000123` -> prefix `JE-`, number 123, width 6; regexes `^(.*?)\d+$` (prefix) and `^.*?(\d+)$` (digits), applied to the stripped `String` cast of the column; a value with no trailing digits is unreadable. Series = (group columns, prefix): `JE-` and `je-` are different series (case-sensitive; reason: two prefixes are two numbering schemes). `number`: whole text must match `^\+?(\d+)(?:\.0+)?$` (so `"000123"`, `"123"` and `123.0` from a Float column all read as 123); prefix `""`. Width for output = the largest digit-string length seen in the series (zero padding is restored with `str.zfill`). Suffixes (`INV-12-A`) are not supported (unreadable). Numbers are Int64.

**Algorithm** (number/prefixed; verified):

```python
valid = lf.filter(num.is_not_null() & prefix.is_not_null())
dist = valid.group_by(keys + ["__td_num"]).agg(width.max(), pl.len().alias("__td_n"), row.min().alias("__td_firstrow")).sort(keys + ["__td_num"])
# optional virtual neighbours so a missing first/last document shows up (range_start/range_end set, series min above/ max below them):
#   append rows with num = range_start - 1 (n = 0) / range_end + 1 for series where lo > start / hi < end
nxt = pl.col("__td_num").shift(-1).over(keys)                                        # keys = group_columns + ["__td_prefix"]
gaps = dist.with_columns(nxt.alias("__td_next")).filter(pl.col("__td_next") - pl.col("__td_num") > 1)
#   from = prefix + (num + 1) zero-padded, to = prefix + (next - 1), count = next - num - 1       finding = "gap"
dups = dist.filter(pl.col("__td_n") > 1)                  # finding "duplicate": from = to = value, count = occurrences, source_row = first occurrence (1-based)
ooo = valid.sort(ROW).with_columns(num.cum_max().shift(1).over(keys).alias("__td_prevmax")).filter(num < prevmax)
#   finding "out_of_order": from = to = value, count = 1, source_row = input position (1-based)
```

`out_of_order` means: *a row whose number is lower than the highest number seen earlier in the same series in input order*. It relies on the order rows arrive in; the dock tooltip says so. One gap row regardless of size (a jump from 1 to 10,000,000 is one row with `count = 9,999,998`; nothing is expanded).

**Date mode.** `date_expr(column, dtype, date_format)` -> distinct dates per group (`unique().sort`); a gap exists where `next - date > 1 day`; `from = date + 1`, `to = next - 1`, `count = days`. With `business_days_only`: `from = from.dt.add_business_days(0, roll="forward")`, `to = to.dt.add_business_days(0, roll="backward")`, `count = pl.business_day_count(from, to + 1 day)`; ranges with `count < min_gap_days` (including those wholly inside a weekend, whose count is 0) are dropped. Output `from`/`to` are ISO text (`dt.to_string("%Y-%m-%d")`), `prefix = ""`, `source_row` null.

**Output schema (one schema for all modes).** Socket 0 `Gaps` (`G`), `gaps_var = var_gaps_<id>`: `[*group_columns, prefix String, finding String, from String, to String, count Int64, source_row UInt32]`; `finding` in `gap | duplicate | out_of_order | date_gap`; sorted by `(group columns, prefix, finding, from)`. Socket 1 `Summary` (`S`), `summary_variable_name = var_gapsum_<id>`: base 11 + `series, gap_ranges, missing_items, duplicate_values, out_of_order_rows, unparseable_rows` (Int64). Definitions: `population_rows` = all input rows; `population_value`, `exception_value` = null; `exception_rows` = number of Gaps rows (all findings); `gap_ranges` = rows with `gap`/`date_gap`; `missing_items` = their `count` sum; `series` = distinct (group, prefix) series with a readable value (date mode: distinct groups, 1 when ungrouped); `unparseable_rows` = present but unreadable. Status `fail` if `exception_rows > 0`. Message (number/prefixed): `"{gap_ranges} gap ranges covering {missing_items} missing numbers; {duplicate_values} repeated numbers; {out_of_order_rows} numbers out of order."`; date mode: `"{gap_ranges} gap ranges covering {missing_items} days."`. `exceptions_var_name()` returns `gaps_var`.

**Criteria sentences.** `je_number is read as a prefix followed by digits (for example JE-000123); numbers missing between the lowest and highest value are reported separately for each ledger. Also reported: repeated numbers and numbers that appear after a higher number.` (number mode: `is read as a whole number`; no groups: drop `separately for each ...`; date mode: `posting_date is read as a date; days with no entry between the first and last date are reported ...` + ` Saturdays and Sundays are not expected.` when `business_days_only`.)

**Dock.**

| Section | Control (kind) | Field | History text |
|---|---|---|---|
| "Sequence" | `FormRow("Column", ColumnPicker)` (`picker`); `SegmentedControl(["Number", "Prefixed", "Date"])` (`segment`) | `sequence_column`, `mode` | `Gaps Column Changed`, `Gaps Type Changed` |
| "Group by" | `ColumnChecklist` + All/None | `group_columns` | `Gaps Groups Changed` |
| "Also report" (hidden in date mode) | `QCheckBox("Repeated numbers")`, `QCheckBox("Numbers out of order")` | `report_duplicates`, `report_out_of_order` | `Gaps Repeats Changed`, `Gaps Order Changed` |
| "Expected range" (hidden in date mode) | `FormRow("First", QSpinBox)`, `FormRow("Last", QSpinBox)`; both `0..2147483647` with `minimum = -1` and `specialValueText("Lowest seen")` / `("Highest seen")` (`optint`, burst) | `range_start`, `range_end` | `Gaps Range Changed` |
| "Dates" (visible only in date mode) | `FormRow("Format", combo)`; `FormRow("Smallest gap", QSpinBox 1..3660, " days")`; `QCheckBox("Skip weekends")` | `date_format`, `min_gap_days`, `business_days_only` | `Gaps Date Format Changed`, `Gaps Smallest Gap Changed`, `Gaps Weekends Changed` |
| "Result" | Count button + label | - | - |

Spin limit (documented): `QSpinBox` is 32-bit, so an expected range above 2,147,483,647 cannot be typed; the algorithm itself is Int64.

**Validation.** `sequence_column` empty 001; missing 002 / nested 003; group column missing 002; unknown `mode` 004; date mode: `date_format` 007, `min_gap_days < 1` 004 (`Smallest gap must be 1 day or more.`); number modes: `range_start`/`range_end` negative 004, `range_end < range_start` 004 (`Expected last number must be not below the first.`).

**Undo.** `set_setting` for all fields; `group_columns` a list copy; the spin's special value maps to `None` in the `optint` kind.

**Verified reference.** (a) `je = [JE-000001, JE-000002, JE-000005, JE-000005, JE-000004, JE-000009, X-0003, X-0001, je-7, JE-000010]`, no groups, `prefixed`: Gaps rows (`prefix, finding, from, to, count, source_row`): `JE- duplicate JE-000005 JE-000005 2 3`; `JE- gap JE-000003 JE-000003 1 null`; `JE- gap JE-000006 JE-000008 3 null`; `JE- out_of_order JE-000004 JE-000004 1 5`; `X- gap X-0002 X-0002 1 null`; `X- out_of_order X-0001 X-0001 1 8`. Summary: `series 3, gap_ranges 3, missing_items 5, duplicate_values 1, out_of_order_rows 2, exception_rows 6, population_rows 10`, message `3 gap ranges covering 5 missing numbers; 1 repeated numbers; 2 numbers out of order.` (b) `number` mode on `["1","2","3","7","8","12","12","11",null,"abc"]`: gaps `4..6 (3)`, `9..10 (2)`, duplicate `12 x2 (source_row 6)`, out of order `11 (source_row 8)`, `unparseable_rows 1`, status `fail`, code `TD-AUDIT-102`. (c) date mode on `["2024-03-01","2024-03-04","2024-03-05","2024-03-09","2024-03-15",null,"x"]`: `2024-03-02..03 (2)`, `2024-03-06..08 (3)`, `2024-03-10..14 (5)`, message `3 gap ranges covering 10 days.`, `unparseable_rows 1`; with `business_days_only`: `2024-03-06..08 (3)`, `2024-03-11..14 (4)`; with `min_gap_days = 3`: the 3-day and 5-day ranges. (d) with `group_columns=["led"]`, `range_start=1`, `range_end=11` on (a) plus `led = [A]*6 + [B,B,B,A]`: ledger A gains `JE-000011` (count 1) and ledger B gains `je-1..je-6 (6)`, `je-8..je-11 (4)`, `X-0004..X-0011 (8)`.

---

### 4.3 Benford

**Purpose.** Compare the leading digit(s) of an amount column with the distribution Benford's Law predicts and say, in a table, a chart and one verdict, whether the column looks natural. A drill-down output returns the source rows behind the digits that stand out.

**Settings** (`BenfordParams`):

```python
@dataclass
class BenfordParams(ParamsBase):
    amount_column: str = ""
    digits: int = 1                  # 1 = first digit (9 bins), 2 = first two digits (90 bins)
    min_abs_amount: float = 10.0     # |amount| below this is not tested; zero is never tested
    drill_auto: bool = True          # drill-down = digits that are over-represented AND significant
    drill_digits: list[int] = field(default_factory=list)   # used when drill_auto is False
```

Reason for `min_abs_amount = 10.00`: sub-10 amounts in ledgers are dominated by rounding, fees and tax lines; the user can lower it to `0.01`.

**Numerics (exact definitions; every formula below was executed).**

Let `x` be the amount read by `amount_expr`; the tested set is `{x : x is a number, x != 0, |x| >= min_abs_amount}`; `n = |tested set|`.

1. **Leading digits** of `a = |x|`: `e = floor(log10 a)`, `m = a / 10^e * (1 + 1e-12)`, renormalise `m` into `[1, 10)` (`m >= 10 -> m/10`, `m < 1 -> m*10`), `d1 = clip(floor(m), 1, 9)`, `d2 = clip(floor(10 m), 10, 99)`. The two guards exist because Polars `log10(1000.0)` returns `2.9999999999999996` and `0.3 / 0.1 = 2.9999999999999996`; without them 535 of 177,096 test values were wrong, with them **0** (checked against exact decimal digits of `repr(x)`; vector: `0.3->3, 0.07->7, 1000->1 (d2 10), 999.99->9 (99), 4.35->4 (43), 12345678.9->1 (12), 1e-5->1 (10), 0.29->2 (29), 9.99->9 (99)`).
2. **Expected proportion** `p_e(d) = log10(1 + 1/d)`, `d = 1..9` (first digit) or `10..99` (first two). Sums to 1.
3. **Observed** count `c_d`, proportion `p_o(d) = c_d / n`, expected count `E_d = n p_e(d)`, `difference = p_o - p_e`.
4. **z-statistic** (Nigrini 2012; always >= 0): `z_d = (|p_o - p_e| - cc) / sqrt(p_e (1 - p_e) / n)` with continuity correction `cc = 1/(2n)` applied only when `1/(2n) < |p_o - p_e|`, else `cc = 0`. `significant = z_d > 1.96` (two-sided 5 %).
5. **MAD** = `(1/K) * sum_d |p_o(d) - p_e(d)|`, `K = 9` or `90`.
6. **Conformity bands** (Nigrini, M. J. (2012), *Benford's Law: Applications for Forensic Accounting, Auditing, and Fraud Detection*, Wiley - the Mean Absolute Deviation ranges for first and first-two digits; also reproduced in Nigrini's articles in the *Journal of Accountancy*). Upper bound inclusive:

   | Test | close | acceptable | marginally acceptable | nonconformity |
   |---|---|---|---|---|
   | First digits (K = 9) | MAD <= 0.006 | <= 0.012 | <= 0.015 | > 0.015 |
   | First-two digits (K = 90) | MAD <= 0.0012 | <= 0.0018 | <= 0.0022 | > 0.0022 |

   Labels stored: `close`, `acceptable`, `marginal`, `nonconforming`. Source for the bands: Nigrini (2012), Table 7.1 (MAD critical values), as cited in the 2024 *Computational Statistics* paper on Benford MAD (doi 10.1007/s00180-024-01463-8) and implemented by the R package `benford.analysis`; the thresholds were cross-checked in a web search on 2026-10-21. They are the single constant `MAD_BANDS` in `benford.py`, pinned by a test.
7. **Chi-square** `chi2 = sum_d (c_d - E_d)^2 / E_d`, `df = K - 1` (8 or 89), `p_value = Q(df/2, chi2/2)` (regularised upper incomplete gamma) via `chi2_sf` below. Verified: `chi2_sf(3.841458820694124, 1) = 0.05`, `chi2_sf(15.50731305586545, 8) = 0.05`, `chi2_sf(20.090235029663233, 8) = 0.01`, `chi2_sf(112.02198, 89) = 0.05000004`, `chi2_sf(0, k) = 1`, and agreement with a 200,000-step Simpson integration of the density to 12 digits for `(x, df)` in `{(2.5,8),(15.5,8),(40,8),(60,89),(112,89),(130,89)}`.
8. **Verdict.** `status`: `close`/`acceptable` -> `pass`; `marginal` -> `warn`; `nonconforming` -> `fail`. If `n < MIN_TESTED[digits]` (100 for first digit, 1000 for first two - an implementation threshold, stated in the message) a `pass` becomes `warn` with code `TD-AUDIT-101`. `n == 0`: `warn`, `TD-AUDIT-101`, message `No row had a usable amount, so nothing was tested.`, `mad/chi_square/p_value` null, table counts 0. Unreadable text amounts: appended note + `TD-AUDIT-102`, `pass -> warn`.

**`chi2_sf` and table builder (verified; copy):**

```python
def _gser(a, x):                        # P(a, x) by series, used when x < a + 1
    gln, ap, s = math.lgamma(a), a, 1.0 / a; d = s
    for _ in range(10000):
        ap += 1; d *= x / ap; s += d
        if abs(d) < abs(s) * 1e-16: break
    return s * math.exp(-x + a * math.log(x) - gln)

def _gcf(a, x):                         # Q(a, x) by Lentz continued fraction, used when x >= a + 1
    gln, tiny = math.lgamma(a), 1e-300
    b = x + 1 - a; c, d = 1 / tiny, 1 / b; h = d
    for i in range(1, 10000):
        an = -i * (i - a); b += 2
        d = an * d + b; d = tiny if abs(d) < tiny else d
        c = b + an / c; c = tiny if abs(c) < tiny else c
        d = 1 / d; de = d * c; h *= de
        if abs(de - 1) < 1e-16: break
    return math.exp(-x + a * math.log(x) - gln) * h

def chi2_sf(x, df):
    if x <= 0: return 1.0
    a, xx = df / 2.0, x / 2.0
    return max(0.0, 1.0 - _gser(a, xx)) if xx < a + 1 else min(1.0, _gcf(a, xx))
```

`build_table(counts, ndig) -> pl.DataFrame` (eager, 9 or 90 rows): left-join the observed counts onto the full digit range (missing = 0), then `proportion = count / n`, `expected_proportion = (1 + 1/digit).log10()`, `expected_count = expected_proportion * n`, `difference = proportion - expected_proportion`, `z_statistic = (|difference| - when(1/(2n) < |difference|).then(1/(2n)).otherwise(0)) / sqrt(expected_proportion (1 - expected_proportion) / n)`, `significant = z_statistic > 1.96`, `chi_square_contribution = (count - expected_count)^2 / expected_count`. `n == 0` -> counts 0, `proportion/difference/z/chi` null, `significant` false.

**Run function** `run_benford(frame, p) -> AuditResult(frames=(Table, Summary, Drill-down), summary_index=1, extras={"table", "stats", "flagged", "chart"})`:

1. `a = amount_expr(...)`; `tested = lf.filter(usable).with_columns(first_digits_expr(...).alias("benford_digits"))`.
2. **Collect** (one streaming pass each; this is the only collect, <= 90 groups): `per_digit = tested.group_by("benford_digits").agg(len, sum(|x|))` and `totals = select(len, bad)` where `bad` counts present-but-unreadable amounts.
3. `table = build_table(counts)`, `stats` (MAD, conformity, chi-square, p-value), `flagged = digits with significant and difference > 0` (**over-represented only**: a deficit is a symptom, an excess is where fabricated entries hide).
4. **Drill-down** (lazy): `tested.filter(benford_digits.is_in(drill_set)).select(originals + ["benford_digits"])` where `drill_set = flagged` when `drill_auto` else `sorted(set(drill_digits))`; empty set -> zero rows with the full schema.
5. **Summary** (built from the eager numbers via a one-row `pl.LazyFrame`, then `summary_frame`): `population_rows` = all input rows, `population_value` = sum(|x|) of tested rows, `exception_rows` / `exception_value` = tested rows (and gross value) whose digit is in `flagged`; extras `digits, tested_rows, mad, conformity, chi_square, chi_square_df, p_value, flagged_digits` (text `"5, 6, 7"`), `unparseable_rows`. `test_name` = `Benford first digit` / `Benford first two digits`. Message: `Mean absolute deviation 0.0036: close with Benford's Law (2,013 rows tested, chi-square p-value 0.9429).`

**Outputs.**

| Socket | Name | Variable attr | Schema |
|---|---|---|---|
| 0 | Table (`T`) | `table_var = var_benford_<id>` | `digit Int64, count Int64, proportion, expected_proportion, expected_count, difference, z_statistic Float64, significant Boolean, chi_square_contribution Float64` (9 or 90 rows; the table is eager data wrapped with `.lazy()`) |
| 1 | Summary (`S`) | `summary_variable_name = var_benfordsum_<id>` | base 11 + `digits Int64, tested_rows Int64, mad Float64, conformity String, chi_square Float64, chi_square_df Int64, p_value Float64, flagged_digits String, unparseable_rows Int64` |
| 2 | Drill-down (`D`) | `drill_var = var_benforddrill_<id>` | input columns + `benford_digits Int64` (rows in input order) |

`exceptions_var_name()` returns `drill_var`. Because Benford and the drill-down need the digit counts, `get_code` calls `run_benford(...).for_run()`; the counting pass executes inside the Run, so a broken amount column fails the node.

**Chart (decision: custom `QPainter` widget; not `core/charts.py`).** Reasons: `ChartSpec` plots one x/y series type per chart and its only renderer imports matplotlib, which the startup guard keeps out of launch (`nodes/__init__.py:156-159`, brief 10.4); the dock needs a 300 px-wide, 170 px-high bar-plus-line that follows the theme. `core/audit/benford.py::chart_data(table, flagged) -> BenfordChartData(digits, observed, expected, flagged, counts, z)` is the Qt-free model; `Audit/benford_chart.py::BenfordChartWidget(QWidget)` paints it:

* `set_data(data: BenfordChartData | None)`; `None` draws the centred text `No data to chart` in `text_secondary`.
* `sizeHint 300x170`, `minimumHeight 170`, expanding horizontally. `accessibleName = "Benford chart"`, `setMouseTracking(True)`.
* Paint (all colours from `get_theme_manager().color(token)`; no hex): y-axis 0..`ceil(max(observed, expected) * 1.1 / 0.05) * 0.05`, three gridlines in `border_subtle` labelled in percent; **observed bars** `accent_primary`, bars of flagged digits `danger`; **expected** as a 2 px polyline with 4 px dots in `text_secondary`; x labels `1..9` (first digit) or every tenth value `10, 20, ... 90` (first two) in `text_primary`, 8 pt.
* `mouseMoveEvent` finds the bar under the cursor and shows `QToolTip.showText(globalPos, f"Digit {d}: observed {obs:.1%} ({count:,}), expected {exp:.1%}, z {z:.2f}", self)`.
* `apply_theme()` calls `update()`; the dock connects it exactly like other widgets that paint tokens.

**Dock.**

| Section | Control (kind) | Field | History text |
|---|---|---|---|
| "Amount" | `FormRow("Column", ColumnPicker)` | `amount_column` | `Benford Column Changed` |
| "Test" | `SegmentedControl(["First digit", "First two"])` (`segment`, `{"First digit": 1, "First two": 2}`); `FormRow("Minimum", QDoubleSpinBox 0..1e12, 2 decimals)` (`dspin`, burst) | `digits`, `min_abs_amount` | `Benford Digits Changed`, `Benford Minimum Changed` |
| "Result" | `BenfordChartWidget`; below it a word-wrapped `QLabel` with `summary.message` and a second label `Chi-square {chi:.2f} (df {df}), p = {p:.4g}`; both read from `self.last_result.extras` (live result) | - | - |
| "Drill-down digits" | `QCheckBox("Digits that stand out (automatic)")` (`check`); `ColumnChecklist` of digits (`digitlist`, labels `f"{d}   z {z:.1f}   {count:,} rows"`), enabled only when automatic is off | `drill_auto`, `drill_digits` | `Benford Drill-down Mode Changed`, `Benford Drill-down Digits Changed` |

When the input is not evaluated yet the chart shows its empty state. `_apply_visibility()` enables/disables the checklist. The table is only a socket (it previews in the Data Preview dock); the dock does not embed a table.

**Validation.** `amount_column` empty 001, missing 002, nested 003; `digits not in (1, 2)` 004; `min_abs_amount < 0` 004 (`Minimum amount must be 0 or more.`); any `drill_digits` outside `1..9` / `10..99` 004; input already has `benford_digits` 005.

**Undo.** `set_setting` for all; `drill_digits` pushed as a sorted copy.

**Verified reference values (independent pure-Python script `benford_reference.py`, matched by the Polars implementation to 1e-12).**

```python
# reference(counts, digits) in plain math: p_e = log10(1+1/d); diff = |p_o-p_e|; cc = 1/(2n) if 1/(2n) < diff else 0
# z = (diff-cc)/sqrt(p_e(1-p_e)/n); E = p_e n; chi2 = sum((c-E)^2/E); MAD = sum(diff)/K
```

| Dataset (fixture) | n | MAD | chi-square (df) | p-value | band / status | z (first, second, last digit) |
|---|---|---|---|---|---|---|
| First digit, counts `[301,176,125,97,79,67,58,51,46]` (amounts `d*1000 + i`, `i < count_d`) | 1000 | 0.0001011163 | 0.002362 (8) | 0.9999999999999 | close / pass | 0.002068, 0.007576, 0.036700 |
| First digit, 100 per digit | 900 | 0.0597170351 | 361.528464 (8) | 3.1297e-73 | nonconforming / fail | 12.384628, 5.074164, 9.302996; significant digits 1,2,5,6,7,8,9 |
| First two, 10 per digit 10..99 | 900 | 0.0059742752 | 366.372711 (89) | 2.4784e-35 | nonconforming / fail (0.00597 > 0.0022) | 4.476884, 4.109703, 2.817293 |

Hand check of the second row, digit 1: `p_e = 0.30103`, `p_o = 0.111111`, `diff = 0.189919`, `cc = 1/1800 = 0.000556`, `se = sqrt(0.30103*0.69897/900) = 0.015290`, `z = (0.189919 - 0.000556)/0.015290 = 12.3846`.

Ledger (generator of 7.5; column `amount`, `min_abs_amount = 10`):

| Population | digits | n | MAD | conformity | chi-square | p-value | flagged digits | drill rows |
|---|---|---|---|---|---|---|---|---|
| GL (2,013 rows) | 1 | 2013 | 0.003594 | close | 2.8592 | 0.9429 | none | 0 |
| GL | 2 | 2013 | 0.001743 | acceptable | 86.2517 | 0.5628 | `49, 94` | 48 |
| AP (400 rows, amounts 5,000-9,800) | 1 | 400 | 0.155327 | nonconforming | 959.9006 | 6.7357e-202 | `5, 6, 7, 8, 9` | 400 |
| all 2,413 rows | 1 | 2413 | 0.028145 | nonconforming | 189.2603 | 1.1653e-36 | `5, 6, 7, 8, 9` | 1032 |

GL first-digit counts: `{1:590, 2:361, 3:243, 4:187, 5:170, 6:138, 7:119, 8:104, 9:101}`; AP: `{5:90, 6:78, 7:79, 8:87, 9:66}`. Exception value for AP first digit = `2,951,968.09`.

---

### 4.4 Sample

**Purpose.** Draw a sample that a reviewer can redraw: same rows + same settings + same seed -> the identical sample, whatever order the rows arrive in. Four methods; every draw writes a Selection log.

**Reproducibility decision (final).** The sample is **order-independent**. Before drawing, the population is put in a *canonical order*: sorted by the **stable key** (`key_columns`, or all columns when empty) with nulls last; if the key is not unique the remaining columns break ties, so the order is total up to identical rows (identical rows are interchangeable). Draws are positions in that order. Reason: the same ledger re-extracted from the source system usually arrives in a different order, and a re-performance must give the same sample; "first N rows then shuffle" would not. Randomness comes from our own **SplitMix64** (below), not from Polars/NumPy, so a library upgrade can never change a sample (Polars documents that `shuffle`/`hash` streams may change between versions). Algorithm id `td-sample-1` is written to every log; changing any step below requires a new id.

**Settings** (`SamplingParams`):

```python
@dataclass
class SamplingParams(ParamsBase):
    method: str = "random"          # random | systematic | mus | stratified
    seed: int = 42                  # 0 .. 2**31-1 (spin limit); any non-negative int is accepted from a file
    size_kind: str = "count"        # count | percent   (ignored by stratified)
    sample_size: int = 100
    sample_percent: float = 10.0
    key_columns: list[str] = field(default_factory=list)   # [] = all columns
    amount_column: str = ""         # required for mus/stratified; for others only fills the log's values
    band_edges: list[float] = field(default_factory=list)  # stratified: ascending; stratum k holds edges[k-1] <= |x| < edges[k]
    band_sizes: list[int] = field(default_factory=list)    # stratified: len(band_edges) + 1 values; -1 = take every row
```

**PRNG and primitives (verified; copy exactly).**

```python
MASK = (1 << 64) - 1
def _mix(z):
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK
    return z ^ (z >> 31)
class SplitMix64:
    def __init__(self, seed): self.state = seed & MASK
    def next_u64(self):
        self.state = (self.state + 0x9E3779B97F4A7C15) & MASK
        return _mix(self.state)
    def unit(self): return (self.next_u64() >> 11) / float(1 << 53)       # [0, 1)
def derive_seed(seed, tag): return _mix((seed & MASK) ^ _mix((tag + 1) & MASK))   # one stream per stratum

def floyd_positions(rng, population, size):          # uniform subset without replacement, sorted
    if size >= population: return list(range(population))
    chosen = set()
    for j in range(population - size, population):
        t = rng.next_u64() % (j + 1)                 # modulo bias < 1e-9 for populations below 1e10: accepted
        chosen.add(j if t in chosen else t)
    return sorted(chosen)

def systematic_positions(rng, population, size):     # fractional interval so the last rows are reachable
    if size >= population: return list(range(population)), 1.0, 0.0
    interval = population / size; start = rng.unit() * interval
    return [int(math.floor(start + i * interval)) for i in range(size)], interval, start
```

Verified outputs: `SplitMix64(0)` first three `next_u64()` = `0xe220a8397b1dcdaf, 0x6e789e6aa1b965f4, 0x06c45d188009454f` (the published SplitMix64 vector); `floyd_positions(SplitMix64(42), 20, 5) == [0, 5, 10, 13, 19]`; `systematic_positions(SplitMix64(42), 20, 5) == ([2, 6, 10, 14, 18], 4.0, 2.9662595150872932)`; `systematic_positions(SplitMix64(42), 10, 3) == ([2, 5, 9], 3.3333333333333335, 2.471882929239411)`; `derive_seed(42, 0) == 14026160589095004880`, `derive_seed(42, 1) == 8933602108916158448`.

**Size rule.** `count`: `n = sample_size`; `percent`: `n = ceil(available * sample_percent / 100)` (at least 1 when `available > 0`), where `available` = population rows (random, systematic) or eligible rows (mus). If `n > available`: `n = available` and the log `note` gets `TD-AUDIT-103: Requested {n:,} but only {available:,} rows exist; the whole population was selected.` (no error).

**Methods.**

* **random**: `positions = floyd_positions(SplitMix64(seed), N, n)` in canonical order.
* **systematic**: interval `k = N / n` (real), start `u = unit() * k`, positions `floor(u + i k)`, `i = 0..n-1`. Always exactly `n` distinct positions (`k >= 1` and `u < k`).
* **mus (monetary-unit / probability proportional to size)** on `|amount|`:
  * **Eligible** rows: readable amount, `|x| > 0`. Zero and unreadable rows cannot be selected (probability proportional to zero is zero); they appear in **Not sampled**, and the log `note` says how many (`... rows have a zero or unreadable amount and cannot be selected.`). **Negatives** use `|x|` (a credit has the same chance as a debit of the same size). No eligible row -> `TD-AUDIT-010`.
  * `n = min(requested, eligible)`. **Items larger than the interval (decision: certainty stratum, iterative).** `V` = sum of `|x|` of eligible rows, sorted by amount descending (stable, ties by canonical order). While `n_rem > 0` and the largest remaining amount `>= V_rem / n_rem`: select it with certainty (`sample_basis = "high_value"`), `V_rem -= amount`, `n_rem -= 1`. Reason: a classic MUS can hit the same big item several times and return fewer distinct items than requested; this procedure returns **exactly `n` distinct items** and every item that would exceed the interval is audited for certain.
  * Remaining items in canonical order: cumulative sums `C`; `interval = C[-1] / n_rem`; `start = unit() * interval`; points `start + j * interval`, `j = 0..n_rem-1`; an item is hit when `C_before <= point < C_after`, implemented as `searchsorted(C, points, side="right")` clamped to the last item (`sample_basis = "interval"`). Because no remaining item is as large as the interval, each point hits a different item, so exactly `n_rem` items.
  * Verified toy: `amounts = [5000,120,80,300,40,60,900,20,150,330]` (positions 0-9), `n = 4`, seed 42 -> positions `[0, 3, 6, 9]`; high-value `{0, 6}` (5000 >= 7000/4; then 900 >= 2000/3), then `interval = 550.0` (1100 / 2), `start = 407.8606833245028`, points 407.86 and 957.86 hit positions 3 (cumulative 500) and 9 (1100); `n_high = 2`.
* **stratified**: band edges ascending (`1000, 10000`) make strata `|x| < 1000`, `1000 <= |x| < 10000`, `|x| >= 10000` (stratum number = `searchsorted(edges, |x|, side="right") + 1`; value on an edge belongs to the higher stratum). `band_sizes[s]` = rows to draw from stratum `s` (`-1` = all rows). Each stratum is drawn with `floyd_positions(SplitMix64(derive_seed(seed, s)), M_s, min(size, M_s))` over its members in canonical order; a stratum with fewer rows than asked takes them all and logs `TD-AUDIT-103`. Rows with unreadable amounts are in no stratum (never sampled) and the overall `note` reports how many. Empty `band_edges` = one stratum.

**Canonical order function (verified).**

```python
def canonical_order(lf, keys, all_cols, extra=()):
    base = lf.with_row_index(ROW); keys = keys or list(all_cols)
    u = base.select(pl.struct(keys).n_unique().alias("u"), pl.len().alias("n")).collect(engine="streaming")
    sort_cols = keys if u["u"][0] == u["n"][0] else keys + [c for c in all_cols if c not in keys]
    cols = list(dict.fromkeys(sort_cols + [ROW] + list(extra)))
    return base.select(cols).sort(sort_cols, nulls_last=True, maintain_order=True).collect()
```

`extra = ("__td_amt",)` (the Float64 `amount_expr`) when an amount column is set. Memory: unique key -> key columns + row index; tied or empty key -> **the whole frame** (documented in the key control's tooltip: `Choose a column that is unique per row (for example the journal number) to keep memory small.`). A nested-dtype column with no key chosen raises `TD-AUDIT-003`.

**Assembling outputs (verified).**

```python
selection = pl.DataFrame({ROW: rows[positions].astype(np.uint32), "sample_seq": np.array(positions) + 1, ...})   # sample_seq = 1-based rank in canonical order
sample = base.join(selection.lazy(), on=ROW, how="inner", maintain_order="left").select(originals + ["sample_seq", *extra_cols])
not_sampled = base.join(selection.lazy().select(ROW), on=ROW, how="anti", maintain_order="left").select(originals)
```

Output rows keep **input order** (users expect that); `sample_seq` is the canonical rank, so it is the same whatever the input order. Extra columns: MUS adds `sample_basis` String (`high_value` | `interval`), stratified adds `sample_stratum` Int64; the input must not already contain `sample_seq`, `sample_stratum`, `sample_basis` (005).

**Selection log** (socket 2, `log_variable_name = var_samplelog_<id>`, eager `pl.DataFrame`, columns in this order): `scope` (`overall` | `stratum`), `stratum` Int64, `method`, `seed` Int64, `algorithm` (`td-sample-1`), `population_rows` Int64, `population_value` Float64 (gross; null without amount column), `requested_size` Int64, `sample_size` Int64, `sample_value` Float64, `interval` Float64 (systematic: rows between picks; MUS: monetary interval), `start` Float64, `high_value_items` Int64 (MUS), `lower_bound`, `upper_bound` Float64 (strata), `key_columns` String, `amount_column` String, `parameters` String (`json_params`), `note` String. One `overall` row; stratified adds one `stratum` row per stratum. No timestamp (determinism; `get_code` must stay idempotent).

**`TestSummary` for Sample** (`sample_test_summary(log, p, *, node_id, sample_var)` in `sampling.py`): `test_name = "Sample"`, `status = "pass"`, `population_rows/value` from the overall row, `exception_rows = sample_size`, `exception_value = sample_value`, `exception_rate = sample_size / population_rows`, `criteria` = `criteria(p, population_rows)`, `parameters = p.to_dict()`, `message = f"Selected {n:,} of {N:,} rows ({method_text}, seed {seed})."`, `code = "TD-AUDIT-103"` when the overall `note` starts with it, `exceptions_var = sample_var`, `details = {"selection_log": log.to_dicts(), "seed": seed, "interval": ..., "start": ...}`. Plan 02 reads the seed from `parameters["seed"]` and the full log from `details["selection_log"]`.

**Live evaluation.** `build_result()` calls `run_sample(frame, params, live=True)`: when the input has more than `LIVE_ROW_LIMIT = 200,000` rows it returns empty frames, sets the tooltip `Population has {n:,} rows: the sample is drawn when you Run.` and leaves `test_summary = None`. Run always draws. (Reason: live evaluation is on the GUI thread and the draw sorts the population.)

**Outputs.** Socket 0 `Sample` (`S`, `sample_var = var_sample_<id>`), socket 1 `Not sampled` (`N`, `not_sampled_var = var_notsampled_<id>`), socket 2 `Selection log` (`L`, `log_variable_name`). `exceptions_var_name()` returns `sample_var`. Sample overrides `after_execution` to build its `TestSummary` from the log variable.

**Dock.**

| Section | Control (kind) | Field | History text |
|---|---|---|---|
| "Method" | `NoWheelComboBox` items Random / Systematic / Monetary unit / Stratified (`combo`, itemData = key) | `method` | `Sample Method Changed` |
| "Size" (hidden for stratified) | `SegmentedControl(["Count", "Percent"])`; `QSpinBox 1..100000000` (`spin`, burst) shown for Count; `QDoubleSpinBox 0.01..100` (2 decimals, suffix " %") shown for Percent | `size_kind`, `sample_size`, `sample_percent` | `Sample Size Kind Changed`, `Sample Size Changed`, `Sample Percent Changed` |
| "Seed" | `QSpinBox 0..2147483647` (`spin`, burst) + `IconButton.themed("New random seed", rsm_icon=icon_refresh)`; click sets the seed to `time.time_ns() % 2147483648` through `set_setting` (undoable) | `seed` | `Sample Seed Changed` |
| "Stable key" | `ColumnChecklist` (+ All/None) | `key_columns` | `Sample Key Changed` |
| "Amount" (shown for mus/stratified; optional otherwise) | `FormRow("Column", ColumnPicker)` | `amount_column` | `Sample Amount Changed` |
| "Strata" (stratified only) | `FormRow("Edges", QLineEdit "1000, 10000")` (`numlist`, burst); `FormRow("Sizes", QLineEdit "20, 20, all")` (`sizelist`, burst) | `band_edges`, `band_sizes` | `Sample Edges Changed`, `Sample Strata Sizes Changed` |
| "Result" | word-wrapped label `Selected {n:,} of {N:,} rows; interval {interval:,.2f}` from `last_result.extras["log"]` | - | - |

**Validation.** unknown method 004; `seed < 0` 004; key column missing 002/nested 003; count mode `sample_size < 1` 004 (`Sample size must be 1 or more.`); percent outside `(0, 100]` 004 (`Sample percent must be above 0 and at most 100.`); mus/stratified without amount column 001; stratified: edges not strictly increasing or negative 009 (`Strata edges: values must be 0 or more and strictly increasing.`), `len(band_sizes) != len(edges)+1` 009 (`Strata sizes: expected 3 values, found 2.`), a size of `0` or below `-1` 009; no readable amount for mus/stratified 010; reserved output names 005.

**Undo.** `set_setting`; lists pushed as copies. The "New random seed" button is one undo step.

**Verified reference (ledger of 7.5, `key_columns=["je_number"]`, seed 42).** `random n=100`: 100 sampled / 2313 not sampled; input-order first three `GL-000015, GL-000038, GL-000049`; `systematic n=100`: interval `24.13`, start `17.893960524764097`, first three `GL-000004, GL-000029, GL-000053`; `mus n=50` on `amount`: interval `3468934.663799994` (= 173,446,733.19 / 50), start `2572440.1134282183`, `high_value_items 0`, sample value `26,253,624.04`, first three `GL-000055, GL-000081, GL-000140`; `stratified` edges `[1000, 10000]`, sizes `[20, 20, -1]`: strata populations `828, 755, 830`, sample `870` (`20 + 20 + 830`), sample value `169,016,858.98`. The same rows shuffled give the same sampled set for every method (verified). Percent `10` of 2,413 -> `242`.

---

### 4.5 Risk Filters

**Purpose.** One node, seven checkboxes. Each switched-on test flags entries; an entry flagged by any test goes to **Flagged** with the list of tests that fired and a risk score; everything else goes to **Not flagged**.

**Settings** (`RiskParams`): column roles `date_column` (posting date), `effective_date_column` (optional), `amount_column`, `description_column`, `manual_column`, `date_format`; switches `weekend, holiday, round_amount, just_below_limit, keyword, after_period_end, manual_journal` (bool, default `False`); options `holidays: list[str]` (ISO dates), `round_multiple: int = 1000`, `approval_limits: list[float]`, `below_pct: float = 2.0`, `keywords: list[str]`, `period_end: str = ""`, `manual_values: list[str] = ["manual","m","y","yes","true","1"]`, `weights: dict[str,int]` (test id -> 1..10, default 1 each).

**The seven tests (decisions; each yields a Boolean that is never null - an unreadable cell does not fire a test).**

| id | Label in `risk_tests` | Fires when | Needs |
|---|---|---|---|
| `weekend` | Weekend posting | `date.dt.weekday() >= 6` (ISO: Saturday 6, Sunday 7) | `date_column` |
| `holiday` | Public-holiday posting | `date` is in the user's list | `date_column`, `holidays` |
| `round_amount` | Round amount | `cents = round(\|amount\| * 100)`; `cents > 0 and cents % (round_multiple * 100) == 0`. Integer cents avoid float error. "Ending 000" is `round_multiple = 1000` (the default). | `amount_column` |
| `just_below_limit` | Just below approval limit | for any limit `L`: `round(L*100*(1 - below_pct/100)) <= cents < round(L*100)`; exactly at the limit does **not** fire | `amount_column`, `approval_limits`, `below_pct` |
| `keyword` | Keyword in description | any keyword is a substring of the description, both lower-cased (`str.contains(literal=True)`, so no regex surprises) | `description_column`, `keywords` |
| `after_period_end` | Posted after period end | `date > period_end`; if `effective_date_column` is set it must also satisfy `effective <= period_end` (back-dated entry). Reason: without the effective date every entry in the next period would fire. | `date_column`, `period_end` (+ optional effective) |
| `manual_journal` | Manual journal | `manual_column` stripped and lower-cased is in `manual_values` (lower-cased) | `manual_column`, `manual_values` |

`risk_score = sum(weight[t] for each fired test)` (Int64; `0` = not flagged); `risk_tests` = labels of fired tests joined by `"; "` in the table's order (`pl.concat_str([when(flag).then(lit(label))...], separator="; ", ignore_nulls=True)`; verified: all-null gives `""`). Weights are per test (a spin in each test's section).

**Run function** `run_risk_filters(frame, p) -> AuditResult(frames=(Flagged, Not flagged, Summary), summary_index=2)`: build the flag expressions (excerpt, verified):

```python
d = date_expr(p.date_column, schema[p.date_column], p.date_format)             # Date | null
a = amount_expr(p.amount_column, schema[p.amount_column])
cents = (a.abs() * 100).round(0).cast(pl.Int64)
flags = {"weekend": d.dt.weekday() >= 6,
         "holiday": d.is_in([dt.date.fromisoformat(h) for h in p.holidays]),
         "round_amount": (cents > 0) & (cents % (p.round_multiple * 100) == 0),
         "just_below_limit": pl.any_horizontal([(cents >= round(L*100*(1-p.below_pct/100))) & (cents < round(L*100)) for L in p.approval_limits]),
         "keyword": pl.any_horizontal([text.str.contains(k.lower(), literal=True) for k in p.keywords]),
         ...}                                                                    # only the switched-on ones
flags = {k: v.fill_null(False) for k, v in flags.items()}
score = sum((flags[t].cast(pl.Int64) * weight[t] for t in on), pl.lit(0, dtype=pl.Int64))
```

Flagged = rows with `risk_score > 0` (`originals + ["risk_tests", "risk_score"]`, input order); Not flagged = the rest (`originals`).

**Outputs.**

| Socket | Name | Variable attr | Schema |
|---|---|---|---|
| 0 | Flagged (`F`) | `flagged_var = var_riskflag_<id>` | input columns + `risk_tests String, risk_score Int64` |
| 1 | Not flagged (`N`) | `not_flagged_var = var_risknone_<id>` | input columns |
| 2 | Summary (`S`) | `summary_variable_name = var_risksum_<id>` | base 11 + `flagged_two_or_more, total_score, unparseable_rows` (Int64) + one Int64 count per test, `n_weekend, n_holiday, n_round_amount, n_just_below_limit, n_keyword, n_after_period_end, n_manual_journal` (**null** for a test that is switched off) |

Summary: `population_rows` = all rows; `population_value` / `exception_value` = gross `|amount|` (null without `amount_column`); `exception_rows` = flagged rows; `flagged_two_or_more` = rows with >= 2 fired tests; `total_score` = sum of `risk_score`; status `warn` when `exception_rows > 0`, else `pass` (indicators are not misstatements, so never `fail`); message `"{exception_rows} of {population_rows} entries were flagged by at least one risk test."`; `unparseable_rows` counts present-but-unreadable posting dates, effective dates and amounts. `exceptions_var_name()` returns `flagged_var`.

**Criteria sentence.** `Entries are flagged when any of these apply: posted on a Saturday or Sunday (posting_date); posted on a listed public holiday (posting_date; 1 dates); a round amount: a whole multiple of 1,000 (amount); an amount within 2% below an approval limit (5,000, 10,000); a description containing 'reversal' and 'plug'; posted after the period end 2024-03-31, with an effective date on or before it (effective_date); a manual journal (source is one of manual).` Only switched-on tests appear, in table order, joined by `; `.

**Dock.**

| Section | Control (kind) | Field | History text |
|---|---|---|---|
| "Columns" | `FormRow` + `ColumnPicker` x5: Posting date, Effective date (optional), Amount, Description, Manual flag; `FormRow("Date format", combo)` | `date_column, effective_date_column, amount_column, description_column, manual_column, date_format` | `Risk Date Column Changed`, `Risk Effective Column Changed`, `Risk Amount Column Changed`, `Risk Description Column Changed`, `Risk Manual Column Changed`, `Risk Date Format Changed` |
| one `ConfigSection` per test, titled with the test label; `section.add_header_action(QCheckBox)` is the switch (`check`); body rows are disabled while the switch is off | switch / options as below | per test | `Risk <Label> Changed` |
| Weekend | switch only | `weekend` | |
| Holiday | `QPlainTextEdit` one ISO date per line, height 90, placeholder `2024-12-25` (`lines`, burst) | `holiday`, `holidays` | |
| Round amount | `FormRow("Multiple of", QSpinBox 1..1000000000)` (`spin`, burst) | `round_amount`, `round_multiple` | |
| Just below limit | `FormRow("Limits", QLineEdit "5000, 10000")` (`numlist`, burst); `FormRow("Within", QDoubleSpinBox 0.1..99.9, " %")` (`dspin`, burst) | `just_below_limit`, `approval_limits`, `below_pct` | |
| Keyword | `QPlainTextEdit` one word per line (`lines`, burst) | `keyword`, `keywords` | |
| Period end | `FormRow("Period end", QLineEdit "2024-03-31")` (`text`, burst; add kind `text` = `QLineEdit` read `.text().strip()`, signal `textChanged`, debounced) | `after_period_end`, `period_end` | |
| Manual journal | `QPlainTextEdit` values (`lines`, burst) | `manual_journal`, `manual_values` | |
| each test section | `FormRow("Weight", QSpinBox 1..10)` (`spin`) | `weights` (whole dict replaced: `set_setting("weights", {**self.weights, id: v}, ...)`) | `Risk Weight Changed` |
| "Result" | Count button + label | - | - |

**Validation (order).** no test on 008; weekend/holiday/period need `date_column` 001 (+ missing 002) and `date_format` 007; round/just-below need `amount_column` 001; `amount_column` set but missing 002; keyword needs `description_column` 001 and >= 1 keyword 004 (`Keywords must be at least one word.`); manual needs `manual_column` 001 and values 004; holiday needs >= 1 date 004 and each valid `YYYY-MM-DD` 006; period end valid 006; effective column missing 002; `round_multiple < 1` 004; limits non-empty and all `> 0` 004; `below_pct` not in `(0,100)` 004; any weight outside 1..10 004; input has `risk_tests` or `risk_score` 005.

**Undo.** `set_setting` for all (lists/dict deep-copied). Switching a test off keeps its option values (nothing is cleared).

**Verified reference.**

Unit fixture (7 rows; date, amount, description, source): `("2024-03-02","5,000.00","Reversal of accrual","Manual")`, `("2024-03-04","4,900","normal","Auto")`, `("2024-12-25","1000","Plug entry","m")`, `("2024-04-03","9999.99","x","AUTO")`, `("2024-03-09","1,000.50","MANUAL adj","y")`, `(null,"(2000)",null,null)`, `("2024-03-05","123.45","lunch","Auto")`; all seven tests on, `holidays=["2024-12-25"]`, `approval_limits=[5000,10000]`, `keywords=["reversal","plug","manual"]`, `period_end="2024-03-31"`, no effective column:

| Row | `risk_score` | `risk_tests` |
|---|---|---|
| 0 | 4 | `Weekend posting; Round amount; Keyword in description; Manual journal` |
| 1 | 1 | `Just below approval limit` |
| 2 | 5 | `Public-holiday posting; Round amount; Keyword in description; Posted after period end; Manual journal` |
| 3 | 2 | `Just below approval limit; Posted after period end` |
| 4 | 3 | `Weekend posting; Keyword in description; Manual journal` |
| 5 | 1 | `Round amount` (null date/description fire nothing; `(2000)` reads as -2000) |
| 6 | not flagged | |

Summary: population 7, exception 6, `flagged_two_or_more 4`, `total_score 16`, `n_weekend 2, n_holiday 1, n_round_amount 3, n_just_below_limit 2, n_keyword 3, n_after_period_end 2, n_manual_journal 3`, population_value `24023.94`, status `warn`, message `6 of 7 entries were flagged by at least one risk test.` Row 0's `5,000.00` is **not** "just below" the 5,000 limit (at the limit); row 1's `4,900` is (inclusive lower bound).

Ledger of 7.5 (holidays `["2024-03-29"]`, limits `[5000, 10000]` at 2 %, keywords `["reversal","plug"]`, period end `2024-03-31` with `effective_date`, manual values `["manual"]`): flagged **94**, not flagged **2,319**, `n_weekend 16, n_holiday 4, n_round_amount 21, n_just_below_limit 13, n_keyword 9, n_after_period_end 7, n_manual_journal 26`, `flagged_two_or_more 1`, `total_score 96`, max score 3 (only `GL-000801`: `Weekend posting; Round amount; Manual journal`), exception value `7,455,480.46`, population value `173,446,733.19`.

---

## 5. Ordered implementation steps

One commit per step. Run the "done when" commands before committing (PowerShell, repo root; `$PY = ".venv\Scripts\python.exe"`; never bare `pytest`, never `uv sync` - brief 2.2/2.3). Each step ends with `ruff format` then `ruff check` on **only the files you touched** (the repo's ruff baseline is not clean; compare before/after).

**Step 0 - baseline (no commit).** `& $PY -m pytest tests\unit -q` and `& $PY -m pytest tests\e2e -q`; record the pass counts (brief: 334 / 20). `& $PY -m pytest tests\ui -q` records the 27-failure baseline.

**Step 1 - foundations** (commit `Add Audit node family and shared audit helpers`).

| File | Change |
|---|---|
| `core/node_configuration.py` | `NodeTypes.AUDIT`, `AuditNodes`, registry + `_OPCODE_ENUMS` + `__all__` (3.1) |
| `qt/helpers/context_menu_mixin.py:40-46` | `"Audit"` category |
| `core/audit/__init__.py` | owned by plan 02 (lazy re-exports): this plan assumes it exists. Create it only if plan 02 has not landed, and then leave it EMPTY (docstring only); plan 02 replaces it. Never edit it. Modules `core/audit/<name>.py` import only `core.audit.common` / stdlib / polars / numpy, never the package `__init__`'s re-exports or plan 02's modules |
| `core/audit/common.py` | exactly 3.5 + `summary_frame`/`warn_unreadable` (3.6) + `parse_number_list`, `parse_size_list` (3.8) |
| `core/audit/test_summary.py` | 3.6 |
| `qt/widgets/common/config_widgets.py`, `common/__init__.py` | `ColumnPicker` (3.10) |
| `qt/widgets/nodes/Audit/_base.py` | `AuditContentMixin`, `AuditNode` (3.8, 3.9) |
| `qt/widgets/nodes/__init__.py` | import `AuditNodes`; add `"Audit._base"`, `"Audit.benford_chart"` to `_LAZY_HELPER_MODULES` (the five specs are added in each node's own step) |
| `tests/unit/test_audit_common.py` | 7.1 |

Done when: `& $PY -m pytest tests\unit\test_audit_common.py tests\unit\test_node_titles.py -q` passes; `& $PY -c "from trigger_designer.core.node_configuration import NodeTypes, AuditNodes; print(NodeTypes.AUDIT, list(AuditNodes))"` prints the family; `& $PY -c "import sys, trigger_designer.core.audit.common as c; assert not [m for m in sys.modules if m.startswith('qtpy')]"` exits 0.

**Step 2 - Duplicates** (commit `Add Duplicates audit node`). Create `core/audit/duplicates.py` (`DuplicatesParams`, `criteria`, `validate`, `run_duplicates`), `qt/widgets/nodes/Audit/duplicates.py`, the spec dict (3.11), tests `test_audit_duplicates.py`, `test_audit_nodes.py` (Duplicates cases), `tests/ui/test_audit_docks.py` (Duplicates cases). Node file skeleton (all five nodes follow it; only the names, sockets and `create_layout` change):

```python
@register_node(AuditNodes.DUPLICATES, NodeTypes.AUDIT)
class TriggerNode_Duplicates(AuditNode):
    icon = "node_unique"
    node_code = AuditNodes.DUPLICATES
    node_title = "Duplicates"
    node_type = NodeTypes.AUDIT
    content_label_objname = "trigger_node_duplicates"
    style = {}

    def __init__(self, scene) -> None:
        super().__init__(scene, inputs=[1], outputs=[3, 3, 1], output_text=["D", "U", "S"])

    def initInnerClasses(self) -> None:
        self.content = DuplicatesContent(self)
        self.grNode = TriggerGraphicsNode(self)
        self.content.evaluate.connect(self.onInputChanged)
        self.param = []

class DuplicatesContent(QDMNodeIconContentWidget, TriggerChangeHandler, AuditContentMixin):
    ...                                        # header exactly as in 3.8
    def build_result(self):                    # live path: same function the generated code calls
        return run_duplicates(self.incom_data, self.params())
    def output_variable_names(self):
        return [self.duplicates_var, self.unique_var, self.summary_variable_name]
    def exceptions_var_name(self):
        return self.duplicates_var
    def get_code(self) -> str:
        return self.audit_code("duplicates", "run_duplicates", "DuplicatesParams", self.output_variable_names())
    def create_layout(self, dock_layout):      # per the dock table in 4.1
        self._bindings.clear()
        if self.incom_data is None:
            dock_layout.addWidget(EmptyStateLabel()); return
        cols = list(self.schema())
        ...                                    # one ConfigSection per row of the table; bind() each control; _mark(section)
        dock_layout.addStretch()
        self._apply_visibility()
```

Done when: `& $PY -m pytest tests\unit\test_audit_duplicates.py tests\unit\test_audit_nodes.py tests\ui\test_audit_docks.py -q -k "duplicates or Duplicates"` passes; palette check: `& $PY -c "from trigger_designer.core.node_configuration import *; import trigger_designer.qt.widgets.nodes; print(NODE_REGISTRIES[NodeTypes.AUDIT])"`.

**Step 3 - Gaps** (commit `Add Gaps audit node`): `core/audit/gaps.py`, `Audit/gaps.py` (sockets `outputs=[3, 1]`, `["G", "S"]`; icon `node_count`), spec, tests. Done when the same three test files pass with `-k gaps`.

**Step 4 - Risk Filters** (commit `Add Risk Filters audit node`): `core/audit/risk_filters.py`, `Audit/risk_filters.py` (`outputs=[3, 3, 1]`, `["F", "N", "S"]`; icon `node_filter`), kind `text` in the mixin, spec, tests.

**Step 5 - Benford** (commit `Add Benford audit node`): `core/audit/benford.py`, `Audit/benford_chart.py`, `Audit/benford.py` (`outputs=[3, 1, 3]`, `["T", "S", "D"]`; icon `node_graph`), kind `digitlist` in the mixin, spec, tests. `Benford.on_result(result)` stores `self.chart_data = result.extras["chart"]` and `self.test_summary = TestSummary.from_summary_frame(result.frames[1].collect(), ...)`.

**Step 6 - Sample** (commit `Add Sample audit node`): `core/audit/sampling.py`, `Audit/sample.py` (`outputs=[3, 3, 1]`, `["S", "N", "L"]`; icon `node_split`), spec, tests. `build_result()` passes `live=True`; `get_code()` uses `audit_code("sampling", "run_sample", "SamplingParams", ...)` (the generated call has no `live` argument, so Run always draws).

**Step 7 - fixtures, E2E and benchmarks** (commit `Add audit ledger fixture, golden workflows and performance test`): `tests/support/audit_ledger.py` (7.5), `tests/e2e/test_audit_workflows.py`, goldens under `tests/e2e/fixtures/expected/audit_*.csv` (generate once with `$env:TRIGGER_UPDATE_E2E_GOLDENS="1"`, review the diff, unset), `tests/benchmarks/test_audit_perf.py`, `tests/unit/test_audit_perf_smoke.py`.

**Step 8 - docs** (commit `Document audit nodes`): add five rows to `docs/NODE_REFERENCE.md` (Audit family, op id, inputs/outputs, settings keys); no other doc.

Final gate (all steps): `& $PY -m pytest tests\unit tests\e2e -q` -> at least 334 + new / 20 + new passing; `& $PY -m pytest tests\ui -q` -> the same 27 baseline failures and no new ones; manual smoke of brief 3.7 step 14 for each node (drop unwired -> Run completes; wire File Input -> Run; save -> reload -> Run).

---

## 6. Edge cases per node

All numeric reading goes through `amount_expr` (text cleaned: `,`, spaces, `$ £ €` removed, `(x)` = negative; `strict=False`; unreadable -> null) and all dates through `date_expr`. **Null** cells are never counted as unreadable; **present but unreadable** cells are counted in `unparseable_rows` and raise `TD-AUDIT-102` (`warn`).

| Case | Duplicates | Gaps | Benford | Sample | Risk Filters |
|---|---|---|---|---|---|
| null cells | null key part -> row is never a duplicate (counted in `skipped_rows`); null amount/date in near mode -> skipped | null number/date -> ignored (not unreadable) | null/unreadable amount not tested | null amount: never sampled by mus/stratified; key nulls sort last | null cell fires nothing |
| zero | zero amounts match normally | number `0` is a valid sequence value | never tested (also `< min_abs_amount`) | mus: ineligible (listed in Not sampled); stratified: first stratum | `cents > 0` required for round amount; 0 is not round |
| negatives | `(25)` and `-25` read as -25; percent tolerance uses `|x|` | n/a | `|x|` is used | mus/stratified use `|x|` | round/just-below use `|x|` |
| text in numeric column | unreadable -> skipped + warning | unreadable sequence -> `unparseable_rows` | skipped + warning | unreadable -> never sampled (mus/stratified) | unreadable -> no fire + warning |
| identical values everywhere | one group of N | one number repeated: 1 duplicate row, 0 gaps | one digit holds 100 %: `nonconforming` | tied key -> whole-frame tie-break sort (identical rows interchangeable) | all flagged or none |
| population 0 | all outputs empty, Summary population 0, `exception_rate` null, status `pass` | 0 findings, `series 0` | `n == 0` -> `warn`, `TD-AUDIT-101` | empty sample, log `population_rows 0` | empty Flagged, status `pass` |
| population 1 | one row, never a duplicate | no gap possible | `n = 1` -> `warn` (too few) | `n` capped to 1, `TD-AUDIT-103` if more asked | works |
| ties | rows with the same amount tie in sort -> row index breaks ties (deterministic) | n/a | n/a | canonical order ties broken by other columns; MUS ties by canonical order | n/a |
| huge cardinality | near mode scales O(N log N); `over(keys)` needs key memory (3.12) | one row per gap regardless of its size; 1,000,000 distinct values 0.45 s | <= 90 groups | Floyd is O(n) in the sample size; unique key keeps memory small | row-wise |
| unicode | keys compared as given; `ignore_case` uses `str.to_lowercase()` (Unicode simple case); no normalisation (NFC/NFD differences are different keys) | prefix may be any text; digits are ASCII prefix may be any text; digits per note (a) | n/a | strings sort by UTF-8 bytes, locale independent | keywords/values lower-cased with the same function; literal match |
| time zones | `Datetime` with a zone -> the calendar date **in that zone** (verified: 23:30 UTC = 2024-03-03 in Asia/Kolkata) | same | n/a | n/a | same; weekend/holiday decided on the zoned date |
| fiscal calendars | **unsupported**: no 4-4-5 or 52/53-week years; Risk Filters has one period-end date; Gaps date mode uses the Gregorian calendar |  |  |  |  |

Additional decisions: (a) Gaps `\d` is the regex digit class, which also matches non-ASCII digits; they parse through `cast(Int64)` and fail to `null` -> unreadable (no crash). (b) A Float column holding `1e16` or larger casts to `"1e+16"` and is unreadable as a sequence. (c) A CSV amount like `1.234,50` (European) is not supported: it reads as unreadable (`TD-AUDIT-102`), never as a wrong number. (d) Duplicate column names cannot occur in a Polars frame. (e) `Datetime` without a zone uses its own date. (f) `Date` columns read by Excel arrive as `Date` and pass through unchanged.

---

## 7. Test plan

Layers per the brief: Qt-free logic in `tests/unit` (no widgets), node classes in `tests/unit/test_audit_nodes.py`, docks in `tests/ui`, files in `tests/e2e`, timing in `tests/benchmarks`. Hand-computed values are inline; expected numbers equal the verified references in section 4. Property tests are seeded loops (hypothesis is not installed): use `random.Random(20260101)` only for `.random()`/`.randint()` and keep the cases small.

### 7.1 `tests/unit/test_audit_common.py`

* `test_core_audit_imports_no_qt`: import every `core/audit/*.py` module in a subprocess (`sys.executable -I -c`) and assert no `qtpy`/`PyQt6` in `sys.modules`.
* `test_amount_expr_reads_accounting_text`: `["1,234.50", " (500) ", "$5", "€7", "abc", None, "-3"]` -> `[1234.5, -500.0, 5.0, 7.0, None, None, -3.0]`; non-String dtype passes through `cast`.
* `test_date_expr`: ISO string, `03/04/2024` with `%d/%m/%Y` -> 2024-04-03, `"2024-03-02 14:05:00"` -> 2024-03-02, `Datetime` UTC 23:30 converted to `Asia/Kolkata` -> 2024-03-03, garbage -> null.
* `test_parse_lists`: `parse_number_list("1000, 10000")`, `parse_size_list("20, 20, all") == [20, 20, -1]`, `"20, x"` raises `ValueError`, `""` -> `[]`.
* `test_audit_config_error_message_starts_with_code`: `str(e).startswith("TD-AUDIT-001: ")`, attributes set.
* `test_params_round_trip_and_unknown_keys`: `from_dict(to_dict()) == params`; unknown keys ignored; missing keys default; list defaults are not shared between instances.
* `test_summary_frame_columns_and_order`: the 11 base columns in order, extras after, dtypes as 3.6; `warn_unreadable` turns `pass` into `warn` with `TD-AUDIT-102` and keeps `fail`.
* `test_test_summary_round_trip`: `TestSummary.from_dict(ts.to_dict()) == ts`; `from_summary_frame` fills `details` with extras only; class is not collected by pytest (`TestSummary.__test__ is False`).

### 7.2 Duplicates (`test_audit_duplicates.py`)

* Fixture and expected values: the 4.1 table (four settings rows, asserting `dup_count`, `dup_group_id`, Unique height, Summary fields).
* `test_ids_are_dense_and_ordered_by_first_appearance`; `test_unique_plus_duplicates_partition_the_input` (heights add up; row sets disjoint; `dup_count == group size` computed independently with a Python `Counter`) over 200 seeded random frames of 1-30 rows.
* `test_near_tolerance_boundary`: amounts `100.00` and `100.50` with tolerance `0.5` group; `100.51` does not (float noise guarded by `1e-9`); percent mode: `100` vs `101` at 1 % group, `100` vs `101.1` not.
* `test_near_window_boundary`: dates 3 days apart group at window 3, 4 days do not; a chain `d, d+3, d+6` groups all three (documented chaining).
* `test_unreadable_and_null_keys`; `test_reserved_column_error` (`TD-AUDIT-005`); `test_validation_codes` (each row of the 4.1 validation table -> its code, via `pytest.raises(AuditConfigError)` and `.code`).
* `test_trim_and_ignore_case_flags`; `test_population_0_and_1`.

### 7.3 Gaps (`test_audit_gaps.py`)

* The 4.2 reference cases (a)-(d) with exact row dictionaries and Summary fields.
* `test_gaps_reconstruct_the_sequence` (property): 200 seeded random sets of 1-40 integers in 1..200 (shuffled, with random repeats); expected set = `set(values) | union(range(from, to + 1) for each gap row)` equals `set(range(min, max + 1))`, and `sum(count of gap rows) == (max - min + 1) - len(set(values))`.
* `test_zero_padding_width_restored` (`JE-000123` -> output `JE-000124`), `test_separate_series_per_prefix_and_group`, `test_range_start_end_add_leading_and_trailing_gaps`, `test_huge_jump_is_one_row` (1 and 10,000,000 -> one row, `count 9,999,998`).
* `test_business_days_only` and `test_min_gap_days` per reference (c); `test_validation_codes`.

### 7.4 Benford, Sample, Risk Filters

`test_audit_benford.py`:
* `test_first_digit_vector`: the 13 values of 4.3 for `d1` and `d2`.
* `test_first_digits_match_decimal_reference_on_random_amounts` (property): 20,000 seeded log-uniform amounts with 2 decimals, compare to the digits of `Decimal(repr(x))`; zero mismatches.
* `test_chi2_sf_reference_points`: the five critical values of 4.3 within `1e-9`; `chi2_sf(0, 8) == 1.0`; monotone decreasing.
* `test_table_matches_independent_reference`: the three datasets of 4.3 (counts, MAD, chi-square, p-value, z of first/second/last digit) with `pytest.approx(rel=1e-9)` against `benford_reference.reference` copied into the test; `proportion` sums to `1.0` and `expected_proportion` to `1.0` within `1e-12` (property for 50 random count vectors).
* `test_conformity_bands_are_pinned`: `MAD_BANDS == {1: (0.006, 0.012, 0.015), 2: (0.0012, 0.0018, 0.0022)}`; boundaries inclusive (`conformity(0.006, 1) == "close"`, `0.0060001 -> "acceptable"`, `0.015 -> "marginal"`, `0.0151 -> "nonconforming"`).
* `test_run_benford_end_to_end_on_fixture_a`: amounts `d*1000+i` -> table counts equal the fixture; status `pass`; drill-down empty; `min_abs_amount` excludes rows (`amount 5` ignored), zero ignored, `"abc"` counted in `unparseable_rows` with `TD-AUDIT-102`; all-zero input -> `n == 0` warn `TD-AUDIT-101`; `n < 100` -> `warn`.
* `test_drill_down_returns_source_rows`: AP-like frame -> drill rows == rows whose digit is in `flagged`, with `benford_digits`; `drill_auto=False, drill_digits=[5]` -> only digit-5 rows; validation codes (digits 3 -> 004, drill digit 10 for `digits=1` -> 004).

`test_audit_sampling.py`:
* PRNG vectors of 4.4 (`SplitMix64(0)`, Floyd, systematic, `derive_seed`), MUS toy (positions, basis, interval, start).
* `test_sample_size_equals_requested` (property): for 100 seeded cases (population 1-300, `n` 1-400): random and systematic return `min(n, N)` distinct positions; MUS returns `min(n, eligible)` distinct items for random positive amounts including heavy-tailed ones (one item 10,000x the rest); stratified returns `sum(min(size, M_s))`.
* `test_seed_reproducibility`: same frame + params twice -> identical frames; seed 42 vs 43 -> different sets (for N=1000, n=50).
* `test_order_independence`: shuffle the input with 5 different seeds -> the same **set** of sampled rows for all four methods, both with a unique key and with the default (all columns, including a frame containing fully identical rows).
* `test_mus_certainty_items`: amounts `[5000, 120, 80, 300, 40, 60, 900, 20, 150, 330]`, `n=4` -> `sample_basis` `high_value` for 5000 and 900 and `interval` for the other two; a frame where one item is bigger than the whole rest still yields `n` distinct items; zeros and negatives: `[-100, 0, 50]` -> zero in Not sampled, `|-100|` eligible; no eligible -> `TD-AUDIT-010`.
* `test_selection_log_fields`: columns exactly `LOG_COLUMNS`; overall row values; stratified has `1 + k` rows; `algorithm == "td-sample-1"`; `TD-AUDIT-103` note when `n > N`; no timestamp column.
* `test_percent_size`: 10 % of 2,413 -> 242; `test_live_limit_returns_empty_for_big_input` (monkeypatch `LIVE_ROW_LIMIT = 10`); validation codes (strata sizes 2 values for 2 edges -> `009` message `Strata sizes: expected 3 values, found 2.`).

`test_audit_risk_filters.py`: the 4.5 fixture (scores, `risk_tests` strings, Summary counts), per-test isolation (switch one test on at a time -> only its rows), boundaries (`4,900` fires, `5,000` does not, `4,899.99` does not at 2 %), weights (weight 3 on `weekend` -> score 3), `effective_date_column` refinement, holiday and period-end validation (`TD-AUDIT-006`), case-insensitive keywords, `risk_tests == ""` never appears in Flagged, and `Flagged + Not flagged == input` rows.

### 7.5 Synthetic ledger generator (`tests/support/audit_ledger.py`, copy verbatim)

Deterministic (own SplitMix64, fixed seed, no library randomness). `make_ledger()` returns `Ledger(frame, planted)` with 2,413 rows: 2,013 `GL` rows (`je_number` `GL-000001..`, 6 digits) and 400 `AP` rows (`AP-0001..AP-0400`, 4 digits); all columns are text, as File Input would read them. Planted anomalies are on disjoint row ranges so every expected count below is exact.

```python
from __future__ import annotations
import datetime as dt
from dataclasses import dataclass, field
import polars as pl
LEDGER_SEED = 20260101
_MASK = (1 << 64) - 1
START, END = dt.date(2024, 2, 1), dt.date(2024, 3, 28)
HOLIDAY = dt.date(2024, 3, 29)
PERIOD_END = dt.date(2024, 3, 31)
DESCRIPTIONS = ("Office supplies", "Consulting fees", "Freight", "Software licence",
                "Utilities", "Travel", "Maintenance")
class _Rng:
    def __init__(self, seed: int) -> None:
        self.state = seed & _MASK
    def u(self) -> float:
        self.state = (self.state + 0x9E3779B97F4A7C15) & _MASK
        z = self.state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & _MASK
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & _MASK
        return ((z ^ (z >> 31)) >> 11) / float(1 << 53)
    def below(self, n: int) -> int:
        return int(self.u() * n)
@dataclass
class Ledger:
    frame: pl.DataFrame
    planted: dict[str, list[int]] = field(default_factory=dict)  # name -> 1-based row numbers
def _days(first: dt.date, last: dt.date) -> list[dt.date]:
    return [first + dt.timedelta(days=i) for i in range((last - first).days + 1)]
def make_ledger(seed: int = LEDGER_SEED) -> Ledger:
    rng = _Rng(seed)
    all_days = _days(START, END)
    weekdays = [d for d in all_days if d.weekday() < 5]
    weekend_days = [d for d in all_days if d.weekday() >= 5]
    def clean_amount(low_exp: float, span: float) -> float:
        while True:
            v = round(10 ** (low_exp + span * rng.u()), 2)
            cents = round(v * 100)
            if cents % 100_000 == 0 or 4900 <= v < 5000 or 9800 <= v < 10000:
                continue
            return v
    def row(i: int) -> dict:
        d = weekdays[rng.below(len(weekdays))]
        return {"ledger": "GL", "posting_date": d, "effective_date": d,
                "amount": clean_amount(1, 5), "vendor": f"V{rng.below(400):03d}",
                "invoice_no": f"INV-{i:05d}", "description": DESCRIPTIONS[rng.below(7)],
                "source": "Auto"}
    base = [row(i + 1) for i in range(2000)]          # index k -> row number k+1 before numbering
    P: dict[str, list[int]] = {}
    def plant(name: str, idxs: range, **fields_by_k) -> None:
        P[name] = [i + 1 for i in idxs]
        for k, i in enumerate(idxs):
            for f, fn in fields_by_k.items():
                base[i][f] = fn(k)
            if "posting_date" in fields_by_k and "effective_date" not in fields_by_k:
                base[i]["effective_date"] = base[i]["posting_date"]
    plant("weekend", range(100, 115), posting_date=lambda k: weekend_days[k % len(weekend_days)])
    plant("holiday", range(200, 204), posting_date=lambda k: HOLIDAY)
    plant("round", range(300, 320), amount=lambda k: float(1000 * (1 + (k * 7) % 40)))
    plant("just_below", range(400, 413), amount=lambda k: 4900 + 12.5 * k if k < 8 else 9800.0 + 40 * (k - 8))
    kw = ["Reversal of accrual"] * 4 + ["REVERSAL OF PRIOR PERIOD"] * 2 + ["Plug adjustment"] * 3
    plant("keyword", range(500, 509), description=lambda k: kw[k])
    plant("after_period", range(600, 607), posting_date=lambda k: dt.date(2024, 4, 2),
          effective_date=lambda k: dt.date(2024, 3, 28))
    plant("manual", range(700, 725), source=lambda k: "Manual")
    plant("triple", range(800, 801), posting_date=lambda k: weekend_days[0],
          amount=lambda k: 20000.0, source=lambda k: "Manual")
    def next_weekday(d: dt.date) -> dt.date:
        i = weekdays.index(d)
        return weekdays[i + 1] if i + 1 < len(weekdays) else weekdays[i - 1]
    copies: list[dict] = []
    def copy_of(i: int, **over) -> dict:
        c = dict(base[i]); c.update(over); return c
    for i in range(900, 910):                          # 10 exact pairs
        copies.append(copy_of(i))
    for i in (910, 911):                               # 2 exact triples
        copies += [copy_of(i), copy_of(i)]
    for i in range(920, 925):                          # 5 amount-shifted (+0.30)
        copies.append(copy_of(i, amount=round(base[i]["amount"] + 0.30, 2)))
    for i in range(930, 935):                          # 5 date-shifted (next weekday)
        copies.append(copy_of(i, posting_date=next_weekday(base[i]["posting_date"]),
                              effective_date=next_weekday(base[i]["posting_date"])))
    P["dup_sources"] = [i + 1 for i in list(range(900, 910)) + [910, 911] + list(range(920, 925)) + list(range(930, 935))]
    gl = base + copies                                  # 2024 rows
    for n, r in enumerate(gl, start=1):
        r["je_n"] = n
    missing = set(range(1000, 1010)) | {1500} | set(range(1800, 1803))
    gl = [r for r in gl if r["je_n"] not in missing]    # 2024 - 14 = 2010 rows
    pos = {r["je_n"]: i for i, r in enumerate(gl)}
    for a in (1100, 1200, 1300, 1400):                  # swap neighbours -> out of order
        i, j = pos[a], pos[a + 1]
        gl[i], gl[j] = gl[j], gl[i]
    repeats = []
    for n, num in enumerate((100, 200, 300), start=1):  # repeated numbers appended at the end
        r = row(5000 + n); r["je_n"] = num; repeats.append(r)
    gl += repeats                                       # 2013 GL rows
    ap = []
    for i in range(400):                                # Benford-violating ledger
        d = weekdays[rng.below(len(weekdays))]
        while True:
            v = round(5000 + 4800 * rng.u(), 2)
            if round(v * 100) % 100_000 != 0:
                break
        ap.append({"ledger": "AP", "je_n": i + 1, "posting_date": d, "effective_date": d,
                   "amount": v, "vendor": f"V{rng.below(400):03d}", "invoice_no": f"APINV-{i+1:04d}",
                   "description": DESCRIPTIONS[rng.below(7)], "source": "Auto"})
    out = []
    for r in gl:
        out.append({**r, "je_number": f"GL-{r['je_n']:06d}"})
    for r in ap:
        out.append({**r, "je_number": f"AP-{r['je_n']:04d}"})
    cols = ["je_number", "ledger", "posting_date", "effective_date", "amount", "vendor",
            "invoice_no", "description", "source"]
    frame = pl.DataFrame(
        {
            "je_number": [r["je_number"] for r in out],
            "ledger": [r["ledger"] for r in out],
            "posting_date": [r["posting_date"].isoformat() for r in out],
            "effective_date": [r["effective_date"].isoformat() for r in out],
            "amount": [f"{r['amount']:.2f}" for r in out],   # text, like a CSV read by File Input
            "vendor": [r["vendor"] for r in out],
            "invoice_no": [r["invoice_no"] for r in out],
            "description": [r["description"] for r in out],
            "source": [r["source"] for r in out],
        }
    ).select(cols)
    return Ledger(frame=frame, planted=P)
if __name__ == "__main__":
    L = make_ledger()
    print(L.frame.shape, {k: len(v) for k, v in L.planted.items()})
```

**Planted anomalies and exact expected results** (all verified by running the reference implementation on this generator):

| Test | Settings | Expected |
|---|---|---|
| Duplicates exact | keys `vendor, invoice_no, amount` | flagged **36**, groups **17** (10 pairs + 2 triples + 5 date-shifted pairs), Unique **2,377** |
| Duplicates near | keys `vendor, invoice_no`, amount absolute `0.50`, `posting_date` window `3` days | flagged **46**, groups **22**, Unique **2,367** |
| Gaps (prefixed, group `ledger`) | column `je_number` | Gaps rows **13**: gap `GL-001000..GL-001009 (10)`, `GL-001500 (1)`, `GL-001800..GL-001802 (3)`; duplicate `GL-000100, GL-000200, GL-000300` (count 2 each, `source_row` 100, 200, 300); out of order `GL-001100, 001200, 001300, 001400` (`source_row` 1091, 1191, 1291, 1391) and the three repeats (`source_row` 2011, 2012, 2013). Summary: `series 2, gap_ranges 3, missing_items 14, duplicate_values 3, out_of_order_rows 7, exception_rows 13, population_rows 2413`, status `fail` |
| Gaps date | `posting_date`, calendar | **2** ranges: `2024-03-24 (1)`, `2024-03-30..2024-04-01 (3)`; `business_days_only`: **1** range `2024-04-01 (1)` |
| Benford first digit | `amount`, GL only (2,013 rows) / AP only (400) / all | GL MAD `0.003594` `close`, status `pass`, no drill rows; AP MAD `0.155327` `nonconforming`, status `fail`, flagged `5, 6, 7, 8, 9`, drill **400** rows; all MAD `0.028145` `nonconforming`, drill **1,032** rows. Full numbers in 4.3 |
| Sample | key `je_number`, seed 42 | random n=100 -> 100 + 2,313; systematic n=100 interval `24.13`; MUS n=50 interval `3468934.663799994`, sample value `26,253,624.04`; stratified edges `[1000, 10000]`, sizes `[20, 20, -1]` -> strata `828 / 755 / 830`, sample **870**. Shuffled input -> same sampled set |
| Risk Filters | all seven tests (4.5 ledger settings) | flagged **94**, not flagged **2,319**, per-test counts `16, 4, 21, 13, 9, 7, 26`, `flagged_two_or_more 1`, `total_score 96`, max score 3 (`GL-000801`) |

### 7.6 UI tests (`tests/ui/test_audit_docks.py`)

Pattern: brief 9.3 (`ConfigDock`, `updateConfig([node.grNode])`, `history.storeHistory("Baseline")`, then edit/undo/redo, `force=True`). Source double + `Edge` as in brief 9.2. One module, parametrized helpers; names:

* `test_<node>_dock_builds_without_error`: call `node.content.create_layout(QVBoxLayout(QWidget()))` directly (the dock swallows exceptions) for each of the five nodes, with and without input (`EmptyStateLabel` when none); every section has `_undo_composite`.
* `test_duplicates_mode_switch_shows_near_section`: select "Near" -> `near_section.isVisible()`; undo -> hidden and `mode == "exact"`.
* `test_duplicates_edit_reevaluates_and_undoes`: tick two key columns -> `node.value[0]["data"].collect().height == 5` on the 4.1 fixture; `history.undo()` -> `key_columns == []`, checkboxes unticked, node invalid with tooltip starting `TD-AUDIT-001`; redo restores; exactly **one** history entry per click (no double recording), tolerance spin bursts merge into one step.
* `test_count_button_sets_test_summary`: click the button (find by `accessibleName == "Count exceptions now"`) -> `content.test_summary.exception_rows == 5` and the label shows the message; the history stack is unchanged.
* `test_gaps_mode_hides_options`: Date mode hides "Also report" and "Expected range" and shows "Dates"; optional-int spin special value -> `range_start is None`.
* `test_benford_chart_paints_and_tooltips`: `BenfordChartWidget` with the fixture-A data: `grab()` returns a non-null pixmap, `set_data(None)` shows the empty state, a simulated mouse move over bar 1 sets a tooltip containing `Digit 1: observed 30.1%`; flagged bars use the `danger` token (compare the pixel colour at a bar of AP data to `get_theme_manager().color("danger")`).
* `test_benford_drill_checklist_enabled_only_when_manual`.
* `test_sample_method_switch_and_strata_fields`: choosing Stratified hides Size and shows Strata; typing `1000, 10000` and `20, 20, all` commits after the 300 ms debounce (`qtbot.waitUntil`), producing `band_edges == [1000.0, 10000.0]`, `band_sizes == [20, 20, -1]`; half-typed `1000,` keeps the previous value; seed button changes the seed in one undo step.
* `test_risk_switch_enables_options` (header checkbox enables the body rows; switching off keeps values), `test_risk_weight_dict_undo` (weight change undone restores the dict).
* `test_audit_node_palette_and_menu`: `NODE_REGISTRIES[NodeTypes.AUDIT]` has five entries; titles equal the lazy spec titles; the Shift+A menu contains an "Audit" submenu with five actions.

### 7.7 Node/codegen tests (`tests/unit/test_audit_nodes.py`)

For each node (brief 9.2 pattern with a `Source` double):

* `test_live_value_and_generated_code_agree`: `exec(node.get_code(), {"__name__": "__main__", "pl": pl}, ns)` with the upstream variable preseeded; every output frame (collected, summary eager) `.equals` the live frame.
* `test_unwired_node_defines_every_output_variable`.
* `test_misconfigured_node_raises_in_run_and_tooltips_live`: empty settings -> live `eval()` returns `None`, node invalid, tooltip starts `TD-AUDIT-001`; the generated code raises `AuditConfigError`.
* `test_state_round_trips_through_serialize`: non-default settings -> `serialize()` -> new node `deserialize()` -> equal `params()`; `deserialize({})` gives defaults; **`.tds` round trip** via `scene.saveToFile` / `fileLoad`.
* `test_op_ids_and_titles`: `node.serialize()["op"] == "audit.duplicates"` etc.; `get_class_from_op(op)` resolves; spec title/icon equal class attributes.
* `test_after_execution_sets_test_summary`: call `content.after_execution({summary_var: summary_df})` -> `test_summary.test_id == f"audit.duplicates#{node.id}"`, `exceptions_var == duplicates_var`; Sample builds its summary from the log (`details["selection_log"]`, `parameters["seed"] == 42`).
* `test_declared_outputs_survive_pruning`: `workflow_execution_mixin._declared_output_variable_names(node)` lists every output variable after `eval()`.

### 7.8 E2E (`tests/e2e/test_audit_workflows.py`, marker `e2e` is automatic)

Build each workflow in code (brief 9.4 skeleton: File Input -> audit node -> one File Output per socket, saved as `.tds` in `tmp_path`, reloaded in a fresh `TriggerSubWindow`, `run_workflow_and_wait`, outputs read with `read_frame`). The ledger is written once per module (`tmp_path_factory`) with `make_ledger().frame.write_csv(...)`; `ledger_gl.csv` and `ledger_ap.csv` are the two ledger subsets for Benford. Tests (exact numbers from 7.5):

* `test_duplicates_exact_workflow` / `test_duplicates_near_workflow`: output files have 36 / 46 rows (Duplicates), 2,377 / 2,367 rows (Unique), Summary `exception_rows`, `groups`, status `fail`; `dup_group_id` has 17 / 22 distinct values and `dup_count` equals the group size; golden `audit_dup_exact_summary`, `audit_dup_near_summary` (Summary CSVs).
* `test_gaps_workflow` (grouped by `ledger`): 13 rows, the exact rows listed in 7.5; golden `audit_gaps_table`; `test_gaps_date_workflow`: 2 rows; business days: 1 row.
* `test_benford_workflows`: GL file -> `close`, status `pass`; AP file -> `nonconforming`, 400 drill rows, `flagged_digits == "5, 6, 7, 8, 9"`; golden `audit_benford_gl_table`.
* `test_sample_workflows_are_reproducible`: run each of the four methods twice (two separate runs) and on a row-shuffled CSV; sampled `je_number` multisets identical; sizes 100 / 100 / 50 / 870; log `seed == 42`, `algorithm == "td-sample-1"`; golden `audit_sample_log_random`.
* `test_risk_filters_workflow`: 94 / 2,319; the per-test counts; golden `audit_risk_summary`.
* `test_audit_workflow_save_reload_roundtrip`: settings of all five nodes identical after reload; a second Run gives identical Summary frames.
* Each test asserts `_assert_run_clean` semantics (every node has results, none invalid) and that `no_modal_dialogs["warnings"] == []`.

### 7.9 Performance

* `tests/benchmarks/test_audit_perf.py` (`--run-benchmarks`): 1,000,000 synthetic rows built in memory (`numpy.random.default_rng(1)`, columns `je` text `JE-0000000..`, `vendor` text of 20,000 distinct values, `inv` 50 values, `amount` text log-normal, `date` text over 28 days, `desc`, `src`). Each of the following must finish within **10 s** (measured on the development machine, 2026-10-21: in parentheses): duplicates exact (0.28 s), near with amount tolerance + 3-day window (0.47 s), gaps prefixed (0.45 s), Benford first-two (0.10 s), sample random with unique key `je` (0.05 s), sample MUS with unique key (0.64 s), sample random with default all-columns key (0.21 s), risk filters with five tests (0.57 s). Assert the elapsed time and one cheap result (e.g. `exception_rows > 0`).
* `tests/unit/test_audit_perf_smoke.py` (always on): the same eight calls at 100,000 rows with a **3 s** total budget (guards accidental quadratic plans).

---

## 8. Acceptance checklist

- [ ] `AUDIT` family appears as a palette tab and a Shift+A submenu with Duplicates, Gaps, Benford, Sample, Risk Filters; titles/icons equal their specs (`test_node_titles`-style test passes).
- [ ] Op ids `audit.duplicates|gaps|benford|sample|risk_filters` persist in `.tds`; old files unaffected; no `V1_OPCODE_TO_OP` edit.
- [ ] Each node: unwired Run is fine; misconfigured Run fails with a `TD-AUDIT-NNN` message; live tooltip shows the same text.
- [ ] Live outputs equal generated-code outputs (7.7) for every node.
- [ ] Summary frames have the 11 base columns in order; `TestSummary.from_summary_frame` parses all of them; `content.test_summary` is set after Run (and after Count / live for Benford and Sample).
- [ ] Duplicates, Gaps, Benford, Sample, Risk Filters reproduce every verified number in section 4 and the E2E table in 7.5.
- [ ] Sample: same rows + seed -> identical sample for shuffled input (all four methods); log carries seed, interval/start, population and sample size, algorithm id.
- [ ] Docks follow the design system: shared widgets only, no inline `setStyleSheet`, no new QSS, controls 30 px, tooltips + accessible names on icon buttons, 300 ms debounce on text; undo/redo restores widgets and results; one history entry per user edit.
- [ ] `core/audit/*` imports no Qt; no new dependency; ruff clean on touched files; `tests\unit` and `tests\e2e` green; `tests\ui` shows only the 27 baseline failures; benchmark within budget.

## 9. Verification commands

```powershell
$PY = ".venv\Scripts\python.exe"
& $PY -m ruff format <touched files>
& $PY -m ruff check  <touched files>
& $PY -m pytest tests\unit\test_audit_common.py tests\unit\test_audit_duplicates.py tests\unit\test_audit_gaps.py `
    tests\unit\test_audit_benford.py tests\unit\test_audit_sampling.py tests\unit\test_audit_risk_filters.py `
    tests\unit\test_audit_nodes.py tests\unit\test_audit_perf_smoke.py tests\unit\test_node_titles.py -q   # unit layer
& $PY -m pytest tests\ui\test_audit_docks.py -q                                                           # ui layer (new file)
& $PY -m pytest tests\e2e\test_audit_workflows.py -q                                                      # e2e layer
& $PY -m pytest tests\unit -q ; & $PY -m pytest tests\e2e -q                                              # regression: >= 334 / 20 passing
& $PY -m pytest tests\ui -q                                                                               # same 27 baseline failures only
& $PY -m pytest tests\benchmarks\test_audit_perf.py --run-benchmarks -q                                   # budget 10 s per case
$env:TRIGGER_UPDATE_E2E_GOLDENS="1"; & $PY -m pytest tests\e2e\test_audit_workflows.py; Remove-Item Env:TRIGGER_UPDATE_E2E_GOLDENS   # regenerate goldens, then review git diff
```

Numeric re-verification script (standalone, plain `math`, reproduces the 4.3 reference table): `uv run --no-sync --project . python benford_reference.py` using the `reference(counts, digits)` function of 4.3.

## 10. Pitfalls

1. **`set_setting` must emit `evaluate` itself**: a merged undo push skips `redo()` (brief 6.1), so without the explicit `evaluate.emit()` a burst edit would not recompute.
2. **Set `incom_data` before validating** in `processInputs`; otherwise a config error leaves `incom_data = None`, the dock shows the empty state and the user cannot fix the setting.
3. **`create_layout` failures are silent** (blank panel); every UI test calls it directly.
4. **`ColumnChecklist` / `SegmentedControl` emit their own signals**; never also bind the inner buttons (`_undo_composite` on the sections prevents the sweep from doing it).
5. **`SegmentedControl.value()` returns the label text**, not the key: always map through `opts["options"]`.
6. **`evaluate = Signal()` must be declared on the concrete content class**; a Signal on the mixin is never created.
7. **Polars specifics** (all verified): `log10(1000.0) != 3.0` exactly; `is_in(pl.Series)` of the same dtype is deprecated (use a Python list or a join); `str.to_date` needs `exact=False` to ignore trailing time text; `join(..., maintain_order="left")` is required to keep input order; `pl.Utf8` is an alias, write `pl.String`; `.collect(engine="streaming")` silently falls back to in-memory for window/sort plans.
8. **The Gaps columns are literally named `from` and `to`** (valid Polars names, but SQL keywords): a downstream Formula/Filter must quote them (`"from"`). Writing them to CSV is fine.
9. **`get_code` must stay pure**: no timestamps, no counters, no `random`; the Selection log has no date for this reason.
10. **Do not import `trigger_designer.main`** anywhere (loguru side effects, brief 1.2).
11. **`TestSummary` named like a test**: keep `__test__ = False`; never rename the module to something pytest collects from `src`.
12. **The brief's `getSocketValue` first-match quirk** does not affect these single-input nodes; do not "fix" it here.
13. **Sample with the default key sorts the whole frame in memory**; the dock tooltip says so and the E2E uses a key. Do not add a hash-based shortcut: its stream is not stable across Polars versions.
14. **Do not let `ColumnPicker` filter by dtype**: CSV amounts are `String`.
15. **Plan 02 owns `core/audit/__init__.py`**: do not create or edit it unless plan 02 has not landed (then leave it empty). Use full-path imports (`from trigger_designer.core.audit.duplicates import ...`).
16. **A test that calls `TestSummary.from_summary_frame` on a frame with 0 rows** raises; `after_execution` guards `height == 1`.

## 11. Interfaces to other plans

**Plan 02 (audit trail / run log).**
* Reads `getattr(node.content, "test_summary", None)` in `node_finished`; this plan sets it in `after_execution` (before `nodeFinished` is delivered), so the recorder stores `dataclasses.asdict(TestSummary)` under `nodes[].test_summary`.
* **Seed:** Sample's seed is in `settings["seed"]` (so plan 02's `extract_seed` finds the key `seed`, brief/02 3.10) **and** in `TestSummary.parameters["seed"]`. Reproducing a sample needs: the input rows, `parameters` (all of `SamplingParams`), and `details["selection_log"]` (list of dict rows with `algorithm`, `interval`, `start`, `high_value_items`, population and sample size/value). The `algorithm` id `td-sample-1` is the version of the draw procedure.
* Generated code imports `trigger_designer.core.audit.<module>`; plan 02's `code_sha256` therefore hashes only the short call, so the recorder must also store the app version (it does, `app_version`): the algorithm is pinned by the app version plus `algorithm`.
* Row counts: `rows_out` for audit nodes can be taken from the Summary (`population_rows`, `exception_rows`) without extra counting.

**Plan 06 (workpaper).** Consumes the Summary frame: base columns `test_name, criteria, parameters (JSON string), status, code, message, population_rows, population_value, exception_rows, exception_value, exception_rate` - a superset of what 06 reads (`06-workpaper-export.md:1041-1043`), so no adapter is needed; 06 may also use `population_value` / `exception_value`, which 06 currently computes itself. `criteria` is the human sentence for the workpaper's "Criteria applied" cell. Exceptions input = socket 0 of Duplicates / Gaps / Risk Filters (Flagged), socket 2 of Benford (Drill-down), socket 0 of Sample.

**Plan 03 (plain-language errors).** Plan 03 registers the codes in the `Error codes` table below (exception text is `TD-AUDIT-NNN: <message>`, `exc_type == "AuditConfigError"`; errors have severity `error`, 101-103 are warnings that travel in the Summary `code` column / log `note`, never as exceptions). The literal prefix `TD-AUDIT-` is kept (brief 10.2 names the area `TST`; plan 03 maps without renaming).

**Plan 09 (foundations).** This plan depends on plan 09 F-B (shared `ExecutionResult` fields and hook stubs): it only fills `content.test_summary` inside `after_execution` as designed in 3.6/3.8 and adds no executor field. Step 1 starts after F-B has landed.

**Plan 05 (profile) / 07 (shaping).** No dependency. Plan 08 (CLI) gets the nodes for free: the generated code needs no GUI, and `AuditConfigError` messages carry their codes for the exit-code contract (any `TD-AUDIT-0xx` error -> exit code 1, "node failed").

### Error codes (table for plan 03's catalogue)

| Code | Sev | Title | Message template | Fix hint |
|---|---|---|---|---|
| TD-AUDIT-001 | error | A required column is not chosen | `Choose the {label} column.` | Open the node and choose a column. |
| TD-AUDIT-002 | error | A chosen column is not in the input | `Column '{col}' is not in the input data. Pick it again.` | Pick the column again; the input data changed. |
| TD-AUDIT-003 | error | Column holds nested values | `Column '{col}' holds nested values and cannot be used for this test.` | Choose a text or number column. |
| TD-AUDIT-004 | error | A number is out of range | `{label} must be {rule}.` | Correct the highlighted number. |
| TD-AUDIT-005 | error | Output column name already exists | `The input already has a column named '{name}', which this node adds. Rename it first.` | Rename that input column. |
| TD-AUDIT-006 | error | Not a valid date | `'{text}' is not a date. Use YYYY-MM-DD.` | Type dates as YYYY-MM-DD, one per line. |
| TD-AUDIT-007 | error | Date format not supported | `Date format '{fmt}' is not supported.` | Pick one of the listed date formats. |
| TD-AUDIT-008 | error | No risk test switched on | `Switch on at least one risk test.` | Tick at least one risk test. |
| TD-AUDIT-009 | error | List or strata settings invalid | `{label}: {detail}.` | Fix the list: numbers separated by commas. |
| TD-AUDIT-010 | error | No readable amount to sample | `No row has a readable amount in '{col}', so a value-based sample cannot be drawn.` | Choose an amount column that contains numbers. |
| TD-AUDIT-101 | warning | Too few rows for a reliable result | `Only {n:,} rows were tested; at least {min:,} are needed for a reliable result.` | Test more data or accept the lower reliability. |
| TD-AUDIT-102 | warning | Some values could not be read | `{n:,} values could not be read as {kind} and were skipped.` | Check the column for text that is not a number or date. |
| TD-AUDIT-103 | warning | Sample larger than population | `Requested {k:,} but only {n:,} rows exist; the whole population was selected.` | Lower the requested size. |

### Generated-code imports (for plan 08's headless policy)

Each node's generated code contains exactly `import polars as pl` plus the one import line below, and nothing else from this package (all names are stable public API of the module):

| Node | Import line |
|---|---|
| Duplicates | `from trigger_designer.core.audit.duplicates import DuplicatesParams, run_duplicates` |
| Gaps | `from trigger_designer.core.audit.gaps import GapsParams, run_gaps` |
| Benford | `from trigger_designer.core.audit.benford import BenfordParams, run_benford` |
| Sample | `from trigger_designer.core.audit.sampling import SamplingParams, run_sample` |
| Risk Filters | `from trigger_designer.core.audit.risk_filters import RiskParams, run_risk_filters` |

Call shape: `Params.from_dict({...}).` then `run_x(<var>, params).for_run()`; no other attribute of these modules is used.

### Packaging

The generated code imports `core.audit.*` by string; packaging is **provided by plan 09 F-G**, which globs every module of `core/audit` into the hidden imports. This plan does not edit `trigger.spec`, `pyproject.toml` or `uv.lock` itself.
