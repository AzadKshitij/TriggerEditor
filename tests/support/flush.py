"""Run the evaluation a Config Dock edit left pending.

Edits reach a node's model at once but the node only runs when the user leaves
it (see ``qt/helpers/deferred_evaluation.py``). A test that changes a setting
and then reads the node's output calls ``flush(node)`` first, as clicking away
from the node would.
"""

from __future__ import annotations


def flush(node_or_content) -> None:
    content = getattr(node_or_content, "content", node_or_content)
    commit = getattr(content, "commit_pending_dock_edits", None)
    if callable(commit):
        commit(evaluate=True)


def live_value(node):
    """``node.value`` after running any evaluation the last edit left pending."""
    flush(node)
    return node.value
