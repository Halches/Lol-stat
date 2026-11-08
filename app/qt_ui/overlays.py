"""Сохранённые карточки оверлеев; окна и события мыши теперь Qt."""
import time
import core,render,performance_model
from app_config import C,WIDGETS
from qt_ui.overlay_base import Overlay

class HintsOverlay(Overlay):
    def __init__(self, app, xy):
        super().__init__(app, 'hints', xy)
        self.items = []

    def push(self, text, color='fg'):
        g = getattr(self.app, 'last_game', None)
        self.items.append((time.time(), text, color, core.mmss(g.t) if g else '')); self.items = self.items[-4:]

    def show(self, _=None):
        now = time.time()
        self.items = [i for i in self.items if now - i[0] < 14]
        if not self.items:
            if not self.unlocked: self.withdraw()
            return
        c = self.card(accent='warn', width=400)
        f = render.font('Forum', c.px(15))
        for i, (t, text, color, at) in enumerate(reversed(self.items)):
            new = i == 0
            col = (color if color != 'fg' else 'fg') if new else 'mute'
            for j, ln in enumerate(render.wrap(text, f, c.px(280))):
                lead = ('gap',2)
                c.row(lead,('cell', at if j == 0 else '', 'warn' if new else 'mute', 11, True, 38, 'l'), ('text', ln, col, 15 if new else 12, new), pad=2)
            c.rows[-1] = (c.rows[-1][0], 7)
        self.put(c)
        if not self.app.hidden and self.app.s['widgets'].get('hints'): self.deiconify()


class PerfOverlay(Overlay):
    """Показатели в игре против нормы: CS/мин, золото/мин, KDA, участие в убийствах, обзор/мин."""
    METRICS = {'csm': ('CS/мин', 1), 'gpm': ('Золото/мин', 0), 'kda': ('KDA', 1), 'kp': ('Участие, %', 0), 'vsm': ('Обзор/мин', 2)}

    def demo(self):
        c = self.card(width=0)
        c.row(('cell', '', 'mute', 9, False, 74, 'l'), ('cell', 'СЕЙЧАС', 'mute', 9, True, 56, 'r'), ('cell', 'ТЫ ОБЫЧНО', 'mute', 9, True, 64, 'r'),
              ('cell', 'АЛМАЗ', 'mute', 9, True, 64, 'r'), pad=3)
        for name, v, col, n, u in (('CS/мин', '7,4', 'good', '6,8', '7,1'), ('Золото/мин', '—', 'fg', '398', '425'), ('KDA', '3,2', 'good', '2,9', '2,7'),
                                   ('Участие, %', '48', 'fg', '52', '—'), ('Обзор/мин', '0,62', 'fg', '0,55', '—')):
            c.row(('cell', name, 'mute', 11, False, 74, 'l'), ('cell', v, col, 15, True, 56, 'r'), ('cell', n, 'fg', 12, False, 64, 'r'), ('cell', u, 'fg', 12, False, 64, 'r'), pad=3)
        self.put(c)

    def __init__(self, app, xy):
        super().__init__(app, 'perf', xy)

    def values(self, g):return performance_model.live_values(g)

    def refs(self, g):
        cfg,me=self.app.s['perf'],g.me
        if cfg['compare']=='emerald':
            lo=self.app.data.lola.get(f"{me['c']}|{g.role}")
            return performance_model.benchmark(lo),('Изумруд+ · среднее за матч' if lo else 'Изумруд+: нет данных')
        n=performance_model.personal(self.app.player,me['c'],g.role)
        return n,(f"Твой чемпион и роль · {n['n']} игр" if n.get('n') else 'Нужно 3 игры на чемпионе и роли')

    def show(self, g):
        cfg = self.app.s['perf']
        vals = self.values(g)
        on = [k for k in self.METRICS if cfg['metrics'].get(k)]
        c = self.card(width=0)
        if cfg['layout'] == 'vertical':
            app = self.app
            norm = performance_model.personal(app.player,g.me['c'],g.role)
            up = app.tier_bench(g.me['c'], g.role)
            tier = up['tier'] if up else app.next_tier()[1]
            c.row(('cell', '', 'mute', 9, False, 74, 'l'), ('cell', 'СЕЙЧАС', 'mute', 9, True, 56, 'r'), ('cell', 'ТЫ ОБЫЧНО', 'mute', 9, True, 64, 'r'),
                  ('cell', tier.upper() if tier else 'РАНГ ВЫШЕ', 'mute', 9, True, 64, 'r'), pad=3)
            for k in on:
                name, dec = self.METRICS[k]
                v, n, u = vals[k], norm.get(k), (up or {}).get(k)
                ref = u if u is not None else n
                col = 'fg' if ref is None or v is None else 'good' if v >= ref else 'warn'
                f = lambda x: '—' if x is None else f'{x:.{dec}f}'.replace('.', ',')
                c.row(('cell', name, 'mute', 11, False, 74, 'l'), ('cell', f(v), col, 15, True, 56, 'r'), ('cell', f(n), 'fg', 12, False, 64, 'r'),
                      ('cell', f(u), 'fg', 12, False, 64, 'r'), pad=3)
        else:
            ref, title = self.refs(g)
            segs = []
            for k in on:
                name, dec = self.METRICS[k]
                v, r = vals[k], ref.get(k)
                col = 'fg' if r is None or v is None else 'good' if v >= r else 'warn'
                segs += [('text', name, 'mute', 10, False), ('text', '—' if v is None else f'{v:.{dec}f}', col, 12, True)]
                if r: segs.append(('text', f'/{r:.{dec}f}', 'mute', 10, False))
                segs.append(('gap', 8))
            c.row(*segs)
        self.put(c)


