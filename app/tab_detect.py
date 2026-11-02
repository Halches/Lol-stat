"""Local, conservative Tab scoreboard detection. No Tk, network or saved screenshots.

Portrait templates come from the bundled Data Dragon assets. Coordinates are
normalised to game height, like tab_rect. An uncertain match returns None.
"""
import base64
from dataclasses import dataclass
from itertools import combinations
import io
import statistics


@dataclass(frozen=True)
class Anchor:
    champ: str
    x: float
    y: float
    size: float
    score: float


@dataclass(frozen=True)
class Layout:
    rect: tuple
    # Champion keys in actual screen order; None means identity is uncertain.
    columns: tuple
    teams: tuple
    confidence: float


def fit_grid(anchors, players, width, height):
    """Require two team columns, >=3 anchors each and a shared five-row grid.

    Reject HUD portraits, kill feeds, duplicate champions and ambiguous layouts.
    Do not guess identities when multiple portraits are covered by death timers.
    """
    by_champ = {}
    for p in players:
        by_champ.setdefault(p['c'], []).append(p['team'])
    usable = [a for a in anchors if len(by_champ.get(a.champ, [])) == 1 and a.score >= .68]
    groups = []
    for seed in usable:
        group = [a for a in usable if abs(a.x - seed.x) < height * .012]
        # One best scale/position per champion in a column.
        best = {}
        for a in sorted(group, key=lambda a: a.score, reverse=True): best.setdefault(a.champ, a)
        group = sorted(best.values(), key=lambda a: a.y)
        if len(group) < 3 or len(group) > 5: continue
        teams = {by_champ[a.champ][0] for a in group}
        if len(teams) != 1: continue
        sig = tuple(a.champ for a in group)
        if all(sig != tuple(a.champ for a in g) for g in groups): groups.append(group)
    fits = []
    for a, b in combinations(groups, 2):
        left, right = sorted((a, b), key=lambda g: statistics.median(p.x for p in g))
        teams = (by_champ[left[0].champ][0], by_champ[right[0].champ][0])
        if teams[0] == teams[1]: continue
        lx, rx = (statistics.median(p.x for p in g) for g in (left, right))
        # Current standard scoreboard: portrait-column distance ~7.1 row steps.
        step = (rx - lx) / 7.1
        if not height * .035 <= step <= height * .115: continue
        all_points = left + right
        if not .43 * step <= statistics.median(p.size for p in all_points) <= .86 * step: continue
        first, last = min(p.y for p in all_points), max(p.y for p in all_points)
        if abs((last - first) / step - 4) > .22: continue
        step = (last - first) / 4
        columns, valid = [], True
        for group, team in zip((left, right), teams):
            slots = [None] * 5
            for p in group:
                row = round((p.y - first) / step)
                if not 0 <= row < 5 or abs(p.y - first - row * step) > step * .12 or slots[row]:
                    valid = False; break
                slots[row] = p.champ
            remaining = [p['c'] for p in players if p['team'] == team and p['c'] not in slots]
            if slots.count(None) == 1 and len(remaining) == 1: slots[slots.index(None)] = remaining[0]
            columns.append(tuple(slots))
        if not valid: continue
        # Portrait anchors locate the outer margins of the standard LoL table.
        # Unlike the old fixed screen position these follow its HUD scale.
        x0, x1 = lx - 1.75 * step, rx + 6.4 * step
        y0, h = first - step / 2, step * 5
        if x0 < -step * .15 or x1 > width + step * .15 or y0 < 0 or y0 + h > height: continue
        rect = ((x0 - width / 2) / height, y0 / height, (x1 - x0) / height, h / height)
        fits.append(Layout(rect, tuple(columns), teams, sum(p.score for p in all_points) / len(all_points)))
    if not fits: return None
    fits.sort(key=lambda f: f.confidence, reverse=True)
    best = fits[0]
    if any(max(abs(a - b) for a, b in zip(best.rect, f.rect)) > .025 for f in fits[1:]): return None
    return best


def detect(frame, portraits, players, cancelled=None):
    """Find bundled portraits at several scales, then validate their geometry.

    Work is bounded to a 540px-high image and only the champions in this match.
    Central crops omit portrait rings/levels; grayscale also handles dead heroes.
    Imports are lazy so missing CV dependencies leave manual placement usable.
    """
    import cv2
    import numpy as np
    from PIL import Image
    cv2.setNumThreads(1)
    if frame.width < 320 or frame.height < 240: return None
    scale = min(540 / frame.height, 1400 / frame.width, 1.)
    gray = cv2.cvtColor(np.asarray(frame.convert('RGB')), cv2.COLOR_RGB2GRAY)
    gray = cv2.resize(gray, (round(frame.width * scale), round(frame.height * scale)), interpolation=cv2.INTER_AREA)
    h, w = gray.shape
    if gray.std() < 3: return None  # fullscreen capture can return a black frame
    anchors = []
    for champ in sorted({p['c'] for p in players}):
        if cancelled and cancelled.is_set(): return None
        raw = portraits.get(champ)
        if not raw: continue
        with Image.open(io.BytesIO(base64.b64decode(raw))) as im:
            src = cv2.cvtColor(np.asarray(im.convert('RGB')), cv2.COLOR_RGB2GRAY)
        candidates = []
        for size in range(max(14, round(h * .024)), round(h * .083) + 1, 2):
            if cancelled and cancelled.is_set(): return None
            # Data Dragon has a thin frame that the in-game circular portrait crops.
            for crop in (0., .08):
                trim = round(src.shape[0] * crop)
                source = src[trim:src.shape[0]-trim, trim:src.shape[1]-trim] if trim else src
                icon = cv2.resize(source, (size, size), interpolation=cv2.INTER_AREA)
                margin = round(size * .18)
                template = icon[margin:size-margin, margin:size-margin]
                if template.std() < 5: continue
                scores = cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED)
                # A champion can also appear in a HUD portrait/kill feed.
                for _ in range(3):
                    _, score, _, (x, y) = cv2.minMaxLoc(scores)
                    if score < .68: break
                    candidates.append(Anchor(champ, x + template.shape[1] / 2, y + template.shape[0] / 2, size, score))
                    scores[max(0, y-size):y+size, max(0, x-size):x+size] = -1
        picked = []
        for a in sorted(candidates, key=lambda p: p.score, reverse=True):
            if any(abs(a.x-b.x) < a.size*.7 and abs(a.y-b.y) < a.size*.7 for b in picked): continue
            picked.append(a)
            if len(picked) == 4: break
        anchors.extend(picked)
    return fit_grid(anchors, players, w, h)


def capture_and_detect(rect, portraits, players, cancelled):
    from PIL import ImageGrab
    x, y, w, h = rect
    if cancelled.is_set(): return None
    # Layered helper windows are omitted; pixels stay in memory and on this PC.
    with ImageGrab.grab(bbox=(x, y, x+w, y+h), all_screens=True, include_layered_windows=False) as frame:
        return detect(frame, portraits, players, cancelled)
