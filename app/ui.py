# Окна LoL Helper: панель управления, виджеты поверх игры, дашборд на втором мониторе, таблица по Tab, итог игры.
import json, os, queue, threading, time, urllib.request
import tkinter as tk
from tkinter import ttk

import core, lcu
from voice import Voice, VOICES

IS_WIN = os.name == 'nt'
if IS_WIN:
    import ctypes
    U32 = ctypes.windll.user32

C = {'bg': '#10141a', 'panel': '#181e26', 'line': '#2a323d', 'fg': '#e9e4d8', 'mute': '#8d96a3', 'gold': '#c8aa6e',
     'good': '#5cc98a', 'bad': '#e8665f', 'blue': '#5aa9e6', 'red': '#e0605a'}
MODES = {'off': 'Выкл', 'text': 'Текст', 'beep': 'Сигнал', 'voice': 'Голос'}
WIDGETS = {'hints': 'Подсказки', 'cs': 'Фарм и норма', 'lane': 'Оппонент на линии', 'timers': 'Таймеры объектов'}
RAW = 'https://raw.githubusercontent.com/Halches/Lol-stat/main/'


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
    'alpha': 88, 'scale': 100, 'layout': {},
    'keys': {'mute': 'ctrl+shift+m', 'hide': 'ctrl+shift+h', 'scoreboard': 'tab', 'drag': 'alt'},
    'voice': 'dmitri', 'volume': 80, 'rate': 1.0,
    'obj': dict(core.OBJ), 'who': '', 'auto_update': True,
}


