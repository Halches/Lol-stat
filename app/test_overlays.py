"""Геометрия и поведение Tab без игры/дисплея: python -m unittest discover -s app -p test_overlays.py."""
import copy
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import ui


class OverlayTests(unittest.TestCase):
    def plate(self):
        w = object.__new__(ui.TabPlates)
        w.app = SimpleNamespace(s=copy.deepcopy(ui.DEFAULTS))
        w.data, w._geometry_sig, w._drag = None, None, None
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


if __name__ == '__main__':
    unittest.main()
