"""Operate real application widgets entirely through the semantic API."""
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

import test_desktop_audit as desktop_checks
qt, QPixmap = desktop_checks.qt, desktop_checks.QPixmap
from PySide6.QtCore import QEventLoop, QTimer, Qt
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import QApplication, QAbstractButton, QComboBox, QDialog, QLabel, QLineEdit, QPushButton, QVBoxLayout


class FullAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if QApplication.instance() is None:
            desktop_checks.DesktopAuditTests.setUpClass()
        cls.app = QApplication.instance()

    def setUp(self):
        images = patch.object(qt.Artwork, "image", return_value=QPixmap())
        images.start()
        self.addCleanup(images.stop)
        self.window = desktop_checks.DesktopAuditTests.window(self)
        self.window.show()
        self.app.processEvents()
        self.api = self.window.automation

    def send(self, method, **parameters):
        return self.api.dispatch(dict(method=method, **parameters))

    def good(self, method, **parameters):
        response = self.send(method, **parameters)
        self.assertTrue(response["ok"], response)
        return response["result"]

    def page(self, name):
        self.good("click", control="menu_" + name)
        self.app.processEvents()

    def test_every_owned_button_and_field_is_discoverable(self):
        controls = self.api.registry.collect()
        covered = {entry[1] for entry in controls.values()}
        expected = set(self.window.findChildren(QAbstractButton))
        expected.update(self.window.overlays.drawer.findChildren(QAbstractButton))
        self.assertFalse(expected - covered, [(w.text(), w.accessibleName()) for w in expected - covered])
        for key in ("assistant_volume", "assistant_cs_target", "overlay_theme", "overlay_scale", "overlay_preview",
                    "game_overlay_scale", "game_overlay_theme_previous", "game_overlay_theme_next", "game_overlay_expand",
                    "update_notes_1", "update_notes_2", "update_notes_3", "main_scroll"):
            self.assertIn(key, controls)

    def test_find_and_read_return_labels_ranges_values_and_screen_text(self):
        self.page("assistant")
        result = self.good("find", query="Громкость", visibleOnly=True)
        self.assertIn("assistant_volume", [c["id"] for c in result["controls"]])
        field = self.good("read", control="assistant_volume")["data"]
        self.assertEqual((field["minimum"], field["maximum"]), (0, 100))
        self.assertEqual(field["inputType"], "integer")
        text = self.good("read", scope="assistant")["data"]["text"]
        self.assertTrue(any("Голос во время матча" in row["text"] for row in text))

    def test_numeric_set_uses_real_settings_signals_and_rejects_bad_values(self):
        self.page("assistant")
        self.good("set", control="assistant_volume", value=73)
        self.good("set", control="assistant_cs_target", value=8.5)
        self.assertEqual(self.window.settings.value("assistant/volume", type=int), 73)
        self.assertEqual(self.window.settings.value("assistant/cs_target", type=float), 8.5)
        for value in (True, float("nan"), float("inf"), 101, -1, 12.5, 10 ** 1000):
            response = self.send("set", control="assistant_volume", value=value)
            self.assertFalse(response["ok"], response)
        self.assertEqual(self.window.assistant_page.volume.value(), 73)
        self.assertFalse(self.send("set", control="assistant_cs_target", value=7.25)["ok"])

    def test_choice_data_preserve_types_and_checkbox_clicks_are_real_actions(self):
        self.good("set", control="rank_history_queue", value="flex")
        self.assertEqual(self.window.dashboard.queue.currentData(), "flex")
        choice = QComboBox(self.window)
        choice.addItem("Solo", 420)
        choice.addItem("Flex", 440)
        choice.show()
        key = next(k for k, entry in self.api.registry.collect().items() if entry[1] is choice)
        self.good("set", control=key, value=440)
        self.assertEqual(choice.currentData(), 440)
        self.assertFalse(self.send("set", control=key, value="420")["ok"])
        self.page("assistant")
        self.good("set", control="assistant_enabled", value=True)
        self.assertTrue(self.window.settings.value("assistant/enabled", type=bool))
        self.good("set", control="assistant_enabled", value=False)
        self.assertFalse(self.window.settings.value("assistant/enabled", type=bool))

    def test_hidden_and_disabled_controls_are_not_silently_modified(self):
        self.assertEqual(self.send("set", control="assistant_volume", value=55)["error"]["code"], "control_hidden")
        self.good("set", control="assistant_volume", value=55, allowHidden=True)
        self.assertEqual(self.window.home_page, "overview")
        self.window.assistant_page.volume.setEnabled(False)
        self.assertEqual(self.send("set", control="assistant_volume", value=22, allowHidden=True)["error"]["code"], "control_disabled")
        self.assertEqual(self.window.assistant_page.volume.value(), 55)

    def test_new_buttons_are_automatic_and_keep_ids_after_label_changes(self):
        button = QPushButton("Будущая команда", self.window)
        button.show()
        clicked = Mock()
        button.clicked.connect(clicked)
        controls = self.api.registry.collect()
        key = next(k for k, entry in controls.items() if entry[1] is button)
        self.good("click", control=key)
        clicked.assert_called_once()
        button.setText("Команда завершена")
        self.assertIs(self.api.registry.collect()[key][1], button)
        button.setParent(None)
        button.deleteLater()
        self.assertEqual(self.send("click", control=key)["error"]["code"], "unknown_control")

    def matches(self, count=14):
        return [{"id": f"EUW1_{n}", "champion": "Виктор", "queue": 420, "playedAt": n * 1000,
                 "win": True, "kda": [1, 2, 3]} for n in range(count)]

    def test_dynamic_match_buttons_keep_semantic_ids_and_retired_rows_disappear(self):
        self.window.snapshot = {"phase": "Lobby", "home": True,
                                "homeProfile": {"historyAvailable": True, "matches": self.matches()}}
        self.window.paint_snapshot()
        self.page("history")
        key = "history_match_EUW1_0_review"
        self.assertIn(key, self.api.registry.collect())
        with patch.object(qt.QDesktopServices, "openUrl", return_value=True) as opened:
            self.window.settings.setValue("site", "http://127.0.0.1:8000")
            self.good("click", control=key)
            self.assertIn("EUW1_0", opened.call_args.args[0].toString())
        self.good("click", control="show_more_matches")
        self.assertIn("history_match_EUW1_13_review", self.api.registry.collect())
        self.window.snapshot["homeProfile"]["matches"] = [dict(row, win=False) for row in self.matches()]
        self.window.paint_snapshot()  # deleteLater has not run yet: no duplicate IDs.
        self.good("state")
        self.assertIn(key, self.api.registry.collect())

    def test_scroll_and_minimized_window_navigation_do_not_need_mouse_or_activation(self):
        self.page("assistant")
        self.app.processEvents()
        bar = self.window.scroll.verticalScrollBar()
        self.good("scroll", control="main_scroll", value=bar.maximum())
        self.assertEqual(bar.value(), bar.maximum())
        self.good("window", operation="minimize")
        self.app.processEvents()
        self.assertTrue(self.window.isMinimized())
        self.good("click", control="menu_updates")
        self.assertEqual(self.window.home_page, "updates")
        self.good("window", operation="restore")

    def test_dialog_content_and_close_are_available_and_modal_blocks_background_edits(self):
        dialog = QDialog(self.window)
        dialog.setWindowTitle("Проверка диалога")
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Содержимое без скриншота"))
        dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        dialog.show()
        self.addCleanup(dialog.close)
        self.app.processEvents()
        response = self.send("set", control="assistant_volume", value=33, allowHidden=True)
        self.assertEqual(response["error"]["code"], "modal_open")
        window_id = next(key for key, widget in self.api.registry.roots().items() if widget is dialog)
        contents = self.good("read", scope=window_id)["data"]["text"]
        self.assertTrue(any(row["text"] == "Содержимое без скриншота" for row in contents))
        self.good("window", window=window_id, operation="close")
        loop = QEventLoop()
        QTimer.singleShot(160, loop.quit)
        loop.exec()
        self.assertFalse(dialog.isVisible())

    def test_models_and_overlay_position_are_semantic_and_validated(self):
        self.window.snapshot["homeProfile"] = {"matches": self.matches(30), "historyAvailable": True}
        model = self.good("read", model="history", offset=10, limit=5)["data"]
        self.assertEqual((model["loaded"], len(model["matches"])), (30, 5))
        self.assertEqual(model["matches"][0]["id"], "EUW1_10")
        self.assertFalse(self.send("read", model="history", limit=1000)["ok"])
        self.good("overlay_position", overlay="build", x=.2, y=.7)
        self.assertEqual(self.window.overlays.cards["build"].position, (.2, .7))
        self.assertFalse(self.send("overlay_position", overlay="build", x=2, y=0)["ok"])
        self.good("overlay_position", overlay="build", reset=True)
        self.assertIsNone(self.window.overlays.cards["build"].position)

    def test_draft_scope_is_readable_and_imports_keep_normal_locks(self):
        self.window.snapshot = {"phase": "pick", "home": False, "draft": {"gameId": 12}}
        self.window.paint_snapshot()
        self.app.processEvents()
        text = self.good("read", scope="draft")["data"]["text"]
        self.assertTrue(any("Профиль урона" in row["text"] for row in text))
        response = self.send("click", control="import_build", allowHidden=True)
        self.assertEqual(response["error"]["code"], "control_disabled")
        self.window.companion.export.assert_not_called()

    def test_all_voice_examples_and_changelog_links_use_normal_callbacks(self):
        self.page("assistant")
        with patch.object(self.window.assistant, "preview") as preview:
            for key in self.api.registry.collect():
                if key.startswith("assistant_example_"):
                    self.good("click", control=key, allowHidden=True)
            self.assertEqual(preview.call_count, len(self.window.assistant_page.previews))
        from desktop.update_service import Release
        page = self.window.updates_page
        page.releases = [Release("v3.0.0", "Выпуск", "Патчноут", "", "https://github.com/Halches/Lol-stat/releases/tag/v3.0.0", None, 0, None, None)]
        page.render_notes()
        self.page("updates")
        with patch.object(qt.QDesktopServices, "openUrl", return_value=True) as opened:
            self.good("click", control="update_notes_1")
            self.assertIn("v3.0.0", opened.call_args.args[0].toString())

    def test_input_validators_password_redaction_and_enter_submission(self):
        field = QLineEdit(self.window)
        field.setAccessibleName("Число")
        field.setValidator(QIntValidator(0, 100, field))
        field.show()
        key = next(k for k, entry in self.api.registry.collect().items() if entry[1] is field)
        self.assertFalse(self.send("set", control=key, value="invalid")["ok"])
        self.good("set", control=key, value="42")
        submitted = Mock()
        field.returnPressed.connect(submitted)
        self.good("submit", control=key)
        submitted.assert_called_once()
        field.setEchoMode(QLineEdit.EchoMode.Password)
        field.setValidator(None)
        self.good("set", control=key, value="hidden-test-value")
        output = json.dumps(self.good("state"))
        self.assertNotIn("hidden-test-value", output)

    def test_cli_json_value_and_generic_call(self):
        automation = sys.modules[self.api.__class__.__module__]
        cases = [(["set", "assistant_volume", "73", "--json-value"], {"method": "set", "control": "assistant_volume", "value": 73}),
                 (["call", "--json", '{"method":"read","model":"build"}'], {"method": "read", "model": "build"})]
        for args, expected in cases:
            with (patch.object(sys, "argv", ["automation.py", "--pid", "123", *args]),
                  patch.object(automation, "request", return_value={"ok": True, "result": {}}) as request,
                  patch("builtins.print")):
                self.assertEqual(automation.main(), 0)
            request.assert_called_once_with(expected, pid=123)

    def test_executable_client_mode_can_return_json_without_console(self):
        automation = sys.modules[self.api.__class__.__module__]
        with TemporaryDirectory() as directory:
            output = Path(directory) / "response.json"
            with (patch.object(sys, "argv", ["app.exe", "--pid", "123", "state", "--output", str(output)]),
                  patch.object(sys, "stdout", None),
                  patch.object(automation, "request", return_value={"ok": True, "result": {"processId": 123}})):
                self.assertEqual(automation.main(require_pid=True), 0)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["result"]["processId"], 123)


if __name__ == "__main__":
    unittest.main()