class Settings(dict):
    def __init__(self, home):
        super().__init__()
        self.path = os.path.join(home, 'settings.json')
        try: saved = json.load(open(self.path, encoding='utf-8'))
        except Exception: saved = {}
        for k, v in DEFAULTS.items():
            self[k] = ({**v, **saved.get(k, {})} if isinstance(v, dict) else saved.get(k, v))

    def save(self):
        tmp = self.path + '.tmp'
        json.dump(dict(self), open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        os.replace(tmp, self.path)


# ---------------- Виджеты поверх игры ----------------

class Overlay(tk.Toplevel):
    def __init__(self, app, key, default_xy):
        super().__init__(app.root)
        self.app, self.key = app, key
        self.overrideredirect(True)
        self.attributes('-topmost', True)
        self.configure(bg=C['bg'], highlightthickness=1, highlightbackground=C['line'])
        self.body = tk.Frame(self, bg=C['bg'], padx=10, pady=6)
        self.body.pack(fill='both', expand=True)
        x, y = app.layout().get(key, default_xy)
        self.geometry(f'+{int(x)}+{int(y)}')
        self.update_idletasks()
        click_through(self, True)
        self.attributes('-alpha', app.s['alpha'] / 100)
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
        self.configure(highlightbackground=C['gold'] if on else C['line'])

    def lbl(self, parent=None, size=11, color='fg', bold=False):
        l = tk.Label(parent or self.body, bg=C['bg'], fg=C[color], font=('Segoe UI', self.app.fs(size), 'bold' if bold else 'normal'),
                     justify='left', anchor='w')
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
        self.a.configure(text=f"{me['cs']} CS · {csm:.1f}/мин", fg=C[col])
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
            self.a.configure(text='Оппонент не определён', fg=C['mute']); self.b.configure(text=''); return
        d, o, me = g.lane_diff(), g.opp, g.me
        self.a.configure(text=f"{self.app.data.cn(o['c'])}: {d:+.0f} золота", fg=C['good' if d > 300 else 'bad' if d < -300 else 'fg'])
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
        self.grid_rows = []
        self.title = self.lbl(size=12, color='gold', bold=True); self.title.pack(anchor='w')
        self.tbl = tk.Frame(self.body, bg=C['bg']); self.tbl.pack()
        self.withdraw()

    def show(self, g):
        for w in self.tbl.winfo_children(): w.destroy()
        d = self.app.data
        self.title.configure(text=f'{core.mmss(g.t)} · золото в предметах команды {g.gold_diff():+.0f}')
        heads = ['', 'Мы', 'ур', 'CS', 'К/С/П', 'золото', 'разница', 'золото', 'К/С/П', 'CS', 'ур', 'Враги']
        for j, h in enumerate(heads):
            tk.Label(self.tbl, text=h, bg=C['bg'], fg=C['mute'], font=('Segoe UI', self.app.fs(9))).grid(row=0, column=j, padx=6)
        for i, r in enumerate(core.ROLES, 1):
            a = next((p for p in g.allies if p['pos'] == r), None)
            e = next((p for p in g.enemies if p['pos'] == r), None)
            if not a and not e: continue
            diff = (a['igold'] - e['igold']) if a and e else 0
            vals = [core.ROLE_RU[r],
                    d.cn(a['c']) if a else '', a and a['lvl'], a and a['cs'], a and f"{a['k']}/{a['d']}/{a['a']}", a and a['igold'],
                    f'{diff:+.0f}',
                    e and e['igold'], e and f"{e['k']}/{e['d']}/{e['a']}", e and e['cs'], e and e['lvl'], d.cn(e['c']) if e else '']
            for j, v in enumerate(vals):
                col = C['gold'] if a is g.me and j in (1,) else C['good'] if j == 6 and diff > 300 else C['bad'] if j == 6 and diff < -300 else C['fg']
                tk.Label(self.tbl, text='' if v in (None, False) else v, bg=C['bg'], fg=col,
                         font=('Segoe UI', self.app.fs(11), 'bold' if j in (1, 6, 11) else 'normal')).grid(row=i, column=j, padx=6, sticky='w')


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
            self.geometry(f'1280x760+{x}+60')
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.bind('<Configure>', self._moved)
        self.head = tk.Label(self, bg=C['bg'], fg=C['gold'], font=('Segoe UI', app.fs(16), 'bold'), anchor='w')
        self.head.pack(fill='x', padx=14, pady=(10, 0))
        self.sub = tk.Label(self, bg=C['bg'], fg=C['mute'], font=('Segoe UI', app.fs(11)), anchor='w')
        self.sub.pack(fill='x', padx=14)
        self.teams = tk.Frame(self, bg=C['bg']); self.teams.pack(fill='both', expand=True, padx=10, pady=8)
        self.cols = [tk.Frame(self.teams, bg=C['bg']) for _ in range(2)]
        for i, f in enumerate(self.cols): f.grid(row=0, column=i, sticky='nsew', padx=4); self.teams.columnconfigure(i, weight=1)
        tk.Label(self, text='Подсказки за игру', bg=C['bg'], fg=C['mute'], font=('Segoe UI', app.fs(10)), anchor='w').pack(fill='x', padx=14)
        self.log = tk.Text(self, height=7, bg=C['panel'], fg=C['fg'], relief='flat', font=('Segoe UI', app.fs(10)), wrap='word')
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
        self.app.panel_sync()

    def add_log(self, t, text):
        self.log.insert('end', f'{core.mmss(t)}  {text}\n'); self.log.see('end')

    def card(self, col, p):
        key = (col, p['riot'])
        if key not in self.cards:
            f = tk.Frame(self.cols[col], bg=C['panel'], padx=10, pady=6, highlightthickness=1, highlightbackground=C['line'])
            f.pack(fill='x', pady=3)
            ls = [tk.Label(f, bg=C['panel'], anchor='w', justify='left') for _ in range(4)]
            fs = self.app.fs
            ls[0].configure(font=('Segoe UI', fs(13), 'bold')); ls[1].configure(font=('Segoe UI', fs(10)), fg=C['fg'])
            ls[2].configure(font=('Segoe UI', fs(9)), fg=C['mute']); ls[3].configure(font=('Segoe UI', fs(9)), fg=C['mute'])
            for l in ls: l.pack(fill='x')
            self.cards[key] = (f, ls)
        return self.cards[key]

    def show(self, g, scout):
        d = self.app.data
        diff = g.gold_diff()
        self.head.configure(text=f'{core.mmss(g.t)} · золото в предметах {diff:+.0f}', fg=C['good' if diff > 1000 else 'bad' if diff < -1000 else 'gold'])
        ob = g.objectives()
        tm = [f"{n}: {core.mmss(ob[k] - g.t)}" for k, n in (('dragon', ob.get('dragon_name')), ('grubs', 'Личинки'), ('herald', 'Герольд'), ('baron', 'Барон')) if k in ob and ob[k] > g.t]
        j = g.ejg
        self.sub.configure(text='   '.join(tm) + (f'   · лесник врагов: {d.cn(j["c"])}' if j else ''))
        order = {r: i for i, r in enumerate(core.ROLES)}
        for col, team in enumerate((g.allies, g.enemies)):
            for p in sorted(team, key=lambda p: order.get(p['pos'], 9)):
                f, ls = self.card(col, p)
                me = p is g.me
                f.configure(highlightbackground=C['gold'] if me else C['line'])
                ls[0].configure(text=f"{d.cn(p['c'])}  ·  {p['lvl']} ур.  ·  {p['k']}/{p['d']}/{p['a']}" + ('  · мёртв ' + core.mmss(p['respawn']) if p['dead'] else ''),
                                fg=C['blue'] if col == 0 else C['red'])
                ls[1].configure(text=f"{core.ROLE_RU.get(p['pos'], '')}  ·  CS {p['cs']} ({p['cs'] / max(1, g.t / 60):.1f}/мин)  ·  предметы {p['igold']:.0f}  ·  обзор {p['ward']:.0f}")
                its = [d.iname(i) for i in p['items'] if d.items.get(str(i), {}).get('g', 0) >= 900]
                ls[2].configure(text=', '.join(its) or 'без крупных предметов')
                ls[3].configure(text=scout.get(p['c'], '') if col == 1 else '')

    def reset(self):
        for f, _ in self.cards.values(): f.destroy()
        self.cards = {}
        self.log.delete('1.0', 'end')
        self.head.configure(text='Ждём начала игры', fg=C['gold']); self.sub.configure(text='')


def scout_text(p):
    """Строка разведки из data/live.json сайта (ранг, серия, игры на чемпионе)."""
    out = []
    if p.get('rk'): out.append(p['rk'])
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
    fs = app.fs
    head = {'Win': 'Победа', 'Lose': 'Поражение'}.get(result, 'Игра окончена')
    tk.Label(w, text=f"{head} · {app.data.cn(res['me']['c'])} · {res['min']:.0f} мин", bg=C['bg'], fg=C['gold'], font=('Segoe UI', fs(16), 'bold')).pack(anchor='w')
    for name, v, th, ok, dec in res['goals']:
        tk.Label(w, text=f"{'✓' if ok else '✗'}  {name}: {v:.{dec}f} (цель {th})", bg=C['bg'], fg=C['good' if ok else 'bad'],
                 font=('Segoe UI', fs(12))).pack(anchor='w')
    if res['main']:
        tk.Label(w, text=f"Главное на следующую игру: {res['main'].lower()}", bg=C['bg'], fg=C['fg'], font=('Segoe UI', fs(12), 'bold'),
                 wraplength=fs(460), justify='left').pack(anchor='w', pady=(10, 0))
    tk.Label(w, text=f"Подсказок за игру: {len(res['hints'])}", bg=C['bg'], fg=C['mute'], font=('Segoe UI', fs(10))).pack(anchor='w', pady=(6, 0))
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
        self.voice.voice, self.voice.volume, self.voice.rate = self.s['voice'], self.s['volume'], self.s['rate']
        self.q = queue.Queue()
        self.hidden = False
        self.account = None
        self.player = None
        self.engine = None
        self.draft = None
        self.imported = None
        self.scout = {}
        self.last_game = None
        self.result = None
        self.keys_prev = {}
        self.root = tk.Tk()
        self.root.title(f'LoL Helper {version}')
        self.root.configure(bg=C['bg'])
        self.root.geometry('720x620')
        self.style()
        self.set_who(self.s['who'] or 'halch')
        self.build_panel()
        sig, (pw, ph), _ = screens()
        self.ov = {'hints': HintsOverlay(self, (40, int(ph * .32))), 'cs': CsOverlay(self, (pw - 380, 70)),
                   'lane': LaneOverlay(self, (pw - 380, 140)), 'timers': TimersOverlay(self, (pw - 380, 210))}
        self.board = Scoreboard(self, (int(pw * .25), int(ph * .2)))
        self.dash = Dashboard(self) if self.s['dashboard'] else None
        self.apply_visibility()
        threading.Thread(target=self.poll, daemon=True).start()
        self.root.after(300, self.drain)
        self.root.after(40, self.keys)
        self.root.after(1000, self.tick_ui)

    # --- общее
    def fs(self, n): return max(7, round(n * self.s['scale'] / 100))

    def layout(self):
        return self.s['layout'].setdefault(screens()[0], {})

    def style(self):
        st = ttk.Style(self.root)
        try: st.theme_use('clam')
        except Exception: pass
        st.configure('.', background=C['bg'], foreground=C['fg'], fieldbackground=C['panel'], font=('Segoe UI', 10))
        st.configure('TNotebook', background=C['bg'], borderwidth=0)
        st.configure('TNotebook.Tab', background=C['panel'], foreground=C['mute'], padding=(12, 5))
        st.map('TNotebook.Tab', background=[('selected', C['line'])], foreground=[('selected', C['gold'])])
        st.configure('TButton', background=C['line'], foreground=C['fg'], padding=(10, 4))
        st.map('TButton', background=[('active', C['gold'])], foreground=[('active', C['bg'])])
        st.configure('TCheckbutton', background=C['bg'], foreground=C['fg'])
        st.configure('TCombobox', fieldbackground=C['panel'], background=C['line'], foreground=C['fg'])
        st.map('TCombobox', fieldbackground=[('readonly', C['panel'])], foreground=[('readonly', C['fg'])],
               selectbackground=[('readonly', C['panel'])], selectforeground=[('readonly', C['fg'])])
        self.root.option_add('*TCombobox*Listbox.background', C['panel'])
        self.root.option_add('*TCombobox*Listbox.foreground', C['fg'])
        st.configure('TEntry', fieldbackground=C['panel'], foreground=C['fg'], insertcolor=C['fg'])
        st.configure('H.TLabel', foreground=C['gold'], font=('Segoe UI', 12, 'bold'))
        st.configure('M.TLabel', foreground=C['mute'])

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
                    in_game = True
                    g = core.Game(raw, self.data)
                    if self.engine is None: self.new_engine()
                    hints = self.engine.tick(g)
                    res = next((e.get('Result') for e in g.events if e.get('EventName') == 'GameEnd'), None)
                    if now - last_scout > 90:
                        last_scout = now
                        self.scout = self.fetch_scout(g)
                    self.q.put(('game', g, hints, res))
                else:
                    if in_game:
                        in_game = False
                        self.q.put(('end', None, None, None))
                    if now - last_me > 60:
                        last_me = now
                        me = self.client.me()
                        if me: self.q.put(('me', me, None, None))
                    if now - last_lcu > 2:
                        last_lcu = now
                        if self.client.phase() == 'ChampSelect':
                            sess = self.client.champ_select()
                            if sess: self.q.put(('draft', core.parse_champ_select(sess, self.data), None, None))
                        elif self.draft is not None:
                            self.q.put(('draft', None, None, None))
            except Exception as e:
                self.q.put(('error', str(e), None, None))
            time.sleep(1)

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
        if me['riot'] == (self.account or {}).get('riot'): self.account = me; return
        self.account = me
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
            try: self.dash.show(g, self.scout)
            except Exception: pass
        self.status.configure(text=f'Игра: {core.mmss(g.t)} · {self.data.cn(g.me["c"]) if g.me else ""}')

    def on_end(self):
        g = self.last_game
        if g and self.engine and self.s['postgame'] and g.t > 300 and self.s['hints'].get('postgame') != 'off':
            res = core.postgame(self.engine, g, self.player)
            if res: show_postgame(self, res, self.result)
        self.last_game, self.result, self.engine, self.scout = None, None, None, {}
        if getattr(self, 'pending_data', None): self.reload_data(self.pending_data)
        self.apply_visibility()
        self.board.withdraw()
        self.status.configure(text='Игра закончилась')

    def on_draft(self, cs):
        self.draft = cs
        if cs is None:
            self.draft_text.configure(text='Драфт появится, когда начнётся выбор чемпионов'); self.imported = None; return
        self.nb.select(self.tab_draft) if not getattr(self, '_draft_shown', False) else None
        self._draft_shown = True
        p, d = self.player, self.data
        if not p:
            self.draft_text.configure(text='Аккаунта нет в статистике сайта: выбери игрока на вкладке «Статус»'); return
        role = cs['role'] or 'TOP'
        r = core.draft_suggest(p, role, cs['enemies'], cs['unavailable'])
        lines = [f'Роль: {core.ROLE_RU[role]}' + (f' · вероятный оппонент: {d.cn(r["opp"])}' if r['opp'] else ''), '', 'Кого взять:']
        lines += [f'  {i}. {x["name"]} — {x["why"]}' for i, x in enumerate(r['picks'], 1)] or ['  нет данных']
        bans = core.ban_suggest(p, cs['unavailable'])
        if bans: lines += ['', 'Кого банить (твои худшие оппоненты на линии):'] + [f'  {d.cn(c)} — {w}–{n - w}' for c, n, w in bans]
        if cs['enemies']:
            lines += ['', 'Враги: ' + ', '.join(f'{d.cn(c)} ({core.ROLE_RU.get(r["roles"].get(c, ""), "?")})' for c in cs['enemies'])]
        me = cs['me']
        if me:
            lines += ['', f'Ты: {d.cn(me)}']
            if r['opp']:
                v = p.vs(me, r['opp'])
                lines.append(f'  против {d.cn(r["opp"])}: ' + (f'{v["w"]}–{v["n"] - v["w"]}' if v['n'] else 'ещё не встречались'))
            ru = p.best_runes(me)
            if ru: lines.append(f'  лучшие руны: из {ru["n"]} игр, {round(ru["w"] / ru["n"] * 100)}% побед')
            b = p.best_build(me)
            if b: lines.append('  сборка: ' + ' → '.join(d.iname(i) for i in b))
            if self.s['auto_import'] and cs['locked'] and self.imported != me: self.do_import()
        self.draft_text.configure(text='\n'.join(lines))

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
        tk.Label(top, text='LoL Helper', bg=C['bg'], fg=C['gold'], font=('Segoe UI', 16, 'bold')).pack(side='left')
        self.status = tk.Label(top, text='Ищу клиент League of Legends…', bg=C['bg'], fg=C['mute'], font=('Segoe UI', 10))
        self.status.pack(side='right')
        self.nb = ttk.Notebook(r); self.nb.pack(fill='both', expand=True, padx=8, pady=8)
        self.tab_status = self.page('Статус'); self.tab_draft = self.page('Драфт')
        self.tab_hints = self.page('Подсказки'); self.tab_win = self.page('Окна')
        self.tab_voice = self.page('Голос'); self.tab_keys = self.page('Клавиши')
        self.tab_time = self.page('Таймеры'); self.tab_upd = self.page('Обновления')
        self.build_status(); self.build_draft(); self.build_hints(); self.build_windows()
        self.build_voice(); self.build_keys(); self.build_timers(); self.build_updates()

    def page(self, name):
        f = tk.Frame(self.nb, bg=C['bg'], padx=14, pady=10); self.nb.add(f, text=name); return f

    def h(self, parent, text): ttk.Label(parent, text=text, style='H.TLabel').pack(anchor='w', pady=(8, 4))

    def note(self, parent, text): ttk.Label(parent, text=text, style='M.TLabel', wraplength=640, justify='left').pack(anchor='w')

    def build_status(self):
        f = self.tab_status
        self.h(f, 'Аккаунт')
        self.acc_lbl = ttk.Label(f, text=''); self.acc_lbl.pack(anchor='w')
        row = tk.Frame(f, bg=C['bg']); row.pack(anchor='w', pady=6)
        ttk.Label(row, text='Статистика игрока: ').pack(side='left')
        self.who_var = tk.StringVar()
        names = {w: p['riot'] for w, p in self.data.d['players'].items()}
        cb = ttk.Combobox(row, state='readonly', width=24, values=list(names.values()), textvariable=self.who_var); cb.pack(side='left')
        def pick(_):
            who = next(w for w, n in names.items() if n == self.who_var.get())
            self.s['who'] = who; self.s.save(); self.set_who(who)
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
        a = self.account
        self.acc_lbl.configure(text=f"В клиенте: {a['riot']}" if a else 'Клиент не найден: запусти League of Legends')
        if self.who: self.who_var.set(self.data.d['players'][self.who]['riot'])
        g = sum(len(p['g']) for p in self.data.d['players'].values())
        self.data_lbl.configure(text=f"Статистика от {self.data.d['t']} · патч {self.data.d['patch']} · {g} игр")

    def open_dash(self):
        if not self.dash:
            self.s['dashboard'] = True; self.s.save(); self.dash = Dashboard(self)
        else: self.dash.deiconify(); self.dash.lift()

    def build_draft(self):
        f = self.tab_draft
        self.draft_text = tk.Label(f, text='Драфт появится, когда начнётся выбор чемпионов', bg=C['bg'], fg=C['fg'],
                                   font=('Segoe UI', 11), justify='left', anchor='nw', wraplength=660)
        self.draft_text.pack(fill='both', expand=True, anchor='nw')
        row = tk.Frame(f, bg=C['bg']); row.pack(fill='x', pady=6)
        ttk.Button(row, text='Импортировать руны и сборку в клиент', command=self.do_import).pack(side='left')
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
        sec = None
        for hid, s, name, _, _ in core.HINTS:
            if s != sec:
                sec = s; ttk.Label(inner, text=s, style='H.TLabel').pack(anchor='w', pady=(8, 2))
            r = tk.Frame(inner, bg=C['bg']); r.pack(fill='x', pady=1)
            v = tk.StringVar(value=MODES[self.s['hints'].get(hid, 'off')]); self.hint_vars[hid] = v
            cb = ttk.Combobox(r, state='readonly', width=8, values=list(MODES.values()), textvariable=v); cb.pack(side='left')
            cb.bind('<<ComboboxSelected>>', lambda e, hid=hid: self.set_hint(hid))
            ttk.Label(r, text=name, wraplength=540).pack(side='left', padx=8)

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
        self.h(f, 'Вид')
        for key, name, lo, hi in (('alpha', 'Непрозрачность виджетов, %', 40, 100), ('scale', 'Размер текста, %', 70, 180)):
            r = tk.Frame(f, bg=C['bg']); r.pack(anchor='w', fill='x')
            ttk.Label(r, text=name, width=28).pack(side='left')
            v = tk.IntVar(value=self.s[key])
            sc = ttk.Scale(r, from_=lo, to=hi, variable=v, length=260)
            sc.pack(side='left')
            sc.configure(command=lambda _, key=key, v=v: self.set_look(key, v.get()))
        self.note(f, 'Размер текста применится после перезапуска.')
        self.h(f, 'Второй монитор')
        ttk.Button(f, text='Открыть дашборд со всеми чемпионами', command=self.open_dash).pack(anchor='w')
        ttk.Button(f, text='Сбросить позиции окон', command=self.reset_layout).pack(anchor='w', pady=6)

    def toggle_widget(self, k):
        self.s['widgets'][k] = self.w_vars[k].get(); self.s.save(); self.apply_visibility()

    def set_look(self, key, v):
        self.s[key] = int(v); self.s.save()
        if key == 'alpha':
            for w in self.ov.values(): w.attributes('-alpha', int(v) / 100)

    def reset_layout(self):
        self.s['layout'].pop(screens()[0], None); self.s.save()
        self.toast('Позиции сброшены: перезапусти программу')

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
        for key, name, lo, hi in (('volume', 'Громкость', 10, 100), ('rate', 'Скорость речи', .7, 1.6)):
            row = tk.Frame(f, bg=C['bg']); row.pack(anchor='w', pady=2)
            ttk.Label(row, text=name, width=16).pack(side='left')
            v = tk.DoubleVar(value=self.s[key])
            ttk.Scale(row, from_=lo, to=hi, variable=v, length=260, command=lambda _, key=key, v=v: self.set_voice_param(key, v.get())).pack(side='left')
        self.note(f, 'Голоса нейросетевые (Piper), работают без интернета. Дмитрий встроен, остальные скачиваются один раз (~60 МБ). '
                     f"Выключить звук в игре: {self.s['keys']['mute'].upper()}.")

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
        self.s[key] = v; setattr(self.voice, key, v); self.s.save()

    def build_keys(self):
        f = self.tab_keys
        self.h(f, 'Горячие клавиши')
        self.key_lbls = {}
        for key, name in (('mute', 'Выключить / включить звук'), ('hide', 'Скрыть / показать виджеты'),
                          ('scoreboard', 'Таблица по линиям (держать)'), ('drag', 'Двигать виджеты мышью (держать)')):
            r = tk.Frame(f, bg=C['bg']); r.pack(anchor='w', pady=3, fill='x')
            ttk.Label(r, text=name, width=34).pack(side='left')
            l = ttk.Label(r, text=self.s['keys'][key].upper(), width=18, foreground=C['gold']); l.pack(side='left')
            self.key_lbls[key] = l
            ttk.Button(r, text='Изменить', command=lambda key=key: self.capture(key)).pack(side='left')
        self.note(f, 'Нажми «Изменить», затем нужное сочетание. Работает, пока окно программы активно. Esc — отмена.')

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
        ttk.Button(f, text='Вернуть значения по умолчанию', command=self.reset_obj).pack(anchor='w', pady=10)

    def set_obj(self, k, v):
        try:
            m, s = v.get().split(':'); sec = int(m) * 60 + int(s)
        except Exception:
            v.set(core.mmss(self.s['obj'][k])); return
        self.s['obj'][k] = core.OBJ[k] = sec; self.s.save()

    def reset_obj(self):
        self.s['obj'] = dict(DEFAULTS['obj']); core.OBJ.update(self.s['obj']); self.s.save()
        self.toast('Таймеры сброшены: перезапусти программу, чтобы обновить поля')

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
