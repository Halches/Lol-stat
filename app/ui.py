# Окна LoL Helper: панель управления, виджеты поверх игры, дашборд на втором мониторе, таблица по Tab, итог игры.
# Внешний вид (тема, акцент, шрифт, иконки) настраивается на вкладке «Вид» и применяется сразу: окна пересобираются.
import base64, io, json, os, platform, queue, subprocess, sys, threading, time, traceback, urllib.request, webbrowser
import tkinter as tk
from collections import OrderedDict
from tkinter import filedialog, messagebox, ttk

from scroll_canvas import ScrollCanvas

import performance_model
import core, lcu, phone, tab_detect, player_comments, player_traits, player_evidence, champion_rank, champion_pool, profile_ranks

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
WIDGETS = {'hints': 'Подсказки', 'perf': 'Показатели (CS, золото, KDA…)', 'lane': 'Оппонент на линии',
           'inventory': 'Чемпионы по стоимости предметов (от большего к меньшему)',
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
    'widgets': {k: False for k in WIDGETS},
    'widget_pins': {},
    'perf': {'metrics': {'csm': True, 'gpm': True, 'kda': True, 'kp': True, 'vsm': True}, 'layout': 'vertical', 'compare': 'norm'},
    'tab_step': 76, 'tab_pos': {}, 'tab_rect': None, 'tab_auto': True,
    'phone': False, 'phone_port': 8765, 'phone_token': '',
    'draft_scope': 'pool', 'draft_build_context': 'general', 'draft_auto_mode_v1': True, 'dashboard': True, 'scoreboard': True, 'postgame': True, 'auto_import': False, 'auto_parts': {'runes': False, 'items': False, 'spells': False}, 'rune_pick': 'pick', 'hint_text': {},
    'theme': 'lol', 'accent': 'theme', 'font': 'Golos Text', 'scale': 100, 'icon': 36, 'alpha': 90, 'widget_bg': 'panel',
    'show': {k: True for k in SHOW},
    'layout': {}, 'champion_pools': {}, 'home_period': 'season',
    'keys': {'mute': 'ctrl+shift+m', 'hide': 'ctrl+shift+h', 'scoreboard': 'tab', 'drag': 'alt', },
    'voice': 'dmitri', 'volume': 80, 'rate': 1.0, 'master': 100, 'beep_volume': 70, 'sound': 'bell',
    'obj': dict(core.OBJ), 'who': '', 'auto_update': True,
}
SECTIONS = {   # что сбрасывает кнопка «По умолчанию» в каждом разделе
    'hints': ['hints', 'hints_role'], 'voice': ['voice', 'volume', 'rate', 'master', 'beep_volume', 'sound'],
    'look': ['theme', 'accent', 'font', 'scale', 'icon', 'alpha', 'widget_bg', 'show'],
    'windows': ['widgets', 'widget_pins', 'perf', 'tab_step', 'tab_pos', 'tab_rect', 'tab_auto', 'dashboard', 'scoreboard', 'postgame', 'layout'], 'keys': ['keys'], 'obj': ['obj'],
}


class Settings(dict):
    def __init__(self, home):
        super().__init__()
        self.path = os.path.join(home, 'settings.json')
        try:
            with open(self.path, encoding='utf-8') as source: saved = json.load(source)
        except Exception: saved = {}
        for k, v in DEFAULTS.items():
            self[k] = ({**v, **saved.get(k, {})} if isinstance(v, dict) else saved.get(k, v))
        if saved.get('auto_import') and 'auto_parts' not in saved:   # раньше была одна галка на всё
            self['auto_parts'] = {'runes': True, 'items': True, 'spells': False}
        if 'draft_auto_mode_v1' not in saved:
            self['auto_import'] = any(self['auto_parts'].values())
            self['draft_auto_mode_v1'] = True
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
        with open(tmp, 'w', encoding='utf-8') as output:
            json.dump(dict(self), output, ensure_ascii=False, indent=1)
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
        self.rounded = OrderedDict()
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

    def rounded_pil(self, grp, key, size, gray=False, ring=None):
        im = self._pil(grp, key)
        if im is None: return None
        k = (grp, key, size, gray, ring)
        cached = self.rounded.get(k)
        if cached is not None and cached[0] is im:
            self.rounded.move_to_end(k)
            return cached[1]
        result = render.rounded_icon(im, size, gray=gray, ring=ring)
        self.rounded[k] = (im, result)
        self.rounded.move_to_end(k)
        if len(self.rounded) > 128: self.rounded.popitem(last=False)
        return result


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
        self.pinned = bool(app.s.get('widget_pins', {}).get(key)) if key != 'tab' else False
        self.pin_window = None
        if key != 'tab':
            # Separate tiny HWND stays interactive while the entire body passes clicks.
            self.pin_window = tk.Toplevel(self)
            self.pin_window.withdraw()
            self.pin_window.overrideredirect(True)
            self.pin_window.attributes('-topmost', True)
            self.pin_window.attributes('-alpha', app.s['alpha'] / 100)
            self.pin_button = tk.Button(self.pin_window, bd=0, highlightthickness=0,
                                        takefocus=False, cursor='hand2', command=self.toggle_pin)
            self.pin_button.pack()
            self.pin_window.update_idletasks()
            click_through(self.pin_window, False)
            self._draw_pin()
            self.bind('<Configure>', self._pin_configure, add='+')
            self.bind('<Map>', self._pin_configure, add='+')
            self.bind('<Unmap>', self._pin_configure, add='+')
        for w in (self, self.lbl):
            w.bind('<ButtonPress-1>', self._start); w.bind('<B1-Motion>', self._move); w.bind('<ButtonRelease-1>', self._end)

    def _start(self, e):
        if self.unlocked and not self.pinned:
            self._drag = (e.x_root - self.winfo_x(), e.y_root - self.winfo_y())

    def _move(self, e):
        if self._drag and not self.pinned: self.geometry(f'+{e.x_root - self._drag[0]}+{e.y_root - self._drag[1]}')

    def _end(self, e):
        if self._drag:
            self._drag = None
            self.app.layout()[self.key] = [self.winfo_x(), self.winfo_y()]
            self.app.s.save()

    def unlock(self, on):
        if not on and self._drag: self._end(None)
        self.unlocked = on
        movable = on and not self.pinned
        click_through(self, not movable)
        self.configure(highlightthickness=2 if movable else 0, highlightbackground=C['gold'])

    def toggle_pin(self):
        if self._drag: self._end(None)
        self.pinned = not self.pinned
        self.app.s.setdefault('widget_pins', {})[self.key] = self.pinned
        self.app.s.save()
        self.unlock(self.unlocked)
        self._draw_pin()

    def _draw_pin(self):
        self._pin_ph = ImageTk.PhotoImage(render.pin_icon(self.pinned, self.app.s['scale']/100))
        self.pin_button.configure(image=self._pin_ph, bg='#081b22', activebackground='#162d33',
                                  text='Открепить' if self.pinned else 'Закрепить')

    def _pin_configure(self, event):
        if event.widget is self: self._sync_pin()

    def _sync_pin(self):
        pin = self.pin_window
        if pin is None: return
        if not self.winfo_viewable(): pin.withdraw(); return
        size = self._pin_ph.width()
        x, y = self.winfo_rootx()+self.winfo_width()-size-3, self.winfo_rooty()+3
        pin.geometry(f'{size}x{size}{x:+d}{y:+d}')
        if not pin.winfo_viewable(): pin.deiconify()
        pin.lift()

    def withdraw(self):
        pin = getattr(self, 'pin_window', None)
        if pin is not None: pin.withdraw()
        super().withdraw()

    def lift(self, aboveThis=None):
        super().lift(aboveThis)
        if self.pin_window is not None: self._sync_pin()

    CAPS = {'hints': 'Подсказки', 'perf': 'Твои показатели', 'lane': 'Линия', 'inventory': 'Стоимость инвентаря',
            'item': 'До предмета', 'timers': 'Таймеры', 'arena': 'Арена'}

    def card(self, accent=None, width=None, title=True):
        return render.Card(C, 'Forum', self.app.s['scale'] / 100, plate=self.app.s['widget_bg'] != 'none', accent=accent, width=width,
                           title=self.CAPS.get(self.key) if title else None)

    def put(self, card):
        if Image is None: return
        signature = card.signature()
        if signature == getattr(self, '_card_signature', None): return
        im = card.render()
        self._ph = ImageTk.PhotoImage(im)
        self.lbl.configure(image=self._ph)
        self._card_signature = signature
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
        f = render.font('Forum', c.px(15))
        for i, (t, text, color, at) in enumerate(reversed(self.items)):
            new = i == 0
            col = (color if color != 'fg' else 'fg') if new else 'mute'
            for j, ln in enumerate(render.wrap(text, f, c.px(280))):
                lead = ('img',render.warning_icon(c.px(24))) if new and j==0 else ('gap',24)
                c.row(lead,('cell', at if j == 0 else '', 'warn' if new else 'mute', 11, True, 38, 'l'), ('text', ln, col, 15 if new else 12, new), pad=2)
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
        for name, v, col, n, u in (('CS/мин', '7,4', 'good', '6,8', '7,1'), ('Золото/мин', '—', 'fg', '398', '425'), ('KDA', '3,2', 'good', '2,9', '2,7'),
                                   ('Участие, %', '48', 'fg', '52', '—'), ('Обзор/мин', '0,62', 'fg', '0,55', '—')):
            c.row(('cell', name, 'mute', 11, False, 74, 'l'), ('cell', v, col, 15, True, 56, 'r'), ('cell', n, 'fg', 12, False, 64, 'r'), ('cell', u, 'fg', 12, False, 64, 'r'), pad=3)
        self.put(c)

    def __init__(self, app, xy):
        super().__init__(app, 'perf', xy)

    def values(self, g):return performance_model.live_values(g)

    def refs(self, g):
        cfg,me=self.app.s['perf'],g.me
        if cfg['compare']=='emerald':
            lo=self.app.data.lola.get(f"{me['c']}|{g.role}")
            return performance_model.benchmark(lo),('Изумруд+ · среднее за матч' if lo else 'Изумруд+: нет данных')
        n=performance_model.personal(self.app.player,me['c'],g.role)
        return n,(f"Твой чемпион и роль · {n['n']} игр" if n.get('n') else 'Нужно 3 игры на чемпионе и роли')

    def show(self, g):
        cfg = self.app.s['perf']
        vals = self.values(g)
        on = [k for k in self.METRICS if cfg['metrics'].get(k)]
        c = self.card(width=0)
        if cfg['layout'] == 'vertical':
            app = self.app
            norm = performance_model.personal(app.player,g.me['c'],g.role)
            up = app.tier_bench(g.me['c'], g.role)
            tier = up['tier'] if up else app.next_tier()[1]
            c.row(('cell', '', 'mute', 9, False, 74, 'l'), ('cell', 'СЕЙЧАС', 'mute', 9, True, 56, 'r'), ('cell', 'ТЫ ОБЫЧНО', 'mute', 9, True, 64, 'r'),
                  ('cell', tier.upper() if tier else 'РАНГ ВЫШЕ', 'mute', 9, True, 64, 'r'), pad=3)
            for k in on:
                name, dec = self.METRICS[k]
                v, n, u = vals[k], norm.get(k), (up or {}).get(k)
                ref = u if u is not None else n
                col = 'fg' if ref is None or v is None else 'good' if v >= ref else 'warn'
                f = lambda x: '—' if x is None else f'{x:.{dec}f}'.replace('.', ',')
                c.row(('cell', name, 'mute', 11, False, 74, 'l'), ('cell', f(v), col, 15, True, 56, 'r'), ('cell', f(n), 'fg', 12, False, 64, 'r'),
                      ('cell', f(u), 'fg', 12, False, 64, 'r'), pad=3)
        else:
            ref, title = self.refs(g)
            segs = []
            for k in on:
                name, dec = self.METRICS[k]
                v, r = vals[k], ref.get(k)
                col = 'fg' if r is None or v is None else 'good' if v >= r else 'warn'
                segs += [('text', name, 'mute', 10, False), ('text', '—' if v is None else f'{v:.{dec}f}', col, 12, True)]
                if r: segs.append(('text', f'/{r:.{dec}f}', 'mute', 10, False))
                segs.append(('gap', 8))
            c.row(*segs)
        self.put(c)


