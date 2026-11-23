"""Data Dragon images and the desktop draft header."""

import json
import sys
from collections import OrderedDict
from pathlib import Path

from PySide6.QtCore import QRectF, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import QWidget


def asset_path(name):
    assets = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).resolve().parent / "assets"
    return assets / name


def loadout_catalog():
    if getattr(sys, "frozen", False):
        path = Path(sys._MEIPASS) / "loadout.json"
    else:
        path = Path(__file__).resolve().parents[1] / "web/loadout.json"
    with path.open(encoding="utf-8") as file:
        return json.load(file)


class Artwork(QNetworkAccessManager):
    changed = Signal()

    def __init__(self, parent):
        super().__init__(parent)
        self.images = OrderedDict()
        self.pending = {}
        self.finished.connect(self.store)
        self.refresh = QTimer(self)
        self.refresh.setSingleShot(True)
        self.refresh.timeout.connect(self.changed.emit)

    def image(self, url):
        if not url:
            return QPixmap()
        if url in self.images:
            self.images.move_to_end(url)
            return self.images[url]
        if url not in self.pending:
            request = QNetworkRequest(QUrl(url))
            request.setTransferTimeout(6000)
            self.pending[url] = self.get(request)
        return QPixmap()

    def store(self, reply):
        key = reply.request().url().toString()
        self.pending.pop(key, None)
        image = QPixmap()
        if reply.error() == QNetworkReply.NetworkError.NoError:
            image.loadFromData(bytes(reply.readAll()))
            if image.width() > 720:
                image = image.scaledToWidth(720, Qt.TransformationMode.SmoothTransformation)
        reply.deleteLater()
        self.images[key] = image
        # A full draft can use 60 portraits before the build icons are loaded.
        if len(self.images) > 128:
            self.images.popitem(last=False)
        if not image.isNull() and not self.refresh.isActive():
            self.refresh.start(0)


class DraftHero(QWidget):
    def __init__(self):
        super().__init__()
        self.art = QPixmap()
        self.setMinimumHeight(146)

    def set_art(self, art):
        if art.cacheKey() != self.art.cacheKey():
            self.art = art
            self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        bounds = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        contour = QPainterPath()
        contour.addRoundedRect(bounds, 15, 15)
        painter.setClipPath(contour)
        background = QLinearGradient(bounds.topLeft(), bounds.bottomRight())
        background.setColorAt(0, QColor("#211b34"))
        background.setColorAt(1, QColor("#151522"))
        painter.fillRect(bounds, background)

        if not self.art.isNull():
            target = QRectF(bounds.width() * 0.29, 0, bounds.width() * 0.71, bounds.height())
            ratio = max(target.width() / self.art.width(), target.height() / self.art.height())
            width, height = target.width() / ratio, target.height() / ratio
            source = QRectF((self.art.width() - width) * 0.55,
                            (self.art.height() - height) * 0.34, width, height)
            painter.drawPixmap(target, self.art, source)
            fade = QLinearGradient(bounds.left(), 0, bounds.right(), 0)
            fade.setColorAt(0, QColor("#211b34"))
            fade.setColorAt(0.31, QColor("#211b34"))
            fade.setColorAt(0.58, QColor(25, 21, 38, 217))
            fade.setColorAt(1, QColor(16, 14, 28, 42))
            painter.fillRect(bounds, fade)

        painter.setClipping(False)
        painter.setPen(QPen(QColor("#4b3c66")))
        painter.drawPath(contour)
