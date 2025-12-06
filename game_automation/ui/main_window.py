from typing import Optional
import os
from PySide6.QtCore import Qt, Signal, QObject, QThread
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QMainWindow, QWidget, QSplitter, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QPushButton, QStatusBar, QFormLayout, QLineEdit, QComboBox, QDoubleSpinBox, QFileDialog, QMessageBox
from .visual_script_editor import VisualScriptEditor
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


class PropertiesPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._node: Optional[VisualNode] = None
        self._editor: Optional[VisualScriptEditor] = None
        self._sidebar: Optional[ResourceSidebar] = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        self.lbl = QLabel("屬性面板")
        layout.addWidget(self.lbl)
        self.form = QFormLayout()
        layout.addLayout(self.form)

    def attach_editor(self, editor: VisualScriptEditor):
        self._editor = editor
    
    def attach_sidebar(self, sidebar: ResourceSidebar):
        self._sidebar = sidebar

    def _clear_form(self):
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
            self.form.addRow("True 走向", edit_true)
            self.form.addRow("False 走向", edit_false)
            self.form.addRow("HSV 最小", edit_hmin)
            self.form.addRow("HSV 最大", edit_hmax)
            self.form.addRow("BGR 最小", edit_bmin)
            self.form.addRow("BGR 最大", edit_bmax)
            combo_mode.currentTextChanged.connect(lambda v: self._update_param("mode", v))
            edit_label.textChanged.connect(lambda v: self._update_param("label", v))
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
            # Template name dropdown - get from sidebar templates
            combo_template = QComboBox()
            combo_template.setEditable(True)
            combo_template.addItem("")  # Empty option
            # Get templates from sidebar if available
            if self._sidebar and hasattr(self._sidebar, '_templates'):
                for tmpl_name in sorted(self._sidebar._templates.keys()):
                    combo_template.addItem(tmpl_name)
            # Set current value
            current_template = str(node.params.get("template_name", ""))
            idx = combo_template.findText(current_template)
            if idx >= 0:
                combo_template.setCurrentIndex(idx)
            else:
                combo_template.setCurrentText(current_template)
            
            spin_confidence = QDoubleSpinBox()
            spin_confidence.setRange(0.0, 1.0)
            spin_confidence.setDecimals(2)
            spin_confidence.setSingleStep(0.05)
            spin_confidence.setValue(float(node.params.get("confidence", 0.8)))
            
            self.form.addRow("範本名稱", combo_template)
            self.form.addRow("置信度", spin_confidence)
            combo_template.currentTextChanged.connect(lambda v: self._update_param("template_name", v))
            spin_confidence.valueChanged.connect(lambda v: self._update_param("confidence", float(v)))

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
            "find_image": "找圖片"
        }
        type_name = type_names.get(node.type, node.type)
        return f"{type_name} ({node_id})"

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


