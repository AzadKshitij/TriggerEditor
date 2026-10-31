# Adding a node

Checked against the tree on branch `feature` (see the README for the commit).
The old recipe in `docs/plan/00-codebase-brief.md` section 3.7 and
`.github/skills/create-node/SKILL.md` are **stale**: they predate the Audit
family, `ShapingNode`, the op catalogue and the error registries. Use this page.

Pick the framework first:

| Your node | Use | Real examples |
|---|---|---|
| Takes 1..n frames, emits 1..n frames, settings are plain values | **`ShapingNode` / `ShapingContent`** (declarative form, generated code calls core). Default choice. | `Preparation/record_id.py` (single output), `Preparation/split.py` (2 outputs), `Join/reconcile.py` (2 inputs, 4 outputs), `Transform/window.py`, `Preparation/text_to_columns.py` |
| An audit test: a pure function plus a one-row Summary | **`AuditNode` / `AuditContent`** | `Audit/duplicates.py`, `Audit/gaps.py` (template for tests: `tests/support/audit_demo.py`) |
| A multi-edge input socket, a bespoke table editor, file dialogs | Hand-written `TriggerNode` + content | `Join/union.py` (`MultiInputNode`, hand-written with modern undo wiring), `InOut/file_input.py`, `InOut/file_output.py`. (`Preparation/select.py` has a bespoke table editor but is still a `ShapingContent`: override `create_layout` and keep the framework.) |

## The checklist (every node)

Do these in order. File paths are relative to `src/trigger_designer/` unless
they start with `tests/` or `docs/`.

1. **Enum member.** `core/node_configuration.py`: append `MY_NODE = auto()` at
   the **end** of the family enum (`PreparationNodes`, `JoinNodes`,
   `TransformNodes`, `ReportNodes`, `AuditNodes`, `IONodes`). The member *name*
   is the persisted identity (`preparation.my_node`); never rename, reorder
   for effect, or delete one. A new node needs no `V1_OPCODE_TO_OP` entry.
   Do not add a new family unless asked (it also needs a Shift+A group in
   `qt/helpers/context_menu_mixin.py`, a registry entry and `_OPCODE_ENUMS`).
2. **Core module** (Qt-free). `core/shaping/<name>.py` (or
   `core/audit/<name>.py`). Expose `DEFAULTS`, `apply_<name>(frame, settings)`,
   `run_node(frames, settings) -> list[LazyFrame]` and optionally
   `describe(frames, settings) -> [(chip text, "accent"|"muted"|"warning")]`.
   Raise `ShapingError(code, detail, columns)` for user mistakes. Keep it lazy
   (`as_lazy`, `schema_of`, `require_columns`, `unique_name` live in
   `core/shaping/common.py`).
3. **Node module.** `qt/widgets/nodes/<Folder>/<module>.py` with
   `@register_node(<Enum>.MY_NODE, NodeTypes.<FAMILY>)`. Folders: `InOut`,
   `Preparation`, `Join`, `Transform`, `Report`, `Audit`. File name is
   free-form (`Join/Append.py` is capitalised); no `__init__.py`.
4. **Lazy spec.** `qt/widgets/nodes/__init__.py`, `_LAZY_NODE_SPECS`:
   `{"module_path": "<Folder>.<module stem>", "node_code": <Enum>.MY_NODE,
   "node_type": NodeTypes.<FAMILY>, "node_title": "<Title>", "icon":
   "node_<name>"}`. `node_title` and `icon` **must equal the class attributes**.
   Skip it and the node still loads, but eagerly at startup. A non-node helper
   module that imports heavy dependencies goes in `_LAZY_HELPER_MODULES`
   instead (the Audit `_base` is there).
5. **Icon.** A 100x100 SVG at
   `resources/qt/images/node_icons/<Folder>/<Name>.svg` (rounded rect in the
   family colour, white glyph; copy `Preparation/RecordID.svg`) and a
   `qt/resources.json` entry
   `"node_<name>": {"path": "qt/images/node_icons/<Folder>/<Name>.svg", "mode": "rb"}`.
   The canvas, palette and Shift+A menu all resolve it through
   `ResourceManager`; there is nothing to compile. Until a real icon exists
   reuse an existing id (Normalize reuses `node_select`). A missing id returns
   `None` silently, so check the icon shows.
6. **Op catalogue row.** `core/headless/op_catalog.py`, `OPS`: add
   `_row("<family>.my_node", "<Title>")` (add `output_keys=("filePath",)` if
   the node holds an output path). `tests/unit/test_op_catalog_matches_registry.py`
   fails until you do, and the title must equal `node_title`.
