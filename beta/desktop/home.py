"""Qt profile dashboard and recent-match cards."""

from PySide6.QtCore import QDateTime, QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QBoxLayout, QComboBox, QGridLayout, QHBoxLayout, QVBoxLayout, QWidget

from artwork import asset_path
from dashboard_charts import MONTHS, RANK_NAMES, MonthChart, RankChart, rank_emblem
from widgets import button, icon_label, label, panel
from worker import DDRAGON
from connection import connection_view


QUEUE_NAMES = {420: "Solo/Duo", 440: "Flex", 400: "Обычная", 430: "Обычная", 450: "ARAM",
               480: "Быстрая игра", 490: "Быстрая игра", 1700: "Арена", 2400: "ARAM: Хаос"}
OVERVIEW_MATCHES = 3
HISTORY_PAGE = 12


def logo_path():
    return asset_path("lolhelper-logo.png")


def set_portrait(widget, image, fallback):
    if image.isNull():
        widget.setText(fallback)
    else:
        widget.setPixmap(image.scaled(widget.contentsRect().size(), Qt.AspectRatioMode.KeepAspectRatio,
                                      Qt.TransformationMode.SmoothTransformation))


def card(role="dashboardPanel"):
    frame, contents = panel(role)
    contents.setContentsMargins(19, 15, 19, 15)
    contents.setSpacing(9)
    return frame, contents


class ProfileCard(QWidget):
    def __init__(self, artwork):
        super().__init__()
        self.artwork = artwork
        self.image_url = ""
        self.initials = ""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        frame, contents = card("dashboardProfile")
        layout.addWidget(frame)
        contents.addWidget(label("Игровой профиль", "dashboardEyebrow"))
        contents.addStretch()
        identity = QHBoxLayout()
        identity.setSpacing(14)
        self.avatar = icon_label(64, "dashboardAvatar")
        self.avatar.setContentsMargins(2, 2, 2, 2)
        identity.addWidget(self.avatar)
        texts = QVBoxLayout()
        texts.setSpacing(3)
        self.name = label("", "dashboardProfileName", wrap=True)
        self.subline = label("", "dashboardMuted", wrap=True)
        texts.addWidget(self.name)
        texts.addWidget(self.subline)
        identity.addLayout(texts, 1)
        contents.addLayout(identity)
        contents.addStretch()
        artwork.changed.connect(self.paint_art)

    def populate(self, profile, patch):
        riot_id = profile.get("riot") or ""
        name, _, tag = riot_id.partition("#")
        level = profile.get("level")
        details = [part for part in (f"#{tag}" if tag else "", "EUW" if profile else "",
                                     f"Уровень {level}" if type(level) is int else "") if part]
        self.name.setText(name or ("Профиль загружается" if profile else "Ожидаем профиль"))
        self.subline.setText("  ·  ".join(details) if details else "Подключитесь к клиенту League of Legends")
        icon = profile.get("icon")
        self.image_url = f"{DDRAGON}/cdn/{patch}/img/profileicon/{icon}.png" if type(icon) is int and patch else ""
        self.initials = name[:2].upper() or "—"
        self.paint_art()

    def paint_art(self):
        set_portrait(self.avatar, self.artwork.image(self.image_url), self.initials)


