"""The small object every command receives (plan 08 3.2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class CliContext:
    state: Path
    emitter: Any = None
    extra: dict = field(default_factory=dict)