7. **Error codes** (section "Error codes" below) in **both** registries.
8. **Packaging.** `trigger.spec` lists `core/audit`, `errors`, `excel`,
   `shaping`, `headless` and `workpaper` by globbing, so a new module in those
   packages is picked up. A new *top-level* `core/<x>.py` imported by generated
   code must be added to `_CORE_MODULES` in `trigger.spec` (otherwise the
   frozen app fails at Run with `ModuleNotFoundError`).
9. **Headless code policy.** Shaping nodes are covered (generated code imports
   only `run_node` from `trigger_designer.core.shaping.<x>`). If your generated
   code imports any other module or name, add it to `GENERATED_IMPORTS` in
   `core/headless/code_policy.py`, or `trigger-designer-cli run` will refuse the
   node (audit nodes are listed there by name; a new audit test needs its
   `Params`/`run_` pair added).
10. **Tests** (section "Tests to write").
11. **Docs.** A row in `docs/NODE_REFERENCE.md`, the user guide under
    `docs/guide/`, and a line under "Added" in `docs/CHANGELOG.md`. If the node
    changes behaviour of saved workflows, list it under "Behaviour changes".
12. **Verify.** `.venv\Scripts\python.exe -m ruff format <files>`, then
    `ruff check <files>`, then the focused tests, then `tests\unit` and
    `tests\e2e`. Smoke by hand: drop the node unwired, Run (no `NameError`);
    wire File Input in, Run; save, reload, Run; undo/redo a setting.

## A. Shaping node (the default)

`ShapingContent` gives you the settings dict, the dock, undo, deferred
evaluation, serialization, live compute and `get_code`. You declare:

| Class attribute | Meaning |
|---|---|
| `SETTINGS` | Default settings dict (deep-copied per node). Persisted as `{"settings": {...}}`. Add keys freely; never rename one. |
| `MODULE` | Dotted path of the core module; generated code imports `run_node` from it. |
| `RUNNER` | Function name, default `"run_node"`. |
| `INPUTS`, `OPTIONAL_INPUTS` | Number of input sockets; indexes that may stay unwired. |
| `OUTPUT_KINDS` | One name per output socket; variables are `var_<kind>_<id>`, the first is also `variable_name`, the rest `out<i>_variable_name`. |
| `FORM` | Tuple of `FormSection(title, fields, info, collapsible, collapsed)`. |
| `HISTORY` | Noun for undo text: `f"{HISTORY} {field label} Changed"`. |
| `SUMMARY` | Tail of the dock summary line. |
| `PRESENTATION_SETTINGS` | Setting keys that only affect display; kept out of generated code. |
| `sql_editors()`, `after_change()` | Optional hooks (Formula/Filter coalesce focus-out evaluation across their SQL editors). |

`Field(key, label, kind, ...)` kinds: `text`, `textarea`, `int`, `float`,
`check`, `combo` / `choices` (`options=((value, label), ...)`), `segment`,
`picker` / `columns` (many columns), `column` (one column; `blank=True` allows
none), `weekdays`, `suffix`, `list` (cards of sub-`items`, with `item_default`,
`summary`, `max_items`), `pair` (two sub-fields in a row), `note` (read-only
hint). `filter="text"|"numeric"|"numeric_only"|"date"` narrows the column
choices, `input=1` reads the schema of the second input, `show_if=lambda
settings: ...` shows/hides a row, `rebuild_on_change=True` rebuilds the form.

The node class sets `icon`, `node_code`, `node_type`, `node_title`,
`content_class`, `content_label_objname`, and optionally `output_text` (one
letter per output socket).

`ShapingNode.processInputs` already: resolves each input by socket, applies
`live_sample` (first 100 rows), sets the input-missing error `TD-SHAPE-005`,
calls `content.compute()` and turns a `ShapingError` into a translated node
error. You do not override it.

### Worked example: "Head Rows" (verified)

The three files below were written to a scratch directory and **run against
the repo with pytest: 9 passed** (core, live == generated code, unwired
outputs, error code on the node, state round trip, dock build, undo/redo).
The only differences from a real node: the scratch node borrowed an existing
enum member and registered itself with `register_node_now(10_001, ...)`
because the verification must not edit `node_configuration.py`; in the real
node use the new enum member and the decorator shown here.

`core/shaping/head_rows.py`

