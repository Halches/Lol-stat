"""Disposable Qt server for addressing tests. No LoL client or user settings."""
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget
from automation_bundle import automation_module
AutomationServer = automation_module().AutomationServer


base, directory, marker = sys.argv[1:]
app = QApplication([])
window = QWidget()
window.setWindowTitle(marker)
layout = QVBoxLayout(window)
window.scroll = QScrollArea()
body = QWidget()
contents = QVBoxLayout(body)
action = QPushButton("0")
def clicked():
    action.setText(str(int(action.text()) + 1))
    window.notice.setText(action.text())
action.clicked.connect(clicked)
contents.addWidget(action)
window.scroll.setWidget(body)
layout.addWidget(window.scroll)
window.snapshot = {"phase": "offline"}
window.headline = QLabel(marker)
window.status = QLabel("")
window.notice = QLabel("")
window.preview_message = QLabel("")
window.preview_job = window.export_job = window.latest_match = None
window.updates_page = SimpleNamespace(version="fixture", available=None, job=None, status=QLabel(""))
window.home_page = marker
window.draft_active = False
window.is_home = lambda: True
window.overlays = SimpleNamespace(visible=lambda: False)
server = AutomationServer(window, base, directory=directory)
server.add(marker, marker, action, "button")
assert server.start()
window.show()
Path(directory, marker + ".ready").write_text(json.dumps({"pid": os.getpid(), "legacy": server.server.isListening(),
                                                        "instance": server.instance_name}), encoding="utf-8")
watch = QTimer()
watch.timeout.connect(lambda: app.quit() if Path(directory, marker + ".stop").exists() else None)
watch.start(30)
QTimer.singleShot(120_000, app.quit)
app.aboutToQuit.connect(server.close)
raise SystemExit(app.exec())
