"""Read the queued shop item from the standard bottom HUD, without game writes."""
from concurrent.futures import ThreadPoolExecutor
import io
import json
import os
from pathlib import Path
import re
from time import monotonic
from urllib.request import Request, urlopen


def load_templates(version, item_ids, cache=None):
    import cv2
    import numpy as np
    from PIL import Image
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Invalid asset version")
    root = (Path(cache) if cache else Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "LoLHelper/quick-buy") / version
    root.mkdir(parents=True, exist_ok=True)
    base = f"https://ddragon.leagueoflegends.com/cdn/{version}/"
    def read(name, url):
        path = root / name
        if path.exists():
            return path.read_bytes()
        with urlopen(Request(base + url, headers={"User-Agent": "LoL Helper"}), timeout=4) as reply:
            data = reply.read(4_000_000)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_bytes(data)
        temp.replace(path)
        return data
    metadata = json.loads(read("items.json", "data/ru_RU/item.json"))
    if metadata.get("version") != version or not isinstance(metadata.get("data"), dict):
        (root / "items.json").unlink(missing_ok=True)
        raise ValueError("Invalid item catalog")
    sprites, templates, equivalent = {}, {}, set()
    for key in sorted(item_ids, key=int):
        info = metadata["data"].get(key, {}).get("image", {})
        name = info.get("sprite", "")
        if not re.fullmatch(r"item\d+\.png", name):
            continue
        if name not in sprites:
            try:
                with Image.open(io.BytesIO(read(name, "img/sprite/" + name))) as image:
                    sprites[name] = cv2.cvtColor(np.asarray(image.convert("RGB")), cv2.COLOR_RGB2GRAY)
            except (OSError, ValueError):
                (root / name).unlink(missing_ok=True)
                raise
        x, y, w, h = (info[k] for k in ("x", "y", "w", "h"))
        icon = sprites[name][y:y+h, x:x+w]
        if icon.shape == (h, w) and h > 0 and w > 0:
            item = metadata["data"][key]
            # Some internal IDs have exactly the same face, name, price and
            # recipe. Keep their canonical ID without creating false ambiguity.
            signature = (icon.tobytes(), item.get("name"), (item.get("gold") or {}).get("total"), tuple(item.get("from", [])))
            if signature in equivalent:
                continue
            equivalent.add(signature)
            templates[int(key)] = icon
    if not templates:
        raise ValueError("Empty item templates")
    return templates


def detect_item(image, templates):
    """Require the lower circular HUD button and an unambiguous item face."""
    import cv2
    import numpy as np
    cv2.setNumThreads(1)
    rgb = np.asarray(image.convert("RGB"))
    h, w = rgb.shape[:2]
    if h < 480 or w < 640:
        return None
    x0, y0 = round(w*.43), round(h*.92)
    gray = cv2.cvtColor(rgb[y0:, x0:round(w*.76)], cv2.COLOR_RGB2GRAY)
    circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, 1, max(10, h*.012),
                              param1=100, param2=23, minRadius=max(8, round(h*.008)), maxRadius=round(h*.027))
    if circles is None:
        return None
    candidates = []
    for x, y, radius in circles[0]:
        if not h-radius*2.2 < y+y0 < h-radius*.6:
            continue
        if not any(abs(xx-x) < radius*.3 and radius*1.8 < y-yy < radius*3.5
                   and .6 < rr/radius < 1.5 for xx, yy, rr in circles[0]):
            continue
        candidates.append((round(x+x0), round(y+y0), round(radius)))
    # The queued item is the rightmost paired button, below Recall. Restrict
    # work to two candidates; never search inventory squares for a recommendation.
    ranks = {}
    locations = {}
    for x, y, radius in sorted(candidates, reverse=True)[:2]:
        edge = min(round(radius*1.5), x, y, w-x-1, h-y-1)
        patch = cv2.cvtColor(rgb[max(0,y-edge):min(h,y+edge+1), max(0,x-edge):min(w,x+edge+1)], cv2.COLOR_RGB2GRAY)
        if patch.shape != (edge*2+1, edge*2+1):
            continue
        def score(source, sizes):
            best = -1.
            for size in sizes:
                icon = cv2.resize(source, (size, size), interpolation=cv2.INTER_AREA)
                margin = round(size*.2)
                face = icon[margin:-margin, margin:-margin]
                if face.std() < 8 or face.shape[0] > patch.shape[0]:
                    continue
                scores = cv2.matchTemplate(patch, face, cv2.TM_CCOEFF_NORMED)
                # Accommodate a few physical pixels of the ring/face offset.
                centre = edge - face.shape[0]//2
                delta = max(2, round(radius*.2))
                local = scores[max(0,centre-delta):centre+delta+1, max(0,centre-delta):centre+delta+1]
                if local.size:
                    best = max(best, float(local.max()))
            return best
        coarse = {key: score(source, sorted({max(14,round(radius*f)) for f in (1.45,1.65,1.85,2.05)}))
                  for key,source in templates.items()}
        for key in sorted(coarse, key=coarse.get, reverse=True)[:12]:
            best = score(templates[key], range(max(14,round(radius*1.2)),round(radius*2.3)+1,2))
            if best > ranks.get(key, -1):
                ranks[key], locations[key] = best, (x,y,radius)
    ordered = sorted(ranks, key=ranks.get, reverse=True)
    if not ordered or ranks[ordered[0]] < .78 or len(ordered) > 1 and ranks[ordered[0]]-ranks[ordered[1]] < .10:
        return None
    key = ordered[0]
    return {"item": key, "confidence": ranks[key], "circle": locations[key], "source": "screen"}


