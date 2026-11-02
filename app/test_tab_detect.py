"""Detection regression tests; synthetic images are NOT live-game accuracy evidence."""
import base64
import io
import threading
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

from tab_detect import Anchor, capture_and_detect, detect, fit_grid


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


class GridTests(unittest.TestCase):
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
