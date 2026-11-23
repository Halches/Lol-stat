"""Team roster and sidebar for ranked champion select."""

import sys
from pathlib import Path

from PySide6.QtCore import QPoint, QRectF, QSize, QSignalBlocker, Qt
from PySide6.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QBoxLayout, QComboBox, QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea, QSizePolicy,
    QStyle, QStyleOptionComboBox, QStylePainter, QVBoxLayout, QWidget,
)

from widgets import button, icon_label, label, panel
from worker import DDRAGON, ROLES, SUGGESTION_LIMIT, allied_role_slots


ALLIES = "#aa98e3"
ENEMIES = "#dc8e9d"
DAMAGE_COLORS = ("#e4a47f", ALLIES, "#b0d2c5")
SIDES = (("allies", "Союзники", ALLIES), ("enemies", "Противники", ENEMIES))
ROLE_ASSETS = (Path(sys._MEIPASS) if getattr(sys, "frozen", False)
               else Path(__file__).resolve().parent / "assets") / "roles"


class ElidedLabel(QLabel):
    def __init__(self, role, center=False):
        super().__init__()
        self.full_text = ""
        self.setProperty("role", role)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        if center:
            self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def setText(self, text):
        self.full_text = text
        self.setAccessibleName(text)
        super().setText(self.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, self.contentsRect().width()))

    def resizeEvent(self, event):
        self.setText(self.full_text)
        super().resizeEvent(event)


