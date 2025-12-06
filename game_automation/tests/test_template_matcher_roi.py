import numpy as np
import cv2
from game_automation.core.template_matcher import TemplateMatcher


def test_match_in_roi(monkeypatch):
    frame = np.zeros((200, 300), dtype=np.uint8)
    tmpl = np.full((10, 20), 255, dtype=np.uint8)
    frame[100:110, 150:170] = 255

    tm = TemplateMatcher()

    def fake_load_templates(self):
        self.templates = {"X": tmpl}
        self.template_sizes = {"X": (20, 10)}
    monkeypatch.setattr(TemplateMatcher, "_load_templates", fake_load_templates, raising=True)
    tm._load_templates()

    from game_automation.core.targets import TARGET_DEFINITIONS
    TARGET_DEFINITIONS.clear()
    TARGET_DEFINITIONS.update({
        "X": {"template": "", "threshold": 0.9, "roi": [0.4, 0.4, 0.9, 0.9]}
    })

    dets = tm.match(frame)
    assert dets, "should detect template in ROI"
    assert dets[0]["label"] == "X"

