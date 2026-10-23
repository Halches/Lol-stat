# Собирает app/data.json для приложения LoL Helper из данных сайта (tools/*.json, tools/dd/*).
# Запуск: python app/make_data.py (из корня репозитория или из app/).
import json, os, time
HERE = os.path.dirname(os.path.abspath(__file__))
T = os.path.join(HERE, '..', 'tools')
def load(p): return json.load(open(os.path.join(T, p), encoding='utf-8'))

games = load('games.json')
icons = load('icons.json')
lola = load('lola.json')
champs = load('dd/champion.json')['data']
items = load('dd/item.json')['data']
patch = open(os.path.join(T, 'dd/ver')).read().strip()

POOLS = {'halch': {'TOP': ['Sett', 'Aatrox', 'Camille', 'DrMundo', 'Garen', 'Irelia'], 'JUNGLE': ['RekSai', 'Sylas', 'Ivern', 'Karthus'],
                   'MIDDLE': ['Viktor', 'Leblanc', 'AurelionSol', 'Sylas'], 'BOTTOM': ['Viktor', 'Aphelios', 'Jinx', 'Jhin'], 'UTILITY': ['Rakan']},
         'drv': {'MIDDLE': ['Hwei', 'Lux'], 'BOTTOM': ['MissFortune', 'Nilah', 'Hwei'], 'UTILITY': ['TahmKench', 'Leona', 'Poppy'], 'JUNGLE': ['Sejuani', 'Briar', 'Volibear'], 'TOP': ['Riven', 'Malphite', 'Chogath', 'Poppy', 'Shen', 'Garen']}}
RIOT = {'halch': 'Halch#9200', 'drv': 'DrVoldemar#EUW'}

players = {w: {'riot': r, 'g': []} for w, r in RIOT.items()}
for rk in load('ranks.json'):   # звание на момент сборки (в приложении потом берётся живое из клиента)
    w = next((w for w, r in RIOT.items() if r == rk['name']), None)
    solo = next((q for q in rk['q'] if q['t'] == 'Соло'), None)
    if w and solo: players[w]['rank'] = solo['r'] + ' · ' + solo['wl']
for g in sorted(games, key=lambda g: g['start']):
    for m in g['me']:
        df = m.get('diffs') or {}
        d10, d15 = df.get('10') or {}, df.get('15') or {}
        players[m['who']]['g'].append({
            'c': m['c'], 'pos': m['pos'], 'w': int(m['win']), 'q': g['q'], 't': g['start'] // 1000, 'dur': g['dur'],
            'opp': (m.get('opp') or {}).get('c'), 'g15': d15.get('gold'), 'cs10': d10.get('mycs'), 'csm': m.get('csm'),
            'd': m.get('d'), 'ed': m.get('early_d', 0), 'vsm': m.get('vsm'), 'kp': m.get('kp'), 'cw': m.get('cw'),
            'k': m.get('k'), 'a': m.get('a'), 'gpm': m.get('gpm'),
            'e': [p['c'] for p in g['parts'] if p['team'] != m['team']],
            'pk': m.get('perks') or [], 'pr': m.get('prim'), 'sc': m.get('sec'), 'f': m.get('first') or [], 'it': [i for i in m.get('items', []) if i],
        })

# у DrVoldemar пул не указан: берём 4 самых сыгранных чемпиона на каждой роли
for w, pl in players.items():
    if POOLS[w]: continue
    by = {}
    for x in pl['g']:
        by.setdefault(x['pos'], {}).setdefault(x['c'], 0)
        by[x['pos']][x['c']] += 1
    POOLS[w] = {pos: [c for c, _ in sorted(cs.items(), key=lambda kv: -kv[1])[:4]] for pos, cs in by.items() if pos in ('TOP', 'JUNGLE', 'MIDDLE', 'BOTTOM', 'UTILITY')}

out = {
    't': time.strftime('%Y-%m-%d %H:%M'), 'patch': patch,
    'names': {k: v['name'] for k, v in champs.items()} | icons.get('names', {}),
    'ids': {v['key']: k for k, v in champs.items()},
    'items': {k: {'g': v['gold']['total'], 'n': v['name'], 'tags': v.get('tags', []), 'done': not v.get('into') and v['gold']['total'] >= 2000,
                  'from': v.get('from', [])}
              for k, v in items.items() if v.get('maps', {}).get('11', True)},
    'lola': {k: v for k, v in lola.items() if not k.startswith('_')},
    'pools': POOLS, 'players': players,
}
p = os.path.join(HERE, 'data.json')
json.dump(out, open(p, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print('data.json', os.path.getsize(p) // 1024, 'KB', {w: len(v['g']) for w, v in players.items()})