class DraftRolePicker(QComboBox):
    def __init__(self, icons):
        super().__init__()
        self.icons = icons
        self.display_role = None
        self.setProperty("role", "draftRoleIcon")
        self.setProperty("manual", False)
        self.setFixedSize(30, 30)
        self.setIconSize(QSize(20, 20))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.addItem("Авто", "auto")
        for role, title in ROLES.items():
            self.addItem(icons.get(role, QIcon()), title, role)
        self.setMaxVisibleItems(self.count())
        self.view().setMinimumWidth(132)
        self.view().setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def sync_role(self, role, manual):
        self.display_role = role
        with QSignalBlocker(self):
            self.setCurrentIndex(self.findData(manual or "auto"))
        is_manual = bool(manual)
        if self.property("manual") != is_manual:
            self.setProperty("manual", is_manual)
            self.style().unpolish(self)
            self.style().polish(self)
        self.update()

    def wheelEvent(self, event):
        event.ignore()

    def showPopup(self):
        view = self.view()
        height = sum(view.sizeHintForRow(index) for index in range(self.count()))
        view.setMinimumHeight(height + 2 * view.frameWidth())
        super().showPopup()

    def paintEvent(self, _event):
        painter = QStylePainter(self)
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        painter.drawComplexControl(QStyle.ComplexControl.CC_ComboBox, option)
        icon = self.icons.get(self.display_role)
        if icon and not icon.isNull():
            icon.paint(painter, self.rect().adjusted(5, 5, -5, -5))
        else:
            painter.setPen(QColor("#dac9ea"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "?")


def set_tag(chip, text, tone, detail):
    if chip.property("tone") != tone:
        chip.setProperty("tone", tone)
        chip.style().unpolish(chip)
        chip.style().polish(chip)
    chip.setText(text)
    chip.setToolTip(detail)


def whole(value):
    return f"{value:,.0f}".replace(",", " ")


class CommentPopup(QDialog):
    def __init__(self, parent, tags, heading="Все комментарии"):
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setObjectName("draftCommentPopup")
        self.setAccessibleName(heading)
        self.setFixedWidth(parent.width())
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        title = label(heading, "draftTeam", wrap=True)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        self.scroll = QScrollArea()
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        body = QWidget()
        body.setObjectName("draftCommentRows")
        rows = QVBoxLayout(body)
        rows.setContentsMargins(0, 0, 0, 0)
        rows.setSpacing(9)
        for tag in tags:
            row = QVBoxLayout()
            row.setSpacing(1)
            heading = label("", "draftCommentHeading", wrap=True)
            set_tag(heading, tag["label"], tag["tone"], tag["detail"])
            heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
            row.addWidget(heading)
            detail = label(tag["detail"], "draftCommentDetail", wrap=True)
            detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
            row.addWidget(detail)
            rows.addLayout(row)
        rows.addStretch()
        self.scroll.setWidget(body)
        margins = layout.contentsMargins()
        content_width = self.width() - margins.left() - margins.right()
        list_height = rows.heightForWidth(content_width)
        if list_height > 248:
            # Balance the right-side scrollbar so the text stays centered in the frame.
            scrollbar_width = self.scroll.verticalScrollBar().sizeHint().width()
            rows.setContentsMargins(scrollbar_width, 0, 0, 0)
        self.scroll.setFixedHeight(min(248, list_height))
        layout.addWidget(self.scroll)

    def show_anchored(self, anchor):
        self.adjustSize()
        gap = 5
        top = anchor.mapToGlobal(QPoint())
        screen = anchor.screen().availableGeometry()
        below = top.y() + anchor.height() + gap
        y = below if below + self.height() <= screen.bottom() + 1 else top.y() - self.height() - gap
        x = self.parentWidget().mapToGlobal(QPoint()).x()
        self.move(min(max(x, screen.left()), screen.right() + 1 - self.width()), max(screen.top(), y))
        self.show()
        self.scroll.setFocus()


class DamageMix(QWidget):
    def __init__(self):
        super().__init__()
        self.values = []
        self.setFixedHeight(6)

    def set_values(self, values):
        if values != self.values:
            self.values = values
            self.update()

    def paintEvent(self, _event):
        total = sum(self.values)
        if not total:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        area = QRectF(self.rect())
        outline = QPainterPath()
        outline.addRoundedRect(area, 3, 3)
        painter.setClipPath(outline)
        start = 0
        for value, color in zip(self.values, DAMAGE_COLORS):
            width = area.width() * value / total
            painter.fillRect(QRectF(start, 0, width, area.height()), QColor(color))
            start += width


class ChampionCard(QWidget):
    def __init__(self, side, color, role_icons, set_role=None):
        super().__init__()
        self.side = side
        self.color = color
        self.set_role = set_role
        self.data = {}
        self.version = None
        self.art = QPixmap()
        self.comment_popup = None
        self.popup_anchor = None
        self.insight_entries = []
        self.setMinimumSize(116, 202)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)
        contents = QVBoxLayout()
        contents.setContentsMargins(9, 10, 9, 7)
        contents.setSpacing(3)
        layout.addLayout(contents, 1)
        self.mine = label("ВЫ", "draftBadge")
        self.mine.hide()
        self.role_icon = DraftRolePicker(role_icons)
        self.role_icon.currentIndexChanged.connect(self.choose_role)
        self.role_icon.hide()
        header = QHBoxLayout()
        header.addWidget(self.mine)
        header.addStretch()
        self.insight_button = button("ⓘ", self.show_insights, "draftDetailsButton")
        self.insight_button.setFixedSize(25, 25)
        self.insight_button.setToolTip("Доли урона и детали рекомендаций")
        self.insight_button.hide()
        header.addWidget(self.insight_button)
        header.addWidget(self.role_icon)
        contents.addLayout(header)
        contents.addStretch()
        self.name = label("", "draftChampion", wrap=True)
        self.name.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft)
        contents.addWidget(self.name)
        self.details = label("", "draftCardDetail", wrap=True)
        contents.addWidget(self.details)
        self.player_name = ElidedLabel("draftPlayerName")
        self.player_stats = ElidedLabel("draftCardDetail")
        self.player_name.hide()
        self.player_stats.hide()
        contents.addWidget(self.player_name)
        contents.addWidget(self.player_stats)
        self.options = QWidget()
        options = QVBoxLayout(self.options)
        options.setContentsMargins(0, 3, 0, 0)
        options.setSpacing(4)
        self.option_title = label("", "draftOptionTitle")
        options.addWidget(self.option_title)
        self.option_status = label("", "draftOptionName", wrap=True)
        options.addWidget(self.option_status)
        group = QHBoxLayout()
        group.setSpacing(2)
        self.option_icons = []
        self.suggestion_artwork = [None] * SUGGESTION_LIMIT
        for _ in range(SUGGESTION_LIMIT):
            cell = QWidget()
            column = QVBoxLayout(cell)
            column.setContentsMargins(0, 0, 0, 0)
            column.setSpacing(2)
            icon = icon_label(17, "draftSuggestionIcon")
            icon.setScaledContents(True)
            column.addWidget(icon, alignment=Qt.AlignmentFlag.AlignHCenter)
            name = ElidedLabel("draftOptionName", center=True)
            column.addWidget(name)
            group.addWidget(cell, 1)
            self.option_icons.append((cell, icon, name))
        options.addLayout(group)
        self.options.hide()
        contents.addWidget(self.options)
        self.damage_bar = DamageMix()
        self.damage_bar.hide()
        damage_row = QHBoxLayout()
        damage_row.setContentsMargins(8, 0, 8, 0)
        damage_row.addWidget(self.damage_bar)
        layout.addLayout(damage_row)
        self.comments = QWidget()
        self.comments.setFixedHeight(22)
        self.comments.hide()
        row = QHBoxLayout(self.comments)
        row.setContentsMargins(9, 1, 9, 2)
        row.setSpacing(8)
        self.comment_labels = [ElidedLabel("draftPlayerComment") for _ in range(2)]
        for comment in self.comment_labels:
            comment.hide()
            row.addWidget(comment, 1)
        row.addStretch()
        self.more_comments = button("", self.show_comment_popup, "draftMoreComments")
        self.more_comments.setFixedHeight(18)
        self.more_comments.hide()
        row.addWidget(self.more_comments)
        layout.addWidget(self.comments)

    def update_card(self, data, artwork, version):
        if data != self.data or version != self.version or not self.name.text():
            if self.comment_popup:
                if self.popup_anchor is self.insight_button:
                    changed = data.get("insights") != self.data.get("insights")
                else:
                    changed = ((data.get("profile") or {}).get("tags")
                               != (self.data.get("profile") or {}).get("tags"))
                if changed or data.get("championKey") != self.data.get("championKey"):
                    self.close_comment_popup()
            self.data = data
            self.version = version
            name = data.get("name") or ("Пик скрыт" if self.side == "enemies" else "Ожидаем выбор")
            manual = data.get("manualRole")
            assigned = manual or data.get("effectiveRole") or data.get("role")
            role = ROLES.get(assigned)
            status = ("Выбран" if data.get("locked") else "Предвыбор") if data.get("name") else ""
            self.name.setText(name)
            self.details.setText(" · ".join(part for part in (role, status) if part))
            self.details.setVisible(bool(self.details.text()))
            self.mine.setVisible(bool(data.get("local")))
            inferred = (data.get("insights") or {}).get("role") if self.side == "enemies" else None
            self.role_icon.sync_role(assigned or inferred, manual)
            self.role_icon.setVisible(data.get("roleSlot") is not None)
            if manual:
                role_text = f"Роль вручную · {role}"
            elif data.get("effectiveRole"):
                role_text = f"Роль в составе · {role}"
            elif inferred:
                role_text = f"Типичная роль чемпиона · {ROLES[inferred]}"
            else:
                role_text = f"Роль · {role or 'ожидаем данные'}"
            self.role_icon.setToolTip(f"{role_text}\nНажмите, чтобы выбрать роль")
            self.role_icon.setAccessibleDescription(role_text)
            self.setAccessibleName(" · ".join(part for part in (name, role, status) if part))
            self.insight_button.setAccessibleName(f"Детали статистики · {name}")
            self.update_profile(data.get("profile"))
            self.update_insights(data.get("insights") or {})
            self.update()
        self.paint_artwork(artwork)

    def choose_role(self, index):
        role = self.role_icon.itemData(index)
        self.role_icon.sync_role(self.role_icon.display_role, self.data.get("manualRole"))
        if self.set_role is not None:
            self.set_role(self.side, self.data.get("roleSlot"), role)

    def update_profile(self, profile):
        self.player_name.setVisible(bool(profile and (profile.get("name") or profile.get("rank"))))
        self.player_stats.setVisible(bool(profile))
        tags = []
        if profile:
            name = profile.get("name") or ""
            rank = profile.get("rank") or ""
            headline = " · ".join(part for part in (name, rank) if part)
            self.player_name.setText(headline)
            self.player_name.setToolTip(headline)
            state = profile.get("status")
            if state == "ready":
                games, wins, kda = profile["n"], profile["w"], profile["kda"]
                stats = f"{wins}/{games} побед  ·  KDA {kda:.1f}".replace(".", ",")
                detail = f"Недавние матчи Solo/Duo · {wins} побед из {games}. KDA — по выборке на пике или по всем играм."
                if profile["on"]:
                    detail += f" На чемпионе побед {profile['on_w']} из {profile['on']}."
                tags = profile["tags"]
            else:
                stats = {"loading": "Загружаем историю…", "unavailable": "История недоступна",
                         "insufficient": "Нет недавних игр Solo/Duo"}.get(state, "")
                detail = stats
            self.player_stats.setText(stats)
            self.player_stats.setToolTip(detail)
        for index, comment in enumerate(self.comment_labels):
            comment.setVisible(index < len(tags))
            if index < len(tags):
                tag = tags[index]
                set_tag(comment, tag["label"], tag["tone"], tag["detail"])
                comment.setMaximumWidth(comment.fontMetrics().horizontalAdvance(tag["label"]) + 2)
        extra = len(tags) - len(self.comment_labels)
        self.more_comments.setVisible(extra > 0)
        if extra > 0:
            self.more_comments.setText(f"+{extra}")
            self.more_comments.setToolTip(f"Показать все комментарии ({len(tags)})")

    def show_comment_popup(self):
        tags = (self.data.get("profile") or {}).get("tags") or []
        if not self.more_comments.isVisible() or len(tags) <= len(self.comment_labels):
            return
        self.close_comment_popup()
        self.comment_popup = CommentPopup(self, tags)
        self.popup_anchor = self.more_comments
        self.comment_popup.show_anchored(self.more_comments)

    def show_insights(self):
        if self.insight_entries:
            self.close_comment_popup()
            self.comment_popup = CommentPopup(self, self.insight_entries, "Детали статистики")
            self.popup_anchor = self.insight_button
            self.comment_popup.show_anchored(self.insight_button)

    def close_comment_popup(self):
        if self.comment_popup is not None:
            self.comment_popup.close()
            self.comment_popup.deleteLater()
            self.comment_popup = None
            self.popup_anchor = None

    def hideEvent(self, event):
        self.close_comment_popup()
        super().hideEvent(event)

    def resizeEvent(self, event):
        if event.size().width() != event.oldSize().width():
            self.close_comment_popup()
        size = min(26, max(17, (event.size().width() - 28) // SUGGESTION_LIMIT))
        for _, icon, _ in self.option_icons:
            if icon.width() != size:
                icon.setFixedSize(size, size)
        super().resizeEvent(event)

    def update_insights(self, insights):
        visible = bool(insights)
        values = insights.get("damage") or []
        self.insight_entries = []
        self.damage_bar.setVisible(bool(values))
        self.damage_bar.set_values(values)
        if values:
            total = sum(values)
            split = "\n".join(f"{kind} · {value / total:.0%}"
                              for kind, value in zip(("Физический", "Магический", "Чистый"), values))
            role = ROLES.get(insights.get("role")) or ""
            damage_detail = f"{split}\nLolalytics · EUW · Изумруд+ · {role}"
            self.damage_bar.setToolTip(f"Доли урона\n{damage_detail}")
            self.insight_entries.append({"label": "Доли урона", "tone": "neutral", "detail": damage_detail})

        options = insights.get("suggestions") or []
        self.options.setVisible(visible)
        enemy = self.side == "enemies"
        title = "Контрпики" if enemy else "Синергия"
        role = ROLES.get(insights.get("role") if enemy else insights.get("partnerRole"))
        self.option_title.setText(f"{title} · {role}" if role else title)
        tip = "Контрпики для типичной роли чемпиона в выборке Lolalytics" if enemy else "Пары чемпионов с положительным отклонением от ожидаемого винрейта"
        self.option_title.setToolTip(tip)
        self.option_status.setVisible(not options)
        self.option_status.setText({"loading": "Загружаем…", "unavailable": "Источник недоступен"}.get(
            insights.get("status"), "Нет подтверждённых вариантов"))
        for index, (cell, icon, name) in enumerate(self.option_icons):
            cell.setVisible(index < len(options))
            if index < len(options):
                choice = options[index]
                name.setText(choice["name"])
                role_text = ROLES.get(choice["role"], "")
                stats = f"{choice['winRate']:.1f}% побед · {whole(choice['games'])} игр".replace(".", ",")
                edge = f"+{choice['edge']:.1f}".replace(".", ",")
                choice_detail = f"{role_text}\n{stats}\n{edge} п.п. к ожидаемому винрейту\nLolalytics · EUW · Изумруд+"
                description = f"{choice['name']} · {choice_detail}"
                cell.setToolTip(description)
                icon.setToolTip(description)
                name.setToolTip(description)
                cell.setAccessibleName(description)
                self.insight_entries.append({"label": f"{title} · {choice['name']}", "tone": "neutral", "detail": choice_detail})
        self.insight_button.setVisible(bool(self.insight_entries))

    def paint_artwork(self, artwork):
        champion = self.data.get("championKey")
        url = f"{DDRAGON}/cdn/img/champion/loading/{champion}_0.jpg" if champion else None
        art = artwork.image(url)
        if art.cacheKey() != self.art.cacheKey():
            self.art = art
            self.update()
        suggestions = (self.data.get("insights") or {}).get("suggestions", [])
        for index, (choice, (_, icon, _)) in enumerate(zip(suggestions, self.option_icons)):
            champion_key = choice["championKey"]
            url = f"{DDRAGON}/cdn/{self.version}/img/champion/{champion_key}.png" if self.version else None
            portrait = artwork.image(url)
            source = url, portrait.cacheKey(), choice["name"]
            if self.suggestion_artwork[index] == source:
                continue
            self.suggestion_artwork[index] = source
            if portrait.isNull():
                icon.setText(choice["name"][:1])
            else:
                # Trim the dark rim baked into Data Dragon champion portraits.
                inset_x, inset_y = portrait.width() // 25, portrait.height() // 25
                crop = portrait.rect().adjusted(inset_x, inset_y, -inset_x, -inset_y)
                icon.setPixmap(portrait.copy(crop).scaled(26, 26, Qt.AspectRatioMode.KeepAspectRatio,
                                                          Qt.TransformationMode.SmoothTransformation))

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        area = QRectF(self.rect()).adjusted(.5, .5, -.5, -.5)
        outline = QPainterPath()
        outline.addRoundedRect(area, 11, 11)
        painter.setClipPath(outline)
        fill = QLinearGradient(area.topLeft(), area.bottomRight())
        fill.setColorAt(0, QColor("#251e35" if self.side == "allies" else "#2e202a"))
        fill.setColorAt(1, QColor("#16141f"))
        painter.fillRect(area, fill)
        if not self.art.isNull():
            scale = max(area.width() / self.art.width(), area.height() / self.art.height())
            width, height = area.width() / scale, area.height() / scale
            crop = QRectF((self.art.width() - width) / 2, (self.art.height() - height) * .16, width, height)
            painter.drawPixmap(area, self.art, crop)
            portrait_shade = QLinearGradient(0, area.top(), 0, area.bottom())
            # Keep the middle clear and make the lower fade heavier behind the stats.
            for position, alpha in ((0, 210), (.11, 125), (.26, 44), (.45, 0), (.52, 0),
                                    (.62, 105), (.75, 196), (.87, 235), (1, 255)):
                portrait_shade.setColorAt(position, QColor(0, 0, 0, alpha))
            painter.fillRect(area, portrait_shade)
        painter.setClipping(False)
        stroke = self.color if self.data.get("local") else ("#514662" if self.side == "allies" else "#54404c")
        painter.setPen(QPen(QColor(stroke), 2 if self.data.get("local") else 1))
        painter.drawPath(outline)


class ShareBar(QWidget):
    def __init__(self, background, height=7):
        super().__init__()
        self.background = background
        self.height_px = height
        self.share = None
        self.setFixedHeight(height)

    def set_share(self, share):
        if share != self.share:
            self.share = share
            self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        area = QRectF(self.rect())
        contour = QPainterPath()
        contour.addRoundedRect(area, self.height_px / 2, self.height_px / 2)
        painter.setClipPath(contour)
        painter.fillRect(area, QColor("#2a2535" if self.share is None else self.background))
        if self.share is not None:
            painter.fillRect(QRectF(0, 0, area.width() * self.share, area.height()), QColor(ALLIES))


class DraftScreen(QWidget):
    SIDEBAR_WIDTH = 354

    def __init__(self, artwork, set_tab, set_role):
        super().__init__()
        self.artwork = artwork
        self.tab = "stats"
        self.roster = None
        self.cards = {}
        self.counts = {}
        self.damage = {}
        self.team_analysis = {}
        role_icons = {role: QIcon(str(ROLE_ASSETS / f"{role.lower()}.png")) for role in ROLES}
        self.columns = QBoxLayout(QBoxLayout.Direction.LeftToRight, self)
        self.columns.setContentsMargins(0, 0, 0, 0)
        self.columns.setSpacing(15)
        self.teams = QWidget()
        roster_layout = QVBoxLayout(self.teams)
        roster_layout.setContentsMargins(0, 0, 0, 0)
        roster_layout.setSpacing(10)
        heading = QHBoxLayout()
        heading.addWidget(label("Составы команд", "section"))
        heading.addStretch()
        self.timer = label("", "chip")
        heading.addWidget(self.timer)
        roster_layout.addLayout(heading)
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(7)
        for col in range(5):
            grid.setColumnStretch(col, 1)
        for heading_row, (side, title, color) in zip((0, 2), SIDES):
            heading = QHBoxLayout()
            heading.addWidget(label(title, "draftTeam"))
            heading.addStretch()
            self.counts[side] = label("", "caption")
            heading.addWidget(self.counts[side])
            grid.addLayout(heading, heading_row, 0, 1, 5)
            self.cards[side] = [ChampionCard(side, color, role_icons, set_role) for _ in range(5)]
            for col, card in enumerate(self.cards[side]):
                grid.addWidget(card, heading_row + 1, col)
            grid.setRowStretch(heading_row + 1, 1)
        roster_layout.addLayout(grid, 1)
        self.columns.addWidget(self.teams, 1)

        self.side, sidebar = panel("draftSide")
        self.side.setFixedWidth(self.SIDEBAR_WIDTH)
        sidebar.setContentsMargins(11, 11, 11, 11)
        sidebar.setSpacing(11)
        tabs = QHBoxLayout()
        self.stats_tab = button("Статистика", lambda: set_tab("stats"), "tab")
        self.build_tab = button("Сборка", lambda: set_tab("build"), "tab")
        for tab in (self.stats_tab, self.build_tab):
            tab.setCheckable(True)
            tabs.addWidget(tab, 1)
        sidebar.addLayout(tabs)
        self.stats_page = self.build_stats_page()
        sidebar.addWidget(self.stats_page)
        self.build_page = QWidget()
        self.build_layout = QVBoxLayout(self.build_page)
        self.build_layout.setContentsMargins(0, 0, 0, 0)
        self.build_layout.setSpacing(8)
        self.build_status = label("", "muted", wrap=True)
        self.build_layout.addWidget(self.build_status)
        sidebar.addWidget(self.build_page)
        self.notice_slot = QVBoxLayout()
        sidebar.addLayout(self.notice_slot)
        sidebar.addStretch()
        self.columns.addWidget(self.side)
        self.show_tab("stats", "")

    def build_stats_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        damage, content = panel()
        content.addWidget(label("Профиль урона", "section"))
        content.addWidget(label("Оценка по открытым пикам · Data Dragon", "caption", wrap=True))
        for side, title, _color in SIDES:
            content.addWidget(label(title, "captionStrong"))
            bar = ShareBar("#e4a47f")
            content.addWidget(bar)
            note = label("", "caption", wrap=True)
            content.addWidget(note)
            self.damage[side] = bar, note
        layout.addWidget(damage)

        analysis, content = panel()
        content.addWidget(label("Анализ команд", "section"))
        content.addWidget(label("Возможности открытых чемпионов", "caption", wrap=True))
        for side, title, _color in SIDES:
            heading = QHBoxLayout()
            heading.addWidget(label(title, "draftTeam"))
            heading.addStretch()
            count = label("", "caption")
            heading.addWidget(count)
            content.addLayout(heading)
            note = label("", "caption", wrap=True)
            content.addWidget(note)
            grid = QGridLayout()
            grid.setSpacing(5)
            grid.setColumnStretch(0, 1)
            grid.setColumnStretch(1, 1)
            chips = [ElidedLabel("draftTag") for _ in range(8)]
            for index, chip in enumerate(chips):
                chip.hide()
                grid.addWidget(chip, index // 2, index % 2)
            content.addLayout(grid)
            self.team_analysis[side] = count, note, chips
        layout.addWidget(analysis)
        return page

    def set_compact(self, compact):
        self.columns.setDirection(QBoxLayout.Direction.TopToBottom if compact else QBoxLayout.Direction.LeftToRight)
        if compact:
            self.side.setMinimumWidth(0)
            self.side.setMaximumWidth(16777215)
        else:
            self.side.setFixedWidth(self.SIDEBAR_WIDTH)

    def side_by_side_width(self):
        return self.teams.minimumSizeHint().width() + self.SIDEBAR_WIDTH + self.columns.spacing()

    def show_tab(self, tab, build_status):
        self.tab = tab
        self.stats_tab.setChecked(tab == "stats")
        self.build_tab.setChecked(tab == "build")
        self.stats_page.setVisible(tab == "stats")
        self.build_page.setVisible(tab == "build")
        self.build_status.setText(build_status)
        self.build_status.setVisible(bool(build_status))

    def update_roster(self, roster):
        if roster == self.roster:
            return
        self.roster = roster
        seconds = roster.get("seconds")
        self.timer.setVisible(seconds is not None)
        if seconds is not None:
            self.timer.setText(f"{seconds // 60:02}:{seconds % 60:02}")
        for side, _, _ in SIDES:
            members = roster.get(side) or []
            if side == "allies":
                members = allied_role_slots(members)
            show_comments = side == "allies" and any((member.get("profile") or {}).get("tags") for member in members)
            for index, card in enumerate(self.cards[side]):
                card.update_card(members[index] if index < len(members) else {}, self.artwork, roster.get("assetVersion"))
                card.comments.setVisible(show_comments)
            picked = sum(bool(member.get("locked")) for member in members)
            typical = side == "enemies" and any(
                (member.get("insights") or {}).get("role") and not member.get("manualRole") for member in members
            )
            self.counts[side].setText(("Типичные роли  ·  " if typical else "") + f"Пики {picked} / 5")
            profile = (roster.get("damage") or {}).get(side) or {}
            bar, note = self.damage[side]
            share = profile.get("ap")
            bar.set_share(share)
            if share is None:
                note.setText("Ожидаем открытые пики")
            else:
                magic = round(share * 100)
                note.setText(f"Магический {magic}%  ·  Физический {100 - magic}%")
            report = (roster.get("composition") or {}).get(side) or []
            count, state, chips = self.team_analysis[side]
            visible = profile.get("n", 0)
            count.setText(f"Учтено {visible}/5")
            state.setVisible(not report)
            state.setText("Ожидаем открытые пики" if not visible else "Пока нет меток по открытым пикам")
            for index, chip in enumerate(chips):
                chip.setVisible(index < len(report))
                if index < len(report):
                    tag = report[index]
                    champions = tag["champions"]
                    title = tag["label"]
                    if champions:
                        title += f" · {len(champions)}"
                    set_tag(chip, title, tag["tone"], tag.get("detail") or ", ".join(champions))

    def paint_artwork(self):
        if self.isVisible():
            for group in self.cards.values():
                for card in group:
                    card.paint_artwork(self.artwork)