```python
"""Head Rows: keep the first N rows. Qt-free."""

from __future__ import annotations

import polars as pl

from trigger_designer.core.shaping.common import (
    Frame,
    ShapingError,
    as_lazy,
    schema_of,
)

DEFAULTS = {"rows": 10, "add_position": False, "position_name": "Position"}


def normalize(settings: dict) -> dict:
    out = {**DEFAULTS, **(settings or {})}
    out["rows"] = int(out["rows"])
    out["position_name"] = str(out["position_name"]).strip()
    return out


def apply_head(frame: Frame, settings: dict) -> pl.LazyFrame:
    s = normalize(settings)
    lf = as_lazy(frame)
    if s["rows"] < 1:
        raise ShapingError("TD-SHAPE-004", "Rows must be 1 or more")
    out = lf.head(s["rows"])
    if s["add_position"]:
        if not s["position_name"]:
            raise ShapingError("TD-SHAPE-001", "Position column name is empty")
        if s["position_name"] in schema_of(lf):
            raise ShapingError(
                "TD-SHAPE-002",
                f"Column '{s['position_name']}' already exists",
                [s["position_name"]],
            )
        out = out.with_row_index(s["position_name"], offset=1)
    return out


def describe(frames: list, settings: dict) -> list[tuple[str, str]]:
    return [(f"first {normalize(settings)['rows']:,} rows", "accent")]


def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    return [apply_head(frames[0], settings)]
```

`qt/widgets/nodes/Preparation/head_rows.py`

```python
"""Head Rows node: Qt wrapper only; the logic is core/shaping/head_rows.py."""

from trigger_designer.core.node_configuration import (
    NodeTypes,
    PreparationNodes,
    register_node,
)
from trigger_designer.core.shaping import head_rows as core
from trigger_designer.qt.helpers.shaping_support import (
    Field,
    FormSection,
    ShapingContent,
    ShapingNode,
)


class HeadRowsContent(ShapingContent):
    SETTINGS = core.DEFAULTS
    MODULE = "trigger_designer.core.shaping.head_rows"
    OUTPUT_KINDS = ("head",)
    HISTORY = "Head Rows"
    SUMMARY = "first N rows"
    FORM = (
        FormSection(
            "",
            (
                Field("rows", "Rows", "int", minimum=1, maximum=10_000_000),
                Field("add_position", "Add position", "check"),
                Field(
                    "position_name",
                    "Name",
                    "text",
                    placeholder="Position",
                    show_if=lambda s: bool(s.get("add_position")),
                ),
            ),
        ),
    )


@register_node(PreparationNodes.HEAD_ROWS, NodeTypes.PREPARATION)  # new member
class TriggerNode_HeadRows(ShapingNode):
    icon = "node_head_rows"  # resources.json id
    node_code = PreparationNodes.HEAD_ROWS
    node_type = NodeTypes.PREPARATION
    node_title = "Head Rows"
    content_class = HeadRowsContent
    content_label_objname = "trigger_node_head_rows"
```

Then add the enum member, the `_LAZY_NODE_SPECS` entry, the SVG +
`resources.json` entry, the op-catalogue row, and the tests. The behaviour
test that was run (minimum useful set, copy it for a real node):

```python
def test_live_equals_generated_code():
    window = TriggerSubWindow()
    source = Source(window.scene, FRAME.lazy())          # tests/unit/test_shaping_nodes.py::Source
    node = TriggerNode_HeadRows(window.scene)
    Edge(window.scene, source.outputs[0], node.inputs[0])
    node.content.settings.update({"rows": 3, "add_position": True})
    node.markDirty(True)
    out = node.eval()
    assert out is not None and not node.isInvalid()
    live = out[0]["data"].collect()
    namespace = {"var_src": FRAME.lazy()}
    exec(node.get_code(), {"__name__": "__main__", "pl": pl}, namespace)  # noqa: S102
    assert namespace[node.content.variable_name].collect().equals(live)


def test_bad_setting_marks_invalid_with_code():
    window = TriggerSubWindow()
    ...wire as above, settings {"rows": 0}...
    assert node.eval() is None and node.isInvalid()
    assert node.current_error.code == "TD-SHAPE-004"


def test_undo_roundtrip():
    node.eval()
    window.scene.history.storeHistory("Baseline")        # undo needs a starting point
    node.content.set_setting("rows", 2, "Head Rows Changed")
    window.scene.history.undo()
    assert node.content.settings["rows"] == 3
    window.scene.history.redo()
    assert node.content.settings["rows"] == 2
```

### Rules the framework enforces for you (do not bypass)

