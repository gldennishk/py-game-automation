import time
import threading
import mss
import numpy as np


class ScreenCaptureWorker(threading.Thread):
    def __init__(self, region, fps=60, callback=None):
        super().__init__(daemon=True)
        self.region = region
        self.fps = fps
        self.callback = callback
        self._running = threading.Event()
        self._running.set()
        self._mss = mss.mss()

    def run(self):
        frame_interval = 1.0 / self.fps
        while self._running.is_set():
            start = time.perf_counter()
            img = self._mss.grab(self.region)
            frame = np.array(img)
            ts = time.time()
            if self.callback:
                self.callback(frame, ts)
            elapsed = time.perf_counter() - start
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def stop(self):
        self._running.clear()

