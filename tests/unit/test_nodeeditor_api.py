#!/usr/bin/env python3
"""The installed nodeeditor exposes the API this app calls.

The canvas is a separate distribution (``nodeeditor-qtpy`` on PyPI, import
package ``nodeeditor``). When the installed copy is older than the code that
calls it, the missing attributes raise deep inside Qt and the errors get
swallowed: edge geometry stops updating, the canvas silently keeps its own
detail rules, and the symptom surfaces as a handful of unrelated UI test
failures instead of one obvious mismatch.

So pin the expectation: the attributes below are the ones
``performance_scene.py``, ``render_settings.py`` and ``node_base.py`` use, and
this test fails loudly when the installed package does not have them.
"""

from __future__ import annotations

import pytest

#: ``(module, class, attribute) -> what the app uses it for``.
REQUIRED_API = {
    (
        "nodeeditor.node_graphics_edge",
        "QDMGraphicsEdge",
        "setPositions",
    ): "edge geometry on node move and load",
    (
        "nodeeditor.node_graphics_edge",
        "QDMGraphicsEdge",
        "setSource",
    ): "edge geometry fallback",
    (
        "nodeeditor.node_graphics_edge",
        "QDMGraphicsEdge",
        "setDestination",
    ): "edge geometry fallback",
    (
        "nodeeditor.node_graphics_scene",
        "QDMGraphicsScene",
        "set_detail_policy",
    ): "per-element level-of-detail policy",
    (
        "nodeeditor.node_graphics_scene",
        "QDMGraphicsScene",
        "detail_enabled",
    ): "level-of-detail answers per element",
    (
        "nodeeditor.node_graphics_scene",
        "QDMGraphicsScene",
        "MIN_GRID_SPACING_PX",
    ): "grid level culling",
    (
        "nodeeditor.node_graphics_node",
        "QDMGraphicsNode",
        "setDetailState",
    ): "per-element detail state on a node",
    (
        "nodeeditor.node_graphics_node",
        "QDMGraphicsNode",
        "syncDetailVisibility",
    ): "applying the detail state to a node",
    (
        "nodeeditor.node_graph",
        None,
        "topological_order",
    ): "dependency ordering for load, restore, and Run",
    (
        "nodeeditor.node_graph",
        None,
        "ancestors",
    ): "error-context upstream traversal",
    (
        "nodeeditor.node_graph",
        None,
        "descendants",
    ): "cycle validation and affected-node closure",
    (
        "nodeeditor.node_graph",
        None,
        "cycles",
    ): "formatting a cycle for load and Run",
    (
        "nodeeditor",
        None,
        "GraphCycleError",
    ): "catching a cyclic workflow without failing the load",
}


def _resolve(module_name: str, class_name: str | None, attribute: str):
    """Return the attribute, or ``None`` when the module or class lacks it."""
    try:
        module = __import__(module_name, fromlist=["__name__"])
    except ImportError:
        return None
    if class_name is None:
        return getattr(module, attribute, None)
    owner = getattr(module, class_name, None)
    if owner is None:
        return None
    return getattr(owner, attribute, None)


@pytest.mark.parametrize(
    ("module_name", "class_name", "attribute"),
    sorted(REQUIRED_API),
    ids=[
        f"{cls or module_name}.{attr}"
        for module_name, cls, attr in sorted(REQUIRED_API)
    ],
)
def test_installed_nodeeditor_has_required_api(
    module_name: str, class_name: str, attribute: str
) -> None:
    assert _resolve(module_name, class_name, attribute) is not None, (
        f"the installed nodeeditor has no {class_name}.{attribute} "
        f"(needed for {REQUIRED_API[(module_name, class_name, attribute)]}). "
        f"Check the nodeeditor-qtpy pin in pyproject.toml and run `uv sync`."
    )


def test_the_scene_carries_a_detail_lod_threshold() -> None:
    """``detail_lod_threshold`` is per instance, so check a real scene."""
    from nodeeditor.node_graphics_scene import QDMGraphicsScene

    scene = QDMGraphicsScene(scene=None)
    assert isinstance(scene.detail_lod_threshold, float)


def test_installed_nodeeditor_matches_the_pinned_version() -> None:
    """The installed distribution is the one the lock pins.

    Read the distribution metadata, not ``nodeeditor.__version__``: 0.8.2's
    PySide6 branch does ``from PySide6 import __version__``, which shadows the
    package's own version with the binding's (the PyQt6 branch assigns
    ``PYQT_VERSION_STR`` to a different name and keeps it intact). Reported
    upstream; the pin is what this test is about.
    """
    import tomllib
    from importlib import metadata
    from pathlib import Path

    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    with pyproject.open("rb") as handle:
        dependencies = tomllib.load(handle)["project"]["dependencies"]

    requirement = next(
        dep for dep in dependencies if dep.lower().startswith("nodeeditor-qtpy==")
    )
    expected = requirement.split("==", 1)[1]
    installed = metadata.version("nodeeditor-qtpy")

    assert installed == expected, (
        f"nodeeditor-qtpy {installed} is installed, but pyproject.toml "
        f"pins {expected}. Run `uv sync` to install the pinned version."
    )
