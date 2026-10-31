# 07 - Shaping nodes (Record ID, Select Records, Find and Replace, Date Helper, Pivot, Unpivot, Reconcile, Fuzzy Match, Window, Text to Columns, Multi-Field Formula, SQL Query, Comment)

Plan author: plan 07 of 8. Read `docs/plan/00-codebase-brief.md` first (shared facts, node recipe 3.7, testing guide 9). This plan adds **13 nodes for 12 features** (Pivot and Unpivot are two nodes). Everything below was verified on 2026-10-21 against `main` @ `71b4041` with Polars 1.44.2, DuckDB 1.5.5, Python 3.13.12. Code blocks marked "verified" were run: 127 core unit tests (section 7) passed against them, and the Qt scaffolding (3.4) was run headless through eval, codegen, dock edit, undo/redo, list add/undo, serialize and forced dock rebuild.

## Table of contents

1. [Goal, non-goals, priorities and order](#1-goal-non-goals-priorities-and-order)
2. [Current state (verified)](#2-current-state-verified)
3. [Shared foundations](#3-shared-foundations)
4. [The nodes](#4-the-nodes) (4.1 Record ID, 4.2 Select Records, 4.3 Find and Replace, 4.4 Date Helper, 4.5 Pivot, 4.6 Unpivot, 4.7 Comment, 4.8 Reconcile, 4.9 Window, 4.10 Text to Columns, 4.11 Fuzzy Match, 4.12 Multi-Field Formula, 4.13 SQL Query)
5. [Ordered implementation steps](#5-ordered-implementation-steps)
6. [Edge cases per node](#6-edge-cases-per-node)
7. [Test plan](#7-test-plan)
8. [Acceptance checklist](#8-acceptance-checklist)
9. [Verification commands](#9-verification-commands)
10. [Pitfalls](#10-pitfalls)
11. [Interfaces for plans 02, 03, 06, 08 and 09](#11-interfaces-for-plans-02-03-06-08-and-09)
12. [TD-SHAPE code catalogue](#12-td-shape-code-catalogue-plan-03-registers-the-codes-in-this-table)

---

## 1. Goal, non-goals, priorities and order

**Goal.** Give audit and finance users the missing "shape the data" tools of a modern prep workflow, as ordinary nodes that follow the brief's recipe: numbered rows, top-N sampling, text cleanup, date and fiscal logic, pivot/unpivot, tolerance reconciliation, fuzzy matching, window maths, text splitting, bulk formulas, read-only SQL, and canvas comments.

**Non-goals.** No change to the executor, run log, error translation, File Input/Output, or the existing nodes' behaviour (Running Total stays; Window supersedes it only for new work). No fix of `getSocketValue` itself (new nodes avoid it, 3.4). No new `NodeTypes` family. No new dependency (DuckDB, Polars, sqlglot, pyarrow are installed; `rapidfuzz` is not and is not needed: DuckDB has `jaro_winkler_similarity` and `levenshtein`). No icon art (existing icon ids are reused). No cancellation of long computations (brief fact 4).

### 1.1 Priority table (audit/finance reasoning)

| # | Node (title) | Op id | Priority | Why |
|---|---|---|---|---|
| A | Record ID | `preparation.record_id` | **P1** | Every workpaper cites rows ("item 1432"); stable numbers are the base of sampling and exception referencing. Tiny, safe. |
| K | Select Records | `preparation.select_records` | **P1** | Largest-N / first-N / range selection is the standard judgemental-sample and "top 25 items" test; second output keeps the remainder for completeness. |
| F | Find and Replace | `preparation.find_replace` | **P1** | Cleaning vendor names, account codes and stray characters precedes every join and match; regex covers the long tail. |
| B | Date Helper | `preparation.date_helper` | **P1** | Cut-off, weekend/holiday postings, period-end and fiscal-period tests all need date parts; CSV dates arrive as text. |
| H1 | Pivot | `transform.pivot` | **P1** | Trial balance by period, ageing buckets; auditors live in matrices. |
| H2 | Unpivot | `transform.unpivot` | **P1** | Turns wide ledgers/TBs into tests-ready long form; round-trips with Pivot. |
| L | Comment | `report.comment` | **P1** | Reviewer notes on the canvas; feeds the workpaper (plan 06) and run log (plan 02). Smallest node, highest documentation value. |
| C | Reconcile | `join.reconcile` | **P1** | Bank-to-ledger, subledger-to-GL, AR/AP matching with tolerance: the core audit reconciliation. Four outputs incl. a summary for the workpaper. |
| I | Window | `transform.window` | **P2** | Prior-row comparison, gaps in sequences, ranking, running balances. Valuable, but Running Total, Sort and Unique cover simple cases today. |
| G | Text to Columns | `preparation.text_to_columns` | **P2** | Splits "1000-200" account strings and "Name; Ref" fields; Excel users expect it. |
| D | Fuzzy Match | `join.fuzzy_match` | **P2** | Duplicate-vendor and related-party screens. Judgemental by nature (threshold), so after exact Reconcile. |
| J | Multi-Field Formula | `preparation.multi_field_formula` | **P3** | Convenience: Formula already does the same one column at a time. |
| E | SQL Query | `transform.sql_query` | **P3** | Power users only and the largest attack surface (4.13); every use case above has a dedicated node. |

### 1.2 Implementation order (one commit per node, shared foundations first)

`F1..F7` foundations (section 3; F7 = the SQL guard, which plan 09 F-H2 imports) -> 1 Record ID -> 2 Select Records -> 3 Find and Replace -> 4 Date Helper -> 5 Pivot -> 6 Unpivot -> 7 Comment -> 8 Reconcile (adds `assign.py`) -> 9 Window -> 10 Text to Columns -> 11 Fuzzy Match (reuses `assign.py`) -> 12 Multi-Field Formula (uses `sql_guard.py` from F7) -> 13 SQL Query (uses the guard, patches the SQL editor).
Reason: P1 first and simple-to-hard so the scaffolding is proven on Record ID before the heavy nodes; shared modules are created by the first node that needs them. Stop after step 8 and the P1 scope is shippable.

---

## 2. Current state (verified)

| Fact | Where |
|---|---|
| Enums to extend (append at the end; never reorder) | `core/node_configuration.py:38-48` `PreparationNodes` (ends `NORMALIZE_COLUMNS`), `:51-54` `JoinNodes` (ends `UNION`), `:57-61` `TransformNodes` (`ARRANGE`, `COUNT_RECORDS`, `RUNNING_TOTAL`, `TRANSPOSE`), `:64-65` `ReportNodes` (`GRAPH`) |
| Lazy registry and import sweep | `qt/widgets/nodes/__init__.py:14` `_LAZY_NODE_SPECS`, `:156` `_LAZY_HELPER_MODULES`, `:173` sweep; title/icon must equal the class (`tests/unit/test_node_titles.py:56-67`) |
| Empty stubs (0 bytes, nothing imports them; only `.pyc` mention them) | `qt/widgets/nodes/Join/find_replace.py`, `qt/widgets/nodes/Documentation/comment.py` |
| Live evaluation requires every input connected | `qt/node_base.py:816-834` (`evalImplementation`: `getInput(i)` falsy -> tooltip "Input i is not connected", return `None`) |
| `getSocketValue` returns the first matching upstream socket | `qt/node_base.py:708-723`. Verified: Split-like source with outputs E,V feeding inputs 0 and 1 of one node returns socket 0 for both. `getInputWithSocket(i)` (vendored `nodeeditor/node_node.py`) returns `(node, socket)`; `socket.index` is the output index (same use in `union.py:897`). Verified to resolve `[(Src, 0), (Src, 1)]` correctly. |
| Multi-output node precedent | `Preparation/filter.py:1136` (`outputs=[3, 3]`, `output_text=["T","F"]`), `split.py:475` |
| Declared outputs survive the Run only if named `variable_name` / `*_variable_name` / `*_var` or listed in `node.param` | `workflow_execution_mixin.py:225-282`; `getSocketData` maps socket index to that ordered list (`:300-319`) |
| Content state schema: dict defaults are merged, so new setting keys are backward compatible | `qt/helpers/state_mixin.py:20-60` |
| Undo paths cannot index lists (`set_in` handles attributes and dict keys only) | `qt/undo/commands.py:61-91`; whole-list changes go through `push_list_change` (`qt/helpers/content_undo_mixin.py:170`) |
| Shared dock widgets | `qt/widgets/common/config_widgets.py`: `ConfigSection:326`, `SegmentedControl:482`, `FormRow:547`, `ColumnChecklist:638`; file imports `from typing import Optional` at `:10`; re-exports in `qt/widgets/common/__init__.py` |
| Existing card QSS to copy | `resources/qt/themes/base.qss:2024-2036` (`FormulaCard*`); `qss/_style.scss:2403` (shared widget block) |
| SQL editor | `qt/widgets/sql_formula_editor.py`: `SQLFormulaWidget:1080` (`_undo_composite=True`, `set_validate_callback:1139`, `set_available_columns:1135`), `match_completions:249`, `validate_column_references:824`, call at `:635`, completion use `:514`, `external_validator` branch `:614`. Columns are completed and validated as `[name]` (formula syntax). |
| Formula DuckDB precedent | `Preparation/formula.py:986` (`SELECT * REPLACE (...)`), `:1048` (`duck.register`), `:1305-1319` (codegen collects, runs `duck.execute(...).pl()`, `normalize_to_supported_dtypes`) |
| Dtype normaliser used after DuckDB | `core/utils/dtype_utils.py:97` |
| Node-module bundling | `trigger.spec:32-51` lists node sources as hidden imports; core modules loaded by string (`importlib`, generated code) need the same treatment (F6) |
| `core/` and `core/utils/` are namespace packages (no `__init__.py`) | so `core/shaping/` needs none |
| Brief facts reused unchanged | brief 3.3 (`processInputs` contract), 3.4 (`get_code`: define every output, idempotent), 4.1-4.2 (live vs Run), 6 (undo), 9 (tests), Excel `xlsxwriter` gap (plan 06 owns it) |

**New facts verified for this plan (snippets in section 3.7):** `LazyFrame.pivot` exists but needs known columns; `DataFrame.pivot(aggregate_function="sum"/"len")` fills missing cells with **0**, `first`/`min`/`max`/`mean`/`median` give null; `pl.business_day_count`, `Expr.dt.add_business_days(..., roll=...)`, `dt.is_business_day`, `dt.month_end`, `dt.quarter`, `str.splitn`, `str.replace_all` capture groups (`$1`, `${name}`), `Expr.over(order_by=...)`, `rolling_sum(min_samples=...)` all exist; Rust regex has no backreferences and is linear time; DuckDB `extract_statements` types `PRAGMA ...`, `DESCRIBE`, `FROM 'file.csv'` and every `read_*()` call as `SELECT`, so a statement-type check alone is not enough.

---

## 3. Shared foundations

Build these seven pieces first (steps F1-F7 in section 5). Every node then reduces to: one Qt-free core module, one thin node module, one test file.

### 3.1 Design rules (decisions, each with its reason)

1. **Core logic is Qt-free** in `src/trigger_designer/core/shaping/<name>.py` and exposes `run_node(frames: list, settings: dict) -> list[pl.LazyFrame]` (one entry per output socket, in socket order) and optionally `describe(frames, settings) -> list[(text, tone)]` for dock chips. *Reason:* unit tests need no widgets (brief 3.7 step 2), and live evaluation and Run call the same function, so they cannot disagree.
2. **One `settings` dict per node**, saved under the content key `"settings"` (`SerializableContentMixin`, default = the core module's `DEFAULTS`). New keys added later get defaults on old files (dict defaults are merged, `state_mixin.py:25-37`). No `WORKFLOW_SCHEMA_VERSION` bump.
3. **Generated code never interpolates user text.** It is `from <core module> import run_node as _run_node` plus `json.loads('<settings json>')`. *Reason:* the brief's injection and quoting pitfalls (10.4) cannot occur; `check_output.py` stays valid Python.
4. **Frames stay lazy at the boundary.** `run_node` returns `LazyFrame`s; nodes that must materialise (Reconcile, Fuzzy, Pivot, Multi-Field, SQL) collect *inside* `run_node` (documented, like Count) and return `.lazy()`.
5. **Errors:** `ShapingError(code, detail)` (a `ValueError`): `str(e) == "[TD-SHAPE-NNN] detail"`. Live path: tooltip = that string. Run path: exception text contains the code, so plan 03 can match `\[TD-SHAPE-\d{3}\]`. Codes are the `ERROR_CODES` table in `common.py` (never renumber).
6. **No silent overwrite.** An output column that already exists is `TD-SHAPE-002`, except two defined suffix rules: Pivot header names (`_2`, `_3`) and Reconcile/Fuzzy right-side columns (`_right`).
7. **Row order is preserved** unless a node states otherwise (Select Records largest/smallest, Reconcile, Fuzzy, Pivot, Unpivot).
8. **CSV text is numeric-ready.** File Input yields all-String columns (brief 7.1); numeric inputs use `numeric_expr` (strip, drop thousands commas, `cast(Float64, strict=False)`; unreadable -> null, never an exception).
9. **Live cap.** `LIVE_CAP_ROWS` on heavy nodes (Reconcile/Fuzzy 200,000; Pivot 5,000,000; SQL Query and Multi-Field 2,000,000): above it the live path returns typed empty frames and a warning chip; Run computes everything. *Reason:* live evaluation is on the GUI thread (brief 4.1).
10. **Two outputs of one node into one node must work.** Shaping nodes read inputs with `getInputWithSocket` (3.4), never `getSocketValue`.

### 3.2 F1 - `core/shaping/common.py` (verified)

Create `src/trigger_designer/core/shaping/common.py` (no `__init__.py`; `core/` is a namespace package).

```python
"""Shared helpers for the shaping nodes (Qt-free)."""

from __future__ import annotations

from typing import Iterable

import polars as pl

Frame = pl.LazyFrame | pl.DataFrame

#: Stable error codes (plan 03 translates; never reuse or renumber).
ERROR_CODES: dict[str, str] = {
    "TD-SHAPE-001": "A required setting is missing",
    "TD-SHAPE-002": "An output column name is empty, duplicated or already exists",
    "TD-SHAPE-003": "A selected column is not in the input any more",
    "TD-SHAPE-004": "A setting value is out of range or unknown",
    "TD-SHAPE-005": "A required input has no data",
    "TD-SHAPE-040": "The pattern is not a valid regular expression",
    "TD-SHAPE-041": "The pattern is too long",
    "TD-SHAPE-042": "Find text is empty",
    "TD-SHAPE-043": "Too many rules",
    "TD-SHAPE-044": "The column must be text",
    "TD-SHAPE-050": "The column is not a date and not text",
    "TD-SHAPE-052": "A holiday is not a YYYY-MM-DD date",
    "TD-SHAPE-053": "Working days must name at least one weekday",
    "TD-SHAPE-060": "Index, header and value columns must be different",
    "TD-SHAPE-061": "Too many new columns",
    "TD-SHAPE-070": "Amount or date column is set on one side only",
    "TD-SHAPE-071": "Add a key column pair or a date column",
    "TD-SHAPE-072": "Too many possible matches",
    "TD-SHAPE-081": "Too many possible fuzzy pairs",
    "TD-SHAPE-082": "Too many rows to compare without blocking",
    "TD-SHAPE-091": "The column must be a number",
    "TD-SHAPE-101": "The split pattern can match nothing",
    "TD-SHAPE-110": "Only one SQL statement is allowed",
    "TD-SHAPE-111": "Only SELECT queries are allowed",
    "TD-SHAPE-112": "A file, system or random function is not allowed",
    "TD-SHAPE-113": "The SQL could not be parsed or run",
    "TD-SHAPE-114": "The SQL is too long",
    "TD-SHAPE-115": "The query took too long",
    "TD-SHAPE-120": "The formula must contain {col}",
}


class ShapingError(ValueError):
    """A configuration or data problem with a stable code.

    Subclass of ValueError so TriggerNode.eval shows str(e) as the tooltip.
    """

    def __init__(self, code: str, detail: str, columns: Iterable[str] = ()):
        self.code = code
        self.detail = detail
        self.columns = tuple(columns)
        super().__init__(f"[{code}] {detail}")


def as_lazy(frame: Frame) -> pl.LazyFrame:
    return frame if isinstance(frame, pl.LazyFrame) else frame.lazy()


def schema_of(frame: Frame) -> dict[str, pl.DataType]:
    schema = frame.collect_schema() if isinstance(frame, pl.LazyFrame) else frame.schema
    return dict(schema.items())


def require_columns(frame_schema: dict, names: Iterable[str]) -> None:
    missing = [n for n in names if n not in frame_schema]
    if missing:
        raise ShapingError("TD-SHAPE-003", f"Column(s) not found: {', '.join(missing)}", missing)


def unique_name(base: str, taken: Iterable[str]) -> str:
    """``base`` if free, else ``base_2``, ``base_3`` ... (deterministic)."""
    taken = set(taken)
    if base not in taken:
        return base
    i = 2
    while f"{base}_{i}" in taken:
        i += 1
    return f"{base}_{i}"


def numeric_expr(name: str, dtype: pl.DataType) -> pl.Expr:
    """Column as Float64; text is cast with strict=False (bad values -> null)."""
    col = pl.col(name)
    if dtype.is_numeric():
        return col.cast(pl.Float64)
    return col.cast(pl.String).str.replace_all(",", "").str.strip_chars().cast(pl.Float64, strict=False)


def estimate_pairs(left: pl.DataFrame, right: pl.DataFrame, keys: list[str]) -> int:
    """Rows an inner join on ``keys`` would produce, without building it."""
    a = left.drop_nulls(keys).group_by(keys).len(name="__cnt_l")
    b = right.drop_nulls(keys).group_by(keys).len(name="__cnt_r")
    total = a.join(b, on=keys).select((pl.col("__cnt_l").cast(pl.Int64) * pl.col("__cnt_r").cast(pl.Int64)).sum())
    return int(total.item() or 0)
```

### 3.3 F2 - optional inputs in `TriggerNode.evalImplementation` (BUG-031; verified)

Exact edit points in `src/trigger_designer/qt/node_base.py` as of `71b4041`: a class attribute after `style` (line 652, inside `class TriggerNode(Node)`, which starts at line 645) and the `if not input_node:` branch of `evalImplementation` (the method spans lines 816-852; the branch is lines 821-826). This plan is the only one that edits these lines; a plan that needs optional inputs reuses `optional_inputs` instead of adding a second mechanism.

SQL Query has inputs `t1` (required), `t2`, `t3` (optional). Patch `src/trigger_designer/qt/node_base.py` (two additions; behaviour of every existing node is unchanged because `optional_inputs` is empty):

```diff
@@ class TriggerNode(Node):   (class attributes, near line 652)
     style: dict[str, str] = {"brush_color": "#000000"}
+    #: input indexes that may stay unconnected; processInputs then gets None for them
+    optional_inputs: frozenset = frozenset()
@@ def evalImplementation(self):   (line ~819)
             input_node = self.getInput(i)
             if not input_node:
+                if i in self.optional_inputs:
+                    input_values.append(None)
+                    continue
                 self.markInvalid()
                 self.markDescendantsDirty()
                 self._set_node_tooltip(f"Input {i} is not connected")
```
Verified by monkeypatching the identical function: a 3-input node with only input 0 wired evaluated valid and generated `_run_node([var_src, None, None], ...)`.

### 3.4 F3/F4 - `RuleStack`, `shaping_support.py`

**F3 `RuleStack`** (ordered cards with move/remove icons and one add icon; verified headless). Add to `qt/widgets/common/config_widgets.py` (change line 10 to `from typing import Any, Optional`), re-export from `qt/widgets/common/__init__.py` (import list and `__all__`), then add QSS.

`RuleStack(add_tooltip: str, rsm=None, parent=None)` is a `QWidget` (vertical layout, spacing `SECTION_GAP`) that only draws; the owner keeps the list and rebuilds after every change.
* Signals: `add_requested()`, `remove_requested(int)`, `move_requested(int, int)` (index, delta -1/+1). Attribute `add_button` (an `IconButton`, right-aligned under the cards). Methods: `clear()` (takeAt + `deleteLater` every card) and `add_card(index, count, body: QWidget)`.
* One card = `QFrame#RuleCard` (margins 4,2,4,4, spacing 2) holding a header `QFrame#RuleCardHeader` (a `QLabel#FieldLabel` with `str(index + 1)` stretched, then three `IconButton.themed` buttons) and `body` (`setObjectName("RuleCardBody")`). Buttons: "Move up" (`icon_move_up`, fallback `:/qss_icons/dark/rc/arrow_up.png`, disabled when `index + delta` is out of `0..count-1`), "Move down" (`icon_move_down`, `arrow_down.png`), "Remove" (`icon_remove`, `window_close.png`); `add_button` uses `icon_add` / `arrow_right.png` and the given tooltip. Resolve each glyph with `rsm.get(id)` (None is fine: `IconButton.themed` falls back) - `icon_move_up/down` do not exist yet, the fallback is what shows.
* `IconButton` already sets tooltip, accessible name, 30x30 size; use no inline QSS (rules below).

QSS (restate nothing else: the icons are `IconButton`s, whose hover/pressed rules already exist). Add to `resources/qt/themes/base.qss` after the `QFrame#FormulaCardBody` rule (~line 2036), and the matching block to `qss/_style.scss` after `QLabel#EmptyStateLabel` (~line 2407):

```css
QFrame#RuleCard {{ background-color: {background_secondary}; border: 1px solid {border_primary}; border-radius: 4px; }}
QFrame#RuleCardHeader {{ background-color: transparent; border: 0px; border-bottom: 1px solid {border_primary}; }}
QFrame#RuleCardBody {{ background-color: transparent; border: 0px; }}
/* _style.scss: same three selectors with single braces, $COLOR_BACKGROUND_2 / $COLOR_BACKGROUND_3 / $SIZE_BORDER_RADIUS */
```
Run `tests/unit/test_theme_tokens.py` afterwards (it formats `base.qss` against every theme).

**F4 `qt/helpers/shaping_support.py`.** `Field` describes a control, `ShapingContent` is the base content class, `ShapingNode` the base node. A node is: `SETTINGS`, `MODULE`, `OUTPUT_KINDS`, `INPUTS`, `FORM`, `HISTORY` plus node attributes. The code below is the verified file with seven mechanical methods reduced to their contract (docstring only); write those from the widget table under the code.

```python
"""Shared scaffolding for the shaping nodes (docs/plan/07-shaping-nodes.md)."""

from __future__ import annotations

import copy
import importlib
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import polars as pl
from nodeeditor.node_icon_content_widget import QDMNodeIconContentWidget
from nodeeditor.utils_no_qt import dumpException
from qtpy.QtCore import QTimer, Signal
from qtpy.QtGui import QPixmap
from qtpy.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QLineEdit,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from trigger_designer.core.shaping.common import ShapingError
from trigger_designer.qt.helpers.state_mixin import SerializableContentMixin
from trigger_designer.qt.node_base import (
    TriggerChangeHandler,
    TriggerGraphicsNode,
    TriggerNode,
    frame_schema,
)
from trigger_designer.qt.undo.protocol import is_syncing
from trigger_designer.qt.widgets.common import (
    ColumnChecklist, ConfigSection, EmptyStateLabel, FormRow, NoWheelComboBox, RuleStack,
)  # fmt: skip


@dataclass(frozen=True)
class Field:
    """One dock control bound to ``settings[key]`` (or to a key inside a list card)."""

    key: str
    label: str
    kind: str  # combo|column|columns|choices|text|textarea|int|float|check|list
    options: tuple = ()  # combo/choices: ((value, label), ...)
    minimum: float = 0
    maximum: float = 1_000_000
    placeholder: str = ""
    tip: str = ""
    blank: bool = False  # column: first entry "(none)" = ""
    input: int = 0  # column(s): which input's schema supplies the names
    filter: str = ""  # column(s): "" all | "text" | "numeric" | "date"
    show_if: Optional[Callable[[dict], bool]] = None  # top-level fields only
    items: tuple = ()  # list: Fields drawn in every card
    item_default: dict = field(default_factory=dict)  # list: a new card
    max_items: int = 50


def _passes(dtype: pl.DataType, kind: str) -> bool:
    if kind == "text":
        return dtype == pl.String
    if kind == "numeric":
        return dtype == pl.String or dtype.is_numeric()
    if kind == "date":
        return dtype in (pl.String, pl.Date) or isinstance(dtype, pl.Datetime)
    return True


class ShapingContent(QDMNodeIconContentWidget, TriggerChangeHandler, SerializableContentMixin):
    evaluate = Signal()
    SETTINGS: dict = {}  # defaults; every key the node reads
    MODULE = ""  # dotted core module exposing RUNNER(frames, settings) -> [LazyFrame, ...]
    RUNNER = "run_node"
    OUTPUT_KINDS: tuple = ("out",)  # variable-name stems, one per output socket
    INPUTS = 1
    OPTIONAL_INPUTS: frozenset = frozenset()
    LIVE_CAP_ROWS = 0  # >0: above this many input rows the live path returns typed empty frames
    FORM: tuple = ()  # ((section title, (Field, ...)), ...)
    HISTORY = "Node"  # noun in history text: "<HISTORY> <field label> Changed"

    def get_serialized_state_schema(self) -> dict:
        return {"settings": {"default": copy.deepcopy(self.SETTINGS)}}  # new keys get defaults

    def __init__(self, node: "TriggerNode", parent: Optional[QWidget] = None) -> None:
        super().__init__(node, parent)
        TriggerChangeHandler.__init__(self, node.scene, node)
        self.history = node.scene.history
        self.settings: dict = copy.deepcopy(self.SETTINGS)
        self.frames: list = [None] * self.INPUTS
        self.input_vars: list = [""] * self.INPUTS
        self.outputs: list = []
        self.chips: list = []  # [(text, tone)] shown by dock_context
        self.output_variables = [f"var_{k}_{self.id}" for k in self.OUTPUT_KINDS]
        for i, name in enumerate(self.output_variables):  # kept by _prune_node_results
            setattr(self, "variable_name" if i == 0 else f"out{i}_variable_name", name)
        self._widgets, self._rows, self._stacks, self._timers = {}, {}, {}, []

    @property
    def node(self) -> "TriggerNode":
        return self._node

    @node.setter
    def node(self, value: "TriggerNode") -> None:
        self._node = value

    def initUI(self, icon: Optional[QPixmap] = None) -> None:
        super().initUI(self.node.rsm.get(f"{self.node.icon}"))

    # ---- data and code generation (live and Run share run_node) ----------------------
    def schema(self, index: int = 0) -> dict:
        frame = self.frames[index] if index < len(self.frames) else None
        return frame_schema(frame) if frame is not None else {}

    def names(self, f: Field) -> list:
        return [c for c, t in self.schema(f.input).items() if _passes(t, f.filter)]

    def _rows_in(self) -> int:
        total = 0
        for f in self.frames:
            if isinstance(f, pl.LazyFrame):
                total += f.select(pl.len()).collect().item()
            elif f is not None:
                total += f.height
        return total

    def compute(self) -> list:
        module = importlib.import_module(self.MODULE)
        settings, frames, self.chips = copy.deepcopy(self.settings), list(self.frames), []
        capped = bool(self.LIVE_CAP_ROWS) and self._rows_in() > self.LIVE_CAP_ROWS
        if capped:  # keep the GUI thread responsive: typed empty outputs, full result at Run
            frames = [None if f is None else pl.DataFrame(schema=frame_schema(f)).lazy() for f in frames]
            self.chips = [(f"Over {self.LIVE_CAP_ROWS:,} rows: full result at Run", "warning")]
        outs = getattr(module, self.RUNNER)(frames, settings)
        self.outputs = [o.lazy() if isinstance(o, pl.DataFrame) else o for o in outs]
        describe = getattr(module, "describe", None)
        try:  # chips are advisory; they must never fail the node
            self.chips += describe(frames, settings) if describe and not capped else []
        except Exception:  # noqa: BLE001
            pass
        return self.outputs

    def get_code(self) -> str:
        outs = self.output_variables
        missing = [i for i in range(self.INPUTS) if not self.input_vars[i] and i not in self.OPTIONAL_INPUTS]
        if missing or not outs:  # always define every output (no NameError downstream)
            return "\n".join(["import polars as pl"] + [f"{v} = pl.DataFrame().lazy()" for v in outs]) + "\n"
        target = ", ".join(outs) + ("," if len(outs) == 1 else "")
        ins = ", ".join(v or "None" for v in self.input_vars)
        payload = json.dumps(self.settings, sort_keys=True)
        return (
            "import json\nimport polars as pl\n"
            f"from {self.MODULE} import {self.RUNNER} as _run_node\n"
            f"{target} = _run_node([{ins}], json.loads({payload!r}))\n"
        )

    # ---- one setting change = one undo step ---------------------------------------------
    def set_setting(self, key: str, value: Any, text: str, merge_key: Optional[str] = None) -> None:
        if is_syncing(self) or self.history.is_restoring_history:  # model -> widget write-back
            return
        old = self.settings.get(key)
        if value == old:
            return
        self.settings[key] = copy.deepcopy(value)  # 1. model
        self._update_visibility()
        self.after_change()
        self.refresh_dock_context()
        self.evaluate.emit()  # 2. re-evaluate (a merged push never calls redo)
        push = self.push_list_change if isinstance(value, list) else self.push_property_change
        push(("settings", key), copy.deepcopy(old), copy.deepcopy(value), text, merge_key=merge_key)  # 3.

    def after_change(self) -> None:
        """Hook run after every model change, user edit or undo/redo (Comment uses it)."""

    # ---- dock -----------------------------------------------------------------------------
    def ready(self) -> bool:
        return all(self.frames[i] is not None for i in range(self.INPUTS) if i not in self.OPTIONAL_INPUTS)

    def create_layout(self, dock_layout: QVBoxLayout) -> None:
        if not self.ready():
            dock_layout.addWidget(EmptyStateLabel())
            return
        self._widgets, self._rows, self._stacks = {}, {}, {}
        for title, fields in self.FORM:
            section = ConfigSection(title)
            section._undo_composite = True  # we record our own commands; skip the sweep
            for f in fields:
                row = self._build_list(f) if f.kind == "list" else self._build_row(f)
                self._rows[f.key] = row
                section.addWidget(row)
            dock_layout.addWidget(section)
        dock_layout.addStretch()
        self._update_visibility()

    def _burst_key(self, f: Field, prefix: str = "") -> Optional[str]:  # typing bursts merge
        return f"{self.node.node_title}-{prefix}{f.key}" if f.kind in ("text", "textarea", "int", "float") else None

    def _build_row(self, f: Field) -> QWidget:
        commit = lambda v, f=f: self.set_setting(f.key, v, f"{self.HISTORY} {f.label} Changed", self._burst_key(f))  # noqa: E731
        w = self._make_widget(f, self.settings.get(f.key), commit)
        self._widgets[f.key] = w
        return FormRow(f.label, w, label_width=96)

    def _make_widget(self, f: Field, value: Any, commit: Callable) -> QWidget:
        """Control for ``f.kind`` per the widget table (3.4); call ``commit(value)`` on user change."""

    def _debounced(self, signal, fire: Callable[[], None]) -> None:  # 300 ms, DESIGN_SYSTEM §6
        """300 ms single-shot QTimer on ``signal``; keep it in ``self._timers``."""

    def flush_pending(self) -> None:
        """Stop and fire (``timeout.emit()``) every active timer in ``self._timers``."""

    @staticmethod
    def _set_combo(w: NoWheelComboBox, value: Any) -> None:
        """Select ``value`` by itemData; if absent, add '<value> (missing)' and select it."""

    # ---- ordered lists: rules, operations, key pairs (whole-list undo commands) -----------------
    def _build_list(self, f: Field) -> QWidget:
        """RuleStack(f'Add <label>', self.node.rsm); wire add/remove/move to ``_list_change``; fill."""

    def _fill_stack(self, f: Field, stack: RuleStack) -> None:
        """stack.clear(); one card per item: a FormRow(sub.label, _make_widget(sub, ...), label_width=84) per sub-field whose commit is ``_list_change(f, 'edit', i, sub, v)``; stack.add_card(i, n, body); disable add_button at max_items."""

    def _list_change(self, f: Field, op: str, index: int = 0, arg: Any = None, value: Any = None) -> None:
        items = copy.deepcopy(self.settings.get(f.key) or [])
        merge, verb = (
            None,
            {"add": "Added", "remove": "Removed", "move": "Moved", "edit": "Changed"}[op],
        )
        if op == "add":
            items.append(copy.deepcopy(dict(f.item_default)))
        elif op == "remove" and 0 <= index < len(items):
            del items[index]
        elif op == "move" and 0 <= index < len(items) and 0 <= index + arg < len(items):
            items[index], items[index + arg] = items[index + arg], items[index]
        elif op == "edit" and index < len(items):
            items[index][arg.key] = value
            merge = self._burst_key(arg, f"{f.key}{index}-")
        else:
            return
        self.set_setting(f.key, items, f"{self.HISTORY} {f.label} {verb}", merge)
        if op != "edit":
            self._fill_stack(f, self._stacks[f.key])

    # ---- undo projection ---------------------------------------------------------------------------
    def _all_fields(self):
        for _title, fields in self.FORM:
            yield from fields

    def _sync_widgets_from_model(self) -> None:  # runs inside syncing(): write quietly
        """Runs inside syncing(): per non-list field blockSignals(True), write settings[key] into the widget, blockSignals(False); drop widgets that raise RuntimeError; then _update_visibility() and after_change()."""

    def _rebuild_widgets(self) -> None:  # list structure changed (undo/redo of add/remove/move)
        for f in self._all_fields():
            stack = self._stacks.get(f.key)
            try:
                if stack is not None:
                    self._fill_stack(f, stack)
            except RuntimeError:
                self._stacks.pop(f.key, None)

    def _update_visibility(self) -> None:
        for f in self._all_fields():
            row = self._rows.get(f.key)
            try:
                if row is not None and f.show_if is not None:
                    row.setVisible(bool(f.show_if(self.settings)))
            except RuntimeError:
                self._rows.pop(f.key, None)

    def dock_context(self):
        return list(self.chips), ""

    # ---- persistence -----------------------------------------------------------------------------------
    def serialize(self):
        return self.serialize_content_state(super().serialize())

    def deserialize(self, data, hashmap={}):
        res = super().deserialize(data, hashmap)
        try:
            self.deserialize_content_state(data)
            self.after_change()
            return True and res
        except Exception as exc:  # noqa: BLE001
            dumpException(exc)
        return res


class ShapingNode(TriggerNode):
    """Base node. Subclass sets icon, node_code, node_type, node_title, content_class, output_text."""

    content_class: type = ShapingContent
    output_text: tuple = ("",)
    style = {}

    @property
    def optional_inputs(self) -> frozenset:  # read by TriggerNode.evalImplementation (F2)
        return self.content_class.OPTIONAL_INPUTS

    def __init__(self, scene) -> None:
        c = self.content_class
        super().__init__(
            scene,
            inputs=[1] * c.INPUTS,
            outputs=[3] * len(c.OUTPUT_KINDS),
            output_text=list(self.output_text),
        )

    def initInnerClasses(self) -> None:
        self.content = self.content_class(self)
        self.grNode = TriggerGraphicsNode(self)
        self.content.evaluate.connect(self.onInputChanged)
        self.param: list = []

    def processInputs(self, input_values) -> Optional[list]:
        content = self.content
        for i in range(content.INPUTS):
            # getInputWithSocket, NOT getSocketValue: when two outputs of ONE upstream node feed
            # two inputs here, getSocketValue returns the first matching socket for both.
            upstream, socket = self.getInputWithSocket(i)
            entry = input_values[i][socket.index] if upstream is not None and input_values[i] is not None else None
            if entry is None or entry.get("data") is None:
                content.frames[i], content.input_vars[i] = None, ""
                if i in content.OPTIONAL_INPUTS:
                    continue
                self._set_node_tooltip(f"[TD-SHAPE-005] Input {i + 1} has no data")
                return None
            content.frames[i], content.input_vars[i] = entry["data"], entry["variable_name"]
        try:
            outs = content.compute()
        except ShapingError as exc:  # stable code is the tooltip prefix
            self._set_node_tooltip(str(exc))
            self.markDirty(True)
            self.markInvalid(True)
            return None
        self.param = [{"data": f, "variable_name": n} for f, n in zip(outs, content.output_variables)]
        return self.param

    def get_code(self) -> str:
        return self.content.get_code()
```

**Widget table** (what `_make_widget` builds; every combo is a `NoWheelComboBox`, every control `setMinimumHeight(30)`, no inline QSS):

| `kind` | Widget | Value in `settings` | Change signal -> `commit` | Quiet write (sync) |
|---|---|---|---|---|
| `combo` | `NoWheelComboBox`, items `options` `(value, label)`, itemData = value | `str` | `currentIndexChanged` -> `currentData()` | `_set_combo` |
| `column` | same; items = `names(f)`, plus `("", "(none)")` first when `blank` | `str` ("" = none) | same | `_set_combo` |
| `columns` | `ColumnChecklist(names(f), checked)` | `list[str]` | `changed(list)` | `setChecked(list)` |
| `choices` | `ColumnChecklist([v for v, _ in options], checked)` | `list[str]` | `changed(list)` | `setChecked(list)` |
| `check` | `QCheckBox` | `bool` | `toggled` | `setChecked` |
| `int` / `float` | `QSpinBox` / `QDoubleSpinBox`, `setRange(minimum, maximum)` | number | `valueChanged` through the 300 ms debounce | `setValue` |
| `text` | `QLineEdit` | `str` | `textChanged` through the 300 ms debounce | `setText` only if different |
| `textarea` | `QPlainTextEdit`, min height 90 | `str` | `textChanged` through the debounce | `setPlainText` only if different |
| `list` | `RuleStack` of cards, each card = `FormRow` per sub-`Field` | `list[dict]` | add/remove/move/edit -> `_list_change` | `_fill_stack` (`_rebuild_widgets`) |

Notes: (a) `placeholder` and `tip` become `setPlaceholderText` / `setToolTip`; labels are `FormRow` captions (`label_width` 96, cards 84). (b) Sections are marked `_undo_composite = True` so the Config Dock sweep (`registerUnboundDockWidgets`) does not also bind the same controls (brief 6.4). (c) Whole lists are the undo unit: `set_in` cannot address list indexes (section 2), so list edits deep-copy the list and call `push_list_change`; typing in a card field merges by key `"<title>-<list key><index>-<field key>"`. (d) History text is `"<HISTORY> <Field label> Changed|Added|Removed|Moved"` ("Noun Verbed", only on a real diff - `set_setting` returns early when `value == old`).

**Node module template** (Record ID; every other node differs only in names, `FORM` and sockets):

```python
"""Record ID node: Qt wrapper only; the logic is core/shaping/record_id.py."""
from trigger_designer.core.node_configuration import NodeTypes, PreparationNodes, register_node
from trigger_designer.core.shaping import record_id as core
from trigger_designer.qt.helpers.shaping_support import Field, ShapingContent, ShapingNode


class RecordIdContent(ShapingContent):
    SETTINGS = core.DEFAULTS
    MODULE = "trigger_designer.core.shaping.record_id"
    OUTPUT_KINDS = ("recordid",)  # variable var_recordid_<id>
    HISTORY = "Record ID"
    FORM = (
        ("", (
            Field("name", "Name", "text", placeholder="RecordID"),
            Field("start", "Start at", "int", minimum=-1_000_000_000, maximum=1_000_000_000),
            Field("position", "Position", "combo", options=(("first", "First"), ("last", "Last"))),
        )),
        ("Number within groups", (
            Field("group_by", "Groups", "columns"),
            Field("order_by", "Order by", "list", item_default={"column": "", "descending": False},
                  items=(Field("column", "Column", "column"), Field("descending", "Descending", "check"))),
        )),
    )  # fmt: skip


@register_node(PreparationNodes.RECORD_ID, NodeTypes.PREPARATION)
class TriggerNode_RecordId(ShapingNode):
    icon = "node_count"  # reused icon id (resources.json); no new art
    node_code = PreparationNodes.RECORD_ID
    node_type = NodeTypes.PREPARATION
    node_title = "Record ID"
    content_class = RecordIdContent
    content_label_objname = "trigger_node_record_id"
```
Multi-output nodes also set `output_text = ("M", "L", "R", "S")` (one letter per socket; the base upper-cases the first letter). `OUTPUT_KINDS` order **is** the socket order and the order `getSocketData` uses after a Run, because `ShapingContent.__init__` sets `variable_name`, `out1_variable_name`, `out2_variable_name`, ... in that order (brief 3.4 pruning rule). Never add another `*_variable_name` string attribute to a content class.

### 3.5 F5 - test helpers (verified graph/live/codegen part)

`tests/support/shaping.py` (unit and UI tests import it). `graph()` builds the node in a `TriggerSubWindow`; `single_source=True` feeds all inputs from one multi-output `Source`, the exact case `getSocketValue` gets wrong.

Contract (all verified; about 70 lines):
* `Source(scene, *frames)`: a `TriggerNode` double with `outputs=[3] * len(frames)` whose `evalImplementation` sets `value = [{"data": f, "variable_name": f"var_src_{self.id}_{i}"}]` and marks itself clean/valid.
* `graph(node_cls, *frames, settings=None, single_source=False) -> G(parent, window, node, sources)`: `parent = QMainWindow()` (strong reference), `window = TriggerSubWindow(parent)`, `node = node_cls(window.scene)`, `node.content.settings.update(settings)`; one `Source` per frame wired to input `i`, or with `single_source=True` one multi-output `Source` whose output `i` feeds input `i`; `node.markDirty(True)`.
* `live(g)`: `out = g.node.eval()`; assert `out is not None and not g.node.isInvalid()` (message = the tooltip); return each `o["data"].collect()`.
* `codegen(g)`: `live(g)`, seed a namespace with every source `variable_name -> frame`, `exec(g.node.get_code(), {"__name__": "__main__", "pl": pl}, namespace)`, return `namespace[v].collect()` for `g.node.content.output_variables`.

The e2e helper is added in step F5 too (section 7.6 gives its body). It follows the brief's skeleton (c): build File Input(s) -> node -> File Output(s) in code, `scene.saveToFile`, reload in a fresh `TriggerSubWindow`, `run_workflow_and_wait`, read the CSVs with `read_frame`.

### 3.6 F6 - packaging and docs

* **Packaging: provided by plan 09 F-G (do not redo here).** F-G globs every module of `core/shaping/` and `core/sql_guard.py` into the hidden imports (`run_node` is imported by string/`importlib`). This plan makes no `trigger.spec` edit and no separate packaging commit.
* `docs/NODE_REFERENCE.md`: one row per new node (also add the missing Union row, brief 3.7 step 13).
* No dependency changes. `uv.lock` untouched.

### 3.7 Verified facts and snippets (record)

Run with `.venv\Scripts\python.exe -c ...` on Polars 1.44.2 / DuckDB 1.5.5.

| Claim | Snippet (abridged) | Result |
|---|---|---|
| DuckDB string similarity exists | `select jaro_winkler_similarity('ACME Corp','Acme Corporation'), levenshtein('kitten','sitting')` | `0.625`, `3`; `jaro_winkler_similarity(NULL,'a')` is NULL; it is case-sensitive (`'ACME'` vs `'acme'` = 0.0), so text is lower-cased first |
| Statement types | `con.extract_statements(q)[0].type` | `SELECT` for plain selects **and** `pragma version`, `describe select 1`, `from range(3)`, `select * from read_csv(..)`; `INSERT/CREATE/COPY/ATTACH/LOAD (install, load)/SET/EXPLAIN/CALL/DELETE/DROP` otherwise |
| Config lock | `SET enable_external_access=false; SET lock_configuration=true` then `read_csv`, `FROM 'x.csv'`, `glob`, `COPY .. TO`, `ATTACH`, `LOAD`, `SET enable_external_access=true`, `SET memory_limit` | all `PermissionException`/`InvalidInputException`; but `create table`, `drop view`, `pragma database_list`, `query('select 1')`, `duckdb_settings()` **still run**, hence the layered checker (4.13) |
| Interrupt | `threading.Timer(1, con.interrupt)` around `select count(*) from range(100000000000)` | raises `duckdb.InterruptException` after ~1 s |
| Pivot zero-fill | `df.pivot(on=..., aggregate_function="sum")` with a missing cell | `0`; with `first` the cell is `null`; `pivot(on_columns=[...])` fixes column order; header equal to an index column name -> `DuplicateError` |
| Window | `shift`, `rank("min"/"dense")`, `cum_sum/min/max`, `rolling_sum(window_size, min_samples)` with `.over(g)` after a sort | exist; `Expr.over(..., order_by=, descending=)` takes ONE flag for all keys, hence sort-compute-restore (4.9) |
| Dates | `dt.weekday` (Mon=1), `dt.to_string("%A")`, `dt.month_end`, `dt.quarter`, `pl.business_day_count(a, b, week_mask, holidays)`, `dt.add_business_days(n, week_mask, holidays, roll)` (default `roll="raise"` errors on a non-business day), `str.to_date(fmt, strict=False)` | exist; `business_day_count` is `[start, end)` forward and `(end, start]` backward |
| Regex | `str.replace_all(r"(\d+)-(\d+)", "$2-$1")`, `${name}`, `(?i)`, literal `$` needs `$$`; `(a)\1` and `(` | captures work; backreference and unclosed group raise `ComputeError`; `(a+)+$` on 50,000 `a` returns in 1 ms (linear-time engine, no ReDoS) |
| Splitting | `str.splitn("-", 3)` -> struct `field_0..field_2`, missing parts null, remainder in the last field; `str.split` of `""` -> `[""]`; `explode(col, empty_as_null=True, keep_nulls=True)` | as stated |

### 3.8 F7 - `core/sql_guard.py`: the shared read-only SQL guard

Standalone, Qt-free, importable by anything. Decision: **this plan creates it** in foundation step F7; plan 09 F-H2 imports it to guard the EXISTING Formula and Filter-expression nodes (BUG-029/030: they run user SQL on a plain DuckDB connection), so plan 09 F-H2 depends on F7 landing first. This plan's SQL Query and Multi-Field Formula are its first consumers. Path `src/trigger_designer/core/sql_guard.py` (not under `shaping/`: it is not shaping-specific). Its only project import is `ShapingError` from `core/shaping/common.py`.

Public API (stable; tell plan 09 before changing a name or signature):

| Name | Contract |
|---|---|
| `check_select_only(sql: str) -> None` | Raises `ShapingError` (a `ValueError`; codes `TD-SHAPE-001` empty, `-110` several statements, `-111` not a SELECT, `-112` forbidden function/file, `-113` unparsable, `-114` too long) unless `sql` is exactly one read-only SELECT; returns `None` when it is. A caller that embeds a user expression in a generated query (Formula, Filter) composes the full `SELECT ... FROM <relation>` first and checks that. |
| `make_locked_connection(inputs: dict[str, Frame] or None = None) -> duckdb.DuckDBPyConnection` | Fresh in-memory connection: external access, extension install/load off, `memory_limit='2GB'`, `threads=4`, `lock_configuration=true`; registers each `inputs` frame under its name (`[A-Za-z_][A-Za-z0-9_]*`, else `TD-SHAPE-004`; lazy frames are collected). The caller closes it. |
| `run_select(sql, inputs, timeout_s=25.0) -> pl.DataFrame` | `check_select_only`, then runs on a fresh locked connection with `threading.Timer(timeout_s, con.interrupt)`; `TD-SHAPE-115` on timeout, `TD-SHAPE-113` (first DuckDB message line) on engine errors; always closes the connection. |
| `infer_schema(sql, schemas: dict[str, dict]) -> dict` | Column names/types from zero-row inputs: `SELECT * FROM (\n<sql>\n) AS _q LIMIT 0` (the newline stops a trailing `--` comment swallowing the parenthesis); `TD-SHAPE-113` on error. Write it from this row (about 12 lines). |

`TD-SYS-*` is not used: the guard raises the `TD-SHAPE-110..115` family (catalogue, section 12), which plan 09 translates like any other. Tests: `tests/unit/test_sql_guard.py` (7.3).

Layers (each verified; 57 cases in 7.3):
1. Length <= 20,000 characters (114). Comments, string literals and quoted identifiers are blanked (`mask`) before any text check, so `'DROP TABLE'` as data and `-- read_csv(` in a comment are fine.
2. Exactly one statement (110): no `;` left after masking and `extract_statements` returns one.
3. The statement must start with `SELECT`, `WITH`, `FROM`, `VALUES`, `TABLE` or `(` (111). This rejects `PRAGMA`, `DESCRIBE`, `SUMMARIZE`, `SHOW`, `EXPLAIN`, `SET`, `INSTALL`, `LOAD`, `COPY`, `ATTACH`, `CALL`, DDL and DML by name, including the ones DuckDB itself labels `SELECT`.
4. DuckDB's own parser must classify it as `StatementType.SELECT` (111), which catches `WITH ... DELETE/INSERT`.
5. Denied calls anywhere in the masked text (112): `read_*()`, `glob()`, `*_scan()`, `sniff_csv()`, `query()`, `query_table()`, `duckdb_*()`, `pragma_*()`, `current_setting()`, `random()`, `uuid()`, `gen_random_uuid()`, `setseed()`, `getenv()`; and `FROM 'file'` / `JOIN 'file'` (a string where a table belongs). `random`/`uuid` are denied because a re-run must reproduce the same workpaper numbers.
6. The engine is configured last-resort safe: a **fresh in-memory connection per run** with `enable_external_access=false`, extension auto-install/load and community/unsigned extensions off, `memory_limit='2GB'`, `threads=4`, then `lock_configuration=true`. Even if layers 1-5 were bypassed, `read_csv`, `COPY`, `ATTACH`, `LOAD`, `SET enable_external_access=true` all fail (tested directly on the engine). The connection is discarded afterwards, so the in-memory DDL that DuckDB still allows cannot persist.
7. `threading.Timer(25 s, con.interrupt)` stops runaway queries (`-115`), before the executor's 30 s limit abandons the thread.

```python
"""Read-only DuckDB sandbox for SQL Query and Multi-Field Formula."""

from __future__ import annotations

import re
import threading

import duckdb
import polars as pl
from trigger_designer.core.shaping.common import Frame, ShapingError, as_lazy, schema_of

_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
MAX_SQL_CHARS = 20_000
TIMEOUT_S = 25.0  # below the executor's 30 s so we fail cleanly instead of timing out
MEMORY_LIMIT = "2GB"
THREADS = 4
#: statement must start with one of these words (after comments are removed)
ALLOWED_FIRST_WORDS = {"select", "with", "from", "values", "table"}
#: function / table-function names rejected anywhere in the statement
_DENIED_CALLS = re.compile(
    r"\b(?:read_[a-z0-9_]+|glob|[a-z0-9_]*_scan|sniff_csv|query|query_table|"
    r"duckdb_[a-z0-9_]+|pragma_[a-z0-9_]+|current_setting|which_secret|"
    r"random|uuid|gen_random_uuid|setseed|getenv)\s*\(",
    re.IGNORECASE,
)
#: FROM 'file.csv' / JOIN 'file.csv' (a quoted *string* where a table belongs)
_FROM_STRING = re.compile(r"\b(?:from|join)\s*'", re.IGNORECASE)
_LEADING_WORD = re.compile(r"[A-Za-z]+|\(")


def mask(sql: str) -> str:
    """Blank out comments and string/identifier contents (keeps quotes and length)."""
    out: list[str] = []
    i, n = 0, len(sql)
    while i < n:
        ch = sql[i]
        two = sql[i : i + 2]
        if two == "--":
            j = sql.find("\n", i)
            j = n if j == -1 else j
            out.append(" " * (j - i))
            i = j
        elif two == "/*":
            j = sql.find("*/", i + 2)
            j = n if j == -1 else j + 2
            out.append(" " * (j - i))
            i = j
        elif ch in ("'", '"'):
            j = i + 1
            while j < n:
                if sql[j] == ch:
                    if sql[j + 1 : j + 2] == ch:  # doubled quote = escaped quote
                        j += 2
                        continue
                    break
                j += 1
            out.append(ch + " " * max(j - i - 1, 0) + (ch if j < n else ""))
            i = j + 1
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def check_select_only(sql: str) -> None:
    """Raise ShapingError (TD-SHAPE-001/110/111/112/113/114) unless ``sql`` is one read-only SELECT."""
    if not sql or not sql.strip():
        raise ShapingError("TD-SHAPE-001", "SQL is empty")
    if len(sql) > MAX_SQL_CHARS:
        raise ShapingError("TD-SHAPE-114", f"SQL is longer than {MAX_SQL_CHARS:,} characters")
    masked = mask(sql).strip().rstrip(";").strip()
    if not masked:
        raise ShapingError("TD-SHAPE-001", "SQL is empty")
    if ";" in masked:
        raise ShapingError("TD-SHAPE-110", "Only one statement is allowed")
    m = _LEADING_WORD.match(masked)
    if not m or (m.group().lower() not in ALLOWED_FIRST_WORDS and m.group() != "("):
        raise ShapingError("TD-SHAPE-111", "Only SELECT queries are allowed")
    if _DENIED_CALLS.search(masked):
        raise ShapingError("TD-SHAPE-112", "This function is not allowed (files, system or random)")
    if _FROM_STRING.search(masked):
        raise ShapingError("TD-SHAPE-112", "Reading files is not allowed")
    # the parser has the last word on what kind of statement this is
    probe = duckdb.connect(":memory:")
    try:
        statements = probe.extract_statements(sql.strip().rstrip(";"))
    except duckdb.Error as exc:
        raise ShapingError("TD-SHAPE-113", f"SQL could not be parsed: {str(exc)[:120]}") from exc
    finally:
        probe.close()
    if len(statements) != 1:
        raise ShapingError("TD-SHAPE-110", "Only one statement is allowed")
    if statements[0].type != duckdb.StatementType.SELECT:
        raise ShapingError("TD-SHAPE-111", "Only SELECT queries are allowed")


def make_locked_connection(inputs: dict[str, Frame]) -> duckdb.DuckDBPyConnection:
    """Fresh in-memory connection: no file/network access, config locked."""
    con = duckdb.connect(":memory:")
    con.execute(f"SET threads={THREADS}")
    con.execute(f"SET memory_limit='{MEMORY_LIMIT}'")
    for stmt in (
        "SET autoinstall_known_extensions=false",
        "SET autoload_known_extensions=false",
        "SET allow_community_extensions=false",
        "SET allow_unsigned_extensions=false",
        "SET enable_external_access=false",
        "SET lock_configuration=true",
    ):
        con.execute(stmt)
    for name, frame in inputs.items():
        if not _NAME.fullmatch(name):
            raise ShapingError("TD-SHAPE-004", f"Invalid table name {name!r}")
        df = as_lazy(frame).collect() if not isinstance(frame, pl.DataFrame) else frame
        con.register(name, df)
    return con


def run_select(sql: str, inputs: dict[str, Frame], timeout_s: float = TIMEOUT_S) -> pl.DataFrame:
    """Validate then run ``sql``; the result is a Polars DataFrame."""
    check_select_only(sql)
    cleaned = sql.strip().rstrip(";").strip()
    con = make_locked_connection(inputs)
    timer = threading.Timer(timeout_s, con.interrupt)
    timer.start()
    try:
        return con.execute(cleaned).pl()
    except duckdb.InterruptException as exc:
        raise ShapingError("TD-SHAPE-115", f"Query took longer than {timeout_s:.0f} s") from exc
    except duckdb.Error as exc:
        raise ShapingError("TD-SHAPE-113", str(exc).splitlines()[0][:200]) from exc
    finally:
        timer.cancel()
        con.close()
```

`infer_schema(sql, schemas: dict[str, dict]) -> dict` (used by the editor diagnostics): `check_select_only`, `make_locked_connection` over zero-row `pl.DataFrame(schema=...)` inputs, execute `SELECT * FROM (` + newline + `<sql>` + newline + `) AS _q LIMIT 0` (the newline before `)` stops a trailing `--` comment from swallowing it), return `dict(result.schema.items())`; a `duckdb.Error` becomes `ShapingError("TD-SHAPE-113", first message line[:200])`.

```python
DEFAULTS = {"sql": "SELECT *\nFROM t1"}

def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    """frames = [t1, t2, t3]; unconnected inputs are None."""
    inputs = {f"t{i + 1}": f for i, f in enumerate(frames) if f is not None}
    out = run_select(settings["sql"], inputs)
    return [normalize_to_supported_dtypes(out).lazy()]
```

`diagnostics(sql, schemas) -> list[dict]` (also in `sql_query.py`) calls `infer_schema` and returns `[{"message": exc.detail, "category": "execution"}]` on `ShapingError`, else `[]`.


### 3.9 Generated-code imports (for plan 08's named-import policy)

Generated code of every shaping node is exactly `import json`, `import polars as pl` and one named import `from <module> import <function> as _run_node`; an unwired node emits only `import polars as pl`. Nothing else is imported by generated code.

| Node | Module | Function |
|---|---|---|
| Record ID | `trigger_designer.core.shaping.record_id` | `run_node` |
| Select Records | `trigger_designer.core.shaping.select_records` | `run_node` |
| Find and Replace | `trigger_designer.core.shaping.find_replace` | `run_node` |
| Date Helper | `trigger_designer.core.shaping.date_helper` | `run_node` |
| Pivot | `trigger_designer.core.shaping.reshape` | `run_pivot` |
| Unpivot | `trigger_designer.core.shaping.reshape` | `run_unpivot` |
| Reconcile | `trigger_designer.core.shaping.reconcile` | `run_node` (all modules share the name `run_node`; there is no `run_reconcile`) |
| Window | `trigger_designer.core.shaping.window` | `run_node` |
| Text to Columns | `trigger_designer.core.shaping.text_to_columns` | `run_node` |
| Fuzzy Match | `trigger_designer.core.shaping.fuzzy` | `run_node` |
| Multi-Field Formula | `trigger_designer.core.shaping.multi_formula` | `run_node` |
| SQL Query | `trigger_designer.core.shaping.sql_query` | `run_node`; **engine entry** inside it: `trigger_designer.core.sql_guard.run_select` (generated code does not import it) |
| Comment | none (`# Comment (not executed)`) | none |

Allow-list for plan 08: the module/function pairs above, plus transitively `trigger_designer.core.shaping.common`, `.assign`, `trigger_designer.core.sql_guard` and `trigger_designer.core.utils.dtype_utils` (imported by those modules, not by generated code).

### 3.10 Enum members and `node_configuration.py` appends

Appended by this plan (names fixed so other plans can check for collisions; op id = `<family>.<member in lower case>`): `PreparationNodes`: `RECORD_ID`, `SELECT_RECORDS`, `FIND_REPLACE`, `DATE_HELPER`, `TEXT_TO_COLUMNS`, `MULTI_FIELD_FORMULA`. `JoinNodes`: `RECONCILE`, `FUZZY_MATCH`. `TransformNodes`: `PIVOT`, `UNPIVOT`, `WINDOW`, `SQL_QUERY`. `ReportNodes`: `COMMENT`. No registry dict, `_OPCODE_ENUMS` or `V1_OPCODE_TO_OP` entry is added or edited (`V1_OPCODE_TO_OP`, lines 92-121, stays frozen).

Appends by plans 04, 05, 06 and this plan to the same enums are **order-independent**: the persisted identity is the stable op-id string (the member name), the integer value is only used for palette ordering and drag payloads within one session, and the legacy integer map is frozen. A merge conflict at the end of an enum is resolved by keeping every member in any order; a real clash exists only if two plans choose the same member name, which the list above lets them check.

---

## 4. The nodes

Code excerpts below omit imports: start each core module with `from __future__ import annotations`, `import polars as pl` and `from trigger_designer.core.shaping.common import <the helpers it uses>`. Common to every node (not repeated below): module pair `core/shaping/<core>.py` + `qt/widgets/nodes/<Folder>/<node>.py`; `_LAZY_NODE_SPECS` entry with title and icon equal to the class; the `.tds` content is `{"settings": {...}}`; dock built from `FORM` (3.4); undo through `set_setting` (one step per real change, `"<HISTORY> <label> Changed"`); unwired input -> empty-state label, outputs still defined by `get_code`; error tooltip `[TD-SHAPE-NNN] ...`. Validation always runs inside `run_node`, so live and Run raise identical errors. "Reused icon" ids exist in `qt/resources.json`.

### 4.1 Record ID (P1) - `preparation.record_id`

**Purpose.** Adds a numbered column so every row can be cited. **Core:** `core/shaping/record_id.py`. **Node:** `Preparation/record_id.py` (template in 3.4), icon `node_count` (reused), title `Record ID`, 1 input, 1 output.

| Setting | Default | Rule |
|---|---|---|
| `name` | `"RecordID"` | trimmed; empty -> 001; existing column -> 002 |
| `start` | `1` | any int; first number |
| `position` | `"first"` | `first` or `last` column |
| `group_by` | `[]` | numbering restarts per group |
| `order_by` | `[]` | `[{"column", "descending"}]`; numbering order inside a group |

**Ordering rule (stable):** numbers follow `group_by`, then `order_by` columns (nulls last), then input position; **rows keep their input order**. Dtype `Int64`; dense (`start..start+n-1`, per group `start..start+k-1`) and unique.

```python
POS = "__pos"

DEFAULTS = {
    "name": "RecordID",
    "start": 1,
    "position": "first",
    "group_by": [],
    "order_by": [],  # [{"column": str, "descending": bool}]
}

def normalize(s: dict) -> dict:
    out = {**DEFAULTS, **(s or {})}
    out["start"] = int(out["start"])
    out["name"] = str(out["name"]).strip()
    return out

def apply_record_id(frame: Frame, settings: dict) -> pl.LazyFrame:
    s = normalize(settings)
    lf = as_lazy(frame)
    schema = schema_of(lf)
    if not s["name"]:
        raise ShapingError("TD-SHAPE-001", "Record ID column name is empty")
    if s["name"] in schema or s["name"] == POS:
        raise ShapingError("TD-SHAPE-002", f"Column '{s['name']}' already exists", [s["name"]])
    order_cols = [o["column"] for o in s["order_by"]]
    require_columns(schema, list(s["group_by"]) + order_cols)

    if not s["group_by"] and not order_cols:
        out = lf.with_row_index(s["name"], offset=s["start"]).with_columns(pl.col(s["name"]).cast(pl.Int64))
    else:
        lf = lf.with_row_index(POS)
        keys = order_cols + [POS]
        desc = [bool(o.get("descending")) for o in s["order_by"]] + [False]
        number = pl.int_range(pl.len(), dtype=pl.Int64) + s["start"]
        if s["group_by"]:
            number = number.over(s["group_by"])
        out = (
            lf.sort(keys, descending=desc, nulls_last=True, maintain_order=True)
            .with_columns(number.alias(s["name"]))
            .sort(POS, maintain_order=True)
            .drop(POS)
        )
    cols = list(schema)
    order = [s["name"], *cols] if s["position"] == "first" else [*cols, s["name"]]
    return out.select(order)

def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    return [apply_record_id(frames[0], settings)]
```

Errors: `TD-SHAPE-001` empty name, `-002` name exists, `-003` unknown column. No chips.

### 4.2 Select Records (P1) - `preparation.select_records`

**Purpose.** First/last N rows, a row range, or the N largest/smallest by a column; the other rows leave through a second output. **Core:** `select_records.py` (`run_node` returns `[selected, rest]`). **Node:** `Preparation/select_records.py`, icon `node_select` (reused), title `Select Records`, 1 input, outputs `S` (selected), `R` (rest).

| Setting | Default | Rule |
|---|---|---|
| `mode` | `"first_n"` | `first_n`, `last_n`, `row_range`, `largest_n`, `smallest_n` |
| `n` | `10` | >= 1 |
| `range_start`, `range_end` | `1`, `100` | 1-based inclusive, `1 <= start <= end` |
| `by` | `""` | ranking column (text is read as numbers, unreadable -> null, **nulls are never selected**) |
| `ties` | `"exact"` | `exact` = exactly N (ties go to the earlier input row), `include_ties` = may return more than N |
| `group_by` | `[]` | N applies per group (not for `row_range`) |

`selected` keeps input order for first/last/range; for largest/smallest it is listed by rank (largest descending, smallest ascending, ties by input position). `rest` keeps input order; `selected + rest` is always the whole input.

```python
POS = "__pos"

MODES = ("first_n", "last_n", "row_range", "largest_n", "smallest_n")

DEFAULTS = {
    "mode": "first_n",
    "n": 10,
    "range_start": 1,
    "range_end": 100,
    "by": "",
    "ties": "exact",
    "group_by": [],
}

def apply_select_records(frame: Frame, settings: dict) -> tuple[pl.LazyFrame, pl.LazyFrame]:
    """Return (selected, rest). Both keep the input columns only."""
    s = {**DEFAULTS, **(settings or {})}
    lf = as_lazy(frame)
    schema = schema_of(lf)
    if s["mode"] not in MODES:
        raise ShapingError("TD-SHAPE-004", f"Unknown mode {s['mode']!r}")
    n = int(s["n"])
    if s["mode"] != "row_range" and n < 1:
        raise ShapingError("TD-SHAPE-004", "N must be at least 1")
    if s["mode"] == "row_range" and not (1 <= int(s["range_start"]) <= int(s["range_end"])):
        raise ShapingError("TD-SHAPE-004", "Row range must satisfy 1 <= start <= end")
    grp = list(s["group_by"])
    require_columns(schema, grp)

    def over(e: pl.Expr) -> pl.Expr:
        return e.over(grp) if grp else e

    lf = lf.with_row_index(POS)
    ranked = None
    if s["mode"] == "first_n":
        keep = over(pl.int_range(pl.len())) < n
    elif s["mode"] == "last_n":
        keep = over(pl.int_range(pl.len())) >= over(pl.len()) - n
    elif s["mode"] == "row_range":
        keep = pl.col(POS).is_between(int(s["range_start"]) - 1, int(s["range_end"]) - 1)
    else:
        if not s["by"]:
            raise ShapingError("TD-SHAPE-001", "Pick the column to rank by")
        require_columns(schema, [s["by"]])
        largest = s["mode"] == "largest_n"
        lf = lf.with_columns(numeric_expr(s["by"], schema[s["by"]]).alias("__key"))
        method = "min" if s["ties"] == "include_ties" else "ordinal"
        keep = (over(pl.col("__key").rank(method, descending=largest)) <= n).fill_null(False)
        ranked = largest
    lf = lf.with_columns(keep.alias("__keep"))
    selected = lf.filter(pl.col("__keep"))
    if ranked is not None:
        selected = selected.sort(
            ["__key", POS],
            descending=[ranked, False],
            nulls_last=True,
            maintain_order=True,
        )
    rest = lf.filter(~pl.col("__keep"))
    drop = ["__keep", "__key", POS]
    return selected.drop(drop, strict=False), rest.drop(drop, strict=False)

def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    return list(apply_select_records(frames[0], settings))
```

```python
FORM = (("", (
    Field("mode", "Mode", "combo", options=(("first_n", "First N rows"), ("last_n", "Last N rows"), ("row_range", "Row range"),
          ("largest_n", "Largest N by column"), ("smallest_n", "Smallest N by column"))),
    Field("n", "N", "int", minimum=1, maximum=100_000_000, show_if=lambda s: s["mode"] != "row_range"),
    Field("range_start", "From row", "int", minimum=1, maximum=100_000_000, show_if=lambda s: s["mode"] == "row_range"),
    Field("range_end", "To row", "int", minimum=1, maximum=100_000_000, show_if=lambda s: s["mode"] == "row_range"),
    Field("by", "Rank by", "column", filter="numeric", blank=True, show_if=lambda s: s["mode"] in ("largest_n", "smallest_n")),
    Field("ties", "Ties", "combo", options=(("exact", "Exactly N rows"), ("include_ties", "Include ties")),
          show_if=lambda s: s["mode"] in ("largest_n", "smallest_n")),
    Field("group_by", "Per group", "columns", show_if=lambda s: s["mode"] != "row_range"),
)),)
```
Errors: `-001` rank column missing, `-003`, `-004` (N < 1, bad range, unknown mode).

### 4.3 Find and Replace (P1) - `preparation.find_replace`

**Decision on the stub:** implement in `Preparation/find_replace.py` and `git rm src/trigger_designer/qt/widgets/nodes/Join/find_replace.py` (0 bytes, unreferenced). *Reason:* the palette tab follows `NodeTypes`, not the folder, and a text-cleanup node belongs to Preparation. Icon `node_cleanser` (reused), title `Find and Replace`, 1 in, 1 out. Core `find_replace.py`.

| Setting | Default | Rule |
|---|---|---|
| `columns` | `[]` | text columns to change (>= 1; non-text -> 044) |
| `rules` | `[]` | ordered, max 50; each `{find, replace, mode, case_sensitive, whole_cell, enabled}` with defaults `"", "", "literal", False, False, True` |
| `suffix` | `""` | blank = replace in place; else results go to `<column><suffix>` (original kept; existing name -> 002) |

Semantics: rules run top to bottom on each selected column, nulls stay null. `literal` matches the text exactly (a `$` in the replacement is literal); `regex` uses the Rust syntax of Polars (capture groups `$1`, `${name}`; write `$$` for a literal `$` in the replacement; no backreferences or lookaround; linear time). `whole_cell` anchors the pattern to the entire cell. `case_sensitive=False` (default, as in Excel) adds `(?i)`. Find cannot be empty (042), longer than 500 characters is 041, an invalid pattern is 040 (validated by running it on an empty string with the same engine), more than 50 rules is 043. Chip: `"<n> cells change (first 10,000 rows)"` (accent) or warning when 0, from `changed_cell_counts` (`describe`).

```python
_RUST_META = re.compile(r"([\\.+*?()|\[\]{}^$#&\-~])")

def escape_rust(text: str) -> str:
    """Escape only characters that are meta in the Rust regex crate."""
    return _RUST_META.sub(r"\\\1", text)

def _pattern(rule: dict) -> tuple[str, str]:
    """(regex pattern, replacement) in Rust-regex syntax for ``rule``."""
    if rule["mode"] == "regex":
        pat, rep = rule["find"], rule["replace"]
    else:
        pat, rep = escape_rust(rule["find"]), rule["replace"].replace("$", "$$")
    if rule["whole_cell"]:
        pat = f"^(?:{pat})$"
    if not rule["case_sensitive"]:
        pat = f"(?i){pat}"
    return pat, rep

def validate_rules(rules: list[dict]) -> list[dict]:
    """Normalise and validate; raises ShapingError(TD-SHAPE-04x)."""
    if len(rules) > MAX_RULES:
        raise ShapingError("TD-SHAPE-043", f"At most {MAX_RULES} rules are allowed")
    out = []
    for i, raw in enumerate(rules, start=1):
        rule = {**RULE_DEFAULTS, **raw}
        if rule["mode"] not in ("literal", "regex"):
            raise ShapingError("TD-SHAPE-004", f"Rule {i}: unknown mode")
        if rule["find"] == "":
            raise ShapingError("TD-SHAPE-042", f"Rule {i}: 'Find' is empty")
        if len(rule["find"]) > MAX_PATTERN_LEN:
            raise ShapingError("TD-SHAPE-041", f"Rule {i}: pattern longer than {MAX_PATTERN_LEN}")
        pat, rep = _pattern(rule)
        try:  # compile with the engine that will run it (linear time, no backrefs)
            pl.select(pl.lit("").str.replace_all(pat, rep))
        except Exception as exc:  # noqa: BLE001
            raise ShapingError("TD-SHAPE-040", f"Rule {i}: invalid pattern ({str(exc)[:80]})") from exc
        out.append(rule)
    return out

def _rule_expr(expr: pl.Expr, rule: dict) -> pl.Expr:
    if rule["mode"] == "literal" and rule["whole_cell"]:
        if rule["case_sensitive"]:
            hit = expr == rule["find"]
        else:
            hit = expr.str.to_lowercase() == rule["find"].lower()
        return pl.when(hit).then(pl.lit(rule["replace"])).otherwise(expr)
    if rule["mode"] == "literal" and rule["case_sensitive"] and not rule["whole_cell"]:
        return expr.str.replace_all(rule["find"], rule["replace"], literal=True)
    pat, rep = _pattern(rule)
    return expr.str.replace_all(pat, rep)
```

Driver (write it from these facts): `apply_find_replace(frame, settings)` validates `columns` (>= 1 -> 001, exist -> 003, all `String` -> 044), runs `validate_rules`, rejects a clashing `<column><suffix>` (002), returns the frame unchanged when no rule is enabled, else `lf.with_columns([<expression per column>.alias(column + suffix)])` where the expression applies every enabled rule in order with `_rule_expr`. `changed_cell_counts(frame, settings)` returns, for the first 10,000 rows, `{column: int((original.ne_missing(new)).sum())}`; `describe` turns the total into the chip.

```python
FORM = (("Columns", (Field("columns", "Columns", "columns", filter="text"),)), ("Rules", (
    Field("rules", "Rule", "list", max_items=50,
          item_default={"find": "", "replace": "", "mode": "literal", "case_sensitive": False, "whole_cell": False, "enabled": True},
          items=(Field("find", "Find", "text"), Field("replace", "Replace", "text"),
                 Field("mode", "Mode", "combo", options=(("literal", "Literal"), ("regex", "Regex"))),
                 Field("case_sensitive", "Match case", "check"), Field("whole_cell", "Whole cell", "check"), Field("enabled", "On", "check"))),
    Field("suffix", "New column suffix", "text", placeholder="blank = replace in place"),
)))
```

### 4.4 Date Helper (P1) - `preparation.date_helper`

Icon `node_formula` (reused), title `Date Helper`, 1 in, 1 out, core `date_helper.py`. Appends one column per operation, in list order; source columns may be Date, Datetime (date part used) or text (parsed with `date_format`, unreadable -> null and a warning chip `"<n> unreadable dates in <col>"`).

| Setting | Default | Rule |
|---|---|---|
| `fiscal_start_month` | `1` | 1-12; FY is named by the calendar year in which it **ends** (start 4: Apr 2024 -> FY2025; start 1 -> calendar year) |
| `working_days` | `["Mon","Tue","Wed","Thu","Fri"]` | at least one (053); defines `is_weekend`, business-day logic |
| `holidays` | `""` | `YYYY-MM-DD` separated by spaces, commas or new lines (bad value -> 052) |
| `date_format` | `"auto"` | `auto` or a strftime pattern (offered: `%Y-%m-%d`, `%d/%m/%Y`, `%m/%d/%Y`, `%d-%b-%Y`, `%Y%m%d`, `%d.%m.%Y`) |
| `roll` | `"forward"` | `add_business_days` from a non-business day: `forward` or `backward` |
| `ops` | `[]` | `{op, source, source2, n, n_column, name}`; blank `name` -> `<source>_<op>` (two-date ops `<a>_to_<b>_<op>`); clashes -> 002 |

| `op` | Uses | Output |
|---|---|---|
| `weekday_name` / `weekday_number` | source | `"Wednesday"` / Int64 Mon=1..Sun=7 |
| `is_weekend` | source | Boolean: weekday not in `working_days` |
| `is_month_end` | source | Boolean: date equals its month end |
| `quarter` | source | Int64 1-4 (calendar) |
| `fiscal_year` / `fiscal_period` / `fiscal_quarter` | source | Int64; period `(month - start) % 12 + 1`, quarter `((month - start) % 12) // 3 + 1` |
| `days_between` | source, source2 | Int64 `source2 - source` in days (negative if earlier) |
| `add_days` | source, `n` or `n_column` | Date `source + n days` (negative subtracts) |
| `add_business_days` | source, `n` or `n_column` | Date, working days and holidays honoured |
| `is_business_day` | source | Boolean |
| `business_days_between` | source, source2 | Int64 `pl.business_day_count`: `[start, end)` forward, negative when reversed |

```python
def date_expr(name: str, dtype: pl.DataType, fmt: str) -> pl.Expr:
    col = pl.col(name)
    if dtype == pl.Date:
        return col
    if isinstance(dtype, pl.Datetime):
        return col.dt.date()
    if dtype == pl.String:
        return col.str.to_date(None if fmt == "auto" else fmt, strict=False)
    raise ShapingError("TD-SHAPE-050", f"Column '{name}' is not a date or text", [name])

def _op_expr(op: dict, s: dict, d1: pl.Expr, d2: pl.Expr | None) -> pl.Expr:
    kind = op["op"]
    mask, hol = tuple(s["week_mask"]), s["holidays_parsed"]
    fm = int(s["fiscal_start_month"])
    month = d1.dt.month()
    if kind == "weekday_name":
        return d1.dt.to_string("%A")
    if kind == "weekday_number":
        return d1.dt.weekday().cast(pl.Int64)
    if kind == "is_weekend":
        return ~d1.dt.weekday().replace_strict({i + 1: mask[i] for i in range(7)}, return_dtype=pl.Boolean)
    if kind == "is_month_end":
        return d1 == d1.dt.month_end()
    if kind == "quarter":
        return d1.dt.quarter().cast(pl.Int64)
    if kind == "fiscal_year":  # named by the calendar year in which it ends
        bump = (month >= fm).cast(pl.Int64) if fm != 1 else pl.lit(0, pl.Int64)
        return d1.dt.year().cast(pl.Int64) + bump
    if kind == "fiscal_period":
        return ((month - fm) % 12 + 1).cast(pl.Int64)
    if kind == "fiscal_quarter":
        return (((month - fm) % 12) // 3 + 1).cast(pl.Int64)
    if kind == "days_between":
        return (d2 - d1).dt.total_days()
    n = pl.col(op["n_column"]).cast(pl.Int64, strict=False) if op["n_column"] else pl.lit(int(op["n"]), pl.Int64)
    if kind == "add_days":
        return d1 + pl.duration(days=n)
    if kind == "add_business_days":
        return d1.dt.add_business_days(n, week_mask=mask, holidays=hol, roll=s["roll"])
    if kind == "is_business_day":
        return d1.dt.is_business_day(week_mask=mask, holidays=hol)
    return pl.business_day_count(d1, d2, week_mask=mask, holidays=hol)  # business_days_between
```

Driver: `normalize` builds `week_mask = [d in working_days for d in ("Mon",...,"Sun")]` (none true -> 053) and `holidays_parsed = sorted({date.fromisoformat(h) for h in re.split(r"[\s,;]+", holidays) if h})` (bad -> 052), checks every op (known name, source set, `source2` set for the two-date ops, default name), `fiscal_start_month` in 1..12 (004); `apply_date_helper` requires the source/second/`n_column` columns (003), refuses output names that already exist or repeat (002), then `lf.with_columns([_op_expr(op, s, d1, d2).alias(op["name"]) ...])` with `d1/d2 = date_expr(...)` per source. `parse_failures(frame, settings)` counts, per text source column in the first 10,000 rows, non-null values whose `date_expr` is null; `describe` returns `(f"{n} unreadable dates in {col}", "warning")` for each.

```python
FORM = (("Calendar", (
    Field("fiscal_start_month", "Fiscal year starts", "combo", options=tuple((m, n) for m, n in enumerate(("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"), 1))),
    Field("working_days", "Working days", "choices", options=tuple((d, d) for d in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"))),
    Field("holidays", "Holidays", "textarea", placeholder="2024-12-25 (one per line)"),
    Field("date_format", "Text dates", "combo", options=(("auto", "Auto-detect"), ("%Y-%m-%d", "2024-12-31"), ("%d/%m/%Y", "31/12/2024"), ("%m/%d/%Y", "12/31/2024"), ("%d-%b-%Y", "31-Dec-2024"), ("%Y%m%d", "20241231"), ("%d.%m.%Y", "31.12.2024"))),
    Field("roll", "From a non-working day", "combo", options=(("forward", "Roll forward"), ("backward", "Roll backward"))))),
 ("Calculations", (Field("ops", "Calculation", "list", item_default={"op": "weekday_name", "source": "", "source2": "", "n": 0, "n_column": "", "name": ""}, items=(
    Field("op", "Calculation", "combo", options=tuple((o, o.replace("_", " ").capitalize()) for o in core.OPS)),
    Field("source", "Date column", "column", filter="date"), Field("source2", "Second date", "column", filter="date", blank=True),
    Field("n", "Days", "int", minimum=-100_000, maximum=100_000), Field("n_column", "Days from column", "column", filter="numeric", blank=True),
    Field("name", "Output name", "text"))),)))
```
(`fiscal_start_month` is stored as the combo's value; the combo's itemData is an `int`, so the saved JSON holds an integer.)

### 4.5 Pivot (P1) - `transform.pivot`

Icon `node_transpose` (reused), title `Pivot`, 1 in, 1 out, core `reshape.py` (`run_pivot`, `RUNNER = "run_pivot"`), `LIVE_CAP_ROWS = 5_000_000`.

| Setting | Default | Rule |
|---|---|---|
| `index_columns` | `[]` | row labels (may be empty -> one row) |
| `header_column` | `""` | its distinct values become columns |
| `value_column` | `""` | what is aggregated (not in `index_columns`, not the header; else 060) |
| `aggregation` | `"sum"` | `sum, mean, min, max, median, first, last, count` (the first five read text as numbers; `count` counts non-null) |
| `blank_label` | `"(blank)"` | name of the column for null headers |
| `missing_as` | `"null"` | cells with no data: `null` or `zero` |

Rules: header columns are ordered by the **natural order of the original dtype** (numbers numerically, dates chronologically, text lexicographically, null last), named with `str()`; a name equal to an index column or an earlier header gets `_2`, `_3`; rows sorted by the index columns (nulls last); a cell with no data is **null** (Polars' own `sum` pivot would give 0, which would invent data, so the node pre-aggregates with `group_by` and pivots with `first`); a group whose values are all null sums to null; more than 500 distinct headers -> 061.

```python
def _agg_expr(agg: str, col: str) -> pl.Expr:
    c = pl.col(col)
    return {
        "sum": pl.when(c.is_not_null().any()).then(c.sum()), "mean": c.mean(), "min": c.min(), "max": c.max(),
        "median": c.median(), "first": c.first(), "last": c.last(),
        "count": c.count().cast(pl.Int64),
    }[agg].alias(col)  # fmt: skip

def apply_pivot(frame: Frame, settings: dict) -> pl.DataFrame:
    s = {**PIVOT_DEFAULTS, **(settings or {})}
    lf = as_lazy(frame)
    schema = schema_of(lf)
    idx, hdr, val = list(s["index_columns"]), s["header_column"], s["value_column"]
    if not hdr or not val:
        raise ShapingError("TD-SHAPE-001", "Pick the header column and the value column")
    if s["aggregation"] not in AGGS:
        raise ShapingError("TD-SHAPE-004", f"Unknown aggregation {s['aggregation']!r}")
    require_columns(schema, idx + [hdr, val])
    if hdr in idx or val in idx or hdr == val:
        raise ShapingError("TD-SHAPE-060", "Index, header and value columns must differ")

    value = pl.col(val)
    if s["aggregation"] in NUMERIC_AGGS:
        value = numeric_expr(val, schema[val])
    base = lf.select(*[pl.col(c) for c in idx], pl.col(hdr), value.alias(val))
    agg = base.group_by(idx + [hdr]).agg(_agg_expr(s["aggregation"], val))
    agg = agg.collect()

    distinct = agg.select(hdr).unique().sort(hdr, nulls_last=True)[hdr].to_list()
    if len(distinct) > MAX_PIVOT_COLUMNS:
        raise ShapingError(
            "TD-SHAPE-061",
            f"Header column has {len(distinct)} distinct values (limit {MAX_PIVOT_COLUMNS})",
            [hdr],
        )
    taken = list(idx)
    names: list[str] = []
    for v in distinct:
        name = unique_name(s["blank_label"] if v is None else str(v), taken)
        taken.append(name)
        names.append(name)
    mapping = {v: n for v, n in zip(distinct, names) if v is not None}
    hdr_name = pl.col(hdr).replace_strict(mapping, return_dtype=pl.String) if mapping else pl.lit(None, pl.String)
    blank = next((n for v, n in zip(distinct, names) if v is None), None)
    if blank is not None:
        hdr_name = pl.when(pl.col(hdr).is_null()).then(pl.lit(blank)).otherwise(hdr_name)
    agg = agg.with_columns(hdr_name.alias("__hdr")).drop(hdr)
    if idx:
        wide = agg.pivot(on="__hdr", on_columns=names, index=idx, values=val,
                         aggregate_function="first", maintain_order=True)  # fmt: skip
        wide = wide.sort(idx, nulls_last=True, maintain_order=True)
    else:
        wide = agg.pivot(on="__hdr", on_columns=names, values=val, aggregate_function="first")
    wide = wide.select(idx + names)
    if s["missing_as"] == "zero":
        wide = wide.with_columns(pl.col(names).fill_null(0))
    return wide
```

Constants: `MAX_PIVOT_COLUMNS = 500`, `AGGS = ("sum","mean","min","max","median","first","last","count")`, `NUMERIC_AGGS = {"sum","mean","min","max","median"}`, `PIVOT_DEFAULTS` = the settings table; `run_pivot(frames, settings) = [apply_pivot(frames[0], settings).lazy()]`. `_agg_expr(agg, col)` maps the name to the Polars aggregation aliased `col`, with `sum` written `pl.when(c.is_not_null().any()).then(c.sum())` (all-null group -> null) and `count` as `c.count().cast(pl.Int64)`.

```python
FORM = (("", (Field("index_columns", "Row labels", "columns"), Field("header_column", "Column headers", "column"),
              Field("value_column", "Values", "column"),
              Field("aggregation", "Aggregate", "combo", options=tuple((a, a.capitalize()) for a in core.AGGS)),
              Field("blank_label", "Blank header", "text"),
              Field("missing_as", "Empty cells", "combo", options=(("null", "Blank"), ("zero", "Zero"))))),)
```
Errors: `-001`, `-003`, `-004` (aggregation), `-060`, `-061`.

### 4.6 Unpivot (P1) - `transform.unpivot`

Icon `node_transpose` (reused), title `Unpivot`, 1 in, 1 out, `RUNNER = "run_unpivot"`.

| Setting | Default | Rule |
|---|---|---|
| `id_columns` | `[]` | kept as they are |
| `value_columns` | `[]` | >= 1; not also an id (060) |
| `variable_name` / `value_name` | `"Attribute"` / `"Value"` | distinct, not id names (002) |
| `drop_nulls` | `False` | drop rows whose value is null (needed for the exact Pivot round trip) |

Output order is **row-major**: for each input row, its value columns in the chosen order (Polars emits column-major; the node sorts back by input position). If the value columns' dtypes differ they are cast to `Float64` when all numeric, else to `String`.

```python
def apply_unpivot(frame: Frame, settings: dict) -> pl.LazyFrame:
    s = {**UNPIVOT_DEFAULTS, **(settings or {})}
    lf = as_lazy(frame)
    schema = schema_of(lf)
    ids, vals = list(s["id_columns"]), list(s["value_columns"])
    if not vals:
        raise ShapingError("TD-SHAPE-001", "Pick at least one column to unpivot")
    require_columns(schema, ids + vals)
    if set(ids) & set(vals):
        raise ShapingError("TD-SHAPE-060", "A column cannot be both an ID and a value column")
    var, valn = s["variable_name"].strip(), s["value_name"].strip()
    if not var or not valn or var == valn or {var, valn} & set(ids):
        raise ShapingError("TD-SHAPE-002", "Name and value column names must be unique")
    dtypes = {schema[c] for c in vals}
    if len(dtypes) > 1:
        target = pl.Float64 if all(schema[c].is_numeric() for c in vals) else pl.String
        lf = lf.with_columns(pl.col(vals).cast(target))
    out = (
        lf.with_row_index("__pos")
        .unpivot(on=vals, index=["__pos"] + ids, variable_name=var, value_name=valn)
        .sort("__pos", maintain_order=True)
        .drop("__pos")
    )
    if s["drop_nulls"]:
        out = out.filter(pl.col(valn).is_not_null())
    return out.select(ids + [var, valn])
```

`UNPIVOT_DEFAULTS` = the settings table; `run_unpivot(frames, settings) = [apply_unpivot(frames[0], settings)]`.

```python
FORM = (("", (Field("id_columns", "Keep columns", "columns"), Field("value_columns", "Unpivot columns", "columns"),
              Field("variable_name", "Name column", "text"), Field("value_name", "Value column", "text"),
              Field("drop_nulls", "Drop empty values", "check"))),)
```

### 4.7 Comment (P1) - `report.comment`

**Purpose.** A note on the canvas that never executes; it is saved in the `.tds`, shown above the node as a floating label, and exported for the workpaper and run log. **Decisions:** family `ReportNodes` (no new family; the Report tab holds nodes that produce no data), module `Documentation/comment.py` (the existing 0-byte stub, so no move), icon `node_unique` (reused), title `Comment`, **0 inputs, 0 outputs**, op id `report.comment`. Its text is `settings["text"]` (default `""`); the floating label is the first line, cut to 60 characters, set with `node.setNodeLabel(label, store_history=False)` inside `after_change` (a manual label edit is overwritten by the next text change; reason: one source of truth). `get_code()` returns `"# Comment (not executed)\n"`: the executor runs it as a no-op that succeeds (verified with the scaffolding: label, undo/redo, serialize, `NodeExecutor` success with no variables, `execution_results[node] == {}`), so "every node has a result" checks stay green. `eval()` returns `[]` (valid).

```python
class CommentContent(ShapingContent):
    SETTINGS = {"text": ""}
    MODULE = "trigger_designer.core.shaping.comments"
    INPUTS, OUTPUT_KINDS, HISTORY = 0, (), "Comment"
    FORM = (("", (Field("text", "Comment", "textarea", placeholder="Note for the reviewer"),)),)

    def ready(self):
        return True  # no input to wait for

    def compute(self):
        self.outputs = []
        return []

    def get_code(self):
        return "# Comment (not executed)
"

    def after_change(self):
        lines = (self.settings.get("text") or "").strip().splitlines()
        label = lines[0][:60] if lines else ""
        if self.node.getNodeLabel() != label:
            self.node.setNodeLabel(label, store_history=False)
```
Node class: `output_text = ()`, `register_node(ReportNodes.COMMENT, NodeTypes.REPORT)`. Plans 02 and 06 read comments with `comments.py` (Qt-free; section 11).

```python
COMMENT_OP = "report.comment"

#: ops that never execute; the run log records them as "skipped"
NOT_EXECUTABLE_OPS = frozenset({COMMENT_OP})

@dataclass(frozen=True)
class CommentRecord:
    node_id: int
    text: str
    x: float
    y: float

def _sorted(records: list[CommentRecord]) -> list[CommentRecord]:
    return sorted(records, key=lambda c: (c.y, c.x, c.node_id))  # reading order

def comments_from_scene_dict(scene: dict[str, Any]) -> list[CommentRecord]:
    """Comments in a ``TriggerScene.serialize()`` dict / loaded ``.tds`` (Qt-free)."""
    found = []
    for node in scene.get("nodes", []):
        if node.get("op") != COMMENT_OP:
            continue
        settings = (node.get("content") or {}).get("settings") or {}
        text = str(settings.get("text", "")).strip()
        if text:
            found.append(
                CommentRecord(
                    int(node["id"]),
                    text,
                    float(node.get("pos_x", 0.0)),
                    float(node.get("pos_y", 0.0)),
                )
            )
    return _sorted(found)
```

`comments_from_nodes(nodes)` is the same for live nodes: op id `f"{node.node_type.value}.{node.node_code.name.lower()}"`, text `node.content.settings["text"]`, position `node.grNode.pos()`, same sort `(y, x, node_id)`.

### 4.8 Reconcile (P1) - `join.reconcile`

**Purpose.** Match two datasets on key columns plus an amount tolerance and/or a date window and report matched pairs, both leftovers and a summary. Icon `node_join` (reused), title `Reconcile`, **2 inputs** (top = Left, bottom = Right), **4 outputs** `M` Matched, `L` Left unmatched, `R` Right unmatched, `S` Summary. Core `reconcile.py` + `assign.py`; `LIVE_CAP_ROWS = 200_000`.

| Setting | Default | Rule |
|---|---|---|
| `match_type` | `"one_to_one"` | `one_to_one`, `one_to_many` (one left, many right), `many_to_one`, `many_to_many` |
| `key_pairs` | `[]` | `[{"left","right"}]`; equality after trim + lower-case (text cast); null keys never match |
| `amount_left`, `amount_right` | `""` | both or neither (070); text read as numbers |
| `tolerance_mode`, `tolerance` | `"absolute"`, `0.0` | `absolute` amount units, or `percent` **of the left amount** (left 0 -> exact); compared after rounding to 6 decimals |
| `date_left`, `date_right`, `date_window_days` | `""`, `""`, `0` | both or neither; `|right - left| <= window`; ignored for `many_to_many` |

Needs at least one key pair or a date pair (071). Candidate pairs: join on the keys; with no keys, date buckets of `max(window, 1)` days probe three neighbouring buckets. **Guard:** the pair count is computed from group sizes *before* joining and more than 5,000,000 pairs -> `TD-SHAPE-072`.

**Algorithms (deterministic; all ties end in input row position):**
* **one_to_one - greedy by quality.** Keep candidates within amount tolerance **and** date window. Rank pairs by `(|amount diff|, |day gap|, left position, right position)` ascending. Walk the ranked list; accept a pair when neither row is used yet. Implemented as rounds of *mutual best* pairs (`assign.greedy_one_to_one`): a pair that is the best remaining pair for both of its rows cannot be beaten, so all such pairs are accepted at once; each round accepts at least the globally best pair, so it ends (after 200 rounds the rest runs sequentially). Equal to the sequential walk (tested on 300 random cases). A row is never matched twice.
* **one_to_many / many_to_one - greedy by owner.** The "many" side is the right (resp. left) side. Candidates are key matches within the date window (amount is **not** tested per pair). Every "many" row joins the single best "one" row (smallest day gap, then earliest position). Matched rows of one "one" row form a group; the group's **total** amount is compared with the "one" amount using the tolerance: `Match_Status` = `Within tolerance` or `Outside tolerance` (`Matched` when no amount is set). Outside-tolerance groups stay in `Matched` so the reviewer sees the difference; filter on `Match_Status`.
* **many_to_many - group totals.** Rows are grouped by the normalised keys on each side; groups present on both sides are matched, totals compared as above. Rows are listed side by side by position inside the group (the shorter side shows nulls). *Reason:* an explainable, order-independent rule for a workpaper; allocation algorithms hide judgement.

**Outputs.** `Matched`: `Match_ID` (1-based group/pair number), `Match_Status`, `Amount_Diff` (**right minus left**, 6 decimals; group difference in group modes; only if amounts set), `Date_Gap_Days` (right - left; not in many_to_many), then all left columns, then all right columns (a right name that equals a left name gets `_right`). `Left unmatched` / `Right unmatched`: the original columns plus `Unmatched_Reason`: `No candidate with the same key` (or `... within the date window` when there are no keys), `Candidates outside tolerance`, `Candidates already matched`. `Summary`: one row, these columns in this order (amounts null when no amount is set; counts `Int64`, the rest `Float64`, `Match_Type` text):

| Column | Definition |
|---|---|
| `Match_Type`, `Left_Rows`, `Right_Rows` | setting and input heights |
| `Matched_Groups` | distinct `Match_ID` |
| `Left_Matched_Rows`, `Right_Matched_Rows`, `Left_Unmatched_Rows`, `Right_Unmatched_Rows` | distinct matched row counts; unmatched output heights |
| `Left_Match_Rate_Pct`, `Right_Match_Rate_Pct` | `round(100 * matched / rows, 2)`, null for 0 rows |
| `Left_Total`, `Right_Total` | sums of the amount columns over all rows |
| `Matched_Left_Total`, `Matched_Right_Total` | sums over matched rows |
| `Matched_Net_Difference` | `Matched_Right_Total - Matched_Left_Total` (6 decimals) |
| `Matched_Abs_Difference` | sum of `abs(Amount_Diff)` per group (6 decimals) |
| `Left_Unmatched_Total`, `Right_Unmatched_Total` | sums over unmatched rows |
| `Net_Difference_Total` | `Right_Total - Left_Total` |
| `Within_Tolerance_Groups`, `Outside_Tolerance_Groups` | groups by `Match_Status` (all `Within` in one_to_one) |

Write `_summary` from this table (the tests in 7.2 fix the numbers). Module (verified; `_summary` and the `Summary` schema are omitted here and follow the table: build one dict with the 21 keys and `pl.DataFrame([row], schema=SUMMARY)` where `SUMMARY` maps each column to the dtype stated above):

```python
"""Deterministic one-to-one assignment shared by Reconcile and Fuzzy Match."""

from __future__ import annotations

import polars as pl

MAX_ROUNDS = 200


def greedy_one_to_one(cand: pl.DataFrame) -> pl.DataFrame:
    """Pick pairs so that no ``__l`` and no ``__r`` is used twice.

    ``cand`` must have integer columns ``__l`` and ``__r`` and be sorted so that
    row 0 is the best pair (the caller owns the ranking; ties are broken by
    row order, so the result is fully deterministic).

    The result equals the sequential greedy "walk the sorted list, accept a
    pair when both sides are free" (see greedy_sequential). It is computed in
    rounds: a pair that is the best remaining pair for BOTH its left and its
    right row cannot be beaten by any other pair, so all such pairs are accepted
    at once. Every round accepts at least the globally best pair, so it ends.

    Returns the accepted rows (all columns of ``cand``) in ``cand`` order.
    """
    remaining = cand.with_row_index("__rank")
    accepted: list[pl.DataFrame] = []
    for _ in range(MAX_ROUNDS):
        if remaining.is_empty():
            break
        best_l = remaining.unique("__l", keep="first", maintain_order=True)
        best_r = remaining.unique("__r", keep="first", maintain_order=True)
        mutual = best_l.filter(pl.col("__rank").is_in(best_r["__rank"].implode()))
        accepted.append(mutual)
        remaining = remaining.filter(~pl.col("__l").is_in(mutual["__l"].implode()) & ~pl.col("__r").is_in(mutual["__r"].implode()))
    if not remaining.is_empty():  # pathological chains: finish sequentially
        accepted.append(_sequential(remaining))
    if not accepted:
        return cand.head(0)
    return pl.concat(accepted).sort("__rank").drop("__rank")


def _sequential(ranked: pl.DataFrame) -> pl.DataFrame:
    used_l: set[int] = set()
    used_r: set[int] = set()
    keep: list[int] = []
    for rank, l_id, r_id in zip(ranked["__rank"], ranked["__l"], ranked["__r"]):
        if l_id not in used_l and r_id not in used_r:
            used_l.add(l_id)
            used_r.add(r_id)
            keep.append(rank)
    return ranked.filter(pl.col("__rank").is_in(pl.Series(keep, dtype=pl.UInt32).implode()))


def greedy_sequential(cand: pl.DataFrame) -> pl.DataFrame:
    """Reference implementation used by tests (slow, obviously correct)."""
    return _sequential(cand.with_row_index("__rank")).sort("__rank").drop("__rank")
```

```python
"""Reconcile two frames: tolerance matching with four deterministic match types."""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl
from trigger_designer.core.shaping.assign import greedy_one_to_one
from trigger_designer.core.shaping.common import (
    Frame, ShapingError, as_lazy, estimate_pairs, numeric_expr, require_columns, schema_of, unique_name,
)  # fmt: skip

MAX_CANDIDATE_PAIRS = 5_000_000
MATCH_TYPES = ("one_to_one", "one_to_many", "many_to_one", "many_to_many")
DEFAULTS = {
    "match_type": "one_to_one",
    "key_pairs": [],  # [{"left": col, "right": col}] equality after trim + lower-case
    "amount_left": "", "amount_right": "",  # "" = no amount test
    "tolerance_mode": "absolute",  # "absolute" | "percent" (of the left amount)
    "tolerance": 0.0,
    "date_left": "", "date_right": "", "date_window_days": 0,  # "" = no date test
}  # fmt: skip
# SUMMARY: {column: dtype} in the table order of section 4.8 (Match_Type String, counts Int64, rest Float64)
PAIR_COLUMNS = ["__mid", "__l", "__r", "__diff", "__gap", "__within", "Match_Status"]


@dataclass
class ReconcileResult:
    matched: pl.DataFrame
    left_unmatched: pl.DataFrame
    right_unmatched: pl.DataFrame
    summary: pl.DataFrame


def normalize(settings: dict) -> dict:
    s = {**DEFAULTS, **(settings or {})}
    if s["match_type"] not in MATCH_TYPES:
        raise ShapingError("TD-SHAPE-004", f"Unknown match type {s['match_type']!r}")
    if s["tolerance_mode"] not in ("absolute", "percent"):
        raise ShapingError("TD-SHAPE-004", "Tolerance mode must be absolute or percent")
    s["tolerance"], s["date_window_days"] = float(s["tolerance"]), int(s["date_window_days"])
    if s["tolerance"] < 0 or s["date_window_days"] < 0:
        raise ShapingError("TD-SHAPE-004", "Tolerance and date window cannot be negative")
    s["key_pairs"] = [p for p in s["key_pairs"] if p.get("left") and p.get("right")]
    if bool(s["amount_left"]) != bool(s["amount_right"]) or bool(s["date_left"]) != bool(s["date_right"]):
        raise ShapingError("TD-SHAPE-070", "Pick the amount/date column on both sides")
    s["has_amount"] = bool(s["amount_left"])
    s["has_date"] = bool(s["date_left"]) and s["match_type"] != "many_to_many"  # m2m ignores dates
    if not s["key_pairs"] and not s["has_date"]:
        raise ShapingError("TD-SHAPE-071", "Add a key column pair or a date window")
    return s


def _date_int(name: str, dtype: pl.DataType) -> pl.Expr:
    col = pl.col(name)
    if dtype == pl.String:
        col = col.str.to_date(strict=False)
    elif isinstance(dtype, pl.Datetime):
        col = col.dt.date()
    elif dtype != pl.Date:
        raise ShapingError("TD-SHAPE-050", f"Column '{name}' is not a date", [name])
    return col.cast(pl.Int32)


def _slim(df: pl.DataFrame, side: str, s: dict) -> pl.DataFrame:
    """Only what matching needs: row id, normalised keys (__k0..), amount (__?a), date (__?d)."""
    sch, name = dict(df.schema), "left" if side == "l" else "right"
    cols = [pl.col(f"__{side}")]
    for i, pair in enumerate(s["key_pairs"]):
        cols.append(pl.col(pair[name]).cast(pl.String).str.strip_chars().str.to_lowercase().alias(f"__k{i}"))
    if s[f"amount_{name}"]:
        cols.append(numeric_expr(s[f"amount_{name}"], sch[s[f"amount_{name}"]]).alias(f"__{side}a"))
    if s[f"date_{name}"] and s["has_date"]:
        cols.append(_date_int(s[f"date_{name}"], sch[s[f"date_{name}"]]).alias(f"__{side}d"))
    return df.select(cols)


def _guard(n: int) -> None:
    if n > MAX_CANDIDATE_PAIRS:
        raise ShapingError(
            "TD-SHAPE-072",
            f"{n:,} possible matches (limit {MAX_CANDIDATE_PAIRS:,}); add a key column or narrow the date window",
        )


def _candidates(ls: pl.DataFrame, rs: pl.DataFrame, s: dict) -> pl.DataFrame:
    keys = [f"__k{i}" for i in range(len(s["key_pairs"]))]
    if keys:
        _guard(estimate_pairs(ls, rs, keys))  # sizes first: never build a huge join
        return ls.join(rs, on=keys, how="inner")  # null keys never match
    size = max(s["date_window_days"], 1)  # no keys: date buckets of `size` days, probe 3 buckets
    probes = pl.DataFrame({"__off": [-1, 0, 1]}, schema={"__off": pl.Int32})
    lb = ls.filter(pl.col("__ld").is_not_null()).join(probes, how="cross")
    lb = lb.with_columns((pl.col("__ld").floordiv(size) + pl.col("__off")).alias("__b")).drop("__off")
    rb = rs.filter(pl.col("__rd").is_not_null()).with_columns(pl.col("__rd").floordiv(size).alias("__b"))
    _guard(estimate_pairs(lb, rb, ["__b"]))
    return lb.join(rb, on="__b", how="inner").drop("__b")


def _within(diff: pl.Expr, base: pl.Expr, s: dict) -> pl.Expr:
    limit = pl.lit(s["tolerance"]) if s["tolerance_mode"] == "absolute" else base.abs() * s["tolerance"] / 100.0
    return (diff.abs().round(6) <= limit.round(6)).fill_null(False)


def _metrics(cand: pl.DataFrame, s: dict) -> pl.DataFrame:
    """__diff = right - left, __adiff, __amt_ok, __gap = right - left days, __agap, __date_ok."""
    cols = []
    if s["has_amount"]:
        d = pl.col("__ra") - pl.col("__la")
        cols += [
            d.round(6).alias("__diff"),
            d.abs().alias("__adiff"),
            _within(d, pl.col("__la"), s).alias("__amt_ok"),
        ]
    else:
        cols += [
            pl.lit(None, pl.Float64).alias("__diff"),
            pl.lit(0.0).alias("__adiff"),
            pl.lit(True).alias("__amt_ok"),
        ]
    if s["has_date"]:
        g = (pl.col("__rd") - pl.col("__ld")).cast(pl.Int64)
        cols += [
            g.alias("__gap"),
            g.abs().alias("__agap"),
            (g.abs() <= s["date_window_days"]).fill_null(False).alias("__date_ok"),
        ]
    else:
        cols += [
            pl.lit(None, pl.Int64).alias("__gap"),
            pl.lit(0, pl.Int64).alias("__agap"),
            pl.lit(True).alias("__date_ok"),
        ]
    return cand.with_columns(cols)


def _status(s: dict) -> pl.Expr:
    if not s["has_amount"]:
        return pl.lit("Matched").alias("Match_Status")
    return pl.when(pl.col("__within")).then(pl.lit("Within tolerance")).otherwise(pl.lit("Outside tolerance")).alias("Match_Status")


def _pairs_one_to_one(cand: pl.DataFrame) -> pl.DataFrame:
    ok = cand.filter(pl.col("__amt_ok") & pl.col("__date_ok")).sort(["__adiff", "__agap", "__l", "__r"])
    taken = greedy_one_to_one(ok).sort("__l").with_row_index("__mid", offset=1)
    return taken.select(
        pl.col("__mid").cast(pl.Int64), "__l", "__r", "__diff", "__gap", pl.lit(True).alias("__within"),
        pl.lit("Within tolerance").alias("Match_Status"),
    )  # fmt: skip


def _pairs_one_to_many(cand: pl.DataFrame, s: dict) -> pl.DataFrame:
    many = "r" if s["match_type"] == "one_to_many" else "l"
    one = "l" if many == "r" else "r"
    ok = cand.filter(pl.col("__date_ok")).sort(["__agap", f"__{one}", f"__{many}"])
    # every 'many' row joins its best 'one' row (smallest date gap, then position)
    p = ok.unique(f"__{many}", keep="first", maintain_order=True).sort([f"__{one}", f"__{many}"])
    p = p.with_columns(pl.col(f"__{one}").rank("dense").cast(pl.Int64).alias("__mid"))
    if s["has_amount"]:
        one_amt, many_sum = pl.col(f"__{one}a").first(), pl.col(f"__{many}a").sum()
        g = p.group_by("__mid").agg(one_amt.alias("__o"), many_sum.alias("__m"))
        sign = 1.0 if one == "l" else -1.0  # __diff is always RIGHT minus LEFT
        g = g.with_columns(
            ((pl.col("__m") - pl.col("__o")) * sign + 0.0).round(6).alias("__diff"),
            _within(pl.col("__m") - pl.col("__o"), pl.col("__o"), s).alias("__within"),
        )
        p = p.drop("__diff").join(g.select("__mid", "__diff", "__within"), on="__mid")
    else:
        p = p.with_columns(pl.lit(None, pl.Float64).alias("__diff"), pl.lit(True).alias("__within"))
    return p.with_columns(_status(s)).select(PAIR_COLUMNS)


def _pairs_many_to_many(ls: pl.DataFrame, rs: pl.DataFrame, s: dict) -> pl.DataFrame:
    keys = [f"__k{i}" for i in range(len(s["key_pairs"]))]
    la = pl.col("__la").sum() if s["has_amount"] else pl.lit(0.0)
    ra = pl.col("__ra").sum() if s["has_amount"] else pl.lit(0.0)
    g = ls.group_by(keys).agg(pl.col("__l").min().alias("__lmin"), la.alias("__gla"))
    g = g.join(rs.group_by(keys).agg(ra.alias("__gra")), on=keys, how="inner")
    g = g.sort("__lmin").with_row_index("__mid", offset=1)
    d = pl.col("__gra") - pl.col("__gla")
    g = g.with_columns(
        pl.col("__mid").cast(pl.Int64),
        (d.round(6) if s["has_amount"] else pl.lit(None, pl.Float64)).alias("__diff"),
        (_within(d, pl.col("__gla"), s) if s["has_amount"] else pl.lit(True)).alias("__within"),
    )
    gk = g.select(keys + ["__mid", "__diff", "__within"])
    lm = ls.join(gk, on=keys).select("__l", "__mid", "__diff", "__within").sort("__mid", "__l")
    rm = rs.join(gk, on=keys).select("__r", "__mid").sort("__mid", "__r")
    lm = lm.with_columns(pl.int_range(pl.len()).over("__mid").alias("__i"))
    rm = rm.with_columns(pl.int_range(pl.len()).over("__mid").alias("__i"))
    # aligned listing: i-th left row beside i-th right row; the shorter side is null
    p = lm.join(rm, on=["__mid", "__i"], how="full", coalesce=True).sort("__mid", "__i")
    p = p.with_columns(
        pl.col("__diff").forward_fill().over("__mid"),
        pl.col("__within").forward_fill().over("__mid"),
        pl.lit(None, pl.Int64).alias("__gap"),
    )
    return p.with_columns(_status(s)).select(PAIR_COLUMNS)


def _unmatched(frame, side, used, key_hit, ok_hit, s) -> pl.DataFrame:
    pos = f"__{side}"
    none = "No candidate with the same key" if s["key_pairs"] else "No candidate within the date window"
    reason = (
        pl.when(~pl.col(pos).is_in(key_hit.implode())).then(pl.lit(none))
        .when(~pl.col(pos).is_in(ok_hit.implode())).then(pl.lit("Candidates outside tolerance"))
        .otherwise(pl.lit("Candidates already matched"))
        .alias("Unmatched_Reason")
    )  # fmt: skip
    return frame.filter(~pl.col(pos).is_in(used.implode())).with_columns(reason).drop(pos)


def _summary(L, R, lu, ru, pairs, s) -> pl.DataFrame:
    """One-row Summary: the 21 columns, order and definitions of the table in section 4.8."""
    raise NotImplementedError


def apply_reconcile(left: Frame, right: Frame, settings: dict) -> ReconcileResult:
    s = normalize(settings)
    lf, rf = as_lazy(left), as_lazy(right)
    for sch, side in ((schema_of(lf), "left"), (schema_of(rf), "right")):
        names = [p[side] for p in s["key_pairs"]] + [c for c in (s[f"amount_{side}"], s[f"date_{side}"]) if c]
        require_columns(sch, names)
    L, R = lf.with_row_index("__l").collect(), rf.with_row_index("__r").collect()
    ls, rs = _slim(L, "l", s), _slim(R, "r", s)
    if s["match_type"] == "many_to_many":
        keys = [f"__k{i}" for i in range(len(s["key_pairs"]))]
        pairs = _pairs_many_to_many(ls, rs, s)
        l_hit = l_ok = ls.join(rs.select(keys).unique(), on=keys, how="semi")["__l"]
        r_hit = r_ok = rs.join(ls.select(keys).unique(), on=keys, how="semi")["__r"]
    else:
        cand = _metrics(_candidates(ls, rs, s), s)
        if s["match_type"] == "one_to_one":
            pairs, ok = (
                _pairs_one_to_one(cand),
                cand.filter(pl.col("__amt_ok") & pl.col("__date_ok")),
            )
        else:
            pairs, ok = _pairs_one_to_many(cand, s), cand.filter(pl.col("__date_ok"))
        l_hit, r_hit, l_ok, r_ok = cand["__l"], cand["__r"], ok["__l"], ok["__r"]

    cols_l = [c for c in L.columns if c != "__l"]
    r_names: dict[str, str] = {}  # right columns that clash with a left name get "_right"
    for c in [c for c in R.columns if c != "__r"]:
        r_names[c] = unique_name(f"{c}_right" if c in cols_l else c, cols_l + list(r_names.values()))
    lead = {"Match_ID": pl.col("__mid"), "Match_Status": pl.col("Match_Status")}
    if s["has_amount"]:
        lead["Amount_Diff"] = pl.col("__diff")
    if s["has_date"]:
        lead["Date_Gap_Days"] = pl.col("__gap")
    matched = (
        pairs.select("__l", "__r", *[e.alias(k) for k, e in lead.items()])
        .join(L, on="__l", how="left").join(R.rename(r_names), on="__r", how="left")
        .sort(["Match_ID", "__l", "__r"], nulls_last=True)
        .select(list(lead) + cols_l + list(r_names.values()))
    )  # fmt: skip
    lu = _unmatched(L, "l", pairs["__l"].drop_nulls(), l_hit, l_ok, s)
    ru = _unmatched(R, "r", pairs["__r"].drop_nulls(), r_hit, r_ok, s)
    return ReconcileResult(matched, lu, ru, _summary(L, R, lu, ru, pairs, s))


def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    r = apply_reconcile(frames[0], frames[1], settings)
    return [r.matched.lazy(), r.left_unmatched.lazy(), r.right_unmatched.lazy(), r.summary.lazy()]
```

```python
FORM = (("Match", (Field("match_type", "Match type", "combo", options=(("one_to_one", "One to one"), ("one_to_many", "One left to many right"), ("many_to_one", "Many left to one right"), ("many_to_many", "Many to many (group totals)"))),
                   Field("key_pairs", "Key", "list", max_items=10, item_default={"left": "", "right": ""},
                         items=(Field("left", "Left column", "column", input=0), Field("right", "Right column", "column", input=1))))),
 ("Amount", (Field("amount_left", "Left amount", "column", input=0, blank=True, filter="numeric"), Field("amount_right", "Right amount", "column", input=1, blank=True, filter="numeric"),
             Field("tolerance_mode", "Tolerance", "combo", options=(("absolute", "Amount"), ("percent", "Percent of left"))), Field("tolerance", "Tolerance value", "float", minimum=0, maximum=1e9))),
 ("Date", (Field("date_left", "Left date", "column", input=0, blank=True, filter="date", show_if=lambda s: s["match_type"] != "many_to_many"),
           Field("date_right", "Right date", "column", input=1, blank=True, filter="date", show_if=lambda s: s["match_type"] != "many_to_many"),
           Field("date_window_days", "Window (days)", "int", maximum=3650, show_if=lambda s: s["match_type"] != "many_to_many"))))
```
`INPUTS = 2`, `OUTPUT_KINDS = ("recon_matched", "recon_left", "recon_right", "recon_summary")`, `HISTORY = "Reconcile"`. Errors: `-003`, `-004`, `-050` (date column not date/text), `-070`, `-071`, `-072`.

### 4.9 Window (P2) - `transform.window`

Icon `node_running_total` (reused), title `Window`, 1 in, 1 out, core `window.py`. Adds one column per operation.

| Setting | Default | Rule |
|---|---|---|
| `partition_by` | `[]` | windows restart per group |
| `order_by` | `[]` | `[{"column","descending"}]`; order inside a group; nulls last; ties by input position |
| `ops` | `[]` | `{op, source, name, offset, window, partial, descending, nulls}` |

| `op` | Meaning | Output dtype / null rule |
|---|---|---|
| `lag` / `lead` | value `offset` (>=1) rows before / after | source dtype; null when out of range or null |
| `row_number` | 1..k in window order | Int64 |
| `rank` / `dense_rank` | rank of the source (`descending` flag; ties share the rank; text read as numbers; null -> null) | Int64 |
| `cum_sum`, `cum_min`, `cum_max`, `cum_mean` | running total / min / max / mean up to the row | Float64; `nulls="skip"` (default): a null row gives null but later rows keep accumulating; `"zero"`: nulls count as 0. `cum_mean` divides by the non-null count |
| `rolling_sum` | sum of the last `window` rows including this one | Float64; `partial=False`: null until `window` non-null rows exist; `True`: sum of what exists |

Blank `name` -> `<source>_lag1`, `<source>_lead1`, `<source>_roll3`, `<source>_<op>`, `Row_Number`; clashes -> 002. Sources of `cum_*`/`rolling_sum` must be numeric or text (091); `rank` also accepts dates. **Method (sort-compute-restore):** `over(order_by=...)` takes one direction flag for all keys, so the node sorts by `partition, order_by..., position` with each key's own direction, computes with `.over(partition)`, then sorts back by position.

```python
def _op_expr(op: dict, dtype: pl.DataType | None) -> pl.Expr:
    kind = op["op"]
    if kind == "row_number":
        return pl.int_range(1, pl.len() + 1, dtype=pl.Int64)
    col = pl.col(op["source"])
    if kind in NUMERIC_OPS and (dtype == pl.String or (dtype is not None and dtype.is_numeric())):
        col = numeric_expr(op["source"], dtype)  # text is read as numbers (bad -> null)
    if kind == "lag":
        return col.shift(op["offset"])
    if kind == "lead":
        return col.shift(-op["offset"])
    if kind in ("rank", "dense_rank"):
        method = "min" if kind == "rank" else "dense"
        return col.rank(method, descending=op["descending"]).cast(pl.Int64)
    if op["nulls"] == "zero":
        col = col.fill_null(0.0)
    if kind == "cum_sum":
        return col.cum_sum()
    if kind == "cum_min":
        return col.cum_min()
    if kind == "cum_max":
        return col.cum_max()
    if kind == "cum_mean":
        return col.cum_sum() / col.is_not_null().cum_sum()
    return col.rolling_sum(  # rolling_sum
        window_size=op["window"], min_samples=1 if op["partial"] else op["window"]
    )
```

Driver: `normalize` fills `OP_DEFAULT` per op, requires `source` for every op except `row_number` (001), `offset`/`window` >= 1 (004), default names as in the table; `apply_window` checks columns (003), numeric/text sources for `cum_*`/`rolling_sum` (091), name clashes (002), then runs the pipeline below. `NUMERIC_OPS = {rank, dense_rank, cum_sum, cum_min, cum_max, cum_mean, rolling_sum}` read text through `numeric_expr`; `OPS` = the ten names in the table.

```python
# apply_window, after validation (verified)
parts = list(s["partition_by"])
keys = parts + order_cols + [POS]
desc = [False] * len(parts) + [bool(o.get("descending")) for o in s["order_by"]] + [False]
exprs = []
for op in s["ops"]:
    e = _op_expr(op, schema.get(op["source"]))
    exprs.append((e.over(parts) if parts else e).alias(op["name"]))
out = (lf.with_row_index(POS)
         .sort(keys, descending=desc, nulls_last=True, maintain_order=True)
         .with_columns(exprs)
         .sort(POS, maintain_order=True).drop(POS))
```
```python
FORM = (("Window", (Field("partition_by", "Restart per", "columns"),
          Field("order_by", "Order by", "list", item_default={"column": "", "descending": False},
                items=(Field("column", "Column", "column"), Field("descending", "Descending", "check"))))),
 ("Calculations", (Field("ops", "Calculation", "list", item_default={"op": "lag", "source": "", "name": "", "offset": 1, "window": 3, "partial": False, "descending": False, "nulls": "skip"},
          items=(Field("op", "Calculation", "combo", options=tuple((o, o.replace("_", " ").capitalize()) for o in core.OPS)),
                 Field("source", "Column", "column", blank=True), Field("name", "Output name", "text"),
                 Field("offset", "Offset", "int", minimum=1, maximum=100_000), Field("window", "Window rows", "int", minimum=1, maximum=100_000),
                 Field("partial", "Allow partial window", "check"), Field("descending", "Rank high to low", "check"),
                 Field("nulls", "Nulls", "combo", options=(("skip", "Skip"), ("zero", "Treat as 0"))))),)))
```
Errors: `-001` (source missing), `-002`, `-003`, `-004` (offset/window < 1, unknown op), `-091`.

### 4.10 Text to Columns (P2) - `preparation.text_to_columns`

Icon `node_split` (reused), title `Text to Columns`, 1 in, 1 out, core `text_to_columns.py`.

| Setting | Default | Rule |
|---|---|---|
| `column` | `""` | text column (044 otherwise) |
| `split_mode`, `pattern` | `"delimiter"`, `","` | delimiter is literal (escapes `\t \n \r \\` accepted); `regex` is Rust syntax and must not match the empty string (101); invalid -> 040 |
| `output` | `"columns"` | `columns` or `rows` |
| `max_splits` | `2` | columns: 1-49, output has `max_splits + 1` columns and the **last receives the remainder**; rows: 0 = unlimited, else the last piece holds the remainder |
| `names` | `""` | columns mode: comma-separated names; missing ones become `<column>_<i>`; clashes get `_2` |
| `trim` | `True` | strip spaces from each piece |
| `keep_original` | `True` | columns mode keeps the source column; rows mode keeps it as `<column>_original` |
| `skip_empty` | `False` | rows mode: drop empty pieces |
| `row_index_column` | `""` | rows mode: name for the 1-based piece number |

Regex mode replaces each match by the sentinel `U+241F` then splits on it (`str.split` has no regex form); a cell that already contains `U+241F` splits there too (documented, accepted).

```python
def apply_text_to_columns(frame: Frame, settings: dict) -> pl.LazyFrame:
    s = normalize(settings)
    lf = as_lazy(frame)
    schema = schema_of(lf)
    require_columns(schema, [s["column"]])
    if schema[s["column"]] != pl.String:
        raise ShapingError("TD-SHAPE-044", "Only text columns can be split", [s["column"]])
    text, sep = _pieces_sep(s)
    if s["output"] == "columns":
        n = s["max_splits"] + 1
        given = [x.strip() for x in str(s["names"]).split(",") if x.strip()][:n]
        taken = list(schema)
        names = []
        for i in range(n):
            base = given[i] if i < len(given) else f"{s['column']}_{i + 1}"
            name = unique_name(base, taken)
            taken.append(name)
            names.append(name)
        parts = text.str.splitn(sep, n)
        exprs = []
        for i, name in enumerate(names):
            piece = parts.struct.field(f"field_{i}")
            exprs.append((piece.str.strip_chars() if s["trim"] else piece).alias(name))
        out = lf.with_columns(exprs)
        if not s["keep_original"]:
            out = out.drop(s["column"])
        return out
    # rows: one output row per piece (other columns repeat)
    n = s["max_splits"] + 1
    if s["max_splits"]:
        parts = text.str.splitn(sep, n)
        lst = pl.concat_list([parts.struct.field(f"field_{i}") for i in range(n)]).list.drop_nulls()
    else:
        lst = text.str.split(sep)
    if s["trim"]:
        lst = lst.list.eval(pl.element().str.strip_chars())
    if s["skip_empty"]:
        lst = lst.list.eval(pl.element().filter(pl.element() != ""))
    out = lf.with_row_index("__pos")
    if s["keep_original"]:
        orig = unique_name(f"{s['column']}_original", schema)
        out = out.with_columns(pl.col(s["column"]).alias(orig))
    out = out.with_columns(lst.alias(s["column"])).explode(s["column"], empty_as_null=True, keep_nulls=True)
    if s["row_index_column"]:
        name = unique_name(s["row_index_column"], out.collect_schema().names())
        out = out.with_columns((pl.int_range(pl.len(), dtype=pl.Int64).over("__pos") + 1).alias(name))
    return out.drop("__pos")
```

`SENTINEL = "\u241f"`, `MAX_COLUMNS = 50`, `_ESCAPES` maps the two characters `\t`, `\n`, `\r`, `\\` to tab, newline, carriage return and one backslash. `normalize` (called first): `column` required (001); delimiter mode un-escapes `\t \n \r \\` (`re.sub(r"\\[tnr\\]", ...)`), empty pattern -> 001; `max_splits` in `1..49` (columns) or `0..49` (rows) else 004; regex mode must compile (040) and must not match `""` (`pl.select(pl.lit("").str.contains(pattern)).item()` true -> 101). `_pieces_sep(s)` returns `(col.str.replace_all(pattern, SENTINEL), SENTINEL)` in regex mode, `(col, pattern)` otherwise.

```python
FORM = (("", (Field("column", "Column", "column", filter="text"),
   Field("split_mode", "Split by", "combo", options=(("delimiter", "Delimiter"), ("regex", "Regex"))), Field("pattern", "Pattern", "text"),
   Field("output", "Output", "combo", options=(("columns", "Columns"), ("rows", "Rows"))),
   Field("max_splits", "Max splits", "int", maximum=49), Field("names", "Column names", "text", placeholder="a, b, c", show_if=lambda s: s["output"] == "columns"),
   Field("trim", "Trim spaces", "check"), Field("keep_original", "Keep original", "check"),
   Field("skip_empty", "Skip empty", "check", show_if=lambda s: s["output"] == "rows"),
   Field("row_index_column", "Piece number name", "text", show_if=lambda s: s["output"] == "rows"))),)
```

### 4.11 Fuzzy Match (P2) - `join.fuzzy_match`

Icon `node_join` (reused), title `Fuzzy Match`, **2 inputs**, **3 outputs** `M` Matched, `L` Left unmatched, `R` Right unmatched, core `fuzzy.py` (+ `assign.py`), `LIVE_CAP_ROWS = 200_000`.

| Setting | Default | Rule |
|---|---|---|
| `left_column`, `right_column` | `""` | text columns (001) |
| `algorithm` | `"jaro_winkler"` | DuckDB `jaro_winkler_similarity`, or `levenshtein` as `1 - distance / max(len)` |
| `threshold` | `0.85` | `0 < t <= 1`; pairs scoring below are dropped |
| `blocking` | `"prefix"` | candidate pairs must share a blocking key: `prefix` (first `prefix_length` characters of the normalised text), `first_token`, or `none` (only when `left rows x right rows <= 1,000,000`, else 082) |
| `prefix_length` | `3` | 1-10 |
| `block_columns` | `[]` | extra `{left,right}` columns that must match exactly (trim, lower-case) |
| `strip_suffixes` | `True` | removes `inc, ltd, llc, plc, corp, co, gmbh, ag, sa, pty, pvt, bv, nv, lp, llp, ...` words before comparing |
| `assignment` | `"one_to_one"` | `one_to_one` (greedy by score, `assign.greedy_one_to_one`), `best_per_left`, `all_pairs` |

**Normalisation** (both sides): lower-case, every run of non-letter/non-digit becomes one space, optional suffix words removed, spaces collapsed and trimmed; rows empty after that never match. **Why blocking:** comparing all pairs is O(n x m); the pair count is computed from block sizes first and more than 5,000,000 pairs -> `TD-SHAPE-081`. **Why lower-casing first:** DuckDB's similarity is case-sensitive. Ranking: score descending, then left position, then right position. Matched output: `Match_ID`, `Match_Score` (4 decimals), all left columns, all right columns (clash -> `_right`; a clash with `Match_Score` gets `_2`).

```python
SUFFIX_WORDS = "inc|incorporated|ltd|limited|llc|plc|corp|corporation|co|company|gmbh|ag|sa|pty|pvt|bv|nv|lp|llp"

def normalize_text(expr: pl.Expr, strip_suffixes: bool) -> pl.Expr:
    """lower-case, punctuation to spaces, optional company suffixes removed."""
    e = expr.cast(pl.String).str.to_lowercase()
    e = e.str.replace_all(r"[^\p{L}\p{N}]+", " ")
    if strip_suffixes:
        e = e.str.replace_all(rf"\b(?:{SUFFIX_WORDS})\b", " ")
    return e.str.replace_all(r"\s+", " ").str.strip_chars()

def _block_expr(norm: pl.Expr, s: dict) -> pl.Expr:
    if s["blocking"] == "prefix":
        return norm.str.slice(0, s["prefix_length"])
    if s["blocking"] == "first_token":
        return norm.str.split(" ").list.first()
    return pl.lit("")

def score_pairs(cand: pl.DataFrame, algorithm: str) -> pl.DataFrame:
    """Add ``__score`` using DuckDB string functions (in-memory, no files)."""
    con = duckdb.connect(":memory:")
    try:
        con.register("cand", cand.to_arrow())
        if algorithm == "jaro_winkler":
            score = "jaro_winkler_similarity(__ln, __rn)"
        else:
            score = "1.0 - levenshtein(__ln, __rn)::DOUBLE / greatest(length(__ln), length(__rn))"
        return con.execute(f"SELECT __l, __r, {score} AS __score FROM cand").pl()
    finally:
        con.close()
```

`apply_fuzzy` outline (verified; write it like `apply_reconcile`'s tail): collect both frames with `with_row_index("__l"/"__r")`; build slim frames (`__ln`, `__blk`, block columns `__x0..`; drop empty normalised text); `estimate_pairs` guard; `cand = ls.join(rs, on=["__blk", "__x0", ...])`; `scored = score_pairs(cand.select("__l","__r","__ln","__rn"), algorithm)`; `filter(score >= threshold)`; `sort([score desc, __l, __r])`; assignment per setting; `Match_ID = row number after sorting by (__l, __r)`; unmatched = input rows whose id is not in the pairs.

```python
FORM = (("Compare", (Field("left_column", "Left text", "column", input=0, filter="text"), Field("right_column", "Right text", "column", input=1, filter="text"),
          Field("algorithm", "Algorithm", "combo", options=(("jaro_winkler", "Jaro-Winkler"), ("levenshtein", "Levenshtein ratio"))),
          Field("threshold", "Minimum score", "float", minimum=0.01, maximum=1.0), Field("strip_suffixes", "Ignore Inc/Ltd/LLC", "check"),
          Field("assignment", "Pairs", "combo", options=(("one_to_one", "One to one"), ("best_per_left", "Best per left row"), ("all_pairs", "All pairs"))))),
 ("Speed", (Field("blocking", "Block on", "combo", options=(("prefix", "First characters"), ("first_token", "First word"), ("none", "Nothing (small data)"))),
            Field("prefix_length", "Characters", "int", minimum=1, maximum=10, show_if=lambda s: s["blocking"] == "prefix"),
            Field("block_columns", "Must also match", "list", max_items=5, item_default={"left": "", "right": ""},
                  items=(Field("left", "Left column", "column", input=0), Field("right", "Right column", "column", input=1))))))
```
Errors: `-001`, `-003`, `-004`, `-081`, `-082`. `threshold` is a `float` field with 2 decimals.

### 4.12 Multi-Field Formula (P3) - `preparation.multi_field_formula`

Icon `node_formula` (reused), title `Multi-Field Formula`, 1 in, 1 out, core `multi_formula.py` (uses `core/sql_guard.py`, F7), `LIVE_CAP_ROWS = 2_000_000`.

| Setting | Default | Rule |
|---|---|---|
| `columns` | `[]` | 1-200 columns |
| `template` | `""` | one DuckDB SQL expression; `{col}` is replaced by the quoted column, `{name}` by the column's name as a text literal; must contain `{col}` (120); `;` -> 110 |
| `mode` | `"in_place"` | `in_place` (`SELECT * REPLACE`, order kept) or `suffix` |
| `suffix` | `"_new"` | `suffix` mode; blank -> 001; existing name -> 002 |

Each substitution is wrapped in parentheses. The composed query goes through `sql_guard.run_select`, so the same read-only guarantees apply (section 4.13); result dtypes pass `normalize_to_supported_dtypes`.

```python
def quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'

def quote_text(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"

def expression_for(template: str, column: str) -> str:
    """Substitute the placeholders; wrapped in parentheses to keep precedence."""
    return "(" + template.replace("{col}", quote_ident(column)).replace("{name}", quote_text(column)) + ")"

def build_query(columns: list[str], template: str, mode: str, suffix: str) -> str:
    if mode == "in_place":
        parts = ", ".join(f"{expression_for(template, c)} AS {quote_ident(c)}" for c in columns)
        return f"SELECT * REPLACE ({parts}) FROM t1"
    parts = ", ".join(f"{expression_for(template, c)} AS {quote_ident(c + suffix)}" for c in columns)
    return f"SELECT *, {parts} FROM t1"
```

Driver: `normalize` (001 no columns, 004 more than 200 columns or unknown mode, 120 missing `{col}`, 110 `;`, 001 blank suffix in suffix mode); `apply_multi_formula(frame, settings)` requires the columns (003), refuses an existing `<column><suffix>` (002), runs `run_select(build_query(...), {"t1": lf.collect()})` and returns `normalize_to_supported_dtypes(out).lazy()`.

```python
FORM = (("", (Field("columns", "Columns", "columns"),
   Field("template", "Formula", "textarea", placeholder="UPPER(TRIM({col}))   or   TRY_CAST({col} AS DOUBLE)"),
   Field("mode", "Result", "combo", options=(("in_place", "Replace the columns"), ("suffix", "Add new columns"))),
   Field("suffix", "New column suffix", "text", show_if=lambda s: s["mode"] == "suffix"))),)
```
Errors: `-001`, `-002`, `-003`, `-004`, `-110`, `-111`/`-112` (sandbox), `-113` (DuckDB error text, first line), `-120`.

### 4.13 SQL Query (P3) - `transform.sql_query`

Icon `node_formula` (reused), title `SQL Query`, **3 inputs** `t1` (required), `t2`, `t3` (optional, F2), 1 output, core `sql_query.py` + `sql_guard.py`, `LIVE_CAP_ROWS = 2_000_000`. Setting `sql` (default `"SELECT *\nFROM t1"`). The query sees only the connected inputs as tables `t1..t3` (referencing an unconnected one gives DuckDB's catalog error, `-113`). Result: `normalize_to_supported_dtypes(...)`. Row order follows the query (no `ORDER BY` keeps input order for simple selects).

**Read-only enforcement** is the standalone `core/sql_guard.py` (section 3.8, created in foundation step F7). This node is its first consumer; its `run_node` calls `sql_guard.run_select(sql, {"t1": ..., "t2": ..., "t3": ...})` (the "engine entry" listed in 3.9).

**SQL editor reuse (the Formula editor, patched once).** The editor completes and validates columns as `[name]` (formula syntax), which is wrong for SQL (`a[1]` is list indexing). Add a switch to `qt/widgets/sql_formula_editor.py`, default unchanged:
1. `SQLFormulaEditor.__init__` (near line 416): `self.bracket_columns: bool = True`.
2. `match_completions(prefix, in_brackets, column_names, bracket=True)` (line 249): in the final loop use `label = f"[{col}]" if bracket else (col if col.isidentifier() else '"' + col.replace('"', '""') + '"')`; the caller (line 514) passes `bracket=self.bracket_columns`; `_prefix_at_cursor` returns `in_brackets=False` when `not self.bracket_columns`.
3. Line 635: `if self.bracket_columns and not any(error.get("category") == "syntax" for error in self.errors):`.
Because `set_validate_callback` is set, the editor ignores its sqlglot "expression" syntax check (`:614-619` else-branch), so a full `SELECT` is not mis-flagged.

`SqlQueryContent._make_widget` overrides the `"sql"` kind only: a container `QWidget` holding `SQLFormulaWidget` (`editor.bracket_columns = False`, `set_available_columns(["t1","t2","t3"] + all input column names)`, `set_validate_callback(lambda text: sql_query.diagnostics(text, {f"t{i+1}": self.schema(i) for i in range(3) if self.frames[i] is not None}))`, text via `set_text`, changes through `textChanged` -> the 300 ms debounce) and a `QLabel` (objectName `formulaSectionError`, word wrap, hidden) fed by `editor.allErrorsDetected` (shows the first message). Diagnostics call `infer_schema` (`SELECT * FROM (<sql>) LIMIT 0` on zero-row inputs): instant and touches no real data. `_sync_widgets_from_model` for `"sql"` writes with `widget.set_text` only when the text differs, inside `blockSignals`.

```python
FORM = (("Query", (Field("sql", "SQL", "sql"),)),)   # "sql" is handled by SqlQueryContent._make_widget
```
`INPUTS = 3`, `OPTIONAL_INPUTS = frozenset({1, 2})`, node `output_text = ("",)`, `OUTPUT_KINDS = ("sql",)`, `HISTORY = "SQL Query"`. Errors: `-001`, `-110`..`-115`.

---

## 5. Ordered implementation steps

One commit per step. Before every commit: `.venv\Scripts\python.exe -m ruff format <files>`, then `-m ruff check <files>` (only the files you touched; the repo baseline is not clean, brief 2.3), then the step's tests. Use `.venv\Scripts\python.exe` directly (not `uv run`, brief 2.2). Never run bare `pytest`. Baseline to protect: unit 334 pass, e2e 20 pass, ui 404 pass + 27 known failures (brief 2.4).

### 5.1 Foundations

| Step | Commit message | Files | Done when |
|---|---|---|---|
| F1 | `Add shaping core helpers` | new `core/shaping/common.py` (3.2); `tests/unit/test_shaping_common.py` | `pytest tests\unit\test_shaping_common.py -q` green: every `ERROR_CODES` key matches `^TD-SHAPE-\d{3}$`, `unique_name("a", ["a","a_2"]) == "a_3"`, `numeric_expr` turns `"1,234.5"` into `1234.5` and `"x"` into null, `estimate_pairs` of keys `[a,a,b]` vs `[a,b,b]` is 4 |
| F2 | `Allow optional node inputs` | `qt/node_base.py` (3.3); `tests/unit/test_shaping_support.py::test_optional_inputs_*` | the 3-input probe node evaluates with input 0 wired; a 2-input existing node (Append) with input 1 unwired is still invalid; `pytest tests\unit\test_node_base.py tests\unit\test_batch_evaluation.py tests\unit\test_shaping_support.py -q` green |
| F3 | `Add RuleStack widget` | `qt/widgets/common/config_widgets.py` (+ `Any` import), `qt/widgets/common/__init__.py`, `resources/qt/themes/base.qss`, `qss/_style.scss`; `tests/ui/test_rule_stack.py` | `pytest tests\ui\test_rule_stack.py tests\unit\test_theme_tokens.py -q` green: add/remove/move signals fire with the right indexes, move buttons disabled at the ends, `add_button` has tooltip and accessible name |
| F4 | `Add shaping node scaffolding` | new `qt/helpers/shaping_support.py` (3.4); `tests/support/shaping_probe.py` (a 10-line `DEFAULTS`/`run_node` that numbers rows); `tests/unit/test_shaping_support.py`, `tests/ui/test_shaping_scaffold.py` | probe node: live equals `exec(get_code())`; unwired `get_code` defines its output; settings survive `serialize`/`deserialize` and old files get defaults; two outputs of one source feed two inputs correctly (`single_source=True`); dock edit -> one undo step -> undo -> redo -> `updateConfig(force=True)`; list add/move/remove undo |
| F5 | `Add shaping test helpers` | new `tests/support/shaping.py` (3.5 + 7.6 `run_shaping_workflow`) | imported by F4's tests; `ruff check` clean |
| F6 | `Document shaping packaging` | no `trigger.spec` edit (3.6: provided by plan 09 F-G); `docs/NODE_REFERENCE.md` gets the Union row | docs row present |
| F7 | `Add SQL guard` | new `core/sql_guard.py` (3.8); `tests/unit/test_sql_guard.py` (7.3: 57 cases, engine lock, limits) | `pytest tests\unit\test_sql_guard.py -q` green; lands **before** plan 09 F-H2 and before step 12 |

### 5.2 One commit per node

Every node commit touches the same nine places; only names differ.

| # | File | Change |
|---|---|---|
| a | `core/node_configuration.py` | append the enum member at the end of its family enum (`:48`, `:54`, `:61`, `:65`) |
| b | `core/shaping/<core>.py` | the Qt-free module (section 4) with `DEFAULTS`, `run_node`, optional `describe`; add its error codes to `ERROR_CODES` only if new |
| c | `qt/widgets/nodes/<Folder>/<node>.py` | content + node classes (template 3.4), `@register_node(...)` |
| d | `qt/widgets/nodes/__init__.py` | `_LAZY_NODE_SPECS` entry `{"module_path": "<Folder>.<stem>", "node_code": <Enum>.X, "node_type": NodeTypes.Y, "node_title": "<Title>", "icon": "<reused icon>"}` |
| e | `tests/unit/test_shaping_<core>.py` | the core tests of section 7.2 for that node |
| f | `tests/unit/test_shaping_nodes.py` | add the node to the parametrized table: registry title/icon/op id, live == codegen, unwired outputs defined, serialize round trip |
| g | `tests/ui/test_shaping_docks.py` | add the node to the parametrized dock table (7.5) |
| h | `tests/e2e/test_shaping_goldens.py` + `tests/e2e/fixtures/shaping/*.csv` + `tests/e2e/fixtures/expected/shaping_<node>*.csv` | the e2e case of section 7.6 |
| i | `docs/NODE_REFERENCE.md` | one table row |

| Step | Node | Enum / module | Extra |
|---|---|---|---|
| 1 | Record ID | `PreparationNodes.RECORD_ID`, `Preparation/record_id.py` | first user of the scaffolding; fix scaffolding bugs here, in the F4 files |
| 2 | Select Records | `PreparationNodes.SELECT_RECORDS`, `Preparation/select_records.py` | `output_text = ("S", "R")` |
| 3 | Find and Replace | `PreparationNodes.FIND_REPLACE`, `Preparation/find_replace.py` | `git rm src/trigger_designer/qt/widgets/nodes/Join/find_replace.py` in the same commit; ReDoS test |
| 4 | Date Helper | `PreparationNodes.DATE_HELPER`, `Preparation/date_helper.py` | |
| 5 | Pivot | `TransformNodes.PIVOT`, `Transform/pivot.py` | `RUNNER = "run_pivot"`, `LIVE_CAP_ROWS = 5_000_000` |
| 6 | Unpivot | `TransformNodes.UNPIVOT`, `Transform/unpivot.py` | `RUNNER = "run_unpivot"`; round-trip property test |
| 7 | Comment | `ReportNodes.COMMENT`, `Documentation/comment.py` | overrides `ready/compute/get_code/after_change`; no sockets |
| 8 | Reconcile | `JoinNodes.RECONCILE`, `Join/reconcile.py` | new `core/shaping/assign.py`; `INPUTS = 2`, 4 outputs, `output_text = ("M","L","R","S")`, `LIVE_CAP_ROWS = 200_000` |
| 9 | Window | `TransformNodes.WINDOW`, `Transform/window.py` | |
| 10 | Text to Columns | `PreparationNodes.TEXT_TO_COLUMNS`, `Preparation/text_to_columns.py` | |
| 11 | Fuzzy Match | `JoinNodes.FUZZY_MATCH`, `Join/fuzzy_match.py` | reuses `assign.py`; `INPUTS = 2`, 3 outputs `("M","L","R")` |
| 12 | Multi-Field Formula | `PreparationNodes.MULTI_FIELD_FORMULA`, `Preparation/multi_field_formula.py` | uses `core/sql_guard.py` (F7); no new guard code |
| 13 | SQL Query | `TransformNodes.SQL_QUERY`, `Transform/sql_query.py` | `core/shaping/sql_query.py`; `INPUTS = 3`, `OPTIONAL_INPUTS = frozenset({1, 2})`; SQL editor patch (4.13) with its UI tests |

Per-node "done when" (run from the repo root):
```powershell
.venv\Scripts\python.exe -m ruff format <touched files>; .venv\Scripts\python.exe -m ruff check <touched files>
.venv\Scripts\python.exe -m pytest tests\unit\test_shaping_<core>.py tests\unit\test_shaping_nodes.py tests\unit\test_node_titles.py -q
.venv\Scripts\python.exe -m pytest tests\ui\test_shaping_docks.py -q -k "<node>"
.venv\Scripts\python.exe -m pytest tests\e2e\test_shaping_goldens.py -q -k "<node>"
```
Manual smoke (brief 3.7 step 14): drop the node unwired -> Run completes (no `NameError`); wire a File Input -> Run; save, reload, Run again; undo/redo a setting; select it and watch the Data Preview.

Step-specific notes the implementer must follow:
* **Step 3:** after the `git rm`, `git grep find_replace` must show only the new module, its tests and docs.
* **Step 7:** after saving a workflow containing a Comment, `comments_from_scene_dict(json.load(open(tds)))` must return its text (e2e test).
* **Step 8:** write `_summary` from the table in 4.8; the numbers in 7.2 are the acceptance values.
* **Step 12:** `sql_guard.py` already exists (F7); run its 57-case table before wiring the node.
* **Step 13:** apply the three SQL-editor edits, then run `tests\ui\test_formula_node.py tests\ui\test_formula_focus.py` and compare with the brief's 5 known failures (no new ones allowed).

---

## 6. Edge cases per node

All nodes: zero input rows -> outputs are typed and empty (verified for every `run_node`); a selected column that vanished upstream -> `TD-SHAPE-003` (dock shows it as `<name> (missing)`); null cells never raise.

| Node | Edge cases and the decided behaviour |
|---|---|
| Record ID | `order_by` on text sorts lexicographically (`"10" < "5"`; cast first for numeric order); descending still puts nulls last; `start` negative is fine; group with nulls is one group; name equal to `__pos` -> 002 |
| Select Records | `n` larger than the input returns everything; `largest_n` with all-null key selects nothing and `rest` is the whole input; `last_n` per group takes each group's last rows in input order; `row_range` past the end returns what exists; text key `"x"` or `""` is null; `include_ties` with N=1 and three equal maxima returns three rows |
| Find and Replace | replacement longer/shorter changes length freely; regex that matches empty (`x*`) replaces at every position (user's choice); `suffix` leaves other columns alone; changing a non-text column is refused (044) rather than casting; `$` handling differs by mode (4.3); chip counts only the first 10,000 rows |
| Date Helper | text with mixed formats: auto mode reads the first value's pattern, others become null and are counted in the warning chip; Datetime values lose the time; `add_business_days` from a holiday rolls per `roll`; `business_days_between` reversed dates give negative counts that are not the mirror of the forward count (half-open on the other side); holidays are de-duplicated; two operations with the same output name -> 002 |
| Pivot | null headers become the `blank_label` column; duplicate (index, header) cells are aggregated; numeric headers sort numerically, so `9` precedes `10`; `count` of a cell whose values are all null is 0, while a cell with no rows is null (0 with `missing_as=zero`); header values that are not valid names are kept as text; 501 distinct headers -> 061 |
| Unpivot | zero value columns -> 001; duplicate id/value overlap -> 060; empty frame -> three typed columns; mixed int/text value columns become text (`"1"`, `"x"`) |
| Comment | empty text is allowed (no label); very long text is stored whole, only the first line (60 chars) is the label; a Comment never has edges (no sockets); undo restores both text and label |
| Reconcile | duplicate keys on both sides are resolved by quality then position (7.2); right row with the same key as two left rows matches the better left only; amounts like `"1,000.50"` are read; a text amount `"x"` is null and never within tolerance; percent tolerance on a left amount of 0 requires an exact match; `many_to_many` with one empty side matches nothing; date pair on text dates uses `to_date(strict=False)`; a right column named like a left one becomes `<name>_right`; one source feeding both inputs works |
| Window | `lag` of a text column stays text; `rank` on text reads numbers; `rolling_sum` with fewer rows than `window` is null unless `partial`; `row_number` ignores `source`; without `partition_by` the whole frame is one window; `order_by` empty uses input order |
| Text to Columns | `max_splits=2` on `"a-b"` gives `a`, `b`, null; null cell -> all nulls; empty cell -> first piece `""`; `trim` also trims the remainder piece; rows mode with `skip_empty` and an all-empty cell yields one null row (the row is kept); names list longer than the columns is ignored; clash with an existing column -> `_2` |
| Fuzzy Match | null/empty/punctuation-only text never matches; identical normalised names score 1.0; `one_to_one` can leave a lower-ranked left row unmatched when its best right row is taken; more than 5,000,000 candidate pairs -> 081 before any scoring; `levenshtein` ratio of two empty strings is excluded |
| Multi-Field Formula | a column name with quotes is escaped (`"` doubled); `{name}` inside a string literal is still substituted (it is plain text replacement); template that returns a different type per column is fine (each output column has its own type); result dtypes are widened by `normalize_to_supported_dtypes` |
| SQL Query | unconnected `t2` referenced -> 113 with DuckDB's catalog message; result with duplicate column names is renamed by DuckDB (`a`, `a_1`); empty result keeps the column types; query over zero-row inputs (schema probe) never touches real data; a 20,001-character query -> 114; a query over 25 s -> 115 |

---

## 7. Test plan

The reference implementations in sections 3-4 passed these tests (127 cases; the full list below is the executable spec - when a test and this prose disagree, the test wins and the prose is fixed). Layers per brief 9: `tests/unit` (core, no widgets), `tests/ui` (docks), `tests/e2e` (goldens), `tests/benchmarks` (opt-in). New files:

| File | Content |
|---|---|
| `tests/unit/test_shaping_common.py`, `test_shaping_<core>.py` (one per core module) | 7.2-7.4 |
| `tests/unit/test_shaping_support.py` | scaffolding: optional inputs, live == codegen, unwired outputs, serialize/defaults, two outputs of one source |
| `tests/unit/test_shaping_nodes.py` | parametrized over all 13 nodes: registry, title/icon pin, op id, live == codegen, unwired, round trip |
| `tests/ui/test_rule_stack.py`, `test_shaping_scaffold.py`, `test_shaping_docks.py` | 7.5 |
| `tests/e2e/test_shaping_goldens.py` (+ `tests/support/shaping.py::run_shaping_workflow`) | 7.6 |
| `tests/benchmarks/test_shaping_perf.py` | 7.7 |

### 7.1 Shared fixtures (put in each core test file as needed)

```python
RID = pl.DataFrame({"acct": list("ABACBA"), "amt": ["10", "5", "7", None, "x", "7"], "d": [1, 2, 3, 4, 5, 6]})
FR = pl.DataFrame({"name": ["Acme Inc.", "ACME inc", "foo 123-45", "a$b", None, "Acme"], "n": list("123456")})
DH = pl.DataFrame({"d": ["2024-01-31", "2024-02-29", "2024-03-30", "2024-04-01", "2024-12-31", "bad", None],
                   "e": ["2024-02-05", "2024-02-29", "2024-04-01", "2024-03-01", "2025-01-02", "2024-01-01", "2024-01-01"], "n": [1, 2, 3, 4, 5, 6, 7]})
PV = pl.DataFrame({"acct": list("AABABBC"), "period": ["10", "9", "10", "10", "9", None, "g"], "amt": ["5", "7", "1.5", "3", "x", "2", "4"]})
RL = pl.DataFrame({"Ref": ["INV1", "INV2", "INV3", "INV4", "INV5", "inv6", None], "Amount": ["100.00", "200.00", "300.00", "400.00", "50.00", "75.00", "10"],
                   "Date": ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05", "2024-01-06", "2024-01-07", "2024-01-08"]})
RR = pl.DataFrame({"Ref": ["INV1", "INV2 ", "INV3", "INV3", "INV9", "INV6", None], "Amount": ["100.00", "199.50", "300.00", "299.90", "5.00", "75.00", "10"],
                   "Date": ["2024-01-02", "2024-01-05", "2024-01-04", "2024-01-06", "2024-01-09", "2024-01-30", "2024-01-08"]})
WN = pl.DataFrame({"acct": list("AABABB"), "d": [3, 1, 1, 2, 2, 3], "v": ["10", None, "5", "7", "8", "9"]})
TT = pl.DataFrame({"id": [1, 2, 3, 4, 5], "acct": ["1000-200-30-4", "7", " a - b ", None, ""]})
FL = pl.DataFrame({"Vendor": ["ACME Corp.", "Globex, Inc", "Initech LLC", "Umbrella Ltd", "Hooli", None], "id": [1, 2, 3, 4, 5, 6]})
FRR = pl.DataFrame({"Supplier": ["Acme Corporation", "GLOBEX INC.", "Initec", "Umbrela Limited", "Pied Piper", "Hooly"], "ref": list("abcdef")})
MF = pl.DataFrame({"a": [" x ", "Y", None], "b": ["1", "2.5", "z"], "n": [1, 2, 3]})
T1 = pl.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]}); T2 = pl.DataFrame({"a": [2, 3, 4], "c": [20.0, 30.0, 40.0]})
def code_of(fn, *a):  # the error code a call raises
    with pytest.raises(ShapingError) as info: fn(*a)
    return info.value.code
```

### 7.2 Core unit tests with hand-computed expectations

**Record ID** (`test_shaping_record_id.py`; `ids(s)` = `apply_record_id(RID, s).collect()["RecordID"].to_list()`)
* `test_record_id_global_starts_at_one_and_goes_first`: columns `["RecordID","acct","amt","d"]`, ids `[1..6]`, dtype `Int64`.
* `test_record_id_start_name_position`: `{"start":100,"name":"Seq","position":"last"}` -> last column `Seq` = `[100..105]`.
* `test_record_id_per_group_follows_input_order`: `{"group_by":["acct"]}` -> `[1,1,2,1,2,3]`.
* `test_record_id_order_by_descending_within_group_keeps_row_order`: `{"group_by":["acct"],"order_by":[{"column":"d","descending":True}]}` -> `[3,2,2,1,1,1]`.
* `test_record_id_order_by_text_ties_broken_by_input_position`: `{"order_by":[{"column":"amt"}]}` -> `[1,2,3,6,5,4]` (text order `"10"<"5"<"7"="7"<"x"<null`; the two `"7"` rows by position).
* `test_record_id_name_collision_and_empty`: `{"name":"d"}` -> `TD-SHAPE-002`; `{"name":"  "}` -> `001`; `{"group_by":["nope"]}` -> `003`.
* property `test_record_id_property_dense_and_unique` (7.4).

**Select Records** (`sel(s)` returns `(selected d list, rest d list)` of `apply_select_records(RID, s)`; `d` is 1..6)

| Settings | selected | rest |
|---|---|---|
| `first_n`, n=2 | `[1,2]` | `[3,4,5,6]` |
| `last_n`, n=2 | `[5,6]` | `[1,2,3,4]` |
| `row_range` 2..4 | `[2,3,4]` | `[1,5,6]` |
| `largest_n`, n=2, by `amt` | `[1,3]` (10, then the first 7) | `[2,4,5,6]` |
| same + `ties=include_ties` | `[1,3,6]` | `[2,4,5]` |
| `smallest_n`, n=1, by `amt`, group `acct` | `[2,3]` (5; first 7) | `[1,4,5,6]` |
| `first_n`, n=1, group `acct` | `[1,2,4]` | `[3,5,6]` |
| `last_n`, n=1, group `acct` | `[4,5,6]` | `[1,2,3]` |
| `first_n`, n=99 | `[1..6]` | `[]` |

Errors: `largest_n` without `by` -> 001; `n=0` -> 004; range 5..2 -> 004. Property: `selected + rest` sorted equals `[1..6]` for `largest_n` n=3 by `d`.

**Find and Replace** (`fr(rules, cols=("name",), suffix="")` = `apply_find_replace(FR, {...}).collect()`; results are the `name` column)

| Rules | Result |
|---|---|
| `acme -> X` (default case-insensitive) | `["X Inc.","X inc","foo 123-45","a$b",None,"X"]` |
| same with `case_sensitive` | unchanged |
| `Acme -> Z`, `whole_cell`, `case_sensitive` | only the last row becomes `"Z"` |
| regex `(\d+)-(\d+)` -> `$2-$1` | row 3 `"foo 45-123"` |
| literal `$ -> USD` | row 4 `"aUSDb"` |
| literal `a -> $1` | `["$1cme Inc.","$1CME inc","foo 123-45","$1$b",None,"$1cme"]` (replacement is literal) |
| `inc. -> ""` then regex `\s+$ -> ""` | row 1 `"Acme"`, row 2 unchanged (no period) |
| rule with `enabled=False` | unchanged |

`suffix="_c"` -> columns `["name","n","name_c"]`, original untouched. `changed_cell_counts(FR, {"columns":["name","n"], rules: acme -> X})` -> `{"name": 3, "n": 0}`. Errors: regex `(a)\1` -> 040, `(` -> 040, empty find -> 042, 501-character find -> 041, numeric column -> 044, no columns -> 001.
**ReDoS guard** `test_find_replace_redos_guard_is_linear_time`: `{"name": ["a"*50_000 + "!"]}` with regex `(a+)+$` finishes in < 2 s (it takes ~1 ms: the Rust engine is linear; the test pins that nobody swaps in Python `re`).

**Date Helper** (`apply_date_helper(DH, {"fiscal_start_month": 4, "holidays": "2024-04-01", "ops": DH_OPS})`, where `DH_OPS` lists every op on `d`, with `days_between` and `business_days_between` against `e`, `add_days n=-1`, `add_business_days n=1`); expected columns (rows 6-7 are `None`: `"bad"` and null):

| Column | Rows 1-5 |
|---|---|
| `d_weekday_name` | Wednesday, Thursday, Saturday, Monday, Tuesday |
| `d_weekday_number` | 3, 4, 6, 1, 2 |
| `d_is_weekend` | F, F, T, F, F |
| `d_is_month_end` | T, T, F, F, T |
| `d_quarter` | 1, 1, 1, 2, 4 |
| `d_fiscal_year` / `_period` / `_quarter` | 2024,2024,2024,2025,2025 / 10,11,12,1,9 / 4,4,4,1,3 |
| `d_to_e_days_between` | 5, 0, 2, -31, 2 |
| `d_add_days` (first two) | 2024-01-30, 2024-02-28 |
| `d_add_business_days` | 2024-02-01, 2024-03-01, 2024-04-03, 2024-04-03, 2025-01-01 (Apr 1 is the holiday) |
| `d_is_business_day` | T, T, F, F, T |
| `d_to_e_business_days_between` (first three) | 3, 0, 0 |

Also: `fiscal_start_month=1` -> `fiscal_year` is the calendar year; `n_column="n"` adds `n` days per row (`2024-02-01, 2024-03-02, 2024-04-02`); `working_days` incl. Sat makes 2024-03-30 a business day; `parse_failures(DH, ...) == {"d": 1}`; errors: numeric source -> 050, holiday `31/12/2024` -> 052, `working_days=[]` -> 053, output name equal to an input column -> 002.

**Pivot / Unpivot** (`PV_S = {"index_columns":["acct"],"header_column":"period","value_column":"amt"}`)
* `test_pivot_sum_columns_sorted_missing_cells_are_null`: columns `["acct","10","9","g","(blank)"]`; rows `A: 8.0, 7.0, None, None`; `B: 1.5, None, None, 2.0` (B/9 is null because `"x"` is unreadable and an all-null sum is null); `C: None, None, 4.0, None`.
* `missing_as="zero"`: first row `("A", 8.0, 7.0, 0.0, 0.0)`. Numeric header `[10, 9]` -> columns `["g","9","10"]`. Header value equal to the index name (`"g"`) -> columns `["g","g_2"]`.
* errors: header = index column -> 060; empty header -> 001; 501 distinct headers -> 061.
* Unpivot of `{"acct":["A","B"],"jan":[1,None],"feb":[2,3]}`, ids `acct`, values `jan,feb`: rows `[("A","jan",1),("A","feb",2),("B","jan",None),("B","feb",3)]`; with `drop_nulls` 3 rows; mixed `a=1` / `b="x"` -> `[(1,"a","1"),(1,"b","x")]`; `variable_name="acct"` -> 002.

**Greedy assignment** (`test_shaping_assign.py`): `greedy_one_to_one(cand)` equals `greedy_sequential(cand)` and has no repeated `__l` or `__r` on 300 random candidate lists (property, 7.4).

**Reconcile** (`apply_reconcile(RL, RR, {**RB, "tolerance": 0.5, "date_window_days": 3})`, `RB` = keys `Ref/Ref`, amounts `Amount`, dates `Date`)
* matched columns: `["Match_ID","Match_Status","Amount_Diff","Date_Gap_Days","Ref","Amount","Date","Ref_right","Amount_right","Date_right"]`; `(Match_ID, Amount_Diff, Date_Gap_Days, Ref)` rows `(1,0.0,0,"INV1"), (2,-0.5,2,"INV2"), (3,0.0,0,"INV3")` (INV3 picks the exact 300.00 over 299.90; `"INV2 "` matches after trim).
* left unmatched reasons: `INV4`, `INV5`, null-key row -> `No candidate with the same key`; `inv6` -> `Candidates outside tolerance` (date gap 23); right row 299.90 -> `Candidates already matched`.
* summary: `Left_Rows 7, Matched_Groups 3, Left_Unmatched_Rows 4, Right_Unmatched_Rows 4, Matched_Left_Total 600.0, Matched_Right_Total 599.5, Matched_Net_Difference -0.5, Matched_Abs_Difference 0.5, Left_Total 1135.0, Right_Total 989.4, Net_Difference_Total -145.6, Left_Match_Rate_Pct 42.86`.
* no dates (`date_left=""`): matched `Ref` = `["INV1","INV3","inv6"]` and no `Date_Gap_Days` column.
* one_to_many: left `Inv/Amt` = INV1 1000, INV2 500, INV3 100; right = INV1 400, 300, 300; INV2 200, 250; INV9 5; tolerance 0: matched `(Match_ID, Match_Status, Amount_Diff, Amt_right)` = `(1,Within,0.0,400.0), (1,Within,0.0,300.0), (1,Within,0.0,300.0), (2,Outside,-50.0,200.0), (2,Outside,-50.0,250.0)`; left unmatched `["INV3"]`; right unmatched `["INV9"]`; summary `Matched_Groups 2, Within 1, Outside 1, Right_Matched_Rows 5`. Swapping inputs with `many_to_one` gives `Amount_Diff` `[0,0,0,50,50]` (always right minus left).
* many_to_many: left `G1 60, G1 40, G2 30`; right `G1 100, G2 10, G2 20, G3 5` -> matched `(Match_ID, Amt, Amt_right)` = `(1,60,100), (1,40,None), (2,30,10), (2,None,20)`; right unmatched `G3` (`No candidate with the same key`); with right G1 = 90 and 5 % tolerance group 1 is `Outside tolerance` (`Amount_Diff -10`) and group 2 `Within`.
* date window only (no keys): left dates `01-01, 01-10, 03-01`, right `01-02, 01-20, 03-01`, equal amounts, window 3 -> matched `(Match_ID, Date_Gap_Days) = (1,1),(2,0)`; the 01-10 row is `No candidate within the date window`.
* errors: amount on one side only -> 070; neither keys nor dates -> 071; unknown column -> 003; with `MAX_CANDIDATE_PAIRS` monkeypatched to 3 and three duplicate keys per side -> 072.

**Fuzzy Match** (`apply_fuzzy(FL, FRR, {"left_column":"Vendor","right_column":"Supplier","threshold":0.85,"prefix_length":3})`)
* `(Match_ID, Match_Score, id, ref)` = `(1,1.0,1,"a"), (2,1.0,2,"b"), (3,0.9714,3,"c"), (4,0.975,4,"d"), (5,0.92,5,"f")`; left unmatched `id 6` (null name), right unmatched `ref "e"`.
* `blocking="none", threshold=0.8, algorithm="levenshtein"`: scores `[1.0, 1.0, 0.8571, 0.875, 0.8]`; `blocking="first_token"`: only ids `[1, 2]` match.
* `all_pairs` vs `best_per_left` on `["acme"]` vs `["acme","acmee"]` (threshold 0.8): 2 rows vs 1 row (`"acme"`); missing column -> 001; threshold 0 -> 004; 100,000 x 100,000 names with `prefix_length=1` -> 081 (checked before scoring).

**Window** (`apply_window(WN, {"partition_by":["acct"],"order_by":[{"column":"d"}],"ops": WO})`, output keeps the input row order `d = [3,1,1,2,2,3]`)

| Column | Values (input order) |
|---|---|
| `v_lag1` | `["7",None,None,None,"5","8"]` |
| `v_lead1` | `[None,"7","8","10","9",None]` |
| `Row_Number` | `[3,1,1,2,2,3]` |
| `v_rank` (descending) | `[1,None,3,2,2,1]` |
| `v_cum_sum` | `[17.0,None,5.0,7.0,13.0,22.0]` |
| `v_cum_min` / `v_cum_max` | `[7,None,5,7,5,5]` / `[10,None,5,7,8,9]` |
| `v_cum_mean` | row 0 `8.5`, row 5 `22/3` |
| `v_roll2` (window 2, strict) | `[17.0,None,None,None,13.0,17.0]` |
| `roll2p` (partial) | `[17.0,None,5.0,7.0,13.0,17.0]` |
| `cs_zero` (`nulls="zero"`) | `[17.0,0.0,5.0,7.0,13.0,22.0]` |

No partition: `row_number` `[1..6]`, `lag` offset 2 of `d` -> `[None,None,3,1,1,2]`. Errors: missing source -> 001, output named like an input -> 002, offset 0 -> 004, `cum_sum` on a Date -> 091.

**Text to Columns** (`TT`)
* `{"column":"acct","pattern":"-","max_splits":2}` -> columns `["id","acct","acct_1","acct_2","acct_3"]`, rows `("1000","200","30-4"), ("7",None,None), ("a","b",None), (None,None,None), ("",None,None)`.
* `max_splits=1, names="Main, Rest", keep_original=False` -> `["id","Main","Rest"]`, first row `(1,"1000","200-30-4")`; `trim=False` -> `acct_1` third value `" a "`.
* rows mode (`max_splits=0, row_index_column="n", keep_original=False`) -> `(1,"1000",1),(1,"200",2),(1,"30",3),(1,"4",4),(2,"7",1),(3,"a",1),(3,"b",2),(4,None,1),(5,"",1)`.
* regex `\s*[,;]\s*` on `"a, b;c"` -> `("a","b","c")`; delimiter `\t` typed as two characters splits on a tab; regex `\s*` -> 101, `(` -> 040, `max_splits=0` in columns mode -> 004, numeric column -> 044.

**Multi-Field Formula** (`MF`): `UPPER(TRIM({col}))` on `a` -> `["X","Y",None]` (order of columns unchanged); `TRY_CAST({col} AS DOUBLE) * 2` on `b,n` with suffix `_x2` -> columns `["a","b","n","b_x2","n_x2"]`, `b_x2 = [2.0,5.0,None]`, `n_x2 = [2.0,4.0,6.0]`; `{name} || ':' || {col}` on `b` -> `["b:1","b:2.5","b:z"]`. Rejected: template without `{col}` 120; no columns 001; `{col}); drop table t1; --` 110; `{col}) FROM read_csv('x') --` 112; `nofunc({col})` 113; empty suffix 001; unknown column 003.

**SQL Query** - 7.3. **Comments** (`test_shaping_comments.py`): scene dict with comment nodes ids 2 (`y=100`, "Second"), 1 (`y=10`, " First "), a blank one and a non-comment -> `[(1,"First"),(2,"Second")]` (reading order, trimmed, blank skipped).

### 7.3 SQL read-only attack tests (`test_sql_guard.py`)

```python
FORBIDDEN = {   # statement -> the code it must raise; every one parametrised, run inside tmp_path with an evil.csv present
  "TD-SHAPE-111": ["insert into t1 values (9,'q')", "update t1 set a=1", "delete from t1", "create table z(a int)", "create or replace view v as select 1",
    "drop table t1", "drop view t1", "alter table t1 add column q int", "truncate t1", "copy t1 to 'out.csv'", "copy (select 1) to 'out.csv'", "attach 'x.db'",
    "detach x", "install httpfs", "load httpfs", "pragma database_list", "pragma table_info('t1')", "set threads=1", "set enable_external_access=true", "reset threads",
    "call pragma_version()", "export database 'd'", "checkpoint", "vacuum", "use memory", "explain select 1", "describe t1", "summarize t1", "show tables",
    "with x as (select 1) delete from t1", "with x as (select 1) insert into t1 select * from t1"],
  "TD-SHAPE-110": ["select 1; drop table t1", "select 1; select 2"],
  "TD-SHAPE-112": ["select * from read_csv('evil.csv')", "select * from READ_CSV_AUTO('evil.csv')", "select * from read_parquet('x.parquet')", "select * from read_json('evil.csv')",
    "select * from read_text('evil.csv')", "select * from parquet_scan('x.parquet')", "select * from glob('*')", "select * from sniff_csv('evil.csv')", "select * from 'evil.csv'",
    "select * from t1 join 'evil.csv' on true", "select * from query('select 1')", "select * from query_table('t1')", "select * from duckdb_settings()",
    "select * from duckdb_extensions()", "select * from pragma_database_size()", "select current_setting('threads')", "select random()", "select uuid()",
    "select read_csv ('x')", "select * from READ_CSV\n('x')"],
  "TD-SHAPE-001": ["", "   ;  ", "-- only a comment"],
  "TD-SHAPE-113": ["select 'unterminated"],
}
@pytest.mark.parametrize("sql,code", [(s, c) for c, lst in FORBIDDEN.items() for s in lst])
def test_sql_query_rejects_forbidden_statement(sql, code, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path); (tmp_path / "evil.csv").write_text("a\n1\n")
    assert code_of(run_select, sql, {"t1": T1}) == code
    assert not (tmp_path / "out.csv").exists() and not (tmp_path / "x.db").exists()
```
(57 cases.) Allowed and must run: `SELECT t1.a, c FROM t1 JOIN t2 USING (a) ORDER BY a;` -> `[(2,20.0),(3,30.0)]`; `with x as (select a from t1) select sum(a) as s from x` -> 6; `from t1 select a` (3 rows); `select 'DROP TABLE t1' as note -- read_csv('x')` -> the text; `select * from t1 where b = 'it''s; fine'` (0 rows); `select "update" from (select 1 as "update")` -> 1.
**Engine lock without the checker** `test_sql_query_engine_is_locked_even_if_the_checker_were_bypassed`: `make_locked_connection({"t1": T1})` and `con.execute` each of `read_csv('evil.csv')`, `copy (select 1) to 'o.csv'`, `attach 'x.db'`, `set enable_external_access=true`, `load httpfs` must raise `duckdb.Error`, and `o.csv` must not exist. **Limits:** `run_select("select count(*) from range(100000000000)", {}, 1.0)` -> 115 in ~1 s; `infer_schema("select a, b from t1", ...)` -> `{"a": Int64, "b": String}`; `select zzz from t1` -> 113; 20,001 characters -> 114.

### 7.4 Property tests (seeded loops, no extra dependency)

```python
def test_greedy_rounds_equal_sequential_walk():            # assign
    for seed in range(300):
        rnd = random.Random(seed)
        pairs = list(dict.fromkeys((rnd.randint(0, 8), rnd.randint(0, 8)) for _ in range(rnd.randint(1, 40))))
        cand = pl.DataFrame({"__l": [a for a, _ in pairs], "__r": [b for _, b in pairs]}).with_columns(pl.Series("k", [rnd.random() for _ in pairs])).sort("k")
        fast = greedy_one_to_one(cand)
        assert fast.equals(greedy_sequential(cand)) and fast["__l"].is_unique().all() and fast["__r"].is_unique().all()

def test_reconcile_one_to_one_never_reuses_a_row_and_equals_sequential_greedy():   # 60 seeds
    # L: lid, k in 0..3, a in 1..6 (n<=25 rows); R: rid, k, a; settings keys k/k, amounts a/a, tolerance 1.0
    got = apply_reconcile(L, R, s)
    assert got.matched["lid"].is_unique().all() and got.matched["rid"].is_unique().all()
    pairs = sorted((abs(ra - la), li, ri) for li, lk, la in L.rows() for ri, rk, ra in R.rows() if lk == rk and abs(ra - la) <= 1.0)
    # walk `pairs`, accept when both free -> `want`;   assert set(zip(got.matched["lid"], got.matched["rid"])) == want
    assert got.left_unmatched.height + got.matched.height == n

def test_pivot_then_unpivot_round_trips_property():        # 25 seeds
    # random unique (acct in ABC, period in p1..p3) -> float amt 1..9; pivot(sum) then unpivot(drop_nulls=True, names period/amt)
    assert back.sort("acct", "period").equals(orig.sort("acct", "period"))

def test_record_id_property_dense_and_unique():            # 40 seeds
    # random g in abc, v in 0..5, n 0..60 rows, start in -3..5
    # global/order_by: sorted(ids) == list(range(start, start + n)); per group: sorted(ids) == 1..k
```

### 7.5 UI tests (`tests/ui/test_shaping_docks.py`, pytest-qt, offscreen)

Pattern (verified headless with the Record ID probe): build with `graph(...)` (3.5), `node.eval()`, `dock = ConfigDock(); dock.updateConfig([node.grNode])`, `history.storeHistory("Baseline")`. Spin/line/area edits are debounced: call `node.content.flush_pending()` after changing them. After `updateConfig(..., force=True)` the old widgets are `deleteLater`'d: call `QApplication.processEvents()` (or look up the last match) before reading values.

```python
@pytest.mark.parametrize("case", DOCK_CASES, ids=lambda c: c.id)      # one Case per node: cls, frames, field key, new value
def test_dock_builds_edits_undoes_and_survives_rebuild(qtbot, case):
    g = graph(case.cls, *case.frames); node = g.node; node.eval()
    node.content.create_layout(QVBoxLayout(host := QWidget()))        # direct call: the dock swallows exceptions (brief 5.1)
    dock = ConfigDock(); qtbot.addWidget(dock); dock.updateConfig([node.grNode]); h = g.window.scene.history; h.storeHistory("Baseline")
    before = copy.deepcopy(node.content.settings)
    case.edit(dock, node)                                             # sets the widget; then node.content.flush_pending()
    assert node.content.settings != before and not node.isInvalid()   # live re-evaluation happened
    assert h.canUndo() and h.currentText().startswith(node.content.HISTORY)
    h.undo(); assert node.content.settings == before
    h.redo(); assert node.content.settings != before
    dock.updateConfig([node.grNode], force=True); QApplication.processEvents()
    assert case.read(dock, node) == node.content.settings[case.key]
```
Per-node checks (each a named test): `test_record_id_order_by_card_add_pick_undo` (add card -> `[{"column":"","descending":False}]`; pick `b`; undo twice -> `[]`); `test_select_records_visibility_follows_mode` (row-range fields hidden unless `row_range`; `by` hidden for `first_n`); `test_find_replace_rule_edit_merges_typing` (type 3 characters in `find` within 300 ms -> one history step); `test_date_helper_working_days_checklist_undo`; `test_pivot_header_combo_lists_input_columns_and_flags_missing` (column removed upstream shows `<name> (missing)`); `test_reconcile_inputs_columns_come_from_their_own_input` (left combos list left columns, right combos right columns; date rows hidden for `many_to_many`); `test_window_op_card_move_up_down_undo`; `test_comment_label_follows_first_line_and_undo_restores_it` (`getNodeLabel() == "Check cut-off"`, then `""` after undo); `test_sql_query_editor_completes_plain_column_names` (`match_completions("na", False, ["name"], bracket=False) == ["name"]`, `bracket=True` gives `["[name]"]`; editor with `bracket_columns=False` reports no `Unknown column` for `a[1]`); `test_sql_query_diagnostics_underline_free_error_label` (type `select zzz from t1` -> label text contains `zzz`; valid text hides it); `test_unwired_dock_shows_empty_state`; `test_no_node_leaves_a_blank_dock` (every node's `create_layout` builds >= 1 section for a wired input). `tests/ui/test_rule_stack.py`: signals/indexes, move buttons disabled at ends, `clear()` removes cards, each icon button has `toolTip()` and `accessibleName()`.

### 7.6 End-to-end golden tests (`tests/e2e/test_shaping_goldens.py`)

Helper (`tests/support/shaping.py`, follows brief 9.4 skeleton c): builds File Input(s) -> chain of nodes -> File Output per output socket in code, saves a `.tds`, reloads it in a fresh window, runs, reads the CSVs.

```python
def run_shaping_workflow(qtbot, tmp_path, chain, csvs, outputs, extras=()):
    """chain = [(node_class, settings), ...]; csvs feed input i of the first node; extras = unconnected nodes
    (a Comment) added to the scene; returns (frames, run_window)."""
    window = TriggerSubWindow(); scene = window.scene
    nodes = []
    for cls, settings in chain:
        node = cls(scene); node.content.settings.update(settings); nodes.append(node)
    for cls, settings in extras:
        cls(scene).content.settings.update(settings)
    for i, text in enumerate(csvs):
        path = tmp_path / f"in{i}.csv"; path.write_text(text + "\n", encoding="utf-8")
        fin = get_class_from_opcode(IONodes.FILE_INPUT, NodeTypes.IO)(scene)
        fin.content.filePath, fin.content.file_type = str(path), "csv"
        Edge(scene, fin.outputs[0], nodes[0].inputs[i])
    for a, b in zip(nodes, nodes[1:]):
        Edge(scene, a.outputs[0], b.inputs[0])
    outs = []
    for j in range(outputs):
        fout = get_class_from_opcode(IONodes.FILE_OUTPUT, NodeTypes.IO)(scene)
        out = tmp_path / "out" / f"out{j}.csv"; out.parent.mkdir(exist_ok=True)
        fout.content.filePath, fout.content.file_format = str(out), "csv"
        Edge(scene, nodes[-1].outputs[j], fout.inputs[0]); outs.append(out)
    tds = tmp_path / "wf.tds"; scene.saveToFile(str(tds)); window.close()
    run = TriggerSubWindow(); qtbot.addWidget(run)
    assert run.fileLoad(str(tds)) is True and run.validateLoadedWorkflow() == []
    run_workflow_and_wait(qtbot, run)
    assert len(run.execution_results) == len(run.getAllNodes())       # every node ran, none invalid
    return [read_frame(p) for p in outs], run

@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_shaping_golden(qtbot, tmp_path, no_modal_dialogs, case):
    frames, _ = run_shaping_workflow(qtbot, tmp_path, case.chain, case.csvs, len(case.goldens))
    for frame, golden in zip(frames, case.goldens):
        assert_frame_golden(frame, golden)                           # sort_by only where a node promises no order (none here)
    assert no_modal_dialogs["run_code"]                              # the run reached getPyFile
```
Fixtures live in `tests/e2e/fixtures/shaping/<name>.csv`; goldens in `tests/e2e/fixtures/expected/<golden>.csv` (write them from the blocks below, then verify with `TRIGGER_UPDATE_E2E_GOLDENS` **unset**; never regenerate blindly). File Input reads every column as text, which is why the numeric nodes cast.

Tables below show one CSV row per `/` (the real files have one row per line).


| Case | Input CSV(s) | Settings | Golden(s) (one row per `/`) |
|---|---|---|---|
| `record_id` | `acct,amt,d` / `A,10,1` / `B,5,2` / `A,7,3` / `C,,4` / `B,x,5` / `A,7,6` | `group_by:["acct"]` | `RecordID,acct,amt,d` / `1,A,10,1` / `1,B,5,2` / `2,A,7,3` / `1,C,,4` / `2,B,x,5` / `3,A,7,6` |
| `select_records` | the `record_id` input | `largest_n`, n=2, by `amt` | selected `acct,amt,d` / `A,10,1` / `A,7,3`; rest `acct,amt,d` / `B,5,2` / `C,,4` / `B,x,5` / `A,7,6` |
| `find_replace` | `name,n` / `Acme Inc.,1` / `ACME inc,2` / `foo 123-45,3` / `a$b,4` / `,5` / `Acme,6` | `columns:["name"]`, rules `acme->X` (literal), regex `(\d+)-(\d+)` -> `$2-$1` | `shaping_find_replace.csv`: `name,n` / `X Inc.,1` / `X inc,2` / `foo 45-123,3` / `a$b,4` / `,5` / `X,6` |
| `date_helper` | `d,e` / `2024-01-31,2024-02-05` / `2024-02-29,2024-02-29` / `2024-03-30,2024-04-01` / `2024-04-01,2024-03-01` / `bad,2024-01-01` | fiscal start 4; ops `weekday_name d`, `is_month_end d`, `fiscal_year d`, `days_between d,e`, `add_business_days d n=1` | `d,e,d_weekday_name,d_is_month_end,d_fiscal_year,d_to_e_days_between,d_add_business_days` / `2024-01-31,2024-02-05,Wednesday,true,2024,5,2024-02-01` / `2024-02-29,2024-02-29,Thursday,true,2024,0,2024-03-01` / `2024-03-30,2024-04-01,Saturday,false,2024,2,2024-04-02` / `2024-04-01,2024-03-01,Monday,false,2025,-31,2024-04-02` / `bad,2024-01-01,,,,,` |
| `pivot` | `acct,period,amt` / `A,p1,1` / `A,p2,2` / `B,p1,3` / `A,p1,4` / `C,p2,5` | index `acct`, header `period`, value `amt`, sum | `acct,p1,p2` / `A,5.0,2.0` / `B,3.0,` / `C,,5.0` |
| `unpivot` | `acct,p1,p2` / `A,5.0,2.0` / `B,3.0,` / `C,,5.0` | ids `acct`, values `p1,p2`, names `period`/`amt`, `drop_nulls` | `acct,period,amt` / `A,p1,5.0` / `A,p2,2.0` / `B,p1,3.0` / `C,p2,5.0` |
| `pivot_unpivot_round_trip` | the pivot input | chain Pivot -> Unpivot (same settings as above) | same golden as `unpivot` |
| `reconcile` | ledger `Ref,Amount,Date` / `INV1,100.00,2024-01-02` / `INV2,200.00,2024-01-03` / `INV3,300.00,2024-01-04` / `INV4,400.00,2024-01-05`; bank `Ref,Amount,Date` / `INV1,100.00,2024-01-02` / `INV2 ,199.50,2024-01-05` / `INV3,299.90,2024-01-06` / `INV9,5.00,2024-01-09` | keys `Ref/Ref`, amounts, dates, tolerance 0.5 absolute, window 3 | matched: `Match_ID,Match_Status,Amount_Diff,Date_Gap_Days,Ref,Amount,Date,Ref_right,Amount_right,Date_right` / `1,Within tolerance,0.0,0,INV1,100.00,2024-01-02,INV1,100.00,2024-01-02` / `2,Within tolerance,-0.5,2,INV2,200.00,2024-01-03,INV2 ,199.50,2024-01-05` / `3,Within tolerance,-0.1,2,INV3,300.00,2024-01-04,INV3,299.90,2024-01-06`; left: `Ref,Amount,Date,Unmatched_Reason` / `INV4,400.00,2024-01-05,No candidate with the same key`; right: same header / `INV9,5.00,2024-01-09,No candidate with the same key`; summary: header `Match_Type,Left_Rows,Right_Rows,Matched_Groups,Left_Matched_Rows,Right_Matched_Rows,Left_Unmatched_Rows,Right_Unmatched_Rows,Left_Match_Rate_Pct,Right_Match_Rate_Pct,Left_Total,Right_Total,Matched_Left_Total,Matched_Right_Total,Matched_Net_Difference,Matched_Abs_Difference,Left_Unmatched_Total,Right_Unmatched_Total,Net_Difference_Total,Within_Tolerance_Groups,Outside_Tolerance_Groups`, row `one_to_one,4,4,3,3,3,1,1,75.0,75.0,1000.0,604.4,600.0,599.4,-0.6,0.6,400.0,5.0,-395.6,3,0` |
| `fuzzy_match` | vendors `Vendor,id` / `ACME Corp.,1` / `"Globex, Inc",2` / `Initech LLC,3` / `Hooli,5`; suppliers `Supplier,ref` / `Acme Corporation,a` / `GLOBEX INC.,b` / `Initec,c` / `Pied Piper,e` | `Vendor`/`Supplier`, threshold 0.85, prefix 3 | matched `Match_ID,Match_Score,Vendor,id,Supplier,ref` / `1,1.0,ACME Corp.,1,Acme Corporation,a` / `2,1.0,"Globex, Inc",2,GLOBEX INC.,b` / `3,0.9714,Initech LLC,3,Initec,c`; left `Vendor,id` / `Hooli,5`; right `Supplier,ref` / `Pied Piper,e` |
| `window` | `acct,d,v` / `A,3,10` / `A,1,` / `B,1,5` / `A,2,7` / `B,2,8` / `B,3,9` | partition `acct`, order `d`, ops `lag v`, `cum_sum v`, `rank v` descending | `acct,d,v,v_lag1,v_cum_sum,v_rank` / `A,3,10,7,17.0,1` / `A,1,,,,` / `B,1,5,,5.0,3` / `A,2,7,,7.0,2` / `B,2,8,5,13.0,2` / `B,3,9,8,22.0,1` |
| `text_to_columns` | `id,acct` / `1,1000-200-30-4` / `2,7` / `3, a - b ` | column `acct`, `-`, max_splits 2 | `id,acct,acct_1,acct_2,acct_3` / `1,1000-200-30-4,1000,200,30-4` / `2,7,7,,` / `3, a - b ,a,b,` |
| `multi_formula` | `a,b,n` / ` x ,1,1` / `Y,2.5,2` / `,z,3` | columns `a,b`, `UPPER(TRIM({col}))`, suffix `_clean` | `a,b,n,a_clean,b_clean` / ` x ,1,1,X,1` / `Y,2.5,2,Y,2.5` / `,z,3,,Z` |
| `sql_query` | t1 `a,b` / `1,x` / `2,y` / `3,z`; t2 `a,c` / `2,20.0` / `3,30.0` / `4,40.0` | `SELECT t1.a, t1.b, t2.c FROM t1 JOIN t2 USING (a) ORDER BY t1.a` (2 inputs wired, input 3 free) | `a,b,c` / `2,y,20.0` / `3,z,30.0` |
| `comment` | any 2-row CSV | chain = Record ID, `extras = [(Comment, {"text": "Check cut-off"})]` | output equals the input; `run.execution_results[<the Comment node>] == {}` (found by `node_title == "Comment"` in `run.getAllNodes()`); `comments_from_scene_dict(orjson.loads(tds.read_bytes()))[0].text == "Check cut-off"`; reloading restores `getNodeLabel() == "Check cut-off"` |

Also `test_two_outputs_of_one_node_feed_reconcile` (unit, `single_source=True`): left = `Source` output 0, right = output 1 of the same `Source`; the matched output uses both different frames (this is the case `getSocketValue` breaks).

### 7.7 Performance tests (`tests/benchmarks/test_shaping_perf.py`, run with `--run-benchmarks`)

Budgets are about 10x the measured times (same machine, Python 3.13): CI noise must not flake them, a quadratic regression must still fail.

| Test | Data | Measured | Budget |
|---|---|---|---|
| `test_window_1m_rows` | 1,000,000 rows, 100,000 partitions, lag + rank + cum_sum + rolling(5) + row_number | 0.32 s | 5 s |
| `test_pivot_1m_rows` | 1M text rows, 50,000 accounts x 12 headers, sum | 0.35 s | 5 s |
| `test_unpivot_600k_rows` | the pivot result unpivoted (600,000 rows) | 0.02 s | 3 s |
| `test_reconcile_1m_x_1m` | 1M x 1M, 400,000 distinct keys, tolerance 0.01, one_to_one | 1.4 s | 20 s |
| `test_greedy_3m_candidates` | 3M candidate pairs | 0.5 s | 10 s |
| `test_fuzzy_10k_x_10k_blocked` | 10,000 x 10,000 names sharing a 3-letter prefix (~3.8M pairs) | 1.4 s | 15 s |
| `test_select_records_largest_100_of_1m` | 1M rows | 0.24 s | 3 s |
| `test_record_id_grouped_ordered_1m` | group + order_by, 1M rows | 0.33 s | 5 s |
| `test_find_replace_regex_1m` | two rules on 1M strings | 0.68 s | 8 s |
| `test_text_to_columns_1m` / `test_date_helper_1m` | 1M rows | 0.23 s / 0.17 s | 3 s |
| `test_sql_query_groupby_1m` | `select acct, sum(try_cast(amt as double)) ... group by acct` over 1M rows | 1.8 s | 20 s |

Skeleton: build the frame with numpy (`default_rng(0)`), `t = time.perf_counter()`, call `run_node([frame], settings)` and `.collect()` every output, `assert time.perf_counter() - t < BUDGET`, and assert one structural fact (row count or width) so a wrong fast answer fails too.

---

## 8. Acceptance checklist

- [ ] All 13 nodes appear in the palette tab of their family and in the Shift+A menu with their title and a reused icon; `tests\unit\test_node_titles.py` and `test_shaping_nodes.py` pass.
- [ ] Each node: drop unwired -> Run completes without `NameError`; wire File Input -> Run -> output correct; save, reload, Run again -> same output.
- [ ] Live output equals `exec(get_code())` output for every node (unit test), including multi-output nodes and zero-row input.
- [ ] Undo/redo: one step per real edit, no step for undo/redo itself; dock rebuild with `force=True` shows the restored value; list add/remove/move are undoable.
- [ ] Reconcile: never reuses a row in one-to-one mode (property test), summary numbers match 7.2, two outputs of one upstream node into both inputs work.
- [ ] SQL Query and Multi-Field Formula reject all 57 forbidden statements; the engine itself is locked (tested without the checker); no file is created by any attack.
- [ ] Find and Replace regex ReDoS test passes; invalid patterns give `TD-SHAPE-040` not a traceback.
- [ ] Pivot -> Unpivot round trip property passes; missing pivot cells are null, never invented zeros (unless `missing_as="zero"`).
- [ ] Comment never executes, persists in `.tds`, appears in `comments_from_scene_dict`, sets the canvas label.
- [ ] Performance budgets in 7.7 met; no GUI-thread freeze above the live caps (chip "Over N rows: full result at Run").
- [ ] `ruff format --check` and `ruff check` clean on every new/touched file; unit >= 334 + new, e2e >= 20 + 13, ui failures unchanged at the 27 baseline.
- [ ] `docs/NODE_REFERENCE.md` rows added; (`trigger.spec` coverage of `core/shaping` is plan 09 F-G's); stub `Join/find_replace.py` removed.

## 9. Verification commands

```powershell
# format + lint only what you touched (baseline is not clean)
.venv\Scripts\python.exe -m ruff format src\trigger_designer\core\shaping src\trigger_designer\qt\helpers\shaping_support.py tests\support\shaping.py tests\unit\test_shaping_*.py tests\ui\test_shaping_*.py tests\e2e\test_shaping_goldens.py
.venv\Scripts\python.exe -m ruff check  src\trigger_designer\core\shaping src\trigger_designer\qt\helpers\shaping_support.py tests\support\shaping.py tests\unit\test_shaping_*.py tests\ui\test_shaping_*.py tests\e2e\test_shaping_goldens.py
# unit layer (core + scaffolding + registry + untouched baseline)
.venv\Scripts\python.exe -m pytest tests\unit -q                       # expect 334 + new, 0 failed
.venv\Scripts\python.exe -m pytest tests\unit\test_sql_guard.py -q   # the 57-case attack table
# ui layer (new files must be green; compare the failures with the brief's 27 baseline)
.venv\Scripts\python.exe -m pytest tests\ui\test_rule_stack.py tests\ui\test_shaping_scaffold.py tests\ui\test_shaping_docks.py -q
.venv\Scripts\python.exe -m pytest tests\ui -q                         # 404 + new passed, still 20 failed + 7 errors (pre-existing)
# e2e layer
.venv\Scripts\python.exe -m pytest tests\e2e -q                        # 20 + 13 passed
# performance (opt-in)
.venv\Scripts\python.exe -m pytest tests\benchmarks\test_shaping_perf.py --run-benchmarks -q
# theme tokens after the QSS edit
.venv\Scripts\python.exe -m pytest tests\unit\test_theme_tokens.py -q
```
Never run bare `pytest` (brief 2.4: the full run aborts on a known teardown). Headless: `$env:QT_QPA_PLATFORM="offscreen"` is set by `tests/conftest.py`.

## 10. Pitfalls

1. **`getSocketValue`** returns the first matching upstream socket (`node_base.py:708-723`); use `getInputWithSocket(i)` and `socket.index` (3.4). A test with `single_source=True` guards it.
2. **Declared outputs.** Only `variable_name`, `*_variable_name`, `*_var` string attributes and `param` names survive `_prune_node_results`. Never add another such attribute to a shaping content class, and keep `OUTPUT_KINDS` in socket order.
3. **`set_in` cannot index lists.** Undo paths are `("settings", key)`; list fields use whole-list `push_list_change`. Do not try `("settings", "rules", 0, "find")`.
4. **Double history entries.** Every section the scaffolding builds is `_undo_composite = True`; do not call `registerInputWidget`/`recursively_find_widgets` in these nodes (brief 6.4).
5. **Debounced controls.** Text, spin and area edits commit after 300 ms; tests must `flush_pending()`. A pending timer firing after an undo is harmless (`set_setting` returns when the value equals the model).
6. **Dock rebuild leaves deleted widgets for one event loop** (`deleteLater`): process events before asserting on `findChild`.
7. **Polars gotchas fixed here:** `pivot(sum)` fills 0 (use pre-aggregate + `first`); `is_in(series)` of the same dtype is deprecated (use `.implode()`); `rank` and `shift` on text compare text (cast numeric first); `str.splitn` field names are `field_0..`; `add_business_days` raises on a non-business start unless `roll` is set; `over(order_by=)` takes a single direction flag.
8. **DuckDB gotchas:** `lock_configuration=true` must be the **last** `SET`; DDL on in-memory objects still works after the lock (hence the checker and the per-run connection); `register()` needs a collected `DataFrame` (the lazy frame is collected first); results can contain `Decimal`, so pass them through `normalize_to_supported_dtypes`.
9. **Namespace packages.** `core/shaping/` has no `__init__.py`; `from trigger_designer.core.shaping import record_id as core` works only because of that, and `trigger.spec` needs explicit hidden imports (provided by plan 09 F-G's file-by-file glob).
10. **Live evaluation is on the GUI thread.** Keep new live work behind `LIVE_CAP_ROWS` (heavy nodes) and never collect in `create_layout`.
11. **CSV text is not numbers.** Cast with `numeric_expr`; do not `cast(strict=True)`.
12. **Greedy determinism depends on the sort keys.** Always end ranking sorts with the row positions (`__l`, `__r`); without them equal-quality pairs would depend on hash order.
13. **Do not reformat generated SQL in `build_query`**: quoting is by doubling `"` and `'` only.

## 11. Interfaces for plans 02, 03, 06, 08 and 09

**Plan 06 (workpaper).**
* *Comments:* `core/shaping/comments.py` (Qt-free). `comments_from_scene_dict(scene_dict) -> list[CommentRecord(node_id, text, x, y)]` reads a `TriggerScene.serialize()` dict or a loaded `.tds` (op `report.comment`, text under `content.settings.text`), sorted top-to-bottom then left-to-right, blank notes skipped. `comments_from_nodes(nodes)` does the same for live nodes. Put them in the "Workflow" sheet as a "Reviewer notes" table (id, text, position).
* *Reconcile summary:* output socket 3 (`S`) of `join.reconcile` is a one-row frame with exactly the 21 columns of 4.8 (`Match_Type` text, the rows/groups counts `Int64`, everything else `Float64`, amount columns null when no amount was configured). After a Run read it with `window.execution_results[node][node.content.output_variables[3]]` (or `executed_frame(window, node, 3)`). The matched and unmatched outputs are sockets 0-2. A workpaper section "Reconciliation" = the summary row transposed plus the two unmatched tables.

**Plan 02 (run log).** `core/shaping/comments.NOT_EXECUTABLE_OPS` (`{"report.comment"}`): record those nodes as `status="skipped"` (they run a no-op), and include the comments in the run record (`comments_from_nodes(nodes)` at run start). Shaping nodes put no counters in generated code; row counts come from the declared output variables (`node.content.output_variables`, socket order). Settings are in `node.content.settings` (JSON-safe) for the "parameters used" field.

**Plan 03 (errors).** Every shaping failure message starts with `[TD-SHAPE-NNN]` (the tooltip text and, after a Run, `ExecutionResult.error`); match with `\[(TD-SHAPE-\d{3})\]`. The authoritative code list with default one-line meanings is `ERROR_CODES` in `core/shaping/common.py` (3.2); plan 03 registers the codes in the table of section 12 (paste it as is; wording may be refined, numbers never change). `ShapingError` also carries `.code`, `.detail` and `.columns` (columns involved) for `NodeError.columns`. `TD-SHAPE-005` ("required input has no data") is a tooltip, not an exception.

**Plan 09 (F-G / F-H2).** F-G globs `core/shaping` and `sql_guard` into the hidden imports (no edit here). F-H2: import `trigger_designer.core.sql_guard` (`check_select_only`, `make_locked_connection`, `run_select`; API in 3.8) to guard Formula and Filter-expression SQL.

**Plan 08 (headless).** Generated-code imports per node: 3.9.

## 12. TD-SHAPE code catalogue (plan 03 registers the codes in this table)

Every message is `[TD-SHAPE-NNN] <message>`; `{x}` are filled values. Severity is `error` for all. A code that several nodes raise is listed once under "All shaping nodes" and again only where its message differs. Grouped by node.

| Code | Title (plain language) | Message template | Fix hint |
|---|---|---|---|
| **All shaping nodes** | | | |
| TD-SHAPE-003 | A selected column is no longer there | `Column(s) not found: {columns}` | Open the node and pick the column again; the upstream data changed. |
| TD-SHAPE-005 | This node has no data to work on | `Input {n} has no data` (tooltip only) | Connect the input and fix the node upstream first. |
| **Record ID** | | | |
| TD-SHAPE-001 | The ID column needs a name | `Record ID column name is empty` | Type a name, for example RecordID. |
| TD-SHAPE-002 | That column name is already used | `Column '{name}' already exists` | Choose a name that is not in the data. |
| **Select Records** | | | |
| TD-SHAPE-001 | Choose a column to rank by | `Pick the column to rank by` | Pick the numeric column in "Rank by". |
| TD-SHAPE-004 | A setting is out of range | `Unknown mode {mode}` / `N must be at least 1` / `Row range must satisfy 1 <= start <= end` | Use N of 1 or more and a From row not after the To row. |
| **Find and Replace** | | | |
| TD-SHAPE-001 | Choose at least one column | `Pick at least one column` | Tick the text columns to change. |
| TD-SHAPE-002 | The new column already exists | `Output column already exists` | Change the suffix or leave it empty to replace in place. |
| TD-SHAPE-004 | A rule has an unknown mode | `Rule {i}: unknown mode` | Set the rule to Literal or Regex. |
| TD-SHAPE-040 | The pattern is not a valid regular expression | `Rule {i}: invalid pattern ({detail})` | Fix the pattern; look-around and back-references are not supported. |
| TD-SHAPE-041 | The pattern is too long | `Rule {i}: pattern longer than 500` | Shorten it or split it into two rules. |
| TD-SHAPE-042 | A rule has nothing to find | `Rule {i}: 'Find' is empty` | Type the text to find or remove the rule. |
| TD-SHAPE-043 | Too many rules | `At most 50 rules are allowed` | Merge rules or use two nodes. |
| TD-SHAPE-044 | Only text columns can be changed | `Only text columns can be changed` | Untick the number/date columns. |
| **Date Helper** | | | |
| TD-SHAPE-001 | A calculation is missing a date column | `Pick a date column` / `Pick the second date column` | Choose the date column(s) for each calculation. |
| TD-SHAPE-002 | An output name is already used | `Output column name already used` | Give each calculation a unique output name. |
| TD-SHAPE-004 | A setting is out of range | `Fiscal year start month must be 1-12` / `Unknown date operation {op}` | Pick a month from the list and a calculation from the list. |
| TD-SHAPE-050 | The column is not a date | `Column '{name}' is not a date or text` | Use a Date, Datetime or text column holding dates. |
| TD-SHAPE-052 | A holiday is not a valid date | `Holiday is not YYYY-MM-DD: {detail}` | Write holidays as 2024-12-25, one per line. |
| TD-SHAPE-053 | No working days selected | `Pick at least one working day` | Tick the days that count as working days. |
| **Pivot** | | | |
| TD-SHAPE-001 | Choose the header and value columns | `Pick the header column and the value column` | Set "Column headers" and "Values". |
| TD-SHAPE-004 | Unknown aggregation | `Unknown aggregation {name}` | Pick an aggregation from the list. |
| TD-SHAPE-060 | The same column is used twice | `Index, header and value columns must differ` | Use a different column for each role. |
| TD-SHAPE-061 | Too many new columns | `Header column has {n} distinct values (limit 500)` | Pick a header column with fewer distinct values or filter first. |
| **Unpivot** | | | |
| TD-SHAPE-001 | Choose columns to unpivot | `Pick at least one column to unpivot` | Tick the columns to turn into rows. |
| TD-SHAPE-002 | The new column names clash | `Name and value column names must be unique` | Use two different names that are not in the kept columns. |
| TD-SHAPE-060 | A column is both kept and unpivoted | `A column cannot be both an ID and a value column` | Untick it in one of the lists. |
| **Comment** | | | |
| (none) | The Comment node raises no codes | - | - |
| **Reconcile** | | | |
| TD-SHAPE-004 | A setting is out of range | `Unknown match type {t}` / `Tolerance mode must be absolute or percent` / `Tolerance and date window cannot be negative` | Use zero or a positive tolerance and window. |
| TD-SHAPE-050 | A date column is not a date | `Column '{name}' is not a date` | Pick a Date/Datetime or text column with dates. |
| TD-SHAPE-070 | Amount or date set on one side only | `Pick the amount/date column on both sides` | Fill both the left and right column, or neither. |
| TD-SHAPE-071 | Nothing to match on | `Add a key column pair or a date window` | Add at least one key pair, or choose date columns. |
| TD-SHAPE-072 | Too many possible matches | `{n} possible matches (limit 5,000,000); add a key column or narrow the date window` | Add a key column or reduce the date window. |
| **Window** | | | |
| TD-SHAPE-001 | A calculation needs a column | `Pick a source column` | Choose the column for the calculation. |
| TD-SHAPE-002 | An output name is already used | `Output column name already used` | Give each calculation a unique name. |
| TD-SHAPE-004 | A setting is out of range | `Unknown window operation {op}` / `Offset and window size must be at least 1` | Use 1 or more. |
| TD-SHAPE-091 | The column is not numeric | `'{name}' must be a number or text holding numbers` | Pick a numeric column for running totals and rolling sums. |
| **Text to Columns** | | | |
| TD-SHAPE-001 | Choose a column and a delimiter | `Pick the column to split` / `Delimiter is empty` | Fill the column and the pattern. |
| TD-SHAPE-004 | A setting is out of range | `Unknown split mode or output` / `Max splits must be {low}-49` | Use a value in the allowed range. |
| TD-SHAPE-040 | The pattern is not a valid regular expression | `Invalid pattern ({detail})` | Fix the pattern. |
| TD-SHAPE-044 | Only text columns can be split | `Only text columns can be split` | Choose a text column. |
| TD-SHAPE-101 | The split pattern can match nothing | `Pattern must not match an empty string` | Use a pattern that needs at least one character, e.g. `\s+` instead of `\s*`. |
| **Fuzzy Match** | | | |
| TD-SHAPE-001 | Choose the text columns | `Pick the text column on both sides` | Set the left and right text column. |
| TD-SHAPE-004 | A setting is out of range | `Unknown {setting} {value}` / `Threshold must be above 0 and at most 1` / `Prefix length must be 1-10` | Use a value in the allowed range. |
| TD-SHAPE-081 | Too many possible pairs | `{n} possible pairs (limit 5,000,000); use a longer prefix or add a block column` | Use a longer prefix or add a "Must also match" column. |
| TD-SHAPE-082 | Too many rows to compare without blocking | `Too many rows to compare without a blocking key; choose prefix or first-token blocking` | Turn on blocking. |
| **Multi-Field Formula** | | | |
| TD-SHAPE-001 | Missing column or suffix | `Pick at least one column` / `Suffix is empty` | Tick columns; give the suffix. |
| TD-SHAPE-002 | The new column already exists | `Output column already exists` | Change the suffix. |
| TD-SHAPE-004 | A setting is out of range | `At most 200 columns` / `Unknown mode` | Tick fewer columns. |
| TD-SHAPE-110 | Only one expression is allowed | `Only one expression is allowed` | Remove the semicolon. |
| TD-SHAPE-120 | The formula must use the column | `The formula must contain {col}` | Write `{col}` where the column goes. |
| (plus the SQL guard codes below) | | | |
| **SQL Query and the shared SQL guard (`core/sql_guard.py`, also used by plan 09)** | | | |
| TD-SHAPE-001 | The SQL is empty | `SQL is empty` | Type a SELECT query. |
| TD-SHAPE-004 | Bad table name | `Invalid table name {name}` | Internal; table names must be plain identifiers. |
| TD-SHAPE-110 | Only one statement is allowed | `Only one statement is allowed` | Remove everything after the first statement. |
| TD-SHAPE-111 | Only SELECT queries are allowed | `Only SELECT queries are allowed` | Use SELECT/WITH only; changing data or settings is not possible here. |
| TD-SHAPE-112 | That function or file access is not allowed | `This function is not allowed (files, system or random)` / `Reading files is not allowed` | Use a File Input node to read files; avoid random() and uuid(). |
| TD-SHAPE-113 | The SQL could not be run | `SQL could not be parsed: {detail}` / the first DuckDB message line | Fix the syntax or the table/column name; t2 and t3 need a connected input. |
| TD-SHAPE-114 | The SQL is too long | `SQL is longer than 20,000 characters` | Shorten the query. |
| TD-SHAPE-115 | The query took too long | `Query took longer than 25 s` | Filter earlier, or reduce the input size. |


*End of plan 07.*
