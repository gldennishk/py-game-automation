import ctypes
import pyautogui


def set_per_monitor_dpi_awareness():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass


def detect_scale_factor(base_width: int = 1920) -> float:
    w, h = pyautogui.size()
    if base_width <= 0:
        return 1.0
    return max(1.0, w / float(base_width))


def logical_to_physical(x: int, y: int, scale: float) -> tuple[int, int]:
    return int(x * scale), int(y * scale)

