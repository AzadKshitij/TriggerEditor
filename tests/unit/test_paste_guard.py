#!/usr/bin/env python3

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)

from trigger_designer.qt.main_window import parse_node_clipboard_payload


def test_rejects_json_scalars() -> None:
    assert parse_node_clipboard_payload("true") is None
    assert parse_node_clipboard_payload("123") is None
    assert parse_node_clipboard_payload('"just text"') is None
    assert parse_node_clipboard_payload("null") is None


def test_rejects_non_node_json() -> None:
    assert parse_node_clipboard_payload("[1, 2]") is None
    assert parse_node_clipboard_payload('{"a": 1}') is None
    assert parse_node_clipboard_payload('{"nodes": {}}') is None
    assert parse_node_clipboard_payload("not json at all") is None
    assert parse_node_clipboard_payload("") is None


def test_accepts_node_payload() -> None:
    payload = parse_node_clipboard_payload('{"nodes": [], "edges": []}')
    assert payload == {"nodes": [], "edges": []}
