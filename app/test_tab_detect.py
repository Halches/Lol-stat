"""Detection regression tests; synthetic images are NOT live-game accuracy evidence."""
import base64
import io
import threading
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

from tab_detect import Anchor, Layout, capture_and_detect, detect, fit_grid, find_frames, recover_question_marks, assign_visible_faces


PLAYERS = [{'c': f'C{i}', 'team': 'ORDER' if i < 5 else 'CHAOS'} for i in range(10)]
ORDER = ((2, 0, 4, 1, 3), (8, 9, 5, 7, 6))


def anchors(width=1920, height=1080, step=76, xshift=0, yshift=0):
    lx = (width - 15.25 * step) / 2 + 1.75 * step + xshift
    return [Anchor(f'C{champ}', lx + col * 7.1 * step, height * .28 + row * step + yshift, step * .66, .91)
            for col, order in enumerate(ORDER) for row, champ in enumerate(order)]


def fixture(width=1280, height=720, step=50, xshift=0):
    rng = np.random.default_rng(17)
    bg = rng.integers(10, 60, (30, 50, 3), dtype=np.uint8)
    frame = Image.fromarray(bg).resize((width, height), Image.Resampling.BILINEAR)
    portraits = {}
    points = anchors(width, height, step, xshift)
    for i, p in enumerate(points):
        src = Image.fromarray(rng.integers(0, 256, (12, 12, 3), dtype=np.uint8)).resize((96, 96), Image.Resampling.BICUBIC)
        d = ImageDraw.Draw(src)
        d.ellipse((20+i, 15, 70, 80-i), outline=(240, 170, 90), width=4)
        buf = io.BytesIO(); src.save(buf, 'PNG')
        portraits[p.champ] = base64.b64encode(buf.getvalue()).decode()
        size = round(p.size)
        icon = src.resize((size, size), Image.Resampling.LANCZOS)
        if i == 3: icon = ImageOps.grayscale(icon).convert('RGB')
        mask = Image.new('L', (size, size)); ImageDraw.Draw(mask).ellipse((0, 0, size-1, size-1), fill=255)
        frame.paste(icon, (round(p.x-size/2), round(p.y-size/2)), mask)
    return frame, portraits, points


def framed_fixture(width=1280, height=720, step=50, visible=(0,), divider=True):
    """A gold frame with deliberately empty player slots, not a full 5v5 grid."""
    original, portraits, points = fixture(width, height, step)
    frame = Image.new('RGB', (width, height), (80, 110, 85))
    x0, y0 = points[0].x-step*1.75, points[0].y-step/2
    x1, y1 = x0+15.25*step, y0+5*step
    d = ImageDraw.Draw(frame)
    gold = (170, 140, 65)
    d.rectangle((x0, y0-step*.9, x1, y1), fill=(9, 22, 30), outline=gold, width=2)
    d.line((x0, y0, x1, y0), fill=gold, width=2)
    if divider: d.line(((x0+x1)/2, y0, (x0+x1)/2, y1), fill=gold, width=2)
    for index in visible:
        p = points[index]
        r = round(p.size/2)+2
        box = (round(p.x)-r, round(p.y)-r, round(p.x)+r, round(p.y)+r)
        frame.paste(original.crop(box), box)
    roster = [p for p in PLAYERS if p['c'] in {points[i].champ for i in visible}]
    return frame, portraits, roster, (x0, y0, x1, y1)


