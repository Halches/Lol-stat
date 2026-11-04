"""Regressions for transparent foregrounds, team tints and missing chart data."""
import os
import unittest
from PIL import Image
import render
import home_charts
import home_model
import ui


class BlossomRenderTests(unittest.TestCase):
    def test_background_is_faint_but_text_remains_opaque(self):
        card=render.Card(ui.THEMES['lol'][1],'Forum',plate=True)
        card.row(('text','350','fg',24,True))
        image=card.render()
        self.assertLessEqual(image.getpixel((image.width//2,image.height-8))[3],50)
        self.assertEqual(image.getchannel('A').getextrema()[1],255)

    def test_team_shading_invalidates_cached_card(self):
        card=render.Card(ui.THEMES['lol'][1],'Forum',plate=True)
        card.row(('text','Виктор','fg',11,False),tint='blue')
        blue=card.signature()
        blue_image=card.render().tobytes()
        card.row_tints[0]='red'
        self.assertNotEqual(blue,card.signature())
        self.assertNotEqual(blue_image,card.render().tobytes())

    def test_empty_and_partial_match_metrics_render_at_compact_sizes(self):
        for games in ([],[{'k':0,'d':0,'a':0,'w':1,'csm':0,'vsm':None}]):
            snapshot=home_model.snapshot(games)
            for key in ('wr','kda','csm','vsm'):
                image=home_charts.metric_image(snapshot,key,'Показатель','Нет данных',
                                               180,148,ui.THEMES['lol'][1],1)
                self.assertEqual(image.size,(180,148))

    @unittest.skipUnless(os.name=='nt','Windows per-pixel compositor')
    def test_native_layered_window_accepts_rgba_pixels(self):
        import tkinter as tk
        import layered_image
        root=tk.Tk()
        root.withdraw()
        window=tk.Toplevel(root)
        try:
            window.overrideredirect(True)
            window.geometry('100x50+0+0')
            window.attributes('-alpha',.9)
            window.update_idletasks()
            layered_image.present(window,Image.new('RGBA',(100,50),(80,40,90,30)),100)
        finally:
            window.destroy()
            root.destroy()


if __name__=='__main__':
    unittest.main()