class RankCard(QWidget):
    def __init__(self, title):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        frame, contents = card()
        layout.addWidget(frame)
        contents.addWidget(label(title, "dashboardEyebrow"))
        current = QHBoxLayout()
        current.setSpacing(9)
        self.emblem = icon_label(45, "")
        current.addWidget(self.emblem)
        self.rank = label("", "dashboardRankName", wrap=True)
        current.addWidget(self.rank, 1)
        self.lp = label("", "dashboardLP")
        current.addWidget(self.lp)
        contents.addLayout(current)
        divider = QWidget()
        divider.setProperty("role", "dashboardDivider")
        divider.setFixedHeight(1)
        contents.addWidget(divider)

        metrics = QHBoxLayout()
        self.metrics = []
        for period in ("За сезон", "За 7 дней"):
            column = QVBoxLayout()
            column.setSpacing(1)
            column.addWidget(label(period, "dashboardMuted"))
            percent = label("", "dashboardPercent")
            note = label("", "dashboardMuted", wrap=True)
            column.addWidget(percent)
            column.addWidget(note)
            self.metrics.append((percent, note))
            metrics.addLayout(column, 1)
        contents.addLayout(metrics)

    def populate(self, data, week):
        name = RANK_NAMES.get(data.get("tier"))
        self.rank.setText(" ".join(filter(None, (name, data.get("div")))) if name else
                          {"unranked": "Без ранга", "provisional": "Калибровка"}.get(data.get("state"), "Ранг недоступен"))
        self.emblem.setVisible(bool(name))
        set_portrait(self.emblem, rank_emblem(data.get("tier")), "")
        self.lp.setVisible(type(data.get("lp")) is int)
        if type(data.get("lp")) is int:
            self.lp.setText(f"{data['lp']} LP")
        wins, losses = data.get("w"), data.get("l")
        total = wins + losses if type(wins) is int and type(losses) is int else None
        self.set_metric(0, wins, total, total is not None)
        self.set_metric(1, week.get("wins"), week.get("games"), week.get("complete", False))

    def set_metric(self, index, wins, total, complete):
        percent, note = self.metrics[index]
        if total:
            rate = f"{100 * wins / total:.1f}".replace(".", ",")
            percent.setText(f"{rate}%")
            note.setText(f"{wins} В · {total - wins} П" if complete else f"{wins} В · {total - wins} П · частично")
        else:
            percent.setText("—")
            note.setText("Нет матчей" if complete else "Нет данных")


class MatchCard(QWidget):
    def __init__(self, artwork, item, open_review):
        super().__init__()
        self.artwork = artwork
        self.item = item
        self.match_id = item["id"]
        self.review = None
        self.setMinimumHeight(104)
        self.splash = QPixmap()
        self.portrait = QPixmap()
        champion = item.get("champion") or "Неизвестный чемпион"
        key, patch = item.get("portrait"), item.get("assetVersion")
        self.splash_url = f"{DDRAGON}/cdn/img/champion/splash/{key}_0.jpg" if key else ""
        self.portrait_url = f"{DDRAGON}/cdn/{patch}/img/champion/{key}.png" if key and patch else ""
        self.initials = champion[:2].upper() if key else "—"
        win = item.get("win")
        color = "#a4d3ba" if win is True else "#e3a2ae" if win is False else "#aba1bb"
        self.edge = QColor(color)

        row = QHBoxLayout(self)
        row.setContentsMargins(18, 11, 18, 11)
        row.setSpacing(12)
        self.icon = icon_label(56, "dashboardAvatar")
        self.icon.setContentsMargins(2, 2, 2, 2)
        row.addWidget(self.icon)
        details = QVBoxLayout()
        details.setSpacing(2)
        name = label(champion, "dashboardMatchName", wrap=True)
        details.addWidget(name)
        result = label("Победа" if win is True else "Поражение" if win is False else "Результат неизвестен", "dashboardOutcome")
        result.setStyleSheet(f"color: {color};")
        details.addWidget(result)
        queue = item.get("queue")
        date = QDateTime.fromMSecsSinceEpoch(item["playedAt"]).toString("dd.MM, HH:mm") if item.get("playedAt") else ""
        duration = item.get("duration")
        pretty_duration = f"{duration // 60}:{duration % 60:02}" if type(duration) is int and duration > 0 else ""
        context = "  ·  ".join(filter(None, (QUEUE_NAMES.get(queue, "Другой режим"), date, pretty_duration)))
        details.addWidget(label(context, "dashboardMatchMeta", wrap=True))
        row.addLayout(details, 3)

        kda = item.get("kda") or ()
        self.kda = self.stat("KDA", " / ".join(map(str, kda)) if len(kda) == 3 and all(type(x) is int for x in kda) else "—")
        self.cs = self.stat("Фарм", self.number(item.get("cs")))
        self.damage = self.stat("Урон", self.number(item.get("damage")))
        for stat in (self.kda, self.cs, self.damage):
            row.addWidget(stat, 1, Qt.AlignmentFlag.AlignVCenter)
        if queue == 420:
            self.review = button("Разбор ↗", lambda: open_review(self.match_id), "dashboardReview")
            self.review.setAccessibleName(f"Разбор матча · {champion} · {date}")
            self.review.setFixedWidth(85)
            row.addWidget(self.review)
        else:
            row.addSpacing(85 + row.spacing())
        artwork.changed.connect(self.paint_art)
        self.paint_art()

    @staticmethod
    def number(value):
        return f"{value:,}".replace(",", " ") if type(value) is int else "—"

    @staticmethod
    def stat(title, value):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        layout.addWidget(label(value, "dashboardMatchStat"))
        layout.addWidget(label(title, "dashboardMatchMeta"))
        return widget

    def set_compact(self, width):
        self.cs.setVisible(width >= 565)
        self.damage.setVisible(width >= 730)

    def paint_art(self):
        if self.splash.isNull() and self.splash_url:
            self.splash = self.artwork.image(self.splash_url)
            if not self.splash.isNull():
                self.update()
        if self.portrait.isNull():
            self.portrait = self.artwork.image(self.portrait_url)
            set_portrait(self.icon, self.portrait, self.initials)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        bounds = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        border = QPainterPath()
        border.addRoundedRect(bounds, 12, 12)
        painter.setClipPath(border)
        painter.fillRect(bounds, QColor("#191820"))
        if not self.splash.isNull():
            target = QRectF(bounds.width() * 0.36, 0, bounds.width() * 0.64, bounds.height())
            scale = max(target.width() / self.splash.width(), target.height() / self.splash.height())
            width, height = target.width() / scale, target.height() / scale
            source = QRectF((self.splash.width() - width) * 0.62, (self.splash.height() - height) * 0.30, width, height)
            painter.drawPixmap(target, self.splash, source)
            fade = QLinearGradient(target.topLeft(), target.topRight())
            fade.setColorAt(0, QColor("#191820"))
            fade.setColorAt(0.48, QColor(21, 19, 29, 163))
            fade.setColorAt(1, QColor(21, 19, 29, 168))
            painter.fillRect(target, fade)
        painter.fillRect(QRectF(0, 0, 4, bounds.height()), self.edge)
        painter.setClipping(False)
        painter.setPen(QPen(QColor("#35303f")))
        painter.drawPath(border)


