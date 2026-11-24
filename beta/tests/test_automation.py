"""Two real Qt processes, shared endpoint contention and explicit PID isolation."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

from PySide6.QtWidgets import QApplication
from automation_bundle import automation_module
automation = automation_module()
from desktop.app_version import VERSION


class InstanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.temporary = TemporaryDirectory(prefix="LoLHelper-automation-")
        cls.root = Path(cls.temporary.name)
        cls.base = "lolhelper-instance-test-" + uuid4().hex
        cls.processes = []
        cls.identities = []
        try:
            for marker in ("first", "second"):
                process = subprocess.Popen([sys.executable, str(Path(__file__).with_name("automation_fixture.py")),
                                            cls.base, str(cls.root), marker],
                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                cls.processes.append(process)
                deadline = time.monotonic() + 15
                ready = cls.root / (marker + ".ready")
                while not ready.exists():
                    if process.poll() is not None or time.monotonic() > deadline:
                        raise AssertionError(f"Disposable {marker} Qt server failed to start")
                    time.sleep(.03)
                cls.identities.append(json.loads(ready.read_text(encoding="utf-8")))
        except Exception:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        for marker in ("first", "second"):
            (cls.root / (marker + ".stop")).touch()
        for process in cls.processes:
            try:
                process.wait(5)
            except subprocess.TimeoutExpired:
                process.terminate()  # Only this test's child, never another app.
                process.wait(5)
        cls.temporary.cleanup()

    def test_both_instances_are_addressable_when_global_lock_is_taken(self):
        self.assertTrue(self.identities[0]["legacy"])
        self.assertFalse(self.identities[1]["legacy"])
        for marker, identity in zip(("first", "second"), self.identities):
            with self.subTest(marker=marker):
                response = automation.request({"method": "state"}, self.base, pid=identity["pid"])
                self.assertTrue(response["ok"], response)
                state = response["result"]
                self.assertEqual(state["processId"], identity["pid"])
                self.assertEqual(state["homePage"], marker)
                self.assertEqual(state["appVersion"], VERSION)
                self.assertEqual(Path(state["executable"]).resolve(), Path(sys.executable).resolve())
                self.assertEqual(state["instanceEndpoint"], identity["instance"])

    def test_shared_endpoint_remains_on_original_owner(self):
        state = automation.request({"method": "state"}, self.base)
        self.assertTrue(state["ok"], state)
        self.assertEqual(state["result"]["processId"], self.identities[0]["pid"])

    def test_describe_identifies_the_selected_server(self):
        second = self.identities[1]
        response = automation.request({"method": "describe"}, self.base, pid=second["pid"])
        result = response["result"]
        self.assertEqual(result["endpoint"], second["instance"])
        self.assertEqual(result["processId"], second["pid"])
        self.assertEqual(result["appVersion"], VERSION)
        self.assertEqual([c["id"] for c in result["controls"]], ["second"])

    def test_explicit_missing_pid_does_not_fall_back_to_running_owner(self):
        response = automation.request({"method": "state"}, self.base, pid=2_000_000_000)
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "not_connected")
        self.assertIn("no other instance", response["error"]["message"])

    def test_command_for_another_pid_is_rejected_before_clicking(self):
        first, second = self.identities
        response = automation.request({"method": "click", "control": "first", "processId": second["pid"]},
                                      name=first["instance"])
        self.assertEqual(response["error"]["code"], "wrong_process")
        state = automation.request({"method": "state"}, self.base, pid=first["pid"])
        self.assertTrue(state["ok"])
        self.assertEqual(state["result"]["notice"], "")
        # A valid subsequent command still goes to the selected second server.
        result = automation.request({"method": "click", "control": "second"}, self.base, pid=second["pid"])
        self.assertTrue(result["ok"])
        self.assertEqual(result["result"]["processId"], second["pid"])
        self.assertEqual(result["result"]["notice"], "1")


class ClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_client_refuses_identity_mismatch_or_old_response_without_identity(self):
        for result in ({"processId": 34}, {"controls": []}):
            socket = Mock()
            socket.waitForConnected.return_value = True
            socket.canReadLine.return_value = True
            socket.readLine.return_value = json.dumps({"ok": True, "result": result}).encode()
            with patch.object(automation, "QLocalSocket", return_value=socket):
                response = automation.request({"method": "state"}, pid=12)
            socket.connectToServer.assert_called_once_with(automation.endpoint_for_pid(12))
            self.assertEqual(response["error"]["code"], "wrong_process")

    def test_bad_pid_is_rejected_without_opening_a_socket(self):
        for pid in (True, 0, -1, "12"):
            with patch.object(automation, "QLocalSocket") as socket:
                response = automation.request({"method": "state"}, pid=pid)
            self.assertEqual(response["error"]["code"], "invalid_pid")
            socket.assert_not_called()

    def test_cli_pid_before_or_after_command_targets_exactly_that_pid(self):
        for arguments in (["--pid", "123", "state"], ["state", "--pid", "123"]):
            with (patch.object(sys, "argv", ["automation.py", *arguments]),
                  patch.object(automation, "request", return_value={"ok": True, "result": {}}) as request,
                  patch("builtins.print")):
                self.assertEqual(automation.main(), 0)
            request.assert_called_once_with({"method": "state"}, pid=123)


if __name__ == "__main__":
    unittest.main()
