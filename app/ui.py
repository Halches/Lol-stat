# Окна LoL Helper: панель управления, виджеты поверх игры, дашборд на втором мониторе, таблица по Tab, итог игры.
# Внешний вид (тема, акцент, шрифт, иконки) настраивается на вкладке «Вид» и применяется сразу: окна пересобираются.
import base64, io, json, os, queue, re, threading, time, urllib.request
import tkinter as tk
from tkinter import ttk

import core, lcu
from voice import Voice, VOICES

try:
    from PIL import Image, ImageOps, ImageTk
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
WIDGETS = {'hints': 'Подсказки', 'cs': 'Фарм и норма', 'lane': 'Оппонент на линии', 'timers': 'Таймеры объектов'}
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
    'hints': {h[0]: h[3] for h in core.HINTS},
    'widgets': {'hints': True, 'cs': True, 'lane': True, 'timers': True},
    'dashboard': True, 'scoreboard': True, 'postgame': True, 'auto_import': False,
    'theme': 'hextech', 'accent': 'theme', 'font': 'Segoe UI', 'scale': 100, 'icon': 36, 'alpha': 90, 'widget_bg': 'panel',
    'show': {k: True for k in SHOW},
    'layout': {},
    'keys': {'mute': 'ctrl+shift+m', 'hide': 'ctrl+shift+h', 'scoreboard': 'tab', 'drag': 'alt'},
    'voice': 'dmitri', 'volume': 80, 'rate': 1.0, 'master': 100, 'beep_volume': 70,
    'obj': dict(core.OBJ), 'who': '', 'auto_update': True,
}
SECTIONS = {   # что сбрасывает кнопка «По умолчанию» в каждом разделе
    'hints': ['hints'], 'voice': ['voice', 'volume', 'rate', 'master', 'beep_volume'],
    'look': ['theme', 'accent', 'font', 'scale', 'icon', 'alpha', 'widget_bg', 'show'],
    'windows': ['widgets', 'dashboard', 'scoreboard', 'postgame', 'layout'], 'keys': ['keys'], 'obj': ['obj'],
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
    if not r: return ''
    t = TIER_RU.get(r['tier'], r['tier'])
    n = r['w'] + r['l']
    return f"{t} {r['div'] if r['tier'] not in ('MASTER', 'GRANDMASTER', 'CHALLENGER') else ''} · {r['lp']} LP" + (f" · {round(r['w'] / n * 100)}% из {n}" if n else '')


# ---------------- Виджеты поверх игры ----------------

class Overlay(tk.Toplevel):
    def __init__(self, app, key, default_xy):
        super().__init__(app.root)
        self.app, self.key = app, key
        self.bg = KEY if app.s['widget_bg'] == 'none' else C['bg']
        self.overrideredirect(True)
        self.attributes('-topmost', True)
        self.configure(bg=self.bg, highlightthickness=0 if self.bg == KEY else 1, highlightbackground=C['line'])
        self.body = tk.Frame(self, bg=self.bg, padx=10, pady=6)
        self.body.pack(fill='both', expand=True)
        x, y = app.layout().get(key, default_xy)
        self.geometry(f'+{int(x)}+{int(y)}')
        self.update_idletasks()
        click_through(self, True)
        self.attributes('-alpha', app.s['alpha'] / 100)
        if self.bg == KEY and IS_WIN: self.attributes('-transparentcolor', KEY)
        self._drag = None
        self.bind_all_children(self)

    def bind_all_children(self, w):
        w.bind('<ButtonPress-1>', self._start, add='+')
        w.bind('<B1-Motion>', self._move, add='+')
        w.bind('<ButtonRelease-1>', self._end, add='+')
        for ch in w.winfo_children(): self.bind_all_children(ch)

    def _start(self, e): self._drag = (e.x_root - self.winfo_x(), e.y_root - self.winfo_y())

    def _move(self, e):
        if self._drag: self.geometry(f'+{e.x_root - self._drag[0]}+{e.y_root - self._drag[1]}')

    def _end(self, e):
        if self._drag:
            self._drag = None
            self.app.layout()[self.key] = [self.winfo_x(), self.winfo_y()]
            self.app.s.save()

    def unlock(self, on):
        click_through(self, not on)
        self.configure(highlightthickness=1 if on or self.bg != KEY else 0, highlightbackground=C['gold'] if on else C['line'])

    def lbl(self, parent=None, size=11, color='fg', bold=False):
        l = tk.Label(parent or self.body, bg=self.bg, fg=C[color], font=(F['font'], self.app.fs(size), 'bold' if bold else 'normal'),
                     justify='left', anchor='w', compound='left')
        self.bind_all_children(l)
        return l


class HintsOverlay(Overlay):
    def __init__(self, app, xy):
        super().__init__(app, 'hints', xy)
        self.items = []
        self.lines = [self.lbl(size=12) for _ in range(4)]
        for l in self.lines: l.configure(wraplength=app.fs(380)); l.pack(anchor='w', fill='x')
        self.show([])

    def push(self, text, color='fg'):
        self.items.append((time.time(), text, color)); self.items = self.items[-4:]

    def show(self, _=None):
        now = time.time()
        self.items = [i for i in self.items if now - i[0] < 14]
        for l, it in zip(self.lines, [None] * (4 - len(self.items)) + self.items):
            l.configure(text=it[1] if it else '', fg=C[it[2]] if it else C['fg'])
        if self.items: self.deiconify_if_allowed()
        else: self.withdraw()

    def deiconify_if_allowed(self):
        if not self.app.hidden and self.app.s['widgets'].get('hints'): self.deiconify()


class CsOverlay(Overlay):
    def __init__(self, app, xy):
        super().__init__(app, 'cs', xy)
        self.a, self.b = self.lbl(size=14, bold=True), self.lbl(size=10, color='mute')
        self.a.pack(anchor='w'); self.b.pack(anchor='w')
        self.a.configure(text='Фарм появится в игре')

    def show(self, g):
        me, m = g.me, max(1, g.t / 60)
        csm = me['cs'] / m
        norm = self.app.player.norm(me['c'], g.role) if self.app.player else {}
        want = norm.get('csm')
        lo = self.app.data.lola.get(f"{me['c']}|{g.role}")
        emer = lo['cs'] / 28 if lo else None   # у lolalytics средний CS за игру; средняя игра ~28 мин
        col = 'good' if want and csm >= want else 'bad' if want and csm < want * .9 else 'fg'
        self.a.configure(text=f"  {me['cs']} CS · {csm:.1f}/мин", fg=C[col], image=self.app.img('champ', me['c'], .8) or '')
        parts = []
        if want: parts.append(f'твоя норма {want:.1f} ({norm["n"]} игр)')
        if emer: parts.append(f'Изумруд+ ≈{emer:.1f}')
        self.b.configure(text=' · '.join(parts))


class LaneOverlay(Overlay):
    def __init__(self, app, xy):
        super().__init__(app, 'lane', xy)
        self.a, self.b = self.lbl(size=12, bold=True), self.lbl(size=10, color='mute')
        self.a.pack(anchor='w'); self.b.pack(anchor='w')
        self.a.configure(text='Оппонент появится в игре')

    def show(self, g):
        if not g.opp:
            self.a.configure(text='Оппонент не определён', fg=C['mute'], image=''); self.b.configure(text=''); return
        d, o, me = g.lane_diff(), g.opp, g.me
        self.a.configure(text=f"  {self.app.data.cn(o['c'])}: {d:+.0f} золота", fg=C['good' if d > 300 else 'bad' if d < -300 else 'fg'],
                         image=self.app.img('champ', o['c'], .8, gray=o['dead']) or '')
        self.b.configure(text=f"ур. {me['lvl']} / {o['lvl']} · CS {me['cs']} / {o['cs']} · {o['k']}/{o['d']}/{o['a']}")


class TimersOverlay(Overlay):
    def __init__(self, app, xy):
        super().__init__(app, 'timers', xy)
        self.rows = [self.lbl(size=11) for _ in range(5)]
        for r in self.rows: r.pack(anchor='w')
        self.rows[0].configure(text='Таймеры появятся в игре')

    def show(self, g):
        ob, t = g.objectives(), g.t
        lines = []
        for key, name in (('dragon', ob.get('dragon_name', 'Дракон')), ('grubs', 'Личинки'), ('herald', 'Герольд'), ('baron', 'Барон')):
            at = ob.get(key)
            if at is None: continue
            left = at - t
            lines.append((f'{name}: ' + (f'через {core.mmss(left)}' if left > 0 else 'жив'), 'gold' if 0 < left <= 60 else 'fg' if left > 0 else 'mute'))
        nc = g.next_cannon()
        if nc: lines.append((f'Осадный миньон: {core.mmss(nc - t)}', 'mute'))
        for r, ln in zip(self.rows, lines + [('', 'fg')] * 5):
            r.configure(text=ln[0], fg=C[ln[1]])


class Scoreboard(Overlay):
    """Таблица по линиям, пока зажат Tab."""
    def __init__(self, app, xy):
        super().__init__(app, 'scoreboard', xy)
        self.title = self.lbl(size=12, color='gold', bold=True); self.title.pack(anchor='w')
        self.tbl = tk.Frame(self.body, bg=self.bg); self.tbl.pack()
        self.withdraw()

    def show(self, g):
        for w in self.tbl.winfo_children(): w.destroy()
        d, app = self.app.data, self.app
        self.title.configure(text=f'{core.mmss(g.t)} · золото в предметах команды {g.gold_diff():+.0f}')
        heads = ['', '', 'Мы', 'ур', 'CS', 'К/С/П', 'золото', 'разница', 'золото', 'К/С/П', 'CS', 'ур', 'Враги', '']
        for j, h in enumerate(heads):
            tk.Label(self.tbl, text=h, bg=self.bg, fg=C['mute'], font=(F['font'], app.fs(9))).grid(row=0, column=j, padx=5)
        for i, r in enumerate(core.ROLES, 1):
            a = next((p for p in g.allies if p['pos'] == r), None)
            e = next((p for p in g.enemies if p['pos'] == r), None)
            if not a and not e: continue
            diff = (a['igold'] - e['igold']) if a and e else 0
            vals = [core.ROLE_RU[r], None,
                    d.cn(a['c']) if a else '', a and a['lvl'], a and a['cs'], a and f"{a['k']}/{a['d']}/{a['a']}", a and a['igold'],
                    f'{diff:+.0f}',
                    e and e['igold'], e and f"{e['k']}/{e['d']}/{e['a']}", e and e['cs'], e and e['lvl'], d.cn(e['c']) if e else '', None]
            for j, v in enumerate(vals):
                if j in (1, 13):
                    p = a if j == 1 else e
                    im = p and app.img('champ', p['c'], 1, gray=p['dead'])
                    if im: tk.Label(self.tbl, image=im, bg=self.bg).grid(row=i, column=j, padx=3, pady=2)
                    continue
                col = C['gold'] if a is g.me and j == 2 else C['good'] if j == 7 and diff > 300 else C['bad'] if j == 7 and diff < -300 else C['fg']
                tk.Label(self.tbl, text='' if v is None or v is False else v, bg=self.bg, fg=col,
                         font=(F['font'], app.fs(11), 'bold' if j in (2, 7, 12) else 'normal')).grid(row=i, column=j, padx=5, sticky='w')


# ---------------- Дашборд на втором мониторе ----------------

class Dashboard(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app.root)
        self.app = app
        self.title('LoL Helper — игра')
        self.configure(bg=C['bg'])
        lay = app.layout().get('dashboard')
        if lay: self.geometry(f'{lay[2]}x{lay[3]}+{lay[0]}+{lay[1]}')
        else:
            sig, (pw, ph), (vx, vy, vw, vh) = screens()
            x = pw + 40 if vw > pw and vx >= 0 else vx + 40 if vx < 0 else 80
            self.geometry(f'1400x820+{x}+60')
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.bind('<Configure>', self._moved)
        fn = F['font']
        self.head = tk.Label(self, bg=C['bg'], fg=C['gold'], font=(fn, app.fs(16), 'bold'), anchor='w')
        self.head.pack(fill='x', padx=14, pady=(10, 0))
        self.sub = tk.Label(self, bg=C['bg'], fg=C['mute'], font=(fn, app.fs(11)), anchor='w')
        self.sub.pack(fill='x', padx=14)
        self.teams = tk.Frame(self, bg=C['bg']); self.teams.pack(fill='both', expand=True, padx=10, pady=8)
        self.cols = [tk.Frame(self.teams, bg=C['bg']) for _ in range(2)]
        for i, f in enumerate(self.cols): f.grid(row=0, column=i, sticky='nsew', padx=4); self.teams.columnconfigure(i, weight=1, uniform='t')
        tk.Label(self, text='Подсказки за игру', bg=C['bg'], fg=C['mute'], font=(fn, app.fs(10)), anchor='w').pack(fill='x', padx=14)
        self.log = tk.Text(self, height=6, bg=C['panel'], fg=C['fg'], relief='flat', font=(fn, app.fs(10)), wrap='word',
                           highlightthickness=1, highlightbackground=C['line'])
        self.log.pack(fill='x', padx=14, pady=(0, 12))
        self.head.configure(text='Ждём начала игры')
        self.cards = {}
        self._save_job = None

    def _moved(self, e):
        if e.widget is not self: return
        if self._save_job: self.after_cancel(self._save_job)
        self._save_job = self.after(800, self._save)

    def _save(self):
        self.app.layout()['dashboard'] = [self.winfo_x(), self.winfo_y(), self.winfo_width(), self.winfo_height()]
        self.app.s.save()

    def close(self):
        self.app.s['dashboard'] = False; self.app.s.save(); self.app.dash = None; self.destroy()

    def add_log(self, t, text):
        self.log.insert('end', f'{core.mmss(t)}  {text}\n'); self.log.see('end')

    def card(self, col, p):
        key = (col, p['riot'])
        if key in self.cards: return self.cards[key]
        app, fn, fs = self.app, F['font'], self.app.fs
        bg = C['panel']
        f = tk.Frame(self.cols[col], bg=bg, padx=8, pady=6, highlightthickness=1, highlightbackground=C['line'])
        f.pack(fill='x', pady=3)
        w = {'f': f}
        w['por'] = tk.Label(f, bg=bg, fg=C['fg'], font=(fn, fs(10), 'bold'), compound='top')
        w['por'].grid(row=0, column=0, rowspan=3, padx=(0, 6), sticky='n')
        sp = tk.Frame(f, bg=bg); sp.grid(row=0, column=1, rowspan=3, sticky='n', padx=(0, 8))
        w['sp'] = [tk.Label(sp, bg=bg) for _ in range(3)]
        for l in w['sp']: l.pack(pady=1)
        w['name'] = tk.Label(f, bg=bg, anchor='w', font=(fn, fs(13), 'bold'))
        w['name'].grid(row=0, column=2, sticky='w')
        w['line'] = tk.Label(f, bg=bg, anchor='w', fg=C['fg'], font=(fn, fs(10)))
        w['line'].grid(row=1, column=2, sticky='w')
        w['items'] = tk.Frame(f, bg=bg); w['items'].grid(row=2, column=2, sticky='w', pady=(3, 0))
        w['rank'] = tk.Label(f, bg=bg, fg=C['mute'], font=(fn, fs(9)), compound='top', justify='center')
        w['rank'].grid(row=0, column=3, rowspan=3, sticky='ne', padx=(8, 0))
        w['scout'] = tk.Label(f, bg=bg, fg=C['mute'], font=(fn, fs(9)), anchor='w', justify='left')
        w['scout'].grid(row=3, column=0, columnspan=4, sticky='w')
        f.columnconfigure(2, weight=1)
        w['sig'] = None
        self.cards[key] = w
        return w

    def show(self, g, scout, ranks):
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
                w['por'].configure(image=big or '', text=str(p['lvl']) if big else f"{p['lvl']} ур.")
                sps = (p['spells'] if sh['spells'] else [])[:2]
                imgs = [app.img('spell', s, .6) for s in sps] + ([app.img('rune', p['keystone'], .6)] if sh['runes'] else [])
                for l, im in zip(w['sp'], imgs + [None] * 3): l.configure(image=im or '')
                dead = f"  · мёртв {core.mmss(p['respawn'])}" if p['dead'] else ''
                w['name'].configure(text=f"{d.cn(p['c'])}   {p['k']}/{p['d']}/{p['a']}{dead}", fg=C['blue'] if col == 0 else C['red'])
                w['line'].configure(text=f"{core.ROLE_RU.get(p['pos'], '')} · CS {p['cs']} ({p['cs'] / max(1, g.t / 60):.1f}/мин) · предметы {p['igold']:.0f} · обзор {p['ward']:.0f}")
                sig = tuple(p['items'])
                if w['sig'] != sig:   # предметы перерисовываем только при изменении
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
                rk = ranks.get(p['riot'])
                if sh['ranks'] and rk:
                    w['rank'].configure(image=app.img('emb', TIER_RU.get(rk['tier']), 1.3) or '', text=rank_text(rk).replace(' · ', '\n', 1))
                else: w['rank'].configure(image='', text='')
                w['scout'].configure(text=(scout.get(p['c'], '') if col == 1 and sh['scout'] else ''))

    def reset(self):
        for w in self.cards.values(): w['f'].destroy()
        self.cards = {}
        self.log.delete('1.0', 'end')
        self.head.configure(text='Ждём начала игры', fg=C['gold']); self.sub.configure(text='')


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
        self.player = None
        self.engine = None
        self.draft = None
        self.draft_sig = None
        self.imported = None
        self.scout = {}
        self.last_game = None
        self.result = None
        self.keys_prev = {}
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
        self.ov = {'hints': HintsOverlay(self, (40, int(ph * .32))), 'cs': CsOverlay(self, (pw - 400, 70)),
                   'lane': LaneOverlay(self, (pw - 400, 150)), 'timers': TimersOverlay(self, (pw - 400, 230))}
        self.board = Scoreboard(self, (int(pw * .22), int(ph * .2)))
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

    def layout(self):
        return self.s['layout'].setdefault(screens()[0], {})

    def sync_voice(self):
        v, s = self.voice, self.s
        v.voice, v.volume, v.rate, v.master, v.beep_volume = s['voice'], s['volume'], s['rate'], s['master'], s['beep_volume']

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
        en = {h: self.s['hints'].get(h, 'off') != 'off' for h in core.HINT_IDS}
        self.engine = core.Engine(self.data, self.player, enabled=en)

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
                    if not in_game: self.ranks = {}
                    in_game = True
                    g = core.Game(raw, self.data)
                    if self.engine is None: self.new_engine()
                    hints = self.engine.tick(g)
                    res = next((e.get('Result') for e in g.events if e.get('EventName') == 'GameEnd'), None)
                    if now - last_scout > 90:
                        last_scout = now
                        self.scout = self.fetch_scout(g)
                    if len(self.ranks) < len(g.players): self.fetch_ranks(g)
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

    def fetch_ranks(self, g):
        """Звания всех десяти через клиент (как в профиле игрока). По одному за проход, чтобы не тормозить."""
        for p in g.players:
            if p['riot'] in self.ranks: continue
            pu = self.client.puuid(p['riot'])
            self.ranks[p['riot']] = self.client.rank(pu) if pu else None
            return

    def draft_allies(self, sess):
        out = []
        for p in sess.get('myTeam') or []:
            pu = p.get('puuid')
            if pu and pu not in self.ranks: self.ranks[pu] = self.client.rank(pu)
            out.append({'c': self.data.ids.get(str(p.get('championId') or p.get('championPickIntent') or 0)),
                        'pos': core.LCU_ROLE.get((p.get('assignedPosition') or '').lower(), ''), 'rank': self.ranks.get(pu),
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
            mode = self.s['hints'].get(h.id, 'off')
            if mode == 'off': continue
            self.ov['hints'].push(h.text)
            if self.dash: self.dash.add_log(g.t, h.text)
            if mode == 'beep': self.voice.beep()
            elif mode == 'voice': self.voice.say(h.say)
        if hints: self.ov['hints'].show()
        for k in ('cs', 'lane', 'timers'):
            try: self.ov[k].show(g)
            except Exception: pass
        if self.dash:
            try: self.dash.show(g, self.scout, self.ranks)
            except Exception: pass
        self.status.configure(text=f'Игра: {core.mmss(g.t)} · {self.data.cn(g.me["c"]) if g.me else ""}')

    def on_end(self):
        g = self.last_game
        if g and self.engine and self.s['postgame'] and g.t > 300 and self.s['hints'].get('postgame') != 'off':
            res = core.postgame(self.engine, g, self.player)
            if res: show_postgame(self, res, self.result)
        self.last_game, self.result, self.engine, self.scout = None, None, None, {}
        if self.pending_data: self.reload_data(self.pending_data)
        self.apply_visibility()
        self.board.withdraw()
        self.status.configure(text='Игра закончилась')

    # ---------------- Драфт ----------------
    def on_draft(self, cs):
        self.draft = cs
        box = self.draft_box
        if cs is None:
            if self.draft_sig != 'none':
                self.draft_sig = 'none'
                for w in box.winfo_children(): w.destroy()
                self.dl(box, 'Драфт появится, когда начнётся выбор чемпионов', 'mute').pack(anchor='w')
            self.imported = None; return
        if not getattr(self, '_draft_shown', False):
            self.nb.select(self.tab_draft); self._draft_shown = True
        sig = json.dumps([cs['role'], cs['me'], cs['enemies'], sorted(cs['unavailable']), [(a['c'], bool(a['rank'])) for a in cs.get('allies', [])]], default=str)
        if sig == self.draft_sig: return
        self.draft_sig = sig
        for w in box.winfo_children(): w.destroy()
        p, d = self.player, self.data
        if not p:
            self.dl(box, 'Аккаунта нет в статистике сайта: выбери игрока на вкладке «Статус»', 'mute').pack(anchor='w'); return
        role = cs['role'] or 'TOP'
        r = core.draft_suggest(p, role, cs['enemies'], cs['unavailable'])
        self.dl(box, f'Роль: {core.ROLE_RU[role]}' + (f' · вероятный оппонент: {d.cn(r["opp"])}' if r['opp'] else ''), 'gold', 12, True).pack(anchor='w')
        self.section(box, 'Кого взять')
        for x in r['picks']:
            row = tk.Frame(box, bg=C['bg']); row.pack(anchor='w', fill='x', pady=1)
            self.dl(row, '  ' + x['name'], 'fg', 11, True, img=self.img('champ', x['c'])).pack(side='left')
            self.dl(row, '  ' + x['why'], 'mute', 10).pack(side='left')
        bans = core.ban_suggest(p, cs['unavailable'])
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
        drag = combo_down(k.get('drag'))
        if drag != self.keys_prev.get('drag'):
            for w in self.ov.values(): w.unlock(drag)
            if drag:
                for key, w in self.ov.items():
                    if self.s['widgets'].get(key) and not self.hidden: w.deiconify()
            else: self.apply_visibility(); self.ov['hints'].show()
            self.keys_prev['drag'] = drag
        tab = self.s['scoreboard'] and self.last_game and not self.hidden and combo_down(k.get('scoreboard')) and game_focused()
        if tab:
            if not self.keys_prev.get('tab') or time.time() - self.keys_prev.get('tab_t', 0) > 1:
                self.board.show(self.last_game); self.board.deiconify(); self.keys_prev['tab_t'] = time.time()
        elif self.keys_prev.get('tab'):
            self.board.withdraw()
        self.keys_prev['tab'] = bool(tab)
        self.root.after(40, self.keys)

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

    def page(self, name):
        f = tk.Frame(self.nb, bg=C['bg'], padx=14, pady=10); self.nb.add(f, text=name); return f

    def h(self, parent, text): ttk.Label(parent, text=text, style='H.TLabel').pack(anchor='w', pady=(8, 4))

    def note(self, parent, text): ttk.Label(parent, text=text, style='M.TLabel', wraplength=self.fs(660), justify='left').pack(anchor='w')

    def reset_btn(self, parent, section, label='По умолчанию'):
        """Кнопка сброса раздела настроек к значениям по умолчанию."""
        def go():
            self.s.reset(SECTIONS[section])
            if section == 'voice': self.sync_voice()
            if section == 'obj': core.OBJ.update(self.s['obj'])
            if section == 'hints' and self.engine: self.engine.enabled = {h: self.s['hints'][h] != 'off' for h in core.HINT_IDS}
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
        f = self.tab_hints
        cv = tk.Canvas(f, bg=C['bg'], highlightthickness=0); sb = ttk.Scrollbar(f, orient='vertical', command=cv.yview)
        inner = tk.Frame(cv, bg=C['bg'])
        inner.bind('<Configure>', lambda e: cv.configure(scrollregion=cv.bbox('all')))
        cv.create_window((0, 0), window=inner, anchor='nw'); cv.configure(yscrollcommand=sb.set)
        cv.pack(side='left', fill='both', expand=True); sb.pack(side='right', fill='y')
        cv.bind_all('<MouseWheel>', lambda e: cv.yview_scroll(-e.delta // 120, 'units') if self.nb.select() == str(self.tab_hints) else None)
        row = tk.Frame(inner, bg=C['bg']); row.pack(fill='x', pady=(0, 6))
        ttk.Label(row, text='Все сразу: ').pack(side='left')
        self.hint_vars = {}
        for m, lab in MODES.items():
            ttk.Button(row, text=lab, command=lambda m=m: self.set_all_hints(m)).pack(side='left', padx=2)
        row = tk.Frame(inner, bg=C['bg']); row.pack(fill='x', pady=(0, 4))
        ttk.Button(row, text='Режимы по умолчанию', command=lambda: (self.s.reset(SECTIONS['hints']), self.rebuild())).pack(side='left')
        ttk.Label(row, text='  ▶ — проверить, как прозвучит подсказка с текущим режимом', style='M.TLabel').pack(side='left')
        sec = None
        for hid, s, name, _, _ in core.HINTS:
            if s != sec:
                sec = s; ttk.Label(inner, text=s, style='H.TLabel').pack(anchor='w', pady=(8, 2))
            r = tk.Frame(inner, bg=C['bg']); r.pack(fill='x', pady=1)
            v = tk.StringVar(value=MODES[self.s['hints'].get(hid, 'off')]); self.hint_vars[hid] = v
            cb = ttk.Combobox(r, state='readonly', width=8, values=list(MODES.values()), textvariable=v); cb.pack(side='left')
            cb.bind('<<ComboboxSelected>>', lambda e, hid=hid: self.set_hint(hid))
            ttk.Button(r, text='▶', width=3, command=lambda hid=hid, name=name: self.test_hint(hid, name)).pack(side='left', padx=(4, 0))
            ttk.Label(r, text=name, wraplength=self.fs(520)).pack(side='left', padx=8)

    def test_hint(self, hid, name):
        """Проверка подсказки: звучит так, как настроено (сигнал, голос или только текст)."""
        mode = self.s['hints'].get(hid, 'off')
        if mode == 'off': self.status.configure(text='Эта подсказка выключена'); return
        self.toast(name); self.status.configure(text=f'Проверка: {MODES[mode].lower()}')
        if mode == 'beep': self.voice.beep(force=True)
        elif mode == 'voice': self.voice.say(name, force=True)

    def set_hint(self, hid):
        m = next(k for k, v in MODES.items() if v == self.hint_vars[hid].get())
        self.s['hints'][hid] = m; self.s.save()
        if self.engine: self.engine.enabled[hid] = m != 'off'

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
        for key, name in (('scoreboard', 'Таблица по линиям, пока зажат Tab'), ('postgame', 'Окно итога после игры')):
            v = tk.BooleanVar(value=self.s[key])
            ttk.Checkbutton(f, text=name, variable=v, command=lambda key=key, v=v: (self.s.__setitem__(key, v.get()), self.s.save())).pack(anchor='w')
        self.h(f, 'Второй монитор')
        ttk.Button(f, text='Открыть дашборд со всеми чемпионами', command=self.open_dash).pack(anchor='w')
        ttk.Button(f, text='Сбросить позиции окон', command=self.reset_layout).pack(anchor='w', pady=6)
        self.reset_btn(f, 'windows', 'Все настройки окон по умолчанию')

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
        for w in list(self.ov.values()) + [self.board]: w.attributes('-alpha', int(v) / 100)

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
        row = tk.Frame(f, bg=C['bg']); row.pack(anchor='w', pady=(6, 0))
        ttk.Button(row, text='▶ Проверить подсказку', style='A.TButton',
                   command=lambda: self.test_hint('gank1', 'Окно ганка через двадцать секунд, поставь вард в реку')).pack(side='left')
        ttk.Label(row, text='  звучит так, как настроено для «Ганк 1» на вкладке «Подсказки»', style='M.TLabel').pack(side='left')
        self.h(f, 'Речь')
        self.slider(f, 'Скорость речи', 'rate', .7, 1.6, lambda x: self.set_voice_param('rate', x), fmt=lambda x: f'{x:.1f}×')
        self.note(f, 'Голоса нейросетевые (Piper), работают без интернета. Дмитрий встроен, остальные скачиваются один раз (~60 МБ). '
                     f"Выключить звук в игре: {self.s['keys']['mute'].upper()}.")
        self.reset_btn(f, 'voice', 'Звук по умолчанию')

    def refresh_voices(self):
        vals = [f"{n}{'' if self.voice.model(v) else ' (скачать)'}" for v, n in VOICES.items()]
        self.voice_cb.configure(values=vals)
        self.voice_var.set(vals[list(VOICES).index(self.s['voice'])] if self.s['voice'] in VOICES else vals[0])

    def pick_voice(self):
        v = list(VOICES)[self.voice_cb.current()]
        if self.voice.model(v):
            self.s['voice'] = self.voice.voice = v; self.s.save(); self.voice_msg.configure(text=f'Голос: {VOICES[v]}'); return
        def job():
            try:
                self.voice.download(v, lambda p: self.root.after(0, lambda: self.voice_msg.configure(text=f'Скачиваю {VOICES[v]}: {p * 100:.0f}%')))
                def done():
                    self.s['voice'] = self.voice.voice = v; self.s.save(); self.refresh_voices()
                    self.voice_msg.configure(text=f'Голос {VOICES[v]} установлен')
                self.root.after(0, done)
            except Exception as e:
                self.root.after(0, lambda: self.voice_msg.configure(text=f'Не скачалось: {e}'))
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
