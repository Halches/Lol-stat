# Окна LoL Helper: панель управления, виджеты поверх игры, дашборд на втором мониторе, таблица по Tab, итог игры.
# Внешний вид (тема, акцент, шрифт, иконки) настраивается на вкладке «Вид» и применяется сразу: окна пересобираются.
import base64, io, json, os, queue, threading, time, urllib.request
import tkinter as tk
from tkinter import ttk

import core, lcu
from voice import Voice, VOICES, SOUNDS

try:
    from PIL import Image, ImageOps, ImageTk
    import render
except Exception:      # без Pillow программа работает, но без картинок
    Image = None

IS_WIN = os.name == 'nt'
if IS_WIN:
    import ctypes
    U32 = ctypes.windll.user32

THEMES = {
    'hextech': ('Хекстек', {'bg': '#010a13', 'panel': '#0a1622', 'line': '#1f3442', 'fg': '#f0e6d2', 'mute': '#a09b8c', 'gold': '#c8aa6e',
                            'good': '#3fc28a', 'bad': '#e8584f', 'blue': '#2fb5e8', 'red': '#e8584f'}),
    'night': ('Ночь', {'bg': '#10141a', 'panel': '#181e26', 'line': '#2a323d', 'fg': '#e9e4d8', 'mute': '#8d96a3', 'gold': '#c8aa6e',
                       'good': '#5cc98a', 'bad': '#e8665f', 'blue': '#5aa9e6', 'red': '#e0605a'}),
    'void': ('Бездна', {'bg': '#0d0a17', 'panel': '#171126', 'line': '#2e2446', 'fg': '#ece6fa', 'mute': '#9a90b3', 'gold': '#b48cff',
                        'good': '#5cd6a0', 'bad': '#ff6b81', 'blue': '#6ab0ff', 'red': '#ff6b81'}),
    'light': ('Светлая', {'bg': '#f4f1ea', 'panel': '#ffffff', 'line': '#d9d2c3', 'fg': '#1d1f24', 'mute': '#6b6f78', 'gold': '#9a7b3c',
                          'good': '#1f8f53', 'bad': '#c43c35', 'blue': '#2a6fb0', 'red': '#c0453f'}),
}
ACCENTS = {'theme': 'Как в теме', '#c8aa6e': 'Золото', '#0ac8b9': 'Бирюза', '#4aa3ff': 'Синий', '#b48cff': 'Фиолетовый',
           '#ff7a59': 'Оранжевый', '#ff6b81': 'Розовый', '#5cc98a': 'Зелёный'}
FONTS = ['Segoe UI', 'Bahnschrift', 'Calibri', 'Trebuchet MS', 'Verdana', 'Consolas']
C = dict(THEMES['hextech'][1])
F = {'font': 'Segoe UI'}
KEY = '#010203'   # цвет-ключ для виджетов без фона

MODES = {'off': 'Выкл', 'text': 'Текст', 'beep': 'Сигнал', 'voice': 'Голос'}
WIDGETS = {'hints': 'Подсказки', 'perf': 'Показатели (CS, золото, KDA…)', 'lane': 'Оппонент на линии', 'gold': 'Золото по линиям',
           'item': 'Золото до предмета', 'timers': 'Таймеры объектов'}
SHOW = {'portraits': 'Портреты чемпионов', 'items': 'Иконки предметов (иначе названия)', 'ranks': 'Эмблемы и звания',
        'spells': 'Заклинания призывателя', 'runes': 'Ключевые руны', 'scout': 'Разведка врагов (серия, игры на чемпионе)'}
RAW = 'https://raw.githubusercontent.com/Halches/Lol-stat/main/'
TIER_RU = {'IRON': 'Железо', 'BRONZE': 'Бронза', 'SILVER': 'Серебро', 'GOLD': 'Золото', 'PLATINUM': 'Платина', 'EMERALD': 'Изумруд',
           'DIAMOND': 'Алмаз', 'MASTER': 'Мастер', 'GRANDMASTER': 'Грандмастер', 'CHALLENGER': 'Претендент'}


# ---------------- Windows ----------------

def dpi_aware():
    if IS_WIN:
        try: ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try: U32.SetProcessDPIAware()
            except Exception: pass


def click_through(win, on):
    """Клик проходит сквозь окно в игру (WS_EX_TRANSPARENT), окно не забирает фокус."""
    if not IS_WIN: return
    h = U32.GetParent(win.winfo_id())
    s = U32.GetWindowLongW(h, -20) | 0x80000 | 0x80 | 0x08000000
    s = s | 0x20 if on else s & ~0x20
    U32.SetWindowLongW(h, -20, s)


VK = {'ctrl': 0x11, 'shift': 0x10, 'alt': 0x12, 'tab': 0x09, 'space': 0x20, 'grave': 0xC0, 'insert': 0x2D, 'home': 0x24,
      'end': 0x23, 'pageup': 0x21, 'pagedown': 0x22, 'capslock': 0x14, 'win': 0x5B}
VK.update({f'f{i}': 0x6F + i for i in range(1, 25)})
VK.update({ch: ord(ch.upper()) for ch in 'abcdefghijklmnopqrstuvwxyz0123456789'})


def key_down(vk):
    return IS_WIN and bool(U32.GetAsyncKeyState(vk) & 0x8000)


def combo_down(combo):
    keys = [k for k in (combo or '').lower().split('+') if k]
    return bool(keys) and all(k in VK and key_down(VK[k]) for k in keys)


def game_focused():
    if not IS_WIN: return False
    b = ctypes.create_unicode_buffer(128)
    U32.GetWindowTextW(U32.GetForegroundWindow(), b, 128)
    return b.value.startswith('League of Legends (TM)')


def screens():
    """(подпись набора мониторов, основной экран w,h, виртуальный экран x,y,w,h)"""
    if not IS_WIN: return '1:1920x1080', (1920, 1080), (0, 0, 1920, 1080)
    g = U32.GetSystemMetrics
    v = (g(76), g(77), g(78), g(79))
    return f'{g(80)}:{v[2]}x{v[3]}', (g(0), g(1)), v


# ---------------- Настройки ----------------

def app_home():
    d = os.path.join(os.environ.get('APPDATA') or os.path.expanduser('~'), 'LoLHelper')
    os.makedirs(d, exist_ok=True)
    return d


DEFAULTS = {
    'hints': {h[0]: h[3] for h in core.HINTS if h[0] not in core.HINT_ROLES},
    'hints_role': {r: {h[0]: h[3] for h in core.HINTS if h[0] in core.HINT_ROLES and r in core.HINT_ROLES[h[0]]} for r in core.ROLES},
    'hint_preset': 'TOP',
    'widgets': {k: True for k in WIDGETS},
    'perf': {'metrics': {'csm': True, 'gpm': True, 'kda': True, 'kp': True, 'vsm': True}, 'layout': 'vertical', 'compare': 'norm'},
    'tab_row': 46, 'tab_gap': 40, 'tab_swap': False,
    'dashboard': True, 'scoreboard': True, 'postgame': True, 'auto_import': False,
    'theme': 'hextech', 'accent': 'theme', 'font': 'Segoe UI', 'scale': 100, 'icon': 36, 'alpha': 90, 'widget_bg': 'panel',
    'show': {k: True for k in SHOW},
    'layout': {},
    'keys': {'mute': 'ctrl+shift+m', 'hide': 'ctrl+shift+h', 'scoreboard': 'tab', 'drag': 'alt'},
    'voice': 'dmitri', 'volume': 80, 'rate': 1.0, 'master': 100, 'beep_volume': 70, 'sound': 'bell',
    'obj': dict(core.OBJ), 'who': '', 'auto_update': True,
}
SECTIONS = {   # что сбрасывает кнопка «По умолчанию» в каждом разделе
    'hints': ['hints', 'hints_role'], 'voice': ['voice', 'volume', 'rate', 'master', 'beep_volume', 'sound'],
    'look': ['theme', 'accent', 'font', 'scale', 'icon', 'alpha', 'widget_bg', 'show'],
    'windows': ['widgets', 'perf', 'tab_row', 'tab_gap', 'tab_swap', 'dashboard', 'scoreboard', 'postgame', 'layout'], 'keys': ['keys'], 'obj': ['obj'],
}


class Settings(dict):
    def __init__(self, home):
        super().__init__()
        self.path = os.path.join(home, 'settings.json')
        try: saved = json.load(open(self.path, encoding='utf-8'))
        except Exception: saved = {}
        for k, v in DEFAULTS.items():
            self[k] = ({**v, **saved.get(k, {})} if isinstance(v, dict) else saved.get(k, v))

    def reset(self, keys):
        for k in keys:
            v = DEFAULTS[k]
            self[k] = json.loads(json.dumps(v))
        self.save()

    def save(self):
        tmp = self.path + '.tmp'
        json.dump(dict(self), open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        os.replace(tmp, self.path)


def apply_theme(s):
    C.clear(); C.update(THEMES.get(s['theme'], THEMES['hextech'])[1])
    if s['accent'] != 'theme': C['gold'] = s['accent']
    F['font'] = s['font']


# ---------------- Картинки ----------------

def bundle_dir():
    import sys
    return getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))


class Icons:
    """Портреты, предметы, заклинания, руны, эмблемы из assets.json; новых чемпионов берёт из клиента."""

    def __init__(self, app):
        self.app, self.cache, self.raw = app, {}, {}
        try: self.a = json.load(open(os.path.join(bundle_dir(), 'assets.json')))
        except Exception: self.a = {}

    def _pil(self, grp, key):
        k = (grp, key)
        if k in self.raw: return self.raw[k]
        im = None
        b64 = (self.a.get(grp) or {}).get(str(key))
        if not b64 and grp == 'spell':
            b64 = next((v for kk, v in (self.a.get('spell') or {}).items() if str(key).startswith(kk)), None)
        try:
            if b64: im = Image.open(io.BytesIO(base64.b64decode(b64))).convert('RGBA')
            elif grp == 'champ':
                cid = next((i for i, c in self.app.data.ids.items() if c == key), None)
                b = cid and self.app.client.image(f'/lol-game-data/assets/v1/champion-icons/{cid}.png')
                if b: im = Image.open(io.BytesIO(b)).convert('RGBA')
            elif grp == 'profile':
                b = self.app.client.image(f'/lol-game-data/assets/v1/profile-icons/{key}.jpg')
                if b: im = Image.open(io.BytesIO(b)).convert('RGBA')
        except Exception:
            im = None
        self.raw[k] = im
        return im

    def get(self, grp, key, size, gray=False):
        if Image is None or key in (None, '', 0): return None
        k = (grp, key, size, gray)
        if k in self.cache: return self.cache[k]
        im = self._pil(grp, key)
        if im is None: return None
        im = im.resize((size, size), Image.LANCZOS)
        if gray: im = ImageOps.grayscale(im).convert('RGBA')
        ph = ImageTk.PhotoImage(im)
        self.cache[k] = ph
        return ph


def tier_of(text):
    """'Изумруд IV · 17 LP' -> 'Изумруд'."""
    w = (text or '').split(' ')[0]
    return w if w in TIER_RU.values() else None


def rank_text(r):
    """Полная строка звания. У чужих игроков клиент не отдаёт поражения — тогда пишем только победы."""
    if not r: return ''
    t = TIER_RU.get(r['tier'], r['tier'])
    div = r['div'] if r['tier'] not in ('MASTER', 'GRANDMASTER', 'CHALLENGER') else ''
    n = r['w'] + r['l']
    tail = f" · {round(r['w'] / n * 100)}% из {n}" if r['l'] else (f" · {r['w']} побед" if r['w'] else '')
    return f"{t} {div} · {r['lp']} LP{tail}".replace('  ', ' ')


def rank_short(r):
    if not r: return ''
    t = TIER_RU.get(r['tier'], r['tier'])
    div = r['div'] if r['tier'] not in ('MASTER', 'GRANDMASTER', 'CHALLENGER') else ''
    return f"{t} {div}".strip() + f"\n{r['lp']} LP" + (f" · {round(r['w'] / (r['w'] + r['l']) * 100)}%" if r['l'] else '')


# ---------------- Виджеты поверх игры ----------------
# Каждый виджет — окно поверх игры с одной картинкой-карточкой (render.Card): так текст сглажен и выглядит аккуратно.

