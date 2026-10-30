"""``core.audit`` stays import-light and Qt-free (plan 02 3.8 "Lazy package init")."""

from __future__ import annotations

import subprocess
import sys

PKG = "trigger_designer.core.audit"


def _run(code: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-I", "-c", code],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_import_leaves_submodules_polars_and_qt_out():
    proc = _run(
        f"import sys, {PKG};"
        f"bad=[m for m in ('{PKG}.recorder','{PKG}.store','{PKG}.schema','polars') if m in sys.modules];"
        "qt=[m for m in sys.modules if m.startswith(('qtpy','PyQt','PySide'))];"
        "assert not bad and not qt, (bad, qt)"
    )
    assert proc.returncode == 0, proc.stderr


def test_recorder_access_imports_it_without_qt_or_executor():
    proc = _run(
        f"import sys, {PKG} as a; a.RunRecorder;"
        f"assert '{PKG}.recorder' in sys.modules;"
        "qt=[m for m in sys.modules if m.startswith(('qtpy','PyQt','PySide'))];"
        "ex=[m for m in sys.modules if 'ExecutionCheck' in m];"
        "assert not qt and not ex, (qt, ex)"
    )
    assert proc.returncode == 0, proc.stderr


def test_unknown_attribute_raises_attribute_error():
    proc = _run(
        f"import {PKG} as a\n"
        "try:\n    a.nope\nexcept AttributeError:\n    pass\nelse:\n    raise SystemExit(1)"
    )
    assert proc.returncode == 0, proc.stderr


def test_existing_submodule_imports_still_work():
    proc = _run(
        f"from {PKG}.common import BASE_SUMMARY; from {PKG}.test_summary import TestSummary;"
        f"from {PKG} import store; assert store.RunStore"
    )
    assert proc.returncode == 0, proc.stderr


def test_every_lazy_export_resolves():
    proc = _run(
        f"import {PKG} as a\n"
        "missing=[n for n in a._EXPORTS if getattr(a, n, None) is None]\n"
        "assert not missing, missing"
    )
    assert proc.returncode == 0, proc.stderr


def test_every_core_module_is_qt_free_and_executor_free():
    modules = [
        "schema",
        "canonical",
        "fingerprint",
        "counting",
        "store",
        "recorder",
        "compare",
        "view",
        "export",
        "errors_adapter",
    ]
    imports = ";".join(f"import {PKG}.{name}" for name in modules)
    proc = _run(
        f"import sys;{imports};"
        "qt=[m for m in sys.modules if m.startswith(('qtpy','PyQt','PySide'))];"
        "ex=[m for m in sys.modules if 'ExecutionCheck' in m or '.qt.' in m];"
        "assert not qt and not ex, (qt, ex)"
    )
    assert proc.returncode == 0, proc.stderr
