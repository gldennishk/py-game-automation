import numpy as np
import cv2
from game_automation.core.actions import VisualScript, VisualNode, Action, ActionSequence
from game_automation.core.automation import AutomationController
from PySide6.QtCore import QPointF


class FakePyAutoGUI:
    def __init__(self):
        self.moves = []
        self.clicks = []
        self.presses = []

    def moveTo(self, x, y, duration=0):
        self.moves.append((x, y, duration))

    def click(self, button="left"):
        self.clicks.append(button)

    def press(self, key):
        self.presses.append(key)


def make_frame_with_green_box():
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    frame[40:60, 10:30] = (0, 255, 0)
    return frame


def test_execute_visual_script_chain_and_callbacks(monkeypatch):
    fake = FakePyAutoGUI()
    monkeypatch.setattr("pyautogui.moveTo", fake.moveTo)
    monkeypatch.setattr("pyautogui.click", fake.click)
    monkeypatch.setattr("pyautogui.press", fake.press)

    n1 = VisualNode(id="n1", type="click", params={"mode": "label", "label": "A", "button": "left"}, position=QPointF(0, 0))
    n2 = VisualNode(id="n2", type="sleep", params={"seconds": 0.0}, position=QPointF(0, 0))
    n3 = VisualNode(id="n3", type="key", params={"key": "space"}, position=QPointF(0, 0))
    vs = VisualScript(id="s1", name="demo", nodes=[n1, n2, n3], connections={"n1": "n2", "n2": "n3"})
    ac = AutomationController(scale_factor=1.0)

    callbacks = []
    ac.on_node_executed = lambda nid, ok: callbacks.append((nid, ok))

    vision = {"found_targets": [{"label": "A", "bbox": [10, 20, 30, 40]}], "frame": make_frame_with_green_box()}
    ac.execute_visual_script(vs, vision)

    assert fake.moves and fake.moves[0][0] == 20
    assert fake.clicks == ["left"]
    assert fake.presses == ["space"]
    assert callbacks == [("n1", True), ("n2", True), ("n3", True)]


def test_execute_visual_script_loop_protection(monkeypatch):
    fake = FakePyAutoGUI()
    monkeypatch.setattr("pyautogui.moveTo", fake.moveTo)
    monkeypatch.setattr("pyautogui.click", fake.click)

    n1 = VisualNode(id="n1", type="click", params={"mode": "label", "label": "A"}, position=QPointF(0, 0))
    n2 = VisualNode(id="n2", type="sleep", params={"seconds": 0.0}, position=QPointF(0, 0))
    vs = VisualScript(id="s1", name="loop", nodes=[n1, n2], connections={"n1": "n2", "n2": "n1"})
    ac = AutomationController(scale_factor=1.0)
    seen = []
    ac.on_node_executed = lambda nid, ok: seen.append(nid)
    vision = {"found_targets": [{"label": "A", "bbox": [0, 0, 10, 10]}], "frame": make_frame_with_green_box()}
    ac.execute_visual_script(vs, vision)
    assert seen == ["n1", "n2"]


def test_find_color_node_visual_success(monkeypatch):
    # Monkeypatch ImageProcessor used inside automation to return a known box
    import game_automation.core.automation as auto_mod
    class _FakeIP:
        def find_color(self, frame_bgr, **kwargs):
            return [(10, 40, 30, 60)]
    monkeypatch.setattr(auto_mod, "ImageProcessor", lambda *args, **kwargs: _FakeIP(), raising=False)

    frame = make_frame_with_green_box()
    n1 = VisualNode(id="n1", type="find_color", params={"hsv_min": [50, 100, 100], "hsv_max": [70, 255, 255]}, position=QPointF(0, 0))
    vs = VisualScript(id="s1", name="color", nodes=[n1], connections={})
    ac = AutomationController(scale_factor=1.0)
    called = []
    ac.on_node_executed = lambda nid, ok: called.append((nid, ok))
    vision = {"frame": frame}
    ac.execute_visual_script(vs, vision)
    assert called == [("n1", True)]


def test_find_color_action_sequence_click(monkeypatch):
    # Monkeypatch ImageProcessor used inside automation to return specific box
    import game_automation.core.automation as auto_mod
    class _FakeIP:
        def find_color(self, frame_bgr, **kwargs):
            return [(10, 40, 30, 60)]
    monkeypatch.setattr(auto_mod, "ImageProcessor", lambda *args, **kwargs: _FakeIP(), raising=False)

    frame = make_frame_with_green_box()
    fake = FakePyAutoGUI()
    monkeypatch.setattr("pyautogui.moveTo", fake.moveTo)
    monkeypatch.setattr("pyautogui.click", fake.click)
    seq = ActionSequence(name="color_seq", actions=[Action(type="find_color", params={"hsv_min": [50, 100, 100], "hsv_max": [70, 255, 255], "click": True, "button": "left"})])
    ac = AutomationController(scale_factor=1.0)
    ac.run_sequence(seq, {"frame": frame})
    assert fake.clicks == ["left"]
    # Center: x ~ (10+30)/2 = 20, y ~ (40+60)/2 = 50
    assert fake.moves and fake.moves[0][0] == 20 and fake.moves[0][1] == 50


def test_image_processor_find_color_hsv_direct():
    # Direct unit without automation; ensure HSV path works
    from game_automation.core.image_processor import ImageProcessor
    frame = make_frame_with_green_box()
    ip = ImageProcessor()
    boxes = ip.find_color(frame, hsv_min=[50, 100, 100], hsv_max=[70, 255, 255])
    assert boxes, "should find green box via HSV range"
