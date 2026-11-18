"""The editor's first window must not wait on the data libraries.

Polars costs about half a second to import, DuckDB and Arrow more. Nothing
needed to draw the window uses them, so they load on a background thread
after it is on screen. This runs in a fresh interpreter, because anything an
earlier test imported would hide a regression.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

HEAVY = ("polars", "duckdb", "pyarrow", "numpy", "sqlglot", "fastexcel")

PROBE = """
import json, sys
from qtpy.QtWidgets import QApplication
app = QApplication([])
import trigger_designer.main
from trigger_designer.qt.main_window import TriggerWindow
window = TriggerWindow(defer_startup_open=True)
window.show()
app.processEvents()
loaded = [name for name in %r if name in sys.modules]
sys.__stdout__.write("PROBE:" + json.dumps(loaded) + ":END")
sys.__stdout__.flush()
"""


def test_building_and_showing_the_main_window_does_not_import_the_data_libraries():
    env = {
        **os.environ,
        "QT_QPA_PLATFORM": "offscreen",
        "PYTHONPATH": str(REPO_ROOT / "src"),
        "PYTHONUTF8": "1",
    }
    done = subprocess.run(
        [sys.executable, "-c", PROBE % (HEAVY,)],
        capture_output=True,
        text=True,
        env=env,
        cwd=REPO_ROOT,
        timeout=120,
        check=False,
    )
    marker = done.stdout.rfind("PROBE:")
    assert marker >= 0, (
        f"probe printed nothing:\n{done.stdout[-500:]}\n{done.stderr[-800:]}"
    )
    loaded = json.loads(done.stdout[marker + len("PROBE:") :].split(":END")[0])
    assert loaded == [], (
        f"building the main window pulled in {loaded}; make the code that "
        "loads it at import or construction time wait for first use instead "
        "(trigger_designer.core.lazy_import)"
    )
