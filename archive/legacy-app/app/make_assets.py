# Картинки для LoL Helper: портреты чемпионов, предметы, заклинания, руны, эмблемы званий -> app/assets.json (PNG в base64).
# Запуск: python app/make_assets.py (нужны tools/dd/*.json и Pillow). В CI запускается перед сборкой exe.
import base64, io, json, os, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
T = os.path.join(HERE, '..', 'tools')
def load(p): return json.load(open(os.path.join(T, p), encoding='utf-8'))
V = open(os.path.join(T, 'dd/ver')).read().strip()
DD = f'https://ddragon.leagueoflegends.com/cdn/{V}/img/'
TIERS = {'IRON': 'Железо', 'BRONZE': 'Бронза', 'SILVER': 'Серебро', 'GOLD': 'Золото', 'PLATINUM': 'Платина', 'EMERALD': 'Изумруд',
         'DIAMOND': 'Алмаз', 'MASTER': 'Мастер', 'GRANDMASTER': 'Грандмастер', 'CHALLENGER': 'Претендент'}


def fetch(url):
    for _ in range(3):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'curl/8'}), timeout=30).read()
        except Exception as e:
            err = e
    print('miss', url, err)
    return None


def png(raw, size, crop=False):
    im = Image.open(io.BytesIO(raw)).convert('RGBA')
    if crop:  # эмблемы: обрезать прозрачные поля
        bb = im.getchannel('A').getbbox()
        if bb: im = im.crop(bb)
        s = max(im.size); sq = Image.new('RGBA', (s, s)); sq.paste(im, ((s - im.width) // 2, (s - im.height) // 2)); im = sq
    im.thumbnail((size, size), Image.LANCZOS)
    b = io.BytesIO(); im.save(b, 'PNG', optimize=True)
    return base64.b64encode(b.getvalue()).decode()


jobs = []   # (группа, ключ, url, размер, обрезка)
for k in load('dd/champion.json')['data']: jobs.append(('champ', k, DD + f'champion/{k}.png', 96, False))
for k, v in load('dd/item.json')['data'].items():
    if v.get('maps', {}).get('11', True): jobs.append(('item', k, DD + f'item/{k}.png', 64, False))
for k, v in load('dd/summoner.json')['data'].items():
    if 'CLASSIC' in v.get('modes', []) or k in ('SummonerSmite', 'SummonerFlash'): jobs.append(('spell', k, DD + f"spell/{v['image']['full']}", 64, False))
for st in load('dd/runes.json'):
    jobs.append(('rune', str(st['id']), 'https://ddragon.leagueoflegends.com/cdn/img/' + st['icon'], 64, False))
    for slot in st['slots']:
        for r in slot['runes']: jobs.append(('rune', str(r['id']), 'https://ddragon.leagueoflegends.com/cdn/img/' + r['icon'], 64, False))
for en, ru in TIERS.items():
    jobs.append(('emb', ru, f'https://raw.communitydragon.org/latest/plugins/rcp-fe-lol-static-assets/global/default/images/ranked-emblem/emblem-{en.lower()}.png', 128, True))

for r, n in (('TOP', 'top'), ('JUNGLE', 'jungle'), ('MIDDLE', 'middle'), ('BOTTOM', 'bottom'), ('UTILITY', 'utility')):   # значки ролей
    jobs.append(('role', r, f'https://raw.communitydragon.org/latest/plugins/rcp-fe-lol-clash/global/default/assets/images/position-selector/positions/icon-position-{n}.png', 64, False))

out = {'v': V, 'champ': {}, 'item': {}, 'spell': {}, 'rune': {}, 'emb': {}, 'role': {}}
with ThreadPoolExecutor(16) as ex:
    for (grp, key, url, size, crop), raw in zip(jobs, ex.map(lambda j: fetch(j[2]), jobs)):
        if raw: out[grp][key] = png(raw, size, crop)
p = os.path.join(HERE, 'assets.json')
json.dump(out, open(p, 'w'), separators=(',', ':'))
print('assets.json', os.path.getsize(p) // 1024, 'KB', {k: len(v) for k, v in out.items() if isinstance(v, dict)})
if len(out['champ']) < 150: sys.exit('мало портретов')
