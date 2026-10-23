# Логика LoL Helper без интерфейса и без Windows: драфт, разбор живой игры, подсказки.
# Всё здесь проверяется тестами на любой системе (app/test_core.py).
import json, math, re, time

ROLES = ['TOP', 'JUNGLE', 'MIDDLE', 'BOTTOM', 'UTILITY']
ROLE_RU = {'TOP': 'топ', 'JUNGLE': 'лес', 'MIDDLE': 'мид', 'BOTTOM': 'бот', 'UTILITY': 'саппорт', '': '—'}
LCU_ROLE = {'top': 'TOP', 'jungle': 'JUNGLE', 'middle': 'MIDDLE', 'bottom': 'BOTTOM', 'utility': 'UTILITY'}

# Время объектов сезона 2026 (секунды). Меняются в настройках, если Riot их поправит.
OBJ = {'dragon_first': 300, 'dragon_respawn': 300, 'elder_respawn': 360, 'grubs': 480, 'herald': 900,
       'baron_first': 1200, 'baron_respawn': 360, 'inhib_respawn': 300}

# Лесники: ранние ганкеры и фармеры (для третьего окна ганка)
JG_EARLY = {'LeeSin', 'Elise', 'JarvanIV', 'RekSai', 'XinZhao', 'Nidalee', 'Shaco', 'Rengar', 'Pantheon', 'Vi', 'Warwick',
            'Briar', 'Naafiri', 'Qiyana', 'Talon', 'Nunu', 'Volibear', 'Taliyah', 'Poppy', 'Sylas', 'Elise', 'Twitch', 'Skarner', 'Rell'}
JG_FARM = {'Karthus', 'Lillia', 'Shyvana', 'MasterYi', 'Kindred', 'Belveth', 'Graves', 'Fiddlesticks', 'Hecarim', 'Khazix',
           'Viego', 'Diana', 'Udyr', 'Ivern', 'Zac', 'Sejuani', 'Amumu', 'Rammus', 'Nocturne', 'Evelynn', 'Kayn', 'Gragas', 'Brand', 'Zyra', 'Mordekaiser'}


def smooth(w, n, k=10, base=.5):
    return (w + k * base) / (n + k)


def plural(n, one, few, many):
    m = n % 100
    w = one if m % 10 == 1 and m != 11 else few if 2 <= m % 10 <= 4 and not 12 <= m <= 14 else many
    return f'{n} {w}'


def mmss(sec):
    sec = max(0, int(sec))
    return f'{sec // 60}:{sec % 60:02d}'


class Data:
    """data.json: статистика обоих игроков, имена, предметы, lolalytics."""

    def __init__(self, d):
        self.d = d
        self.names = d['names']
        self.ids = d['ids']                    # '62' -> 'MonkeyKing'
        self.items = d['items']
        self.lola = d['lola']

    @classmethod
    def load(cls, path):
        return cls(json.load(open(path, encoding='utf-8')))

    def cn(self, key):
        return self.names.get(key, key or '?')

    def iname(self, iid):
        it = self.items.get(str(iid))
        return it['n'] if it else str(iid)

    def igold(self, iid):
        it = self.items.get(str(iid))
        return it['g'] if it else 0

    def who_by_riot(self, riot):
        r = (riot or '').lower()
        for w, p in self.d['players'].items():
            if p['riot'].lower() == r or p['riot'].split('#')[0].lower() == r.split('#')[0]:
                return w
        return None

    def role_of_champ(self, c):
        """Самая частая роль чемпиона по lolalytics (сколько игр на каждой)."""
        best = max(((self.lola.get(f'{c}|{r}', {}).get('n', 0), r) for r in ROLES), default=(0, ''))
        return best[1] if best[0] else ''