class PreviewOverlay(QWidget):
    matches_updated = Signal(str)
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.preview_label = QLabel("預覽視圖", self)
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("background-color: #ffffff; color: #222222; border: 1px solid #e6e6ea;")
        layout.addWidget(self.preview_label)

    def highlight(self, node_id: str):
        self.matches_updated.emit(node_id)

    def set_image(self, qimage: QImage):
        pix = QPixmap.fromImage(qimage)
        if self.preview_label.width() > 0 and self.preview_label.height() > 0:
            pix = pix.scaled(self.preview_label.width(), self.preview_label.height(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.preview_label.setPixmap(pix)


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

        editor_preview_split = QSplitter(Qt.Vertical, self)
        editor = VisualScriptEditor(self)
        preview = PreviewOverlay(self)
        editor_preview_split.addWidget(editor)
        editor_preview_split.addWidget(preview)

        properties = PropertiesPanel(self)
        self._properties = properties  # Store reference for refresh method

        right_split.addWidget(editor_preview_split)
        right_split.addWidget(properties)

        root.addWidget(sidebar)
        root.addWidget(right_split, 1)
        self.setCentralWidget(central)

        toolbar = self.addToolBar("Main")
        btn_start = QPushButton("開始截圖", self)
        btn_exec = QPushButton("執行腳本", self)
        btn_reload = QPushButton("重新載入", self)
        btn_record = QPushButton("錄製模式 (即將推出)", self)
        btn_record.setCheckable(True)
        btn_record.setEnabled(False)  # Disable until implemented
        btn_record.setToolTip("錄製滑鼠與鍵盤操作並轉換為節點 (功能開發中)")
        btn_step = QPushButton("單步執行 (即將推出)", self)
        btn_step.setEnabled(False)  # Disable until implemented
        btn_step.setToolTip("逐步執行腳本，每次執行一個節點 (功能開發中)")
        btn_pause = QPushButton("暫停 (即將推出)", self)
        btn_pause.setEnabled(False)  # Disable until implemented
        btn_pause.setToolTip("暫停執行中的腳本 (功能開發中)")
        btn_save = QPushButton("保存")
        btn_load = QPushButton("載入")
        toolbar.addWidget(btn_start)
        toolbar.addWidget(btn_exec)
        toolbar.addWidget(btn_record)
        toolbar.addWidget(btn_step)
        toolbar.addWidget(btn_pause)
        toolbar.addWidget(btn_save)
        toolbar.addWidget(btn_load)
        toolbar.addWidget(btn_reload)

        status = QStatusBar(self)
        self.setStatusBar(status)
        status.showMessage("就緒")

        properties.attach_editor(editor)
        properties.attach_sidebar(sidebar)
        editor.nodeSelected.connect(properties.set_node)
        editor.nodeParamsChanged.connect(properties.set_node)  # Refresh properties when node params change
        preview.matches_updated.connect(editor.highlight_active_node)
        btn_start.clicked.connect(self._start_capture)
        btn_exec.clicked.connect(self._run_current_script)
        btn_record.toggled.connect(self._toggle_recording_mode)
        btn_step.clicked.connect(self._step_execute)
        btn_pause.clicked.connect(self._pause_execution)
        btn_save.clicked.connect(self._save_all_scripts_dialog)
        btn_load.clicked.connect(self._load_all_scripts_dialog)
        editor.executeRequested.connect(self._run_current_script)
        
        # Store references to execution control buttons
        self._btn_record = btn_record
        self._btn_step = btn_step
        self._btn_pause = btn_pause
        self._recording_mode = False
        self._execution_paused = False
        
        # Store references before setting up callbacks that use them
        self._editor = editor
        self._preview = preview
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
        editor.scriptChanged.connect(lambda _vs: self._refresh_current_node_properties())
        editor.scriptChanged.connect(lambda _vs: self._save_scripts_to_disk())
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
        self.statusBar().showMessage(reason, 3000)  # Show for 3 seconds
    
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
        self._preview.set_image(qimg)
        self.statusBar().showMessage(f"FPS: {fps:.1f}")

    def _run_current_script(self):
        script = self._editor.export_script()
        # Check if script has nodes before execution
        if not script.nodes:
            self.statusBar().showMessage("腳本沒有任何節點")
            return
        
        # Ensure capture is running before executing the script
        if self._capture_worker is None or not self._capture_worker.is_alive():
            self.statusBar().showMessage("正在啟動畫面擷取...")
            self._start_capture()
            # Wait briefly for the first frame to arrive
            import time
            max_wait = 2.0  # Maximum wait time in seconds
            wait_interval = 0.1  # Check every 100ms
            waited = 0.0
            while waited < max_wait:
                if "frame" in self._latest_vision_result:
                    break
                time.sleep(wait_interval)
                waited += wait_interval
            if "frame" not in self._latest_vision_result:
                self.statusBar().showMessage("警告: 畫面擷取尚未就緒，腳本可能無法正常執行", 3000)
        
        # Pass a callable that returns the latest vision result for dynamic updates
        get_vision_result = lambda: self._latest_vision_result or {}
        try:
            runner = ScriptRunnerThread(self._automation, script, get_vision_result)
            self._script_runner = runner
            runner.nodeExecuted.connect(lambda nid, ok: self._editor.highlight_active_node(nid))
            runner.finishedOK.connect(lambda: self.statusBar().showMessage("腳本執行完成"))
            runner.failed.connect(lambda msg: self.statusBar().showMessage(f"腳本執行失敗: {msg}"))
            runner.start()
        except Exception:
            print("[MainWindow] start ScriptRunnerThread failed")
            traceback.print_exc()
    
    def _toggle_recording_mode(self, enabled: bool):
        """Toggle recording mode - disabled until implemented"""
        # Feature not yet implemented - button is disabled in UI
        self.statusBar().showMessage("錄製模式功能開發中，敬請期待", 2000)
    
    def _step_execute(self):
        """Step execution - disabled until implemented"""
        # Feature not yet implemented - button is disabled in UI
        self.statusBar().showMessage("單步執行功能開發中，敬請期待", 2000)
    
    def _pause_execution(self):
        """Pause execution - disabled until implemented"""
        # Feature not yet implemented - button is disabled in UI
        self.statusBar().showMessage("暫停功能開發中，敬請期待", 2000)

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
            
            # Create new script
            new_script = VisualScript(
                id=new_name,
                name=new_name,
                nodes=new_nodes,
                connections=new_connections
            )
            self._script_cache[new_name] = new_script
        else:
            # If base not in cache, create blank
            self._script_cache[new_name] = self._create_blank_script(new_name)
        
        # Reload sidebar to show new name
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
        try:
            if hasattr(self, '_script_runner') and self._script_runner is not None:
                self._script_runner.requestInterruption()
                self._script_runner.quit()
                self._script_runner.wait(500)
        except Exception:
            print("[MainWindow] stop script runner failed")
            traceback.print_exc()
        
        try:
            self._sidebar.persist()
        except Exception:
            pass
        try:
            self._save_scripts_to_disk()
        except Exception:
            pass
        super().closeEvent(event)

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
class ScriptRunnerThread(QThread):
    nodeExecuted = Signal(str, bool)
    finishedOK = Signal()
    failed = Signal(str)
    def __init__(self, automation: AutomationController, script: VisualScript, get_vision_result):
        super().__init__()
        self._automation = automation
        self._script = script
        self._get_vision_result = get_vision_result
    def run(self):
        try:
            self._automation.on_node_executed = lambda nid, ok: self.nodeExecuted.emit(nid, ok)
            self._automation.execute_visual_script(self._script, self._get_vision_result)
            self.finishedOK.emit()
        except ValueError as e:
            self.failed.emit(str(e))
        except Exception as e:
            try:
                traceback.print_exc()
            except Exception:
                pass
            self.failed.emit(str(e))
