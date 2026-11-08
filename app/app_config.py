"""Общие настройки и платформенные функции; Qt не импортирует Tkinter."""
import os,sys,json,time,traceback,copy
import core,player_comments
IS_WIN=os.name=="nt"
if IS_WIN:
    import ctypes,ctypes.wintypes
    U32=ctypes.windll.user32
RELEASES = 'https://github.com/Halches/Lol-stat/releases'   # список всех версий с изменениями

THEMES = {   # три палитры дизайна 26.10, у каждой ночь и день; ключи старых тем ведут на новые (Settings)
    'lol': ('Клиент LoL · ночь', {'bg': '#06101c', 'panel': '#0b1a2a', 'line': '#1f3347', 'fg': '#e8dfcc', 'mute': '#8c9bab', 'gold': '#c8aa6e', 'good': '#0ac8b9', 'bad': '#e2584e', 'blue': '#4fb3ff', 'red': '#e2584e', 'deep': '#081422', 'raise': '#14283c', 'edge': '#0b1a2a', 'glow': '#0f2236', 'tag_g': '#0b3641', 'tag_r': '#2d2430', 'tag_y': '#2e302d', 'good2': '#3bd3c7', 'bad2': '#e87971', 'warn': '#e8a33d', 'red2': '#e87971', 'blue2': '#72c2ff', 'on_gold': '#06101c', 'dark': True}),
    'lol_day': ('Клиент LoL · день', {'bg': '#eef1f5', 'panel': '#ffffff', 'line': '#d3dae3', 'fg': '#0d1b2a', 'mute': '#56657a', 'gold': '#8a6a2b', 'good': '#0b8f88', 'bad': '#b8433b', 'blue': '#2f7fd0', 'red': '#b8433b', 'deep': '#f6f7fa', 'raise': '#e3e9f0', 'edge': '#ffffff', 'glow': '#ffffff', 'tag_g': '#d8edec', 'tag_r': '#f4e1e0', 'tag_y': '#f4e8d9', 'good2': '#0b8f88', 'bad2': '#b8433b', 'warn': '#b86e12', 'red2': '#b8433b', 'blue2': '#2f7fd0', 'on_gold': '#eef1f5', 'dark': False}),
    'pilt': ('Пилтовер · ночь', {'bg': '#0d0b1c', 'panel': '#151230', 'line': '#2c2856', 'fg': '#ece7f6', 'mute': '#9b94b8', 'gold': '#e2c27a', 'good': '#4fb3ff', 'bad': '#ff5d73', 'blue': '#4fb3ff', 'red': '#ff5d73', 'deep': '#110e25', 'raise': '#211d45', 'edge': '#151230', 'glow': '#1d1a3d', 'tag_g': '#1e2c51', 'tag_r': '#3a1e3b', 'tag_y': '#382d34', 'good2': '#72c2ff', 'bad2': '#ff7d8f', 'warn': '#f2b84b', 'red2': '#ff7d8f', 'blue2': '#72c2ff', 'on_gold': '#0d0b1c', 'dark': True}),
    'pilt_day': ('Пилтовер · день', {'bg': '#f2f0f8', 'panel': '#ffffff', 'line': '#d4cfe6', 'fg': '#16122e', 'mute': '#5f5880', 'gold': '#86662a', 'good': '#1f6fc0', 'bad': '#c2364c', 'blue': '#1f6fc0', 'red': '#c2364c', 'deep': '#f8f7fb', 'raise': '#e7e3f3', 'edge': '#ffffff', 'glow': '#ffffff', 'tag_g': '#dbe8f5', 'tag_r': '#f5dfe2', 'tag_y': '#f4e8d9', 'good2': '#1f6fc0', 'bad2': '#c2364c', 'warn': '#b86e12', 'red2': '#c2364c', 'blue2': '#1f6fc0', 'on_gold': '#f2f0f8', 'dark': False}),
    'dgold': ('Тёмное золото · ночь', {'bg': '#0e0e0f', 'panel': '#171717', 'line': '#2e2b27', 'fg': '#f0e9db', 'mute': '#9d978b', 'gold': '#d6ab52', 'good': '#4cc38a', 'bad': '#e5604f', 'blue': '#5aa9e6', 'red': '#e5604f', 'deep': '#121213', 'raise': '#211f1c', 'edge': '#171717', 'glow': '#1d1b18', 'tag_g': '#1f3329', 'tag_r': '#382320', 'tag_y': '#382d1d', 'good2': '#70cfa1', 'bad2': '#ea8072', 'warn': '#e8a33d', 'red2': '#ea8072', 'blue2': '#7bbaeb', 'on_gold': '#0e0e0f', 'dark': True}),
    'dgold_day': ('Тёмное золото · день', {'bg': '#f4f2ee', 'panel': '#ffffff', 'line': '#dcd6cb', 'fg': '#1c1a17', 'mute': '#6b665c', 'gold': '#8a6420', 'good': '#1f8a5b', 'bad': '#b9442f', 'blue': '#2f7fd0', 'red': '#b9442f', 'deep': '#f9f8f6', 'raise': '#ebe7df', 'edge': '#ffffff', 'glow': '#ffffff', 'tag_g': '#dbece5', 'tag_r': '#f4e1de', 'tag_y': '#f4e8d9', 'good2': '#1f8a5b', 'bad2': '#b9442f', 'warn': '#b86e12', 'red2': '#b9442f', 'blue2': '#2f7fd0', 'on_gold': '#f4f2ee', 'dark': False}),
}