class Overlay(tk.Toplevel):
    def __init__(self, app, key, default_xy):
        super().__init__(app.root)
        self.app, self.key = app, key
        self.overrideredirect(True)
        self.attributes('-topmost', True)
        self.configure(bg=KEY, highlightthickness=0)
        self.lbl = tk.Label(self, bg=KEY, bd=0)
        self.lbl.pack()
        x, y = app.layout().get(key, default_xy)
        self.geometry(f'+{int(x)}+{int(y)}')
        self.update_idletasks()
        click_through(self, True)
        self.attributes('-alpha', app.s['alpha'] / 100)
        if IS_WIN: self.attributes('-transparentcolor', KEY)
        self._drag, self._ph, self.unlocked = None, None, False
        for w in (self, self.lbl):
            w.bind('<ButtonPress-1>', self._start); w.bind('<B1-Motion>', self._move); w.bind('<ButtonRelease-1>', self._end)

    def _start(self, e): self._drag = (e.x_root - self.winfo_x(), e.y_root - self.winfo_y())

    def _move(self, e):
        if self._drag: self.geometry(f'+{e.x_root - self._drag[0]}+{e.y_root - self._drag[1]}')

    def _end(self, e):
        if self._drag:
            self._drag = None
            self.app.layout()[self.key] = [self.winfo_x(), self.winfo_y()]
            self.app.s.save()

    def unlock(self, on):
        self.unlocked = on
        click_through(self, not on)
        self.configure(highlightthickness=2 if on else 0, highlightbackground=C['gold'])

    def card(self, accent=None, width=None):
        return render.Card(C, F['font'], self.app.s['scale'] / 100, plate=self.app.s['widget_bg'] != 'none', accent=accent, width=width)

    def put(self, card):
        if Image is None: return
        im = card.render()
        self._ph = ImageTk.PhotoImage(im)
        self.lbl.configure(image=self._ph)
        x, sw = self.winfo_x(), self.winfo_screenwidth()
        if not self._drag and x + im.width > sw: self.geometry(f'+{max(0, sw - im.width)}+{self.winfo_y()}')   # не уезжать за край экрана

    def demo(self):
        """Пример содержимого, чтобы виджет можно было расставить без игры."""
        self.put(self.card(accent='gold').row(('text', dict(WIDGETS, tabtop='Перевес команды (Tab)').get(self.key, self.key), 'fg', 12, True)).row(('text', 'зажми модификатор и тяни', 'mute', 10, False)))


class HintsOverlay(Overlay):
    def __init__(self, app, xy):
        super().__init__(app, 'hints', xy)
        self.items = []

    def push(self, text, color='fg'):
        self.items.append((time.time(), text, color)); self.items = self.items[-4:]

    def show(self, _=None):
        now = time.time()
        self.items = [i for i in self.items if now - i[0] < 14]
        if not self.items:
            if not self.unlocked: self.withdraw()
            return
        c = self.card(accent='gold', width=400)
        for i, (t, text, color) in enumerate(self.items):
            if i: c.row(('gap', 1), pad=4)
            c.text(text, color, 13, i == len(self.items) - 1, wrap_to=370)
        self.put(c)
        if not self.app.hidden and self.app.s['widgets'].get('hints'): self.deiconify()


class PerfOverlay(Overlay):
    """Показатели в игре против нормы: CS/мин, золото/мин, KDA, участие в убийствах, обзор/мин."""
    METRICS = {'csm': ('CS/мин', 1), 'gpm': ('Золото/мин', 0), 'kda': ('KDA', 1), 'kp': ('Участие, %', 0), 'vsm': ('Обзор/мин', 2)}

    def __init__(self, app, xy):
        super().__init__(app, 'perf', xy)

    def values(self, g):
        me, m = g.me, max(1, g.t / 60)
        team_k = sum(p['k'] for p in g.allies) or 1
        return {'csm': me['cs'] / m, 'gpm': (me['igold'] + g.gold) / m, 'kda': (me['k'] + me['a']) / max(1, me['d']),
                'kp': min(100, (me['k'] + me['a']) / team_k * 100), 'vsm': me['ward'] / m}

    def refs(self, g):
        cfg, me = self.app.s['perf'], g.me
        if cfg['compare'] == 'emerald':
            lo = self.app.data.lola.get(f"{me['c']}|{g.role}")
            if not lo: return {}, 'Изумруд+: нет данных по чемпиону'
            return {'csm': lo['cs'] / 28, 'gpm': lo['g'] / 28, 'kda': (lo['k'] + lo['a']) / max(.1, lo['d'])}, f"Изумруд+ на {self.app.data.cn(me['c'])}"
        n = self.app.player.norm(me['c'], g.role) if self.app.player else {}
        return n, (f"твоя норма · {n['n']} игр" if n.get('n') else 'нормы пока нет')

    def show(self, g):
        cfg = self.app.s['perf']
        vals, (ref, title) = self.values(g), self.refs(g)
        on = [k for k in self.METRICS if cfg['metrics'].get(k)]
        c = self.card(width=0)
        if cfg['layout'] == 'vertical':
            c.row(('text', title, 'mute', 10, False))
            for k in on:
                name, dec = self.METRICS[k]
                v, r = vals[k], ref.get(k)
                col = 'fg' if not r else 'good' if v >= r else 'bad' if v < r * .9 else 'fg'
                segs = [('text', f'{name}', 'mute', 11, False), ('text', f'{v:.{dec}f}', col, 13, True)]
                if r: segs += [('text', f'/ {r:.{dec}f}', 'mute', 11, False), ('bar', min(1, v / r / 1.5), col if col != 'fg' else 'gold', 'line', 70)]
                c.row(*segs)
        else:
            segs = []
            for k in on:
                name, dec = self.METRICS[k]
                v, r = vals[k], ref.get(k)
                col = 'fg' if not r else 'good' if v >= r else 'bad' if v < r * .9 else 'fg'
                segs += [('text', name, 'mute', 10, False), ('text', f'{v:.{dec}f}', col, 12, True)]
                if r: segs.append(('text', f'/{r:.{dec}f}', 'mute', 10, False))
                segs.append(('gap', 8))
            c.row(*segs)
        self.put(c)


class LaneOverlay(Overlay):
    def __init__(self, app, xy):
        super().__init__(app, 'lane', xy)

    def show(self, g):
        if not g.opp: self.put(self.card().row(('text', 'Оппонент не определён', 'mute', 11, False))); return
        d, o, me = g.lane_diff(), g.opp, g.me
        col = 'good' if d > 300 else 'bad' if d < -300 else 'fg'
        c = self.card()
        icon = self.app.pimg('champ', o['c'], 1.0, gray=o['dead'], ring=C['red'])
        segs = ([('img', icon)] if icon else []) + [('text', f"{d:+.0f}", col, 16, True), ('text', 'золота против ' + self.app.data.cn(o['c']), 'mute', 11, False)]
        c.row(*segs)
        c.row(('text', f"ур. {me['lvl']} / {o['lvl']} · CS {me['cs']} / {o['cs']} · {o['k']}/{o['d']}/{o['a']}", 'mute', 10, False))
        self.put(c)


class GoldOverlay(Overlay):
    """Разница золота по линиям (по стоимости предметов) и полоса золота команд."""
    def __init__(self, app, xy):
        super().__init__(app, 'gold', xy)

    def show(self, g):
        ours, theirs = g.team_gold(g.my_team), sum(p['igold'] for p in g.enemies)
        diff = ours - theirs
        c = self.card()
        c.row(('text', f'{ours / 1000:.1f}k', 'blue', 11, True), ('bar', ours / max(1, ours + theirs), 'blue', 'red', 150),
              ('text', f'{theirs / 1000:.1f}k', 'red', 11, True))
        c.row(('text', f'Команда {diff:+.0f}', 'good' if diff > 0 else 'bad' if diff < 0 else 'fg', 12, True))
        for r in core.ROLES:
            a = next((p for p in g.allies if p['pos'] == r), None)
            e = next((p for p in g.enemies if p['pos'] == r), None)
            if not a or not e: continue
            dd = a['igold'] - e['igold']
            ia = self.app.pimg('champ', a['c'], .75, gray=a['dead'], ring=C['gold'] if a is g.me else None)
            ie = self.app.pimg('champ', e['c'], .75, gray=e['dead'])
            segs = ([('img', ia)] if ia else []) + [('text', f'{dd:+6.0f}'.replace(' ', ' '), 'good' if dd > 300 else 'bad' if dd < -300 else 'fg', 12, True)] + ([('img', ie)] if ie else [])
            c.row(*segs, pad=3)
        self.put(c)


class ItemOverlay(Overlay):
    """Сколько золота до следующего предмета из твоей лучшей сборки."""
    def __init__(self, app, xy):
        super().__init__(app, 'item', xy)

    def show(self, g):
        plan = core.next_item_plan(self.app.data, self.app.player, g.me['c'], g.me['items'], g.gold)
        d = self.app.data
        if not plan:
            self.put(self.card().row(('text', 'Сборка готова или нет данных', 'mute', 11, False))); return
        it, cp = self.app.pimg('item', plan['item'], 1.0), self.app.pimg('item', plan['comp'], .8)
        c = self.card()
        if plan['comp_need'] == 0:
            segs = [('text', 'можно купить', 'good', 12, True)]
        else:
            segs = [('text', f"ещё {int(plan['comp_need'])}", 'gold', 16, True)]
        c.row(*(([('img', it)] if it else []) + ([('img', cp)] if cp and plan['comp'] != plan['item'] else []) + segs))
        line = d.iname(plan['comp']) if plan['comp'] == plan['item'] else f"{d.iname(plan['comp'])} → {d.iname(plan['item'])}, всего ещё {int(plan['need'])}"
        c.row(('text', line, 'mute', 10, False))
        self.put(c)


class TimersOverlay(Overlay):
    def __init__(self, app, xy):
        super().__init__(app, 'timers', xy)

    def show(self, g):
        ob, t = g.objectives(), g.t
        c = self.card()
        if g.role == 'JUNGLE' and t < core.OBJ['crab']:
            c.row(('text', 'Крабы', 'fg', 11, False), ('text', core.mmss(core.OBJ['crab'] - t), 'gold' if core.OBJ['crab'] - t <= 60 else 'fg', 11, True))
        for key, name in (('dragon', ob.get('dragon_name', 'Дракон')), ('grubs', 'Личинки'), ('herald', 'Герольд'), ('baron', 'Барон')):
            at = ob.get(key)
            if at is None: continue
            left = at - t
            c.row(('text', name, 'fg' if left > 0 else 'mute', 11, False),
                  ('text', core.mmss(left) if left > 0 else 'жив', 'gold' if 0 < left <= 60 else 'fg' if left > 0 else 'mute', 11, True))
        nc = g.next_cannon()
        if nc: c.row(('text', 'Осадный миньон', 'mute', 10, False), ('text', core.mmss(nc - t), 'mute', 10, True))
        self.put(c)


