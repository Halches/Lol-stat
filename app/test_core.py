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
    # не выполнено 4 цели из 5: в ошибках три самые сильные недостачи, у каждой совет
    names = [m[0] for m in r['mistakes']]
    assert len(r['mistakes']) == 3 and names[0] == r['main'] and all(m[3] for m in r['mistakes']), r['mistakes']
    assert 'CS в минуту' not in names and r['mistakes'][2][3].startswith('6 смертей'), r['mistakes']


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



def test_skills_parse():
    v = {'runes': {'set': {'pri': [8010, 9111, 9105, 8299], 'sec': [8453, 8473]}}, 'skillorder': {'id': '132111414144323333'}, 'skillpriority': {'id': 'QWE'}}
    b = core._lola_variant(v)
    assert b['skills'] == 'QEWQQQRQRQRREWEEEE' and b['skill_prio'] == 'QWE', b['skills']


def test_comp_advice():
    r = core.comp_advice(D, ['Darius', 'Garen', 'Jinx', 'Caitlyn'], 'MIDDLE', ['Lux', 'Zed'])
    assert r and 'магический' in r[0] and r[1] == ['Lux'], r
    assert core.comp_advice(D, ['Darius', 'Lux', 'Jinx', 'Ahri'], 'MIDDLE', ['Lux']) is None


def tl_game(kills, pos3=(3000, 9000)):
    """Таймлайн клиента: 10 кадров, игрок №2 (puuid 'J') — в кадре 3 стоит в pos3; kills: [(секунда, x, y, убийца, жертва)]."""
    frames = [{'participantFrames': {str(i): {'participantId': i, 'totalGold': 500 + m * (400 if i == 2 else 350), 'position': {'x': 7000, 'y': 7000}}
                                     for i in range(1, 11)}, 'events': []} for m in range(10)]
    frames[3]['participantFrames']['2']['position'] = {'x': pos3[0], 'y': pos3[1]}
    for t, x, y, k, v in kills:
        frames[t // 60 + 1]['events'].append({'type': 'CHAMPION_KILL', 'timestamp': t * 1000, 'position': {'x': x, 'y': y}, 'killerId': k, 'victimId': v,
                                              'assistingParticipantIds': []})
    game = {'participantIdentities': [{'participantId': i, 'player': {'puuid': 'J' if i == 2 else f'p{i}'}} for i in range(1, 11)],
            'participants': [{'participantId': i, 'teamId': 100 if i <= 5 else 200, 'championId': 100 + i,
                              'timeline': {'lane': ['TOP', 'JUNGLE', 'MIDDLE', 'BOTTOM', 'BOTTOM'][(i - 1) % 5],
                                           'role': ['SOLO', 'NONE', 'SOLO', 'DUO_CARRY', 'DUO_SUPPORT'][(i - 1) % 5]}} for i in range(1, 11)]}
    return {'frames': frames}, game


def test_jungle_plan():
    gs = [core.jungle_game(*tl_game([(185, 1500, 12000, 2, 6)]), 'J'), core.jungle_game(*tl_game([(200, 2000, 13000, 2, 6)]), 'J'),
          core.jungle_game(*tl_game([(250, 13000, 1500, 2, 9)], pos3=(9000, 3000)), 'J')]
    assert gs[0] == {'end': 'TOP', 'first': (185, 'TOP')}, gs[0]
    p = core.jungle_plan(gs)
    assert p['lane'] == 'TOP' and p['k'] == 2 and p['n'] == 3 and p['t'] == 200 and 'верхней' in p['text'], p
    assert core.jungle_plan([None, None]) is None
    g = core.Game(snap(100), D)
    w = dict((h, (a, b, why)) for h, a, b, why in core.gank_windows(g, p))
    assert w['gank3'][:2] == (175, 215) and 'твоя линия' in w['gank3'][2], w
    eng = core.Engine(D, core.Player(D, 'halch')); eng.jg_plan = p
    hs = run(eng, [snap(t) for t in range(100, 180, 2)])
    ids = [h.id for h in hs]
    assert 'jg_path' in ids and 'gank3' in ids, ids


def test_gold_and_marks():
    tl, game = tl_game([(185, 1500, 12000, 2, 6), (300, 7000, 7000, 7, 2)])
    gs = core.gold_series(tl, game, 'J', opp_cid=107)
    assert gs['oc'] == 107 and gs['me'][9] - gs['opp'][9] == 450, gs
    assert core.gold_series(tl, game, 'J')['oc'] == 107   # без чемпиона: по линии
    assert '+' in core.gold_note(gs)
    m = core.timeline_marks(tl, game, 'J')
    assert [x[3] for x in m] == ['kill', 'death'], m


def test_settings_backup():
    import tempfile, json as js
    try: import ui
    except Exception: return   # без tkinter (CI-ранер Linux) пропускаем
    d = tempfile.mkdtemp()
    s = ui.Settings(d); s['scale'] = 130; s['phone_token'] = 'secret'
    b = js.loads(js.dumps(s.export('v-test')))
    assert 'phone_token' not in b['settings']
    s2 = ui.Settings(tempfile.mkdtemp())
    n = s2.load_backup(b)
    assert s2['scale'] == 130 and n > 5, n
    try: s2.load_backup({'x': 1}); assert False
    except ValueError: pass


def test_items_value():
    d = D
    # сапоги + законченный предмет считаются, зелья (даже 3 шт.), контрольный вард и тотем — нет
    assert d.items_value([3006, 3031, 2003, 2055, 3340]) == d.igold(3006) + d.igold(3031)
    assert d.items_value([]) == 0


def test_arena_mode():
    s = snap(300)
    assert not core.Game(s, D).arena
    s['gameData']['gameMode'] = 'CHERRY'
    assert core.Game(s, D).arena


def test_arena_stats():
    gs = [{'c': 'Sett', 'place': 1, 'dmg': 30000}, {'c': 'Sett', 'place': 5, 'dmg': 10000}, {'c': 'Sett', 'place': 3, 'dmg': 20000},
          {'c': 'Lux', 'place': 8, 'dmg': 5000}, {'c': 'Lux', 'place': 7, 'dmg': 5000}, {'c': 'Lux', 'place': 6, 'dmg': 5000}]
    st = core.arena_stats(gs, 'Sett')
    assert st['n'] == 3 and st['avg'] == 3 and round(st['top4']) == 67 and st['wins'] == 1 and st['dmg'] == 20000
    assert [c for c, _ in core.arena_best(gs)] == ['Sett', 'Lux']
    assert core.arena_stats([]) is None
    game = {'participantIdentities': [{'participantId': 1, 'player': {'puuid': 'me'}}, {'participantId': 2, 'player': {'puuid': 'x'}}],
            'participants': [{'participantId': 1, 'championId': 875, 'stats': {'playerSubteamId': 3, 'subteamPlacement': 2, 'kills': 5, 'deaths': 2,
                                                                               'assists': 4, 'totalDamageDealtToChampions': 41000}},
                             {'participantId': 2, 'championId': 99, 'stats': {'playerSubteamId': 3}}]}
    r = core.arena_result(game, 'me')
    assert r['place'] == 2 and r['mate'] == 99 and r['dmg'] == 41000
    html = '<div>55.29 % Win Rate</div><b>8,718 Games</b>'
    assert core.parse_lola_arena(html) == {'wr': 55.29, 'n': 8718}


if __name__ == '__main__':
    n = 0
    for k, f in list(globals().items()):
        if k.startswith('test_'):
            f(); n += 1; print('ok', k)
    print(n, 'tests passed')
