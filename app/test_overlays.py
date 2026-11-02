"""Геометрия и поведение Tab без игры/дисплея: python -m unittest discover -s app -p test_overlays.py."""
import copy
import tempfile
import queue
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import ui
import tab_detect


class OverlayTests(unittest.TestCase):
    def plate(self):
        w = object.__new__(ui.TabPlates)
        w.app = SimpleNamespace(s=copy.deepcopy(ui.DEFAULTS))
        w.data, w._geometry_sig, w._drag = None, None, None
        w.auto_layout, w._auto_context, w._left_ally = None, None, True
        w._auto_results, w._auto_cancel = queue.Queue(), threading.Event()
        w._auto_epoch, w._auto_next, w._auto_time = 0, 0., 0.
        w._auto_pending, w._auto_active = False, False
        w.auto_status = 'Автоподгонка: ожидаю Tab в игре'
        w.handle = Mock()
        w.unlocked = False
        return w

    def test_manual_rect_tracks_game_window_and_ultrawide(self):
        w = self.plate()
        w.app.s['tab_rect'] = [-.5, .25, 1., .4]
        with patch.object(ui, 'game_rect', return_value=(100, 200, 1920, 1080)):
            x, y, width, height, *_ = w.geom()
        self.assertEqual((x, y, width, height), (520, 470, 1080, 432))
        with patch.object(ui, 'game_rect', return_value=(-400, 0, 3440, 1440)):
            x, y, width, height, *_ = w.geom()
        self.assertEqual((x, y, width, height), (600, 360, 1440, 576))

    def test_handle_move_resize_and_minimum_size(self):
        rect = [-.5, .25, 1., .4]
        self.assertEqual(ui.tab_rect_drag(rect, .1, .05), [-.4, .3, 1., .4])
        self.assertEqual(ui.tab_rect_drag(rect, .1, .05, True), [-.5, .25, 1.1, .45])
        self.assertEqual(ui.tab_rect_drag(rect, -2, -2, True), [-.5, .25, .2, .1])
        self.assertEqual(rect, [-.5, .25, 1., .4])

    def test_alt_never_makes_large_window_interactive(self):
        w = self.plate()
        with patch.object(ui, 'click_through') as through:
            w.unlock(True)
            w.unlock(False)
        self.assertEqual(through.call_args_list, [((w, True),), ((w, True),)])
        w.handle.withdraw.assert_called_once()

    def test_releasing_alt_commits_active_handle_drag(self):
        w = self.plate()
        w.app.s = Mock()
        w._drag = (10, 20, [-.5, .25, 1., .4], 1080, False)
        with patch.object(ui, 'click_through'):
            w.unlock(False)
        self.assertIsNone(w._drag)
        w.app.s.save.assert_called_once()

    def test_legacy_settings_keep_layout_and_enable_new_widget(self):
        import json
        from pathlib import Path
        with tempfile.TemporaryDirectory() as home:
            Path(home, 'settings.json').write_text(json.dumps({'widgets': {'gold': False}, 'tab_rect': [-.5, .2, 1., .4]}))
            s = ui.Settings(home)
        self.assertTrue(s['widgets']['inventory'])
        self.assertFalse(s['widgets']['gold'])
        self.assertEqual(s['tab_rect'], [-.5, .2, 1., .4])
        self.assertTrue(s['tab_auto'])

    def test_detection_session_discards_results_after_release_and_window_change(self):
        w = self.plate()
        players = [{'riot': str(i), 'c': str(i), 'team': 'ORDER' if i < 5 else 'CHAOS'} for i in range(10)]
        g = SimpleNamespace(players=players, t=100)
        layout = tab_detect.Layout((-.5, .2, 1., .4), ((), ()), ('ORDER', 'CHAOS'), .9)
        w._detection_status, w.show = Mock(), Mock()
        with patch.object(ui, 'IS_WIN', True), patch.object(ui, 'game_rect', return_value=(0, 0, 1920, 1080)) as rect, patch.object(ui.time, 'monotonic', return_value=10):
            w.auto_tick(True, g)
            w._auto_pending = True
            w._auto_results.put((w._auto_epoch, layout, None))
            w.auto_tick(False, g)
            self.assertIsNone(w.auto_layout)
            w.show.assert_not_called()
            w.auto_tick(True, g)
            w._auto_results.put((w._auto_epoch, layout, None))
            w.auto_tick(True, g)
            self.assertEqual(w.auto_layout, layout)
            w.show.assert_called_once_with(g)
            # A result from before the game window moved must not be applied.
            w._auto_results.put((w._auto_epoch, layout, None))
            rect.return_value = (-1920, 0, 1920, 1080)
            w.auto_tick(True, g)
            self.assertIsNone(w.auto_layout)

    def test_disabled_detection_does_not_launch_worker(self):
        w = self.plate()
        w.app.s['tab_auto'] = False
        w._detection_status = Mock()
        g = SimpleNamespace(players=[{'riot': str(i), 'c': str(i), 'team': 'ORDER'} for i in range(10)], t=100)
        with patch.object(ui, 'IS_WIN', True), patch.object(ui, 'game_rect', return_value=(0, 0, 1920, 1080)), patch.object(ui.threading, 'Thread') as worker:
            w.auto_tick(True, g)
            w.auto_tick(True, g)
        worker.assert_not_called()

    def test_one_player_practice_starts_and_applies_capture(self):
        w = self.plate()
        w.app.icons = SimpleNamespace(a={'champ': {'Viktor': 'bundled-portrait'}})
        w.show, w._detection_status = Mock(), Mock()
        g = SimpleNamespace(players=[{'riot': 'Practice#1', 'c': 'Viktor', 'team': 'ORDER'}], t=100)
        layout = tab_detect.Layout((-.5, .3, 1., .4), (('Viktor', None, None, None, None), (None,)*5), ('ORDER', 'CHAOS'), .9, 'frame')
        with patch.object(ui, 'IS_WIN', True), patch.object(ui, 'game_focused', return_value=True), patch.object(ui, 'game_rect', return_value=(0, 0, 1920, 1080)), patch.object(ui.time, 'monotonic', return_value=10) as clock, patch.object(ui.threading, 'Thread') as thread, patch.object(ui.tab_detect, 'capture_and_detect', return_value=layout) as capture:
            w.auto_tick(True, g)
            thread.assert_not_called()  # opening animation delay
            clock.return_value = 10.3
            w.auto_tick(True, g)
            thread.return_value.start.assert_called_once()
            thread.call_args.kwargs['target']()  # run the worker deterministically
            capture.assert_called_once()
            w.auto_tick(True, g)
        self.assertEqual(w.auto_layout, layout)
        w.show.assert_called_once_with(g)
        self.assertTrue(any('1/1' in c.args[0] for c in w._detection_status.call_args_list))

    def test_no_players_reports_waiting_for_live_data(self):
        w = self.plate()
        w._detection_status = Mock()
        with patch.object(ui.threading, 'Thread') as thread:
            w.auto_tick(True, SimpleNamespace(players=[], t=0))
        thread.assert_not_called()
        self.assertIn('игровые данные', w._detection_status.call_args.args[0])

    def test_detected_rows_use_champion_identity_and_uncertain_rows_are_empty(self):
        w = self.plate()
        w.draw = Mock()
        allies = [{'c': f'A{i}', 'pos': r, 'igold': 1000+i} for i, r in enumerate(ui.core.ROLES)]
        enemies = [{'c': f'E{i}', 'pos': r, 'igold': 2000+i} for i, r in enumerate(ui.core.ROLES)]
        g = SimpleNamespace(allies=allies, enemies=enemies, my_team='ORDER')
        w.auto_layout = tab_detect.Layout((-.5, .2, 1., .4), (('A3', None, 'A2', 'A4', 'A0'), ('E1', 'E2', 'E3', 'E4', 'E0')), ('ORDER', 'CHAOS'), .9)
        w.show(g)
        rows, = w.data
        self.assertEqual(rows[0], ({'v': 1003}, {'v': 2001}))
        self.assertIsNone(rows[1][0])
        self.assertEqual(ui.render.tab_advantage(*rows[0]), ('998', 1, 'red'))


if __name__ == '__main__':
    unittest.main()
