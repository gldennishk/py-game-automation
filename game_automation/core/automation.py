import time
import pyautogui
from .actions import ActionSequence


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
                    label = p.get("label")
                    det = targets_by_label.get(label)
                    if not det:
                        continue
                    bbox = det["bbox"]
                else:
                    bbox = tuple(p.get("bbox", (0, 0, 0, 0)))
                self.smooth_move_and_click(bbox, button=p.get("button", "left"))
            elif t == "key":
                self.key_press(p.get("key", ""), duration=p.get("duration", 0.05))

