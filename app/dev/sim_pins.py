"""Real Tk pin lifecycle and widget gallery; no client or personal settings."""
import copy
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import tkinter as tk
from PIL import ImageGrab
import ui
import test_core as T


class Settings(dict):
    def save(self): pass


for theme in ('lol','lol_day'):
    s = Settings(copy.deepcopy(ui.DEFAULTS)); s.update(theme=theme,scale=125,alpha=100)
    ui.apply_theme(s)
    root = tk.Tk(); root.geometry('1920x1080+0+0'); root.configure(bg=ui.C['deep'])
    root.update()
    app = SimpleNamespace(root=root,s=s,data=T.D,hidden=False,layout=lambda:{},pimg=lambda *a,**kw:None,
                          role_pil=lambda *a:None,last_game=SimpleNamespace(t=760))
    wins = []
    for cls,xy in ((ui.HintsOverlay,(40,80)),(ui.PerfOverlay,(660,80)),(ui.LaneOverlay,(1320,80)),
                   (ui.InventoryOverlay,(40,380)),(ui.ItemOverlay,(660,380)),(ui.TimersOverlay,(1320,380)),
                   (ui.ArenaOverlay,(660,650))):
        w = cls(app,xy); wins.append(w)
        if isinstance(w,ui.HintsOverlay):
            w.push('Дракон через 45 секунд. Подготовь обзор у реки.'); w.show()
        elif isinstance(w,ui.LaneOverlay):
            w.put(w.card().row(('text','+850','blue',24,True),('text','против Виктора','mute',11,False))
                  .row(('text','Уровень 11 / 10 · CS 92 / 80','mute',10,False)))
        elif isinstance(w,ui.ItemOverlay):
            w.put(w.card().row(('text','ещё 350','gold',24,True)).row(('text','Длинный меч','fg',12,False)))
        else: w.demo()
        w.deiconify(); root.update()
        assert w.pin_window.winfo_viewable(), w.key
        with patch.object(ui,'click_through') as through:
            w.unlock(True)
            w.pin_button.invoke()
            assert w.pinned and s['widget_pins'][w.key]
            through.assert_called_with(w,True)
            w._start(SimpleNamespace(x_root=300,y_root=300)); assert w._drag is None
            w.unlock(False); w.unlock(True); through.assert_called_with(w,True)
            w.pin_button.invoke(); assert not w.pinned
            through.assert_called_with(w,False)
            w.unlock(False); through.assert_called_with(w,True)
        w.withdraw(); root.update(); assert not w.pin_window.winfo_viewable()
        w.deiconify(); root.update(); assert w.pin_window.winfo_viewable()
        w.pin_button.invoke()  # final screenshot: gold means pinned
    tab = ui.TabPlates(app); assert tab.pin_window is None; tab.destroy()
    root.update()
    out = Path(os.environ.get('SIM_OUT','/tmp')); out.mkdir(parents=True,exist_ok=True)
    ImageGrab.grab(xdisplay=os.environ.get('DISPLAY')).save(out/f'pins_{theme}.png')
    print('OK',theme,'all seven widgets: pin/unpin during Alt, no drag, hide/show, Tab excluded')
    root.destroy()
