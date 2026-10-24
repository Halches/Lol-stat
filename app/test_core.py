# Тесты логики LoL Helper на заготовленных снимках (без игры и без Windows): python app/test_core.py
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core

D = core.Data.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data.json'))


def pl(name, champ, team, pos, lvl=1, items=(), cs=0, k=0, d=0, a=0, ward=0, smite=False):
    s1 = 'SummonerSmite' if smite else 'SummonerFlash'
    return {'riotId': name + '#EUW', 'rawChampionName': 'game_character_displayname_' + champ, 'championName': champ, 'team': team,
            'position': pos, 'level': lvl, 'items': [{'itemID': i, 'count': 1} for i in items],
            'scores': {'kills': k, 'deaths': d, 'assists': a, 'creepScore': cs, 'wardScore': ward},
            'summonerSpells': {'summonerSpellOne': {'rawDisplayName': s1}, 'summonerSpellTwo': {'rawDisplayName': 'SummonerTeleport'}}}


def snap(t, me=None, opp=None, events=(), gold=500, ejg='LeeSin'):
    me = me or {}
    opp = opp or {}
    return {'activePlayer': {'riotId': 'Halch#EUW', 'currentGold': gold},
            'gameData': {'gameTime': t, 'gameMode': 'CLASSIC'},
            'events': {'Events': list(events)},
            'allPlayers': [pl('Halch', 'Sett', 'ORDER', 'TOP', **me), pl('A2', 'RekSai', 'ORDER', 'JUNGLE', smite=True),
                           pl('A3', 'Viktor', 'ORDER', 'MIDDLE'), pl('A4', 'Jinx', 'ORDER', 'BOTTOM'), pl('A5', 'Rakan', 'ORDER', 'UTILITY'),
                           pl('E1', 'Darius', 'CHAOS', 'TOP', **opp), pl('E2', ejg, 'CHAOS', 'JUNGLE', smite=True),
                           pl('E3', 'Ahri', 'CHAOS', 'MIDDLE'), pl('E4', 'Caitlyn', 'CHAOS', 'BOTTOM'), pl('E5', 'Lux', 'CHAOS', 'UTILITY')]}


def run(eng, snaps):
    out = []
    for s in snaps:
        out += eng.tick(core.Game(s, D))
    return out


def test_game_parse():
    g = core.Game(snap(100), D)
    assert g.me['c'] == 'Sett' and g.opp['c'] == 'Darius' and g.ejg['c'] == 'LeeSin', (g.me, g.opp)
    assert g.role == 'TOP' and len(g.enemies) == 5


def test_no_positions():
    s = snap(100)
    for p in s['allPlayers']: p['position'] = ''
    g = core.Game(s, D)
    assert g.opp and g.opp['c'] == 'Darius', g.opp


def test_gank_windows():
    eng = core.Engine(D, core.Player(D, 'halch'))
    hs = run(eng, [snap(t) for t in range(0, 300, 1)])
    ids = [h.id for h in hs]
    for i in ('jungler', 'scout', 'gank1', 'gank2', 'gank3', 'early_ward'):
        assert i in ids, (i, ids)
    assert ids.count('gank1') == 1
    w = core.gank_windows(core.Game(snap(100, ejg='Karthus'), D))
    assert w[2][1] > 200


def test_objectives_and_levels():
    eng = core.Engine(D, core.Player(D, 'halch'))
    hs = run(eng, [snap(239, me={'lvl': 5}, opp={'lvl': 5}), snap(240, me={'lvl': 6}, opp={'lvl': 5})])
    assert any(h.id == 'objectives' and 'Дракон' in h.text for h in hs), hs
    assert any(h.id == 'powerspike' for h in hs), hs
    ev = [{'EventName': 'DragonKill', 'EventTime': 600, 'DragonType': 'Fire', 'EventID': 1}]
    g = core.Game(snap(700, events=ev), D)
    assert g.objectives()['dragon'] == 900


