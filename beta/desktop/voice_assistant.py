"""Qt integration and an independent settings page for prerecorded advice."""
from concurrent.futures import ThreadPoolExecutor
from time import monotonic

from PySide6.QtCore import QObject, QSignalBlocker, QTimer, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QBoxLayout, QCheckBox, QComboBox, QDoubleSpinBox, QHBoxLayout, QSizePolicy, QSpinBox, QVBoxLayout, QWidget

import lcu
from .voice_audio import ClipPlayer, VoicePack
from .voice_catalog import PHRASES, ROLES, TOPICS, asset_root, setting_key
from .voice_rules import VoiceRules
from .widgets import button, label, panel


def read_live():
    return lcu.live_data()


class Assistant(QObject):
    changed = Signal()
    played = Signal(str)
    failed = Signal(str)

    def __init__(self, settings, companion, parent=None, *, running=True, pack=None, player=None):
        super().__init__(parent)
        self.settings, self.companion = settings, companion
        self.pack = pack or VoicePack()
        self.player = player or ClipPlayer(on_error=self.failed.emit, on_play=self.played.emit)
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="voice-live-data")
        self.job = None
        self.revision = 0
        self.session = None
        self.rules = None
        self.after = 0
        self.context_after = 0
        self.was_active = False
        self.watching = False
        self.last_clock = None
        self.last_clock_at = 0
        self.closed = False
        self.status = "Ожидаем матч EUW Solo/Duo или Flex"
        self.last_phrase = "Подсказок ещё не было"
        self.error = ""
        self.text_message = ""
        self.text_until = 0
        self.played.connect(self.on_played)
        self.failed.connect(self.on_failed)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        if running:
            self.timer.start(150)

    def flag(self, key, default=True):
        return self.settings.value(key, default, type=bool)

    def enabled(self, topic, role):
        if topic.roles and role not in topic.roles:
            return False
        return self.flag(setting_key(topic.key, role if topic.roles else ""), topic.default)

    @property
    def voice(self):
        selected = self.settings.value("assistant/voice", "svetlana")
        return selected if selected in self.pack.voices else next(iter(self.pack.voices), "")

    def configure(self, key, value):
        self.settings.setValue(key, value)
        self.revision += 1
        self.player.stop()
        self.text_message = ""
        if self.rules:
            self.rules.engine.prev = None
        self.poll()
        self.changed.emit()

    def phrase_channel(self, phrase, channel):
        key = f"assistant/phrase_output/{phrase}/{channel}"
        if self.settings.contains(key):
            return self.flag(key)
        mode = self.settings.value("assistant/output", "voice")
        return self.flag("assistant/text", False) if channel == "text" else mode == channel

    def reset_phrase_output(self, phrase):
        self.settings.remove(f"assistant/phrase_output/{phrase}")
        self.revision += 1
        self.player.stop()
        self.text_message = ""
        self.changed.emit()

    def preview(self, phrase="sample"):
        if phrase != "sample":
            self.deliver_phrase(phrase, preview=True)
            return
        self.player.stop()
        path = self.pack.clip(self.voice, phrase)
        if path:
            self.error = ""
            self.player.submit(path, phrase, self.settings.value("assistant/volume", 70, type=int), priority=100)
        else:
            self.on_failed("Для выбранного голоса нет готовой записи.")

    def on_played(self, phrase):
        self.last_phrase = PHRASES.get(phrase, "")
        self.changed.emit()

    def deliver_phrase(self, phrase, *, preview=False):
        if not preview and not self.flag("assistant/phrases/" + phrase):
            return
        self.last_phrase = PHRASES.get(phrase, "")
        if self.phrase_channel(phrase, "text"):
            self.text_message, self.text_until = self.last_phrase, monotonic() + 6
        if self.phrase_channel(phrase, "sound"):
            QApplication.beep()
        if self.phrase_channel(phrase, "voice"):
            path = self.pack.clip(self.voice, phrase)
            if path:
                priority = 90 if phrase.startswith(("enemy_level", "level", "dragon", "baron", "elder")) else 50
                self.player.submit(path, phrase, self.settings.value("assistant/volume", 70, type=int),
                                   priority=priority, ttl=2 if phrase.endswith(("_60", "_30")) else 5)
        self.changed.emit()

    def on_failed(self, error):
        self.error = f"Не удалось воспроизвести голос. {error}"
        self.changed.emit()

    def poll(self):
        if self.closed:
            return
        now = monotonic()
        context = dict(getattr(self.companion, "voice_context", {}) or {})
        configured = self.flag("assistant/enabled", False) and (bool(self.pack.voices)
            or self.settings.value("assistant/output", "voice") != "voice" or self.flag("assistant/text", False)
            or any(self.phrase_channel(p, c) for p in PHRASES for c in ("text", "sound")))
        active = bool(configured and context.get("active") and now - context.get("observedAt", 0) <= 4)
        session = (context.get("generation"), context.get("gameId")) if configured and context.get("gameId") else None
        if session != self.session:
            self.text_message = ""
            self.revision += 1
            self.player.stop()
            self.session = session
            self.rules = VoiceRules(self.companion.catalog) if session else None
            self.after = 0
            self.watching = False
            self.last_clock = None
        if active != self.was_active:
            self.text_message = ""
            self.revision += 1
            self.player.stop()
            if self.rules:
                self.rules.engine.prev = None
            self.was_active = active
            self.watching = False
        self.status = ("Помощник выключен" if not self.flag("assistant/enabled", False) else
                       "Нет готовых голосовых записей" if not self.pack.voices and self.settings.value("assistant/output", "voice") == "voice" and not self.flag("assistant/text", False) else
                       "Ожидаем матч EUW Solo/Duo или Flex" if not active else
                       "Помощник следит за матчем" if self.watching else "Ожидаем данные игрока")
        if self.job and self.job[1].done():
            revision, job = self.job
            self.job = None
            try:
                raw = job.result()
                if active and session and revision == self.revision:
                    role = self.settings.value("assistant/role", "") or context.get("role", "")
                    phrases = self.rules.tick(raw, role, self.enabled,
                                              self.settings.value("assistant/cs_target", 7.0, type=float))
                    if self.rules.accepted:
                        if self.rules.reset_detected:
                            self.player.stop()
                            self.last_clock = None
                        if self.last_clock != self.rules.last_time:
                            self.last_clock, self.last_clock_at = self.rules.last_time, now
                        elif now - self.last_clock_at > 3:
                            self.rules.accepted = False
                    self.watching = self.rules.accepted
                    if self.watching:
                        self.status = "Помощник следит за матчем"
                        self.player.retain({p for p in self.rules.valid_phrases if self.flag("assistant/phrases/" + p)})
                    else:
                        self.status = "Данные матча недоступны · озвучка приостановлена"
                        self.player.stop()
                        self.rules.engine.prev = None
                    for phrase in phrases if self.watching else []:
                        self.deliver_phrase(phrase)
            except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
                self.player.stop()
                if self.rules:
                    self.rules.engine.prev = None
                self.on_failed(f"Данные матча временно недоступны: {type(error).__name__}.")
        if active and session and self.job is None and now >= self.after:
            self.after = now + 1
            self.job = self.revision, self.executor.submit(read_live)
        if now >= self.context_after:
            self.context_after = now + 1
            self.changed.emit()

    def close(self):
        self.closed = True
        self.timer.stop()
        self.revision += 1
        self.player.close()
        self.executor.shutdown(wait=False, cancel_futures=True)


