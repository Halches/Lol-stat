"""Exercise real Tk scrolling, including Windows CI's native child windows."""
import os
import json
from pathlib import Path
import tempfile
import time
import tkinter as tk
from types import SimpleNamespace
import unittest
from scroll_canvas import ScrollCanvas


class Scrolling(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            if os.name == 'nt':
                raise
            self.skipTest(str(error))
        self.root.geometry('600x400+0+0')
        self.errors = []
        self.root.report_callback_exception = lambda *args: self.errors.append(str(args[1]))
        self.cv = ScrollCanvas(self.root, highlightthickness=0)
        self.cv.pack(fill='both', expand=True)
        body = tk.Frame(self.cv)
        self.cv.create_window(0, 0, window=body, anchor='nw', width=580)
        for i in range(80):
            row = tk.Frame(body, bg='#102132', height=48)
            row.pack(fill='x', pady=4)
            tk.Label(row, text=f'Матч {i} · 7 / 2 / 10').pack(side='left')
            tk.Button(row, text='Подробнее').pack(side='right')
        self.root.update()
        self.cv.configure(scrollregion=self.cv.bbox('all'))
        self.root.update()
        self.addCleanup(self.root.destroy)

    def settle(self):
        self.root.after(55, self.root.quit)
        self.root.mainloop()
        self.assertEqual(self.errors, [])

    def test_burst_is_bounded_and_applied_once(self):
        before = self.cv.yview()
        for _ in range(300):
            self.cv.wheel(SimpleNamespace(delta=-120))
        job = self.cv._scroll_job
        self.assertIsNotNone(job)
        self.assertEqual(before, self.cv.yview())
        self.assertLessEqual(self.cv._pending_units, 400 // 24)
        self.settle()
        self.assertIsNone(self.cv._scroll_job)
        self.assertGreater(self.cv.yview()[0], before[0])
        self.assertLessEqual(self.cv.canvasy(0), 400)

    def test_small_wheel_deltas_and_direction(self):
        for _ in range(3):self.cv.wheel(SimpleNamespace(delta=-30))
        self.assertIsNone(self.cv._scroll_job)
        self.cv.wheel(SimpleNamespace(delta=-30))
        self.settle()
        self.assertEqual(self.cv.canvasy(0), 72)
        self.cv.wheel(SimpleNamespace(delta=120))
        self.settle()
        self.assertEqual(self.cv.canvasy(0), 0)

    def test_scrollbar_overrides_pending_wheel(self):
        self.cv.wheel(SimpleNamespace(delta=-120))
        self.cv.yview('moveto', .5)
        position = self.cv.yview()
        self.settle()
        self.assertEqual(self.cv.yview(), position)
        self.assertIsNone(self.cv._scroll_job)

    def test_destroy_cancels_callbacks(self):
        self.cv.wheel(SimpleNamespace(delta=-120))
        self.cv.destroy()
        self.settle()
        self.assertIsNone(self.cv._scroll_job)

    def test_scroll_moves_window_without_native_canvas_yview(self):
        logical = self.cv.bbox('all')
        self.cv.yview_moveto(.5)
        self.settle()
        self.assertEqual(self.cv.bbox('all'), logical)
        self.assertEqual(tk.Canvas.yview(self.cv)[0], 0)
        self.assertLess(tk.Canvas.coords(self.cv, self.cv._content_window)[1], 0)
        self.assertGreater(self.cv.yview()[0], 0)
        self.cv.yview_moveto(1)
        self.assertEqual(self.cv.yview()[1], 1)

    def test_content_shrink_resets_offset_and_thumb(self):
        values = []
        self.cv.configure(yscrollcommand=lambda *v: values.append(v))
        self.cv.yview_moveto(1)
        self.cv.configure(scrollregion=(0,0,580,100))
        self.assertEqual(self.cv.yview(), (0,1))
        self.assertEqual(values[-1], (0,1))
        self.assertEqual(tk.Canvas.coords(self.cv, self.cv._content_window)[1], 0)

    def test_review_latency_log_records_stalls_and_restores_tk(self):
        from ui_latency import LatencyLog
        original = tk.CallWrapper.__call__
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'latency.json'
            log = LatencyLog(self.root, path)
            try:
                self.root.after(0, lambda: time.sleep(.16))
                self.settle()
            finally:
                log.close()
            data = json.loads(path.read_text(encoding='utf-8'))
            self.assertGreaterEqual(data['max_gap_ms'], 150)
            self.assertTrue(data['slow_callbacks'])
            self.assertIs(tk.CallWrapper.__call__, original)


if __name__ == '__main__':unittest.main()
