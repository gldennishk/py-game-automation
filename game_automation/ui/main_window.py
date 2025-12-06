import cv2
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QFrame,
    QPushButton, QLabel, QTabWidget, QStatusBar, QPlainTextEdit
)
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import Qt, Signal, QObject

from ui.themes import LIGHT_QSS
from ui.widgets import ActionSequenceEditor
from core.screen_capture import ScreenCaptureWorker
from core.image_processor import ImageProcessor
from core.actions import ActionSequence
from core.automation import AutomationController
from core.performance_monitor import PerformanceMonitor
from core.scaling import set_per_monitor_dpi_awareness, detect_scale_factor


class FrameBus(QObject):
    frame_arrived = Signal(object, float)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Game Automation Studio")
        self.resize(1280, 720)
        self.setStyleSheet(LIGHT_QSS)

        set_per_monitor_dpi_awareness()
        self.scale_factor = detect_scale_factor(1920)

        self.frame_bus = FrameBus()
        self.frame_bus.frame_arrived.connect(self.on_frame)

        self.capture_worker = None
        self.processor = ImageProcessor()
        self.current_sequence = ActionSequence()
        self.automation = AutomationController(scale_factor=self.scale_factor)
        self.perf = PerformanceMonitor(window_seconds=1.0)
        self.last_vision_result = None
        self._processing = False
        self._last_process_ts = 0.0
        self._process_min_interval = 1.0 / 15.0

        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        root = QHBoxLayout(central)
        self.setCentralWidget(central)

        side = QFrame()
        side.setObjectName("SideBar")
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(12, 12, 12, 12)
        side_layout.setSpacing(12)

        self.btn_start = QPushButton("開始截圖")
        self.btn_stop = QPushButton("停止截圖")
        self.btn_stop.setEnabled(False)
        self.btn_run_seq = QPushButton("執行腳本")

        self.lbl_fps = QLabel("FPS: -")
        self.lbl_latency = QLabel("Latency: - ms")

        side_layout.addWidget(self.btn_start)
        side_layout.addWidget(self.btn_stop)
        side_layout.addWidget(self.btn_run_seq)
        side_layout.addSpacing(12)
        side_layout.addWidget(self.lbl_fps)
        side_layout.addWidget(self.lbl_latency)
        side_layout.addStretch()

        self.tabs = QTabWidget()

        self.preview_label = QLabel("預覽")
        self.preview_label.setAlignment(Qt.AlignCenter)
        preview_container = QWidget()
        v_preview = QVBoxLayout(preview_container)
        v_preview.addWidget(self.preview_label)
        self.tabs.addTab(preview_container, "Preview")

        self.script_editor = ActionSequenceEditor()
        self.tabs.addTab(self.script_editor, "Script")

        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        self.tabs.addTab(self.log_edit, "Log")

        root.addWidget(side, 0)
        root.addWidget(self.tabs, 1)

        status = QStatusBar()
        self.setStatusBar(status)

        self.btn_start.clicked.connect(self.start_capture)
        self.btn_stop.clicked.connect(self.stop_capture)
        self.btn_run_seq.clicked.connect(self.run_current_sequence)
        self.script_editor.sequenceChanged.connect(self.on_sequence_changed)
        self.script_editor.logMessage.connect(self.append_log)

    def start_capture(self):
        if self.capture_worker:
            return
        region = {"top": 0, "left": 0, "width": 1920, "height": 1080}
        self.capture_worker = ScreenCaptureWorker(
            region=region,
            fps=30,
            callback=lambda f, t: self.frame_bus.frame_arrived.emit(f, t),
        )
        self.capture_worker.start()
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.append_log("Capture started")

    def stop_capture(self):
        if self.capture_worker:
            self.capture_worker.stop()
            self.capture_worker = None
            self.append_log("Capture stopped")
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)

    def on_frame(self, frame, ts):
        self.perf.tick(ts)
        # 預覽始終更新，但匹配處理以節流方式執行，避免卡死
        if (not self._processing) and (ts - self._last_process_ts >= self._process_min_interval):
            self._processing = True
            try:
                result = self.processor.process_frame(frame)
                self.last_vision_result = result
                self._last_process_ts = ts
                self.lbl_latency.setText(f"Latency: {result['latency_ms']:.1f} ms")
            finally:
                self._processing = False

        fps_val = self.perf.fps()
        self.lbl_fps.setText(f"FPS: {fps_val:.0f}")

        rgb = cv2.cvtColor(cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR), cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pix = QPixmap.fromImage(qimg).scaled(
            self.preview_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.preview_label.setPixmap(pix)

    def run_current_sequence(self):
        if not self.last_vision_result:
            self.append_log("No vision result to run sequence")
            return
        seq = self.current_sequence
        if not seq.actions:
            self.append_log("Sequence is empty")
            return
        self.append_log(f"Running sequence: {seq.name}")
        self.automation.run_sequence(seq, self.last_vision_result)
        self.append_log("Sequence run finished")

    def on_sequence_changed(self, seq: ActionSequence):
        self.current_sequence = seq
        self.append_log(f"Sequence updated: {seq.name}, {len(seq.actions)} actions")

    def append_log(self, msg: str):
        self.log_edit.appendPlainText(msg)