def test_items_and_gold():
    eng = core.Engine(D, core.Player(D, 'halch'))
    hs = run(eng, [snap(400, gold=2100, opp={'items': [1036]}), snap(401, gold=200, opp={'items': [3071]})])
    ids = [h.id for h in hs]
    assert 'hoard' in ids and 'enemy_item' in ids and 'control' in ids, ids


def test_disabled():
    en = {h: True for h in core.HINT_IDS}; en['gank1'] = False
    eng = core.Engine(D, core.Player(D, 'halch'), enabled=en)
    hs = run(eng, [snap(t) for t in range(140, 160)])
    assert not any(h.id == 'gank1' for h in hs)


def test_cannon():
    g = core.Game(snap(61), D)
    assert g.next_cannon() == 90, g.next_cannon()


def test_draft():
    p = core.Player(D, 'halch')
    r = core.draft_suggest(p, 'TOP', ['Darius', 'LeeSin', 'Ahri', 'Caitlyn', 'Lux'])
    assert r['opp'] == 'Darius' and r['picks'], r
    sess = {'localPlayerCellId': 0, 'myTeam': [{'cellId': 0, 'assignedPosition': 'top', 'championId': 0, 'championPickIntent': 875}],
            'theirTeam': [{'championId': 122}], 'bans': {'myTeamBans': [24], 'theirTeamBans': []}, 'actions': [], 'timer': {'phase': 'BAN_PICK'}}
    cs = core.parse_champ_select(sess, D)
    assert cs['role'] == 'TOP' and cs['me'] == 'Sett' and cs['enemies'] == ['Darius'] and 'Jax' in cs['unavailable'], cs
    assert p.best_runes('Sett') and p.best_build('Sett')
    drv = core.Player(D, 'drv')
    assert drv.pool and D.who_by_riot('drvoldemar#euw') == 'drv'


def test_postgame():
    eng = core.Engine(D, core.Player(D, 'halch'))
    g = core.Game(snap(1500, me={'cs': 150, 'd': 6, 'ward': 10}), D)
    r = core.postgame(eng, g, eng.player)
    assert r['main'] and len(r['goals']) == 5, r


def test_lola_full():
    v = lambda core_, pri: {'sums': {'ids': [4, 14]}, 'runes': {'n': 100, 'wr': 51, 'set': {'pri': pri, 'sec': [8453, 8473], 'mod': [5008, 5008, 5001]}},
                            'items': {'start': {'set': [1055, 2003]}, 'core': {'set': core_, 'n': 900, 'wr': 53.1},
                                      'item4': [{'id': 6333}], 'item5': [{'id': 3053}], 'item6': [{'id': 3026}]}}
    j = {'header': {'n': 5000, 'wr': 51.5}, 'summary': {'pick': v([6692, 3047, 6610], [8010, 9111, 9105, 8299]), 'win': v([6692, 3047, 3161], [8112, 8143, 8137, 8135])},
         'boots': [[3047, 51, 60, 100, 13], [3111, 53, 29, 50, 16]], 'popularItem': [[6692, 51, 50, 1, 1], [3165, 55, 2, 1, 1], [3071, 53, 17, 1, 1]]}
    b = core.parse_lola_full(j)
    assert b['prim'] == 8000 and b['win']['prim'] == 8100 and b['spells'] == ['SummonerFlash', 'SummonerDot'], b
    assert [x[0] for x in b['situ']] == [3111, 3165], b['situ']   # 3047 уже в основе, у 3071 нет подписи
    sets = core.lola_item_sets(b, 'Атрокс')
    assert len(sets) == 2 and sets[1][1][1][1] == [6692, 3047, 3161]
    assert ('Ситуативно: против лечения', [3165]) in sets[0][1]


if __name__ == '__main__':
    n = 0
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); n += 1; print('ok', k)
    print(n, 'tests passed')