class AssistantPage(QWidget):
    def __init__(self, assistant):
        super().__init__()
        self.assistant = assistant
        self.checks = {}
        self.previews = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        card, contents = panel("homePanel")
        contents.addWidget(label("Голос во время матча", "section"))
        contents.addWidget(label("Готовые записи на русском. Во время игры интернет для озвучки не нужен. "
                                 "Настройки сохраняются автоматически.", "caption", wrap=True))
        self.master = QCheckBox("Включить голосового помощника")
        self.master.setChecked(assistant.flag("assistant/enabled", False))
        self.master.toggled.connect(lambda value: assistant.configure("assistant/enabled", value))
        contents.addWidget(self.master)
        self.output = QComboBox()
        self.output.setAccessibleName("Звуковое оповещение помощника")
        self.output.setProperty("automationId", "assistant_output")
        for title, value in (("Голос", "voice"), ("Звуковой сигнал вместо голоса", "sound"), ("Без звука", "none")):
            self.output.addItem(title, value)
        self.output.setCurrentIndex(max(0, self.output.findData(assistant.settings.value("assistant/output", "voice"))))
        self.output.currentIndexChanged.connect(lambda _: assistant.configure("assistant/output", self.output.currentData()))
        contents.addWidget(self.output)
        self.text_hints = QCheckBox("Показывать подсказки текстом поверх игры")
        self.text_hints.setProperty("automationId", "assistant_text")
        self.text_hints.setChecked(assistant.flag("assistant/text", False))
        self.text_hints.toggled.connect(lambda value: assistant.configure("assistant/text", value))
        contents.addWidget(self.text_hints)
        contents.addWidget(label("Звуковой сигнал использует системную громкость Windows. Текст можно включить с любым режимом звука.", "caption", wrap=True))
        self.test_output = button("Проверить выбранное оповещение", lambda: assistant.deliver_phrase("sample", preview=True), "tab")
        self.test_output.setProperty("automationId", "assistant_test_output")
        contents.addWidget(self.test_output)
        self.voice_row = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        selector = QWidget()
        row = QHBoxLayout(selector)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(label("Голос", "captionStrong"))
        self.voice = QComboBox()
        self.voice.setAccessibleName("Голос помощника")
        self.voice.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.voice.setMinimumContentsLength(10)
        self.voice.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.voice.setMinimumWidth(0)
        for key, metadata in assistant.pack.voices.items():
            self.voice.addItem(metadata["name"], key)
        if not assistant.pack.voices:
            self.voice.addItem("Нет готовых записей", "")
        self.voice.setCurrentIndex(max(0, self.voice.findData(assistant.voice)))
        self.voice.setToolTip(self.voice.currentText())
        self.voice.currentTextChanged.connect(self.voice.setToolTip)
        self.voice.currentIndexChanged.connect(lambda _: assistant.configure("assistant/voice", self.voice.currentData()))
        row.addWidget(self.voice, 1)
        self.voice_row.addWidget(selector, 1)
        actions = QWidget()
        row = QHBoxLayout(actions)
        row.setContentsMargins(0, 0, 0, 0)
        self.test = button("▶ Проверить голос", lambda: assistant.preview(), "tab")
        self.test.setEnabled(bool(assistant.pack.voices))
        row.addWidget(self.test)
        self.stop = button("■ Остановить", assistant.player.stop, "tab")
        row.addWidget(self.stop)
        self.voice_row.addWidget(actions)
        contents.addLayout(self.voice_row)
        row = QHBoxLayout()
        row.addWidget(label("Громкость", "captionStrong"))
        self.volume = QSpinBox()
        self.volume.setRange(0, 100)
        self.volume.setSuffix(" %")
        self.volume.setValue(assistant.settings.value("assistant/volume", 70, type=int))
        self.volume.setAccessibleName("Громкость помощника")
        self.volume.valueChanged.connect(lambda value: assistant.configure("assistant/volume", value))
        row.addWidget(self.volume)
        row.addStretch()
        contents.addLayout(row)
        self.state = label("", "captionStrong", wrap=True)
        self.last = label("", "caption", wrap=True)
        self.error = label("", "notice", wrap=True)
        for widget in (self.state, self.last, self.error):
            contents.addWidget(widget)
        layout.addWidget(card)
        card, contents = panel("homePanel")
        contents.addWidget(label("Общие и настройки роли", "section"))
        contents.addWidget(label("Общие подсказки действуют на всех ролях. В разделах линий можно независимо "
                                 "выбрать подсказки для каждой роли. Роль определяется из драфта или данных матча.", "caption", wrap=True))
        row = QHBoxLayout()
        row.addWidget(label("Моя роль", "captionStrong"))
        self.role = QComboBox()
        self.role.setAccessibleName("Роль для голосовых подсказок")
        self.role.addItem("Автоматически", "")
        for key, name in ROLES.items():
            self.role.addItem(QIcon(str(asset_root().parent / "roles" / f"{key.lower()}.png")), name, key)
        self.role.setCurrentIndex(max(0, self.role.findData(assistant.settings.value("assistant/role", ""))))
        self.role.currentIndexChanged.connect(lambda _: assistant.configure("assistant/role", self.role.currentData()))
        row.addWidget(self.role, 1)
        contents.addLayout(row)
        row = QHBoxLayout()
        row.addWidget(label("Цель фарма в минуту", "captionStrong"))
        self.cs = QDoubleSpinBox()
        self.cs.setRange(1, 15)
        self.cs.setDecimals(1)
        self.cs.setSingleStep(.5)
        self.cs.setValue(assistant.settings.value("assistant/cs_target", 7.0, type=float))
        self.cs.setAccessibleName("Цель фарма в минуту")
        self.cs.valueChanged.connect(lambda value: assistant.configure("assistant/cs_target", value))
        row.addWidget(self.cs)
        row.addStretch()
        contents.addLayout(row)
        self.category = QComboBox()
        self.category.setAccessibleName("Категория голосовых подсказок")
        self.category.addItem("Общие", "")
        for key, name in ROLES.items():
            self.category.addItem(QIcon(str(asset_root().parent / "roles" / f"{key.lower()}.png")), name, key)
        self.category.currentIndexChanged.connect(self.show_category)
        contents.addWidget(self.category)
        layout.addWidget(card)
        self.sections = {}
        for scope in ("", *ROLES):
            card, contents = panel("homePanel")
            contents.addWidget(label("Общие подсказки" if not scope else ROLES[scope], "section"))
            for topic in TOPICS:
                if (not scope and topic.roles) or (scope and scope not in topic.roles):
                    continue
                toggle = QCheckBox(topic.title)
                toggle.setChecked(assistant.flag(setting_key(topic.key, scope), topic.default))
                toggle.setAccessibleName(f"{ROLES.get(scope, 'Общие')}: {topic.title}")
                toggle.toggled.connect(lambda value, key=setting_key(topic.key, scope): assistant.configure(key, value))
                contents.addWidget(toggle)
                contents.addWidget(label(topic.description, "caption", wrap=True))
                preview = topic.phrases[0]
                # Pick a role's corresponding ward recording.
                if topic.key == "early_ward":
                    preview = "ward_jungle" if scope == "JUNGLE" else "ward_support" if scope == "UTILITY" else "ward_lane"
                contents.addWidget(label(f"«{PHRASES[preview]}»", "captionStrong", wrap=True))
                play = button("▶ Пример подсказки", lambda _, phrase=preview: assistant.preview(phrase), "tab")
                play.setEnabled(bool(assistant.pack.voices))
                contents.addWidget(play, alignment=Qt.AlignmentFlag.AlignLeft)
                self.checks[(scope, topic.key)] = toggle
                self.previews[(scope, topic.key)] = play
                contents.addSpacing(8)
            self.sections[scope] = card
            layout.addWidget(card)
        layout.addWidget(label("Ганки — оценка, а не обнаружение врага. Сравнение уровней требует известной роли оппонента. "
                               "Исторические маршруты лесника и имена чемпионов в записи не включены.", "caption", wrap=True))
        self.show_category()
        self.phrase_toggles = {}
        self.channel_checks = {}
        phrase_card, phrases = panel("homePanel")
        self.phrase_expand = button("Отдельные фразы", lambda: None, "tab")
        self.phrase_expand.setProperty("automationId", "assistant_phrases_expand")
        self.phrase_expand.setCheckable(True)
        phrases.addWidget(self.phrase_expand)
        phrase_list = QWidget()
        rows = QVBoxLayout(phrase_list)
        for key, text in PHRASES.items():
            if key == "sample":
                continue
            toggle = QCheckBox()
            toggle.setAccessibleName(text)
            toggle.setProperty("automationId", "assistant_phrase_" + key)
            toggle.setChecked(assistant.flag("assistant/phrases/" + key))
            toggle.toggled.connect(lambda value, key=key: assistant.configure("assistant/phrases/" + key, value))
            row = QHBoxLayout()
            row.addWidget(toggle)
            row.addWidget(label(text, "captionStrong", wrap=True), 1)
            rows.addLayout(row)
            channels = QHBoxLayout()
            for channel, title in (("voice", "Голос"), ("text", "Текст"), ("sound", "Сигнал")):
                option = QCheckBox(title)
                option.setAccessibleName(f"{title}: {text}")
                option.setProperty("automationId", f"assistant_phrase_{key}_{channel}")
                option.setChecked(assistant.phrase_channel(key, channel))
                option.toggled.connect(lambda value, key=key, channel=channel: assistant.configure(
                    f"assistant/phrase_output/{key}/{channel}", value))
                self.channel_checks[(key, channel)] = option
                channels.addWidget(option)
            reset = button("По умолчанию", lambda _checked=False, key=key: assistant.reset_phrase_output(key), "tab")
            reset.setProperty("automationId", f"assistant_phrase_{key}_reset")
            channels.addWidget(reset)
            rows.addLayout(channels)
            self.phrase_toggles[key] = toggle
        phrases.addWidget(phrase_list)
        phrase_list.hide()
        self.phrase_expand.toggled.connect(phrase_list.setVisible)
        layout.addWidget(phrase_card)
        assistant.changed.connect(self.refresh)
        self.refresh()

    def show_category(self, *_):
        for scope, section in self.sections.items():
            section.setVisible(scope == self.category.currentData())

    def reflow(self, width):
        self.voice_row.setDirection(QBoxLayout.Direction.TopToBottom if width < 620 else QBoxLayout.Direction.LeftToRight)

    def refresh(self):
        for (phrase, channel), widget in self.channel_checks.items():
            with QSignalBlocker(widget):
                widget.setChecked(self.assistant.phrase_channel(phrase, channel))
        self.state.setText(self.assistant.status)
        self.last.setText(f"Последняя подсказка: {self.assistant.last_phrase}")
        self.error.setText(self.assistant.error)
        self.error.setVisible(bool(self.assistant.error))

    def focus_controls(self):
        return [self.master, self.voice, self.test, self.stop, self.volume, self.role, self.cs, self.category,
                *[widget for scope in self.sections for key in self.checks if key[0] == scope
                  for widget in (self.checks[key], self.previews[key])]]
