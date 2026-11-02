"""Проверка рейтинга инвентаря и ручки Tab без игры, клиента и сети.

DISPLAY=... SIM_OUT=/tmp python app/dev/sim_overlays.py
Скриншоты overlay_night.png / overlay_day.png; assertions проверяют перенос,
изменение размера, сохранение и скрытие ручки. На Linux не проверяет Win32 click-through.
"""
import copy
import os
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tkinter as tk
from PIL import ImageGrab
import core
import ui
import test_core as T
import test_tab_detect as TD
import tab_detect


class Settings(dict):
    saves = 0

    def save(self):
        self.saves += 1


def run():
    out = Path(os.environ.get('SIM_OUT', '/tmp'))
    out.mkdir(parents=True, exist_ok=True)
    for theme, filename in (('lol', 'overlay_night.png'), ('lol_day', 'overlay_day.png')):
        s = Settings(copy.deepcopy(ui.DEFAULTS))
        s['scale'], s['theme'], s['alpha'] = 125, theme, 100
        s['tab_rect'] = [-.52, .32, 1.04, .40]
        ui.apply_theme(s)
        root = tk.Tk()
        root.geometry('1920x1080+0+0')
        root.configure(bg=ui.C['deep'])
        tk.Label(root, text='LoL Helper · демонстрационные данные', bg=ui.C['deep'], fg=ui.C['fg'], font=('sans', 22)).place(x=40, y=25)
        tk.Label(root, text='Tab: клики проходят в игру; только золотая ручка принимает мышь.', bg=ui.C['deep'], fg=ui.C['mute'], font=('sans', 14)).place(x=40, y=75)
        app = SimpleNamespace(root=root, s=s, data=T.D, layout=lambda: {}, fs=lambda n: round(n * 1.25), pimg=lambda *a, **kw: None)
        original_rect = ui.game_rect
        ui.game_rect = lambda: (0, 0, 1920, 1080)
        try:
            tab = ui.TabPlates(app)
            tab.unlock(True)
            tab.demo()
            tab.deiconify()
            rank = ui.InventoryOverlay(app, (1510, 650))
            rank.demo()
            root.update()
            assert tab.handle.winfo_viewable()
            assert not tab.lbl.bind('<ButtonPress-1>')
            assert not tab.bind('<ButtonPress-1>')
            assert tab.handle.winfo_width() < 350
            before = list(tab.rect())
            tab._start(SimpleNamespace(x_root=500, y_root=250, state=0))
            tab._move(SimpleNamespace(x_root=608, y_root=304))
            tab._end(None)
            assert tab.rect() == ui.tab_rect_drag(before, .1, .05)
            before = list(tab.rect())
            tab._start(SimpleNamespace(x_root=500, y_root=250, state=1))
            tab._move(SimpleNamespace(x_root=554, y_root=277))
            tab.unlock(False)   # отпускание Alt во время переноса тоже сохраняет
            assert tab.rect() == ui.tab_rect_drag(before, .05, .025, True)
            assert s.saves == 2
            root.update()
            assert not tab.handle.winfo_viewable()
            tab.unlock(True)
            root.update()
            assert tab.handle.winfo_viewable()
            tab.withdraw()
            root.update()
            assert not tab.handle.winfo_viewable()
            # Стандартная рамка для наглядного скриншота.
            s['tab_rect'] = [-.52, .32, 1.04, .40]
            tab.demo()
            tab.deiconify()
            tab.lift()
            rank.lift()
            root.update()
            assert tab.winfo_width() > 1000 and tab.winfo_height() > 400
            print('Tab geometry:', tab.winfo_geometry(), 'label:', tab.lbl.winfo_geometry())
            ImageGrab.grab(xdisplay=os.environ.get('DISPLAY')).save(out / filename)
            print('ok', theme, 'handle move/resize/save/hide; screenshot', out / filename)
            # Detection output drives the real Tk window, not a second drawing of it.
            frame, portraits, _ = TD.fixture(1920, 1080, 65)
            found = tab_detect.detect(frame, portraits, TD.PLAYERS)
            assert found is not None
            tab.auto_layout = found
            players = [dict(p, pos=core.ROLES[i % 5], igold=4000+i*450) for i, p in enumerate(TD.PLAYERS)]
            g = SimpleNamespace(players=players, allies=players[:5], enemies=players[5:], my_team='ORDER')
            tab.show(g)
            tab.deiconify(); tab.lift()
            root.update()
            assert not tab.handle.winfo_viewable()  # automatic placement needs no drag target
            assert tab.data[0][0][0]['v'] == players[2]['igold']
            X, Y, W, H, side, top = tab.geom()
            assert abs(Y - (1080 * .28 - 65/2)) < 4
            ImageGrab.grab(xdisplay=os.environ.get('DISPLAY')).save(out / ('auto_' + filename))
            print('ok', theme, 'detected row order/geometry and hidden handle')
            frame, portraits, roster, box = TD.framed_fixture(1920, 1080, 65)
            tab.auto_layout = tab_detect.detect(frame, portraits, roster)
            assert tab.auto_layout and tab.auto_layout.source == 'frame'
            player = dict(roster[0], pos='', igold=1250)
            tab.show(SimpleNamespace(players=[player], allies=[player], enemies=[], my_team='ORDER'))
            tab._detection_status('Таблица найдена по рамке · распознаны строки 1/1')
            root.update()
            assert tab.data[0][0][0]['v'] == 1250
            assert all(row == (None, None) for row in tab.data[0][1:])
            assert abs(tab.geom()[1] - box[1]) < 5
            ImageGrab.grab(xdisplay=os.environ.get('DISPLAY')).save(out / ('practice_' + filename))
            print('ok', theme, 'one-player practice, no fake rows, status updated')
        finally:
            root.destroy()
            ui.game_rect = original_rect


if __name__ == '__main__':
    run()
