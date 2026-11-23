"""Discover and operate the LoL Helper desktop UI over a local Qt socket."""

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QLockFile, QObject, QPoint, QStandardPaths, QTimer
from PySide6.QtNetwork import QLocalServer, QLocalSocket


VERSION = 1
USER_SUFFIX = hashlib.sha256(str(Path.home()).casefold().encode("utf-8")).hexdigest()[:12]
SOCKET_NAME = f"lolhelper-beta-ui-v{VERSION}-{USER_SUFFIX}"
MAX_REQUEST = 8192
TIMEOUT_MS = 3000


def schema():
    return {
        "application": "LoL Helper Windows Beta",
        "version": VERSION,
        "endpoint": SOCKET_NAME,
        "transport": "Qt local socket, one UTF-8 JSON request and response per connection, each terminated by LF",
        "methods": {
            "describe": {"request": {"method": "describe"}, "result": "Protocol and live control catalog"},
            "state": {"request": {"method": "state"}, "result": "Current window, game phase, and UI controls"},
            "click": {"request": {"method": "click", "control": "button ID"},
                      "result": "Dispatch a visible, enabled button and return the updated state"},
            "set": {"request": {"method": "set", "control": "field ID", "value": "See inputType in state"},
                    "result": "Edit a visible, enabled field and return the updated state"},
        },
        "response": {"success": {"ok": True, "result": {}},
                     "failure": {"ok": False, "error": {"code": "stable identifier", "message": "detail"}}},
        "coordinates": {"window": "Screen coordinates", "control": "Relative to window client area",
                        "unit": "Qt device-independent pixels"},
        "notes": [
            "Read state before acting. Use control IDs to act without screen coordinates.",
            "Check state after a click for app validation messages or a pending import.",
            "Use the Save button to persist edited settings.",
        ],
    }


def failure(code, message):
    return {"ok": False, "error": {"code": code, "message": message}}


def rect(x, y, width, height):
    return {"x": x, "y": y, "width": width, "height": height}


class AutomationServer(QObject):
    def __init__(self, window, name=SOCKET_NAME):
        super().__init__(window)
        self.window = window
        self.name = name
        self.controls = {}
        self.server = QLocalServer(self)
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self.server.newConnection.connect(self._accept)
        directory = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.GenericDataLocation))
        self.directory = directory / "LoLHelper" / "automation"
        self.lock = QLockFile(str(self.directory / (name + ".lock")))

    def add(self, key, label, widget, kind):
        widget.setObjectName(key)
        widget.setAccessibleName(label)
        self.controls[key] = (label, widget, kind)

    def start(self):
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
        except OSError:
            return False
        if not self.lock.tryLock(0):
            return False
        if os.name != "nt":
            QLocalServer.removeServer(self.name)
        if not self.server.listen(self.name):
            self.lock.unlock()
            return False
        return True

    def close(self):
        self.server.close()
        if self.lock.isLocked():
            self.lock.unlock()

    def catalog(self):
        return [
            {"id": key, "label": label, "kind": kind,
             "actions": ["click"] if kind == "button" else ["set"],
             **({"inputType": "boolean" if kind == "checkbox" else "string"} if kind != "button" else {}),
             **({"options": [{"value": widget.itemData(i), "label": widget.itemText(i)}
                             for i in range(widget.count())]} if kind == "choice" else {})}
            for key, (label, widget, kind) in self.controls.items()
        ]

    def state(self):
        origin = self.window.mapToGlobal(QPoint())
        visible = self.window.isVisible() and not self.window.isMinimized()
        controls = self.catalog()
        for entry in controls:
            _, widget, kind = self.controls[entry["id"]]
            entry["visible"] = visible and widget.isVisibleTo(self.window)
            entry["enabled"] = widget.isEnabled()
            if entry["visible"]:
                position = widget.mapTo(self.window, QPoint())
                entry["bounds"] = rect(position.x(), position.y(), widget.width(), widget.height())
            if kind == "checkbox":
                entry["value"] = widget.isChecked()
            elif kind == "choice":
                entry["value"] = widget.currentData()
            elif kind == "text":
                entry["value"] = widget.text()
                if entry["id"] == "site" and widget.text().strip():
                    try:
                        entry["value"] = self.window.validated_site()
                    except ValueError:
                        entry["value"] = None
        return {
            "version": VERSION,
            "window": {"title": self.window.windowTitle(), "visible": visible,
                       "minimized": self.window.isMinimized(), "active": self.window.isActiveWindow(),
                       "bounds": rect(origin.x(), origin.y(), self.window.width(), self.window.height())},
            "game": {"phase": self.window.snapshot.get("phase"), "matchId": self.window.snapshot.get("matchId")},
            "status": " · ".join(filter(None, (self.window.headline.text(), self.window.status.text()))),
            "notice": self.window.notice.text(),
            "previewMessage": self.window.preview_message.text(),
            "previewInProgress": self.window.preview_job is not None,
            "latestMatch": self.window.latest_match if self.window.is_home() else None,
            "homePage": self.window.home_page if self.window.is_home() else None,
            "draftTab": self.window.draft_screen.tab if self.window.draft_active else None,
            "importInProgress": self.window.export_job is not None,
            "overlayVisible": self.window.overlay.isVisible(),
            "controls": controls,
        }

    def dispatch(self, request):
        if not isinstance(request, dict):
            return failure("invalid_request", "Send a JSON object.")
        method = request.get("method")
        if method == "describe":
            return {"ok": True, "result": dict(schema(), endpoint=self.name, controls=self.catalog())}
        if method == "state":
            return {"ok": True, "result": self.state()}
        if method not in ("click", "set"):
            return failure("unknown_method", "Use describe to discover the supported methods.")
        key = request.get("control")
        if not isinstance(key, str) or key not in self.controls:
            return failure("unknown_control", "Use state to discover the current control IDs.")
        _, widget, kind = self.controls[key]
        if not self.window.isVisible() or self.window.isMinimized() or not widget.isVisibleTo(self.window):
            return failure("control_hidden", "This control is not visible in the current window.")
        if not widget.isEnabled():
            return failure("control_disabled", "This control is disabled in the current state.")
        if method == "click" and kind == "button":
            widget.click()
        elif method == "set" and kind == "checkbox" and type(request.get("value")) is bool:
            widget.setChecked(request["value"])
        elif method == "set" and kind == "text" and isinstance(request.get("value"), str):
            widget.setText(request["value"])
        elif method == "set" and kind == "choice" and isinstance(request.get("value"), str):
            index = widget.findData(request["value"])
            if index < 0:
                return failure("invalid_value", "Use one of the values in the control options.")
            widget.setCurrentIndex(index)
        else:
            return failure("invalid_action", "Use describe for the control action and input type.")
        if self.window.scroll.widget().isAncestorOf(widget):
            self.window.scroll.ensureWidgetVisible(widget)
        return {"ok": True, "result": self.state()}

    def _accept(self):
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            socket.setReadBufferSize(MAX_REQUEST + 1)
            timer = QTimer(socket)
            timer.setSingleShot(True)
            timer.timeout.connect(socket.abort)
            timer.start(TIMEOUT_MS)
            socket.disconnected.connect(socket.deleteLater)
            socket.readyRead.connect(lambda socket=socket: self._read(socket))
            self._read(socket)

    def _read(self, socket):
        if socket.property("automationHandled"):
            return
        if socket.bytesAvailable() > MAX_REQUEST:
            response = failure("request_too_large", "Requests may be at most 8192 bytes.")
        elif socket.canReadLine():
            try:
                request = json.loads(bytes(socket.readLine()).decode("utf-8"))
            except (ValueError, RecursionError):
                response = failure("invalid_json", "Send a UTF-8 JSON object on one line.")
            else:
                response = self.dispatch(request)
        else:
            return
        socket.setProperty("automationHandled", True)
        socket.write((json.dumps(response, ensure_ascii=False) + "\n").encode("utf-8"))
        socket.disconnectFromServer()


