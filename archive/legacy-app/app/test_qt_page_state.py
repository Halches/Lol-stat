"""Offline tests for Qt page filters and settings rebuilds."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from PySide6.QtCore import QCoreApplication, QEvent, Qt
    from PySide6.QtWidgets import QApplication, QComboBox, QLineEdit, QPushButton
except ModuleNotFoundError as error:
    if error.name != 'PySide6':
        raise
    raise unittest.SkipTest('Qt dependencies are unavailable') from error

import app_config
import core
from qt_app import App
from voice import Voice


def combo_keys(control):
    return [control.itemData(index) for index in range(control.count())]


def combo_with(page, *values):
    return next(control for control in page.findChildren(QComboBox)
                if all(control.findData(value) >= 0 for value in values))


def select(control, value):
    control.setCurrentIndex(control.findData(value))


class QtPageStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication(['page-tests', '-platform', 'offscreen'])

    def setUp(self):
        home = self.enterContext(tempfile.TemporaryDirectory())
        assets = Path(home) / 'assets.json'
        assets.write_text('{}', encoding='utf-8')
        self.addCleanup(self.qt.setStyleSheet, self.qt.styleSheet())
        self.addCleanup(self.qt.setFont, self.qt.font())
        self.addCleanup(self.qt.setProperty, 'uiScale', self.qt.property('uiScale'))
        self.enterContext(patch.dict(app_config.C))
        self.enterContext(patch.dict(app_config.F))
        self.enterContext(patch.dict(core.OBJ))
        self.enterContext(patch.object(app_config, 'LOG_HOME', home))
        data = core.Data({
            'names': {'Ahri': 'Ahri', 'Viktor': 'Viktor'},
            'ids': {'103': 'Ahri', '112': 'Viktor'},
            'items': {}, 'lola': {},
            'champs': {'Ahri': {'tags': ['Mage']}, 'Viktor': {'tags': ['Mage']}},
            'players': {
                'halch': {'riot': 'One#EUW', 'g': [{'c': 'Ahri', 'pos': 'MIDDLE', 'q': 420}]},
                'other': {'riot': 'Two#EUW', 'g': [{'c': 'Viktor', 'pos': 'MIDDLE', 'q': 450}]},
            },
            'pools': {'halch': {'MIDDLE': ['Ahri']}},
        })
        # Native overlays and the voice worker are outside the offscreen page tests.
        self.enterContext(patch.object(App, 'create_overlays'))
        with patch.object(Voice, '_loop'):
            self.app = App(data, 'test', offline=True, home=home, assets=assets)
        self.addCleanup(self.close_app)

    def close_app(self):
        self.app.window.close()
        self.app.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def apply_theme(self):
        self.app.navigate(5)
        self.app.s['theme'] = 'lol_day'
        self.app.apply_settings()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.assertEqual(self.app.active_page, 5)
        self.assertFalse(self.app.errors)

    def test_history_queue_choices_follow_client_results_and_source(self):
        history = self.app.history_view
        self.assertEqual(combo_keys(history.queue_choice), ['', 420])
        select(history.queue_choice, 420)
        games = [{'gid': 101, 'q': 450, 'champ': 103, 'win': True},
                 {'gid': 102, 'q': 1700, 'champ': 112, 'win': False}]
        with patch.object(self.app, 'background') as background:
            history.load_client(background=True)
            select(history.source_choice, 'client')
            self.assertEqual(combo_keys(history.queue_choice), [''])
            self.assertEqual(history.filtered, [])
            _, done = background.call_args.args
            done(({'puuid': 'client'}, games, {}), None)

        self.assertEqual(combo_keys(history.queue_choice), ['', 450, 1700])
        self.assertEqual(history.queue_choice.currentData(), '')
        self.assertEqual([record['gid'] for record in history.filtered], [101, 102])
        select(history.queue_choice, 450)
        history.search.setText('Ahri')
        self.assertEqual(combo_keys(history.queue_choice), ['', 450, 1700])
        self.assertEqual(history.queue_choice.currentData(), 450)
        self.assertEqual([record['gid'] for record in history.filtered], [101])

        self.apply_theme()
        history = self.app.history_view
        self.assertEqual(history.source_choice.currentData(), 'client')
        self.assertEqual(history.search.text(), 'Ahri')
        self.assertEqual(history.queue_choice.currentData(), 450)
        self.assertEqual([record['gid'] for record in history.filtered], [101])

        select(history.source_choice, 'saved')
        self.assertEqual(combo_keys(history.queue_choice), ['', 420])
        self.assertEqual(history.queue_choice.currentData(), '')
        self.assertEqual([record['queue'] for record in history.filtered], [420])

    def test_history_queue_choices_follow_saved_profile(self):
        history = self.app.history_view
        select(history.queue_choice, 420)
        self.app.set_who('other')
        self.assertEqual(combo_keys(history.queue_choice), ['', 450])
        self.assertEqual(history.queue_choice.currentData(), '')
        self.assertEqual([record['champion'] for record in history.filtered], ['Viktor'])

    def test_theme_rebuild_preserves_pool_filters(self):
        self.app.navigate(10)
        pool = self.app.pool_view
        select(combo_with(pool, 'MIDDLE'), 'MIDDLE')
        select(pool.mode_choice, 'pool')
        pool.search.setText('Ahr')
        select(pool.filter_choices['classes'], 'Mage')
        select(combo_with(pool, 'year', 'name'), 'year')
        next(button for button in pool.findChildren(QPushButton)
             if button.text() == 'Дополнительные фильтры').click()

        self.apply_theme()
        pool = self.app.pool_view
        self.assertEqual(combo_with(pool, 'MIDDLE').currentData(), 'MIDDLE')
        self.assertEqual(pool.mode_choice.currentData(), 'pool')
        self.assertEqual(pool.search.text(), 'Ahr')
        self.assertEqual(pool.filter_choices['classes'].currentData(), 'Mage')
        self.assertEqual(combo_with(pool, 'year', 'name').currentData(), 'year')
        self.assertFalse(pool.advanced.isHidden())
        self.assertEqual(pool.list.count(), 1)
        self.assertEqual(pool.list.item(0).data(Qt.ItemDataRole.UserRole), 'Ahri')

    def test_theme_rebuild_preserves_champion_build_selection(self):
        build = {'core': [], 'i4': [], 'i5': [], 'i6': []}
        self.app.lola[('matchup', 'Ahri', 'MIDDLE', 'Viktor')] = {
            'pick': dict(build, start=[1056]), 'win': dict(build, start=[1055]),
        }
        self.app.cp_pick('Ahri', 'MIDDLE')
        champion = self.app.champion_view
        select(champion.enemy, 'Viktor')
        next(button for button in champion.findChildren(QPushButton)
             if button.text() == 'По винрейту').click()

        self.apply_theme()
        champion = self.app.champion_view
        self.assertEqual(champion.select.currentData(), 'Ahri')
        self.assertEqual(champion.role_select.currentData(), 'MIDDLE')
        self.assertEqual(champion.enemy.currentData(), 'Viktor')
        self.assertEqual(self.app.cp_sel, ('Ahri', 'MIDDLE'))
        active = {button.text() for button in champion.findChildren(QPushButton) if button.active}
        self.assertEqual(active, {'Против оппонента', 'По винрейту'})

    def test_theme_rebuild_preserves_hints_filters(self):
        hints = self.app.hints_view
        hints.findChild(QLineEdit).setText('Итог игры')
        select(combo_with(hints, 'common'), 'common')
        select(combo_with(hints, 'all', 'text'), 'text')

        self.apply_theme()
        hints = self.app.hints_view
        self.assertEqual(hints.findChild(QLineEdit).text(), 'Итог игры')
        self.assertEqual(combo_with(hints, 'common').currentData(), 'common')
        self.assertEqual(combo_with(hints, 'all', 'text').currentData(), 'text')
        self.assertEqual([hint[0] for hint in hints.visible()], ['postgame'])

    def test_theme_rebuild_preserves_scroll_positions_on_other_pages(self):
        self.app.window.resize(940, 640)
        positions = [(3, 'verticalScrollBar', 196), (9, 'horizontalScrollBar', 31)]
        for page, direction, value in positions:
            self.app.navigate(page)
            QCoreApplication.processEvents()
            bar = getattr(self.app.scrolls[page], direction)()
            bar.setValue(value)
            self.assertEqual(bar.value(), value)

        self.apply_theme()
        self.app.s['theme'] = 'pilt_day'
        self.app.apply_settings()

        for page, direction, value in positions:
            self.app.navigate(page)
            QCoreApplication.processEvents()
            self.assertEqual(getattr(self.app.scrolls[page], direction)().value(), value)
