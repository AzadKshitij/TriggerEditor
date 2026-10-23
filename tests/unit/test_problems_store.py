"""ProblemsStore keeps one row per node/source and de-duplicates."""

from __future__ import annotations

from trigger_designer.core.errors import ErrorContext, make_error
from trigger_designer.qt.helpers.problems_store import ProblemsStore


def _error(code="TD-SYS-001", node_id=1, **params):
    ctx = ErrorContext(node_id=node_id, node_label=f"Node {node_id}")
    return make_error(code, ctx, **params)


def test_upsert_dedupes_equal_errors() -> None:
    store = ProblemsStore()
    changes: list[int] = []
    store.changed.connect(lambda: changes.append(1))
    error = _error()
    assert store.upsert(error, "live") is True
    assert store.upsert(error, "live") is False
    assert len(changes) == 1


def test_upsert_replaces_on_new_fingerprint() -> None:
    store = ProblemsStore()
    store.upsert(_error(message="one"), "live")
    store.upsert(_error(message="two"), "live")
    assert store.count() == 1
    assert "two" in store.entries()[0][1].title


def test_run_entries_listed_before_live() -> None:
    store = ProblemsStore()
    store.upsert(_error("TD-SYS-001", node_id=2), "live")
    store.upsert(_error("TD-RUN-001", node_id=1), "run")
    assert [source for source, _error in store.entries()] == ["run", "live"]


def test_clear_source_run_leaves_live() -> None:
    store = ProblemsStore()
    store.upsert(_error("TD-RUN-001", node_id=1), "run")
    store.upsert(_error("TD-SYS-001", node_id=1), "live")
    store.clear_source("run")
    assert store.count() == 1
    assert store.entries()[0][0] == "live"


def test_roots_only_excludes_knock_on() -> None:
    store = ProblemsStore()
    store.upsert(_error("TD-RUN-003", culprit_label="Upstream"), "run")
    store.upsert(_error("TD-SYS-001", node_id=2), "run")
    assert store.count("error") == 2
    assert store.count("error", roots_only=True) == 1


def test_remove_by_node() -> None:
    store = ProblemsStore()
    store.upsert(_error(node_id=1), "live")
    store.upsert(_error(node_id=2), "live")
    store.remove(1)
    assert store.count() == 1
