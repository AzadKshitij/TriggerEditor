"""Serialization helpers for node content widgets.

Schema-based, opt-in content state: a node declares a schema and gets
serialize/deserialize/validation for the fields it names, instead of hand-writing
a pair of methods per field.

Undo/redo does not live here - see ``trigger_designer.qt.undo``.
"""

import copy
from typing import Any, Dict, Optional


class SerializableContentMixin:
    """Opt-in helpers for explicit, schema-based content serialization."""

    serialized_state_schema: Dict[str, Dict[str, Any]] = {}

    def get_serialized_state_schema(self) -> Dict[str, Dict[str, Any]]:
        return self.serialized_state_schema

    def _copy_serialized_value(self, value: Any) -> Any:
        return copy.deepcopy(value)

    def _normalize_serialized_value(self, default: Any, value: Any) -> Any:
        if value is None and default is not None:
            return self._copy_serialized_value(default)

        if isinstance(default, dict) and isinstance(value, dict):
            merged = self._copy_serialized_value(default)
            merged.update(value)
            return merged

        if isinstance(default, list) and value is None:
            return self._copy_serialized_value(default)

        return self._copy_serialized_value(value)

    def get_serialized_state(self) -> Dict[str, Any]:
        state: Dict[str, Any] = {}
        for key, spec in self.get_serialized_state_schema().items():
            attr_name = spec.get("attr", key)
            default = self._copy_serialized_value(spec.get("default"))
            value = getattr(self, attr_name, default)
            state[key] = self._normalize_serialized_value(default, value)
        return state

    def serialize_content_state(self, payload: Optional[dict] = None) -> dict:
        data = {} if payload is None else payload
        data.update(self.get_serialized_state())
        return data

    def deserialize_content_state(self, data: dict) -> Dict[str, Any]:
        normalized_state: Dict[str, Any] = {}
        for key, spec in self.get_serialized_state_schema().items():
            attr_name = spec.get("attr", key)
            default = self._copy_serialized_value(spec.get("default"))
            value = self._normalize_serialized_value(default, data.get(key, default))
            setattr(self, attr_name, value)
            normalized_state[key] = value
        return normalized_state

    def validate_loaded_state(self) -> list[str]:
        return []
