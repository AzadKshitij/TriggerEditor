import copy
from typing import Any, Dict, List, Optional, Callable
from nodeeditor.node_content_widget import QDMNodeContentWidget


class StateManagementMixin:
    """Mixin class to handle state management and history tracking for node contents"""

    def __init__(self) -> None:
        self.changes: Dict[str, Any] = {}
        self.initial_state: Dict[str, Any] = {}

    def init_state_management(self, initial_state: Dict[str, Any]) -> None:
        """Initialize the state management with initial state structure"""
        self.initial_state = initial_state.copy()
        self.changes = initial_state.copy()

    def handle_state_change(
        self,
        new_data: Any,
        process_func: Callable,
        apply_func: Callable,
        desc: str = "State Changed",
    ) -> None:
        """Generic state change handler with history management

        Args:
            new_data: The new data to process
            process_func: Function to process the new data into state changes
            apply_func: Function to apply the state changes
            desc: Description for the history entry
        """
        if self.history.is_restoring_history:
            return

        # Store old state
        old_changes = {
            key: value.copy() if hasattr(value, "copy") else value
            for key, value in self.changes.items()
        }
        print(
            "🐍 File: helpers/state_mixin.py:37 | handle_state_change ~ old_changes",
            old_changes,
        )

        # Process new changes
        self.changes = process_func(new_data)
        print("")
        print("")
        print(
            "🐍 File: helpers/state_mixin.py:41 | handle_state_change ~ self.changes",
            self.changes,
        )
        print("")
        print("")

        # Apply changes
        apply_func()

        # Store history if there are actual changes
        if old_changes != self.changes:
            history_data = {
                "node": self.node,
                "old_changes": old_changes,
                "new_changes": {
                    key: value.copy() if hasattr(value, "copy") else value
                    for key, value in self.changes.items()
                },
            }

            self.history.storeHistory(desc=desc, data=history_data, setModified=True)

    def history_stamp_callback(self, history_data: dict, is_undo: bool) -> None:
        """Default history callback for undo/redo operations"""
        if is_undo:
            self.changes = history_data["old_changes"]
        else:
            self.changes = history_data["new_changes"]

        # Apply the changes
        if hasattr(self, "apply_changes"):
            self.apply_changes()

        # Update UI if needed
        if hasattr(self, "update_ui_from_changes"):
            self.update_ui_from_changes()

    def serialize(self) -> dict:
        """Serialize the state"""
        return {"changes": self.changes, "initial_state": self.initial_state}

    def deserialize(self, data: dict) -> None:
        """Deserialize the state"""
        self.changes = data.get("changes", self.initial_state.copy())
        self.initial_state = data.get("initial_state", {})


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
