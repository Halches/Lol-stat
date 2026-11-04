"""Performance regressions must preserve pixels and deliver every queued event."""
import copy
import queue
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import render
import ui
from PIL import Image


class RenderReuse(unittest.TestCase):
    def setUp(self):
        # Cache tests use window doubles; the native compositor has its own test.
        compositor=patch.object(ui.layered_image,'present')
        self.present=compositor.start()
        self.addCleanup(compositor.stop)

    def card(self):
        return render.Card(dict(ui.C), 'Forum', title='Показатели').row(
            ('text', 'Фарм', 'fg', 12, False), ('cell', '8,1', 'gold', 16, True, 60, 'r'))

    def overlay(self):
        return SimpleNamespace(lbl=Mock(), geometry=Mock(),app=SimpleNamespace(s={'alpha':100}),
                               _drag=False, winfo_x=lambda:0,
                               winfo_screenwidth=lambda:1920)

    def test_unchanged_card_does_not_render_or_replace_tk_image(self):
        overlay=self.overlay()
        with patch.object(ui.ImageTk, 'PhotoImage', return_value=object()) as photo:
            first=self.card()
            with patch.object(first, 'render', wraps=first.render) as paint:
                ui.Overlay.put(overlay, first)
                ui.Overlay.put(overlay, self.card())
                paint.assert_called_once()
            photo.assert_called_once()
            overlay.lbl.configure.assert_called_once()

    def test_signature_tracks_theme_scale_text_and_image_mutation(self):
        card=self.card(); image=Image.new('RGBA',(8,8),'red')
        card.row(('img',image)); original=card.signature()
        image.putpixel((0,0),(0,0,255,255))
        self.assertNotEqual(original,card.signature())
        for field,value in [('k',1.5),('plate',False),('width',500),('accent','bad'),('fn','Cinzel')]:
            changed=copy.copy(card);setattr(changed,field,value)
            self.assertNotEqual(card.signature(),changed.signature())
        card.t['fg']='#ffffff'
        self.assertNotEqual(original,card.signature())

    def test_changed_card_renders_and_failed_render_can_retry(self):
        overlay=self.overlay(); card=self.card()
        with patch.object(ui.ImageTk,'PhotoImage',return_value=object()):
            ui.Overlay.put(overlay,card)
            card.row(('text','Новый результат','bad',12,False))
            with patch.object(card,'render',side_effect=ValueError('paint failed')):
                with self.assertRaises(ValueError):ui.Overlay.put(overlay,card)
            ui.Overlay.put(overlay,card)
            self.assertEqual(overlay.lbl.configure.call_count,2)

    def test_round_icons_are_bounded_and_replaced_sources_are_not_stale(self):
        icons=ui.Icons(SimpleNamespace());image=Image.new('RGBA',(16,16),'red')
        icons._pil=Mock(return_value=image)
        first=icons.rounded_pil('champ','Ahri',24)
        self.assertIs(first,icons.rounded_pil('champ','Ahri',24))
        self.assertNotEqual(first.tobytes(),icons.rounded_pil('champ','Ahri',24,gray=True).tobytes())
        for key in range(150):icons.rounded_pil('item',key,16)
        self.assertEqual(len(icons.rounded),128)
        icons._pil.return_value=Image.new('RGBA',(16,16),'blue')
        self.assertNotEqual(first.tobytes(),icons.rounded_pil('champ','Ahri',24).tobytes())

    def test_cached_material_is_not_modified_by_draws(self):
        frame=render._badge_frame(160,264);before=frame.tobytes()
        render.hud_badge('123',1,'red',40,66)
        self.assertEqual(before,frame.tobytes())
        card=self.card();first=card.render().tobytes()
        self.assertEqual(first,card.render().tobytes())

    def test_hint_reuses_image_and_still_expires(self):
        overlay=self.overlay()
        overlay.items=[(99,'Подготовь обзор у реки.','fg','12:40')]
        overlay.app=SimpleNamespace(hidden=False,s={'widgets':{'hints':True},'alpha':100})
        overlay.unlocked=False;overlay.withdraw=Mock();overlay.deiconify=Mock()
        overlay.card=lambda **kw:render.Card(dict(ui.C),'Forum',**kw)
        overlay.put=lambda card:ui.Overlay.put(overlay,card)
        with patch.object(ui.ImageTk,'PhotoImage',return_value=object()) as photo,patch.object(ui.time,'time',return_value=100):
            ui.HintsOverlay.show(overlay);ui.HintsOverlay.show(overlay)
            photo.assert_called_once()
            self.assertEqual(overlay.deiconify.call_count,2)
        with patch.object(ui.time,'time',return_value=115):ui.HintsOverlay.show(overlay)
        overlay.withdraw.assert_called_once()
        self.assertEqual(overlay.items,[])

    def test_tab_reuses_pixels_but_updates_values_geometry_and_edit_frame(self):
        tab=SimpleNamespace(geom=lambda:(0,0,600,300,0,100),k=lambda:1,
                            unlocked=False,_left_ally=True,totals=(100,90),lbl=Mock(),geometry=Mock(),
                            app=SimpleNamespace(s={'scale':100,'alpha':100}),rect=lambda:[0,0,1,1],_place_handle=Mock())
        rows=[({'v':100},{'v':90})]
        with patch.object(ui.ImageTk,'PhotoImage',return_value=object()),patch.object(ui,'game_rect',return_value=(0,0,1920,1080)),patch.object(ui.render,'tab_plates',return_value=Image.new('RGBA',(600,400))) as paint:
            ui.TabPlates.draw(tab,rows);ui.TabPlates.draw(tab,rows)
            self.assertEqual(paint.call_count,1)
            rows[0][0]['v']=110;ui.TabPlates.draw(tab,rows)
            self.assertEqual(paint.call_count,2)
            tab.unlocked=True;ui.TabPlates.draw(tab,rows)
            self.assertEqual(paint.call_count,3)
            tab.geom=lambda:(10,0,600,300,0,100);ui.TabPlates.draw(tab,rows)
            self.assertEqual(paint.call_count,4)


class EventQueue(unittest.TestCase):
    def app(self,count=100):
        app=SimpleNamespace(q=queue.Queue(),root=Mock(),status=Mock(),on_me=Mock())
        app.drain=lambda:ui.App.drain(app)
        for i in range(count):app.q.put(('me',i,None,None))
        return app

    def test_burst_yields_and_keeps_all_events_in_order(self):
        app=self.app()
        with patch.object(ui.time,'perf_counter',return_value=0):app.drain()
        self.assertEqual(app.on_me.call_count,32)
        self.assertEqual(app.root.after.call_args.args[0],1)
        while not app.q.empty():app.drain()
        self.assertEqual([c.args[0] for c in app.on_me.call_args_list],list(range(100)))

    def test_slow_event_yields_before_next_event(self):
        app=self.app(3)
        with patch.object(ui.time,'perf_counter',side_effect=[0,.009]):app.drain()
        self.assertEqual(app.on_me.call_count,1)
        self.assertEqual(app.q.qsize(),2)
        self.assertEqual(app.root.after.call_args.args[0],1)

    def test_bad_event_does_not_stop_following_events_or_polling(self):
        app=self.app(3);app.on_me.side_effect=[ValueError('bad snapshot'),None,None]
        with patch.object(ui,'log_error') as log:app.drain()
        log.assert_called_once()
        self.assertEqual(app.on_me.call_count,3)
        self.assertEqual(app.root.after.call_args.args[0],300)


if __name__=='__main__':unittest.main()
