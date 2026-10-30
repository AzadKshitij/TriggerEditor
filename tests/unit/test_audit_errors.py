"""Stored errors of failed nodes (plan 02 3.8a, adapted to the real NodeError)."""

from __future__ import annotations

import dataclasses

import polars as pl
import pytest

from tests.support.audit_helpers import FakeNode, FakeResult
from trigger_designer.core.audit import errors_adapter
from trigger_designer.core.audit.canonical import canonical_json
from trigger_designer.core.audit.errors_adapter import (
    STABLE_KEYS,
    error_to_dict,
    exception_to_dict,
    node_error_to_dict,
)
from trigger_designer.core.errors import NodeError, translate_exception


def _column_error() -> NodeError:
    try:
        pl.DataFrame({"a": [1]}).select(pl.col("amnt"))
    except Exception as exc:  # noqa: BLE001
        return translate_exception(exc, node=FakeNode(14, "Filter"), phase="run")
    raise AssertionError("select of a missing column must fail")


def test_stored_error_has_the_stable_key_set_and_list_columns():
    data = node_error_to_dict(_column_error())
    assert set(STABLE_KEYS) <= set(data)
    assert isinstance(data["columns"], list)
    assert data["code"].startswith("TD-") and data["title"]
    canonical_json(data)  # tuples would have raised


def test_every_error_field_is_json_safe():
    error = NodeError(
        code="TD-X-001",
        title="t",
        columns=("a", "b"),
        sample_values=("1", "2"),
        did_you_mean=("c",),
        params={"row": 3, "values": ("x",)},
    )
    data = node_error_to_dict(error)
    assert data["columns"] == ["a", "b"] and data["sample_values"] == ["1", "2"]
    assert data["params"]["values"] == ["x"]
    canonical_json(data)


def test_technical_is_capped():
    error = NodeError(code="TD-X", title="t", technical="x" * 20_000)
    assert len(node_error_to_dict(error)["technical"]) == 8000


def test_error_to_dict_translates_the_result_exception():
    try:
        pl.DataFrame({"a": [1]}).select(pl.col("amnt"))
    except Exception as exc:  # noqa: BLE001
        result = FakeResult(False, exception=exc, error=str(exc))
    data = error_to_dict(result, FakeNode(14, "Filter"))
    assert data["node_id"] == 14 and data["code"].startswith("TD-")
    assert data["technical"]


def test_exception_to_dict_unwraps_original_exception():
    class Wrapper(Exception):
        original_exception = KeyError("amnt")

    data = exception_to_dict(Wrapper("wrapped"), FakeNode(1, "N"))
    assert "amnt" in data["technical"] or data["exc_type"]


def test_string_error_is_accepted():
    data = error_to_dict(FakeResult(False, error="something odd"), FakeNode(2))
    assert data["code"] and data["title"]


def test_fallback_has_the_same_stable_keys(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def deny(name, *args, **kwargs):
        if name == "trigger_designer.core.errors":
            raise ImportError("plan 03 not merged")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", deny)
    data = error_to_dict(FakeResult(False, error="boom"), FakeNode(5, "Node"))
    monkeypatch.undo()
    assert tuple(data) == STABLE_KEYS
    assert data["code"] == "TD-SYS-999" and data["technical"] == "boom"
    assert data["node_id"] == 5
    canonical_json(data)


def test_stable_keys_are_real_nodeerror_fields():
    fields = {f.name for f in dataclasses.fields(NodeError)}
    assert set(STABLE_KEYS) <= fields


def test_sync_enrich_returns_a_dict_and_never_raises():
    result = FakeResult(False, exception=ValueError("x"), error="x")
    data = error_to_dict(result, FakeNode(1), enrich=True)
    assert data["code"]
    assert errors_adapter.error_to_dict(
        result, FakeNode(1), enricher=lambda err, node: err
    )["code"]


def test_broken_enricher_degrades_to_fallback():
    def boom(_err, _node):
        raise RuntimeError("enricher bug")

    data = error_to_dict(FakeResult(False, error="e"), FakeNode(3), enricher=boom)
    assert data["code"] == "TD-SYS-999"


@pytest.mark.parametrize("redact", [True, False])
def test_redact_flag_is_accepted(redact):
    data = error_to_dict(FakeResult(False, error="bad value 42"), None, redact=redact)
    assert data["title"]
