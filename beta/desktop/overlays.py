"""Match overlays and their shared desktop and in-game controls."""
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
import sys
import base64

from PySide6.QtCore import QBuffer, QIODevice, QEvent, QObject, QPoint, QRect, QSignalBlocker, Qt, QTimer, QUrl
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QGridLayout, QHBoxLayout, QPushButton, QScrollArea, QSlider, QToolTip,
    QVBoxLayout, QWidget,
)

from worker import DDRAGON, foreground_game
from qt_ui import native
from overlay_samples import SampleCard, ScoreboardDecoration
from overlay_tab import TabFrameFinder
from overlay_themes import DEFAULT_THEME, MAX_SCALE, MIN_SCALE, THEMES, ThemePanel, asset_folder
from widgets import icon_label, label, panel


class IconGrid(QWidget):
    def __init__(self, artwork, size, columns, role="icon"):
        super().__init__()
        self.artwork = artwork
        self.base_size = self.icon_size = size
        self.columns = columns
        self.role = role
        self.assets = []
        self.icons = []
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(4)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

    def set_assets(self, assets):
        self.assets = list(assets)
        while len(self.icons) < len(self.assets):
            row, col = divmod(len(self.icons), self.columns)
            icon = icon_label(self.icon_size, self.role)
            self.icons.append(icon)
            self.grid.addWidget(icon, row, col)
        for index, icon in enumerate(self.icons):
            icon.setVisible(index < len(self.assets))
        self.setVisible(bool(self.assets))
        self.paint_icons()

    def paint_icons(self):
        for icon, (title, url) in zip(self.icons, self.assets):
            self.artwork.set_icon(icon, title, url)

    def set_scale(self, scale):
        self.icon_size = round(self.base_size * scale)
        self.grid.setSpacing(round(4 * scale))
        for icon in self.icons:
            icon.setFixedSize(self.icon_size, self.icon_size)
        self.paint_icons()


