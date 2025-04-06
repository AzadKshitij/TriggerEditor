from qtpy.QtWidgets import QGraphicsItem, QGraphicsRectItem, QGraphicsTextItem
from qtpy.QtCore import Qt, QRectF
from qtpy.QtGui import QPen, QBrush, QColor, QFont, QCursor, QTextOption
from nodeeditor.node_scene import Scene
from nodeeditor.node_node import Node


class NodeGroup(QGraphicsRectItem):
    def __init__(self, scene: 'Scene'):
        super().__init__()
        self.nodes: set['Node'] = set()
        self._scene = scene
        self.title = "Group"
        self.title_height = 25

        # Visual properties
        self.setFlag(QGraphicsItem.ItemIsMovable, False)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setAcceptHoverEvents(True)

        self.setPen(QPen(QColor("#666666"), 1.5, Qt.DashLine))
        self.setBrush(QBrush(QColor(80, 80, 80, 40)))

        # Create title bar
        self.title_item = QGraphicsTextItem(self)
        self.title_item.setDefaultTextColor(QColor("#333333"))
        self.title_item.setFont(QFont("Arial", 10, QFont.Bold))
        self.title_item.setPlainText(self.title)
        self.title_item.setTextWidth(200)

        # Center text within text item
        doc = self.title_item.document()
        # doc.setDocumentMargin(0)
        if doc:
            option = doc.defaultTextOption()
            option.setAlignment(Qt.AlignmentFlag.AlignCenter)
            option.setWrapMode(QTextOption.WrapMode.NoWrap)
            option.setTextDirection(Qt.LeftToRight)
            doc.setDocumentMargin(0)
            doc.setDefaultTextOption(option)
            doc.setMaximumBlockCount(1)  # Limit to one line

        # Enable text editing on double click
        self.title_item.setFlag(QGraphicsItem.ItemIsMovable, False)
        self.title_item.setFlag(QGraphicsItem.ItemIsSelectable)
        self.title_item.setFlag(QGraphicsItem.ItemIsFocusable)
        self.title_item.setTextInteractionFlags(Qt.TextEditorInteraction)

        # Track if we're dragging from title
        self.dragging = False
        self.last_pos = None
        self.hovering = False

        # Add to graphics scene
        scene.grScene.addItem(self)

    def add_node(self, node):
        """Add a node to the group"""
        self.nodes.add(node)
        self.update_geometry()

    def remove_node(self, node):
        """Remove a node from the group"""
        if node in self.nodes:
            self.nodes.remove(node)
            self.update_geometry()

    def update_geometry(self):
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

    def mousePressEvent(self, event):
        """Handle mouse press to start dragging"""
        if self.is_title_bar_area(event.pos()):
            self.dragging = True
            self.last_pos = event.pos()
            event.accept()
        else:
            event.ignore()
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """Handle mouse release to stop dragging"""
        self.dragging = False
        self.last_pos = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        """Handle double click to edit title"""
        if self.title_item.contains(event.pos() - self.title_item.pos()):
            self.title_item.setTextInteractionFlags(Qt.TextEditorInteraction)
            # Set single line behavior
            doc = self.title_item.document()
            doc.setMaximumBlockCount(1)  # Limit to one line
            doc.setDocumentMargin(0)     # Remove margins
            self.title_item.setFocus()
            event.accept()
        else:
            event.ignore()
            super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event):
        """Handle key events for title editing"""
        print("🐍 File: widgets/node_group.py:125 | keyPressEvent ~ self.title_item.hasFocus()",
              self.title_item.hasFocus())
        if self.title_item.hasFocus():
            print(
                "🐍 File: widgets/node_group.py:126 | keyPressEvent ~ event.key()", event.key(), "Qt.Key_Return:", Qt.Key_Return)
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                # Commit changes and disable editing
                self.title = self.title_item.toPlainText().strip()
                self.title_item.clearFocus()
                self.title_item.setTextInteractionFlags(Qt.NoTextInteraction)
                event.accept()
                return
        super().keyPressEvent(event)

    def focusOutEvent(self, event):
        """Handle focus out to save title changes"""
        if self.title_item.hasFocus():
            self.title = self.title_item.toPlainText().strip()
            self.title_item.setTextInteractionFlags(Qt.NoTextInteraction)
        super().focusOutEvent(event)

    def mouseMoveEvent(self, event):
        """Move group only when dragging from title bar"""
        if self.dragging and self.last_pos:
            delta = event.pos() - self.last_pos

            # Move group rectangle
            self.setPos(self.pos() + delta)

            # Move all contained nodes
            for node in self.nodes:
                new_pos = node.pos + delta
                node.setPos(new_pos.x(), new_pos.y())

            # self.last_pos = event.pos()
            event.accept()
        else:
            event.ignore()
            super().mouseMoveEvent(event)

    def is_title_bar_area(self, pos):
        """Check if position is in title bar area"""
        return QRectF(
            self.rect().left(),
            self.rect().top(),
            self.rect().width(),
            self.title_height
        ).contains(pos)

    # def mouseMoveEvent(self, event):
    #     """Move all nodes when group is moved"""
    #     super().mouseMoveEvent(event)
    #     delta = event.pos() - event.lastPos()

    #     # Update positions of all nodes using separate x,y coordinates
    #     for node in self.nodes:
    #         new_pos = node.pos + delta
    #         node.setPos(new_pos.x(), new_pos.y())

    def paint(self, painter, option, widget=None):
        """Custom paint to add title bar background"""
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
        if self.hovering and self.is_title_bar_area(self.mapFromScene(self._scene.grScene.views()[0].mapToScene(self._scene.grScene.views()[0].mapFromGlobal(QCursor.pos())))):
            title_color = QColor(160, 160, 160, 180)  # Darker when hovered

        painter.fillRect(title_rect, title_color)

    def hoverEnterEvent(self, event):
        self.hovering = True
        return super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.hovering = False
        return super().hoverLeaveEvent(event)

# class TriggerScene:
#     def __init__(self):
#         super().__init__()
#         self.groups = []

#     def create_group(self, nodes=None):
#         """Create a new node group"""
#         group = NodeGroup(self)
#         self.groups.append(group)

#         if nodes:
#             for node in nodes:
#                 group.add_node(node)

#         return group

#     def delete_group(self, group):
#         """Delete a node group"""
#         if group in self.groups:
#             self.groups.remove(group)
#             self.removeItem(group)
