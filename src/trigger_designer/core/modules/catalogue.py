"""The list of modules the app offers, read from a file on this machine.

``load_catalogue`` never raises for a bad file: a missing or broken file gives an
empty catalogue with a problem, and a bad entry is skipped with a problem, so the
app still starts. Nothing here touches the network.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from trigger_designer.core.modules.errors import ModuleError
from trigger_designer.core.modules.manifest import ModuleManifest, parse_manifest

#: Overrides the bundled catalogue (tests, or a private build). Empty means unset.
ENV_CATALOGUE = "TRIGGER_DESIGNER_MODULE_CATALOGUE"
SCHEMA_VERSION = 1
BUNDLED_SOURCE = "bundled"


@dataclass(frozen=True)
class Catalogue:
    modules: tuple[ModuleManifest, ...]
    problems: tuple[str, ...]
    #: The file that was read, or ``"bundled"``.
    source: str


def bundled_catalogue_path() -> Path:
    """``trigger_designer/resources/modules/catalogue.json``, found next to the package.

    The same relative layout holds inside a PyInstaller bundle, where the package
    sits under ``_MEIPASS``.
    """
    return Path(__file__).parents[2] / "resources" / "modules" / "catalogue.json"


def load_catalogue(path: Path | None = None) -> Catalogue:
    """Read ``{"schema": 1, "modules": [...]}``.

    Precedence: ``path``, then the ``TRIGGER_DESIGNER_MODULE_CATALOGUE`` environment
    variable, then the bundled file.
    """
    override = os.environ.get(ENV_CATALOGUE, "").strip()
    if path is not None:
        target, source = Path(path), str(path)
    elif override:
        target, source = Path(override), override
    else:
        target, source = bundled_catalogue_path(), BUNDLED_SOURCE
    try:
        raw = target.read_bytes()
    except FileNotFoundError:
        return _empty(source, f"The module catalogue was not found at {target}.")
    except OSError as exc:
        return _empty(
            source,
            f"The module catalogue at {target} cannot be read ({exc.strerror or exc}).",
        )
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except ValueError:  # includes UnicodeDecodeError
        return _empty(source, f"The module catalogue at {target} is not valid JSON.")
    if (
        not isinstance(data, dict)
        or type(data.get("schema")) is not int
        or data["schema"] != SCHEMA_VERSION
    ):
        return _empty(
            source,
            f"The module catalogue at {target} has an unsupported schema "
            f"(expected {SCHEMA_VERSION}).",
        )
    entries = data.get("modules")
    if not isinstance(entries, list):
        return _empty(source, "The module catalogue must contain a 'modules' list.")

    modules: list[ModuleManifest] = []
    problems: list[str] = []
    seen: set[str] = set()
    for number, entry in enumerate(entries, start=1):
        try:
            manifest = parse_manifest(entry)
        except ModuleError as exc:
            problems.append(f"Entry {number} was skipped: {exc.message}")
            continue
        if manifest.id in seen:
            problems.append(
                f"Entry {number} was skipped: the id '{manifest.id}' is already listed."
            )
            continue
        seen.add(manifest.id)
        modules.append(manifest)
    return Catalogue(tuple(modules), tuple(problems), source)


def _empty(source: str, problem: str) -> Catalogue:
    return Catalogue((), (problem,), source)