class MatchList(QWidget):
    def __init__(self, artwork, open_review, *, overview=False, open_history=None, open_latest=None):
        super().__init__()
        self.artwork, self.open_review, self.overview = artwork, open_review, overview
        self.limit = OVERVIEW_MATCHES if overview else HISTORY_PAGE
        self.matches = []
        self.has_more = False
        self.rows = []
        self.compact_width = 1000
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        if overview:
            header = QHBoxLayout()
            header.addWidget(label("История матчей", "dashboardSection"), 1)
            self.latest = button("Последний разбор", open_latest, "dashboardReview")
            self.history = button("Вся история", open_history, "dashboardReview")
            header.addWidget(self.latest)
            header.addWidget(self.history)
            header.setSpacing(6)
            layout.addLayout(header)
        self.cards = QVBoxLayout()
        self.cards.setSpacing(8)
        layout.addLayout(self.cards)
        self.empty = label("", "dashboardMuted", wrap=True)
        layout.addWidget(self.empty)
        self.more = button("Показать ещё", self.show_more, "dashboardReview")
        layout.addWidget(self.more, alignment=Qt.AlignmentFlag.AlignLeft)

    def populate(self, matches, available, has_more=False):
        if matches[:len(self.rows)] != self.matches[:len(self.rows)]:
            self.replace_rows(matches[:self.limit])
        self.matches, self.has_more = matches, has_more
        self.add_rows()
        self.empty.setText("В истории пока нет матчей." if available else "История появится после подключения к клиенту.")
        self.empty.setVisible(not matches)
        self.update_more()

    def show_more(self):
        if self.limit <= len(self.matches):
            self.limit += HISTORY_PAGE
        self.add_rows()
        self.update_more()

    def update_more(self):
        self.more.setVisible(not self.overview and (self.has_more or len(self.matches) > self.limit))
        self.update_focus_order()

    def update_focus_order(self):
        controls = [row.review for row in self.rows if row.review is not None]
        controls.append(self.more)
        # Keep the list at its existing place in the window's focus chain.
        anchor = self.history if self.overview else self.more.previousInFocusChain()
        while not self.overview and anchor is not self.more and (self.isAncestorOf(anchor)
                                                                or not anchor.focusPolicy() & Qt.FocusPolicy.TabFocus):
            anchor = anchor.previousInFocusChain()
        if anchor is not self.more:
            controls.insert(0, anchor)
        for before, after in zip(controls, controls[1:]):
            QWidget.setTabOrder(before, after)

    def replace_rows(self, matches):
        existing = {row.match_id: row for row in self.rows}
        focused = next((row for row in self.rows if row.review and row.review.hasFocus()), None)
        replacement = None
        for row in self.rows:
            self.cards.removeWidget(row)
        self.rows.clear()
        for item in matches:
            row = existing.get(item["id"])
            if row is not None and row.item == item:
                existing.pop(row.match_id)
                self.cards.addWidget(row)
                self.rows.append(row)
            else:
                added = self.add_row(item)
                if row is focused and focused is not None:
                    replacement = added
        for row in existing.values():
            row.setProperty("automationRetired", True)
            row.hide()
            row.deleteLater()
        if replacement and replacement.review and self.isVisible():
            replacement.show()
            replacement.review.setFocus(Qt.FocusReason.OtherFocusReason)

    def add_rows(self):
        for item in self.matches[len(self.rows):self.limit]:
            self.add_row(item)

    def add_row(self, item):
        row = MatchCard(self.artwork, item, self.open_review)
        if row.review is not None:
            scope = "overview" if self.overview else "history"
            row.review.setProperty("automationId", f"{scope}_match_{row.match_id}_review")
            row.review.setAccessibleName(f"Разбор матча {row.match_id}")
        row.set_compact(self.compact_width)
        self.cards.addWidget(row)
        self.rows.append(row)
        return row

    def reflow(self, width):
        self.compact_width = width
        for row in self.rows:
            row.set_compact(width)


