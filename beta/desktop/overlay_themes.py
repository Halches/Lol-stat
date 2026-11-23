"""Shared materials, type and sizing for match overlays."""
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import sys

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QWidget


@dataclass(frozen=True)
class Theme:
    name: str
    base: str
    light: str
    shadow: str
    textures: tuple[str, ...]
    cut: bool = False


THEMES = {
    "circuit": Theme("Неоновая сетка", "#140e1c", "#d968ed", "#ffba69", ("circuit",), True),
    "void": Theme("Бездна", "#110e1b", "#be9aff", "#7650cc", ("void",), True),
    "crystal": Theme("Аметист", "#19112a", "#d2a1ff", "#844bdb", ("crystal",), True),
    "hex": Theme("Гексагон", "#0d1425", "#82bcff", "#a66ce8", ("hex",), True),
    "mist": Theme("Лиловый дым", "#1b1125", "#d9afff", "#a568d1", ("mist",)),
    "carmine": Theme("Кармин", "#21121d", "#ff99bd", "#c24a7f", ("carmine",)),
    "hex_crystal": Theme("Аметист × Гексагон", "#121327", "#c4a2ff", "#6ca7ff", ("hex", "crystal"), True),
    "void_carmine": Theme("Бездна × Кармин", "#1b1022", "#ef9cdb", "#8964e2", ("void", "carmine"), True),
}
DEFAULT_THEME = "crystal"
FOREGROUND = QColor("#fcf8ff")
MUTED = QColor("#d4ccdf")
GOOD = QColor("#8bf5b9")
BAD = QColor("#ff9ca9")
GOLD = QColor("#ffda86")
MIN_SCALE, MAX_SCALE = 80, 140


def asset_folder(name):
    root = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).resolve().parent / "assets"
    return root / name


def hud_font(size, weight=QFont.Weight.DemiBold):
    font = QFont("Segoe UI")
    font.setPixelSize(round(size))
    font.setWeight(weight)
    return font


def alpha(color, opacity):
    color = QColor(color)
    color.setAlpha(opacity)
    return color


@lru_cache(maxsize=len(THEMES))
def texture(name):
    return QPixmap(str(asset_folder("overlay-themes") / f"{name}.jpg"))


def cover(painter, rect, pixmap, opacity):
    if pixmap.isNull():
        return
    ratio = max(rect.width() / pixmap.width(), rect.height() / pixmap.height())
    source_w = rect.width() / ratio
    source_h = rect.height() / ratio
    source = QRectF((pixmap.width() - source_w) / 2, (pixmap.height() - source_h) * .25, source_w, source_h)
    painter.setOpacity(opacity)
    painter.drawPixmap(rect, pixmap, source)
    painter.setOpacity(1)


def draw_panel(painter, rect, theme):
    inside = rect.adjusted(.5, .5, -.5, -.5)
    if inside.isEmpty():
        return
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    shape = QPainterPath()
    corner = min(8, inside.height() / 3)
    if theme.cut:
        shape.moveTo(inside.left() + corner, inside.top())
        shape.lineTo(inside.right(), inside.top())
        shape.lineTo(inside.right(), inside.bottom() - corner)
        shape.lineTo(inside.right() - corner, inside.bottom())
        shape.lineTo(inside.left(), inside.bottom())
        shape.lineTo(inside.left(), inside.top() + corner)
        shape.closeSubpath()
    else:
        shape.addRoundedRect(inside, corner, corner)
    fill = QLinearGradient(inside.topLeft(), inside.bottomRight())
    fill.setColorAt(0, alpha(theme.base, 224))
    fill.setColorAt(1, alpha("#080912", 212))
    painter.fillPath(shape, fill)
    painter.setClipPath(shape)
    for index, name in enumerate(theme.textures):
        cover(painter, inside, texture(name), .28 if index == 0 else .18)
    painter.setClipping(False)
    rim = QLinearGradient(inside.topLeft(), inside.bottomRight())
    rim.setColorAt(0, alpha(theme.light, 245))
    rim.setColorAt(.48, alpha(theme.light, 101))
    rim.setColorAt(1, alpha(theme.shadow, 205))
    painter.setPen(QPen(rim, 1))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(shape)
    painter.setPen(QPen(alpha(theme.light, 236), 2))
    painter.drawLine(QPointF(inside.left() + corner + 2, inside.top() + 1),
                     QPointF(inside.left() + min(inside.width() - 2, corner + 27), inside.top() + 1))
    painter.restore()


class ThemePanel(QWidget):
    def __init__(self):
        super().__init__()
        self.theme = THEMES[DEFAULT_THEME]

    def set_theme(self, theme):
        self.theme = theme
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        draw_panel(painter, QRectF(self.rect()), self.theme)
