# Graph - modernization plan

Status: not started.
Implementation order: 6 of 18 (Tier 0, pass-through data, chart side effect).
Read first: `plans/nodes/README.md`.

## 1. Current implementation

- File: `src/trigger_designer/qt/widgets/nodes/Report/graph.py`.
- Content: `GraphContent` (line 110).
- Node: `TriggerNode_Graph` (line 612).
- Inputs: one. Outputs: one - the input frame is forwarded unchanged.
- Settings today:
  - `graph_type` (`line`, `bar`, `scatter`)
  - `x_column`, `y_column`, `color_column`
  - `aggregation`
  - `title`
- Old execution: `TriggerNode_Graph.processInputs` stores `incom_data`,
  forwards the frame, and calls `content.update_column_options()`.
- Chart building already lives in the Qt-free `core/charts.py`
  (`build_chart_spec`, `CHART_TYPES`, `AGGREGATIONS`).
- Old UI: graph type, X/Y/color columns, aggregation, title, and an
  "Open Graph" button. `open_graph_in_new_window` launches `ChartWindow`.
- Run hook: `GraphContent.after_execution(context)` receives the executed
  frame on the worker thread, latches `workflow_ran_successfully`, and emits
  `runDataReady` so the GUI slot can open/refresh the chart.
- Existing tests: `tests/ui/test_graph_dock.py`, `tests/ui/test_chart_view.py`,
  `tests/e2e/test_graph_run.py`, `tests/unit/test_chart_model.py`.
- Saved workflow: `savedfiles/8. In-Graph.tds`.

## 2. Target

- Core: `src/trigger_designer/core/shaping/graph.py`.
- Content: `GraphContent(ShapingContent)` with a custom `create_layout`.
- Node: `TriggerNode_Graph(ShapingNode)`.
- Settings: the six keys above.
- Output kind: `("graph",)`.
- `INPUTS = 1`; `HISTORY = "Graph"`;
  `SUMMARY = "chart, pass-through"`.

### Settings schema

```python
DEFAULTS = {
    "graph_type": "line",
    "x_column": "",
    "y_column": "",
    "color_column": "",
    "aggregation": "",
    "title": "",
}
```

## 3. Behavior contract

- **Data is pass-through.** The output frame must be the input frame
  unchanged (same schema, rows, order, lazy/eager kind at the boundary).
  The chart is a side effect, not a transform.
- A graph with unconfigured columns still forwards data; it must not
  invalidate the workflow.
- Column options are projected from the live schema every time the input
  changes; missing saved columns show as missing, do not silently rewrite
  them to another column (old behavior: keep the saved string, let
  `build_chart_spec` report the error when opened).
- `graph_type` must be one of `CHART_TYPES`; unknown -> `"line"`.
- `aggregation` is `""` (default), `"none"`, or an `AGGREGATIONS` value;
  `build_chart_spec` already resolves defaults and validates numeric Y.
- Do not write chart PNGs during live evaluation. Opening the chart window
  is a user action. (The existing chart window owns any export.)
- `after_execution` must keep working: Run must publish the frame and allow
  the user to open the graph after the run even when the dock was closed.
- Output variable: `var_graph_<id>`.

## 4. Core extraction

Create `core/shaping/graph.py`:

```python
"""Graph: a pass-through node (the chart lives in core/charts.py)."""

from __future__ import annotations

import polars as pl

from trigger_designer.core.shaping.common import as_lazy

DEFAULTS = {
    "graph_type": "line",
    "x_column": "",
    "y_column": "",
    "color_column": "",
    "aggregation": "",
    "title": "",
}


def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    return [as_lazy(frames[0])]
```

- Do not move `build_chart_spec` into this module; it is already Qt-free and
  shared with the chart view.
- `normalize` can validate `graph_type`/`aggregation` for generated code if
  desired, but the chart builder already tolerates unknown values. Keep the
  runner a pure pass-through.

## 5. UI

Custom layout, because the column choices depend on the chart type and the
"Open Graph" action is part of the dock:

