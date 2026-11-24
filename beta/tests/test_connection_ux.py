"""Connection guidance and actions use the same widgets through the public API."""
import unittest
from concurrent.futures import Future
from unittest.mock import patch
import test_desktop_audit as checks
from connection import connection_view


class ConnectionUXTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if checks.QApplication.instance() is None:
            checks.DesktopAuditTests.setUpClass()
        cls.app = checks.QApplication.instance()

    def setUp(self):
        images = patch.object(checks.qt.Artwork, "image", return_value=checks.QPixmap())
        images.start()
        self.addCleanup(images.stop)
        self.window = checks.DesktopAuditTests.window(self)
        self.window.show()
        self.app.processEvents()

    def call(self, method, **kwargs):
        result = self.window.automation.dispatch(dict(method=method, **kwargs))
        self.assertTrue(result["ok"], result)
        return result["result"]

    def test_offline_has_one_connection_card_and_api_actions(self):
        dashboard = self.window.dashboard
        self.assertTrue(dashboard.connection_panel.isVisible())
        for area in (dashboard.profile_area, dashboard.charts_area, dashboard.matches):
            self.assertTrue(area.isHidden())
        self.assertEqual(self.call("read", model="connection")["data"]["state"], "offline")
        self.call("click", control="connection_builds")
        self.assertEqual(self.window.home_page, "builds")
        result = self.window.automation.dispatch({"method": "click", "control": "connection_retry"})
        self.assertFalse(result["ok"])  # hidden button cannot restart anything
        self.call("click", control="menu_overview")
        with patch.object(self.window.assistant_page.test, "click") as test:
            self.call("click", control="connection_voice")
            test.assert_called_once()
        self.assertEqual(self.window.home_page, "assistant")

    def test_retry_is_queued_on_worker_and_cannot_be_clicked_twice(self):
        self.call("click", control="connection_retry")
        self.assertTrue(self.call("read", model="connection")["data"]["retryPending"])
        self.assertFalse(self.window.automation.dispatch({"method": "click", "control": "connection_retry"})["ok"])
        with patch.object(self.window.executor, "submit", return_value=Future()) as submit:
            self.window.poll()
        self.assertTrue(submit.call_args.kwargs["refresh_connection"])
        self.assertFalse(self.window.connection_retry_pending)

    def test_offline_build_example_fills_real_form_without_import(self):
        self.call("click", control="menu_builds")
        self.assertIn("без игры", self.window.home_connection.text())
        self.assertTrue(self.window.build_access_hint.isVisible())
        self.call("click", control="build_example")
        self.assertEqual(self.call("read", control="champion_search")["data"]["value"], "Виктор")
        self.assertEqual(self.call("read", control="preview_role")["data"]["value"], "MIDDLE")
        self.assertIsNone(self.window.export_job)
        self.assertFalse(self.window.automation.dispatch({"method": "click", "control": "import_build"})["ok"])

    def test_advanced_site_is_optional_and_has_explicit_save(self):
        self.call("click", control="menu_settings")
        self.assertTrue(self.window.site_settings.isHidden())
        self.assertTrue(self.window.overlays.preferences.isVisible())
        self.call("click", control="settings_advanced")
        self.assertTrue(self.window.site.isVisible())
        self.assertEqual(self.window.save_button.text(), "Сохранить адрес")
        self.call("set", control="site", value="https://example.com:banana")
        self.call("click", control="save_settings")
        self.assertNotEqual(self.window.settings.value("site"), "https://example.com:banana")
        self.call("set", control="site", value="http://127.0.0.1:8001")
        self.call("click", control="save_settings")
        self.assertEqual(self.window.settings.value("site"), "http://127.0.0.1:8001")

    def test_laboratory_is_collapsed_and_api_cannot_activate_hidden_demo(self):
        self.call("click", control="menu_settings")
        self.assertTrue(self.window.overlays.laboratory.isHidden())
        self.assertFalse(self.window.automation.dispatch({"method": "set", "control": "overlay_preview", "value": True})["ok"])
        self.call("click", control="overlay_laboratory")
        self.assertTrue(self.call("read", model="overlays")["data"]["laboratoryExpanded"])
        demo = self.window.overlays.desktop["metrics"]
        self.assertTrue(demo.isEnabled())
        with patch.object(self.window.overlays, "sync"):
            self.call("set", control="overlay_preview", value=True)
            self.assertTrue(demo.isEnabled())
            self.assertTrue(self.call("read", model="overlays")["data"]["preview"])
            self.call("set", control="overlay_preview", value=False)
        self.assertTrue(demo.isEnabled())
        self.call("click", control="overlay_laboratory")
        self.assertTrue(self.window.overlays.laboratory.isHidden())

    def test_navigation_keeps_button_semantics_current_page_and_compact_api(self):
        from PySide6.QtGui import QAccessible
        self.window.resize(670, 770)
        self.app.processEvents()
        self.assertEqual(self.window.menu_sidebar.width(), 64)
        self.assertTrue(self.call("read", model="navigation")["data"]["collapsed"])
        self.call("click", control="menu_settings")
        entry = self.call("read", control="menu_settings")["data"]
        self.assertTrue(entry["current"])
        self.assertFalse(entry["checkable"])
        interface = QAccessible.queryAccessibleInterface(self.window.nav_buttons["settings"])
        self.assertEqual(interface.role(), QAccessible.Role.Button)
        self.assertIn("Текущий", interface.text(QAccessible.Text.Description))
        self.assertFalse(self.window.automation.dispatch({"method": "set", "control": "menu_settings", "value": True})["ok"])
        self.call("click", control="navigation_toggle")
        for _ in range(6):
            self.app.processEvents()  # Drain nested layout requests after changing the rail width.
        self.assertFalse(self.call("read", model="navigation")["data"]["collapsed"])
        self.assertFalse(self.call("read", model="navigation")["data"]["automatic"])
        self.assertIn("Настройки", self.window.nav_buttons["settings"].text())
        self.assertLessEqual(self.window.scroll.widget().width(), self.window.scroll.viewport().width() + 2)

    def test_loaded_ranks_reflow_and_keep_native_qt_paint_metrics(self):
        from PySide6.QtGui import QPaintDevice
        self.window.snapshot = {"phase": "idle", "home": True,
            "homeProfile": {"profile": {"riot": "Player#EUW"}, "ranks": {
                "solo": {"state": "ranked", "tier": "GOLD", "div": "II", "lp": 44, "w": 30, "l": 20},
                "flex": {"state": "unranked"}}},
            "connection": {"state": "ready", "profileAvailable": True, "history": "unavailable"}}
        self.window.paint_snapshot()
        rank = self.window.dashboard.ranks["solo"]
        for width in (1570, 1160, 670, 1570):
            self.window.resize(width, 770)
            self.app.processEvents()
            self.assertTrue(rank.isVisible())
            self.assertGreater(rank.metric(QPaintDevice.PaintDeviceMetric.PdmDpiX), 0)
            self.assertEqual(rank.rank.text(), "Золото II")
            self.assertEqual(rank.metrics[0][0].text(), "60,0%")

    def test_profile_with_unavailable_history_does_not_show_empty_rank_and_charts(self):
        self.window.snapshot = {"phase": "idle", "home": True,
                                "homeProfile": {"profile": {"riot": "Player#EUW"}},
                                "connection": {"state": "ready", "profileAvailable": True, "history": "unavailable"}}
        self.window.paint_snapshot()
        dashboard = self.window.dashboard
        self.assertTrue(dashboard.profile_area.isVisible())
        self.assertTrue(all(rank.isHidden() for rank in dashboard.ranks.values()))
        self.assertTrue(dashboard.charts_area.isHidden())
        self.assertIn("пока не отдаёт", dashboard.connection_message.text())
        self.assertTrue(dashboard.retry.isHidden())
        for state in ("offline", "connecting", "loading_profile", "profile_error", "unsupported_region"):
            view = connection_view({"connection": {"state": state}})
            self.assertTrue(view["message"])
            self.assertTrue(view["hint"])
