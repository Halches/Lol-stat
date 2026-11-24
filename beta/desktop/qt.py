"""Windows shell for the beta companion."""
import sys
from concurrent.futures import ThreadPoolExecutor
from time import monotonic
from urllib.parse import urlsplit

from PySide6.QtCore import QMargins, QRect, QSettings, QSignalBlocker, QStringListModel, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QBoxLayout, QComboBox, QCompleter, QFrame, QGridLayout, QHBoxLayout,
    QLayout, QLineEdit, QScrollArea, QVBoxLayout, QWidget,
)

from artwork import Artwork, DraftHero, loadout_catalog
from automation import AutomationServer
from build_choice import BuildChoice
from draft import DraftScreen
from home import Dashboard, MatchList, logo_path, set_portrait
from theme import STYLE
from widgets import button, icon_label, label, panel
from worker import Companion, DDRAGON, DRAFT_PHASES, HOME_PHASES, PLAYING, ROLES, SOURCE_ERRORS
from desktop.voice_assistant import Assistant, AssistantPage
from desktop.update_page import UpdatePage
from desktop.update_service import apply_update, confirm_startup, last_update_error
from overlays import OverlayControls


PHASES = {
    "offline": "Ожидаем клиент League of Legends",
    "pick": "Выберите чемпиона и роль",
    "loading": "Загружаем сборку…",
    "no_build": "Сборка для этого патча недоступна",
    "game": "Матч идёт",
    "ended": "Матч завершён",
}
PHASE_LABELS = {"offline": "КЛИЕНТ", "pick": "ДРАФТ", "loading": "ДРАФТ", "no_build": "ДРАФТ",
                "draft": "ДРАФТ", "game": "МАТЧ", "ended": "ПОСЛЕ МАТЧА"}
HOME_CONNECTION = {
    "offline": "Ожидаем клиент LoL",
    "Matchmaking": "Идёт поиск матча",
    "ReadyCheck": "Найден матч",
}
HOME_PAGES = {
    "overview": "Главная",
    "history": "История матчей",
    "builds": "Сборки",
    "assistant": "Голосовой помощник",
    "settings": "Настройки",
    "updates": "Обновление",
}
REVIEW_RETRY_SECONDS = 30


