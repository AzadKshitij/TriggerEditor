"""Node grouping functionality for the node editor"""
from typing import Optional, Set, Dict, Any, TYPE_CHECKING, cast
from qtpy.QtWidgets import (QGraphicsItem, QGraphicsRectItem, QGraphicsTextItem,
                          QWidget, QStyleOptionGraphicsItem, QGraphicsSceneMouseEvent,
                          QGraphicsSceneHoverEvent)
from qtpy.QtCore import Qt, QRectF, QPointF, QEvent
from qtpy.QtGui import (QPen, QBrush, QColor, QFont, QCursor, QTextOption,
                       QPainter, QPainterPath, QKeyEvent, QFocusEvent)
from nodeeditor.utils_no_qt import dumpException

if TYPE_CHECKING:
    from nodeeditor.node_socket import Socket
    from nodeeditor.node_edge import Edge
    from nodeeditor.node_node import Node
    from nodeeditor.node_scene import Scene
    from trigger_designer.qt.node_base import TriggerNode


class NodeGroup(QGraphicsRectItem):
    """A group of nodes that can be moved, collapsed, and managed together.
    
    The NodeGroup provides functionality for:
    - Grouping multiple nodes together
    - Moving them as a single unit
    - Collapsing/expanding to reduce visual clutter
    - Maintaining connections between nodes
    """
    def __init__(self, scene: 'Scene'):
        """Initialize the node group."""
        super().__init__()
        self.nodes: Set['Node'] = set()
        self._scene = scene
        self.title = "Group"
        self.title_height = 25
        
        # Visual properties
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setAcceptHoverEvents(True)

        # Set up appearance
        self.setPen(QPen(QColor("#666666"), 1.5, Qt.PenStyle.DashLine))
        self.setBrush(QBrush(QColor(80, 80, 80, 40)))

        # Create title bar
        self.title_item = QGraphicsTextItem(self)
        self.title_item.setDefaultTextColor(QColor("#333333"))
        font = QFont("Arial", 10)
        font.setWeight(QFont.Weight.Bold)
        self.title_item.setFont(font)
        self.title_item.setPlainText(self.title)
        self.title_item.setTextWidth(200)

        # Center text within text item
        doc = self.title_item.document()
        if doc:
            option = doc.defaultTextOption()
            option.setAlignment(Qt.AlignmentFlag.AlignCenter)
            option.setWrapMode(QTextOption.WrapMode.NoWrap)
            doc.setDocumentMargin(0)
            doc.setDefaultTextOption(option)
            doc.setMaximumBlockCount(1)  # Limit to one line

        # Enable text editing on double click
        self.title_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.title_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.title_item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable)
        self.title_item.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)

        # Track dragging state
        self.dragging = False
        self.last_pos = None
        self.hovering = False
        self.collapsed = False

        # Add to graphics scene
        scene.grScene.addItem(self)

    def add_node(self, node: 'Node') -> None:
        """Add a node to the group"""
        self.nodes.add(node)
        self.update_geometry()

    def remove_node(self, node: 'Node') -> None:
        """Remove a node from the group"""
        if node in self.nodes:
            self.nodes.remove(node)
            if not self.nodes:
                self._scene.grScene.removeItem(self)
            else:
                self.update_geometry()

    def update_geometry(self) -> None:
        """Update the group's bounding rectangle to encompass all nodes"""
        if not self.nodes:
            return

        # Get bounds of all nodes
        rects = [node.grNode.boundingRect().translated(node.pos)
                 for node in self.nodes]
        group_rect = rects[0]
        for rect in rects[1:]:
            group_rect = group_rect.united(rect)

        # Add padding
        padding = 20
        group_rect.adjust(-padding, -padding, padding, padding)
        self.setRect(group_rect)

        # Position title bar at top of group
        title_width = self.title_item.boundingRect().width()
        self.title_item.setPos(
            group_rect.left() + (group_rect.width() - title_width) / 2,
            group_rect.top() + 5
        )

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Handle mouse press to start dragging"""
        if self.is_title_bar_area(event.pos()):
            self.dragging = True
            self.last_pos = event.pos()
            event.accept()
        else:
            event.ignore()
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Handle mouse release to stop dragging"""
        self.dragging = False
        self.last_pos = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Handle double click to edit title"""
        if self.title_item.contains(event.pos() - self.title_item.pos()):
            self.title_item.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
            # Set single line behavior
            doc = self.title_item.document()
            if doc:
                doc.setMaximumBlockCount(1)  # Limit to one line
                doc.setDocumentMargin(0)     # Remove margins
            self.title_item.setFocus()
            event.accept()
        else:
            event.ignore()
            super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle key events for title editing"""
        if self.title_item.hasFocus():
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                # Commit changes and disable editing
                self.title = self.title_item.toPlainText().strip()
                self.title_item.clearFocus()
                self.title_item.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
                event.accept()
                return
        super().keyPressEvent(event)

    def focusOutEvent(self, event: QFocusEvent) -> None:
        """Handle focus out to save title changes"""
        if self.title_item.hasFocus():
            self.title = self.title_item.toPlainText().strip()
            self.title_item.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        super().focusOutEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        """Move group only when dragging from title bar"""
        if self.dragging and self.last_pos is not None:
            delta = event.pos() - self.last_pos

            # Move group rectangle
            self.setPos(self.pos() + delta)

            # Move all contained nodes
            for node in self.nodes:
                new_pos = node.pos + delta
                node.setPos(new_pos.x(), new_pos.y())

            event.accept()
        else:
            event.ignore()
            super().mouseMoveEvent(event)

    def is_title_bar_area(self, pos: QPointF) -> bool:
        """Check if position is in title bar area"""
        return QRectF(
            self.rect().left(),
            self.rect().top(),
            self.rect().width(),
            self.title_height
        ).contains(pos)

    def paint(self, painter: QPainter | None, option: QStyleOptionGraphicsItem | None,
              widget: QWidget | None = None) -> None:
        """Custom paint to add title bar background"""
        if painter is None:
            return
            
        super().paint(painter, option, widget)

        # Draw title bar background with hover effect
        title_rect = QRectF(
            self.rect().left(),
            self.rect().top(),
            self.rect().width(),
            self.title_height
        )

        # Use darker color for title bar to indicate draggable area
        title_color = QColor(180, 180, 180, 150)
        if self.hovering and self.is_title_bar_area(
                self.mapFromScene(
                    self._scene.grScene.views()[0].mapToScene(
                        self._scene.grScene.views()[0].mapFromGlobal(
                            QCursor.pos())))):
            title_color = QColor(160, 160, 160, 180)  # Darker when hovered

        painter.fillRect(title_rect, title_color)

    def hoverEnterEvent(self, event: QGraphicsSceneHoverEvent) -> None:
        """Handle mouse hover enter"""
        self.hovering = True
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event: QGraphicsSceneHoverEvent) -> None:
        """Handle mouse hover leave"""
        self.hovering = False
        super().hoverLeaveEvent(event)