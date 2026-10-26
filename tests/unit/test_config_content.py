"""Both node families share the ConfigContent plumbing."""

from __future__ import annotations

from trigger_designer.qt.helpers.config_content import ConfigContent
from trigger_designer.qt.helpers.shaping_support import ShapingContent
from trigger_designer.qt.widgets.nodes.Preparation.select import SelectContent


def test_select_and_shaping_share_config_content() -> None:
    assert issubclass(SelectContent, ConfigContent)
    assert issubclass(ShapingContent, ConfigContent)
