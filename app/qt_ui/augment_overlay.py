"""Click-through advice above the visible Arena or Mayhem cards."""
import time
from concurrent.futures import ThreadPoolExecutor
from html import escape

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel

from app_config import C, IS_WIN, game_focused, game_rect, log_error
from augment_advice import CLASS_COMPATIBILITY, STRONG_SYNERGY, WEAK_SYNERGY, explain, mode_for
from augment_scan import Reader
from augment_champion_stats import fetch_champion_picks
from . import native


class AugmentOverlay:
    def __init__(self, app):
        self.app = app
        self.labels = []
        self.pick_labels = []
        self.champion_picks = {}
        self.picks_pending = False
        self.context = self.pending = self.reader = None
        self.epoch = 0
        self.next_scan = 0
        self.last_time = 0
        self.status = 'Ожидаю выбора в Арене или ARAM Хаосе'
        self.worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix='augment-ocr')
        self.timer = QTimer(app.window)
        self.timer.timeout.connect(self.tick)
        if IS_WIN and not app.offline:
            self.timer.start(180)

    def active_context(self):
        a, g = self.app, self.app.last_game
        if (not g or not g.me or not a.s.get('augment_advice') or a.live_stale
                or a.result or a.hidden or a.demo_on or not game_focused()):
            return None
        mode = mode_for(g.mode, getattr(g, 'queue_id', None))
        if mode:
            return mode, g.me['c'], getattr(g, 'match_id', None), game_rect()
        return None

    def scan(self, mode, rect):
        # The reader and its native OCR state belong to this single worker.
        if self.reader is None:
            self.reader = Reader()
        return self.reader.capture(mode, rect)

    def tick(self):
        ctx = self.active_context()
        now = time.monotonic()
        clock = self.app.last_game.t if ctx else 0
        if ctx != self.context or clock < self.last_time:
            self.context = ctx
            self.epoch += 1
            self.next_scan = 0
            self.hide()
            if not ctx:
                self.set_status('Ожидаю выбора в Арене или ARAM Хаосе')
        self.last_time = clock
        if self.pending is not None and self.pending.done():
            future, self.pending = self.pending, None
            try:
                result = future.result()
            except Exception as error:
                result = ()
                if self.scan_epoch == self.epoch:
                    log_error('распознавание аугментаций', error)
                    self.set_status('Распознавание недоступно. Проверьте установку моделей OCR.')
                    self.next_scan = now + 45
            else:
                if ctx and self.scan_epoch == self.epoch:
                    self.set_status('Карточки распознаны' if result else 'Ожидаю экран выбора аугментаций')
            if ctx and self.scan_epoch == self.epoch:
                if result:
                    self.show(result, ctx)
                else:
                    self.hide()
        if ctx:
            self.load_picks(ctx[0], ctx[1], now)
        if ctx and self.pending is None and now >= self.next_scan:
            self.scan_epoch = self.epoch
            self.next_scan = now + 1
            self.pending = self.worker.submit(self.scan, ctx[0], ctx[3])

    def load_picks(self, mode, champion, now):
        key = (mode, champion)
        expires, _ = self.champion_picks.get(key, (0, None))
        if self.picks_pending or now < expires:
            return
        self.picks_pending = True

        def remember(picks, error):
            self.picks_pending = False
            if picks is None:
                _, picks = self.champion_picks.get(key, (0, None))
                retry = 60
            else:
                retry = 1800
            self.champion_picks[key] = (time.monotonic() + retry, picks)

        self.app.background(lambda: fetch_champion_picks(mode, champion), remember)

    def set_status(self, text):
        self.status = text
        label = getattr(self.app, 'augment_status', None)
        if label and label.text() != text:
            label.setText(text)

    def hide(self):
        for label in self.labels + self.pick_labels:
            label.hide()

    @staticmethod
    def new_label(wrap):
        label = QLabel(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                       Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus |
                       Qt.WindowType.WindowTransparentForInput)
        label.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setWordWrap(wrap)
        return label

    @staticmethod
    def place(label, x, y, width, height, font_size):
        native.move(label, round(x-width/2), y, width, height)
        # Use the monitor's current logical DPI after moving the native window.
        font = label.font()
        font.setPixelSize(max(8, round(font_size / label.devicePixelRatioF())))
        label.setFont(font)
        label.show()
        if IS_WIN:
            native.styles(label, True)

    def show(self, result, ctx):
        mode, champion, _, (_, gy, _, gh) = ctx
        tags = self.app.data.champs.get(champion, {}).get('tags', ())
        _, picks = self.champion_picks.get((mode, champion), (0, None))
        while len(self.labels) < len(result):
            self.labels.append(self.new_label(wrap=True))
            self.pick_labels.append(self.new_label(wrap=False))
        spacing = min(b[0]-a[0] for a,b in zip(result,result[1:]))
        width = round(min(gh*.32, spacing*.94))
        for label, pick_label, (x, y, card) in zip(self.labels, self.pick_labels, result):
            heading, reason = explain(card, mode, champion, tags)
            rate = picks.label(card) if picks else 'Берут: —'
            accent = {STRONG_SYNERGY: C['good'], CLASS_COMPATIBILITY: C['good'],
                      WEAK_SYNERGY: C['warn']}.get(heading, C['mute'])
            label.setStyleSheet(f'background:{C["panel"]};color:{C["fg"]};border:1px solid {accent};border-radius:5px;padding:3px;')
            self.place(label, x, max(gy+2, round(y-gh*.36)), width, round(gh*.116), gh*.014)
            heading_size = max(12, round(gh*.020 / label.devicePixelRatioF()))
            heading_html = f'<b style="font-size:{heading_size}px">{escape(heading)}</b>'
            title = f'<b>{escape(card["ru"])}</b>'
            detail = escape(reason)
            label.setText(f'{heading_html}<br>{title}<br>{detail}')
            if label.heightForWidth(label.width()) > label.height():
                # The in-game card already has a title. Preserve the assessment and
                # its explanation when there is only room for two text blocks.
                label.setText(f'{heading_html}<br>{detail}')

            pick_label.setStyleSheet(f'background:{C["panel"]};color:{C["fg"]};border:1px solid {C["mute"]};border-radius:7px;padding:1px;')
            pick_label.setText(f'<b>{escape(rate)}</b>')
            # Anchor inside the bottom of the card, away from the reroll buttons.
            self.place(pick_label, x, round(y+gh*.22), min(width, round(gh*.22)), round(gh*.031), gh*.015)
        for label in self.labels[len(result):] + self.pick_labels[len(result):]:
            label.hide()

    def close(self):
        self.timer.stop()
        self.worker.shutdown(wait=False, cancel_futures=True)
        for label in self.labels + self.pick_labels:
            label.close()
