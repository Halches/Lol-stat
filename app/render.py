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
        if title: self.row(('text', title.upper(), 'gold', 9, True, CAPS), pad=4)

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
        return rgb(c if c.startswith('#') else self.t.get(c, c))

    def render(self):
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
            d.rounded_rectangle((0, 0, W - 1, H - 1), self.px(8), fill=rgb(self.t['bg']) + (255,))
            if self.accent: d.rectangle((self.px(6), pady, self.px(6) + self.px(3) - 1, H - pady), fill=self._color(self.accent) + (255,))
        y = pady
        for (segs, pad), sz, h in zip(self.rows, sizes, heights):
            x = padx + stripe
            for s, (w, sh) in zip(segs, sz):
                if s[0] in ('text', 'cell'):
                    f = self._font(s) if s[0] == 'text' else font(self.fn, self.px(s[3]), s[4])
                    col = self._color(s[2]) + (255,)
                    tx = x + (w - int(f.getlength(s[1])) if s[0] == 'cell' and s[6] == 'r' else 0)
                    ty = y + (h - sh) // 2
                    if self.plate: d.text((tx, ty), s[1], font=f, fill=col)
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
        return im


CAPS = 'Fira Sans Condensed SemiBold'   # подписи капсом и цифры
OUTLINE = (5, 10, 16, 255)              # обводка текста без плашки: #050a10


def tint(im, color, size):
    """Значок по альфа-каналу, перекрашенный в один цвет (значки ролей в золото)."""
    a = im.getchannel('A').resize((size, size), Image.LANCZOS)
    out = Image.new('RGBA', (size, size), rgb(color) + (0,)); out.putalpha(a)
    return out


def tab_plates(rect, rows, top, theme, k, frame=False):
    """Таблички стоимости предметов у внешних краёв таблицы Tab. rect = (x, y, w, h) таблицы внутри картинки,
    rows = 5 пар (союзник, враг): {'v': стоимость, 'd': разница с оппонентом} или None; top = (наши, их) или None.
    frame — режим подгонки: золотая пунктирная рамка с уголками по краям таблицы."""
    X, Y, TW, TH = rect
    PW, gap = int(112 * k), int(8 * k)
    W, H = int(TW + 2 * (PW + gap) + 2), int(TH + Y + 2)
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    t = lambda c: rgb(theme[c]) + (255,)
    rh = TH / 5
    ph = max(int(22 * k), int(rh * .62))
    big, small = font(CAPS, max(11, int(19 * k))), font(CAPS, max(9, int(13 * k)))
    for i, (a, e) in enumerate(rows):
        cy = int(Y + i * rh + rh / 2)
        for side, p in (('a', a), ('e', e)):
            if not p: continue
            x0 = X - gap - PW if side == 'a' else X + TW + gap
            d.rounded_rectangle((x0, cy - ph // 2, x0 + PW, cy + ph // 2), int(6 * k), fill=t('bg'))
            edge = (x0, x0 + int(3 * k)) if side == 'a' else (x0 + PW - int(3 * k), x0 + PW)
            d.rectangle((edge[0], cy - ph // 2 + int(5 * k), edge[1], cy + ph // 2 - int(5 * k)), fill=t('blue' if side == 'a' else 'red'))
            val = f"{p['v'] / 1000:.1f}k".replace('.', ',')
            if side == 'a':
                d.text((x0 + int(12 * k), cy), val, font=big, fill=t('fg'), anchor='lm')
                dd = p.get('d')
                if dd is not None:
                    col = 'mute' if abs(dd) < 100 else 'good' if dd > 0 else 'bad'
                    d.text((x0 + PW - int(9 * k), cy), f'{dd:+.0f}' if abs(dd) >= 100 else '0', font=small, fill=t(col), anchor='rm')
            else:
                d.text((x0 + PW - int(12 * k), cy), val, font=big, fill=t('fg'), anchor='rm')
    if top:
        ours, theirs = top
        diff = ours - theirs
        bw, bh = int(360 * k), int(30 * k)
        bx, by = int(X + TW / 2 - bw / 2), int(Y - bh - 8 * k)
        d.rounded_rectangle((bx, by, bx + bw, by + bh), int(6 * k), fill=t('bg'))
        cy = by + bh // 2
        d.text((bx + int(12 * k), cy), f'{ours / 1000:.1f}k'.replace('.', ','), font=small, fill=t('blue'), anchor='lm')
        d.text((bx + bw - int(12 * k), cy), f'{theirs / 1000:.1f}k'.replace('.', ','), font=small, fill=t('red'), anchor='rm')
        lx0, lx1 = bx + int(62 * k), bx + bw - int(62 * k)
        frac = ours / max(1, ours + theirs)
        d.rounded_rectangle((lx0, cy - int(3 * k), lx1, cy + int(3 * k)), int(3 * k), fill=t('red'))
        d.rounded_rectangle((lx0, cy - int(3 * k), lx0 + max(int(6 * k), int((lx1 - lx0) * frac)), cy + int(3 * k)), int(3 * k), fill=t('blue'))
        lbl = f'{diff:+.0f}' if diff else '0'
        tw = int(small.getlength(lbl)) + int(12 * k)
        mx = (lx0 + lx1) // 2
        d.rounded_rectangle((mx - tw // 2, cy - int(10 * k), mx + tw // 2, cy + int(10 * k)), int(5 * k), fill=t('bg'))
        d.text((mx, cy), lbl, font=small, fill=t('good' if diff > 0 else 'bad' if diff < 0 else 'mute'), anchor='mm')
    if frame:   # полупрозрачная заливка: в Windows пиксели цвета-ключа пропускают клики, а рамку нужно ловить мышью
        d.rectangle((X, Y, X + TW - 1, Y + TH - 1), fill=rgb(theme['bg']) + (110,))
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
        f = font(CAPS, max(10, int(13 * k)))
        msg = 'ПОДГОНКА: ТЯНИ ЗА КРАЯ И УГЛЫ, ВНУТРИ — ПЕРЕНОС'
        mw = int(f.getlength(msg)) + int(16 * k)
        d.rounded_rectangle((X + TW / 2 - mw / 2, Y + TH / 2 - 14 * k, X + TW / 2 + mw / 2, Y + TH / 2 + 14 * k), int(6 * k), fill=t('bg'))
        d.text((X + TW / 2, Y + TH / 2), msg, font=f, fill=g, anchor='mm')
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
