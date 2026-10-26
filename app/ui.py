# Окна LoL Helper: панель управления, виджеты поверх игры, дашборд на втором мониторе, таблица по Tab, итог игры.
# Внешний вид (тема, акцент, шрифт, иконки) настраивается на вкладке «Вид» и применяется сразу: окна пересобираются.
import base64, io, json, os, platform, queue, subprocess, sys, threading, time, traceback, urllib.request, webbrowser
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import core, lcu, phone

RELEASES = 'https://github.com/Halches/Lol-stat/releases'   # список всех версий с изменениями
from voice import Voice, VOICES, SOUNDS

try:
    from PIL import Image, ImageOps, ImageTk
    import render
except Exception:      # без Pillow программа работает, но без картинок
    Image = None

IS_WIN = os.name == 'nt'
if IS_WIN:
    import ctypes, ctypes.wintypes
    U32 = ctypes.windll.user32

THEMES = {   # три палитры дизайна 26.10, у каждой ночь и день; ключи старых тем ведут на новые (Settings)
    'lol': ('Клиент LoL · ночь', {'bg': '#06101c', 'panel': '#0b1a2a', 'line': '#1f3347', 'fg': '#e8dfcc', 'mute': '#8c9bab', 'gold': '#c8aa6e', 'good': '#0ac8b9', 'bad': '#e2584e', 'blue': '#4fb3ff', 'red': '#e2584e', 'deep': '#081422', 'raise': '#14283c', 'edge': '#0b1a2a', 'glow': '#0f2236', 'tag_g': '#0b3641', 'tag_r': '#2d2430', 'tag_y': '#2e302d', 'good2': '#3bd3c7', 'bad2': '#e87971', 'warn': '#e8a33d', 'red2': '#e87971', 'blue2': '#72c2ff', 'on_gold': '#06101c', 'dark': True}),
    'lol_day': ('Клиент LoL · день', {'bg': '#eef1f5', 'panel': '#ffffff', 'line': '#d3dae3', 'fg': '#0d1b2a', 'mute': '#56657a', 'gold': '#8a6a2b', 'good': '#0b8f88', 'bad': '#b8433b', 'blue': '#2f7fd0', 'red': '#b8433b', 'deep': '#f6f7fa', 'raise': '#e3e9f0', 'edge': '#ffffff', 'glow': '#ffffff', 'tag_g': '#d8edec', 'tag_r': '#f4e1e0', 'tag_y': '#f4e8d9', 'good2': '#0b8f88', 'bad2': '#b8433b', 'warn': '#b86e12', 'red2': '#b8433b', 'blue2': '#2f7fd0', 'on_gold': '#eef1f5', 'dark': False}),
    'pilt': ('Пилтовер · ночь', {'bg': '#0d0b1c', 'panel': '#151230', 'line': '#2c2856', 'fg': '#ece7f6', 'mute': '#9b94b8', 'gold': '#e2c27a', 'good': '#4fb3ff', 'bad': '#ff5d73', 'blue': '#4fb3ff', 'red': '#ff5d73', 'deep': '#110e25', 'raise': '#211d45', 'edge': '#151230', 'glow': '#1d1a3d', 'tag_g': '#1e2c51', 'tag_r': '#3a1e3b', 'tag_y': '#382d34', 'good2': '#72c2ff', 'bad2': '#ff7d8f', 'warn': '#f2b84b', 'red2': '#ff7d8f', 'blue2': '#72c2ff', 'on_gold': '#0d0b1c', 'dark': True}),
    'pilt_day': ('Пилтовер · день', {'bg': '#f2f0f8', 'panel': '#ffffff', 'line': '#d4cfe6', 'fg': '#16122e', 'mute': '#5f5880', 'gold': '#86662a', 'good': '#1f6fc0', 'bad': '#c2364c', 'blue': '#1f6fc0', 'red': '#c2364c', 'deep': '#f8f7fb', 'raise': '#e7e3f3', 'edge': '#ffffff', 'glow': '#ffffff', 'tag_g': '#dbe8f5', 'tag_r': '#f5dfe2', 'tag_y': '#f4e8d9', 'good2': '#1f6fc0', 'bad2': '#c2364c', 'warn': '#b86e12', 'red2': '#c2364c', 'blue2': '#1f6fc0', 'on_gold': '#f2f0f8', 'dark': False}),
    'dgold': ('Тёмное золото · ночь', {'bg': '#0e0e0f', 'panel': '#171717', 'line': '#2e2b27', 'fg': '#f0e9db', 'mute': '#9d978b', 'gold': '#d6ab52', 'good': '#4cc38a', 'bad': '#e5604f', 'blue': '#5aa9e6', 'red': '#e5604f', 'deep': '#121213', 'raise': '#211f1c', 'edge': '#171717', 'glow': '#1d1b18', 'tag_g': '#1f3329', 'tag_r': '#382320', 'tag_y': '#382d1d', 'good2': '#70cfa1', 'bad2': '#ea8072', 'warn': '#e8a33d', 'red2': '#ea8072', 'blue2': '#7bbaeb', 'on_gold': '#0e0e0f', 'dark': True}),
    'dgold_day': ('Тёмное золото · день', {'bg': '#f4f2ee', 'panel': '#ffffff', 'line': '#dcd6cb', 'fg': '#1c1a17', 'mute': '#6b665c', 'gold': '#8a6420', 'good': '#1f8a5b', 'bad': '#b9442f', 'blue': '#2f7fd0', 'red': '#b9442f', 'deep': '#f9f8f6', 'raise': '#ebe7df', 'edge': '#ffffff', 'glow': '#ffffff', 'tag_g': '#dbece5', 'tag_r': '#f4e1de', 'tag_y': '#f4e8d9', 'good2': '#1f8a5b', 'bad2': '#b9442f', 'warn': '#b86e12', 'red2': '#b9442f', 'blue2': '#2f7fd0', 'on_gold': '#f4f2ee', 'dark': False}),
}
OLD_THEMES = {'hex2': 'lol', 'hextech': 'lol', 'night': 'dgold', 'void': 'pilt', 'light': 'lol_day'}
ACCENTS = {'theme': 'Как в теме', '#c8aa6e': 'Золото', '#0ac8b9': 'Бирюза', '#4aa3ff': 'Синий', '#b48cff': 'Фиолетовый',
           '#ff7a59': 'Оранжевый', '#ff6b81': 'Розовый', '#5cc98a': 'Зелёный'}
FONTS = ['Golos Text', 'Segoe UI', 'Bahnschrift', 'Calibri', 'Trebuchet MS', 'Verdana', 'Consolas']
C = dict(THEMES['lol'][1])
F = {'font': 'Golos Text', 'num': 'Fira Sans Condensed Medium', 'numb': 'Fira Sans Condensed SemiBold', 'head': 'Forum'}
KEY = '#010203'   # цвет-ключ для виджетов без фона

MODES = {'off': 'Выкл', 'text': 'Текст', 'beep': 'Сигнал', 'voice': 'Голос'}
WIDGETS = {'hints': 'Подсказки', 'perf': 'Показатели (CS, золото, KDA…)', 'lane': 'Оппонент на линии', 'gold': 'Золото по линиям',
           'item': 'Золото до предмета', 'timers': 'Таймеры объектов', 'arena': 'Арена: счёт и золото'}
SHOW = {'portraits': 'Портреты чемпионов', 'items': 'Иконки предметов (иначе названия)', 'ranks': 'Эмблемы и звания',
        'spells': 'Заклинания призывателя', 'runes': 'Ключевые руны', 'scout': 'Разведка врагов (серия, игры на чемпионе)'}
RAW = 'https://raw.githubusercontent.com/Halches/Lol-stat/main/'
RIOT_NOTE = ("LoL Helper isn't endorsed by Riot Games and doesn't reflect the views or opinions of Riot Games or anyone officially involved "
             "in producing or managing Riot Games properties. Riot Games, and all associated properties are trademarks or registered trademarks of Riot Games, Inc.")
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


def game_rect():
    """Клиентская область окна игры на экране (x, y, w, h); без игры — основной экран."""
    if IS_WIN:
        h = U32.FindWindowW(None, 'League of Legends (TM) Client')
        if h:
            r = ctypes.wintypes.RECT(); U32.GetClientRect(h, ctypes.byref(r))
            pt = ctypes.wintypes.POINT(0, 0); U32.ClientToScreen(h, ctypes.byref(pt))
            if r.right > 200 and r.bottom > 200: return pt.x, pt.y, r.right, r.bottom
    _, (pw, ph), _ = screens()
    return 0, 0, pw, ph


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


# ---------------- Журнал ошибок ----------------
# В exe нет консоли, поэтому всё, что ломается, пишется в errors.log в папке программы. Одинаковые ошибки — не чаще раза в минуту.

_LAST_ERR = {}


def log_error(where, e=None):
    try:
        tb = ''.join(traceback.format_exception(type(e), e, e.__traceback__)).strip() if isinstance(e, BaseException) else str(e or '')
        key = (where, tb.splitlines()[-1] if tb else '')
        if time.time() - _LAST_ERR.get(key, 0) < 60: return
        _LAST_ERR[key] = time.time()
        path = os.path.join(app_home(), 'errors.log')
        with open(path, 'a', encoding='utf-8') as f: f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} [{where}] {tb}\n")
        if os.path.getsize(path) > 300_000:   # держим последние ~150 КБ
            txt = open(path, encoding='utf-8', errors='replace').read()
            open(path, 'w', encoding='utf-8').write(txt[-150_000:])
    except Exception:
        pass


def tail(path, n):
    try: return open(path, encoding='utf-8', errors='replace').read().splitlines()[-n:]
    except Exception: return []


DEFAULTS = {
    'hints': {h[0]: h[3] for h in core.HINTS if h[0] not in core.HINT_ROLES},
    'hints_role': {r: {h[0]: h[3] for h in core.HINTS if h[0] in core.HINT_ROLES and r in core.HINT_ROLES[h[0]]} for r in core.ROLES},
    'hint_preset': 'TOP',
    'widgets': {k: True for k in WIDGETS},
    'perf': {'metrics': {'csm': True, 'gpm': True, 'kda': True, 'kp': True, 'vsm': True}, 'layout': 'vertical', 'compare': 'norm'},
    'tab_step': 76, 'tab_pos': {}, 'tab_rect': None,
    'phone': False, 'phone_port': 8765, 'phone_token': '',
    'dashboard': True, 'scoreboard': True, 'postgame': True, 'auto_import': False, 'auto_parts': {'runes': False, 'items': False, 'spells': False}, 'rune_pick': 'pick', 'hint_text': {},
    'theme': 'lol', 'accent': 'theme', 'font': 'Golos Text', 'scale': 100, 'icon': 36, 'alpha': 90, 'widget_bg': 'panel',
    'show': {k: True for k in SHOW},
    'layout': {},
    'keys': {'mute': 'ctrl+shift+m', 'hide': 'ctrl+shift+h', 'scoreboard': 'tab', 'drag': 'alt', },
    'voice': 'dmitri', 'volume': 80, 'rate': 1.0, 'master': 100, 'beep_volume': 70, 'sound': 'bell',
    'obj': dict(core.OBJ), 'who': '', 'auto_update': True,
}
SECTIONS = {   # что сбрасывает кнопка «По умолчанию» в каждом разделе
    'hints': ['hints', 'hints_role'], 'voice': ['voice', 'volume', 'rate', 'master', 'beep_volume', 'sound'],
    'look': ['theme', 'accent', 'font', 'scale', 'icon', 'alpha', 'widget_bg', 'show'],
    'windows': ['widgets', 'perf', 'tab_step', 'tab_pos', 'tab_rect', 'dashboard', 'scoreboard', 'postgame', 'layout'], 'keys': ['keys'], 'obj': ['obj'],
}