class BuildCard(QWidget):
    def __init__(self, artwork, catalog, *, demo=False):
        super().__init__()
        self.catalog = catalog
        self.demo = demo
        self.demo_assets = asset_folder("overlay-preview")
        self.bundled = demo
        self.portrait = IconGrid(artwork, 48, 1)
        self.spells = IconGrid(artwork, 22, 2)
        self.items = IconGrid(artwork, 30, 6)
        self.runes = IconGrid(artwork, 20, 6, "overlayRune")
        self.shards = IconGrid(artwork, 16, 3, "overlayRune")
        self.icon_groups = self.portrait, self.spells, self.items, self.runes, self.shards

        left = QVBoxLayout()
        self.left = left
        left.addWidget(self.portrait)
        left.addWidget(self.spells)
        left.addStretch()
        self.perks = QWidget()
        perks = QHBoxLayout(self.perks)
        self.perk_layout = perks
        perks.setContentsMargins(0, 0, 0, 0)
        perks.addWidget(self.runes, alignment=Qt.AlignmentFlag.AlignVCenter)
        perks.addWidget(self.shards, alignment=Qt.AlignmentFlag.AlignVCenter)
        perks.addStretch()
        right = QVBoxLayout()
        self.right = right
        right.addWidget(self.items)
        right.addStretch()
        right.addWidget(self.perks)

        frame = self.frame = ThemePanel()
        contents = QHBoxLayout(frame)
        self.contents = contents
        contents.addLayout(left)
        contents.addLayout(right, 1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(frame)
        self.set_appearance(THEMES[DEFAULT_THEME], 1)
        artwork.changed.connect(self.paint_icons)

    def set_appearance(self, theme, scale):
        self.frame.set_theme(theme)
        self.setFixedWidth(round(300 * scale))
        self.contents.setContentsMargins(round(14 * scale), round(12 * scale), round(14 * scale), round(12 * scale))
        self.contents.setSpacing(round(12 * scale))
        self.left.setSpacing(round(4 * scale))
        self.right.setSpacing(round(6 * scale))
        self.perk_layout.setSpacing(round(6 * scale))
        for group in self.icon_groups:
            group.set_scale(scale)

    def asset(self, path):
        if self.bundled:
            return QUrl.fromLocalFile(str(self.demo_assets / path.rsplit("/", 1)[-1])).toString()
        return f"{DDRAGON}/cdn/{path}"

    def set_content(self, build):
        self.bundled = self.demo or build.get("example", False)
        version = build.get("assetVersion") or self.catalog["version"]
        champion = build.get("championKey")
        self.portrait.set_assets([(build["champion"], self.asset(f"{version}/img/champion/{champion}.png") if champion else None)])
        self.items.set_assets((item["name"], self.asset(f"{version}/img/item/{item['id']}.png") if item.get("id") else None)
                              for item in build.get("items", []))
        spell_catalog = self.catalog["spells"]
        spell_ids = build.get("spellIds", [])
        spells = []
        for index, name in enumerate(build.get("spellNames", [])):
            spell = spell_catalog.get(str(spell_ids[index])) if index < len(spell_ids) else None
            spells.append((spell["name"], self.asset(f"{version}/img/spell/{spell['image']}")) if spell else (name, None))
        self.spells.set_assets(spells)
        for key, grid in (("runes", self.runes), ("shards", self.shards)):
            entries = ((rune_id, self.catalog["runes"].get(str(rune_id))) for rune_id in build.get(key, []))
            grid.set_assets((rune["name"], self.asset(f"img/{rune['image']}")) if rune else (f"Руна {rune_id}", None)
                            for rune_id, rune in entries)
        self.perks.setVisible(bool(self.runes.assets or self.shards.assets))

    def paint_icons(self):
        for group in self.icon_groups:
            group.paint_icons()

    def event(self, event):
        if event.type() == QEvent.Type.DevicePixelRatioChange:
            self.paint_icons()
        return super().event(event)


@dataclass(frozen=True)
class OverlaySpec:
    key: str
    title: str
    description: str
    card: Callable[..., QWidget]
    sample: dict
    default_position: tuple[float, float] | None = None
    preview_only: bool = False
    attached: bool = False


OVERLAYS = (
    OverlaySpec("advice", "Текст помощника", "Фразы, выбранные в настройках помощника.",
                partial(SampleCard, kind="metrics"), {"title": "Подсказка", "lines": ["Пример текстовой подсказки"]}, (.5, .75)),
    OverlaySpec(
        "build", "Сборка в матче", "Предметы по порядку покупки, заклинания и руны из драфта.",
        BuildCard, {"example": True, "champion": "Виктор", "championKey": "Viktor", "items": [
            {"id": 3020, "name": "Сапоги чародея"}, {"id": 3100, "name": "Гроза личей"},
            {"id": 4645, "name": "Пламя Тьмы"}, {"id": 3089, "name": "Смертельная шляпа Рабадона"},
            {"id": 3135, "name": "Посох Бездны"}, {"id": 3157, "name": "Песочные часы Жони"},
        ], "spellIds": [4, 12], "spellNames": ["Скачок", "Телепорт"],
            "runes": [8230, 8226, 8210, 8237, 8304, 8345], "shards": [5008, 5008, 5001]},
    ),
    OverlaySpec("metrics", "Темп игры", "Фарм, наличное золото, KDA и уровень текущего игрока.",
                partial(SampleCard, kind="metrics"), {}, (.815, .18), preview_only=False),
    OverlaySpec("lane", "Золото на линии", "Разница стоимости предметов с соперником известной роли.",
                partial(SampleCard, kind="lane"), {}, (.815, .39), preview_only=False),
    OverlaySpec("standings", "Стоимость предметов", "Десять чемпионов по стоимости предметов, от большей к меньшей.",
                partial(SampleCard, kind="standings"), {}, (.04, .31), preview_only=False),
    OverlaySpec("purchase", "До покупки", "Следующий предмет сборки: полная цена и наличные, без вычета компонентов.",
                partial(SampleCard, kind="purchase"), {}, (.815, .60), preview_only=False),
    OverlaySpec("objectives", "События объектов", "Время с последнего подтверждённого события объекта.",
                partial(SampleCard, kind="objectives"), {}, (.55, .06), preview_only=False),
    OverlaySpec("tab", "Перевес в Tab", "Полоска над игровой таблицей и разница по золоту между соперниками.",
                partial(SampleCard, kind="tab"), {}, attached=True),
)


class OverlaySurface(QWidget):
    def __init__(self, title, content):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setWindowTitle("LoL Helper · " + title)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(content)

    def set_interactive(self, interactive):
        if native.IS_WIN:
            native.styles(self, not interactive)
        else:
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, not interactive)

    def present(self, area, position=None):
        visible = native.place_overlay(self, area, self.sizeHint(), position)
        self.setVisible(visible)


