"""Audit package: run records (plan 02) and audit tests (plan 04).

Run records
    ``RunRecorder`` / ``RunStore`` / ``verify_store`` / ``compare_runs`` /
    ``render_html`` ... are re-exported lazily (``__getattr__``), so importing
    this package costs nothing and generated code may import a single
    submodule (``trigger_designer.core.audit.common``) without pulling in
    polars, the store or the recorder.

Audit tests
    Each test is one pure function ``run_<name>(frame, params) -> AuditResult``
    in its own module; ``common`` holds the shared building blocks and
    ``test_summary`` the record other features read.

Nothing here may import Qt (a unit test fails if it does).
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

_EXPORTS: dict[str, str] = {
    # schema
    "RUN_RECORD_SCHEMA_VERSION": "schema",
    "HASH_ALGO": "schema",
    "FileFingerprint": "schema",
    "NodeRunRecord": "schema",
    "RunRecord": "schema",
    "validate_record_dict": "schema",
    # canonical
    "GENESIS_HASH": "canonical",
    "canonical_json": "canonical",
    "sha256_hex": "canonical",
    "compute_record_hash": "canonical",
    "utc_now_iso": "canonical",
    # fingerprint / counting
    "FingerprintCache": "fingerprint",
    "fingerprint_file": "fingerprint",
    "sha256_stream": "fingerprint",
    "count_rows_in_file": "fingerprint",
    "decide_row_count_mode": "counting",
    "count_frame": "counting",
    "schema_of": "counting",
    "CountError": "counting",
    # store
    "RunStore": "store",
    "RunHeader": "store",
    "VerifyProblem": "store",
    "VerifyReport": "store",
    "RunAlreadySealed": "store",
    "StoreLockTimeout": "store",
    "resolve_store_dir": "store",
    "verify_store": "store",
    "verify_record_file": "store",
    # recorder
    "AuditOptions": "recorder",
    "NodeSpec": "recorder",
    "EdgeRef": "recorder",
    "RunRecorder": "recorder",
    "set_run_record_provider": "recorder",
    "get_run_record_provider": "recorder",
    "extract_seed": "recorder",
    "sanitize": "recorder",
    # compare / view / export / errors
    "DiffItem": "compare",
    "RunDiff": "compare",
    "InputCheck": "compare",
    "compare_runs": "compare",
    "check_inputs": "compare",
    "format_duration": "view",
    "run_summary_rows": "view",
    "node_table_rows": "view",
    "test_table_rows": "view",
    "format_test_result": "view",
    "render_html": "export",
    "export_json": "export",
    "error_to_dict": "errors_adapter",
    "exception_to_dict": "errors_adapter",
}

if TYPE_CHECKING:  # pragma: no cover - static analysis only
    from trigger_designer.core.audit.canonical import (  # noqa: F401
        GENESIS_HASH,
        canonical_json,
    )
    from trigger_designer.core.audit.recorder import (  # noqa: F401
        AuditOptions,
        RunRecorder,
    )
    from trigger_designer.core.audit.schema import RunRecord  # noqa: F401


def __getattr__(name: str):
    module = _EXPORTS.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(importlib.import_module(f"{__name__}.{module}"), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_EXPORTS))
