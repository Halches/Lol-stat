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
if __package__:
    from .app_version import VERSION as APP_VERSION
else:
    from app_version import VERSION as APP_VERSION


VERSION = 1
USER_SUFFIX = hashlib.sha256(str(Path.home()).casefold().encode("utf-8")).hexdigest()[:12]
SOCKET_NAME = f"lolhelper-beta-ui-v{VERSION}-{USER_SUFFIX}"
MAX_REQUEST = 8192
TIMEOUT_MS = 3000


def endpoint_for_pid(pid, base=SOCKET_NAME):
    if type(pid) is not int or pid <= 0:
        raise ValueError("PID must be a positive integer.")
    return f"{base}-pid-{pid}"


def schema():
    return {
        "application": "LoL Helper Windows Beta",
        "version": VERSION,
        "endpoint": SOCKET_NAME,
        "instanceEndpointPattern": f"{SOCKET_NAME}-pid-<processId>",
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
            "Use --pid PROCESS_ID to address the GUI process explicitly; it never falls back to the shared endpoint.",
        ],
    }


def failure(code, message):
    return {"ok": False, "error": {"code": code, "message": message}}


def rect(x, y, width, height):
    return {"x": x, "y": y, "width": width, "height": height}


class AutomationServer(QObject):
    def __init__(self, window, name=SOCKET_NAME, *, directory=None):
        super().__init__(window)
        self.window = window
        self.name = name
        self.instance_name = endpoint_for_pid(os.getpid(), name)
        self.controls = {}
        self.server = QLocalServer(self)
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self.server.newConnection.connect(lambda: self._accept(self.server))
        self.instance_server = QLocalServer(self)
        self.instance_server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self.instance_server.newConnection.connect(lambda: self._accept(self.instance_server))
        self.directory = Path(directory) if directory is not None else (
            Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.GenericDataLocation)) / "LoLHelper" / "automation")
        self.lock = QLockFile(str(self.directory / (name + ".lock")))
        self.instance_lock = QLockFile(str(self.directory / (self.instance_name + ".lock")))

    def add(self, key, label, widget, kind):
        widget.setObjectName(key)
        widget.setAccessibleName(label)
        self.controls[key] = (label, widget, kind)

    def start(self):
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
        except OSError:
            return False
        if not self._listen(self.instance_server, self.instance_lock, self.instance_name):
            return False
        # The shared endpoint is optional compatibility, never a prerequisite
        # for addressing this instance. Another application may own it.
        self._listen(self.server, self.lock, self.name)
        return True

    @staticmethod
    def _listen(server, lock, name):
        if server.isListening():
            return True
        if not lock.tryLock(0):
            return False
        if os.name != "nt":
            QLocalServer.removeServer(name)
        if not server.listen(name):
            lock.unlock()
            return False
        return True

    def close(self):
        for server, lock in ((self.instance_server, self.instance_lock), (self.server, self.lock)):
            server.close()
            if lock.isLocked():
                lock.unlock()

    def identity(self):
        return {"processId": os.getpid(), "executable": str(Path(sys.executable).resolve()),
                "appVersion": APP_VERSION, "instanceEndpoint": self.instance_name,
                "legacyEndpoint": self.name if self.server.isListening() else None}

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
            **self.identity(),
            "window": {"title": self.window.windowTitle(), "visible": visible,
                       "minimized": self.window.isMinimized(), "active": self.window.isActiveWindow(),
                       "bounds": rect(origin.x(), origin.y(), self.window.width(), self.window.height())},
            "game": {"phase": self.window.snapshot.get("phase"), "matchId": self.window.snapshot.get("matchId")},
            "status": " · ".join(filter(None, (self.window.headline.text(), self.window.status.text()))),
            "notice": self.window.notice.text(),
            "previewMessage": self.window.preview_message.text(),
            "previewInProgress": self.window.preview_job is not None,
            "updates": {"version": self.window.updates_page.version,
                        "available": getattr(self.window.updates_page.available, "version", None),
                        "busy": self.window.updates_page.job is not None,
                        "status": self.window.updates_page.status.text()},
            "latestMatch": self.window.latest_match if self.window.is_home() else None,
            "homePage": self.window.home_page if self.window.is_home() else None,
            "draftTab": self.window.draft_screen.tab if self.window.draft_active else None,
            "importInProgress": self.window.export_job is not None,
            "overlayVisible": self.window.overlays.visible(),
            "controls": controls,
        }

    def dispatch(self, request, *, endpoint=None):
        if not isinstance(request, dict):
            return failure("invalid_request", "Send a JSON object.")
        if "processId" in request and (type(request["processId"]) is not int or request["processId"] != os.getpid()):
            return failure("wrong_process", "This command targets another process. Read state using the correct --pid.")
        method = request.get("method")
        if method == "describe":
            return {"ok": True, "result": dict(schema(), endpoint=endpoint or self.name,
                                               controls=self.catalog(), **self.identity())}
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

    def _accept(self, server):
        while server.hasPendingConnections():
            socket = server.nextPendingConnection()
            socket.setProperty("automationEndpoint", server.serverName())
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
                response = self.dispatch(request, endpoint=socket.property("automationEndpoint"))
        else:
            return
        socket.setProperty("automationHandled", True)
        socket.write((json.dumps(response, ensure_ascii=False) + "\n").encode("utf-8"))
        socket.disconnectFromServer()