class Player:
    """Статистика одного игрока: нормы, матчапы, лучшие руны и сборки."""

    def __init__(self, data, who):
        self.data, self.who = data, who
        self.games = data.d['players'][who]['g']
        self.pool = data.d['pools'].get(who, {})

    def on(self, c=None, pos=None):
        return [g for g in self.games if (c is None or g['c'] == c) and (pos is None or g['pos'] == pos)]

    def norm(self, c, pos=None):
        gs = self.on(c, pos) or self.on(c)
        if len(gs) < 3: gs = self.on(pos=pos) if pos else self.games
        avg = lambda k: (sum(g[k] for g in gs if g.get(k) is not None) / max(1, sum(1 for g in gs if g.get(k) is not None))) if gs else None
        return {'n': len(gs), 'csm': avg('csm'), 'cs10': avg('cs10'), 'ed': avg('ed'), 'vsm': avg('vsm'), 'd': avg('d')}

    def vs(self, mine, enemy):
        gs = [g for g in self.games if g['opp'] == enemy and (mine is None or g['c'] == mine)]
        w = sum(g['w'] for g in gs)
        g15 = [g['g15'] for g in gs if g['g15'] is not None]
        return {'n': len(gs), 'w': w, 'g15': sum(g15) / len(g15) if g15 else None}

    def bad_enemies(self, min_n=3):
        by = {}
        for g in self.games:
            if g['opp']:
                o = by.setdefault(g['opp'], [0, 0]); o[0] += 1; o[1] += g['w']
        return sorted([(c, n, w) for c, (n, w) in by.items() if n >= min_n and w / n < .5], key=lambda x: smooth(x[2], x[1], 5))

    def best_runes(self, c):
        """Страница рун с лучшим сглаженным винрейтом (от 3 игр), иначе самая частая."""
        by = {}
        for g in self.on(c):
            if len(g['pk']) != 6 or not g['pr']: continue
            k = (tuple(g['pk']), g['pr'], g['sc'])
            o = by.setdefault(k, [0, 0]); o[0] += 1; o[1] += g['w']
        if not by: return None
        pick = max(by.items(), key=lambda kv: (kv[1][0] >= 3, smooth(kv[1][1], kv[1][0], 5), kv[1][0]))
        (pk, pr, sc), (n, w) = pick
        return {'perks': list(pk), 'prim': pr, 'sec': sc, 'n': n, 'w': w}

    def best_build(self, c):
        """Порядок законченных предметов: самые частые первые два + частые в итоговой сборке."""
        gs = self.on(c)
        if not gs: return []
        first, final = {}, {}
        for g in gs:
            for i, it in enumerate(g['f'][:3]):
                o = first.setdefault(it, [0, 0, 0]); o[0] += 1; o[1] += g['w']; o[2] += i
            for it in set(g['it']):
                if self.data.items.get(str(it), {}).get('done'):
                    o = final.setdefault(it, [0, 0]); o[0] += 1; o[1] += g['w']
        order = [it for it, _ in sorted(first.items(), key=lambda kv: (kv[1][2] / kv[1][0], -kv[1][0])) if first[it][0] >= max(2, len(gs) // 6)]
        rest = [it for it, _ in sorted(final.items(), key=lambda kv: -smooth(kv[1][1], kv[1][0], 5)) if it not in order and final[it][0] >= 2]
        return (order + rest)[:6]


# ---------------- Драфт ----------------

def guess_enemy_roles(data, champs):
    """Распределить вражеских чемпионов по ролям, максимизируя частоту по lolalytics."""
    champs = [c for c in champs if c]
    best, best_s = {}, -1
    def rec(i, used, cur, s):
        nonlocal best, best_s
        if i == len(champs):
            if s > best_s: best, best_s = dict(cur), s
            return
        c = champs[i]
        opts = sorted(ROLES, key=lambda r: -data.lola.get(f'{c}|{r}', {}).get('n', 0))
        for r in opts:
            if r in used: continue
            cur[c] = r
            rec(i + 1, used | {r}, cur, s + math.log1p(data.lola.get(f'{c}|{r}', {}).get('n', 0)))
            del cur[c]
    rec(0, frozenset(), {}, 0)
    return best


def draft_suggest(player, role, enemies=(), unavailable=(), top=3):
    """Кого взять: винрейт на роли со сглаживанием + матчап против вероятного оппонента + Изумруд+."""
    data = player.data
    roles = guess_enemy_roles(data, list(enemies))
    opp = next((c for c, r in roles.items() if r == role), None)
    cands = set(player.pool.get(role, [])) | {g['c'] for g in player.on(pos=role)}
    out = []
    for c in cands:
        if c in unavailable: continue
        gs = player.on(c, role)
        if len(gs) < 2 and c not in player.pool.get(role, []): continue
        w = sum(g['w'] for g in gs)
        s = smooth(w, len(gs), 20)
        v = player.vs(c, opp) if opp else {'n': 0}
        if v['n']: s = s * .6 + smooth(v['w'], v['n'], 2) * .4
        lo = data.lola.get(f'{c}|{role}')
        if lo: s += (lo['wr'] - 50) / 400
        if c in player.pool.get(role, []): s += .01
        why = [f'{plural(len(gs), "игра", "игры", "игр")} на роли, {round(w / len(gs) * 100)}%' if gs else 'в пуле, игр на роли нет']
        if v['n']: why.append(f'с {data.cn(opp)} {v["w"]}–{v["n"] - v["w"]}')
        if lo: why.append(f'Изумруд+ {lo["wr"]:.1f}%')
        out.append({'c': c, 'name': data.cn(c), 's': s, 'why': ', '.join(why), 'pool': c in player.pool.get(role, [])})
    out.sort(key=lambda x: -x['s'])
    return {'opp': opp, 'roles': roles, 'picks': out[:top]}


def ban_suggest(player, unavailable=(), top=3):
    return [(c, n, w) for c, n, w in player.bad_enemies() if c not in unavailable][:top]


def parse_champ_select(sess, data):
    """Сессия выбора чемпионов из LCU -> удобный вид."""
    me_cell = sess.get('localPlayerCellId')
    my = sess.get('myTeam') or []
    mine = next((p for p in my if p.get('cellId') == me_cell), {})
    cid = lambda i: data.ids.get(str(i)) if i else None
    picked = {cid(p.get('championId')) for p in my + (sess.get('theirTeam') or [])} - {None}
    bans = sess.get('bans') or {}
    banned = {cid(b) for b in (bans.get('myTeamBans') or []) + (bans.get('theirTeamBans') or [])} - {None}
    for grp in sess.get('actions') or []:
        for a in grp:
            if a.get('type') == 'ban' and a.get('completed'): banned.add(cid(a.get('championId')))
    banned.discard(None)
    locked = any(a.get('actorCellId') == me_cell and a.get('type') == 'pick' and a.get('completed')
                 for grp in sess.get('actions') or [] for a in grp)
    return {'role': LCU_ROLE.get((mine.get('assignedPosition') or '').lower(), ''),
            'me': cid(mine.get('championId')) or cid(mine.get('championPickIntent')),
            'enemies': [c for c in (cid(p.get('championId')) for p in sess.get('theirTeam') or []) if c],
            'unavailable': picked | banned,
            'phase': (sess.get('timer') or {}).get('phase', ''), 'locked': locked,
            'my_ids': {cid(p.get('championId')): p.get('championId') for p in my if p.get('championId')}}


# ---------------- Живая игра ----------------

def champ_key(p, data):
    raw = p.get('rawChampionName') or ''
    k = raw.replace('game_character_displayname_', '')
    if k: return k
    name = p.get('championName', '')
    return next((key for key, n in data.names.items() if n == name), name)


class Game:
    """Снимок allgamedata, разобранный для подсказок и окон."""

    def __init__(self, raw, data):
        self.raw, self.data = raw, data
        gd = raw.get('gameData') or {}
        self.t = float(gd.get('gameTime') or 0)
        self.mode = gd.get('gameMode', '')
        ap = raw.get('activePlayer') or {}
        self.my_riot = ap.get('riotId') or ap.get('summonerName') or ''
        self.gold = float(ap.get('currentGold') or 0)
        self.players = []
        for p in raw.get('allPlayers') or []:
            its = [x.get('itemID') for x in p.get('items') or []]
            sp = p.get('summonerSpells') or {}
            spells = ' '.join((sp.get(k) or {}).get('rawDisplayName', '') for k in ('summonerSpellOne', 'summonerSpellTwo'))
            sc = p.get('scores') or {}
            riot = p.get('riotId') or (f"{p.get('riotIdGameName', '')}#{p.get('riotIdTagLine', '')}" if p.get('riotIdGameName') else p.get('summonerName', ''))
            self.players.append({
                'riot': riot, 'c': champ_key(p, data), 'team': p.get('team'), 'pos': p.get('position') or '', 'lvl': p.get('level', 1),
                'items': its, 'igold': sum(data.igold(i) * max(1, x.get('count', 1)) for i, x in zip(its, p.get('items') or [])),
                'k': sc.get('kills', 0), 'd': sc.get('deaths', 0), 'a': sc.get('assists', 0), 'cs': sc.get('creepScore', 0), 'ward': sc.get('wardScore', 0),
                'dead': p.get('isDead', False), 'respawn': p.get('respawnTimer', 0), 'smite': 'Smite' in spells, 'tp': 'Teleport' in spells,
                'spells': re.findall(r'(Summoner(?!Spell)[A-Za-z]+?)(?:_|\b)', spells),
                'keystone': ((p.get('runes') or {}).get('keystone') or {}).get('id'),
                'sec_tree': ((p.get('runes') or {}).get('secondaryRuneTree') or {}).get('id'),
            })
        rn = lambda r: (r or '').split('#')[0].lower()
        self.me = next((p for p in self.players if rn(p['riot']) == rn(self.my_riot)), self.players[0] if self.players else None)
        self.my_team = self.me['team'] if self.me else 'ORDER'
        self.allies = [p for p in self.players if p['team'] == self.my_team]
        self.enemies = [p for p in self.players if p['team'] != self.my_team]
        self.events = (raw.get('events') or {}).get('Events') or []
        self.ejg = next((p for p in self.enemies if p['smite']), None) or next((p for p in self.enemies if p['pos'] == 'JUNGLE'), None)
        self.opp = None
        if self.me:
            if self.me['pos']:
                self.opp = next((p for p in self.enemies if p['pos'] == self.me['pos']), None)
            if not self.opp:  # обычные игры без позиций: угадываем по lolalytics
                myrole = data.role_of_champ(self.me['c'])
                roles = guess_enemy_roles(data, [p['c'] for p in self.enemies])
                self.opp = next((p for p in self.enemies if roles.get(p['c']) == myrole), None)
        self.role = (self.me or {}).get('pos') or (data.role_of_champ(self.me['c']) if self.me else '')

    def team_gold(self, team):
        return sum(p['igold'] for p in self.players if p['team'] == team)

    def gold_diff(self):
        return self.team_gold(self.my_team) - sum(p['igold'] for p in self.enemies)

    def lane_diff(self):
        return (self.me['igold'] - self.opp['igold']) if self.me and self.opp else None

    def by_name(self, name):
        n = (name or '').split('#')[0].lower()
        return next((p for p in self.players if p['riot'].split('#')[0].lower() == n or p['c'].lower() == n), None)

    def objectives(self):
        """Таймеры: дракон, личинки, Герольд, барон (по событиям убийства)."""
        o = {}
        drakes = [e for e in self.events if e.get('EventName') == 'DragonKill']
        elder = [e for e in drakes if e.get('DragonType') == 'Elder']
        soul = len([e for e in drakes if e.get('DragonType') != 'Elder']) >= 4
        if drakes:
            last = drakes[-1]['EventTime']
            o['dragon'] = last + (OBJ['elder_respawn'] if soul else OBJ['dragon_respawn'])
            o['dragon_name'] = 'Древний дракон' if soul else 'Дракон'
        else:
            o['dragon'], o['dragon_name'] = OBJ['dragon_first'], 'Дракон'
        barons = [e for e in self.events if e.get('EventName') == 'BaronKill']
        o['baron'] = barons[-1]['EventTime'] + OBJ['baron_respawn'] if barons else OBJ['baron_first']
        if not any(e.get('EventName') == 'HordeKill' for e in self.events) and self.t < OBJ['herald'] - 15: o['grubs'] = OBJ['grubs']
        if not any(e.get('EventName') == 'HeraldKill' for e in self.events) and self.t < OBJ['herald'] + 285: o['herald'] = OBJ['herald']
        return o

    def next_cannon(self):
        """Когда появится следующая волна с осадным миньоном (волны каждые 30 с с 0:30)."""
        n = max(1, math.ceil((self.t - 30) / 30) + 1)
        for k in range(n, n + 12):
            ts = 30 + 30 * (k - 1)
            every = 3 if ts < 900 else 2 if ts < 1500 else 1
            if k % every == 0 and ts >= self.t: return ts
        return None


def gank_windows(game):
    """Три окна ганка: 3 лагеря, полная зачистка, поправка под вражеского лесника."""
    j = game.ejg['c'] if game.ejg else None
    w = [('gank1', 170, 200, 'лесник взял 3 лагеря'), ('gank2', 200, 240, 'полная зачистка и краб')]
    if j in JG_EARLY: w.append(('gank3', 150, 185, f'{game.data.cn(j)} любит ранние ганки'))
    elif j in JG_FARM: w.append(('gank3', 225, 280, f'{game.data.cn(j)} обычно фармит, ганк позже'))
    else: w.append(('gank3', 190, 230, f'обычный темп для {game.data.cn(j)}' if j else 'обычный темп'))
    return w


# ---------------- Подсказки ----------------
# Каждая подсказка: id, раздел, название, режим по умолчанию (off/text/beep/voice), пауза между повторами (с).
HINTS = [
    ('scout', 'Загрузка', 'Карточка оппонента и твоя история против него', 'text', 0),
    ('jungler', 'Загрузка', 'Кто лесник врагов: ранний ганкер или фармер', 'voice', 0),
    ('trinket', 'Загрузка', 'Купи тотем, если слот пуст', 'voice', 60),
    ('early_ward', 'Загрузка', 'Ранний вард в реку / вражеский лес', 'text', 0),
    ('gank1', 'Линия', 'Ганк 1: лесник взял 3 лагеря', 'voice', 0),
    ('gank2', 'Линия', 'Ганк 2: полная зачистка', 'voice', 0),
    ('gank3', 'Линия', 'Ганк 3: под вражеского лесника', 'voice', 0),
    ('jg_seen', 'Линия', 'Лесник врагов на другой стороне: можно давить', 'voice', 45),
    ('cs_norm', 'Линия', 'CS отстаёт от твоей нормы (5, 10, 15 мин)', 'text', 0),
    ('lane_gold', 'Линия', 'Разница в предметах с оппонентом', 'text', 90),
    ('levels', 'Линия', 'Уровни 2, 3 и 6: пик силы', 'voice', 0),
    ('early_deaths', 'Линия', '2 смерти до 14 минуты: играй от варда', 'voice', 0),
    ('base', 'Линия', '1300+ золота: можно на базу', 'beep', 60),
    ('hoard', 'Линия', '2000+ золота не потрачено', 'voice', 120),
    ('tp', 'Линия', 'Телепорт к дракону', 'text', 0),
    ('cannon', 'Линия', 'Волна с осадным миньоном', 'off', 0),
    ('control', 'Обзор и предметы', 'Нет контрольного тотема после возвращения', 'voice', 0),
    ('lens', 'Обзор и предметы', 'Поменяй тотем на линзу', 'text', 0),
    ('vision', 'Обзор и предметы', 'Обзор ниже цели (10 и 20 мин)', 'text', 0),
    ('enemy_dmg', 'Обзор и предметы', 'Тип урона врагов и антихил', 'text', 0),
    ('enemy_item', 'Обзор и предметы', 'Оппонент закончил предмет', 'voice', 0),
    ('next_item', 'Обзор и предметы', 'Следующий предмет по твоему лучшему билду', 'text', 0),
    ('objectives', 'Объекты', 'Дракон, личинки, Герольд, барон: за 60 и 30 с', 'voice', 0),
    ('fight_won', 'Объекты', 'Выиграли драку: берите объект', 'voice', 30),
    ('team_gold', 'Объекты', 'Перевес команды 3000+: играйте вместе', 'text', 240),
    ('side_lane', 'Объекты', 'Впереди после 15 мин: сначала вард, потом сплит', 'text', 240),
    ('baron_jungle', 'Объекты', 'Барон через 30 с: не заходи в лес один', 'voice', 0),
    ('inhib', 'Объекты', 'Ингибитор восстановится через минуту', 'text', 0),
    ('powerspike', 'Пики силы', '6-й уровень раньше/позже оппонента, твой собранный предмет, 11 и 16 уровень', 'voice', 0),
    ('postgame', 'После игры', 'Итог игры: цели и главная ошибка', 'text', 0),
]
HINT_IDS = [h[0] for h in HINTS]


class Hint:
    def __init__(self, hid, text, say=None):
        self.id, self.text, self.say, self.t = hid, text, say if say is not None else text, time.time()

    def __repr__(self):
        return f'<{self.id}: {self.text}>'


class Engine:
    """Проверяет снимок игры раз в секунду и выдаёт подсказки. Помнит, что уже говорил."""

    def __init__(self, data, player, goals=None, enabled=None):
        self.data, self.player = data, player
        self.goals = goals or {'vsm': .8, 'early': 1, 'csm': 7}
        self.enabled = enabled or {h: True for h in HINT_IDS}
        self.cool = {h[0]: h[4] for h in HINTS}
        self.done, self.last = set(), {}
        self.prev = None
        self.fired = []          # история за игру для итога
        self.spent_at = None     # когда последний раз тратили золото (возвращение на базу)

    def _once(self, key):
        if key in self.done: return False
        self.done.add(key); return True

    def _cool(self, hid, now):
        if now - self.last.get(hid, -1e9) < self.cool.get(hid, 0): return False
        self.last[hid] = now; return True

    def tick(self, g):
        out = []
        if not g.me: return out
        add = lambda hid, text, say=None: out.append(Hint(hid, text, say)) if self.enabled.get(hid, True) else None
        t, me, opp, d = g.t, g.me, g.opp, self.data
        p = self.prev
        norm = self.player.norm(me['c'], g.role) if self.player else {}
        laner = g.role not in ('JUNGLE', '')

        # --- загрузка и первые минуты
        if t > 3 and self._once('jungler') and g.ejg:
            j = g.ejg['c']
            kind = 'ранний ганкер, жди его уже к трём минутам' if j in JG_EARLY else 'фармер, первые минуты спокойнее' if j in JG_FARM else 'обычный темп'
            add('jungler', f'Лесник врагов: {d.cn(j)} — {kind}', f'Лесник врагов {d.cn(j)}, {kind}')
        if t > 3 and opp and self._once('scout'):
            v = self.player.vs(None, opp['c']) if self.player else {'n': 0}
            txt = f'Оппонент {d.cn(opp["c"])}: ' + (f'{v["w"]}–{v["n"] - v["w"]} на линии' + (f', золото на 15 в среднем {v["g15"]:+.0f}' if v['g15'] is not None else '') if v['n'] else 'вы ещё не встречались')
            if self.player and any(c == opp['c'] for c, _, _ in self.player.bad_enemies()): txt += '. Это твой неудобный враг: играй от фарма и варда'
            add('scout', txt)
        if 30 < t < 120 and not any(i in (3340, 3363, 3364) for i in me['items']) and self._cool('trinket', t):
            add('trinket', 'Слот тотема пуст: купи Скрытый тотем', 'Купи тотем')
        if 55 < t < 70 and self._once('early_ward'):
            add('early_ward', 'Поставь первый вард в реку или вход во вражеский лес к 1:30', 'Первый вард в реку')

        # --- ганки (только для линии)
        if laner and t < 300:
            for hid, a, b, why in gank_windows(g):
                if a - 20 <= t < a and self._once(hid):
                    add(hid, f'Окно ганка {mmss(a)}–{mmss(b)}: {why}. Вард в реку', 'Окно ганка, вард в реку')
        if laner and g.ejg and 90 < t < 900:
            for e in g.events[-5:]:
                if e.get('EventName') != 'ChampionKill' or e.get('EventTime', 0) < t - 5: continue
                names = [e.get('KillerName')] + list(e.get('Assisters') or [])
                if not any(g.by_name(n) is g.ejg for n in names if n): continue
                victim = g.by_name(e.get('VictimName'))
                far = {'TOP': ('BOTTOM', 'UTILITY'), 'BOTTOM': ('TOP',), 'UTILITY': ('TOP',), 'MIDDLE': ()}
                if victim and victim['pos'] in far.get(g.role, ()) and self._cool('jg_seen', t):
                    add('jg_seen', f'{d.cn(g.ejg["c"])} показался на другой стороне карты: можно давить', 'Лесник на другой стороне, дави')

        # --- CS и золото
        if g.role != 'UTILITY':
            for m in (5, 10, 15):
                if m * 60 <= t < m * 60 + 5 and norm.get('csm') and self._once(f'cs{m}'):
                    want = norm['cs10'] * m / 10 if m <= 10 and norm.get('cs10') else norm['csm'] * m
                    if me['cs'] < want * .85:
                        add('cs_norm', f'{m} мин: {me["cs"]} CS, твоя норма на {d.cn(me["c"])} ~{want:.0f}', f'Отстаёшь по фарму на {want - me["cs"]:.0f} миньонов')
        ld = g.lane_diff()
        if ld is not None and t > 180 and abs(ld) >= 900 and self._cool('lane_gold', t):
            add('lane_gold', f'Разница в предметах с оппонентом ({d.cn(opp["c"])}): {ld:+.0f} золота. ' + ('Преимущество: дави, забирай пластины' if ld > 0 else 'Отстаёшь: фарми под башней, не дерись один на один'))

        # --- уровни
        if opp and p and p.me and p.opp:
            for lv in (2, 3, 6):
                if me['lvl'] >= lv > p.me['lvl'] and opp['lvl'] < lv and self._once(f'lv{lv}'):
                    add('levels' if lv < 6 else 'powerspike', f'У тебя {lv}-й уровень раньше оппонента: пик силы, дави', f'{lv} уровень раньше оппонента, дави')
                if opp['lvl'] >= lv > p.opp['lvl'] and me['lvl'] < lv and self._once(f'olv{lv}'):
                    add('levels' if lv < 6 else 'powerspike', f'У {d.cn(opp["c"])} {lv}-й уровень раньше тебя: отойди', f'У оппонента {lv} уровень, отойди')
        early = [e for e in g.events if e.get('EventName') == 'ChampionKill' and e.get('EventTime', 0) < 840 and (g.by_name(e.get('VictimName')) is me)]
        if len(early) >= 2 and t < 840 and self._once('early2'):
            add('early_deaths', 'Уже 2 смерти до 14 минуты: играй от варда и не дерись без лесника', 'Две ранние смерти, играй от варда')

        # --- золото на руках, возвращение на базу
        if p and g.gold < p.gold - 250: self.spent_at = t
        if 120 < t and g.gold >= 1300 and not me['dead'] and self._cool('base', t):
            add('base', f'{g.gold:.0f} золота: при удобной волне можно на базу', '')
        if g.gold >= 2000 and t > 300 and self._cool('hoard', t):
            add('hoard', f'{g.gold:.0f} золота не потрачено', 'Больше двух тысяч золота, на базу')

        # --- обзор и предметы
        if p and self.spent_at == t and t > 300 and 2055 not in me['items'] and self._cool('control', t):
            add('control', 'Нет контрольного тотема: купи на базе', 'Купи контрольный тотем')
        if me['lvl'] >= 9 and 3340 in me['items'] and self._once('lens'):
            add('lens', 'Девятый уровень: поменяй Скрытый тотем на Лупу оракула', 'Поменяй тотем на линзу')
        for m in (10, 20):
            if m * 60 <= t < m * 60 + 5 and self._once(f'vis{m}'):
                vsm = me['ward'] / (t / 60)
                if vsm < self.goals.get('vsm', .8) * .9:
                    add('vision', f'Обзор {vsm:.2f}/мин при цели {self.goals.get("vsm", .8)}: поставь вард и контрольный тотем')
        if t > 600 and self._cool('enemy_dmg', t) and 'enemy_dmg' not in self.done:
            tags = [tag for e in g.enemies for i in e['items'] for tag in d.items.get(str(i), {}).get('tags', [])]
            ad, ap = tags.count('Damage') + tags.count('ArmorPenetration'), tags.count('SpellDamage') + tags.count('MagicPenetration')
            heal = tags.count('LifeSteal') + tags.count('SpellVamp')
            msg = []
            if ad + ap >= 6:
                if ad >= 2 * ap: msg.append(f'у врагов в основном физический урон — бери броню')
                elif ap >= 2 * ad: msg.append(f'у врагов в основном магический урон — бери сопротивление магии')
            if heal >= 3: msg.append('много вампиризма — нужен антихил')
            if msg:
                self.done.add('enemy_dmg'); add('enemy_dmg', 'Предметы врагов: ' + '; '.join(msg))
        if opp and p and p.opp:
            for i in set(opp['items']) - set(p.opp['items']):
                if d.items.get(str(i), {}).get('done') and self._once(f'oi{i}'):
                    add('enemy_item', f'{d.cn(opp["c"])} собрал {d.iname(i)}: пик силы, не начинай драку первым', f'Оппонент собрал {d.iname(i)}')
        if p and p.me:
            for i in set(me['items']) - set(p.me['items']):
                if d.items.get(str(i), {}).get('done') and self._once(f'mi{i}'):
                    add('powerspike', f'Собран {d.iname(i)}: твой пик силы, ищи драку или давление', f'Собран {d.iname(i)}, пик силы')
            for lv in (11, 16):
                if me['lvl'] >= lv > p.me['lvl'] and self._once(f'ult{lv}'):
                    add('powerspike', f'{lv}-й уровень: ульта сильнее', '')
        if p and self.spent_at == t and self.player and self._cool('next_item', t):
            have = set(me['items'])
            nxt = next((i for i in self.player.best_build(me['c']) if i not in have), None)
            if nxt: add('next_item', f'Следующий предмет по твоим лучшим играм: {d.iname(nxt)}')

        # --- объекты
        ob = g.objectives()
        for key, label in (('dragon', ob.get('dragon_name', 'Дракон')), ('grubs', 'Личинки'), ('herald', 'Герольд'), ('baron', 'Барон')):
            at = ob.get(key)
            if not at: continue
            for lead in (60, 30):
                if at - lead <= t < at - lead + 2 and self._once(f'{key}{at}-{lead}'):
                    add('objectives', f'{label} через {lead} с ({mmss(at)})', f'{label} через {"минуту" if lead == 60 else "тридцать секунд"}')
                    if key == 'dragon' and lead == 60 and me['tp'] and g.role == 'TOP': add('tp', 'Дракон через минуту: будь готов к телепорту на бот')
            if key == 'baron' and at - 30 <= t < at - 28 and self._once(f'bj{at}'):
                add('baron_jungle', 'Барон через 30 секунд: не заходи в лес один без обзора', 'Не заходи в лес один')
        kills = [e for e in g.events if e.get('EventName') == 'ChampionKill' and e.get('EventTime', 0) > t - 15]
        ek = sum(1 for e in kills if g.by_name(e.get('VictimName')) in g.enemies)
        ak = sum(1 for e in kills if g.by_name(e.get('VictimName')) in g.allies)
        if ek >= 2 and ak <= ek - 2 and self._cool('fight_won', t):
            add('fight_won', f'Выиграли драку {ek}:{ak}: берите дракона, барона или башню', 'Драка выиграна, берите объект')
        gd = g.gold_diff()
        if t > 900 and gd >= 3000 and self._cool('team_gold', t):
            add('team_gold', f'Команда впереди на {gd:.0f} золота: играйте вместе на объекты, не сплитуйся без вардов')
        if 900 < t < 1500 and ld is not None and ld > 0 and self._cool('side_lane', t):
            add('side_lane', 'Ты впереди, но в твоих играх с 15 по 25 минуту ты чаще всего умираешь на боковой линии: сначала вард')
        for e in g.events:
            if e.get('EventName') == 'InhibKilled':
                back = e['EventTime'] + OBJ['inhib_respawn']
                if back - 60 <= t < back - 58 and self._once(f'inh{e.get("EventID")}'):
                    add('inhib', 'Ингибитор восстановится через минуту: успейте дожать линию')
        nc = g.next_cannon()
        if nc and nc - 3 <= t < nc - 1 and self._once(f'cn{nc}'):
            add('cannon', 'Волна с осадным миньоном', 'Осадный миньон')

        self.prev = g
        for h in out: self.fired.append((t, h))
        return out


def postgame(engine, g, player):
    """Итог: цели, выполненные и нет, и одна главная ошибка."""
    if not g or not g.me: return None
    me, mins = g.me, max(1, g.t / 60)
    early = len([e for e in g.events if e.get('EventName') == 'ChampionKill' and e.get('EventTime', 0) < 840 and g.by_name(e.get('VictimName')) is me])
    team_k = sum(p['k'] for p in g.allies) or 1
    goals = engine.goals
    rows = [
        ('CS в минуту', me['cs'] / mins, goals.get('csm', 7), '>=', 1),
        ('Смертей до 14 минуты', early, goals.get('early', 1), '<=', 0),
        ('Смертей за игру', me['d'], goals.get('d', 5), '<=', 0),
        ('Обзор в минуту', me['ward'] / mins, goals.get('vsm', .8), '>=', 2),
        ('Участие в убийствах, %', (me['k'] + me['a']) / team_k * 100, goals.get('kp', 50), '>=', 0),
    ]
    if g.role == 'UTILITY': rows = rows[1:]
    res = [(n, v, th, (v >= th) if op == '>=' else (v <= th), dec) for n, v, th, op, dec in rows]
    worst = min((r for r in res if not r[3]), key=lambda r: (r[1] / r[2] if r[2] else 0) if r[0] in ('CS в минуту', 'Обзор в минуту', 'Участие в убийствах, %') else -r[1], default=None)
    return {'goals': res, 'main': worst[0] if worst else None, 'hints': list(engine.fired), 'me': me, 'min': mins}
