# Логика LoL Helper без интерфейса и без Windows: драфт, разбор живой игры, подсказки.
# Всё здесь проверяется тестами на любой системе (app/test_core.py).
import json, math, re, time

ROLES = ['TOP', 'JUNGLE', 'MIDDLE', 'BOTTOM', 'UTILITY']
ROLE_RU = {'TOP': 'топ', 'JUNGLE': 'лес', 'MIDDLE': 'мид', 'BOTTOM': 'бот', 'UTILITY': 'саппорт', '': '—', 'ARAM': 'ARAM'}
LCU_ROLE = {'top': 'TOP', 'jungle': 'JUNGLE', 'middle': 'MIDDLE', 'bottom': 'BOTTOM', 'utility': 'UTILITY'}

# Время объектов сезона 2026 (секунды). Меняются в настройках, если Riot их поправит.
OBJ = {'crab': 175, 'dragon_first': 300, 'dragon_respawn': 300, 'elder_respawn': 360, 'grubs': 480, 'herald': 900,
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
        self.champs = d.get('champs', {})        # 'Sett' -> {'tags': ['Fighter', 'Tank'], 'atk': 8, 'mag': 1, 'def': 5} (Data Dragon)
        self.lanes = {}                        # 'Seraphine' -> {'UTILITY': 52000, 'MIDDLE': 9000, ...} — игры на линиях, все чемпионы

    def lane_n(self, c, r):
        """Сколько игр у чемпиона на линии (Изумруд+): таблица по всем чемпионам, иначе lolalytics из data.json."""
        n = self.lanes.get(c, {}).get(r)
        return n if n is not None else self.lola.get(f'{c}|{r}', {}).get('n', 0)

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

    def items_value(self, ids):
        """Стоимость предметов как в таблице Tab: все слоты, включая особый слот сапог; без зелий, вардов и тотемов."""
        skip = {'Consumable', 'Trinket'}
        return sum(it['g'] for i in ids for it in [self.items.get(str(i))] if it and not skip & set(it.get('tags') or []))

    def who_by_riot(self, riot):
        r = (riot or '').lower()
        for w, p in self.d['players'].items():
            if p['riot'].lower() == r or p['riot'].split('#')[0].lower() == r.split('#')[0]:
                return w
        return None

    def role_of_champ(self, c):
        """Самая частая роль чемпиона по lolalytics (сколько игр на каждой)."""
        best = max(((self.lane_n(c, r), r) for r in ROLES), default=(0, ''))
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
        def avg(k):
            xs = [g[k] for g in gs if g.get(k) is not None]
            return sum(xs) / len(xs) if xs else None
        kda = [(g['k'] + g['a']) / max(1, g['d']) for g in gs if g.get('k') is not None and g.get('d') is not None]
        return {'n': len(gs), 'csm': avg('csm'), 'cs10': avg('cs10'), 'ed': avg('ed'), 'vsm': avg('vsm'), 'd': avg('d'),
                'gpm': avg('gpm'), 'kp': avg('kp'), 'kda': sum(kda) / len(kda) if kda else None}

    def vs(self, mine, enemy):
        gs = [g for g in self.games if g['opp'] == enemy and (mine is None or g['c'] == mine)]
        w = sum(g['w'] for g in gs)
        g15 = [g['g15'] for g in gs if g['g15'] is not None]
        return {'n': len(gs), 'w': w, 'g15': sum(g15) / len(g15) if g15 else None}

    def matchup_tip(self, enemy):
        """Личный совет по матчапу из твоих игр против него: смерти до 14 минуты и как заканчивались игры."""
        gs = [g for g in self.games if g['opp'] == enemy and g.get('ed') is not None]
        if len(gs) < 2: return None
        ed = sum(g['ed'] for g in gs) / len(gs)
        base = [g['ed'] for g in self.games if g.get('ed') is not None]
        usual = sum(base) / len(base) if base else 0
        lost = [g for g in gs if not g['w']]
        early_lost = sum(1 for g in lost if g['ed'] >= 2)
        if lost and early_lost * 2 >= len(lost) and early_lost >= 2:
            return f'В {early_lost} из {len(lost)} проигрышей против {self.data.cn(enemy)} ты умирал дважды до 14 минуты: первые уровни играй от фарма и варда'
        if ed >= usual + .7:
            return f'Против {self.data.cn(enemy)} ты умираешь до 14 минуты чаще обычного ({ed:.1f} против {usual:.1f} за игру): не начинай размен первым'
        if ed <= usual - .5 and sum(g['w'] for g in gs) * 2 > len(gs):
            return f'Против {self.data.cn(enemy)} ты обычно спокойно стоишь линию ({ed:.1f} смерти до 14 мин): можно давить'
        return None

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

def champ_profile(data, c, dmg=None):
    """Тип урона и живучесть чемпиона: {'ap': доля магического урона 0..1, 'front': танк/брузер}.
    dmg — урон по lolalytics (точнее), иначе оценка Data Dragon (атака и магия по 10-балльной шкале)."""
    info = (getattr(data, 'champs', {}) or {}).get(c) or {}
    if dmg and dmg.get('ad', 0) + dmg.get('ap', 0) > 0: ap = dmg['ap'] / (dmg['ad'] + dmg['ap'])
    elif info: ap = info.get('mag', 0) / max(1, info.get('atk', 0) + info.get('mag', 0))
    else: ap = None
    tags = info.get('tags') or []
    front = 'Tank' in tags or ('Fighter' in tags and info.get('def', 0) >= 6)
    return {'ap': ap, 'front': front, 'known': bool(info) or ap is not None}


def team_comp(data, champs, dmgs=None):
    """Состав команды: доля AP-урона, сколько фронтлайна и сколько чемпионов учтено."""
    pr = [champ_profile(data, c, (dmgs or {}).get(c)) for c in champs if c]
    aps = [x['ap'] for x in pr if x['ap'] is not None]
    return {'n': len(pr), 'ap': sum(aps) / len(aps) if aps else None, 'front': sum(x['front'] for x in pr)}


def comp_advice(data, allies, role, pool, dmgs=None):
    """Чего не хватает команде без тебя и кто из пула это закрывает: (текст, [чемпионы пула]) или None."""
    tc = team_comp(data, allies, dmgs)
    if tc['n'] < 2 or tc['ap'] is None: return None
    need, fit = [], lambda c: True
    if tc['ap'] < .3:
        need.append('почти весь урон физический — нужен магический')
        fit = lambda c, f=fit: f(c) and (champ_profile(data, c, (dmgs or {}).get(c))['ap'] or 0) >= .5
    elif tc['ap'] > .7:
        need.append('почти весь урон магический — нужен физический')
        fit = lambda c, f=fit: f(c) and (champ_profile(data, c, (dmgs or {}).get(c))['ap'] or 1) <= .5
    if tc['front'] == 0 and tc['n'] >= 3 and role in ('TOP', 'JUNGLE', 'UTILITY'):
        need.append('нет фронтлайна — нужен танк или брузер')
        fit = lambda c, f=fit: f(c) and champ_profile(data, c)['front']
    if not need: return None
    return 'У союзников ' + ', '.join(need), [c for c in pool if fit(c)]

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
        opts = sorted(ROLES, key=lambda r: -data.lane_n(c, r))
        for r in opts:
            if r in used: continue
            cur[c] = r
            rec(i + 1, used | {r}, cur, s + math.log1p(data.lane_n(c, r)))
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
    aram = bool(sess.get('benchEnabled'))   # скамейка чемпионов есть только в ARAM-режимах
    if aram: locked = bool(mine.get('championId'))
    return {'role': LCU_ROLE.get((mine.get('assignedPosition') or '').lower(), ''), 'aram': aram,
            'bench': [c for c in (cid(b.get('championId') if isinstance(b, dict) else b) for b in sess.get('benchChampions') or []) if c],
            'me': cid(mine.get('championId')) or cid(mine.get('championPickIntent')),
            'enemies': [c for c in (cid(p.get('championId')) for p in sess.get('theirTeam') or []) if c],
            'unavailable': picked | banned,
            'phase': (sess.get('timer') or {}).get('phase', ''), 'locked': locked, 'arena': False,
            'left': ((sess.get('timer') or {}).get('adjustedTimeLeftInPhase') or 0) / 1000,
            'my_ids': {cid(p.get('championId')): p.get('championId') for p in my if p.get('championId')}}


# ---------------- Живая игра ----------------

def _norm(s):
    return re.sub(r'[\W_]', '', (s or '').lower())


def champ_key(p, data):
    """Ключ чемпиона (как в Data Dragon) из любых вариантов имени, которые отдаёт игра:
    game_character_displayname_Seraphine, Character_Seraphine_Name, русское имя и т.п."""
    keys = data.__dict__.setdefault('_keys', {_norm(k): k for k in data.names})
    ru = data.__dict__.setdefault('_ru', {_norm(n): k for k, n in data.names.items()})
    for cand in (p.get('rawChampionName'), p.get('championName')):
        c = (cand or '').replace('game_character_displayname_', '')
        m = re.search(r'Character_([A-Za-z]+?)_Name', c)
        if m: c = m.group(1)
        n = _norm(c)
        if not n: continue
        if n in keys: return keys[n]
        if n in ru: return ru[n]
    raw = (p.get('rawChampionName') or '').replace('game_character_displayname_', '')
    return raw or p.get('championName', '')


class Game:
    """Снимок allgamedata, разобранный для подсказок и окон."""

    def __init__(self, raw, data):
        self.raw, self.data = raw, data
        gd = raw.get('gameData') or {}
        self.t = float(gd.get('gameTime') or 0)
        self.mode = gd.get('gameMode', '')
        self.arena = self.mode == 'CHERRY'   # Арена: нет линий, лесников и объектов Ущелья
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
                'items': its, 'igold': data.items_value(its),
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


SIDE = {'TOP': 'TOP', 'MIDDLE': 'MIDDLE', 'BOTTOM': 'BOTTOM', 'UTILITY': 'BOTTOM'}   # роль -> сторона карты для ганков
LANE_TO = {'TOP': 'топ', 'MIDDLE': 'мид', 'BOTTOM': 'бот'}


def gank_windows(game, plan=None):
    """Три окна ганка: 3 лагеря, полная зачистка, поправка под вражеского лесника (по его прошлым играм, если они есть)."""
    j = game.ejg['c'] if game.ejg else None
    w = [('gank1', 170, 200, 'лесник взял 3 лагеря'), ('gank2', 200, 240, 'полная зачистка и краб')]
    if plan and plan.get('lane') and plan.get('t'):
        t, mine = plan['t'], plan['lane'] == SIDE.get(game.role)
        who = f"{game.data.cn(j)} в {plan['k']} из {plan['n']} последних игр первым ганкал {LANE_TO[plan['lane']]}"
        w.append(('gank3', max(90, t - 25), t + 15, who + (', это твоя линия' if mine else ', но держи вард и у себя')))
    elif j in JG_EARLY: w.append(('gank3', 150, 185, f'{game.data.cn(j)} любит ранние ганки'))
    elif j in JG_FARM: w.append(('gank3', 225, 280, f'{game.data.cn(j)} обычно фармит, ганк позже'))
    else: w.append(('gank3', 190, 230, f'обычный темп для {game.data.cn(j)}' if j else 'обычный темп'))
    return w


# ---------------- Подсказки ----------------
# Каждая подсказка: id, раздел, название, режим по умолчанию (off/text/beep/voice), пауза между повторами (с).
HINTS = [
    ('scout', 'Загрузка', 'Карточка оппонента и твоя история против него', 'text', 0),
    ('jungler', 'Загрузка', 'Кто лесник врагов: ранний ганкер или фармер', 'voice', 0),
    ('trinket', 'Загрузка', 'Купи тотем, если слот пуст', 'voice', 60),
    ('early_ward', 'Загрузка', 'Первый вард: когда и куда (своё для роли)', 'text', 0),
    ('crab', 'Лес', 'Лесник: крабы в 2:55 и на какой стороне сильнее линии', 'voice', 0),
    ('gank1', 'Линия', 'Ганк 1: лесник взял 3 лагеря', 'voice', 0),
    ('gank2', 'Линия', 'Ганк 2: полная зачистка', 'voice', 0),
    ('gank3', 'Линия', 'Ганк 3: под вражеского лесника', 'voice', 0),
    ('jg_path', 'Линия', 'Куда лесник врагов ганкал в прошлых играх', 'text', 0),
    ('jg_seen', 'Линия', 'Лесник врагов на другой стороне: можно давить', 'voice', 45),
    ('cs_norm', 'Линия', 'CS отстаёт от твоей нормы (5, 10, 15 мин)', 'text', 0),
    ('lane_gold', 'Линия', 'Разница в предметах с оппонентом', 'text', 90),
    ('levels', 'Линия', 'Уровни 2, 3 и 6: пик силы', 'voice', 0),
    ('skills', 'Линия', 'Какое умение качать на 1–3 уровне и когда ульту (по Европе)', 'voice', 0),
    ('bench', 'Линия', 'Контрольные точки 10 и 15 мин: CS и золото против нормы', 'text', 0),
    ('early_deaths', 'Линия', '2 смерти до 14 минуты: играй от варда', 'voice', 0),
    ('base', 'Линия', '1300+ золота: можно на базу', 'beep', 60),
    ('hoard', 'Линия', '2000+ золота не потрачено', 'voice', 120),
    ('tp', 'Линия', 'Телепорт к дракону', 'text', 0),
    ('cannon', 'Линия', 'Волна с осадным миньоном', 'off', 0),
    ('control', 'Обзор и предметы', 'Нет контрольного тотема после возвращения', 'voice', 0),
    ('lens', 'Обзор и предметы', 'Поддержка: поменяй тотем на линзу', 'text', 0),
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
SKILL_SAY = {'Q': 'ку', 'W': 'дабл-ю', 'E': 'и', 'R': 'ульту'}
# Когда срабатывает и зачем — для вкладки «Подсказки».
HINT_DESC = {
    'scout': 'На 0:03. Твой счёт против этого оппонента по истории игр и золото на 15 минуте. Помечает неудобных врагов.',
    'jungler': 'На 0:03. Кто лесник врагов и в каком темпе он обычно играет: ранний ганкер, фармер или обычный.',
    'trinket': 'С 0:30 до 2:00, если слот тотема пуст. Чтобы не выйти на линию без варда.',
    'early_ward': 'С 0:20 до 0:40, пока идёшь на линию. Куда и когда ставить первый вард, своё для каждой роли.',
    'crab': 'За 25 с до появления крабов (2:55). Какой краб брать: там, где твои линии сильнее по уровню и фарму.',
    'gank1': 'За 20 с до окна 2:50–3:20: в это время приходит лесник, взявший 3 лагеря.',
    'gank2': 'За 20 с до окна 3:20–4:00: лесник после полной зачистки и краба.',
    'gank3': 'Окно под конкретного лесника врагов: по его 2–3 последним играм в лесу (где и когда был первый ганк), '
             'а без них по чемпиону: у ранних ганкеров раньше (2:30–3:05), у фармеров позже (3:45–4:40).',
    'jg_path': 'В первые минуты: где лесник врагов был к 3:00 и куда шёл первый ганк в его последних играх (таймлайны из клиента).',
    'jg_seen': 'С 1:30 до 15:00, когда лесник врагов участвует в убийстве на другой стороне карты: в это время можно давить.',
    'cs_norm': 'На 5, 10 и 15 минуте, если фарм ниже 85% твоей обычной нормы на этом чемпионе.',
    'lane_gold': 'После 3:00, когда разница в предметах с оппонентом 900+ золота. Подсказывает, давить или отходить.',
    'levels': 'Когда ты или оппонент первым берёт 2-й или 3-й уровень: момент для размена или отхода.',
    'skills': 'На 1, 2 и 3 уровне и при каждом очке ульты: какое умение качать. Порядок — самый выигрышный по Европе (Изумруд+, lolalytics).',
    'bench': 'На 10:00 и 15:00: твой CS против твоей обычной нормы на чемпионе и темпа Изумруда+, на 15 ещё золото против оппонента.',
    'early_deaths': 'Если до 14:00 ты умер дважды. Совет играть осторожнее, от варда.',
    'base': 'После 2:00, когда у тебя 1300+ золота: можно возвращаться на базу при удобной волне.',
    'hoard': 'После 5:00, если 2000+ золота не потрачено.',
    'tp': 'Только топ: за минуту до дракона, если телепорт готов.',
    'cannon': 'За пару секунд до волны с осадным миньоном. Его легко потерять, если не следить.',
    'control': 'После возвращения на базу, если ты не купил контрольный тотем.',
    'lens': 'Только саппорт: на 9 уровне, если ещё стоит Скрытый тотем.',
    'vision': 'На 10 и 20 минуте, если обзор в минуту ниже твоей цели.',
    'enemy_dmg': 'После 10:00, один раз. Какой урон у врагов по их предметам и нужен ли антихил.',
    'enemy_item': 'Когда оппонент по линии собирает законченный предмет: это его пик силы.',
    'next_item': 'После покупки на базе. Следующий предмет по твоим лучшим играм на этом чемпионе.',
    'objectives': 'За 60 и 30 с до дракона, личинок, Герольда и барона.',
    'fight_won': 'Когда за 15 с враги потеряли хотя бы на 2 чемпиона больше: время брать объект.',
    'team_gold': 'После 15:00, когда команда впереди на 3000+ золота. Совет играть вместе.',
    'side_lane': 'С 15 до 25 минуты, когда ты впереди по линии: напоминание ставить вард перед сплитом.',
    'baron_jungle': 'За 30 с до барона: не заходить в лес одному.',
    'inhib': 'За минуту до восстановления уничтоженного ингибитора.',
    'powerspike': '6-й, 11-й и 16-й уровень раньше или позже оппонента и твой законченный предмет.',
    'postgame': 'После игры, если она длилась дольше 5 минут: цели, которые выполнены и нет, и главная ошибка.',
}
LANERS = ('TOP', 'MIDDLE', 'BOTTOM', 'UTILITY')
# Подсказки, которые нужны не всем ролям; у каждой роли свои режимы. Остальные — общие для всех.
HINT_ROLES = {
    'scout': LANERS, 'crab': ('JUNGLE',), 'gank1': LANERS, 'gank2': LANERS, 'gank3': LANERS, 'jg_path': LANERS, 'jg_seen': LANERS,
    'cs_norm': ('TOP', 'JUNGLE', 'MIDDLE', 'BOTTOM'), 'lane_gold': LANERS, 'levels': LANERS, 'tp': ('TOP',),
    'cannon': ('TOP', 'MIDDLE', 'BOTTOM'), 'lens': ('UTILITY',), 'enemy_item': LANERS, 'side_lane': ('TOP', 'MIDDLE'),
    'early_ward': ROLES,
}


def hint_for(hid, role):
    """Подходит ли подсказка роли (пустая роль — тренировка, подходит всё)."""
    return not role or role in HINT_ROLES.get(hid, ROLES)


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
        self.skills, self.skill_prio = '', ''   # порядок умений по Европе ('QWEQQRQ…'), задаёт программа при старте игры
        self.situ = []           # ситуативные предметы из сборки по Европе: [(id, коротко, когда)]
        self.bench = None        # темп Изумруда+ на чемпионе: {'cs': CS за игру, 'min': минут}
        self.jg_plan = None      # как лесник врагов начинал последние игры (jungle_plan); {} если данных нет

    def _once(self, key):
        if key in self.done: return False
        self.done.add(key); return True

    def _cool(self, hid, now):
        if now - self.last.get(hid, -1e9) < self.cool.get(hid, 0): return False
        self.last[hid] = now; return True

    def tick(self, g):
        out = []
        if not g.me: return out
        add = lambda hid, text, say=None: out.append(Hint(hid, text, say)) if self.enabled.get(hid, True) and hint_for(hid, g.role) else None
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
        if 20 < t < 40 and self._once('early_ward'):   # пока идёшь на линию, до первой встречи у реки
            if g.role == 'JUNGLE':
                add('early_ward', 'Тотем: поставь у входа в свой лес со стороны второго бафа, чтобы увидеть вторжение', 'Вард у входа в свой лес')
            elif g.role == 'UTILITY':
                add('early_ward', 'Поставь вард в куст реки у бота до 1:30, оттуда приходит лесник на первом ганке', 'Вард в речной куст')
            else:
                add('early_ward', 'Первый вард держи до 2:30 и ставь в реку: тогда увидишь первый ганк', 'Первый вард держи до ганка')

        # --- крабы (только для лесника): появляются в 3:30, сторону подсказываем по силе своих линий
        if g.role == 'JUNGLE' and OBJ['crab'] - 25 <= t < OBJ['crab'] - 20 and self._once('crab'):
            def side(roles):
                sc = 0
                for r in roles:
                    a_ = next((x for x in g.allies if x['pos'] == r), None); e_ = next((x for x in g.enemies if x['pos'] == r), None)
                    if a_ and e_: sc += (a_['lvl'] - e_['lvl']) * 10 + (a_['cs'] - e_['cs'])
                return sc
            top, bot = side(['TOP', 'MIDDLE']), side(['BOTTOM', 'UTILITY', 'MIDDLE'])
            where = 'верхнего' if top > bot + 5 else 'нижнего' if bot > top + 5 else None
            if where: add('crab', f'Крабы в {mmss(OBJ["crab"])}: иди на {where} краба — там твои линии сильнее и помогут', f'Крабы через двадцать секунд, иди на {where}')
            else: add('crab', f'Крабы в {mmss(OBJ["crab"])}: линии равны, бери ближайшего краба и поставь вард в реку', 'Крабы через двадцать секунд')

        # --- ганки (только для линии)
        if laner and t < 300:
            if self.jg_plan and self.jg_plan.get('text') and t < 200 and self._once('jg_path'):
                add('jg_path', f'Лесник врагов в прошлых играх: {self.jg_plan["text"]}', 'Лесник врагов: ' + self.jg_plan['say'])
            for hid, a, b, why in gank_windows(g, self.jg_plan):
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
            for m in ((5,) if self.enabled.get('bench', True) else (5, 10, 15)):   # 10 и 15 покрывает «Контрольная точка»
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
        if self.skills:
            was = p.me['lvl'] if p and p.me else 0
            for lv in range(was + 1, min(me['lvl'], len(self.skills)) + 1):
                k = self.skills[lv - 1]
                if (lv <= 3 or k == 'R') and self._once(f'sk{lv}'):
                    prio = f". Дальше максим {' → '.join(self.skill_prio)}" if lv == 3 and self.skill_prio else ''
                    add('skills', f'Уровень {lv}: качай {k}{prio}', 'Качай ульту' if k == 'R' else f'Качай {SKILL_SAY[k]}')
        for m in (10, 15):
            if m * 60 <= t < m * 60 + 5 and g.role != 'UTILITY' and self._once(f'bench{m}'):
                parts = [f'{m}:00 — {me["cs"]} CS']
                want = (norm.get('cs10') * m / 10 if m == 10 and norm.get('cs10') else (norm.get('csm') or 0) * m)
                if want: parts.append(f'твоя норма {want:.0f}')
                if self.bench and self.bench.get('cs'): parts.append(f'Изумруд+ ~{self.bench["cs"] / self.bench.get("min", 28) * m:.0f}')
                if m == 15 and opp:
                    ld = g.lane_diff()
                    v = self.player.vs(me['c'], opp['c']) if self.player else {}
                    if ld is not None: parts.append(f'предметы против оппонента {ld:+.0f}' + (f' (обычно {v["g15"]:+.0f})' if v.get('g15') is not None else ''))
                behind = want and me['cs'] < want * .9
                add('bench', ', '.join(parts) + ('. Отстаёшь: забирай волны перед уходом' if behind else ''), '')
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
        if g.role == 'UTILITY' and me['lvl'] >= 9 and 3340 in me['items'] and self._once('lens'):
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
                want = (['против лечения'] if heal >= 3 else []) + (['против AD', 'против бурста', 'против критов', 'против автоатак'] if ad >= 2 * ap else
                                                                    ['против магов', 'против магов и контроля'] if ap >= 2 * ad else [])
                have = set(me['items'])
                pick = [x for x in self.situ if x[1] in want and x[0] not in have]
                tip = ('. Из твоей сборки: ' + ', '.join(f'{d.iname(i)} ({short})' for i, short, _ in pick[:2])) if pick else ''
                self.done.add('enemy_dmg'); add('enemy_dmg', 'Предметы врагов: ' + '; '.join(msg) + tip)
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
    # невыполненные цели от самой сильной недостачи: «больше» — насколько не дотянул, «меньше» — насколько перебрал
    gap = lambda r: (1 - r[1] / r[2] if r[2] else 1) if r[0] in MORE else (r[1] - r[2]) / max(1, r[2])
    bad = sorted((r for r in res if not r[3]), key=gap, reverse=True)
    mistakes = [(r[0], r[1], r[2], ADVICE[r[0]](r[1], r[2], mins)) for r in bad[:3]]
    norm = player.norm(me['c'], g.role) if player else {}
    return {'goals': res, 'main': bad[0][0] if bad else None, 'mistakes': mistakes, 'hints': list(engine.fired), 'me': me, 'min': mins,
            'role': g.role, 'norm': norm, 'opp': g.opp['c'] if g.opp else None}


# цель итога -> поле нормы игрока (Player.norm) для сравнения «обычно у тебя»
GOAL_NORM = {'CS в минуту': 'csm', 'Смертей до 14 минуты': 'ed', 'Смертей за игру': 'd', 'Обзор в минуту': 'vsm', 'Участие в убийствах, %': 'kp'}


def game_pid(game, puuid):
    return next((x.get('participantId') for x in (game or {}).get('participantIdentities') or []
                 if (x.get('player') or {}).get('puuid') == puuid), None)


def frame_of(fr, pid):
    """Кадр игрока в минуте таймлайна (клиент отдаёт словарь по номерам, Riot API — список)."""
    pf = fr.get('participantFrames') or {}
    if isinstance(pf, dict): return pf.get(str(pid)) or pf.get(pid) or {}
    return next((x for x in pf if x.get('participantId') == pid), {})


def lane_of(x, y):
    """Сторона карты по координатам: диагональ — мид, выше — топ, ниже — бот (река считается своей стороной)."""
    return 'MIDDLE' if abs(x - y) < 2200 else 'TOP' if y > x else 'BOTTOM'


def jungle_game(tl, game, puuid):
    """Начало одной игры лесника: где он к 3:00 и первое убийство или помощь до 6 минут (секунда, сторона)."""
    pid = game_pid(game, puuid)
    frames = (tl or {}).get('frames') or []
    if not pid or len(frames) < 4: return None
    pos = frame_of(frames[3], pid).get('position') or {}
    end = ('TOP' if pos['y'] > pos['x'] else 'BOTTOM') if pos.get('x') is not None and pos.get('y') is not None else None
    first = None
    for fr in frames[:7]:
        for e in fr.get('events') or []:
            if e.get('type') != 'CHAMPION_KILL' or not e.get('position') or (e.get('timestamp') or 0) > 360000: continue
            if e.get('killerId') == pid or pid in (e.get('assistingParticipantIds') or []):
                first = first or ((e.get('timestamp') or 0) // 1000, lane_of(e['position'].get('x', 0), e['position'].get('y', 0)))
    return {'end': end, 'first': first}


def jungle_plan(games):
    """Сводка по 2–3 играм лесника: куда чаще идёт первый ганк и когда. None, если таймлайнов нет."""
    gs = [g for g in games if g]
    if not gs: return None
    n, firsts = len(gs), [g['first'] for g in gs if g['first']]
    out = {'n': n, 'lane': None, 't': None, 'k': 0, 'text': '', 'say': ''}
    if firsts:
        lane = max(LANE_TO, key=lambda l: sum(f[1] == l for f in firsts))
        k = sum(f[1] == lane for f in firsts)
        if k * 2 > n or n == 1:
            ts = sorted(f[0] for f in firsts if f[1] == lane)
            out.update(lane=lane, k=k, t=ts[len(ts) // 2])
            out['text'] = f"в {k} из {n} игр первый ганк на {LANE_TO[lane]} около {mmss(out['t'])}"
            out['say'] = f"первый ганк обычно {LANE_TO[lane]}, около {mmss(out['t'])}"
    ends = [g['end'] for g in gs if g['end']]
    if ends:
        side = max(('TOP', 'BOTTOM'), key=ends.count)
        if ends.count(side) * 2 > len(ends):
            s = f"к 3:00 обычно на {'верхней' if side == 'TOP' else 'нижней'} стороне"
            out['text'] = (out['text'] + ', ' if out['text'] else '') + s
            out['say'] = out['say'] or s
    return out if out['text'] else None


def gold_series(tl, game, puuid, opp_cid=None):
    """Золото по минутам: ты и оппонент по линии. Оппонент — по чемпиону из игры, иначе по линии в итогах клиента."""
    pid = game_pid(game, puuid)
    ps = (game or {}).get('participants') or []
    me = next((p for p in ps if p.get('participantId') == pid), None)
    if not me: return None
    foes = [p for p in ps if p.get('teamId') != me.get('teamId')]
    opp = next((p for p in foes if opp_cid and p.get('championId') == opp_cid), None)
    if not opp:
        lane = lambda p: ((p.get('timeline') or {}).get('lane'), (p.get('timeline') or {}).get('role') if (p.get('timeline') or {}).get('lane') == 'BOTTOM' else '')
        c = [p for p in foes if lane(p) == lane(me)]
        opp = c[0] if len(c) == 1 else None
    if not opp: return None
    frames = (tl or {}).get('frames') or []
    a = [frame_of(f, pid).get('totalGold') or 0 for f in frames]
    b = [frame_of(f, opp['participantId']).get('totalGold') or 0 for f in frames]
    return {'me': a, 'opp': b, 'oc': opp.get('championId')} if len(a) > 2 else None


def gold_note(gs):
    """Подпись к графику золота: разница на 10 и 15 минуте, в конце и где было хуже всего."""
    d = [x - y for x, y in zip(gs['me'], gs['opp'])]
    out = [f'{m} мин: {d[m]:+}' for m in (10, 15) if len(d) > m]
    out.append(f'конец: {d[-1]:+}')
    w = min(range(len(d)), key=d.__getitem__)
    if d[w] < -500 and w != len(d) - 1: out.append(f'хуже всего {d[w]:+} на {w} мин')
    return ' · '.join(out)


def timeline_marks(tl, game, puuid):
    """Точки для карты смертей из таймлайна клиента: [(x, y, секунда, 'death' | 'kill')]. Координаты карты 0..15000."""
    pid = game_pid(game, puuid)
    if not pid: return []
    out = []
    for fr in (tl or {}).get('frames') or []:
        for e in fr.get('events') or []:
            if e.get('type') != 'CHAMPION_KILL' or not e.get('position'): continue
            kind = 'death' if e.get('victimId') == pid else 'kill' if e.get('killerId') == pid or pid in (e.get('assistingParticipantIds') or []) else None
            if kind: out.append((e['position'].get('x', 0), e['position'].get('y', 0), (e.get('timestamp') or 0) // 1000, kind))
    return out


MORE = ('CS в минуту', 'Обзор в минуту', 'Участие в убийствах, %')
# Совет к невыполненной цели итога: (значение, цель, минут игры) -> текст
ADVICE = {
    'CS в минуту': lambda v, th, m: f'недобрал около {round((th - v) * m)} миньонов, это примерно {round((th - v) * m * 21 / 100) * 100:.0f} золота. '
                                    'Перед уходом на базу добивай волну, а в середине игры забирай волны на боковых линиях.',
    'Смертей до 14 минуты': lambda v, th, m: f'{plural(round(v), "смерть", "смерти", "смертей")} на линии. Перед разменом проверь, где лесник врага, '
                                             'и не дави без варда в реке.',
    'Смертей за игру': lambda v, th, m: f'{plural(round(v), "смерть", "смерти", "смертей")} за игру. После линии не заходи в туман без обзора и держись ближе к команде.',
    'Обзор в минуту': lambda v, th, m: f'обзор {v:.1f} в минуту против цели {th}. Покупай контрольный вард каждый заход на базу и ставь тотем, как только он готов.',
    'Участие в убийствах, %': lambda v, th, m: f'участие {v:.0f}% против цели {th}%. Смотри на мини-карту и приходи на драконов и стычки у реки.',
}


def summarize_history(hist, champ_id, pos=None):
    """Характеристика игрока по последним играм: серия, винрейт, игры на чемпионе, KDA и паттерны —
    тильт, в чём силён, в чём слаб (фарм, смерти, урон, обзор)."""
    if not hist: return None
    w = sum(h['win'] for h in hist)
    st = 0
    for h in hist:
        if st == 0 or (st > 0) == h['win']: st += 1 if h['win'] else -1
        else: break
    on = [h for h in hist if str(h['champ']) == str(champ_id)] if champ_id else []
    kd = lambda xs: round(sum(x['k'] + x['a'] for x in xs) / max(1, sum(x['d'] for x in xs)), 1)
    out = {'n': len(hist), 'w': w, 'streak': st, 'on': len(on), 'on_w': sum(x['win'] for x in on), 'kda': kd(on or hist)}
    tags = []
    if len(on) >= len(hist) * .7 and len(on) >= 5: tags.append('играет почти только на нём')
    elif champ_id and not on: tags.append('не играл на нём недавно')
    if st >= 3: tags.append(f'серия побед {st}')
    if st <= -3: tags.append(f'серия поражений {-st}')
    out['tags'] = tags
    out['tilt'], out['good'], out['bad'] = history_patterns(hist, pos)
    return out


def history_patterns(hist, pos=None):
    """Тильт, сильные и слабые стороны по последним играм клиента. Пороги — для Изумруда, у саппорта и леса свои."""
    tilt, good, bad = [], [], []
    st = 0
    for h in hist:
        if st == 0 or (st > 0) == h['win']: st += 1 if h['win'] else -1
        else: break
    if st <= -3: tilt.append(f'{plural(-st, "поражение", "поражения", "поражений")} подряд')
    last5 = hist[:5]
    if len(last5) == 5 and sum(not h['win'] for h in last5) >= 4 and st > -3: tilt.append(f'{sum(not h["win"] for h in last5)} из 5 последних проиграны')
    ds = [h['d'] for h in hist]
    if len(ds) >= 6:
        recent, before = sum(ds[:3]) / 3, sum(ds[3:]) / len(ds[3:])
        if recent >= before + 2 and recent >= 6: tilt.append(f'смертей всё больше: {recent:.0f} за игру против {before:.0f} раньше')
    if st >= 3: good.append(f'в форме, {plural(st, "победа", "победы", "побед")} подряд')
    games = [h for h in hist if h.get('dur', 0) >= 600]
    if len(games) < 3: return tilt, good, bad
    mins = sum(h['dur'] for h in games) / 60
    n = len(games)
    avg_d = sum(h['d'] for h in games) / n
    kda = sum(h['k'] + h['a'] for h in games) / max(1, sum(h['d'] for h in games))
    if avg_d <= 4: good.append(f'редко умирает ({avg_d:.1f} за игру)')
    elif avg_d >= 7: bad.append(f'часто умирает ({avg_d:.1f} за игру)')
    if kda >= 4: good.append(f'KDA {kda:.1f}')
    elif kda <= 2: bad.append(f'KDA {kda:.1f}')
    if 'cs' in games[0]:
        sup = pos == 'UTILITY'
        csm = sum(h['cs'] for h in games) / mins
        if not sup:
            hi, lo = (6.5, 4.8) if pos == 'JUNGLE' else (7.5, 5.8)
            if csm >= hi: good.append(f'хорошо фармит ({csm:.1f} CS/мин)')
            elif csm <= lo: bad.append(f'слабый фарм ({csm:.1f} CS/мин)')
        dmg = sum(h['dmg'] for h in games) / mins
        if dmg >= (700 if sup else 900): good.append(f'много урона ({dmg:.0f}/мин)')
        elif not sup and dmg <= 450: bad.append(f'мало урона ({dmg:.0f}/мин)')
        vis = sum(h['vis'] for h in games) / mins
        hi, lo = (2.2, 1.3) if sup else (1.2, .45)
        if vis >= hi: good.append(f'сильный обзор ({vis:.1f}/мин)')
        elif vis <= lo: bad.append(f'мало обзора ({vis:.1f}/мин)')
    return tilt, good, bad


def item_remaining(data, it, owned):
    """Сколько золота докупить до предмета it, если owned (список id) уже есть. Использованные компоненты убираются из owned."""
    it = str(it)
    if it in owned:
        owned.remove(it); return 0
    info = data.items.get(it) or {}
    comps = [str(x) for x in info.get('from', [])]
    if not comps: return info.get('g', 0)
    own_cost = info.get('g', 0) - sum((data.items.get(x) or {}).get('g', 0) for x in comps)
    return own_cost + sum(item_remaining(data, x, owned) for x in comps)


def next_item_plan(data, player, champ, items, gold):
    """Следующий крупный предмет по лучшей сборке игрока: что докупить сейчас и сколько не хватает.
    -> {'item', 'need' (до предмета), 'comp', 'comp_need' (до компонента)} или None."""
    if not player: return None
    have = [str(i) for i in items]
    target = next((i for i in player.best_build(champ) if str(i) not in have), None)
    if not target: return None
    owned = list(have)
    need = item_remaining(data, target, owned)
    comps = []
    for x in (data.items.get(str(target)) or {}).get('from', []):
        o = list(have)
        r = item_remaining(data, x, o)
        if r > 0: comps.append((str(x), r))
    afford = [c for c in comps if c[1] <= gold]
    comp = max(afford, key=lambda c: c[1]) if afford else (min(comps, key=lambda c: c[1]) if comps else (str(target), need))
    return {'item': str(target), 'need': max(0, need - gold), 'total': need, 'comp': comp[0], 'comp_need': max(0, comp[1] - gold)}


# ---------------- Сборки по Европе (lolalytics, EUW, Изумруд+) ----------------

LOLA_LANE = {'TOP': 'top', 'JUNGLE': 'jungle', 'MIDDLE': 'middle', 'BOTTOM': 'bottom', 'UTILITY': 'support'}
LOLA_FIX = {'MonkeyKing': 'wukong'}
SPELL_KEY = {1: 'SummonerBoost', 3: 'SummonerExhaust', 4: 'SummonerFlash', 6: 'SummonerHaste', 7: 'SummonerHeal', 11: 'SummonerSmite',
             12: 'SummonerTeleport', 13: 'SummonerMana', 14: 'SummonerDot', 21: 'SummonerBarrier', 32: 'SummonerSnowball'}
SPELL_ID = {v: k for k, v in SPELL_KEY.items()}
SPELL_RU = {'SummonerFlash': 'Скачок', 'SummonerDot': 'Воспламенение', 'SummonerTeleport': 'Телепорт', 'SummonerSmite': 'Кара',
            'SummonerHeal': 'Исцеление', 'SummonerBarrier': 'Барьер', 'SummonerExhaust': 'Изнурение', 'SummonerHaste': 'Призрак',
            'SummonerBoost': 'Очищение', 'SummonerMana': 'Ясность', 'SummonerSnowball': 'Метка'}


def lola_url(champ, role):
    if role == 'ARAM': return f"https://lolalytics.com/lol/{LOLA_FIX.get(champ, champ.lower())}/aram/build/?tier=all"
    return (f"https://lolalytics.com/lol/{LOLA_FIX.get(champ, champ.lower())}/build/"
            f"?lane={LOLA_LANE.get(role, 'top')}&tier=emerald_plus&region=euw")


def rune_tree(perk):
    if perk // 100 == 99: return 8100      # Град клинков
    if perk // 100 == 91: return 8000      # Триумф, Легенды
    return perk // 100 * 100


def parse_lola_build(html):
    """Страница сборки lolalytics -> руны, заклинания и предметы, которые там выделены, с числом игр."""
    toks = re.findall(r'<img[^>]*?(rune68|item64|spell64|statmod\w*)/(\d+)\.webp[^>]*?class="([^"]*)"|>([^<>]{2,40})<', html)
    seq = []
    for kind, i, cls, txt in toks:
        if kind:
            if 'grayscale' not in cls: seq.append((kind[:4], int(i)))
        elif txt.strip(): seq.append(('t', txt.strip()))
    def section(name, stop):
        """Выделенные иконки после заголовка name до заголовка stop, плюс первые «N Games» и «% Win Rate» в ней."""
        try: a = next(k for k, s in enumerate(seq) if s == ('t', name))
        except StopIteration: return [], None, None
        ids, n, wr = [], None, None
        for k in range(a + 1, len(seq)):
            kind, v = seq[k]
            if kind == 't':
                if v in stop: break
                m = re.match(r'([\d,]+) Games$', v)
                if m and n is None: n = int(m.group(1).replace(',', ''))
                if v == '% Win Rate' and wr is None and k and re.match(r'[\d.]+$', str(seq[k - 1][1])): wr = float(seq[k - 1][1])
            else: ids.append(v)
            if kind == 't' and re.match(r'[\d.,]+$', v) and v not in stop:
                if wr is None and '.' in v: wr = float(v)
                elif n is None and '.' not in v: n = int(v.replace(',', ''))
        return ids, n, wr
    t = ' '.join(str(v) for _, v in seq)
    m = re.search(r'([\d.]+) Win Rate [\d.]+ WR Delta', t)
    games = re.search(r'Ban Rate ([\d,]+) Games', t)
    spells, _, _ = section('Summoner Spells', {'Skill Order', 'Primary Runes'})
    prim, nr, wrr = section('Primary Runes', {'Secondary'})
    sec, _, _ = section('Secondary', {'Stat Mods'})
    shards, _, _ = section('Stat Mods', {'Starting Items'})
    start, ns, _ = section('Starting Items', {'Core Build'})
    core_, nc, wrc = section('Core Build', {'Item 4'})
    i4, _, _ = section('Item 4', {'Item 5'})
    i5, _, _ = section('Item 5', {'Item 6'})
    i6, _, _ = section('Item 6', {'LEGEND:'})
    prim = [p for p in prim if p > 5100]; sec = [p for p in sec if p > 5100]
    if len(prim) < 4 or len(sec) < 2: return None
    return {'spells': [SPELL_KEY.get(s, s) for s in spells][:2], 'prim': rune_tree(prim[0]), 'sec': rune_tree(sec[0]), 'perks': prim[:4] + sec[:2],
            'shards': [s for s in shards][:3], 'start': start, 'core': core_[:3], 'i4': i4, 'i5': i5, 'i6': i6,
            'n_runes': nr, 'wr_runes': wrr, 'n_core': nc, 'wr_core': wrc, 'wr': float(m.group(1)) if m else None,
            'games': int(games.group(1).replace(',', '')) if games else None}


def lola_build_items(b):
    """Порядок предметов: основа, затем по одному лучшему варианту 4–6 слота без повторов."""
    out = list(b['core'])
    for opts in (b['i4'], b['i5'], b['i6']):
        it = next((x for x in opts if x not in out), None)
        if it: out.append(it)
    return out


# ---------------- Контрпики, синергия и баны (lolalytics, Изумруд+) ----------------

def parse_lola_arena(html):
    """Чемпион в Арене со страницы lolalytics: винрейт и число игр. Винрейты аугментов и предметов Арены Riot показывать запрещает."""
    t = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html))
    wr, n = re.search(r'([\d.]+) ?% Win Rate', t), re.search(r'([\d,]+) Games', t)
    return {'wr': float(wr.group(1)), 'n': int(n.group(1).replace(',', ''))} if wr and n else None


def arena_stats(games, champ=None):
    """Сводка игр Арены (из arena.json): игр, среднее место, доля топ-4, побед, средний урон."""
    gs = [g for g in games if g.get('place') and (champ is None or g['c'] == champ)]
    if not gs: return None
    n = len(gs)
    return {'n': n, 'avg': sum(g['place'] for g in gs) / n, 'top4': sum(g['place'] <= 4 for g in gs) / n * 100,
            'wins': sum(g['place'] == 1 for g in gs), 'dmg': sum(g.get('dmg') or 0 for g in gs) / n}


def arena_best(games, n=3, min_games=3):
    """Твои лучшие чемпионы Арены по среднему месту (от min_games игр)."""
    by = {}
    for g in games:
        if g.get('place'): by.setdefault(g['c'], []).append(g)
    rows = [(c, arena_stats(gs)) for c, gs in by.items() if len(gs) >= min_games]
    return sorted(rows, key=lambda x: (x[1]['avg'], -x[1]['n']))[:n]


def arena_result(game, puuid):
    """Итог игры Арены из истории клиента: место, урон, счёт, чемпион и чемпион напарника."""
    pid = game_pid(game, puuid)
    ps = (game or {}).get('participants') or []
    p = next((x for x in ps if x.get('participantId') == pid), None)
    if not p: return None
    st = p.get('stats') or {}
    sub = st.get('playerSubteamId')
    mate = next((x for x in ps if x is not p and sub and (x.get('stats') or {}).get('playerSubteamId') == sub), None)
    return {'place': st.get('subteamPlacement') or st.get('placement'), 'dmg': st.get('totalDamageDealtToChampions', 0),
            'k': st.get('kills', 0), 'd': st.get('deaths', 0), 'a': st.get('assists', 0), 'c': p.get('championId'),
            'mate': mate.get('championId') if mate else None}


def parse_lola_avg(html):
    """Средние за игру со страницы сборки lolalytics: убийства, смерти, помощь, золото, CS (миньоны + лес)."""
    t = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html))
    f = lambda p: float(re.search(p, t).group(1).replace(',', ''))
    try:
        return {'k': f(r'Kills: ([\d.]+)'), 'd': f(r'Deaths: ([\d.]+)'), 'a': f(r'Assists: ([\d.]+)'), 'g': f(r'Gold: ([\d,]+)'),
                'cs': f(r'Minions Killed: ([\d.]+)') + f(r'Jungle CS: ([\d.]+)')}
    except Exception:
        return None


def lola_api(ep, champ, role, region='all'):
    """JSON lolalytics: ep='counter' — винрейт champ против каждого на линии, ep='build-team' — с каждым союзником,
    ep='build-full' — руны и предметы (популярные и с лучшим винрейтом)."""
    return (f"https://a1.lolalytics.com/mega/?ep={ep}&v=1&patch=30&c={LOLA_FIX.get(champ, champ.lower())}"
            f"&lane={LOLA_LANE.get(role, 'top')}&tier=emerald_plus&queue=ranked&region={region}")


def lola_counters(j, data, min_n=150):
    """Ответ ep=counter -> {враг: (винрейт champ против него, Δ2, игр)}. Δ2 < 0 — champ проигрывает ему сверх ожидаемого.
    Редкие на линии чемпионы (меньше 0,4% матчапов) отбрасываем: высокий винрейт на 200 играх — шум, а не контрпик."""
    rows = (j or {}).get('counters') or []
    floor = max(min_n, sum(x.get('n', 0) for x in rows) * .004)
    out = {}
    for x in rows:
        c = data.ids.get(str(x.get('cid')))
        if c and x.get('n', 0) >= floor: out[c] = (x['vsWr'], x['d2'], x['n'])
    return out


def lola_team(j, data, min_n=150):
    """Ответ ep=build-team -> {(линия LCU, союзник): (винрейт вместе, Δ2, игр)}."""
    back = {v: k for k, v in LOLA_LANE.items()}
    out = {}
    for lane, rows in ((j or {}).get('team') or {}).items():
        for cid, wr, d1, d2, pr, n in rows:
            c = data.ids.get(str(cid))
            if c and n >= min_n: out[(back.get(lane, lane), c)] = (wr, d2, n)
    return out


def counter_picks(cnt, top=3, pool=()):
    """Кто контрит врага: у кого он сильнее всего проигрывает (Δ2). Чемпионы из пула идут отдельно."""
    worst = sorted(cnt.items(), key=lambda kv: kv[1][1])
    return ([(c, -d2, 100 - wr) for c, (wr, d2, n) in worst if d2 <= -1][:top],
            [(c, -cnt[c][1], 100 - cnt[c][0]) for c in pool if c in cnt])


def ban_suggest(player, unavailable=(), top=3, role=None, cnt=None):
    """Кого банить на твоей линии: твои игры против него на этой линии + насколько он контрит твой пул (lolalytics Δ2).
    cnt — {твой чемпион: lola_counters(...)} для чемпионов пула на этой линии."""
    data = player.data
    score, why = {}, {}
    by = {}
    for g in player.games:
        if g['opp'] and (role is None or g['pos'] == role):
            o = by.setdefault(g['opp'], [0, 0]); o[0] += 1; o[1] += g['w']
    for c, (n, w) in by.items():
        if n >= 2 and w / n < .5:
            score[c] = score.get(c, 0) + (n - 2 * w) * 1.5
            why.setdefault(c, []).append(f'ты {w}–{n - w}')
    mine = cnt or {}
    for c in {e for v in mine.values() for e in v}:
        hurt = [(m, -v[c][1]) for m, v in mine.items() if c in v and v[c][1] < 0]
        if not hurt: continue
        s = sum(h for _, h in hurt) / max(1, len(mine))
        if s < .8: continue
        score[c] = score.get(c, 0) + s
        hurt.sort(key=lambda x: -x[1])
        why.setdefault(c, []).append('контрит ' + ', '.join(f'{data.cn(m)} −{h:.1f}%' for m, h in hurt[:2]))
    out = [(c, s, ' · '.join(why[c])) for c, s in score.items() if c not in unavailable]
    out.sort(key=lambda x: -x[1])
    return out[:top]


def ban_pool(player, role, top=3):
    """Чемпионы, на которых ты скорее всего сыграешь на линии: пул, иначе самые частые."""
    pool = list(player.pool.get(role, []))
    if len(pool) < top:
        cnt = {}
        for g in player.on(pos=role): cnt[g['c']] = cnt.get(g['c'], 0) + 1
        pool += [c for c, _ in sorted(cnt.items(), key=lambda kv: -kv[1]) if c not in pool]
    return pool[:max(top, len(player.pool.get(role, [])))][:5]


# ---------------- История матчей из клиента ----------------

QUEUE_RU = {420: 'Одиночная', 440: 'Гибкая', 400: 'Обычная', 430: 'Обычная', 490: 'Быстрая', 450: 'ARAM', 1700: 'Арена', 1900: 'URF'}
TIER_ORDER = ['IRON', 'BRONZE', 'SILVER', 'GOLD', 'PLATINUM', 'EMERALD', 'DIAMOND', 'MASTER', 'GRANDMASTER', 'CHALLENGER']
DIV_ORDER = {'IV': 0, 'III': 1, 'II': 2, 'I': 3}


def ladder(r):
    """Звание одним числом, чтобы считать разницу LP через повышения: 100 LP на дивизион."""
    if not r or r.get('tier') not in TIER_ORDER: return None
    t = TIER_ORDER.index(r['tier'])
    if t >= 7: return 2800 + r.get('lp', 0)
    return t * 400 + DIV_ORDER.get(r.get('div'), 0) * 100 + r.get('lp', 0)


def lp_changes(hist, snaps):
    """LP за каждую одиночную игру по снимкам звания [время мс, ladder]: снимок до игры и первый после,
    если между ними не было других одиночных игр. {gid: +/-LP}."""
    out = {}
    solo = sorted((h for h in hist if h.get('q') == 420), key=lambda h: h['t'])
    for i, h in enumerate(solo):
        end = h['t'] + h.get('dur', 0) * 1000
        nxt = solo[i + 1]['t'] if i + 1 < len(solo) else float('inf')
        before = [v for t, v in snaps if t <= h['t']]
        after = [v for t, v in snaps if end <= t < nxt]
        if before and after: out[h['gid']] = after[0] - before[-1]
    return out


def lcu_pos(p):
    tl = p.get('timeline') or {}
    lane, role = (tl.get('lane') or '').upper(), (tl.get('role') or '').upper()
    if lane in ('MID', 'MIDDLE'): return 'MIDDLE'
    if lane in ('BOT', 'BOTTOM'): return 'UTILITY' if 'SUPPORT' in role else 'BOTTOM'
    return lane if lane in ('TOP', 'JUNGLE') else ''


def review_game(g, puuid, data):
    """Разбор игры из /lol-match-history/v1/games/{id}: обе команды и короткий разбор твоей игры против оппонента по линии."""
    if not g: return None
    who = {x.get('participantId'): x.get('player') or {} for x in g.get('participantIdentities') or []}
    mins = max(1, (g.get('gameDuration') or 0) / 60)
    rows = []
    for p in g.get('participants') or []:
        st, pl = p.get('stats') or {}, who.get(p.get('participantId'), {})
        rows.append({'team': p.get('teamId'), 'c': data.ids.get(str(p.get('championId'))), 'pos': lcu_pos(p),
                     'name': pl.get('gameName') or pl.get('summonerName') or '', 'me': pl.get('puuid') == puuid,
                     'win': bool(st.get('win')), 'k': st.get('kills', 0), 'd': st.get('deaths', 0), 'a': st.get('assists', 0),
                     'cs': st.get('totalMinionsKilled', 0) + st.get('neutralMinionsKilled', 0), 'gold': st.get('goldEarned', 0),
                     'dmg': st.get('totalDamageDealtToChampions', 0), 'vis': st.get('visionScore', 0), 'lvl': st.get('champLevel', 0),
                     'items': [st.get(f'item{i}', 0) for i in range(7)]})
    me = next((r for r in rows if r['me']), None)
    out = {'rows': rows, 'min': mins, 'me': me, 'q': g.get('queueId'), 'lines': []}
    if not me: return out
    team = [r for r in rows if r['team'] == me['team']]
    opp = next((r for r in rows if r['team'] != me['team'] and r['pos'] and r['pos'] == me['pos']), None)
    out['opp'] = opp
    tk_ = sum(r['k'] for r in team) or 1
    kp = (me['k'] + me['a']) / tk_ * 100
    share = me['dmg'] / max(1, sum(r['dmg'] for r in team)) * 100
    csm, vsm = me['cs'] / mins, me['vis'] / mins
    good, bad = [], []
    sup, jg = me['pos'] == 'UTILITY', me['pos'] == 'JUNGLE'
    if not sup:
        lo, hi = (5, 6.5) if jg else (6, 7.5)
        (good if csm >= hi else bad if csm < lo else []).append(f'фарм {csm:.1f} CS/мин')
    (good if me['d'] <= 3 else bad if me['d'] >= 7 else []).append(f'{plural(me["d"], "смерть", "смерти", "смертей")}')
    (good if kp >= 60 else bad if kp < 40 else []).append(f'участие в убийствах {kp:.0f}%')
    vg, vb = (2.0, 1.2) if sup else (1.0, .5)
    (good if vsm >= vg else bad if vsm < vb else []).append(f'обзор {vsm:.1f}/мин')
    if not sup: (good if share >= 28 else bad if share < 16 else []).append(f'{share:.0f}% урона команды')
    if opp:
        dg, dc = me['gold'] - opp['gold'], me['cs'] - opp['cs']
        t = f"против {data.cn(opp['c'])}: золото {dg:+d}, CS {dc:+d}, {me['k']}/{me['d']}/{me['a']} против {opp['k']}/{opp['d']}/{opp['a']}"
        out['lines'].append((t[0].upper() + t[1:], 'good' if dg > 500 else 'bad' if dg < -500 else 'fg'))
    if good: out['lines'].append(('Хорошо: ' + ', '.join(good), 'good'))
    if bad: out['lines'].append(('Плохо: ' + ', '.join(bad), 'bad'))
    tip = None
    if me['d'] >= 7: tip = 'меньше смертей: каждую смерть разбирай — где не было варда и куда пропал лесник врага'
    elif not sup and csm < (5 if jg else 6): tip = 'фарм: доигрывай волны между драками, не уходи с линии с полной волной'
    elif kp < 40: tip = 'чаще присоединяйся к драке за объекты, держи телепорт или ротацию к дракону'
    elif vsm < vb: tip = 'больше вардов: покупай контрольный вард при каждом возвращении'
    if tip: out['lines'].append(('Главное на следующую игру: ' + tip, 'gold'))
    return out


# ---------------- Две сборки lolalytics: популярная и с лучшим винрейтом (ep=build-full) ----------------

# Ситуативные предметы: против чего и когда. Только то, что следует из описания предмета; остальным подписи нет.
SITU = {
    3075: ('против лечения', 'против лечения и автоатак: бери, когда у врагов лечатся'),
    3076: ('против лечения', 'дешёвое антилечение: бери рано против лечащихся'),
    3165: ('против лечения', 'против лечения: бери, когда у врагов лечатся'),
    3033: ('против лечения', 'против лечения и брони'),
    3123: ('против лечения', 'дешёвое антилечение: бери рано против лечащихся'),
    6609: ('против лечения', 'против лечения: бери, когда у врагов лечатся'),
    3156: ('против магов', 'против магического бурста: щит от магии'),
    4401: ('против магов', 'против магического урона'),
    3065: ('против магов', 'против магов, усиливает твоё лечение'),
    2504: ('против магов', 'против магического урона'),
    3091: ('против магов', 'против магического урона'),
    3111: ('против магов и контроля', 'сапоги против магов и контроля'),
    3047: ('против AD', 'сапоги против автоатак'),
    3143: ('против критов', 'против критующих стрелков'),
    3110: ('против автоатак', 'против автоатакующих'),
    6333: ('против бурста', 'против бурста AD: растягивает урон'),
    3053: ('против бурста', 'против бурста в затяжных драках, даёт стойкость'),
    3026: ('если фокусят', 'если тебя фокусят: второе воскрешение, поздняя игра'),
    3157: ('против бурста', 'против бурста: остановка времени'),
    3814: ('против контроля', 'щит от одного умения: против ключевого контроля'),
    3102: ('против контроля', 'щит от одного умения: против ключевого контроля'),
    3139: ('против контроля', 'снимает контроль'),
    3140: ('против контроля', 'снимает контроль'),
    3036: ('против танков', 'против врагов с большим запасом здоровья'),
    6694: ('против брони', 'против брони'),
    6695: ('против щитов', 'против щитов'),
    3135: ('против маг. защиты', 'против магической защиты'),
    3137: ('против маг. защиты', 'против магической защиты'),
}


def _lola_variant(v):
    """summary.pick / summary.win -> руны, заклинания, старт и основа."""
    ru, it = v.get('runes') or {}, v.get('items') or {}
    st = ru.get('set') or {}
    prim, sec = st.get('pri') or [], st.get('sec') or []
    if len(prim) < 4 or len(sec) < 2: return None
    core_ = it.get('core') or {}
    ids = lambda xs: [x['id'] for x in xs or []]
    return {'spells': [SPELL_KEY.get(s, s) for s in ((v.get('sums') or {}).get('ids') or [])][:2],
            'prim': rune_tree(prim[0]), 'sec': rune_tree(sec[0]), 'perks': prim[:4] + sec[:2], 'shards': (st.get('mod') or [])[:3],
            'n_runes': ru.get('n'), 'wr_runes': ru.get('wr'),
            'start': list((it.get('start') or {}).get('set') or []), 'core': list(core_.get('set') or []),
            'n_core': core_.get('n'), 'wr_core': core_.get('wr'),
            'i4': ids(it.get('item4')), 'i5': ids(it.get('item5')), 'i6': ids(it.get('item6')),
            'skills': ''.join('QWER'[int(ch) - 1] for ch in str((v.get('skillorder') or {}).get('id') or '') if ch in '1234'),
            'skill_prio': str((v.get('skillpriority') or {}).get('id') or '')}


def parse_lola_full(j, data=None):
    """Ответ ep=build-full -> популярная сборка (верхний уровень и 'pick'), сборка с лучшим винрейтом ('win')
    и ситуативные предметы ('situ': [(id, коротко, когда)]), которые часто покупают, но вне основы."""
    s = (j or {}).get('summary') or {}
    pick, win = _lola_variant(s.get('pick') or {}), _lola_variant(s.get('win') or {})
    if not pick: return None
    out = dict(pick)
    out['pick'], out['win'] = pick, win or pick
    out['games'] = ((j.get('header') or {}).get('n')) or j.get('n')
    out['wr'] = (j.get('header') or {}).get('wr')
    dm = (j.get('header') or {}).get('damage') or {}
    if dm: out['dmg'] = {'ad': dm.get('physical', 0), 'ap': dm.get('magic', 0), 'true': dm.get('true', 0)}
    used = set(pick['core']) | set((win or pick)['core'])
    situ = []
    for row in (j.get('boots') or [])[:3] + (j.get('popularItem') or []):
        iid, wr, pr = row[0], row[1], row[2]
        if iid in used or iid in (x[0] for x in situ) or pr < .5: continue
        if iid in SITU: situ.append((iid, *SITU[iid]))
    out['situ'] = situ[:8]
    return out


def lola_item_sets(b, name):
    """Наборы предметов для магазина: популярная сборка и с лучшим винрейтом, в конце каждой — ситуативные с подписями."""
    situ = {}
    for iid, short, _ in b.get('situ') or []: situ.setdefault(short, []).append(iid)
    tail = [(f'Ситуативно: {k}', v) for k, v in situ.items()] + [('Тотемы', [2055, 3340, 3364])]
    sets = []
    for key, title in (('pick', 'популярная'), ('win', 'лучший винрейт')):
        v = b.get(key) or b
        n = f" ({v['n_core']} игр, {v['wr_core']:.0f}%)" if v.get('n_core') and v.get('wr_core') else ''
        blocks = [('Старт', v['start']), ('Основа' + n, v['core']), ('Предмет 4', v['i4']), ('Предмет 5', v['i5']), ('Предмет 6', v['i6'])] + tail
        sets.append((f'{name}: {title}', blocks))
    return sets


def lola_lanes(lists, data):
    """Ответы ep=list по пяти линиям {роль LCU: json} -> {чемпион: {роль: игр}} для угадывания линий врагов."""
    out = {}
    for role, j in lists.items():
        for cid, x in ((j or {}).get('cid') or {}).items():
            c = data.ids.get(str(cid))
            if c: out.setdefault(c, {})[role] = x.get('games', 0)
    return out