def capture_item(rect, templates):
    from cv2 import error
    from PIL import ImageGrab
    x, y, w, h = rect
    with ImageGrab.grab(bbox=(x,y,x+w,y+h), all_screens=True, include_layered_windows=False) as image:
        try:
            return detect_item(image, templates)
        except error:
            return None


class QuickBuyReader:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="quick-buy")
        self.job = None
        self.templates = None
        self.version = None
        self.context = None
        self.candidate = None
        self.after = self.seen = 0
        self.status = {"state": "inactive", "source": "screen"}

    def poll(self, rect, session, catalog):
        version = catalog.get("patch")
        context = rect, session, version
        now = monotonic()
        if context != self.context:
            self.context, self.candidate = context, None
            self.status = {"state": "searching" if rect else "inactive", "source": "screen"}
        if version != self.version:
            self.version, self.templates = version, None
        if self.job and self.job[2].done():
            requested, kind, job = self.job
            self.job = None
            try:
                result = job.result()
                if kind == "templates" and requested == version:
                    self.templates = result
                elif kind == "capture" and requested == context and rect:
                    self.status = {"state": "searching", "source": "screen"}
                    if result and result["item"] == self.candidate:
                        self.status = dict(result, state="ready")
                        self.seen = now
                    self.candidate = result["item"] if result else None
            except (OSError, ValueError, KeyError, TypeError, RuntimeError, ImportError):
                if requested == context or kind == "templates" and requested == version:
                    self.status = {"state": "unavailable", "source": "screen"}
                    self.after = now+15
        if self.status.get("state") == "ready" and now-self.seen > 2.5:
            self.status = {"state": "searching", "source": "screen"}
            self.candidate = None
        if rect and not self.job and now >= self.after:
            if self.templates is None:
                self.status = {"state": "loading_templates", "source": "screen"}
                self.job = version, "templates", self.executor.submit(load_templates, version, tuple(catalog.get("items", {})))
            else:
                self.after = now+.65
                self.job = context, "capture", self.executor.submit(capture_item, rect, self.templates)
        return self.status if rect else {"state": "inactive", "source": "screen"}

    def close(self):
        self.executor.shutdown(wait=False, cancel_futures=True)


def remaining_price(item_id, owned, items):
    """Credit each actually owned recipe component at most once."""
    from collections import Counter
    bag = Counter(map(str, owned))
    def cost(key, path=(), component=False):
        if key in path:
            raise ValueError("Cyclic recipe")
        if component and bag[key]:
            bag[key] -= 1
            return 0
        item = items.get(key, {})
        total = item.get("g", (item.get("gold") or {}).get("total"))
        if type(total) not in (int, float) or total < 0:
            raise ValueError("Unknown price")
        parts = item.get("from", [])
        if not isinstance(parts, list):
            raise ValueError("Invalid recipe")
        child_total = sum(items.get(str(k), {}).get("g", (items.get(str(k), {}).get("gold") or {}).get("total", -1)) for k in parts)
        if child_total > total:
            raise ValueError("Invalid component prices")
        return total-child_total+sum(cost(str(k), (*path,key), True) for k in parts)
    try:
        return cost(str(item_id))
    except (ValueError, TypeError):
        return None
