# 06 — Dependencies (`pyproject.toml`)

Import counts = files under `src/` with a real import line. Requires-python is >=3.13.12. After each edit run `uv lock`, a smoke import (`uv run python -c "import trigger_designer.main"`), the full pytest, and finally rebuild the PyInstaller bundle (`trigger.spec`, check hiddenimports).

## Batch A — zero imports in src/ (risk low)

| Dep | Imports | Action | Note |
|---|---|---|---|
| `click==8.5.0` | 0 | remove | CLI plan (docs/plan/08) unbuilt; re-add when it lands |
| `colorama==0.4.6` | 0 | remove | transitive via loguru on Windows |
| `packaging==26.3` | 0 | remove | still arrives transitively |
| `python-dateutil==2.9.0.post0` | 0 | remove | still arrives via matplotlib (lock lines ~303/424) |
| `tzdata==2026.4` | 0 | remove **after** confirming no `zoneinfo`/polars time-zone use (grep for `zoneinfo`/`time_zone` found nothing in `src/`) and that the PyInstaller bundle on Windows still resolves time zones | polars/pandas pull it in transitively; low-medium risk on Windows bundle |
| `openpyxl>=3.1.0` | 0 | move to dev group | only `tests/support/input_fixtures.py` and `tests/unit/test_errors_translator.py` use it; `fastexcel` (3 imports) reads |
| `pyqt6-qt6==6.8.1`, `pyqt6-sip==13.9.1` | 0 | drop the pins | `pyqt6==6.8.0` pulls both; `uv.lock` already gives reproducibility. Keep if the pins exist for a documented reason |
| `numpy==2.5.3` | 1 (`Report/chart_view.py`) | drop the direct pin only if you accept the transitive pull via matplotlib/polars | keep the import; low value, optional |

## Batch B — replace with stdlib/platform (risk very low to low-medium)

1. `stdlib:` `typing-extensions`: single import `qt/main_window.py:4` (`from typing_extensions import override`) → `from typing import override` (stdlib since 3.12). Drop the pin.
2. `native:` `pillow`: single use `qt/resource_manager.py:6` `from PIL import Image, ImageQt` at ~182-192 → `QImage(path)`/`QPixmap(path)`. Drop the direct pin (matplotlib keeps it in the lock). Verify no unusual image formats are loaded. Combine with 01 Batch D (the `pil` branch is unreachable anyway).

## Not cut (kept deliberately)

- `psutil`: 1 use (`ExecutionCheck/executor.py:24`, memory readout, line ~158). No stdlib equivalent on Windows. Keep unless the readout is cut.
- `orjson` (4 imports, all in qt/): stdlib `json` swap is possible but is churn for no concept removed. Deferred.
- `matplotlib` (2 imports, chart node only): keep unless the chart Report node itself is cut. Product decision, not an over-engineering cut.
- `pyarrow` (0 direct imports): required by DuckDB registering Polars frames (see pyproject comment). Keep.
- `qtpy` (119 import lines) and `nodeeditor-qtpy`: load-bearing. Not a cut.
- `polars`, `duckdb`, `sqlglot`, `fastexcel`, `loguru`: real use.

## Follow-ups

- `xlsxwriter` is referenced in `core/errors/catalogue.py:356` and `translator.py:813` and recorded as chosen in project memory, but is not in dependencies. Either add it when the workpaper export lands or remove those catalogue entries until then. Product decision.
- After 02 Batch B removes `check_output_pandas.py`, re-check whether dev-group `pandas` and `pandas-stubs` are still needed.
