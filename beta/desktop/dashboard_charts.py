"""Rank and activity charts for the Qt home screen."""

from calendar import monthrange
from datetime import datetime
from functools import lru_cache
from math import ceil, floor

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QToolTip, QWidget

from artwork import asset_path


MONTHS = ("Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
          "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь")
RANK_NAMES = {
    "IRON": "Железо", "BRONZE": "Бронза", "SILVER": "Серебро", "GOLD": "Золото",
    "PLATINUM": "Платина", "EMERALD": "Изумруд", "DIAMOND": "Алмаз",
    "MASTER": "Мастер", "GRANDMASTER": "Грандмастер", "CHALLENGER": "Претендент",
}
TIERS = tuple(RANK_NAMES)
DIVISIONS = ("IV", "III", "II", "I")
ACCENT = QColor("#a996d0")
GRID = QColor("#2e2a39")
MUTED = QColor("#a8a0b4")
WEEKDAYS = ("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")
ACTIVITY_SCALE = (
    (0, "0", QColor("#2b2635")),
    (1, "1", QColor("#4d3e64")),
    (3, "2–3", QColor("#705789")),
    (6, "4–6", QColor("#9a7fba")),
    (float("inf"), "7+", QColor("#c4afe8")),
)


@lru_cache(maxsize=len(TIERS))
def rank_emblem(tier):
    return QPixmap(str(asset_path(f"ranks/{tier.lower()}.png"))) if tier in RANK_NAMES else QPixmap()


