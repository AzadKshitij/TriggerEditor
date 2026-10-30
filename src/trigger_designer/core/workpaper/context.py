"""The run record the workpaper reads while a workflow is running.

Plan 02's ``RunRecorder`` registers a provider with
``trigger_designer.core.audit.recorder.set_run_record_provider``; this module
reads that one registry (no second one) and never raises.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from typing import Any


def current_run_record() -> Mapping[str, Any] | None:
    """The in-flight record as a plain dict, or ``None`` (no recorder / failure)."""
    try:
        from trigger_designer.core.audit.recorder import get_run_record_provider

        provider = get_run_record_provider()
        if provider is None:
            return None
        record = provider()
        if dataclasses.is_dataclass(record) and not isinstance(record, type):
            record = dataclasses.asdict(record)
        return record if isinstance(record, Mapping) else None
    except Exception:  # noqa: BLE001 - a recording problem must never break the workpaper
        return None


def set_run_record_provider(provider) -> None:
    """Install ``provider`` in the shared registry (tests and headless callers)."""
    from trigger_designer.core.audit.recorder import set_run_record_provider as _set

    _set(provider)
