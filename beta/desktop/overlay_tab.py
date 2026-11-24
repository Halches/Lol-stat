"""Find the visible scoreboard frame for the in-game design preview."""
from concurrent.futures import ThreadPoolExecutor
from time import monotonic

from tab_detect import detect, find_frames

FRAME_TOLERANCE = 8
IDENTITY_GRACE = 1.4


def same_geometry(first, second):
    return len(first) == len(second) and max(abs(a-b) for a,b in zip(first,second)) <= FRAME_TOLERANCE


def capture_frame(rect, portraits=None, players=None):
    import numpy as np
    from cv2 import error, setNumThreads
    from PIL import ImageGrab

    x, y, width, height = rect
    setNumThreads(1)
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
        self.anchor = None
        self.candidate = None
        self.last_seen = 0
        self.identities = {}

    def accept_observation(self, result, now):
        if result is None:
            if now - self.last_seen > IDENTITY_GRACE:
                self.frame = None
            return
        geometry = result["frame"] if isinstance(result, dict) else result
        if self.anchor is None or not same_geometry(self.anchor, geometry):
            if self.candidate is None or not same_geometry(self.candidate, geometry):
                self.candidate = geometry
                return
            self.anchor = tuple(round((a+b)/2) for a,b in zip(self.candidate,geometry))
            self.identities.clear()
        self.candidate = None
        self.last_seen = now
        if isinstance(result, dict):
            result = dict(result, frame=self.anchor)
            columns = []
            for side, column in enumerate(result["columns"]):
                # A recognized row change invalidates missing identities in the
                # whole column; a death animation must not reshuffle badges.
                changed = any(value is not None and (side,row) in self.identities
                              and self.identities[side,row][0] != value for row,value in enumerate(column))
                if changed:
                    self.identities = {k:v for k,v in self.identities.items() if k[0] != side}
                resolved = []
                visible = {value for value in column if value is not None}
                for row,value in enumerate(column):
                    key = side,row
                    if value is not None:
                        self.identities[key] = value,now
                    elif key in self.identities:
                        previous,stamp = self.identities[key]
                        if now-stamp <= IDENTITY_GRACE and previous not in visible:
                            value = previous
                    resolved.append(value)
                columns.append(tuple(resolved))
            result["columns"] = tuple(columns)
        else:
            result = self.anchor
        self.frame = result

    def update(self, rect, portraits=None, players=None, session=None):
        # Downloaded templates and API row order do not change the scoreboard.
        # Keep its confirmed geometry while using new templates on the next scan.
        context = (rect, portraits is not None,
                   tuple(sorted((p['c'], p['team']) for p in players or [])), session)
        if self.rect != context:
            self.rect = context
            self.revision += 1
            self.frame = None
            self.anchor = self.candidate = None
            self.identities.clear()
            self.next_capture = monotonic() + .18  # Let the native Tab animation finish.
        if self.job is not None and self.job[1].done():
            revision, job = self.job
            self.job = None
            if revision == self.revision:
                try:
                    self.accept_observation(job.result(), monotonic())
                except (ImportError, OSError, ValueError, RuntimeError):
                    self.accept_observation(None, monotonic())
        if rect and self.job is None and monotonic() >= self.next_capture:
            self.next_capture = monotonic() + (.12 if self.frame is None else 1.0)
            self.job = self.revision, self.executor.submit(capture_frame, rect, portraits, players)
        return self.frame

    def close(self):
        self.executor.shutdown(wait=False, cancel_futures=True)