class LaneOverlay(Overlay):
    def __init__(self, app, xy):
        super().__init__(app, 'lane', xy)

    def show(self, g):
        if not g.opp: self.put(self.card().row(('text', 'Оппонент не определён', 'mute', 11, False))); return
        self.draw(g.opp,g.me,g.lane_diff())

    def draw(self,o,me,delta):
        col = 'blue' if delta>0 else 'red' if delta<0 else 'mute'
        c = self.card()
        icon = self.app.pimg('champ', o['c'], 1.0, gray=o['dead'], ring=C['red'])
        value=render.Card(C,'Forum',self.app.s['scale']/100,plate=False)
        value.row(('text',f'{delta:+.0f}',render.HUD[col],24,True))
        value.row(('text','против '+self.app.data.cn(o['c']),render.HUD['fg'],11,False))
        segs = ([('img', icon)] if icon else []) + [('img',value.render())]
        c.row(*segs)
        c.row(('text', f"ур. {me['lvl']} / {o['lvl']} · CS {me['cs']} / {o['cs']} · {o['k']}/{o['d']}/{o['a']}", 'mute', 10, False))
        self.put(c)

    def demo(self):
        self.draw({'c':'Viktor','dead':False,'lvl':10,'cs':80,'k':2,'d':3,'a':1},
                  {'lvl':11,'cs':92},850)


class InventoryOverlay(Overlay):
    """Общий рейтинг чемпионов: стоимость предметов, а не заработанное/наличное золото."""
    def __init__(self, app, xy):
        super().__init__(app, 'inventory', xy)

    def show(self, g):
        self.draw(core.inventory_ranking(g.players), g.my_team, g.me)

    def draw(self, players, my_team, me):
        c = self.card()
        c.row(('text', 'С — союзник · В — враг · ты — твой герой', 'mute', 9, False), pad=3)
        for rank, p in enumerate(players, 1):
            team = 'С' if p['team'] == my_team else 'В'
            color = 'gold' if p is me else 'blue' if p['team'] == my_team else 'red'
            icon = self.app.pimg('champ', p['c'], .65, gray=p.get('dead', False), ring=C[color])
            segs = [('cell', str(rank), 'mute', 10, False, 16, 'r'),
                    ('cell', 'ты' if p is me else team, color, 10, True, 18, 'l')]
            if icon: segs.append(('img', icon))
            segs += [('cell', self.app.data.cn(p['c']), color, 11, p is me, 120, 'l'),
                     ('bar', p['igold']/max(1,players[0]['igold']), color, 'deep', 36),
                     ('cell', f"{p['igold']:,.0f}".replace(',', ' '), 'fg', 13, True, 62, 'r')]
            c.row(*segs, pad=3)
        if not players: c.row(('text', 'Жду данные игры…', 'mute', 11, False))
        c.row(('text', 'Без зелий, вардов и тотемов', 'mute', 9, False), pad=5)
        self.put(c)

    def demo(self):
        champs = ('Sett', 'Jinx', 'Ahri', 'Darius', 'Viktor', 'LeeSin', 'Caitlyn', 'RekSai', 'Lux', 'Rakan')
        players = [{'riot': f'P{i}', 'c': c, 'team': 'ORDER' if i % 2 == 0 else 'CHAOS',
                    'igold': gold} for i, (c, gold) in enumerate(zip(champs, (11800, 10560, 10300, 9800, 8950, 7720, 7400, 6200, 5290, 5200)))]
        self.draw(core.inventory_ranking(players), 'ORDER', players[0])


class ItemOverlay(Overlay):
    """Сколько золота до следующего предмета из твоей лучшей сборки."""
    def __init__(self, app, xy):
        super().__init__(app, 'item', xy)

    def show(self, g):
        plan = core.next_item_plan(self.app.data, self.app.player, g.me['c'], g.me['items'], g.gold)
        d = self.app.data
        if not plan:
            self.put(self.card().row(('text', 'Сборка готова или нет данных', 'mute', 11, False))); return
        self.draw_plan(plan)

    def draw_plan(self,plan):
        d=self.app.data
        it, cp = self.app.pimg('item', plan['item'], 1.0), self.app.pimg('item', plan['comp'], .8)
        c = self.card()
        if plan['comp_need'] == 0:
            segs = [('text', 'можно купить', 'good', 12, True)]
        else:
            segs = [('text', f"ещё {int(plan['comp_need'])}", 'gold', 24, True)]
        c.row(*(([('img', it)] if it else []) + ([('img', cp)] if cp and plan['comp'] != plan['item'] else []) + segs))
        line = d.iname(plan['comp']) if plan['comp'] == plan['item'] else f"{d.iname(plan['comp'])} → {d.iname(plan['item'])}, всего ещё {int(plan['need'])}"
        c.row(('text', line, 'mute', 10, False))
        self.put(c)

    def demo(self):
        self.draw_plan({'item':1036,'comp':1036,'comp_need':350,'need':350})


class ArenaOverlay(Overlay):
    """Арена: счёт, золото и стоимость предметов, плюс твоё среднее место на этом чемпионе. Урона и места в лобби игра во время матча не отдаёт."""
    def __init__(self, app, xy):
        super().__init__(app, 'arena', xy)

    def show(self, g):
        me = g.me
        if not me: return
        c = self.values_card(f"{me['k']}/{me['d']}/{me['a']}",int(g.gold),int(me['igold']))
        st = core.arena_stats(self.app.arena_games(), me['c'])
        if st: c.row(('text', f"на {self.app.data.cn(me['c'])}: среднее место {st['avg']:.1f} за {st['n']} игр".replace('.', ','), 'mute', 10, False))
        self.put(c)

    def demo(self):
        self.put(self.values_card('7/3/5',1350,6200))

    def values_card(self,kda,gold,inventory):
        c=self.card()
        c.row(('cell',kda,'fg',22,True,82,'r'),
              ('cell',f'{gold:,}'.replace(',',' '),'gold',22,True,82,'r'),
              ('cell',f'{inventory:,}'.replace(',',' '),'fg',22,True,82,'r'))
        c.row(('cell','счёт','mute',10,False,82,'r'),
              ('cell','золото','mute',10,False,82,'r'),
              ('cell','в предметах','mute',10,False,82,'r'))
        return c


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
            icon = render.objective_icon(name,c.px(24))
            c.row(('img',icon) if icon else ('gap',24),('cell', name, 'fg' if left > 0 else 'mute', 11, False, 110, 'l'),
                  ('cell', core.mmss(left) if left > 0 else 'на карте', 'gold' if soon else 'fg' if left > 0 else 'good', 12, True, 62, 'r'))
        if cannon: c.row(('cell', 'Осадный миньон', 'mute', 10, False, 110, 'l'), ('cell', core.mmss(cannon), 'mute', 11, True, 62, 'r'))
        self.put(c)

    def demo(self):
        self.draw([('Адский дракон', 45), ('Личинки', -1), ('Барон', 412)], 38)


def tab_rect_drag(rect, dx, dy, resize=False):
    """Смещение в долях высоты окна игры; resize сохраняет левый верхний угол."""
    l, t, w, h = rect
    if resize: w, h = max(.2, w + dx), max(.1, h + dy)
    else: l, t = l + dx, t + dy
    return [round(v, 4) for v in (l, t, w, h)]


