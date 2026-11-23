"""Find the visible scoreboard frame for the in-game design preview."""
from concurrent.futures import ThreadPoolExecutor
from time import monotonic

from tab_detect import find_frames


def capture_frame(rect):
    import numpy as np
    from cv2 import error
    from PIL import ImageGrab

    x, y, width, height = rect
    with ImageGrab.grab(bbox=(x, y, x + width, y + height), all_screens=True,
                        include_layered_windows=False) as screenshot:
        try:
            frames = find_frames(np.array(screenshot.convert("RGB")), include_header=True)
        except error:
            return None
    return frames[0] if len(frames) == 1 else None


class TabFrameFinder:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.rect = None
        self.revision = 0
        self.job = None
        self.frame = None
        self.next_capture = 0

    def update(self, rect):
        if self.rect != rect:
            self.rect = rect
            self.revision += 1
            self.frame = None
            self.next_capture = monotonic() + .18  # Let the native Tab animation finish.
        if self.job is not None and self.job[1].done():
            revision, job = self.job
            self.job = None
            if revision == self.revision:
                try:
                    self.frame = job.result()
                except (ImportError, OSError, ValueError, RuntimeError):
                    self.frame = None
        if rect and self.job is None and monotonic() >= self.next_capture:
            self.next_capture = monotonic() + .6
            self.job = self.revision, self.executor.submit(capture_frame, rect)
        return self.frame

    def close(self):
        self.executor.shutdown(wait=False, cancel_futures=True)
