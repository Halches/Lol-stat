"""Update status, background checks, downloads and the last three release notes."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import json
import sys

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

from . import update_service as service
from .widgets import button, label, panel


class UpdatePage(QWidget):
    changed = Signal()
    restart = Signal()
    progress = Signal(int, int)

    def __init__(self, settings, can_restart, *, running=True):
        super().__init__()
        self.settings = settings
        self.can_restart = can_restart
        self.version = service.current_version()
        self.releases = []
        self.available = None
        self.downloaded = None
        self.job = None
        self.operation = None
        self.closed = False
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="app-updates")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        card, contents = panel("homePanel")
        contents.addWidget(label(f"Установлена версия {self.version}", "section", wrap=True))
        self.status = label("Проверяем GitHub при запуске и каждые 15 минут, пока приложение открыто.", "caption", wrap=True)
        contents.addWidget(self.status)
        self.action = button("Проверить обновления", self.activate, "primary")
        contents.addWidget(self.action, alignment=Qt.AlignmentFlag.AlignLeft)
        self.github = button("Все выпуски на GitHub ↗", lambda: QDesktopServices.openUrl(QUrl(service.RELEASES_URL)), "tab")
        contents.addWidget(self.github, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(card)
        layout.addWidget(label("Последние патчноуты", "section", wrap=True))
        self.empty = label("Патчноуты появятся после проверки GitHub.", "caption", wrap=True)
        layout.addWidget(self.empty)
        self.notes = []
        for index in range(3):
            card, contents = panel("homePanel")
            title = label("", "section", wrap=True)
            date = label("", "caption")
            body = label("", "captionStrong", wrap=True)
            for text_widget in (title, body):
                policy = text_widget.sizePolicy()
                policy.setHorizontalPolicy(QSizePolicy.Policy.Ignored)
                text_widget.setSizePolicy(policy)
                text_widget.setMinimumWidth(0)
            body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard)
            link = button("Полный патчноут на GitHub ↗", lambda _checked=False, i=index: self.open_notes(i), "tab")
            for widget in (title, date, body, link):
                contents.addWidget(widget)
            layout.addWidget(card)
            self.notes.append((card, title, date, body, link))
            card.hide()
        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(150)
        self.poll_timer.timeout.connect(self.finish)
        self.check_timer = QTimer(self)
        self.check_timer.setInterval(service.CHECK_SECONDS * 1000)
        self.check_timer.timeout.connect(self.check)
        self.start_timer = QTimer(self)
        self.start_timer.setSingleShot(True)
        self.start_timer.timeout.connect(self.check)
        self.progress.connect(self.show_progress)
        try:
            cached = json.loads(settings.value("updates/releases", "[]", type=str))
            if not isinstance(cached, list):
                cached = []
            self.releases = [service.Release(**row) for row in cached[:3]
                             if isinstance(row, dict) and service.version_number(row.get("version")) is not None
                             and all(isinstance(row.get(key), str) for key in ("title", "notes", "published"))]
            self.render_notes()
        except (TypeError, ValueError, KeyError):
            self.releases = []
        if running:
            self.check_timer.start()
            self.start_timer.start(1000)

    def render_notes(self):
        self.empty.setVisible(not self.releases)
        for index, (card, title, date, body, link) in enumerate(self.notes):
            if index >= len(self.releases):
                card.hide()
                continue
            release = self.releases[index]
            excerpt, short = service.note_excerpt(release.notes)
            title.setText(release.title[:180])
            date.setText(release.version + (f" · {release.published}" if release.published else "") + (" · сокращено" if short else ""))
            body.setText(excerpt)
            link.setVisible(True)
            card.show()

    def open_notes(self, index):
        if index < len(self.releases):
            release = self.releases[index]
            QDesktopServices.openUrl(QUrl(f"{service.RELEASES_URL}/tag/{release.version}"))

    def start(self, operation, task, *args):
        if self.closed or self.job is not None:
            return
        self.operation = operation
        self.action.setEnabled(False)
        self.job = self.executor.submit(task, *args)
        self.poll_timer.start()
        self.changed.emit()

    def check(self):
        if self.closed or self.job is not None or self.downloaded is not None:
            return
        self.status.setText("Проверяем выпуски на GitHub…")
        self.action.setText("Проверяем…")
        self.start("check", service.fetch_releases)

    def activate(self):
        if self.closed or self.job is not None:
            return
        if self.downloaded is not None:
            if not self.can_restart():
                self.status.setText("Обновление скачано. Завершите драфт или матч, затем нажмите «Перезапустить и обновить».")
                return
            self.status.setText("Подготавливаем установку… Приложение перезапустится после замены файла.")
            self.action.setText("Подготавливаем…")
            self.start("install", service.launch_installer, self.downloaded)
        elif self.available:
            if not getattr(sys, "frozen", False):
                self.status.setText("Сейчас приложение запущено из исходников. Установка обновления доступна в EXE.")
                return
            self.status.setText(f"Скачиваем {self.available.version}…")
            self.action.setText("Скачиваем…")
            self.start("download", service.download_release, self.available, self.progress.emit)
        else:
            self.check()

    def show_progress(self, got, total):
        if not self.closed and self.operation == "download":
            self.status.setText(f"Скачиваем обновление: {got * 100 // total}% · {got // (1024 * 1024)} из {total // (1024 * 1024)} МБ")

    def refresh_action(self):
        self.action.setEnabled(self.job is None)
        self.action.setText("Перезапустить и обновить" if self.downloaded else "Обновить" if self.available else "Проверить обновления")
        self.action.setAccessibleName(self.action.text())

    def finish(self):
        if self.closed or self.job is None or not self.job.done():
            return
        job, self.job = self.job, None
        operation, self.operation = self.operation, None
        self.poll_timer.stop()
        try:
            result = job.result()
            if operation == "check":
                self.releases = result
                self.settings.setValue("updates/releases", json.dumps([asdict(release) for release in result], ensure_ascii=False))
                self.render_notes()
                latest = next(iter(result), None)
                self.available = latest if latest and version_newer(latest.version, self.version) and latest.download else None
                if self.available:
                    self.status.setText(f"Доступна версия {self.available.version}. Обновление устанавливается по вашей кнопке.")
                elif latest and version_newer(latest.version, self.version):
                    self.status.setText(f"Опубликована {latest.version}, но Windows-файл ещё не готов. Повторим проверку автоматически.")
                else:
                    self.status.setText(
                        "Установленная версия новее последнего опубликованного выпуска на GitHub."
                        if latest and version_newer(self.version, latest.version)
                        else "У вас последняя версия." if result else "Опубликованных выпусков пока нет.")
            elif operation == "download":
                self.downloaded = result
                self.status.setText("Обновление скачано и проверено. Нажмите «Перезапустить и обновить», когда будете готовы.")
            elif operation == "install":
                if self.can_restart():
                    self.restart.emit()
                else:
                    (result / "cancel").touch()
                    self.status.setText("Установка отложена до завершения драфта или матча. Обновление уже скачано.")
        except Exception as error:
            detail = str(error) if isinstance(error, service.UpdateError) else "Проверьте соединение и повторите попытку."
            self.status.setText(f"Не удалось {'проверить выпуски' if operation == 'check' else 'обновить приложение'}. {detail}")
        self.refresh_action()
        self.changed.emit()

    def close(self):
        self.closed = True
        for timer in (self.start_timer, self.check_timer, self.poll_timer):
            timer.stop()
        self.executor.shutdown(wait=False, cancel_futures=True)


def version_newer(latest, current):
    return service.version_number(latest) > service.version_number(current)
