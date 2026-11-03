"""Native draft dashboard using the existing application data and import controls."""
import tkinter as tk
from tkinter import ttk
import core
import draft_model


class DraftView:
    def __init__(self, dashboard, cs, result, bans, me, full, colors, fonts):
        self.w, self.app = dashboard, dashboard.app
        self.cs, self.r, self.bans, self.me, self.full = cs, result, bans, me, full
        self.c, self.f = colors, fonts
        self.fs, self.d = self.app.fs, self.app.data
        self.width = max(220, int((dashboard.winfo_width() - 90) / 3))
        if not hasattr(dashboard, '_draft_open'): dashboard._draft_open = set()

    def label(self, parent, text='', color='fg', size=10, bold=False, **kw):
        return tk.Label(parent, text=text, bg=parent.cget('bg'), fg=self.c[color],
                        font=(self.f['font'], self.fs(size), 'bold' if bold else 'normal'), **kw)

    def image(self, parent, group, key, size=24):
        im = self.app.icons.get(group, key, self.fs(size))
        if im:
            label = self.label(parent, image=im)
            label.pack(side='left', padx=(0, 4))
        return im

    def box(self, parent, title=None, accent=None):
        frame = tk.Frame(parent, bg=self.c['panel'], padx=self.fs(10), pady=self.fs(8),
                         highlightthickness=1, highlightbackground=self.c[accent or 'line'])
        frame.pack(fill='x', pady=(0, self.fs(7)))
        if title: self.label(frame, title, 'gold', 11, True).pack(anchor='w', pady=(0, 5))
        return frame

    def fold(self, parent, title, key, draw, compact=False):
        if compact:
            wrapper = tk.Frame(parent, bg=parent.cget('bg'))
            wrapper.pack(fill='x', pady=(2, 0))
        else:
            wrapper = self.box(parent)
        body = tk.Frame(wrapper, bg=self.c['panel'])
        button = self.label(wrapper, size=8, color='mute', cursor='hand2') if compact else ttk.Button(wrapper)
        button.pack(anchor='w' if compact else 'center', fill=None if compact else 'x')
        built = False
        def show():
            nonlocal built
            on = key in self.w._draft_open
            button.configure(text=('▾ ' if on else '▸ ') + title)
            if on:
                if not built: draw(body); built = True
                body.pack(fill='x', pady=(6, 0))
            else: body.pack_forget()
        def toggle():
            self.w._draft_open.symmetric_difference_update({key})
            show()
        if compact: button.bind('<Button-1>', lambda event: toggle())
        else: button.configure(command=toggle)
        show()
        return wrapper

    def toolbar(self):
        for child in self.w.bar.winfo_children(): child.destroy()
        frame = tk.Frame(self.w.bar, bg=self.c['deep'], padx=10, pady=7)
        frame.pack(fill='x')
        left = tk.Frame(frame, bg=self.c['deep']); left.pack(side='left')
        for rr in core.ROLES:
            im = self.app.icons.get('role', rr, self.fs(17))
            ttk.Button(left, text=' ' + core.ROLE_RU[rr].capitalize(), image=im or '', compound='left',
                       style='A.TButton' if rr == self.r['role'] else 'TButton',
                       command=lambda rr=rr: self.app.set_draft_role(rr)).pack(side='left', padx=(0, 3))
        right = tk.Frame(frame, bg=self.c['deep']); right.pack(side='right')
        for key, text in (('pool', 'Мой пул'), ('all', 'Все чемпионы')):
            ttk.Button(right, text=text, style='A.TButton' if self.app.s['draft_scope'] == key else 'TButton',
                       command=lambda key=key: self.app.set_draft_scope(key)).pack(side='left', padx=3)
        self.w.head.configure(text='Подготовка к матчу' if self.cs.get('locked') else 'Выбор чемпиона')
        self.w.sub.configure(text='Пары: Lolalytics · Изумруд+ · все регионы · проценты по выборке, а не прогноз победы')

    def pair_rows(self, champion, lane, enemy):
        kind = 'counter' if enemy else 'build-team'
        raw = self.app.lola_fetch(kind, champion, lane)
        cnt = core.lola_counters(raw, self.d) if enemy else {}
        team = {} if enemy else core.lola_team(raw, self.d)
        pools = self.app.player.pool if self.app.player else {}
        return draft_model.recommendations(self.d, champion, lane, 'enemy' if enemy else 'ally',
                                           self.r['role'], cnt, team, pools,
                                           self.app.s['draft_scope'], self.cs['unavailable'], limit=20)

    def player(self, parent, player, enemy=False):
        ch, lane = player.get('c'), player.get('pos')
        mine = player.get('me')
        card = self.box(parent, accent='gold' if mine else None)
        if not ch:
            self.label(card, 'Ожидание выбора', 'mute', 11).pack(anchor='w')
            return
        head = tk.Frame(card, bg=self.c['panel']); head.pack(fill='x')
        self.image(head, 'champ', ch, 40)
        name = tk.Frame(head, bg=self.c['panel']); name.pack(side='left', fill='x', expand=True)
        rl = tk.Frame(name, bg=self.c['panel']); rl.pack(anchor='w')
        self.label(rl, self.d.cn(ch) + (' · ты' if mine else ''), 'blue2' if not enemy else 'red2', 12, True).pack(side='left', padx=(0, 7))
        self.image(rl, 'role', lane, 16)
        self.label(rl, core.ROLE_RU.get(lane, 'Роль неизвестна').capitalize(), 'mute', 9).pack(side='left')
        rank = player.get('rank')
        if rank and self.app.s['show']['ranks']:
            rr = tk.Frame(head, bg=self.c['panel']); rr.pack(side='right')
            # Local import avoids depending on UI globals in the presentation model.
            from ui import TIER_RU, rank_short
            self.image(rr, 'emb', TIER_RU.get(rank['tier']), 30)
            self.label(rr, rank_short(rank), 'mute', 8).pack(side='left')
        history = player.get('hist')
        if history:
            from ui import hist_tags
            summary, _ = hist_tags(history)
            self.label(name, summary, 'mute', 8, wraplength=max(150, self.width-190), justify='left').pack(anchor='w')
            traits = tk.Frame(card, bg=self.c['panel']); traits.pack(fill='x', pady=(2, 0))
            column = 0
            for field, prefix, color in (('good', 'Силен: ', 'good2'), ('bad', 'Слаб: ', 'bad2'), ('tilt', 'Последние игры: ', 'warn')):
                values = history.get(field) or []
                if values:
                    traits.columnconfigure(column % 2, weight=1, uniform='trait')
                    self.label(traits, prefix + '; '.join(values[:2]), color, 8,
                               wraplength=max(120, (self.width-40)//2), justify='left').grid(row=0 if column < 2 else 1, column=column % 2, sticky='nw')
                    column += 1
        else:
            self.label(name, 'История игрока недоступна', 'mute', 8).pack(anchor='w')
        if not mine and lane:
            rows = self.pair_rows(ch, lane, enemy)
            if rows:
                self.label(card, 'Контрпики' if enemy else 'Рекомендуемые сочетания', 'mute', 8).pack(anchor='w', pady=(4, 1))
                self.draw_recommendations(card, rows[:3])
                if len(rows) > 3:
                    self.fold(card, f'Ещё варианты ({len(rows)-3})', ('pairs', enemy, ch),
                              lambda box: self.draw_recommendations(box, rows[3:]))
            else:
                key = ('counter' if enemy else 'build-team', ch, lane)
                state = self.app.lola_state.get(key)
                text = 'Загрузка статистики пар…' if state == 'loading' else ('Нет подходящих пар в пуле' if self.app.s['draft_scope'] == 'pool' else 'Нет подтверждённой статистики пар')
                self.label(card, text, 'mute', 8).pack(anchor='w', pady=(4, 0))
        pu = player.get('pu')
        if pu:
            def history_details(box):
                from ui import hist_tags
                _, tags = hist_tags(history)
                self.w.chips(box, tags, self.c['panel'])
                self.w.mini_hist(box, pu, n=5)
            self.fold(card, 'Последние матчи', ('history', pu), history_details, compact=True)

    def draw_recommendations(self, parent, rows):
        row = None
        for i, recommendation in enumerate(rows):
            if i % 3 == 0:
                row = tk.Frame(parent, bg=parent.cget('bg')); row.pack(fill='x', pady=2)
                for column in range(3): row.columnconfigure(column, weight=1, uniform='recommendation')
            tile = tk.Frame(row, bg=self.c['deep'], padx=3, pady=3)
            tile.grid(row=0, column=i % 3, sticky='nsew', padx=(0, 3))
            top = tk.Frame(tile, bg=self.c['deep']); top.pack(anchor='w')
            self.image(top, 'champ', recommendation['champion'], 20)
            self.image(top, 'role', recommendation['role'], 15)
            wr = f"{recommendation['winrate']:.1f}%".replace('.', ',')
            self.label(top, wr, 'good2', 9, True).pack(side='left')
            count = f"{recommendation['games']:,} игр".replace(',', ' ')
            self.label(tile, self.d.cn(recommendation['champion']) + ' · ' + count, 'mute', 8).pack(anchor='w')

    def top_picks(self):
        box = self.box(self.w.mid, 'Лучшие пики для тебя')
        if not self.r['picks']:
            self.label(box, 'Нет доступных рекомендаций. Проверь пул и роль.', 'mute', 10,
                       wraplength=max(120, self.width-28)).pack(anchor='w')
        for pick in self.r['picks'][:3]:
            row = tk.Frame(box, bg=self.c['panel']); row.pack(fill='x', pady=4)
            self.image(row, 'champ', pick['c'], 30)
            self.image(row, 'role', self.r['role'], 18)
            label = self.label(row, pick['name'], 'gold', 11, True); label.pack(side='left')
            self.label(box, pick['why'], 'mute', 9, wraplength=max(120, self.width-32), justify='left').pack(anchor='w')

    def set_auto(self, enabled):
        self.app.s['auto_import'] = enabled
        if enabled and not any(self.app.s['auto_parts'].values()):
            self.app.s['auto_parts'].update(runes=True, items=True)
            for key in ('runes', 'items'): self.app.auto_vars[key].set(True)
        self.app.s.save()
        self.app.draft_sig = self.w.draft_sig = None
        if self.app.draft: self.app.on_draft(self.app.draft)

    def build_table(self):
        box = self.box(self.w.mid, 'Руны и сборки · ' + self.d.cn(self.me))
        mode = tk.Frame(box, bg=self.c['panel']); mode.pack(fill='x')
        for enabled, text in ((True, 'Автоэкспорт'), (False, 'Вручную')):
            ttk.Button(mode, text=text, style='A.TButton' if self.app.s['auto_import'] == enabled else 'TButton',
                       command=lambda enabled=enabled: self.set_auto(enabled)).pack(side='left', padx=(0, 4))
        ttk.Button(mode, text='Экспорт', command=lambda: self.app.do_import(tuple(key for key, value in self.app.s['auto_parts'].items() if value))).pack(side='right')
        parts = tk.Frame(box, bg=self.c['panel']); parts.pack(fill='x', pady=4)
        for key, text in (('runes', 'Руны'), ('items', 'Предметы'), ('spells', 'Заклинания')):
            ttk.Checkbutton(parts, text=text, variable=self.app.auto_vars[key],
                            command=lambda key=key: self.app.set_import_part(key)).pack(side='left')
        options = draft_model.build_options(self.full)
        for option in options:
            variant, key = option['variant'], option['key']
            row = tk.Frame(box, bg=self.c['raise'] if self.app.s['rune_pick'] == key else self.c['deep'], padx=5, pady=5)
            row.pack(fill='x', pady=2)
            narrow = self.width < self.fs(480)
            ttk.Button(row, text=option['title'], width=12, command=lambda key=key: self.app.set_rune_pick(key)).pack(side='top' if narrow else 'left', anchor='w', padx=(0, 5))
            runes = tk.Frame(row, bg=row.cget('bg')); runes.pack(side='top' if narrow else 'left', anchor='w')
            for rid in variant.get('perks', [])[:6]: self.image(runes, 'rune', rid, 18)
            items = tk.Frame(row, bg=row.cget('bg')); items.pack(side='top' if narrow else 'left', anchor='w')
            if not narrow: self.label(items, ' → ', 'mute', 9).pack(side='left')
            for item in core.lola_build_items(variant)[:6]: self.image(items, 'item', item, 20)
        if not options:
            self.label(box, 'Загрузка сборок…' if self.app.lola_state.get((self.me, self.r['role'])) == 'loading' else 'Источник сборок недоступен', 'mute', 9).pack(anchor='w')
        self.label(box, 'Винрейт общей связки: нет подтверждённой выборки', 'mute', 8).pack(anchor='w', pady=(4, 0))
        # Unsupported groups stay visible without inventing source data.
        for title in ('Оффметовые', 'От мейнеров · до 3', 'От профессионалов · до 3'):
            self.label(box, title + ' — источник не подключён', 'mute', 8).pack(anchor='w', pady=1)
        self.w.import_lbl = self.label(box, self.app.import_text, 'mute', 9,
                                       wraplength=max(120, self.width-32), justify='left')
        self.w.import_lbl.pack(anchor='w', pady=(4, 0))
        self.w.import_err = ttk.Button(box, text='Скопировать отчёт об импорте', command=self.app.copy_report)
        if 'не получилось' in self.app.import_text: self.w.import_err.pack(anchor='w')
        def details(parent):
            variant = (self.full or {}).get(self.app.s['rune_pick']) or self.full or {}
            self.label(parent, 'Заклинания и ветки рун', 'mute', 9).pack(anchor='w')
            row = tk.Frame(parent, bg=self.c['panel']); row.pack(anchor='w')
            for spell in variant.get('spells', [])[:2]:
                self.image(row, 'spell', spell, 22)
                self.label(row, core.SPELL_RU.get(spell, spell), 'fg', 8).pack(side='left', padx=(0, 6))
            row = tk.Frame(parent, bg=self.c['panel']); row.pack(anchor='w', pady=3)
            for rune in [variant.get('prim'), variant.get('sec')] + variant.get('shards', []):
                self.image(row, 'rune', rune, 22)
            self.label(parent, 'Старт', 'mute', 9).pack(anchor='w')
            row = tk.Frame(parent, bg=self.c['panel']); row.pack(anchor='w')
            for item in variant.get('start', []): self.image(row, 'item', item, 24)
            for name, wr, n in (('Руны', variant.get('wr_runes'), variant.get('n_runes')),
                                ('Основа предметов', variant.get('wr_core'), variant.get('n_core'))):
                if wr is not None and n is not None:
                    self.label(parent, f'{name}: {wr:.1f}% · {n} игр (отдельная выборка)', 'mute', 9).pack(anchor='w')
            self.label(parent, 'Lolalytics · EUW · Изумруд+' + (f" · {self.full['games']} игр на чемпионе" if self.full and self.full.get('games') else ''),
                       'mute', 8, wraplength=max(120, self.width-32)).pack(anchor='w')
            self.label(parent, 'Прокачка: ' + ' › '.join(variant.get('skill_prio') or ''), 'gold', 9).pack(anchor='w', pady=4)
            skills = variant.get('skills') or ''
            for offset in range(0, len(skills), 9):
                self.label(parent, '  '.join(f'{i+1}:{skill}' for i, skill in enumerate(skills) if offset <= i < offset+9), 'fg', 9).pack(anchor='w')
            for item, short, when in (self.full or {}).get('situ', []):
                row = tk.Frame(parent, bg=self.c['panel']); row.pack(fill='x', pady=2)
                self.image(row, 'item', item, 22)
                self.label(row, short + ': ' + when, 'mute', 9, wraplength=max(120, self.width-65), justify='left').pack(side='left')
        self.fold(self.w.mid, 'Разбор сборки · руны, старт и умения', 'build-details', details)

    def draw(self):
        for col in self.w.cols + [self.w.mid]:
            for child in col.winfo_children(): child.destroy()
        self.toolbar()
        for parent, text, color in ((self.w.cols[0], 'Союзники', 'blue2'), (self.w.cols[1], 'Противники', 'red2')):
            self.label(parent, text, color, 13, True).pack(anchor='w', pady=(0, 7))
        order = {rr: i for i, rr in enumerate(core.ROLES)}
        allies = sorted(self.cs.get('allies') or [], key=lambda a: order.get(a.get('pos'), 9))
        enemies = sorted(({'c': c, 'pos': self.r['roles'].get(c, '')} for c in self.cs['enemies']), key=lambda a: order.get(a['pos'], 9))
        for column, players in enumerate((allies, enemies)):
            for player in players: self.player(self.w.cols[column], player, column == 1)
            for _ in range(max(0, 5-len(players))): self.player(self.w.cols[column], {}, column == 1)
        if self.me and self.cs.get('locked'): self.build_table()
        else: self.top_picks()
        self.w.matchup_card(self.me, self.r)
        self.fold(self.w.mid, 'Композиции · сильные и слабые стороны', 'composition',
                  lambda body: self.draw_composition(body, allies))
        self.fold(self.w.mid, 'Кого банить', 'bans', self.draw_bans)
        if self.me and not self.cs.get('locked'):
            self.fold(self.w.mid, 'Предварительная сборка', 'preview-build', lambda body: self.w.build_box(body, self.me, self.full, self.r['role']))

    def draw_composition(self, parent, allies):
        original = self.w.mid
        try:
            self.w.mid = parent
            self.w.comp_card(self.cs, self.r, allies)
        finally:
            self.w.mid = original

    def draw_bans(self, parent):
        for ch, _, why in self.bans or []:
            row = tk.Frame(parent, bg=self.c['panel']); row.pack(fill='x', pady=3)
            self.image(row, 'champ', ch, 28)
            self.label(row, self.d.cn(ch) + ' · ' + why, 'mute', 9,
                       wraplength=max(120, self.width-65), justify='left').pack(side='left')
        if not self.bans: self.label(parent, 'Нет данных для персональных банов', 'mute', 9).pack(anchor='w')


def render_draft(dashboard, cs, result, bans, me, full, colors, fonts):
    DraftView(dashboard, cs, result, bans, me, full, colors, fonts).draw()
