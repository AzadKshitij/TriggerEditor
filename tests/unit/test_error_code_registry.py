"""Every ``TD-XXX-nnn`` code the source mentions is registered.

An unregistered code reaches the error translator with no title or fix text, so
the user sees a bare code. This scan catches a code added in a module but not in
``core/errors/catalogue.py`` (all codes) or ``core/shaping/common.py::ERROR_CODES``
(``TD-SHAPE-*``).
"""

from __future__ import annotations

import re
from pathlib import Path

import trigger_designer
from trigger_designer.core.errors.catalogue import CATALOGUE
from trigger_designer.core.shaping.common import ERROR_CODES

SRC = Path(trigger_designer.__file__).parent
CODE = re.compile(r"""["'](TD-[A-Z]+-\d+)["']""")


def _literals() -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for path in SRC.rglob("*.py"):
        for code in CODE.findall(path.read_text(encoding="utf-8")):
            found.setdefault(code, set()).add(path.relative_to(SRC).as_posix())
    return found


def test_scan_finds_codes() -> None:
    found = _literals()
    assert "TD-SHAPE-112" in found and "TD-AUDIT-102" in found


def test_every_code_literal_is_in_the_catalogue() -> None:
    missing = {c: sorted(f) for c, f in _literals().items() if c not in CATALOGUE}
    assert not missing, f"register in core/errors/catalogue.py: {missing}"


def test_every_shape_code_literal_is_in_error_codes() -> None:
    missing = {
        c: sorted(f)
        for c, f in _literals().items()
        if c.startswith("TD-SHAPE-") and c not in ERROR_CODES
    }
    assert not missing, f"register in core/shaping/common.py ERROR_CODES: {missing}"


def test_shaping_error_codes_have_catalogue_entries() -> None:
    assert not [c for c in ERROR_CODES if c not in CATALOGUE]
