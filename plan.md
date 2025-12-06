
你说：
請PLAN 遊戲自動化腳本+pyside6GUI+介面美觀,現代化,易用性


用 mss 截圖（高 FPS、低延遲）→ OpenCV /pyautogui 來移動滑鼠、點擊、按鍵。

用 mss 截圖（高 FPS、低延遲）→ OpenCV / OCR / 分析 → 圖的字

pyautogui.screenshot()  → 算 bbox 中心  → pyautogui 移動＋點擊

                       1920*1080, 縮放125%



改做以下高性能屏幕自动化系统，要求实现以下功能模块：

1. 屏幕捕获模块：
- 使用mss库实现高帧率(≥60FPS)、低延迟(<50ms)的屏幕截图功能
- 支持1920×1080分辨率下125%缩放比例的屏幕区域捕获
- 实现显示器环境下的精准区域捕获

2. 图像处理与分析模块：
- 集成OpenCV进行实时图像处理
- 实现OCR功能识别屏幕中的文字内容
- 开发图像特征分析算法识别特定界面元素

3. 自动化控制模块：
- 使用pyautogui实现精确的鼠标控制：
  * 计算目标区域的边界框(bbox)中心坐标
  * 实现平滑的鼠标移动轨迹
  * 支持左/右键点击操作
- 实现键盘按键模拟功能
- 开发动作序列编排系统

4. 性能优化要求：
- 确保从截图到动作执行的端到端延迟<100ms
- 实现多线程处理架构保证高吞吐量
- 开发资源占用监控机制

5. 兼容性要求：
- 支持Windows11系统
- 适配125%系统缩放设置
- 提供分辨率自适应处理
ChatGPT 说：

已思考 7s
先給你一個完整「系統設計＋程式骨架」方案，你可以直接按這個結構實作 / 擴充。
下面我會用 繁中說明、英文當程式名，方便對照。

一、整體架構概念
目標：

高 FPS mss 截圖 → OpenCV / OCR / 視覺分析 → pyautogui 控制 → 全部包在一個 PySide6 現代化 GUI 裡。

建議拆成 4 個層：

Capture Layer（截圖層）

用 mss 在獨立執行緒高 FPS 截圖

支援指定區域、整螢幕、1920×1080 @ 125% DPI

Vision Layer（視覺處理層）

用 cv2 做模板匹配、顏色檢測、輪廓分析

用 OCR（如 pytesseract，先預留介面）做文字辨識

Automation Layer（自動化層）

用 pyautogui 控制滑鼠 / 鍵盤

提供「動作序列」抽象：點擊 / 按鍵 / 延遲 / 條件判斷

GUI Layer（介面層 / PySide6）

設定截圖區域、顯示預覽、啟停自動化

可視化腳本編輯（列表 + 可儲存/載入）

狀態列顯示 FPS / 延遲 / CPU / RAM

二、專案結構建議
game_automation/
│  main.py                 # 入口：啟動 PySide6 GUI
│
├─ core/
│   screen_capture.py      # mss 截圖 worker
│   image_processor.py     # OpenCV + OCR 分析
│   automation.py          # pyautogui 動作 & 序列
│   actions.py             # 動作模型 / 序列定義
│   performance_monitor.py # 資源占用監控
│   scaling.py             # DPI / 解析度自適應
│
└─ ui/
    main_window.py         # 主視窗
    widgets.py             # 自訂控件（預覽、腳本編輯器）
    themes.py              # 樣式（深色、現代化）
三、關鍵流程（從截圖到動作）
ScreenCaptureWorker（Thread / QThread）

用 mss.mss().grab(region) 以 ≥60 FPS 截圖

每次抓到 frame（numpy array）後丟到 queue 或用 PySide signal 發給 GUI & Vision

ImageProcessorWorker

接收 frame：

做影像處理（灰階、二值化、邊緣檢測）

OCR：從指定 ROI 讀文字

元素檢測：模板匹配、顏色 / 形狀判斷

輸出「分析結果」物件，例如：

{
    "timestamp": ...,
    "fps": ...,
    "latency_ms": ...,
    "found_targets": [
        {"bbox": (x1, y1, x2, y2), "confidence": 0.92, "label": "START_BUTTON"}
    ],
    "ocr_text": "..."
}
AutomationController

接收分析結果，判斷是否要執行某個「動作序列」

使用 pyautogui：

計算 bbox 中心：cx = (x1 + x2) // 2

平滑移動：pyautogui.moveTo(cx, cy, duration=0.1, tween=pyautogui.easeInOutQuad)

點擊 / 鍵盤事件

PerformanceMonitor

用 psutil（可選）讀 CPU / RAM

估算端到端延遲（frame 產生 timestamp → 動作執行 timestamp）

顯示在 GUI 狀態列，確保 <100ms

四、DPI / 解析度 & 125% 縮放處理
Windows 11 + 125% 縮放時會有兩組座標：

邏輯座標（Windows / GUI 認知的）

實際像素座標（螢幕真實像素，mss / pyautogui 用的）

處理方式：

啟動程式時設定 DPI Aware（可選）：

import ctypes
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-monitor DPI
except Exception:
    pass
用 Windows API / pyautogui 判斷螢幕實際解析度：

import pyautogui
screen_w, screen_h = pyautogui.size()
# 1920x1080, 125% 時，邏輯解析度會不同，要以這個為準
在 GUI 裡選擇截圖區域時，記錄的是「邏輯座標」，送去 mss / pyautogui 前做縮放：

SCALE = 1.25  # 可以自動偵測：screen_w / 1920
def logical_to_physical(x, y):
    return int(x * SCALE), int(y * SCALE)
五、PySide6 GUI 設計（美觀、現代化）
整體佈局
用 QMainWindow + 深色風格：

左側側邊欄（QFrame / QVBoxLayout）

「啟動 / 停止」按鈕（大顆圓角）

FPS / 延遲 / CPU / RAM 小卡片

配置區（截圖區域、分辨率、DPI factor 下拉）

中央主區域（Tab Widget）

Preview Tab：顯示即時縮圖（用 QLabel 顯示 QPixmap）

Script Tab：動作序列列表 + 編輯表單

Log Tab：文字 log（QPlainTextEdit）

簡化 GUI 風格（stylesheet）
# ui/themes.py
DARK_QSS = """
QMainWindow {
    background-color: #151515;
}
QFrame#SideBar {
    background-color: #1f1f1f;
    border-right: 1px solid #333;
}
QPushButton {
    background-color: #2d89ef;
    border-radius: 8px;
    padding: 8px 16px;
    color: white;
    font-weight: 600;
}
QPushButton:disabled {
    background-color: #555;
}
QLabel, QCheckBox, QRadioButton, QLineEdit, QComboBox {
    color: #f0f0f0;
    font-size: 12px;
}
"""
六、核心類別介面設計
1. ScreenCaptureWorker（mss 截圖）
# core/screen_capture.py
import time
import threading
import mss
import numpy as np

class ScreenCaptureWorker(threading.Thread):
    def __init__(self, region, fps=60, callback=None):
        super().__init__(daemon=True)
        self.region = region  # dict: {"top":..., "left":..., "width":..., "height":...}
        self.fps = fps
        self.callback = callback  # 調用: callback(frame, timestamp)
        self._running = threading.Event()
        self._running.set()
        self._mss = mss.mss()

    def run(self):
        frame_interval = 1.0 / self.fps
        while self._running.is_set():
            start = time.perf_counter()
            img = self._mss.grab(self.region)
            frame = np.array(img)  # BGRA
            ts = time.time()
            if self.callback:
                self.callback(frame, ts)
            elapsed = time.perf_counter() - start
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def stop(self):
        self._running.clear()
2. ImageProcessor（OpenCV + OCR）
# core/image_processor.py
import cv2
import time

class ImageProcessor:
    def __init__(self, ocr_engine=None):
        self.ocr_engine = ocr_engine  # 可注入 pytesseract 等

    def process_frame(self, frame_bgra):
        t0 = time.perf_counter()

        frame = cv2.cvtColor(frame_bgra, cv2.COLOR_BGRA2BGR)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # TODO: 自訂模板匹配 / 元素識別
        found_targets = []

        # OCR 示例（如果有：
        ocr_text = ""
        if self.ocr_engine:
            ocr_text = self.ocr_engine(gray)

        latency = (time.perf_counter() - t0) * 1000.0
        return {
            "frame": frame,
            "gray": gray,
            "latency_ms": latency,
            "found_targets": found_targets,
            "ocr_text": ocr_text,
        }
