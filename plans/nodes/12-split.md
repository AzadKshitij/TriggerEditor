# Split - modernization plan

Status: implemented.
Implementation order: 4 of 18 (Tier 0, row partition, two outputs).
Read first: `plans/nodes/README.md`.

## 1. Current implementation

- File: `src/trigger_designer/qt/widgets/nodes/Preparation/split.py`.
- Content: `SplitContent` (line 34).
- Node: `TriggerNode_Split` (line 446).
- Inputs: one. Outputs: two - estimation and validation
  (`output_text=["E", "V"]`, `outputs=[3, 3]`).
- Settings today: `estimation_percent` (default 70), `random_seed` (42),
  `is_random` (True).
- Old execution (`TriggerNode_Split.processInputs`):
  - adds `__split_idx` with `with_row_index`;
  - if random, sorts by `__split_idx.shuffle(seed=random_seed)`;
  - `threshold = estimation_percent / 100.0`;
  - estimation = rows with `idx < idx.max() * threshold`;
  - validation = rows with `idx >= idx.max() * threshold`;
  - drops `__split_idx`.
- Old UI: mode selector, estimation percent spin, seed spin, validation
  label.
- Old codegen: emits the same row-index/shuffle/filter logic.
- Existing tests: no dedicated unit test; saved workflow
  `savedfiles/11. Split.tds` and goldens.
- Saved workflow: `savedfiles/11. Split.tds`.

## 2. Target

- Core: `src/trigger_designer/core/shaping/split.py`.
- Content: `SplitContent(ShapingContent)`.
- Node: `TriggerNode_Split(ShapingNode)`.
- Settings: `estimation_percent`, `random_seed`, `is_random`.
- Output kinds: `("estimation", "validation")`.
- `INPUTS = 1`; `HISTORY = "Split"`; `SUMMARY = "train/validation split"`.

### Settings schema

```python
DEFAULTS = {
    "estimation_percent": 70,
    "random_seed": 42,
    "is_random": True,
}
```

## 3. Behavior contract

- Preserve the current split algorithm exactly. Do not switch to
  `DataFrame.sample` or sklearn; the old split uses a shuffled index and a
  threshold, and the saved golden pins it.
- `estimation_percent` is an integer in `1..99` (the old spin box allowed a
  range; verify and keep the same). Treat out-of-range as `TD-SHAPE-004`.
- Random mode uses `pl.col(idx).shuffle(seed=random_seed)`. Sequential mode
  keeps input order.
- The two outputs partition all rows and preserve the shuffled/index order for
  random mode.
- Empty input -> both outputs are empty; do not fail.
- `estimation_percent=100` or `0` is not allowed by the UI; the core should
  clamp or raise. Prefer `TD-SHAPE-004` for invalid values, but keep the UI
  range 1-99.
- Return lazy frames.
- Output variable names: keep `var_estimation_<id>` and
  `var_validation_<id>`; downstream saved code may reference them.

## 4. Core extraction

Create `core/shaping/split.py`:

```python
DEFAULTS = {"estimation_percent": 70, "random_seed": 42, "is_random": True}
SPLIT_COL = "__split_idx"


def run_node(frames: list, settings: dict) -> list[pl.LazyFrame]:
    frame = as_lazy(frames[0])
    percent = int((settings or {}).get("estimation_percent", 70))
    if not 1 <= percent <= 99:
        raise ShapingError("TD-SHAPE-004", "Estimation percent must be between 1 and 99")
    indexed = frame.with_row_index(SPLIT_COL)
    if bool((settings or {}).get("is_random", True)):
        seed = int((settings or {}).get("random_seed", 42))
        indexed = indexed.sort(pl.col(SPLIT_COL).shuffle(seed=seed))
    threshold = percent / 100.0
    estimation = indexed.filter(
        pl.col(SPLIT_COL) < pl.col(SPLIT_COL).max() * threshold
    ).drop(SPLIT_COL)
    validation = indexed.filter(
        pl.col(SPLIT_COL) >= pl.col(SPLIT_COL).max() * threshold
    ).drop(SPLIT_COL)
    return [estimation, validation]
```

- Keep the helper method naming (`estimation`/`validation`) in output kinds.
- Do not change the threshold formula to row count; preserve the old
  index-based formula even though it is unusual.

## 5. UI

```python
FORM = (
    FormSection(
        "Split",
        (
            Field(
                "is_random",
                "Method",
                "combo",
                options=((True, "Random"), (False, "Sequential")),
            ),
            Field("estimation_percent", "Estimation %", "int", minimum=1, maximum=99),
            Field(
                "random_seed",
                "Random seed",
                "int",
                minimum=0,
                maximum=2_147_483_647,
                show_if=lambda s: s.get("is_random"),
            ),
        ),
        info="Estimation rows first; the rest go to Validation.",
    ),
)
```

`is_random` stays a **bool** in settings. The `combo` stores the bool as the
item data; do not store `"random"`/`"sequential"` strings in this key.

- The seed field must hide/disable in sequential mode (`show_if`).
- Show the split count/summary in `dock_context` if easy; do not add a
  second output table.

## 6. Content and node

- Delete `create_layout` custom widgets, `_on_estimation_changed`,
  `_on_seed_changed`, `_on_mode_changed`, `_store_history`,
  `history_stamp_callback`, old `get_code`/`serialize`/`deserialize`.
- Set `self.output_variables = [f"var_estimation_{self.id}",
  f"var_validation_{self.id}"]`.
- Keep the node class name, enum, icon, title and registry entry.
- No upstream rename following is needed.

## 7. Legacy loader

Old content serialized the three keys at the top level:

```python
def _legacy_settings(self, data):
    percent = int(data.get("estimation_percent", 70))
    return {
        "estimation_percent": max(1, min(99, percent)),
        "random_seed": int(data.get("random_seed", 42)),
        "is_random": bool(data.get("is_random", True)),
    }

def deserialize(self, data, hashmap={}):  # noqa: B006
    if "settings" not in data and "estimation_percent" in data:
        data = dict(data)
        data["settings"] = self._legacy_settings(data)
    return super().deserialize(data, hashmap)
```

Test with `savedfiles/11. Split.tds`.

## 8. Tests

`tests/unit/test_split_core.py`:

- sequential 70/30 split, exact row counts;
- random split is deterministic for a fixed seed;
- changing the seed changes the order;
- both outputs partition the input (no rows lost/duplicated);
- empty input -> two empty frames;
- percent bounds (1, 99, 0 -> error, 100 -> error);
- lazy input stays lazy.

`tests/ui/test_split_dock.py`:

- dock builds with method/percent/seed;
- random/sequential toggle updates output;
- seed visibility follows the mode;
- undo/redo restores settings;
- generated code equals live for both outputs;
- serialization round-trip.

Run the Split golden and the all-node e2e.

## 9. Steps

1. Add core + tests.
2. Replace content with form + loader.
3. Replace node with `ShapingNode` and set output variables.
4. Remove old widget code and imports.
5. Run focused tests, Split golden, all-node e2e.
6. Commit as `refactor: move Split onto the shaping execution system`.

## 10. Acceptance

- [x] The split is deterministic for a fixed seed and matches the old golden.
- [x] Both outputs are lazy and partition the input.
- [x] Percent bounds are enforced.
- [x] Checked-in sample workflows were migrated to the new `settings` schema;
      no legacy loader is kept (project decision: no backward compatibility).
- [x] Live == generated output.

## 11. Do not

- Do not switch to a random sample with a different row-count formula.
- Do not store `is_random` as a string.
- Do not expose the internal `__split_idx` column.
