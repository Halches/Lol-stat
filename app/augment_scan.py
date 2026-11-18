"""Recognize only locally visible card titles. All coordinates are physical pixels."""
from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations
from statistics import median

from PIL import Image, ImageGrab, ImageOps

from augment_advice import DATA, identify


@dataclass(frozen=True)
class Line:
    text: str
    x: float
    y: float
    height: float


def selection(lines, mode, center, height):
    """Require a level, centered row of distinct cards before showing any advice."""
    matches = []
    for line in lines:
        texts = [line.text]
        for below in lines:
            if (0 < below.y - line.y < 1.9 * max(line.height, below.height)
                    and abs(below.x - line.x) < height * .055):
                texts.append(line.text + ' ' + below.text)
        for text in reversed(texts):
            card = identify(mode, text)
            if card:
                matches.append((line.x, line.y, card))
                break
    for count in (4, 3):
        for group in combinations(sorted(matches, key=lambda m: m[0]), count):
            xs = [x for x, _, _ in group]
            ys = [y for _, y, _ in group]
            gaps = [b - a for a, b in zip(xs, xs[1:])]
            if (max(ys) - min(ys) < height * .035
                    and abs((xs[0] + xs[-1]) / 2 - center) < height * .045
                    and min(gaps) > height * .17 and max(gaps) < height * .49
                    and max(gaps) - min(gaps) < height * .065
                    and len({card['key'] for _, _, card in group}) == count):
                return group
    return ()


def region(rect):
    x, y, w, h = rect
    half = min(w / 2, h * .85)
    return round(x + w / 2 - half), round(y + .28*h), round(x + w / 2 + half), round(y + .57*h)


class Reader:
    def __init__(self, model_dir=None):
        from tesserocr import PSM, PyTessBaseAPI
        self.api = PyTessBaseAPI(path=str(model_dir or DATA / 'tessdata'), lang='rus+eng', psm=PSM.SPARSE_TEXT)
        self.api.SetVariable('classify_enable_learning', '0')

    def read(self, band, mode, height):
        # Most map frames have no dark card interiors. Skip OCR on those frames.
        gray = band.convert('L')
        sample = gray.resize((64, 24))
        if sum(v < 68 for v in sample.tobytes()) < 64 * 24 * .48:
            return ()
        factor = min(2.7, 1800 / height)
        target = gray.resize((round(gray.width*factor), round(gray.height*factor)), Image.Resampling.BILINEAR)
        self.api.SetImage(ImageOps.invert(target).point(lambda p: 255 if p > 138 else 0))
        lines = defaultdict(list)
        for row in self.api.GetTSVText(0).splitlines():
            fields = row.split('\t', 11)
            if len(fields) != 12 or fields[0] != '5' or not fields[11].strip():
                continue
            left, top, width, h = map(int, fields[6:10])
            if .008 * height <= h / factor <= .058 * height:
                lines[tuple(fields[1:5])].append((left, top, width, h, fields[11]))
        candidates = []
        for words in lines.values():
            parts = []
            for word in sorted(words):
                if parts and word[0] - (parts[-1][0] + parts[-1][2]) > height * factor * .03:
                    candidates.append(self._line(parts, factor))
                    parts = []
                parts.append(word)
            if parts:
                candidates.append(self._line(parts, factor))
        return selection(candidates, mode, band.width / 2, height)

    @staticmethod
    def _line(words, scale):
        first, last = words[0], words[-1]
        return Line(' '.join(w[4] for w in words), (first[0]+last[0]+last[2])/(2*scale),
                    median(w[1] for w in words)/scale, max(w[3] for w in words)/scale)

    def capture(self, mode, rect):
        from app_config import game_focused, game_rect
        if not game_focused() or game_rect() != rect:
            return ()
        left, top, right, bottom = region(rect)
        with ImageGrab.grab(bbox=(left, top, right, bottom), all_screens=True,
                            include_layered_windows=False) as band:
            group = self.read(band, mode, rect[3])
        return tuple((round(left+x), round(top+y), card) for x,y,card in group)