* A setting change goes through `content.set_setting(key, value, history_text,
  merge_key=None, structural=False, evaluate=None)`: guard (`is_syncing` /
  `history.is_restoring_history`), diff, mutate the model, mark the scene
  modified, then schedule evaluation (deferred) and push **one** undo command
  with `push_property_change(("settings", key), old, new, ...)`
  (`push_list_change` when `structural=True` and the value is a list: the
  widgets are rebuilt on restore). `merge_key` collapses a typing burst; the
  built-in text/number fields pass one. See `conventions.md` for the undo rules.
* Restore writes widgets from the model inside `syncing(content)`;
  `_sync_widgets_from_model` / `_rebuild_widgets` are implemented for you.
* Every dock control is also tracked by `registerUnboundDockWidgets`; do not
  call `registerInputWidget` for form fields.
* Dock layout rules (spacing 2, margins 5, controls H30, icon buttons) are in
  `docs/DESIGN_SYSTEM.md`; use the shared widgets in
  `qt/widgets/common/config_widgets.py` and never inline `setStyleSheet`.

## B. Audit node

Pattern in `qt/widgets/nodes/Audit/_base.py`; read `Audit/duplicates.py` (168
lines) and `core/audit/duplicates.py` side by side.

1. **Core** `core/audit/<test>.py`: a `@dataclass class XParams(ParamsBase)`
   (every field has a default and is JSON friendly; field names are persisted
   keys) and `run_x(frame, params) -> AuditResult`. Validate first and raise
   `AuditConfigError("TD-AUDIT-0nn", message, field=..., columns=...)` using
   `need`, `need_many`, `check_range`, `check_date_format`, `check_reserved` in
   `core/audit/common.py`. Build frames lazily; build the one-row Summary with
   `summary_frame(...)` so the schema matches `BASE_SUMMARY`; return
   `AuditResult(frames=(...), summary_index=..., log_index=..., extras={...})`.
   `AuditResult.for_run()` collects only the one-row summary/log frames.
   Internal helper columns start with `__td_` (`ROW`); reject inputs that
   already use that prefix.
2. **Node** `qt/widgets/nodes/Audit/<test>.py`:
   ```python
   class XContent(AuditContent):
       PARAMS = XParams
       RUN = staticmethod(run_x)          # staticmethod, or it binds as a method
       OP = "audit.x"                     # also the undo merge-key prefix
       TEST_NAME = "X"
       OUTPUT_KINDS = ("xexc", "xsum")    # var_<kind>_<id> per socket
       SUMMARY_INDEX = 1                  # socket holding the one-row Summary
       EXCEPTIONS_INDEX = 0               # socket with exception rows
       HISTORY = "X Setting Changed"
       def build_dock(self, dock_layout): ...   # self.section / self.bind / self.add_*
       def dock_context(self): ...
       def dock_summary(self): ...

   @register_node(AuditNodes.X, NodeTypes.AUDIT)
   class TriggerNode_X(AuditNode):
       icon = "node_x"; node_code = AuditNodes.X; node_type = NodeTypes.AUDIT
       node_title = "X"; content_class = XContent
       OUTPUT_TYPES = (3, 1); output_text = ("E", "S")   # 3 = data socket, 1 = summary/log
       content_label_objname = "trigger_node_x"; style = {}
   ```
   `init_audit_state` raises if a `PARAMS` field name shadows a content
   attribute (rename the field). Settings change through
   `content.set_setting(name, value, text, merge_key=..., structural=...)`; the
   `add_picker/add_segment/add_check/add_spin/add_dspin/add_combo/add_text/
   add_lines/add_checklist/add_digits` helpers wire a control to a setting
   (`bind` does it for a custom widget). Call `self.result_section()` last for
   the Summary text and the "Count exceptions now" button. Hooks:
   `build_result`, `on_result`, `on_live_failed` (call `super()` first),
   `live_notice`, `format_summary`, `summary_from_frame`. `LIVE_SUMMARY = True`
   makes the Summary fill on every live evaluation (Benford, Sample); otherwise
   it fills at Run (`after_execution`) or on the Count button.
3. Lazy spec, icon (`Audit/<Name>.svg`), op-catalogue row, AuditNodes member,
   `_LAZY_HELPER_MODULES` untouched (already lists `Audit._base`).
4. **Codegen** is inherited: `AuditContentMixin.get_code` emits the
   `from <module> import XParams, run_x` snippet. Do not write your own.
5. Test with `tests/support/audit_demo.py::demo_graph(frame, NodeClass)` (builds
   a window, a source node and your node) like `tests/ui/test_audit_duplicates_dock.py`.
   Audit test fixtures: `tests/support/audit_ledger.py::make_ledger()` has
   planted anomalies with known counts.

## C. Hand-written node (only if you must)

