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