class LaneOverlay(Overlay):
    def __init__(self, app, xy):
        super().__init__(app, 'lane', xy)

    def show(self, g):
        if not g.opp: self.put(self.card().row(('text', 'Оппонент не определён', 'mute', 11, False))); return
        self.draw(g.opp,g.me,g.lane_diff())

    def draw(self,o,me,delta):
        col = 'blue' if delta>0 else 'red' if delta<0 else 'mute'
        c = self.card()
        icon = self.app.pimg('champ', o['c'], 1.0, gray=o['dead'])
        value=render.Card(C,'Forum',self.app.s['scale']/100,plate=False)
        value.row(('text',f'{delta:+.0f}',render.OVERLAY[col],24,True))
        value.row(('text','против '+self.app.data.cn(o['c']),render.OVERLAY['fg'],11,False))
        segs = ([('img', icon)] if icon else []) + [('img',value.render())]
        c.row(*segs)
        c.row(('text', f"ур. {me['lvl']} / {o['lvl']} · CS {me['cs']} / {o['cs']} · {o['k']}/{o['d']}/{o['a']}", 'mute', 10, False))
        self.put(c)

    def demo(self):
        self.draw({'c':'Viktor','dead':False,'lvl':10,'cs':80,'k':2,'d':3,'a':1},
                  {'lvl':11,'cs':92},850)


class InventoryOverlay(Overlay):
    """Общий рейтинг чемпионов: стоимость предметов, а не заработанное/наличное золото."""
    def __init__(self, app, xy):
        super().__init__(app, 'inventory', xy)

    def show(self, g):
        self.draw(core.inventory_ranking(g.players), g.my_team, g.me)

    def draw(self, players, my_team, me):
        c = self.card()
        for rank, p in enumerate(players, 1):
            color = 'blue' if p['team'] == my_team else 'red'
            icon = self.app.pimg('champ', p['c'], .65, gray=p.get('dead',False))
            segs = [('cell',str(rank),'mute',10,False,16,'r')]
            if icon: segs.append(('img',icon))
            segs += [('cell',self.app.data.cn(p['c']),'fg',11,p is me,120,'l'),
                     ('bar',p['igold']/max(1,players[0]['igold']),color,'deep',36),
                     ('cell',f"{p['igold']:,.0f}".replace(',',' '),'fg',13,True,62,'r')]
            c.row(*segs,pad=3,tint=color)
        if not players: c.row(('text', 'Жду данные игры…', 'mute', 11, False))
        c.row(('text', 'Без зелий, вардов и тотемов', 'mute', 9, False), pad=5)
        self.put(c)

    def demo(self):
        champs = ('Sett', 'Jinx', 'Ahri', 'Darius', 'Viktor', 'LeeSin', 'Caitlyn', 'RekSai', 'Lux', 'Rakan')
        players = [{'riot': f'P{i}', 'c': c, 'team': 'ORDER' if i % 2 == 0 else 'CHAOS',
                    'igold': gold} for i, (c, gold) in enumerate(zip(champs, (11800, 10560, 10300, 9800, 8950, 7720, 7400, 6200, 5290, 5200)))]
        self.draw(core.inventory_ranking(players), 'ORDER', players[0])


