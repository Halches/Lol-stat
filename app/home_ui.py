"""Native home screen: profile first, loaded season statistics, matches and champion pool."""
import time
import tkinter as tk
from tkinter import ttk
import core
import home_model as model


class HomeScreen(tk.Frame):
    def __init__(self,parent,app):
        from ui import C,F
        super().__init__(parent,bg=C['bg'])
        self.app,self.c,self.f=app,dict(C),F
        fg,bg=C['fg'],C['panel']
        self.c['mute']='#'+''.join(f'{round(int(fg[i:i+2],16)*.8+int(bg[i:i+2],16)*.2):02x}' for i in (1,3,5))
        self.pack(fill='both',expand=True)
        self.period=app.s.get('home_period','season')
        if self.period not in ('season','recent'):self.period='season'
        self.layout=None;self.resize_job=None
        self.bind('<Configure>',self.resized)
        self.bind('<Destroy>',self.cleanup,add='+')
        self.refresh()

    def cleanup(self,event):
        if event.widget is self and self.resize_job:self.after_cancel(self.resize_job);self.resize_job=None

    def resized(self,event):
        if event.widget is not self:return
        mode=self.mode(max(self.app.fs(550),event.width))
        if mode!=self.layout or getattr(self,'layout_width',None)!=event.width:
            if self.resize_job:self.after_cancel(self.resize_job)
            self.resize_job=self.after(100,self.reflow)

    def reflow(self):
        if self.resize_job:self.after_cancel(self.resize_job)
        self.resize_job=None
        width=self.winfo_width()
        if width>1 and (self.mode(max(self.app.fs(550),width))!=self.layout or width!=self.layout_width):
            self.refresh()

    def mode(self,width):return (width>=self.app.fs(1100),width>=self.app.fs(780),width>=self.app.fs(740),width>=self.app.fs(1100),width>=self.app.fs(1050))

    def label(self,parent,text,size=10,color='fg',head=False,**kw):
        return tk.Label(parent,text=text,bg=kw.pop('bg',parent.cget('bg')),fg=self.c[color],
                        font=(self.f['head'] if head else self.f['font'],self.app.fs(max(11,size))),anchor=kw.pop('anchor','w'),**kw)

    def button(self,parent,text,command,on=False):
        c=self.c
        return tk.Button(parent,text=text,command=command,bg=c['raise'] if on else c['deep'],fg=c['gold'] if on else c['fg'],
                         relief='flat',bd=0,highlightthickness=1,highlightbackground=c['gold'] if on else c['line'],
                         highlightcolor=c['gold'],activebackground=c['raise'],activeforeground=c['gold'],
                         font=(self.f['font'],self.app.fs(11)),padx=self.app.fs(10),pady=self.app.fs(7),cursor='hand2')

    def panel(self,parent,pad=12):
        return tk.Frame(parent,bg=self.c['panel'],padx=self.app.fs(pad),pady=self.app.fs(pad),
                        highlightthickness=1,highlightbackground=self.c['line'])

    def image(self,parent,group,key,size):
        # Do not trigger Icons' synchronous LCU fallback while rendering.
        if key is None or str(key) not in self.app.icons.a.get(group,{}):return None
        photo=self.app.icons.get(group,str(key),self.app.fs(size))
        if photo:
            label=tk.Label(parent,image=photo,bg=parent.cget('bg'));label.pack(side='left',padx=(0,self.app.fs(10)))
            return label

    def period_pick(self,value):
        old=self.app.s.get('home_period','season')
        self.app.s['home_period']=value
        try:self.app.s.save()
        except OSError:
            self.app.s['home_period']=old
            self.app.status.configure(text='Не удалось сохранить выбранный период')
            return
        self.period=value;self.refresh()

    def choose_profile(self,var):
        who=next((key for key,p in self.app.data.d['players'].items() if p['riot']==var.get()),None)
        if who is None:return
        old=self.app.s.get('who','')
        self.app.s['who']=who
        try:self.app.s.save()
        except OSError:
            self.app.s['who']=old
            self.app.status.configure(text='Не удалось сохранить выбранный профиль')
            self.refresh();return
        self.app.set_who(who);self.app.panel_sync()

    def open_champion(self,champion,role):
        self.app.nb.select(2);self.app.cp_var.set(self.app.data.cn(champion));self.app.cp_pick(champion,role or None)

    def refresh(self):
        from ui import RIOT_NOTE
        if not self.winfo_exists():return
        app,d,c,fs=self.app,self.app.data,self.c,self.app.fs
        width=max(fs(550),self.winfo_width() if self.winfo_width()>1 else app.root.winfo_width()-fs(250))
        self.layout_width=self.winfo_width()
        wide,metrics_wide,room,rank_inline,show_tft=self.layout=self.mode(width)
        for child in self.winfo_children():child.destroy()
        profile=d.d['players'].get(app.who or '') or {}
        own=model.live_profile(profile,app.account)
        account=(app.account or {}) if own else {}
        name=profile.get('riot') or account.get('riot') or 'Профиль не выбран'
        games=app.player.games if app.player else []
        self.data=model.snapshot(games,self.period)
        controls=tk.Frame(self,bg=c['bg']);controls.pack(fill='x',pady=(0,10))
        self.label(controls,'ПРОСМОТР ПРОФИЛЯ',9,'mute').pack(side='left')
        var=tk.StringVar(value=name)
        cb=ttk.Combobox(controls,state='readonly',textvariable=var,values=[p['riot'] for p in d.d['players'].values()],width=24,font=(self.f['font'],fs(12)))
        cb.pack(side='left',padx=(10,0),ipady=4);cb.bind('<<ComboboxSelected>>',lambda e:self.choose_profile(var))
        self.hero=self.panel(self,18);self.hero.pack(fill='x')
        identity=tk.Frame(self.hero,bg=c['panel']);identity.grid(row=0,column=0,sticky='nw')
        portrait=tk.Frame(identity,bg=c['panel']);portrait.pack(side='left',anchor='n')
        icon=account.get('icon')
        if icon is not None:app.ensure_home_icon(icon)
        avatar=self.image(portrait,'profile',icon,86)
        if not avatar:
            fallback=tk.Frame(portrait,bg=c['deep'],width=fs(76),height=fs(76),highlightthickness=1,highlightbackground=c['line'])
            fallback.pack(side='left',padx=(0,fs(14)));fallback.pack_propagate(False)
            self.label(fallback,'Профиль',10,'mute',anchor='center').pack(expand=True)
        text=tk.Frame(identity,bg=c['panel']);text.pack(side='left',fill='both',expand=True)
        self.label(text,'ТВОЙ ПРОФИЛЬ' if own and account else 'ИГРОВОЙ ПРОФИЛЬ',9,'mute').pack(anchor='w')
        name_label=self.label(text,name,26,'fg',wraplength=max(fs(220),fs(260) if rank_inline else width-fs(180)),justify='left');name_label.configure(font=(self.f['font'],fs(26),'bold'));name_label.pack(anchor='w',pady=(4,8))
        state=f"Уровень {account['level']} · клиент подключён" if account.get('level') else ('Клиент подключён' if account else 'Сохранённая статистика · клиент этого профиля не подключён')
        self.label(text,state,9,'mute',wraplength=max(fs(220),fs(245) if rank_inline else width-fs(160)),justify='left').pack(anchor='w')
        ranks=tk.Frame(self.hero,bg=c['panel'])
        ranks.grid(row=0 if rank_inline else 1,column=1 if rank_inline else 0,sticky='new',
                   padx=(fs(16),0) if rank_inline else 0,pady=0 if rank_inline else (fs(12),0))
        self.rank_cards={}
        entries=[('solo','СОЛО / ДУО'),('flex','ФЛЕКС'),('arena','АРЕНА')]
        if show_tft:entries.append(('tft','TFT'))
        overview=account.get('ranks') or {}
        for i,(key,title) in enumerate(entries):
            data=overview.get(key) if own else None
            fallback=profile.get('rank','') if key=='solo' else ''
            if key=='solo' and not data and own and app.my_rank:
                data=dict(app.my_rank,state='ranked')
            self.rank_card(ranks,key,title,data,fallback,i)
            ranks.columnconfigure(i,weight=1,uniform='rank')
        self.hero.columnconfigure(1 if rank_inline else 0,weight=1)
        actions=tk.Frame(self,bg=c['bg']);actions.pack(fill='x',pady=(10,14))
        links=[('Окно драфта и игры',app.open_dash),('Мой пул чемпионов',lambda:app.nb.select(10)),('Сайт со статистикой',app.open_site)]
        for i,(title,action) in enumerate(links):
            self.button(actions,title,action,i==0).grid(row=i//(3 if room else 2),column=i%(3 if room else 2),sticky='ew',padx=(0,6),pady=2)
        for i in range(3 if room else 2):actions.columnconfigure(i,weight=1,uniform='actions')
        period_line=tk.Frame(self,bg=c['bg']);period_line.pack(fill='x',pady=(0,7))
        self.label(period_line,'СТАТИСТИКА',16,'gold',head=True).pack(side='left')
        for title,key in [('Сезон','season'),('Последние 20','recent')]:
            self.button(period_line,title,lambda key=key:self.period_pick(key),self.period==key).pack(side='right',padx=(4,0))
        n=self.data['stats']['n']
        self.label(self,('Сезон · ' if self.period=='season' else 'Последние матчи · ')+core.plural(n,'загруженная игра','загруженные игры','загруженных игр'),9,'mute').pack(anchor='w',pady=(0,8))
        self.metrics=tk.Frame(self,bg=c['bg']);self.metrics.pack(fill='x')
        stat=self.data['stats'];season=self.data['season'];cols=4 if metrics_wide else 2
        for i,(title,key,fmt,count) in enumerate([('Винрейт','wr','{:.1f}%','results'),('KDA','kda','{:.2f}','kda_n'),('Фарм / мин','csm','{:.1f}','csm_n'),('Обзор / мин','vsm','{:.2f}','vsm_n')]):
            card=self.panel(self.metrics,16);card.grid(row=i//cols,column=i%cols,sticky='nsew',padx=(0,6),pady=(0,6))
            self.label(card,title,11,'mute').pack(anchor='w')
            v=stat[key]
            number=self.label(card,fmt.format(v).replace('.',',') if v is not None else '—',32,'fg')
            number.configure(font=(self.f['numb'],fs(32)));number.pack(anchor='w',pady=(3,3))
            detail_color='mute'
            detail=(f"{stat['wins']} побед · {stat['results']-stat['wins']} поражений" if key=='wr' and stat['results'] else f"По {stat[count]} матчам" if stat[count] else 'Нет данных')
            if self.period=='recent' and v is not None and season[key] is not None and stat['n']<season['n']:
                change=v-season[key]
                precision=2 if key in ('kda','vsm') else 1
                detail=(f"{change:+.{precision}f}"+(' п.п.' if key=='wr' else '')+' к сезону') if round(change,precision) else 'Как в сезоне'
                detail_color=('good' if change>0 else 'bad') if round(change,precision) else 'mute'
            self.label(card,detail,9,detail_color,wraplength=fs(230)).pack(anchor='w')
        for i in range(cols):self.metrics.columnconfigure(i,weight=1,uniform='metrics')
        body=tk.Frame(self,bg=c['bg']);body.pack(fill='x',pady=(10,0))
        self.matches=tk.Frame(body,bg=c['bg']);self.matches.grid(row=0,column=0,sticky='new',padx=(0,12 if wide else 0))
        side=tk.Frame(body,bg=c['bg']);side.grid(row=0 if wide else 1,column=1 if wide else 0,sticky='new',pady=(0 if wide else 14,0))
        body.columnconfigure(0,weight=3)
        if wide:body.columnconfigure(1,weight=1,minsize=fs(300))
        self.label(self.matches,'ПОСЛЕДНИЕ МАТЧИ',16,'gold',head=True).pack(anchor='w',pady=(0,7))
        match_width=width-fs(330) if wide else width
        for game in self.data['games'][:6]:self.match(self.matches,game,match_width)
        if not games:
            empty=self.panel(self.matches,24);empty.pack(fill='x')
            self.label(empty,'Матчей пока нет',17,'fg',head=True).pack(anchor='w')
            self.label(empty,'Для выбранного профиля ещё нет загруженной статистики.',10,'mute',wraplength=max(fs(250),match_width-fs(60)),justify='left').pack(anchor='w',pady=(6,0))
        self.button(self.matches,'Открыть всю историю матчей →',lambda:app.nb.select(1)).pack(anchor='w',pady=(6,0))
        self.label(side,'ЧАСТЫЕ ЧЕМПИОНЫ',15,'gold',head=True).pack(anchor='w',pady=(0,7))
        champions=self.panel(side,10);champions.pack(fill='x')
        for row in self.data['frequent']:self.champion(champions,row)
        if not self.data['frequent']:self.label(champions,'Недостаточно матчей',10,'mute').pack(anchor='w')
        pool=self.panel(side,10);pool.pack(fill='x',pady=(10,0))
        self.label(pool,'ТВОЙ ПУЛ',10,'gold').pack(anchor='w')
        configured=app.current_pool()
        for role in core.ROLES:
            line=tk.Frame(pool,bg=c['panel']);line.pack(fill='x',pady=3)
            self.image(line,'role',role,18)
            self.label(line,core.ROLE_RU[role].capitalize(),9,'mute').pack(side='left')
            self.label(line,str(len(configured.get(role,[]))),10,'fg').pack(side='right')
        self.button(pool,'Настроить пул →',lambda:app.nb.select(10)).pack(fill='x',pady=(6,0))
        self.advice(side)
        footer=tk.Frame(self,bg=c['bg']);footer.pack(fill='x',pady=(18,6))
        self.label(footer,f"Данные от {d.d.get('t','—')} · патч {d.d.get('patch','—')} · {len(games)} матчей этого профиля",9,'mute',wraplength=width-20,justify='left').pack(anchor='w')
        self.label(footer,RIOT_NOTE,8,'mute',wraplength=width-20,justify='left').pack(anchor='w',pady=(6,0))

    def rank_card(self,parent,key,title,data,fallback,column):
        from ui import TIER_RU,tier_of
        c,fs=self.c,self.app.fs
        card=self.panel(parent,10);card.grid(row=0,column=column,sticky='nsew',padx=(0,5))
        self.rank_cards[key]=card
        self.label(card,title,8,'mute',anchor='center').pack(fill='x')
        state=(data or {}).get('state','unknown')
        tier=(data or {}).get('tier')
        rank='';points='';source='Из клиента'
        if key=='arena':
            rank='Слава';points='Нет данных';source='Рангов больше нет'
        elif state=='ranked':
            division=data.get('div','')
            rank=TIER_RU.get(tier,tier)+(' '+division if division else '')
            points=f"{data['lp']} LP"
        elif state=='unranked':rank='Без ранга';source='Из клиента'
        elif state=='provisional':rank='Калибровка';source='Из клиента'
        elif fallback:
            parts=fallback.split(' · ');rank=parts[0];points=parts[1] if len(parts)>1 else ''
            tier=next((k for k,v in TIER_RU.items() if v==tier_of(fallback)),None)
            source='Сохранённые данные'
        else:rank='Нет данных';source='Ранг недоступен'
        emblem=tk.Frame(card,bg=c['panel'],height=fs(62));emblem.pack(fill='x',pady=(3,2));emblem.pack_propagate(False)
        # TFT uses its own artwork; do not substitute an unverified LoL badge.
        group='tft_emb' if key=='tft' else 'emb'
        name=TIER_RU.get(tier)
        photo=self.app.icons.get(group,name,fs(58)) if self.app.s['show']['ranks'] and name in self.app.icons.a.get(group,{}) and key!='arena' else None
        if photo:tk.Label(emblem,image=photo,bg=c['panel']).pack(expand=True)
        else:self.label(emblem,'TFT' if key=='tft' else '—',16,'gold' if key=='tft' else 'mute',anchor='center').pack(expand=True)
        rank_label=self.label(card,rank,14,'fg',anchor='center',wraplength=fs(150),justify='center');rank_label.configure(font=(self.f['font'],fs(14),'bold'));rank_label.pack(fill='x')
        self.label(card,points or '—',13,'gold' if points and key!='arena' else 'mute',anchor='center').pack(fill='x',pady=(2,0))
        self.label(card,source,7,'mute',anchor='center',wraplength=fs(135),justify='center').pack(fill='x',pady=(3,0))

    def match(self,parent,game,width):
        app,d,c,fs=self.app,self.app.data,self.c,self.app.fs
        win=game.get('w');tone='good' if win==1 else 'bad' if win==0 else 'mute'
        row=self.panel(parent,14);row.pack(fill='x',pady=(0,10))
        strip=tk.Frame(row,bg=c[tone],width=3);strip.place(x=-fs(14),y=0,relheight=1)
        left=tk.Frame(row,bg=c['panel']);left.grid(row=0,column=0,sticky='w')
        self.image(left,'champ',game.get('c'),56)
        middle=tk.Frame(row,bg=c['panel']);middle.grid(row=0,column=1,sticky='ew',padx=(0,8))
        title=tk.Frame(middle,bg=c['panel']);title.pack(anchor='w')
        self.image(title,'role',game.get('pos'),18)
        label=self.label(title,d.cn(game.get('c')),13,'fg',wraplength=max(fs(150),width-fs(430)),justify='left');label.configure(font=(self.f['font'],fs(13),'bold'));label.pack(side='left')
        queue=core.QUEUE_RU.get(game.get('q'),'Режим не указан')
        self.label(middle,queue+(' · против '+d.cn(game['opp']) if game.get('opp') else ''),8,'mute',wraplength=max(fs(150),width-fs(430)),justify='left').pack(anchor='w',pady=(2,3))
        items=tk.Frame(middle,bg=c['panel']);items.pack(anchor='w')
        for item in (game.get('it') or [])[:6]:self.image(items,'item',item,24)
        kd=tk.Frame(row,bg=c['panel']);kd.grid(row=0,column=2,sticky='e',padx=(3,10))
        self.label(kd,' / '.join(str(game[k]) if model.number(game.get(k)) else '—' for k in ('k','d','a')),18,'fg').pack(anchor='e')
        self.label(kd,'K / D / A',10,'mute').pack(anchor='e',pady=(2,4))
        self.label(kd,f"{game['csm']:.1f} CS/мин" if model.number(game.get('csm')) else 'CS —',8,'mute').pack(anchor='e')
        result=tk.Frame(row,bg=c['panel']);result.grid(row=0,column=3,sticky='ne')
        self.label(result,'ПОБЕДА' if win==1 else 'ПОРАЖЕНИЕ' if win==0 else 'НЕТ РЕЗУЛЬТАТА',9,tone).pack(anchor='e')
        duration=game.get('dur');stamp=game.get('t')
        duration=core.mmss(round(duration*60)) if model.number(duration) else '—'
        date=time.strftime('%d.%m',time.localtime(stamp)) if model.number(stamp) and stamp else ''
        self.label(result,' · '.join(x for x in (duration,date) if x),8,'mute').pack(anchor='e',pady=(2,0))
        row.columnconfigure(1,weight=1)
        for widget in (label,left):
            widget.configure(cursor='hand2');widget.bind('<Button-1>',lambda e,g=game:self.open_champion(g['c'],g.get('pos')))

    def champion(self,parent,row):
        app,c=self.app,self.c
        line=tk.Frame(parent,bg=c['panel']);line.pack(fill='x',pady=8)
        self.image(line,'champ',row['champion'],42)
        main=tk.Frame(line,bg=c['panel']);main.pack(side='left',fill='x',expand=True)
        name=self.label(main,app.data.cn(row['champion']),10,'fg',cursor='hand2',wraplength=self.app.fs(130));name.pack(anchor='w')
        name.bind('<Button-1>',lambda e:self.open_champion(row['champion'],row['role']))
        s=row['stats'];self.label(main,f"{s['n']} игр"+(' · мало данных' if s['n']<5 else ''),8,'mute').pack(anchor='w')
        self.label(line,f"{s['wr']:.0f}%" if s['wr'] is not None else '—',13,'gold').pack(side='right')

    def advice(self,parent):
        recent,season=self.data['recent'],self.data['season']
        worst=(None,0)
        if recent['n']>=5 and season['n']>recent['n']:
            for key in ('wr','kda','csm','vsm'):
                count='results' if key=='wr' else key+'_n'
                if recent[count]<5 or season[count]<=recent[count]:continue
                a,b=recent[key],season[key]
                if a is not None and b and (b-a)/b>worst[1]:worst=key,(b-a)/b
        if not worst[0]:return
        box=self.panel(parent,10);box.pack(fill='x',pady=(10,0))
        self.label(box,'НА ЧТО ОБРАТИТЬ ВНИМАНИЕ',9,'gold',wraplength=self.app.fs(240)).pack(anchor='w')
        self.label(box,self.app.TIPS[worst[0]],9,'mute',wraplength=self.app.fs(240),justify='left').pack(anchor='w',pady=(6,0))