def request(message, name=SOCKET_NAME):
    socket = QLocalSocket()
    socket.connectToServer(name)
    if not socket.waitForConnected(TIMEOUT_MS):
        return failure("not_connected", "Open LoL Helper Beta on this computer and try again.")
    data = (json.dumps(message, ensure_ascii=False) + "\n").encode("utf-8")
    if len(data) > MAX_REQUEST:
        return failure("request_too_large", "Requests may be at most 8192 bytes.")
    socket.write(data)
    socket.flush()
    deadline = time.monotonic() + TIMEOUT_MS / 1000
    while not socket.canReadLine():
        remaining = int((deadline - time.monotonic()) * 1000)
        if remaining <= 0 or not socket.waitForReadyRead(remaining):
            break
    if socket.canReadLine():
        try:
            return json.loads(bytes(socket.readLine()).decode("utf-8"))
        except (ValueError, RecursionError):
            return failure("invalid_response", "LoL Helper returned an invalid response.")
    return failure("no_response", "LoL Helper did not reply in time.")


def main():
    parser = argparse.ArgumentParser(description="Inspect and control a running LoL Helper Beta for Windows.")
    commands = parser.add_subparsers(dest="method", required=True)
    commands.add_parser("schema", help="Print the API contract without starting the app")
    commands.add_parser("describe", help="List the controls and their supported actions")
    commands.add_parser("state", help="Read the UI state and the control positions")
    click = commands.add_parser("click", help="Click a visible, enabled button by control ID")
    click.add_argument("control")
    edit = commands.add_parser("set", help="Set a field by control ID")
    edit.add_argument("control")
    edit.add_argument("value", help="Enter true or false for a checkbox, or text for a text field")
    args = vars(parser.parse_args())
    sys.stdout.reconfigure(encoding="utf-8")
    if args["method"] == "schema":
        print(json.dumps(schema(), ensure_ascii=False, indent=2))
        return 0
    if args["method"] == "set" and args["value"] in ("true", "false"):
        args["value"] = args["value"] == "true"
    _application = QCoreApplication([])
    response = request(args)
    print(json.dumps(response, ensure_ascii=False, indent=2))
    return 0 if response["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
