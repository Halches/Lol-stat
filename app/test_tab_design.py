"""Centre-gutter Tab design: semantics, bounds and packaged arrow sprite."""
import unittest

from PIL import ImageChops

import render
import ui


class TabDesignTests(unittest.TestCase):
    def test_number_direction_and_team_colour(self):
        self.assertEqual(render.tab_advantage({'v': 9800}, {'v': 8950}), ('850', -1, 'blue'))
        self.assertEqual(render.tab_advantage({'v': 7400}, {'v': 7720}), ('320', 1, 'red'))
        self.assertEqual(render.tab_advantage({'v': 9800}, {'v': 8950}, False), ('850', -1, 'red'))
        self.assertEqual(render.tab_advantage({'v': 7400}, {'v': 7720}, False), ('320', 1, 'blue'))

    def test_tie_and_missing_player_have_no_direction(self):
        self.assertEqual(render.tab_advantage({'v': 1000}, {'v': 1000}), ('0', 0, 'mute'))
        self.assertEqual(render.tab_advantage({'v': 1000}, None), ('—', 0, 'mute'))
        self.assertEqual(render.tab_advantage(None, {'v': 0}), ('—', 0, 'mute'))
        self.assertEqual(render.tab_advantage(None, None), ('—', 0, 'mute'))

    def test_small_difference_is_not_rounded_to_a_tie(self):
        self.assertEqual(render.tab_advantage({'v': 1001}, {'v': 1000}), ('1', -1, 'blue'))
        self.assertEqual(render.tab_advantage({'v': 1000}, {'v': 1090}), ('90', 1, 'red'))

    def test_large_values_are_compact(self):
        self.assertEqual(render.tab_advantage({'v': 22450}, {'v': 10000})[0], '12,4k')
        self.assertEqual(render.tab_advantage({'v': 20000}, {'v': 10000})[0], '10k')

    def test_generated_arrow_is_transparent_and_reverses(self):
        left = render.advantage_arrow(24, 14, -1)
        right = render.advantage_arrow(24, 14, 1)
        self.assertEqual(left.mode, 'RGBA')
        self.assertLessEqual(left.width, 24)
        self.assertLessEqual(left.height, 14)
        self.assertEqual(left.getchannel('A').getextrema(), (0, 255))
        self.assertIsNone(ImageChops.difference(left.transpose(render.Image.Transpose.ROTATE_180), right).getbbox())

    def test_badges_stay_between_players_at_different_scales(self):
        rows = [({'v': a}, {'v': b}) for a, b in ((9800, 8950), (7400, 7720), (1000, 1000), (22450, 10000), (1000, 1090))]
        for name in ('lol', 'lol_day'):
            for game_scale in (.667, 1., 1.333):
                for ui_scale in (1., 1.25, 1.5, 2.):
                    with self.subTest(theme=name, game_scale=game_scale, ui_scale=ui_scale):
                        rect = (20, 48, 1160*game_scale, 380*game_scale)
                        k = game_scale*ui_scale
                        cx, rh, width, height = render.tab_badge_geometry(rect, k)
                        im = render.tab_plates(rect, rows, ui.THEMES[name][1], k)
                        bounds = im.getchannel('A').getbbox()
                        self.assertLessEqual(width, round(rh*.28))
                        self.assertGreaterEqual(bounds[0], int(cx-width/2)-1)
                        self.assertLessEqual(bounds[2], int(cx+width/2)+2)
                        self.assertGreaterEqual(bounds[1], rect[1])  # no team-total strip above Tab
                        self.assertLessEqual(bounds[3], rect[1]+rect[3]+1)
                        self.assertIsNone(im.getchannel('A').crop((0, 0, im.width, 48)).getbbox())

    def test_unidentified_empty_rows_stay_transparent(self):
        im = render.tab_plates((0, 0, 1160, 380), [(None, None)]*5, ui.THEMES['lol'][1], 1.)
        self.assertIsNone(im.getchannel('A').getbbox())

    def test_total_extension_stays_above_game_header_and_in_bounds(self):
        for k in (.667, 1., 1.5, 2.):
            height = 380*k
            top = round(height*.35+max(30,height*.22))
            im = render.tab_plates((0,top,1160*k,height),[(None,None)]*5,ui.THEMES['lol'][1],k,totals=(24050,21600))
            box = im.getchannel('A').getbbox()
            self.assertIsNotNone(box)
            self.assertGreaterEqual(box[1],0)
            self.assertLessEqual(box[3],top-height*.17+2)
            # The wrapping side strokes must not paint over dragon-buff slots.
            wing=round((1160*k-1160*k*.54)/2)
            protected=im.getchannel('A').crop((wing+3,round(top-height*.35)+3,
                                               round(1160*k-wing)-3,round(top-height*.17)-3))
            self.assertIsNone(protected.getbbox())
            self.assertIsNone(im.getchannel('A').crop((0,top,im.width,im.height)).getbbox())


if __name__ == '__main__': unittest.main()
