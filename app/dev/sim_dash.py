# Эмуляция окон без клиента LoL: python3.12 sim_dash.py draft|game -> скриншоты n_*.png в $SIM_OUT (см. README.md рядом).
import sys, os, time, subprocess
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import core, lcu, ui, test_core as T, lolhelper
t0 = time.time()
GAME = {'gameDuration': 1800, 'queueId': 420, 'participantIdentities': [{'participantId': i, 'player': {'gameName': f'P{i}', 'puuid': f'P{i-1}'}} for i in range(1, 11)],
        'participants': [{'participantId': i, 'teamId': 100 if i <= 5 else 200, 'championId': c, 'timeline': {'lane': l, 'role': r},
                          'stats': {'win': i <= 5, 'kills': 5, 'deaths': 3 + i % 4, 'assists': 7, 'totalMinionsKilled': 180 + i * 5, 'neutralMinionsKilled': 0,
                                    'goldEarned': 11000 + i * 100, 'totalDamageDealtToChampions': 20000 + i * 900, 'visionScore': 20, 'champLevel': 15,
                                    'item0': 3071, 'item1': 6631, 'item2': 3047, 'item6': 3340}}
                         for i, (c, l, r) in enumerate(zip([266, 64, 112, 222, 412, 122, 121, 103, 51, 117], ['TOP','JUNGLE','MIDDLE','BOTTOM','BOTTOM']*2,
                                                           ['SOLO','NONE','SOLO','DUO_CARRY','DUO_SUPPORT']*2), 1)]}
mode = sys.argv[1]
OUT = os.environ.get('SIM_OUT', '/tmp')
def fake():
    t = 640 + (time.time() - t0) * 3
    s = T.snap(t, me={'lvl': 11, 'cs': 98, 'items': [3071, 6631, 3047, 3340], 'k': 4, 'd': 1, 'a': 3, 'ward': 9},
               opp={'lvl': 10, 'cs': 85, 'items': [6631, 3047, 1037], 'k': 1, 'd': 4}, gold=1450)
    for p in s['allPlayers']:
        p['runes'] = {'keystone': {'id': 8010}, 'secondaryRuneTree': {'id': 8400}}
    s['allPlayers'][7]['isDead'] = True; s['allPlayers'][7]['respawnTimer'] = 23
    s['allPlayers'][8]['rawChampionName'] = 'game_character_displayname_Character_Seraphine_Name'
    return s
lcu.live_data = fake if mode == 'game' else (lambda: None)
lcu.LCU.puuid = lambda self, r: None
import random
random.seed(1)
def fh(n=20, lose_first=4):
    out=[]
    for i in range(n):
        out.append({'win': i >= lose_first and random.random() > .4, 'champ': 266, 'k': random.randint(1,9), 'd': random.randint(6,11) if i < 3 else random.randint(2,6), 'a': random.randint(2,10),
                    'q': 420, 't': 1767829643000 - i * 3600000, 'lane': 'TOP', 'role': 'SOLO', 'gid': 1000 + i, 'dur': 1800, 'cs': 250, 'dmg': 30000, 'vis': 12, 'gold': 12000,
                    'items': [3071, 6631, 3047, 0, 0, 0, 3340], 'spells': [4, 12], 'lvl': 16, 'perk': 8010})
    return out
lcu.LCU.history = lambda self, pu, n=20: fh(n)
lcu.LCU.me = lambda self: {'riot': 'Halch#9200', 'puuid': 'P0', 'rank': None}
lcu.LCU.rank = lambda self, pu=None: {'tier': 'EMERALD', 'div': 'II', 'lp': 40}
R = lambda t, d, lp, w=120, l=101: {'tier': t, 'div': d, 'lp': lp, 'w': w, 'l': l}
HP = core.history_patterns(fh(), 'TOP')
H = {'tilt': HP[0], 'good': HP[1], 'bad': HP[2], 'n': 20, 'w': 13, 'streak': 3, 'on': 7, 'on_w': 5, 'kda': 3.4, 'tags': ['почти только на чемпионе']}
H2 = {'tilt': [], 'good': ['хорошо фармит (8.1 CS/мин)', 'KDA 4.2'], 'bad': ['мало обзора (0.4/мин)'], 'n': 20, 'w': 7, 'streak': -4, 'on': 0, 'on_w': 0, 'kda': 1.9, 'tags': ['не играл на чемпионе']}
if mode != 'game': ui.App.poll = lambda self: None

