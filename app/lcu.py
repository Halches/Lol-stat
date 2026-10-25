# Связь с клиентом LoL (LCU) и с игрой (Live Client Data). Только чтение, кроме импорта рун и набора предметов.
import base64, json, os, re, ssl, subprocess, urllib.parse, urllib.request

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE   # у клиента и игры самоподписанный сертификат riotgames на 127.0.0.1


def _req(url, method='GET', body=None, auth=None, timeout=2):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header('Accept', 'application/json')
    if data is not None: r.add_header('Content-Type', 'application/json')
    if auth: r.add_header('Authorization', 'Basic ' + base64.b64encode(f'riot:{auth}'.encode()).decode())
    with urllib.request.urlopen(r, context=CTX, timeout=timeout) as f:
        raw = f.read()
        if f.headers.get_content_type().startswith('image/'): return raw
        return json.loads(raw) if raw else None


def live_data():
    """Снимок текущей игры или None, если игры нет."""
    try:
        return _req('https://127.0.0.1:2999/liveclientdata/allgamedata', timeout=1)
    except Exception:
        return None


NOWIN = 0x08000000  # CREATE_NO_WINDOW: не мигать консолью


class LCU:
    def __init__(self):
        self.port = self.token = None
        self.last_error = ''

    def find(self):
        """Порт и пароль клиента: из командной строки LeagueClientUx, иначе из lockfile."""
        if os.name == 'nt':
            try:
                out = subprocess.run(['powershell', '-NoProfile', '-Command',
                                      "Get-CimInstance Win32_Process -Filter \"name='LeagueClientUx.exe'\" | Select -Expand CommandLine"],
                                     capture_output=True, text=True, timeout=8, creationflags=NOWIN).stdout
                p, t = re.search(r'--app-port=(\d+)', out), re.search(r'--remoting-auth-token=([\w-]+)', out)
                if p and t:
                    self.port, self.token = p.group(1), t.group(1); return True
            except Exception:
                pass
        for d in (r'C:\Riot Games\League of Legends', r'D:\Riot Games\League of Legends', os.path.expanduser('~/Riot Games/League of Legends')):
            try:
                parts = open(os.path.join(d, 'lockfile')).read().split(':')
                self.port, self.token = parts[2], parts[3]; return True
            except Exception:
                pass
        self.port = self.token = None
        return False

    def call(self, path, method='GET', body=None):
        if not self.port and not self.find(): return None
        try:
            return _req(f'https://127.0.0.1:{self.port}{path}', method, body, self.token, timeout=2 if method == 'GET' else 10)
        except urllib.error.HTTPError as e:
            try: msg = json.loads(e.read() or b'{}').get('message', '')
            except Exception: msg = ''
            self.last_error = f'{method} {path.split("?")[0]}: {e.code} {msg}'.strip()
            if e.code == 404 and method == 'GET': return None
            raise
        except Exception as e:
            self.port = None   # клиент перезапустили: найдём заново
            if method != 'GET':
                self.last_error = f'{method} {path}: {type(e).__name__} {e}'
                raise
            return None

    def me(self):
        s = self.call('/lol-summoner/v1/current-summoner')
        if not s: return None
        name = s.get('gameName') or s.get('displayName') or ''
        return {'riot': f"{name}#{s.get('tagLine', '')}", 'id': s.get('summonerId'), 'puuid': s.get('puuid'),
                'icon': s.get('profileIconId'), 'level': s.get('summonerLevel')}

    def image(self, path):
        """Картинка из ресурсов клиента (иконка профиля, новый чемпион): байты или None."""
        try:
            b = self.call(path)
            return b if isinstance(b, (bytes, bytearray)) else None
        except Exception:
            return None

    def puuid(self, riot):
        name, _, tag = (riot or '').partition('#')
        q = urllib.parse.urlencode({'gameName': name, 'tagLine': tag})
        for path in (f'/lol-summoner/v1/alias/lookup?{q}', f'/player-account/aliases/v1/lookup?{q}'):
            try:
                r = self.call(path)
            except Exception:
                continue
            if isinstance(r, list): r = r[0] if r else None
            if r and r.get('puuid'): return r['puuid']
        return None

    def rank(self, puuid=None):
        """Одиночный рейтинг: {'tier': 'EMERALD', 'div': 'IV', 'lp': 17, 'w': 221, 'l': 211} или None."""
        try:
            r = self.call(f'/lol-ranked/v1/ranked-stats/{puuid}' if puuid else '/lol-ranked/v1/current-ranked-stats')
        except Exception:
            return None
        q = ((r or {}).get('queueMap') or {}).get('RANKED_SOLO_5x5') or {}
        if not q.get('tier') or q['tier'] in ('NONE', ''): return None
        return {'tier': q['tier'], 'div': q.get('division', ''), 'lp': q.get('leaguePoints', 0), 'w': q.get('wins', 0), 'l': q.get('losses', 0)}

    def history(self, puuid, n=20):
        """Последние игры игрока из клиента (как во вкладке «История» профиля):
        [{'win', 'champ' (id), 'k', 'd', 'a', 'q', 'lane'}], новые первыми."""
        try:
            r = self.call(f'/lol-match-history/v1/products/lol/{puuid}/matches?begIndex=0&endIndex={n - 1}')
        except Exception:
            return None
        out = []
        for g in (((r or {}).get('games') or {}).get('games') or []):
            pid = next((x.get('participantId') for x in g.get('participantIdentities') or []
                        if (x.get('player') or {}).get('puuid') == puuid), None)
            p = next((x for x in g.get('participants') or [] if x.get('participantId') == pid), None)
            if not p or (g.get('gameDuration') or 0) < 300: continue
            st = p.get('stats') or {}
            out.append({'win': bool(st.get('win')), 'champ': p.get('championId'), 'k': st.get('kills', 0), 'd': st.get('deaths', 0),
                        'a': st.get('assists', 0), 'q': g.get('queueId'), 't': g.get('gameCreation', 0),
                        'lane': ((p.get('timeline') or {}).get('lane') or ''), 'role': ((p.get('timeline') or {}).get('role') or ''),
                        'gid': g.get('gameId'), 'dur': g.get('gameDuration') or 0,
                        'cs': st.get('totalMinionsKilled', 0) + st.get('neutralMinionsKilled', 0),
                        'dmg': st.get('totalDamageDealtToChampions', 0), 'vis': st.get('visionScore', 0), 'gold': st.get('goldEarned', 0),
                        'items': [st.get(f'item{i}', 0) for i in range(7)], 'spells': [p.get('spell1Id'), p.get('spell2Id')],
                        'lvl': st.get('champLevel', 0), 'perk': st.get('perk0')})
        out.sort(key=lambda x: -x['t'])
        return out

    def game(self, gid):
        """Подробности одной игры: все десять участников."""
        try: return self.call(f'/lol-match-history/v1/games/{gid}')
        except Exception: return None

    def loading(self):
        """Составы на экране загрузки (в драфте противники скрыты, здесь уже видны все десять):
        [{'pu', 'champ' (id), 'pos' ('top'…), 'team' (100/200), 'name'}] или None."""
        try: s = self.call('/lol-gameflow/v1/session')
        except Exception: return None
        gd = (s or {}).get('gameData') or {}
        out = []
        for team, key in ((100, 'teamOne'), (200, 'teamTwo')):
            for p in gd.get(key) or []:
                out.append({'pu': p.get('puuid') or None, 'champ': p.get('championId') or 0, 'team': team,
                            'pos': (p.get('selectedPosition') or '').lower(), 'name': p.get('gameName') or p.get('summonerName') or ''})
        return out or None

    def timeline(self, gid):
        """Таймлайн игры из клиента: кадры по минутам с событиями и координатами (для карты смертей)."""
        try: return self.call(f'/lol-match-history/v1/game-timelines/{gid}')
        except Exception: return None

    def phase(self):
        return self.call('/lol-gameflow/v1/gameflow-phase') or 'None'

    def champ_select(self):
        return self.call('/lol-champ-select/v1/session')

    def set_spells(self, a, b):
        """Заклинания призывателя в драфте. Скачок остаётся на той клавише, где он у тебя сейчас."""
        sess = self.call('/lol-champ-select/v1/session') or {}
        me = next((p for p in sess.get('myTeam') or [] if p.get('cellId') == sess.get('localPlayerCellId')), {})
        if 4 in (a, b) and me.get('spell2Id') == 4 and a == 4: a, b = b, a
        if 4 in (a, b) and me.get('spell1Id') == 4 and b == 4: a, b = b, a
        self.call('/lol-champ-select/v1/session/my-selection', 'PATCH', {'spell1Id': a, 'spell2Id': b})
        return True

    def set_runes(self, name, prim, sec, perks, shards=None):
        """Страница рун «LoL Helper»: правим свою, иначе создаём, иначе перезаписываем текущую редактируемую."""
        body = {'name': f'LoL Helper: {name}'[:25], 'primaryStyleId': prim, 'subStyleId': sec,
                'selectedPerkIds': list(perks) + list(shards or [5008, 5008, 5011]), 'current': True}
        pages = self.call('/lol-perks/v1/pages') or []
        editable = lambda p: p.get('isEditable', p.get('isDeletable'))
        mine = next((p for p in pages if p.get('name', '').startswith('LoL Helper') and editable(p)), None)
        cur = self.call('/lol-perks/v1/currentpage') or {}
        # Как делают Blitz и Porofessor: удалить свою старую страницу и создать заново; при лимите страниц
        # заменить текущую редактируемую. Правка через PUT — последний вариант (в части клиентов отвечает 400).
        plans = []
        if mine: plans.append(('replace', mine['id']))
        plans.append(('post', None))
        if editable(cur) and cur.get('id') != (mine or {}).get('id'): plans.append(('replace', cur['id']))
        if mine: plans.append(('put', mine['id']))
        errors = []
        for kind, pid in plans:
            try:
                if kind == 'replace':
                    self.call(f'/lol-perks/v1/pages/{pid}', 'DELETE')
                    r = self.call('/lol-perks/v1/pages', 'POST', body)
                elif kind == 'post': r = self.call('/lol-perks/v1/pages', 'POST', body)
                else: r = self.call(f'/lol-perks/v1/pages/{pid}', 'PUT', dict(body, id=pid)) or {'id': pid}
                new_id = (r or {}).get('id')
                if new_id:
                    try: self.call('/lol-perks/v1/currentpage', 'PUT', new_id)
                    except Exception: pass
                self.last_error = ''
                return True
            except Exception:
                errors.append(self.last_error)
        self.last_error = '; '.join(e for e in errors if e)
        return False

    def set_items(self, summoner_id, champ_id, title, blocks):
        """Наборы предметов в магазине для чемпиона. blocks: [(название, [id предметов])]; несколько наборов — title=[(название, blocks)]."""
        if not summoner_id:
            s = self.call('/lol-summoner/v1/current-summoner') or {}
            summoner_id = s.get('summonerId') or s.get('accountId')
        if not summoner_id: self.last_error = 'клиент не отдал id призывателя'; return False
        path = f'/lol-item-sets/v1/item-sets/{summoner_id}/sets'
        try: cur = self.call(path) or {}
        except Exception: cur = {}
        cur = {'accountId': cur.get('accountId', summoner_id), 'itemSets': cur.get('itemSets') or [], 'timestamp': cur.get('timestamp', 0)}
        sets = [s for s in cur.get('itemSets', []) if not s.get('title', '').startswith('LoL Helper')]
        for k, (t, bl) in enumerate([(title, blocks)] if isinstance(title, str) else title):   # title — строка или [(название, блоки)]
            sets.append({'title': f'LoL Helper: {t}'[:75], 'associatedChampions': [int(champ_id)], 'associatedMaps': [11],
                         'type': 'custom', 'map': 'any', 'mode': 'any', 'sortrank': k, 'startedFrom': 'blank',
                         'blocks': [{'type': n, 'items': [{'id': str(i), 'count': 1} for i in its]} for n, its in bl if its]})
        cur['itemSets'] = sets
        try:
            self.call(path, 'PUT', cur); return True
        except Exception:
            return False