class TabGold(Overlay):
    """Поверх игровой таблицы по Tab: ±золото каждого против своего оппонента (без дублирования самой таблицы)."""
    def __init__(self, app, xy):
        super().__init__(app, 'tabgold', xy)
        self.withdraw()

    def show(self, g):
        s = self.app.s
        rows = [p for p in g.players if p['team'] == 'ORDER'] + [p for p in g.players if p['team'] != 'ORDER']
        if s['tab_swap']: rows = rows[5:] + rows[:5]
        k = s['scale'] / 100
        rh, gap = s['tab_row'], s['tab_gap']
        W, H = int(90 * k), rh * len(rows) + gap
        im = Image.new('RGBA', (max(W, 10), max(H, 10)), (0, 0, 0, 0))
        dr = render.ImageDraw.Draw(im)
        f = render.font(F['font'], max(10, int(15 * k)), True)
        for i, p in enumerate(rows):
            opp = next((e for e in g.players if e['team'] != p['team'] and e['pos'] == p['pos'] and p['pos']), None)
            if not opp: continue
            dd = p['igold'] - opp['igold']
            mine = p['team'] == g.my_team
            good = (dd > 0) == mine
            col = C['good'] if abs(dd) >= 300 and good else C['bad'] if abs(dd) >= 300 else C['fg']
            y = i * rh + (gap if i >= 5 else 0) + rh // 2
            dr.text((W - 4, y), f'{dd:+.0f}', font=f, fill=render.rgb(col) + (255,), anchor='rm', stroke_width=2, stroke_fill=(0, 0, 0, 255))
        self._ph = ImageTk.PhotoImage(im)
        self.lbl.configure(image=self._ph)

    def demo(self):
        s = self.app.s
        rh, gap = s['tab_row'], s['tab_gap']
        im = Image.new('RGBA', (int(90 * s['scale'] / 100), rh * 10 + gap), (0, 0, 0, 0))
        dr = render.ImageDraw.Draw(im)
        f = render.font(F['font'], int(15 * s['scale'] / 100), True)
        for i in range(10):
            y = i * rh + (gap if i >= 5 else 0) + rh // 2
            dr.rectangle((0, y - rh // 2 + 1, im.width - 1, y + rh // 2 - 1), outline=render.rgb(C['gold']) + (255,))
            dr.text((im.width - 4, y), f'+{(i + 1) * 100}', font=f, fill=render.rgb(C['fg']) + (255,), anchor='rm', stroke_width=2, stroke_fill=(0, 0, 0, 255))
        self._ph = ImageTk.PhotoImage(im); self.lbl.configure(image=self._ph)


class TabTop(Overlay):
    """Над игровой таблицей по Tab: общий перевес команды по золоту."""
    def __init__(self, app, xy):
        super().__init__(app, 'tabtop', xy)
        self.withdraw()

    def show(self, g):
        ours, theirs = g.team_gold(g.my_team), sum(p['igold'] for p in g.enemies)
        diff = ours - theirs
        c = self.card(accent='good' if diff > 0 else 'bad' if diff < 0 else None)
        c.row(('text', f'Перевес команды {diff:+.0f} золота', 'good' if diff > 0 else 'bad' if diff < 0 else 'fg', 14, True),
              ('bar', ours / max(1, ours + theirs), 'blue', 'red', 140))
        self.put(c)


# ---------------- Дашборд на втором мониторе ----------------
# Во время выбора чемпионов показывает драфт в реальном времени, в игре — карточки всех десяти.

def hist_lines(h, rank=None):
    """Строки характеристики игрока под портретом."""
    out = []
    if rank:
        out.append((rank_short(rank), 'gold'))
    if h:
        st = h['streak']
        out.append((f"{h['w']}–{h['n'] - h['w']} за {h['n']}", 'fg'))
        if abs(st) >= 2: out.append((f"серия {'+' if st > 0 else '−'}{abs(st)}", 'good' if st > 0 else 'bad'))
        if h['on']: out.append((f"на чемп. {h['on']} · {round(h['on_w'] / h['on'] * 100)}%", 'fg'))
        elif h['tags'] and 'не играл' in h['tags'][-1]: out.append(('новый чемп.', 'bad'))
        out.append((f"KDA {h['kda']}", 'mute'))
        if any('почти только' in t for t in h['tags']): out.append(('мейн чемпиона', 'gold'))
    return out


class Dashboard(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app.root)
        self.app = app
        self.title('LoL Helper — драфт и игра')
        self.configure(bg=C['bg'])
        lay = app.layout().get('dashboard')
        if lay: self.geometry(f'{lay[2]}x{lay[3]}+{lay[0]}+{lay[1]}')
        else:
            sig, (pw, ph), (vx, vy, vw, vh) = screens()
            x = pw + 40 if vw > pw and vx >= 0 else vx + 40 if vx < 0 else 80
            self.geometry(f'1400x860+{x}+60')
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.bind('<Configure>', self._moved)
        fn = F['font']
        self.head = tk.Label(self, bg=C['bg'], fg=C['gold'], font=(fn, app.fs(16), 'bold'), anchor='w')
        self.head.pack(fill='x', padx=14, pady=(10, 0))
        self.sub = tk.Label(self, bg=C['bg'], fg=C['mute'], font=(fn, app.fs(11)), anchor='w', justify='left')
        self.sub.pack(fill='x', padx=14)
        self.body = tk.Frame(self, bg=C['bg']); self.body.pack(fill='both', expand=True, padx=10, pady=8)
        self.logl = tk.Label(self, text='Подсказки за игру', bg=C['bg'], fg=C['mute'], font=(fn, app.fs(10)), anchor='w')
        self.log = tk.Text(self, height=5, bg=C['panel'], fg=C['fg'], relief='flat', font=(fn, app.fs(10)), wrap='word',
                           highlightthickness=1, highlightbackground=C['line'])
        self.mode, self.cards, self._save_job, self.draft_sig = None, {}, None, None
        self.idle()

    def _moved(self, e):
        if e.widget is not self: return
        if self._save_job: self.after_cancel(self._save_job)
        self._save_job = self.after(800, self._save)

    def _save(self):
        self.app.layout()['dashboard'] = [self.winfo_x(), self.winfo_y(), self.winfo_width(), self.winfo_height()]
        self.app.s.save()

    def close(self):
        self.app.s['dashboard'] = False; self.app.s.save(); self.app.dash = None; self.destroy()

    def clear(self, mode):
        if self.mode == mode: return
        self.mode = mode
        for w in self.body.winfo_children(): w.destroy()
        self.cards, self.draft_sig = {}, None
        if mode == 'game':
            self.logl.pack(fill='x', padx=14); self.log.pack(fill='x', padx=14, pady=(0, 12)); self.log.delete('1.0', 'end')
            self.cols = [tk.Frame(self.body, bg=C['bg']) for _ in range(2)]
            for i, f in enumerate(self.cols): f.grid(row=0, column=i, sticky='nsew', padx=4); self.body.columnconfigure(i, weight=1, uniform='t')
        else:
            self.logl.pack_forget(); self.log.pack_forget()

    def idle(self):
        self.clear('idle')
        self.head.configure(text='Ждём выбора чемпионов', fg=C['gold']); self.sub.configure(text='Окно само покажет драфт, а потом игру.')

    def reset(self):
        self.mode = None; self.clear('game')
        self.head.configure(text='Игра загружается', fg=C['gold']); self.sub.configure(text='')

    def add_log(self, t, text):
        if self.mode == 'game': self.log.insert('end', f'{core.mmss(t)}  {text}\n'); self.log.see('end')

    # --- драфт
    def show_draft(self, cs, r, bans):
        """cs — разбор сессии выбора, r — draft_suggest, bans — ban_suggest."""
        app, d = self.app, self.app.data
        sig = json.dumps([cs['role'], r.get('role'), cs['me'], cs['enemies'], sorted(cs['unavailable']),
                          [(a['c'], bool(a.get('rank')), bool(a.get('hist'))) for a in cs.get('allies', [])], [x['c'] for x in r['picks']]], default=str)
        self.clear('draft')
        if sig == self.draft_sig: return
        self.draft_sig = sig
        for w in self.body.winfo_children(): w.destroy()
        fn, fs = F['font'], app.fs
        role = core.ROLE_RU.get(r.get('role') or cs['role'], '')
        self.head.configure(text='Выбор чемпионов' + (f' · ты: {role}' if role else ''), fg=C['gold'])
        self.sub.configure(text=(f"Вероятный оппонент: {d.cn(r['opp'])}" if r['opp'] else 'Оппонент ещё не выбран'))
        teams = tk.Frame(self.body, bg=C['bg']); teams.pack(fill='x')
        for col, (title, color) in enumerate((('Союзники', 'blue'), ('Враги', 'red'))):
            f = tk.Frame(teams, bg=C['bg']); f.grid(row=0, column=col, sticky='nw', padx=(0, 30))
            tk.Label(f, text=title, bg=C['bg'], fg=C[color], font=(fn, fs(13), 'bold')).pack(anchor='w')
            row = tk.Frame(f, bg=C['bg']); row.pack(anchor='w', pady=4)
            people = (cs.get('allies') or []) if col == 0 else [{'c': c, 'pos': r['roles'].get(c, '')} for c in cs['enemies']]
            for p in people:
                box = tk.Frame(row, bg=C['panel'], padx=6, pady=6, highlightthickness=1,
                               highlightbackground=C['gold'] if p.get('me') else C['line'])
                box.pack(side='left', padx=3, anchor='n')
                im = app.img('champ', p['c'], 1.7) if p.get('c') else None
                tk.Label(box, image=im or '', text='' if im else '?', bg=C['panel'], fg=C['mute'], font=(fn, fs(18))).pack()
                tk.Label(box, text=core.ROLE_RU.get(p.get('pos'), '') or '—', bg=C['panel'], fg=C[color], font=(fn, fs(9), 'bold')).pack()
                for text, c in hist_lines(p.get('hist'), p.get('rank')):
                    tk.Label(box, text=text, bg=C['panel'], fg=C[c], font=(fn, fs(9))).pack()
        if bans:
            tk.Label(self.body, text='Кого банить (твои худшие оппоненты)', bg=C['bg'], fg=C['gold'], font=(fn, fs(12), 'bold')).pack(anchor='w', pady=(14, 4))
            row = tk.Frame(self.body, bg=C['bg']); row.pack(anchor='w')
            for c, n, w in bans:
                tk.Label(row, text=f'{d.cn(c)}\n{w}–{n - w}', image=app.img('champ', c, 1.2) or '', compound='top', bg=C['bg'], fg=C['bad'],
                         font=(fn, fs(9))).pack(side='left', padx=6)
        tk.Label(self.body, text='Кого взять', bg=C['bg'], fg=C['gold'], font=(fn, fs(12), 'bold')).pack(anchor='w', pady=(14, 4))
        for x in r['picks']:
            row = tk.Frame(self.body, bg=C['bg']); row.pack(anchor='w', pady=2)
            tk.Label(row, text='  ' + x['name'], image=app.img('champ', x['c'], 1.2) or '', compound='left', bg=C['bg'], fg=C['fg'],
                     font=(fn, fs(12), 'bold')).pack(side='left')
            tk.Label(row, text='   ' + x['why'], bg=C['bg'], fg=C['mute'], font=(fn, fs(10))).pack(side='left')
        me = cs.get('me')
        p = app.player
        if me and p:
            tk.Label(self.body, text=f'Ты: {d.cn(me)}', bg=C['bg'], fg=C['gold'], font=(fn, fs(12), 'bold')).pack(anchor='w', pady=(14, 4))
            ru = p.best_runes(me)
            row = tk.Frame(self.body, bg=C['bg']); row.pack(anchor='w')
            if ru:
                for i, rid in enumerate([ru['prim']] + ru['perks'][:4] + [ru['sec']] + ru['perks'][4:]):
                    im = app.img('rune', rid, 1.1 if i == 1 else .8)
                    if im: tk.Label(row, image=im, bg=C['bg']).pack(side='left', padx=1)
                tk.Label(row, text=f"  руны из {ru['n']} игр, {round(ru['w'] / ru['n'] * 100)}% побед", bg=C['bg'], fg=C['mute'], font=(fn, fs(10))).pack(side='left')
            row = tk.Frame(self.body, bg=C['bg']); row.pack(anchor='w', pady=4)
            for i, it in enumerate(p.best_build(me)):
                if i: tk.Label(row, text='›', bg=C['bg'], fg=C['mute'], font=(fn, fs(12))).pack(side='left', padx=2)
                im = app.img('item', it, 1.0)
                tk.Label(row, image=im or '', text='' if im else d.iname(it), bg=C['bg'], fg=C['fg']).pack(side='left')

    # --- игра
    def card(self, col, p):
        key = (col, p['riot'])
        if key in self.cards: return self.cards[key]
        app, fn, fs = self.app, F['font'], self.app.fs
        bg = C['panel']
        f = tk.Frame(self.cols[col], bg=bg, padx=8, pady=6, highlightthickness=1, highlightbackground=C['line'])
        f.pack(fill='x', pady=3)
        w = {'f': f}
        left = tk.Frame(f, bg=bg); left.grid(row=0, column=0, rowspan=4, padx=(0, 8), sticky='n')
        w['por'] = tk.Label(left, bg=bg, fg=C['fg'], font=(fn, fs(10), 'bold'), compound='top'); w['por'].pack()
        w['chars'] = tk.Frame(left, bg=bg); w['chars'].pack()
        sp = tk.Frame(f, bg=bg); sp.grid(row=0, column=1, rowspan=3, sticky='n', padx=(0, 8))
        w['sp'] = [tk.Label(sp, bg=bg) for _ in range(3)]
        for l in w['sp']: l.pack(pady=1)
        w['name'] = tk.Label(f, bg=bg, anchor='w', font=(fn, fs(13), 'bold')); w['name'].grid(row=0, column=2, sticky='w')
        w['line'] = tk.Label(f, bg=bg, anchor='w', fg=C['fg'], font=(fn, fs(10))); w['line'].grid(row=1, column=2, sticky='w')
        w['items'] = tk.Frame(f, bg=bg); w['items'].grid(row=2, column=2, sticky='w', pady=(3, 0))
        w['rank'] = tk.Label(f, bg=bg, fg=C['mute'], font=(fn, fs(9)), compound='top', justify='center')
        w['rank'].grid(row=0, column=3, rowspan=3, sticky='ne', padx=(8, 0))
        w['scout'] = tk.Label(f, bg=bg, fg=C['mute'], font=(fn, fs(9)), anchor='w', justify='left'); w['scout'].grid(row=3, column=1, columnspan=3, sticky='w')
        f.columnconfigure(2, weight=1)
        w['sig'] = w['csig'] = None
        self.cards[key] = w
        return w

    def show(self, g, scout, ranks, hists):
        if self.mode != 'game': self.reset()
        app, d, sh = self.app, self.app.data, self.app.s['show']
        diff = g.gold_diff()
        self.head.configure(text=f'{core.mmss(g.t)} · золото в предметах {diff:+.0f}', fg=C['good' if diff > 1000 else 'bad' if diff < -1000 else 'gold'])
        ob = g.objectives()
        tm = [f"{n}: {core.mmss(ob[k] - g.t)}" for k, n in (('dragon', ob.get('dragon_name')), ('grubs', 'Личинки'), ('herald', 'Герольд'), ('baron', 'Барон')) if k in ob and ob[k] > g.t]
        j = g.ejg
        self.sub.configure(text='   '.join(tm) + (f'   · лесник врагов: {d.cn(j["c"])}' if j else ''))
        order = {r: i for i, r in enumerate(core.ROLES)}
        for col, team in enumerate((g.allies, g.enemies)):
            for p in sorted(team, key=lambda p: order.get(p['pos'], 9)):
                w = self.card(col, p)
                w['f'].configure(highlightbackground=C['gold'] if p is g.me else C['line'])
                big = app.img('champ', p['c'], 1.6, gray=p['dead']) if sh['portraits'] else None
                w['por'].configure(image=big or '', text=f"{p['lvl']} ур.")
                rk, h = ranks.get(p['riot']), hists.get(p['riot'])
                csig = (bool(rk), json.dumps(h, default=str))
                if w['csig'] != csig:   # характеристика под портретом
                    w['csig'] = csig
                    for c in w['chars'].winfo_children(): c.destroy()
                    for text, c in hist_lines(h, rk if sh['ranks'] else None):
                        tk.Label(w['chars'], text=text, bg=C['panel'], fg=C[c], font=(F['font'], app.fs(9))).pack()
                sps = (p['spells'] if sh['spells'] else [])[:2]
                imgs = [app.img('spell', s, .6) for s in sps] + ([app.img('rune', p['keystone'], .6)] if sh['runes'] else [])
                for l, im in zip(w['sp'], imgs + [None] * 3): l.configure(image=im or '')
                dead = f"  · мёртв {core.mmss(p['respawn'])}" if p['dead'] else ''
                w['name'].configure(text=f"{d.cn(p['c'])}   {p['k']}/{p['d']}/{p['a']}{dead}", fg=C['blue'] if col == 0 else C['red'])
                w['line'].configure(text=f"{core.ROLE_RU.get(p['pos'], '')} · CS {p['cs']} ({p['cs'] / max(1, g.t / 60):.1f}/мин) · предметы {p['igold']:.0f} · обзор {p['ward']:.0f}")
                sig = tuple(p['items'])
                if w['sig'] != sig:
                    w['sig'] = sig
                    for c in w['items'].winfo_children(): c.destroy()
                    if sh['items']:
                        for i in p['items']:
                            im = app.img('item', i, .75)
                            if im: tk.Label(w['items'], image=im, bg=C['panel']).pack(side='left', padx=1)
                    else:
                        its = [d.iname(i) for i in p['items'] if d.items.get(str(i), {}).get('g', 0) >= 900]
                        tk.Label(w['items'], text=', '.join(its) or 'без крупных предметов', bg=C['panel'], fg=C['mute'],
                                 font=(F['font'], app.fs(9))).pack(side='left')
                if sh['ranks'] and rk:
                    w['rank'].configure(image=app.img('emb', TIER_RU.get(rk['tier']), 1.3) or '', text=rank_short(rk))
                else: w['rank'].configure(image='', text='')
                w['scout'].configure(text=(scout.get(p['c'], '') if col == 1 and sh['scout'] else ''))


def scout_text(p):
    """Строка разведки из data/live.json сайта (серия, игры на чемпионе, мастерство)."""
    out = []
    sc = p.get('sc') or {}
    if sc.get('r'): out.append(f"последние 10: {sc['r'][0]}–{sc['r'][1]}")
    if sc.get('st'): out.append(f"серия {'+' if sc['st'] > 0 else ''}{sc['st']}")
    if sc.get('cn'): out.append(f"на чемпионе {sc['cn'][0]} игр, {sc['cn'][1]} побед" + (f", KDA {sc['kda']}" if sc.get('kda') else ''))
    if sc.get('m'): out.append(f"мастерство {sc['m'][0]} ({sc['m'][1] // 1000}k)")
    return ' · '.join(out)


# ---------------- Итог игры ----------------

def show_postgame(app, res, result):
    w = tk.Toplevel(app.root); w.title('LoL Helper — итог игры'); w.configure(bg=C['bg'], padx=18, pady=14)
    w.attributes('-topmost', True)
    fs, fn = app.fs, F['font']
    head = {'Win': 'Победа', 'Lose': 'Поражение'}.get(result, 'Игра окончена')
    tk.Label(w, text=f"  {head} · {app.data.cn(res['me']['c'])} · {res['min']:.0f} мин", bg=C['bg'],
             fg=C['good'] if result == 'Win' else C['bad'] if result == 'Lose' else C['gold'], font=(fn, fs(16), 'bold'),
             image=app.img('champ', res['me']['c'], 1.4) or '', compound='left').pack(anchor='w', pady=(0, 8))
    for name, v, th, ok, dec in res['goals']:
        tk.Label(w, text=f"{'✓' if ok else '✗'}  {name}: {v:.{dec}f} (цель {th})", bg=C['bg'], fg=C['good' if ok else 'bad'],
                 font=(fn, fs(12))).pack(anchor='w')
    if res['main']:
        tk.Label(w, text=f"Главное на следующую игру: {res['main'].lower()}", bg=C['bg'], fg=C['fg'], font=(fn, fs(12), 'bold'),
                 wraplength=fs(460), justify='left').pack(anchor='w', pady=(10, 0))
    tk.Label(w, text=f"Подсказок за игру: {len(res['hints'])}", bg=C['bg'], fg=C['mute'], font=(fn, fs(10))).pack(anchor='w', pady=(6, 0))
    ttk.Button(w, text='Закрыть', command=w.destroy).pack(anchor='e', pady=(12, 0))


# ---------------- Приложение ----------------

class App:
    def __init__(self, data, version, updater=None):
        dpi_aware()
        self.home = app_home()
        self.s = Settings(self.home)
        self.data, self.version, self.updater = data, version, updater
        core.OBJ.update(self.s['obj'])
        self.client = lcu.LCU()
        self.voice = Voice(self.home)
        self.sync_voice()
        self.q = queue.Queue()
        self.hidden = False
        self.account = None
        self.my_rank = None
        self.ranks = {}
        self.hists = {}
        self.role_override = None
        self.player = None
        self.engine = None
        self.draft = None
        self.draft_sig = None
        self.imported = None
        self.scout = {}
        self.last_game = None
        self.result = None
        self.keys_prev = {}
        self.demo_on = False
        self.pending_data = None
        self.root = tk.Tk()
        self.root.title(f'LoL Helper {version}')
        self.root.geometry('760x680')
        self.icons = Icons(self)
        self.set_who(self.s['who'] or 'halch')
        self.build_all()
        threading.Thread(target=self.poll, daemon=True).start()
        self.root.after(300, self.drain)
        self.root.after(40, self.keys)
        self.root.after(1000, self.tick_ui)

    def build_all(self, tab=0):
        """Создать (или пересоздать после смены вида/сброса) все окна."""
        apply_theme(self.s)
        for w in self.root.winfo_children(): w.destroy()
        self.root.configure(bg=C['bg'])
        self.style()
        self.build_panel()
        try: self.nb.select(tab)
        except Exception: pass
        sig, (pw, ph), _ = screens()
        self.ov = {'hints': HintsOverlay(self, (40, int(ph * .30))), 'perf': PerfOverlay(self, (pw - 330, 80)),
                   'lane': LaneOverlay(self, (pw - 330, 300)), 'gold': GoldOverlay(self, (40, int(ph * .55))),
                   'item': ItemOverlay(self, (pw - 330, 400)), 'timers': TimersOverlay(self, (pw - 330, 490))}
        self.tab = {'tabgold': TabGold(self, (int(pw * .5 - 45), int(ph * .3))), 'tabtop': TabTop(self, (int(pw * .5 - 160), int(ph * .2)))}
        self.dash = Dashboard(self) if self.s['dashboard'] else None
        self.draft_sig = None
        if self.draft: self.on_draft(self.draft)
        self.apply_visibility()

    def rebuild(self):
        tab = self.nb.index('current') if hasattr(self, 'nb') else 0
        self.build_all(tab)

    # --- общее
    def fs(self, n): return max(7, round(n * self.s['scale'] / 100))

    def img(self, grp, key, k=1.0, gray=False):
        return self.icons.get(grp, key, max(12, int(self.s['icon'] * k)), gray)

    def pimg(self, grp, key, k=1.0, gray=False, ring=None):
        """Иконка для карточек виджетов (PIL), скруглённая, с рамкой по желанию."""
        if Image is None or key in (None, '', 0): return None
        im = self.icons._pil(grp, key)
        return render.rounded_icon(im, max(12, int(self.s['icon'] * k * self.s['scale'] / 100)), gray=gray, ring=ring) if im else None

    def layout(self):
        return self.s['layout'].setdefault(screens()[0], {})

    def sync_voice(self):
        v, s = self.voice, self.s
        v.voice, v.volume, v.rate, v.master, v.beep_volume = s['voice'], s['volume'], s['rate'], s['master'], s['beep_volume']
        v.sound = s['sound']
        v.warm()

    def style(self):
        st = ttk.Style(self.root)
        try: st.theme_use('clam')
        except Exception: pass
        fn = F['font']
        st.configure('.', background=C['bg'], foreground=C['fg'], fieldbackground=C['panel'], font=(fn, self.fs(10)),
                     bordercolor=C['line'], lightcolor=C['panel'], darkcolor=C['panel'], troughcolor=C['panel'], focuscolor=C['gold'])
        st.configure('TNotebook', background=C['bg'], borderwidth=0)
        st.configure('TNotebook.Tab', background=C['panel'], foreground=C['mute'], padding=(12, 5), bordercolor=C['line'])
        st.map('TNotebook.Tab', background=[('selected', C['line'])], foreground=[('selected', C['gold'])])
        st.configure('TButton', background=C['line'], foreground=C['fg'], padding=(10, 4), bordercolor=C['line'])
        st.map('TButton', background=[('active', C['gold'])], foreground=[('active', C['bg'])])
        st.configure('A.TButton', background=C['gold'], foreground=C['bg'])
        st.map('A.TButton', background=[('active', C['fg'])])
        st.configure('TCheckbutton', background=C['bg'], foreground=C['fg'], indicatorbackground=C['panel'], indicatorforeground=C['gold'])
        st.map('TCheckbutton', background=[('active', C['bg'])], indicatorbackground=[('selected', C['gold'])], indicatorforeground=[('selected', C['bg'])])
        st.configure('TRadiobutton', background=C['bg'], foreground=C['fg'], indicatorbackground=C['panel'])
        st.map('TRadiobutton', background=[('active', C['bg'])], indicatorbackground=[('selected', C['gold'])])
        st.configure('TCombobox', fieldbackground=C['panel'], background=C['line'], foreground=C['fg'], arrowcolor=C['gold'])
        st.map('TCombobox', fieldbackground=[('readonly', C['panel'])], foreground=[('readonly', C['fg'])],
               selectbackground=[('readonly', C['panel'])], selectforeground=[('readonly', C['fg'])])
        self.root.option_add('*TCombobox*Listbox.background', C['panel'])
        self.root.option_add('*TCombobox*Listbox.foreground', C['fg'])
        self.root.option_add('*TCombobox*Listbox.selectBackground', C['gold'])
        st.configure('TEntry', fieldbackground=C['panel'], foreground=C['fg'], insertcolor=C['fg'])
        st.configure('Horizontal.TScale', background=C['gold'], troughcolor=C['line'], bordercolor=C['line'], lightcolor=C['gold'], darkcolor=C['gold'])
        st.configure('Vertical.TScrollbar', background=C['line'], troughcolor=C['bg'], arrowcolor=C['mute'], bordercolor=C['bg'])
        st.configure('H.TLabel', foreground=C['gold'], font=(fn, self.fs(12), 'bold'))
        st.configure('M.TLabel', foreground=C['mute'])
        st.configure('V.TLabel', foreground=C['gold'])

    def set_who(self, who):
        if who not in self.data.d['players']: who = None
        self.player = core.Player(self.data, who) if who else None
        self.who = who
        self.engine = None

    def new_engine(self):
        self.engine = core.Engine(self.data, self.player, enabled=self.hint_flags(''))

    def hint_mode(self, hid, role=None):
        """Режим подсказки: общие — один на все роли, ролевые — свой у каждой роли."""
        if hid not in core.HINT_ROLES: return self.s['hints'].get(hid, 'off')
        role = role or self.s['hint_preset']
        if role not in core.HINT_ROLES[hid]: return 'off'
        dflt = next(h[3] for h in core.HINTS if h[0] == hid)
        return self.s['hints_role'].get(role, {}).get(hid, dflt)

    def hint_flags(self, role):
        return {h: self.hint_mode(h, role) != 'off' for h in core.HINT_IDS}

    def apply_visibility(self):
        for k, w in self.ov.items():
            if k == 'hints': continue
            if self.hidden or not self.s['widgets'].get(k) or not self.last_game: w.withdraw()
            else: w.deiconify()
        if self.hidden: self.ov['hints'].withdraw()

    def toast(self, text, color='gold'):
        self.ov['hints'].push(text, color); self.ov['hints'].show()

    # --- фоновый опрос клиента и игры
    def poll(self):
        last_lcu, last_me, last_scout, in_game = 0, 0, 0, False
        while True:
            try:
                raw = lcu.live_data()
                now = time.time()
                if raw and (raw.get('gameData') or {}).get('gameTime', 0) > 0:
                    if not in_game: self.ranks, self.hists = {}, {}
                    in_game = True
                    g = core.Game(raw, self.data)
                    if self.engine is None: self.new_engine()
                    self.engine.enabled = self.hint_flags(g.role)
                    hints = self.engine.tick(g)
                    res = next((e.get('Result') for e in g.events if e.get('EventName') == 'GameEnd'), None)
                    if now - last_scout > 90:
                        last_scout = now
                        self.scout = self.fetch_scout(g)
                    if len(self.ranks) < len(g.players): self.fetch_people(g)
                    self.q.put(('game', g, hints, res))
                else:
                    if in_game:
                        in_game = False
                        self.q.put(('end', None, None, None))
                    if now - last_me > 60:
                        last_me = now
                        me = self.client.me()
                        if me:
                            me['rank'] = self.client.rank()
                            self.q.put(('me', me, None, None))
                    if now - last_lcu > 2:
                        last_lcu = now
                        if self.client.phase() == 'ChampSelect':
                            sess = self.client.champ_select()
                            if sess:
                                cs = core.parse_champ_select(sess, self.data)
                                cs['allies'] = self.draft_allies(sess)
                                self.q.put(('draft', cs, None, None))
                        elif self.draft is not None:
                            self.q.put(('draft', None, None, None))
            except Exception as e:
                self.q.put(('error', str(e), None, None))
            time.sleep(1)

    def cid(self, key):
        return next((i for i, c in self.data.ids.items() if c == key), None)

    def fetch_people(self, g):
        """Звание и история последних игр каждого из десяти через клиент (как в профиле). По одному за проход."""
        for p in g.players:
            if p['riot'] in self.ranks: continue
            pu = self.client.puuid(p['riot'])
            self.ranks[p['riot']] = self.client.rank(pu) if pu else None
            self.hists[p['riot']] = core.summarize_history(self.client.history(pu), self.cid(p['c'])) if pu else None
            return

    def draft_allies(self, sess):
        """Союзники в драфте: чемпион (или наведённый), роль, звание и история игр."""
        self.__dict__.setdefault('hraw', {})
        out = []
        for p in sess.get('myTeam') or []:
            pu = p.get('puuid')
            if pu and pu not in self.hraw:
                self.ranks[pu] = self.client.rank(pu)
                self.hraw[pu] = self.client.history(pu)
            champ_id = p.get('championId') or p.get('championPickIntent') or 0
            out.append({'c': self.data.ids.get(str(champ_id)), 'pos': core.LCU_ROLE.get((p.get('assignedPosition') or '').lower(), ''),
                        'rank': self.ranks.get(pu), 'hist': core.summarize_history(self.hraw.get(pu), champ_id) if pu else None,
                        'me': p.get('cellId') == sess.get('localPlayerCellId')})
        return out

    def fetch_scout(self, g):
        try:
            with urllib.request.urlopen(RAW + 'data/live.json', timeout=8) as r:
                live = json.load(r)
        except Exception:
            return self.scout
        mine = {p['c'] for p in g.players}
        for gm in live.get('games', []):
            if {p['c'] for p in gm['players']} == mine:
                return {p['c']: scout_text(p) for p in gm['players']}
        return self.scout

    # --- обработка в потоке интерфейса
    def drain(self):
        try:
            while True:
                kind, a, b, c = self.q.get_nowait()
                if kind == 'game': self.on_game(a, b, c)
                elif kind == 'end': self.on_end()
                elif kind == 'me': self.on_me(a)
                elif kind == 'draft': self.on_draft(a)
                elif kind == 'error': self.status.configure(text=f'Ошибка: {a}')
        except queue.Empty:
            pass
        self.root.after(300, self.drain)

    def on_me(self, me):
        self.account, self.my_rank = me, me.get('rank')
        who = self.data.who_by_riot(me['riot'])
        if who and who != self.who:
            self.s['who'] = who; self.s.save(); self.set_who(who)
        self.panel_sync()

    def on_game(self, g, hints, result):
        first = self.last_game is None
        self.last_game, self.result = g, result or self.result
        if first:
            if not self.account:
                who = self.data.who_by_riot(g.my_riot)
                if who and who != self.who: self.set_who(who); self.new_engine()
            self.apply_visibility()
            if self.dash: self.dash.reset()
        for h in hints:
            mode = self.hint_mode(h.id, g.role)
            if mode == 'off': continue
            self.ov['hints'].push(h.text)
            if self.dash: self.dash.add_log(g.t, h.text)
            if mode == 'beep': self.voice.beep()
            elif mode == 'voice': self.voice.say(h.say)
        if hints: self.ov['hints'].show()
        for k in ('perf', 'lane', 'gold', 'item', 'timers'):
            if not self.s['widgets'].get(k): continue
            try: self.ov[k].show(g)
            except Exception as e: print('widget', k, e)
        if self.dash:
            try: self.dash.show(g, self.scout, self.ranks, self.hists)
            except Exception as e: print('dash', e)
        self.status.configure(text=f'Игра: {core.mmss(g.t)} · {self.data.cn(g.me["c"]) if g.me else ""}')

    def on_end(self):
        g = self.last_game
        if g and self.engine and self.s['postgame'] and g.t > 300 and self.hint_mode('postgame') != 'off':
            res = core.postgame(self.engine, g, self.player)
            if res: show_postgame(self, res, self.result)
        self.last_game, self.result, self.engine, self.scout = None, None, None, {}
        if self.pending_data: self.reload_data(self.pending_data)
        self.apply_visibility()
        for w in self.tab.values(): w.withdraw()
        if self.dash: self.dash.idle()
        self.status.configure(text='Игра закончилась')

    # ---------------- Драфт ----------------
    def on_draft(self, cs):
        self.draft = cs
        box = self.draft_box
        if cs is None:
            self.role_override = None
            if self.dash and self.draft_sig not in (None, 'none'): self.dash.idle()
            if self.draft_sig != 'none':
                self.draft_sig = 'none'
                for w in box.winfo_children(): w.destroy()
                self.dl(box, 'Драфт появится, когда начнётся выбор чемпионов', 'mute').pack(anchor='w')
            self.imported = None; return
        if not getattr(self, '_draft_shown', False):
            self.nb.select(self.tab_draft.outer); self._draft_shown = True
        sig = json.dumps([cs['role'], self.role_override, cs['me'], cs['enemies'], sorted(cs['unavailable']), [(a['c'], bool(a['rank']), bool(a.get('hist'))) for a in cs.get('allies', [])]], default=str)
        if sig == self.draft_sig: return
        self.draft_sig = sig
        for w in box.winfo_children(): w.destroy()
        p, d = self.player, self.data
        if not p:
            self.dl(box, 'Аккаунта нет в статистике сайта: выбери игрока на вкладке «Статус»', 'mute').pack(anchor='w'); return
        role, how = self.draft_role(cs)
        r = core.draft_suggest(p, role, cs['enemies'], cs['unavailable'])
        r['role'] = role
        for a in cs.get('allies') or []:
            if a.get('me') and (not a.get('pos') or a.get('auto')): a['pos'], a['auto'] = role, True
        bans = core.ban_suggest(p, cs['unavailable'])
        if self.dash:
            try: self.dash.show_draft(cs, r, bans)
            except Exception as e: print('dash draft', e)
        self.dl(box, f'Роль: {core.ROLE_RU[role]} ({how})' + (f' · вероятный оппонент: {d.cn(r["opp"])}' if r['opp'] else ''), 'gold', 12, True).pack(anchor='w')
        row = tk.Frame(box, bg=C['bg']); row.pack(anchor='w', pady=(2, 0))
        self.dl(row, 'Сменить линию: ', 'mute', 10).pack(side='left')
        for rr in core.ROLES:
            ttk.Button(row, text=core.ROLE_RU[rr], width=8, style='A.TButton' if rr == role else 'TButton',
                       command=lambda rr=rr: self.set_draft_role(rr)).pack(side='left', padx=1)
        self.section(box, 'Кого взять')
        for x in r['picks']:
            row = tk.Frame(box, bg=C['bg']); row.pack(anchor='w', fill='x', pady=1)
            self.dl(row, '  ' + x['name'], 'fg', 11, True, img=self.img('champ', x['c'])).pack(side='left')
            self.dl(row, '  ' + x['why'], 'mute', 10).pack(side='left')
        if bans:
            self.section(box, 'Кого банить (твои худшие оппоненты на линии)')
            row = tk.Frame(box, bg=C['bg']); row.pack(anchor='w')
            for c, n, w in bans:
                self.dl(row, f'{d.cn(c)}\n{w}–{n - w}', 'bad', 9, img=self.img('champ', c), compound='top').pack(side='left', padx=6)
        allies = cs.get('allies') or []
        if allies or cs['enemies']:
            self.section(box, 'Команды')
            row = tk.Frame(box, bg=C['bg']); row.pack(anchor='w')
            for a in allies:
                t = core.ROLE_RU.get(a['pos'], '') + ('\n' + rank_text(a['rank']).split(' · ')[0] if a['rank'] and self.s['show']['ranks'] else '')
                self.dl(row, t, 'gold' if a['me'] else 'blue', 9, img=self.img('champ', a['c']) if a['c'] else None, compound='top').pack(side='left', padx=4)
            if cs['enemies']:
                self.dl(row, '  против  ', 'mute', 10).pack(side='left')
                for c in cs['enemies']:
                    self.dl(row, core.ROLE_RU.get(r['roles'].get(c, ''), '?'), 'red', 9, img=self.img('champ', c), compound='top').pack(side='left', padx=4)
        me = cs['me']
        if me:
            self.section(box, f'Ты: {d.cn(me)}')
            if r['opp']:
                v = p.vs(me, r['opp'])
                self.dl(box, f'Против {d.cn(r["opp"])}: ' + (f'{v["w"]}–{v["n"] - v["w"]}' if v['n'] else 'ещё не встречались'), 'fg', 10).pack(anchor='w')
            ru = p.best_runes(me)
            if ru:
                row = tk.Frame(box, bg=C['bg']); row.pack(anchor='w', pady=2)
                for i, rid in enumerate([ru['prim']] + ru['perks'][:4] + [ru['sec']] + ru['perks'][4:]):
                    im = self.img('rune', rid, 1.0 if i == 1 else .7)
                    if im: tk.Label(row, image=im, bg=C['bg']).pack(side='left', padx=1)
                self.dl(row, f"  из {ru['n']} игр, {round(ru['w'] / ru['n'] * 100)}% побед", 'mute', 10).pack(side='left')
            b = p.best_build(me)
            if b:
                row = tk.Frame(box, bg=C['bg']); row.pack(anchor='w', pady=2)
                for i, it in enumerate(b):
                    if i: self.dl(row, '›', 'mute', 12).pack(side='left', padx=2)
                    im = self.img('item', it, .9)
                    self.dl(row, '' if im else d.iname(it), 'fg', 9, img=im).pack(side='left')
            if self.s['auto_import'] and cs['locked'] and self.imported != me: self.do_import()

    def draft_role(self, cs):
        """Линия для подсказок: выбранная вручную, назначенная клиентом или основная линия игрока."""
        if self.role_override: return self.role_override, 'выбрана вручную'
        if cs['role']: return cs['role'], 'назначена клиентом'
        if cs['me'] and self.player:
            on = {r: len(self.player.on(cs['me'], r)) for r in core.ROLES}
            if max(on.values()) >= 3: return max(on, key=on.get), f'твоя линия на {self.data.cn(cs["me"])}'
        if self.player:
            cnt = {r: len(self.player.on(pos=r)) for r in core.ROLES}
            if max(cnt.values()): return max(cnt, key=cnt.get), 'твоя основная'
        return 'TOP', 'по умолчанию'

    def set_draft_role(self, role):
        self.role_override = role
        self.draft_sig = None
        if self.dash: self.dash.draft_sig = None
        if self.draft: self.on_draft(self.draft)

    def dl(self, parent, text, color='fg', size=11, bold=False, img=None, compound='left'):
        return tk.Label(parent, text=text, bg=C['bg'], fg=C[color], font=(F['font'], self.fs(size), 'bold' if bold else 'normal'),
                        image=img or '', compound=compound, justify='left', anchor='w')

    def section(self, parent, text):
        self.dl(parent, text, 'gold', 11, True).pack(anchor='w', pady=(10, 3))

    def do_import(self):
        cs, p = self.draft, self.player
        if not cs or not cs['me'] or not p:
            self.import_msg.configure(text='Сначала выбери чемпиона'); return
        me = cs['me']
        ru = p.best_runes(me)
        ok_r = ru and self.client.set_runes(self.data.cn(me), ru['prim'], ru['sec'], ru['perks'])
        acc = self.account or self.client.me() or {}
        cid = next((k for k, v in self.data.ids.items() if v == me), None)
        b = p.best_build(me)
        ok_i = bool(acc.get('id') and cid and b and self.client.set_items(acc['id'], cid, self.data.cn(me), [('Сборка из твоих побед', b), ('Тотемы', [2055, 3340, 3364])]))
        self.imported = me
        self.import_msg.configure(text=f"Руны: {'готово' if ok_r else 'не получилось'} · предметы: {'готово' if ok_i else 'не получилось'}")

    # --- клавиши и Tab
    def keys(self):
        k = self.s['keys']
        for name in ('mute', 'hide'):
            down = combo_down(k.get(name))
            if down and not self.keys_prev.get(name):
                if name == 'mute':
                    self.voice.muted = not self.voice.muted
                    self.toast('Звук выключен' if self.voice.muted else 'Звук включён')
                else:
                    self.hidden = not self.hidden; self.apply_visibility()
            self.keys_prev[name] = down
        drag = combo_down(k.get('drag')) or self.demo_on
        if drag != self.keys_prev.get('drag'):
            self.set_unlocked(drag)
            self.keys_prev['drag'] = drag
        if drag: return self.root.after(40, self.keys)
        tab = self.s['scoreboard'] and self.last_game and not self.hidden and combo_down(k.get('scoreboard')) and game_focused()
        if tab:
            if not self.keys_prev.get('tab') or time.time() - self.keys_prev.get('tab_t', 0) > 1:
                for w in self.tab.values():
                    try: w.show(self.last_game); w.deiconify()
                    except Exception as e: print('tab', e)
                self.keys_prev['tab_t'] = time.time()
        elif self.keys_prev.get('tab'):
            for w in self.tab.values(): w.withdraw()
        self.keys_prev['tab'] = bool(tab)
        self.root.after(40, self.keys)

    def set_unlocked(self, on):
        """Режим расстановки: все виджеты видны, ловят мышь; без игры показывают пример содержимого."""
        wins = dict(self.ov, **(self.tab if self.s['scoreboard'] else {}))
        for key, w in wins.items():
            w.unlock(on)
            if not on: continue
            if key in self.ov and not self.s['widgets'].get(key): continue
            try:
                if self.last_game and key != 'hints': w.show(self.last_game)
                else: w.demo()
            except Exception: w.demo()
            w.deiconify(); w.lift()
        if not on:
            for w in self.tab.values(): w.withdraw()
            self.apply_visibility(); self.ov['hints'].show()

    def toggle_demo(self):
        self.demo_on = not self.demo_on
        self.demo_btn.configure(text='Готово, закрепить виджеты' if self.demo_on else 'Показать все виджеты для расстановки')

    def tick_ui(self):
        self.ov['hints'].show()
        self.root.after(1000, self.tick_ui)

    # ---------------- Панель управления ----------------
    def build_panel(self):
        r = self.root
        top = tk.Frame(r, bg=C['bg']); top.pack(fill='x', padx=12, pady=(10, 4))
        tk.Label(top, text='LoL Helper', bg=C['bg'], fg=C['gold'], font=(F['font'], self.fs(16), 'bold')).pack(side='left')
        self.status = tk.Label(top, text='Ищу клиент League of Legends…', bg=C['bg'], fg=C['mute'], font=(F['font'], self.fs(10)))
        self.status.pack(side='right')
        self.banner = tk.Frame(r, bg=C['gold'], padx=12, pady=6)
        self.banner_lbl = tk.Label(self.banner, bg=C['gold'], fg=C['bg'], font=(F['font'], self.fs(11), 'bold'), anchor='w')
        self.banner_lbl.pack(side='left', fill='x', expand=True)
        self.banner_btn = tk.Button(self.banner, bg=C['bg'], fg=C['gold'], activebackground=C['panel'], activeforeground=C['gold'],
                                    relief='flat', font=(F['font'], self.fs(10), 'bold'), padx=12, cursor='hand2')
        self.nb = ttk.Notebook(r); self.nb.pack(fill='both', expand=True, padx=8, pady=8)
        self.tab_status = self.page('Статус'); self.tab_draft = self.page('Драфт')
        self.tab_hints = self.page('Подсказки'); self.tab_win = self.page('Окна'); self.tab_look = self.page('Вид')
        self.tab_voice = self.page('Звук'); self.tab_keys = self.page('Клавиши')
        self.tab_time = self.page('Таймеры'); self.tab_upd = self.page('Обновления')
        self.build_status(); self.build_draft(); self.build_hints(); self.build_windows(); self.build_look()
        self.build_voice(); self.build_keys(); self.build_timers(); self.build_updates()
        if getattr(self, 'upd', None): self.update_state(*self.upd)

    def page(self, name, scroll=True):
        """Вкладка панели; с прокруткой колесом мыши, если содержимое не помещается."""
        outer = tk.Frame(self.nb, bg=C['bg'], padx=14, pady=10); self.nb.add(outer, text=name)
        if not scroll: outer.outer = outer; return outer
        cv = tk.Canvas(outer, bg=C['bg'], highlightthickness=0); sb = ttk.Scrollbar(outer, orient='vertical', command=cv.yview)
        inner = tk.Frame(cv, bg=C['bg'])
        inner.bind('<Configure>', lambda e: (cv.configure(scrollregion=cv.bbox('all')),
                                             sb.pack(side='right', fill='y') if inner.winfo_reqheight() > cv.winfo_height() else sb.pack_forget()))
        win = cv.create_window((0, 0), window=inner, anchor='nw'); cv.configure(yscrollcommand=sb.set)
        cv.bind('<Configure>', lambda e: cv.itemconfigure(win, width=e.width))
        cv.pack(side='left', fill='both', expand=True)
        self.__dict__.setdefault('canvases', {})[str(outer)] = cv
        if not getattr(self, '_wheel', False):
            self._wheel = True
            def wheel(e):
                c = self.canvases.get(self.nb.select())
                if c and c.winfo_exists() and c.bbox('all') and c.bbox('all')[3] > c.winfo_height(): c.yview_scroll(-e.delta // 120, 'units')
            self.root.bind_all('<MouseWheel>', wheel)
        inner.outer = outer
        return inner

    def h(self, parent, text): ttk.Label(parent, text=text, style='H.TLabel').pack(anchor='w', pady=(8, 4))

    def note(self, parent, text): ttk.Label(parent, text=text, style='M.TLabel', wraplength=self.fs(660), justify='left').pack(anchor='w')

    def reset_btn(self, parent, section, label='По умолчанию'):
        """Кнопка сброса раздела настроек к значениям по умолчанию."""
        def go():
            self.s.reset(SECTIONS[section])
            if section == 'voice': self.sync_voice()
            if section == 'obj': core.OBJ.update(self.s['obj'])
            self.rebuild()
            self.status.configure(text='Настройки раздела сброшены')
        ttk.Button(parent, text=label, command=go).pack(anchor='w', pady=(12, 0))

    def build_status(self):
        f = self.tab_status
        self.h(f, 'Аккаунт')
        self.acc_card = tk.Frame(f, bg=C['panel'], padx=12, pady=10, highlightthickness=1, highlightbackground=C['line'])
        self.acc_card.pack(anchor='w', fill='x')
        self.acc_icon = tk.Label(self.acc_card, bg=C['panel']); self.acc_icon.pack(side='left', padx=(0, 12))
        mid = tk.Frame(self.acc_card, bg=C['panel']); mid.pack(side='left', fill='x', expand=True)
        self.acc_lbl = tk.Label(mid, bg=C['panel'], fg=C['fg'], font=(F['font'], self.fs(14), 'bold'), anchor='w'); self.acc_lbl.pack(anchor='w')
        self.acc_sub = tk.Label(mid, bg=C['panel'], fg=C['mute'], font=(F['font'], self.fs(10)), anchor='w', justify='left'); self.acc_sub.pack(anchor='w')
        self.acc_emb = tk.Label(self.acc_card, bg=C['panel'], fg=C['gold'], font=(F['font'], self.fs(10), 'bold'), compound='top')
        self.acc_emb.pack(side='right')
        row = tk.Frame(f, bg=C['bg']); row.pack(anchor='w', pady=8)
        ttk.Label(row, text='Статистика игрока: ').pack(side='left')
        self.who_var = tk.StringVar()
        names = {w: p['riot'] for w, p in self.data.d['players'].items()}
        cb = ttk.Combobox(row, state='readonly', width=24, values=list(names.values()), textvariable=self.who_var); cb.pack(side='left')
        def pick(_):
            who = next(w for w, n in names.items() if n == self.who_var.get())
            self.s['who'] = who; self.s.save(); self.set_who(who); self.panel_sync()
        cb.bind('<<ComboboxSelected>>', pick)
        self.note(f, 'Определяется сам по аккаунту, вошедшему в клиент. Меняй вручную, только если определилось неверно.')
        self.h(f, 'Данные')
        self.data_lbl = ttk.Label(f, text=''); self.data_lbl.pack(anchor='w')
        self.h(f, 'Окна')
        row = tk.Frame(f, bg=C['bg']); row.pack(anchor='w')
        ttk.Button(row, text='Открыть дашборд', command=self.open_dash).pack(side='left', padx=(0, 8))
        ttk.Button(row, text='Скрыть / показать виджеты', command=lambda: (setattr(self, 'hidden', not self.hidden), self.apply_visibility())).pack(side='left')
        self.panel_sync()

    def panel_sync(self):
        a, d = self.account, self.data
        if self.who: self.who_var.set(d.d['players'][self.who]['riot'])
        pl = d.d['players'].get(self.who or '', {})
        if a:
            self.acc_lbl.configure(text=a['riot'])
            self.acc_sub.configure(text=f"уровень {a.get('level') or '?'} · вошёл в клиент")
            self.acc_icon.configure(image=self.img('profile', a.get('icon'), 2) or '')
        else:
            self.acc_lbl.configure(text=pl.get('riot', 'Клиент не найден'))
            self.acc_sub.configure(text='Клиент не найден: запусти League of Legends')
            self.acc_icon.configure(image='')
        if self.my_rank:
            self.acc_emb.configure(image=self.img('emb', TIER_RU.get(self.my_rank['tier']), 2.2) if self.s['show']['ranks'] else '',
                                   text=rank_text(self.my_rank).replace(' · ', '\n', 1))
        elif pl.get('rank'):
            self.acc_emb.configure(image=self.img('emb', tier_of(pl['rank']), 2.2) if self.s['show']['ranks'] else '',
                                   text=pl['rank'].replace(' · ', '\n', 1))
        g = sum(len(p['g']) for p in d.d['players'].values())
        self.data_lbl.configure(text=f"Статистика от {d.d['t']} · патч {d.d['patch']} · {g} игр")

    def open_dash(self):
        if not self.dash:
            self.s['dashboard'] = True; self.s.save(); self.dash = Dashboard(self)
        else: self.dash.deiconify(); self.dash.lift()

    def build_draft(self):
        f = self.tab_draft
        self.draft_box = tk.Frame(f, bg=C['bg']); self.draft_box.pack(fill='both', expand=True, anchor='nw')
        self.dl(self.draft_box, 'Драфт появится, когда начнётся выбор чемпионов', 'mute').pack(anchor='w')
        row = tk.Frame(f, bg=C['bg']); row.pack(fill='x', pady=6)
        ttk.Button(row, text='Импортировать руны и сборку в клиент', style='A.TButton', command=self.do_import).pack(side='left')
        self.auto_var = tk.BooleanVar(value=self.s['auto_import'])
        ttk.Checkbutton(row, text='сам после выбора', variable=self.auto_var,
                        command=lambda: (self.s.__setitem__('auto_import', self.auto_var.get()), self.s.save())).pack(side='left', padx=10)
        self.import_msg = ttk.Label(f, text='', style='M.TLabel'); self.import_msg.pack(anchor='w')
        self.note(f, 'Руны берутся из твоих игр на этом чемпионе с лучшим винрейтом (от 3 игр), сборка — частые первые предметы и лучшие в итоге. '
                     'Создаётся страница «LoL Helper: …» и набор в магазине.')

    def build_hints(self):
        inner = self.tab_hints
        row = tk.Frame(inner, bg=C['bg']); row.pack(fill='x', pady=(0, 6))
        ttk.Label(row, text='Все сразу: ').pack(side='left')
        self.hint_vars = {}
        for m, lab in MODES.items():
            ttk.Button(row, text=lab, command=lambda m=m: self.set_all_hints(m)).pack(side='left', padx=2)
        row = tk.Frame(inner, bg=C['bg']); row.pack(fill='x', pady=(0, 4))
        ttk.Button(row, text='Режимы по умолчанию', command=lambda: (self.s.reset(SECTIONS['hints']), self.rebuild())).pack(side='left')
        ttk.Label(row, text='  ▶ — проверить, как прозвучит подсказка с текущим режимом', style='M.TLabel').pack(side='left')
        pr = self.s['hint_preset']
        row = tk.Frame(inner, bg=C['bg']); row.pack(fill='x', pady=(8, 0))
        ttk.Label(row, text='Роль: ', style='H.TLabel').pack(side='left')
        for rr in core.ROLES:
            ttk.Button(row, text=core.ROLE_RU[rr], width=8, style='A.TButton' if rr == pr else 'TButton',
                       command=lambda rr=rr: self.set_preset(rr)).pack(side='left', padx=1)
        self.note(inner, 'Общие подсказки одинаковы для всех ролей. Подсказки роли настраиваются отдельно для каждой, '
                         'в игре включается набор той роли, на которой ты стоишь.')
        groups = [(f'Только для роли «{core.ROLE_RU[pr]}»', [h for h in core.HINTS if h[0] in core.HINT_ROLES and pr in core.HINT_ROLES[h[0]]])]
        sec = None
        for h in core.HINTS:
            if h[0] in core.HINT_ROLES: continue
            if h[1] != sec: sec = h[1]; groups.append((f'Общие: {sec.lower()}', []))
            groups[-1][1].append(h)
        for title, hs in groups:
            ttk.Label(inner, text=title, style='H.TLabel').pack(anchor='w', pady=(8, 2))
            for hid, _, name, _, _ in hs: self.hint_row(inner, hid, name)

    def hint_row(self, inner, hid, name):
        if True:
            r = tk.Frame(inner, bg=C['bg']); r.pack(fill='x', pady=1)
            v = tk.StringVar(value=MODES[self.hint_mode(hid)]); self.hint_vars[hid] = v
            cb = ttk.Combobox(r, state='readonly', width=8, values=list(MODES.values()), textvariable=v); cb.pack(side='left')
            cb.bind('<<ComboboxSelected>>', lambda e, hid=hid: self.set_hint(hid))
            ttk.Button(r, text='▶', width=3, command=lambda hid=hid, name=name: self.test_hint(hid, name)).pack(side='left', padx=(4, 0))
            ttk.Label(r, text=name, wraplength=self.fs(520)).pack(side='left', padx=8)

    def test_hint(self, hid, name):
        """Проверка подсказки: звучит так, как настроено (сигнал, голос или только текст)."""
        mode = self.hint_mode(hid)
        if mode == 'off': self.status.configure(text='Эта подсказка выключена'); return
        self.toast(name); self.status.configure(text=f'Проверка: {MODES[mode].lower()}')
        if mode == 'beep': self.voice.beep(force=True)
        elif mode == 'voice': self.voice.say(name, force=True)

    def set_hint(self, hid):
        m = next(k for k, v in MODES.items() if v == self.hint_vars[hid].get())
        if hid in core.HINT_ROLES: self.s['hints_role'].setdefault(self.s['hint_preset'], {})[hid] = m
        else: self.s['hints'][hid] = m
        self.s.save()

    def set_preset(self, role):
        self.s['hint_preset'] = role; self.s.save(); self.rebuild()

    def set_all_hints(self, m):
        for hid, v in self.hint_vars.items(): v.set(MODES[m]); self.set_hint(hid)

    def build_windows(self):
        f = self.tab_win
        self.h(f, 'Виджеты поверх игры')
        self.note(f, f"Клики проходят сквозь виджеты в игру. Чтобы передвинуть, зажми {self.s['keys']['drag'].upper()} и тяни мышью. "
                     'Позиции запоминаются отдельно для каждого набора мониторов.')
        self.w_vars = {}
        for k, name in WIDGETS.items():
            v = tk.BooleanVar(value=self.s['widgets'].get(k, True)); self.w_vars[k] = v
            ttk.Checkbutton(f, text=name, variable=v, command=lambda k=k: self.toggle_widget(k)).pack(anchor='w')
        for key, name in (('scoreboard', 'Золото против оппонента поверх игровой таблицы (Tab)'), ('postgame', 'Окно итога после игры')):
            v = tk.BooleanVar(value=self.s[key])
            ttk.Checkbutton(f, text=name, variable=v, command=lambda key=key, v=v: (self.s.__setitem__(key, v.get()), self.s.save())).pack(anchor='w')
        self.demo_btn = ttk.Button(f, text='Показать все виджеты для расстановки', style='A.TButton', command=self.toggle_demo)
        self.demo_btn.pack(anchor='w', pady=6)
        self.h(f, 'Показатели в игре')
        pf = self.s['perf']
        row = tk.Frame(f, bg=C['bg']); row.pack(anchor='w')
        for k, (name, _) in PerfOverlay.METRICS.items():
            v = tk.BooleanVar(value=pf['metrics'].get(k, True))
            ttk.Checkbutton(row, text=name, variable=v, command=lambda k=k, v=v: self.set_perf('metrics', k, v.get())).pack(side='left', padx=(0, 10))
        for key, name, opts in (('layout', 'Расположение', (('vertical', 'столбиком'), ('horizontal', 'в строку'))),
                                ('compare', 'Сравнивать с', (('norm', 'твоей нормой на чемпионе'), ('emerald', 'Изумруд+ (lolalytics)')))):
            row = tk.Frame(f, bg=C['bg']); row.pack(anchor='w', pady=2)
            ttk.Label(row, text=name, width=16).pack(side='left')
            v = tk.StringVar(value=pf[key])
            for val, t in opts:
                ttk.Radiobutton(row, text=t, value=val, variable=v, command=lambda key=key, v=v: self.set_perf(key, None, v.get())).pack(side='left', padx=(0, 10))
        self.h(f, 'Золото поверх таблицы Tab')
        self.note(f, 'Цифры встают справа от строк игровой таблицы. Открой таблицу в игре, нажми кнопку расстановки выше и подгони: '
                     'тяни столбик мышью, ползунками — высоту строки и промежуток между командами.')
        self.slider(f, 'Высота строки', 'tab_row', 30, 80, lambda x: self.set_tab('tab_row', int(x)), fmt=lambda x: f'{x:.0f} px')
        self.slider(f, 'Промежуток между командами', 'tab_gap', 0, 120, lambda x: self.set_tab('tab_gap', int(x)), fmt=lambda x: f'{x:.0f} px')
        v = tk.BooleanVar(value=self.s['tab_swap'])
        ttk.Checkbutton(f, text='Моя команда в таблице снизу', variable=v, command=lambda: self.set_tab('tab_swap', v.get())).pack(anchor='w')
        self.h(f, 'Второй монитор')
        ttk.Button(f, text='Открыть дашборд со всеми чемпионами', command=self.open_dash).pack(anchor='w')
        ttk.Button(f, text='Сбросить позиции окон', command=self.reset_layout).pack(anchor='w', pady=6)
        self.reset_btn(f, 'windows', 'Все настройки окон по умолчанию')

    def set_perf(self, key, sub, v):
        if sub: self.s['perf'][key][sub] = v
        else: self.s['perf'][key] = v
        self.s.save()
        if self.last_game: self.ov['perf'].show(self.last_game)
        elif self.demo_on: self.ov['perf'].demo()

    def set_tab(self, key, v):
        if self.s.get(key) == v: return
        self.s[key] = v; self.s.save()
        if self.demo_on: self.tab['tabgold'].demo()

    def toggle_widget(self, k):
        self.s['widgets'][k] = self.w_vars[k].get(); self.s.save(); self.apply_visibility()

    def reset_layout(self):
        self.s['layout'].pop(screens()[0], None); self.s.save(); self.rebuild()

    def slider(self, parent, name, key, lo, hi, on_change, fmt=lambda x: f'{x:.0f}%', live=True, test=None):
        """Ползунок с подписью значения. live=False — применяется, когда отпустишь мышь."""
        row = tk.Frame(parent, bg=C['bg']); row.pack(anchor='w', pady=3)
        ttk.Label(row, text=name, width=22).pack(side='left')
        v = tk.DoubleVar(value=self.s[key])
        val = ttk.Label(row, width=7, style='V.TLabel', text=fmt(self.s[key]))
        sc = ttk.Scale(row, from_=lo, to=hi, variable=v, length=self.fs(300))
        sc.pack(side='left'); val.pack(side='left', padx=8)
        if live: sc.configure(command=lambda _: (val.configure(text=fmt(v.get())), on_change(v.get())))
        else:
            sc.configure(command=lambda _: val.configure(text=fmt(v.get())))
            sc.bind('<ButtonRelease-1>', lambda e: on_change(v.get()))
        if test: ttk.Button(row, text='Проверить', command=test).pack(side='left')
        return v

    def build_look(self):
        f = self.tab_look
        self.h(f, 'Тема')
        row = tk.Frame(f, bg=C['bg']); row.pack(anchor='w')
        for k, (name, pal) in THEMES.items():
            b = tk.Label(row, text=name, bg=pal['panel'], fg=pal['gold'], font=(F['font'], self.fs(10), 'bold'), padx=12, pady=6,
                         highlightthickness=2, highlightbackground=C['gold'] if self.s['theme'] == k else pal['line'], cursor='hand2')
            b.pack(side='left', padx=(0, 6))
            b.bind('<Button-1>', lambda e, k=k: self.set_look('theme', k))
        self.h(f, 'Акцентный цвет')
        row = tk.Frame(f, bg=C['bg']); row.pack(anchor='w')
        for col, name in ACCENTS.items():
            sw = THEMES[self.s['theme']][1]['gold'] if col == 'theme' else col
            b = tk.Label(row, text='Тема' if col == 'theme' else '  ', bg=sw, fg=C['bg'], width=4, cursor='hand2',
                         highlightthickness=2, highlightbackground=C['fg'] if self.s['accent'] == col else C['bg'])
            b.pack(side='left', padx=2)
            b.bind('<Button-1>', lambda e, col=col: self.set_look('accent', col))
        row = tk.Frame(f, bg=C['bg']); row.pack(anchor='w', pady=(10, 0))
        ttk.Label(row, text='Шрифт', width=22).pack(side='left')
        fv = tk.StringVar(value=self.s['font'])
        cb = ttk.Combobox(row, state='readonly', width=20, values=FONTS, textvariable=fv); cb.pack(side='left')
        cb.bind('<<ComboboxSelected>>', lambda e: self.set_look('font', fv.get()))
        self.h(f, 'Размеры')
        self.slider(f, 'Размер текста', 'scale', 70, 170, lambda x: self.set_look('scale', int(x)), live=False)
        self.slider(f, 'Размер иконок', 'icon', 20, 64, lambda x: self.set_look('icon', int(x)), fmt=lambda x: f'{x:.0f} px', live=False)
        self.slider(f, 'Непрозрачность виджетов', 'alpha', 30, 100, self.set_alpha)
        row = tk.Frame(f, bg=C['bg']); row.pack(anchor='w', pady=3)
        ttk.Label(row, text='Фон виджетов', width=22).pack(side='left')
        bgv = tk.StringVar(value=self.s['widget_bg'])
        for val, name in (('panel', 'плашка'), ('none', 'без фона, только текст')):
            ttk.Radiobutton(row, text=name, value=val, variable=bgv, command=lambda: self.set_look('widget_bg', bgv.get())).pack(side='left', padx=(0, 10))
        self.h(f, 'Что показывать')
        grid = tk.Frame(f, bg=C['bg']); grid.pack(anchor='w')
        for i, (k, name) in enumerate(SHOW.items()):
            v = tk.BooleanVar(value=self.s['show'].get(k, True))
            ttk.Checkbutton(grid, text=name, variable=v, command=lambda k=k, v=v: self.set_show(k, v.get())).grid(row=i // 2, column=i % 2, sticky='w', padx=(0, 18))
        if Image is None: self.note(f, 'Картинки недоступны: не найдена библиотека Pillow.')
        self.reset_btn(f, 'look', 'Вид по умолчанию')

    def set_look(self, key, v):
        if self.s.get(key) == v: return
        self.s[key] = v; self.s.save(); self.rebuild()

    def set_alpha(self, v):
        self.s['alpha'] = int(v); self.s.save()
        for w in list(self.ov.values()) + list(self.tab.values()): w.attributes('-alpha', int(v) / 100)

    def set_show(self, k, v):
        self.s['show'][k] = v; self.s.save(); self.rebuild()

    def build_voice(self):
        f = self.tab_voice
        self.h(f, 'Голос подсказок')
        r = tk.Frame(f, bg=C['bg']); r.pack(anchor='w')
        self.voice_var = tk.StringVar()
        self.voice_cb = ttk.Combobox(r, state='readonly', width=26, textvariable=self.voice_var); self.voice_cb.pack(side='left')
        self.voice_cb.bind('<<ComboboxSelected>>', lambda e: self.pick_voice())
        ttk.Button(r, text='Прослушать', command=lambda: self.voice.say('Окно ганка через двадцать секунд, поставь вард в реку', force=True)).pack(side='left', padx=8)
        self.voice_msg = ttk.Label(f, text='', style='M.TLabel'); self.voice_msg.pack(anchor='w', pady=4)
        self.refresh_voices()
        self.h(f, 'Громкость')
        self.slider(f, 'Общая', 'master', 0, 100, lambda x: self.set_voice_param('master', x))
        self.slider(f, 'Голос', 'volume', 0, 100, lambda x: self.set_voice_param('volume', x),
                    test=lambda: self.voice.say('Дракон через минуту', force=True))
        self.slider(f, 'Сигнал', 'beep_volume', 0, 100, lambda x: self.set_voice_param('beep_volume', x),
                    test=lambda: self.voice.beep(force=True))
        row = tk.Frame(f, bg=C['bg']); row.pack(anchor='w', pady=3)
        ttk.Label(row, text='Звук сигнала', width=22).pack(side='left')
        names = [v[0] for v in SOUNDS.values()]
        sv = self.sound_var = tk.StringVar(value=SOUNDS.get(self.s['sound'], SOUNDS['bell'])[0])
        cb = ttk.Combobox(row, state='readonly', width=24, values=names, textvariable=sv); cb.pack(side='left')
        def pick_sound(_=None):
            self.s['sound'] = self.voice.sound = list(SOUNDS)[cb.current()]; self.s.save(); self.voice.beep(force=True)
        cb.bind('<<ComboboxSelected>>', pick_sound)
        ttk.Button(row, text='Прослушать', command=lambda: self.voice.beep(force=True)).pack(side='left', padx=8)
        row = tk.Frame(f, bg=C['bg']); row.pack(anchor='w', pady=(6, 0))
        ttk.Button(row, text='▶ Проверить подсказку', style='A.TButton',
                   command=lambda: self.test_hint('gank1', 'Окно ганка через двадцать секунд, поставь вард в реку')).pack(side='left')
        ttk.Label(row, text='  звучит так, как настроено для «Ганк 1» на вкладке «Подсказки»', style='M.TLabel').pack(side='left')
        self.h(f, 'Речь')
        self.slider(f, 'Скорость речи', 'rate', .7, 1.6, lambda x: self.set_voice_param('rate', x), fmt=lambda x: f'{x:.1f}×')
        self.note(f, 'Microsoft звучат лучше всех, но нужен интернет. Silero работают без интернета, пакет ~350 МБ скачивается один раз. '
                     'Piper: Дмитрий встроен, остальные ~60 МБ. Если выбранный голос не сработал, говорит Piper. '
                     f"Выключить звук в игре: {self.s['keys']['mute'].upper()}.")
        self.reset_btn(f, 'voice', 'Звук по умолчанию')

    def refresh_voices(self):
        vals = [f"{n}{'' if self.voice.ready(v) else ' (скачать)'}" for v, n in VOICES.items()]
        self.voice_cb.configure(values=vals)
        self.voice_var.set(vals[list(VOICES).index(self.s['voice'])] if self.s['voice'] in VOICES else vals[0])

    def pick_voice(self):
        v = list(VOICES)[self.voice_cb.current()]
        if self.voice.ready(v):
            self.s['voice'] = self.voice.voice = v; self.s.save(); self.voice.warm()
            self.voice_msg.configure(text=f'Голос: {VOICES[v]}'); return
        what = 'пакет Silero (~350 МБ, один раз для всех голосов Silero)' if v.startswith('silero') else VOICES[v]
        def job():
            try:
                self.voice.fetch(v, lambda p: self.root.after(0, lambda: self.voice_msg.configure(text=f'Скачиваю {what}: {p * 100:.0f}%')))
                def done():
                    self.s['voice'] = self.voice.voice = v; self.s.save(); self.refresh_voices(); self.voice.warm()
                    self.voice_msg.configure(text=f'Голос {VOICES[v]} установлен')
                self.root.after(0, done)
            except Exception as e:
                msg = f'Не скачалось: {e}'
                self.root.after(0, lambda: self.voice_msg.configure(text=msg))
        threading.Thread(target=job, daemon=True).start()

    def set_voice_param(self, key, v):
        v = round(v, 2) if key == 'rate' else int(v)
        if self.s.get(key) == v: return
        self.s[key] = v; setattr(self.voice, key, v); self.s.save()

    def build_keys(self):
        f = self.tab_keys
        self.h(f, 'Горячие клавиши')
        self.key_lbls = {}
        for key, name in (('mute', 'Выключить / включить звук'), ('hide', 'Скрыть / показать виджеты'),
                          ('scoreboard', 'Таблица по линиям (держать)'), ('drag', 'Двигать виджеты мышью (держать)')):
            r = tk.Frame(f, bg=C['bg']); r.pack(anchor='w', pady=3, fill='x')
            ttk.Label(r, text=name, width=34).pack(side='left')
            l = ttk.Label(r, text=self.s['keys'][key].upper(), width=18, style='V.TLabel'); l.pack(side='left')
            self.key_lbls[key] = l
            ttk.Button(r, text='Изменить', command=lambda key=key: self.capture(key)).pack(side='left')
        self.note(f, 'Нажми «Изменить», затем нужное сочетание. Работает, пока окно программы активно. Esc — отмена.')
        self.reset_btn(f, 'keys', 'Клавиши по умолчанию')

    def capture(self, key):
        self.key_lbls[key].configure(text='нажми сочетание…')
        mods_only = key == 'drag'
        def on(e):
            ks = e.keysym.lower()
            if ks == 'escape':
                done(); self.key_lbls[key].configure(text=self.s['keys'][key].upper()); return
            names = {'control_l': 'ctrl', 'control_r': 'ctrl', 'shift_l': 'shift', 'shift_r': 'shift', 'alt_l': 'alt', 'alt_r': 'alt', 'quoteleft': 'grave', 'prior': 'pageup', 'next': 'pagedown'}
            k = names.get(ks, ks)
            if k in ('ctrl', 'shift', 'alt') and not mods_only: return
            if k not in VK: return
            combo = [m for m, bit in (('ctrl', 0x4), ('shift', 0x1), ('alt', 0x20000)) if e.state & bit and m != k] + [k]
            if mods_only: combo = [k]
            self.s['keys'][key] = '+'.join(combo); self.s.save()
            self.key_lbls[key].configure(text=self.s['keys'][key].upper()); done()
        def done(): self.root.unbind('<KeyPress>')
        self.root.bind('<KeyPress>', on)

    def build_timers(self):
        f = self.tab_time
        self.h(f, 'Время объектов')
        self.note(f, 'Значения сезона 2026. Если Riot поменяет время в патче, поправь здесь (минуты:секунды).')
        names = {'dragon_first': 'Первый дракон', 'dragon_respawn': 'Дракон, возрождение', 'elder_respawn': 'Древний дракон, возрождение',
                 'grubs': 'Личинки Бездны', 'herald': 'Герольд', 'baron_first': 'Барон', 'baron_respawn': 'Барон, возрождение',
                 'inhib_respawn': 'Ингибитор, восстановление'}
        for k, n in names.items():
            r = tk.Frame(f, bg=C['bg']); r.pack(anchor='w', pady=2)
            ttk.Label(r, text=n, width=30).pack(side='left')
            v = tk.StringVar(value=core.mmss(self.s['obj'].get(k, core.OBJ[k])))
            e = ttk.Entry(r, textvariable=v, width=8); e.pack(side='left')
            e.bind('<FocusOut>', lambda ev, k=k, v=v: self.set_obj(k, v))
            e.bind('<Return>', lambda ev, k=k, v=v: self.set_obj(k, v))
        self.reset_btn(f, 'obj', 'Таймеры по умолчанию')

    def set_obj(self, k, v):
        try:
            m, s = v.get().split(':'); sec = int(m) * 60 + int(s)
        except Exception:
            v.set(core.mmss(self.s['obj'][k])); return
        self.s['obj'][k] = core.OBJ[k] = sec; self.s.save()

    def build_updates(self):
        f = self.tab_upd
        self.h(f, 'Версия')
        ttk.Label(f, text=f'LoL Helper {self.version}').pack(anchor='w')
        self.upd_msg = ttk.Label(f, text='', style='M.TLabel'); self.upd_msg.pack(anchor='w', pady=4)
        v = tk.BooleanVar(value=self.s['auto_update'])
        ttk.Checkbutton(f, text='Проверять обновления при запуске', variable=v,
                        command=lambda: (self.s.__setitem__('auto_update', v.get()), self.s.save())).pack(anchor='w')
        ttk.Button(f, text='Проверить сейчас', command=lambda: self.check_updates(True)).pack(anchor='w', pady=6)
        self.note(f, 'Статистика обновляется сама каждые 30 минут с raw.githubusercontent.com (работает без VPN).')
        self.h(f, 'Сброс')
        self.note(f, 'Вернуть все настройки программы к начальным: подсказки, вид, звук, окна, клавиши, таймеры.')
        self.confirm = None
        def reset_all():
            if self.confirm is None:
                self.confirm = ttk.Label(f, text='Нажми ещё раз, чтобы подтвердить', style='V.TLabel'); self.confirm.pack(anchor='w')
                return
            self.s.reset([k for ks in SECTIONS.values() for k in ks])
            self.sync_voice(); core.OBJ.update(self.s['obj']); self.rebuild()
            self.status.configure(text='Все настройки сброшены')
        ttk.Button(f, text='Сбросить все настройки', command=reset_all).pack(anchor='w', pady=6)

    def offer_update(self, tag, start):
        self.update_state(f'Доступна новая версия {tag} (у тебя {self.version})', start, 'Обновить')

    def update_state(self, text, action=None, label=None):
        """Плашка обновления над вкладками: текст и кнопка (Обновить / Перезапустить / Повторить)."""
        self.upd = (text, action, label)
        self.banner.pack(fill='x', padx=8, pady=(0, 4), before=self.nb)
        self.banner_lbl.configure(text=text)
        if action:
            self.banner_btn.configure(text=label or ('Перезапустить' if 'скачана' in text else 'Повторить'), command=action)
            self.banner_btn.pack(side='right')
        else: self.banner_btn.pack_forget()
        if hasattr(self, 'upd_msg'):
            try: self.upd_msg.configure(text=text)
            except Exception: pass

    def check_updates(self, manual=False):
        if not self.updater: return
        def job():
            msg = self.updater(self)
            self.root.after(0, lambda: self.upd_msg.configure(text=msg))
        threading.Thread(target=job, daemon=True).start()

    def reload_data(self, data):
        """Новая статистика скачалась: подменяем между играми, текущая игра доигрывается со старой."""
        if self.last_game:
            self.pending_data = data; return
        self.pending_data = None
        self.data = data
        self.set_who(self.who)
        self.panel_sync()

    def run(self):
        self.root.mainloop()