def draft_window_bounds(area, frame):
    available_width = area.width() - frame.left() - frame.right()
    available_height = area.height() - frame.top() - frame.bottom()
    width = min(1540, max(1, available_width - 32))
    height = min(880, max(1, available_height - 32))
    return QRect(area.x() + frame.left() + (available_width - width) // 2,
                 area.y() + frame.top() + (available_height - height) // 2, width, height)


class Window(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("main")
        self.setWindowTitle("LoL Helper · EUW")
        self.setMinimumWidth(670)
        self.resize(1570, 940)
        self.setWindowIcon(QIcon(str(logo_path())))
        self.companion = Companion()
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.preview_executor = ThreadPoolExecutor(max_workers=1)
        self.settings = QSettings("LoL Helper", "Closed Beta")
        self.assistant = Assistant(self.settings, self.companion, self,
                                   running="--probe" not in sys.argv and "--smoke" not in sys.argv)
        self.snapshot = {"phase": "offline"}
        self.job = self.export_job = None
        self.role_change_pending = False
        self.draft_action_focus = None
        self.notice_draft_key = None
        self.draft_key = None
        self.flow_generation = None
        self.choice = None
        self.draft_build = None
        self.match_build = None
        self.preview_job = None
        self.preview_options = {}
        self.preview_choice = None
        self.preview_target = None
        self.preview_patch = None
        self.preview_action_focus = None
        self.preview_session_context = None
        self.preview_revision = 0
        self.preview_request_revision = None
        self.champion_index = {}
        self.champion_catalog = None
        self.latest_match = None
        self.draft_active = False
        self.normal_geometry = None
        self.auto_review_opened = None
        self.auto_review_retry = None
        self.probe = "--probe" in sys.argv
        self.auto_open_review = not self.probe and "--smoke" not in sys.argv
        self.shown_build = None
        self.loadout_catalog = loadout_catalog()
        self.artwork = Artwork(self)
        self.artwork.changed.connect(self.render_art)
        if self.probe:
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.overlays = OverlayControls(self, self.settings, self.artwork, self.loadout_catalog, probe=self.probe)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.home_page = "overview"
        self.menu_sidebar = self.build_menu_sidebar()
        self.menu_sidebar.hide()
        outer.addWidget(self.menu_sidebar)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(self.scroll, 1)
        body = QWidget()
        body.setObjectName("body")
        self.scroll.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        layout.setContentsMargins(22, 18, 22, 14)
        layout.setSpacing(13)
        self.game_header = QWidget()
        header = QHBoxLayout(self.game_header)
        header.setContentsMargins(0, 0, 0, 0)
        brand = label("L", "brand")
        brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand.setFixedSize(42, 42)
        header.addWidget(brand)
        identity = QVBoxLayout()
        identity.setSpacing(1)
        identity.setContentsMargins(5, 0, 0, 0)
        identity.addWidget(label("LoL Helper", "title"))
        identity.addWidget(label("EUW · Рейтинговая Solo/Duo", "caption"))
        header.addLayout(identity)
        header.addStretch()
        self.assistant_mute = button("Голос: выкл", lambda checked: self.assistant_page.master.setChecked(checked), "tab")
        self.assistant_mute.setCheckable(True)
        self.assistant_mute.setAccessibleName("Включить или выключить голосового помощника")
        self.assistant_mute.setEnabled(bool(self.assistant.pack.voices))
        header.addWidget(self.assistant_mute)
        self.stage = label("КЛИЕНТ", "chip")
        header.addWidget(self.stage, alignment=Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.game_header)

        self.hero = DraftHero()
        hero_contents = QVBoxLayout(self.hero)
        hero_contents.setContentsMargins(20, 18, 20, 18)
        hero_contents.setSpacing(3)
        hero_contents.addStretch()
        self.headline = label("Подключаемся к клиенту LoL…", "headline", wrap=True)
        hero_contents.addWidget(self.headline)
        self.status = label("", "captionStrong", wrap=True)
        hero_contents.addWidget(self.status)
        hero_contents.addStretch()
        layout.addWidget(self.hero)

        self.workspace = QWidget()
        menu = QVBoxLayout(self.workspace)
        menu.setContentsMargins(0, 0, 0, 0)
        menu.setSpacing(14)
        layout.addWidget(self.workspace)
        self.menu_header = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.page_title = label("", "dashboardTitle", wrap=True)
        self.menu_header.addWidget(self.page_title, 1)
        self.home_connection = label("", "homeConnection")
        self.menu_header.addWidget(self.home_connection, alignment=Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        menu.addLayout(self.menu_header)
        self.update_banner = QWidget()
        self.update_banner_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight, self.update_banner)
        self.update_banner_layout.setContentsMargins(0, 0, 0, 0)
        self.update_banner_text = label("", "notice", wrap=True)
        self.update_banner_layout.addWidget(self.update_banner_text, 1)
        self.update_banner_button = button("Открыть обновление", lambda: self.show_home_page("updates"), "tab")
        self.update_banner_layout.addWidget(self.update_banner_button)
        self.update_banner.hide()
        menu.addWidget(self.update_banner)
        self.menu_notice = self.slot(menu)
        self.dashboard = Dashboard(self.artwork, self.open_match_review,
                                   lambda: self.show_home_page("history"), self.open_latest_review)
        self.match_history = MatchList(self.artwork, self.open_match_review)
        self.build_page = QWidget()
        main_column = QVBoxLayout(self.build_page)
        main_column.setContentsMargins(0, 0, 0, 0)
        main_column.addWidget(self.build_search())
        main_column.addWidget(self.build_preview_placeholder())
        self.settings_page = self.slot(menu)
        self.assistant_page = AssistantPage(self.assistant)
        self.assistant.changed.connect(self.update_assistant_button)
        self.update_assistant_button()
        self.updates_page = UpdatePage(
            self.settings, lambda: self.is_home() and self.export_job is None,
            running=not self.probe and "--smoke" not in sys.argv)
        self.updates_page.restart.connect(self.close)
        self.updates_page.changed.connect(self.update_update_notice)
        self.home_views = {"overview": self.dashboard, "history": self.match_history, "builds": self.build_page,
                           "assistant": self.assistant_page,
                           "settings": self.settings_page.parentWidget(), "updates": self.updates_page}
        for key, view in self.home_views.items():
            if key != "settings":
                menu.addWidget(view)

        self.build_elsewhere = self.slot(layout)

        self.build_panel, build_contents = panel()
        self.build_contents = build_contents
        self.preview_hero = DraftHero()
        self.preview_hero.setMinimumHeight(108)
        preview_contents = QVBoxLayout(self.preview_hero)
        preview_contents.setContentsMargins(16, 13, 16, 13)
        preview_contents.setSpacing(3)
        self.preview_champion = label("", "previewChampion", wrap=True)
        self.preview_context = label("", "captionStrong", wrap=True)
        preview_contents.addStretch()
        preview_contents.addWidget(self.preview_champion)
        preview_contents.addWidget(self.preview_context)
        preview_contents.addStretch()
        build_contents.addWidget(self.preview_hero)
        self.build_heading = label("Сборка", "section")
        build_contents.addWidget(self.build_heading)
        self.choice_grid = QGridLayout()
        self.choice_grid.setSpacing(5)
        self.choice_columns = None
        self.choices = {}
        for key, title in (("pick", "Популярная"), ("win", "По винрейту"), ("unusual", "Нестандартная")):
            choice = button(title, lambda _checked=False, key=key: self.choose_variant(key), "buildChoice")
            choice.setCheckable(True)
            self.choices[key] = choice
        self.otp_choice = BuildChoice(self.artwork, "Мейнеры")
        self.extra_build_choice = BuildChoice(self.artwork, "Другие сборки")
        for combo in (self.otp_choice, self.extra_build_choice):
            combo.currentIndexChanged.connect(lambda index, combo=combo: self.choose_special_build(combo, index))
        self.choice_widgets = [*self.choices.values(), self.otp_choice, self.extra_build_choice]
        build_contents.addLayout(self.choice_grid)
        self.build_source_button = button("Турнир на Leaguepedia ↗", self.open_build_source, "tab")
        build_contents.addWidget(self.build_source_button, alignment=Qt.AlignmentFlag.AlignLeft)
        item_header = QHBoxLayout()
        self.item_heading = label("Порядок покупки", "captionStrong")
        item_header.addWidget(self.item_heading)
        item_header.addStretch()
        self.stats = label("", "chip")
        item_header.addWidget(self.stats)
        build_contents.addLayout(item_header)
        self.item_grid = QGridLayout()
        self.item_grid.setSpacing(8)
        self.item_slots = []
        for _ in range(6):
            tile, contents = panel("item")
            tile.setMinimumHeight(96)
            contents.setContentsMargins(6, 7, 6, 7)
            contents.setSpacing(5)
            icon = icon_label(32, "icon")
            name = label("", "itemName", wrap=True)
            name.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
            name.setMinimumHeight(43)
            contents.addWidget(icon, alignment=Qt.AlignmentFlag.AlignHCenter)
            contents.addWidget(name, 1)
            self.item_slots.append((tile, icon, name))
        build_contents.addLayout(self.item_grid)
        self.situational = label("", "caption", wrap=True)
        build_contents.addWidget(self.situational)
        build_contents.addWidget(self.build_loadout())
        self.import_button = button("Импортировать руны и предметы", self.import_build, "primary")
        self.spell_button = button("Импортировать заклинания", lambda: self.import_build(spells_only=True))
        self.import_timer = label("", "chip")
        build_contents.addWidget(self.import_timer, alignment=Qt.AlignmentFlag.AlignRight)
        self.import_actions = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.import_actions.addWidget(self.import_button)
        self.import_actions.addWidget(self.spell_button)
        build_contents.addLayout(self.import_actions)
        self.import_hint = label("", "caption", wrap=True)
        build_contents.addWidget(self.import_hint)
        self.build_home = main_column
        self.build_home.addWidget(self.build_panel)
        self.build_compact = None
        self.arrange_build(wide=True)
        self.draft_screen = DraftScreen(self.artwork, self.set_draft_tab, self.set_draft_role)
        self.artwork.changed.connect(self.draft_screen.paint_artwork)
        self.draft_screen.hide()
        layout.addWidget(self.draft_screen, 1)

        self.review_button = button("Открыть разбор матча", lambda: self.open_site(saved=True), "primary")
        layout.addWidget(self.review_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.notice = label("", "notice", wrap=True)
        self.notice.hide()
        self.notice_home = self.slot(layout)
        self.notice_home.addWidget(self.notice)

        self.settings_panel = self.build_settings()
        self.settings_elsewhere = self.slot(layout)
        self.settings_elsewhere.addWidget(self.settings_panel)
        layout.addStretch()
        layout.addWidget(label(
            "LoL Helper is not endorsed by Riot Games and does not reflect the views or opinions of Riot Games or anyone "
            "officially involved in producing or managing Riot Games properties. Riot Games and all associated properties "
            "are trademarks or registered trademarks of Riot Games, Inc.", "footer", wrap=True,
        ))
        self.build_panel.hide()
        self.review_button.hide()
        self.update_champion_index()
        self.timer = QTimer(self)
        if not self.probe:
            self.timer.timeout.connect(self.poll)
            self.timer.start(225)
        self.automation = AutomationServer(self)
        for page, control in self.nav_buttons.items():
            self.automation.add(f"menu_{page}", control.text(), control, "button")
        for control, control_widget in (
            ("import_build", self.import_button), ("open_review", self.review_button),
            ("save_settings", self.save_button), ("open_site", self.site_button),
            ("choose_popular", self.choices["pick"]), ("choose_winrate", self.choices["win"]),
            ("choose_unusual", self.choices["unusual"]), ("open_build_source", self.build_source_button),
            ("import_spells", self.spell_button),
            ("preview_build", self.preview_button), ("open_latest_review", self.dashboard.matches.latest),
            ("open_match_history", self.dashboard.matches.history), ("show_more_matches", self.match_history.more),
            ("draft_stats_tab", self.draft_screen.stats_tab), ("draft_build_tab", self.draft_screen.build_tab),
        ):
            self.automation.add(control, control_widget.text(), control_widget, "button")
        for (role, title), card in zip(ROLES.items(), self.draft_screen.cards["allies"]):
            self.automation.add(f"draft_comments_{role.lower()}", f"Все комментарии · {title}",
                                card.more_comments, "button")
        for side, title in (("allies", "союзник"), ("enemies", "соперник")):
            for index, card in enumerate(self.draft_screen.cards[side], 1):
                self.automation.add(f"draft_role_{side}_{index}", f"Роль · {title} {index}",
                                    card.role_icon, "choice")
                self.automation.add(f"draft_details_{side}_{index}", f"Детали статистики · {title} {index}",
                                    card.insight_button, "button")
        for key, toggle in self.overlays.desktop.items():
            self.automation.add("overlay" if key == "build" else f"overlay_{key}", toggle.text(), toggle, "checkbox")
        self.automation.add("site", "Адрес закрытого сайта", self.site, "text")
        self.automation.add("champion_search", "Чемпион", self.champion_input, "text")
        self.automation.add("preview_role", "Роль", self.role_input, "choice")
        self.automation.add("other_build", "Другие сборки", self.extra_build_choice, "choice")
        self.automation.add("otp_build", "Мейнеры", self.otp_choice, "choice")
        self.automation.add("rank_history_queue", "Очередь графика ранга", self.dashboard.queue, "choice")
        self.automation.add("update_action", "Проверить или установить обновление", self.updates_page.action, "button")
        self.automation.add("update_github", "Все выпуски на GitHub", self.updates_page.github, "button")
        for key, widget, kind in (
            ("assistant_enabled", self.assistant_page.master, "checkbox"),
            ("assistant_voice", self.assistant_page.voice, "choice"),
            ("assistant_category", self.assistant_page.category, "choice"),
            ("assistant_role", self.assistant_page.role, "choice"),
            ("assistant_test", self.assistant_page.test, "button"),
            ("assistant_stop", self.assistant_page.stop, "button"),
            ("assistant_mute", self.assistant_mute, "button"),
        ):
            title = widget.text() if kind == "button" else widget.accessibleName()
            self.automation.add(key, title, widget, kind)
        for (scope, topic), widget in self.assistant_page.checks.items():
            self.automation.add(f"assistant_{scope.lower() or 'common'}_{topic}", widget.accessibleName(), widget, "checkbox")
        self.home_active = None
        self.paint_snapshot()
        if self.auto_open_review:
            self.automation.start()

    @staticmethod
    def slot(layout):
        widget = QWidget()
        contents = QVBoxLayout(widget)
        contents.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widget)
        return contents

    def update_assistant_button(self):
        enabled = self.assistant.flag("assistant/enabled", False)
        self.assistant_mute.setChecked(enabled)
        self.assistant_mute.setText("Голос: вкл" if enabled else "Голос: выкл")

    def build_menu_sidebar(self):
        sidebar = QFrame()
        sidebar.setObjectName("dashboardSidebar")
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(12, 19, 12, 15)
        layout.setSpacing(7)
        self.sidebar_identity = QHBoxLayout()
        self.sidebar_identity.setSpacing(8)
        self.sidebar_mark = icon_label(34, "")
        set_portrait(self.sidebar_mark, QPixmap(str(logo_path())), "L")
        self.sidebar_brand = label("LoL Helper", "dashboardBrand")
        self.sidebar_identity.addWidget(self.sidebar_mark)
        self.sidebar_identity.addWidget(self.sidebar_brand, 1)
        layout.addLayout(self.sidebar_identity)
        layout.addSpacing(24)
        self.nav_buttons = {}
        for key, title in HOME_PAGES.items():
            control = button(title, lambda _checked=False, page=key: self.show_home_page(page), "dashboardNav")
            if key == "assistant":
                control.setText("Голосовой\nпомощник")
                control.setAccessibleName(title)
            control.setCheckable(True)
            self.nav_buttons[key] = control
            layout.addWidget(control)
        layout.addStretch()
        return sidebar

    def update_update_notice(self):
        available = self.updates_page.available
        self.update_banner.setVisible(bool(available))
        self.update_banner_text.setText(f"Доступна новая версия LoL Helper {available.version}" if available else "")
        self.nav_buttons["updates"].setText("Обновление •" if available else "Обновление")

    def arrange_build(self, *, wide, compact=False):
        columns = 6 if wide and not compact else 3
        margins = (16, 13, 16, 13) if wide else (11, 9, 11, 9)
        self.build_contents.setContentsMargins(*margins)
        self.build_contents.setSpacing(10 if wide else 7)
        for index, (tile, _, name) in enumerate(self.item_slots):
            self.item_grid.removeWidget(tile)
            tile.setMinimumHeight(96 if wide else 77)
            name.setMinimumHeight(43 if wide else 28)
            self.item_grid.addWidget(tile, index // columns, index % columns)
        for index in range(6):
            self.item_grid.setColumnStretch(index, int(index < columns))
        direction = QBoxLayout.Direction.LeftToRight if wide else QBoxLayout.Direction.TopToBottom
        self.loadout_columns.setDirection(QBoxLayout.Direction.TopToBottom if compact else direction)
        self.loadout_columns.setSpacing(12 if wide else 6)
        self.import_actions.setDirection(direction)
        self.import_actions.setSpacing(8 if wide else 5)
        self.arrange_choices()
        self.build_contents.activate()
        self.build_panel.updateGeometry()

    def arrange_choices(self):
        columns = 1 if self.draft_active and self.height() >= 780 else 2
        if columns == self.choice_columns:
            return
        self.choice_columns = columns
        for index, widget in enumerate(self.choice_widgets):
            self.choice_grid.removeWidget(widget)
            self.choice_grid.addWidget(widget, index // columns, index % columns)
        for index in range(2):
            self.choice_grid.setColumnStretch(index, int(index < columns))

    def arrange_home(self):
        compact_sidebar = self.width() < 1180
        self.menu_sidebar.setFixedWidth(144 if compact_sidebar else 214)
        if self.sidebar_brand.property("compact") != compact_sidebar:
            self.sidebar_brand.setProperty("compact", compact_sidebar)
            self.sidebar_brand.style().unpolish(self.sidebar_brand)
            self.sidebar_brand.style().polish(self.sidebar_brand)
            self.sidebar_brand.updateGeometry()
            self.sidebar_mark.setFixedSize(28 if compact_sidebar else 34, 28 if compact_sidebar else 34)
            self.sidebar_identity.setSpacing(6 if compact_sidebar else 8)
            set_portrait(self.sidebar_mark, QPixmap(str(logo_path())), "L")
        width = self.width() - self.menu_sidebar.width() - 52
        self.dashboard.reflow(width)
        self.match_history.reflow(width)
        self.settings_panel.setFixedWidth(min(694, width))
        compact = width < 660
        self.menu_header.setDirection(QBoxLayout.Direction.TopToBottom if compact else QBoxLayout.Direction.LeftToRight)
        self.update_banner_layout.setDirection(QBoxLayout.Direction.TopToBottom if compact else QBoxLayout.Direction.LeftToRight)
        self.assistant_page.reflow(width)
        if compact != self.build_compact:
            self.build_compact = compact
            self.search_row.setDirection(
                QBoxLayout.Direction.TopToBottom if compact else QBoxLayout.Direction.LeftToRight
            )
            self.arrange_build(wide=True, compact=compact)

    def show_home_page(self, page):
        if page != self.home_page:
            self.home_page = page
            self.set_notice("")
            self.scroll.verticalScrollBar().setValue(0)
        self.page_title.setText(HOME_PAGES[page])
        for name, view in self.home_views.items():
            view.setVisible(name == page)
            self.nav_buttons[name].setChecked(name == page)

    def set_home_active(self, home):
        if home == self.home_active:
            return
        self.home_active = home
        self.menu_sidebar.setVisible(home)
        self.menu_notice.parentWidget().setVisible(home and bool(self.notice.text()))
        self.settings_elsewhere.parentWidget().setVisible(not home and not self.draft_active)
        self.notice_home.parentWidget().setVisible(not home and not self.draft_active and bool(self.notice.text()))
        if home:
            self.build_home.addWidget(self.build_panel)
            self.settings_page.addWidget(self.settings_panel, alignment=Qt.AlignmentFlag.AlignLeft)
            self.menu_notice.addWidget(self.notice)
            self.arrange_home()
            self.show_home_page(self.home_page)
            controls = [*self.nav_buttons.values(), self.scroll, self.dashboard.queue, self.dashboard.matches.latest,
                        self.dashboard.matches.history, self.champion_input, self.role_input, self.preview_button,
                        *self.choice_widgets, self.build_source_button, self.site, self.save_button, self.site_button,
                        self.overlays.desktop_theme, self.overlays.desktop_scale, self.overlays.desktop_preview,
                        *self.overlays.desktop.values(), *self.assistant_page.focus_controls(),
                        self.updates_page.action, self.updates_page.github]
            for before, after in zip(controls, controls[1:]):
                QWidget.setTabOrder(before, after)
        else:
            self.settings_panel.setMinimumWidth(0)
            self.settings_panel.setMaximumWidth(694)
            self.settings_elsewhere.addWidget(self.settings_panel)
            if not self.draft_active:
                self.build_elsewhere.addWidget(self.build_panel)
                self.notice_home.addWidget(self.notice)
        self.settings_panel.setVisible(not self.draft_active)
        self.notice.setVisible(bool(self.notice.text()))

    def set_draft_active(self, active):
        if active == self.draft_active:
            return
        self.draft_active = active
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded if active else Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.hero.setVisible(not active)
        self.settings_panel.setVisible(not active)
        self.draft_screen.setVisible(active)
        self.workspace.setVisible(not active)
        self.settings_elsewhere.parentWidget().setVisible(not active and not self.home_active)
        self.notice_home.parentWidget().setVisible(not active and not self.home_active and bool(self.notice.text()))
        if active:
            self.normal_geometry = self.geometry()
            self.draft_screen.show_tab("stats", "")
            self.draft_screen.build_layout.addWidget(self.build_panel)
            self.draft_screen.notice_slot.addWidget(self.notice)
            if not self.isMaximized():
                window = self.windowHandle()
                frame = window.frameMargins() if window else QMargins()
                self.setGeometry(draft_window_bounds(self.screen().availableGeometry(), frame))
            self.update_draft_layout()
            self.set_draft_focus_order()
            if self.isActiveWindow():
                tab = self.draft_screen.stats_tab
                tab.setFocus(Qt.FocusReason.OtherFocusReason)
                QTimer.singleShot(0, self, lambda: self.scroll.ensureWidgetVisible(tab) if tab.hasFocus() else None)
        else:
            build_slot = self.build_home if self.is_home() else self.build_elsewhere
            build_slot.addWidget(self.build_panel)
            notice_slot = self.menu_notice if self.is_home() else self.notice_home
            notice_slot.addWidget(self.notice)
            if self.normal_geometry is not None and not self.isMaximized():
                self.setGeometry(self.normal_geometry)
        self.build_compact = None
        self.arrange_build(wide=not active)
        self.notice.setVisible(bool(self.notice.text()))
        self.scroll.verticalScrollBar().setValue(0)

    def set_draft_tab(self, tab):
        if self.draft_active and tab in {"stats", "build"}:
            self.draft_screen.show_tab(tab, "")
            self.paint_snapshot()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.draft_active:
            self.update_draft_layout()
            self.arrange_choices()
        elif self.home_active:
            self.arrange_home()

    def update_draft_layout(self):
        margins = self.scroll.widget().layout().contentsMargins()
        available = self.width() - margins.left() - margins.right() - self.scroll.verticalScrollBar().sizeHint().width()
        compact = available < self.draft_screen.side_by_side_width()
        self.draft_screen.set_compact(compact)
        seconds = (self.snapshot.get("draft") or {}).get("seconds")
        if seconds is not None:
            self.import_timer.setText(f"{seconds // 60:02}:{seconds % 60:02}")
        self.import_timer.setVisible(compact and seconds is not None and self.snapshot.get("phase") == "draft")

    def set_draft_focus_order(self):
        screen = self.draft_screen
        controls = [self.scroll, screen.stats_tab, screen.build_tab, *self.choice_widgets,
                    self.build_source_button, self.import_button, self.spell_button]
        for cards in screen.cards.values():
            for card in cards:
                controls.extend((card.role_icon, card.insight_button, card.more_comments))
        for before, after in zip(controls, controls[1:]):
            QWidget.setTabOrder(before, after)

    def build_search(self):
        self.search_panel, contents = panel("homeSearch")
        contents.setContentsMargins(20, 17, 20, 20)
        contents.setSpacing(14)
        contents.addWidget(label("Поиск сборки", "homeSection"))
        fields = QHBoxLayout()
        fields.setSpacing(10)
        self.champion_input = QLineEdit()
        self.champion_names = QStringListModel(self.champion_input)
        completer = QCompleter(self.champion_names, self.champion_input)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setMaxVisibleItems(8)
        self.champion_input.setCompleter(completer)
        self.champion_input.setPlaceholderText("Начните вводить имя")
        self.champion_input.setMaxLength(48)
        self.champion_input.textChanged.connect(self.preview_input_changed)
        self.champion_input.returnPressed.connect(self.request_preview)
        self.role_input = QComboBox()
        for role, title in ROLES.items():
            self.role_input.addItem(title, role)
        self.role_input.setPlaceholderText("Выберите роль")
        self.role_input.setCurrentIndex(-1)
        self.role_input.currentIndexChanged.connect(self.preview_input_changed)
        for title, field, stretch in (("Чемпион", self.champion_input, 1), ("Роль", self.role_input, 0)):
            column = QVBoxLayout()
            column.setSpacing(6)
            field_label = label(title, "homeField")
            field_label.setBuddy(field)
            column.addWidget(field_label)
            column.addWidget(field)
            fields.addLayout(column, stretch)
        self.preview_button = button("Показать сборку", self.request_preview, "primary")
        self.search_row = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.search_row.setSpacing(10)
        self.search_row.addLayout(fields, 1)
        self.search_row.addWidget(self.preview_button, alignment=Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)
        contents.addLayout(self.search_row)
        return self.search_panel

    def build_preview_placeholder(self):
        self.preview_placeholder, contents = panel("homePlaceholder")
        contents.setContentsMargins(20, 18, 20, 19)
        contents.setSpacing(6)
        contents.addWidget(label("Предпросмотр сборки", "homeSection"))
        self.preview_hint = label("Здесь появятся предметы, руны и заклинания.", "homeSecondary", wrap=True)
        contents.addWidget(self.preview_hint)
        self.preview_message = label("", "notice", wrap=True)
        self.preview_message.hide()
        contents.addWidget(self.preview_message)
        return self.preview_placeholder

    def build_settings(self):
        settings_panel, contents = panel("homePanel")
        settings_panel.setMaximumWidth(694)
        contents.setContentsMargins(17, 15, 17, 16)
        contents.setSpacing(12)
        contents.addWidget(label("Настройки", "homeSection"))

        site_group = QVBoxLayout()
        site_group.setSpacing(6)
        site_label = label("Адрес закрытого сайта", "homeField")
        self.site = QLineEdit(self.settings.value("site", "", type=str))
        self.site.setPlaceholderText("http://127.0.0.1:8000")
        self.site.returnPressed.connect(self.save)
        site_label.setBuddy(self.site)
        site_group.addWidget(site_label)
        site_group.addWidget(self.site)
        contents.addLayout(site_group)

        site_actions = QHBoxLayout()
        site_actions.setSpacing(8)
        self.save_button = button("Сохранить", self.save)
        self.site_button = button("Открыть сайт", self.open_site)
        site_actions.addWidget(self.save_button)
        site_actions.addWidget(self.site_button)
        contents.addLayout(site_actions)
        contents.addWidget(self.overlays.preferences)
        return settings_panel

    def update_champion_index(self):
        catalog = getattr(self.companion, "catalog", {})
        if catalog is self.champion_catalog:
            return
        if self.preview_options and self.preview_patch != catalog.get("patch"):
            self.preview_options = {}
            self.preview_choice = None
            self.set_preview_message("Патч обновился. Загрузите сборку ещё раз.")
        self.champion_catalog = catalog
        entries = {alias: int(cid) for cid, key in catalog.get("ids", {}).items()
                   for alias in (catalog.get("names", {}).get(key, key), key)}
        self.champion_index = {alias.casefold(): cid for alias, cid in entries.items()}
        self.champion_names.setStringList(sorted(entries, key=str.casefold))

    def build_loadout(self):
        self.loadout_panel, contents = panel("loadout")
        contents.setContentsMargins(11, 8, 11, 9)
        self.loadout_columns = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.loadout_columns.setSpacing(12)
        self.runes = QWidget()
        runes = QVBoxLayout(self.runes)
        runes.setContentsMargins(0, 0, 0, 0)
        runes.setSpacing(5)
        runes.addWidget(label("Руны", "captionStrong"))
        rune_groups = QHBoxLayout()
        rune_groups.setSpacing(11)
        self.rune_icons = []
        for sizes in ((30, 26, 26, 26), (26, 26), (22, 22, 22)):
            row = QHBoxLayout()
            row.setSpacing(4)
            icons = [icon_label(size, "rune") for size in sizes]
            for icon in icons:
                row.addWidget(icon)
            self.rune_icons.append(icons)
            rune_groups.addLayout(row)
        rune_groups.addStretch()
        runes.addLayout(rune_groups)
        self.loadout_columns.addWidget(self.runes, 1)

        self.spells = QWidget()
        spells = QVBoxLayout(self.spells)
        spells.setContentsMargins(0, 0, 0, 0)
        spells.setSpacing(5)
        spells.addWidget(label("Заклинания", "captionStrong"))
        spell_row = QHBoxLayout()
        spell_row.setSpacing(11)
        self.spell_icons = []
        for _ in range(2):
            cell = QWidget()
            row = QHBoxLayout(cell)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(5)
            icon = icon_label(29, "icon")
            name = label("", "caption")
            row.addWidget(icon)
            row.addWidget(name)
            spell_row.addWidget(cell)
            self.spell_icons.append((cell, icon, name))
        spells.addLayout(spell_row)
        self.loadout_columns.addWidget(self.spells)
        contents.addLayout(self.loadout_columns)
        self.loadout_panel.hide()
        return self.loadout_panel

    def set_notice(self, text, *, draft_key=None):
        self.notice_draft_key = draft_key
        self.notice.setText(text)
        self.notice.setVisible(bool(text))
        self.notice_home.parentWidget().setVisible(bool(text) and not self.home_active and not self.draft_active)
        self.menu_notice.parentWidget().setVisible(bool(text) and bool(self.home_active))

    def validated_site(self, address=None):
        site = (self.site.text() if address is None else address).strip().rstrip("/")
        message = "Введите адрес закрытого сайта без пути."
        try:
            url = urlsplit(site)
            port = url.port
        except ValueError:
            raise ValueError(message) from None
        local = url.scheme == "http" and url.hostname in ("localhost", "127.0.0.1", "::1")
        if ((url.scheme != "https" and not local) or not url.hostname
                or url.username is not None or url.path or url.query or url.fragment
                or port == 0 or url.netloc.endswith(":") or not QUrl(site, QUrl.ParsingMode.StrictMode).isValid()):
            raise ValueError(message)
        return site

    def save(self):
        try:
            site = self.validated_site() if self.site.text().strip() else ""
            self.settings.setValue("site", site)
            self.set_notice("Настройки сохранены.")
            self.open_pending_review()
        except ValueError as error:
            self.set_notice(str(error))

    def open_site(self, *, saved=False, path=None):
        try:
            address = self.settings.value("site", "", type=str) if saved else None
            site = self.validated_site(address)
        except ValueError as error:
            self.set_notice(str(error))
            if self.home_active:
                self.scroll.ensureWidgetVisible(self.notice)
            return False
        match_id = self.snapshot.get("matchId")
        destination = path or (f"/matches/{match_id}" if match_id else "/")
        if not QDesktopServices.openUrl(QUrl(site + destination)):
            self.set_notice("Не удалось открыть браузер.")
            return False
        return True

    def open_latest_review(self):
        match_id = self.snapshot.get("matchId") or (self.latest_match or {}).get("id")
        self.open_match_review(match_id or "latest")

    def open_match_review(self, match_id):
        self.open_site(saved=True, path=f"/matches/{match_id}")

    def is_home(self):
        return self.snapshot.get("home", self.snapshot.get("phase", "offline") in HOME_PHASES)

    def current_preview_target(self):
        champion = self.champion_index.get(self.champion_input.text().strip().casefold())
        return champion, self.role_input.currentData()

    def update_preview_context(self):
        generation = self.snapshot.get("flowGeneration")
        account = ((self.snapshot.get("homeProfile") or {}).get("profile") or {}).get("riot")
        # The profile may be absent during a match or a temporary read failure.
        # Keep the last confirmed identity only within the same LCU generation.
        if not account and self.preview_session_context and generation == self.preview_session_context[0]:
            account = self.preview_session_context[1]
        context = generation, account
        if context == self.preview_session_context:
            return
        self.preview_session_context = context
        self.preview_revision += 1
        had_preview = bool(self.preview_options) or self.preview_job is not None
        self.preview_options = {}
        self.preview_choice = None
        if had_preview:
            self.set_preview_message(
                "Сессия клиента изменилась. Дождитесь завершения предыдущего запроса и загрузите сборку заново."
                if self.preview_job is not None else "Сессия клиента изменилась. Загрузите сборку заново.")

    def set_preview_message(self, text):
        self.preview_message.setText(text)
        self.preview_message.setVisible(bool(text))
        self.preview_hint.setVisible(not text)

    def preview_input_changed(self, *_args):
        if self.current_preview_target() != self.preview_target:
            self.preview_options = {}
            self.preview_choice = None
            self.set_preview_message(
                "Загружаем предыдущую сборку. Дождитесь завершения, затем нажмите «Показать сборку»."
                if self.preview_job is not None else "")
        elif self.preview_job is not None:
            self.set_preview_message("Загружаем сборку…")
        self.paint_snapshot()

    def request_preview(self):
        if not self.is_home() or self.preview_job is not None:
            return
        self.update_preview_context()
        target = self.current_preview_target()
        if not all(target):
            self.set_preview_message("Выберите чемпиона из списка и укажите роль.")
            return
        self.preview_options = {}
        self.preview_choice = None
        self.preview_target = target
        self.preview_patch = self.companion.catalog.get("patch")
        self.preview_request_revision = self.preview_revision
        self.set_preview_message("Загружаем сборку…")
        self.preview_job = self.preview_executor.submit(self.companion.preview_build, *target, include_specials=True)
        focused = self.preview_button.hasFocus()
        self.paint_snapshot()
        if focused:
            self.preview_action_focus = self.focusWidget()

    def finish_preview(self):
        if not self.preview_job or not self.preview_job.done():
            return
        self.update_preview_context()
        job, self.preview_job = self.preview_job, None
        previous_focus, self.preview_action_focus = self.preview_action_focus, None
        if self.preview_request_revision != self.preview_revision:
            self.set_preview_message("Сессия клиента изменилась. Нажмите «Показать сборку», чтобы загрузить новый вариант.")
        elif self.preview_target == self.current_preview_target():
            options = {}
            if self.preview_patch != self.companion.catalog.get("patch"):
                message = "Патч обновился. Загрузите сборку ещё раз."
            else:
                try:
                    options = job.result()
                    message = "" if options else "Для этой роли нет сборки на текущем патче."
                except SOURCE_ERRORS:
                    message = "Источник сборок временно недоступен. Попробуйте ещё раз."
            self.preview_options = options
            self.set_preview_message(message)
        else:
            self.set_preview_message("Выбор изменён. Нажмите «Показать сборку», чтобы загрузить новый вариант.")
        restore_focus = previous_focus is not None and self.focusWidget() is previous_focus
        self.paint_snapshot()
        if restore_focus and self.is_home() and self.isActiveWindow():
            self.preview_button.setFocus(Qt.FocusReason.OtherFocusReason)
            self.scroll.ensureWidgetVisible(self.preview_button)

    def choose_variant(self, choice):
        if self.is_home() and choice in self.preview_options:
            self.preview_choice = choice
            self.paint_snapshot()
        elif self.snapshot.get("phase") == "draft" and choice in self.snapshot.get("buildOptions", {}):
            self.choice = choice
            self.paint_snapshot()

    def choose_special_build(self, combo, index):
        if index >= 0:
            self.choose_variant(combo.itemData(index))

    def open_build_source(self):
        if source := (self.shown_build or {}).get("sourceUrl"):
            QDesktopServices.openUrl(QUrl(source))

    def paint_special_builds(self, options, choice, can_choose):
        groups = {self.otp_choice: {}, self.extra_build_choice: {}}
        for key, build in options.items():
            if key not in self.choices and build.get("title"):
                combo = self.otp_choice if key.startswith("otp:") else self.extra_build_choice
                groups[combo][key] = build
        for combo, builds in groups.items():
            with QSignalBlocker(combo):
                combo.populate(builds)
                combo.select_key(choice)
            combo.setVisible(can_choose and bool(builds))
            combo.setEnabled(self.export_job is None and not self.role_change_pending)
        self.build_source_button.setVisible(can_choose and bool((self.shown_build or {}).get("sourceUrl")))

    def import_build(self, *, spells_only=False):
        if (self.export_job is not None or self.role_change_pending
                or self.snapshot.get("phase") != "draft" or not self.snapshot.get("locked")):
            return
        button = self.spell_button if spells_only else self.import_button
        focused = button.hasFocus()
        draft_key = self.snapshot.get("draftKey")
        draft_id = draft_key[3] if draft_key else None
        self.set_notice("Импортируем…", draft_key=draft_key)
        self.export_job = self.executor.submit(
            self.companion.export, draft_key, self.choice, spells_only,
            revision=(self.shown_build or {}).get("revision", ""),
        )
        self.paint_snapshot()
        if focused:
            self.draft_action_focus = draft_id, button, self.focusWidget()

    def role_picker(self, side, slot):
        return next((card.role_icon for card in self.draft_screen.cards.get(side, [])
                     if card.data.get("roleSlot") == slot), None)

    def set_draft_role(self, side, slot, role):
        draft_id = (self.snapshot.get("draft") or {}).get("gameId")
        if (self.role_change_pending or self.export_job is not None or not draft_id or slot is None
                or self.snapshot.get("phase") not in DRAFT_PHASES):
            return
        picker = self.role_picker(side, slot)
        focused = picker and (picker.hasFocus() or picker.view().hasFocus() or picker.view().isVisible())
        self.role_change_pending = True
        self.job = self.executor.submit(self.companion.snapshot, home=True,
                                        role_change=(draft_id, side, slot, role))
        self.paint_snapshot()
        if focused:
            self.draft_action_focus = draft_id, (side, slot), self.focusWidget()

    def paint_draft_action_result(self):
        saved, self.draft_action_focus = self.draft_action_focus, None
        restore = saved and self.isActiveWindow() and self.focusWidget() is saved[2]
        self.paint_snapshot()
        if restore and saved[0] == (self.snapshot.get("draft") or {}).get("gameId"):
            target = self.role_picker(*saved[1]) if isinstance(saved[1], tuple) else saved[1]
            if target and target.isVisible() and target.isEnabled():
                target.setFocus(Qt.FocusReason.TabFocusReason)
                self.scroll.ensureWidgetVisible(target)

    def poll(self):
        self.finish_preview()
        if self.export_job:
            if not self.export_job.done():
                return
            job, self.export_job = self.export_job, None
            try:
                message = " · ".join(job.result()["results"])
            except SOURCE_ERRORS:
                message = "Клиент LoL временно недоступен."
            self.set_notice(message, draft_key=self.notice_draft_key)
            self.paint_draft_action_result()
        if self.job:
            if not self.job.done():
                return
            job, self.job = self.job, None
            previous = self.snapshot
            try:
                self.snapshot = job.result()
            except SOURCE_ERRORS:
                self.snapshot = {"phase": "offline"}
            role_changed, self.role_change_pending = self.role_change_pending, False
            if role_changed:
                self.paint_draft_action_result()
            elif self.snapshot != previous or self.champion_catalog is not self.companion.catalog:
                self.paint_snapshot()
        self.open_pending_review()
        self.job = self.executor.submit(self.companion.snapshot, home=True, history_limit=self.match_history.limit)

    def paint_snapshot(self):
        self.update_preview_context()
        phase = self.snapshot.get("phase")
        drafting = phase in DRAFT_PHASES
        if self.notice_draft_key is not None and (not drafting or self.notice_draft_key != self.snapshot.get("draftKey")):
            self.set_notice("")
        self.set_draft_active(drafting)
        if drafting:
            roster = self.snapshot.get("draft") or {}
            self.draft_screen.update_roster(roster)
            self.update_draft_layout()
            can_change_role = (bool(roster.get("gameId")) and not self.snapshot.get("draftInterrupted")
                               and not self.role_change_pending and self.export_job is None)
            for cards in self.draft_screen.cards.values():
                for card in cards:
                    card.role_icon.setEnabled(can_change_role)
        else:
            self.import_timer.hide()
        home = self.is_home()
        self.update_champion_index()
        self.set_home_active(home)
        self.preview_button.setEnabled(self.preview_job is None)
        if home:
            self.home_connection.setText(HOME_CONNECTION.get(phase, "Клиент LoL подключён"))
            self.latest_match = self.snapshot.get("latestMatch")
            profile = self.snapshot.get("homeProfile") or {}
            self.dashboard.populate(profile)
            self.match_history.populate(profile.get("matches", []), profile.get("historyAvailable", False),
                                        profile.get("historyHasMore", False))
        options = self.preview_options if home else self.snapshot.get("buildOptions", {})
        draft_key = self.snapshot.get("draftKey")
        generation = self.snapshot.get("flowGeneration")
        if (generation != self.flow_generation or draft_key is not None and draft_key != self.draft_key
                or draft_key is None and phase not in {"game", "ended"}):
            self.flow_generation, self.draft_key = generation, draft_key
            self.choice = self.draft_build = None
        choice = self.preview_choice if home else self.choice
        if options and choice not in options:
            choice = next(iter(options))
            if home:
                self.preview_choice = choice
            else:
                self.choice = choice
        build = options.get(choice) or (None if home else self.snapshot.get("build"))
        if drafting:
            self.draft_build = build
        self.match_build = None
        if phase == "game" and draft_key is not None:
            if self.draft_build is None:
                self.draft_build = build
            self.match_build = build = self.draft_build
        self.stage.setText(PHASE_LABELS.get(phase, "ЛОББИ"))
        if build:
            context = f"{build['role']}  ·  Патч {build['patch']}  ·  {build['source']}"
            self.headline.setText(build["champion"])
            self.status.setText(context)
            if home:
                self.preview_champion.setText(build["champion"])
                self.preview_context.setText(context)
        else:
            self.headline.setText(PHASES.get(phase, "Ожидаем драфт Solo/Duo"))
            self.status.clear()
        self.hero.setVisible(not home and not drafting)
        self.game_header.setVisible(not home)
        self.status.setVisible(bool(self.status.text()))
        self.workspace.setVisible(home)
        self.build_elsewhere.parentWidget().setVisible(not home and not drafting and bool(build))
        self.preview_placeholder.setVisible(home and not build)
        self.preview_hero.setVisible(home and bool(build))
        self.build_heading.setVisible(not home and not drafting)
        self.build_panel.setVisible(bool(build))
        if drafting:
            details = "" if build else self.headline.text()
            if self.snapshot.get("draftInterrupted"):
                details = "Связь с клиентом LoL прервалась. Импорт приостановлен."
            self.draft_screen.show_tab(self.draft_screen.tab, details)
        if build != self.shown_build:
            self.shown_build = build
            self.render_art()
        self.paint_build_controls(build, options, choice, home=home, phase=phase)
        self.review_button.setVisible(bool(self.snapshot.get("matchId")) and not home)
        self.open_pending_review()
        self.overlays.update_match(phase == "game" or phase in PLAYING, {"build": self.match_build})

    def paint_build_controls(self, build, options, choice, *, home, phase):
        can_choose = home or phase == "draft"
        self.paint_special_builds(options, choice, can_choose)
        self.item_heading.setText((build or {}).get("itemHeading") or "Порядок покупки")
        equipped = {item["id"] for item in (build or {}).get("items", [])}
        alternates = [f"{item['name']} · {item['reason']}" for item in self.snapshot.get("situationalItems", [])
                     if item["id"] not in equipped]
        self.situational.setText("Ситуативно\n" + "\n".join(alternates) if alternates else "")
        self.situational.setVisible(phase in DRAFT_PHASES and bool(alternates))
        sample = build.get("sample") if build else None
        rate = build.get("winRate") if build else None
        stats = ""
        if sample and rate is not None:
            count = f"{sample:,}".replace(",", " ")
            percentage = f"{rate:.1f}".replace(".", ",")
            stats = f"{percentage}% побед · игр: {count}"
        self.stats.setText(stats)
        self.stats.setToolTip((build or {}).get("source", ""))
        self.stats.setVisible(bool(stats))
        spells = build.get("spellNames", []) if build else []
        can_import = bool(self.snapshot.get("locked")) and self.export_job is None and not self.role_change_pending
        for key, button in self.choices.items():
            button.setChecked(choice == key)
            button.setVisible(can_choose and len(options) > 1 and key in options)
            button.setEnabled(self.export_job is None and not self.role_change_pending)
            button.setToolTip((options.get(key) or {}).get("source", ""))
        self.import_button.setVisible(phase == "draft")
        self.import_button.setEnabled(can_import)
        can_import_runes = (build or {}).get("canImportRunes", True)
        self.import_button.setText("Импортировать руны и предметы" if can_import_runes else "Импортировать предметы")
        lock_hint = "Зафиксируйте чемпиона в клиенте LoL, чтобы применить сборку."
        awaiting_lock = phase == "draft" and not self.snapshot.get("locked") and not self.snapshot.get("draftInterrupted")
        self.import_hint.setText(lock_hint if awaiting_lock else "")
        self.import_hint.setVisible(awaiting_lock)
        self.import_button.setToolTip(lock_hint if awaiting_lock else (
            "" if can_import_runes else "В истории матча нет осколков для импорта рун."))
        self.spell_button.setToolTip(lock_hint if awaiting_lock else "")
        self.spell_button.setVisible(phase == "draft" and bool(spells))
        self.spell_button.setEnabled(can_import)

    def open_pending_review(self):
        match_id = self.snapshot.get("matchId")
        if (not self.auto_open_review or not match_id or not self.snapshot.get("postGameReady")
                or match_id == self.auto_review_opened):
            return
        address = self.settings.value("site", "", type=str).strip()
        if not address:
            return
        now = monotonic()
        key = match_id, address
        if self.auto_review_retry and self.auto_review_retry[0] == key and now < self.auto_review_retry[1]:
            return
        if self.open_site(saved=True):
            self.auto_review_opened = match_id
            self.auto_review_retry = None
        else:
            self.auto_review_retry = key, now + REVIEW_RETRY_SECONDS

    def render_art(self):
        build = self.shown_build or {}
        champion = build.get("championKey")
        version = build.get("assetVersion")
        splash = f"{DDRAGON}/cdn/img/champion/splash/{champion}_0.jpg" if champion else None
        art = self.artwork.image(splash)
        self.hero.set_art(art)
        self.preview_hero.set_art(art)
        items = build.get("items", [])
        for index, (tile, icon, name) in enumerate(self.item_slots):
            if index >= len(items):
                tile.hide()
                continue
            item = items[index]
            name.setText(item["name"])
            tile.setToolTip(item["name"])
            tile.show()
            url = f"{DDRAGON}/cdn/{version}/img/item/{item['id']}.png" if version else None
            self.artwork.set_icon(icon, item["name"], url)
        self.render_loadout(build, version or self.loadout_catalog["version"])

    def render_loadout(self, build, version):
        runes = build.get("runes", [])
        shards = build.get("shards", [])
        spell_names = build.get("spellNames", [])
        spell_ids = build.get("spellIds", [])
        rune_catalog = self.loadout_catalog["runes"]
        spell_catalog = self.loadout_catalog["spells"]
        for icons, ids in zip(self.rune_icons, (runes[:4], runes[4:6], shards[:3])):
            for index, icon in enumerate(icons):
                icon.setVisible(index < len(ids))
                if index < len(ids):
                    rune = rune_catalog.get(str(ids[index]))
                    title = rune["name"] if rune else f"Руна {ids[index]}"
                    url = f"{DDRAGON}/cdn/img/{rune['image']}" if rune else None
                    self.artwork.set_icon(icon, title, url)
        for index, (cell, icon, name) in enumerate(self.spell_icons):
            cell.setVisible(index < len(spell_names))
            if index < len(spell_names):
                spell = spell_catalog.get(str(spell_ids[index])) if index < len(spell_ids) else None
                title = spell["name"] if spell else spell_names[index]
                name.setText(title)
                url = f"{DDRAGON}/cdn/{version}/img/spell/{spell['image']}" if spell else None
                self.artwork.set_icon(icon, title, url)
        self.runes.setVisible(bool(runes or shards))
        self.spells.setVisible(bool(spell_names))
        self.loadout_panel.setVisible(bool(runes or shards or spell_names))

    def closeEvent(self, event):
        self.timer.stop()
        self.assistant.close()
        self.updates_page.close()
        self.automation.close()
        self.overlays.close()
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.preview_executor.shutdown(wait=False, cancel_futures=True)
        self.companion.close()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    window = Window()
    if error := last_update_error():
        window.show_home_page("updates")
        window.updates_page.status.setText(f"Обновление не установлено. {error}")
    window.show()
    confirm_startup()
    if "--smoke" in sys.argv:
        QTimer.singleShot(2000, window.close)
    return app.exec()


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--apply-update":
        raise SystemExit(apply_update(sys.argv[2]))
    raise SystemExit(main())
