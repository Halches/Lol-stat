"""Isolated Qt Quick history prototype. Read-only, offline; no Tk or LCU startup."""
from __future__ import annotations
import argparse
import base64
import io
import json
import os
from pathlib import Path
import sys
import time
from functools import lru_cache

HERE = Path(__file__).resolve().parent
APP = HERE.parents[1]
sys.path.insert(0, str(APP))
from PySide6.QtCore import QAbstractListModel, QModelIndex, QObject, Property, Qt, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QGuiApplication, QFontDatabase, QImage
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickImageProvider
import core
import history_model
import material_assets
import render
from PIL import Image


class MatchList(QAbstractListModel):
    ROLE = int(Qt.ItemDataRole.UserRole) + 1

    def __init__(self):
        super().__init__()
        self.rows = []

    def roleNames(self):
        return {self.ROLE: b'record'}

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def data(self, index, role):
        if index.isValid() and role == self.ROLE and 0 <= index.row() < len(self.rows):
            return self.rows[index.row()]

    def replace(self, rows):
        self.beginResetModel(); self.rows = rows; self.endResetModel()


class Images(QQuickImageProvider):
    def __init__(self, icons):
        super().__init__(QQuickImageProvider.ImageType.Image)
        self.icons = icons

    @lru_cache(maxsize=384)
    def get(self, key):
        if key.startswith('painted/'):
            name = key.split('/')[1]
            # Source coordinates exclude empty export margins, retaining the
            # painted edge and shadow. Resizing is runtime nine-slice only.
            regions = {'panel': ((26,279,2148,448), 44, 20, (1200,104)),
                       'button': ((100,226,1915,566), 120, 12, (320,64)),
                       'selected': ((92,202,2084,554), 128, 12, (320,64))}
            rect, cut, border, dimensions = regions[name]
            with Image.open(HERE/'painted'/f'blossom-{name}-v1.png') as source:
                art = material_assets.nine_slice(source.convert('RGBA').crop(rect), *dimensions, cut, border)
            buffer = io.BytesIO(); art.save(buffer, format='PNG')
            return QImage.fromData(buffer.getvalue())
        if key.startswith('art/'):
            name = key.split('/')[1]
            art = {'shell': lambda: material_assets.shell(1536, 864),
                   'surface': lambda: material_assets.nine_slice(
                       material_assets.source('blossom-panel-v2.png').crop((37,271,2134,450)),
                       1200, 100, 48, 20),
                   'panel': lambda: material_assets.panel(1200, 100),
                   'button': lambda: material_assets.panel(220, 36, compact=True),
                   'active': lambda: material_assets.panel(220, 36, active=True, compact=True)}[name]()
            if art is None: raise RuntimeError('Bundled blossom artwork missing')
            buffer = io.BytesIO(); art.save(buffer, format='PNG')
            return QImage.fromData(buffer.getvalue())
        if key.startswith('nav/'):
            art = render.nav_icon(key.split('/')[1], '#d7c7dd', 24)
            buffer = io.BytesIO(); art.save(buffer, format='PNG')
            return QImage.fromData(buffer.getvalue())
        group, _, identity = key.partition('/')
        encoded = self.icons.get(group, {}).get(identity)
        return QImage.fromData(base64.b64decode(encoded)) if encoded else QImage()

    def requestImage(self, identity, size, requested_size):
        image = self.get(identity)
        size.setWidth(image.width()); size.setHeight(image.height())
        return image