3. AutomationController（pyautogui 控制）
# core/automation.py
import time
import pyautogui

pyautogui.FAILSAFE = False

def bbox_center(bbox):
    x1, y1, x2, y2 = bbox
    return (x1 + x2) // 2, (y1 + y2) // 2

class AutomationController:
    def __init__(self, scale_factor=1.25):
        self.scale_factor = scale_factor

    def _to_physical(self, x, y):
        return int(x * self.scale_factor), int(y * self.scale_factor)

    def smooth_move_and_click(self, bbox, button="left", move_duration=0.08):
        cx, cy = bbox_center(bbox)
        px, py = self._to_physical(cx, cy)
        pyautogui.moveTo(px, py, duration=move_duration)
        pyautogui.click(button=button)

    def key_press(self, key, duration=0.05):
        pyautogui.keyDown(key)
        time.sleep(duration)
        pyautogui.keyUp(key)
4. 動作序列模型（簡單版）
# core/actions.py
from dataclasses import dataclass, field
from typing import List, Literal, Dict, Any

ActionType = Literal["click", "key", "sleep"]

@dataclass
class Action:
    type: ActionType
    params: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ActionSequence:
    name: str
    actions: List[Action]

七、PySide6 主視窗骨架
# main.py
import sys
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
# ui/main_window.py
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QFrame,
    QPushButton, QLabel, QTabWidget, QStatusBar
)
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import Qt, Signal, QObject

from ui.themes import DARK_QSS
from core.screen_capture import ScreenCaptureWorker
from core.image_processor import ImageProcessor

import cv2