class GridTests(unittest.TestCase):
    def test_similar_faces_are_assigned_jointly_not_greedily(self):
        scores={0:{'W':.80,'S':.3,'G':.4,'M':.4},1:{'W':.4,'S':.74,'G':.4,'M':.81},
                3:{'W':.4,'S':.4,'G':.80,'M':.4},4:{'W':.4,'S':.60,'G':.4,'M':.79}}
        self.assertEqual(assign_visible_faces(scores,['W','S','G','M']),{0:'W',1:'S',3:'G',4:'M'})
        self.assertEqual(assign_visible_faces({0:{'A':.9,'B':.9},1:{'A':.9,'B':.9}},['A','B']),{})

    def test_scale_move_ultrawide_and_row_order(self):
        for w, h, step, dx, dy in ((1920, 1080, 76, 0, 0), (3440, 1440, 95, -90, 40), (1280, 720, 42, 30, -20)):
            with self.subTest(resolution=(w, h)):
                pts = anchors(w, h, step, dx, dy)
                layout = fit_grid(pts, PLAYERS, w, h)
                self.assertIsNotNone(layout)
                self.assertEqual(layout.columns, tuple(tuple(f'C{i}' for i in col) for col in ORDER))
                self.assertAlmostEqual(layout.rect[0] * h + w/2, pts[0].x - 1.75*step)
                self.assertAlmostEqual(layout.rect[1] * h, pts[0].y - step/2)
                self.assertAlmostEqual(layout.rect[3] * h, step*5)

    def test_obscured_portraits_do_not_get_guessed(self):
        pts = anchors()
        # Two unknown left rows remain blank; exactly one missing right can be inferred.
        layout = fit_grid([p for p in pts if p.champ not in ('C0', 'C1', 'C7')], PLAYERS, 1920, 1080)
        self.assertEqual(layout.columns[0], ('C2', None, 'C4', None, 'C3'))
        self.assertEqual(layout.columns[1], tuple(f'C{i}' for i in ORDER[1]))

    def test_rejects_hud_columns_inconsistent_grid_and_insufficient_anchors(self):
        pts = anchors()
        self.assertIsNone(fit_grid(pts[:5], PLAYERS, 1920, 1080))
        self.assertIsNone(fit_grid(pts[:2] + pts[5:7], PLAYERS, 1920, 1080))
        self.assertIsNone(fit_grid([Anchor(p.champ, p.x, p.y + (i % 3)*25, p.size, p.score) for i, p in enumerate(pts)], PLAYERS, 1920, 1080))
        self.assertIsNone(fit_grid([Anchor(p.champ, p.x, p.y, p.size, .5) for p in pts], PLAYERS, 1920, 1080))

    def test_team_sides_come_from_image_not_player_list(self):
        players = [dict(p, team='CHAOS' if p['team'] == 'ORDER' else 'ORDER') for p in PLAYERS]
        self.assertEqual(fit_grid(anchors(), players, 1920, 1080).teams, ('CHAOS', 'ORDER'))

    def test_duplicate_champions_are_ambiguous(self):
        players = [dict(p, c='same') for p in PLAYERS]
        pts = [Anchor('same', p.x, p.y, p.size, p.score) for p in anchors()]
        self.assertIsNone(fit_grid(pts, players, 1920, 1080))


