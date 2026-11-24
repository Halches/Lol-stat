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
from PySide6.QtWidgets import QDialog
if __package__:
    from .app_version import VERSION as APP_VERSION
    from .ui_api import UIError, UIRegistry, numeric
else:
    from app_version import VERSION as APP_VERSION
    from ui_api import UIError, UIRegistry, numeric


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
        "capabilities": {"automaticControls": True, "typedInputs": True, "backgroundOperations": True,
                         "models": ["connection", "navigation", "profile", "history", "draft", "build", "updates", "overlays", "assistant"]},
        "transport": "Qt local socket, one UTF-8 JSON request and response per connection, each terminated by LF",
        "methods": {
            "describe": {"request": {"method": "describe"}, "result": "Protocol and live control catalog"},
            "state": {"request": {"method": "state"}, "result": "Current window, game phase, and UI controls"},
            "click": {"request": {"method": "click", "control": "button ID"},
                      "result": "Dispatch a visible, enabled button and return the updated state"},
            "set": {"request": {"method": "set", "control": "field ID", "value": "See inputType in state"},
                    "result": "Edit a visible, enabled field and return the updated state"},
            "select": {"request": {"method": "select", "control": "choice ID", "index": 0},
                       "result": "Choose an enabled dropdown option by index or typed value"},
            "read": {"request": {"method": "read", "model": "build"},
                     "result": "Read a control, screen text, or profile/history/draft/build/updates/overlays model"},
            "find": {"request": {"method": "find", "query": "громкость", "visibleOnly": True},
                     "result": "Discover controls by label, ID or tooltip; optional scope/page filter"},
            "focus": {"request": {"method": "focus", "control": "field ID"}, "result": "Focus an application control"},
            "submit": {"request": {"method": "submit", "control": "text field ID"}, "result": "Invoke the field's Enter action"},
            "scroll": {"request": {"method": "scroll", "control": "scroll area ID", "axis": "vertical", "value": 0},
                       "result": "Scroll to a value within the reported range"},
            "window": {"request": {"method": "window", "window": "main", "operation": "restore"},
                       "result": "Read/restore/activate/minimize/resize/close an owned main window or dialog"},
            "overlay_position": {"request": {"method": "overlay_position", "overlay": "build", "x": 0.1, "y": 0.2},
                                 "result": "Set a draggable overlay position (0..1), or reset=true"},
        },
        "response": {"success": {"ok": True, "result": {}},
                     "failure": {"ok": False, "error": {"code": "stable identifier", "message": "detail"}}},
        "coordinates": {"window": "Screen coordinates", "control": "Relative to window client area",
                        "unit": "Qt device-independent pixels"},
        "notes": [
            "Read state before acting. Use control IDs to act without screen coordinates.",
            "Check state after a click for app validation messages or a pending import.",
            "save_settings applies the site address. Voice and overlay settings are saved immediately by their normal UI handlers.",
            "Use --pid PROCESS_ID to address the GUI process explicitly; it never falls back to the shared endpoint.",
            "describe/state accept query, scope and visibleOnly filters. Read control actions, values, options and ranges before acting.",
            "All application buttons and input controls are discovered automatically, including dynamic match rows and dialogs.",
            "Explicit IDs are stable; auto_* IDs are valid for this widget lifetime. Rediscover after replacing a screen.",
            "allowHidden=true explicitly permits background operations. Disabled controls and modal dialogs remain protected.",
            "Boolean and numeric values are JSON values; CLI set supports --json-value, and call accepts a complete JSON request.",
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
        self.registry = UIRegistry(window, self.controls)
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

    def start(self, *, legacy=True):
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
        except OSError:
            return False
        if not self._listen(self.instance_server, self.instance_lock, self.instance_name):
            return False
        # The shared endpoint is optional compatibility, never a prerequisite
        # for addressing this instance. Another application may own it.
        if legacy:
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

    def catalog(self, request=None):
        return self.registry.catalog(request)

    def state(self, request=None):
        origin = self.window.mapToGlobal(QPoint())
        visible = self.window.isVisible() and not self.window.isMinimized()
        controls = self.catalog(request)
        texts = self.registry.texts((request or {}).get("scope"))
        return {
            "version": VERSION,
            **self.identity(),
            "window": {"title": self.window.windowTitle(), "visible": visible,
                       "minimized": self.window.isMinimized(), "active": self.window.isActiveWindow(),
                       "bounds": rect(origin.x(), origin.y(), self.window.width(), self.window.height())},
            "game": {"phase": self.window.snapshot.get("phase"), "matchId": self.window.snapshot.get("matchId"),
                     "queueId": self.window.snapshot.get("queueId")},
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
            "connection": self.read_model({"model": "connection"}),
            "draftTab": self.window.draft_screen.tab if self.window.draft_active else None,
            "importInProgress": self.window.export_job is not None,
            "overlayVisible": self.window.overlays.visible(),
            "controls": controls,
            "windows": self.registry.windows(),
            "screenText": texts[:200],
            "screenTextTruncated": len(texts) > 200,
            "roleChangeInProgress": bool(getattr(self.window, "role_change_pending", False)),
        }

    def dispatch(self, request, *, endpoint=None):
        if not isinstance(request, dict):
            return failure("invalid_request", "Send a JSON object.")
        if "processId" in request and (type(request["processId"]) is not int or request["processId"] != os.getpid()):
            return failure("wrong_process", "This command targets another process. Read state using the correct --pid.")
        method = request.get("method")
        try:
            if method in ("describe", "find"):
                return {"ok": True, "result": dict(schema(), endpoint=endpoint or self.name,
                                                   controls=self.catalog(request), windows=self.registry.windows(), **self.identity())}
            if method == "state":
                return {"ok": True, "result": self.state(request)}
            if method == "read":
                result = (self.registry.operate(request) if "control" in request else self.read_model(request)
                          if "model" in request else {"text": self.registry.texts(request.get("scope")),
                                                      "windows": self.registry.windows()})
                return {"ok": True, "result": dict(self.identity(), data=result)}
            if method == "window":
                return {"ok": True, "result": dict(self.identity(), **self.window_action(request))}
            if method == "overlay_position":
                self.overlay_position(request)
            elif method in ("click", "set", "select", "focus", "submit", "scroll"):
                self.registry.operate(request)
            else:
                return failure("unknown_method", "Use describe to discover the supported methods.")
            return {"ok": True, "result": self.state()}
        except UIError as error:
            return failure(error.code, error.message)
        except (RuntimeError, ReferenceError):
            return failure("control_gone", "The UI element changed. Refresh state and retry.")

    def read_model(self, request):
        name = request.get("model")
        profile = self.window.snapshot.get("homeProfile") or {}
        if name == "connection":
            if __package__:
                from .connection import connection_view
            else:
                from connection import connection_view
            return dict(connection_view(self.window.snapshot), retryPending=getattr(self.window, "connection_retry_pending", False))
        if name == "navigation":
            return {"page": self.window.home_page, "collapsed": self.window.navigation_collapsed(),
                    "automatic": not self.window.settings.contains("navigation/collapsed")}
        if name == "profile":
            return {key: value for key, value in profile.items() if key != "matches"}
        if name == "history":
            offset = numeric(request.get("offset", 0), integer=True)
            limit = numeric(request.get("limit", 20), integer=True)
            if offset < 0 or not 1 <= limit <= 100:
                raise UIError("invalid_value", "History requires offset>=0 and limit in 1..100.")
            matches = profile.get("matches", [])
            return {"matches": matches[offset:offset + limit], "loaded": len(matches), "offset": offset,
                    "hasMore": profile.get("historyHasMore", False), "available": profile.get("historyAvailable", False)}
        if name == "draft":
            return self.window.snapshot.get("draft")
        if name == "assistant":
            from desktop.voice_catalog import PHRASES
            assistant = self.window.assistant
            return {"output": assistant.settings.value("assistant/output", "voice"),
                    "text": assistant.flag("assistant/text", False), "status": assistant.status,
                    "lastPhrase": assistant.last_phrase, "textMessage": assistant.text_message,
                    "error": assistant.error, "textActive": bool(assistant.text_message and time.monotonic() < assistant.text_until),
                    "phrases": {key: {"text": text, "enabled": assistant.flag("assistant/phrases/" + key),
                                     "channels": {channel: assistant.phrase_channel(key,channel) for channel in ("voice","text","sound")}}
                                for key, text in PHRASES.items() if key != "sample"}}
        if name == "build":
            return getattr(self.window, "shown_build", None)
        if name == "updates":
            page = self.window.updates_page
            return {"installed": page.version, "status": page.status.text(),
                    "releases": [{"version": r.version, "title": r.title, "published": r.published,
                                  "notes": r.notes, "url": r.url} for r in getattr(page, "releases", [])]}
        if name == "overlays":
            overlays = self.window.overlays
            return {"theme": getattr(overlays, "theme_id", None), "scale": getattr(overlays, "scale_percent", None),
                    "preview": getattr(overlays, "previewing", False),
                    "live": getattr(getattr(self.window, "live_feed", None), "contents", {}),
                    "tab": getattr(overlays, "tab_status", {"state": "hidden"}),
                    "laboratoryExpanded": bool(getattr(overlays, "laboratory_toggle", None)
                                               and overlays.laboratory_toggle.isChecked()),
                    "positions": {key: card.position for key, card in getattr(overlays, "cards", {}).items()}}
        raise UIError("unknown_model", "Use connection, navigation, profile, history, draft, build, updates or overlays.")

    def window_action(self, request):
        key = request.get("window", "main")
        roots = self.registry.roots()
        if not isinstance(key, str) or key not in roots:
            raise UIError("unknown_window", "Use an owned window ID from state.windows.")
        widget = roots[key]
        operation = request.get("operation", "read")
        if operation == "read":
            return {"window": next(w for w in self.registry.windows() if w["id"] == key)}
        if key != "main" and not isinstance(widget, QDialog):
            raise UIError("invalid_action", "Control this overlay using its settings, not window actions.")
        if operation in ("restore", "activate"):
            widget.showNormal()
            if operation == "activate":
                widget.raise_()
                widget.activateWindow()
        elif operation == "minimize":
            widget.showMinimized()
        elif operation == "resize":
            width = numeric(request.get("width"), integer=True)
            height = numeric(request.get("height"), integer=True)
            if not max(1, widget.minimumWidth()) <= width <= 16384 or not max(1, widget.minimumHeight()) <= height <= 16384:
                raise UIError("invalid_value", "Requested window size is outside its limits.")
            widget.resize(width, height)
        elif operation == "close":
            QTimer.singleShot(100, widget.close)
        else:
            raise UIError("invalid_action", "Use read, restore, activate, minimize, resize or close.")
        return {"accepted": True, "window": key, "operation": operation}

    def overlay_position(self, request):
        key = request.get("overlay")
        cards = getattr(self.window.overlays, "cards", {})
        if not isinstance(key, str) or key not in cards:
            raise UIError("unknown_control", "Choose a draggable overlay from read model=overlays.")
        card = cards[key]
        if request.get("reset") is True:
            card.position = None
            card.settings.remove(card.position_key)
        else:
            x, y = numeric(request.get("x")), numeric(request.get("y"))
            if not 0 <= x <= 1 or not 0 <= y <= 1:
                raise UIError("invalid_value", "Overlay coordinates must be within 0..1.")
            card.position = (x, y)
            card.settings.setValue(card.position_key, [x, y])
        self.window.overlays.sync()

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
                json.dumps(request, ensure_ascii=False, allow_nan=False).encode("utf-8")
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
    try:
        data = (json.dumps(message, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError):
        return failure("invalid_request", "Send a valid UTF-8 JSON request with finite numbers.")
    if len(data) > MAX_REQUEST:
        return failure("request_too_large", "Requests may be at most 8192 bytes.")
    socket = QLocalSocket()
    socket.connectToServer(name)
    if not socket.waitForConnected(TIMEOUT_MS):
        return failure("not_connected", f"LoL Helper PID {pid} is not available; no other instance was used."
                       if pid is not None else "Open LoL Helper Beta on this computer and try again.")
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


def main(*, require_pid=False):
    parser = argparse.ArgumentParser(description="Inspect and control a running LoL Helper Beta for Windows.")
    parser.add_argument("--pid", type=positive_pid, help="GUI process ID; no fallback to another instance")
    parser.add_argument("--output", help="Write the JSON result to this UTF-8 file (required by the GUI EXE)")
    commands = parser.add_subparsers(dest="method", required=True)
    commands.add_parser("schema", help="Print the API contract without starting the app")
    commands.add_parser("describe", help="List the controls and their supported actions")
    commands.add_parser("state", help="Read the UI state and the control positions")
    click = commands.add_parser("click", help="Click a visible, enabled button by control ID")
    click.add_argument("control")
    edit = commands.add_parser("set", help="Set a field by control ID")
    edit.add_argument("control")
    edit.add_argument("value", help="Enter true or false for a checkbox, or text for a text field")
    edit.add_argument("--json-value", action="store_true", help="Parse value as JSON (numbers, booleans, choice data)")
    for method in ("read", "focus", "submit"):
        command = commands.add_parser(method, help="Read/focus/submit a control by ID")
        command.add_argument("control")
    find = commands.add_parser("find", help="Find controls by ID, label or tooltip")
    find.add_argument("query")
    call = commands.add_parser("call", help="Execute any documented JSON API request")
    source = call.add_mutually_exclusive_group(required=True)
    source.add_argument("--json", dest="request_json", help="One JSON request object")
    source.add_argument("--file", dest="request_file", help="UTF-8 file containing one JSON request object")
    for command in commands.choices.values():
        command.add_argument("--pid", type=positive_pid, default=argparse.SUPPRESS,
                             help="GUI process ID; no fallback to another instance")
        command.add_argument("--output", default=argparse.SUPPRESS, help="Write the JSON result to a UTF-8 file")
    args = vars(parser.parse_args())
    pid = args.pop("pid", None)
    output = args.pop("output", None)
    if require_pid and args["method"] != "schema" and pid is None:
        parser.error("Choose the GUI process explicitly with --pid")
    if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if sys.stdout is None and not output:
        parser.error("Use --output response.json when calling the GUI EXE")
    def emit(value):
        data = json.dumps(value, ensure_ascii=False, indent=2)
        if output:
            Path(output).write_text(data, encoding="utf-8")
        if sys.stdout is not None:
            print(data)
    if args["method"] == "schema":
        emit(dict(schema(), endpoint=endpoint_for_pid(pid) if pid is not None else SOCKET_NAME))
        return 0
    if args["method"] == "set" and args["value"] in ("true", "false"):
        args["value"] = args["value"] == "true"
    if args.pop("json_value", False):
        try:
            args["value"] = json.loads(args["value"]) if isinstance(args["value"], str) else args["value"]
        except ValueError:
            parser.error("--json-value requires valid JSON")
    if args["method"] == "call":
        try:
            data = args.get("request_json")
            if args.get("request_file"):
                data = Path(args["request_file"]).read_text(encoding="utf-8-sig")
            args = json.loads(data)
            if not isinstance(args, dict):
                raise ValueError("Request must be an object")
        except (OSError, ValueError) as error:
            parser.error(str(error))
    _application = QCoreApplication.instance() or QCoreApplication([])
    response = request(args, pid=pid)
    emit(response)
    return 0 if response["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
