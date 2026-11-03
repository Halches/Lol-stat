"""Local, conservative Tab scoreboard detection. No Tk, network or saved screenshots.

Portrait templates come from the bundled Data Dragon assets. Coordinates are
normalised to game height, like tab_rect. An uncertain match returns None.
"""
import base64
from dataclasses import dataclass, replace
from itertools import combinations, permutations
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
        divider = tolerant[body_top+5:bottom-5, cx-2:cx+3].any(axis=1)
        # Some capture paths include our badges. Inspect the clear row gaps.
        phase = ((np.arange(len(divider))+5)*5/(bottom-body_top)) % 1
        clear = (phase<.16) | (phase>.84)
        if not clear.any() or divider[clear].mean() < .65: continue
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
    matched = []
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
        matched.append((row,a))
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
    slopes=[(b.y-a.y)/(rb-ra) for ra,a in matched for rb,b in matched if rb>ra]
    if len({r for r,_ in matched})>=3 and slopes:
        refined=statistics.median(slopes)
        first=statistics.median(a.y-(r+.5)*refined for r,a in matched)
        if abs(refined-step)<step*.08 and abs(first-y0)<step*.24:
            y0,y1=first,first+5*refined
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


def assign_visible_faces(candidates,remaining):
    """Resolve the whole column jointly; reject a close alternative assignment."""
    rows=sorted(candidates)
    if not rows or len(remaining)<len(rows) or len(remaining)>5: return {}
    ranked=[]
    for order in permutations(remaining,len(rows)):
        scores=[candidates[row].get(champ,-1.) for row,champ in zip(rows,order)]
        ranked.append((sum(scores),min(scores),order))
    ranked.sort(reverse=True)
    total,weakest,order=ranked[0]
    if weakest<.70 or total/len(rows)<.76: return {}
    if len(ranked)<2 or total-ranked[1][0]<.08: return {}
    return dict(zip(rows,order))


def recover_question_marks(layout, rgb, sources, players, anchors=()):
    """Read face edges around '?' inside a confirmed frame, never roster order."""
    import cv2
    import numpy as np
    h,w = rgb.shape[:2]
    dx,y,rw,rh = layout.rect
    x, step = dx*h+w/2, rh*h/5
    gray = cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
    hsv = cv2.cvtColor(rgb,cv2.COLOR_RGB2HSV)
    columns = [list(c) for c in layout.columns]
    recovered_scores=[]
    counts = {c:sum(p['c']==c for p in players) for c in sources}
    for col,team in enumerate(layout.teams):
        roster = [p['c'] for p in players if p['team']==team]
        expected=x+step*(1.75+col*7.1)
        known_points=[]
        for row,champ in enumerate(columns[col]):
            hits=[a for a in anchors if a.champ==champ and a.score>=.76 and abs(a.x-expected)<step*.4 and abs(a.y-(y*h+step*(row+.5)))<step*.3]
            if hits: known_points.append(max(hits,key=lambda a:a.score))
        known_centres=[a.x for a in known_points]
        portrait_x=statistics.median(known_centres) if known_centres else expected
        base_size=statistics.median(a.size for a in known_points) if known_points else step*.65
        candidates = {}
        for row,known in enumerate(columns[col]):
            if known: continue
            cx,cy = portrait_x, y*h+step*(row+.5)
            q = hsv[max(0,round(cy-step*.23)):round(cy+step*.23),max(0,round(cx-step*.23)):round(cx+step*.23)]
            if q.size==0: continue
            yellow = cv2.inRange(q,np.array((15,110,120)),np.array((40,255,255)))
            if np.count_nonzero(yellow)/yellow.size < .035: continue
            roi = gray[max(0,round(cy-step*.5)):round(cy+step*.5),max(0,round(cx-step*.65)):round(cx+step*.65)]
            scores = {}
            for champ in roster:
                if champ not in sources or counts[champ]!=1: continue
                best = -1.
                for size in range(max(14,round(base_size*.80)),round(base_size*1.20)+1):
                    icon = cv2.resize(sources[champ],(size,size),interpolation=cv2.INTER_AREA)
                    m = round(size*.18); template = icon[m:-m,m:-m]
                    if template.shape[0]>roi.shape[0] or template.shape[1]>roi.shape[1]: continue
                    mask = np.full(template.shape,255,np.uint8)
                    mask[:,round(template.shape[1]*.25):round(template.shape[1]*.75)] = 0
                    if template[mask>0].std()<8: continue
                    matches = cv2.matchTemplate(roi,template,cv2.TM_CCOEFF_NORMED,mask=mask)
                    matches = np.nan_to_num(matches,nan=-1.,posinf=-1.,neginf=-1.)
                    yy,xx=np.indices(matches.shape)
                    centred=(abs(xx+template.shape[1]/2-roi.shape[1]/2)<=step*.14) & (abs(yy+template.shape[0]/2-roi.shape[0]/2)<=step*.14)
                    matches[~centred]=-1.
                    best = max(best,float(matches.max()))
                scores[champ] = best
            candidates[row] = scores
        used={c for side in columns for c in side if c}
        remaining=[c for c in roster if c not in used and counts.get(c)==1]
        for row,champ in assign_visible_faces(candidates,remaining).items():
            columns[col][row]=champ
            recovered_scores.append(candidates[row][champ])
        remaining = [c for c in roster if c not in columns[col]]
        if len(roster)==5 and len(set(roster))==5 and columns[col].count(None)==1 and len(remaining)==1:
            columns[col][columns[col].index(None)] = remaining[0]
    confidence=min(layout.confidence,sum(recovered_scores)/len(recovered_scores)) if recovered_scores else layout.confidence
    return replace(layout,columns=tuple(tuple(c) for c in columns),confidence=confidence)