class ItemOverlay(Overlay):
    """Сколько золота до следующего предмета из твоей лучшей сборки."""
    def __init__(self, app, xy):
        super().__init__(app, 'item', xy)

    def show(self, g):
        plan = core.next_item_plan(self.app.data, self.app.player, g.me['c'], g.me['items'], g.gold)
        d = self.app.data
        if not plan:
            self.put(self.card().row(('text', 'Сборка готова или нет данных', 'mute', 11, False))); return
        self.draw_plan(plan)

    def draw_plan(self,plan):
        d=self.app.data
        it, cp = self.app.pimg('item', plan['item'], 1.0), self.app.pimg('item', plan['comp'], .8)
        c = self.card()
        if plan['comp_need'] == 0:
            segs = [('text', 'можно купить', 'good', 12, True)]
        else:
            segs = [('text', f"ещё {int(plan['comp_need'])}", 'gold', 24, True)]
        c.row(*(([('img', it)] if it else []) + ([('img', cp)] if cp and plan['comp'] != plan['item'] else []) + segs))
        line = d.iname(plan['comp']) if plan['comp'] == plan['item'] else f"{d.iname(plan['comp'])} → {d.iname(plan['item'])}, всего ещё {int(plan['need'])}"
        c.row(('text', line, 'mute', 10, False))
        self.put(c)

    def demo(self):
        self.draw_plan({'item':1036,'comp':1036,'comp_need':350,'need':350})


class ArenaOverlay(Overlay):
    """Арена: счёт, золото и стоимость предметов, плюс твоё среднее место на этом чемпионе. Урона и места в лобби игра во время матча не отдаёт."""
    def __init__(self, app, xy):
        super().__init__(app, 'arena', xy)

    def show(self, g):
        me = g.me
        if not me: return
        c = self.values_card(f"{me['k']}/{me['d']}/{me['a']}",int(g.gold),int(me['igold']))
        st = core.arena_stats(self.app.arena_games(), me['c'])
        if st: c.row(('text', f"на {self.app.data.cn(me['c'])}: среднее место {st['avg']:.1f} за {st['n']} игр".replace('.', ','), 'mute', 10, False))
        self.put(c)

    def demo(self):
        self.put(self.values_card('7/3/5',1350,6200))

    def values_card(self,kda,gold,inventory):
        c=self.card()
        c.row(('cell',kda,'fg',22,True,82,'r'),
              ('cell',f'{gold:,}'.replace(',',' '),'gold',22,True,82,'r'),
              ('cell',f'{inventory:,}'.replace(',',' '),'fg',22,True,82,'r'))
        c.row(('cell','счёт','mute',10,False,82,'r'),
              ('cell','золото','mute',10,False,82,'r'),
              ('cell','в предметах','mute',10,False,82,'r'))
        return c


class TimersOverlay(Overlay):
    def __init__(self, app, xy):
        super().__init__(app, 'timers', xy)

    def show(self, g):
        ob, t = g.objectives(), g.t
        rows = []
        if g.role == 'JUNGLE' and t < core.OBJ['crab']: rows.append(('Крабы', core.OBJ['crab'] - t))
        for key, name in (('dragon', ob.get('dragon_name', 'Дракон')), ('grubs', 'Личинки'), ('herald', 'Герольд'), ('baron', 'Барон')):
            if ob.get(key) is not None: rows.append((name, ob[key] - t))
        nc = g.next_cannon()
        self.draw(rows, nc - t if nc else None)

    def draw(self, rows, cannon=None):
        c = self.card()
        for name, left in rows:
            soon = 0 < left <= 60
            icon = render.objective_icon(name,c.px(24))
            c.row(('img',icon) if icon else ('gap',24),('cell', name, 'fg' if left > 0 else 'mute', 11, False, 110, 'l'),
                  ('cell', core.mmss(left) if left > 0 else 'на карте', 'gold' if soon else 'fg' if left > 0 else 'good', 12, True, 62, 'r'))
        if cannon: c.row(('cell', 'Осадный миньон', 'mute', 10, False, 110, 'l'), ('cell', core.mmss(cannon), 'mute', 11, True, 62, 'r'))
        self.put(c)

    def demo(self):
        self.draw([('Адский дракон', 45), ('Личинки', -1), ('Барон', 412)], 38)
