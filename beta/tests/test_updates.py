"""Update protocol, file replacement and real Qt controls, without GitHub writes."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from concurrent.futures import Future
from dataclasses import replace
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from desktop import update_service as service
from desktop.update_page import UpdatePage
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication


EXE = b"MZ" + b"test executable" * 100
DIGEST = sha256(EXE).hexdigest()


def raw_release(version="v3.1.0", **changes):
    return {"tag_name": version, "name": "LoL Helper " + str(version), "body": "Исправления\n" * 80,
            "published_at": "2026-11-24T09:00:00Z", "assets": [
                {"name": service.ASSET_NAME, "browser_download_url": service.release_asset_url(version, service.ASSET_NAME),
                 "size": len(EXE), "digest": "sha256:" + DIGEST}], **changes}


def release(**changes):
    return replace(service.parse_release(raw_release()), **changes)


class ReleaseTests(unittest.TestCase):
    def test_strict_versions_and_non_application_tags(self):
        for tag in ("voices", "silero", "v2.2.0-beta", "v02.2.0", None):
            self.assertIsNone(service.parse_release(raw_release(tag)))
        for fields in ({"draft": True}, {"prerelease": True}):
            self.assertIsNone(service.parse_release(raw_release(**fields)))
        self.assertEqual(service.version_number("v2.10.0"), (2, 10, 0))

    def test_fetches_three_stable_releases_and_ignores_service_tags(self):
        payload = [raw_release("voices"), raw_release("v2.0.9"), raw_release("v2.1.0"), raw_release("v2.0.8"),
                   raw_release("v9.0.0", prerelease=True)]
        with patch.object(service, "open_download", return_value=BytesIO(json.dumps(payload).encode())):
            self.assertEqual([r.version for r in service.fetch_releases()], ["v2.1.0", "v2.0.9", "v2.0.8"])

    def test_invalid_payload_does_not_look_like_empty_history(self):
        with patch.object(service, "open_download", return_value=BytesIO(b'{"message":"unavailable"}')):
            with self.assertRaises(service.UpdateError):
                service.fetch_releases()

    def test_untrusted_or_other_exe_is_not_selected(self):
        row = raw_release()
        row["assets"][0]["browser_download_url"] = "https://example.com/LoLHelper.exe"
        self.assertIsNone(service.parse_release(row).download)
        row["assets"][0]["name"] = "other.exe"
        self.assertIsNone(service.parse_release(row).download)

    def test_long_notes_are_bounded_short_notes_unchanged(self):
        self.assertEqual(service.note_excerpt("Краткое исправление"), ("Краткое исправление", False))
        excerpt, shortened = service.note_excerpt("Длинный патчноут\n" * 200)
        self.assertTrue(shortened)
        self.assertLessEqual(len(excerpt), 651)
        self.assertLessEqual(len(excerpt.splitlines()), 9)

    def test_digest_falls_back_to_published_checksums(self):
        item = release(digest=None, checksum_url=service.release_asset_url("v3.1.0", "SHA256SUMS.txt"))
        with patch.object(service, "open_download", return_value=BytesIO(f"{DIGEST}  LoLHelper.exe\n".encode())):
            self.assertEqual(service.expected_digest(item), DIGEST)
        with self.assertRaises(service.UpdateError):
            service.expected_digest(replace(item, checksum_url=None))

    def test_download_verifies_size_hash_and_progress(self):
        with TemporaryDirectory() as directory, patch.object(service, "update_root", return_value=Path(directory)):
            progress = Mock()
            with patch.object(service, "open_download", return_value=BytesIO(EXE)):
                result = service.download_release(release(), progress)
            self.assertEqual(Path(result["candidate"]).read_bytes(), EXE)
            progress.assert_called_with(len(EXE), len(EXE))
            for data in (b"bad", EXE[:-1], b"ZZ" + EXE[2:], EXE + b"extra"):
                with self.subTest(data=len(data)), patch.object(service, "open_download", return_value=BytesIO(data)):
                    with self.assertRaises(service.UpdateError):
                        service.download_release(release())
            self.assertFalse(list(Path(directory).rglob("*.part")))

    def test_invalid_digest_rejects_same_size_executable(self):
        with TemporaryDirectory() as directory, patch.object(service, "update_root", return_value=Path(directory)), \
                patch.object(service, "open_download", return_value=BytesIO(b"MZ" + b"x" * (len(EXE) - 2))):
            with self.assertRaises(service.UpdateError):
                service.download_release(release())


class InstallationTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory(prefix="Обновление с пробелами ")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.cache = self.root / "cache"
        self.cache.mkdir()
        self.target = self.root / "LoL Helper & test.exe"
        self.target.write_bytes(b"MZprevious")
        self.candidate = self.cache / "new.exe"
        self.candidate.write_bytes(EXE)
        self.manifest = {"target": str(self.target), "folder": str(self.cache), "candidate": str(self.candidate),
                         "digest": DIGEST, "size": len(EXE)}

    def test_replaces_atomically_from_target_volume_and_preserves_old_file(self):
        launch = Mock()
        actual_replace = os.replace
        def on_replace(source, target):
            self.assertEqual(Path(source).parent, self.target.parent)
            actual_replace(source, target)
        with patch.object(service.os, "replace", side_effect=on_replace):
            service.replace_and_restart(self.manifest, launch=launch)
        self.assertEqual(self.target.read_bytes(), EXE)
        self.assertEqual((self.cache / "previous.exe").read_bytes(), b"MZprevious")
        self.assertEqual(launch.call_args.args[0][0], str(self.target))
        self.assertEqual(launch.call_args.kwargs["env"]["PYINSTALLER_RESET_ENVIRONMENT"], "1")
        self.assertFalse(list(self.root.glob(".lolhelper-update-*")))

    def test_launch_failure_rolls_back_without_changing_user_data(self):
        settings = self.root / "settings.ini"
        settings.write_text("user preferences")
        with self.assertRaises(service.UpdateError):
            service.replace_and_restart(self.manifest, launch=Mock(side_effect=OSError("launch failed")))
        self.assertEqual(self.target.read_bytes(), b"MZprevious")
        self.assertEqual(settings.read_text(), "user preferences")

    def test_corrupt_candidate_never_replaces_old_application(self):
        self.candidate.write_bytes(b"MZcorrupt")
        with self.assertRaises(service.UpdateError):
            service.replace_and_restart(self.manifest, launch=Mock())
        self.assertEqual(self.target.read_bytes(), b"MZprevious")

    def test_os_launch_error_restores_previous_exe(self):
        with patch.object(service.subprocess, "Popen", side_effect=OSError("not a valid Win32 application")):
            with self.assertRaisesRegex(service.UpdateError, "Восстановлена"):
                service.replace_and_restart(self.manifest)
        self.assertEqual(self.target.read_bytes(), b"MZprevious")

    def test_clears_inherited_pyinstaller_environment(self):
        with patch.dict(os.environ, {"_PYI_APPLICATION_HOME_DIR": "old", "_MEIPASS2": "old", "KEEP_ME": "value"}):
            env = service.clean_environment()
        self.assertNotIn("_PYI_APPLICATION_HOME_DIR", env)
        self.assertNotIn("_MEIPASS2", env)
        self.assertEqual(env["KEEP_ME"], "value")


class PageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def page(self, running=False):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        settings = QSettings(str(Path(temporary.name) / "settings.ini"), QSettings.Format.IniFormat)
        page = UpdatePage(settings, lambda: True, running=running)
        self.addCleanup(page.close)
        return page

    def complete(self, page, operation, result=None, error=None):
        pending = Future()
        pending.set_exception(error) if error else pending.set_result(result)
        page.operation, page.job = operation, pending
        page.finish()

    def test_startup_and_periodic_timers_and_shutdown(self):
        page = self.page(running=True)
        self.assertTrue(page.start_timer.isActive())
        self.assertEqual(page.start_timer.interval(), 1000)
        self.assertTrue(page.check_timer.isActive())
        self.assertEqual(page.check_timer.interval(), 15 * 60 * 1000)
        page.close()
        self.assertFalse(page.check_timer.isActive())
        self.assertFalse(page.start_timer.isActive())

    def test_button_changes_and_three_notes_are_truncated(self):
        page = self.page()
        self.assertEqual(page.action.text(), "Проверить обновления")
        releases = [release(version=f"v3.{n}.0") for n in (4, 3, 2)]
        self.complete(page, "check", releases)
        self.assertEqual(page.action.text(), "Обновить")
        self.assertEqual(page.available.version, "v3.4.0")
        for card, title, date, body, link in page.notes:
            self.assertFalse(card.isHidden())
            self.assertIn("сокращено", date.text())
            self.assertLessEqual(len(body.text()), 651)
            self.assertFalse(link.isHidden())
        self.assertTrue(page.settings.value("updates/releases"))

    def test_startup_and_open_application_discover_releases_without_user_click(self):
        page = self.page(running=True)
        for timer, version in ((page.start_timer, "v3.1.0"), (page.check_timer, "v3.2.0")):
            with patch.object(service, "fetch_releases", return_value=[release(version=version)]):
                timer.timeout.emit()
                page.job.result(timeout=2)
                page.finish()
            self.assertEqual(page.available.version, version)
            self.assertEqual(page.action.text(), "Обновить")

    def test_no_downgrade_or_false_update_for_missing_asset(self):
        page = self.page()
        for result in ([release(version="v1.9.0")], [release(version=page.version)], [release(download=None)]):
            self.complete(page, "check", result)
            self.assertIsNone(page.available)
            self.assertEqual(page.action.text(), "Проверить обновления")

    def test_failed_refresh_keeps_previous_notes_and_offer(self):
        page = self.page()
        self.complete(page, "check", [release()])
        self.complete(page, "check", error=OSError("offline"))
        self.assertEqual(len(page.releases), 1)
        self.assertIsNotNone(page.available)
        self.assertEqual(page.action.text(), "Обновить")
        self.assertIn("Не удалось", page.status.text())

    def test_download_and_restart_are_separate_and_game_blocks_restart(self):
        page = self.page()
        self.complete(page, "download", {"version": "v3.1.0"})
        self.assertEqual(page.action.text(), "Перезапустить и обновить")
        page.can_restart = lambda: False
        with patch.object(service, "launch_installer") as installer:
            page.activate()
        installer.assert_not_called()
        self.assertIn("Завершите", page.status.text())

    def test_retry_recovers_after_network_failure(self):
        page = self.page()
        self.complete(page, "check", error=OSError())
        self.assertTrue(page.action.isEnabled())
        self.complete(page, "check", [release()])
        self.assertEqual(page.action.text(), "Обновить")


if __name__ == "__main__":
    unittest.main()
