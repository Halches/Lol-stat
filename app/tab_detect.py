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
    source: str = 'portraits'


def find_frames(rgb):
    """Find the standard gold scoreboard frame, including an almost empty one.

    Two long sides, bottom, header separator and centre divider are all required.
    This only proposes geometry; a champion portrait must still confirm it.
    """
    import cv2
    import numpy as np
    height, width = rgb.shape[:2]
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    gold = cv2.inRange(hsv, np.array((12, 65, 40)), np.array((40, 255, 245)))
    gold = cv2.morphologyEx(gold, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    vertical = cv2.morphologyEx(gold, cv2.MORPH_OPEN, np.ones((max(15, round(height * .12)), 1), np.uint8))
    _, _, stats, _ = cv2.connectedComponentsWithStats(vertical)
    sides = [(x + w//2, y, y+h) for x, y, w, h, area in stats[1:]
             if w < height*.018 and height*.20 < h < height*.70]
    tolerant = cv2.dilate(gold, np.ones((3, 3), np.uint8)) > 0
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    frames = []
    for a, b in combinations(sides, 2):
        left, right = sorted((a, b))
        x0, x1 = int(left[0]), int(right[0])
        top, bottom = int(max(left[1], right[1])), int(min(left[2], right[2]))
        w, h = x1-x0, bottom-top
        if h <= 0: continue
        if not height*.5 < w < min(width*.96, height*1.65) or not 2.25 < w/h < 3.1: continue
        if abs(left[1]-right[1]) > h*.08 or abs(left[2]-right[2]) > h*.08: continue
        # The bottom border is sometimes dim in its centre; use a small y band.
        ends = tolerant[max(top, bottom-5):min(height, bottom+3), x0+3:x1-3].mean(axis=1)
        if not len(ends) or ends.max() < .60: continue
        bottom = max(top, bottom-5) + int(ends.argmax())
        # Header line separates team totals from the five player rows.
        lo, hi = top + round(h*.04), top + round(h*.24)
        headers = tolerant[lo:hi, x0+5:x1-5].mean(axis=1)
        if not len(headers) or headers.max() < .52: continue
        body_top = lo + int(headers.argmax())
        if not 2.6 < w / (bottom-body_top) < 3.4: continue
        cx = (x0+x1)//2
        if tolerant[body_top+5:bottom-5, cx-2:cx+3].any(axis=1).mean() < .65: continue
        if (gray[body_top+3:bottom-3, x0+3:x1-3] < 100).mean() < .75: continue
        frame = (x0, body_top, x1, bottom)
        if not any(max(abs(v-q) for v, q in zip(frame, f)) < 5 for f in frames): frames.append(frame)
    return frames


def fit_frame(anchors, players, frame, width, height):
    """Confirm a frame by visible portraits; supports practice/custom matches."""
    by_champ = {}
    for p in players: by_champ.setdefault(p['c'], []).append(p['team'])
    x0, y0, x1, y1 = frame
    step = (y1-y0)/5
    columns, teams, scores, used = [[None]*5, [None]*5], [None, None], [], set()
    for a in sorted(anchors, key=lambda p: p.score, reverse=True):
        if a.score < .76 or len(by_champ.get(a.champ, [])) != 1 or a.champ in used: continue
        if not step*.43 < a.size < step*.90: continue
        col = 0 if a.x < (x0+x1)/2 else 1
        expected_x = x0 + step*1.75 + col*step*7.1
        row = round((a.y-y0)/step-.5)
        if abs(a.x-expected_x) > step*.40 or not 0 <= row < 5: continue
        if abs(a.y-y0-(row+.5)*step) > step*.24 or columns[col][row]: continue
        team = by_champ[a.champ][0]
        if teams[col] not in (None, team) or teams[1-col] == team: continue
        columns[col][row], teams[col] = a.champ, team
        used.add(a.champ); scores.append(a.score)
    if not scores: return None
    for col in (0, 1):
        if teams[col] is None:
            others = {p['team'] for p in players} - {teams[1-col]}
            teams[col] = next(iter(others)) if len(others) == 1 else ('CHAOS' if teams[1-col] == 'ORDER' else 'ORDER')
        roster = [p['c'] for p in players if p['team'] == teams[col]]
        remaining = [c for c in roster if c not in used]
        # Only a full five-player team has a uniquely inferable last row.
        if len(roster) == 5 and len(remaining) == 1 and columns[col].count(None) == 1:
            columns[col][columns[col].index(None)] = remaining[0]
    rect = ((x0-width/2)/height, y0/height, (x1-x0)/height, (y1-y0)/height)
    return Layout(rect, tuple(tuple(c) for c in columns), tuple(teams), sum(scores)/len(scores), 'frame')


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
    rgb = cv2.resize(np.asarray(frame.convert('RGB')), (round(frame.width * scale), round(frame.height * scale)), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    h, w = gray.shape
    if gray.std() < 3: return None  # fullscreen capture can return a black frame
    frames = find_frames(rgb)
    allowed = np.zeros(gray.shape, dtype=bool) if frames else None
    for x0, y0, x1, y1 in frames:
        step = (y1-y0)/5
        for col in (0, 1):
            cx = x0 + step*1.75 + col*step*7.1
            allowed[y0:y1, max(0, round(cx-step*.6)):min(w, round(cx+step*.6))] = True
    anchors, frame_anchors = [], []
    for champ in sorted({p['c'] for p in players}):
        if cancelled and cancelled.is_set(): return None
        raw = portraits.get(champ)
        if not raw: continue
        with Image.open(io.BytesIO(base64.b64decode(raw))) as im:
            src = cv2.cvtColor(np.asarray(im.convert('RGB')), cv2.COLOR_RGB2GRAY)
        candidates, frame_candidates = [], []
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
                maps = [(scores, candidates)]
                if allowed is not None:
                    cy, cx = template.shape[0]//2, template.shape[1]//2
                    restricted = scores.copy()
                    restricted[~allowed[cy:cy+scores.shape[0], cx:cx+scores.shape[1]]] = -1
                    maps.append((restricted, frame_candidates))
                # A champion can also appear in a HUD portrait/kill feed.
                for matches, found in maps:
                    for _ in range(3):
                        _, score, _, (x, y) = cv2.minMaxLoc(matches)
                        if score < .68: break
                        found.append(Anchor(champ, x + template.shape[1] / 2, y + template.shape[0] / 2, size, score))
                        matches[max(0, y-size):y+size, max(0, x-size):x+size] = -1
        for found, target in ((candidates, anchors), (frame_candidates, frame_anchors)):
            picked = []
            for a in sorted(found, key=lambda p: p.score, reverse=True):
                if any(abs(a.x-b.x) < a.size*.7 and abs(a.y-b.y) < a.size*.7 for b in picked): continue
                picked.append(a)
                if len(picked) == 4: break
            target.extend(picked)
    confirmed = [layout for f in frames if (layout := fit_frame(frame_anchors, players, f, w, h))]
    if len(confirmed) == 1: return confirmed[0]
    if len(confirmed) > 1: return None
    return fit_grid(anchors, players, w, h)


def capture_and_detect(rect, portraits, players, cancelled):
    from PIL import ImageGrab
    x, y, w, h = rect
    if cancelled.is_set(): return None
    # Layered helper windows are omitted; pixels stay in memory and on this PC.
    with ImageGrab.grab(bbox=(x, y, x+w, y+h), all_screens=True, include_layered_windows=False) as frame:
        return detect(frame, portraits, players, cancelled)