class OverlayCard(OverlaySurface):
    def __init__(self, spec, settings, artwork, catalog):
        self.card = spec.card(artwork, catalog)
        super().__init__(spec.title, self.card)
        self.settings = settings
        self.default_position = spec.default_position
        self.position_key = f"overlays/{spec.key}/position"
        saved = settings.value(self.position_key)
        self.position = (tuple(saved) if isinstance(saved, (list, tuple)) and len(saved) == 2
                         and all(isinstance(value, (float, int)) and 0 <= value <= 1 for value in saved) else None)
        self.content = None
        self.drag_offset = None
        self.editing = False
        self.set_interactive(False)

    def set_content(self, content):
        if content != self.content:
            self.content = content
            if content is not None:
                self.card.set_content(content)

    def set_editing(self, editing):
        if self.editing == editing:
            return
        self.editing = editing
        if not editing:
            self.finish_drag()
        self.set_interactive(editing)
        self.setCursor(Qt.CursorShape.SizeAllCursor if editing else Qt.CursorShape.ArrowCursor)

    def mousePressEvent(self, event):
        if self.editing and event.button() == Qt.MouseButton.LeftButton:
            self.drag_offset = native.cursor() - QPoint(*native.geometry(self)[:2])
            event.accept()
        else:
            super().mousePressEvent(event)

    def finish_drag(self):
        if self.drag_offset is not None:
            self.drag_offset = None
            if self.position is not None:
                self.settings.setValue(self.position_key, list(self.position))

    def present_card(self, area):
        if self.drag_offset is not None:
            if self.editing and native.primary_mouse_down():
                point = native.cursor() - self.drag_offset - area.topLeft()
                _, _, width, height = native.geometry(self)
                self.position = (
                    min(1, max(0, point.x() / max(1, area.width() - width))),
                    min(1, max(0, point.y() / max(1, area.height() - height))),
                )
            else:
                self.finish_drag()
        super().present(area, self.position or self.default_position)


def tab_values(live, detected):
    """Use recognized screen columns, never fixed role order or assumed sides."""
    by_champion = {p["c"]: p for p in live["players"]}
    own_left = detected["teams"][0] == live["myTeam"]
    gold = [sum(p["gold"] for p in live["players"] if p["team"] == team) for team in detected["teams"]]
    differences = []
    for left, right in zip(*detected["columns"]):
        a, b = by_champion.get(left), by_champion.get(right)
        differences.append((a["gold"] - b["gold"]) * (1 if own_left else -1) if a and b else None)
    return {"gold": gold, "ownLeft": own_left, "differences": differences,
            "columns": detected["columns"]}


class ScoreboardSurface(OverlaySurface):
    def __init__(self):
        self.decoration = ScoreboardDecoration()
        super().__init__("Перевес в Tab", self.decoration)
        self.set_interactive(False)

    def attach(self, area, bounds, frame, theme, scale):
        x0, body_top, x1, bottom, top = frame
        x, y = bounds["x"] + x0, bounds["y"] + top
        for _ in range(2):
            ratio = self.devicePixelRatioF()
            bar = min(round(33 * scale * ratio), y - area.top())
            target = QRect(x, y - bar, x1 - x0, bottom - top + bar)
            if bar < 16 or not area.contains(target):
                self.hide()
                return
            self.resize(round(target.width() / ratio), round(target.height() / ratio))
            if native.geometry(self) == target.getRect():
                break
            try:
                native.move(self, *target.getRect())
            except OSError:
                self.hide()
                return
        self.decoration.theme = theme
        self.decoration.scale = scale
        self.decoration.bar = bar / ratio
        self.decoration.header = (body_top - top + bar) / ratio
        self.decoration.rows = (bottom - body_top) / ratio
        self.decoration.update()
        self.show()