class FrameBus(QObject):
    frame_arrived = Signal(object, float)  # frame, timestamp

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Game Automation Studio")
        self.resize(1280, 720)
        self.setStyleSheet(DARK_QSS)

        self.frame_bus = FrameBus()
        self.frame_bus.frame_arrived.connect(self.on_frame)

        self._build_ui()
        self.capture_worker = None
        self.processor = ImageProcessor()

    def _build_ui(self):
        central = QWidget()
        root = QHBoxLayout(central)
        self.setCentralWidget(central)

        # 左側側邊欄
        side = QFrame()
        side.setObjectName("SideBar")
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(12, 12, 12, 12)
        side_layout.setSpacing(12)

        self.btn_start = QPushButton("開始")
        self.btn_stop = QPushButton("停止")
        self.btn_stop.setEnabled(False)

        self.lbl_fps = QLabel("FPS: -")
        self.lbl_latency = QLabel("Latency: - ms")

        side_layout.addWidget(self.btn_start)
        side_layout.addWidget(self.btn_stop)
        side_layout.addSpacing(12)
        side_layout.addWidget(self.lbl_fps)
        side_layout.addWidget(self.lbl_latency)
        side_layout.addStretch()

        # 中央區域
        tabs = QTabWidget()
        # Preview tab
        self.preview_label = QLabel("預覽")
        self.preview_label.setAlignment(Qt.AlignCenter)
        tabs.addTab(self.preview_label, "Preview")
        # Script tab / Log tab 可以之後補

        root.addWidget(side, 0)
        root.addWidget(tabs, 1)

        # status bar
        status = QStatusBar()
        self.setStatusBar(status)

        self.btn_start.clicked.connect(self.start_capture)
        self.btn_stop.clicked.connect(self.stop_capture)

    def start_capture(self):
        if self.capture_worker:
            return
        region = {"top": 0, "left": 0, "width": 1920, "height": 1080}
        self.capture_worker = ScreenCaptureWorker(
            region=region,
            fps=60,
            callback=lambda f, t: self.frame_bus.frame_arrived.emit(f, t),
        )
        self.capture_worker.start()
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)

    def stop_capture(self):
        if self.capture_worker:
            self.capture_worker.stop()
            self.capture_worker = None
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)

    def on_frame(self, frame, ts):
        # TODO: 可放到另一起 thread 處理，這裡簡化
        result = self.processor.process_frame(frame)
        self.lbl_latency.setText(f"Latency: {result['latency_ms']:.1f} ms")

        # 更新 preview（縮圖）
        rgb = cv2.cvtColor(result["frame"], cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pix = QPixmap.fromImage(qimg).scaled(
            self.preview_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.preview_label.setPixmap(pix)
八、性能優化建議（達成 <100ms）
截圖層

固定區域（不要每次重算 region）

使用單一 mss() 實例

避免不必要的圖像複製

視覺層

能用灰階就不要彩色

模板縮小 / 多解析度匹配

OCR 只在必要區域執行，而不是整張圖

多線程架構

至少 2 條 Thread：

Capture → 專心快速抓 frame

Processing/Automation → 處理上一張 frame（不要阻塞 Capture）

監控

定期（例如 1 秒）計算 FPS：
frame 計數 / 時間差

記錄每一階段耗時：截圖、處理、動作

如果你願意，下一步我可以幫你把 動作序列編輯 GUI（Script Tab） 也設計成可視化：
例如每一行顯示「動作類型、參數」＋ 上下移動、刪除按鈕，並支援 JSON 匯入 / 匯出。

你说：
願意
ChatGPT 说：

已思考 15s
好，那我直接幫你把 「Script 腳本編輯 Tab」完整設計 + 程式骨架 生出來，你可以直接複製進專案用。

重點目標：

在 PySide6 GUI 裡有一個 視覺化腳本編輯器

可以：新增動作、刪除、上下移動、編輯參數

支援 JSON 匯入 / 匯出 腳本

動作序列結構清晰，之後很好接到自動化控制（AutomationController）

1. 動作資料結構（core/actions.py）
先把動作 / 序列的資料結構補強，增加 JSON 轉換方便 Script Editor 使用。

# core/actions.py
from dataclasses import dataclass, field, asdict
from typing import List, Literal, Dict, Any
import json

ActionType = Literal["click", "key", "sleep"]

@dataclass
class Action:
    type: ActionType
    params: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ActionSequence:
    name: str = "Unnamed Sequence"
    actions: List[Action] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "actions": [asdict(a) for a in self.actions],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ActionSequence":
        name = data.get("name", "Imported Sequence")
        actions_data = data.get("actions", [])
        actions: List[Action] = []
        for a in actions_data:
            actions.append(Action(
                type=a.get("type", "click"),
                params=a.get("params", {}),
            ))
        return cls(name=name, actions=actions)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_json(cls, text: str) -> "ActionSequence":
        data = json.loads(text)
        return cls.from_dict(data)
2. Script Editor Widget（ui/widgets.py）
這個 widget 會：

顯示一個 Table：每列是一個 Action

欄位：

類型（下拉：click/key/sleep）

參數（JSON 字串）

操作按鈕（上移 / 下移 / 刪除）

底部按鈕：

Add Action

Load JSON

Save JSON

# ui/widgets.py
from typing import List
import json
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QComboBox, QLineEdit, QToolButton, QFileDialog, QMessageBox, QPushButton,
    QLabel
)

from core.actions import Action, ActionSequence, ActionType

class ActionSequenceEditor(QWidget):
    sequenceChanged = Signal(ActionSequence)
    logMessage = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sequence = ActionSequence()
        self._build_ui()

    # ---------- UI ----------
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        title_row = QHBoxLayout()
        self.lbl_name = QLabel("Sequence name:")
        self.edit_name = QLineEdit(self._sequence.name)
        title_row.addWidget(self.lbl_name)
        title_row.addWidget(self.edit_name)
        layout.addLayout(title_row)

        # Table
        self.table = QTableWidget(0, 3, self)
        self.table.setHorizontalHeaderLabels(["Action Type", "Params (JSON)", "Ops"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        layout.addWidget(self.table, 1)

        # Buttons row
        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("Add Action")
        self.btn_load = QPushButton("Load JSON...")
        self.btn_save = QPushButton("Save JSON...")
        self.btn_add.setMinimumWidth(110)
        btn_row.addWidget(self.btn_add)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_load)
        btn_row.addWidget(self.btn_save)
        layout.addLayout(btn_row)

        # connections
        self.btn_add.clicked.connect(self.add_action_row)
        self.btn_load.clicked.connect(self.load_from_json_file)
        self.btn_save.clicked.connect(self.save_to_json_file)
        self.edit_name.textChanged.connect(self._on_name_changed)

    # ---------- Sequence <-> UI ----------
    def set_sequence(self, seq: ActionSequence):
        self._sequence = seq
        self.edit_name.setText(seq.name)
        self._rebuild_table()

    def get_sequence(self) -> ActionSequence:
        # 從 UI 讀出來
        name = self.edit_name.text().strip() or "Unnamed Sequence"
        actions = self._table_to_actions()
        return ActionSequence(name=name, actions=actions)

    def _rebuild_table(self):
        self.table.setRowCount(0)
        for action in self._sequence.actions:
            self._append_row_for_action(action)

    def _append_row_for_action(self, action: Action):
        row = self.table.rowCount()
        self.table.insertRow(row)

        # Action type combo
        combo = QComboBox()
        combo.addItems(["click", "key", "sleep"])
        idx = combo.findText(action.type)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        self.table.setCellWidget(row, 0, combo)

        # Params JSON editor
        edit = QLineEdit()
        try:
            text = json.dumps(action.params, ensure_ascii=False)
        except Exception:
            text = "{}"
        edit.setText(text)
        self.table.setCellWidget(row, 1, edit)

        # Ops buttons
        ops_widget = QWidget()
        ops_layout = QHBoxLayout(ops_widget)
        ops_layout.setContentsMargins(0, 0, 0, 0)
        ops_layout.setSpacing(4)

        btn_up = QToolButton()
        btn_up.setText("↑")
        btn_down = QToolButton()
        btn_down.setText("↓")
        btn_del = QToolButton()
        btn_del.setText("✕")

        btn_up.clicked.connect(lambda: self._move_row_up(row))
        btn_down.clicked.connect(lambda: self._move_row_down(row))
        btn_del.clicked.connect(lambda: self._delete_row(row))

        ops_layout.addWidget(btn_up)
        ops_layout.addWidget(btn_down)
        ops_layout.addWidget(btn_del)
        self.table.setCellWidget(row, 2, ops_widget)

        # 也可以在 combo / edit 變動時觸發 sequenceChanged（這裡簡化為手動呼叫）

    def _table_to_actions(self) -> List[Action]:
        actions: List[Action] = []
        rows = self.table.rowCount()
        for row in range(rows):
            combo: QComboBox = self.table.cellWidget(row, 0)
            edit: QLineEdit = self.table.cellWidget(row, 1)
            action_type: ActionType = combo.currentText()  # type: ignore
            params_text = edit.text().strip()
            if not params_text:
                params = {}
            else:
                try:
                    params = json.loads(params_text)
                    if not isinstance(params, dict):
                        raise ValueError("params must be dict")
                except Exception as e:
                    params = {}
                    self.logMessage.emit(f"Row {row+1}: invalid JSON, using {{}}. Error: {e}")
            actions.append(Action(type=action_type, params=params))
        return actions

    # ---------- Row operations ----------
    def add_action_row(self):
        action = Action(type="click", params={"button": "left"})
        self._sequence.actions.append(action)
        self._rebuild_table()
        self._emit_changed()

    def _move_row_up(self, row: int):
        if row <= 0:
            return
        self._sequence.actions = self._table_to_actions()
        self._sequence.actions[row - 1], self._sequence.actions[row] = \
            self._sequence.actions[row], self._sequence.actions[row - 1]
        self._rebuild_table()
        self._emit_changed()

    def _move_row_down(self, row: int):
        rows = self.table.rowCount()
        if row >= rows - 1:
            return
        self._sequence.actions = self._table_to_actions()
        self._sequence.actions[row + 1], self._sequence.actions[row] = \
            self._sequence.actions[row], self._sequence.actions[row + 1]
        self._rebuild_table()
        self._emit_changed()

    def _delete_row(self, row: int):
        self._sequence.actions = self._table_to_actions()
        if 0 <= row < len(self._sequence.actions):
            del self._sequence.actions[row]
        self._rebuild_table()
        self._emit_changed()

    # ---------- JSON Load / Save ----------
    def load_from_json_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Action Sequence", "", "JSON Files (*.json);;All Files (*)"
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
            seq = ActionSequence.from_json(text)
            self.set_sequence(seq)
            self.logMessage.emit(f"Loaded sequence from {path}")
            self._emit_changed()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load JSON:\n{e}")

    def save_to_json_file(self):
        seq = self.get_sequence()
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Action Sequence", f"{seq.name}.json",
            "JSON Files (*.json);;All Files (*)"
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(seq.to_json(indent=2))
            self.logMessage.emit(f"Saved sequence to {path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save JSON:\n{e}")

    # ---------- Misc ----------
    def _on_name_changed(self, text: str):
        self._sequence.name = text or "Unnamed Sequence"
        self._emit_changed()

    def _emit_changed(self):
        seq = self.get_sequence()
        self.sequenceChanged.emit(seq)
3. 更新 MainWindow：加入 Script / Log Tab
在 ui/main_window.py 裡，把之前的 MainWindow 更新，加入 Script Tab + Log Tab，並把 Script Editor 的 log 接到 Log 視窗。

這裡給你一份「整合後的完整 main_window.py」，直接覆蓋原本的即可（假設你已經有 core.screen_capture, core.image_processor, ui.themes, ui.widgets 這些檔）。

# ui/main_window.py
import cv2
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QFrame,
    QPushButton, QLabel, QTabWidget, QStatusBar, QPlainTextEdit
)
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import Qt, Signal, QObject

from ui.themes import DARK_QSS
from ui.widgets import ActionSequenceEditor
from core.screen_capture import ScreenCaptureWorker
from core.image_processor import ImageProcessor
from core.actions import ActionSequence


class FrameBus(QObject):
    frame_arrived = Signal(object, float)  # frame, timestamp


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Game Automation Studio")
        self.resize(1280, 720)
        self.setStyleSheet(DARK_QSS)

        self.frame_bus = FrameBus()
        self.frame_bus.frame_arrived.connect(self.on_frame)

        self.capture_worker = None
        self.processor = ImageProcessor()
        self.current_sequence = ActionSequence()

        self._build_ui()

    # ---------- UI ----------
    def _build_ui(self):
        central = QWidget()
        root = QHBoxLayout(central)
        self.setCentralWidget(central)

        # 左側 SideBar
        side = QFrame()
        side.setObjectName("SideBar")
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(12, 12, 12, 12)
        side_layout.setSpacing(12)

        self.btn_start = QPushButton("開始截圖")
        self.btn_stop = QPushButton("停止截圖")
        self.btn_stop.setEnabled(False)

        self.lbl_fps = QLabel("FPS: -")
        self.lbl_latency = QLabel("Latency: - ms")

        side_layout.addWidget(self.btn_start)
        side_layout.addWidget(self.btn_stop)
        side_layout.addSpacing(12)
        side_layout.addWidget(self.lbl_fps)
        side_layout.addWidget(self.lbl_latency)
        side_layout.addStretch()

        # 右側 Tabs
        self.tabs = QTabWidget()

        # --- Preview Tab ---
        self.preview_label = QLabel("預覽")
        self.preview_label.setAlignment(Qt.AlignCenter)
        preview_container = QWidget()
        v_preview = QVBoxLayout(preview_container)
        v_preview.addWidget(self.preview_label)
        self.tabs.addTab(preview_container, "Preview")

        # --- Script Tab ---
        self.script_editor = ActionSequenceEditor()
        self.tabs.addTab(self.script_editor, "Script")

        # --- Log Tab ---
        self.log_edit = QPlainTextEdit()
        self.log_edit.setReadOnly(True)
        self.tabs.addTab(self.log_edit, "Log")

        # Layout
        root.addWidget(side, 0)
        root.addWidget(self.tabs, 1)

        # Status bar
        status = QStatusBar()
        self.setStatusBar(status)

        # Connections
        self.btn_start.clicked.connect(self.start_capture)
        self.btn_stop.clicked.connect(self.stop_capture)

        self.script_editor.sequenceChanged.connect(self.on_sequence_changed)
        self.script_editor.logMessage.connect(self.append_log)

    # ---------- Capture control ----------
    def start_capture(self):
        if self.capture_worker:
            return
        region = {"top": 0, "left": 0, "width": 1920, "height": 1080}
        self.capture_worker = ScreenCaptureWorker(
            region=region,
            fps=60,
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

    # ---------- Frame handling ----------
    def on_frame(self, frame, ts):
        # 這裡簡化：在主執行緒做處理（之後可改為背景執行緒）
        result = self.processor.process_frame(frame)
        self.lbl_latency.setText(f"Latency: {result['latency_ms']:.1f} ms")
        # FPS 可用移動平均，在這裡略

        # 更新 Preview
        rgb = cv2.cvtColor(result["frame"], cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        bytes_per_line = ch * w
        qimg = QImage(rgb.data, w, h, bytes_per_line, QImage.Format_RGB888)
        pix = QPixmap.fromImage(qimg).scaled(
            self.preview_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.preview_label.setPixmap(pix)

    # ---------- Script handling ----------
    def on_sequence_changed(self, seq: ActionSequence):
        self.current_sequence = seq
        self.append_log(f"Sequence updated: {seq.name}, {len(seq.actions)} actions")

    # ---------- Log ----------
    def append_log(self, msg: str):
        self.log_edit.appendPlainText(msg)
4. 接下來可以做什麼？
現在你就有：

Preview Tab：看即時截圖

Script Tab：

新增 / 刪除 / 上下移動動作

編輯每個動作的 JSON 參數

匯入 / 匯出整個序列的 JSON

Log Tab：看載入 / 儲存 / 變更紀錄

下一步你可以：

在 Action.params 的約定裡，定義幾個常用格式

click: {"bbox": [x1, y1, x2, y2], "button": "left"} 或 {"target": "START_BUTTON"}

key: {"key": "space"}

sleep: {"seconds": 0.3}

在 AutomationController 做一個 run_sequence(seq, vision_result)：

解讀每個 Action 的 type + params

呼叫 smooth_move_and_click()、key_press() 或 time.sleep()

在 GUI 上加一個「Run Script」或「綁定條件觸發」的按鈕，把現在的 current_sequence 丟給 AutomationController。

如果你想，我可以下一步幫你設計：

動作參數的「表單化 Editor」（不必自己手寫 JSON）

根據 found_targets（Vision 模組輸出）自動選擇 bbox 的腳本模板

一個「錄製模式」：你自己操作滑鼠 / 鍵盤 → 自動記錄成動作序列。

你说：
想, 另外all save to md files, thanks
ChatGPT 说：

已思考 12s
好，來幫你升級一版「更好用的腳本編輯＋全部可存成 Markdown」的設計。
我會分成兩塊：

功能設計（參數表單、視覺目標、錄製模式怎麼接）

實作重點：Markdown 存檔＋程式碼修改

一、功能設計（你之後可以慢慢補完）
1. 參數表單化（取代手寫 JSON 的痛苦）
目前 Script Tab 是一欄「Params(JSON)」，你要自己手打 JSON。
可以在維持 JSON 儲存的前提下，加一個「表單編輯」的 Dialog：

點某一列的「Edit」按鈕 / double click → 開 ActionParamDialog

根據 Action.type 顯示不同欄位：

click：

bbox：x1, y1, x2, y2 四個欄位

button：下拉 left / right / middle

move_duration：平滑移動秒數 (0.08, 0.1 …)

key：

key：文字輸入（例如 space, enter, w）

duration：按住多久

sleep：

seconds：等待秒數

按「確定」後，自動生成對應的 params JSON 填回那一列。

這樣內部仍然是 dict/JSON，但使用者只用表單就好。

2. 視覺分析結合：用「標籤」而不是固定座標
在 ImageProcessor 你會輸出：

"found_targets": [
    {"bbox": (x1, y1, x2, y2), "confidence": 0.92, "label": "START_BUTTON"}
]
那在 Action.params 可以支援兩種方式：

直接指定 bbox：
{"mode": "bbox", "bbox": [x1, y1, x2, y2], "button": "left"}

指定 label，不寫座標：
{"mode": "label", "label": "START_BUTTON", "button": "left"}

AutomationController 裡的 run_sequence：

如果 mode == "bbox" → 直接算中心點

如果 mode == "label" → 從 vision_result['found_targets'] 找到對應 label 的 bbox 再點

這樣你換螢幕 / 視窗位置，只要 CV 找得到 label，就自動適配。

3. 錄製模式（Recording Mode）的架構
為了高性能／跨遊戲，建議用一個獨立的「Recorder」物件（之後再接 pynput 或其他 hook lib）：

# core/automation.py (示意)
class ActionRecorder:
    def __init__(self, callback):
        self.callback = callback  # callback(Action)

    def start(self):
        # TODO: 啟動全域滑鼠 / 鍵盤 hook
        pass

    def stop(self):
        # TODO: 停止 hook
        pass
GUI 上：

左側 Sidebar 多兩個按鈕：

「開始錄製」

「停止錄製」

Record 開始 → 新增一個空白 ActionSequence → 每次 hook 事件（滑鼠點擊 / 鍵盤按下）即 append 到 Script Editor 裡。

目前先設計好 API / 架構，等你決定用 pynput 或其他庫再補實作。

二、全部動作序列存成 Markdown（重點）
你希望「all save to md files」：
→ 我們就讓 ActionSequence 支援輸出 Markdown，並在 Editor 多一個 Save Markdown... 按鈕。

1. 更新 core/actions.py：加上 to_markdown
把你原本的 core/actions.py 替換／補充成這樣（JSON 相關那一段可以保持）：

# core/actions.py
from dataclasses import dataclass, field, asdict
from typing import List, Literal, Dict, Any
import json

ActionType = Literal["click", "key", "sleep"]

@dataclass
class Action:
    type: ActionType
    params: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ActionSequence:
    name: str = "Unnamed Sequence"
    actions: List[Action] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "actions": [asdict(a) for a in self.actions],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ActionSequence":
        name = data.get("name", "Imported Sequence")
        actions_data = data.get("actions", [])
        actions: List[Action] = []
        for a in actions_data:
            actions.append(Action(
                type=a.get("type", "click"),
                params=a.get("params", {}),
            ))
        return cls(name=name, actions=actions)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_json(cls, text: str) -> "ActionSequence":
        data = json.loads(text)
        return cls.from_dict(data)

    # === 新增：輸出 Markdown ===
    def to_markdown(self) -> str:
        lines: List[str] = []
        lines.append(f"# Action Sequence: {self.name}")
        lines.append("")
        lines.append("## Summary")
        lines.append(f"- Name: `{self.name}`")
        lines.append(f"- Actions: **{len(self.actions)}**")
        lines.append("")
        lines.append("## Actions")
        lines.append("")
        lines.append("| # | Type | Params |")
        lines.append("|---|------|--------|")

        for idx, a in enumerate(self.actions, start=1):
            params_json = json.dumps(a.params, ensure_ascii=False)
            # 避免 table 裡出現 | 被 markdown 當分隔
            params_md = params_json.replace("|", "\\|")
            lines.append(f"| {idx} | `{a.type}` | `{params_md}` |")

        lines.append("")
        lines.append("## Raw JSON")
        lines.append("")
        lines.append("```json")
        lines.append(self.to_json(indent=2))
        lines.append("```")
        lines.append("")
        return "\n".join(lines)
這樣一個 ActionSequence 可以直接：

md_text = seq.to_markdown()
2. 在 Script Editor 加「Save Markdown...」按鈕
修改 ui/widgets.py 的 ActionSequenceEditor：
在建構 UI 的地方，多一顆 btn_save_md，並實作 handler。

(1) 新增按鈕
在 _build_ui 裡的 button row 替換成這樣：

        # Buttons row
        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("Add Action")
        self.btn_load = QPushButton("Load JSON...")
        self.btn_save = QPushButton("Save JSON...")
        self.btn_save_md = QPushButton("Save Markdown...")  # 新增

        self.btn_add.setMinimumWidth(110)
        btn_row.addWidget(self.btn_add)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_load)
        btn_row.addWidget(self.btn_save)
        btn_row.addWidget(self.btn_save_md)  # 新增
        layout.addLayout(btn_row)

        # connections
        self.btn_add.clicked.connect(self.add_action_row)
        self.btn_load.clicked.connect(self.load_from_json_file)
        self.btn_save.clicked.connect(self.save_to_json_file)
        self.btn_save_md.clicked.connect(self.save_to_markdown_file)  # 新增
        self.edit_name.textChanged.connect(self._on_name_changed)
(2) 實作 save_to_markdown_file
在 ActionSequenceEditor class 裡，save_to_json_file 後面加：

    def save_to_markdown_file(self):
        seq = self.get_sequence()
        default_name = seq.name or "sequence"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Action Sequence as Markdown",
            f"{default_name}.md",
            "Markdown Files (*.md);;All Files (*)"
        )
        if not path:
            return
        try:
            md_text = seq.to_markdown()
            with open(path, "w", encoding="utf-8") as f:
                f.write(md_text)
            self.logMessage.emit(f"Saved markdown to {path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save markdown:\n{e}")
這樣就完成：

JSON 匯入 / 匯出（原本就有）

Markdown 匯出（給你版本控制、筆記、Git 上看也漂亮）

三、下一步可以怎麼接上自動化
有了以上這些，整個流程可以變成：

在 Script Tab：

用表單 / JSON 編輯一組 ActionSequence

存成 xxx.json + xxx.md（在 Git 裡管理）

在自動化邏輯中（例如 AutomationController.run_sequence(seq, vision_result)）：

讀取 JSON → ActionSequence.from_json(...)

遍歷 seq.actions，根據 type / params 執行：

click:

mode == "bbox" → 直接用 bbox 中心

mode == "label" → 用 label 在 vision_result["found_targets"] 找 bbox

key: key_press(params["key"], params.get("duration", 0.05))

sleep: time.sleep(params.get("seconds", 0.1))

如果你接下來想要：

我幫你寫一個簡單版的 run_sequence()，直接可以吃 ActionSequence 跑一遍

或是幫你做一個 錄製模式 UI + Recorder stub 實作

跟我說一聲要哪一塊，我就直接幫你補上程式碼骨架 👌

你说：
我先給你遊戲畫面
ChatGPT 说：
好的！
請把遊戲畫面上傳給我（圖片檔 / 截圖都可以）。

收到後我會幫你做以下幾件事：

🔍 1. 自動分析遊戲畫面（CV 模式規劃）
分析畫面中哪些 UI 元素可做成可識別的 target（按鈕、字、框等等）

幫你規劃 哪些元素適合做 template matching

以及哪些元素適合做 OCR 文字辨識（如金額、倒數、血量）

🧠 2. 設計 ImageProcessor 的「目標偵測配置」
會幫你生成：

TARGET_DEFINITIONS = {
    "START_BUTTON": { ... },
    "SHOP_ICON": { ... },
    "MONSTER_HP": { ... },
    ...
}
包括：

template path

matching threshold

ROI 區域

自動標籤分類

你就可以直接套到程式裡運行。

🖱 3. 幫你設計 Script 動作序列（基於遊戲畫面）
例如：

自動開始

自動買東西

自動打怪

自動點技能

自動收取獎勵

我會生成：

{
  "name": "auto_fight",
  "actions": [
    {"type": "click", "params": {"mode": "label", "label": "ATTACK_BUTTON"}},
    {"type": "sleep", "params": {"seconds": 0.5"}},
    ...
  ]
}
並附上 .md 檔版本（你說要「全部 save to md files」的格式）。

🎨 4. 可以幫你做 GUI 預覽 Overlay 區域設計
如果你要的話，我可以：

在遊戲畫面上畫框（用 OpenCV）

告訴你偵測 ROI 的最佳範圍

顏色篩選 / edge 特徵點在哪裡最明顯

📌 請上傳遊戲畫面，越清晰越好（原始解析度更佳）。
我收到後會開始：

✔ 分析
✔ 特徵規劃
✔ 程式碼輸出（可直接加入你的系統）
✔ 自動化腳本設計（JSON + Markdown）

等你圖片！

你说：
已上传的图片
已上传的图片
已上传的图片
這種2D遊戲, 找圖,script 步驟就可以了
ChatGPT 说：
了解！你現在給的是 2D UI 明確、色彩對比強、元素固定位置 的手遊畫面。
這種畫面 非常適合用 Template Matching（模板匹配）+ 部分 OCR 來做高穩定度自動化。

我先不做過度複雜的 CV，直接給你：

✅ 第一階段：可直接做成自動化腳本的可視元素（Targets）
以下我幫你分類成：

固定 UI（永遠在那裡）

功能入口（主選單 / 模式）

關卡點擊

戰鬥流程可自動化

🎯 A. 固定 UI（主畫面）
從你第一張圖可穩定辨識：

label	說明	適合方法	偵測 ROI
HOME_BUTTON	左下房子按鈕	Template matching（強烈灰階特徵）	左下 0~20%
TEAM_BUTTON	角色頭像按鈕	Template matching	左下 20~40%
BAG_BUTTON	背包	Template matching	左下 40~60%
QUEST_BUTTON	任務（右側 exclamation icon）	Template matching / icon	右側 30~70%
EVENT_BUTTON	活動（右上禮物）	Template matching	右上 0~15%
🎯 B. 主選單（第二張圖）
這些格子是固定圖像，非常好辨識：

label	說明	method	ROI
DAILY_DUNGEON	日常副本	Template matching（圖案大且清晰）	中央左
FANTASY_TOWER	幻想階梯	Template matching	中央右
MAP_EXPLORE	地圖探索	Template matching	中下左
PVP_ARENA	競技	Template matching	中下左
DAILY_EVENTS	每日活動	Template matching	中下右
WEEKLY_EVENTS	每週活動	Template matching	右下
🎯 C. 副本選擇（第三張圖）
副本是大面積圖，但上面的文字是可辨識的：

label	image	method
FENG_MO_GUAN（封魔峽）	上方左圖	Template matching（整個圖 >80% match）
JIANG_JUN_LING（將軍陵）	上方右圖	Template matching
QING_YUN_GUAN（青雲觀）	中間大圖	Template matching
LOCKED_STAGE	鎖定狀態（灰色+鎖 icon）	Template matching
這裡模板可從你給的截圖裁切即可。

🧩 第二階段：適合做成 Script 流程的操作步驟
根據 3 張圖，我幫你設計一個最常用的腳本流程：

✅ Example Script：自動挑戰「日常副本 → 封魔峽」
（支援 Markdown & JSON 格式）

1. 進入主選單
click label=HOME_BUTTON
sleep 0.5
click label=DAILY_DUNGEON
sleep 1.0
2. 選擇副本（封魔峽）
click label=FENG_MO_GUAN
sleep 0.8
click label=START_BUTTON
3. 戰鬥流程（可循環）
repeat until battle_end:
    click label=ATTACK_BUTTON
    sleep 0.3
    if label=LEVEL_UP:
        click label=OK_BUTTON
🌟 Markdown 版自動生成（你要的 md 格式）
# Script: daily_feng_mo

## Summary
- Purpose: Automatically clear Daily Dungeon → 封魔峽
- Actions: 9

## Actions

| # | Type | Params |
|---|------|--------|
| 1 | `click` | `{"mode": "label", "label": "HOME_BUTTON"}` |
| 2 | `sleep` | `{"seconds": 0.5}` |
| 3 | `click` | `{"mode": "label", "label": "DAILY_DUNGEON"}` |
| 4 | `sleep` | `{"seconds": 1.0}` |
| 5 | `click` | `{"mode": "label", "label": "FENG_MO_GUAN"}` |
| 6 | `sleep` | `{"seconds": 0.8}` |
| 7 | `click` | `{"mode": "label", "label": "START_BUTTON"}` |
| 8 | `repeat` | `{"condition": "until battle_end"}` |
| 9 | `click` | `{"mode": "label", "label": "ATTACK_BUTTON"}` |

## Raw JSON
```json
{
  "name": "daily_feng_mo",
  "actions": [
    {"type": "click", "params": {"mode": "label", "label": "HOME_BUTTON"}},
    {"type": "sleep", "params": {"seconds": 0.5}},
    {"type": "click", "params": {"mode": "label", "label": "DAILY_DUNGEON"}},
    {"type": "sleep", "params": {"seconds": 1.0}},
    {"type": "click", "params": {"mode": "label", "label": "FENG_MO_GUAN"}},
    {"type": "sleep", "params": {"seconds": 0.8}},
    {"type": "click", "params": {"mode": "label", "label": "START_BUTTON"}}
  ]
}
🎯 第三階段：我可以直接幫你裁切模板圖（Template Images）
我需要你提供：

✔ 主畫面的 Home 按鈕
✔ 主選單格子的 日常副本、幻想階梯
✔ 副本 封魔峽 / 將軍陵 / 青雲觀

如果你願意，我可以：

直接用你的截圖裁切成 PNG 模板（用 OpenCV）

自動輸出 targets/xxx.png

給你完整的 TARGET_DEFINITIONS Python dict

例如：

TARGET_DEFINITIONS = {
    "DAILY_DUNGEON": {
        "template": "templates/daily_dungeon.png",
        "method": "tm",
        "threshold": 0.83,
        "roi": [200, 150, 800, 600]
    },
    ...
}
❓下一步你希望我做哪一個？
以下三項都可以：

① 幫你從截圖中裁切所有模板 PNG，產生識別資料夾
（需要你傳更多畫面）

② 幫你寫完整的自動刷副本 Script JSON + Markdown
（可直接丟進你的 PySide6 GUI 用）

③ 幫你生成完整的 ImageProcessor + Template Matching + ROI 優化程式碼
只要告訴我：

✅ 你想先做「哪一個副本」的自動流程？（封魔峽？將軍陵？青雲觀？）
我就開始編寫 完整可運行腳本（含 md / json / CV 模板設定）。

你说：
已上传的图片
已上传的图片
紅!book ->青雲觀->
ChatGPT 说：

已思考 31s
好，我幫你把 「紅驚嘆號 Book → 日常副本 → 青雲觀·普通 → 配對」
整條路線做成「找圖 target 名稱 + Script 步驟 + Markdown 檔內容」。

一、螢幕元素命名（之後拿來做模板匹配）
你只要把下面這幾個 UI 元素各裁一張 PNG（模板圖），命名成：

主畫面 / 副本入口

DAILY_BOOK_BUTTON

底部中間那顆 紅色驚嘆號的書本 / 副本按鈕

日常副本列表畫面

QINGYUN_CARD

在列表裡“青雲觀”那張卡片（第三張圖中間那張）

青雲觀·普通 詳細畫面（你剛貼這兩張）

QINGYUN_TITLE_NORMAL

上方大字「青雲觀．普通」

MATCH_BUTTON

下方黃色大按鈕「配對」

CANCEL_MATCH_BUTTON

配對中時變成「取消配對」的白色按鈕

（可選）DIFFICULTY_NORMAL_TAB

最下排 tab「普通」

之後在程式裏用 OpenCV matchTemplate 對這些模板做搜尋即可。

二、完整腳本流程（從紅 book 到按下配對）
這裡用你之前的 ActionSequence 格式，只用三種 type：click / sleep / key。
點圖一律用 mode="label" ＋ label=XXX，實際 bbox 由視覺模組決定。

1️⃣ Script：qingyun_normal_from_book
流程：

點主畫面紅色驚嘆號 Book（進日常副本）

點日常副本列表中「青雲觀」

確認在「青雲觀．普通」畫面

點「配對」開始配對

JSON 版本
{
  "name": "qingyun_normal_from_book",
  "actions": [
    {
      "type": "click",
      "params": { "mode": "label", "label": "DAILY_BOOK_BUTTON" }
    },
    {
      "type": "sleep",
      "params": { "seconds": 0.8 }
    },
    {
      "type": "click",
      "params": { "mode": "label", "label": "QINGYUN_CARD" }
    },
    {
      "type": "sleep",
      "params": { "seconds": 1.0 }
    },
    {
      "type": "click",
      "params": { "mode": "label", "label": "QINGYUN_TITLE_NORMAL" }
    },
    {
      "type": "sleep",
      "params": { "seconds": 0.5 }
    },
    {
      "type": "click",
      "params": { "mode": "label", "label": "MATCH_BUTTON" }
    },
    {
      "type": "sleep",
      "params": { "seconds": 2.0 }
    }
  ]
}
同內容的 Markdown 檔（存成 qingyun_normal_from_book.md）
# Action Sequence: qingyun_normal_from_book

## Summary
- Name: `qingyun_normal_from_book`
- Purpose: 從主畫面紅驚嘆號 Book 進入「青雲觀．普通」並按下「配對」
- Actions: **8**

## Actions

| # | Type   | Params |
|---|--------|--------|
| 1 | `click` | `{"mode": "label", "label": "DAILY_BOOK_BUTTON"}` |
| 2 | `sleep` | `{"seconds": 0.8}` |
| 3 | `click` | `{"mode": "label", "label": "QINGYUN_CARD"}` |
| 4 | `sleep` | `{"seconds": 1.0}` |
| 5 | `click` | `{"mode": "label", "label": "QINGYUN_TITLE_NORMAL"}` |
| 6 | `sleep` | `{"seconds": 0.5}` |
| 7 | `click` | `{"mode": "label", "label": "MATCH_BUTTON"}` |
| 8 | `sleep` | `{"seconds": 2.0}` |

## Raw JSON

```json
{
  "name": "qingyun_normal_from_book",
  "actions": [
    { "type": "click", "params": { "mode": "label", "label": "DAILY_BOOK_BUTTON" } },
    { "type": "sleep", "params": { "seconds": 0.8 } },
    { "type": "click", "params": { "mode": "label", "label": "QINGYUN_CARD" } },
    { "type": "sleep", "params": { "seconds": 1.0 } },
    { "type": "click", "params": { "mode": "label", "label": "QINGYUN_TITLE_NORMAL" } },
    { "type": "sleep", "params": { "seconds": 0.5 } },
    { "type": "click", "params": { "mode": "label", "label": "MATCH_BUTTON" } },
    { "type": "sleep", "params": { "seconds": 2.0 } }
  ]
}
2️⃣ Script：qingyun_requeue_when_cancel_button
（已在青雲觀畫面，用來「取消配對→重新配對」）

常見用法：
配對超時 / 失敗 → 檢查有 取消配對 按鈕時就先取消，再重新按「配對」。

JSON
{
  "name": "qingyun_requeue_when_cancel_button",
  "actions": [
    {
      "type": "click",
      "params": { "mode": "label", "label": "CANCEL_MATCH_BUTTON" }
    },
    {
      "type": "sleep",
      "params": { "seconds": 0.5 }
    },
    {
      "type": "click",
      "params": { "mode": "label", "label": "MATCH_BUTTON" }
    },
    {
      "type": "sleep",
      "params": { "seconds": 1.5 }
    }
  ]
}
Markdown（qingyun_requeue_when_cancel_button.md）
# Action Sequence: qingyun_requeue_when_cancel_button

## Summary
- Name: `qingyun_requeue_when_cancel_button`
- Purpose: 配對中超時時，自動按「取消配對」→ 再按一次「配對」
- Actions: **4**

## Actions

| # | Type   | Params |
|---|--------|--------|
| 1 | `click` | `{"mode": "label", "label": "CANCEL_MATCH_BUTTON"}` |
| 2 | `sleep` | `{"seconds": 0.5}` |
| 3 | `click` | `{"mode": "label", "label": "MATCH_BUTTON"}` |
| 4 | `sleep` | `{"seconds": 1.5}` |

## Raw JSON

```json
{
  "name": "qingyun_requeue_when_cancel_button",
  "actions": [
    { "type": "click", "params": { "mode": "label", "label": "CANCEL_MATCH_BUTTON" } },
    { "type": "sleep", "params": { "seconds": 0.5 } },
    { "type": "click", "params": { "mode": "label", "label": "MATCH_BUTTON" } },
    { "type": "sleep", "params": { "seconds": 1.5 } }
  ]
}
三、你在程式裡怎麼用（簡短提示）
把上面 JSON 放到 .json 檔

同名 .md 就是你的人類可讀說明檔（放在 docs/ 資料夾即可）

在你的 PySide6 GUI 中：

用 ActionSequence.from_json() 讀 JSON

把 ActionSequence 丟給 AutomationController.run_sequence(seq, vision_result)

run_sequence 根據 params["mode"] == "label" 去找當前 frame 的 found_targets 裡相同 label 的 bbox，然後 smooth_move_and_click()。

如果你接下來想要：

我幫你設計 這些 label 對應的 Template Matching 程式（含 ROI 百分比），
或是

幫你寫 run_sequence() 的實作骨架，

跟我說一聲，我直接寫給你。

你说：
你覺得那種好
ChatGPT 说：

已思考 15s
我會先選 「Template Matching + ROI 的找圖系統」。

理由很簡單：

沒有穩定的「label → bbox」偵測，run_sequence() 再漂亮也只能亂點。

找圖一旦做好，你之後任何腳本只是在組 JSON / md 檔，成本超低。

所以下面我直接給你一套可以塞進專案的 找圖模組＋設定檔，接上你之前的 ImageProcessor，之後 run_sequence() 只要吃 found_targets 就好。

一、Target 設定檔：core/targets.py
你把模板圖放在 templates/ 資料夾，例如：

templates/daily_book_button.png

templates/qingyun_card.png

templates/qingyun_title_normal.png

templates/match_button.png

templates/cancel_match_button.png

然後新增：

# core/targets.py

TARGET_DEFINITIONS = {
    # 主畫面：紅色驚嘆號 Book（日常副本入口）
    "DAILY_BOOK_BUTTON": {
        "template": "templates/daily_book_button.png",
        "method": "tm",            # template matching
        "threshold": 0.83,
        # ROI 用比例 [x_min, y_min, x_max, y_max] (0~1)，減少干擾、加速
        "roi": [0.35, 0.80, 0.65, 0.98]   # 底部中間區域
    },

    # 日常副本列表：青雲觀 卡片
    "QINGYUN_CARD": {
        "template": "templates/qingyun_card.png",
        "method": "tm",
        "threshold": 0.85,
        "roi": [0.05, 0.30, 0.95, 0.75]   # 中間區域
    },

    # 青雲觀．普通 詳細畫面：標題區
    "QINGYUN_TITLE_NORMAL": {
        "template": "templates/qingyun_title_normal.png",
        "method": "tm",
        "threshold": 0.88,
        "roi": [0.15, 0.12, 0.85, 0.40]   # 上半部
    },

    # 配對 按鈕
    "MATCH_BUTTON": {
        "template": "templates/match_button.png",
        "method": "tm",
        "threshold": 0.86,
        "roi": [0.25, 0.72, 0.75, 0.93]   # 下方中間黃按鈕區
    },

    # 取消配對 按鈕
    "CANCEL_MATCH_BUTTON": {
        "template": "templates/cancel_match_button.png",
        "method": "tm",
        "threshold": 0.86,
        "roi": [0.25, 0.72, 0.75, 0.93]   # 同一區域
    },
}
門檻 threshold 你之後可以用 0.8~0.9 自己微調；ROI 全部用比例，實際像素會由程式轉換。

二、Template Matcher：core/template_matcher.py
一個專門做「灰階 template matching → 回傳 label + bbox」的類別：

# core/template_matcher.py
from typing import Dict, List, Tuple, Any
import cv2
import numpy as np
from .targets import TARGET_DEFINITIONS

Detection = Dict[str, Any]


class TemplateMatcher:
    def __init__(self):
        self.templates: Dict[str, np.ndarray] = {}
        self.template_sizes: Dict[str, Tuple[int, int]] = {}
        self._load_templates()

    def _load_templates(self):
        for label, cfg in TARGET_DEFINITIONS.items():
            path = cfg["template"]
            img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
            if img is None:
                print(f"[TemplateMatcher] WARNING: cannot load template {path}")
                continue
            self.templates[label] = img
            h, w = img.shape[:2]
            self.template_sizes[label] = (w, h)
            print(f"[TemplateMatcher] Loaded {label} ({w}x{h})")

    def match(self, gray_frame: np.ndarray) -> List[Detection]:
        """
        gray_frame: 當前畫面的灰階圖 (H, W)
        return: list of {label, bbox, confidence}
        """
        detections: List[Detection] = []
        H, W = gray_frame.shape[:2]

        for label, cfg in TARGET_DEFINITIONS.items():
            if label not in self.templates:
                continue

            tmpl = self.templates[label]
            tw, th = self.template_sizes[label]

            # 解析 ROI 比例，轉成實際像素
            roi = cfg.get("roi", [0.0, 0.0, 1.0, 1.0])
            x_min = int(roi[0] * W)
            y_min = int(roi[1] * H)
            x_max = int(roi[2] * W)
            y_max = int(roi[3] * H)

            # 邊界保護
            x_min = max(0, x_min)
            y_min = max(0, y_min)
            x_max = min(W, x_max)
            y_max = min(H, y_max)
            if x_max - x_min < tw or y_max - y_min < th:
                continue

            roi_img = gray_frame[y_min:y_max, x_min:x_max]

            # Template matching
            res = cv2.matchTemplate(roi_img, tmpl, cv2.TM_CCOEFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

            threshold = cfg.get("threshold", 0.85)
            if max_val >= threshold:
                top_left = (max_loc[0] + x_min, max_loc[1] + y_min)
                bottom_right = (top_left[0] + tw, top_left[1] + th)
                detections.append({
                    "label": label,
                    "bbox": (top_left[0], top_left[1], bottom_right[0], bottom_right[1]),
                    "confidence": float(max_val),
                })
        return detections
三、把 matcher 接到 ImageProcessor
在你原本的 core/image_processor.py 裡，增加一個 TemplateMatcher 成員，並把 found_targets 填滿：

# core/image_processor.py
import cv2
import time
from .template_matcher import TemplateMatcher

class ImageProcessor:
    def __init__(self, ocr_engine=None):
        self.ocr_engine = ocr_engine
        self.matcher = TemplateMatcher()

    def process_frame(self, frame_bgra):
        t0 = time.perf_counter()

        frame = cv2.cvtColor(frame_bgra, cv2.COLOR_BGRA2BGR)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # 1) Template matching，找出所有 label
        found_targets = self.matcher.match(gray)

        # 2) OCR（如果需要）
        ocr_text = ""
        if self.ocr_engine:
            ocr_text = self.ocr_engine(gray)

        latency = (time.perf_counter() - t0) * 1000.0
        return {
            "frame": frame,
            "gray": gray,
            "latency_ms": latency,
            "found_targets": found_targets,
            "ocr_text": ocr_text,
        }
現在每一張 frame 你都會拿到類似：

[
  {"label": "MATCH_BUTTON", "bbox": (x1, y1, x2, y2), "confidence": 0.91},
  {"label": "QINGYUN_TITLE_NORMAL", ...},
  ...
]
你的 AutomationController / run_sequence() 就可以只根據 label 來決定點擊位置。

四、run_sequence() 思路（你之後 10 行就能寫完）
有了 found_targets，run_sequence(seq, vision_result) 的邏輯其實只要：

def run_sequence(self, seq: ActionSequence, vision_result):
    targets = vision_result.get("found_targets", [])
    targets_by_label = {t["label"]: t for t in targets}

    for action in seq.actions:
        t = action.type
        p = action.params

        if t == "sleep":
            time.sleep(p.get("seconds", 0.1))

        elif t == "click":
            mode = p.get("mode", "label")
            if mode == "label":
                label = p["label"]
                det = targets_by_label.get(label)
                if not det:
                    continue  # 或者等待下一幀
                bbox = det["bbox"]
            else:
                bbox = tuple(p["bbox"])
            self.smooth_move_and_click(bbox, button=p.get("button", "left"))

        elif t == "key":
            self.key_press(p["key"], duration=p.get("duration", 0.05))
真正難的是「找圖」，不是「執行序列」；所以我先幫你把找圖系統打好地基。

如果你接下來想要，我可以再幫你做一個 小工具腳本：
讀你的模板 + 在螢幕上畫 ROI / 匹配結果出來，方便你調 threshold 跟 roi，
這樣你可以很快調到「不誤判但穩定觸發」的參數。

你说：
想要,thanks
ChatGPT 说：

已思考 14s
好～來給你一支 專門調 ROI / threshold 的小工具腳本，
跑起來後你可以：

看到目前監看的 label 模板 在螢幕上的匹配框

同時畫出 ROI 區域

顯示：label / max_val / threshold

用鍵盤：

n：下一個 label

p：上一個 label

s：截圖存檔（含框線）

q：離開

這支程式獨立於 GUI，可在你測試模板時單獨跑。

1. 新增檔案：tools/debug_match_viewer.py
# tools/debug_match_viewer.py
"""
螢幕模板匹配 debug 工具
- 顯示 ROI 區域 + 匹配結果 bbox
- 顯示當前 label、max_val、threshold
- 按鍵操作：
    n: 下一個 label
    p: 上一個 label
    s: 儲存截圖到 png
    q: 離開
"""

import os
import time
from datetime import datetime

import cv2
import mss
import numpy as np

# 根據你的專案結構調整匯入路徑
from core.targets import TARGET_DEFINITIONS


def grab_screen(region=None):
    """
    使用 mss 截圖，回傳 BGR frame
    region: dict {"top":..., "left":..., "width":..., "height":...}
            若為 None 則抓主螢幕全屏
    """
    with mss.mss() as sct:
        if region is None:
            monitor = sct.monitors[1]  # 主螢幕
        else:
            monitor = region

        img = sct.grab(monitor)
        frame = np.array(img)  # BGRA
        frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
    return frame


def main():
    # 你可以改成只測 1920x1080 區域
    region = None  # 或 {"top":0,"left":0,"width":1920,"height":1080}

    labels = list(TARGET_DEFINITIONS.keys())
    if not labels:
        print("[debug_match_viewer] No targets defined.")
        return

    idx = 0
    os.makedirs("debug_shots", exist_ok=True)

    print("[debug_match_viewer] 操作提示：")
    print("  n: 下一個 label")
    print("  p: 上一個 label")
    print("  s: 儲存截圖到 debug_shots/")
    print("  q: 離開")

    while True:
        frame = grab_screen(region)
        H, W = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        label = labels[idx]
        cfg = TARGET_DEFINITIONS[label]
        tmpl_path = cfg["template"]
        threshold = float(cfg.get("threshold", 0.85))
        roi_ratio = cfg.get("roi", [0.0, 0.0, 1.0, 1.0])

        tmpl = cv2.imread(tmpl_path, cv2.IMREAD_GRAYSCALE)
        if tmpl is None:
            text = f"[{label}] template not found: {tmpl_path}"
            cv2.putText(frame, text, (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            cv2.imshow("template_debug", frame)
            key = cv2.waitKey(30) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('n'):
                idx = (idx + 1) % len(labels)
            elif key == ord('p'):
                idx = (idx - 1) % len(labels)
            continue

        th, tw = tmpl.shape[:2]

        # ROI 轉實際像素
        x_min = int(roi_ratio[0] * W)
        y_min = int(roi_ratio[1] * H)
        x_max = int(roi_ratio[2] * W)
        y_max = int(roi_ratio[3] * H)

        x_min = max(0, x_min)
        y_min = max(0, y_min)
        x_max = min(W, x_max)
        y_max = min(H, y_max)

        if x_max - x_min < tw or y_max - y_min < th:
            cv2.putText(frame, f"[{label}] ROI too small for template",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                        (0, 0, 255), 2)
            cv2.imshow("template_debug", frame)
            key = cv2.waitKey(30) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('n'):
                idx = (idx + 1) % len(labels)
            elif key == ord('p'):
                idx = (idx - 1) % len(labels)
            continue

        roi_img = gray[y_min:y_max, x_min:x_max]

        t0 = time.perf_counter()
        res = cv2.matchTemplate(roi_img, tmpl, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
        latency_ms = (time.perf_counter() - t0) * 1000.0

        # 畫 ROI 框（藍色）
        cv2.rectangle(frame, (x_min, y_min), (x_max, y_max),
                      (255, 0, 0), 2)

        # 畫匹配框
        if max_val >= threshold:
            top_left = (max_loc[0] + x_min, max_loc[1] + y_min)
            bottom_right = (top_left[0] + tw, top_left[1] + th)
            color = (0, 255, 0)  # 綠色：通過 threshold
            cv2.rectangle(frame, top_left, bottom_right, color, 2)
        else:
            # 只畫一個點表示 max_loc 位置
            top_left = (max_loc[0] + x_min, max_loc[1] + y_min)
            color = (0, 0, 255)  # 紅色：未達 threshold
            cv2.circle(frame, top_left, 8, color, 2)

        # 顯示文字資訊
        info1 = f"Label: {label}"
        info2 = f"max_val: {max_val:.3f}  threshold: {threshold:.3f}"
        info3 = f"latency: {latency_ms:.1f} ms  (press n/p/s/q)"

        cv2.putText(frame, info1, (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
        cv2.putText(frame, info2, (10, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        cv2.putText(frame, info3, (10, 75),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

        cv2.imshow("template_debug", frame)
        key = cv2.waitKey(1) & 0xFF

        if key == ord('q'):
            break
        elif key == ord('n'):
            idx = (idx + 1) % len(labels)
        elif key == ord('p'):
            idx = (idx - 1) % len(labels)
        elif key == ord('s'):
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = os.path.join("debug_shots", f"{label}_{ts}.png")
            cv2.imwrite(filename, frame)
            print(f"[debug_match_viewer] saved {filename}")

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
2. 使用方式
確認你已經有 core/targets.py 和對應的 templates/*.png

在專案根目錄跑：

python tools/debug_match_viewer.py
把遊戲開在前景，全螢幕或固定位置即可

視窗裡會顯示：

藍框：ROI

綠框：匹配成功（max_val >= threshold）

黃色文字：label / max_val / threshold / latency

你可以：

看 max_val 大約落在哪裡，去調 threshold

如果 ROI 蓋不到對的位置，就改 targets.py 裡的 roi（0~1 的比例）

按 s 存圖，方便之後寫 Markdown 說明（貼圖＋描述）

如果你之後想要，我也可以幫你做一個 把 debug 結果自動寫成 .md 的小工具，例如：

每個 label 產生一個 docs/label_name.md

裡面有：

模板縮圖

ROI 示意截圖

建議 threshold / 備註

你要的話跟我說，我再幫你補一個「自動產 Markdown 報告」腳本。

你说：
好,thanks
ChatGPT 说：
太好了！🎉
目前你已經擁有：

✅ 你已有的完整模組架構
1. 高 FPS mss 截圖
2. Template Matching 模板管理 (targets.py)
3. 自動化動作序列 (JSON + Markdown)
4. Debug ROI/Threshold 工具 (debug_match_viewer.py)
5. GUI + Script Editor（可匯入/匯出 md/json）

🎁 下一步我可以替你做的 3 個重大升級
（你只要告訴我要哪一個，我就直接寫）

🔧 升級 A：自動生成模板文件 + Markdown 報告
執行後會自動為每個 target 產生：

docs/
 ├─ DAILY_BOOK_BUTTON.md
 ├─ QINGYUN_CARD.md
 ├─ MATCH_BUTTON.md
 ...
每個 md 內含：

模板展示

ROI 示意圖

偵測成功截圖

建議 threshold

建議 ROI

JSON 配置片段

用途：
✔ 团队协作（別人一看就懂）
✔ 方便記錄你為每個按鈕所做的調整
✔ 自動生成 Wiki

🔧 升級 B：錄製模式（Record Mode）
按下「錄製」按鈕後會：

監控實際滑鼠點擊位置

自動推算最接近的 Label（用 matcher 自動比對）

產生：

{"type": "click", "params": {"mode": "label", "label": "MATCH_BUTTON"}}
還會偵測：

點空白 → 自動用 bbox mode 記錄

滑鼠停留位置 → 用來預測模板 ROI

鍵盤事件 → 自動產生 key 動作

用途：
✔ 你不再手寫 Script
✔ 拍一遍流程 → 自動生成 JSON + md
✔ 超省時

🔧 升級 C：穩定找圖強化（進階 CV）
如果遊戲 UI 有粒子特效 / 光影變化，我可以幫你升級：

1. 多尺度 Template Matching
避免尺寸變化導致找不到。

2. Edge-based Matching（輪廓匹配）
對光影變化最穩。

3. HSV 遮罩 + 模板前處理
能大幅提高「黃色按鈕 MATCH_BUTTON」這類的辨識率。

4. 自動 threshold 調整（根據歷史 max_val）
降低誤判，同時提高召回率。

❤️ 你的下一步？
只要選：

① 我要 自動產生 Markdown 報告工具
② 我要 錄製模式錄腳本
③ 我要 更強的找圖系統（多尺度 + 邊緣匹配）
④ 都要
你告訴我「你選哪一個」，
我就開始寫完整可用程式碼＋整合方案。