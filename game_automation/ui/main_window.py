from typing import Optional
import os
from PySide6.QtCore import Qt, Signal, QObject, QThread, QTimer, QPointF, QMutex
from PySide6.QtGui import QImage, QPixmap, QFont
from PySide6.QtWidgets import QMainWindow, QWidget, QSplitter, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QPushButton, QStatusBar, QFormLayout, QLineEdit, QComboBox, QDoubleSpinBox, QFileDialog, QMessageBox, QApplication, QCompleter, QScrollArea, QInputDialog, QTextEdit, QDockWidget
from .visual_script_editor import VisualScriptEditor, VisualNodeItem, CommentItem
from .widgets import ResourceSidebar
from .themes import LIGHT_QSS
from ..core.actions import VisualScript, VisualNode
from ..core.screen_capture import ScreenCaptureWorker
from ..core.image_processor import ImageProcessor
from ..core.performance_monitor import PerformanceMonitor
from ..core.automation import AutomationController
import traceback

# Base directory for JSON files (project root)
# All JSON persistence files (visual_scripts.json, resources.json) are stored at the project root.
# Legacy files like scripts.json and game_automation/*.json are deprecated and no longer used.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


def _to_relative_path(path: str) -> str:
    """
    Convert absolute path to project-relative path.
    
    NOTE: This function is deprecated. Use game_automation.core.path_utils.to_relative_path() instead.
    This function is kept for backward compatibility but should not be used in new code.
    """
    # Use the canonical implementation from path_utils to ensure consistency
    from ..core.path_utils import to_relative_path as _canonical_to_relative_path
    return _canonical_to_relative_path(path)


def register_inline_image_template(pixmap: QPixmap, sidebar: ResourceSidebar) -> tuple[str, str]:
    """
    Shared helper function to register an inline image template.
    
    Generates a unique template name, ensures temp_templates directory exists,
    saves the QPixmap to PNG, and registers it in ResourceSidebar.
    
    Args:
        pixmap: The QPixmap to save as a template
        sidebar: The ResourceSidebar instance to register the template in
    
    Returns:
        tuple[str, str]: (template_name, absolute_path) on success, ("", "") on failure
    
    This function ensures consistent behavior between PropertiesPanel upload/paste
    and MainWindow drag-and-drop image registration.
    """
    if pixmap.isNull():
        return "", ""
    
    # Sidebar is required for registration - return failure if not available
    if not sidebar:
        return "", ""
    
    # Ensure temp_templates directory exists
    temp_dir = os.path.join(BASE_DIR, "temp_templates")
    try:
        os.makedirs(temp_dir, exist_ok=True)
    except Exception:
        return "", ""
    
    # Generate unique template name
    import time
    tmpl_name = f"inline_image_{int(time.time()*1000)}"
    abs_path = os.path.join(temp_dir, f"{tmpl_name}.png")
    
    # Save pixmap to file
    try:
        if not pixmap.save(abs_path, "PNG"):
            return "", ""
    except Exception:
        return "", ""
    
    # Register in sidebar using public API
    try:
        sidebar.register_template(tmpl_name, abs_path)
        sidebar.persist()
    except Exception:
        return "", ""
    
    return tmpl_name, abs_path


class PropertiesPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._node: Optional[VisualNode] = None
        self._editor: Optional[VisualScriptEditor] = None
        self._sidebar: Optional[ResourceSidebar] = None
        # Track label-related line edits for refreshing autocomplete
        self._label_line_edits: list[QLineEdit] = []
        # Set fixed width to prevent expansion
        self.setFixedWidth(300)
        self._build_ui()

    def _build_ui(self):
        # Create scroll area for content that may exceed panel height
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Create inner widget to hold the form
        inner_widget = QWidget()
        layout = QVBoxLayout(inner_widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        self.lbl = QLabel("屬性面板")
        layout.addWidget(self.lbl)
        self.form = QFormLayout()
        layout.addLayout(self.form)
        
        # Set inner widget to scroll area
        scroll_area.setWidget(inner_widget)
        
        # Set main layout with scroll area
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(scroll_area)

    def attach_editor(self, editor: VisualScriptEditor):
        self._editor = editor
    
    def attach_sidebar(self, sidebar: ResourceSidebar):
        self._sidebar = sidebar

    def _get_available_labels(self):
        """Get list of available labels from TARGET_DEFINITIONS and sidebar templates"""
        labels = set()
        try:
            from ..core.targets import TARGET_DEFINITIONS
            labels.update(TARGET_DEFINITIONS.keys())
        except Exception:
            pass
        if self._sidebar and hasattr(self._sidebar, '_templates'):
            labels.update(self._sidebar._templates.keys())
        return sorted(list(labels))

    def _setup_label_autocomplete(self, line_edit: QLineEdit):
        """Setup autocomplete for label/template_name input fields"""
        if not line_edit:
            return
        try:
            # Remove existing completer if any to avoid conflicts
            existing_completer = line_edit.completer()
            if existing_completer:
                existing_completer.setParent(None)
                line_edit.setCompleter(None)
            
            labels = self._get_available_labels()
            completer = QCompleter(labels, line_edit)
            completer.setCaseSensitivity(Qt.CaseInsensitive)
            completer.setCompletionMode(QCompleter.PopupCompletion)
            line_edit.setCompleter(completer)
            
            # Add validation: show red border if label doesn't exist
            # Store labels in closure to avoid accessing _get_available_labels repeatedly
            validation_labels = set(labels)
            def _validate_label(text: str):
                try:
                    if not line_edit:  # Check if line_edit still exists
                        return
                    if text and text not in validation_labels:
                        # Use dynamic property instead of setStyleSheet to avoid conflicts with global QSS
                        line_edit.setProperty("hasError", True)
                        line_edit.style().unpolish(line_edit)
                        line_edit.style().polish(line_edit)
                    else:
                        # Clear error state
                        line_edit.setProperty("hasError", False)
                        line_edit.style().unpolish(line_edit)
                        line_edit.style().polish(line_edit)
                except Exception:
                    # Silently ignore validation errors to prevent crashes
                    pass
            
            # 只斷開先前儲存的驗證回調，避免 Qt 斷開無連線時的警告
            try:
                prev = getattr(line_edit, "_validator_callback", None)
                if prev:
                    line_edit.textChanged.disconnect(prev)
            except Exception:
                pass
            
            line_edit.textChanged.connect(_validate_label)
            try:
                setattr(line_edit, "_validator_callback", _validate_label)
            except Exception:
                pass
            # Validate initial value
            _validate_label(line_edit.text())
        except Exception as e:
            # Log error but don't crash
            print(f"[PropertiesPanel] _setup_label_autocomplete failed: {e}")
            import traceback
            traceback.print_exc()

    def _clear_form(self):
        # Clear tracked label line edits
        self._label_line_edits.clear()
        while self.form.count():
            item = self.form.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def set_node(self, node_id: str, node: VisualNode):
        self._node = node
        self.lbl.setText(f"選中節點: {node_id}")
        self._clear_form()
        if not node:
            return
        t = node.type
        if t == "click":
            edit_label = QLineEdit(str(node.params.get("label", "")))
            self._setup_label_autocomplete(edit_label)
            self._label_line_edits.append(edit_label)
            combo_btn = QComboBox()
            combo_btn.addItems(["left", "middle", "right"]) 
            idx = combo_btn.findText(str(node.params.get("button", "left")))
            if idx >= 0:
                combo_btn.setCurrentIndex(idx)
            spin_dur = QDoubleSpinBox()
            spin_dur.setRange(0.0, 10.0)
            spin_dur.setDecimals(2)
            spin_dur.setSingleStep(0.1)
            spin_dur.setValue(float(node.params.get("duration", 0.0)))
            self.form.addRow("標籤", edit_label)
            self.form.addRow("按鈕", combo_btn)
            self.form.addRow("持續秒數", spin_dur)
            edit_label.textChanged.connect(lambda v: self._update_param("label", v))
            combo_btn.currentTextChanged.connect(lambda v: self._update_param("button", v))
            spin_dur.valueChanged.connect(lambda v: self._update_param("duration", float(v)))
        elif t == "sleep":
            spin_secs = QDoubleSpinBox()
            spin_secs.setRange(0.0, 60.0)
            spin_secs.setDecimals(2)
            spin_secs.setSingleStep(0.1)
            spin_secs.setValue(float(node.params.get("seconds", 0.2)))
            self.form.addRow("秒數", spin_secs)
            spin_secs.valueChanged.connect(lambda v: self._update_param("seconds", float(v)))
        elif t == "key":
            edit_key = QLineEdit(str(node.params.get("key", "space")))
            spin_dur = QDoubleSpinBox()
            spin_dur.setRange(0.0, 10.0)
            spin_dur.setDecimals(2)
            spin_dur.setSingleStep(0.1)
            spin_dur.setValue(float(node.params.get("duration", 0.0)))
            self.form.addRow("按鍵", edit_key)
            self.form.addRow("持續秒數", spin_dur)
            edit_key.textChanged.connect(lambda v: self._update_param("key", v))
            spin_dur.valueChanged.connect(lambda v: self._update_param("duration", float(v)))
        elif t == "find_color":
            edit_hmin = QLineEdit(",".join(str(x) for x in (node.params.get("hsv_min") or [])))
            edit_hmax = QLineEdit(",".join(str(x) for x in (node.params.get("hsv_max") or [])))
            edit_bmin = QLineEdit(",".join(str(x) for x in (node.params.get("bgr_min") or [])))
            edit_bmax = QLineEdit(",".join(str(x) for x in (node.params.get("bgr_max") or [])))
            self.form.addRow("HSV 最小", edit_hmin)
            self.form.addRow("HSV 最大", edit_hmax)
            self.form.addRow("BGR 最小", edit_bmin)
            self.form.addRow("BGR 最大", edit_bmax)
            edit_hmin.textChanged.connect(lambda v: self._update_param("hsv_min", self._parse_list(v)))
            edit_hmax.textChanged.connect(lambda v: self._update_param("hsv_max", self._parse_list(v)))
            edit_bmin.textChanged.connect(lambda v: self._update_param("bgr_min", self._parse_list(v)))
            edit_bmax.textChanged.connect(lambda v: self._update_param("bgr_max", self._parse_list(v)))
        elif t == "condition":
            combo_mode = QComboBox()
            combo_mode.addItems(["label", "color"]) 
            idx = combo_mode.findText(str(node.params.get("mode", "label")))
            if idx >= 0:
                combo_mode.setCurrentIndex(idx)
            edit_label = QLineEdit(str(node.params.get("label", "")))
            self._setup_label_autocomplete(edit_label)
            self._label_line_edits.append(edit_label)
            spin_min_confidence = QDoubleSpinBox()
            spin_min_confidence.setRange(0.0, 1.0)
            spin_min_confidence.setDecimals(2)
            spin_min_confidence.setSingleStep(0.05)
            spin_min_confidence.setValue(float(node.params.get("min_confidence", 0.0)))
            next_true_id = str(node.params.get("next_true", ""))
            next_false_id = str(node.params.get("next_false", ""))
            true_label = self._get_node_label(next_true_id) if next_true_id else ""
            false_label = self._get_node_label(next_false_id) if next_false_id else ""
            edit_true = QLineEdit(true_label if true_label else next_true_id)
            edit_false = QLineEdit(false_label if false_label else next_false_id)
            edit_true.setReadOnly(True)
            edit_false.setReadOnly(True)
            edit_hmin = QLineEdit(",".join(str(x) for x in (node.params.get("hsv_min") or [])))
            edit_hmax = QLineEdit(",".join(str(x) for x in (node.params.get("hsv_max") or [])))
            edit_bmin = QLineEdit(",".join(str(x) for x in (node.params.get("bgr_min") or [])))
            edit_bmax = QLineEdit(",".join(str(x) for x in (node.params.get("bgr_max") or [])))
            self.form.addRow("模式", combo_mode)
            self.form.addRow("標籤", edit_label)
            self.form.addRow("最小置信度", spin_min_confidence)
            self.form.addRow("True 走向", edit_true)
            self.form.addRow("False 走向", edit_false)
            self.form.addRow("HSV 最小", edit_hmin)
            self.form.addRow("HSV 最大", edit_hmax)
            self.form.addRow("BGR 最小", edit_bmin)
            self.form.addRow("BGR 最大", edit_bmax)
            combo_mode.currentTextChanged.connect(lambda v: self._update_param("mode", v))
            edit_label.textChanged.connect(lambda v: self._update_param("label", v))
            spin_min_confidence.valueChanged.connect(lambda v: self._update_param("min_confidence", float(v)))
            edit_hmin.textChanged.connect(lambda v: self._update_param("hsv_min", self._parse_list(v)))
            edit_hmax.textChanged.connect(lambda v: self._update_param("hsv_max", self._parse_list(v)))
            edit_bmin.textChanged.connect(lambda v: self._update_param("bgr_min", self._parse_list(v)))
            edit_bmax.textChanged.connect(lambda v: self._update_param("bgr_max", self._parse_list(v)))
        elif t == "loop":
            spin_count = QDoubleSpinBox()
            spin_count.setRange(0, 100)
            spin_count.setDecimals(0)
            spin_count.setSingleStep(1)
            spin_count.setValue(float(node.params.get("count", 0)))
            next_body_id = str(node.params.get("next_body", ""))
            next_after_id = str(node.params.get("next_after", ""))
            body_label = self._get_node_label(next_body_id) if next_body_id else ""
            after_label = self._get_node_label(next_after_id) if next_after_id else ""
            edit_body = QLineEdit(body_label if body_label else next_body_id)
            edit_after = QLineEdit(after_label if after_label else next_after_id)
            edit_body.setReadOnly(True)
            edit_after.setReadOnly(True)
            self.form.addRow("次數", spin_count)
            self.form.addRow("迴圈體", edit_body)
            self.form.addRow("迴圈後", edit_after)
            spin_count.valueChanged.connect(lambda v: self._update_param("count", int(v)))
        elif t == "find_image":
            # Template name dropdown - get from sidebar templates and TARGET_DEFINITIONS
            combo_template = QComboBox()
            combo_template.setEditable(True)
            combo_template.addItem("")  # Empty option
            # Get templates from sidebar if available
            if self._sidebar and hasattr(self._sidebar, '_templates'):
                for tmpl_name in sorted(self._sidebar._templates.keys()):
                    combo_template.addItem(tmpl_name)
            # Also add labels from TARGET_DEFINITIONS
            try:
                from ..core.targets import TARGET_DEFINITIONS
                for label in sorted(TARGET_DEFINITIONS.keys()):
                    if combo_template.findText(label) < 0:  # Avoid duplicates
                        combo_template.addItem(label)
            except Exception:
                pass
            # Set current value
            current_template = str(node.params.get("template_name", ""))
            idx = combo_template.findText(current_template)
            if idx >= 0:
                combo_template.setCurrentIndex(idx)
            else:
                combo_template.setCurrentText(current_template)
            # Setup autocomplete for the editable combo box
            # Ensure QComboBox is editable before accessing lineEdit()
            try:
                if combo_template.isEditable():
                    line_edit = combo_template.lineEdit()
                    if line_edit:
                        self._setup_label_autocomplete(line_edit)
                        self._label_line_edits.append(line_edit)
            except Exception as e:
                # Log error but don't crash - autocomplete is optional
                print(f"[PropertiesPanel] Failed to setup autocomplete for template combo: {e}")
                import traceback
                traceback.print_exc()
            
            spin_confidence = QDoubleSpinBox()
            spin_confidence.setRange(0.0, 1.0)
            spin_confidence.setDecimals(2)
            spin_confidence.setSingleStep(0.05)
            spin_confidence.setValue(float(node.params.get("confidence", 0.8)))
            
            self.form.addRow("範本名稱", combo_template)
            self.form.addRow("置信度", spin_confidence)
            combo_template.currentTextChanged.connect(lambda v: self._update_param("template_name", v))
            spin_confidence.valueChanged.connect(lambda v: self._update_param("confidence", float(v)))
            
            # Add read-only description label
            desc_label = QLabel("此節點只負責偵測圖片並回傳是否找到，要點擊必須額外接上一個 click 節點。")
            desc_label.setWordWrap(True)
            desc_label.setStyleSheet("color: #666666; font-size: 11px; padding: 4px;")
            self.form.addRow("", desc_label)

            btn_row = QHBoxLayout()
            btn_upload = QPushButton("上傳圖片")
            btn_paste = QPushButton("從剪貼簿貼上")
            btn_row.addWidget(btn_upload)
            btn_row.addWidget(btn_paste)
            container = QWidget()
            container.setLayout(btn_row)
            self.form.addRow("圖片來源", container)

            def _register_template_from_pixmap(pix: QPixmap):
                """Register a template from a QPixmap using the shared helper function"""
                if not self._sidebar:
                    return
                tmpl_name, abs_path = register_inline_image_template(pix, self._sidebar)
                if not tmpl_name or not abs_path:
                    QMessageBox.critical(self, "錯誤", "保存圖片失敗")
                    return
                # Update UI
                if combo_template.findText(tmpl_name) < 0:
                    combo_template.addItem(tmpl_name)
                combo_template.setCurrentText(tmpl_name)
                self._update_param("template_name", tmpl_name)

            def _on_upload():
                path, _ = QFileDialog.getOpenFileName(self, "選擇圖片", "", "Image Files (*.png *.jpg *.jpeg);;All Files (*)")
                if not path:
                    return
                try:
                    pix = QPixmap(path)
                    if pix.isNull():
                        QMessageBox.warning(self, "提示", "無法載入圖片")
                        return
                    _register_template_from_pixmap(pix)
                except Exception:
                    QMessageBox.critical(self, "錯誤", "圖片處理失敗")

            def _on_paste():
                cb = QApplication.clipboard()
                pix = cb.pixmap()
                if pix.isNull():
                    QMessageBox.warning(self, "提示", "剪貼簿沒有圖片")
                    return
                _register_template_from_pixmap(pix)

            btn_upload.clicked.connect(_on_upload)
            btn_paste.clicked.connect(_on_paste)
        elif t == "verify_image_color":
            # Template name dropdown
            combo_template = QComboBox()
            combo_template.setEditable(True)
            combo_template.addItem("")  # Empty option
            if self._sidebar and hasattr(self._sidebar, '_templates'):
                for tmpl_name in sorted(self._sidebar._templates.keys()):
                    combo_template.addItem(tmpl_name)
            try:
                from ..core.targets import TARGET_DEFINITIONS
                for label in sorted(TARGET_DEFINITIONS.keys()):
                    if combo_template.findText(label) < 0:
                        combo_template.addItem(label)
            except Exception:
                pass
            current_template = str(node.params.get("template_name", ""))
            idx = combo_template.findText(current_template)
            if idx >= 0:
                combo_template.setCurrentIndex(idx)
            else:
                combo_template.setCurrentText(current_template)
            try:
                if combo_template.isEditable():
                    line_edit = combo_template.lineEdit()
                    if line_edit:
                        self._setup_label_autocomplete(line_edit)
                        self._label_line_edits.append(line_edit)
            except Exception:
                pass
            
            spin_offset_x = QDoubleSpinBox()
            spin_offset_x.setRange(-1000.0, 1000.0)
            spin_offset_x.setDecimals(0)
            spin_offset_x.setSingleStep(1)
            spin_offset_x.setValue(float(node.params.get("offset_x", 0)))
            
            spin_offset_y = QDoubleSpinBox()
            spin_offset_y.setRange(-1000.0, 1000.0)
            spin_offset_y.setDecimals(0)
            spin_offset_y.setSingleStep(1)
            spin_offset_y.setValue(float(node.params.get("offset_y", 0)))
            
            edit_hmin = QLineEdit(",".join(str(x) for x in (node.params.get("hsv_min") or [])))
            edit_hmax = QLineEdit(",".join(str(x) for x in (node.params.get("hsv_max") or [])))
            edit_bmin = QLineEdit(",".join(str(x) for x in (node.params.get("bgr_min") or [])))
            edit_bmax = QLineEdit(",".join(str(x) for x in (node.params.get("bgr_max") or [])))
            
            spin_radius = QDoubleSpinBox()
            spin_radius.setRange(0.0, 100.0)
            spin_radius.setDecimals(1)
            spin_radius.setSingleStep(1.0)
            spin_radius.setValue(float(node.params.get("radius", 0.0)))
            
            self.form.addRow("範本名稱", combo_template)
            self.form.addRow("X 偏移", spin_offset_x)
            self.form.addRow("Y 偏移", spin_offset_y)
            self.form.addRow("HSV 最小", edit_hmin)
            self.form.addRow("HSV 最大", edit_hmax)
            self.form.addRow("BGR 最小", edit_bmin)
            self.form.addRow("BGR 最大", edit_bmax)
            self.form.addRow("檢查半徑", spin_radius)
            
            combo_template.currentTextChanged.connect(lambda v: self._update_param("template_name", v))
            spin_offset_x.valueChanged.connect(lambda v: self._update_param("offset_x", int(v)))
            spin_offset_y.valueChanged.connect(lambda v: self._update_param("offset_y", int(v)))
            edit_hmin.textChanged.connect(lambda v: self._update_param("hsv_min", self._parse_list(v)))
            edit_hmax.textChanged.connect(lambda v: self._update_param("hsv_max", self._parse_list(v)))
            edit_bmin.textChanged.connect(lambda v: self._update_param("bgr_min", self._parse_list(v)))
            edit_bmax.textChanged.connect(lambda v: self._update_param("bgr_max", self._parse_list(v)))
            spin_radius.valueChanged.connect(lambda v: self._update_param("radius", float(v)))

    def _parse_list(self, s: str):
        try:
            vals = [int(x.strip()) for x in s.split(",") if x.strip() != ""]
            return vals
        except Exception:
            return []

    def _get_node_label(self, node_id: str) -> str:
        """Get a short label for a node by its ID"""
        if not node_id or not self._editor:
            return ""
        node = self._editor._find_node(node_id)
        if not node:
            return node_id
        # Return a short label: node type + ID
        type_names = {
            "click": "點擊",
            "key": "按鍵",
            "sleep": "等待",
            "find_color": "找顏色",
            "condition": "條件",
            "loop": "迴圈",
            "find_image": "找圖片",
            "verify_image_color": "驗證圖片顏色"
        }
        type_name = type_names.get(node.type, node.type)
        return f"{type_name} ({node_id})"

    def refresh_label_completers(self):
        """
        Refresh autocomplete for all active label-related input fields.
        Called when templates change to update the available label list.
        """
        if not self._node:
            return
        # Filter out invalid line edits and refresh valid ones
        valid_line_edits = []
        for line_edit in self._label_line_edits:
            try:
                # Check if line_edit is still valid (has a parent widget)
                if line_edit and line_edit.parent() and line_edit.isVisible():
                    valid_line_edits.append(line_edit)
            except (RuntimeError, AttributeError):
                # Widget has been deleted, skip it
                continue
        
        # Update the tracked list to only include valid line edits
        self._label_line_edits = valid_line_edits
        
        # Refresh all valid line edits
        for line_edit in valid_line_edits:
            try:
                self._setup_label_autocomplete(line_edit)
            except Exception as e:
                # Log error but continue with other line edits
                print(f"[PropertiesPanel] refresh_label_completers failed for line_edit: {e}")
                import traceback
                traceback.print_exc()

    def _update_param(self, key: str, value):
        if not self._node:
            return
        self._node.params[key] = value
        if self._editor:
            try:
                self._editor._emit_changed()
            except Exception:
                print("[MainWindow] _update_param emit changed failed")
                traceback.print_exc()


class FrameUpdateSignal(QObject):
    """Signal object for thread-safe frame updates"""
    frame_ready = Signal(QImage, float)  # qimg, fps


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Game Automation Studio")
        self._automation = AutomationController(scale_factor=1.0)
        self._build_ui()
        self.setStyleSheet(LIGHT_QSS)
        self._capture_worker: Optional[ScreenCaptureWorker] = None
        self._capture_region: Optional[dict] = None
        self._window_geometry: Optional[dict] = None  # Store window geometry for thread-safe access
        self._image_processor = ImageProcessor()
        self._perf = PerformanceMonitor(window_seconds=1.0)
        self._latest_vision_result: dict = {}
        self._script_cache: dict[str, VisualScript] = {}
        self._current_script_name: Optional[str] = None
        # Signal for thread-safe frame updates
        self._frame_signal = FrameUpdateSignal()
        self._frame_signal.frame_ready.connect(self._on_frame_ui)
        self._is_closing = False  # Flag to prevent signal emission after window starts closing
        # Debounced autosave timer
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setSingleShot(True)
        self._autosave_timer.timeout.connect(self._autosave_scripts)
        # Initialize window geometry for thread-safe access
        try:
            geo = self.frameGeometry()
            self._window_geometry = {
                "x": geo.x(),
                "y": geo.y(),
                "width": geo.width(),
                "height": geo.height()
            }
        except Exception:
            print("[MainWindow] initial geometry fetch failed")
            traceback.print_exc()
            self._window_geometry = None
        try:
            self._load_scripts_from_disk()
        except Exception:
            print("[MainWindow] load_scripts_from_disk failed")
            traceback.print_exc()

    def _build_ui(self):
        central = QWidget(self)
        root = QHBoxLayout(central)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        sidebar = ResourceSidebar(self)
        right_split = QSplitter(Qt.Horizontal, self)

        editor = VisualScriptEditor(self)
        self._editor = editor  # Store reference for signal connections

        properties = PropertiesPanel(self)
        self._properties = properties  # Store reference for refresh method

        right_split.addWidget(editor)
        right_split.addWidget(properties)
        # Set initial sizes and stretch factors for right splitter
        # Properties panel has fixed width of 300px, editor area can expand
        right_split.setSizes([800, 300])
        right_split.setStretchFactor(0, 1)  # Editor area can expand
        right_split.setStretchFactor(1, 0)  # Properties panel has fixed width

        root.addWidget(sidebar)
        root.addWidget(right_split, 1)
        self.setCentralWidget(central)
        
        # Create log panel as dock widget
        log_dock = QDockWidget("執行日誌", self)
        log_dock.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.TopDockWidgetArea)
        log_panel = QTextEdit()
        log_panel.setReadOnly(True)
        log_panel.setFont(QFont("Consolas", 9))
        log_panel.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4;")
        log_clear_btn = QPushButton("清除日誌")
        log_clear_btn.clicked.connect(lambda: log_panel.clear())
        log_layout = QVBoxLayout()
        log_layout.setContentsMargins(4, 4, 4, 4)
        log_layout.addWidget(log_clear_btn)
        log_layout.addWidget(log_panel)
        log_widget = QWidget()
        log_widget.setLayout(log_layout)
        log_dock.setWidget(log_widget)
        self.addDockWidget(Qt.BottomDockWidgetArea, log_dock)
        self._log_panel = log_panel
        
        # Create preview panel as dock widget
        preview_dock = QDockWidget("畫面預覽", self)
        preview_dock.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea)
        preview_label = QLabel()
        preview_label.setMinimumSize(320, 240)
        preview_label.setAlignment(Qt.AlignCenter)
        preview_label.setText("等待畫面...")
        preview_label.setStyleSheet("background-color: #2d2d2d; color: #888888; border: 1px solid #444444;")
        preview_freeze_btn = QPushButton("凍結畫面")
        preview_freeze_btn.setCheckable(True)
        preview_freeze_btn.setToolTip("凍結當前畫面以便仔細檢視")
        self._preview_frozen = False
        preview_freeze_btn.toggled.connect(lambda checked: setattr(self, '_preview_frozen', checked))
        preview_layout = QVBoxLayout()
        preview_layout.setContentsMargins(4, 4, 4, 4)
        preview_layout.addWidget(preview_freeze_btn)
        preview_layout.addWidget(preview_label)
        preview_widget = QWidget()
        preview_widget.setLayout(preview_layout)
        preview_dock.setWidget(preview_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, preview_dock)
        self._preview_label = preview_label
        self._preview_freeze_btn = preview_freeze_btn

        toolbar = self.addToolBar("Main")
        btn_start = QPushButton("開始截圖", self)
        btn_exec = QPushButton("執行腳本", self)
        btn_stop = QPushButton("停止執行", self)
        btn_stop.setEnabled(False)  # Disabled until script is running
        btn_reload = QPushButton("重新載入", self)
        btn_record = QPushButton("錄製模式 (即將推出)", self)
        btn_record.setCheckable(True)
        btn_record.setEnabled(False)  # Disable until implemented
        btn_record.setToolTip("錄製滑鼠與鍵盤操作並轉換為節點 (功能開發中)")
        btn_step = QPushButton("單步執行", self)
        btn_step.setEnabled(False)  # Enabled when script is running
        btn_step.setToolTip("逐步執行腳本，每次執行一個節點")
        btn_pause = QPushButton("暫停", self)
        btn_pause.setEnabled(False)  # Enabled when script is running
        btn_pause.setCheckable(True)
        btn_pause.setToolTip("暫停/繼續執行中的腳本")
        btn_validate = QPushButton("驗證腳本", self)
        btn_validate.setToolTip("檢查腳本是否有錯誤或問題")
        btn_save = QPushButton("保存")
        btn_load = QPushButton("載入")
        btn_undo = QPushButton("撤銷", self)
        btn_undo.setToolTip("撤銷上一步操作 (Ctrl+Z)")
        btn_redo = QPushButton("重做", self)
        btn_redo.setToolTip("重做上一步操作 (Ctrl+Shift+Z)")
        toolbar.addWidget(btn_start)
        toolbar.addWidget(btn_exec)
        toolbar.addWidget(btn_stop)
        toolbar.addWidget(btn_validate)
        toolbar.addSeparator()
        toolbar.addWidget(btn_record)
        toolbar.addWidget(btn_step)
        toolbar.addWidget(btn_pause)
        toolbar.addSeparator()
        toolbar.addWidget(btn_undo)
        toolbar.addWidget(btn_redo)
        toolbar.addSeparator()
        toolbar.addWidget(btn_save)
        toolbar.addWidget(btn_load)
        toolbar.addWidget(btn_reload)

        status = QStatusBar(self)
        self.setStatusBar(status)
        status.showMessage("就緒")

        properties.attach_editor(editor)
        properties.attach_sidebar(sidebar)
        # Connect template changes to refresh label autocomplete
        sidebar.templatesChanged.connect(properties.refresh_label_completers)
        editor.nodeSelected.connect(properties.set_node)
        editor.nodeParamsChanged.connect(properties.set_node)  # Refresh properties when node params change
        editor.imageDropped.connect(self._handle_image_drop)  # Handle image drops on find_image nodes
        btn_start.clicked.connect(self._start_capture)
        btn_exec.clicked.connect(self._run_current_script)
        btn_stop.clicked.connect(self._stop_current_script)
        btn_validate.clicked.connect(self._validate_current_script)
        btn_record.toggled.connect(self._toggle_recording_mode)
        btn_step.clicked.connect(self._step_execute)
        btn_pause.toggled.connect(self._pause_execution)
        btn_save.clicked.connect(self._save_all_scripts_dialog)
        btn_load.clicked.connect(self._load_all_scripts_dialog)
        btn_undo.clicked.connect(self._on_undo)
        btn_redo.clicked.connect(self._on_redo)
        editor.executeRequested.connect(self._run_current_script)
        
        # Store references to execution control buttons
        self._btn_exec = btn_exec
        self._btn_stop = btn_stop
        self._btn_record = btn_record
        self._btn_step = btn_step
        self._btn_pause = btn_pause
        self._recording_mode = False
        self._execution_paused = False
        self._script_runner: Optional[ScriptRunnerThread] = None
        self._step_mode = False
        
        # Store references before setting up callbacks that use them
        self._editor = editor
        self._sidebar = sidebar
        
        # Now safe to bind callbacks that reference self._editor
        self._automation.on_node_executed = lambda nid, ok: self._editor.highlight_active_node(nid) if hasattr(self, '_editor') and self._editor else None
        sidebar.currentScriptChanged.connect(self._on_sidebar_script_selected)
        
        # Connect connection rejection signal to show status message
        editor.connectionRejected.connect(self._on_connection_rejected)

        sidebar.scriptsChanged.connect(self._on_scripts_changed)
        sidebar.templatesChanged.connect(self._on_templates_changed)
        sidebar.scriptRenamed.connect(self._on_script_renamed)
        sidebar.scriptDuplicated.connect(self._on_script_duplicated)
        sidebar.saveNodeTemplateRequested.connect(self._on_save_node_template_requested)
        sidebar.nodeTemplateActivated.connect(self._on_node_template_activated)
        editor.scriptChanged.connect(lambda _vs: self._refresh_current_node_properties())
        editor.scriptChanged.connect(lambda _vs: self._schedule_autosave())  # Debounced autosave instead of immediate save
        btn_reload.clicked.connect(self._reload_scripts_now)

    def _refresh_current_node_properties(self):
        """Refresh properties panel if a node is currently selected"""
        if self._editor:
            sel = self._editor._selected_node_id()
            if sel:
                node = self._editor._find_node(sel)
                if node:
                    self._properties.set_node(sel, node)

    def _on_connection_rejected(self, src_id: str, reason: str):
        """Handle connection rejection feedback from VisualScriptEditor"""
        # Show non-blocking notification in status bar
        # Using status bar instead of QMessageBox to avoid interrupting user workflow
        self.statusBar().showMessage(f"連線失敗: {reason}", 3000)  # Show for 3 seconds
    
    def _create_blank_script(self, name: str) -> VisualScript:
        return VisualScript(id=name, name=name, nodes=[])

    def _on_sidebar_script_selected(self, name: str):
        if self._current_script_name:
            try:
                self._script_cache[self._current_script_name] = self._editor.export_script()
            except Exception:
                pass
        self._current_script_name = name
        if name in self._script_cache:
            self._editor.load_script(self._script_cache[name])
        else:
            script = self._create_blank_script(name)
            self._script_cache[name] = script
            self._editor.load_script(script)
        try:
            self._save_scripts_to_disk()
        except Exception:
            pass

    def _start_capture(self):
        import mss
        with mss.mss() as sct:
            mon = sct.monitors[1]
            region = {"left": mon["left"], "top": mon["top"], "width": mon["width"], "height": mon["height"]}
        self._capture_region = region
        if self._capture_worker:
            try:
                self._capture_worker.stop()
            except Exception:
                pass
        self._capture_worker = ScreenCaptureWorker(region=region, fps=60, callback=self._on_frame)
        self._capture_worker.start()
        self.statusBar().showMessage("截圖已開始")

    def _on_frame(self, frame_bgra, ts: float):
        # This callback runs on the worker thread - do non-GUI processing here
        # Do NOT call any GUI methods here (like self.frameGeometry()) as the window may be deleted
        self._perf.tick(ts)
        res = self._image_processor.process_frame(frame_bgra)
        self._latest_vision_result = res
        frame_bgr = res["frame"]
        
        # Process frame data (non-GUI work)
        # Use stored window geometry instead of calling GUI methods
        if self._capture_region and self._window_geometry:
            wx = self._window_geometry["x"]
            wy = self._window_geometry["y"]
            ww = self._window_geometry["width"]
            wh = self._window_geometry["height"]
            rx, ry, rw, rh = self._capture_region["left"], self._capture_region["top"], self._capture_region["width"], self._capture_region["height"]
            x1 = max(wx, rx)
            y1 = max(wy, ry)
            x2 = min(wx + ww, rx + rw)
            y2 = min(wy + wh, ry + rh)
            if x2 > x1 and y2 > y1:
                import cv2
                cv2.rectangle(frame_bgr, (x1 - rx, y1 - ry), (x2 - rx, y2 - ry), (255, 255, 255), -1)
        
        import cv2
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        h, w = rgb.shape[:2]
        bytes_per_line = 3 * w
        # Create QImage with a copy of the data to avoid memory reference issues
        qimg = QImage(rgb.copy(), w, h, bytes_per_line, QImage.Format_RGB888)
        fps = self._perf.fps()
        
        # Emit signal to queue GUI update on main thread
        # Check if window is closing to prevent RuntimeError when signal source is deleted
        if not self._is_closing and self._frame_signal is not None:
            try:
                self._frame_signal.frame_ready.emit(qimg, fps)
            except RuntimeError:
                # Signal source has been deleted, ignore
                pass
    
    def _on_frame_ui(self, qimg: QImage, fps: float):
        """Handle frame updates on the GUI thread"""
        self.statusBar().showMessage(f"FPS: {fps:.1f}")
        
        # Update preview panel if not frozen
        if hasattr(self, '_preview_label') and self._preview_label and not self._preview_frozen:
            # Draw detection boxes on the frame
            preview_img = qimg.copy()
            if self._latest_vision_result and "found_targets" in self._latest_vision_result:
                from PySide6.QtGui import QPainter, QPen, QColor
                painter = QPainter(preview_img)
                pen = QPen(QColor(0, 255, 0), 2)
                painter.setPen(pen)
                for det in self._latest_vision_result["found_targets"]:
                    bbox = det.get("bbox", [])
                    if len(bbox) == 4:
                        x1, y1, x2, y2 = bbox
                        painter.drawRect(int(x1), int(y1), int(x2 - x1), int(y2 - y1))
                        # Draw label
                        label = det.get("label", "")
                        if label:
                            painter.drawText(int(x1), int(y1) - 5, label)
                painter.end()
            
            # Scale image to fit preview label
            scaled = preview_img.scaled(
                self._preview_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self._preview_label.setPixmap(QPixmap.fromImage(scaled))


    def _run_current_script(self):
        script = self._editor.export_script()
        # Check if script has nodes before execution
        if not script.nodes:
            self.statusBar().showMessage("腳本沒有任何節點")
            return
        
        # Check if already running
        if self._script_runner and self._script_runner.isRunning():
            self.statusBar().showMessage("腳本正在執行中，請先停止")
            return
        
        # Display pre-execution checklist in status bar
        self.statusBar().showMessage("檢查前置條件：請確保已啟動截圖，且所有模板圖片檔案存在且可讀取...", 2000)
        
        # Gate script execution on vision frame availability
        if "frame" not in self._latest_vision_result:
            # Ensure capture is running
            if self._capture_worker is None or not self._capture_worker.is_alive():
                self.statusBar().showMessage("正在啟動畫面擷取...")
                self._start_capture()
            
            # Disable execute button during wait to prevent duplicate runs
            self._btn_exec.setEnabled(False)
            self.statusBar().showMessage("等待畫面擷取就緒...", 2000)
            
            # Wait for first frame with callback to start script
            self._wait_for_first_frame(callback=self._start_script_runner, script=script)
            return
        
        # Frame is available, start script immediately
        self._start_script_runner(script)
    
    def _start_script_runner(self, script):
        """Start the script runner thread (called when frame is ready or immediately if frame exists)"""
        # Pass a callable that returns the latest vision result for dynamic updates
        get_vision_result = lambda: self._latest_vision_result or {}
        try:
            runner = ScriptRunnerThread(self._automation, script, get_vision_result)
            self._script_runner = runner
            
            # Connect signals
            runner.nodeAboutToExecute.connect(self._on_node_about_to_execute)
            runner.nodeExecuted.connect(self._on_node_executed)
            runner.logMessage.connect(self._append_log_message)
            runner.finishedOK.connect(self._on_script_finished)
            runner.failed.connect(self._on_script_failed)
            runner.finished.connect(self._on_script_thread_finished)  # QThread finished signal
            
            # Clear previous execution states
            self._editor.clear_execution_states()
            
            # Sync breakpoints with automation controller
            self._automation.breakpoints = self._editor.get_breakpoints()
            
            # Update UI state
            self._btn_exec.setEnabled(False)
            self._btn_stop.setEnabled(True)
            self._btn_step.setEnabled(True)
            self._btn_pause.setEnabled(True)
            
            runner.start()
        except Exception:
            print("[MainWindow] start ScriptRunnerThread failed")
            traceback.print_exc()
            self._btn_exec.setEnabled(True)
            self._btn_stop.setEnabled(False)
    
    def _stop_current_script(self):
        """Stop the currently running script"""
        if self._script_runner and self._script_runner.isRunning():
            self._script_runner.stop()
            self.statusBar().showMessage("正在停止腳本執行...", 2000)
    
    def _on_script_finished(self):
        """Handle script completion"""
        self.statusBar().showMessage("腳本執行完成", 3000)
    
    def _on_script_failed(self, msg: str):
        """Handle script failure"""
        self.statusBar().showMessage(f"腳本執行失敗: {msg}", 5000)
        self._append_log_message(f"執行失敗: {msg}")
    
    def _on_node_about_to_execute(self, node_id: str):
        """Handle node about to execute - set running state"""
        self._editor.set_node_execution_state(node_id, VisualNodeItem.STATE_RUNNING)
        self._editor.highlight_active_node(node_id)
    
    def _on_node_executed(self, node_id: str, ok: bool):
        """Handle node execution signal - update visual state"""
        # Set execution state based on result (running state is set before execution)
        state = VisualNodeItem.STATE_SUCCESS if ok else VisualNodeItem.STATE_FAILED
        self._editor.set_node_execution_state(node_id, state)
        
        # Highlight the active node
        self._editor.highlight_active_node(node_id)
        
        # Clear success states after a short delay (keep failed states visible)
        if ok:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(lambda: self._clear_node_success_state(node_id))
            timer.start(500)  # Clear after 500ms
    
    def _clear_node_success_state(self, node_id: str):
        """Clear success state for a node (reset to idle if not running)"""
        item = self._editor._node_items.get(node_id)
        if item and item.get_execution_state() == VisualNodeItem.STATE_SUCCESS:
            item.set_execution_state(VisualNodeItem.STATE_IDLE)
    
    def _on_script_thread_finished(self):
        """Handle script thread completion (cleanup)"""
        self._btn_exec.setEnabled(True)
        self._btn_stop.setEnabled(False)
        self._btn_step.setEnabled(False)
        self._btn_pause.setEnabled(False)
        self._btn_pause.setChecked(False)
        # Clear all execution states
        self._editor.clear_execution_states()
        self._script_runner = None
        self._step_mode = False
        # Note: AutomationController state is reset in its finally block, so we don't need to reset it here
    
    def _wait_for_first_frame(self, callback=None, **callback_kwargs):
        """
        Wait for first frame using QTimer instead of blocking GUI thread.
        
        Args:
            callback: Optional callable to invoke when frame is ready (or on timeout)
            **callback_kwargs: Additional keyword arguments to pass to callback
        """
        if "frame" in self._latest_vision_result:
            # Frame already available, invoke callback immediately
            if callback:
                callback(**callback_kwargs)
            return
        
        # Store callback and kwargs for later invocation
        self._frame_wait_callback = callback
        self._frame_wait_callback_kwargs = callback_kwargs
        
        # Use QTimer to check periodically without blocking
        wait_timer = QTimer(self)
        wait_timer.setSingleShot(False)
        wait_timer.timeout.connect(lambda: self._check_first_frame(wait_timer))
        wait_timer.start(100)  # Check every 100ms
        
        # Set timeout to stop waiting after 2 seconds
        timeout_timer = QTimer(self)
        timeout_timer.setSingleShot(True)
        timeout_timer.timeout.connect(lambda: self._on_frame_wait_timeout(wait_timer))
        timeout_timer.start(2000)
    
    def _check_first_frame(self, timer: QTimer):
        """Check if first frame has arrived"""
        if "frame" in self._latest_vision_result:
            timer.stop()
            # Invoke callback if provided
            if hasattr(self, '_frame_wait_callback') and self._frame_wait_callback:
                callback = self._frame_wait_callback
                kwargs = getattr(self, '_frame_wait_callback_kwargs', {})
                # Clear callback references
                delattr(self, '_frame_wait_callback')
                if hasattr(self, '_frame_wait_callback_kwargs'):
                    delattr(self, '_frame_wait_callback_kwargs')
                # Invoke callback
                callback(**kwargs)
        elif not self._capture_worker or not self._capture_worker.is_alive():
            timer.stop()
            # Clear callback references on failure
            if hasattr(self, '_frame_wait_callback'):
                delattr(self, '_frame_wait_callback')
            if hasattr(self, '_frame_wait_callback_kwargs'):
                delattr(self, '_frame_wait_callback_kwargs')
    
    def _on_frame_wait_timeout(self, wait_timer: QTimer):
        """Handle timeout waiting for first frame"""
        wait_timer.stop()
        if "frame" not in self._latest_vision_result:
            self.statusBar().showMessage("警告: 畫面擷取尚未就緒，腳本可能無法正常執行。若 find_image/點擊完全沒反應，請開啟 resources.json 確認路徑與檔案是否存在。", 5000)
            # Re-enable execute button on timeout
            self._btn_exec.setEnabled(True)
        # Invoke callback even on timeout (script will start but may fail)
        if hasattr(self, '_frame_wait_callback') and self._frame_wait_callback:
            callback = self._frame_wait_callback
            kwargs = getattr(self, '_frame_wait_callback_kwargs', {})
            # Clear callback references
            delattr(self, '_frame_wait_callback')
            if hasattr(self, '_frame_wait_callback_kwargs'):
                delattr(self, '_frame_wait_callback_kwargs')
            # Invoke callback (script will start but may fail on vision-dependent nodes)
            callback(**kwargs)
    
    def _append_log_message(self, message: str):
        """Append a log message to the log panel"""
        if hasattr(self, '_log_panel') and self._log_panel:
            self._log_panel.append(message)
    
    def _toggle_recording_mode(self, enabled: bool):
        """Toggle recording mode - disabled until implemented"""
        # Feature not yet implemented - button is disabled in UI
        self.statusBar().showMessage("錄製模式功能開發中，敬請期待", 2000)
    
    def _step_execute(self):
        """Step execution - execute one node at a time"""
        if self._script_runner and self._script_runner.isRunning():
            self._automation.execution_mode = "step"
            self._automation.resume_execution()
            self.statusBar().showMessage("單步執行：已執行一個節點", 1500)
        else:
            self.statusBar().showMessage("請先開始執行腳本", 2000)
    
    def _pause_execution(self, checked: bool):
        """Pause/resume execution"""
        if checked:
            self._automation.pause_execution()
            self.statusBar().showMessage("腳本已暫停", 2000)
        else:
            self._automation.resume_execution()
            self.statusBar().showMessage("腳本已繼續", 2000)
    
    def _validate_current_script(self):
        """Validate current script and show issues"""
        issues = self._editor.validate_script()
        if not issues:
            QMessageBox.information(self, "驗證結果", "腳本驗證通過，沒有發現問題。")
        else:
            # Show dialog with issues
            from PySide6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QListWidgetItem, QPushButton
            dlg = QDialog(self)
            dlg.setWindowTitle("腳本驗證結果")
            layout = QVBoxLayout(dlg)
            list_widget = QListWidget()
            for node_id, issue in issues:
                item_text = f"{node_id}: {issue}" if node_id else issue
                list_widget.addItem(QListWidgetItem(item_text))
            layout.addWidget(list_widget)
            
            def on_item_clicked(item: QListWidgetItem):
                # Extract node_id from item text
                text = item.text()
                if ":" in text:
                    node_id = text.split(":")[0].strip()
                    if node_id:
                        # Select the node in editor
                        self._editor.highlight_active_node(node_id)
            
            list_widget.itemDoubleClicked.connect(on_item_clicked)
            
            btn_close = QPushButton("關閉")
            btn_close.clicked.connect(dlg.accept)
            layout.addWidget(btn_close)
            dlg.exec()

    def _on_undo(self):
        """Handle undo button click"""
        if not self._editor:
            return
        success = self._editor.undo()
        if success:
            self.statusBar().showMessage("已撤銷", 1500)
        else:
            self.statusBar().showMessage("無法撤銷：已到達歷史記錄開頭", 2000)

    def _on_redo(self):
        """Handle redo button click"""
        if not self._editor:
            return
        success = self._editor.redo()
        if success:
            self.statusBar().showMessage("已重做", 1500)
        else:
            self.statusBar().showMessage("無法重做：已到達歷史記錄結尾", 2000)

    def _handle_image_drop(self, node_id: str, pixmap: QPixmap):
        """Handle image drop on a find_image node - register as template and update node"""
        try:
            # Find the node
            node = self._editor._find_node(node_id) if self._editor else None
            if not node or node.type != 'find_image':
                return
            
            # Use shared helper function for consistent template registration
            tmpl_name, abs_path = register_inline_image_template(pixmap, self._sidebar)
            if not tmpl_name or not abs_path:
                QMessageBox.critical(self, "錯誤", "保存圖片失敗")
                return
            
            # Update node's template_name parameter
            node.params["template_name"] = tmpl_name
            if self._editor:
                self._editor.nodeParamsChanged.emit(node_id, node)
                self._editor._emit_changed()
            
            # Refresh properties panel if this node is selected
            if hasattr(self, '_properties') and self._properties:
                sel = self._editor._selected_node_id() if self._editor else None
                if sel == node_id:
                    self._properties.set_node(node_id, node)
        except Exception:
            print("[MainWindow] _handle_image_drop failed")
            traceback.print_exc()

    def _window_intersects_region(self, region: dict) -> bool:
        geo = self.frameGeometry()
        wx, wy, ww, wh = geo.x(), geo.y(), geo.width(), geo.height()
        rx, ry, rw, rh = region["left"], region["top"], region["width"], region["height"]
        no_overlap = (wx + ww) <= rx or (rx + rw) <= wx or (wy + wh) <= ry or (ry + rh) <= wy
        return not no_overlap

    def _on_script_renamed(self, old_name: str, new_name: str):
        # Save current editor state before rename
        if self._current_script_name == old_name:
            try:
                self._script_cache[old_name] = self._editor.export_script()
            except Exception:
                pass
        
        # Move VisualScript from old to new name in cache
        if old_name in self._script_cache:
            script = self._script_cache.pop(old_name)
            # Update script's id and name
            script.id = new_name
            script.name = new_name
            # Update all node ids if they reference the script name
            # (This is a safety measure, though node ids are typically independent)
            self._script_cache[new_name] = script
        else:
            # If not in cache, create blank one
            self._script_cache[new_name] = self._create_blank_script(new_name)
        
        # Update current script name if it was the renamed one
        if self._current_script_name == old_name:
            self._current_script_name = new_name
            try:
                self._editor.load_script(self._script_cache[new_name])
            except Exception:
                pass
        
        # Update sidebar list (already done by ResourceSidebar, but ensure sync)
        try:
            self._save_scripts_to_disk()
        except Exception:
            print("[MainWindow] save after rename failed")
            traceback.print_exc()

    def _on_script_duplicated(self, base_name: str, new_name: str):
        # Save current editor state before duplication
        if self._current_script_name == base_name:
            try:
                self._script_cache[base_name] = self._editor.export_script()
            except Exception:
                pass
        
        # Deep copy the base script
        if base_name in self._script_cache:
            import copy
            base_script = self._script_cache[base_name]
            # Create deep copy of nodes and connections
            new_nodes = []
            node_id_mapping = {}  # old_id -> new_id
            
            # First pass: create new nodes with new ids
            for i, node in enumerate(base_script.nodes):
                new_id = f"node_{len(new_nodes)+1}"
                node_id_mapping[node.id] = new_id
                new_node = copy.deepcopy(node)
                new_node.id = new_id
                new_nodes.append(new_node)
            
            # Second pass: update connections with new node ids
            new_connections = {}
            for src_id, dst_id in base_script.connections.items():
                new_src = node_id_mapping.get(src_id, src_id)
                new_dst = node_id_mapping.get(dst_id, dst_id)
                new_connections[new_src] = new_dst
            
            # Third pass: update condition/loop node next_* parameter references
            for node in new_nodes:
                if node.type == "condition":
                    # Update next_true and next_false references
                    if "next_true" in node.params and node.params["next_true"]:
                        old_id = node.params["next_true"]
                        node.params["next_true"] = node_id_mapping.get(old_id, old_id)
                    if "next_false" in node.params and node.params["next_false"]:
                        old_id = node.params["next_false"]
                        node.params["next_false"] = node_id_mapping.get(old_id, old_id)
                elif node.type == "loop":
                    # Update next_body and next_after references
                    if "next_body" in node.params and node.params["next_body"]:
                        old_id = node.params["next_body"]
                        node.params["next_body"] = node_id_mapping.get(old_id, old_id)
                    if "next_after" in node.params and node.params["next_after"]:
                        old_id = node.params["next_after"]
                        node.params["next_after"] = node_id_mapping.get(old_id, old_id)
            
            # Fourth pass: duplicate and remap groups field
            # Groups are kept in sync with node ID remapping during duplication
            new_groups = {}
            for group_name, node_ids in base_script.groups.items():
                remapped_node_ids = [node_id_mapping.get(old_id, old_id) for old_id in node_ids]
                new_groups[group_name] = remapped_node_ids
            
            # Create new script
            new_script = VisualScript(
                id=new_name,
                name=new_name,
                nodes=new_nodes,
                connections=new_connections,
                groups=new_groups
            )
            self._script_cache[new_name] = new_script
        else:
            # If base not in cache, create blank
            self._script_cache[new_name] = self._create_blank_script(new_name)
        
        # Reload sidebar to show new name (execute regardless of which branch was taken)
        try:
            self._sidebar.set_scripts(list(self._script_cache.keys()))
            self._save_scripts_to_disk()
        except Exception:
            print("[MainWindow] update sidebar/save after duplicate failed")
            traceback.print_exc()

    def _on_scripts_changed(self, names: list[str]):
        # Persist immediately and keep cache in sync
        # Sidebar does not persist scripts; MainWindow owns script IO
        # Reconcile cache entries - only handle deletions and pure new additions
        # Rename/duplicate are handled by their specific handlers
        to_remove = [k for k in list(self._script_cache.keys()) if k not in names]
        for k in to_remove:
            self._script_cache.pop(k, None)
        for name in names:
            if name not in self._script_cache:
                self._script_cache[name] = self._create_blank_script(name)
        
        # Handle deletion of currently selected script
        if self._current_script_name and self._current_script_name not in names:
            if names:
                # Switch to first available script
                # Set _current_script_name to None FIRST to prevent _on_sidebar_script_selected
                # from saving the deleted script's content to the new script's cache
                self._current_script_name = None
                self._on_sidebar_script_selected(names[0])
            else:
                # No scripts left, create blank script and clear editor
                self._current_script_name = None
                # Clear cache to reflect that no scripts remain
                self._script_cache.clear()
                blank_script = self._create_blank_script("")
                try:
                    self._editor.load_script(blank_script)
                except Exception:
                    pass
        
        try:
            self._save_scripts_to_disk()
        except Exception:
            print("[MainWindow] save_scripts_to_disk in _on_scripts_changed failed")
            traceback.print_exc()

    def _on_templates_changed(self, mapping: dict[str, str]):
        # Templates persist remains in ResourceSidebar
        pass

    def moveEvent(self, event):
        """Update stored window geometry when window moves"""
        super().moveEvent(event)
        try:
            geo = self.frameGeometry()
            self._window_geometry = {
                "x": geo.x(),
                "y": geo.y(),
                "width": geo.width(),
                "height": geo.height()
            }
        except RuntimeError:
            print("[MainWindow] moveEvent geometry access after close")
        except Exception:
            traceback.print_exc()
    
    def resizeEvent(self, event):
        """Update stored window geometry when window resizes"""
        super().resizeEvent(event)
        try:
            geo = self.frameGeometry()
            self._window_geometry = {
                "x": geo.x(),
                "y": geo.y(),
                "width": geo.width(),
                "height": geo.height()
            }
        except RuntimeError:
            print("[MainWindow] resizeEvent geometry access after close")
        except Exception:
            traceback.print_exc()

    def closeEvent(self, event):
        # Set flag to prevent signal emission from background thread
        self._is_closing = True
        
        # Stop capture worker before closing to prevent background thread issues
        if self._capture_worker is not None:
            try:
                self._capture_worker.stop()
                # Wait a brief moment for the worker to finish current frame processing
                import time
                self._capture_worker.join(timeout=0.5)
            except Exception:
                print("[MainWindow] stop capture worker failed")
                traceback.print_exc()
            self._capture_worker = None
        # Stop script runner cleanly by calling stop() method to set cancellation flag
        if hasattr(self, '_script_runner') and self._script_runner is not None:
            try:
                if self._script_runner.isRunning():
                    # Call stop() to set the internal cancellation flag
                    self._script_runner.stop()
                    # Wait for thread to exit (timeout in milliseconds)
                    if not self._script_runner.wait(1000):  # Wait up to 1 second
                        print("[MainWindow] ScriptRunnerThread did not exit within timeout")
                # Clear reference after shutdown
                self._script_runner = None
            except Exception:
                print("[MainWindow] stop script runner failed")
                traceback.print_exc()
                # Ensure reference is cleared even on error
                self._script_runner = None
        
        try:
            self._sidebar.persist()
        except Exception:
            pass
        try:
            self._save_scripts_to_disk()
        except Exception:
            pass
        super().closeEvent(event)

    def _schedule_autosave(self):
        """Schedule an autosave after a delay (debounced)"""
        # Stop any existing timer and restart it
        self._autosave_timer.stop()
        self._autosave_timer.start(1500)  # 1.5 second delay

    def _autosave_scripts(self):
        """Called by autosave timer to save scripts after inactivity period"""
        self._save_scripts_to_disk()

    def _save_scripts_to_disk(self):
        # visual_scripts.json is the authoritative storage for all script definitions.
        # This file contains both script names and their full content (nodes, connections).
        # Script names are derived from this file when loading, not from scripts.json.
        # Ensure cache contains latest editor state for current script
        if self._current_script_name:
            try:
                self._script_cache[self._current_script_name] = self._editor.export_script()
            except Exception:
                print("[MainWindow] export current script failed during save")
                traceback.print_exc()
        data = {
            "version": "1.0",
            "scripts": [self._script_cache[name].to_dict() for name in sorted(self._script_cache.keys())]
        }
        import json
        file_path = os.path.join(BASE_DIR, "visual_scripts.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_scripts_from_disk(self):
        import json
        file_path = os.path.join(BASE_DIR, "visual_scripts.json")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            print("[MainWindow] load visual_scripts.json failed; starting with empty")
            traceback.print_exc()
            data = {"scripts": []}
        cache: dict[str, VisualScript] = {}
        for sd in data.get("scripts", []):
            vs = VisualScript.from_dict(sd)
            nm = vs.name or vs.id or "Unnamed"
            cache[nm] = vs
        self._script_cache = cache
        self._sidebar.set_scripts(list(cache.keys()))
        if cache:
            first = next(iter(cache.keys()))
            self._on_sidebar_script_selected(first)

    def _save_all_scripts_dialog(self):
        """Save all scripts to a user-selected file via file dialog"""
        import json
        # Ensure cache contains latest editor state for current script
        if self._current_script_name:
            try:
                self._script_cache[self._current_script_name] = self._editor.export_script()
            except Exception:
                pass
        
        default_path = os.path.join(BASE_DIR, "visual_scripts.json")
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存視覺腳本",
            default_path,
            "JSON Files (*.json);;All Files (*)"
        )
        
        if not file_path:
            return
        
        try:
            data = {
                "version": "1.0",
                "scripts": [self._script_cache[name].to_dict() for name in sorted(self._script_cache.keys())]
            }
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.statusBar().showMessage(f"腳本已保存至: {file_path}", 3000)
        except Exception as e:
            QMessageBox.critical(self, "保存失敗", f"無法保存腳本:\n{str(e)}")
            try:
                traceback.print_exc()
            except Exception:
                pass

    def _load_all_scripts_dialog(self):
        """Load all scripts from a user-selected file via file dialog"""
        import json
        default_path = os.path.join(BASE_DIR, "visual_scripts.json")
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "載入視覺腳本",
            default_path,
            "JSON Files (*.json);;All Files (*)"
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            cache: dict[str, VisualScript] = {}
            for sd in data.get("scripts", []):
                vs = VisualScript.from_dict(sd)
                nm = vs.name or vs.id or "Unnamed"
                cache[nm] = vs
            
            self._script_cache = cache
            self._sidebar.set_scripts(list(cache.keys()))
            
            if cache:
                first = next(iter(cache.keys()))
                self._on_sidebar_script_selected(first)
                self.statusBar().showMessage(f"腳本已載入自: {file_path}", 3000)
            else:
                self.statusBar().showMessage("載入的檔案中沒有腳本", 3000)
        except Exception as e:
            QMessageBox.critical(self, "載入失敗", f"無法載入腳本:\n{str(e)}")
            try:
                traceback.print_exc()
            except Exception:
                pass

    def _reload_scripts_now(self):
        try:
            self._load_scripts_from_disk()
            self.statusBar().showMessage("已重新載入 visual_scripts.json", 2000)
        except Exception:
            print("[MainWindow] reload scripts failed")
            traceback.print_exc()
    
    def _on_save_node_template_requested(self):
        """Handle request to save selected nodes as a node template"""
        if not self._editor:
            return
        
        # Get selected nodes
        selected_nodes = self._editor.get_selected_nodes()
        if not selected_nodes:
            QMessageBox.warning(self, "提示", "請先選中要保存為模板的節點")
            return
        
        # Ask for template name
        name, ok = QInputDialog.getText(self, "保存節點模板", "模板名稱：")
        if not ok or not name.strip():
            return
        
        # Check if name already exists
        if self._sidebar.get_node_template(name.strip()):
            reply = QMessageBox.question(
                self, "確認", f"模板 '{name.strip()}' 已存在，是否覆蓋？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
        
        # Serialize selected nodes and their connections
        # Get node IDs
        selected_node_ids = {node.id for node in selected_nodes}
        
        # Extract nodes data (convert to dict for serialization)
        nodes_data = [node.to_dict() for node in selected_nodes]
        
        # Extract connections that are between selected nodes only
        script = self._editor.export_script()
        connections_data = {}
        for src_id, dst_id in script.connections.items():
            if src_id in selected_node_ids and dst_id in selected_node_ids:
                connections_data[src_id] = dst_id
        
        # Also extract condition/loop node next_* parameters that reference selected nodes
        for node in selected_nodes:
            if node.type == "condition":
                next_true = node.params.get("next_true", "")
                next_false = node.params.get("next_false", "")
                if next_true and next_true in selected_node_ids:
                    connections_data[f"{node.id}:next_true"] = next_true
                if next_false and next_false in selected_node_ids:
                    connections_data[f"{node.id}:next_false"] = next_false
            elif node.type == "loop":
                next_body = node.params.get("next_body", "")
                next_after = node.params.get("next_after", "")
                if next_body and next_body in selected_node_ids:
                    connections_data[f"{node.id}:next_body"] = next_body
                if next_after and next_after in selected_node_ids:
                    connections_data[f"{node.id}:next_after"] = next_after
        
        # Save template via sidebar
        self._sidebar.save_node_template(name.strip(), nodes_data, connections_data)
        self.statusBar().showMessage(f"節點模板 '{name.strip()}' 已保存", 2000)
    
    def _on_node_template_activated(self, template_name: str):
        """Handle node template double-click to instantiate in editor"""
        if not self._editor:
            return
        
        # Get template from sidebar
        template = self._sidebar.get_node_template(template_name)
        if not template:
            QMessageBox.warning(self, "錯誤", f"找不到模板 '{template_name}'")
            return
        
        nodes_data = template.get("nodes", [])
        connections_data = template.get("connections", {})
        
        if not nodes_data:
            QMessageBox.warning(self, "錯誤", f"模板 '{template_name}' 沒有節點")
            return
        
        # Calculate offset to place template at viewport center
        viewport_center = self._editor._scene_view.mapToScene(
            self._editor._scene_view.viewport().rect().center()
        )
        
        # Find bounding box of template nodes to center them
        if nodes_data:
            positions = [QPointF(n.get("position", [0, 0])[0], n.get("position", [0, 0])[1]) for n in nodes_data]
            min_x = min(p.x() for p in positions)
            min_y = min(p.y() for p in positions)
            max_x = max(p.x() for p in positions)
            max_y = max(p.y() for p in positions)
            template_center = QPointF((min_x + max_x) / 2, (min_y + max_y) / 2)
            offset = viewport_center - template_center
        else:
            offset = QPointF(0, 0)
        
        # Create new nodes with unique IDs and adjusted positions
        script = self._editor.export_script()
        existing_ids = {node.id for node in script.nodes}
        
        # Generate unique IDs for new nodes
        node_id_mapping = {}  # old_id -> new_id
        new_nodes = []
        
        for node_data in nodes_data:
            # Generate unique ID
            old_id = node_data.get("id", "")
            counter = 1
            while True:
                new_id = f"node_{counter}"
                if new_id not in existing_ids:
                    break
                counter += 1
            existing_ids.add(new_id)
            node_id_mapping[old_id] = new_id
            
            # Create node with new ID and adjusted position
            pos = node_data.get("position", [0, 0])
            new_pos = QPointF(pos[0] + offset.x(), pos[1] + offset.y())
            
            new_node = VisualNode(
                id=new_id,
                type=node_data.get("type", "click"),
                params=dict(node_data.get("params", {})),
                position=new_pos,
                outputs=list(node_data.get("outputs", [])),
                comment=node_data.get("comment")
            )
            new_nodes.append(new_node)
        
        # Add nodes to script
        for node in new_nodes:
            script.nodes.append(node)
            item = VisualNodeItem(node, self._editor)
            self._editor._scene.addItem(item)
            self._editor._node_items[node.id] = item
            
            # Load comment if node has one
            if node.comment:
                comment_item = CommentItem(node.comment, node.position + QPointF(200, 0), self._editor, node.id)
                self._editor._scene.addItem(comment_item)
                self._editor._comment_items[node.id] = comment_item
        
        # Update connections with new node IDs
        # First, update node params that reference other nodes (condition/loop nodes)
        for node in new_nodes:
            if node.type == "condition":
                next_true = node.params.get("next_true", "")
                next_false = node.params.get("next_false", "")
                if next_true and next_true in node_id_mapping:
                    node.params["next_true"] = node_id_mapping[next_true]
                if next_false and next_false in node_id_mapping:
                    node.params["next_false"] = node_id_mapping[next_false]
            elif node.type == "loop":
                next_body = node.params.get("next_body", "")
                next_after = node.params.get("next_after", "")
                if next_body and next_body in node_id_mapping:
                    node.params["next_body"] = node_id_mapping[next_body]
                if next_after and next_after in node_id_mapping:
                    node.params["next_after"] = node_id_mapping[next_after]
        
        # Then update standard connections and handle special connection format
        for old_src, old_dst in connections_data.items():
            # Handle special connection format for condition/loop nodes (backward compatibility)
            if ":" in old_src:
                # Format: "node_id:param_name" -> "target_node_id"
                parts = old_src.split(":", 1)
                if len(parts) == 2:
                    old_node_id, param_name = parts
                    new_node_id = node_id_mapping.get(old_node_id)
                    new_dst = node_id_mapping.get(old_dst, old_dst)
                    if new_node_id:
                        node = self._editor._find_node(new_node_id)
                        if node:
                            node.params[param_name] = new_dst
            else:
                # Standard connection
                new_src = node_id_mapping.get(old_src, old_src)
                new_dst = node_id_mapping.get(old_dst, old_dst)
                if new_src in node_id_mapping.values() and new_dst in node_id_mapping.values():
                    script.connections[new_src] = new_dst
        
        # Rebuild edges and update history
        self._editor._rebuild_edges_from_model()
        self._editor._push_history()
        self._editor._emit_changed()
        
        self.statusBar().showMessage(f"已實例化模板 '{template_name}'", 2000)

class ScriptRunnerThread(QThread):
    nodeExecuted = Signal(str, bool)
    nodeAboutToExecute = Signal(str)  # Emit when node is about to execute
    finishedOK = Signal()
    failed = Signal(str)
    logMessage = Signal(str)  # Emit structured log messages
    def __init__(self, automation: AutomationController, script: VisualScript, get_vision_result):
        super().__init__()
        self._automation = automation
        self._script = script
        self._get_vision_result = get_vision_result
        self._should_stop = False
        self._mutex = QMutex()  # Use QMutex for thread-safe flag access
    
    def stop(self):
        """Thread-safe method to request script execution to stop"""
        self._mutex.lock()
        try:
            self._should_stop = True
        finally:
            self._mutex.unlock()
    
    def run(self):
        try:
            import time
            from datetime import datetime
            
            def log(msg: str):
                timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                self.logMessage.emit(f"[{timestamp}] {msg}")
            
            def node_about_to_execute_callback(nid: str):
                # Emit signal to MainWindow to set node to running state
                self.nodeAboutToExecute.emit(nid)
            
            def node_executed_callback(nid: str, ok: bool):
                node = self._automation._find_node(self._script, nid) if hasattr(self._automation, '_find_node') else None
                node_type = node.type if node else "unknown"
                status = "成功" if ok else "失敗"
                log(f"節點執行: {nid} ({node_type}) - {status}")
                self.nodeExecuted.emit(nid, ok)
            
            self._automation.on_node_about_to_execute = node_about_to_execute_callback
            self._automation.on_node_executed = node_executed_callback
            log("腳本執行開始")
            
            # Pass cancellation callback to automation controller
            def should_cancel():
                self._mutex.lock()
                try:
                    return self._should_stop
                finally:
                    self._mutex.unlock()
            
            self._automation.execute_visual_script(
                self._script, 
                self._get_vision_result,
                should_cancel_callback=should_cancel
            )
            
            if self._should_stop:
                log("腳本執行已停止（使用者取消）")
            else:
                log("腳本執行完成")
                self.finishedOK.emit()
        except ValueError as e:
            self.logMessage.emit(f"錯誤: {str(e)}")
            self.failed.emit(str(e))
        except Exception as e:
            try:
                traceback.print_exc()
            except Exception:
                pass
            self.logMessage.emit(f"執行異常: {str(e)}")
            self.failed.emit(str(e))