class TabPlates(Overlay):
    """Разница стоимости предметов между игроками в строках Tab.

    Всё большое окно всегда пропускает клики. Только отдельная небольшая ручка
    принимает мышь в режиме расстановки: перетаскивание — перенос, Shift — размер.
    """
    def __init__(self, app):
        super().__init__(app, 'tab', (0, 0))
        self.data, self._geometry_sig = None, None
        self.auto_layout, self._auto_context = None, None
        self._auto_results, self._auto_cancel = queue.Queue(), threading.Event()
        self._auto_pending, self._auto_active = False, False
        self._auto_epoch, self._auto_next, self._auto_time = 0, 0., 0.
        self.auto_status = 'Автоподгонка: ожидаю Tab в игре'
        self._left_ally = True
        self.bind('<Destroy>', self._stop_detection, add='+')
        # Не оставлять обработчики переноса на большой поверхности даже вне Windows.
        for w in (self, self.lbl):
            for event in ('<ButtonPress-1>', '<B1-Motion>', '<ButtonRelease-1>'): w.unbind(event)
        self.handle = tk.Toplevel(self)
        self.handle.withdraw()
        self.handle.overrideredirect(True)
        self.handle.attributes('-topmost', True)
        self.handle.configure(bg=C['gold'])
        if Image is not None:
            self._handle_ph = ImageTk.PhotoImage(render.tab_handle(C, F['font'], app.s['scale'] / 100))
            label = tk.Label(self.handle, image=self._handle_ph, bg=C['gold'], bd=0, padx=0, pady=0, cursor='fleur')
        else:
            label = tk.Label(self.handle, text='TAB · тяни | Shift: размер', bg=C['gold'], fg=C['on_gold'], cursor='fleur')
        label.pack()
        for w in (self.handle, label):
            w.bind('<ButtonPress-1>', self._start)
            w.bind('<B1-Motion>', self._move)
            w.bind('<ButtonRelease-1>', self._end)
        self.handle.update_idletasks()
        click_through(self.handle, False)   # WS_EX_NOACTIVATE: ручка не забирает фокус игры
        self.handle.attributes('-alpha', app.s['alpha'] / 100)
        self.withdraw()

    def rect(self):
        if self.app.s.get('tab_auto') and self.auto_layout: return self.auto_layout.rect
        r = self.app.s.get('tab_rect')
        if r: return r
        dx, y = self.app.s['tab_pos'].get('tabgold', [-.553, .288])
        return [dx, y, -2 * dx, 5 * self.app.s['tab_step'] / 1080]

    def k(self):
        return game_rect()[3] / 1080 * self.app.s['scale'] / 100

    def geom(self):
        gx, gy, gw, gh = game_rect()
        l, t, w, h = self.rect()
        side = 0
        top = round(h*gh*.35+max(30,46*self.k())) if self.__dict__.get('totals') is not None else 0
        return gx + gw / 2 + l * gh, gy + t * gh, w * gh, h * gh, side, top

    def draw(self, rows):
        X, Y, W, H, side, tp = self.geom()
        scale = self.k()
        signature = (X,Y,W,H,side,tp,scale,self.unlocked,self._left_ally,
                     self.__dict__.get('totals'),tuple(sorted(C.items())),
                     tuple(tuple(p['v'] if p is not None else None for p in row) for row in rows))
        if signature == getattr(self, '_tab_draw_signature', None): return
        im = render.tab_plates((side, tp, W, H), rows, C, scale, frame=self.unlocked,
                               left_ally=self._left_ally, totals=self.__dict__.get('totals'))
        self._ph = ImageTk.PhotoImage(im)
        self.lbl.configure(image=self._ph)
        self.geometry(f'{im.width}x{im.height}+{int(X - side)}+{int(Y - tp)}')
        self._geometry_sig = (game_rect(), tuple(self.rect()), self.app.s['scale'])
        self._place_handle()
        self._tab_draw_signature = signature

    def refresh_geometry(self):
        sig = (game_rect(), tuple(self.rect()), self.app.s['scale'])
        if self.data and sig != self._geometry_sig: self.draw(*self.data)

    def _place_handle(self):
        if not self.unlocked or not self.winfo_viewable() or (self.app.s.get('tab_auto') and self.auto_layout):
            self.handle.withdraw(); return
        X, Y, W, H, side, tp = self.geom()
        vx, vy, vw, vh = screens()[2]
        hw, hh = self.handle.winfo_reqwidth(), self.handle.winfo_reqheight()
        x = max(vx, min(int(X), vx + vw - hw))
        y = max(vy, min(int(Y - tp - hh - 6), vy + vh - hh))
        self.handle.geometry(f'+{x}+{y}')
        self.handle.deiconify()
        self.handle.lift()

    def deiconify(self):
        super().deiconify()
        if not getattr(self,'_handle_job',None):
            def place():
                self._handle_job=None
                if self.winfo_exists():self._place_handle()
            self._handle_job=self.after_idle(place)

    def withdraw(self):
        handle = self.__dict__.get('handle')
        job=getattr(self,'_handle_job',None)
        if job:
            self.after_cancel(job);self._handle_job=None
        if handle: handle.withdraw()
        super().withdraw()

    def show(self, g):
        rows = []
        layout = self.auto_layout if self.app.s.get('tab_auto') else None
        self._left_ally = not layout or layout.teams[0] == g.my_team
        left = g.allies if self._left_ally else g.enemies
        right = g.enemies if self._left_ally else g.allies
        self.totals = (sum(p['igold'] for p in left), sum(p['igold'] for p in right)) if left and right else None
        for i, r in enumerate(core.ROLES):
            a = next((p for p in left if (p['c'] == layout.columns[0][i] if layout else p['pos'] == r)), None)
            e = next((p for p in right if (p['c'] == layout.columns[1][i] if layout else p['pos'] == r)), None)
            # Compare the two visible players in this row, including manual reordering.
            rows.append(({'v': a['igold']} if a else None, {'v': e['igold']} if e else None))
        self.data = (rows,)
        self.draw(*self.data)

    def _stop_detection(self, event):
        if event.widget is self:
            self._auto_cancel.set()
            job=getattr(self,'_handle_job',None)
            if job:
                self.after_cancel(job);self._handle_job=None

    def _detection_status(self, text):
        if text == self.auto_status: return
        self.auto_status = text
        label = getattr(self.app, 'tab_auto_label', None)
        if label and label.winfo_exists(): label.configure(text=text)

    def auto_tick(self, active, g):
        """Called only on Tk's thread. Workers return plain data through a queue."""
        now = time.monotonic()
        # Practice/custom games can have fewer than ten players. The frame detector
        # validates those without inventing the missing portraits.
        active = bool(active and IS_WIN and self.app.s.get('tab_auto') and g and g.players)
        context = (game_rect(), tuple(sorted((p['riot'], p['c'], p['team']) for p in g.players))) if g else None
        reset = context != self._auto_context or (g and g.t < self._auto_time)
        if reset or active != self._auto_active:
            self._auto_cancel.set()
            self._auto_epoch += 1
            self._auto_next = now + .20  # allow the game's opening animation to finish
            if active: self._detection_status(f'Автоподгонка: запускаю поиск · игроков {len(g.players)}')
        if reset: self.auto_layout = None
        self._auto_context, self._auto_active = context, active
        self._auto_time = g.t if g else 0
        while not self._auto_results.empty():
            epoch, result, error = self._auto_results.get_nowait()
            self._auto_pending = False
            if epoch != self._auto_epoch or not active: continue
            if error:
                log_error('Tab: автоподгонка', error)
                self._detection_status('Автоподгонка недоступна; используется сохранённая рамка')
            elif result:
                self.auto_layout = result
                known = sum(c is not None for col in result.columns for c in col)
                source = 'по рамке' if result.source == 'frame' else 'по портретам'
                self._detection_status(f'Таблица найдена {source} · распознаны строки {known}/{len(g.players)}')
                self.show(g)
            else:
                self._detection_status('Таблица не распознана · последняя рамка; ручная настройка через Alt')
        if not self.app.s.get('tab_auto'):
            self._detection_status('Автоподгонка выключена · ручная настройка через Tab + Alt')
        elif not g or not g.players:
            self._detection_status('Автоподгонка: ожидаю игровые данные от клиента LoL')
        if not active or self._auto_pending or now < self._auto_next: return
        self._auto_next, self._auto_pending = now + 2.5, True
        if not self.auto_layout:
            self._detection_status(f'Автоподгонка: ищу таблицу · игроков {len(g.players)}')
        self._auto_cancel = cancel = threading.Event()
        epoch, results = self._auto_epoch, self._auto_results
        rect = context[0]
        players = [dict(p) for p in g.players]
        portraits = dict(getattr(self.app.icons, 'a', {}).get('champ', {}))
        def work():
            result, error = None, None
            try:
                if not cancel.is_set() and game_focused() and game_rect() == rect:
                    result = tab_detect.capture_and_detect(rect, portraits, players, cancel)
            except Exception as e: error = str(e)
            results.put((epoch, result, error))
        threading.Thread(target=work, daemon=True, name='tab-detection').start()

    def demo(self):
        self._left_ally = True
        vals = ((9800, 8950), (7400, 7720), (10300, 10300), (11800, 10560), (5200, 5290))
        self.totals = (sum(a for a,_ in vals),sum(b for _,b in vals))
        rows = [({'v': a}, {'v': e}) for a, e in vals]
        self.data = (rows,)
        self.draw(*self.data)

    def unlock(self, on):
        if not on and self._drag: self._end(None)
        if self.unlocked==on:
            if not on:self.handle.withdraw()
            return
        self.unlocked = on
        click_through(self, True)   # в том числе при Alt: игровая таблица остаётся кликабельной
        if self.data and self.winfo_viewable(): self.draw(*self.data)
        if not on: self.handle.withdraw()

    def _start(self, e):
        self.auto_layout = None
        self._drag = (e.x_root, e.y_root, list(self.rect()), max(1, game_rect()[3]), bool(e.state & 0x1))

    def _move(self, e):
        if not self._drag: return
        x0, y0, rect, gh, resize = self._drag
        self.app.s['tab_rect'] = tab_rect_drag(rect, (e.x_root - x0) / gh, (e.y_root - y0) / gh, resize)
        if self.data: self.draw(*self.data)

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
    if not h.get('n'): return [('История игрока недоступна','gold')] + [(text, {'good':'good','neutral':'gold','bad':'bad'}[tone]) for _,text,tone in player_comments.comments(h) if _ != 'N3']
    st = h['streak']
    top = [f"{h['w']}–{h['n'] - h['w']} за {h['n']}"]
    if abs(st) >= 2: top.append(f"серия {'+' if st > 0 else '−'}{abs(st)}")
    if h['on']: top.append(f"на чемпионе {h['on']} игр, {round(h['on_w'] / h['on'] * 100)}%")
    top.append(f"KDA {h['kda']}")
    out = [(' · '.join(top), 'fg')]
    out.extend((text, {'good':'good', 'neutral':'gold', 'bad':'bad'}[tone]) for _,text,tone in player_comments.comments(h))
    return out