class Dashboard(QWidget):
    def __init__(self, artwork, open_review, open_history, open_latest):
        super().__init__()
        self.data = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        self.connection_panel, connection = card()
        self.connection_title = label("", "dashboardSection", wrap=True)
        self.connection_message = label("", "captionStrong", wrap=True)
        self.connection_hint = label("", "caption", wrap=True)
        for item in (self.connection_title, self.connection_message, self.connection_hint):
            connection.addWidget(item)
        self.connection_actions = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.retry = button("Повторить подключение", lambda: None, "tab")
        self.builds = button("Посмотреть сборки", lambda: None, "primary")
        self.voice = button("Проверить голос", lambda: None, "tab")
        for item in (self.retry, self.builds, self.voice):
            self.connection_actions.addWidget(item)
        connection.addLayout(self.connection_actions)
        layout.addWidget(self.connection_panel)
        self.profile_area = QWidget()
        self.top = QGridLayout(self.profile_area)
        self.top.setContentsMargins(0, 0, 0, 0)
        self.top.setSpacing(14)
        self.profile = ProfileCard(artwork)
        self.ranks = {"solo": RankCard("Solo/Duo"), "flex": RankCard("Flex")}
        layout.addWidget(self.profile_area)

        self.charts_area = QWidget()
        self.charts = QBoxLayout(QBoxLayout.Direction.LeftToRight, self.charts_area)
        self.charts.setContentsMargins(0, 0, 0, 0)
        self.charts.setSpacing(14)
        trend_panel, trend = card()
        self.trend_panel = trend_panel
        trend_header = QHBoxLayout()
        trend_header.addWidget(label("Изменение ранга", "dashboardSection", wrap=True), 1)
        self.queue = QComboBox()
        self.queue.setProperty("role", "dashboardQueue")
        self.queue.addItem("Solo/Duo", "solo")
        self.queue.addItem("Flex", "flex")
        self.queue.currentIndexChanged.connect(self.paint_trend)
        trend_header.addWidget(self.queue)
        trend.addLayout(trend_header)
        self.season = label("Сезон", "dashboardMuted")
        trend.addWidget(self.season)
        self.trend = RankChart()
        trend.addWidget(self.trend)
        self.charts.addWidget(trend_panel, 3)

        activity_panel, activity = card()
        self.activity_panel = activity_panel
        activity.addWidget(label("Активность за месяц", "dashboardSection"))
        self.month = label("", "dashboardMuted", wrap=True)
        activity.addWidget(self.month)
        self.activity = MonthChart()
        activity.addWidget(self.activity)
        self.charts.addWidget(activity_panel, 2)
        layout.addWidget(self.charts_area)
        self.matches = MatchList(artwork, open_review, overview=True, open_history=open_history, open_latest=open_latest)
        layout.addWidget(self.matches)
        self.columns = None
        self.card_keys = None
        self.reflow(1000)

    def populate(self, data, connection=None):
        self.data = data
        info = connection or connection_view({"homeProfile": data, "phase": "offline"})
        self.connection_title.setText(info["title"])
        self.connection_message.setText(info["message"])
        self.connection_hint.setText(info["hint"])
        self.connection_hint.setVisible(bool(info["hint"]))
        ready = info.get("state") == "ready"
        self.connection_title.setVisible(not ready)
        for item in (self.builds, self.voice):
            item.setVisible(not ready)
        self.connection_panel.setVisible(not ready or info.get("history") in {"cached", "unavailable"})
        self.retry.setEnabled(not info.get("refreshing", False))
        self.retry.setVisible(info.get("state") != "ready")
        has_profile = bool(data.get("profile"))
        self.profile_area.setVisible(has_profile)
        for key, widget in self.ranks.items():
            widget.setVisible(has_profile and bool(data.get("ranks", {}).get(key)))
        self.reflow(getattr(self, "content_width", 1000))
        self.trend_panel.setVisible(any(data.get("trend", {}).values()))
        self.activity_panel.setVisible(bool(data.get("month", {}).get("available")))
        self.charts_area.setVisible(not self.trend_panel.isHidden() or not self.activity_panel.isHidden())
        self.matches.setVisible(bool(data.get("matches")) or bool(data.get("historyAvailable")))
        self.profile.populate(data.get("profile", {}), data.get("assetVersion"))
        for key, widget in self.ranks.items():
            widget.populate(data.get("ranks", {}).get(key, {}), data.get("weekly", {}).get(key, {}))
        month = data.get("month", {})
        if month:
            amount = sum(month.get("days", {}).values())
            month_name = MONTHS[month["month"] - 1]
            if month.get("available"):
                text = f"{month_name}  ·  Матчей: {amount}"
                if not month.get("complete"):
                    text += "  ·  Частичные данные"
            else:
                text = f"{month_name}  ·  История недоступна"
        else:
            text = "Матчи по дням"
        self.month.setText(text)
        self.activity.set_data(month)
        self.matches.populate(data.get("matches", []), data.get("historyAvailable", False))
        self.paint_trend()

    def paint_trend(self):
        period = self.data.get("range", ())
        queue = self.queue.currentData()
        points = self.data.get("trend", {}).get(queue, ())
        self.season.setText(f"Сезон {QDateTime.fromMSecsSinceEpoch(period[0]).date().year()}" if period else "Сезон")
        self.trend.set_data(points, period, self.data.get("ranks", {}).get(queue, {}))

    def reflow(self, width):
        self.content_width = width
        self.connection_actions.setDirection(QBoxLayout.Direction.TopToBottom if width < 660 else QBoxLayout.Direction.LeftToRight)
        columns = 3 if width >= 890 else 2 if width >= 590 else 1
        self.matches.reflow(width)
        card_keys = tuple(key for key in self.ranks if self.data.get("ranks", {}).get(key))
        if columns == self.columns and card_keys == self.card_keys:
            return
        self.columns = columns
        self.card_keys = card_keys
        for widget in (self.profile, *self.ranks.values()):
            self.top.removeWidget(widget)
        cards = [self.profile, *(self.ranks[key] for key in card_keys)]
        if columns == 2 and len(cards) == 3:
            self.top.addWidget(self.profile, 0, 0, 1, 2)
            self.top.addWidget(cards[1], 1, 0)
            self.top.addWidget(cards[2], 1, 1)
        else:
            for index, widget in enumerate(cards):
                self.top.addWidget(widget, index // columns, index % columns)
        for index in range(3):
            self.top.setColumnStretch(index, int(index < min(columns, len(cards))))
        direction = QBoxLayout.Direction.LeftToRight if columns == 3 else QBoxLayout.Direction.TopToBottom
        self.charts.setDirection(direction)
