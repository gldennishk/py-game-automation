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
                continue
            self.templates[label] = img
            h, w = img.shape[:2]
            self.template_sizes[label] = (w, h)

    def match(self, gray_frame: np.ndarray) -> List[Detection]:
        detections: List[Detection] = []
        H, W = gray_frame.shape[:2]

        for label, cfg in TARGET_DEFINITIONS.items():
            if label not in self.templates:
                continue

            tmpl = self.templates[label]
            tw, th = self.template_sizes[label]

            roi = cfg.get("roi", [0.0, 0.0, 1.0, 1.0])
            x_min = int(roi[0] * W)
            y_min = int(roi[1] * H)
            x_max = int(roi[2] * W)
            y_max = int(roi[3] * H)

            x_min = max(0, x_min)
            y_min = max(0, y_min)
            x_max = min(W, x_max)
            y_max = min(H, y_max)
            if x_max - x_min < tw or y_max - y_min < th:
                continue

            roi_img = gray_frame[y_min:y_max, x_min:x_max]
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

