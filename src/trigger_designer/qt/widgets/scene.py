"""Custom Scene implementation with group support"""
from typing import List, Optional, Set, TYPE_CHECKING, cast
from nodeeditor.node_scene import Scene as BaseScene
from trigger_designer.qt.widgets.node_scene_group import NodeSceneGroupMixin
from loguru import logger

if TYPE_CHECKING:
    from trigger_designer.qt.widgets.node_group import NodeGroup
    from nodeeditor.node_node import Node


class TriggerScene(NodeSceneGroupMixin, BaseScene):
    """Scene class with support for node grouping"""

    def __init__(self) -> None:
        BaseScene.__init__(self)
        NodeSceneGroupMixin.__init__(self)

    def serialize(self) -> dict:
        """Serialize scene data including groups
        
        Returns:
            Dict containing serialized scene data
        """
        data = super().serialize()
        
        # Add groups
        data['groups'] = [group.serialize() for group in self.groups]
        
        return data

    def deserialize(self, data: dict, hashmap={}, restore_id: bool = True) -> bool:
        """Deserialize scene data including groups
        
        Args:
            data: Dict containing serialized scene data
            hashmap: Mapping of old to new object IDs
            restore_id: Whether to restore object IDs
            
        Returns:
            True if deserialization was successful
        """
        try:
            # Deserialize nodes first
            success = super().deserialize(data, hashmap, restore_id)
            if not success:
                return False
                
            # Then restore groups
            if 'groups' in data:
                # Import here to avoid circular dependency
                from trigger_designer.qt.widgets.node_group import NodeGroup
                
                for group_data in data['groups']:
                    group = NodeGroup(self)
                    success = group.deserialize(group_data, hashmap)
                    if success:
                        self.groups.add(group)
                    else:
                        logger.warning(f"Failed to deserialize group: {group_data}")
            
            return True
            
        except Exception as e:
            logger.exception("Error deserializing scene groups")
            return False