class Settings(dict):
    def __init__(self, home):
        super().__init__()
        self.path = os.path.join(home, 'settings.json')
        try: saved = json.load(open(self.path, encoding='utf-8'))
        except Exception: saved = {}
        for k, v in DEFAULTS.items():
            self[k] = ({**v, **saved.get(k, {})} if isinstance(v, dict) else saved.get(k, v))
        if saved.get('auto_import') and 'auto_parts' not in saved:   # раньше была одна галка на всё
            self['auto_parts'] = {'runes': True, 'items': True, 'spells': False}
        if not saved.get('design3'):   # дизайн 26.10: новые темы и шрифты включаются всем один раз
            self['theme'], self['font'], self['accent'], self['design3'] = 'lol', 'Golos Text', 'theme', True
        self['theme'] = OLD_THEMES.get(self['theme'], self['theme'])
        if self['font'] == 'Manrope': self['font'] = 'Golos Text'
        if self['obj'].get('crab') == 210: self['obj']['crab'] = 175   # старое время крабов 3:30 -> 2:55 (патч 26.1)

    def reset(self, keys):
        for k in keys:
            v = DEFAULTS[k]
            self[k] = json.loads(json.dumps(v))
        self.save()

    BACKUP_SKIP = ('phone_token', 'design2', 'design3')   # адрес телефона у каждого свой

    def export(self, version=''):
        """Копия настроек в файл: окна, клавиши, подсказки и их тексты, вид, звук, таймеры."""
        return {'app': 'LoL Helper', 'version': version, 'settings': {k: v for k, v in self.items() if k not in self.BACKUP_SKIP}}

    def load_backup(self, d):
        """Применить копию настроек. Неизвестные ключи пропускаются, недостающие остаются как были. Возвращает число разделов."""
        if not isinstance(d, dict) or d.get('app') != 'LoL Helper' or not isinstance(d.get('settings'), dict):
            raise ValueError('это не файл настроек LoL Helper')
        n = 0
        for k, v in d['settings'].items():
            if k not in DEFAULTS or k in self.BACKUP_SKIP: continue
            dv = DEFAULTS[k]
            if isinstance(dv, dict) != isinstance(v, dict): continue
            self[k] = {**dv, **v} if isinstance(dv, dict) else v
            n += 1
        self.save()
        return n

    def save(self):
        tmp = self.path + '.tmp'
        json.dump(dict(self), open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        os.replace(tmp, self.path)


def apply_theme(s):
    C.clear(); C.update(THEMES.get(OLD_THEMES.get(s['theme'], s['theme']), THEMES['lol'])[1])
    if s['accent'] != 'theme': C['gold'] = s['accent']
    F['font'] = s['font']
    own = s['font'] == 'Golos Text'   # шрифты дизайна: цифры Fira Sans Condensed, заголовки Forum
    F['num'], F['numb'], F['head'] = ('Fira Sans Condensed Medium', 'Fira Sans Condensed SemiBold', 'Forum') if own else (s['font'],) * 3


def load_fonts():
    """Шрифты дизайна (Golos Text, Fira Sans Condensed, Forum) из папки fonts: только для этого процесса, в систему не ставятся."""
    d = os.path.join(bundle_dir(), 'fonts')
    if not os.path.isdir(d): return
    for n in os.listdir(d):
        if not n.endswith('.ttf'): continue
        p = os.path.join(d, n)
        if IS_WIN:
            try: ctypes.windll.gdi32.AddFontResourceExW(p, 0x10, 0)   # FR_PRIVATE
            except Exception: pass


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

    CAPS = {'hints': 'Подсказки', 'perf': 'Стата', 'lane': 'Линия', 'gold': 'Золото по линиям', 'item': 'До предмета', 'timers': 'Таймеры', 'arena': 'Арена'}

    def card(self, accent=None, width=None, title=True):
        return render.Card(C, F['font'], self.app.s['scale'] / 100, plate=self.app.s['widget_bg'] != 'none', accent=accent, width=width,
                           title=self.CAPS.get(self.key) if title else None)

    def put(self, card):
        if Image is None: return
        im = card.render()
        self._ph = ImageTk.PhotoImage(im)
        self.lbl.configure(image=self._ph)
        x, sw = self.winfo_x(), self.winfo_screenwidth()
        if not self._drag and x + im.width > sw: self.geometry(f'+{max(0, sw - im.width)}+{self.winfo_y()}')   # не уезжать за край экрана

    def demo(self):
        """Пример содержимого, чтобы виджет можно было расставить без игры."""
        self.put(self.card().row(('text', WIDGETS.get(self.key, self.key), 'fg', 12, True)).row(('text', 'зажми модификатор и тяни', 'mute', 10, False)))


class HintsOverlay(Overlay):
    def __init__(self, app, xy):
        super().__init__(app, 'hints', xy)
        self.items = []

    def push(self, text, color='fg'):
        g = getattr(self.app, 'last_game', None)
        self.items.append((time.time(), text, color, core.mmss(g.t) if g else '')); self.items = self.items[-4:]

    def show(self, _=None):
        now = time.time()
        self.items = [i for i in self.items if now - i[0] < 14]
        if not self.items:
            if not self.unlocked: self.withdraw()
            return
        c = self.card(accent='warn', width=400)
        f = render.font(F['font'], c.px(13))
        for i, (t, text, color, at) in enumerate(reversed(self.items)):
            new = i == 0
            col = (color if color != 'fg' else 'fg') if new else 'mute'
            for j, ln in enumerate(render.wrap(text, f, c.px(320))):
                c.row(('cell', at if j == 0 else '', 'warn' if new else 'mute', 11, True, 38, 'l'), ('text', ln, col, 13 if new else 12, new), pad=2)
            c.rows[-1] = (c.rows[-1][0], 7)
        self.put(c)
        if not self.app.hidden and self.app.s['widgets'].get('hints'): self.deiconify()


class PerfOverlay(Overlay):
    """Показатели в игре против нормы: CS/мин, золото/мин, KDA, участие в убийствах, обзор/мин."""
    METRICS = {'csm': ('CS/мин', 1), 'gpm': ('Золото/мин', 0), 'kda': ('KDA', 1), 'kp': ('Участие, %', 0), 'vsm': ('Обзор/мин', 2)}

    def demo(self):
        c = self.card(width=0)
        c.row(('cell', '', 'mute', 9, False, 74, 'l'), ('cell', 'СЕЙЧАС', 'mute', 9, True, 56, 'r'), ('cell', 'ТЫ ОБЫЧНО', 'mute', 9, True, 64, 'r'),
              ('cell', 'АЛМАЗ', 'mute', 9, True, 64, 'r'), pad=3)
        for name, v, col, n, u in (('CS/мин', '7,4', 'good', '6,8', '7,1'), ('Золото/мин', '412', 'warn', '398', '425'), ('KDA', '3,2', 'good', '2,9', '2,7'),
                                   ('Участие, %', '48', 'fg', '52', '—'), ('Обзор/мин', '0,62', 'fg', '0,55', '—')):
            c.row(('cell', name, 'mute', 11, False, 74, 'l'), ('cell', v, col, 15, True, 56, 'r'), ('cell', n, 'fg', 12, False, 64, 'r'), ('cell', u, 'fg', 12, False, 64, 'r'), pad=3)
        self.put(c)

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
        vals = self.values(g)
        on = [k for k in self.METRICS if cfg['metrics'].get(k)]
        c = self.card(width=0)
        if cfg['layout'] == 'vertical':
            app = self.app
            norm = app.player.norm(g.me['c'], g.role) if app.player else {}
            up = app.tier_bench(g.me['c'], g.role)
            tier = up['tier'] if up else app.next_tier()[1]
            c.row(('cell', '', 'mute', 9, False, 74, 'l'), ('cell', 'СЕЙЧАС', 'mute', 9, True, 56, 'r'), ('cell', 'ТЫ ОБЫЧНО', 'mute', 9, True, 64, 'r'),
                  ('cell', tier.upper() if tier else 'РАНГ ВЫШЕ', 'mute', 9, True, 64, 'r'), pad=3)
            for k in on:
                name, dec = self.METRICS[k]
                v, n, u = vals[k], norm.get(k), (up or {}).get(k)
                ref = u if u is not None else n
                col = 'fg' if ref is None else 'good' if v >= ref else 'warn'
                f = lambda x: '—' if x is None else f'{x:.{dec}f}'.replace('.', ',')
                c.row(('cell', name, 'mute', 11, False, 74, 'l'), ('cell', f(v), col, 15, True, 56, 'r'), ('cell', f(n), 'fg', 12, False, 64, 'r'),
                      ('cell', f(u), 'fg', 12, False, 64, 'r'), pad=3)
        else:
            ref, title = self.refs(g)
            segs = []
            for k in on:
                name, dec = self.METRICS[k]
                v, r = vals[k], ref.get(k)
                col = 'fg' if not r else 'good' if v >= r else 'warn'
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
        c.row(('text', f'{ours / 1000:.1f}k'.replace('.', ','), 'blue', 11, True), ('bar', ours / max(1, ours + theirs), 'blue', 'red', 110),
              ('text', f'{theirs / 1000:.1f}k'.replace('.', ','), 'red', 11, True))
        c.row(('cell', 'команда', 'mute', 11, False, 70, 'l'), ('cell', f'{diff:+.0f}' if diff else '0', 'good' if diff > 0 else 'bad' if diff < 0 else 'mute', 13, True, 64, 'r'))
        for r in core.ROLES:
            a = next((p for p in g.allies if p['pos'] == r), None)
            e = next((p for p in g.enemies if p['pos'] == r), None)
            if not a or not e: continue
            self.lane_row(c, r, a['igold'] - e['igold'], self.app.pimg('champ', a['c'], .6, gray=a['dead'], ring=C['gold'] if a is g.me else None),
                          self.app.pimg('champ', e['c'], .6, gray=e['dead']))
        self.put(c)

    def lane_row(self, c, role, dd, ia=None, ie=None):
        ri = self.app.role_pil(role, .5)
        col = 'mute' if abs(dd) < 100 else 'good' if dd >= 300 else 'bad' if dd <= -300 else 'fg'
        segs = ([('img', ri)] if ri else [('cell', core.ROLE_RU.get(role, ''), 'gold', 10, False, 18, 'l')]) + ([('img', ia)] if ia else [])
        segs += [('cell', f'{dd:+.0f}' if abs(dd) >= 100 else '0', col, 13, True, 56, 'r')] + ([('img', ie)] if ie else [])
        c.row(*segs, pad=3)

    def demo(self):
        c = self.card()
        c.row(('text', '24,1k', 'blue', 11, True), ('bar', .53, 'blue', 'red', 110), ('text', '21,6k', 'red', 11, True))
        c.row(('cell', 'команда', 'mute', 11, False, 70, 'l'), ('cell', '+2450', 'good', 13, True, 64, 'r'))
        for r, dd in zip(core.ROLES, (850, -320, 0, 1240, -90)): self.lane_row(c, r, dd)
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


class ArenaOverlay(Overlay):
    """Арена: счёт, золото и стоимость предметов, плюс твоё среднее место на этом чемпионе. Урона и места в лобби игра во время матча не отдаёт."""
    def __init__(self, app, xy):
        super().__init__(app, 'arena', xy)

    def show(self, g):
        me = g.me
        if not me: return
        c = self.card()
        c.row(('cell', 'счёт', 'mute', 11, False, 80, 'l'), ('cell', f"{me['k']}/{me['d']}/{me['a']}", 'fg', 15, True, 80, 'r'))
        c.row(('cell', 'золото', 'mute', 11, False, 80, 'l'), ('cell', f'{int(g.gold)}', 'gold' if g.gold >= 1000 else 'fg', 15, True, 80, 'r'))
        c.row(('cell', 'в предметах', 'mute', 11, False, 80, 'l'), ('cell', f"{me['igold']:.0f}", 'fg', 12, False, 80, 'r'))
        st = core.arena_stats(self.app.arena_games(), me['c'])
        if st: c.row(('text', f"на {self.app.data.cn(me['c'])}: среднее место {st['avg']:.1f} за {st['n']} игр".replace('.', ','), 'mute', 10, False))
        self.put(c)

    def demo(self):
        c = self.card()
        c.row(('cell', 'счёт', 'mute', 11, False, 80, 'l'), ('cell', '7/3/5', 'fg', 15, True, 80, 'r'))
        c.row(('cell', 'золото', 'mute', 11, False, 80, 'l'), ('cell', '1350', 'gold', 15, True, 80, 'r'))
        c.row(('cell', 'в предметах', 'mute', 11, False, 80, 'l'), ('cell', '6200', 'fg', 12, False, 80, 'r'))
        self.put(c)


class TimersOverlay(Overlay):
    def __init__(self, app, xy):
        super().__init__(app, 'timers', xy)

    def show(self, g):
        ob, t = g.objectives(), g.t
        rows = []
        if g.role == 'JUNGLE' and t < core.OBJ['crab']: rows.append(('Крабы', core.OBJ['crab'] - t))
        for key, name in (('dragon', ob.get('dragon_name', 'Дракон')), ('grubs', 'Личинки'), ('herald', 'Герольд'), ('baron', 'Барон')):
            if ob.get(key) is not None: rows.append((name, ob[key] - t))
        nc = g.next_cannon()
        self.draw(rows, nc - t if nc else None)

    def draw(self, rows, cannon=None):
        c = self.card()
        for name, left in rows:
            soon = 0 < left <= 60
            c.row(('cell', name, 'fg' if left > 0 else 'mute', 11, False, 110, 'l'),
                  ('cell', core.mmss(left) if left > 0 else 'на карте', 'gold' if soon else 'fg' if left > 0 else 'good', 12, True, 62, 'r'))
        if cannon: c.row(('cell', 'Осадный миньон', 'mute', 10, False, 110, 'l'), ('cell', core.mmss(cannon), 'mute', 11, True, 62, 'r'))
        self.put(c)

    def demo(self):
        self.draw([('Адский дракон', 45), ('Личинки', -1), ('Барон', 412)], 38)


class TabPlates(Overlay):
    """Таблички стоимости предметов у внешних краёв игровой таблицы Tab: союзники слева (стоимость и разница с оппонентом),
    враги справа, над рамкой — итог команд. Таблицу рисует игра; её рамка хранится как [left, top, width, height] в долях
    высоты окна игры (left — от центра окна), поэтому всё идёт за игрой и масштабируется по высоте, в том числе на 21:9.
    В режиме подгонки (Alt) видна золотая пунктирная рамка: края и углы тянутся, внутри — перенос."""

    def __init__(self, app):
        super().__init__(app, 'tab', (0, 0))
        self.withdraw()
        self.data, self.edge = None, None

    def rect(self):
        """Рамка таблицы в долях высоты окна игры. По умолчанию — из старых настроек (место чисел и шаг строк)."""
        r = self.app.s.get('tab_rect')
        if r: return r
        dx, y = self.app.s['tab_pos'].get('tabgold', [-.553, .288])
        return [dx, y, -2 * dx, 5 * self.app.s['tab_step'] / 1080]

    def k(self):
        return game_rect()[3] / 1080 * self.app.s['scale'] / 100

    def geom(self):
        """Рамка таблицы на экране и отступы окна вокруг неё под таблички и итог."""
        gx, gy, gw, gh = game_rect()
        l, t, w, h = self.rect()
        k = self.k()
        side, top = int(122 * k) + 2, int(46 * k)
        return gx + gw / 2 + l * gh, gy + t * gh, w * gh, h * gh, side, top

    def draw(self, rows, top):
        X, Y, W, H, side, tp = self.geom()
        im = render.tab_plates((side, tp, W, H), rows, top, C, self.k(), frame=self.unlocked)
        self._ph = ImageTk.PhotoImage(im)
        self.lbl.configure(image=self._ph)
        self.geometry(f'{im.width}x{im.height}+{int(X - side)}+{int(Y - tp)}')

    def show(self, g):
        rows = []
        for r in core.ROLES:
            a = next((p for p in g.allies if p['pos'] == r), None)
            e = next((p for p in g.enemies if p['pos'] == r), None)
            rows.append(({'v': a['igold'], 'd': a['igold'] - e['igold'] if e else None} if a else None, {'v': e['igold']} if e else None))
        self.data = (rows, (sum(p['igold'] for p in g.allies), sum(p['igold'] for p in g.enemies)))
        self.draw(*self.data)

    def demo(self):
        vals = ((9800, 8950), (7400, 7720), (10300, 10300), (11800, 10560), (5200, 5290))
        rows = [({'v': a, 'd': a - e}, {'v': e}) for a, e in vals]
        self.draw(rows, (sum(a for a, _ in vals), sum(e for _, e in vals)))

    def unlock(self, on):
        self.unlocked = on
        click_through(self, not on)

    def _start(self, e):
        X, Y, W, H, side, tp = self.geom()
        x, y = e.x_root - X, e.y_root - Y
        m = 14
        ed = ('l' if abs(x) < m else 'r' if abs(x - W) < m else '') + ('t' if abs(y) < m else 'b' if abs(y - H) < m else '')
        self.edge = ed or 'move'
        self._drag = (e.x_root, e.y_root, list(self.rect()))

    def _move(self, e):
        if not self._drag: return
        x0, y0, (l, t, w, h) = self._drag
        gh = game_rect()[3] or 1
        dx, dy = (e.x_root - x0) / gh, (e.y_root - y0) / gh
        if self.edge == 'move': l, t = l + dx, t + dy
        else:
            if 'l' in self.edge: l, w = l + dx, w - dx
            if 'r' in self.edge: w = w + dx
            if 't' in self.edge: t, h = t + dy, h - dy
            if 'b' in self.edge: h = h + dy
        self.app.s['tab_rect'] = [round(l, 4), round(t, 4), round(max(.2, w), 4), round(max(.1, h), 4)]
        self.draw(*self.data) if self.data else self.demo()

    def _end(self, e):
        if self._drag:
            self._drag = None
            self.app.s.save()


def no_flicker(win, fn):
    """Пересобрать содержимое окна без мигания. В Windows каждая метка — своё окно и рисуется сразу при создании,
    поэтому на время пересборки окно не рисуется (WM_SETREDRAW), а потом показывается целиком одним кадром."""
    hwnd = None
    if os.name == 'nt':
        try: hwnd = int(win.wm_frame(), 16)
        except Exception: hwnd = None
    if hwnd: U32.SendMessageW(hwnd, 0x000B, 0, 0)
    try:
        fn()
        win.update_idletasks()
    finally:
        if hwnd:
            U32.SendMessageW(hwnd, 0x000B, 1, 0)
            U32.RedrawWindow(hwnd, None, None, 0x0001 | 0x0004 | 0x0080 | 0x0100 | 0x0400)   # INVALIDATE ERASE ALLCHILDREN UPDATENOW FRAME


# ---------------- Дашборд на втором мониторе ----------------
# Во время выбора чемпионов показывает драфт в реальном времени, в игре — карточки всех десяти.

def hist_lines(h):
    """Характеристика игрока на всю ширину карточки: итог последних игр и паттерны (тильт, сильные и слабые стороны)."""
    if not h: return []
    st = h['streak']
    top = [f"{h['w']}–{h['n'] - h['w']} за {h['n']}"]
    if abs(st) >= 2: top.append(f"серия {'+' if st > 0 else '−'}{abs(st)}")
    if h['on']: top.append(f"на чемпионе {h['on']} игр, {round(h['on_w'] / h['on'] * 100)}%")
    elif h['tags'] and 'не играл' in h['tags'][-1]: top.append('новый чемпион')
    if any('почти только' in t for t in h['tags']): top.append('мейн чемпиона')
    top.append(f"KDA {h['kda']}")
    out = [(' · '.join(top), 'fg')]
    if h.get('tilt'): out.append(('Тильт: ' + ', '.join(h['tilt']), 'bad'))
    if h.get('good'): out.append(('Силён: ' + ', '.join(h['good']), 'good'))
    if h.get('bad'): out.append(('Слаб: ' + ', '.join(h['bad']), 'gold'))
    return out


def hist_tags(h):
    """Метки игрока в стиле Porofessor: (текст, вид g|r|y|n) и строка итога последних игр."""
    if not h: return '', []
    st, tags = h['streak'], []
    if any('почти только' in t for t in h['tags']): tags.append(('★ Мейн чемпиона', 'g'))
    elif h['tags'] and 'не играл' in h['tags'][-1]: tags.append(('✦ Новый чемпион', 'y'))
    if st >= 3: tags.append((f'▲ Серия побед: {st}', 'g'))
    elif st <= -3 and not h.get('tilt'): tags.append((f'▼ Серия поражений: {-st}', 'r'))
    for t in h.get('tilt') or []: tags.append(('▼ Тильт: ' + t, 'r'))
    for t in h.get('good') or []: tags.append((t[:1].upper() + t[1:], 'g'))
    for t in h.get('bad') or []: tags.append((t[:1].upper() + t[1:], 'y'))
    top = [f"{h['w']}–{h['n'] - h['w']} за {h['n']}"]
    if h['on']: top.append(f"на чемпионе {h['on']} игр, {round(h['on_w'] / h['on'] * 100)}%")
    top.append(f"KDA {h['kda']}")
    return ' · '.join(top), tags


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
            self.geometry(f'1560x900+{x}+60')
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.bind('<Configure>', self._moved)
        fn = F['font']
        self.head = tk.Label(self, bg=C['bg'], fg=C['gold'], font=(F['head'], app.fs(22)), anchor='w')
        self.head.pack(fill='x', padx=16, pady=(12, 0))
        conf = self.head.configure
        def head(**kw):   # заголовок окна всегда капсом и золотом (Forum)
            if 'text' in kw: kw['text'] = kw['text'].upper()
            kw['fg'] = C['gold']; conf(**kw)
        self.head.configure = head
        self.timer = tk.Label(self, bg=C['bg'], fg=C['fg'], font=(F['numb'], app.fs(22)))   # в драфте: таймер пика справа сверху
        self.deadline = 0
        self.sub = tk.Label(self, bg=C['bg'], fg=C['mute'], font=(fn, app.fs(11)), anchor='w', justify='left')
        self.sub.pack(fill='x', padx=16)
        self.objs = tk.Frame(self, bg=C['bg'])   # в игре: плитки таймеров объектов справа от заголовка
        self.bar = tk.Frame(self, bg=C['bg'])   # в драфте: смена линии и импорт рун/предметов
        # карточки внутри прокручиваемой области: не всё помещается на маленьком мониторе
        self.wrap = tk.Frame(self, bg=C['bg']); self.wrap.pack(fill='both', expand=True, padx=10, pady=8)
        self.cv = tk.Canvas(self.wrap, bg=C['bg'], highlightthickness=0)
        sb = ttk.Scrollbar(self.wrap, orient='vertical', command=self.cv.yview)
        self.body = tk.Frame(self.cv, bg=C['bg'])
        self.body.bind('<Configure>', lambda e: (self.cv.configure(scrollregion=self.cv.bbox('all')),
                                                 sb.pack(side='right', fill='y') if self.body.winfo_reqheight() > self.cv.winfo_height() else sb.pack_forget()))
        win = self.cv.create_window((0, 0), window=self.body, anchor='nw'); self.cv.configure(yscrollcommand=sb.set)
        self.cv.bind('<Configure>', lambda e: self.cv.itemconfigure(win, width=e.width))
        self.cv.pack(side='left', fill='both', expand=True)
        self.low = tk.Frame(self, bg=C['bg'])
        lf = tk.Frame(self.low, bg=C['bg'])
        lf.pack(side='left', fill='both', expand=True, padx=(0, 10))
        self.logl = tk.Label(lf, text='ПОДСКАЗКИ ЗА ИГРУ', bg=C['bg'], fg=C['gold'], font=(F['head'], app.fs(12)), anchor='w'); self.logl.pack(fill='x', pady=(0, 4))
        self.log = tk.Frame(lf, bg=C['bg']); self.log.pack(fill='both', expand=True)   # плитки последних подсказок, новые первыми
        for i in range(3): self.log.columnconfigure(i, weight=1, uniform='h')
        self.log_items = []
        self.lanes = tk.Frame(self.low, bg=C['panel'], padx=12, pady=8, highlightthickness=0, width=app.fs(380), height=app.fs(215))
        self.lanes.pack(side='left', fill='y'); self.lanes.pack_propagate(False)
        self.mode, self.cards, self._save_job, self.draft_sig, self.load_sig = None, {}, None, None, None
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
        self.sub.configure(fg=C['mute']); self._objs_sig = self._lanes_sig = None
        for w in self.body.winfo_children(): w.destroy()
        self.cards, self.draft_sig, self.load_sig = {}, None, None
        for i in range(3): self.body.columnconfigure(i, weight=0, uniform='')
        if mode in ('game', 'draft', 'load'):
            self.cols = [tk.Frame(self.body, bg=C['bg']) for _ in range(2)]
            self.mid = tk.Frame(self.body, bg=C['bg']) if mode == 'draft' else None
            place = [self.cols[0], self.mid, self.cols[1]] if self.mid else self.cols
            for i, f in enumerate(place): f.grid(row=0, column=i, sticky='nsew', padx=6); self.body.columnconfigure(i, weight=1, uniform='t')
        if mode == 'draft': self.timer.place(relx=1.0, x=-20, y=10, anchor='ne'); self.tick()
        else: self.timer.place_forget()
        if mode == 'draft':
            self.bottom = tk.Frame(self.mid, bg=C['bg'])   # в середине: кого взять и кого банить
            self.bar.pack(fill='x', padx=16, pady=(8, 0), before=self.wrap)
        else:
            self.bar.pack_forget()
        if mode == 'game':
            self.low.pack(fill='x', padx=16, pady=(0, 14)); self.log_items = []; self.draw_log()
            self.objs.place(relx=1.0, x=-16, y=12, anchor='ne')
        else:
            self.low.pack_forget(); self.objs.place_forget()

    def idle(self):
        self.clear('idle')
        self.head.configure(text='Ждём выбора чемпионов', fg=C['fg']); self.sub.configure(text='Окно само покажет драфт, а потом игру.')

    def reset(self):
        self.mode = None; self.clear('game')
        self.head.configure(text='Игра загружается', fg=C['fg']); self.sub.configure(text='')

    def add_log(self, t, text):
        if self.mode == 'game': self.log_items = ([(t, text)] + self.log_items)[:6]; self.draw_log()

    def draw_log(self):
        fn, fs = F['font'], self.app.fs
        for w in self.log.winfo_children(): w.destroy()
        for i, (t, text) in enumerate(self.log_items):
            bg = C['tag_y'] if i == 0 else C['panel']
            f = tk.Frame(self.log, bg=bg, padx=fs(10), pady=fs(6)); f.grid(row=i // 3, column=i % 3, sticky='nsew', padx=(0, 6), pady=(0, 6))
            tk.Label(f, text=core.mmss(t), bg=bg, fg=C['warn'] if i == 0 else C['mute'], font=(F['numb'], fs(10))).pack(side='left', anchor='n', padx=(0, 8))
            tk.Label(f, text=text, bg=bg, fg=C['fg'] if i == 0 else C['mute'], font=(fn, fs(10)), wraplength=fs(250), justify='left', anchor='w').pack(side='left', fill='x')

    def tick(self):
        """Таймер пика в драфте: отсчёт до конца текущей фазы по данным клиента."""
        if self.mode != 'draft': return
        left = self.deadline - time.time()
        self.timer.configure(text=f'{int(left)}' if left > 0 else '', fg=C['warn'] if 0 < left <= 10 else C['fg'])
        self.after(250, self.tick)

    # --- ARAM: своя команда, скамейка и сборка ARAM
    def show_aram(self, cs):
        app = self.app
        me = cs.get('me')
        eu = app.lola_build(me, 'ARAM') if me else None
        sig = json.dumps(['aram', me, bool(eu), [(a['c'], bool(a.get('rank'))) for a in cs.get('allies', [])], cs.get('bench')], default=str)
        self.clear('draft')
        if sig == self.draft_sig: return
        self.draft_sig = sig
        no_flicker(self, lambda: self._show_aram(cs, me, eu))

    def _show_aram(self, cs, me, eu):
        app, d, fn, fs = self.app, self.app.data, F['font'], self.app.fs
        for col in self.cols + [self.mid]:
            for w in col.winfo_children(): w.destroy()
        self.draft_bar('ARAM', me)
        self.head.configure(text='ARAM' + (f' · ты: {d.cn(me)}' if me else ''), fg=C['fg'])
        self.sub.configure(text='Сборка и руны ARAM с lolalytics, импорт той же кнопкой. Скамейка — справа.')
        for col, t, c in ((self.cols[0], 'Твоя команда', 'blue'), (self.mid, 'Сборка', 'gold'), (self.cols[1], 'Скамейка', 'mute')):
            tk.Label(col, text=t.upper(), bg=C['bg'], fg=C[c], font=(fn, fs(9), 'bold'), anchor='w').pack(fill='x', padx=4, pady=(0, 2))
        for p in cs.get('allies') or []: self.draft_card(0, dict(p, pos=''), {'role': ''}, None)
        if me: self.build_box(self.mid, me, eu, 'ARAM')
        for c in cs.get('bench') or []:
            tk.Label(self.cols[1], text='  ' + d.cn(c), image=app.img('champ', c, 1.0) or '', compound='left', bg=C['bg'], fg=C['fg'],
                     font=(fn, fs(11), 'bold'), anchor='w').pack(anchor='w', pady=2)
        if not cs.get('bench'): tk.Label(self.cols[1], text='пусто', bg=C['bg'], fg=C['mute'], font=(fn, fs(10))).pack(anchor='w')

    def show_arena(self, cs):
        app = self.app
        me = cs.get('me')
        lo = app.lola_fetch('arena', me, 'ARENA') if me else None
        sig = json.dumps(['arena', me, bool(lo), [(a['c'], bool(a.get('rank')), bool(a.get('hist'))) for a in cs.get('allies', [])]], default=str)
        self.clear('draft')
        if sig == self.draft_sig: return
        self.draft_sig = sig
        no_flicker(self, lambda: self._show_arena(cs, me, lo))

    def _show_arena(self, cs, me, lo):
        """Драфт Арены: ты и напарник, твой чемпион в Арене (lolalytics и твои игры) и твои лучшие чемпионы Арены."""
        app, d, fn, fs = self.app, self.app.data, F['font'], self.app.fs
        for col in self.cols + [self.mid]:
            for w in col.winfo_children(): w.destroy()
        for w in self.bar.winfo_children(): w.destroy()
        self.bar.pack_forget()
        self.head.configure(text='Арена' + (f' · ты: {d.cn(me)}' if me else ''))
        self.sub.configure(text='Место считается среди пар. Винрейты аугментов и предметов Арены не показываем: Riot это запрещает.')
        games = app.arena_games()
        head = lambda col, t: tk.Label(col, text=t.upper(), bg=C['bg'], fg=C['gold'], font=(F['head'], fs(12)), anchor='w').pack(fill='x', padx=4, pady=(6, 2))
        head(self.cols[0], 'Ты и напарник')
        for p in cs.get('allies') or []: self.draft_card(0, dict(p, pos=''), {'role': ''}, None)
        head(self.mid, 'Чемпион в Арене')
        box = tk.Frame(self.mid, bg=C['panel'], padx=fs(14), pady=fs(12)); box.pack(fill='x', pady=3)
        if not me: tk.Label(box, text='Выбери чемпиона: здесь будет его винрейт в Арене и твои игры на нём.', bg=C['panel'], fg=C['mute'], font=(fn, fs(10)), wraplength=fs(360), justify='left').pack(anchor='w')
        else:
            row = tk.Frame(box, bg=C['panel']); row.pack(fill='x')
            tk.Label(row, image=app.img('champ', me, 1.4) or '', bg=C['panel']).pack(side='left', padx=(0, 12))
            t = tk.Frame(row, bg=C['panel']); t.pack(side='left', fill='x')
            tk.Label(t, text=d.cn(me), bg=C['panel'], fg=C['gold'], font=(fn, fs(13), 'bold')).pack(anchor='w')
            st = app.lola_state.get(('arena', me, 'ARENA'))
            txt = (f"Изумруд+: {lo['wr']:.1f}% побед · {lo['n']:,} игр".replace(',', ' ').replace('.', ',') if lo else
                   'не удалось загрузить lolalytics' if st == 'fail' else 'загружаю lolalytics…')
            tk.Label(t, text=txt, bg=C['panel'], fg=C['fg'], font=(fn, fs(10))).pack(anchor='w')
            my = core.arena_stats(games, me)
            tk.Label(t, text=(f"Ты: {my['n']} игр · среднее место {my['avg']:.1f} · топ-4 {my['top4']:.0f}%".replace('.', ',') if my else 'Ты на нём в Арене ещё не играл'),
                     bg=C['panel'], fg=C['mute'], font=(fn, fs(10))).pack(anchor='w')
        best = core.arena_best(games)
        head(self.mid, 'Твои лучшие в Арене')
        if not best: tk.Label(self.mid, text='Нужно хотя бы 3 игры на чемпионе в Арене.', bg=C['bg'], fg=C['mute'], font=(fn, fs(10))).pack(anchor='w', padx=4)
        row = tk.Frame(self.mid, bg=C['bg']); row.pack(fill='x')
        for i, (c, s) in enumerate(best):
            bg = C['raise'] if i == 0 else C['panel']
            f = tk.Frame(row, bg=bg, padx=fs(10), pady=fs(8)); f.grid(row=0, column=i, sticky='nsew', padx=(0 if i == 0 else 4, 0)); row.columnconfigure(i, weight=1, uniform='a')
            tk.Label(f, image=app.img('champ', c, 1.1) or '', bg=bg).pack(anchor='w')
            tk.Label(f, text=d.cn(c), bg=bg, fg=C['gold'] if i == 0 else C['fg'], font=(fn, fs(11), 'bold')).pack(anchor='w', pady=(4, 0))
            tk.Label(f, text=f"место {s['avg']:.1f} · {s['n']} игр".replace('.', ','), bg=bg, fg=C['mute'], font=(fn, fs(9))).pack(anchor='w')
        head(self.cols[1], 'Последние игры Арены')
        for g in games[:8]:
            r = tk.Frame(self.cols[1], bg=C['panel'], padx=fs(10), pady=fs(5)); r.pack(fill='x', pady=2)
            tk.Label(r, text=str(g['place']), bg=C['panel'], fg=C['good'] if g['place'] <= 4 else C['bad'], font=(F['numb'], fs(14)), width=2).pack(side='left')
            tk.Label(r, image=app.img('champ', g['c'], .8) or '', bg=C['panel']).pack(side='left', padx=6)
            tk.Label(r, text=f"{d.cn(g['c'])} · {g['k']}/{g['d']}/{g['a']}" + (f" · с {d.cn(g['pc'])}" if g.get('pc') else ''), bg=C['panel'], fg=C['fg'], font=(fn, fs(10))).pack(side='left')
        if not games: tk.Label(self.cols[1], text='Игр Арены в статистике пока нет', bg=C['bg'], fg=C['mute'], font=(fn, fs(10))).pack(anchor='w', padx=4)

    # --- экран загрузки: обе команды целиком (в драфте противники скрыты)
    def show_loading(self, ps):
        app, d = self.app, self.app.data
        sig = json.dumps([(p['c'], p['pos'], p['ok'], bool(p['rank'])) for p in ps], default=str)
        self.clear('load')
        if sig == self.load_sig: return
        self.load_sig = sig
        no_flicker(self, lambda: self._show_loading(ps))

    def _show_loading(self, ps):
        app, d = self.app, self.app.data
        for col in self.cols:
            for w in col.winfo_children(): w.destroy()
        fn, fs = F['font'], app.fs
        me = next((p for p in ps if p['me']), None)
        role = me['pos'] if me else ''
        opp = next((p for p in ps if p['col'] == 1 and role and p['pos'] == role), None)
        done = sum(p['ok'] for p in ps)
        self.head.configure(text='Игра загружается · разведка', fg=C['fg'])
        enemy = [p for p in ps if p['col'] == 1 and p.get('hist')]
        mains = [d.cn(p['c']) for p in enemy if any('почти только' in t for t in p['hist']['tags'])]
        tilt = [d.cn(p['c']) for p in enemy if p['hist'].get('tilt')]
        sub = [f'Загружено {done} из {len(ps)}' if done < len(ps) else 'Все игроки загружены']
        if opp: sub.append(f"твой оппонент: {d.cn(opp['c'])}")
        if mains: sub.append('мейны у врагов: ' + ', '.join(mains))
        if tilt: sub.append('в тильте: ' + ', '.join(tilt))
        plan = scout_plan(d, ps, role)
        self.sub.configure(text=' · '.join(sub) + ('\n' + '  '.join(plan) if plan else ''), fg=C['mute'])
        order = {x: i for i, x in enumerate(core.ROLES)}
        for col, t, c in ((0, 'Твоя команда', 'blue'), (1, 'Противники', 'red')):
            tk.Label(self.cols[col], text=t.upper(), bg=C['bg'], fg=C[c], font=(fn, fs(9), 'bold'), anchor='w').pack(fill='x', padx=4, pady=(0, 2))
            for p in sorted((p for p in ps if p['col'] == col), key=lambda p: order.get(p['pos'], 9)):
                self.draft_card(col, p, {'role': role}, None)

    # --- драфт: тот же вид, что в игре — две колонки карточек
    def show_draft(self, cs, r, bans):
        """cs — разбор сессии выбора, r — draft_suggest, bans — ban_suggest."""
        app, d = self.app, self.app.data
        me = cs.get('me')
        eu = app.lola_build(me, r.get('role')) if me else None
        if cs.get('left'): self.deadline = time.time() + cs['left']
        sig = json.dumps([cs['role'], r.get('role'), me, cs['enemies'], sorted(cs['unavailable']), bool(eu), len(app.lola), bans,
                          [(a['c'], a.get('pos'), bool(a.get('rank')), bool(a.get('hist'))) for a in cs.get('allies', [])], [x['c'] for x in r['picks']]], default=str)
        self.clear('draft')
        if sig == self.draft_sig: return
        self.draft_sig = sig
        y = self.cv.yview()[0]
        no_flicker(self, lambda: self._show_draft(cs, r, bans, me, eu))
        self.cv.yview_moveto(y)   # прокрутка остаётся на месте

    def _show_draft(self, cs, r, bans, me, eu):
        app, d = self.app, self.app.data
        for col in self.cols + [self.mid]:
            for w in col.winfo_children(): w.destroy()
        fn, fs = F['font'], app.fs
        self.draft_bar(r.get('role') or cs['role'], me)
        role = core.ROLE_RU.get(r.get('role') or cs['role'], '')
        self.head.configure(text='Выбор чемпионов' + (f' · ты: {role}' if role else ''), fg=C['fg'])
        self.sub.configure(text=(f"Вероятный оппонент: {d.cn(r['opp'])}" if r['opp'] else 'Оппонент ещё не выбран'))
        order = {x: i for i, x in enumerate(core.ROLES)}
        for col, t, c in ((self.cols[0], 'Твоя команда', 'blue'), (self.cols[1], 'Противники', 'red')):
            tk.Label(col, text=t.upper(), bg=C['bg'], fg=C[c], font=(F['head'], fs(12)), anchor='w').pack(fill='x', padx=4, pady=(0, 2))
        allies = sorted(cs.get('allies') or [], key=lambda a: order.get(a.get('pos'), 9))
        enemies = sorted(({'c': c, 'pos': r['roles'].get(c, '')} for c in cs['enemies']), key=lambda a: order.get(a['pos'], 9))
        for col, team in enumerate((allies, enemies + [{}] * (5 - len(enemies)))):
            for p in team: self.draft_card(col, p, r, eu if p.get('me') else None, app.matchup_lines(p, col, allies, r))
        if r['picks'] and not cs.get('locked'):   # сверху: кого взять — три карточки, лучшая подсвечена
            tk.Label(self.mid, text='КОГО ВЗЯТЬ', bg=C['bg'], fg=C['gold'], font=(F['head'], fs(12)), anchor='w').pack(fill='x', padx=4, pady=(6, 2))
            row = tk.Frame(self.mid, bg=C['bg']); row.pack(fill='x', pady=(0, 6))
            for i, x in enumerate(r['picks'][:3]):
                bg = C['raise'] if i == 0 else C['panel']
                c = tk.Frame(row, bg=bg, padx=fs(10), pady=fs(8)); c.grid(row=0, column=i, sticky='nsew', padx=(0 if i == 0 else 4, 0))
                row.columnconfigure(i, weight=1, uniform='p')
                tk.Label(c, image=app.img('champ', x['c'], 1.1) or '', bg=bg).pack(anchor='w')
                tk.Label(c, text=x['name'], bg=bg, fg=C['gold'] if i == 0 else C['fg'], font=(fn, fs(11), 'bold'), anchor='w').pack(anchor='w', pady=(4, 0))
                tk.Label(c, text=x['why'], bg=bg, fg=C['mute'], font=(fn, fs(9)), wraplength=fs(150), justify='left', anchor='w').pack(anchor='w')
        self.matchup_card(me, r)
        self.comp_card(cs, r, allies)
        if me: self.build_box(self.mid, me, eu, r.get('role'))
        self.bottom = tk.Frame(self.mid, bg=C['bg']); self.bottom.pack(fill='x', pady=(12, 0))
        b = self.bottom   # снизу: кого банить
        if bans:
            tk.Label(b, text=f'КОГО БАНИТЬ · {role.upper()}', bg=C['bg'], fg=C['gold'], font=(F['head'], fs(12))).grid(row=5, column=0, columnspan=2, sticky='w', pady=(0, 2))
            for i, (c, sc, why) in enumerate(bans):
                tk.Label(b, text='  ' + d.cn(c), image=app.img('champ', c, 1.0) or '', compound='left', bg=C['bg'], fg=C['bad'],
                         font=(fn, fs(11), 'bold')).grid(row=6 + i, column=0, sticky='w', pady=1)
                tk.Label(b, text='  ' + why, bg=C['bg'], fg=C['mute'], font=(fn, fs(9)), wraplength=fs(250), justify='left').grid(row=6 + i, column=1, sticky='w')

    def draft_bar(self, role, me):
        """Над карточками: линия, вариант рун, импорт в клиент и автоимпорт."""
        app, fn, fs = self.app, F['font'], self.app.fs
        for w in self.bar.winfo_children(): w.destroy()
        box = tk.Frame(self.bar, bg=C['deep'], padx=10, pady=8, highlightthickness=0); box.pack(fill='x')
        row = tk.Frame(box, bg=C['deep']); row.pack(anchor='w', fill='x')
        def seg(parent, items, cur, cmd):
            g = tk.Frame(parent, bg=C['panel'], highlightthickness=0, padx=2, pady=2); g.pack(side='left', padx=(0, 10))
            for val, t in items:
                on = val == cur
                b = tk.Label(g, text=t, bg=C['gold'] if on else C['panel'], fg=C['on_gold'] if on else C['mute'], font=(fn, fs(10), 'bold'),
                             padx=fs(12), pady=fs(4), cursor='hand2')
                b.pack(side='left', padx=1); b.bind('<Button-1>', lambda e, val=val: cmd(val))
        if role != 'ARAM':
            seg(row, [(rr, core.ROLE_RU[rr].capitalize()) for rr in core.ROLES], role, app.set_draft_role)
            seg(row, [('pick', 'Популярные руны'), ('win', 'Лучший винрейт')], app.s['rune_pick'], app.set_rune_pick)
        else: tk.Label(row, text='ARAM: сборка и руны по всем рангам (lolalytics)', bg=C['deep'], fg=C['gold'], font=(fn, fs(10), 'bold')).pack(side='left', padx=(0, 10))
        ttk.Button(row, text='Импортировать в клиент', style='A.TButton', command=app.do_import).pack(side='left')
        row2 = tk.Frame(box, bg=C['deep']); row2.pack(anchor='w', fill='x', pady=(6, 0))
        tk.Label(row2, text='АВТОИМПОРТ, КАК ТОЛЬКО ВЫБЕРЕШЬ ЧЕМПИОНА:', bg=C['deep'], fg=C['mute'], font=(fn, fs(8), 'bold')).pack(side='left')
        for key, t in (('runes', 'руны'), ('items', 'предметы'), ('spells', 'заклинания призывателя')):
            ttk.Checkbutton(row2, text=t, variable=app.auto_vars[key], style='D.TCheckbutton',
                            command=lambda key=key: (app.s['auto_parts'].__setitem__(key, app.auto_vars[key].get()), app.s.save())).pack(side='left', padx=(10, 0))
        self.import_err = ttk.Button(row2, text='Скопировать ошибку для Claude', command=app.copy_report)
        bad = 'не получилось' in app.import_text
        if bad: self.import_err.pack(side='right', padx=(8, 0))
        self.import_lbl = tk.Label(row2, text=app.import_text, bg=C['deep'], fg=C['bad'] if bad else C['mute'], font=(fn, fs(10)), anchor='e')
        self.import_lbl.pack(side='right')

    def matchup_card(self, me, r):
        """Середина драфта: ты против вероятного оппонента — винрейт по Европе, твой счёт и золото на 15."""
        app, d, fn, fs = self.app, self.app.data, F['font'], self.app.fs
        opp, role = r.get('opp'), r.get('role')
        tk.Label(self.mid, text='ТВОЙ МАТЧАП', bg=C['bg'], fg=C['gold'], font=(F['head'], fs(12)), anchor='w').pack(fill='x', padx=4, pady=(6, 2))
        f = tk.Frame(self.mid, bg=C['panel'], padx=fs(14), pady=fs(12), highlightthickness=0); f.pack(fill='x', pady=3)
        if not me or not opp:
            tk.Label(f, text=('Выбери чемпиона' if not me else 'Оппонент ещё не выбран') + ': здесь будет матчап по Европе и твой счёт.',
                     bg=C['panel'], fg=C['mute'], font=(fn, fs(10)), wraplength=fs(380), justify='left').pack(anchor='w')
            return
        wr = n = None
        cnt = core.lola_counters(app.lola_fetch('counter', opp, role), d) if role else {}
        if me in cnt: wr, n = 100 - cnt[me][0], cnt[me][2]
        else:
            cnt = core.lola_counters(app.lola_fetch('counter', me, role), d) if role else {}
            if opp in cnt: wr, n = cnt[opp][0], cnt[opp][2]
        top = tk.Frame(f, bg=C['panel']); top.pack(fill='x')
        tk.Label(top, image=app.img('champ', me, 1.5) or '', bg=C['blue'], padx=2, pady=2).pack(side='left')
        tk.Label(top, image=app.img('champ', opp, 1.5) or '', bg=C['red'], padx=2, pady=2).pack(side='right')
        mid = tk.Frame(top, bg=C['panel']); mid.pack(side='left', fill='x', expand=True, padx=12)
        tk.Label(mid, text=f'{wr:.1f}%' if wr is not None else '—', bg=C['panel'], fg=C['fg'], font=(F['num'], fs(24), 'bold')).pack()
        bar = tk.Frame(mid, bg=C['red'], height=fs(8)); bar.pack(fill='x', pady=4)
        if wr is not None: tk.Frame(bar, bg=C['blue']).place(relx=0, rely=0, relwidth=wr / 100, relheight=1)
        verdict = '' if wr is None else 'сложный матчап' if wr < 48.5 else 'удобный матчап' if wr > 51.5 else 'ровный матчап'
        tk.Label(mid, text=(f'{n:,} игр · {verdict}'.replace(',', ' ') if n else 'загружаю lolalytics…'), bg=C['panel'], fg=C['mute'], font=(fn, fs(9))).pack()
        pl = app.player
        v = pl.vs(me, opp) if pl else {'n': 0}
        if pl and not v['n']: v = pl.vs(None, opp)
        stats = tk.Frame(f, bg=C['panel']); stats.pack(fill='x', pady=(10, 0))
        for i in range(3): stats.columnconfigure(i, weight=1, uniform='s')
        cells = [('Твой счёт', f"{v['w']}–{v['n'] - v['w']}" if v['n'] else '—', 'fg'),
                 ('Золото на 15', f"{v['g15']:+.0f}" if v.get('g15') is not None else '—', 'good' if (v.get('g15') or 0) > 0 else 'bad' if (v.get('g15') or 0) < 0 else 'fg'),
                 ('Против него', 'ещё не встречались' if not v['n'] else ('ты сильнее' if v['w'] * 2 > v['n'] else 'ты слабее' if v['w'] * 2 < v['n'] else 'поровну'), 'mute')]
        for i, (t, val, c) in enumerate(cells):
            cl = tk.Frame(stats, bg=C['deep'], padx=8, pady=6); cl.grid(row=0, column=i, sticky='nsew', padx=(0 if i == 0 else 4, 0))
            tk.Label(cl, text=t.upper(), bg=C['deep'], fg=C['mute'], font=(fn, fs(8), 'bold')).pack()
            tk.Label(cl, text=val, bg=C['deep'], fg=C[c], font=(F['num'] if i < 2 else fn, fs(15) if i < 2 else fs(10), 'bold')).pack()
        tip = pl.matchup_tip(opp) if pl else None
        if tip: tk.Label(f, text=tip, bg=C['panel'], fg=C['gold'], font=(fn, fs(9)), wraplength=fs(380), justify='left').pack(anchor='w', pady=(8, 0))

    def comp_card(self, cs, r, allies):
        """Состав команд: доля магического урона и фронтлайн у вас и у врагов, кого из пула взять под команду."""
        app, d, fn, fs = self.app, self.app.data, F['font'], self.app.fs
        ours = [a['c'] for a in allies if a.get('c')]
        theirs = [c for c in cs['enemies'] if c]
        if len(ours) + len(theirs) < 2: return
        dm = {c: (app.lola.get((c, a.get('pos'))) or {}).get('dmg') for a in allies for c in [a.get('c')] if c}
        tk.Label(self.mid, text='СОСТАВ КОМАНД', bg=C['bg'], fg=C['gold'], font=(F['head'], fs(12)), anchor='w').pack(fill='x', padx=4, pady=(12, 2))
        f = tk.Frame(self.mid, bg=C['panel'], padx=fs(14), pady=fs(10), highlightthickness=0); f.pack(fill='x', pady=3)
        for name, champs, col in (('Вы', ours, 'blue'), ('Враги', theirs, 'red')):
            tc = core.team_comp(d, champs, dm)
            if not tc['n']: continue
            row = tk.Frame(f, bg=C['panel']); row.pack(fill='x', pady=2)
            tk.Label(row, text=name, bg=C['panel'], fg=C[col], font=(fn, fs(10), 'bold'), width=7, anchor='w').pack(side='left')
            ap = tc['ap'] or 0
            bar = tk.Frame(row, bg=C['red2'], height=fs(10), width=fs(150)); bar.pack(side='left', padx=(0, 8)); bar.pack_propagate(False)
            tk.Frame(bar, bg=C['blue2']).place(relx=0, rely=0, relwidth=ap, relheight=1)
            fr = tc['front']
            tk.Label(row, text=f'AP {ap * 100:.0f}% · AD {100 - ap * 100:.0f}% · фронтлайн: {fr if fr else "нет"}', bg=C['panel'],
                     fg=C['fg'], font=(fn, fs(9))).pack(side='left')
        role = r.get('role')
        pool = (app.player.pool.get(role) if app.player else []) or []
        adv = core.comp_advice(d, [a['c'] for a in allies if a.get('c') and not a.get('me')], role, pool, dm)
        if adv:
            text, fit = adv
            tk.Label(f, text=text + ('. Из пула подходят: ' + ', '.join(d.cn(c) for c in fit) if fit else '. В твоём пуле на эту роль подходящих нет'),
                     bg=C['panel'], fg=C['gold'], font=(fn, fs(9)), wraplength=fs(380), justify='left').pack(anchor='w', pady=(6, 0))
        tk.Label(f, text='Синим — магический урон. Оценка по Data Dragon, для чемпионов со сборкой — по урону на lolalytics.',
                 bg=C['panel'], fg=C['mute'], font=(fn, fs(8)), wraplength=fs(380), justify='left').pack(anchor='w', pady=(4, 0))

    def build_box(self, col, me, full, role):
        """Руны и сборки по Европе отдельным блоком в окне драфта (над «Кого взять»)."""
        app, d, fn, fs = self.app, self.app.data, F['font'], self.app.fs
        bg = C['panel']
        tk.Label(col, text=f'РУНЫ И СБОРКА · {d.cn(me).upper()}', bg=C['bg'], fg=C['gold'], font=(F['head'], fs(12)), anchor='w').pack(fill='x', padx=4, pady=(12, 2))
        f = tk.Frame(col, bg=bg, padx=fs(14), pady=fs(10), highlightthickness=0); f.pack(fill='x', pady=3)
        p = {'c': me}
        r = {'role': role}
        eu = full.get(app.s['rune_pick']) or full if full else None
        box = tk.Frame(f, bg=bg); box.pack(anchor='w', pady=(3, 0))
        if eu:
            row = tk.Frame(box, bg=bg); row.pack(anchor='w')
            tk.Label(row, text='Руны', bg=bg, fg=C['fg'],
                     font=(fn, fs(9), 'bold'), width=13, anchor='w').pack(side='left')
            for sp in eu.get('spells', [])[:2]:
                i2 = app.img('spell', sp, .6)
                if i2: tk.Label(row, image=i2, bg=bg).pack(side='left', padx=1)
            tk.Label(row, text=' ', bg=bg).pack(side='left')
            for i, rid in enumerate([eu['prim']] + eu['perks'][:4] + [eu['sec']] + eu['perks'][4:]):
                i2 = app.img('rune', rid, .9 if i == 1 else .6)
                if i2: tk.Label(row, image=i2, bg=bg).pack(side='left', padx=1)
            for key, title in (('pick', 'Популярная'), ('win', 'Лучший винрейт')):
                v = full.get(key)
                if not v or (key == 'win' and v is full.get('pick')): continue
                row = tk.Frame(box, bg=bg); row.pack(anchor='w', pady=(3, 0))
                tk.Label(row, text=title, bg=bg, fg=C['fg'], font=(fn, fs(9), 'bold'), width=13, anchor='w').pack(side='left')
                for it in v['start'] + [None] + core.lola_build_items(v):
                    if it is None: tk.Label(row, text=' › ', bg=bg, fg=C['mute']).pack(side='left'); continue
                    i2 = app.img('item', it, .6)
                    tk.Label(row, image=i2 or '', text='' if i2 else d.iname(it), bg=bg, fg=C['fg']).pack(side='left', padx=1)
                if v.get('n_core') and v.get('wr_core'):
                    tk.Label(row, text=f"  {v['wr_core']:.0f}% · {v['n_core']} игр", bg=bg, fg=C['mute'], font=(fn, fs(9))).pack(side='left')
            if not full.get('pick'):   # старый формат со страницы сборки
                row = tk.Frame(box, bg=bg); row.pack(anchor='w', pady=(3, 0))
                for it in eu['start'] + [None] + core.lola_build_items(eu):
                    if it is None: tk.Label(row, text=' › ', bg=bg, fg=C['mute']).pack(side='left'); continue
                    i2 = app.img('item', it, .6)
                    tk.Label(row, image=i2 or '', text='' if i2 else d.iname(it), bg=bg, fg=C['fg']).pack(side='left', padx=1)
            if eu.get('skills'):   # порядок прокачки умений
                row = tk.Frame(box, bg=bg); row.pack(anchor='w', pady=(4, 0))
                tk.Label(row, text='Умения', bg=bg, fg=C['fg'], font=(fn, fs(9), 'bold'), width=13, anchor='w').pack(side='left')
                if eu.get('skill_prio'):
                    tk.Label(row, text=' › '.join(eu['skill_prio']), bg=bg, fg=C['gold'], font=(F['num'], fs(12), 'bold')).pack(side='left', padx=(0, 10))
                for i, k in enumerate(eu['skills'][:15]):
                    tk.Label(row, text=k, bg=C['gold'] if k == 'R' else C['deep'], fg=C['on_gold'] if k == 'R' else C['fg'] if i < 3 else C['mute'],
                             font=(F['num'], fs(9), 'bold'), width=2).pack(side='left', padx=1)
            situ = full.get('situ') or []
            for k0 in range(0, min(6, len(situ)), 2):   # по два в строку, чтобы не вылезать за карточку
                row = tk.Frame(box, bg=bg); row.pack(anchor='w', pady=(3, 0))
                tk.Label(row, text='Ситуативно' if not k0 else '', bg=bg, fg=C['fg'], font=(fn, fs(9), 'bold'), width=13, anchor='w').pack(side='left')
                for it, short, _ in situ[k0:k0 + 2]:
                    tk.Label(row, image=app.img('item', it, .6) or '', text=' ' + short, compound='left', bg=bg, fg=C['fg'],
                             font=(fn, fs(9))).pack(side='left', padx=(0, 6))
            where = 'ARAM, все ранги' if role == 'ARAM' else 'Европа, Изумруд+'
            tk.Label(box, text=f"{where}: {full['games']} игр на чемпионе" if full.get('games') else where,
                     bg=bg, fg=C['mute'], font=(fn, fs(9))).pack(anchor='w')
        else:
            st = app.lola_state.get((p['c'], r.get('role')))
            tk.Label(box, text=('Сборка ARAM: ' if role == 'ARAM' else 'Сборка по Европе: ') + ('не удалось загрузить lolalytics' if st == 'fail' else 'загружаю…'),
                     bg=bg, fg=C['mute'], font=(fn, fs(9))).pack(anchor='w')

    def chips(self, parent, items, bg, maxw=44):
        """Метки строками: Tk не умеет переносить, поэтому раскладываем по примерной длине."""
        fn, fs = F['font'], self.app.fs
        row, used = None, maxw
        for text, kind in items:
            if used + len(text) > maxw: row = tk.Frame(parent, bg=bg); row.pack(anchor='w', pady=(4, 0)); used = 0
            cbg, cfg = {'g': (C['tag_g'], C['good2']), 'r': (C['tag_r'], C['bad2']), 'y': (C['tag_y'], C['warn'])}.get(kind, (C['raise'], C['fg']))
            tk.Label(row, text=text, bg=cbg, fg=cfg, font=(fn, fs(9), 'bold'), padx=8, pady=2, wraplength=fs(330), justify='left').pack(side='left', padx=(0, 6))
            used += len(text) + 3

    def draft_card(self, col, p, r, eu, extra=None):
        """Карточка игрока в драфте: портрет, звание, метки игрока и строки контрпиков/синергии."""
        app, d, fn, fs = self.app, self.app.data, F['font'], self.app.fs
        empty = not p.get('c')
        bg = C['deep'] if empty else C['raise'] if p.get('me') else C['panel']
        opp = col == 1 and p.get('c') and app.player and p.get('pos') == r.get('role')
        f = tk.Frame(self.cols[col], bg=bg, padx=fs(12), pady=fs(10), highlightthickness=0)
        f.pack(fill='x', pady=4)
        if p.get('me') or opp: tk.Frame(f, bg=C['gold'] if p.get('me') else C['red']).place(x=-fs(12), rely=.08, relheight=.84, width=3)
        left = tk.Frame(f, bg=bg); left.grid(row=0, column=0, rowspan=3, padx=(0, 10), sticky='n')
        im = app.img('champ', p['c'], 1.5) if p.get('c') else None
        tk.Label(left, image=im or '', text='' if im else '?', bg=bg if im else C['raise'], fg=C['mute'], font=(fn, fs(20)), width=0 if im else 3).pack()
        sp = tk.Frame(f, bg=bg); sp.grid(row=0, column=1, rowspan=3, sticky='n', padx=(0, 8))
        if eu: eu = eu.get(app.s['rune_pick']) or eu   # руны и заклинания выбранного варианта
        if eu:
            for s in eu['spells'][:2]:
                i2 = app.img('spell', s, .55)
                if i2: tk.Label(sp, image=i2, bg=bg).pack(pady=1)
            i2 = app.img('rune', eu['perks'][0], .55)
            if i2: tk.Label(sp, image=i2, bg=bg).pack(pady=1)
        name = d.cn(p['c']) if p.get('c') else ('выбирает…' if p else 'ещё не выбран')
        tk.Label(f, text=name + ('  · ты' if p.get('me') else ''), bg=bg, anchor='w',
                 fg=C['mute'] if empty else C['blue2'] if col == 0 else C['red2'], font=(fn, fs(13), 'bold')).grid(row=0, column=2, sticky='w')
        summary, tags = hist_tags(p.get('hist'))
        line = core.ROLE_RU[p['pos']] if p.get('pos') else 'роль неизвестна'
        if opp:
            v = app.player.vs(None, p['c'])
            tags.insert(0, ('Твой оппонент', 'y'))
            line += f" · ты {v['w']}–{v['n'] - v['w']} против него" if v['n'] else ' · ещё не встречались'
        elif summary: line += ' · ' + summary
        tk.Label(f, text=line, bg=bg, anchor='w', fg=C['mute'], font=(fn, fs(10))).grid(row=1, column=2, sticky='w')
        if p.get('rank') and app.s['show']['ranks']:
            tk.Label(f, image=app.img('emb', TIER_RU.get(p['rank']['tier']), 1.1) or '', text=rank_short(p['rank']), bg=bg, fg=C['mute'],
                     font=(fn, fs(9)), compound='top', justify='center').grid(row=0, column=3, rowspan=3, sticky='ne', padx=(8, 0))
        chars = tk.Frame(f, bg=bg); chars.grid(row=3, column=0, columnspan=4, sticky='we', pady=(2, 0))
        if tags: self.chips(chars, tags, bg)
        for text, c in extra or []:
            if isinstance(c, str):
                tk.Label(chars, text=text, bg=bg, fg=C[c], font=(fn, fs(10)), anchor='w', justify='left', wraplength=fs(520)).pack(anchor='w', pady=(4, 0)); continue
            tk.Label(chars, text=text.upper(), bg=bg, fg=C['mute'], font=(fn, fs(8), 'bold')).pack(anchor='w', pady=(6, 0))
            for k in range(0, len(c), 2):   # чемпионы с иконками по два в строку: контрпики, синергия
                row = tk.Frame(chars, bg=bg); row.pack(anchor='w', pady=(2, 0))
                for ch, val, col_ in c[k:k + 2]:
                    col_ = {'blue': 'good2', 'good': 'good2', 'bad': 'bad2'}.get(col_, col_)
                    tk.Label(row, text=f' {d.cn(ch)} {val}', image=app.img('champ', ch, .6) or '', compound='left', bg=bg, fg=C[col_],
                             font=(fn, fs(9), 'bold')).pack(side='left', padx=(0, 10))
        f.columnconfigure(2, weight=1)
        if p.get('pu'): self.hist_toggle(f, p['pu'], 5, [left])

    def hist_toggle(self, f, pu, row, click):
        """Строка «▸ История игр»: клик по ней или по портрету раскрывает последние игры игрока."""
        app, fn, fs, bg = self.app, F['font'], self.app.fs, C['panel']
        lbl = tk.Label(f, bg=bg, fg=C['gold'], font=(fn, fs(9)), cursor='hand2', anchor='w')
        lbl.grid(row=row, column=0, columnspan=4, sticky='w', pady=(3, 0))
        box = tk.Frame(f, bg=bg)
        def draw():
            for c in box.winfo_children(): c.destroy()
            on = pu in app.hist_exp
            lbl.configure(text=('▾ Скрыть историю игр' if on else '▸ История игр (клик)'))
            if not on: box.grid_forget(); return
            box.grid(row=row + 1, column=0, columnspan=4, sticky='we')
            self.mini_hist(box, pu)
        def toggle(e=None):
            app.hist_exp.symmetric_difference_update({pu}); draw()
        for w in [lbl] + click:
            w.bind('<Button-1>', toggle); w.configure(cursor='hand2')
        draw()

    def mini_hist(self, box, pu, n=10):
        app, d, fn, fs, bg = self.app, self.app.data, F['font'], self.app.fs, C['panel']
        hist = (getattr(app, 'hraw', {}) or {}).get(pu)
        if not hist:
            tk.Label(box, text='клиент не отдал историю игр', bg=bg, fg=C['mute'], font=(fn, fs(9))).pack(anchor='w'); return
        for h in hist[:n]:
            c = d.ids.get(str(h['champ']))
            r = tk.Frame(box, bg=C['deep'], padx=6, pady=1, cursor='hand2')
            r.pack(fill='x', pady=1)
            tk.Frame(r, bg=C['good'] if h['win'] else C['bad']).place(x=0, rely=.2, relheight=.6, width=3)   # полоска победы/поражения
            mins = max(1, h.get('dur', 0) / 60)
            pos = core.lcu_pos({'timeline': {'lane': h.get('lane'), 'role': h.get('role')}})
            ws = [tk.Label(r, image=app.img('champ', c, .55) or '', text='' if c else '?', bg=C['deep']),
                  tk.Label(r, text='П' if h['win'] else 'Пр', width=3, bg=C['deep'], fg=C['good' if h['win'] else 'bad'], font=(fn, fs(9), 'bold')),
                  tk.Label(r, text=(d.cn(c) if c else '?') + (f" · {core.ROLE_RU[pos]}" if pos else ''), width=15, anchor='w', bg=C['deep'], fg=C['fg'], font=(fn, fs(9))),
                  tk.Label(r, text=f"{h['k']}/{h['d']}/{h['a']}", width=8, anchor='w', bg=C['deep'], fg=C['fg'], font=(fn, fs(9), 'bold')),
                  tk.Label(r, text=f"{h.get('cs', 0)} CS ({h.get('cs', 0) / mins:.1f}) · {core.mmss(h.get('dur', 0))}", width=17, anchor='w', bg=C['deep'], fg=C['mute'], font=(fn, fs(9))),
                  tk.Label(r, text=time.strftime('%d.%m', time.localtime(h['t'] / 1000)) if h.get('t') else '',
                           anchor='w', bg=C['deep'], fg=C['mute'], font=(fn, fs(9)))]
            for w in ws: w.pack(side='left', padx=2)
            for w in [r] + ws: w.bind('<Button-1>', lambda e, h=h: app.hist_open(h, None, pu))

    def show_objs(self, g):
        ob = g.objectives()
        items = [(n, ob[k] - g.t) for k, n in (('dragon', ob.get('dragon_name') or 'Дракон'), ('grubs', 'Личинки'), ('herald', 'Герольд'), ('baron', 'Барон'))
                 if k in ob and ob[k] > g.t]
        sig = [(n, int(t)) for n, t in items]
        if getattr(self, '_objs_sig', None) == sig: return
        self._objs_sig = sig
        fn, fs = F['font'], self.app.fs
        for w in self.objs.winfo_children(): w.destroy()
        for n, t in items:
            soon = t <= 60
            bg = C['raise'] if soon else C['panel']
            f = tk.Frame(self.objs, bg=bg, padx=12, pady=4); f.pack(side='left', padx=(8, 0))
            tk.Label(f, text=n.upper(), bg=bg, fg=C['mute'], font=(F['num'], fs(9))).pack()
            tk.Label(f, text=core.mmss(t), bg=bg, fg=C['gold'] if soon else C['fg'], font=(F['numb'], fs(15))).pack()

    def show_lanes(self, g):
        rows = []
        for r in core.ROLES:
            a = next((p for p in g.allies if p['pos'] == r), None)
            e = next((p for p in g.enemies if p['pos'] == r), None)
            if a and e: rows.append((r, a['igold'] - e['igold']))
        sig = [(r, int(v // 50)) for r, v in rows]
        if getattr(self, '_lanes_sig', None) == sig: return
        self._lanes_sig = sig
        fn, fs, box = F['font'], self.app.fs, self.lanes
        for w in box.winfo_children(): w.destroy()
        tk.Label(box, text='ЗОЛОТО ПО ЛИНИЯМ', bg=C['panel'], fg=C['gold'], font=(F['head'], fs(12)), anchor='w').pack(fill='x', pady=(0, 4))
        for r, v in rows:
            row = tk.Frame(box, bg=C['panel']); row.pack(fill='x', pady=3)
            ri = self.app.role_img(r, .45)
            if ri: tk.Label(row, image=ri, bg=C['panel']).pack(side='left', padx=(0, 6))
            tk.Label(row, text=core.ROLE_RU[r].capitalize(), bg=C['panel'], fg=C['fg'], font=(fn, fs(10)), width=7, anchor='w').pack(side='left')
            tk.Label(row, text=f'{v:+,.0f}'.replace(',', ' '), bg=C['panel'], fg=C['blue2'] if v > 0 else C['red2'] if v < 0 else C['mute'],
                     font=(F['num'], fs(11)), width=7, anchor='e').pack(side='right')
            tr = tk.Frame(row, bg=C['line'], height=fs(7)); tr.pack(side='left', fill='x', expand=True, padx=6)
            k = min(.5, abs(v) / 4000 * .5)
            if k > .005: tk.Frame(tr, bg=C['blue'] if v > 0 else C['red']).place(relx=.5 if v > 0 else .5 - k, rely=0, relwidth=k, relheight=1)

    # --- игра
    def card(self, col, p):
        key = (col, p['riot'])
        if key in self.cards: return self.cards[key]
        app, fn, fs = self.app, F['font'], self.app.fs
        bg = C['panel']
        f = tk.Frame(self.cols[col], bg=bg, padx=self.app.fs(12), pady=self.app.fs(8), highlightthickness=0)
        f.pack(fill='x', pady=3)
        w = {'f': f}
        left = tk.Frame(f, bg=bg); left.grid(row=0, column=0, rowspan=4, padx=(0, 8), sticky='n')
        w['por'] = tk.Label(left, bg=bg, fg=C['fg'], font=(fn, fs(10), 'bold'), compound='top'); w['por'].pack()
        w['chars'] = tk.Frame(f, bg=bg); w['chars'].grid(row=4, column=0, columnspan=4, sticky='we', pady=(4, 0))
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
        w['hist'] = None
        self.cards[key] = w
        return w

    def show(self, g, scout, ranks, hists):
        if self.mode != 'game': self.reset()
        app, d, sh = self.app, self.app.data, self.app.s['show']
        diff = g.gold_diff()
        self.head.configure(text=core.mmss(g.t), fg=C['fg'])
        j = g.ejg
        self.sub.configure(text=f"Золото в предметах: {diff:+,.0f} {'в пользу твоей команды' if diff > 0 else 'в пользу противников' if diff < 0 else ''}".replace(',', ' ')
                                + (f'   ·   лесник врагов: {d.cn(j["c"])}' if j else ''), fg=C['good' if diff > 1000 else 'bad' if diff < -1000 else 'mute'])
        self.show_objs(g); self.show_lanes(g)
        order = {r: i for i, r in enumerate(core.ROLES)}
        for col, team in enumerate((g.allies, g.enemies)):
            for p in sorted(team, key=lambda p: order.get(p['pos'], 9)):
                w = self.card(col, p)
                if p is g.me and not w.get('strip'): w['strip'] = tk.Frame(w['f'], bg=C['gold']); w['strip'].place(x=-app.fs(12), rely=.08, relheight=.84, width=3)
                big = app.img('champ', p['c'], 1.6, gray=p['dead']) if sh['portraits'] else None
                w['por'].configure(image=big or '', text=f"{p['lvl']} ур.")
                rk, h = ranks.get(p['riot']), hists.get(p['riot'])
                csig = (bool(rk), json.dumps(h, default=str))
                if w['csig'] != csig:   # характеристика под портретом
                    w['csig'] = csig
                    for c in w['chars'].winfo_children(): c.destroy()
                    summary, tags = hist_tags(h)
                    if summary: tk.Label(w['chars'], text=summary, bg=C['panel'], fg=C['mute'], font=(F['font'], app.fs(9)), anchor='w').pack(anchor='w')
                    if tags: self.chips(w['chars'], tags[:4], C['panel'], 70)
                sps = (p['spells'] if sh['spells'] else [])[:2]
                imgs = [app.img('spell', s, .6) for s in sps] + ([app.img('rune', p['keystone'], .6)] if sh['runes'] else [])
                for l, im in zip(w['sp'], imgs + [None] * 3): l.configure(image=im or '')
                dead = f"  · мёртв {core.mmss(p['respawn'])}" if p['dead'] else ''
                w['name'].configure(text=f"{d.cn(p['c'])}   {p['k']}/{p['d']}/{p['a']}{dead}", fg=C['blue2'] if col == 0 else C['red2'])
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
                pu = app.pus.get(p['riot'])
                if pu and w['hist'] != pu:
                    w['hist'] = pu; self.hist_toggle(w['f'], pu, 6, [w['por'], w['name']])


def scout_plan(d, ps, role):
    """Вывод разведки: что делать с тем, что видно у игроков (как Porofessor, но с советом)."""
    out = []
    find = lambda col, pos: next((p for p in ps if p['col'] == col and p['pos'] == pos and p.get('hist')), None)
    opp, ejg = (find(1, role) if role else None), find(1, 'JUNGLE')
    if opp:
        tags = ' '.join(opp['hist']['tags'])
        if 'почти только' in tags: out.append(f"▸ {d.cn(opp['c'])} — мейн: знает свои пики силы, играй от фарма и не дерись на его условиях.")
        elif 'не играл' in tags: out.append(f"▸ {d.cn(opp['c'])} впервые за 20 игр: дави первые уровни, он ещё не знает чемпиона.")
        if opp['hist'].get('tilt'): out.append(f"▸ Оппонент в тильте: провоцируй размены, он чаще ошибается.")
    if ejg and ejg is not opp:
        h = ejg['hist']
        if h.get('tilt') or any('часто умирает' in b for b in h.get('bad') or []):
            out.append(f"▸ Лесник врагов {d.cn(ejg['c'])} " + ('в тильте' if h.get('tilt') else 'часто умирает') +
                       (': вторгайся в его лес и контри первые лагеря.' if role == 'JUNGLE' else ': помогай своему леснику на реке.'))
    weak = [p for p in ps if p['col'] == 0 and not p['me'] and p.get('hist') and p['hist'].get('tilt')]
    if weak: out.append(f"▸ У союзника ({', '.join(d.cn(p['c']) for p in weak)}) серия поражений: не флейми, играй от сильных линий.")
    return out[:3]


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

def show_arena_post(app, res):
    """Окно итога Арены: место, урон и счёт рядом с твоими средними по Арене."""
    d, fs, fn = app.data, app.fs, F['font']
    c = d.ids.get(str(res['c']))
    st = core.arena_stats(app.arena_games()) or {}
    w = tk.Toplevel(app.root); w.title('LoL Helper — итог Арены'); w.configure(bg=C['bg'], padx=18, pady=14); w.attributes('-topmost', True)
    pl = res.get('place') or 0
    tk.Label(w, text=f"  {pl}-е место · {d.cn(c)}" + (f" с {d.cn(d.ids.get(str(res['mate'])))}" if res.get('mate') else ''), image=app.img('champ', c, 1.4) or '',
             compound='left', bg=C['bg'], fg=C['good'] if pl and pl <= 4 else C['bad'], font=(F['head'], fs(18))).pack(anchor='w', pady=(0, 10))
    rows = [('Место', f'{pl}', f"обычно {st['avg']:.1f}".replace('.', ',') if st else '', bool(st) and pl <= st['avg']),
            ('Урон по чемпионам', f"{res['dmg']:,}".replace(',', ' '), f"обычно {st['dmg']:,.0f}".replace(',', ' ') if st else '', bool(st) and res['dmg'] >= st['dmg']),
            ('Счёт', f"{res['k']}/{res['d']}/{res['a']}", '', None)]
    for name, v, norm, good in rows:
        r = tk.Frame(w, bg=C['panel'], padx=12, pady=6); r.pack(fill='x', pady=2)
        tk.Label(r, text=name, bg=C['panel'], fg=C['mute'], font=(fn, fs(10)), width=18, anchor='w').pack(side='left')
        tk.Label(r, text=v, bg=C['panel'], fg=C['fg'] if good is None else C['good'] if good else C['warn'], font=(F['numb'], fs(15))).pack(side='left')
        if norm: tk.Label(r, text=norm, bg=C['panel'], fg=C['mute'], font=(fn, fs(10))).pack(side='right')
    ttk.Button(w, text='Закрыть', command=w.destroy).pack(anchor='e', pady=(10, 0))


def show_postgame(app, res, result):
    w = tk.Toplevel(app.root); w.title('LoL Helper — итог игры'); w.configure(bg=C['bg'], padx=18, pady=14)
    w.attributes('-topmost', True)
    fs, fn = app.fs, F['font']
    head = {'Win': 'Победа', 'Lose': 'Поражение'}.get(result, 'Игра окончена')
    tk.Label(w, text=f"  {head} · {app.data.cn(res['me']['c'])} · {res['min']:.0f} мин", bg=C['bg'],
             fg=C['good'] if result == 'Win' else C['bad'] if result == 'Lose' else C['gold'], font=(fn, fs(16), 'bold'),
             image=app.img('champ', res['me']['c'], 1.4) or '', compound='left').pack(anchor='w', pady=(0, 8))
    body = tk.Frame(w, bg=C['bg']); body.pack(fill='x')
    left = tk.Frame(body, bg=C['bg']); left.pack(side='left', anchor='n')
    right = tk.Frame(body, bg=C['bg']); right.pack(side='left', anchor='n', padx=(18, 0))
    rows = []   # строки появляются по очереди
    norm = res.get('norm') or {}
    for name, v, th, ok, dec in res['goals']:
        nv = norm.get(core.GOAL_NORM.get(name))
        cmp = ''
        if nv is not None:   # стрелка: лучше или хуже, чем обычно у тебя на этом чемпионе
            better = v > nv if name in core.MORE else v < nv
            cmp = f"   {'▲' if better else '▼' if abs(v - nv) > 1e-9 else '='} обычно {nv:.{max(dec, 1) if dec else 1}f}"
        r = tk.Frame(left, bg=C['bg'])
        tk.Label(r, text=f"{'✓' if ok else '✗'}  {name}: {v:.{dec}f} (цель {th})", bg=C['bg'], fg=C['good' if ok else 'bad'],
                 font=(fn, fs(12))).pack(side='left')
        if cmp: tk.Label(r, text=cmp, bg=C['bg'], fg=C['mute'], font=(fn, fs(10))).pack(side='left')
        rows.append(r)
    for i, r in enumerate(rows): w.after(140 * (i + 1), lambda r=r: r.winfo_exists() and r.pack(anchor='w'))
    app.death_map(right, res)
    mis = res.get('mistakes') or []
    tk.Label(w, text='ЧТО ИСПРАВИТЬ В СЛЕДУЮЩЕЙ ИГРЕ' if mis else 'Все цели выполнены, так держать', bg=C['bg'], fg=C['gold'] if mis else C['good'],
             font=(fn, fs(10 if mis else 12), 'bold')).pack(anchor='w', pady=(12, 2))
    for i, (name, v, th, tip) in enumerate(mis, 1):
        tk.Label(w, text=f'{i}. {name}', bg=C['bg'], fg=C['fg'], font=(fn, fs(12), 'bold'), anchor='w').pack(anchor='w', pady=(6, 0))
        tk.Label(w, text=tip[:1].upper() + tip[1:], bg=C['bg'], fg=C['mute'], font=(fn, fs(10)), wraplength=fs(480), justify='left').pack(anchor='w', padx=(18, 0))
    tk.Label(w, text=f"Подсказок за игру: {len(res['hints'])}", bg=C['bg'], fg=C['mute'], font=(fn, fs(10))).pack(anchor='w', pady=(10, 0))
    row = tk.Frame(w, bg=C['bg']); row.pack(fill='x', pady=(12, 0))
    ttk.Button(row, text='Закрыть', command=w.destroy).pack(side='right')
    if app.player:   # игры Halch и DrVoldemar есть на сайте
        ttk.Button(row, text='Разбор на сайте', style='A.TButton', command=app.open_last_game).pack(side='right', padx=8)
        tk.Label(w, text='Игра появляется на сайте через 10–15 минут после конца.', bg=C['bg'], fg=C['mute'], font=(fn, fs(9))).pack(anchor='e', pady=(4, 0))


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
        self.rank_pu, self.hraw, self.jg_cache = {}, {}, {}   # звание и история игр по puuid: с экрана загрузки переходят в игру без повторных запросов
        self.pus, self.hist_exp = {}, set()   # puuid по Riot ID; чьи истории раскрыты кликом
        self.role_override = None
        self.lola, self.lola_state = {}, {}
        self.import_text = ''
        self.cp_sel = None
        self.phone_srv = None
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
        load_fonts()
        self.root = tk.Tk()
        self.root.report_callback_exception = lambda et, ev, tb: log_error('окно', ev)
        threading.excepthook = lambda a: log_error(f'поток {a.thread.name if a.thread else ""}', a.exc_value)
        self.auto_vars = {k: tk.BooleanVar(value=v) for k, v in self.s['auto_parts'].items()}
        self.root.title(f'LoL Helper {version}')
        try: self.root.iconphoto(True, tk.PhotoImage(file=os.path.join(bundle_dir(), 'icon.png')))   # логотип в заголовке и на панели задач
        except Exception: pass
        self.root.geometry('1060x740')
        self.root.minsize(820, 560)
        self.icons = Icons(self)
        self.set_who(self.s['who'] or 'halch')
        self.build_all()
        self.sync_phone()
        threading.Thread(target=self.poll, daemon=True).start()
        threading.Thread(target=self.load_lanes, daemon=True).start()
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
        self.nav_sync()
        sig, (pw, ph), _ = screens()
        self.ov = {'hints': HintsOverlay(self, (40, int(ph * .30))), 'perf': PerfOverlay(self, (pw - 330, 80)),
                   'lane': LaneOverlay(self, (pw - 330, 300)), 'gold': GoldOverlay(self, (40, int(ph * .55))),
                   'item': ItemOverlay(self, (pw - 330, 400)), 'timers': TimersOverlay(self, (pw - 330, 490)),
                   'arena': ArenaOverlay(self, (pw - 330, 80))}
        self.tab = {'tab': TabPlates(self)}
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
                     bordercolor=C['raise'], lightcolor=C['panel'], darkcolor=C['panel'], troughcolor=C['panel'], focuscolor=C['gold'])
        st.configure('TNotebook', background=C['bg'], borderwidth=0, tabmargins=0)
        st.configure('TNotebook.Tab', background=C['panel'], foreground=C['mute'], padding=(12, 5), bordercolor=C['line'])
        st.map('TNotebook.Tab', background=[('selected', C['line'])], foreground=[('selected', C['gold'])])
        st.configure('Rail.TNotebook', background=C['bg'], borderwidth=0, tabmargins=0, padding=0, bordercolor=C['bg'], lightcolor=C['bg'], darkcolor=C['bg'])
        st.layout('Rail.TNotebook', [('Notebook.client', {'sticky': 'nswe'})])   # без рамки вокруг страницы
        st.layout('Rail.TNotebook.Tab', [])   # вкладки переключает боковое меню
        st.configure('TButton', background=C['raise'], foreground=C['fg'], padding=(14, 7), bordercolor=C['raise'],
                     lightcolor=C['raise'], darkcolor=C['raise'], font=(F['numb'], self.fs(10)))
        st.map('TButton', background=[('active', C['line'])], bordercolor=[('active', C['line'])], foreground=[('active', C['fg'])])
        st.configure('A.TButton', background=C['gold'], foreground=C['on_gold'], bordercolor=C['gold'], lightcolor=C['gold'], darkcolor=C['gold'])
        st.map('A.TButton', background=[('active', C['warn'])], bordercolor=[('active', C['warn'])], foreground=[('active', C['on_gold'])])
        st.configure('TCheckbutton', background=C['bg'], foreground=C['fg'], indicatorbackground=C['panel'], indicatorforeground=C['gold'])
        st.map('TCheckbutton', background=[('active', C['bg'])], indicatorbackground=[('selected', C['gold'])], indicatorforeground=[('selected', C['bg'])])
        st.configure('D.TCheckbutton', background=C['deep'], foreground=C['fg'], indicatorbackground=C['panel'], indicatorforeground=C['gold'])
        st.map('D.TCheckbutton', background=[('active', C['deep'])], indicatorbackground=[('selected', C['gold'])], indicatorforeground=[('selected', C['bg'])])
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
        st.layout('Vertical.TScrollbar', [('Vertical.Scrollbar.trough', {'sticky': 'ns', 'children': [('Vertical.Scrollbar.thumb', {'expand': '1', 'sticky': 'nswe'})]})])
        st.configure('Vertical.TScrollbar', background=C['raise'], troughcolor=C['bg'], bordercolor=C['bg'], lightcolor=C['raise'], darkcolor=C['raise'],
                     gripcount=0, arrowsize=self.fs(6), width=self.fs(6))
        st.configure('H.TLabel', foreground=C['gold'], font=(F['head'], self.fs(13)))
        st.configure('Cap.TLabel', foreground=C['mute'], font=(F['num'], self.fs(8)))
        st.configure('M.TLabel', foreground=C['mute'])
        st.configure('V.TLabel', foreground=C['gold'])

    def set_who(self, who):
        if who not in self.data.d['players']: who = None
        self.player = core.Player(self.data, who) if who else None
        self.who = who
        self.engine = None

    def new_engine(self):
        self.engine = core.Engine(self.data, self.player, enabled=self.hint_flags(''))

    def cached_build(self, champ, role):
        """Сборка по Европе из памяти или с диска (любой давности): в игре важнее быстро, чем свежо."""
        b = self.lola.get((champ, role))
        if b: return b
        try: return json.load(open(os.path.join(self.home, 'lola', f'full_{champ}_{role}.json'), encoding='utf-8'))
        except Exception: return None

    def prep_engine(self, g):
        """В начале игры: порядок умений, ситуативные предметы и темп Изумруда+ для подсказок."""
        self.engine.prepped = True
        b = self.cached_build(g.me['c'], g.role)
        if not b and g.role: self.root.after(0, lambda: self.lola_fetch('build', g.me['c'], g.role)); self.engine.prepped = False
        v = (b or {}).get(self.s['rune_pick']) or b or {}
        self.engine.skills, self.engine.skill_prio = v.get('skills', ''), v.get('skill_prio', '')
        self.engine.situ = (b or {}).get('situ') or []
        lo = self.data.lola.get(f"{g.me['c']}|{g.role}")
        if lo: self.engine.bench = {'cs': lo['cs'], 'min': 28}

    def hint_mode(self, hid, role=None):
        """Режим подсказки: общие — один на все роли, ролевые — свой у каждой роли."""
        if hid not in core.HINT_ROLES: return self.s['hints'].get(hid, 'off')
        role = role or self.s['hint_preset']
        if role not in core.HINT_ROLES[hid]: return 'off'
        dflt = next(h[3] for h in core.HINTS if h[0] == hid)
        return self.s['hints_role'].get(role, {}).get(hid, dflt)

    def hint_flags(self, role):
        return {h: self.hint_mode(h, role) != 'off' for h in core.HINT_IDS}

    SR_ONLY = ('lane', 'gold', 'timers', 'perf', 'item')   # виджеты только для Ущелья: в Арене их нет

    def apply_visibility(self):
        arena = bool(self.last_game and self.last_game.arena)
        for k, w in self.ov.items():
            if k == 'hints': continue
            if self.hidden or not self.s['widgets'].get(k) or not self.last_game or (arena and k in self.SR_ONLY) or (k == 'arena' and not arena): w.withdraw()
            else: w.deiconify()
        if self.hidden: self.ov['hints'].withdraw()

    def arena_tick(self, g):
        """Арена: напоминание о покупке, когда скопилось 1000+ золота (раз в минуту, режим как у подсказки «Следующий предмет»)."""
        mode = self.hint_mode('next_item')
        if mode == 'off' or g.gold < 1000 or time.time() - getattr(self, '_arena_buy', 0) < 60: return
        self._arena_buy = time.time()
        self.ov['hints'].push(f'Есть {int(g.gold)} золота: купи предмет до начала раунда'); self.ov['hints'].show()
        if mode == 'beep': self.voice.beep()
        elif mode == 'voice': self.voice.say('Есть золото, купи предмет')

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
                    if g.me and not getattr(self.engine, 'prepped', False): self.prep_engine(g)
                    self.engine.enabled = self.hint_flags(g.role)
                    hints = [] if g.arena else self.engine.tick(g)   # подсказки Ущелья в Арене не имеют смысла
                    res = next((e.get('Result') for e in g.events if e.get('EventName') == 'GameEnd'), None)
                    if now - last_scout > 90:
                        last_scout = now
                        self.scout = self.fetch_scout(g)
                    if len(self.ranks) < len(g.players): self.fetch_people(g)
                    elif g.ejg and not g.arena and self.engine.jg_plan is None and g.t < 240: self.scout_jungler(g)
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
                        ph = self.client.phase()
                        if ph == 'ChampSelect':
                            sess = self.client.champ_select()
                            if sess:
                                cs = core.parse_champ_select(sess, self.data)
                                cs['allies'] = self.draft_allies(sess)
                                cs['arena'] = self.client.queue() == 1700
                                self.q.put(('draft', cs, None, None))
                        else:
                            if self.draft is not None: self.q.put(('draft', None, None, None))
                            if ph in ('GameStart', 'InProgress'): self.load_scout()
            except Exception as e:
                log_error('опрос клиента', e)
                self.q.put(('error', str(e), None, None))
            time.sleep(1)

    def scout_jungler(self, g):
        """Лесник врагов: как он начинал 2–3 последние игры в лесу (для окна ганка и подсказки)."""
        pu = self.pus.get(g.ejg['riot'])
        if not pu or pu not in self.hraw: self.engine.jg_plan = {}; return
        try: self.engine.jg_plan = self.jg_plan_for(pu) or {}
        except Exception as e: log_error('разведка лесника', e); self.engine.jg_plan = {}

    def jg_plan_for(self, pu):
        if pu in self.jg_cache: return self.jg_cache[pu]
        games = [h for h in (self.hraw.get(pu) or []) if h.get('lane') == 'JUNGLE' and h.get('gid')][:3]
        plan = core.jungle_plan([core.jungle_game(self.client.timeline(h['gid']), self.client.game(h['gid']), pu) for h in games])
        self.jg_cache[pu] = plan
        return plan

    def cid(self, key):
        return next((i for i, c in self.data.ids.items() if c == key), None)

    def fetch_people(self, g):
        """Звание и история последних игр каждого из десяти через клиент (как в профиле). По одному за проход."""
        for p in g.players:
            if p['riot'] in self.ranks: continue
            pu = self.pus.get(p['riot']) or self.client.puuid(p['riot'])
            if pu and pu in self.hraw: raw, self.ranks[p['riot']] = self.hraw[pu], self.rank_pu.get(pu)   # уже скачано на экране загрузки
            else:
                self.ranks[p['riot']] = self.rank_pu[pu] = self.client.rank(pu) if pu else None
                raw = self.client.history(pu) if pu else None
            if pu: self.hraw[pu], self.pus[p['riot']] = raw, pu
            self.hists[p['riot']] = core.summarize_history(raw, self.cid(p['c']), p['pos']) if pu else None
            return

    def draft_allies(self, sess):
        """Союзники в драфте: чемпион (или наведённый), роль, звание и история игр."""
        out = []
        for p in sess.get('myTeam') or []:
            # Riot запрещает раскрывать игроков, которых игра скрыла: у скрытых союзников не берём ни звание, ни историю
            hidden = p.get('nameVisibilityType') == 'HIDDEN' and p.get('cellId') != sess.get('localPlayerCellId')
            pu = None if hidden else p.get('puuid')
            if pu and pu not in self.hraw:
                self.ranks[pu] = self.rank_pu[pu] = self.client.rank(pu)
                self.hraw[pu] = self.client.history(pu)
            champ_id = p.get('championId') or p.get('championPickIntent') or 0
            out.append({'c': self.data.ids.get(str(champ_id)), 'pos': core.LCU_ROLE.get((p.get('assignedPosition') or '').lower(), ''),
                        'rank': self.ranks.get(pu), 'hist': core.summarize_history(self.hraw.get(pu), champ_id,
                                                                   core.LCU_ROLE.get((p.get('assignedPosition') or '').lower(), '')) if pu else None,
                        'me': p.get('cellId') == sess.get('localPlayerCellId'), 'pu': pu})
        return out

    def load_scout(self):
        """Экран загрузки: все десять из клиента. Звание и история — по одному игроку за проход, как в игре."""
        ps = self.client.loading()
        if not ps: return
        mine = (self.account or {}).get('puuid')
        my_team = next((p['team'] for p in ps if p['pu'] and p['pu'] == mine), 100)
        todo = next((p['pu'] for p in ps if p['pu'] and p['pu'] not in self.hraw), None)
        if todo:
            self.rank_pu[todo] = self.client.rank(todo)
            self.hraw[todo] = self.client.history(todo)
        else:   # все истории есть: заранее смотрим, как начинает лесник врагов
            jg = next((p['pu'] for p in ps if p['pu'] and p['team'] != my_team and p['pos'] == 'jungle'), None)
            if jg and jg not in self.jg_cache:
                try: self.jg_plan_for(jg)
                except Exception as e: log_error('разведка лесника', e); self.jg_cache[jg] = None
        out = []
        for p in ps:
            pu, pos = p['pu'], core.LCU_ROLE.get(p['pos'], '')
            out.append({'c': self.data.ids.get(str(p['champ'])), 'pos': pos, 'col': 0 if p['team'] == my_team else 1, 'pu': pu,
                        'me': bool(pu) and pu == mine, 'name': p['name'], 'ok': not pu or pu in self.hraw, 'rank': self.rank_pu.get(pu),
                        'hist': core.summarize_history(self.hraw.get(pu), p['champ'], pos) if pu else None})
        self.q.put(('load', out, None, None))

    def on_loading(self, ps):
        if self.last_game is not None: return
        if not self.dash: self.open_dash()
        try: self.dash.show_loading(ps)
        except Exception as e: log_error('второе окно: загрузка', e)
        self.status.configure(text='Экран загрузки: разведка во втором окне')

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
                elif kind == 'load': self.on_loading(a)
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
            self.apply_text(h)
            self.ov['hints'].push(h.text)
            if self.dash: self.dash.add_log(g.t, h.text)
            if mode == 'beep': self.voice.beep()
            elif mode == 'voice': self.voice.say(h.say)
        if hints: self.ov['hints'].show()
        if g.arena: self.arena_tick(g)
        for k in ('perf', 'lane', 'gold', 'item', 'timers', 'arena'):
            if not self.s['widgets'].get(k) or (g.arena and k in self.SR_ONLY) or (k == 'arena' and not g.arena): continue
            try: self.ov[k].show(g)
            except Exception as e: log_error(f'виджет {k}', e)
        if self.dash and g.arena:
            if first: self.dash.idle(); self.dash.head.configure(text='Арена'); self.dash.sub.configure(text='Окно игры для Арены пока не сделано.')
        elif self.dash:
            try: self.dash.show(g, self.scout, self.ranks, self.hists)
            except Exception as e: log_error('второе окно: игра', e)
        self.status.configure(text=f'Игра: {core.mmss(g.t)} · {self.data.cn(g.me["c"]) if g.me else ""}')

    def arena_games(self):
        return (self.data.d.get('arena') or {}).get(self.who or '', [])

    def arena_post(self):
        """Итог Арены: место, урон и счёт из истории клиента рядом с твоими средними по Арене."""
        pu = (self.account or {}).get('puuid')
        def job():
            hist = self.client.history(pu, 3) if pu else None
            h = next((x for x in hist or [] if x.get('q') == 1700), None)
            res = core.arena_result(self.client.game(h['gid']), pu) if h else None
            if res: self.root.after(0, lambda: show_arena_post(self, res))
        threading.Thread(target=job, daemon=True).start()

    def on_end(self):
        g = self.last_game
        if g and g.arena and self.s['postgame'] and self.hint_mode('postgame') != 'off': self.root.after(20000, self.arena_post)
        if g and not g.arena and self.engine and self.s['postgame'] and g.t > 300 and self.hint_mode('postgame') != 'off':
            res = core.postgame(self.engine, g, self.player)
            if res: show_postgame(self, res, self.result)
        self.last_game, self.result, self.engine, self.scout = None, None, None, {}
        self.hraw, self.rank_pu, self.jg_cache = {}, {}, {}   # к следующей игре история у всех уже другая
        if self.pending_data: self.reload_data(self.pending_data)
        self.apply_visibility()
        for w in self.tab.values(): w.withdraw()
        if self.dash: self.dash.idle()
        self.status.configure(text='Игра закончилась')
        self.root.after(30000, self.hist_refresh)   # LP и игра появляются в клиенте не сразу

    # ---------------- Драфт ----------------
    def on_draft(self, cs):
        """Драфт целиком во втором окне (дашборд): карточки, линия, импорт, кого взять и банить."""
        self.draft = cs
        if cs is None:
            if self.phone_srv: self.phone_srv.state = {'mode': 'idle'}
            self.role_override = None
            if self.dash and self.draft_sig not in (None, 'none'): self.dash.idle()
            self.draft_sig = 'none'
            self.imported = None; return
        if not self.dash: self.open_dash()
        sig = json.dumps([cs['role'], self.role_override, cs['me'], cs['enemies'], sorted(cs['unavailable']), len(self.lola), [(a['c'], bool(a['rank']), bool(a.get('hist'))) for a in cs.get('allies', [])]], default=str)
        if sig == self.draft_sig: return
        self.draft_sig = sig
        p, d = self.player, self.data
        self.status.configure(text='Выбор чемпионов: всё во втором окне')
        if not p:
            self.dash.clear('idle')
            self.dash.head.configure(text='Выбор чемпионов', fg=C['gold'])
            self.dash.sub.configure(text='Аккаунта нет в статистике сайта: выбери игрока на вкладке «Статус» основного окна'); return
        if cs.get('arena'):
            try: self.dash.show_arena(cs)
            except Exception as e: log_error('второе окно: Арена', e)
            return
        role, how = self.draft_role(cs)
        if role == 'ARAM':
            try: self.dash.show_aram(cs)
            except Exception as e: log_error('второе окно: ARAM', e)
            self.phone_draft(cs, {'role': 'ARAM', 'picks': [], 'opp': None}, [])
            auto = tuple(k for k, v in self.s['auto_parts'].items() if v)
            if auto and cs['locked'] and cs['me'] and self.imported != cs['me']: self.do_import(auto)
            return
        r = core.draft_suggest(p, role, cs['enemies'], cs['unavailable'])
        r['role'], r['how'] = role, how
        for a in cs.get('allies') or []:
            if a.get('me') and (not a.get('pos') or a.get('auto')): a['pos'], a['auto'] = role, True
        pool = core.ban_pool(p, role)
        cnt = {m: core.lola_counters(self.lola_fetch('counter', m, role), d) for m in pool}
        bans = core.ban_suggest(p, cs['unavailable'], 3, role, {m: v for m, v in cnt.items() if v})
        try: self.dash.show_draft(cs, r, bans)
        except Exception as e: log_error('второе окно: драфт', e)
        self.phone_draft(cs, r, bans)
        auto = tuple(k for k, v in self.s['auto_parts'].items() if v)
        if auto and cs['locked'] and cs['me'] and self.imported != cs['me']: self.do_import(auto)

    def draft_role(self, cs):
        """Линия для подсказок: выбранная вручную, назначенная клиентом или основная линия игрока."""
        if cs.get('aram'): return 'ARAM', 'ARAM'
        if self.role_override: return self.role_override, 'выбрана вручную'
        if cs['role']: return cs['role'], 'назначена клиентом'
        if cs['me'] and self.player:
            on = {r: len(self.player.on(cs['me'], r)) for r in core.ROLES}
            if max(on.values()) >= 3: return max(on, key=on.get), f'твоя линия на {self.data.cn(cs["me"])}'
        if self.player:
            cnt = {r: len(self.player.on(pos=r)) for r in core.ROLES}
            if max(cnt.values()): return max(cnt, key=cnt.get), 'твоя основная'
        return 'TOP', 'по умолчанию'

    TIERS = ['IRON', 'BRONZE', 'SILVER', 'GOLD', 'PLATINUM', 'EMERALD', 'DIAMOND', 'MASTER', 'GRANDMASTER', 'CHALLENGER']

    def next_tier(self):
        """Ранг на ступень выше твоего: (слаг lolalytics, название). Мастер и выше сравниваются с собой."""
        t = (self.my_rank or {}).get('tier')
        if not t:
            ru = tier_of((self.data.d['players'].get(self.who or '') or {}).get('rank'))
            t = next((k for k, v in TIER_RU.items() if v == ru), None)
        if t not in self.TIERS: return None, None
        i = self.TIERS.index(t)
        up = self.TIERS[i if i >= 7 else i + 1]
        return up.lower(), TIER_RU[up]

    def tier_bench(self, champ, role):
        """Средние ранга выше на чемпионе и роли (lolalytics, грузится в фоне): CS, золото и KDA в минуту за ~28 минут игры."""
        slug, name = self.next_tier()
        if not slug or role not in core.ROLES: return None
        b = self.lola_fetch('tier_' + slug, champ, role)
        if not b: return None
        return {'tier': name, 'csm': b['cs'] / 28, 'gpm': b['g'] / 28, 'kda': (b['k'] + b['a']) / max(.1, b['d'])}

    def role_pil(self, role, k=.5):
        """Значок роли в золоте для карточек виджетов (PIL)."""
        if Image is None or not role: return None
        im = self.icons._pil('role', role)
        return render.tint(im, C['gold'], max(10, int(self.s['icon'] * k * self.s['scale'] / 100))) if im else None

    def lola_build(self, champ, role):
        """Руны и сборка по Европе (lolalytics, EUW Изумруд+). Нет в памяти — грузим в фоне и перерисовываем драфт."""
        return self.lola_fetch('build', champ, role)

    def lola_fetch(self, kind, champ, role):
        """Данные lolalytics в фоне с кешем на 12 часов: kind='build' — руны и сборка, 'counter' — матчапы, 'build-team' — синергия.
        Пока грузится — None; по готовности драфт перерисуется."""
        if not champ or not role: return None
        k = (champ, role) if kind == 'build' else (kind, champ, role)
        if k in self.lola: return self.lola[k]
        if self.lola_state.get(k): return None
        self.lola_state[k] = 'loading'
        name = f'full_{champ}_{role}.json' if kind == 'build' else f'{kind}_{champ}_{role}.json'
        path = os.path.join(self.home, 'lola', name)
        def job():
            b = None
            try:
                if os.path.exists(path) and time.time() - os.path.getmtime(path) < 12 * 3600:
                    b = json.load(open(path, encoding='utf-8'))
                else:
                    get = lambda url: urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=20).read().decode('utf-8', 'ignore')
                    if kind == 'build' and role == 'ARAM':   # ARAM: в API нет, только страница сборки (все ранги)
                        b = core.parse_lola_build(get(core.lola_url(champ, role)))
                    elif kind == 'arena':   # чемпион в Арене: только винрейт и число игр
                        b = core.parse_lola_arena(get(f"https://lolalytics.com/lol/{core.LOLA_FIX.get(champ, champ.lower())}/arena/build/"))
                    elif kind.startswith('tier_'):   # средние ранга выше со страницы сборки
                        b = core.parse_lola_avg(get(core.lola_url(champ, role).replace('tier=emerald_plus', 'tier=' + kind[5:])))
                    elif kind == 'build':   # две сборки по Европе из API, иначе одна со страницы сборки
                        try: b = core.parse_lola_full(json.loads(get(core.lola_api('build-full', champ, role, 'euw'))), self.data)
                        except Exception as e: log_error(f'lolalytics build-full {champ} {role}', e); b = None
                        b = b or core.parse_lola_build(get(core.lola_url(champ, role)))
                    else: b = json.loads(get(core.lola_api(kind, champ, role)))
                    if kind == 'build-team': b = {'team': b.get('team')} if b.get('team') else None
                    if kind == 'counter': b = {'counters': b.get('counters')} if b.get('counters') else None
                    if b:
                        os.makedirs(os.path.dirname(path), exist_ok=True)
                        json.dump(b, open(path, 'w', encoding='utf-8'))
            except Exception as e:
                log_error(f'lolalytics {kind} {champ} {role}', e)
                try: b = json.load(open(path, encoding='utf-8'))   # старый кеш лучше, чем ничего
                except Exception: b = None
            def done():
                if b: self.lola[k] = b
                self.lola_state[k] = 'ok' if b else 'fail'
                self.redraw_draft()
                if self.cp_sel and (champ, role) == self.cp_sel: self.cp_show()
            self.root.after(0, done)
        threading.Thread(target=job, daemon=True).start()
        return None

    def redraw_draft(self):
        """Перерисовать драфт один раз, даже если несколько загрузок lolalytics закончились подряд (иначе окно моргает)."""
        if getattr(self, '_redraw_job', None): return
        def go():
            self._redraw_job = None
            self.draft_sig = None
            if self.dash: self.dash.draft_sig = None
            if self.draft: self.on_draft(self.draft)
        self._redraw_job = self.root.after(400, go)

    def matchup_lines(self, p, col, allies, r):
        """Строки под чемпионом в драфте: у врага — кто его контрит (и кто из твоего пула), у союзника — синергия с командой."""
        d, pl = self.data, self.player
        c, pos = p.get('c'), p.get('pos')
        if not c or not pos: return []
        myrole = r.get('role')
        if col == 1:
            cnt = core.lola_counters(self.lola_fetch('counter', c, pos), d)
            main = d.role_of_champ(c)
            if not cnt and main and main != pos and self.lola_state.get(('counter', c, pos)) == 'ok':
                cnt = core.lola_counters(self.lola_fetch('counter', c, main), d)   # на этой линии его почти не играют
            if not cnt: return [('Контрпики: загружаю lolalytics…', 'mute')] if self.lola_state.get(('counter', c, pos)) == 'loading' else []
            pool = pl.pool.get(myrole, []) if pl and pos == myrole else []
            best, mine = core.counter_picks(cnt, 3, pool)
            out = []
            if best: out.append(('Контрпики', [(x, f'{wr:.0f}% (+{dd:.1f})', 'blue') for x, dd, wr in best]))
            if mine:
                mine.sort(key=lambda x: -x[1])
                out.append(('Из твоего пула', [(x, f'{wr:.0f}% ({dd:+.1f})', 'good' if dd > .5 else 'bad' if dd < -.5 else 'fg') for x, dd, wr in mine[:3]]))
            return out
        team = core.lola_team(self.lola_fetch('build-team', c, pos), d)
        if not team: return []
        out, parts = [], []
        for a in allies:
            if a is p or not a.get('c') or not a.get('pos'): continue
            v = team.get((a['pos'], a['c']))
            if v: parts.append((v[1], (a['c'], f"{v[0]:.0f}% ({v[1]:+.1f})", 'good' if v[1] > .5 else 'bad' if v[1] < -.5 else 'fg')))
        if parts:
            parts.sort(key=lambda x: -x[0])
            out.append(('Синергия', [t for _, t in parts]))
        me = next((a for a in allies if a.get('me')), None)
        if pl and me and not me.get('c') and not p.get('me') and myrole:
            pool = [(team[(myrole, x)][1], x) for x in pl.pool.get(myrole, []) if (myrole, x) in team]
            if pool:
                pool.sort(reverse=True)
                out.append(('Тебе с ним из пула', [(x, f'({v:+.1f})', 'good' if v > .5 else 'fg') for v, x in pool[:4]]))
        return out

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

    def set_rune_pick(self, val):
        self.s['rune_pick'] = val; self.s.save()
        self.imported = None
        if self.dash: self.dash.draft_sig = None
        self.draft_sig = None
        if self.draft: self.on_draft(self.draft)

    def sync_phone(self):
        """Включить или выключить сервер для телефона по настройке. Адрес постоянный: токен хранится в настройках."""
        if self.s['phone'] and not self.phone_srv:
            try:
                self.phone_srv = phone.PhoneServer(self.s['phone_port'], lambda: self.root.after(0, self.do_import), self.s['phone_token'] or None)
                if self.s['phone_token'] != self.phone_srv.token: self.s['phone_token'] = self.phone_srv.token; self.s.save()
            except Exception as e:
                log_error('сервер для телефона', e); self.phone_srv = None
        elif not self.s['phone'] and self.phone_srv:
            self.phone_srv.stop(); self.phone_srv = None
        if getattr(self, 'phone_lbl', None):
            try: self.phone_lbl.configure(text=(f'Открой на телефоне: {self.phone_srv.url}' if self.phone_srv else
                                                'Выключено' if not self.s['phone'] else f"Не удалось открыть порт {self.s['phone_port']}: подробности в журнале ошибок"))
            except tk.TclError: pass

    def phone_draft(self, cs, r, bans):
        """То же, что во втором окне, текстом для телефона."""
        if not self.phone_srv: return
        d, me, role = self.data, cs.get('me'), r.get('role')
        st = {'mode': 'draft', 'me': d.cn(me) if me else '', 'imp': self.import_text,
              'title': 'ARAM' if role == 'ARAM' else 'Драфт' + (f" · {core.ROLE_RU.get(role, '')}" if role else ''),
              'sub': (f"Оппонент: {d.cn(r['opp'])}" if r.get('opp') else 'Оппонент ещё не выбран') if role != 'ARAM' else 'Сборка ARAM по всем рангам',
              'picks': [(x['name'], x['why']) for x in r.get('picks') or []], 'bans': [(d.cn(c), why) for c, sc, why in bans or []]}
        if me and r.get('opp'):
            cnt = core.lola_counters(self.lola.get(('counter', r['opp'], role)), d)
            if me in cnt: st['mu'] = {'wr': f"{100 - cnt[me][0]:.1f}%", 'text': f"{cnt[me][2]} игр, Европа Изумруд+"}
        full = self.lola.get((me, role)) if me else None
        if full:
            v = full.get(self.s['rune_pick']) or full
            st['build'] = [('Заклинания', ', '.join(core.SPELL_RU.get(x, x) for x in v.get('spells', [])[:2])),
                           ('Старт', ', '.join(d.iname(i) for i in v.get('start', []))),
                           ('Основа', ' → '.join(d.iname(i) for i in core.lola_build_items(v)))]
            if v.get('skill_prio'): st['build'].append(('Умения', ' › '.join(v['skill_prio'])))
            st['skills'] = v.get('skills', '')
        allies = [a['c'] for a in cs.get('allies') or [] if a.get('c') and not a.get('me')]
        adv = core.comp_advice(d, allies, role, (self.player.pool.get(role) if self.player else []) or [])
        if adv: st['comp'] = [adv[0] + ('. Из пула: ' + ', '.join(d.cn(c) for c in adv[1]) if adv[1] else '')]
        self.phone_srv.state = st

    def set_import_msg(self, text):
        self.import_text = text
        if self.phone_srv and self.phone_srv.state.get('mode') == 'draft': self.phone_srv.state['imp'] = text
        if self.dash and getattr(self.dash, 'import_lbl', None):
            try:
                self.dash.import_lbl.configure(text=text, fg=C['bad'] if 'не получилось' in text else C['mute'])
                self.dash.import_err.pack(side='right', padx=(8, 0)) if 'не получилось' in text else self.dash.import_err.pack_forget()
            except tk.TclError: pass

    def report_text(self):
        """Отчёт для Claude: версия, система, состояние клиента и последние строки журналов."""
        h = self.home
        try: ph = self.client.phase()
        except Exception: ph = '?'
        L = [f'LoL Helper {self.version} · {platform.platform()} · Python {platform.python_version()}',
             f"Экран: {screens()[0] if os.name == 'nt' else '?'} · масштаб {self.s['scale']}% · клиент {'найден' if self.client.port else 'не найден'}, фаза {ph}",
             f"Аккаунт: {(self.account or {}).get('riot', 'нет')} · статистика: {self.who}", '']
        for name, n in (('errors.log', 60), ('import.log', 15), ('update.log', 10), ('crash.txt', 40), ('site_error.txt', 20)):
            lines = tail(os.path.join(h, name), n)
            if lines: L += [f'--- {name} (последние {len(lines)} строк)'] + lines + ['']
        if len(L) == 4: L.append('Журналы пустые: ошибок не было.')
        return '\n'.join(L)

    def copy_report(self):
        self.root.clipboard_clear(); self.root.clipboard_append(self.report_text())
        self.status.configure(text='Отчёт скопирован: вставь его в чат с Claude')
        if getattr(self, 'rep_msg', None):
            try: self.rep_msg.configure(text='Скопировано. Вставь в чат с Claude (Ctrl+V).')
            except tk.TclError: pass

    def do_import(self, parts=('runes', 'items', 'spells')):
        """Импорт в клиент: руны, наборы предметов и заклинания призывателя. parts — что именно (для автоимпорта по галкам)."""
        cs, p = self.draft, self.player
        if not cs or not cs['me'] or not p:
            self.set_import_msg('Сначала выбери чемпиона'); return
        me = cs['me']
        eu = self.lola_build(me, self.draft_role(cs)[0])
        ev = (eu.get(self.s['rune_pick']) or eu) if eu else None
        out = []
        def attempt(name, fn):
            self.client.last_error = ''
            try: ok = fn()
            except Exception as e: ok = False; self.client.last_error = self.client.last_error or repr(e)
            out.append(f"{name}: {'готово' if ok else 'не получилось' + (f' ({self.client.last_error})' if self.client.last_error else '')}")
            if not ok: log_error(f'импорт {name}, {me}', self.client.last_error or 'клиент ответил отказом без текста ошибки')
        if 'runes' in parts:
            def runes():
                if ev: return self.client.set_runes(self.data.cn(me), ev['prim'], ev['sec'], ev['perks'], ev['shards'] if len(ev['shards']) == 3 else None)
                ru = p.best_runes(me)
                return bool(ru) and self.client.set_runes(self.data.cn(me), ru['prim'], ru['sec'], ru['perks'])
            src = ('по Европе, ' + ('лучший винрейт' if self.s['rune_pick'] == 'win' else 'популярные')) if eu else 'из твоих игр'
            attempt(f'Руны ({src})', runes)
        if 'items' in parts:
            def items():
                acc = self.account or self.client.me() or {}
                cid = next((k for k, v in self.data.ids.items() if v == me), None)
                if eu: sets = core.lola_item_sets(eu, self.data.cn(me))
                else: sets = [(self.data.cn(me), [('Сборка из твоих побед', p.best_build(me)), ('Тотемы', [2055, 3340, 3364])])]
                return bool(cid and sets[0][1][0][1]) and self.client.set_items(acc.get('id'), cid, sets, None)
            attempt('Предметы (2 набора)' if eu else 'Предметы', items)
        if 'spells' in parts and ev and ev.get('spells'):
            ids = [core.SPELL_ID.get(x) for x in ev['spells'][:2]]
            attempt('Заклинания (' + ', '.join(core.SPELL_RU.get(x, x) for x in ev['spells'][:2]) + ')',
                    lambda: None not in ids and self.client.set_spells(*ids))
        self.imported = me
        msg = ' · '.join(out)
        self.set_import_msg(msg)
        try:
            with open(os.path.join(self.home, 'import.log'), 'a', encoding='utf-8') as f: f.write(time.strftime('%Y-%m-%d %H:%M:%S ') + me + ' ' + msg + '\n')
        except Exception: pass

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
        drag = bool(combo_down(k.get('drag')) and self.last_game) or self.demo_on   # Alt двигает виджеты только в игре
        if drag != self.keys_prev.get('drag'):
            self.set_unlocked(drag)
            self.keys_prev['drag'] = drag
        if drag: return self.root.after(40, self.keys)
        tab = self.s['scoreboard'] and self.last_game and not self.last_game.arena and not self.hidden and combo_down(k.get('scoreboard')) and game_focused()
        if tab:
            if not self.keys_prev.get('tab') or time.time() - self.keys_prev.get('tab_t', 0) > 1:
                for w in self.tab.values():
                    try: w.show(self.last_game); w.deiconify()
                    except Exception as e: log_error('Tab', e)
                self.keys_prev['tab_t'] = time.time()
        elif self.keys_prev.get('tab'):
            for w in self.tab.values(): w.withdraw()
        self.keys_prev['tab'] = bool(tab)
        self.root.after(40, self.keys)

    def set_unlocked(self, on):
        """Режим расстановки: все виджеты видны, ловят мышь; без игры показывают пример содержимого."""
        wins = dict(self.tab if self.s['scoreboard'] else {}, **self.ov)   # рамка Tab снизу, виджеты поверх неё
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
    NAV = [('Главная', 'home'), ('История матчей', 'list'), ('Чемпион', 'search'), ('Подсказки', 'bulb'), ('Виджеты и окна', 'window'), ('Вид', 'look'),
           ('Звук', 'sound'), ('Клавиши', 'keys'), ('Таймеры', 'clock'), ('Обновления', 'update')]
    NAV_GROUPS = {0: 'Игра', 3: 'Настройки'}   # подписи групп перед пунктами меню

    def build_panel(self):
        r = self.root
        self.pages, self.nav_items = [], []
        rail = tk.Frame(r, bg=C['deep'], width=self.fs(210), padx=10, pady=14)
        rail.pack(side='left', fill='y'); rail.pack_propagate(False)
        logo = self.logo_img()
        tk.Label(rail, text='  LOL HELPER', image=logo or '', compound='left', bg=C['deep'], fg=C['gold'],
                 font=(F['head'], self.fs(15)), anchor='w').pack(fill='x', padx=6, pady=(0, 14))
        main = tk.Frame(r, bg=C['bg']); main.pack(side='left', fill='both', expand=True)
        top = tk.Frame(main, bg=C['bg']); top.pack(fill='x', padx=22, pady=(16, 4))
        self.page_title = tk.Label(top, text='', bg=C['bg'], fg=C['gold'], font=(F['head'], self.fs(19)))
        self.page_title.pack(side='left')
        pill = tk.Frame(top, bg=C['panel'], highlightthickness=0, padx=12, pady=4); pill.pack(side='right')
        self.status_dot = tk.Label(pill, text='●', bg=C['panel'], fg=C['mute'], font=(F['font'], self.fs(9))); self.status_dot.pack(side='left')
        self.status = tk.Label(pill, text='Ищу клиент League of Legends…', bg=C['panel'], fg=C['mute'], font=(F['font'], self.fs(10)))
        self.status.pack(side='left', padx=(4, 0))
        self.banner = tk.Frame(main, bg=C['gold'], padx=12, pady=6)
        self.banner_lbl = tk.Label(self.banner, bg=C['gold'], fg=C['on_gold'], font=(F['font'], self.fs(11), 'bold'), anchor='w')
        self.banner_lbl.pack(side='left', fill='x', expand=True)
        self.banner_btn = tk.Button(self.banner, bg=C['bg'], fg=C['gold'], activebackground=C['panel'], activeforeground=C['gold'],
                                    relief='flat', font=(F['font'], self.fs(10), 'bold'), padx=12, cursor='hand2')
        self.nb = ttk.Notebook(main, style='Rail.TNotebook'); self.nb.pack(fill='both', expand=True, padx=8, pady=(4, 8))
        self.tab_status = self.page('Главная'); self.tab_hist = self.page('История матчей'); self.tab_champ = self.page('Чемпион')
        self.tab_hints = self.page('Подсказки'); self.tab_win = self.page('Окна'); self.tab_look = self.page('Вид')
        self.tab_voice = self.page('Звук'); self.tab_keys = self.page('Клавиши')
        self.tab_time = self.page('Таймеры'); self.tab_upd = self.page('Обновления')
        for i, (name, ic) in enumerate(self.NAV[:-1]):
            if i in self.NAV_GROUPS:
                tk.Label(rail, text=self.NAV_GROUPS[i].upper(), bg=C['deep'], fg=C['mute'], font=(F['num'], self.fs(9)), anchor='w').pack(fill='x', padx=8, pady=(10 if i else 0, 2))
            self.nav_item(rail, i, name, ic)
        tk.Frame(rail, bg=C['deep']).pack(fill='both', expand=True)
        low = tk.Frame(rail, bg=C['deep']); low.pack(fill='x', side='bottom')
        tk.Label(low, text=self.version, bg=C['deep'], fg=C['mute'], font=(F['num'], self.fs(9))).pack(side='right', padx=(0, 6))
        self.nav_item(low, len(self.NAV) - 1, self.NAV[-1][0], self.NAV[-1][1])
        self.nb.bind('<<NotebookTabChanged>>', lambda e: self.nav_sync())
        self.build_status(); self.build_history(); self.build_champ(); self.build_hints(); self.build_windows(); self.build_look()
        self.build_voice(); self.build_keys(); self.build_timers(); self.build_updates()
        if getattr(self, 'upd', None): self.update_state(*self.upd)

    def logo_img(self):
        if Image is None: return None
        from PIL import ImageDraw
        return self.keep(ImageTk.PhotoImage(render.logo(self.fs(26), C)))

    def keep(self, ph):
        self.__dict__.setdefault('_imgs', []).append(ph); return ph

    def nav_item(self, rail, i, name, ic):
        icons = {0: None, 1: None}
        lb = tk.Label(rail, text=name, bg=C['deep'], fg=C['fg'], anchor='w', font=(F['font'], self.fs(11)), padx=10, pady=self.fs(6), cursor='hand2')
        lb.pack(fill='x', pady=1)
        lb.bind('<Button-1>', lambda e, i=i: self.nb.select(i))
        lb.bind('<Enter>', lambda e: lb.configure(bg=C['panel']) if lb.cget('fg') != C['gold'] else None)
        lb.bind('<Leave>', lambda e: self.nav_sync())
        self.nav_items.append((lb, icons))

    def nav_sync(self):
        try: cur = self.nb.index('current')
        except Exception: return
        for i, (lb, icons) in enumerate(self.nav_items):
            on = i == cur
            lb.configure(bg=C['raise'] if on else C['deep'], fg=C['gold'] if on else C['fg'])
        self.page_title.configure(text=self.NAV[cur][0].upper())

    def page(self, name, scroll=True):
        """Вкладка панели; с прокруткой колесом мыши, если содержимое не помещается."""
        outer = tk.Frame(self.nb, bg=C['bg'], padx=14, pady=6); self.nb.add(outer, text=name)
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
                try: top = e.widget.winfo_toplevel()
                except Exception: top = None
                if self.dash and top is self.dash: c = self.dash.cv   # колесо над вторым окном — крутим его
                else: c = self.canvases.get(self.nb.select())
                if c and c.winfo_exists() and c.bbox('all') and c.bbox('all')[3] > c.winfo_height(): c.yview_scroll(-e.delta // 120, 'units')
            self.root.bind_all('<MouseWheel>', wheel)
        inner.outer = outer
        return inner

    def h(self, parent, text): ttk.Label(parent, text=text.upper(), style='H.TLabel').pack(anchor='w', pady=(12, 4))

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

    # ---------------- История матчей ----------------
    def build_history(self):
        f = self.tab_hist
        row = tk.Frame(f, bg=C['bg']); row.pack(anchor='w', fill='x')
        ttk.Button(row, text='Обновить', command=self.hist_refresh).pack(side='left')
        ttk.Button(row, text='Сайт со статистикой', command=self.open_site).pack(side='left', padx=8)
        self.hist_msg = self.dl(row, '', 'mute', 10); self.hist_msg.pack(side='left', padx=8)
        self.note(f, 'Последние игры из клиента. Нажми на игру — откроются обе команды и короткий разбор. '
                     'LP за игру программа видит, только если была запущена до и после неё.')
        self.hist_box = tk.Frame(f, bg=C['bg']); self.hist_box.pack(anchor='w', fill='x', pady=(6, 0))
        self.hist_data = []
        self.root.after(4000, self.hist_refresh)

    # --- страница чемпиона вне драфта (как у U.GG и Mobalytics): сборка, умения, матчапы и твоя статистика
    def build_champ(self):
        f = self.tab_champ
        names = sorted(((self.data.cn(k), k) for k in self.data.ids.values()), key=lambda x: x[0])
        self.cp_names = dict(names)
        row = tk.Frame(f, bg=C['bg']); row.pack(anchor='w', fill='x')
        self.cp_var = tk.StringVar()
        cb = ttk.Combobox(row, textvariable=self.cp_var, values=[n for n, _ in names], width=24); cb.pack(side='left')
        def typed(e=None):   # поиск по первым буквам
            q = self.cp_var.get().strip().lower()
            cb.configure(values=[n for n, _ in names if q in n.lower()] or [n for n, _ in names])
        cb.bind('<KeyRelease>', typed)
        cb.bind('<<ComboboxSelected>>', lambda e: self.cp_pick(self.cp_names.get(self.cp_var.get()), None))
        cb.bind('<Return>', lambda e: self.cp_pick(next((k for n, k in names if n.lower().startswith(self.cp_var.get().strip().lower())), None), None))
        self.cp_roles = tk.Frame(row, bg=C['bg']); self.cp_roles.pack(side='left', padx=12)
        self.note(f, 'Найди чемпиона: руны, сборка и умения по Европе (Изумруд+, lolalytics), сложные и удобные матчапы, твоя статистика на нём.')
        self.cp_box = tk.Frame(f, bg=C['bg']); self.cp_box.pack(fill='x', pady=(8, 0))
        self.cp_sel = None

    def cp_pick(self, champ, role):
        if not champ: return
        role = role or self.data.role_of_champ(champ) or 'TOP'
        self.cp_sel = (champ, role)
        for w in self.cp_roles.winfo_children(): w.destroy()
        for r in core.ROLES:
            on = r == role
            b = tk.Label(self.cp_roles, text=core.ROLE_RU[r].capitalize(), bg=C['gold'] if on else C['panel'], fg=C['on_gold'] if on else C['mute'],
                         font=(F['font'], self.fs(10), 'bold'), padx=self.fs(10), pady=self.fs(3), cursor='hand2')
            b.pack(side='left', padx=1); b.bind('<Button-1>', lambda e, r=r: self.cp_pick(champ, r))
        self.cp_show()

    def cp_show(self):
        if not self.cp_sel: return
        champ, role = self.cp_sel
        box, d, fn, fs = self.cp_box, self.data, F['font'], self.fs
        full = self.lola_fetch('build', champ, role)
        cnt = core.lola_counters(self.lola_fetch('counter', champ, role), d)
        def draw():
            for w in box.winfo_children(): w.destroy()
            hd = self.card(box, C['raise'], (16, 12)); hd.pack(fill='x')
            tk.Label(hd, image=self.img('champ', champ, 1.6) or '', bg=C['raise']).pack(side='left', padx=(0, 14))
            mid = tk.Frame(hd, bg=C['raise']); mid.pack(side='left')
            tk.Label(mid, text=d.cn(champ), bg=C['raise'], fg=C['fg'], font=(F['num'], fs(20), 'bold')).pack(anchor='w')
            eu = f"Европа, Изумруд+: {full['wr']:.1f}% · {full['games']} игр" if full and full.get('wr') and full.get('games') else 'Европа, Изумруд+: загружаю…'
            tk.Label(mid, text=f'{core.ROLE_RU[role]} · {eu}', bg=C['raise'], fg=C['mute'], font=(fn, fs(10))).pack(anchor='w')
            if self.player:
                gs = self.player.on(champ)
                if gs:
                    w = sum(g['w'] for g in gs); kda = sum((g['k'] or 0) + (g['a'] or 0) for g in gs) / max(1, sum(g['d'] or 0 for g in gs))
                    tk.Label(mid, text=f'Ты: {len(gs)} игр, {w}–{len(gs) - w} ({w / len(gs) * 100:.0f}%), KDA {kda:.1f}', bg=C['raise'], fg=C['gold'],
                             font=(fn, fs(10), 'bold')).pack(anchor='w')
            col = tk.Frame(box, bg=C['bg']); col.pack(fill='x')
            from types import SimpleNamespace
            Dashboard.build_box(SimpleNamespace(app=self), col, champ, full, role)
            if cnt:
                rows = sorted(cnt.items(), key=lambda kv: kv[1][0])
                grid = tk.Frame(box, bg=C['bg']); grid.pack(fill='x', pady=(10, 0))
                for i, (title, part, colr) in enumerate((('Сложные матчапы', rows[:6], 'bad'), ('Удобные матчапы', rows[::-1][:6], 'good'))):
                    c = self.card(grid); c.grid(row=0, column=i, sticky='nsew', padx=(0 if i == 0 else 10, 0)); grid.columnconfigure(i, weight=1, uniform='m')
                    self.cap(c, title).pack(anchor='w', pady=(0, 4))
                    for e, (wr, d2, n) in part:
                        tk.Label(c, text=f'  {d.cn(e)}   {wr:.1f}% · {n} игр', image=self.img('champ', e, .6) or '', compound='left', bg=C['panel'],
                                 fg=C[colr], font=(fn, fs(10), 'bold'), anchor='w').pack(anchor='w', pady=1)
            else:
                self.dl(box, 'Матчапы: ' + ('не удалось загрузить lolalytics' if self.lola_state.get(('counter', champ, role)) == 'fail' else 'загружаю…'), 'mute', 10).pack(anchor='w', pady=(8, 0))
        no_flicker(self.root, draw)

    def lp_snaps(self, rank=None):
        """Снимки звания [время мс, ladder] в %APPDATA%/LoLHelper/lp.json; с rank — дописать новый, если LP изменились."""
        path = os.path.join(self.home, 'lp.json')
        try: snaps = json.load(open(path, encoding='utf-8'))
        except Exception: snaps = []
        v = core.ladder(rank)
        if v is not None and (not snaps or snaps[-1][1] != v or time.time() * 1000 - snaps[-1][0] > 6 * 3600 * 1000):
            snaps.append([int(time.time() * 1000), v]); snaps = snaps[-400:]
            try: json.dump(snaps, open(path, 'w', encoding='utf-8'))
            except Exception: pass
        return snaps

    def hist_refresh(self):
        if getattr(self, '_hist_busy', False): return
        self._hist_busy = True
        self.hist_msg.configure(text='загружаю из клиента…')
        def job():
            me = self.account or self.client.me() or {}
            pu = me.get('puuid')
            hist = self.client.history(pu, 30) if pu else None
            snaps = self.lp_snaps(self.client.rank(pu) if pu else None)
            def done():
                self._hist_busy = False
                if hist is None:
                    self.hist_msg.configure(text='клиент LoL не запущен' if not pu else 'клиент не отдал историю'); return
                self.hist_msg.configure(text=f'{len(hist)} игр · обновлено {time.strftime("%H:%M")}')
                self.hist_show(hist, core.lp_changes(hist, snaps), pu)
            self.root.after(0, done)
        threading.Thread(target=job, daemon=True).start()

    def hist_show(self, hist, lp, puuid):
        box, d, fn, fs = self.hist_box, self.data, F['font'], self.fs
        for w in box.winfo_children(): w.destroy()
        if not hist:
            self.dl(box, 'Игр пока нет', 'mute').pack(anchor='w'); return
        for h in hist:
            c = d.ids.get(str(h['champ']))
            bg = C['panel']
            row = tk.Frame(box, bg=bg, padx=12, pady=4, cursor='hand2')
            row.pack(fill='x', pady=2)
            tk.Frame(row, bg=C['good'] if h['win'] else C['bad']).place(x=0, rely=.2, relheight=.6, width=3)   # полоска победы/поражения
            mins = max(1, h.get('dur', 0) / 60)
            pos = core.lcu_pos({'timeline': {'lane': h.get('lane'), 'role': h.get('role')}})
            cells = [
                (tk.Label(row, image=self.img('champ', c, 1.0) or '', text='' if c else '?', bg=bg), 0),
                (tk.Label(row, text=('Победа' if h['win'] else 'Поражение'), bg=bg, fg=C['good' if h['win'] else 'bad'], font=(fn, fs(11), 'bold'), width=10, anchor='w'), 1),
                (tk.Label(row, text=f"{d.cn(c) if c else '?'}" + (f" · {core.ROLE_RU[pos]}" if pos else '') + '\n' + core.QUEUE_RU.get(h.get('q'), str(h.get('q')))
                          + (time.strftime(' · %d.%m %H:%M', time.localtime(h['t'] / 1000)) if h.get('t') else ''), bg=bg, fg=C['fg'],
                          font=(fn, fs(10)), width=24, anchor='w', justify='left'), 2),
                (tk.Label(row, text=f"{h['k']}/{h['d']}/{h['a']}", bg=bg, fg=C['fg'], font=(fn, fs(11), 'bold'), width=8, anchor='w'), 3),
                (tk.Label(row, text=f"{h.get('cs', 0)} CS ({h.get('cs', 0) / mins:.1f})\n{core.mmss(h.get('dur', 0))}", bg=bg, fg=C['mute'], font=(fn, fs(10)),
                          width=12, anchor='w', justify='left'), 4),
            ]
            v = lp.get(h.get('gid'))
            cells.append((tk.Label(row, text=f'{v:+d} LP' if v is not None else '', bg=bg, fg=C['good' if (v or 0) > 0 else 'bad'], font=(fn, fs(11), 'bold'), width=7, anchor='e'), 5))
            for w, i in cells: w.grid(row=0, column=i, sticky='w', padx=3)
            row.columnconfigure(5, weight=1)
            for w in [row] + [w for w, _ in cells]: w.bind('<Button-1>', lambda e, h=h, v=v: self.hist_open(h, v, puuid))
        self.hist_data = hist

    def hist_open(self, h, lp, puuid):
        """Окно с подробностями игры: обе команды и разбор."""
        def job():
            g = self.client.game(h['gid']) if h.get('gid') else None
            res = core.review_game(g, puuid, self.data)
            self.root.after(0, lambda: self.hist_window(h, lp, res))
        threading.Thread(target=job, daemon=True).start()

    def hist_window(self, h, lp, res):
        d, fn, fs = self.data, F['font'], self.fs
        w = tk.Toplevel(self.root); w.title('LoL Helper — разбор игры'); w.configure(bg=C['bg'], padx=16, pady=12)
        c = d.ids.get(str(h['champ']))
        head = f"{'Победа' if h['win'] else 'Поражение'} · {d.cn(c) if c else '?'} · {h['k']}/{h['d']}/{h['a']} · {core.mmss(h.get('dur', 0))}"
        if lp is not None: head += f' · {lp:+d} LP'
        tk.Label(w, text='  ' + head, image=self.img('champ', c, 1.4) or '', compound='left', bg=C['bg'], fg=C['good' if h['win'] else 'bad'],
                 font=(fn, fs(15), 'bold')).pack(anchor='w', pady=(0, 8))
        if not res:
            self.dl(w, 'Клиент не отдал подробности этой игры', 'mute').pack(anchor='w'); return
        for text, col in res['lines']:
            tk.Label(w, text=text, bg=C['bg'], fg=C[col], font=(fn, fs(11)), wraplength=fs(860), justify='left', anchor='w').pack(anchor='w', fill='x')
        mins = res['min']
        for team in sorted({r['team'] for r in res['rows']}):
            rows = [r for r in res['rows'] if r['team'] == team]
            win = rows and rows[0]['win']
            ours = res['me'] and res['me']['team'] == team
            tk.Label(w, text=('Твоя команда' if ours else 'Противники') + (' · победа' if win else ' · поражение'), bg=C['bg'],
                     fg=C['blue' if ours else 'red'], font=(fn, fs(12), 'bold')).pack(anchor='w', pady=(10, 2))
            order = {x: i for i, x in enumerate(core.ROLES)}
            for r in sorted(rows, key=lambda r: order.get(r['pos'], 9)):
                bg = C['panel']
                f = tk.Frame(w, bg=bg, padx=6, pady=2, highlightthickness=1, highlightbackground=C['gold'] if r['me'] else bg); f.pack(fill='x', pady=1)
                tk.Label(f, image=self.img('champ', r['c'], .9) or '', bg=bg).grid(row=0, column=0, padx=(0, 6))
                tk.Label(f, text=f"{d.cn(r['c']) if r['c'] else '?'}\n{r['name']}", bg=bg, fg=C['fg'], font=(fn, fs(10)), width=18, anchor='w', justify='left').grid(row=0, column=1, sticky='w')
                tk.Label(f, text=f"{r['k']}/{r['d']}/{r['a']}", bg=bg, fg=C['fg'], font=(fn, fs(11), 'bold'), width=9, anchor='w').grid(row=0, column=2)
                tk.Label(f, text=f"{r['cs']} CS ({r['cs'] / mins:.1f})\n{r['dmg'] / 1000:.1f}k урона · обзор {r['vis']}", bg=bg, fg=C['mute'],
                         font=(fn, fs(9)), width=24, anchor='w', justify='left').grid(row=0, column=3)
                its = tk.Frame(f, bg=bg); its.grid(row=0, column=4, sticky='w')
                for it in r['items']:
                    im = self.img('item', it, .6) if it else None
                    if im: tk.Label(its, image=im, bg=bg).pack(side='left', padx=1)
        ttk.Button(w, text='Закрыть', command=w.destroy).pack(anchor='e', pady=(10, 0))

    def death_map(self, box, res):
        """Карта смертей в окне итога: таймлайн появляется в клиенте не сразу, поэтому пробуем несколько раз."""
        fn, fs = F['font'], self.fs
        tk.Label(box, text='КАРТА СМЕРТЕЙ', bg=C['bg'], fg=C['gold'], font=(fn, fs(9), 'bold')).pack(anchor='w')
        pic = tk.Label(box, bg=C['bg'], fg=C['mute'], font=(fn, fs(9)), text='жду таймлайн игры из клиента…', width=26, height=10)
        pic.pack(anchor='w')
        note = tk.Label(box, bg=C['bg'], fg=C['mute'], font=(fn, fs(9)), justify='left'); note.pack(anchor='w')
        gbox = tk.Frame(box, bg=C['bg']); gbox.pack(anchor='w', pady=(8, 0))
        pu, started = (self.account or {}).get('puuid'), time.time()
        def job(tries):
            marks, gid, gs = None, None, None
            h = self.client.history(pu, 1) if pu else None
            if h and h[0].get('t', 0) / 1000 > started - 3600 * 2 and h[0]['champ'] == int(self.cid(res['me']['c']) or 0):
                gid = h[0]['gid']
                tl, gm = self.client.timeline(gid), self.client.game(gid)
                marks = core.timeline_marks(tl, gm, pu)
                try: gs = core.gold_series(tl, gm, pu, int(self.cid(res.get('opp')) or 0) if res.get('opp') else None)
                except Exception as e: log_error('итог: золото', e)
            def done():
                if not pic.winfo_exists(): return
                if marks is None or Image is None:
                    if tries < 6 and pu: return self.root.after(20000, lambda: threading.Thread(target=job, args=(tries + 1,), daemon=True).start())
                    return pic.configure(text='клиент не отдал таймлайн' if pu else 'нет связи с клиентом')
                ph = ImageTk.PhotoImage(render.death_map(marks, self.fs(220), C)); self.keep(ph)
                pic.configure(image=ph, text='', width=0, height=0)
                dd = [m for m in marks if m[3] == 'death']
                note.configure(text=f"✕ смерти: {len(dd)}, до 14 мин: {sum(m[2] < 840 for m in dd)}\n● убийства и помощь: {len(marks) - len(dd)}")
                if gs: self.gold_box(gbox, gs)
            self.root.after(0, done)
        self.root.after(15000, lambda: threading.Thread(target=job, args=(0,), daemon=True).start())

    def gold_box(self, box, gs):
        """График «золото против оппонента по линии» под картой смертей."""
        fn, fs = F['font'], self.fs
        tk.Label(box, text=f"ЗОЛОТО: ТЫ И {self.data.cn(self.data.ids.get(str(gs['oc']))).upper()}", bg=C['bg'], fg=C['gold'],
                 font=(fn, fs(9), 'bold')).pack(anchor='w')
        ph = ImageTk.PhotoImage(render.gold_chart(gs, self.fs(220), self.fs(90), C)); self.keep(ph)
        tk.Label(box, image=ph, bg=C['bg']).pack(anchor='w')
        tk.Label(box, text=core.gold_note(gs) + '\nвертикальные линии: каждые 5 минут', bg=C['bg'], fg=C['mute'], font=(fn, fs(9)),
                 justify='left', wraplength=self.fs(230)).pack(anchor='w')

    def open_last_game(self):
        """Сайт сразу на последней игре: её номер берём из истории клиента."""
        def job():
            pu = (self.account or {}).get('puuid')
            h = self.client.history(pu, 1) if pu else None
            gid = h[0].get('gid') if h else None
            self.root.after(0, lambda: self.open_site(f'EUW1_{gid}' if gid else None))
        threading.Thread(target=job, daemon=True).start()

    def open_site(self, game=None):
        """Сайт со статистикой в отдельном окне (WebView2). Отдельный процесс: окно браузера не уживается с Tk в одном потоке."""
        exe = sys.executable
        args = [exe, '--site'] if getattr(sys, 'frozen', False) else [exe, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lolhelper.py'), '--site']
        if game: args.append(f'--game={game}')
        env = {k: v for k, v in os.environ.items() if not k.startswith(('_PYI', '_MEI'))}
        env['PYINSTALLER_RESET_ENVIRONMENT'] = '1'
        try: subprocess.Popen(args, env=env)
        except Exception as e: messagebox.showerror('LoL Helper', f'Не удалось открыть сайт: {e}')

    # --- карточки нового дизайна
    def card(self, parent, bg=None, pad=(16, 12), edge=None):
        return tk.Frame(parent, bg=bg or C['panel'], padx=self.fs(pad[0]), pady=self.fs(pad[1]), highlightthickness=1 if edge else 0,
                        highlightbackground=edge or bg or C['panel'])

    def cap(self, parent, text, bg=None, color='mute'):
        return tk.Label(parent, text=text.upper(), bg=bg or C['panel'], fg=C[color], font=(F['num'], self.fs(9)), anchor='w')

    def build_status(self):
        """Главная: карточка звания с кнопками, 4 плитки за 20 игр, последние игры, пул и один совет."""
        f, fs, fn = self.tab_status, self.fs, F['font']
        hero = self.card(f, C['panel'], (18, 14)); hero.pack(fill='x', pady=(4, 10))
        self.acc_icon = tk.Label(hero, bg=C['panel']); self.acc_icon.pack(side='left', padx=(0, 16))
        mid = tk.Frame(hero, bg=C['panel']); mid.pack(side='left', fill='x', expand=True)
        self.acc_cap = self.cap(mid, 'Одиночная / парная'); self.acc_cap.pack(anchor='w')
        self.acc_rank = tk.Label(mid, bg=C['panel'], fg=C['gold'], font=(F['head'], fs(24)), anchor='w'); self.acc_rank.pack(anchor='w')
        self.acc_lbl = tk.Label(mid, bg=C['panel'], fg=C['mute'], font=(fn, fs(10)), anchor='w'); self.acc_lbl.pack(anchor='w')
        self.acc_sub = tk.Label(mid, bg=C['panel'], fg=C['mute'], font=(fn, fs(9)), anchor='w', justify='left'); self.acc_sub.pack(anchor='w')
        right = tk.Frame(hero, bg=C['panel']); right.pack(side='right', anchor='n')
        ttk.Button(right, text='Открыть окно драфта и игры', style='A.TButton', command=self.open_dash).pack(fill='x')
        ttk.Button(right, text='Сайт со статистикой', command=self.open_site).pack(fill='x', pady=(6, 0))
        self.acc_emb = tk.Label(hero, bg=C['panel'])   # не показывается: эмблема стоит слева
        self.tiles = tk.Frame(f, bg=C['bg']); self.tiles.pack(fill='x')
        for i in range(4): self.tiles.columnconfigure(i, weight=1, uniform='t')
        row = tk.Frame(f, bg=C['bg']); row.pack(fill='both', expand=True, pady=(12, 0))
        row.columnconfigure(0, weight=3, uniform='r'); row.columnconfigure(1, weight=2, uniform='r')
        g = tk.Frame(row, bg=C['bg']); g.grid(row=0, column=0, sticky='nsew', padx=(0, 12))
        hd = tk.Frame(g, bg=C['bg']); hd.pack(fill='x', pady=(0, 6))
        tk.Label(hd, text='ПОСЛЕДНИЕ ИГРЫ', bg=C['bg'], fg=C['gold'], font=(F['head'], fs(12))).pack(side='left')
        more = tk.Label(hd, text='вся история →', bg=C['bg'], fg=C['mute'], font=(fn, fs(9)), cursor='hand2'); more.pack(side='right')
        more.bind('<Button-1>', lambda e: self.nb.select(1))
        self.home_games = tk.Frame(g, bg=C['bg']); self.home_games.pack(fill='both', expand=True)
        side = tk.Frame(row, bg=C['bg']); side.grid(row=0, column=1, sticky='nsew')
        hd = tk.Frame(side, bg=C['bg']); hd.pack(fill='x', pady=(0, 6))
        self.home_pool_cap = tk.Label(hd, text='ПУЛ', bg=C['bg'], fg=C['gold'], font=(F['head'], fs(12))); self.home_pool_cap.pack(side='left')
        self.home_pool_n = tk.Label(hd, bg=C['bg'], fg=C['mute'], font=(fn, fs(9))); self.home_pool_n.pack(side='right')
        pc = self.card(side); pc.pack(fill='x')
        self.home_pool = tk.Frame(pc, bg=C['panel']); self.home_pool.pack(fill='x')
        self.home_tip = tk.Frame(side, bg=C['tag_y'], padx=fs(12), pady=fs(10)); self.home_tip.pack(fill='x', pady=(10, 0))
        pl = tk.Frame(side, bg=C['bg']); pl.pack(fill='x', pady=(12, 0))
        tk.Label(pl, text='Чья статистика', bg=C['bg'], fg=C['mute'], font=(fn, fs(9))).pack(side='left')
        self.who_var = tk.StringVar()
        names = {w: p['riot'] for w, p in self.data.d['players'].items()}
        cb = ttk.Combobox(pl, state='readonly', values=list(names.values()), textvariable=self.who_var, width=18); cb.pack(side='left', padx=(8, 0))
        def pick(_):
            who = next(w for w, n in names.items() if n == self.who_var.get())
            self.s['who'] = who; self.s.save(); self.set_who(who); self.panel_sync()
        cb.bind('<<ComboboxSelected>>', pick)
        self.data_lbl = tk.Label(side, bg=C['bg'], fg=C['mute'], font=(fn, fs(9)), anchor='w', wraplength=fs(300), justify='left')
        self.data_lbl.pack(anchor='w', pady=(4, 0))
        tk.Label(side, text="LoL Helper isn't endorsed by Riot Games. League of Legends — товарный знак Riot Games, Inc.", bg=C['bg'], fg=C['mute'],
                 font=(fn, fs(8)), anchor='w', wraplength=fs(300), justify='left').pack(anchor='w', pady=(6, 0))
        self.panel_sync()

    TIPS = {'csm': 'Фарм просел к сезону: добивай волну перед каждым возвращением на базу и забирай боковые линии в середине игры.',
            'vsm': 'Обзор просел к сезону: ставь контрольный вард при каждом возвращении на базу.',
            'kda': 'KDA просел к сезону: меньше заходов в туман без обзора, после линии держись ближе к команде.',
            'wr': 'Винрейт ниже сезона: играй меньше игр подряд после двух поражений и бери свой основной пул.'}

    def role_img(self, pos, k=.5):
        """Официальный значок роли, перекрашенный в золото."""
        if Image is None or not pos: return None
        size = max(10, int(self.s['icon'] * k))
        key = ('role', pos, size, C['gold'])
        if key in self.icons.cache: return self.icons.cache[key]
        im = self.icons._pil('role', pos)
        if im is None: return None
        self.icons.cache[key] = ph = ImageTk.PhotoImage(render.tint(im, C['gold'], size))
        return ph

    def home_fill(self):
        """Плитки, последние игры и пул выбранного игрока (из статистики сайта)."""
        d, fs, fn = self.data, self.fs, F['font']
        games = sorted(self.player.games, key=lambda g: g.get('t') or 0, reverse=True) if self.player else []
        def stats(gs):
            if not gs: return None
            n = len(gs); avg = lambda k: sum(g[k] for g in gs if g.get(k) is not None) / max(1, sum(1 for g in gs if g.get(k) is not None))
            return {'wr': sum(g['w'] for g in gs) / n * 100, 'kda': sum((g['k'] + g['a']) / max(1, g['d']) for g in gs) / n,
                    'csm': avg('csm'), 'vsm': avg('vsm')}
        last, allg = stats(games[:20]), stats(games)
        for w in self.tiles.winfo_children(): w.destroy()
        tiles = [('Винрейт · 20 игр', 'wr', '{:.0f}%', 1), ('KDA · 20 игр', 'kda', '{:.1f}', .1), ('CS в минуту', 'csm', '{:.1f}', .1), ('Обзор в минуту', 'vsm', '{:.2f}', .02)]
        worst = (None, 0)
        for i, (t, k, fmt, eps) in enumerate(tiles):
            c = self.card(self.tiles); c.grid(row=0, column=i, sticky='nsew', padx=(0 if i == 0 else 5, 0 if i == 3 else 5))
            self.cap(c, t).pack(anchor='w')
            v, base = (last or {}).get(k), (allg or {}).get(k)
            low = v is not None and base and v < base - eps
            tk.Label(c, text=(fmt.format(v) if v is not None else '—').replace('.', ','), bg=C['panel'], fg=C['warn'] if low else C['fg'],
                     font=(F['numb'], fs(22)), anchor='w').pack(anchor='w')
            if v is not None and base is not None:
                dv = v - base
                txt, col = (('▲ ' if dv > 0 else '▼ ') + fmt.format(abs(dv)).replace('.', ',') + ' к сезону', 'good' if dv > 0 else 'bad') if abs(dv) >= eps else ('как в сезоне', 'mute')
                tk.Label(c, text=txt, bg=C['panel'], fg=C[col], font=(fn, fs(9)), anchor='w').pack(anchor='w')
                if low and (base - v) / max(abs(base), 1e-6) > worst[1]: worst = (k, (base - v) / max(abs(base), 1e-6))
        box = self.home_games
        for w in box.winfo_children(): w.destroy()
        if not games: tk.Label(box, text='Игр пока нет', bg=C['bg'], fg=C['mute'], font=(fn, fs(10))).pack(anchor='w')
        for g in games[:6]:
            bg = C['panel']
            r = tk.Frame(box, bg=bg, padx=fs(12), pady=fs(6)); r.pack(fill='x', pady=3)
            tk.Frame(r, bg=C['good'] if g['w'] else C['bad']).place(x=-fs(12), rely=.2, relheight=.6, width=3)   # полоска победы/поражения
            tk.Label(r, image=self.round_img('champ', g['c'], .95) or '', bg=bg).pack(side='left', padx=(0, 10))
            res = tk.Frame(r, bg=bg); res.pack(side='right')
            tk.Label(res, text='ПОБЕДА' if g['w'] else 'ПОРАЖЕНИЕ', bg=bg, fg=C['good'] if g['w'] else C['bad'], font=(F['numb'], fs(10)), anchor='e').pack(anchor='e')
            meta = [core.QUEUE_RU.get(g.get('q'), ''), f"{int(g['dur'])}:{int(g['dur'] % 1 * 60):02d}" if g.get('dur') else '',
                    time.strftime('%d.%m', time.localtime(g['t'])) if g.get('t') else '']
            tk.Label(res, text=' · '.join(m for m in meta if m), bg=bg, fg=C['mute'], font=(fn, fs(9)), anchor='e').pack(anchor='e')
            kd = tk.Frame(r, bg=bg); kd.pack(side='right', padx=(8, 14))
            tk.Label(kd, text=f"{g['k']}/{g['d']}/{g['a']}", bg=bg, fg=C['fg'], font=(F['numb'], fs(12)), anchor='e').pack(anchor='e')
            tk.Label(kd, text=f"CS {g.get('csm', 0):.1f}".replace('.', ','), bg=bg, fg=C['mute'], font=(fn, fs(9)), anchor='e').pack(anchor='e')
            t1 = tk.Frame(r, bg=bg); t1.pack(side='left', fill='x', expand=True)
            hd = tk.Frame(t1, bg=bg); hd.pack(anchor='w')
            tk.Label(hd, text=d.cn(g['c']), bg=bg, fg=C['fg'], font=(fn, fs(10), 'bold')).pack(side='left')
            ri = self.role_img(g.get('pos'), .4)
            if ri: tk.Label(hd, image=ri, bg=bg).pack(side='left', padx=(6, 3))
            tk.Label(hd, text=(f"против {d.cn(g['opp'])}" if g.get('opp') else core.ROLE_RU.get(g.get('pos'), '')), bg=bg, fg=C['mute'],
                     font=(fn, fs(9))).pack(side='left')
            its = tk.Frame(t1, bg=bg); its.pack(anchor='w', pady=(3, 0))
            for it in (g.get('it') or [])[:6]:
                tk.Label(its, image=self.img('item', it, .5) or '', bg=bg).pack(side='left', padx=(0, 2))
        box = self.home_pool
        for w in box.winfo_children(): w.destroy()
        if games:
            roles = {}
            for g in games[:100]: roles[g['pos']] = roles.get(g['pos'], 0) + 1
            main = max(roles, key=roles.get)
            self.home_pool_cap.configure(text=f"ПУЛ · {core.ROLE_RU.get(main, '').upper()}")
            self.home_pool_n.configure(text=f'{min(100, len(games))} игр')
            by = {}
            for g in games[:100]:
                if g['pos'] == main: by.setdefault(g['c'], []).append(g['w'])
            few = []
            for c, ws in sorted(by.items(), key=lambda x: -len(x[1]))[:4]:
                wr = sum(ws) / len(ws)
                if len(ws) < 5: few.append(d.cn(c))
                r = tk.Frame(box, bg=C['panel']); r.pack(fill='x', pady=4)
                tk.Label(r, image=self.round_img('champ', c, .8) or '', bg=C['panel']).pack(side='left', padx=(0, 10))
                tk.Label(r, text=d.cn(c), bg=C['panel'], fg=C['fg'], font=(fn, fs(10)), width=11, anchor='w').pack(side='left')
                tk.Label(r, text=str(len(ws)), bg=C['panel'], fg=C['mute'], font=(F['num'], fs(9)), width=3, anchor='e').pack(side='right')
                tk.Label(r, text=f'{wr * 100:.0f}%', bg=C['panel'], fg=C['fg'], font=(F['numb'], fs(11)), width=5, anchor='e').pack(side='right')
                bar = tk.Frame(r, bg=C['raise'], height=6); bar.pack(side='left', fill='x', expand=True, padx=(4, 8))
                tk.Frame(bar, bg=C['good'] if wr >= .5 else C['bad'], height=6).place(relx=0, rely=0, relwidth=max(.02, wr), relheight=1)
            if few: tk.Label(box, text='мало игр у ' + ', '.join(few[:2]) + ', ненадёжно', bg=C['panel'], fg=C['mute'], font=(fn, fs(9)), anchor='w').pack(anchor='w', pady=(4, 0))
        tip = self.home_tip
        for w in tip.winfo_children(): w.destroy()
        txt = self.TIPS.get(worst[0]) if worst[0] else ('Все показатели последних 20 игр не хуже сезона. Так держать.' if games else '')
        if txt:
            tk.Label(tip, text='Совет', bg=C['tag_y'], fg=C['warn'], font=(F['numb'], fs(10))).pack(side='left', anchor='n', padx=(0, 10))
            tk.Label(tip, text=txt, bg=C['tag_y'], fg=C['fg'], font=(fn, fs(10)), wraplength=fs(250), justify='left').pack(side='left', fill='x')
            tip.pack(fill='x', pady=(10, 0))
        else: tip.pack_forget()

    def round_img(self, grp, key, k=1.0):
        """Круглая иконка (портрет в строке игры, как на сайте)."""
        if Image is None or not key: return None
        size = max(12, int(self.s['icon'] * k))
        ck = ('round', grp, key, size)
        if ck in self.icons.cache: return self.icons.cache[ck]
        im = self.icons._pil(grp, key)
        if im is None: return None
        im = im.resize((size * 2, size * 2), Image.LANCZOS)
        m = Image.new('L', im.size, 0); render.ImageDraw.Draw(m).ellipse((0, 0, im.width - 1, im.height - 1), fill=255)
        im.putalpha(Image.composite(im.getchannel('A'), m, m))
        self.icons.cache[ck] = ph = ImageTk.PhotoImage(im.resize((size, size), Image.LANCZOS))
        return ph

    def panel_sync(self):
        a, d = self.account, self.data
        if self.who: self.who_var.set(d.d['players'][self.who]['riot'])
        pl = d.d['players'].get(self.who or '', {})
        try: self.status_dot.configure(fg=C['good'] if a else C['mute'])
        except Exception: pass
        if a and self.status.cget('text').startswith('Ищу клиент'): self.status.configure(text='Клиент найден')
        rk = rank_text(self.my_rank) if self.my_rank else pl.get('rank', '')
        parts = rk.split(' · ') if rk else []
        self.acc_rank.configure(text=' · '.join(parts[:2]).upper() if parts else 'БЕЗ ЗВАНИЯ')
        self.acc_cap.configure(text='ОДИНОЧНАЯ / ПАРНАЯ · EUW')
        self.acc_lbl.configure(text=' · '.join([a['riot'] if a else pl.get('riot', '')] + parts[2:]))
        self.acc_sub.configure(text=f"уровень {a.get('level') or '?'} · вошёл в клиент" if a else 'Клиент не найден: запусти League of Legends')
        tier = TIER_RU.get(self.my_rank['tier']) if self.my_rank else tier_of(pl.get('rank'))
        emb = self.img('emb', tier, 2.0) if tier and self.s['show']['ranks'] else None
        self.acc_icon.configure(image=emb or (self.img('profile', a.get('icon'), 2) if a else None) or '')
        g = sum(len(p['g']) for p in d.d['players'].values())
        self.data_lbl.configure(text=f"Статистика от {d.d['t']} · патч {d.d['patch']} · {g} игр")
        self.home_fill()

    def open_dash(self):
        if not self.dash:
            self.s['dashboard'] = True; self.s.save(); self.dash = Dashboard(self)
        else: self.dash.deiconify(); self.dash.lift()

    def build_hints(self):
        inner = self.tab_hints
        row = tk.Frame(inner, bg=C['bg']); row.pack(fill='x', pady=(0, 6))
        ttk.Label(row, text='Все сразу: ').pack(side='left')
        self.hint_vars = {}
        for m, lab in MODES.items():
            ttk.Button(row, text=lab, command=lambda m=m: self.set_all_hints(m)).pack(side='left', padx=2)
        row = tk.Frame(inner, bg=C['bg']); row.pack(fill='x', pady=(0, 4))
        ttk.Button(row, text='Режимы по умолчанию', command=lambda: (self.s.reset(SECTIONS['hints']), self.rebuild())).pack(side='left')
        ttk.Label(row, text='  ▶ — проверить, как прозвучит подсказка · ✎ — свой текст', style='M.TLabel').pack(side='left')
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
        r = tk.Frame(inner, bg=C['bg']); r.pack(fill='x', pady=(3, 0))
        v = tk.StringVar(value=MODES[self.hint_mode(hid)]); self.hint_vars[hid] = v
        cb = ttk.Combobox(r, state='readonly', width=8, values=list(MODES.values()), textvariable=v); cb.pack(side='left')
        cb.bind('<<ComboboxSelected>>', lambda e, hid=hid: self.set_hint(hid))
        ttk.Button(r, text='▶', width=3, command=lambda hid=hid, name=name: self.test_hint(hid, name)).pack(side='left', padx=(4, 0))
        ttk.Button(r, text='✎', width=3, command=lambda hid=hid, name=name: self.edit_hint(hid, name)).pack(side='left', padx=(2, 0))
        ttk.Label(r, text=name + (' ✎' if self.s['hint_text'].get(hid) else ''), wraplength=self.fs(480)).pack(side='left', padx=8)
        d = core.HINT_DESC.get(hid)
        if d: ttk.Label(inner, text=d, style='M.TLabel', wraplength=self.fs(560)).pack(anchor='w', padx=(self.fs(130), 0))

    def apply_text(self, h):
        """Свой текст подсказки: {текст} заменяется исходным."""
        o = self.s['hint_text'].get(h.id)
        if not o: return
        orig_t, orig_s = h.text, h.say or h.text
        if o.get('text'): h.text = o['text'].replace('{текст}', orig_t)
        if o.get('say'): h.say = o['say'].replace('{текст}', orig_s)
        elif o.get('text'): h.say = o['text'].replace('{текст}', orig_s)

    def edit_hint(self, hid, name):
        o = self.s['hint_text'].get(hid, {})
        w = tk.Toplevel(self.root); w.title('Текст подсказки'); w.configure(bg=C['bg']); w.transient(self.root)
        f = tk.Frame(w, bg=C['bg'], padx=14, pady=12); f.pack(fill='both', expand=True)
        ttk.Label(f, text=name, style='H.TLabel').pack(anchor='w')
        if core.HINT_DESC.get(hid): ttk.Label(f, text=core.HINT_DESC[hid], style='M.TLabel', wraplength=self.fs(460)).pack(anchor='w', pady=(2, 8))
        ttk.Label(f, text='Текст на экране. {текст} — подставит исходный текст подсказки, пусто — как было:').pack(anchor='w')
        t = tk.StringVar(value=o.get('text', '')); ttk.Entry(f, textvariable=t, width=60).pack(fill='x', pady=(2, 8))
        ttk.Label(f, text='Что говорит голос (пусто — то же, что на экране):').pack(anchor='w')
        sy = tk.StringVar(value=o.get('say', '')); ttk.Entry(f, textvariable=sy, width=60).pack(fill='x', pady=(2, 10))
        b = tk.Frame(f, bg=C['bg']); b.pack(fill='x')
        def save():
            tx, sv = t.get().strip(), sy.get().strip()
            if tx or sv: self.s['hint_text'][hid] = {'text': tx, 'say': sv}
            else: self.s['hint_text'].pop(hid, None)
            self.s.save(); w.destroy(); self.rebuild()
        def reset(): t.set(''); sy.set('')
        ttk.Button(b, text='Сохранить', style='A.TButton', command=save).pack(side='left')
        ttk.Button(b, text='Как было', command=reset).pack(side='left', padx=6)
        ttk.Button(b, text='Отмена', command=w.destroy).pack(side='left')

    def test_hint(self, hid, name):
        """Проверка подсказки: звучит так, как настроено (сигнал, голос или только текст)."""
        mode = self.hint_mode(hid)
        if mode == 'off': self.status.configure(text='Эта подсказка выключена'); return
        h = core.Hint(hid, name, None); self.apply_text(h)
        self.toast(h.text); self.status.configure(text=f'Проверка: {MODES[mode].lower()}')
        if mode == 'beep': self.voice.beep(force=True)
        elif mode == 'voice': self.voice.say(h.say or h.text, force=True)

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
        self.h(f, 'Драфт на телефоне')
        self.note(f, 'Телефон в той же Wi-Fi сети, что и компьютер, открывает адрес ниже и видит драфт: кого брать и банить, руны, сборку, умения. '
                     'Кнопка на телефоне импортирует руны и предметы в клиент. При первом включении Windows спросит разрешение для сети: разреши для частных сетей.')
        pv = tk.BooleanVar(value=self.s['phone'])
        ttk.Checkbutton(f, text='Включить драфт на телефоне', variable=pv,
                        command=lambda: (self.s.__setitem__('phone', pv.get()), self.s.save(), self.sync_phone())).pack(anchor='w')
        self.phone_lbl = ttk.Label(f, text='', style='V.TLabel'); self.phone_lbl.pack(anchor='w', pady=(2, 0))
        self.sync_phone()
        self.h(f, 'Раскладка виджетов')
        row = tk.Frame(f, bg=C['bg']); row.pack(anchor='w', pady=(8, 0))
        ttk.Label(row, text='Готовая раскладка:').pack(side='left')
        ttk.Button(row, text='По краям окна игры', command=lambda: self.preset_layout('edges')).pack(side='left', padx=6)
        ttk.Button(row, text='Ближе к центру (ультраширокий)', command=lambda: self.preset_layout('center')).pack(side='left')
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
        self.h(f, 'Стоимость предметов по Tab')
        self.note(f, 'Таблички у краёв игровой таблицы: союзники слева (стоимость и разница с оппонентом по линии), враги справа, над рамкой — итог команд. '
                     'Считаются все предметы, кроме зелий, вардов и тотемов. Всё привязано к окну игры и масштабируется по его высоте, в том числе на широких мониторах. '
                     'Если не совпало: в игре зажми Tab и Alt — появится золотая рамка, подтяни её края к краям таблицы.')
        ttk.Button(f, text='Вернуть рамку по умолчанию', command=lambda: self.set_tab('tab_rect', None)).pack(anchor='w', pady=(4, 0))
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
        if self.demo_on:
            for w in self.tab.values(): w.demo()

    def toggle_widget(self, k):
        self.s['widgets'][k] = self.w_vars[k].get(); self.s.save(); self.apply_visibility()

    def preset_layout(self, kind):
        """Готовая раскладка виджетов (как у Blitz): 'edges' — по краям окна игры, 'center' — по краям центральной части 16:9,
        чтобы на ультрашироком мониторе не водить глазами к краям экрана."""
        gx, gy, gw, gh = game_rect()
        k = gh / 1080
        cx = gx + gw / 2
        half = gw / 2 if kind == 'edges' else min(gw / 2, gh * 16 / 9 / 2)
        L, R = cx - half + 24 * k, cx + half - 340 * k
        pos = {'hints': (L, gy + .30 * gh), 'gold': (L, gy + .55 * gh), 'perf': (R, gy + .10 * gh), 'lane': (R, gy + .30 * gh),
               'item': (R, gy + .40 * gh), 'timers': (R, gy + .49 * gh)}
        lay = self.layout()
        for key, (x, y) in pos.items(): lay[key] = [int(x), int(y)]
        self.s.save(); self.rebuild()
        self.status.configure(text='Раскладка применена: проверь кнопкой «Показать все виджеты»')

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
        for i, (k, (name, pal)) in enumerate(THEMES.items()):   # столбец — палитра, строки — ночь и день
            b = tk.Label(row, text=name, bg=pal['panel'], fg=pal['gold'], font=(F['numb'], self.fs(10)), padx=12, pady=6, width=20,
                         highlightthickness=2, highlightbackground=C['gold'] if self.s['theme'] == k else pal['bg'], cursor='hand2')
            b.grid(row=i % 2, column=i // 2, padx=(0, 6), pady=(0, 6), sticky='w')
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
        self.voice_msg = ttk.Label(f, text='', style='M.TLabel', wraplength=self.fs(660)); self.voice_msg.pack(anchor='w', pady=4)
        self.voice.on_error = lambda m: self.root.after(0, lambda: self.voice_msg.winfo_exists() and self.voice_msg.configure(text=m, foreground=C['bad']))
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
            self.voice_msg.configure(text=f'Голос: {VOICES[v]}', foreground=C['mute']); return
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
                          ('scoreboard', 'Таблица Tab: стоимость предметов (держать)'), ('drag', 'Двигать виджеты и рамку Tab (держать)')):
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
        self.note(f, RIOT_NOTE)
        self.upd_msg = ttk.Label(f, text='', style='M.TLabel'); self.upd_msg.pack(anchor='w', pady=4)
        v = tk.BooleanVar(value=self.s['auto_update'])
        ttk.Checkbutton(f, text='Проверять обновления при запуске', variable=v,
                        command=lambda: (self.s.__setitem__('auto_update', v.get()), self.s.save())).pack(anchor='w')
        row = tk.Frame(f, bg=C['bg']); row.pack(anchor='w', pady=6)
        ttk.Button(row, text='Проверить сейчас', command=lambda: self.check_updates(True)).pack(side='left')
        ttk.Button(row, text='Что нового: все релизы на GitHub', command=lambda: webbrowser.open(RELEASES)).pack(side='left', padx=8)
        link = tk.Label(f, text=RELEASES, bg=C['bg'], fg=C['blue'], font=(F['font'], self.fs(10), 'underline'), cursor='hand2')
        link.pack(anchor='w'); link.bind('<Button-1>', lambda e: webbrowser.open(RELEASES))
        self.note(f, 'Статистика обновляется сама каждые 30 минут с raw.githubusercontent.com (работает без VPN).')
        self.h(f, 'Список изменений')
        self.chlog_box = tk.Frame(f, bg=C['bg']); self.chlog_box.pack(fill='x')
        self.load_changelog()
        self.h(f, 'Если что-то сломалось')
        self.note(f, 'Программа записывает ошибки (окна, связь с клиентом, импорт рун, предметов и заклинаний, lolalytics) в журнал. '
                     'Кнопка копирует отчёт: вставь его в чат с Claude, и по нему можно сразу найти причину.')
        row = tk.Frame(f, bg=C['bg']); row.pack(anchor='w', pady=6)
        ttk.Button(row, text='Скопировать отчёт для Claude', style='A.TButton', command=self.copy_report).pack(side='left')
        ttk.Button(row, text='Открыть папку с журналами', command=lambda: os.startfile(self.home) if os.name == 'nt' else None).pack(side='left', padx=8)
        n = len([ln for ln in tail(os.path.join(self.home, 'errors.log'), 400) if ln[:2] == '20'])
        self.rep_msg = ttk.Label(f, text=f'В журнале записей: {n}' if n else 'Журнал пуст: ошибок не было.', style='M.TLabel'); self.rep_msg.pack(anchor='w')
        self.h(f, 'Копия настроек')
        self.note(f, 'Сохрани настройки в файл (раскладка окон, клавиши, подсказки и их тексты, вид, звук, таймеры), '
                     'чтобы перенести на другой компьютер или отдать другу. Загрузка из файла заменит текущие настройки.')
        row = tk.Frame(f, bg=C['bg']); row.pack(anchor='w', pady=6)
        ttk.Button(row, text='Сохранить в файл', command=self.backup_save).pack(side='left')
        ttk.Button(row, text='Загрузить из файла', command=self.backup_load).pack(side='left', padx=8)
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

    def backup_save(self):
        path = filedialog.asksaveasfilename(parent=self.root, title='Сохранить настройки', defaultextension='.json',
                                            initialfile='LoLHelper-настройки.json', filetypes=[('Настройки LoL Helper', '*.json')])
        if not path: return
        try:
            json.dump(self.s.export(self.version), open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            self.status.configure(text=f'Настройки сохранены: {os.path.basename(path)}')
        except Exception as e:
            log_error('копия настроек: сохранение', e); messagebox.showerror('LoL Helper', f'Не удалось сохранить: {e}')

    def backup_load(self):
        path = filedialog.askopenfilename(parent=self.root, title='Загрузить настройки', filetypes=[('Настройки LoL Helper', '*.json')])
        if not path: return
        try:
            n = self.s.load_backup(json.load(open(path, encoding='utf-8')))
        except Exception as e:
            log_error('копия настроек: загрузка', e); messagebox.showerror('LoL Helper', f'Не удалось загрузить: {e}'); return
        self.sync_voice(); core.OBJ.update(self.s['obj']); self.rebuild()
        self.status.configure(text=f'Настройки загружены из файла ({n} разделов)')

    def load_changelog(self):
        """Изменения по версиям из релизов GitHub; без сети показывает сохранённый список."""
        path = os.path.join(self.home, 'changelog.json')
        try: cached = json.load(open(path, encoding='utf-8'))
        except Exception: cached = None
        def job():
            rels = None
            try:
                req = urllib.request.Request('https://api.github.com/repos/Halches/Lol-stat/releases?per_page=30',
                                             headers={'User-Agent': 'LoLHelper', 'Accept': 'application/vnd.github+json'})
                with urllib.request.urlopen(req, timeout=10) as r:
                    rels = [{'tag': x['tag_name'], 't': x.get('published_at') or '', 'body': x.get('body') or ''}
                            for x in json.load(r) if x['tag_name'].startswith('v')]
                json.dump(rels, open(path, 'w', encoding='utf-8'), ensure_ascii=False)
            except Exception: pass
            self.root.after(0, lambda: self.show_changelog(rels or cached, bool(rels)))
        if cached: self.show_changelog(cached, False)
        threading.Thread(target=job, daemon=True).start()

    def show_changelog(self, rels, fresh):
        box, fs, fn = getattr(self, 'chlog_box', None), self.fs, F['font']
        try:
            if not box or not box.winfo_exists(): return
        except tk.TclError: return
        for w in box.winfo_children(): w.destroy()
        if not rels:
            self.dl(box, 'Не удалось загрузить список: нет связи с GitHub. Все версии есть по ссылке выше.', 'mute', 10).pack(anchor='w'); return
        for r in rels[:15]:
            mine = r['tag'] == self.version
            c = self.card(box, edge=C['gold'] if mine else None); c.pack(fill='x', pady=3)
            hd = tk.Frame(c, bg=C['panel']); hd.pack(fill='x')
            tk.Label(hd, text=r['tag'], bg=C['panel'], fg=C['gold'] if mine else C['fg'], font=(F['num'], fs(14), 'bold')).pack(side='left')
            if mine: tk.Label(hd, text='  у тебя сейчас', bg=C['panel'], fg=C['gold'], font=(fn, fs(9), 'bold')).pack(side='left')
            when = r['t'][8:10] + '.' + r['t'][5:7] + '.' + r['t'][:4] if len(r['t']) >= 10 else ''
            tk.Label(hd, text=when, bg=C['panel'], fg=C['mute'], font=(fn, fs(9))).pack(side='right')
            lines = [ln.strip() for ln in r['body'].replace('\r', '').split('\n') if ln.strip() and ln.strip() != 'Изменения:']
            for ln in lines:
                bullet = ln.startswith(('- ', '* '))
                ln = ln[2:] if bullet else ln
                if ln.startswith('LoL Helper: '): ln = ln[len('LoL Helper: '):]
                ln = ln[:1].upper() + ln[1:]
                tk.Label(c, text=('•  ' if bullet else '') + ln, bg=C['panel'], fg=C['fg'], font=(fn, fs(10), 'normal' if bullet else 'bold'),
                         anchor='w', justify='left', wraplength=fs(640)).pack(anchor='w', fill='x', padx=(10 if bullet else 0, 0), pady=1)

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

    def load_lanes(self):
        """Частоты линий всех чемпионов (lolalytics, Изумруд+): по ним угадываются линии врагов в драфте. Кеш на 3 дня."""
        path = os.path.join(self.home, 'lola', 'lanes.json')
        lanes = None
        try:
            if time.time() - os.path.getmtime(path) < 3 * 86400: lanes = json.load(open(path, encoding='utf-8'))
        except Exception: pass
        if not lanes:
            try:
                lists = {}
                for r, lane in core.LOLA_LANE.items():
                    url = f'https://a1.lolalytics.com/mega/?ep=list&v=1&patch=30&lane={lane}&tier=emerald_plus&queue=ranked&region=all'
                    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                    lists[r] = json.loads(urllib.request.urlopen(req, timeout=20).read().decode('utf-8', 'ignore'))
                lanes = core.lola_lanes(lists, self.data)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                json.dump(lanes, open(path, 'w', encoding='utf-8'))
            except Exception as e:
                log_error('таблица линий', e)
                try: lanes = json.load(open(path, encoding='utf-8'))
                except Exception: lanes = {}
        def done():
            self.data.lanes = lanes or {}
            self.redraw_draft()
        self.root.after(0, done)

    def reload_data(self, data):
        """Новая статистика скачалась: подменяем между играми, текущая игра доигрывается со старой."""
        if self.last_game:
            self.pending_data = data; return
        self.pending_data = None
        data.lanes = self.data.lanes
        self.data = data
        self.set_who(self.who)
        self.panel_sync()

    def run(self):
        self.root.mainloop()
