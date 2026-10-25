# Рисование карточек виджетов через Pillow: сглаженный шрифт, скруглённая плашка, иконки, обводка текста.
# Tk сам рисует текст грубо, поэтому виджеты поверх игры — это картинки, собранные здесь.
import os
import sys
from PIL import Image, ImageDraw, ImageFont

FONT_FILES = {   # шрифты Windows: обычный и полужирный
    'Segoe UI': ('segoeui.ttf', 'seguisb.ttf'), 'Bahnschrift': ('bahnschrift.ttf', 'bahnschrift.ttf'),
    'Calibri': ('calibri.ttf', 'calibrib.ttf'), 'Trebuchet MS': ('trebuc.ttf', 'trebucbd.ttf'),
    'Verdana': ('verdana.ttf', 'verdanab.ttf'), 'Consolas': ('consola.ttf', 'consolab.ttf'),
}
HERE = getattr(sys, '_MEIPASS', None) or os.path.dirname(os.path.abspath(__file__))
for _n in ('Manrope', 'Oswald'):   # свои шрифты лежат рядом в fonts/
    FONT_FILES[_n] = tuple(os.path.join(HERE, 'fonts', f'{_n}-{w}.ttf') for w in ('Regular', 'Bold'))
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
    """Строки из сегментов: ('text', str, цвет, размер, жирный) | ('img', PIL.Image) | ('gap', px) | ('bar', доля, цвет1, цвет2, ширина)."""

    def __init__(self, theme, font_name, scale=1.0, plate=True, accent=None, width=None):
        self.t, self.fn, self.k, self.plate = theme, font_name, scale, plate
        self.accent, self.width = accent, width
        self.rows = []

    def px(self, n): return max(1, round(n * self.k))

    def row(self, *segs, pad=4):
        self.rows.append((segs, pad)); return self

    def text(self, s, color='fg', size=12, bold=False, wrap_to=None):
        """Абзац с переносом по ширине: каждая строка — отдельный ряд."""
        f = font(self.fn, self.px(size), bold)
        for ln in (wrap(s, f, self.px(wrap_to)) if wrap_to else [s]):
            self.row(('text', ln, color, size, bold), pad=2)
        return self

    def _seg_size(self, s):
        if s[0] == 'text':
            f = font(self.fn, self.px(s[3]), s[4])
            return int(f.getlength(s[1])), self.px(s[3]) + self.px(5)
        if s[0] == 'img': return s[1].width, s[1].height
        if s[0] == 'gap': return self.px(s[1]), 1
        if s[0] == 'bar': return self.px(s[4]), self.px(8)
        return 0, 0

    def render(self):
        padx, pady = self.px(12), self.px(8)
        stripe = 0
        sizes = [[self._seg_size(s) for s in segs] for segs, _ in self.rows]
        widths = [sum(w for w, h in r) + self.px(6) * max(0, len(r) - 1) for r in sizes]
        heights = [max([h for w, h in r] or [0]) for r in sizes]
        W = max(widths + [self.px(self.width or 0) - 2 * padx - stripe, 10]) + 2 * padx + stripe
        H = sum(heights) + sum(self.px(p) for _, p in self.rows[1:]) + 2 * pady
        im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        r = self.px(10)
        if self.plate:   # акцент — цветная рамка всей карточки
            line = rgb(self.t[self.accent]) if self.accent else rgb(self.t.get('edge', self.t['line']))
            d.rounded_rectangle((0, 0, W - 1, H - 1), r, fill=rgb(self.t['panel']) + (255,), outline=line + (255,), width=self.px(2) if self.accent else 1)
        y = pady
        for (segs, pad), sz, h in zip(self.rows, sizes, heights):
            x = padx + stripe
            for s, (w, sh) in zip(segs, sz):
                if s[0] == 'text':
                    f = font(self.fn, self.px(s[3]), s[4])
                    col = rgb(self.t.get(s[2], s[2]) if not s[2].startswith('#') else s[2])
                    ty = y + (h - sh) // 2
                    if self.plate: d.text((x, ty), s[1], font=f, fill=col + (255,))
                    else: d.text((x, ty), s[1], font=f, fill=col + (255,), stroke_width=self.px(2), stroke_fill=(0, 0, 0, 255))
                elif s[0] == 'img':
                    im.alpha_composite(s[1].convert('RGBA'), (x, y + (h - sh) // 2))
                elif s[0] == 'bar':
                    frac, c1, c2 = s[1], rgb(self.t[s[2]]), rgb(self.t[s[3]])
                    by = y + (h - sh) // 2
                    d.rounded_rectangle((x, by, x + w, by + sh), sh // 2, fill=c2 + (255,))
                    d.rounded_rectangle((x, by, x + max(sh, int(w * frac)), by + sh), sh // 2, fill=c1 + (255,))
                x += w + self.px(6)
            y += h + self.px(pad)
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
