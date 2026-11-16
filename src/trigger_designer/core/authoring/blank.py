"""An empty workflow, written the way the editor saves one (Qt-free)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from trigger_designer.core.constants import VERSION, WORKFLOW_SCHEMA_VERSION

#: The scene size the editor uses for every workflow.
SCENE_SIZE = 64000


def new_workflow() -> dict:
    """A workflow with no nodes. It gets its own ``workflow_uuid``, which the
    run records use to tell workflows apart."""
    return {
        "id": 1,
        "scene_width": SCENE_SIZE,
        "scene_height": SCENE_SIZE,
        "nodes": [],
        "edges": [],
        "groups": [],
        "comments": [],
        "workflow_metadata": {
            "schema_version": WORKFLOW_SCHEMA_VERSION,
            "app_version": VERSION,
            "saved_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "workflow_uuid": str(uuid.uuid4()),
        },
    }
