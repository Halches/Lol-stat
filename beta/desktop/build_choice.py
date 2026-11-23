"""Visual entries for alternate builds and exact matchups."""

import sys
from pathlib import Path

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication, QComboBox, QStyle, QStyleOptionComboBox, QStyleOptionViewItem,
    QStylePainter, QStyledItemDelegate,
)

from worker import DDRAGON


class BuildChoiceDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        styled = QStyleOptionViewItem(option)
        self.initStyleOption(styled, index)
        styled.text = ""
        style = styled.widget.style() if styled.widget else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, styled, painter, styled.widget)
        selected = styled.state & QStyle.StateFlag.State_Selected
        pen = styled.palette.highlightedText().color() if selected else styled.palette.text().color()
        self.parent().draw_entry(painter, styled.rect.adjusted(8, 0, -8, 0), index.row(), pen)

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        size.setHeight(max(28, size.height()))
        return size


class BuildChoice(QComboBox):
    def __init__(self, artwork, placeholder):
        super().__init__()
        self.artwork = artwork
        self.entries = []
        self.emblems = {}
        self.setProperty("role", "buildChoice")
        self.setProperty("chosen", False)
        self.setPlaceholderText(placeholder)
        self.setItemDelegate(BuildChoiceDelegate(self))
        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.view().setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        artwork.changed.connect(self.refresh_images)

    def populate(self, options):
        entries = [(key, build["title"], build.get("opponentName"), build.get("opponent"),
                    build.get("assetVersion"), build.get("proRank"), build.get("winRate"), build.get("sample"),
                    tuple(item["id"] for item in build.get("items", [])), build["source"]) for key, build in options.items()]
        if entries == self.entries:
            return
        self.entries = entries
        self.clear()
        for key, title, _opponent, champion, version, rank, rate, sample, items, source in entries:
            rank = rank if key.startswith("pro:") else None
            label = f"{rank['label']} · {title}" if rank else title
            self.addItem(label, key)
            detail = source
            if key == "matchup" and champion and version:
                self.opponent_image(champion, version)
            if key.startswith("otp:"):
                for item in items:
                    self.item_image(item, version)
                detail = f"{self.rate_text(rate)} побед · игр: {sample}\n{source}"
            if rank:
                rating = f"{rank['label']} · {rank['lp']} LP" if rank.get("lp") is not None else rank["label"]
                detail = f"{rating} · Solo/Duo EUW\n{source}"
            self.setItemData(self.count() - 1, detail, Qt.ItemDataRole.ToolTipRole)

    def select_key(self, key):
        self.setCurrentIndex(self.findData(key))
        self.setToolTip(self.currentData(Qt.ItemDataRole.ToolTipRole) or "")
        chosen = self.currentIndex() >= 0
        if self.property("chosen") != chosen:
            self.setProperty("chosen", chosen)
            self.style().unpolish(self)
            self.style().polish(self)
        self.update()

    def refresh_images(self):
        self.update()
        if self.view().isVisible():
            self.view().viewport().update()

    def opponent_image(self, champion, version):
        return self.artwork.image(f"{DDRAGON}/cdn/{version}/img/champion/{champion}.png")

    def item_image(self, item, version):
        return self.artwork.image(f"{DDRAGON}/cdn/{version}/img/item/{item}.png")

    def emblem(self, tier):
        if tier not in self.emblems:
            folder = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).resolve().parent / "assets"
            self.emblems[tier] = QPixmap(str(folder / "ranks" / f"{tier.lower()}.png"))
        return self.emblems[tier]

    @staticmethod
    def rate_text(rate):
        return f"{rate:.1f}%".replace(".", ",") if rate is not None else ""

    def showPopup(self):
        view = self.view()
        height = sum(view.sizeHintForRow(row) for row in range(self.count()))
        view.setMinimumHeight(height + 2 * view.frameWidth())
        super().showPopup()

    def draw_entry(self, painter, rect, row, color):
        key, title, opponent, champion, version, rank, rate, sample, items, _source = self.entries[row]
        painter.save()
        painter.setClipRect(rect)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        metrics = painter.fontMetrics()
        if key == "matchup" and opponent:
            badge = QRect(rect.left(), rect.center().y() - 8, 21, 17)
            self.draw_badge(painter, badge, "VS", "#392b51", "#eadcff")
            rect.setLeft(badge.right() + 7)
            title = metrics.elidedText(opponent, Qt.TextElideMode.ElideRight, max(0, rect.width() - 26))
            x = rect.left() + metrics.horizontalAdvance(title) + 6
            if champion and version:
                art = self.opponent_image(champion, version)
                if not art.isNull():
                    painter.drawPixmap(QRect(x, rect.center().y() - 10, 20, 20), art)
        elif key.startswith("pro:") and rank and rank.get("tier"):
            art = self.emblem(rank["tier"])
            if not art.isNull():
                size = art.size().scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio)
                mark = QRect(rect.left(), rect.center().y() - size.height() // 2, size.width(), size.height())
                painter.drawPixmap(mark, art)
                rect.setLeft(mark.right() + 7)
        elif key.startswith("otp:"):
            win = f"{self.rate_text(rate)} · игр: {sample}" if rect.width() >= 240 else self.rate_text(rate)
            painter.setPen(color)
            painter.drawText(rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, win)
            rect.setRight(rect.right() - metrics.horizontalAdvance(win) - 8)
            if rect.width() >= 160:
                x = rect.right() - 22 * len(items) + 2
                for item in items:
                    art = self.item_image(item, version)
                    if not art.isNull():
                        painter.drawPixmap(QRect(x, rect.center().y() - 9, 18, 18), art)
                    x += 22
                rect.setRight(rect.right() - 22 * len(items) - 5)
        if key != "matchup" or not opponent:
            title = metrics.elidedText(title, Qt.TextElideMode.ElideRight, max(0, rect.width()))
        painter.setPen(color)
        painter.drawText(rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, title)
        painter.restore()

    @staticmethod
    def draw_badge(painter, rect, text, background, foreground):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(background))
        painter.drawRoundedRect(rect, 4, 4)
        font = painter.font()
        font.setPixelSize(10)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(foreground))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()

    def paintEvent(self, event):
        row = self.currentIndex()
        if not 0 <= row < len(self.entries):
            super().paintEvent(event)
            return
        painter = QStylePainter(self)
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        painter.drawComplexControl(QStyle.ComplexControl.CC_ComboBox, option)
        content = self.style().subControlRect(QStyle.ComplexControl.CC_ComboBox, option,
                                              QStyle.SubControl.SC_ComboBoxEditField, self)
        self.draw_entry(painter, content.adjusted(2, 0, -2, 0), row, option.palette.text().color())
