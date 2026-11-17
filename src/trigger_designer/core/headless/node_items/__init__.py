"""What the settings of list-valued (and untyped) properties look like.

``node_spec`` infers a JSON Schema from each op's *defaults*, and an empty list
says nothing about its items. A harness that reads ``describe_op`` then has to
read the source to learn that ``preparation.groupby`` wants
``{"field", "action", "output_name"}``. These tables fill that in.

Each group module holds plain dict literals (no data libraries, no Qt, so
``list_ops`` stays instant):

``PROPS``
    ``(op, setting) -> schema fragment`` merged into that setting's schema:
    ``{"items": ...}`` for a list, ``{"type": ...}`` for a setting whose
    default is ``None``. Choice lists copy the editor's vocabulary; a test per
    group pins them to the real constants.
``EXAMPLES``
    ``op -> settings`` that work when the node is wired up. A test per group
    runs each through the node's own ``run_node``.
"""

from __future__ import annotations

from typing import Any

from trigger_designer.core.headless.node_items import (
    audit,
    join,
    prep_a,
    prep_b,
    transform,
)

GROUPS = (prep_a, prep_b, join, transform, audit)

PROPS: dict[tuple[str, str], dict[str, Any]] = {}
EXAMPLES: dict[str, dict[str, Any]] = {}

for _group in GROUPS:
    PROPS.update(_group.PROPS)
    EXAMPLES.update(_group.EXAMPLES)