class OverlayControls(QObject):
    def __init__(self, parent, settings, artwork, catalog, *, probe=False):
        super().__init__(parent)
        self.settings = settings
        self.probe = probe
        self.previewing = probe
        self.match_active = False
        self.match_contents = {}
        self.artwork = artwork
        self.tab_portraits = {}
        self.tab_status = {"state": "hidden"}
        self.theme_id = settings.value("overlays/theme", DEFAULT_THEME, type=str)
        if self.theme_id not in THEMES:
            self.theme_id = DEFAULT_THEME
        self.scale_percent = min(MAX_SCALE, max(MIN_SCALE, settings.value("overlays/scale", 100, type=int)))
        self.objective_phase = 0
        self.last_probe = None
        self.editing = False
        self.cards = {}
        self.desktop = {}
        self.in_game = {}
        self.samples = {}
        self.tab_finder = TabFrameFinder()
        self.scoreboard = ScoreboardSurface()
        indicator = self.indicator_skin = ThemePanel()
        contents = QVBoxLayout(indicator)
        contents.setContentsMargins(11, 5, 11, 5)
        contents.addWidget(label("Предпросмотр · пример данных", "captionStrong"))
        self.preview_indicator = OverlaySurface("Предпросмотр", indicator)
        self.preview_indicator.set_interactive(False)

        self.preferences, desktop_layout = panel()
        desktop_layout.addWidget(label("Оверлеи", "section"))
        desktop_layout.addWidget(label("В игре удерживайте Alt, чтобы открыть настройки или переместить карточку.", "caption", wrap=True))
        self.desktop_theme = QComboBox()
        self.desktop_theme.setAccessibleName("Тема оверлеев")
        for key, theme in THEMES.items():
            self.desktop_theme.addItem(theme.name, key)
        desktop_layout.addLayout(self.setting_row("Тема", self.desktop_theme))
        self.desktop_scale, self.desktop_percent, desktop_slider = self.scale_controls()
        desktop_layout.addLayout(desktop_slider)
        self.desktop_preview = QCheckBox("Предпросмотр в игре")
        self.desktop_preview.setToolTip("Показывает примерные данные поверх матча или тренировки.")
        desktop_layout.addWidget(label("Действующие в матче", "captionStrong"))
        self.laboratory = QWidget()
        laboratory_layout = QVBoxLayout(self.laboratory)
        laboratory_layout.setContentsMargins(0, 0, 0, 0)
        laboratory_layout.addWidget(label(
            "Примеры оформления с демонстрационными данными. Они не анализируют текущий матч. "
            "Включите предпросмотр, чтобы показать примеры поверх игры или тренировки.", "caption", wrap=True))
        laboratory_layout.addWidget(self.desktop_preview)
        self.laboratory.hide()
        self.laboratory_toggle = QPushButton("Лаборатория · демо оверлеев +")
        self.laboratory_toggle.setProperty("role", "tab")
        self.laboratory_toggle.setCheckable(True)
        self.laboratory_toggle.setAccessibleName("Открыть лабораторию демонстрационных оверлеев")
        self.laboratory_toggle.toggled.connect(self.laboratory.setVisible)
        self.laboratory_toggle.toggled.connect(lambda expanded: self.laboratory_toggle.setText(
            "Лаборатория · демо оверлеев −" if expanded else "Лаборатория · демо оверлеев +"))

        drawer_panel = self.drawer_skin = ThemePanel()
        drawer_layout = QVBoxLayout(drawer_panel)
        drawer_layout.setContentsMargins(12, 11, 12, 11)
        drawer_layout.setSpacing(8)
        drawer_panel.setFixedWidth(140)
        drawer_body = QWidget()
        drawer_controls = QVBoxLayout(drawer_body)
        drawer_controls.setContentsMargins(0, 0, 0, 0)
        drawer_controls.setSpacing(7)
        self.game_theme = label("", "captionStrong")
        self.game_theme.setAlignment(Qt.AlignmentFlag.AlignCenter)
        themes = QHBoxLayout()
        themes.setSpacing(4)
        for text, direction, name in (("‹", -1, "Предыдущая тема"), ("›", 1, "Следующая тема")):
            change = QPushButton(text)
            change.setAccessibleName(name)
            change.setProperty("automationId", "game_overlay_theme_previous" if direction == -1 else "game_overlay_theme_next")
            change.setFixedWidth(34)
            change.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            change.clicked.connect(lambda _checked=False, step=direction: self.cycle_theme(step))
            if direction == 1:
                themes.addWidget(self.game_theme, 1)
            themes.addWidget(change)
        drawer_controls.addLayout(themes)
        self.game_scale, self.game_percent, drawer_slider = self.scale_controls()
        self.game_scale.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        drawer_controls.addLayout(drawer_slider)
        self.game_preview = QPushButton()
        self.game_preview.setCheckable(True)
        self.game_preview.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        drawer_controls.addWidget(self.game_preview)
        self.objective_preview = QPushButton("Сменить объект")
        self.objective_preview.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.objective_preview.clicked.connect(self.next_objective)
        drawer_controls.addWidget(self.objective_preview)

        self.drawer_rows = QWidget()
        self.drawer_rows.setObjectName("overlayRows")
        drawer_checkboxes = QVBoxLayout(self.drawer_rows)
        drawer_checkboxes.setContentsMargins(0, 2, 0, 2)
        self.drawer_scroll = QScrollArea()
        self.drawer_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.drawer_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.drawer_scroll.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.drawer_scroll.setWidgetResizable(True)
        self.drawer_scroll.setWidget(self.drawer_rows)
        drawer_controls.addWidget(self.drawer_scroll)
        drawer_body.hide()
        self.drawer_header = QPushButton("Оверлеи ▾")
        self.drawer_header.setCheckable(True)
        self.drawer_header.setCursor(Qt.CursorShape.PointingHandCursor)
        self.drawer_header.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        def expand_drawer(expanded):
            drawer_panel.setFixedWidth(274 if expanded else 140)
            self.drawer_header.setText("Оверлеи ▴" if expanded else "Оверлеи ▾")
            drawer_body.setVisible(expanded)

        self.drawer_header.toggled.connect(expand_drawer)
        drawer_layout.addWidget(self.drawer_header)
        drawer_layout.addWidget(drawer_body)
        self.drawer = OverlaySurface("Настройки оверлеев", drawer_panel)
        self.drawer.set_interactive(True)

        demo_heading_shown = False
        for spec in OVERLAYS:
            if spec.preview_only and not demo_heading_shown:
                demo_heading_shown = True
                desktop_layout.addWidget(self.laboratory_toggle)
                desktop_layout.addWidget(self.laboratory)
                drawer_checkboxes.addWidget(label("Только демонстрация", "captionStrong"))
            if not spec.attached:
                self.cards[spec.key] = OverlayCard(spec, settings, artwork, catalog)
            title = f"{spec.title} · демо" if spec.preview_only else spec.title
            desktop_toggle = QCheckBox(title)
            game_toggle = QCheckBox(title)
            if spec.preview_only:
                for toggle in (desktop_toggle, game_toggle):
                    toggle.setToolTip("Только демонстрация. Игровые данные не подключены. Включите предпросмотр.")
            game_toggle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self.desktop[spec.key] = desktop_toggle
            self.in_game[spec.key] = game_toggle
            setting = settings.value("overlay", True, type=bool) if spec.key == "build" else True
            enabled = settings.value(f"overlays/{spec.key}/enabled", setting, type=bool)

            preview = spec.card(artwork, catalog, demo=True)
            preview.set_content(spec.sample)
            self.samples[spec.key] = preview
            setting_panel, setting_layout = panel("tile")
            setting_layout.addWidget(desktop_toggle)
            if spec.preview_only:
                setting_layout.addWidget(label("Только демонстрация · нет игровых данных", "caption", wrap=True))
            setting_layout.addWidget(label(spec.description, "caption", wrap=True))
            laboratory_layout.addWidget(label(spec.title, "captionStrong"))
            laboratory_layout.addWidget(preview, alignment=Qt.AlignmentFlag.AlignLeft)
            (laboratory_layout if spec.preview_only else desktop_layout).addWidget(setting_panel)
            drawer_checkboxes.addWidget(game_toggle)
            for toggle in (desktop_toggle, game_toggle):
                toggle.setChecked(enabled and (self.previewing or not spec.preview_only))
                toggle.toggled.connect(lambda checked, key=spec.key: self.set_enabled(key, checked))

        desktop_layout.addWidget(self.laboratory_toggle)
        desktop_layout.addWidget(self.laboratory)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.sync)
        self.refresh_appearance()
        self.refresh_preview_controls()
        self.desktop_theme.currentIndexChanged.connect(lambda index: self.set_theme(self.desktop_theme.itemData(index)))
        self.desktop_scale.valueChanged.connect(self.set_scale)
        self.game_scale.valueChanged.connect(self.set_scale)
        self.desktop_preview.toggled.connect(self.set_preview)
        self.game_preview.toggled.connect(self.set_preview)

    @staticmethod
    def setting_row(title, widget):
        row = QHBoxLayout()
        row.addWidget(label(title, "captionStrong"))
        row.addWidget(widget, 1)
        return row

    def scale_controls(self):
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setAccessibleName("Масштаб оверлеев")
        slider.setRange(MIN_SCALE, MAX_SCALE)
        slider.setSingleStep(5)
        slider.setPageStep(10)
        row = self.setting_row("Масштаб", slider)
        value = label("", "captionStrong")
        value.setFixedWidth(40)
        value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(value)
        return slider, value, row

    def cycle_theme(self, direction):
        keys = tuple(THEMES)
        self.set_theme(keys[(keys.index(self.theme_id) + direction) % len(keys)])

    def set_theme(self, key):
        if key in THEMES and key != self.theme_id:
            self.theme_id = key
            self.settings.setValue("overlays/theme", key)
            self.refresh_appearance()
            self.sync()

    def set_scale(self, value):
        if value != self.scale_percent:
            self.scale_percent = value
            self.settings.setValue("overlays/scale", value)
            self.refresh_appearance()
            self.sync()

    def refresh_appearance(self):
        theme = THEMES[self.theme_id]
        scale = self.scale_percent / 100
        self.drawer_skin.set_theme(theme)
        self.indicator_skin.set_theme(theme)
        self.drawer_rows.setStyleSheet(f"QWidget#overlayRows {{ background: {theme.base}; }}")
        self.game_theme.setText(theme.name)
        self.game_theme.setStyleSheet(f"color: {theme.light};")
        with QSignalBlocker(self.desktop_theme):
            self.desktop_theme.setCurrentIndex(self.desktop_theme.findData(self.theme_id))
        for slider in (self.desktop_scale, self.game_scale):
            slider.setStyleSheet(f"""
                QSlider::groove:horizontal {{ height: 4px; background: #43384f; border-radius: 2px; }}
                QSlider::sub-page:horizontal {{ background: {theme.shadow}; border-radius: 2px; }}
                QSlider::handle:horizontal {{
                    width: 13px; margin: -5px 0; border: 1px solid #fcf8ff;
                    border-radius: 7px; background: {theme.light};
                }}
            """)
            with QSignalBlocker(slider):
                slider.setValue(self.scale_percent)
        for value in (self.desktop_percent, self.game_percent):
            value.setText(f"{self.scale_percent}%")
        for card in self.cards.values():
            card.card.set_appearance(theme, scale)
        for sample in self.samples.values():
            sample.set_appearance(theme, scale)

    def refresh_preview_controls(self):
        for toggle in (self.desktop_preview, self.game_preview):
            with QSignalBlocker(toggle):
                toggle.setChecked(self.previewing)
        self.game_preview.setText("Завершить предпросмотр" if self.previewing else "Предпросмотр")
        self.objective_preview.setVisible(self.previewing)
        for spec in OVERLAYS:
            if spec.preview_only:
                enabled = self.previewing and self.settings.value(f"overlays/{spec.key}/enabled", True, type=bool)
                for toggle in (self.desktop[spec.key], self.in_game[spec.key]):
                    with QSignalBlocker(toggle):
                        toggle.setChecked(enabled)
                    toggle.setEnabled(self.previewing)

    def set_preview(self, enabled):
        self.previewing = enabled
        self.refresh_preview_controls()
        self.update_match(self.match_active, self.match_contents)

    def next_objective(self):
        self.objective_phase = (self.objective_phase + 1) % 3
        for widget in (self.cards["objectives"].card, self.samples["objectives"]):
            widget.phase = self.objective_phase
            widget.update()

    def set_enabled(self, key, enabled):
        if not self.previewing and any(spec.key == key and spec.preview_only for spec in OVERLAYS):
            return
        self.settings.setValue(f"overlays/{key}/enabled", enabled)
        for toggle in (self.desktop[key], self.in_game[key]):
            with QSignalBlocker(toggle):
                toggle.setChecked(enabled)
        self.sync()

    def update_match(self, active, contents):
        self.match_active, self.match_contents = active, contents
        for spec in OVERLAYS:
            if not spec.attached:
                if self.previewing:
                    content = spec.sample
                else:
                    content = None if spec.preview_only else contents.get(spec.key)
                self.cards[spec.key].set_content(content)
        if active or self.probe or self.previewing:
            if not self.timer.isActive():
                self.timer.start(75)
        else:
            self.timer.stop()
        self.sync()

    def sync(self):
        bounds = foreground_game() if self.timer.isActive() else None
        area = native.overlay_area(bounds) if bounds else None
        has_area = area is not None and not area.isEmpty()
        editing = has_area and native.overlay_edit_key()
        raise_drawer = editing and not self.editing
        if editing != self.editing:
            if not editing:
                QToolTip.hideText()
            self.editing = editing
            self.timer.setInterval(25 if editing else 75)
        for key, card in self.cards.items():
            visible = has_area and card.content is not None and self.desktop[key].isChecked()
            if key == "tab" and not self.previewing:
                visible = visible and native.scoreboard_key()
            card.set_editing(editing and visible)
            if visible:
                was_visible = card.isVisible()
                card.present_card(area)
                raise_drawer |= editing and not was_visible and card.isVisible()
            else:
                card.hide()
        live = (self.match_contents.get("tab") or {}).get("visual")
        show_tab = has_area and (self.previewing or self.match_active and live) and self.desktop["tab"].isChecked() and native.scoreboard_key()
        tab_bounds = tuple(bounds[key] for key in ("x", "y", "width", "height")) if show_tab else None
        portraits = None
        players = None
        session = None
        if show_tab and not self.previewing:
            players = live["players"]
            session = live.get("session")
            portraits = {}
            for player in players:
                key = player["c"]
                url = f"{DDRAGON}/cdn/{live['version']}/img/champion/{key}.png"
                if url not in self.tab_portraits:
                    image = self.artwork.image(url)
                    if not image.isNull():
                        buffer = QBuffer()
                        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
                        image.save(buffer, "PNG")
                        self.tab_portraits[url] = base64.b64encode(bytes(buffer.data())).decode("ascii")
                if url in self.tab_portraits:
                    portraits[key] = self.tab_portraits[url]
        detected = self.tab_finder.update(tab_bounds, portraits, players, session)
        frame = detected.get("frame") if isinstance(detected, dict) else detected
        self.scoreboard.decoration.live = None
        self.tab_status = {"state": "searching" if show_tab else "hidden"}
        if show_tab and not self.previewing and isinstance(detected, dict):
            values = tab_values(live, detected)
            self.scoreboard.decoration.live = values
            self.tab_status = dict(values, state="attached", frame=list(frame), confidence=detected["confidence"])
        if show_tab and frame:
            self.scoreboard.attach(area, bounds, frame, THEMES[self.theme_id], self.scale_percent / 100)
            if not self.scoreboard.isVisible():
                self.tab_status = {"state": "searching", "reason": "Рамка находится за доступной областью окна."}
        else:
            self.scoreboard.hide()
        if has_area and self.previewing:
            self.preview_indicator.present(area, (.5, .012))
        else:
            self.preview_indicator.hide()
        if editing:
            height = round(area.height() / self.drawer.devicePixelRatioF())
            available = max(32, height - 245)
            self.drawer_scroll.setFixedHeight(min(235, available, self.drawer_rows.sizeHint().height()))
            self.drawer.present(area, (1, 0.24))
            if raise_drawer:
                self.drawer.raise_()
        else:
            self.drawer.hide()
        if self.probe and sys.stdout:
            result = {"foregroundGame": bounds, "overlayVisible": self.visible(), "editing": editing}
            if result != self.last_probe:
                print(result, flush=True)
                self.last_probe = result

    def visible(self):
        return any(card.isVisible() for card in self.cards.values()) or self.scoreboard.isVisible()

    def close(self):
        self.timer.stop()
        for card in self.cards.values():
            card.finish_drag()
            card.close()
        self.drawer.close()
        self.preview_indicator.close()
        self.scoreboard.close()
        self.tab_finder.close()
