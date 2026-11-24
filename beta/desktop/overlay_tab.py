"""Find the visible scoreboard frame for the in-game design preview."""
from concurrent.futures import ThreadPoolExecutor
from time import monotonic

from tab_detect import detect, find_frames


def capture_frame(rect, portraits=None, players=None):
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
        if portraits is not None:
            try:
                layout = detect(screenshot, portraits, players or [])
            except error:
                return None
            if layout is None or len(frames) != 1:
                return None
            return {"frame": frames[0], "columns": layout.columns, "teams": layout.teams,
                    "confidence": layout.confidence}
    return frames[0] if len(frames) == 1 else None


class TabFrameFinder:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.rect = None
        self.revision = 0
        self.job = None
        self.frame = None
        self.next_capture = 0

    def update(self, rect, portraits=None, players=None, session=None):
        context = (rect, tuple(sorted(portraits)) if portraits is not None else None,
                   tuple((p['c'], p['team']) for p in players or []), session)
        if self.rect != context:
            self.rect = context
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
            self.job = self.revision, self.executor.submit(capture_frame, rect, portraits, players)
        return self.frame

    def close(self):
        self.executor.shutdown(wait=False, cancel_futures=True)
