"""Render and exercise the actual QML window; no synthetic screenshots."""
import json
import platform
import traceback
from pathlib import Path
from PySide6 import __version__ as qt_version
from PySide6.QtCore import QObject, QPoint, Qt, QTimer
from PySide6.QtGui import QImage, QFontDatabase
from PySide6.QtTest import QTest
from PIL import Image


class Review:
    def __init__(self, app, engine, history, warnings, directory):
        self.app, self.engine, self.history, self.warnings = app, engine, history, warnings
        self.window = engine.rootObjects()[0]
        self.directory = Path(directory); self.directory.mkdir(parents=True, exist_ok=True)
        self.checks = []; self.errors = []

    def obj(self, name):
        obj = self.window.findChild(QObject, name)
        assert obj is not None, name
        return obj

    def check(self, condition, name):
        assert condition, name
        self.checks.append(name)

    def settle(self): QTest.qWait(180)

    def type_text(self, text):
        for char in text:
            QTest.keyClick(self.window, char)

    def click(self, name):
        obj = self.obj(name)
        point = obj.mapToScene(QPoint(int(obj.width()/2), int(obj.height()/2)))
        QTest.mouseClick(self.window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point.toPoint())
        self.settle()

    def capture(self, name):
        self.settle()
        image = self.window.grabWindow()
        self.check(not image.isNull(), 'render ' + name)
        # Preserve the actual captured pixels; use Pillow's PNG encoder because
        # this Linux Qt build can report success for a truncated PNG stream.
        rgba = image.convertToFormat(QImage.Format.Format_RGBA8888)
        target = self.directory/(name+'.png')
        Image.frombytes('RGBA', (rgba.width(), rgba.height()), bytes(rgba.constBits()),
                        'raw', 'RGBA', rgba.bytesPerLine()).save(target)
        with Image.open(target) as check:
            check.load()
            self.check(check.size == (image.width(),image.height()), 'save ' + name)

    def start(self):
        try:
            h = self.history
            self.check('PT Serif' in QFontDatabase.families(), 'bundled serif loaded')
            baseline = dict(h.values)
            self.check(baseline['n'] == len(h.all_rows) > 0, 'archive loaded')
            self.capture('history-1536x864')
            self.click('winButton')
            self.check(h.result == 'win' and all(r['win'] is True for r in h.filtered_rows), 'win button')
            self.click('lossButton')
            self.check(h.result == 'loss' and all(r['win'] is False for r in h.filtered_rows), 'loss button')
            self.click('resetButton')
            self.check(h.values == baseline, 'reset restores totals')
            self.click('search')
            self.type_text('Sett')
            self.settle()
            self.check(h.query == 'Sett' and 0 < h.values['n'] < baseline['n'], 'native text search')
            self.capture('history-search')
            QTest.keyClick(self.window, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
            self.type_text('nonexistent_champion_9283')
            self.settle()
            self.check(h.values['n'] == 0, 'empty search')
            self.capture('history-empty')
            self.click('resetButton')
            self.click('roleChoice')
            self.settle()
            QTest.keyClick(self.window, Qt.Key.Key_Down)
            QTest.keyClick(self.window, Qt.Key.Key_Return)
            self.settle()
            self.check(h.role_index == 1 and h.values['n'] < baseline['n'], 'native role selector')
            self.click('resetButton')
            self.click('queueChoice')
            QTest.keyClick(self.window, Qt.Key.Key_Down)
            QTest.keyClick(self.window, Qt.Key.Key_Return)
            self.settle()
            self.check(h.queue_index == 1 and all(r['queue'] == h.queues[0] for r in h.filtered_rows), 'native queue selector')
            self.click('resetButton')
            matches = self.obj('matchList')
            point = matches.mapToScene(QPoint(120, 25))
            QTest.mouseClick(self.window, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, point.toPoint())
            self.settle()
            self.check(self.obj('matchDialog').property('visible') and h.selected['champion'] == h.matches.rows[0]['champion'], 'open real match details')
            self.capture('history-details')
            self.window.closeDetails(); self.settle()
            matches.setProperty('contentY', 15000); self.settle()
            self.check(matches.property('contentY') > 10000, 'scroll deep archive')
            self.check(matches.property('liveDelegates') < 40, 'bounded live delegates')
            self.capture('history-scrolled')
            self.window.resetFilters()
            for width, height in [(1366,768),(1060,740),(940,640),(1920,1080)]:
                self.window.resize(width,height); self.settle()
                self.check(matches.height() > 100 and matches.width() > 600, f'usable viewport {width}x{height}')
                self.capture(f'history-{width}x{height}')
            self.window.resize(1536,864); self.window.resetFilters()
            self.window.contentItem().forceActiveFocus()
            QTest.mouseMove(self.window, QPoint(240,70))
            self.capture('history-final')
            self.check(not self.warnings, 'no QML warnings')
        except Exception:
            self.errors.append(traceback.format_exc())
        report = {'checks':self.checks, 'errors':self.errors, 'qml_warnings':self.warnings,
                  'platform':platform.platform(), 'pyside':qt_version,
                  'qt_platform':self.app.platformName(), 'renderer':'software (review environment)',
                  'summary':self.history.values, 'filter_ms':self.history.filter_times}
        (self.directory/'checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
        self.app.exit(1 if self.errors or self.warnings else 0)
