"""Native champion page; uses existing asynchronous sources without altering draft choices."""
import tkinter as tk
import ui_skin
from tkinter import ttk
from scroll_canvas import ScrollCanvas
import core
import champion_pool
import draft_model
import home_model
from view_components import ReadableComponents as Components, readable_palette


class ChampionScreen(ui_skin.material_ui.Frame, Components):
    def __init__(self,parent,app):
        from ui import C,F
        super().__init__(parent,bg=C['bg']);self.app,self.c,self.f=app,readable_palette(C),F
        self.pack(fill='both',expand=True)
        self.champion=None;self.role='MIDDLE';self.opponent=None;self.context='general';self.variant='pick'
        self.expanded=False;self.job=None;self.layout=None
        self.right_open=False;self.right_scroll=0;self.right_canvas=None
        self.names=sorted(((app.data.cn(k),k) for k in set(app.data.ids.values())),key=lambda p:p[0])
        self.query=tk.StringVar();self.enemy_query=tk.StringVar()
        self.label(self,'Чемпион',22,'gold',head=True).pack(anchor='w')
        self.label(self,'Статистика · руны и предметы · умения · матчапы',10,'mute').pack(anchor='w',pady=(0,10))
        search=ui_skin.Frame(self,bg=C['bg']);search.pack(fill='x')
        self.label(search,'Найти чемпиона',10).pack(side='left',padx=(0,10))
        self.search=ttk.Combobox(search,textvariable=self.query,values=[n for n,k in self.names],width=24,font=(F['font'],app.fs(12)))
        self.search.pack(side='left');self.search.bind('<KeyRelease>',lambda e:self.suggest(self.search,self.query))
        self.search.bind('<<ComboboxSelected>>',lambda e:self.search_pick());self.search.bind('<Return>',lambda e:self.search_pick())
        self.roles=ui_skin.Frame(self,bg=C['bg']);self.roles.pack(fill='x',pady=(8,10))
        self.body=ui_skin.Frame(self,bg=C['bg']);self.body.pack(fill='both',expand=True)
        self.bind('<Configure>',self.resized);self.bind('<Destroy>',self.cleanup,add='+')
        self.bind('<Map>',lambda e:self.refresh() if e.widget is self else None)
        self.refresh()

    def cleanup(self,e):
        if e.widget is self and self.job:self.after_cancel(self.job);self.job=None

    def resized(self,e):
        if e.widget is self and self.layout!=(e.width>=self.app.fs(1140)):
            if self.job:self.after_cancel(self.job)
            self.job=self.after(100,self.refresh)

    def suggest(self,widget,var):
        q=champion_pool.norm(var.get())
        widget.configure(values=[n for n,k in self.names if q in champion_pool.norm(n+' '+k)])

    def resolve(self,query):
        q=champion_pool.norm(query)
        if not q:return None
        exact=[k for n,k in self.names if q in (champion_pool.norm(n),champion_pool.norm(k))]
        matches=exact or [k for n,k in self.names if champion_pool.norm(n).startswith(q) or champion_pool.norm(k).startswith(q)]
        return matches[0] if len(matches)==1 else None

    def search_pick(self):
        champion=self.resolve(self.query.get())
        if champion:self.choose(champion)
        else:self.search.configure(values=[n for n,k in self.names if champion_pool.norm(self.query.get()) in champion_pool.norm(n+' '+k)])

    def choose(self,champion,role=None):
        if champion not in self.app.data.ids.values():return
        if champion!=self.champion:self.context='general';self.variant='pick';self.opponent=None;self.enemy_query.set('');self.expanded=False
        self.champion=champion;self.role=role or self.app.data.role_of_champ(champion) or 'TOP'
        if self.role not in core.ROLES:self.role='TOP'
        self.query.set(self.app.data.cn(champion));self.app.cp_sel=(champion,self.role)
        self.refresh()

    def select_opponent(self,champion=None):
        champion=champion or self.resolve(self.enemy_query.get())
        if not champion or champion==self.champion:return
        self.opponent=champion;self.enemy_query.set(self.app.data.cn(champion));self.context='matchup';self.variant='pick';self.refresh()

    def select_build(self,context,variant):
        self.context,self.variant=context,variant;self.refresh()

    def select_player(self,bid):
        row=next((r for group in (self.players or {}).get('groups',{}).values() for r in group if r['id']==bid),None)
        if row and row.get('variant'):
            self.context='general';self.variant='player:'+bid;self.refresh()

    def section(self,parent,title):
        box=self.panel(parent,12);box.pack(fill='x',pady=(0,8))
        self.label(box,title,14,'fg',head=True).pack(anchor='w',pady=(0,8));return box

    def refresh(self):
        if self.job:self.after_cancel(self.job);self.job=None
        if not self.winfo_exists():return
        if self.right_canvas and self.right_canvas.winfo_exists():self.right_scroll=self.right_canvas.yview()[0]
        self.right_canvas=None
        for w in self.body.winfo_children():w.destroy()
        for w in self.roles.winfo_children():w.destroy()
        self.layout=self.winfo_width()>=self.app.fs(1140)
        if not self.champion:
            box=self.section(self.body,'Выбери чемпиона')
            self.label(box,'Поиск по русскому или английскому имени. Ниже — твои частые чемпионы.',10,'mute').pack(anchor='w')
            games=self.app.player.games if self.app.player else []
            frequent=home_model.snapshot(games)['frequent']
            row=ui_skin.Frame(box,bg=self.c['panel']);row.pack(anchor='w',pady=(10,0))
            for entry in frequent:
                key=entry['champion'];tile=ui_skin.Frame(row,bg=self.c['panel']);tile.pack(side='left',padx=(0,16))
                self.image(tile,'champ',key,48)
                self.button(tile,self.app.data.cn(key),lambda k=key:self.choose(k)).pack(side='left')
            return
        for role in core.ROLES:
            b=self.button(self.roles,core.ROLE_RU[role].capitalize(),lambda r=role:self.choose(self.champion,r),role==self.role)
            icon=self.app.icons.get('role',role,self.app.fs(16)) if role in self.app.icons.a.get('role',{}) else None
            if icon:b.configure(image=icon,compound='left')
            b.pack(side='left',padx=(0,4))
        full=self.app.lola_build(self.champion,self.role)
        self.offmeta=self.app.offmeta_build(self.champion,self.role)
        self.players=self.app.player_builds(self.champion,self.role)
        counters=core.lola_counters(self.app.lola_fetch('counter',self.champion,self.role),self.app.data)
        matchup=self.app.lola_matchup(self.champion,self.role,self.opponent) if self.opponent else None
        selected=matchup if self.context=='matchup' else full
        options=draft_model.build_options(selected)
        if self.context=='general' and self.offmeta and self.offmeta.get('variant'):
            options.append({'key':'offmeta','title':'Оффметовая','variant':self.offmeta['variant'],
                            'rune_winrate':None,'rune_games':None,'item_winrate':None,'item_games':None})
        self.current_options=options
        option=next((o for o in options if o['key']==self.variant),None)
        variant=option['variant'] if option else None
        if self.context=='general' and self.variant=='offmeta':selected=self.offmeta
        self.selected_player=None
        if self.context=='general' and self.variant.startswith('player:'):
            self.selected_player=next((r for group in (self.players or {}).get('groups',{}).values() for r in group if self.variant=='player:'+r['id']),None)
            selected=self.selected_player;variant=(selected or {}).get('variant')
        self.selected_variant=variant
        self.header(full)
        grid=ui_skin.Frame(self.body,bg=self.c['bg']);grid.pack(fill='x')
        left=ui_skin.Frame(grid,bg=self.c['bg']);right=ui_skin.Frame(grid,bg=self.c['bg'])
        left.grid(row=0,column=0,sticky='nsew',padx=(0,8) if self.layout else 0)
        right.grid(row=0 if self.layout else 1,column=1 if self.layout else 0,sticky='nsew',pady=(0,8) if self.layout else 0)
        self.left_column,self.right_column=left,right
        if self.layout:right.configure(height=1,width=1);right.pack_propagate(False)
        grid.columnconfigure(0,weight=3,uniform='page' if self.layout else '')
        if self.layout:grid.columnconfigure(1,weight=2,uniform='page')
        self.builds(left,full,matchup)
        self.loadout(left,selected,variant)
        self.skills(left,variant)
        self.personal(right)
        self.opponent_picker(right)
        self.right_details(right,counters)

    def toggle_right(self):
        self.right_open=not self.right_open;self.right_scroll=0
        if self.right_canvas and self.right_canvas.winfo_exists():self.right_canvas.yview_moveto(0)
        self.refresh()

    def right_details(self,parent,counters):
        c,fs=self.c,self.app.fs
        handle=tk.Canvas(parent,height=fs(74),bg=c['bg'],highlightthickness=0,takefocus=True,cursor='hand2')
        handle.pack(side='bottom',fill='x');self.curtain_handle=handle
        groups=(self.players or {}).get('groups',{})
        count=f"Мейнеры {len(groups.get('OTP',[]))}/3   ·   Проигроки {len(groups.get('Pro',[]))}/3"
        def draw(e=None):
            w=handle.winfo_width();h=fs(73);cut=fs(12);mid=w/2
            handle.delete('all')
            handle.create_polygon(cut,1,w-cut,1,w-1,cut,w-1,h-cut,w-cut,h-1,cut,h-1,1,h-cut,1,cut,fill=c['deep'],outline=c['gold'],width=1)
            for direction in (-1,1):
                edge=mid+direction*fs(36);tip=mid+direction*fs(9)
                handle.create_line(mid+direction*fs(72),fs(11),edge,fs(11),tip,fs(18),fill=c['gold'])
                x=mid+direction*fs(80)
                handle.create_oval(x-fs(2),fs(9),x+fs(2),fs(13),outline=c['gold'])
            handle.create_polygon(mid,fs(6),mid+fs(7),fs(13),mid,fs(20),mid-fs(7),fs(13),outline=c['gold'],fill=c['raise'])
            ys=(fs(15),fs(11)) if self.right_open else (fs(11),fs(15))
            handle.create_line(mid-fs(3),ys[0],mid,ys[1],mid+fs(3),ys[0],fill=c['gold'],width=2)
            handle.create_text(mid,fs(33),text='Скрыть сборки игроков' if self.right_open else 'Сборки мейнеров и профи',font=(self.f['font'],fs(11)),fill=c['gold'])
            handle.create_text(mid,fs(57),text=count,font=(self.f['font'],fs(11)),fill=c['mute'])
        handle.bind('<Configure>',draw);handle.bind('<Button-1>',lambda e:self.toggle_right())
        handle.bind('<Return>',lambda e:self.toggle_right());handle.bind('<space>',lambda e:self.toggle_right())
        handle.bind('<FocusIn>',lambda e:handle.configure(highlightthickness=1,highlightbackground=c['gold']))
        handle.bind('<FocusOut>',lambda e:handle.configure(highlightthickness=0))
        if not self.layout:
            if self.right_open:self.special_sources(parent)
            else:self.player_cards=[]
            self.matchups(parent,counters);return
        viewport=ui_skin.Frame(parent,bg=c['bg']);viewport.pack(fill='both',expand=True)
        cv=ScrollCanvas(viewport,bg=c['bg'],highlightthickness=0);self.right_canvas=cv
        sb=ttk.Scrollbar(viewport,orient='vertical',command=cv.yview)
        sb.pack(side='right',fill='y');cv.pack(side='left',fill='both',expand=True);cv.configure(yscrollcommand=sb.set)
        body=ui_skin.Frame(cv,bg=c['bg']);win=cv.create_window((0,0),window=body,anchor='nw')
        cv.bind('<Configure>',lambda e:cv.itemconfigure(win,width=e.width), add='+')
        body.bind('<Configure>',lambda e:cv.configure(scrollregion=cv.bbox('all')))
        if self.right_open:self.special_sources(body)
        else:self.player_cards=[]
        self.matchups(body,counters)
        scroll=cv.wheel
        def bind_wheel(widget):
            widget.bind('<MouseWheel>',scroll);widget.bind('<Button-4>',scroll);widget.bind('<Button-5>',scroll)
            for child in widget.winfo_children():bind_wheel(child)
        bind_wheel(body);cv.bind('<MouseWheel>',scroll);cv.bind('<Button-4>',scroll);cv.bind('<Button-5>',scroll)
        def restore():
            if cv.winfo_exists():cv.yview_moveto(self.right_scroll)
        self.after_idle(restore)

    def header(self,full):
        box=self.panel(self.body,14);box.pack(fill='x',pady=(0,10))
        self.image(box,'champ',self.champion,64);self.image(box,'role',self.role,22)
        text=ui_skin.Frame(box,bg=self.c['panel']);text.pack(side='left',fill='x',expand=True)
        self.label(text,self.app.data.cn(self.champion),24,'gold',head=True).pack(anchor='w')
        self.label(text,core.ROLE_RU[self.role].capitalize()+' · EUW · Изумруд+',10,'mute').pack(anchor='w')
        wr=full.get('wr') if full else None;n=full.get('games') if full else None
        self.label(text,(f'{wr:.1f}% побед' if wr is not None else 'Винрейт —')+(f' · {n:,} игр'.replace(',',' ') if n is not None else ''),12,'fg',num=True).pack(anchor='w',pady=(4,0))
        pool=self.app.current_pool();in_pool=self.champion in pool.get(self.role,[])
        self.button(box,'✓ В твоём пуле' if in_pool else '+ В мой пул',self.toggle_pool,in_pool).pack(side='right')

    def toggle_pool(self):
        try:self.app.toggle_pool(self.champion,self.role)
        except (OSError,ValueError):
            self.app.status.configure(text='Не удалось сохранить пул');return
        self.refresh()

    def builds(self,parent,full,matchup):
        box=self.section(parent,'Руны и сборка')
        row=ui_skin.Frame(box,bg=self.c['panel']);row.pack(fill='x',pady=(0,6))
        self.button(row,'Все матчапы',lambda:self.select_build('general','pick'),self.context=='general').pack(side='left',padx=(0,4))
        if self.opponent:self.button(row,'Против: '+self.app.data.cn(self.opponent),lambda:self.select_build('matchup','pick'),self.context=='matchup').pack(side='left')
        source=matchup if self.context=='matchup' else full
        self.option_buttons=[]
        for option in self.current_options:
            key=option['key'];active=key==self.variant
            item=ui_skin.Frame(box,bg=self.c['raise'] if active else self.c['deep'],padx=self.app.fs(8),pady=self.app.fs(8),highlightthickness=1,highlightbackground=self.c['gold' if active else 'line'],takefocus=True)
            item.pack(fill='x',pady=(0,5));self.option_buttons.append(item)
            heading=ui_skin.Frame(item,bg=item.cget('bg'));heading.pack(fill='x')
            self.label(heading,option['title']+(' ✓' if active else ''),12,'gold' if active else 'fg').pack(side='left')
            self.label(heading,'Руны + предметы',9,'mute').pack(side='right')
            icons=ui_skin.Frame(item,bg=item.cget('bg'));icons.pack(anchor='w',pady=(6,0))
            for rune in option['variant'].get('perks',[])[:6]:self.image(icons,'rune',rune,22)
            self.label(icons,'  ›  ',10,'mute').pack(side='left')
            self.item_icons(icons,core.lola_build_items(option['variant']),24)
            metric='Ключевая руна' if option['variant'].get('rune_stat_kind')=='keystone' else 'Руны источника'
            samples=[]
            for title,wr,n in ((metric,option['rune_winrate'],option['rune_games']),('Основа',option['item_winrate'],option['item_games'])):
                samples.append(title+': '+(f'{wr:.1f}%' if wr is not None else '—')+(f' · {n:,} игр'.replace(',',' ') if n is not None else ''))
            if key=='offmeta':
                meta=self.offmeta
                caption=f"Mobalytics · {meta['source_winrate']:.1f}% · {meta['source_games']:,} игр · патч {meta['patch']}".replace(',',' ')
                self.label(item,caption,10,'gold',wraplength=self.app.fs(540),justify='left').pack(anchor='w',pady=(6,0))
                self.label(item,'Off-Meta по классификации источника · все регионы · Изумруд+',8,'mute',wraplength=self.app.fs(540),justify='left').pack(anchor='w',pady=(3,0))
                if meta.get('stale'):self.label(item,'Сохранённые данные · обновление не удалось',9,'gold').pack(anchor='w')
            else:self.label(item,'    |    '.join(samples),9,'fg',wraplength=self.app.fs(540),justify='left').pack(anchor='w',pady=(6,0))
            def select(e=None,k=key):self.select_build(self.context,k)
            def bind(widget):
                widget.configure(cursor='hand2');widget.bind('<Button-1>',select)
                for child in widget.winfo_children():bind(child)
            bind(item);item.bind('<Return>',select);item.bind('<space>',select)
        if not source:
            key=('matchup',self.champion,self.role,self.opponent) if self.context=='matchup' else (self.champion,self.role)
            self.label(box,'Сборка недоступна' if self.app.lola_state.get(key)=='fail' else 'Загрузка сборки…',11,'mute').pack(anchor='w')
        if self.context=='general' and not (self.offmeta or {}).get('variant'):
            loader=getattr(self.app,'_offmeta_source',None)
            failed=loader and loader.states.get((self.champion,self.role))=='fail'
            self.label(box,'Оффметовая: источник не подтвердил сборку для этой роли' if failed else 'Оффметовая: нет подтверждённого варианта' if self.offmeta else 'Оффметовая: загрузка Mobalytics…',9,'mute',wraplength=self.app.fs(470),justify='left').pack(anchor='w',pady=(3,4))
        where='Все регионы · Изумруд+ · оппонент: '+self.app.data.cn(self.opponent) if self.context=='matchup' else 'EUW · Изумруд+ · все матчапы'
        if self.selected_player:
            self.label(box,'Выбрано: '+self.selected_player['name']+' · Mobalytics · патч '+self.selected_player['patch'],9,'mute',wraplength=self.app.fs(470),justify='left').pack(anchor='w',pady=(4,0))
        elif self.variant=='offmeta' and self.context=='general' and self.offmeta:
            self.label(box,'Выбрано: Mobalytics · все регионы · Изумруд+ · патч '+self.offmeta['patch'],9,'mute',wraplength=self.app.fs(470),justify='left').pack(anchor='w',pady=(4,0))
        else:
            self.label(box,'Lolalytics · '+where,9,'mute',wraplength=self.app.fs(470),justify='left').pack(anchor='w',pady=(4,0))
            if source:self.label(box,'Выборки рун и предметов раздельные.',8,'mute').pack(anchor='w',pady=(3,0))
        if source and source.get('stale'):self.label(box,'Показан сохранённый ответ: обновить источник не удалось.',9,'gold',wraplength=self.app.fs(470),justify='left').pack(anchor='w')

    def loadout(self,parent,full,variant):
        box=self.section(parent,'Выбранный вариант')
        if not variant:
            self.label(box,'Руны и предметы появятся после загрузки.',10,'mute').pack(anchor='w');return
        if self.selected_player:
            row=self.selected_player
            self.label(box,row['name']+' · '+('Мейнер' if row['kind']=='OTP' else 'Проигрок'),14,'gold',wraplength=self.app.fs(470),justify='left').pack(anchor='w')
            self.label(box,f"Mobalytics · {row['winrate']:.1f}% · {row['games']} игр · патч {row['patch']}",10,'mute').pack(anchor='w',pady=(3,8))
            if row.get('stale') or (self.players or {}).get('stale'):self.label(box,'Сохранённая сборка · обновить не удалось',10,'gold').pack(anchor='w')
        if self.context=='general' and self.variant=='offmeta':
            self.label(box,'Оффметовая · Mobalytics · патч '+full['patch'],12,'gold').pack(anchor='w',pady=(0,8))
        row=ui_skin.Frame(box,bg=self.c['panel']);row.pack(anchor='w')
        for rune in variant.get('perks',[])[:6]:self.image(row,'rune',rune,30)
        for shard in variant.get('shards',[]):self.image(row,'rune',shard,20)
        row=ui_skin.Frame(box,bg=self.c['panel']);row.pack(anchor='w',pady=(8,0))
        self.label(row,'Старт',10).pack(side='left',padx=(0,10));self.item_icons(row,variant.get('start',[]),28)
        for spell in variant.get('spells',[])[:2]:self.image(row,'spell',spell,26)
        row=ui_skin.Frame(box,bg=self.c['panel']);row.pack(anchor='w',pady=(8,0))
        self.label(row,'Сборка',10).pack(side='left',padx=(0,8));self.item_icons(row,core.lola_build_items(variant),32)
        self.button(box,('▾' if self.expanded else '▸')+' Подробности и выборки',self.toggle_details,self.expanded).pack(anchor='w',pady=(10,0))
        if self.expanded:
            if self.selected_player:
                self.label(box,'Статистика варианта этого игрока на выбранном чемпионе и роли по данным Mobalytics. Полная сборка взята из его записи; проценты для отдельных рун и предметов не опубликованы.',9,'mute',wraplength=self.app.fs(470),justify='left').pack(anchor='w')
            elif self.context=='general' and self.variant=='offmeta':
                self.label(box,'Выборка варианта Mobalytics. Отдельные проценты для полной страницы рун и шести предметов не опубликованы.',9,'mute',wraplength=self.app.fs(470),justify='left').pack(anchor='w',pady=(5,0))
            else:
                for title,wr,n in [('Ключевая руна' if variant.get('rune_stat_kind')=='keystone' else 'Руны источника',variant.get('wr_runes'),variant.get('n_runes')),('Основа предметов',variant.get('wr_core'),variant.get('n_core'))]:
                    self.label(box,title+': '+(f'{wr:.1f}%' if wr is not None else '—')+(f' · {n:,} игр'.replace(',',' ') if n is not None else ' · выборка недоступна'),10,'fg').pack(anchor='w',pady=(5,0))
                self.label(box,'Это отдельные выборки. Общий винрейт рун вместе с предметами источник не подтверждает.',9,'mute',wraplength=self.app.fs(470),justify='left').pack(anchor='w',pady=(5,0))
        for iid,short,when in (full or {}).get('situ',[])[:6]:
            row=ui_skin.Frame(box,bg=self.c['panel']);row.pack(fill='x',pady=(6,0))
            self.item_icons(row,[iid],23);self.label(row,when if short.casefold() in when.casefold() else short+' · '+when,9,'mute',wraplength=self.app.fs(420),justify='left').pack(side='left')

    def toggle_details(self):self.expanded=not self.expanded;self.refresh()

    def skills(self,parent,variant):
        box=self.section(parent,'Порядок умений')
        if not variant:
            self.label(box,'Порядок пока недоступен',10,'mute').pack(anchor='w');return
        priority=variant.get('skill_prio') or ''
        self.label(box,' → '.join(priority) if priority else 'Приоритет не указан',15,'gold',num=True).pack(anchor='w')
        sequence=variant.get('skills') or ''
        for offset in (0,9):
            row=ui_skin.Frame(box,bg=self.c['panel']);row.pack(fill='x',pady=(5,0))
            for col,level in enumerate(range(offset,offset+9)):
                row.columnconfigure(col,weight=1,uniform='skill')
                self.label(row,str(level+1),8,'mute',anchor='center').grid(row=0,column=col)
                letter=sequence[level] if level<len(sequence) else '—'
                self.label(row,letter,12,'gold' if letter=='R' else 'fg',num=True,bg=self.c['deep'],anchor='center',pady=4).grid(row=1,column=col,sticky='ew',padx=1)
        if len(sequence)<18:self.label(box,f'Подтверждено уровней: {len(sequence)} из 18.',9,'mute').pack(anchor='w',pady=(5,0))

    def personal(self,parent):
        box=self.section(parent,'Твоя статистика')
        games=self.app.player.on(self.champion,self.role) if self.app.player else []
        if self.context=='matchup':games=[g for g in games if g.get('opp')==self.opponent]
        stats=home_model.stats(games)
        profile=(self.app.data.d['players'].get(self.app.who) or {}).get('riot') or self.app.who or 'Профиль не выбран'
        self.label(box,profile,11,'gold').pack(anchor='w')
        self.label(box,('Против: '+self.app.data.cn(self.opponent) if self.context=='matchup' else 'Все оппоненты')+' · '+core.ROLE_RU[self.role],9,'mute').pack(anchor='w',pady=(2,8))
        values=[('Матчей',str(stats['n'])),('Победы',f"{stats['wr']:.1f}%" if stats['wr'] is not None else '—'),('KDA',f"{stats['kda']:.2f}" if stats['kda'] is not None else '—'),('Фарм / мин',f"{stats['csm']:.1f}" if stats['csm'] is not None else '—')]
        grid=ui_skin.Frame(box,bg=self.c['panel']);grid.pack(fill='x')
        for i,(title,value) in enumerate(values):
            cell=ui_skin.Frame(grid,bg=self.c['deep'],padx=8,pady=6);cell.grid(row=i//2,column=i%2,sticky='nsew',padx=(0,5),pady=(0,5));grid.columnconfigure(i%2,weight=1,uniform='personal')
            self.label(cell,value,22,'fg',num=True).pack(anchor='w');self.label(cell,title,9,'mute').pack(anchor='w')
        self.label(box,f"Сохранённые матчи · KDA: {stats['kda_n']} · фарм: {stats['csm_n']} игр",8,'mute',wraplength=self.app.fs(340),justify='left').pack(anchor='w')
        if not games:self.label(box,'Нет сохранённых игр на этом чемпионе и роли.',10,'mute',wraplength=self.app.fs(340),justify='left').pack(anchor='w',pady=(5,0))

    def opponent_picker(self,parent):
        box=self.section(parent,'Против кого играешь?')
        self.enemy_search=ttk.Combobox(box,textvariable=self.enemy_query,values=[n for n,k in self.names if k!=self.champion],width=24)
        self.enemy_search.pack(fill='x');self.enemy_search.bind('<KeyRelease>',lambda e:self.suggest(self.enemy_search,self.enemy_query))
        self.enemy_search.bind('<<ComboboxSelected>>',lambda e:self.select_opponent());self.enemy_search.bind('<Return>',lambda e:self.select_opponent())
        self.label(box,'Выбери оппонента — появятся популярный вариант и вариант по винрейту именно против него.',9,'mute',wraplength=self.app.fs(340),justify='left').pack(anchor='w',pady=(7,0))

    def matchups(self,parent,counters):
        box=self.section(parent,'Матчапы на линии')
        if not counters:
            failed=self.app.lola_state.get(('counter',self.champion,self.role))=='fail'
            self.label(box,'Матчапы недоступны' if failed else 'Загрузка матчапов…',10,'mute').pack(anchor='w');return
        ordered=sorted(counters.items(),key=lambda kv:kv[1][0])
        for title,rows,color in [('Сложные',ordered[:3],'bad'),('Удобные',list(reversed(ordered))[:3],'good')]:
            self.label(box,title,11,color).pack(anchor='w',pady=(6,3))
            for enemy,(wr,delta,n) in rows:
                row=ui_skin.Frame(box,bg=self.c['deep'],padx=5,pady=5);row.pack(fill='x',pady=(0,3))
                self.image(row,'champ',enemy,26)
                self.label(row,self.app.data.cn(enemy),10).pack(side='left')
                self.label(row,f'{wr:.1f}% · {n:,}'.replace(',',' '),10,color,num=True).pack(side='right')
                def select(e=None,k=enemy):self.select_opponent(k)
                for widget in [row]+row.winfo_children():widget.bind('<Button-1>',select);widget.configure(cursor='hand2')
        self.label(box,'Твой чемпион: % побед · число игр. Нажми на оппонента для сборки. Все регионы · Изумруд+ · от 150 игр.',8,'mute',wraplength=self.app.fs(340),justify='left').pack(anchor='w',pady=(5,0))

    def special_sources(self,parent):
        self.player_cards=[]
        packet=self.players or {};groups=packet.get('groups',{})
        loader=getattr(self.app,'_player_build_source',None)
        state=loader.states.get((self.champion,self.role)) if loader else None
        for kind,title in (('OTP','Мейнеры'),('Pro','Проигроки')):
            rows=groups.get(kind,[]);box=self.section(parent,title+f' · {len(rows)}/3')
            if not packet:
                self.label(box,'Источник не подтвердил данные для этой роли' if state=='fail' else 'Загрузка Mobalytics…',10,'mute',wraplength=self.app.fs(340),justify='left').pack(anchor='w');continue
            for row in rows:
                active=self.variant=='player:'+row['id'] and self.context=='general'
                tile=ui_skin.Frame(box,bg=self.c['raise'] if active else self.c['deep'],padx=8,pady=7,highlightthickness=1,highlightbackground=self.c['gold' if active else 'line'],takefocus=True)
                tile.pack(fill='x',pady=(0,5));self.player_cards.append(tile)
                head=ui_skin.Frame(tile,bg=tile.cget('bg'));head.pack(fill='x')
                self.label(head,row['name']+(' ✓' if active else ''),11,'gold' if active else 'fg',wraplength=self.app.fs(190),justify='left').pack(side='left')
                self.label(head,f"{row['winrate']:.1f}% · {row['games']} игр",11,'fg',num=True).pack(side='right')
                icons=ui_skin.Frame(tile,bg=tile.cget('bg'));icons.pack(anchor='w',pady=(5,0))
                for rune in row.get('perks',[])[:6]:self.image(icons,'rune',rune,18)
                if row.get('variant'):
                    items=ui_skin.Frame(tile,bg=tile.cget('bg'));items.pack(anchor='w',pady=(4,0));self.item_icons(items,core.lola_build_items(row['variant']),23)
                else:self.label(tile,'Предметы: — · подробности недоступны' if row.get('error') or state=='ok' else 'Предметы: загрузка…',9,'mute').pack(anchor='w',pady=(3,0))
                self.label(tile,'Патч '+row['patch']+(' · сохранённые данные' if row.get('stale') or packet.get('stale') else ''),8,'mute').pack(anchor='w',pady=(3,0))
                if row.get('variant'):
                    def select(e=None,bid=row['id']):self.select_player(bid)
                    def bind(widget):
                        widget.configure(cursor='hand2');widget.bind('<Button-1>',select)
                        for child in widget.winfo_children():bind(child)
                    bind(tile);tile.bind('<Return>',select);tile.bind('<space>',select)
            if len(rows)<3:self.label(box,f'Подтверждено {len(rows)} из 3. Других игроков источник не предоставил.',9,'mute',wraplength=self.app.fs(340),justify='left').pack(anchor='w',pady=(3,0))
            self.label(box,'Mobalytics · '+('OTP' if kind=='OTP' else 'Pro')+' · по числу игр',8,'mute').pack(anchor='w',pady=(3,0))
