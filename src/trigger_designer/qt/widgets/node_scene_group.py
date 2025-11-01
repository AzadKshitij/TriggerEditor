"""Scene extensions for node grouping functionality"""
from typing import List, Optional, Set, TYPE_CHECKING
from nodeeditor.node_scene import Scene
from nodeeditor.node_node import Node
from nodeeditor.utils import dumpException

if TYPE_CHECKING:
    from trigger_designer.qt.widgets.node_group import NodeGroup
    from trigger_designer.qt.node_base import TriggerNode

class NodeSceneGroupMixin:
    """Mixin class adding group management functionality to Scene"""

    def __init__(self) -> None:
        """Initialize group management"""
        self.groups: Set['NodeGroup'] = set()

    def create_group(self, nodes: List['Node'] = None) -> Optional['NodeGroup']:
        """Create a new node group
        
        Args:
            nodes: Optional list of nodes to add to the group. If None, uses selected nodes.
        
        Returns:
            The created NodeGroup or None if no valid nodes were provided
        """
        try:
            # Use provided nodes or get selected ones
            if nodes is None:
                nodes = [
                    item.node 
                    for item in self.selectedItems()
                    if hasattr(item, "node")
                ]

            # Need at least 2 nodes to form a group
            if len(nodes) < 2:
                return None

            # Import here to avoid circular dependency
            from trigger_designer.qt.widgets.node_group import NodeGroup
            
            # Create and setup group
            group = NodeGroup(self)
            for node in nodes:
                group.add_node(node)
            
            self.groups.add(group)
            self.history.storeHistory("Created Node Group")
            
            return group

        except Exception as e:
            dumpException(e)
            return None

    def remove_group(self, group: 'NodeGroup') -> None:
        """Remove a node group
        
        Args:
            group: The group to remove
        """
        if group in self.groups:
            self.groups.remove(group)
            group.setParentItem(None)
            if self.grScene:
                self.grScene.removeItem(group)
                self.history.storeHistory("Removed Node Group")

    def get_groups(self) -> List['NodeGroup']:
        """Get all node groups in the scene
        
        Returns:
            List of all NodeGroup instances
        """
        return list(self.groups)

    def collapse_group(self, group: 'NodeGroup') -> None:
        """Collapse a node group to minimize visual space
        
        Args:
            group: The group to collapse
        """
        if group in self.groups:
            group.collapse()
            self.history.storeHistory("Collapsed Group")

    def expand_group(self, group: 'NodeGroup') -> None:
        """Expand a collapsed node group
        
        Args:
            group: The group to expand
        """
        if group in self.groups:
            group.expand()
            self.history.storeHistory("Expanded Group")

    def ungroup_selected(self) -> None:
        """Ungroup any selected groups"""
        selected_groups = [
            item for item in self.selectedItems()
            if hasattr(item, "nodes")  # NodeGroup check
        ]
        for group in selected_groups:
            self.remove_group(group)