def request(message, name=SOCKET_NAME, *, pid=None):
    if not isinstance(message, dict):
        return failure("invalid_request", "Send a JSON object.")
    if pid is not None:
        try:
            name = endpoint_for_pid(pid, name)
        except ValueError as error:
            return failure("invalid_pid", str(error))
        message = dict(message, processId=pid)
    socket = QLocalSocket()
    socket.connectToServer(name)
    if not socket.waitForConnected(TIMEOUT_MS):
        return failure("not_connected", f"LoL Helper PID {pid} is not available; no other instance was used."
                       if pid is not None else "Open LoL Helper Beta on this computer and try again.")
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
            response = json.loads(bytes(socket.readLine()).decode("utf-8"))
            if not isinstance(response, dict) or type(response.get("ok")) is not bool:
                return failure("invalid_response", "LoL Helper returned an invalid response.")
            if pid is not None and response["ok"] and (not isinstance(response.get("result"), dict)
                                                       or response["result"].get("processId") != pid):
                return failure("wrong_process", "The responding application does not match the requested PID.")
            return response
        except (ValueError, RecursionError):
            return failure("invalid_response", "LoL Helper returned an invalid response.")
    return failure("no_response", "LoL Helper did not reply in time.")


def positive_pid(value):
    try:
        pid = int(value)
        endpoint_for_pid(pid)
        return pid
    except ValueError:
        raise argparse.ArgumentTypeError("PID must be a positive integer.") from None


def main():
    parser = argparse.ArgumentParser(description="Inspect and control a running LoL Helper Beta for Windows.")
    parser.add_argument("--pid", type=positive_pid, help="GUI process ID; no fallback to another instance")
    commands = parser.add_subparsers(dest="method", required=True)
    commands.add_parser("schema", help="Print the API contract without starting the app")
    commands.add_parser("describe", help="List the controls and their supported actions")
    commands.add_parser("state", help="Read the UI state and the control positions")
    click = commands.add_parser("click", help="Click a visible, enabled button by control ID")
    click.add_argument("control")
    edit = commands.add_parser("set", help="Set a field by control ID")
    edit.add_argument("control")
    edit.add_argument("value", help="Enter true or false for a checkbox, or text for a text field")
    for command in commands.choices.values():
        command.add_argument("--pid", type=positive_pid, default=argparse.SUPPRESS,
                             help="GUI process ID; no fallback to another instance")
    args = vars(parser.parse_args())
    pid = args.pop("pid", None)
    sys.stdout.reconfigure(encoding="utf-8")
    if args["method"] == "schema":
        print(json.dumps(dict(schema(), endpoint=endpoint_for_pid(pid) if pid is not None else SOCKET_NAME),
                         ensure_ascii=False, indent=2))
        return 0
    if args["method"] == "set" and args["value"] in ("true", "false"):
        args["value"] = args["value"] == "true"
    _application = QCoreApplication.instance() or QCoreApplication([])
    response = request(args, pid=pid)
    print(json.dumps(response, ensure_ascii=False, indent=2))
    return 0 if response["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
