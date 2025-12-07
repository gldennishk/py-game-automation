from typing import Dict, Optional, List
import os
import traceback
from PySide6.QtCore import Qt, QPointF, Signal, QEvent
from PySide6.QtGui import QPen, QBrush, QColor, QPainter, QFont, QPainterPath, QTransform, QShortcut, QKeySequence, QDragEnterEvent, QDropEvent, QPixmap
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsItem, QGraphicsEllipseItem, QGraphicsRectItem, QGraphicsPathItem, QWidget, QHBoxLayout, QVBoxLayout, QGraphicsTextItem, QPushButton, QMenu, QGraphicsProxyWidget, QTextEdit, QSizeGrip
from ..core.actions import VisualScript, VisualNode


class VisualNodeItem(QGraphicsRectItem):
    _colors = {
        'click': '#B0B8C4',      # Muted blue-gray
        'key': '#C4B8A8',        # Muted beige
        'sleep': '#B8A8C4',      # Muted purple-gray
        'find_color': '#C4A8A8', # Muted rose-gray
        'condition': '#A8B0C4', # Muted blue-gray
        'loop': '#B8B0A8',       # Muted brown-gray
        'find_image': '#A8C4B0', # Muted green-gray
        'verify_image_color': '#C4B0A8', # Muted orange-gray
        'default': '#B0B4B8'     # Neutral gray
    }
    
    # Execution state constants
    STATE_IDLE = "idle"
    STATE_RUNNING = "running"
    STATE_SUCCESS = "success"
    STATE_FAILED = "failed"
    
    _titles = {
        'click': '點擊',
        'key': '按鍵',
        'sleep': '等待',
        'find_color': '找顏色',
        'condition': '條件',
        'loop': '迴圈',
        'find_image': '找圖片（不點擊）',
        'verify_image_color': '驗證圖片顏色',
        'default': '節點'
    }
    
    def __init__(self, node: VisualNode, editor=None):
        super().__init__(0, 0, 180, 80)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        
        self.node = node
        self._editor = editor
        self.setPos(node.position)
        
        self._normal_color = QColor(self._colors.get(node.type, self._colors['default']))
        self._selected_color = QColor('#0078d4')
        self._pen = QPen(QColor(200, 200, 200), 1.5)
        self._selected_pen = QPen(QColor('#0078d4'), 2.0)
        
        # Execution state tracking
        self._execution_state = self.STATE_IDLE
        self._execution_pen = None  # Will be set based on state
        
        # Breakpoint indicator (red circle in top-left corner)
        self._breakpoint_indicator = QGraphicsEllipseItem(0, 0, 10, 10, self)
        self._breakpoint_indicator.setPos(5, 5)  # Position in top-left corner
        self._breakpoint_indicator.setBrush(QBrush(QColor(244, 67, 54)))  # Red color
        self._breakpoint_indicator.setPen(QPen(QColor(200, 50, 50), 1))
        self._breakpoint_indicator.setZValue(10)  # Above other elements
        self._breakpoint_enabled = False
        self._breakpoint_indicator.setVisible(False)
        
        # Add text items
        self._title = QGraphicsTextItem(self)
        self._title.setPlainText(f"{self._titles.get(node.type, '節點')}")
        self._title.setPos(10, 10)
        tfont = QFont('Arial')
        tfont.setPointSize(12)
        tfont.setWeight(QFont.Weight.DemiBold)
        self._title.setFont(tfont)
        self._title.setDefaultTextColor(QColor(51, 51, 51))
        
        # Add parameter preview
        self._params_text = QGraphicsTextItem(self)
        params = []
        if node.type == 'click':
            if 'button' in node.params:
                params.append(f"按鈕: {node.params['button']}")
            if 'duration' in node.params:
                params.append(f"{node.params['duration']}秒")
        elif node.type == 'sleep':
            if 'seconds' in node.params:
                params.append(f"{node.params['seconds']}秒")
        elif node.type == 'find_color':
            if 'confidence' in node.params:
                params.append(f"置信度: {node.params['confidence']}")
        elif node.type == 'find_image':
            if 'template_name' in node.params:
                template_name = node.params['template_name']
                params.append(f"範本: {template_name}")
            if 'confidence' in node.params:
                params.append(f"置信度: {node.params['confidence']}")
                
        self._params_text.setPlainText("\n".join(params[:3]))
        self._params_text.setPos(10, 40)
        pfont = QFont('Arial')
        pfont.setPointSize(11)
        self._params_text.setFont(pfont)
        self._params_text.setDefaultTextColor(QColor(51, 51, 51))
        
        # Enable drag-and-drop for find_image nodes
        if node.type == 'find_image':
            self.setAcceptDrops(True)
        
        # Add visual output handle for drag-to-connect discoverability
        # Small circle on the right side of the node to indicate connection point
        self._output_handle = QGraphicsEllipseItem(0, 0, 8, 8, self)
        rect = self.rect()
        handle_x = rect.width() - 12  # 12px from right edge
        handle_y = rect.height() / 2 - 4  # Centered vertically
        self._output_handle.setPos(handle_x, handle_y)
        self._output_handle.setBrush(QBrush(QColor(100, 100, 100)))
        self._output_handle.setPen(QPen(QColor(150, 150, 150), 1))
        self._output_handle.setZValue(1)  # Above the node background
        
        self.update_appearance()

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing, True)
        
        # Determine pen and fill based on selection and execution state
        if self.isSelected():
            pen = self._selected_pen
            fill = QColor(self._normal_color).lighter(150)  # Subtle lightening for selected
        else:
            pen = self._pen
            fill = QColor(self._normal_color).lighter(140)  # Flat fill, no gradient
        
        # Override with execution state pen if active
        if self._execution_state == self.STATE_RUNNING:
            # Blue flashing border for running state (thicker border)
            pen = QPen(QColor('#0078d4'), 3.0)
            fill = QColor(self._normal_color).lighter(160)  # Brighter when running
        elif self._execution_state == self.STATE_SUCCESS:
            # Green border for success (short-lived)
            pen = QPen(QColor('#4caf50'), 2.5)
        elif self._execution_state == self.STATE_FAILED:
            # Red border for failed (persistent)
            pen = QPen(QColor('#f44336'), 2.5)
        
        painter.setPen(pen)
        painter.setBrush(QBrush(fill))
        rect = self.rect()
        painter.drawRoundedRect(rect, 8, 8)
        # Note: Child items (_title, _params_text, _output_handle) are QGraphicsItem children
        # and will be rendered automatically by Qt's graphics system, so we don't call super().paint()
    
    def update_appearance(self):
        if self.isSelected():
            self.setPen(self._selected_pen)
            # Highlight output handle when selected
            if hasattr(self, '_output_handle'):
                self._output_handle.setBrush(QBrush(QColor(0, 120, 212)))  # Blue highlight
                self._output_handle.setPen(QPen(QColor(0, 120, 212), 1.5))
        else:
            self.setPen(self._pen)
            # Reset output handle to default appearance
            if hasattr(self, '_output_handle'):
                self._output_handle.setBrush(QBrush(QColor(100, 100, 100)))
                self._output_handle.setPen(QPen(QColor(150, 150, 150), 1))
        # Trigger repaint to show execution state
        self.update()
    
    def set_execution_state(self, state: str):
        """Set execution state and update visual appearance"""
        if state in [self.STATE_IDLE, self.STATE_RUNNING, self.STATE_SUCCESS, self.STATE_FAILED]:
            self._execution_state = state
            self.update_appearance()
    
    def get_execution_state(self) -> str:
        """Get current execution state"""
        return self._execution_state
    
    def set_breakpoint_enabled(self, enabled: bool):
        """Set breakpoint visibility"""
        self._breakpoint_enabled = enabled
        if hasattr(self, '_breakpoint_indicator'):
            self._breakpoint_indicator.setVisible(enabled)
        self.update()
    
    def is_breakpoint_enabled(self) -> bool:
        """Check if breakpoint is enabled"""
        return self._breakpoint_enabled

    def mousePressEvent(self, event):
        # 左鍵在右側 20px 連接區或輸出把手區域啟動拖拽連線
        try:
            if event.button() == Qt.LeftButton:
                local = event.pos()
                rect = self.rect()
                # Check if click is in output handle area or right-side connection zone
                handle_x = rect.width() - 12
                handle_y = rect.height() / 2 - 4
                handle_size = 8
                # Check if click is within handle bounds (handle is 8x8, positioned at handle_x, handle_y)
                in_handle = (handle_x <= local.x() <= handle_x + handle_size and 
                            handle_y <= local.y() <= handle_y + handle_size)
                in_connection_zone = local.x() > rect.width() - 20
                if in_handle or in_connection_zone:
                    if self._editor:
                        scene_pos = self.mapToScene(local)
                        self._editor.start_connection_drag(self.node.id, scene_pos)
                        event.accept()
                        return
        except Exception:
            pass
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        # 拖拽過程更新臨時邊線並提供目標節點高亮
        try:
            if self._editor and self._editor._temp_connection_src_id == self.node.id:
                scene_pos = self.mapToScene(event.pos())
                self._editor.update_connection_drag(scene_pos)
                # 掃描場景下的項目，檢測目標節點，並顯示可/不可連接的邊框顏色
                item = self._editor._scene.itemAt(scene_pos, QTransform())
                target = item
                while target and not isinstance(target, VisualNodeItem):
                    target = target.parentItem() if hasattr(target, 'parentItem') else None
                can = False
                dst_id = None
                if isinstance(target, VisualNodeItem):
                    for nid, node_item in self._editor._node_items.items():
                        if node_item is target:
                            dst_id = nid
                            break
                    can = self._editor._can_connect(self.node.id, dst_id)
                self._editor._update_hover_target(target if isinstance(target, VisualNodeItem) else None, can)
                event.accept()
                return
        except Exception:
            pass
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        # Let the view handle connection completion logic
        # This ensures connections are properly established regardless of which node receives the event
        super().mouseReleaseEvent(event)
    
    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemSelectedChange:
            self.update_appearance()
        elif change == QGraphicsItem.ItemPositionChange:
            try:
                self.node.position = value
                # Notify editor to update edges when node moves
                if self._editor:
                    self._editor._update_all_edges()
            except Exception:
                print("[VisualNodeItem] itemChange update position failed")
                traceback.print_exc()
        return super().itemChange(change, value)
    
    def mouseDoubleClickEvent(self, event):
        # Emit signal when node is double-clicked
        if self._editor:
            self._editor.nodeDoubleClicked.emit(self.node.id, self.node)
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event):
        if not self._editor:
            return super().contextMenuEvent(event)
        menu = QMenu()
        act_edit_comment = menu.addAction("編輯註釋")
        menu.addSeparator()
        # Check if breakpoint is set
        is_breakpoint = hasattr(self._editor, '_breakpoints') and self.node.id in getattr(self._editor, '_breakpoints', set())
        act_breakpoint = menu.addAction("移除斷點" if is_breakpoint else "設定斷點")
        menu.addSeparator()
        act_del = menu.addAction("刪除節點")
        act_rm = menu.addAction("移除連線")
        # QMenu.exec() requires QPoint
        # In PySide6, QGraphicsSceneContextMenuEvent.screenPos() returns QPoint (not QPointF)
        # So we can use it directly without conversion
        chosen = menu.exec(event.screenPos())
        if chosen == act_edit_comment:
            try:
                self._editor._on_edit_node_comment(self.node.id)
            except Exception:
                print("[VisualNodeItem] context edit_comment failed")
                traceback.print_exc()
        elif chosen == act_breakpoint:
            try:
                self._editor.toggle_breakpoint(self.node.id)
            except Exception:
                print("[VisualNodeItem] context toggle_breakpoint failed")
                traceback.print_exc()
        elif chosen == act_del:
            try:
                self._editor.delete_node(self.node.id)
            except Exception:
                print("[VisualNodeItem] context delete_node failed")
                traceback.print_exc()
        elif chosen == act_rm:
            try:
                self._editor.remove_node_connections(self.node.id)
            except Exception:
                print("[VisualNodeItem] context remove_node_connections failed")
                traceback.print_exc()
        else:
            event.ignore()

    def dragEnterEvent(self, event: QDragEnterEvent):
        """Accept image drops on find_image nodes"""
        if self.node.type != 'find_image':
            event.ignore()
            return
        
        mime_data = event.mimeData()
        # Accept image files and image data
        if mime_data.hasUrls():
            # Check if any URL is an image file
            for url in mime_data.urls():
                path = url.toLocalFile()
                if path and any(path.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.bmp', '.gif']):
                    event.acceptProposedAction()
                    return
        elif mime_data.hasImage():
            # Accept image data from clipboard/applications
            event.acceptProposedAction()
            return
        
        event.ignore()

    def dropEvent(self, event: QDropEvent):
        """Handle image drop and register as template"""
        if self.node.type != 'find_image':
            event.ignore()
            return
        
        mime_data = event.mimeData()
        pixmap = None
        
        # Try to load from file URL
        if mime_data.hasUrls():
            for url in mime_data.urls():
                path = url.toLocalFile()
                if path and os.path.exists(path):
                    pixmap = QPixmap(path)
                    if not pixmap.isNull():
                        break
        
        # Try to load from image data
        if pixmap is None or pixmap.isNull():
            if mime_data.hasImage():
                from PySide6.QtGui import QImage
                img_data = mime_data.imageData()
                if isinstance(img_data, QPixmap):
                    pixmap = img_data
                elif isinstance(img_data, QImage):
                    pixmap = QPixmap.fromImage(img_data)
        
        if pixmap and not pixmap.isNull():
            # Emit signal to register the template
            if self._editor:
                self._editor.imageDropped.emit(self.node.id, pixmap)
            event.acceptProposedAction()
        else:
            event.ignore()


class EdgeItem(QGraphicsPathItem):
    """Visual edge connecting two nodes"""
    def __init__(self, src_point: QPointF, dst_point: QPointF, parent=None):
        super().__init__(parent)
        self._src_point = src_point
        self._dst_point = dst_point
        self._update_path()
        # Style the edge
        pen = QPen(QColor(100, 100, 100), 2.0)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        self.setPen(pen)
        self.setZValue(-1)  # Draw edges behind nodes
    
    def _update_path(self):
        """Update the path based on current source and destination points"""
        path = QPainterPath()
        path.moveTo(self._src_point)
        
        # Create a bezier curve for smoother appearance
        dx = self._dst_point.x() - self._src_point.x()
        dy = self._dst_point.y() - self._src_point.y()
        # Control points for bezier curve
        ctrl1 = QPointF(self._src_point.x() + dx * 0.5, self._src_point.y())
        ctrl2 = QPointF(self._dst_point.x() - dx * 0.5, self._dst_point.y())
        path.cubicTo(ctrl1, ctrl2, self._dst_point)
        
        self.setPath(path)
    
    def set_source_point(self, point: QPointF):
        """Update source point and refresh path"""
        self._src_point = point
        self._update_path()
    
    def set_destination_point(self, point: QPointF):
        """Update destination point and refresh path"""
        self._dst_point = point
        self._update_path()
    
    def set_points(self, src_point: QPointF, dst_point: QPointF):
        """Update both points and refresh path"""
        self._src_point = src_point
        self._dst_point = dst_point
        self._update_path()


class CommentItem(QGraphicsRectItem):
    """Editable comment item that can attach to nodes or exist independently"""
    def __init__(self, text: str = "", position: QPointF = QPointF(0, 0), editor=None, node_id: Optional[str] = None):
        super().__init__(0, 0, 200, 100)
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        
        self._editor = editor
        self._node_id = node_id  # Optional: attach to a specific node
        self._text = text
        self.setPos(position)
        
        # Yellow semi-transparent background
        self._brush = QBrush(QColor(255, 255, 200, 200))  # Light yellow with transparency
        self._pen = QPen(QColor(200, 200, 100), 1.5)
        self._selected_pen = QPen(QColor('#0078d4'), 2.0)
        
        # Text item for display
        self._text_item = QGraphicsTextItem(self)
        self._text_item.setPlainText(text or "點擊編輯註釋...")
        self._text_item.setPos(5, 5)
        self._text_item.setTextWidth(self.rect().width() - 10)
        self._text_item.setDefaultTextColor(QColor(51, 51, 51))
        
        # Editable text widget (shown when editing)
        self._text_edit_proxy = None
        self._text_edit = None
        self._editing = False
        
        self.update_appearance()
    
    def update_appearance(self):
        """Update visual appearance based on selection state"""
        if self.isSelected():
            self.setPen(self._selected_pen)
        else:
            self.setPen(self._pen)
        self.setBrush(self._brush)
    
    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemSelectedChange:
            self.update_appearance()
        elif change == QGraphicsItem.ItemPositionChange:
            # Update node comment position if attached to a node
            if self._editor and self._node_id:
                node = self._editor._find_node(self._node_id)
                if node:
                    # Store relative position to node
                    if self._editor._node_items.get(self._node_id):
                        node_item = self._editor._node_items[self._node_id]
                        rel_pos = value - node_item.pos()
                        # Could store this in node params if needed
        return super().itemChange(change, value)
    
    def mouseDoubleClickEvent(self, event):
        """Start editing on double-click"""
        if not self._editing:
            self.start_editing()
        super().mouseDoubleClickEvent(event)
    
    def start_editing(self):
        """Switch to edit mode"""
        if self._editing:
            return
        self._editing = True
        
        # Create text edit widget
        from PySide6.QtWidgets import QTextEdit
        self._text_edit = QTextEdit()
        self._text_edit.setPlainText(self._text)
        self._text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #ffffff;
                border: 2px solid #0078d4;
                border-radius: 4px;
                padding: 4px;
            }
        """)
        
        # Create proxy widget
        self._text_edit_proxy = QGraphicsProxyWidget(self)
        self._text_edit_proxy.setWidget(self._text_edit)
        self._text_edit_proxy.setPos(5, 5)
        self._text_edit_proxy.resize(self.rect().width() - 10, self.rect().height() - 10)
        
        # Hide text item
        self._text_item.setVisible(False)
        
        # Focus and select all
        self._text_edit.setFocus()
        self._text_edit.selectAll()
        
        # Store original methods
        original_focus_out = self._text_edit.focusOutEvent
        original_key_press = self._text_edit.keyPressEvent
        
        # Override methods
        def focus_out_wrapper(e):
            self.finish_editing()
            original_focus_out(e)
        
        def key_press_wrapper(e):
            if e.key() == Qt.Key_Return and e.modifiers() & Qt.ControlModifier:
                self.finish_editing()
            elif e.key() == Qt.Key_Escape:
                self.cancel_editing()
            else:
                original_key_press(e)
        
        self._text_edit.focusOutEvent = focus_out_wrapper
        self._text_edit.keyPressEvent = key_press_wrapper
    
    
    def finish_editing(self):
        """Finish editing and save text"""
        if not self._editing:
            return
        
        new_text = self._text_edit.toPlainText()
        self._text = new_text
        
        # Update node comment if attached
        if self._editor and self._node_id:
            node = self._editor._find_node(self._node_id)
            if node:
                node.comment = new_text if new_text else None
                if self._editor:
                    self._editor.commentChanged.emit(self._node_id, new_text)
                    self._editor._push_history()
                    self._editor._emit_changed()
        
        # Clean up edit widget
        if self._text_edit_proxy:
            self._text_edit_proxy.setWidget(None)
            self._text_edit_proxy = None
        self._text_edit = None
        self._editing = False
        
        # Update text item
        self._text_item.setPlainText(new_text if new_text else "點擊編輯註釋...")
        self._text_item.setVisible(True)
    
    def cancel_editing(self):
        """Cancel editing without saving"""
        if not self._editing:
            return
        
        # Clean up edit widget
        if self._text_edit_proxy:
            self._text_edit_proxy.setWidget(None)
            self._text_edit_proxy = None
        self._text_edit = None
        self._editing = False
        
        # Restore text item
        self._text_item.setVisible(True)
    
    def set_text(self, text: str):
        """Set comment text programmatically"""
        self._text = text
        self._text_item.setPlainText(text if text else "點擊編輯註釋...")
        # Update node if attached
        if self._editor and self._node_id:
            node = self._editor._find_node(self._node_id)
            if node:
                node.comment = text if text else None
    
    def get_text(self) -> str:
        """Get comment text"""
        return self._text
    
    def paint(self, painter: QPainter, option, widget=None):
        """Custom paint to draw rounded rectangle background"""
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(self.brush())
        painter.setPen(self.pen())
        rect = self.rect()
        painter.drawRoundedRect(rect, 6, 6)


class ScriptGraphicsView(QGraphicsView):
    """Custom QGraphicsView that handles connect mode for VisualScriptEditor"""
    def __init__(self, scene, editor, parent=None):
        super().__init__(scene, parent)
        self._editor = editor
        self._panning = False
        self._last_pan_pos = None
        self._scale = 1.0  # Track scale in the view itself
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        try:
            self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        except Exception:
            print("[ScriptGraphicsView] setResizeAnchor failed")
            traceback.print_exc()
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MiddleButton or (event.button() == Qt.RightButton and event.modifiers() & Qt.ControlModifier):
            self._panning = True
            self._last_pan_pos = event.position()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)
    
    def mouseReleaseEvent(self, event):
        if self._panning:
            self._panning = False
            self.setCursor(Qt.ArrowCursor)
            event.accept()
            # Skip _on_scene_view_mouse_release() for pan operations since they don't modify node positions
            return
        
        # Store connection state before event propagation
        # Record the source node ID before event propagation to determine if connection was active
        connection_was_active = False
        src_id_before = None
        if self._editor and self._editor._temp_connection_src_id:
            connection_was_active = True
            src_id_before = self._editor._temp_connection_src_id
        
        super().mouseReleaseEvent(event)
        self._editor._on_scene_view_mouse_release()
        
        # Handle connection completion at view level based on release position
        # This ensures connections work regardless of which node receives the mouse release event
        try:
            if connection_was_active and self._editor and self._editor._temp_connection_src_id:
                # Connection is still active, check if mouse was released over a target node
                # Convert event position to scene coordinates
                scene_pos = self.mapToScene(event.position().toPoint())
                
                # Find the item at the release position
                item = self._editor._scene.itemAt(scene_pos, QTransform())
                
                # Walk up the parent chain to find a VisualNodeItem
                target_node_item = None
                while item and not isinstance(item, VisualNodeItem):
                    item = item.parentItem() if hasattr(item, 'parentItem') else None
                
                # If we found a VisualNodeItem, try to get its node ID
                dst_id = None
                if isinstance(item, VisualNodeItem):
                    # Find the node ID from _node_items
                    for nid, node_item in self._editor._node_items.items():
                        if node_item is item:
                            dst_id = nid
                            break
                
                # If we found a valid target node that's different from source, and can connect
                if dst_id and dst_id != src_id_before and self._editor._can_connect(src_id_before, dst_id):
                    # Complete the connection
                    self._editor.finish_connection_drag(dst_id)
                else:
                    # No valid target found, or cannot connect, cancel the connection
                    self._editor.finish_connection_drag(None)
        except Exception:
            # On any error, cancel the connection to prevent stuck state
            try:
                if self._editor and self._editor._temp_connection_src_id:
                    self._editor.finish_connection_drag(None)
            except Exception:
                pass

    def mouseMoveEvent(self, event):
        if self._panning and self._last_pan_pos is not None:
            delta = event.position() - self._last_pan_pos
            # Use view transform for smoother panning
            try:
                hbar = self.horizontalScrollBar()
                vbar = self.verticalScrollBar()
                hbar.setValue(hbar.value() - int(delta.x()))
                vbar.setValue(vbar.value() - int(delta.y()))
            except Exception:
                print("[ScriptGraphicsView] panning scroll failed")
                traceback.print_exc()
            self._last_pan_pos = event.position()
            event.accept()
            return
        # 在視圖層級更新拖拽臨時邊線位置
        # This handles connection drag when mouse moves over empty scene areas
        # Node-level mouseMoveEvent handles drag when mouse moves over nodes
        try:
            if self._editor and self._editor._temp_connection_src_id:
                scene_pos = self.mapToScene(event.position().toPoint())
                self._editor.update_connection_drag(scene_pos)
                # Also update hover target by checking what item is under the mouse
                item = self._editor._scene.itemAt(scene_pos, QTransform())
                target = item
                while target and not isinstance(target, VisualNodeItem):
                    target = target.parentItem() if hasattr(target, 'parentItem') else None
                if isinstance(target, VisualNodeItem):
                    # Find source and target node IDs
                    src_id = self._editor._temp_connection_src_id
                    dst_id = None
                    for nid, node_item in self._editor._node_items.items():
                        if node_item is target:
                            dst_id = nid
                            break
                    if dst_id:
                        can = self._editor._can_connect(src_id, dst_id)
                        self._editor._update_hover_target(target, can)
                    else:
                        self._editor._update_hover_target(None, False)
                else:
                    self._editor._update_hover_target(None, False)
        except Exception:
            pass
        super().mouseMoveEvent(event)

    def wheelEvent(self, event):
        """Handle mouse wheel events for zooming with proper scale tracking and clamping"""
        dy = event.angleDelta().y()
        if dy == 0:
            super().wheelEvent(event)
            return
        
        # Calculate zoom factor (1.15 provides smoother zoom steps)
        factor = 1.15 if dy > 0 else 1.0 / 1.15
        
        # Clamp scale between sensible limits (0.25x to 3.0x)
        min_scale = 0.25
        max_scale = 3.0
        new_scale = max(min_scale, min(max_scale, self._scale * factor))
        
        # Only apply if scale actually changed
        if abs(new_scale - self._scale) > 1e-6:
            scale_factor = new_scale / max(1e-9, self._scale)
            try:
                # Apply scaling to view transform
                self.scale(scale_factor, scale_factor)
                self._scale = new_scale
                # Keep editor's scale in sync for compatibility
                self._editor._scale = new_scale
            except Exception:
                print("[ScriptGraphicsView] wheel scaling failed")
                traceback.print_exc()
        
        event.accept()


class VisualScriptEditor(QWidget):
    nodeSelected = Signal(str, VisualNode)
    nodeDoubleClicked = Signal(str, VisualNode)
    scriptChanged = Signal(VisualScript)
    executeRequested = Signal()
    connectionRejected = Signal(str, str)  # src_id, reason
    nodeParamsChanged = Signal(str, VisualNode)  # node_id, node - emitted when node params change
    imageDropped = Signal(str, QPixmap)  # node_id, pixmap - emitted when image is dropped on a find_image node
    commentChanged = Signal(str, str)  # node_id, comment_text - emitted when node comment changes
    
    # Node type definitions (modernized: no emoji, neutral styling)
    NODE_TYPES = [
        {"id": "click", "name": "點擊", "color": "#B0B8C4"},
        {"id": "key", "name": "按鍵", "color": "#C4B8A8"},
        {"id": "sleep", "name": "等待", "color": "#B8A8C4"},
        {"id": "find_color", "name": "找顏色", "color": "#C4A8A8"},
        {"id": "condition", "name": "條件", "color": "#A8B0C4"},
        {"id": "loop", "name": "迴圈", "color": "#B8B0A8"},
        {"id": "find_image", "name": "找圖片", "color": "#A8C4B0"},
        {"id": "verify_image_color", "name": "驗證圖片顏色", "color": "#C4B0A8"}
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self._script: VisualScript = VisualScript()
        self._node_items: Dict[str, VisualNodeItem] = {}
        self._edge_items: Dict[tuple[str, str], EdgeItem] = {}  # (src_id, dst_id) -> EdgeItem
        self._comment_items: Dict[str, CommentItem] = {}  # node_id -> CommentItem (for node-attached comments)
        self._standalone_comments: list[CommentItem] = []  # Standalone comments not attached to nodes
        self._scale = 1.0
        self._temp_connection_src_id: Optional[str] = None
        self._temp_connection_edge: Optional[EdgeItem] = None
        self._hover_target: Optional[VisualNodeItem] = None
        self._history_stack: list[dict] = []
        self._history_index: int = -1
        self._last_mouse_scene_pos: Optional[QPointF] = None
        self._last_node_positions: Dict[str, QPointF] = {}  # Track node positions to avoid unnecessary history pushes
        self._breakpoints: set[str] = set()  # Set of node IDs with breakpoints
        self._available_templates: set[str] = set()  # Set of available template names for validation
        self._build_controls()
        try:
            self._scene.selectionChanged.connect(self._on_selection_changed)
        except Exception:
            print("[VisualScriptEditor] connect selectionChanged failed")
            traceback.print_exc()

    def _build_controls(self):
        # Create a container for the toolbar
        toolbar = QWidget(self)
        toolbar.setFixedHeight(40)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(8, 2, 8, 2)
        toolbar_layout.setSpacing(4)
        
        # Toolbar primary action
        self._play_btn = QPushButton("執行")
        self._play_btn.clicked.connect(self.executeRequested.emit)
        
        # Create node type buttons (neutral labels)
        node_buttons = [(nt["name"], nt["id"]) for nt in self.NODE_TYPES]
        
        # Add buttons to toolbar
        toolbar_layout.addWidget(self._play_btn)
        toolbar_layout.addSpacing(10)
        
        for text, node_type in node_buttons:
            btn = QPushButton(text)
            # Apply neutral gray styling to all node-type buttons
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #f0f0f0;
                    border: 1px solid #d0d0d0;
                    border-radius: 6px;
                    padding: 6px 12px;
                    color: #333333;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #e8e8e8;
                    border: 1px solid #0078d4;
                }
                QPushButton:pressed {
                    background-color: #e0e0e0;
                }
            """)
            btn.clicked.connect(lambda checked, t=node_type: self.add_node(t))
            toolbar_layout.addWidget(btn)
        
        toolbar_layout.addSpacing(10)
        
        # Add comment button
        btn_add_comment = QPushButton("添加註釋")
        btn_add_comment.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                color: #333333;
                border: 1px solid #dcdfe6;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
                border: 1px solid #0078d4;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
        """)
        btn_add_comment.clicked.connect(self._on_add_comment)
        toolbar_layout.addWidget(btn_add_comment)
        
        toolbar_layout.addStretch()
        
        # Remove explicit connect mode toggle; drag-to-connect is used
        
        # Add toolbar to main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(toolbar)
        
        # Create single scene view - this is the only QGraphicsView
        self._scene_view = ScriptGraphicsView(self._scene, self, self)
        self._scene_view.setRenderHint(QPainter.Antialiasing, True)
        self._scene_view.setDragMode(QGraphicsView.RubberBandDrag)
        self._scene_view.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self._scene_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self._scene_view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        # Sync initial scale
        self._scene_view._scale = self._scale
        
        layout.addWidget(self._scene_view)
        
        # Set minimum size
        self.setMinimumSize(800, 600)

        # 綁定撤銷/重做快捷鍵
        try:
            QShortcut(QKeySequence("Ctrl+Z"), self, self.undo)
            QShortcut(QKeySequence("Ctrl+Shift+Z"), self, self.redo)
            QShortcut(QKeySequence("Ctrl+Space"), self, self._open_search_panel)
        except Exception:
            pass
    
    def start_connection_drag(self, src_node_id: str, start_scene_pos: QPointF):
        try:
            self._temp_connection_src_id = src_node_id
            src_item = self._node_items.get(src_node_id)
            if not src_item:
                return
            # Connection point should align with output handle center (handle is 8px wide, positioned 12px from right edge)
            # Handle center is at: rect.width() - 12 + 4 = rect.width() - 8
            sp = src_item.scenePos() + QPointF(src_item.rect().width() - 8, src_item.rect().height() / 2)
            self._temp_connection_edge = EdgeItem(sp, start_scene_pos)
            pen = QPen(QColor(150, 150, 150), 1.5, Qt.DashLine)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            self._temp_connection_edge.setPen(pen)
            self._scene.addItem(self._temp_connection_edge)
        except Exception:
            pass

    def update_connection_drag(self, scene_pos: QPointF):
        try:
            if self._temp_connection_edge:
                self._temp_connection_edge.set_destination_point(scene_pos)
        except Exception:
            pass

    def finish_connection_drag(self, dst_node_id: Optional[str]):
        """Finish connection drag and create connection if valid target node provided"""
        try:
            # Clean up temporary connection edge
            if self._temp_connection_edge:
                try:
                    self._scene.removeItem(self._temp_connection_edge)
                except Exception:
                    pass
            self._temp_connection_edge = None
            # 清除 hover 樣式
            self._update_hover_target(None, False)
            src_id = self._temp_connection_src_id
            self._temp_connection_src_id = None
            # Create connection if valid source and destination nodes provided
            if src_id and dst_node_id and src_id != dst_node_id:
                self.connect_nodes(src_id, dst_node_id)
        except Exception as e:
            print(f"[VisualScriptEditor] finish_connection_drag failed: {e}")
            traceback.print_exc()

    def _update_hover_target(self, item: Optional[VisualNodeItem], can_connect: bool):
        # 更新拖拽時的目標節點高亮（綠/紅邊），並重置上一個目標
        try:
            if self._hover_target and self._hover_target is not item:
                self._hover_target.update_appearance()
            self._hover_target = item
            if item:
                pen = QPen(QColor(76, 175, 80), 2) if can_connect else QPen(QColor(244, 67, 54), 2)
                item.setPen(pen)
                # Also highlight output handle when node is hover target
                if hasattr(item, '_output_handle'):
                    if can_connect:
                        item._output_handle.setBrush(QBrush(QColor(76, 175, 80)))
                        item._output_handle.setPen(QPen(QColor(76, 175, 80), 2))
                    else:
                        item._output_handle.setBrush(QBrush(QColor(244, 67, 54)))
                        item._output_handle.setPen(QPen(QColor(244, 67, 54), 2))
        except Exception:
            pass

    def _can_connect(self, src_id: Optional[str], dst_id: Optional[str]) -> bool:
        try:
            if not src_id or not dst_id or src_id == dst_id:
                return False
            src_node = self._find_node(src_id)
            if not src_node:
                return False
            if src_node.type == "condition":
                nt = src_node.params.get("next_true", "")
                nf = src_node.params.get("next_false", "")
                return not (nt and nf)
            if src_node.type == "loop":
                nb = src_node.params.get("next_body", "")
                na = src_node.params.get("next_after", "")
                return not (nb and na)
            return src_id not in self._script.connections
        except Exception:
            return False

    def load_script(self, script: VisualScript):
        self._script = script
        try:
            self._scene.blockSignals(True)
        except Exception:
            pass
        self._scene.clear()
        self._node_items.clear()
        self._edge_items.clear()
        self._comment_items.clear()
        self._standalone_comments.clear()
        
        for n in script.nodes:
            item = VisualNodeItem(n, self)
            self._scene.addItem(item)
            self._node_items[n.id] = item
            
            # Load comment if node has one
            if n.comment:
                comment_item = CommentItem(n.comment, n.position + QPointF(200, 0), self, n.id)
                self._scene.addItem(comment_item)
                self._comment_items[n.id] = comment_item
        
        # Sync breakpoint indicators after loading nodes
        self._sync_breakpoint_indicators()
        
        self._rebuild_edges_from_model()
        try:
            self._scene.blockSignals(False)
        except Exception:
            pass
        # Reset history stack when switching scripts
        # Clear history and push initial state to prevent undo/redo from affecting other scripts
        self._history_stack = []
        self._history_index = -1
        # Initialize last node positions for change detection
        self._last_node_positions = {n.id: n.position for n in script.nodes}
        self._push_history()  # Push initial state of the loaded script
        self._emit_changed()
        
    def add_node(self, node_type: str, at: Optional[QPointF] = None) -> VisualNode:
        # Generate unique node ID by checking existing IDs
        existing_ids = {node.id for node in self._script.nodes}
        counter = 1
        while True:
            nid = f"node_{counter}"
            if nid not in existing_ids:
                break
            counter += 1
        
        n = VisualNode(id=nid, type=node_type, position=at or QPointF(40, 40))
        self._script.nodes.append(n)
        item = VisualNodeItem(n, self)
        self._scene.addItem(item)
        self._node_items[n.id] = item
        # Initialize position tracking to prevent duplicate history push on first mouse release
        self._last_node_positions[n.id] = n.position
        self._push_history()
        self._emit_changed()
        return n

    def connect_nodes(self, src_id: str, dst_id: str):
        # Check if source node exists and get its type
        src_node = self._find_node(src_id)
        if not src_node:
            return
        
        # Handle condition and loop nodes specially - map connections to next_* parameters
        if src_node.type == "condition":
            # For condition nodes, map connections to next_true and next_false
            next_true = src_node.params.get("next_true", "")
            next_false = src_node.params.get("next_false", "")
            
            if not next_true:
                src_node.params["next_true"] = dst_id
            elif not next_false:
                src_node.params["next_false"] = dst_id
            else:
                # Both already set - emit signal to inform user
                reason = "條件節點的 True/False 走向已設定，請先清除參數"
                self.connectionRejected.emit(src_id, reason)
                return
            # Emit signal to notify that node params changed
            self.nodeParamsChanged.emit(src_id, src_node)
            self._push_history()  # Record state for undo/redo
            self._rebuild_edges_from_model()
            self._emit_changed()
            return
        
        if src_node.type == "loop":
            # For loop nodes, map connections to next_body and next_after
            next_body = src_node.params.get("next_body", "")
            next_after = src_node.params.get("next_after", "")
            
            if not next_body:
                src_node.params["next_body"] = dst_id
            elif not next_after:
                src_node.params["next_after"] = dst_id
            else:
                # Both already set - emit signal to inform user
                reason = "迴圈節點的迴圈體/迴圈後已設定，請先清除參數"
                self.connectionRejected.emit(src_id, reason)
                return
            # Emit signal to notify that node params changed
            self.nodeParamsChanged.emit(src_id, src_node)
            self._push_history()  # Record state for undo/redo
            self._rebuild_edges_from_model()
            self._emit_changed()
            return
        
        # For other node types, use the standard connection mechanism
        # Guard against silently overwriting existing connections
        if src_id in self._script.connections:
            # Connection already exists - emit signal to inform user
            reason = "來源已有連線，無法覆寫"
            self.connectionRejected.emit(src_id, reason)
            return
        
        self._script.connections[src_id] = dst_id
        self._push_history()
        self._rebuild_edges_from_model()
        self._emit_changed()

    def wheelEvent(self, event):
        # Forward wheel events to the scene view for zooming
        # Zooming is fully handled by ScriptGraphicsView.wheelEvent, which manages
        # scale limits (0.25-3.0) and transform updates. This method should only
        # forward the event and accept it, without performing additional scaling.
        # Avoid calling super().wheelEvent(event) to prevent double zooming.
        self._scene_view.wheelEvent(event)
        event.accept()

    def _on_scene_view_mouse_release(self):
        """Called after scene view processes mouse release"""
        # Track which nodes actually moved
        nodes_moved = False
        for nid, item in self._node_items.items():
            node = self._find_node(nid)
            if node:
                new_pos = item.pos()
                old_pos = self._last_node_positions.get(nid)
                # Check if position actually changed
                if old_pos is None or old_pos != new_pos:
                    node.position = new_pos
                    self._last_node_positions[nid] = new_pos
                    nodes_moved = True
        
        # Only update edges, push history, and emit changed if nodes actually moved
        if nodes_moved:
            self._update_all_edges()
            self._push_history()
            self._emit_changed()
        
        # Always emit node selection (even if no movement)
        sel = self._selected_node_id()
        if sel:
            n = self._find_node(sel)
            if n:
                self.nodeSelected.emit(sel, n)

    def _on_selection_changed(self):
        try:
            sel = self._selected_node_id()
            if sel:
                n = self._find_node(sel)
                if n:
                    try:
                        self.nodeSelected.emit(sel, n)
                    except Exception:
                        pass
        finally:
            self._emit_changed()


    def _selected_node_id(self) -> Optional[str]:
        for nid, item in list(self._node_items.items()):
            try:
                if item and item.scene() and item.isSelected():
                    return nid
            except RuntimeError:
                # 該圖元已被刪除，跳過
                continue
        return None
    
    def get_selected_nodes(self) -> List[VisualNode]:
        """Get all currently selected nodes"""
        selected = []
        for nid, item in list(self._node_items.items()):
            try:
                if item and item.scene() and item.isSelected():
                    node = self._find_node(nid)
                    if node:
                        selected.append(node)
            except RuntimeError:
                # 該圖元已被刪除，跳過
                continue
        return selected

    def _find_node(self, nid: str) -> Optional[VisualNode]:
        for n in self._script.nodes:
            if n.id == nid:
                return n
        return None

    def export_script(self) -> VisualScript:
        return self._script

    def highlight_active_node(self, node_id: str):
        """Highlight the active node by setting selection state, which triggers VisualNodeItem.update_appearance"""
        item = self._node_items.get(node_id)
        if item:
            # Use selection state instead of direct pen manipulation
            # This ensures VisualNodeItem.update_appearance remains the single source of truth
            item.setSelected(True)
            # Center view on the active node for better UX
            self._scene_view.centerOn(item)
        
        # Deselect all other nodes
        for nid, it in self._node_items.items():
            if nid != node_id:
                it.setSelected(False)
    
    def set_node_execution_state(self, node_id: str, state: str):
        """Set execution state for a specific node"""
        item = self._node_items.get(node_id)
        if item:
            item.set_execution_state(state)
    
    def clear_execution_states(self):
        """Clear execution states for all nodes"""
        for item in self._node_items.values():
            item.set_execution_state(VisualNodeItem.STATE_IDLE)
    
    def _sync_breakpoint_indicators(self):
        """Sync visual breakpoint indicators with _breakpoints set"""
        for node_id, item in self._node_items.items():
            item.set_breakpoint_enabled(node_id in self._breakpoints)
    
    def toggle_breakpoint(self, node_id: str):
        """Toggle breakpoint on a node"""
        if node_id in self._breakpoints:
            self._breakpoints.remove(node_id)
        else:
            self._breakpoints.add(node_id)
        
        # Update visual breakpoint indicator
        item = self._node_items.get(node_id)
        if item:
            item.set_breakpoint_enabled(node_id in self._breakpoints)
        
        # Update edges to reflect any changes
        self._update_all_edges()
    
    def get_breakpoints(self) -> set[str]:
        """Get set of node IDs with breakpoints"""
        return self._breakpoints.copy()
    
    def set_available_templates(self, template_names: set[str]):
        """
        Set available template names for validation.
        This should be called by MainWindow after sidebar is initialized.
        
        Args:
            template_names: Set of template names available from ResourceSidebar
        """
        self._available_templates = template_names.copy()
    
    def validate_script(self) -> List[tuple[str, str]]:
        """
        Validate script and return list of issues.
        Returns list of (node_id, issue_description) tuples.
        """
        issues = []
        
        # Check for isolated nodes (no connections and not a starting node)
        if not self._script.nodes:
            issues.append(("", "腳本沒有任何節點"))
            return issues
        
        starting_node_id = self._script.nodes[0].id if self._script.nodes else None
        connected_nodes = set()
        connected_nodes.add(starting_node_id)
        
        # Collect all connected nodes
        for src_id, dst_id in self._script.connections.items():
            connected_nodes.add(src_id)
            connected_nodes.add(dst_id)
        
        # Check condition nodes
        for node in self._script.nodes:
            if node.type == "condition":
                next_true = node.params.get("next_true", "")
                next_false = node.params.get("next_false", "")
                if not next_true:
                    issues.append((node.id, "條件節點缺少 True 走向"))
                if not next_false:
                    issues.append((node.id, "條件節點缺少 False 走向"))
                if next_true:
                    connected_nodes.add(next_true)
                if next_false:
                    connected_nodes.add(next_false)
        
        # Check loop nodes
        for node in self._script.nodes:
            if node.type == "loop":
                next_body = node.params.get("next_body", "")
                next_after = node.params.get("next_after", "")
                if not next_body:
                    issues.append((node.id, "迴圈節點缺少迴圈體"))
                if not next_after:
                    issues.append((node.id, "迴圈節點缺少迴圈後"))
                if next_body:
                    connected_nodes.add(next_body)
                if next_after:
                    connected_nodes.add(next_after)
        
        # Check for isolated nodes
        for node in self._script.nodes:
            if node.id not in connected_nodes and node.id != starting_node_id:
                issues.append((node.id, "孤立節點（沒有連線）"))
        
        # Check for unknown template names in find_image and verify_image_color nodes
        # Use injected available_templates set (set via set_available_templates())
        available_templates = self._available_templates.copy()
        try:
            from ..core.targets import TARGET_DEFINITIONS
            available_templates.update(TARGET_DEFINITIONS.keys())
        except Exception:
            pass
        
        for node in self._script.nodes:
            if node.type in ["find_image", "verify_image_color"]:
                template_name = node.params.get("template_name", "")
                if template_name and template_name not in available_templates:
                    issues.append((node.id, f"未知的模板名稱: {template_name}"))
        
        # Check for obvious infinite cycles (simple check: node pointing to itself)
        for src_id, dst_id in self._script.connections.items():
            if src_id == dst_id:
                issues.append((src_id, "節點連線到自己（可能造成無限迴圈）"))
        
        return issues

    def _create_edge(self, src_id: str, dst_id: str):
        """Create or update an edge between two nodes"""
        if not hasattr(self, '_edge_items'):
            self._edge_items = {}
        if src_id not in self._node_items or dst_id not in self._node_items:
            return
        
        edge_key = (src_id, dst_id)
        if edge_key in self._edge_items:
            # Edge already exists, just update it
            self._update_edge(edge_key)
            return
        
        # Create new edge
        src_item = self._node_items[src_id]
        dst_item = self._node_items[dst_id]
        # Connection points should align with output handle centers (handle is 8px wide, positioned 12px from right edge)
        # Handle center is at: rect.width() - 12 + 4 = rect.width() - 8
        src_point = src_item.scenePos() + QPointF(src_item.rect().width() - 8, src_item.rect().height() / 2)
        dst_point = dst_item.scenePos() + QPointF(dst_item.rect().width() - 8, dst_item.rect().height() / 2)
        
        edge = EdgeItem(src_point, dst_point)
        self._scene.addItem(edge)
        self._edge_items[edge_key] = edge
    
    def _update_edge(self, edge_key: tuple[str, str]):
        """Update an existing edge's position"""
        src_id, dst_id = edge_key
        if src_id not in self._node_items or dst_id not in self._node_items:
            return
        
        edge = self._edge_items.get(edge_key)
        if not edge:
            return
        
        src_item = self._node_items[src_id]
        dst_item = self._node_items[dst_id]
        # Connection points should align with output handle centers (handle is 8px wide, positioned 12px from right edge)
        # Handle center is at: rect.width() - 12 + 4 = rect.width() - 8
        src_point = src_item.scenePos() + QPointF(src_item.rect().width() - 8, src_item.rect().height() / 2)
        dst_point = dst_item.scenePos() + QPointF(dst_item.rect().width() - 8, dst_item.rect().height() / 2)
        edge.set_points(src_point, dst_point)
    
    def _update_all_edges(self):
        """Update all edge positions based on current node positions"""
        if not hasattr(self, '_edge_items'):
            self._edge_items = {}
        try:
            self._scene.setUpdatesEnabled(False)
        except Exception:
            pass
        for edge_key in list(self._edge_items.keys()):
            self._update_edge(edge_key)
        try:
            self._scene.setUpdatesEnabled(True)
        except Exception:
            pass
    
    def _emit_changed(self):
        self.scriptChanged.emit(self._script)
    
    def _on_add_comment(self):
        """Add a standalone comment at the center of the viewport"""
        try:
            center_pos = self._scene_view.mapToScene(self._scene_view.viewport().rect().center())
            comment_item = CommentItem("", center_pos, self, None)
            self._scene.addItem(comment_item)
            self._standalone_comments.append(comment_item)
            comment_item.start_editing()
            self._push_history()
            self._emit_changed()
        except Exception:
            print("[VisualScriptEditor] _on_add_comment failed")
            traceback.print_exc()
    
    def _on_edit_node_comment(self, node_id: str):
        """Edit or create comment for a node"""
        try:
            node = self._find_node(node_id)
            if not node:
                return
            
            # If comment item already exists, start editing it
            if node_id in self._comment_items:
                comment_item = self._comment_items[node_id]
                comment_item.start_editing()
                return
            
            # Create new comment item
            node_item = self._node_items.get(node_id)
            if node_item:
                # Position comment to the right of the node
                comment_pos = node_item.pos() + QPointF(node_item.rect().width() + 20, 0)
                comment_item = CommentItem(node.comment or "", comment_pos, self, node_id)
                self._scene.addItem(comment_item)
                self._comment_items[node_id] = comment_item
                comment_item.start_editing()
                self._push_history()
                self._emit_changed()
        except Exception:
            print("[VisualScriptEditor] _on_edit_node_comment failed")
            traceback.print_exc()

    def delete_node(self, node_id: str):
        node = self._find_node(node_id)
        if not node:
            return
        try:
            try:
                self._scene.blockSignals(True)
            except Exception:
                pass
            if node_id in self._node_items:
                item = self._node_items.pop(node_id)
                self._scene.removeItem(item)
            # Remove associated comment if exists
            if node_id in self._comment_items:
                comment_item = self._comment_items.pop(node_id)
                self._scene.removeItem(comment_item)
            # Clean up position tracking to prevent memory leak
            if node_id in self._last_node_positions:
                self._last_node_positions.pop(node_id)
            # 移除舊有連接點顯示（已不再使用）
        except Exception:
            print("[VisualScriptEditor] delete_node UI remove failed")
            traceback.print_exc()
        self.remove_node_connections(node_id, push_history=False)
        try:
            self._script.nodes = [n for n in self._script.nodes if n.id != node_id]
        except Exception:
            print("[VisualScriptEditor] delete_node update model failed")
            traceback.print_exc()
        # Rebuild edges after all modifications (connections and node removal) are complete
        self._rebuild_edges_from_model()
        self._push_history()
        try:
            self._scene.blockSignals(False)
        except Exception:
            pass
        self._emit_changed()

    def remove_node_connections(self, node_id: str, push_history: bool = True):
        """
        Remove all connections involving the specified node.
        
        Args:
            node_id: ID of the node whose connections should be removed
            push_history: If True, push current state to history for undo/redo.
                         Set to False if the caller will push history separately
                         (e.g., when called from delete_node which pushes history after all modifications).
        """
        try:
            self._script.connections = {s: d for s, d in self._script.connections.items() if s != node_id and d != node_id}
        except Exception:
            print("[VisualScriptEditor] remove_node_connections update connections failed")
            traceback.print_exc()
        try:
            for n in self._script.nodes:
                if n.type == "condition":
                    if n.params.get("next_true") == node_id:
                        n.params["next_true"] = ""
                    if n.params.get("next_false") == node_id:
                        n.params["next_false"] = ""
                elif n.type == "loop":
                    if n.params.get("next_body") == node_id:
                        n.params["next_body"] = ""
                    if n.params.get("next_after") == node_id:
                        n.params["next_after"] = ""
        except Exception:
            print("[VisualScriptEditor] remove_node_connections update params failed")
            traceback.print_exc()
        if push_history:
            self._push_history()  # Record state for undo/redo
            # Only rebuild edges and emit changes when push_history=True
            # When push_history=False, the caller (e.g., delete_node) will handle
            # edge rebuilding and change emission after all modifications are complete
            self._rebuild_edges_from_model()
            self._emit_changed()

    def _rebuild_edges_from_model(self):
        try:
            for edge_key, edge in list(self._edge_items.items()):
                if edge:
                    try:
                        self._scene.removeItem(edge)
                    except Exception:
                        print("[VisualScriptEditor] rebuild remove edge failed")
                        traceback.print_exc()
            self._edge_items.clear()
        except Exception:
            print("[VisualScriptEditor] rebuild clear edges failed")
            traceback.print_exc()
        try:
            for src_id, dst_id in self._script.connections.items():
                self._create_edge(src_id, dst_id)
            for node in self._script.nodes:
                if node.type == "condition":
                    nt = node.params.get("next_true", "")
                    nf = node.params.get("next_false", "")
                    if nt:
                        self._create_edge(node.id, nt)
                    if nf:
                        self._create_edge(node.id, nf)
                elif node.type == "loop":
                    nb = node.params.get("next_body", "")
                    na = node.params.get("next_after", "")
                    if nb:
                        self._create_edge(node.id, nb)
                    if na:
                        self._create_edge(node.id, na)
        except Exception:
            print("[VisualScriptEditor] rebuild create edges failed")
            traceback.print_exc()

    def _push_history(self):
        # 推送腳本狀態快照以支援撤銷/重做
        try:
            snap = self._script.to_dict()
            # 截斷未來分支
            if self._history_index < len(self._history_stack) - 1:
                self._history_stack = self._history_stack[:self._history_index + 1]
            self._history_stack.append(snap)
            self._history_index = len(self._history_stack) - 1
        except Exception:
            pass

    def _restore_history(self, idx: int):
        try:
            if 0 <= idx < len(self._history_stack):
                data = self._history_stack[idx]
                vs = VisualScript.from_dict(data)
                # 用不觸發歷史的方式重建場景
                try:
                    self._scene.blockSignals(True)
                except Exception:
                    pass
                self._script = vs
                self._scene.clear()
                self._node_items.clear()
                self._edge_items.clear()
                self._comment_items.clear()
                self._standalone_comments.clear()
                
                for n in vs.nodes:
                    item = VisualNodeItem(n, self)
                    self._scene.addItem(item)
                    self._node_items[n.id] = item
                    
                    # Load comment if node has one
                    if n.comment:
                        comment_item = CommentItem(n.comment, n.position + QPointF(200, 0), self, n.id)
                        self._scene.addItem(comment_item)
                        self._comment_items[n.id] = comment_item
                
                self._rebuild_edges_from_model()
                try:
                    self._scene.blockSignals(False)
                except Exception:
                    pass
                # Reinitialize last node positions for change detection
                # This prevents spurious history pushes on next mouse release
                # when nodes were at different positions before restoration
                self._last_node_positions = {n.id: n.position for n in vs.nodes}
                self._emit_changed()
        except Exception:
            pass

    def undo(self):
        # 撤銷
        try:
            if self._history_index > 0:
                self._history_index -= 1
                self._restore_history(self._history_index)
                return True  # Success
            return False  # No more history to undo
        except Exception:
            return False

    def redo(self):
        # 重做
        try:
            if self._history_index < len(self._history_stack) - 1:
                self._history_index += 1
                self._restore_history(self._history_index)
                return True  # Success
            return False  # No more history to redo
        except Exception:
            return False

    def _open_search_panel(self):
        # 節點搜尋面板（簡化版）：直接在目前視圖中心位置建立所選類型
        try:
            from PySide6.QtWidgets import QDialog, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem
            dlg = QDialog(self)
            dlg.setWindowTitle("新增節點")
            lay = QVBoxLayout(dlg)
            edit = QLineEdit(dlg)
            lst = QListWidget(dlg)
            for nt in self.NODE_TYPES:
                lst.addItem(QListWidgetItem(f"{nt['name']}|{nt['id']}"))
            def _filter(text: str):
                for i in range(lst.count()):
                    item = lst.item(i)
                    vis = (text.strip().lower() in item.text().lower()) if text.strip() else True
                    item.setHidden(not vis)
            edit.textChanged.connect(_filter)
            lay.addWidget(edit)
            lay.addWidget(lst)
            def _select_and_add():
                it = lst.currentItem()
                if not it:
                    return
                parts = it.text().split("|")
                t = parts[-1]
                pos = self._scene_view.mapToScene(self._scene_view.viewport().rect().center())
                self.add_node(t, pos)
                dlg.accept()
            from PySide6.QtCore import Qt as _Qt
            lst.itemDoubleClicked.connect(lambda _i: _select_and_add())
            edit.returnPressed.connect(_select_and_add)
            dlg.exec()
        except Exception:
            pass