app = ui.App(lolhelper.load_data(), 'v-test', lolhelper.updater)
names = ['Halch','A2','A3','A4','A5','E1','E2','E3','E4','E5']
app.ranks = {f'{n}#EUW': R(t, 'II', 40, w, 0 if i == 6 else 101) for i, (n, t, w) in enumerate(zip(names,
             ['EMERALD','PLATINUM','EMERALD','DIAMOND','GOLD','EMERALD','MASTER','PLATINUM','EMERALD','SILVER'], [120]*6+[220]+[120]*3))}
app.hraw = {f'{n}#EUW': fh(12) for n in names}; app.pus = {f'{n}#EUW': f'{n}#EUW' for n in names}; app.hist_exp = {'Halch#EUW'}
app.hists = {f'{n}#EUW': (H if i % 2 else H2) for i, n in enumerate(names)}
def shot(name): subprocess.run(['import', '-window', 'root', f'{OUT}/{name}.png'])
if mode == 'game':
    app.root.withdraw()
    app.root.after(3000, lambda: (app.ov['hints'].push('Окно ганка 2:50–3:20: лесник взял 3 лагеря. Вард в реку'), app.ov['hints'].show()))
    app.root.after(4000, lambda: shot('n_dash'))
    def tab():
        app.dash.withdraw()
        for w in app.tab.values(): w.show(app.last_game); w.deiconify()
    app.root.after(4500, tab)
    app.root.after(5500, lambda: shot('n_tab'))
    def horiz():
        app.s['perf']['layout'] = 'horizontal'; app.s['perf']['compare'] = 'emerald'
    app.root.after(5600, horiz)
    app.root.after(7000, lambda: shot('n_tab2'))
elif mode == 'demo':
    app.root.withdraw()
    if app.dash: app.dash.withdraw()
    app.demo_on = True
    app.root.after(1500, lambda: shot('n_demo'))
else:
    sess = {'localPlayerCellId': 0, 'myTeam': [{'cellId': 0, 'assignedPosition': 'top', 'championId': 0, 'championPickIntent': 266}, {'cellId': 1, 'assignedPosition': '', 'championId': 421},
            {'cellId': 2, 'assignedPosition': 'top', 'championId': 112}, {'cellId': 3, 'assignedPosition': '', 'championId': 0}, {'cellId': 4, 'assignedPosition': '', 'championId': 497}],
            'theirTeam': [{'championId': 122}, {'championId': 64}, {'championId': 147}], 'bans': {'myTeamBans': [24]}, 'actions': [], 'timer': {}}
    cs = core.parse_champ_select(sess, app.data)
    cs['allies'] = [{'c': app.data.ids.get(str(p['championId'] or p.get('championPickIntent') or 0)), 'pos': ['TOP','JUNGLE','MIDDLE','BOTTOM','UTILITY'][p['cellId']], 'rank': R('EMERALD','III',5), 'hist': H if p['cellId'] % 2 else H2, 'me': p['cellId']==0, 'pu': f"P{p['cellId']}"} for p in sess['myTeam']]
    app.hraw = {f'P{i}': fh(12) for i in range(5)}; app.hist_exp = {'P1'}
    app.on_draft(cs)

    app.root.after(6000, lambda: shot('n_draft_dash'))
    app.root.after(6200, lambda: None)
    app.root.after(6700, lambda: shot('n_draft_panel'))
    app.s['hint_text']['crab'] = {'text': 'КРАБ! {текст}', 'say': ''}
    app.root.after(7000, lambda: (app.dash.withdraw(), app.rebuild(), app.nb.select(app.tab_hints.outer)))
    app.root.after(8000, lambda: shot('n_hints'))
    app.root.after(8200, lambda: app.hist_window(fh()[0], -18, core.review_game(GAME, 'P0', app.data)))
    app.root.after(9000, lambda: shot('n_review'))
    app.root.after(9300, lambda: app.edit_hint('crab', 'Крабы'))
    app.root.after(10000, lambda: shot('n_edit'))
app.root.after(11000, app.root.destroy)
app.run()
