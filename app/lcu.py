# Связь с клиентом LoL (LCU) и с игрой (Live Client Data). Только чтение, кроме импорта рун и набора предметов.
import base64, json, os, re, ssl, subprocess, urllib.parse, urllib.request
import uuid
import profile_ranks
import rune_catalog

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
    """Снимок текущей игры или None, если данные недоступны."""
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
        if not self.port and not self.find():
            self.last_error = 'клиент недоступен'
            if method != 'GET':
                raise ConnectionError(self.last_error)
            return None
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

    def region(self):
        """Платформа клиента; локаль интерфейса не определяет регион аккаунта."""
        try:
            result = self.call('/riotclient/region-locale')
            return (result or {}).get('region') if isinstance(result, dict) else None
        except Exception: return None

    def ranked_overview(self):
        """Текущие соло/флекс/TFT одним чтением; отсутствие очереди не означает нулевой ранг."""
        try: raw = self.call('/lol-ranked/v1/current-ranked-stats')
        except Exception: raw = None
        return profile_ranks.parse(raw)

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
        page = r.get('games') if isinstance(r, dict) else None
        games = page.get('games') if isinstance(page, dict) else None
        if not isinstance(games, list):
            return None
        out = []
        for g in games:
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
                            'pos': (p.get('selectedPosition') or '').lower(), 'name': (p['gameName']+'#'+p['tagLine']) if p.get('gameName') and p.get('tagLine') else (p.get('gameName') or p.get('summonerName') or '')})
        return out or None

    def queue_and_map(self):
        try:
            session = self.call('/lol-gameflow/v1/session') or {}
            game = session.get('gameData') or {}
            queue = game.get('queue') or {}
            map_id = queue.get('mapId') or (session.get('map') or {}).get('id') or game.get('mapId')
            return queue.get('id'), map_id if type(map_id) is int and map_id > 0 else None
        except Exception:
            return None, None

    def queue(self):
        return self.queue_and_map()[0]

    def live_match_id(self):
        return self.live_match_context()[0]

    def live_match_context(self):
        try:
            session = self.call('/lol-gameflow/v1/session') or {}
        except Exception:
            return None, None
        if session.get('phase') in ('GameStart', 'InProgress', 'Reconnect', 'WaitingForStats', 'PreEndOfGame', 'EndOfGame'):
            game = session.get('gameData') or {}
            gid = game.get('gameId')
            queue = (game.get('queue') or {}).get('id')
            return (gid if type(gid) is int and gid > 0 else None,
                    queue if type(queue) is int else None)
        return None, None

    def timeline(self, gid):
        """Таймлайн игры из клиента: кадры по минутам с событиями и координатами (для карты смертей)."""
        try: return self.call(f'/lol-match-history/v1/game-timelines/{gid}')
        except Exception: return None

    def phase(self):
        """Фаза клиента. None означает отсутствие ответа, строка 'None' — ответ клиента."""
        try:
            return self.call('/lol-gameflow/v1/gameflow-phase')
        except urllib.error.HTTPError:
            return None

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
        """Изменяем только страницу помощника и проверяем активный набор после записи."""
        self.last_error = ''
        perks = list(perks or [])
        shards = list([5008, 5008, 5011] if shards is None else shards)
        if not rune_catalog.valid_page(prim, sec, perks, shards):
            self.last_error = 'проверь ветки, шесть рун и три осколка сборки'
            return False

        path = '/lol-perks/v1/pages'
        current = '/lol-perks/v1/currentpage'
        selected = perks + shards
        body = {'name': f'LoL Helper: {name}'[:25], 'primaryStyleId': prim,
                'subStyleId': sec, 'selectedPerkIds': selected, 'current': True}

        def matches(page):
            ids = page.get('selectedPerkIds')
            return (page.get('primaryStyleId') == prim and page.get('subStyleId') == sec
                    and isinstance(ids, list) and len(ids) == 9 and ids[:4] == selected[:4]
                    and set(ids[4:6]) == set(selected[4:6]) and ids[6:] == selected[6:])

        try:
            pages = self.call(path)
            if not isinstance(pages, list):
                self.last_error = 'клиент недоступен'
                return False
            mine = next((p for p in pages if p.get('isEditable', p.get('isDeletable'))
                         and p.get('id') and p.get('name', '').startswith('LoL Helper: ')), None)
            if mine:
                pid = mine['id']
                if mine.get('name') != body['name'] or not matches(mine):
                    self.call(f'{path}/{pid}', 'PUT', dict(body, id=pid))
            else:
                saved = self.call(path, 'POST', body) or {}
                pid = saved.get('id')
                if not pid:
                    # Некоторые клиенты принимают POST без тела ответа.
                    pages = self.call(path) or []
                    found = [p for p in pages if p.get('name') == body['name'] and matches(p)]
                    pid = found[0].get('id') if len(found) == 1 else None
                if not pid:
                    self.last_error = 'клиент не подтвердил сохранение страницы'
                    return False
        except Exception as error:
            self.last_error = self.last_error or str(error)
            return False
        try:
            self.call(current, 'PUT', pid)
        except Exception:
            pass  # Клиент мог применить запись до обрыва связи. Проверяем фактический выбор.
        try:
            active = self.call(current)
        except Exception:
            active = None
        if not active:
            self.last_error = 'страница сохранена, активная страница не подтверждена'
        elif active.get('id') != pid:
            self.last_error = 'страница сохранена, но не выбрана'
        elif not matches(active):
            self.last_error = 'активная страница отличается от выбранной сборки'
        else:
            self.last_error = ''
            return True
        return False

    def set_items(self, summoner_id, champ_id, title, blocks, map_id=11):
        """Наборы предметов в магазине для чемпиона. blocks: [(название, [id предметов])]; несколько наборов — title=[(название, blocks)]."""
        if not summoner_id:
            s = self.call('/lol-summoner/v1/current-summoner') or {}
            summoner_id = s.get('summonerId') or s.get('accountId')
        if not summoner_id: self.last_error = 'клиент не отдал id призывателя'; return False
        path = f'/lol-item-sets/v1/item-sets/{summoner_id}/sets'
        self.last_error = ''
        try:
            collection = self.call(path)
        except Exception as error:
            self.last_error = self.last_error or str(error)
            return False
        pages = collection.get('itemSets') if isinstance(collection, dict) else None
        if not isinstance(pages, list) or not all(isinstance(p, dict) for p in pages):
            self.last_error = 'клиент не отдал список наборов предметов'
            return False

        # Одинаковые ранги встречаются у старых страниц. При равенстве сохраняем порядок клиента.
        ordered = sorted(pages, key=lambda p: p['sortrank'] if type(p.get('sortrank')) is int else 0)
        incoming = [(title, blocks)] if isinstance(title, str) else list(title)
        # Два постоянных слота. Старые и личные наборы с произвольными UUID сохраняем.
        slot_ids = [str(uuid.uuid5(uuid.NAMESPACE_URL, f'LoLHelper/item-sets/{summoner_id}/{i}'))
                    for i in range(max(2, len(incoming)))]
        owned = {page['uid']: page for page in ordered if page.get('uid') in slot_ids}
        personal_pages = [page for page in ordered if page.get('uid') not in owned]
        imported = []
        for slot, (name, groups) in enumerate(incoming):
            item_blocks = [{'type': label, 'items': [{'id': str(i), 'count': 1} for i in items]}
                           for label, items in groups if items]
            if not item_blocks:
                self.last_error = 'в наборе нет предметов'
                return False
            previous = owned.get(slot_ids[slot], {})
            # UID принадлежит позиции помощника, чтобы следующий импорт обновлял ту же страницу.
            imported.append({**previous, 'uid': slot_ids[slot],
                             'title': f'LoL Helper: {name}'[:75], 'associatedChampions': [int(champ_id)],
                             'associatedMaps': [map_id] if map_id else [], 'type': 'custom', 'map': 'any', 'mode': 'any',
                             'sortrank': slot, 'startedFrom': 'blank', 'blocks': item_blocks})
        if not imported:
            self.last_error = 'нет наборов для импорта'
            return False

        personal = [dict(page, sortrank=i) for i, page in enumerate(personal_pages, start=len(imported))]
        updated = imported + personal
        if pages == updated:
            return True
        try:
            self.call(path, 'PUT', dict(collection, itemSets=updated))
            saved = self.call(path)
        except Exception as error:
            self.last_error = self.last_error or str(error)
            return False

        saved_pages = saved.get('itemSets') if isinstance(saved, dict) else None
        if not isinstance(saved_pages, list) or len(saved_pages) < len(imported):
            self.last_error = 'клиент не подтвердил сохранение первых страниц предметов'
            return False
        for expected, actual in zip(imported, saved_pages):
            fields = ('uid', 'sortrank', 'title', 'associatedChampions', 'associatedMaps')
            if not isinstance(actual, dict) or any(actual.get(k) != expected[k] for k in fields):
                self.last_error = 'клиент не подтвердил порядок наборов предметов'
                return False
            # Клиент может дополнить блоки полями для заклинаний. Сверяем содержимое магазина.
            actual_blocks = [(b.get('type'), b.get('items')) for b in actual.get('blocks') or []]
            if actual_blocks != [(b['type'], b['items']) for b in expected['blocks']]:
                self.last_error = 'предметы на сохранённой странице отличаются от выбранной сборки'
                return False
        saved_personal = saved_pages[len(imported):]
        if (len(saved_personal) != len(personal) or
                any(not isinstance(actual, dict) or any(actual.get(k) != v for k, v in original.items())
                    for original, actual in zip(personal, saved_personal))):
            self.last_error = 'клиент не подтвердил сохранение личных наборов'
            return False
        return True
