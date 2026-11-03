# 06 — Dependencies (`pyproject.toml`)

**Status:** most of the original Batch A is already applied in the staged `pyproject.toml`: `click`, `colorama`, `packaging`, `python-dateutil`, `tzdata`, the `pyqt6-*` pins and `typing-extensions` are gone, and the app is now PySide6 on Python 3.14. The table below is what is LEFT; re-read `pyproject.toml` first, versions drift. Import counts = files under `src/` with a real import line. After each edit run `uv lock`, a smoke import (`uv run python -c "import trigger_designer.main"`), the full pytest, and finally rebuild the PyInstaller bundle (`trigger.spec`, check hiddenimports).

## Remaining cuts

| Dep | Imports | Action | Note |
|---|---|---|---|
| `openpyxl>=3.1.5` | 0 in `src/` | move to dev group | only `tests/support/input_fixtures.py` and `tests/unit/test_errors_translator.py` use it; `fastexcel` reads. Check `trigger.spec` hiddenimports |
| `shiboken6==6.12.0` | 0 in `src/` | drop the direct pin | `PySide6-Essentials` pulls its own matching shiboken6. Keep if pyproject history documents a reason |
| `pillow==13.0.0` | 1 (`resource_manager.py`: `PIL`, `ImageQt`) | replace with `QImage(path)`/`QPixmap(path)`, drop the direct pin | matplotlib keeps pillow in the lock. Do together with 01 Batch D (the `pil` branch is unreachable). Verify no unusual image formats are loaded |
| `numpy==2.5.4` | 1 (`Report/chart_view.py`) | optional: drop the direct pin | arrives via polars[pyarrow]/matplotlib; keep the import. Low value |

## Do NOT remove

- `tzdata`: keep it (re-add if it was dropped). Polars needs it for time zones on Windows, and a grep for explicit `zoneinfo`/`time_zone` use in `src/` does not show that need. To remove it anyway, first test the frozen Windows bundle with a time-zone-aware column.

## Not cut (kept deliberately)

- `psutil`: 1 use (`ExecutionCheck/executor.py:24`, memory readout, line ~158). No stdlib equivalent on Windows. Keep unless the readout is cut.
- `orjson` (4 imports, all in qt/): stdlib `json` swap is possible but is churn for no concept removed. Deferred.
- `pyqtgraph` (chart renderer/view/window): live, keep.
- `matplotlib` (2 imports, chart node only): keep unless the chart Report node itself is cut. Product decision, not an over-engineering cut.
- `pyarrow` (0 direct imports): required by DuckDB registering Polars frames (see pyproject comment). Keep.
- `qtpy` (119 import lines) and `nodeeditor-qtpy`: load-bearing. Not a cut.
- `polars`, `duckdb`, `sqlglot`, `fastexcel`, `loguru`: real use.

## Follow-ups

- `xlsxwriter` is referenced in `core/errors/catalogue.py:356` and `translator.py:813` and recorded as chosen in project memory, but is not in dependencies. Either add it when the workpaper export lands or remove those catalogue entries until then. Product decision.
- pandas is already absent from the dev group (see the pyproject comment); nothing to re-check after 02 Batch B.
