# Связь с клиентом LoL (LCU) и с игрой (Live Client Data). Только чтение, кроме импорта рун и набора предметов.
import base64, json, os, re, ssl, subprocess, urllib.request

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
            return _req(f'https://127.0.0.1:{self.port}{path}', method, body, self.token)
        except urllib.error.HTTPError as e:
            if e.code == 404: return None
            raise
        except Exception:
            self.port = None   # клиент перезапустили: найдём заново
            return None

    def me(self):
        s = self.call('/lol-summoner/v1/current-summoner')
        if not s: return None
        name = s.get('gameName') or s.get('displayName') or ''
        return {'riot': f"{name}#{s.get('tagLine', '')}", 'id': s.get('summonerId')}

    def phase(self):
        return self.call('/lol-gameflow/v1/gameflow-phase') or 'None'

    def champ_select(self):
        return self.call('/lol-champ-select/v1/session')

    def set_runes(self, name, prim, sec, perks):
        """Создаёт страницу рун «LoL Helper», заменяя прошлую такую же."""
        pages = self.call('/lol-perks/v1/pages') or []
        for p in pages:
            if p.get('name', '').startswith('LoL Helper') and p.get('isDeletable'):
                self.call(f"/lol-perks/v1/pages/{p['id']}", 'DELETE')
        body = {'name': f'LoL Helper: {name}', 'primaryStyleId': prim, 'subStyleId': sec,
                'selectedPerkIds': list(perks) + [5008, 5008, 5011], 'current': True}
        try:
            self.call('/lol-perks/v1/pages', 'POST', body); return True
        except urllib.error.HTTPError:
            # лимит страниц: удаляем текущую редактируемую и пробуем ещё раз
            cur = self.call('/lol-perks/v1/currentpage')
            if cur and cur.get('isDeletable'):
                self.call(f"/lol-perks/v1/pages/{cur['id']}", 'DELETE')
                try:
                    self.call('/lol-perks/v1/pages', 'POST', body); return True
                except Exception:
                    pass
        return False

    def set_items(self, summoner_id, champ_id, title, blocks):
        """Набор предметов в магазине для чемпиона. blocks: [(название, [id предметов])]."""
        path = f'/lol-item-sets/v1/item-sets/{summoner_id}/sets'
        cur = self.call(path) or {'itemSets': [], 'accountId': summoner_id, 'timestamp': 0}
        sets = [s for s in cur.get('itemSets', []) if not s.get('title', '').startswith('LoL Helper')]
        sets.append({'title': f'LoL Helper: {title}', 'associatedChampions': [int(champ_id)], 'associatedMaps': [11],
                     'type': 'custom', 'map': 'any', 'mode': 'any', 'sortrank': 0, 'startedFrom': 'blank',
                     'blocks': [{'type': n, 'items': [{'id': str(i), 'count': 1} for i in its]} for n, its in blocks if its]})
        cur['itemSets'] = sets
        try:
            self.call(path, 'PUT', cur); return True
        except Exception:
            return False
