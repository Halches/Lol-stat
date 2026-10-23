# Рисование карточек виджетов через Pillow: сглаженный шрифт, скруглённая плашка, иконки, обводка текста.
# Tk сам рисует текст грубо, поэтому виджеты поверх игры — это картинки, собранные здесь.
import os
from PIL import Image, ImageDraw, ImageFont

FONT_FILES = {   # шрифты Windows: обычный и полужирный
    'Segoe UI': ('segoeui.ttf', 'seguisb.ttf'), 'Bahnschrift': ('bahnschrift.ttf', 'bahnschrift.ttf'),
    'Calibri': ('calibri.ttf', 'calibrib.ttf'), 'Trebuchet MS': ('trebuc.ttf', 'trebucbd.ttf'),
    'Verdana': ('verdana.ttf', 'verdanab.ttf'), 'Consolas': ('consola.ttf', 'consolab.ttf'),
}
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
        stripe = self.px(4) if self.accent else 0
        sizes = [[self._seg_size(s) for s in segs] for segs, _ in self.rows]
        widths = [sum(w for w, h in r) + self.px(6) * max(0, len(r) - 1) for r in sizes]
        heights = [max([h for w, h in r] or [0]) for r in sizes]
        W = max(widths + [self.px(self.width or 0) - 2 * padx - stripe, 10]) + 2 * padx + stripe
        H = sum(heights) + sum(self.px(p) for _, p in self.rows[1:]) + 2 * pady
        im = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        r = self.px(10)
        if self.plate:
            d.rounded_rectangle((0, 0, W - 1, H - 1), r, fill=rgb(self.t['panel']) + (255,), outline=rgb(self.t['line']) + (255,))
            if self.accent:   # цветная полоска слева, повторяет скругление карточки
                m = Image.new('L', (W, H), 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, W - 1, H - 1), r, fill=255)
                m2 = Image.new('L', (W, H), 0); m2.paste(m.crop((0, 0, stripe, H)), (0, 0))
                im.paste(Image.new('RGBA', (W, H), rgb(self.t[self.accent]) + (255,)), (0, 0), m2)
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