Two classes in one module: `TriggerNode_X(TriggerNode)` and
`XContent(QDMNodeIconContentWidget, TriggerChangeHandler[, SerializableContentMixin])`
(or subclass `ConfigContent` from `qt/node_content.py`, which supplies the `evaluate` signal, `node`
property, `history`, `initUI`). You then own: `initInnerClasses`,
`processInputs` (return a list of `{"data", "variable_name"}` or `None` after
setting an error), `get_code` (rules in `architecture.md` section 6),
`create_layout`, `serialize`/`deserialize`, the undo calls and
`_sync_widgets_from_model`. Read `Join/union.py` (the modern reference) and the `ShapingContent` source in
`qt/helpers/shaping_support.py` for the shape of `set_setting`, `_sync_widgets_from_model`,
`serialize`/`deserialize` and `get_code`.
Sockets: `super().__init__(scene, inputs=[1], outputs=[3, 3], output_text=["T","F"])`
(the int is a colour class; one entry per socket).

## Error codes

A user mistake in a node must reach the user as a stable `TD-` code with a
plain sentence, not a traceback.

* **Shaping nodes**: raise `ShapingError("TD-SHAPE-nnn", detail, columns)`. A
  *new* code must be added to **both**
  1. `core/shaping/common.py::ERROR_CODES` (`code -> short description`), and
  2. the `_PASSTHROUGH` table in `core/errors/catalogue.py`
     (`code -> (title, hint, severity)`), which becomes a catalogue entry with
     `passthrough=True`.
  Never reuse or renumber a code. Parse errors from the SQL guard use
  `TD-SHAPE-110..115`.
* **Audit nodes**: `AuditConfigError("TD-AUDIT-nnn", ...)`; the code goes in
  `_PASSTHROUGH` (there is no separate `ERROR_CODES` for audit). `TD-AUDIT-101`
  .. `103` are Summary warnings, not exceptions.
* Tests that pin it: `tests/unit/test_error_code_registry.py` (every quoted
  `"TD-..."` literal in `src/` must be in the catalogue; every `TD-SHAPE-*` literal
  in `ERROR_CODES`). It only sees literals, so never build a code with an f-string.
  Per-node tests still assert `code in ERROR_CODES and code in CATALOGUE` for the
  codes the node raises.
* More: `error-system.md`.

## Tests to write

| Layer | File | Must prove |
|---|---|---|
| Unit | `tests/unit/test_<name>_core.py` | Hand-computed expectations (not "whatever it printed"); each error code (`pytest.mark.parametrize`); `test_error_codes_are_registered`; input stays lazy; zero-row input stays typed; `test_core_has_no_qt_import`; **live == generated code** (build node, `eval()`, `exec(get_code())`, `.equals`); unwired node defines every output variable; bad settings raise the same code live and in generated code. Model: `tests/unit/test_text_to_columns_core.py`. |
| Unit | `tests/unit/test_node_titles.py` / `test_shaping_nodes.py` | Only if you add a registry-identity case. `test_op_catalog_matches_registry.py` already covers the catalogue row. |
| UI | `tests/ui/test_<name>_dock.py` | Dock builds with and without input (`EmptyStateLabel`); each control writes the setting; undo and redo restore the control; deferred run (`flush(node)`); save/load round trip. Models: `tests/ui/test_audit_duplicates_dock.py`, `tests/ui/test_shaping_docks.py`. |
| E2E | `tests/e2e/test_<name>_workflow.py` | File Input -> node -> File Output through `run_workflow_and_wait`; expected rows computed by hand in the test. Model: `tests/e2e/test_text_to_columns_workflow.py`. Add a `WorkflowCase` + golden in `tests/support/corpus.py` only for checked-in sample workflows. |

Fixtures you will use: `qtbot`, `no_modal_dialogs` (e2e), `clean_preferences`,
`tests/support/flush.py::flush`, `tests/support/workflows.py`
(`run_workflow_and_wait`, `executed_frame`, `nodes_titled`). More in
`testing.md`.

## Common mistakes

* Reading `incom_data.columns` on a `LazyFrame` (use `frame_schema`).
* Forgetting an output variable on the unwired/misconfigured path
  (`NameError` downstream).
* Interpolating a setting into code (`f"'{x}'"`); the AST guard will fail.
* Registering a `TD-SHAPE` code in only one of the two places.
* A second `QApplication` in a test (process abort): use the `qapp` fixture.
* Writing widgets from a command instead of mutating the model and calling
  `sync_from_model()`.
* Renaming an enum member or a persisted settings key.
* Putting logic in the Qt file: it is then untestable without a window and
  absent from the generated code.
