"""DiagnosticFeed keeps one row per node/source and orders both kinds by seq."""

from __future__ import annotations

from trigger_designer.core.errors import ErrorContext, make_error
from trigger_designer.qt.helpers.diagnostic_feed import (
    CATEGORY_CONV,
    CATEGORY_ERRORS,
    CATEGORY_MESSAGES,
    CATEGORY_WARNINGS,
    KIND_LOG,
    KIND_PROBLEM,
    DiagnosticFeed,
)


def _error(code="TD-SYS-001", node_id=1, **params):
    ctx = ErrorContext(node_id=node_id, node_label=f"Node {node_id}")
    return make_error(code, ctx, **params)


# -- the six behaviours carried over from ProblemsStore --------------------
def test_upsert_dedupes_equal_errors() -> None:
    feed = DiagnosticFeed()
    changes: list[int] = []
    feed.changed.connect(lambda: changes.append(1))
    error = _error()
    assert feed.upsert(error, "live") is True
    assert feed.upsert(error, "live") is False
    assert len(changes) == 1


def test_upsert_replaces_on_new_fingerprint() -> None:
    feed = DiagnosticFeed()
    feed.upsert(_error(message="one"), "live")
    feed.upsert(_error(message="two"), "live")
    assert feed.count() == 1
    assert "two" in feed.entries()[0][1].title


def test_run_entries_listed_before_live() -> None:
    feed = DiagnosticFeed()
    feed.upsert(_error("TD-SYS-001", node_id=2), "live")
    feed.upsert(_error("TD-RUN-001", node_id=1), "run")
    assert [source for source, _error in feed.entries()] == ["run", "live"]


def test_clear_source_run_leaves_live() -> None:
    feed = DiagnosticFeed()
    feed.upsert(_error("TD-RUN-001", node_id=1), "run")
    feed.upsert(_error("TD-SYS-001", node_id=1), "live")
    feed.clear_source("run")
    assert feed.count() == 1
    assert feed.entries()[0][0] == "live"


def test_roots_only_excludes_knock_on() -> None:
    feed = DiagnosticFeed()
    feed.upsert(_error("TD-RUN-003", culprit_label="Upstream"), "run")
    feed.upsert(_error("TD-SYS-001", node_id=2), "run")
    assert feed.count("error") == 2
    assert feed.count("error", roots_only=True) == 1


def test_remove_by_node() -> None:
    feed = DiagnosticFeed()
    feed.upsert(_error(node_id=1), "live")
    feed.upsert(_error(node_id=2), "live")
    feed.remove(1)
    assert feed.count() == 1


# -- the merge ------------------------------------------------------------
def test_log_and_problem_records_interleave_by_seq() -> None:
    feed = DiagnosticFeed()
    feed.add_log("INFO", "first")
    feed.upsert(_error(node_id=1), "live")
    feed.add_log("ERROR", "third")
    assert [record.kind for record in feed.records()] == [
        KIND_LOG,
        KIND_PROBLEM,
        KIND_LOG,
    ]
    assert [record.seq for record in feed.records()] == [1, 2, 3]


def test_upsert_keeps_slot_and_first_seen() -> None:
    feed = DiagnosticFeed()
    feed.upsert(_error(message="one"), "live")
    first = feed.records()[0]
    feed.add_log("INFO", "in between")
    feed.upsert(_error(message="two"), "live")
    problem = next(r for r in feed.records() if r.kind == KIND_PROBLEM)
    assert problem.seq == first.seq
    assert problem.first_seen == first.first_seen
    assert problem.error is not None and "two" in problem.error.title


def test_log_cap_never_evicts_a_problem() -> None:
    feed = DiagnosticFeed(max_log_records=2)
    feed.upsert(_error(node_id=1), "live")
    for index in range(5):
        feed.add_log("INFO", f"line {index}")
    assert [record.message for record in feed.records() if record.kind == KIND_LOG] == [
        "line 3",
        "line 4",
    ]
    assert feed.count() == 1


def test_clear_logs_leaves_problems() -> None:
    feed = DiagnosticFeed()
    feed.upsert(_error(node_id=1), "live")
    feed.add_log("INFO", "hello")
    feed.clear_logs()
    assert feed.count() == 1
    assert not [r for r in feed.records() if r.kind == KIND_LOG]


def test_node_less_errors_do_not_collide() -> None:
    feed = DiagnosticFeed()
    feed.upsert(_error("TD-SYS-001", node_id=None, message="alpha"), "live")
    feed.upsert(_error("TD-SYS-001", node_id=None, message="beta"), "live")
    assert feed.count() == 2


def test_categories_are_derived() -> None:
    feed = DiagnosticFeed()
    feed.upsert(_error("TD-TYP-001", node_id=1), "run")
    feed.upsert(_error("TD-SYS-001", node_id=2), "run")
    feed.upsert(_error("TD-RUN-005", node_id=3), "run")
    feed.add_log("INFO", "hello")
    counts = feed.counts()
    assert counts[CATEGORY_CONV] == 1
    assert counts[CATEGORY_ERRORS] == 1
    assert counts[CATEGORY_WARNINGS] == 1
    assert counts[CATEGORY_MESSAGES] == 1
    assert counts["all"] == 4