class History(QObject):
    changed = Signal()
    detailChanged = Signal()

    def __init__(self, data, profile, icons):
        super().__init__()
        self.data_store, self.profile, self.icons = data, profile, icons
        self.all_rows = history_model.saved(core.Player(data, profile).games, data, profile)
        self.matches = MatchList()
        self.query, self.role_index, self.queue_index, self.result = '', 0, 0, 'all'
        self.queues = sorted({r['queue'] for r in self.all_rows if type(r['queue']) is int})
        self.selected = {}; self.filtered_rows = []; self.values = {}
        self.filter_times = []
        self.refresh()

    @Property(QObject, constant=True)
    def matchModel(self): return self.matches

    @Property(str, constant=True)
    def profileLabel(self):
        return f"{self.data_store.d['players'][self.profile]['riot']} · выгрузка от {self.data_store.d.get('t','—')}"

    @Property('QVariantList', constant=True)
    def roles(self): return ['Все роли'] + [core.ROLE_RU[r].capitalize() for r in core.ROLES]

    @Property('QVariantList', constant=True)
    def queueLabels(self): return ['Все режимы'] + [core.QUEUE_RU.get(q, str(q)) for q in self.queues]

    @Property('QVariantMap', notify=changed)
    def summary(self): return self.values

    @Property('QVariantMap', notify=detailChanged)
    def detail(self): return self.selected

    def icon(self, group, key):
        return f'image://assets/{group}/{key}' if str(key) in self.icons.get(group, {}) else ''

    def present(self, row):
        fmt = lambda value, digits: f'{value:.{digits}f}'.replace('.', ',') if value is not None else '—'
        icons = [self.icon('spell', core.SPELL_KEY.get(s, s)) for s in row['spells']]
        if row['perk']: icons.append(self.icon('rune', row['perk']))
        icons.extend(self.icon('item', item) for item in row['items'] if item)
        return {
            'champion': self.data_store.cn(row['champion']), 'portrait': self.icon('champ', row['champion']),
            'subtitle': core.QUEUE_RU.get(row['queue'], 'Режим неизвестен') + ' · ' +
                        (time.strftime('%d.%m %H:%M', time.localtime(row['timestamp'])) if row['timestamp'] else '—'),
            'equipment': [icon for icon in icons if icon],
            'score': ' / '.join(str(row[k]) if row[k] is not None else '—' for k in ('k','d','a')),
            'farm': fmt(row['csm'], 1) + ' CS/мин',
            'participation': 'Участие ' + fmt(row['kp'], 0) + '%',
            'vision': 'Обзор ' + fmt(row['vsm'], 2) + '/мин',
            'result': 'ПОБЕДА' if row['win'] is True else 'ПОРАЖЕНИЕ' if row['win'] is False else 'НЕТ ДАННЫХ',
            'tone': '#78cec9' if row['win'] is True else '#e48ca7' if row['win'] is False else '#c5b5d1',
            'duration': core.mmss(row['duration']) if row['duration'] is not None else '—',
            'lp': f"{row['lp']:+d} LP" if type(row['lp']) is int else 'LP —',
            'damage': row.get('dmg') if row.get('dmg') is not None else '—',
            'gold': row.get('gold') if row.get('gold') is not None else '—',
            'cs': row.get('cs') if row.get('cs') is not None else '—',
            'opponent': self.data_store.cn(row.get('opp')) if row.get('opp') else '—'}

    def refresh(self):
        start = time.perf_counter()
        self.filtered_rows = history_model.filtered(self.all_rows, self.data_store, self.query,
            core.ROLES[self.role_index-1] if self.role_index else '',
            self.queues[self.queue_index-1] if self.queue_index else '', self.result)
        stats = history_model.stats(self.filtered_rows)
        fmt = lambda v, n: f'{v:.{n}f}'.replace('.', ',') if v is not None else '—'
        self.values = {'n': stats['n'], 'wins': fmt(stats['wr'], 1) + ('%' if stats['wr'] is not None else ''),
                       'kda': fmt(stats['kda'], 2), 'farm': fmt(stats['csm'], 1),
                       'known': stats['results'], 'kdaCount': stats['kda_n'], 'farmCount': stats['csm_n'],
                       'total': len(self.all_rows)}
        self.matches.replace([self.present(row) for row in self.filtered_rows])
        self.filter_times.append((time.perf_counter()-start)*1000)
        self.changed.emit()

    @Slot(str, int, int, str)
    def setFilters(self, query, role, queue, result):
        if result not in ('all','win','loss') or not 0 <= role <= len(core.ROLES) or not 0 <= queue <= len(self.queues):return
        self.query, self.role_index, self.queue_index, self.result = query, role, queue, result
        self.refresh()

    @Slot(int)
    def openMatch(self, index):
        if 0 <= index < len(self.matches.rows):
            self.selected = self.matches.rows[index]; self.detailChanged.emit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=Path, default=APP/'data.json')
    parser.add_argument('--assets', type=Path, default=HERE/'icons.json')
    parser.add_argument('--profile', default='halch')
    parser.add_argument('--capture-dir', type=Path)
    args = parser.parse_args()
    qt = QGuiApplication(sys.argv[:1])
    qt.setApplicationName('LoL Helper · Qt preview')
    for path in (APP/'fonts').glob('*.ttf'): QFontDatabase.addApplicationFont(str(path))
    for path in (HERE/'fonts').glob('*.ttf'): QFontDatabase.addApplicationFont(str(path))
    data = core.Data.load(args.data)
    if args.profile not in data.d['players']: parser.error('Unknown saved profile')
    icons = json.loads(args.assets.read_text(encoding='utf-8'))
    history = History(data, args.profile, icons)
    engine = QQmlApplicationEngine()
    warnings = []
    engine.warnings.connect(lambda errors: warnings.extend(error.toString() for error in errors))
    engine.addImageProvider('assets', Images(icons))
    engine.rootContext().setContextProperty('history', history)
    engine.rootContext().setContextProperty('serifFamily', 'PT Serif')
    engine.load(QUrl.fromLocalFile(str(HERE/'qml'/'Main.qml')))
    if not engine.rootObjects(): return 1
    if args.capture_dir:
        from review import Review
        review = Review(qt, engine, history, warnings, args.capture_dir)
        QTimer.singleShot(500, review.start)
    code = qt.exec()
    return code


if __name__ == '__main__':sys.exit(main())
