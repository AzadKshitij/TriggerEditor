# Legacy node modernization - implementation plans

Status: in progress - Count, Running Total, Sort, Split, Unique, Graph,
Normalize, Transpose, Filter, Cleansing, Rows, Aggregate, Formula, Append and
Join and File Output are implemented; Union and File Input are planned.
Reference migration: Select (`23eadb8`).
Authoritative architecture: `docs/plan/07-shaping-nodes.md` and
`docs/plan/08-simplify-node-base.md`.

This folder contains one implementation brief per remaining legacy node.
The briefs are written for a smaller coding model: each names the files,
the settings, the exact existing methods to extract, the UI contract, the
legacy loader decision and the tests that must pass.

**Do not implement these as one change.** One node per branch/commit, in the
order in [Implementation order](#5-implementation-order-least-destructive-first).

---

## 1. Scope

### Already modernized - reference, no work

| Node | Core | Qt content | Core tests | UI tests |
|---|---|---|---|---|
| Record ID | `core/shaping/record_id.py` | `Preparation/record_id.py` | `tests/unit/test_shaping_p1.py` | `tests/ui/test_shaping_docks.py` |
| Select Records | `core/shaping/select_records.py` | `Preparation/select_records.py` | `tests/unit/test_shaping_p1.py` | `tests/ui/test_shaping_docks.py` |
| Find and Replace | `core/shaping/find_replace.py` | `Preparation/find_replace.py` | `tests/unit/test_shaping_p1.py` | `tests/ui/test_shaping_docks.py` |
| Date Helper | `core/shaping/date_helper.py` | `Preparation/date_helper.py` | `tests/unit/test_shaping_p1.py` | `tests/ui/test_shaping_docks.py` |
| Pivot | `core/shaping/reshape.py` | `Transform/pivot.py` | `tests/unit/test_shaping_p1.py` | `tests/ui/test_shaping_docks.py` |
| Unpivot | `core/shaping/reshape.py` | `Transform/unpivot.py` | `tests/unit/test_shaping_p1.py` | `tests/ui/test_shaping_docks.py` |
| Reconcile | `core/shaping/reconcile.py` | `Join/reconcile.py` | `tests/unit/test_shaping_p1.py` | `tests/ui/test_shaping_docks.py` |
| **Select** | `core/shaping/select.py` | `Preparation/select.py` | `tests/unit/test_select_core.py` | `tests/ui/test_select_dock.py` |

### Legacy nodes covered by this folder

This table is an inventory in family order, not the implementation order.
The numeric file prefixes (`01-`, `02-`, ...) are stable inventory IDs, not
sequence numbers. Use
[Implementation order](#5-implementation-order-least-destructive-first) for
the sequence.

| # | Plan | Node | Current module | Target core |
|---|---|---|---|---|
| 01 | `01-file-input.md` | File Input | `InOut/file_input.py` | `core/shaping/file_input.py` (wraps `core/input_source.py`) |
| 02 | `02-file-output.md` | File Output | `InOut/file_output.py` | `core/shaping/file_output.py` |
| 03 | `03-append.md` | Append | `Join/Append.py` | `core/shaping/append.py` |
| 04 | `04-join.md` | Join | `Join/join.py` | `core/shaping/join.py` |
| 05 | `05-union.md` | Union | `Join/union.py` | `core/shaping/union.py` |
| 06 | `06-cleansing.md` | Cleansing | `Preparation/cleansing.py` | `core/shaping/cleansing.py` |
| 07 | `07-filter.md` | Filter | `Preparation/filter.py` | `core/shaping/filter.py` |
| 08 | `08-aggregate.md` | Aggregate (GroupBy) | `Preparation/groupby.py` | `core/shaping/aggregate.py` |
| 09 | `09-formula.md` | Formula | `Preparation/formula.py` | `core/shaping/formula.py` |
| 10 | `10-sort.md` | Sort | `Preparation/sort.py` | `core/shaping/sort.py` |
| 11 | `11-unique.md` | Unique | `Preparation/unique.py` | `core/shaping/unique.py` |
| 12 | `12-split.md` | Split | `Preparation/split.py` | `core/shaping/split.py` |
| 13 | `13-normalize.md` | Normalize | `Preparation/normalize_columns.py` | `core/shaping/normalize.py` |
| 14 | `14-rows.md` | Rows | `Preparation/dynamic_row_builder.py` | `core/shaping/rows.py` |
| 15 | `15-count.md` | Count | `Transform/count_records.py` | `core/shaping/count.py` |
| 16 | `16-running-total.md` | Running Total | `Transform/running_total.py` | `core/shaping/running_total.py` |
| 17 | `17-transpose.md` | Transpose | `Transform/transpose.py` | `core/shaping/transpose.py` |
| 18 | `18-graph.md` | Graph | `Report/graph.py` | `core/shaping/graph.py` |
| 19 | `19-select-reference.md` | Select (done) | `Preparation/select.py` | reference only |

Not in scope: Comment (`Documentation/comment.py`) is not registered. Do not
add it while doing these plans.

---

## 2. What "modernized" means

A modernized node has exactly these layers:

1. **Qt-free core** - `src/trigger_designer/core/shaping/<name>.py`
   - `DEFAULTS: dict` - the one settings schema.
   - `run_node(frames: list, settings: dict) -> list[pl.LazyFrame]`.
   - optional `normalize(settings) -> dict`, `describe(frames, settings) -> list[(text, tone)]`.
   - imports core modules and data libraries only (`polars`, `duckdb`,
     `core.utils`, `core.input_source`). **Never** imports Qt.
2. **`ShapingContent`** - a subclass in the existing node module.
   - `SETTINGS = core.DEFAULTS`, `MODULE = "trigger_designer.core.shaping.<name>"`,
     `RUNNER = "run_node"`, `INPUTS`, `OUTPUT_KINDS`, `HISTORY`, `SUMMARY`, `FORM`.
   - the dock is built from `FORM` for normal nodes, or `create_layout` when
     the node needs a table/editor (Select, Join, Aggregate, Formula, Union).
   - all model edits go through `set_setting(...)` or a table adapter that
     calls it. No direct widget-to-widget model.
3. **`ShapingNode`** - a subclass in the same module.
   - preserves `icon`, `node_code`, `node_type`, `node_title`, `content_class`,
     `output_text`, `content_label_objname`.
   - override only to follow upstream renames (`processInputs`) or to preserve
     a special run hook.
4. **No legacy runtime state** - no `incom_data`, `incoming_variable`, `data`,
   `changes`, `apply_changes`, `update_data`, `process_data` or custom
   `get_code` in the new content. The only allowed custom execution is the
   documented sink/Graph exception in the per-node plan.
5. **One-way loader** - optional `deserialize` override translating the old
   saved-content keys into `settings`; it never writes the old keys.
6. **Tests** - core unit tests, dock/undo tests and the saved-workflow e2e
   cases that contain the node.

### Settings are the only truth

- `settings` is a plain JSON-compatible dict.
- New keys added later are safe: `SerializableContentMixin` merges dict
  defaults.
- Every control must be undoable. `ShapingContent.create_layout` tracks
  unbound dock controls, but nodes should still register their controls.
- Never mutate `SETTINGS` in place. `ShapingContent` copies it per instance.
- A list that changes size (`formula sections`, `mapping rows`, `sort rows`)
  is one `push_list_change`; a single field is `push_property_change` with a
  burst merge key for typing.

---

## 3. Shared contracts

Read these before editing any node:

| Concern | File |
|---|---|
| base content, form engine, list cards, undo projection | `qt/helpers/shaping_support.py` |
| common content plumbing | `qt/helpers/config_content.py` |
| core helpers and error codes | `core/shaping/common.py` |
| Select reference core | `core/shaping/select.py` |
| Select reference UI | `qt/widgets/nodes/Preparation/select.py` |
| shared dock widgets | `qt/widgets/common/config_widgets.py` |
| design system | `docs/DESIGN_SYSTEM.md` |
| node base phases | `docs/plan/08-simplify-node-base.md` |

### 3.1 `run_node` contract

```python
def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    ...
```

- One output per output socket, in socket order.
- Accept `pl.DataFrame` or `pl.LazyFrame` input; normalise with
  `as_lazy` unless the node must collect (document why).
- Return `LazyFrame`s. Collect only inside the runner where the algorithm
  requires it, then return `.lazy()` (Join, Filter, Formula, Graph).
- Read the schema with `schema_of` / `frame_schema`, never `.columns` on a
  lazy frame.
- Use `require_columns` for configured columns. Missing configured columns
  are `TD-SHAPE-003`, not a silent pass-through, unless the per-node plan
  says otherwise.
- Use `ShapingError` for expected configuration/data errors.
- Preserve current behaviour first; do not redesign outputs while migrating.

### 3.2 Content contract

Minimal form-driven content:

```python
class SortContent(ShapingContent):
    SETTINGS = core.DEFAULTS
    MODULE = "trigger_designer.core.shaping.sort"
    OUTPUT_KINDS = ("sort",)
    INPUTS = 1
    HISTORY = "Sort"
    SUMMARY = "sort keys"
    FORM = (
        FormSection("Sort keys", (Field("keys", "Sort by", "list", items=(...)),)),
    )
```

- `FORM` sections are the default. A table/editor is allowed only where the
  plan says so; keep the existing specialized widget rather than weakening it.
- Do not call `setStyleSheet`; use object names and existing QSS.
- Icon buttons: 30x30, 12 px icon, tooltip + accessible name.
- Controls: 30 px high. Main layout: spacing 2, margins 5. Toolbar: 40 px.
- Use `ColumnPicker`, `ColumnChecklist`, `RuleStack`, `SegmentedControl`,
  `ConfigSection`, `FormRow`, `NoWheelComboBox` from `qt/widgets/common`.

### 3.3 Node contract

```python
@register_node(PreparationNodes.SORT, NodeTypes.PREPARATION)
class TriggerNode_Sort(ShapingNode):
    icon = "node_sort"
    node_code = PreparationNodes.SORT
    node_type = NodeTypes.PREPARATION
    node_title = "Sort"
    content_class = SortContent
    output_text = ("Out",)
    content_label_objname = "trigger_node_sort"
    style = {}
```

- Do not change enum values, opcodes, title, icon or class name.
- Keep the existing registry entry in `qt/widgets/nodes/__init__.py` unchanged
  unless the module path itself must move (it must not).
- If the node renames columns, override `processInputs` exactly like Select:

```python
def processInputs(self, input_values):
    try:
        input_node = self.getInput(0)
        if input_node is not None:
            self.content.apply_upstream_renames(upstream_rename_map(input_node))
    except (AttributeError, ValueError, RuntimeError):
        pass
    return super().processInputs(input_values)
```

### 3.4 Legacy loader contract

Use the Select pattern (`qt/widgets/nodes/Preparation/select.py:603-669`):

```python
def deserialize(self, data, hashmap={}):  # noqa: B006
    if "settings" not in data and ("<old key>" in data):
        data = dict(data)
        data["settings"] = self._legacy_settings(data)
    return super().deserialize(data, hashmap)
```

- Loader is one-way. Do not add setters/properties for old attributes.
- Only add a loader when a checked-in workflow under `savedfiles/` or a
  user-visible saved file needs it. The per-node plan says which.
- Map old keys to the new settings schema; do not keep both models alive.

### 3.5 Tests and gates

For every node:

1. **Core** - `tests/unit/test_<name>_core.py`
   - normal case, empty settings, missing columns, expected error codes,
     lazy input, DataFrame input, multiple outputs.
2. **Dock** - `tests/ui/test_<name>_dock.py`
   - `create_layout` builds with a frame;
   - edit -> setting -> `node.eval()` changes output;
   - undo/redo restores both model and widget;
   - generated code executes to the same frame as live.
3. **Existing tests** - update old tests that touch removed internals.
   Do not keep a compatibility method just to keep an old test green.
4. **Saved workflows** - run the cases in `savedfiles/` that contain the node:
   - `tests/e2e/test_workflow_goldens.py`
   - `tests/e2e/test_input_types_e2e.py`
   - `tests/e2e/test_graph_run.py`
5. **Focused command**:

```powershell
uv run --project . ruff format <changed files>
uv run --project . ruff check <changed files>
uv run --project . pytest tests/unit/test_<name>_core.py tests/ui/test_<name>_dock.py -q
uv run --project . pytest tests/unit tests/e2e -q
```

The full `tests/ui` suite has a pre-existing Formula-editor teardown abort.
Use targeted UI files until that is fixed; run the new dock file and the
already-green shaping UI files.

---

## 4. Standard form recipe

Use `Field.kind` values exactly as implemented in `shaping_support.py`:

| Kind | Widget | Use |
|---|---|---|
| `text` | `QLineEdit` | names, paths, titles |
| `textarea` | `QPlainTextEdit` | expressions, SQL |
| `int` / `float` | `QSpinBox` / `QDoubleSpinBox` | limits, percentages |
| `check` | `QCheckBox` | booleans |
| `combo` | `NoWheelComboBox` | mode/operation |
| `segment` | `SegmentedControl` | 2-4 modes |
| `column` | single-select `ColumnPicker` | one column |
| `columns` / `picker` | multi-select `ColumnPicker` | column lists |
| `choices` | `ColumnChecklist` | compact multi-select |
| `list` | `RuleStack` cards | ordered rules/rows |
| `pair` | two controls in one form row | min/max |
| `suffix` | `SuffixEditor` | keep-original rename |
| `note` | hint label | explanations only |

- `show_if` for dependent fields (e.g. seed only when random).
- `summary` for list-card captions.
- `rebuild_on_change` only when the change alters widget structure.
- `max_items` for safety; use the old node's cap where it had one.

---

## 5. Implementation order (least destructive first)

One node per commit. Stop and review after each tier. A later node is only
started when the earlier tier's focused tests and saved-workflow cases are
green.

The order is by **blast radius**: a bug in an early node changes row order,
sorting or one additive column. A bug in a late node can rewrite the schema,
multiply rows, merge two inputs or write files. UI complexity is secondary to
data risk.

### Tier 0 - prove the recipe on the smallest, lowest-risk nodes

1. **Count** (`15-count.md`) - no settings, one row out.
2. **Running Total** (`16-running-total.md`) - additive columns only.
3. **Sort** (`10-sort.md`) - row order only, no schema change.
4. **Split** (`12-split.md`) - partitions rows, loses no columns.
5. **Unique** (`11-unique.md`) - removes rows, but the removal is the point.
6. **Graph** (`18-graph.md`) - pass-through data, chart side effect only.

### Tier 1 - one-to-one schema rewrites

7. **Normalize** (`13-normalize.md`) - renames columns, keeps row count.
8. **Transpose** (`17-transpose.md`) - wide to long; changes shape but keeps
   all values.

### Tier 2 - value and row mutation

9. **Filter** (`07-filter.md`) - drops rows, two outputs; expression mode is
   the first arbitrary SQL surface.
10. **Cleansing** (`06-cleansing.md`) - changes values and can drop rows and
    columns.
11. **Rows** (`14-rows.md`) - generates rows and adds a column.

### Tier 3 - aggregation and arbitrary expressions

12. **Aggregate** (`08-aggregate.md`) - groups and replaces the schema; the
    action table is a larger custom dock.
13. **Formula** (`09-formula.md`) - arbitrary DuckDB expressions and the
    Formula editor; highest single-input risk.

### Tier 4 - multi-input

14. **Append** (`03-append.md`) - two inputs, schema union.
15. **Join** (`04-join.md`) - two inputs, three outputs, suffixes and renames.
16. **Union** (`05-union.md`) - dynamic input count and manual column mapping.

### Tier 5 - side effects

17. **File Output** (`02-file-output.md`) - writes to disk; live must not
    write, Run must.
18. **File Input** (`01-file-input.md`) - source of every workflow, largest
    saved-state surface and existing test matrix.

Reason for the order: Count is the smallest possible runner and dock, so it
proves the contract with almost no data risk. Running Total, Sort, Split,
Unique and Graph are still fixed-arity and single-input, but each adds one
new concern (additive columns, ordering, two outputs, chart/run hook).
Normalize and Transpose change the schema one-to-one. Filter and Cleansing
discard data. Aggregate and Formula are the largest single-input engines.
Append/Join/Union introduce multiple sockets and output arity. File
Output/Input are last because they touch the filesystem and File Input is
upstream of every saved workflow.

Do not skip ahead to Join or File Input while an earlier tier is red. A
failure in Count or Sort is a scaffolding bug that would otherwise be
repeated in every later node.

---

## 6. Global acceptance checklist

A node migration is done only when all are true:

- [ ] New core module exists and has no Qt imports.
- [ ] `DEFAULTS` is the only default schema; old defaults are not duplicated.
- [ ] `run_node` returns one lazy output per socket in socket order.
- [ ] Live and generated code call the same core function.
- [ ] Content is `ShapingContent` or the documented exception.
- [ ] Node is `ShapingNode` or the documented exception.
- [ ] No `changes`/`incom_data`/`incoming_variable`/`data`/`update_data`
      runtime path remains in the modernized node.
- [ ] Settings changes are undoable and survive serialize/deserialize.
- [ ] Dock follows `docs/DESIGN_SYSTEM.md` and has no inline styles.
- [ ] Legacy loader (if required) is one-way and tested.
- [ ] Core + dock tests pass; saved-workflow e2e cases pass.
- [ ] Formatting/lint on changed files is clean.
- [ ] No unrelated type annotations or formatting churn.
- [ ] One commit with a node-scoped message.

---

## 7. Hard rules

1. **Do not redesign node behaviour during migration.** The old implementation
   is the oracle. Extract it, preserve defaults and edge cases, then improve
   only where the per-node plan explicitly lists a fix.
2. **Do not add compatibility properties for old attributes.** Use a one-way
   loader and update tests.
3. **Do not copy `get_code` into the new content.** The shared `ShapingContent`
   codegen is the point of the migration. Only File Output (side effect) and
   Graph (run hook) may override it, as specified.
4. **Do not use `getSocketValue` in fixed-arity `ShapingNode` code.** The base
   `ShapingNode.processInputs` already uses `getInputWithSocket`.
5. **Do not change `node_base.py` for a node migration.** The node_base
   redesign phases own that file. If a node appears to need a new base hook,
   stop and raise it in the plan rather than patching `node_base.py`.
6. **Do not add new dependencies.** Polars, DuckDB and existing helpers are
   enough.
7. **Do not regenerate e2e goldens to hide a behavior change.** Only regenerate
   when the plan says the output is intentionally changed; otherwise fix the
   loader/core.
