# Рисование карточек виджетов через Pillow: сглаженный шрифт, скруглённая плашка, иконки, обводка текста.
# Tk сам рисует текст грубо, поэтому виджеты поверх игры — это картинки, собранные здесь.
import os
import sys
import copy
from functools import lru_cache
from PIL import Image, ImageDraw, ImageFont

FONT_FILES = {   # шрифты Windows: обычный и полужирный
    'Segoe UI': ('segoeui.ttf', 'seguisb.ttf'), 'Bahnschrift': ('bahnschrift.ttf', 'bahnschrift.ttf'),
    'Calibri': ('calibri.ttf', 'calibrib.ttf'), 'Trebuchet MS': ('trebuc.ttf', 'trebucbd.ttf'),
    'Verdana': ('verdana.ttf', 'verdanab.ttf'), 'Consolas': ('consola.ttf', 'consolab.ttf'),
}
HERE = getattr(sys, '_MEIPASS', None) or os.path.dirname(os.path.abspath(__file__))
_ff = lambda n: os.path.join(HERE, 'fonts', n + '.ttf')   # свои шрифты лежат рядом в fonts/
FONT_FILES.update({'Golos Text': (_ff('GolosText-Regular'), _ff('GolosText-SemiBold')),
                   'Fira Sans Condensed Medium': (_ff('FiraSansCondensed-Medium'), _ff('FiraSansCondensed-SemiBold')),
                   'Fira Sans Condensed SemiBold': (_ff('FiraSansCondensed-SemiBold'), _ff('FiraSansCondensed-SemiBold')),
                   'Forum': (_ff('Forum-Regular'), _ff('Forum-Regular'))})
FALLBACK = ['/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf']
_cache = {}


def font(name, size, bold=False):
    k = (name, size, bold)
    if k in _cache: return _cache[k]
    files = FONT_FILES.get(name, FONT_FILES['Segoe UI'])
    windir = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')
    f = None
    for p in (os.path.join(windir, files[1 if bold else 0]), FALLBACK[1 if bold else 0], FALLBACK[0]):
        try:
            f = ImageFont.truetype(p, size); break
        except Exception:
            continue
    if f is None:
        try: f = ImageFont.load_default(size)
        except Exception: f = ImageFont.load_default()
    _cache[k] = f
    return f


def rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def wrap(text, f, width):
    words, lines, cur = text.split(), [], ''
    for w in words:
        t = (cur + ' ' + w).strip()
        if f.getlength(t) <= width or not cur: cur = t
        else: lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines or ['']


