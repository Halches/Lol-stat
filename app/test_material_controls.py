"""Native UI regressions for material controls and static scroll backgrounds."""
import os
import unittest
import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace
from unittest.mock import Mock
import ui
import ui_skin


@unittest.skipUnless(os.name=='nt' or os.environ.get('DISPLAY'),'Requires a native Tk display')
class MaterialControls(unittest.TestCase):
    def setUp(self):
        self.root=tk.Tk();self.root.geometry('500x280+0+0')
        ui_skin.material_ui.Manager(self.root,ui.THEMES['lol'][1])
        self.frame=ui_skin.Frame(self.root,bg=ui.THEMES['lol'][1]['bg'])
        self.frame.pack(fill='both',expand=True)

    def tearDown(self):
        self.root.destroy()

    def test_page_refresh_keeps_background_and_resize_handler(self):
        resize=Mock();self.frame.bind('<Configure>',resize)
        label=ui_skin.Label(self.frame,text='Коротко',anchor='w');label.pack()
        self.root.update()
        self.assertTrue(resize.called)
        photo=self.frame._material_photo
        self.assertIsNotNone(photo)
        for child in self.frame.winfo_children():child.destroy()
        variable=tk.StringVar(self.root,value='Новые данные')
        label=ui_skin.Label(self.frame,textvariable=variable,anchor='w');label.pack()
        self.root.update();before=label.winfo_reqwidth()
        variable.set('Очень длинное обновление показателя')
        self.root.update()
        self.assertGreater(label.winfo_reqwidth(),before)
        self.assertEqual(label.cget('text'),variable.get())
        self.assertIs(self.frame._material_photo,photo)

    def test_moving_static_content_reuses_background_pixels(self):
        row=ui_skin.Frame(self.frame,bg=ui.THEMES['lol'][1]['panel'],width=200,height=70)
        row.place(x=0,y=0);self.root.update();photo=row._material_photo
        row.place_configure(y=100);self.root.update()
        self.assertIs(row._material_photo,photo)

    def test_toggle_keeps_native_variable_and_disabled_state(self):
        value=tk.BooleanVar(self.root,value=False);changed=Mock()
        button=ui_skin.Checkbutton(self.frame,text='Включить',variable=value,command=changed)
        button.pack();self.root.update();button.invoke()
        self.assertTrue(value.get());changed.assert_called_once()
        value.set(False);self.root.update();button.configure(state='disabled');button.invoke()
        self.assertFalse(value.get());changed.assert_called_once()

    def test_styled_combobox_keeps_mouse_popup_and_keyboard_selection(self):
        style=ttk.Style(self.root);style.theme_use('clam')
        app=SimpleNamespace(root=self.root,skin_palette=ui.THEMES['lol'][1],s={'scale':100})
        ui_skin.install_fields(app,style)
        value=tk.StringVar(self.root,value='Все роли');changed=Mock()
        combo=ttk.Combobox(self.frame,textvariable=value,values=['Все роли','Лес','Центр'],
                           state='readonly',style='History.TCombobox')
        combo.pack(padx=20,pady=20);combo.bind('<<ComboboxSelected>>',changed)
        self.root.update()
        combo.event_generate('<Button-1>',x=combo.winfo_width()-12,y=combo.winfo_height()//2)
        self.root.update()
        popup=str(self.root.tk.call('ttk::combobox::PopdownWindow',combo))
        self.assertTrue(int(self.root.tk.call('winfo','ismapped',popup)))
        listbox=popup+'.f.l'
        self.root.tk.call('event','generate',listbox,'<KeyPress-Down>')
        self.root.tk.call('event','generate',listbox,'<KeyPress-Return>')
        self.root.update()
        self.assertEqual(value.get(),'Лес');changed.assert_called_once()
        self.assertFalse(int(self.root.tk.call('winfo','ismapped',popup)))
        combo.configure(state='disabled')
        combo.event_generate('<Button-1>',x=combo.winfo_width()-12,y=combo.winfo_height()//2)
        self.root.update()
        self.assertFalse(int(self.root.tk.call('winfo','ismapped',popup)))

    def test_styled_entry_keeps_editing_selection_and_theme_rebuild(self):
        style=ttk.Style(self.root);style.theme_use('clam')
        app=SimpleNamespace(root=self.root,skin_palette=ui.THEMES['lol'][1],s={'scale':100})
        ui_skin.install_fields(app,style)
        value=tk.StringVar(self.root,value='Атрокс')
        entry=ttk.Entry(self.frame,textvariable=value,style='History.TEntry')
        entry.pack(padx=20,pady=20);self.root.update();entry.focus_force();entry.icursor('end')
        self.root.update();entry.event_generate('<KeyPress-BackSpace>');self.root.update()
        self.assertEqual(value.get(),'Атрок')
        entry.selection_range(0,2);entry.event_generate('<KeyPress-Delete>');self.root.update()
        self.assertEqual(value.get(),'рок')
        app.skin_palette=ui.THEMES['lol_day'][1];ui_skin.install_fields(app,style)
        self.root.update();entry.insert('end','!');self.assertEqual(value.get(),'рок!')

    def test_viewport_art_does_not_extend_scrolling_or_destroy_content(self):
        view=ui_skin.material_ui.Viewport(self.frame,bg=ui.THEMES['lol'][1]['bg'],highlightthickness=0)
        view.pack(fill='both',expand=True)
        content=tk.Frame(view,width=200,height=900)
        window=view.create_window((0,0),window=content,anchor='nw');self.root.update()
        self.assertIsNotNone(view._viewport_photo)
        view.configure(scrollregion=view.bbox('all'));view.yview_moveto(.5)
        self.assertEqual(view.bbox('all'),(0,0,200,900))
        content.configure(height=90);self.root.update();view.configure(scrollregion=view.bbox('all'))
        self.assertEqual(view.bbox('all'),(0,0,200,90));self.assertEqual(view.yview(),(0,1))
        self.root._material.release(view)
        self.assertEqual(view.type(window),'window')
        view._material_paint(force=True);self.root.update()
        self.assertIsNotNone(view._viewport_photo)


if __name__=='__main__':unittest.main()
