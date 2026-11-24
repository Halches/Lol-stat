"""Regression checks with real Qt widgets and isolated settings; no live LCU writes."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
import unittest
from concurrent.futures import Future
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "desktop"), str(ROOT.parent / "app"), str(ROOT)]

from PySide6.QtCore import QBuffer, QIODevice, QSettings, QUrl
from PySide6.QtGui import QFont, QFontDatabase, QPixmap
from PySide6.QtNetwork import QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import QApplication
import artwork
import overlays
import qt


class DesktopAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        for font in ("segoeui.ttf", "segoeuib.ttf", "seguisb.ttf"):
            path = Path("C:/Windows/Fonts") / font
            if path.exists():
                QFontDatabase.addApplicationFont(str(path))
        cls.app.setFont(QFont("Segoe UI", 10))
        cls.app.setStyle("Fusion")
        cls.app.setStyleSheet(qt.STYLE)

    def window(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        settings = QSettings(str(Path(temporary.name) / "settings.ini"), QSettings.Format.IniFormat)
        catalog = {"patch": "16.23.1", "ids": {"112": "Viktor", "103": "Ahri"},
                   "names": {"Viktor": "Виктор", "Ahri": "Ари"}, "items": {}}
        with (patch.object(qt, "Companion", return_value=Mock(catalog=catalog, voice_context={})),
              patch.object(qt, "QSettings", return_value=settings),
              patch.object(qt.Artwork, "image", return_value=QPixmap()),
              patch.object(qt.AutomationServer, "start", return_value=False),
              patch.object(overlays, "foreground_game", return_value=None),
              patch.object(sys, "argv", ["test", "--smoke"])):
            window = qt.Window()
        window.timer.stop()
        self.addCleanup(window.close)
        return window

    def pending_preview(self, window):
        window.champion_input.setText("Viktor")
        window.role_input.setCurrentIndex(window.role_input.findData("MIDDLE"))
        pending = Future()
        with patch.object(window.preview_executor, "submit", return_value=pending):
            window.request_preview()
        self.assertIs(window.preview_job, pending)
        return pending

    def set_session(self, window, generation=1, account="one", *, paint=True):
        window.snapshot = {"phase": "Lobby", "home": True, "flowGeneration": generation,
                           "homeProfile": {"profile": {"riot": account + "#EUW"}}}
        if paint:
            window.paint_snapshot()

    def personal_build(self):
        return {"personal": {"champion": "Виктор", "championKey": "Viktor", "items": [],
                             "runes": [], "shards": [], "spellNames": [], "spellIds": [],
                             "role": "Центр", "patch": "16.23", "source": "Моя сборка"}}

    def test_pending_personal_build_is_rejected_after_session_changes(self):
        for generation, account in ((2, "one"), (1, "two"), (2, "two")):
            with self.subTest(generation=generation, account=account):
                window = self.window()
                self.set_session(window)
                pending = self.pending_preview(window)
                self.set_session(window, generation, account)
                pending.set_result(self.personal_build())
                window.finish_preview()
                window.paint_snapshot()
                self.assertFalse(window.preview_options)
                self.assertIsNone(window.shown_build)
                self.assertTrue(window.preview_button.isEnabled())

    def test_loaded_personal_build_is_cleared_on_session_change(self):
        window = self.window()
        self.set_session(window)
        pending = self.pending_preview(window)
        pending.set_result(self.personal_build())
        window.finish_preview()
        self.assertIn("personal", window.preview_options)
        self.set_session(window, 2, "two")
        for _ in range(3):
            window.paint_snapshot()
            self.assertFalse(window.preview_options)
            self.assertIsNone(window.shown_build)
        fresh = self.pending_preview(window)
        current_build = self.personal_build()
        current_build["personal"]["source"] = "Новая сессия"
        fresh.set_result(current_build)
        window.finish_preview()
        self.assertEqual(window.preview_options["personal"]["source"], "Новая сессия")

    def test_preview_completion_checks_context_even_before_next_paint(self):
        window = self.window()
        self.set_session(window)
        pending = self.pending_preview(window)
        self.set_session(window, 2, "two", paint=False)
        pending.set_result(self.personal_build())
        window.finish_preview()
        self.assertFalse(window.preview_options)

    def test_returning_to_old_account_does_not_revive_pending_personal_build(self):
        window = self.window()
        self.set_session(window)
        pending = self.pending_preview(window)
        self.set_session(window, account="two")
        self.set_session(window, account="one")
        pending.set_result(self.personal_build())
        window.finish_preview()
        self.assertFalse(window.preview_options)

    def test_temporarily_missing_profile_preserves_same_session_build(self):
        window = self.window()
        self.set_session(window)
        pending = self.pending_preview(window)
        pending.set_result(self.personal_build())
        window.finish_preview()
        window.snapshot["homeProfile"] = None
        window.paint_snapshot()
        self.assertIn("personal", window.preview_options)
        self.set_session(window)
        self.assertIn("personal", window.preview_options)

    def test_voice_page_fits_minimum_window_with_long_voice_names(self):
        window = self.window()
        self.set_session(window)
        window.assistant_page.voice.addItem("Очень длинное название голоса Microsoft для проверки ширины окна", "test")
        window.assistant_page.voice.setCurrentIndex(window.assistant_page.voice.count() - 1)
        window.show_home_page("assistant")
        window.show()
        for width in (1570, 1160, 800, 670):
            with self.subTest(width=width):
                window.resize(width, 770)
                self.app.processEvents()
                self.assertLessEqual(window.scroll.widget().width(), window.scroll.viewport().width() + 2)
                for action in (window.assistant_page.test, window.assistant_page.stop):
                    window.scroll.ensureWidgetVisible(action)
                    self.app.processEvents()
                    bounds = action.geometry()
                    origin = action.parentWidget().mapTo(window.scroll.viewport(), bounds.topLeft())
                    self.assertGreaterEqual(origin.x(), 0)
                    self.assertLessEqual(origin.x() + action.width(), window.scroll.viewport().width())

    def test_updates_page_order_and_narrow_layout_with_available_release(self):
        from desktop.update_service import Release
        window = self.window()
        self.assertEqual(list(qt.HOME_PAGES)[-2:], ["settings", "updates"])
        window.updates_page.available = Release("v3.1.0", "Обновление", "текст", "", "", "exe", 1, None, None)
        window.update_update_notice()
        self.assertFalse(window.update_banner.isHidden())
        self.assertIn("•", window.nav_buttons["updates"].text())
        window.updates_page.releases = [Release(f"v3.{n}.0", "Название выпуска " * 12, "А" * 2000, "", "", None, 0, None, None)
                                        for n in (4, 3, 2)]
        window.updates_page.render_notes()
        window.show_home_page("updates")
        window.show()
        for width in (1570, 1160, 670):
            with self.subTest(width=width):
                window.resize(width, 770)
                self.app.processEvents()
                self.assertLessEqual(window.scroll.widget().width(), window.scroll.viewport().width() + 2)

    def test_sidebar_brand_fits_at_all_supported_widths(self):
        window = self.window()
        window.show()
        for width in (1570, 1160, 670, 1570):
            with self.subTest(width=width):
                window.resize(width, 770)
                self.app.processEvents()
                brand = window.sidebar_brand
                self.assertEqual(brand.text(), "LoL Helper")
                if width >= 900:
                    self.assertTrue(brand.isVisible())
                    self.assertLessEqual(brand.fontMetrics().horizontalAdvance(brand.text()), brand.contentsRect().width())
                    self.assertLessEqual(brand.geometry().right(), window.menu_sidebar.contentsRect().right())
                else:
                    self.assertTrue(brand.isHidden())
                    self.assertFalse(window.sidebar_mark.isHidden())
                self.assertEqual(window.menu_sidebar.width(), 64 if width < 900 else 154 if width < 1180 else 214)
                self.assertEqual(window.minimumWidth(), 670)

    def test_changed_champion_explains_why_preview_is_waiting(self):
        window = self.window()
        pending = self.pending_preview(window)
        window.champion_input.setText("Ahri")
        self.assertFalse(window.preview_button.isEnabled())
        self.assertTrue(window.preview_message.text())
        self.assertIn("предыдущ", window.preview_message.text().lower())
        pending.set_result({"pick": {"championKey": "Viktor"}})
        window.finish_preview()
        self.assertTrue(window.preview_button.isEnabled())
        self.assertFalse(window.preview_options)
        self.assertIn("Показать сборку", window.preview_message.text())

    def test_changed_role_does_not_apply_old_result_or_leave_loading(self):
        window = self.window()
        pending = self.pending_preview(window)
        window.role_input.setCurrentIndex(window.role_input.findData("TOP"))
        self.assertTrue(window.preview_message.text())
        pending.set_exception(OSError("temporary failure"))
        window.finish_preview()
        self.assertFalse(window.preview_options)
        self.assertTrue(window.preview_button.isEnabled())
        self.assertNotIn("Загружаем", window.preview_message.text())

    def test_returning_to_pending_selection_keeps_loading_message(self):
        window = self.window()
        pending = self.pending_preview(window)
        window.champion_input.setText("Ahri")
        window.champion_input.setText("Viktor")
        self.assertIn("Загружаем", window.preview_message.text())
        pending.set_result({})
        window.finish_preview()
        self.assertTrue(window.preview_button.isEnabled())
        self.assertIn("нет сборки", window.preview_message.text())

    def test_demo_controls_are_labelled_and_unavailable_outside_preview(self):
        window = self.window()
        controls = window.overlays
        controls.update_match(True, {"build": None})
        self.assertTrue(controls.desktop["build"].isEnabled())
        for spec in overlays.OVERLAYS:
            if spec.preview_only:
                for toggle in (controls.desktop[spec.key], controls.in_game[spec.key]):
                    with self.subTest(key=spec.key):
                        self.assertIn("демо", toggle.text().lower())
                        self.assertFalse(toggle.isEnabled())
                        self.assertFalse(toggle.isChecked())
                if spec.key in controls.cards:
                    self.assertIsNone(controls.cards[spec.key].content)

    def test_demo_preferences_survive_preview_without_enabling_live_demo(self):
        window = self.window()
        controls = window.overlays
        controls.set_preview(True)
        self.assertTrue(controls.desktop["metrics"].isEnabled())
        self.assertTrue(controls.desktop["metrics"].isChecked())
        controls.desktop["metrics"].setChecked(False)
        controls.set_preview(False)
        self.assertFalse(controls.desktop["metrics"].isEnabled())
        self.assertFalse(controls.desktop["lane"].isChecked())
        controls.set_preview(True)
        self.assertFalse(controls.desktop["metrics"].isChecked())
        self.assertTrue(controls.desktop["lane"].isChecked())
        controls.set_preview(False)
        self.assertFalse(controls.desktop["lane"].isChecked())

    def test_invalid_ports_are_rejected_and_valid_local_sites_are_preserved(self):
        window = self.window()
        for address in ("https://example.com:banana", "https://example.com:99999",
                        "https://example.com:0", "https://example.com:"):
            with self.subTest(address=address), self.assertRaises(ValueError):
                window.validated_site(address)
        for address in ("https://example.com", "https://example.com:8443",
                        "http://localhost:8000", "http://127.0.0.1:8000", "http://[::1]:8000"):
            self.assertEqual(window.validated_site(address + "/"), address)
        window.settings.setValue("site", "http://127.0.0.1:8000")
        window.site.setText("https://example.com:banana")
        window.save()
        self.assertEqual(window.settings.value("site"), "http://127.0.0.1:8000")
        self.assertNotIn("сохранены", window.notice.text())

    def test_failed_image_is_retried_after_backoff_and_success_is_cached(self):
        art = artwork.Artwork(None)
        self.addCleanup(art.deleteLater)
        url = "https://example.com/icon.png"
        failure = Mock()
        failure.request.return_value = QNetworkRequest(QUrl(url))
        failure.error.return_value = QNetworkReply.NetworkError.TimeoutError
        image = QPixmap(8, 8)
        image.fill()
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(buffer, "PNG")
        success = Mock()
        success.request.return_value = QNetworkRequest(QUrl(url))
        success.error.return_value = QNetworkReply.NetworkError.NoError
        success.readAll.return_value = buffer.data()
        with patch.object(artwork, "monotonic", return_value=100) as now, patch.object(art, "get") as get:
            art.image(url)
            art.store(failure)
            self.assertNotIn(url, art.images)
            art.image(url)
            self.assertEqual(get.call_count, 1)
            now.return_value = 100 + artwork.IMAGE_RETRY_SECONDS + 1
            art.retry_failed()
            art.image(url)
            self.assertEqual(get.call_count, 2)
            art.store(success)
            self.assertFalse(art.image(url).isNull())
            self.assertEqual(get.call_count, 2)


if __name__ == "__main__":
    unittest.main()
