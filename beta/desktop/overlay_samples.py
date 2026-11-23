"""Visual examples of the planned match overlays."""
from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QPolygonF
from PySide6.QtWidgets import QWidget

from overlay_themes import (
    BAD, DEFAULT_THEME, FOREGROUND, GOLD, GOOD, MUTED, THEMES, alpha, asset_folder, draw_panel, hud_font,
)


METRICS = (
    ("CS/мин", "7,4", "7,1", 1),
    ("Золото/мин", "386", "421", -1),
    ("KDA", "3,2", "2,8", 1),
    ("Уровень", "11", "12", -1),
)
STANDINGS = (
    ("Jinx", "Джинкс", 8420, True), ("Darius", "Дариус", 8110, False), ("Viktor", "Виктор", 7650, True),
    ("Ahri", "Ари", 7130, False), ("LeeSin", "Ли Син", 6810, True), ("Caitlyn", "Кейтлин", 6440, False),
    ("Sett", "Сетт", 5930, True), ("Rakan", "Рэйкан", 5290, False), ("Lux", "Люкс", 4920, True),
    ("RekSai", "Рек’Сай", 4700, False),
)
LANE_DIFFS = (-2180, 2110, 520, 1980, -370)
TEAM_GOLD = (33730, 31670)
TEAM_DIFF = TEAM_GOLD[0] - TEAM_GOLD[1]
OBJECTIVES = (("Дракон", "0:48", "Личинки", "0:22", 1),
              ("Дракон", "2:14", "Герольд", "1:06", 3),
              ("Дракон", "3:24", "Барон Нашор", "2:16", 2))


def money(value):
    return f"{value:,}".replace(",", " ")


def text(painter, value, rect, size=15, color=FOREGROUND, alignment=Qt.AlignmentFlag.AlignLeft):
    painter.setFont(hud_font(size))
    painter.setPen(color)
    painter.drawText(QRectF(*rect), alignment | Qt.AlignmentFlag.AlignVCenter, value)


def triangle(painter, x, y, direction, color, size=5):
    points = {
        "up": [(0, -1), (-1, .65), (1, .65)],
        "down": [(0, 1), (-1, -.65), (1, -.65)],
        "left": [(-1, 0), (.65, -1), (.65, 1)],
        "right": [(1, 0), (-.65, -1), (-.65, 1)],
    }
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(color)
    painter.drawPolygon(QPolygonF([QPointF(x + sx * size, y + sy * size) for sx, sy in points[direction]]))


def trend(value):
    return GOOD if value > 0 else BAD if value < 0 else MUTED


