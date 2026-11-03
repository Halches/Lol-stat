"""Native draft dashboard using the existing application data and import controls."""
import tkinter as tk
from tkinter import ttk
import core
import draft_model


class RoundedPanel(tk.Frame):
    """Theme-aware native panel with the outline and corners of the approved preview."""
    def __init__(self, parent, fill, outline, padding, radius=7):
        super().__init__(parent, bg=parent.cget('bg'))
        self.canvas = tk.Canvas(self, bg=parent.cget('bg'), highlightthickness=0, bd=0)
        self.canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.body = tk.Frame(self, bg=fill)
        self.vpad = padding
        self.body.pack(fill='both', expand=True, padx=padding, pady=padding)
        self.body._panel = self
        def paint(event):
            w, h, r = event.width-1, event.height-1, radius
            self.canvas.delete('panel')
            self.canvas.create_polygon(r, 1, w-r, 1, w, 1, w, r, w, h-r, w, h,
                w-r, h, r, h, 1, h, 1, h-r, 1, r, 1, 1,
                fill=fill, outline=outline, smooth=True, splinesteps=24, tags='panel')
        self.bind('<Configure>', paint)


class DraftView:
    def __init__(self, dashboard, cs, result, bans, me, full, colors, fonts):
        self.w, self.app = dashboard, dashboard.app
        self.cs, self.r, self.bans, self.me, self.full = cs, result, bans, me, full
        self.c, self.f = dict(colors), fonts
        if self.app.s['theme'] == 'lol':
            self.c.update(bg='#08121e', deep='#0b1724', panel='#102132',
                          raise_='#172d40', line='#2b4053', fg='#eee9df', mute='#a8b8c8',
                          gold='#d9bc7e', blue2='#80c6fc', red2='#f49394',
                          good2='#78d8b8', bad2='#f49394', tag_g='#11362f', tag_r='#39252e')
            self.c['raise'] = self.c.pop('raise_')
        self.player_cards = []
        self.wrapped_labels = []
        self._size_job = None
        self._resize_job = None
        self.fs, self.d = self.app.fs, self.app.data
        self.width = max(220, int((dashboard.winfo_width() - 90) / 3))
        if not hasattr(dashboard, '_draft_open'): dashboard._draft_open = set()

    def label(self, parent, text='', color='fg', size=10, bold=False, **kw):
        label = tk.Label(parent, text=text, bg=parent.cget('bg'), fg=self.c[color],
                         font=(self.f['font'], self.fs(size), 'bold' if bold else 'normal'), **kw)
        if kw.get('wraplength'): self.wrapped_labels.append((label, kw['wraplength']/self.width))
        return label

    def image(self, parent, group, key, size=24):
        im = self.app.icons.get(group, key, self.fs(size))
        if im:
            label = self.label(parent, image=im)
            label.pack(side='left', padx=(0, 4))
        return im

    def box(self, parent, title=None, accent=None):
        panel = RoundedPanel(parent, self.c['panel'], self.c[accent or 'line'], self.fs(10), self.fs(7))
        panel.pack(fill='x', pady=(0, self.fs(8)))
        if title: self.label(panel.body, title, 'fg', 11, True).pack(anchor='w', pady=(0, 8))
        return panel.body

    def schedule_sizes(self, event=None):
        if self._size_job is None and not getattr(self, '_sizing', False):
            self._size_job = self.w.after_idle(self.sync_card_sizes)

    def sync_card_sizes(self):
        self._size_job = None
        if getattr(self.w, '_draft_view', None) is not self: return
        cards = [card for card in self.player_cards if card.winfo_exists()]
        if not cards: return
        self._sizing = True
        self.w.update_idletasks()
        width = min(col.winfo_width() for col in self.w.cols)
        if abs(width-self.width) > 24 and self._resize_job is None:
            def redraw():
                if getattr(self.w, '_draft_view', None) is self and self.w.mode == 'draft':
                    render_draft(self.w, self.cs, self.r, self.bans, self.me, self.full, self.c, self.f)
            self._resize_job = self.w.after(150, redraw)
        for label, ratio in self.wrapped_labels:
            if label.winfo_exists(): label.configure(wraplength=max(70, round(width*ratio)))
        self.w.update_idletasks()
        height = max(card.body.winfo_reqheight() + 2*card.vpad for card in cards)
        for card in cards:
            if (int(card.cget('height')), int(card.cget('width'))) != (height, width):
                card.configure(height=height, width=width)
            card.pack_configure(fill='none', anchor='w')
            card.pack_propagate(False)
        self._sizing = False

    def styles(self):
        style = ttk.Style(self.w)
        style.configure('Draft.TCheckbutton', background=self.c['panel'], foreground=self.c['mute'],
                        font=(self.f['font'], self.fs(8)))
        style.map('Draft.TCheckbutton', background=[('active', self.c['panel'])],
                  foreground=[('active', self.c['fg'])])
        style.configure('DraftLink.TButton', background=self.c['panel'], foreground=self.c['mute'],
                        bordercolor=self.c['panel'], lightcolor=self.c['panel'], darkcolor=self.c['panel'],
                        padding=0, borderwidth=0, relief='flat', anchor='w',
                        font=(self.f['font'], self.fs(8)))
        style.map('DraftLink.TButton', background=[('active', self.c['panel'])],
                  foreground=[('active', self.c['gold'])], bordercolor=[('active', self.c['panel'])])
        for name, bg, fg, border in (
                ('Draft.TButton', self.c['deep'], self.c['fg'], self.c['line']),
                ('DraftActive.TButton', self.c['raise'], self.c['gold'], self.c['gold']),
                ('DraftPrimary.TButton', self.c['gold'], self.c['on_gold'], self.c['gold'])):
            style.configure(name, background=bg, foreground=fg, bordercolor=border,
                lightcolor=bg, darkcolor=bg, padding=(self.fs(9), self.fs(6)),
                font=(self.f['font'], self.fs(9)), relief='flat')
            style.map(name, background=[('active', self.c['raise'])],
                foreground=[('active', self.c['fg'])], bordercolor=[('active', self.c['gold'])])

    def fold(self, parent, title, key, draw, compact=False):
        if compact:
            wrapper = tk.Frame(parent, bg=parent.cget('bg'))
            wrapper.pack(fill='x', pady=(2, 0))
        else:
            wrapper = self.box(parent)
        body = tk.Frame(wrapper, bg=self.c['panel'])
        button = ttk.Button(wrapper, style='DraftLink.TButton' if compact else 'Draft.TButton')
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
            self.schedule_sizes()
        def toggle():
            self.w._draft_open.symmetric_difference_update({key})
            show()
        button.configure(command=toggle)
        show()
        return wrapper

    def toolbar(self):
        for child in self.w.bar.winfo_children(): child.destroy()
        frame = tk.Frame(self.w.bar, bg=self.c['bg'], padx=0, pady=3)
        frame.pack(fill='x')
        left = tk.Frame(frame, bg=self.c['bg']); left.pack(side='left')
        for rr in core.ROLES:
            im = self.app.icons.get('role', rr, self.fs(17))
            ttk.Button(left, text=' ' + core.ROLE_RU[rr].capitalize(), image=im or '', compound='left',
                       style='DraftActive.TButton' if rr == self.r['role'] else 'Draft.TButton',
                       command=lambda rr=rr: self.app.set_draft_role(rr)).pack(side='left', padx=(0, 3))
        right = tk.Frame(frame, bg=self.c['bg']); right.pack(side='right')
        for key, text in (('pool', 'Мой пул'), ('all', 'Все чемпионы')):
            ttk.Button(right, text=text, style='DraftActive.TButton' if self.app.s['draft_scope'] == key else 'Draft.TButton',
                       command=lambda key=key: self.app.set_draft_scope(key)).pack(side='left', padx=3)
        tk.Label.configure(self.w.head, text='Подготовка к матчу' if self.cs.get('locked') else 'Выбор чемпиона',
                           font=(self.f['font'], self.fs(22)), fg=self.c['fg'], bg=self.c['bg'])
        self.w.configure(bg=self.c['bg'])
        self.w.timer.configure(bg=self.c['bg'], fg=self.c['gold'])
        for surface in [self.w.sub, self.w.body, self.w.cv, self.w.wrap, self.w.bar, *self.w.cols, self.w.mid]:
            surface.configure(bg=self.c['bg'])
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
        card._panel.vpad = self.fs(7)
        card.pack_configure(pady=card._panel.vpad)
        self.player_cards.append(card._panel)
        card.bind('<Configure>', self.schedule_sizes)
        if not ch:
            row = tk.Frame(card, bg=self.c['panel']); row.pack(anchor='w')
            self.image(row, 'role', lane, 22)
            self.label(row, core.ROLE_RU.get(lane, 'Роль неизвестна').capitalize(), 'mute', 10).pack(side='left')
            self.label(card, 'Ожидание выбора', 'mute', 11).pack(anchor='w', pady=6)
            return
        head = tk.Frame(card, bg=self.c['panel']); head.pack(fill='x')
        self.image(head, 'champ', ch, 40)
        name = tk.Frame(head, bg=self.c['panel']); name.pack(side='left', fill='x', expand=True)
        self.label(name, self.d.cn(ch) + (' · ты' if mine else ''), 'gold' if mine else 'fg', 12).pack(anchor='w')
        rl = tk.Frame(name, bg=self.c['panel']); rl.pack(anchor='w')
        self.image(rl, 'role', lane, 16)
        self.label(rl, core.ROLE_RU.get(lane, 'Роль неизвестна').capitalize(), 'mute', 9).pack(side='left')
        rank = player.get('rank')
        if rank and self.app.s['show']['ranks']:
            rr = tk.Frame(head, bg=self.c['panel']); rr.pack(side='right')
            # Local import avoids depending on UI globals in the presentation model.
            from ui import TIER_RU
            self.image(rr, 'emb', TIER_RU.get(rank['tier']), 30)
            self.label(rr, TIER_RU.get(rank['tier'], rank['tier']) + ' ' + rank.get('div',''), 'mute', 8).pack(side='left')
        history = player.get('hist')
        if history:
            from ui import hist_tags
            summary, _ = hist_tags(history)
            self.label(card, summary, 'mute', 8, wraplength=max(150, self.width-32), justify='left').pack(anchor='w', pady=(3, 2))
            traits = tk.Frame(card, bg=self.c['panel']); traits.pack(fill='x', pady=(2, 0))
            column = 0
            for field, prefix, color in (('good', 'Силен: ', 'good2'), ('bad', 'Слаб: ', 'bad2'), ('tilt', 'Последние игры: ', 'warn')):
                values = history.get(field) or []
                if values:
                    traits.columnconfigure(column % 2, weight=1, uniform='trait')
                    trait = self.label(traits, prefix + '; '.join(values[:2]), color, 8,
                               wraplength=max(120, (self.width-48)//2), justify='left', anchor='w', padx=5, pady=2)
                    trait.configure(bg=self.c['tag_g' if field == 'good' else 'tag_r' if field == 'bad' else 'raise'])
                    trait.grid(row=0 if column < 2 else 1, column=column % 2, sticky='nsew', padx=(0, 4))
                    column += 1
        else:
            self.label(card, 'История игрока недоступна', 'mute', 8).pack(anchor='w', pady=(3, 2))
        if not mine and lane:
            rows = self.pair_rows(ch, lane, enemy)
            if rows:
                self.draw_recommendations(card, rows[:3])
                if len(rows) > 3:
                    self.fold(card, f'Ещё варианты ({len(rows)-3})', ('pairs', enemy, ch),
                              lambda box: self.draw_recommendations(box, rows[3:]))
            else:
                key = ('counter' if enemy else 'build-team', ch, lane)
                state = self.app.lola_state.get(key)
                text = 'Загрузка статистики пар…' if state == 'loading' else ('Нет подходящих пар в пуле' if self.app.s['draft_scope'] == 'pool' else 'Нет подтверждённой статистики пар')
                self.label(card, text, 'mute', 8).pack(anchor='w', pady=(4, 0))
        if mine:
            selected = (self.full or {}).get(self.app.s['rune_pick']) or self.full or {}
            row = tk.Frame(card, bg=self.c['panel']); row.pack(anchor='w', pady=(4, 0))
            for spell in selected.get('spells', [])[:2]: self.image(row, 'spell', spell, 20)
            if selected.get('perks'): self.image(row, 'rune', selected['perks'][0], 20)
            self.label(row, 'Пик подтверждён' if self.cs.get('locked') else 'Предварительный выбор', 'mute', 8).pack(side='left')
        pu = player.get('pu')
        if pu:
            def history_details(box):
                from ui import hist_tags, rank_short
                if rank: self.label(box, rank_short(rank), 'mute', 8).pack(anchor='w')
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
            narrow = self.width < self.fs(540)
            if not narrow: self.label(top, self.d.cn(recommendation['champion']), 'fg', 8).pack(side='left', padx=(0, 4))
            self.image(top, 'role', recommendation['role'], 14)
            wr = f"{recommendation['winrate']:.1f}%".replace('.', ',')
            self.label(top, wr, 'good2', 9, True).pack(side='left')
            count = f"{recommendation['games']:,} игр".replace(',', ' ')
            self.label(tile, (self.d.cn(recommendation['champion'])+' · ' if narrow else '') + count, 'mute', 7).pack(anchor='w')

    def top_picks(self):
        box = self.box(self.w.mid, 'Лучшие пики для тебя')
        if not self.r['picks']:
            self.label(box, 'Нет доступных рекомендаций. Проверь пул и роль.', 'mute', 10,
                       wraplength=max(120, self.width-28)).pack(anchor='w')
        row = tk.Frame(box, bg=self.c['panel']); row.pack(fill='x')
        for i, pick in enumerate(self.r['picks'][:3]):
            row.columnconfigure(i, weight=1, uniform='pick')
            tile = tk.Frame(row, bg=self.c['deep'], padx=8, pady=8,
                            highlightthickness=1, highlightbackground=self.c['gold' if i == 0 else 'line'])
            tile.grid(row=0, column=i, sticky='nsew', padx=(0, 5))
            portrait = tk.Frame(tile, bg=self.c['deep']); portrait.pack(anchor='w')
            self.image(portrait, 'champ', pick['c'], 42)
            self.label(tile, pick['name'], 'gold' if i == 0 else 'fg', 11).pack(anchor='w', pady=(4, 0))
            role = tk.Frame(tile, bg=self.c['deep']); role.pack(anchor='w')
            self.image(role, 'role', self.r['role'], 16)
            self.label(role, core.ROLE_RU.get(self.r['role'], ''), 'mute', 8).pack(side='left')
            stat = self.d.lola.get(pick['c'] + '|' + self.r['role'])
            if stat:
                self.label(tile, f"{stat['wr']:.1f}% на роли", 'good2', 11, True).pack(anchor='w')
            self.label(tile, pick['why'], 'mute', 8, wraplength=max(80, (self.width-90)//3), justify='left').pack(anchor='w')

    def matchup(self):
        box = self.box(self.w.mid, 'Твой матчап')
        opp, role = self.r.get('opp'), self.r.get('role')
        if not self.me or not opp:
            self.label(box, 'Выбери чемпиона' if not self.me else 'Оппонент ещё не выбран', 'mute', 10).pack(anchor='w')
            return
        self.label(box, self.d.cn(self.me) + ' против ' + self.d.cn(opp), 'mute', 9).pack(anchor='w', pady=(0, 7))
        wr = n = None
        counters = core.lola_counters(self.app.lola_fetch('counter', opp, role), self.d)
        if self.me in counters: wr, _, n = counters[self.me]; wr = 100-wr
        else:
            counters = core.lola_counters(self.app.lola_fetch('counter', self.me, role), self.d)
            if opp in counters: wr, _, n = counters[opp]
        pl = self.app.player
        personal = pl.vs(self.me, opp) if pl else {'n':0}
        if pl and not personal['n']: personal = pl.vs(None, opp)
        gold = personal.get('g15')
        cells = [('Винрейт пары', f'{wr:.1f}%' if wr is not None else '—',
                  f'{n:,} игр'.replace(',', ' ') if n else 'Нет выборки', 'good2' if wr is not None and wr >= 50 else 'bad2'),
                 ('Твой счёт', f"{personal['w']}–{personal['n']-personal['w']}" if personal['n'] else '—',
                  f"{personal['n']} личных игр", 'fg'),
                 ('Золото на 15', f'{gold:+.0f}' if gold is not None else '—',
                  'По личной истории', 'good2' if gold is not None and gold >= 0 else 'bad2')]
        row = tk.Frame(box, bg=self.c['panel']); row.pack(fill='x')
        for i, (title, value, subtitle, color) in enumerate(cells):
            row.columnconfigure(i, weight=1, uniform='matchup')
            cell = tk.Frame(row, bg=self.c['deep'], padx=8, pady=8)
            cell.grid(row=0, column=i, sticky='nsew', padx=(0, 6))
            self.label(cell, title, 'mute', 8).pack(anchor='w')
            self.label(cell, value, color, 18, True).pack(anchor='w')
            self.label(cell, subtitle, 'mute', 7).pack(anchor='w')
        tip = pl.matchup_tip(opp) if pl else None
        if tip:
            self.label(box, tip, 'mute', 8, wraplength=max(120, self.width-28), justify='left').pack(anchor='w', pady=(6, 0))

    def set_auto(self, enabled):
        self.app.s['auto_import'] = enabled
        if enabled and not any(self.app.s['auto_parts'].values()):
            self.app.s['auto_parts'].update(runes=True, items=True)
            for key in ('runes', 'items'): self.app.auto_vars[key].set(True)
        self.app.s.save()
        self.app.draft_sig = self.w.draft_sig = None
        if self.app.draft: self.app.on_draft(self.app.draft)

    def build_table(self):
        box = self.box(self.w.mid, 'Связки рун и сборок · ' + self.d.cn(self.me))
        mode = tk.Frame(box, bg=self.c['panel']); mode.pack(fill='x')
        for enabled, text in ((True, 'Автоэкспорт'), (False, 'Вручную')):
            ttk.Button(mode, text=text, style='DraftActive.TButton' if self.app.s['auto_import'] == enabled else 'Draft.TButton',
                       command=lambda enabled=enabled: self.set_auto(enabled)).pack(side='left', padx=(0, 4))
        ttk.Button(mode, text='Экспорт', style='DraftPrimary.TButton', command=lambda: self.app.do_import(tuple(key for key, value in self.app.s['auto_parts'].items() if value))).pack(side='right')
        parts = tk.Frame(box, bg=self.c['panel']); parts.pack(fill='x', pady=4)
        for key, text in (('runes', 'Руны'), ('items', 'Предметы'), ('spells', 'Заклинания')):
            ttk.Checkbutton(parts, text=text, variable=self.app.auto_vars[key],
                            style='Draft.TCheckbutton',
                            command=lambda key=key: self.app.set_import_part(key)).pack(side='left')
        options = draft_model.build_options(self.full)
        for option in options:
            variant, key = option['variant'], option['key']
            row = tk.Frame(box, bg=self.c['raise'] if self.app.s['rune_pick'] == key else self.c['deep'], padx=5, pady=5)
            row.pack(fill='x', pady=2)
            narrow = self.width < self.fs(480)
            ttk.Button(row, text=option['title'], style='Draft.TButton', width=12, command=lambda key=key: self.app.set_rune_pick(key)).pack(side='top' if narrow else 'left', anchor='w', padx=(0, 5))
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
            self.label(box, title, 'gold', 8).pack(anchor='w', pady=(7, 2))
            placeholder = tk.Frame(box, bg=self.c['deep'], padx=9, pady=7, highlightthickness=1, highlightbackground=self.c['line'])
            placeholder.pack(fill='x')
            self.label(placeholder, 'Источник не подключён', 'mute', 8).pack(anchor='w')
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
        self.styles()
        self.toolbar()
        self.w._draft_cards = self.player_cards
        for col in self.w.cols: col.bind('<Configure>', self.schedule_sizes)
        for parent, text, color in ((self.w.cols[0], 'Союзники', 'blue2'), (self.w.cols[1], 'Противники', 'red2')):
            self.label(parent, text, color, 13, True).pack(anchor='w', pady=(0, 7))
        order = {rr: i for i, rr in enumerate(core.ROLES)}
        allies = sorted(self.cs.get('allies') or [], key=lambda a: order.get(a.get('pos'), 9))
        enemies = sorted(({'c': c, 'pos': self.r['roles'].get(c, '')} for c in self.cs['enemies']), key=lambda a: order.get(a['pos'], 9))
        for column, players in enumerate((allies, enemies)):
            for player in draft_model.role_slots(players, core.ROLES):
                self.player(self.w.cols[column], player, column == 1)
        self.schedule_sizes()
        if self.me and self.cs.get('locked'): self.build_table()
        else: self.top_picks()
        self.matchup()
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
    view = DraftView(dashboard, cs, result, bans, me, full, colors, fonts)
    dashboard._draft_view = view
    view.draw()