class ImageTests(unittest.TestCase):
    def test_confirmed_frame_avoids_slow_full_screen_template_search(self):
        import cv2
        frame,portraits,players,_=framed_fixture(visible=range(10))
        with patch.object(cv2,'matchTemplate',wraps=cv2.matchTemplate) as matching:
            found=detect(frame,portraits,players)
        self.assertIsNotNone(found)
        self.assertTrue(matching.call_args_list)
        self.assertTrue(all(c.args[0].shape[1]<frame.width*.2 for c in matching.call_args_list))

    def test_existing_centre_badges_do_not_break_next_capture(self):
        frame,portraits,players,box=framed_fixture(visible=range(10))
        x0,y0,x1,y1=box; step=(y1-y0)/5; cx=(x0+x1)/2
        d=ImageDraw.Draw(frame)
        for row in range(5):
            cy=y0+(row+.5)*step
            d.rectangle((cx-step*.18,cy-step*.32,cx+step*.18,cy+step*.32),fill=(5,15,22))
        found=detect(frame,portraits,players)
        self.assertIsNotNone(found)
        self.assertEqual(found.columns,tuple(tuple(f'C{i}' for i in col) for col in ORDER))

    def test_question_marks_recover_peripheral_faces_without_roster_order(self):
        frame,portraits,points=fixture(); d=ImageDraw.Draw(frame)
        for p in points[5:]:
            d.rectangle((p.x-p.size*.14,p.y-p.size*.35,p.x+p.size*.14,p.y+p.size*.35),fill=(242,213,30))
        step=50; x0=points[0].x-step*1.75; y0=points[0].y-step/2
        layout=Layout(((x0-1280/2)/720,y0/720,step*15.25/720,step*5/720),
                      (tuple(f'C{i}' for i in ORDER[0]),(None,)*5),('ORDER','CHAOS'),.95,'frame')
        import cv2
        sources={c:cv2.cvtColor(np.asarray(Image.open(io.BytesIO(base64.b64decode(v))).convert('RGB')),cv2.COLOR_RGB2GRAY) for c,v in portraits.items()}
        found=recover_question_marks(layout,np.asarray(frame),sources,list(reversed(PLAYERS)))
        self.assertEqual(found.columns,tuple(tuple(f'C{i}' for i in col) for col in ORDER))
        ambiguous={c:sources['C5'] for c in sources}
        found=recover_question_marks(layout,np.asarray(frame),ambiguous,PLAYERS)
        self.assertEqual(found.columns[1],(None,)*5)

    def test_single_player_practice_at_different_scales(self):
        for w, h, step in ((1280, 720, 50), (2560, 1440, 86), (1720, 720, 52)):
            with self.subTest(resolution=(w, h)):
                frame, portraits, players, box = framed_fixture(w, h, step)
                found = detect(frame, portraits, players)
                self.assertIsNotNone(found)
                self.assertEqual(found.source, 'frame')
                self.assertEqual(found.columns, (('C2', None, None, None, None), (None,)*5))
                self.assertAlmostEqual(found.rect[0]*h+w/2, box[0], delta=5)
                self.assertAlmostEqual(found.rect[1]*h, box[1], delta=5)
                self.assertAlmostEqual(found.rect[3]*h, box[3]-box[1], delta=5)

    def test_incomplete_custom_teams_and_reordered_rows(self):
        frame, portraits, players, _ = framed_fixture(visible=(0, 2, 8))
        found = detect(frame, portraits, players)
        self.assertIsNotNone(found)
        self.assertEqual(found.columns, (('C2', None, 'C4', None, None), (None, None, None, 'C7', None)))

    def test_frame_with_full_teams_preserves_identity(self):
        frame, portraits, players, _ = framed_fixture(visible=range(10))
        found = detect(frame, portraits, players)
        self.assertEqual(found.columns, tuple(tuple(f'C{i}' for i in col) for col in ORDER))

    def test_frame_requires_divider_and_a_confirmed_portrait(self):
        frame, portraits, players, _ = framed_fixture()
        self.assertTrue(find_frames(np.asarray(frame)))
        self.assertIsNone(detect(frame, {}, players))
        empty, _, _, _ = framed_fixture(visible=())
        self.assertIsNone(detect(empty, portraits, players))
        no_divider, portraits, players, _ = framed_fixture(divider=False)
        self.assertIsNone(detect(no_divider, portraits, players))

    def test_unconfirmed_frame_does_not_disable_portrait_grid_fallback(self):
        frame, portraits, _ = fixture()
        with patch('tab_detect.find_frames', return_value=[(50, 50, 600, 250)]):
            found = detect(frame, portraits, PLAYERS)
        self.assertIsNotNone(found)
        self.assertEqual(found.source, 'portraits')

    def test_disjoint_vertical_edges_are_not_a_frame(self):
        im = Image.new('RGB', (1280, 720), (9, 22, 30))
        d = ImageDraw.Draw(im)
        d.line((250, 20, 250, 250), fill=(170, 140, 65), width=2)
        d.line((800, 251, 800, 490), fill=(170, 140, 65), width=2)
        self.assertFalse(find_frames(np.asarray(im)))

    def test_multiscale_circular_and_grayscale_portraits(self):
        for w, h, step in ((1280, 720, 50), (2560, 1440, 86)):
            with self.subTest(resolution=(w, h)):
                frame, portraits, pts = fixture(w, h, step)
                found = detect(frame, portraits, PLAYERS)
                self.assertIsNotNone(found)
                self.assertEqual(found.columns, tuple(tuple(f'C{i}' for i in col) for col in ORDER))
                self.assertAlmostEqual(found.rect[1]*h, pts[0].y-step/2, delta=4)

    def test_no_table_black_capture_missing_assets_and_cancellation(self):
        frame, portraits, _ = fixture()
        self.assertIsNone(detect(Image.new('RGB', frame.size), portraits, PLAYERS))
        self.assertIsNone(detect(frame, {}, PLAYERS))
        self.assertIsNone(detect(Image.effect_noise((1280, 720), 60).convert('RGB'), portraits, PLAYERS))
        cancel = threading.Event(); cancel.set()
        self.assertIsNone(detect(frame, portraits, PLAYERS, cancel))

    def test_capture_uses_game_bounds_and_excludes_layered_overlays(self):
        with patch('PIL.ImageGrab.grab', return_value=Image.new('RGB', (1920, 1080))) as grab:
            self.assertIsNone(capture_and_detect((-1920, -100, 1920, 1080), {}, [], threading.Event()))
        grab.assert_called_once_with(bbox=(-1920, -100, 0, 980), all_screens=True, include_layered_windows=False)


if __name__ == '__main__': unittest.main()