class Card:
    """Строки из сегментов: ('text', str, цвет, размер, жирный) | ('cell', str, цвет, размер, жирный, ширина, 'l'|'r') — ячейка
    фиксированной ширины для ровных столбцов | ('img', PIL.Image) | ('gap', px) | ('bar', доля, цвет1, цвет2, ширина).
    Плашка — фон без рамки, акцент — полоска слева; без плашки текст с тонкой тёмной обводкой. title — подпись капсом сверху."""

    def __init__(self, theme, font_name, scale=1.0, plate=True, accent=None, width=None, title=None):
        self.t, self.fn, self.k, self.plate = theme, font_name, scale, plate
        self.accent, self.width = accent, width
        self.rows = []
        self.title = title
        if title: self.row(('text', title.upper(), 'gold', 11, False, 'Forum'), ('gap', 24), pad=7)

    def px(self, n): return max(1, round(n * self.k))

    def row(self, *segs, pad=4):
        self.rows.append((segs, pad)); return self

    def text(self, s, color='fg', size=12, bold=False, wrap_to=None):
        """Абзац с переносом по ширине: каждая строка — отдельный ряд."""
        f = font(self.fn, self.px(size), bold)
        for ln in (wrap(s, f, self.px(wrap_to)) if wrap_to else [s]):
            self.row(('text', ln, color, size, bold), pad=2)
        return self

    def _font(self, s):
        if s[1] and any(c.isdigit() for c in s[1]) and not any(c.isalpha() and c != 'k' for c in s[1]):
            return font('Forum', self.px(s[3]+2), False)
        return font(s[5] if s[0] == 'text' and len(s) > 5 else self.fn, self.px(s[3]), s[4])

    def _seg_size(self, s):
        if s[0] == 'text':
            return int(self._font(s).getlength(s[1])), self.px(s[3]) + self.px(5)
        if s[0] == 'cell': return self.px(s[5]), self.px(s[3]) + self.px(5)
        if s[0] == 'img': return s[1].width, s[1].height
        if s[0] == 'gap': return self.px(s[1]), 1
        if s[0] == 'bar': return self.px(s[4]), self.px(7)
        return 0, 0

    def _color(self, c):
        if self.plate and c in HUD: return rgb(HUD[c])
        return rgb(c if c.startswith('#') else self.t.get(c, c))

    def render(self):
        card = copy.copy(self)
        card.k *= 2
        card.rows = [([('img', s[1].resize((s[1].width*2,s[1].height*2),Image.Resampling.LANCZOS)) if s[0]=='img' else s for s in segs],pad) for segs,pad in self.rows]
        im = card._render()
        return im.resize((max(1,im.width//2),max(1,im.height//2)),Image.Resampling.LANCZOS)

    def _render(self):
        stripe = self.px(3) + self.px(6) if self.accent and self.plate else 0
        padx, pady = self.px(12), self.px(9)
        sizes = [[self._seg_size(s) for s in segs] for segs, _ in self.rows]
        widths = [sum(w for w, h in r) + self.px(6) * max(0, len(r) - 1) for r in sizes]
        heights = [max([h for w, h in r] or [0]) for r in sizes]
        W = max(widths + [self.px(self.width or 0) - 2 * padx - stripe, 10]) + 2 * padx + stripe
        H = sum(heights) + sum(self.px(p) for _, p in self.rows[1:]) + 2 * pady
        im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        if self.plate:
            hud_frame(d, (0, 0, W-1, H-1), self.px(7))
            if self.accent: d.rectangle((self.px(6), pady, self.px(6) + self.px(3) - 1, H - pady), fill=self._color(self.accent) + (255,))
        y = pady
        for row_index, ((segs, pad), sz, h) in enumerate(zip(self.rows, sizes, heights)):
            x = padx + stripe
            for s, (w, sh) in zip(segs, sz):
                if s[0] in ('text', 'cell'):
                    f = self._font(s)
                    col = self._color(s[2]) + (255,)
                    tx = x + (w - int(f.getlength(s[1])) if s[0] == 'cell' and s[6] == 'r' else 0)
                    ty = y + (h - sh) // 2
                    if self.plate:
                        d.text((tx, ty+1), s[1], font=f, fill=OUTLINE)
                        d.text((tx, ty), s[1], font=f, fill=col, stroke_width=1 if f.getname()[0]=='Forum' else 0)
                    else: d.text((tx, ty), s[1], font=f, fill=col, stroke_width=max(1, round(self.k)), stroke_fill=OUTLINE)
                elif s[0] == 'img':
                    im.alpha_composite(s[1].convert('RGBA'), (x, y + (h - sh) // 2))
                elif s[0] == 'bar':
                    frac, c1, c2 = s[1], self._color(s[2]), self._color(s[3])
                    by = y + (h - sh) // 2
                    d.rounded_rectangle((x, by, x + w, by + sh), sh // 2, fill=c2 + (255,))
                    d.rounded_rectangle((x, by, x + max(sh, int(w * frac)), by + sh), sh // 2, fill=c1 + (255,))
                x += w + self.px(6)
            y += h + self.px(pad)
            if row_index == 0 and self.title and self.plate:
                ly, mx, rad = y-self.px(3), W/2, self.px(2)
                d.line((padx,ly,W-padx,ly),fill='#756243',width=max(1,self.px(.5)))
                d.polygon([(mx-rad,ly),(mx,ly-rad),(mx+rad,ly),(mx,ly+rad)],fill=HUD['gold'])
        return im


CAPS = 'Fira Sans Condensed SemiBold'   # подписи капсом и цифры
OUTLINE = (5, 10, 16, 255)              # обводка текста без плашки: #050a10

# Game overlays keep the scoreboard's dark materials, even in the daytime app theme.
HUD = {'deep': '#10272d', 'gold': '#c9a56b', 'fg': '#ede5d2', 'mute': '#9aafa9', 'blue': '#91d8f3',
       'red': '#ed8b76', 'good': '#91d8f3', 'bad': '#ed8b76', 'warn': '#e4c68b'}


def hud_frame(d, box, cut=5):
    x, y, r, b = box
    cut = min(cut, (r-x)/3, (b-y)/3)
    def points(inset):
        a, c, e, f = x+inset, y+inset, r-inset, b-inset
        n = max(1, cut-inset)
        return [(a+n,c),(e-n,c),(e,c+n),(e,f-n),(e-n,f),(a+n,f),(a,f-n),(a,c+n)]
    d.polygon(points(0), fill='#081b22', outline='#b38b50', width=max(1,round(cut/7)))
    d.line(points(2)+[points(2)[0]], fill='#304847', width=1)
    d.line((x+cut,y,r-cut,y), fill='#e4c68b', width=1)


def pin_icon(pinned, k):
    size = max(18, round(22*k)); z = 3
    im = Image.new('RGBA', (size*z, size*z)); d = ImageDraw.Draw(im)
    hud_frame(d, (0, 0, size*z-1, size*z-1), 3*z)
    c = HUD['gold'] if pinned else HUD['mute']
    def p(x,y): return round(x*size*z/22), round(y*size*z/22)
    d.polygon([p(7,5),p(15,5),p(14,8),p(14,11),p(17,13),p(5,13),p(8,11),p(8,8)], fill=c)
    d.line([p(11,13),p(11,19)], fill=c, width=2*z)
    if not pinned: d.line([p(4,18),p(18,4)], fill='#081b22', width=3*z); d.line([p(4,18),p(18,4)], fill=c, width=z)
    return im.resize((size,size), Image.Resampling.LANCZOS)


def hud_badge(text, direction, color, width, height):
    z = 4; w, h = width*z, height*z
    im = Image.new('RGBA', (w,h)); d = ImageDraw.Draw(im)
    hud_frame(d, (0,0,w-1,h-1), min(w*.24,h*.16))
    if direction:
        # A solid, engraved silhouette survives the narrow real scoreboard gutter.
        pts = [(.16,.27),(.43,.16),(.43,.23),(.84,.25),(.43,.29),(.43,.36)]
        if direction > 0: pts = [(1-x,y) for x,y in pts]
        d.polygon([(round(x*w),round(y*h)) for x,y in pts], fill=HUD['gold'])
    f = font('Forum', round(h*.40))
    box = f.getbbox(text); tw, th = box[2]-box[0], box[3]-box[1]
    glyph = Image.new('RGBA',(tw+4*z, th+4*z)); gd = ImageDraw.Draw(glyph)
    col = HUD.get(color, HUD['mute'])
    gd.text((2*z-box[0],2*z-box[1]+z//2),text,font=f,fill=OUTLINE)
    gd.text((2*z-box[0],2*z-box[1]),text,font=f,fill=col,stroke_width=1)
    # Keep the serif numerals tall; compress horizontally only when needed.
    gw = min(glyph.width, w-4*z)
    glyph = glyph.resize((max(1,gw),glyph.height), Image.Resampling.LANCZOS)
    gy = round(h*(.61 if direction else .50)-glyph.height/2)
    im.alpha_composite(glyph, ((w-glyph.width)//2,gy))
    return im.resize((width,height), Image.Resampling.LANCZOS)


def tint(im, color, size):
    """Значок по альфа-каналу, перекрашенный в один цвет (значки ролей в золото)."""
    a = im.getchannel('A').resize((size, size), Image.LANCZOS)
    out = Image.new('RGBA', (size, size), rgb(color) + (0,)); out.putalpha(a)
    return out


def tab_handle(theme, font_name, k):
    """Небольшая ручка настройки Tab с теми же шрифтами, что у оверлеев."""
    text = 'TAB · тяни | Shift: размер'
    f = font(font_name, max(10, round(11 * k)))
    pad = max(6, round(8 * k))
    im = Image.new('RGB', (int(f.getlength(text)) + pad * 2, round(18 * k) + pad), rgb(theme['gold']))
    ImageDraw.Draw(im).text((pad, im.height / 2), text, font=f, fill=rgb(theme['on_gold']), anchor='lm')
    return im


@lru_cache(maxsize=1)
def advantage_arrow_source():
    """Generated left-pointing sprite. Ignore nearly transparent stray pixels in its bounds."""
    path = os.path.join(HERE, 'ui_assets', 'tab-advantage-arrow.png')
    with Image.open(path) as source:
        im = source.convert('RGBA')
    box = im.getchannel('A').point(lambda a: 255 if a >= 8 else 0).getbbox()
    return im.crop(box) if box else im


@lru_cache(maxsize=64)
def advantage_arrow(width, height, direction):
    """-1 points left, +1 right. Same generated asset, rotated at runtime."""
    im = advantage_arrow_source().copy()
    im.thumbnail((max(1, width), max(1, height)), Image.Resampling.LANCZOS)
    return im.transpose(Image.Transpose.ROTATE_180) if direction > 0 else im


def tab_advantage(left, right, left_ally=True):
    """One magnitude per actual scoreboard row; colour is relative to our team."""
    if left is None or right is None: return '—', 0, 'mute'
    diff = left['v'] - right['v']
    if not diff: return '0', 0, 'mute'
    value = abs(round(diff))
    text = str(value) if value < 10_000 else f'{value / 1000:.1f}'.rstrip('0').rstrip('.').replace('.', ',') + 'k'
    ours = diff if left_ally else -diff
    return text, -1 if diff > 0 else 1, 'blue' if ours > 0 else 'red'


def tab_badge_geometry(rect, k):
    """Fit inside the narrow centre gutter, even with a large helper UI scale."""
    X, Y, TW, TH = rect
    rh = TH / 5
    width = max(10, min(round(24*k), round(rh*.28), round(TW*.018)))
    height = max(12, min(round(36*k), round(rh*.64)))
    return X + TW/2, rh, width, height


def tab_plates(rect, rows, theme, k, frame=False, left_ally=True, totals=None):
    """One compact arrow + difference between each pair of players, no team total.

    rect = (x, y, w, h) of the detected table body; rows contain the actual
    left/right players' inventory values, or None for an unidentified player.
    """
    X, Y, TW, TH = rect
    W, H = int(X + TW + 2), int(TH + Y + 2)
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    t = lambda c: rgb(theme[c]) + (255,)
    cx, rh, bw, bh = tab_badge_geometry(rect, k)
    for i, (a, e) in enumerate(rows):
        if a is None and e is None: continue
        cy = int(Y + i * rh + rh / 2)
        text, direction, color = tab_advantage(a, e, left_ally)
        x0, y0 = round(cx-bw/2), round(cy-bh/2)
        im.alpha_composite(hud_badge(text, direction, color, bw, bh), (x0,y0))
    if totals is not None:
        left, right = totals
        ours = left-right if left_ally else right-left
        width = min(round(TW*.52), round(520*k))
        height = max(30, round(46*k))
        bx = round(X+(TW-width)/2)
        by = max(0, round(Y-TH*.35-height))
        hud_frame(d, (bx,by,bx+width-1,by+height-1), max(3,round(8*k)))
        title = font('Forum', max(8,round(10*k)))
        d.text((bx+width/2,by+3*k), 'ПЕРЕВЕС ПО ПРЕДМЕТАМ',font=title,fill=HUD['gold'],anchor='mt')
        small = font('Forum', max(9,round(16*k)))
        lc, rc = (HUD['blue'],HUD['red']) if left_ally else (HUD['red'],HUD['blue'])
        d.text((bx+10*k,by+height*.58),f'{left/1000:.1f}k'.replace('.',','),font=small,fill=lc,anchor='lm')
        d.text((bx+width-10*k,by+height*.58),f'{right/1000:.1f}k'.replace('.',','),font=small,fill=rc,anchor='rm')
        a, b = bx+round(width*.21), bx+round(width*.79)
        yy = by+height-round(10*k)
        split = a+round((b-a)*left/max(1,left+right))
        d.rectangle((a,yy,b,yy+max(3,round(5*k))),fill=rc,outline=HUD['gold'])
        if split > a: d.rectangle((a+1,yy+1,min(b-1,split),yy+max(2,round(5*k))-1),fill=lc)
        d.line(((a+b)/2,yy-2,(a+b)/2,yy+7*k),fill=HUD['gold'])
        label = f'{ours:+,.0f}'.replace(',',' ') if ours else '0'
        f = font('Forum',max(11,round(19*k)))
        color = HUD['blue'] if ours>0 else HUD['red'] if ours<0 else HUD['mute']
        mid = bx+width/2
        badge_w = f.getlength(label)+32*k
        hud_frame(d, (mid-badge_w/2,by+height*.27,mid+badge_w/2,by+height*.75),max(2,round(4*k)))
        d.text((mid+6*k,by+height*.51),label,font=f,fill=color,anchor='mm')
        if ours:
            arrow_x = mid-f.getlength(label)/2-7*k
            direction = -1 if left>right else 1
            pts = [(-5,0),(0,-3),(0,-1),(6,-1),(6,1),(0,1),(0,3)]
            d.polygon([(arrow_x+x*k*(-direction),by+height*.51+y*k) for x,y in pts],fill=HUD['gold'])
    if frame:   # Только контур: клики через всю рамку идут в игру, мышь принимает отдельная ручка.
        g, L = t('gold'), int(18 * k)
        x0, y0, x1, y1 = X, Y, X + TW - 1, Y + TH - 1
        dash = int(8 * k)
        for xx in range(int(x0), int(x1), dash * 2):
            d.line((xx, y0, min(xx + dash, x1), y0), fill=g, width=2); d.line((xx, y1, min(xx + dash, x1), y1), fill=g, width=2)
        for yy in range(int(y0), int(y1), dash * 2):
            d.line((x0, yy, x0, min(yy + dash, y1)), fill=g, width=2); d.line((x1, yy, x1, min(yy + dash, y1)), fill=g, width=2)
        for cx, cy, sx, sy in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
            d.line((cx, cy, cx + sx * L, cy), fill=g, width=int(4 * k) or 2); d.line((cx, cy, cx, cy + sy * L), fill=g, width=int(4 * k) or 2)
        for i in range(1, 5):
            yy = int(Y + i * rh)
            for xx in range(int(x0), int(x1), dash * 2): d.line((xx, yy, min(xx + dash // 2, x1), yy), fill=t('gold') [:3] + (140,), width=1)
    return im


def death_map(marks, size, theme):
    """Схема карты Ущелья с точками: смерти красным крестом (до 14 минуты крупнее), убийства и помощь зелёным."""
    k = 4; S = size * k
    im = Image.new('RGBA', (S, S), rgb(theme['deep']) + (255,)); d = ImageDraw.Draw(im)
    P = lambda x, y: (x / 15000 * S, S - y / 15000 * S)
    lane = rgb(theme['line']) + (255,); w = max(2, S // 40)
    d.line([P(1200, 1800), P(1200, 13800), P(13200, 13800)], fill=lane, width=w)           # верхняя линия
    d.line([P(1800, 1200), P(13800, 1200), P(13800, 13200)], fill=lane, width=w)           # нижняя
    d.line([P(1800, 1800), P(13200, 13200)], fill=lane, width=w)                           # средняя
    d.line([P(3200, 11800), P(11800, 3200)], fill=rgb(theme['blue']) + (90,), width=w * 2)  # река
    for (x, y), c in (((900, 900), 'blue'), ((14100, 14100), 'red')):
        cx, cy = P(x, y); r = S / 22
        d.rectangle((cx - r, cy - r, cx + r, cy + r), fill=rgb(theme[c]) + (255,))
    for x, y, t, kind in marks:
        cx, cy = P(x, y)
        if kind == 'death':
            r = S / (34 if t < 840 else 48)
            d.line((cx - r, cy - r, cx + r, cy + r), fill=rgb(theme['bad']) + (255,), width=w)
            d.line((cx - r, cy + r, cx + r, cy - r), fill=rgb(theme['bad']) + (255,), width=w)
        else:
            r = S / 70
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=rgb(theme['good']) + (255,))
    return im.resize((size, size), Image.LANCZOS)


def gold_chart(gs, w, h, theme):
    """Разница золота с оппонентом по минутам: столбики вверх (впереди, зелёные) и вниз (позади, красные), метки 10/15/20/25."""
    k = 4; W, H = w * k, h * k
    im = Image.new('RGBA', (W, H), rgb(theme['deep']) + (255,)); d = ImageDraw.Draw(im)
    diff = [x - y for x, y in zip(gs['me'], gs['opp'])]
    top = max(500, max(abs(v) for v in diff))
    mid, pad = H / 2, H * .08
    sc = (mid - pad) / top
    bw = W / max(1, len(diff))
    line = rgb(theme['line']) + (255,)
    for m in range(5, len(diff), 5):
        x = m * bw + bw / 2
        d.line((x, pad / 2, x, H - pad / 2), fill=line, width=k)
    for i, v in enumerate(diff):
        x0, x1 = i * bw + bw * .15, (i + 1) * bw - bw * .15
        y = mid - v * sc
        d.rectangle((x0, min(y, mid), x1, max(y, mid)), fill=rgb(theme['good' if v >= 0 else 'bad']) + (255,))
    d.line((0, mid, W, mid), fill=rgb(theme['mute']) + (255,), width=k)
    return im.resize((w, h), Image.LANCZOS)


def logo(size, theme):
    """Монограмма: буква H в шестиугольнике, перекладина — бирюзовый кристалл (как logo-dark.svg, сетка 64×64)."""
    k = 4; S = size * k; im = Image.new('RGBA', (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    P = lambda pts: [(x / 64 * S, y / 64 * S) for x, y in pts]
    hexa = P([(32, 4), (56, 18), (56, 46), (32, 60), (8, 46), (8, 18)])
    gold = rgb(theme['gold']) + (255,)
    d.polygon(hexa, fill=rgb(theme['bg']) + (255,))
    d.line(hexa + hexa[:1], fill=gold, width=max(2, round(3.5 / 64 * S)), joint='curve')
    for x in (19, 39): d.rounded_rectangle(P([(x, 18), (x + 6, 46)]), radius=S / 64, fill=gold)
    d.polygon(P([(25, 32), (32, 26.5), (39, 32), (32, 37.5)]), fill=rgb(theme['good']) + (255,))
    return im.resize((size, size), Image.LANCZOS)


def rounded_icon(im, size, radius=0.18, gray=False, ring=None):
    """Квадратная иконка со скруглением и, по желанию, цветной рамкой."""
    from PIL import ImageOps
    im = im.convert('RGBA').resize((size, size), Image.LANCZOS)
    if gray: im = ImageOps.grayscale(im).convert('RGBA')
    m = Image.new('L', (size, size), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, size - 1, size - 1), int(size * radius), fill=255)
    im.putalpha(Image.composite(im.getchannel('A'), m, m))
    if ring:
        ImageDraw.Draw(im).rounded_rectangle((0, 0, size - 1, size - 1), int(size * radius), outline=rgb(ring) + (255,), width=max(1, size // 18))
    return im


def nav_icon(kind, color, size=20):
    """Линейные иконки бокового меню (рисуются в 4 раза крупнее и уменьшаются для гладкости)."""
    k = 4; S = size * k; w = max(2, round(S / 11))
    im = Image.new('RGBA', (S, S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    c = rgb(color) + (255,)
    P = lambda *xy: [(x * S / 24, y * S / 24) for x, y in xy]
    def box(x0, y0, x1, y1, r=2): d.rounded_rectangle((x0 * S / 24, y0 * S / 24, x1 * S / 24, y1 * S / 24), int(r * S / 24), outline=c, width=w)
    def circ(cx, cy, r, fill=False):
        b = ((cx - r) * S / 24, (cy - r) * S / 24, (cx + r) * S / 24, (cy + r) * S / 24)
        d.ellipse(b, fill=c) if fill else d.ellipse(b, outline=c, width=w)
    ln = lambda *xy: d.line(P(*xy), fill=c, width=w, joint='curve')
    if kind == 'home': ln((3, 11), (12, 4), (21, 11)); ln((5, 10), (5, 20), (19, 20), (19, 10))
    elif kind == 'list': ln((4, 6), (20, 6)); ln((4, 12), (20, 12)); ln((4, 18), (14, 18))
    elif kind == 'bulb': circ(12, 9, 6); ln((9, 15), (9, 18), (15, 18), (15, 15)); ln((10, 21), (14, 21))
    elif kind == 'window': box(3, 5, 21, 19); ln((3, 10), (21, 10))
    elif kind == 'look': circ(12, 12, 9); circ(8, 10, 1.5, True); circ(12, 7, 1.5, True); circ(16, 10, 1.5, True)
    elif kind == 'sound': ln((4, 9), (8, 9), (13, 5), (13, 19), (8, 15), (4, 15), (4, 9)); ln((17, 9), (18, 12), (17, 15))
    elif kind == 'keys': box(2, 6, 22, 18); ln((6, 10), (7, 10)); ln((11, 10), (12, 10)); ln((16, 10), (17, 10)); ln((7, 14), (17, 14))
    elif kind == 'clock': circ(12, 12, 9); ln((12, 7), (12, 12), (15, 14))
    elif kind == 'update': ln((12, 3), (12, 15)); ln((7, 10), (12, 15), (17, 10)); ln((4, 20), (20, 20))
    elif kind == 'search': circ(10, 10, 6); ln((15, 15), (20, 20))
    elif kind == 'site': circ(12, 12, 9); ln((3, 12), (21, 12)); d.arc(((8) * S / 24, 3 * S / 24, 16 * S / 24, 21 * S / 24), 0, 360, fill=c, width=w)
    return im.resize((size, size), Image.LANCZOS)
