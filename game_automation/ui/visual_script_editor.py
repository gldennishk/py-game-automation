from typing import Dict, Optional
import os
import traceback
from PySide6.QtCore import Qt, QPointF, Signal, QEvent
from PySide6.QtGui import QPen, QBrush, QColor, QPainter, QLinearGradient, QFont, QPainterPath, QTransform
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsItem, QGraphicsEllipseItem, QGraphicsRectItem, QGraphicsPathItem, QWidget, QHBoxLayout, QVBoxLayout, QGraphicsTextItem, QPushButton, QMenu
from ..core.actions import VisualScript, VisualNode


class VisualNodeItem(QGraphicsRectItem):
    _colors = {
        'click': '#2196F3',
        'key': '#FF9800',
        'sleep': '#9C27B0',
        'find_color': '#F44336',
        'condition': '#3F51B5',
        'loop': '#795548',
        'find_image': '#4CAF50',
        'default': '#607D8B'
    }
    
    _icons = {
        'click': '🐭',
        'key': '⌨️',
        'sleep': '⏱️',
        'find_color': '🎨',
        'condition': '🔀',
        'loop': '🔁',
        'find_image': '🖼️',
        'default': '○'
    }
    
    _titles = {
        'click': '點擊',
        'key': '按鍵',
        'sleep': '等待',
        'find_color': '找顏色',
        'condition': '條件',
        'loop': '迴圈',
        'find_image': '找圖片',
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
        
        # Set colors based on node type
        self._normal_color = QColor(self._colors.get(node.type, self._colors['default']))
        self._selected_color = QColor(self._normal_color).darker(120)
        
        # Create a gradient background
        self._gradient = QLinearGradient(0, 0, 0, 80)
        self._gradient.setColorAt(0, self._normal_color.lighter(150))
        self._gradient.setColorAt(1, self._normal_color)
        
        self._pen = QPen(QColor(0, 0, 0, 50), 1.5)
        self._selected_pen = QPen(QColor(0, 120, 215), 2.5)
        
        # Add text items
        self._title = QGraphicsTextItem(self)
        self._title.setPlainText(f"{self._titles.get(node.type, '節點')}")
        self._title.setPos(10, 10)
        self._title.setDefaultTextColor(QColor(255, 255, 255))
        
        # Add icon
        self._icon = QGraphicsTextItem(self)
        self._icon.setPlainText(self._icons.get(node.type, self._icons['default']))
        self._icon.setPos(140, 10)
        self._icon.setDefaultTextColor(QColor(255, 255, 255, 180))
        self._icon.setFont(QFont('Arial', 20))
        
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
                
        self._params_text.setPlainText("\n".join(params[:3]))  # Show max 3 params
        self._params_text.setPos(10, 40)
        self._params_text.setDefaultTextColor(QColor(255, 255, 255, 220))
        
        # Update appearance
        self.update_appearance()
    
    def update_appearance(self):
        # Update visual appearance based on selection state
        if self.isSelected():
            self.setBrush(QBrush(self._selected_color))
            self.setPen(self._selected_pen)
        else:
            self.setBrush(QBrush(self._gradient))
            self.setPen(self._pen)
    
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
        act_del = menu.addAction("刪除節點")
        act_rm = menu.addAction("移除連線")
        chosen = menu.exec(event.screenPos().toPoint())
        if chosen == act_del:
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


class ConnectionItem(QGraphicsEllipseItem):
    def __init__(self, p: QPointF):
        super().__init__(0, 0, 12, 12)
        self.setBrush(QBrush(QColor(200, 220, 255)))
        self.setPen(QPen(QColor(180, 198, 230)))
        self.setPos(p)


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
        if self._editor._connect_mode:
            item = self.itemAt(event.position().toPoint())
            nid = None
            if isinstance(item, ConnectionItem):
                nid = self._editor._conn_points_inv.get(item)
            else:
                # Allow clicking anywhere on the node to connect when in connect mode
                try:
                    current = item
                    while current and not isinstance(current, VisualNodeItem):
                        current = current.parentItem() if hasattr(current, 'parentItem') else None
                    if isinstance(current, VisualNodeItem):
                        # Find node id by item reference
                        for node_id, node_item in self._editor._node_items.items():
                            if node_item is current:
                                nid = node_id
                                break
                except Exception:
                    print("[ScriptGraphicsView] resolve node from click failed")
                    traceback.print_exc()
            if nid:
                if self._editor._pending_connection_src_id is None:
                    self._editor._pending_connection_src_id = nid
                else:
                    self._editor.connect_nodes(self._editor._pending_connection_src_id, nid)
                    self._editor._pending_connection_src_id = None
                    return
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
        super().mouseReleaseEvent(event)
        self._editor._on_scene_view_mouse_release()

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
    
    # Node type definitions
    NODE_TYPES = [
        {"id": "click", "name": "點擊", "icon": "🐭", "color": "#2196F3"},
        {"id": "key", "name": "按鍵", "icon": "⌨️", "color": "#FF9800"},
        {"id": "sleep", "name": "等待", "icon": "⏱️", "color": "#9C27B0"},
        {"id": "find_color", "name": "找顏色", "icon": "🎨", "color": "#F44336"},
        {"id": "condition", "name": "條件", "icon": "🔀", "color": "#3F51B5"},
        {"id": "loop", "name": "迴圈", "icon": "🔁", "color": "#795548"},
        {"id": "find_image", "name": "找圖片", "icon": "🖼️", "color": "#4CAF50"}
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self._script: VisualScript = VisualScript()
        self._node_items: Dict[str, VisualNodeItem] = {}
        self._conn_points: Dict[str, ConnectionItem] = {}
        self._conn_points_inv: Dict[ConnectionItem, str] = {}
        self._edge_items: Dict[tuple[str, str], EdgeItem] = {}  # (src_id, dst_id) -> EdgeItem
        self._scale = 1.0
        self._pending_connection_src_id: Optional[str] = None
        self._connect_mode: bool = False
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
        
        # Add buttons with icons
        self._play_btn = QPushButton("▶ 執行")
        self._play_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 4px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        self._play_btn.clicked.connect(self.executeRequested.emit)
        
        # Create node type buttons
        node_buttons = [
            ("🐭 點擊", "click", "#2196F3"),
            ("⌨️ 按鍵", "key", "#FF9800"),
            ("⏱️ 等待", "sleep", "#9C27B0"),
            ("🎨 找顏色", "find_color", "#F44336"),
            ("🔀 條件", "condition", "#3F51B5"),
            ("🔁 迴圈", "loop", "#795548"),
            ("🖼️ 找圖片", "find_image", "#4CAF50")
        ]
        
        # Add buttons to toolbar
        toolbar_layout.addWidget(self._play_btn)
        toolbar_layout.addSpacing(10)
        
        for text, node_type, color in node_buttons:
            btn = QPushButton(text)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {color};
                    color: white;
                    border: none;
                    padding: 4px 12px;
                    border-radius: 4px;
                    margin-right: 4px;
                }}
                QPushButton:hover {{
                    background-color: {self._adjust_color(color, 0.9)};
                }}
            """)
            btn.clicked.connect(lambda checked, t=node_type: self.add_node(t))
            toolbar_layout.addWidget(btn)
        
        toolbar_layout.addStretch()
        
        # Add connect mode toggle
        self._connect_mode_btn = QPushButton("🔗 連接模式")
        self._connect_mode_btn.setCheckable(True)
        self._connect_mode_btn.setStyleSheet("""
            QPushButton {
                background-color: #607D8B;
                color: white;
                border: none;
                padding: 4px 12px;
                border-radius: 4px;
            }
            QPushButton:checked {
                background-color: #455A64;
            }
        """)
        self._connect_mode_btn.toggled.connect(self._set_connect_mode)
        toolbar_layout.addWidget(self._connect_mode_btn)
        
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
    
    def _adjust_color(self, hex_color, factor):
        # Adjust color brightness
        color = QColor(hex_color)
        h, s, v, a = color.hue(), color.saturation(), color.value(), color.alpha()
        v = max(0, min(255, v * factor))
        color.setHsv(h, s, v, a)
        return color.name()

    def _set_connect_mode(self, enabled: bool):
        self._connect_mode = enabled
        self._pending_connection_src_id = None

    def load_script(self, script: VisualScript):
        self._script = script
        self._scene.clear()
        self._node_items.clear()
        self._conn_points.clear()
        self._conn_points_inv.clear()
        self._edge_items.clear()
        
        for n in script.nodes:
            item = VisualNodeItem(n, self)
            self._scene.addItem(item)
            self._node_items[n.id] = item
            cp = ConnectionItem(item.pos() + QPointF(110, 20))
            self._scene.addItem(cp)
            self._conn_points[n.id] = cp
            self._conn_points_inv[cp] = n.id
        
        self._rebuild_edges_from_model()
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
        cp = ConnectionItem(item.pos() + QPointF(110, 20))
        self._scene.addItem(cp)
        self._conn_points[n.id] = cp
        self._conn_points_inv[cp] = n.id
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
        self._rebuild_edges_from_model()
        self._emit_changed()

    def wheelEvent(self, event):
        # Forward wheel events to the scene view for zooming
        # TODO: Enhance zoom with pan support and zoom limits
        self._scene_view.wheelEvent(event)

    def _on_scene_view_mouse_release(self):
        """Called after scene view processes mouse release"""
        for nid, item in self._node_items.items():
            node = self._find_node(nid)
            if node:
                node.position = item.pos()
        # Update all edges when nodes move (positions changed, model unchanged)
        self._update_all_edges()
        sel = self._selected_node_id()
        if sel:
            n = self._find_node(sel)
            if n:
                self.nodeSelected.emit(sel, n)
        self._emit_changed()

    def _on_selection_changed(self):
        sel = self._selected_node_id()
        if sel:
            n = self._find_node(sel)
            if n:
                try:
                    self.nodeSelected.emit(sel, n)
                except Exception:
                    pass
        self._emit_changed()


    def _selected_node_id(self) -> Optional[str]:
        for nid, item in self._node_items.items():
            if item.isSelected():
                return nid
        return None

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
        src_point = src_item.pos() + QPointF(110, 20)  # Connection point position
        dst_point = dst_item.pos() + QPointF(110, 20)
        
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
        src_point = src_item.pos() + QPointF(110, 20)
        dst_point = dst_item.pos() + QPointF(110, 20)
        edge.set_points(src_point, dst_point)
    
    def _update_all_edges(self):
        """Update all edge positions based on current node positions"""
        if not hasattr(self, '_edge_items'):
            self._edge_items = {}
        for edge_key in list(self._edge_items.keys()):
            self._update_edge(edge_key)
    
    def _emit_changed(self):
        self.scriptChanged.emit(self._script)

    def delete_node(self, node_id: str):
        node = self._find_node(node_id)
        if not node:
            return
        try:
            if node_id in self._node_items:
                item = self._node_items.pop(node_id)
                self._scene.removeItem(item)
            if node_id in self._conn_points:
                cp = self._conn_points.pop(node_id)
                self._conn_points_inv.pop(cp, None)
                self._scene.removeItem(cp)
        except Exception:
            print("[VisualScriptEditor] delete_node UI remove failed")
            traceback.print_exc()
        self.remove_node_connections(node_id)
        try:
            self._script.nodes = [n for n in self._script.nodes if n.id != node_id]
        except Exception:
            print("[VisualScriptEditor] delete_node update model failed")
            traceback.print_exc()
        self._emit_changed()

    def remove_node_connections(self, node_id: str):
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
