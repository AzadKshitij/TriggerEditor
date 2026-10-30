"""Workpaper Output has its own icon, registered and documented."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "trigger_designer"
ICON = (
    SRC
    / "resources"
    / "qt"
    / "images"
    / "node_icons"
    / "Input"
    / "Workpaper Output.svg"
)


def test_icon_file_follows_the_input_family_style():
    text = ICON.read_text(encoding="utf-8")
    assert 'viewBox="0 0 100 100"' in text
    assert 'rx="15"' in text and 'fill="#C92C2F"' in text
    assert "white" in text.lower() or "#fff" in text.lower()


def test_icon_is_registered_and_used_by_the_node_and_the_palette_spec():
    resources = json.loads((SRC / "qt" / "resources.json").read_text(encoding="utf-8"))
    entry = resources["node_workpaper_output"]
    assert (SRC / "resources" / entry["path"]).is_file()

    from trigger_designer.qt.widgets.nodes import _LAZY_NODE_SPECS
    from trigger_designer.qt.widgets.nodes.InOut.workpaper_output import (
        TriggerNode_WorkpaperOutput,
    )

    spec = next(
        s for s in _LAZY_NODE_SPECS if s["module_path"] == "InOut.workpaper_output"
    )
    assert spec["icon"] == TriggerNode_WorkpaperOutput.icon == "node_workpaper_output"


def test_node_reference_has_a_workpaper_output_row_with_the_real_icon():
    text = (ROOT / "docs" / "NODE_REFERENCE.md").read_text(encoding="utf-8")
    row = next(
        (line for line in text.splitlines() if line.startswith("| Workpaper Output |")),
        None,
    )
    assert row is not None
    target = re.search(r"\]\(([^)]+\.svg)\)", row).group(1)
    assert (ROOT / "docs" / target.replace("%20", " ")).is_file()
