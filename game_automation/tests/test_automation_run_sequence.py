from core.actions import Action, ActionSequence
from core.automation import AutomationController


class FakePyAutoGUI:
    def __init__(self):
        self.moves = []
        self.clicks = []
        self.keys = []

    def moveTo(self, x, y, duration=0):
        self.moves.append((x, y, duration))

    def click(self, button="left"):
        self.clicks.append(button)

    def keyDown(self, key):
        self.keys.append(("down", key))

    def keyUp(self, key):
        self.keys.append(("up", key))


def test_run_sequence_monkeypatch(monkeypatch):
    fake = FakePyAutoGUI()
    monkeypatch.setattr("pyautogui.moveTo", fake.moveTo)
    monkeypatch.setattr("pyautogui.click", fake.click)
    monkeypatch.setattr("pyautogui.keyDown", fake.keyDown)
    monkeypatch.setattr("pyautogui.keyUp", fake.keyUp)

    ac = AutomationController(scale_factor=1.0)
    seq = ActionSequence(name="s", actions=[
        Action(type="click", params={"mode": "bbox", "bbox": [10, 20, 30, 40]}),
        Action(type="key", params={"key": "space", "duration": 0}),
    ])
    vision = {"found_targets": []}
    ac.run_sequence(seq, vision)

    assert fake.clicks == ["left"]
    assert fake.moves and fake.moves[0][0] == 20