def hist_tags(h):
    """Метки игрока в стиле Porofessor: (текст, вид g|r|y|n) и строка итога последних игр."""
    if not h: return '', []
    tags = [(text, {'good':'g','neutral':'y','bad':'r'}[tone]) for _,text,tone in player_comments.comments(h)]
    if not h.get('n'): return 'История игрока недоступна', tags
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
        self.cv = ScrollCanvas(self.wrap, bg=C['bg'], highlightthickness=0)
        sb = ttk.Scrollbar(self.wrap, orient='vertical', command=self.cv.yview)
        self.body = tk.Frame(self.cv, bg=C['bg'])
        self.body.bind('<Configure>', lambda e: (self.cv.configure(scrollregion=self.cv.bbox('all')),
                                                 sb.pack(side='right', fill='y') if self.body.winfo_reqheight() > self.cv.winfo_height() else sb.pack_forget()))
        win = self.cv.create_window((0, 0), window=self.body, anchor='nw'); self.cv.configure(yscrollcommand=sb.set)
        self.cv.bind('<Configure>', lambda e: self.cv.itemconfigure(win, width=e.width), add='+')
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
        self._manual_hidden=True
        self.withdraw()

    def clear(self, mode):
        if self.mode == mode: return
        self.mode = mode
        if mode != 'draft':
            self._draft_view = None
            self.configure(bg=C['bg'])
            self.head.configure(bg=C['bg'], font=(F['head'], self.app.fs(22)))
            for surface in (self.sub, self.body, self.cv, self.wrap, self.bar, self.timer):
                surface.configure(bg=C['bg'])
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
        sig = json.dumps(['arena', me, bool(lo), [(a['c'], bool(a.get('rank')), a.get('hist')) for a in cs.get('allies', [])]], default=str)
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
        sig = json.dumps([(p['c'], p['pos'], p['ok'], bool(p['rank']), p.get('hist')) for p in ps], default=str)
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
                          self.app.s.get('draft_scope'), cs.get('locked'), self.app.s.get('rune_pick'), self.app.s.get('draft_build_context'),
                          [(a['c'], a.get('pos'), bool(a.get('rank')), a.get('hist')) for a in cs.get('allies', [])], [x['c'] for x in r['picks']]], default=str)
        self.clear('draft')
        if sig == self.draft_sig: return
        self.draft_sig = sig
        y = self.cv.yview()[0]
        no_flicker(self, lambda: self._show_draft(cs, r, bans, me, eu))
        self.cv.yview_moveto(y)   # прокрутка остаётся на месте

    def _show_draft(self, cs, r, bans, me, eu):
        from draft_ui import render_draft
        render_draft(self, cs, r, bans, me, eu, C, F)

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
        auto_mode = tk.BooleanVar(value=app.s['auto_import'])
        def save_auto_mode():
            app.s['auto_import'] = auto_mode.get(); app.s.save()
            app.draft_sig = None
            if app.draft: app.on_draft(app.draft)
        ttk.Checkbutton(row2, text='Автоэкспорт', variable=auto_mode, command=save_auto_mode, style='D.TCheckbutton').pack(side='left')
        tk.Label(row2, text='Экспортировать:', bg=C['deep'], fg=C['mute'], font=(fn, fs(8), 'bold')).pack(side='left')
        for key, t in (('runes', 'руны'), ('items', 'предметы'), ('spells', 'заклинания призывателя')):
            ttk.Checkbutton(row2, text=t, variable=app.auto_vars[key], style='D.TCheckbutton',
                            command=lambda key=key: app.set_import_part(key)).pack(side='left', padx=(10, 0))
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
        row, used, previous_kind = None, maxw, None
        for text, kind in sorted(items, key=lambda item: {'g':0,'y':1,'r':2}.get(item[1],3)):
            if kind != previous_kind or used + len(text) > maxw: row = tk.Frame(parent, bg=bg); row.pack(anchor='w', pady=(4, 0)); used = 0
            colours = player_comments.palette(C['dark'])
            cbg, cfg = {key:colours[tone] for key,tone in (('g','good'),('r','bad'),('y','neutral'))}.get(kind, (C['raise'], C['fg']))
            tk.Label(row, text=text, bg=cbg, fg=cfg, font=(fn, fs(9), 'bold'), padx=8, pady=2, wraplength=fs(330), justify='left').pack(side='left', padx=(0, 6))
            used += len(text) + 3
            previous_kind = kind

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
                    if tags: self.chips(w['chars'], [(text, {'good':'g','neutral':'y','bad':'r'}[tone]) for _,text,tone in player_comments.preview(h)], C['panel'], 70)
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
        self.evidence = player_evidence.Evidence()
        self.evidence_region, self.evidence_region_at = None, 0
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
        self.root.minsize(self.fs(820), self.fs(560))
        self.icons = Icons(self)
        self.set_who(self.s['who'] or 'halch')
        self.build_all()
        self.sync_phone()
        threading.Thread(target=self.poll, daemon=True).start()
        threading.Thread(target=self.load_lanes, daemon=True).start()
        self.root.after(300, self.drain)
        self.root.after(40, self.keys)
        self.root.bind('<Escape>', self.stop_demo, add='+')
        self.root.after(1000, self.tick_ui)

    def build_all(self, tab=0):
        """Создать (или пересоздать после смены вида/сброса) все окна."""
        apply_theme(self.s)
        self.root.minsize(self.fs(820), self.fs(560))
        for w in self.root.winfo_children(): w.destroy()
        self.root.configure(bg=C['bg'])
        self.style()
        self.build_panel()
        try: self.nb.select(tab)
        except Exception: pass
        self.nav_sync()
        sig, (pw, ph), _ = screens()
        self.ov = {'hints': HintsOverlay(self, (40, int(ph * .30))), 'perf': PerfOverlay(self, (pw - 330, 80)),
                   'lane': LaneOverlay(self, (pw - 330, 300)),
                   'item': ItemOverlay(self, (pw - 330, 400)), 'timers': TimersOverlay(self, (pw - 330, 490)),
                   'arena': ArenaOverlay(self, (pw - 330, 80)), 'inventory': InventoryOverlay(self, (max(40, pw - 650), 80))}
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
        return self.icons.rounded_pil(grp, key, max(12, int(self.s['icon'] * k * self.s['scale'] / 100)), gray=gray, ring=ring)

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
        st.configure('.', background=C['bg'], foreground=C['fg'], fieldbackground=C['panel'], font=(fn, self.fs(11)),
                     bordercolor=C['raise'], lightcolor=C['panel'], darkcolor=C['panel'], troughcolor=C['panel'], focuscolor=C['gold'])
        st.configure('TNotebook', background=C['bg'], borderwidth=0, tabmargins=0)
        st.configure('TNotebook.Tab', background=C['panel'], foreground=C['mute'], padding=(12, 5), bordercolor=C['line'])
        st.map('TNotebook.Tab', background=[('selected', C['line'])], foreground=[('selected', C['gold'])])
        st.configure('Rail.TNotebook', background=C['bg'], borderwidth=0, tabmargins=0, padding=0, bordercolor=C['bg'], lightcolor=C['bg'], darkcolor=C['bg'])
        st.layout('Rail.TNotebook', [('Notebook.client', {'sticky': 'nswe'})])   # без рамки вокруг страницы
        st.layout('Rail.TNotebook.Tab', [])   # вкладки переключает боковое меню
        st.configure('TButton', background=C['raise'], foreground=C['fg'], padding=(14, 7), bordercolor=C['raise'],
                     lightcolor=C['raise'], darkcolor=C['raise'], font=(F['font'], self.fs(11)))
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
        self.root.option_add('*TCombobox*Listbox.font',(fn,self.fs(11)))
        self.root.option_add('*TCombobox*Listbox.background', C['panel'])
        self.root.option_add('*TCombobox*Listbox.foreground', C['fg'])
        self.root.option_add('*TCombobox*Listbox.selectBackground', C['gold'])
        st.configure('TEntry', fieldbackground=C['panel'], foreground=C['fg'], insertcolor=C['fg'])
        st.configure('Horizontal.TScale', background=C['gold'], troughcolor=C['line'], bordercolor=C['line'], lightcolor=C['gold'], darkcolor=C['gold'])
        st.layout('Vertical.TScrollbar', [('Vertical.Scrollbar.trough', {'sticky': 'ns', 'children': [('Vertical.Scrollbar.thumb', {'expand': '1', 'sticky': 'nswe'})]})])
        st.configure('Vertical.TScrollbar', background=C['raise'], troughcolor=C['bg'], bordercolor=C['bg'], lightcolor=C['raise'], darkcolor=C['raise'],
                     gripcount=0, arrowsize=self.fs(6), width=self.fs(6))
        st.configure('H.TLabel', foreground=C['gold'], font=(F['font'], self.fs(15), 'bold'))
        st.configure('Cap.TLabel', foreground=C['fg'], font=(F['font'], self.fs(11)))
        from view_components import readable_palette
        st.configure('M.TLabel', foreground=readable_palette(C)['mute'])
        st.configure('V.TLabel', foreground=C['gold'])

    def set_who(self, who):
        if who not in self.data.d['players']: who = None
        self.player = core.Player(self.data, who) if who else None
        self.who = who
        if self.player: self.player.pool = self.current_pool()
        view = getattr(self, 'pool_view', None)
        if view and view.winfo_exists(): view.refresh()
        history=getattr(self,'history_view',None)
        if history and history.winfo_exists(): history.profile_changed()
        champion=getattr(self,'champion_view',None)
        if champion and champion.winfo_exists(): champion.refresh()
        self.engine = None

    def current_pool(self):
        defaults = self.data.d.get('pools',{}).get(self.who or '',{})
        return champion_pool.saved_pool(self.s,self.who or 'local',defaults,set(self.data.ids.values()))

    def toggle_pool(self, champion, role):
        if champion not in self.data.ids.values() or role not in core.ROLES: raise ValueError('Неизвестный чемпион или роль')
        pool = self.current_pool()
        if champion in pool[role]: pool[role].remove(champion)
        else: pool[role].append(champion)
        old = self.s.get('champion_pools',{})
        self.s['champion_pools'] = {**(old if isinstance(old,dict) else {}), self.who or 'local':pool}
        try: self.s.save()
        except Exception:
            self.s['champion_pools'] = old
            raise
        if self.player: self.player.pool = pool
        self.draft_sig = None
        if self.dash: self.dash.draft_sig = None

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
        chosen=getattr(self,'_chosen_draft_build',None)
        context=self.s.get('draft_build_context','general')
        external=context=='offmeta' or context.startswith('player:')
        b=chosen[3] if chosen and chosen[:3]==(g.me['c'],g.role,context) else None
        if not b and not external:b=self.cached_build(g.me['c'],g.role)
        if not b and g.role and not external: self.root.after(0, lambda: self.lola_fetch('build', g.me['c'], g.role)); self.engine.prepped = False
        v = (b or {}).get(self.s['rune_pick']) or b or {}
        self.engine.skills, self.engine.skill_prio = v.get('skills', ''), v.get('skill_prio', '')
        self.engine.situ = (b or {}).get('situ') or []
        lo = self.data.lola.get(f"{g.me['c']}|{g.role}")
        self.engine.bench={'csm':lo['csm']} if lo and type(lo.get('csm')) in (int,float) and lo['csm']<float('inf') and lo['csm']>=0 else None

    def hint_mode(self, hid, role=None):
        """Режим подсказки: общие — один на все роли, ролевые — свой у каждой роли."""
        if hid not in core.HINT_ROLES: return self.s['hints'].get(hid, 'off')
        role = role or self.s['hint_preset']
        if role not in core.HINT_ROLES[hid]: return 'off'
        dflt = next(h[3] for h in core.HINTS if h[0] == hid)
        return self.s['hints_role'].get(role, {}).get(hid, dflt)

    def hint_flags(self, role):
        return {h: self.hint_mode(h, role) != 'off' for h in core.HINT_IDS}

    SR_ONLY = ('lane', 'timers', 'perf', 'item')   # виджеты только для Ущелья: в Арене их нет

    def apply_visibility(self):
        arena = bool(self.last_game and self.last_game.arena)
        no_player=bool(self.last_game and not self.last_game.me)
        non_sr=bool(self.last_game and not getattr(self.last_game,'sr',not arena))
        demo=bool(getattr(self,'demo_on',False) and not self.hidden)
        for k,w in self.ov.items():
            enabled=self.s['widgets'].get(k)
            if demo:
                if enabled and w.unlocked:w.deiconify()
                else:w.withdraw()
                continue
            if k=='hints':
                if self.hidden or no_player or not enabled:w.withdraw()
                continue
            if self.hidden or no_player or not enabled or not self.last_game or (non_sr and k in self.SR_ONLY) or (k=='arena' and not arena):w.withdraw()
            else:w.deiconify()
        if self.hidden or no_player or not self.s.get('scoreboard') or (not demo and (not self.last_game or arena)):
            for w in self.tab.values():w.withdraw()

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
                            me['ranks'] = self.client.ranked_overview()
                            me['rank'] = profile_ranks.legacy_solo(me['ranks'])
                            self.q.put(('me', me, None, None))
                        elif self.account:
                            self.q.put(('me', None, None, None))
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

    def player_history(self, pu, champion_id, pos, riot=''):
        """Вызывается фоновым опросом: готовые данные сразу, подробности догружаются."""
        if not pu: return None
        raw = self.hraw.get(pu)
        champion = self.data.ids.get(str(champion_id))
        self.evidence.request(self.client, pu, raw, champion, champion_id, pos, riot)
        metrics, board = self.evidence.snapshot(pu, champion)
        out = core.summarize_history(raw, champion_id, pos)
        extras = player_traits.traits(raw, champion_id, pos, metrics)
        if board and champion_rank.identity(riot):
            if time.time() - self.evidence_region_at > 300:
                self.evidence_region = self.client.region()
                self.evidence_region_at = time.time()
            rank = champion_rank.lookup(board, champion, riot, self.evidence_region)
            if rank:
                extras.insert(0, ('G10', f"Топ-1000 · №{rank['rank']} в мире · {rank['source']}", 'good'))
                if out is None: out = {'n':0,'w':0,'streak':0,'on':0,'on_w':0,'kda':0,'tags':[], 'good':[], 'bad':[], 'tilt':[]}
                out['champion_rank'] = rank
        if out is not None: out['extra_comments'] = extras
        return out

    def fetch_people(self, g):
        """Звание и история последних игр каждого из десяти через клиент (как в профиле). По одному за проход."""
        for p in g.players:
            if p['riot'] in self.ranks:
                pu = self.pus.get(p['riot'])
                self.hists[p['riot']] = self.player_history(pu, self.cid(p['c']), p['pos'], p['riot'])
                continue
            pu = self.pus.get(p['riot']) or self.client.puuid(p['riot'])
            if pu and pu in self.hraw: raw, self.ranks[p['riot']] = self.hraw[pu], self.rank_pu.get(pu)   # уже скачано на экране загрузки
            else:
                self.ranks[p['riot']] = self.rank_pu[pu] = self.client.rank(pu) if pu else None
                raw = self.client.history(pu) if pu else None
            if pu: self.hraw[pu], self.pus[p['riot']] = raw, pu
            self.hists[p['riot']] = self.player_history(pu, self.cid(p['c']), p['pos'], p['riot'])
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
            riot = (p['gameName']+'#'+p['tagLine']) if not hidden and p.get('gameName') and p.get('tagLine') else ''
            if not riot and pu and pu == (self.account or {}).get('puuid'): riot = self.account.get('riot','')
            out.append({'c': self.data.ids.get(str(champ_id)), 'pos': core.LCU_ROLE.get((p.get('assignedPosition') or '').lower(), ''),
                        'rank': self.ranks.get(pu), 'hist': self.player_history(pu, champ_id, core.LCU_ROLE.get((p.get('assignedPosition') or '').lower(), ''), riot),
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
                        'hist': self.player_history(pu, p['champ'], pos, p['name'])})
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
        deadline = time.perf_counter() + .008
        delay = 300
        try:
            for _ in range(32):
                kind, a, b, c = self.q.get_nowait()
                try:
                    if kind == 'game': self.on_game(a, b, c)
                    elif kind == 'end': self.on_end()
                    elif kind == 'me': self.on_me(a)
                    elif kind == 'draft': self.on_draft(a)
                    elif kind == 'load': self.on_loading(a)
                    elif kind == 'error': self.status.configure(text=f'Ошибка: {a}')
                except Exception as error:
                    log_error('событие интерфейса ' + str(kind), error)
                if time.perf_counter() >= deadline:
                    delay = 1
                    break
            else:
                delay = 1
        except queue.Empty:
            pass
        finally:
            try: self.root.after(delay, self.drain)
            except (tk.TclError, RuntimeError): pass

    def on_me(self, me):
        self.account, self.my_rank = me, (me or {}).get('rank')
        history=getattr(self,'history_view',None)
        if history and history.winfo_exists(): history.account_changed(me)
        if not me:
            self.panel_sync(); return
        who = self.data.who_by_riot(me['riot'])
        if who and who != self.who:
            self.s['who'] = who; self.s.save(); self.set_who(who)
        self.panel_sync()

    def on_game(self, g, hints, result):
        first = self.last_game is None
        self.last_game, self.result = g, result or self.result
        self.apply_visibility()
        if not g.me:
            self.status.configure(text='Ожидаю данные твоего игрока из клиента')
            return
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
        for k in ('perf', 'lane', 'item', 'timers', 'arena', 'inventory'):
            if not self.s['widgets'].get(k) or (not getattr(g,'sr',not g.arena) and k in self.SR_ONLY) or (k == 'arena' and not g.arena): continue
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
        if g and g.me and getattr(g,'sr',not g.arena) and self.engine and self.s['postgame'] and g.t > 300 and self.hint_mode('postgame') != 'off':
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
        new_draft=self.draft is None and cs is not None
        self.draft = cs
        if cs is None:
            if self.phone_srv: self.phone_srv.state = {'mode': 'idle'}
            self.role_override = None
            if self.dash and self.draft_sig not in (None, 'none'): self.dash.idle()
            self.draft_sig = 'none'
            self.imported = None; return
        if not self.dash:self.open_dash()
        elif new_draft and getattr(self.dash,'_manual_hidden',False):
            self.dash._manual_hidden=False;self.dash.deiconify()
        sig = json.dumps([cs['role'], self.role_override, self.s.get('draft_scope'), cs.get('locked'), cs['me'], cs['enemies'], sorted(cs['unavailable']), len(self.lola), [(a['c'], bool(a['rank']), a.get('hist')) for a in cs.get('allies', [])]], default=str)
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
            if self.s['auto_import'] and auto and cs['locked'] and cs['me'] and self.imported != cs['me']: self.do_import(auto)
            return
        r = core.draft_suggest(p, role, cs['enemies'], cs['unavailable'], scope=self.s.get('draft_scope', 'pool'))
        r['role'], r['how'] = role, how
        export_target = (cs['me'], role, self.s.get('draft_build_context'), r.get('opp') if self.s.get('draft_build_context') == 'matchup' else None)
        if getattr(self, '_draft_export_target', None) != export_target:
            self.imported = None; self._draft_export_target = export_target
        for a in cs.get('allies') or []:
            if a.get('me') and (not a.get('pos') or a.get('auto')): a['pos'], a['auto'] = role, True
        pool = core.ban_pool(p, role)
        cnt = {m: core.lola_counters(self.lola_fetch('counter', m, role), d) for m in pool}
        bans = core.ban_suggest(p, cs['unavailable'], 3, role, {m: v for m, v in cnt.items() if v})
        try: self.dash.show_draft(cs, r, bans)
        except Exception as e: log_error('второе окно: драфт', e)
        self.phone_draft(cs, r, bans)
        auto = tuple(k for k, v in self.s['auto_parts'].items() if v)
        if self.s['auto_import'] and auto and cs['locked'] and cs['me'] and self.imported != cs['me']: self.do_import(auto)

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
        """Подтверждённые средние ранга выше; длительность матча не угадывается."""
        slug, name = self.next_tier()
        if not slug or role not in core.ROLES: return None
        b = self.lola_fetch('tier_' + slug, champ, role)
        if not b: return None
        return {'tier':name,**performance_model.benchmark(b)}

    def role_pil(self, role, k=.5):
        """Значок роли в золоте для карточек виджетов (PIL)."""
        if Image is None or not role: return None
        im = self.icons._pil('role', role)
        return render.tint(im, C['gold'], max(10, int(self.s['icon'] * k * self.s['scale'] / 100))) if im else None

    def ensure_skill_icons(self, champion):
        """Load the selected champion's official Data Dragon spell images off the Tk thread."""
        import re
        keys = [champion+letter for letter in 'QWER']
        if all(key in self.icons.a.get('skill', {}) for key in keys): return
        version = str(self.icons.a.get('v') or '')
        if not re.fullmatch(r'\d+\.\d+\.\d+', version) or not re.fullmatch(r'[A-Za-z0-9]+', champion): return
        if not hasattr(self, '_skill_loading'): self._skill_loading = set()
        if champion in self._skill_loading: return
        self._skill_loading.add(champion)
        path = os.path.join(self.home, 'skills', version, champion+'.json')
        def job():
            images = {}
            try:
                try:
                    with open(path, encoding='utf-8') as source: images = json.load(source)
                except (OSError, ValueError): pass
                if not all(images.get(key) for key in keys):
                    base = 'https://ddragon.leagueoflegends.com/cdn/'+version
                    with urllib.request.urlopen(base+'/data/en_US/champion/'+champion+'.json', timeout=15) as response:
                        spells = json.load(response)['data'][champion]['spells']
                    if len(spells) != 4: raise ValueError('Нет четырёх умений чемпиона')
                    for key, spell in zip(keys, spells):
                        filename = spell['image']['full']
                        if not re.fullmatch(r'[A-Za-z0-9_.-]+', filename): raise ValueError('Некорректное имя изображения')
                        with urllib.request.urlopen(base+'/img/spell/'+filename, timeout=15) as response:
                            images[key] = base64.b64encode(response.read()).decode('ascii')
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    with open(path+'.tmp', 'w', encoding='utf-8') as output: json.dump(images, output)
                    os.replace(path+'.tmp', path)
            except Exception as error: log_error('иконки умений '+champion, error)
            def done():
                if not images: return
                self.icons.a.setdefault('skill', {}).update(images)
                for key in list(self.icons.raw):
                    if key[0] == 'skill' and key[1] in images: self.icons.raw.pop(key, None)
                self.redraw_draft()
            try: self.root.after(0, done)
            except (RuntimeError, tk.TclError): pass
        threading.Thread(target=job, daemon=True, name='skill-images').start()

    def draft_opponent(self, cs, role):
        roles = core.guess_enemy_roles(self.data, cs.get('enemies') or [])
        return next((champ for champ, lane in roles.items() if lane == role), None)

    def selected_draft_build(self, cs=None):
        cs = cs or self.draft
        if not cs or not cs.get('me'): return None
        role = self.draft_role(cs)[0]
        context=self.s.get('draft_build_context','general') if role in core.ROLES else 'general'
        if context=='matchup':return self.lola_matchup(cs['me'],role,self.draft_opponent(cs,role))
        if context=='offmeta' or context.startswith('player:'):
            from draft_external import selected
            return selected(context,cs['me'],role,self.offmeta_build(cs['me'],role) if context=='offmeta' else None,
                            self.player_builds(cs['me'],role) if context.startswith('player:') else None)
        return self.lola_build(cs['me'],role)

    def set_draft_build(self, context, variant):
        if context not in ('general','matchup','offmeta') and not (context.startswith('player:') and context[7:].isdigit()):return
        if variant not in ('pick','win') or (context not in ('general','matchup') and variant!='pick'):return
        self.s['draft_build_context'] = context
        self.s['rune_pick']=variant
        if self.draft and self.draft.get('me'):
            role=self.draft_role(self.draft)[0]
            self._chosen_draft_build=(self.draft['me'],role,context,self.selected_draft_build(self.draft))
        self.set_rune_pick(variant)

    def lola_matchup(self, champion, role, opponent):
        """Public matchup page only. Cache includes both champions and the verified source context."""
        if not champion or not opponent or role not in core.ROLES: return None
        key = ('matchup', champion, role, opponent)
        if key in self.lola: return self.lola[key]
        if self.lola_state.get(key): return None
        self.lola_state[key] = 'loading'
        path = os.path.join(self.home, 'lola', f'matchup_v1_{champion}_{role}_{opponent}.json')
        def valid(value):
            meta = (value or {}).get('matchup') or {}
            return (meta.get('champion'), meta.get('role'), meta.get('opponent'), meta.get('region')) == (champion, role, opponent, 'all')
        def job():
            import matchup_data
            value, saved = None, None
            try:
                try:
                    with open(path, encoding='utf-8') as source: saved = json.load(source)
                    if not valid(saved): saved = None
                except (OSError, ValueError): pass
                if saved and time.time()-saved.get('fetched_at',0) < 12*3600:
                    value = saved
                else:
                    req = urllib.request.Request(matchup_data.url(champion, role, opponent), headers={'User-Agent':'Mozilla/5.0'})
                    with urllib.request.urlopen(req, timeout=20) as response: html = response.read().decode('utf-8')
                    value = matchup_data.parse(html, champion, role, opponent, self.data)
                    if value:
                        value['fetched_at'] = time.time()
                        os.makedirs(os.path.dirname(path), exist_ok=True)
                        with open(path+'.tmp', 'w', encoding='utf-8') as output: json.dump(value, output)
                        os.replace(path+'.tmp', path)
                    else: raise ValueError('Источник не подтвердил состав, роль или выборку матчапа')
            except Exception as error:
                log_error(f'сборка {champion} против {opponent}, {role}', error)
                if saved:
                    value = dict(saved, stale=True)
            def done():
                if value: self.lola[key] = value
                self.lola_state[key] = 'ok' if value else 'fail'
                self.redraw_draft()
                if getattr(self,'cp_sel',None)==(champion,role): self.cp_show()
            try: self.root.after(0, done)
            except (RuntimeError, tk.TclError): pass
        threading.Thread(target=job, daemon=True, name='matchup-build').start()
        return None

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

    def set_draft_scope(self, scope):
        self.s['draft_scope'] = scope
        self.s.save()
        self.draft_sig = None
        if self.dash: self.dash.draft_sig = None
        if self.draft: self.on_draft(self.draft)

    def set_import_part(self, key):
        self.s['auto_parts'][key] = self.auto_vars[key].get()
        self.s.save()
        self.imported = None
        self.draft_sig = None
        if self.dash: self.dash.draft_sig = None
        if self.draft: self.on_draft(self.draft)

    def set_draft_role(self, role):
        self.role_override = role
        self.imported = None
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
        L += [w.auto_status for w in self.tab.values()]
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
        """Snapshot the chosen variant in Tk, serialize client mutations in a worker."""
        cs, player = self.draft, self.player
        if not cs or not cs.get('me') or not player:
            self.set_import_msg('Сначала выбери чемпиона в драфте'); return
        parts = tuple(k for k in parts if k in ('runes', 'items', 'spells'))
        if not parts:
            self.set_import_msg('Выбери, что экспортировать: руны, предметы или заклинания'); return
        me, role = cs['me'], self.draft_role(cs)[0]
        context = self.s.get('draft_build_context', 'general') if role in core.ROLES else 'general'
        opponent = self.draft_opponent(cs, role) if context == 'matchup' else None
        full = self.selected_draft_build(cs)
        if context!='general' and not full:
            self.set_import_msg('Выбранная сборка ещё не подтверждена или не загружена. Экспорт не выполнен.');return
        if context == 'matchup' and not full.get(self.s['rune_pick']):
            self.set_import_msg('Выбранный вариант матчапа недоступен. Экспорт не выполнен.'); return
        variant = (full.get(self.s['rune_pick']) or full) if full else None
        signature = (me, role, self.s['rune_pick'], parts, context, opponent)
        if getattr(self, '_import_pending', None) == signature: return
        self._import_pending = signature
        self._import_generation = getattr(self, '_import_generation', 0) + 1
        generation = self._import_generation
        if not hasattr(self, '_import_lock'): self._import_lock = threading.Lock()
        name, client = self.data.cn(me) + (' против ' + self.data.cn(opponent) if opponent else ''), self.client
        account = dict(self.account or {})
        cid = next((key for key, value in self.data.ids.items() if value == me), None)
        chosen = self.s['rune_pick']
        # Copy data before starting a worker; no Tk/settings calls in the worker.
        variant = json.loads(json.dumps(variant)) if variant else None
        personal_runes = player.best_runes(me) if not variant else None
        if full and full.get('external'):
            sets=core.lola_item_sets(dict(variant,situ=full.get('situ',[])),name)[:1]
            sets=[(name+': '+full['external']+' · '+full.get('external_name','выбранный вариант'),sets[0][1])]
        elif full:sets=core.lola_item_sets(full,name)
        else:sets=[(name,[('Сборка из твоих побед',player.best_build(me)),('Тотемы',[2055,3340,3364])])]
        if full and chosen == 'win': sets.reverse()
        sets = json.loads(json.dumps(sets))
        log_path = os.path.join(self.home, 'import.log') if getattr(self, 'home', None) else None
        source = ((('Против ' + self.data.cn(opponent) + ', все регионы') if opponent else 'Европа') + ', ' + ('лучший винрейт' if chosen == 'win' else 'популярная')) if full else 'из твоих игр'
        if full and full.get('external'):source=full['external']+' · патч '+str(full.get('patch') or '—')
        self.set_import_msg('Экспортирую выбранные данные…')

        def current():
            draft = self.draft or {}
            return (self._import_generation == generation and draft.get('me') == me
                    and self.draft_role(draft)[0] == role and self.s['rune_pick'] == chosen
                    and (self.s.get('draft_build_context', 'general') if role in core.ROLES else 'general') == context
                    and (context != 'matchup' or self.draft_opponent(draft, role) == opponent)
                    and not self.last_game)

        def job():
            results = []
            with self._import_lock:
                for part in parts:
                    if not current(): break
                    client.last_error = ''
                    try:
                        if part == 'runes':
                            runes = variant or personal_runes
                            ok = bool(runes) and client.set_runes(name, runes['prim'], runes['sec'], runes['perks'],
                                        runes.get('shards') if len(runes.get('shards') or []) == 3 else None)
                        elif part == 'items':
                            acc = account or client.me() or {}
                            ok = bool(cid and sets and sets[0][1] and sets[0][1][0][1]) and client.set_items(acc.get('id'), cid, sets, None)
                        else:
                            spells = (variant or {}).get('spells') or []
                            ids = [core.SPELL_ID.get(spell) for spell in spells[:2]]
                            ok = len(ids) == 2 and None not in ids and client.set_spells(*ids)
                        error = client.last_error or ('нет подходящих данных' if not ok else '')
                    except Exception as exc:
                        ok, error = False, str(exc)
                    title = {'runes': 'Руны', 'items': 'Предметы', 'spells': 'Заклинания'}[part]
                    results.append((ok, title + (': готово' if ok else ': не получилось (' + error + ')')))
                    if not ok: log_error('импорт ' + title, error)
            def done():
                if self._import_generation != generation: return
                self._import_pending = None
                if not current():
                    self.set_import_msg('Экспорт остановлен: выбор изменился или драфт завершён'); return
                success = len(results) == len(parts) and all(ok for ok, _ in results)
                self.imported = me if success else None
                message = source + ' · ' + ' · '.join(text for _, text in results)
                self.set_import_msg(message)
                if log_path:
                    try:
                        with open(log_path, 'a', encoding='utf-8') as output:
                            output.write(time.strftime('%Y-%m-%d %H:%M:%S ') + me + ' ' + message + '\n')
                    except OSError: pass
            try: self.root.after(0, done)
            except (RuntimeError, tk.TclError): pass
        threading.Thread(target=job, daemon=True, name='draft-import').start()

    # --- клавиши и Tab
    def keys(self):
        try:
            self._poll_keys()
        except Exception as error:
            self._recover_overlays(error)
        finally:
            try:self.root.after(40, self.keys)
            except (tk.TclError,RuntimeError):pass

    def _recover_overlays(self,error):
        log_error('клавиши и виджеты',error)
        self.demo_on=False
        self._demo_epoch=getattr(self,'_demo_epoch',0)+1
        self.keys_prev.update(tab=False,drag=False)
        for window in list(self.tab.values())+list(self.ov.values()):
            try:
                window.withdraw()
                window.unlocked=False
                click_through(window,True)
            except Exception:pass
        try:self.demo_btn.configure(text='Показать все виджеты для расстановки')
        except (AttributeError,tk.TclError):pass

    def _poll_keys(self):
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
        drag = bool(combo_down(k.get('drag')) and self.last_game and not self.hidden and game_focused()) or self.demo_on   # Alt двигает виджеты только в игре
        tab_down = combo_down(k.get('scoreboard'))
        focused = game_focused()
        tab = bool(self.s['scoreboard'] and self.last_game and self.last_game.me and not self.last_game.arena and not self.hidden and tab_down and focused)
        if not tab and not self.demo_on:
            for w in self.tab.values():
                if w.winfo_viewable():w.withdraw()
        for w in self.tab.values():
            if tab_down and self.s.get('tab_auto'):
                reason = ('включите оверлей таблицы Tab' if not self.s['scoreboard'] else
                          'ожидаю игровые данные от клиента LoL' if not self.last_game else
                          'таблица Арены пока не поддерживается' if self.last_game.arena else
                          'показ оверлеев скрыт горячей клавишей' if self.hidden else
                          'завершите расстановку виджетов' if self.demo_on else
                          'отпустите Alt для автоматического поиска' if drag else
                          'переключитесь в окно игры' if not focused else None)
                if reason: w._detection_status('Автоподгонка: ' + reason)
            w.auto_tick(bool(tab and not drag), self.last_game)
        if drag != self.keys_prev.get('drag'):
            self.set_unlocked(drag)
            self.keys_prev['drag'] = drag
        if self.demo_on:
            for w in self.tab.values():
                if not self.s['scoreboard']:w.withdraw()
                elif w.winfo_viewable():w.refresh_geometry()
            self.keys_prev['tab']=False
            return
        if tab:
            for w in self.tab.values():
                if w.unlocked!=drag:w.unlock(drag)
                w.refresh_geometry()
            if not self.keys_prev.get('tab') or time.time() - self.keys_prev.get('tab_t', 0) > 1:
                for w in self.tab.values():
                    try: w.show(self.last_game); w.deiconify()
                    except Exception as e: log_error('Tab', e)
                self.keys_prev['tab_t'] = time.time()
        else:
            for w in self.tab.values():
                if w.winfo_viewable():w.withdraw()
        self.keys_prev['tab'] = bool(tab)

    def set_unlocked(self, on, keys=None):
        """Расстановка виджетов; у Tab мышь принимает только отдельная ручка."""
        if on and self.hidden and not self.demo_on: return
        if not on:
            for w in self.tab.values():w.withdraw()
        wins=dict(self.tab,**self.ov)
        for key,w in wins.items():
            if keys is not None and key not in keys:continue
            enabled=self.s['scoreboard'] if key in self.tab else self.s['widgets'].get(key)
            if not enabled:
                w.withdraw();w.unlock(False);continue
            if on and key in self.tab and not self.demo_on and not combo_down(self.s['keys'].get('scoreboard')):
                w.withdraw();w.unlock(False);continue
            w.unlock(on)
            if not on:continue
            if self.last_game and self.last_game.me and key!='hints':w.show(self.last_game)
            else:w.demo()
            w.deiconify();w.lift()
        if not on:
            self.apply_visibility();self.ov['hints'].show()

    def toggle_demo(self):
        self.demo_on=not self.demo_on
        self._demo_epoch=getattr(self,'_demo_epoch',0)+1
        epoch=self._demo_epoch
        self.demo_btn.configure(text='Завершить расстановку (Esc)' if self.demo_on else 'Показать все виджеты для расстановки')
        self.keys_prev['drag']=self.demo_on
        if not self.demo_on:
            self.set_unlocked(False)
            return
        pending=iter(list(self.tab)+list(self.ov))
        def show_next():
            if not self.demo_on or epoch!=self._demo_epoch:return
            key=next(pending,None)
            if key is None:return
            try:self.set_unlocked(True,keys=(key,))
            except Exception as error:self._recover_overlays(error);return
            self.root.after(16,show_next)
        self.root.after(0,show_next)

    def stop_demo(self,event=None):
        if self.demo_on:
            self.toggle_demo()
            return 'break'

    def tick_ui(self):
        self.ov['hints'].show()
        self.root.after(1000, self.tick_ui)

    # ---------------- Панель управления ----------------
    NAV = [('Главная', 'home'), ('История матчей', 'list'), ('Чемпион', 'search'), ('Подсказки', 'bulb'), ('Виджеты и окна', 'window'), ('Вид', 'look'),
           ('Звук', 'sound'), ('Клавиши', 'keys'), ('Таймеры', 'clock'), ('Обновления', 'update'), ('Мой пул', 'pool')]
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
        self.tab_pool = self.page('Мой пул', scroll=False)
        for i in (0, 1, 10, 2, 3, 4, 5, 6, 7, 8):
            name, ic = self.NAV[i]
            if i in self.NAV_GROUPS:
                tk.Label(rail, text=self.NAV_GROUPS[i].upper(), bg=C['deep'], fg=C['mute'], font=(F['num'], self.fs(9)), anchor='w').pack(fill='x', padx=8, pady=(10 if i else 0, 2))
            self.nav_item(rail, i, name, ic)
        tk.Frame(rail, bg=C['deep']).pack(fill='both', expand=True)
        low = tk.Frame(rail, bg=C['deep']); low.pack(fill='x', side='bottom')
        tk.Label(low, text=self.version, bg=C['deep'], fg=C['mute'], font=(F['num'], self.fs(9))).pack(side='right', padx=(0, 6))
        self.nav_item(low, 9, self.NAV[9][0], self.NAV[9][1])
        self.nb.bind('<<NotebookTabChanged>>', lambda e: self.nav_sync())
        self.build_status(); self.build_history(); self.build_champ(); self.build_hints(); self.build_windows(); self.build_look()
        self.build_voice(); self.build_keys(); self.build_timers(); self.build_updates()
        from pool_ui import PoolScreen
        self.pool_view = PoolScreen(self.tab_pool, self)
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
        self.nav_items.append((i, lb, icons))

    def nav_sync(self):
        try: cur = self.nb.index('current')
        except Exception: return
        for i, lb, icons in self.nav_items:
            on = i == cur
            lb.configure(bg=C['raise'] if on else C['deep'], fg=C['gold'] if on else C['fg'])
        self.page_title.configure(text=self.NAV[cur][0].upper())

    def page(self, name, scroll=True):
        """Вкладка панели; с прокруткой колесом мыши, если содержимое не помещается."""
        outer = tk.Frame(self.nb, bg=C['bg'], padx=14, pady=6); self.nb.add(outer, text=name)
        if not scroll: outer.outer = outer; return outer
        cv = ScrollCanvas(outer, bg=C['bg'], highlightthickness=0); sb = ttk.Scrollbar(outer, orient='vertical', command=cv.yview)
        inner = tk.Frame(cv, bg=C['bg'])
        sb.pack(side='right', fill='y')
        inner.bind('<Configure>', lambda e: cv.configure(scrollregion=cv.bbox('all')))
        win = cv.create_window((0, 0), window=inner, anchor='nw'); cv.configure(yscrollcommand=sb.set)
        cv.bind('<Configure>', lambda e: cv.itemconfigure(win, width=e.width), add='+')
        cv.pack(side='left', fill='both', expand=True)
        self.__dict__.setdefault('canvases', {})[str(outer)] = cv
        if not getattr(self, '_wheel', False):
            self._wheel = True
            def wheel(e):
                try: top = e.widget.winfo_toplevel()
                except Exception: top = None
                if self.dash and top is self.dash: c = self.dash.cv   # колесо над вторым окном — крутим его
                else: c = self.canvases.get(self.nb.select())
                if c and c.winfo_exists() and top is c.winfo_toplevel() and c.bbox('all') and c.bbox('all')[3] > c.winfo_height(): return c.wheel(e)
            self.root.bind_all('<MouseWheel>', wheel)
            self.root.bind_all('<Button-4>', wheel)
            self.root.bind_all('<Button-5>', wheel)
        inner.outer = outer
        return inner

    def h(self, parent, text): ttk.Label(parent, text=text, style='H.TLabel').pack(anchor='w', pady=(20, 9))

    def note(self, parent, text):
        label=ttk.Label(parent,text=text,style='M.TLabel',wraplength=self.fs(660),justify='left')
        label.pack(anchor='w',pady=(0,6))
        parent.bind('<Configure>',lambda e:label.configure(wraplength=max(self.fs(220),e.width-self.fs(24))) if label.winfo_exists() else None,add='+')

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
        from history_ui import HistoryScreen
        self.hist_data = []
        self.history_view = HistoryScreen(self.tab_hist,self)
        self.root.after(4000,self.hist_refresh)

    # --- страница чемпиона вне драфта (как у U.GG и Mobalytics): сборка, умения, матчапы и твоя статистика
    def build_champ(self):
        from champion_ui import ChampionScreen
        self.cp_sel = None
        self.champion_view = ChampionScreen(self.tab_champ,self)
        self.cp_var = self.champion_view.query

    def cp_pick(self, champ, role=None):
        self.champion_view.choose(champ,role)

    def cp_show(self):
        view=getattr(self,'champion_view',None)
        if view and view.winfo_exists():view.refresh()

    def external_build_ready(self,champion,role):
        if self.cp_sel==(champion,role):self.cp_show()
        if self.draft and self.draft.get('me')==champion and self.draft_role(self.draft)[0]==role:
            self.draft_sig=None
            self._chosen_draft_build=(champion,role,self.s.get('draft_build_context','general'),self.selected_draft_build(self.draft))
            if self.dash:self.dash.draft_sig=None
            self.on_draft(self.draft)

    def offmeta_build(self,champion,role):
        from offmeta_source import OffmetaSource
        if not hasattr(self,'_offmeta_source'):
            self._offmeta_source=OffmetaSource(self.home,self.root.after,
                self.external_build_ready)
        return self._offmeta_source.get(champion,role)

    def player_builds(self,champion,role):
        from player_build_source import PlayerBuildSource
        if not hasattr(self,'_player_build_source'):
            self._player_build_source=PlayerBuildSource(self.home,self.root.after,
                self.external_build_ready)
        return self._player_build_source.get(champion,role)

    def lp_snaps(self, rank=None, puuid=None):
        """Снимки звания [время мс, ladder] в %APPDATA%/LoLHelper/lp.json; с rank — дописать новый, если LP изменились."""
        import hashlib
        name = 'lp-'+hashlib.sha256(puuid.encode()).hexdigest()[:16]+'.json' if puuid else 'lp.json'
        path = os.path.join(self.home,name)
        try:
            with open(path,encoding='utf-8') as source: snaps=json.load(source)
        except (OSError,ValueError): snaps=[]
        v = core.ladder(rank)
        if v is not None and (not snaps or snaps[-1][1] != v or time.time() * 1000 - snaps[-1][0] > 6 * 3600 * 1000):
            snaps.append([int(time.time() * 1000), v]); snaps = snaps[-400:]
            try:
                with open(path+'.tmp','w',encoding='utf-8') as output: json.dump(snaps,output)
                os.replace(path+'.tmp',path)
            except OSError: pass
        return snaps

    def hist_refresh(self):
        view=getattr(self,'history_view',None)
        if view and view.winfo_exists(): view.load_client(background=True)

    def hist_show(self,hist,lp,puuid):
        self.history_view.set_client(hist,lp,puuid,(self.account or {}).get('riot','') if puuid and puuid==(self.account or {}).get('puuid') else '')

    def hist_open(self,h,lp,puuid):
        from history_ui import MatchWindow
        import history_model
        row=history_model.client([h],self.data,puuid,{h.get('gid'):lp})[0]
        window=MatchWindow(self,row)
        if row.get('gid'):window.load()
        return window

    def hist_window(self,h,lp,res):
        """Совместимый вход для существующих симуляций готового разбора."""
        from history_ui import MatchWindow
        import history_model
        row=history_model.client([h],self.data,None,{h.get('gid'):lp})[0]
        window=MatchWindow(self,row,res)
        if res is None:
            window.loading=False;window.error='Клиент не отдал подробности этой игры';window.render()
        return window

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
        from home_ui import HomeScreen
        self.home_view = HomeScreen(self.tab_status, self)

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
        view = getattr(self, 'home_view', None)
        if view and view.winfo_exists(): view.refresh()

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

    def ensure_home_icon(self, icon):
        """Официальная иконка профиля загружается вне Tk, без подмены на другом профиле."""
        key = str(icon)
        if key in self.icons.a.get('profile',{}) or Image is None: return
        pending = self.__dict__.setdefault('_home_icons',set())
        failed = self.__dict__.setdefault('_home_icon_failures',{})
        if key in pending or not key.isdigit() or time.time()-failed.get(key,0)<300: return
        pending.add(key)
        def job():
            try:
                value = self.client.image(f'/lol-game-data/assets/v1/profile-icons/{key}.jpg')
                if not value:
                    import re
                    patch = self.data.d.get('patch','')
                    if re.fullmatch(r'\d+\.\d+\.\d+',patch):
                        with urllib.request.urlopen(f'https://ddragon.leagueoflegends.com/cdn/{patch}/img/profileicon/{key}.png',timeout=8) as response:
                            value = response.read(1_000_001)
                if not isinstance(value,bytes) or len(value)>1_000_000: raise ValueError('Нет иконки профиля')
                with Image.open(io.BytesIO(value)) as image: image.verify()
                def done():
                    self.icons.a.setdefault('profile',{})[key] = base64.b64encode(value).decode()
                    self.icons.raw.pop(('profile',key),None)
                    pending.discard(key)
                    self.home_fill()
                self.root.after(0,done)
            except Exception:
                failed[key] = time.time()
                pending.discard(key)
        threading.Thread(target=job,daemon=True).start()

    def panel_sync(self):
        try:
            self.status_dot.configure(fg=C['good'] if self.account else C['mute'])
            if self.account and self.status.cget('text').startswith(('Ищу клиент','Клиент League of Legends недоступен')):
                self.status.configure(text='Клиент League of Legends подключён')
            elif not self.account and self.status.cget('text').startswith('Клиент League of Legends подключён'):
                self.status.configure(text='Клиент League of Legends недоступен')
        except Exception: pass
        self.home_fill()

    def open_dash(self):
        if not self.dash:
            self.s['dashboard'] = True; self.s.save(); self.dash = Dashboard(self)
        else:
            self.dash._manual_hidden=False;self.dash.deiconify();self.dash.lift()

    def build_hints(self):
        from hints_ui import HintsScreen
        self.hints_view = HintsScreen(self.tab_hints,self)

    def apply_text(self, h):
        """Свой текст подсказки: {текст} заменяется исходным."""
        o = self.s['hint_text'].get(h.id)
        if not o: return
        orig_t, orig_s = h.text, h.say or h.text
        if o.get('text'): h.text = o['text'].replace('{текст}', orig_t)
        if o.get('say'): h.say = o['say'].replace('{текст}', orig_s)
        elif o.get('text'): h.say = o['text'].replace('{текст}', orig_s)

    def edit_hint(self, hid, name):
        from hints_ui import HintEditor
        self.hint_editor = HintEditor(self.hints_view,hid,name)

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
        self.hints_view.choose_role(role)

    def set_all_hints(self, m):
        self.hints_view.set_all(m)

    def build_windows(self):
        from windows_ui import WindowsScreen
        self.windows_view = WindowsScreen(self.tab_win,self)

    def build_windows_options(self,parent):
        f = parent
        pg = tk.BooleanVar(value=self.s['postgame'])
        ttk.Checkbutton(f,text='Окно итога после игры',variable=pg,command=lambda:(self.s.__setitem__('postgame',pg.get()),self.s.save())).pack(anchor='w')
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
        av = tk.BooleanVar(value=self.s['tab_auto'])
        ttk.Checkbutton(f, text='Автоматически находить таблицу Tab по портретам (экспериментально)', variable=av,
                        command=lambda: self.set_tab('tab_auto', av.get())).pack(anchor='w')
        self.tab_auto_label = ttk.Label(f, text='Автоподгонка: ожидаю Tab в игре' if self.s['tab_auto'] else 'Автоподгонка выключена', style='V.TLabel')
        self.tab_auto_label.pack(anchor='w', pady=(2, 4))
        self.note(f, 'Между игроками в каждой строке Tab — одно число разницы стоимости предметов. Стрелка указывает на игрока с перевесом. '
                     'Синие цифры — преимущество нашей команды в этой паре, красные — отставание. Серый 0 означает равенство, прочерк — нет данных для сравнения. '
                     'Над таблицей — общая стоимость предметов команд, красно-синяя полоса баланса и число перевеса. '
                     'Считаются все предметы, кроме зелий, вардов и тотемов. Всё привязано к окну игры и масштабируется по его высоте, в том числе на широких мониторах. '
                     'Автоподгонка анализирует изображение игры только при удержании Tab; снимки никуда не отправляются и не сохраняются. '
                     'Работает и в тренировке: ищет рамку таблицы и проверяет её по видимым портретам. Неуверенно распознанные строки не подписываются. '
                     'Если не совпало: выключи автоподгонку и зажми Tab и Alt. Тяни небольшую золотую ручку TAB для переноса; Shift + перетаскивание ручки меняет ширину и высоту. '
                     'Остальная область пропускает клики в игру даже при Alt. Ручка скрывается при отпускании Alt. ')
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
        for w in self.tab.values():
            w.auto_layout = None
            w._auto_cancel.set()
            w._auto_epoch += 1
            if self.last_game: w.show(self.last_game)
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
        pos = {'hints': (L, gy + .30 * gh), 'perf': (R, gy + .10 * gh), 'lane': (R, gy + .30 * gh),
               'item': (R, gy + .40 * gh), 'timers': (R, gy + .49 * gh), 'inventory': (max(gx, R - 310 * k), gy + .10 * gh)}
        lay = self.layout()
        for key, (x, y) in pos.items(): lay[key] = [int(x), int(y)]
        self.s.save(); self.rebuild()
        self.status.configure(text='Раскладка применена: проверь кнопкой «Показать все виджеты»')

    def reset_layout(self):
        self.s['layout'].pop(screens()[0], None); self.s.save(); self.rebuild()

    def slider(self, parent, name, key, lo, hi, on_change, fmt=lambda x: f'{x:.0f}%', live=True, test=None):
        """Ползунок с подписью значения. live=False — применяется, когда отпустишь мышь."""
        row = tk.Frame(parent, bg=C['bg']); row.pack(fill='x', pady=6)
        ttk.Label(row, text=name, width=22,wraplength=self.fs(185)).pack(side='left')
        v = tk.DoubleVar(value=self.s[key])
        val = ttk.Label(row, width=7, style='V.TLabel', text=fmt(self.s[key]))
        sc = ttk.Scale(row, from_=lo, to=hi, variable=v, length=self.fs(300))
        val.pack(side='right', padx=8)
        if test: ttk.Button(row, text='Проверить', command=test).pack(side='right',padx=6)
        sc.pack(side='left',fill='x',expand=True)
        if live: sc.configure(command=lambda _: (val.configure(text=fmt(v.get())), on_change(v.get())))
        else:
            sc.configure(command=lambda _: val.configure(text=fmt(v.get())))
            sc.bind('<ButtonRelease-1>', lambda e: on_change(v.get()))
            sc.bind('<KeyRelease>', lambda e: on_change(v.get()))
        return v

    def build_look(self):
        f = self.tab_look
        self.h(f, 'Тема')
        row = tk.Frame(f, bg=C['bg']); row.pack(anchor='w')
        for i, (k, (name, pal)) in enumerate(THEMES.items()):   # столбец — палитра, строки — ночь и день
            b = tk.Label(row, text=name, bg=pal['panel'], fg=pal['gold'], font=(F['numb'], self.fs(11)), padx=10, pady=10, width=18,
                         highlightthickness=2, highlightbackground=C['gold'] if self.s['theme'] == k else pal['bg'], cursor='hand2')
            b.grid(row=i//2, column=i%2, padx=(0, 8), pady=(0, 8), sticky='w')
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
        self.note(f,'Проверка использует режим «Ганк 1» для выбранной роли на вкладке «Подсказки».')
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
            ttk.Label(r, text=name, width=34,wraplength=self.fs(310)).pack(side='left')
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
            value='+'.join(combo)
            if any(other!=key and value==saved for other,saved in self.s['keys'].items()):
                self.status.configure(text='Это сочетание уже назначено другому действию. Выбери другое или нажми Esc.')
                return
            self.s['keys'][key] = value; self.s.save()
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
        from settings_validation import clock_seconds
        try:sec=clock_seconds(v.get(),positive=k.endswith('respawn'))
        except ValueError:
            v.set(core.mmss(self.s['obj'].get(k,core.OBJ[k])))
            self.status.configure(text='Нужно время ММ:СС: секунды 00–59, без отрицательных значений')
            return
        self.s['obj'][k] = core.OBJ[k] = sec; self.s.save()
        v.set(core.mmss(sec));self.status.configure(text='Время объекта сохранено')

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
        if getattr(self,'pool_view',None) and self.pool_view.winfo_exists():
            self.pool_view.rows, self.pool_view.source = champion_pool.load_catalog(data)
        self.set_who(self.who)
        self.panel_sync()

    def run(self):
        self.root.mainloop()