1. `ConfigSection("Chart")`
   - `NoWheelComboBox` for `graph_type` with labels Line/Bar/Scatter.
   - `ColumnPicker` single-select for X and Y; Y should prefer numeric
     columns and may use a `filter` when the chart type requires numeric.
   - Optional color column picker (allow blank).
   - Aggregation combo: Default plus `none`/Count/Sum/Mean/Min/Max/Median.
   - `QLineEdit` for title.
2. `IconButton`/`TextButton` "Open Graph" in the section toolbar or
   `dock_actions`; disabled until there is data and a valid spec. Use
   tooltip + accessible name, no inline style.

- Every control writes through `set_setting`. The old `on_*_changed` methods
  become thin commit functions; do not keep duplicate model fields.
- On `after_change`, refresh the open chart window with the new spec (old
  `_schedule_window_refresh` behavior), debounced ~300 ms.
- `update_column_options` becomes a schema projection that preserves the
  saved value even if missing.
- Keep the current window class (`Report/chart_window.py`) and its tests.

## 6. Content and node

- `GraphContent(ShapingContent)`:
  - `SETTINGS`, `MODULE`, `OUTPUT_KINDS`, `INPUTS`, `FORM` unused because
    `create_layout` is custom.
  - add `runDataReady = Signal(object)` (the old content had it).
  - keep `build_spec()`, `open_graph_in_new_window()`,
    `after_execution(context)`, `_on_run_data_ready`, and the chart-window
    refresh logic.
  - `build_spec()` reads `self.frames[0]` (or `self.outputs[0]` after
    compute); do not reintroduce `incom_data`.
  - `workflow_ran_successfully` stays as UI state, not a setting.
- `TriggerNode_Graph(ShapingNode)` with output text `("Out",)`; remove
  `processInputs` and `get_code` (base handles them).
- Keep the node class name, enum, icon, title and registry entry.

## 7. Legacy loader

Old content used `serialize_content_state`, so the six keys are top-level:

```python
def _legacy_settings(self, data):
    return {
        "graph_type": str(data.get("graph_type") or "line"),
        "x_column": str(data.get("x_column") or ""),
        "y_column": str(data.get("y_column") or ""),
        "color_column": str(data.get("color_column") or ""),
        "aggregation": str(data.get("aggregation") or ""),
        "title": str(data.get("title") or ""),
    }

def deserialize(self, data, hashmap={}):  # noqa: B006
    if "settings" not in data and "graph_type" in data:
        data = dict(data)
        data["settings"] = self._legacy_settings(data)
    return super().deserialize(data, hashmap)
```

Test with `savedfiles/8. In-Graph.tds`.

## 8. Tests

`tests/unit/test_graph_core.py`:

- pass-through preserves frame, schema and order;
- lazy input -> lazy output;
- no chart settings still forwards;
- generated code defines `var_graph_<id>` and returns the same frame.

`tests/ui/test_graph_dock.py`:

- dock builds with a frame;
- controls update settings and the chart spec;
- missing saved column stays missing in the combo but does not invalidate the
  node;
- undo/redo restores every setting;
- Open Graph button enables only with a valid spec;
- post-run `after_execution` publishes the frame and the window opens;
- generated code == live frame.

Keep `tests/e2e/test_graph_run.py` and the saved Graph workflow green.

## 9. Steps

1. Add core pass-through + tests.
2. Rebuild content on `ShapingContent` with custom layout + loader.
3. Replace node with `ShapingNode`; remove old execution/codegen.
4. Keep `runDataReady` and all chart-window behavior.
5. Run focused graph tests + `test_graph_run` + all-node e2e.
6. Commit as `refactor: move Graph onto the shaping execution system`.

## 10. Acceptance

- [ ] Graph output equals its input for every graph type.
- [ ] The chart window opens after Run and after live configuration changes.
- [ ] No file is written just by editing the dock.
- [ ] Old saved graph settings load.
- [ ] Live == generated output.

## 11. Do not

- Do not make the graph transform or aggregate the data it forwards.
- Do not move `core/charts.py` into the node module.
- Do not drop `after_execution`/`runDataReady`; they are how Run hands the
  frame to the GUI.
