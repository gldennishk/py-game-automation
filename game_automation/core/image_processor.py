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
        found_targets = self.matcher.match(gray)
        overlays = []
        for det in found_targets:
            x1, y1, x2, y2 = det["bbox"]
            color = (0, 255, 0)
            overlays.append((x1, y1, x2, y2, color))
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        ocr_text = ""
        if self.ocr_engine:
            ocr_text = self.ocr_engine(gray)
        latency = (time.perf_counter() - t0) * 1000.0
        return {
            "frame": frame,
            "gray": gray,
            "latency_ms": latency,
            "found_targets": found_targets,
            "overlays": overlays,
            "ocr_text": ocr_text,
        }

    def find_color(self, frame_bgr, hsv_min=None, hsv_max=None, bgr_min=None, bgr_max=None):
        import numpy as np
        if hsv_min is not None and hsv_max is not None:
            hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
            lo = np.array(hsv_min, dtype=np.uint8)
            hi = np.array(hsv_max, dtype=np.uint8)
            mask = cv2.inRange(hsv, lo, hi)
        elif bgr_min is not None and bgr_max is not None:
            lo = np.array(bgr_min, dtype=np.uint8)
            hi = np.array(bgr_max, dtype=np.uint8)
            cond = (frame_bgr >= lo) & (frame_bgr <= hi)
            mask = np.where(np.all(cond, axis=2), 255, 0).astype(np.uint8)
        else:
            return []
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        boxes = []
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            boxes.append((x, y, x + w, y + h))
        if not boxes:
            ys, xs = (mask > 0).nonzero()
            if ys.size and xs.size:
                x1, y1 = int(xs.min()), int(ys.min())
                x2, y2 = int(xs.max()), int(ys.max())
                boxes.append((x1, y1, x2, y2))
        return boxes