THEMES['lol']=('Цветение · ночь',dict(THEMES['lol'][1],bg='#180f22',panel='#35253f',
    line='#68516f',fg='#f2e6f3',mute='#b9a8c3',gold='#d5addb',deep='#21152d',
    **{'raise':'#654572'},edge='#5d4569',glow='#38263f',tag_g='#243b3e',
    tag_r='#482e3c',tag_y='#423747',on_gold='#201528',good='#8ccfcc',
    good2='#a7ded7',bad='#df91a8',bad2='#edb2c2',blue='#86c9ec',red='#df91a8'))

THEMES['lol_day']=('Цветение · день',dict(THEMES['lol_day'][1],bg='#f1eaf3',
    panel='#fcf8fd',line='#c3adc9',fg='#2d2035',mute='#73617e',gold='#80519b',
    deep='#e5d9ea',**{'raise':'#ddc7e8'},on_gold='#ffffff'))

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

def app_home():
    d = os.path.join(os.environ.get('APPDATA') or os.path.expanduser('~'), 'LoLHelper')
    os.makedirs(d, exist_ok=True)
    return d

_LAST_ERR = {}
LOG_HOME = None

def log_error(where, e=None):
    try:
        tb = ''.join(traceback.format_exception(type(e), e, e.__traceback__)).strip() if isinstance(e, BaseException) else str(e or '')
        key = (where, tb.splitlines()[-1] if tb else '')
        if time.time() - _LAST_ERR.get(key, 0) < 60: return
        _LAST_ERR[key] = time.time()
        path = os.path.join(LOG_HOME or app_home(), 'errors.log')
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
        if not isinstance(saved,dict): saved={}
        if os.path.isfile(self.path) and not os.path.exists(self.path+".pre-v2"):
            import shutil
            with open(self.path,"rb") as original, open(self.path+".pre-v2","xb") as backup:
                shutil.copyfileobj(original,backup)
        self.update(copy.deepcopy(saved))
        for k, v in DEFAULTS.items():
            self[k] = (copy.deepcopy({**v, **saved.get(k, {})}) if isinstance(v, dict) and isinstance(saved.get(k, {}),dict) else copy.deepcopy(saved.get(k, v)))
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

def bundle_dir():
    import sys
    return getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))

def tier_of(text):
    """'Изумруд IV · 17 LP' -> 'Изумруд'."""
    w = (text or '').split(' ')[0]
    return w if w in TIER_RU.values() else None

def tab_rect_drag(rect, dx, dy, resize=False):
    """Смещение в долях высоты окна игры; resize сохраняет левый верхний угол."""
    l, t, w, h = rect
    if resize: w, h = max(.2, w + dx), max(.1, h + dy)
    else: l, t = l + dx, t + dy
    return [round(v, 4) for v in (l, t, w, h)]


def rank_short(r):
    if not r: return ''
    t = TIER_RU.get(r['tier'], r['tier'])
    div = r['div'] if r['tier'] not in ('MASTER', 'GRANDMASTER', 'CHALLENGER') else ''
    return f"{t} {div}".strip() + f"\n{r['lp']} LP" + (f" · {round(r['w'] / (r['w'] + r['l']) * 100)}%" if r['l'] else '')


def hist_tags(h):
    """Метки игрока в стиле Porofessor: (текст, вид g|r|y|n) и строка итога последних игр."""
    if not h: return '', []
    tags = [(text, {'good':'g','neutral':'y','bad':'r'}[tone]) for _,text,tone in player_comments.comments(h)]
    if not h.get('n'): return 'История игрока недоступна', tags
    top = [f"{h['w']}–{h['n'] - h['w']} за {h['n']}"]
    if h['on']: top.append(f"на чемпионе {h['on']} игр, {round(h['on_w'] / h['on'] * 100)}%")
    top.append(f"KDA {h['kda']}")
    return ' · '.join(top), tags


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