def frame_portraits(gray,frames,sources,cancelled=None):
    """Search portrait strips first; keep global search as a fallback."""
    import cv2
    found={c:[] for c in sources}
    h,w=gray.shape
    for x0,y0,x1,y1 in frames:
        step=(y1-y0)/5
        for col in (0,1):
            cx=x0+step*(1.75+col*7.1)
            left,right=max(0,round(cx-step*.6)),min(w,round(cx+step*.6))
            strip=gray[y0:y1,left:right]
            for champ,src in sources.items():
                if cancelled and cancelled.is_set(): return []
                for size in range(max(14,round(step*.43)//2*2),round(step*.90)+1,2):
                    for crop in (0.,.08):
                        trim=round(src.shape[0]*crop)
                        source=src[trim:-trim,trim:-trim] if trim else src
                        icon=cv2.resize(source,(size,size),interpolation=cv2.INTER_AREA)
                        margin=round(size*.18); template=icon[margin:-margin,margin:-margin]
                        if template.std()<5 or template.shape[0]>strip.shape[0] or template.shape[1]>strip.shape[1]: continue
                        matches=cv2.matchTemplate(strip,template,cv2.TM_CCOEFF_NORMED)
                        for _ in range(3):
                            _,score,_,(xx,yy)=cv2.minMaxLoc(matches)
                            if score<.68: break
                            found[champ].append(Anchor(champ,left+xx+template.shape[1]/2,y0+yy+template.shape[0]/2,size,score))
                            matches[max(0,yy-size):yy+size,max(0,xx-size):xx+size]=-1
    out=[]
    for candidates in found.values():
        picked=[]
        for a in sorted(candidates,key=lambda a:a.score,reverse=True):
            if any(abs(a.x-b.x)<a.size*.7 and abs(a.y-b.y)<a.size*.7 for b in picked): continue
            picked.append(a)
            if len(picked)==4: break
        out.extend(picked)
    return out


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
    sources={}
    for champ in sorted({p['c'] for p in players}):
        if cancelled and cancelled.is_set(): return None
        raw = portraits.get(champ)
        if not raw: continue
        with Image.open(io.BytesIO(base64.b64decode(raw))) as im:
            sources[champ] = cv2.cvtColor(np.asarray(im.convert('RGB')), cv2.COLOR_RGB2GRAY)
    if frames:
        local=frame_portraits(gray,frames,sources,cancelled)
        confirmed=[layout for frame in frames if (layout:=fit_frame(local,players,frame,w,h))]
        if len(confirmed)==1: return recover_question_marks(confirmed[0],rgb,sources,players,local)
        if len(confirmed)>1: return None
    anchors, frame_anchors = [], []
    for champ,src in sources.items():
        if cancelled and cancelled.is_set(): return None
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
    if len(confirmed) == 1: return recover_question_marks(confirmed[0],rgb,sources,players,frame_anchors)
    if len(confirmed) > 1: return None
    return fit_grid(anchors, players, w, h)


def capture_and_detect(rect, portraits, players, cancelled):
    from PIL import ImageGrab
    x, y, w, h = rect
    if cancelled.is_set(): return None
    # Layered helper windows are omitted; pixels stay in memory and on this PC.
    with ImageGrab.grab(bbox=(x, y, x+w, y+h), all_screens=True, include_layered_windows=False) as frame:
        return detect(frame, portraits, players, cancelled)