def score_tier(score):
    return TIERS[min(score // 400, 7)]


def rank_scale(score):
    division = max(0, round(score / 100))
    if division >= 28:
        return f"Мастер+ {max(0, int(score) - 2800)} LP"
    return f"{RANK_NAMES[TIERS[division // 4]]} {DIVISIONS[division % 4]}"


class Chart(QWidget):
    def __init__(self, title):
        super().__init__()
        self.setAccessibleName(title)
        self.setMinimumHeight(138)
        self.setMouseTracking(True)

    def painter(self):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        font = QFont(self.font())
        font.setPixelSize(12)
        painter.setFont(font)
        return painter

    def empty(self, painter, message):
        painter.setPen(MUTED)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, message)


class RankChart(Chart):
    def __init__(self):
        super().__init__("Изменение ранга")
        self.points = ()
        self.period = ()
        self.marks = []
        self.current_tier = None
        self.current_rank = ""

    def set_data(self, points, period, rank):
        self.points, self.period = points, period
        self.current_tier = rank.get("tier") if rank.get("state") == "ranked" else None
        name = RANK_NAMES.get(self.current_tier, "")
        self.current_rank = " ".join(filter(None, (name, rank.get("div")))) if name else ""
        if name and type(rank.get("lp")) is int:
            self.current_rank += f" · {rank['lp']} LP"
        description = f"Сохранённых замеров: {len(points)}"
        if self.current_rank:
            description = f"Текущий ранг: {self.current_rank}. {description}"
        self.setAccessibleDescription(description)
        self.update()

    def paintEvent(self, _event):
        painter = self.painter()
        self.marks = []
        if not self.points or len(self.period) != 2 or self.period[0] >= self.period[1]:
            self.empty(painter, "Пока нет сохранённых замеров ранга")
            return
        low = max(0, floor(min(lp for _, lp in self.points) / 100) * 100)
        high = max(low + 100, ceil(max(lp for _, lp in self.points) / 100) * 100)
        if high - low < 200 and low >= 100:
            low -= 100

        middle = (low + high) // 200 * 100
        ticks = {score: rank_scale(score) for score in (high, middle, low)}
        left = 36 + max(painter.fontMetrics().horizontalAdvance(title) for title in ticks.values())
        plot = QRectF(left, 17, max(1, self.width() - left - 24), self.height() - 48)
        for score, title in ticks.items():
            y = plot.bottom() - (score - low) / (high - low) * plot.height()
            painter.setPen(GRID)
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            painter.setPen(MUTED)
            self.draw_emblem(painter, QPointF(11, y), 22, score_tier(score))
            painter.drawText(QRectF(27, y - 8, left - 34, 16), Qt.AlignmentFlag.AlignVCenter, title)

        start, end = self.period
        painter.setPen(MUTED)
        for fraction in (0, 0.25, 0.5, 0.75, 1):
            stamp = start + fraction * (end - start)
            name = datetime.fromtimestamp(stamp / 1000).strftime("%d.%m")
            x = plot.left() + fraction * plot.width()
            painter.drawText(QRectF(x - 20, plot.bottom() + 6, 40, 18), Qt.AlignmentFlag.AlignCenter, name)

        self.marks = [(QPointF(plot.left() + (stamp - start) / (end - start) * plot.width(),
                               plot.bottom() - (lp - low) / (high - low) * plot.height()), stamp, lp)
                      for stamp, lp in self.points]
        line = QPainterPath(self.marks[0][0])
        for point, _, _ in self.marks[1:]:
            line.lineTo(point)
        area = QPainterPath(line)
        area.lineTo(self.marks[-1][0].x(), plot.bottom())
        area.lineTo(self.marks[0][0].x(), plot.bottom())
        area.closeSubpath()
        tint = QLinearGradient(plot.topLeft(), plot.bottomLeft())
        tint.setColorAt(0, QColor(151, 124, 198, 98))
        tint.setColorAt(1, QColor(151, 124, 198, 8))
        painter.fillPath(area, tint)
        painter.setPen(QPen(ACCENT, 2.2))
        painter.drawPath(line)
        if self.current_tier:
            self.draw_emblem(painter, self.marks[-1][0], 34, self.current_tier)

    @staticmethod
    def draw_emblem(painter, center, size, tier):
        pixmap = rank_emblem(tier)
        if not pixmap.isNull():
            bounds = QRectF(center.x() - size / 2, center.y() - size / 2, size, size)
            painter.drawPixmap(bounds, pixmap, QRectF(pixmap.rect()))

    def mouseMoveEvent(self, event):
        if not self.marks:
            return
        pos = event.position()
        point, stamp, lp = min(self.marks, key=lambda mark: (mark[0] - pos).manhattanLength())
        current = (point, stamp, lp) == self.marks[-1] and self.current_rank
        if (point - pos).manhattanLength() <= (23 if current else 18):
            when = datetime.fromtimestamp(stamp / 1000).strftime("%d.%m, %H:%M")
            rank = rank_scale(lp // 100 * 100) + f" · {lp % 100} LP" if lp < 2800 else rank_scale(lp)
            text = f"Текущий ранг · {self.current_rank}" if current else f"{when} · {rank}"
            QToolTip.showText(event.globalPosition().toPoint(), text, self)


class MonthChart(Chart):
    def __init__(self):
        super().__init__("Матчи по дням месяца")
        self.setMinimumHeight(156)
        self.month = {}
        self.cells = {}
        self.selected_day = None

    def set_data(self, month):
        if (month.get("year"), month.get("month")) != (self.month.get("year"), self.month.get("month")):
            self.selected_day = None
        self.month = month
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus if month.get("available") else Qt.FocusPolicy.NoFocus)
        self.describe_selection()
        self.update()

    def paintEvent(self, _event):
        painter = self.painter()
        self.cells = {}
        if not self.month:
            self.empty(painter, "История матчей пока недоступна")
            return
        weekday, days = monthrange(self.month["year"], self.month["month"])
        weeks = (weekday + days + 6) // 7
        cell = min(19, (self.height() - 23 - 6 * 3) / 7)
        step = cell + 3
        grid_width = weeks * step - 3
        legend_width = 144
        x = max(28, (self.width() - (28 + grid_width + 26 + legend_width)) / 2 + 28)
        y = 21

        painter.setPen(MUTED)
        for index, name in enumerate(WEEKDAYS):
            painter.drawText(QRectF(x - 27, y + index * step, 22, cell),
                             Qt.AlignmentFlag.AlignVCenter, name)
        for week in range(weeks):
            first = max(1, week * 7 - weekday + 1)
            painter.drawText(QRectF(x + week * step - 2, 0, cell + 4, 16),
                             Qt.AlignmentFlag.AlignCenter, str(first))

        for day in range(1, days + 1):
            week, row = divmod(weekday + day - 1, 7)
            bounds = QRectF(x + week * step, y + row * step, cell, cell)
            self.cells[day] = bounds
            count = self.day_count(day)
            painter.setBrush(self.color(count))
            if day == self.month["today"] or self.hasFocus() and day == self.selected_day:
                painter.setPen(QPen(QColor("#d8c5ee"), 1.5))
            elif count is None:
                painter.setPen(QPen(GRID))
            else:
                painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(bounds, 3, 3)

        self.draw_legend(painter, x + grid_width + 26, legend_width)

    def draw_legend(self, painter, x, width):
        y = (self.height() - 56) / 2
        painter.setPen(MUTED)
        painter.drawText(QRectF(x, y, width, 17), Qt.AlignmentFlag.AlignCenter, "Матчей за день")
        step = width / len(ACTIVITY_SCALE)
        for index, (_, title, color) in enumerate(ACTIVITY_SCALE):
            left = x + index * step
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRectF(left + (step - 14) / 2, y + 22, 14, 14), 3, 3)
            painter.setPen(MUTED)
            painter.drawText(QRectF(left, y + 39, step, 16), Qt.AlignmentFlag.AlignCenter, title)

    @staticmethod
    def color(count):
        if count is None:
            return QColor("#18171f")
        return next(color for maximum, _, color in ACTIVITY_SCALE if count <= maximum)

    def day_count(self, day):
        if self.month.get("available") and self.month.get("firstKnownDay", 1) <= day <= self.month["today"]:
            return self.month["days"].get(day, 0)
        return None

    def day_text(self, day):
        count = self.day_count(day)
        value = f"Матчей: {count}" if count is not None else "Будущий день" if day > self.month["today"] else "Нет данных"
        return f"{day:02}.{self.month['month']:02} · {value}"

    def describe_selection(self):
        total = sum(self.month.get("days", {}).values())
        description = f"Матчей в доступной истории: {total}" if self.month.get("available") else "История недоступна"
        if self.selected_day is not None:
            description = f"{description}. {self.day_text(self.selected_day)}"
        self.setAccessibleDescription(description)

    def mouseMoveEvent(self, event):
        day = next((day for day, bounds in self.cells.items() if bounds.contains(event.position())), None)
        if day is not None:
            QToolTip.showText(event.globalPosition().toPoint(), self.day_text(day), self)
        else:
            QToolTip.hideText()

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.selected_day = self.selected_day or self.month.get("today")
        self.describe_selection()
        self.update()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        QToolTip.hideText()
        self.update()

    def keyPressEvent(self, event):
        offsets = {Qt.Key.Key_Left: -7, Qt.Key.Key_Right: 7, Qt.Key.Key_Up: -1, Qt.Key.Key_Down: 1}
        offset = offsets.get(event.key())
        if offset is None or not self.cells or self.selected_day is None:
            super().keyPressEvent(event)
            return
        self.selected_day = max(1, min(max(self.cells), self.selected_day + offset))
        self.describe_selection()
        position = self.mapToGlobal(self.cells[self.selected_day].bottomRight().toPoint())
        QToolTip.showText(position, self.day_text(self.selected_day), self)
        self.update()
