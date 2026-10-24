# Append - modernization plan

Status: not started.
Implementation order: 14 of 18 (Tier 4, two inputs).
Read first: `plans/nodes/README.md`.

## 1. Current implementation

- File: `src/trigger_designer/qt/widgets/nodes/Join/Append.py`.
- Content: `AppendContent` (line 36).
- Node: `TriggerNode_Append` (line 186).
- Inputs: two (`[1, 1]`). Outputs: one.
- Settings today: `how` (default `"diagonal_relaxed"`).
- Old execution: `AppendContent.concat` uses
  `pl.concat([left, right], how=self.how)`; for `vertical`, it first checks
  exact schema equality and returns a readable error.
- Old UI: one combo for the concat method and a count summary.
- Old codegen: `pl.concat` with the configured method.
- Existing tests: none dedicated; all-node e2e only.
- Saved workflow: all-node workflow.

## 2. Target

- Core: `src/trigger_designer/core/shaping/append.py`.
- Content: `AppendContent(ShapingContent)`.
- Node: `TriggerNode_Append(ShapingNode)`.
- Settings: `how`.
- Output kind: `("append",)`.
- `INPUTS = 2`; `HISTORY = "Append"`;
  `SUMMARY = "stack two inputs"`.

### Settings schema

```python
DEFAULTS = {
    "how": "diagonal_relaxed",  # vertical | horizontal | diagonal | diagonal_relaxed
}
```

## 3. Behavior contract

- Both inputs are required. A missing input is the base ShapingNode error
  (`TD-SHAPE-005`), not a custom tooltip.
- `how` must be one of `vertical`, `horizontal`, `diagonal`,
  `diagonal_relaxed`; unknown -> `TD-SHAPE-004`.
- `vertical` requires identical schemas (names, order and dtypes). If they
  differ, raise `TD-SHAPE-004` with the old message shape:
  `schemas differ (left-only: [...], right-only: [...]). Try 'diagonal_relaxed'.`
- Other modes use Polars `pl.concat` directly. Do not reimplement column
  union/missing-null logic.
- Preserve lazy/eager at the boundary by returning a LazyFrame. The old
  `_as_lazy` helper converts both inputs.
- Do not silently coerce schemas for `vertical`.
- Output variable: `var_append_<id>`.

## 4. Core extraction

Create `core/shaping/append.py`:

```python
DEFAULTS = {"how": "diagonal_relaxed"}
HOW_VALUES = ("vertical", "horizontal", "diagonal", "diagonal_relaxed")


def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    left, right = as_lazy(frames[0]), as_lazy(frames[1])
    how = str((settings or {}).get("how") or "diagonal_relaxed")
    if how not in HOW_VALUES:
        raise ShapingError("TD-SHAPE-004", f"Unknown Append method '{how}'")
    if how == "vertical":
        l_schema = schema_of(left)
        r_schema = schema_of(right)
        if l_schema != r_schema:
            l_only = [name for name in l_schema if name not in r_schema]
            r_only = [name for name in r_schema if name not in l_schema]
            raise ShapingError(
                "TD-SHAPE-004",
                f"schemas differ (left-only: {l_only}, right-only: {r_only}). "
                "Try 'diagonal_relaxed'.",
            )
    return [pl.concat([left, right], how=how)]
```

- Use `schema_of` so a LazyFrame does not warn on `.schema` access.
- Do not collect.

## 5. UI

```python
FORM = (
    FormSection(
        "Append",
        (
            Field(
                "how",
                "Method",
                "combo",
                options=(
                    ("diagonal_relaxed", "Diagonal (relaxed)"),
                    ("vertical", "Vertical (same columns)"),
                    ("horizontal", "Horizontal (side by side)"),
                    ("diagonal", "Diagonal (strict)"),
                ),
            ),
        ),
        info="Vertical requires identical schemas.",
    ),
)
```

- Keep the old default `diagonal_relaxed` first.
- The old count summary can be a `dock_context` chip based on the two input
  frames; no extra setting.
- No add/remove controls; the two inputs are fixed sockets.

## 6. Content and node

- Delete `concat`, `schema_mismatch`, `_on_how_changed`,
  `_refresh_append_counts`, old `get_code`/`serialize`/`deserialize`.
- `AppendContent` uses the standard form; `get_code` inherited.
- Set `self.output_variables = [f"var_append_{self.id}"]`.
- Keep node class/title/icon/enum/registry.
- No upstream rename following is needed (Append does not rename).

## 7. Legacy loader

Old content serialized `how` at the top level:

```python
def _legacy_settings(self, data):
    how = str(data.get("how") or "diagonal_relaxed")
    if how not in core.HOW_VALUES:
        how = "diagonal_relaxed"
    return {"how": how}

def deserialize(self, data, hashmap={}):  # noqa: B006
    if "settings" not in data and "how" in data:
        data = dict(data)
        data["settings"] = self._legacy_settings(data)
    return super().deserialize(data, hashmap)
```

## 8. Tests

`tests/unit/test_append_core.py`:

- each `how` mode on compatible frames;
- vertical identical schema succeeds;
- vertical mismatch raises `TD-SHAPE-004` with left/right-only detail;
- unknown `how` raises;
- lazy + eager inputs;
- output is lazy;
- empty frames.

`tests/ui/test_append_dock.py`:

- combo edits settings and output;
- undo/redo restores method;
- generated code equals live for all methods;
- serialization round-trip.

Run the all-node e2e.

## 9. Steps

1. Add core + tests.
2. Replace content with form + loader.
3. Replace node with `ShapingNode` with `INPUTS=2`.
4. Remove old widget/codegen.
5. Run focused tests + all-node e2e.
6. Commit as `refactor: move Append onto the shaping execution system`.

## 10. Acceptance

- [ ] All four concat methods work.
- [ ] Vertical mismatch has a readable error.
- [ ] Both inputs are required.
- [ ] Old saved `how` loads.
- [ ] Live == generated output.

## 11. Do not

- Do not use `pl.concat(..., how="vertical_relaxed")`; it is not a valid
  Polars mode and changes semantics.
- Do not coerce vertical schemas.
- Do not make the method a per-input setting.