class SampleCard(QWidget):
    dimensions = {
        "metrics": (235, 134), "lane": (201, 58), "standings": (232, 339),
        "purchase": (150, 58), "objectives": (185, 61), "tab": (254, 69),
    }

    def __init__(self, _artwork, _catalog, *, kind, demo=False):
        super().__init__()
        self.kind = kind
        self.theme = THEMES[DEFAULT_THEME]
        self.scale = 1
        self.phase = 0
        self.frames = {}

    def set_content(self, _sample):
        self.update()

    def set_appearance(self, theme, scale):
        self.theme, self.scale = theme, scale
        self.updateGeometry()
        self.update()

    def sizeHint(self):
        width, height = self.dimensions[self.kind]
        return QSize(round(width * self.scale), round(height * self.scale))

    def pixmap(self, name):
        if name not in self.frames:
            self.frames[name] = QPixmap(str(asset_folder("overlay-preview") / f"{name}.png"))
        return self.frames[name]

    def icon(self, painter, name, x, y, size):
        image = self.pixmap(name)
        if not image.isNull():
            painter.drawPixmap(QRectF(x, y, size, size), image, QRectF(image.rect()))

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        width, height = self.dimensions[self.kind]
        painter.scale(self.width() / width, self.height() / height)
        if self.kind != "tab":
            draw_panel(painter, QRectF(0, 0, width, height), self.theme)
        getattr(self, f"draw_{self.kind}")(painter)

    def draw_metrics(self, painter):
        text(painter, "Ранг выше", (107, 4, 96, 22), 13, MUTED, Qt.AlignmentFlag.AlignRight)
        for i, (name, current, reference, direction) in enumerate(METRICS):
            y = 27 + i * 25
            if i % 2 == 0:
                painter.fillRect(QRectF(8, y, 219, 25), alpha(self.theme.light, 13))
            text(painter, name, (13, y, 100, 25), 13, MUTED)
            text(painter, current, (115, y, 39, 25), 16, trend(direction), Qt.AlignmentFlag.AlignRight)
            text(painter, reference, (161, y, 42, 25), 13, MUTED, Qt.AlignmentFlag.AlignRight)
            triangle(painter, 217, y + 12, "up" if direction > 0 else "down", trend(direction), 4)

    def draw_lane(self, painter):
        self.icon(painter, "Ahri", 10, 9, 40)
        text(painter, "Ари", (59, 9, 58, 40), 15)
        triangle(painter, 120, 29, "up", GOOD, 5)
        text(painter, "+520", (130, 9, 59, 40), 19, GOOD, Qt.AlignmentFlag.AlignRight)

    def draw_standings(self, painter):
        ranked = sorted(STANDINGS, key=lambda champion: champion[2], reverse=True)
        highest_cost = max(1, ranked[0][2])
        text(painter, "Стоимость предметов", (12, 6, 208, 21), 12, MUTED)
        for rank, (champion, name, cost, ally) in enumerate(ranked, 1):
            y = 31 + (rank - 1) * 30
            color = GOOD if ally else BAD
            painter.fillRect(QRectF(7, y, 218, 27), alpha(color, 31))
            painter.fillRect(QRectF(7, y, 2, 27), alpha(color, 164))
            text(painter, str(rank), (11, y, 17, 27), 12, MUTED, Qt.AlignmentFlag.AlignRight)
            self.icon(painter, champion, 35, y + 2, 23)
            text(painter, name, (65, y + 1, 93, 18), 13)
            text(painter, money(cost), (160, y + 1, 58, 18), 14, FOREGROUND, Qt.AlignmentFlag.AlignRight)
            painter.fillRect(QRectF(65, y + 21, 153, 3), alpha(FOREGROUND, 33))
            painter.fillRect(QRectF(65, y + 21, 153 * cost / highest_cost, 3), alpha(color, 190))

    def draw_purchase(self, painter):
        self.icon(painter, "3089", 10, 9, 40)
        text(painter, "До покупки", (59, 6, 80, 19), 12, MUTED)
        text(painter, "640", (59, 24, 72, 27), 21, GOLD)

    def draw_objectives(self, painter):
        share = self.pixmap("objective-portraits")
        cell_w, cell_h = share.width() / 2, share.height() / 2
        _, dragon_time, _, top_time, top_icon = OBJECTIVES[self.phase]
        for x, index, value in ((8, 0, dragon_time), (98, top_icon, top_time)):
            if not share.isNull():
                source = QRectF(index % 2 * cell_w, index // 2 * cell_h, cell_w, cell_h)
                painter.drawPixmap(QRectF(x, 11, 34, 36), share, source)
            text(painter, value, (x + 35, 11, 50, 36), 15, GOLD if value.startswith("0:") else FOREGROUND)
        painter.setPen(QPen(alpha(self.theme.light, 75), 1))
        painter.drawLine(QPointF(92, 15), QPointF(92, 46))

    def draw_tab(self, painter):
        draw_team_bar(painter, QRectF(12, 7, 230, 28), self.theme)
        for index, value in enumerate(LANE_DIFFS):
            draw_comparison(painter, QRectF(11 + 47 * index, 40, 44, 23), self.theme, value)


def draw_team_bar(painter, rect, theme):
    # Match the scoreboard's side edges and leave its own top border visible at the join.
    left, top = rect.left() + .5, rect.top() + .5
    right, bottom = rect.right() - .5, rect.bottom()
    corner = min(8, rect.height() * .28)
    outline = QPainterPath(QPointF(left, bottom))
    outline.lineTo(left, top + corner)
    outline.lineTo(left + corner, top)
    outline.lineTo(right - corner, top)
    outline.lineTo(right, top + corner)
    outline.lineTo(right, bottom)

    surface = QLinearGradient(0, top, 0, bottom)
    surface.setColorAt(0, alpha(theme.base, 237))
    surface.setColorAt(1, alpha("#0c2427", 230))
    painter.fillPath(outline, surface)
    trim = QLinearGradient(0, top, 0, bottom)
    trim.setColorAt(0, alpha(theme.light, 209))
    trim.setColorAt(1, alpha("#9b895f", 226))
    painter.setPen(QPen(trim, 1))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(outline)

    stripe = QRectF(rect.left() + 9, rect.bottom() - 8, rect.width() - 18, 4)
    split = stripe.width() * TEAM_GOLD[0] / sum(TEAM_GOLD)
    painter.fillRect(QRectF(stripe.left(), stripe.top(), split, stripe.height()), GOOD)
    painter.fillRect(QRectF(stripe.left() + split, stripe.top(), stripe.width() - split, stripe.height()), BAD)
    text(painter, f"{TEAM_DIFF:+,}".replace(",", " "),
         (rect.left(), rect.top(), rect.width(), rect.height() - 8), min(22, rect.height() * .57),
         trend(TEAM_DIFF), Qt.AlignmentFlag.AlignHCenter)


def draw_comparison(painter, rect, theme, value):
    draw_panel(painter, rect, theme)
    color = trend(value)
    text(painter, f"{value:+}" if value else "0", (rect.left(), rect.top(), rect.width(), rect.height() * .60),
         min(20, rect.height() * .48), color, Qt.AlignmentFlag.AlignHCenter)
    if value:
        triangle(painter, rect.center().x(), rect.top() + rect.height() * .74, "left" if value > 0 else "right",
                 color, min(5, rect.height() * .16))


class ScoreboardDecoration(QWidget):
    """Draw only the attached banner and the five badges in the native gutter."""

    def __init__(self):
        super().__init__()
        self.theme = THEMES[DEFAULT_THEME]
        self.rows = 0
        self.header = 0
        self.bar = 0
        self.scale = 1

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        draw_team_bar(painter, QRectF(0, 0, self.width(), self.bar), self.theme)
        step = self.rows / 5
        label_width = min(54 * self.scale, step)
        label_height = min(33 * self.scale, step * .74)
        for index, value in enumerate(LANE_DIFFS):
            y = self.header + (index + .5) * step - label_height / 2
            draw_comparison(painter, QRectF((self.width() - label_width) / 2, y, label_width, label_height),
                            self.theme, value)
