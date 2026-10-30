"""Docs stay truthful: no empty placeholders, no features that do not exist."""

from __future__ import annotations

from pathlib import Path

DOCS = Path(__file__).resolve().parents[2] / "docs"


def test_every_doc_file_is_non_empty() -> None:
    empty = [
        str(path.relative_to(DOCS))
        for path in DOCS.rglob("*")
        if path.is_file()
        and path.suffix in {".md", ".txt"}
        and path.stat().st_size == 0
    ]
    assert empty == []


def test_executor_guide_documents_no_missing_features() -> None:
    text = (DOCS / "ENHANCED_EXECUTOR_GUIDE.md").read_text(encoding="utf-8")
    for invented in ("allowed_imports", "forbidden_functions", "allow_file_access"):
        assert invented not in text
    for real in ("max_execution_time", "before_node", "after_node", "code_filter"):
        assert real in text
