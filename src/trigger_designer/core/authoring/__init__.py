"""Safe workflow authoring over the plain ``.tds`` JSON (Qt-free).

``Editor`` applies edits to a copy, ``apply_patch`` runs a list of them as one
batch, ``diff_workflows`` shows what changed. Nothing here writes a file: the
CLI (``edit`` / ``diff``) decides when to, and only with ``--apply``.
"""

from trigger_designer.core.authoring.blank import new_workflow
from trigger_designer.core.authoring.diff import diff_workflows, render_lines
from trigger_designer.core.authoring.edits import Editor
from trigger_designer.core.authoring.external_edit import (
    ExternalChange,
    analyse_external_edit,
)
from trigger_designer.core.authoring.patch import apply_patch

__all__ = [
    "Editor",
    "ExternalChange",
    "analyse_external_edit",
    "apply_patch",
    "diff_workflows",
    "new_workflow",
    "render_lines",
]
