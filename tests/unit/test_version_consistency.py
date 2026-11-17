"""The version is written in two places and they must not drift apart.

``core/constants.py`` (what the program prints and records in run records) and
``pyproject.toml`` (what the wheel and the lock file carry) once disagreed after
a release bump. The program's text uses the dashed form (``0.1.0-alpha.2``) and
the package metadata the PEP 440 one (``0.1.0a2``); both name the same version.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from packaging.version import Version

from trigger_designer.core.constants import VERSION

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


def test_pyproject_and_the_program_name_the_same_version():
    meta = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert Version(meta["project"]["version"]) == Version(VERSION)


def test_the_lock_file_carries_the_same_version():
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    project = next(p for p in lock["package"] if p["name"] == "triggerdesigner")
    assert Version(project["version"]) == Version(VERSION)
